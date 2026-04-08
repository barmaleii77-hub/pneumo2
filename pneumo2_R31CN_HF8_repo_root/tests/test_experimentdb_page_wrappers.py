from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_experimentdb_wrappers_point_to_live_db_viewer() -> None:
    page21 = (ROOT / "pneumo_solver_ui" / "pages" / "21_ExperimentDB.py").read_text(encoding="utf-8")
    page31 = (ROOT / "pneumo_solver_ui" / "pages" / "31_OptDatabase.py").read_text(encoding="utf-8")

    assert 'with_name("03_DistributedOptimizationDB.py")' in page21
    assert 'runpy.run_path(str(_target))' in page21
    assert 'with_name("21_ExperimentDB.py")' in page31
    assert 'runpy.run_path(str(_target))' in page31
