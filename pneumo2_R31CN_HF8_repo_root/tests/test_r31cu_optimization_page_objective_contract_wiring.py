from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'pneumo_solver_ui'
PAGE = ROOT / 'pages' / '03_Optimization.py'
LAUNCH = ROOT / 'optimization_launch_plan_runtime.py'
RUNNER = ROOT / 'opt_stage_runner_v1.py'
ARCHIVE = ROOT / 'calibration' / 'archive_influence_report_v1.py'


def test_r31cu_stage_runner_and_page_sources_share_objective_contract() -> None:
    page_src = PAGE.read_text(encoding='utf-8')
    launch_src = LAUNCH.read_text(encoding='utf-8')
    runner_src = RUNNER.read_text(encoding='utf-8')
    archive_src = ARCHIVE.read_text(encoding='utf-8')

    assert 'build_optimization_launch_plan(' in page_src
    assert 'for key in obj_keys:' in launch_src
    assert 'cmd += ["--objective", key]' in launch_src
    assert '"--penalty-key"' in launch_src
    assert 'objective_contract.json' in runner_src
    assert 'score_tuple_from_row' in runner_src
    assert 'objective_keys=objective_keys' in runner_src
    assert 'scalarize_score_tuple' in runner_src
    assert 'score_tuple_from_row' in archive_src
    assert 'scalarize_score_tuple' in archive_src
