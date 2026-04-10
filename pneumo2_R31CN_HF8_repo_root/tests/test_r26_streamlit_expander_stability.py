from __future__ import annotations

from pathlib import Path


def _src(rel: str) -> str:
    return (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")


def test_ui_scenario_ring_segment_expander_label_is_stable() -> None:
    src = _src("pneumo_solver_ui/ui_scenario_ring.py")
    assert 'with st.expander(summary, expanded=False):' not in src
    assert 'with st.expander(f"Сегмент {idx + 1}", expanded=False):' in src


def test_playhead_and_events_expanders_do_not_use_dynamic_labels() -> None:
    for rel in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = _src(rel)
        assert 'with st.expander(f"События/алёрты (' not in src
        assert 'with st.expander(f"Текущие значения при t=' not in src
    event_src = _src("pneumo_solver_ui/ui_event_panel_helpers.py")
    playhead_src = _src("pneumo_solver_ui/ui_playhead_value_helpers.py")
    assert 'with st.expander("События/алёрты", expanded=False):' in event_src
    assert 'title: str = "Текущие значения (playhead)"' in playhead_src


def test_param_influence_pareto_expander_label_is_stable() -> None:
    src = _src("pneumo_solver_ui/param_influence_ui.py")
    assert 'with st.expander(f"Pareto-front точки (' not in src
    assert 'with st.expander("Pareto-front точки", expanded=False):' in src
