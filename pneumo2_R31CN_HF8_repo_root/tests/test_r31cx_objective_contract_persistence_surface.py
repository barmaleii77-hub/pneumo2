from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'pneumo_solver_ui'
COORD = ROOT / 'tools' / 'dist_opt_coordinator.py'
DETAILS = ROOT / 'optimization_run_history_details_ui.py'
SUMMARY = ROOT / 'optimization_contract_summary_ui.py'
RUN_HISTORY = ROOT / 'optimization_run_history.py'


def test_r31cx_coordinator_and_ui_surface_objective_contract_persistence() -> None:
    coord_src = COORD.read_text(encoding='utf-8')
    details_src = DETAILS.read_text(encoding='utf-8')
    summary_src = SUMMARY.read_text(encoding='utf-8')
    hist_src = RUN_HISTORY.read_text(encoding='utf-8')

    assert 'objective_contract.json' in coord_src
    assert 'objective_contract_payload(' in coord_src
    assert 'penalty_tol=float(args.penalty_tol)' in coord_src

    assert 'Файл objective-contract:' in summary_src
    assert 'contract_diff_bits = compare_objective_contract_to_current(' in details_src
    assert 'resume/cache уже различает такие контракты по problem_hash' in summary_src

    assert "problem_spec_cfg_fallback" in hist_src
    assert 'objective_contract_path' in hist_src
