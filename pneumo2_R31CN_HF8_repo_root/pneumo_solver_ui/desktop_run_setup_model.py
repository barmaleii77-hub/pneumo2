from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pneumo_solver_ui.desktop_input_model import describe_desktop_run_mode


DESKTOP_RUN_PROFILE_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "baseline",
        "Краткий предпросмотр",
        "Быстрый расчёт для первичной оценки текущей конфигурации.",
    ),
    (
        "detail",
        "Подробный расчёт",
        "Рабочий одиночный прогон с сохранением таблиц результатов без лишней тяжести.",
    ),
    (
        "full",
        "Полный расчёт",
        "Подробный прогон с полным журналом и готовностью к сохранению файла анимации.",
    ),
)

DESKTOP_RUN_CACHE_POLICY_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "reuse",
        "Переиспользовать",
        "Если совпали параметры, сценарий и режим, взять уже готовый результат.",
    ),
    (
        "refresh",
        "Пересчитать заново",
        "Не брать готовый результат, а сохранить новый результат после запуска.",
    ),
    (
        "off",
        "Не искать готовые результаты",
        "Не читать и не обновлять сохранённые результаты подробного расчёта.",
    ),
)

DESKTOP_RUN_RUNTIME_POLICY_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "balanced",
        "С подтверждением",
        "При предупреждениях спросить подтверждение, но не блокировать оператора слишком рано.",
    ),
    (
        "strict",
        "Строго",
        "Блокировать запуск при проблемах предварительной проверки или самопроверки.",
    ),
    (
        "force",
        "Форсировать",
        "Продолжать запуск даже при предупреждениях, фиксируя их в логе.",
    ),
)


@dataclass(frozen=True)
class DesktopRunSetupSnapshot:
    launch_profile: str = "detail"
    scenario_key: str = "worldroad"
    preview_dt: float = 0.01
    preview_t_end: float = 3.0
    preview_road_len_m: float = 60.0
    run_dt: float = 0.003
    run_t_end: float = 1.6
    record_full: bool = False
    primary_value: float = 3.0
    secondary_value: float = 0.4
    cache_policy: str = "reuse"
    export_csv: bool = True
    export_npz: bool = False
    auto_check: bool = True
    write_log_file: bool = True
    runtime_policy: str = "balanced"


def _labels_map(
    options: tuple[tuple[str, str, str], ...],
) -> dict[str, str]:
    return {key: label for key, label, _desc in options}


def _descriptions_map(
    options: tuple[tuple[str, str, str], ...],
) -> dict[str, str]:
    return {key: desc for key, _label, desc in options}


def run_profile_label(profile_key: str) -> str:
    key = str(profile_key or "").strip()
    return _labels_map(DESKTOP_RUN_PROFILE_OPTIONS).get(key, key or "detail")


def run_profile_description(profile_key: str) -> str:
    key = str(profile_key or "").strip()
    return _descriptions_map(DESKTOP_RUN_PROFILE_OPTIONS).get(key, "")


def cache_policy_label(policy_key: str) -> str:
    key = str(policy_key or "").strip()
    return _labels_map(DESKTOP_RUN_CACHE_POLICY_OPTIONS).get(key, key or "reuse")


def cache_policy_description(policy_key: str) -> str:
    key = str(policy_key or "").strip()
    return _descriptions_map(DESKTOP_RUN_CACHE_POLICY_OPTIONS).get(key, "")


def runtime_policy_label(policy_key: str) -> str:
    key = str(policy_key or "").strip()
    return _labels_map(DESKTOP_RUN_RUNTIME_POLICY_OPTIONS).get(key, key or "balanced")


def runtime_policy_description(policy_key: str) -> str:
    key = str(policy_key or "").strip()
    return _descriptions_map(DESKTOP_RUN_RUNTIME_POLICY_OPTIONS).get(key, "")


def _ok_status_label(value: bool) -> str:
    return "норма" if bool(value) else "ошибка"


def _selfcheck_mode_label(value: object) -> str:
    raw = str(value or "fast").strip().lower() or "fast"
    labels = {
        "fast": "быстрый",
        "quick": "быстрый",
        "standard": "стандартный",
        "full": "полный",
    }
    return labels.get(raw, raw)


def _scenario_duration(profile_key: str, scenario_key: str) -> float:
    profile = str(profile_key or "detail").strip().lower() or "detail"
    scenario = str(scenario_key or "worldroad").strip().lower() or "worldroad"
    if profile == "baseline":
        return 0.8 if scenario == "worldroad" else 1.0
    if profile == "full":
        return 2.4 if scenario == "worldroad" else 2.0
    return 1.6 if scenario == "worldroad" else 1.8


def apply_run_setup_profile(
    snapshot: dict[str, Any] | DesktopRunSetupSnapshot,
    profile_key: str,
    *,
    scenario_key: str = "worldroad",
) -> tuple[dict[str, Any], list[str]]:
    current = (
        dict(snapshot)
        if isinstance(snapshot, dict)
        else dict(vars(snapshot))
    )
    updated = dict(current)
    changed_keys: list[str] = []

    def _set_value(key: str, value: Any) -> None:
        if updated.get(key) != value:
            updated[key] = value
            changed_keys.append(key)

    profile = str(profile_key or "detail").strip().lower() or "detail"
    scenario = str(scenario_key or "worldroad").strip().lower() or "worldroad"

    _set_value("launch_profile", profile)

    if profile == "baseline":
        _set_value("preview_dt", 0.006)
        _set_value("preview_t_end", _scenario_duration("baseline", scenario))
        _set_value("run_dt", 0.006)
        _set_value("run_t_end", _scenario_duration("baseline", scenario))
        _set_value("record_full", False)
        _set_value("cache_policy", "off")
        _set_value("export_csv", False)
        _set_value("export_npz", False)
        _set_value("auto_check", True)
        _set_value("write_log_file", True)
        _set_value("runtime_policy", "balanced")
        return updated, changed_keys

    if profile == "full":
        _set_value("run_dt", 0.0015)
        _set_value("run_t_end", _scenario_duration("full", scenario))
        _set_value("record_full", True)
        _set_value("cache_policy", "refresh")
        _set_value("export_csv", True)
        _set_value("export_npz", True)
        _set_value("auto_check", True)
        _set_value("write_log_file", True)
        _set_value("runtime_policy", "strict")
        return updated, changed_keys

    _set_value("run_dt", 0.003)
    _set_value("run_t_end", _scenario_duration("detail", scenario))
    _set_value("record_full", False)
    _set_value("cache_policy", "reuse")
    _set_value("export_csv", True)
    _set_value("export_npz", False)
    _set_value("auto_check", True)
    _set_value("write_log_file", True)
    _set_value("runtime_policy", "balanced")
    return updated, changed_keys


def describe_run_setup_snapshot(
    snapshot: dict[str, Any] | DesktopRunSetupSnapshot,
    *,
    scenario_label: str,
    preview_surface_label: str,
    snapshot_enabled: bool,
    snapshot_name: str,
) -> dict[str, str]:
    current = (
        dict(snapshot)
        if isinstance(snapshot, dict)
        else dict(vars(snapshot))
    )
    launch_profile = str(current.get("launch_profile") or "detail").strip() or "detail"
    profile_label = run_profile_label(launch_profile)
    profile_description = run_profile_description(launch_profile)
    cache_key = str(current.get("cache_policy") or "reuse").strip() or "reuse"
    runtime_policy_key = str(current.get("runtime_policy") or "balanced").strip() or "balanced"
    export_csv = bool(current.get("export_csv", True))
    export_npz = bool(current.get("export_npz", False))
    auto_check = bool(current.get("auto_check", True))
    write_log_file = bool(current.get("write_log_file", True))
    record_full = bool(current.get("record_full", False))
    run_mode = describe_desktop_run_mode(
        {
            "dt": float(current.get("run_dt", 0.003) or 0.003),
            "t_end": float(current.get("run_t_end", 1.6) or 1.6),
            "record_full": record_full,
        }
    )
    autosnapshot_text = (
        f"автоснимок включён ({snapshot_name})"
        if snapshot_enabled
        else "автоснимок выключен"
    )
    preview_line = (
        f"Предпросмотр: профиль дороги «{preview_surface_label}», "
        f"шаг: {float(current.get('preview_dt', 0.01) or 0.01):.3f} с, "
        f"длительность: {float(current.get('preview_t_end', 3.0) or 3.0):.1f} с, "
        f"длина участка: {float(current.get('preview_road_len_m', 60.0) or 60.0):.1f} м."
    )
    detail_line = (
        f"Подробный расчёт: {scenario_label}, шаг: {float(current.get('run_dt', 0.003) or 0.003):.4f} с, "
        f"длительность: {float(current.get('run_t_end', 1.6) or 1.6):.1f} с, "
        f"расширенный журнал {'включён' if record_full else 'выключен'}."
    )
    runtime_line = (
        f"Профиль запуска: {profile_label}. "
        f"Повторное использование: {cache_policy_label(cache_key)}. "
        f"Таблицы результатов: {'да' if export_csv else 'нет'}. "
        f"Файл анимации: {'да' if export_npz else 'нет'}. "
        f"Самопроверка: {'да' if auto_check else 'нет'}. "
        f"Журнал в файл: {'да' if write_log_file else 'нет'}. "
        f"Режим выполнения: {runtime_policy_label(runtime_policy_key)}. "
        f"{autosnapshot_text}."
    )
    headline = (
        f"Профиль запуска «{profile_label}»: {profile_description} "
        f"Фактическая оценка подробного режима: {str(run_mode.get('mode_label') or '').strip()}."
    )
    return {
        "headline": headline.strip(),
        "preview_line": preview_line,
        "detail_line": detail_line,
        "runtime_line": runtime_line,
        "mode_summary": str(run_mode.get("summary") or "").strip(),
        "cost_summary": str(run_mode.get("cost_summary") or "").strip(),
        "advice_summary": str(run_mode.get("advice_summary") or "").strip(),
        "usage_summary": str(run_mode.get("usage_summary") or "").strip(),
    }


def describe_latest_run_summary(
    summary: dict[str, Any],
    *,
    latest_run_name: str,
    latest_run_dir: str,
) -> dict[str, str]:
    current = dict(summary or {})
    run_profile_key = str(current.get("run_profile") or "detail").strip() or "detail"
    cache_policy_key = str(current.get("cache_policy") or "off").strip() or "off"
    cache_entry_key = str(current.get("cache_key") or "").strip()
    cache_dir = str(current.get("cache_dir") or "").strip()
    cache_hit = bool(current.get("cache_hit", False))
    export_csv = bool(current.get("export_csv", True))
    export_npz = bool(current.get("export_npz", False))
    saved_files = dict(current.get("saved_files") or {})
    csv_artifacts = sum(1 for value in saved_files.values() if str(value or "").lower().endswith(".csv"))
    npz_path = str(saved_files.get("npz_bundle") or "").strip()
    run_mode = describe_desktop_run_mode(
        {
            "dt": current.get("dt_s"),
            "t_end": current.get("t_end_s"),
            "record_full": current.get("record_full"),
        }
    )
    mech_ok = current.get("mech_selfcheck_ok")
    if mech_ok is None:
        mech_label = "данных пока нет"
    else:
        mech_label = "в норме" if bool(mech_ok) else "требует внимания"
    if cache_policy_key == "off":
        cache_state = "не используется"
        cache_line = "Повторное использование результата: выключено."
    else:
        cache_state = "использован готовый результат" if cache_hit else "новый расчёт"
        if cache_dir:
            cache_line = f"Папка повторного использования: {cache_dir}"
        elif cache_entry_key:
            cache_line = f"Повторное использование результата: запись {cache_entry_key}"
        else:
            cache_line = "Повторное использование результата: пока не зафиксировано."
    log_path = str(current.get("ui_subprocess_log") or "").strip()
    return {
        "headline": f"Последний запуск: {latest_run_name}",
        "scenario_line": (
            f"Сценарий: {current.get('scenario_name') or '—'} "
            f"({current.get('scenario_type') or '—'})"
        ),
        "runtime_line": (
            f"Профиль запуска: {run_profile_label(run_profile_key)}; "
            f"повторное использование: {cache_policy_label(cache_policy_key)} ({cache_state}); "
            f"таблицы результатов: {'да' if export_csv else 'нет'}; "
            f"файл анимации: {'да' if export_npz else 'нет'}."
        ),
        "mode_line": (
            f"Режим: {run_mode.get('mode_label') or '—'}; "
            f"{run_mode.get('cost_label') or '—'}"
        ),
        "health_line": (
            f"Строк df_main: {int(current.get('df_main_rows') or 0)}; "
            f"самопроверка механики: {mech_label}"
        ),
        "artifact_state_line": (
            f"Сохранено: таблиц результатов: {csv_artifacts}; "
            f"файл анимации: {'есть' if npz_path else 'нет'}; "
            f"журнал запуска: {'есть' if log_path else 'нет'}."
        ),
        "cache_line": cache_line,
        "log_line": f"Журнал запуска: {log_path}" if log_path else "Журнал запуска: не записан.",
        "artifact_line": f"Папка результатов: {current.get('outdir') or latest_run_dir}",
    }


def describe_latest_preview_summary(
    summary: dict[str, Any],
    *,
    report_path: str,
) -> dict[str, str]:
    current = dict(summary or {})
    surface_label = str(current.get("preview_surface_label") or "—").strip() or "—"
    dt_s = float(current.get("dt_s", 0.0) or 0.0)
    t_end_s = float(current.get("t_end_s", 0.0) or 0.0)
    n_steps = int(current.get("n_steps", 0) or 0)
    roll_deg = float(current.get("max_abs_phi_deg", 0.0) or 0.0)
    pitch_deg = float(current.get("max_abs_theta_deg", 0.0) or 0.0)
    min_tire_fz = float(current.get("min_tire_Fz_N", 0.0) or 0.0)
    max_tire_pen = float(current.get("max_tire_pen_m", 0.0) or 0.0)
    max_pr3 = float(current.get("max_pR3_Pa", 0.0) or 0.0)
    road_len_m = float(current.get("preview_road_len_m", 0.0) or 0.0)
    log_path = str(current.get("ui_subprocess_log") or "").strip()
    note = str(current.get("note") or "").strip()
    return {
        "headline": "Последний предпросмотр дороги.",
        "surface_line": (
            f"Профиль дороги: {surface_label}; "
            f"шаг: {dt_s:.3f} с; длительность: {t_end_s:.1f} с; "
            f"длина участка: {road_len_m:.1f} м; шагов: {n_steps}."
        ),
        "metrics_line": (
            f"макс. крен={roll_deg:.2f} град; "
            f"макс. тангаж={pitch_deg:.2f} град; "
            f"мин. реакция шины={min_tire_fz:.1f} Н; "
            f"макс. сжатие шины={max_tire_pen:.4f} м."
        ),
        "pressure_line": f"Макс. давление R3: {max_pr3:.1f} Па.",
        "log_line": f"Журнал предпросмотра: {log_path}" if log_path else "Журнал предпросмотра: не записан.",
        "report_line": f"Сводка предпросмотра: {report_path}",
        "note_line": f"Примечание: {note}" if note else "",
    }


def describe_latest_selfcheck_summary(
    summary: dict[str, Any],
    *,
    report_path: str,
    has_signature: bool = True,
    is_stale: bool = False,
) -> dict[str, str]:
    current = dict(summary or {})
    ok = bool(current.get("ok", False))
    mode = str(current.get("mode") or "fast").strip() or "fast"
    errors = [str(item).strip() for item in list(current.get("errors") or []) if str(item).strip()]
    warnings = [str(item).strip() for item in list(current.get("warnings") or []) if str(item).strip()]
    checks = dict(current.get("checks") or {})
    check_count = len(checks)
    dt_sec = float(current.get("dt_sec", 0.0) or 0.0)
    log_path = str(current.get("ui_subprocess_log") or "").strip()

    if errors:
        note_line = f"Первое замечание: ошибка — {errors[0]}"
    elif warnings:
        note_line = f"Первое замечание: предупреждение — {warnings[0]}"
    else:
        note_line = "Первое замечание: критичных проблем и предупреждений нет."

    return {
        "headline": "Последняя самопроверка.",
        "status_line": (
            f"Статус: {_ok_status_label(ok)}; "
            f"режим: {_selfcheck_mode_label(mode)}; ошибок: {len(errors)}; предупреждений: {len(warnings)}; "
            f"проверок: {check_count}; время: {dt_sec:.2f} с."
        ),
        "freshness_line": f"Актуальность: {describe_selfcheck_freshness(has_signature, is_stale)}.",
        "checks_line": (
            f"Покрытие: файлы: {'да' if 'files' in checks else 'нет'}; "
            f"диапазоны: {'да' if 'ranges' in checks else 'нет'}; "
            f"набор испытаний: {'да' if 'suite' in checks else 'нет'}; "
            f"сценарии: {'да' if 'scenario_expansion' in checks else 'нет'}; "
            f"модель: {'да' if 'model_import' in checks else 'нет'}."
        ),
        "log_line": f"Журнал самопроверки: {log_path}" if log_path else "Журнал самопроверки: не записан.",
        "report_line": f"Сводка самопроверки: {report_path}",
        "note_line": note_line,
    }


def describe_selfcheck_freshness(has_signature: bool, is_stale: bool) -> str:
    if not has_signature:
        return "без привязки к текущей конфигурации"
    return "устарел для текущих настроек" if is_stale else "актуален для текущих настроек"


def describe_selfcheck_gate_status(
    summary: dict[str, Any] | None,
    *,
    report_exists: bool,
    modified_at: str = "",
    has_signature: bool = True,
    is_stale: bool = False,
) -> str:
    if not report_exists:
        return "Последняя самопроверка: ещё не запускалась."
    if not isinstance(summary, dict):
        return "Последняя самопроверка: отчёт найден, но не читается."
    errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
    warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
    ok = bool(summary.get("ok", False))
    mode = str(summary.get("mode") or "fast").strip() or "fast"
    updated_suffix = f"; обновлён {modified_at}" if modified_at else ""
    freshness = describe_selfcheck_freshness(has_signature, is_stale)
    return (
        f"Последняя самопроверка: {_ok_status_label(ok)}; "
        f"режим: {_selfcheck_mode_label(mode)}; ошибок: {len(errors)}; предупреждений: {len(warnings)}"
        f"; {freshness}{updated_suffix}."
    )


def describe_run_launch_route(
    *,
    auto_check_enabled: bool,
    runtime_policy_key: str,
    summary: dict[str, Any] | None,
    report_exists: bool,
    has_signature: bool = True,
    is_stale: bool = False,
) -> str:
    if auto_check_enabled:
        return (
            "Маршрут запуска: «Запустить расчёт» сначала делает свежую самопроверку; "
            "«Проверить и запустить» выполняет тот же маршрут одним явным действием."
        )

    policy_key = str(runtime_policy_key or "balanced").strip().lower() or "balanced"
    if not report_exists:
        stored_state = "последняя сохранённая самопроверка не найдена"
    elif not isinstance(summary, dict):
        stored_state = "последняя сохранённая самопроверка не читается"
    else:
        errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
        warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
        freshness = describe_selfcheck_freshness(has_signature, is_stale)
        stored_state = (
            f"использует сохранённую самопроверку ({_ok_status_label(bool(summary.get('ok', False)))}; "
            f"ошибок: {len(errors)}; предупреждений: {len(warnings)}; {freshness})"
        )

    stored_is_fresh_ok = (
        report_exists
        and isinstance(summary, dict)
        and bool(summary.get("ok", False))
        and has_signature
        and not is_stale
    )
    if stored_is_fresh_ok:
        action = "обычный запуск опирается на него без повторной проверки"
    elif policy_key == "force":
        action = "при проблеме форсированный режим всё равно разрешит запуск"
    elif policy_key == "strict":
        action = "при проблеме строгий режим остановит запуск"
    else:
        action = "при проблеме режим с подтверждением запросит решение оператора"

    return (
        f"Маршрут запуска: «Запустить расчёт» {stored_state}; {action}. "
        "«Проверить и запустить» сначала обновит самопроверку."
    )


def describe_run_launch_outlook(
    *,
    auto_check_enabled: bool,
    runtime_policy_key: str,
    summary: dict[str, Any] | None,
    report_exists: bool,
    has_signature: bool = True,
    is_stale: bool = False,
) -> str:
    policy_key = str(runtime_policy_key or "balanced").strip().lower() or "balanced"
    if auto_check_enabled:
        if policy_key == "force":
            action = "даже при ошибках форсированный режим разрешит продолжение"
        elif policy_key == "strict":
            action = "если свежая самопроверка вернёт ошибки, строгий режим остановит запуск"
        else:
            action = "если свежая самопроверка вернёт ошибки, режим с подтверждением запросит решение оператора"
        return f"Прогноз обычного запуска: сначала выполнит свежую самопроверку; {action}."

    if not report_exists:
        reason = "сохранённая самопроверка не найдена"
    elif not isinstance(summary, dict):
        reason = "сохранённая самопроверка не читается"
    else:
        errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
        warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
        ok = bool(summary.get("ok", False))
        if not has_signature or is_stale:
            reason = (
                "сохранённая самопроверка устарела для текущих настроек"
                if is_stale
                else "сохранённая самопроверка не привязана к текущей конфигурации"
            )
        elif ok:
            return (
                "Прогноз обычного запуска: пойдёт сразу по актуальной сохранённой самопроверке; "
                f"предупреждений: {len(warnings)} не блокируют старт."
            )
        else:
            reason = f"актуальная сохранённая самопроверка содержит ошибки (ошибок: {len(errors)})"

    if policy_key == "force":
        return f"Прогноз обычного запуска: продолжит запуск, хотя {reason}; форсированный режим разрешает это."
    if policy_key == "strict":
        return f"Прогноз обычного запуска: будет остановлен, потому что {reason}; строгий режим требует новую проверку."
    return f"Прогноз обычного запуска: запросит подтверждение, потому что {reason}."


def describe_run_launch_target(
    *,
    launch_profile_key: str,
    scenario_key: str,
    scenario_label: str,
) -> dict[str, str]:
    profile_key = str(launch_profile_key or "detail").strip().lower() or "detail"
    scenario_name = str(scenario_key or "worldroad").strip().lower() or "worldroad"
    scenario_title = str(scenario_label or scenario_name).strip() or scenario_name
    profile_title = run_profile_label(profile_key)
    if profile_key == "baseline" and scenario_name == "worldroad":
        return {
            "target_label": "краткий предпросмотр",
            "plain_button": "Запустить предпросмотр",
            "checked_button": "Проверить и запустить предпросмотр",
            "hint_line": "Целевой запуск: краткий предпросмотр дороги.",
        }
    return {
        "target_label": profile_title,
        "plain_button": f"Запустить {profile_title}",
        "checked_button": f"Проверить и запустить {profile_title}",
        "hint_line": f"Целевой запуск: {profile_title}, сценарий «{scenario_title}».",
    }


def recommended_run_launch_action(
    *,
    auto_check_enabled: bool,
    summary: dict[str, Any] | None,
    report_exists: bool,
    has_signature: bool = True,
    is_stale: bool = False,
) -> str:
    if auto_check_enabled:
        return "plain_launch"
    if not report_exists or not isinstance(summary, dict):
        return "check_then_launch"
    if not has_signature or is_stale:
        return "check_then_launch"
    if bool(summary.get("ok", False)):
        return "plain_launch"
    return "check_then_launch"


def describe_plain_launch_availability(
    *,
    auto_check_enabled: bool,
    runtime_policy_key: str,
    summary: dict[str, Any] | None,
    report_exists: bool,
    has_signature: bool = True,
    is_stale: bool = False,
) -> dict[str, Any]:
    policy_key = str(runtime_policy_key or "balanced").strip().lower() or "balanced"
    if auto_check_enabled:
        return {
            "enabled": True,
            "detail": "перед стартом выполнится свежая самопроверка",
        }

    if not report_exists or not isinstance(summary, dict):
        if policy_key == "strict":
            return {
                "enabled": False,
                "detail": "строгий режим требует новую самопроверку перед запуском",
            }
        if policy_key == "force":
            return {
                "enabled": True,
                "detail": "форсированный режим всё равно разрешит старт без новой проверки",
            }
        return {
            "enabled": True,
            "detail": "режим с подтверждением запросит решение оператора при проблеме",
        }

    errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
    if not has_signature or is_stale:
        detail = (
            "строгий режим требует свежую самопроверку для текущих настроек"
            if policy_key == "strict"
            else "сохранённая самопроверка уже не подходит текущей конфигурации"
        )
        return {
            "enabled": policy_key != "strict",
            "detail": detail,
        }

    if bool(summary.get("ok", False)):
        warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
        return {
            "enabled": True,
            "detail": f"есть актуальная самопроверка; предупреждений: {len(warnings)} не блокируют старт",
        }

    if policy_key == "strict":
        return {
            "enabled": False,
            "detail": f"строгий режим блокирует старт, пока самопроверка содержит ошибки (ошибок: {len(errors)})",
        }
    if policy_key == "force":
        return {
            "enabled": True,
            "detail": f"форсированный режим разрешит старт, несмотря на ошибки самопроверки (ошибок: {len(errors)})",
        }
    return {
        "enabled": True,
        "detail": f"режим с подтверждением спросит решение оператора из-за ошибок самопроверки (ошибок: {len(errors)})",
    }


def describe_run_launch_recommendation(
    *,
    auto_check_enabled: bool,
    runtime_policy_key: str,
    summary: dict[str, Any] | None,
    report_exists: bool,
    has_signature: bool = True,
    is_stale: bool = False,
) -> str:
    policy_key = str(runtime_policy_key or "balanced").strip().lower() or "balanced"
    if auto_check_enabled:
        return (
            "Рекомендация: можно нажимать «Запустить расчёт»; свежая самопроверка всё равно выполнится. "
            "«Проверить и запустить» полезно, если хотите видеть этап проверки как отдельное действие."
        )

    if not report_exists or not isinstance(summary, dict):
        if policy_key == "strict":
            return (
                "Рекомендация: используйте «Проверить и запустить»; без новой самопроверки "
                "обычный запуск остановит строгий режим."
            )
        return (
            "Рекомендация: лучше использовать «Проверить и запустить», "
            "чтобы не стартовать без свежей самопроверки."
        )

    errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
    ok = bool(summary.get("ok", False))
    if not has_signature or is_stale:
        if policy_key == "strict":
            return (
                "Рекомендация: используйте «Проверить и запустить»; сохранённая самопроверка "
                "уже не подходит текущей конфигурации, и строгий режим её не пропустит."
            )
        return (
            "Рекомендация: лучше использовать «Проверить и запустить», "
            "потому что сохранённая самопроверка уже не подходит текущим настройкам."
        )

    if ok:
        return (
            "Рекомендация: можно запускать обычной кнопкой; актуальная самопроверка "
            "уже подходит текущим настройкам."
        )

    if policy_key == "strict":
        return (
            "Рекомендация: используйте «Проверить и запустить»; обычный запуск будет остановлен, "
            f"пока самопроверка содержит ошибки (ошибок: {len(errors)})."
        )
    if policy_key == "force":
        return (
            "Рекомендация: лучше использовать «Проверить и запустить»; обычный запуск разрешён в форсированном режиме, "
            f"но самопроверка уже содержит ошибки (ошибок: {len(errors)})."
        )
    return (
        "Рекомендация: лучше использовать «Проверить и запустить»; обычный запуск лишь спросит "
        f"подтверждение поверх уже известных ошибок (ошибок: {len(errors)})."
    )


__all__ = [
    "DESKTOP_RUN_CACHE_POLICY_OPTIONS",
    "DESKTOP_RUN_PROFILE_OPTIONS",
    "DESKTOP_RUN_RUNTIME_POLICY_OPTIONS",
    "DesktopRunSetupSnapshot",
    "apply_run_setup_profile",
    "cache_policy_description",
    "cache_policy_label",
    "describe_latest_preview_summary",
    "describe_selfcheck_freshness",
    "describe_selfcheck_gate_status",
    "describe_run_launch_route",
    "describe_run_launch_outlook",
    "describe_run_launch_target",
    "recommended_run_launch_action",
    "describe_plain_launch_availability",
    "describe_run_launch_recommendation",
    "describe_latest_selfcheck_summary",
    "describe_latest_run_summary",
    "describe_run_setup_snapshot",
    "run_profile_description",
    "run_profile_label",
    "runtime_policy_description",
    "runtime_policy_label",
]
