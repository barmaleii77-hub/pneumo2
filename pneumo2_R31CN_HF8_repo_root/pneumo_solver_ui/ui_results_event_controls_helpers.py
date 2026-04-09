from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def render_results_event_controls(
    st: Any,
    *,
    session_state: Mapping[str, object],
    vacuum_label: str,
    pmax_label: str,
    vacuum_state_key: str,
    pmax_state_key: str,
    migration_source_vacuum_key: str | None = None,
    migration_source_pmax_key: str | None = None,
    migration_scale: float = 1.0,
    graph_severity_options: Sequence[str] = ("error", "warn", "info"),
    graph_severity_default: Sequence[str] = ("error", "warn"),
) -> None:
    if migration_source_vacuum_key and vacuum_state_key not in session_state and migration_source_vacuum_key in session_state:
        try:
            session_state[vacuum_state_key] = float(session_state[migration_source_vacuum_key]) * float(migration_scale)
        except Exception:
            pass
    if migration_source_pmax_key and pmax_state_key not in session_state and migration_source_pmax_key in session_state:
        try:
            session_state[pmax_state_key] = float(session_state[migration_source_pmax_key]) * float(migration_scale)
        except Exception:
            pass

    cols_evt = st.columns([1, 1, 1, 1])
    with cols_evt[0]:
        st.checkbox("События/алёрты", value=True, key="events_show")
    with cols_evt[1]:
        st.slider(vacuum_label, -1.0, 0.0, -0.2, 0.05, key=vacuum_state_key)
    with cols_evt[2]:
        st.slider(pmax_label, 0.0, 1.0, 0.10, 0.05, key=pmax_state_key)
    with cols_evt[3]:
        st.slider("Дребезг: toggles/окно", 3, 20, 6, 1, key="events_chatter_toggles")

    cols_evt2 = st.columns([1, 2, 1, 1])
    with cols_evt2[0]:
        st.checkbox("Метки событий на графиках", value=True, key="events_on_graphs")
    with cols_evt2[1]:
        st.multiselect(
            "Уровни на графиках",
            options=list(graph_severity_options),
            default=list(graph_severity_default),
            key="events_graph_sev",
        )
    with cols_evt2[2]:
        st.checkbox("Подписи error", value=False, key="events_graph_labels")
    with cols_evt2[3]:
        st.slider("Макс. событий на графиках", 0, 300, 120, 10, key="events_graph_max")
