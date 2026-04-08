from __future__ import annotations

import time
from typing import Any, Callable, Mapping, MutableMapping

from pneumo_solver_ui.ui_svg_mapping_helpers import write_svg_edge_route
from pneumo_solver_ui.ui_svg_mapping_state_helpers import update_svg_mapping_meta
from pneumo_solver_ui.ui_svg_route_report_helpers import resolve_svg_route_quality_params


def evaluate_svg_route_quality_for_assignment(
    session_state: MutableMapping[str, Any],
    polyline: list[list[float]],
    route_report: Mapping[str, Any] | Any,
    *,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    quality_params = resolve_svg_route_quality_params(session_state)
    try:
        quality_report = evaluate_quality_fn(
            polyline,
            attach_start=route_report.get("attach_start") if isinstance(route_report, Mapping) else None,
            attach_end=route_report.get("attach_end") if isinstance(route_report, Mapping) else None,
            min_turn_deg=float(quality_params.get("min_turn_deg", 45.0)),
            max_detour=float(quality_params.get("max_detour", 8.0)),
            max_attach_dist=float(quality_params.get("max_attach_dist", 35.0)),
        )
        session_state["svg_route_quality"] = quality_report
        return quality_report
    except Exception:
        return None


def build_svg_route_assignment_edge_meta(
    session_state: MutableMapping[str, Any],
    polyline: list[list[float]],
    route_report: Mapping[str, Any] | Any,
    quality_report: Mapping[str, Any] | None,
    *,
    timestamp: float,
) -> dict[str, Any]:
    route_length = float(route_report.get("length", 0.0) or 0.0) if isinstance(route_report, Mapping) else 0.0
    return {
        "manual": True,
        "quality": quality_report,
        "review": {"status": "approved", "by": "manual", "ts": float(timestamp)},
        "route": {
            "length_px": route_length,
            "points": int(len(polyline)),
        },
        "start_end": session_state.get("svg_route_label_picks", {}),
    }


def write_svg_route_assignment(
    mapping: dict[str, Any],
    session_state: MutableMapping[str, Any],
    edge_name: str,
    polyline: list[list[float]],
    mode: str,
    route_report: Mapping[str, Any] | Any,
    *,
    view_box: Any,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
    timestamp: float | None = None,
) -> Mapping[str, Any] | None:
    effective_timestamp = float(time.time() if timestamp is None else timestamp)
    quality_report = evaluate_svg_route_quality_for_assignment(
        session_state,
        polyline,
        route_report,
        evaluate_quality_fn=evaluate_quality_fn,
    )
    edge_meta = build_svg_route_assignment_edge_meta(
        session_state,
        polyline,
        route_report,
        quality_report,
        timestamp=effective_timestamp,
    )
    write_svg_edge_route(
        mapping,
        edge_name,
        polyline,
        mode,
        edge_meta,
        view_box=view_box,
    )
    update_svg_mapping_meta(
        mapping,
        "last_route_assign",
        {
            "edge": edge_name,
            "mode": mode,
            "route_length_px": float(route_report.get("length", 0.0) or 0.0) if isinstance(route_report, Mapping) else 0.0,
            "points": int(len(polyline)),
            "ts": effective_timestamp,
        },
    )
    return quality_report
