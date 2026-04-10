from __future__ import annotations

from typing import Any, Callable, List

import numpy as np
import pandas as pd
import streamlit as st

if not hasattr(st, "warning"):
    st.warning = lambda *args, **kwargs: None  # type: ignore[attr-defined]
if not hasattr(st, "info"):
    st.info = lambda *args, **kwargs: None  # type: ignore[attr-defined]


def plot_studio_timeseries(
    df: pd.DataFrame,
    tcol: str,
    y_cols: List[str],
    title: str = "Graph Studio",
    mode: str = "stack",
    max_points: int = 2000,
    decimation: str = "minmax",
    auto_units: bool = True,
    render: str = "svg",
    hover_unified: bool = True,
    playhead_x: float | None = None,
    events: List[dict] | None = None,
    plot_key: str = "plot_studio",
    *,
    has_plotly: bool,
    go_module: Any,
    make_subplots_fn: Callable[..., Any],
    safe_plotly_chart_fn: Callable[..., Any],
    infer_unit_and_transform_fn: Callable[[str], tuple[str, Callable[[Any], Any] | None, str]],
    extract_plotly_selection_points_fn: Callable[[Any], list[dict]],
    plotly_points_signature_fn: Callable[[Any], str],
    decimate_minmax_fn: Callable[[Any, Any], tuple[Any, Any]],
    missing_plotly_message: str,
) -> None:
    """Render Graph Studio time-series plot(s)."""
    if df is None or df.empty or not y_cols:
        st.info("Нет данных/сигналов для построения.")
        return
    if not has_plotly:
        st.warning(missing_plotly_message)
        return

    if tcol not in df.columns:
        st.warning(f"Нет колонки времени '{tcol}'")
        return
    x = df[tcol].to_numpy()

    xph = None
    if playhead_x is not None:
        try:
            xph = float(playhead_x)
        except Exception:
            xph = None

    if mode == "overlay":
        fig = go_module.Figure()

        yaxis_title = ""
        units = []
        transforms = {}
        if auto_units:
            for c in y_cols:
                u, tr, _ya = infer_unit_and_transform_fn(c)
                units.append(u)
                transforms[c] = tr
            units_u = [u for u in units if u]
            if units_u and all(u == units_u[0] for u in units_u):
                yaxis_title = units_u[0]

        idx_ph = None
        if xph is not None:
            try:
                idx_ph = int(np.argmin(np.abs(np.asarray(x, dtype=float) - float(xph))))
            except Exception:
                idx_ph = None

        trace_ctor = go_module.Scattergl if (render == "webgl") else go_module.Scatter

        for c in y_cols:
            if c not in df.columns:
                continue
            y_raw = df[c].to_numpy()
            tr = transforms.get(c) if auto_units else None
            y = y_raw
            if tr is not None:
                try:
                    y = tr(np.asarray(y_raw, dtype=float))
                except Exception:
                    y = y_raw

            xx = x
            yy = y
            if decimation == "minmax":
                xx, yy = decimate_minmax_fn(xx, np.asarray(yy, dtype=float), max_points=int(max_points))
            else:
                if len(xx) > int(max_points):
                    idx2 = np.linspace(0, len(xx) - 1, num=int(max_points), dtype=int)
                    xx = xx[idx2]
                    yy = np.asarray(yy, dtype=float)[idx2]

            fig.add_trace(
                trace_ctor(
                    x=xx,
                    y=yy,
                    mode="lines",
                    name=c,
                    hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
                )
            )

            if idx_ph is not None and 0 <= idx_ph < len(x):
                try:
                    yph = float(y[idx_ph]) if idx_ph < len(y) else None
                    if yph is not None and np.isfinite(yph):
                        fig.add_trace(
                            go_module.Scatter(
                                x=[float(x[idx_ph])],
                                y=[yph],
                                mode="markers",
                                marker=dict(size=8, color="rgba(0,0,0,0.55)"),
                                showlegend=False,
                                hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
                            )
                        )
                except Exception:
                    pass

        if hover_unified:
            fig.update_layout(hovermode="x unified")
        else:
            fig.update_layout(hovermode="closest")

        if events:
            try:
                for ev in events[:200]:
                    t_ev = float(ev.get("t", 0.0))
                    sev = str(ev.get("severity", "info")).lower()
                    col = "rgba(0,0,0,0.10)"
                    if sev == "warn":
                        col = "rgba(255,165,0,0.22)"
                    if sev == "error":
                        col = "rgba(255,0,0,0.30)"
                    fig.add_shape(
                        type="line",
                        x0=t_ev,
                        x1=t_ev,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line=dict(width=1, dash="dot", color=col),
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
                    line=dict(width=2, color="rgba(0,0,0,0.45)"),
                )
            except Exception:
                pass

        fig.update_layout(
            title=title,
            height=460,
            margin=dict(l=50, r=20, t=50, b=40),
            yaxis_title=yaxis_title,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )

        st.session_state[plot_key + "__trace_names"] = list(y_cols)
        state = safe_plotly_chart_fn(fig, key=plot_key, on_select="rerun", selection_mode=("points",))

        pts = extract_plotly_selection_points_fn(state)
        if pts:
            sig = plotly_points_signature_fn(pts)
            last_sig = st.session_state.get(plot_key + "__last_sig")
            if sig != last_sig:
                st.session_state[plot_key + "__last_sig"] = sig
                try:
                    x0 = pts[0].get("x")
                    if x0 is not None:
                        st.session_state["playhead_request_x"] = float(x0)
                except Exception:
                    pass

        return

    rows = len(y_cols)
    height = max(260, min(1200, 140 * rows + 80))
    fig = make_subplots_fn(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, subplot_titles=y_cols)

    for i, c in enumerate(y_cols):
        if c not in df.columns:
            continue
        y_raw = df[c].to_numpy()
        unit = ""
        tr = None
        if auto_units:
            unit, tr, _ya = infer_unit_and_transform_fn(c)
        y = y_raw
        if tr is not None:
            try:
                y = tr(np.asarray(y_raw, dtype=float))
            except Exception:
                y = y_raw

        xx = x
        yy = y
        if decimation == "minmax":
            xx, yy = decimate_minmax_fn(xx, np.asarray(yy, dtype=float), max_points=int(max_points))
        else:
            if len(xx) > int(max_points):
                idx2 = np.linspace(0, len(xx) - 1, num=int(max_points), dtype=int)
                xx = xx[idx2]
                yy = np.asarray(yy, dtype=float)[idx2]

        trace_ctor = go_module.Scattergl if (render == "webgl") else go_module.Scatter
        fig.add_trace(
            trace_ctor(
                x=xx,
                y=yy,
                mode="lines",
                name=c,
                showlegend=False,
                hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
            ),
            row=i + 1,
            col=1,
        )
        if unit:
            fig.update_yaxes(title_text=unit, row=i + 1, col=1)

    if hover_unified:
        fig.update_layout(hovermode="x unified", hoversubplots="axis")
    else:
        fig.update_layout(hovermode="closest")

    if events:
        try:
            for ev in events[:200]:
                t_ev = float(ev.get("t", 0.0))
                sev = str(ev.get("severity", "info")).lower()
                col = "rgba(0,0,0,0.10)"
                if sev == "warn":
                    col = "rgba(255,165,0,0.22)"
                if sev == "error":
                    col = "rgba(255,0,0,0.30)"
                fig.add_shape(
                    type="line",
                    x0=t_ev,
                    x1=t_ev,
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    line=dict(width=1, dash="dot", color=col),
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
                line=dict(width=2, color="rgba(0,0,0,0.45)"),
            )
        except Exception:
            pass

    fig.update_layout(title=title, height=height, margin=dict(l=40, r=20, t=50, b=35))
    st.session_state[plot_key + "__trace_names"] = list(y_cols)
    state = safe_plotly_chart_fn(fig, key=plot_key, on_select="rerun", selection_mode=("points",))

    pts = extract_plotly_selection_points_fn(state)
    if pts:
        sig = plotly_points_signature_fn(pts)
        last_sig = st.session_state.get(plot_key + "__last_sig")
        if sig != last_sig:
            st.session_state[plot_key + "__last_sig"] = sig
            try:
                x0 = pts[0].get("x")
                if x0 is not None:
                    st.session_state["playhead_request_x"] = float(x0)
            except Exception:
                pass


__all__ = ["plot_studio_timeseries"]
