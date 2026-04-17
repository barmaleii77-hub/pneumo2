from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_suite_snapshot import build_validated_suite_snapshot
from pneumo_solver_ui.desktop_spec_shell.diagnostics_panel import DiagnosticsWorkspacePage
from pneumo_solver_ui.desktop_spec_shell.main_window import DesktopGuiSpecMainWindow
from pneumo_solver_ui.desktop_spec_shell.registry import build_workspace_map
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
from pneumo_solver_ui.optimization_baseline_source import (
    append_baseline_history_item,
    baseline_history_item_from_contract,
    baseline_suite_handoff_snapshot_path,
    build_active_baseline_contract,
    read_active_baseline_contract,
    read_baseline_history,
    write_active_baseline_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def _app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _suite_snapshot() -> dict[str, object]:
    return build_validated_suite_snapshot(
        [
            {
                "id": "baseline-ui-row-1",
                "имя": "baseline_ui_smoke",
                "тип": "инерция_крен",
                "включен": True,
                "стадия": 0,
                "dt": 0.01,
                "t_end": 1.0,
            }
        ],
        inputs_snapshot_hash="inputs-hash-ui",
        ring_source_hash="ring-hash-ui",
        created_at_utc="2026-04-17T00:00:00Z",
        context_label="baseline-ui",
    )


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
    baseline_labels = {fact.label for fact in baseline.facts}
    assert "HO-005 -> active_baseline_contract -> HO-006" in baseline_labels
    assert "Активный baseline" in baseline_labels
    assert "Действия review/adopt/restore" in baseline_labels
    assert any("Active contract:" in line for line in baseline.evidence_lines)

    assert optimization.headline
    assert len(optimization.facts) >= 6
    assert any(fact.label == "Objective stack" for fact in optimization.facts)
    optimization_baseline = next(
        fact for fact in optimization.facts if fact.label == "Baseline provenance"
    )
    assert "HO-006=" in optimization_baseline.value

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


def test_gui_spec_main_window_startup_env_opens_baseline_workspace(monkeypatch, tmp_path: Path) -> None:
    app = _app()
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(tmp_path / "shell.ini"))
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE", "baseline_run")
    window = DesktopGuiSpecMainWindow()
    try:
        assert window._current_workspace_id == "baseline_run"
        assert isinstance(window._page_widget_by_workspace_id["baseline_run"], BaselineWorkspacePage)
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


def test_hosted_baseline_workspace_page_requires_explicit_action_before_restore(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    suite_snapshot = _suite_snapshot()
    suite_path = baseline_suite_handoff_snapshot_path(workspace_dir=workspace_dir)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite_snapshot, ensure_ascii=False), encoding="utf-8")

    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_path=tmp_path / "baseline_active.json",
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-baseline-ui"},
        source_run_dir=tmp_path / "runs" / "active",
        created_at_utc="2026-04-17T00:10:00Z",
    )
    candidate = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_path=tmp_path / "baseline_candidate.json",
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-baseline-ui"},
        source_run_dir=tmp_path / "runs" / "candidate",
        created_at_utc="2026-04-17T00:11:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=workspace_dir)
    history_item = baseline_history_item_from_contract(candidate, action="adopt", actor="unit")
    append_baseline_history_item(history_item, workspace_dir=workspace_dir)

    page = BaselineWorkspacePage(
        build_workspace_map()["baseline_run"],
        (),
        lambda _command_id: None,
        repo_root=ROOT,
    )
    try:
        app.processEvents()

        assert page.baseline_center_box.title() == "Baseline Center: review / adopt / restore"
        assert page.review_button.isEnabled()
        assert not page.adopt_button.isEnabled()
        assert not page.restore_button.isEnabled()
        assert "Silent rebinding: запрещён" in page.baseline_mismatch_label.text()
        assert page.baseline_mismatch_matrix.objectName() == "BL-MISMATCH-MATRIX"
        assert page.baseline_mismatch_matrix.rowCount() == 5
        matrix_status = {
            page.baseline_mismatch_matrix.item(row, 0).text(): page.baseline_mismatch_matrix.item(row, 3).text()
            for row in range(page.baseline_mismatch_matrix.rowCount())
        }
        assert matrix_status["active_baseline_hash"] == "mismatch"
        assert matrix_status["suite_snapshot_hash"] == "match"
        assert matrix_status["inputs_snapshot_hash"] == "match"
        assert matrix_status["ring_source_hash"] == "match"
        assert matrix_status["policy_mode"] == "match"

        page.handle_command("baseline.review")
        assert "action=review" in page.action_result_label.text()
        assert "status=review_only" in page.action_result_label.text()
        page.handle_command("baseline.restore")
        assert "restore: blocked" in page.action_result_label.text()

        blocked = page.apply_baseline_action("restore")
        assert blocked["status"] == "blocked"
        assert read_active_baseline_contract(workspace_dir=workspace_dir)["active_baseline_hash"] == active["active_baseline_hash"]

        page.explicit_confirmation_checkbox.setChecked(True)
        app.processEvents()
        assert page.restore_button.isEnabled()
        page._confirm_baseline_action = lambda _action, _surface: True  # type: ignore[method-assign]

        applied = page.apply_baseline_action("restore")
        history = read_baseline_history(workspace_dir=workspace_dir)

        assert applied["status"] == "applied"
        assert applied["silent_rebinding_allowed"] is False
        assert read_active_baseline_contract(workspace_dir=workspace_dir)["active_baseline_hash"] == candidate["active_baseline_hash"]
        assert history[-1]["action"] == "restore"
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
