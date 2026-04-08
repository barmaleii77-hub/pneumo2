from __future__ import annotations


def flow_edge_columns(df_mdot, *, time_column: str = "время_с") -> list[str]:
    if df_mdot is None:
        return []
    return [column for column in df_mdot.columns if column != time_column]


def default_flow_edge_selection(edge_columns: list[str], *, limit: int = 6) -> list[str]:
    return list(edge_columns[: min(limit, len(edge_columns))])


def render_flow_edge_graphs_section(
    st_module,
    *,
    df_mdot,
    df_open,
    playhead_x,
    events_for_graphs,
    events_graph_max,
    events_graph_labels,
    p_atm,
    model_module,
    plot_lines_fn,
    flow_scale_and_unit_fn,
    has_plotly: bool,
) -> dict[str, object]:
    st_module.subheader("Потоки по веткам")
    if df_mdot is None:
        st_module.info("Потоки доступны только при record_full=True.")
        return {"status": "no_data", "selected_edges": []}

    edge_columns = flow_edge_columns(df_mdot)
    selected_edges = st_module.multiselect(
        "Ветки/элементы",
        options=edge_columns,
        default=default_flow_edge_selection(edge_columns),
        key="flow_graph_edges",
    )

    scale, unit = flow_scale_and_unit_fn(
        p_atm=p_atm,
        model_module=model_module,
    )
    plot_lines_fn(
        df_mdot,
        "время_с",
        selected_edges,
        title=f"Расход по веткам ({unit})",
        yaxis_title=unit,
        transform_y=lambda values: values * scale,
        height=360,
        plot_key="plot_flow_edges",
        enable_select=True,
        playhead_x=playhead_x,
        events=events_for_graphs,
        events_max=events_graph_max,
        events_show_labels=events_graph_labels,
    )
    if has_plotly:
        st_module.caption(
            "Клик по графику выбирает ветку и подсвечивает её на SVG схеме (вкладка ‘Анимация’)."
        )

    if df_open is not None:
        open_columns = [column for column in selected_edges if column in df_open.columns]
        if open_columns:
            plot_lines_fn(
                df_open,
                "время_с",
                open_columns,
                title="Состояния элементов (open=1)",
                yaxis_title="0/1",
                transform_y=lambda values: values,
                height=220,
                playhead_x=playhead_x,
                events=events_for_graphs,
                events_max=events_graph_max,
                events_show_labels=events_graph_labels,
            )

    return {
        "status": "ok",
        "edge_columns": edge_columns,
        "selected_edges": list(selected_edges),
        "unit": unit,
        "scale": scale,
    }
