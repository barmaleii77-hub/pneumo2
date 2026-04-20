from __future__ import annotations

import hashlib
import json
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols
from pneumo_solver_ui.tools.make_send_bundle import make_send_bundle
from pneumo_solver_ui.ui_persistence import save_autosave

ROOT = Path(__file__).resolve().parents[1]


def _solver_df() -> pd.DataFrame:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data: dict[str, object] = {
        "время_с": t,
        "скорость_vx_м_с": np.array([10.0, 10.0, 10.0], dtype=float),
        "yaw_рад": np.array([0.0, 0.0, 0.0], dtype=float),
    }
    for c in CORNERS:
        data[f"дорога_{c}_м"] = np.array([0.0, 0.0, 0.0], dtype=float)
        data[f"перемещение_колеса_{c}_м"] = np.array([0.3, 0.3, 0.3], dtype=float)
        data[f"рама_угол_{c}_z_м"] = np.array([0.5, 0.5, 0.5], dtype=float)

    seed = 0.0
    for kind in POINT_KINDS:
        for corner in CORNERS:
            for axis_i, col in enumerate(point_cols(kind, corner)):
                base = seed + float(axis_i)
                data[col] = np.array([base, base + 0.01, base + 0.02], dtype=float)
            seed += 0.1
    return pd.DataFrame(data)


def test_make_send_bundle_health_sees_final_triage_and_latest_copy(tmp_path: Path, monkeypatch) -> None:
    env_ws = tmp_path / "env_workspace"
    app_state = tmp_path / "app_state"
    out_dir = tmp_path / "send_bundles"
    env_ws.mkdir(parents=True, exist_ok=True)
    app_state.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(env_ws))
    monkeypatch.setenv("PNEUMO_BUNDLE_RUN_SELFCHECK", "0")

    ok, _info = save_autosave(app_state, {"demo": True, "value": 1})
    assert ok is True

    exports_dir = env_ws / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    road_csv = env_ws / "road_profiles" / "road.csv"
    road_csv.parent.mkdir(parents=True, exist_ok=True)
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n0.1,0.01,0.02,-0.01,-0.02\n", encoding="utf-8")

    npz_path, pointer_path = export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )
    assert npz_path.exists()
    assert pointer_path.exists()
    assert (env_ws / "_pointers" / "anim_latest.json").exists()
    (exports_dir / "anim_latest.desktop_mnemo_events.json").write_text(
        json.dumps(
            {
                "schema_version": "desktop_mnemo_event_log_v1",
                "updated_utc": "2026-04-10T09:45:00Z",
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

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        zip_path = make_send_bundle(repo_root=ROOT, out_dir=out_dir, keep_last_n=1, max_file_mb=20)
    latest_zip = out_dir / "latest_send_bundle.zip"
    latest_txt = out_dir / "latest_send_bundle_path.txt"
    latest_sha = out_dir / "latest_send_bundle.sha256"
    latest_triage_md = out_dir / "latest_triage_report.md"
    latest_triage_json = out_dir / "latest_triage_report.json"
    assert latest_zip.exists()
    assert latest_txt.read_text(encoding="utf-8").strip() == str(zip_path.resolve())
    assert latest_sha.read_text(encoding="utf-8").strip() == (
        hashlib.sha256(latest_zip.read_bytes()).hexdigest() + "  latest_send_bundle.zip"
    )
    assert latest_zip.read_bytes() == zip_path.read_bytes()
    assert not any(
        "Duplicate name: 'validation/validation_report." in str(w.message)
        or "Duplicate name: 'dashboard/" in str(w.message)
        for w in caught
    )

    with zipfile.ZipFile(zip_path, "r") as z:
        names = set(z.namelist())
        assert "triage/triage_report.json" in names
        assert "triage/triage_report_pre.md" in names
        assert "triage/triage_report_pre.json" in names
        assert "health/health_report.json" in names
        triage_md_main = z.read("triage/triage_report.md")
        triage_main = z.read("triage/triage_report.json")
        triage_md_text = triage_md_main.decode("utf-8", errors="replace")
        triage_json = json.loads(triage_main.decode("utf-8", errors="replace"))
        health = json.loads(z.read("health/health_report.json").decode("utf-8", errors="replace"))

    artifacts = dict((health.get("signals") or {}).get("artifacts") or {})
    mnemo = dict((health.get("signals") or {}).get("mnemo_event_log") or {})
    recommendations = list((health.get("signals") or {}).get("operator_recommendations") or [])
    assert artifacts.get("triage_report") is True
    assert artifacts.get("validation_report") is True
    assert artifacts.get("anim_diagnostics") is True
    assert triage_json["mnemo_event_log"]["severity"] == "critical"
    assert triage_json["operator_recommendations"][0].startswith("Сначала откройте мнемосхему")
    assert mnemo["severity"] == "critical"
    assert mnemo["current_mode"] == "Регуляторный коридор"
    assert recommendations[0].startswith("Сначала откройте мнемосхему")
    assert latest_triage_md.read_text(encoding="utf-8") == triage_md_text
    assert json.loads(latest_triage_json.read_text(encoding="utf-8")) == triage_json
    assert "Актуальный архив проекта" in triage_md_text
    assert "Проверка актуального архива" in triage_md_text

    with zipfile.ZipFile(latest_zip, "r") as z:
        latest_names = set(z.namelist())
        assert "triage/triage_report.json" in latest_names
        assert "health/health_report.json" in latest_names
        assert z.read("triage/triage_report.md") == triage_md_main
        assert z.read("triage/triage_report.json") == triage_main


def test_make_send_bundle_projects_optimizer_scope_gate_into_index_and_registry(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    runs_root = repo_root / "runs"
    dist_dir = runs_root / "dist_runs" / "DIST_SCOPE_MISMATCH"
    export_dir = dist_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "pneumo_solver_ui" / "logs").mkdir(parents=True, exist_ok=True)

    (dist_dir / "progress.json").write_text(
        json.dumps(
            {
                "status": "running",
                "completed": 7,
                "in_flight": 2,
                "cached_hits": 1,
                "duplicates_skipped": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (dist_dir / "problem_hash.txt").write_text("ph_triage_scope_1234567890\n", encoding="utf-8")
    (dist_dir / "problem_hash_mode.txt").write_text("stable\n", encoding="utf-8")
    (export_dir / "run_scope.json").write_text(
        json.dumps(
            {
                "schema": "expdb_run_scope_v1",
                "run_id": "dist-run-001",
                "problem_hash": "ph_export_scope_9999999999",
                "problem_hash_short": "ph_export_sc",
                "problem_hash_mode": "legacy",
                "objective_keys": ["comfort", "energy"],
                "penalty_key": "violations",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    env_ws = tmp_path / "env_workspace"
    app_state = tmp_path / "app_state"
    out_dir = tmp_path / "send_bundles"
    env_ws.mkdir(parents=True, exist_ok=True)
    app_state.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(env_ws))
    monkeypatch.setenv("PNEUMO_BUNDLE_RUN_SELFCHECK", "0")
    monkeypatch.setattr("pneumo_solver_ui.run_registry._runs_root", lambda: runs_root)

    ok, _info = save_autosave(app_state, {"demo": True, "value": 1})
    assert ok is True

    exports_dir = env_ws / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    road_csv = env_ws / "road_profiles" / "road.csv"
    road_csv.parent.mkdir(parents=True, exist_ok=True)
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n0.1,0.01,0.02,-0.01,-0.02\n", encoding="utf-8")

    npz_path, pointer_path = export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )
    assert npz_path.exists()
    assert pointer_path.exists()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        zip_path = make_send_bundle(repo_root=repo_root, out_dir=out_dir, keep_last_n=1, max_file_mb=20)
    assert zip_path.exists()
    assert not any(
        "Duplicate name: 'validation/validation_report." in str(w.message)
        or "Duplicate name: 'dashboard/" in str(w.message)
        for w in caught
    )

    validation = json.loads((out_dir / "latest_send_bundle_validation.json").read_text(encoding="utf-8"))
    latest_dashboard = json.loads((out_dir / "latest_dashboard.json").read_text(encoding="utf-8"))
    gate = dict(validation.get("optimizer_scope_gate") or {})
    scope = dict(validation.get("optimizer_scope") or {})
    assert gate["release_gate"] == "FAIL"
    assert gate["release_risk"] is True
    assert scope["problem_hash"] == "ph_triage_scope_1234567890"
    assert scope["problem_hash_mode"] == "stable"

    bundle_index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    bundle_rec = dict((bundle_index.get("bundles") or [])[0] or {})
    assert dict(bundle_rec.get("validation") or {})["release_risks"] == 1
    assert bundle_rec["validation_release_risks"] == 1
    assert bundle_rec["optimizer_scope_release_gate"] == "FAIL"
    assert bundle_rec["optimizer_scope_release_risk"] is True
    assert bundle_rec["optimizer_scope_problem_hash"] == "ph_triage_scope_1234567890"
    assert bundle_rec["optimizer_scope_problem_hash_mode"] == "stable"
    assert dict(bundle_rec.get("optimizer_scope_gate") or {})["release_gate"] == "FAIL"
    assert dict(bundle_rec.get("optimizer_scope") or {})["mismatch_fields"] == ["problem_hash", "problem_hash_mode"]

    runs_index = json.loads((runs_root / "index.json").read_text(encoding="utf-8"))
    last_event = dict(runs_index.get("last_event") or {})
    assert last_event["event"] == "send_bundle_created"
    assert "optimizer_scope_release_gate" in last_event
    assert "validation_release_risks" in last_event

    with zipfile.ZipFile(zip_path, "r") as z:
        triage_validation = json.loads(
            z.read("triage/latest_send_bundle_validation.json").decode("utf-8", errors="replace")
        )
        root_validation = json.loads(
            z.read("validation/validation_report.json").decode("utf-8", errors="replace")
        )
        zip_dashboard = json.loads(
            z.read("dashboard/dashboard.json").decode("utf-8", errors="replace")
        )
    assert dict(triage_validation.get("optimizer_scope_gate") or {})["release_gate"] == "FAIL"
    assert triage_validation == root_validation
    assert dict(latest_dashboard.get("optimizer_scope_gate") or {})["release_gate"] == "FAIL"
    assert dict(latest_dashboard.get("optimizer_scope") or {})["problem_hash"] == "ph_triage_scope_1234567890"
    assert zip_dashboard == latest_dashboard
