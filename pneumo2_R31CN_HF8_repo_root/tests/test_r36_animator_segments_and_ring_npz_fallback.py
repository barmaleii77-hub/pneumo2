from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pneumo_ui_app_has_ring_visual_npz_fallback_and_exports_dir_sidecar_search() -> None:
    ui_src = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    helper_src = (ROOT / 'pneumo_solver_ui' / 'ui_mech_animation_helpers.py').read_text(encoding='utf-8')
    assert 'load_ring_spec_from_npz' in ui_src
    assert 'WORKSPACE_EXPORTS_DIR' in ui_src
    assert 'session_state.get("anim_latest_npz")' in helper_src
    assert 'ring_visual_loaded_from_npz_sidecar' in helper_src


def test_ui_scenario_ring_keeps_whole_ring_overlay_only_in_debug_expander() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')
    assert 'DEBUG: кольцо целиком (не основной способ подсветки сегментов)' in src
    assert 'expanded=False' in src
    assert 'Основная цветовая подсветка сегментов должна быть в 3D и в cockpit animator' in src


def test_playhead_ctrl_has_segment_band_timeline_and_current_segment_badge() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'components' / 'playhead_ctrl' / 'index.html').read_text(encoding='utf-8')
    assert 'segment_ranges' in src
    assert 'segmentBar' in src
    assert 'renderSegmentBands' in src
    assert 'segNow' in src
    assert 'currentSegment()' in src


def test_mech_car3d_has_current_segment_pill_and_thick_segment_edges() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'components' / 'mech_car3d' / 'index.html').read_text(encoding='utf-8')
    assert 'pillSeg' in src
    assert '__ringCurrentSegment' in src
    assert 'lineW = isCurrent ? 7 : 4' in src
    assert 'boundaryW = isCurrent ? 5 : 3' in src
    assert 'drawRingRoadEmbedded(currentRingSeg)' in src
