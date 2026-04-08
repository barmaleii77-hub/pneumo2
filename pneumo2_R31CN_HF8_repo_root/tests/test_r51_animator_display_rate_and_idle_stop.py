from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')

COMPONENTS = [
    ROOT / 'pneumo_solver_ui' / 'components' / 'mech_car3d' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'mech_anim' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'mech_anim_quad' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'corner_heatmap_live' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'minimap_live' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'road_profile_live' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'pneumo_svg_flow' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'playhead_ctrl' / 'index.html',
    ROOT / 'pneumo_solver_ui' / 'components' / 'playhead_ctrl' / 'index_unified_v1.html',
]


def test_desktop_animator_uses_display_rate_playback_instead_of_4ms_frame_chasing() -> None:
    assert 'self._play_cursor_t_s = 0.0' in APP
    assert 'Display cadence' in APP or 'display cadence' in APP
    assert 'base_ms = 12.0  # ~83 Hz keeps x1.0 visibly alive without source-frame chasing.' in APP
    assert 'base_ms = 10.0  # ~100 Hz for moderate fast-forward.' in APP
    assert 'base_ms = 8.0   # ~125 Hz.' in APP
    assert 'base_ms = 6.0   # ~166 Hz upper service cadence on Windows precise timer.' in APP
    assert 'np.searchsorted(t, float(self._play_cursor_t_s), side=\'left\')' in APP
    assert 'base_ms = 4.0 if speed >= 1.0' not in APP
    assert 'visible_budget = int(max(1, _max_visible_advances_per_tick(self._speed)))' not in APP


def test_live_gl_layout_no_longer_hides_or_shows_viewport() -> None:
    assert 'self.view.hide()' not in APP
    assert 'self.view.show()' not in APP
    assert 'Hide/show was cheap' in APP
    assert 'vp.setUpdatesEnabled(not active)' in APP


def test_auxiliary_panes_are_restored_to_live_cadence_during_playback() -> None:
    assert 'self._aux_play_fast_fps: float = 24.0' in APP
    assert 'self._aux_play_slow_fps: float = 12.0' in APP
    assert 'self._aux_many_fast_fps: float = 18.0' in APP
    assert 'self._aux_many_slow_fps: float = 10.0' in APP
    assert 'self._many_visible_threshold: int = 12' in APP
    assert '("dock_hud", self.hud, "update_frame")' in APP
    assert '("dock_front", self.axleF, "update_frame")' in APP
    assert '("dock_rear", self.axleR, "update_frame")' in APP
    assert '("dock_left", self.sideL, "update_frame")' in APP
    assert '("dock_right", self.sideR, "update_frame")' in APP


def test_web_followers_stop_idle_polling_and_wake_from_scroll_resize_focus_visibility() -> None:
    for path in COMPONENTS:
        src = path.read_text(encoding='utf-8')
        assert '__nextIdleMs(60000, 180000, 300000)' not in src, path
        assert "window.addEventListener('scroll'" in src, path
        assert "window.addEventListener('resize'" in src, path

    for rel in ['pneumo_solver_ui/app.py', 'pneumo_solver_ui/pneumo_ui_app.py']:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert '__nextIdleMs(60000, 180000, 300000)' not in src, rel
        assert "window.addEventListener('scroll'" in src, rel
        assert "window.addEventListener('resize'" in src, rel
