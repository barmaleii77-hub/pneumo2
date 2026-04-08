from __future__ import annotations

from typing import Any

from pneumo_solver_ui.ui_svg_animation_section_helpers import (
    render_svg_animation_section,
)
from pneumo_solver_ui.ui_svg_mapping_review_section_helpers import (
    render_svg_mapping_review_section,
)


def render_svg_post_mapping_sections(
    st: Any,
    session_state: dict[str, Any],
    *,
    mapping: Any,
    edge_columns: list[str],
    selected_node_names: list[str] | None,
    df_mdot,
    df_open,
    df_p,
    p_atm: float,
    model_module: Any,
    pressure_divisor: float,
    pressure_unit: str,
    dataset_id: str,
    safe_dataframe_fn: Any,
    flow_scale_and_unit_fn: Any,
    get_component_fn: Any,
    render_svg_flow_animation_html_fn: Any,
    svg_inline: str,
    evaluate_quality_fn: Any,
) -> str:
    if not mapping:
        st.warning("Нужен mapping JSON. Создайте его в разметчиках выше или загрузите файл.")
        return "missing_mapping"

    render_svg_mapping_review_section(
        st,
        session_state,
        mapping=mapping,
        edge_columns=edge_columns,
        evaluate_quality_fn=evaluate_quality_fn,
        safe_dataframe_fn=safe_dataframe_fn,
    )
    render_svg_animation_section(
        st,
        session_state,
        mapping=mapping,
        edge_columns=edge_columns,
        selected_node_names=selected_node_names,
        df_mdot=df_mdot,
        df_open=df_open,
        df_p=df_p,
        p_atm=p_atm,
        model_module=model_module,
        pressure_divisor=pressure_divisor,
        pressure_unit=pressure_unit,
        dataset_id=dataset_id,
        safe_dataframe_fn=safe_dataframe_fn,
        flow_scale_and_unit_fn=flow_scale_and_unit_fn,
        get_component_fn=get_component_fn,
        render_svg_flow_animation_html_fn=render_svg_flow_animation_html_fn,
        svg_inline=svg_inline,
    )
    return "ok"
