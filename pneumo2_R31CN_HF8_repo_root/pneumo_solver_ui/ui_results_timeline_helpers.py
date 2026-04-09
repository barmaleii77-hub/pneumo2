from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def prepare_results_timeline_prelude(
    st: Any,
    *,
    session_state: Mapping[str, object],
    time_s: Sequence[float] | None,
    heading_markdown: str = "### ⏱ Общий таймлайн",
) -> tuple[int, float | None]:
    playhead_idx = 0
    playhead_x = None

    if time_s:
        try:
            playhead_idx = int(session_state.get("playhead_idx", 0))
        except Exception:
            playhead_idx = 0
        playhead_idx = max(0, min(playhead_idx, len(time_s) - 1))
        session_state["playhead_idx"] = playhead_idx
        playhead_x = float(time_s[playhead_idx])
        session_state["playhead_t"] = playhead_x

    st.markdown(heading_markdown)
    return playhead_idx, playhead_x
