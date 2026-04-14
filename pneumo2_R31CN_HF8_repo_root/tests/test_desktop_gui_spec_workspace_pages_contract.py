from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_spec_shell.diagnostics_panel import DiagnosticsWorkspacePage
from pneumo_solver_ui.desktop_spec_shell.main_window import DesktopGuiSpecMainWindow
from pneumo_solver_ui.desktop_spec_shell.workspace_pages import (
    BaselineWorkspacePage,
    ControlHubWorkspacePage,
    InputWorkspacePage,
    OptimizationWorkspacePage,
    ResultsWorkspacePage,
)
from pneumo_solver_ui.desktop_spec_shell.workspace_runtime import (
    build_baseline_workspace_summary,
    build_diagnostics_workspace_summary,
    build_input_workspace_summary,
    build_optimization_workspace_summary,
    build_results_workspace_summary,
)


ROOT = Path(__file__).resolve().parents[1]


def _app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_gui_spec_workspace_runtime_builders_cover_route_critical_surfaces() -> None:
    input_data = build_input_workspace_summary(ROOT)
    baseline = build_baseline_workspace_summary(ROOT)
    optimization = build_optimization_workspace_summary(ROOT)
    results = build_results_workspace_summary(ROOT)
    diagnostics = build_diagnostics_workspace_summary(ROOT)

    assert input_data.headline
    assert len(input_data.facts) >= 6
    assert any(fact.label == "Рабочая копия" for fact in input_data.facts)
    assert any(fact.label == "Следующий шаг" for fact in input_data.facts)

    assert baseline.headline
    assert len(baseline.facts) >= 5
    assert any(fact.label == "Активный baseline" for fact in baseline.facts)

    assert optimization.headline
    assert len(optimization.facts) >= 6
    assert any(fact.label == "Objective stack" for fact in optimization.facts)

    assert results.headline
    assert len(results.facts) >= 5
    assert any(fact.label == "Валидация" for fact in results.facts)

    assert diagnostics.headline
    assert len(diagnostics.facts) >= 5
    assert any(fact.label == "Последний ZIP" for fact in diagnostics.facts)


def test_gui_spec_main_window_uses_hosted_pages_for_runtime_and_control_hubs_for_route_pages() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        assert isinstance(window._page_widget_by_workspace_id["input_data"], InputWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["ring_editor"], ControlHubWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["test_matrix"], ControlHubWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["animation"], ControlHubWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["baseline_run"], BaselineWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["optimization"], OptimizationWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["results_analysis"], ResultsWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["diagnostics"], DiagnosticsWorkspacePage)
        assert callable(getattr(window._page_widget_by_workspace_id["overview"], "refresh_view", None))
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_hosted_input_workspace_page_keeps_runtime_summary_and_route_actions() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["input_data"]
        assert isinstance(page, InputWorkspacePage)
        page.refresh_view()
        app.processEvents()

        assert page.status_box.title() == "Текущее состояние"
        assert page.facts_box.title() == "Ключевые сигналы"
        assert len(page.action_commands) >= 3
        assert page.workspace.launch_surface == "workspace"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_control_hub_pages_render_catalog_surface_summary_and_actions() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["test_matrix"]
        assert isinstance(page, ControlHubWorkspacePage)
        page.refresh_view()
        app.processEvents()

        assert page.surface_box.title() == "Ключевые элементы surface"
        assert page.actions_box.title() == "Основные действия"
        assert page.workspace.automation_id == "TS-TABLE"
        assert len(page.action_commands) >= 2
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
