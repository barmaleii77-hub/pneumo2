import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle, export_full_log_to_npz
from pneumo_solver_ui.solver_points_contract import (
    CORNERS,
    POINT_KINDS,
    assert_required_solver_points_contract,
    point_cols,
)


def _geom_meta() -> dict:
    return {"geometry": {"wheelbase_m": 2.8, "track_m": 1.6}}


def _solver_df() -> pd.DataFrame:
    data: dict[str, list[float]] = {"время_с": [0.0, 0.1]}
    seed = 0.0
    for kind in POINT_KINDS:
        for corner in CORNERS:
            for axis_i, col in enumerate(point_cols(kind, corner)):
                base = seed + float(axis_i)
                data[col] = [base, base + 0.01]
            seed += 0.1
    return pd.DataFrame(data)


def test_assert_required_solver_points_contract_rejects_missing_triplets() -> None:
    df = pd.DataFrame({"время_с": [0.0], point_cols("arm_pivot", "ЛП")[0]: [0.0]})
    with pytest.raises(ValueError, match="solver-point contract failed"):
        assert_required_solver_points_contract(df, context="pytest solver gate")


def test_export_full_log_to_npz_optional_solver_gate_rejects_missing_triplets(tmp_path: Path) -> None:
    df_main = pd.DataFrame({"время_с": [0.0]})
    with pytest.raises(ValueError, match="solver-point contract failed"):
        export_full_log_to_npz(
            tmp_path / "broken_full_log.npz",
            df_main,
            meta=_geom_meta(),
            require_solver_points_contract=True,
        )


def test_export_anim_latest_bundle_rejects_missing_solver_points(tmp_path: Path) -> None:
    df_main = pd.DataFrame({"время_с": [0.0]})
    with pytest.raises(ValueError, match="solver-point contract failed"):
        export_anim_latest_bundle(
            exports_dir=tmp_path,
            df_main=df_main,
            meta=_geom_meta(),
        )
    assert not (tmp_path / "anim_latest.npz").exists()
    assert not (tmp_path / "anim_latest.json").exists()


def test_export_anim_latest_bundle_accepts_valid_solver_points_and_geometry(tmp_path: Path) -> None:
    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=tmp_path,
        df_main=_solver_df(),
        meta=_geom_meta(),
    )
    assert npz_path.exists()
    assert ptr_path.exists()
    with np.load(npz_path, allow_pickle=True) as data:
        meta = json.loads(str(data["meta_json"].item()))
    assert meta["geometry"]["wheelbase_m"] == 2.8
    assert meta["geometry"]["track_m"] == 1.6


def test_legacy_app_fallback_keeps_solver_gate() -> None:
    text = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    assert "assert_required_solver_points_contract" in text
    assert "require_solver_points_contract=True" in text
