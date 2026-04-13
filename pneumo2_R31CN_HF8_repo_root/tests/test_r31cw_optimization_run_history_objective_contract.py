from __future__ import annotations

import csv
from pathlib import Path

from pneumo_solver_ui.optimization_objective_contract import objective_contract_payload
from pneumo_solver_ui.optimization_run_history import summarize_optimization_run


def test_r31cw_run_history_reads_objective_contract_for_coordinator_run(tmp_path: Path) -> None:
    run_dir = tmp_path / 'p_coordinator_demo'
    export_dir = run_dir / 'export'
    export_dir.mkdir(parents=True)

    (run_dir / 'coordinator.log').write_text('started\n', encoding='utf-8')
    (run_dir / 'run_id.txt').write_text('run_demo_001\n', encoding='utf-8')
    (run_dir / 'objective_contract.json').write_text(
        __import__('json').dumps(
            objective_contract_payload(
                objective_keys=['comfort', 'roll', 'energy'],
                penalty_key='penalty_total',
                penalty_tol=1.25,
                source='dist_opt_coordinator_R59',
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    with (export_dir / 'trials.csv').open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['trial_id', 'status', 'error_text', 'g_json', 'y_json', 'metrics_json'])
        writer.writeheader()
        writer.writerow({
            'trial_id': '1',
            'status': 'DONE',
            'error_text': '',
            'g_json': '[0.0]',
            'y_json': '[1.0, 2.0, 3.0]',
            'metrics_json': '{"comfort": 1.0, "roll": 2.0, "energy": 3.0, "penalty_total": 0.0}',
        })
        writer.writerow({'trial_id': '2', 'status': 'ERROR', 'error_text': 'boom', 'g_json': '', 'y_json': '', 'metrics_json': ''})

    summary = summarize_optimization_run(run_dir)
    assert summary is not None
    assert summary.pipeline_mode == 'coordinator'
    assert summary.objective_keys == ('comfort', 'roll', 'energy')
    assert summary.penalty_key == 'penalty_total'
    assert summary.penalty_tol == 1.25
    assert summary.objective_contract_path == run_dir / 'objective_contract.json'
    assert summary.runtime_summary is not None
    assert summary.runtime_summary['trial_health'] == {'done': 1, 'running': 0, 'error': 1}
    assert summary.runtime_summary['penalty_gate'] == {}
    assert summary.runtime_summary['recent_errors'] == ['boom']


def test_r31cw_run_history_falls_back_to_problem_spec_cfg_when_explicit_contract_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / 'p_coordinator_cfg_only'
    export_dir = run_dir / 'export'
    export_dir.mkdir(parents=True)
    (run_dir / 'coordinator.log').write_text('started\n', encoding='utf-8')
    (run_dir / 'run_id.txt').write_text('run_demo_002\n', encoding='utf-8')
    (run_dir / 'problem_spec.json').write_text(
        '{"cfg": {"objective_keys": ["comfort", "roll"], "penalty_key": "penalty_total", "penalty_tol": 0.5}}',
        encoding='utf-8',
    )
    with (export_dir / 'trials.csv').open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['status', 'error_text'])
        writer.writeheader()
        writer.writerow({'status': 'DONE', 'error_text': ''})

    summary = summarize_optimization_run(run_dir)
    assert summary is not None
    assert summary.objective_keys == ('comfort', 'roll')
    assert summary.penalty_key == 'penalty_total'
    assert summary.penalty_tol == 0.5
    assert summary.objective_source == 'problem_spec_cfg_fallback'
    assert summary.objective_contract_path == run_dir / 'problem_spec.json'


def test_r31cw_run_history_keeps_string_objective_keys_from_problem_spec_cfg(tmp_path: Path) -> None:
    run_dir = tmp_path / 'p_coordinator_cfg_string'
    export_dir = run_dir / 'export'
    export_dir.mkdir(parents=True)
    (run_dir / 'coordinator.log').write_text('started\n', encoding='utf-8')
    (run_dir / 'run_id.txt').write_text('run_demo_003\n', encoding='utf-8')
    (run_dir / 'problem_spec.json').write_text(
        '{"cfg": {"objective_keys": "comfort\\nroll;energy", "penalty_key": "penalty_total", "penalty_tol": 1.5}}',
        encoding='utf-8',
    )
    with (export_dir / 'trials.csv').open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['status', 'error_text'])
        writer.writeheader()
        writer.writerow({'status': 'DONE', 'error_text': ''})

    summary = summarize_optimization_run(run_dir)
    assert summary is not None
    assert summary.objective_keys == ('comfort', 'roll', 'energy')
    assert summary.penalty_key == 'penalty_total'
    assert summary.penalty_tol == 1.5
