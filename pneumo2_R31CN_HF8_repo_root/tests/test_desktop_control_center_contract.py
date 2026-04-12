from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_control_center_targets_core_desktop_tools_without_mnemo() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_control_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "pneumo_solver_ui.tools.test_center_gui" in src
    assert "pneumo_solver_ui.tools.desktop_input_editor" in src
    assert "pneumo_solver_ui.tools.run_full_diagnostics_gui" in src
    assert "pneumo_solver_ui.tools.send_results_gui" in src
    assert "pneumo_solver_ui.qt_compare_viewer" in src
    assert "pneumo_solver_ui.desktop_animator.app" in src
    assert "DesktopControlCenter" in src

    src_lower = src.lower()
    assert "desktop mnemo" in src_lower
    assert "desktop_mnemo" not in src_lower
    assert "pneumo_solver_ui.desktop_mnemo" not in src


def test_root_desktop_control_center_wrappers_delegate_to_launcher() -> None:
    cmd = (ROOT / "START_DESKTOP_CONTROL_CENTER.cmd").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    vbs = (ROOT / "START_DESKTOP_CONTROL_CENTER.vbs").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    pyw = (ROOT / "START_DESKTOP_CONTROL_CENTER.pyw").read_text(
        encoding="utf-8",
        errors="replace",
    )
    py = (ROOT / "START_DESKTOP_CONTROL_CENTER.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "start_desktop_control_center.vbs" in cmd or "start_desktop_control_center.pyw" in cmd
    assert "wscript.shell" in vbs
    assert "start_desktop_control_center.pyw" in vbs
    assert 'Path(__file__).with_name("START_DESKTOP_CONTROL_CENTER.py")' in pyw
    assert 'MODULE = "pneumo_solver_ui.tools.desktop_control_center"' in py
