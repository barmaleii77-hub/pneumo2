from __future__ import annotations

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    _road_crossbar_line_pairs,
    _road_longitudinal_line_pairs,
    polyline_line_segments,
    regular_grid_submesh,
    road_edge_line_segments,
    road_display_counts_from_view,
    road_grid_line_segments,
    road_surface_grid_from_profiles,
    grid_faces_rect,
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


def test_road_display_counts_keep_surface_topology_in_stable_buckets() -> None:
    args = dict(
        visible_length_m=62.0,
        viewport_width_px=1280,
        viewport_height_px=720,
        min_long=220,
        max_long=600,
        min_lat=7,
        max_lat=15,
    )
    n_long_a, n_lat_a, _, _ = road_display_counts_from_view(raw_point_count=497, **args)
    n_long_b, n_lat_b, _, _ = road_display_counts_from_view(raw_point_count=511, **args)

    assert n_long_a == n_long_b
    assert n_long_a % 32 == 0 or n_long_a in (220, 600)
    assert n_lat_a == n_lat_b


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


def test_grid_faces_rect_reuses_cached_topology_for_same_shape() -> None:
    faces_a = grid_faces_rect(9, 7)
    faces_b = grid_faces_rect(9, 7)
    assert faces_a is faces_b
    assert faces_a.flags.writeable is False


def test_road_line_pair_helpers_reuse_cached_topology_for_same_shape() -> None:
    rails_a = _road_longitudinal_line_pairs(10, 7, 2)
    rails_b = _road_longitudinal_line_pairs(10, 7, 2)
    cross_a = _road_crossbar_line_pairs(10, 7, (0, 3, 9))
    cross_b = _road_crossbar_line_pairs(10, 7, (0, 3, 9))
    assert rails_a is rails_b
    assert cross_a is cross_b
    assert rails_a.flags.writeable is False
    assert cross_a.flags.writeable is False


def test_road_longitudinal_line_pairs_can_exclude_outer_edge_rails() -> None:
    rails_with_edges = _road_longitudinal_line_pairs(6, 5, 2, True)
    rails_without_edges = _road_longitudinal_line_pairs(6, 5, 2, False)
    assert rails_without_edges.shape[0] < rails_with_edges.shape[0]
    assert rails_without_edges.flags.writeable is False


def test_road_grid_line_segments_honor_explicit_crossbar_rows() -> None:
    x = np.linspace(0.0, 5.0, 6)
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
    segs = road_grid_line_segments(
        vertices_xyz=verts,
        n_long=6,
        n_lat=5,
        include_longitudinal=False,
        include_crossbars=True,
        row_indices=np.asarray([4, 1, 4], dtype=np.int32),
        force_last_crossbar=False,
    )
    assert segs.shape == (2 * (5 - 1) * 2, 3)
    assert np.allclose(np.unique(np.round(segs[:, 0], 6)), np.asarray([1.0, 4.0], dtype=float))


def test_road_grid_line_segments_can_skip_outer_longitudinal_edges() -> None:
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
    rails_with_edges = road_grid_line_segments(
        vertices_xyz=verts,
        n_long=6,
        n_lat=5,
        include_longitudinal=True,
        include_crossbars=False,
        include_outer_longitudinal=True,
    )
    rails_without_edges = road_grid_line_segments(
        vertices_xyz=verts,
        n_long=6,
        n_lat=5,
        include_longitudinal=True,
        include_crossbars=False,
        include_outer_longitudinal=False,
    )
    assert rails_without_edges.shape[0] < rails_with_edges.shape[0]


def test_polyline_line_segments_do_not_create_closing_join() -> None:
    pts = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ],
        dtype=float,
    )
    segs = polyline_line_segments(pts)
    np.testing.assert_allclose(
        segs,
        np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
            ],
            dtype=float,
        ),
    )


def test_road_edge_line_segments_keep_left_and_right_edges_separate() -> None:
    left = np.asarray(
        [
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
            [2.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    right = np.asarray(
        [
            [0.0, -1.0, 0.0],
            [1.0, -1.0, 0.0],
            [2.0, -1.0, 0.0],
        ],
        dtype=float,
    )
    segs = road_edge_line_segments(left, right)
    assert segs.shape == (8, 3)
    np.testing.assert_allclose(segs[0], left[0])
    np.testing.assert_allclose(segs[1], left[1])
    np.testing.assert_allclose(segs[2], left[1])
    np.testing.assert_allclose(segs[3], left[2])
    np.testing.assert_allclose(segs[4], right[0])
    np.testing.assert_allclose(segs[5], right[1])
