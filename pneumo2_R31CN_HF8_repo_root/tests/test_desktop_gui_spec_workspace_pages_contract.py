from __future__ import annotations

import json
import os
from pathlib import Path
import re

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
    RingWorkspacePage,
    SuiteWorkspacePage,
    _operator_catalog_text,
)
from pneumo_solver_ui.desktop_spec_shell.v19_guidance_widgets import V19_ACTION_FEEDBACK_TITLE
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


def test_gui_spec_imported_catalog_text_is_sanitized_before_display() -> None:
    raw = (
        "Compare и validation; bundle_ready=False; legacy workspace surface; "
        "objective contract; baseline source; run-ов; KPI"
    )
    sanitized = _operator_catalog_text(raw)

    assert sanitized == (
        "Окно сравнения и проверка; архив не готов; отдельное рабочее окно; "
        "цели расчёта; источник опорного прогона; запусков; показателями"
    )
    for forbidden in (
        "Compare и validation",
        "validation",
        "bundle",
        "legacy",
        "workspace",
        "surface",
        "contract",
        "baseline source",
        "run-ов",
        "KPI",
        "False",
        "True",
    ):
        assert forbidden not in sanitized


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
    assert any(fact.label == "Готовность кластеров" for fact in input_data.facts)
    input_visible_text = "\n".join(
        part
        for fact in input_data.facts
        for part in (fact.label, fact.value, fact.detail)
    )
    assert "Эталон base JSON" not in input_visible_text
    assert "готово=" not in input_visible_text
    assert "разделов=" not in input_visible_text

    assert baseline.headline
    assert len(baseline.facts) >= 5
    baseline_labels = {fact.label for fact in baseline.facts}
    assert "Снимок набора и активный опорный прогон" in baseline_labels
    assert "Активный опорный прогон" in baseline_labels
    assert "Действия с опорным прогоном" in baseline_labels
    assert any("Активный опорный прогон -" in line for line in baseline.evidence_lines)

    assert optimization.headline
    assert len(optimization.facts) >= 6
    assert any(fact.label == "Цели оптимизации" for fact in optimization.facts)
    optimization_baseline = next(
        fact for fact in optimization.facts if fact.label == "Происхождение опорного прогона"
    )
    assert "Состояние опорного прогона -" in optimization_baseline.value
    assert "состояние=" not in optimization_baseline.value
    optimization_visible_text = "\n".join(
        part
        for fact in optimization.facts
        for part in (fact.label, fact.value, fact.detail)
    )
    for forbidden in ("StageRunner", "staged", "missing", "включено=", "строк=", "готово="):
        assert forbidden not in optimization_visible_text

    assert results.headline
    assert len(results.facts) >= 5
    assert any(fact.label == "Проверка результата" for fact in results.facts)
    results_visible_text = "\n".join(
        part
        for fact in results.facts
        for part in (fact.label, fact.value, fact.detail)
    )
    results_visible_text += "\n" + "\n".join(results.evidence_lines)
    for forbidden in (
        "Optimizer scope",
        "Browser perf",
        "bundle_ready",
        "release_risk",
        "MISSING",
        "missing",
        "False",
        "True",
        "send-bundle",
    ):
        assert forbidden not in results_visible_text

    assert diagnostics.headline
    assert len(diagnostics.facts) >= 5
    assert any(fact.label == "Последний архив" for fact in diagnostics.facts)


def test_gui_spec_main_window_uses_hosted_pages_for_runtime_and_control_hubs_for_route_pages() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        assert isinstance(window._page_widget_by_workspace_id["input_data"], InputWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["ring_editor"], RingWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["test_matrix"], SuiteWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["animation"], ControlHubWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["baseline_run"], BaselineWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["optimization"], OptimizationWorkspacePage)
        assert window._page_widget_by_workspace_id["optimization"].objectName() == "WS-OPTIMIZATION-HOSTED-PAGE"
        assert isinstance(window._page_widget_by_workspace_id["results_analysis"], ResultsWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["diagnostics"], DiagnosticsWorkspacePage)
        assert callable(getattr(window._page_widget_by_workspace_id["overview"], "refresh_view", None))
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_suite_workspace_page_shows_test_rows_without_launcher_shell() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["test_matrix"]
        assert isinstance(page, SuiteWorkspacePage)
        assert page.objectName() == "WS-SUITE-HOSTED-PAGE"
        page.refresh_view()
        app.processEvents()

        headers = [
            page.suite_table.horizontalHeaderItem(column).text()
            for column in range(page.suite_table.columnCount())
        ]
        assert headers == [
            "Включено",
            "Название",
            "Тип испытания",
            "Первый вход",
            "Шаг, с",
            "Длительность, с",
            "Связанные файлы",
        ]
        assert page.suite_table.rowCount() > 0
        visible_text = "\n".join(
            [
                *(label.text() for label in page.findChildren(QtWidgets.QLabel)),
                *(box.title() for box in page.findChildren(QtWidgets.QGroupBox)),
                *(button.text() for button in page.findChildren(QtWidgets.QPushButton)),
                *headers,
            ]
        )
        assert "Связано с редактором циклического сценария" in visible_text
        assert "Перейти к базовому прогону" in visible_text
        assert "Расширенная настройка набора" in visible_text
        assert "Смысл и правила окна" not in visible_text
        assert "Открытие:" not in visible_text
        assert "stage" not in visible_text
        assert "suite" not in visible_text
        assert "sidecar" not in visible_text
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_optimization_workspace_page_hosts_primary_launch_controls() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["optimization"]
        assert isinstance(page, OptimizationWorkspacePage)
        window.run_command("optimization.center.open")
        app.processEvents()

        assert page.optimization_launch_box.objectName() == "OP-STAGERUNNER-BLOCK"
        visible_buttons = {button.text() for button in page.findChildren(QtWidgets.QPushButton)}
        assert "Проверить готовность" in visible_buttons
        assert "Подготовить основной запуск" in visible_buttons
        assert "Расширенная настройка" in visible_buttons
        assert "Настройка основного запуска открыта" in page.optimization_result_label.text()

        window.run_command("optimization.primary_launch.prepare")
        app.processEvents()
        assert page.optimization_result_label.text()
        assert "optimization.primary_launch.prepare" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_v19_action_feedback_guidance_is_visible_on_route_critical_pages() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        expected_by_workspace = {
            "input_data": "две пружины",
            "ring_editor": "статус шва",
            "optimization": "недобор",
            "diagnostics": "архив",
        }
        for workspace_id, expected in expected_by_workspace.items():
            window.open_workspace(workspace_id)
            app.processEvents()
            page = window._page_widget_by_workspace_id[workspace_id]
            visible_text = "\n".join(
                [
                    *(label.text() for label in page.findChildren(QtWidgets.QLabel)),
                    *(box.title() for box in page.findChildren(QtWidgets.QGroupBox)),
                ]
            )
            assert V19_ACTION_FEEDBACK_TITLE in visible_text
            assert expected in visible_text.casefold()
            assert "contract" not in visible_text
            assert "контракт" not in visible_text.casefold()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_gui_spec_main_window_visible_text_hides_internal_service_terms() -> None:
    app = _app()
    forbidden = re.compile(
        r"\b(workspace|legacy|hosted|surface|pipeline|source-of-truth|master-copy|"
        r"StageRunner|staged|missing|True|False|bundle_ready|release_risk|"
        r"Optimizer scope|Browser perf|send-bundle|validation|KPI|run-ов|"
        r"review_only|Explicit confirmation|Selected history|Field|Status|"
        r"suite|baseline|contract|handoff|snapshot|hash|payload|schema)\b|"
        r"\b(Open .*refresh|current evidence status|Review|Adopt|Restore)\b|"
        r"готово=|состояние=|строк=|включено=|level=|skip_ui_smoke|действие=|статус=|пакет готов=|"
        r"(?-i:контроль:|сверка:|выбрано:|строк:|включено:|режим:|Режим:|"
        r"Открыто:|Открыто " r"окно:|Сводка окна:|Подсказка:|Обязательное условие:|"
        r"Почему это важно:|Где виден результат:|пояснение:|Ограничение:|"
        r"Опорный прогон:|Идентификатор прогона:|Метка прогона:|Состояние опорного прогона:|"
        r"Набор испытаний:|Исходные данные:|Сценарий:|Доступен оптимизатору:|"
        r"Источник данных:|"
        r"базовых параметров:|перебираемых:|расширенных диапазонов:|служебных параметров|"
        r"стадия [^\\n:]+:|ZIP:|готово:|ошибок:|предупреждений:|критичных:|"
        r"справочных:|автотест:|диагностика:|объём проверки:|проверка окна:|"
        r"проверка оптимизации:|лимит оптимизации:|задач:)|"
        r"риск выпуска=|"
        r"GUI-spec|Desktop Shell|Данные машины|Открыть выбранный|статус миграции|контракт|"
        r"Элемент участвует|Берутся из источник данных|Берутся из источника данных|"
        r"[A-Z]{2,}-BTN-[A-Z0-9-]+",
        re.IGNORECASE,
    )
    window = DesktopGuiSpecMainWindow()
    try:
        window.resize(1600, 950)
        window.show()
        app.processEvents()

        hits: list[str] = []
        for workspace_id in window.workspace_by_id:
            window.open_workspace(workspace_id)
            app.processEvents()
            lines: list[tuple[str, str]] = []

            def add_text(where: str, raw: object) -> None:
                text = " ".join(str(raw or "").split()).strip()
                if text and "C:\\" not in text:
                    lines.append((where, text))

            add_text("window_title", window.windowTitle())
            for action in window.menuBar().actions():
                add_text("menu", action.text())
                menu = action.menu()
                if menu is None:
                    continue
                for child in menu.actions():
                    add_text(f"menu/{action.text()}", child.text())
                    add_text(f"menu/{action.text()}.tooltip", child.toolTip())

            for widget in window.findChildren(QtWidgets.QWidget):
                if not widget.isVisibleTo(window):
                    continue
                widget_name = widget.__class__.__name__
                text_getter = getattr(widget, "text", None)
                if callable(text_getter):
                    add_text(widget_name, text_getter())
                title_getter = getattr(widget, "title", None)
                if callable(title_getter):
                    add_text(f"{widget_name}.title", title_getter())
                tooltip_getter = getattr(widget, "toolTip", None)
                if callable(tooltip_getter):
                    add_text(f"{widget_name}.tooltip", tooltip_getter())
                if isinstance(widget, QtWidgets.QComboBox):
                    for index in range(widget.count()):
                        add_text(f"{widget_name}.item", widget.itemText(index))
                if isinstance(widget, QtWidgets.QListWidget):
                    for index in range(widget.count()):
                        add_text(f"{widget_name}.item", widget.item(index).text())
                if isinstance(widget, QtWidgets.QTableWidget):
                    for column in range(widget.columnCount()):
                        item = widget.horizontalHeaderItem(column)
                        if item is not None:
                            add_text(f"{widget_name}.header", item.text())
                    for row in range(min(widget.rowCount(), 5)):
                        for column in range(widget.columnCount()):
                            item = widget.item(row, column)
                            if item is not None:
                                add_text(f"{widget_name}.cell", item.text())

            for where, text in lines:
                if forbidden.search(text):
                    hits.append(f"{workspace_id}::{where}: {text}")

        assert not hits, "\n".join(hits[:20])
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
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, ControlHubWorkspacePage)
        page.refresh_view()
        app.processEvents()

        assert page.surface_box.title() == "Ключевые элементы рабочего шага"
        assert page.actions_box.title() == "Основные действия"
        assert page.workspace.workspace_id == "animation"
        assert len(page.action_commands) >= 1
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

        assert page.objectName() == "WS-BASELINE-HOSTED-PAGE"
        assert page.run_setup_box.objectName() == "BL-RUN-SETUP-PANEL"
        assert page.run_setup_box.title() == "Базовый прогон: настройка и запуск"
        assert page.run_profile_combo.objectName() == "BL-RUN-PROFILE"
        assert page.run_cache_policy_combo.objectName() == "BL-RUN-CACHE-POLICY"
        assert page.run_runtime_policy_combo.objectName() == "BL-RUN-RUNTIME-POLICY"
        assert page.run_setup_check_button.text() == "Проверить готовность"
        assert page.run_setup_checked_launch_button.text() == "Проверить и подготовить запуск"
        assert page.run_setup_plain_launch_button.text() == "Подготовить запуск"
        assert page.run_setup_advanced_button.text() == "Расширенный центр запуска"
        assert "Профиль запуска" in page.run_setup_summary_label.text()
        assert "Готовность набора испытаний" in page.run_setup_gate_label.text()
        page.handle_command("baseline.run_setup.open")
        assert "Настройка запуска открыта" in page.run_setup_result_label.text()
        page.handle_command("baseline.run_setup.verify")
        assert "Проверка готовности" in page.run_setup_result_label.text()
        page.handle_command("baseline.run_setup.prepare")
        assert page.run_setup_result_label.text()

        assert page.baseline_center_box.title() == "Базовый прогон: просмотр, принятие, восстановление"
        assert page.review_button.text() == "Просмотреть"
        assert page.adopt_button.text() == "Принять"
        assert page.restore_button.text() == "Восстановить"
        assert "Explicit confirmation" not in page.explicit_confirmation_checkbox.text()
        assert page.baseline_mismatch_matrix.horizontalHeaderItem(0).text() == "Поле"
        assert page.baseline_mismatch_matrix.horizontalHeaderItem(1).text() == "Активный прогон"
        assert page.baseline_mismatch_matrix.horizontalHeaderItem(2).text() == "Выбранная запись"
        assert page.baseline_mismatch_matrix.horizontalHeaderItem(3).text() == "Сверка"
        assert page.review_button.isEnabled()
        assert not page.adopt_button.isEnabled()
        assert not page.restore_button.isEnabled()
        assert "Молчаливая подмена запрещена" in page.baseline_mismatch_label.text()
        assert page.baseline_mismatch_matrix.objectName() == "BL-MISMATCH-MATRIX"
        assert page.baseline_mismatch_matrix.rowCount() == 5
        matrix_status = {
            page.baseline_mismatch_matrix.item(row, 0).text(): page.baseline_mismatch_matrix.item(row, 3).text()
            for row in range(page.baseline_mismatch_matrix.rowCount())
        }
        assert matrix_status["Опорный прогон"] == "расходится"
        assert matrix_status["Снимок набора"] == "совпадает"
        assert matrix_status["Исходные данные"] == "совпадает"
        assert matrix_status["Циклический сценарий"] == "совпадает"
        assert matrix_status["Режим"] == "совпадает"

        page.handle_command("baseline.review")
        assert "Действие: Просмотреть" in page.action_result_label.text()
        assert "Состояние: просмотр выполнен" in page.action_result_label.text()
        assert "действие=" not in page.action_result_label.text()
        assert "review_only" not in page.action_result_label.text()
        page.handle_command("baseline.restore")
        assert "Действие заблокировано" in page.action_result_label.text()

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


def test_hosted_baseline_workspace_page_warns_before_restore_with_context_mismatch(
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

    historical_suite = build_validated_suite_snapshot(
        [
            {
                "id": "baseline-ui-row-1",
                "имя": "baseline_ui_smoke",
                "тип": "инерция_крен",
                "включен": True,
                "стадия": 0,
                "dt": 0.02,
                "t_end": 1.0,
            }
        ],
        inputs_snapshot_hash="inputs-hash-ui-old",
        ring_source_hash="ring-hash-ui",
        created_at_utc="2026-04-17T00:09:00Z",
        context_label="baseline-ui-historical",
    )
    active = build_active_baseline_contract(
        suite_snapshot=suite_snapshot,
        baseline_path=tmp_path / "baseline_active.json",
        baseline_payload={"param_a": 1.0},
        baseline_meta={"problem_hash": "ph-baseline-ui"},
        source_run_dir=tmp_path / "runs" / "active",
        policy_mode="review_adopt",
        created_at_utc="2026-04-17T00:10:00Z",
    )
    candidate = build_active_baseline_contract(
        suite_snapshot=historical_suite,
        baseline_path=tmp_path / "baseline_historical.json",
        baseline_payload={"param_a": 2.0},
        baseline_meta={"problem_hash": "ph-baseline-ui-old"},
        source_run_dir=tmp_path / "runs" / "historical",
        policy_mode="restore_only",
        created_at_utc="2026-04-17T00:11:00Z",
    )
    write_active_baseline_contract(active, workspace_dir=workspace_dir)
    history_item = baseline_history_item_from_contract(candidate, action="restore", actor="unit")
    append_baseline_history_item(history_item, workspace_dir=workspace_dir)

    page = BaselineWorkspacePage(
        build_workspace_map()["baseline_run"],
        (),
        lambda _command_id: None,
        repo_root=ROOT,
    )
    try:
        app.processEvents()

        assert page.review_button.isEnabled()
        assert not page.adopt_button.isEnabled()
        assert not page.restore_button.isEnabled()
        assert "Снимок набора" in page.baseline_banner_label.text()
        assert "Исходные данные" in page.baseline_banner_label.text()
        assert "Режим" in page.baseline_banner_label.text()
        assert "Молчаливая подмена запрещена" in page.baseline_mismatch_label.text()
        matrix_status = {
            page.baseline_mismatch_matrix.item(row, 0).text(): page.baseline_mismatch_matrix.item(row, 3).text()
            for row in range(page.baseline_mismatch_matrix.rowCount())
        }
        assert matrix_status["Снимок набора"] == "расходится"
        assert matrix_status["Исходные данные"] == "расходится"
        assert matrix_status["Циклический сценарий"] == "совпадает"
        assert matrix_status["Режим"] == "расходится"

        blocked_restore = page.apply_baseline_action("restore")
        assert blocked_restore["status"] == "blocked"
        assert read_active_baseline_contract(workspace_dir=workspace_dir)["active_baseline_hash"] == active["active_baseline_hash"]

        page.explicit_confirmation_checkbox.setChecked(True)
        app.processEvents()
        assert not page.adopt_button.isEnabled()
        assert page.restore_button.isEnabled()
        page._confirm_baseline_action = lambda _action, _surface: True  # type: ignore[method-assign]

        blocked_adopt = page.apply_baseline_action("adopt")
        assert blocked_adopt["status"] == "blocked"
        assert read_active_baseline_contract(workspace_dir=workspace_dir)["active_baseline_hash"] == active["active_baseline_hash"]

        applied_restore = page.apply_baseline_action("restore")
        assert applied_restore["status"] == "applied"
        assert applied_restore["silent_rebinding_allowed"] is False
        assert read_active_baseline_contract(workspace_dir=workspace_dir)["active_baseline_hash"] == candidate["active_baseline_hash"]
        assert read_baseline_history(workspace_dir=workspace_dir)[-1]["action"] == "restore"
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
