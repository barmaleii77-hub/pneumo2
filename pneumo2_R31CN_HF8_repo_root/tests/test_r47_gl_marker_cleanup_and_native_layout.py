from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_no_user_facing_glscatter_point_sprites_remain_in_desktop_animator() -> None:
    assert 'gl.GLScatterPlotItem(' not in APP
    assert 'GL_POINT_SPRITE' in APP
    assert '_contact_pts = gl.GLLinePlotItem(' in APP
    assert 'self._cyl_piston_markers = None' in APP


def test_native_live_gl_layout_policy_is_now_explicit() -> None:
    assert 'the 3D viewport is temporarily suspended until the layout settles' in APP
    assert 'def _on_live_gl_layout_activity(self, reason: str) -> None:' in APP
    assert 'def _finish_gl_layout_transition(self) -> None:' in APP
    assert 'self._register_live_gl_layout_guard("dock_3d", dock_3d)' in APP
