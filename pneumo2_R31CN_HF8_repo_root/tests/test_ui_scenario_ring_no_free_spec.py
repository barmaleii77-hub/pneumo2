from __future__ import annotations

from pathlib import Path


def test_render_segment_editor_source_does_not_reference_outer_spec_freevar() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")
    marker = "def _render_segment_editor"
    start = src.index(marker)
    tail = src[start:]
    next_def = tail.find("\ndef ", len(marker))
    block = tail if next_def < 0 else tail[:next_def]
    assert "spec.get(" not in block
