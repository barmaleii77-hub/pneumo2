from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping

from pneumo_solver_ui.optimization_job_launch_runtime import (
    launch_optimization_job_payload,
)
from pneumo_solver_ui.optimization_coordinator_handoff_runtime import (
    build_coordinator_handoff_launch_plan,
)
from pneumo_solver_ui.optimization_job_session_runtime import (
    DistOptJob,
    save_job_to_session,
)
from pneumo_solver_ui.optimization_launch_plan_runtime import (
    app_root_from_ui_root,
    build_optimization_launch_plan,
    coordinator_resume_run_dir,
    new_optimization_run_dir,
    staged_resume_run_dir,
    workspace_dir_for_ui_root,
)


def start_optimization_job(
    session_state: MutableMapping[str, Any],
    *,
    ui_root: Path,
    ui_jobs_default: int,
    problem_hash_mode: str,
    python_executable: str | None = None,
    workspace_dir_fn: Callable[[Path], Path] = workspace_dir_for_ui_root,
    app_root_fn: Callable[[Path], Path] = app_root_from_ui_root,
    new_run_dir_fn: Callable[[Path, str], Path] = new_optimization_run_dir,
    resume_run_dir_fn: Callable[..., Path] = coordinator_resume_run_dir,
    staged_resume_run_dir_fn: Callable[..., Path] = staged_resume_run_dir,
    build_plan_fn: Callable[..., Any] = build_optimization_launch_plan,
    launch_payload_fn: Callable[..., Mapping[str, Any]] = launch_optimization_job_payload,
    save_job_fn: Callable[[MutableMapping[str, Any], DistOptJob], None] = save_job_to_session,
) -> DistOptJob:
    ui_root = Path(ui_root)
    is_staged = bool(session_state.get("opt_use_staged", False))
    workspace_dir = workspace_dir_fn(ui_root)
    if is_staged and bool(session_state.get("opt_stage_resume", False)):
        run_dir = Path(
            staged_resume_run_dir_fn(
                session_state,
                workspace_dir=workspace_dir,
                ui_root=ui_root,
                problem_hash_mode=str(problem_hash_mode or "stable"),
            )
        )
    elif not is_staged and bool(session_state.get("opt_resume", False)):
        run_dir = Path(
            resume_run_dir_fn(
                session_state,
                workspace_dir=workspace_dir,
                ui_root=ui_root,
                problem_hash_mode=str(problem_hash_mode or "stable"),
            )
        )
    else:
        run_dir = new_run_dir_fn(workspace_dir, "staged" if is_staged else "coordinator")
    plan = build_plan_fn(
        session_state,
        run_dir=run_dir,
        ui_root=ui_root,
        python_executable=str(python_executable or sys.executable),
        ui_jobs_default=int(ui_jobs_default),
    )
    job = DistOptJob(
        **launch_payload_fn(
            app_root_fn(ui_root),
            run_dir,
            plan,
            problem_hash_mode=str(problem_hash_mode or "stable"),
        )
    )
    save_job_fn(session_state, job)
    return job


def start_coordinator_handoff_job(
    session_state: MutableMapping[str, Any],
    *,
    source_run_dir: Path,
    ui_root: Path,
    problem_hash_mode: str,
    python_executable: str | None = None,
    app_root_fn: Callable[[Path], Path] = app_root_from_ui_root,
    build_handoff_plan_fn: Callable[..., Any] = build_coordinator_handoff_launch_plan,
    launch_payload_fn: Callable[..., Mapping[str, Any]] = launch_optimization_job_payload,
    save_job_fn: Callable[[MutableMapping[str, Any], DistOptJob], None] = save_job_to_session,
) -> DistOptJob:
    ui_root = Path(ui_root)
    plan = build_handoff_plan_fn(
        source_run_dir=Path(source_run_dir),
        ui_root=ui_root,
        python_executable=str(python_executable or sys.executable),
    )
    raw_run_dir = getattr(plan, "launch_run_dir", None)
    if raw_run_dir is None or not str(raw_run_dir):
        raise RuntimeError("Coordinator handoff plan does not define launch_run_dir")
    run_dir = Path(raw_run_dir)
    job = DistOptJob(
        **launch_payload_fn(
            app_root_fn(ui_root),
            run_dir,
            plan,
            problem_hash_mode=str(problem_hash_mode or "stable"),
        )
    )
    save_job_fn(session_state, job)
    return job


__all__ = [
    "start_coordinator_handoff_job",
    "start_optimization_job",
]
