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


def _pt(x, y, z):
    return np.asarray([[x, y, z], [x, y, z]], dtype=float)


def test_detects_missing_second_arm_and_coincident_cylinders():
    points = {}
    for corner, s in [("ЛП", +1.0), ("ПП", -1.0), ("ЛЗ", +1.0), ("ПЗ", -1.0)]:
        points[("arm_pivot", corner)] = _pt(0.0, 0.0, 0.0)
        points[("arm_joint", corner)] = _pt(0.0, 0.5 * s, -0.1)
        # Cylinders present twice, but with identical geometry.
        points[("cyl1_top", corner)] = _pt(0.0, 0.1 * s, 0.2)
        points[("cyl1_bot", corner)] = _pt(0.0, 0.3 * s, -0.05)
        points[("cyl2_top", corner)] = _pt(0.0, 0.1 * s, 0.2)
        points[("cyl2_bot", corner)] = _pt(0.0, 0.3 * s, -0.05)
    b = _DummyBundle(points)
    st = collect_suspension_geometry_status(b)
    assert not st["ok"]
    assert st["missing_second_arm_corners"] == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    assert st["coincident_cylinder_corners"] == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    lines = format_suspension_hud_lines(b)
    joined = "\n".join(lines)
    assert "рычагов/угол 1/2" in joined
    assert "C1/C2 совпадают" in joined


def test_detects_two_distinct_arms_and_cylinder_axes():
    points = {}
    for corner, s in [("ЛП", +1.0), ("ПП", -1.0), ("ЛЗ", +1.0), ("ПЗ", -1.0)]:
        points[("arm_pivot", corner)] = _pt(0.0, 0.0, 0.0)
        points[("arm_joint", corner)] = _pt(0.0, 0.5 * s, -0.1)
        points[("arm2_pivot", corner)] = _pt(0.0, 0.0, 0.15)
        points[("arm2_joint", corner)] = _pt(0.0, 0.5 * s, -0.02)
        points[("cyl1_top", corner)] = _pt(0.0, 0.1 * s, 0.2)
        points[("cyl1_bot", corner)] = _pt(0.0, 0.3 * s, -0.05)
        points[("cyl2_top", corner)] = _pt(0.02, 0.12 * s, 0.22)
        points[("cyl2_bot", corner)] = _pt(0.01, 0.33 * s, 0.03)
    b = _DummyBundle(points)
    st = collect_suspension_geometry_status(b)
    rows = {r["corner"]: r for r in st["rows"]}
    assert st["missing_second_arm_corners"] == []
    assert rows["ЛП"]["upper_arm_present"] is True
    assert rows["ЛП"]["arm_geometries_present"] == 2
    assert rows["ЛП"]["distinct_cylinder_axes"] == 2
    assert rows["ПЗ"]["coincident_cylinder_axes"] is False


def test_detects_collapsed_upper_and_lower_arm_joints():
    points = {}
    for corner, s in [("ЛП", +1.0), ("ПП", -1.0), ("ЛЗ", +1.0), ("ПЗ", -1.0)]:
        points[("arm_pivot", corner)] = _pt(0.0, 0.0, 0.0)
        points[("arm_joint", corner)] = _pt(0.0, 0.5 * s, -0.1)
        points[("arm2_pivot", corner)] = _pt(0.0, 0.0, 0.15)
        points[("arm2_joint", corner)] = _pt(0.0, 0.5 * s, -0.1)
    b = _DummyBundle(points)
    st = collect_suspension_geometry_status(b)
    assert st["coincident_arm_joint_corners"] == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    lines = format_suspension_hud_lines(b)
    assert any("сходятся в одну точку" in line for line in lines)
