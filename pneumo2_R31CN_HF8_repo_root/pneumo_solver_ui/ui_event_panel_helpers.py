from __future__ import annotations

import time
from collections.abc import Sequence

import pandas as pd
import streamlit as st

from pneumo_solver_ui.ui_playhead_helpers import make_playhead_jump_command


def build_event_alerts_table(events_list: Sequence[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "t, s": float(event.get("t", 0.0)),
                "severity": event.get("severity"),
                "kind": event.get("kind"),
                "name": event.get("name"),
                "label": event.get("label"),
                "idx": int(event.get("idx", 0)),
            }
            for event in events_list
        ]
    )


def format_event_jump_option(events_list: Sequence[dict], index: int) -> str:
    event = events_list[index]
    return f't={float(event.get("t", 0.0)):.3f}s | {event.get("severity", "")} | {event.get("label", "")}'


def render_event_alerts_panel(
    events_list: Sequence[dict] | None,
    *,
    safe_dataframe_fn,
    time_ms_fn=time.time,
) -> None:
    picked_event = st.session_state.get("playhead_picked_event")
    if isinstance(picked_event, dict):
        st.caption(f"Последний клик по событию: {picked_event.get('label', '')}")

    if not st.session_state.get("events_show", True) or not events_list:
        return

    with st.expander("События/алёрты", expanded=False):
        st.caption(f"Найдено событий: {len(events_list)}")
        safe_dataframe_fn(build_event_alerts_table(events_list), height=240)

        options = list(range(len(events_list)))

        def _fmt(index: int) -> str:
            return format_event_jump_option(events_list, index)

        selected_index = st.selectbox(
            "Перейти к событию",
            options=options,
            format_func=_fmt,
            key="events_jump_sel",
        )
        if st.button("Перейти (jump playhead)", key="events_jump_btn"):
            try:
                event = events_list[int(selected_index)]
                jump_index = int(event.get("idx", 0))
                st.session_state["playhead_cmd"] = make_playhead_jump_command(jump_index, time_ms_fn=time_ms_fn)
                st.session_state["playhead_idx"] = jump_index
                st.session_state["playhead_t"] = float(event.get("t", 0.0))
            except Exception:
                pass
