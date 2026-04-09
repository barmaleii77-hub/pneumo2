from pathlib import Path

from pneumo_solver_ui.ui_event_sync_helpers import (
    consume_mech_pick_event,
    consume_playhead_event,
    consume_plotly_pick_events,
    consume_svg_pick_event,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def _apply_pick_list(cur, name: str, mode: str) -> list[str]:
    items = list(cur) if isinstance(cur, list) else []
    if mode == "replace":
        return [name]
    if name not in items:
        items.append(name)
    return items


def test_consume_svg_and_mech_pick_events_sync_expected_state() -> None:
    state = {
        "svg_pick_event": {"kind": "edge", "name": "edge_A", "ts": 1},
        "svg_click_mode": "add",
        "flow_graph_edges": [],
        "anim_edges_svg": [],
    }
    consume_svg_pick_event(state, _apply_pick_list)
    assert state["svg_selected_edge"] == "edge_A"
    assert state["flow_graph_edges"] == ["edge_A"]
    assert state["anim_edges_svg"] == ["edge_A"]

    state["mech3d_pick_event"] = {"name": "front", "ts": 2}
    consume_mech_pick_event(state)
    assert state["mech_selected_corners"] == ["ко", "оо"]
    assert state["mech_plot_corners"] == ["ко", "оо"]


def test_consume_plotly_and_playhead_events_update_selection_and_logging() -> None:
    state = {
        "plot_flow_edges": {"kind": "flow"},
        "plot_flow_edges__trace_names": ["edge_A", "edge_B"],
        "plot_node_pressure": {"kind": "node"},
        "plot_node_pressure__trace_names": ["node_A", "node_B"],
        "anim_edges_svg": [],
        "anim_nodes_svg": [],
        "node_pressure_plot": [],
    }

    def _extract_points(plot_state):
        kind = (plot_state or {}).get("kind")
        if kind == "flow":
            return [{"curve_number": 1, "x": 12.5}]
        if kind == "node":
            return [{"curve_number": 0, "x": 7.0}]
        return []

    def _signature(points):
        return repr(points)

    consume_plotly_pick_events(state, _extract_points, _signature, _apply_pick_list)
    assert state["svg_selected_edge"] == "edge_B"
    assert state["anim_edges_svg"] == ["edge_B"]
    assert state["svg_selected_node"] == "node_A"
    assert state["anim_nodes_svg"] == ["node_A"]
    assert state["node_pressure_plot"] == ["node_A"]
    assert state["playhead_request_x"] == 7.0

    logged = []
    state["playhead_event"] = {
        "kind": "playhead",
        "dataset_id": "demo",
        "idx": 3,
        "t": 1.25,
        "playing": True,
        "speed": 1.5,
        "loop": False,
        "picked_event": {"name": "marker"},
        "ts": 99,
    }
    consume_playhead_event(
        state,
        persist_browser_perf_snapshot_event_fn=lambda *_args, **_kwargs: None,
        workspace_exports_dir=REPO_ROOT,
        log_event_fn=lambda event, **fields: logged.append((event, fields)),
        proc_metrics_fn=lambda: {"pid": 1},
    )
    assert state["playhead_dataset_id"] == "demo"
    assert state["playhead_idx"] == 3
    assert state["playhead_t"] == 1.25
    assert state["playhead_playing"] is True
    assert state["playhead_speed"] == 1.5
    assert state["playhead_loop"] is False
    assert state["playhead_picked_event"] == {"name": "marker"}
    assert logged and logged[0][0] == "playhead_update"


def test_large_ui_entrypoints_import_shared_event_sync_helpers() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_event_sync_helpers import (" in src
        assert "from pneumo_solver_ui.ui_event_surface_profile_helpers import (" in src
        assert "consume_svg_pick_event = build_svg_pick_consumer(" in src
        assert "consume_mech_pick_event = build_mech_pick_consumer(" in src
        assert "consume_plotly_pick_events = build_plotly_pick_consumer(" in src
        assert "consume_playhead_event = build_playhead_event_consumer(" in src
        assert "def consume_svg_pick_event(" not in src
        assert "def consume_mech_pick_event(" not in src
        assert "def consume_plotly_pick_events(" not in src
        assert "def consume_playhead_event(" not in src
