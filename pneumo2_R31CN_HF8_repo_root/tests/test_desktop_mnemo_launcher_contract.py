from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_is_launchable_from_streamlit_shells() -> None:
    repo = Path(__file__).resolve().parents[1]
    home_src = (repo / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    legacy_src = (repo / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")

    assert "launch_desktop_mnemo_follow" in home_src
    assert "pneumo_solver_ui.desktop_mnemo.main" in home_src
    assert "pneumo_solver_ui.desktop_mnemo.main" in legacy_src
    assert "launch_desktop_mnemo" in legacy_src

