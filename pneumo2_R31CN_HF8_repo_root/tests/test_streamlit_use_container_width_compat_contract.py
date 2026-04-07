from __future__ import annotations

from pathlib import Path


def test_streamlit_compat_wraps_page_link_and_image() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "ui_st_compat.py").read_text(encoding="utf-8")

    assert '"image"' in src
    assert '"page_link"' in src
    assert '"form_submit_button"' in src


def test_streamlit_compat_is_installed_in_main_streamlit_entrypoints() -> None:
    root = Path(__file__).resolve().parents[1]
    app_src = (root / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    pneumo_src = (root / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_st_compat import install_st_compat" in app_src
    assert "install_st_compat()" in app_src
    assert "from pneumo_solver_ui.ui_st_compat import install_st_compat" in pneumo_src
    assert "install_st_compat()" in pneumo_src
