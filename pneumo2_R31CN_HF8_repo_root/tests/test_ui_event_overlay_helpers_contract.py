from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_event_overlay_helpers import prepare_events_for_graph_overlays


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
RESULTS_SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_helpers.py"


def test_prepare_events_for_graph_overlays_filters_sorts_and_thins() -> None:
    events_list = [
        {"idx": 9, "severity": "info"},
        {"idx": 3, "severity": "warn"},
        {"idx": 1, "severity": "error"},
        {"idx": 7, "severity": "warn"},
        {"idx": 5, "severity": "warn"},
        {"idx": 11, "severity": "warn"},
        {"idx": 13, "severity": "warn"},
        {"idx": 15, "severity": "warn"},
        {"idx": 17, "severity": "warn"},
        {"idx": 19, "severity": "warn"},
        {"idx": 21, "severity": "warn"},
        {"idx": 23, "severity": "warn"},
        {"idx": 25, "severity": "warn"},
        {"idx": 27, "severity": "warn"},
    ]
    session_state = {
        "events_on_graphs": True,
        "events_graph_labels": True,
        "events_graph_sev": ["error", "warn"],
        "events_graph_max": 2,
    }

    events_for_graphs, events_graph_labels, events_graph_max = prepare_events_for_graph_overlays(
        events_list,
        session_state,
    )

    assert events_graph_labels is True
    assert events_graph_max == 2
    assert all(event["severity"] in {"error", "warn"} for event in events_for_graphs)
    assert [event["idx"] for event in events_for_graphs] == [1, 5, 11, 15, 19, 23, 27]


def test_prepare_events_for_graph_overlays_handles_disabled_or_bad_max() -> None:
    events_for_graphs, events_graph_labels, events_graph_max = prepare_events_for_graph_overlays(
        [{"idx": 1, "severity": "error"}],
        {
            "events_on_graphs": False,
            "events_graph_labels": False,
            "events_graph_max": "oops",
        },
    )

    assert events_for_graphs == []
    assert events_graph_labels is False
    assert events_graph_max == 120


def test_entrypoints_use_shared_event_overlay_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = RESULTS_SURFACE_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_event_overlay_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_event_overlay_helpers import (" not in heavy_text
    assert "prepare_events_for_graph_overlays(" not in app_text
    assert "prepare_events_for_graph_overlays(" not in heavy_text
    assert "prepare_events_for_graph_overlays(" in surface_text
    assert 'events_graph_sev", ["error", "warn"]' not in app_text
    assert 'events_graph_sev", ["error", "warn"]' not in heavy_text
    assert "events_for_graphs.sort(key=lambda e: int(e.get(\"idx\", 0)))" not in app_text
    assert "events_for_graphs.sort(key=lambda e: int(e.get(\"idx\", 0)))" not in heavy_text
