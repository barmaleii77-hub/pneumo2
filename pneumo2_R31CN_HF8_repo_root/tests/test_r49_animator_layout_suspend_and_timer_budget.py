from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_layout_guard_observes_only_dock_and_suspends_viewport() -> None:
    assert 'Only observe the dock widget itself.' in APP
    assert 'dock.installEventFilter(self)' in APP
    assert 'self.view.hide()' not in APP
    assert 'self._layout_pause_placeholder.setVisible(False)' in APP
    assert 'if not should_notify and dock_is_floating and et in {' in APP


def test_playback_timer_and_road_mesh_budget_are_tightened_for_live_playback() -> None:
    assert 'base_ms = 8.0  # Fallback ~125 Hz display cadence when source sampling is sparse.' in APP
    assert 'display_hz=self._display_refresh_hz_hint(),' in APP
    assert 'target_ms = 500.0 * dense_dt_s' in APP
    assert 'speed-independent' in APP
    assert 'int(max(4, min(20, round(base_ms))))' in APP
    assert 'def _playback_rearm_delay_ms(target_interval_ms: int, *, spent_s: float = 0.0) -> int:' in APP
    assert 'self._timer.setInterval(_playback_rearm_delay_ms(target_interval_ms, spent_s=float(spent_s)))' in APP
    assert 'tick_spent_s = max(0.0, float(time.perf_counter()) - now)' in APP
    assert 'min_long = int(max(240, self._road_pts))' in APP
    assert 'max_long = 1200' in APP
    assert 'min_lat = 9' in APP
