from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.run_registry import log_send_bundle_created
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols
from pneumo_solver_ui.tools.make_send_bundle import _collect_anim_latest_bundle_diagnostics


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



def _prepare_anim_export(tmp_path: Path, monkeypatch) -> tuple[Path, Path, dict]:
    workspace_dir = tmp_path / "workspace"
    exports_dir = workspace_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))

    road_csv = tmp_path / "road.csv"
    road_csv.write_text(
        "t,z0,z1,z2,z3\n"
        "0,0,0,0,0\n"
        "0.1,0.01,0.02,-0.01,-0.02\n",
        encoding="utf-8",
    )

    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )
    pointer = json.loads(ptr_path.read_text(encoding="utf-8"))
    return npz_path, ptr_path, pointer



def test_collect_anim_latest_bundle_diagnostics_writes_sidecars(tmp_path: Path, monkeypatch) -> None:
    npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)

    diag, md = _collect_anim_latest_bundle_diagnostics(tmp_path)

    assert diag["anim_latest_available"] is True
    assert diag["anim_latest_pointer_json"] == str(ptr_path.resolve())
    assert diag["anim_latest_npz_path"] == str(npz_path.resolve())
    assert diag["anim_latest_visual_cache_token"] == pointer["visual_cache_token"]
    assert diag["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert (tmp_path / "latest_anim_pointer_diagnostics.json").exists()
    assert (tmp_path / "latest_anim_pointer_diagnostics.md").exists()
    assert pointer["visual_cache_token"] in md



def test_run_registry_send_bundle_created_accepts_extended_anim_fields(tmp_path: Path, monkeypatch) -> None:
    _npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)
    diag = collect_anim_latest_diagnostics_summary(include_meta=True)

    runs_root = tmp_path / "runs"
    monkeypatch.setattr("pneumo_solver_ui.run_registry._runs_root", lambda: runs_root)

    zip_path = tmp_path / "bundle.zip"
    zip_path.write_bytes(b"zip bytes")
    dashboard_html = tmp_path / "latest_dashboard.html"
    dashboard_html.write_text("<html></html>", encoding="utf-8")

    log_send_bundle_created(
        zip_path=zip_path,
        latest_zip_path=tmp_path / "latest_send_bundle.zip",
        sha256="abc123",
        size_bytes=123,
        release="pytest-release",
        primary_session_dir=tmp_path / "session",
        validation_ok=True,
        validation_errors=0,
        validation_warnings=1,
        dashboard_created=True,
        dashboard_html_path=dashboard_html,
        env={"PNEUMO_RUN_ID": "PYTEST"},
        **diag,
    )

    lines = (runs_root / "run_registry.jsonl").read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[-1])

    assert rec["event"] == "send_bundle_created"
    assert rec["zip_path"] == str(zip_path)
    assert rec["latest_zip_path"].endswith("latest_send_bundle.zip")
    assert rec["dashboard_created"] is True
    assert rec["anim_latest_pointer_json"] == str(ptr_path.resolve())
    assert rec["anim_latest_visual_cache_token"] == pointer["visual_cache_token"]
    assert rec["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert rec["anim_latest_available"] is True
    assert rec["anim_latest_global_pointer_json"].endswith("workspace/_pointers/anim_latest.json")



def test_sources_wire_anim_diagnostics_into_launcher_and_send_bundle() -> None:
    bundle_text = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    gui_text = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(encoding="utf-8")
    launcher_text = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8")

    assert '("_pointers", False)' in bundle_text
    assert 'latest_anim_pointer_diagnostics.json' in bundle_text
    assert '**anim_diag_event' in bundle_text
    assert 'collect_anim_latest_diagnostics_summary' in launcher_text
    assert 'send_results_gui_spawned' in launcher_text
    assert 'latest_anim_pointer_diagnostics.json' in gui_text
    assert 'Anim latest token:' in gui_text
