from __future__ import annotations

from functools import partial
from typing import Any, Callable

from pneumo_solver_ui.ui_line_plot_helpers import plot_lines
from pneumo_solver_ui.ui_plot_studio_helpers import plot_studio_timeseries


def build_plot_studio_renderer(
    *,
    has_plotly: bool,
    go_module: Any,
    make_subplots_fn: Callable[..., Any] | None,
    safe_plotly_chart_fn: Callable[..., Any],
    infer_unit_and_transform_fn: Callable[..., Any],
    extract_plotly_selection_points_fn: Callable[..., Any],
    plotly_points_signature_fn: Callable[..., Any],
    decimate_minmax_fn: Callable[..., Any],
    missing_plotly_message: str,
):
    return partial(
        plot_studio_timeseries,
        has_plotly=has_plotly,
        go_module=go_module,
        make_subplots_fn=make_subplots_fn,
        safe_plotly_chart_fn=safe_plotly_chart_fn,
        infer_unit_and_transform_fn=infer_unit_and_transform_fn,
        extract_plotly_selection_points_fn=extract_plotly_selection_points_fn,
        plotly_points_signature_fn=plotly_points_signature_fn,
        decimate_minmax_fn=decimate_minmax_fn,
        missing_plotly_message=missing_plotly_message,
    )


def build_line_plot_renderer(
    *,
    has_plotly: bool,
    go_module: Any,
    safe_plotly_chart_fn: Callable[..., Any],
    is_any_fallback_anim_playing_fn: Callable[..., Any],
    shorten_name_fn: Callable[..., Any],
    preprocess_df_and_y_cols_fn: Callable[..., Any] | None = None,
):
    return partial(
        plot_lines,
        has_plotly=has_plotly,
        go_module=go_module,
        safe_plotly_chart_fn=safe_plotly_chart_fn,
        is_any_fallback_anim_playing_fn=is_any_fallback_anim_playing_fn,
        shorten_name_fn=shorten_name_fn,
        preprocess_df_and_y_cols_fn=preprocess_df_and_y_cols_fn,
    )
