from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.data_bundle import load_npz


def test_animator_road_profile_bins_near_overlap_instead_of_zigzag(tmp_path: Path) -> None:
    t = np.asarray([0.0, 1.0, 2.000001, 3.000001], dtype=float)
    vals = np.column_stack(
        [
            t,
            np.ones_like(t),  # скорость_vx_м_с
            np.asarray([0.10, 0.10, 0.10, 0.10], dtype=float),  # дорога_ЛП_м
            np.asarray([-0.10, -0.10, -0.10, -0.10], dtype=float),  # дорога_ЛЗ_м
            np.asarray([0.05, 0.05, 0.05, 0.05], dtype=float),  # дорога_ПП_м
            np.asarray([-0.05, -0.05, -0.05, -0.05], dtype=float),  # дорога_ПЗ_м
        ]
    )
    cols = [
        "время_с",
        "скорость_vx_м_с",
        "дорога_ЛП_м",
        "дорога_ЛЗ_м",
        "дорога_ПП_м",
        "дорога_ПЗ_м",
    ]
    meta = {"geometry": {"wheelbase_m": 2.0}}
    npz_path = tmp_path / "road_overlap.npz"
    np.savez(
        npz_path,
        main_cols=np.asarray(cols, dtype=object),
        main_values=np.asarray(vals, dtype=float),
        meta_json=json.dumps(meta, ensure_ascii=False),
    )

    bundle = load_npz(npz_path)
    s_left, z_left = bundle.ensure_road_profile(mode="left")

    ds = np.diff(np.asarray(s_left, dtype=float))
    dz = np.diff(np.asarray(z_left, dtype=float))

    # The reconstructed service profile must no longer keep near-zero ds with a huge z jump.
    assert float(ds.min()) >= 0.49
    assert float(np.max(np.abs(dz))) <= 0.100001
