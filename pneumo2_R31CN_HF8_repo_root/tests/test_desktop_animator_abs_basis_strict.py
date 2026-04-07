from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.run_self_checks import _road_profile_quick_check
from pneumo_solver_ui.desktop_animator.self_checks import run_self_checks


CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _write_npz(tmp_path: Path, cols: list[str], values: list[np.ndarray], meta: dict | None = None) -> Path:
    npz_path = tmp_path / "bundle.npz"
    np.savez_compressed(
        npz_path,
        main_cols=np.array(cols, dtype=object),
        main_values=np.column_stack(values).astype(float),
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    return npz_path


def test_data_bundle_does_not_implicitly_substitute_rel0_into_abs_path(tmp_path: Path) -> None:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    z_rel0 = np.array([0.0, 0.02, -0.01], dtype=float)
    npz_path = _write_npz(
        tmp_path,
        cols=["время_с", "перемещение_рамы_z_м_rel0"],
        values=[t, z_rel0],
        meta={"geometry": {"wheelbase_m": 2.8, "track_m": 1.6}},
    )

    b = load_npz(npz_path)

    assert b.get("перемещение_рамы_z_м", default=None) is None
    assert np.allclose(b.get("перемещение_рамы_z_м", default=-7.0), np.full(t.shape, -7.0))
    assert np.allclose(b.get_abs("перемещение_рамы_z_м", default=-3.0), np.full(t.shape, -3.0))
    assert np.allclose(b.get_rel0("перемещение_рамы_z_м"), z_rel0)


def test_self_checks_fail_on_rel0_only_geometry_contract(tmp_path: Path) -> None:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    cols = ["время_с", "скорость_vx_м_с", "yaw_рад", "перемещение_рамы_z_м_rel0"]
    values = [t, np.full_like(t, 10.0), np.zeros_like(t), np.array([0.0, 0.01, -0.01], dtype=float)]

    for c in CORNERS:
        cols.extend([
            f"дорога_{c}_м_rel0",
            f"перемещение_колеса_{c}_м_rel0",
            f"рама_угол_{c}_z_м_rel0",
        ])
        values.extend([
            np.array([0.0, 0.001, 0.0], dtype=float),
            np.array([0.0, 0.301, 0.299], dtype=float),
            np.array([0.0, 0.011, -0.009], dtype=float),
        ])

    npz_path = _write_npz(
        tmp_path,
        cols=cols,
        values=values,
        meta={"geometry": {"wheelbase_m": 2.8, "track_m": 1.6, "wheel_radius_m": 0.3}},
    )

    b = load_npz(npz_path)
    rep = run_self_checks(b, wheel_radius_m=0.3, track_m=1.6, wheelbase_m=2.8)

    assert rep.level == "FAIL"
    assert any("отсутствуют ABS-каналы геометрии" in msg for msg in rep.messages)
    assert b.get("перемещение_колеса_ЛП_м", default=None) is None
    assert np.allclose(b.get_abs("дорога_ЛП_м", default=-1.0), np.full(t.shape, -1.0))


def test_self_checks_accept_sidecar_road_without_false_abs_failure(tmp_path: Path) -> None:
    t = np.array([0.0, 0.1, 0.2, 0.3], dtype=float)
    cols = ["время_с", "скорость_vx_м_с", "yaw_рад", "перемещение_рамы_z_м"]
    values = [t, np.full_like(t, 8.0), np.zeros_like(t), np.array([0.50, 0.505, 0.495, 0.50], dtype=float)]

    for c in CORNERS:
        cols.extend([
            f"перемещение_колеса_{c}_м",
            f"рама_угол_{c}_z_м",
        ])
        values.extend([
            np.array([0.30, 0.305, 0.295, 0.30], dtype=float),
            np.array([0.50, 0.505, 0.495, 0.50], dtype=float),
        ])

    road_csv = tmp_path / "road.csv"
    pd.DataFrame(
        {
            "t": t,
            "z0": np.array([0.00, 0.001, 0.002, 0.001], dtype=float),
            "z1": np.array([0.00, 0.001, 0.002, 0.001], dtype=float),
            "z2": np.array([0.00, 0.000, 0.001, 0.000], dtype=float),
            "z3": np.array([0.00, 0.000, 0.001, 0.000], dtype=float),
        }
    ).to_csv(road_csv, index=False)

    npz_path = _write_npz(
        tmp_path,
        cols=cols,
        values=values,
        meta={
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6, "wheel_radius_m": 0.3},
            "road_csv": road_csv.name,
        },
    )

    b = load_npz(npz_path)
    rep = run_self_checks(b, wheel_radius_m=0.3, track_m=1.6, wheelbase_m=2.8)

    assert not any("отсутствуют ABS-каналы геометрии" in msg for msg in rep.messages)
    assert b.road_series("ЛП", allow_sidecar=True) is not None

    report = {"level": rep.level, "messages": list(rep.messages)}
    _road_profile_quick_check(report, b, wheelbase_m=2.8)
    assert report["road_profile"]["ok"] is True
    assert "axle_fit_max_abs_err_m" in report["road_profile"]
