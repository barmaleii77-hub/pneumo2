from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_results_model import (
    DesktopResultsArtifact,
    DesktopResultsContextField,
    DesktopResultsSessionHandoff,
    DesktopResultsSnapshot,
    format_npz_summary,
    format_optimizer_gate_summary,
    format_result_context_summary,
    format_triage_summary,
    format_validation_summary,
)
from pneumo_solver_ui.desktop_results_runtime import (
    COMPARE_CURRENT_CONTEXT_SIDECAR_JSON,
    DesktopResultsRuntime,
)
from pneumo_solver_ui.tools.desktop_results_center import _artifact_matches_filters
from pneumo_solver_ui.tools.send_bundle_contract import ANIM_DIAG_SIDECAR_JSON


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_desktop_results_session_handoff_model_defaults() -> None:
    handoff = DesktopResultsSessionHandoff(summary="rc=0")

    assert handoff.summary == "rc=0"
    assert handoff.detail == ""
    assert handoff.step_lines == ()
    assert handoff.zip_path is None


def test_desktop_results_center_browse_filter_matches_category_and_query() -> None:
    artifact = DesktopResultsArtifact(
        key="validation_json",
        title="Проверка текущего прогона в JSON",
        category="validation",
        path=Path("C:/tmp/latest_send_bundle_validation.json"),
        detail="Закреплено из последней локальной точки передачи.",
    )

    assert _artifact_matches_filters(artifact, category="all", query="")
    assert _artifact_matches_filters(artifact, category="validation", query="send_bundle")
    assert _artifact_matches_filters(artifact, category="validation", query="текущего прогона")
    assert not _artifact_matches_filters(artifact, category="triage", query="")
    assert not _artifact_matches_filters(artifact, category="validation", query="animator")


def test_desktop_results_center_uses_split_workspace_and_scrollable_summary_panel() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_results_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(self, orient="horizontal")' in src
    assert 'left_pane = ttk.Panedwindow(left_column, orient="vertical")' in src
    assert 'right_pane = ttk.Panedwindow(right_column, orient="vertical")' in src
    assert "summary_host = ScrollableFrame(right_pane)" in src
    assert 'ttk.Sizegrip(footer).pack(side="right")' in src
    assert 'text="Обновить результаты"' in src
    assert 'text="Обновить"' not in src
    assert '"open_send_center": "открыто копирование архива"' in src
    assert '"open_diagnostics_gui": "открыта проверка проекта"' in src
    assert 'success_message="Открыто копирование архива."' in src
    assert 'text="Сохранить архив проекта"' in src
    assert "Материалы проверки проекта" in src
    assert "Перейти к рекомендованной проверке" in src
    assert "открыт центр отправки" not in src
    assert "Открыт центр отправки" not in src
    for forbidden in (
        "Собрать диагностику",
        "Материалы диагностики",
        "Открыть последнюю диагностику",
        "Сохранить материалы диагностики",
        "Открыта диагностика проекта",
        "Показать рекомендованный раздел",
    ):
        assert forbidden not in src


def test_desktop_results_center_refreshes_analysis_evidence_before_opening_send_center() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_results_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    block = src.split('elif action == "open_send_center":', 1)[1].split(
        'elif action == "open_send_bundles":',
        1,
    )[0]

    assert "write_diagnostics_evidence_manifest(" in block
    assert block.index("write_diagnostics_evidence_manifest(") < block.index("launch_send_results_gui()")


def test_test_center_gui_uses_left_controls_and_right_log_workspace() -> None:
    tool_src = (UI_ROOT / "tools" / "test_center_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'run_split = ttk.Panedwindow(run_tab, orient="horizontal")' in tool_src
    assert 'summary_box = ttk.LabelFrame(config_body, text="Сводка работы", padding=pad)' in tool_src
    assert 'btns = ttk.LabelFrame(config_body, text="Команды", padding=pad)' in tool_src
    assert 'ttk.Button(header_actions, text="Результаты", command=lambda: self.notebook.select(self.results_center)).pack(side="left", padx=(8, 0))' in tool_src
    assert 'ttk.LabelFrame(config_body, text="Набор испытаний", padding=pad)' in tool_src
    assert "Снимок набора испытаний" in tool_src
    assert "Включено испытаний:" in tool_src
    assert "Ссылки на исходные данные:" in tool_src
    assert "контроль=" not in tool_src
    assert "включено=" not in tool_src
    assert "Подготовить пакет" not in tool_src
    assert "Пакеты отправки" not in tool_src
    assert "Открыть папку пакетов" not in tool_src
    assert "Команда запуска:" not in tool_src
    assert "▶" not in tool_src
    assert "■" not in tool_src
    assert 'text="Открыть снимок набора"' in tool_src
    assert "read_desktop_suite_handoff_state" in tool_src


def test_desktop_results_runtime_collects_latest_validation_and_artifacts(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    autotest_run = repo_root / "pneumo_solver_ui" / "autotest_runs" / "AT_001"
    diagnostics_run = repo_root / "diagnostics_runs" / "DG_001"
    autotest_run.mkdir(parents=True, exist_ok=True)
    diagnostics_run.mkdir(parents=True, exist_ok=True)

    zip_path = send_bundles / "bundle_001.zip"
    zip_path.write_bytes(b"zip")
    (send_bundles / "latest_send_bundle_path.txt").write_text(str(zip_path), encoding="utf-8")
    (send_bundles / "latest_send_bundle_validation.md").write_text("# validation\n", encoding="utf-8")
    (send_bundles / "latest_triage_report.json").write_text(
        json.dumps(
            {
                "severity_counts": {
                    "critical": 1,
                    "warn": 2,
                    "info": 3,
                },
                "red_flags": [
                    "Desktop Mnemo recent: Большой перепад давлений",
                ],
                "operator_recommendations": [
                    "Open Desktop Animator first and inspect Mnemo red flags before send.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (send_bundles / "latest_triage_report.md").write_text("# triage\n", encoding="utf-8")
    (send_bundles / "latest_dashboard.html").write_text("<html></html>", encoding="utf-8")
    (send_bundles / ANIM_DIAG_SIDECAR_JSON).write_text("{}", encoding="utf-8")
    (send_bundles / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "ok": True,
                "errors": [],
                "warnings": ["warn-a", "warn-b"],
                "optimizer_scope_gate": {
                    "release_gate": "FAIL",
                    "release_risk": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    latest_npz = repo_root / "workspace" / "exports" / "anim_latest.npz"
    latest_pointer = repo_root / "workspace" / "exports" / "anim_latest.json"
    latest_capture_manifest = repo_root / "workspace" / "exports" / "capture_export_manifest.json"
    latest_event_log = repo_root / "workspace" / "exports" / "anim_latest.desktop_mnemo_events.json"
    latest_npz.parent.mkdir(parents=True, exist_ok=True)
    latest_npz.write_bytes(b"npz")
    latest_pointer.write_text("{}", encoding="utf-8")
    latest_capture_manifest.write_text(
        json.dumps(
            {
                "schema": "capture_export_manifest.v1",
                "handoff_id": "HO-010",
                "capture_hash": "capture-hash-010",
                "analysis_context_hash": "analysis-context-hash-010",
                "analysis_context_refs": {
                    "analysis_context_status": "READY",
                    "animator_link_contract_hash": "animator-link-010",
                    "selected_run_contract_hash": "selected-run-010",
                    "selected_test_id": "T03",
                    "selected_npz_path": str(latest_npz),
                    "objective_contract_hash": "objective-010",
                    "suite_snapshot_hash": "suite-010",
                    "problem_hash": "problem-010",
                },
                "truth_mode_hash": "truth-mode-010",
                "truth_summary": {"overall_truth_state": "READY"},
                "blocking_states": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    latest_event_log.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.collect_anim_latest_diagnostics_summary",
        lambda include_meta=True: {
            "anim_latest_npz_path": str(latest_npz),
            "anim_latest_pointer_json": str(latest_pointer),
            "anim_latest_capture_export_manifest_path": str(latest_capture_manifest),
            "anim_latest_capture_export_manifest_handoff_id": "HO-010",
            "anim_latest_capture_hash": "capture-hash-010",
            "anim_latest_analysis_context_hash": "analysis-context-hash-010",
            "anim_latest_analysis_context_status": "READY",
            "anim_latest_animator_link_contract_hash": "animator-link-010",
            "anim_latest_selected_run_contract_hash": "selected-run-010",
            "anim_latest_selected_test_id": "T03",
            "anim_latest_selected_npz_path": str(latest_npz),
            "anim_latest_objective_contract_hash": "objective-010",
            "anim_latest_suite_snapshot_hash": "suite-010",
            "anim_latest_problem_hash": "problem-010",
            "anim_latest_truth_mode_hash": "truth-mode-010",
            "anim_latest_capture_export_manifest_blocking_states": [],
            "anim_latest_capture_export_manifest_truth_state": "READY",
            "anim_latest_mnemo_event_log_path": str(latest_event_log),
            "anim_latest_mnemo_event_log_current_mode": "Регуляторный коридор",
            "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений"],
        },
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.load_latest_send_bundle_anim_dashboard",
        lambda out_dir: {"visual_cache_token": "tok-123"},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.format_anim_dashboard_brief_lines",
        lambda anim: [f"token={anim.get('visual_cache_token')}"],
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.build_anim_operator_recommendations",
        lambda anim: ["Open Desktop Animator first", "Then inspect Compare Viewer"],
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    snapshot = runtime.snapshot()

    assert snapshot.latest_zip_path == zip_path.resolve()
    assert snapshot.validation_ok is True
    assert snapshot.validation_error_count == 0
    assert snapshot.validation_warning_count == 2
    assert snapshot.triage_critical_count == 1
    assert snapshot.triage_warn_count == 2
    assert snapshot.triage_info_count == 3
    assert snapshot.validation_errors == ()
    assert snapshot.validation_warnings == ("warn-a", "warn-b")
    assert snapshot.triage_red_flags == ("Недавнее событие мнемосхемы: Большой перепад давлений",)
    assert snapshot.optimizer_scope_gate == "FAIL"
    assert snapshot.optimizer_scope_gate_reason == ""
    assert snapshot.optimizer_scope_release_risk is True
    overview = {row.key: row for row in snapshot.validation_overview_rows}
    assert overview["send_bundle_validation"].status == "WARN"
    assert "предупреждений: 2" in overview["send_bundle_validation"].detail
    assert overview["send_bundle_validation"].action_key == "open_artifact"
    assert overview["selected_result_context"].status == "CURRENT"
    assert overview["selected_result_context"].action_key == "export_diagnostics_evidence"
    assert overview["triage_report"].status == "CRITICAL"
    assert "критично: 1" in overview["triage_report"].detail
    assert overview["triage_report"].action_key == "open_artifact"
    assert overview["anim_latest_results"].status == "READY"
    assert overview["anim_latest_results"].action_key == "open_compare_viewer"
    assert overview["animator_pointer"].status == "READY"
    assert overview["animator_pointer"].action_key == "open_animator_follow"
    assert overview["capture_export_manifest"].status == "READY"
    assert overview["capture_export_manifest"].action_key == "open_artifact"
    assert overview["capture_export_manifest"].artifact_key == "capture_export_manifest"
    assert "capture-hash-010" in overview["capture_export_manifest"].detail
    assert overview["bundle_sidecars"].status == "READY"
    assert overview["bundle_sidecars"].action_key == "open_send_center"
    assert snapshot.latest_npz_path == latest_npz.resolve()
    assert snapshot.latest_pointer_json_path == latest_pointer.resolve()
    assert snapshot.latest_capture_export_manifest_path == latest_capture_manifest.resolve()
    assert snapshot.latest_capture_export_manifest_status == "READY"
    assert snapshot.latest_capture_export_manifest_handoff_id == "HO-010"
    assert snapshot.latest_capture_hash == "capture-hash-010"
    assert snapshot.result_context_state == "CURRENT"
    context_fields = {field.key: field for field in snapshot.result_context_fields}
    assert context_fields["analysis_context_hash"].current_value == "analysis-context-hash-010"
    assert context_fields["analysis_context_hash"].selected_value == "analysis-context-hash-010"
    assert context_fields["selected_npz_path"].current_value == str(latest_npz)
    assert context_fields["selected_npz_path"].selected_value == str(latest_npz)
    assert snapshot.latest_mnemo_event_log_path == latest_event_log.resolve()
    assert snapshot.latest_autotest_run_dir == autotest_run.resolve()
    assert snapshot.latest_diagnostics_run_dir == diagnostics_run.resolve()
    assert snapshot.anim_summary_lines == ("token=tok-123",)
    assert snapshot.operator_recommendations[0] == (
        "Сначала откройте аниматор и проверьте красные флаги мнемосхемы перед сохранением архива проекта."
    )
    assert snapshot.mnemo_current_mode == "Регуляторный коридор"
    assert snapshot.mnemo_recent_titles == ("Большой перепад давлений",)
    assert snapshot.suggested_next_step == (
        "Сначала откройте аниматор и проверьте красные флаги мнемосхемы перед сохранением архива проекта."
    )
    assert snapshot.suggested_next_detail == "Недавнее событие мнемосхемы: Большой перепад давлений"
    assert snapshot.suggested_next_action_key == "open_animator_follow"
    assert snapshot.suggested_next_artifact_key == "latest_pointer"

    titles = {item.title for item in snapshot.recent_artifacts}
    assert "Последний архив проекта" in titles
    assert "Отчёт проверки" in titles
    assert "Последний файл анимации" in titles
    assert "Запись сохранения анимации" in titles
    assert "Журнал событий мнемосхемы" in titles

    validation_artifact = next(
        item for item in snapshot.recent_artifacts if item.key == "validation_json"
    )
    preview = runtime.artifact_preview_lines(validation_artifact)
    triage_artifact = runtime.artifact_by_key(snapshot, "triage_json")
    assert triage_artifact is not None
    assert triage_artifact.key == "triage_json"
    overview_artifact = runtime.overview_evidence_artifact(snapshot, overview["animator_pointer"])
    assert overview_artifact is not None
    assert overview_artifact.key == "latest_pointer"
    capture_artifact = runtime.overview_evidence_artifact(snapshot, overview["capture_export_manifest"])
    assert capture_artifact is not None
    assert capture_artifact.key == "capture_export_manifest"
    capture_preview = runtime.artifact_preview_lines(capture_artifact)
    assert "Тип: сохранение анимации" in capture_preview
    assert "Метка записи: capture-hash-010" in capture_preview
    assert "Данные анализа: готово" in capture_preview
    assert not any("handoff_id=" in line or "schema=" in line for line in capture_preview)
    session_artifacts = runtime.session_artifacts(
        snapshot,
        DesktopResultsSessionHandoff(
            summary="rc=0 | duration=1.0s",
            detail="Pinned current run.",
            step_lines=("Autotest: rc=0", "Diagnostics: rc=0"),
            zip_path=zip_path.resolve(),
            autotest_run_dir=autotest_run.resolve(),
            diagnostics_run_dir=diagnostics_run.resolve(),
        ),
    )
    session_titles = {item.title for item in session_artifacts}
    session_keys = {item.key for item in session_artifacts}
    session_categories = {item.key: item.category for item in session_artifacts}
    assert "Архив текущего прогона" in session_titles
    assert "Данные проверки текущего прогона" in session_titles
    assert "Данные разбора замечаний текущего прогона" in session_titles
    assert "Анимация текущего прогона" in session_titles
    assert "Запись сохранения анимации текущего прогона" in session_titles
    assert "session_send_bundle_zip" in session_keys
    assert "session_validation_json" in session_keys
    assert "session_capture_export_manifest" in session_keys
    assert session_categories["session_send_bundle_zip"] == "bundle"
    assert session_categories["session_validation_json"] == "validation"
    assert session_categories["session_triage_json"] == "triage"
    assert session_categories["session_latest_pointer"] == "results"
    preferred_validation = runtime.preferred_artifact_by_key(
        snapshot,
        "validation_json",
        handoff=DesktopResultsSessionHandoff(
            summary="rc=0 | duration=1.0s",
            detail="Pinned current run.",
            step_lines=("Autotest: rc=0",),
            zip_path=zip_path.resolve(),
            autotest_run_dir=autotest_run.resolve(),
            diagnostics_run_dir=diagnostics_run.resolve(),
        ),
    )
    assert preferred_validation is not None
    assert preferred_validation.key == "session_validation_json"
    preferred_triage = runtime.preferred_artifact_by_key(
        snapshot,
        "triage_json",
        handoff=DesktopResultsSessionHandoff(
            summary="rc=0 | duration=1.0s",
            detail="Pinned current run.",
            step_lines=("Autotest: rc=0",),
            zip_path=zip_path.resolve(),
            autotest_run_dir=autotest_run.resolve(),
            diagnostics_run_dir=diagnostics_run.resolve(),
        ),
    )
    assert preferred_triage is not None
    assert preferred_triage.key == "session_triage_json"
    preferred_pointer = runtime.preferred_artifact_by_key(
        snapshot,
        "latest_pointer",
        handoff=DesktopResultsSessionHandoff(
            summary="rc=0 | duration=1.0s",
            detail="Pinned current run.",
            step_lines=("Autotest: rc=0",),
            zip_path=zip_path.resolve(),
            autotest_run_dir=autotest_run.resolve(),
            diagnostics_run_dir=diagnostics_run.resolve(),
        ),
    )
    assert preferred_pointer is not None
    assert preferred_pointer.key == "session_latest_pointer"
    preferred_overview_artifact = runtime.preferred_overview_evidence_artifact(
        snapshot,
        overview["animator_pointer"],
        handoff=DesktopResultsSessionHandoff(
            summary="rc=0 | duration=1.0s",
            detail="Pinned current run.",
            step_lines=("Autotest: rc=0",),
            zip_path=zip_path.resolve(),
            autotest_run_dir=autotest_run.resolve(),
            diagnostics_run_dir=diagnostics_run.resolve(),
        ),
    )
    assert preferred_overview_artifact is not None
    assert preferred_overview_artifact.key == "session_latest_pointer"
    assert preview[:4] == (
        "Проверка: пройдена",
        "Ошибок: 0",
        "Предупреждений: 2",
        "Оптимизация: ошибка",
    )
    assert "Предупреждение: warn-a" in preview
    assert not any("ok=" in line or "errors=" in line or "warnings=" in line for line in preview)

    assert format_validation_summary(snapshot).startswith("Проверка: Норма")
    assert "Оптимизация: ошибка" in format_optimizer_gate_summary(snapshot)
    assert "FAIL" not in format_optimizer_gate_summary(snapshot)
    assert "критичных: 1" in format_triage_summary(snapshot)
    assert "anim_latest.npz" in format_npz_summary(snapshot)
    assert format_result_context_summary(snapshot).startswith("Результаты расчёта:")

    manifest_payload = runtime.build_diagnostics_evidence_manifest(snapshot)
    assert manifest_payload["result_context"]["state"] == "CURRENT"
    assert manifest_payload["mismatch_summary"]["state"] == "CURRENT"
    assert manifest_payload["result_context"]["current"]["analysis_context_hash"] == "analysis-context-hash-010"
    assert manifest_payload["result_context"]["selected"]["analysis_context_hash"] == "analysis-context-hash-010"
    assert manifest_payload["result_context"]["current"]["selected_npz_path"] == str(latest_npz)
    assert manifest_payload["result_context"]["selected"]["selected_npz_path"] == str(latest_npz)


def test_desktop_results_runtime_surfaces_stale_selected_result_context(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    validation_path = send_bundles / "latest_send_bundle_validation.json"
    validation_path.write_text(
        json.dumps(
            {
                "ok": True,
                "errors": [],
                "warnings": [],
                "result_context": {
                    "current": {
                        "run_id": "run-current",
                        "run_contract_hash": "run-hash-current",
                        "objective_contract_hash": "objective-current",
                        "scenario_lineage_hash": "ring-current",
                    },
                    "selected": {
                        "run_id": "run-historical",
                        "run_contract_hash": "run-hash-historical",
                        "objective_contract_hash": "objective-current",
                        "scenario_lineage_hash": "ring-historical",
                        "compare_contract_hash": "compare-001",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (send_bundles / "latest_send_bundle_validation.md").write_text(
        "# validation\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.collect_anim_latest_diagnostics_summary",
        lambda include_meta=True: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.load_latest_send_bundle_anim_dashboard",
        lambda out_dir: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.format_anim_dashboard_brief_lines",
        lambda anim: [],
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.build_anim_operator_recommendations",
        lambda anim: [],
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    snapshot = runtime.snapshot()
    overview = {row.key: row for row in snapshot.validation_overview_rows}
    context_fields = {field.key: field for field in snapshot.result_context_fields}

    assert snapshot.result_context_state == "STALE"
    assert "Текущая постановка отличается" in snapshot.result_context_banner
    assert "run_contract_hash" in snapshot.result_context_detail
    assert "scenario_lineage_hash" in snapshot.result_context_detail
    assert overview["selected_result_context"].status == "STALE"
    assert overview["selected_result_context"].action_key == "export_diagnostics_evidence"
    assert context_fields["objective_contract_hash"].status == "CURRENT"
    assert context_fields["run_contract_hash"].status == "STALE"
    assert context_fields["run_contract_hash"].selected_value == "run-hash-historical"
    assert context_fields["scenario_lineage_hash"].current_value == "ring-current"
    assert format_result_context_summary(snapshot) == "Результаты расчёта: устарели"


def test_desktop_results_runtime_surfaces_latest_optimizer_selected_run_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    workspace = repo_root / "pneumo_solver_ui" / "workspace"
    pointer_dir = workspace / "_pointers"
    contract_dir = workspace / "handoffs" / "WS-OPTIMIZATION"
    run_dir = workspace / "opt_runs" / "coord" / "p_selected_contract"
    send_bundles.mkdir(parents=True, exist_ok=True)
    pointer_dir.mkdir(parents=True, exist_ok=True)
    contract_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    selected_contract_path = contract_dir / "selected_run_contract.json"
    selected_contract_path.write_text(
        json.dumps(
            {
                "schema_version": "selected_run_contract_v1",
                "handoff_id": "HO-007",
                "run_id": "run-selected-001",
                "run_dir": str(run_dir),
                "objective_contract_hash": "objective-selected",
                "hard_gate_key": "penalty_total",
                "hard_gate_tolerance": 0.15,
                "problem_hash": "problem-selected",
                "problem_hash_mode": "stable",
                "active_baseline_hash": "baseline-selected",
                "suite_snapshot_hash": "suite-selected",
                "results_csv_path": str(run_dir / "export" / "trials.csv"),
                "analysis_handoff_ready_state": "ready",
                "selected_run_contract_hash": "selected-contract-001",
                "blocking_states": [],
                "warnings": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    latest_optimizer_pointer = pointer_dir / "latest_optimization.json"
    latest_optimizer_pointer.write_text(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "updated_at": "2026-04-17T12:00:00Z",
                "kind": "optimization",
                "meta": {
                    "selected_from": "desktop_optimizer_center",
                    "selected_run_contract_path": str(selected_contract_path),
                    "selected_run_contract_hash": "selected-contract-001",
                    "analysis_handoff_ready_state": "ready",
                    "status": "done",
                    "backend": "Ray",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (send_bundles / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "ok": True,
                "errors": [],
                "warnings": [],
                "result_context": {
                    "current": {
                        "run_id": "run-current-001",
                        "objective_contract_hash": "objective-current",
                        "problem_hash": "problem-current",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (send_bundles / "latest_send_bundle_validation.md").write_text("# validation\n", encoding="utf-8")

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.collect_anim_latest_diagnostics_summary",
        lambda include_meta=True: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.load_latest_send_bundle_anim_dashboard",
        lambda out_dir: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.format_anim_dashboard_brief_lines",
        lambda anim: [],
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.build_anim_operator_recommendations",
        lambda anim: [],
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    snapshot = runtime.snapshot()
    overview = {row.key: row for row in snapshot.validation_overview_rows}
    artifacts = {item.key: item for item in snapshot.recent_artifacts}
    fields = {field.key: field for field in snapshot.result_context_fields}

    assert snapshot.latest_optimizer_pointer_json_path == latest_optimizer_pointer.resolve()
    assert snapshot.latest_optimizer_run_dir == run_dir.resolve()
    assert snapshot.selected_run_contract_path == selected_contract_path.resolve()
    assert snapshot.selected_run_contract_hash == "selected-contract-001"
    assert snapshot.selected_run_contract_status == "READY"
    assert overview["selected_optimizer_run_contract"].status == "READY"
    assert overview["selected_optimizer_run_contract"].artifact_key == "selected_optimizer_run_contract"
    assert artifacts["selected_optimizer_run_contract"].path == selected_contract_path.resolve()
    assert artifacts["latest_optimizer_pointer"].path == latest_optimizer_pointer.resolve()
    assert snapshot.result_context_state == "STALE"
    assert fields["selected_run_contract_hash"].selected_value == "selected-contract-001"
    assert fields["selected_run_contract_path"].selected_value == str(selected_contract_path.resolve())
    assert fields["objective_contract_hash"].status == "STALE"
    assert fields["objective_contract_hash"].selected_value == "objective-selected"
    assert fields["problem_hash"].selected_value == "problem-selected"
    assert fields["active_baseline_hash"].selected_value == "baseline-selected"
    assert fields["suite_snapshot_hash"].selected_value == "suite-selected"

    manifest = runtime.build_diagnostics_evidence_manifest(snapshot)
    assert manifest["selected_run_contract_hash"] == "selected-contract-001"
    assert manifest["selected_run_contract_path"] == str(selected_contract_path.resolve())
    assert manifest["optimizer_selected_run_contract"]["status"] == "READY"
    assert manifest["result_context"]["selected"]["selected_run_contract_hash"] == "selected-contract-001"
    assert manifest["result_context"]["selected"]["active_baseline_hash"] == "baseline-selected"

    sidecar = runtime.build_compare_current_context_sidecar(snapshot)
    assert sidecar["optimizer_selected_run_contract"]["hash"] == "selected-contract-001"
    assert sidecar["artifacts"]["selected_run_contract_path"] == str(selected_contract_path.resolve())
    assert sidecar["selected_context_ref"]["selected_run_contract_path"] == str(selected_contract_path.resolve())


def test_desktop_results_runtime_warns_when_selected_contract_exists_without_pointer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    workspace = repo_root / "pneumo_solver_ui" / "workspace"
    contract_dir = workspace / "handoffs" / "WS-OPTIMIZATION"
    run_dir = workspace / "opt_runs" / "coord" / "p_selected_without_pointer"
    send_bundles.mkdir(parents=True, exist_ok=True)
    contract_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    selected_contract_path = contract_dir / "selected_run_contract.json"
    selected_contract_path.write_text(
        json.dumps(
            {
                "schema_version": "selected_run_contract_v1",
                "handoff_id": "HO-007",
                "run_id": "run-selected-no-pointer",
                "run_dir": str(run_dir),
                "objective_contract_hash": "objective-no-pointer",
                "hard_gate_key": "penalty_total",
                "hard_gate_tolerance": 0.15,
                "problem_hash": "problem-no-pointer",
                "problem_hash_mode": "stable",
                "active_baseline_hash": "baseline-no-pointer",
                "suite_snapshot_hash": "suite-no-pointer",
                "results_csv_path": str(run_dir / "export" / "trials.csv"),
                "analysis_handoff_ready_state": "ready",
                "selected_run_contract_hash": "selected-contract-no-pointer",
                "blocking_states": [],
                "warnings": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (send_bundles / "latest_send_bundle_validation.json").write_text(
        json.dumps({"ok": True, "errors": [], "warnings": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (send_bundles / "latest_send_bundle_validation.md").write_text("# validation\n", encoding="utf-8")

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.collect_anim_latest_diagnostics_summary",
        lambda include_meta=True: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.load_latest_send_bundle_anim_dashboard",
        lambda out_dir: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.format_anim_dashboard_brief_lines",
        lambda anim: [],
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.build_anim_operator_recommendations",
        lambda anim: [],
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    snapshot = runtime.snapshot()
    overview = {row.key: row for row in snapshot.validation_overview_rows}
    artifacts = {item.key: item for item in snapshot.recent_artifacts}
    fields = {field.key: field for field in snapshot.result_context_fields}

    assert snapshot.latest_optimizer_pointer_json_path is None
    assert snapshot.latest_optimizer_run_dir == run_dir.resolve()
    assert snapshot.selected_run_contract_path == selected_contract_path.resolve()
    assert snapshot.selected_run_contract_hash == "selected-contract-no-pointer"
    assert snapshot.selected_run_contract_status == "WARN"
    assert "закреплённые данные анализа отсутствуют" in snapshot.selected_run_contract_banner
    assert overview["selected_optimizer_run_contract"].status == "WARN"
    assert overview["selected_optimizer_run_contract"].artifact_key == "selected_optimizer_run_contract"
    assert artifacts["selected_optimizer_run_contract"].path == selected_contract_path.resolve()
    assert "latest_optimizer_pointer" not in artifacts
    assert fields["selected_run_contract_hash"].selected_value == "selected-contract-no-pointer"
    assert fields["selected_run_contract_path"].selected_value == str(selected_contract_path.resolve())
    assert fields["objective_contract_hash"].selected_value == "objective-no-pointer"
    assert fields["problem_hash"].selected_value == "problem-no-pointer"

    manifest = runtime.build_diagnostics_evidence_manifest(snapshot)
    assert manifest["optimizer_selected_run_contract"]["status"] == "WARN"
    assert manifest["optimizer_selected_run_contract"]["path"] == str(selected_contract_path.resolve())
    assert manifest["optimizer_selected_run_contract"]["latest_optimizer_pointer_path"] == ""

    sidecar = runtime.build_compare_current_context_sidecar(snapshot)
    assert sidecar["optimizer_selected_run_contract"]["status"] == "WARN"
    assert sidecar["optimizer_selected_run_contract"]["latest_optimizer_pointer_path"] == ""
    assert sidecar["artifacts"]["selected_run_contract_path"] == str(selected_contract_path.resolve())


def test_desktop_results_runtime_keeps_validation_report_visible_without_json(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    validation_md = send_bundles / "latest_send_bundle_validation.md"
    validation_md.write_text("# validation\noperator report\n", encoding="utf-8")

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.collect_anim_latest_diagnostics_summary",
        lambda include_meta=True: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.load_latest_send_bundle_anim_dashboard",
        lambda out_dir: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.format_anim_dashboard_brief_lines",
        lambda anim: [],
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.build_anim_operator_recommendations",
        lambda anim: [],
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    snapshot = runtime.snapshot()
    overview = {row.key: row for row in snapshot.validation_overview_rows}
    validation_artifact = runtime.artifact_by_key(snapshot, "validation_json")

    assert snapshot.latest_validation_json_path is None
    assert snapshot.latest_validation_md_path == validation_md.resolve()
    assert overview["send_bundle_validation"].evidence_path == validation_md.resolve()
    assert overview["send_bundle_validation"].artifact_key == "validation_md"
    assert validation_artifact is not None
    assert validation_artifact.key == "validation_md"
    assert "Отчёт проверки" in {item.title for item in snapshot.recent_artifacts}


def test_desktop_results_runtime_exports_diagnostics_evidence_manifest_input(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    (send_bundles / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "ok": True,
                "errors": [],
                "warnings": [],
                "result_context": {
                    "current": {
                        "run_id": "run-777",
                        "run_contract_hash": "run-hash-777",
                        "analysis_context_hash": "analysis-777",
                        "compare_contract_hash": "compare-777",
                    },
                    "selected": {
                        "run_id": "run-777",
                        "run_contract_hash": "run-hash-777",
                        "analysis_context_hash": "analysis-777",
                        "compare_contract_hash": "compare-777",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (send_bundles / "latest_send_bundle_validation.md").write_text("# validation\n", encoding="utf-8")
    latest_npz = repo_root / "pneumo_solver_ui" / "workspace" / "exports" / "anim_latest.npz"
    latest_pointer = latest_npz.with_suffix(".json")
    latest_npz.parent.mkdir(parents=True, exist_ok=True)
    latest_npz.write_bytes(b"npz")
    latest_pointer.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.collect_anim_latest_diagnostics_summary",
        lambda include_meta=True: {
            "anim_latest_npz_path": str(latest_npz),
            "anim_latest_pointer_json": str(latest_pointer),
            "anim_latest_visual_cache_token": "tok-777",
            "anim_latest_capture_export_manifest_handoff_id": "HO-010",
            "anim_latest_capture_hash": "capture-777",
            "anim_latest_analysis_context_hash": "analysis-777",
            "anim_latest_analysis_context_status": "READY",
            "anim_latest_animator_link_contract_hash": "animator-link-777",
            "anim_latest_selected_run_contract_hash": "run-hash-777",
            "anim_latest_selected_test_id": "T01",
            "anim_latest_selected_npz_path": str(latest_npz),
            "anim_latest_objective_contract_hash": "objective-777",
            "anim_latest_suite_snapshot_hash": "suite-777",
            "anim_latest_problem_hash": "problem-777",
            "anim_latest_truth_mode_hash": "truth-777",
        },
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.load_latest_send_bundle_anim_dashboard",
        lambda out_dir: {},
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.format_anim_dashboard_brief_lines",
        lambda anim: [],
    )
    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.build_anim_operator_recommendations",
        lambda anim: [],
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    snapshot = runtime.snapshot()
    manifest_path = runtime.write_diagnostics_evidence_manifest(
        snapshot,
        handoff=DesktopResultsSessionHandoff(
            summary="rc=0",
            detail="Pinned run.",
            step_lines=("Autotest: rc=0",),
        ),
    )
    workspace_manifest = (
        repo_root / "pneumo_solver_ui" / "workspace" / "exports" / "analysis_evidence_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    refreshed = runtime.snapshot()
    artifact_keys = {item["key"] for item in payload["selected_artifact_list"]}
    fields = {field.key: field for field in snapshot.result_context_fields}

    assert manifest_path == (send_bundles / "latest_analysis_evidence_manifest.json").resolve()
    assert workspace_manifest.exists()
    assert payload["schema"] == "desktop_results_evidence_manifest"
    assert payload["handoff_id"] == "HO-009"
    assert payload["produced_by"] == "WS-ANALYSIS"
    assert payload["consumed_by"] == "WS-DIAGNOSTICS"
    assert payload["run_id"] == "run-777"
    assert payload["run_contract_hash"] == "run-hash-777"
    assert payload["compare_contract_id"] == "compare-777"
    assert payload["result_context"]["selected"]["analysis_context_status"] == "READY"
    assert payload["result_context"]["selected"]["animator_link_contract_hash"] == "animator-link-777"
    assert payload["result_context"]["selected"]["selected_run_contract_hash"] == "run-hash-777"
    assert payload["result_context"]["selected"]["selected_test_id"] == "T01"
    assert payload["result_context"]["selected"]["selected_npz_path"] == str(latest_npz)
    assert payload["result_context"]["selected"]["objective_contract_hash"] == "objective-777"
    assert payload["result_context"]["selected"]["suite_snapshot_hash"] == "suite-777"
    assert payload["result_context"]["selected"]["problem_hash"] == "problem-777"
    assert payload["result_context"]["selected"]["capture_export_manifest_handoff_id"] == "HO-010"
    assert payload["result_context"]["selected"]["capture_hash"] == "capture-777"
    assert payload["result_context"]["selected"]["truth_mode_hash"] == "truth-777"
    assert fields["analysis_context_status"].title == "Состояние данных анализа"
    assert fields["animator_link_contract_hash"].title == "Метка данных анимации"
    assert fields["selected_npz_path"].selected_value == str(latest_npz)
    assert payload["result_context"]["state"] == "CURRENT"
    assert payload["mismatch_summary"]["state"] == "CURRENT"
    assert payload["evidence_manifest_hash"]
    assert "validation_json" in artifact_keys
    assert "latest_npz" in artifact_keys
    assert payload["selected_filters"]["handoff_present"] is True
    assert refreshed.diagnostics_evidence_manifest_path == manifest_path
    assert refreshed.diagnostics_evidence_manifest_status == "READY"
    assert refreshed.diagnostics_evidence_manifest_hash == payload["evidence_manifest_hash"]

    compare_sidecar_path = runtime.write_compare_current_context_sidecar(snapshot)
    compare_sidecar = json.loads(compare_sidecar_path.read_text(encoding="utf-8"))

    assert compare_sidecar_path.name == COMPARE_CURRENT_CONTEXT_SIDECAR_JSON
    assert compare_sidecar["schema"] == "desktop_results_compare_current_context"
    assert compare_sidecar["readonly"] is True
    assert compare_sidecar["current_context_ref"]["run_id"] == "run-777"
    assert compare_sidecar["selected_context_ref"]["compare_contract_hash"] == "compare-777"
    assert compare_sidecar["mismatch_banner"]["banner_id"] == "BANNER-HIST-001"
    assert compare_sidecar["current_context_ref_hash"]

    refreshed_with_compare = runtime.snapshot()
    compare_artifact = runtime.artifact_by_key(
        refreshed_with_compare,
        "compare_current_context_sidecar",
    )
    assert compare_artifact is not None
    assert compare_artifact.path == compare_sidecar_path
    assert compare_artifact.category == "evidence"
    assert compare_artifact.detail == "Материалы для сравнения результатов расчёта."
    compare_preview = runtime.artifact_preview_lines(compare_artifact)
    assert "Тип: данные сравнения" in compare_preview
    assert "Состояние данных: текущий" in compare_preview
    assert "Согласование: BANNER-HIST-001" in compare_preview
    assert not any("schema=" in line or "handoff_id=" in line or "context_state=" in line for line in compare_preview)


def test_desktop_results_runtime_builds_branch_args() -> None:
    npz_path = Path("C:/tmp/anim_latest.npz")
    pointer_path = Path("C:/tmp/anim_latest.json")
    pointer_artifact = type("Artifact", (), {"path": pointer_path, "category": "results"})()
    npz_artifact = type("Artifact", (), {"path": npz_path, "category": "results"})()
    mnemo_log_path = Path("C:/tmp/anim_latest.desktop_mnemo_events.json")
    mnemo_artifact = type("Artifact", (), {"path": mnemo_log_path, "category": "results"})()
    snapshot = DesktopResultsSnapshot(
        latest_zip_path=None,
        latest_validation_json_path=None,
        latest_validation_md_path=None,
        latest_triage_json_path=None,
        latest_triage_md_path=None,
        latest_dashboard_html_path=None,
        latest_anim_diag_json_path=None,
        latest_npz_path=npz_path,
        latest_pointer_json_path=pointer_path,
        latest_mnemo_event_log_path=None,
        latest_autotest_run_dir=None,
        latest_diagnostics_run_dir=None,
        validation_ok=None,
        validation_error_count=0,
        validation_warning_count=0,
        triage_critical_count=0,
        triage_warn_count=0,
        triage_info_count=0,
        validation_errors=(),
        validation_warnings=(),
        triage_red_flags=(),
        optimizer_scope_gate="",
        optimizer_scope_gate_reason="",
        optimizer_scope_release_risk=None,
        anim_summary_lines=(),
        operator_recommendations=(),
        mnemo_current_mode="",
        mnemo_recent_titles=(),
        suggested_next_step="",
        suggested_next_detail="",
        validation_overview_rows=(),
        recent_artifacts=(),
    )
    runtime = DesktopResultsRuntime(repo_root=Path.cwd(), python_executable="python")
    context_path = Path("C:/tmp/latest_compare_current_context.json")

    assert runtime.compare_viewer_args(snapshot) == [str(npz_path)]
    assert runtime.compare_viewer_args(
        snapshot,
        current_context_path=context_path,
    ) == [
        "--current-context",
        str(context_path),
        str(npz_path),
    ]
    assert runtime.animator_args(snapshot, follow=False) == [
        "--npz",
        str(npz_path),
        "--pointer",
        str(pointer_path),
        "--no-follow",
    ]
    assert runtime.animator_args(snapshot, follow=True) == [
        "--pointer",
        str(pointer_path),
    ]
    assert runtime.compare_viewer_args(snapshot, artifact=npz_artifact) == [str(npz_path)]
    assert runtime.compare_viewer_args(snapshot, artifact=pointer_artifact) == [str(npz_path)]
    assert runtime.animator_args(snapshot, follow=False, artifact=pointer_artifact) == [
        "--npz",
        str(npz_path),
        "--pointer",
        str(pointer_path),
        "--no-follow",
    ]
    assert runtime.animator_args(snapshot, follow=True, artifact=mnemo_artifact) == [
        "--pointer",
        str(pointer_path),
    ]


def test_desktop_results_runtime_launch_compare_viewer_writes_current_context_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    latest_npz = repo_root / "workspace" / "exports" / "anim_latest.npz"
    latest_npz.parent.mkdir(parents=True, exist_ok=True)
    latest_npz.write_bytes(b"npz")
    snapshot = DesktopResultsSnapshot(
        latest_zip_path=None,
        latest_validation_json_path=None,
        latest_validation_md_path=None,
        latest_triage_json_path=None,
        latest_triage_md_path=None,
        latest_dashboard_html_path=None,
        latest_anim_diag_json_path=None,
        latest_npz_path=latest_npz,
        latest_pointer_json_path=None,
        latest_mnemo_event_log_path=None,
        latest_autotest_run_dir=None,
        latest_diagnostics_run_dir=None,
        validation_ok=True,
        validation_error_count=0,
        validation_warning_count=0,
        triage_critical_count=0,
        triage_warn_count=0,
        triage_info_count=0,
        validation_errors=(),
        validation_warnings=(),
        triage_red_flags=(),
        optimizer_scope_gate="PASS",
        optimizer_scope_gate_reason="",
        optimizer_scope_release_risk=False,
        anim_summary_lines=(),
        operator_recommendations=(),
        mnemo_current_mode="",
        mnemo_recent_titles=(),
        suggested_next_step="",
        suggested_next_detail="",
        validation_overview_rows=(),
        recent_artifacts=(),
        result_context_state="STALE",
        result_context_banner="Текущая постановка отличается от результатов расчёта.",
        result_context_detail="objective_contract_hash",
        result_context_action="Открыть окно сравнения",
        result_context_fields=(
            DesktopResultsContextField(
                key="run_id",
                title="Номер прогона",
                current_value="run-current",
                selected_value="run-history",
                status="STALE",
                detail="run_id drift",
            ),
            DesktopResultsContextField(
                key="objective_contract_hash",
                title="Метка целевого профиля",
                current_value="obj-current",
                selected_value="obj-history",
                status="STALE",
                detail="objective drift",
            ),
        ),
    )
    captured: dict[str, object] = {}

    def _fake_spawn_module(module: str, args=None):
        captured["module"] = module
        captured["args"] = list(args or [])
        return {"module": module, "args": list(args or [])}

    monkeypatch.setattr(
        "pneumo_solver_ui.desktop_results_runtime.spawn_module",
        _fake_spawn_module,
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")
    result = runtime.launch_compare_viewer(snapshot)
    sidecar_path = runtime.compare_current_context_sidecar_path()
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert result == captured
    assert captured["module"] == "pneumo_solver_ui.qt_compare_viewer"
    assert captured["args"] == ["--current-context", str(sidecar_path), str(latest_npz)]
    assert payload["current_context_ref"]["objective_contract_hash"] == "obj-current"
    assert payload["selected_context_ref"]["objective_contract_hash"] == "obj-history"
    assert payload["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"
    assert payload["mismatch_banner"]["mismatch_dimensions"] == [
        "run_id",
        "objective_contract_hash",
    ]


def test_desktop_results_runtime_previews_selected_result_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    pointer_path = repo_root / "workspace" / "exports" / "anim_latest.json"
    mnemo_log_path = repo_root / "workspace" / "exports" / "anim_latest.desktop_mnemo_events.json"
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(
        json.dumps(
            {
                "updated_utc": "2026-04-13T10:00:00Z",
                "npz_path": str(pointer_path.with_suffix(".npz")),
                "visual_cache_token": "tok-preview",
                "visual_reload_inputs": ["npz", "road_csv"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    mnemo_log_path.write_text(
        json.dumps(
            {
                "current_mode": "Регуляторный коридор",
                "event_count": 4,
                "active_latch_count": 1,
                "acknowledged_latch_count": 2,
                "recent_events": [
                    {"title": "Большой перепад давлений"},
                    {"title": "Смена режима"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime = DesktopResultsRuntime(repo_root=repo_root, python_executable="python")

    pointer_artifact = type(
        "Artifact",
        (),
        {"key": "latest_pointer", "path": pointer_path, "category": "results"},
    )()
    mnemo_artifact = type(
        "Artifact",
        (),
        {"key": "mnemo_event_log", "path": mnemo_log_path, "category": "results"},
    )()

    pointer_preview = runtime.artifact_preview_lines(pointer_artifact)
    mnemo_preview = runtime.artifact_preview_lines(mnemo_artifact)

    assert "Метка готовых данных анимации: tok-preview" in pointer_preview
    assert "Состав данных анимации: ['npz', 'road_csv']" in pointer_preview
    assert "Режим: Регуляторный коридор" in mnemo_preview
    assert "Недавнее событие: Большой перепад давлений" in mnemo_preview

    triage_path = repo_root / "send_bundles" / "latest_triage_report.json"
    triage_path.parent.mkdir(parents=True, exist_ok=True)
    triage_path.write_text(
        json.dumps(
            {
                "severity_counts": {"critical": 0, "warn": 1, "info": 0},
                "red_flags": ["Pointer drift"],
                "operator_recommendations": ["Открыть Compare Viewer " "следующим шагом"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    triage_artifact = type(
        "Artifact",
        (),
        {"key": "triage_json", "path": triage_path, "category": "triage"},
    )()
    triage_preview = runtime.artifact_preview_lines(triage_artifact)

    assert "Замечания: критичных: 0; предупреждений: 1; справочных: 0" in triage_preview
    assert "Красный флаг: Расхождение данных сопровождения" in triage_preview
    assert "Рекомендация: Перейти к сравнению прогонов" in triage_preview
    assert "Открыть окно сравнения " "следующим шагом" not in triage_preview
    assert not any("severity_counts=" in line or "red_flag:" in line or "next:" in line for line in triage_preview)


def test_test_center_gui_embeds_validation_results_center_modules() -> None:
    tool_src = (UI_ROOT / "tools" / "test_center_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    center_src = (UI_ROOT / "tools" / "desktop_results_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    model_src = (UI_ROOT / "desktop_results_model.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_src = (UI_ROOT / "desktop_results_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "DesktopResultsRuntime" in tool_src
    assert "DesktopResultsSessionHandoff" in tool_src
    assert "DesktopResultsCenter" in tool_src
    assert "ttk.Notebook" in tool_src
    assert 'self.notebook.add(self.results_center, text="Результаты и анализ")' in tool_src
    assert "self.results_center.refresh()" in tool_src
    assert "self.results_center.set_session_handoff(" in tool_src
    assert "self.notebook.select(self.results_center)" in tool_src

    assert "class DesktopResultsCenter" in center_src
    assert "build_scrolled_treeview" in center_src
    assert "build_scrolled_text" in center_src
    assert "def refresh(self) -> None:" in center_src
    assert "Обзор проверок" in center_src
    assert "Рекомендация:" in center_src
    assert "Следующий шаг:" not in center_src
    assert "Данные результата:" not in center_src
    assert "Пояснение:" not in center_src
    assert "Материалы последнего прогона" in center_src
    assert "def set_session_handoff(" in center_src
    assert "Перейти к рекомендованной проверке" in center_src
    assert "Открыть последний архив" in center_src
    assert "Открыть текущую проверку" in center_src
    assert "Открыть текущий разбор замечаний" in center_src
    assert "Сравнить в отдельном окне" in center_src
    assert "Сравнить текущий прогон в отдельном окне" in center_src
    assert 'text="Сравнение"' not in center_src
    assert "Открыть текущее сравнение" not in center_src
    assert "Аниматор по результату" in center_src
    assert "Открыть текущую анимацию" in center_src
    assert "Открыть текущую визуализацию" not in center_src
    assert "Показать рекомендованный раздел" not in center_src
    assert 'text="Сопровождение"' not in center_src
    assert "Открыть последний ZIP" not in center_src
    assert "идентификатор:" not in center_src
    assert '"hash=": "идентификатор "' not in center_src
    assert "Артефакт" not in center_src
    assert "Validation & Results" not in center_src
    assert "Suggested next step launched." not in center_src
    assert "Контекст аниматора:" not in center_src
    assert "Проверка в JSON" not in center_src
    assert "Проверка в Markdown" not in center_src
    assert "def _preferred_handoff_artifact(" in center_src
    assert "Только текущий прогон" in center_src
    assert "Раздел:" in center_src
    assert "Все материалы" in center_src
    assert "Поиск:" in center_src
    assert "def _clear_browse_query(" in center_src
    assert "query=" in center_src
    assert "def _on_browse_scope_changed(" in center_src
    assert "def _artifact_matches_browse_filter(" in center_src
    assert "def _artifact_matches_filters(" in center_src
    assert "def _browse_scope_summary(" in center_src
    assert "Область просмотра:" in center_src
    assert "session_artifacts(" in center_src
    assert "Текущий прогон (закреплён)" in center_src
    assert "Последние материалы рабочей области" in center_src
    assert "preferred_artifact_by_key(" in center_src
    assert "preferred_overview_evidence_artifact(" in center_src
    assert "overview_tree_frame, self.overview_tree = build_scrolled_treeview(" in center_src
    assert "self.overview_tree.bind(\"<<TreeviewSelect>>\", self._on_overview_select)" in center_src
    assert "self.overview_tree.bind(\"<Double-1>\", self._on_overview_open)" in center_src
    assert "self.tree.bind(\"<Double-1>\", self._on_open_selected)" in center_src
    assert "Выполнить рекомендацию" in center_src
    assert "Выполнить следующий шаг" not in center_src
    assert "Выполнить действие по проверке" in center_src
    assert "artifact_preview_lines" in center_src
    assert "Предпросмотр:" in center_src
    assert "Красные флаги разбора замечаний:" in center_src
    assert "launch_compare_viewer" in center_src
    assert "launch_animator" in center_src
    assert "Предупреждения проверки:" in center_src
    assert "Файл для сравнения:" in center_src
    assert "artifact=self._selected_artifact()" in center_src

    assert "class DesktopResultsSnapshot" in model_src
    assert "class DesktopResultsOverviewRow" in model_src
    assert "class DesktopResultsSessionHandoff" in model_src
    assert "def format_validation_summary(" in model_src
    assert "def format_optimizer_gate_summary(" in model_src
    assert "def format_triage_summary(" in model_src
    assert "action_key: str = \"\"" in model_src
    assert "artifact_key: str = \"\"" in model_src
    assert "validation_errors: tuple[str, ...]" in model_src
    assert "triage_red_flags: tuple[str, ...]" in model_src
    assert "validation_overview_rows: tuple[DesktopResultsOverviewRow, ...]" in model_src
    assert "optimizer_scope_gate_reason: str" in model_src
    assert "suggested_next_step: str" in model_src
    assert "suggested_next_action_key: str = \"\"" in model_src
    assert "latest_optimizer_pointer_json_path: Path | None = None" in model_src
    assert "selected_run_contract_hash: str = \"\"" in model_src

    assert "class DesktopResultsRuntime" in runtime_src
    assert "def snapshot(self) -> DesktopResultsSnapshot:" in runtime_src
    assert "def artifact_preview_lines(" in runtime_src
    assert "DesktopResultsOverviewRow(" in runtime_src
    assert "key=\"triage_report\"" in runtime_src
    assert "_suggested_next_step" in runtime_src
    assert "def artifact_by_key(" in runtime_src
    assert "def overview_evidence_artifact(" in runtime_src
    assert "def session_artifacts(" in runtime_src
    assert "def preferred_artifact_by_key(" in runtime_src
    assert "def preferred_overview_evidence_artifact(" in runtime_src
    assert "Данные проверки текущего прогона" in runtime_src
    assert "Проверка текущего прогона в JSON" not in runtime_src
    assert "Разбор замечаний текущего прогона в JSON" not in runtime_src
    assert "Сводная HTML-страница" not in runtime_src
    assert "JSON-файл:" not in runtime_src
    assert "Предпросмотр JSON" not in runtime_src
    assert "Сначала откройте Desktop Animator" not in runtime_src
    assert "Откройте Compare Viewer " "следующим шагом" not in runtime_src
    assert "Метка визуального кэша" not in runtime_src
    assert "Входные данные перезагрузки" not in runtime_src
    assert "Данные для аниматора" not in runtime_src
    assert "Данные аниматора текущего прогона" not in runtime_src
    assert "Диагностика визуализации" not in runtime_src
    assert "Запись экспорта текущего прогона" not in runtime_src
    assert "Идентификатор" not in runtime_src
    assert "идентификатор" not in runtime_src
    assert "def compare_viewer_path(" in runtime_src
    assert "def animator_target_paths(" in runtime_src
    assert "def compare_viewer_args(" in runtime_src
    assert "write_compare_current_context_sidecar(" in runtime_src
    assert "latest_compare_current_context.json" in runtime_src
    assert "compare_current_context_sidecar" in runtime_src
    assert "selected_optimizer_run_contract" in runtime_src
    assert "latest_optimizer_pointer" in runtime_src
    assert "optimizer_selected_run_contract" in runtime_src
    assert "--current-context" in runtime_src
    assert "def animator_args(" in runtime_src
