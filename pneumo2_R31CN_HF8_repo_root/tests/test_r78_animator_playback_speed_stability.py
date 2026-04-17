from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.app import (
    MainWindow,
    _advance_prepared_playback_cursor_limited,
    _build_prepared_playback_times,
    _advance_playback_cursor_limited,
    _nominal_positive_dt_s,
    _playback_interval_ms_for_speed,
    _playback_rearm_delay_ms,
    _playback_source_index_for_time,
    _resolve_runtime_validation_budget_state,
    _requires_dense_validation_budget,
    _sample_prepared_playback_time,
    _update_playback_underrun_score,
)
from pneumo_solver_ui.desktop_animator.playback_sampling import (
    lerp_series_value,
    sample_time_bracket,
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


def test_playback_cursor_clamps_small_late_tick_to_visible_step_budget() -> None:
    interval_ms = _playback_interval_ms_for_speed(1.0)
    cursor_t_1, carry_s_1 = _advance_playback_cursor_limited(
        0.0,
        raw_wall_dt_s=0.030,
        speed=1.0,
        interval_ms=interval_ms,
        carry_s=0.0,
    )
    assert abs(cursor_t_1 - (float(interval_ms) / 1000.0)) <= 1e-12
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
    assert _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s) == 4
    assert _playback_interval_ms_for_speed(2.0, source_dt_s=dense_dt_s) == 4
    assert _playback_interval_ms_for_speed(4.0, source_dt_s=dense_dt_s) == 4
    assert _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s, display_hz=60.0) == 17
    assert _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s, display_hz=144.0) == 7
    assert _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s, display_hz=26.0) == 38


def test_prepared_playback_sampling_replaces_wall_clock_catchup_in_tick_path() -> None:
    assert "def _build_prepared_playback_times(" in APP
    assert "def _sample_prepared_playback_time(prepared_times_s: np.ndarray, cursor_f: float) -> float:" in APP
    assert "def _prepared_playback_cursor_for_time(prepared_times_s: np.ndarray, sample_t_s: float) -> float:" in APP
    assert "def _advance_prepared_playback_cursor_limited(" in APP
    assert "step_s = min(float(step_s), float(_playback_visible_step_budget_s(speed, interval_ms=interval_ms)))" in APP
    assert 'self._prepared_playback_times_s = _build_prepared_playback_times(' in APP
    assert 'display_hz=self._display_refresh_hz_hint(),' in APP
    assert 'use_prepared_clock = bool(prepared_times.size >= 2)' in APP
    assert 'cursor_f, sample_t_prepared = _advance_prepared_playback_cursor_limited(' in APP
    assert 'raw_wall_dt_s=raw_wall_dt,' in APP
    assert 'self._play_cursor_t_s = float(sample_t_prepared)' in APP


def test_dense_regular_sinusoid_gets_intermediate_visible_phase_between_solver_frames() -> None:
    dense_dt_s = 0.00542888165038
    t = np.arange(0.0, dense_dt_s * 7.0, dense_dt_s, dtype=float)
    prepared = _build_prepared_playback_times(t, source_dt_s=dense_dt_s)

    # Prepared presentation sampling must actually insert sub-frame timestamps, not
    # simply replay the source rows one-to-one.
    inner = prepared[(prepared > float(t[0]) + 1e-12) & (prepared < float(t[1]) - 1e-12)]
    assert inner.size > 0

    # Regular sinusoidal road excitation is exactly the case that looked visually
    # "stuck" when playback kept landing on the same phase each visible frame.
    z = np.sin((2.0 * np.pi / (8.0 * dense_dt_s)) * t)
    ts_mid = float(inner[0])
    i0, i1, alpha, _ = sample_time_bracket(t, sample_t=ts_mid, fallback_index=0)
    z_mid = float(lerp_series_value(z, i0=i0, i1=i1, alpha=alpha, default=0.0))

    assert i0 == 0
    assert i1 == 1
    assert 0.0 < alpha < 1.0
    assert float(z[0]) < z_mid < float(z[1])

    # And the prepared display times themselves must move through distinct phases.
    visible_t = np.asarray(
        [_sample_prepared_playback_time(prepared, float(k)) for k in range(min(5, int(prepared.size)))],
        dtype=float,
    )
    assert np.all(np.diff(visible_t) > 0.0)
    assert any(not np.any(np.isclose(ts, t, atol=1e-12)) for ts in visible_t[1:-1])


def test_prepared_playback_cursor_clamps_late_tick_to_visible_budget_instead_of_jump() -> None:
    dense_dt_s = 0.00542888165038
    t = np.arange(0.0, 0.30, dense_dt_s, dtype=float)
    prepared = _build_prepared_playback_times(t, source_dt_s=dense_dt_s)
    interval_ms = _playback_interval_ms_for_speed(1.0, source_dt_s=dense_dt_s)

    cursor_f, sample_t = _advance_prepared_playback_cursor_limited(
        prepared,
        0.0,
        raw_wall_dt_s=0.075,
        speed=1.0,
        interval_ms=interval_ms,
    )

    # Validation-first rule: under overload, prepared playback should lag rather than
    # jump across many dense solver phases in a single visible frame.
    assert 0.5 <= cursor_f <= 1.5
    assert 0.003 <= sample_t <= 0.005


def test_single_shot_rearm_compensates_time_spent_rendering() -> None:
    assert _playback_rearm_delay_ms(8, spent_s=0.000) == 8
    assert _playback_rearm_delay_ms(8, spent_s=0.0032) == 5
    assert _playback_rearm_delay_ms(8, spent_s=0.0100) == 1
    assert "Never rearm playback with a 0 ms single-shot timer." in APP


def test_dense_validation_budget_prioritizes_motion_views_on_dense_exports() -> None:
    assert _requires_dense_validation_budget(0.00542888165038, visible_aux=6)
    assert _requires_dense_validation_budget(0.0085, visible_aux=9)
    assert not _requires_dense_validation_budget(0.0090, visible_aux=9)
    assert not _requires_dense_validation_budget(0.0054, visible_aux=5)
    assert not _requires_dense_validation_budget(float("nan"), visible_aux=10)


def test_runtime_underrun_score_activates_and_recovers_validation_budget() -> None:
    score = 0.0
    active = False
    for _ in range(2):
        score, active = _update_playback_underrun_score(
            score,
            spent_s=0.0078,
            raw_wall_dt_s=0.0108,
            interval_ms=8,
        )
    assert active
    for _ in range(10):
        score, active = _update_playback_underrun_score(
            score,
            spent_s=0.0010,
            raw_wall_dt_s=0.0040,
            interval_ms=8,
        )
    assert score == 0.0
    assert not active


def test_load_npz_accepts_str_path_and_normalizes_to_path_object(monkeypatch) -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod

    class _DummyBundle:
        def __init__(self) -> None:
            self.t = np.asarray([0.0, 0.1], dtype=float)

        def ensure_world_xy(self): return None
        def ensure_world_velocity_xy(self): return None
        def ensure_body_velocity_xy(self): return None
        def ensure_yaw_rate_rad_s(self): return None
        def ensure_world_acceleration_xy(self): return None
        def ensure_body_acceleration_xy(self): return None
        def service_fallback_messages(self): return []

    class _DummyStopper:
        def stop(self): return None

    class _DummySlider:
        def blockSignals(self, _flag): return None
        def setMinimum(self, _v): return None
        def setMaximum(self, _v): return None
        def setValue(self, _v): return None

    class _DummyCockpit:
        def __init__(self) -> None:
            self.bundle = None
        def set_bundle(self, bundle): self.bundle = bundle

    class _DummyButton:
        def __init__(self) -> None:
            self.text = None
        def setText(self, text): self.text = text

    normalized = {}

    def _fake_load_npz(path):
        normalized["path"] = path
        return _DummyBundle()

    win = appmod.MainWindow.__new__(appmod.MainWindow)
    win.bundle = None
    win._scrub_release_pending = False
    win._scrub_release_timer = _DummyStopper()
    win.cockpit = _DummyCockpit()
    win.slider = _DummySlider()
    win.btn_play = _DummyButton()
    win._timer = _DummyStopper()
    win._display_refresh_hz_hint = lambda: 60.0
    win._speed = 1.0
    win._status_text = None
    win._update_frame_calls = []
    win._status = lambda text: setattr(win, "_status_text", text)
    win._update_frame = lambda idx, sample_t=None: win._update_frame_calls.append((idx, sample_t))

    monkeypatch.setattr(appmod, "load_npz", _fake_load_npz)
    monkeypatch.setattr(appmod, "run_self_checks", lambda bundle: type("Report", (), {"messages": []})())
    monkeypatch.setattr(appmod, "_emit_animator_warning", lambda *args, **kwargs: None)

    win.load_npz(r"C:\\tmp\\dense_validation_bundle.npz", background=False)

    assert isinstance(normalized["path"], Path)
    assert normalized["path"].name == "dense_validation_bundle.npz"
    assert win.cockpit.bundle is not None
    assert win._update_frame_calls
    assert win._status_text == f"Loaded: {normalized['path']}"


def test_runtime_validation_budget_is_latched_while_playing_to_prevent_visual_flap() -> None:
    assert _resolve_runtime_validation_budget_state(False, True, playing=True)
    assert _resolve_runtime_validation_budget_state(True, False, playing=True)
    assert not _resolve_runtime_validation_budget_state(True, False, playing=False)
    assert not _resolve_runtime_validation_budget_state(False, False, playing=True)


def test_mainwindow_detects_pending_car3d_present_and_defers_next_playback_step() -> None:
    class _FakeView:
        def __init__(self, pending: bool):
            self._anim_present_pending = pending

    class _FakeCar3D:
        def __init__(self, pending: bool):
            self.view = _FakeView(pending)

    class _FakeCockpit:
        def __init__(self, pending: bool):
            self.car3d = _FakeCar3D(pending)

    win = MainWindow.__new__(MainWindow)
    win.cockpit = _FakeCockpit(True)
    assert win._car3d_present_pending()

    win.cockpit = _FakeCockpit(False)
    assert not win._car3d_present_pending()


def test_pending_gl_present_does_not_accumulate_wall_time_debt(monkeypatch) -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod

    class _DummyBundle:
        t = np.asarray([0.0, 0.1, 0.2], dtype=float)

    win = MainWindow.__new__(MainWindow)
    win.bundle = _DummyBundle()
    win._playing = True
    win._idx = 0
    win._play_wall_ts = 10.0
    win._playback_interval_ms_for_index = lambda _idx: 8
    win._car3d_present_pending = lambda: True
    calls = []
    win._arm_next_playback_tick = lambda *, spent_s=0.0: calls.append(float(spent_s))

    monkeypatch.setattr(appmod.time, "perf_counter", lambda: 10.2)

    win._tick()

    assert abs(float(win._play_wall_ts) - 10.2) <= 1e-12
    assert calls == [0.0]
    assert win._idx == 0


def test_effective_display_refresh_prefers_measured_present_hz_over_nominal_screen_hz() -> None:
    win = MainWindow.__new__(MainWindow)
    win._present_hz_ema = 27.5
    win._display_refresh_hz_hint = lambda: 119.999
    assert abs(float(win._effective_display_refresh_hz_hint()) - 27.5) <= 1e-12


def test_car3d_present_signal_updates_measured_present_rate_only_while_playing() -> None:
    win = MainWindow.__new__(MainWindow)
    win._playing = False
    win._present_last_ts = 0.0
    win._present_dt_ema_s = float("nan")
    win._present_hz_ema = float("nan")

    win._on_car3d_frame_presented(10.0)
    win._on_car3d_frame_presented(10.05)
    assert not np.isfinite(float(win._present_hz_ema))

    win._playing = True
    win._on_car3d_frame_presented(11.0)
    win._on_car3d_frame_presented(11.04)
    hz = float(win._present_hz_ema)
    assert np.isfinite(hz)
    assert 20.0 <= hz <= 30.0


def test_car3d_present_signal_rearms_single_shot_timer_to_measured_present_cadence() -> None:
    class _DummyTimer:
        def __init__(self) -> None:
            self._interval = 8
            self.set_calls: list[int] = []
            self.start_calls = 0
            self.stop_calls = 0

        def isActive(self) -> bool:
            return True

        def interval(self) -> int:
            return int(self._interval)

        def setInterval(self, value: int) -> None:
            self._interval = int(value)
            self.set_calls.append(int(value))

        def start(self) -> None:
            self.start_calls += 1

        def stop(self) -> None:
            self.stop_calls += 1

    win = MainWindow.__new__(MainWindow)
    win.bundle = type("_DummyBundle", (), {"t": np.asarray([0.0, 0.1, 0.2], dtype=float)})()
    win._playing = True
    win._idx = 0
    win._present_last_ts = 0.0
    win._present_dt_ema_s = float("nan")
    win._present_hz_ema = float("nan")
    win._timer = _DummyTimer()
    win._car3d_present_pending = lambda: False
    win._playback_interval_ms_for_index = lambda _idx: 43

    win._on_car3d_frame_presented(11.0)
    win._on_car3d_frame_presented(11.04)

    assert win._timer.set_calls == [43]
    assert win._timer.stop_calls == 1
    assert win._timer.start_calls == 1
    assert win._timer.interval() == 43
