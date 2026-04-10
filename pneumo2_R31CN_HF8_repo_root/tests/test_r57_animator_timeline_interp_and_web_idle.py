from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    cylinder_visual_state_from_packaging,
    rod_internal_centerline_vertices_from_packaging_state,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')
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
    assert 'if interactive_scrub and heatmap_panel is not None and self._dock_is_exposed("dock_heatmap"):' in APP
    assert 'if interactive_scrub and corner_quick_panel is not None and self._dock_is_exposed("dock_corner_quick"):' in APP
    assert 'if interactive_scrub and road_profile_panel is not None and self._dock_is_exposed("dock_road_profile"):' in APP
    assert 'self.corner_table.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.corner_heatmap.update_frame(b, i, sample_t=sample_t)' in APP
    assert 'self.corner_quick.update_frame(b, i, sample_t=sample_t)' in APP
    assert 't = sample(summary["t"], 0.0)' in APP
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
    assert 'lambda: heatmap_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: corner_quick_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: road_profile_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: self.trends.update_frame(idx, sample_t=self._playback_sample_t_s),' in APP
    assert 'lambda: self.trends.update_frame(i, sample_t=self._playback_sample_t_s),' in APP


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
