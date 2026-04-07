from __future__ import annotations

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    contact_point_from_patch_faces,
    cylinder_visual_segments_from_state,
    road_patch_faces_inside_wheel_cylinder,
    road_surface_grid_from_profiles,
)


def test_road_patch_is_subset_of_surface_mesh_not_analytic_ellipse() -> None:
    x = np.linspace(-0.6, 0.6, 41)
    y = np.zeros_like(x)
    zl = np.zeros_like(x)
    zc = np.zeros_like(x)
    zr = np.zeros_like(x)
    nx = np.zeros_like(x)
    ny = np.ones_like(x)
    verts, faces, _ = road_surface_grid_from_profiles(
        x_center=x,
        y_center=y,
        z_left=zl,
        z_center=zc,
        z_right=zr,
        normal_x=nx,
        normal_y=ny,
        half_width_m=0.20,
        lateral_count=11,
    )
    patch_faces = road_patch_faces_inside_wheel_cylinder(
        vertices_xyz=verts,
        faces=faces,
        wheel_center_xyz=np.array([0.0, 0.0, 0.95], dtype=float),
        wheel_axle_xyz=np.array([0.0, 1.0, 0.0], dtype=float),
        wheel_up_xyz=np.array([0.0, 0.0, 1.0], dtype=float),
        wheel_radius_m=1.0,
        wheel_width_m=0.40,
    )
    assert patch_faces.shape[0] > 0
    cent = verts[patch_faces].mean(axis=1)
    # On a flat road + cylindrical wheel volume the selected surface patch should span the wheel width.
    y_span = float(np.max(cent[:, 1]) - np.min(cent[:, 1]))
    x_span = float(np.max(cent[:, 0]) - np.min(cent[:, 0]))
    assert y_span > 0.25
    assert x_span > 0.20
    pt = contact_point_from_patch_faces(
        vertices_xyz=verts,
        faces=patch_faces,
        wheel_center_xyz=np.array([0.0, 0.0, 0.95], dtype=float),
        wheel_up_xyz=np.array([0.0, 0.0, 1.0], dtype=float),
    )
    assert pt is not None
    assert np.isclose(pt[2], 0.0)


def test_cylinder_visual_segments_keep_piston_visible_for_short_assembly() -> None:
    body_seg, rod_seg, piston_seg = cylinder_visual_segments_from_state(
        top_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.array([0.0, 0.14, 0.0], dtype=float),
        stroke_pos_m=0.12,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        dead_vol_m3=1.5e-5,
    )
    assert body_seg is not None
    assert rod_seg is not None
    assert piston_seg is not None
    piston_center = 0.5 * (np.asarray(piston_seg[0]) + np.asarray(piston_seg[1]))
    assert 0.0 < float(piston_center[1]) < 0.14
    assert float(np.linalg.norm(np.asarray(rod_seg[1]) - np.asarray(rod_seg[0]))) > 0.0
