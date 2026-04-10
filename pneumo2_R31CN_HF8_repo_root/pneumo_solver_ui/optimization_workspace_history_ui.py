from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from pneumo_solver_ui.optimization_page_readonly_ui import (
    current_objective_keys,
)
from pneumo_solver_ui.optimization_run_history import (
    discover_workspace_optimization_runs,
    format_run_choice,
)
from pneumo_solver_ui.optimization_run_history_details_ui import (
    render_selected_optimization_run_details,
)
from pneumo_solver_ui.optimization_run_pointer_actions_ui import (
    render_optimization_run_pointer_actions,
)


def render_workspace_run_history_block(
    st: Any,
    *,
    workspace_dir: Path,
    active_job: Any,
    session_state: Mapping[str, Any],
    default_objectives: Sequence[str],
    objectives_text_fn: Callable[[Sequence[str]], str],
    penalty_key_default: str,
    current_penalty_tol: Any,
    load_log_text: Callable[[Path], str],
    rerun_fn: Callable[[Any], None],
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    discover_runs_fn: Callable[..., list[Any]] = discover_workspace_optimization_runs,
    format_run_choice_fn: Callable[[Any], str] = format_run_choice,
    render_details_fn: Callable[..., Any] = render_selected_optimization_run_details,
    render_pointer_actions_fn: Callable[..., Any] = render_optimization_run_pointer_actions,
) -> None:
    active_run_dir = getattr(active_job, "run_dir", None) if active_job is not None else None
    summaries = discover_runs_fn(workspace_dir, active_run_dir=active_run_dir)
    if not summaries:
        st.info("В текущем workspace ещё нет запусков оптимизации на диске.")
        return

    st.caption(
        "Если вы запускаете оптимизации последовательно (например, сначала StageRunner, потом coordinator), "
        "это нормальный инженерный сценарий. staged и coordinator run dirs показаны одновременно, чтобы второй запуск "
        "не затирал понимание первого."
    )

    option_map = {str(item.run_dir): item for item in summaries}
    option_keys = list(option_map.keys())
    preferred = str(st.session_state.get("__opt_history_selected_run_dir") or option_keys[0])
    if preferred not in option_map:
        preferred = option_keys[0]
    selected_run_dir = st.selectbox(
        "Выберите run для разбора",
        options=option_keys,
        index=option_keys.index(preferred),
        key="__opt_history_selected_run_dir",
        format_func=lambda key: format_run_choice_fn(option_map[key]),
        help=(
            "Здесь сохраняется последовательность запусков по папкам run_dir. Это нужно, когда сначала был StageRunner, "
            "а потом coordinator (или наоборот)."
        ),
    )
    summary = option_map[selected_run_dir]

    cols = st.columns([1.2, 1.0, 1.0, 1.0])
    with cols[0]:
        st.metric("Статус", summary.status_label)
    with cols[1]:
        if summary.pipeline_mode == "staged":
            st.metric("Rows", int(summary.row_count))
        else:
            st.metric("DONE", int(summary.done_count))
    with cols[2]:
        if summary.pipeline_mode == "staged":
            st.metric("Pipeline", summary.backend)
        else:
            st.metric("ERROR", int(summary.error_count))
    with cols[3]:
        if summary.pipeline_mode == "coordinator":
            st.metric("RUNNING", int(summary.running_count))
        else:
            st.metric("Run dir", summary.run_dir.name)

    render_details_fn(
        st,
        summary,
        current_objective_keys=tuple(
            current_objective_keys(
                session_state,
                default_objectives=default_objectives,
                objectives_text_fn=objectives_text_fn,
            )
        ),
        current_penalty_key=str(
            session_state.get("opt_penalty_key", penalty_key_default) or penalty_key_default
        ).strip(),
        current_penalty_tol=current_penalty_tol,
        load_log_text=load_log_text,
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
    )

    render_pointer_actions_fn(
        st,
        summary,
        key_prefix="opt_history",
        rerun_fn=rerun_fn,
        selected_from="optimization_history",
        make_latest_label="Сделать текущей «последней оптимизацией»",
        make_latest_help="Перепривязать глобальный latest_optimization pointer к выбранному run_dir.",
        open_results_label="Открыть результаты выбранного run",
        open_results_help="Сначала перепривязать latest_optimization, затем открыть страницу результатов.",
        results_page="pages/20_DistributedOptimization.py",
    )


__all__ = [
    "render_workspace_run_history_block",
]
