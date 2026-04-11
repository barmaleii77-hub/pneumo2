from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_card_panel_helpers.py"
EDITOR_PANEL_HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py"
APP = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_suite_card_panel_helper_wraps_shell_runtime() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_card_shell_helpers import (" in text
    assert "render_app_suite_right_card_shell," in text
    assert "render_heavy_suite_right_card_shell," in text
    assert "from pneumo_solver_ui.ui_suite_editor_shell_helpers import (" in text
    assert "render_suite_empty_card_state," in text
    assert "render_suite_missing_card_state," in text
    assert "def render_app_suite_right_card_panel(" in text
    assert "def render_heavy_suite_right_card_panel(" in text
    assert 'if st.button("✅ Применить"' in text
    assert 'if st.button("Применить изменения"' in text
    assert 'st.success("Сохранено.")' in text
    assert 'set_flash_fn("success", "Тест обновлён.")' in text
    assert "render_app_suite_right_card_shell(" in text
    assert "render_heavy_suite_right_card_shell(" in text


def test_suite_card_panel_helper_uses_human_readable_labels_instead_of_raw_codes() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "С какой стадии тест начинает участвовать в оптимизации по стадиям." in text
    assert "Нумерация начинается с 0" in text
    assert "Начальная скорость, м/с" in text
    assert "Расчётная длина проезда = скорость × длительность" in text
    assert "Авто: длительность = длина / скорость" in text
    assert "с защитой от деления на ноль" in text
    assert "Длительность теста будет вычислена автоматически" in text
    assert "Профиль дороги для сценария с дорожным профилем" in text
    assert "Амплитуда A задаёт полуразмах синусоиды" in text
    assert "полный размах между минимумом и максимумом" in text
    assert "Коэффициент формы" in text
    assert "Путь к CSV манёвра (ax/ay)" in text
    assert "Ровная дорога" in text
    assert "Что проверять в этом сценарии" in text
    assert "Порог или целевое значение" in text
    assert "Переопределения параметров в формате JSON (необязательно)" in text
    assert "Оптимизация учитывает только включённые ниже ограничения" in text
    assert "staged optimization" not in text
    assert "0-based" not in text
    assert "Скорость (vx0_м_с), м/с" not in text
    assert "Ровная (flat)" not in text
    assert "Авто: t_end = (длина / скорость)" not in text
    assert "max(начальная скорость, eps)" not in text
    assert "t_end будет вычислен автоматически" not in text
    assert "Профиль дороги для сценария WorldRoad" not in text
    assert "полный размах p-p = 2A" not in text
    assert "Высота h, м" not in text
    assert "Ширина w, м" not in text
    assert "Форма k" not in text
    assert "Путь к CSV манёвра ax/ay" not in text
    assert "Список целевых ограничений оптимизации" not in text
    assert "Целевое значение" not in text
    assert "Штраф оптимизации учитывает только" not in text
    assert "JSON с переопределениями параметров (необязательно)" not in text


def test_suite_editor_panel_helper_uses_suite_card_panels() -> None:
    text = EDITOR_PANEL_HELPER.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_suite_card_panel_helpers import (" in text
    assert "render_app_suite_right_card_panel," in text
    assert "render_heavy_suite_right_card_panel," in text
    assert "render_app_suite_right_card_panel(" in text
    assert "render_heavy_suite_right_card_panel(" in text


def test_entrypoints_no_longer_call_suite_card_panels_directly() -> None:
    app_text = APP.read_text(encoding="utf-8")
    heavy_text = HEAVY.read_text(encoding="utf-8")

    assert "render_app_suite_right_card_panel(" not in app_text
    assert "render_heavy_suite_right_card_panel(" not in heavy_text
