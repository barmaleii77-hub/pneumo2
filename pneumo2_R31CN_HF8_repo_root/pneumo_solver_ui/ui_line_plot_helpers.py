from __future__ import annotations

import math
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st


def prefer_rel0_plot_columns(
    df: pd.DataFrame,
    y_cols: List[str],
) -> tuple[pd.DataFrame, List[str]]:
    rel_map = {}
    for col in list(y_cols):
        if str(col).endswith("_rel0"):
            continue
        rel0_candidates = [f"{col}_rel0"]
        # Backward compatibility: some older datasets used *_rel0_m / *_rel0_rad.
        if str(col).endswith("_m"):
            rel0_candidates.append(str(col)[:-2] + "_rel0_m")
        if str(col).endswith("_rad"):
            rel0_candidates.append(str(col)[:-4] + "_rel0_rad")
        for rel0_col in rel0_candidates:
            if rel0_col in df.columns:
                rel_map[rel0_col] = col
                break
    if not rel_map:
        return df, list(y_cols)
    out = df.copy()
    for src, dst in rel_map.items():
        out[dst] = out[src]
    return out, list(y_cols)


def plot_lines(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    title: str,
    yaxis_title: str = "",
    transform_y=None,
    height: int = 320,
    plot_key: str | None = None,
    enable_select: bool = False,
    playhead_x: float | None = None,
    events: List[dict] | None = None,
    events_max: int = 120,
    events_show_labels: bool = False,
    events_label_severities: Tuple[str, ...] = ("error",),
    *,
    has_plotly: bool,
    go_module,
    safe_plotly_chart_fn: Callable,
    is_any_fallback_anim_playing_fn: Callable[[], bool],
    shorten_name_fn: Callable[[str, int], str],
    preprocess_df_and_y_cols_fn: Callable[[pd.DataFrame, List[str]], tuple[pd.DataFrame, List[str]]] | None = None,
):
    if df is None or len(df) == 0:
        st.info("Нет данных для графика.")
        return None

    if preprocess_df_and_y_cols_fn is not None:
        try:
            df, y_cols = preprocess_df_and_y_cols_fn(df, list(y_cols))
        except Exception:
            y_cols = list(y_cols)
    y_cols = [col for col in y_cols if col in df.columns]
    if len(y_cols) == 0:
        st.info("Не выбрано ни одной колонки для графика.")
        return None

    # Avoid expensive Plotly rebuilds while the fallback animation is playing.
    try:
        if st.session_state.get("skip_heavy_on_play", True) and is_any_fallback_anim_playing_fn():
            if not st.session_state.get("_skip_plotly_notice_shown", False):
                st.info(
                    "Play (fallback) активен -> Plotly-графики временно скрыты, чтобы анимация не тормозила. "
                    "Поставь на паузу, чтобы вернуть графики."
                )
                st.session_state["_skip_plotly_notice_shown"] = True
            return None
    except Exception:
        pass

    if transform_y is None:
        def transform_y(a):
            return a

    idx_ph = None
    xph = None
    x_arr = None
    try:
        x_arr = df[x_col].to_numpy(dtype=float)
        if playhead_x is not None and len(x_arr) > 0:
            idx_ph = int(np.argmin(np.abs(x_arr - float(playhead_x))))
            idx_ph = max(0, min(idx_ph, len(x_arr) - 1))
            xph = float(x_arr[idx_ph])
    except Exception:
        idx_ph = None
        xph = None

    show_markers = bool(st.session_state.get("playhead_show_markers", True))
    play_values: Dict[str, float] = {}

    if has_plotly:
        fig = go_module.Figure()
        x = x_arr if x_arr is not None else df[x_col].to_numpy()

        if events:
            try:
                evs = list(events)
                if events_max and len(evs) > int(events_max):
                    step = int(math.ceil(len(evs) / float(events_max)))
                    if step > 1:
                        evs = evs[::step]

                label_sev = set(str(sev).lower() for sev in (events_label_severities or ()))
                sev_color = {
                    "info": "rgba(0,0,0,0.10)",
                    "warn": "rgba(255,165,0,0.25)",
                    "error": "rgba(255,0,0,0.30)",
                }
                for ev in evs:
                    t_ev = float(ev.get("t", 0.0))
                    sev = str(ev.get("severity", "info")).lower()
                    color = sev_color.get(sev, "rgba(0,0,0,0.10)")
                    fig.add_shape(
                        type="line",
                        x0=t_ev,
                        x1=t_ev,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line=dict(width=1, dash="dot", color=color),
                        layer="below",
                    )
                    if events_show_labels and sev in label_sev:
                        fig.add_annotation(
                            x=t_ev,
                            y=1,
                            yref="paper",
                            text=shorten_name_fn(str(ev.get("kind", "evt")), 12),
                            showarrow=False,
                            xanchor="left",
                            yanchor="top",
                            font=dict(size=9, color=color),
                            bgcolor="rgba(255,255,255,0.6)",
                        )
            except Exception:
                pass

        for col in y_cols:
            y = transform_y(df[col].to_numpy())
            if enable_select and plot_key:
                fig.add_trace(
                    go_module.Scatter(
                        x=x,
                        y=y,
                        mode="lines+markers",
                        marker=dict(size=10, opacity=0.0),
                        name=col,
                    )
                )
            else:
                fig.add_trace(go_module.Scatter(x=x, y=y, mode="lines", name=col))

            if idx_ph is not None and xph is not None:
                try:
                    yph = float(y[idx_ph])
                    play_values[col] = yph
                    if show_markers:
                        fig.add_trace(
                            go_module.Scatter(
                                x=[xph],
                                y=[yph],
                                mode="markers",
                                marker=dict(size=10, color="rgba(0,0,0,0.55)", symbol="circle"),
                                showlegend=False,
                                hovertemplate=f"{col}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
                            )
                        )
                except Exception:
                    pass

        if xph is not None:
            try:
                fig.add_shape(
                    type="line",
                    x0=float(xph),
                    x1=float(xph),
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    line=dict(width=1, dash="dot", color="rgba(0,0,0,0.35)"),
                )
            except Exception:
                pass

        fig.update_layout(
            title=title,
            height=int(height),
            margin=dict(l=10, r=10, t=40, b=10),
        )
        if yaxis_title:
            fig.update_yaxes(title=yaxis_title)
        fig.update_xaxes(title=x_col)

        if enable_select and plot_key:
            st.session_state[plot_key + "__trace_names"] = list(y_cols)
            safe_plotly_chart_fn(fig, key=plot_key, on_select="rerun", selection_mode=("points",))
        else:
            safe_plotly_chart_fn(fig)
    else:
        data = df[[x_col] + y_cols].copy()
        data = data.set_index(x_col)
        st.line_chart(data, height=height)

        if idx_ph is not None:
            for col in y_cols:
                try:
                    y = transform_y(df[col].to_numpy())
                    play_values[col] = float(y[idx_ph])
                except Exception:
                    pass

    if idx_ph is not None and xph is not None:
        return {"idx": int(idx_ph), "x": float(xph), "values": play_values}
    return None
