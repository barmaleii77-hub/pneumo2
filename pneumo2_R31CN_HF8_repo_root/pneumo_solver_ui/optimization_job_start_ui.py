from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, MutableMapping

from pneumo_solver_ui.optimization_job_start_runtime import (
    start_optimization_job,
)


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
        start_job_fn(
            session_state,
            ui_root=ui_root,
            ui_jobs_default=ui_jobs_default,
            python_executable=str(python_executable or sys.executable),
            problem_hash_mode=str(problem_hash_mode or "stable"),
        )
        st.success("Запуск создан. Лог и прогресс появятся через пару секунд.")
        rerun_fn(st)
        return True
    except Exception as exc:
        st.error(f"Не удалось запустить оптимизацию: {exc}")
        return False


__all__ = [
    "start_optimization_job_with_feedback",
]
