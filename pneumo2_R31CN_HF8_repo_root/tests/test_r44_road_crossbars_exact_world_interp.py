from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    road_crossbar_line_segments_from_profiles,
    road_grid_target_s_values_from_range,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_road_grid_target_s_values_are_world_anchored_without_forced_edge_bar() -> None:
    targets = road_grid_target_s_values_from_range(
        s_min_m=0.2,
        s_max_m=3.1,
        cross_spacing_m=1.0,
        anchor_s_m=0.0,
        include_last=False,
    )
    assert np.allclose(targets, np.asarray([1.0, 2.0, 3.0], dtype=float))


def test_road_crossbar_segments_are_sampled_at_exact_target_s_values() -> None:
    s_nodes = np.linspace(0.0, 10.0, 11)
    x_center = s_nodes.copy()
    y_center = np.zeros_like(s_nodes)
    z_left = np.zeros_like(s_nodes)
    z_center = np.zeros_like(s_nodes)
    z_right = np.zeros_like(s_nodes)
    normal_x = np.zeros_like(s_nodes)
    normal_y = np.ones_like(s_nodes)
    targets = np.asarray([1.25, 4.75], dtype=float)
    segs = road_crossbar_line_segments_from_profiles(
        s_targets_m=targets,
        s_nodes_m=s_nodes,
        x_center=x_center,
        y_center=y_center,
        z_left=z_left,
        z_center=z_center,
        z_right=z_right,
        normal_x=normal_x,
        normal_y=normal_y,
        half_width_m=0.5,
        lateral_count=5,
    )
    assert segs.shape == (2 * (5 - 1) * len(targets), 3)
    x_vals = np.unique(np.round(segs[:, 0], 6))
    assert np.allclose(x_vals, targets)


def test_car3d_uses_exact_world_target_crossbars_from_stable_support_rows() -> None:
    assert "road_grid_target_s_values_from_range as _road_grid_target_s_values_from_range" in APP
    assert "road_native_support_s_values_from_axis as _road_native_support_s_values_from_axis" in APP
    assert "road_crossbar_line_segments_from_profiles as _road_crossbar_line_segments_from_profiles" in APP
    assert "include_last=False" in APP
    assert "include_crossbars=False" in APP
    assert "grid_stride_rows = int(max(1, round(float(grid_cross_spacing_m) / native_step_m)))" in APP
    assert "grid_target_s = _road_native_support_s_values_from_axis(" in APP
    assert "cross_lines = _road_crossbar_line_segments_from_profiles(" in APP
