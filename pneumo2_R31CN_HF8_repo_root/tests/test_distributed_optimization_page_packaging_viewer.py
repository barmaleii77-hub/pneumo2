from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_distributed_optimization_page_uses_current_expdb_api_and_packaging_filters() -> None:
    src = (ROOT / "pneumo_solver_ui" / "pages" / "20_DistributedOptimization.py").read_text(encoding="utf-8")

    assert "enrich_packaging_surface_df" in src
    assert "apply_packaging_surface_filters" in src
    assert "render_packaging_surface_metrics" in src
    assert "packaging_surface_result_columns" in src
    assert "db.get_run(run_id)" in src
    assert "db.count_by_status(run_id)" in src
    assert "_done_trials_objective_rows" in src
    assert 'key_prefix="dist"' in src
    assert "fetch_dataset_arrays" not in src
    assert "count_status" not in src
    assert ".connect()" not in src
