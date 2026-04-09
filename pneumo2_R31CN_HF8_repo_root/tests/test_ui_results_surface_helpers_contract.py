from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_surface_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_render_results_surface_binds_events_to_playhead_and_results(monkeypatch) -> None:
    overlay_calls: list[tuple[object, object]] = []
    playhead_calls: list[dict[str, object]] = []
    results_calls: list[tuple[object, dict[str, object]]] = []

    monkeypatch.setattr(
        helpers,
        "prepare_events_for_graph_overlays",
        lambda events_list, session_state: (
            overlay_calls.append((list(events_list or []), session_state))
            or ([{"idx": 7, "severity": "warn"}], True, 42)
        ),
    )

    playhead_kwargs = {"token": "playhead-token"}
    results_kwargs = {
        "token": "results-token",
        "results_graph_section_kwargs": {"graph": "keep"},
        "secondary_results_views_kwargs": {
            "flow_section_kwargs": {"flow": "keep"},
            "animation_section_kwargs": {"anim": "keep"},
        },
    }

    view_res, playhead_status = helpers.render_results_surface(
        "streamlit",
        events_list=[{"idx": 1, "severity": "error"}],
        session_state={"events_on_graphs": True},
        render_playhead_results_section_fn=lambda **kwargs: playhead_calls.append(kwargs) or "missing",
        playhead_results_section_kwargs=playhead_kwargs,
        render_results_section_fn=lambda st, **kwargs: results_calls.append((st, kwargs)) or "Графики",
        results_section_kwargs=results_kwargs,
    )

    assert view_res == "Графики"
    assert playhead_status == "missing"
    assert overlay_calls == [([{"idx": 1, "severity": "error"}], {"events_on_graphs": True})]
    assert playhead_calls == [{"token": "playhead-token"}]
    assert results_calls == [
        (
            "streamlit",
            {
                "token": "results-token",
                "results_graph_section_kwargs": {
                    "graph": "keep",
                    "events_for_graphs": [{"idx": 7, "severity": "warn"}],
                    "events_graph_max": 42,
                    "events_graph_labels": True,
                },
                "secondary_results_views_kwargs": {
                    "flow_section_kwargs": {
                        "flow": "keep",
                        "events_for_graphs": [{"idx": 7, "severity": "warn"}],
                        "events_graph_max": 42,
                        "events_graph_labels": True,
                    },
                    "animation_section_kwargs": {"anim": "keep"},
                },
            },
        )
    ]
    assert playhead_kwargs == {"token": "playhead-token"}
    assert results_kwargs == {
        "token": "results-token",
        "results_graph_section_kwargs": {"graph": "keep"},
        "secondary_results_views_kwargs": {
            "flow_section_kwargs": {"flow": "keep"},
            "animation_section_kwargs": {"anim": "keep"},
        },
    }


def test_entrypoints_use_shared_results_surface_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_surface_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_surface_helpers import (" not in heavy_text
    assert "render_results_surface(" not in app_text
    assert "render_results_surface(" not in heavy_text
    assert "prepare_events_for_graph_overlays(" not in app_text
    assert "prepare_events_for_graph_overlays(" not in heavy_text
    assert "render_playhead_results_section(" not in app_text
    assert "render_playhead_results_section(" not in heavy_text
    assert "render_results_section(" not in app_text
    assert "render_results_section(" not in heavy_text
    assert "def render_results_surface(" in helper_text
    assert "prepare_events_for_graph_overlays(" in helper_text
    assert "render_playhead_results_section_fn(**playhead_results_section_kwargs)" in helper_text
    assert "render_results_section_fn(st, **results_section_bound_kwargs)" in helper_text
    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in heavy_text
    assert "render_results_surface(" in section_text
