from __future__ import annotations

DEFAULT_NODE_PRIORITY = ["Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор"]
PLOTLY_NODE_HINT = "Клик по графику выбирает узел и подсвечивает его на SVG схеме (вкладка ‘Анимация’)."


def resolve_default_node_pressure_selection(
    node_columns: list[str],
    session_state,
    *,
    selected_key: str = "node_pressure_plot",
    anim_nodes_key: str = "anim_nodes_svg",
    max_default: int = 6,
) -> list[str]:
    selected = session_state.get(selected_key)
    if not selected:
        selected = session_state.get(anim_nodes_key)
    if not selected:
        selected = [name for name in DEFAULT_NODE_PRIORITY if name in node_columns]
    if not selected:
        selected = node_columns[: min(max_default, len(node_columns))]
    return list(selected)


def render_node_pressure_expander(
    *,
    df_p,
    plot_lines_fn,
    session_state,
    playhead_x,
    events,
    events_max: int,
    events_show_labels: bool,
    title: str,
    yaxis_title: str,
    transform_y_fn,
    has_plotly: bool,
    expander_fn,
    multiselect_fn,
    info_fn,
    caption_fn,
) -> None:
    if df_p is None:
        return

    with expander_fn("Давление узлов (df_p)", expanded=False):
        node_columns = [column for column in df_p.columns if column != "время_с"]
        if not node_columns:
            info_fn("В df_p нет колонок узлов давления.")
            return

        default_nodes = resolve_default_node_pressure_selection(
            node_columns,
            session_state,
        )
        picked_nodes = multiselect_fn(
            "Узлы (df_p)",
            options=node_columns,
            default=default_nodes,
            key="node_pressure_plot",
        )
        plot_lines_fn(
            df_p,
            "время_с",
            picked_nodes,
            title=title,
            yaxis_title=yaxis_title,
            transform_y=transform_y_fn,
            height=320,
            plot_key="plot_node_pressure",
            enable_select=True,
            playhead_x=playhead_x,
            events=events,
            events_max=events_max,
            events_show_labels=events_show_labels,
        )
        if has_plotly:
            caption_fn(PLOTLY_NODE_HINT)
