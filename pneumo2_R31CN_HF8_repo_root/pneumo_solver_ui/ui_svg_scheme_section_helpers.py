from __future__ import annotations

from pathlib import Path
from typing import Any

from pneumo_solver_ui.ui_svg_autotrace_helpers import (
    render_svg_autotrace_panel,
)
from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (
    render_svg_connectivity_panel,
)
from pneumo_solver_ui.ui_svg_scheme_input_helpers import (
    render_svg_scheme_inputs,
)
from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (
    render_svg_mapping_workbench_section,
)


def render_svg_scheme_section(
    st: Any,
    session_state: dict[str, Any],
    *,
    df_mdot,
    df_open,
    df_p,
    base_dir: Path,
    default_svg_mapping_path: Path,
    route_write_view_box: str,
    do_rerun_fn: Any,
    log_event_fn: Any,
    p_atm: float,
    model_module: Any,
    pressure_divisor: float,
    pressure_unit: str,
    dataset_id: str,
    safe_dataframe_fn: Any,
    flow_scale_and_unit_fn: Any,
    get_component_fn: Any,
    render_svg_flow_animation_html_fn: Any,
    has_svg_autotrace: bool,
    extract_polylines_fn: Any,
    auto_build_mapping_from_svg_fn: Any,
    detect_component_bboxes_fn: Any,
    name_score_fn: Any,
    shortest_path_fn: Any,
    evaluate_quality_fn: Any,
) -> None:
    if df_mdot is None:
        st.info("Анимация по схеме (SVG) доступна только при record_full=True (df_mdot + mapping).")
        return

    scheme_inputs = render_svg_scheme_inputs(
        st,
        df_mdot=df_mdot,
        df_p=df_p,
        base_dir=base_dir,
    )
    if scheme_inputs is None:
        return
    edge_columns = list(scheme_inputs["edge_columns"])
    node_columns = list(scheme_inputs["node_columns"])
    selected_node_names = list(scheme_inputs["selected_node_names"])
    svg_inline = str(scheme_inputs["svg_inline"])

    render_svg_autotrace_panel(
        st,
        svg_inline=svg_inline,
        edge_columns=edge_columns,
        selected_node_names=selected_node_names,
        node_columns=node_columns,
        has_svg_autotrace=has_svg_autotrace,
        extract_polylines_fn=extract_polylines_fn,
        auto_build_mapping_from_svg_fn=auto_build_mapping_from_svg_fn,
        detect_component_bboxes_fn=detect_component_bboxes_fn,
        safe_dataframe_fn=safe_dataframe_fn,
    )
    render_svg_connectivity_panel(
        st,
        session_state,
        edge_columns,
        route_write_view_box,
        name_score_fn=name_score_fn,
        shortest_path_fn=shortest_path_fn,
        evaluate_quality_fn=evaluate_quality_fn,
        safe_dataframe_fn=safe_dataframe_fn,
    )
    render_svg_mapping_workbench_section(
        st,
        session_state,
        default_svg_mapping_path=default_svg_mapping_path,
        do_rerun_fn=do_rerun_fn,
        log_event_fn=log_event_fn,
        edge_columns=edge_columns,
        node_columns=node_columns,
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
