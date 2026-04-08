from __future__ import annotations

import re

import numpy as np
import pandas as pd


def build_graph_studio_sources(
    *,
    df_main,
    df_p,
    df_mdot,
    df_open,
) -> dict[str, object]:
    return {
        "df_main": df_main,
        "df_p (давления узлов)": df_p,
        "df_mdot (потоки)": df_mdot,
        "df_open (состояния клапанов)": df_open,
    }


def filter_graph_studio_sources(sources: dict[str, object]) -> dict[str, object]:
    return {
        name: frame
        for name, frame in sources.items()
        if frame is not None and hasattr(frame, "columns") and len(frame)
    }


def resolve_graph_studio_time_column(df_src, *, preferred: str = "время_с") -> str | None:
    if df_src is None:
        return None
    if preferred in df_src.columns:
        return preferred
    if len(df_src.columns):
        return str(df_src.columns[0])
    return None


def list_graph_studio_signal_columns(
    df_src,
    *,
    time_column: str | None,
    drop_all_nan: bool = False,
) -> list[str]:
    if df_src is None or time_column is None or time_column not in df_src.columns:
        return []

    columns = [column for column in df_src.columns if column != time_column]
    if not drop_all_nan:
        return columns

    try:
        return [column for column in columns if df_src[column].notna().any()]
    except Exception:
        return columns


def render_graph_studio_plot_controls(
    st_module,
    *,
    cache_key: str,
    auto_units_label: str,
) -> dict[str, object]:
    col1, col2, col3, col4 = st_module.columns([1.0, 0.9, 0.8, 0.8], gap="medium")
    with col1:
        mode = st_module.radio(
            "\u0420\u0435\u0436\u0438\u043c",
            options=["stack", "overlay"],
            index=0,
            format_func=lambda value: "\u041e\u0441\u0446\u0438\u043b\u043b\u043e\u0433\u0440\u0430\u0444 (stack)" if value == "stack" else "Overlay (\u043e\u0434\u043d\u0430 \u043e\u0441\u044c)",
            key=f"gs_mode_{cache_key}",
        )
    with col2:
        max_points = st_module.number_input(
            "\u041c\u0430\u043a\u0441 \u0442\u043e\u0447\u0435\u043a",
            min_value=400,
            max_value=20000,
            value=2200,
            step=200,
            key=f"gs_maxp_{cache_key}",
        )
    with col3:
        decimation = st_module.selectbox(
            "Decimation",
            options=["minmax", "stride"],
            index=0,
            key=f"gs_dec_{cache_key}",
        )
    with col4:
        render = st_module.selectbox(
            "Renderer",
            options=["svg", "webgl"],
            index=0,
            key=f"gs_render_{cache_key}",
        )

    col5, col6, col7 = st_module.columns([1.0, 1.0, 1.0], gap="medium")
    with col5:
        auto_units = st_module.checkbox(
            auto_units_label,
            value=True,
            key=f"gs_auto_units_{cache_key}",
        )
    with col6:
        hover_unified = st_module.checkbox(
            "Hover: x unified (\u043f\u043e \u0432\u0441\u0435\u043c \u043f\u043e\u0434\u0433\u0440\u0430\u0444\u0438\u043a\u0430\u043c)",
            value=True,
            key=f"gs_hover_{cache_key}",
        )
    with col7:
        show_events = st_module.checkbox(
            "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u0441\u043e\u0431\u044b\u0442\u0438\u044f (timeline)",
            value=True,
            key=f"gs_events_{cache_key}",
        )

    return {
        "mode": mode,
        "max_points": int(max_points),
        "decimation": decimation,
        "render": render,
        "auto_units": bool(auto_units),
        "hover_unified": bool(hover_unified),
        "show_events": bool(show_events),
    }


def build_graph_studio_export_frame(
    df_src,
    *,
    time_column: str,
    selected_columns: list[str],
):
    export_columns = [time_column] + [
        column
        for column in selected_columns
        if column in df_src.columns and column != time_column
    ]
    return df_src[export_columns].copy()


def render_graph_studio_export_controls(
    st_module,
    *,
    df_src,
    time_column: str,
    selected_columns: list[str],
    cache_key: str,
    excel_bytes_fn,
) -> None:
    st_module.markdown("**\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0445 \u0441\u0438\u0433\u043d\u0430\u043b\u043e\u0432**")
    try:
        df_export = build_graph_studio_export_frame(
            df_src,
            time_column=time_column,
            selected_columns=selected_columns,
        )
        csv_bytes = df_export.to_csv(index=False).encode("utf-8")
        st_module.download_button(
            "\u0421\u043a\u0430\u0447\u0430\u0442\u044c CSV",
            data=csv_bytes,
            file_name="graph_studio_signals.csv",
            mime="text/csv",
            key=f"gs_csv_{cache_key}",
        )
        xlsx_bytes = excel_bytes_fn({"signals": df_export})
        st_module.download_button(
            "\u0421\u043a\u0430\u0447\u0430\u0442\u044c Excel",
            data=xlsx_bytes,
            file_name="graph_studio_signals.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"gs_xlsx_{cache_key}",
        )
    except Exception:
        st_module.info(
            "\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0434\u043b\u044f \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0433\u043e \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0430."
        )


def build_graph_studio_stats_frame(
    df_src,
    *,
    time_column: str,
    selected_columns: list[str],
    time_window: tuple[float, float],
    max_columns: int = 64,
):
    time_values = np.asarray(df_src[time_column].to_numpy(), dtype=float)
    mask = (time_values >= float(time_window[0])) & (time_values <= float(time_window[1]))
    rows = []
    for column in selected_columns[:max_columns]:
        if column not in df_src.columns:
            continue
        values = np.asarray(df_src[column].to_numpy(), dtype=float)
        values = values[mask]
        if values.size <= 0:
            continue
        rows.append(
            {
                "\u0441\u0438\u0433\u043d\u0430\u043b": column,
                "min": float(np.nanmin(values)),
                "max": float(np.nanmax(values)),
                "mean": float(np.nanmean(values)),
            }
        )
    return pd.DataFrame(rows)


def render_graph_studio_quick_stats(
    st_module,
    *,
    df_src,
    time_column: str,
    selected_columns: list[str],
    cache_key: str,
    safe_dataframe_fn,
) -> None:
    try:
        time_values = np.asarray(df_src[time_column].to_numpy(), dtype=float)
        time_min = float(np.min(time_values))
        time_max = float(np.max(time_values))
        time_window = st_module.slider(
            "\u041e\u043a\u043d\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u0438 \u0434\u043b\u044f \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0438 (min/max/mean)",
            min_value=float(time_min),
            max_value=float(time_max),
            value=(float(time_min), float(time_max)),
            step=float(max(1e-3, (time_max - time_min) / 200.0)),
            key=f"gs_tw_{cache_key}",
        )
        df_stats = build_graph_studio_stats_frame(
            df_src,
            time_column=time_column,
            selected_columns=selected_columns,
            time_window=time_window,
        )
        if len(df_stats):
            safe_dataframe_fn(
                df_stats,
                height=min(420, 34 * (len(df_stats) + 1) + 40),
            )
    except Exception:
        pass


def render_graph_studio_selected_signals_panel(
    st_module,
    *,
    df_src,
    source_name: str,
    time_column: str,
    available_columns: list[str],
    selection_key: str,
    cache_key: str,
    playhead_x,
    events_for_graphs,
    auto_units_label: str,
    plot_timeseries_fn,
    excel_bytes_fn,
    safe_dataframe_fn,
) -> list[str]:
    pick_cols = st_module.multiselect(
        "\u0421\u0438\u0433\u043d\u0430\u043b\u044b",
        options=available_columns,
        key=selection_key,
    )
    if not pick_cols:
        st_module.info("\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0445\u043e\u0442\u044f \u0431\u044b \u043e\u0434\u0438\u043d \u0441\u0438\u0433\u043d\u0430\u043b.")
        return []

    controls = render_graph_studio_plot_controls(
        st_module,
        cache_key=cache_key,
        auto_units_label=auto_units_label,
    )
    plot_timeseries_fn(
        df=df_src,
        tcol=time_column,
        y_cols=pick_cols[:32],
        title=f"Graph Studio: {source_name}",
        mode=controls["mode"],
        max_points=controls["max_points"],
        decimation=controls["decimation"],
        auto_units=controls["auto_units"],
        render=controls["render"],
        hover_unified=controls["hover_unified"],
        playhead_x=playhead_x,
        events=(events_for_graphs if (controls["show_events"] and events_for_graphs) else None),
        plot_key=f"plot_graph_studio_{cache_key}",
    )
    render_graph_studio_export_controls(
        st_module,
        df_src=df_src,
        time_column=time_column,
        selected_columns=pick_cols,
        cache_key=cache_key,
        excel_bytes_fn=excel_bytes_fn,
    )
    render_graph_studio_quick_stats(
        st_module,
        df_src=df_src,
        time_column=time_column,
        selected_columns=pick_cols,
        cache_key=cache_key,
        safe_dataframe_fn=safe_dataframe_fn,
    )
    return list(pick_cols)


def render_graph_studio_panel(
    st_module,
    *,
    df_main,
    df_p,
    df_mdot,
    df_open,
    cache_key: str,
    pressure_preset_label: str,
    auto_units_label: str,
    drop_all_nan: bool,
    session_state,
    playhead_x,
    events_for_graphs,
    plot_timeseries_fn,
    excel_bytes_fn,
    safe_dataframe_fn,
) -> dict[str, object]:
    available_sources = filter_graph_studio_sources(
        build_graph_studio_sources(
            df_main=df_main,
            df_p=df_p,
            df_mdot=df_mdot,
            df_open=df_open,
        )
    )
    if not available_sources:
        st_module.info(
            "\u041d\u0435\u0442 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f Graph Studio (\u043d\u0443\u0436\u043d\u043e record_full=True \u0438\u043b\u0438 df_main)."
        )
        return {"status": "no_sources", "available_sources": []}

    source_name = st_module.selectbox(
        "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0434\u0430\u043d\u043d\u044b\u0445",
        options=list(available_sources.keys()),
        index=0,
        key=f"gs_src_{cache_key}",
    )
    df_src = available_sources.get(source_name)
    time_column = resolve_graph_studio_time_column(df_src)
    if df_src is None or time_column is None or time_column not in df_src.columns:
        st_module.warning(
            "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u0442\u044c \u043a\u043e\u043b\u043e\u043d\u043a\u0443 \u0432\u0440\u0435\u043c\u0435\u043d\u0438."
        )
        return {
            "status": "missing_time_column",
            "source_name": source_name,
            "available_sources": list(available_sources.keys()),
        }

    all_columns = list_graph_studio_signal_columns(
        df_src,
        time_column=time_column,
        drop_all_nan=drop_all_nan,
    )
    query = st_module.text_input(
        "\u0424\u0438\u043b\u044c\u0442\u0440 \u0441\u0438\u0433\u043d\u0430\u043b\u043e\u0432 (\u043f\u043e\u0434\u0441\u0442\u0440\u043e\u043a\u0430 \u0438\u043b\u0438 regex)",
        value="",
        key=f"gs_filter_{cache_key}",
    )
    filtered_columns = filter_graph_studio_signal_columns(all_columns, query)
    preset = st_module.selectbox(
        "\u041f\u0440\u0435\u0441\u0435\u0442",
        options=graph_studio_preset_options(pressure_preset_label),
        index=0,
        key=f"gs_preset_{cache_key}",
    )
    selection_key = graph_studio_selection_key(cache_key, source_name)
    ensure_graph_studio_selection(
        session_state,
        selection_key=selection_key,
        available_columns=filtered_columns,
    )
    if st_module.button(
        "\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c \u043f\u0440\u0435\u0441\u0435\u0442",
        key=f"gs_apply_{cache_key}",
    ):
        picked_columns = graph_studio_preset_columns(
            all_columns,
            preset,
            current_selection=session_state.get(selection_key, []),
        )
        if picked_columns:
            session_state[selection_key] = sanitize_graph_studio_selection(
                picked_columns,
                filtered_columns,
            )

    selected_columns = render_graph_studio_selected_signals_panel(
        st_module,
        df_src=df_src,
        source_name=source_name,
        time_column=time_column,
        available_columns=filtered_columns,
        selection_key=selection_key,
        cache_key=cache_key,
        playhead_x=playhead_x,
        events_for_graphs=events_for_graphs,
        auto_units_label=auto_units_label,
        plot_timeseries_fn=plot_timeseries_fn,
        excel_bytes_fn=excel_bytes_fn,
        safe_dataframe_fn=safe_dataframe_fn,
    )
    return {
        "status": "ok",
        "available_sources": list(available_sources.keys()),
        "source_name": source_name,
        "time_column": time_column,
        "selection_key": selection_key,
        "selected_columns": selected_columns,
    }


def render_graph_studio_section(
    st_module,
    *,
    df_main,
    df_p,
    df_mdot,
    df_open,
    cache_key: str,
    pressure_preset_label: str,
    auto_units_label: str,
    drop_all_nan: bool,
    session_state,
    playhead_x,
    events_for_graphs,
    plot_timeseries_fn,
    excel_bytes_fn,
    safe_dataframe_fn,
) -> dict[str, object]:
    st_module.divider()
    st_module.subheader("\u041a\u043e\u043d\u0441\u0442\u0440\u0443\u043a\u0442\u043e\u0440 \u0433\u0440\u0430\u0444\u0438\u043a\u043e\u0432 (Graph Studio)")
    st_module.caption(
        "\u0412\u044b\u0431\u0438\u0440\u0430\u0439\u0442\u0435 \u043b\u044e\u0431\u044b\u0435 \u0441\u0438\u0433\u043d\u0430\u043b\u044b \u0438\u0437 df_main/df_p/df_mdot/df_open, \u0441\u0442\u0440\u043e\u0439\u0442\u0435 \u043e\u0441\u0446\u0438\u043b\u043b\u043e\u0433\u0440\u0430\u0444 (stack) \u0438\u043b\u0438 overlay, \u043a\u043b\u0438\u043a\u043e\u043c \u043f\u0440\u044b\u0433\u0430\u0439\u0442\u0435 \u043f\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u0438."
    )
    with st_module.expander(
        "Graph Studio: \u0441\u0438\u0433\u043d\u0430\u043b\u044b \u2192 \u0433\u0440\u0430\u0444\u0438\u043a \u2192 \u044d\u043a\u0441\u043f\u043e\u0440\u0442",
        expanded=True,
    ):
        return render_graph_studio_panel(
            st_module,
            df_main=df_main,
            df_p=df_p,
            df_mdot=df_mdot,
            df_open=df_open,
            cache_key=cache_key,
            pressure_preset_label=pressure_preset_label,
            auto_units_label=auto_units_label,
            drop_all_nan=drop_all_nan,
            session_state=session_state,
            playhead_x=playhead_x,
            events_for_graphs=events_for_graphs,
            plot_timeseries_fn=plot_timeseries_fn,
            excel_bytes_fn=excel_bytes_fn,
            safe_dataframe_fn=safe_dataframe_fn,
        )


def filter_graph_studio_signal_columns(columns: list[str], query: str) -> list[str]:
    if not query:
        return list(columns)
    try:
        regex = re.compile(query, flags=re.IGNORECASE)
        return [column for column in columns if regex.search(str(column))]
    except Exception:
        query_lower = query.lower()
        return [column for column in columns if query_lower in str(column).lower()]


def graph_studio_preset_options(pressure_preset_label: str) -> list[str]:
    return [
        "(нет)",
        "Механика: штоки (положение/скорость)",
        "Механика: колёса (z + дорога)",
        pressure_preset_label,
        "Крен/тангаж (рад → град)",
    ]


def graph_studio_selection_key(cache_key: str, source_name: str) -> str:
    return f"gs_cols_{cache_key}::{source_name}"


def sanitize_graph_studio_selection(selection: list, allowed_columns: list[str]) -> list[str]:
    return [column for column in selection if column in allowed_columns]


def ensure_graph_studio_selection(
    session_state,
    *,
    selection_key: str,
    available_columns: list[str],
    default_limit: int = 8,
) -> list[str]:
    if (selection_key not in session_state) or (not isinstance(session_state.get(selection_key), list)):
        session_state[selection_key] = available_columns[: min(default_limit, len(available_columns))]
    else:
        session_state[selection_key] = sanitize_graph_studio_selection(
            session_state.get(selection_key, []),
            available_columns,
        )
    return list(session_state.get(selection_key, []))


def graph_studio_preset_columns(
    all_columns: list[str],
    preset: str,
    *,
    current_selection: list[str] | None = None,
) -> list[str]:
    if preset.startswith("Механика: штоки"):
        return [column for column in all_columns if str(column).startswith("положение_штока_") or str(column).startswith("скорость_штока_")]
    if preset.startswith("Механика: колёса"):
        return [column for column in all_columns if ("перемещение_колеса_" in str(column)) or str(column).startswith("дорога_")]
    if preset.startswith("Давления"):
        return [column for column in all_columns if str(column).endswith("_Па") and ("давление" in str(column))]
    if preset.startswith("Крен/тангаж"):
        return [column for column in all_columns if str(column) in ("крен_phi_рад", "тангаж_theta_рад")]
    return list(current_selection or [])
