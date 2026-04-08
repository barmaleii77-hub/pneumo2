from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping

from pneumo_solver_ui.ui_svg_mapping_state_helpers import store_svg_route_preview


SvgRoutePoint = tuple[float, float]


def resolve_svg_route_endpoints(
    texts: list[dict[str, Any]],
    start_option: Any,
    end_option: Any,
    option_to_index: Mapping[Any, int],
) -> tuple[SvgRoutePoint, SvgRoutePoint]:
    start_index = option_to_index.get(start_option, None)
    end_index = option_to_index.get(end_option, None)
    if start_index is None or end_index is None:
        raise ValueError("Не удалось распарсить индексы меток.")

    start_row = texts[int(start_index)]
    end_row = texts[int(end_index)]
    start_point = (float(start_row.get("x", 0.0)), float(start_row.get("y", 0.0)))
    end_point = (float(end_row.get("x", 0.0)), float(end_row.get("y", 0.0)))
    return start_point, end_point


def format_svg_route_success_message(route_report: Mapping[str, Any]) -> str:
    return (
        f"Путь найден: длина≈{float(route_report.get('length', 0.0)):.1f}px, "
        f"точек={len(route_report.get('path_xy', []))}."
    )


def find_svg_route_between_labels(
    session_state: MutableMapping[str, Any],
    texts: list[dict[str, Any]],
    start_option: Any,
    end_option: Any,
    option_to_index: Mapping[Any, int],
    analysis: Mapping[str, Any] | Any,
    simplify_epsilon: float,
    *,
    shortest_path_fn: Callable[..., Mapping[str, Any]],
) -> tuple[bool, str]:
    try:
        start_point, end_point = resolve_svg_route_endpoints(
            texts,
            start_option,
            end_option,
            option_to_index,
        )
        nodes = analysis.get("nodes", []) if isinstance(analysis, Mapping) else []
        edges = analysis.get("edges", []) if isinstance(analysis, Mapping) else []
        route = shortest_path_fn(
            nodes_coords=nodes,
            edges_ab=edges,
            p_start=start_point,
            p_end=end_point,
            snap_eps_px=0.25,
            simplify_epsilon=float(simplify_epsilon),
        )
        polyline = route.get("path_xy", []) if isinstance(route, Mapping) else []
        store_svg_route_preview(session_state, polyline, route)
        return True, format_svg_route_success_message(route)
    except Exception as exc:
        session_state["svg_route_paths"] = []
        session_state["svg_route_report"] = {"ok": False, "error": str(exc)}
        return False, f"Не удалось найти путь: {exc}"
