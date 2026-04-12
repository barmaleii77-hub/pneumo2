from __future__ import annotations

import time
from typing import Any, Callable

from pneumo_solver_ui import run_artifacts
from pneumo_solver_ui.optimization_coordinator_handoff_ui import (
    render_coordinator_handoff_action,
)
from pneumo_solver_ui.optimization_run_history import summarize_optimization_run
from pneumo_solver_ui.optimization_run_pointer_actions_ui import (
    build_run_pointer_meta_from_summary,
)


def _render_finished_job_status(st: Any, *, rc: int, soft_stop_requested: bool) -> None:
    if rc == 0 and soft_stop_requested:
        st.warning(f"Оптимизация остановлена по STOP-файлу (код={rc}).")
    elif rc == 0:
        st.success(f"Оптимизация завершена успешно (код={rc}).")
    else:
        st.error(f"Оптимизация завершилась с ошибкой (код={rc}).")


def _save_finished_job_pointer(
    st: Any,
    job: Any,
    summary: Any,
    *,
    save_ptr_fn: Callable[[Any, dict[str, Any]], None],
    autoload_session_fn: Callable[[Any], None],
) -> None:
    if summary is None:
        return
    meta = build_run_pointer_meta_from_summary(
        summary,
        selected_from="finished_job",
        now_text=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    meta["backend"] = getattr(job, "backend", meta.get("backend", ""))
    meta["run_dir"] = str(getattr(job, "run_dir"))
    if summary.status in {"done", "partial"}:
        save_ptr_fn(getattr(job, "run_dir"), meta)
        autoload_session_fn(st.session_state)
    elif summary.status == "error":
        st.warning(
            "Этот run завершился без usable optimization artifacts — latest_optimization pointer автоматически не переключаю."
        )


def render_finished_optimization_job_panel(
    st: Any,
    job: Any,
    *,
    rc: int,
    soft_stop_requested: bool,
    clear_job_fn: Callable[[], None],
    rerun_fn: Callable[[Any], None],
    summarize_run_fn: Callable[[Any], Any] | None = None,
    save_ptr_fn: Callable[[Any, dict[str, Any]], None] | None = None,
    autoload_session_fn: Callable[[Any], None] | None = None,
    start_handoff_fn: Callable[[Any], bool] | None = None,
    render_handoff_action_fn: Callable[..., bool] = render_coordinator_handoff_action,
) -> bool:
    _render_finished_job_status(st, rc=rc, soft_stop_requested=soft_stop_requested)

    summarize = summarize_run_fn or summarize_optimization_run
    save_ptr = save_ptr_fn or run_artifacts.save_last_opt_ptr
    autoload = autoload_session_fn or run_artifacts.autoload_to_session

    try:
        summary = summarize(getattr(job, "run_dir"))
        _save_finished_job_pointer(
            st,
            job,
            summary,
            save_ptr_fn=save_ptr,
            autoload_session_fn=autoload,
        )
    except Exception as exc:
        st.warning(f"Не удалось сохранить указатель на последнюю оптимизацию: {exc}")

    if (
        int(rc) == 0
        and str(getattr(job, "pipeline_mode", "") or "") == "staged"
        and render_handoff_action_fn is not None
    ):
        render_handoff_action_fn(
            st,
            source_run_dir=getattr(job, "run_dir"),
            start_handoff_fn=start_handoff_fn,
            button_key="finished_job_start_coordinator_handoff",
            missing_caption=(
                "Coordinator handoff пока не собран для этого staged run. "
                "Он появляется после успешного завершения staged-пайплайна с auto tuner plan."
            ),
        )

    if st.button("Очистить статус запуска", help="Скрыть завершённую задачу и вернуться к настройкам"):
        clear_job_fn()
        rerun_fn(st)
    return True


__all__ = [
    "render_finished_optimization_job_panel",
]
