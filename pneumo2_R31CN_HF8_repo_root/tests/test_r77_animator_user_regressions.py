from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_tick_redraws_live_frame_once_per_playback_service_tick() -> None:
    assert APP.count('self._update_frame(int(self._idx), sample_t=self._play_cursor_t_s)') == 1


def test_animator_source_lifts_contact_patch_above_road_to_avoid_z_fighting() -> None:
    assert 'patch_verts[:, 2] = np.asarray(patch_verts[:, 2], dtype=float) + max(0.0015, 0.008 * wheel_radius_m)' in APP


def test_animator_source_uses_axis_sidewall_bulge_and_wishbone_plate_mesh() -> None:
    assert "def _wishbone_plate_mesh(" in APP
    assert 'verts[:, 1] = np.asarray(verts[:, 1], dtype=float) + (side_sign * sidewall_bulge_m)' in APP
