from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_input_contract import normalize_suite_stage_numbers

ROOT = Path(__file__).resolve().parents[1]


def test_r31bj_ring_editor_uses_explicit_widget_key_and_zero_min() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')
    assert 'key="ring_stage_num"' in src
    assert 'st.session_state["ring_stage_num"] = int(_ring_stage_default)' in src
    assert 'min_value=0,' in src


def test_r31bj_suite_card_stage_uses_explicit_key_and_zero_default() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    assert '_stage_default = max(0, int(st.session_state.get(_stage_key, infer_suite_stage(rec)) or 0))' in src
    assert '_stage_key = _suite_editor_widget_key(sid, "stage")' in src
    assert 'key=_stage_key' in src
    assert 'min_value=0' in src


def test_r31bj_stage_display_is_explicitly_zero_based() -> None:
    app_src = (ROOT / 'pneumo_solver_ui' / 'app.py').read_text(encoding='utf-8')
    ui_src = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    expected = '(idx={stage_idx}, 0-based; всего стадий: {max(1, stage_total)})'
    assert expected in app_src
    assert expected in ui_src


def test_r31bj_negative_stage_values_are_clamped_to_zero() -> None:
    suite = [
        {'имя': 'bad_neg', 'стадия': -3, 'включен': True},
        {'имя': 'good_zero', 'стадия': 0, 'включен': True},
    ]
    normalized, audit = normalize_suite_stage_numbers(suite)
    assert normalized[0]['стадия'] == 0
    assert audit['clamped_negative_rows'] == 1
    assert audit['after']['enabled_stage_counts']['0'] == 2
