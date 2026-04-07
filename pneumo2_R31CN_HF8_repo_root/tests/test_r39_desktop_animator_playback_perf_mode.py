from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_many_docks_mode_uses_lighter_overlays_but_keeps_aux_panels_live() -> None:
    assert "self._aux_play_fast_fps: float = 24.0" in SRC
    assert "self._aux_play_slow_fps: float = 12.0" in SRC
    assert "self._aux_many_fast_fps: float = 18.0" in SRC
    assert "self._aux_many_slow_fps: float = 10.0" in SRC
    assert "self._many_visible_threshold: int = 12" in SRC
    assert 'many_visible_budget = bool(playing) and visible_aux >= int(getattr(self, "_many_visible_threshold", 10))' in SRC
    assert "self._playback_perf_mode_active: bool = False" in SRC
    assert "def _visible_aux_dock_count(self) -> int:" in SRC
    assert "def _apply_playback_perf_mode(self, enabled: bool) -> None:" in SRC


def test_visible_fast_and_slow_groups_are_refreshed_as_groups() -> None:
    assert "for entry in fast_visible:" in SRC
    assert "for entry in slow_visible:" in SRC
    assert "_call_panel(entry)" in SRC
    assert "self.timeline.set_index(i)" in SRC
    assert "self.trends.update_frame(i)" in SRC


def test_views_have_playback_perf_mode_and_hide_expensive_overlays() -> None:
    assert SRC.count("def set_playback_perf_mode(self, enabled: bool) -> None:") >= 3
    assert "eff_show_labels = bool(self.show_labels) and not bool(self._playback_perf_mode)" in SRC
    assert "eff_show_text = bool(self.show_text) and not bool(self._playback_perf_mode)" in SRC
    assert "eff_show_seg_markers = bool(self.show_seg_markers) and not bool(self._playback_perf_mode)" in SRC
