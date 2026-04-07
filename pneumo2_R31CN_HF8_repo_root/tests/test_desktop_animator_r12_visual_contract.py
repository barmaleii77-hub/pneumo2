from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    contact_patch_extent_from_vertical_clearance,
    lifted_box_center_from_lower_corners,
)


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')


def test_lifted_box_center_from_lower_corners_raises_center_by_half_height_along_local_z() -> None:
    center = np.array([0.2, -0.1, 0.30], dtype=float)
    R = np.eye(3, dtype=float)
    lifted = lifted_box_center_from_lower_corners(center, R, height_m=0.60)
    assert np.allclose(lifted, np.array([0.2, -0.1, 0.60]), atol=1e-12)


def test_contact_patch_extent_from_vertical_clearance_is_zero_without_penetration() -> None:
    length, width, pen = contact_patch_extent_from_vertical_clearance(
        wheel_radius_m=0.30,
        wheel_width_m=0.22,
        clearance_m=0.30,
    )
    assert np.isclose(length, 0.0)
    assert np.isclose(width, 0.22)
    assert np.isclose(pen, 0.0)



def test_contact_patch_extent_from_vertical_clearance_grows_for_positive_penetration() -> None:
    length, width, pen = contact_patch_extent_from_vertical_clearance(
        wheel_radius_m=0.30,
        wheel_width_m=0.22,
        clearance_m=0.27,
    )
    assert length > 0.0
    assert np.isclose(width, 0.22)
    assert pen > 0.0



def test_animator_source_contains_solver_point_lines_contact_patch_and_split_telemetry_docks() -> None:
    for needle in (
        '_contact_patch_mesh',
        '_arm_lines',
        '_cyl1_lines',
        '_cyl2_lines',
        '_lifted_box_center_from_lower_corners',
        'dock_heatmap',
        'dock_corner_quick',
        'dock_road_profile',
        'dock_corner_table',
        'dock_pressures',
        'dock_flows',
        'dock_valves',
        'TelemetryPanel(compact=True)',
    ):
        assert needle in APP_SOURCE



def test_animator_source_has_mouse_zoom_and_double_click_reset_in_all_main_metric_views() -> None:
    assert APP_SOURCE.count('def wheelEvent(self, event: QtGui.QWheelEvent)') >= 3
    assert APP_SOURCE.count('def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent)') >= 3
