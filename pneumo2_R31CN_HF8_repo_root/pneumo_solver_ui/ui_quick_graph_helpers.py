from __future__ import annotations

import math


ANGLE_COLUMNS = ["крен_phi_рад", "тангаж_theta_рад"]
MAIN_PRESSURE_COLUMNS = [
    "давление_ресивер1_Па",
    "давление_ресивер2_Па",
    "давление_ресивер3_Па",
    "давление_аккумулятор_Па",
]


def present_main_pressure_columns(df_main) -> list[str]:
    if df_main is None:
        return []
    return [column for column in MAIN_PRESSURE_COLUMNS if column in df_main.columns]


def render_main_overview_graphs(
    *,
    plot_lines_fn,
    df_main,
    tcol: str,
    playhead_x,
    events,
    events_max: int,
    events_show_labels: bool,
    pressure_title: str,
    pressure_yaxis_title: str,
    pressure_transform_fn,
) -> None:
    if df_main is None:
        return

    plot_lines_fn(
        df_main,
        tcol,
        ANGLE_COLUMNS,
        title="Крен/тангаж",
        yaxis_title="град",
        transform_y=lambda values: values * 180.0 / math.pi,
        playhead_x=playhead_x,
        events=events,
        events_max=events_max,
        events_show_labels=events_show_labels,
    )

    pressure_columns = present_main_pressure_columns(df_main)
    if not pressure_columns:
        return

    plot_lines_fn(
        df_main,
        tcol,
        pressure_columns,
        title=pressure_title,
        yaxis_title=pressure_yaxis_title,
        transform_y=pressure_transform_fn,
        playhead_x=playhead_x,
        events=events,
        events_max=events_max,
        events_show_labels=events_show_labels,
    )
