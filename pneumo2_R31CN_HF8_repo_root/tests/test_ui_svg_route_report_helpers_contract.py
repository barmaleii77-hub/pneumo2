from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_report_helpers import (
    build_svg_route_quality_details,
    build_svg_route_report_details,
    evaluate_svg_route_quality_report,
    resolve_svg_route_quality_params,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SEARCH_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_search_panel_helpers.py"


def test_build_svg_route_report_details_keeps_expected_fields() -> None:
    route_report = {
        "ok": True,
        "length": 42.0,
        "node_count": 7,
        "attach_start": {"x": 1},
        "attach_end": {"x": 2},
        "params": {"snap_eps_px": 0.25},
        "ignored": "value",
    }

    assert build_svg_route_report_details(route_report) == {
        "ok": True,
        "length_px": 42.0,
        "node_count": 7,
        "attach_start": {"x": 1},
        "attach_end": {"x": 2},
        "params": {"snap_eps_px": 0.25},
    }


def test_resolve_svg_route_quality_params_falls_back_on_bad_values() -> None:
    assert resolve_svg_route_quality_params(
        {
            "route_q_min_turn_deg": "oops",
            "route_q_max_detour": 3.5,
            "route_q_max_attach_dist": 9.0,
        }
    ) == {
        "min_turn_deg": 45.0,
        "max_detour": 8.0,
        "max_attach_dist": 35.0,
    }


def test_evaluate_svg_route_quality_report_updates_session_state_on_success() -> None:
    session_state: dict[str, object] = {
        "route_q_min_turn_deg": 50.0,
        "route_q_max_detour": 6.5,
        "route_q_max_attach_dist": 21.0,
    }
    route_report = {
        "path_xy": [[0.0, 0.0], [1.0, 1.0]],
        "attach_start": {"dist": 1.0},
        "attach_end": {"dist": 2.0},
    }

    def fake_evaluate(path_xy, **kwargs):
        assert path_xy == [[0.0, 0.0], [1.0, 1.0]]
        assert kwargs == {
            "attach_start": {"dist": 1.0},
            "attach_end": {"dist": 2.0},
            "min_turn_deg": 50.0,
            "max_detour": 6.5,
            "max_attach_dist": 21.0,
        }
        return {"grade": "PASS", "points": 2}

    quality_report = evaluate_svg_route_quality_report(
        session_state,
        route_report,
        evaluate_quality_fn=fake_evaluate,
    )

    assert quality_report == {"grade": "PASS", "points": 2}
    assert session_state["svg_route_quality"] == {"grade": "PASS", "points": 2}


def test_evaluate_svg_route_quality_report_returns_fail_payload_on_error() -> None:
    quality_report = evaluate_svg_route_quality_report(
        {},
        {"path_xy": []},
        evaluate_quality_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert quality_report == {"grade": "FAIL", "reasons": ["Не удалось оценить: boom"]}


def test_build_svg_route_quality_details_keeps_expected_fields() -> None:
    assert build_svg_route_quality_details(
        {
            "grade": "WARN",
            "length_px": 10.0,
            "detour_ratio": 1.1,
            "points": 5,
            "turns": 2,
            "self_intersections": 0,
            "attach_start_dist": 3.0,
            "attach_end_dist": 4.0,
            "reasons": ["ignored"],
        }
    ) == {
        "grade": "WARN",
        "length_px": 10.0,
        "detour_ratio": 1.1,
        "points": 5,
        "turns": 2,
        "self_intersections": 0,
        "attach_start_dist": 3.0,
        "attach_end_dist": 4.0,
    }


def test_entrypoints_use_shared_svg_route_report_helpers() -> None:
    search_panel_text = SEARCH_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_route_report_helpers import render_svg_route_report_panel" in search_panel_text
    assert "render_svg_route_report_panel(" in search_panel_text
    assert 'with st.expander("Маршрут: детали", expanded=False):' not in search_panel_text
    assert 'with st.expander("Проверка качества маршрута (beta)", expanded=False):' not in search_panel_text
