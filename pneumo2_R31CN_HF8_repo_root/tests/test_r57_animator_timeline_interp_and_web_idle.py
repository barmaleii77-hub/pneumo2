from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    cylinder_visual_state_from_packaging,
    rod_internal_centerline_vertices_from_packaging_state,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')
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
    assert np.allclose(inner[0], np.asarray(state['rod_seg'][0], dtype=float), atol=1e-12)
    assert np.allclose(inner[1], np.asarray(state['housing_seg'][1], dtype=float), atol=1e-12)
    assert float(np.linalg.norm(inner[1] - inner[0])) > 1e-9


def test_front_and_side_helper_views_now_accept_continuous_sample_t() -> None:
    assert 'def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):' in APP
    assert APP.count('def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):') >= 3
    assert APP.count('_sample_series_local(') >= 2
    assert 'if panel in (self.hud, self.axleF, self.axleR, self.sideL, self.sideR):' in APP
    assert 'sample_t=self._playback_sample_t_s if bool(playing) else None' in APP


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
