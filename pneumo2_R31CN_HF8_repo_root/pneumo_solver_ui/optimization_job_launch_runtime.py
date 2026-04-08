from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping


def optimization_job_log_path(run_dir: Path, pipeline_mode: str) -> Path:
    mode = str(pipeline_mode or "").strip().lower()
    return run_dir / ("stage_runner.log" if mode == "staged" else "coordinator.log")


def launch_optimization_job_payload(
    app_root: Path,
    run_dir: Path,
    plan: Any,
    *,
    problem_hash_mode: str,
    base_env: Mapping[str, str] | None = None,
    popen_factory: Callable[..., Any] | None = None,
    now_fn: Callable[[], float] | None = None,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    env = dict(base_env or os.environ.copy())
    env["PNEUMO_OPT_PROBLEM_HASH_MODE"] = str(problem_hash_mode or "stable")
    log_path = optimization_job_log_path(run_dir, getattr(plan, "pipeline_mode", ""))
    popen = popen_factory or subprocess.Popen
    clock = now_fn or time.time

    with log_path.open("wb") as log_file:
        proc = popen(
            getattr(plan, "cmd"),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(app_root),
            env=env,
        )

    return {
        "proc": proc,
        "run_dir": run_dir,
        "log_path": log_path,
        "started_ts": float(clock()),
        "budget": int(getattr(plan, "budget", 0) or 0),
        "backend": str(getattr(plan, "label", "")),
        "pipeline_mode": str(getattr(plan, "pipeline_mode", "")),
        "progress_path": getattr(plan, "progress_path", None),
        "stop_file": getattr(plan, "stop_file", None),
    }


__all__ = [
    "launch_optimization_job_payload",
    "optimization_job_log_path",
]
