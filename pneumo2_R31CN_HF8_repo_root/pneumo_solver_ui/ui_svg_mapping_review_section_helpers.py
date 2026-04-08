from __future__ import annotations

import copy
from typing import Any

from pneumo_solver_ui.ui_svg_mapping_review_actions_helpers import (
    render_svg_mapping_review_actions,
)
from pneumo_solver_ui.ui_svg_mapping_review_panel_helpers import (
    render_svg_mapping_review_panel,
)


def normalize_svg_mapping_review_payload(mapping: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    mapping_copy = copy.deepcopy(mapping) if isinstance(mapping, dict) else {}
    if not isinstance(mapping_copy, dict):
        mapping_copy = {}
    mapping_copy.setdefault("version", 2)
    mapping_copy.setdefault("edges", {})
    mapping_copy.setdefault("nodes", {})
    mapping_copy.setdefault("edges_meta", {})
    if not isinstance(mapping_copy.get("edges"), dict):
        mapping_copy["edges"] = {}
    if not isinstance(mapping_copy.get("edges_meta"), dict):
        mapping_copy["edges_meta"] = {}
    return mapping_copy, mapping_copy["edges"], mapping_copy["edges_meta"]


def make_svg_edge_first_poly_reader(edges_geo: dict[str, Any]) -> Any:
    def _first_poly(edge_name: str):
        try:
            segments = edges_geo.get(edge_name, None)
            if isinstance(segments, list) and segments:
                first_poly = segments[0]
                if isinstance(first_poly, list) and len(first_poly) >= 2:
                    return first_poly
        except Exception:
            pass
        return None

    return _first_poly


def render_svg_mapping_review_section(
    st: Any,
    session_state: dict[str, Any],
    *,
    mapping: Any,
    edge_columns: list[str] | None,
    evaluate_quality_fn: Any,
    safe_dataframe_fn: Any,
) -> None:
    with st.expander("Review / Quality: mapping.edges_meta (approve/reject)", expanded=False):
        mapping_copy, edges_geo, edges_meta = normalize_svg_mapping_review_payload(mapping)
        first_poly_fn = make_svg_edge_first_poly_reader(edges_geo)

        render_svg_mapping_review_actions(
            st,
            session_state,
            edges_geo=edges_geo,
            edges_meta=edges_meta,
            mapping=mapping_copy,
            first_poly_fn=first_poly_fn,
            evaluate_quality_fn=evaluate_quality_fn,
        )
        render_svg_mapping_review_panel(
            st,
            session_state,
            edge_columns=edge_columns,
            edges_geo=edges_geo,
            edges_meta=edges_meta,
            mapping=mapping_copy,
            first_poly_fn=first_poly_fn,
            safe_dataframe_fn=safe_dataframe_fn,
        )
