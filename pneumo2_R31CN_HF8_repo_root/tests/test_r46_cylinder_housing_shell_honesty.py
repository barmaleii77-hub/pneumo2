from __future__ import annotations

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    cylinder_dead_lengths_from_contract,
    cylinder_visual_state_from_packaging,
)


def test_cylinder_visual_state_exposes_transparent_housing_shell_until_gland_point_contract_exists() -> None:
    dead_cap, dead_rod = cylinder_dead_lengths_from_contract(bore_d_m=0.05, rod_d_m=0.014, dead_vol_m3=1.5e-5)
    assert dead_cap is not None and dead_rod is not None
    top = np.array([0.0, 0.0, 0.0], dtype=float)
    bot = np.array([0.0, 0.14, 0.0], dtype=float)
    st = cylinder_visual_state_from_packaging(
        top_xyz=top,
        bot_xyz=bot,
        stroke_pos_m=0.125,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        outer_d_m=0.056,
        dead_cap_len_m=float(dead_cap),
        dead_rod_len_m=float(dead_rod),
    )
    assert st is not None
    assert 'housing_seg' in st
    housing = st['housing_seg']
    body = st['body_seg']
    rod = st['rod_seg']
    piston = np.asarray(st['piston_center'], dtype=float)
    assert np.allclose(np.asarray(housing[0], dtype=float), top)
    assert np.allclose(np.asarray(housing[1], dtype=float), bot)
    assert np.allclose(np.asarray(body[0], dtype=float), top)
    assert np.allclose(np.asarray(body[1], dtype=float), piston)
    assert np.allclose(np.asarray(rod[0], dtype=float), piston)
    assert np.allclose(np.asarray(rod[1], dtype=float), bot)
