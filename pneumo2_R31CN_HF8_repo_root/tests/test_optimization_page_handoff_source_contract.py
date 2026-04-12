from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_optimization_page_wires_live_coordinator_handoff_actions() -> None:
    src = (
        ROOT / "pneumo_solver_ui" / "pages" / "03_Optimization.py"
    ).read_text(encoding="utf-8")

    assert "start_coordinator_handoff_job_with_feedback" in src
    assert "start_handoff_fn=lambda source_run_dir: start_coordinator_handoff_job_with_feedback(" in src
    assert "start_handoff_job_fn=lambda source_run_dir: start_coordinator_handoff_job_with_feedback(" in src
