from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Callable, MutableMapping

from pneumo_solver_ui.ui_event_sync_helpers import (
    consume_mech_pick_event,
    consume_playhead_event,
    consume_plotly_pick_events,
    consume_svg_pick_event,
)


SessionState = MutableMapping[str, Any]


def build_svg_pick_consumer(
    session_state: SessionState,
    *,
    apply_pick_list_fn: Callable[[Any, str, str], list[str]],
):
    return partial(
        consume_svg_pick_event,
        session_state,
        apply_pick_list_fn=apply_pick_list_fn,
    )


def build_mech_pick_consumer(session_state: SessionState):
    return partial(
        consume_mech_pick_event,
        session_state,
    )


def build_plotly_pick_consumer(
    session_state: SessionState,
    *,
    extract_plotly_selection_points_fn: Callable[..., Any],
    plotly_points_signature_fn: Callable[..., Any],
    apply_pick_list_fn: Callable[[Any, str, str], list[str]],
):
    return partial(
        consume_plotly_pick_events,
        session_state,
        extract_plotly_selection_points_fn=extract_plotly_selection_points_fn,
        plotly_points_signature_fn=plotly_points_signature_fn,
        apply_pick_list_fn=apply_pick_list_fn,
    )


def build_playhead_event_consumer(
    session_state: SessionState,
    *,
    persist_browser_perf_snapshot_event_fn: Callable[..., Any],
    workspace_exports_dir: Path,
    log_event_fn: Callable[..., Any],
    proc_metrics_fn: Callable[..., Any],
):
    return partial(
        consume_playhead_event,
        session_state,
        persist_browser_perf_snapshot_event_fn=persist_browser_perf_snapshot_event_fn,
        workspace_exports_dir=workspace_exports_dir,
        log_event_fn=log_event_fn,
        proc_metrics_fn=proc_metrics_fn,
    )
