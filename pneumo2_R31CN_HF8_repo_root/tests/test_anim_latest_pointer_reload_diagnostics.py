from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.visual_contract import build_visual_reload_diagnostics
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols


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


def test_build_visual_reload_diagnostics_reports_npz_and_road_csv(tmp_path: Path) -> None:
    npz_path = tmp_path / "bundle.npz"
    npz_path.write_bytes(b"npz placeholder")
    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n", encoding="utf-8")

    diag = build_visual_reload_diagnostics(
        npz_path,
        meta={"road_csv": "road.csv"},
        context="pytest pointer diag",
    )

    assert diag["visual_cache_token"]
    assert diag["inputs"] == ["npz", "road_csv"]
    deps = dict(diag["visual_cache_dependencies"])
    assert deps["road_csv_path"] == str(road_csv.resolve())
    assert dict(deps["road_csv"])["exists"] is True


def test_export_anim_latest_pointer_contains_visual_reload_diagnostics(tmp_path: Path) -> None:
    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n0.1,0.01,0.02,-0.01,-0.02\n", encoding="utf-8")

    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=tmp_path,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )

    pointer = json.loads(ptr_path.read_text(encoding="utf-8"))
    trace = json.loads((tmp_path / "anim_latest_trace.json").read_text(encoding="utf-8"))

    assert npz_path.exists()
    assert pointer["updated_utc"]
    assert pointer["npz_path"] == str(npz_path.resolve())
    assert pointer["meta"]["road_csv"] == "anim_latest_road_csv.csv"
    assert pointer["visual_cache_token"]
    assert pointer["visual_reload_inputs"] == ["npz", "road_csv"]

    deps = dict(pointer["visual_cache_dependencies"])
    assert deps["road_csv_path"] == str((tmp_path / "anim_latest_road_csv.csv").resolve())
    assert dict(deps["road_csv"])["exists"] is True

    assert trace["pointer"]["visual_cache_token"] == pointer["visual_cache_token"]
    assert trace["visual_reload_diagnostics"]["visual_cache_token"] == pointer["visual_cache_token"]
    assert trace["visual_reload_diagnostics"]["inputs"] == ["npz", "road_csv"]


def test_pointer_status_sources_reference_visual_reload_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    app_text = (root / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    page_text = (root / "pneumo_solver_ui" / "pages/08_DesktopAnimator.py").read_text(encoding="utf-8")

    assert '"visual_cache_token"' in app_text
    assert '"visual_cache_dependencies"' in app_text
    assert '"visual_reload_inputs"' in app_text

    assert 'obj.get("visual_cache_token", "")' in page_text
    assert 'obj.get("visual_reload_inputs", [])' in page_text
    assert 'obj.get("visual_cache_dependencies", {})' in page_text
