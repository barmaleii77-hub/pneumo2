from __future__ import annotations

from typing import Any


def render_results_graph_section(
    st: Any,
    *,
    df_main,
    df_p,
    df_mdot,
    df_open,
    cache_key: str,
    session_state,
    playhead_x,
    events_for_graphs,
    events_graph_max: int,
    events_graph_labels: bool,
    plot_lines_fn: Any,
    plot_timeseries_fn: Any,
    excel_bytes_fn: Any,
    safe_dataframe_fn: Any,
    pressure_title: str,
    pressure_yaxis_title: str,
    pressure_transform_fn: Any,
    node_pressure_title: str,
    node_pressure_yaxis_title: str,
    node_pressure_transform_fn: Any,
    graph_studio_pressure_preset_label: str,
    graph_studio_auto_units_label: str,
    graph_studio_drop_all_nan: bool,
    has_plotly: bool,
    render_main_overview_graphs_fn: Any,
    render_mech_overview_graphs_fn: Any,
    render_node_pressure_expander_fn: Any,
    render_graph_studio_section_fn: Any,
    time_column: str = "время_с",
    section_title: str = "Графики по времени",
) -> None:
    st.subheader(section_title)

    render_main_overview_graphs_fn(
        plot_lines_fn=plot_lines_fn,
        df_main=df_main,
        tcol=time_column,
        playhead_x=playhead_x,
        events=events_for_graphs,
        events_max=events_graph_max,
        events_show_labels=events_graph_labels,
        pressure_title=pressure_title,
        pressure_yaxis_title=pressure_yaxis_title,
        pressure_transform_fn=pressure_transform_fn,
    )

    render_mech_overview_graphs_fn(
        plot_lines_fn=plot_lines_fn,
        df_main=df_main,
        tcol=time_column,
        playhead_x=playhead_x,
        events=events_for_graphs,
        events_max=events_graph_max,
        events_show_labels=events_graph_labels,
        session_state=session_state,
        markdown_fn=st.markdown,
        columns_fn=st.columns,
        multiselect_fn=st.multiselect,
        caption_fn=st.caption,
    )

    render_node_pressure_expander_fn(
        df_p=df_p,
        plot_lines_fn=plot_lines_fn,
        session_state=session_state,
        playhead_x=playhead_x,
        events=events_for_graphs,
        events_max=events_graph_max,
        events_show_labels=events_graph_labels,
        title=node_pressure_title,
        yaxis_title=node_pressure_yaxis_title,
        transform_y_fn=node_pressure_transform_fn,
        has_plotly=has_plotly,
        expander_fn=st.expander,
        multiselect_fn=st.multiselect,
        info_fn=st.info,
        caption_fn=st.caption,
    )

    with st.container():
        render_graph_studio_section_fn(
            st,
            df_main=df_main,
            df_p=df_p,
            df_mdot=df_mdot,
            df_open=df_open,
            cache_key=cache_key,
            pressure_preset_label=graph_studio_pressure_preset_label,
            auto_units_label=graph_studio_auto_units_label,
            drop_all_nan=bool(graph_studio_drop_all_nan),
            session_state=session_state,
            playhead_x=playhead_x,
            events_for_graphs=events_for_graphs,
            plot_timeseries_fn=plot_timeseries_fn,
            excel_bytes_fn=excel_bytes_fn,
            safe_dataframe_fn=safe_dataframe_fn,
        )
