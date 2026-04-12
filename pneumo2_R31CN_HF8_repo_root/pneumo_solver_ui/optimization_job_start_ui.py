from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, MutableMapping

from pneumo_solver_ui.optimization_job_start_runtime import (
    start_coordinator_handoff_job,
    start_optimization_job,
)

_ACTIVE_LAUNCH_CONTEXT_KEY = "__opt_active_launch_context"
_HISTORY_SELECTED_RUN_DIR_KEY = "__opt_history_selected_run_dir"


def _resolved_path_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve())
    except Exception:
        return text


def _remember_started_job(
    session_state: MutableMapping[str, Any],
    job: Any,
    *,
    launch_kind: str,
    source_run_dir: Path | None = None,
) -> None:
    run_dir_text = _resolved_path_text(getattr(job, "run_dir", None))
    if not run_dir_text:
        return
    pipeline_mode = str(getattr(job, "pipeline_mode", "") or "").strip()
    backend = str(getattr(job, "backend", "") or "").strip()
    is_staged = pipeline_mode == "staged"
    session_state[_HISTORY_SELECTED_RUN_DIR_KEY] = run_dir_text
    session_state[_ACTIVE_LAUNCH_CONTEXT_KEY] = {
        "kind": str(launch_kind or "manual"),
        "run_dir": run_dir_text,
        "pipeline_mode": pipeline_mode,
        "backend": backend,
        "source_run_dir": _resolved_path_text(source_run_dir),
    }
    session_state["opt_use_staged"] = bool(is_staged)
    session_state["use_staged_opt"] = bool(is_staged)


def start_optimization_job_with_feedback(
    st: Any,
    *,
    session_state: MutableMapping[str, Any],
    ui_root: Path,
    ui_jobs_default: int,
    problem_hash_mode: str,
    rerun_fn: Callable[[Any], None],
    python_executable: str | None = None,
    start_job_fn: Callable[..., Any] = start_optimization_job,
) -> bool:
    try:
        job = start_job_fn(
            session_state,
            ui_root=ui_root,
            ui_jobs_default=ui_jobs_default,
            python_executable=str(python_executable or sys.executable),
            problem_hash_mode=str(problem_hash_mode or "stable"),
        )
        if job is not None:
            _remember_started_job(session_state, job, launch_kind="manual")
        st.success("Запуск создан. Лог и прогресс появятся через пару секунд.")
        rerun_fn(st)
        return True
    except Exception as exc:
        st.error(f"Не удалось запустить оптимизацию: {exc}")
        return False


def start_coordinator_handoff_job_with_feedback(
    st: Any,
    *,
    session_state: MutableMapping[str, Any],
    source_run_dir: Path,
    ui_root: Path,
    problem_hash_mode: str,
    rerun_fn: Callable[[Any], None],
    python_executable: str | None = None,
    start_job_fn: Callable[..., Any] = start_coordinator_handoff_job,
) -> bool:
    try:
        job = start_job_fn(
            session_state,
            source_run_dir=Path(source_run_dir),
            ui_root=ui_root,
            python_executable=str(python_executable or sys.executable),
            problem_hash_mode=str(problem_hash_mode or "stable"),
        )
        if job is not None:
            _remember_started_job(
                session_state,
                job,
                launch_kind="handoff",
                source_run_dir=Path(source_run_dir),
            )
        st.success("Coordinator handoff запущен. Full-ring лог появится через пару секунд.")
        rerun_fn(st)
        return True
    except Exception as exc:
        st.error(f"Не удалось запустить coordinator handoff: {exc}")
        return False


__all__ = [
    "start_coordinator_handoff_job_with_feedback",
    "start_optimization_job_with_feedback",
]
