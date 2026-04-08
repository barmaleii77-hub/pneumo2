from __future__ import annotations

import json
from typing import Any


SVG_ROUTE_APPEND_SEGMENT_MODE = "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0441\u0435\u0433\u043c\u0435\u043d\u0442"


def load_svg_mapping_or_empty(mapping_text: object, *, view_box: Any) -> dict[str, Any]:
    text = str(mapping_text or "").strip()
    if text:
        try:
            mapping = json.loads(text)
            if isinstance(mapping, dict):
                return mapping
        except Exception:
            pass
    return {"version": 2, "viewBox": view_box, "edges": {}, "nodes": {}}


def ensure_svg_edge_mapping_store(mapping: dict[str, Any], *, view_box: Any) -> None:
    mapping.setdefault("version", 2)
    mapping.setdefault("viewBox", view_box)
    mapping.setdefault("edges", {})
    mapping.setdefault("nodes", {})
    if not isinstance(mapping.get("edges"), dict):
        mapping["edges"] = {}


def clear_svg_edge_route(mapping: dict[str, Any], edge_name: str, *, view_box: Any) -> None:
    ensure_svg_edge_mapping_store(mapping, view_box=view_box)
    mapping["edges"].pop(edge_name, None)


def write_svg_edge_route(
    mapping: dict[str, Any],
    edge_name: str,
    poly_xy: list[list[float]],
    mode: str,
    meta: dict[str, Any] | None,
    *,
    view_box: Any,
) -> None:
    ensure_svg_edge_mapping_store(mapping, view_box=view_box)
    if mode == SVG_ROUTE_APPEND_SEGMENT_MODE:
        segments = mapping["edges"].get(edge_name, [])
        if not isinstance(segments, list):
            segments = []
        segments.append(poly_xy)
        mapping["edges"][edge_name] = segments
    else:
        mapping["edges"][edge_name] = [poly_xy]

    mapping.setdefault("edges_meta", {})
    if not isinstance(mapping.get("edges_meta"), dict):
        mapping["edges_meta"] = {}
    try:
        existing = mapping["edges_meta"].get(edge_name, {})
    except Exception:
        existing = {}
    if isinstance(existing, dict) and isinstance(meta, dict):
        merged = dict(existing)
        for key, value in meta.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged_value = dict(merged.get(key, {}))
                merged_value.update(value)
                merged[key] = merged_value
            else:
                merged[key] = value
        mapping["edges_meta"][edge_name] = merged
    else:
        mapping["edges_meta"][edge_name] = meta
