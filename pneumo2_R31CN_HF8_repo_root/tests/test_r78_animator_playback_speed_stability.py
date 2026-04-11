from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.app import (
    _advance_playback_cursor_limited,
    _nominal_positive_dt_s,
    _playback_interval_ms_for_speed,
    _playback_source_index_for_time,
    _playback_visible_step_budget_s,
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


def test_playback_cursor_carries_small_late_tick_without_single_large_jump() -> None:
    interval_ms = _playback_interval_ms_for_speed(1.0)
    visible_budget_s = _playback_visible_step_budget_s(1.0, interval_ms=interval_ms)
    cursor_t_1, carry_s_1 = _advance_playback_cursor_limited(
        0.0,
        raw_wall_dt_s=0.030,
        speed=1.0,
        interval_ms=interval_ms,
        carry_s=0.0,
    )
    assert abs(cursor_t_1 - visible_budget_s) <= 1e-12
    assert 0.0 < carry_s_1 < 0.030

    cursor_t_2, carry_s_2 = _advance_playback_cursor_limited(
        cursor_t_1,
        raw_wall_dt_s=0.0,
        speed=1.0,
        interval_ms=interval_ms,
        carry_s=carry_s_1,
    )
    assert cursor_t_2 > cursor_t_1
    assert carry_s_2 < carry_s_1


def test_playback_source_index_is_causal_not_nearest_future_frame() -> None:
    t = np.asarray([0.0, 0.10, 0.20], dtype=float)
    assert _playback_source_index_for_time(t, 0.049) == 0
    assert _playback_source_index_for_time(t, 0.099999) == 0
    assert _playback_source_index_for_time(t, 0.100000) == 1
    assert _playback_source_index_for_time(t, 0.199999) == 1
    assert _playback_source_index_for_time(t, 0.200000) == 2


def test_speed_change_resets_pending_playback_carry_before_rearming_timer() -> None:
    assert "self._play_accum_s = 0.0\n            self._play_wall_ts = float(time.perf_counter())" in APP


def test_dense_bundle_nominal_dt_is_measured_from_positive_time_deltas() -> None:
    t = np.asarray([0.0, 0.0054, 0.0108, 0.0162], dtype=float)
    assert abs(_nominal_positive_dt_s(t) - 0.0054) <= 1e-12


def test_dense_bundle_fast_forward_uses_tighter_cadence_without_restoring_4ms_busy_loop() -> None:
    dense_dt_s = 0.00542888165038
    assert _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s) == 12
    assert _playback_interval_ms_for_speed(2.0, source_dt_s=dense_dt_s) == 8
    assert _playback_interval_ms_for_speed(4.0, source_dt_s=dense_dt_s) == 6
