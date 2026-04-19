from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_run_setup_model import (
    describe_plain_launch_availability,
    describe_latest_preview_summary,
    describe_run_launch_outlook,
    describe_run_launch_recommendation,
    describe_run_launch_route,
    describe_run_launch_target,
    recommended_run_launch_action,
    describe_selfcheck_freshness,
    describe_selfcheck_gate_status,
    describe_latest_selfcheck_summary,
    apply_run_setup_profile,
    describe_latest_run_summary,
    describe_run_setup_snapshot,
)
from pneumo_solver_ui.desktop_run_setup_runtime import (
    build_selfcheck_subject_signature,
    desktop_single_run_cache_key,
    remap_saved_files_to_dir,
    write_json_report_from_stdout,
)


def test_apply_run_setup_profile_switches_runtime_defaults() -> None:
    baseline, baseline_keys = apply_run_setup_profile({}, "baseline", scenario_key="worldroad")
    full, full_keys = apply_run_setup_profile({}, "full", scenario_key="worldroad")
    detail, detail_keys = apply_run_setup_profile({}, "detail", scenario_key="roll")

    assert baseline["launch_profile"] == "baseline"
    assert baseline["run_dt"] == 0.006
    assert baseline["cache_policy"] == "off"
    assert baseline["export_csv"] is False
    assert baseline["runtime_policy"] == "balanced"
    assert "cache_policy" in baseline_keys

    assert full["launch_profile"] == "full"
    assert full["run_dt"] == 0.0015
    assert full["record_full"] is True
    assert full["cache_policy"] == "refresh"
    assert full["export_npz"] is True
    assert full["runtime_policy"] == "strict"
    assert "export_npz" in full_keys

    assert detail["launch_profile"] == "detail"
    assert detail["run_t_end"] == 1.8
    assert detail["cache_policy"] == "reuse"
    assert detail["export_csv"] is True
    assert detail["runtime_policy"] == "balanced"
    assert "run_t_end" in detail_keys


def test_describe_run_setup_snapshot_includes_operator_friendly_runtime_summary() -> None:
    summary = describe_run_setup_snapshot(
        {
            "launch_profile": "full",
            "preview_dt": 0.006,
            "preview_t_end": 0.8,
            "preview_road_len_m": 80.0,
            "run_dt": 0.0015,
            "run_t_end": 2.4,
            "record_full": True,
            "cache_policy": "refresh",
            "export_csv": True,
            "export_npz": True,
            "auto_check": True,
            "write_log_file": True,
            "runtime_policy": "strict",
        },
        scenario_label="Дорога: текущий профиль preview",
        preview_surface_label="Косинусный бугор",
        snapshot_enabled=True,
        snapshot_name="before_full_run",
    )

    assert "Профиль запуска" in summary["headline"]
    assert "Предпросмотр" in summary["preview_line"]
    assert "Подробный расчёт" in summary["detail_line"]
    assert "Повторное использование: Пересчитать заново." in summary["runtime_line"]
    assert "Таблицы результатов: да." in summary["runtime_line"]
    assert "Файл анимации: да." in summary["runtime_line"]
    assert "Выгрузка NPZ" not in summary["runtime_line"]
    assert "автоснимок включён (before_full_run)" in summary["runtime_line"]


def test_describe_latest_run_summary_exposes_cache_export_and_log_state() -> None:
    summary = describe_latest_run_summary(
        {
            "scenario_name": "desktop_run_worldroad",
            "scenario_type": "worldroad",
            "dt_s": 0.0015,
            "t_end_s": 2.4,
            "record_full": True,
            "run_profile": "full",
            "cache_policy": "reuse",
            "cache_hit": True,
            "cache_key": "abc123",
            "cache_dir": "C:/cache/desktop_run_setup/single_run/abc123",
            "export_csv": True,
            "export_npz": True,
            "df_main_rows": 1800,
            "mech_selfcheck_ok": True,
            "outdir": "C:/tmp/run_001",
            "ui_subprocess_log": "C:/tmp/run_001.log",
            "saved_files": {
                "df_main": "C:/tmp/run_001/df_main.csv",
                "df_atm": "C:/tmp/run_001/df_atm.csv",
                "npz_bundle": "C:/tmp/run_001/full_log_bundle.npz",
            },
        },
        latest_run_name="desktop_input_run_20260412_150000",
        latest_run_dir="C:/tmp/run_001",
    )

    assert "Последний запуск" in summary["headline"]
    assert "desktop_run_worldroad" in summary["scenario_line"]
    assert "Профиль запуска: Полный расчёт" in summary["runtime_line"]
    assert "использован готовый результат" in summary["runtime_line"]
    assert "таблицы результатов: да" in summary["runtime_line"]
    assert "файл анимации: да" in summary["runtime_line"]
    assert "CSV: да" not in summary["runtime_line"]
    assert "NPZ: да" not in summary["runtime_line"]
    assert "самопроверка механики: в норме" in summary["health_line"]
    assert "таблиц результатов: 2" in summary["artifact_state_line"]
    assert "файл анимации: есть" in summary["artifact_state_line"]
    assert "журнал запуска: есть" in summary["artifact_state_line"]
    assert "C:/cache/desktop_run_setup/single_run/abc123" in summary["cache_line"]
    assert "C:/tmp/run_001.log" in summary["log_line"]
    assert "C:/tmp/run_001" in summary["artifact_line"]


def test_describe_latest_preview_summary_exposes_metrics_and_log_state() -> None:
    summary = describe_latest_preview_summary(
        {
            "preview_surface_label": "Косинусный бугор",
            "dt_s": 0.006,
            "t_end_s": 0.8,
            "n_steps": 134,
            "preview_road_len_m": 80.0,
            "max_abs_phi_deg": 2.4,
            "max_abs_theta_deg": 1.2,
            "min_tire_Fz_N": 912.5,
            "max_tire_pen_m": 0.013,
            "max_pR3_Pa": 615000.0,
            "ui_subprocess_log": "C:/tmp/preview.log",
            "note": "compile_only demo",
        },
        report_path="C:/tmp/desktop_input_preview_report.json",
    )

    assert "Последний предпросмотр" in summary["headline"]
    assert "Косинусный бугор" in summary["surface_line"]
    assert "шагов: 134" in summary["surface_line"]
    assert "макс. крен=2.40 град" in summary["metrics_line"]
    assert "Макс. давление R3: 615000.0 Па." in summary["pressure_line"]
    assert "C:/tmp/preview.log" in summary["log_line"]
    assert "desktop_input_preview_report.json" in summary["report_line"]
    assert "compile_only demo" in summary["note_line"]


def test_describe_latest_selfcheck_summary_exposes_status_and_log_state() -> None:
    summary = describe_latest_selfcheck_summary(
        {
            "ok": False,
            "mode": "fast",
            "dt_sec": 0.42,
            "errors": ["Missing file: demo.py"],
            "warnings": ["Suite contains duplicate test names"],
            "checks": {
                "files": {"ok": False},
                "ranges": {"ok": True},
                "suite": {"ok": True},
                "scenario_expansion": {"ok": True},
            },
            "ui_subprocess_log": "C:/tmp/selfcheck.log",
        },
        report_path="C:/tmp/desktop_input_selfcheck_report.json",
        has_signature=True,
        is_stale=True,
    )

    assert "Последняя самопроверка" in summary["headline"]
    assert "Статус: ошибка" in summary["status_line"]
    assert "устарел для текущих настроек" in summary["freshness_line"]
    assert "режим: быстрый" in summary["status_line"]
    assert "ошибок: 1" in summary["status_line"]
    assert "предупреждений: 1" in summary["status_line"]
    assert "файлы: да" in summary["checks_line"]
    assert "сценарии: да" in summary["checks_line"]
    assert "C:/tmp/selfcheck.log" in summary["log_line"]
    assert "desktop_input_selfcheck_report.json" in summary["report_line"]
    assert "Missing file: demo.py" in summary["note_line"]


def test_describe_selfcheck_gate_status_produces_launch_friendly_line() -> None:
    missing = describe_selfcheck_gate_status(None, report_exists=False)
    broken = describe_selfcheck_gate_status(None, report_exists=True)
    legacy = describe_selfcheck_gate_status(
        {
            "ok": True,
            "mode": "fast",
            "errors": [],
            "warnings": [],
        },
        report_exists=True,
        has_signature=False,
    )
    ok = describe_selfcheck_gate_status(
        {
            "ok": True,
            "mode": "fast",
            "errors": [],
            "warnings": ["minor"],
        },
        report_exists=True,
        modified_at="2026-04-13 10:45",
        has_signature=True,
        is_stale=False,
    )
    stale = describe_selfcheck_gate_status(
        {
            "ok": False,
            "mode": "fast",
            "errors": ["x"],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=True,
    )

    assert "ещё не запускалась" in missing
    assert "отчёт найден, но не читается" in broken
    assert "без привязки к текущей конфигурации" in legacy
    assert "Последняя самопроверка: норма" in ok
    assert "актуален для текущих настроек" in ok
    assert "устарел для текущих настроек" in stale
    assert "предупреждений: 1" in ok
    assert "2026-04-13 10:45" in ok


def test_describe_run_launch_route_explains_default_and_prechecked_paths() -> None:
    auto = describe_run_launch_route(
        auto_check_enabled=True,
        runtime_policy_key="balanced",
        summary=None,
        report_exists=False,
    )
    stored_ok = describe_run_launch_route(
        auto_check_enabled=False,
        runtime_policy_key="balanced",
        summary={
            "ok": True,
            "errors": [],
            "warnings": ["minor"],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    )
    strict_stale = describe_run_launch_route(
        auto_check_enabled=False,
        runtime_policy_key="strict",
        summary={
            "ok": False,
            "errors": ["broken"],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=True,
    )

    assert "сначала делает свежую самопроверку" in auto
    assert "Проверить и запустить" in auto
    assert "использует сохранённую самопроверку (норма" in stored_ok
    assert "без повторной проверки" in stored_ok
    assert "устарел для текущих настроек" in strict_stale
    assert "строгий режим остановит запуск" in strict_stale
    assert "сначала обновит самопроверку" in strict_stale


def test_describe_run_launch_outlook_predicts_operator_visible_gate() -> None:
    auto = describe_run_launch_outlook(
        auto_check_enabled=True,
        runtime_policy_key="balanced",
        summary=None,
        report_exists=False,
    )
    stored_ok = describe_run_launch_outlook(
        auto_check_enabled=False,
        runtime_policy_key="balanced",
        summary={
            "ok": True,
            "errors": [],
            "warnings": ["minor"],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    )
    strict_stale = describe_run_launch_outlook(
        auto_check_enabled=False,
        runtime_policy_key="strict",
        summary={
            "ok": True,
            "errors": [],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=True,
    )
    force_failed = describe_run_launch_outlook(
        auto_check_enabled=False,
        runtime_policy_key="force",
        summary={
            "ok": False,
            "errors": ["broken", "also broken"],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    )

    assert "сначала выполнит свежую самопроверку" in auto
    assert "режим с подтверждением запросит решение оператора" in auto
    assert "пойдёт сразу по актуальной сохранённой самопроверке" in stored_ok
    assert "предупреждений: 1" in stored_ok
    assert "будет остановлен" in strict_stale
    assert "устарела для текущих настроек" in strict_stale
    assert "строгий режим требует новую проверку" in strict_stale
    assert "продолжит запуск" in force_failed
    assert "ошибок: 2" in force_failed
    assert "форсированный режим" in force_failed


def test_describe_run_launch_recommendation_guides_button_choice() -> None:
    auto = describe_run_launch_recommendation(
        auto_check_enabled=True,
        runtime_policy_key="balanced",
        summary=None,
        report_exists=False,
    )
    stored_ok = describe_run_launch_recommendation(
        auto_check_enabled=False,
        runtime_policy_key="balanced",
        summary={
            "ok": True,
            "errors": [],
            "warnings": ["minor"],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    )
    strict_missing = describe_run_launch_recommendation(
        auto_check_enabled=False,
        runtime_policy_key="strict",
        summary=None,
        report_exists=False,
    )
    force_failed = describe_run_launch_recommendation(
        auto_check_enabled=False,
        runtime_policy_key="force",
        summary={
            "ok": False,
            "errors": ["broken", "also broken"],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    )

    assert "можно нажимать «Запустить расчёт»" in auto
    assert "Проверить и запустить" in auto
    assert "можно запускать обычной кнопкой" in stored_ok
    assert "актуальная самопроверка" in stored_ok
    assert "используйте «Проверить и запустить»" in strict_missing
    assert "строгий режим" in strict_missing
    assert "лучше использовать «Проверить и запустить»" in force_failed
    assert "ошибок: 2" in force_failed
    assert "форсированном режиме" in force_failed


def test_describe_run_launch_target_names_preview_and_profile_routes() -> None:
    preview_target = describe_run_launch_target(
        launch_profile_key="baseline",
        scenario_key="worldroad",
        scenario_label="Дорога: текущий профиль preview",
    )
    full_target = describe_run_launch_target(
        launch_profile_key="full",
        scenario_key="roll",
        scenario_label="Крен на ступени",
    )

    assert preview_target["target_label"] == "краткий предпросмотр"
    assert preview_target["plain_button"] == "Запустить предпросмотр"
    assert preview_target["checked_button"] == "Проверить и запустить предпросмотр"
    assert "краткий предпросмотр дороги" in preview_target["hint_line"]
    assert full_target["target_label"] == "Полный расчёт"
    assert full_target["plain_button"] == "Запустить Полный расчёт"
    assert full_target["checked_button"] == "Проверить и запустить Полный расчёт"
    assert "Крен на ступени" in full_target["hint_line"]


def test_recommended_run_launch_action_prefers_plain_or_checked_flow() -> None:
    assert recommended_run_launch_action(
        auto_check_enabled=True,
        summary=None,
        report_exists=False,
    ) == "plain_launch"
    assert recommended_run_launch_action(
        auto_check_enabled=False,
        summary={
            "ok": True,
            "errors": [],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    ) == "plain_launch"
    assert recommended_run_launch_action(
        auto_check_enabled=False,
        summary=None,
        report_exists=False,
    ) == "check_then_launch"
    assert recommended_run_launch_action(
        auto_check_enabled=False,
        summary={
            "ok": False,
            "errors": ["broken"],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    ) == "check_then_launch"
    assert recommended_run_launch_action(
        auto_check_enabled=False,
        summary={
            "ok": True,
            "errors": [],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=True,
    ) == "check_then_launch"


def test_describe_plain_launch_availability_marks_strict_blockers() -> None:
    auto = describe_plain_launch_availability(
        auto_check_enabled=True,
        runtime_policy_key="balanced",
        summary=None,
        report_exists=False,
    )
    strict_missing = describe_plain_launch_availability(
        auto_check_enabled=False,
        runtime_policy_key="strict",
        summary=None,
        report_exists=False,
    )
    balanced_stale = describe_plain_launch_availability(
        auto_check_enabled=False,
        runtime_policy_key="balanced",
        summary={
            "ok": True,
            "errors": [],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=True,
    )
    force_failed = describe_plain_launch_availability(
        auto_check_enabled=False,
        runtime_policy_key="force",
        summary={
            "ok": False,
            "errors": ["broken", "also broken"],
            "warnings": [],
        },
        report_exists=True,
        has_signature=True,
        is_stale=False,
    )

    assert auto["enabled"] is True
    assert "свежая самопроверка" in str(auto["detail"])
    assert strict_missing["enabled"] is False
    assert "строгий режим требует новую самопроверку" in str(strict_missing["detail"])
    assert balanced_stale["enabled"] is True
    assert "не подходит текущей конфигурации" in str(balanced_stale["detail"])
    assert force_failed["enabled"] is True
    assert "форсированный режим" in str(force_failed["detail"])
    assert "ошибок: 2" in str(force_failed["detail"])


def test_describe_selfcheck_freshness_and_signature_are_stable() -> None:
    signature_a = build_selfcheck_subject_signature(
        payload={"p": 1},
        run_settings={"launch_profile": "detail", "dt": 0.003},
    )
    signature_b = build_selfcheck_subject_signature(
        payload={"p": 1},
        run_settings={"launch_profile": "detail", "dt": 0.003},
    )
    signature_c = build_selfcheck_subject_signature(
        payload={"p": 2},
        run_settings={"launch_profile": "detail", "dt": 0.003},
    )

    assert signature_a == signature_b
    assert signature_a != signature_c
    assert describe_selfcheck_freshness(False, True) == "без привязки к текущей конфигурации"
    assert describe_selfcheck_freshness(True, False) == "актуален для текущих настроек"
    assert describe_selfcheck_freshness(True, True) == "устарел для текущих настроек"


def test_runtime_helpers_persist_stdout_json_and_remap_saved_files(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    saved = write_json_report_from_stdout(
        "preview started\n{\"ok\": true, \"rows\": 12}\npreview done",
        report_path,
    )

    outdir = tmp_path / "run"
    outdir.mkdir()
    df_main = outdir / "df_main.csv"
    df_main.write_text("time,value\n0,1\n", encoding="utf-8")
    summary = {"df_main": "C:/cache/df_main.csv", "missing": "C:/cache/other.csv"}

    key_a = desktop_single_run_cache_key(
        params={"a": 1},
        test_row={"имя": "demo"},
        dt=0.01,
        t_end=1.0,
        record_full=False,
        export_csv=True,
        export_npz=False,
        run_profile="detail",
    )
    key_b = desktop_single_run_cache_key(
        params={"a": 1},
        test_row={"имя": "demo"},
        dt=0.01,
        t_end=1.0,
        record_full=False,
        export_csv=True,
        export_npz=True,
        run_profile="detail",
    )

    assert saved == report_path
    assert json.loads(report_path.read_text(encoding="utf-8")) == {"ok": True, "rows": 12}
    assert remap_saved_files_to_dir(summary, outdir) == {"df_main": str(df_main)}
    assert key_a != key_b
