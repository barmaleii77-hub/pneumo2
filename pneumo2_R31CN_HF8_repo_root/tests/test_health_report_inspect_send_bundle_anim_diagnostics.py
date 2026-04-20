from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.tools.health_report import (
    add_health_report_to_zip,
    build_health_report,
    collect_health_report,
    render_health_report_md,
)
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



def _write_minimal_send_bundle(
    tmp_path: Path,
    *,
    validation_token: str = "tok-sidecar",
    diag_token: str = "tok-sidecar",
    dist_progress: dict | None = None,
    export_scopes: list[tuple[str, dict]] | None = None,
    geometry_acceptance_report: dict | None = None,
) -> Path:
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
    if dist_progress:
        triage["dist_progress"] = dict(dist_progress)

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
        if geometry_acceptance_report is not None:
            zf.writestr(
                "workspace/exports/geometry_acceptance_report.json",
                json.dumps(geometry_acceptance_report, ensure_ascii=False, indent=2),
            )
        for run_name, run_scope in list(export_scopes or []):
            zf.writestr(
                f"dist_runs/{run_name}/export/run_scope.json",
                json.dumps(run_scope, ensure_ascii=False, indent=2),
            )
    return zip_path


def _geometry_acceptance_report(gate: str, inspection_status: str) -> dict:
    reason = f"pytest geometry acceptance {gate}"
    return {
        "schema": "geometry_acceptance_report.v1",
        "inspection_status": inspection_status,
        "truth_state_summary": {
            "graphics_truth_state": "unavailable" if gate == "MISSING" else "approximate_inferred_with_warning",
            "release_gate": gate,
            "release_gate_reason": reason,
            "available": gate != "MISSING",
            "ok": gate == "PASS",
            "producer_owned": True,
            "no_synthetic_geometry": True,
        },
        "missing_fields": ["road_contact_ЛП_z_м"],
        "warnings": [reason, "missing producer-side fields: road_contact_ЛП_z_м"],
        "summary": {
            "release_gate": gate,
            "release_gate_reason": reason,
            "available": gate != "MISSING",
            "missing_triplets": ["road_contact_ЛП_z_м"],
        },
        "summary_lines": [f"Геом.acceptance gate={gate}: {reason}"],
    }


def test_health_and_inspect_preserve_geometry_acceptance_report_states(tmp_path: Path) -> None:
    cases = (
        ("MISSING", "missing", True),
        ("WARN", "warning", True),
        ("FAIL", "fail", False),
    )
    for gate, inspection_status, expected_ok in cases:
        case_dir = tmp_path / gate.lower()
        case_dir.mkdir(parents=True, exist_ok=True)
        zip_path = _write_minimal_send_bundle(
            case_dir,
            geometry_acceptance_report=_geometry_acceptance_report(gate, inspection_status),
        )

        rep = collect_health_report(zip_path)
        geom = dict(rep.signals.get("geometry_acceptance") or {})
        health_md = render_health_report_md(rep)
        summary = inspect_send_bundle(zip_path)
        inspect_md = render_inspection_md(summary)

        assert rep.ok is expected_ok
        assert geom["source_kind"] == "geometry_acceptance_report"
        assert geom["release_gate"] == gate
        assert geom["inspection_status"] == inspection_status
        assert geom["producer_owned"] is True
        assert geom["no_synthetic_geometry"] is True
        assert geom["missing_fields"] == ["road_contact_ЛП_z_м"]
        assert any(f"проверка геометрии: {gate}" in str(note) for note in rep.notes)
        assert summary["geometry_acceptance_gate"] == gate
        assert summary["geometry_acceptance_inspection_status"] == inspection_status
        assert summary["geometry_acceptance_missing_fields"] == ["road_contact_ЛП_z_м"]
        assert f"Допуск геометрии: {gate}" in health_md
        assert f"Состояние проверки: {inspection_status}" in health_md
        assert "Не хватает полей: road_contact_ЛП_z_м" in health_md
        assert f"Допуск геометрии: {gate}" in inspect_md
        assert f"Состояние проверки: {inspection_status}" in inspect_md
        assert "Не хватает полей: road_contact_ЛП_z_м" in inspect_md


def test_health_and_inspector_carry_latest_integrity_and_self_check_snapshot(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path)
    latest_zip = tmp_path / "latest_send_bundle.zip"
    zip_path.rename(latest_zip)
    with zipfile.ZipFile(latest_zip, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "reports/SELF_CHECK_SILENT_WARNINGS.json",
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
        )
    original_zip = tmp_path / "SEND_20260418_000000_bundle.zip"
    original_zip.write_bytes(latest_zip.read_bytes())
    final_sha = hashlib.sha256(latest_zip.read_bytes()).hexdigest()
    (tmp_path / "latest_send_bundle.sha256").write_text(final_sha + "  latest_send_bundle.zip\n", encoding="utf-8")
    (tmp_path / "latest_send_bundle_path.txt").write_text(str(original_zip.resolve()), encoding="utf-8")
    (tmp_path / "latest_evidence_manifest.json").write_text(
        json.dumps(
            {
                "schema": "diagnostics_evidence_manifest",
                "zip_path": str(original_zip.resolve()),
                "zip_sha256": "build-stage-sha",
                "zip_sha256_scope": "zip bytes at evidence manifest build time",
                "stage": "pytest_build_stage",
                "finalization_stage": "pytest_build_stage",
                "trigger": "watchdog",
                "collection_mode": "watchdog",
                "missing_warnings": ["producer-owned browser perf evidence is still missing"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    rep = collect_health_report(latest_zip)
    proof = dict(rep.signals.get("latest_integrity_proof") or {})
    snapshot = dict(rep.signals.get("self_check_silent_warnings") or {})
    health_md = render_health_report_md(rep)
    summary = inspect_send_bundle(latest_zip)
    inspect_md = render_inspection_md(summary)

    assert proof["status"] == "READY"
    assert proof["final_latest_zip_sha256"] == final_sha
    assert proof["latest_sha_sidecar_matches"] is True
    assert proof["latest_pointer_matches_original"] is True
    assert proof["embedded_manifest_stage_scoped"] is True
    assert proof["trigger"] == "watchdog"
    assert proof["collection_mode"] == "watchdog"
    assert proof["warning_only_gaps_present"] is True
    assert proof["no_release_closure_claim"] is True
    assert rep.ok is False
    assert snapshot["status"] == "READY"
    assert snapshot["snapshot_only"] is True
    assert snapshot["does_not_close_producer_warnings"] is True
    assert summary["latest_integrity_proof"]["status"] == "READY"
    assert summary["ok"] is False
    assert summary["self_check_silent_warnings"]["status"] == "READY"
    assert "Проверка актуального архива" in health_md
    assert "Финальное закрытие не заявлено: True" in health_md
    assert "Тихие предупреждения самопроверки" in inspect_md



def test_build_health_report_exposes_anim_latest_diagnostics_and_embeds_into_zip(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(tmp_path)

    json_path, md_path = build_health_report(zip_path, out_dir=tmp_path)
    assert json_path is not None and json_path.exists()
    assert md_path is not None and md_path.exists()

    rep = json.loads(json_path.read_text(encoding="utf-8"))
    anim = dict(rep.get("signals", {}).get("anim_latest") or {})
    mnemo = dict(rep.get("signals", {}).get("mnemo_event_log") or {})
    ring = dict(rep.get("signals", {}).get("ring_closure") or {})
    recommendations = list(rep.get("signals", {}).get("operator_recommendations") or [])
    artifacts = dict(rep.get("signals", {}).get("artifacts") or {})

    assert rep["schema"] == "health_report"
    assert anim["available"] is True
    assert anim["visual_cache_token"] == "tok-sidecar"
    assert anim["visual_reload_inputs"] == ["npz", "road_csv"]
    assert mnemo["severity"] == "critical"
    assert mnemo["current_mode"] == "Регуляторный коридор"
    assert recommendations
    assert recommendations[0].startswith("Сначала откройте мнемосхему")
    assert any("открытый шов кольца ожидаем" in msg for msg in recommendations)
    assert anim["browser_perf_evidence_status"] == "snapshot_only"
    assert anim["browser_perf_bundle_ready"] is False
    assert anim["browser_perf_comparison_status"] == "no_reference"
    assert anim["browser_perf_comparison_ready"] is False
    assert anim["ring_closure_policy"] == "strict_exact"
    assert anim["ring_seam_open"] is True
    assert ring["severity"] == "warn"
    assert ring["closure_policy"] == "strict_exact"
    assert ring["seam_open"] is True
    assert "открытый шов допустим" in ring["red_flags"][0]
    assert artifacts["health_report_embedded"] is False
    assert artifacts["browser_perf_registry_snapshot"] is False
    assert artifacts["browser_perf_previous_snapshot"] is False
    assert artifacts["browser_perf_contract"] is False
    assert artifacts["browser_perf_evidence_report"] is False
    assert artifacts["browser_perf_comparison_report"] is False
    assert artifacts["browser_perf_trace"] is False
    assert "Токен визуального кэша" in md_path.read_text(encoding="utf-8")
    assert "tok-sidecar" in md_path.read_text(encoding="utf-8")
    assert "## События мнемосхемы" in md_path.read_text(encoding="utf-8")
    assert "## Замыкание кольца" in md_path.read_text(encoding="utf-8")
    assert "## Рекомендуемые действия" in md_path.read_text(encoding="utf-8")
    assert "Важность: warn" in md_path.read_text(encoding="utf-8")
    assert "Шов кольца намеренно оставлен открытым в режиме strict_exact" in md_path.read_text(encoding="utf-8")
    assert "Большой перепад давлений" in md_path.read_text(encoding="utf-8")
    assert "Данные производительности" in md_path.read_text(encoding="utf-8")
    assert "Состояние сравнения производительности" in md_path.read_text(encoding="utf-8")
    assert "Замыкание кольца: режим=strict_exact / применено=False / шов открыт=True / скачок шва, м=0.012 / исходный скачок, м=0.015" in md_path.read_text(encoding="utf-8")
    assert "Отчёт производительности: False" in md_path.read_text(encoding="utf-8")

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
    assert summary["operator_recommendations"][0].startswith("Сначала откройте мнемосхему")
    assert summary["anim_latest"]["visual_reload_inputs"] == ["npz", "road_csv"]
    assert summary["anim_latest"]["browser_perf_evidence_status"] == "snapshot_only"
    assert summary["anim_latest"]["browser_perf_comparison_status"] == "no_reference"
    assert summary["anim_latest"]["ring_closure_policy"] == "strict_exact"
    assert summary["anim_latest"]["ring_seam_open"] is True
    assert summary["ring_closure"]["severity"] == "warn"
    assert summary["ring_closure"]["closure_policy"] == "strict_exact"
    assert summary["ring_closure"]["seam_open"] is True
    assert summary["anim_latest"]["browser_perf_registry_snapshot_ref"] == "browser_perf_registry_snapshot.json"
    assert summary["anim_latest"]["browser_perf_registry_snapshot_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_contract_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_evidence_report_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_comparison_report_in_bundle"] is False
    assert summary["anim_latest"]["browser_perf_trace_in_bundle"] is False
    inspect_md = render_inspection_md(summary)
    assert "tok-sidecar" in inspect_md
    assert "## События мнемосхемы" in inspect_md
    assert "## Замыкание кольца" in inspect_md
    assert "## Рекомендуемые действия" in inspect_md
    assert "Важность: warn" in inspect_md
    assert "Шов кольца намеренно оставлен открытым в режиме strict_exact" in inspect_md
    assert "Регуляторный коридор" in inspect_md
    assert "Данные производительности" in inspect_md
    assert "Сравнение производительности" in inspect_md
    assert "Замыкание кольца: режим=strict_exact / применено=False / шов открыт=True / скачок шва, м=0.012 / исходный скачок, м=0.015" in inspect_md
    assert "Отчёт производительности: False" in inspect_md
    assert "Трасса производительности: False" in inspect_md
    assert "Основные данные производительности" in inspect_md
    assert "Дополнительные данные производительности" in inspect_md
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
    assert any("Токен визуального кэша" in msg for msg in anim.get("issues") or [])
    assert any("Токен визуального кэша" in msg for msg in notes)
    assert any("В мнемосхеме есть активные события: 1" in msg for msg in notes)
    assert any("Шов кольца открыт в режиме strict_exact" in msg for msg in notes)
    assert any("Шов кольца намеренно оставлен открытым в режиме strict_exact" in msg for msg in notes)
    assert any("данные производительности анимации не готовы к восстановлению из архива" in msg for msg in notes)
    assert any("состояние сравнения производительности анимации: no_reference" in msg for msg in notes)



def test_sources_wire_health_report_and_offline_inspector_into_send_bundle_flow() -> None:
    bundle_text = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    health_text = (ROOT / "pneumo_solver_ui" / "tools" / "health_report.py").read_text(encoding="utf-8")
    inspect_text = (ROOT / "pneumo_solver_ui" / "tools" / "inspect_send_bundle.py").read_text(encoding="utf-8")

    assert 'build_health_report(zip_path, out_dir=out_dir)' in bundle_text
    assert 'def _run_health_pass' in bundle_text
    assert '_replace_zip_entries(_entries)' in bundle_text
    assert 'health/health_report.json' in bundle_text
    assert 'health/health_report.md' in bundle_text
    assert '_atomic_copy_file(zip_path, latest_zip)' in bundle_text

    assert 'collect_health_report' in health_text
    assert 'render_health_report_md' in health_text
    assert 'signals["anim_latest"]' in health_text
    assert 'signals["optimizer_scope"]' in health_text
    assert 'signals["optimizer_scope_gate"]' in health_text
    assert 'signals["mnemo_event_log"]' in health_text
    assert 'signals["ring_closure"]' in health_text
    assert 'signals["operator_recommendations"]' in health_text
    assert 'signals["latest_integrity_proof"]' in health_text
    assert 'signals["self_check_silent_warnings"]' in health_text
    assert '## Оптимизация' in health_text
    assert '## Проверка актуального архива' in health_text
    assert "scope_sync_ok" in health_text
    assert '## События мнемосхемы' in health_text
    assert '## Замыкание кольца' in health_text
    assert '## Рекомендуемые действия' in health_text
    assert 'browser_perf_evidence_report' in health_text
    assert 'browser_perf_trace' in health_text

    assert 'inspect_send_bundle' in inspect_text
    assert 'отчёт состояния отсутствует в архиве' in inspect_text
    assert 'mnemo_event_log' in inspect_text
    assert 'ring_closure' in inspect_text
    assert 'optimizer_scope' in inspect_text
    assert 'optimizer_scope_gate' in inspect_text
    assert 'latest_integrity_proof' in inspect_text
    assert 'self_check_silent_warnings' in inspect_text
    assert 'operator_recommendations' in inspect_text
    assert '## Оптимизация' in inspect_text
    assert '## Проверка актуального архива' in inspect_text
    assert "scope_sync_ok" in inspect_text
    assert "Риск выпуска" in inspect_text
    assert '## События мнемосхемы' in inspect_text
    assert '## Замыкание кольца' in inspect_text
    assert '## Рекомендуемые действия' in inspect_text
    assert 'browser_perf_evidence_status' in inspect_text
    assert 'Основные данные производительности' in inspect_text
    assert 'has_browser_perf_evidence_report' in inspect_text
    assert 'render_inspection_md' in inspect_text


def test_health_report_and_inspector_surface_optimizer_scope_from_triage(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(
        tmp_path,
        dist_progress={
            "status": "running",
            "completed": 9,
            "in_flight": 3,
            "cached_hits": 1,
            "duplicates_skipped": 2,
            "problem_hash": "ph_bundle_scope_1234567890",
            "problem_hash_short": "ph_bundle_sc",
            "problem_hash_mode": "legacy",
        },
    )

    json_path, md_path = build_health_report(zip_path, out_dir=tmp_path)
    rep = json.loads(Path(json_path).read_text(encoding="utf-8"))
    optimizer_scope = dict(rep.get("signals", {}).get("optimizer_scope") or {})
    triage = dict(rep.get("signals", {}).get("triage") or {})
    triage_dist = dict(triage.get("dist_progress") or {})
    md_text = Path(md_path).read_text(encoding="utf-8")

    assert optimizer_scope["problem_hash"] == "ph_bundle_scope_1234567890"
    assert optimizer_scope["problem_hash_short"] == "ph_bundle_sc"
    assert optimizer_scope["problem_hash_mode"] == "legacy"
    assert triage_dist["problem_hash_mode"] == "legacy"
    assert "## Оптимизация" in md_text
    assert "Область задачи: `ph_bundle_sc`" in md_text
    assert "Режим хэша: `legacy`" in md_text

    add_health_report_to_zip(zip_path, json_path, md_path)
    summary = inspect_send_bundle(zip_path)
    inspect_md = render_inspection_md(summary)

    assert dict(summary.get("optimizer_scope") or {})["problem_hash_mode"] == "legacy"
    assert "## Оптимизация" in inspect_md
    assert "Область задачи: `ph_bundle_sc`" in inspect_md
    assert "Режим хэша: `legacy`" in inspect_md


def test_health_report_and_inspector_surface_optimizer_scope_mismatch_between_triage_and_export(tmp_path: Path) -> None:
    zip_path = _write_minimal_send_bundle(
        tmp_path,
        dist_progress={
            "status": "running",
            "completed": 4,
            "in_flight": 1,
            "cached_hits": 0,
            "duplicates_skipped": 0,
            "problem_hash": "ph_bundle_scope_1234567890",
            "problem_hash_short": "ph_bundle_sc",
            "problem_hash_mode": "stable",
        },
        export_scopes=[
            (
                "DIST_SCOPE_B",
                {
                    "schema": "expdb_run_scope_v1",
                    "run_id": "dist-run-002",
                    "problem_hash": "ph_bundle_scope_mismatch_222222",
                    "problem_hash_short": "ph_bundle_ex",
                    "problem_hash_mode": "legacy",
                    "objective_keys": ["comfort", "energy"],
                    "penalty_key": "violations",
                },
            )
        ],
    )

    json_path, md_path = build_health_report(zip_path, out_dir=tmp_path)
    rep = json.loads(Path(json_path).read_text(encoding="utf-8"))
    optimizer_scope = dict(rep.get("signals", {}).get("optimizer_scope") or {})
    optimizer_scope_gate = dict(rep.get("signals", {}).get("optimizer_scope_gate") or {})
    notes = [str(x) for x in (rep.get("notes") or [])]
    md_text = Path(md_path).read_text(encoding="utf-8")

    assert optimizer_scope["problem_hash"] == "ph_bundle_scope_1234567890"
    assert optimizer_scope["problem_hash_mode"] == "stable"
    assert optimizer_scope["scope_sync_ok"] is False
    assert optimizer_scope_gate["release_gate"] == "FAIL"
    assert optimizer_scope_gate["release_risk"] is True
    assert "export:DIST_SCOPE_B" in optimizer_scope["sources"]
    assert any("поле problem_hash отличается" in msg for msg in optimizer_scope.get("issues") or [])
    assert any("поле problem_hash_mode отличается" in msg for msg in optimizer_scope.get("issues") or [])
    assert any("поле problem_hash отличается" in msg for msg in notes)
    assert any("риск выпуска по области оптимизации" in msg for msg in notes)
    assert "Допуск области: `FAIL`" in md_text
    assert "Риск выпуска: `True`" in md_text
    assert "Синхронизация области: `False`" in md_text
    assert "Замечание области: область оптимизации: поле problem_hash отличается" in md_text

    add_health_report_to_zip(zip_path, json_path, md_path)
    summary = inspect_send_bundle(zip_path)
    inspect_md = render_inspection_md(summary)

    assert dict(summary.get("optimizer_scope") or {})["scope_sync_ok"] is False
    assert dict(summary.get("optimizer_scope_gate") or {})["release_gate"] == "FAIL"
    assert any("поле problem_hash отличается" in msg for msg in (summary.get("notes") or []))
    assert "Допуск области: `FAIL`" in inspect_md
    assert "Риск выпуска: `True`" in inspect_md
    assert "Синхронизация области: `False`" in inspect_md
    assert "Замечание области: область оптимизации: поле problem_hash отличается" in inspect_md
