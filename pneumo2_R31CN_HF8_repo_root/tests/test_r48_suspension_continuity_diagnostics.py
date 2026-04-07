import numpy as np

from pneumo_solver_ui.desktop_animator.suspension_geometry_diagnostics import (
    collect_suspension_geometry_status,
    format_suspension_hud_lines,
)


class _DummyBundle:
    def __init__(self, points):
        self._points = points

    def point_xyz(self, kind: str, corner: str):
        return self._points.get((kind, corner))


def _pt_frames(*rows):
    return np.asarray(rows, dtype=float)


def _build_rigid_corner_points():
    pts = {}
    frame = {
        'ЛП': np.asarray([[+1.0, +0.5, 0.4], [+1.0, +0.5, 0.5]], dtype=float),
        'ПП': np.asarray([[+1.0, -0.5, 0.2], [+1.0, -0.5, 0.3]], dtype=float),
        'ЛЗ': np.asarray([[-1.0, +0.5, 0.4], [-1.0, +0.5, 0.5]], dtype=float),
        'ПЗ': np.asarray([[-1.0, -0.5, 0.2], [-1.0, -0.5, 0.3]], dtype=float),
    }
    for c, arr in frame.items():
        pts[('frame_corner', c)] = arr
        pts[('lower_arm_frame_front', c)] = np.asarray([[+0.7, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.35], [+0.7, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.45]], dtype=float)
        pts[('lower_arm_frame_rear', c)] = np.asarray([[+0.5, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.35], [+0.5, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.45]], dtype=float)
        pts[('upper_arm_frame_front', c)] = np.asarray([[+0.7, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.45], [+0.7, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.55]], dtype=float)
        pts[('upper_arm_frame_rear', c)] = np.asarray([[+0.5, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.45], [+0.5, +0.2 if c in ('ЛП','ЛЗ') else -0.2, 0.55]], dtype=float)
        pts[('arm_pivot', c)] = 0.5 * (pts[('lower_arm_frame_front', c)] + pts[('lower_arm_frame_rear', c)])
        pts[('arm2_pivot', c)] = 0.5 * (pts[('upper_arm_frame_front', c)] + pts[('upper_arm_frame_rear', c)])
        # wheel/upright rigid family
        s = +1.0 if c in ('ЛП','ЛЗ') else -1.0
        pts[('lower_arm_hub_front', c)] = np.asarray([[+0.9, 0.55*s, 0.15], [+0.9, 0.55*s, 0.25]], dtype=float)
        pts[('lower_arm_hub_rear', c)] = np.asarray([[+0.7, 0.55*s, 0.15], [+0.7, 0.55*s, 0.25]], dtype=float)
        pts[('upper_arm_hub_front', c)] = np.asarray([[+0.9, 0.55*s, 0.25], [+0.9, 0.55*s, 0.35]], dtype=float)
        pts[('upper_arm_hub_rear', c)] = np.asarray([[+0.7, 0.55*s, 0.25], [+0.7, 0.55*s, 0.35]], dtype=float)
        pts[('arm_joint', c)] = 0.5 * (pts[('lower_arm_hub_front', c)] + pts[('lower_arm_hub_rear', c)])
        pts[('arm2_joint', c)] = 0.5 * (pts[('upper_arm_hub_front', c)] + pts[('upper_arm_hub_rear', c)])
        pts[('wheel_center', c)] = np.asarray([[0.8, 0.55*s, 0.20], [0.8, 0.55*s, 0.30]], dtype=float)
        pts[('cyl1_top', c)] = pts[('upper_arm_frame_front', c)].copy()
        pts[('cyl2_top', c)] = pts[('upper_arm_frame_rear', c)].copy()
        pts[('cyl1_bot', c)] = pts[('upper_arm_frame_front', c)] + 0.4 * (pts[('upper_arm_hub_front', c)] - pts[('upper_arm_frame_front', c)])
        pts[('cyl2_bot', c)] = pts[('upper_arm_frame_rear', c)] + 0.6 * (pts[('upper_arm_hub_rear', c)] - pts[('upper_arm_frame_rear', c)])
    return pts


def test_diagnostics_accept_rigid_mounts_and_attached_cylinder_bots():
    b = _DummyBundle(_build_rigid_corner_points())
    st = collect_suspension_geometry_status(b, tol_m=1e-9)
    assert st['frame_drift_corners'] == []
    assert st['wheel_drift_corners'] == []
    assert st['cyl1_detached_corners'] == []
    assert st['cyl2_detached_corners'] == []
    lines = format_suspension_hud_lines(b, tol_m=1e-9)
    assert not any('дрейфуют' in line for line in lines)
    assert not any('off-arm' in line for line in lines)


def test_diagnostics_flag_frame_drift_and_detached_cylinder_bot():
    pts = _build_rigid_corner_points()
    # Break frame rigidity for one frame-mounted point.
    pts[('cyl1_top', 'ЛП')] = pts[('cyl1_top', 'ЛП')].copy()
    pts[('cyl1_top', 'ЛП')][1, 0] += 0.05
    # Break arm continuity for one cylinder bot.
    pts[('cyl2_bot', 'ЛП')] = pts[('cyl2_bot', 'ЛП')].copy()
    pts[('cyl2_bot', 'ЛП')][1, 2] += 0.03
    b = _DummyBundle(pts)
    st = collect_suspension_geometry_status(b, tol_m=1e-6)
    assert 'ЛП' in st['frame_drift_corners']
    assert 'ЛП' in st['cyl2_detached_corners']
    lines = '\n'.join(format_suspension_hud_lines(b, tol_m=1e-6))
    assert 'Рама: точки крепления дрейфуют' in lines
    assert 'Шток→рычаг: off-arm' in lines
