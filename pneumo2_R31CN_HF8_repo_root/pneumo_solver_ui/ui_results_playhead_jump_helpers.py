from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

import numpy as np


def apply_results_playhead_request_x(
    *,
    session_state: Mapping[str, object],
    time_s: Sequence[float] | None,
    make_playhead_jump_command_fn: Callable[[int], dict[str, Any]],
    request_key: str = "playhead_request_x",
) -> int | None:
    req_x = session_state.pop(request_key, None)
    if req_x is None or not time_s:
        return None

    try:
        req_x_f = float(req_x)
        arr = np.asarray(time_s, dtype=float)
        jump_index = int(np.argmin(np.abs(arr - req_x_f)))
        session_state["playhead_idx"] = jump_index
        session_state["playhead_t"] = float(time_s[jump_index])
        session_state["playhead_cmd"] = make_playhead_jump_command_fn(jump_index)
        return jump_index
    except Exception:
        return None
