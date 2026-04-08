from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager

import numpy as np
import pandas as pd


TIME_COL = "время_с"
DEFAULT_CORNERS = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
DEFAULT_NODE_FALLBACKS = ["Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор"]
ANGLE_COLUMNS = (
    ("крен_phi_рад", "крен φ"),
    ("тангаж_theta_рад", "тангаж θ"),
)
MAIN_PRESSURE_COLUMNS = (
    ("давление_ресивер1_Па", "P ресивер1"),
    ("давление_ресивер2_Па", "P ресивер2"),
    ("давление_ресивер3_Па", "P ресивер3"),
    ("давление_аккумулятор_Па", "P аккумулятор"),
)
LABEL_KEY = "показатель"
VALUE_KEY = "значение"
UNIT_KEY = "ед"


def nearest_time_index(
    df: pd.DataFrame | None,
    target_time_s: float | None,
    *,
    time_col: str = TIME_COL,
) -> int:
    if df is None or time_col not in df.columns or len(df) == 0:
        return 0
    try:
        arr = df[time_col].to_numpy(dtype=float)
        idx = int(np.argmin(np.abs(arr - float(target_time_s))))
    except Exception:
        idx = 0
    return max(0, min(idx, len(df) - 1))


def resolve_selected_corners(
    session_state: Mapping[str, object],
    *,
    key: str = "mech_plot_corners",
) -> list[str]:
    corners = session_state.get(key)
    if not isinstance(corners, list) or not corners:
        return list(DEFAULT_CORNERS)
    return list(corners)


def resolve_selected_nodes(
    df_p: pd.DataFrame | None,
    session_state: Mapping[str, object],
    *,
    node_pressure_key: str = "node_pressure_plot",
    anim_nodes_key: str = "anim_nodes_svg",
) -> list[str]:
    nodes = session_state.get(node_pressure_key)
    if not isinstance(nodes, list) or not nodes:
        nodes = session_state.get(anim_nodes_key)
    if not isinstance(nodes, list):
        nodes = []
    if nodes:
        return list(nodes)
    if df_p is None:
        return []
    return [name for name in DEFAULT_NODE_FALLBACKS if name in df_p.columns]


def resolve_selected_edges(
    df_mdot: pd.DataFrame | None,
    session_state: Mapping[str, object],
    *,
    flow_edges_key: str = "flow_graph_edges",
    anim_edges_key: str = "anim_edges_svg",
    time_col: str = TIME_COL,
    default_limit: int = 4,
) -> list[str]:
    edges = session_state.get(flow_edges_key)
    if not isinstance(edges, list) or not edges:
        edges = session_state.get(anim_edges_key)
    if not isinstance(edges, list):
        edges = []
    if edges:
        return list(edges)
    if df_mdot is None:
        return []
    return [col for col in df_mdot.columns if col != time_col][:default_limit]


def build_playhead_value_rows(
    *,
    df_main: pd.DataFrame | None,
    df_p: pd.DataFrame | None,
    df_mdot: pd.DataFrame | None,
    playhead_x: float | None,
    session_state: Mapping[str, object],
    pressure_from_pa_fn: Callable[[object], float],
    pressure_unit: str,
    stroke_scale: float,
    stroke_unit: str,
    flow_scale_and_unit_fn: Callable[..., tuple[float, str]],
    p_atm: float,
    model_module,
    time_col: str = TIME_COL,
    max_nodes: int = 8,
    max_edges: int = 8,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    if playhead_x is None:
        return rows

    if df_main is not None and time_col in df_main.columns and len(df_main) > 0:
        idx0 = nearest_time_index(df_main, playhead_x, time_col=time_col)

        for col, label in ANGLE_COLUMNS:
            if col in df_main.columns:
                rows.append(
                    {
                        LABEL_KEY: label,
                        VALUE_KEY: float(df_main[col].iloc[idx0] * 180.0 / math.pi),
                        UNIT_KEY: "град",
                    }
                )

        for col, label in MAIN_PRESSURE_COLUMNS:
            if col in df_main.columns:
                rows.append(
                    {
                        LABEL_KEY: label,
                        VALUE_KEY: float(pressure_from_pa_fn(df_main[col].iloc[idx0])),
                        UNIT_KEY: pressure_unit,
                    }
                )

        for corner in resolve_selected_corners(session_state):
            col = f"положение_штока_{corner}_м"
            if col in df_main.columns:
                rows.append(
                    {
                        LABEL_KEY: f"шток {corner}",
                        VALUE_KEY: float(df_main[col].iloc[idx0]) * float(stroke_scale),
                        UNIT_KEY: stroke_unit,
                    }
                )

    if df_p is not None and time_col in df_p.columns and len(df_p) > 0:
        nodes = resolve_selected_nodes(df_p, session_state)
        if nodes:
            idxp = nearest_time_index(df_p, playhead_x, time_col=time_col)
            for node in nodes[:max_nodes]:
                if node in df_p.columns:
                    rows.append(
                        {
                            LABEL_KEY: f"P узел {node}",
                            VALUE_KEY: float(pressure_from_pa_fn(df_p[node].iloc[idxp])),
                            UNIT_KEY: pressure_unit,
                        }
                    )

    if df_mdot is not None and time_col in df_mdot.columns and len(df_mdot) > 0:
        edges = resolve_selected_edges(df_mdot, session_state, time_col=time_col)
        if edges:
            flow_scale, flow_unit = flow_scale_and_unit_fn(
                p_atm=p_atm,
                model_module=model_module,
            )
            idxm = nearest_time_index(df_mdot, playhead_x, time_col=time_col)
            for edge in edges[:max_edges]:
                if edge in df_mdot.columns:
                    rows.append(
                        {
                            LABEL_KEY: f"Q {edge}",
                            VALUE_KEY: float(df_mdot[edge].iloc[idxm]) * float(flow_scale),
                            UNIT_KEY: flow_unit,
                        }
                    )

    return rows


def render_playhead_value_content(
    *,
    df_main: pd.DataFrame | None,
    df_p: pd.DataFrame | None,
    df_mdot: pd.DataFrame | None,
    playhead_x: float | None,
    session_state: Mapping[str, object],
    pressure_from_pa_fn: Callable[[object], float],
    pressure_unit: str,
    stroke_scale: float,
    stroke_unit: str,
    flow_scale_and_unit_fn: Callable[..., tuple[float, str]],
    p_atm: float,
    model_module,
    safe_dataframe_fn: Callable[..., object],
    caption_fn: Callable[[str], object],
    info_fn: Callable[[str], object],
) -> None:
    caption_fn(f"t = {float(playhead_x):.3f} s")
    rows = build_playhead_value_rows(
        df_main=df_main,
        df_p=df_p,
        df_mdot=df_mdot,
        playhead_x=playhead_x,
        session_state=session_state,
        pressure_from_pa_fn=pressure_from_pa_fn,
        pressure_unit=pressure_unit,
        stroke_scale=stroke_scale,
        stroke_unit=stroke_unit,
        flow_scale_and_unit_fn=flow_scale_and_unit_fn,
        p_atm=p_atm,
        model_module=model_module,
    )

    if rows:
        df_values = pd.DataFrame(rows)
        safe_dataframe_fn(
            df_values,
            height=min(360, 34 * (len(df_values) + 1) + 40),
        )
        return

    info_fn("Нет данных для отображения на playhead.")


def render_playhead_value_panel(
    *,
    enabled: bool,
    df_main: pd.DataFrame | None,
    df_p: pd.DataFrame | None,
    df_mdot: pd.DataFrame | None,
    playhead_x: float | None,
    session_state: Mapping[str, object],
    pressure_from_pa_fn: Callable[[object], float],
    pressure_unit: str,
    stroke_scale: float,
    stroke_unit: str,
    flow_scale_and_unit_fn: Callable[..., tuple[float, str]],
    p_atm: float,
    model_module,
    safe_dataframe_fn: Callable[..., object],
    caption_fn: Callable[[str], object],
    info_fn: Callable[[str], object],
    expander_fn: Callable[..., AbstractContextManager[object]],
    title: str = "Текущие значения (playhead)",
    expanded: bool = False,
) -> None:
    if not enabled or playhead_x is None:
        return

    with expander_fn(title, expanded=expanded):
        render_playhead_value_content(
            df_main=df_main,
            df_p=df_p,
            df_mdot=df_mdot,
            playhead_x=playhead_x,
            session_state=session_state,
            pressure_from_pa_fn=pressure_from_pa_fn,
            pressure_unit=pressure_unit,
            stroke_scale=stroke_scale,
            stroke_unit=stroke_unit,
            flow_scale_and_unit_fn=flow_scale_and_unit_fn,
            p_atm=p_atm,
            model_module=model_module,
            safe_dataframe_fn=safe_dataframe_fn,
            caption_fn=caption_fn,
            info_fn=info_fn,
        )


def render_playhead_display_settings(
    *,
    columns_fn: Callable[[int], Sequence[AbstractContextManager[object]]],
    checkbox_fn: Callable[..., bool],
    markers_key: str = "playhead_show_markers",
    values_key: str = "playhead_show_values",
    markers_label: str = "Маркеры на графиках (playhead)",
    values_label: str = "Таблица значений (playhead)",
) -> tuple[bool, bool]:
    columns = columns_fn(2)
    with columns[0]:
        show_markers = bool(
            checkbox_fn(
                markers_label,
                value=True,
                key=markers_key,
            )
        )
    with columns[1]:
        show_values = bool(
            checkbox_fn(
                values_label,
                value=True,
                key=values_key,
            )
        )
    return show_markers, show_values
