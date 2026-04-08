from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping, MutableMapping

from pneumo_solver_ui.ui_svg_mapping_helpers import (
    clear_svg_edge_route,
    ensure_svg_edge_mapping_store,
)
from pneumo_solver_ui.ui_svg_mapping_state_helpers import finalize_svg_route_mapping_edit
from pneumo_solver_ui.ui_svg_route_assign_helpers import write_svg_route_assignment


def load_svg_mapping_for_route_edit(mapping_text: object, *, view_box: Any) -> dict[str, Any]:
    text = str(mapping_text or "").strip()
    if text:
        mapping = json.loads(text)
        if not isinstance(mapping, dict):
            raise ValueError("mapping JSON должен быть объектом (dict).")
    else:
        mapping = {"version": 2, "viewBox": view_box, "edges": {}, "nodes": {}}
    ensure_svg_edge_mapping_store(mapping, view_box=view_box)
    return mapping


def apply_svg_route_mapping_edit(
    session_state: MutableMapping[str, Any],
    mapping_text: object,
    edge_name: str,
    edge_columns: Iterable[str],
    *,
    mapping_view_box: Any,
    route_write_view_box: Any,
    clear_edge: bool,
    assign_route: bool,
    polyline: list[list[float]] | None,
    mode: str,
    route_report: Mapping[str, Any] | Any,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> tuple[dict[str, Any], str]:
    mapping = load_svg_mapping_for_route_edit(mapping_text, view_box=mapping_view_box)
    message = ""

    if clear_edge:
        clear_svg_edge_route(mapping, edge_name, view_box=mapping_view_box)
        message = f"Очищено: mapping.edges['{edge_name}']"

    if assign_route:
        if polyline is None:
            raise ValueError("Маршрут не готов для записи.")
        write_svg_route_assignment(
            mapping,
            session_state,
            edge_name,
            polyline,
            mode,
            route_report,
            view_box=route_write_view_box,
            evaluate_quality_fn=evaluate_quality_fn,
        )
        message = f"Маршрут записан в mapping.edges['{edge_name}'] ({mode})."

    finalize_svg_route_mapping_edit(
        session_state,
        mapping,
        edge_columns,
        assigned=bool(assign_route),
    )
    return mapping, message
