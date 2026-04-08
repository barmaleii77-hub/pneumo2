from __future__ import annotations

from pathlib import Path
from typing import Any

from pneumo_solver_ui.ui_svg_flow_helpers import (
    render_svg_click_mode_selector,
    render_svg_pressure_node_selector,
    render_svg_source_template_controls,
    svg_edge_columns,
    svg_pressure_node_columns,
)


def render_svg_scheme_inputs(
    st: Any,
    *,
    df_mdot,
    df_p,
    base_dir: Path,
) -> dict[str, Any] | None:
    st.caption(
        "Анимация поверх SVG схемы работает по mapping JSON: "
        "ветка → polyline(points), узел → [x,y] в координатах SVG."
    )

    render_svg_click_mode_selector(st, key="svg_click_mode")

    edge_columns = svg_edge_columns(df_mdot)
    node_columns = svg_pressure_node_columns(df_p)
    selected_node_names = render_svg_pressure_node_selector(
        st,
        node_columns,
        key="anim_nodes_svg",
    )
    _svg_text, svg_inline = render_svg_source_template_controls(
        st,
        base_dir=base_dir,
        edge_columns=edge_columns,
        selected_node_names=selected_node_names,
        uploader_key="svg_scheme_upl",
    )
    if svg_inline is None:
        return None
    return {
        "edge_columns": edge_columns,
        "node_columns": node_columns,
        "selected_node_names": selected_node_names,
        "svg_inline": svg_inline,
    }
