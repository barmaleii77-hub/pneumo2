from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')


def test_front_view_update_frame_resolves_visual_toggles_locally() -> None:
    assert "eff_show_accel = bool(getattr(self, 'show_accel', True))" in APP
    assert "eff_show_vel = bool(getattr(self, 'show_vel', False))" in APP
    assert "eff_show_labels = bool(getattr(self, 'show_labels', True))" in APP


def test_startup_gl_meshes_stay_hidden_until_first_valid_geometry_arrives() -> None:
    assert 'self._road_mesh.setVisible(False)' in APP
    assert 'self._road_edges.setVisible(False)' in APP
    assert 'self._road_stripes.setVisible(False)' in APP
    assert 'self._contact_patch_mesh.setVisible(False)' in APP
