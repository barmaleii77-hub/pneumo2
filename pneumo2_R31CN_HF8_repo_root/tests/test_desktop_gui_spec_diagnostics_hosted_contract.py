from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_diagnostics_model import DesktopDiagnosticsBundleRecord
from pneumo_solver_ui.desktop_spec_shell.diagnostics_panel import DiagnosticsWorkspacePage
from pneumo_solver_ui.desktop_spec_shell.main_window import DesktopGuiSpecMainWindow
from pneumo_solver_ui.desktop_spec_shell.registry import build_command_map, build_workspace_map


ROOT = Path(__file__).resolve().parents[1]


def _app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_hosted_diagnostics_workspace_page_builds_offscreen_and_refreshes() -> None:
    app = _app()
    workspace = build_workspace_map()["diagnostics"]
    page = DiagnosticsWorkspacePage(workspace, repo_root=ROOT)
    try:
        page.refresh_view()
        app.processEvents()

        assert page.bundle_box.title() == "Текущее состояние архива диагностики"
        assert page.run_box.title() == "Последний запуск диагностики"
        assert page.check_box.title() == "Проверка архива диагностики"
        assert page.baseline_box.title() == "Опорный прогон"
        assert page.actions_box.title() == "Действия"
        assert page.log_box.title() == "Журнал / последние сообщения"
        assert "Данные берутся из состояния диагностики приложения" in page.source_label.text()
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_diagnostics_page_routes_send_and_legacy_actions_through_panel() -> None:
    app = _app()
    workspace = build_workspace_map()["diagnostics"]
    spawns: list[str] = []
    page = DiagnosticsWorkspacePage(
        workspace,
        repo_root=ROOT,
        spawn_module_fn=lambda module: spawns.append(module),
    )
    try:
        page.controller._current_bundle = DesktopDiagnosticsBundleRecord(
            out_dir=str((ROOT / "send_bundles").resolve()),
            latest_zip_path=str((ROOT / "send_bundles" / "SEND_mock_bundle.zip").resolve()),
        )

        page.handle_command("diagnostics.send_results")
        page.handle_command("diagnostics.legacy_center.open")
        app.processEvents()

        assert "pneumo_solver_ui.tools.send_results_gui" in spawns
        assert "pneumo_solver_ui.tools.desktop_diagnostics_center" in spawns
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_diagnostics_page_links_baseline_banner_to_baseline_center(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(tmp_path / "workspace"))
    workspace = build_workspace_map()["diagnostics"]
    commands: list[str] = []
    page = DiagnosticsWorkspacePage(
        workspace,
        repo_root=ROOT,
        on_command=lambda command_id: commands.append(command_id),
    )
    try:
        page.refresh_view()
        app.processEvents()

        assert page.baseline_status_value.objectName() == "DG-BASELINE-STATUS"
        assert page.open_baseline_center_button.objectName() == "DG-BTN-OPEN-BASELINE"
        assert "Опорный прогон не найден" in page.baseline_status_value.text()
        assert "missing" not in page.baseline_status_value.text()
        assert "Молчаливая подмена запрещена" in page.baseline_status_value.text()
        assert "Объём проверки - полная" in page.request_value.text()
        for forbidden in ("level=", "full", "False", "True", "skip_ui_smoke"):
            assert forbidden not in page.request_value.text()

        page.open_baseline_center()
        app.processEvents()

        assert commands == ["baseline.center.open"]
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_main_window_routes_diagnostics_collect_to_hosted_page_handler() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["diagnostics"]
        calls: list[str] = []
        page.handle_command = lambda command_id: calls.append(command_id)  # type: ignore[method-assign]

        window.run_command("diagnostics.collect_bundle")
        app.processEvents()

        assert calls == ["diagnostics.collect_bundle"]
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_main_window_routes_diagnostics_baseline_link_to_restore_guard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(tmp_path / "shell.ini"))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        diagnostics_page = window._page_widget_by_workspace_id["diagnostics"]
        diagnostics_page.open_baseline_center()
        app.processEvents()

        assert window._current_workspace_id == "baseline_run"
        baseline_page = window._page_widget_by_workspace_id["baseline_run"]
        assert baseline_page.baseline_center_box.title() == "Центр опорного прогона: просмотр, принятие, восстановление"

        window.run_command("baseline.restore")
        app.processEvents()

        assert window._current_workspace_id == "baseline_run"
        assert "Действие заблокировано" in baseline_page.action_result_label.text()
        assert "baseline.restore" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_diagnostics_fallback_command_remains_available() -> None:
    commands = build_command_map()
    assert commands["diagnostics.legacy_center.open"].kind == "launch_module"
    assert commands["diagnostics.legacy_center.open"].module == "pneumo_solver_ui.tools.desktop_diagnostics_center"
