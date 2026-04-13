from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_QUICK_PRESET_OPTIONS,
    DESKTOP_RUN_PRESET_OPTIONS,
    apply_desktop_quick_preset,
    apply_desktop_run_preset,
    DESKTOP_PREVIEW_SURFACE_OPTIONS,
    build_desktop_preview_surface,
    build_desktop_profile_diff,
    build_desktop_section_field_search_items,
    build_desktop_section_change_cards,
    build_desktop_section_issue_cards,
    build_desktop_section_summary_cards,
    DESKTOP_INPUT_SECTIONS,
    desktop_field_values_match,
    find_desktop_field_matches,
    desktop_section_status_label,
    desktop_profile_dir_path,
    desktop_profile_display_name,
    desktop_runs_dir_path,
    desktop_run_summary_path,
    desktop_profile_path,
    desktop_snapshot_dir_path,
    desktop_snapshot_display_name,
    desktop_snapshot_path,
    default_base_json_path,
    default_ranges_json_path,
    default_suite_json_path,
    default_working_copy_path,
    describe_desktop_run_mode,
    evaluate_desktop_section_readiness,
    field_spec_map,
    list_desktop_profile_paths,
    list_desktop_run_dirs,
    list_desktop_snapshot_paths,
    load_desktop_run_summary,
    preview_surface_label,
    quick_preset_description,
    quick_preset_label,
    run_preset_description,
    run_preset_label,
    sanitize_desktop_profile_name,
)
from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_input_model_exposes_main_operator_sections() -> None:
    titles = [section.title for section in DESKTOP_INPUT_SECTIONS]
    assert "Геометрия" in titles
    assert "Пневматика" in titles
    assert "Механика" in titles
    assert "Статическая настройка" in titles
    assert "Компоненты" in titles
    assert "Справочные данные" in titles

    specs = field_spec_map()
    assert specs["база"].unit_label == "м"
    assert specs["начальное_давление_Ресивер2"].unit_label == "кПа (абс.)"
    assert specs["corner_loads_mode"].control == "choice"
    assert "adiabatic" in specs["термодинамика"].choices
    assert "table" in specs["механика_кинематика"].choices
    assert dict(specs["corner_loads_mode"].choice_labels)["cg"] == "Через центр тяжести"
    assert dict(specs["механика_кинематика"].choice_labels)["table"] == "По табличной характеристике"
    assert specs["использовать_паспорт_компонентов"].control == "bool"
    assert specs["газ_модель_теплоемкости"].control == "choice"
    assert specs["static_trim_enable"].control == "bool"


def test_desktop_input_model_requires_units_tooltips_and_help_for_user_fields() -> None:
    for key, spec in field_spec_map().items():
        assert str(spec.effective_tooltip_text or "").strip(), key
        assert str(spec.effective_help_title or "").strip(), key
        assert str(spec.effective_help_body or "").strip(), key
        if spec.control not in {"bool", "choice"}:
            assert str(spec.unit_label or "").strip(), key


def test_desktop_input_model_exposes_graphic_context_for_core_fields() -> None:
    specs = field_spec_map()

    assert specs["база"].effective_graphic_context == "frame_dimensions"
    assert specs["колея"].effective_graphic_context == "track"
    assert specs["ход_штока"].effective_graphic_context == "stroke"
    assert specs["начальное_давление_Ресивер1"].effective_graphic_context == "pressure"
    assert specs["объём_ресивера_1"].effective_graphic_context == "volume"
    assert specs["масса_рамы"].effective_graphic_context == "mass_sprung"
    assert specs["zero_pose_target_stroke_frac"].effective_graphic_context == "trim_target"
    assert specs["механика_кинематика"].effective_graphic_context == "kinematics"
    assert specs["температура_окр_К"].effective_graphic_context == "temperature"


def test_desktop_input_model_uses_safe_paths_inside_repo_workspace() -> None:
    default_base = default_base_json_path()
    default_ranges = default_ranges_json_path()
    default_suite = default_suite_json_path()
    working_copy = default_working_copy_path()
    profile_dir = desktop_profile_dir_path()
    profile_path = desktop_profile_path("Мой профиль: demo/1")
    snapshot_dir = desktop_snapshot_dir_path()
    snapshot_path = desktop_snapshot_path("Перед запуском: rough/demo", stamp="20260412_101500")
    runs_dir = desktop_runs_dir_path()
    run_summary = desktop_run_summary_path(runs_dir / "desktop_input_run_20260412_101500")

    assert default_base.name == "default_base.json"
    assert default_ranges.name == "default_ranges.json"
    assert default_suite.name == "default_suite.json"
    assert "workspace" in str(working_copy)
    assert working_copy.name == "desktop_input_base.json"
    assert "workspace" in str(profile_dir)
    assert profile_dir.name == "desktop_input_profiles"
    assert profile_path.name.endswith(".json")
    assert ":" not in profile_path.name
    assert "/" not in profile_path.name
    assert "workspace" in str(snapshot_dir)
    assert snapshot_dir.name == "desktop_input_snapshots"
    assert snapshot_path.name == "20260412_101500__Перед_запуском_rough_demo.json"
    assert "workspace" in str(runs_dir)
    assert runs_dir.name == "desktop_runs"
    assert run_summary.name == "run_summary.json"


def test_desktop_input_model_exposes_profile_helpers() -> None:
    assert sanitize_desktop_profile_name(" Мой профиль: city/rough ") == "Мой_профиль_city_rough"
    assert desktop_profile_display_name(Path("city_rough.json")) == "city rough"
    assert isinstance(list_desktop_profile_paths(), list)
    assert desktop_snapshot_display_name(Path("20260412_101500__city_rough.json")) == "20260412_101500 · city rough"
    assert isinstance(list_desktop_snapshot_paths(), list)
    assert isinstance(list_desktop_run_dirs(), list)
    assert desktop_run_summary_path(Path("workspace/desktop_runs/demo_run")).name == "run_summary.json"


def test_desktop_run_summary_loader_reads_json_object() -> None:
    tmp = ROOT / "workspace" / "tmp_desktop_input_test_run"
    tmp.mkdir(parents=True, exist_ok=True)
    summary_path = tmp / "run_summary.json"
    summary_path.write_text('{"scenario_name": "demo", "record_full": true}', encoding="utf-8")
    try:
        summary = load_desktop_run_summary(tmp)
        assert summary["scenario_name"] == "demo"
        assert summary["record_full"] is True
    finally:
        if summary_path.exists():
            summary_path.unlink()
        if tmp.exists():
            tmp.rmdir()


def test_desktop_input_model_exposes_operator_friendly_preview_profiles() -> None:
    labels = dict(DESKTOP_PREVIEW_SURFACE_OPTIONS)
    assert labels["flat"] == "Ровная дорога"
    assert labels["sine_x"] == "Синус вдоль"
    assert labels["bump"] == "Бугор"
    assert labels["ridge_cosine_bump"] == "Косинусный бугор"
    assert preview_surface_label("ridge_cosine_bump") == "Косинусный бугор"

    assert build_desktop_preview_surface(surface_type="flat") == "flat"
    assert build_desktop_preview_surface(
        surface_type="sine_x",
        amplitude_m=0.03,
        wavelength_or_width_m=2.5,
    ) == {
        "type": "sine_x",
        "A": 0.03,
        "wavelength": 2.5,
    }
    assert build_desktop_preview_surface(
        surface_type="bump",
        amplitude_m=0.04,
        wavelength_or_width_m=0.6,
        start_m=7.5,
    ) == {
        "type": "bump",
        "h": 0.04,
        "w": 0.6,
        "x0": 7.5,
    }
    assert build_desktop_preview_surface(
        surface_type="ridge_cosine_bump",
        amplitude_m=0.05,
        wavelength_or_width_m=0.8,
        start_m=6.0,
        angle_deg=25.0,
        shape_k=2.0,
    ) == {
        "type": "ridge_cosine_bump",
        "h": 0.05,
        "w": 0.8,
        "u0": 6.0,
        "angle_deg": 25.0,
        "k": 2.0,
    }


def test_desktop_profile_diff_helpers_detect_only_meaningful_changes() -> None:
    specs = field_spec_map()
    base = {
        "база": 2.4,
        "стабилизатор_вкл": True,
        "термодинамика": "thermal",
        "макс_число_внутренних_шагов_на_dt": 8000,
    }
    same = {
        "база": 2.404,
        "стабилизатор_вкл": 1,
        "термодинамика": "thermal",
        "макс_число_внутренних_шагов_на_dt": 8000.4,
    }
    changed = dict(same)
    changed["база"] = 2.46
    changed["термодинамика"] = "isothermal"

    assert desktop_field_values_match(specs["база"], base["база"], same["база"])
    assert desktop_field_values_match(
        specs["стабилизатор_вкл"],
        base["стабилизатор_вкл"],
        same["стабилизатор_вкл"],
    )
    assert not desktop_field_values_match(specs["база"], base["база"], changed["база"])
    assert not desktop_field_values_match(
        specs["термодинамика"],
        base["термодинамика"],
        changed["термодинамика"],
    )

    diffs = build_desktop_profile_diff(changed, base)
    diff_keys = {item["key"] for item in diffs}
    assert "база" in diff_keys
    assert "термодинамика" in diff_keys
    assert "стабилизатор_вкл" not in diff_keys
    assert "макс_число_внутренних_шагов_на_dt" not in diff_keys


def test_desktop_quick_presets_modify_expected_parameter_groups() -> None:
    labels = {key: label for key, label, _desc in DESKTOP_QUICK_PRESET_OPTIONS}
    assert labels["soft_ride"] == "Подвеска мягче"
    assert labels["firm_ride"] == "Подвеска жёстче"
    assert labels["pressure_up"] == "Выше давление"
    assert labels["draft_calc"] == "Черновой расчёт"
    assert quick_preset_label("precise_calc") == "Точнее интегрирование"
    assert "пневмосистеме" in quick_preset_description("pressure_down")

    base = {
        "пружина_масштаб": 1.0,
        "жёсткость_шины": 200000.0,
        "демпфирование_шины": 4000.0,
        "стабилизатор_перед_жесткость_Н_м": 120000.0,
        "стабилизатор_зад_жесткость_Н_м": 100000.0,
        "начальное_давление_Ресивер1": 500000.0,
        "начальное_давление_Ресивер2": 520000.0,
        "начальное_давление_Ресивер3": 540000.0,
        "начальное_давление_аккумулятора": 560000.0,
        "макс_шаг_интегрирования_с": 0.002,
        "макс_число_внутренних_шагов_на_dt": 8000,
    }

    softer, softer_keys = apply_desktop_quick_preset(base, "soft_ride")
    firmer, firmer_keys = apply_desktop_quick_preset(base, "firm_ride")
    pressure_up, pressure_up_keys = apply_desktop_quick_preset(base, "pressure_up")
    draft_calc, draft_keys = apply_desktop_quick_preset(base, "draft_calc")

    assert softer["пружина_масштаб"] < base["пружина_масштаб"]
    assert softer["жёсткость_шины"] < base["жёсткость_шины"]
    assert "стабилизатор_перед_жесткость_Н_м" in softer_keys
    assert firmer["пружина_масштаб"] > base["пружина_масштаб"]
    assert firmer["жёсткость_шины"] > base["жёсткость_шины"]
    assert pressure_up["начальное_давление_Ресивер1"] > base["начальное_давление_Ресивер1"]
    assert "начальное_давление_аккумулятора" in pressure_up_keys
    assert draft_calc["макс_шаг_интегрирования_с"] > base["макс_шаг_интегрирования_с"]
    assert draft_calc["макс_число_внутренних_шагов_на_dt"] < base["макс_число_внутренних_шагов_на_dt"]
    assert "макс_число_внутренних_шагов_на_dt" in draft_keys


def test_desktop_run_presets_modify_expected_run_settings() -> None:
    labels = {key: label for key, label, _desc in DESKTOP_RUN_PRESET_OPTIONS}
    assert labels["sanity_check"] == "Быстрый sanity-check"
    assert labels["draft_run"] == "Черновой запуск"
    assert run_preset_label("precise_run") == "Точнее"
    assert "расширенного лога" in run_preset_description("sanity_check")

    base = {
        "scenario_key": "worldroad",
        "dt": 0.003,
        "t_end": 1.6,
        "record_full": True,
    }

    sanity, sanity_keys = apply_desktop_run_preset(base, "sanity_check", scenario_key="worldroad")
    draft, draft_keys = apply_desktop_run_preset(base, "draft_run", scenario_key="roll")
    precise, precise_keys = apply_desktop_run_preset(base, "precise_run", scenario_key="worldroad")

    assert sanity["dt"] > base["dt"]
    assert sanity["t_end"] < base["t_end"]
    assert sanity["record_full"] is False
    assert "record_full" in sanity_keys
    assert draft["t_end"] == 1.8
    assert "t_end" in draft_keys
    assert precise["dt"] < base["dt"]
    assert precise["t_end"] == 2.4
    assert precise["record_full"] is True


def test_desktop_run_mode_summary_is_operator_friendly() -> None:
    fast = describe_desktop_run_mode({"dt": 0.006, "t_end": 0.9, "record_full": False})
    balanced = describe_desktop_run_mode({"dt": 0.003, "t_end": 1.8, "record_full": False})
    detailed = describe_desktop_run_mode({"dt": 0.0015, "t_end": 2.4, "record_full": True})

    assert fast["mode_key"] == "fast"
    assert fast["mode_label"] == "быстро"
    assert "Ожидаемый режим: быстро." in fast["summary"]
    assert fast["cost_label"] == "быстро и легко"
    assert "Цена запуска: быстро и легко." in fast["cost_summary"]
    assert fast["advice_label"] == "берите для первого sanity-check"
    assert "конфигурация в целом живая" in fast["advice_summary"]
    assert "Когда запускать: берите для первого sanity-check." in fast["usage_summary"]
    assert balanced["mode_key"] == "balanced"
    assert balanced["mode_label"] == "сбалансировано"
    assert "обычного рабочего прогона" in balanced["summary"]
    assert balanced["cost_label"] == "рабочий баланс"
    assert balanced["advice_label"] == "берите для основной работы"
    assert "Когда запускать: берите для основной работы." in balanced["usage_summary"]
    assert detailed["mode_key"] == "detailed"
    assert detailed["mode_label"] == "подробно"
    assert "расширенный лог включён" in detailed["summary"]
    assert detailed["cost_label"] == "дольше, но подробнее"
    assert "времени и данных потребуется больше" in detailed["cost_summary"]
    assert detailed["advice_label"] == "берите для финальной проверки"
    assert "разбором сложного поведения" in detailed["advice_summary"]
    assert "Когда запускать: берите для финальной проверки." in detailed["usage_summary"]


def test_desktop_field_search_helpers_find_operator_friendly_matches() -> None:
    pressure_matches = find_desktop_field_matches("давление", limit=6)
    pressure_keys = {row["key"] for row in pressure_matches}
    assert "начальное_давление_Ресивер1" in pressure_keys
    assert any("Пневматика" == row["section_title"] for row in pressure_matches)
    assert all("—" in row["display"] for row in pressure_matches)

    trim_matches = find_desktop_field_matches("статическая посадка", limit=6)
    trim_keys = {row["key"] for row in trim_matches}
    assert "static_trim_enable" in trim_keys
    assert "static_trim_force" in trim_keys
    assert any("Статическая настройка" == row["section_title"] for row in trim_matches)

    passport_matches = find_desktop_field_matches("паспорт компонентов", limit=6)
    passport_keys = {row["key"] for row in passport_matches}
    assert "использовать_паспорт_компонентов" in passport_keys
    assert any("Компоненты" == row["section_title"] for row in passport_matches)

    assert find_desktop_field_matches("несуществующий_параметр", limit=6) == []


def test_desktop_section_field_search_items_follow_cluster_structure() -> None:
    pneumatics_items = build_desktop_section_field_search_items("Пневматика")
    pneumatics_keys = {row["key"] for row in pneumatics_items}
    assert "объём_ресивера_1" in pneumatics_keys
    assert "начальное_давление_Ресивер1" in pneumatics_keys
    assert all(row["section_title"] == "Пневматика" for row in pneumatics_items)
    assert all("Пневматика" in row["display"] for row in pneumatics_items)

    static_items = build_desktop_section_field_search_items("Статическая настройка")
    static_keys = {row["key"] for row in static_items}
    assert "static_trim_enable" in static_keys
    assert "corner_loads_mode" in static_keys

    assert build_desktop_section_field_search_items("Несуществующий кластер") == []


def test_desktop_input_editor_exposes_cluster_search_shortcuts() -> None:
    editor_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "section_search_buttons" in editor_src
    assert "_field_search_tracks_current_section" in editor_src
    assert "_show_current_section_attention_fields_in_search" in editor_src
    assert "_show_current_section_changed_fields_in_search" in editor_src
    assert "_show_section_search_from_summary" in editor_src
    assert "Показать параметры кластера" in editor_src
    assert "Показать замечания кластера:" in editor_src
    assert "Показать изменения кластера:" in editor_src
    assert "Замечания текущего кластера «" in editor_src
    assert "Изменения текущего кластера «" in editor_src
    assert "current_section_attention" in editor_src
    assert "current_section_changed" in editor_src


def test_desktop_section_readiness_flags_inconsistent_inputs() -> None:
    payload = {
        "база": 2.5,
        "колея": 1.6,
        "радиус_колеса_м": 0.35,
        "ход_штока": 0.18,
        "объём_ресивера_1": 0.002,
        "объём_ресивера_2": 0.002,
        "объём_ресивера_3": 0.002,
        "объём_аккумулятора": 0.002,
        "начальное_давление_Ресивер1": 500000.0,
        "начальное_давление_Ресивер2": 520000.0,
        "начальное_давление_Ресивер3": 540000.0,
        "начальное_давление_аккумулятора": 560000.0,
        "диаметр_поршня_Ц1": 0.03,
        "диаметр_штока_Ц1": 0.035,
        "диаметр_поршня_Ц2": 0.04,
        "диаметр_штока_Ц2": 0.02,
        "масса_рамы": 1200.0,
        "масса_неподрессоренная_на_угол": 60.0,
        "жёсткость_шины": 200000.0,
        "демпфирование_шины": 3500.0,
        "стабилизатор_вкл": True,
        "стабилизатор_перед_жесткость_Н_м": 0.0,
        "стабилизатор_зад_жесткость_Н_м": 0.0,
        "макс_шаг_интегрирования_с": 0.002,
        "макс_число_внутренних_шагов_на_dt": 900,
        "static_trim_enable": False,
        "static_trim_force": True,
        "static_trim_pneumo_mode": "pressure",
        "термодинамика": "",
        "газ_модель_теплоемкости": "",
        "механика_кинематика": "",
        "колесо_координата": "invalid",
    }

    rows = evaluate_desktop_section_readiness(payload)
    rows_by_title = {row["title"]: row for row in rows}

    assert desktop_section_status_label("ok") == "в норме"
    assert desktop_section_status_label("warn") == "требует внимания"
    assert rows_by_title["Геометрия"]["status"] == "ok"
    assert rows_by_title["Пневматика"]["status"] == "warn"
    assert "Ц1: шток не должен быть больше поршня" in rows_by_title["Пневматика"]["issues"]
    assert rows_by_title["Механика"]["status"] == "warn"
    assert "включён стабилизатор без жёсткости" in rows_by_title["Механика"]["issues"]
    assert rows_by_title["Статическая настройка"]["status"] == "warn"
    assert "форсированный static trim без включённого поиска посадки" in rows_by_title["Статическая настройка"]["issues"]
    assert rows_by_title["Компоненты"]["status"] == "warn"
    assert "кинематика подвески" in rows_by_title["Компоненты"]["issues"]
    assert "режим колесо_координата" in rows_by_title["Компоненты"]["issues"]
    assert rows_by_title["Справочные данные"]["status"] == "warn"
    assert "режим термодинамики" in rows_by_title["Справочные данные"]["issues"]
    assert "лимит внутренних шагов" in rows_by_title["Справочные данные"]["issues"]


def test_desktop_section_summary_cards_show_live_cluster_context() -> None:
    payload = {
        "база": 1.5,
        "колея": 1.0,
        "ход_штока": 0.32,
        "wheel_width_m": 0.22,
        "начальное_давление_Ресивер1": 101325.0,
        "начальное_давление_Ресивер2": 405300.0,
        "начальное_давление_Ресивер3": 405300.0,
        "начальное_давление_аккумулятора": 405300.0,
        "объём_ресивера_1": 0.001,
        "объём_ресивера_2": 0.002,
        "объём_ресивера_3": 0.003,
        "объём_аккумулятора": 0.003,
        "масса_рамы": 600.0,
        "масса_неподрессоренная_на_угол": 15.0,
        "жёсткость_шины": 200000.0,
        "пружина_длина_свободная_м": 0.65,
        "vx0_м_с": 0.0,
        "cg_x_м": 0.0,
        "cg_y_м": 0.0,
        "corner_loads_mode": "cg",
        "static_trim_enable": True,
        "static_trim_pneumo_mode": "pressure",
        "механика_кинематика": "dw2d",
        "колесо_координата": "center",
        "использовать_паспорт_компонентов": True,
        "enforce_camozzi_only": True,
        "пружина_по_цилиндру": "C1",
        "термодинамика": "thermal",
        "газ_модель_теплоемкости": "constant",
        "T_AIR_К": 293.15,
        "температура_окр_К": 293.15,
        "макс_шаг_интегрирования_с": 0.0003,
        "autoverif_enable": True,
        "mechanics_selfcheck": True,
        "пружина_запас_до_coil_bind_минимум_м": 0.0,
    }

    cards = build_desktop_section_summary_cards(payload)
    cards_by_title = {card["title"]: card for card in cards}

    assert set(cards_by_title) >= {
        "Геометрия",
        "Пневматика",
        "Механика",
        "Статическая настройка",
        "Компоненты",
        "Справочные данные",
    }
    assert "ход 320 мм" in cards_by_title["Геометрия"]["headline"]
    assert "Р1 101 кПа" in cards_by_title["Пневматика"]["headline"]
    assert "рама 600 кг" in cards_by_title["Механика"]["headline"].lower()
    assert "corner loads cg" in cards_by_title["Статическая настройка"]["headline"]
    assert "Camozzi-only да" in cards_by_title["Компоненты"]["headline"]
    assert "Термо thermal / constant" in cards_by_title["Справочные данные"]["headline"]
    assert cards_by_title["Компоненты"]["status"] == "ok"
    assert cards_by_title["Компоненты"]["focus_key"] == ""


def test_desktop_section_change_cards_group_live_edits_by_cluster() -> None:
    reference_payload = {
        "база": 1.0,
        "колея": 1.0,
        "vx0_м_с": 0.0,
        "термодинамика": "thermal",
    }
    current_payload = dict(reference_payload)
    current_payload.update(
        {
            "база": 1.7,
            "колея": 1.3,
            "vx0_м_с": 2.5,
            "термодинамика": "adiabatic",
        }
    )

    cards = build_desktop_section_change_cards(current_payload, reference_payload)
    cards_by_title = {card["title"]: card for card in cards}

    assert cards_by_title["Геометрия"]["changed_count"] == 2
    assert "Колёсная база" in cards_by_title["Геометрия"]["changed_labels"]
    assert "Колея" in cards_by_title["Геометрия"]["changed_labels"]
    assert "2 параметра" in str(cards_by_title["Геометрия"]["summary"])
    assert cards_by_title["Геометрия"]["focus_key"] == "база"
    assert cards_by_title["Геометрия"]["focus_label"] == "Колёсная база"
    assert cards_by_title["Статическая настройка"]["changed_count"] == 1
    assert cards_by_title["Статическая настройка"]["focus_key"] == "vx0_м_с"
    assert cards_by_title["Справочные данные"]["changed_count"] == 1
    assert cards_by_title["Пневматика"]["status"] == "clean"
    assert cards_by_title["Пневматика"]["summary"] == "без изменений"
    assert cards_by_title["Пневматика"]["focus_key"] == ""


def test_desktop_section_issue_cards_group_live_issues_by_cluster() -> None:
    payload = {
        "объём_ресивера_1": 0.001,
        "объём_ресивера_2": 0.002,
        "объём_ресивера_3": 0.003,
        "объём_аккумулятора": 0.004,
        "диаметр_поршня_Ц1": 0.04,
        "диаметр_штока_Ц1": 0.05,
        "масса_рамы": 1200.0,
        "масса_неподрессоренная_на_угол": 60.0,
        "жёсткость_шины": 200000.0,
        "демпфирование_шины": 3500.0,
        "стабилизатор_вкл": True,
        "стабилизатор_перед_жесткость_Н_м": 0.0,
        "стабилизатор_зад_жесткость_Н_м": 0.0,
        "макс_шаг_интегрирования_с": 0.002,
        "макс_число_внутренних_шагов_на_dt": 900,
        "static_trim_enable": False,
        "static_trim_force": True,
        "static_trim_pneumo_mode": "pressure",
        "термодинамика": "",
        "газ_модель_теплоемкости": "",
        "механика_кинематика": "",
        "колесо_координата": "invalid",
    }

    cards = build_desktop_section_issue_cards(payload)
    cards_by_title = {card["title"]: card for card in cards}

    assert cards_by_title["Геометрия"]["issue_count"] == 0
    assert cards_by_title["Пневматика"]["issue_count"] == 1
    assert cards_by_title["Пневматика"]["focus_key"] == "диаметр_штока_Ц1"
    assert "Ц1" in str(cards_by_title["Пневматика"]["focus_label"])
    assert cards_by_title["Механика"]["issue_count"] == 1
    assert cards_by_title["Статическая настройка"]["issue_count"] == 1
    assert cards_by_title["Компоненты"]["issue_count"] == 2
    assert "Кинематика подвески" in cards_by_title["Компоненты"]["issue_labels"]
    assert "Режим колесо_координата" in cards_by_title["Компоненты"]["issue_labels"]
    assert cards_by_title["Справочные данные"]["issue_count"] == 3
    assert "Режим термодинамики" in cards_by_title["Справочные данные"]["issue_labels"]
    assert "Модель теплоёмкости" in cards_by_title["Справочные данные"]["issue_labels"]
    assert "Лимит внутренних шагов" in cards_by_title["Справочные данные"]["issue_labels"]
    assert "замечани" in str(cards_by_title["Справочные данные"]["summary"]).lower()


def test_desktop_section_summary_cards_expose_first_issue_focus_targets() -> None:
    payload = {
        "база": 0.0,
        "начальное_давление_Ресивер1": 0.0,
        "масса_рамы": 0.0,
        "vx0_м_с": -0.1,
        "использовать_паспорт_компонентов": False,
        "enforce_camozzi_only": True,
        "термодинамика": "unsupported_mode",
    }

    cards = build_desktop_section_summary_cards(payload)
    cards_by_title = {card["title"]: card for card in cards}

    assert cards_by_title["Геометрия"]["focus_key"] == "база"
    assert cards_by_title["Пневматика"]["focus_key"] == "начальное_давление_Ресивер1"
    assert cards_by_title["Механика"]["focus_key"] == "масса_рамы"
    assert cards_by_title["Статическая настройка"]["focus_key"] == "vx0_м_с"
    assert cards_by_title["Компоненты"]["focus_key"] == "использовать_паспорт_компонентов"
    assert cards_by_title["Справочные данные"]["focus_key"] == "термодинамика"
    assert "Camozzi-only" in str(cards_by_title["Компоненты"]["focus_reason"])
    assert "термодинамики" in str(cards_by_title["Справочные данные"]["focus_reason"]).lower()


def test_desktop_input_editor_is_wired_into_desktop_control_center() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_control_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    editor_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    run_setup_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    run_setup_model_src = (ROOT / "pneumo_solver_ui" / "desktop_run_setup_model.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    run_setup_runtime_src = (ROOT / "pneumo_solver_ui" / "desktop_run_setup_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    single_run_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_single_run.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    launcher_items = build_desktop_launch_catalog(include_mnemo=False)
    launcher_modules = {item.module for item in launcher_items}
    launcher_titles = {item.title for item in launcher_items}

    assert "build_desktop_launch_catalog(include_mnemo=False)" in src
    assert "pneumo_solver_ui.tools.desktop_input_editor" in launcher_modules
    assert "Данные машины" in launcher_titles
    assert "default_base.json" in editor_src
    assert "Сохранить рабочую копию" in editor_src
    assert "Рабочие профили" in editor_src
    assert 'profile_details_notebook.add(snapshots, text="Снимки")' in editor_src
    assert "Сохранить профиль" in editor_src
    assert "Загрузить профиль" in editor_src
    assert "Удалить профиль" in editor_src
    assert "Автоматически сохранять снимок перед запуском" in editor_src
    assert "Сохранить снимок" in editor_src
    assert "Загрузить снимок" in editor_src
    assert "Открыть папку снимков" in editor_src
    assert "Текущая рабочая точка" in editor_src
    assert "Источник параметров:" in editor_src
    assert "Активный профиль:" in editor_src
    assert "Последний снимок:" in editor_src
    assert "Сравнение с профилем:" in editor_src
    assert "Автоснимок перед запуском:" in editor_src
    assert "Имя профиля для рабочей точки" in editor_src
    assert "Сохранить рабочую точку как профиль" in editor_src
    assert "active_profile_path" in editor_src
    assert "active_snapshot_path" in editor_src
    assert "run_context_var" in editor_src
    assert "_refresh_run_context_summary" in editor_src
    assert "_suggest_run_context_profile_name" in editor_src
    assert "_save_profile_payload" in editor_src
    assert "_save_run_context_profile" in editor_src
    assert "[run-context]" in editor_src
    assert "_save_snapshot" in editor_src
    assert "_save_named_snapshot" in editor_src
    assert "_load_selected_snapshot" in editor_src
    assert "_autosave_snapshot_before_run" in editor_src
    assert "[snapshot]" in editor_src
    assert 'self._autosave_snapshot_before_run("quick_preview")' in editor_src
    assert 'self._autosave_snapshot_before_run("detail_run")' in editor_src
    assert "Сравнить с текущим" in editor_src
    assert "Сбросить сравнение" in editor_src
    assert "изменено параметров" in editor_src
    assert "отличий нет" in editor_src
    assert "· изменено" in editor_src
    assert 'profile_details_notebook.add(diff_frame, text="Сравнение")' in editor_src
    assert 'text="Параметр"' in editor_src
    assert 'text="Текущее"' in editor_src
    assert 'text="Профиль"' in editor_src
    assert "Сравнение не активно или отличий нет" in editor_src
    assert "_refresh_profile_diff_tree" in editor_src
    assert "Сводка конфигурации перед запуском" in editor_src
    assert "Массы: рама" in editor_src
    assert "Давления на старте:" in editor_src
    assert "Подробный расчёт:" in editor_src
    assert "_refresh_config_summary" in editor_src
    assert "Быстрые пресеты" in editor_src
    assert "quick_preset_hint_var" in editor_src
    assert "_apply_quick_preset" in editor_src
    assert "[quick-preset]" in editor_src
    assert "DESKTOP_QUICK_PRESET_OPTIONS" in editor_src
    assert "apply_desktop_quick_preset" in editor_src
    assert "quick_preset_label" in editor_src
    assert "quick_preset_description" in editor_src
    assert "История последних действий" in editor_src
    assert "Отменить последнее действие" in editor_src
    assert "_remember_safe_action" in editor_src
    assert "_undo_last_safe_action" in editor_src
    assert "_refresh_safe_action_history_view" in editor_src
    assert "[undo]" in editor_src
    assert "История пока пуста." in editor_src
    assert "Пошаговый маршрут настройки" in editor_src
    assert "self.section_titles" in editor_src
    assert 'text=f"{idx + 1}. {title}"' in editor_src
    assert "Назад" in editor_src
    assert "Далее" in editor_src
    assert "К следующему замечанию" in editor_src
    assert "К следующему изменению" in editor_src
    assert "desktop_section_status_label" in editor_src
    assert "evaluate_desktop_section_readiness" in editor_src
    assert "_configure_route_button_styles" in editor_src
    assert "_route_button_style_for_state" in editor_src
    assert "DesktopRouteCurrent.TButton" in editor_src
    assert "DesktopRouteWarn.TButton" in editor_src
    assert "DesktopRouteChanged.TButton" in editor_src
    assert "DesktopRouteCurrentWarnChanged.TButton" in editor_src
    assert "Готово шагов:" in editor_src
    assert "требуют внимания:" in editor_src
    assert "Шагов с замечаниями:" in editor_src
    assert "Изменено шагов:" in editor_src
    assert "Следующий шаг с замечанием:" in editor_src
    assert "Следующий изменённый шаг:" in editor_src
    assert "Замечаний шага:" in editor_src
    assert "Замечания шага:" in editor_src
    assert "Изменения шага:" in editor_src
    assert "Статус шага:" in editor_src
    assert "_build_section_route_state" in editor_src
    assert "_find_next_section_title" in editor_src
    assert "_refresh_section_route_summary" in editor_src
    assert "issue_badge" in editor_src
    assert "change_badge" in editor_src
    assert "_select_section_by_title" in editor_src
    assert "_go_prev_section" in editor_src
    assert "_go_next_section" in editor_src
    assert "_go_next_attention_section" in editor_src
    assert "_go_next_changed_section" in editor_src
    assert "не дублирует отдельные окна Animator, Compare Viewer или Mnemo" in editor_src
    assert "Сводка по текущему кластеру" in editor_src
    assert "section_summary_vars" in editor_src
    assert "section_issue_buttons" in editor_src
    assert "section_restore_buttons" in editor_src
    assert "section_search_buttons" in editor_src
    assert "section_change_focus_by_title" in editor_src
    assert "field_restore_buttons" in editor_src
    assert "source_reference_payload" in editor_src
    assert "source_reference_diffs_by_key" in editor_src
    assert "_refresh_source_reference_diff_state" in editor_src
    assert "_build_field_restore_button" in editor_src
    assert "_refresh_section_header_summaries" in editor_src
    assert "_jump_to_section_issue" in editor_src
    assert "_reset_section_to_source_reference" in editor_src
    assert "_restore_field_to_source_reference" in editor_src
    assert "Статус кластера:" in editor_src
    assert "Изменено от рабочей точки:" in editor_src
    assert "Первое изменение:" in editor_src
    assert "Перейти к замечанию" in editor_src
    assert "Перейти к изменению:" in editor_src
    assert "Вернуть к рабочей точке" in editor_src
    assert "Совпадает с рабочей точкой" in editor_src
    assert "Кластер в норме" in editor_src
    assert "· изменено от рабочей точки" in editor_src
    assert "· изменено и от рабочей точки" in editor_src
    assert 'text="К рабочей точке"' in editor_src
    assert 'text="Совпадает"' in editor_src
    assert "build_desktop_section_change_cards" in editor_src
    assert "build_desktop_section_issue_cards" in editor_src
    assert "Быстрый поиск по параметрам" in editor_src
    assert "Найти параметр" in editor_src
    assert "Подходящие параметры" in editor_src
    assert "Перейти к параметру" in editor_src
    assert "Очистить поиск" in editor_src
    assert "Показать изменённые" in editor_src
    assert "Показать замечания" in editor_src
    assert "Показать текущий кластер" in editor_src
    assert "Показать отличия с профилем" in editor_src
    assert "field_search_var" in editor_src
    assert "field_search_choice_var" in editor_src


def test_desktop_input_editor_promotes_classic_desktop_workspace_with_navigation_and_inspector() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_control_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    editor_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    run_setup_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_run_setup_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    run_setup_model_src = (ROOT / "pneumo_solver_ui" / "desktop_run_setup_model.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    run_setup_runtime_src = (ROOT / "pneumo_solver_ui" / "desktop_run_setup_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    single_run_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_single_run.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'text="Данные машины"' in editor_src
    assert 'ttk.Panedwindow(outer, orient="horizontal")' in editor_src
    assert 'text="Дерево разделов"' in editor_src
    assert "build_scrolled_treeview(" in editor_src
    assert 'self.section_tree.bind("<<TreeviewSelect>>", self._on_section_tree_selected)' in editor_src
    assert 'text="Свойства и связи"' in editor_src
    assert "self.graphics_panel = DesktopInputGraphicPanel(inspector_panel)" in editor_src
    assert "textvariable=self.inspector_unit_var" in editor_src
    assert 'text="?"' in editor_src
    assert 'text="Текущее поле"' in editor_src
    assert 'text="Связанные параметры"' in editor_src
    assert "inspector_related_tree" in editor_src
    assert "_refresh_inspector_related_fields" in editor_src
    assert "_jump_to_inspector_related_field" in editor_src
    assert "spec.display_choices or spec.choices" in editor_src
    assert "show_help_dialog(" in editor_src
    assert "field_search_summary_var" in editor_src
    assert "field_search_mode" in editor_src
    assert "_current_section_title" in editor_src
    assert "_field_search_tracks_current_section" in editor_src
    assert "_on_section_tab_changed" in editor_src
    assert "_apply_field_search_items" in editor_src
    assert "_field_search_badges_for_key" in editor_src
    assert "_build_field_search_item" in editor_src
    assert "_refresh_active_field_search_view" in editor_src
    assert "_refresh_field_search_results" in editor_src
    assert "_show_changed_fields_in_search" in editor_src
    assert "_show_attention_fields_in_search" in editor_src
    assert "_show_current_section_fields_in_search" in editor_src
    assert "_show_current_section_attention_fields_in_search" in editor_src
    assert "_show_current_section_changed_fields_in_search" in editor_src
    assert "_show_section_search_from_summary" in editor_src
    assert "_show_profile_diff_fields_in_search" in editor_src
    assert "_jump_to_selected_field" in editor_src
    assert "_jump_to_field" in editor_src
    assert "_scroll_to_field" in editor_src
    assert "build_desktop_section_field_search_items" in editor_src
    assert "find_desktop_field_matches" in editor_src
    assert "Найдено параметров:" in editor_src
    assert "Из них:" in editor_src
    assert "Изменено от рабочей точки:" in editor_src
    assert "Шагов с замечаниями:" in editor_src
    assert "Текущий кластер «" in editor_src
    assert "Замечания текущего кластера «" in editor_src
    assert "Изменения текущего кластера «" in editor_src
    assert "Сравнение с профилем выключено." in editor_src
    assert "Отличия с профилем «" in editor_src
    assert "изм. от рабочей точки" in editor_src
    assert "отличается от профиля" in editor_src
    assert "первое замечание секции" in editor_src
    assert "Показать параметры кластера" in editor_src
    assert "Показать замечания кластера:" in editor_src
    assert "Показать изменения кластера:" in editor_src
    assert "_soft_preflight_before_run" in editor_src
    assert "Перед запуском «" in editor_src
    assert "есть шаги, требующие внимания" in editor_src
    assert "Запустить всё равно?" in editor_src
    assert "[preflight]" in editor_src
    assert "_launch_with_optional_auto_check" in editor_src
    assert "_stored_selfcheck_allows_launch" in editor_src
    assert "_run_quick_preview(self, *, prechecked: bool = False)" in editor_src
    assert "_run_single_desktop_run(self, *, prechecked: bool = False)" in editor_src
    assert "run_auto_check_var" in editor_src
    assert "Auto-check перед «" in editor_src
    assert "последний сохранённый auto-check" in editor_src
    assert "persist_stdout_json=True" in editor_src
    assert "Вернуть раздел к значениям по умолчанию" in editor_src
    assert "_reset_section_to_defaults" in editor_src
    assert "[section-reset]" in editor_src
    assert "[section-restore]" in editor_src
    assert "[field-restore]" in editor_src
    assert "desktop_profile_dir_path" in editor_src
    assert "list_desktop_profile_paths" in editor_src
    assert "load_desktop_profile" in editor_src
    assert "save_desktop_profile" in editor_src
    assert "build_desktop_profile_diff" in editor_src
    assert "Проверить конфигурацию" in editor_src
    assert "Быстрый расчёт" in editor_src
    assert "Открыть отдельное окно настройки расчёта" in editor_src
    assert "_open_run_setup_center" in editor_src
    assert "DesktopRunSetupCenter" in editor_src
    assert "run_launch_summary_var" in editor_src
    assert "_refresh_run_launch_summary" in editor_src
    assert "Preview:" in editor_src
    assert "Run setup:" in editor_src
    assert "Подробный расчёт:" in editor_src
    assert "describe_selfcheck_gate_status" in editor_src
    assert "_current_selfcheck_subject_signature" in editor_src
    assert "_selfcheck_freshness_state" in editor_src
    assert "статическая настройка, компоненты и справочные данные" in editor_src
    assert "автоснимок включён" in run_setup_model_src
    assert 'artifacts_notebook = ttk.Notebook(actions)' in editor_src
    assert 'artifacts_notebook.add(latest_preview_frame, text="Preview")' in editor_src
    assert "latest_preview_summary_var" in editor_src
    assert "active_preview_report_path" in editor_src
    assert "active_preview_log_path" in editor_src
    assert "_refresh_latest_preview_summary" in editor_src
    assert "Обновить preview-сводку" in editor_src
    assert "Открыть preview_report.json" in editor_src
    assert "Открыть preview-лог" in editor_src
    assert "_open_latest_preview_report_json" in editor_src
    assert "_open_latest_preview_log" in editor_src
    assert "_open_run_setup_cache_root" in editor_src
    assert "_open_run_setup_log_root" in editor_src
    assert "_runtime_preview_report_path" in editor_src
    assert 'artifacts_notebook.add(latest_selfcheck_frame, text="Самопроверка")' in editor_src
    assert "latest_selfcheck_summary_var" in editor_src
    assert "active_selfcheck_report_path" in editor_src
    assert "active_selfcheck_log_path" in editor_src
    assert "_refresh_latest_selfcheck_summary" in editor_src
    assert "Обновить selfcheck-сводку" in editor_src
    assert "Открыть selfcheck_report.json" in editor_src
    assert "Открыть selfcheck-лог" in editor_src
    assert "_open_latest_selfcheck_report_json" in editor_src
    assert "_open_latest_selfcheck_log" in editor_src
    assert "_runtime_selfcheck_report_path" in editor_src
    assert 'artifacts_notebook.add(latest_run_frame, text="Подробный расчёт")' in editor_src
    assert "latest_run_summary_var" in editor_src
    assert "active_run_dir" in editor_src
    assert "active_run_summary_path" in editor_src
    assert "active_run_cache_dir" in editor_src
    assert "active_run_saved_files" in editor_src
    assert "_refresh_latest_run_summary" in editor_src
    assert "_current_latest_run_dir" in editor_src
    assert "_latest_run_cache_dir_from_summary" in editor_src
    assert "Обновить сводку" in editor_src
    assert "Открыть папку запуска" in editor_src
    assert "Открыть run_summary.json" in editor_src
    assert "Открыть run-лог" in editor_src
    assert "Открыть df_main.csv" in editor_src
    assert "Открыть NPZ bundle" in editor_src
    assert "Открыть cache entry" in editor_src
    assert "Открыть папку всех запусков" in editor_src
    assert "Подробные расчёты ещё не запускались." in editor_src
    assert "run_summary.json пока не найден." in editor_src
    assert "Папка артефактов:" in run_setup_model_src
    assert "Лог запуска:" in run_setup_model_src
    assert "_open_latest_run_dir" in editor_src
    assert "_open_latest_run_summary_json" in editor_src
    assert "_open_latest_run_log" in editor_src
    assert "_open_latest_run_cache_dir" in editor_src
    assert "_open_latest_df_main_csv" in editor_src
    assert "_open_latest_npz_bundle" in editor_src
    assert "_open_latest_saved_file" in editor_src
    assert "_open_desktop_runs_dir" in editor_src
    assert "_open_path" in editor_src
    assert "ui_subprocess_log" in editor_src
    assert "desktop_run_setup_cache_root" in editor_src
    assert "desktop_run_setup_log_root" in editor_src
    assert "desktop_runs_dir_path" in editor_src
    assert "desktop_run_summary_path" in editor_src
    assert "list_desktop_run_dirs" in editor_src
    assert "load_desktop_run_summary" in editor_src
    assert "run_preset_hint_var" in editor_src
    assert "run_mode_summary_var" in editor_src
    assert "run_mode_cost_var" in editor_src
    assert "run_mode_advice_var" in editor_src
    assert "run_mode_usage_var" in editor_src
    assert "_gather_run_settings_snapshot" in editor_src
    assert "_restore_run_settings_snapshot" in editor_src
    assert "_apply_run_preset" in editor_src
    assert "_refresh_run_mode_summary" in editor_src
    assert "[run-preset]" in editor_src
    assert "DESKTOP_RUN_PRESET_OPTIONS" in editor_src
    assert "apply_desktop_run_preset" in editor_src
    assert "describe_desktop_run_mode" in editor_src
    assert "run_preset_label" in editor_src
    assert "run_preset_description" in editor_src
    assert "Запустить подробный расчёт" in editor_src
    assert "pneumo_solver_ui.tools.desktop_single_run" in editor_src
    assert "--cache_policy" in editor_src
    assert "--run_profile" in editor_src
    assert "--export_npz" in editor_src
    assert "--no_export_csv" in editor_src
    assert "append_subprocess_log" in editor_src
    assert "write_json_report_from_stdout" in editor_src
    assert "DESKTOP_PREVIEW_SURFACE_OPTIONS" in editor_src
    assert "build_desktop_preview_surface" in editor_src
    assert "preview_surface_label" in editor_src
    assert "pneumo_solver_ui.opt_selfcheck_v1" in editor_src
    assert "pneumo_solver_ui.tools.worldroad_compile_only_demo" in editor_src
    assert "Профиль запуска" in run_setup_src
    assert "Профиль preview-дороги" in run_setup_src
    assert "Настройки запуска расчёта" in run_setup_src
    assert "Пресеты запуска" in run_setup_src
    assert "Cache, export и runtime policy" in run_setup_src
    assert "Будет запущено сейчас" in run_setup_src
    assert "Проверить и запустить" in run_setup_src
    assert "Запустить выбранный режим" in run_setup_src
    assert "_run_selected_profile_with_check" in run_setup_src
    assert "Рекомендуемая кнопка:" in run_setup_src
    assert "Целевой запуск:" in run_setup_src or "Обычный запуск" in run_setup_src
    assert "рекомендуется" in run_setup_src
    assert "недоступно" in run_setup_src
    assert "_refresh_launch_action_hint" in run_setup_src
    assert "prechecked=True" in run_setup_src
    assert "Последние runtime-артефакты" in run_setup_src
    assert "Последний baseline / preview" in run_setup_src
    assert "Последний auto-check / selfcheck" in run_setup_src
    assert "Последний detail / full" in run_setup_src
    assert "Открыть preview_report.json" in run_setup_src
    assert "Открыть preview-лог" in run_setup_src
    assert "Открыть selfcheck_report.json" in run_setup_src
    assert "Открыть selfcheck-лог" in run_setup_src
    assert "Открыть run_summary.json" in run_setup_src
    assert "Открыть run-лог" in run_setup_src
    assert "Открыть cache entry" in run_setup_src
    assert "Открыть cache runtime" in run_setup_src
    assert "Открыть папку логов" in run_setup_src
    assert "Обновить все сводки" in run_setup_src
    assert "_refresh_runtime_summaries" in run_setup_src
    assert "Экспортировать CSV-таблицы для detail/full" in run_setup_src
    assert "Экспортировать NPZ bundle для detail/full" in run_setup_src
    assert "Автоматический auto-check перед запуском" in run_setup_src
    assert "Писать subprocess-лог в файл" in run_setup_src
    assert "DESKTOP_RUN_PROFILE_OPTIONS" in run_setup_model_src
    assert "DESKTOP_RUN_CACHE_POLICY_OPTIONS" in run_setup_model_src
    assert "DESKTOP_RUN_RUNTIME_POLICY_OPTIONS" in run_setup_model_src
    assert "apply_run_setup_profile" in run_setup_model_src
    assert "describe_latest_run_summary" in run_setup_model_src
    assert "describe_latest_preview_summary" in run_setup_model_src
    assert "describe_run_launch_outlook" in run_setup_model_src
    assert "describe_run_launch_recommendation" in run_setup_model_src
    assert "describe_run_launch_route" in run_setup_model_src
    assert "describe_run_launch_target" in run_setup_model_src
    assert "recommended_run_launch_action" in run_setup_model_src
    assert "describe_plain_launch_availability" in run_setup_model_src
    assert "describe_selfcheck_freshness" in run_setup_model_src
    assert "describe_selfcheck_gate_status" in run_setup_model_src
    assert "describe_latest_selfcheck_summary" in run_setup_model_src
    assert "describe_run_setup_snapshot" in run_setup_model_src
    assert "artifact_state_line" in run_setup_model_src
    assert "Cache entry:" in run_setup_model_src
    assert "Последний auto-check:" in run_setup_model_src
    assert "Маршрут запуска:" in run_setup_model_src
    assert "Прогноз обычного запуска:" in run_setup_model_src
    assert "Рекомендация:" in run_setup_model_src
    assert "CSV таблиц=" in run_setup_model_src
    assert "JSON отчёт preview:" in run_setup_model_src
    assert "Лог preview:" in run_setup_model_src
    assert "JSON отчёт selfcheck:" in run_setup_model_src
    assert "Лог auto-check:" in run_setup_model_src
    assert '"baseline"' in run_setup_model_src
    assert '"detail"' in run_setup_model_src
    assert '"full"' in run_setup_model_src
    assert '"reuse"' in run_setup_model_src
    assert '"refresh"' in run_setup_model_src
    assert '"off"' in run_setup_model_src
    assert '"balanced"' in run_setup_model_src
    assert '"strict"' in run_setup_model_src
    assert '"force"' in run_setup_model_src
    assert "desktop_single_run_cache_key" in run_setup_runtime_src
    assert "build_selfcheck_subject_signature" in run_setup_runtime_src
    assert "build_run_log_path" in run_setup_runtime_src
    assert "append_subprocess_log" in run_setup_runtime_src
    assert "write_json_report_from_stdout" in run_setup_runtime_src
    assert "--cache_policy" in single_run_src
    assert "--run_profile" in single_run_src
    assert "--export_npz" in single_run_src
    assert "--no_export_csv" in single_run_src
    assert "cache_hit" in single_run_src
    assert "cache_key" in single_run_src
    assert "cache_dir" in single_run_src
    assert "mirror_tree" in single_run_src
    assert "remap_saved_files_to_dir" in single_run_src
    assert "full_log_bundle.npz" in single_run_src
    assert "Desktop Mnemo" in src
    assert "desktop_mnemo" not in editor_src.lower()


def test_desktop_input_editor_hides_service_layers_behind_explicit_toggle() -> None:
    editor_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "service_toggle_text_var" in editor_src
    assert "_toggle_service_panels" in editor_src
    assert "_set_service_panels_visible" in editor_src
    assert 'textvariable=self.service_toggle_text_var' in editor_src
    assert 'overview_frame = ttk.LabelFrame(outer, text="Главное сейчас", padding=10)' in editor_src
    assert 'self._service_container = ttk.Frame(outer)' in editor_src
    assert 'service_notebook = ttk.Notebook(self._service_container)' in editor_src
    assert '(files_service_tab, "Файлы")' in editor_src
    assert '(profiles_service_tab, "Профили и снимки")' in editor_src
    assert '(actions_service_tab, "Расчёт и действия")' in editor_src
    assert '(tools_service_tab, "Навигация и поиск")' in editor_src
    assert 'ttk.LabelFrame(files_service_tab.body, text="Файл параметров", padding=10)' in editor_src
    assert 'profiles_workspace = ttk.Panedwindow(profiles_service_tab.body, orient="horizontal")' in editor_src
    assert 'actions_workspace = ttk.Panedwindow(actions_service_tab.body, orient="horizontal")' in editor_src
    assert 'ttk.LabelFrame(profiles_left_col, text="Рабочие профили", padding=10)' in editor_src
    assert 'profile_details_notebook = ttk.Notebook(profiles_right_col)' in editor_src
    assert 'profile_details_notebook.add(snapshots, text="Снимки")' in editor_src
    assert 'profile_details_notebook.add(diff_frame, text="Сравнение")' in editor_src
    assert 'ttk.LabelFrame(actions_left_col, text="Сводка конфигурации перед запуском", padding=10)' in editor_src
    assert 'ttk.LabelFrame(actions_left_col, text="Быстрые пресеты", padding=10)' in editor_src
    assert 'ttk.LabelFrame(actions_left_col, text="История последних действий", padding=10)' in editor_src
    assert 'ttk.LabelFrame(actions_right_col, text="Проверка и расчёт", padding=10)' in editor_src
    assert 'ttk.LabelFrame(tools_service_tab.body, text="Пошаговый маршрут настройки", padding=10)' in editor_src
    assert 'ttk.LabelFrame(tools_service_tab.body, text="Быстрый поиск по параметрам", padding=10)' in editor_src
    assert 'ttk.LabelFrame(actions_service_tab.body, text="Журнал проверки и расчёта", padding=8)' in editor_src
    assert "_set_service_panels_visible(False)" in editor_src
    assert "before=toolbar" not in editor_src


def test_desktop_input_editor_uses_dense_field_rows_instead_of_large_cards() -> None:
    editor_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'field_row = ttk.Frame(tab.body, padding=(8, 4))' in editor_src
    assert 'name_label = ttk.Label(' in editor_src
    assert 'rowspan=2' in editor_src
    assert 'wraplength=220' in editor_src
    assert 'ttk.Separator(frame, orient="horizontal")' in editor_src
    assert 'frame.columnconfigure(1, weight=1)' in editor_src
    assert 'value_label.grid(row=1, column=1, columnspan=5, sticky="w", pady=(4, 0))' in editor_src
    assert 'ttk.LabelFrame(tab.body, text=spec.label, padding=10)' not in editor_src
    assert 'field_desc_label = ttk.Label(' not in editor_src
