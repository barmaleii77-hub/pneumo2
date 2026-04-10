from __future__ import annotations

import csv
import json
from pathlib import Path

from pneumo_dist.expdb import ExperimentDB


def test_export_run_to_csv_writes_scope_sidecars_and_scope_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    export_dir = tmp_path / "export"

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(
            problem_hash="ph_export_scope_1234567890",
            spec={
                "cfg": {
                    "objective_keys": ["legacy_objective"],
                    "penalty_key": "legacy_penalty",
                    "penalty_tol": 9.0,
                }
            },
            meta={
                "backend": "ray",
                "created_by": "pytest",
                "problem_hash_mode": "legacy",
                "objective_contract": {
                    "objective_keys": ["comfort", "energy"],
                    "penalty_key": "penalty_total",
                    "penalty_tol": 0.25,
                },
            },
        )
        reserve = db.reserve_trial(
            run_id=run_id,
            problem_hash="ph_export_scope_1234567890",
            param_hash="param_demo",
            x_u=[0.1, 0.2],
            params={"demo": 1},
        )
        db.mark_done(
            reserve.trial_id,
            y=[1.0, 2.0],
            g=[0.0],
            metrics={"comfort": 1.0, "energy": 2.0},
        )
        db.add_run_metric(
            run_id,
            key="hypervolume",
            value=0.5,
            json_blob={"completed": 1},
        )

        db.export_run_to_csv(run_id, out_dir=str(export_dir))

    run_scope = json.loads((export_dir / "run_scope.json").read_text(encoding="utf-8"))
    assert run_scope["schema"] == "expdb_run_scope_v1"
    assert run_scope["run_id"] == run_id
    assert run_scope["problem_hash"] == "ph_export_scope_1234567890"
    assert run_scope["problem_hash_short"] == "ph_export_sc"
    assert run_scope["problem_hash_mode"] == "legacy"
    assert run_scope["objective_keys"] == ["comfort", "energy"]
    assert run_scope["penalty_key"] == "penalty_total"
    assert float(run_scope["penalty_tol"]) == 0.25

    with (export_dir / "run_scope.csv").open(encoding="utf-8", newline="") as fh:
        scope_rows = list(csv.DictReader(fh))
    assert len(scope_rows) == 1
    assert scope_rows[0]["run_id"] == run_id
    assert scope_rows[0]["problem_hash_mode"] == "legacy"
    assert json.loads(scope_rows[0]["objective_keys_json"]) == ["comfort", "energy"]

    with (export_dir / "trials.csv").open(encoding="utf-8", newline="") as fh:
        trial_rows = list(csv.DictReader(fh))
    assert len(trial_rows) == 1
    assert trial_rows[0]["run_id"] == run_id
    assert trial_rows[0]["problem_hash"] == "ph_export_scope_1234567890"
    assert trial_rows[0]["problem_hash_mode"] == "legacy"
    assert trial_rows[0]["trial_id"] == reserve.trial_id

    with (export_dir / "run_metrics.csv").open(encoding="utf-8", newline="") as fh:
        metric_rows = list(csv.DictReader(fh))
    assert len(metric_rows) == 1
    assert metric_rows[0]["run_id"] == run_id
    assert metric_rows[0]["problem_hash"] == "ph_export_scope_1234567890"
    assert metric_rows[0]["problem_hash_mode"] == "legacy"
    assert metric_rows[0]["key"] == "hypervolume"
