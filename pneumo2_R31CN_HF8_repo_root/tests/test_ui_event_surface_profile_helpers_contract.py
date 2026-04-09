from pathlib import Path

from pneumo_solver_ui.ui_event_surface_profile_helpers import (
    build_mech_pick_consumer,
    build_playhead_event_consumer,
    build_plotly_pick_consumer,
    build_svg_pick_consumer,
)


ROOT = Path(__file__).resolve().parents[1]


def _apply_pick_list(cur, name: str, mode: str) -> list[str]:
    items = list(cur) if isinstance(cur, list) else []
    if mode == "replace":
        return [name]
    if name not in items:
        items.append(name)
    return items


def test_event_surface_profile_builders_return_bound_consumers() -> None:
    state = {
        "svg_pick_event": {"kind": "edge", "name": "edge_A", "ts": 1},
        "svg_click_mode": "add",
        "flow_graph_edges": [],
        "anim_edges_svg": [],
    }
    build_svg_pick_consumer(state, apply_pick_list_fn=_apply_pick_list)()
    assert state["svg_selected_edge"] == "edge_A"

    state["mech3d_pick_event"] = {"name": "front", "ts": 2}
    build_mech_pick_consumer(state)()
    assert state["mech_plot_corners"] == ["ко", "оо"]

    state.update(
        {
            "plot_flow_edges": {"kind": "flow"},
            "plot_flow_edges__trace_names": ["edge_A", "edge_B"],
            "plot_node_pressure": {"kind": "node"},
            "plot_node_pressure__trace_names": ["node_A", "node_B"],
            "node_pressure_plot": [],
            "anim_nodes_svg": [],
        }
    )
    build_plotly_pick_consumer(
        state,
        extract_plotly_selection_points_fn=lambda plot_state: [{"curve_number": 0, "x": 7.0}] if plot_state else [],
        plotly_points_signature_fn=repr,
        apply_pick_list_fn=_apply_pick_list,
    )()
    assert state["playhead_request_x"] == 7.0

    logged = []
    state["playhead_event"] = {"dataset_id": "demo", "idx": 1, "t": 0.5, "ts": 10}
    build_playhead_event_consumer(
        state,
        persist_browser_perf_snapshot_event_fn=lambda *_args, **_kwargs: None,
        workspace_exports_dir=ROOT,
        log_event_fn=lambda event, **fields: logged.append((event, fields)),
        proc_metrics_fn=lambda: {"pid": 1},
    )()
    assert logged and logged[0][0] == "playhead_update"


def test_active_entrypoints_use_shared_event_surface_profile_builders() -> None:
    helper_source = (ROOT / "pneumo_solver_ui" / "ui_event_surface_profile_helpers.py").read_text(encoding="utf-8")
    app_source = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def build_svg_pick_consumer" in helper_source
    assert "def build_mech_pick_consumer" in helper_source
    assert "def build_plotly_pick_consumer" in helper_source
    assert "def build_playhead_event_consumer" in helper_source
    assert "from pneumo_solver_ui.ui_event_surface_profile_helpers import (" in app_source
    assert "from pneumo_solver_ui.ui_event_surface_profile_helpers import (" in heavy_source
    assert "build_svg_pick_consumer(" in app_source
    assert "build_mech_pick_consumer(" in app_source
    assert "build_plotly_pick_consumer(" in app_source
    assert "build_playhead_event_consumer(" in app_source
    assert "build_svg_pick_consumer(" in heavy_source
    assert "build_mech_pick_consumer(" in heavy_source
    assert "build_plotly_pick_consumer(" in heavy_source
    assert "build_playhead_event_consumer(" in heavy_source
