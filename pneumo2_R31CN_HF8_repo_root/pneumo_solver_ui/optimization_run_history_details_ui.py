from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

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
    heading: str = "Packaging snapshot по выбранному run",
    interference_prefix: str = "В выбранном run есть packaging-interference evidence",
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
            st.metric("Status=complete", int(packaging_snapshot.packaging_complete_rows))
        with pc6:
            st.metric(
                "Spring interference",
                int(packaging_snapshot.spring_pair_interference_rows + packaging_snapshot.spring_host_interference_rows),
            )
        with pc7:
            st.caption(
                f"Packaging evidence rows: {int(packaging_snapshot.rows_with_packaging)} / "
                f"{int(packaging_snapshot.rows_considered)} done-rows. Этот snapshot нарочно не переоценивает "
                "historical run по сегодняшнему base_json: здесь показаны только threshold-independent packaging "
                "truth / autoverif / interference сигналы."
            )
        return True

    if result_path is not None:
        st.caption(
            "В result-артефакте выбранного run пока нет packaging summary columns. "
            "Для детального просмотра всё равно можно открыть страницу результатов."
        )
    return False


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
) -> None:
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

    render_optimization_run_packaging_details(st, summary.result_path)
    render_optimization_run_log_tail(st, summary.log_path, load_log_text=load_log_text)


__all__ = [
    "render_optimization_run_log_tail",
    "render_optimization_run_packaging_details",
    "render_selected_optimization_run_details",
]
