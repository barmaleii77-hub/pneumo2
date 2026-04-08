from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def prepare_events_for_graph_overlays(
    events_list: Sequence[dict] | None,
    session_state: Mapping[str, object],
) -> tuple[list[dict], bool, int]:
    events_for_graphs: list[dict] = []
    events_graph_labels = bool(session_state.get("events_graph_labels", False))
    try:
        events_graph_max = int(session_state.get("events_graph_max", 120))
    except Exception:
        events_graph_max = 120

    if not events_list or not session_state.get("events_on_graphs", True) or events_graph_max <= 0:
        return events_for_graphs, events_graph_labels, events_graph_max

    sev_allow = {
        str(severity).lower()
        for severity in (session_state.get("events_graph_sev", ["error", "warn"]) or [])
    }
    events_for_graphs = [
        event
        for event in events_list
        if str(event.get("severity", "")).lower() in sev_allow
    ]
    events_for_graphs.sort(key=lambda event: int(event.get("idx", 0)))

    cap = max(10, events_graph_max * 4)
    if len(events_for_graphs) > cap:
        step = int(math.ceil(len(events_for_graphs) / float(cap)))
        if step > 1:
            events_for_graphs = events_for_graphs[::step]

    return events_for_graphs, events_graph_labels, events_graph_max
