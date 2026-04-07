from __future__ import annotations

import numpy as np
from pathlib import Path

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    road_grid_target_s_values_from_range,
    road_native_support_s_values_from_axis,
    stable_road_surface_spacing_from_view,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_stable_road_surface_spacing_is_bundle_view_stable() -> None:
    s1 = stable_road_surface_spacing_from_view(
        nominal_visible_length_m=64.8,
        viewport_width_px=1280,
        min_long=180,
        max_long=720,
    )
    s2 = stable_road_surface_spacing_from_view(
        nominal_visible_length_m=64.8,
        viewport_width_px=1280,
        min_long=180,
        max_long=720,
    )
    s3 = stable_road_surface_spacing_from_view(
        nominal_visible_length_m=64.8,
        viewport_width_px=640,
        min_long=180,
        max_long=720,
    )
    assert np.isclose(s1, s2)
    assert s1 > 0.0
    assert s3 > 0.0
    assert not np.isclose(s1, s3)


def test_world_anchored_surface_nodes_keep_interior_spacing_constant() -> None:
    spacing = stable_road_surface_spacing_from_view(
        nominal_visible_length_m=64.8,
        viewport_width_px=1280,
        min_long=180,
        max_long=720,
    )
    s_nodes = road_grid_target_s_values_from_range(
        s_min_m=10.3,
        s_max_m=45.7,
        cross_spacing_m=spacing,
        anchor_s_m=0.0,
        include_last=False,
    )
    if s_nodes.size > 3:
        diffs = np.diff(s_nodes)
        assert diffs.size > 0
        assert np.allclose(diffs, diffs[0])


def test_native_support_rows_are_bundle_stable_and_not_window_local_resampling() -> None:
    support = np.arange(0.0, 100.0, 0.1, dtype=float)
    a = road_native_support_s_values_from_axis(
        support_s_m=support,
        s_min_m=10.2,
        s_max_m=18.7,
        stride_rows=5,
        extra_rows_each_side=1,
    )
    b = road_native_support_s_values_from_axis(
        support_s_m=support,
        s_min_m=10.45,
        s_max_m=18.95,
        stride_rows=5,
        extra_rows_each_side=1,
    )
    assert a.size >= 4
    assert b.size >= 4
    # Same support axis + same stride must keep the same native lattice phase.
    assert np.allclose(np.diff(a), np.diff(a)[0])
    assert np.allclose(np.diff(b), np.diff(b)[0])
    common = min(a.size, b.size)
    assert np.allclose(a[:common], b[:common], atol=0.5)


def test_desktop_animator_source_uses_native_support_rows_and_cached_world_normals() -> None:
    assert "road_native_support_s_values_from_axis as _road_native_support_s_values_from_axis" in APP
    assert "surface_stride_rows = int(max(1, round(surface_spacing_m / native_step_m)))" in APP
    assert "s_nodes = _road_native_support_s_values_from_axis(" in APP
    assert "stable native support rows instead of from a fresh" in APP
    assert "self._road_path_s_world_cache" in APP
    assert "self._road_path_nx_world_cache" in APP
    assert "window size / visible range" in APP
