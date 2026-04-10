from __future__ import annotations

from typing import Any, Callable

from pneumo_solver_ui.optimization_baseline_source_ui import (
    render_baseline_source_summary,
)
from pneumo_solver_ui.optimization_problem_scope_ui import (
    render_problem_scope_summary,
)


def render_live_optimization_job_panel(
    st: Any,
    job: Any,
    *,
    log_text: str,
    soft_stop_requested: bool,
    coordinator_done: int | None,
    render_stage_runtime: Callable[[], None] | None,
    write_soft_stop_file_fn: Callable[[Any], bool],
    terminate_process_fn: Callable[[Any], None],
    rerun_fn: Callable[[Any], None],
    sleep_fn: Callable[[float], None],
    running_message: str,
    soft_stop_active_message: str,
    soft_stop_label: str,
    soft_stop_help: str,
    soft_stop_success_message: str,
    soft_stop_error_message: str,
    hard_stop_label: str,
    hard_stop_help: str,
    hard_stop_warning_message: str,
    hard_stop_with_stopfile_warning: str,
    hard_only_label: str,
    hard_only_help: str,
    hard_only_error_prefix: str,
    refresh_label: str,
    refresh_help: str,
    auto_refresh_label: str,
    auto_refresh_help: str,
    auto_refresh_default: bool,
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    auto_refresh_key: str = "__opt_autorefresh_enabled",
    log_tail_chars: int = 8000,
) -> bool:
    st.info(running_message)
    if soft_stop_requested:
        st.warning(soft_stop_active_message)

    if str(getattr(job, "pipeline_mode", "") or "") == "staged":
        if render_stage_runtime is not None:
            render_stage_runtime()
    elif coordinator_done is not None and int(getattr(job, "budget", 0) or 0) > 0:
        done = int(coordinator_done)
        budget = int(getattr(job, "budget", 0) or 0)
        st.progress(min(1.0, max(0.0, done / float(budget))))
        st.caption(f"Выполнено: {done} из {budget}")

    render_baseline_source_summary(
        st,
        run_dir=getattr(job, "run_dir", None),
    )
    render_problem_scope_summary(
        st,
        run_dir=getattr(job, "run_dir", None),
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
    )

    st.code(log_text[-log_tail_chars:] if len(log_text) > log_tail_chars else log_text)

    if getattr(job, "stop_file", None) is not None:
        c_stop_soft, c_stop_hard, c_refresh, _ = st.columns([1, 1, 1, 3])
        with c_stop_soft:
            if st.button(soft_stop_label, type="secondary", help=soft_stop_help):
                if write_soft_stop_file_fn(getattr(job, "stop_file", None)):
                    st.warning(soft_stop_success_message)
                    rerun_fn(st)
                else:
                    st.error(soft_stop_error_message)
        with c_stop_hard:
            if st.button(hard_stop_label, type="secondary", help=hard_stop_help):
                if not write_soft_stop_file_fn(getattr(job, "stop_file", None)):
                    st.warning(hard_stop_with_stopfile_warning)
                terminate_process_fn(getattr(job, "proc"))
                st.warning(hard_stop_warning_message)
                rerun_fn(st)
        with c_refresh:
            if st.button(refresh_label, help=refresh_help):
                rerun_fn(st)
    else:
        c_stop, c_refresh, _ = st.columns([1, 1, 3])
        with c_stop:
            if st.button(hard_only_label, type="secondary", help=hard_only_help):
                try:
                    terminate_process_fn(getattr(job, "proc"))
                    st.warning(hard_stop_warning_message)
                    rerun_fn(st)
                except Exception as exc:
                    st.error(f"{hard_only_error_prefix}: {exc}")
        with c_refresh:
            if st.button(refresh_label, help=refresh_help):
                rerun_fn(st)

    auto_refresh = st.checkbox(
        auto_refresh_label,
        value=bool(auto_refresh_default),
        key=auto_refresh_key,
        help=auto_refresh_help,
    )
    if auto_refresh:
        sleep_fn(2.0)
        rerun_fn(st)
    return True


__all__ = [
    "render_live_optimization_job_panel",
]
