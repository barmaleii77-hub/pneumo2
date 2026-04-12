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
    assert 'base_ms = 8.0  # ~125 Hz stable display cadence across playback speeds.' in APP
    assert 'target_ms = 1000.0 * 1.5 * dense_dt_s' in APP
    assert 'speed-independent' in APP
    assert 'int(max(6, min(20, round(base_ms))))' in APP
    assert 'max_long = 260' in APP
    assert 'max_long = 420' in APP
    assert 'min_lat = 5' in APP
