from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_search_panel_helpers import (
    format_svg_route_pick_mode_warning,
    resolve_svg_route_end_default_index,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
CONNECTIVITY_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"


def test_resolve_svg_route_end_default_index_matches_previous_behavior() -> None:
    assert resolve_svg_route_end_default_index(0) == 0
    assert resolve_svg_route_end_default_index(1) == 0
    assert resolve_svg_route_end_default_index(2) == 1
    assert resolve_svg_route_end_default_index(5) == 1


def test_format_svg_route_pick_mode_warning_formats_only_known_modes() -> None:
    assert format_svg_route_pick_mode_warning("start") == "Режим выбора метки: **START**. Кликните по текстовой подписи на схеме (SVG справа)."
    assert format_svg_route_pick_mode_warning("END") == "Режим выбора метки: **END**. Кликните по текстовой подписи на схеме (SVG справа)."
    assert format_svg_route_pick_mode_warning("other") is None
    assert format_svg_route_pick_mode_warning(None) is None


def test_entrypoints_use_shared_svg_route_search_panel_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    connectivity_text = CONNECTIVITY_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "render_svg_connectivity_panel(" in section_text
    assert "render_svg_route_search_panel(" in connectivity_text
    assert 'if st.button("Выбрать START кликом на схеме", key="btn_svg_pick_start_label"):' not in app_text
    assert 'if st.button("Выбрать START кликом на схеме", key="btn_svg_pick_start_label"):' not in heavy_text
    assert 'btn_find = st.button("Найти путь", key="btn_svg_route_find")' not in app_text
    assert 'btn_find = st.button("Найти путь", key="btn_svg_route_find")' not in heavy_text
    assert 'btn_clear = st.button("Очистить путь", key="btn_svg_route_clear")' not in app_text
    assert 'btn_clear = st.button("Очистить путь", key="btn_svg_route_clear")' not in heavy_text
