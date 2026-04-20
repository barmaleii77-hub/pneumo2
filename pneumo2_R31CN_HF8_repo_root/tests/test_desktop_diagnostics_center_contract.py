from __future__ import annotations

import json
import hashlib
import zipfile
from pathlib import Path

from pneumo_solver_ui.desktop_diagnostics_model import (
    LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON,
    LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD,
    LATEST_SEND_BUNDLE_INSPECTION_JSON,
    DesktopDiagnosticsRequest,
    DesktopDiagnosticsRunRecord,
    build_run_full_diagnostics_command,
    parse_run_full_diagnostics_output_line,
)
from pneumo_solver_ui.desktop_diagnostics_runtime import (
    append_desktop_diagnostics_run_log,
    load_desktop_diagnostics_bundle_record,
    load_last_desktop_diagnostics_center_state,
    load_last_desktop_diagnostics_run_record,
    load_last_desktop_diagnostics_run_log_text,
    persist_desktop_diagnostics_run,
    refresh_desktop_diagnostics_bundle_record,
    write_desktop_diagnostics_summary_md,
    write_desktop_diagnostics_center_state,
)
from pneumo_solver_ui.tools.send_bundle_evidence import (
    ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME,
    EVIDENCE_MANIFEST_SIDECAR_NAME,
    GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME,
)


ROOT = Path(__file__).resolve().parents[1]


def _analysis_manifest(
    *,
    run_id: str = "run-001",
    manifest_hash: str = "hash-001",
    state: str = "CURRENT",
    mismatches: list[dict[str, str]] | None = None,
) -> dict:
    return {
        "schema": "desktop_results_evidence_manifest",
        "schema_version": "1.0.0",
        "handoff_id": "HO-009",
        "evidence_manifest_hash": manifest_hash,
        "run_id": run_id,
        "run_contract_hash": f"contract-{run_id}",
        "compare_contract_id": f"compare-{run_id}",
        "selected_artifact_list": [
            {"key": "validation_json", "path": "validation.json"},
            {"key": "latest_npz", "path": "anim_latest.npz"},
        ],
        "result_context": {"state": state, "selected": {"run_id": run_id}},
        "mismatch_summary": {"state": state, "mismatches": list(mismatches or [])},
    }


def _geometry_reference_evidence() -> dict:
    return {
        "schema": "geometry_reference_evidence.v1",
        "producer_owned": False,
        "reference_center_role": "reader_and_evidence_surface",
        "does_not_render_animator_meshes": True,
        "artifact_status": "current",
        "artifact_freshness_status": "current",
        "artifact_freshness_relation": "matches_latest",
        "artifact_freshness_reason": "Selected artifact matches latest by NPZ or pointer path.",
        "latest_artifact_status": "current",
        "artifact_source_label": "pytest",
        "road_width_status": "explicit_meta",
        "road_width_source": "meta.geometry.road_width_m",
        "packaging_status": "complete",
        "packaging_mismatch_status": "match",
        "packaging_contract_hash": "packaging-hash",
        "geometry_acceptance_gate": "PASS",
        "geometry_acceptance_available": True,
        "producer_artifact_status": "ready",
        "producer_readiness_reasons": [],
        "producer_evidence_owner": "producer_export",
        "producer_required_artifacts": [
            "workspace/_pointers/anim_latest.json or workspace/exports/anim_latest.json",
            "workspace/exports/anim_latest.npz",
            "workspace/exports/CYLINDER_PACKAGING_PASSPORT.json",
            "workspace/exports/geometry_acceptance_report.json",
        ],
        "producer_next_action": "No producer action required for this complete synthetic fixture.",
        "consumer_may_fabricate_geometry": False,
        "component_passport_components": 3,
        "component_passport_needs_data": 0,
        "evidence_missing": [],
    }


def _engineering_analysis_evidence() -> dict:
    return {
        "schema": "desktop_engineering_analysis_evidence_manifest",
        "schema_version": "1.0.0",
        "evidence_manifest_hash": "engineering-hash-001",
        "validation": {"status": "READY", "influence_status": "PASS", "calibration_status": "PASS"},
        "validated_artifacts": {
            "schema": "engineering_analysis_validated_artifacts.v1",
            "status": "READY",
            "required_artifact_count": 3,
            "ready_required_artifact_count": 3,
            "missing_required_artifact_count": 0,
            "missing_required_artifacts": [],
            "hash_ready_artifact_count": 3,
        },
        "handoff_requirements": {
            "handoff_id": "HO-007",
            "contract_status": "READY",
            "required_contract_path": "C:/workspace/handoffs/WS-OPTIMIZATION/selected_run_contract.json",
            "missing_fields": [],
            "can_run_engineering_analysis": True,
        },
        "selected_run_candidate_readiness": {
            "schema": "selected_run_candidate_readiness.v1",
            "candidate_count": 2,
            "ready_candidate_count": 1,
            "missing_inputs_candidate_count": 1,
            "failed_candidate_count": 0,
            "unique_missing_inputs": ["results_csv_path"],
            "ready_run_dirs": ["C:/workspace/opt_runs/coord/run_ready"],
        },
    }


def test_desktop_diagnostics_model_builds_headless_command_and_parses_paths() -> None:
    req = DesktopDiagnosticsRequest(
        level="full",
        skip_ui_smoke=True,
        no_zip=True,
        run_opt_smoke=True,
        opt_minutes=5,
        opt_jobs=3,
        osc_dir="C:/tmp/osc",
        out_root="C:/tmp/diagnostics",
    )

    cmd = build_run_full_diagnostics_command("python", Path("tool.py"), req)
    assert cmd == [
        "python",
        "tool.py",
        "--level",
        "full",
        "--skip_ui_smoke",
        "--no_zip",
        "--run_opt_smoke",
        "--opt_minutes",
        "5",
        "--opt_jobs",
        "3",
        "--osc_dir",
        "C:/tmp/osc",
        "--out_root",
        "C:/tmp/diagnostics",
    ]

    assert parse_run_full_diagnostics_output_line("Run dir: C:/tmp/run") == {"run_dir": "C:/tmp/run"}
    assert parse_run_full_diagnostics_output_line("Zip: C:/tmp/run.zip") == {"zip_path": "C:/tmp/run.zip"}
    assert parse_run_full_diagnostics_output_line("noop") == {}


def test_desktop_diagnostics_reads_analysis_evidence_from_send_bundles_first(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    out_dir = repo_root / "send_bundles"
    workspace_exports = repo_root / "pneumo_solver_ui" / "workspace" / "exports"
    out_dir.mkdir(parents=True)
    workspace_exports.mkdir(parents=True)
    (out_dir / "latest_analysis_evidence_manifest.json").write_text(
        json.dumps(_analysis_manifest(run_id="run-sidecar", manifest_hash="hash-sidecar"), ensure_ascii=False),
        encoding="utf-8",
    )
    (workspace_exports / "analysis_evidence_manifest.json").write_text(
        json.dumps(_analysis_manifest(run_id="run-workspace", manifest_hash="hash-workspace"), ensure_ascii=False),
        encoding="utf-8",
    )

    bundle = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)

    assert bundle.latest_analysis_evidence_manifest_path == str(
        (out_dir / "latest_analysis_evidence_manifest.json").resolve()
    )
    assert bundle.analysis_evidence_status == "READY"
    assert bundle.analysis_evidence_context_state == "CURRENT"
    assert bundle.analysis_evidence_manifest_hash == "hash-sidecar"
    assert bundle.analysis_evidence_run_id == "run-sidecar"
    assert bundle.analysis_evidence_artifact_count == 2
    assert bundle.analysis_evidence_mismatch_count == 0


def test_desktop_diagnostics_reads_analysis_evidence_workspace_fallback_and_warns(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    out_dir = repo_root / "send_bundles"
    workspace = tmp_path / "effective_workspace"
    out_dir.mkdir(parents=True)
    (workspace / "exports").mkdir(parents=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))
    (workspace / "exports" / "analysis_evidence_manifest.json").write_text(
        json.dumps(
            _analysis_manifest(
                run_id="run-stale",
                manifest_hash="hash-stale",
                state="STALE",
                mismatches=[{"key": "run_contract_hash", "current": "new", "selected": "old"}],
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)

    assert bundle.latest_analysis_evidence_manifest_path == str(
        (workspace / "exports" / "analysis_evidence_manifest.json").resolve()
    )
    assert bundle.analysis_evidence_status == "WARN"
    assert bundle.analysis_evidence_context_state == "STALE"
    assert bundle.analysis_evidence_manifest_hash == "hash-stale"
    assert bundle.analysis_evidence_run_id == "run-stale"
    assert bundle.analysis_evidence_mismatch_count == 1
    assert any("context is STALE" in msg for msg in bundle.analysis_evidence_warnings)
    assert any("context mismatch" in msg for msg in bundle.analysis_evidence_warnings)


def test_desktop_diagnostics_surfaces_ho008_analysis_context_warning(tmp_path: Path) -> None:
    from pneumo_solver_ui.tools.desktop_diagnostics_center import DesktopDiagnosticsCenter

    repo_root = tmp_path / "repo"
    out_dir = repo_root / "send_bundles"
    out_dir.mkdir(parents=True)
    manifest = _analysis_manifest(run_id="run-ho008", manifest_hash="hash-ho008")
    manifest["result_context"]["selected"] = {
        "run_id": "run-ho008",
        "analysis_context_status": "BLOCKED",
        "animator_link_contract_hash": "animator-link-ho008",
        "selected_run_contract_hash": "selected-run-ho008",
        "selected_test_id": "T02",
        "selected_npz_path": "C:/workspace/exports/selected.npz",
        "capture_export_manifest_handoff_id": "HO-010",
        "capture_hash": "capture-ho008",
        "truth_mode_hash": "truth-ho008",
    }
    (out_dir / "latest_analysis_evidence_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    bundle = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)

    assert bundle.analysis_evidence_status == "WARN"
    assert bundle.analysis_context_status == "BLOCKED"
    assert bundle.analysis_animator_link_contract_hash == "animator-link-ho008"
    assert bundle.analysis_selected_run_contract_hash == "selected-run-ho008"
    assert bundle.analysis_selected_test_id == "T02"
    assert bundle.analysis_selected_npz_path == "C:/workspace/exports/selected.npz"
    assert bundle.analysis_capture_export_manifest_status == "READY"
    assert bundle.analysis_capture_export_manifest_handoff_id == "HO-010"
    assert bundle.analysis_capture_hash == "capture-ho008"
    assert bundle.analysis_truth_mode_hash == "truth-ho008"
    assert "Engineering Analysis Center" in bundle.analysis_context_action
    assert any("HO-008 analysis context is BLOCKED" in msg for msg in bundle.analysis_evidence_warnings)
    summary_lines = DesktopDiagnosticsCenter._analysis_evidence_summary_lines(object(), bundle)
    assert "- Файлы для аниматора: готово | проверка=capture-ho008" in summary_lines

    center_state = write_desktop_diagnostics_center_state(out_dir, bundle_record=bundle)
    payload = json.loads(center_state.read_text(encoding="utf-8"))
    assert payload["analysis_evidence"]["analysis_context_status"] == "BLOCKED"
    assert payload["analysis_evidence"]["animator_link_contract_hash"] == "animator-link-ho008"
    assert payload["analysis_evidence"]["selected_test_id"] == "T02"
    assert payload["analysis_evidence"]["capture_export_manifest_status"] == "READY"
    assert payload["analysis_evidence"]["capture_export_manifest_handoff_id"] == "HO-010"


def test_desktop_diagnostics_marks_missing_analysis_evidence_with_results_action(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    out_dir = repo_root / "send_bundles"
    out_dir.mkdir(parents=True)

    bundle = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)

    assert bundle.analysis_evidence_status == "MISSING"
    assert bundle.analysis_evidence_context_state == "MISSING"
    assert bundle.latest_analysis_evidence_manifest_path == ""
    assert "Results Center" in bundle.analysis_evidence_action
    assert any("Analysis evidence / HO-009 missing" in msg for msg in bundle.analysis_evidence_warnings)


def test_desktop_diagnostics_operator_preview_localizes_markdown_reports() -> None:
    from pneumo_solver_ui.tools.desktop_diagnostics_center import _operator_log_text, _operator_preview_text

    raw = "\n".join(
        [
            "# Send bundle inspection",
            "- OK: **False**",
            "- Embedded health report: True",
            "## Evidence manifest",
            "- missing_evidence: Analysis evidence / HO-009 context state is missing.",
            "## Engineering analysis evidence",
            "- status: READY",
            "## Anim latest diagnostics",
            "- available: False",
            "- pointer_sync_ok: None",
            "- npz_path_sync_ok: True",
            "- npz_path: C:/workspace/exports/anim_latest.npz",
        ]
    )

    translated = _operator_preview_text(raw)

    assert "# Проверка архива проекта" in translated
    assert "- Успешно: **нет**" in translated
    assert "- Вложенный отчёт о состоянии: да" in translated
    assert "## Файл состава данных" in translated
    assert "- Нет данных: нет состояния данных анализа результатов." in translated
    assert "## Данные инженерного анализа" in translated
    assert "- Состояние: готово" in translated
    assert "## Данные последней анимации" in translated
    assert "## Сведения о последней анимации" not in translated
    assert "- Доступно: нет" in translated
    assert "- Последняя анимация синхронизирована: нет данных" in translated
    assert "- Файл анимации синхронизирован: да" in translated
    assert "- Файл анимации: C:/workspace/exports/anim_latest.npz" in translated
    assert "Путь NPZ" not in translated

    log_text = _operator_log_text("Run dir: C:/tmp/run\nZip: C:/tmp/run.zip\nrc=1\n")
    assert "Папка запуска: C:/tmp/run" in log_text
    assert "Архив проекта: C:/tmp/run.zip" in log_text
    assert "код завершения 1" in log_text
    assert "Run dir:" not in log_text
    assert "Zip:" not in log_text
    assert "rc=" not in log_text


def test_desktop_diagnostics_runtime_persists_machine_readable_bundle_and_run_state(tmp_path: Path) -> None:
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir()

    zip_path = out_dir / "latest_send_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "bundle/meta.json",
            json.dumps({"release": "TEST", "run_id": "R1", "created_at": "2026-04-13 00:00:00"}),
        )
    (out_dir / "latest_send_bundle_path.txt").write_text(str(zip_path.resolve()), encoding="utf-8")
    (out_dir / "latest_send_bundle.sha256").write_text(
        hashlib.sha256(zip_path.read_bytes()).hexdigest() + "  latest_send_bundle.zip\n",
        encoding="utf-8",
    )
    (out_dir / EVIDENCE_MANIFEST_SIDECAR_NAME).write_text(
        json.dumps(
            {
                "schema": "diagnostics_evidence_manifest",
                "zip_path": str(zip_path.resolve()),
                "zip_sha256": "build-stage-sha",
                "zip_sha256_scope": "zip bytes at evidence manifest build time",
                "stage": "pytest_build_stage",
                "finalization_stage": "pytest_build_stage",
                "trigger": "manual",
                "collection_mode": "manual",
                "missing_warnings": ["producer-owned geometry evidence is still missing"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "REPORTS"
    reports_dir.mkdir()
    (reports_dir / "SELF_CHECK_SILENT_WARNINGS.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-04-18T00:00:00Z",
                "rc": 0,
                "summary": {"fail_count": 0, "warn_count": 0},
                "fails": [],
                "warnings": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (reports_dir / "SELF_CHECK_SILENT_WARNINGS.md").write_text("# self-check snapshot\n", encoding="utf-8")

    (out_dir / "last_bundle_meta.json").write_text(
        json.dumps(
            {
                "ok": True,
                "summary_lines": ["Anim latest token: tok-123"],
                "zip": {"path": str(zip_path.resolve()), "name": zip_path.name, "size_bytes": zip_path.stat().st_size},
                "anim_pointer_diagnostics_path": str((out_dir / "latest_anim_pointer_diagnostics.json").resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "anim_latest": {
                    "visual_cache_token": "tok-123",
                    "visual_reload_inputs": ["anim_latest.npz"],
                    "npz_path": "workspace/exports/anim_latest.npz",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_clipboard_status.json").write_text(
        json.dumps({"ok": True, "message": "powershell ok", "zip_path": str(zip_path.resolve())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME).write_text(
        json.dumps(_geometry_reference_evidence(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME).write_text(
        json.dumps(_engineering_analysis_evidence(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    bundle = refresh_desktop_diagnostics_bundle_record(tmp_path, out_dir=out_dir, zip_path=zip_path)
    assert bundle.latest_zip_path == str(zip_path.resolve())
    assert "Anim latest token: tok-123" in bundle.summary_lines
    assert Path(bundle.latest_inspection_json_path).exists()
    assert Path(bundle.latest_health_json_path).exists()
    assert bundle.latest_engineering_analysis_evidence_manifest_path.endswith(
        ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME
    )
    assert bundle.engineering_analysis_evidence_status == "READY"
    assert bundle.engineering_analysis_readiness_status == "READY"
    assert bundle.engineering_analysis_open_gap_status == "CLEAR"
    assert bundle.engineering_analysis_open_gap_reasons == []
    assert bundle.engineering_analysis_no_release_closure_claim is True
    assert bundle.engineering_analysis_validation_status == "READY"
    assert bundle.engineering_analysis_evidence_manifest_hash == "engineering-hash-001"
    assert bundle.engineering_analysis_candidate_count == 2
    assert bundle.engineering_analysis_ready_candidate_count == 1
    assert bundle.engineering_analysis_missing_inputs_candidate_count == 1
    assert bundle.engineering_analysis_candidate_unique_missing_inputs == ["results_csv_path"]
    assert bundle.geometry_reference_status == "READY"
    assert bundle.geometry_reference_artifact_freshness_status == "current"
    assert bundle.geometry_reference_artifact_freshness_relation == "matches_latest"
    assert bundle.geometry_reference_road_width_status == "explicit_meta"
    assert bundle.geometry_reference_packaging_contract_hash == "packaging-hash"
    assert bundle.geometry_reference_acceptance_gate == "PASS"
    assert bundle.geometry_reference_producer_artifact_status == "ready"
    assert bundle.geometry_reference_producer_readiness_reasons == []
    assert bundle.geometry_reference_consumer_may_fabricate_geometry is False
    assert bundle.latest_integrity_status == "READY"
    assert bundle.latest_integrity_final_zip_sha256 == hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert bundle.latest_integrity_sha_sidecar_matches is True
    assert bundle.latest_integrity_pointer_matches_original is True
    assert bundle.latest_integrity_embedded_manifest_zip_sha256_scope == "zip bytes at evidence manifest build time"
    assert bundle.latest_integrity_producer_warning_count > 0
    assert bundle.latest_integrity_warning_only_gaps_present is True
    assert bundle.latest_integrity_no_release_closure_claim is True
    assert bundle.self_check_silent_warnings_status == "READY"
    assert bundle.self_check_silent_warnings_fail_count == 0
    assert bundle.self_check_silent_warnings_warn_count == 0
    assert bundle.self_check_silent_warnings_snapshot_only is True

    run = DesktopDiagnosticsRunRecord(
        ok=True,
        started_at="2026-04-13 00:00:00",
        finished_at="2026-04-13 00:05:00",
        status="finished",
        command=["python", "tool.py"],
        returncode=0,
        out_root=str((tmp_path / "diagnostics").resolve()),
        last_message="OK",
    )
    append_desktop_diagnostics_run_log(tmp_path / "diagnostics", "line-1\n")
    append_desktop_diagnostics_run_log(tmp_path / "diagnostics", "line-2\n")
    assert load_last_desktop_diagnostics_run_log_text(tmp_path / "diagnostics") == "line-1\nline-2\n"
    run = persist_desktop_diagnostics_run(tmp_path / "diagnostics", run, log_text="diagnostics log")
    assert Path(run.state_path).exists()
    assert Path(run.log_path).exists()
    loaded_run = load_last_desktop_diagnostics_run_record(tmp_path / "diagnostics")
    assert loaded_run is not None
    assert loaded_run.status == "finished"
    assert loaded_run.returncode == 0
    assert loaded_run.last_message == "OK"
    assert load_last_desktop_diagnostics_run_log_text(tmp_path / "diagnostics") == "diagnostics log"

    summary_md = write_desktop_diagnostics_summary_md(out_dir, "# Desktop diagnostics/send summary\n")
    center_state = write_desktop_diagnostics_center_state(
        out_dir,
        bundle_record=bundle,
        run_record=run,
        summary_md_path=summary_md,
        ui_state={
            "selected_tab": "bundle",
            "bundle_busy": False,
            "level": "full",
            "out_root": str((tmp_path / "diagnostics").resolve()),
            "active_bundle_out_dir": str(out_dir.resolve()),
        },
    )
    payload = json.loads(center_state.read_text(encoding="utf-8"))
    loaded_center_state = load_last_desktop_diagnostics_center_state(out_dir)
    assert summary_md.name == LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD
    assert payload["machine_paths"]["latest_summary_md"].endswith(LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD)
    assert payload["machine_paths"]["latest_bundle_inspection_json"].endswith(LATEST_SEND_BUNDLE_INSPECTION_JSON)
    assert payload["machine_paths"]["latest_bundle_path_txt"].endswith("latest_send_bundle_path.txt")
    assert payload["machine_paths"]["latest_bundle_sha256"].endswith("latest_send_bundle.sha256")
    assert payload["machine_paths"]["latest_integrity_evidence_sidecar_json"].endswith(
        EVIDENCE_MANIFEST_SIDECAR_NAME
    )
    assert payload["machine_paths"]["self_check_silent_warnings_json"].endswith(
        "SELF_CHECK_SILENT_WARNINGS.json"
    )
    assert "latest_analysis_evidence_manifest_json" in payload["machine_paths"]
    assert payload["machine_paths"]["latest_engineering_analysis_evidence_manifest_json"].endswith(
        ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME
    )
    assert payload["machine_paths"]["latest_geometry_reference_evidence_json"].endswith(
        GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME
    )
    assert payload["machine_paths"]["latest_run_state_json"].endswith(LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON)
    assert payload["analysis_evidence"]["status"] == bundle.analysis_evidence_status
    assert payload["analysis_evidence"]["context_state"] == bundle.analysis_evidence_context_state
    assert payload["engineering_analysis_evidence"]["status"] == "READY"
    assert payload["engineering_analysis_evidence"]["readiness_status"] == "READY"
    assert payload["engineering_analysis_evidence"]["open_gap_status"] == "CLEAR"
    assert payload["engineering_analysis_evidence"]["open_gap_reasons"] == []
    assert payload["engineering_analysis_evidence"]["no_release_closure_claim"] is True
    assert payload["engineering_analysis_evidence"]["validation_status"] == "READY"
    assert payload["engineering_analysis_evidence"]["manifest_hash"] == "engineering-hash-001"
    assert payload["engineering_analysis_evidence"]["selected_run_candidate_count"] == 2
    assert payload["engineering_analysis_evidence"]["selected_run_ready_candidate_count"] == 1
    assert payload["engineering_analysis_evidence"]["selected_run_missing_inputs_candidate_count"] == 1
    assert payload["engineering_analysis_evidence"]["selected_run_unique_missing_inputs"] == ["results_csv_path"]
    assert payload["geometry_reference_evidence"]["status"] == "READY"
    assert payload["geometry_reference_evidence"]["artifact_freshness_status"] == "current"
    assert payload["geometry_reference_evidence"]["artifact_freshness_relation"] == "matches_latest"
    assert payload["geometry_reference_evidence"]["road_width_status"] == "explicit_meta"
    assert payload["geometry_reference_evidence"]["packaging_contract_hash"] == "packaging-hash"
    assert payload["geometry_reference_evidence"]["geometry_acceptance_gate"] == "PASS"
    assert payload["geometry_reference_evidence"]["producer_artifact_status"] == "ready"
    assert payload["geometry_reference_evidence"]["producer_readiness_reasons"] == []
    assert payload["geometry_reference_evidence"]["consumer_may_fabricate_geometry"] is False
    assert "workspace/exports/anim_latest.npz" in payload["geometry_reference_evidence"]["producer_required_artifacts"]
    assert payload["latest_integrity_proof"]["status"] == "READY"
    assert payload["latest_integrity_proof"]["latest_sha_sidecar_matches"] is True
    assert payload["latest_integrity_proof"]["latest_pointer_matches_original"] is True
    assert payload["latest_integrity_proof"]["warning_only_gaps_present"] is True
    assert payload["latest_integrity_proof"]["no_release_closure_claim"] is True
    assert payload["self_check_silent_warnings"]["status"] == "READY"
    assert payload["self_check_silent_warnings"]["snapshot_only"] is True
    assert payload["self_check_silent_warnings"]["does_not_close_producer_warnings"] is True
    assert payload["bundle"]["latest_clipboard_status_path"].endswith("latest_send_bundle_clipboard_status.json")
    assert payload["ui"]["selected_tab"] == "bundle"
    assert payload["ui"]["active_bundle_out_dir"].endswith("send_bundles")
    assert loaded_center_state["ui"]["level"] == "full"
    assert loaded_center_state["ui"]["out_root"].endswith("diagnostics")
    assert loaded_center_state["ui"]["selected_tab"] == "bundle"


def test_desktop_diagnostics_exposes_engineering_open_gap_state(tmp_path: Path) -> None:
    from pneumo_solver_ui.tools.desktop_diagnostics_center import DesktopDiagnosticsCenter

    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir()
    payload = {
        "schema": "desktop_engineering_analysis_evidence_manifest",
        "schema_version": "1.0.0",
        "evidence_manifest_hash": "engineering-hash-blocked",
        "validation": {
            "status": "BLOCKED",
            "influence_status": "BLOCKED",
            "calibration_status": "BLOCKED",
        },
        "handoff_requirements": {
            "handoff_id": "HO-007",
            "contract_status": "MISSING",
            "required_contract_path": "workspace/handoffs/WS-OPTIMIZATION/selected_run_contract.json",
            "missing_fields": ["selected_run_contract_hash"],
        },
        "selected_run_candidate_readiness": {
            "schema": "selected_run_candidate_readiness.v1",
            "candidate_count": 1,
            "ready_candidate_count": 0,
            "missing_inputs_candidate_count": 1,
            "failed_candidate_count": 0,
            "unique_missing_inputs": ["results_csv_path"],
            "ready_run_dirs": [],
        },
    }
    (out_dir / ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    bundle = load_desktop_diagnostics_bundle_record(tmp_path, out_dir=out_dir)
    assert bundle.engineering_analysis_evidence_status == "WARN"
    assert bundle.engineering_analysis_readiness_status == "WARN"
    assert bundle.engineering_analysis_open_gap_status == "OPEN"
    assert bundle.engineering_analysis_no_release_closure_claim is True
    assert "influence_status=BLOCKED" in bundle.engineering_analysis_open_gap_reasons
    assert "calibration_status=BLOCKED" in bundle.engineering_analysis_open_gap_reasons
    assert "validated_artifacts_status=MISSING" in bundle.engineering_analysis_open_gap_reasons
    assert "handoff_contract_status=MISSING" in bundle.engineering_analysis_open_gap_reasons

    center_state = write_desktop_diagnostics_center_state(out_dir, bundle_record=bundle)
    center_payload = json.loads(center_state.read_text(encoding="utf-8"))
    assert center_payload["engineering_analysis_evidence"]["open_gap_status"] == "OPEN"
    assert "handoff_contract_status=MISSING" in center_payload["engineering_analysis_evidence"]["open_gap_reasons"]

    summary_lines = DesktopDiagnosticsCenter._engineering_analysis_evidence_summary_lines(object(), bundle)
    status_text = DesktopDiagnosticsCenter._engineering_analysis_status_text(object(), bundle)
    assert "- Незакрытые вопросы: открыто" in summary_lines
    assert any("Причины незакрытых вопросов:" in line for line in summary_lines)
    assert "открытые вопросы: открыто" in status_text


def test_desktop_diagnostics_prefers_latest_bundle_pointer_over_stale_meta(tmp_path: Path) -> None:
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir()

    stale_zip = out_dir / "SEND_stale_bundle.zip"
    latest_zip = out_dir / "latest_send_bundle.zip"
    for path, release in ((stale_zip, "STALE"), (latest_zip, "LATEST")):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bundle/meta.json", json.dumps({"release": release}))

    (out_dir / "last_bundle_meta.json").write_text(
        json.dumps(
            {"ok": True, "zip": {"path": str(stale_zip.resolve()), "name": stale_zip.name}},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_path.txt").write_text(str(latest_zip.resolve()), encoding="utf-8")
    (out_dir / "latest_send_bundle.sha256").write_text(
        hashlib.sha256(latest_zip.read_bytes()).hexdigest() + "  latest_send_bundle.zip\n",
        encoding="utf-8",
    )

    bundle = load_desktop_diagnostics_bundle_record(tmp_path, out_dir=out_dir)

    assert bundle.latest_zip_path == str(latest_zip.resolve())
    assert bundle.latest_path_pointer_path.endswith("latest_send_bundle_path.txt")
    assert bundle.latest_sha_path.endswith("latest_send_bundle.sha256")


def test_desktop_diagnostics_marks_clipboard_status_stale_when_it_points_to_old_zip(tmp_path: Path) -> None:
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir()

    old_zip = out_dir / "SEND_old_bundle.zip"
    latest_zip = out_dir / "latest_send_bundle.zip"
    old_zip.write_bytes(b"old zip bytes")
    latest_zip.write_bytes(b"latest zip bytes")
    (out_dir / "latest_send_bundle_path.txt").write_text(str(latest_zip.resolve()), encoding="utf-8")
    (out_dir / "latest_send_bundle.sha256").write_text(
        hashlib.sha256(latest_zip.read_bytes()).hexdigest() + "  latest_send_bundle.zip\n",
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_clipboard_status.json").write_text(
        json.dumps(
            {
                "ok": True,
                "message": f"Copied file to clipboard (CF_HDROP): {old_zip.resolve()}",
                "zip_path": str(old_zip.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    bundle = load_desktop_diagnostics_bundle_record(tmp_path, out_dir=out_dir)

    assert bundle.latest_zip_path == str(latest_zip.resolve())
    assert bundle.clipboard_ok is False
    assert "stale" in bundle.clipboard_message
    assert str(old_zip.resolve()) in bundle.clipboard_message


def test_diagnostics_and_send_wrappers_delegate_to_shared_desktop_center() -> None:
    diag_src = (ROOT / "pneumo_solver_ui" / "tools" / "run_full_diagnostics_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    center_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_src = (ROOT / "pneumo_solver_ui" / "desktop_diagnostics_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "DesktopDiagnosticsCenter" in diag_src
    assert 'initial_tab="diagnostics"' in diag_src
    assert "Проверка проекта - PneumoApp" in diag_src
    assert "Центр диагностики" not in diag_src
    assert "Full Diagnostics (GUI)" not in diag_src
    assert "DesktopDiagnosticsCenter" in send_src
    assert 'initial_tab="send"' in send_src
    assert "latest_send_bundle_clipboard_status.json" in send_src
    assert "Архив проекта готов и уже скопирован в буфер обмена." in send_src
    assert "Данные последней анимации:" in send_src
    assert "Сведения о последней анимации:" not in send_src
    assert "Anim pointer diagnostics:" not in send_src
    assert "Не удалось сохранить архив проекта" in send_src
    assert "bundle build failed" not in send_src
    assert "load_desktop_diagnostics_bundle_record" in send_src
    assert "ttk.Notebook" in center_src
    assert "Проверка проекта и сохранение архива" in center_src
    assert "Проверка проекта и архив" not in center_src
    assert "Центр диагностики и отправки" not in center_src
    assert "Из этого центра" not in center_src
    assert "write_desktop_diagnostics_center_state" in center_src
    assert "Полезные файлы и отчёты" in center_src
    assert "Сводка и полезные файлы" in center_src
    assert "Данные анализа результатов" in center_src
    assert "latest_analysis_evidence_manifest.json" in center_src
    assert "Данные инженерного анализа" in center_src
    assert "latest_engineering_analysis_evidence_manifest_path" in center_src
    assert "engineering_analysis_ready_candidate_count" in center_src
    assert "latest_engineering_analysis_evidence_manifest_json" in runtime_src
    assert "selected_run_ready_candidate_count" in runtime_src
    assert 'text="Открыть данные анализа"' in center_src
    assert "self.btn_open_analysis_evidence" in center_src
    assert "def _open_analysis_evidence(self) -> None:" in center_src
    assert 'text="Открыть инженерный анализ"' in center_src
    assert "self.btn_open_engineering_analysis_evidence" in center_src
    assert "def _open_engineering_analysis_evidence(self) -> None:" in center_src
    assert "def _engineering_analysis_evidence_summary_lines(self, bundle) -> list[str]:" in center_src
    assert "def _engineering_analysis_status_text(self, bundle) -> str:" in center_src
    assert "Готовность архива проекта" in center_src
    assert "Связь с анимацией" in center_src
    assert "Файлы для аниматора" in center_src
    assert "Захват для анимации" not in center_src
    assert "хэш захвата" not in center_src
    assert "analysis_capture_export_manifest_status" in center_src
    assert "capture_export_manifest_status" in runtime_src
    assert "analysis_context_status" in runtime_src
    assert "analysis_context_action" in runtime_src
    assert "Данные справочника геометрии" in center_src
    assert "Актуальность данных" in center_src
    assert "Данные источника" in center_src
    assert "источник={_producer_owner_ru" in center_src
    assert "владелец=" not in center_src
    assert "Причины неготовности источника" in center_src
    assert "Автоматически добавлять недостающую геометрию" in center_src
    assert "Справочнику разрешено достраивать геометрию" not in center_src
    assert "geometry_reference_artifact_freshness_relation" in center_src
    assert "Проверка актуального архива" in center_src
    assert "Предупреждения источников данных остаются предупреждениями" in center_src
    assert "Снимок скрытых предупреждений проверки" in center_src
    assert "latest_integrity_proof" in runtime_src
    assert "self_check_silent_warnings" in runtime_src
    assert "geometry_reference_producer_artifact_status" in runtime_src
    assert "geometry_reference_producer_readiness_reasons" in runtime_src
    assert "consumer_may_fabricate_geometry" in runtime_src
    assert 'text="Открыть геометрию"' in center_src
    assert "self.btn_open_geometry_reference_evidence" in center_src
    assert "def _open_geometry_reference_evidence(self) -> None:" in center_src
    assert "latest_geometry_reference_evidence.json" in center_src
    assert "geometry_reference_evidence.json" in center_src
    assert "def _geometry_reference_evidence_summary_lines(self, bundle) -> list[str]:" in center_src
    assert "def _geometry_reference_status_text(self, bundle) -> str:" in center_src
    assert "copy_latest_bundle_to_clipboard(" in center_src
    assert "out_dir=self._active_bundle_out_dir()" in center_src
    assert "def _schedule_poll(self) -> None:" in center_src
    assert "def _poll_external_state(self) -> None:" in center_src
    assert "def _compute_external_state_signature(self) -> tuple[str, ...]:" in center_src
    assert "load_last_desktop_diagnostics_center_state" in center_src
    assert "append_desktop_diagnostics_run_log" in center_src
    assert "load_last_desktop_diagnostics_run_record" in center_src
    assert "load_last_desktop_diagnostics_run_log_text" in center_src
    assert "def _restore_bundle_state_from_last_center_state(self) -> None:" in center_src
    assert "def _restore_diagnostics_request_from_last_center_state(self) -> None:" in center_src
    assert "def _resolve_initial_tab_name(self, initial_tab: str) -> str:" in center_src
    assert "## Последняя проверка проекта" in center_src
    assert "status=\"running\"" in center_src
    assert "status=\"stopping\"" in center_src
    assert "- Состояние:" in center_src
    assert "- Метка расчёта:" in center_src
    assert "- Файл подробностей:" in center_src
    assert "- Краткий отчёт:" in center_src
    assert "latest_desktop_diagnostics_summary.md" in center_src
    assert 'DesktopDiagnosticsCenter(root, initial_tab="restore")' in center_src
    assert "<<NotebookTabChanged>>" in center_src
    assert 'self._poll_after_id = self.root.after(1000, self._poll_external_state)' in center_src
    assert "self.root.after_cancel(self._poll_after_id)" in center_src


def test_desktop_diagnostics_center_uses_split_workspace_and_sidebar_actions() -> None:
    center_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(outer, orient="horizontal")' in center_src
    assert 'context_box = ttk.LabelFrame(sidebar, text="Состояние", padding=8)' in center_src
    assert 'quick_box = ttk.LabelFrame(sidebar, text="Основные действия", padding=8)' in center_src
    assert 'ttk.Button(header_actions, text="Настройки проверки", command=lambda: self.notebook.select(self.diag_tab)).pack(side="left")' in center_src
    assert 'ttk.Button(header_actions, text="Состав архива", command=lambda: self.notebook.select(self.bundle_tab)).pack(side="left", padx=(8, 0))' in center_src
    assert 'ttk.Button(header_actions, text="Архив", command=lambda: self.notebook.select(self.send_tab)).pack(side="left", padx=(8, 0))' in center_src
    assert 'process_box = ttk.LabelFrame(outer, text="Текущий процесс", padding=8)' in center_src
    assert "self.process_progress = ttk.Progressbar(" in center_src
    assert "preview_area = ttk.Frame(self.bundle_body)" in center_src
    assert 'inspect_box = ttk.LabelFrame(preview_area, text="Проверка архива", padding=6)' in center_src
    assert 'health_box = ttk.LabelFrame(preview_area, text="Состояние проекта", padding=6)' in center_src
    assert "def _set_process_busy(self, title: str, detail: str) -> None:" in center_src
    assert "def _start_run(self) -> None:" in center_src
    assert "def _open_bundle_dir(self) -> None:" in center_src

    start_run_block = center_src[center_src.index("def _start_run"): center_src.index("def _open_bundle_dir")]
    assert "self.notebook.select" not in start_run_block


def test_desktop_diagnostics_center_operator_text_is_russian_and_progress_global() -> None:
    center_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    required = [
        "Текущий процесс",
        "Прогресс проверки проекта и сохранения архива всегда показывается здесь.",
        "Идёт проверка проекта. Прогресс показан здесь; можно оставаться в текущем разделе.",
        "Идёт сохранение архива проекта. Прогресс показан здесь; можно оставаться в текущем разделе.",
        "Пропустить быструю проверку окон приложения",
        "Папки для проверки",
        "Открыть отчёт проверки",
        "Обновить сводку",
        "Раздел «",
        "Прогресс любой длительной операции",
        "без переключения разделов",
        "Архив проекта сохраняется здесь.",
        "Сохранённое состояние проверки",
        "Скопировать архив в буфер обмена",
        "Папка файлов анимации",
        "Выберите папку с файлами анимации",
        "- Файл анимации:",
        "Данные анализа результатов:",
        "Данные инженерного анализа:",
        "Данные справочника геометрии:",
        "Снимок скрытых предупреждений проверки",
    ]
    for fragment in required:
        assert fragment in center_src

    assert '"Results Center": "анализ результатов"' in center_src
    assert '"Engineering Analysis Center": "инженерный анализ"' in center_src
    assert '"Reference Center": "справочник"' in center_src
    assert "справочник не должен создавать данные геометрии за источник" in center_src

    forbidden = [
        'text="Открыть Analysis JSON"',
        'text="Открыть Engineering JSON"',
        'text="Открыть Geometry JSON"',
        "Evidence handoff status",
        "## Analysis evidence / HO-009",
        '"Analysis evidence / HO-009: "',
        "## Engineering Analysis evidence / HO-007",
        '"Engineering Analysis evidence / HO-007: "',
        "## Geometry Reference evidence",
        '"Geometry Reference evidence: "',
        "Latest integrity: ",
        "SELF_CHECK silent warnings snapshot",
        "Producer-owned warnings remain warning-only",
        "📋",
        "📂",
        "▶",
        "■",
        "minutes:",
        "jobs:",
        "State JSON:",
        "Технический журнал диагностики",
        "Техническая команда",
        "Файл состояния окна",
        "self.pb",
        "preview_book",
        "Сводка и машинно-читаемые пути",
        "Машиночитаемые пути",
        "Данные анализа HO-009:",
        "Данные инженерного анализа HO-007:",
        'text="Анализ результатов / HO-009"',
        'text="Инженерный анализ / HO-007"',
        "Захват/экспорт HO-010",
        "handoff=",
        "Сборка пакета отправки",
        "Запущен автономный",
        "Открыт раздел",
        "Открыт шаг",
        "выбранного раздела",
        "Центр диагностики",
        "Из этого центра",
        "Снимок состояния центра",
        "старого интерфейса",
        "старый интерфейс",
        "вкладку менять не нужно",
        "не зависит от выбранной вкладки",
        "Пути (если нужно)",
        'text="..."',
        'text="Открыть результат"',
        'last_message="rc',
        "Каталог прогона",
        "Папка с NPZ",
        "Выберите папку с NPZ",
        "Выбранный NPZ",
        "Путь NPZ",
        "Каталог:",
        "Идентификатор",
        "идентификатор",
        "Артефакт",
        "артефакт",
        "статус миграции",
        "Открыть выбранный этап",
        "Данные машины",
        "ID расчёта",
        "Снимок тихих предупреждений самопроверки",
        "Тихие предупреждения самопроверки",
        "Предупреждения самопроверки",
        "Читаемые предупреждения самопроверки",
        '"Results Center": "центр результатов"',
        '"Engineering Analysis Center": "центр инженерного анализа"',
        '"Reference Center": "центр справочников"',
        "центр справочников не должен создавать данные геометрии за источник",
        "- JSON:",
        "- Markdown:",
    ]
    for fragment in forbidden:
        assert fragment not in center_src


def test_test_center_integration_reuses_existing_latest_bundle_when_opening_send_center() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "test_center_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'env["PNEUMO_SEND_RESULTS_REUSE_LATEST"] = "1"' in src
    assert "launch_send_results_gui(env=env)" in src or "results_runtime.launch_send_results_gui(env=env)" in src or "subprocess.Popen([self.py, str(send_gui)], cwd=str(self.repo), env=env)" in src
    assert 'os.environ.get("PNEUMO_SEND_RESULTS_REUSE_LATEST", "0")' in send_src
    assert "auto_build_bundle=(not reuse_latest) or (not bundle_state.latest_zip_path)" in send_src


def test_legacy_wrapper_helpers_remain_available_for_hidden_launcher_contracts() -> None:
    import pneumo_solver_ui.tools.run_full_diagnostics_gui as diag_module
    import pneumo_solver_ui.tools.send_results_gui as send_module

    assert hasattr(diag_module, "ROOT")
    assert hasattr(diag_module, "TOOLS_DIR")
    assert callable(diag_module._guess_python_exe)
    assert callable(diag_module._open_in_explorer)

    assert callable(send_module._repo_root)
    assert callable(send_module._log_dir)
    assert callable(send_module._sha256_file)
    assert callable(send_module._safe_write_text)
    assert callable(send_module._is_full_file_clipboard_success)
    assert hasattr(send_module.SendResultsGUI, "_write_clipboard_status")
    assert hasattr(send_module.SendResultsGUI, "_worker")
    assert hasattr(send_module.SendResultsGUI, "_poll")
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    assert "send_results_gui_error.log" in send_src
    assert "send_results_gui_crash.log" in send_src
