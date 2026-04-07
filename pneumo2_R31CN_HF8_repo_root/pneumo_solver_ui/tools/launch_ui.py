#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""launch_ui.py

Единый кроссплатформенный launcher для Streamlit UI.

Зачем
-----
Исторически RUN_WINDOWS.bat и RUN_LINUX.sh дублировали логику:

- генерация run_id / session_dir
- прокладка PNEUMO_* переменных окружения
- запись run_registry (run_start/run_end)
- запуск Streamlit
- пост-обработка: send bundle + окно "Copy ZIP"

В R54 мы выносим всё это в один python-модуль, чтобы:

1) убрать расхождения между Windows/Linux путями,
2) упростить дальнейшее развитие (watchdog/quality gates),
3) повысить надёжность и воспроизводимость.

Запуск
------
  python -m pneumo_solver_ui.tools.launch_ui

Параметры
---------
  --port 8505
  --no_open_browser
  --headless

"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from pneumo_solver_ui.entrypoints import canonical_streamlit_entrypoint, repo_root
from pneumo_solver_ui.workspace_contract import ensure_workspace_contract_dirs


try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _pyw_for_windows(py_exe: str) -> str:
    """Best effort: use pythonw.exe for GUI subprocesses on Windows."""
    try:
        p = Path(py_exe)
        if p.name.lower() == "python.exe":
            cand = p.with_name("pythonw.exe")
            if cand.exists():
                return str(cand)
    except Exception:
        pass
    return str(py_exe)


def _creationflags_no_window() -> int:
    if os.name != "nt":
        return 0
    try:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    except Exception:
        return 0x08000000


def main() -> int:
    ap = argparse.ArgumentParser(description="Launch Streamlit UI with isolated session dirs + postmortem send bundle")
    ap.add_argument("--port", type=int, default=None, help="Streamlit port (default: PNEUMO_UI_PORT or 8505)")
    ap.add_argument("--no_open_browser", action="store_true", help="Do not open browser automatically")
    ap.add_argument("--headless", action="store_true", help="Run Streamlit headless=true")
    args = ap.parse_args()

    repo = repo_root(here=__file__)
    pneumo_dir = repo / "pneumo_solver_ui"
    app = canonical_streamlit_entrypoint(here=__file__)
    if not app.exists():
        print(f"ERROR: app not found: {app}")
        return 2

    port = int(args.port or os.environ.get("PNEUMO_UI_PORT", "8505"))

    run_id = f"UI_{_ts()}"
    session_dir = (repo / "runs" / "ui_sessions" / run_id).resolve()
    log_dir = session_dir / "logs"
    ws_dir = session_dir / "workspace"
    (log_dir).mkdir(parents=True, exist_ok=True)
    ensure_workspace_contract_dirs(ws_dir, include_optional=True)

    env = os.environ.copy()
    env["PNEUMO_SESSION_DIR"] = str(session_dir)
    env["PNEUMO_RUN_ID"] = run_id
    env["PNEUMO_TRACE_ID"] = run_id
    env["PNEUMO_LOG_DIR"] = str(log_dir)
    env["PNEUMO_WORKSPACE_DIR"] = str(ws_dir)
    env["PNEUMO_RELEASE"] = RELEASE

    print("")
    print(f"[Obobshchenie {RELEASE}] Session: {run_id}")
    print(f"  PNEUMO_LOG_DIR      = {log_dir}")
    print(f"  PNEUMO_WORKSPACE_DIR= {ws_dir}")
    print("")

    # Run Registry start (best-effort)
    token = None
    try:
        from pneumo_solver_ui.run_registry import env_context, start_run

        extra = {}
        try:
            extra["env"] = env_context()
        except Exception:
            pass
        token = start_run(
            "ui_session",
            run_id,
            session_dir=str(session_dir),
            launcher="launch_ui.py",
            app=str(app),
            release=RELEASE,
            **extra,
        )
    except Exception:
        token = None

    # Streamlit command
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
    ]
    if args.headless:
        cmd += ["--server.headless", "true"]

    # Redirect streamlit stdout/stderr to session log for postmortem
    launcher_log = session_dir / "launcher_streamlit.log"
    lf = None
    try:
        lf = open(launcher_log, "a", encoding="utf-8", errors="replace")
    except Exception:
        lf = None

    print("Starting Streamlit...")
    proc = None
    try:
        proc = subprocess.Popen(cmd, cwd=str(repo), env=env, stdout=lf, stderr=lf, creationflags=_creationflags_no_window())
    except Exception as e:
        if lf:
            try:
                lf.close()
            except Exception:
                pass
        print(f"ERROR: failed to start streamlit: {e}")
        return 2

    # Postmortem watchdog (best-effort)
    try:
        wd = pneumo_dir / "tools" / "postmortem_watchdog.py"
        if wd.exists() and proc is not None:
            py_for_gui = sys.executable
            if os.name == "nt":
                py_for_gui = _pyw_for_windows(sys.executable)
            subprocess.Popen(
                [
                    str(py_for_gui),
                    str(wd),
                    "--target_pid",
                    str(proc.pid),
                    "--launcher_pid",
                    str(os.getpid()),
                    "--session_dir",
                    str(session_dir),
                    "--open_send_gui",
                ],
                cwd=str(repo),
                env=env,
                creationflags=_creationflags_no_window(),
            )
    except Exception:
        pass

    # Open browser
    if not args.no_open_browser:
        time.sleep(1.0)
        try:
            webbrowser.open(f"http://127.0.0.1:{port}", new=2)
        except Exception:
            pass

    # Wait for streamlit
    rc = 0
    try:
        rc = int(proc.wait() if proc is not None else 999)
    except Exception:
        rc = 999

    try:
        if lf:
            lf.write(f"\n[launcher] streamlit exited with code {rc}\n")
            lf.flush()
            lf.close()
    except Exception:
        pass

    # Run Registry end (best-effort)
    try:
        from pneumo_solver_ui.run_registry import end_run

        if token is not None:
            end_run(
                token,
                status=("ok" if rc == 0 else "fail"),
                rc=int(rc),
                session_dir=str(session_dir),
                launcher="launch_ui.py",
                release=RELEASE,
            )
    except Exception:
        pass

    # Post-exit: open the 1-button send GUI (it builds the bundle automatically)
    try:
        send_gui = pneumo_dir / "tools" / "send_results_gui.py"
        py_for_gui = sys.executable
        if os.name == "nt":
            py_for_gui = _pyw_for_windows(sys.executable)
        subprocess.Popen([str(py_for_gui), str(send_gui)], cwd=str(repo), env=env, creationflags=_creationflags_no_window())
    except Exception as e:
        print(f"WARN: failed to open send_results_gui: {e}")

    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
