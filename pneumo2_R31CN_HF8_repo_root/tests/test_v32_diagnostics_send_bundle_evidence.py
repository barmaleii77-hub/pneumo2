from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.browser_perf_artifacts import write_browser_perf_artifacts, write_browser_perf_trace_artifact
from pneumo_solver_ui.desktop_animator.truth_contract import (
    ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME,
    build_frame_budget_evidence,
)
from pneumo_solver_ui.desktop_diagnostics_runtime import load_desktop_diagnostics_bundle_record
from pneumo_solver_ui.desktop_suite_snapshot import build_validated_suite_snapshot
from pneumo_solver_ui.optimization_baseline_source import (
    baseline_history_item_from_contract,
    build_active_baseline_contract,
)
from pneumo_solver_ui.runtime_evidence import build_windows_runtime_proof, write_windows_runtime_proof
from pneumo_solver_ui.tools.health_report import build_health_report
from pneumo_solver_ui.tools.inspect_send_bundle import inspect_send_bundle, render_inspection_md
from pneumo_solver_ui.tools.make_send_bundle import make_send_bundle
from pneumo_solver_ui.tools.send_bundle_evidence import (
    ANALYSIS_EVIDENCE_SIDECAR_NAME,
    ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME,
    ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME,
    ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME,
    EVIDENCE_MANIFEST_ARCNAME,
    GEOMETRY_REFERENCE_EVIDENCE_ARCNAME,
    GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME,
    build_evidence_manifest,
    classify_collection_mode,
    evidence_manifest_warnings,
    summarize_geometry_reference_evidence,
)
from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle

ROOT = Path(__file__).resolve().parents[1]


def _prepare_repo_and_workspace(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "send_bundles"
    workspace = tmp_path / "workspace"

    (repo_root / "pneumo_solver_ui" / "logs").mkdir(parents=True, exist_ok=True)
    (repo_root / "pneumo_solver_ui" / "logs" / "app.log").write_text("ok\n", encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel in ("exports", "uploads", "road_profiles", "maneuvers", "opt_runs", "ui_state"):
        d = workspace / rel
        d.mkdir(parents=True, exist_ok=True)
        if rel == "ui_state":
            (d / "autosave_profile.json").write_text(
                json.dumps({"diag_build_bundle": True}, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            (d / "keep.txt").write_text("x\n", encoding="utf-8")

    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("PNEUMO_BUNDLE_RUN_SELFCHECK", "0")
    return repo_root, out_dir, workspace


def _analysis_manifest(
    *,
    run_id: str = "run-ho009",
    manifest_hash: str = "hash-ho009",
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


def _geometry_reference_evidence(*, gate: str = "PASS", missing: list[str] | None = None) -> dict:
    missing_items = list(missing or [])
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
        "artifact_source_label": "pytest anim_latest",
        "artifact_npz_path": "C:/workspace/exports/anim_latest.npz",
        "road_width_status": "explicit_meta",
        "road_width_source": "meta.geometry.road_width_m",
        "road_width_effective_m": 2.0,
        "packaging_status": "complete",
        "packaging_contract_hash": "packaging-hash",
        "packaging_mismatch_status": "match",
        "packaging_axis_only_cylinders": [],
        "geometry_acceptance_gate": gate,
        "geometry_acceptance_available": gate == "PASS",
        "component_passport_components": 3,
        "component_passport_needs_data": 0,
        "evidence_missing": missing_items,
    }


def test_make_send_bundle_embeds_v32_evidence_manifest_and_final_latest_pointer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root, out_dir, workspace = _prepare_repo_and_workspace(tmp_path, monkeypatch)
    (workspace / "exports" / "analysis_evidence_manifest.json").write_text(
        json.dumps(
            _analysis_manifest(run_id="run-bundle", manifest_hash="hash-bundle"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    zip_path = make_send_bundle(
        repo_root=repo_root,
        out_dir=out_dir,
        keep_last_n=1,
        max_file_mb=20,
        trigger="manual",
    )

    latest_zip = out_dir / "latest_send_bundle.zip"
    latest_txt = out_dir / "latest_send_bundle_path.txt"
    latest_sha = out_dir / "latest_send_bundle.sha256"
    latest_evidence = out_dir / "latest_evidence_manifest.json"
    latest_inspection_json = out_dir / "latest_send_bundle_inspection.json"
    latest_inspection_md = out_dir / "latest_send_bundle_inspection.md"
    latest_geometry_reference = out_dir / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME
    latest_health = out_dir / "latest_health_report.md"

    assert latest_zip.exists()
    assert latest_txt.read_text(encoding="utf-8").strip() == str(zip_path.resolve())
    assert latest_sha.read_text(encoding="utf-8").strip() == (
        hashlib.sha256(latest_zip.read_bytes()).hexdigest() + "  latest_send_bundle.zip"
    )
    assert latest_zip.read_bytes() == zip_path.read_bytes()
    assert latest_evidence.exists()
    assert latest_inspection_json.exists()
    assert latest_inspection_md.exists()
    assert latest_geometry_reference.exists()
    assert latest_health.exists()

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        meta = json.loads(zf.read("bundle/meta.json").decode("utf-8", errors="replace"))
        evidence = json.loads(zf.read(EVIDENCE_MANIFEST_ARCNAME).decode("utf-8", errors="replace"))
        geometry_reference = json.loads(
            zf.read(GEOMETRY_REFERENCE_EVIDENCE_ARCNAME).decode("utf-8", errors="replace")
        )
    latest_evidence_payload = json.loads(latest_evidence.read_text(encoding="utf-8"))
    latest_inspection_payload = json.loads(latest_inspection_json.read_text(encoding="utf-8"))

    assert "health/health_report.json" in names
    assert "triage/triage_report.json" in names
    assert EVIDENCE_MANIFEST_ARCNAME in names
    assert GEOMETRY_REFERENCE_EVIDENCE_ARCNAME in names
    assert ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME in names
    assert meta["trigger"] == "manual"
    assert meta["collection_mode"] == "manual"
    assert meta["effective_workspace"] == str(workspace.resolve())
    helper = dict(meta.get("helper_runtime_provenance") or {})
    assert helper["python_executable"]
    assert helper["python_prefix"]
    assert helper["python_base_prefix"]
    assert helper["preferred_cli_python"]
    assert helper["effective_workspace"] == str(workspace.resolve())
    assert helper["provenance_complete"] is True

    assert evidence["workspace"] == "WS-DIAGNOSTICS"
    assert evidence["playbook_id"] == "PB-002"
    assert evidence["collection_mode"] == "manual"
    assert evidence["finalization_stage"] == "final_after_validation_dashboard"
    assert evidence["zip_sha256"]
    assert evidence["pb002_missing_required_count"] == 0
    assert evidence["analysis_handoff"]["handoff_id"] == "HO-009"
    assert evidence["analysis_handoff"]["status"] == "READY"
    assert evidence["analysis_handoff"]["run_id"] == "run-bundle"
    assert evidence["analysis_handoff"]["evidence_manifest_hash"] == "hash-bundle"
    assert evidence["geometry_reference_handoff"]["schema"] == "geometry_reference_evidence.v1"
    assert evidence["geometry_reference_handoff"]["source_path"].endswith(GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME)
    assert geometry_reference["schema"] == "geometry_reference_evidence.v1"
    assert geometry_reference["reference_center_role"] == "reader_and_evidence_surface"
    assert geometry_reference["does_not_render_animator_meshes"] is True
    assert evidence["runtime_provenance"]["effective_workspace"] == str(workspace.resolve())
    content_classes = {
        row["class"]: row
        for row in evidence["bundle_contents_summary"]["mandatory_classes"]
    }
    assert content_classes["meta"]["status"] == "present"
    assert content_classes["triage"]["status"] == "present"
    assert content_classes["health"]["status"] == "present"
    assert content_classes["validation"]["status"] == "present"
    assert content_classes["manifest"]["status"] == "present"
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}
    assert evidence_ids["BND-001"]["status"] == "present"
    assert evidence_ids["BND-006"]["status"] == "present"
    assert evidence_ids["BND-002"]["status"] == "present"
    assert latest_evidence_payload["finalization_stage"] == "latest_zip_sha_inspection_proof"
    assert latest_evidence_payload["final_latest_zip_sha256"] == hashlib.sha256(latest_zip.read_bytes()).hexdigest()
    assert latest_evidence_payload["zip_sha256"] == latest_evidence_payload["final_latest_zip_sha256"]
    assert latest_evidence_payload["latest_zip_matches_original"] is True
    assert latest_evidence_payload["latest_sha_sidecar_matches"] is True
    assert latest_evidence_payload["latest_pointer_matches_original"] is True
    assert latest_inspection_payload["schema"] == "send_bundle_inspection"
    assert latest_inspection_payload["zip_path"] == str(latest_zip.resolve())
    assert latest_inspection_payload["zip_sha256"] == hashlib.sha256(latest_zip.read_bytes()).hexdigest()
    assert latest_inspection_payload["has_evidence_manifest"] is True
    assert latest_inspection_payload["has_triage_report"] is True
    assert latest_inspection_payload["has_validation_report"] is True
    assert latest_inspection_payload["has_embedded_health_report"] is True
    latest_inspection_text = latest_inspection_md.read_text(encoding="utf-8")
    assert "ZIP SHA256" in latest_inspection_text
    assert "Evidence manifest" in latest_inspection_text

    validation = validate_send_bundle(zip_path)
    assert validation.ok is True, json.dumps(validation.report_json, ensure_ascii=False, indent=2)
    warnings = [str(x) for x in (validation.report_json.get("warnings") or [])]
    assert not any(EVIDENCE_MANIFEST_ARCNAME in msg and "Missing" in msg for msg in warnings)

    text_for_encoding = (
        json.dumps(meta, ensure_ascii=False)
        + json.dumps(evidence, ensure_ascii=False)
        + latest_health.read_text(encoding="utf-8", errors="replace")
    )
    for bad in ("вЂ", "в†", "Рђ", "РЎ", "????"):
        assert bad not in text_for_encoding


def test_collection_mode_classifier_covers_manual_exit_crash_and_watchdog() -> None:
    assert classify_collection_mode("manual") == "manual"
    assert classify_collection_mode("desktop_diagnostics_center") == "manual"
    assert classify_collection_mode("auto-exit") == "exit"
    assert classify_collection_mode("auto-sys.excepthook") == "crash"
    assert classify_collection_mode("auto-threading.excepthook") == "crash"
    assert classify_collection_mode("watchdog") == "watchdog"


def test_send_bundle_evidence_manifest_tracks_windows_runtime_proof(tmp_path: Path) -> None:
    meta = {
        "python_executable": "C:/Python/python.exe",
        "python_prefix": "C:/Python",
        "python_base_prefix": "C:/Python",
        "venv_active": False,
        "preferred_cli_python": "C:/Python/python.exe",
        "effective_workspace": "C:/workspace",
    }
    evidence = build_evidence_manifest(
        zip_path=tmp_path / "bundle.zip",
        names=["workspace/exports/windows_runtime_proof.json"],
        meta=meta,
        stage="pytest",
    )
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}

    assert evidence_ids["BND-019"]["required"] is True
    assert evidence_ids["BND-019"]["required_reason"] == "windows_runtime_claimed"
    assert evidence_ids["BND-019"]["status"] == "present"
    assert "workspace/exports/windows_runtime_proof.json" in evidence_ids["BND-019"]["present_paths"]


def test_make_send_bundle_embeds_engineering_analysis_evidence_for_validation_and_inspection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root, out_dir, _workspace = _prepare_repo_and_workspace(tmp_path, monkeypatch)
    engineering_payload = {
        "schema": "desktop_engineering_analysis_evidence_manifest",
        "schema_version": "1.0.0",
        "handoff_id": "HO-009",
        "produced_by": "WS-ANALYSIS",
        "consumed_by": "WS-DIAGNOSTICS",
        "run_dir": "C:/runs/RUN_engineering",
        "validation": {
            "status": "PASS",
            "influence_status": "PASS",
            "calibration_status": "PASS",
            "compare_status": "MISSING",
        },
        "unit_catalog": {"Kphi": "N*m/rad", "eps_rel_used": "dimensionless"},
        "sensitivity_summary": [{"param": "база", "score": 1.0, "status": "ok"}],
        "selected_artifact_list": [{"key": "system_influence_json", "sha256": "abc"}],
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
            "status_counts": {"MISSING_INPUTS": 1, "READY": 1},
            "unique_missing_inputs": ["results_csv_path"],
            "unique_blocking_states": ["missing results artifact"],
            "ready_run_dirs": ["C:/workspace/opt_runs/coord/run_ready"],
            "candidates": [
                {"run_id": "run_ready", "bridge_status": "READY"},
                {
                    "run_id": "run_missing",
                    "bridge_status": "MISSING_INPUTS",
                    "missing_inputs": ["results_csv_path"],
                },
            ],
        },
        "evidence_manifest_hash": "engineering-hash-001",
    }
    (out_dir / ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME).write_text(
        json.dumps(engineering_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    zip_path = make_send_bundle(
        repo_root=repo_root,
        out_dir=out_dir,
        keep_last_n=1,
        max_file_mb=20,
        trigger="manual",
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        embedded = json.loads(zf.read(ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME).decode("utf-8", errors="replace"))
        evidence = json.loads(zf.read(EVIDENCE_MANIFEST_ARCNAME).decode("utf-8", errors="replace"))

    assert ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME in names
    assert embedded["schema"] == "desktop_engineering_analysis_evidence_manifest"
    assert embedded["evidence_manifest_hash"] == "engineering-hash-001"
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}
    assert evidence_ids["BND-021"]["status"] == "present"
    assert ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME in evidence_ids["BND-021"]["present_paths"]

    validation = validate_send_bundle(zip_path)
    assert validation.ok is True, json.dumps(validation.report_json, ensure_ascii=False, indent=2)
    validation_engineering = dict(validation.report_json.get("engineering_analysis_evidence") or {})
    assert validation_engineering["status"] == "READY"
    assert validation_engineering["evidence_manifest_hash"] == "engineering-hash-001"
    assert validation_engineering["influence_status"] == "PASS"
    assert validation_engineering["handoff_requirements"]["contract_status"] == "READY"
    assert validation_engineering["selected_run_candidate_count"] == 2
    assert validation_engineering["selected_run_ready_candidate_count"] == 1
    assert validation_engineering["selected_run_missing_inputs_candidate_count"] == 1

    inspection = inspect_send_bundle(zip_path)
    inspection_md = render_inspection_md(inspection)
    assert inspection["has_engineering_analysis_evidence"] is True
    inspection_engineering = dict(inspection["engineering_analysis_evidence"])
    assert inspection_engineering["evidence_manifest_hash"] == "engineering-hash-001"
    assert inspection_engineering["selected_run_ready_candidate_count"] == 1
    assert "Engineering analysis evidence" in inspection_md
    assert "engineering-hash-001" in inspection_md
    assert "handoff_contract_status" in inspection_md
    assert "selected_run_ready_candidate_count" in inspection_md


def test_send_bundle_evidence_analysis_handoff_prefers_latest_sidecar(tmp_path: Path) -> None:
    out_dir = tmp_path / "send_bundles"
    workspace = tmp_path / "workspace"
    out_dir.mkdir()
    (workspace / "exports").mkdir(parents=True)
    zip_path = out_dir / "bundle.zip"
    (out_dir / ANALYSIS_EVIDENCE_SIDECAR_NAME).write_text(
        json.dumps(_analysis_manifest(run_id="run-sidecar", manifest_hash="hash-sidecar"), ensure_ascii=False),
        encoding="utf-8",
    )
    (workspace / "exports" / "analysis_evidence_manifest.json").write_text(
        json.dumps(_analysis_manifest(run_id="run-workspace", manifest_hash="hash-workspace"), ensure_ascii=False),
        encoding="utf-8",
    )

    evidence = build_evidence_manifest(
        zip_path=zip_path,
        names=[ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME],
        meta={
            "python_executable": "C:/Python/python.exe",
            "python_prefix": "C:/Python",
            "python_base_prefix": "C:/Python",
            "venv_active": False,
            "preferred_cli_python": "C:/Python/python.exe",
            "effective_workspace": str(workspace),
        },
        json_by_name={
            ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME: _analysis_manifest(
                run_id="run-workspace",
                manifest_hash="hash-workspace",
            ),
        },
        stage="pytest",
    )

    handoff = evidence["analysis_handoff"]
    assert handoff["status"] == "READY"
    assert handoff["source_path"].endswith(ANALYSIS_EVIDENCE_SIDECAR_NAME)
    assert handoff["run_id"] == "run-sidecar"
    assert handoff["evidence_manifest_hash"] == "hash-sidecar"
    assert handoff["artifact_count"] == 2
    assert evidence_manifest_warnings(evidence) == evidence["missing_warnings"]


def test_send_bundle_evidence_analysis_handoff_warns_for_stale_and_missing(tmp_path: Path) -> None:
    stale = _analysis_manifest(
        run_id="run-stale",
        manifest_hash="hash-stale",
        state="STALE",
        mismatches=[{"key": "run_contract_hash", "current": "new", "selected": "old"}],
    )
    evidence = build_evidence_manifest(
        zip_path=tmp_path / "bundle.zip",
        names=[ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME],
        meta={
            "python_executable": "C:/Python/python.exe",
            "python_prefix": "C:/Python",
            "python_base_prefix": "C:/Python",
            "venv_active": False,
            "preferred_cli_python": "C:/Python/python.exe",
            "effective_workspace": str(tmp_path / "workspace"),
        },
        json_by_name={ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME: stale},
        stage="pytest",
    )

    warnings = evidence_manifest_warnings(evidence)
    assert evidence["analysis_handoff"]["status"] == "WARN"
    assert evidence["analysis_handoff"]["result_context_state"] == "STALE"
    assert evidence["analysis_handoff"]["mismatch_count"] == 1
    assert any("context is STALE" in msg for msg in warnings)
    assert any("context mismatch" in msg for msg in warnings)

    missing = build_evidence_manifest(
        zip_path=tmp_path / "missing.zip",
        names=[],
        meta={
            "python_executable": "C:/Python/python.exe",
            "python_prefix": "C:/Python",
            "python_base_prefix": "C:/Python",
            "venv_active": False,
            "preferred_cli_python": "C:/Python/python.exe",
            "effective_workspace": str(tmp_path / "workspace"),
        },
        stage="pytest",
    )
    assert missing["analysis_handoff"]["status"] == "MISSING"
    assert any("Analysis evidence / HO-009 missing" in msg for msg in evidence_manifest_warnings(missing))


def test_geometry_reference_evidence_handoff_reaches_manifest_validation_and_diagnostics_record(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "send_bundles"
    repo_root = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out_dir.mkdir()
    (workspace / "exports").mkdir(parents=True)
    payload = _geometry_reference_evidence()
    zip_path = out_dir / "bundle.zip"

    evidence = build_evidence_manifest(
        zip_path=zip_path,
        names=[GEOMETRY_REFERENCE_EVIDENCE_ARCNAME],
        meta={
            "python_executable": "C:/Python/python.exe",
            "python_prefix": "C:/Python",
            "python_base_prefix": "C:/Python",
            "venv_active": False,
            "preferred_cli_python": "C:/Python/python.exe",
            "effective_workspace": str(workspace),
        },
        json_by_name={GEOMETRY_REFERENCE_EVIDENCE_ARCNAME: payload},
        stage="pytest",
    )
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}

    assert evidence_ids["BND-018"]["status"] == "present"
    assert evidence["geometry_reference_handoff"]["status"] == "READY"
    assert evidence["geometry_reference_handoff"]["artifact_freshness_status"] == "current"
    assert evidence["geometry_reference_handoff"]["artifact_freshness_relation"] == "matches_latest"
    assert evidence["geometry_reference_handoff"]["road_width_status"] == "explicit_meta"
    assert evidence["geometry_reference_handoff"]["packaging_contract_hash"] == "packaging-hash"
    assert not any("Geometry reference" in msg for msg in evidence_manifest_warnings(evidence))

    summary = summarize_geometry_reference_evidence(payload, source_path=GEOMETRY_REFERENCE_EVIDENCE_ARCNAME)
    assert summary["status"] == "READY"
    assert summary["artifact_freshness_relation"] == "matches_latest"
    assert summary["geometry_acceptance_gate"] == "PASS"

    (out_dir / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    record = load_desktop_diagnostics_bundle_record(repo_root, out_dir=out_dir)
    assert record.geometry_reference_status == "READY"
    assert record.geometry_reference_artifact_freshness_status == "current"
    assert record.geometry_reference_artifact_freshness_relation == "matches_latest"
    assert record.geometry_reference_acceptance_gate == "PASS"
    assert record.geometry_reference_packaging_contract_hash == "packaging-hash"
    assert record.latest_geometry_reference_evidence_path.endswith(GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest"}, ensure_ascii=False))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr(GEOMETRY_REFERENCE_EVIDENCE_ARCNAME, json.dumps(payload, ensure_ascii=False))
        zf.writestr(EVIDENCE_MANIFEST_ARCNAME, json.dumps(evidence, ensure_ascii=False, indent=2))
    validation = validate_send_bundle(zip_path)
    assert validation.report_json["geometry_reference_evidence"]["status"] == "READY"
    assert validation.report_json["geometry_reference_evidence"]["artifact_freshness_relation"] == "matches_latest"


def test_send_bundle_includes_full_runtime_evidence_set_and_manifest_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root, out_dir, workspace = _prepare_repo_and_workspace(tmp_path, monkeypatch)
    exports = workspace / "exports"

    write_browser_perf_trace_artifact(
        exports,
        {"traceEvents": [{"name": "present", "ts": 100}]},
        trace_session_id="send-bundle-runtime",
    )
    write_browser_perf_artifacts(
        exports,
        {
            "updated_utc": "2026-04-17T00:00:00Z",
            "dataset_id": "send-bundle-runtime",
            "components": {
                "playhead_ctrl": {"viewport_state": "visible", "wakeups": 1, "render_count": 1},
                "details_pane": {
                    "viewport_state": "offscreen",
                    "wakeups": 0,
                    "render_count": 0,
                    "schedule_raf_count": 0,
                    "schedule_timeout_count": 0,
                },
            },
        },
        updated_utc="2026-04-17T00:00:01Z",
    )
    frame_budget = build_frame_budget_evidence(
        panels={
            "dock_hud": {"count": 3, "hz": 60.0, "visible": True},
            "dock_hidden": {"count": 0, "hz": 0.0, "visible": False},
        },
        visible_aux=1,
        total_aux_docks=2,
        playing=True,
        many_visible_budget=False,
        frame_budget_active=False,
        window_s=1.0,
        source_dt_s=1.0 / 60.0,
        frame_cadence={"target_interval_ms": 16, "measured_present_hz": 59.9, "present_dt_ema_ms": 16.7},
        updated_utc="2026-04-17T00:00:02Z",
        provenance={"producer": "pytest"},
    )
    (exports / ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME).write_text(
        json.dumps(frame_budget, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_windows_runtime_proof(
        exports,
        build_windows_runtime_proof(
            checks={
                "native_titlebar_system_menu": True,
                "snap_half_third_quarter": True,
                "docking_undocking_floating": True,
                "second_monitor_workflow": True,
                "mixed_dpi_or_pmv2": True,
                "keyboard_f6_focus": True,
                "resize_affordances": True,
                "portable_path_budget": True,
                "send_bundle_latest_pointer": True,
            },
            path_budget={"status": "PASS", "max_full_path_chars": 120},
            updated_utc="2026-04-17T00:00:03Z",
        ),
    )

    zip_path = make_send_bundle(
        repo_root=repo_root,
        out_dir=out_dir,
        keep_last_n=1,
        max_file_mb=20,
        trigger="manual",
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        evidence = json.loads(zf.read(EVIDENCE_MANIFEST_ARCNAME).decode("utf-8", errors="replace"))

    expected_paths = {
        "workspace/exports/browser_perf_trace.json",
        "workspace/exports/viewport_gating_report.json",
        "workspace/exports/animator_frame_budget_evidence.json",
        "workspace/exports/windows_runtime_proof.json",
    }
    assert expected_paths <= names
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}
    for evidence_id in ("BND-015", "BND-016", "BND-017", "BND-019"):
        assert evidence_ids[evidence_id]["status"] == "present"


def test_send_bundle_evidence_manifest_tracks_active_baseline_history_and_mismatch(tmp_path: Path) -> None:
    suite = build_validated_suite_snapshot(
        [
            {
                "id": "baseline-row-1",
                "имя": "baseline_smoke",
                "тип": "инерция_крен",
                "включен": True,
                "стадия": 0,
            }
        ],
        inputs_snapshot_hash="inputs-hash-1",
        ring_source_hash="ring-hash-1",
        created_at_utc="2026-04-17T01:00:00Z",
        context_label="send-bundle-baseline",
    )
    active = build_active_baseline_contract(
        suite_snapshot=suite,
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-active"},
        created_at_utc="2026-04-17T01:01:00Z",
    )
    historical = build_active_baseline_contract(
        suite_snapshot=build_validated_suite_snapshot(
            [{"id": "baseline-row-1", "имя": "baseline_smoke", "тип": "инерция_крен", "включен": True}],
            inputs_snapshot_hash="inputs-hash-2",
            ring_source_hash="ring-hash-1",
            created_at_utc="2026-04-17T01:02:00Z",
            context_label="send-bundle-baseline-historical",
        ),
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-historical"},
        policy_mode="restore_only",
        created_at_utc="2026-04-17T01:03:00Z",
    )
    history_item = baseline_history_item_from_contract(historical, action="restore", actor="unit")
    meta = {
        "python_executable": "C:/Python/python.exe",
        "python_prefix": "C:/Python",
        "python_base_prefix": "C:/Python",
        "venv_active": False,
        "preferred_cli_python": "C:/Python/python.exe",
        "effective_workspace": "C:/workspace",
    }
    names = [
        "workspace/handoffs/WS-SUITE/validated_suite_snapshot.json",
        "workspace/handoffs/WS-BASELINE/active_baseline_contract.json",
        "workspace/baselines/baseline_history.jsonl",
    ]
    evidence = build_evidence_manifest(
        zip_path=tmp_path / "bundle.zip",
        names=names,
        meta=meta,
        json_by_name={
            "workspace/handoffs/WS-SUITE/validated_suite_snapshot.json": suite,
            "workspace/handoffs/WS-BASELINE/active_baseline_contract.json": active,
            "workspace/baselines/baseline_history.jsonl": {"rows": [history_item]},
        },
        stage="pytest",
    )
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}
    baseline = dict(evidence["baseline_center_evidence"])

    assert evidence_ids["BND-010"]["status"] == "present"
    assert evidence_ids["BND-020"]["status"] == "present"
    assert baseline["active_baseline_hash"] == active["active_baseline_hash"]
    assert baseline["banner_state"]["state"] == "current"
    assert baseline["mismatch_state"]["has_mismatch"] is True
    assert baseline["mismatch_state"]["rows"][0]["state"] == "historical_mismatch"
    assert baseline["silent_rebinding_allowed"] is False


def test_send_gui_preserves_exit_crash_and_watchdog_trigger_provenance() -> None:
    center_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    launcher_src = (ROOT / "pneumo_solver_ui" / "tools" / "launch_ui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    watchdog_src = (ROOT / "pneumo_solver_ui" / "tools" / "postmortem_watchdog.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'os.environ.get("PNEUMO_SEND_BUNDLE_TRIGGER")' in center_src
    assert "trigger=trigger" in center_src
    assert '"auto-exit"' in launcher_src
    assert '"auto-crash-rc-' in launcher_src
    assert 'send_env["PNEUMO_SEND_RESULTS_REUSE_LATEST"] = "1"' in watchdog_src
    assert 'send_env["PNEUMO_SEND_BUNDLE_TRIGGER"] = "watchdog"' in watchdog_src


def test_missing_evidence_warnings_reach_validation_and_health(tmp_path: Path) -> None:
    zip_path = tmp_path / "bundle.zip"
    meta = {
        "release": "pytest",
        "created_at": "2026-04-17T00:00:00",
        "trigger": "manual",
        "collection_mode": "manual",
        "python_executable": "C:/Python/python.exe",
        "python_prefix": "C:/Python",
        "python_base_prefix": "C:/Python",
        "venv_active": False,
        "preferred_cli_python": "C:/Python/python.exe",
        "effective_workspace": "C:/workspace",
    }
    diag = {
        "anim_latest_available": True,
        "anim_latest_visual_cache_token": "tok-ring",
        "anim_latest_npz_path": "C:/workspace/exports/anim_latest.npz",
        "anim_latest_meta": {
            "scenario_kind": "ring",
            "scenario_json": "scenario.json",
        },
    }
    analysis_stale = _analysis_manifest(
        run_id="run-validation-stale",
        manifest_hash="hash-validation-stale",
        state="STALE",
        mismatches=[{"key": "run_contract_hash", "current": "new", "selected": "old"}],
    )
    base_entries: dict[str, object] = {
        "bundle/meta.json": meta,
        "bundle/manifest.json": {},
        "bundle/summary.json": {"added_files": 1},
        "bundle/skips.json": [],
        "bundle/README_SEND_BUNDLE.txt": "README",
        "MANIFEST.json": {},
        "triage/triage_report.md": "# triage\n",
        "triage/triage_report.json": {"severity_counts": {"critical": 0}, "red_flags": []},
        "triage/latest_anim_pointer_diagnostics.json": diag,
        "triage/latest_anim_pointer_diagnostics.md": "# anim\n",
        "validation/validation_report.json": {"ok": True, "errors": [], "warnings": []},
        "dashboard/dashboard.json": {"sections": {}, "warnings": [], "errors": []},
        "health/health_report.json": {"schema": "health_report", "ok": True},
        "health/health_report.md": "# health\n",
        "ui_logs/app.log": "ok\n",
        "workspace/exports/.gitkeep": "",
        ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME: analysis_stale,
        "workspace/uploads/placeholder.txt": "u",
        "workspace/road_profiles/placeholder.txt": "r",
        "workspace/maneuvers/placeholder.txt": "m",
        "workspace/opt_runs/placeholder.txt": "o",
        "workspace/ui_state/autosave_profile.json": {"ui_x": 1},
    }
    evidence = build_evidence_manifest(
        zip_path=zip_path,
        names=list(base_entries.keys()),
        meta=meta,
        json_by_name={
            "triage/latest_anim_pointer_diagnostics.json": diag,
            ANALYSIS_EVIDENCE_WORKSPACE_ARCNAME: analysis_stale,
        },
        planned_paths=(EVIDENCE_MANIFEST_ARCNAME,),
        stage="pytest",
    )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, payload in base_entries.items():
            if isinstance(payload, (dict, list)):
                zf.writestr(arcname, json.dumps(payload, ensure_ascii=False, indent=2))
            elif isinstance(payload, str):
                zf.writestr(arcname, payload)
            else:
                zf.writestr(arcname, str(payload))
        zf.writestr(EVIDENCE_MANIFEST_ARCNAME, json.dumps(evidence, ensure_ascii=False, indent=2))

    validation = validate_send_bundle(zip_path)
    warnings = [str(x) for x in (validation.report_json.get("warnings") or [])]
    assert validation.ok is True
    assert any("Missing evidence BND-007" in msg for msg in warnings)
    assert any("Missing evidence BND-008" in msg for msg in warnings)
    assert any("Analysis evidence / HO-009 context is STALE" in msg for msg in warnings)

    health_json, health_md = build_health_report(zip_path, out_dir=tmp_path)
    health = json.loads(Path(health_json).read_text(encoding="utf-8"))
    notes = [str(x) for x in (health.get("notes") or [])]
    md_text = Path(health_md).read_text(encoding="utf-8", errors="replace")
    assert any("Missing evidence BND-007" in msg for msg in notes)
    assert any("Analysis evidence / HO-009 context is STALE" in msg for msg in notes)
    assert "## Evidence manifest" in md_text
    assert "missing_evidence: Missing evidence BND-007" in md_text
    assert "missing_evidence: Analysis evidence / HO-009 context is STALE" in md_text
