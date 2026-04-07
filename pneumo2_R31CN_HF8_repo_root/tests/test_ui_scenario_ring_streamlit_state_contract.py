from __future__ import annotations

from pathlib import Path


def test_ui_scenario_ring_does_not_self_assign_streamlit_widget_keys() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")
    forbidden = [
        'st.session_state["ring_n_laps"] =',
        'st.session_state["ring_seed"] =',
        'st.session_state["ring_dx_m"] =',
        'st.session_state["ring_test_name"] =',
        'st.session_state["ring_test_desc"] =',
        'st.session_state["ring_dt_s"] =',
        'st.session_state["ring_stage_num"] =',
    ]
    for needle in forbidden:
        assert needle not in src, needle


def test_render_segment_editor_invalid_mode_warning_uses_idx_not_free_i() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")
    assert 'Сегмент {i}:' not in src
    assert 'Сегмент {idx+1}:' in src or 'Сегмент {idx + 1}:' in src
