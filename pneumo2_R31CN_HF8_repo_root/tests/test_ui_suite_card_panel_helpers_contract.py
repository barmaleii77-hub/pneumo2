from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_suite_card_panel_helpers import (
    _normalize_suite_transport_fields,
    _resolve_suite_transport_mode,
    _resolve_suite_effective_t_end,
)


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_card_panel_helpers.py"
EDITOR_PANEL_HELPER = ROOT / "pneumo_solver_ui" / "ui_suite_editor_panel_helpers.py"
APP = ROOT / "pneumo_solver_ui" / "app.py"
HEAVY = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_suite_card_panel_helper_wraps_shell_runtime() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "def _normalize_saved_road_surface_spec(" in text
    assert "def _resolve_numeric_choice(" in text
    assert "def _load_penalty_target_specs_map(" in text
    assert "def _resolve_suite_transport_mode(" in text
    assert "def _normalize_suite_transport_fields(" in text
    assert "def _resolve_suite_effective_t_end(" in text
    assert "from pneumo_solver_ui.ui_suite_card_shell_helpers import (" in text
    assert "render_app_suite_right_card_shell," in text
    assert "render_heavy_suite_right_card_shell," in text
    assert "from pneumo_solver_ui.ui_suite_editor_shell_helpers import (" in text
    assert "format_suite_test_type_label," in text
    assert "render_suite_empty_card_state," in text
    assert "render_suite_missing_card_state," in text
    assert "def render_app_suite_right_card_panel(" in text
    assert "def render_heavy_suite_right_card_panel(" in text
    assert "format_func=format_suite_test_type_label" in text
    assert 'if st.button("✅ Применить"' in text
    assert 'if st.button("Применить изменения"' in text
    assert 'st.success("Сохранено.")' in text
    assert 'set_flash_fn("success", "Сценарий обновлён.")' in text
    assert "render_app_suite_right_card_shell(" in text
    assert "render_heavy_suite_right_card_shell(" in text


def test_suite_card_panel_helper_uses_human_readable_labels_instead_of_raw_codes() -> None:
    text = HELPER.read_text(encoding="utf-8")

    assert "Сценарий {sel_i + 1}" in text
    assert "Шаг интегрирования, с" in text
    assert "Своё значение шага, с" in text
    assert "Своя длительность, с" in text
    assert "current_type = str(st.session_state.get(type_key, typ) or typ)" in text
    assert "transport_mode = _resolve_suite_transport_mode(current_type)" in text
    assert "current_t_end = _resolve_numeric_choice(" in text
    assert "transport_fields = _normalize_suite_transport_fields(" in text
    assert "t_end_effective = _resolve_suite_effective_t_end(" in text
    assert "С какой стадии сценарий начинает участвовать в оптимизации по стадиям." in text
    assert "Нумерация начинается с 0" in text
    assert "Начальная скорость, м/с" in text
    assert "Продольное ускорение ax, м/с²" in text
    assert "Поперечное ускорение ay, м/с²" in text
    assert "Амплитуда A (полуразмах), м" in text
    assert "Частота f, Гц" in text
    assert "Угол, град" in text
    assert "##### Источник дороги и манёвра" in text
    assert "Путь к CSV дороги" in text
    assert "Профиль дороги будет прочитан из CSV-файла для этого сценария." in text
    assert "Манёвр и, при необходимости, дорога будут прочитаны из CSV-файлов." in text
    assert "Для этого типа сценария отдельные файлы дороги и манёвра не используются." in text
    assert "Тип поверхности" in text
    assert "Длина участка, м" in text
    assert 'if transport_mode == "worldroad":' in text
    assert 'elif transport_mode == "road_profile_csv":' in text
    assert 'elif transport_mode == "maneuver_csv":' in text
    assert 'elif transport_mode == "road_profile_csv":' in text
    assert 'elif transport_mode == "maneuver_csv":' in text
    assert "Расчётная длина проезда = скорость × длительность" in text
    assert "Авто: длительность = длина / скорость" in text
    assert "с защитой от деления на ноль" in text
    assert "Длительность сценария, с" in text
    assert "Длительность сценария будет вычислена автоматически" in text
    assert "Профиль дороги для сценария с дорожным профилем" in text
    assert "Амплитуда A задаёт полуразмах синусоиды" in text
    assert "полный размах между минимумом и максимумом" in text
    assert "Коэффициент формы" in text
    assert "Путь к CSV манёвра (ax/ay)" in text
    assert "Ровная дорога" in text
    assert "Что проверять в этом сценарии" in text
    assert "Что проверять и настраивать в этом сценарии" in text
    assert "Оптимизация учитывает только включённые ограничения" in text
    assert 'label = str(spec.get("label", key))' in text
    assert "Переопределения параметров (сценарий)" in text
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
    assert "С какой стадии тест начинает участвовать" not in text
    assert "Длительность теста, с" not in text
    assert "Длительность теста будет вычислена автоматически" not in text
    assert "test_{sel_i}" not in text
    assert "Шаг dt (с)" not in text
    assert "Длительность t_end (с)" not in text
    assert "ax (м/с²)" not in text
    assert "ay (м/с²)" not in text
    assert "A (м)" not in text
    assert "f (Гц)" not in text
    assert "Угол (град)" not in text
    assert "Порог, уставки и расширенные параметры" not in text
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
    assert 'f"Порог для {key}"' not in text


def test_suite_transport_mode_detects_builtin_and_csv_variants() -> None:
    assert _resolve_suite_transport_mode("worldroad") == "worldroad"
    assert _resolve_suite_transport_mode("road_profile_csv") == "road_profile_csv"
    assert _resolve_suite_transport_mode("maneuver_csv") == "maneuver_csv"
    assert _resolve_suite_transport_mode("инерция_крен") == "builtin"


def test_suite_transport_fields_are_normalized_by_scenario_type() -> None:
    worldroad = _normalize_suite_transport_fields(
        test_type="worldroad",
        road_csv="road.csv",
        axay_csv="maneuver.csv",
        road_surface='{"type":"sine_x"}',
        road_len_m=123.0,
        auto_t_end_from_len=True,
    )
    assert worldroad == {
        "road_csv": "",
        "axay_csv": "",
        "road_surface": '{"type":"sine_x"}',
        "road_len_m": 123.0,
        "auto_t_end_from_len": True,
    }

    road_profile = _normalize_suite_transport_fields(
        test_type="road_profile_csv",
        road_csv="road.csv",
        axay_csv="maneuver.csv",
        road_surface='{"type":"ridge_x"}',
        road_len_m=456.0,
        auto_t_end_from_len=True,
    )
    assert road_profile == {
        "road_csv": "road.csv",
        "axay_csv": "",
        "road_surface": "flat",
        "road_len_m": 456.0,
        "auto_t_end_from_len": False,
    }

    maneuver = _normalize_suite_transport_fields(
        test_type="maneuver_csv",
        road_csv="road.csv",
        axay_csv="maneuver.csv",
        road_surface='{"type":"ridge_x"}',
        road_len_m=789.0,
        auto_t_end_from_len=True,
    )
    assert maneuver == {
        "road_csv": "road.csv",
        "axay_csv": "maneuver.csv",
        "road_surface": "flat",
        "road_len_m": 789.0,
        "auto_t_end_from_len": False,
    }

    builtin = _normalize_suite_transport_fields(
        test_type="инерция_крен",
        road_csv="road.csv",
        axay_csv="maneuver.csv",
        road_surface='{"type":"ridge_x"}',
        road_len_m=333.0,
        auto_t_end_from_len=True,
    )
    assert builtin == {
        "road_csv": "",
        "axay_csv": "",
        "road_surface": "flat",
        "road_len_m": 333.0,
        "auto_t_end_from_len": False,
    }


def test_effective_t_end_uses_auto_length_only_for_worldroad() -> None:
    assert _resolve_suite_effective_t_end(
        test_type="worldroad",
        t_end=3.0,
        road_len_m=120.0,
        speed_mps=10.0,
        auto_t_end_from_len=True,
    ) == 12.0
    assert _resolve_suite_effective_t_end(
        test_type="road_profile_csv",
        t_end=3.0,
        road_len_m=120.0,
        speed_mps=10.0,
        auto_t_end_from_len=True,
    ) == 3.0
    assert _resolve_suite_effective_t_end(
        test_type="maneuver_csv",
        t_end=4.5,
        road_len_m=120.0,
        speed_mps=10.0,
        auto_t_end_from_len=True,
    ) == 4.5


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
