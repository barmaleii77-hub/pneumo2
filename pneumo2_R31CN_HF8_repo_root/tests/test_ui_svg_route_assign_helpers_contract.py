from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_assign_helpers import (
    build_svg_route_assignment_edge_meta,
    evaluate_svg_route_quality_for_assignment,
    write_svg_route_assignment,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
ROUTE_EDIT_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_mapping_edit_helpers.py"


def test_evaluate_svg_route_quality_for_assignment_updates_session_state() -> None:
    session_state: dict[str, object] = {
        "route_q_min_turn_deg": 50.0,
        "route_q_max_detour": 6.0,
        "route_q_max_attach_dist": 20.0,
    }

    def fake_evaluate(polyline, **kwargs):
        assert polyline == [[1.0, 2.0], [3.0, 4.0]]
        assert kwargs == {
            "attach_start": {"x": 1},
            "attach_end": {"x": 2},
            "min_turn_deg": 50.0,
            "max_detour": 6.0,
            "max_attach_dist": 20.0,
        }
        return {"grade": "PASS"}

    quality_report = evaluate_svg_route_quality_for_assignment(
        session_state,
        [[1.0, 2.0], [3.0, 4.0]],
        {"attach_start": {"x": 1}, "attach_end": {"x": 2}},
        evaluate_quality_fn=fake_evaluate,
    )

    assert quality_report == {"grade": "PASS"}
    assert session_state["svg_route_quality"] == {"grade": "PASS"}


def test_build_svg_route_assignment_edge_meta_uses_session_state_and_route() -> None:
    meta = build_svg_route_assignment_edge_meta(
        {"svg_route_label_picks": {"start": {"ti": 1}, "end": {"ti": 2}}},
        [[0.0, 0.0], [1.0, 1.0]],
        {"length": 42.5},
        {"grade": "WARN"},
        timestamp=123.0,
    )

    assert meta == {
        "manual": True,
        "quality": {"grade": "WARN"},
        "review": {"status": "approved", "by": "manual", "ts": 123.0},
        "route": {"length_px": 42.5, "points": 2},
        "start_end": {"start": {"ti": 1}, "end": {"ti": 2}},
    }


def test_write_svg_route_assignment_updates_mapping_and_merges_edge_meta() -> None:
    mapping = {
        "version": 2,
        "viewBox": "existing-box",
        "edges": {"edge-a": [[[0.0, 0.0], [1.0, 1.0]]]},
        "nodes": {},
        "edges_meta": {"edge-a": {"keep": 1, "review": {"by": "human"}}},
    }
    session_state: dict[str, object] = {"svg_route_label_picks": {"start": {"ti": 7}}}

    quality_report = write_svg_route_assignment(
        mapping,
        session_state,
        "edge-a",
        [[2.0, 2.0], [3.0, 3.0]],
        "Добавить сегмент",
        {"length": 99.0, "attach_start": {"x": 1}, "attach_end": {"x": 2}},
        view_box="new-box",
        evaluate_quality_fn=lambda *args, **kwargs: {"grade": "PASS", "score": 0.9},
        timestamp=456.0,
    )

    assert quality_report == {"grade": "PASS", "score": 0.9}
    assert session_state["svg_route_quality"] == {"grade": "PASS", "score": 0.9}
    assert mapping["viewBox"] == "existing-box"
    assert mapping["edges"]["edge-a"] == [
        [[0.0, 0.0], [1.0, 1.0]],
        [[2.0, 2.0], [3.0, 3.0]],
    ]
    assert mapping["meta"]["last_route_assign"] == {
        "edge": "edge-a",
        "mode": "Добавить сегмент",
        "route_length_px": 99.0,
        "points": 2,
        "ts": 456.0,
    }
    assert mapping["edges_meta"]["edge-a"] == {
        "keep": 1,
        "manual": True,
        "quality": {"grade": "PASS", "score": 0.9},
        "review": {"by": "manual", "status": "approved", "ts": 456.0},
        "route": {"length_px": 99.0, "points": 2},
        "start_end": {"start": {"ti": 7}},
    }


def test_write_svg_route_assignment_keeps_working_when_quality_fails() -> None:
    mapping: dict[str, object] = {}
    session_state: dict[str, object] = {}

    quality_report = write_svg_route_assignment(
        mapping,
        session_state,
        "edge-b",
        [[10.0, 10.0], [20.0, 20.0]],
        "replace",
        {"length": 12.0},
        view_box="0 0 100 100",
        evaluate_quality_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        timestamp=789.0,
    )

    assert quality_report is None
    assert "svg_route_quality" not in session_state
    assert mapping["edges"] == {"edge-b": [[[10.0, 10.0], [20.0, 20.0]]]}
    assert mapping["edges_meta"]["edge-b"]["quality"] is None
    assert mapping["meta"]["last_route_assign"]["ts"] == 789.0


def test_entrypoints_use_shared_svg_route_assign_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    route_edit_text = ROUTE_EDIT_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_route_assign_helpers import write_svg_route_assignment" in route_edit_text
    assert "write_svg_route_assignment(" in route_edit_text
    assert 'segs = mapping2["edges"].get(edge_target, [])' not in app_text
    assert 'segs = mapping2["edges"].get(edge_target, [])' not in heavy_text
    assert 'update_svg_mapping_meta(mapping2, "last_route_assign"' not in app_text
    assert 'update_svg_mapping_meta(mapping2, "last_route_assign"' not in heavy_text
    assert 'edge_meta_new = {' not in app_text
    assert 'edge_meta_new = {' not in heavy_text
