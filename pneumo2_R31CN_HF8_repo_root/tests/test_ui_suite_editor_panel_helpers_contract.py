from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py"
SECTION_HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_section_helpers.py"


def test_suite_editor_panel_helper_contains_master_detail_orchestration() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "def render_app_suite_master_detail_panel(" in text
    assert "def render_heavy_suite_master_detail_panel(" in text
    assert 'st.columns([1.0, 1.2], gap="large")' in text
    assert 'st.columns([1.05, 1.0], gap="large")' in text
    assert "render_app_suite_search_box(" in text
    assert "render_app_suite_left_panel(" in text
    assert "render_heavy_suite_left_panel(" in text
    assert "render_app_suite_right_card_panel(" in text
    assert "render_heavy_suite_right_card_panel(" in text


def test_suite_editor_section_helper_uses_master_detail_panel() -> None:
    text = SECTION_HELPER.read_text(encoding="utf-8")

    assert "render_app_suite_master_detail_panel(" in text
    assert "render_heavy_suite_master_detail_panel(" in text
