from __future__ import annotations

from pathlib import Path


def test_svg_autotrace_imported_via_package_path() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    ui_src = (root / "pneumo_ui_app.py").read_text(encoding="utf-8")
    legacy_ui_src = (root / "app.py").read_text(encoding="utf-8")
    cli_src = (root / "tools" / "svg_autotrace_cli.py").read_text(encoding="utf-8")

    assert 'from pneumo_solver_ui.svg_autotrace import extract_polylines' in ui_src
    assert 'from pneumo_solver_ui.svg_autotrace import extract_polylines' in legacy_ui_src
    assert 'from pneumo_solver_ui import svg_autotrace' in cli_src
    assert 'from svg_autotrace import' not in ui_src
    assert 'from svg_autotrace import' not in legacy_ui_src
