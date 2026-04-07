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
        "anim_latest_meta": {"road_csv": "anim_latest_road_csv.csv"},
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



def _write_minimal_send_bundle(tmp_path: Path, *, global_token: str = "tok-123", local_token: str = "tok-123", diag_token: str = "tok-123") -> Path:
    zip_path = tmp_path / "bundle.zip"
    diag = _make_anim_diag(diag_token, ["npz", "road_csv"])
    local_ptr = _make_local_pointer(local_token, ["npz", "road_csv"])
    global_ptr = _make_global_pointer(global_token, ["npz", "road_csv"])

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({"added_files": 1}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))

        zf.writestr("triage/triage_report.md", "# triage\n")
        zf.writestr("triage/latest_anim_pointer_diagnostics.json", json.dumps(diag, ensure_ascii=False, indent=2))
        zf.writestr("triage/latest_anim_pointer_diagnostics.md", "# Anim latest diagnostics\n\n- token: tok-123\n")

        zf.writestr("workspace/_pointers/anim_latest.json", json.dumps(global_ptr, ensure_ascii=False, indent=2))
        zf.writestr("workspace/exports/anim_latest.json", json.dumps(local_ptr, ensure_ascii=False, indent=2))
        zf.writestr("workspace/exports/anim_latest.npz", b"npz bytes")
        zf.writestr("workspace/exports/anim_latest_road_csv.csv", "t,z0,z1,z2,z3\n0,0,0,0,0\n")
        zf.writestr("workspace/uploads/placeholder.txt", "u")
        zf.writestr("workspace/road_profiles/placeholder.txt", "r")
        zf.writestr("workspace/maneuvers/placeholder.txt", "m")
        zf.writestr("workspace/opt_runs/placeholder.txt", "o")
        zf.writestr("workspace/ui_state/state.json", json.dumps({"ok": True}, ensure_ascii=False))
        zf.writestr("ui_logs/app.log", "ok\n")
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
    assert anim["diagnostics_json_present"] is True
    assert anim["local_pointer_present"] is True
    assert anim["global_pointer_present"] is True
    assert "tok-123" in res.report_md
    assert "workspace/_pointers/anim_latest.json" in res.report_md

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
    assert rep["sections"]["anim_latest"]["json_zip_path"] == "triage/latest_anim_pointer_diagnostics.json"
    assert "Anim latest diagnostics" in html
    assert "tok-123" in html



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
