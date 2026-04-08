from __future__ import annotations


def default_flow_animation_edges(edge_columns: list[str], *, limit: int = 8) -> list[str]:
    defaults = [
        column
        for column in edge_columns
        if ("Ресивер3" in column or "выхлоп" in column or "предохран" in column)
    ][:limit]
    if defaults:
        return defaults
    return list(edge_columns[: min(limit, len(edge_columns))])


def build_flow_animation_edge_series(
    df_mdot,
    *,
    selected_edges: list[str],
    scale: float,
    unit: str,
    df_open=None,
    time_column: str = "время_с",
) -> tuple[list[float], list[dict[str, object]]]:
    time_s = df_mdot[time_column].astype(float).tolist()
    edge_series: list[dict[str, object]] = []
    for edge_name in selected_edges:
        q = (df_mdot[edge_name].astype(float).to_numpy() * scale).tolist()
        if df_open is not None and edge_name in df_open.columns:
            op = df_open[edge_name].astype(int).tolist()
        else:
            op = None
        edge_series.append({"name": edge_name, "q": q, "open": op, "unit": unit})
    return time_s, edge_series


def render_flow_animation_panel(
    st_module,
    *,
    df_mdot,
    df_open,
    p_atm,
    model_module,
    flow_scale_and_unit_fn,
    render_flow_panel_html_fn,
) -> dict[str, object]:
    if df_mdot is None:
        st_module.info("Анимация потоков доступна только при record_full=True (df_mdot).")
        return {"status": "no_data", "selected_edges": []}

    st_module.caption("MVP: каждая выбранная ветка рисуется отдельной линией, по ней бегает маркер.")
    edge_columns = [column for column in df_mdot.columns if column != "время_с"]
    selected_edges = st_module.multiselect(
        "Ветки для анимации",
        options=edge_columns,
        default=default_flow_animation_edges(edge_columns),
        key="anim_edges",
    )
    if not selected_edges:
        st_module.info("Выберите хотя бы одну ветку.")
        return {"status": "no_selection", "selected_edges": []}

    scale, unit = flow_scale_and_unit_fn(
        p_atm=p_atm,
        model_module=model_module,
    )
    time_s, edge_series = build_flow_animation_edge_series(
        df_mdot,
        selected_edges=list(selected_edges),
        scale=float(scale),
        unit=str(unit),
        df_open=df_open,
    )
    render_flow_panel_html_fn(
        time_s=time_s,
        edge_series=edge_series,
        height=560,
    )
    return {
        "status": "ok",
        "edge_columns": edge_columns,
        "selected_edges": list(selected_edges),
        "unit": unit,
        "scale": scale,
    }
