from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_last_pointer_snapshot_helper_is_used_by_home_and_optimization_page() -> None:
    helper_src = (ROOT / "pneumo_solver_ui" / "optimization_last_pointer_snapshot.py").read_text(encoding="utf-8")
    ui_src = (ROOT / "pneumo_solver_ui" / "optimization_last_pointer_ui.py").read_text(encoding="utf-8")
    readonly_ui_src = (ROOT / "pneumo_solver_ui" / "optimization_page_readonly_ui.py").read_text(encoding="utf-8")
    contract_ui_src = (ROOT / "pneumo_solver_ui" / "optimization_contract_summary_ui.py").read_text(encoding="utf-8")
    home_src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    page_src = (ROOT / "pneumo_solver_ui" / "pages" / "03_Optimization.py").read_text(encoding="utf-8")

    assert "load_last_opt_ptr" in helper_src
    assert "summarize_optimization_run" in helper_src
    assert "summarize_run_packaging_snapshot" in helper_src
    assert "summarize_stage_policy_runtime" in helper_src
    assert "render_objective_contract_summary" in contract_ui_src
    assert "compare_objective_contract_to_current" in contract_ui_src
    assert "render_packaging_snapshot_summary" in ui_src
    assert "render_last_optimization_pointer_summary" in ui_src
    assert "render_objective_contract_summary" in ui_src
    assert "render_last_optimization_pointer_summary" in readonly_ui_src
    assert "render_last_optimization_overview_block" in readonly_ui_src
    assert "load_last_optimization_pointer_snapshot" in home_src
    assert "render_last_optimization_pointer_summary" in home_src
    assert "load_last_optimization_pointer_snapshot" in page_src
    assert "render_last_optimization_overview_block" in page_src
