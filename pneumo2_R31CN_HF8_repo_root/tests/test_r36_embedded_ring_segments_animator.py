from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ui_scenario_ring_hides_whole_ring_plot_under_debug_expander() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')
    assert 'DEBUG: кольцо целиком (не основной способ подсветки сегментов)' in src
    assert 'Основная цветовая подсветка сегментов должна быть в 3D и в cockpit animator.' in src


def test_pneumo_ui_app_embedded_animator_falls_back_to_anim_latest_npz_sidecar() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    assert 'load_ring_spec_from_npz' in src
    assert "st.session_state.get('anim_latest_npz')" in src
    assert "WORKSPACE_EXPORTS_DIR / 'anim_latest.npz'" in src
    assert 'load_ring_spec_from_npz(_npz_cand)' in src


def test_animation_cockpit_playhead_receives_segment_ranges() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'animation_cockpit_web.py').read_text(encoding='utf-8')
    assert 'segment_ranges=playhead_segment_ranges' in src
    assert 'build_segment_ranges_from_progress' in src
    assert 'Цветные полосы на таймлайне = сегменты кольца.' in src


def test_playhead_ctrl_has_segment_band_overlay_and_current_segment_label() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'components' / 'playhead_ctrl' / 'index.html').read_text(encoding='utf-8')
    assert 'segmentBar' in src
    assert 'segmentBand' in src
    assert 'segNow' in src
    assert 'renderSegmentBands' in src
    assert 'segment_ranges' in src


def test_mech_car3d_has_ring_segment_hud_and_current_segment_emphasis() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'components' / 'mech_car3d' / 'index.html').read_text(encoding='utf-8')
    assert 'pillSeg' in src
    assert '__ringCurrentSegment' in src
    assert 'const lineW = isCurrent ? 7 : 4;' in src
    assert 'drawRingRoadEmbedded(currentRingSeg);' in src
