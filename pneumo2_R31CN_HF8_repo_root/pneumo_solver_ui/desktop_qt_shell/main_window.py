from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_qt_shell.coexistence import DesktopShellCoexistenceManager
from pneumo_solver_ui.desktop_qt_shell.project_context import (
    ShellProjectContext,
    build_shell_project_context,
)
from pneumo_solver_ui.desktop_qt_shell.pipeline_surfaces import (
    OPERATOR_FORBIDDEN_LABELS,
    V38_PIPELINE_SURFACES,
    V38_PIPELINE_WORKSPACE_IDS,
    WORKSPACE_ARTIFACT_LABELS,
    ShellPipelineSurface,
    artifact_state_label,
    build_pipeline_surface_by_key,
    default_surface_key_for_tool,
    forbidden_operator_label_hits,
    operator_readiness_label,
    service_jargon_hits,
    workspace_source_label,
)
from pneumo_solver_ui.desktop_shell.command_search import (
    ShellCommandSearchEntry,
    build_shell_command_search_entries,
    rank_shell_command_search_entries,
)
from pneumo_solver_ui.desktop_shell.contracts import DesktopShellToolSpec
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.desktop_animator.analysis_context import load_analysis_context
from pneumo_solver_ui.release_info import get_release


MAIN_ROUTE_KEYS = (
    "desktop_input_editor",
    "desktop_ring_editor",
    "test_center",
    "desktop_optimizer_center",
    "desktop_results_center",
    "desktop_diagnostics_center",
)

SURFACE_ROLE = int(QtCore.Qt.ItemDataRole.UserRole)
TOOL_ROLE = SURFACE_ROLE + 1
ITEM_KIND_ROLE = SURFACE_ROLE + 2


def _build_shell_settings() -> QtCore.QSettings:
    state_path = str(os.environ.get("PNEUMO_QT_MAIN_SHELL_STATE_PATH") or "").strip()
    if state_path:
        return QtCore.QSettings(state_path, QtCore.QSettings.Format.IniFormat)
    return QtCore.QSettings("PneumoApp", "DesktopQtMainShell")


def _operator_state_label(spec: DesktopShellToolSpec) -> str:
    status = spec.effective_migration_status
    if status == "managed_external":
        return "Готово: отдельное окно"
    if status == "in_development":
        return "Есть открытые ограничения"
    return "Готово к работе"


def _runtime_label(spec: DesktopShellToolSpec) -> str:
    kind = spec.effective_runtime_kind
    if kind == "tk":
        return "Рабочее GUI-окно"
    if kind == "qt":
        return "Специализированное GUI-окно"
    return "Служебный процесс"


def _workspace_role_label(spec: DesktopShellToolSpec) -> str:
    role = spec.effective_workspace_role
    if role == "workspace":
        return "Рабочий раздел"
    if role == "specialized_window":
        return "Специализированное окно"
    if role == "contextual_tool":
        return "Контекстный инструмент"
    return "Служебный центр"


def _source_of_truth_label(spec: DesktopShellToolSpec) -> str:
    role = spec.effective_source_of_truth_role
    if role == "master":
        return "Основной ввод"
    if role == "derived":
        return "Результаты и анализ"
    if role == "launcher":
        return "Запуск"
    if role == "support":
        return "Справка и диагностика"
    return "Не задан"


def _unique_specs(specs: tuple[DesktopShellToolSpec, ...]) -> tuple[DesktopShellToolSpec, ...]:
    seen: set[str] = set()
    result: list[DesktopShellToolSpec] = []
    for spec in specs:
        if spec.key in seen:
            continue
        seen.add(spec.key)
        result.append(spec)
    return tuple(result)


class DesktopQtMainShell(QtWidgets.QMainWindow):
    def __init__(self, *, startup_tool_keys: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.specs = build_desktop_shell_specs()
        self.spec_by_key = {spec.key: spec for spec in self.specs}
        self.pipeline_surfaces = V38_PIPELINE_SURFACES
        self.pipeline_surface_by_key = build_pipeline_surface_by_key()
        self.command_entries = (
            *self._build_pipeline_search_entries(),
            *build_shell_command_search_entries(self.specs),
        )
        self.settings = _build_shell_settings()
        self.project_context: ShellProjectContext = build_shell_project_context()
        self.coexistence = DesktopShellCoexistenceManager()
        self._startup_tool_keys = startup_tool_keys
        self._selected_tool_key = startup_tool_keys[0] if startup_tool_keys else "desktop_input_editor"
        self._selected_surface_key = (
            default_surface_key_for_tool(self._selected_tool_key)
            if startup_tool_keys
            else "ws_project"
        )
        self._selected_search_entries: list[ShellCommandSearchEntry] = []
        self._focus_regions: list[QtWidgets.QWidget] = []
        self._message_log: list[str] = []

        self._configure_window()
        self._build_command_toolbar()
        self._build_browser_dock()
        self._build_inspector_dock()
        self._build_runtime_dock()
        self._build_central_surface()
        self._build_status_bar()
        self._build_menu()
        self._restore_layout()
        self._populate_workspace_switcher()
        self._populate_launch_tool_switcher()
        self._populate_browser_tree()
        self._refresh_search_results()
        self._apply_selected_surface(self._selected_surface_key, announce=False)
        self._install_shortcuts()
        self._start_polling()
        QtCore.QTimer.singleShot(0, self._open_startup_tools)

    def _launchable_specs(self) -> tuple[DesktopShellToolSpec, ...]:
        return tuple(spec for spec in self.specs if spec.standalone_module)

    def _main_route_specs(self) -> tuple[DesktopShellToolSpec, ...]:
        return tuple(self.spec_by_key[key] for key in MAIN_ROUTE_KEYS if key in self.spec_by_key)

    def _launch_surface_groups(self) -> tuple[tuple[str, tuple[DesktopShellToolSpec, ...]], ...]:
        main_route_specs = self._main_route_specs()
        tool_specs = tuple(spec for spec in self.specs if spec.entry_kind == "tool")
        analysis_specs = tuple(
            spec
            for spec in self.specs
            if spec.entry_kind in {"contextual", "external"}
        )
        return (
            ("Маршрут проекта", main_route_specs),
            ("Справочники и проверка проекта", _unique_specs(tool_specs)),
            ("Анализ и специализированные окна", _unique_specs(analysis_specs)),
        )

    def _build_pipeline_search_entries(self) -> tuple[ShellCommandSearchEntry, ...]:
        entries: list[ShellCommandSearchEntry] = []
        for surface in self.pipeline_surfaces:
            entries.append(
                ShellCommandSearchEntry(
                    label=surface.title,
                    location=f"Главное окно -> Маршрут проекта -> {surface.title}",
                    summary=surface.purpose,
                    action_kind="pipeline_surface",
                    action_value=surface.key,
                    keywords=(
                        surface.workspace_id,
                        surface.title,
                        surface.purpose,
                        surface.source_label,
                        surface.next_action,
                        surface.handoff_label,
                        *surface.search_aliases,
                    ),
                )
            )
        return tuple(entries)

    def _surface_for_tool(self, key: str) -> ShellPipelineSurface:
        if self._selected_surface_key in self.pipeline_surface_by_key:
            current = self.pipeline_surface_by_key[self._selected_surface_key]
            if current.tool_key == key:
                return current
        return self.pipeline_surface_by_key[default_surface_key_for_tool(key)]

    def expected_launchable_tool_keys(self) -> tuple[str, ...]:
        return tuple(spec.key for spec in self._launchable_specs())

    def visible_browser_tool_keys(self) -> tuple[str, ...]:
        keys: set[str] = set()

        def visit(item: QtWidgets.QTreeWidgetItem) -> None:
            for role in (TOOL_ROLE, SURFACE_ROLE):
                key = item.data(0, role)
                if isinstance(key, str) and key in self.spec_by_key:
                    keys.add(key)
            for child_index in range(item.childCount()):
                visit(item.child(child_index))

        for index in range(self.browser_tree.topLevelItemCount()):
            visit(self.browser_tree.topLevelItem(index))
        return tuple(sorted(keys))

    def visible_browser_workspace_ids(self) -> tuple[str, ...]:
        ids: set[str] = set()

        def visit(item: QtWidgets.QTreeWidgetItem) -> None:
            surface_key = item.data(0, SURFACE_ROLE)
            if isinstance(surface_key, str) and surface_key in self.pipeline_surface_by_key:
                ids.add(self.pipeline_surface_by_key[surface_key].workspace_id)
            for child_index in range(item.childCount()):
                visit(item.child(child_index))

        for index in range(self.browser_tree.topLevelItemCount()):
            visit(self.browser_tree.topLevelItem(index))
        return tuple(sorted(ids))

    def visible_menu_tool_keys(self) -> tuple[str, ...]:
        keys = {
            str(action.data())
            for action in self.findChildren(QtGui.QAction)
            if isinstance(action.data(), str) and action.data() in self.spec_by_key
        }
        return tuple(sorted(keys))

    def visible_toolbar_tool_keys(self) -> tuple[str, ...]:
        keys: set[str] = set()
        for index in range(self.launch_tool_combo.count()):
            key = self.launch_tool_combo.itemData(index)
            if isinstance(key, str) and key in self.spec_by_key:
                keys.add(key)
        for index in range(self.workspace_combo.count()):
            surface_key = self.workspace_combo.itemData(index)
            if isinstance(surface_key, str):
                surface = self.pipeline_surface_by_key.get(surface_key)
                if surface is not None and surface.tool_key:
                    keys.add(surface.tool_key)
        return tuple(sorted(keys))

    def visible_toolbar_workspace_ids(self) -> tuple[str, ...]:
        ids: set[str] = set()
        for index in range(self.workspace_combo.count()):
            surface_key = self.workspace_combo.itemData(index)
            if isinstance(surface_key, str) and surface_key in self.pipeline_surface_by_key:
                ids.add(self.pipeline_surface_by_key[surface_key].workspace_id)
        return tuple(sorted(ids))

    def visible_command_search_tool_keys(self) -> tuple[str, ...]:
        keys = {
            entry.action_value
            for entry in self.command_entries
            if entry.action_kind == "tool" and entry.action_value in self.spec_by_key
        }
        return tuple(sorted(keys))

    def visible_command_search_workspace_ids(self) -> tuple[str, ...]:
        ids = {
            self.pipeline_surface_by_key[entry.action_value].workspace_id
            for entry in self.command_entries
            if entry.action_kind == "pipeline_surface"
            and entry.action_value in self.pipeline_surface_by_key
        }
        return tuple(sorted(ids))

    def launch_surface_coverage(self) -> dict[str, tuple[str, ...]]:
        return {
            "expected": self.expected_launchable_tool_keys(),
            "browser": self.visible_browser_tool_keys(),
            "menu": self.visible_menu_tool_keys(),
            "toolbar": self.visible_toolbar_tool_keys(),
            "command_search": self.visible_command_search_tool_keys(),
        }

    def pipeline_surface_coverage(self) -> dict[str, tuple[str, ...]]:
        return {
            "expected": V38_PIPELINE_WORKSPACE_IDS,
            "browser": self.visible_browser_workspace_ids(),
            "toolbar": self.visible_toolbar_workspace_ids(),
            "command_search": self.visible_command_search_workspace_ids(),
        }

    def _add_tool_action(
        self,
        menu: QtWidgets.QMenu,
        spec: DesktopShellToolSpec,
        *,
        shortcut: QtGui.QKeySequence | None = None,
    ) -> QtGui.QAction:
        action = menu.addAction(spec.title)
        action.setData(spec.key)
        action.setObjectName(f"LaunchAction_{spec.key}")
        action.setToolTip(spec.effective_tooltip)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(lambda _checked=False, item_key=spec.key: self.open_tool(item_key))
        return action

    def _configure_window(self) -> None:
        release = get_release()
        self.setWindowTitle(f"PneumoApp - Рабочее место инженера ({release})")
        self.setObjectName("DesktopQtMainShell")
        self.resize(1640, 980)
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.GroupedDragging
        )

    def _project_summary_text(self) -> str:
        return (
            f"Проект: {self.project_context.project_name} | "
            f"Рабочая папка: {self.project_context.workspace_dir} | "
            f"{operator_readiness_label(self.project_context.missing_workspace_dirs)}"
        )

    def _set_status_message(self, text: str) -> None:
        message = str(text or "").strip() or "Готово"
        self.status_label.setText(message)
        self._message_log.insert(0, message)
        self._message_log = self._message_log[:8]
        self.message_strip_label.setText(f"Сообщения: {message}")

    def _set_shell_progress(self, value: int, *, text: str | None = None) -> None:
        bounded = max(0, min(100, int(value)))
        self.status_progress_bar.setValue(bounded)
        if text is not None:
            self.status_progress_bar.setFormat(text)

    def _focus_command_search(self) -> None:
        self.command_search_edit.setFocus()
        self.command_search_edit.selectAll()

    def _focus_project_tree(self) -> None:
        self.browser_tree.setFocus()
        if self.browser_tree.topLevelItemCount() > 0:
            self.browser_tree.setCurrentItem(self.browser_tree.topLevelItem(0))
        self._set_status_message("Фокус переведён в дерево проекта.")

    def _focus_messages_strip(self) -> None:
        self.message_strip_label.setFocus()
        self._set_status_message("Фокус переведён в нижнюю строку сообщений.")

    def _show_project_overview(self) -> None:
        self.command_search_edit.clear()
        self._apply_selected_surface("ws_project")
        self._focus_project_tree()

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        overview_action = file_menu.addAction("Обзор проекта")
        overview_action.triggered.connect(self._show_project_overview)
        file_menu.addSeparator()
        save_layout_action = file_menu.addAction("Сохранить раскладку")
        save_layout_action.triggered.connect(self._save_layout)
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        edit_menu = menubar.addMenu("Правка")
        search_action = edit_menu.addAction("Поиск команд")
        search_action.setShortcut(QtGui.QKeySequence("Ctrl+K"))
        search_action.triggered.connect(self._focus_command_search)
        tree_action = edit_menu.addAction("Фокус на дерево проекта")
        tree_action.triggered.connect(self._focus_project_tree)

        view_menu = menubar.addMenu("Вид")
        view_menu.addAction(self.browser_dock.toggleViewAction())
        view_menu.addAction(self.inspector_dock.toggleViewAction())
        view_menu.addAction(self.runtime_dock.toggleViewAction())
        view_menu.addSeparator()
        restore_layout_action = view_menu.addAction("Восстановить раскладку")
        restore_layout_action.triggered.connect(self._restore_layout)
        reset_layout_action = view_menu.addAction("Сбросить раскладку окна")
        reset_layout_action.triggered.connect(self._reset_layout)

        run_menu = menubar.addMenu("Запуск")
        for key in (
            "desktop_input_editor",
            "desktop_ring_editor",
            "test_center",
            "desktop_optimizer_center",
        ):
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            self._add_tool_action(run_menu, spec)
        all_tools_menu = run_menu.addMenu("Все GUI-модули")
        for group_title, group_specs in self._launch_surface_groups():
            group_menu = all_tools_menu.addMenu(group_title)
            for spec in group_specs:
                self._add_tool_action(group_menu, spec)
        run_menu.addSeparator()
        stop_action = run_menu.addAction("Остановить выбранное окно")
        stop_action.setShortcut(QtGui.QKeySequence("Shift+F5"))
        stop_action.triggered.connect(self.stop_selected_tool)

        analysis_menu = menubar.addMenu("Анализ")
        for key in ("desktop_results_center", "desktop_engineering_analysis_center", "compare_viewer"):
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            self._add_tool_action(analysis_menu, spec)

        animation_menu = menubar.addMenu("Анимация")
        for key in ("desktop_animator", "desktop_mnemo"):
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            self._add_tool_action(
                animation_menu,
                spec,
                shortcut=QtGui.QKeySequence("F8") if key == "desktop_animator" else None,
            )

        diagnostics_menu = menubar.addMenu("Диагностика")
        collect_diag_action = diagnostics_menu.addAction("Собрать диагностику")
        collect_diag_action.setShortcut(QtGui.QKeySequence("F7"))
        collect_diag_action.triggered.connect(lambda: self.open_tool("desktop_diagnostics_center"))
        focus_messages_action = diagnostics_menu.addAction("Показать сообщения рабочего места")
        focus_messages_action.triggered.connect(self._focus_messages_strip)

        tools_menu = menubar.addMenu("Инструменты")
        for key in ("desktop_geometry_reference_center", "autotest_gui"):
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            self._add_tool_action(tools_menu, spec)
        legacy_action = tools_menu.addAction("Открыть резервное старое окно")
        legacy_action.triggered.connect(self._show_legacy_shell_note)

        help_menu = menubar.addMenu("Справка")
        help_action = help_menu.addAction("О рабочем месте")
        help_action.triggered.connect(self._show_about_dialog)

    def _build_command_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Командная зона", self)
        toolbar.setObjectName("DesktopQtShellToolbar")
        toolbar.setMovable(False)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addWidget(QtWidgets.QLabel("Рабочее пространство:"))
        self.workspace_combo = QtWidgets.QComboBox(toolbar)
        self.workspace_combo.setAccessibleName("Переключатель рабочего пространства")
        self.workspace_combo.currentIndexChanged.connect(self._on_workspace_changed)
        toolbar.addWidget(self.workspace_combo)

        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel("GUI-модуль:"))
        self.launch_tool_combo = QtWidgets.QComboBox(toolbar)
        self.launch_tool_combo.setObjectName("DesktopQtShellLaunchToolCombo")
        self.launch_tool_combo.setAccessibleName("Единый выбор GUI-модуля")
        self.launch_tool_combo.setToolTip("Все доступные GUI-модули рабочего места.")
        self.launch_tool_combo.currentIndexChanged.connect(self._on_launch_tool_changed)
        toolbar.addWidget(self.launch_tool_combo)

        self.open_launch_tool_button = QtWidgets.QPushButton("Запустить GUI", toolbar)
        self.open_launch_tool_button.setObjectName("DesktopQtShellOpenLaunchTool")
        self.open_launch_tool_button.setToolTip("Явно запускает выбранное GUI-окно; навигация по маршруту работает сразу при выборе.")
        self.open_launch_tool_button.clicked.connect(self.open_selected_launch_tool)
        toolbar.addWidget(self.open_launch_tool_button)

        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel("Поиск команд:"))
        self.command_search_edit = QtWidgets.QLineEdit(toolbar)
        self.command_search_edit.setAccessibleName("Поиск команд")
        self.command_search_edit.setPlaceholderText(
            "Команды, экраны, тесты, сценарии, bundle, runs, artifacts"
        )
        self.command_search_edit.setToolTip("Ctrl+K. Поиск по разделам, командам, артефактам и маршрутам запуска.")
        self.command_search_edit.textChanged.connect(self._refresh_search_results)
        self.command_search_edit.returnPressed.connect(self._activate_primary_search_result)
        toolbar.addWidget(self.command_search_edit)

        toolbar.addSeparator()

        self.diagnostics_button = QtWidgets.QPushButton("Собрать диагностику", toolbar)
        self.diagnostics_button.setObjectName("AlwaysVisibleDiagnosticsAction")
        self.diagnostics_button.setShortcut(QtGui.QKeySequence("F7"))
        self.diagnostics_button.setToolTip("F7. Открыть диагностику и сбор SEND bundle.")
        self.diagnostics_button.clicked.connect(lambda: self.open_tool("desktop_diagnostics_center"))
        toolbar.addWidget(self.diagnostics_button)

        self.compare_button = QtWidgets.QPushButton("Открыть сравнение", toolbar)
        self.compare_button.clicked.connect(lambda: self.open_tool("compare_viewer"))
        toolbar.addWidget(self.compare_button)

        self.animator_button = QtWidgets.QPushButton("Открыть в аниматоре", toolbar)
        self.animator_button.clicked.connect(lambda: self.open_tool("desktop_animator"))
        toolbar.addWidget(self.animator_button)

        self.stop_button = QtWidgets.QPushButton("Остановить", toolbar)
        self.stop_button.clicked.connect(self.stop_selected_tool)
        toolbar.addWidget(self.stop_button)

        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel("Режим оптимизации:"))
        self.optimization_mode_combo = QtWidgets.QComboBox(toolbar)
        self.optimization_mode_combo.addItem("Поэтапный запуск")
        self.optimization_mode_combo.addItem("Распределённая координация")
        self.optimization_mode_combo.currentIndexChanged.connect(self._refresh_contract_badge)
        toolbar.addWidget(self.optimization_mode_combo)

        self.contract_badge = QtWidgets.QLabel(toolbar)
        self.contract_badge.setObjectName("ContractBadge")
        self.contract_badge.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        toolbar.addWidget(self.contract_badge)
        self._refresh_contract_badge()

    def _build_browser_dock(self) -> None:
        self.browser_dock = QtWidgets.QDockWidget("Обзор проекта", self)
        self.browser_dock.setObjectName("DesktopQtShellBrowserDock")
        self.browser_tree = QtWidgets.QTreeWidget(self.browser_dock)
        self.browser_tree.setHeaderLabels(("Раздел", "Состояние"))
        self.browser_tree.itemSelectionChanged.connect(self._on_browser_selection_changed)
        self.browser_tree.itemDoubleClicked.connect(self._on_browser_item_activated)
        self.browser_dock.setWidget(self.browser_tree)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.browser_dock)

    def _build_inspector_dock(self) -> None:
        self.inspector_dock = QtWidgets.QDockWidget("Свойства и помощь", self)
        self.inspector_dock.setObjectName("DesktopQtShellInspectorDock")
        self.inspector_tabs = QtWidgets.QTabWidget(self.inspector_dock)

        properties_page = QtWidgets.QWidget(self.inspector_tabs)
        properties_layout = QtWidgets.QFormLayout(properties_page)
        self.property_title_value = QtWidgets.QLabel(properties_page)
        self.property_runtime_value = QtWidgets.QLabel(properties_page)
        self.property_role_value = QtWidgets.QLabel(properties_page)
        self.property_source_value = QtWidgets.QLabel(properties_page)
        self.property_operator_state_value = QtWidgets.QLabel(properties_page)
        self.property_module_value = QtWidgets.QLabel(properties_page)
        self.property_module_value.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        properties_layout.addRow("Раздел:", self.property_title_value)
        properties_layout.addRow("Поверхность:", self.property_runtime_value)
        properties_layout.addRow("Роль:", self.property_role_value)
        properties_layout.addRow("Источник данных:", self.property_source_value)
        properties_layout.addRow("Состояние:", self.property_operator_state_value)
        properties_layout.addRow("Связанный GUI:", self.property_module_value)
        self.inspector_tabs.addTab(properties_page, "Свойства")

        help_page = QtWidgets.QWidget(self.inspector_tabs)
        help_layout = QtWidgets.QVBoxLayout(help_page)
        self.help_title = QtWidgets.QLabel("Пояснение [?]", help_page)
        self.help_text = QtWidgets.QTextBrowser(help_page)
        help_layout.addWidget(self.help_title)
        help_layout.addWidget(self.help_text)
        self.inspector_tabs.addTab(help_page, "Помощь")

        warnings_page = QtWidgets.QWidget(self.inspector_tabs)
        warnings_layout = QtWidgets.QVBoxLayout(warnings_page)
        self.warning_list = QtWidgets.QListWidget(warnings_page)
        warnings_layout.addWidget(self.warning_list)
        self.inspector_tabs.addTab(warnings_page, "Предупреждения")

        self.inspector_dock.setWidget(self.inspector_tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)

    def _build_runtime_dock(self) -> None:
        self.runtime_dock = QtWidgets.QDockWidget("Ход выполнения и внешние окна", self)
        self.runtime_dock.setObjectName("DesktopQtShellRuntimeDock")
        runtime_widget = QtWidgets.QWidget(self.runtime_dock)
        runtime_layout = QtWidgets.QVBoxLayout(runtime_widget)

        self.runtime_progress_label = QtWidgets.QLabel(
            "Здесь видно, какие GUI-окна запущены, что выполняется сейчас и где смотреть результат.",
            runtime_widget,
        )
        self.runtime_progress_label.setWordWrap(True)
        runtime_layout.addWidget(self.runtime_progress_label)

        self.runtime_progress_bar = QtWidgets.QProgressBar(runtime_widget)
        self.runtime_progress_bar.setRange(0, 100)
        self.runtime_progress_bar.setValue(0)
        self.runtime_progress_bar.setFormat("Готово: %p%")
        runtime_layout.addWidget(self.runtime_progress_bar)

        self.runtime_table = QtWidgets.QTreeWidget(runtime_widget)
        self.runtime_table.setHeaderLabels(("Окно", "Состояние", "Тип", "Процесс"))
        runtime_layout.addWidget(self.runtime_table)

        self.runtime_dock.setWidget(runtime_widget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.runtime_dock)

    def _build_central_surface(self) -> None:
        central = QtWidgets.QWidget(self)
        central_layout = QtWidgets.QVBoxLayout(central)

        self.banner_label = QtWidgets.QLabel(
            "Главное окно объединяет рабочие разделы проекта, поиск команд, диагностику и запуск специализированных GUI без возврата в WEB.",
            central,
        )
        self.banner_label.setWordWrap(True)
        self.banner_label.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        central_layout.addWidget(self.banner_label)

        self.route_label = QtWidgets.QLabel(
            "Маршрут: Исходные данные -> Набор испытаний и сценарии -> Базовый прогон -> Оптимизация -> Анализ -> Анимация -> Диагностика",
            central,
        )
        self.route_label.setWordWrap(True)
        central_layout.addWidget(self.route_label)

        self.project_summary_label = QtWidgets.QLabel(self._project_summary_text(), central)
        self.project_summary_label.setObjectName("ProjectContextSummary")
        self.project_summary_label.setWordWrap(True)
        central_layout.addWidget(self.project_summary_label)

        self.central_stack = QtWidgets.QStackedWidget(central)
        central_layout.addWidget(self.central_stack, 1)

        self.overview_page = QtWidgets.QWidget(self.central_stack)
        overview_layout = QtWidgets.QVBoxLayout(self.overview_page)
        self.surface_title = QtWidgets.QLabel(self.overview_page)
        surface_font = self.surface_title.font()
        surface_font.setPointSize(surface_font.pointSize() + 4)
        surface_font.setBold(True)
        self.surface_title.setFont(surface_font)
        overview_layout.addWidget(self.surface_title)

        self.surface_meta = QtWidgets.QLabel(self.overview_page)
        self.surface_meta.setWordWrap(True)
        overview_layout.addWidget(self.surface_meta)

        self.surface_description = QtWidgets.QLabel(self.overview_page)
        self.surface_description.setWordWrap(True)
        overview_layout.addWidget(self.surface_description)

        workflow_box = QtWidgets.QGroupBox("Видимый основной путь", self.overview_page)
        workflow_layout = QtWidgets.QVBoxLayout(workflow_box)
        self.workflow_list = QtWidgets.QListWidget(workflow_box)
        self.workflow_list.itemDoubleClicked.connect(self._on_workflow_item_activated)
        workflow_layout.addWidget(self.workflow_list)
        overview_layout.addWidget(workflow_box, 1)

        session_box = QtWidgets.QGroupBox("Открытые GUI-окна", self.overview_page)
        session_layout = QtWidgets.QVBoxLayout(session_box)
        self.session_summary_label = QtWidgets.QLabel(session_box)
        self.session_summary_label.setWordWrap(True)
        session_layout.addWidget(self.session_summary_label)
        overview_layout.addWidget(session_box)

        self.central_stack.addWidget(self.overview_page)

        self.search_page = QtWidgets.QWidget(self.central_stack)
        search_layout = QtWidgets.QVBoxLayout(self.search_page)
        self.search_summary_label = QtWidgets.QLabel(self.search_page)
        self.search_summary_label.setWordWrap(True)
        search_layout.addWidget(self.search_summary_label)
        self.search_results_list = QtWidgets.QListWidget(self.search_page)
        self.search_results_list.itemDoubleClicked.connect(self._on_search_result_activated)
        search_layout.addWidget(self.search_results_list, 1)
        self.central_stack.addWidget(self.search_page)

        self.central_stack.setCurrentWidget(self.overview_page)
        self.setCentralWidget(central)

    def _build_status_bar(self) -> None:
        status = QtWidgets.QStatusBar(self)
        self.setStatusBar(status)
        self.status_label = QtWidgets.QLabel("Готово", status)
        self.message_strip_label = QtWidgets.QLabel("Сообщения: готово", status)
        self.message_strip_label.setObjectName("ShellMessagesStrip")
        self.message_strip_label.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.status_progress_bar = QtWidgets.QProgressBar(status)
        self.status_progress_bar.setObjectName("ShellStatusProgress")
        self.status_progress_bar.setRange(0, 100)
        self.status_progress_bar.setValue(0)
        self.status_progress_bar.setMaximumWidth(170)
        self.mode_status_label = QtWidgets.QLabel(status)
        self.bundle_status_label = QtWidgets.QLabel(
            "Последний архив диагностики: откройте центр диагностики",
            status,
        )
        status.addWidget(self.status_label, 1)
        status.addWidget(self.message_strip_label, 1)
        status.addPermanentWidget(self.status_progress_bar)
        status.addPermanentWidget(self.mode_status_label)
        status.addPermanentWidget(self.bundle_status_label)
        self._refresh_status_bar()

    def _populate_workspace_switcher(self) -> None:
        self.workspace_combo.blockSignals(True)
        self.workspace_combo.clear()
        for surface in self.pipeline_surfaces:
            self.workspace_combo.addItem(surface.title, userData=surface.key)
        index = max(0, self.workspace_combo.findData(self._selected_surface_key))
        self.workspace_combo.setCurrentIndex(index)
        self.workspace_combo.blockSignals(False)

    def _populate_launch_tool_switcher(self) -> None:
        self.launch_tool_combo.blockSignals(True)
        self.launch_tool_combo.clear()
        for spec in self._launchable_specs():
            self.launch_tool_combo.addItem(spec.title, userData=spec.key)
        index = max(0, self.launch_tool_combo.findData(self._selected_tool_key))
        self.launch_tool_combo.setCurrentIndex(index)
        self.launch_tool_combo.blockSignals(False)

    def _populate_browser_tree(self) -> None:
        self.browser_tree.clear()
        project_root = QtWidgets.QTreeWidgetItem(
            (
                f"Проект: {self.project_context.project_name}",
                operator_readiness_label(self.project_context.missing_workspace_dirs),
            )
        )
        project_root.addChild(
            QtWidgets.QTreeWidgetItem(("Папка проекта", str(self.project_context.project_dir)))
        )
        project_root.addChild(
            QtWidgets.QTreeWidgetItem(("Рабочая папка", str(self.project_context.workspace_dir)))
        )
        project_root.addChild(
            QtWidgets.QTreeWidgetItem(
                ("Выбор рабочей папки", workspace_source_label(self.project_context.workspace_source))
            )
        )
        artifacts_root = QtWidgets.QTreeWidgetItem(
            (
                "Рабочие артефакты",
                operator_readiness_label(self.project_context.missing_workspace_dirs),
            )
        )
        for dirname in ("exports", "uploads", "road_profiles", "maneuvers", "opt_runs", "ui_state"):
            artifacts_root.addChild(
                QtWidgets.QTreeWidgetItem(
                    (
                        WORKSPACE_ARTIFACT_LABELS.get(dirname, dirname),
                        artifact_state_label(dirname, self.project_context.missing_workspace_dirs),
                    )
                )
            )
        project_root.addChild(artifacts_root)
        self.browser_tree.addTopLevelItem(project_root)
        project_root.setExpanded(True)
        artifacts_root.setExpanded(True)

        route_root = QtWidgets.QTreeWidgetItem(("Маршрут проекта", "выбор сразу показывает раздел"))
        for surface in self.pipeline_surfaces:
            item = QtWidgets.QTreeWidgetItem((surface.title, "готово к выбору"))
            item.setData(0, SURFACE_ROLE, surface.key)
            if surface.tool_key:
                item.setData(0, TOOL_ROLE, surface.tool_key)
            item.setData(0, ITEM_KIND_ROLE, "surface")
            route_root.addChild(item)
        self.browser_tree.addTopLevelItem(route_root)
        route_root.setExpanded(True)

        modules_root = QtWidgets.QTreeWidgetItem(("GUI-модули", "явный запуск отдельных окон"))
        for group_title, group_specs in self._launch_surface_groups():
            root_item = QtWidgets.QTreeWidgetItem((group_title, ""))
            for spec in group_specs:
                item = QtWidgets.QTreeWidgetItem(
                    (
                        spec.title,
                        _operator_state_label(spec),
                    )
                )
                item.setData(0, SURFACE_ROLE, default_surface_key_for_tool(spec.key))
                item.setData(0, TOOL_ROLE, spec.key)
                item.setData(0, ITEM_KIND_ROLE, "tool")
                root_item.addChild(item)
            modules_root.addChild(root_item)
            root_item.setExpanded(True)
        self.browser_tree.addTopLevelItem(modules_root)
        modules_root.setExpanded(True)

    def _refresh_search_results(self) -> None:
        query = self.command_search_edit.text().strip()
        entries = rank_shell_command_search_entries(query, self.command_entries)
        self._selected_search_entries = list(entries[:24])
        self.search_results_list.clear()
        for entry in self._selected_search_entries:
            label = f"{entry.label} — {entry.location}"
            item = QtWidgets.QListWidgetItem(label)
            item.setToolTip(entry.summary)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.action_value)
            item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, entry.action_kind)
            self.search_results_list.addItem(item)
        if query:
            self.search_summary_label.setText(
                f"Найдено результатов: {len(self._selected_search_entries)}. Enter открывает первый результат."
            )
            self.central_stack.setCurrentWidget(self.search_page)
        else:
            self.search_summary_label.setText("Начните вводить команду, экран, run, bundle или artifact.")
            self.central_stack.setCurrentWidget(self.overview_page)

    def _refresh_contract_badge(self) -> None:
        active_mode = self.optimization_mode_combo.currentText().strip()
        self.contract_badge.setText(
            "Расчёт: базовый прогон не выбран | цель не задана | "
            f"ограничения не проверены | режим: {active_mode}"
        )
        if hasattr(self, "mode_status_label"):
            self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        if not hasattr(self, "mode_status_label"):
            return
        self.mode_status_label.setText(
            f"Активный режим: {self.optimization_mode_combo.currentText().strip()}"
        )

    def _apply_selected_tool(self, key: str, *, announce: bool = True) -> None:
        spec = self.spec_by_key.get(key)
        if spec is None:
            return
        surface = self._surface_for_tool(key)
        self._apply_selected_surface(surface.key, announce=announce, selected_tool_key=key)

    def _apply_selected_surface(
        self,
        key: str,
        *,
        announce: bool = True,
        selected_tool_key: str | None = None,
    ) -> None:
        surface = self.pipeline_surface_by_key.get(key)
        if surface is None:
            return
        self._selected_surface_key = surface.key
        if selected_tool_key is not None:
            self._selected_tool_key = selected_tool_key
        elif surface.tool_key:
            self._selected_tool_key = surface.tool_key
        spec = self.spec_by_key.get(surface.tool_key or "") if surface.tool_key else None
        self.surface_title.setText(surface.title)
        self.surface_meta.setText(
            f"Шаг маршрута: {surface.title} | {surface.source_label} | "
            f"{operator_readiness_label(self.project_context.missing_workspace_dirs)}"
        )
        self.surface_description.setText(
            "\n".join(
                (
                    surface.purpose,
                    f"Следующее действие: {surface.next_action}",
                    f"Передача дальше: {surface.handoff_label}",
                )
            )
        )
        self.project_summary_label.setText(self._project_summary_text())
        self.session_summary_label.setText(
            "Выбор в дереве, поиске или верхнем переключателе уже является навигацией. "
            "Отдельное GUI-окно запускается только явной командой из списка GUI-модулей."
        )
        self._refresh_workflow_list()
        self._refresh_inspector(surface, spec)
        self._refresh_runtime_table()
        self._select_browser_item(surface.key)
        if hasattr(self, "launch_tool_combo"):
            index = self.launch_tool_combo.findData(surface.tool_key)
            if index >= 0 and self.launch_tool_combo.currentIndex() != index:
                self.launch_tool_combo.blockSignals(True)
                self.launch_tool_combo.setCurrentIndex(index)
                self.launch_tool_combo.blockSignals(False)
        if announce:
            self._set_status_message(f"Выбран раздел маршрута: {surface.title}")

    def _refresh_workflow_list(self) -> None:
        self.workflow_list.clear()
        for index, surface in enumerate(self.pipeline_surfaces, start=1):
            line = f"{index}. {surface.title} — {surface.next_action}"
            item = QtWidgets.QListWidgetItem(line)
            item.setData(SURFACE_ROLE, surface.key)
            if surface.tool_key:
                item.setData(TOOL_ROLE, surface.tool_key)
            item.setData(ITEM_KIND_ROLE, "surface")
            if surface.key == self._selected_surface_key:
                item.setSelected(True)
            self.workflow_list.addItem(item)

    def _refresh_inspector(
        self,
        surface: ShellPipelineSurface,
        spec: DesktopShellToolSpec | None,
    ) -> None:
        self.property_title_value.setText(surface.title)
        self.property_runtime_value.setText(
            "Обзор внутри главного окна" if spec is None else _runtime_label(spec)
        )
        self.property_role_value.setText(
            "Сводка проекта" if spec is None else _workspace_role_label(spec)
        )
        self.property_source_value.setText(
            surface.source_label if spec is None else _source_of_truth_label(spec)
        )
        self.property_operator_state_value.setText(
            operator_readiness_label(self.project_context.missing_workspace_dirs)
            if spec is None
            else _operator_state_label(spec)
        )
        self.property_module_value.setText(
            "Навигация внутри главного окна" if spec is None else spec.title
        )

        self.help_text.setPlainText(
            "\n\n".join(
                [
                    f"Что это: {surface.title}",
                    f"Назначение: {surface.purpose}",
                    f"Следующее действие: {surface.next_action}",
                    f"Передача дальше: {surface.handoff_label}",
                    f"Связанный GUI: {spec.title if spec is not None else 'не требуется'}",
                    f"Источник данных: {surface.source_label}",
                ]
            )
        )

        warnings: list[str] = []
        if spec is not None and spec.effective_migration_status == "managed_external":
            warnings.append(
                "Окно открывается отдельно, а главное окно передаёт ему проектный контекст и отслеживает состояние."
            )
        if spec is not None and spec.key == "desktop_animator":
            warnings.append(
                "Аниматор обязан показывать режимы: Расчётно подтверждено / По исходным данным / Условно по неполным данным."
            )
        if spec is not None and spec.key == "desktop_optimizer_center":
            warnings.append(
                "Для оптимизации разрешён только один активный режим запуска. Два равноправных launch controls запрещены."
            )
        if spec is not None and spec.key == "desktop_ring_editor":
            warnings.append(
                "Редактор кольца остаётся единственным источником истины для сценариев. Все road_csv, axay_csv и scenario_json — производные артефакты."
            )
        if not warnings:
            warnings.append("Критичных предупреждений по выбранному маршруту сейчас нет.")

        self.warning_list.clear()
        for line in warnings:
            self.warning_list.addItem(line)

    def _refresh_runtime_table(self) -> None:
        sessions = self.coexistence.all_sessions()
        self.runtime_table.clear()
        for session in sessions:
            item = QtWidgets.QTreeWidgetItem(
                (
                    session.spec.title,
                    session.status_label(),
                    session.runtime_label,
                    str(session.pid or "—"),
                )
            )
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, session.spec.key)
            self.runtime_table.addTopLevelItem(item)
        if sessions:
            self.runtime_progress_bar.setValue(min(100, 10 + len(sessions) * 10))
            self._set_shell_progress(min(100, 10 + len(sessions) * 10), text="Окна: %p%")
            self.runtime_progress_label.setText(
                "Главное окно отслеживает запущенные GUI и передаёт им выбранный проектный контекст."
            )
        else:
            self.runtime_progress_bar.setValue(0)
            self._set_shell_progress(0, text="Готово: %p%")
            self.runtime_progress_label.setText(
                "Пока нет открытых GUI-окон. Используйте верхнюю командную зону, обзор проекта или поиск команд."
            )

    def _browser_tree_texts(self) -> list[str]:
        rows: list[str] = []

        def visit(item: QtWidgets.QTreeWidgetItem) -> None:
            values = [
                item.text(column).strip()
                for column in range(self.browser_tree.columnCount())
                if item.text(column).strip()
            ]
            if values:
                rows.append(" | ".join(values))
            for child_index in range(item.childCount()):
                visit(item.child(child_index))

        for index in range(self.browser_tree.topLevelItemCount()):
            visit(self.browser_tree.topLevelItem(index))
        return rows

    def operator_visible_audit(self) -> dict[str, object]:
        command_catalog = [
            {
                "label": entry.label,
                "location": entry.location,
                "summary": entry.summary,
                "action_kind": entry.action_kind,
                "action_value": entry.action_value,
            }
            for entry in self.command_entries
        ]
        command_results = {
            query: [
                {
                    "label": entry.label,
                    "location": entry.location,
                    "action_kind": entry.action_kind,
                    "action_value": entry.action_value,
                }
                for entry in rank_shell_command_search_entries(query, self.command_entries)[:8]
            ]
            for query in (
                "дерево проекта",
                "исходные данные",
                "диагностика",
                "Engineering Analysis",
            )
        }
        toolbar_buttons = [
            button.text().strip()
            for button in self.findChildren(QtWidgets.QPushButton)
            if button.text().strip()
        ]
        inspector = {
            "labels": [
                "Раздел:",
                "Поверхность:",
                "Роль:",
                "Источник данных:",
                "Состояние:",
                "Связанный GUI:",
            ],
            "values": {
                "section": self.property_title_value.text(),
                "surface": self.property_runtime_value.text(),
                "role": self.property_role_value.text(),
                "source": self.property_source_value.text(),
                "state": self.property_operator_state_value.text(),
                "gui": self.property_module_value.text(),
            },
            "help_text": self.help_text.toPlainText(),
            "warnings": [
                self.warning_list.item(index).text()
                for index in range(self.warning_list.count())
            ],
        }
        status_strip = {
            "status_text": self.status_label.text(),
            "message_text": self.message_strip_label.text(),
            "progress_format": self.status_progress_bar.format(),
            "progress_value": int(self.status_progress_bar.value()),
            "mode_text": self.mode_status_label.text(),
            "bundle_text": self.bundle_status_label.text(),
        }
        workspace_selector_items = [
            self.workspace_combo.itemText(index)
            for index in range(self.workspace_combo.count())
        ]
        gui_module_selector_items = [
            self.launch_tool_combo.itemText(index)
            for index in range(self.launch_tool_combo.count())
        ]
        browser_rows = self._browser_tree_texts()
        menu_titles = [action.text() for action in self.menuBar().actions()]
        primary_visible_texts: list[str] = [
            *menu_titles,
            *toolbar_buttons,
            *workspace_selector_items,
            *gui_module_selector_items,
            *browser_rows,
            *inspector["labels"],
            *dict(inspector["values"]).values(),
            str(inspector["help_text"]),
            *list(inspector["warnings"]),
            *dict(status_strip).values(),
        ]
        command_visible_texts: list[str] = []
        for entry in command_catalog:
            command_visible_texts.extend(str(value) for value in entry.values())
        for rows in command_results.values():
            for row in rows:
                command_visible_texts.extend(str(value) for value in row.values())
        all_texts = [
            str(text)
            for text in (*primary_visible_texts, *command_visible_texts)
            if str(text).strip()
        ]
        return {
            "menu_titles": menu_titles,
            "toolbar_buttons": toolbar_buttons,
            "workspace_selector_items": workspace_selector_items,
            "gui_module_selector_items": gui_module_selector_items,
            "browser_rows": browser_rows,
            "command_search_catalog": command_catalog,
            "command_search_results": command_results,
            "inspector": inspector,
            "status_strip": status_strip,
            "visible_text_count": len(all_texts),
            "forbidden_labels": list(OPERATOR_FORBIDDEN_LABELS),
            "forbidden_label_hits": forbidden_operator_label_hits(all_texts),
            "service_blocker_hits": service_jargon_hits(
                [str(text) for text in primary_visible_texts if str(text).strip()]
            ),
        }

    def operator_surface_snapshot(self) -> dict[str, object]:
        audit = self.operator_visible_audit()
        return {
            "visible_text_count": audit["visible_text_count"],
            "service_blocker_hits": audit["service_blocker_hits"],
            "forbidden_label_hits": audit["forbidden_label_hits"],
            "toolbar_buttons": audit["toolbar_buttons"],
            "browser_rows": audit["browser_rows"],
        }

    def prove_v38_pipeline_selection_sync(self) -> dict[str, object]:
        original_surface_key = self._selected_surface_key
        original_tool_key = self._selected_tool_key
        rows: list[dict[str, object]] = []
        for surface in self.pipeline_surfaces:
            self._apply_selected_surface(surface.key, announce=False)
            current_item = self.browser_tree.currentItem()
            rows.append(
                {
                    "workspace_id": surface.workspace_id,
                    "surface_key": surface.key,
                    "title": surface.title,
                    "tool_key": surface.tool_key or "",
                    "central_title": self.surface_title.text(),
                    "inspector_title": self.property_title_value.text(),
                    "browser_selection": current_item.text(0) if current_item is not None else "",
                    "synced": (
                        self.surface_title.text() == surface.title
                        and self.property_title_value.text() == surface.title
                        and current_item is not None
                        and current_item.data(0, SURFACE_ROLE) == surface.key
                    ),
                }
            )
        self._apply_selected_surface(
            original_surface_key,
            announce=False,
            selected_tool_key=original_tool_key,
        )
        observed = {str(row["workspace_id"]) for row in rows if row.get("synced") is True}
        required = set(V38_PIPELINE_WORKSPACE_IDS)
        return {
            "required_workspace_ids": list(V38_PIPELINE_WORKSPACE_IDS),
            "observed_workspace_ids": sorted(observed),
            "missing_workspace_ids": sorted(required - observed),
            "rows": rows,
        }

    def _select_browser_item(self, key: str) -> None:
        items = self.browser_tree.findItems(
            "*",
            QtCore.Qt.MatchFlag.MatchWildcard | QtCore.Qt.MatchFlag.MatchRecursive,
            0,
        )
        self.browser_tree.blockSignals(True)
        try:
            for item in items:
                if item.data(0, SURFACE_ROLE) == key:
                    self.browser_tree.setCurrentItem(item)
                    break
        finally:
            self.browser_tree.blockSignals(False)

    def _current_context_payload(self, spec: DesktopShellToolSpec) -> dict[str, object]:
        return {
            "selected_tool_key": spec.key,
            "workflow_stage": spec.workflow_stage or "",
            "active_optimization_mode": self.optimization_mode_combo.currentText().strip(),
            "source_of_truth_role": spec.effective_source_of_truth_role,
            "workspace_role": spec.effective_workspace_role,
            "selected_run_dir": "",
            "selected_artifact": "",
            "selected_scenario": "",
            "project_name": self.project_context.project_name,
            "project_dir": str(self.project_context.project_dir),
            "workspace_dir": str(self.project_context.workspace_dir),
            "repo_root": str(self.project_context.repo_root),
        }

    def _analysis_context_path(self) -> Path:
        return (
            self.project_context.workspace_dir
            / "handoffs"
            / "WS-ANALYSIS"
            / "analysis_context.json"
        ).resolve(strict=False)

    def _read_json_dict(self, path: Path) -> dict[str, object]:
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return {}
        return dict(obj) if isinstance(obj, dict) else {}

    def _resolve_capture_export_manifest_path(self) -> Path | None:
        workspace_dir = self.project_context.workspace_dir
        pointer_candidates = (
            workspace_dir / "exports" / "anim_latest.json",
            workspace_dir / "_pointers" / "anim_latest.json",
        )
        for pointer_path in pointer_candidates:
            if not pointer_path.exists():
                continue
            payload = self._read_json_dict(pointer_path)
            meta = payload.get("meta")
            meta_obj = dict(meta) if isinstance(meta, dict) else {}
            artifact_refs = meta_obj.get("anim_export_contract_artifacts")
            refs_obj = dict(artifact_refs) if isinstance(artifact_refs, dict) else {}
            raw_ref = str(refs_obj.get("capture_export_manifest") or "").strip()
            if not raw_ref:
                continue
            target = Path(raw_ref)
            if not target.is_absolute():
                target = pointer_path.parent / target
            try:
                target = target.resolve(strict=False)
            except Exception:
                pass
            if target.exists():
                return target

        default_path = workspace_dir / "exports" / "capture_export_manifest.json"
        try:
            return default_path.resolve(strict=False)
        except Exception:
            return default_path

    def _resolve_animator_artifact_path(self, artifact_id: str) -> Path | None:
        context_path = self._analysis_context_path()
        if artifact_id == "animator.analysis_context":
            return context_path
        if artifact_id == "animator.animator_link_contract":
            return context_path.with_name("animator_link_contract.json")
        if artifact_id == "animator.capture_export_manifest":
            return self._resolve_capture_export_manifest_path()

        snapshot = load_analysis_context(context_path, repo_root=self.project_context.repo_root)
        if artifact_id == "animator.selected_result_artifact_pointer":
            return snapshot.selected_result_artifact_path
        if artifact_id == "animator.selected_npz_path":
            return snapshot.selected_npz_path
        return None

    def _open_local_artifact_path(self, path: Path | None, *, artifact_label: str) -> bool:
        if path is None:
            self._set_status_message(f"Артефакт не найден: {artifact_label}")
            QtWidgets.QMessageBox.warning(
                self,
                "Артефакт не найден",
                f"{artifact_label}\n\nПуть не указан в frozen HO-008 context.",
            )
            return False
        target = Path(path).expanduser().resolve(strict=False)
        if not target.exists():
            self._set_status_message(f"Артефакт отсутствует: {target}")
            QtWidgets.QMessageBox.warning(
                self,
                "Артефакт отсутствует",
                f"{artifact_label}\n\n{target}",
            )
            return False
        opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(target)))
        if opened:
            self._set_status_message(f"Открыт артефакт: {target}")
            return True
        self._set_status_message(f"Не удалось открыть артефакт: {target}")
        QtWidgets.QMessageBox.warning(
            self,
            "Не удалось открыть артефакт",
            f"{artifact_label}\n\n{target}",
        )
        return False

    def open_shell_artifact(self, artifact_id: str) -> bool:
        labels = {
            "animator.analysis_context": "HO-008 analysis_context.json",
            "animator.animator_link_contract": "HO-008 animator_link_contract.json",
            "animator.selected_result_artifact_pointer": "selected result artifact pointer",
            "animator.selected_npz_path": "selected animation NPZ",
            "animator.capture_export_manifest": "HO-010 capture_export_manifest.json",
        }
        artifact_label = labels.get(str(artifact_id), str(artifact_id))
        try:
            target = self._resolve_animator_artifact_path(str(artifact_id))
        except Exception as exc:
            self._set_status_message(f"Не удалось прочитать HO-008 context: {exc}")
            QtWidgets.QMessageBox.warning(
                self,
                "Не удалось прочитать HO-008 context",
                f"{artifact_label}\n\n{exc}",
            )
            return False
        return self._open_local_artifact_path(target, artifact_label=artifact_label)

    def open_tool(self, key: str) -> bool:
        spec = self.spec_by_key.get(key)
        if spec is None:
            self._set_status_message(f"Неизвестный ключ окна: {key}")
            return False
        self._apply_selected_tool(key)
        try:
            session = self.coexistence.open_tool(
                spec,
                context_payload=self._current_context_payload(spec),
            )
        except Exception as exc:
            self._set_status_message(f"Не удалось открыть {spec.title}: {exc}")
            QtWidgets.QMessageBox.warning(
                self,
                "Не удалось открыть окно",
                f"{spec.title}\n\n{exc}",
            )
            return False
        self._set_status_message(f"Открыто окно: {spec.title}")
        self._refresh_runtime_table()
        return True

    def open_selected_workspace(self) -> None:
        key = self.workspace_combo.currentData()
        if isinstance(key, str) and key:
            self._select_surface(key)

    def open_selected_launch_tool(self) -> None:
        key = self.launch_tool_combo.currentData()
        if isinstance(key, str) and key:
            self.open_tool(key)

    def stop_selected_tool(self) -> None:
        key = self._selected_tool_key
        if not key:
            return
        if self.coexistence.stop_tool(key):
            title = self.spec_by_key.get(key).title if key in self.spec_by_key else key
            self._set_status_message(f"Остановлено окно: {title}")
        else:
            self._set_status_message("Для выбранного окна нет активного управляемого процесса.")
        self._refresh_runtime_table()

    def _open_startup_tools(self) -> None:
        for key in self._startup_tool_keys:
            self.open_tool(key)

    def _show_legacy_shell_note(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Резервное старое окно",
            "Старое окно сохранено только как резервный отладочный маршрут. "
            "Основная работа должна идти через это главное desktop-окно.",
        )

    def _show_about_dialog(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "О рабочем месте",
            "PneumoApp\n\n"
            "Главное окно держит меню, поиск команд, дерево проекта, инспектор, диагностику и запуск GUI-разделов.\n"
            "Специализированные окна Desktop Animator, Compare Viewer и Desktop Mnemo остаются отдельными окнами.",
        )

    def _on_workspace_changed(self, index: int) -> None:
        key = self.workspace_combo.itemData(index)
        if isinstance(key, str) and key:
            self._select_surface(key)

    def _on_launch_tool_changed(self, index: int) -> None:
        key = self.launch_tool_combo.itemData(index)
        if isinstance(key, str) and key:
            self._select_workspace(key)

    def _select_workspace(self, key: str) -> None:
        self._apply_selected_tool(key)
        index = self.workspace_combo.findData(self._selected_surface_key)
        if index >= 0 and self.workspace_combo.currentIndex() != index:
            self.workspace_combo.blockSignals(True)
            self.workspace_combo.setCurrentIndex(index)
            self.workspace_combo.blockSignals(False)

    def _select_surface(self, key: str) -> None:
        self._apply_selected_surface(key)
        index = self.workspace_combo.findData(key)
        if index >= 0 and self.workspace_combo.currentIndex() != index:
            self.workspace_combo.blockSignals(True)
            self.workspace_combo.setCurrentIndex(index)
            self.workspace_combo.blockSignals(False)

    def _on_browser_selection_changed(self) -> None:
        item = self.browser_tree.currentItem()
        if item is None:
            return
        surface_key = item.data(0, SURFACE_ROLE)
        if isinstance(surface_key, str) and surface_key in self.pipeline_surface_by_key:
            self._select_surface(surface_key)

    def _on_browser_item_activated(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        item_kind = item.data(0, ITEM_KIND_ROLE)
        tool_key = item.data(0, TOOL_ROLE)
        surface_key = item.data(0, SURFACE_ROLE)
        if item_kind == "tool" and isinstance(tool_key, str) and tool_key:
            self.open_tool(tool_key)
            return
        if isinstance(surface_key, str) and surface_key in self.pipeline_surface_by_key:
            self._select_surface(surface_key)

    def _on_workflow_item_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        key = item.data(SURFACE_ROLE)
        if isinstance(key, str) and key:
            self._select_surface(key)

    def _on_search_result_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        self._activate_search_item(item)

    def _activate_primary_search_result(self) -> None:
        if self.search_results_list.count() <= 0:
            return
        item = self.search_results_list.item(0)
        if item is not None:
            self._activate_search_item(item)

    def _activate_search_item(self, item: QtWidgets.QListWidgetItem) -> None:
        action_kind = item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        action_value = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if action_kind == "home" or action_value == "home":
            self.command_search_edit.clear()
            self._select_surface("ws_project")
            self._set_status_message("Открыта панель проекта.")
            return
        if action_kind == "focus" and action_value == "project_tree":
            self.command_search_edit.clear()
            self.central_stack.setCurrentWidget(self.overview_page)
            self._focus_project_tree()
            return
        if action_kind == "pipeline_surface" and isinstance(action_value, str):
            self.command_search_edit.clear()
            self._select_surface(action_value)
            return
        if action_kind == "tool" and isinstance(action_value, str):
            self.open_tool(action_value)
            return
        if action_kind == "open_artifact" and isinstance(action_value, str):
            self.open_shell_artifact(action_value)

    def _install_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self._focus_command_search)
        QtGui.QShortcut(QtGui.QKeySequence("F7"), self, activated=lambda: self.open_tool("desktop_diagnostics_center"))
        QtGui.QShortcut(QtGui.QKeySequence("F8"), self, activated=lambda: self.open_tool("desktop_animator"))
        QtGui.QShortcut(QtGui.QKeySequence("Shift+F5"), self, activated=self.stop_selected_tool)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Tab"), self, activated=self._select_next_workspace)
        QtGui.QShortcut(QtGui.QKeySequence("F6"), self, activated=lambda: self._move_focus(1))
        QtGui.QShortcut(QtGui.QKeySequence("Shift+F6"), self, activated=lambda: self._move_focus(-1))

        self._focus_regions = [
            self.command_search_edit,
            self.browser_tree,
            self.workflow_list,
            self.inspector_tabs,
            self.runtime_table,
            self.message_strip_label,
        ]

    def _move_focus(self, delta: int) -> None:
        if not self._focus_regions:
            return
        focus_widget = self.focusWidget()
        index = self._focus_regions.index(focus_widget) if focus_widget in self._focus_regions else -1
        next_index = (index + delta) % len(self._focus_regions)
        self._focus_regions[next_index].setFocus()

    def _select_next_workspace(self) -> None:
        count = self.workspace_combo.count()
        if count <= 0:
            return
        self.workspace_combo.setCurrentIndex((self.workspace_combo.currentIndex() + 1) % count)

    def _start_polling(self) -> None:
        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.timeout.connect(self._poll_managed_windows)
        self.poll_timer.start(1200)

    def _poll_managed_windows(self) -> None:
        finished = self.coexistence.poll()
        if finished:
            names = ", ".join(session.spec.title for session in finished)
            self._set_status_message(f"Обновлён статус управляемых окон: {names}")
        self._refresh_runtime_table()

    def _restore_layout(self) -> None:
        geometry = self.settings.value("layout/geometry") or self.settings.value("geometry")
        state = self.settings.value("layout/window_state") or self.settings.value("window_state")
        last_surface_key = str(self.settings.value("layout/last_surface_key") or "").strip()
        last_key = str(self.settings.value("layout/last_workspace_key") or "").strip()
        if last_surface_key in self.pipeline_surface_by_key:
            self._selected_surface_key = last_surface_key
            surface = self.pipeline_surface_by_key[last_surface_key]
            if surface.tool_key:
                self._selected_tool_key = surface.tool_key
        elif last_key in self.spec_by_key:
            self._selected_tool_key = last_key
            self._selected_surface_key = default_surface_key_for_tool(last_key)
        mode = str(self.settings.value("layout/optimization_mode") or "").strip()
        if mode:
            index = self.optimization_mode_combo.findText(mode)
            if index >= 0:
                self.optimization_mode_combo.setCurrentIndex(index)
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)
        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)
        if hasattr(self, "status_label"):
            self._set_status_message("Раскладка dock-панелей восстановлена.")

    def _save_layout(self) -> None:
        geometry = self.saveGeometry()
        state = self.saveState()
        self.settings.setValue("layout/geometry", geometry)
        self.settings.setValue("layout/window_state", state)
        self.settings.setValue("layout/last_workspace_key", self._selected_tool_key)
        self.settings.setValue("layout/last_surface_key", self._selected_surface_key)
        self.settings.setValue("layout/optimization_mode", self.optimization_mode_combo.currentText().strip())
        self.settings.setValue("geometry", geometry)
        self.settings.setValue("window_state", state)
        self.settings.sync()
        if hasattr(self, "status_label"):
            self._set_status_message("Раскладка панелей сохранена.")

    def _reset_layout(self) -> None:
        for dock in (self.browser_dock, self.inspector_dock, self.runtime_dock):
            dock.setFloating(False)
            dock.show()
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.browser_dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.runtime_dock)
        self.resize(1640, 980)
        self._set_status_message("Раскладка сброшена к базовой: дерево слева, инспектор справа, ход выполнения снизу.")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._save_layout()
        super().closeEvent(event)


def main(*, startup_tool_keys: tuple[str, ...] = ()) -> int:
    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication([Path(sys.argv[0]).name, *sys.argv[1:]])
        app.setApplicationName("PneumoApp Desktop")
        app.setOrganizationName("PneumoApp")
    window = DesktopQtMainShell(startup_tool_keys=startup_tool_keys)
    window.show()
    window.raise_()
    window.activateWindow()
    if not owns_app:
        return 0
    return int(app.exec())
