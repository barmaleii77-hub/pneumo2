from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.pneumo_dist.trial_hash import make_problem_spec, stable_hash_problem


def _write_problem_files(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    model = tmp_path / 'model.py'
    worker = tmp_path / 'worker.py'
    base = tmp_path / 'base.json'
    ranges = tmp_path / 'ranges.json'
    suite = tmp_path / 'suite.json'

    model.write_text('P_ATM = 101325.0\n', encoding='utf-8')
    worker.write_text('def eval_candidate(*args, **kwargs):\n    return {}\n', encoding='utf-8')
    base.write_text(json.dumps({'fixed': 1.0, 'k': 10.0}, ensure_ascii=False), encoding='utf-8')
    ranges.write_text(json.dumps({'k': [5.0, 15.0]}, ensure_ascii=False), encoding='utf-8')
    suite.write_text(json.dumps({'tests': ['micro']}, ensure_ascii=False), encoding='utf-8')
    return {
        'model': model,
        'worker': worker,
        'base': base,
        'ranges': ranges,
        'suite': suite,
    }


def _make_spec(
    tmp_path: Path,
    *,
    objective_keys: list[str],
    penalty_key: str,
    penalty_tol: float,
):
    files = _write_problem_files(tmp_path)
    return make_problem_spec(
        model_path=str(files['model']),
        worker_path=str(files['worker']),
        base_json=str(files['base']),
        ranges_json=str(files['ranges']),
        suite_json=str(files['suite']),
        cfg={
            'objective_keys': list(objective_keys),
            'penalty_key': str(penalty_key),
            'penalty_tol': float(penalty_tol),
        },
        include_file_hashes=True,
    )


def test_r31cv_stable_problem_hash_changes_when_objective_or_penalty_contract_changes(tmp_path: Path) -> None:
    spec_a = _make_spec(tmp_path / 'a', objective_keys=['obj_a', 'obj_b'], penalty_key='penalty_a', penalty_tol=0.0)
    spec_b = _make_spec(tmp_path / 'b', objective_keys=['obj_a', 'obj_b'], penalty_key='penalty_b', penalty_tol=0.0)
    spec_c = _make_spec(tmp_path / 'c', objective_keys=['obj_a', 'obj_b'], penalty_key='penalty_a', penalty_tol=2.5)
    spec_d = _make_spec(tmp_path / 'd', objective_keys=['obj_a', 'obj_c'], penalty_key='penalty_a', penalty_tol=0.0)

    hash_a = stable_hash_problem(spec_a)
    assert hash_a != stable_hash_problem(spec_b)
    assert hash_a != stable_hash_problem(spec_c)
    assert hash_a != stable_hash_problem(spec_d)
