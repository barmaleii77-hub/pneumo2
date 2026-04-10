#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""postmortem_watchdog.py

Зачем
-----
Это внешний (отдельный) процесс-«сторож» для максимальной надёжности доставки
артефактов в чат.

Проблема: при аварийном завершении Streamlit/launcher (например, kill процесса),
обычный atexit-хук может не успеть отработать, и пользователь не получит ZIP.

Решение:
- watchdog мониторит PID Streamlit процесса
- опционально мониторит PID launcher процесса
- если Streamlit остановился, а launcher уже мёртв, watchdog:
    1) проверяет marker-файл UI-сессии ("_send_bundle_done.json")
    2) если marker отсутствует — строит Send Bundle
    3) (опционально) открывает 1-кнопочное окно Copy ZIP

Важно
------
Watchdog не должен мешать «нормальному» сценарию:
- когда launcher жив, он сам откроет send_results_gui
- watchdog в этом случае молча завершается

Запуск (обычно автоматически из START_PNEUMO_UI.pyw)
----------------------------------------------------
python -m pneumo_solver_ui.tools.postmortem_watchdog --target_pid 1234 --launcher_pid 5678

"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _pyw_for_windows(py_exe: str) -> str:
    """Best effort: if running under python.exe, prefer pythonw.exe for GUI."""
    try:
        p = Path(py_exe)
        if p.name.lower() == "python.exe":
            cand = p.with_name("pythonw.exe")
            if cand.exists():
                return str(cand)
    except Exception:
        pass
    return str(py_exe)


def _pid_alive_unix(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _pid_alive_windows(pid: int) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid))
        if not handle:
            return False

        code = wintypes.DWORD()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        if not ok:
            return False
        return int(code.value) == STILL_ACTIVE
    except Exception:
        return False


def pid_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        pid_i = int(pid)
    except Exception:
        return False
    if pid_i <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid_i)
    return _pid_alive_unix(pid_i)


def _log(path: Path, msg: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _bundle_summary_fields(meta: object) -> dict[str, object]:
    meta_dict = dict(meta or {}) if isinstance(meta, dict) else {}
    anim_summary = dict(meta_dict.get("anim_latest_summary") or {}) if isinstance(meta_dict.get("anim_latest_summary"), dict) else {}
    lines = [str(x) for x in (meta_dict.get("summary_lines") or []) if str(x).strip()]
    diag_path = str(meta_dict.get("anim_pointer_diagnostics_path") or "").strip()
    out = {
        "summary_lines": lines,
        "anim_pointer_diagnostics_path": diag_path,
    }
    for key in (
        "scenario_kind",
        "ring_closure_policy",
        "ring_closure_applied",
        "ring_seam_open",
        "ring_seam_max_jump_m",
        "ring_raw_seam_max_jump_m",
    ):
        if anim_summary.get(key) is not None:
            out[key] = anim_summary.get(key)
    return out


def _log_bundle_summary(path: Path, meta: object) -> None:
    summary = _bundle_summary_fields(meta)
    for line in summary["summary_lines"]:
        _log(path, f"[watchdog] {line}")
    diag_path = str(summary.get("anim_pointer_diagnostics_path") or "").strip()
    if diag_path:
        _log(path, f"[watchdog] Anim pointer diagnostics: {diag_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Postmortem watchdog: ensure Send Bundle after crash/kill")
    ap.add_argument("--target_pid", type=int, required=True, help="PID streamlit/python процесса")
    ap.add_argument("--launcher_pid", type=int, default=None, help="PID launcher процесса (если жив — watchdog не вмешивается)")
    ap.add_argument("--session_dir", default=None, help="UI session dir (runs/ui_sessions/UI_*)")
    ap.add_argument("--out_dir", default="send_bundles", help="Каталог send bundles (относительно repo root)")
    ap.add_argument("--poll_s", type=float, default=0.5, help="Период опроса PID")
    ap.add_argument("--grace_s", type=float, default=1.0, help="Пауза после остановки target перед действиями")
    ap.add_argument("--open_send_gui", action="store_true", help="Открыть send_results_gui при вмешательстве")
    args = ap.parse_args()

    repo = _repo_root()

    # R59: load diagnostics settings from persistent_state so watchdog sees UI changes.
    cfg = None
    try:
        from pneumo_solver_ui.diagnostics_entrypoint import load_diagnostics_config

        cfg = load_diagnostics_config(repo)
    except Exception:
        cfg = None

    # Determine out_dir (CLI can override, otherwise use persisted config).
    def _resolve_out_dir(raw: str) -> Path:
        s = (raw or "").strip()
        if not s:
            return (repo / "send_bundles").resolve()
        try:
            p = Path(s).expanduser()
            if p.is_absolute():
                return p.resolve()
        except Exception:
            pass
        return (repo / s).resolve()

    if str(args.out_dir).strip() and str(args.out_dir).strip() != "send_bundles":
        out_dir = _resolve_out_dir(str(args.out_dir))
    elif cfg is not None:
        try:
            out_dir = cfg.resolved_out_dir(repo)
        except Exception:
            out_dir = (repo / "send_bundles").resolve()
    else:
        out_dir = (repo / "send_bundles").resolve()

    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "_postmortem_watchdog.log"

    # resolve session dir
    session_dir = args.session_dir or os.environ.get("PNEUMO_SESSION_DIR")
    p_session: Optional[Path] = None
    if session_dir:
        try:
            p_session = Path(session_dir).expanduser().resolve()
        except Exception:
            p_session = Path(session_dir)

    _log(log_path, f"[watchdog] start target_pid={args.target_pid} launcher_pid={args.launcher_pid} session_dir={p_session}")

    # Wait for target to exit
    try:
        while pid_alive(args.target_pid):
            time.sleep(max(0.05, float(args.poll_s)))
    except Exception:
        _log(log_path, "[watchdog] wait loop failed:\n" + traceback.format_exc())

    _log(log_path, "[watchdog] target exited")
    try:
        time.sleep(max(0.0, float(args.grace_s)))
    except Exception:
        pass

    # If launcher still alive, assume it will handle post-exit steps.
    try:
        if pid_alive(args.launcher_pid):
            _log(log_path, "[watchdog] launcher alive -> exiting (normal path)")
            return 0
    except Exception:
        pass

    # If marker exists -> do nothing.
    marker_path: Optional[Path] = None
    try:
        if p_session is not None:
            marker_path = p_session / "_send_bundle_done.json"
            if marker_path.exists():
                _log(log_path, f"[watchdog] marker exists -> bundle already built: {marker_path}")
                return 0
    except Exception:
        _log(log_path, "[watchdog] marker check failed:\n" + traceback.format_exc())

    # Build send bundle (unified entrypoint)
    try:
        # Respect autosave toggle (if config loaded). Default: enabled.
        if cfg is not None and hasattr(cfg, "autosave_on_watchdog"):
            if not bool(getattr(cfg, "autosave_on_watchdog", True)):
                _log(log_path, "[watchdog] autosave_on_watchdog disabled -> skipping bundle")
                return 0

        from pneumo_solver_ui.diagnostics_entrypoint import build_full_diagnostics_bundle

        # If CLI overrides out_dir, pass a full session_state override dict (so other fields stay consistent).
        ss_override = None
        if str(args.out_dir).strip() and str(args.out_dir).strip() != "send_bundles":
            try:
                # merge: persisted cfg + override output dir
                if cfg is not None:
                    ss_override = {
                        "diag_output_dir": str(args.out_dir),
                        "diag_keep_last_n": int(getattr(cfg, "keep_last_n", 10)),
                        "diag_max_file_mb": int(getattr(cfg, "max_file_mb", 200)),
                        "diag_include_workspace_osc": bool(getattr(cfg, "include_workspace_osc", False)),
                        "diag_run_selfcheck": bool(getattr(cfg, "run_selfcheck_before_bundle", True)),
                        "diag_selfcheck_level": str(getattr(cfg, "selfcheck_level", "standard")),
                        "diag_autosave_on_crash": bool(getattr(cfg, "autosave_on_crash", True)),
                        "diag_autosave_on_exit": bool(getattr(cfg, "autosave_on_exit", True)),
                        "diag_autosave_on_watchdog": bool(getattr(cfg, "autosave_on_watchdog", True)),
                        "diag_tag": str(getattr(cfg, "tag", "")),
                        "diag_reason": str(getattr(cfg, "reason", "")),
                    }
                else:
                    ss_override = {"diag_output_dir": str(args.out_dir)}
            except Exception:
                ss_override = {"diag_output_dir": str(args.out_dir)}

        res = build_full_diagnostics_bundle(
            trigger="watchdog",
            repo_root=repo,
            session_state=ss_override,
            primary_session_dir=p_session,
            open_folder=False,
        )

        if res.ok and res.zip_path:
            _log(log_path, f"[watchdog] bundle OK: {res.zip_path}")
            _log_bundle_summary(log_path, getattr(res, "meta", {}))
        else:
            _log(log_path, "[watchdog] bundle FAILED: " + (res.message or "unknown"))
            _log_bundle_summary(log_path, getattr(res, "meta", {}))
            try:
                tb = (res.meta or {}).get("traceback")
                if tb:
                    _log(log_path, str(tb))
            except Exception:
                pass

    except Exception:
        _log(log_path, "[watchdog] build failed:\n" + traceback.format_exc())

    # Open GUI (only when watchdog intervened)
    if args.open_send_gui:
        try:
            py_for_gui = sys.executable
            if os.name == "nt":
                py_for_gui = _pyw_for_windows(sys.executable)
            send_gui = repo / "pneumo_solver_ui" / "tools" / "send_results_gui.py"
            subprocess.Popen([str(py_for_gui), str(send_gui)], cwd=str(repo), env=os.environ.copy())
            _log(log_path, "[watchdog] opened send_results_gui")
        except Exception:
            _log(log_path, "[watchdog] failed to open send_results_gui:\n" + traceback.format_exc())

    # Run Registry event (best-effort)
    try:
        from pneumo_solver_ui.run_registry import append_event

        append_event(
            {
                "event": "watchdog_intervened",
                "target_pid": int(args.target_pid),
                "launcher_pid": int(args.launcher_pid) if args.launcher_pid else None,
                "session_dir": str(p_session) if p_session else None,
                "release": os.environ.get("PNEUMO_RELEASE", "R54"),
                "ts": time.time(),
                **_bundle_summary_fields(getattr(locals().get("res"), "meta", {})),
            }
        )
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
