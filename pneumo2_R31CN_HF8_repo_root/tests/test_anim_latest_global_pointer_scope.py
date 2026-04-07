from __future__ import annotations

import json
import importlib
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.run_artifacts import latest_animation_ptr_path, load_latest_animation_ptr, _workspace_dir
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


def test_export_anim_latest_bundle_does_not_poison_global_pointer_for_adhoc_exports(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports_dir = tmp_path / "adhoc_exports"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    global_ptr = latest_animation_ptr_path()
    if global_ptr.exists():
        global_ptr.unlink()

    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n", encoding="utf-8")

    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )

    assert npz_path.exists()
    assert ptr_path.exists()
    assert not global_ptr.exists()
    assert load_latest_animation_ptr() is None


def test_export_anim_latest_bundle_auto_mirrors_only_for_workspace_exports(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports_dir = workspace / "exports"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n", encoding="utf-8")

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
    global_info = load_latest_animation_ptr()
    assert global_info is not None
    assert global_info["pointer_json"] == str(ptr_path.resolve())
    assert global_info["npz_path"] == str(npz_path.resolve())
    assert global_info["visual_cache_token"] == pointer["visual_cache_token"]


def test_workspace_env_short_circuits_optional_config_import(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    real_import_module = importlib.import_module

    def _guard(name: str, package: str | None = None):
        if name == "pneumo_solver_ui.config":
            raise AssertionError("optional config import must not happen when PNEUMO_WORKSPACE_DIR is set")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _guard)
    got = _workspace_dir()
    assert got == workspace.resolve()
