from __future__ import annotations

from typing import Any

import pandas as pd

from pneumo_solver_ui.ui_interaction_helpers import (
    ensure_mapping_for_selection,
)


def resolve_svg_mapping_selection(
    mapping: Any,
    *,
    need_edges: list[str],
    need_nodes: list[str] | None,
    auto_match: bool,
    min_score: float,
) -> tuple[Any, dict[str, list[dict[str, Any]]]]:
    mapping_use = mapping
    report: dict[str, list[dict[str, Any]]] = {"edges": [], "nodes": []}
    if auto_match:
        mapping_use, report = ensure_mapping_for_selection(
            mapping=mapping,
            need_edges=need_edges,
            need_nodes=need_nodes,
            min_score=float(min_score),
        )
    return mapping_use, report


def render_svg_mapping_selection_report(
    st_module: Any,
    report: dict[str, list[dict[str, Any]]],
    *,
    safe_dataframe_fn: Any,
) -> None:
    if not (report.get("edges") or report.get("nodes")):
        return

    with st_module.expander("Отчёт автосопоставления", expanded=False):
        if report.get("edges"):
            st_module.markdown("**Ветки (edges)**")
            safe_dataframe_fn(
                pd.DataFrame(report["edges"]).sort_values("score", ascending=False),
                height=220,
            )
        if report.get("nodes"):
            st_module.markdown("**Узлы (nodes)**")
            safe_dataframe_fn(
                pd.DataFrame(report["nodes"]).sort_values("score", ascending=False),
                height=220,
            )


def prepare_svg_mapping_selection(
    st_module: Any,
    mapping: Any,
    *,
    need_edges: list[str],
    need_nodes: list[str] | None,
    auto_match: bool,
    min_score: float,
    safe_dataframe_fn: Any,
) -> tuple[Any, dict[str, list[dict[str, Any]]]]:
    mapping_use, report = resolve_svg_mapping_selection(
        mapping,
        need_edges=need_edges,
        need_nodes=need_nodes,
        auto_match=auto_match,
        min_score=float(min_score),
    )
    render_svg_mapping_selection_report(
        st_module,
        report,
        safe_dataframe_fn=safe_dataframe_fn,
    )
    return mapping_use, report
