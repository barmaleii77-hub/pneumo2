from __future__ import annotations

import os
import pickle
import subprocess
from pathlib import Path
from typing import Any, Callable


def dump_pickle_payload(handle: Any, payload: dict[str, Any]) -> None:
    pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle_payload(handle: Any) -> dict[str, Any]:
    return pickle.load(handle)


def dump_cloudpickle_payload(handle: Any, payload: dict[str, Any]) -> None:
    try:
        import cloudpickle as _cp  # type: ignore

        _cp.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_cloudpickle_payload(handle: Any) -> dict[str, Any]:
    try:
        import cloudpickle as _cp  # type: ignore

        return _cp.load(handle)
    except Exception:
        return pickle.load(handle)


def start_background_worker(
    cmd: list,
    cwd: Path,
    *,
    console_python_executable_fn: Callable[[str | Path | None], str] | None = None,
):
    """Start a non-GUI worker process with detached console and log files."""
    creationflags = 0
    startupinfo = None
    run_cmd = list(cmd)
    stdout_f = None
    stderr_f = None
    try:
        if run_cmd and console_python_executable_fn is not None:
            run_cmd[0] = console_python_executable_fn(run_cmd[0]) or str(run_cmd[0])
    except Exception:
        pass
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        try:
            script_stem = Path(str(run_cmd[1] if len(run_cmd) > 1 else "worker")).stem
        except Exception:
            script_stem = "worker"
        try:
            cwd = Path(cwd)
            cwd.mkdir(parents=True, exist_ok=True)
            stdout_f = (cwd / "_proc.out.log").open("ab")
            stderr_f = (cwd / "_proc.err.log").open("ab")
        except Exception:
            stdout_f = None
            stderr_f = None
    try:
        proc = subprocess.Popen(
            run_cmd,
            cwd=str(cwd),
            creationflags=creationflags,
            startupinfo=startupinfo,
            stdout=stdout_f,
            stderr=stderr_f,
        )
    finally:
        # Child already inherited descriptors; parent must close them to avoid
        # Windows ResourceWarning noise on _proc.*.log files.
        for _fh in (stdout_f, stderr_f):
            try:
                if _fh is not None:
                    _fh.close()
            except Exception:
                pass
    return proc


__all__ = [
    "dump_cloudpickle_payload",
    "dump_pickle_payload",
    "load_cloudpickle_payload",
    "load_pickle_payload",
    "start_background_worker",
]
