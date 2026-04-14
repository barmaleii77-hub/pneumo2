from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_qt_shell.coexistence import DesktopShellCoexistenceManager
from pneumo_solver_ui.desktop_shell.command_search import (
    ShellCommandSearchEntry,
    build_shell_command_search_entries,
    rank_shell_command_search_entries,
)
from pneumo_solver_ui.desktop_shell.contracts import DesktopShellToolSpec
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.release_info import get_release


MAIN_ROUTE_KEYS = (
    "desktop_input_editor",
    "desktop_ring_editor",
    "test_center",
    "desktop_optimizer_center",
    "desktop_results_center",
    "desktop_diagnostics_center",
)


def _migration_label(spec: DesktopShellToolSpec) -> str:
    status = spec.effective_migration_status
    if status == "managed_external":
        return "Управляемое внешнее окно"
    if status == "in_development":
        return "В разработке"
    return "Нативный маршрут"


def _runtime_label(spec: DesktopShellToolSpec) -> str:
    kind = spec.effective_runtime_kind
    if kind == "tk":
        return "Tk"
    if kind == "qt":
        return "Qt"
    return "Процесс"


class DesktopQtMainShell(QtWidgets.QMainWindow):
    def __init__(self, *, startup_tool_keys: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.specs = build_desktop_shell_specs()
        self.spec_by_key = {spec.key: spec for spec in self.specs}
        self.command_entries = build_shell_command_search_entries(self.specs)
        self.settings = QtCore.QSettings("PneumoApp", "DesktopQtMainShell")
        self.coexistence = DesktopShellCoexistenceManager()
        self._startup_tool_keys = startup_tool_keys
        self._selected_tool_key = startup_tool_keys[0] if startup_tool_keys else "desktop_input_editor"
        self._selected_search_entries: list[ShellCommandSearchEntry] = []
        self._focus_regions: list[QtWidgets.QWidget] = []

        self._configure_window()
        self._build_menu()
        self._build_command_toolbar()
        self._build_browser_dock()
        self._build_inspector_dock()
        self._build_runtime_dock()
        self._build_central_surface()
        self._build_status_bar()
        self._restore_layout()
        self._populate_workspace_switcher()
        self._populate_browser_tree()
        self._refresh_search_results()
        self._apply_selected_tool(self._selected_tool_key, announce=False)
        self._install_shortcuts()
        self._start_polling()
        QtCore.QTimer.singleShot(0, self._open_startup_tools)

    def _configure_window(self) -> None:
        release = get_release()
        self.setWindowTitle(f"PneumoApp - Qt shell инженера ({release})")
        self.setObjectName("DesktopQtMainShell")
        self.resize(1640, 980)
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.GroupedDragging
        )

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        workspace_menu = menubar.addMenu("Рабочее пространство")
        for key in MAIN_ROUTE_KEYS:
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            action = workspace_menu.addAction(spec.title)
            action.triggered.connect(lambda _checked=False, item_key=key: self._select_workspace(item_key))

        window_menu = menubar.addMenu("Окно")
        for key in ("compare_viewer", "desktop_animator", "desktop_mnemo"):
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            action = window_menu.addAction(spec.title)
            action.triggered.connect(lambda _checked=False, item_key=key: self.open_tool(item_key))

        tools_menu = menubar.addMenu("Инструменты")
        diag_action = tools_menu.addAction("Собрать диагностику")
        diag_action.triggered.connect(lambda: self.open_tool("desktop_diagnostics_center"))
        legacy_action = tools_menu.addAction("Открыть legacy Tk-shell")
        legacy_action.triggered.connect(self._show_legacy_shell_note)

        help_menu = menubar.addMenu("Справка")
        help_action = help_menu.addAction("О текущем Qt-shell")
        help_action.triggered.connect(self._show_about_dialog)

    def _build_command_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Командная зона", self)
        toolbar.setObjectName("DesktopQtShellToolbar")
        toolbar.setMovable(False)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addWidget(QtWidgets.QLabel("Рабочее пространство:"))
        self.workspace_combo = QtWidgets.QComboBox(toolbar)
        self.workspace_combo.currentIndexChanged.connect(self._on_workspace_changed)
        toolbar.addWidget(self.workspace_combo)

        self.open_workspace_button = QtWidgets.QPushButton("Открыть рабочее пространство", toolbar)
        self.open_workspace_button.clicked.connect(self.open_selected_workspace)
        toolbar.addWidget(self.open_workspace_button)

        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel("Поиск команд:"))
        self.command_search_edit = QtWidgets.QLineEdit(toolbar)
        self.command_search_edit.setPlaceholderText(
            "Команды, экраны, тесты, сценарии, bundle, runs, artifacts"
        )
        self.command_search_edit.textChanged.connect(self._refresh_search_results)
        self.command_search_edit.returnPressed.connect(self._activate_primary_search_result)
        toolbar.addWidget(self.command_search_edit)

        toolbar.addSeparator()

        self.diagnostics_button = QtWidgets.QPushButton("Собрать диагностику", toolbar)
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
        self.property_migration_value = QtWidgets.QLabel(properties_page)
        self.property_module_value = QtWidgets.QLabel(properties_page)
        self.property_module_value.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        properties_layout.addRow("Окно:", self.property_title_value)
        properties_layout.addRow("Toolkit:", self.property_runtime_value)
        properties_layout.addRow("Роль:", self.property_role_value)
        properties_layout.addRow("Источник истины:", self.property_source_value)
        properties_layout.addRow("Состояние миграции:", self.property_migration_value)
        properties_layout.addRow("Standalone module:", self.property_module_value)
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
            "Длительные операции пока не встроены в native workspace. Здесь отражается переходный managed-external слой.",
            runtime_widget,
        )
        self.runtime_progress_label.setWordWrap(True)
        runtime_layout.addWidget(self.runtime_progress_label)

        self.runtime_progress_bar = QtWidgets.QProgressBar(runtime_widget)
        self.runtime_progress_bar.setRange(0, 100)
        self.runtime_progress_bar.setValue(0)
        self.runtime_progress_bar.setFormat("Переходный shell-phase: %p%")
        runtime_layout.addWidget(self.runtime_progress_bar)

        self.runtime_table = QtWidgets.QTreeWidget(runtime_widget)
        self.runtime_table.setHeaderLabels(("Окно", "Состояние", "Toolkit", "Процесс"))
        runtime_layout.addWidget(self.runtime_table)

        self.runtime_dock.setWidget(runtime_widget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.runtime_dock)

    def _build_central_surface(self) -> None:
        central = QtWidgets.QWidget(self)
        central_layout = QtWidgets.QVBoxLayout(central)

        self.banner_label = QtWidgets.QLabel(
            "Qt-shell уже стал главным desktop entrypoint. Tk-центры пока открываются как управляемые внешние окна, без потери функциональности и без попытки хостить Tk внутри Qt.",
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

        session_box = QtWidgets.QGroupBox("Управляемые внешние окна", self.overview_page)
        session_layout = QtWidgets.QVBoxLayout(session_box)
        self.session_summary_label = QtWidgets.QLabel(session_box)
        self.session_summary_label.setWordWrap(True)
        session_layout.addWidget(self.session_summary_label)
        self.open_tool_button = QtWidgets.QPushButton("Открыть выбранное окно", session_box)
        self.open_tool_button.clicked.connect(self.open_selected_workspace)
        session_layout.addWidget(self.open_tool_button)
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
        self.mode_status_label = QtWidgets.QLabel(status)
        self.bundle_status_label = QtWidgets.QLabel(
            "Последний архив диагностики: откройте центр диагностики",
            status,
        )
        status.addWidget(self.status_label, 1)
        status.addPermanentWidget(self.mode_status_label)
        status.addPermanentWidget(self.bundle_status_label)
        self._refresh_status_bar()

    def _populate_workspace_switcher(self) -> None:
        self.workspace_combo.blockSignals(True)
        self.workspace_combo.clear()
        for key in MAIN_ROUTE_KEYS:
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            self.workspace_combo.addItem(spec.title, userData=key)
        index = max(0, self.workspace_combo.findData(self._selected_tool_key))
        self.workspace_combo.setCurrentIndex(index)
        self.workspace_combo.blockSignals(False)

    def _populate_browser_tree(self) -> None:
        self.browser_tree.clear()
        grouped_specs = {
            "Основной маршрут": [self.spec_by_key[key] for key in MAIN_ROUTE_KEYS if key in self.spec_by_key],
            "Справочники и служебные центры": [
                spec for spec in self.specs if spec.entry_kind == "tool"
            ],
            "Анализ и специализированные окна": [
                spec
                for spec in self.specs
                if spec.key in ("compare_viewer", "desktop_animator", "desktop_mnemo")
            ],
        }
        for group_title, group_specs in grouped_specs.items():
            root_item = QtWidgets.QTreeWidgetItem((group_title, ""))
            for spec in group_specs:
                item = QtWidgets.QTreeWidgetItem(
                    (
                        spec.title,
                        _migration_label(spec),
                    )
                )
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, spec.key)
                root_item.addChild(item)
            self.browser_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)

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
            "Контракт: baseline не выбран | objective stack не задан | "
            f"hard gate не задан | режим: {active_mode}"
        )
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        self.mode_status_label.setText(
            f"Активный режим: {self.optimization_mode_combo.currentText().strip()}"
        )

    def _apply_selected_tool(self, key: str, *, announce: bool = True) -> None:
        spec = self.spec_by_key.get(key)
        if spec is None:
            return
        self._selected_tool_key = key
        self.surface_title.setText(spec.title)
        self.surface_meta.setText(
            f"{spec.menu_section} -> {spec.nav_section} | Toolkit: {_runtime_label(spec)} | {_migration_label(spec)}"
        )
        self.surface_description.setText(spec.details or spec.description)
        self.session_summary_label.setText(
            "Tk-центры временно запускаются как управляемые внешние окна. "
            "Qt-переписывание идёт волнами: shell/platform -> setup -> ring/test suite -> baseline/optimization -> analysis/diagnostics."
        )
        self._refresh_workflow_list()
        self._refresh_inspector(spec)
        self._refresh_runtime_table()
        self._select_browser_item(key)
        if announce:
            self.status_label.setText(f"Выбрано рабочее окно: {spec.title}")

    def _refresh_workflow_list(self) -> None:
        self.workflow_list.clear()
        for index, key in enumerate(MAIN_ROUTE_KEYS, start=1):
            spec = self.spec_by_key.get(key)
            if spec is None:
                continue
            line = f"{index}. {spec.title} — {_migration_label(spec)}"
            item = QtWidgets.QListWidgetItem(line)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            if key == self._selected_tool_key:
                item.setSelected(True)
            self.workflow_list.addItem(item)

    def _refresh_inspector(self, spec: DesktopShellToolSpec) -> None:
        self.property_title_value.setText(spec.title)
        self.property_runtime_value.setText(_runtime_label(spec))
        self.property_role_value.setText(spec.effective_workspace_role)
        self.property_source_value.setText(spec.effective_source_of_truth_role)
        self.property_migration_value.setText(_migration_label(spec))
        self.property_module_value.setText(spec.standalone_module or "n/a")

        self.help_text.setPlainText(
            "\n\n".join(
                [
                    f"Что это: {spec.title}",
                    f"Короткая подсказка: {spec.effective_tooltip}",
                    f"Развёрнутое описание: {spec.effective_help_topic}",
                    f"Где находится: {spec.menu_section} -> {spec.title}",
                    f"Что откроется: standalone module {spec.standalone_module or 'не задан'}",
                    f"Источник истины: {spec.effective_source_of_truth_role}",
                ]
            )
        )

        warnings: list[str] = []
        if spec.effective_migration_status == "managed_external":
            warnings.append(
                "Это окно пока не переписано в Qt-workspace. Оно откроется как управляемое внешнее окно без встраивания Tk в shell."
            )
        if spec.key == "desktop_animator":
            warnings.append(
                "Аниматор обязан показывать режимы: Расчётно подтверждено / По исходным данным / Условно по неполным данным."
            )
        if spec.key == "desktop_optimizer_center":
            warnings.append(
                "Для оптимизации разрешён только один активный режим запуска. Два равноправных launch controls запрещены."
            )
        if spec.key == "desktop_ring_editor":
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
            self.runtime_progress_label.setText(
                "Qt-shell отслеживает жизненный цикл внешних окон и передаёт им launch context через shell handoff."
            )
        else:
            self.runtime_progress_bar.setValue(0)
            self.runtime_progress_label.setText(
                "Пока нет открытых управляемых окон. Используйте верхнюю командную зону, обзор проекта или поиск команд."
            )

    def _select_browser_item(self, key: str) -> None:
        items = self.browser_tree.findItems(
            "*",
            QtCore.Qt.MatchFlag.MatchWildcard | QtCore.Qt.MatchFlag.MatchRecursive,
            0,
        )
        self.browser_tree.blockSignals(True)
        try:
            for item in items:
                if item.data(0, QtCore.Qt.ItemDataRole.UserRole) == key:
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
        }

    def open_tool(self, key: str) -> bool:
        spec = self.spec_by_key.get(key)
        if spec is None:
            self.status_label.setText(f"Неизвестный ключ окна: {key}")
            return False
        self._apply_selected_tool(key)
        try:
            session = self.coexistence.open_tool(
                spec,
                context_payload=self._current_context_payload(spec),
            )
        except Exception as exc:
            self.status_label.setText(f"Не удалось открыть {spec.title}: {exc}")
            QtWidgets.QMessageBox.warning(
                self,
                "Не удалось открыть окно",
                f"{spec.title}\n\n{exc}",
            )
            return False
        self.status_label.setText(
            f"Открыто окно: {spec.title} ({session.runtime_label}, PID {session.pid or '—'})"
        )
        self._refresh_runtime_table()
        return True

    def open_selected_workspace(self) -> None:
        key = self.workspace_combo.currentData()
        if isinstance(key, str) and key:
            self.open_tool(key)

    def stop_selected_tool(self) -> None:
        key = self._selected_tool_key
        if not key:
            return
        if self.coexistence.stop_tool(key):
            title = self.spec_by_key.get(key).title if key in self.spec_by_key else key
            self.status_label.setText(f"Остановлено окно: {title}")
        else:
            self.status_label.setText("Для выбранного окна нет активного управляемого процесса.")
        self._refresh_runtime_table()

    def _open_startup_tools(self) -> None:
        for key in self._startup_tool_keys:
            self.open_tool(key)

    def _show_legacy_shell_note(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Legacy Tk-shell",
            "Старый Tk-shell сохранён как fallback/debug route. "
            "Qt-shell теперь является основным desktop entrypoint, а Tk-центры временно живут как управляемые внешние окна.",
        )

    def _show_about_dialog(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "О текущем Qt-shell",
            "PneumoApp Qt-shell\n\n"
            "Фаза A: новый shell-platform слой на QMainWindow + QDockWidget.\n"
            "Текущие Tk-центры открываются как managed-external workspaces без попытки встраивать Tk в Qt.\n"
            "Специализированные окна Desktop Animator, Compare Viewer и Desktop Mnemo остаются отдельными native windows.",
        )

    def _on_workspace_changed(self, index: int) -> None:
        key = self.workspace_combo.itemData(index)
        if isinstance(key, str) and key:
            self._select_workspace(key)

    def _select_workspace(self, key: str) -> None:
        self._apply_selected_tool(key)
        index = self.workspace_combo.findData(key)
        if index >= 0 and self.workspace_combo.currentIndex() != index:
            self.workspace_combo.blockSignals(True)
            self.workspace_combo.setCurrentIndex(index)
            self.workspace_combo.blockSignals(False)

    def _on_browser_selection_changed(self) -> None:
        item = self.browser_tree.currentItem()
        if item is None:
            return
        key = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(key, str) and key:
            self._select_workspace(key)

    def _on_browser_item_activated(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        key = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(key, str) and key:
            self.open_tool(key)

    def _on_workflow_item_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        key = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(key, str) and key:
            self.open_tool(key)

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
        if action_kind == "home":
            self.command_search_edit.clear()
            self.central_stack.setCurrentWidget(self.overview_page)
            self.status_label.setText("Открыт обзор рабочего места.")
            return
        if action_kind == "tool" and isinstance(action_value, str):
            self.open_tool(action_value)

    def _install_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self.command_search_edit.setFocus)
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
            self.status_label.setText(f"Обновлён статус управляемых окон: {names}")
        self._refresh_runtime_table()

    def _restore_layout(self) -> None:
        geometry = self.settings.value("geometry")
        state = self.settings.value("window_state")
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)
        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)

    def _save_layout(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._save_layout()
        super().closeEvent(event)


def main(*, startup_tool_keys: tuple[str, ...] = ()) -> int:
    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication([Path(sys.argv[0]).name, *sys.argv[1:]])
        app.setApplicationName("PneumoApp Qt Shell")
        app.setOrganizationName("PneumoApp")
    window = DesktopQtMainShell(startup_tool_keys=startup_tool_keys)
    window.show()
    window.raise_()
    window.activateWindow()
    if not owns_app:
        return 0
    return int(app.exec())
