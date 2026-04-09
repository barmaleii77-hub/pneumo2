from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from pneumo_solver_ui.ui_event_overlay_helpers import prepare_events_for_graph_overlays


def render_results_surface(
    st: Any,
    *,
    events_list: Sequence[dict[str, Any]] | None,
    session_state: Mapping[str, object],
    render_playhead_results_section_fn: Callable[..., Any],
    playhead_results_section_kwargs: dict[str, Any],
    render_results_section_fn: Callable[..., Any],
    results_section_kwargs: dict[str, Any],
) -> tuple[Any, Any]:
    events_for_graphs, events_graph_labels, events_graph_max = prepare_events_for_graph_overlays(
        events_list,
        session_state,
    )

    playhead_status = render_playhead_results_section_fn(**playhead_results_section_kwargs)

    graph_section_kwargs = dict(results_section_kwargs.get("results_graph_section_kwargs", {}))
    graph_section_kwargs.update(
        {
            "events_for_graphs": events_for_graphs,
            "events_graph_max": events_graph_max,
            "events_graph_labels": events_graph_labels,
        }
    )

    secondary_views_kwargs = dict(results_section_kwargs.get("secondary_results_views_kwargs", {}))
    flow_section_kwargs = dict(secondary_views_kwargs.get("flow_section_kwargs", {}))
    flow_section_kwargs.update(
        {
            "events_for_graphs": events_for_graphs,
            "events_graph_max": events_graph_max,
            "events_graph_labels": events_graph_labels,
        }
    )
    secondary_views_kwargs["flow_section_kwargs"] = flow_section_kwargs

    results_section_bound_kwargs = dict(results_section_kwargs)
    results_section_bound_kwargs["results_graph_section_kwargs"] = graph_section_kwargs
    results_section_bound_kwargs["secondary_results_views_kwargs"] = secondary_views_kwargs

    view_res = render_results_section_fn(st, **results_section_bound_kwargs)
    return view_res, playhead_status
