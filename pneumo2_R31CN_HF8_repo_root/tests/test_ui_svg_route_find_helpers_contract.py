from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_find_helpers import (
    find_svg_route_between_labels,
    format_svg_route_success_message,
    resolve_svg_route_endpoints,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SEARCH_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_search_panel_helpers.py"


def test_resolve_svg_route_endpoints_returns_selected_points() -> None:
    texts = [
        {"x": 10, "y": 20},
        {"x": 30, "y": 40},
    ]

    assert resolve_svg_route_endpoints(
        texts,
        "start",
        "end",
        {"start": 0, "end": 1},
    ) == ((10.0, 20.0), (30.0, 40.0))


def test_find_svg_route_between_labels_updates_preview_on_success() -> None:
    session_state: dict[str, object] = {}
    texts = [
        {"x": 10, "y": 20},
        {"x": 30, "y": 40},
    ]

    def fake_shortest_path(**kwargs):
        assert kwargs["nodes_coords"] == ["n1"]
        assert kwargs["edges_ab"] == ["e1"]
        assert kwargs["p_start"] == (10.0, 20.0)
        assert kwargs["p_end"] == (30.0, 40.0)
        assert kwargs["snap_eps_px"] == 0.25
        assert kwargs["simplify_epsilon"] == 1.5
        return {"ok": True, "length": 42.4, "path_xy": [[1.0, 2.0], [3.0, 4.0]]}

    ok, message = find_svg_route_between_labels(
        session_state,
        texts,
        "start",
        "end",
        {"start": 0, "end": 1},
        {"nodes": ["n1"], "edges": ["e1"]},
        1.5,
        shortest_path_fn=fake_shortest_path,
    )

    assert ok is True
    assert message == "Путь найден: длина≈42.4px, точек=2."
    assert session_state["svg_route_paths"] == [[[1.0, 2.0], [3.0, 4.0]]]
    assert session_state["svg_route_report"] == {
        "ok": True,
        "length": 42.4,
        "path_xy": [[1.0, 2.0], [3.0, 4.0]],
    }


def test_find_svg_route_between_labels_stores_error_report() -> None:
    session_state: dict[str, object] = {"svg_route_paths": [[0.0, 0.0]]}

    def fake_shortest_path(**kwargs):
        raise RuntimeError("boom")

    ok, message = find_svg_route_between_labels(
        session_state,
        [{"x": 10, "y": 20}, {"x": 30, "y": 40}],
        "start",
        "end",
        {"start": 0, "end": 1},
        {"nodes": [], "edges": []},
        0.5,
        shortest_path_fn=fake_shortest_path,
    )

    assert ok is False
    assert message == "Не удалось найти путь: boom"
    assert session_state["svg_route_paths"] == []
    assert session_state["svg_route_report"] == {"ok": False, "error": "boom"}


def test_format_svg_route_success_message_defaults() -> None:
    assert format_svg_route_success_message({}) == "Путь найден: длина≈0.0px, точек=0."


def test_entrypoints_use_shared_svg_route_find_helpers() -> None:
    search_panel_text = SEARCH_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_mapping_state_helpers import clear_svg_route_preview" in search_panel_text
    assert "from pneumo_solver_ui.ui_svg_route_find_helpers import find_svg_route_between_labels" in search_panel_text
    assert "find_svg_route_between_labels(" in search_panel_text
    assert "clear_svg_route_preview(session_state)" in search_panel_text
    assert "si = opt_to_idx.get(start_opt, None)" not in search_panel_text
    assert 'p1 = (float(texts[si].get("x", 0.0)), float(texts[si].get("y", 0.0)))' not in search_panel_text
    assert 'st.session_state["svg_route_paths"] = [route.get("path_xy", [])]' not in search_panel_text
