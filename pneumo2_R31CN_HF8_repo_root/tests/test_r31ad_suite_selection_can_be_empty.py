from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PNEUMO_UI_APP = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
LEGACY_APP = (ROOT / 'pneumo_solver_ui' / 'app.py').read_text(encoding='utf-8')
DEFAULT_SUITE = json.loads((ROOT / 'pneumo_solver_ui' / 'default_suite.json').read_text(encoding='utf-8'))
DEFAULT_SUITE_LONG = json.loads((ROOT / 'pneumo_solver_ui' / 'default_suite_long.json').read_text(encoding='utf-8'))
RING_EDITOR = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')


def test_main_suite_editor_uses_normal_selection_and_default_suite_disabled() -> None:
    assert 'load_optimization_ready_suite_rows' in PNEUMO_UI_APP
    assert 'load_default_suite_disabled(DEFAULT_SUITE_PATH)' not in PNEUMO_UI_APP
    assert 'st.session_state["ui_suite_selected_id"] = _cur_sel' in PNEUMO_UI_APP
    assert '_suite_select_options = list(_row_ids)' in PNEUMO_UI_APP
    assert 'format_func=lambda _id: _label_for_id(str(_id))' in PNEUMO_UI_APP
    assert '"(не выбрано)"' not in PNEUMO_UI_APP[PNEUMO_UI_APP.index('_suite_select_options = list(_row_ids)'):PNEUMO_UI_APP.index('with right:', PNEUMO_UI_APP.index('_suite_select_options = list(_row_ids)'))]
    assert '_ui_suite_clear_selection_once_r31ad' not in PNEUMO_UI_APP


def test_legacy_app_suite_editor_uses_normal_selection_and_default_suite_disabled() -> None:
    assert 'load_default_suite_disabled(DEFAULT_SUITE_PATH)' in LEGACY_APP
    assert 'options=idx_map' in LEGACY_APP
    assert 'options=[None] + idx_map' not in LEGACY_APP
    assert 'first_suite_selected_index' in LEGACY_APP
    assert '_suite_sel_clear_once_r31ad' not in LEGACY_APP


def test_shipped_default_suites_have_all_scenarios_disabled() -> None:
    assert DEFAULT_SUITE and DEFAULT_SUITE_LONG
    assert all(bool(row.get('включен', False)) is False for row in DEFAULT_SUITE)
    assert all(bool(row.get('включен', False)) is False for row in DEFAULT_SUITE_LONG)


def test_new_ring_scenarios_still_start_enabled_after_manual_creation() -> None:
    assert '"включен": True,' in RING_EDITOR
