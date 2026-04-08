from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_assignment_panel_helpers import (
    is_svg_route_polyline_ready,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SEARCH_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_search_panel_helpers.py"


def test_is_svg_route_polyline_ready_accepts_valid_route_paths() -> None:
    assert is_svg_route_polyline_ready([[[1.0, 2.0], [3.0, 4.0]]]) is True
    assert is_svg_route_polyline_ready([]) is False
    assert is_svg_route_polyline_ready([[]]) is False
    assert is_svg_route_polyline_ready(None) is False


def test_entrypoints_use_shared_svg_route_assignment_panel_helpers() -> None:
    search_panel_text = SEARCH_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_route_assignment_panel_helpers import (" in search_panel_text
    assert "render_svg_route_assignment_panel(" in search_panel_text
    assert 'st.markdown("#### Привязать найденный путь к ветке модели (mapping.edges)")' not in search_panel_text
    assert 'btn_assign = st.button("Записать маршрут", key="btn_svg_route_assign")' not in search_panel_text
    assert 'btn_clear_edge = st.button("Очистить ветку", key="btn_svg_route_clear_edge")' not in search_panel_text
