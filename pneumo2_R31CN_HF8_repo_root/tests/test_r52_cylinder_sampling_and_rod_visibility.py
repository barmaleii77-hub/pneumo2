from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    cylinder_visual_state_from_packaging,
    rod_centerline_vertices_from_packaging_state,
)
from pneumo_solver_ui.desktop_animator.playback_sampling import (
    lerp_point_row,
    lerp_series_value,
    sample_time_bracket,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py'


def test_sample_time_bracket_returns_fraction_inside_source_interval() -> None:
    t = np.array([0.0, 0.2, 0.4], dtype=float)
    i0, i1, alpha, ts = sample_time_bracket(t, sample_t=0.05, fallback_index=0)

    assert (i0, i1) == (0, 1)
    assert np.isclose(alpha, 0.25, atol=1e-12)
    assert np.isclose(ts, 0.05, atol=1e-12)


def test_lerp_helpers_interpolate_scalars_and_solver_points() -> None:
    scalar = np.array([10.0, 14.0], dtype=float)
    point_rows = np.array([
        [0.0, 0.0, 0.0],
        [2.0, 4.0, 6.0],
    ], dtype=float)

    v = lerp_series_value(scalar, i0=0, i1=1, alpha=0.25, default=-1.0)
    p = lerp_point_row(point_rows, i0=0, i1=1, alpha=0.25)

    assert np.isclose(v, 11.0, atol=1e-12)
    assert p is not None
    assert np.allclose(p, np.array([0.5, 1.0, 1.5], dtype=float), atol=1e-12)


def test_cylinder_visual_state_keeps_housing_on_frame_and_rod_runs_from_piston_to_eye() -> None:
    state = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 1.0], dtype=float),
        bot_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        stroke_pos_m=0.10,
        stroke_len_m=0.25,
        bore_d_m=0.032,
        rod_d_m=0.016,
        outer_d_m=0.038,
        dead_cap_len_m=0.018,
        dead_rod_len_m=0.025,
        body_len_m=0.30,
        dead_height_m=0.018,
    )

    assert state is not None
    housing0, housing1 = state['housing_seg']
    body0, body1 = state['body_seg']
    rod0, rod1 = state['rod_seg']
    piston = np.asarray(state['piston_center'], dtype=float)

    assert np.allclose(housing0, np.array([0.0, 0.0, 1.0], dtype=float), atol=1e-12)
    assert np.allclose(body0, np.array([0.0, 0.0, 1.0], dtype=float), atol=1e-12)
    assert np.allclose(body1, piston, atol=1e-12)
    # The opaque rod mesh represents only the exposed section outside the housing.
    assert np.allclose(rod0, housing1, atol=1e-12)
    assert np.allclose(rod1, np.array([0.0, 0.0, 0.0], dtype=float), atol=1e-12)
    assert float(housing1[2]) < 1.0
    assert float(housing1[2]) > 0.0


def test_rod_centerline_overlay_uses_existing_rod_segment_without_inventing_geometry() -> None:
    state = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 1.0], dtype=float),
        bot_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        stroke_pos_m=0.10,
        stroke_len_m=0.25,
        bore_d_m=0.032,
        rod_d_m=0.016,
        outer_d_m=0.038,
        dead_cap_len_m=0.018,
        dead_rod_len_m=0.025,
        body_len_m=0.30,
        dead_height_m=0.018,
    )

    vertices = rod_centerline_vertices_from_packaging_state(state)

    assert vertices is not None
    assert vertices.shape == (2, 3)
    assert np.allclose(vertices[0], np.asarray(state['rod_seg'][0], dtype=float), atol=1e-12)
    assert np.allclose(vertices[1], np.asarray(state['rod_seg'][1], dtype=float), atol=1e-12)


def test_app_source_wires_playback_sampling_into_3d_renderer() -> None:
    src = APP.read_text(encoding='utf-8')

    assert 'set_playback_sample_t' in src
    assert 'sample_t=self._playback_sample_t_s if bool(playing) else None' in src
    assert '_sample_time_bracket(' in src
    assert '_orient_centered_cylinder_vertices_to_y(v_unit)' in src
    assert '_rod_internal_centerline_vertices_from_packaging_state(packaging_state)' in src
    assert 'self._cyl_rod_core_lines' in src
