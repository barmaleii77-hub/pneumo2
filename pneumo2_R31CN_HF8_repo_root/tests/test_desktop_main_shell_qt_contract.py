from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.tools import desktop_main_shell_qt as desktop_main_shell_qt_module


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_qt_shell_launcher_exposes_qt_first_cli_and_legacy_fallback() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_main_shell_qt.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "def build_arg_parser() -> argparse.ArgumentParser:" in src
    assert '"--open"' in src
    assert '"--list-tools"' in src
    assert '"--legacy-tk-shell"' in src
    assert "Desktop shell tools (Qt shell catalog):" in src
    assert "from pneumo_solver_ui.tools import desktop_main_shell as legacy_shell" in src
    assert "from pneumo_solver_ui.desktop_qt_shell.main_window import main as run_qt_shell_main" in src
    assert "fallback to legacy Tk shell" in src


def test_desktop_qt_shell_launcher_catalog_keeps_runtime_and_migration_metadata() -> None:
    catalog = build_desktop_launch_catalog(include_mnemo=True)
    by_key = {item.key: item for item in catalog}

    assert by_key["desktop_input_editor"].runtime_kind == "tk"
    assert by_key["desktop_input_editor"].migration_status == "managed_external"
    assert by_key["desktop_input_editor"].source_of_truth_role == "master"

    assert by_key["desktop_animator"].runtime_kind == "qt"
    assert by_key["desktop_animator"].migration_status == "native"
    assert by_key["desktop_animator"].source_of_truth_role == "derived"

    assert "исходные данные" in by_key["desktop_input_editor"].search_aliases
    assert "stagerunner" in by_key["desktop_optimizer_center"].search_aliases


def test_desktop_qt_shell_spec_contract_marks_tk_workspaces_as_managed_external() -> None:
    specs = build_desktop_shell_specs()
    by_key = {spec.key: spec for spec in specs}

    assert by_key["desktop_input_editor"].effective_runtime_kind == "tk"
    assert by_key["desktop_input_editor"].effective_migration_status == "managed_external"
    assert by_key["desktop_ring_editor"].effective_source_of_truth_role == "master"
    assert by_key["desktop_results_center"].effective_source_of_truth_role == "derived"
    assert by_key["desktop_diagnostics_center"].effective_source_of_truth_role == "support"
    assert "selected_tool_key" in by_key["desktop_optimizer_center"].effective_context_handoff_keys
    assert "active_optimization_mode" in by_key["desktop_optimizer_center"].effective_context_handoff_keys


def test_desktop_qt_shell_main_window_uses_qmainwindow_docks_and_search_surface() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_qt_shell" / "main_window.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopQtMainShell(QtWidgets.QMainWindow):" in src
    assert 'self.setObjectName("DesktopQtMainShell")' in src
    assert 'QtWidgets.QToolBar("Командная зона", self)' in src
    assert 'self.workspace_combo = QtWidgets.QComboBox(toolbar)' in src
    assert 'self.command_search_edit = QtWidgets.QLineEdit(toolbar)' in src
    assert 'self.optimization_mode_combo = QtWidgets.QComboBox(toolbar)' in src
    assert 'self.browser_dock = QtWidgets.QDockWidget("Обзор проекта", self)' in src
    assert 'self.inspector_dock = QtWidgets.QDockWidget("Свойства и помощь", self)' in src
    assert 'self.runtime_dock = QtWidgets.QDockWidget("Ход выполнения и внешние окна", self)' in src
    assert "self.central_stack = QtWidgets.QStackedWidget(central)" in src
    assert 'self.banner_label = QtWidgets.QLabel(' in src
    assert 'self.route_label = QtWidgets.QLabel(' in src
    assert 'QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K")' in src
    assert 'QtGui.QShortcut(QtGui.QKeySequence("F6")' in src
    assert 'QtGui.QShortcut(QtGui.QKeySequence("Shift+F6")' in src
    assert "DesktopShellCoexistenceManager()" in src
    assert "QSettings" in src


def test_desktop_qt_shell_coexistence_manager_tracks_managed_external_windows() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_qt_shell" / "coexistence.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class ManagedExternalWindowSession" in src
    assert "class DesktopShellCoexistenceManager" in src
    assert "build_shell_context_env" in src
    assert "spawn_module(" in src
    assert '"selected_tool_key"' in src
    assert '"active_optimization_mode"' in src
    assert '"source_of_truth_role"' in src
    assert '"migration_status"' in src


def test_desktop_qt_shell_launcher_validates_registry_keys_and_formats_catalog() -> None:
    catalog = desktop_main_shell_qt_module.format_tool_catalog()

    assert "Desktop shell tools (Qt shell catalog):" in catalog
    assert "desktop_input_editor" in catalog
    assert "desktop_animator" in catalog
    assert "managed_external" in catalog
    assert "qt" in catalog.lower()

    assert desktop_main_shell_qt_module.resolve_startup_tool_keys(
        ["desktop_input_editor", "compare_viewer"]
    ) == ("desktop_input_editor", "compare_viewer")
