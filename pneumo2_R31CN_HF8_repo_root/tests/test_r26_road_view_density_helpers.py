from __future__ import annotations

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    regular_grid_submesh,
    road_display_counts_from_view,
    road_grid_line_segments,
    road_surface_grid_from_profiles,
)


def test_road_display_counts_respect_view_and_decimate_wire_grid() -> None:
    n_long, n_lat, cross_stride, lateral_stride = road_display_counts_from_view(
        visible_length_m=62.0,
        raw_point_count=1600,
        viewport_width_px=1280,
        viewport_height_px=720,
        min_long=220,
        max_long=600,
        min_lat=7,
        max_lat=15,
    )
    assert 220 <= n_long <= 600
    assert n_lat % 2 == 1
    assert cross_stride >= 1
    assert lateral_stride >= 1


def test_regular_grid_submesh_reindexes_faces_to_local_grid() -> None:
    x = np.linspace(-1.0, 1.0, 6)
    y = np.zeros_like(x)
    zl = np.zeros_like(x)
    zc = np.zeros_like(x)
    zr = np.zeros_like(x)
    nx = np.zeros_like(x)
    ny = np.ones_like(x)
    verts, _, _ = road_surface_grid_from_profiles(
        x_center=x,
        y_center=y,
        z_left=zl,
        z_center=zc,
        z_right=zr,
        normal_x=nx,
        normal_y=ny,
        half_width_m=0.5,
        lateral_count=7,
    )
    sub_verts, sub_faces = regular_grid_submesh(
        vertices_xyz=verts,
        n_long=6,
        n_lat=7,
        row_start=1,
        row_stop=5,
        col_start=0,
        col_stop=7,
    )
    assert sub_verts.shape[0] == 4 * 7
    assert sub_faces.shape[0] == (4 - 1) * (7 - 1) * 2
    assert int(np.max(sub_faces)) < sub_verts.shape[0]


def test_road_grid_line_segments_can_decimate_lateral_rails() -> None:
    x = np.linspace(-1.0, 1.0, 10)
    y = np.zeros_like(x)
    zl = np.zeros_like(x)
    zc = np.zeros_like(x)
    zr = np.zeros_like(x)
    nx = np.zeros_like(x)
    ny = np.ones_like(x)
    verts, _, _ = road_surface_grid_from_profiles(
        x_center=x,
        y_center=y,
        z_left=zl,
        z_center=zc,
        z_right=zr,
        normal_x=nx,
        normal_y=ny,
        half_width_m=0.5,
        lateral_count=9,
    )
    dense = road_grid_line_segments(vertices_xyz=verts, n_long=10, n_lat=9, cross_stride=1, lateral_stride=1)
    sparse = road_grid_line_segments(vertices_xyz=verts, n_long=10, n_lat=9, cross_stride=2, lateral_stride=3)
    assert sparse.shape[0] < dense.shape[0]


def test_road_grid_line_segments_can_emit_only_longitudinal_rails() -> None:
    x = np.linspace(-1.0, 1.0, 6)
    y = np.zeros_like(x)
    zl = np.zeros_like(x)
    zc = np.zeros_like(x)
    zr = np.zeros_like(x)
    nx = np.zeros_like(x)
    ny = np.ones_like(x)
    verts, _, _ = road_surface_grid_from_profiles(
        x_center=x,
        y_center=y,
        z_left=zl,
        z_center=zc,
        z_right=zr,
        normal_x=nx,
        normal_y=ny,
        half_width_m=0.5,
        lateral_count=5,
    )
    rails_only = road_grid_line_segments(
        vertices_xyz=verts,
        n_long=6,
        n_lat=5,
        lateral_stride=2,
        include_longitudinal=True,
        include_crossbars=False,
        force_last_crossbar=False,
    )
    # Rails: columns {0,2,4} -> 3 rails, each with (6-1) segments and 2 endpoints.
    assert rails_only.shape == (3 * (6 - 1) * 2, 3)
