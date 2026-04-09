from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.tools.health_report import build_health_report, add_health_report_to_zip
from pneumo_solver_ui.tools.inspect_send_bundle import inspect_send_bundle, render_inspection_md


ROOT = Path(__file__).resolve().parents[1]


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
        "anim_latest_meta": {"road_csv": "anim_latest_road_csv.csv"},
        "browser_perf_status": "snapshot_only",
        "browser_perf_level": "WARN",
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
        "browser_perf_component_count": 2,
        "browser_perf_total_wakeups": 10,
        "browser_perf_total_duplicate_guard_hits": 3,
        "browser_perf_max_idle_poll_ms": 60000,
        "anim_latest_mnemo_event_log_ref": "anim_latest.desktop_mnemo_events.json",
        "anim_latest_mnemo_event_log_path": "/abs/workspace/exports/anim_latest.desktop_mnemo_events.json",
        "anim_latest_mnemo_event_log_exists": True,
        "anim_latest_mnemo_event_log_schema_version": "desktop_mnemo_event_log_v1",
        "anim_latest_mnemo_event_log_updated_utc": updated_utc,
        "anim_latest_mnemo_event_log_current_mode": "Регуляторный коридор",
        "anim_latest_mnemo_event_log_event_count": 4,
        "anim_latest_mnemo_event_log_active_latch_count": 1,
        "anim_latest_mnemo_event_log_acknowledged_latch_count": 2,
        "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений", "Смена режима"],
    }



def _make_validation_report(token: str, reload_inputs: list[str], *, pointer_sync_ok: bool, warnings: list[str] | None = None) -> dict:
    return {
        "schema": "send_bundle_validation",
        "schema_version": "1.0.0",
        "release": "pytest",
        "checked_at": "2026-03-11T12:00:00",
        "zip_path": "/abs/bundle.zip",
        "ok": True,
        "errors": [],
        "warnings": list(warnings or []),
        "stats": {},
        "anim_latest": {
            "available": True,
            "visual_cache_token": token,
            "visual_reload_inputs": list(reload_inputs),
            "pointer_json": "/abs/workspace/exports/anim_latest.json",
            "global_pointer_json": "/abs/workspace/_pointers/anim_latest.json",
            "npz_path": "/abs/workspace/exports/anim_latest.npz",
            "updated_utc": "2026-03-11T12:00:00+00:00",
            "pointer_sync_ok": pointer_sync_ok,
            "reload_inputs_sync_ok": True,
            "npz_path_sync_ok": True,
            "browser_perf_status": "snapshot_only",
            "browser_perf_level": "WARN",
            "browser_perf_registry_snapshot_ref": "browser_perf_registry_snapshot.json",
            "browser_perf_registry_snapshot_exists": False,
            "browser_perf_registry_snapshot_in_bundle": False,
            "browser_perf_previous_snapshot_ref": "browser_perf_previous_snapshot.json",
            "browser_perf_previous_snapshot_exists": False,
            "browser_perf_previous_snapshot_in_bundle": False,
            "browser_perf_contract_ref": "browser_perf_contract.json",
            "browser_perf_contract_exists": False,
            "browser_perf_contract_in_bundle": False,
            "browser_perf_evidence_report_ref": "browser_perf_evidence_report.json",
            "browser_perf_evidence_report_exists": False,
            "browser_perf_evidence_report_in_bundle": False,
            "browser_perf_comparison_report_ref": "browser_perf_comparison_report.json",
            "browser_perf_comparison_report_exists": False,
            "browser_perf_comparison_report_in_bundle": False,
            "browser_perf_trace_ref": "browser_perf_trace.json",
            "browser_perf_trace_exists": False,
            "browser_perf_trace_in_bundle": False,
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
            "issues": [
                "anim_latest visual_cache_token mismatch between sources: diagnostics=tok-sidecar, global_pointer=tok-global"
            ] if not pointer_sync_ok else [],
            "sources": {
                "diagnostics": {"visual_cache_token": "tok-sidecar"},
                "global_pointer": {"visual_cache_token": token},
            },
        },
    }



def _write_minimal_send_bundle(tmp_path: Path, *, validation_token: str = "tok-sidecar", diag_token: str = "tok-sidecar") -> Path:
    zip_path = tmp_path / "bundle.zip"
    diag = _make_anim_diag(diag_token, ["npz", "road_csv"])
    validation = _make_validation_report(
        validation_token,
        ["npz", "road_csv"],
        pointer_sync_ok=(validation_token == diag_token),
        warnings=[] if validation_token == diag_token else [
            f"anim_latest visual_cache_token mismatch between sources: diagnostics={diag_token}, global_pointer={validation_token}"
        ],
    )
    dashboard = {
        "schema": "dashboard_report",
        "schema_version": "1.0.0",
        "release": "pytest",
        "anim_latest": {
            "available": True,
            "visual_cache_token": diag_token,
            "visual_reload_inputs": ["npz", "road_csv"],
            "npz_path": "/abs/workspace/exports/anim_latest.npz",
            "updated_utc": "2026-03-11T12:00:00+00:00",
        },
        "sections": {"anim_latest": {"json_zip_path": "triage/latest_anim_pointer_diagnostics.json"}},
        "warnings": [],
        "errors": [],
    }
    triage = {
        "created_at": "2026-03-11T12:00:00",
        "release": "pytest",
        "severity_counts": {"critical": 0},
        "red_flags": [],
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest", "created_at": "2026-03-11T12:00:00"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("validation/validation_report.json", json.dumps(validation, ensure_ascii=False, indent=2))
        zf.writestr("dashboard/dashboard.json", json.dumps(dashboard, ensure_ascii=False, indent=2))
        zf.writestr("triage/triage_report.json", json.dumps(triage, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps(diag, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.md", "# Anim latest diagnostics\n")
    return zip_path



def test_build_health_report_exposes_anim_latest_diagnostics_and_embeds_into_zip(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path)

    json_path, md_path = build_health_report(zip_path, out_dir=tmp_path)
    assert json_path is not None and json_path.exists()
    assert md_path is not None and md_path.exists()

    rep = json.loads(json_path.read_text(encoding="utf-8"))
    anim = dict(rep.get("signals", {}).get("anim_latest") or {})
    mnemo = dict(rep.get("signals", {}).get("mnemo_event_log") or {})
    artifacts = dict(rep.get("signals", {}).get("artifacts") or {})

    assert rep["schema"] == "health_report"
    assert anim["available"] is True
    assert anim["visual_cache_token"] == "tok-sidecar"
    assert anim["visual_reload_inputs"] == ["npz", "road_csv"]
    assert mnemo["severity"] == "critical"
    assert mnemo["current_mode"] == "Регуляторный коридор"
    assert anim["browser_perf_evidence_status"] == "snapshot_only"
    assert anim["browser_perf_bundle_ready"] is False
    assert anim["browser_perf_comparison_status"] == "no_reference"
    assert anim["browser_perf_comparison_ready"] is False
    assert artifacts["health_report_embedded"] is False
    assert artifacts["browser_perf_registry_snapshot"] is False
    assert artifacts["browser_perf_previous_snapshot"] is False
    assert artifacts["browser_perf_contract"] is False
    assert artifacts["browser_perf_evidence_report"] is False
    assert artifacts["browser_perf_comparison_report"] is False
    assert artifacts["browser_perf_trace"] is False
    assert "visual_cache_token" in md_path.read_text(encoding="utf-8")
    assert "tok-sidecar" in md_path.read_text(encoding="utf-8")
    assert "## Desktop Mnemo events" in md_path.read_text(encoding="utf-8")
    assert "Большой перепад давлений" in md_path.read_text(encoding="utf-8")
    assert "browser_perf_evidence_status" in md_path.read_text(encoding="utf-8")
    assert "browser_perf_comparison_status" in md_path.read_text(encoding="utf-8")
    assert "browser_perf_evidence_report: False" in md_path.read_text(encoding="utf-8")

    add_health_report_to_zip(zip_path, json_path, md_path)
    summary = inspect_send_bundle(zip_path)

    assert summary["has_embedded_health_report"] is True
    assert summary["has_browser_perf_registry_snapshot"] is False
    assert summary["has_browser_perf_previous_snapshot"] is False
    assert summary["has_browser_perf_contract"] is False
    assert summary["has_browser_perf_evidence_report"] is False
    assert summary["has_browser_perf_comparison_report"] is False
    assert summary["has_browser_perf_trace"] is False
    assert summary["anim_latest"]["visual_cache_token"] == "tok-sidecar"
    assert summary["mnemo_event_log"]["severity"] == "critical"
    assert summary["anim_latest"]["visual_reload_inputs"] == ["npz", "road_csv"]
    assert summary["anim_latest"]["browser_perf_evidence_status"] == "snapshot_only"
    assert summary["anim_latest"]["browser_perf_comparison_status"] == "no_reference"
    assert summary["anim_latest"]["browser_perf_registry_snapshot_ref"] == "browser_perf_registry_snapshot.json"
    assert summary["anim_latest"]["browser_perf_registry_snapshot_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_contract_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_evidence_report_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_comparison_report_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_trace_in_bundle"] is False
    inspect_md = render_inspection_md(summary)
    assert "tok-sidecar" in inspect_md
    assert "## Desktop Mnemo events" in inspect_md
    assert "Регуляторный коридор" in inspect_md
    assert "browser_perf_evidence_status" in inspect_md
    assert "browser_perf_comparison_status" in inspect_md
    assert "Browser perf evidence report: False" in inspect_md
    assert "Browser perf trace: False" in inspect_md
    assert "browser_perf_artifacts_primary" in inspect_md
    assert "browser_perf_artifacts_secondary" in inspect_md
    assert "browser_perf_registry_snapshot.json" in inspect_md



def test_health_report_surfaces_anim_latest_mismatch_from_validation(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path, validation_token="tok-global", diag_token="tok-sidecar")

    json_path, _md_path = build_health_report(zip_path, out_dir=tmp_path)
    rep = json.loads(Path(json_path).read_text(encoding="utf-8"))
    anim = dict(rep.get("signals", {}).get("anim_latest") or {})
    notes = [str(x) for x in (rep.get("notes") or [])]

    assert anim["visual_cache_token"] == "tok-global"
    assert anim["pointer_sync_ok"] is False
    assert anim["browser_perf_evidence_status"] == "snapshot_only"
    assert anim["browser_perf_comparison_status"] == "no_reference"
    assert any("visual_cache_token mismatch" in msg for msg in anim.get("issues") or [])
    assert any("visual_cache_token mismatch" in msg for msg in notes)
    assert any("Desktop Mnemo reports 1 active latched event(s)" in msg for msg in notes)
    assert any("browser perf evidence is not trace_bundle_ready" in msg for msg in notes)
    assert any("browser perf comparison status: no_reference" in msg for msg in notes)



def test_sources_wire_health_report_and_offline_inspector_into_send_bundle_flow() -> None:
    bundle_text = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    health_text = (ROOT / "pneumo_solver_ui" / "tools" / "health_report.py").read_text(encoding="utf-8")
    inspect_text = (ROOT / "pneumo_solver_ui" / "tools" / "inspect_send_bundle.py").read_text(encoding="utf-8")

    assert 'build_health_report(zip_path, out_dir=out_dir)' in bundle_text
    assert 'add_health_report_to_zip(zip_path, _health_json, _health_md)' in bundle_text
    assert 'health/health_report.json' in bundle_text
    assert 'health/health_report.md' in bundle_text
    assert '_atomic_copy_file(zip_path, latest_zip)' in bundle_text

    assert 'collect_health_report' in health_text
    assert 'render_health_report_md' in health_text
    assert 'signals["anim_latest"]' in health_text
    assert 'signals["mnemo_event_log"]' in health_text
    assert '## Desktop Mnemo events' in health_text
    assert 'browser_perf_evidence_report' in health_text
    assert 'browser_perf_trace' in health_text

    assert 'inspect_send_bundle' in inspect_text
    assert 'embedded health report is missing' in inspect_text
    assert 'mnemo_event_log' in inspect_text
    assert '## Desktop Mnemo events' in inspect_text
    assert 'browser_perf_evidence_status' in inspect_text
    assert 'browser_perf_artifacts_primary' in inspect_text
    assert 'has_browser_perf_evidence_report' in inspect_text
    assert 'render_inspection_md' in inspect_text
