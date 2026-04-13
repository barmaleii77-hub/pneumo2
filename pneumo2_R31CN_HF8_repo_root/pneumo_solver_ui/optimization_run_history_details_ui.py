from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from pneumo_solver_ui.optimization_active_runtime_summary import (
    active_handoff_provenance_caption,
    active_runtime_penalty_gate_caption,
    active_runtime_progress_caption,
    active_runtime_recent_errors_caption,
    active_runtime_trial_health_caption,
)
from pneumo_solver_ui.optimization_coordinator_handoff_ui import (
    render_coordinator_handoff_action,
)
from pneumo_solver_ui.optimization_contract_summary_ui import (
    compare_objective_contract_to_current,
    render_objective_contract_drift_warning,
    render_objective_contract_summary,
)
from pneumo_solver_ui.optimization_packaging_snapshot_ui import (
    render_packaging_snapshot_summary,
)
from pneumo_solver_ui.optimization_problem_scope_ui import (
    render_problem_scope_summary,
)
from pneumo_solver_ui.optimization_run_history import (
    summarize_run_packaging_snapshot,
)


def _run_dir_key(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve())
    except Exception:
        return text


def _render_active_run_marker(
    st: Any,
    summary: Any,
    *,
    active_run_dir: Any = None,
    active_launch_context: dict[str, Any] | None = None,
    active_runtime_summary: dict[str, Any] | None = None,
) -> bool:
    selected_run_dir = _run_dir_key(getattr(summary, "run_dir", None))
    current_active_run_dir = _run_dir_key(active_run_dir)
    if not selected_run_dir or not current_active_run_dir or selected_run_dir != current_active_run_dir:
        return False

    context = dict(active_launch_context or {})
    is_handoff = str(context.get("kind") or "").strip() == "handoff"
    progress_caption = active_runtime_progress_caption(
        active_runtime_summary,
        prefix="Active handoff progress" if is_handoff else "Active run progress",
    )
    trial_health_caption = active_runtime_trial_health_caption(
        active_runtime_summary,
        prefix="Active handoff trial health" if is_handoff else "Active run trial health",
    )
    penalty_gate_caption = active_runtime_penalty_gate_caption(
        active_runtime_summary,
        prefix="Active handoff penalty gate" if is_handoff else "Active run penalty gate",
    )
    recent_errors_caption = active_runtime_recent_errors_caption(
        active_runtime_summary,
        prefix="Recent handoff errors" if is_handoff else "Recent run errors",
    )
    provenance_caption = active_handoff_provenance_caption(
        active_runtime_summary,
        prefix="Handoff provenance" if is_handoff else "Run provenance",
    )
    if str(context.get("kind") or "").strip() == "handoff":
        source_run_dir = _run_dir_key(context.get("source_run_dir"))
        source_name = Path(source_run_dir).name if source_run_dir else "staged run"
        st.info(
            "LIVE NOW: сейчас это активный seeded full-ring coordinator handoff "
            f"из staged run `{source_name}`."
        )
        if progress_caption:
            st.caption(progress_caption)
        if trial_health_caption:
            st.caption(trial_health_caption)
        if penalty_gate_caption:
            st.caption(penalty_gate_caption)
        if recent_errors_caption:
            st.caption(recent_errors_caption)
        if provenance_caption:
            st.caption(provenance_caption)
        return True

    st.info("LIVE NOW: этот optimization run сейчас выполняется в текущей сессии.")
    if progress_caption:
        st.caption(progress_caption)
    if trial_health_caption:
        st.caption(trial_health_caption)
    if penalty_gate_caption:
        st.caption(penalty_gate_caption)
    if recent_errors_caption:
        st.caption(recent_errors_caption)
    if provenance_caption:
        st.caption(provenance_caption)
    return True


def render_optimization_run_log_tail(
    st: Any,
    log_path: Path | None,
    *,
    load_log_text: Callable[[Path], str],
    max_chars: int = 8000,
) -> bool:
    if log_path is None:
        return False
    log_text = load_log_text(log_path)
    if log_text:
        st.code(log_text[-max_chars:] if len(log_text) > max_chars else log_text)
        return True
    st.caption(
        "Лог-файл существует, но сейчас пуст. Для staged run это не обязательно означает провал: "
        "ориентируйтесь на sp.json / CSV / trial export."
    )
    return False


def render_optimization_run_packaging_details(
    st: Any,
    result_path: Path | None,
    *,
    heading: str = "Сводка по геометрии узлов (выбранный run)",
    interference_prefix: str = "В выбранном run есть признаки пересечений по геометрии узлов",
) -> bool:
    packaging_snapshot = summarize_run_packaging_snapshot(result_path)
    if render_packaging_snapshot_summary(
        st,
        packaging_snapshot,
        compact=False,
        heading=heading,
        interference_prefix=interference_prefix,
    ):
        pc5, pc6, pc7 = st.columns([1, 1, 2])
        with pc5:
            st.metric("Полных строк", int(packaging_snapshot.packaging_complete_rows))
        with pc6:
            st.metric(
                "Пересечения пружин и цилиндров",
                int(packaging_snapshot.spring_pair_interference_rows + packaging_snapshot.spring_host_interference_rows),
            )
        with pc7:
            st.caption(
                f"Строк с evidence по геометрии: {int(packaging_snapshot.rows_with_packaging)} / "
                f"{int(packaging_snapshot.rows_considered)} done-rows. Этот snapshot нарочно не переоценивает "
                "historical run по сегодняшнему base_json: здесь показаны только threshold-independent сигналы "
                "по достаточности данных, автопроверке и пересечениям."
            )
        return True

    if result_path is not None:
        st.caption(
            "В result-артефакте выбранного run пока нет packaging summary columns. "
            "Для детального просмотра всё равно можно открыть страницу результатов."
        )
    return False


def _render_final_runtime_summary(
    st: Any,
    summary: Any,
    *,
    active_run_dir: Any = None,
) -> bool:
    selected_run_dir = _run_dir_key(getattr(summary, "run_dir", None))
    current_active_run_dir = _run_dir_key(active_run_dir)
    if selected_run_dir and current_active_run_dir and selected_run_dir == current_active_run_dir:
        return False
    runtime_summary = dict(getattr(summary, "runtime_summary", None) or {})
    if not runtime_summary:
        return False
    is_handoff = str(getattr(summary, "backend", "") or "").startswith("Handoff/")
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
        return False
    st.write("**Final runtime diagnostics**")
    for line in diagnostic_lines:
        st.caption(str(line))
    return True


def render_selected_optimization_run_details(
    st: Any,
    summary: Any,
    *,
    current_objective_keys: Iterable[Any],
    current_penalty_key: Any,
    current_penalty_tol: Any,
    load_log_text: Callable[[Path], str],
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    start_handoff_fn: Callable[[Path], bool] | None = None,
    active_run_dir: Any = None,
    active_launch_context: dict[str, Any] | None = None,
    active_runtime_summary: dict[str, Any] | None = None,
    render_handoff_action_fn: Callable[..., bool] = render_coordinator_handoff_action,
) -> None:
    _render_active_run_marker(
        st,
        summary,
        active_run_dir=active_run_dir,
        active_launch_context=active_launch_context,
        active_runtime_summary=active_runtime_summary,
    )
    st.write(f"**Pipeline:** {summary.backend}")
    st.write(f"**run_dir:** `{summary.run_dir}`")
    if summary.result_path is not None:
        st.write(f"**Артефакт результатов:** `{summary.result_path}`")
    if summary.started_at:
        st.write(f"**Started hint:** `{summary.started_at}`")
    render_problem_scope_summary(
        st,
        summary=summary,
        run_dir=getattr(summary, "run_dir", None),
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
    )
    baseline_source_label = str(getattr(summary, "baseline_source_label", "") or "").strip()
    baseline_source_path = getattr(summary, "baseline_source_path", None)
    if baseline_source_label:
        st.write(f"**Baseline source:** {baseline_source_label}")
        if baseline_source_path is not None:
            st.caption(f"Baseline override at launch: `{baseline_source_path}`")
    if summary.note:
        st.caption(summary.note)
    if summary.last_error:
        st.warning("Последняя ошибка из артефактов: " + summary.last_error)
    if str(getattr(summary, "handoff_preset_tag", "") or "").strip():
        st.write(
            "**Coordinator handoff:** "
            + str(getattr(summary, "handoff_preset_tag", "") or "")
        )
        st.caption(
            "Рекомендуемый full-ring handoff: "
            f"budget={int(getattr(summary, 'handoff_budget', 0) or 0)}, "
            f"seed-candidates={int(getattr(summary, 'handoff_seed_count', 0) or 0)}, "
            f"suite={str(getattr(summary, 'handoff_suite_family', '') or 'unknown')}."
        )
        for line in tuple(getattr(summary, "handoff_reason_lines", ()) or ()):
            st.caption(str(line))
        if bool(getattr(summary, "handoff_requires_full_ring_validation", False)):
            st.caption(
                "Этот historical handoff требовал обязательную проверку на полном пользовательском кольце."
            )
        handoff_plan_path = getattr(summary, "handoff_plan_path", None)
        if handoff_plan_path is not None:
            st.caption(f"Handoff plan: `{handoff_plan_path}`")

    render_objective_contract_summary(
        st,
        objective_keys=summary.objective_keys,
        penalty_key=summary.penalty_key,
        penalty_tol=summary.penalty_tol,
        objective_contract_path=summary.objective_contract_path,
    )

    contract_diff_bits = compare_objective_contract_to_current(
        objective_keys=summary.objective_keys,
        penalty_key=summary.penalty_key,
        penalty_tol=summary.penalty_tol,
        current_objective_keys=current_objective_keys,
        current_penalty_key=current_penalty_key,
        current_penalty_tol=current_penalty_tol,
    )
    render_objective_contract_drift_warning(st, contract_diff_bits)

    _render_final_runtime_summary(
        st,
        summary,
        active_run_dir=active_run_dir,
    )
    render_optimization_run_packaging_details(st, summary.result_path)
    render_optimization_run_log_tail(st, summary.log_path, load_log_text=load_log_text)
    if str(getattr(summary, "pipeline_mode", "") or "") == "staged" and render_handoff_action_fn is not None:
        render_handoff_action_fn(
            st,
            source_run_dir=getattr(summary, "run_dir"),
            start_handoff_fn=start_handoff_fn,
            button_key=f"history_start_handoff_{Path(getattr(summary, 'run_dir')).name}",
            missing_caption="Для выбранного staged run на диске пока нет coordinator handoff плана.",
        )


__all__ = [
    "render_optimization_run_log_tail",
    "render_optimization_run_packaging_details",
    "render_selected_optimization_run_details",
]
