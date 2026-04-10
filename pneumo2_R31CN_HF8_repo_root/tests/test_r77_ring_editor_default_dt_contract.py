from __future__ import annotations

from pathlib import Path


def test_ring_editor_passes_explicit_default_dt_to_generator() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    assert "def _resolve_ring_default_dt_s(" in src
    assert 'st.session_state.get("ui_suite_selected_id")' in src
    assert 'default_dt_s=float(ring_default_dt_s)' in src
    assert "return fallback_dt_s" in src
