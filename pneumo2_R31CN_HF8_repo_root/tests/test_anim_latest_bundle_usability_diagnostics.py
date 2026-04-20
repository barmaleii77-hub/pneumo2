from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary, save_latest_animation_ptr
from pneumo_solver_ui.tools.dashboard_report import generate_dashboard_report
from pneumo_solver_ui.tools.health_report import build_health_report
from pneumo_solver_ui.tools.validate_send_bundle import validate_send_bundle


def _write_external_pointer_bundle(tmp_path: Path) -> Path:
    zip_path = tmp_path / "bundle.zip"
    diag = {
        "anim_latest_available": False,
        "anim_latest_global_pointer_json": "C:/host/workspace/_pointers/anim_latest.json",
        "anim_latest_pointer_json": "",
        "anim_latest_npz_path": "",
        "anim_latest_visual_cache_token": "",
        "anim_latest_visual_reload_inputs": [],
        "anim_latest_visual_cache_dependencies": {},
        "anim_latest_updated_utc": "",
        "anim_latest_usable": False,
        "anim_latest_issues": [],
    }
    global_ptr = {
        "kind": "anim_latest",
        "updated_at": "2026-03-12T15:23:43Z",
        "meta": {"source": "pytest"},
        "pointer_json": "/tmp/pytest-of-root/pytest-3/test_export_anim_latest_pointe0/anim_latest.json",
        "npz_path": "/tmp/pytest-of-root/pytest-3/test_export_anim_latest_pointe0/anim_latest.npz",
        "schema_version": "pneumo_npz_meta_v1",
        "updated_utc": "2026-03-12T15:23:43.684336+00:00",
        "visual_cache_token": "tok-global",
        "visual_reload_inputs": ["npz", "road_csv"],
        "visual_cache_dependencies": {
            "version": 1,
            "context": "anim_latest export pointer",
            "npz": {"path": "/tmp/pytest-of-root/pytest-3/test_export_anim_latest_pointe0/anim_latest.npz", "exists": True, "size": 3372},
            "road_csv_ref": "anim_latest_road_csv.csv",
            "road_csv_path": "/tmp/pytest-of-root/pytest-3/test_export_anim_latest_pointe0/anim_latest_road_csv.csv",
            "road_csv": {"path": "/tmp/pytest-of-root/pytest-3/test_export_anim_latest_pointe0/anim_latest_road_csv.csv", "exists": True, "size": 50},
        },
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest", "created_at": "2026-03-13T00:31:22"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))

        zf.writestr("triage/triage_report.md", "# triage\n")
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps(diag, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.md", "# Anim latest diagnostics\n")
        zf.writestr("workspace/_pointers/anim_latest.json", json.dumps(global_ptr, ensure_ascii=False, indent=2))

        zf.writestr("workspace/exports/.gitkeep", "")
        zf.writestr("workspace/uploads/placeholder.txt", "u")
        zf.writestr("workspace/road_profiles/placeholder.txt", "r")
        zf.writestr("workspace/maneuvers/placeholder.txt", "m")
        zf.writestr("workspace/opt_runs/placeholder.txt", "o")
        zf.writestr("workspace/ui_state/state.json", json.dumps({"ok": True}, ensure_ascii=False))
        zf.writestr("ui_logs/app.log", "ok\n")
    return zip_path


def _write_no_anim_bundle(tmp_path: Path) -> Path:
    zip_path = tmp_path / "bundle_no_anim.zip"
    diag = {
        "anim_latest_available": False,
        "anim_latest_global_pointer_json": "C:/external/workspace/_pointers/anim_latest.json",
        "anim_latest_pointer_json": "",
        "anim_latest_npz_path": "",
        "anim_latest_visual_cache_token": "",
        "anim_latest_visual_reload_inputs": [],
        "anim_latest_visual_cache_dependencies": {},
        "anim_latest_updated_utc": "",
        "anim_latest_usable": False,
        "anim_latest_issues": [],
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest", "created_at": "2026-03-13T00:31:22"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("triage/triage_report.md", "# triage\n")
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps(diag, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.md", "# Anim latest diagnostics\n")
        zf.writestr("workspace/exports/.gitkeep", "")
        zf.writestr("workspace/uploads/placeholder.txt", "u")
        zf.writestr("workspace/road_profiles/placeholder.txt", "r")
        zf.writestr("workspace/maneuvers/placeholder.txt", "m")
        zf.writestr("workspace/opt_runs/placeholder.txt", "o")
        zf.writestr("workspace/ui_state/state.json", json.dumps({"ok": True}, ensure_ascii=False))
        zf.writestr("ui_logs/app.log", "ok\n")
    return zip_path


def _write_expected_anim_bundle_without_pointers(tmp_path: Path) -> Path:
    zip_path = tmp_path / "bundle_expected_anim.zip"
    diag = {
        "anim_latest_available": True,
        "anim_latest_global_pointer_json": "C:/external/workspace/_pointers/anim_latest.json",
        "anim_latest_pointer_json": "C:/external/workspace/exports/anim_latest.json",
        "anim_latest_npz_path": "C:/external/workspace/exports/anim_latest.npz",
        "anim_latest_visual_cache_token": "tok-expected",
        "anim_latest_visual_reload_inputs": ["npz"],
        "anim_latest_visual_cache_dependencies": {},
        "anim_latest_updated_utc": "2026-03-12T15:23:43.684336+00:00",
        "anim_latest_usable": False,
        "anim_latest_issues": [],
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest", "created_at": "2026-03-13T00:31:22"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("triage/triage_report.md", "# triage\n")
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps(diag, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.md", "# Anim latest diagnostics\n")
        zf.writestr("workspace/exports/.gitkeep", "")
        zf.writestr("workspace/uploads/placeholder.txt", "u")
        zf.writestr("workspace/road_profiles/placeholder.txt", "r")
        zf.writestr("workspace/maneuvers/placeholder.txt", "m")
        zf.writestr("workspace/opt_runs/placeholder.txt", "o")
        zf.writestr("workspace/ui_state/state.json", json.dumps({"ok": True}, ensure_ascii=False))
        zf.writestr("ui_logs/app.log", "ok\n")
    return zip_path


def test_collect_anim_latest_diagnostics_summary_marks_external_missing_paths_unusable(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))
    missing_ptr = tmp_path / "external" / "anim_latest.json"
    missing_npz = tmp_path / "external" / "anim_latest.npz"

    save_latest_animation_ptr(npz_path=missing_npz, pointer_json=missing_ptr, meta={"source": "pytest"})
    diag = collect_anim_latest_diagnostics_summary(include_meta=True)

    assert diag["anim_latest_available"] is True
    assert diag["anim_latest_usable"] is False
    assert diag["anim_latest_pointer_json_exists"] is False
    assert diag["anim_latest_npz_exists"] is False
    assert diag["anim_latest_pointer_json_in_workspace"] is False
    assert diag["anim_latest_npz_in_workspace"] is False
    assert any("outside current workspace" in msg for msg in diag["anim_latest_issues"])
    assert any("missing on disk" in msg for msg in diag["anim_latest_issues"])


def test_validate_and_health_report_surface_unusable_external_anim_pointer(tmp_path: Path) -> None:
    zip_path = _write_external_pointer_bundle(tmp_path)

    res = validate_send_bundle(zip_path)
    anim = dict(res.report_json.get("anim_latest") or {})
    warnings = [str(x) for x in (res.report_json.get("warnings") or [])]

    assert res.ok is True
    assert anim["available"] is True
    assert anim["visual_cache_token"] == "tok-global"
    assert anim["usable_from_bundle"] is False
    assert anim["pointer_json_in_bundle"] is False
    assert anim["npz_path_in_bundle"] is False
    assert any("не восстанавливаются из архива" in msg or "не восстанавливается из архива" in msg for msg in anim["issues"])
    assert any("находится вне архива" in msg for msg in anim["issues"])
    assert any("из этого архива они не восстанавливаются" in msg for msg in warnings)

    json_path, _md_path = build_health_report(zip_path, out_dir=tmp_path)
    rep = json.loads(Path(json_path).read_text(encoding="utf-8"))
    health_anim = dict(rep.get("signals", {}).get("anim_latest") or {})

    assert health_anim["visual_cache_token"] == "tok-global"
    assert health_anim["usable_from_bundle"] is False
    assert any("не восстанавливаются из архива" in msg or "не восстанавливается из архива" in msg for msg in health_anim["issues"])

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest_triage_report.md").write_text("# triage\n", encoding="utf-8")
    (out_dir / "latest_triage_report.json").write_text(json.dumps({"ok": True}, ensure_ascii=False, indent=2), encoding="utf-8")

    html, rep_dash = generate_dashboard_report(repo_root, out_dir, zip_path=zip_path)
    dash_anim = dict(rep_dash.get("anim_latest") or {})
    assert dash_anim["visual_cache_token"] == "tok-global"
    assert dash_anim["usable_from_bundle"] is False
    assert "usable_from_bundle" in html
    assert "tok-global" in html


def test_sources_wire_bundle_usability_diagnostics_everywhere() -> None:
    root = Path(__file__).resolve().parents[1]
    make_text = (root / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    validate_text = (root / "pneumo_solver_ui" / "tools" / "validate_send_bundle.py").read_text(encoding="utf-8")
    health_text = (root / "pneumo_solver_ui" / "tools" / "health_report.py").read_text(encoding="utf-8")
    dashboard_text = (root / "pneumo_solver_ui" / "tools" / "dashboard_report.py").read_text(encoding="utf-8")
    triage_text = (root / "pneumo_solver_ui" / "tools" / "triage_report.py").read_text(encoding="utf-8")

    assert "anim_latest_usable" in make_text
    assert "anim_latest_pointer_json_exists" in make_text
    assert "usable_from_bundle" in validate_text
    assert "pointer_json_in_bundle" in validate_text
    assert "npz_path_in_bundle" in validate_text
    assert 'rep["optimizer_scope"]' in validate_text
    assert 'rep["optimizer_scope_gate"]' in validate_text
    assert "release_risks" in validate_text
    assert "usable_from_bundle" in health_text
    assert "scope_sync_ok" in health_text
    assert 'signals["optimizer_scope_gate"]' in health_text
    assert "usable_from_bundle" in dashboard_text
    assert "Синхронизация оптимизации" in dashboard_text
    assert "Допуск оптимизации" in dashboard_text
    assert "anim_latest_usable" in triage_text


def test_validate_send_bundle_skips_missing_anim_pointer_warnings_when_no_anim_export_happened(tmp_path: Path) -> None:
    zip_path = _write_no_anim_bundle(tmp_path)

    res = validate_send_bundle(zip_path)
    warnings = [str(x) for x in (res.report_json.get("warnings") or [])]
    anim = dict(res.report_json.get("anim_latest") or {})

    assert res.ok is True
    assert anim["available"] is False
    assert anim["contract_expected"] is False
    assert not any("global anim_latest pointer" in msg for msg in warnings)
    assert not any("local anim_latest pointer" in msg for msg in warnings)


def test_validate_send_bundle_keeps_missing_pointer_warnings_when_anim_contract_is_expected(tmp_path: Path) -> None:
    zip_path = _write_expected_anim_bundle_without_pointers(tmp_path)

    res = validate_send_bundle(zip_path)
    warnings = [str(x) for x in (res.report_json.get("warnings") or [])]
    anim = dict(res.report_json.get("anim_latest") or {})

    assert res.ok is True
    assert anim["available"] is True
    assert anim["contract_expected"] is True
    assert any("общий указатель последней анимации" in msg for msg in warnings)
    assert any("локальный указатель последней анимации" in msg for msg in warnings)
