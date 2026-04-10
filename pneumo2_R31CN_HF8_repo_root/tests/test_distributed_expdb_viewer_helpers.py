from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.distributed_expdb_viewer_helpers import (
    find_expdb_paths,
    load_packaging_params_for_run,
    load_run_problem_scope,
)


class _FakeDB:
    def __init__(self, run_detail):
        self._run_detail = run_detail

    def get_run(self, run_id: str):
        return dict(self._run_detail)


def test_find_expdb_paths_collects_supported_databases(tmp_path: Path) -> None:
    newer = tmp_path / "runs" / "dist_runs" / "alpha" / "experiments.duckdb"
    newer.parent.mkdir(parents=True, exist_ok=True)
    newer.write_text("", encoding="utf-8")

    older = tmp_path / "runs_distributed" / "experiments.sqlite"
    older.parent.mkdir(parents=True, exist_ok=True)
    older.write_text("", encoding="utf-8")

    found = find_expdb_paths(tmp_path)

    found_text = [str(path) for path in found]
    assert str(newer.resolve()) in found_text
    assert str(older.resolve()) in found_text


def test_load_packaging_params_for_run_resolves_relative_base_json_near_db(tmp_path: Path) -> None:
    db_path = tmp_path / "runs" / "dist_runs" / "beta" / "experiments.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("", encoding="utf-8")
    base_json = db_path.parent / "base.json"
    base_json.write_text(
        json.dumps({"autoverif_midstroke_t0_max_error_m": 0.012}, ensure_ascii=False),
        encoding="utf-8",
    )

    fake_db = _FakeDB({"spec": {"base_json": "base.json"}, "meta": {}})

    params = load_packaging_params_for_run(fake_db, "run-1", db_path, tmp_path)

    assert float(params["autoverif_midstroke_t0_max_error_m"]) == 0.012


def test_load_run_problem_scope_prefers_explicit_meta_mode_and_contract() -> None:
    run_scope = load_run_problem_scope(
        {
            "run_id": "run-1",
            "problem_hash": "ph_demo_scope_1234567890",
            "spec": {
                "cfg": {
                    "objective_keys": ["legacy_obj"],
                    "penalty_key": "legacy_penalty",
                }
            },
            "meta": {
                "problem_hash_mode": "legacy",
                "objective_contract": {
                    "objective_keys": ["comfort", "energy"],
                    "penalty_key": "penalty_total",
                    "penalty_tol": 0.25,
                },
            },
        }
    )

    assert run_scope["problem_hash"] == "ph_demo_scope_1234567890"
    assert run_scope["problem_hash_short"] == "ph_demo_scop"
    assert run_scope["problem_hash_mode"] == "legacy"
    assert run_scope["objective_keys"] == ("comfort", "energy")
    assert run_scope["penalty_key"] == "penalty_total"
    assert float(run_scope["penalty_tol"]) == 0.25
