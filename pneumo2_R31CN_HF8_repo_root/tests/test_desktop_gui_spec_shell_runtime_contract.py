from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from pneumo_solver_ui.desktop_ring_editor_model import build_default_ring_spec
from pneumo_solver_ui.desktop_spec_shell.main_window import DesktopGuiSpecMainWindow
from pneumo_solver_ui.desktop_spec_shell.workspace_runtime import build_ring_workspace_summary
from pneumo_solver_ui.desktop_spec_shell.workspace_pages import (
    AnimationWorkspacePage,
    BaselineWorkspacePage,
    InputWorkspacePage,
    OptimizationWorkspacePage,
    ResultsWorkspacePage,
    RingWorkspacePage,
    SuiteWorkspacePage,
    ToolsWorkspacePage,
)
from pneumo_solver_ui.desktop_spec_shell.diagnostics_panel import (
    DiagnosticsWorkspacePage as HostedDiagnosticsWorkspacePage,
)


ROOT = Path(__file__).resolve().parents[1]


def _app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _route_tree_item(
    window: DesktopGuiSpecMainWindow,
    *,
    workspace_id: str = "",
    command_id: str = "",
) -> QtWidgets.QTreeWidgetItem | None:
    for item in window._iter_route_tree_items():
        item_workspace_id = str(item.data(0, QtCore.Qt.UserRole) or "")
        item_command_id = str(item.data(0, QtCore.Qt.UserRole + 1) or "")
        if workspace_id and item_workspace_id != workspace_id:
            continue
        if command_id and item_command_id != command_id:
            continue
        if not command_id and item_command_id:
            continue
        return item
    return None


def test_main_window_applies_v3_shortcuts_and_docking_contracts(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_runtime.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        app.processEvents()

        assert window._keyboard_shortcut_by_name["Поиск команд"] == "Ctrl+K"
        assert window._keyboard_shortcut_by_name["Быстрый поиск"] == "Ctrl+K"
        assert window._keyboard_shortcut_by_name["Главное действие шага"] == "Ctrl+Enter"
        assert window._keyboard_shortcut_by_name["Сохранить архив проекта"] == "Ctrl+Shift+D"
        assert "Собрать архив для отправки" not in window._keyboard_shortcut_by_name
        assert "Собрать диагностику" not in window._keyboard_shortcut_by_name
        assert len(window._shortcut_objects) >= 6

        assert not bool(
            window.route_dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable
        )
        assert bool(
            window.inspector_dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable
        )
        assert window.route_dock.property("spec_panel_id") == "левая_навигация"
        assert window.inspector_dock.property("spec_can_second_monitor") is True
        assert window._workspace_dock_by_workspace_id["input_data"].property("spec_child_window_role") == "workspace"
        assert window._workspace_dock_by_workspace_id["animation"].features() & QtWidgets.QDockWidget.DockWidgetFloatable
        workspace_ids = tuple(workspace.workspace_id for workspace in window.workspaces)
        assert tuple(window._workspace_dock_by_workspace_id) == workspace_ids
        for workspace in window.workspaces:
            dock = window._workspace_dock_by_workspace_id[workspace.workspace_id]
            assert dock.widget() is window._page_widget_by_workspace_id[workspace.workspace_id]
            assert dock.property("spec_workspace_id") == workspace.workspace_id
            assert dock.property("spec_child_window_role") == "workspace"
            assert dock.features() & QtWidgets.QDockWidget.DockWidgetMovable
            assert dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable
            assert dock.features() & QtWidgets.QDockWidget.DockWidgetClosable
        menu_titles = [
            action.text()
            for action in window.windows_menu.actions()
            if action.text().strip()
        ]
        assert menu_titles == [workspace.title for workspace in window.workspaces]
        assert len(menu_titles) == len(set(menu_titles))
        assert window.status_primary_label.property("ui_state_id") == "STATE-VALID"
        assert window.warning_label.property("ui_state_id") == "STATE-WARNING"
        assert window.findChild(QtWidgets.QGroupBox, "V16-VISIBILITY-WS-PROJECT") is not None
        assert window.findChild(QtWidgets.QGroupBox, "V16-VISIBILITY-WS-INPUTS") is not None
        assert window.findChild(QtWidgets.QGroupBox, "V16-VISIBILITY-WS-DIAGNOSTICS") is not None
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_defers_settings_sync_during_initial_open(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_deferred_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        app.processEvents()
        assert window._state_save_suppressed is False
        assert not window._state_save_timer.isActive()
        assert str(window._settings.value("window/last_workspace") or "") != "overview"

        window.open_workspace("diagnostics")
        assert window._state_save_timer.isActive()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()

    settings = QtCore.QSettings(str(settings_path), QtCore.QSettings.IniFormat)
    assert str(settings.value("window/last_workspace") or "") == "diagnostics"


def test_main_window_routes_input_editor_to_hosted_page(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_input_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("input.editor.open")
        app.processEvents()

        assert window._current_workspace_id == "input_data"
        page = window._page_widget_by_workspace_id["input_data"]
        assert isinstance(page, InputWorkspacePage)
        assert page.objectName() == "WS-INPUTS-HOSTED-PAGE"
        assert page.input_editor_box.objectName() == "ID-PARAM-TABLE"
        assert page.input_table.rowCount() > 0
        assert "Редактирование исходных данных открыто" in page.input_action_label.text()
        assert "input.editor.open" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_hosts_ring_workspace_without_legacy_bridge_surface(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_ring_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("ring.editor.open")
        app.processEvents()

        assert window._current_workspace_id == "ring_editor"
        page = window._page_widget_by_workspace_id["ring_editor"]
        assert isinstance(page, RingWorkspacePage)
        assert page.objectName() == "WS-RING-HOSTED-PAGE"
        assert page.ring_editor_box.objectName() == "RG-SEGMENT-LIST"
        assert page.ring_segment_table.rowCount() > 0
        assert "Циклический сценарий" in page.headline_label.text()
        assert "Редактор циклического сценария открыт" in page.ring_action_label.text()
        assert "ring.editor.open" in window.recent_command_ids
        action_ids = tuple(command.command_id for command in page.action_commands)
        assert action_ids == ("ring.editor.open", "workspace.test_matrix.open")
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_ring_workspace_summary_prefers_source_of_truth_over_newer_meta(tmp_path) -> None:
    ring_dir = tmp_path / "pneumo_solver_ui" / "workspace" / "generated_scenarios" / "ring"
    ring_dir.mkdir(parents=True)
    source_path = ring_dir / "scenario_demo_ring_source_of_truth.json"
    meta_path = ring_dir / "scenario_demo_ring_meta.json"
    source_path.write_text(
        json.dumps(build_default_ring_spec(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps({"kind": "meta", "segments": "not-a-ring-spec"}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.utime(source_path, (1000, 1000))
    os.utime(meta_path, (2000, 2000))

    summary = build_ring_workspace_summary(tmp_path)
    visible_text = "\n".join(
        (
            summary.headline,
            summary.detail,
            *(fact.value for fact in summary.facts),
            *summary.evidence_lines,
        )
    )

    assert str(source_path.resolve()) in visible_text
    assert str(meta_path.resolve()) not in visible_text


def test_main_window_hosts_suite_workspace_as_ring_consumer(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_suite_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("test.center.open")
        app.processEvents()

        assert window._current_workspace_id == "test_matrix"
        page = window._page_widget_by_workspace_id["test_matrix"]
        assert isinstance(page, SuiteWorkspacePage)
        assert page.objectName() == "WS-SUITE-HOSTED-PAGE"
        assert page.suite_table.objectName() == "TS-TABLE"
        assert page.suite_table.rowCount() > 0
        assert "Проверка набора открыта" in page.validation_label.text()
        assert "test.center.open" in window.recent_command_ids
        action_ids = tuple(command.command_id for command in page.action_commands)
        assert action_ids == (
            "test.center.open",
            "workspace.baseline_run.open",
            "workspace.ring_editor.open",
        )
        visible_buttons = {button.text() for button in page.findChildren(QtWidgets.QPushButton)}
        assert "Перейти к базовому прогону" in visible_buttons
        assert "Расширенная настройка набора" not in visible_buttons
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_routes_baseline_setup_to_hosted_page(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_baseline_setup_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("baseline.run_setup.open")
        app.processEvents()

        assert window._current_workspace_id == "baseline_run"
        page = window._page_widget_by_workspace_id["baseline_run"]
        assert isinstance(page, BaselineWorkspacePage)
        assert page.objectName() == "WS-BASELINE-HOSTED-PAGE"
        assert page.run_setup_box.objectName() == "BL-RUN-SETUP-PANEL"
        assert "Настройка запуска открыта" in page.run_setup_result_label.text()
        assert "baseline.run_setup.open" in window.recent_command_ids

        window.run_command("baseline.run_setup.verify")
        app.processEvents()
        assert "Проверка готовности" in page.run_setup_result_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_routes_optimization_setup_to_hosted_page(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_optimization_setup_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("optimization.center.open")
        app.processEvents()

        assert window._current_workspace_id == "optimization"
        page = window._page_widget_by_workspace_id["optimization"]
        assert isinstance(page, OptimizationWorkspacePage)
        assert page.objectName() == "WS-OPTIMIZATION-HOSTED-PAGE"
        assert page.optimization_launch_box.objectName() == "OP-STAGERUNNER-BLOCK"
        assert "Настройка основного запуска открыта" in page.optimization_result_label.text()
        assert "optimization.center.open" in window.recent_command_ids

        window.run_command("optimization.readiness.check")
        app.processEvents()
        assert "Проверка готовности" in page.optimization_result_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_routes_results_analysis_to_hosted_page(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_results_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("results.center.open")
        app.processEvents()

        assert window._current_workspace_id == "results_analysis"
        page = window._page_widget_by_workspace_id["results_analysis"]
        assert isinstance(page, ResultsWorkspacePage)
        assert page.objectName() == "WS-ANALYSIS-HOSTED-PAGE"
        assert page.results_analysis_box.objectName() == "RS-LEADERBOARD"
        assert "Анализ результатов открыт" in page.results_action_label.text()
        assert "results.center.open" in window.recent_command_ids

        window.run_command("results.compare.prepare")
        app.processEvents()
        assert "Сравнение подготовлено" in page.results_action_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_routes_animation_to_hosted_page(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_animation_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.run_command("animation.animator.open")
        app.processEvents()

        assert window._current_workspace_id == "animation"
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, AnimationWorkspacePage)
        assert page.objectName() == "WS-ANIMATOR-HOSTED-PAGE"
        assert page.animation_hub_box.objectName() == "AM-VIEWPORT"
        assert "Анимация открыта" in page.animation_action_label.text()
        assert "animation.animator.open" in window.recent_command_ids

        window.run_command("animation.mnemo.open")
        app.processEvents()
        assert "Мнемосхема открыта" in page.animation_action_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_route_tree_directly_opens_workspace_and_action_docks(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_tree_direct_open.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        target_workspace_item = _route_tree_item(window, workspace_id="ring_editor")
        target_action_item = _route_tree_item(window, command_id="ring.editor.open")
        assert target_workspace_item is not None
        assert target_action_item is not None

        window._activate_route_tree_item(target_workspace_item)
        app.processEvents()
        assert window._current_workspace_id == "ring_editor"
        assert not window._workspace_dock_by_workspace_id["ring_editor"].isHidden()

        window._activate_route_tree_item(target_action_item)
        app.processEvents()
        page = window._page_widget_by_workspace_id["ring_editor"]
        assert isinstance(page, RingWorkspacePage)
        assert "Редактор циклического сценария открыт" in page.ring_action_label.text()
        assert "ring.editor.open" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_route_tree_actions_are_direct_dock_routes_without_legacy_launchers(
    tmp_path,
    monkeypatch,
) -> None:
    settings_path = tmp_path / "desktop_spec_shell_tree_actions.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        visible_command_ids: list[str] = []
        for item in window._iter_route_tree_items():
            command_id = str(item.data(0, QtCore.Qt.UserRole + 1) or "")
            if not command_id:
                continue
            visible_command_ids.append(command_id)
            command = window.command_by_id[command_id]
            assert command.availability != "support_fallback", command_id
            assert command.kind != "launch_module", command_id
            assert command.module is None, command_id

        assert "tools.autotest.legacy_open" not in visible_command_ids
        assert "animation.legacy_animator.open" not in visible_command_ids
        assert "diagnostics.legacy_center.open" not in visible_command_ids

        safe_direct_commands = {
            "input.editor.open": "input_data",
            "ring.editor.open": "ring_editor",
            "test.center.open": "test_matrix",
            "baseline.run_setup.open": "baseline_run",
            "optimization.center.open": "optimization",
            "results.center.open": "results_analysis",
            "animation.animator.open": "animation",
            "diagnostics.verify_bundle": "diagnostics",
            "tools.geometry_reference.open": "tools",
        }
        for command_id, workspace_id in safe_direct_commands.items():
            item = _route_tree_item(window, command_id=command_id)
            assert item is not None, command_id
            window._activate_route_tree_item(item)
            app.processEvents()
            assert window._current_workspace_id == workspace_id
            assert not window._workspace_dock_by_workspace_id[workspace_id].isHidden()
            assert command_id in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_route_tree_actions_land_on_functional_surfaces(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_tree_functional_surfaces.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        surface_contracts = {
            "input.editor.open": (
                "input_data",
                InputWorkspacePage,
                lambda page: (
                    page.input_editor_box.objectName() == "ID-PARAM-TABLE"
                    and page.input_table.rowCount() > 0
                    and "Редактирование исходных данных открыто" in page.input_action_label.text()
                ),
            ),
            "ring.editor.open": (
                "ring_editor",
                RingWorkspacePage,
                lambda page: (
                    page.ring_editor_box.objectName() == "RG-SEGMENT-LIST"
                    and page.ring_segment_table.rowCount() > 0
                    and "Редактор циклического сценария открыт" in page.ring_action_label.text()
                ),
            ),
            "test.center.open": (
                "test_matrix",
                SuiteWorkspacePage,
                lambda page: (
                    page.suite_table.objectName() == "TS-TABLE"
                    and page.suite_table.rowCount() > 0
                    and "Проверка набора открыта" in page.validation_label.text()
                ),
            ),
            "baseline.run_setup.open": (
                "baseline_run",
                BaselineWorkspacePage,
                lambda page: (
                    page.run_setup_box.objectName() == "BL-RUN-SETUP-PANEL"
                    and "Настройка запуска открыта" in page.run_setup_result_label.text()
                ),
            ),
            "optimization.center.open": (
                "optimization",
                OptimizationWorkspacePage,
                lambda page: (
                    page.optimization_launch_box.objectName() == "OP-STAGERUNNER-BLOCK"
                    and "Настройка основного запуска открыта" in page.optimization_result_label.text()
                ),
            ),
            "results.center.open": (
                "results_analysis",
                ResultsWorkspacePage,
                lambda page: (
                    page.results_analysis_box.objectName() == "RS-LEADERBOARD"
                    and "Анализ результатов открыт" in page.results_action_label.text()
                ),
            ),
            "animation.animator.open": (
                "animation",
                AnimationWorkspacePage,
                lambda page: (
                    page.animation_hub_box.objectName() == "AM-VIEWPORT"
                    and "Анимация открыта" in page.animation_action_label.text()
                ),
            ),
            "diagnostics.verify_bundle": (
                "diagnostics",
                HostedDiagnosticsWorkspacePage,
                lambda page: (
                    page.check_box.title() == "Проверка архива проекта"
                    and "Провер" in page.status_label.text()
                ),
            ),
            "tools.geometry_reference.open": (
                "tools",
                ToolsWorkspacePage,
                lambda page: (
                    page.geometry_box.objectName() == "TOOLS-GEOMETRY-REFERENCE"
                    and page.geometry_cylinder_table.rowCount() > 0
                ),
            ),
        }

        for command_id, (workspace_id, page_type, assert_surface_ready) in surface_contracts.items():
            item = _route_tree_item(window, command_id=command_id)
            assert item is not None, command_id
            window._activate_route_tree_item(item)
            app.processEvents()

            assert window._current_workspace_id == workspace_id, command_id
            dock = window._workspace_dock_by_workspace_id[workspace_id]
            assert not dock.isHidden(), command_id
            page = window._page_widget_by_workspace_id[workspace_id]
            assert isinstance(page, page_type), command_id
            assert assert_surface_ready(page), command_id
            assert command_id in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_command_search_opens_direct_hosted_surfaces(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_search_direct_surfaces.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        search_routes = {
            "редактировать исходные данные": ("input.editor.open", "input_data"),
            "редактор кольца": ("ring.editor.open", "ring_editor"),
            "настройка расчёта": ("baseline.run_setup.open", "baseline_run"),
            "аниматор": ("animation.animator.open", "animation"),
            "проверить архив": ("diagnostics.verify_bundle", "diagnostics"),
            "справочник геометрии": ("tools.geometry_reference.open", "tools"),
        }

        for query, (command_id, workspace_id) in search_routes.items():
            window._refresh_search_results(query)
            app.processEvents()
            assert window._search_ids_by_index, query
            assert window._search_ids_by_index[0] == command_id

            window._activate_first_search_result()
            app.processEvents()

            command = window.command_by_id[command_id]
            assert command.availability != "support_fallback"
            assert command.kind != "launch_module"
            assert window._current_workspace_id == workspace_id
            assert not window._workspace_dock_by_workspace_id[workspace_id].isHidden()
            assert command_id in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_cycles_focus_by_f6_region_order(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_focus.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window._focus_command_search()
        app.processEvents()
        assert window._active_shell_region == "верхняя_командная_панель"

        window._focus_next_region()
        app.processEvents()
        assert window._active_shell_region == "левая_навигация"

        window._focus_next_region()
        app.processEvents()
        assert window._active_shell_region == "центральная_рабочая_область"

        window._focus_next_region()
        app.processEvents()
        assert window._active_shell_region == "правая_панель_свойств_и_справки"

        window._focus_previous_region()
        app.processEvents()
        assert window._active_shell_region == "центральная_рабочая_область"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_persists_layout_and_last_workspace(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "desktop_spec_shell_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        window.open_workspace("diagnostics")
        app.processEvents()
        window._save_window_state()
        app.processEvents()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()

    settings = QtCore.QSettings(str(settings_path), QtCore.QSettings.IniFormat)
    assert settings_path.exists()
    assert str(settings.value("window/last_workspace") or "") == "diagnostics"
    assert settings.value("window/geometry") is not None
    assert settings.value("window/state") is not None
