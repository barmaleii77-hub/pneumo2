# -*- coding: utf-8 -*-
"""pneumo_solver_ui.diagnostics_entrypoint

Единая точка сборки **полной диагностики (Send Bundle)**.

Зачем
-----
Проектное требование (R59):
- должна существовать *одна* кнопка «Сохранить полную диагностику (ZIP)»;
- автосейв при crash/exit/watchdog должен собирать **тот же** архив тем же методом;
- настройки диагностики должны жить в persistent_state (Streamlit autosave), чтобы
  их видел не только UI-процесс, но и внешний watchdog/GUI после выхода.

Этот модуль:
- извлекает DiagnosticsConfig из st.session_state **или** из autosave_profile.json;
- выставляет совместимые env-флаги (для legacy-скриптов);
- вызывает `pneumo_solver_ui.send_bundle.make_send_bundle`;
- пишет last_bundle_meta.json рядом с архивами.

Best-effort: любая ошибка сборки не должна ронять UI/launcher.
"""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _repo_root_from_here() -> Path:
    # .../pneumo_solver_ui/diagnostics_entrypoint.py -> parents[1] == repo root
    return Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _atomic_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8", errors="replace")
        os.replace(str(tmp), str(path))
    except Exception:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", errors="replace")
        except Exception:
            return


def _parse_bool(v: Any, default: bool) -> bool:
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"0", "false", "no", "off", ""}:
            return False
        if s in {"1", "true", "yes", "on"}:
            return True
    return bool(default)


def _parse_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return int(default)
        if isinstance(v, bool):
            return int(default)
        return int(float(str(v).strip()))
    except Exception:
        return int(default)


def _sanitize_tag(tag: Optional[str], *, max_len: int = 48) -> str:
    if not tag:
        return ""
    s = str(tag).strip()
    if not s:
        return ""
    # allow only filesystem-safe subset
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "", s)
    s = s.strip("._-")
    if len(s) > max_len:
        s = s[:max_len]
    return s


@dataclass
class DiagnosticsConfig:
    # where to put bundles
    out_dir: str = "send_bundles"

    # file retention + safety
    keep_last_n: int = 10
    max_file_mb: int = 200

    # heavy extras
    include_workspace_osc: bool = False

    # preflight/self_check/property_invariants suite
    run_selfcheck_before_bundle: bool = True
    selfcheck_level: str = "standard"  # quick|standard|full

    # autosave triggers
    autosave_on_crash: bool = True
    autosave_on_exit: bool = True
    autosave_on_watchdog: bool = True

    # optional naming/help
    tag: str = ""
    reason: str = ""

    # internal
    _source: str = "defaults"

    def resolved_out_dir(self, repo_root: Path) -> Path:
        s = (self.out_dir or "").strip()
        if not s:
            return (repo_root / "send_bundles").resolve()
        try:
            p = Path(s).expanduser()
            if p.is_absolute():
                return p.resolve()
        except Exception:
            pass
        return (repo_root / s).resolve()


@dataclass
class DiagnosticsBuildResult:
    ok: bool
    zip_path: Optional[Path] = None
    message: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


def _load_persisted_state(repo_root: Path) -> Tuple[Dict[str, Any], str]:
    """Load autosave_profile.json (UI persistence) without importing Streamlit."""
    try:
        from pneumo_solver_ui.ui_persistence import pick_state_dir, load_autosave

        sd = pick_state_dir(app_here=(repo_root / "pneumo_solver_ui"))
        if sd is None:
            return {}, "no_state_dir"
        data, err = load_autosave(sd)
        if err:
            return (data or {}), str(err)
        return (data or {}), ""
    except Exception:
        return {}, traceback.format_exc(limit=5)


def load_diagnostics_config(
    repo_root: Optional[Path] = None,
    *,
    session_state: Optional[Dict[str, Any]] = None,
) -> DiagnosticsConfig:
    """Load DiagnosticsConfig from (priority): session_state -> autosave_profile.json -> defaults."""

    repo_root = (repo_root or _repo_root_from_here()).resolve()
    cfg = DiagnosticsConfig()

    src: Dict[str, Any] = {}
    src_name = "defaults"
    if session_state is not None:
        try:
            src = dict(session_state)
            src_name = "session_state"
        except Exception:
            src = {}
    else:
        st, err = _load_persisted_state(repo_root)
        src = st
        src_name = "autosave" if st else ("autosave_error" if err else "defaults")

    # read values (all keys are prefixed diag_ and persisted by ui_persistence)
    cfg.out_dir = str(src.get("diag_output_dir", cfg.out_dir) or cfg.out_dir)
    cfg.keep_last_n = _parse_int(src.get("diag_keep_last_n", cfg.keep_last_n), cfg.keep_last_n)
    cfg.max_file_mb = _parse_int(src.get("diag_max_file_mb", cfg.max_file_mb), cfg.max_file_mb)
    cfg.include_workspace_osc = _parse_bool(src.get("diag_include_workspace_osc", cfg.include_workspace_osc), cfg.include_workspace_osc)

    cfg.run_selfcheck_before_bundle = _parse_bool(
        src.get("diag_run_selfcheck", cfg.run_selfcheck_before_bundle),
        cfg.run_selfcheck_before_bundle,
    )
    lvl = str(src.get("diag_selfcheck_level", cfg.selfcheck_level) or cfg.selfcheck_level).strip().lower()
    if lvl not in {"quick", "standard", "full"}:
        lvl = cfg.selfcheck_level
    cfg.selfcheck_level = lvl

    cfg.autosave_on_crash = _parse_bool(src.get("diag_autosave_on_crash", cfg.autosave_on_crash), cfg.autosave_on_crash)
    cfg.autosave_on_exit = _parse_bool(src.get("diag_autosave_on_exit", cfg.autosave_on_exit), cfg.autosave_on_exit)
    cfg.autosave_on_watchdog = _parse_bool(src.get("diag_autosave_on_watchdog", cfg.autosave_on_watchdog), cfg.autosave_on_watchdog)

    cfg.tag = str(src.get("diag_tag", cfg.tag) or "").strip()
    cfg.reason = str(src.get("diag_reason", cfg.reason) or "").strip()
    cfg._source = src_name
    return cfg


def export_config_to_env(cfg: DiagnosticsConfig) -> None:
    """Export config to env vars so legacy tools (and child procs) can reuse settings."""
    try:
        os.environ["PNEUMO_BUNDLE_KEEP_LAST_N"] = str(int(cfg.keep_last_n))
        os.environ["PNEUMO_BUNDLE_MAX_FILE_MB"] = str(int(cfg.max_file_mb))
        os.environ["PNEUMO_BUNDLE_INCLUDE_WORKSPACE"] = "1" if cfg.include_workspace_osc else "0"

        os.environ["PNEUMO_BUNDLE_RUN_SELFCHECK"] = "1" if cfg.run_selfcheck_before_bundle else "0"
        os.environ["PNEUMO_BUNDLE_SELFCHECK_LEVEL"] = str(cfg.selfcheck_level)

        os.environ["PNEUMO_AUTOSAVE_BUNDLE_ON_CRASH"] = "1" if cfg.autosave_on_crash else "0"
        os.environ["PNEUMO_AUTOSAVE_BUNDLE_ON_EXIT"] = "1" if cfg.autosave_on_exit else "0"
        os.environ["PNEUMO_AUTOSAVE_BUNDLE_ON_WATCHDOG"] = "1" if cfg.autosave_on_watchdog else "0"

        # legacy watchdog env names (older scripts)
        os.environ["PNEUMO_SEND_BUNDLE_KEEP_LAST_N"] = str(int(cfg.keep_last_n))
        os.environ["PNEUMO_SEND_BUNDLE_MAX_FILE_MB"] = str(int(cfg.max_file_mb))
        os.environ["PNEUMO_SEND_BUNDLE_INCLUDE_OSC"] = "1" if cfg.include_workspace_osc else "0"
    except Exception:
        return


def _write_reason_note(out_dir: Path, *, trigger: str, release: str, reason: str) -> None:
    try:
        note = (reason or "").strip()
        if not note:
            return
        p = out_dir / "_user_reason.txt"
        payload = f"release={release}\ntrigger={trigger}\nlocal_time={_now_iso()}\n\n{note}\n"
        _atomic_write_text(p, payload)
    except Exception:
        return


def _write_last_meta(out_dir: Path, meta: Dict[str, Any]) -> None:
    try:
        _atomic_write_text(out_dir / "last_bundle_meta.json", json.dumps(meta, ensure_ascii=False, indent=2, default=str))
    except Exception:
        return


def read_last_meta(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    repo_root = (repo_root or _repo_root_from_here()).resolve()
    out_dir = (repo_root / "send_bundles").resolve()
    p = out_dir / "last_bundle_meta.json"
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return {}


def build_full_diagnostics_bundle(
    *,
    trigger: str,
    repo_root: Optional[Path] = None,
    session_state: Optional[Dict[str, Any]] = None,
    primary_session_dir: Optional[Path] = None,
    open_folder: bool = False,
) -> DiagnosticsBuildResult:
    """Build full diagnostics ZIP on disk.

    This is the *single* entrypoint that UI + crash_guard + watchdog + send_results_gui should use.
    """
    repo_root = (repo_root or _repo_root_from_here()).resolve()

    try:
        from pneumo_solver_ui.release_info import get_release

        release = get_release(default=os.environ.get("PNEUMO_RELEASE", ""))
    except Exception:
        release = os.environ.get("PNEUMO_RELEASE", "")

    cfg = load_diagnostics_config(repo_root, session_state=session_state)
    export_config_to_env(cfg)

    out_dir = cfg.resolved_out_dir(repo_root)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # If caller did not pass primary_session_dir, try env PNEUMO_SESSION_DIR
    if primary_session_dir is None:
        env_sd = (os.environ.get("PNEUMO_SESSION_DIR") or "").strip()
        if env_sd:
            try:
                primary_session_dir = Path(env_sd).expanduser().resolve()
            except Exception:
                primary_session_dir = Path(env_sd)

    # Reason note (human-readable) — included by bundler (it copies out_dir sidecars)
    _write_reason_note(out_dir, trigger=str(trigger), release=str(release), reason=str(cfg.reason))

    tag = _sanitize_tag(cfg.tag)
    tag = tag or _sanitize_tag(str(trigger))

    meta: Dict[str, Any] = {
        "schema": "pneumo_diagnostics_bundle_meta",
        "schema_version": "1.0.0",
        "ts": _now_iso(),
        "trigger": str(trigger),
        "release": str(release),
        "config_source": str(cfg._source),
        "config": {
            "out_dir": str(cfg.out_dir),
            "keep_last_n": int(cfg.keep_last_n),
            "max_file_mb": int(cfg.max_file_mb),
            "include_workspace_osc": bool(cfg.include_workspace_osc),
            "run_selfcheck_before_bundle": bool(cfg.run_selfcheck_before_bundle),
            "selfcheck_level": str(cfg.selfcheck_level),
            "autosave_on_crash": bool(cfg.autosave_on_crash),
            "autosave_on_exit": bool(cfg.autosave_on_exit),
            "autosave_on_watchdog": bool(cfg.autosave_on_watchdog),
            "tag": str(cfg.tag),
        },
    }

    try:
        from pneumo_solver_ui.send_bundle import make_send_bundle

        zp = make_send_bundle(
            repo_root=repo_root,
            out_dir=out_dir,
            keep_last_n=int(cfg.keep_last_n),
            max_file_mb=int(cfg.max_file_mb),
            include_workspace_osc=bool(cfg.include_workspace_osc),
            primary_session_dir=primary_session_dir,
            tag=tag or None,
            operator_note=str(cfg.reason or "").strip() or None,
        )
        zip_path = Path(zp).resolve()

        # file stats
        try:
            st = zip_path.stat()
            meta["zip"] = {
                "path": str(zip_path),
                "name": str(zip_path.name),
                "size_bytes": int(st.st_size),
                "mtime": float(st.st_mtime),
            }
        except Exception:
            meta["zip"] = {"path": str(zip_path), "name": str(zip_path.name)}

        meta["ok"] = True
        _write_last_meta(out_dir, meta)

        if open_folder:
            try:
                # Best-effort convenience
                import sys
                if sys.platform.startswith("win"):
                    os.startfile(str(out_dir))  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", str(out_dir)])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", str(out_dir)])
            except Exception:
                pass

        return DiagnosticsBuildResult(ok=True, zip_path=zip_path, message="OK", meta=meta)
    except Exception as e:
        meta["ok"] = False
        meta["error"] = f"{type(e).__name__}: {e}"
        meta["traceback"] = traceback.format_exc(limit=30)
        _write_last_meta(out_dir, meta)
        try:
            _atomic_write_text(out_dir / "last_bundle_error.txt", meta["traceback"])
        except Exception:
            pass
        return DiagnosticsBuildResult(ok=False, zip_path=None, message=str(meta.get("error") or "failed"), meta=meta)
