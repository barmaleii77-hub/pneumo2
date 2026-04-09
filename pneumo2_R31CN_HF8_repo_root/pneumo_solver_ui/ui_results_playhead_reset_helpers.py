from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable


def reset_results_playhead_on_dataset_change(
    *,
    session_state: Mapping[str, object],
    cache_key: str,
    dataset_id_ui: str,
    time_s: Sequence[float] | None,
    make_playhead_reset_command_fn: Callable[[], dict[str, Any]],
    log_event_fn: Callable[..., Any],
    active_dataset_key: str = "playhead_active_dataset",
) -> bool:
    if session_state.get(active_dataset_key) == cache_key:
        return False

    session_state[active_dataset_key] = cache_key
    session_state["playhead_idx"] = 0
    if time_s:
        session_state["playhead_t"] = float(time_s[0])
    session_state["playhead_cmd"] = make_playhead_reset_command_fn()
    log_event_fn("playhead_reset", dataset_id=str(dataset_id_ui))
    return True
