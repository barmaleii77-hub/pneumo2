from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
CAR3D = (ROOT / "pneumo_solver_ui" / "components" / "mech_car3d" / "index.html").read_text(encoding="utf-8")
MECH_ANIM = (ROOT / "pneumo_solver_ui" / "components" / "mech_anim" / "index.html").read_text(encoding="utf-8")
PLAYHEAD = (ROOT / "pneumo_solver_ui" / "components" / "playhead_ctrl" / "index.html").read_text(encoding="utf-8")


def test_road_preview_defaults_to_mesh_without_wire_overlay() -> None:
    assert "_set_poly_mesh(" in APP
    assert "self._road_mesh," in APP
    assert "drawEdges=True," in APP
    assert "edgeColor=(0.22, 0.30, 0.38, 0.40)," in APP
    assert 'show_road_wire = bool(show_road and bool(self._visual.get("show_road_wire", False)))' in APP
    assert '_set_line_item_pos(self._road_edges, None)' in APP
    assert '_set_line_item_pos(self._road_stripes, None)' in APP


def test_playback_perf_mode_applies_consistent_perf_hints_to_all_aux_panels() -> None:
    assert 'for panel in (self.axleF, self.axleR, self.sideL, self.sideR, self.hud):' in APP


def test_web_heavy_components_can_fully_stop_render_loops_when_idle() -> None:
    assert '__RENDER_HANDLE = null;' in CAR3D
    assert "__LOOP_HANDLE = null;" in MECH_ANIM
    assert "__LOOP_HANDLE = null;" in PLAYHEAD
    assert "__scheduleRender('timeout', __PAUSE_POLL_MS);" not in CAR3D
