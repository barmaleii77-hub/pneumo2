from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols
from pneumo_solver_ui.tools.make_send_bundle import _collect_anim_latest_bundle_diagnostics
from pneumo_solver_ui.tools.triage_report import generate_triage_report


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


def test_collect_anim_latest_bundle_diagnostics_surfaces_sidecar_paths(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports_dir = workspace / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n0.1,0.01,0.02,-0.01,-0.02\n", encoding="utf-8")
    axay_csv = tmp_path / "axay.csv"
    axay_csv.write_text("t,ax,ay\n0,0,0\n0.1,0.1,0.2\n", encoding="utf-8")
    scenario_json = tmp_path / "scenario.json"
    scenario_json.write_text(json.dumps({"schema": "ring_v2", "segments": []}, ensure_ascii=False), encoding="utf-8")

    export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
            "axay_csv": str(axay_csv),
            "scenario_json": str(scenario_json),
        },
    )

    diag, _md = _collect_anim_latest_bundle_diagnostics(tmp_path)
    assert diag["anim_latest_road_csv_ref"] == "anim_latest_road_csv.csv"
    assert diag["anim_latest_road_csv_path"].endswith("anim_latest_road_csv.csv")
    assert diag["anim_latest_road_csv_exists"] is True
    assert diag["anim_latest_axay_csv_ref"] == "anim_latest_axay_csv.csv"
    assert diag["anim_latest_axay_csv_exists"] is True
    assert diag["anim_latest_scenario_json_ref"] == "anim_latest_scenario_json.json"
    assert diag["anim_latest_scenario_json_exists"] is True
    assert diag["anim_latest_contract_sidecar_ref"] == "anim_latest.contract.sidecar.json"
    assert diag["anim_latest_contract_sidecar_exists"] is True
    assert diag["anim_latest_hardpoints_source_of_truth_ref"] == "HARDPOINTS_SOURCE_OF_TRUTH.json"
    assert diag["anim_latest_hardpoints_source_of_truth_exists"] is True
    assert diag["anim_latest_cylinder_packaging_passport_ref"] == "CYLINDER_PACKAGING_PASSPORT.json"
    assert diag["anim_latest_cylinder_packaging_passport_exists"] is True
    assert diag["anim_latest_road_contract_web_ref"] == "road_contract_web.json"
    assert diag["anim_latest_road_contract_web_exists"] is True
    assert diag["anim_latest_road_contract_desktop_ref"] == "road_contract_desktop.json"
    assert diag["anim_latest_road_contract_desktop_exists"] is True

    web_contract = json.loads((exports_dir / "road_contract_web.json").read_text(encoding="utf-8"))
    desktop_contract = json.loads((exports_dir / "road_contract_desktop.json").read_text(encoding="utf-8"))
    assert web_contract["level"] == "PASS"
    assert desktop_contract["level"] == "PASS"
    assert web_contract["road_width_status"] == "explicit"
    assert desktop_contract["road_width_status"] == "explicit"


def test_generate_triage_report_prefers_latest_send_bundle_path_over_stale_registry_event(tmp_path: Path) -> None:
    send_bundles = tmp_path / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    latest_zip = tmp_path / "send_bundles" / "SEND_current_bundle.zip"
    latest_zip.write_bytes(b"zip")
    (send_bundles / "latest_send_bundle_path.txt").write_text(str(latest_zip.resolve()), encoding="utf-8")
    (send_bundles / "latest_send_bundle_validation.json").write_text(
        json.dumps({"ok": True, "errors": [], "warnings": [], "stats": {}, "zip_path": str(latest_zip.resolve())}, ensure_ascii=False),
        encoding="utf-8",
    )
    (send_bundles / "latest_anim_pointer_diagnostics.json").write_text(
        json.dumps({"anim_latest_available": False}, ensure_ascii=False),
        encoding="utf-8",
    )

    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    stale = {
        "ts": "2026-03-22T11:00:00",
        "event": "send_bundle_created",
        "run_type": "send_bundle",
        "run_id": "SEND_OLD",
        "zip_path": "/mnt/data/work_r30/send_bundles/SEND_old_bundle.zip",
        "env": {"cwd": "/mnt/data/work_r30"},
    }
    current = {
        "ts": "2026-03-22T10:59:00",
        "event": "send_bundle_created",
        "run_type": "send_bundle",
        "run_id": "SEND_CURRENT",
        "zip_path": str(latest_zip.resolve()),
        "env": {"cwd": str(tmp_path.resolve())},
    }
    (runs_root / "run_registry.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in [current, stale]) + "\n",
        encoding="utf-8",
    )

    md, summary = generate_triage_report(tmp_path, keep_last_n=1)
    rr = dict(summary.get("run_registry") or {})
    picked = dict(rr.get("last_send_bundle") or {})

    assert picked["run_id"] == "SEND_CURRENT"
    assert rr["last_send_bundle_matches_latest_path"] is True
    assert str(latest_zip.resolve()) in md


def test_desktop_animator_default_pointer_source_scans_global_and_session_pointers() -> None:
    helper_src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "pointer_paths.py").read_text(encoding="utf-8")
    app_src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
    main_src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "main.py").read_text(encoding="utf-8")
    assert "global_anim_latest_pointer_path" in helper_src
    assert "local_anim_latest_export_paths" in helper_src
    assert 'runs" / "ui_sessions"' in helper_src or "runs' / 'ui_sessions'" in helper_src
    assert "default_anim_pointer_path(PROJECT_ROOT)" in app_src
    assert "default_anim_pointer_path(" in main_src
    assert "Path(__file__).resolve().parents[2]" in main_src


def test_generate_triage_report_surfaces_road_contract_artifacts(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports_dir = workspace / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n0.1,0.01,0.02,-0.01,-0.02\n", encoding="utf-8")

    export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )

    md, summary = generate_triage_report(tmp_path, keep_last_n=1)
    anim = dict(summary.get("anim_latest") or {})

    assert anim["anim_latest_road_contract_web_ref"] == "road_contract_web.json"
    assert anim["anim_latest_road_contract_web_exists"] is True
    assert anim["anim_latest_road_contract_desktop_ref"] == "road_contract_desktop.json"
    assert anim["anim_latest_road_contract_desktop_exists"] is True
    assert "anim_latest_road_contract_web" in md
    assert "anim_latest_road_contract_desktop" in md
