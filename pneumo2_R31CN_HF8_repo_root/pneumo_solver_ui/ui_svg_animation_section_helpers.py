from __future__ import annotations

from typing import Any

from pneumo_solver_ui.ui_svg_animation_panel_helpers import (
    render_svg_animation_panel,
)
from pneumo_solver_ui.ui_svg_mapping_selection_helpers import (
    prepare_svg_mapping_selection,
)
from pneumo_solver_ui.ui_svg_review_helpers import (
    render_svg_review_controls,
)
from pneumo_solver_ui.ui_svg_series_helpers import (
    prepare_svg_animation_series,
)


def filter_svg_animation_edges_by_review(
    edge_columns: list[str],
    mapping: Any,
    *,
    approved_only: bool,
) -> list[str]:
    edge_options = list(edge_columns)
    try:
        if approved_only and isinstance(mapping, dict):
            edges_meta = mapping.get("edges_meta", {})
            if isinstance(edges_meta, dict):
                edge_options = []
                for edge_name in edge_columns:
                    meta = edges_meta.get(str(edge_name), {})
                    if not isinstance(meta, dict):
                        continue
                    review = meta.get("review", {})
                    if not isinstance(review, dict):
                        continue
                    if str(review.get("status", "")) == "approved":
                        edge_options.append(str(edge_name))
                if not edge_options:
                    edge_options = list(edge_columns)
    except Exception:
        edge_options = list(edge_columns)
    return edge_options


def default_svg_animation_edges(edge_options: list[str], *, limit: int = 6) -> list[str]:
    defaults = [
        edge_name
        for edge_name in edge_options
        if ("Ресивер3" in edge_name or "выхлоп" in edge_name or "предохран" in edge_name)
    ][:limit]
    if defaults:
        return defaults
    return list(edge_options[: min(limit, len(edge_options))])


def render_svg_animation_section(
    st_module: Any,
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
) -> dict[str, Any]:
    approved_only = st_module.checkbox(
        "Только APPROVED (review.status=approved)",
        value=False,
        key="svg_only_approved_edges",
    )
    edge_options = filter_svg_animation_edges_by_review(
        edge_columns,
        mapping,
        approved_only=bool(approved_only),
    )

    selected_edges = st_module.multiselect(
        "Ветки для анимации на схеме",
        options=edge_options,
        default=default_svg_animation_edges(edge_options),
        key="anim_edges_svg",
    )

    auto_match = st_module.checkbox(
        "Автосопоставление имён (fuzzy) — если mapping делался под другую версию модели",
        value=True,
        key="svg_auto_match_names",
    )
    min_score = st_module.slider(
        "Порог совпадения имён",
        min_value=0.50,
        max_value=0.95,
        value=0.70,
        step=0.01,
        key="svg_auto_match_threshold",
    )

    if len(selected_edges) == 0:
        st_module.info("Выберите хотя бы одну ветку.")
        return {"status": "no_edges", "selected_edges": []}

    mapping_use, report = prepare_svg_mapping_selection(
        st_module,
        mapping,
        need_edges=list(selected_edges),
        need_nodes=selected_node_names,
        auto_match=bool(auto_match),
        min_score=float(min_score),
        safe_dataframe_fn=safe_dataframe_fn,
    )

    scale, unit = flow_scale_and_unit_fn(
        p_atm=p_atm,
        model_module=model_module,
    )
    svg_series = prepare_svg_animation_series(
        df_mdot=df_mdot,
        selected_edges=list(selected_edges),
        scale=float(scale),
        unit=str(unit),
        mapping=mapping_use,
        df_open=df_open,
        df_p=df_p,
        selected_nodes=selected_node_names,
        p_atm=p_atm,
        pressure_divisor=pressure_divisor,
        pressure_unit=pressure_unit,
    )
    if svg_series["missing_edges"]:
        st_module.warning(
            "Для некоторых веток нет геометрии в mapping.edges: "
            + ", ".join(svg_series["missing_edges"][:20])
        )
    if svg_series["missing_nodes"]:
        st_module.warning(
            "Для некоторых узлов нет координат в mapping.nodes: "
            + ", ".join(svg_series["missing_nodes"][:20])
        )

    render_svg_review_controls(
        st_module,
        session_state,
        mapping_text=session_state.get("svg_mapping_text", ""),
    )
    render_svg_animation_panel(
        st_module,
        session_state,
        svg_inline=svg_inline,
        mapping=mapping_use,
        time_s=svg_series["time_s"],
        edge_series=svg_series["edge_series"],
        node_series=svg_series["node_series"],
        dataset_id=dataset_id,
        get_component_fn=get_component_fn,
        render_svg_flow_animation_html_fn=render_svg_flow_animation_html_fn,
    )
    return {
        "status": "ok",
        "selected_edges": list(selected_edges),
        "mapping": mapping_use,
        "report": report,
        "series": svg_series,
        "scale": scale,
        "unit": unit,
    }
