from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    car_frame_rotate_xy,
    center_and_orient_cylinder_vertices_to_y,
    localize_world_points_to_car_frame,
    orient_centered_cylinder_vertices_to_y,
    orthonormal_frame_from_corners,
)


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py'


def test_localize_world_points_to_car_frame_preserves_canonical_xyz_semantics() -> None:
    # Canonical car basis: x forward, y left, z up.
    yaw = math.radians(30.0)
    x0, y0 = 10.0, -4.0

    # Construct four wheel centers in local car frame, rotate into world and back.
    local = np.array([
        [0.75, 0.50, 0.31],
        [0.75, -0.50, 0.29],
        [-0.75, 0.50, 0.32],
        [-0.75, -0.50, 0.28],
    ], dtype=float)
    c = math.cos(yaw)
    s = math.sin(yaw)
    world = np.empty_like(local)
    world[:, 0] = x0 + c * local[:, 0] - s * local[:, 1]
    world[:, 1] = y0 + s * local[:, 0] + c * local[:, 1]
    world[:, 2] = local[:, 2]

    restored = localize_world_points_to_car_frame(world, x0=x0, y0=y0, yaw_rad=yaw)
    assert np.allclose(restored, local, atol=1e-9)


def test_car_frame_rotate_xy_matches_expected_left_right_sign() -> None:
    # Positive local +Y must remain 'left'.
    yaw = math.radians(45.0)
    x_local = np.array([0.75, 0.75], dtype=float)
    y_local = np.array([0.50, -0.50], dtype=float)
    c = math.cos(yaw)
    s = math.sin(yaw)
    x_world = c * x_local - s * y_local
    y_world = s * x_local + c * y_local

    rx, ry = car_frame_rotate_xy(x_world, y_world, yaw)
    assert np.allclose(rx, x_local, atol=1e-9)
    assert np.allclose(ry, y_local, atol=1e-9)


def test_orthonormal_frame_from_corners_recovers_center_and_up_axis() -> None:
    lp = np.array([+0.75, +0.50, 0.31], dtype=float)
    pp = np.array([+0.75, -0.50, 0.29], dtype=float)
    lz = np.array([-0.75, +0.50, 0.32], dtype=float)
    pz = np.array([-0.75, -0.50, 0.28], dtype=float)

    center, R = orthonormal_frame_from_corners(lp, pp, lz, pz)

    assert center.shape == (3,)
    assert np.allclose(center, np.array([0.0, 0.0, 0.30]), atol=0.03)
    # X axis points forward, Y left, Z up.
    assert R.shape == (3, 3)
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-9)
    assert float(R[0, 0]) > 0.9
    assert float(R[1, 1]) > 0.9
    assert float(R[2, 2]) > 0.9


def test_center_and_orient_cylinder_vertices_to_y_recenters_axis_without_runtime_rotate() -> None:
    # Simulate MeshData.cylinder() convention: axis Z in [0..L].
    v = np.array([
        [0.1, 0.0, 0.0],
        [-0.1, 0.0, 0.0],
        [0.1, 0.0, 0.22],
        [-0.1, 0.0, 0.22],
    ], dtype=float)
    out = center_and_orient_cylinder_vertices_to_y(v, length_m=0.22)

    # Axis must be centered on Y after conversion: [-L/2, +L/2].
    assert np.isclose(out[:, 1].min(), -0.11, atol=1e-9)
    assert np.isclose(out[:, 1].max(), +0.11, atol=1e-9)
    # Z now carries former -Y; with input Y=0 it must stay 0.
    assert np.allclose(out[:, 2], 0.0, atol=1e-12)




def test_orient_centered_cylinder_vertices_to_y_keeps_centered_mesh_on_axis() -> None:
    v = np.array([
        [0.1, 0.0, -0.11],
        [-0.1, 0.0, -0.11],
        [0.1, 0.0, +0.11],
        [-0.1, 0.0, +0.11],
    ], dtype=float)
    out = orient_centered_cylinder_vertices_to_y(v)

    assert np.isclose(out[:, 1].min(), -0.11, atol=1e-9)
    assert np.isclose(out[:, 1].max(), +0.11, atol=1e-9)
    assert np.isclose(float(np.mean(out[:, 1])), 0.0, atol=1e-12)

def test_app_source_uses_solver_points_and_no_runtime_wheel_rotate_in_update_frame() -> None:
    src = APP_SOURCE.read_text(encoding='utf-8')
    assert 'wheel_center_xyz' in src
    assert 'road_contact_xyz' in src
    assert 'frame_corner_xyz' in src
    assert 'center_and_orient_cylinder_vertices_to_y' in src
    assert 'w.rotate(90.0, 1, 0, 0)' not in src
