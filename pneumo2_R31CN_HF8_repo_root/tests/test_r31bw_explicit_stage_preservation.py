from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r31bw_stage_runner_skips_empty_earlier_stage_instead_of_failing() -> None:
    src = (ROOT / "pneumo_solver_ui" / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert 'stage_skipped_empty_suite' in src
    assert 'explicit suite stages are preserved and earlier empty stages are skipped' in src
    assert 'failed_all_stage_suites_empty' in src


def test_r31bw_stage_help_explains_cumulative_entry_semantics() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    assert 'Момент входа теста в staged optimization' in src
    assert 'stage 1 не должен молча переписываться в 0' in src
