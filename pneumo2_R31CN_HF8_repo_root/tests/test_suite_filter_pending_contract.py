from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pneumo_ui_app_applies_pending_stage_extend_before_widgets() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8')
    assert '_ui_suite_stage_filter_extend_pending' in src
    assert 'st.session_state["ui_suite_stage_filter"] = sorted(set(int(x) for x in (_merged_stage_filter or _stages.copy())))' in src


def test_ring_ui_queues_stage_filter_extend_instead_of_direct_widget_assignment() -> None:
    src = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')
    assert '_ui_suite_stage_filter_extend_pending' in src
    assert 'st.session_state["ui_suite_stage_filter"] = sorted(set(flt + [stage_i]))' not in src
