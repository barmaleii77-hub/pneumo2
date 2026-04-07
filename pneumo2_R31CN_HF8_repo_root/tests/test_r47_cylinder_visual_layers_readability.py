from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_cylinder_visual_stack_contains_shell_chamber_rod_piston_and_frame_mount_markers() -> None:
    assert '_cyl_body_meshes' in APP
    assert '_cyl_chamber_meshes' in APP
    assert '_cyl_rod_meshes' in APP
    assert '_cyl_piston_meshes' in APP
    assert '_cyl_piston_ring_lines' in APP
    assert '_cyl_frame_mount_markers' in APP
    assert 'frame_mount_pts = [p for p in (cyl1_top_local_pts + cyl2_top_local_pts) if p is not None]' in APP
    assert 'self._contact_marker_line_vertices(' in APP


def test_outer_housing_shell_is_weakened_while_internal_layers_stay_readable() -> None:
    assert 'edgeColor=(0.18, 0.62, 0.88, 0.38)' in APP
    assert 'body.setGLOptions("translucent")' in APP
    assert 'edgeColor=(0.12, 0.84, 1.00, 0.96)' in APP
    assert 'color=(0.20, 0.74, 0.98, 0.24)' in APP
    assert 'color=(1.00, 0.88, 0.22, 0.88)' in APP
