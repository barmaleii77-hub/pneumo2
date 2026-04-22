from __future__ import annotations

import csv
import math
from pathlib import Path

from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB


def test_expdb_legacy_runner_api_compatibility(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"

    with ExperimentDB(db_path, engine="sqlite") as db:
        db.connect()
        db.add_run("run_legacy", problem_hash="ph_legacy", meta={"runner": "legacy"}, status="running")
        assert db.get_run("run_legacy")["meta"]["status"] == "running"

        reserve = db.reserve_trial(
            "run_legacy",
            "ph_legacy",
            "param_a",
            params={"a": 1.0},
            x_u=[0.1, 0.2],
            source="propose",
        )
        trial_id, inserted = reserve
        assert inserted is True

        db.mark_started(trial_id, worker_id="ray")
        db.mark_done(
            trial_id,
            metrics={"comfort": 1.2, "energy": 2.3},
            obj1=1.2,
            obj2=2.3,
            penalty=0.4,
            status="cached",
        )

        counts = db.count_status("run_legacy")
        assert counts["cached"] == 1
        assert counts["done"] == 0

        X_u, Y_min, penalty = db.fetch_dataset_arrays("run_legacy")
        assert X_u.shape == (1, 2)
        assert [float(v) for v in Y_min[0].tolist()] == [1.2, 2.3]
        assert float(penalty[0]) == 0.4

        reserve_err = db.reserve_trial(
            "run_legacy",
            "ph_legacy",
            "param_b",
            params={"b": 2.0},
            x_u=[0.3, 0.4],
        )
        db.mark_error(reserve_err.trial_id, error="worker failed", traceback_str="trace line")
        trial_err = db.get_trial(reserve_err.trial_id)
        assert trial_err is not None
        assert "worker failed" in trial_err.error_text
        assert "trace line" in trial_err.error_text

        db.update_run_status("run_legacy", "done")
        assert db.get_run("run_legacy")["meta"]["status"] == "done"


def test_expdb_legacy_cache_and_metrics_helpers(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    with ExperimentDB(db_path, engine="sqlite") as db:
        db.add_run("run_metrics", problem_hash="ph_metrics", status="running")

        db.put_cache(
            "ph_metrics",
            "param_cache",
            metrics={"score": 11.0},
            obj1=5.0,
            obj2=6.0,
            penalty=0.7,
        )
        cached = db.get_cached("ph_metrics", "param_cache")
        assert cached is not None
        assert float(cached["obj1"]) == 5.0
        assert float(cached["obj2"]) == 6.0
        assert float(cached["penalty"]) == 0.7

        db.add_metric(
            "run_metrics",
            completed=1,
            submitted=2,
            n_feasible=1,
            hypervolume=0.5,
            best_obj1=5.0,
            best_obj2=6.0,
            info={"inflight": 1},
        )
        keys = [row["key"] for row in db.fetch_metrics("run_metrics", key=None, limit=100)]
        assert "progress" in keys
        assert "hv" in keys


def test_expdb_legacy_get_cached_returns_floatable_nans_for_missing_values(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    with ExperimentDB(db_path, engine="sqlite") as db:
        db.add_run("run_nan_compat", problem_hash="ph_nan", status="running")
        db.put_cache("ph_nan", "param_nan", metrics={})
        cached = db.get_cached("ph_nan", "param_nan")
        assert cached is not None
        assert math.isnan(float(cached["obj1"]))
        assert math.isnan(float(cached["obj2"]))
        assert math.isnan(float(cached["penalty"]))


def test_expdb_reserve_trial_uses_only_usable_cache_payloads(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    with ExperimentDB(db_path, engine="sqlite") as db:
        db.add_run("run_cache_gate", problem_hash="ph_cache_gate", status="running")

        # Empty cache payload should not be treated as DONE.
        db.put_cache("ph_cache_gate", "param_empty", metrics={})
        reserve_empty = db.reserve_trial(
            "run_cache_gate",
            "ph_cache_gate",
            "param_empty",
            x_u=[0.1, 0.2],
            params={"a": 1.0},
        )
        assert reserve_empty.status == "PENDING"
        assert reserve_empty.from_cache is False

        # Metrics-only cache payload with obj1/obj2 should still hydrate a cache hit.
        db.upsert_cache(
            problem_hash="ph_cache_gate",
            param_hash="param_metrics_only",
            y=[],
            g=None,
            metrics={"obj1": 1.5, "obj2": 2.5, "penalty": 0.05},
        )
        reserve_metrics = db.reserve_trial(
            "run_cache_gate",
            "ph_cache_gate",
            "param_metrics_only",
            x_u=[0.3, 0.4],
            params={"b": 2.0},
        )
        assert reserve_metrics.status == "DONE"
        assert reserve_metrics.from_cache is True
        assert [float(v) for v in reserve_metrics.y or []] == [1.5, 2.5]
        assert [float(v) for v in reserve_metrics.g or []] == [0.05]


def test_expdb_export_supports_legacy_output_file_arguments(tmp_path: Path) -> None:
    db_path = tmp_path / "experiments.sqlite"
    export_trials = tmp_path / "legacy_export" / "trials_legacy.csv"
    export_metrics = tmp_path / "legacy_export" / "run_metrics_legacy.csv"

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.add_run("run_export", problem_hash="ph_export", status="running")
        reserve = db.reserve_trial(
            run_id="run_export",
            problem_hash="ph_export",
            param_hash="param_export",
            x_u=[0.2, 0.4],
            params={"k": 1.0},
        )
        db.mark_done(
            reserve.trial_id,
            y=[1.0, 2.0],
            g=[0.0],
            metrics={"comfort": 1.0, "energy": 2.0},
        )
        db.add_run_metric("run_export", key="hv", value=0.1, json_blob={"completed": 1})
        db.export_run_to_csv(run_id, str(export_trials), str(export_metrics))

    assert export_trials.exists()
    assert export_metrics.exists()
    assert (export_trials.parent / "run_scope.json").exists()
    assert (export_trials.parent / "run_scope.csv").exists()
    with export_trials.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run_export"
