from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest
from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_baseline_run_runtime import (
    DESKTOP_SINGLE_RUN_MODULE,
    baseline_run_launch_request_path,
    prepare_baseline_run_launch_request,
)
from pneumo_solver_ui.desktop_results_model import DesktopResultsArtifact
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
from pneumo_solver_ui.desktop_input_model import (
    load_base_with_defaults,
    save_desktop_inputs_snapshot,
)
from pneumo_solver_ui.desktop_spec_shell import workspace_pages as workspace_pages_module
from pneumo_solver_ui.desktop_suite_snapshot import build_validated_suite_snapshot
from pneumo_solver_ui.desktop_spec_shell.diagnostics_panel import DiagnosticsWorkspacePage
from pneumo_solver_ui.desktop_spec_shell.main_window import DesktopGuiSpecMainWindow
from pneumo_solver_ui.desktop_spec_shell.registry import build_workspace_map
from pneumo_solver_ui.desktop_spec_shell.workspace_pages import (
    AnimationWorkspacePage,
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


def _write_launch_ready_baseline_handoffs(workspace_dir: Path) -> dict[str, object]:
    inputs_path = workspace_dir / "handoffs" / "WS-INPUTS" / "inputs_snapshot.json"
    save_desktop_inputs_snapshot(load_base_with_defaults(), target_path=inputs_path)
    inputs_snapshot = json.loads(inputs_path.read_text(encoding="utf-8"))
    suite_snapshot = build_validated_suite_snapshot(
        [
            {
                "id": "baseline-ui-launch-row-1",
                "имя": "baseline_ui_launch",
                "тип": "инерция_крен",
                "включен": True,
                "стадия": 0,
                "dt": 0.01,
                "t_end": 1.0,
            }
        ],
        inputs_snapshot_ref=inputs_path,
        inputs_snapshot_hash=str(inputs_snapshot["payload_hash"]),
        ring_source_hash="ring-hash-ui",
        created_at_utc="2026-04-17T00:20:00Z",
        context_label="baseline-ui-launch",
    )
    suite_path = baseline_suite_handoff_snapshot_path(workspace_dir=workspace_dir)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "inputs_path": inputs_path,
        "suite_path": suite_path,
        "suite_snapshot": suite_snapshot,
    }


def test_baseline_run_launch_runtime_blocks_without_suite_snapshot(tmp_path: Path, monkeypatch) -> None:
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))

    request = prepare_baseline_run_launch_request(
        {"launch_profile": "detail", "cache_policy": "reuse", "runtime_policy": "balanced"},
        repo_root=ROOT,
        python_executable="python-test",
    )
    request_path = baseline_run_launch_request_path(repo_root=ROOT, workspace_dir=workspace_dir)

    assert request["execution_ready"] is False
    assert request["command"] == []
    assert "нет зафиксированного набора испытаний" in request["operator_blockers"]
    assert request_path.exists()
    assert json.loads(request_path.read_text(encoding="utf-8"))["execution_ready"] is False


def test_baseline_run_launch_runtime_prepares_desktop_single_run_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    _write_launch_ready_baseline_handoffs(workspace_dir)

    request = prepare_baseline_run_launch_request(
        {
            "launch_profile": "detail",
            "cache_policy": "reuse",
            "runtime_policy": "balanced",
            "run_dt": 0.003,
            "run_t_end": 1.6,
            "export_csv": True,
            "export_npz": False,
            "record_full": False,
        },
        repo_root=ROOT,
        python_executable="python-test",
    )
    paths = dict(request["paths"])
    command = list(request["command"])

    assert request["execution_ready"] is True
    assert request["command_module"] == DESKTOP_SINGLE_RUN_MODULE
    assert command[:3] == ["python-test", "-m", DESKTOP_SINGLE_RUN_MODULE]
    assert "--params" in command
    assert "--test" in command
    assert "--outdir" in command
    assert Path(str(paths["prepared_inputs"])).exists()
    assert Path(str(paths["prepared_suite"])).exists()
    assert str(workspace_dir.resolve()) in str(paths["run_dir"])
    assert json.loads(Path(str(paths["request"])).read_text(encoding="utf-8"))["execution_ready"] is True


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
        assert window._page_widget_by_workspace_id["input_data"].objectName() == "WS-INPUTS-HOSTED-PAGE"
        assert isinstance(window._page_widget_by_workspace_id["ring_editor"], RingWorkspacePage)
        assert window._page_widget_by_workspace_id["ring_editor"].objectName() == "WS-RING-HOSTED-PAGE"
        assert isinstance(window._page_widget_by_workspace_id["test_matrix"], SuiteWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["animation"], AnimationWorkspacePage)
        assert window._page_widget_by_workspace_id["animation"].objectName() == "WS-ANIMATOR-HOSTED-PAGE"
        assert isinstance(window._page_widget_by_workspace_id["baseline_run"], BaselineWorkspacePage)
        assert isinstance(window._page_widget_by_workspace_id["optimization"], OptimizationWorkspacePage)
        assert window._page_widget_by_workspace_id["optimization"].objectName() == "WS-OPTIMIZATION-HOSTED-PAGE"
        assert isinstance(window._page_widget_by_workspace_id["results_analysis"], ResultsWorkspacePage)
        assert window._page_widget_by_workspace_id["results_analysis"].objectName() == "WS-ANALYSIS-HOSTED-PAGE"
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
        assert page.suite_table.objectName() == "TS-TABLE"
        assert page.validation_label.objectName() == "TS-VALIDATION-SUMMARY"
        assert page.check_button.objectName() == "TS-BTN-VALIDATE"
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

        window.run_command("test.center.open")
        app.processEvents()
        assert "Проверка набора открыта" in page.validation_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_suite_workspace_page_keeps_read_error_message_when_open_command_fails(
    monkeypatch,
) -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["test_matrix"]
        assert isinstance(page, SuiteWorkspacePage)

        def _raise_suite_read_error(_path: Path) -> list[dict[str, object]]:
            raise RuntimeError("suite read failed")

        monkeypatch.setattr(workspace_pages_module, "load_suite_rows", _raise_suite_read_error)

        window.run_command("test.center.open")
        app.processEvents()

        assert page.suite_table.rowCount() == 0
        assert "Не удалось прочитать основной набор испытаний." in page.validation_label.text()
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
        assert "Запустить оптимизацию" in visible_buttons
        assert "Мягкая остановка" in visible_buttons
        assert "Остановить сейчас" in visible_buttons
        assert "Открыть журнал" in visible_buttons
        assert "Открыть папку запуска" in visible_buttons
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


def test_optimization_workspace_page_runs_stage_runner_through_hosted_surface(tmp_path, monkeypatch) -> None:
    class _FakeProc:
        def __init__(self) -> None:
            self.returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

    class _FakeOptimizerRuntime:
        instances: list["_FakeOptimizerRuntime"] = []

        def __init__(self, *, ui_root: Path, python_executable: str | None = None) -> None:
            self.ui_root = Path(ui_root)
            self.python_executable = python_executable
            self.job: SimpleNamespace | None = None
            self.soft_stop_requested = False
            self.hard_stop_requested = False
            self.run_dir = tmp_path / "opt_runs" / "staged" / "fake-stage-runner"
            self.log_path = self.run_dir / "stage_runner.log"
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text("done=1/3\n", encoding="utf-8")
            self.instances.append(self)

        def contract_snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(
                objective_keys=("objective_clearance",),
                penalty_key="penalty_total",
                penalty_tol=0.0,
                optimizer_baseline_can_consume=True,
                enabled_suite_total=1,
                suite_row_count=1,
                search_param_count=2,
                base_param_count=5,
                active_baseline_hash="baseline-hash",
                active_baseline_state="active",
            )

        def latest_pointer_summary(self) -> dict[str, object]:
            return {"exists": False}

        def current_job(self) -> SimpleNamespace | None:
            return self.job

        def start_job(self) -> SimpleNamespace:
            self.job = SimpleNamespace(
                proc=_FakeProc(),
                run_dir=self.run_dir,
                log_path=self.log_path,
                backend="StageRunner",
                pipeline_mode="staged",
            )
            return self.job

        def active_job_surface(self) -> dict[str, object]:
            return {"returncode": None, "captions": ("done=1/3",)}

        def request_soft_stop(self) -> bool:
            self.soft_stop_requested = True
            return True

        def request_hard_stop(self) -> bool:
            self.hard_stop_requested = True
            if self.job is not None:
                self.job.proc.returncode = -15
            return True

    opened_paths: list[str] = []
    settings_path = tmp_path / "desktop_spec_shell_optimization_execution_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    monkeypatch.setattr(workspace_pages_module, "DesktopOptimizerRuntime", _FakeOptimizerRuntime)
    monkeypatch.setattr(
        workspace_pages_module.QtGui.QDesktopServices,
        "openUrl",
        lambda url: opened_paths.append(url.toLocalFile()) or True,
    )

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["optimization"]
        assert isinstance(page, OptimizationWorkspacePage)

        window.run_command("optimization.primary_launch.execute")
        app.processEvents()

        runtime = _FakeOptimizerRuntime.instances[-1]
        assert runtime.job is not None
        assert "Оптимизация запущена" in page.optimization_result_label.text()
        assert page.optimization_execute_button.isEnabled() is False
        assert page.optimization_soft_stop_button.isEnabled() is True
        assert "optimization.primary_launch.execute" in window.recent_command_ids

        window.run_command("optimization.primary_launch.open_log")
        window.run_command("optimization.primary_launch.open_run_dir")
        assert [Path(path) for path in opened_paths[-2:]] == [runtime.log_path, runtime.run_dir]

        window.run_command("optimization.primary_launch.soft_stop")
        assert runtime.soft_stop_requested is True
        assert "Мягкая остановка" in page.optimization_result_label.text()

        window.run_command("optimization.primary_launch.hard_stop")
        app.processEvents()
        assert runtime.hard_stop_requested is True
        assert page.optimization_soft_stop_button.isEnabled() is False
        assert "Остановка активного запуска" in page.optimization_result_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_results_workspace_page_hosts_analysis_and_compare_controls() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["results_analysis"]
        assert isinstance(page, ResultsWorkspacePage)
        window.run_command("results.center.open")
        app.processEvents()

        assert page.results_analysis_box.objectName() == "RS-LEADERBOARD"
        visible_buttons = {button.text() for button in page.findChildren(QtWidgets.QPushButton)}
        assert "Обновить анализ" in visible_buttons
        assert "Подготовить сравнение" in visible_buttons
        assert "Открыть сравнение" in visible_buttons
        assert "Передать в анимацию" in visible_buttons
        assert "Подготовить материалы проверки" in visible_buttons
        assert "Расширенный анализ" in visible_buttons
        assert "Анализ результатов открыт" in page.results_action_label.text()
        assert page.results_overview_table.columnCount() == 4
        assert page.results_artifacts_table.columnCount() == 3
        assert page.results_compare_preview_box.objectName() == "RS-COMPARE-PREVIEW"
        assert page.results_compare_preview_table.columnCount() == 2
        assert page.results_compare_preview_table.rowCount() >= 4
        assert page.results_chart_preview_box.objectName() == "RS-CHART-PREVIEW"
        assert page.results_chart_preview_table.columnCount() == 4
        assert page.results_chart_preview_table.rowCount() >= 1

        window.run_command("results.evidence.prepare")
        app.processEvents()
        assert "Материалы проверки подготовлены" in page.results_action_label.text()
        assert "results.evidence.prepare" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_results_workspace_page_renders_native_chart_preview(tmp_path, monkeypatch) -> None:
    npz_path = tmp_path / "chart_result.npz"
    npz_path.write_bytes(b"NPZ")

    class _FakeResultsRuntime:
        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable

        def snapshot(self) -> SimpleNamespace:
            artifact = SimpleNamespace(
                key="latest_npz",
                title="Последний файл результата",
                category="results",
                path=npz_path,
                detail="",
            )
            return SimpleNamespace(
                result_context_state="CURRENT",
                result_context_banner="Свежий результат готов к графикам.",
                validation_overview_rows=(
                    SimpleNamespace(
                        title="Графики",
                        status="READY",
                        detail="Числовые серии найдены.",
                        next_action="Проверьте графики.",
                    ),
                ),
                recent_artifacts=(artifact,),
                latest_npz_path=npz_path,
                latest_pointer_json_path=None,
                latest_mnemo_event_log_path=None,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="нет данных",
                mnemo_recent_titles=(),
                operator_recommendations=("Проверьте графики.",),
                selected_run_contract_status="CURRENT",
                selected_run_contract_banner="Выбранный прогон актуален.",
            )

        def artifact_by_key(self, snapshot: SimpleNamespace, artifact_key: str) -> SimpleNamespace | None:
            for artifact in snapshot.recent_artifacts:
                if artifact.key == artifact_key:
                    return artifact
            return None

        def compare_viewer_path(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> Path | None:
            return artifact.path if artifact is not None else snapshot.latest_npz_path

        def artifact_preview_lines(self, artifact: SimpleNamespace) -> tuple[str, ...]:
            return (f"Файл результата: {artifact.path.name}", "Размер: 3 байт")

        def chart_preview_rows(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> tuple[dict[str, str], ...]:
            return (
                {
                    "series": "z_body_mm",
                    "points": "1200; форма 1200",
                    "range": "-10 .. 35",
                    "role": "готово к графику",
                },
                {
                    "series": "roll_deg",
                    "points": "1200; форма 1200",
                    "range": "-3 .. 4",
                    "role": "готово к графику",
                },
            )

        def chart_preview_series_samples(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> dict[str, object]:
            return {
                "status": "READY",
                "series": "z_body_mm",
                "samples": (-10.0, -5.0, 0.0, 20.0, 35.0),
                "point_count": 1200,
                "range": "-10 .. 35",
            }

    settings_path = tmp_path / "desktop_spec_shell_results_chart_preview_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    app = _app()
    window = DesktopGuiSpecMainWindow()
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)
    try:
        page = window._page_widget_by_workspace_id["results_analysis"]
        assert isinstance(page, ResultsWorkspacePage)

        window.run_command("results.center.open")
        app.processEvents()

        chart_values = {
            page.results_chart_preview_table.item(row, column).text()
            for row in range(page.results_chart_preview_table.rowCount())
            for column in range(page.results_chart_preview_table.columnCount())
            if page.results_chart_preview_table.item(row, column) is not None
        }
        assert "z_body_mm" in chart_values
        assert "roll_deg" in chart_values
        assert "1200; форма 1200" in chart_values
        assert "-10 .. 35" in chart_values
        assert "готово к графику" in chart_values
        assert page.results_chart_preview_view.objectName() == "RS-CHART-NATIVE-PREVIEW"
        assert page.results_chart_preview_view.scene().items()
        assert "z_body_mm" in page.results_chart_preview_view.toolTip()
        assert "-10" in page.results_chart_preview_view.toolTip()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_results_workspace_page_updates_previews_for_selected_artifact(tmp_path, monkeypatch) -> None:
    latest_path = tmp_path / "latest_result.npz"
    selected_path = tmp_path / "selected_result.npz"
    latest_path.write_bytes(b"NPZ")
    selected_path.write_bytes(b"NPZ")

    class _FakeResultsRuntime:
        handoff_paths: list[Path | None] = []

        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable

        def snapshot(self) -> SimpleNamespace:
            artifacts = (
                SimpleNamespace(
                    key="latest_npz",
                    title="Последний файл результата",
                    category="results",
                    path=latest_path,
                    detail="",
                ),
                SimpleNamespace(
                    key="selected_npz",
                    title="Выбранный файл результата",
                    category="results",
                    path=selected_path,
                    detail="",
                ),
            )
            return SimpleNamespace(
                result_context_state="CURRENT",
                result_context_banner="Свежий результат готов к выбору.",
                validation_overview_rows=(
                    SimpleNamespace(
                        title="Результат",
                        status="READY",
                        detail="Есть несколько материалов.",
                        next_action="Выберите материал.",
                    ),
                ),
                recent_artifacts=artifacts,
                latest_npz_path=latest_path,
                latest_pointer_json_path=None,
                latest_mnemo_event_log_path=None,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="нет данных",
                mnemo_recent_titles=(),
                operator_recommendations=("Выберите материал.",),
                selected_run_contract_status="CURRENT",
                selected_run_contract_banner="Выбранный прогон актуален.",
            )

        def artifact_by_key(self, snapshot: SimpleNamespace, artifact_key: str) -> SimpleNamespace | None:
            for artifact in snapshot.recent_artifacts:
                if artifact.key == artifact_key:
                    return artifact
            return None

        def compare_viewer_path(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> Path | None:
            return artifact.path if artifact is not None else snapshot.latest_npz_path

        def artifact_preview_lines(self, artifact: SimpleNamespace) -> tuple[str, ...]:
            return (f"Файл результата: {artifact.path.name}",)

        def chart_preview_rows(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> tuple[dict[str, str], ...]:
            name = artifact.path.stem if artifact is not None else "latest_result"
            return (
                {
                    "series": f"{name}_series",
                    "points": "42; форма 42",
                    "range": "1 .. 2",
                    "role": "готово к графику",
                },
            )

        def chart_preview_series_samples(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> dict[str, object]:
            name = artifact.path.stem if artifact is not None else "latest_result"
            return {
                "status": "READY",
                "series": f"{name}_series",
                "samples": (1.0, 1.5, 2.0),
                "point_count": 42,
                "range": "1 .. 2",
            }

        def write_analysis_animation_handoff(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> Path:
            self.__class__.handoff_paths.append(artifact.path if artifact is not None else None)
            path = tmp_path / "latest_analysis_animation_handoff.json"
            path.write_text("{}", encoding="utf-8")
            return path

    settings_path = tmp_path / "desktop_spec_shell_results_selected_preview_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    app = _app()
    window = DesktopGuiSpecMainWindow()
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)
    try:
        page = window._page_widget_by_workspace_id["results_analysis"]
        assert isinstance(page, ResultsWorkspacePage)

        window.run_command("results.center.open")
        app.processEvents()
        page.results_artifacts_table.selectRow(1)
        app.processEvents()

        compare_values = {
            page.results_compare_preview_table.item(row, 1).text()
            for row in range(page.results_compare_preview_table.rowCount())
            if page.results_compare_preview_table.item(row, 1) is not None
        }
        chart_values = {
            page.results_chart_preview_table.item(row, column).text()
            for row in range(page.results_chart_preview_table.rowCount())
            for column in range(page.results_chart_preview_table.columnCount())
            if page.results_chart_preview_table.item(row, column) is not None
        }
        assert "selected_result.npz" in compare_values
        assert "selected_result_series" in chart_values
        assert "latest_result_series" not in chart_values
        assert "selected_result_series" in page.results_chart_preview_view.toolTip()
        assert page.results_compare_window_button.isEnabled()

        window.run_command("results.animation.prepare")
        app.processEvents()
        assert _FakeResultsRuntime.handoff_paths == [selected_path]
        assert "Материал передан в анимацию" in page.results_action_label.text()
        assert "results.animation.prepare" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_results_runtime_extracts_npz_chart_preview_rows(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    npz_path = tmp_path / "runtime_chart_result.npz"
    np.savez(
        npz_path,
        z_body_mm=np.array([0.0, 2.0, 4.0]),
        roll_deg=np.array([-3.0, 0.5, 4.0]),
        labels=np.array(["start", "middle", "end"]),
    )
    runtime = DesktopResultsRuntime(repo_root=tmp_path, python_executable=sys.executable)
    snapshot = SimpleNamespace(latest_npz_path=npz_path, recent_artifacts=())
    artifact = SimpleNamespace(path=npz_path)

    rows = runtime.chart_preview_rows(snapshot, artifact=artifact)
    rows_by_series = {row["series"]: row for row in rows}
    samples = runtime.chart_preview_series_samples(snapshot, artifact=artifact, max_points=2)

    assert rows_by_series["z_body_mm"]["points"] == "3; форма 3"
    assert rows_by_series["z_body_mm"]["range"] == "0 .. 4"
    assert rows_by_series["roll_deg"]["range"] == "-3 .. 4"
    assert "labels" not in rows_by_series
    assert samples["status"] == "READY"
    assert samples["series"] == "z_body_mm"
    assert samples["samples"] == (0.0, 4.0)
    assert samples["point_count"] == 3
    assert samples["range"] == "0 .. 4"


def test_results_runtime_extracts_animation_scene_preview_points(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    npz_path = tmp_path / "runtime_scene_result.npz"
    pointer_path = tmp_path / "runtime_scene_result.json"
    pointer_path.write_text("{}", encoding="utf-8")
    np.savez(
        npz_path,
        z_body_mm=np.array([1.0, 2.0, 3.0]),
        time_s=np.array([0.0, 1.0, 2.0]),
        labels=np.array(["start", "middle", "end"]),
    )
    runtime = DesktopResultsRuntime(repo_root=tmp_path, python_executable=sys.executable)
    snapshot = SimpleNamespace(latest_npz_path=npz_path, latest_pointer_json_path=pointer_path)

    preview = runtime.animation_scene_preview_points(snapshot, max_points=2)

    assert preview["status"] == "READY"
    assert preview["series_y"] == "z_body_mm"
    assert preview["series_x"] == "time_s"
    assert preview["points"] == ((0.0, 1.0), (2.0, 3.0))
    assert preview["point_count"] == 3
    assert preview["source_path"] == str(npz_path)
    assert preview["pointer_path"] == str(pointer_path)


def test_results_runtime_writes_animation_handoff_for_selected_artifact(tmp_path) -> None:
    latest_path = tmp_path / "latest_result.npz"
    selected_path = tmp_path / "selected_result.npz"
    pointer_path = tmp_path / "selected_result.json"
    latest_path.write_bytes(b"NPZ")
    selected_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")

    runtime = DesktopResultsRuntime(repo_root=tmp_path, python_executable=sys.executable)
    snapshot = SimpleNamespace(
        latest_npz_path=latest_path,
        latest_pointer_json_path=None,
        latest_mnemo_event_log_path=None,
        latest_capture_export_manifest_path=None,
        selected_run_contract_path=None,
        result_context_state="CURRENT",
        result_context_banner="Выбранный результат готов.",
        recent_artifacts=(),
    )
    artifact = DesktopResultsArtifact(
        key="selected_npz",
        title="Выбранный файл результата",
        category="results",
        path=selected_path,
    )

    handoff_path = runtime.write_analysis_animation_handoff(snapshot, artifact=artifact)
    payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff_artifact = runtime.animation_handoff_artifact(snapshot)

    assert payload["produced_by"] == "WS-ANALYSIS"
    assert payload["consumed_by"] == "WS-ANIMATOR"
    assert payload["selected_artifact"]["path"] == str(selected_path)
    assert payload["artifacts"]["latest_npz_path"] == str(selected_path)
    assert payload["artifacts"]["latest_pointer_json_path"] == str(pointer_path)
    assert handoff_artifact is not None
    assert handoff_artifact.path == selected_path


def test_results_runtime_writes_animation_diagnostics_handoff(tmp_path) -> None:
    selected_path = tmp_path / "selected_result.npz"
    pointer_path = tmp_path / "selected_result.json"
    mnemo_path = tmp_path / "selected_result.desktop_mnemo_events.json"
    selected_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")
    mnemo_path.write_text("{}", encoding="utf-8")

    runtime = DesktopResultsRuntime(repo_root=tmp_path, python_executable=sys.executable)
    snapshot = SimpleNamespace(
        latest_npz_path=None,
        latest_pointer_json_path=None,
        latest_mnemo_event_log_path=mnemo_path,
        latest_capture_export_manifest_path=None,
        latest_capture_export_manifest_status="READY",
        recent_artifacts=(),
    )
    artifact = DesktopResultsArtifact(
        key="selected_npz",
        title="Выбранный файл результата",
        category="results",
        path=selected_path,
    )

    handoff_path = runtime.write_animation_diagnostics_handoff(snapshot, artifact=artifact)
    payload = json.loads(handoff_path.read_text(encoding="utf-8"))

    assert payload["produced_by"] == "WS-ANIMATOR"
    assert payload["consumed_by"] == "WS-DIAGNOSTICS"
    assert payload["selected_artifact"]["path"] == str(selected_path)
    assert payload["artifacts"]["scene_npz_path"] == str(selected_path)
    assert payload["artifacts"]["pointer_json_path"] == str(pointer_path)
    assert payload["artifacts"]["mnemo_event_log_path"] == str(mnemo_path)
    assert payload["animation_context"]["scene_ready"] is True

    evidence_snapshot = SimpleNamespace(
        latest_npz_path=selected_path,
        latest_pointer_json_path=pointer_path,
        latest_mnemo_event_log_path=mnemo_path,
        latest_capture_export_manifest_path=None,
        latest_capture_export_manifest_status="READY",
        latest_autotest_run_dir=None,
        latest_diagnostics_run_dir=None,
        latest_optimizer_pointer_json_path=None,
        latest_optimizer_run_dir=None,
        latest_validation_json_path=None,
        latest_validation_md_path=None,
        validation_ok=None,
        validation_errors=(),
        validation_warnings=(),
        selected_run_contract_path=None,
        selected_run_contract_hash="",
        selected_run_contract_status="MISSING",
        selected_run_contract_banner="",
        result_context_state="CURRENT",
        result_context_banner="Свежий результат готов.",
        result_context_detail="",
        result_context_action="",
        result_context_fields=(),
        recent_artifacts=(artifact,),
    )
    manifest = runtime.build_diagnostics_evidence_manifest(evidence_snapshot)

    assert manifest["animation_diagnostics_handoff"]["status"] == "READY"
    assert manifest["animation_diagnostics_handoff"]["sidecar_path"] == str(handoff_path)
    assert manifest["animation_diagnostics_handoff"]["selected_artifact"]["path"] == str(selected_path)
    assert manifest["animation_diagnostics_handoff"]["artifacts"]["scene_npz_path"] == str(selected_path)


def test_results_workspace_page_opens_compare_through_hosted_surface(tmp_path, monkeypatch) -> None:
    npz_path = tmp_path / "latest_result.npz"
    npz_path.write_bytes(b"NPZ")

    class _FakeResultsRuntime:
        instances: list["_FakeResultsRuntime"] = []
        launched_paths: list[Path | None] = []

        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable
            self.launched_artifact: SimpleNamespace | None = None
            self.instances.append(self)

        def snapshot(self) -> SimpleNamespace:
            artifact = SimpleNamespace(
                key="latest_npz",
                title="Последний файл результата",
                category="results",
                path=npz_path,
                detail="",
            )
            return SimpleNamespace(
                result_context_state="CURRENT",
                result_context_banner="Свежий результат готов к сравнению.",
                validation_overview_rows=(
                    SimpleNamespace(
                        title="Результат",
                        status="READY",
                        detail="Файл результата найден.",
                        next_action="Открыть сравнение.",
                    ),
                ),
                recent_artifacts=(artifact,),
                latest_npz_path=npz_path,
                latest_pointer_json_path=None,
                latest_mnemo_event_log_path=None,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="нет данных",
                mnemo_recent_titles=(),
                operator_recommendations=("Откройте сравнение.",),
                selected_run_contract_status="CURRENT",
                selected_run_contract_banner="Выбранный прогон актуален.",
            )

        def artifact_by_key(self, snapshot: SimpleNamespace, artifact_key: str) -> SimpleNamespace | None:
            for artifact in snapshot.recent_artifacts:
                if artifact.key == artifact_key:
                    return artifact
            return None

        def compare_viewer_path(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> Path | None:
            return (artifact.path if artifact is not None else snapshot.latest_npz_path)

        def artifact_preview_lines(self, artifact: SimpleNamespace) -> tuple[str, ...]:
            return (f"Файл результата: {artifact.path.name}", "Размер: 3 байт")

        def launch_compare_viewer(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> SimpleNamespace:
            self.launched_artifact = artifact
            self.__class__.launched_paths.append(
                self.compare_viewer_path(snapshot, artifact=artifact)
            )
            return SimpleNamespace(pid=321)

    settings_path = tmp_path / "desktop_spec_shell_results_compare_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)

    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["results_analysis"]
        assert isinstance(page, ResultsWorkspacePage)
        page.results_artifacts_table.selectRow(0)

        window.run_command("results.compare.open")
        app.processEvents()

        assert _FakeResultsRuntime.launched_paths == [npz_path]
        preview_values = {
            page.results_compare_preview_table.item(row, 1).text()
            for row in range(page.results_compare_preview_table.rowCount())
            if page.results_compare_preview_table.item(row, 1) is not None
        }
        assert "latest_result.npz" in preview_values
        assert "Сравнение открывается" in page.results_action_label.text()
        assert "results.compare.open" in window.recent_command_ids
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
        assert page.input_editor_box.objectName() == "ID-PARAM-TABLE"
        assert page.input_table.columnCount() == 5
        assert page.input_table.rowCount() > 0
        visible_buttons = {button.text() for button in page.findChildren(QtWidgets.QPushButton)}
        assert "Сохранить рабочую копию" in visible_buttons
        assert "Зафиксировать снимок для маршрута" in visible_buttons
        assert "Расширенный редактор" in visible_buttons
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_ring_workspace_page_hosts_segment_editor_controls() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["ring_editor"]
        assert isinstance(page, RingWorkspacePage)
        window.run_command("ring.editor.open")
        app.processEvents()

        assert page.ring_editor_box.objectName() == "RG-SEGMENT-LIST"
        assert page.ring_segment_table.columnCount() == 7
        assert page.ring_segment_table.rowCount() > 0
        visible_buttons = {button.text() for button in page.findChildren(QtWidgets.QPushButton)}
        assert "Добавить сегмент" in visible_buttons
        assert "Дублировать сегмент" in visible_buttons
        assert "Сохранить сценарий" in visible_buttons
        assert "Проверить шов" in visible_buttons
        assert "Расширенный редактор" in visible_buttons
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_control_hub_pages_render_catalog_surface_summary_and_actions() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["tools"]
        assert isinstance(page, ControlHubWorkspacePage)
        page.refresh_view()
        app.processEvents()

        assert page.surface_box.title() == "Ключевые элементы рабочего шага"
        assert page.actions_box.title() == "Основные действия"
        assert page.workspace.workspace_id == "tools"
        assert len(page.action_commands) >= 1
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_animation_workspace_page_hosts_route_aware_animation_hub() -> None:
    app = _app()
    window = DesktopGuiSpecMainWindow()
    try:
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, AnimationWorkspacePage)
        window.run_command("animation.animator.open")
        app.processEvents()

        assert page.animation_hub_box.objectName() == "AM-VIEWPORT"
        visible_buttons = {button.text() for button in page.findChildren(QtWidgets.QPushButton)}
        assert "Обновить анимацию" in visible_buttons
        assert "Проверить аниматор" in visible_buttons
        assert "Проверить мнемосхему" in visible_buttons
        assert "Проверить движение" in visible_buttons
        assert "Проверить схему" in visible_buttons
        assert "Передать в проверку проекта" in visible_buttons
        assert page.animation_status_table.columnCount() == 3
        assert page.animation_scene_preview_box.objectName() == "AM-SCENE-PREVIEW"
        assert page.animation_scene_preview_table.columnCount() == 2
        assert page.animation_scene_preview_table.rowCount() >= 5
        assert "Анимация открыта" in page.animation_action_label.text()

        window.run_command("animation.mnemo.open")
        app.processEvents()
        assert "Мнемосхема открыта" in page.animation_action_label.text()
        assert "animation.mnemo.open" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_animation_workspace_page_renders_native_scene_preview(tmp_path, monkeypatch) -> None:
    npz_path = tmp_path / "scene_result.npz"
    pointer_path = tmp_path / "scene_result.json"
    event_log_path = tmp_path / "scene_result.desktop_mnemo_events.json"
    capture_path = tmp_path / "scene_result.capture_manifest.json"
    npz_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")
    event_log_path.write_text("{}", encoding="utf-8")
    capture_path.write_text("{}", encoding="utf-8")

    class _FakeResultsRuntime:
        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable

        def snapshot(self) -> SimpleNamespace:
            artifacts = (
                SimpleNamespace(key="latest_npz", path=npz_path),
                SimpleNamespace(key="latest_pointer", path=pointer_path),
                SimpleNamespace(key="mnemo_event_log", path=event_log_path),
                SimpleNamespace(key="capture_export_manifest", path=capture_path),
            )
            return SimpleNamespace(
                latest_npz_path=npz_path,
                latest_pointer_json_path=pointer_path,
                latest_mnemo_event_log_path=event_log_path,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="overview",
                mnemo_recent_titles=("Давление проверено",),
                operator_recommendations=("Проверьте движение.",),
                recent_artifacts=artifacts,
            )

        def artifact_by_key(
            self,
            snapshot: SimpleNamespace,
            artifact_key: str,
        ) -> SimpleNamespace | None:
            for artifact in snapshot.recent_artifacts:
                if artifact.key == artifact_key:
                    return artifact
            return None

        def artifact_preview_lines(self, artifact: SimpleNamespace) -> tuple[str, ...]:
            return (f"Файл: {artifact.path.name}", "Размер: 3 байт")

        def animation_scene_preview_points(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> dict[str, object]:
            return {
                "status": "READY",
                "source_path": str(npz_path),
                "pointer_path": str(pointer_path),
                "series_x": "time_s",
                "series_y": "z_body_mm",
                "points": ((0.0, 0.0), (1.0, 4.0), (2.0, 2.0)),
                "point_count": 3,
                "range": "x 0 .. 2; y 0 .. 4",
            }

    settings_path = tmp_path / "desktop_spec_shell_animation_preview_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))

    app = _app()
    window = DesktopGuiSpecMainWindow()
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)
    try:
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, AnimationWorkspacePage)

        window.run_command("animation.animator.open")
        app.processEvents()

        preview_values = {
            page.animation_scene_preview_table.item(row, 1).text()
            for row in range(page.animation_scene_preview_table.rowCount())
            if page.animation_scene_preview_table.item(row, 1) is not None
        }
        assert "scene_result.npz" in preview_values
        assert "scene_result.json" in preview_values
        assert "scene_result.desktop_mnemo_events.json" in preview_values
        assert "готово" in preview_values
        assert "scene_result.capture_manifest.json" in preview_values
        assert "Файл: scene_result.npz" in preview_values
        assert "Размер: 3 байт" in preview_values
        assert page.animation_scene_preview_view.objectName() == "AM-SCENE-NATIVE-PREVIEW"
        assert page.animation_scene_preview_view.scene().items()
        assert "scene_result.npz" in page.animation_scene_preview_view.toolTip()
        assert "x 0 .. 2" in page.animation_scene_preview_view.toolTip()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_animation_workspace_page_uses_analysis_handoff_artifact(tmp_path, monkeypatch) -> None:
    latest_path = tmp_path / "latest_result.npz"
    selected_path = tmp_path / "selected_result.npz"
    pointer_path = tmp_path / "selected_result.json"
    latest_path.write_bytes(b"NPZ")
    selected_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")

    class _FakeResultsRuntime:
        launched_args: list[list[str]] = []
        diagnostics_handoff_paths: list[Path | None] = []

        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable

        def snapshot(self) -> SimpleNamespace:
            artifacts = (
                SimpleNamespace(key="latest_npz", path=latest_path),
                SimpleNamespace(key="latest_pointer", path=pointer_path),
            )
            return SimpleNamespace(
                latest_npz_path=latest_path,
                latest_pointer_json_path=None,
                latest_mnemo_event_log_path=None,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="нет данных",
                mnemo_recent_titles=(),
                operator_recommendations=("Проверьте движение.",),
                recent_artifacts=artifacts,
            )

        def animation_handoff_artifact(self, snapshot: SimpleNamespace) -> SimpleNamespace:
            return SimpleNamespace(
                key="selected_npz",
                title="Выбранный файл результата",
                category="results",
                path=selected_path,
                detail="",
            )

        def animator_target_paths(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> tuple[Path | None, Path | None]:
            if artifact is not None:
                return artifact.path, pointer_path
            return snapshot.latest_npz_path, snapshot.latest_pointer_json_path

        def artifact_by_key(self, snapshot: SimpleNamespace, artifact_key: str) -> SimpleNamespace | None:
            for artifact in snapshot.recent_artifacts:
                if artifact.key == artifact_key:
                    return artifact
            return None

        def artifact_preview_lines(self, artifact: SimpleNamespace) -> tuple[str, ...]:
            return (f"Файл результата: {artifact.path.name}",)

        def animation_scene_preview_points(
            self,
            snapshot: SimpleNamespace,
            artifact: SimpleNamespace | None = None,
        ) -> dict[str, object]:
            target = artifact.path if artifact is not None else latest_path
            return {
                "status": "READY",
                "source_path": str(target),
                "pointer_path": str(pointer_path),
                "series_x": "time_s",
                "series_y": target.stem,
                "points": ((0.0, 1.0), (1.0, 2.0), (2.0, 1.5)),
                "point_count": 3,
                "range": f"{target.name}: 1 .. 2",
            }

        def animator_args(self, snapshot: SimpleNamespace, *, follow: bool, artifact=None) -> list[str]:
            npz_path, pointer = self.animator_target_paths(snapshot, artifact=artifact)
            assert npz_path == selected_path
            return ["--pointer", str(pointer)]

        def launch_animator(self, snapshot: SimpleNamespace, *, follow: bool, artifact=None) -> SimpleNamespace:
            self.__class__.launched_args.append(
                self.animator_args(snapshot, follow=follow, artifact=artifact)
            )
            return SimpleNamespace(pid=777)

        def write_animation_diagnostics_handoff(
            self,
            snapshot: SimpleNamespace,
            artifact=None,
        ) -> Path:
            self.__class__.diagnostics_handoff_paths.append(
                artifact.path if artifact is not None else None
            )
            path = tmp_path / "latest_animation_diagnostics_handoff.json"
            path.write_text("{}", encoding="utf-8")
            return path

    settings_path = tmp_path / "desktop_spec_shell_animation_handoff_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    app = _app()
    window = DesktopGuiSpecMainWindow()
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)
    try:
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, AnimationWorkspacePage)

        window.run_command("animation.animator.open")
        app.processEvents()

        preview_values = {
            page.animation_scene_preview_table.item(row, 1).text()
            for row in range(page.animation_scene_preview_table.rowCount())
            if page.animation_scene_preview_table.item(row, 1) is not None
        }
        assert "передано из анализа" in preview_values
        assert "selected_result.npz" in preview_values
        assert "latest_result.npz" not in preview_values
        assert "selected_result.npz" in page.animation_scene_preview_view.toolTip()
        assert "latest_result.npz" not in page.animation_scene_preview_view.toolTip()

        window.run_command("animation.animator.launch")
        app.processEvents()
        assert _FakeResultsRuntime.launched_args == [["--pointer", str(pointer_path)]]

        window.run_command("animation.diagnostics.prepare")
        app.processEvents()
        assert _FakeResultsRuntime.diagnostics_handoff_paths == [selected_path]
        assert "Материал передан в проверку проекта" in page.animation_action_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_animation_workspace_page_launches_animator_through_hosted_surface(tmp_path, monkeypatch) -> None:
    npz_path = tmp_path / "anim_result.npz"
    pointer_path = tmp_path / "anim_result.json"
    npz_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")

    class _FakeResultsRuntime:
        launched_args: list[list[str]] = []

        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable

        def snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(
                latest_npz_path=npz_path,
                latest_pointer_json_path=pointer_path,
                latest_mnemo_event_log_path=None,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="нет данных",
                mnemo_recent_titles=(),
                operator_recommendations=("Проверьте движение.",),
            )

        def animator_args(self, snapshot: SimpleNamespace, *, follow: bool, artifact=None) -> list[str]:
            assert follow is True
            return ["--pointer", str(snapshot.latest_pointer_json_path)]

        def launch_animator(self, snapshot: SimpleNamespace, *, follow: bool, artifact=None) -> SimpleNamespace:
            self.__class__.launched_args.append(
                self.animator_args(snapshot, follow=follow, artifact=artifact)
            )
            return SimpleNamespace(pid=654)

    settings_path = tmp_path / "desktop_spec_shell_animation_launch_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    app = _app()
    window = DesktopGuiSpecMainWindow()
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)
    try:
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, AnimationWorkspacePage)

        window.run_command("animation.animator.launch")
        app.processEvents()

        assert _FakeResultsRuntime.launched_args == [["--pointer", str(pointer_path)]]
        assert "Аниматор открывается" in page.animation_action_label.text()
        assert "animation.animator.launch" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_animation_workspace_page_launches_mnemo_through_hosted_surface(tmp_path, monkeypatch) -> None:
    npz_path = tmp_path / "mnemo_result.npz"
    pointer_path = tmp_path / "mnemo_result.json"
    event_log_path = tmp_path / "mnemo_result.desktop_mnemo_events.json"
    npz_path.write_bytes(b"NPZ")
    pointer_path.write_text("{}", encoding="utf-8")
    event_log_path.write_text("{}", encoding="utf-8")

    class _FakeResultsRuntime:
        launched_args: list[list[str]] = []

        def __init__(self, *, repo_root: Path, python_executable: str) -> None:
            self.repo_root = Path(repo_root)
            self.python_executable = python_executable

        def snapshot(self) -> SimpleNamespace:
            return SimpleNamespace(
                latest_npz_path=npz_path,
                latest_pointer_json_path=pointer_path,
                latest_mnemo_event_log_path=event_log_path,
                latest_capture_export_manifest_status="READY",
                mnemo_current_mode="overview",
                mnemo_recent_titles=("Давление проверено",),
                operator_recommendations=("Проверьте схему.",),
            )

        def mnemo_args(self, snapshot: SimpleNamespace, *, follow: bool, artifact=None) -> list[str]:
            assert follow is True
            return ["--follow", "--pointer", str(snapshot.latest_pointer_json_path)]

        def launch_mnemo(self, snapshot: SimpleNamespace, *, follow: bool, artifact=None) -> SimpleNamespace:
            self.__class__.launched_args.append(
                self.mnemo_args(snapshot, follow=follow, artifact=artifact)
            )
            return SimpleNamespace(pid=655)

    settings_path = tmp_path / "desktop_spec_shell_mnemo_launch_state.ini"
    monkeypatch.setenv("PNEUMO_GUI_SPEC_SHELL_STATE_PATH", str(settings_path))
    app = _app()
    window = DesktopGuiSpecMainWindow()
    monkeypatch.setattr(workspace_pages_module, "DesktopResultsRuntime", _FakeResultsRuntime)
    try:
        page = window._page_widget_by_workspace_id["animation"]
        assert isinstance(page, AnimationWorkspacePage)

        window.run_command("animation.mnemo.launch")
        app.processEvents()

        assert _FakeResultsRuntime.launched_args == [["--follow", "--pointer", str(pointer_path)]]
        assert "Мнемосхема запускается" in page.animation_action_label.text()
        assert "animation.mnemo.launch" in window.recent_command_ids
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_hosted_baseline_workspace_page_prepares_native_launch_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    _write_launch_ready_baseline_handoffs(workspace_dir)

    page = BaselineWorkspacePage(
        build_workspace_map()["baseline_run"],
        (),
        lambda _command_id: None,
        repo_root=ROOT,
        python_executable="python-test",
    )
    try:
        app.processEvents()
        page.handle_command("baseline.run_setup.prepare")
        app.processEvents()

        request_path = baseline_run_launch_request_path(repo_root=ROOT, workspace_dir=workspace_dir)
        request = json.loads(request_path.read_text(encoding="utf-8"))

        assert request["execution_ready"] is True
        assert request["command"][:3] == ["python-test", "-m", DESKTOP_SINGLE_RUN_MODULE]
        assert Path(request["paths"]["prepared_inputs"]).exists()
        assert Path(request["paths"]["prepared_suite"]).exists()
        assert "Команда запуска подготовлена" in page.run_setup_result_label.text()
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_baseline_workspace_page_runs_native_request_in_background(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    _write_launch_ready_baseline_handoffs(workspace_dir)
    shell_statuses: list[tuple[str, bool]] = []
    opened_paths: list[str] = []

    def fake_open_url(url) -> bool:
        opened_paths.append(url.toLocalFile())
        return True

    def fake_prepare(run_setup, *, repo_root=None, workspace_dir=None, python_executable=None, checked=False):
        request = prepare_baseline_run_launch_request(
            run_setup,
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            python_executable=python_executable,
            checked=checked,
        )
        run_dir = Path(str(request["paths"]["run_dir"]))
        script = (
            "import json, pathlib\n"
            f"run_dir = pathlib.Path({str(run_dir)!r})\n"
            "run_dir.mkdir(parents=True, exist_ok=True)\n"
            "summary = {'ok': True, 'scenario_name': 'baseline_ui_launch', "
            "'run_profile': 'detail', 'cache_key': 'fake-cache-key', 'dt_s': 0.003, 't_end_s': 1.6}\n"
            "(run_dir / 'run_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')\n"
            "print('baseline fake done')\n"
        )
        request["command"] = [sys.executable, "-c", script]
        Path(str(request["paths"]["request"])).write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        return request

    monkeypatch.setattr(workspace_pages_module, "prepare_baseline_run_launch_request", fake_prepare)
    monkeypatch.setattr(workspace_pages_module.QtGui.QDesktopServices, "openUrl", fake_open_url)

    page = BaselineWorkspacePage(
        build_workspace_map()["baseline_run"],
        (),
        lambda _command_id: None,
        repo_root=ROOT,
        python_executable=sys.executable,
        on_shell_status=lambda text, busy: shell_statuses.append((text, bool(busy))),
    )
    try:
        app.processEvents()
        page.handle_command("baseline.run.execute")
        app.processEvents()

        process = page._baseline_process
        assert process is not None
        assert process.waitForFinished(10000)
        app.processEvents()

        request_path = baseline_run_launch_request_path(repo_root=ROOT, workspace_dir=workspace_dir)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        history = read_baseline_history(workspace_dir=workspace_dir)

        assert request["execution_status"] == "done"
        assert request["returncode"] == 0
        assert Path(request["run_summary_path"]).exists()
        assert request["baseline_candidate"]["requires_explicit_adopt"] is True
        assert history
        assert history[-1]["action"] == "review"
        assert "Базовый прогон завершён" in page.run_setup_result_label.text()
        assert shell_statuses[-1] == ("Базовый прогон завершён.", False)
        assert page.run_setup_open_log_button.isEnabled()
        assert page.run_setup_open_result_button.isEnabled()

        page.handle_command("baseline.run.open_log")
        page.handle_command("baseline.run.open_result")

        assert Path(opened_paths[0]) == Path(request["paths"]["log"])
        assert Path(opened_paths[1]) == Path(request["paths"]["run_dir"])
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_hosted_baseline_workspace_page_cancels_background_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))
    _write_launch_ready_baseline_handoffs(workspace_dir)
    shell_statuses: list[tuple[str, bool]] = []

    def fake_prepare(run_setup, *, repo_root=None, workspace_dir=None, python_executable=None, checked=False):
        request = prepare_baseline_run_launch_request(
            run_setup,
            repo_root=repo_root,
            workspace_dir=workspace_dir,
            python_executable=python_executable,
            checked=checked,
        )
        script = "import time\nprint('baseline fake long run', flush=True)\ntime.sleep(30)\n"
        request["command"] = [sys.executable, "-c", script]
        Path(str(request["paths"]["request"])).write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        return request

    monkeypatch.setattr(workspace_pages_module, "prepare_baseline_run_launch_request", fake_prepare)

    page = BaselineWorkspacePage(
        build_workspace_map()["baseline_run"],
        (),
        lambda _command_id: None,
        repo_root=ROOT,
        python_executable=sys.executable,
        on_shell_status=lambda text, busy: shell_statuses.append((text, bool(busy))),
    )
    try:
        app.processEvents()
        page.handle_command("baseline.run.execute")
        app.processEvents()

        process = page._baseline_process
        assert process is not None
        assert page.run_setup_cancel_button.isEnabled()

        page.handle_command("baseline.run.cancel")
        assert process.waitForFinished(10000)
        app.processEvents()

        request_path = baseline_run_launch_request_path(repo_root=ROOT, workspace_dir=workspace_dir)
        request = json.loads(request_path.read_text(encoding="utf-8"))

        assert request["execution_status"] == "failed"
        assert "Запуск отменён оператором" in request["stderr_tail"]
        assert "отменён" in page.run_setup_result_label.text()
        assert shell_statuses[-1] == ("Базовый прогон отменён.", False)
    finally:
        page.close()
        page.deleteLater()
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
        assert page.run_setup_execute_button.text() == "Запустить в фоне"
        assert page.run_setup_cancel_button.text() == "Отменить запуск"
        assert page.run_setup_open_log_button.text() == "Открыть журнал"
        assert page.run_setup_open_result_button.text() == "Открыть папку результата"
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
        assert page.baseline_review_detail_box.objectName() == "BL-REVIEW-DETAILS"
        assert page.baseline_review_detail_box.title() == "Карточка проверки выбранного результата"
        assert page.baseline_review_detail_table.objectName() == "BL-REVIEW-DETAILS-TABLE"
        assert page.baseline_review_detail_table.horizontalHeaderItem(0).text() == "Проверка"
        assert page.baseline_review_detail_table.horizontalHeaderItem(1).text() == "Значение"
        assert page.baseline_review_detail_table.horizontalHeaderItem(2).text() == "Следующий шаг"
        assert page.baseline_review_detail_table.rowCount() >= 10
        matrix_status = {
            page.baseline_mismatch_matrix.item(row, 0).text(): page.baseline_mismatch_matrix.item(row, 3).text()
            for row in range(page.baseline_mismatch_matrix.rowCount())
        }
        assert matrix_status["Опорный прогон"] == "расходится"
        assert matrix_status["Снимок набора"] == "совпадает"
        assert matrix_status["Исходные данные"] == "совпадает"
        assert matrix_status["Циклический сценарий"] == "совпадает"
        assert matrix_status["Режим"] == "совпадает"
        review_details = {
            page.baseline_review_detail_table.item(row, 0).text(): (
                page.baseline_review_detail_table.item(row, 1).text(),
                page.baseline_review_detail_table.item(row, 2).text(),
            )
            for row in range(page.baseline_review_detail_table.rowCount())
        }
        assert review_details["Файл результата"][0].endswith("baseline_candidate.json")
        assert review_details["Папка запуска"][0].endswith("candidate")
        assert review_details["Доступность оптимизации"][0] == "готов"
        assert "явное подтверждение" in review_details["Следующий безопасный шаг"][0]

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
        review_details = {
            page.baseline_review_detail_table.item(row, 0).text(): (
                page.baseline_review_detail_table.item(row, 1).text(),
                page.baseline_review_detail_table.item(row, 2).text(),
            )
            for row in range(page.baseline_review_detail_table.rowCount())
        }
        assert review_details["Файл результата"][0].endswith("baseline_historical.json")
        assert review_details["Состояние сверки"][0] == "другой набор данных"
        assert "расхождения" in review_details["Следующий безопасный шаг"][0]
        assert "Снимок набора" in review_details["Состояние сверки"][1]

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
