from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pneumo_solver_ui.desktop_input_model import describe_desktop_run_mode


DESKTOP_RUN_PROFILE_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "baseline",
        "Baseline / preview",
        "Короткий pre-run режим для sanity-check и быстрой оценки текущей конфигурации.",
    ),
    (
        "detail",
        "Detail",
        "Рабочий одиночный прогон с CSV-артефактами без лишней тяжести.",
    ),
    (
        "full",
        "Full",
        "Подробный прогон с полным логом и готовностью к NPZ-экспорту.",
    ),
)

DESKTOP_RUN_CACHE_POLICY_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "reuse",
        "Переиспользовать",
        "Если совпали параметры, сценарий и режим, взять готовый detail/full результат из cache.",
    ),
    (
        "refresh",
        "Пересчитать заново",
        "Не брать старый cache-hit, но обновить кэш новым результатом после запуска.",
    ),
    (
        "off",
        "Без cache",
        "Не читать и не обновлять runtime-cache для detail/full запуска.",
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
        "Блокировать запуск при проблемах preflight или auto-check.",
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
        f"Baseline / preview: профиль дороги «{preview_surface_label}», "
        f"dt={float(current.get('preview_dt', 0.01) or 0.01):.3f} с, "
        f"длительность={float(current.get('preview_t_end', 3.0) or 3.0):.1f} с, "
        f"длина участка={float(current.get('preview_road_len_m', 60.0) or 60.0):.1f} м."
    )
    detail_line = (
        f"Detail / full: {scenario_label}, dt={float(current.get('run_dt', 0.003) or 0.003):.4f} с, "
        f"длительность={float(current.get('run_t_end', 1.6) or 1.6):.1f} с, "
        f"расширенный лог {'включён' if record_full else 'выключен'}."
    )
    runtime_line = (
        f"Профиль запуска: {profile_label}. "
        f"Cache: {cache_policy_label(cache_key)}. "
        f"Export CSV: {'да' if export_csv else 'нет'}. "
        f"Export NPZ: {'да' if export_npz else 'нет'}. "
        f"Auto-check: {'да' if auto_check else 'нет'}. "
        f"Лог в файл: {'да' if write_log_file else 'нет'}. "
        f"Runtime policy: {runtime_policy_label(runtime_policy_key)}. "
        f"{autosnapshot_text}."
    )
    headline = (
        f"Профиль запуска «{profile_label}»: {profile_description} "
        f"Фактическая оценка detail-режима: {str(run_mode.get('mode_label') or '').strip()}."
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
        cache_state = "cache отключён"
        cache_line = "Cache entry: не используется."
    else:
        cache_state = "cache-hit" if cache_hit else "свежий прогон"
        if cache_dir:
            cache_line = f"Cache entry: {cache_dir}"
        elif cache_entry_key:
            cache_line = f"Cache entry: ключ {cache_entry_key}"
        else:
            cache_line = "Cache entry: пока не зафиксирован."
    log_path = str(current.get("ui_subprocess_log") or "").strip()
    return {
        "headline": f"Последний запуск: {latest_run_name}",
        "scenario_line": (
            f"Сценарий: {current.get('scenario_name') or '—'} "
            f"({current.get('scenario_type') or '—'})"
        ),
        "runtime_line": (
            f"Профиль запуска: {run_profile_label(run_profile_key)}; "
            f"cache: {cache_policy_label(cache_policy_key)} ({cache_state}); "
            f"CSV: {'да' if export_csv else 'нет'}; "
            f"NPZ: {'да' if export_npz else 'нет'}."
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
            f"Экспорт: CSV таблиц={csv_artifacts}; "
            f"NPZ bundle: {'есть' if npz_path else 'нет'}; "
            f"UI лог: {'есть' if log_path else 'нет'}."
        ),
        "cache_line": cache_line,
        "log_line": f"Лог запуска: {log_path}" if log_path else "Лог запуска: не записан.",
        "artifact_line": f"Папка артефактов: {current.get('outdir') or latest_run_dir}",
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
        "headline": "Последний preview: baseline / worldroad sanity-check.",
        "surface_line": (
            f"Профиль дороги: {surface_label}; "
            f"dt={dt_s:.3f} с; длительность={t_end_s:.1f} с; "
            f"длина участка={road_len_m:.1f} м; шагов={n_steps}."
        ),
        "metrics_line": (
            f"roll_max={roll_deg:.2f} deg; "
            f"pitch_max={pitch_deg:.2f} deg; "
            f"min_tire_Fz={min_tire_fz:.1f} N; "
            f"max_tire_pen={max_tire_pen:.4f} м."
        ),
        "pressure_line": f"max_pR3={max_pr3:.1f} Па.",
        "log_line": f"Лог preview: {log_path}" if log_path else "Лог preview: не записан.",
        "report_line": f"JSON отчёт preview: {report_path}",
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
        note_line = f"Первое замечание: warning — {warnings[0]}"
    else:
        note_line = "Первое замечание: критичных проблем и предупреждений нет."

    return {
        "headline": "Последний auto-check / selfcheck.",
        "status_line": (
            f"Статус: {'OK' if ok else 'FAIL'}; "
            f"mode={mode}; errors={len(errors)}; warnings={len(warnings)}; "
            f"checks={check_count}; dt={dt_sec:.2f} с."
        ),
        "freshness_line": f"Актуальность: {describe_selfcheck_freshness(has_signature, is_stale)}.",
        "checks_line": (
            f"Покрытие: files={'files' in checks}; "
            f"ranges={'ranges' in checks}; "
            f"suite={'suite' in checks}; "
            f"scenario_expansion={'scenario_expansion' in checks}; "
            f"model_import={'model_import' in checks}."
        ),
        "log_line": f"Лог auto-check: {log_path}" if log_path else "Лог auto-check: не записан.",
        "report_line": f"JSON отчёт selfcheck: {report_path}",
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
        return "Последний auto-check: ещё не запускался."
    if not isinstance(summary, dict):
        return "Последний auto-check: отчёт найден, но не читается."
    errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
    warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
    ok = bool(summary.get("ok", False))
    mode = str(summary.get("mode") or "fast").strip() or "fast"
    updated_suffix = f"; обновлён {modified_at}" if modified_at else ""
    freshness = describe_selfcheck_freshness(has_signature, is_stale)
    return (
        f"Последний auto-check: {'OK' if ok else 'FAIL'}; "
        f"mode={mode}; errors={len(errors)}; warnings={len(warnings)}"
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
            "Маршрут запуска: «Запустить выбранный режим» сначала делает свежий auto-check; "
            "«Проверить и запустить» выполняет тот же маршрут одним явным действием."
        )

    policy_key = str(runtime_policy_key or "balanced").strip().lower() or "balanced"
    if not report_exists:
        stored_state = "последний сохранённый auto-check не найден"
    elif not isinstance(summary, dict):
        stored_state = "последний сохранённый auto-check не читается"
    else:
        errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
        warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
        freshness = describe_selfcheck_freshness(has_signature, is_stale)
        stored_state = (
            f"использует сохранённый auto-check ({'OK' if bool(summary.get('ok', False)) else 'FAIL'}, "
            f"errors={len(errors)}, warnings={len(warnings)}, {freshness})"
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
        action = "при проблеме policy=force всё равно разрешит запуск"
    elif policy_key == "strict":
        action = "при проблеме policy=strict остановит запуск"
    else:
        action = "при проблеме policy=balanced запросит подтверждение"

    return (
        f"Маршрут запуска: «Запустить выбранный режим» {stored_state}; {action}. "
        "«Проверить и запустить» сначала обновит auto-check."
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
            action = "даже при ошибках policy=force разрешит продолжение"
        elif policy_key == "strict":
            action = "если свежий auto-check вернёт ошибки, policy=strict остановит запуск"
        else:
            action = "если свежий auto-check вернёт ошибки, policy=balanced запросит подтверждение"
        return f"Прогноз обычного запуска: сначала выполнит свежий auto-check; {action}."

    if not report_exists:
        reason = "сохранённый auto-check не найден"
    elif not isinstance(summary, dict):
        reason = "сохранённый auto-check не читается"
    else:
        errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
        warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
        ok = bool(summary.get("ok", False))
        if not has_signature or is_stale:
            reason = (
                "сохранённый auto-check устарел для текущих настроек"
                if is_stale
                else "сохранённый auto-check не привязан к текущей конфигурации"
            )
        elif ok:
            return (
                "Прогноз обычного запуска: пойдёт сразу по актуальному сохранённому auto-check; "
                f"warnings={len(warnings)} не блокируют старт."
            )
        else:
            reason = f"актуальный сохранённый selfcheck содержит ошибки (errors={len(errors)})"

    if policy_key == "force":
        return f"Прогноз обычного запуска: продолжит запуск, хотя {reason}; policy=force разрешает это."
    if policy_key == "strict":
        return f"Прогноз обычного запуска: будет остановлен, потому что {reason}; policy=strict требует новую проверку."
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
            "target_label": "baseline / preview",
            "plain_button": "Запустить preview",
            "checked_button": "Проверить и запустить preview",
            "hint_line": "Целевой запуск: baseline / preview для worldroad sanity-check.",
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
            "detail": "перед стартом выполнится свежий auto-check",
        }

    if not report_exists or not isinstance(summary, dict):
        if policy_key == "strict":
            return {
                "enabled": False,
                "detail": "strict требует новый selfcheck перед запуском",
            }
        if policy_key == "force":
            return {
                "enabled": True,
                "detail": "при проблеме policy=force всё равно разрешит старт без новой проверки",
            }
        return {
            "enabled": True,
            "detail": "при проблеме policy=balanced запросит подтверждение",
        }

    errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
    if not has_signature or is_stale:
        detail = (
            "strict требует свежий selfcheck для текущих настроек"
            if policy_key == "strict"
            else "сохранённый selfcheck уже не подходит текущей конфигурации"
        )
        return {
            "enabled": policy_key != "strict",
            "detail": detail,
        }

    if bool(summary.get("ok", False)):
        warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
        return {
            "enabled": True,
            "detail": f"есть актуальный selfcheck; warnings={len(warnings)} не блокируют старт",
        }

    if policy_key == "strict":
        return {
            "enabled": False,
            "detail": f"strict блокирует старт, пока selfcheck содержит ошибки (errors={len(errors)})",
        }
    if policy_key == "force":
        return {
            "enabled": True,
            "detail": f"policy=force разрешит старт, несмотря на ошибки selfcheck (errors={len(errors)})",
        }
    return {
        "enabled": True,
        "detail": f"policy=balanced спросит подтверждение из-за ошибок selfcheck (errors={len(errors)})",
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
            "Рекомендация: можно нажимать «Запустить выбранный режим»; свежий auto-check всё равно выполнится. "
            "«Проверить и запустить» полезно, если хотите видеть этап проверки как отдельное действие."
        )

    if not report_exists or not isinstance(summary, dict):
        if policy_key == "strict":
            return (
                "Рекомендация: используйте «Проверить и запустить»; без нового selfcheck "
                "обычный запуск упрётся в strict-gate."
            )
        return (
            "Рекомендация: лучше использовать «Проверить и запустить», "
            "чтобы не стартовать без свежего selfcheck."
        )

    errors = [str(item).strip() for item in list(summary.get("errors") or []) if str(item).strip()]
    ok = bool(summary.get("ok", False))
    if not has_signature or is_stale:
        if policy_key == "strict":
            return (
                "Рекомендация: используйте «Проверить и запустить»; сохранённый selfcheck "
                "уже не подходит текущей конфигурации, и strict его не пропустит."
            )
        return (
            "Рекомендация: лучше использовать «Проверить и запустить», "
            "потому что сохранённый selfcheck уже не подходит текущим настройкам."
        )

    if ok:
        return (
            "Рекомендация: можно запускать обычной кнопкой; актуальный selfcheck "
            "уже подходит текущим настройкам."
        )

    if policy_key == "strict":
        return (
            "Рекомендация: используйте «Проверить и запустить»; обычный запуск будет остановлен, "
            f"пока selfcheck содержит ошибки (errors={len(errors)})."
        )
    if policy_key == "force":
        return (
            "Рекомендация: лучше использовать «Проверить и запустить»; обычный запуск разрешён по force, "
            f"но selfcheck уже содержит ошибки (errors={len(errors)})."
        )
    return (
        "Рекомендация: лучше использовать «Проверить и запустить»; обычный запуск лишь спросит "
        f"подтверждение поверх уже известных ошибок (errors={len(errors)})."
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
