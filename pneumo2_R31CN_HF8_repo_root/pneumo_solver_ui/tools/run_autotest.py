#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_autotest.py

Автономная система тестирования (Autotest Harness) + максимально полный сбор артефактов.

Что делает
----------
Один запуск создаёт артефакт прогона (папка + опциональный ZIP) с:
  - результатами ключевых проверок (compileall/self_check/pytest/...)
  - stdout/stderr каждого шага
  - снимком окружения (pip freeze/check, платформа, python, ...)
  - структурированной лентой событий (autotest_events.jsonl)
  - проверкой качества логов (loglint)
  - вариативным smoke (fuzz_smoke) для раннего ловления неустойчивостей
  - манифестом файлов с SHA256
  - reproduce-скриптами (bat/sh) для воспроизведения

Скрипт НЕ модифицирует исходники. Он пишет только в pneumo_solver_ui/autotest_runs/.

Windows:
  RUN_AUTOTEST_WINDOWS.bat

Linux/macOS:
  ./RUN_AUTOTEST_LINUX.sh [quick|standard|full]

"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import secrets
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pneumo_solver_ui.entrypoints import canonical_streamlit_entrypoint


try:
    from pneumo_solver_ui.release_info import get_release
    HARNESS_RELEASE = get_release()
except Exception:
    HARNESS_RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"

LOG_SCHEMA = "harness"
LOG_SCHEMA_VERSION = "1.2.0"



@dataclass
class CmdResult:
    cmd: list[str]
    returncode: int
    duration_s: float
    stdout: str
    stderr: str
    sys_before: dict | None = None
    sys_after: dict | None = None


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _to_jsonable(x: Any) -> Any:
    """Best-effort преобразование к JSON-совместимому виду.

    Важно для логов/метаданных: мы не хотим, чтобы логирование падало
    из-за Path/bytes/Exception/numpy/pandas и т.п.

    Также убираем NaN/Inf, чтобы JSONL был строгим JSON.
    """
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return bool(x)
        if isinstance(x, int):
            return int(x)
        if isinstance(x, float):
            try:
                if not math.isfinite(float(x)):
                    return None
            except Exception:
                return None
            return float(x)
        if isinstance(x, str):
            return x
        if isinstance(x, Path):
            return str(x)
        if isinstance(x, bytes):
            try:
                return x.decode("utf-8", errors="replace")
            except Exception:
                return repr(x)

        # numpy scalar
        try:
            import numpy as _np  # type: ignore

            if isinstance(x, _np.generic):
                return _to_jsonable(x.item())
        except Exception:
            pass

        # array-like
        if hasattr(x, "tolist"):
            try:
                return _to_jsonable(x.tolist())  # type: ignore[attr-defined]
            except Exception:
                pass

        if isinstance(x, dict):
            return {str(k): _to_jsonable(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [_to_jsonable(v) for v in list(x)]
        if isinstance(x, Exception):
            return repr(x)

        return str(x)
    except Exception:
        return repr(x)


def _json_dumps(obj: Any, indent: int | None = None) -> str:
    """Безопасный json.dumps для логов/артефактов."""
    try:
        return json.dumps(_to_jsonable(obj), ensure_ascii=False, indent=indent, allow_nan=False)
    except Exception:
        try:
            return json.dumps({"_nonserializable": repr(obj)}, ensure_ascii=False, indent=indent, allow_nan=False)
        except Exception:
            return "{}"


def _safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def _safe_write_json(path: Path, obj: Any) -> None:
    _safe_write_text(path, _json_dumps(obj, indent=2))


def _append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(_json_dumps(obj) + "\n")


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _sys_snapshot() -> dict:
    """Короткий снимок CPU/RAM — best effort."""
    snap: dict[str, Any] = {"ts": _now_iso()}
    try:
        import psutil  # type: ignore

        snap["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        try:
            snap["virtual_memory"] = psutil.virtual_memory()._asdict()
            snap["swap_memory"] = psutil.swap_memory()._asdict()
        except Exception:
            pass
        try:
            p = psutil.Process()
            snap["proc_memory"] = p.memory_info()._asdict()
            snap["proc_cpu_times"] = p.cpu_times()._asdict()
        except Exception:
            pass
    except Exception:
        snap["psutil_error"] = traceback.format_exc()
    return _to_jsonable(snap)


def _subproc_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONFAULTHANDLER", "1")
    return env


def _run(cmd: list[str], cwd: Path, timeout_s: Optional[float] = None) -> CmdResult:
    sys_before = _sys_snapshot()
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=_subproc_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        dt = time.perf_counter() - t0
        sys_after = _sys_snapshot()
        return CmdResult(
            cmd=[str(x) for x in cmd],
            returncode=int(proc.returncode),
            duration_s=float(dt),
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            sys_before=sys_before,
            sys_after=sys_after,
        )
    except subprocess.TimeoutExpired as e:
        dt = time.perf_counter() - t0
        sys_after = _sys_snapshot()
        so = e.stdout
        se = e.stderr
        if isinstance(so, bytes):
            so = so.decode(errors="replace")
        if isinstance(se, bytes):
            se = se.decode(errors="replace")
        return CmdResult(
            cmd=[str(x) for x in cmd],
            returncode=124,
            duration_s=float(dt),
            stdout=str(so or ""),
            stderr=str(se or "TIMEOUT"),
            sys_before=sys_before,
            sys_after=sys_after,
        )
    except Exception:
        dt = time.perf_counter() - t0
        sys_after = _sys_snapshot()
        return CmdResult(
            cmd=[str(x) for x in cmd],
            returncode=125,
            duration_s=float(dt),
            stdout="",
            stderr=traceback.format_exc(),
            sys_before=sys_before,
            sys_after=sys_after,
        )


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_dir():
                continue
            arc = p.relative_to(src_dir)
            z.write(p, arcname=str(arc))


def _pick_python(repo_root: Path) -> str:
    """Prefer venv python (Windows/Linux), else fallback to current interpreter."""
    candidates = [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


def _pick_free_port() -> int:
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _ui_smoke_streamlit(python_exe: Path, repo_root: Path, app_path: Path, out_dir: Path, timeout_s: float = 30.0) -> dict:
    """Headless smoke-test Streamlit UI.

    - стартуем streamlit в headless
    - делаем HTTP GET / через stdlib urllib

    Задача: поймать критические ошибки уровня import/NameError и убедиться,
    что сервер реально поднялся.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    port = _pick_free_port()
    url = f"http://127.0.0.1:{port}"

    cmd = [
        str(python_exe),
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]

    meta: dict[str, Any] = {
        "cmd": cmd,
        "url": url,
        "timeout_s": float(timeout_s),
        "started": False,
        "http_ok": False,
        "http_status": None,
        "returncode": None,
        "duration_s": None,
        "exception": None,
    }

    t0 = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=_subproc_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    html_snippet: str | None = None

    try:
        import urllib.request
        import urllib.error

        while time.perf_counter() - t0 < timeout_s:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(url, timeout=1.0) as r:
                    meta["http_status"] = int(getattr(r, "status", 200))
                    meta["http_ok"] = True
                    meta["started"] = True
                    try:
                        html_snippet = (r.read(200000) or b"").decode("utf-8", errors="replace")
                    except Exception:
                        html_snippet = None
                    break
            except urllib.error.HTTPError as e:
                # даже 404 означает, что сервер жив и слушает
                meta["http_status"] = int(getattr(e, "code", 0) or 0)
                meta["http_ok"] = True
                meta["started"] = True
                break
            except Exception as e:
                meta["exception"] = repr(e)
                time.sleep(0.5)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

        try:
            out, _ = proc.communicate(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            out, _ = proc.communicate(timeout=10)

        meta["returncode"] = proc.returncode
        meta["duration_s"] = float(time.perf_counter() - t0)

        _safe_write_text(out_dir / "streamlit_combined.log", out or "")
        if html_snippet is not None:
            _safe_write_text(out_dir / "root_html_snippet.html", html_snippet)
        _safe_write_json(out_dir / "ui_smoke_meta.json", meta)

    return meta


def _collect_manifest(run_dir: Path, out_path: Path) -> None:
    """Создать манифест файлов прогона с sha256."""
    rows: list[dict[str, Any]] = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_dir():
            continue
        if p.resolve() == out_path.resolve():
            continue
        try:
            rows.append(
                {
                    "path": str(p.relative_to(run_dir)).replace("\\", "/"),
                    "size": int(p.stat().st_size),
                    "sha256": _sha256_file(p),
                }
            )
        except Exception as e:
            rows.append({"path": str(p), "error": repr(e)})
    _safe_write_json(out_path, {"generated_at": _now_iso(), "files": rows})


def _write_reproduce_scripts(run_dir: Path, level: str) -> None:
    """Положить в артефакт скрипты для воспроизведения."""
    # run_dir = repo_root/pneumo_solver_ui/autotest_runs/RUN_xxx...
    # repo_root = run_dir/../../..
    rel_up = "..\\..\\.."  # for Windows

    win = "\n".join(
        [
            "@echo off",
            "chcp 65001 > nul",
            "set PYTHONUTF8=1",
            "set PYTHONIOENCODING=utf-8",
            "cd /d %~dp0\\" + rel_up,
            "echo Reproducing autotest...",
            "if exist .venv\\Scripts\\activate (call .venv\\Scripts\\activate)",
            "python pneumo_solver_ui\\tools\\run_autotest.py --level " + level,
            "pause",
            "",
        ]
    )

    sh = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'DIR="$(cd "$(dirname "$0")" && pwd)"',
            'REPO_ROOT="$(cd "$DIR/../../.." && pwd)"',
            'cd "$REPO_ROOT"',
            'echo "Reproducing autotest..."',
            'if [ -x "$REPO_ROOT/.venv/bin/python" ]; then',
            f'  "$REPO_ROOT/.venv/bin/python" pneumo_solver_ui/tools/run_autotest.py --level {level}',
            'else',
            f'  python3 pneumo_solver_ui/tools/run_autotest.py --level {level}',
            'fi',
            "",
        ]
    )

    _safe_write_text(run_dir / "reproduce_windows.bat", win)
    p_sh = run_dir / "reproduce_linux.sh"
    _safe_write_text(p_sh, sh)
    try:
        os.chmod(p_sh, 0o755)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["quick", "standard", "full"], default="standard")
    ap.add_argument(
        "--out_root",
        default=None,
        help="Куда складывать autotest_runs/ (по умолчанию pneumo_solver_ui/autotest_runs)",
    )
    ap.add_argument("--no_zip", action="store_true", help="Не упаковывать итоговую папку в zip")
    ap.add_argument("--ui_smoke_timeout_s", type=float, default=30.0)
    ap.add_argument("--pytest_args", default="", help="Доп. аргументы pytest (строкой)")
    args = ap.parse_args()

    this_file = Path(__file__).resolve()
    pneumo_dir = this_file.parent.parent  # pneumo_solver_ui/
    repo_root = pneumo_dir.parent

    python_exe = _pick_python(repo_root)
    python_exe_path = Path(python_exe)

    out_root = Path(args.out_root).expanduser().resolve() if args.out_root else (pneumo_dir / "autotest_runs").resolve()
    run_dir = out_root / f"RUN_{_ts()}_autotest_{args.level}"
    run_id = run_dir.name
    run_dir.mkdir(parents=True, exist_ok=True)

    # --- structured event log for this harness ---
    events_path = run_dir / "autotest_events.jsonl"
    seq_counter = 0

    def ev(event: str, **fields: Any) -> None:
        nonlocal seq_counter
        seq_counter += 1
        _append_jsonl(
            events_path,
            {
                "schema": LOG_SCHEMA,
                "schema_version": LOG_SCHEMA_VERSION,
                "event_id": f"h_{seq_counter:06d}_{secrets.token_hex(4)}",
                "seq": int(seq_counter),
                "ts": _now_iso(),
                "event": event,
                "release": HARNESS_RELEASE,
                "run_id": run_id,
                "trace_id": run_id,
                "level": args.level,
                "pid": os.getpid(),
                **fields,
            },
        )

    meta: dict[str, Any] = {
        "ts": _ts(),
        "release": HARNESS_RELEASE,
        "run_id": run_id,
        "level": args.level,
        "python_exe": python_exe,
        "sys_executable": sys.executable,
        "platform": platform.platform(),
        "python": sys.version,
        "cwd": os.getcwd(),
        "repo_root": str(repo_root),
        "pneumo_dir": str(pneumo_dir),
        "argv": sys.argv,
    }
    _safe_write_json(run_dir / "meta.json", meta)
    ev("start", python_exe=python_exe, platform=meta["platform"])

    # R49: Run Registry start (best-effort)
    rr_token = None
    try:
        from pneumo_solver_ui.run_registry import env_context, start_run

        rr_token = start_run(
            "autotest",
            run_id,
            run_dir=str(run_dir),
            level=args.level,
            release=HARNESS_RELEASE,
            env=env_context(),
        )
    except Exception:
        rr_token = None


    # Изоляция логов/артефактов под конкретный прогон.
    # Это критично для strict loglint: в папке не должны смешиваться логи прошлых запусков.
    logs_live = run_dir / "logs_live"
    ws_live = run_dir / "workspace_live"
    logs_live.mkdir(parents=True, exist_ok=True)
    ws_live.mkdir(parents=True, exist_ok=True)

    os.environ["PNEUMO_LOG_DIR"] = str(logs_live)
    os.environ["PNEUMO_WORKSPACE_DIR"] = str(ws_live)
    os.environ["PNEUMO_RUN_ID"] = str(run_id)
    os.environ["PNEUMO_TRACE_ID"] = str(run_id)
    ev("env_override", PNEUMO_LOG_DIR=str(logs_live), PNEUMO_WORKSPACE_DIR=str(ws_live), PNEUMO_RUN_ID=str(run_id), PNEUMO_TRACE_ID=str(run_id))


    # Copy key configs for reproducibility
    cfg_dir = run_dir / "config"
    for fn in [
        "default_base.json",
        "default_suite.json",
        "default_ranges.json",
        "component_passport.json",
        "WISHLIST.md",
        "WISHLIST.json",
        "WISHLIST_v2.md",
        "PROJECT_CONTEXT_ANALYSIS_v2.md",
        "TODO.md",
        "TODO.json",
    ]:
        src = repo_root / fn
        if not src.exists():
            src = pneumo_dir / fn
        if src.exists():
            (cfg_dir / fn).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, cfg_dir / fn)

    rc = 0
    steps: list[dict[str, Any]] = []

    def step_record(name: str, result: CmdResult | None = None, **extra: Any) -> None:
        rec: dict[str, Any] = {"name": name, **extra}
        if result is not None:
            rec.update(
                {
                    "returncode": result.returncode,
                    "duration_s": result.duration_s,
                    "cmd": result.cmd,
                    "sys_before": result.sys_before,
                    "sys_after": result.sys_after,
                }
            )
        steps.append(rec)
        _safe_write_json(run_dir / "summary" / "steps.json", {"steps": steps})
        ev("step", step=name, returncode=rec.get("returncode"), duration_s=rec.get("duration_s"))

    # timeouts (seconds)
    T_PIP = 180.0
    T_COMPILE = 180.0
    T_SELF = 240.0
    T_PASS = 240.0
    T_PYTEST = 900.0 if args.level == "standard" else 1800.0
    T_RUFF = 240.0
    T_PYTEST_COV = 1800.0
    T_ROOTCAUSE = 600.0
    T_LOGLINT = 180.0
    T_SQLITE = 240.0
    T_FUZZ = 600.0
    T_OPT = 900.0

    try:
        # --- environment capture ---
        env_dir = run_dir / "env"
        rr = _run([python_exe, "-m", "pip", "freeze"], cwd=repo_root, timeout_s=T_PIP)
        _safe_write_text(env_dir / "pip_freeze.txt", rr.stdout + ("\n\nSTDERR:\n" + rr.stderr if rr.stderr else ""))
        step_record("pip_freeze", rr)

        rr2 = _run([python_exe, "-m", "pip", "check"], cwd=repo_root, timeout_s=T_PIP)
        _safe_write_text(env_dir / "pip_check.txt", rr2.stdout + ("\n\nSTDERR:\n" + rr2.stderr if rr2.stderr else ""))
        step_record("pip_check", rr2)

        # --- compileall (syntax check) ---
        c_dir = run_dir / "checks"
        rr_ca = _run([python_exe, "-m", "compileall", "-q", str(pneumo_dir)], cwd=repo_root, timeout_s=T_COMPILE)
        _safe_write_text(c_dir / "compileall.txt", rr_ca.stdout + ("\n\nSTDERR:\n" + rr_ca.stderr if rr_ca.stderr else ""))
        step_record("compileall", rr_ca)
        if rr_ca.returncode != 0:
            rc = max(rc, 2)

        # --- self_check ---
        rr_sc = _run([python_exe, str(pneumo_dir / "self_check.py")], cwd=pneumo_dir, timeout_s=T_SELF)
        _safe_write_text(c_dir / "self_check.txt", rr_sc.stdout + ("\n\nSTDERR:\n" + rr_sc.stderr if rr_sc.stderr else ""))
        step_record("self_check", rr_sc)
        if rr_sc.returncode != 0:
            rc = max(rc, 3)

        # --- passport_check ---
        rr_pc = _run([python_exe, str(pneumo_dir / "passport_check.py")], cwd=pneumo_dir, timeout_s=T_PASS)
        _safe_write_text(c_dir / "passport_check.txt", rr_pc.stdout + ("\n\nSTDERR:\n" + rr_pc.stderr if rr_pc.stderr else ""))
        step_record("passport_check", rr_pc)
        if rr_pc.returncode != 0:
            rc = max(rc, 4)

        # --- pytest suite ---
        if args.level in {"standard", "full"}:
            t_dir = run_dir / "tests"
            t_dir.mkdir(parents=True, exist_ok=True)

            rr_pytest_help = _run([python_exe, "-m", "pytest", "--version"], cwd=repo_root, timeout_s=60.0)
            _safe_write_text(t_dir / "pytest_version.txt", rr_pytest_help.stdout + ("\n" + rr_pytest_help.stderr if rr_pytest_help.stderr else ""))
            if rr_pytest_help.returncode != 0:
                step_record("pytest_missing", rr_pytest_help)
                rc = max(rc, 8)
            else:
                marker = "not slow" if args.level == "standard" else ""
                junit_xml = (t_dir / "pytest_junit.xml").resolve()
                cmd = [python_exe, "-m", "pytest", "-q", "--durations=10", f"--junitxml={junit_xml}"]
                if marker:
                    cmd += ["-m", marker]
                if args.pytest_args.strip():
                    cmd += args.pytest_args.strip().split()
                rr_pt = _run(cmd, cwd=repo_root, timeout_s=T_PYTEST)
                _safe_write_text(t_dir / "pytest_stdout.txt", rr_pt.stdout)
                _safe_write_text(t_dir / "pytest_stderr.txt", rr_pt.stderr)
                step_record("pytest", rr_pt, marker=marker)
                if rr_pt.returncode != 0:
                    rc = max(rc, 5)

                # --- optional: static checks (full only) ---
                if args.level == "full":
                    s_dir = run_dir / "static_checks"
                    s_dir.mkdir(parents=True, exist_ok=True)

                    # ruff (lint)
                    rr_rv = _run([python_exe, "-m", "ruff", "--version"], cwd=repo_root, timeout_s=30.0)
                    _safe_write_text(s_dir / "ruff_version.txt", rr_rv.stdout + ("\n" + rr_rv.stderr if rr_rv.stderr else ""))
                    if rr_rv.returncode != 0:
                        step_record("ruff_missing", rr_rv)
                    else:
                        rr_r = _run([python_exe, "-m", "ruff", "check", str(repo_root)], cwd=repo_root, timeout_s=T_RUFF)
                        _safe_write_text(s_dir / "ruff_stdout.txt", rr_r.stdout)
                        _safe_write_text(s_dir / "ruff_stderr.txt", rr_r.stderr)
                        step_record("ruff", rr_r)
                        if rr_r.returncode != 0:
                            rc = max(rc, 6)

                    # pytest-cov (coverage)
                    junit_cov = (s_dir / "pytest_cov_junit.xml").resolve()
                    cmd_cov = [python_exe, "-m", "pytest", "-q", "--durations=10", f"--junitxml={junit_cov}", "--cov=pneumo_solver_ui", "--cov-report=term-missing"]
                    rr_cov = _run(cmd_cov, cwd=repo_root, timeout_s=T_PYTEST_COV)
                    # если pytest-cov не установлен, pytest ругнётся на аргументы --cov
                    if rr_cov.returncode != 0 and ("unrecognized arguments: --cov" in (rr_cov.stderr or "")):
                        step_record("pytest_cov_missing", rr_cov)
                    else:
                        _safe_write_text(s_dir / "pytest_cov_stdout.txt", rr_cov.stdout)
                        _safe_write_text(s_dir / "pytest_cov_stderr.txt", rr_cov.stderr)
                        step_record("pytest_cov", rr_cov)
                        if rr_cov.returncode != 0:
                            rc = max(rc, 7)

        # --- root_cause_report ---
        if args.level in {"standard", "full"}:
            r_dir = run_dir / "reports"
            r_dir.mkdir(parents=True, exist_ok=True)
            out_prefix = (r_dir / "baseline_root_cause").resolve()
            cmd_rc = [str(python_exe_path), str(pneumo_dir / "root_cause_report.py"), "--out", str(out_prefix)]
            rr_rc = _run(cmd_rc, cwd=repo_root, timeout_s=T_ROOTCAUSE)
            _safe_write_text(r_dir / "root_cause_report_stdout.txt", rr_rc.stdout)
            _safe_write_text(r_dir / "root_cause_report_stderr.txt", rr_rc.stderr)
            step_record("root_cause_report", rr_rc)
            if rr_rc.returncode != 0:
                rc = max(rc, 6)

        # --- UI smoke ---
        if args.level in {"standard", "full"}:
            try:
                ui_meta = _ui_smoke_streamlit(
                    python_exe_path,
                    repo_root,
                    canonical_streamlit_entrypoint(here=__file__),
                    run_dir / "ui_smoke",
                    timeout_s=float(args.ui_smoke_timeout_s),
                )
                step_record("ui_smoke", None, **ui_meta)
                if not ui_meta.get("http_ok"):
                    rc = max(rc, 7)
            except Exception:
                _safe_write_text(run_dir / "ui_smoke_failed.txt", traceback.format_exc())
                step_record("ui_smoke", None, failed=True)
                rc = max(rc, 7)

        # --- fuzz smoke ---
        if args.level in {"standard", "full"}:
            try:
                f_dir = run_dir / "fuzz"
                f_dir.mkdir(parents=True, exist_ok=True)
                n = 5 if args.level == "standard" else 20
                cmd_fuzz = [
                    python_exe,
                    str(pneumo_dir / "tools" / "fuzz_smoke.py"),
                    "--n",
                    str(n),
                    "--seed",
                    "0",
                    "--allow_failures",
                    "0",
                    "--model",
                    str(pneumo_dir / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"),
                    "--worker",
                    str(pneumo_dir / "opt_worker_v3_margins_energy.py"),
                    "--suite_json",
                    str(pneumo_dir / "default_suite.json"),
                    "--base_json",
                    str(pneumo_dir / "default_base.json"),
                    "--ranges_json",
                    str(pneumo_dir / "default_ranges.json"),
                    "--out_dir",
                    str(f_dir),
                ]
                rr_f = _run(cmd_fuzz, cwd=repo_root, timeout_s=T_FUZZ)
                _safe_write_text(f_dir / "fuzz_stdout.txt", rr_f.stdout)
                _safe_write_text(f_dir / "fuzz_stderr.txt", rr_f.stderr)
                step_record("fuzz_smoke", rr_f, n=n)
                if rr_f.returncode != 0:
                    rc = max(rc, 10)
            except Exception:
                _safe_write_text(run_dir / "fuzz_failed.txt", traceback.format_exc())
                step_record("fuzz_smoke", None, failed=True)
                rc = max(rc, 10)

        # --- optimization smoke (full) ---
        if args.level == "full":
            try:
                o_dir = run_dir / "opt_smoke"
                o_dir.mkdir(parents=True, exist_ok=True)
                out_csv = (o_dir / "opt_smoke.csv").resolve()
                cmd_opt = [
                    python_exe,
                    str(pneumo_dir / "opt_worker_v3_margins_energy.py"),
                    "--minutes",
                    "0.5",
                    "--jobs",
                    "1",
                    "--model",
                    str(pneumo_dir / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"),
                    "--out",
                    str(out_csv),
                    "--suite_json",
                    str(pneumo_dir / "default_suite.json"),
                    "--base_json",
                    str(pneumo_dir / "default_base.json"),
                    "--ranges_json",
                    str(pneumo_dir / "default_ranges.json"),
                ]
                rr_opt = _run(cmd_opt, cwd=repo_root, timeout_s=T_OPT)
                _safe_write_text(o_dir / "opt_stdout.txt", rr_opt.stdout)
                _safe_write_text(o_dir / "opt_stderr.txt", rr_opt.stderr)
                step_record("opt_smoke", rr_opt)
                if rr_opt.returncode != 0:
                    rc = max(rc, 9)
            except Exception:
                _safe_write_text(run_dir / "opt_smoke_failed.txt", traceback.format_exc())
                step_record("opt_smoke", None, failed=True)
                rc = max(rc, 9)

        # --- collect latest app logs (after UI/opt/fuzz) ---
        try:
            src_logs = logs_live
            if src_logs.exists():
                shutil.copytree(src_logs, run_dir / "logs", dirs_exist_ok=True)
        except Exception:
            _safe_write_text(run_dir / "logs_copy_failed.txt", traceback.format_exc())

        # --- loglint ---
        if args.level in {"standard", "full", "quick"}:
            try:
                ll_root = run_dir / "loglint"
                ll_root.mkdir(parents=True, exist_ok=True)

                cmd_ll_h = [
                    python_exe,
                    str(pneumo_dir / "tools" / "loglint.py"),
                    "--strict",
                    "--path",
                    str(events_path),
                    "--schema",
                    "harness",
                    "--out_dir",
                    str(ll_root / "harness"),
                ]
                rr_ll_h = _run(cmd_ll_h, cwd=repo_root, timeout_s=T_LOGLINT)
                _safe_write_text(ll_root / "loglint_harness_stdout.txt", rr_ll_h.stdout)
                _safe_write_text(ll_root / "loglint_harness_stderr.txt", rr_ll_h.stderr)
                step_record("loglint_harness", rr_ll_h)
                if rr_ll_h.returncode != 0:
                    rc = max(rc, 11)

                cmd_ll_ui = [
                    python_exe,
                    str(pneumo_dir / "tools" / "loglint.py"),
                    "--strict",
                    "--path",
                    str(run_dir / "logs"),
                    "--recursive",
                    "--schema",
                    "ui",
                    "--out_dir",
                    str(ll_root / "ui"),
                ]
                rr_ll_ui = _run(cmd_ll_ui, cwd=repo_root, timeout_s=T_LOGLINT)
                _safe_write_text(ll_root / "loglint_ui_stdout.txt", rr_ll_ui.stdout)
                _safe_write_text(ll_root / "loglint_ui_stderr.txt", rr_ll_ui.stderr)
                step_record("loglint_ui", rr_ll_ui)
                if rr_ll_ui.returncode != 0:
                    rc = max(rc, 11)

                # --- logstats (агрегаты по событиям/спанам) ---
                try:
                    ls_root = run_dir / "logstats"
                    ls_root.mkdir(parents=True, exist_ok=True)

                    cmd_ls_h = [
                        python_exe,
                        str(pneumo_dir / "tools" / "logstats.py"),
                        "--path",
                        str(events_path),
                        "--out_dir",
                        str(ls_root / "harness"),
                    ]
                    rr_ls_h = _run(cmd_ls_h, cwd=repo_root, timeout_s=T_LOGLINT)
                    _safe_write_text(ls_root / "logstats_harness_stdout.txt", rr_ls_h.stdout)
                    _safe_write_text(ls_root / "logstats_harness_stderr.txt", rr_ls_h.stderr)
                    step_record("logstats_harness", rr_ls_h)

                    cmd_ls_ui = [
                        python_exe,
                        str(pneumo_dir / "tools" / "logstats.py"),
                        "--path",
                        str(run_dir / "logs"),
                        "--recursive",
                        "--out_dir",
                        str(ls_root / "ui"),
                    ]
                    rr_ls_ui = _run(cmd_ls_ui, cwd=repo_root, timeout_s=T_LOGLINT)
                    _safe_write_text(ls_root / "logstats_ui_stdout.txt", rr_ls_ui.stdout)
                    _safe_write_text(ls_root / "logstats_ui_stderr.txt", rr_ls_ui.stderr)
                    step_record("logstats_ui", rr_ls_ui)

                    # --- log2sqlite (метрики/события в SQLite для long-runs и быстрых агрегаций) ---
                    try:
                        sql_root = run_dir / "sqlite"
                        sql_root.mkdir(parents=True, exist_ok=True)
                        db_path = sql_root / "metrics.sqlite"

                        cmd_sql_h = [
                            python_exe,
                            str(pneumo_dir / "tools" / "log2sqlite.py"),
                            "--input",
                            str(events_path),
                            "--db",
                            str(db_path),
                            "--source",
                            "harness",
                        ]
                        rr_sql_h = _run(cmd_sql_h, cwd=repo_root, timeout_s=T_SQLITE)
                        _safe_write_text(sql_root / "log2sqlite_harness_stdout.txt", rr_sql_h.stdout)
                        _safe_write_text(sql_root / "log2sqlite_harness_stderr.txt", rr_sql_h.stderr)
                        step_record("log2sqlite_harness", rr_sql_h)
                        if rr_sql_h.returncode != 0:
                            rc = max(rc, 12)

                        cmd_sql_ui = [
                            python_exe,
                            str(pneumo_dir / "tools" / "log2sqlite.py"),
                            "--input",
                            str(run_dir / "logs"),
                            "--recursive",
                            "--db",
                            str(db_path),
                            "--source",
                            "ui",
                            "--append",
                        ]
                        rr_sql_ui = _run(cmd_sql_ui, cwd=repo_root, timeout_s=T_SQLITE)
                        _safe_write_text(sql_root / "log2sqlite_ui_stdout.txt", rr_sql_ui.stdout)
                        _safe_write_text(sql_root / "log2sqlite_ui_stderr.txt", rr_sql_ui.stderr)
                        step_record("log2sqlite_ui", rr_sql_ui)
                        if rr_sql_ui.returncode != 0:
                            rc = max(rc, 12)

                        # Короткий sanity-query отчёт
                        cmd_sql_report = [
                            python_exe,
                            str(pneumo_dir / "tools" / "log2sqlite.py"),
                            "--db",
                            str(db_path),
                            "--report_only",
                        ]
                        rr_sql_rep = _run(cmd_sql_report, cwd=repo_root, timeout_s=T_SQLITE)
                        _safe_write_text(sql_root / "sqlite_report_stdout.txt", rr_sql_rep.stdout)
                        _safe_write_text(sql_root / "sqlite_report_stderr.txt", rr_sql_rep.stderr)
                        step_record("sqlite_report", rr_sql_rep)

                    except Exception:
                        _safe_write_text(run_dir / "log2sqlite_failed.txt", traceback.format_exc())
                        step_record("log2sqlite", None, failed=True)

                except Exception:
                    _safe_write_text(run_dir / "logstats_failed.txt", traceback.format_exc())
                    step_record("logstats", None, failed=True)

            except Exception:
                _safe_write_text(run_dir / "loglint_failed.txt", traceback.format_exc())
                step_record("loglint", None, failed=True)
                rc = max(rc, 11)

        # --- summary ---
        summary = {
            "finished_at": _now_iso(),
            "release": HARNESS_RELEASE,
            "level": args.level,
            "rc": int(rc),
            "ok": (rc == 0),
            "run_dir": str(run_dir),
        }
        _safe_write_json(run_dir / "summary" / "summary.json", summary)
        _safe_write_text(
            run_dir / "summary" / "summary.md",
            "\n".join(
                [
                    f"# Autotest summary ({args.level})",
                    "",
                    f"OK: **{summary['ok']}**",
                    f"RC: **{summary['rc']}**",
                    "",
                    "## Steps",
                ]
                + [f"- {s.get('name')}: rc={s.get('returncode', 'n/a')}" for s in steps]
            )
            + "\n",
        )
        ev("finish", rc=int(rc), ok=bool(summary["ok"]))

    except Exception:
        rc = max(rc, 2)
        _safe_write_text(run_dir / "FATAL.txt", traceback.format_exc())
        ev("fatal", error="unhandled_exception")
    finally:
        # reproduce scripts
        try:
            _write_reproduce_scripts(run_dir, args.level)
        except Exception:
            _safe_write_text(run_dir / "reproduce_failed.txt", traceback.format_exc())

        # Manifest + ZIP even on failure
        try:
            _collect_manifest(run_dir, run_dir / "manifest.json")
        except Exception:
            _safe_write_text(run_dir / "manifest_failed.txt", traceback.format_exc())

        zip_path = run_dir.with_suffix(".zip")
        if not args.no_zip:
            try:
                _zip_dir(run_dir, zip_path)
            except Exception:
                _safe_write_text(run_dir / "zip_failed.txt", traceback.format_exc())

        print("\n=== AUTOTEST FINISHED ===")
        print(f"Release: {HARNESS_RELEASE}")
        print(f"Run dir: {run_dir}")
        if not args.no_zip:
            print(f"Zip: {zip_path}")


    # R49: Run Registry end (best-effort)
    try:
        from pneumo_solver_ui.run_registry import end_run, env_context

        if rr_token is not None:
            zp = None
            try:
                if "zip_path" in locals() and isinstance(zip_path, Path) and zip_path.exists():
                    zp = str(zip_path)
            except Exception:
                zp = None

            end_run(
                rr_token,
                status=("ok" if int(rc) == 0 else "fail"),
                rc=int(rc),
                run_dir=str(run_dir),
                zip_path=zp,
                env=env_context(),
                release=HARNESS_RELEASE,
            )
    except Exception:
        pass

    return int(rc)



if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("FATAL: run_autotest crashed")
        traceback.print_exc()
        raise SystemExit(2)
