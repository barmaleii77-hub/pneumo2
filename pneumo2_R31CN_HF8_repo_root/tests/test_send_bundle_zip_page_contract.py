from __future__ import annotations

from pathlib import Path


def test_send_bundle_zip_page_surfaces_shared_anim_latest_browser_perf_summary() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "pneumo_solver_ui"
        / "pages"
        / "98_BuildBundle_ZIP.py"
    ).read_text(encoding="utf-8")

    assert "load_latest_send_bundle_anim_dashboard" in src
    assert "format_anim_dashboard_brief_lines" in src
    assert "last_send_bundle_anim_dashboard" in src
    assert "last_send_bundle_anim_diag_path" in src
    assert "Anim pointer diagnostics:" in src
