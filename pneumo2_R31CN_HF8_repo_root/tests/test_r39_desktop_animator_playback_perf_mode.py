from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_many_docks_mode_uses_lighter_overlays_but_keeps_aux_panels_live() -> None:
    assert "self._aux_play_fast_fps: float = 24.0" in SRC
    assert "self._aux_play_slow_fps: float = 12.0" in SRC
    assert "self._aux_many_fast_fps: float = 18.0" in SRC
    assert "self._aux_many_slow_fps: float = 10.0" in SRC
    assert "self._many_visible_threshold: int = 12" in SRC
    assert 'many_visible_budget = (bool(playing) or interactive_scrub) and visible_aux >= int(getattr(self, "_many_visible_threshold", 10))' in SRC
    assert "self._playback_perf_mode_active: bool = False" in SRC
    assert "def _visible_aux_dock_count(self) -> int:" in SRC
    assert "def _apply_playback_perf_mode(self, enabled: bool) -> None:" in SRC


def test_visible_fast_and_slow_groups_are_refreshed_as_groups() -> None:
    assert "for entry in fast_visible:" in SRC
    assert "slow_entries = slow_visible" in SRC
    assert "for entry in slow_entries:" in SRC
    assert "_call_panel(entry)" in SRC
    assert 'if self._dock_is_exposed("dock_timeline") and (bool(playing) or interactive_scrub or fast_due):' in SRC
    assert 'if interactive_scrub and self._dock_is_exposed("dock_telemetry"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and pressure_panel is not None and self._dock_is_exposed("dock_pressures"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and flow_panel is not None and self._dock_is_exposed("dock_flows"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and valve_panel is not None and self._dock_is_exposed("dock_valves"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and slow_due and corner_table_panel is not None and self._dock_is_exposed("dock_corner_table"):' in SRC
    assert 'if interactive_scrub and heatmap_panel is not None and self._dock_is_exposed("dock_heatmap"):' in SRC
    assert 'if interactive_scrub and corner_quick_panel is not None and self._dock_is_exposed("dock_corner_quick"):' in SRC
    assert 'if interactive_scrub and road_profile_panel is not None and self._dock_is_exposed("dock_road_profile"):' in SRC
    assert "self.timeline.set_playhead_time(self._playback_sample_t_s, idx=i)" in SRC
    assert "pressure_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "flow_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "valve_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "corner_table_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "heatmap_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "corner_quick_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "road_profile_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert 'if interactive_scrub and self._dock_is_exposed("dock_trends"):' in SRC
    assert "self.trends.update_frame(i, sample_t=self._playback_sample_t_s)" in SRC
    assert 'heatmap_panel = getattr(self, "telemetry_heatmap", None)' in SRC
    assert 'corner_quick_panel = getattr(self, "telemetry_corner_quick", None)' in SRC
    assert 'corner_table_panel = getattr(self, "telemetry_corner_table", None)' in SRC
    assert 'pressure_panel = getattr(self, "telemetry_press_panel", None)' in SRC
    assert 'flow_panel = getattr(self, "telemetry_flow_panel", None)' in SRC
    assert 'valve_panel = getattr(self, "telemetry_valve_panel", None)' in SRC
    assert 'road_profile_panel = getattr(self, "telemetry_road_profile", None)' in SRC
    assert "sample_t_panels = (" in SRC
    assert 'if self._dock_is_exposed("dock_timeline") and not interactive_scrub:' not in SRC


def test_views_have_playback_perf_mode_and_hide_expensive_overlays() -> None:
    assert SRC.count("def set_playback_perf_mode(self, enabled: bool) -> None:") >= 3
    assert "eff_show_labels = bool(self.show_labels) and not bool(self._playback_perf_mode)" in SRC
    assert "eff_show_text = bool(self.show_text) and not bool(self._playback_perf_mode)" in SRC
    assert "eff_show_seg_markers = bool(self.show_seg_markers) and not bool(self._playback_perf_mode)" in SRC
