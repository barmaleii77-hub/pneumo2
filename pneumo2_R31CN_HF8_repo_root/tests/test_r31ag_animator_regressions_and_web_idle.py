from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
CAR3D = (ROOT / "pneumo_solver_ui" / "components" / "mech_car3d" / "index.html").read_text(encoding="utf-8")
MECH_ANIM = (ROOT / "pneumo_solver_ui" / "components" / "mech_anim" / "index.html").read_text(encoding="utf-8")
PLAYHEAD = (ROOT / "pneumo_solver_ui" / "components" / "playhead_ctrl" / "index.html").read_text(encoding="utf-8")


def test_road_items_become_visible_after_valid_geometry_update() -> None:
    assert 'self._road_mesh.setVisible(True)' in APP
    assert 'self._road_edges.setVisible(True)' in APP
    assert 'self._road_stripes.setVisible(True)' in APP


def test_playback_perf_mode_no_longer_suppresses_front_and_rear_axle_views() -> None:
    assert 'for panel in (self.sideL, self.sideR, self.hud):' in APP
    assert 'for panel in (self.axleF, self.axleR, self.sideL, self.sideR, self.hud):' not in APP


def test_web_heavy_components_can_fully_stop_render_loops_when_idle() -> None:
    assert '__RENDER_HANDLE = null;' in CAR3D
    assert "__LOOP_HANDLE = null;" in MECH_ANIM
    assert "__LOOP_HANDLE = null;" in PLAYHEAD
    assert "__scheduleRender('timeout', __PAUSE_POLL_MS);" not in CAR3D
