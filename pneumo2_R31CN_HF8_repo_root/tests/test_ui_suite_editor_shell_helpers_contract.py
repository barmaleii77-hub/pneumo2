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

    assert "2. Набор сценариев" in text
    assert '"worldroad": "Дорожный профиль (WorldRoad)"' in text
    assert '"road_profile_csv": "Дорога из CSV"' in text
    assert '"maneuver_csv": "Манёвр из CSV (ax/ay)"' in text
    assert '"инерция_крен": "Инерция: крен"' in text
    assert '"микро_синфаза": "Микроход: синфаза"' in text
    assert '"кочка_диагональ": "Кочка: диагональ"' in text
    assert "Список сценариев набора. Слева выбирается сценарий" in text
    assert "Ровная дорога (WorldRoad)" in text
    assert "По текущим условиям отбора сценарии не найдены." in text
    assert "фильтр по стадиям" in text
    assert "без названия" in text
    assert "тип не задан" in text
    assert "Показать весь набор" in text
    assert "Сценарий для редактирования" in text
    assert "Включить все видимые" in text
    assert "Выключить все видимые" in text
    assert "Дублировать выбранный сценарий" in text
    assert "Удалить выбранный сценарий" in text
    assert "Набор сценариев пока пуст." in text
    assert "Выбранный сценарий не найден в текущем наборе." in text
    assert "меняйте стадию сценария, тип сценария" in text
    assert "Логика оптимизации по стадиям" in text
    assert "быстрый предварительный отсев" in text
    assert "финальная стадия проверки устойчивости" in text
    assert "нормализации стадий" in text
    assert "меняйте stage" not in text
    assert "staged optimization" not in text
    assert "relevance-screen" not in text
    assert "robustness-стадия" not in text
    assert "staged-normalization" not in text
    assert "Выберите сценарий слева, чтобы открыть карточку редактирования." in text
    assert "Карточка выбранного сценария." in text
    assert "Показано **" in text
    assert "Поиск сценария" in text
    assert "Сбросить фильтры" in text
    assert "Добавить сценарий по шаблону" in text
    assert "Всего сценариев:" in text
    assert "Инерция: торможение ax=-3 м/с²" in text
    assert "WorldRoad: ровная дорога" not in text
    assert "Список пуст в текущем фильтре." not in text
    assert "stage-фильтр" not in text
    assert "<без имени>" not in text
    assert "<без типа>" not in text
    assert "Список тестов. Слева выбирается сценарий" not in text
    assert "Показать все" not in text
    assert "Выбранный тест" not in text
    assert "Тестовый набор" not in text
    assert "Поиск теста" not in text
    assert "Добавить тест-шаблон" not in text
    assert "Всего тестов:" not in text
    assert "Выберите тест слева" not in text
    assert '"имя": "Сценарий"' in text


def test_suite_editor_shell_helper_exposes_shared_list_panels() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "def format_suite_test_type_label(" in text
    assert "build_app_suite_selection_options(" in text
    assert "render_app_suite_list_panel(" in text
    assert "render_app_suite_left_panel(" in text
    assert "build_heavy_suite_list_label(" in text
    assert "build_heavy_suite_list_frame(" in text
    assert 'list_df["тип"] = list_df["тип"].map(format_suite_test_type_label)' in text
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
