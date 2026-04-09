from __future__ import annotations

import json
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

    zip_path = make_send_bundle(repo_root=ROOT, out_dir=out_dir, keep_last_n=1, max_file_mb=20)
    latest_zip = out_dir / "latest_send_bundle.zip"
    assert latest_zip.exists()

    with zipfile.ZipFile(zip_path, "r") as z:
        names = set(z.namelist())
        assert "triage/triage_report.json" in names
        assert "health/health_report.json" in names
        triage_main = z.read("triage/triage_report.json")
        triage_json = json.loads(triage_main.decode("utf-8", errors="replace"))
        health = json.loads(z.read("health/health_report.json").decode("utf-8", errors="replace"))

    artifacts = dict((health.get("signals") or {}).get("artifacts") or {})
    mnemo = dict((health.get("signals") or {}).get("mnemo_event_log") or {})
    assert artifacts.get("triage_report") is True
    assert artifacts.get("validation_report") is True
    assert artifacts.get("anim_diagnostics") is True
    assert triage_json["mnemo_event_log"]["severity"] == "critical"
    assert mnemo["severity"] == "critical"
    assert mnemo["current_mode"] == "Регуляторный коридор"

    with zipfile.ZipFile(latest_zip, "r") as z:
        latest_names = set(z.namelist())
        assert "triage/triage_report.json" in latest_names
        assert "health/health_report.json" in latest_names
        assert z.read("triage/triage_report.json") == triage_main
