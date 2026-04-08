from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def render_svg_animation_panel(
    st_module: Any,
    session_state: MutableMapping[str, Any],
    *,
    svg_inline: str,
    mapping: Any,
    time_s: list[float],
    edge_series: list[dict[str, Any]],
    node_series: list[dict[str, Any]],
    dataset_id: str,
    get_component_fn: Any,
    render_svg_flow_animation_html_fn: Any,
) -> Any:
    component = get_component_fn()
    selected = {
        "edge": session_state.get("svg_selected_edge"),
        "node": session_state.get("svg_selected_node"),
    }
    if component is not None:
        event = component(
            title="Анимация по схеме (SVG)",
            svg=svg_inline,
            mapping=mapping,
            show_review_overlay=bool(session_state.get("svg_show_review_overlay", True)),
            review_pick_mode=bool(session_state.get("svg_review_pick_mode", False)),
            review_statuses=session_state.get("svg_review_statuses", ["approved", "pending", "rejected"]),
            review_hud=bool(session_state.get("svg_review_hud", True)),
            route_paths=session_state.get("svg_route_paths", []),
            label_pick_mode=session_state.get("svg_label_pick_mode", ""),
            label_picks=session_state.get("svg_route_label_picks", {}),
            label_pick_radius=session_state.get("svg_label_pick_radius", 18),
            time=time_s,
            edges=edge_series,
            nodes=node_series,
            selected=selected,
            sync_playhead=True,
            playhead_storage_key="pneumo_play_state",
            dataset_id=dataset_id,
            height=760,
            key="svg_pick_event",
            default=None,
        )
        st_module.caption("Клик по ветке/узлу на схеме добавляет/заменяет выбор в графиках (см. переключатель выше).")
        return event

    render_svg_flow_animation_html_fn(
        svg_inline=svg_inline,
        mapping=mapping,
        time_s=time_s,
        edge_series=edge_series,
        node_series=node_series,
        height=760,
    )
    return None
