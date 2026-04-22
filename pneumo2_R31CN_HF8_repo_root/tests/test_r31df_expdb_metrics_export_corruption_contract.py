from __future__ import annotations

import csv
from pathlib import Path

from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB


def test_r31df_fetch_metrics_tolerates_corrupted_legacy_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31df_metrics", spec={}, meta={"source": "pytest"})
        db.add_run_metric(run_id, key="ok_metric", value=1.5, json_blob={"ok": True})
        db.execute(
            "INSERT INTO run_metrics(run_id, ts, key, value, json) VALUES(?,?,?,?,?);",
            [run_id, "bad-ts", "legacy_bad", "not-a-float", '{"broken_json":'],
        )

        rows = db.fetch_metrics(run_id, key=None, limit=100)

    bad_row = next(row for row in rows if row["key"] == "legacy_bad")
    assert bad_row["ts"] == 0.0
    assert bad_row["value"] is None
    assert bad_row["json"] is None


def test_r31df_export_run_to_csv_survives_corrupted_metrics_payloads(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    export_dir = tmp_path / "export"
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31df_export", spec={}, meta={"source": "pytest"})
        reserve = db.reserve_trial(
            run_id=run_id,
            problem_hash="ph_r31df_export",
            param_hash="param_r31df",
            x_u=[0.1, 0.2],
            params={"x0": 0.1, "x1": 0.2},
        )
        db.mark_done(
            reserve.trial_id,
            y=[1.0, 2.0],
            g=[0.0],
            metrics={"obj1": 1.0, "obj2": 2.0},
        )
        # Corrupt persisted trial metrics JSON (legacy damaged DB scenario).
        db.execute("UPDATE trials SET metrics_json=? WHERE trial_id=?;", ['{"broken_trial_metrics":', reserve.trial_id])
        # Corrupt run-metric row (bad ts/value/json).
        db.execute(
            "INSERT INTO run_metrics(run_id, ts, key, value, json) VALUES(?,?,?,?,?);",
            [run_id, "bad-ts", "legacy_bad", "not-a-float", '{"broken_json":'],
        )

        db.export_run_to_csv(run_id, out_dir=str(export_dir))

    trials_csv = export_dir / "trials.csv"
    metrics_csv = export_dir / "run_metrics.csv"
    assert trials_csv.exists()
    assert metrics_csv.exists()

    with trials_csv.open("r", encoding="utf-8", newline="") as fh:
        trial_rows = list(csv.DictReader(fh))
    assert len(trial_rows) == 1
    assert trial_rows[0]["metrics_json"] == "null"

    with metrics_csv.open("r", encoding="utf-8", newline="") as fh:
        metric_rows = list(csv.DictReader(fh))
    legacy_rows = [row for row in metric_rows if row.get("key") == "legacy_bad"]
    assert legacy_rows, "Expected corrupted legacy metric row to be exported safely."
    assert legacy_rows[0]["value"] == ""
