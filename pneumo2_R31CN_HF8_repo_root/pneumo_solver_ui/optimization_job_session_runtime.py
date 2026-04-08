from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

from pneumo_solver_ui.process_tree import terminate_process_tree


@dataclass
class DistOptJob:
    proc: subprocess.Popen
    run_dir: Path
    log_path: Path
    started_ts: float
    budget: int
    backend: str
    pipeline_mode: str
    progress_path: Optional[Path] = None
    stop_file: Optional[Path] = None


_PROGRESS_RE = re.compile(r"\bdone=(\d+)(?:/(\d+))?")


def tail_file_text(path: Path, max_bytes: int = 24_000) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except Exception as exc:
        return f"[не удалось прочитать лог: {exc}]"


def parse_done_from_log(text: str) -> Optional[int]:
    matches = list(_PROGRESS_RE.finditer(text))
    if not matches:
        return None
    try:
        return int(matches[-1].group(1))
    except Exception:
        return None


def load_job_from_session(session_state: Mapping[str, Any]) -> Optional[DistOptJob]:
    raw = session_state.get("__dist_opt_job")
    if not raw:
        return None
    try:
        return DistOptJob(**raw)
    except Exception:
        return None


def save_job_to_session(session_state: MutableMapping[str, Any], job: DistOptJob) -> None:
    session_state["__dist_opt_job"] = {
        "proc": job.proc,
        "run_dir": job.run_dir,
        "log_path": job.log_path,
        "started_ts": job.started_ts,
        "budget": int(job.budget),
        "backend": str(job.backend),
        "pipeline_mode": str(job.pipeline_mode),
        "progress_path": job.progress_path,
        "stop_file": job.stop_file,
    }


def clear_job_from_session(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop("__dist_opt_job", None)


def write_soft_stop_file(stop_file: Optional[Path]) -> bool:
    if stop_file is None:
        return False
    try:
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("stop", encoding="utf-8")
        return True
    except Exception:
        return False


def soft_stop_requested(job: DistOptJob) -> bool:
    try:
        return bool(job.stop_file and Path(job.stop_file).exists())
    except Exception:
        return False


def terminate_optimization_process(proc: subprocess.Popen) -> None:
    try:
        terminate_process_tree(proc, grace_sec=0.8, reason="optimization_hard_stop")
        return
    except Exception:
        pass
    try:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass


__all__ = [
    "DistOptJob",
    "clear_job_from_session",
    "load_job_from_session",
    "parse_done_from_log",
    "save_job_to_session",
    "soft_stop_requested",
    "tail_file_text",
    "terminate_optimization_process",
    "write_soft_stop_file",
]
