from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pneumo_solver_ui.data_contract import assert_required_geometry_meta, collect_geometry_contract_issues
from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.self_checks import run_self_checks
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols


def _mini_df() -> pd.DataFrame:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data = {
        "время_с": t,
        "перемещение_рамы_z_м": np.array([0.5, 0.5, 0.5], dtype=float),
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


def test_collect_geometry_contract_issues_flags_missing_required_nested_geometry() -> None:
    issues = collect_geometry_contract_issues({}, require_nested=True, require_required=True, context="test meta")
    assert issues
    assert any("nested object 'geometry'" in m for m in issues)

    with pytest.raises(ValueError):
        assert_required_geometry_meta({}, context="test meta", require_nested=True)


def test_export_anim_latest_bundle_rejects_missing_geometry(tmp_path: Path) -> None:
    df = _mini_df()
    with pytest.raises(ValueError):
        export_anim_latest_bundle(
            exports_dir=tmp_path,
            df_main=df,
            meta={"source": "pytest"},
        )


def test_load_npz_and_selfcheck_fail_without_required_geometry(tmp_path: Path) -> None:
    df = _mini_df()
    npz_path = tmp_path / "broken_bundle.npz"
    np.savez_compressed(
        npz_path,
        main_cols=np.array(list(df.columns), dtype=object),
        main_values=df.to_numpy(dtype=float),
        meta_json=np.array(json.dumps({"source": "pytest"}, ensure_ascii=False), dtype=str),
    )

    b = load_npz(npz_path)
    rep = run_self_checks(b, wheel_radius_m=0.3, track_m=0.0, wheelbase_m=0.0)

    assert b.contract_issues
    assert any("geometry" in m for m in b.contract_issues)
    assert rep.level == "FAIL"
    assert any("meta_json.geometry" in str(m) for m in rep.messages)


def test_export_anim_latest_bundle_accepts_valid_nested_geometry(tmp_path: Path) -> None:
    df = _mini_df()
    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=tmp_path,
        df_main=df,
        meta={
            "source": "pytest",
            "geometry": {
                "wheelbase_m": 2.8,
                "track_m": 1.6,
                "wheel_radius_front_m": 0.31,
                "wheel_radius_rear_m": 0.31,
            },
        },
    )

    assert npz_path.exists()
    assert ptr_path.exists()

    b = load_npz(npz_path)
    rep = run_self_checks(b, wheel_radius_m=0.31, track_m=1.6, wheelbase_m=2.8)

    assert not b.contract_issues
    assert rep.ok
