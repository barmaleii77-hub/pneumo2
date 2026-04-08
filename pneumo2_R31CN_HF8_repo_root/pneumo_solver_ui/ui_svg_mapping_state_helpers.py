from __future__ import annotations

import json
from typing import Any, Iterable, MutableMapping


def update_svg_mapping_meta(mapping: dict[str, Any], key: str, payload: Any) -> None:
    mapping.setdefault("meta", {})
    if not isinstance(mapping.get("meta"), dict):
        mapping["meta"] = {}
    mapping["meta"][key] = payload


def persist_svg_mapping_text(session_state: MutableMapping[str, Any], mapping: dict[str, Any]) -> None:
    session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)


def request_next_unmapped_svg_edge(
    session_state: MutableMapping[str, Any],
    mapping: Any,
    edge_columns: Iterable[str],
) -> None:
    try:
        edges = mapping.get("edges") if isinstance(mapping, dict) else {}
        if not isinstance(edges, dict):
            edges = {}
        mapped = set(edges.keys())
        unmapped = [edge_name for edge_name in edge_columns if edge_name not in mapped]
        if unmapped:
            session_state["route_advance_to_unmapped"] = unmapped[0]
    except Exception:
        pass


def store_svg_route_preview(
    session_state: MutableMapping[str, Any],
    polyline: Any,
    route_report: Any,
) -> None:
    session_state["svg_route_paths"] = [polyline]
    session_state["svg_route_report"] = route_report


def clear_svg_route_preview(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop("svg_route_paths", None)
    session_state.pop("svg_route_report", None)


def finalize_svg_route_mapping_edit(
    session_state: MutableMapping[str, Any],
    mapping: dict[str, Any],
    edge_columns: Iterable[str],
    *,
    assigned: bool,
) -> None:
    persist_svg_mapping_text(session_state, mapping)
    if session_state.get("route_auto_next", True):
        request_next_unmapped_svg_edge(session_state, mapping, edge_columns)
    if assigned and session_state.get("route_clear_after_assign", False):
        clear_svg_route_preview(session_state)
