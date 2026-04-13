from __future__ import annotations

import time
from typing import Any, Callable

from pneumo_solver_ui import run_artifacts
from pneumo_solver_ui.optimization_active_runtime_summary import (
    active_handoff_provenance_caption,
    active_runtime_penalty_gate_caption,
    active_runtime_progress_caption,
    active_runtime_recent_errors_caption,
    active_runtime_trial_health_caption,
    build_run_runtime_summary,
)
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


def _render_finished_job_runtime_diagnostics(
    st: Any,
    job: Any,
    summary: Any,
    *,
    active_launch_context: dict[str, Any] | None = None,
) -> None:
    if summary is None:
        return
    pipeline_mode = str(getattr(summary, "pipeline_mode", getattr(job, "pipeline_mode", "")) or "").strip()
    done_hint = getattr(summary, "done_count", None)
    if pipeline_mode == "staged":
        done_hint = getattr(summary, "row_count", done_hint)
    runtime_summary = build_run_runtime_summary(
        getattr(job, "run_dir", None),
        pipeline_mode=pipeline_mode,
        backend=str(getattr(job, "backend", getattr(summary, "backend", "")) or ""),
        budget=int(getattr(job, "budget", 0) or 0),
        done=done_hint,
        active_launch_context=active_launch_context,
    )
    if not runtime_summary:
        return
    is_handoff = str((active_launch_context or {}).get("kind") or "").strip() == "handoff"
    progress_caption = active_runtime_progress_caption(
        runtime_summary,
        prefix="Final handoff progress" if is_handoff else "Final run progress",
    )
    trial_health_caption = active_runtime_trial_health_caption(
        runtime_summary,
        prefix="Final handoff trial health" if is_handoff else "Final run trial health",
    )
    penalty_gate_caption = active_runtime_penalty_gate_caption(
        runtime_summary,
        prefix="Final handoff penalty gate" if is_handoff else "Final run penalty gate",
    )
    recent_errors_caption = active_runtime_recent_errors_caption(
        runtime_summary,
        prefix="Recent handoff errors" if is_handoff else "Recent run errors",
    )
    provenance_caption = active_handoff_provenance_caption(
        runtime_summary,
        prefix="Handoff provenance" if is_handoff else "Run provenance",
    )
    diagnostic_lines = [
        text
        for text in (
            progress_caption,
            trial_health_caption,
            penalty_gate_caption,
            recent_errors_caption,
            provenance_caption,
        )
        if str(text or "").strip()
    ]
    if not diagnostic_lines:
        return
    st.write("**Final runtime diagnostics**")
    for line in diagnostic_lines:
        st.caption(str(line))


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
    active_launch_context: dict[str, Any] | None = None,
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
        _render_finished_job_runtime_diagnostics(
            st,
            job,
            summary,
            active_launch_context=active_launch_context,
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
