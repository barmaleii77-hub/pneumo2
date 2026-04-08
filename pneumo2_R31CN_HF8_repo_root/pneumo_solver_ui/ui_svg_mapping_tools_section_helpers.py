from __future__ import annotations

from pathlib import Path
from typing import Any

from pneumo_solver_ui.ui_svg_mapping_input_helpers import (
    render_svg_mapping_input,
)
from pneumo_solver_ui.ui_svg_post_mapping_helpers import (
    render_svg_post_mapping_sections,
)


def render_svg_mapping_tools_section(
    st: Any,
    session_state: dict[str, Any],
    *,
    default_svg_mapping_path: Path,
    do_rerun_fn: Any,
    log_event_fn: Any,
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
) -> Any:
    st.markdown("### Анимация по схеме (по mapping JSON)")
    current_source = session_state.get("svg_mapping_source", "(не задан)")
    st.caption(f"Источник mapping: {current_source}")

    col_map1, col_map2 = st.columns([1.0, 1.0], gap="medium")
    with col_map1:
        if st.button(
            "Сбросить mapping к default",
            key="svg_mapping_reset_default",
            help="Загрузить default_svg_mapping.json из пакета приложения.",
        ):
            try:
                session_state["svg_mapping_text"] = default_svg_mapping_path.read_text(encoding="utf-8")
                session_state["svg_mapping_source"] = str(default_svg_mapping_path)
                log_event_fn("svg_mapping_reset_default", path=str(default_svg_mapping_path))
                do_rerun_fn()
            except Exception as exc:
                st.error(f"Не удалось загрузить default mapping: {exc}")
                log_event_fn("svg_mapping_reset_default_failed", error=repr(exc))

    with col_map2:
        try:
            current_bytes = (session_state.get("svg_mapping_text", "") or "").encode("utf-8")
            st.download_button(
                "Скачать текущий mapping.json",
                data=current_bytes,
                file_name="mapping.json",
                mime="application/json",
                help="Скачивает содержимое mapping из текстового поля (как сейчас в UI).",
            )
        except Exception:
            pass

    mapping = render_svg_mapping_input(
        st,
        session_state,
        log_event_fn=log_event_fn,
    )
    render_svg_post_mapping_sections(
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
        evaluate_quality_fn=evaluate_quality_fn,
    )
    return mapping
