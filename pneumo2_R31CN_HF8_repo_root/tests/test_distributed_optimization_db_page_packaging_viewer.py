from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_distributed_db_page_uses_current_api_and_shared_packaging_surface() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pages" / "03_DistributedOptimizationDB.py").read_text(encoding="utf-8")

    assert "find_expdb_paths" in src
    assert "load_packaging_params_for_run" in src
    assert "load_run_problem_scope" in src
    assert "flatten_trial_rows" in src
    assert "enrich_packaging_surface_df" in src
    assert "apply_packaging_surface_filters" in src
    assert "render_packaging_surface_metrics" in src
    assert "packaging_surface_result_columns" in src
    assert "db.list_runs(" in src
    assert "db.get_run(" in src
    assert "db.count_by_status(" in src
    assert "db.fetch_metrics(" in src
    assert "db.fetch_trials(" in src
    assert "problem_hash_mode" in src
    assert "Selected run scope:" in src
    assert "resolved_problem_scope" in src
    assert "_exec(" not in src
    assert "list_metrics(" not in src
