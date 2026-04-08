from __future__ import annotations

from pathlib import Path
from typing import Any

from pneumo_solver_ui.ui_svg_html_builders import (
    render_svg_edge_mapper_html,
    render_svg_node_mapper_html,
)
from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (
    render_svg_mapping_tools_section,
)


def default_svg_mapper_node_names(
    selected_node_names: list[str] | None,
    node_columns: list[str],
) -> list[str]:
    if selected_node_names:
        return list(selected_node_names)
    if not node_columns:
        return []
    return list(node_columns[: min(20, len(node_columns))])


def render_svg_mapping_workbench_section(
    st: Any,
    session_state: dict[str, Any],
    *,
    default_svg_mapping_path: Path,
    do_rerun_fn: Any,
    log_event_fn: Any,
    edge_columns: list[str],
    node_columns: list[str],
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
) -> Any:
    with st.expander("Разметка веток (edges)", expanded=False):
        st.info(
            "Инструмент ниже создаёт mapping.edges локально в браузере. "
            "Нажмите Download/Copy и потом загрузите JSON обратно в блоке анимации. "
            "Если в JSON уже есть mapping.nodes — они сохранятся."
        )
        render_svg_edge_mapper_html(
            svg_inline=svg_inline,
            edge_names=edge_columns,
            height=760,
        )

    with st.expander("Разметка узлов давления (nodes)", expanded=False):
        st.info(
            "Инструмент ниже размечает mapping.nodes (координаты узлов давления). "
            "Можно вставить сюда JSON после разметки веток и дополнить узлами."
        )
        node_names_for_mapper = default_svg_mapper_node_names(
            selected_node_names,
            node_columns,
        )
        render_svg_node_mapper_html(
            svg_inline=svg_inline,
            node_names=node_names_for_mapper,
            edge_names=edge_columns,
            height=760,
        )

    return render_svg_mapping_tools_section(
        st,
        session_state,
        default_svg_mapping_path=default_svg_mapping_path,
        do_rerun_fn=do_rerun_fn,
        log_event_fn=log_event_fn,
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
        evaluate_quality_fn=evaluate_quality_fn,
    )
