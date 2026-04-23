from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6 import QtWidgets

from pneumo_solver_ui import desktop_diagnostics_runtime
from pneumo_solver_ui.desktop_spec_shell import diagnostics_panel as diagnostics_panel_module
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


def test_diagnostics_state_write_falls_back_when_latest_state_file_is_locked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "latest_desktop_diagnostics_center_state.json"
    target.write_text("{}", encoding="utf-8")
    original_replace = Path.replace

    def locked_replace(self: Path, target_path: Path | str) -> Path:
        if Path(target_path) == target:
            raise PermissionError("state file is locked")
        return original_replace(self, target_path)

    monkeypatch.setattr(Path, "replace", locked_replace)

    desktop_diagnostics_runtime._safe_write_json(target, {"schema": "diagnostics_state"})

    fallback = tmp_path / "latest_desktop_diagnostics_center_state.write_failed.json"
    assert json.loads(fallback.read_text(encoding="utf-8"))["schema"] == "diagnostics_state"
    assert target.read_text(encoding="utf-8") == "{}"


def test_hosted_diagnostics_workspace_page_builds_offscreen_and_refreshes() -> None:
    app = _app()
    workspace = build_workspace_map()["diagnostics"]
    page = DiagnosticsWorkspacePage(workspace, repo_root=ROOT)
    try:
        page.refresh_view()
        app.processEvents()

        assert page.bundle_box.title() == "Текущее состояние архива проекта"
        assert page.run_box.title() == "Последнее сохранение архива"
        assert page.check_box.title() == "Проверка архива проекта"
        assert page.baseline_box.title() == "Опорный прогон"
        assert page.actions_box.title() == "Действия"
        assert page.log_box.title() == "Журнал / последние сообщения"
        assert page.progress_bar.format() == "Готово"
        assert page.progress_bar.minimum() == 0
        assert page.progress_bar.maximum() == 100
        assert page.progress_bar.value() == 100
        assert page.send_button.text() == "Скопировать архив"
        assert "Данные берутся из состояния проверки проекта" in page.source_label.text()
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_diagnostics_page_shows_animation_handoff_material(tmp_path: Path) -> None:
    app = _app()
    repo_root = tmp_path / "repo"
    send_bundles = repo_root / "send_bundles"
    send_bundles.mkdir(parents=True)
    scene_path = repo_root / "result.npz"
    pointer_path = repo_root / "result.json"
    scene_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")
    (send_bundles / "latest_animation_diagnostics_handoff.json").write_text(
        json.dumps(
            {
                "schema": "desktop_animation_diagnostics_handoff",
                "produced_by": "WS-ANIMATOR",
                "consumed_by": "WS-DIAGNOSTICS",
                "selected_artifact": {
                    "title": "Выбранный файл результата",
                    "path": str(scene_path),
                },
                "artifacts": {
                    "scene_npz_path": str(scene_path),
                    "pointer_json_path": str(pointer_path),
                },
                "next_step": "Сохраните архив проекта с текущим материалом.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workspace = build_workspace_map()["diagnostics"]
    page = DiagnosticsWorkspacePage(workspace, repo_root=repo_root)
    try:
        page.refresh_view()
        app.processEvents()

        assert page.animation_handoff_box.objectName() == "DG-ANIMATION-HANDOFF"
        assert page.animation_handoff_source_value.text() == "Выбранный файл результата"
        assert page.animation_handoff_scene_value.text() == str(scene_path)
        assert page.animation_handoff_pointer_value.text() == str(pointer_path)
        assert "Сохраните архив проекта" in page.animation_handoff_next_value.text()

        state_path = send_bundles / "latest_desktop_diagnostics_center_state.json"
        summary_path = send_bundles / "latest_desktop_diagnostics_summary.md"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        summary = summary_path.read_text(encoding="utf-8")
        assert state["machine_paths"]["latest_animation_diagnostics_handoff_json"]
        assert state["animation_diagnostics_handoff"]["selected_path"] == str(scene_path)
        assert state["animation_diagnostics_handoff"]["pointer_json_path"] == str(pointer_path)
        assert "Материал анимации для проверки" in summary
        assert str(scene_path) in summary
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_diagnostics_page_routes_send_and_legacy_actions_through_panel(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    workspace = build_workspace_map()["diagnostics"]
    spawns: list[str] = []
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir()
    zip_path = out_dir / "SEND_mock_bundle.zip"
    zip_path.write_bytes(b"ZIP")

    def fake_copy_latest_bundle_to_clipboard(
        repo_root: Path,
        *,
        out_dir: Path | str | None = None,
        zip_path: Path | str | None = None,
    ):
        return (
            DesktopDiagnosticsBundleRecord(
                out_dir=str(Path(out_dir or tmp_path).resolve()),
                latest_zip_path=str(Path(zip_path or "").resolve()),
                clipboard_ok=True,
                clipboard_message="Clipboard updated for latest bundle: SEND_mock_bundle.zip",
            ),
            True,
            "Clipboard updated for latest bundle: SEND_mock_bundle.zip",
        )

    monkeypatch.setattr(
        diagnostics_panel_module,
        "copy_latest_bundle_to_clipboard",
        fake_copy_latest_bundle_to_clipboard,
    )
    page = DiagnosticsWorkspacePage(
        workspace,
        repo_root=tmp_path,
        spawn_module_fn=lambda module: spawns.append(module),
    )
    try:
        page.controller._current_bundle = DesktopDiagnosticsBundleRecord(
            out_dir=str(out_dir.resolve()),
            latest_zip_path=str(zip_path.resolve()),
        )

        page.handle_command("diagnostics.send_results")
        app.processEvents()
        assert "Архив проекта скопирован" in page.status_label.text()
        page.handle_command("diagnostics.legacy_center.open")
        app.processEvents()

        assert "pneumo_solver_ui.tools.send_results_gui" not in spawns
        assert spawns == ["pneumo_solver_ui.tools.desktop_diagnostics_center"]
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_diagnostics_page_shows_long_action_progress_on_same_surface() -> None:
    app = _app()
    workspace = build_workspace_map()["diagnostics"]
    page = DiagnosticsWorkspacePage(workspace, repo_root=ROOT)
    try:
        page._on_controller_status("Идёт сохранение архива проекта...", True)
        app.processEvents()

        assert page.status_label.text() == "Идёт сохранение архива проекта..."
        assert page.progress_bar.minimum() == 0
        assert page.progress_bar.maximum() == 0
        assert page.progress_bar.format() == "Выполняется"
        assert page.progress_note.text() == "Идёт сохранение архива проекта..."

        page._on_controller_status("Архив проекта сохранён.", False)
        app.processEvents()

        assert page.progress_bar.minimum() == 0
        assert page.progress_bar.maximum() == 100
        assert page.progress_bar.value() == 100
        assert page.progress_bar.format() == "Готово"
        assert page.progress_note.text() == "Архив проекта сохранён."
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
        assert baseline_page.baseline_center_box.title() == "Базовый прогон: просмотр, принятие, восстановление"

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
    assert commands["diagnostics.send_results"].title == "Скопировать архив"
    assert commands["diagnostics.legacy_center.open"].kind == "launch_module"
    assert commands["diagnostics.legacy_center.open"].module == "pneumo_solver_ui.tools.desktop_diagnostics_center"
    assert commands["diagnostics.legacy_center.open"].title == "Сервисная проверка проекта"
    assert commands["diagnostics.legacy_center.open"].availability == "support_fallback"
    assert "центр диагностики" not in commands["diagnostics.legacy_center.open"].title.lower()
    assert "диагностику" not in commands["diagnostics.legacy_center.open"].title.lower()
    assert "отдельным окном" not in commands["diagnostics.legacy_center.open"].title.lower()


def test_hosted_diagnostics_visible_text_avoids_stale_center_labels() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_spec_shell" / "diagnostics_panel.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    for forbidden in (
        "центр опорного прогона",
        "Открыть центр диагностики",
        "Открыт центр диагностики",
        "Текущее состояние архива диагностики",
        "Последний запуск диагностики",
        "Проверка архива диагностики",
        "Данные берутся из состояния диагностики приложения",
    ):
        assert forbidden not in src
