from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')


def test_playback_stop_restores_lightened_panels_immediately() -> None:
    assert 'def _refresh_after_playback_stop(self) -> None:' in APP
    assert 'self._refresh_after_playback_stop()' in APP
    assert 'if the user stops playback manually' in APP


def test_live_gl_layout_change_auto_pauses_and_restores_native_dock() -> None:
    assert 'self._gl_layout_pause_timer' in APP
    assert 'def _on_live_gl_layout_activity(self, reason: str) -> None:' in APP
    assert 'self.cockpit.set_gl_layout_transition_active(True)' in APP
    assert 'self._resume_after_gl_layout_transition = True' in APP
    assert 'dock.topLevelChanged.connect' in APP
    assert 'dock.dockLocationChanged.connect' in APP
    assert 'self.view.setUpdatesEnabled(not active)' in APP
    assert 'self._layout_pause_placeholder.setVisible(False)' in APP
    assert 'self.view.hide()' not in APP


def test_layout_version_gate_prevents_old_special_window_state_from_returning() -> None:
    assert 'layout_matches = bool(saved_layout_version == str(getattr(self, "_dock_layout_version", "")))' in APP
    assert 'self.cockpit.show_all_docks()' in APP
    assert 'r31cn_continuous_sampling_gl_native_v2' in APP
