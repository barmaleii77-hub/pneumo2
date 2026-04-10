from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from pneumo_solver_ui.ui_playhead_helpers import render_results_view_selector


def render_results_section(
    st: Any,
    *,
    options: Sequence[str],
    session_state,
    cur_hash: str,
    test_pick: str,
    log_event_fn: Callable[..., Any],
    render_results_graph_section_fn: Callable[..., None],
    results_graph_section_kwargs: dict[str, Any],
    render_secondary_results_views_fn: Callable[..., bool],
    secondary_results_views_kwargs: dict[str, Any],
    graph_view_label: str = "Графики",
    radio_fn: Callable[..., str] | None = None,
) -> str:
    view_res = render_results_view_selector(
        options=options,
        session_state=session_state,
        cur_hash=cur_hash,
        test_pick=test_pick,
        log_event_fn=log_event_fn,
        radio_fn=radio_fn or st.radio,
    )

    if view_res == graph_view_label:
        render_results_graph_section_fn(st, **results_graph_section_kwargs)
    else:
        render_secondary_results_views_fn(
            st,
            view_res=view_res,
            **secondary_results_views_kwargs,
        )
    return str(view_res)
