from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from pneumo_solver_ui.desktop_spec_shell.main_window import DesktopGuiSpecMainWindow


ROOT = Path(__file__).resolve().parents[1]


def _app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


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
