from __future__ import annotations

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import road_grid_rows_from_s_nodes


def _max_distance_to_spacing_lattice(values: np.ndarray, spacing: float) -> float:
    values = np.asarray(values, dtype=float).reshape(-1)
    if values.size == 0:
        return 0.0
    mod = np.mod(values, spacing)
    return float(np.max(np.minimum(mod, spacing - mod)))


def test_road_grid_rows_are_world_anchored_instead_of_window_anchored() -> None:
    spacing = 2.0
    s_a = np.linspace(10.0, 22.0, 121, dtype=float)
    s_b = np.linspace(10.3, 22.3, 121, dtype=float)

    rows_a = road_grid_rows_from_s_nodes(s_nodes=s_a, cross_spacing_m=spacing, anchor_s_m=0.0)
    rows_b = road_grid_rows_from_s_nodes(s_nodes=s_b, cross_spacing_m=spacing, anchor_s_m=0.0)

    chosen_a = s_a[rows_a]
    chosen_b = s_b[rows_b]
    # Ignore the mandatory trailing boundary row; test only interior world-anchored bars.
    interior_a = chosen_a[(chosen_a > s_a[0] + 0.25) & (chosen_a < s_a[-1] - 0.25)]
    interior_b = chosen_b[(chosen_b > s_b[0] + 0.25) & (chosen_b < s_b[-1] - 0.25)]

    assert interior_a.size >= 4
    assert interior_b.size >= 4
    ds_a = float(np.max(np.diff(s_a)))
    ds_b = float(np.max(np.diff(s_b)))
    assert _max_distance_to_spacing_lattice(interior_a, spacing) <= ds_a + 1e-9
    assert _max_distance_to_spacing_lattice(interior_b, spacing) <= ds_b + 1e-9
    common = min(len(interior_a), len(interior_b))
    # A shifted window should keep the same world-anchored cross-bar phase.
    assert np.allclose(interior_a[:common], interior_b[:common], atol=max(ds_a, ds_b) + 1e-9)

    naive_stride_b = int(max(1, round(spacing / ds_b)))
    naive_rows_b = np.arange(0, len(s_b), naive_stride_b, dtype=int)
    naive_b = s_b[naive_rows_b]
    naive_b = naive_b[(naive_b > s_b[0] + 0.25) & (naive_b < s_b[-1] - 0.25)]
    common_naive = min(common, len(naive_b))
    # The anchored rows must differ from a window-anchored "start from row 0" policy.
    assert np.max(np.abs(interior_b[:common_naive] - naive_b[:common_naive])) >= 0.2
