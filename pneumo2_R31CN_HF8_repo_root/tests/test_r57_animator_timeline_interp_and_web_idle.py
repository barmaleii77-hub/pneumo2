from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    cylinder_visual_state_from_packaging,
    rod_internal_centerline_vertices_from_packaging_state,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')
DATA_BUNDLE = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'data_bundle.py').read_text(encoding='utf-8')
HMI = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'hmi_widgets.py').read_text(encoding='utf-8')
PLAYHEAD = (ROOT / 'pneumo_solver_ui' / 'components' / 'playhead_ctrl' / 'index.html').read_text(encoding='utf-8')
PLAYHEAD_UNIFIED = (ROOT / 'pneumo_solver_ui' / 'components' / 'playhead_ctrl' / 'index_unified_v1.html').read_text(encoding='utf-8')
ROAD = (ROOT / 'pneumo_solver_ui' / 'components' / 'road_profile_live' / 'index.html').read_text(encoding='utf-8')
MINIMAP = (ROOT / 'pneumo_solver_ui' / 'components' / 'minimap_live' / 'index.html').read_text(encoding='utf-8')
HEAT = (ROOT / 'pneumo_solver_ui' / 'components' / 'corner_heatmap_live' / 'index.html').read_text(encoding='utf-8')
QUAD = (ROOT / 'pneumo_solver_ui' / 'components' / 'mech_anim_quad' / 'index.html').read_text(encoding='utf-8')
CAR3D = (ROOT / 'pneumo_solver_ui' / 'components' / 'mech_car3d' / 'index.html').read_text(encoding='utf-8')
MECH_ANIM = (ROOT / 'pneumo_solver_ui' / 'components' / 'mech_anim' / 'index.html').read_text(encoding='utf-8')
SVG_FLOW = (ROOT / 'pneumo_solver_ui' / 'components' / 'pneumo_svg_flow' / 'index.html').read_text(encoding='utf-8')


def test_internal_rod_overlay_targets_only_the_segment_inside_transparent_housing() -> None:
    state = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 1.0], dtype=float),
        bot_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        stroke_pos_m=0.10,
        stroke_len_m=0.25,
        bore_d_m=0.032,
        rod_d_m=0.016,
        outer_d_m=0.038,
        dead_cap_len_m=0.018,
        dead_rod_len_m=0.025,
        body_len_m=0.30,
        dead_height_m=0.018,
    )

    assert state is not None
    inner = rod_internal_centerline_vertices_from_packaging_state(state)
    assert inner is not None
    assert inner.shape == (2, 3)
    assert np.allclose(inner[0], np.asarray(state['piston_center'], dtype=float), atol=1e-12)
    assert np.allclose(inner[1], np.asarray(state['housing_seg'][1], dtype=float), atol=1e-12)
    assert float(np.linalg.norm(inner[1] - inner[0])) > 1e-9


def test_front_and_side_helper_views_now_accept_continuous_sample_t() -> None:
    assert 'def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):' in APP
    assert APP.count('def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):') >= 3
    assert APP.count('_sample_series_local(') >= 2
    assert 'road_profile_panel = getattr(self, "telemetry_road_profile", None)' in APP
    assert 'heatmap_panel = getattr(self, "telemetry_heatmap", None)' in APP
    assert 'corner_quick_panel = getattr(self, "telemetry_corner_quick", None)' in APP
    assert 'corner_table_panel = getattr(self, "telemetry_corner_table", None)' in APP
    assert 'pressure_panel = getattr(self, "telemetry_press_panel", None)' in APP
    assert 'flow_panel = getattr(self, "telemetry_flow_panel", None)' in APP
    assert 'valve_panel = getattr(self, "telemetry_valve_panel", None)' in APP
    assert "sample_t_panels = (" in APP
    assert 'sample_t=self._playback_sample_t_s,' in APP
    assert 'sample_t=self._playback_sample_t_s if bool(playing) else None' not in APP
    assert 'if interactive_scrub and self._dock_is_exposed("dock_telemetry"):' in APP
    assert 'if interactive_scrub and (not many_visible_budget) and pressure_panel is not None and self._dock_is_exposed("dock_pressures"):' in APP
    assert 'if interactive_scrub and (not many_visible_budget) and flow_panel is not None and self._dock_is_exposed("dock_flows"):' in APP
    assert 'if interactive_scrub and (not many_visible_budget) and valve_panel is not None and self._dock_is_exposed("dock_valves"):' in APP
    assert 'if interactive_scrub and (not many_visible_budget) and slow_due and corner_table_panel is not None and self._dock_is_exposed("dock_corner_table"):' in APP
    assert 'if interactive_scrub and heatmap_panel is not None and self._dock_is_exposed("dock_heatmap"):' in APP
    assert 'if interactive_scrub and corner_quick_panel is not None and self._dock_is_exposed("dock_corner_quick"):' in APP
    assert 'if interactive_scrub and road_profile_panel is not None and self._dock_is_exposed("dock_road_profile"):' in APP
    assert '"dock_multifactor",' in APP
    assert '("dock_multifactor", getattr(self, "telemetry_multifactor", None), "update_frame"),' in APP
    assert 'if interactive_scrub and multifactor_panel is not None and self._dock_is_exposed("dock_multifactor"):' not in APP
    assert 'self.corner_table.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.corner_heatmap.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.corner_quick.update_frame(b, i, sample_t=sample_t)' in APP
    assert 't = sample(summary["t"], 0.0)' in APP
    assert "def _current_segment_index_for_sample(self, *, idx: int, s_value: float) -> int:" in APP
    assert "v0_mps = math.hypot(vx0, vy0)" in APP
    assert "cur_seg_idx = self._current_segment_index_for_sample(idx=idx_ref, s_value=s_now)" in APP
    assert 'self.press_quick.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.valve_quick.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.flow_quick.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.tank_gauge.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.press_panel.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.flow_panel.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.valve_panel.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'zb = sample(sig["zb"], 0.0)' in APP
    assert 'air = int(sample(sig["air"], 0.0) > 0.5)' in APP
    assert 'v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0' in APP
    assert 'P = sample(arr, patm)' in APP
    assert "vals0 = np.asarray(b.open.values[i0, self._idxs], dtype=float)" in APP
    assert "q0 = np.asarray(b.q.values[i0, self._idxs], dtype=float)" in APP
    assert 'self.road_profile.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'idx_ref = int(_clamp(int(sample_i0 if float(alpha) < 0.5 else sample_i1), 0, len(s) - 1))' in APP
    assert 's0 = sample(s, float(s[idx_ref]))' in APP
    assert 'zc = sample(z_arr, float("nan"))' in APP
    assert 'def update_frame(self, i: int, *, sample_t: float | None = None):' in HMI
    assert 'self.canvas.set_playhead_time(sample_t, idx=i)' in HMI
    assert 'def set_playhead_time(self, sample_t: float | None, *, idx: int):' in HMI
    assert 'play_t = self._normalized_playhead_time(sample_t, idx_i)' in HMI
    assert 'y0 = self._sample_series_value(y_all, play_t, idx)' in HMI
    assert 'u = (play_t - t0) / dt' in HMI
    assert 'x_i = (play_t - t_min) / (t_max - t_min)' in HMI
    assert 'lambda: self.timeline.set_playhead_time(self._playback_sample_t_s, idx=idx),' in APP
    assert 'lambda: self.timeline.set_playhead_time(self._playback_sample_t_s, idx=i),' in APP
    assert 'lambda: pressure_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: flow_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: valve_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: corner_table_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: heatmap_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: corner_quick_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: road_profile_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: self.trends.update_frame(idx, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: self.trends.update_frame(i, sample_t=self._playback_sample_t_s),' in APP


def test_event_timeline_click_to_seek_carries_exact_sample_time() -> None:
    assert "seek_sample = QtCore.Signal(int, float)" in HMI
    assert "tc = t0 + u * (t1 - t0)" in HMI
    assert 'idx = int(np.searchsorted(self._t, tc, side="right") - 1)' in HMI
    assert "self.seek_sample.emit(idx, float(tc))" in HMI
    assert "seek_sample_requested = QtCore.Signal(int, float)" in APP
    assert "self.timeline.seek_sample.connect(self.seek_sample_requested.emit)" in APP
    assert "self.timeline.seek_index.connect(self.seek_requested.emit)" not in APP
    assert "self.cockpit.seek_sample_requested.connect(self._on_seek_sample_requested)" in APP
    assert "def _apply_seek_request(self, idx: int, *, sample_t: float | None = None) -> None:" in APP
    assert "self._idx = int(_playback_source_index_for_time(t_arr, seek_t))" in APP
    assert "self._play_cursor_t_s = seek_t" in APP
    assert "def _on_seek_sample_requested(self, idx: int, sample_t: float):" in APP
    assert "self._apply_seek_request(idx, sample_t=float(sample_t))" in APP


def test_event_timeline_promotes_authored_ring_segment_ranges_into_desktop_band() -> None:
    assert "def _timeline_ring_segment_ranges_for_bundle(bundle: object) -> List[dict]:" in HMI
    assert 'cached = getattr(bundle, "_desktop_ring_segment_ranges_cache", _RING_SEGMENT_CACHE_MISS)' in HMI
    assert "build_nominal_ring_progress_from_spec" in HMI
    assert "build_segment_ranges_from_progress" in HMI
    assert "self._segment_ranges: List[dict] = []" in HMI
    assert "ring_ranges = _timeline_ring_segment_ranges_for_bundle(b)" in HMI
    assert "self._segment_ranges = [dict(rr) for rr in ring_ranges if isinstance(rr, dict)]" in HMI
    assert "segment_band_h = 8 if segment_ranges else 0" in HMI
    assert 'p.drawText(' in HMI
    assert '"RING"' in HMI


def test_desktop_animator_world_progress_falls_back_to_xy_arclength_for_truthful_motion() -> None:
    assert 'key = "svc__world_progress_series"' in APP
    assert 'key = "svc__body_longitudinal_progress_series"' in APP
    assert 'def _cumulative_path_length_series(x_series: Any, y_series: Any) -> np.ndarray:' in APP
    assert 'def _ensure_world_progress_series(b: DataBundle) -> np.ndarray:' in APP
    assert 'def _ensure_body_longitudinal_progress_series(b: DataBundle) -> np.ndarray:' in APP
    assert 'xw, yw = b.ensure_world_xy()' in APP
    assert 's_world_xy = _cumulative_path_length_series(' in APP
    assert 'monotonic_non_decreasing = bool(np.all(~np.isfinite(ds) | (ds >= -1e-9)))' in APP
    assert 'vxb_arr, _ = b.ensure_body_velocity_xy()' in APP
    assert 'vx_mid = 0.5 * (vx[:-1] + vx[1:])' in APP
    assert 'ds = vx_mid * dt' in APP
    assert 's_progress_series = np.asarray(_ensure_world_progress_series(b), dtype=float)' in APP
    assert 'spin_progress_series = np.asarray(_ensure_body_longitudinal_progress_series(b), dtype=float)' in APP
    assert 's_path = np.asarray(_ensure_world_progress_series(bundle), dtype=float).reshape(-1)' in APP
    assert 's_world = _ensure_world_progress_series(b)' in APP
    assert 'def _solver_signed_speed_along_road(' in APP
    assert 'vx, vy = b.ensure_body_velocity_xy()' in APP
    assert 'yaw_rate = b.ensure_yaw_rate_rad_s()' in APP
    assert 'ax, ay = b.ensure_body_acceleration_xy()' in APP
    assert 'vxb_arr, vyb_arr = b.ensure_body_velocity_xy()' in APP
    assert 'body_vx = float("nan")' in APP
    assert 'body_vy = float("nan")' in APP
    assert 'body_vx = float(get_value("скорость_vx_м_с", 0.0))' in APP
    assert 'body_vy = float(get_value("скорость_vy_м_с", 0.0))' in APP
    assert 'solver_speed_mag = float(math.hypot(body_vx, body_vy))' in APP
    assert 'speed_mag = abs(ds / dt)' in APP
    assert 'return float(math.copysign(speed_mag, body_vx))' in APP
    assert 'rolling_progress_m=spin_progress_m' in APP
    assert 'path_progress_m=s_progress_m' not in APP
    assert 'speed_sign * math.hypot(float(x0), float(y0))' not in APP
    assert 'sample_i0, sample_i1, alpha, _status_sample_t = _sample_time_bracket(' in APP
    assert 'summary = _ensure_telemetry_summary_cache(b)' in APP
    assert 't_status = _sample_series_local(summary["t"], i0=sample_i0, i1=sample_i1, alpha=alpha, default=t)' in APP
    assert 'vx_status = _sample_series_local(summary["vx"], i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'vy_status = _sample_series_local(summary["vy"], i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'v = float(math.hypot(float(vx_status), float(vy_status)))' in APP
    assert 'vx_status = _sample_series_local(vxw, i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'vy_status = _sample_series_local(vyw, i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'vxb, vyb = b.ensure_body_velocity_xy()' in HMI
    assert 'vx_arr = np.asarray(vxb, dtype=float).reshape(-1)' in HMI
    assert 'vy_arr = np.asarray(vyb, dtype=float).reshape(-1)' in HMI
    assert 'y_v[:n_v] = np.asarray(np.hypot(vx_arr[:n_v], vy_arr[:n_v]), dtype=float)' in HMI
    assert 'vx_raw = _align_series_length(b.get("скорость_vx_м_с", 0.0), n_t, fill=0.0)' in HMI
    assert 'vy_raw = _align_series_length(b.get("скорость_vy_м_с", 0.0), n_t, fill=0.0)' in HMI
    assert 'y_v = np.asarray(np.hypot(vx_raw, vy_raw), dtype=float)' in HMI
    assert 'y_az = _align_series_length(b.get("ускорение_рамы_z_м_с2", 0.0), n_t, fill=0.0)' in HMI
    assert 'y_roll = np.degrees(_align_series_length(b.get("крен_phi_рад", 0.0), n_t, fill=0.0))' in HMI
    assert 'y_pitch = np.degrees(_align_series_length(b.get("тангаж_theta_рад", 0.0), n_t, fill=0.0))' in HMI
    assert 'bar_g = _align_series_length((pacc - patm) / 1e5, n_t, fill=0.0)' in HMI
    assert 'cnt = _align_series_length(np.sum(mat[:, idxs] > thr, axis=1).astype(float), n_t, fill=0.0)' in HMI
    assert 'mdot_max = _align_series_length(np.nanmax(aq, axis=1) * 1000.0, n_t, fill=0.0)' in HMI
    assert 'mdot_active = _align_series_length(np.sum(aq > thr, axis=1).astype(float), n_t, fill=0.0)' in HMI
    assert 'a_fl = (_align_series_length(b.get("колесо_в_воздухе_ЛП", 0.0), n_t, fill=0.0) > 0.5).astype(float)' in HMI
    assert 'from .data_bundle import _align_series_length' in HMI
    assert 'm = _align_series_length(b.get(col, 0.0), n, fill=0.0) > 0.5' in HMI
    assert 'np.any(mat[:, idxs] > thr, axis=1),' in HMI
    assert 'np.any(np.abs(matq[:, idxs]) > thr_q, axis=1),' in HMI
    assert 'sid = _align_series_length(b.get("сегмент_id", 0.0), n, fill=0.0)' in HMI
    assert 'sid = np.rint(np.where(np.isfinite(sid), sid, 0.0)).astype(np.int32, copy=False)' in HMI
    assert 'if sid.size >= n and n > 1:' in HMI
    assert 'x_path_arr, y_path_arr = bundle.ensure_world_xy()' in APP
    assert 'xw_arr, yw_arr = b.ensure_world_xy()' in APP
    assert 'x0 = float(' in APP
    assert 'y0 = float(' in APP
    assert 'default=float(_g("путь_x_м", 0.0)),' in APP
    assert 'default=float(_g("путь_y_м", 0.0)),' in APP
    assert "animator falls back to derived world XY from solver скорости + yaw." in DATA_BUNDLE
    assert "def _align_series_length(arr: Any, n: int, *, fill: float = 0.0) -> np.ndarray:" in DATA_BUNDLE
    assert "without cyclic wraparound" in DATA_BUNDLE
    assert "pad_value = float(vec[-1]) if np.isfinite(float(vec[-1])) else float(fill)" in DATA_BUNDLE
    assert "from .data_bundle import CORNERS, DataBundle, _align_series_length, load_npz" in APP
    assert 't_series = np.asarray(b.t, dtype=float).reshape(-1)' in APP
    assert 'n_t = int(t_series.size)' in APP
    assert 'return _align_series_length(b.get(name, default), n_t, fill=float(default))' in APP
    assert 'vx_series = _align_series_length(vxb, n_t, fill=0.0)' in APP
    assert 'vy_series = _align_series_length(vyb, n_t, fill=0.0)' in APP
    assert 'yaw_rate_series = _align_series_length(b.ensure_yaw_rate_rad_s(), n_t, fill=0.0)' in APP
    assert 'ax_series = _align_series_length(axb, n_t, fill=0.0)' in APP
    assert 'ay_series = _align_series_length(ayb, n_t, fill=0.0)' in APP
    assert '"t": t_series,' in APP
    assert "seg_arr = _align_series_length(seg, int(n), fill=0.0)" in APP
    assert "seg = _align_series_length(seg, n, fill=0.0)" in APP
    assert "seg_full = _align_series_length(seg_full, required_n, fill=0.0)" in APP
    assert "s_world = _align_series_length(s_world, n, fill=0.0)" in APP
    assert "vx = _align_series_length(vx, n, fill=0.0)" in APP
    assert "vy = _align_series_length(vy, n, fill=0.0)" in APP
    assert "yaw_rate = _align_series_length(yaw_rate, n, fill=0.0)" in APP
    assert "ax = _align_series_length(ax, n, fill=0.0)" in APP
    assert "ay = _align_series_length(ay, n, fill=0.0)" in APP
    assert "speed = np.asarray(np.hypot(vx, vy), dtype=float)" in APP
    assert "zc = _align_series_length(zc, n, fill=0.0)" in APP
    assert "np.resize(seg, n)" not in APP
    assert "def ensure_yaw_rate_rad_s(self) -> np.ndarray:" in DATA_BUNDLE
    assert 'yaw_rate = _align_series_length(self.get("yaw_rate_рад_с", default=0.0), n, fill=0.0)' in DATA_BUNDLE
    assert 'yaw = np.asarray(np.unwrap(np.asarray(yaw, dtype=float)), dtype=float)' in DATA_BUNDLE
    assert 'yaw_rate = np.asarray(np.gradient(yaw, t, edge_order=1), dtype=float)' in DATA_BUNDLE
    assert "1) rotate canonical body-frame ``ax/ay`` into world frame;" in DATA_BUNDLE
    assert 'if self.main.has("скорость_vx_м_с") and self.main.has("скорость_vy_м_с"):' in DATA_BUNDLE
    assert 'if self.main.has("ускорение_продольное_ax_м_с2") and self.main.has("ускорение_поперечное_ay_м_с2"):' in DATA_BUNDLE
    assert 'vxw = vx * np.cos(yaw) - vy * np.sin(yaw)' in DATA_BUNDLE
    assert 'vyw = vx * np.sin(yaw) + vy * np.cos(yaw)' in DATA_BUNDLE
    assert 'axw = c * axb - s * ayb' in DATA_BUNDLE
    assert 'ayw = s * axb + c * ayb' in DATA_BUNDLE
    assert 'vxw, vyw = self.ensure_world_velocity_xy()' in DATA_BUNDLE
    assert 'axw = np.asarray(np.gradient(vxw, t, edge_order=1), dtype=float)' in DATA_BUNDLE
    assert 'ayw = np.asarray(np.gradient(vyw, t, edge_order=1), dtype=float)' in DATA_BUNDLE
    assert 'yaw = _align_series_length(self.get("yaw_рад", default=0.0), int(len(vxw)), fill=0.0)' in DATA_BUNDLE
    assert 'yaw = _align_series_length(self.get("yaw_рад", default=0.0), n, fill=0.0)' in DATA_BUNDLE
    assert 'axb = _align_series_length(self.get("ускорение_продольное_ax_м_с2", default=0.0), n, fill=0.0)' in DATA_BUNDLE
    assert 'ayb = _align_series_length(self.get("ускорение_поперечное_ay_м_с2", default=0.0), n, fill=0.0)' in DATA_BUNDLE
    assert "2) trapezoidal integration of canonical body-speed magnitude" in DATA_BUNDLE
    assert "hypot(скорость_vx_м_с, скорость_vy_м_с)" in DATA_BUNDLE
    assert "ds = np.where(np.isfinite(ds), np.maximum(ds, 0.0), 0.0)" in DATA_BUNDLE
    assert 'dx = vx * np.cos(yaw) - vy * np.sin(yaw)' in DATA_BUNDLE
    assert 'dy = vx * np.sin(yaw) + vy * np.cos(yaw)' in DATA_BUNDLE
    assert 'vxw = vx * np.cos(yaw) - vy * np.sin(yaw)' in DATA_BUNDLE
    assert 'vyw = vx * np.sin(yaw) + vy * np.cos(yaw)' in DATA_BUNDLE
    assert 'v = np.asarray(np.hypot(vx, vy), dtype=float)' in DATA_BUNDLE
    assert "v = np.where(np.isfinite(v), np.maximum(v, 0.0), 0.0)" in DATA_BUNDLE
    assert 'v = np.asarray(vx, dtype=float)' not in DATA_BUNDLE
    assert 'np.resize(vx, n)' not in DATA_BUNDLE
    assert 'np.resize(vy, n)' not in DATA_BUNDLE
    assert 'np.resize(yaw, n)' not in DATA_BUNDLE
    assert "deriving world XY from скорость_vx_м_с + yaw_рад as SERVICE/DERIVED." not in DATA_BUNDLE


def test_desktop_animator_hud_lookahead_uses_sampled_body_speed_truth() -> None:
    assert 'summary = _ensure_telemetry_summary_cache(b)' in APP
    assert 'np.asarray(summary["t"], dtype=float)' in APP
    assert 'yaw_series = summary["yaw"]' in APP
    assert 'vxb_series = summary["vx"]' in APP
    assert 'vyb_series = summary["vy"]' in APP
    assert 'yaw_rate_series = summary["yaw_rate"]' in APP
    assert 'ax_series = summary["ax"]' in APP
    assert 'ay_series = summary["ay"]' in APP
    assert 'v_mps = math.hypot(sample(vxb_series, 0.0), sample(vyb_series, 0.0))' in APP
    assert 'def _sample_signed_speed_along_world_path_local(' in APP
    assert 'xw_arr, yw_arr = b.ensure_world_xy()' in APP
    assert 'vxw_arr, vyw_arr = b.ensure_world_velocity_xy()' in APP
    assert 'yaw_value = float(' in APP
    assert '_sample_angle_series_local(' in APP
    assert 'vxw = float(body_vx * math.cos(yaw_value) - body_vy * math.sin(yaw_value))' in APP
    assert 'vyw = float(body_vx * math.sin(yaw_value) + body_vy * math.cos(yaw_value))' in APP
    assert 'tangent_x = float(tx / tangent_norm)' in APP
    assert 'tangent_y = float(ty / tangent_norm)' in APP
    assert 'v_proj = float(vxw * tangent_x + vyw * tangent_y)' in APP
    assert 'signed_speed_hint = _sample_signed_speed_along_world_path_local(' in APP
    assert 'return float(math.copysign(speed_mag, signed_speed_hint))' in APP
    assert 'v_forward_signed_m_s = _sample_signed_speed_along_world_path_local(' in APP
    assert 'default_signed_m_s=float(sample(vxb_series, 0.0)),' in APP
    assert 'self._lookahead_m = float(_clamp(20.0 + v_mps * 4.0, 40.0, 140.0))' in APP
    assert 'self._history_m = float(_clamp(8.0 + v_mps * 1.5, 15.0, 60.0))' in APP
    assert 'def _hud_motion_window_extents(self, *, signed_body_forward_m_s: float) -> tuple[float, float]:' in APP
    assert 'if np.isfinite(float(signed_body_forward_m_s)) and float(signed_body_forward_m_s) < -1e-6:' in APP
    assert 'hud_rear_m, hud_forward_m = self._hud_motion_window_extents(' in APP
    assert 'signed_body_forward_m_s=v_forward_signed_m_s,' in APP
    assert 'idx_ref = int(_clamp(int(sample_i0 if float(alpha) < 0.5 else sample_i1), 0, n - 1))' in APP
    assert 'win_i0 = max(0, idx_ref - 200)' in APP
    assert 'win_i1 = min(n, idx_ref + 400)' in APP
    assert 's0 = sample(s, float(s[idx_ref]))' in APP
    assert 's_idx_ref = int(_clamp(int(sample_i0 if float(alpha) < 0.5 else sample_i1), 0, max(0, len(s_world) - 1)))' in APP
    assert 'float(s_world[s_idx_ref])' in APP
    assert 'mask = (yl >= -float(hud_rear_m)) & (yl <= float(hud_forward_m))' in APP
    assert 'top_y = float(hud_forward_m) - 4.5' in APP
    assert 'scene_rect = QtCore.QRectF(-8.0, -float(hud_rear_m) - 4.0, 16.0, float(hud_forward_m + hud_rear_m) + 8.0)' in APP
    assert 'vx0 = sample(vx_series, 0.0)' not in APP
    assert 'v_forward_signed_m_s = float(sample(vxb_series, 0.0))' not in APP
    assert 'def _sampled_road_preview_window_m(' in APP
    assert 'signed_speed_m_s: float,' in APP
    assert 'return float(-lookahead_m), float(history_m)' in APP
    assert 'preview_back_m, preview_fwd_m = self._sampled_road_preview_window_m(' in APP
    assert 'signed_speed_m_s=float(speed_along_road),' in APP


def test_desktop_animator_subframe_yaw_uses_shortest_arc_sampling() -> None:
    assert 'def _sample_angle_series_local(' in APP
    assert 'delta = math.atan2(math.sin(a1 - a0), math.cos(a1 - a0))' in APP
    assert 'yaw = _sample_angle_series_local(' in APP
    assert 'yaw_series,' in APP
    assert 'yaw0 = _sample_angle_series_local(' in APP
    assert 'b.get("yaw_рад", 0.0),' in APP
    assert 'summary["yaw"],' in APP
    assert 'yaw_display = math.atan2(math.sin(yaw), math.cos(yaw))' in APP
    assert 'yaw = sample(yaw_series, 0.0)' not in APP
    assert 'yaw0 = _g("yaw_рад", 0.0)' not in APP
    assert 'yaw = sample(summary["yaw"], 0.0)' not in APP


def test_playback_service_interval_is_tightened_for_high_speed_without_restoring_busy_loop() -> None:
    assert 'base_ms = 8.0  # Fallback service cadence when no live present rate is known yet.' in APP
    assert 'changing playback speed' in APP
    assert 'target_ms = 500.0 * dense_dt_s' in APP
    assert 'def _playback_rearm_delay_ms(target_interval_ms: int, *, spent_s: float = 0.0) -> int:' in APP
    assert '4 ms' in APP
    assert 'two visual samples per solver step' in APP


def test_bundle_load_surfaces_validation_fallbacks_explicitly() -> None:
    assert 'def service_fallback_messages(self) -> List[str]:' in DATA_BUNDLE
    assert 'fallback_msgs = list(getattr(b, "service_fallback_messages", lambda: [])())' in APP
    assert 'check_report = run_self_checks(b)' in APP
    assert 'status_msg = (' in APP
    assert '"VALIDATION WARN: "' in APP
    assert 'f"fallback={len(fallback_msgs)} "' in APP
    assert 'code="bundle_validation_fallback"' in APP
    assert 'code="bundle_self_check"' in APP


def test_playhead_publishers_do_not_force_storage_churn_on_every_render() -> None:
    assert 'writeStorage(false);' in PLAYHEAD
    assert 'writeStorage(false);' in PLAYHEAD_UNIFIED
    assert 'else if (__perfPanelVisible)' in PLAYHEAD_UNIFIED


def test_web_followers_ignore_noop_storage_updates_while_paused() -> None:
    assert 'if (!changed && !__DIRTY) return;' in ROAD
    assert 'if (!__canAnimateNow()) return;' in ROAD

    assert 'if (!changed && !__DIRTY) return;' in MINIMAP
    assert 'if (!__canAnimateNow()) return;' in MINIMAP

    assert 'if (!changed && !__DIRTY) return;' in HEAT
    assert 'if (!__canAnimateNow()) return;' in HEAT

    assert 'if (!changed && !__DIRTY) return;' in QUAD
    assert 'if (!__canAnimateNow()) return;' in QUAD

    assert 'if (!__DIRTY && idxNow === __LAST_IDX) return;' in CAR3D
    assert 'if (!(st && st.playing) && stTs && stTs === lastExternalTs && stIdx === lastExternalIdx) return;' in MECH_ANIM
    assert 'if (!changed && !__FLOW_DIRTY) return;' in SVG_FLOW
