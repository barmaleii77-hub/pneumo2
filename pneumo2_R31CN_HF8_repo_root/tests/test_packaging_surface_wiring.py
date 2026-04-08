from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_and_root_cause_use_shared_packaging_surface_helpers() -> None:
    app_src = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    report_src = (ROOT / "pneumo_solver_ui" / "root_cause_report.py").read_text(encoding="utf-8")

    assert "collect_packaging_surface_metrics" in app_src
    assert "enrich_packaging_surface_df" in app_src
    assert "apply_packaging_surface_filters" in app_src
    assert "render_packaging_surface_metrics" in app_src
    assert "packaging_surface_result_columns" in app_src
    assert "packaging_error_surface_metrics" in app_src
    assert "collect_packaging_surface_metrics" in heavy_src
    assert "enrich_packaging_surface_df" in heavy_src
    assert "apply_packaging_surface_filters" in heavy_src
    assert "render_packaging_surface_metrics" in heavy_src
    assert "packaging_surface_result_columns" in heavy_src
    assert "packaging_error_surface_metrics" in heavy_src
    assert "collect_packaging_surface_metrics" in report_src
    assert "format_packaging_markdown_lines" in report_src
