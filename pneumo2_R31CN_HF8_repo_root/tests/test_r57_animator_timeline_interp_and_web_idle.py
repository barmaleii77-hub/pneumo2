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
    assert 'sample_t=self._playback_sample_t_s if bool(playing) else None' in APP
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
    assert 's0 = sample(s, float(s[idx]))' in APP
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
    assert 'vx_status = _sample_series_local(vxw, i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'vy_status = _sample_series_local(vyw, i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'vxb_status, vyb_status = b.ensure_body_velocity_xy()' in APP
    assert 'vb_x = _sample_series_local(' in APP
    assert 'vb_y = _sample_series_local(' in APP
    assert 'v = float(math.hypot(float(vx_status), float(vy_status)))' in APP
    assert 'v = float(math.hypot(float(vb_x), float(vb_y)))' in APP
    assert 'x_path_arr, y_path_arr = bundle.ensure_world_xy()' in APP
    assert 'xw_arr, yw_arr = b.ensure_world_xy()' in APP
    assert 'x0 = float(' in APP
    assert 'y0 = float(' in APP
    assert 'default=float(_g("путь_x_м", 0.0)),' in APP
    assert 'default=float(_g("путь_y_м", 0.0)),' in APP
    assert "deriving world XY from скорость_vx_м_с + скорость_vy_м_с + yaw_рад as SERVICE/DERIVED." in DATA_BUNDLE
    assert "def _align_series_length(arr: Any, n: int, *, fill: float = 0.0) -> np.ndarray:" in DATA_BUNDLE
    assert "without cyclic wraparound" in DATA_BUNDLE
    assert "pad_value = float(vec[-1]) if np.isfinite(float(vec[-1])) else float(fill)" in DATA_BUNDLE
    assert "def ensure_yaw_rate_rad_s(self) -> np.ndarray:" in DATA_BUNDLE
    assert 'yaw_rate = _align_series_length(self.get("yaw_rate_рад_с", default=0.0), n, fill=0.0)' in DATA_BUNDLE
    assert 'yaw = np.asarray(np.unwrap(np.asarray(yaw, dtype=float)), dtype=float)' in DATA_BUNDLE
    assert 'yaw_rate = np.asarray(np.gradient(yaw, t, edge_order=1), dtype=float)' in DATA_BUNDLE
    assert "1) derivative of world-frame velocity from ``ensure_world_velocity_xy()``;" in DATA_BUNDLE
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
    assert 'vxb_series, vyb_series = b.ensure_body_velocity_xy()' in APP
    assert 'v_mps = math.hypot(sample(vxb_series, 0.0), sample(vyb_series, 0.0))' in APP
    assert 'def _sample_signed_speed_along_world_path_local(' in APP
    assert 'xw_arr, yw_arr = b.ensure_world_xy()' in APP
    assert 'vxw_arr, vyw_arr = b.ensure_world_velocity_xy()' in APP
    assert 'tangent_x = float(tx / tangent_norm)' in APP
    assert 'tangent_y = float(ty / tangent_norm)' in APP
    assert 'v_proj = float(vxw * tangent_x + vyw * tangent_y)' in APP
    assert 'v_forward_signed_m_s = _sample_signed_speed_along_world_path_local(' in APP
    assert 'default_signed_m_s=float(sample(vxb_series, 0.0)),' in APP
    assert 'self._lookahead_m = float(_clamp(20.0 + v_mps * 4.0, 40.0, 140.0))' in APP
    assert 'self._history_m = float(_clamp(8.0 + v_mps * 1.5, 15.0, 60.0))' in APP
    assert 'def _hud_motion_window_extents(self, *, signed_body_forward_m_s: float) -> tuple[float, float]:' in APP
    assert 'if np.isfinite(float(signed_body_forward_m_s)) and float(signed_body_forward_m_s) < -1e-6:' in APP
    assert 'hud_rear_m, hud_forward_m = self._hud_motion_window_extents(' in APP
    assert 'signed_body_forward_m_s=v_forward_signed_m_s,' in APP
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
    assert 'base_ms = 12.0  # ~83 Hz keeps x1.0 visibly alive without source-frame chasing.' in APP
    assert 'base_ms = 10.0  # ~100 Hz for moderate fast-forward.' in APP
    assert 'base_ms = 8.0   # ~125 Hz.' in APP
    assert 'base_ms = 6.0   # ~166 Hz upper service cadence on Windows precise timer.' in APP
    assert '4 ms' in APP


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
