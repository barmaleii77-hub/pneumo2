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
    DESKTOP_INPUT_SECTIONS,
    desktop_field_values_match,
    find_desktop_field_matches,
    desktop_section_status_label,
    desktop_profile_dir_path,
    desktop_profile_display_name,
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
    list_desktop_snapshot_paths,
    preview_surface_label,
    quick_preset_description,
    quick_preset_label,
    run_preset_description,
    run_preset_label,
    sanitize_desktop_profile_name,
)


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_input_model_exposes_main_operator_sections() -> None:
    titles = [section.title for section in DESKTOP_INPUT_SECTIONS]
    assert "Геометрия" in titles
    assert "Пневматика" in titles
    assert "Механика" in titles
    assert "Настройки расчёта" in titles

    specs = field_spec_map()
    assert specs["база"].unit_label == "м"
    assert specs["начальное_давление_Ресивер2"].unit_label == "кПа (абс.)"
    assert specs["термодинамика"].control == "choice"
    assert specs["static_trim_enable"].control == "bool"


def test_desktop_input_model_uses_safe_paths_inside_repo_workspace() -> None:
    default_base = default_base_json_path()
    default_ranges = default_ranges_json_path()
    default_suite = default_suite_json_path()
    working_copy = default_working_copy_path()
    profile_dir = desktop_profile_dir_path()
    profile_path = desktop_profile_path("Мой профиль: demo/1")
    snapshot_dir = desktop_snapshot_dir_path()
    snapshot_path = desktop_snapshot_path("Перед запуском: rough/demo", stamp="20260412_101500")

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


def test_desktop_input_model_exposes_profile_helpers() -> None:
    assert sanitize_desktop_profile_name(" Мой профиль: city/rough ") == "Мой_профиль_city_rough"
    assert desktop_profile_display_name(Path("city_rough.json")) == "city rough"
    assert isinstance(list_desktop_profile_paths(), list)
    assert desktop_snapshot_display_name(Path("20260412_101500__city_rough.json")) == "20260412_101500 · city rough"
    assert isinstance(list_desktop_snapshot_paths(), list)


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

    assert find_desktop_field_matches("несуществующий_параметр", limit=6) == []


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
        "термодинамика": "thermal",
        "механика_кинематика": "dw2d",
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
    assert rows_by_title["Настройки расчёта"]["status"] == "warn"
    assert "форсированный static trim без включённого поиска посадки" in rows_by_title["Настройки расчёта"]["issues"]
    assert "лимит внутренних шагов" in rows_by_title["Настройки расчёта"]["issues"]


def test_desktop_input_editor_is_wired_into_desktop_control_center() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_control_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    editor_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "pneumo_solver_ui.tools.desktop_input_editor" in src
    assert "Исходные данные и расчёт" in src
    assert "default_base.json" in editor_src
    assert "Сохранить рабочую копию" in editor_src
    assert "Рабочие профили" in editor_src
    assert "Снимки перед запуском" in editor_src
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
    assert "Что изменилось по секциям" in editor_src
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
    assert "desktop_section_status_label" in editor_src
    assert "evaluate_desktop_section_readiness" in editor_src
    assert "Готово шагов:" in editor_src
    assert "требуют внимания:" in editor_src
    assert "Статус шага:" in editor_src
    assert "_refresh_section_route_summary" in editor_src
    assert "_select_section_by_title" in editor_src
    assert "_go_prev_section" in editor_src
    assert "_go_next_section" in editor_src
    assert "не дублирует отдельные окна Animator, Compare Viewer или Mnemo" in editor_src
    assert "Быстрый поиск по параметрам" in editor_src
    assert "Найти параметр" in editor_src
    assert "Подходящие параметры" in editor_src
    assert "Перейти к параметру" in editor_src
    assert "Очистить поиск" in editor_src
    assert "field_search_var" in editor_src
    assert "field_search_choice_var" in editor_src
    assert "field_search_summary_var" in editor_src
    assert "_refresh_field_search_results" in editor_src
    assert "_jump_to_selected_field" in editor_src
    assert "_jump_to_field" in editor_src
    assert "_scroll_to_field" in editor_src
    assert "find_desktop_field_matches" in editor_src
    assert "Найдено параметров:" in editor_src
    assert "_soft_preflight_before_run" in editor_src
    assert "Перед запуском «" in editor_src
    assert "есть шаги, требующие внимания" in editor_src
    assert "Запустить всё равно?" in editor_src
    assert "[preflight]" in editor_src
    assert 'if not self._soft_preflight_before_run("Быстрый расчёт")' in editor_src
    assert 'if not self._soft_preflight_before_run("Запустить подробный расчёт")' in editor_src
    assert "Вернуть раздел к значениям по умолчанию" in editor_src
    assert "_reset_section_to_defaults" in editor_src
    assert "[section-reset]" in editor_src
    assert "desktop_profile_dir_path" in editor_src
    assert "list_desktop_profile_paths" in editor_src
    assert "load_desktop_profile" in editor_src
    assert "save_desktop_profile" in editor_src
    assert "build_desktop_profile_diff" in editor_src
    assert "Проверить конфигурацию" in editor_src
    assert "Быстрый расчёт" in editor_src
    assert "Профиль preview-дороги" in editor_src
    assert "Настройки запуска расчёта" in editor_src
    assert "Пресеты запуска" in editor_src
    assert "Будет запущено сейчас" in editor_src
    assert "run_launch_summary_var" in editor_src
    assert "_refresh_run_launch_summary" in editor_src
    assert "Быстрый расчёт: дорожный preview" in editor_src
    assert "Подробный расчёт:" in editor_src
    assert "автоснимок включён" in editor_src
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
    assert "DESKTOP_PREVIEW_SURFACE_OPTIONS" in editor_src
    assert "build_desktop_preview_surface" in editor_src
    assert "preview_surface_label" in editor_src
    assert "pneumo_solver_ui.opt_selfcheck_v1" in editor_src
    assert "pneumo_solver_ui.tools.worldroad_compile_only_demo" in editor_src
    assert "Desktop Mnemo" in src
    assert "desktop_mnemo" not in editor_src.lower()
