from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pneumo_solver_ui.desktop_qt_shell import main_window as qt_main_window_module
from pneumo_solver_ui.desktop_qt_shell.coexistence import _default_context_payload
from pneumo_solver_ui.desktop_qt_shell.project_context import (
    ShellProjectContext,
    build_shell_project_context,
)
from pneumo_solver_ui.desktop_qt_shell.pipeline_surfaces import (
    OPERATOR_FORBIDDEN_LABELS,
    V38_PIPELINE_SURFACES,
    V38_PIPELINE_WORKSPACE_IDS,
)
from pneumo_solver_ui.desktop_qt_shell.runtime_proof import (
    QT_MAIN_SHELL_MANUAL_CHECKLIST_JSON_NAME,
    QT_MAIN_SHELL_MANUAL_RESULTS_TEMPLATE_JSON_NAME,
    QT_MAIN_SHELL_RUNTIME_PROOF_JSON_NAME,
    build_v38_pipeline_dot_alignment,
    validate_qt_main_shell_manual_results,
    validate_qt_main_shell_runtime_proof,
    write_qt_main_shell_manual_results_template,
    write_qt_main_shell_runtime_proof,
)
from pneumo_solver_ui.desktop_animator.analysis_context import ANALYSIS_TO_ANIMATOR_HANDOFF_ID
from pneumo_solver_ui.desktop_animator.truth_contract import file_sha256, stable_contract_hash
from pneumo_solver_ui.desktop_shell.command_search import (
    build_shell_command_search_entries,
    rank_shell_command_search_entries,
)
from pneumo_solver_ui.desktop_shell.external_launch import build_shell_context_env
from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.tools import desktop_main_shell_qt as desktop_main_shell_qt_module


ROOT = Path(__file__).resolve().parents[1]


def test_v38_pipeline_search_aliases_are_operator_language_not_service_jargon() -> None:
    visible_alias_text = "\n".join(
        alias
        for surface in V38_PIPELINE_SURFACES
        for alias in surface.search_aliases
    )

    for forbidden in (
        "project dashboard",
        "next action",
        "machine inputs",
        "geometry",
        "baseline",
        "active baseline",
        "optimization",
        "analysis",
        "results",
        "compare",
        "validation",
        "animator",
        "viewcube",
        "diagnostics",
        "send bundle",
        "self-check",
    ):
        assert forbidden not in visible_alias_text


def _qt_modules():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


def _qt_app():
    _QtCore, _QtGui, QtWidgets = _qt_modules()
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _test_project_context(tmp_path: Path) -> ShellProjectContext:
    repo_root = tmp_path / "repo"
    workspace_dir = tmp_path / "workspace"
    state_root = workspace_dir / "ui_state"
    project_dir = state_root / "projects" / "Runtime Shell"
    for dirname in ("exports", "uploads", "road_profiles", "maneuvers", "opt_runs", "ui_state"):
        (workspace_dir / dirname).mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    repo_root.mkdir(parents=True, exist_ok=True)
    return ShellProjectContext(
        repo_root=repo_root.resolve(),
        workspace_dir=workspace_dir.resolve(),
        state_root=state_root.resolve(),
        project_name="Runtime Shell",
        project_dir=project_dir.resolve(),
        workspace_source="PNEUMO_WORKSPACE_DIR",
        missing_workspace_dirs=(),
    )


def _write_qt_shell_analysis_context(workspace_dir: Path) -> tuple[Path, Path, Path, Path]:
    context_path = workspace_dir / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"
    link_path = context_path.with_name("animator_link_contract.json")
    npz_path = workspace_dir / "exports" / "anim_latest.npz"
    pointer_path = workspace_dir / "exports" / "anim_latest.json"
    capture_manifest_path = workspace_dir / "exports" / "capture_export_manifest.json"
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    npz_path.write_bytes(b"npz-demo")
    capture_manifest_path.write_text(
        json.dumps(
            {
                "schema": "capture_export_manifest.v1",
                "handoff_id": "HO-010",
                "capture_hash": "capture-shell-010",
                "analysis_context_hash": "analysis-context-shell",
                "analysis_context_refs": {
                    "analysis_context_status": "READY",
                    "selected_test_id": "T01",
                    "selected_npz_path": str(npz_path),
                },
                "truth_summary": {"overall_truth_state": "READY"},
                "blocking_states": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pointer_path.write_text(
        json.dumps(
            {
                "npz_path": str(npz_path),
                "meta": {
                    "anim_export_contract_artifacts": {
                        "capture_export_manifest": capture_manifest_path.name,
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pointer = {
        "path": str(pointer_path),
        "exists": True,
        "kind": "json",
        "sha256": file_sha256(pointer_path),
        "size_bytes": pointer_path.stat().st_size,
    }
    link = {
        "schema": "analysis_to_animator_link_contract.v1",
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "producer_workspace": "WS-ANALYSIS",
        "consumer_workspace": "WS-ANIMATOR",
        "analysis_context_path": str(context_path),
        "run_id": "run-shell-001",
        "run_contract_hash": "selected-run-shell-hash",
        "selected_test_id": "T01",
        "selected_segment_id": "segment-1",
        "selected_time_window": {"mode": "time_s", "start_s": 0.0, "end_s": 1.0},
        "selected_best_candidate_ref": "candidate-001",
        "selected_result_artifact_pointer": pointer,
        "objective_contract_hash": "objective-shell",
        "suite_snapshot_hash": "suite-shell",
        "problem_hash": "problem-shell",
    }
    link["animator_link_contract_hash"] = stable_contract_hash(
        {key: value for key, value in link.items() if key != "animator_link_contract_hash"}
    )
    context = {
        "schema": "analysis_context.v1",
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "producer_workspace": "WS-ANALYSIS",
        "consumer_workspace": "WS-ANIMATOR",
        "analysis_context_path": str(context_path),
        "selected_run_contract_path": str(workspace_dir / "handoffs" / "WS-OPTIMIZATION" / "selected_run_contract.json"),
        "selected_run_contract_hash": "selected-run-shell-hash",
        "selected_run_context": {
            "run_id": "run-shell-001",
            "objective_contract_hash": "objective-shell",
            "suite_snapshot_hash": "suite-shell",
            "problem_hash": "problem-shell",
            "run_contract_hash": "selected-run-shell-hash",
        },
        "selected_result_artifact_pointer": pointer,
        "animator_link_contract_path": str(link_path),
        "animator_link_contract_hash": link["animator_link_contract_hash"],
        "animator_link_contract": link,
        "diagnostics_bundle_finalized": False,
    }
    context["analysis_context_hash"] = stable_contract_hash(
        {key: value for key, value in context.items() if key != "analysis_context_hash"}
    )
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    link_path.write_text(json.dumps(link, ensure_ascii=False, indent=2), encoding="utf-8")
    return context_path, link_path, pointer_path, capture_manifest_path


class _FakeCoexistenceManager:
    instances: list["_FakeCoexistenceManager"] = []

    def __init__(self) -> None:
        self.opened: list[SimpleNamespace] = []
        _FakeCoexistenceManager.instances.append(self)

    def open_tool(self, spec, *, context_payload=None):
        session = SimpleNamespace(
            spec=spec,
            pid=4321,
            runtime_label="Проверочное окно",
            context_payload=dict(context_payload or {}),
            status_label=lambda: "Открыто",
        )
        self.opened.append(session)
        return session

    def stop_tool(self, key: str) -> bool:
        return any(session.spec.key == key for session in self.opened)

    def all_sessions(self) -> tuple[SimpleNamespace, ...]:
        return tuple(self.opened)

    def poll(self) -> tuple[SimpleNamespace, ...]:
        return ()


def test_desktop_qt_shell_launcher_exposes_qt_first_cli_and_legacy_fallback() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_main_shell_qt.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "def build_arg_parser() -> argparse.ArgumentParser:" in src
    assert '"--open"' in src
    assert '"--list-tools"' in src
    assert '"--legacy-tk-shell"' in src
    assert '"--runtime-proof"' in src
    assert '"--runtime-proof-offscreen"' in src
    assert '"--runtime-proof-manual-results"' in src
    assert '"--runtime-proof-manual-template"' in src
    assert '"--runtime-proof-validate"' in src
    assert '"--runtime-proof-require-manual-pass"' in src
    assert "Рабочие окна приложения:" in src
    assert "from pneumo_solver_ui.tools import desktop_main_shell as legacy_shell" in src
    assert "from pneumo_solver_ui.desktop_qt_shell.main_window import main as run_qt_shell_main" in src
    assert "запускаю запасной оконный режим" in src
    assert "запускаю резервное Tk-окно" not in src


def test_desktop_qt_shell_launcher_catalog_keeps_runtime_and_migration_metadata() -> None:
    catalog = build_desktop_launch_catalog(include_mnemo=True)
    by_key = {item.key: item for item in catalog}

    assert catalog[0].key == "desktop_main_shell_qt"
    assert by_key["desktop_main_shell_qt"].module == "pneumo_solver_ui.tools.desktop_main_shell_qt"
    assert by_key["desktop_main_shell_qt"].group == "Рабочее место"
    assert by_key["desktop_gui_spec_shell"].group == "Восстановление окон"
    assert by_key["desktop_gui_spec_shell"].module == "pneumo_solver_ui.tools.desktop_gui_spec_shell"

    assert by_key["desktop_input_editor"].runtime_kind == "tk"
    assert by_key["desktop_input_editor"].migration_status == "managed_external"
    assert by_key["desktop_input_editor"].source_of_truth_role == "master"
    assert by_key["desktop_run_setup_center"].module == "pneumo_solver_ui.tools.desktop_run_setup_center"
    assert by_key["desktop_run_setup_center"].runtime_kind == "tk"
    assert by_key["desktop_run_setup_center"].source_of_truth_role == "master"

    assert by_key["desktop_animator"].runtime_kind == "qt"
    assert by_key["desktop_animator"].migration_status == "native"
    assert by_key["desktop_animator"].source_of_truth_role == "derived"
    assert "HO-008" in by_key["desktop_animator"].search_aliases
    assert "analysis_context_path" in by_key["desktop_animator"].context_handoff_keys
    assert "selected_npz_path" in by_key["desktop_animator"].context_handoff_keys
    assert by_key["desktop_engineering_analysis_center"].module == (
        "pneumo_solver_ui.tools.desktop_engineering_analysis_center"
    )
    assert by_key["desktop_engineering_analysis_center"].runtime_kind == "tk"
    assert by_key["desktop_engineering_analysis_center"].source_of_truth_role == "derived"
    assert "selected_run_contract" not in by_key["desktop_engineering_analysis_center"].search_aliases
    assert "контракт выбранного прогона" not in by_key[
        "desktop_engineering_analysis_center"
    ].search_aliases
    assert "выбранный прогон" in by_key["desktop_engineering_analysis_center"].search_aliases
    assert "selected_run_contract_path" in by_key[
        "desktop_engineering_analysis_center"
    ].context_handoff_keys

    assert "исходные данные" in by_key["desktop_input_editor"].search_aliases
    assert "распределённый расчёт" in by_key["desktop_optimizer_center"].search_aliases


def test_desktop_qt_shell_spec_contract_marks_tk_workspaces_as_managed_external() -> None:
    specs = build_desktop_shell_specs()
    by_key = {spec.key: spec for spec in specs}

    assert by_key["desktop_input_editor"].effective_runtime_kind == "tk"
    assert by_key["desktop_input_editor"].effective_migration_status == "managed_external"
    assert by_key["desktop_run_setup_center"].workflow_stage == "calculation"
    assert by_key["desktop_run_setup_center"].effective_source_of_truth_role == "master"
    assert by_key["desktop_ring_editor"].effective_source_of_truth_role == "master"
    assert by_key["desktop_results_center"].effective_source_of_truth_role == "derived"
    assert by_key["desktop_engineering_analysis_center"].workflow_stage == "analysis"
    assert by_key["desktop_engineering_analysis_center"].entry_kind == "contextual"
    assert by_key["desktop_engineering_analysis_center"].effective_source_of_truth_role == "derived"
    assert by_key["desktop_engineering_analysis_center"].standalone_module == (
        "pneumo_solver_ui.tools.desktop_engineering_analysis_center"
    )
    assert "animator_link_contract_hash" in by_key[
        "desktop_animator"
    ].effective_context_handoff_keys
    assert by_key["desktop_diagnostics_center"].effective_source_of_truth_role == "support"
    assert "selected_tool_key" in by_key["desktop_optimizer_center"].effective_context_handoff_keys
    assert "active_optimization_mode" in by_key["desktop_optimizer_center"].effective_context_handoff_keys
    assert "project_name" in by_key["desktop_optimizer_center"].effective_context_handoff_keys
    assert "workspace_dir" in by_key["desktop_optimizer_center"].effective_context_handoff_keys
    assert "selected_run_contract_hash" in by_key[
        "desktop_engineering_analysis_center"
    ].effective_context_handoff_keys


def test_desktop_qt_shell_main_window_uses_qmainwindow_docks_and_search_surface() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_qt_shell" / "main_window.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopQtMainShell(QtWidgets.QMainWindow):" in src
    assert "def _apply_cyrillic_operator_font(" in src
    assert "QtGui.QFontDatabase.addApplicationFont" in src
    assert '"segoeui.ttf"' in src
    assert 'self.setObjectName("DesktopQtMainShell")' in src
    assert "PRIMARY_START_ACTIONS = (" in src
    assert "VISUAL_TRUTH_ROWS = (" in src
    assert 'QtWidgets.QToolBar("Быстрые действия", self)' in src
    assert 'menubar.addMenu("Файл")' in src
    assert 'menubar.addMenu("Правка")' in src
    assert 'menubar.addMenu("Вид")' in src
    assert 'menubar.addMenu("Запуск")' in src
    assert 'menubar.addMenu("Анализ")' in src
    assert 'menubar.addMenu("Анимация")' in src
    assert 'menubar.addMenu("Проверка")' in src
    assert 'menubar.addMenu("Инструменты")' in src
    assert 'menubar.addMenu("Справка")' in src
    assert 'run_menu.addMenu("Окна по задаче")' in src
    assert 'run_menu.addMenu("Все окна")' not in src
    assert '("Справочники и проверки", support_specs)' in src
    assert '("Детальная проверка результата", result_detail_specs)' in src
    assert 'analysis_menu.addMenu("Детальная проверка результата")' in src
    assert 'animation_menu.addMenu("Дополнительная визуализация")' in src
    assert 'panels_menu = view_menu.addMenu("Панели")' in src
    assert 'show_all_panels_action = panels_menu.addAction("Вернуть все панели")' in src
    assert "def _show_all_docks(self) -> None:" in src
    assert 'self.workspace_combo = QtWidgets.QComboBox(toolbar)' in src
    assert 'self.launch_tool_combo = QtWidgets.QComboBox(toolbar)' in src
    assert "self.launch_tool_combo.activated.connect(self._on_launch_tool_activated)" in src
    assert "def _on_launch_tool_activated(self, index: int) -> None:" in src
    assert 'QtWidgets.QPushButton("Открыть окно", toolbar)' not in src
    assert "DesktopQtShellOpenLaunchTool" not in src
    assert 'self.command_search_edit = QtWidgets.QLineEdit(toolbar)' in src
    assert 'self.optimization_mode_combo = QtWidgets.QComboBox(toolbar)' in src
    assert 'self.browser_dock = QtWidgets.QDockWidget("Панель проекта", self)' in src
    assert 'self.inspector_dock = QtWidgets.QDockWidget("Свойства и помощь", self)' in src
    assert 'self.runtime_dock = QtWidgets.QDockWidget("Ход выполнения и внешние окна", self)' in src
    assert "def _dock_features(self) -> QtWidgets.QDockWidget.DockWidgetFeature:" in src
    assert "setAllowedAreas(" in src
    assert "resizeDocks((self.browser_dock, self.inspector_dock)" in src
    assert 'self.runtime_table.setHeaderLabels(("Окно", "Состояние", "Тип"))' in src
    assert 'self.diagnostics_button.setObjectName("AlwaysVisibleDiagnosticsAction")' in src
    assert 'self.diagnostics_button.setShortcut(QtGui.QKeySequence("F7"))' in src
    assert 'self.diagnostics_button.setToolTip("F7. Проверить проект и сохранить архив проекта.")' in src
    assert "Открыть диагностику и собрать" not in src
    assert "self.central_stack = QtWidgets.QStackedWidget(central)" in src
    assert 'self.banner_label = QtWidgets.QLabel(' in src
    assert 'self.route_label = QtWidgets.QLabel(' in src
    assert 'self.project_summary_label = QtWidgets.QLabel(self._project_summary_text(), central)' in src
    assert "self.overview_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self.overview_page)" in src
    assert 'self.overview_splitter.setObjectName("DesktopQtShellOverviewSplitter")' in src
    assert "self.overview_splitter.setChildrenCollapsible(False)" in src
    assert "self.overview_splitter.setSizes((920, 560))" in src
    assert 'QtWidgets.QGroupBox("Основной порядок работы", left_overview_panel)' in src
    assert 'QtWidgets.QGroupBox("Рабочие шаги", left_overview_panel)' in src
    assert "V10_ROUTE_SURFACE_KEYS = (" in src
    assert '"1. Исходные данные"' in src
    assert '"2. Сценарии"' in src
    assert '"3. Набор испытаний"' in src
    assert '"4. Базовый прогон"' in src
    assert '"5. Оптимизация"' in src
    assert '"6. Анализ"' in src
    assert '"7. Анимация"' in src
    assert '"8. Проверка проекта"' in src
    assert '"Проверить проект"' in src
    assert "self.start_action_buttons" in src
    assert 'self.start_action_buttons.setdefault(tool_key, button)' in src
    assert 'QtWidgets.QGroupBox("Достоверность отображения", right_overview_panel)' in src
    assert '"Результаты"' in src
    assert '"Графики"' in src
    assert '"Анимация"' in src
    assert '"Пневмосхема"' in src
    assert '"Крупные состояния: расчётно подтверждено, по исходным данным, условно, недоступно."' in src
    assert "self.visual_truth_labels" in src
    assert 'self.message_strip_label.setObjectName("ShellMessagesStrip")' in src
    assert 'self.status_progress_bar.setObjectName("ShellStatusProgress")' in src
    animator_src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    assert 'setObjectName("AnalysisContextBanner")' in animator_src
    assert "def set_analysis_context_snapshot" in animator_src
    assert "format_analysis_context_banner" in animator_src
    assert 'QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K")' in src
    assert 'QtGui.QShortcut(QtGui.QKeySequence("F6")' in src
    assert 'QtGui.QShortcut(QtGui.QKeySequence("Shift+F6")' in src
    assert 'self.message_strip_label,' in src
    assert "DesktopShellCoexistenceManager()" in src
    assert "QSettings" in src
    assert "build_shell_project_context()" in src
    assert "def launch_surface_coverage(self) -> dict[str, tuple[str, ...]]:" in src
    assert "def pipeline_surface_coverage(self) -> dict[str, tuple[str, ...]]:" in src
    assert "def operator_visible_audit(self) -> dict[str, object]:" in src
    assert '"item_visible_texts": item_visible_texts' in src
    assert "def operator_surface_snapshot(self) -> dict[str, object]:" in src
    assert "def prove_v38_pipeline_selection_sync(self) -> dict[str, object]:" in src
    assert '"desktop_engineering_analysis_center"' in src
    assert "def _reset_layout(self) -> None:" in src
    assert 'self.settings.setValue("layout/geometry", geometry)' in src
    assert 'self.settings.setValue("layout/window_state", state)' in src
    assert 'self.settings.setValue("layout/last_workspace_key", self._selected_tool_key)' in src
    assert 'self.settings.setValue("layout/last_surface_key", self._selected_surface_key)' in src
    assert '"project_name": self.project_context.project_name' in src
    assert '"workspace_dir": str(self.project_context.workspace_dir)' in src
    assert "_project_display_name(self.project_context.project_name)" in src
    assert 'f"Проект: {self.project_context.project_name}"' not in src
    assert '"Порядок работы"' in src
    assert 'action_kind == "focus" and action_value == "project_tree"' in src
    assert '"Запустить раздел"' not in src
    assert '"Запустить текущий раздел"' not in src
    assert '"Workspace:"' not in src
    assert '"required dirs"' not in src
    assert "ContractBadge" not in src
    assert "contract_badge" not in src
    assert "_refresh_contract_badge" not in src
    assert 'self.compare_button = QtWidgets.QPushButton("Открыть сравнение"' not in src
    assert "Служебный центр" not in src
    assert 'return "Инструмент проекта"' in src
    assert 'setObjectName("CalculationStatusBadge")' in src
    assert "def _refresh_calculation_status_badge(self) -> None:" in src
    assert '"Окна, действия, испытания, сценарии, архив проекта, расчёты, файлы"' in src
    assert '"Начните вводить действие, окно, расчёт, архив проекта или файл."' in src
    forbidden_qt_visible_fragments = [
        "Команды, экраны, тесты, сценарии, bundle, runs, artifacts",
        "run, bundle или artifact",
        "SEND bundle",
        "Рабочие артефакты",
        "артефактам и маршрутам",
        "Артефакт не найден",
        "Артефакт отсутствует",
        "Открыт артефакт",
        "Не удалось открыть артефакт",
        "frozen HO-008 context",
        "HO-008 analysis_context.json",
        "HO-008 animator_link_contract.json",
        "selected result artifact pointer",
        "selected animation NPZ",
        "NPZ-файл",
        "Файл анимации NPZ",
        "HO-010 capture_export_manifest.json",
        "HO-008 context",
        "road_csv, axay_csv",
        "scenario_json — производные артефакты",
        '"Процесс"',
        "session.pid",
        "активного управляемого процесса",
        "Открыть резервное главное окно",
        "Резервное главное окно",
        "Окно восстановления",
        "Контекстный инструмент",
        "проектный контекст",
        "Контекст анимации",
        "контекст анимации",
        "Контекст анализа",
        "контекст анализа",
        "GUI-модули",
        "GUI-модуль",
        "GUI-окно",
        "GUI-окна",
        "специализированных GUI",
        "запущенные GUI",
        "Compare Viewer",
        "desktop-центр",
        "dock-панелей",
        "launch controls",
        "Проект: default",
            "C:\\",
            "master-copy",
        "Панель восстановления окон",
        "dt и t_end",
    ]
    for fragment in forbidden_qt_visible_fragments:
        assert fragment not in src


def test_desktop_qt_shell_project_context_resolves_project_and_workspace(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workspace_dir = tmp_path / "workspace"
    env = {
        "PNEUMO_WORKSPACE_DIR": str(workspace_dir),
        "PNEUMO_PROJECT": "Shell Demo",
    }

    context = build_shell_project_context(repo_root=repo_root, env=env)

    assert context.repo_root == repo_root.resolve()
    assert context.workspace_dir == workspace_dir.resolve()
    assert context.workspace_source == "PNEUMO_WORKSPACE_DIR"
    assert context.project_name == "Shell Demo"
    assert context.project_dir == workspace_dir.resolve() / "ui_state" / "projects" / "Shell Demo"
    assert "exports" in context.missing_workspace_dirs
    assert context.readiness_label.startswith("Нужно подготовить папки:")
    assert "workspace contract ok" not in context.readiness_label
    assert "missing workspace dirs" not in context.readiness_label


def test_desktop_shell_command_search_home_and_project_tree_actions_are_routable() -> None:
    entries = build_shell_command_search_entries(build_desktop_shell_specs())
    by_label = {entry.label: entry for entry in entries}

    assert by_label["Панель проекта"].action_kind == "home"
    assert by_label["Панель проекта"].action_value == "home"
    assert by_label["Перейти к списку рабочих окон"].action_kind == "focus"
    assert by_label["Перейти к списку рабочих окон"].action_value == "project_tree"
    assert by_label["Инженерный анализ"].action_kind == "tool"
    assert by_label["Инженерный анализ"].action_value == "desktop_engineering_analysis_center"
    assert "HO-007" in by_label["Инженерный анализ"].keywords
    engineering_matches = rank_shell_command_search_entries("Engineering Analysis", entries)
    assert engineering_matches[0].action_value == "desktop_engineering_analysis_center"
    assert by_label["Проверить подготовку анимации"].action_kind == "open_artifact"
    assert by_label["Проверить подготовку анимации"].action_value == "animator.analysis_context"
    assert "Показать данные для аниматора" not in by_label
    assert "Показать сведения для аниматора" not in by_label
    assert by_label["Проверить связь с аниматором"].action_value == (
        "animator.animator_link_contract"
    )
    assert by_label["Открыть результаты расчёта"].action_value == (
        "animator.selected_result_artifact_pointer"
    )
    assert by_label["Загрузить файл анимации"].action_kind == "tool"
    assert by_label["Загрузить файл анимации"].action_value == "desktop_animator"
    assert by_label["Открыть описание сохранённой анимации"].action_kind == "open_artifact"
    assert by_label["Открыть описание сохранённой анимации"].action_value == (
        "animator.capture_export_manifest"
    )
    assert "Показать результаты расчёта" not in by_label
    assert "Показать сохранение анимации" not in by_label
    assert "Показать файл анимации" not in by_label
    assert "Показать выбранный результат" not in by_label
    assert "Показать список рабочих окон" not in by_label
    assert "Открыть выбранный результат" not in by_label
    assert "Открыть файл анимации" not in by_label
    assert "Открыть сведения об экспорте анимации" not in by_label
    assert "Показать сведения об экспорте анимации" not in by_label
    assert "Открыть сравнение прогонов" not in by_label


def test_desktop_shell_command_search_manual_keywords_are_operator_language() -> None:
    entries = build_shell_command_search_entries(build_desktop_shell_specs())
    checked_labels = {
        "Перейти к списку рабочих окон",
        "Проверить проект и сохранить архив",
        "Анимировать результат",
        "Проверить подготовку анимации",
        "Проверить связь с аниматором",
        "Открыть результаты расчёта",
        "Загрузить файл анимации",
        "Открыть описание сохранённой анимации",
        "Сравнить прогоны",
    }
    forbidden = (
        "project",
        "browser",
        "navigator",
        "diagnostics",
        "bundle",
        "health",
        "self-check",
        "animation",
        "viewport",
        "viewcube",
        "HO-",
        "analysis_context",
        "analysis context",
        "frozen context",
        "handoff",
        "animator_link_contract",
        "link contract",
        "analysis to animator",
        "selected_result_artifact_pointer",
        "selected pointer",
        "artifact pointer",
        "selected_npz_path",
        "animation npz",
        "anim_latest",
        "capture_export_manifest",
        "capture export manifest",
        "capture_hash",
        "animator export",
        "analysis lineage",
        "compare",
        "results",
        "маршрут",
    )
    offenders: list[str] = []

    for entry in entries:
        if entry.label not in checked_labels:
            continue
        keyword_text = " | ".join(entry.keywords)
        bad = [fragment for fragment in forbidden if fragment.lower() in keyword_text.lower()]
        if bad:
            offenders.append(f"{entry.label}: {', '.join(bad)}")

    assert not offenders, "\n".join(offenders)


def test_desktop_shell_visible_text_does_not_expose_service_handoff_jargon() -> None:
    forbidden = (
        "HO-",
        "handoff",
        "source-of-truth",
        "selected_run_contract",
        "validated_suite_snapshot",
        "runtime overrides",
        "derived/consumer",
        "ring_source_of_truth_json",
        "scenario_json",
        "road_csv",
        "axay_csv",
        "meta_json",
        "suite_snapshot_hash",
        "health-check",
        "Desktop Animator",
    )

    offenders: list[str] = []
    specs = build_desktop_shell_specs()
    for spec in specs:
        visible = " | ".join((spec.title, spec.description, spec.details))
        bad = [fragment for fragment in forbidden if fragment in visible]
        if bad:
            offenders.append(f"{spec.key}: {', '.join(bad)}")

    for entry in build_shell_command_search_entries(specs):
        visible = " | ".join((entry.label, entry.location, entry.summary))
        bad = [fragment for fragment in forbidden if fragment in visible]
        if bad:
            offenders.append(f"{entry.action_value}: {', '.join(bad)}")

    assert not offenders, "\n".join(offenders)


def test_desktop_qt_shell_v38_pipeline_dot_alignment_contract() -> None:
    alignment = build_v38_pipeline_dot_alignment(ROOT)

    assert alignment["ok"] is True
    assert alignment["shell_workspace_present"] is True
    assert set(alignment["expected_workspace_ids"]) == set(V38_PIPELINE_WORKSPACE_IDS)
    assert set(alignment["dot_workspace_ids"]) >= set(V38_PIPELINE_WORKSPACE_IDS)
    assert "WS-SHELL" in alignment["dot_workspace_ids"]
    assert set(alignment["selection_sync_workspace_ids"]) >= set(V38_PIPELINE_WORKSPACE_IDS)
    assert alignment["missing_workspace_ids_from_dot"] == []
    assert alignment["missing_selection_sync_edges"] == []
    assert alignment["unexpected_pipeline_workspace_ids"] == []


def test_desktop_qt_shell_opens_animator_ho008_artifacts_from_command_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QtCore, QtGui, _QtWidgets = _qt_modules()
    context = _test_project_context(tmp_path)
    context_path, link_path, pointer_path, capture_manifest_path = _write_qt_shell_analysis_context(
        context.workspace_dir
    )
    opened: list[str] = []

    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: context,
    )
    monkeypatch.setattr(
        QtGui.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )

    app = _qt_app()
    window = qt_main_window_module.DesktopQtMainShell()
    try:
        app.processEvents()
        assert window.open_shell_artifact("animator.analysis_context") is True
        assert Path(opened[-1]) == context_path.resolve()
        assert window.open_shell_artifact("animator.animator_link_contract") is True
        assert Path(opened[-1]) == link_path.resolve()
        assert window.open_shell_artifact("animator.selected_result_artifact_pointer") is True
        assert Path(opened[-1]) == pointer_path.resolve()
        assert window.open_shell_artifact("animator.selected_npz_path") is True
        assert Path(opened[-1]).name == "anim_latest.npz"
        assert window.open_shell_artifact("animator.capture_export_manifest") is True
        assert Path(opened[-1]) == capture_manifest_path.resolve()

        launched: list[str] = []
        window.open_tool = lambda key: launched.append(key) or True  # type: ignore[method-assign]

        window.command_search_edit.setText("загрузить файл анимации")
        app.processEvents()
        first = window.search_results_list.item(0)
        assert first is not None
        assert first.data(QtCore.Qt.ItemDataRole.UserRole + 1) == "tool"
        window._activate_search_item(first)
        assert launched[-1] == "desktop_animator"

        window.command_search_edit.setText("сохранение анимации")
        app.processEvents()
        first = window.search_results_list.item(0)
        assert first is not None
        assert first.data(QtCore.Qt.ItemDataRole.UserRole + 1) == "open_artifact"
        window._activate_search_item(first)
        assert Path(opened[-1]) == capture_manifest_path.resolve()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_desktop_qt_shell_offscreen_runtime_keeps_menu_docks_shortcuts_and_status_strip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QtCore, QtGui, QtWidgets = _qt_modules()
    settings_path = tmp_path / "main_shell_state.ini"
    monkeypatch.setenv("PNEUMO_QT_MAIN_SHELL_STATE_PATH", str(settings_path))
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )
    _FakeCoexistenceManager.instances.clear()
    monkeypatch.setattr(
        qt_main_window_module,
        "DesktopShellCoexistenceManager",
        _FakeCoexistenceManager,
    )

    app = _qt_app()
    window = qt_main_window_module.DesktopQtMainShell()
    try:
        app.processEvents()

        assert isinstance(window, QtWidgets.QMainWindow)
        assert window.windowFlags() & QtCore.Qt.WindowType.Window
        assert window.objectName() == "DesktopQtMainShell"
        assert [action.text() for action in window.menuBar().actions()] == [
            "Файл",
            "Правка",
            "Вид",
            "Запуск",
            "Анализ",
            "Анимация",
            "Проверка",
            "Инструменты",
            "Справка",
        ]

        dock_names = {dock.objectName() for dock in window.findChildren(QtWidgets.QDockWidget)}
        assert {
            "DesktopQtShellBrowserDock",
            "DesktopQtShellInspectorDock",
            "DesktopQtShellRuntimeDock",
        } <= dock_names
        assert window.browser_dock.features() & QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable

        diagnostics_button = window.findChild(QtWidgets.QPushButton, "AlwaysVisibleDiagnosticsAction")
        assert diagnostics_button is window.diagnostics_button
        assert diagnostics_button.shortcut().matches(QtGui.QKeySequence("F7"))
        launch_combo = window.findChild(QtWidgets.QComboBox, "DesktopQtShellLaunchToolCombo")
        assert launch_combo is window.launch_tool_combo
        assert window.message_strip_label.objectName() == "ShellMessagesStrip"
        assert window.status_progress_bar.objectName() == "ShellStatusProgress"
        assert window.status_progress_bar.value() == 0

        shortcut_keys = {
            shortcut.key().toString(QtGui.QKeySequence.SequenceFormat.PortableText)
            for shortcut in window.findChildren(QtGui.QShortcut)
        }
        assert {"Ctrl+K", "F6", "Shift+F6", "F7", "F8"} <= shortcut_keys
        assert window._focus_regions == [
            window.command_search_edit,
            window.browser_tree,
            window.workflow_list,
            window.inspector_tabs,
            window.runtime_table,
            window.message_strip_label,
        ]

        top_level_labels = {
            window.browser_tree.topLevelItem(index).text(0)
            for index in range(window.browser_tree.topLevelItemCount())
        }
        assert "Проект: Runtime Shell" in top_level_labels
        assert "Порядок работы" in top_level_labels
        assert "Окна" in top_level_labels

        expected_launch_keys = {
            spec.key for spec in build_desktop_shell_specs() if spec.standalone_module
        }
        coverage = {
            surface: set(keys)
            for surface, keys in window.launch_surface_coverage().items()
        }
        assert coverage["expected"] == expected_launch_keys
        assert expected_launch_keys <= coverage["browser"]
        assert expected_launch_keys <= coverage["menu"]
        assert expected_launch_keys <= coverage["toolbar"]
        assert expected_launch_keys <= coverage["command_search"]
        assert "desktop_engineering_analysis_center" in coverage["browser"]
        assert "desktop_engineering_analysis_center" in coverage["menu"]
        assert "desktop_engineering_analysis_center" in coverage["toolbar"]

        pipeline_coverage = {
            surface: set(keys)
            for surface, keys in window.pipeline_surface_coverage().items()
        }
        expected_workspace_ids = set(V38_PIPELINE_WORKSPACE_IDS)
        assert pipeline_coverage["expected"] == expected_workspace_ids
        assert expected_workspace_ids <= pipeline_coverage["browser"]
        assert expected_workspace_ids <= pipeline_coverage["toolbar"]
        assert expected_workspace_ids <= pipeline_coverage["command_search"]

        operator_snapshot = window.operator_surface_snapshot()
        assert operator_snapshot["service_blocker_hits"] == []
        assert operator_snapshot["forbidden_label_hits"] == []
        assert "Запустить раздел" not in operator_snapshot["toolbar_buttons"]
        assert "Запустить текущий раздел" not in operator_snapshot["toolbar_buttons"]
        visible_audit = window.operator_visible_audit()
        assert visible_audit["forbidden_label_hits"] == []
        assert set(visible_audit["forbidden_labels"]) >= set(OPERATOR_FORBIDDEN_LABELS)
        assert set(visible_audit["forbidden_labels"]) >= {
            "Идентификатор",
            "идентификатор",
            "Идентичность запуска",
            "Артефакт",
            "артефакт",
            "Маршрут",
            "маршрут",
            "статус миграции",
        }
        assert visible_audit["menu_titles"] == [
            "Файл",
            "Правка",
            "Вид",
            "Запуск",
            "Анализ",
            "Анимация",
            "Проверка",
            "Инструменты",
            "Справка",
        ]
        assert "Помощь по рабочим окнам" in visible_audit["menu_actions"]
        assert "Панели" in visible_audit["menu_actions"]
        assert "Вернуть все панели" in visible_audit["menu_actions"]
        assert "Окна по задаче" in visible_audit["menu_actions"]
        assert "Справочники и проверки" in visible_audit["menu_actions"]
        assert "Детальная проверка результата" in visible_audit["menu_actions"]
        assert "Дополнительная визуализация" in visible_audit["menu_actions"]
        assert "Все окна" not in visible_audit["menu_actions"]
        assert "Окно восстановления" not in visible_audit["menu_actions"]
        assert "Панель восстановления окон" not in visible_audit["menu_actions"]
        assert "Открыть окно" not in visible_audit["toolbar_buttons"]
        assert "1. Исходные данные" in visible_audit["toolbar_buttons"]
        assert "2. Сценарии" in visible_audit["toolbar_buttons"]
        assert "7. Анимация" in visible_audit["toolbar_buttons"]
        assert "8. Проверка проекта" in visible_audit["toolbar_buttons"]
        assert "Открыть сравнение" not in visible_audit["toolbar_buttons"]
        assert "Открыть в аниматоре" not in visible_audit["toolbar_buttons"]
        assert "Показать в аниматоре" not in visible_audit["toolbar_buttons"]
        assert "Анимировать результат" in visible_audit["toolbar_buttons"]
        assert (
            "Выбор показывает связанный рабочий шаг. Рабочее окно запускается через меню «Запуск», двойной щелчок в списке «Окна» или быстрый поиск."
            in visible_audit["auxiliary_visible_texts"]
        )
        assert "Выбор из списка сразу открывает выбранное окно." not in visible_audit["auxiliary_visible_texts"]
        assert "Док-панель: перетаскивается, открепляется и меняет ширину границей." in visible_audit["auxiliary_visible_texts"]
        assert "Открепить панель" in visible_audit["auxiliary_visible_texts"]
        assert "Закрыть панель" in visible_audit["auxiliary_visible_texts"]
        assert "Прокрутить вкладки влево" in visible_audit["auxiliary_visible_texts"]
        assert "Прокрутить вкладки вправо" in visible_audit["auxiliary_visible_texts"]
        assert (
            "Рабочее место инженера: выберите шаг работы, проверьте состояние и запускайте отдельные окна только явной командой."
            in visible_audit["direct_visible_texts"]
        )
        assert (
            "Основной порядок: исходные данные -> сценарии -> испытания -> базовый прогон -> оптимизация -> анализ -> анимация -> проверка проекта."
            in visible_audit["direct_visible_texts"]
        )
        assert "Окна, действия, испытания, сценарии, архив проекта, расчёты, файлы" in visible_audit["direct_visible_texts"]
        assert "Панель проекта" in visible_audit["direct_visible_texts"]
        assert "Основной порядок работы" in visible_audit["direct_visible_texts"]
        assert "Рабочие шаги" in visible_audit["direct_visible_texts"]
        assert "Достоверность отображения" in visible_audit["direct_visible_texts"]
        assert "Крупные состояния: расчётно подтверждено, по исходным данным, условно, недоступно." in visible_audit["direct_visible_texts"]
        assert "Окно / шаг" in visible_audit["item_visible_texts"]
        assert "Недоступно до выбранного прогона" in visible_audit["direct_visible_texts"]
        assert "По исходным данным до расчёта" in visible_audit["direct_visible_texts"]
        assert "Недоступна до результатов расчёта" in visible_audit["direct_visible_texts"]
        assert "Локальный запуск" in visible_audit["item_visible_texts"]
        assert "Параллельный запуск" in visible_audit["item_visible_texts"]
        assert "Поэтапный запуск" not in visible_audit["item_visible_texts"]
        assert "Распределённая координация" not in visible_audit["item_visible_texts"]
        assert (
            "3. Набор испытаний - Проверить включение тестов, этапы, приоритеты, шаг расчёта и длительность."
            in visible_audit["item_visible_texts"]
        )
        assert (
            "4. Базовый прогон - Создать или проверить базовый прогон перед оптимизацией."
            in visible_audit["item_visible_texts"]
        )
        runtime_rows_text = "\n".join(visible_audit["runtime_rows"])
        assert "Процесс" not in runtime_rows_text
        assert "pid" not in runtime_rows_text.lower()
        assert "4321" not in runtime_rows_text
        assert any(
            row.startswith("Порядок работы | выбор сразу показывает нужный экран")
            for row in visible_audit["browser_rows"]
        )
        assert "Исходные данные" in visible_audit["workspace_selector_items"]
        assert visible_audit["inspector"]["values"]["section"] == window.property_title_value.text()
        assert visible_audit["status_strip"]["message_text"].startswith("Сообщения:")
        visible_text = "\n".join(
            str(item)
            for item in [
                *visible_audit["menu_titles"],
                *visible_audit["menu_actions"],
                *visible_audit["toolbar_buttons"],
                *visible_audit["workspace_selector_items"],
                *visible_audit["gui_module_selector_items"],
                *visible_audit["browser_rows"],
                *visible_audit["runtime_rows"],
                *visible_audit["inspector"]["labels"],
                *visible_audit["inspector"]["values"].values(),
                visible_audit["inspector"]["help_text"],
                *visible_audit["inspector"]["warnings"],
                *visible_audit["status_strip"].values(),
                *visible_audit["auxiliary_visible_texts"],
                *visible_audit["direct_visible_texts"],
                *visible_audit["item_visible_texts"],
            ]
        )
        for fragment in (
            "open_artifact",
            "animator_link_contract",
            "selected_result_artifact_pointer",
            "capture_export_manifest",
            "dt и t_end",
            "Идентификатор",
            "идентификатор",
            "Идентичность запуска",
            "Артефакт",
            "артефакт",
            "статус миграции",
            "Показать список рабочих окон",
        ):
            assert fragment not in visible_text
        catalog_labels = {
            entry["label"] for entry in visible_audit["command_search_catalog"]
        }
        assert "Перейти к списку рабочих окон" in catalog_labels
        assert any(
            result["action_value"] == "project_tree"
            for result in visible_audit["command_search_results"]["список проекта"]
        )
        pipeline_sync = window.prove_v38_pipeline_selection_sync()
        assert pipeline_sync["missing_workspace_ids"] == []
        assert all(row["synced"] is True for row in pipeline_sync["rows"])

        window.command_search_edit.setText("список проекта")
        app.processEvents()
        assert window.search_results_list.count() > 0
        window._activate_primary_search_result()
        assert window.central_stack.currentWidget() is window.overview_page
        assert window.browser_tree.currentItem() is not None
        assert "список проекта" in window.status_label.text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_desktop_qt_shell_handoff_payload_and_layout_state_are_runtime_checked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QtCore, _QtGui, _QtWidgets = _qt_modules()
    settings_path = tmp_path / "main_shell_state.ini"
    monkeypatch.setenv("PNEUMO_QT_MAIN_SHELL_STATE_PATH", str(settings_path))
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )
    _FakeCoexistenceManager.instances.clear()
    monkeypatch.setattr(
        qt_main_window_module,
        "DesktopShellCoexistenceManager",
        _FakeCoexistenceManager,
    )

    app = _qt_app()
    window = qt_main_window_module.DesktopQtMainShell()
    try:
        app.processEvents()
        window.optimization_mode_combo.setCurrentIndex(1)
        assert window.visual_truth_labels["Анимация"].text() == "Недоступна до результатов расчёта"
        window.start_action_buttons["desktop_ring_editor"].click()
        app.processEvents()
        assert window._selected_surface_key == "ws_ring"
        input_index = window.launch_tool_combo.findData("desktop_input_editor")
        assert input_index >= 0
        window.launch_tool_combo.setCurrentIndex(input_index)
        window.launch_tool_combo.activated.emit(input_index)
        app.processEvents()
        assert window._selected_surface_key == "ws_inputs"
        assert window.open_tool("desktop_animator") is True

        manager = _FakeCoexistenceManager.instances[-1]
        assert [session.spec.key for session in manager.opened] == [
            "desktop_animator",
        ]
        payload = manager.opened[-1].context_payload
        assert payload["selected_tool_key"] == "desktop_animator"
        assert payload["active_optimization_mode"] == "Параллельный запуск"
        assert payload["project_name"] == "Runtime Shell"
        assert payload["workspace_dir"] == str((tmp_path / "workspace").resolve())
        assert payload["repo_root"] == str((tmp_path / "repo").resolve())
        assert window.runtime_table.topLevelItemCount() == 1
        assert window.runtime_table.columnCount() == 3
        runtime_rows = [
            " | ".join(
                window.runtime_table.topLevelItem(row).text(column)
                for column in range(window.runtime_table.columnCount())
            )
            for row in range(window.runtime_table.topLevelItemCount())
        ]
        assert "4321" not in "\n".join(runtime_rows)
        assert window.status_progress_bar.value() > 0

        window._apply_selected_tool("desktop_results_center", announce=False)
        window._save_layout()
        settings = QtCore.QSettings(str(settings_path), QtCore.QSettings.Format.IniFormat)
        assert settings.value("layout/last_workspace_key") == "desktop_results_center"
        assert settings.value("layout/last_surface_key") == "ws_analysis"
        assert settings.value("layout/optimization_mode") == "Параллельный запуск"
        assert settings.value("layout/geometry") is not None
        assert settings.value("layout/window_state") is not None

        window.browser_dock.setFloating(True)
        window.browser_dock.hide()
        window._reset_layout()
        assert window.browser_dock.isFloating() is False
        assert window.browser_dock.isHidden() is False
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()

    restored = qt_main_window_module.DesktopQtMainShell()
    try:
        app.processEvents()
        assert restored._selected_tool_key == "desktop_results_center"
        assert restored.optimization_mode_combo.currentText() == "Параллельный запуск"
    finally:
        restored.close()
        restored.deleteLater()
        app.processEvents()


def test_desktop_qt_shell_default_handoff_payload_filters_to_allowed_shell_context() -> None:
    spec = {item.key: item for item in build_desktop_shell_specs()}["desktop_optimizer_center"]
    payload = _default_context_payload(
        spec,
        {
            "selected_tool_key": "desktop_optimizer_center",
            "project_name": "Runtime Shell",
            "project_dir": "C:/work/project",
            "workspace_dir": "C:/work",
            "repo_root": "C:/repo",
            "workspace_role": "workspace",
            "runtime_kind": "tk",
            "migration_status": "managed_external",
            "domain_parameter": "must not leak",
        },
    )
    env = build_shell_context_env(payload)
    decoded = json.loads(env["PNEUMO_GUI_SHELL_CONTEXT_JSON"])

    assert decoded["selected_tool_key"] == "desktop_optimizer_center"
    assert decoded["project_name"] == "Runtime Shell"
    assert decoded["workspace_dir"] == "C:/work"
    assert decoded["repo_root"] == "C:/repo"
    assert decoded["runtime_kind"] == "tk"
    assert decoded["migration_status"] == "managed_external"
    assert "domain_parameter" not in decoded


def test_desktop_qt_shell_runtime_proof_writes_shell_only_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _qt_modules()
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )

    result = write_qt_main_shell_runtime_proof(tmp_path / "evidence", offscreen=True)
    proof_path = Path(str(result["json_path"]))
    proof = json.loads(proof_path.read_text(encoding="utf-8"))

    assert result["status"] == "PASS"
    assert result["release_readiness"] == "PENDING_MANUAL_VERIFICATION"
    assert result["manual_verification_status"] == "PENDING"
    assert proof_path.name == QT_MAIN_SHELL_RUNTIME_PROOF_JSON_NAME
    assert proof["schema"] == "qt_main_shell_runtime_proof.v1"
    assert proof["release_readiness"] == "PENDING_MANUAL_VERIFICATION"
    assert proof["manual_verification"]["status"] == "PENDING"
    assert proof["handoff_policy"]["external_domain_windows_launched"] == 0
    assert proof["checks"]["qmainwindow_runtime"] is True
    assert proof["checks"]["dock_layout_present"] is True
    assert proof["checks"]["keyboard_first_shortcuts"] is True
    assert proof["checks"]["visible_diagnostics_action"] is True
    assert proof["checks"]["layout_save_restore_reset"] is True
    assert proof["checks"]["command_search_project_tree_route"] is True
    assert proof["checks"]["all_launchable_tools_visible_from_shell"] is True
    assert proof["checks"]["operator_surface_no_service_jargon"] is True
    assert proof["checks"]["operator_visible_forbidden_labels_absent"] is True
    assert proof["checks"]["v38_pipeline_selection_sync"] is True
    assert proof["checks"]["v38_pipeline_dot_alignment"] is True
    expected_launch_keys = {
        spec.key for spec in build_desktop_shell_specs() if spec.standalone_module
    }
    assert set(proof["launch_coverage"]["expected"]) == expected_launch_keys
    assert set(proof["launch_coverage"]["browser"]) >= expected_launch_keys
    assert set(proof["launch_coverage"]["menu"]) >= expected_launch_keys
    assert set(proof["launch_coverage"]["toolbar"]) >= expected_launch_keys
    assert set(proof["launch_coverage"]["command_search"]) >= expected_launch_keys
    assert proof["launch_coverage_missing"] == {
        "browser": [],
        "menu": [],
        "toolbar": [],
        "command_search": [],
    }
    expected_workspace_ids = set(V38_PIPELINE_WORKSPACE_IDS)
    assert set(proof["pipeline_surface_coverage"]["expected"]) == expected_workspace_ids
    assert set(proof["pipeline_surface_coverage"]["browser"]) >= expected_workspace_ids
    assert set(proof["pipeline_surface_coverage"]["toolbar"]) >= expected_workspace_ids
    assert set(proof["pipeline_surface_coverage"]["command_search"]) >= expected_workspace_ids
    assert proof["pipeline_surface_coverage_missing"] == {
        "browser": [],
        "toolbar": [],
        "command_search": [],
    }
    assert proof["operator_surface"]["service_blocker_hits"] == []
    assert proof["operator_surface"]["forbidden_label_hits"] == []
    assert proof["operator_visible_audit"]["forbidden_label_hits"] == []
    assert proof["forbidden_operator_label_hits"] == []
    assert proof["pipeline_selection_sync"]["missing_workspace_ids"] == []
    assert proof["pipeline_dot_alignment"]["ok"] is True
    assert proof["pipeline_dot_alignment"]["missing_workspace_ids_from_dot"] == []
    assert proof["pipeline_dot_alignment"]["missing_selection_sync_edges"] == []
    assert proof["pipeline_dot_alignment"]["unexpected_pipeline_workspace_ids"] == []
    assert proof["diagnostics_action"]["object_name"] == "AlwaysVisibleDiagnosticsAction"
    assert "snap_half_third_quarter" in proof["manual_verification_required"]
    validation = validate_qt_main_shell_runtime_proof(proof_path)
    strict_validation = validate_qt_main_shell_runtime_proof(proof_path, require_manual_pass=True)
    assert validation["ok"] is True
    assert validation["release_readiness"] == "PENDING_MANUAL_VERIFICATION"
    assert validation["warnings"] == ["manual Snap/DPI/second-monitor verification is still pending"]
    assert strict_validation["ok"] is False
    assert any("requires manual PASS" in error for error in strict_validation["errors"])
    assert Path(str(result["manual_checklist_json_path"])).name == QT_MAIN_SHELL_MANUAL_CHECKLIST_JSON_NAME
    assert Path(str(result["manual_checklist_json_path"])).exists()
    assert Path(str(result["manual_checklist_md_path"])).exists()
    assert (tmp_path / "evidence" / "qt_main_shell_runtime_proof.md").exists()


def test_desktop_qt_shell_runtime_proof_accepts_operator_manual_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _qt_modules()
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )
    manual_results = tmp_path / "manual_results.json"
    manual_results.write_text(
        json.dumps(
            {
                "checks": {
                    "snap_half_third_quarter": {
                        "status": "PASS",
                        "operator": "pytest",
                        "checked_at": "2026-04-17T00:00:00Z",
                    },
                    "second_monitor_workflow": {
                        "status": "PASS",
                        "operator": "pytest",
                        "checked_at": "2026-04-17T00:00:00Z",
                    },
                    "mixed_dpi_or_pmv2_visual_check": {
                        "status": "PASS",
                        "operator": "pytest",
                        "checked_at": "2026-04-17T00:00:00Z",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = write_qt_main_shell_runtime_proof(
        tmp_path / "evidence_with_manual",
        offscreen=True,
        manual_results_path=manual_results,
    )
    proof = json.loads(Path(str(result["json_path"])).read_text(encoding="utf-8"))
    checklist = json.loads(Path(str(result["manual_checklist_json_path"])).read_text(encoding="utf-8"))

    assert result["status"] == "PASS"
    assert result["release_readiness"] == "PASS"
    assert result["manual_verification_status"] == "PASS"
    assert proof["release_readiness"] == "PASS"
    assert proof["manual_verification"]["manual_results_path"] == str(manual_results.resolve())
    assert checklist["status"] == "PASS"
    assert checklist["validation"]["ok"] is True
    assert {row["status"] for row in checklist["checks"]} == {"PASS"}
    assert validate_qt_main_shell_runtime_proof(result["json_path"], require_manual_pass=True)["ok"] is True


def test_desktop_qt_shell_manual_results_template_and_validator(tmp_path: Path) -> None:
    result = write_qt_main_shell_manual_results_template(tmp_path)
    template_path = Path(str(result["template_path"]))
    template = json.loads(template_path.read_text(encoding="utf-8"))

    assert template_path.name == QT_MAIN_SHELL_MANUAL_RESULTS_TEMPLATE_JSON_NAME
    assert template["schema"] == "qt_main_shell_manual_results.v1"
    assert set(template["checks"]) == {
        "snap_half_third_quarter",
        "second_monitor_workflow",
        "mixed_dpi_or_pmv2_visual_check",
    }
    assert validate_qt_main_shell_manual_results(template_path)["ok"] is True


def test_desktop_qt_shell_manual_results_validator_rejects_crooked_marks(tmp_path: Path) -> None:
    bad_results = tmp_path / "bad_manual_results.json"
    bad_results.write_text(
        json.dumps(
            {
                "checks": {
                    "snap_half_third_quarter": {"status": "PASS"},
                    "unknown_check": {"status": "PASS", "operator": "qa", "checked_at": "now"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validation = validate_qt_main_shell_manual_results(bad_results)

    assert validation["ok"] is False
    assert "unknown_check" in validation["unknown_check_ids"]
    assert "second_monitor_workflow" in validation["missing_check_ids"]
    assert any("operator is required" in error for error in validation["errors"])
    assert any("checked_at is required" in error for error in validation["errors"])


def test_desktop_qt_shell_runtime_proof_rejects_invalid_manual_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _qt_modules()
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )
    bad_results = tmp_path / "bad_manual_results.json"
    bad_results.write_text(
        json.dumps(
            {
                "checks": {
                    "snap_half_third_quarter": {"status": "PASS"},
                    "second_monitor_workflow": {"status": "PASS"},
                    "mixed_dpi_or_pmv2_visual_check": {"status": "PASS"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = write_qt_main_shell_runtime_proof(
        tmp_path / "invalid_manual_evidence",
        offscreen=True,
        manual_results_path=bad_results,
    )
    proof = json.loads(Path(str(result["json_path"])).read_text(encoding="utf-8"))

    assert result["status"] == "PASS"
    assert result["manual_verification_status"] == "FAIL"
    assert result["release_readiness"] == "FAIL"
    assert proof["manual_verification"]["validation"]["ok"] is False
    validation = validate_qt_main_shell_runtime_proof(result["json_path"])
    assert validation["ok"] is False
    assert any("manual validation failed" in error for error in validation["errors"])


def test_desktop_qt_shell_launcher_runtime_proof_cli_collects_and_exits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _qt_modules()
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )

    rc = desktop_main_shell_qt_module.main(
        ["--runtime-proof", str(tmp_path / "cli_evidence"), "--runtime-proof-offscreen"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["status"] == "PASS"
    assert payload["release_readiness"] == "PENDING_MANUAL_VERIFICATION"
    assert Path(payload["json_path"]).exists()
    assert Path(payload["md_path"]).exists()
    assert Path(payload["manual_checklist_json_path"]).exists()


def test_desktop_qt_shell_launcher_runtime_proof_validate_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _qt_modules()
    monkeypatch.setattr(
        qt_main_window_module,
        "build_shell_project_context",
        lambda: _test_project_context(tmp_path),
    )
    result = write_qt_main_shell_runtime_proof(tmp_path / "evidence", offscreen=True)

    rc = desktop_main_shell_qt_module.main(["--runtime-proof-validate", str(result["json_path"])])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["release_readiness"] == "PENDING_MANUAL_VERIFICATION"

    strict_rc = desktop_main_shell_qt_module.main(
        [
            "--runtime-proof-validate",
            str(result["json_path"]),
            "--runtime-proof-require-manual-pass",
        ]
    )
    strict_payload = json.loads(capsys.readouterr().out)

    assert strict_rc == 1
    assert strict_payload["ok"] is False
    assert any("requires manual PASS" in error for error in strict_payload["errors"])


def test_desktop_qt_shell_runtime_proof_validator_rejects_failed_automated_check(tmp_path: Path) -> None:
    proof_path = tmp_path / "qt_main_shell_runtime_proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "schema": "qt_main_shell_runtime_proof.v1",
                "status": "PASS",
                "release_readiness": "PENDING_MANUAL_VERIFICATION",
                "manual_verification_required": [
                    "snap_half_third_quarter",
                    "second_monitor_workflow",
                    "mixed_dpi_or_pmv2_visual_check",
                ],
                "manual_verification": {
                    "status": "PENDING",
                    "validation": {"ok": True, "errors": []},
                },
                "handoff_policy": {
                    "external_domain_windows_launched": 0,
                    "managed_external_launcher_only": True,
                },
                "launch_coverage": {
                    "expected": ["desktop_input_editor"],
                    "browser": ["desktop_input_editor"],
                    "menu": ["desktop_input_editor"],
                    "toolbar": ["desktop_input_editor"],
                    "command_search": ["desktop_input_editor"],
                },
                "pipeline_surface_coverage": {
                    "expected": ["WS-PROJECT"],
                    "browser": ["WS-PROJECT"],
                    "toolbar": ["WS-PROJECT"],
                    "command_search": ["WS-PROJECT"],
                },
                "operator_surface": {
                    "service_blocker_hits": [],
                    "forbidden_label_hits": [],
                },
                "operator_visible_audit": {
                    "forbidden_label_hits": [],
                },
                "forbidden_operator_label_hits": [],
                "pipeline_selection_sync": {
                    "missing_workspace_ids": [],
                },
                "pipeline_dot_alignment": {
                    "ok": True,
                    "missing_workspace_ids_from_dot": [],
                    "missing_selection_sync_edges": [],
                    "unexpected_pipeline_workspace_ids": [],
                },
                "checks": {
                    "qmainwindow_runtime": True,
                    "native_titlebar_precondition": True,
                    "menus_present": True,
                    "dock_layout_present": True,
                    "keyboard_first_shortcuts": False,
                    "visible_diagnostics_action": True,
                    "status_progress_messages_strip": True,
                    "command_search_project_tree_route": True,
                    "all_launchable_tools_visible_from_shell": True,
                    "operator_surface_no_service_jargon": True,
                    "operator_visible_forbidden_labels_absent": True,
                    "v38_pipeline_selection_sync": True,
                    "v38_pipeline_dot_alignment": True,
                    "layout_save_restore_reset": True,
                    "no_domain_windows_launched": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validation = validate_qt_main_shell_runtime_proof(proof_path)

    assert validation["ok"] is False
    assert validation["failed_automated_checks"] == ["keyboard_first_shortcuts"]
    assert any("failed automated" in error for error in validation["errors"])


def test_desktop_qt_shell_launcher_manual_template_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = desktop_main_shell_qt_module.main(["--runtime-proof-manual-template", str(tmp_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert Path(payload["template_path"]).name == QT_MAIN_SHELL_MANUAL_RESULTS_TEMPLATE_JSON_NAME
    assert Path(payload["template_path"]).exists()


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
    assert '"project_name"' in src
    assert '"workspace_dir"' in src
    assert '"migration_status"' in src


def test_desktop_qt_shell_launcher_validates_registry_keys_and_formats_catalog() -> None:
    catalog = desktop_main_shell_qt_module.format_tool_catalog()

    assert "Рабочие окна приложения:" in catalog
    assert "desktop_input_editor" in catalog
    assert "desktop_animator" in catalog
    assert "master" in catalog
    assert "derived" in catalog

    assert desktop_main_shell_qt_module.resolve_startup_tool_keys(
        ["desktop_input_editor", "compare_viewer"]
    ) == ("desktop_input_editor", "compare_viewer")
