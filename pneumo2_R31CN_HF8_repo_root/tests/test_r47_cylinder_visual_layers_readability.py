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
    assert 'edgeColor=(0.18, 0.62, 0.88, 0.26)' in APP
    assert 'body.setGLOptions("translucent")' in APP
    assert 'drawEdges=False' in APP
    assert 'color=(0.20, 0.74, 0.98, 0.08)' in APP
    assert 'color=(0.90, 0.96, 1.00, 0.78)' in APP
    assert 'color=(0.34, 0.90, 1.00, 0.74)' in APP
    assert 'color=(1.00, 0.80, 0.34, 0.74)' in APP
    assert 'color=(1.00, 0.88, 0.22, 0.96)' in APP
    assert 'rod_display_seg = self._rod_display_segment_from_packaging_state(packaging_state)' in APP
    assert 'packaging_state.get("piston_center")' in APP
    assert 'show_cylinder_internal_detail_lines = True' in APP
    assert 'if rod_display_seg is not None:' in APP
    assert 'rod_inner_seg = _rod_internal_centerline_vertices_from_packaging_state(packaging_state)' in APP
