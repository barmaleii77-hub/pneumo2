from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_autotest_and_test_center_guis_surface_shared_send_bundle_summary() -> None:
    files = [
        ROOT / "pneumo_solver_ui" / "tools" / "run_autotest_gui.py",
        ROOT / "pneumo_solver_ui" / "tools" / "test_center_gui.py",
    ]

    for path in files:
        src = path.read_text(encoding="utf-8")
        assert "load_latest_send_bundle_anim_dashboard" in src, str(path)
        assert "format_anim_dashboard_brief_lines" in src, str(path)
        assert "ANIM_DIAG_SIDECAR_JSON" in src, str(path)
        assert "Диагностика последней анимации:" in src, str(path)
        assert "Диагностика указателя анимации:" not in src, str(path)
        assert "Anim pointer diagnostics:" not in src, str(path)
