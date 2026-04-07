from __future__ import annotations

"""Shared selection/mapping helpers for large UI entrypoints."""

import copy
import hashlib
import json
from typing import Any, Dict, List, Tuple

from pneumo_solver_ui.ui_shared_helpers import best_match as _best_match


def apply_pick_list(cur: Any, name: str, mode: str) -> List[str]:
    """Update a selected-name list in add/replace mode."""
    if cur is None:
        cur_list: List[str] = []
    elif isinstance(cur, list):
        cur_list = list(cur)
    else:
        try:
            cur_list = list(cur)
        except Exception:
            cur_list = []

    if mode == "replace":
        return [name]
    if name not in cur_list:
        cur_list.append(name)
    return cur_list


def extract_plotly_selection_points(plot_state: Any) -> List[Dict[str, Any]]:
    """Best-effort extraction of Plotly selection points from Streamlit state."""
    if plot_state is None:
        return []

    sel = None
    try:
        sel = plot_state.get("selection") if isinstance(plot_state, dict) else getattr(plot_state, "selection", None)
    except Exception:
        sel = None

    if sel is None:
        try:
            sel = plot_state["selection"]
        except Exception:
            sel = None

    if sel is None:
        return []

    try:
        pts = sel.get("points") if isinstance(sel, dict) else getattr(sel, "points", None)
    except Exception:
        pts = None

    if pts is None:
        try:
            pts = sel["points"]
        except Exception:
            pts = None

    if pts is None:
        return []

    out: List[Dict[str, Any]] = []
    if isinstance(pts, list):
        for point in pts:
            if isinstance(point, dict):
                out.append(point)
            else:
                try:
                    out.append(dict(point))
                except Exception:
                    pass
    return out


def plotly_points_signature(points: List[Dict[str, Any]]) -> str:
    """Small stable signature for deduplicating Plotly selection events."""
    sig_items = []
    for point in points:
        curve_number = point.get("curve_number", point.get("curveNumber"))
        point_index = point.get(
            "point_index",
            point.get("pointIndex", point.get("point_number", point.get("pointNumber"))),
        )
        try:
            curve_i = int(curve_number) if curve_number is not None else -1
        except Exception:
            curve_i = -1
        try:
            point_i = int(point_index) if point_index is not None else -1
        except Exception:
            point_i = -1
        sig_items.append((curve_i, point_i))

    sig_items = sorted(set(sig_items))
    payload = json.dumps(sig_items, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def strip_svg_xml_header(svg_text: str) -> str:
    """Return the SVG fragment starting from the first `<svg` tag."""
    if not svg_text:
        return ""
    pos = svg_text.find("<svg")
    if pos >= 0:
        return svg_text[pos:]
    return svg_text


def ensure_mapping_for_selection(
    mapping: Dict[str, Any],
    need_edges: List[str],
    need_nodes: List[str],
    min_score: float = 0.70,
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """Backfill missing mapping keys using best-match name lookup."""
    mapping_use = copy.deepcopy(mapping) if isinstance(mapping, dict) else {}
    report: Dict[str, List[Dict[str, Any]]] = {"edges": [], "nodes": []}

    edges_dict = mapping_use.get("edges")
    if not isinstance(edges_dict, dict):
        edges_dict = {}
    nodes_dict = mapping_use.get("nodes")
    if not isinstance(nodes_dict, dict):
        nodes_dict = {}

    edge_keys = list(edges_dict.keys())
    node_keys = list(nodes_dict.keys())

    for name in need_edges or []:
        if not isinstance(name, str) or not name:
            continue
        if edges_dict.get(name):
            continue
        best, score = _best_match(name, edge_keys)
        if best is not None and score >= float(min_score) and edges_dict.get(best):
            edges_dict[name] = edges_dict.get(best)
            report["edges"].append({"need": name, "from": best, "score": score})

    for name in need_nodes or []:
        if not isinstance(name, str) or not name:
            continue
        val = nodes_dict.get(name)
        if isinstance(val, list) and len(val) >= 2:
            continue
        best, score = _best_match(name, node_keys)
        if best is not None and score >= float(min_score):
            best_val = nodes_dict.get(best)
            if isinstance(best_val, list) and len(best_val) >= 2:
                nodes_dict[name] = best_val
                report["nodes"].append({"need": name, "from": best, "score": score})

    mapping_use["edges"] = edges_dict
    mapping_use["nodes"] = nodes_dict
    return mapping_use, report


__all__ = [
    "apply_pick_list",
    "ensure_mapping_for_selection",
    "extract_plotly_selection_points",
    "plotly_points_signature",
    "strip_svg_xml_header",
]
