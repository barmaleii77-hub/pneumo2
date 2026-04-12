from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.app import (
    _advance_playback_cursor_limited,
    _nominal_positive_dt_s,
    _playback_interval_ms_for_speed,
    _playback_source_index_for_time,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_long_timer_gap_is_downgraded_to_single_service_quantum() -> None:
    interval_ms = _playback_interval_ms_for_speed(1.0)
    cursor_t, carry_s = _advance_playback_cursor_limited(
        0.0,
        raw_wall_dt_s=0.42,
        speed=1.0,
        interval_ms=interval_ms,
        carry_s=0.0,
    )
    expected_step_s = float(interval_ms) / 1000.0
    assert abs(cursor_t - expected_step_s) <= 1e-12
    assert abs(carry_s) <= 1e-12


def test_playback_cursor_preserves_small_late_tick_duration_without_budget_distortion() -> None:
    interval_ms = _playback_interval_ms_for_speed(1.0)
    cursor_t_1, carry_s_1 = _advance_playback_cursor_limited(
        0.0,
        raw_wall_dt_s=0.030,
        speed=1.0,
        interval_ms=interval_ms,
        carry_s=0.0,
    )
    assert abs(cursor_t_1 - 0.030) <= 1e-12
    assert abs(carry_s_1) <= 1e-12

    cursor_t_2, carry_s_2 = _advance_playback_cursor_limited(
        cursor_t_1,
        raw_wall_dt_s=0.0,
        speed=1.0,
        interval_ms=interval_ms,
        carry_s=carry_s_1,
    )
    assert abs(cursor_t_2 - cursor_t_1) <= 1e-12
    assert abs(carry_s_2) <= 1e-12


def test_playback_source_index_is_causal_not_nearest_future_frame() -> None:
    t = np.asarray([0.0, 0.10, 0.20], dtype=float)
    assert _playback_source_index_for_time(t, 0.049) == 0
    assert _playback_source_index_for_time(t, 0.099999) == 0
    assert _playback_source_index_for_time(t, 0.100000) == 1
    assert _playback_source_index_for_time(t, 0.199999) == 1
    assert _playback_source_index_for_time(t, 0.200000) == 2


def test_speed_change_consumes_pending_wall_time_before_rearming_timer() -> None:
    assert "raw_wall_dt = max(0.0, now - last)" in APP
    assert "self._play_cursor_t_s, self._play_accum_s = _advance_playback_cursor_limited(" in APP
    assert "speed=float(self._speed)," in APP
    assert "self._update_frame(int(self._idx), sample_t=self._play_cursor_t_s)" in APP
    assert "self._play_accum_s = 0.0\n            self._play_wall_ts = float(time.perf_counter())" in APP


def test_paused_refresh_and_resume_keep_continuous_sample_time() -> None:
    assert 'sample_t = getattr(self, "_play_cursor_t_s", None)' in APP
    assert 'def current_time(self, *, prefer_play_cursor: bool = True) -> float:' in APP
    assert 'if np.isfinite(ts):' in APP
    assert 'return float(np.clip(ts, float(t[0]), float(t[-1])))' in APP
    assert 'sample_t_release = self.current_time(prefer_play_cursor=True)' in APP
    assert 'self._idx = int(_playback_source_index_for_time(t_arr, float(self._play_cursor_t_s)))' in APP
    assert 'self._play_cursor_t_s = self.current_time(prefer_play_cursor=False)' in APP
    assert 'reset_to_start = False' in APP
    assert 'self._play_cursor_t_s = self.current_time(prefer_play_cursor=not bool(reset_to_start))' in APP
    assert 'self._update_frame(int(self._idx), sample_t=sample_t_arg)' in APP
    assert 'self.cockpit.update_frame(int(self._idx), playing=False, sample_t=sample_t_arg)' in APP


def test_toolbar_frame_readout_uses_continuous_sample_position() -> None:
    assert "sample_i0, sample_i1, alpha, _status_sample_t = _sample_time_bracket(" in APP
    assert "frame_pos = float(sample_i0) + (float(alpha) if int(sample_i1) != int(sample_i0) else 0.0)" in APP
    assert 'self.lbl_frame.setText(f"{frame_pos + 1.0:.2f}/{n}")' in APP
    assert 'self.lbl_frame.setText(f"{idx+1}/{n}")' in APP


def test_slider_drag_seek_uses_mouse_position_for_subframe_sample_time() -> None:
    assert "def _slider_drag_sample_time_hint(self) -> float | None:" in APP
    assert 'self.slider.mapFromGlobal(QtGui.QCursor.pos())' in APP
    assert "opt = QtWidgets.QStyleOptionSlider()" in APP
    assert "style.subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderGroove, self.slider)" in APP
    assert "idx_f = float(u * float(n - 1))" in APP
    assert "elif (sample_t_hint := self._slider_drag_sample_time_hint()) is not None and np.isfinite(float(sample_t_hint)):" in APP
    assert "self._idx = int(_playback_source_index_for_time(t_arr, seek_t))" in APP


def test_dense_bundle_nominal_dt_is_measured_from_positive_time_deltas() -> None:
    t = np.asarray([0.0, 0.0054, 0.0108, 0.0162], dtype=float)
    assert abs(_nominal_positive_dt_s(t) - 0.0054) <= 1e-12


def test_dense_bundle_keeps_speed_invariant_display_cadence_without_restoring_4ms_busy_loop() -> None:
    dense_dt_s = 0.00542888165038
    assert _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s) == 8
    assert _playback_interval_ms_for_speed(2.0, source_dt_s=dense_dt_s) == 8
    assert _playback_interval_ms_for_speed(4.0, source_dt_s=dense_dt_s) == 8
