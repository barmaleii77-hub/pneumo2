from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_shell_helpers.py"
EDITOR_PANEL_HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py"
SECTION_HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_section_helpers.py"
APP = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_suite_editor_shell_helper_keeps_clean_russian_copy() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "2. Тестовый набор" in text
    assert "Список тестов. Слева выбирается сценарий" in text
    assert "Выберите тест слева, чтобы открыть карточку редактирования." in text
    assert "Карточка выбранного сценария." in text
    assert "Показано **" in text
    assert "Поиск теста" in text
    assert "Сбросить фильтры" in text
    assert "Включить все" in text
    assert "Добавить тест-шаблон" in text
    assert "Всего тестов:" in text
    assert "Инерция: торможение ax=-3 м/с²" in text


def test_suite_editor_shell_helper_exposes_shared_list_panels() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "build_app_suite_selection_options(" in text
    assert "render_app_suite_list_panel(" in text
    assert "render_app_suite_left_panel(" in text
    assert "build_heavy_suite_list_label(" in text
    assert "build_heavy_suite_list_frame(" in text
    assert "render_heavy_suite_list_panel(" in text
    assert "render_heavy_suite_left_panel(" in text


def test_suite_editor_panel_helper_uses_left_and_right_panels() -> None:
    text = EDITOR_PANEL_HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_card_panel_helpers import (" in text
    assert "from pneumo_solver_ui.ui_suite_editor_shell_helpers import (" in text
    assert "render_app_suite_search_box," in text
    assert "render_app_suite_left_panel," in text
    assert "render_heavy_suite_left_panel," in text
    assert "def render_app_suite_master_detail_panel(" in text
    assert "def render_heavy_suite_master_detail_panel(" in text
    assert "render_app_suite_right_card_panel(" in text
    assert "render_heavy_suite_right_card_panel(" in text


def test_suite_editor_section_helper_uses_intro_and_filter_shells() -> None:
    text = SECTION_HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_editor_shell_helpers import (" in text
    assert "render_app_suite_editor_intro," in text
    assert "render_heavy_suite_editor_intro," in text
    assert "render_heavy_suite_preset_wizard," in text
    assert "render_heavy_suite_filter_row," in text
    assert "render_suite_hidden_summary," in text
    assert "render_app_suite_editor_intro(st)" in text
    assert "render_heavy_suite_editor_intro(st)" in text
    assert "render_heavy_suite_preset_wizard(" in text
    assert "render_heavy_suite_filter_row(" in text
    assert "render_suite_hidden_summary(" in text


def test_app_suite_editor_uses_shared_section_helper() -> None:
    text = APP.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_editor_section_helpers import (" in text
    assert "render_app_suite_editor_section," in text
    assert "render_app_suite_editor_section(" in text
    assert "render_app_suite_editor_intro(st)" not in text
    assert "render_app_suite_master_detail_panel(" not in text


def test_heavy_suite_editor_uses_shared_section_helper() -> None:
    text = HEAVY.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_editor_section_helpers import (" in text
    assert "render_heavy_suite_editor_section," in text
    assert "render_heavy_suite_editor_section(" in text
    assert "render_heavy_suite_editor_intro(st)" not in text
    assert "render_heavy_suite_master_detail_panel(" not in text
    assert "render_heavy_suite_filter_row(" not in text
    assert "render_suite_hidden_summary(" not in text
    assert "render_heavy_suite_preset_wizard(" not in text
