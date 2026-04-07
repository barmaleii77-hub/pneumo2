from __future__ import annotations

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import road_surface_grid_from_profiles


def test_road_surface_build_faces_false_skips_topology_rebuild() -> None:
    n = 8
    x = np.linspace(0.0, 5.0, n)
    y = np.zeros_like(x)
    zl = np.linspace(0.0, 0.01, n)
    zc = np.linspace(0.0, 0.0, n)
    zr = np.linspace(0.0, -0.01, n)
    nx = np.zeros_like(x)
    ny = np.ones_like(x)

    verts, faces, lat = road_surface_grid_from_profiles(
        x_center=x,
        y_center=y,
        z_left=zl,
        z_center=zc,
        z_right=zr,
        normal_x=nx,
        normal_y=ny,
        half_width_m=1.0,
        lateral_count=7,
        build_faces=False,
    )

    assert verts.shape == (n * 7, 3)
    assert faces.shape == (0, 3)
    assert lat.shape == (7,)
