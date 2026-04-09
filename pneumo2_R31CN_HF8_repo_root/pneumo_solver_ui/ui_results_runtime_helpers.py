from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pneumo_solver_ui.ui_results_event_controls_helpers import render_results_event_controls
from pneumo_solver_ui.ui_results_event_runtime_helpers import compute_results_events
from pneumo_solver_ui.ui_results_playhead_jump_helpers import apply_results_playhead_request_x
from pneumo_solver_ui.ui_results_playhead_reset_helpers import reset_results_playhead_on_dataset_change
from pneumo_solver_ui.ui_results_timeline_helpers import prepare_results_timeline_prelude


def prepare_results_runtime(
    st: Any,
    *,
    session_state: Mapping[str, object],
    cache_key: str,
    get_ui_nonce_fn: Callable[[], str],
    time_s: Sequence[float] | None,
    make_playhead_reset_command_fn: Callable[[], dict[str, Any]],
    make_playhead_jump_command_fn: Callable[[int], dict[str, Any]],
    log_event_fn: Callable[..., Any],
    event_controls_kwargs: dict[str, Any],
    compute_results_events_kwargs: dict[str, Any],
) -> dict[str, Any]:
    dataset_id_ui = f"{cache_key}__{get_ui_nonce_fn()}"

    reset_results_playhead_on_dataset_change(
        session_state=session_state,
        cache_key=cache_key,
        dataset_id_ui=dataset_id_ui,
        time_s=time_s,
        make_playhead_reset_command_fn=make_playhead_reset_command_fn,
        log_event_fn=log_event_fn,
    )

    apply_results_playhead_request_x(
        session_state=session_state,
        time_s=time_s,
        make_playhead_jump_command_fn=make_playhead_jump_command_fn,
    )

    playhead_idx, playhead_x = prepare_results_timeline_prelude(
        st,
        session_state=session_state,
        time_s=time_s,
    )

    render_results_event_controls(
        st,
        session_state=session_state,
        **event_controls_kwargs,
    )

    events_list = compute_results_events(
        session_state=session_state,
        **compute_results_events_kwargs,
    )

    return {
        "dataset_id_ui": dataset_id_ui,
        "playhead_idx": int(playhead_idx),
        "playhead_x": playhead_x,
        "events_list": events_list,
    }
