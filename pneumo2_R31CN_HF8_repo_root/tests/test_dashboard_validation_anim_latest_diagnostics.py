from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.tools.dashboard_report import generate_dashboard_report
from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle



def _make_anim_diag(token: str, reload_inputs: list[str], *, updated_utc: str = "2026-03-11T12:00:00+00:00") -> dict:
    deps = {
        "version": 1,
        "context": "anim_latest export pointer",
        "npz": {"path": "/abs/workspace/exports/anim_latest.npz", "exists": True, "size": 123},
        "road_csv_ref": "anim_latest_road_csv.csv",
        "road_csv_path": "/abs/workspace/exports/anim_latest_road_csv.csv",
        "road_csv": {"path": "/abs/workspace/exports/anim_latest_road_csv.csv", "exists": True, "size": 77},
    }
    return {
        "anim_latest_available": True,
        "anim_latest_global_pointer_json": "/abs/workspace/_pointers/anim_latest.json",
        "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
        "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
        "anim_latest_visual_cache_token": token,
        "anim_latest_visual_reload_inputs": list(reload_inputs),
        "anim_latest_visual_cache_dependencies": deps,
        "anim_latest_updated_utc": updated_utc,
        "anim_latest_meta": {
            "road_csv": "anim_latest_road_csv.csv",
            "scenario_kind": "ring",
            "ring_closure_policy": "strict_exact",
            "ring_closure_applied": False,
            "ring_seam_open": True,
            "ring_seam_max_jump_m": 0.012,
            "ring_raw_seam_max_jump_m": 0.015,
        },
        "browser_perf_status": "snapshot_only",
        "browser_perf_level": "WARN",
        "browser_perf_registry_snapshot_ref": "browser_perf_registry_snapshot.json",
        "browser_perf_registry_snapshot_path": "/abs/workspace/exports/browser_perf_registry_snapshot.json",
        "browser_perf_registry_snapshot_exists": True,
        "browser_perf_contract_ref": "browser_perf_contract.json",
        "browser_perf_contract_path": "/abs/workspace/exports/browser_perf_contract.json",
        "browser_perf_contract_exists": True,
        "browser_perf_evidence_report_ref": "browser_perf_evidence_report.json",
        "browser_perf_evidence_report_path": "/abs/workspace/exports/browser_perf_evidence_report.json",
        "browser_perf_evidence_report_exists": True,
        "browser_perf_comparison_report_ref": "browser_perf_comparison_report.json",
        "browser_perf_comparison_report_path": "/abs/workspace/exports/browser_perf_comparison_report.json",
        "browser_perf_comparison_report_exists": True,
        "browser_perf_trace_ref": "browser_perf_trace.json",
        "browser_perf_trace_path": "/abs/workspace/exports/browser_perf_trace.json",
        "browser_perf_trace_exists": False,
        "browser_perf_evidence_status": "snapshot_only",
        "browser_perf_evidence_level": "WARN",
        "browser_perf_bundle_ready": False,
        "browser_perf_snapshot_contract_match": True,
        "browser_perf_comparison_status": "no_reference",
        "browser_perf_comparison_level": "WARN",
        "browser_perf_comparison_ready": False,
        "browser_perf_comparison_changed": None,
        "browser_perf_comparison_delta_total_wakeups": 0,
        "browser_perf_comparison_delta_total_duplicate_guard_hits": 0,
        "browser_perf_comparison_delta_total_render_count": 0,
        "browser_perf_comparison_delta_max_idle_poll_ms": 0,
        "browser_perf_component_count": 2,
        "browser_perf_total_wakeups": 10,
        "browser_perf_total_duplicate_guard_hits": 3,
        "browser_perf_max_idle_poll_ms": 60000,
    }



def _make_local_pointer(token: str, reload_inputs: list[str], *, updated_utc: str = "2026-03-11T12:00:00+00:00") -> dict:
    return {
        "schema_version": "anim_latest_pointer_v1",
        "updated_utc": updated_utc,
        "npz_path": "/abs/workspace/exports/anim_latest.npz",
        "meta": {"road_csv": "anim_latest_road_csv.csv"},
        "visual_cache_token": token,
        "visual_reload_inputs": list(reload_inputs),
        "visual_cache_dependencies": {
            "version": 1,
            "context": "anim_latest export pointer",
            "npz": {"path": "/abs/workspace/exports/anim_latest.npz", "exists": True, "size": 123},
            "road_csv_ref": "anim_latest_road_csv.csv",
            "road_csv_path": "/abs/workspace/exports/anim_latest_road_csv.csv",
            "road_csv": {"path": "/abs/workspace/exports/anim_latest_road_csv.csv", "exists": True, "size": 77},
        },
    }



def _make_global_pointer(token: str, reload_inputs: list[str], *, updated_utc: str = "2026-03-11T12:00:00+00:00") -> dict:
    return {
        "kind": "anim_latest",
        "updated_at": updated_utc,
        "pointer_json": "/abs/workspace/exports/anim_latest.json",
        "npz_path": "/abs/workspace/exports/anim_latest.npz",
        "meta": {"road_csv": "anim_latest_road_csv.csv"},
        "schema_version": "anim_latest_pointer_v1",
        "updated_utc": updated_utc,
        "visual_cache_token": token,
        "visual_reload_inputs": list(reload_inputs),
        "visual_cache_dependencies": {
            "version": 1,
            "context": "anim_latest export pointer",
            "npz": {"path": "/abs/workspace/exports/anim_latest.npz", "exists": True, "size": 123},
            "road_csv_ref": "anim_latest_road_csv.csv",
            "road_csv_path": "/abs/workspace/exports/anim_latest_road_csv.csv",
            "road_csv": {"path": "/abs/workspace/exports/anim_latest_road_csv.csv", "exists": True, "size": 77},
        },
    }



def _write_minimal_send_bundle(
    tmp_path: Path,
    *,
    global_token: str = "tok-123",
    local_token: str = "tok-123",
    diag_token: str = "tok-123",
    include_browser_perf_files: bool = True,
    triage_scope: dict | None = None,
    export_scopes: list[tuple[str, dict]] | None = None,
) -> Path:
    zip_path = tmp_path / "bundle.zip"
    diag = _make_anim_diag(diag_token, ["npz", "road_csv"])
    local_ptr = _make_local_pointer(local_token, ["npz", "road_csv"])
    global_ptr = _make_global_pointer(global_token, ["npz", "road_csv"])
    triage_report = {
        "created_at": "2026-03-11T12:00:00",
        "release": "pytest",
        "severity_counts": {"critical": 0},
        "red_flags": [],
    }
    if triage_scope:
        triage_report["dist_progress"] = dict(triage_scope)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))

        zf.writestr("triage/triage_report.md", "# triage\n")
        zf.writestr("triage/triage_report.json", json.dumps(triage_report, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps(diag, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.md", "# Anim latest diagnostics\n\n- token: tok-123\n")

        zf.writestr("workspace/_pointers/anim_latest.json", json.dumps(global_ptr, ensure_ascii=False, indent=2))
        zf.writestr("workspace/exports/anim_latest.json", json.dumps(local_ptr, ensure_ascii=False, indent=2))
        zf.writestr("workspace/exports/anim_latest.npz", b"npz bytes")
        zf.writestr("workspace/exports/anim_latest_road_csv.csv", "t,z0,z1,z2,z3\n0,0,0,0,0\n")
        if include_browser_perf_files:
            zf.writestr("workspace/exports/browser_perf_registry_snapshot.json", json.dumps({"schema": "browser_perf_registry_snapshot_v1"}, ensure_ascii=False, indent=2))
            zf.writestr("workspace/exports/browser_perf_contract.json", json.dumps({"schema": "browser_perf_contract_v1"}, ensure_ascii=False, indent=2))
            zf.writestr("workspace/exports/browser_perf_evidence_report.json", json.dumps({"schema": "browser_perf_evidence_report_v1"}, ensure_ascii=False, indent=2))
            zf.writestr("workspace/exports/browser_perf_comparison_report.json", json.dumps({"schema": "browser_perf_comparison_report_v1"}, ensure_ascii=False, indent=2))
        zf.writestr("workspace/uploads/placeholder.txt", "u")
        zf.writestr("workspace/road_profiles/placeholder.txt", "r")
        zf.writestr("workspace/maneuvers/placeholder.txt", "m")
        zf.writestr("workspace/opt_runs/placeholder.txt", "o")
        zf.writestr("workspace/ui_state/state.json", json.dumps({"ok": True}, ensure_ascii=False))
        zf.writestr("ui_logs/app.log", "ok\n")
        for run_name, run_scope in list(export_scopes or []):
            zf.writestr(
                f"dist_runs/{run_name}/export/run_scope.json",
                json.dumps(run_scope, ensure_ascii=False, indent=2),
            )
    return zip_path



def test_validate_send_bundle_exposes_anim_latest_diagnostics_and_dashboard_renders_them(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path)

    res = validate_send_bundle(zip_path)
    anim = dict(res.report_json.get("anim_latest") or {})

    assert res.ok is True
    assert anim["available"] is True
    assert anim["visual_cache_token"] == "tok-123"
    assert anim["visual_reload_inputs"] == ["npz", "road_csv"]
    assert anim["pointer_sync_ok"] is True
    assert anim["reload_inputs_sync_ok"] is True
    assert anim["npz_path_sync_ok"] is True
    assert anim["browser_perf_status"] == "snapshot_only"
    assert anim["browser_perf_level"] == "WARN"
    assert anim["browser_perf_registry_snapshot_ref"] == "browser_perf_registry_snapshot.json"
    assert anim["browser_perf_registry_snapshot_exists"] is True
    assert anim["browser_perf_registry_snapshot_in_bundle"] is True
    assert anim["browser_perf_contract_ref"] == "browser_perf_contract.json"
    assert anim["browser_perf_contract_exists"] is True
    assert anim["browser_perf_contract_in_bundle"] is True
    assert anim["browser_perf_evidence_status"] == "snapshot_only"
    assert anim["browser_perf_evidence_level"] == "WARN"
    assert anim["browser_perf_evidence_report_ref"] == "browser_perf_evidence_report.json"
    assert anim["browser_perf_evidence_report_exists"] is True
    assert anim["browser_perf_evidence_report_in_bundle"] is True
    assert anim["browser_perf_bundle_ready"] is False
    assert anim["browser_perf_snapshot_contract_match"] is True
    assert anim["browser_perf_comparison_status"] == "no_reference"
    assert anim["browser_perf_comparison_level"] == "WARN"
    assert anim["browser_perf_comparison_report_ref"] == "browser_perf_comparison_report.json"
    assert anim["browser_perf_comparison_report_exists"] is True
    assert anim["browser_perf_comparison_report_in_bundle"] is True
    assert anim["browser_perf_comparison_ready"] is False
    assert anim["browser_perf_comparison_changed"] is None
    assert anim["browser_perf_comparison_delta_total_wakeups"] == 0
    assert anim["browser_perf_comparison_delta_total_duplicate_guard_hits"] == 0
    assert anim["browser_perf_comparison_delta_total_render_count"] == 0
    assert anim["browser_perf_comparison_delta_max_idle_poll_ms"] == 0
    assert anim["browser_perf_trace_ref"] == "browser_perf_trace.json"
    assert anim["browser_perf_trace_exists"] is False
    assert anim["browser_perf_trace_in_bundle"] is False
    assert anim["scenario_kind"] == "ring"
    assert anim["ring_closure_policy"] == "strict_exact"
    assert anim["ring_closure_applied"] is False
    assert anim["ring_seam_open"] is True
    assert anim["ring_seam_max_jump_m"] == 0.012
    assert anim["ring_raw_seam_max_jump_m"] == 0.015
    assert anim["diagnostics_json_present"] is True
    assert anim["local_pointer_present"] is True
    assert anim["global_pointer_present"] is True
    assert "tok-123" in res.report_md
    assert "workspace/_pointers/anim_latest.json" in res.report_md
    assert "browser_perf_evidence_status" in res.report_md
    assert "browser_perf_comparison_status" in res.report_md
    assert "browser_perf_registry_snapshot.json" in res.report_md
    assert "browser_perf_evidence_report.json" in res.report_md
    assert "browser_perf_comparison_report.json" in res.report_md
    with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("validation/validation_report.json", json.dumps(res.report_json, ensure_ascii=False, indent=2))

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest_triage_report.md").write_text("# triage\n", encoding="utf-8")
    (out_dir / "latest_triage_report.json").write_text(json.dumps({"ok": True}, ensure_ascii=False, indent=2), encoding="utf-8")

    html, rep = generate_dashboard_report(repo_root, out_dir, zip_path=zip_path)
    dash_anim = dict(rep.get("anim_latest") or {})

    assert dash_anim["visual_cache_token"] == "tok-123"
    assert dash_anim["visual_reload_inputs"] == ["npz", "road_csv"]
    assert dash_anim["browser_perf_evidence_status"] == "snapshot_only"
    assert dash_anim["browser_perf_bundle_ready"] is False
    assert dash_anim["browser_perf_comparison_status"] == "no_reference"
    assert dash_anim["browser_perf_comparison_ready"] is False
    assert dash_anim["browser_perf_registry_snapshot_in_bundle"] is True
    assert dash_anim["browser_perf_contract_in_bundle"] is True
    assert dash_anim["browser_perf_evidence_report_in_bundle"] is True
    assert dash_anim["browser_perf_comparison_report_in_bundle"] is True
    assert dash_anim["browser_perf_trace_in_bundle"] is False
    assert dash_anim["scenario_kind"] == "ring"
    assert dash_anim["ring_closure_policy"] == "strict_exact"
    assert dash_anim["ring_closure_applied"] is False
    assert dash_anim["ring_seam_open"] is True
    assert dash_anim["ring_seam_max_jump_m"] == 0.012
    assert dash_anim["ring_raw_seam_max_jump_m"] == 0.015
    assert rep["sections"]["anim_latest"]["json_zip_path"] == "triage/latest_anim_pointer_diagnostics.json"
    assert "Anim latest diagnostics" in html
    assert "tok-123" in html
    assert "ring_closure" in html
    assert "strict_exact" in html
    assert "seam_open=True" in html
    assert "browser_perf.evidence" in html
    assert "snapshot_only / WARN" in html
    assert "browser_perf.comparison" in html
    assert "no_reference / WARN" in html
    assert "browser_perf_artifacts_primary" in html



def test_validate_send_bundle_warns_when_browser_perf_reports_are_missing_from_bundle(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path, include_browser_perf_files=False)

    res = validate_send_bundle(zip_path)
    anim = dict(res.report_json.get("anim_latest") or {})
    warnings = [str(x) for x in (res.report_json.get("warnings") or [])]

    assert res.ok is True
    assert anim["browser_perf_registry_snapshot_in_bundle"] is False
    assert anim["browser_perf_contract_in_bundle"] is False
    assert anim["browser_perf_evidence_report_in_bundle"] is False
    assert anim["browser_perf_comparison_report_in_bundle"] is False
    assert any("browser_perf_registry_snapshot" in msg and "missing in bundle" in msg for msg in warnings)
    assert any("browser_perf_evidence_report" in msg and "missing in bundle" in msg for msg in warnings)
    assert any("browser_perf_comparison_report" in msg and "missing in bundle" in msg for msg in warnings)


def test_validate_send_bundle_warns_on_anim_latest_token_mismatch(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path, global_token="tok-global", local_token="tok-local", diag_token="tok-sidecar")

    res = validate_send_bundle(zip_path)
    anim = dict(res.report_json.get("anim_latest") or {})
    warnings = [str(x) for x in (res.report_json.get("warnings") or [])]

    assert res.ok is True
    assert anim["available"] is True
    assert anim["visual_cache_token"] == "tok-sidecar"
    assert anim["pointer_sync_ok"] is False
    assert any("visual_cache_token mismatch" in w for w in warnings)
    assert anim["sources"]["global_pointer"]["visual_cache_token"] == "tok-global"
    assert anim["sources"]["local_pointer"]["visual_cache_token"] == "tok-local"
    assert anim["sources"]["diagnostics"]["visual_cache_token"] == "tok-sidecar"


def test_validate_and_dashboard_surface_optimizer_scope_mismatch_between_triage_and_export(tmp_path: Path) -> None:
    triage_scope = {
        "status": "running",
        "completed": 7,
        "in_flight": 2,
        "cached_hits": 1,
        "duplicates_skipped": 0,
        "problem_hash": "ph_triage_scope_1234567890",
        "problem_hash_short": "ph_triage_sc",
        "problem_hash_mode": "stable",
    }
    export_scope = {
        "schema": "expdb_run_scope_v1",
        "run_id": "dist-run-001",
        "problem_hash": "ph_export_scope_9999999999",
        "problem_hash_short": "ph_export_sc",
        "problem_hash_mode": "legacy",
        "objective_keys": ["comfort", "energy"],
        "penalty_key": "violations",
    }
    zip_path = _write_minimal_send_bundle(
        tmp_path,
        triage_scope=triage_scope,
        export_scopes=[("DIST_SCOPE_A", export_scope)],
    )

    res = validate_send_bundle(zip_path)
    optimizer_scope = dict(res.report_json.get("optimizer_scope") or {})
    optimizer_scope_gate = dict(res.report_json.get("optimizer_scope_gate") or {})
    warnings = [str(x) for x in (res.report_json.get("warnings") or [])]
    release_risks = [str(x) for x in (res.report_json.get("release_risks") or [])]

    assert optimizer_scope["problem_hash"] == "ph_triage_scope_1234567890"
    assert optimizer_scope["problem_hash_mode"] == "stable"
    assert optimizer_scope["scope_sync_ok"] is False
    assert optimizer_scope_gate["release_gate"] == "FAIL"
    assert optimizer_scope_gate["release_risk"] is True
    assert "triage" in optimizer_scope["sources"]
    assert "export:DIST_SCOPE_A" in optimizer_scope["sources"]
    assert any("optimizer scope problem_hash mismatch" in msg for msg in warnings)
    assert any("optimizer scope problem_hash_mode mismatch" in msg for msg in warnings)
    assert any("optimizer scope release risk" in msg for msg in warnings)
    assert any("optimizer scope release risk" in msg for msg in release_risks)
    assert "## Optimizer scope" in res.report_md
    assert "release_gate: `FAIL`" in res.report_md
    assert "release_risk: `True`" in res.report_md
    assert "scope_sync_ok" in res.report_md
    assert "export:DIST_SCOPE_A" in res.report_md

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest_triage_report.md").write_text("# triage\n", encoding="utf-8")
    (out_dir / "latest_triage_report.json").write_text(
        json.dumps(
            {
                "created_at": "2026-03-11T12:00:00",
                "release": "pytest",
                "severity_counts": {"critical": 0},
                "red_flags": [],
                "dist_progress": triage_scope,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    html, rep = generate_dashboard_report(repo_root, out_dir, zip_path=zip_path)
    dash_scope = dict(rep.get("optimizer_scope") or {})
    dash_gate = dict(rep.get("optimizer_scope_gate") or {})

    assert dash_scope["problem_hash"] == "ph_triage_scope_1234567890"
    assert dash_scope["problem_hash_mode"] == "stable"
    assert dash_scope["scope_sync_ok"] is False
    assert dash_gate["release_gate"] == "FAIL"
    assert dash_gate["release_risk"] is True
    assert any("optimizer scope problem_hash mismatch" in msg for msg in rep.get("warnings") or [])
    assert any("optimizer scope release risk" in msg for msg in rep.get("warnings") or [])
    assert "optimizer.problem_hash" in html
    assert "optimizer.gate" in html
    assert "optimizer.hash_mode" in html
    assert "optimizer.scope_sync" in html
    assert "ph_triage_sc" in html
    assert "stable" in html
    assert "FAIL" in html


def test_sources_wire_optimizer_scope_compare_in_validation_and_dashboard() -> None:
    root = Path(__file__).resolve().parents[1]
    validate_text = (root / "pneumo_solver_ui" / "tools" / "validate_send_bundle.py").read_text(encoding="utf-8")
    dashboard_text = (root / "pneumo_solver_ui" / "tools" / "dashboard_report.py").read_text(encoding="utf-8")
    helper_text = (root / "pneumo_solver_ui" / "optimization_scope_compare.py").read_text(encoding="utf-8")

    assert 'rep["optimizer_scope"]' in validate_text
    assert "## Optimizer scope" in validate_text
    assert "optimizer.problem_hash" in dashboard_text
    assert "optimizer.gate" in dashboard_text
    assert "optimizer.scope_sync" in dashboard_text
    assert 'rep["optimizer_scope_gate"]' in dashboard_text
    assert 'rep["optimizer_scope"]' in dashboard_text
    assert "compare_optimizer_scope_sources" in helper_text
    assert "evaluate_optimizer_scope_gate" in helper_text
    assert "release_risk" in helper_text
    assert "optimizer scope " in helper_text
    assert " mismatch between sources" in helper_text
