from __future__ import annotations

from typing import Any, Callable, Iterable, MutableMapping


SvgRouteItem = tuple[int, str, float, float]


def apply_pending_svg_route_label_pick(
    session_state: MutableMapping[str, Any],
    pending: Any,
    items: Iterable[SvgRouteItem],
    options: list[str],
    option_to_index: dict[str, int],
    *,
    format_item_fn: Callable[[SvgRouteItem], str],
) -> tuple[list[str], dict[str, int]]:
    if not isinstance(pending, dict):
        return options, option_to_index

    updated_options = list(options)
    updated_option_to_index = dict(option_to_index)
    try:
        pick_mode = str(pending.get("mode", "")).strip().lower()
        text_index = pending.get("ti")
        x_coord = float(pending.get("x", 0.0))
        y_coord = float(pending.get("y", 0.0))
        label_name = str(pending.get("name", "")).strip()

        picked_item: SvgRouteItem | None = None
        if isinstance(text_index, int):
            for item in items:
                if int(item[0]) == int(text_index):
                    picked_item = item
                    break
        if picked_item is None:
            best_distance = 1e18
            for item in items:
                _, label, item_x, item_y = item
                if label_name and str(label).strip().lower() != label_name.lower():
                    continue
                distance = (float(item_x) - x_coord) ** 2 + (float(item_y) - y_coord) ** 2
                if distance < best_distance:
                    best_distance = distance
                    picked_item = item
        if picked_item is not None:
            picked_option = format_item_fn(picked_item)
            if picked_option not in updated_options:
                updated_options.append(picked_option)
                updated_option_to_index[picked_option] = int(picked_item[0])
            if pick_mode == "start":
                session_state["svg_route_start_opt"] = picked_option
            elif pick_mode == "end":
                session_state["svg_route_end_opt"] = picked_option

            picks = session_state.get("svg_route_label_picks")
            picks = dict(picks) if isinstance(picks, dict) else {}
            picks[pick_mode] = {
                "ti": int(picked_item[0]),
                "name": str(picked_item[1]),
                "x": float(picked_item[2]),
                "y": float(picked_item[3]),
            }
            session_state["svg_route_label_picks"] = picks
    except Exception:
        pass
    try:
        session_state.pop("svg_route_label_pick_pending", None)
    except Exception:
        pass
    return updated_options, updated_option_to_index


def resolve_svg_route_label_picks(
    items: Iterable[SvgRouteItem],
    start_option: Any,
    end_option: Any,
    option_to_index: dict[str, int],
) -> dict[str, dict[str, Any]]:
    picks: dict[str, dict[str, Any]] = {}
    start_index = option_to_index.get(start_option)
    end_index = option_to_index.get(end_option)
    if isinstance(start_index, int):
        for item in items:
            if int(item[0]) == int(start_index):
                picks["start"] = {
                    "ti": int(item[0]),
                    "name": str(item[1]),
                    "x": float(item[2]),
                    "y": float(item[3]),
                }
                break
    if isinstance(end_index, int):
        for item in items:
            if int(item[0]) == int(end_index):
                picks["end"] = {
                    "ti": int(item[0]),
                    "name": str(item[1]),
                    "x": float(item[2]),
                    "y": float(item[3]),
                }
                break
    return picks
