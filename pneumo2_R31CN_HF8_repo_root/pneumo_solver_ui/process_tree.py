from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

LogFn = Callable[[str], None] | None


def _log(log: LogFn, msg: str) -> None:
    try:
        if log is not None:
            log(str(msg))
    except Exception:
        pass


def _coerce_pid(proc_or_pid: Any) -> int | None:
    try:
        if proc_or_pid is None:
            return None
        if isinstance(proc_or_pid, int):
            return int(proc_or_pid) if int(proc_or_pid) > 0 else None
        pid = getattr(proc_or_pid, "pid", None)
        if pid is None:
            return None
        pid_i = int(pid)
        return pid_i if pid_i > 0 else None
    except Exception:
        return None


def _close_proc_handle(proc_or_pid: Any) -> None:
    try:
        proc_or_pid.stdout and proc_or_pid.stdout.close()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        proc_or_pid.stderr and proc_or_pid.stderr.close()  # type: ignore[attr-defined]
    except Exception:
        pass


def _taskkill_tree(pid: int, *, force: bool, log: LogFn = None) -> None:
    if os.name != "nt" or pid <= 0:
        return
    cmd = ["taskkill", "/PID", str(int(pid)), "/T"]
    if force:
        cmd.append("/F")
    try:
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (cp.stdout or "").strip()
        if out:
            _log(log, f"[taskkill] {' '.join(cmd)} -> {out}")
    except Exception as exc:
        _log(log, f"[taskkill] failed for pid={pid}: {exc!r}")


def _snapshot_procs(pid: int) -> tuple[Any | None, list[Any]]:
    if psutil is None or pid <= 0:
        return None, []
    try:
        parent = psutil.Process(int(pid))
    except Exception:
        return None, []
    try:
        children = list(parent.children(recursive=True))
    except Exception:
        children = []
    return parent, children


def _safe_terminate(proc: Any, *, log: LogFn = None) -> None:
    try:
        proc.terminate()
    except Exception as exc:
        _log(log, f"[proc terminate] pid={getattr(proc, 'pid', '?')} err={exc!r}")


def _safe_kill(proc: Any, *, log: LogFn = None) -> None:
    try:
        proc.kill()
    except Exception as exc:
        _log(log, f"[proc kill] pid={getattr(proc, 'pid', '?')} err={exc!r}")


def terminate_process_tree(proc_or_pid: Any, *, grace_sec: float = 0.8, reason: str = "", log: LogFn = None) -> dict[str, Any]:
    """Best-effort recursive process-tree shutdown.

    Why this helper exists:
    - On Windows, killing only the top-level python/streamlit pid can leave child
      python.exe workers and their console host windows (conhost.exe) alive.
    - We need one explicit path that first tries graceful termination and then
      performs a Windows tree sweep (taskkill /T /F) if something still survives.

    Returns a small diagnostic dict suitable for logs/tests.
    """

    pid = _coerce_pid(proc_or_pid)
    result: dict[str, Any] = {
        "pid": pid,
        "reason": str(reason or ""),
        "children_before": [],
        "alive_after_soft": [],
        "alive_after_hard": [],
        "taskkill_used": False,
    }
    if pid is None:
        return result

    parent, children = _snapshot_procs(pid)
    result["children_before"] = [int(getattr(p, "pid", -1)) for p in children]
    if parent is None and hasattr(proc_or_pid, "poll"):
        # Fallback for environments where psutil snapshot failed but Popen handle exists.
        try:
            if proc_or_pid.poll() is None:
                try:
                    proc_or_pid.terminate()
                    proc_or_pid.wait(timeout=max(0.1, float(grace_sec)))
                except Exception:
                    try:
                        proc_or_pid.kill()
                    except Exception:
                        pass
            _close_proc_handle(proc_or_pid)
        except Exception:
            pass
        return result

    procs: list[Any] = []
    if parent is not None:
        procs.append(parent)
    procs.extend(children)
    seen: set[int] = set()
    ordered: list[Any] = []
    # Kill children first, then parent.
    for proc in list(reversed(children)) + ([parent] if parent is not None else []):
        try:
            pid_i = int(proc.pid)
        except Exception:
            continue
        if pid_i in seen:
            continue
        seen.add(pid_i)
        ordered.append(proc)

    for proc in ordered:
        _safe_terminate(proc, log=log)

    try:
        if psutil is not None and ordered:
            _, alive = psutil.wait_procs(ordered, timeout=max(0.1, float(grace_sec)))
        else:
            alive = []
    except Exception:
        alive = []

    alive_pids = []
    for proc in alive:
        try:
            if proc.is_running():
                alive_pids.append(int(proc.pid))
        except Exception:
            pass
    result["alive_after_soft"] = alive_pids

    if alive_pids and os.name == "nt":
        result["taskkill_used"] = True
        _taskkill_tree(int(pid), force=True, log=log)

    if alive_pids:
        for proc in alive:
            _safe_kill(proc, log=log)
        try:
            if psutil is not None and alive:
                _, alive2 = psutil.wait_procs(alive, timeout=max(0.2, float(grace_sec)))
            else:
                alive2 = []
        except Exception:
            alive2 = []
    else:
        alive2 = []

    alive_after_hard = []
    for proc in alive2:
        try:
            if proc.is_running():
                alive_after_hard.append(int(proc.pid))
        except Exception:
            pass
    result["alive_after_hard"] = alive_after_hard

    # Windows final sweep: even if psutil reports parent gone, taskkill is the most
    # reliable way to take down stray console host windows bound to the tree.
    if os.name == "nt" and (alive_after_hard or result["taskkill_used"]):
        try:
            _taskkill_tree(int(pid), force=True, log=log)
        except Exception:
            pass

    if hasattr(proc_or_pid, "wait"):
        try:
            proc_or_pid.wait(timeout=0.2)
        except Exception:
            pass
    _close_proc_handle(proc_or_pid)
    return result


__all__ = ["terminate_process_tree"]
