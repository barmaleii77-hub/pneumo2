from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pneumo_solver_ui.desktop_engineering_analysis_model import (
    ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
    SELECTED_RUN_HANDOFF_ID,
    SELECTED_RUN_PRODUCED_BY,
    SelectedRunContext,
    build_analysis_compare_contract,
    build_analysis_to_animator_link_contract,
    build_compare_influence_surface,
    build_sensitivity_summary,
    infer_engineering_unit,
)
from pneumo_solver_ui.desktop_engineering_analysis_runtime import (
    LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST,
    DesktopEngineeringAnalysisRuntime,
    load_selected_run_contract,
)
from pneumo_solver_ui.optimization_objective_contract import (
    objective_contract_hash,
    objective_contract_payload,
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_system_influence_payload() -> dict:
    return {
        "version": "system_influence_report_v1",
        "config": {
            "requested_eps_rel": 0.01,
            "adaptive_eps": True,
            "stage_name": "stage1_long",
        },
        "baseline": {
            "pneumo": {
                "min_bottleneck_mdot": 0.032,
                "avg_bottleneck_mdot": 0.051,
            },
            "mech": {
                "Kphi": 12000.0,
                "f_roll": 1.45,
            },
        },
        "params": [
            {
                "param": "база",
                "group": "kinematics",
                "score": 1.4,
                "status": "ok",
                "eps_rel_used": 0.001,
                "elas_Kphi": 1.2,
                "elas_min_bottleneck_mdot": 0.1,
            },
            {
                "param": "клапан_dp_переход_Па",
                "group": "pneumatics",
                "score": 0.8,
                "status": "ok",
                "eps_rel_used": 0.003,
                "elas_Kphi": 0.0,
                "elas_min_bottleneck_mdot": -0.8,
            },
            {
                "param": "колея",
                "group": "kinematics",
                "score": 0.2,
                "status": "ok",
                "eps_rel_used": 0.001,
                "elas_Kphi": 0.2,
                "elas_f_roll": 0.1,
            },
        ],
    }


def _build_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "RUN_engineering_analysis"
    payload = _build_system_influence_payload()
    _write_json(run_dir / "system_influence.json", payload)
    _write_text(run_dir / "SYSTEM_INFLUENCE.md", "# System Influence\n")
    _write_text(
        run_dir / "system_influence_params.csv",
        "param,group,score,eps_rel_used\nбаза,kinematics,1.4,0.001\n",
    )
    _write_text(run_dir / "system_influence_edges.csv", "edge,mdot_ref\nE1,0.032\n")
    _write_text(run_dir / "system_influence_paths.csv", "chamber,path_bottleneck_mdot\nC1,0.032\n")
    _write_text(run_dir / "REPORT_FULL.md", "# REPORT_FULL\n")
    _write_json(run_dir / "fit_report_final.json", {"best_rmse": 0.12, "success": True})
    _write_json(run_dir / "fit_details_final.json", {"tests": [], "signals": []})
    _write_json(
        run_dir / "compare_influence.json",
        {
            "schema": "compare_influence_fixture",
            "title": "Fixture compare influence",
            "corr_matrix": [[0.25, -0.75], [0.91, 0.1]],
            "feature_names": ["база", "колея"],
            "target_names": ["RMS(положение_штока_ЛП_м)", "MAXABS(давление_ресивер1_Па)"],
            "feature_units": {"база": "m", "колея": "m"},
            "target_units": {
                "RMS(положение_штока_ЛП_м)": "m",
                "MAXABS(давление_ресивер1_Па)": "Pa",
            },
        },
    )
    return run_dir


def _selected_run_contract_payload(run_dir: Path, **overrides) -> dict:
    result_path = run_dir / "compare_influence.json"
    payload = {
        "schema_version": "selected_run_contract_v1",
        "handoff_id": SELECTED_RUN_HANDOFF_ID,
        "source_workspace": SELECTED_RUN_PRODUCED_BY,
        "target_workspace": "WS-ANALYSIS",
        "run_id": "run-analysis-001",
        "run_name": run_dir.name,
        "run_dir": str(run_dir),
        "mode": "distributed_coordinator",
        "status": "done",
        "started_at_utc": "2026-04-17T00:00:00Z",
        "finished_at_utc": "2026-04-17T00:05:00Z",
        "objective_contract_hash": "objective-hash-001",
        "objective_stack": ["min_rms", "min_pressure"],
        "hard_gate_key": "max_pressure_pa",
        "hard_gate_tolerance": 250000.0,
        "active_baseline_hash": "baseline-hash-001",
        "suite_snapshot_hash": "suite-hash-001",
        "problem_hash": "problem-hash-001",
        "results_csv_path": str(result_path),
        "artifact_dir": str(run_dir),
        "analysis_handoff_ready_state": "ready",
        "diagnostics_handoff_ready_state": "not_finalized_by_optimizer",
        "results_artifact_index": {
            "run_dir": str(run_dir),
            "results_csv_path": str(result_path),
            "objective_contract_path": str(run_dir / "objective_contract.json"),
        },
    }
    for key, value in overrides.items():
        if value is None:
            payload.pop(key, None)
        else:
            payload[key] = value
    return payload


def _write_selected_run_contract(path: Path, run_dir: Path, **overrides) -> Path:
    _write_json(path, _selected_run_contract_payload(run_dir, **overrides))
    return path


def _build_optimizer_ready_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "pneumo_solver_ui" / "workspace" / "opt_runs" / "coord" / "p_ho007_bridge_ready"
    _write_text(run_dir / "export" / "trials.csv", "status,metrics_json\nDONE,\"{}\"\n")
    _write_text(run_dir / "coordinator.log", "done=1/1\n")
    _write_text(run_dir / "run_id.txt", "run_ho007_bridge_ready")
    _write_json(
        run_dir / "baseline_source.json",
        {
            "active_baseline_hash": "active-baseline-hash-bridge",
            "suite_snapshot_hash": "suite-snapshot-hash-bridge",
        },
    )
    _write_json(
        run_dir / "objective_contract.json",
        objective_contract_payload(
            source="engineering_analysis_bridge_test",
        ),
    )
    return run_dir


def test_compare_influence_surface_preserves_units_and_diagnostics() -> None:
    corr = np.asarray(
        [
            [0.10, -0.82],
            [0.96, 0.25],
        ],
        dtype=float,
    )
    surface = build_compare_influence_surface(
        corr,
        ["база", "колея"],
        ["RMS(положение_штока_ЛП_м)", "MAXABS(давление_ресивер1_Па)"],
        feature_units={"база": "m", "колея": "m"},
        target_units={
            "RMS(положение_штока_ЛП_м)": "m",
            "MAXABS(давление_ресивер1_Па)": "Pa",
        },
        top_k=3,
    )

    assert surface["surface_type"] == "compare_influence"
    assert surface["diagnostics"]["shape_matches_axes"] is True
    assert surface["diagnostics"]["finite_cell_count"] == 4
    assert surface["diagnostics"]["max_abs_corr"] == 0.96
    assert surface["ranked_features"][0] == "колея"
    assert surface["top_cells"][0]["feature"] == "колея"
    assert surface["top_cells"][0]["target_unit"] == "m"
    assert surface["axes"]["features"][0]["unit"] == "m"


def test_sensitivity_summary_ranks_influence_rows_and_units_are_explicit() -> None:
    summary = build_sensitivity_summary(_build_system_influence_payload(), top_k=2)

    assert [row.param for row in summary] == ["база", "клапан_dp_переход_Па"]
    assert summary[0].strongest_metric == "elas_Kphi"
    assert summary[1].strongest_metric == "elas_min_bottleneck_mdot"
    assert infer_engineering_unit("elas_Kphi") == "dimensionless"
    assert infer_engineering_unit("min_bottleneck_mdot") == "kg/s"
    assert infer_engineering_unit("Kphi") == "N*m/rad"


def test_engineering_analysis_runtime_validates_artifacts_and_exports_evidence(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    assert snapshot.status == "PASS"
    assert snapshot.contract_status == "READY"
    assert snapshot.selected_run_context is not None
    assert snapshot.selected_run_context.run_id == "run-analysis-001"
    assert snapshot.selected_run_context.objective_contract_hash == "objective-hash-001"
    assert snapshot.selected_run_context.hard_gate_key == "max_pressure_pa"
    assert snapshot.selected_run_context.active_baseline_hash == "baseline-hash-001"
    assert snapshot.selected_run_context.suite_snapshot_hash == "suite-hash-001"
    assert snapshot.influence_status == "PASS"
    assert snapshot.calibration_status == "PASS"
    assert snapshot.compare_status == "PASS"
    assert snapshot.artifact_by_key("system_influence_json") is not None
    assert snapshot.artifact_by_key("report_full_md") is not None
    assert snapshot.sensitivity_rows[0].param == "база"
    assert snapshot.unit_catalog["eps_rel_used"] == "dimensionless"
    assert snapshot.unit_catalog["min_bottleneck_mdot"] == "kg/s"

    surface = build_compare_influence_surface(
        np.asarray([[1.0], [-1.0]], dtype=float),
        ["база", "колея"],
        ["RMS(положение_штока_ЛП_м)"],
        feature_units={"база": "m", "колея": "m"},
        target_units={"RMS(положение_штока_ЛП_м)": "m"},
    )
    sidecar = runtime.write_diagnostics_evidence_manifest(
        snapshot,
        compare_surfaces=[surface],
    )

    workspace_manifest = tmp_path / "pneumo_solver_ui" / "workspace" / "exports" / "engineering_analysis_evidence_manifest.json"
    assert sidecar == (tmp_path / "send_bundles" / LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST).resolve()
    assert sidecar.exists()
    assert workspace_manifest.exists()

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["schema"] == "desktop_engineering_analysis_evidence_manifest"
    assert payload["handoff_id"] == "HO-009"
    assert payload["produced_by"] == "WS-ANALYSIS"
    assert payload["consumed_by"] == "WS-DIAGNOSTICS"
    assert payload["upstream_handoff"]["handoff_id"] == "HO-007"
    assert payload["upstream_handoff"]["selected_run_contract_path"] == str(contract_path.resolve())
    assert payload["upstream_handoff"]["run_id"] == "run-analysis-001"
    assert payload["upstream_handoff"]["objective_contract_hash"] == "objective-hash-001"
    assert payload["upstream_handoff"]["hard_gate_key"] == "max_pressure_pa"
    assert payload["upstream_handoff"]["active_baseline_hash"] == "baseline-hash-001"
    assert payload["upstream_handoff"]["suite_snapshot_hash"] == "suite-hash-001"
    assert payload["handoff_requirements"]["handoff_id"] == "HO-007"
    assert payload["handoff_requirements"]["can_run_engineering_analysis"] is True
    assert payload["handoff_requirements"]["missing_fields"] == []
    assert payload["selected_run_candidate_readiness"]["schema"] == "selected_run_candidate_readiness.v1"
    assert payload["selected_run_candidate_readiness"]["candidate_count"] == 0
    assert payload["diagnostics_bundle_finalized"] is False
    assert payload["validation"]["influence_status"] == "PASS"
    assert payload["validation"]["selected_run_contract_status"] == "READY"
    assert payload["unit_catalog"]["Kphi"] == "N*m/rad"
    assert payload["sensitivity_summary"][0]["param"] == "база"
    assert payload["compare_influence_surfaces"][0]["diagnostics"]["finite_cell_count"] == 2
    assert payload["evidence_manifest_hash"]
    pipeline = {item["key"]: item for item in payload["analysis_workspace_pipeline"]}
    assert pipeline["selected_run_context"]["status"] == "READY"
    assert pipeline["calibration_fit_reports"]["status"] == "READY"
    assert pipeline["influence_system"]["status"] == "READY"
    assert pipeline["sensitivity_summary"]["status"] == "READY"
    assert pipeline["handoff_ho008_animator"]["status"] in {"MISSING", "BLOCKED"}
    assert payload["runtime_data_gaps"]
    assert payload["validated_artifacts"]["schema"] == "engineering_analysis_validated_artifacts.v1"
    assert payload["validated_artifacts"]["status"] == "READY"
    assert payload["validated_artifacts"]["required_artifact_count"] == 3
    assert payload["validated_artifacts"]["ready_required_artifact_count"] == 3
    assert payload["validated_artifacts"]["missing_required_artifacts"] == []

    records = {item["key"]: item for item in payload["selected_artifact_list"]}
    assert records["system_influence_json"]["sha256"]
    assert records["system_influence_json"]["size_bytes"] > 0
    assert records["system_influence_json"]["source_run_dir"] == str(run_dir.resolve())
    assert records["system_influence_json"]["source_relpath"] == "system_influence.json"
    assert records["system_influence_json"]["source_selected_run_contract_hash"] == snapshot.selected_run_contract_hash
    assert records["system_influence_json"]["source_objective_contract_hash"] == "objective-hash-001"
    assert records["report_full_md"]["sha256"]
    assert any(item["key"] == "report_full_md" for item in payload["report_provenance"])
    validated_records = {
        item["key"]: item
        for item in payload["validated_artifacts"]["expected_artifacts"]
    }
    assert validated_records["system_influence_json"]["validation_status"] == "READY"
    assert validated_records["system_influence_params_csv"]["validation_status"] == "READY"

    refreshed = runtime.snapshot(selected_contract_path=contract_path)
    assert refreshed.diagnostics_evidence_manifest_path == sidecar
    assert refreshed.diagnostics_evidence_manifest_status == "READY"
    assert refreshed.diagnostics_evidence_manifest_hash == payload["evidence_manifest_hash"]
    refreshed_pipeline = {row.key: row for row in runtime.analysis_workspace_pipeline_status(refreshed)}
    assert refreshed_pipeline["handoff_ho009_diagnostics"].status == "READY"


def test_evidence_export_builds_compare_influence_surfaces_from_artifacts(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    surfaces = runtime.compare_influence_surfaces(snapshot)

    assert len(surfaces) == 1
    assert surfaces[0]["surface_type"] == "compare_influence"
    assert surfaces[0]["source"].endswith("compare_influence.json")
    assert surfaces[0]["diagnostics"]["shape_matches_axes"] is True
    assert surfaces[0]["diagnostics"]["finite_cell_count"] == 4
    assert surfaces[0]["top_cells"][0]["feature"] == "колея"
    assert surfaces[0]["top_cells"][0]["target_unit"] == "m"

    sidecar = runtime.write_diagnostics_evidence_manifest(snapshot)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["compare_influence_surfaces"][0]["diagnostics"]["finite_cell_count"] == 4
    assert payload["selected_charts"] == ["Fixture compare influence"]


def test_evidence_export_reports_missing_required_validated_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN_partial_engineering_analysis"
    _write_json(run_dir / "system_influence.json", _build_system_influence_payload())
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    payload = runtime.build_diagnostics_evidence_manifest(snapshot)

    validated = payload["validated_artifacts"]
    assert validated["status"] == "MISSING"
    assert validated["required_artifact_count"] == 3
    assert validated["ready_required_artifact_count"] == 1
    missing_keys = {item["key"] for item in validated["missing_required_artifacts"]}
    assert missing_keys == {"system_influence_md", "system_influence_params_csv"}
    records = {item["key"]: item for item in validated["expected_artifacts"]}
    assert records["system_influence_json"]["validation_status"] == "READY"
    assert records["system_influence_md"]["validation_status"] == "MISSING"
    assert any(
        "Required engineering analysis artifact(s) missing or unvalidated" in warning
        for warning in payload["validation"]["warnings"]
    )


def test_evidence_export_warns_when_compare_influence_artifact_is_unparseable(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    _write_json(run_dir / "compare_influence.json", {"schema": "compare_influence_fixture"})
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    payload = runtime.build_diagnostics_evidence_manifest(snapshot)

    assert payload["compare_influence_surfaces"] == []
    assert payload["selected_charts"] == []
    diagnostics = payload["compare_influence_diagnostics"]
    assert diagnostics["artifact_count"] == 1
    assert diagnostics["surface_count"] == 0
    assert diagnostics["source"] == "artifact_auto_discovery"
    assert diagnostics["unparsed_artifacts"][0].endswith("compare_influence.json")
    assert any(
        "no parseable compare_influence surface" in warning
        for warning in payload["validation"]["warnings"]
    )

    sidecar = runtime.write_diagnostics_evidence_manifest(snapshot)
    exported = json.loads(sidecar.read_text(encoding="utf-8"))
    assert exported["compare_influence_diagnostics"]["surface_count"] == 0
    assert exported["validation"]["warnings"] == payload["validation"]["warnings"]


def test_v38_pipeline_status_exposes_static_trim_uq_handoffs_and_gaps(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    results_csv = run_dir / "selected_results.csv"
    _write_text(
        results_csv,
        "static_trim_success,static_trim_body_height_err_max_m,static_trim_pressure_trim_enable,"
        "static_trim_pressure_trim_mode,static_trim_pressure_trim_max_abs_scale_delta\n"
        "true,0.0004,true,per_corner,0.2\n",
    )
    _write_json(run_dir / "AUTOPILOT_V20_WRAPPER.json", {"status": "done", "out_dir": str(run_dir)})
    _write_text(run_dir / "uq_sensitivity_summary.csv", "param,importance\nKphi,0.8\n")
    _write_text(run_dir / "measurement_priority.csv", "component,priority\nfront_left,0.9\n")
    _write_text(run_dir / "uq_runs.csv", "run,metric\n1,0.1\n")
    _write_text(run_dir / "uq_report.md", "# UQ report\n")
    contract_path = _write_selected_run_contract(
        tmp_path / "selected_run_contract.json",
        run_dir,
        results_csv_path=str(results_csv),
        results_artifact_index={
            "run_dir": str(run_dir),
            "results_csv_path": str(results_csv),
            "objective_contract_path": str(run_dir / "objective_contract.json"),
        },
    )
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    rows = {row.key: row.to_payload() for row in runtime.analysis_workspace_pipeline_status(snapshot)}

    assert rows["selected_run_context"]["status"] == "READY"
    assert rows["calibration_autopilot_v20"]["status"] == "READY"
    assert rows["calibration_static_trim"]["status"] == "READY"
    assert rows["calibration_static_trim"]["metrics"]["static_trim_body_height_err_max_m"] == "0.0004"
    assert rows["calibration_static_trim"]["units"]["static_trim_body_height_err_max_m"] == "m"
    assert rows["influence_compare_surfaces"]["status"] == "READY"
    assert rows["sensitivity_summary"]["status"] == "READY"
    assert rows["uncertainty_uq"]["status"] == "READY"
    assert rows["handoff_ho008_animator"]["status"] in {"MISSING", "BLOCKED"}
    assert rows["handoff_ho009_diagnostics"]["status"] == "MISSING"

    manifest = runtime.build_diagnostics_evidence_manifest(snapshot)
    manifest_rows = {item["key"]: item for item in manifest["analysis_workspace_pipeline"]}
    assert manifest_rows["calibration_static_trim"]["status"] == "READY"
    assert manifest_rows["uncertainty_uq"]["metrics"]["artifact_count"] == 4
    assert any(item["key"] == "handoff_ho009_diagnostics" for item in manifest["runtime_data_gaps"])


def test_v38_pipeline_marks_static_trim_missing_and_uq_available_not_run(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    rows = {row.key: row for row in runtime.analysis_workspace_pipeline_status(snapshot)}

    assert rows["calibration_static_trim"].status == "MISSING"
    assert rows["uncertainty_uq"].status == "AVAILABLE_NOT_RUN"
    gaps = {item["key"]: item for item in runtime.analysis_workspace_runtime_gaps(snapshot)}
    assert gaps["calibration_static_trim"]["status"] == "MISSING"
    assert gaps["uncertainty_uq"]["status"] == "AVAILABLE_NOT_RUN"


def test_latest_evidence_manifest_freshness_detects_stale_and_invalid(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path / "first")
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    first_snapshot = runtime.snapshot(selected_contract_path=contract_path)
    sidecar = runtime.write_diagnostics_evidence_manifest(first_snapshot)

    refreshed = runtime.snapshot(selected_contract_path=contract_path)
    assert refreshed.diagnostics_evidence_manifest_status == "READY"

    second_run_dir = _build_run_dir(tmp_path / "second")
    second_contract_path = _write_selected_run_contract(
        tmp_path / "selected_run_contract_second.json",
        second_run_dir,
    )
    second_snapshot = runtime.snapshot(selected_contract_path=second_contract_path)
    assert second_snapshot.diagnostics_evidence_manifest_path == sidecar
    assert second_snapshot.diagnostics_evidence_manifest_status == "STALE"

    _write_json(sidecar, {"run_dir": str(second_run_dir.resolve()), "evidence_manifest_hash": "bad"})
    invalid_snapshot = runtime.snapshot(selected_contract_path=second_contract_path)
    assert invalid_snapshot.diagnostics_evidence_manifest_status == "INVALID"


def test_selected_run_contract_loads_ho007_context_as_analysis_master_source(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(
        tmp_path / "workspace" / "handoffs" / "WS-OPTIMIZATION" / "selected_run_contract.json",
        run_dir,
    )

    snapshot = load_selected_run_contract(contract_path)

    assert snapshot.exists is True
    assert snapshot.status == "READY"
    assert snapshot.selected_run_context is not None
    assert snapshot.selected_run_context.run_id == "run-analysis-001"
    assert snapshot.selected_run_context.mode == "distributed_coordinator"
    assert snapshot.selected_run_context.results_artifact_index["run_dir"] == str(run_dir)
    assert snapshot.selected_run_contract_hash
    assert snapshot.blocking_states == ()


def test_runtime_exports_ho007_selected_run_contract_from_explicit_optimizer_run_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PNEUMO_WORKSPACE_DIR", raising=False)
    monkeypatch.delenv("PNEUMO_SELECTED_RUN_CONTRACT_PATH", raising=False)
    run_dir = _build_optimizer_ready_run_dir(tmp_path)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")

    result = runtime.export_selected_run_contract_from_run_dir(
        run_dir,
        now_text="2026-04-17T00:00:00Z",
    )

    contract_path = tmp_path / "pneumo_solver_ui" / "workspace" / "handoffs" / "WS-OPTIMIZATION" / "selected_run_contract.json"
    assert result.ok is True
    assert result.status == "FINISHED"
    assert result.returncode == 0
    assert result.command[0] == "export_selected_run_contract_from_run_dir"
    assert contract_path.exists()
    assert result.artifacts[0].key == "selected_run_contract_json"

    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "selected_run_contract_v1"
    assert payload["handoff_id"] == SELECTED_RUN_HANDOFF_ID
    assert payload["source_workspace"] == SELECTED_RUN_PRODUCED_BY
    assert payload["target_workspace"] == "WS-ANALYSIS"
    assert payload["selected_from"] == "desktop_engineering_analysis_center"
    assert payload["run_id"] == "run_ho007_bridge_ready"
    assert payload["mode"] == "distributed_coordinator"
    assert payload["status"] == "done"
    assert payload["objective_contract_hash"] == objective_contract_hash()
    assert payload["hard_gate_key"]
    assert payload["hard_gate_tolerance"] == 0.0
    assert payload["active_baseline_hash"] == "active-baseline-hash-bridge"
    assert payload["suite_snapshot_hash"] == "suite-snapshot-hash-bridge"
    results_csv_path = payload["results_artifact_index"]["results_csv_path"]
    assert results_csv_path.endswith("export\\trials.csv") or results_csv_path.endswith("export/trials.csv")
    assert payload["results_artifact_index"]["objective_contract_path"].endswith("objective_contract.json")
    assert payload["analysis_handoff_ready_state"] == "ready"
    assert payload["selected_run_contract_hash"]

    contract_snapshot = load_selected_run_contract(contract_path)
    assert contract_snapshot.status == "READY"
    assert contract_snapshot.selected_run_context is not None
    assert contract_snapshot.selected_run_context.run_id == "run_ho007_bridge_ready"
    assert contract_snapshot.blocking_states == ()


def test_runtime_discovers_ho007_bridge_candidates_with_preflight_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PNEUMO_WORKSPACE_DIR", raising=False)
    monkeypatch.delenv("PNEUMO_SELECTED_RUN_CONTRACT_PATH", raising=False)
    ready_run_dir = _build_optimizer_ready_run_dir(tmp_path)
    missing_run_dir = tmp_path / "pneumo_solver_ui" / "workspace" / "opt_runs" / "coord" / "p_ho007_missing"
    _write_text(missing_run_dir / "coordinator.log", "started but no completed artifacts\n")
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")

    rows = runtime.discover_selected_run_candidates(limit=10)

    by_dir = {Path(row["run_dir"]): row for row in rows}
    assert ready_run_dir.resolve() in by_dir
    assert missing_run_dir.resolve() in by_dir
    ready = by_dir[ready_run_dir.resolve()]
    missing = by_dir[missing_run_dir.resolve()]
    assert ready["bridge_status"] == "READY"
    assert ready["analysis_handoff_ready_state"] == "ready"
    assert ready["run_id"] == "run_ho007_bridge_ready"
    assert ready["selected_run_contract_hash"]
    assert missing["bridge_status"] == "MISSING_INPUTS"
    assert "results_csv_path" in missing["missing_inputs"]
    assert "blocking_state:missing results artifact" in missing["missing_inputs"]

    snapshot = runtime.snapshot(selected_contract_path=tmp_path / "missing" / "selected_run_contract.json")
    manifest = runtime.build_diagnostics_evidence_manifest(snapshot)
    readiness = manifest["selected_run_candidate_readiness"]
    assert readiness["candidate_count"] == 2
    assert readiness["ready_candidate_count"] == 1
    assert readiness["missing_inputs_candidate_count"] == 1
    assert str(ready_run_dir.resolve()) in readiness["ready_run_dirs"]
    assert "blocking_state:missing results artifact" in readiness["unique_missing_inputs"]


def test_runtime_refuses_ho007_export_when_optimizer_run_inputs_are_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PNEUMO_WORKSPACE_DIR", raising=False)
    monkeypatch.delenv("PNEUMO_SELECTED_RUN_CONTRACT_PATH", raising=False)
    run_dir = tmp_path / "pneumo_solver_ui" / "workspace" / "opt_runs" / "coord" / "p_ho007_missing"
    _write_text(run_dir / "coordinator.log", "started but no completed artifacts\n")
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")

    result = runtime.export_selected_run_contract_from_run_dir(run_dir)

    contract_path = tmp_path / "pneumo_solver_ui" / "workspace" / "handoffs" / "WS-OPTIMIZATION" / "selected_run_contract.json"
    assert result.ok is False
    assert result.status == "MISSING_INPUTS"
    assert "active_baseline_hash" in result.error
    assert "suite_snapshot_hash" in result.error
    assert "results_csv_path" in result.error
    assert "objective_contract_path" in result.error
    assert "blocking_state:run unknown" in result.error
    assert "blocking_state:missing results artifact" in result.error
    assert not contract_path.exists()


def test_missing_selected_contract_blocks_analysis_without_live_runtime(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=tmp_path / "missing" / "selected_run_contract.json")

    assert snapshot.status == "BLOCKED"
    assert snapshot.contract_status == "MISSING"
    assert snapshot.artifacts == ()
    assert "missing selected run contract" in snapshot.blocking_states
    assert snapshot.mismatch_summary["handoff_id"] == "HO-007"

    requirements = runtime.selected_run_handoff_requirements(snapshot)
    assert requirements["handoff_id"] == "HO-007"
    assert requirements["producer_workspace"] == "WS-OPTIMIZATION"
    assert requirements["consumer_workspace"] == "WS-ANALYSIS"
    assert requirements["contract_status"] == "MISSING"
    assert requirements["can_run_engineering_analysis"] is False
    assert "run_id" in requirements["missing_fields"]
    assert "results_artifact_index" in requirements["missing_fields"]
    assert requirements["required_contract_path"] == str((tmp_path / "missing" / "selected_run_contract.json").resolve())

    explicit_run_snapshot = runtime.snapshot(
        run_dir,
        selected_contract_path=tmp_path / "missing" / "selected_run_contract.json",
    )
    assert explicit_run_snapshot.status == "BLOCKED"
    assert explicit_run_snapshot.artifacts == ()


def test_incomplete_selected_contract_degrades_but_keeps_available_artifacts(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(
        tmp_path / "selected_run_contract.json",
        run_dir,
        suite_snapshot_hash=None,
        results_artifact_index={},
    )
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")

    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    assert snapshot.status == "DEGRADED"
    assert snapshot.contract_status == "DEGRADED"
    assert snapshot.artifact_by_key("system_influence_json") is not None
    assert set(snapshot.mismatch_summary["missing_fields"]) >= {
        "suite_snapshot_hash",
        "results_artifact_index",
    }


def test_analysis_compare_contract_blocks_objective_mismatch_before_charts() -> None:
    left = SelectedRunContext(
        run_id="left",
        mode="distributed_coordinator",
        status="done",
        run_dir="C:/runs/left",
        objective_contract_hash="objective-a",
        hard_gate_key="max_pressure_pa",
        hard_gate_tolerance=250000.0,
        active_baseline_hash="baseline-a",
        suite_snapshot_hash="suite-a",
        problem_hash="problem-a",
    )
    right_payload = left.to_payload()
    right_payload["run_id"] = "right"
    right_payload["objective_contract_hash"] = "objective-b"

    contract = build_analysis_compare_contract(
        left,
        right_payload,
        compare_mode="selected_vs_history_run",
        selected_metrics=["score"],
        unit_profile={"score": "dimensionless"},
    )

    assert contract["analysis_compare_ready_state"] == "blocked"
    assert "objective_contract_hash" in contract["blocking_states"]
    assert contract["results_source_kind"] == "selected_run_contract"
    assert contract["metric_units"]["score"] == "dimensionless"
    assert contract["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"


def test_analysis_compare_contract_requires_explicit_refs() -> None:
    contract = build_analysis_compare_contract(None, None)

    assert contract["analysis_compare_ready_state"] == "blocked"
    assert contract["blocking_states"] == ("missing explicit compare refs",)
    assert contract["mismatch_banner"]["scope"] == "missing_compare_contract"


def test_analysis_to_animator_link_blocks_without_explicit_artifact_pointer() -> None:
    context = SelectedRunContext(
        run_id="run-analysis-001",
        mode="distributed_coordinator",
        status="done",
        run_dir="C:/runs/run-analysis-001",
        objective_contract_hash="objective-hash-001",
        hard_gate_key="max_pressure_pa",
        hard_gate_tolerance=250000.0,
        active_baseline_hash="baseline-hash-001",
        suite_snapshot_hash="suite-hash-001",
        problem_hash="problem-hash-001",
        run_contract_hash="selected-run-contract-hash-001",
    )

    contract = build_analysis_to_animator_link_contract(
        context,
        selected_result_artifact_pointer=None,
        selected_best_candidate_ref="candidate-001",
    )

    assert contract["handoff_id"] == ANALYSIS_TO_ANIMATOR_HANDOFF_ID
    assert contract["producer_workspace"] == "WS-ANALYSIS"
    assert contract["consumer_workspace"] == "WS-ANIMATOR"
    assert contract["ready_state"] == "blocked"
    assert "missing selected result artifact pointer" in contract["blocking_states"]
    assert "missing selected_test_id" in contract["blocking_states"]
    assert contract["rules"][0].startswith("WS-ANIMATOR receives only explicit artifact pointers")


def test_runtime_exports_analysis_to_animator_context_from_selected_contract(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    pointer_path = run_dir / "compare_influence.json"
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    payload = runtime.export_analysis_to_animator_link_contract(
        snapshot,
        selected_result_artifact_pointer=pointer_path,
        selected_test_id="T01",
        selected_segment_id="segment-1",
        selected_time_window={"mode": "time_s", "start_s": 0.0, "end_s": 1.0},
        selected_best_candidate_ref="candidate-001",
        now_text="2026-04-17T00:00:00Z",
    )

    context_path = tmp_path / "pneumo_solver_ui" / "workspace" / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"
    link_path = tmp_path / "pneumo_solver_ui" / "workspace" / "handoffs" / "WS-ANALYSIS" / "animator_link_contract.json"
    assert context_path.exists()
    assert link_path.exists()

    link = json.loads(link_path.read_text(encoding="utf-8"))
    context = json.loads(context_path.read_text(encoding="utf-8"))
    assert payload["analysis_context_path"] == str(context_path.resolve())
    assert payload["animator_link_contract_path"] == str(link_path.resolve())
    assert link["schema"] == "analysis_to_animator_link_contract.v1"
    assert link["handoff_id"] == ANALYSIS_TO_ANIMATOR_HANDOFF_ID
    assert link["producer_workspace"] == "WS-ANALYSIS"
    assert link["consumer_workspace"] == "WS-ANIMATOR"
    assert link["run_id"] == "run-analysis-001"
    assert link["run_contract_hash"] == snapshot.selected_run_contract_hash
    assert link["selected_test_id"] == "T01"
    assert link["selected_segment_id"] == "segment-1"
    assert link["selected_time_window"]["start_s"] == 0.0
    assert link["selected_result_artifact_pointer"]["path"] == str(pointer_path.resolve())
    assert link["selected_result_artifact_pointer"]["exists"] is True
    assert link["selected_result_artifact_pointer"]["sha256"]
    assert link["objective_contract_hash"] == "objective-hash-001"
    assert link["suite_snapshot_hash"] == "suite-hash-001"
    assert link["problem_hash"] == "problem-hash-001"
    assert link["ready_state"] == "ready"
    assert link["animator_link_contract_hash"]

    assert context["schema"] == "analysis_context.v1"
    assert context["handoff_id"] == ANALYSIS_TO_ANIMATOR_HANDOFF_ID
    assert context["analysis_context_path"] == str(context_path.resolve())
    assert context["selected_run_contract_hash"] == snapshot.selected_run_contract_hash
    assert context["selected_run_context"]["run_id"] == "run-analysis-001"
    assert context["selected_result_artifact_pointer"]["sha256"] == link["selected_result_artifact_pointer"]["sha256"]
    assert context["animator_link_contract_hash"] == link["animator_link_contract_hash"]
    assert context["animator_link_contract"]["run_id"] == "run-analysis-001"
    assert context["diagnostics_bundle_finalized"] is False
    assert context["analysis_context_hash"]


def test_runtime_blocks_analysis_to_animator_export_for_missing_pointer(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    contract_path = _write_selected_run_contract(tmp_path / "selected_run_contract.json", run_dir)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="python")
    snapshot = runtime.snapshot(selected_contract_path=contract_path)

    with pytest.raises(RuntimeError, match="selected result artifact pointer"):
        runtime.export_analysis_to_animator_link_contract(
            snapshot,
            selected_result_artifact_pointer=run_dir / "missing.npz",
            selected_test_id="T01",
            selected_segment_id="segment-1",
            selected_best_candidate_ref="candidate-001",
        )

    assert not runtime.analysis_context_path().exists()
    assert not runtime.animator_link_contract_path().exists()


def test_runtime_system_influence_command_helper_is_subprocess_free_under_patch(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")
    captured: list[tuple[tuple[str, ...], Path]] = []

    def _fake_run(command, *, cwd):
        captured.append((tuple(command), Path(cwd)))
        return 0, "system influence ok", ""

    runtime._run_command = _fake_run  # type: ignore[method-assign]

    result = runtime.run_system_influence(
        run_dir,
        fit_ranges_json=run_dir / "fit_ranges.json",
        adaptive_eps=True,
        stage_name="stage1_long",
        max_params=17,
    )

    assert result.ok is True
    assert result.status == "FINISHED"
    assert result.returncode == 0
    command = captured[0][0]
    assert command[:3] == ("PYTHON", "-m", "pneumo_solver_ui.calibration.system_influence_report_v1")
    assert "--run_dir" in command
    assert str(run_dir.resolve()) in command
    assert "--adaptive_eps" in command
    assert command[command.index("--stage_name") + 1] == "stage1_long"
    assert command[command.index("--max_params") + 1] == "17"
    assert captured[0][1] == tmp_path.resolve()


def test_runtime_full_report_command_helper_builds_report_argv(tmp_path: Path) -> None:
    run_dir = _build_run_dir(tmp_path)
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")
    captured: list[tuple[str, ...]] = []

    def _fake_run(command, *, cwd):
        captured.append(tuple(command))
        return 0, "full report ok", ""

    runtime._run_command = _fake_run  # type: ignore[method-assign]

    result = runtime.run_full_report(run_dir, max_plots=5)

    assert result.ok is True
    command = captured[0]
    assert command[:3] == ("PYTHON", "-m", "pneumo_solver_ui.calibration.report_full_from_run_v1")
    assert command[command.index("--run_dir") + 1] == str(run_dir.resolve())
    assert command[command.index("--max_plots") + 1] == "5"


def test_runtime_param_staging_reports_missing_inputs_without_subprocess(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN_missing_staging"
    run_dir.mkdir()
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")

    result = runtime.run_param_staging(run_dir)

    assert result.ok is False
    assert result.status == "MISSING_INPUTS"
    assert result.returncode is None
    assert "fit_ranges_json" in result.error
    assert "system_influence_json" in result.error


def test_runtime_param_staging_command_helper_requires_fit_ranges_and_influence(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN_staging"
    _write_json(run_dir / "system_influence.json", _build_system_influence_payload())
    _write_json(run_dir / "fit_ranges_final.json", {"база": [2.0, 4.0]})
    runtime = DesktopEngineeringAnalysisRuntime(repo_root=tmp_path, python_executable="PYTHON")
    captured: list[tuple[str, ...]] = []

    def _fake_run(command, *, cwd):
        captured.append(tuple(command))
        return 0, "staging ok", ""

    runtime._run_command = _fake_run  # type: ignore[method-assign]

    result = runtime.run_param_staging(run_dir)

    assert result.ok is True
    command = captured[0]
    assert command[:3] == ("PYTHON", "-m", "pneumo_solver_ui.calibration.param_staging_v3_influence")
    assert command[command.index("--fit_ranges_json") + 1] == str((run_dir / "fit_ranges_final.json").resolve())
    assert command[command.index("--system_influence_json") + 1] == str((run_dir / "system_influence.json").resolve())
    assert command[command.index("--out_dir") + 1] == str(run_dir.resolve())


def test_desktop_engineering_analysis_center_shell_is_materialized() -> None:
    from pneumo_solver_ui.tools.desktop_engineering_analysis_center import (
        ANALYSIS_COMMAND_OPEN_TARGETS,
        DesktopEngineeringAnalysisCenter,
        format_contract_banner,
        format_selected_run_summary,
    )

    assert DesktopEngineeringAnalysisCenter.__name__ == "DesktopEngineeringAnalysisCenter"
    assert callable(format_contract_banner)
    assert callable(format_selected_run_summary)
    assert hasattr(DesktopEngineeringAnalysisCenter, "_export_animator_link")
    assert hasattr(DesktopEngineeringAnalysisCenter, "_run_command_surface_action")
    command_labels = {label for _key, label in ANALYSIS_COMMAND_OPEN_TARGETS}
    assert "Открыть HO-007 selected_run_contract.json" in command_labels
    assert "Открыть selected run_dir" in command_labels
    assert "Открыть selected artifact" in command_labels
    assert "Открыть HO-009 evidence manifest" in command_labels
    assert "Открыть HO-008 analysis_context.json" in command_labels
    assert "Открыть HO-008 animator_link_contract.json" in command_labels
