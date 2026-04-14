from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_control_center_targets_core_desktop_tools_without_mnemo() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_control_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "DesktopControlCenter" in src
    assert "build_desktop_launch_catalog(include_mnemo=False)" in src
    assert "DesktopLaunchCatalogItem" in src
    assert "spawn_module(module)" in src

    src_lower = src.lower()
    assert "desktop mnemo" in src_lower
    assert "desktop_mnemo" not in src_lower
    assert "pneumo_solver_ui.desktop_mnemo" not in src


def test_launcher_catalog_keeps_shared_desktop_tool_list_and_optional_mnemo() -> None:
    without_mnemo = build_desktop_launch_catalog(include_mnemo=False)
    with_mnemo = build_desktop_launch_catalog(include_mnemo=True)

    modules_without_mnemo = {item.module for item in without_mnemo}
    modules_with_mnemo = {item.module for item in with_mnemo}

    assert "pneumo_solver_ui.tools.desktop_input_editor" in modules_without_mnemo
    assert "pneumo_solver_ui.tools.desktop_geometry_reference_center" in modules_without_mnemo
    assert "pneumo_solver_ui.tools.desktop_ring_scenario_editor" in modules_without_mnemo
    assert "pneumo_solver_ui.tools.test_center_gui" in modules_without_mnemo
    assert "pneumo_solver_ui.tools.run_autotest_gui" in modules_without_mnemo
    assert "pneumo_solver_ui.tools.desktop_diagnostics_center" in modules_without_mnemo
    assert "pneumo_solver_ui.qt_compare_viewer" in modules_without_mnemo
    assert "pneumo_solver_ui.desktop_animator.app" in modules_without_mnemo
    assert "pneumo_solver_ui.desktop_mnemo.main" not in modules_without_mnemo
    assert "pneumo_solver_ui.desktop_mnemo.main" in modules_with_mnemo


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
    assert "ensure_root_launcher_runtime" in py
    assert 'MODULE = "pneumo_solver_ui.tools.desktop_control_center"' in py


def test_desktop_control_center_uses_list_detail_workspace_instead_of_cards() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_control_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(outer, orient="horizontal")' in src
    assert 'list_box = ttk.LabelFrame(left, text="Инженерные окна", padding=8)' in src
    assert 'right_split = ttk.Panedwindow(right, orient="vertical")' in src
    assert 'tree_frame, self.tree = build_scrolled_treeview(' in src
    assert "def _launch_selected_target(self) -> None:" in src
