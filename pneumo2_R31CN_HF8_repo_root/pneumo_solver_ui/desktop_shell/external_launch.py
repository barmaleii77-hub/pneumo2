from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Mapping, Sequence


_LIVE_PROCESSES: set[subprocess.Popen] = set()
_LIVE_PROCESSES_LOCK = threading.Lock()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def python_gui_exe() -> str:
    if os.name != "nt":
        return sys.executable

    try:
        exe = Path(sys.executable)
        if exe.name.lower() == "python.exe":
            pyw = exe.with_name("pythonw.exe")
            if pyw.exists():
                return str(pyw)
    except Exception:
        pass
    return sys.executable


def track_spawned_process(proc: subprocess.Popen) -> subprocess.Popen:
    """Keep spawned child alive until it exits to avoid Popen GC warnings."""

    with _LIVE_PROCESSES_LOCK:
        _LIVE_PROCESSES.add(proc)

    def _waiter() -> None:
        try:
            proc.wait()
        except Exception:
            pass
        finally:
            with _LIVE_PROCESSES_LOCK:
                _LIVE_PROCESSES.discard(proc)

    threading.Thread(target=_waiter, name=f"spawn-track-{getattr(proc, 'pid', 'na')}", daemon=True).start()
    return proc


def spawn_module(
    module: str,
    args: Sequence[str] | None = None,
    *,
    env_updates: Mapping[str, str] | None = None,
) -> subprocess.Popen:
    cmd = [python_gui_exe(), "-m", module]
    if args:
        cmd.extend(str(item) for item in args)
    kwargs: dict[str, object] = {
        "cwd": str(repo_root()),
    }
    if env_updates:
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in env_updates.items()})
        kwargs["env"] = env
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(cmd, **kwargs)
    return track_spawned_process(proc)


def build_shell_context_env(payload: Mapping[str, object] | None) -> dict[str, str]:
    if not payload:
        return {}
    return {
        "PNEUMO_GUI_SHELL_CONTEXT_JSON": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }
