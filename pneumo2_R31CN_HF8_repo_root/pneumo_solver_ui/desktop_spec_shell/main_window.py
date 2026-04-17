# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import traceback
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from pneumo_solver_ui.desktop_shell.external_launch import repo_root as legacy_repo_root
from pneumo_solver_ui.desktop_shell.external_launch import spawn_module

from .catalogs import (
    docking_rules_by_panel,
    f6_region_order,
    get_tooltip,
    get_ui_element,
    keyboard_shortcuts_by_name,
    ui_state_palette,
)
from .contracts import DesktopHelpTopicSpec, DesktopShellCommandSpec, DesktopWorkspaceSpec
from .diagnostics_panel import DiagnosticsWorkspacePage
from .help_registry import build_help_registry
from .overview_state import OverviewCardState, build_overview_snapshot
from .registry import (
    build_command_map,
    build_shell_commands,
    build_shell_workspaces,
    build_workspace_map,
)
from .search import build_search_entries, search_command_palette
from .workspace_pages import (
    BaselineWorkspacePage,
    ControlHubWorkspacePage,
    InputWorkspacePage,
    OptimizationWorkspacePage,
    ResultsWorkspacePage,
)

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = "GUI_SPEC_SHELL"


DEFAULT_PINNED_COMMAND_IDS = (
    "workspace.input_data.open",
    "workspace.ring_editor.open",
    "workspace.test_matrix.open",
    "workspace.baseline_run.open",
    "workspace.optimization.open",
    "workspace.results_analysis.open",
    "workspace.animation.open",
    "workspace.diagnostics.open",
)

DEFAULT_SHELL_STATE_RELATIVE_PATH = Path("pneumo_solver_ui") / "workspace" / "desktop_spec_shell_settings.ini"
STARTUP_WORKSPACE_ENV = "PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE"

_COLOR_BY_TOKEN = {
    "граница_контрола": "#d9e2ec",
    "граница_выделения": "#4c9aff",
    "граница_предупреждения": "#d9822b",
    "граница_ошибки": "#cc4b37",
    "рамка_фокуса": "#1f6feb",
    "фон_рабочей_поверхности": "#ffffff",
    "фон_вторичной_панели": "#f4f7fb",
    "фон_успеха_ослабленный": "#e8f7ee",
    "фон_предупреждения_ослабленный": "#fff4e5",
    "фон_ошибки_ослабленный": "#fdecea",
    "фон_отключённый": "#f0f2f5",
    "акцент_ослабленный": "#eef5ff",
    "текст_основной": "#16202a",
    "текст_вторичный": "#5b6672",
}


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _apply_element_contract(widget: QtWidgets.QWidget, element_id: str) -> None:
    element = get_ui_element(element_id)
    if element is None:
        return
    widget.setObjectName(element.automation_id or element.element_id)
    widget.setAccessibleName(element.title)
    widget.setAccessibleDescription(element.purpose or element.title)
    tooltip = get_tooltip(element.tooltip_id)
    if tooltip is not None and tooltip.text:
        widget.setToolTip(tooltip.text)
        widget.setWhatsThis(tooltip.rule)
    if element.hotkey and isinstance(widget, QtWidgets.QPushButton):
        try:
            widget.setShortcut(QtGui.QKeySequence(element.hotkey))
        except Exception:
            pass


def _default_shell_state_path(repo_root: Path) -> Path:
    override = str(os.environ.get("PNEUMO_GUI_SPEC_SHELL_STATE_PATH") or "").strip()
    if override:
        return Path(override)
    return Path(repo_root) / DEFAULT_SHELL_STATE_RELATIVE_PATH


def _startup_workspace_id(
    settings: QtCore.QSettings,
    workspace_by_id: dict[str, DesktopWorkspaceSpec],
) -> str:
    requested_workspace_id = str(os.environ.get(STARTUP_WORKSPACE_ENV) or "").strip()
    if requested_workspace_id in workspace_by_id:
        return requested_workspace_id
    restored_workspace_id = str(
        settings.value("window/last_workspace", "overview") or "overview"
    ).strip()
    return restored_workspace_id if restored_workspace_id in workspace_by_id else "overview"


class InspectorPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title_label = QtWidgets.QLabel("Контекст и provenance")
        title_font = self.title_label.font()
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.summary_label = QtWidgets.QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.why_label = QtWidgets.QLabel("")
        self.why_label.setWordWrap(True)
        layout.addWidget(self.why_label)

        self.source_label = QtWidgets.QLabel("")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        self.units_label = QtWidgets.QLabel("")
        self.units_label.setWordWrap(True)
        layout.addWidget(self.units_label)

        self.next_step_label = QtWidgets.QLabel("")
        self.next_step_label.setWordWrap(True)
        layout.addWidget(self.next_step_label)

        self.hard_gate_label = QtWidgets.QLabel("")
        self.hard_gate_label.setWordWrap(True)
        layout.addWidget(self.hard_gate_label)

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        self.graphics_label = QtWidgets.QLabel("")
        self.graphics_label.setWordWrap(True)
        layout.addWidget(self.graphics_label)

        self.route_label = QtWidgets.QLabel("")
        self.route_label.setWordWrap(True)
        layout.addWidget(self.route_label)
        layout.addStretch(1)

    def show_topic(
        self,
        topic: DesktopHelpTopicSpec,
        *,
        route_label: str = "",
        command_status: str = "",
    ) -> None:
        self.title_label.setText(topic.title)
        summary_text = topic.summary
        if topic.tooltip_text:
            summary_text = f"{summary_text}\nПодсказка: {topic.tooltip_text}"
        self.summary_label.setText(summary_text)
        self.why_label.setText(f"Почему это важно: {topic.why_it_matters}" if topic.why_it_matters else "")
        self.source_label.setText(f"Источник истины: {topic.source_of_truth}")
        self.units_label.setText(f"Единицы и microcopy: {topic.units_policy}")
        self.next_step_label.setText(f"Следующий шаг: {topic.next_step}")
        self.hard_gate_label.setText(f"Hard gate: {topic.hard_gate}")
        self.result_label.setText(
            f"Где виден результат: {topic.result_location}" if topic.result_location else ""
        )
        graphics_text = topic.graphics_policy
        if command_status:
            graphics_text = f"{graphics_text}\nСтатус surface: {command_status}"
        self.graphics_label.setText(f"Graphics honesty: {graphics_text}")
        self.route_label.setText(f"Маршрут: {route_label}" if route_label else "")


class OverviewPage(QtWidgets.QWidget):
    def __init__(
        self,
        repo_root: Path,
        on_command: Callable[[str], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo_root = repo_root
        self.on_command = on_command

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("Обзор проекта")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Shell удерживает последовательный маршрут: исходные данные -> сценарии -> набор испытаний -> baseline -> оптимизация -> анализ -> анимация -> диагностика."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.cards_grid = QtWidgets.QGridLayout()
        self.cards_grid.setHorizontalSpacing(14)
        self.cards_grid.setVerticalSpacing(14)
        layout.addLayout(self.cards_grid)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_view()

    def _render_card(self, index: int, card: OverviewCardState) -> None:
        box = QtWidgets.QGroupBox(card.title)
        box_layout = QtWidgets.QVBoxLayout(box)
        value = QtWidgets.QLabel(card.value)
        value_font = value.font()
        value_font.setBold(True)
        value_font.setPointSize(value_font.pointSize() + 1)
        value.setFont(value_font)
        value.setWordWrap(True)
        detail = QtWidgets.QLabel(card.detail)
        detail.setWordWrap(True)
        button = QtWidgets.QPushButton("Открыть")
        button.clicked.connect(
            lambda _checked=False, cid=card.command_id: self.on_command(cid)
        )
        box_layout.addWidget(value)
        box_layout.addWidget(detail)
        box_layout.addStretch(1)
        box_layout.addWidget(button)
        self.cards_grid.addWidget(box, index // 2, index % 2)

    def refresh_view(self) -> None:
        snapshot = build_overview_snapshot(self.repo_root)
        _clear_layout(self.cards_grid)
        for index, card in enumerate(snapshot.cards):
            self._render_card(index, card)


class DesktopGuiSpecMainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.repo_root = legacy_repo_root()
        self._settings = QtCore.QSettings(
            str(_default_shell_state_path(self.repo_root)),
            QtCore.QSettings.IniFormat,
        )
        self.workspaces = build_shell_workspaces()
        self.workspace_by_id = build_workspace_map()
        self.commands = build_shell_commands()
        self.command_by_id = build_command_map()
        self.help_topics = build_help_registry()
        self.search_entries = build_search_entries(self.workspaces, self.commands)
        self._keyboard_shortcut_by_name = keyboard_shortcuts_by_name()
        self._f6_region_order = f6_region_order()
        self._dock_rules_by_panel = docking_rules_by_panel()
        self._ui_state_palette = ui_state_palette()
        self.recent_command_ids: deque[str] = deque(maxlen=10)
        self._search_ids_by_index: list[str] = []
        self._page_index_by_workspace_id: dict[str, int] = {}
        self._page_widget_by_workspace_id: dict[str, QtWidgets.QWidget] = {}
        self._dock_widget_by_panel: dict[str, QtWidgets.QDockWidget] = {}
        self._shortcut_objects: list[QtGui.QShortcut] = []
        self._primary_command_id: str | None = None
        self._current_workspace_id = "overview"
        self._active_shell_region = "верхняя_командная_панель"

        self.setWindowTitle(f"PneumoApp Desktop Shell - GUI-spec ({RELEASE})")
        self.resize(1680, 980)
        self.setMinimumSize(1320, 840)
        self._build_ui()
        self._populate_workspaces()
        self._populate_pinned_actions()
        self._apply_shell_shortcuts()
        self._restore_window_state()
        self.open_workspace(_startup_workspace_id(self._settings, self.workspace_by_id))

    def _build_ui(self) -> None:
        self._build_menu()
        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(8, 8, 8, 0)
        central_layout.setSpacing(8)

        header = QtWidgets.QFrame()
        header.setFrameShape(QtWidgets.QFrame.StyledPanel)
        header_layout = QtWidgets.QVBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(8)

        row1 = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("PneumoApp Desktop Shell")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        row1.addWidget(title)
        self.project_label = QtWidgets.QLabel(str(self.repo_root))
        self.project_label.setStyleSheet("color: #576574;")
        row1.addWidget(self.project_label, 1)
        self.workspace_badge = QtWidgets.QLabel("Workspace: Обзор")
        row1.addWidget(self.workspace_badge)
        header_layout.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        self.command_search = QtWidgets.QComboBox()
        self.command_search.setEditable(True)
        self.command_search.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.command_search.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.command_search.setMinimumContentsLength(52)
        self.command_search.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.command_search.lineEdit().setPlaceholderText(
            "Поиск команд, экранов, help-topics и legacy web routes"
        )
        self.command_search.lineEdit().textEdited.connect(self._refresh_search_results)
        self.command_search.lineEdit().returnPressed.connect(
            self._activate_first_search_result
        )
        self.command_search.activated[int].connect(self._activate_search_index)
        _apply_element_contract(self.command_search, "SH-CMD-SEARCH")
        row2.addWidget(self.command_search, 1)

        self.primary_action_button = QtWidgets.QPushButton("Главное действие")
        self.primary_action_button.clicked.connect(self._run_primary_action)
        _apply_element_contract(self.primary_action_button, "SH-PRIMARY-ACTION")
        row2.addWidget(self.primary_action_button)

        self.diagnostics_button = QtWidgets.QPushButton("Собрать диагностику")
        self.diagnostics_button.clicked.connect(
            lambda: self.run_command("diagnostics.collect_bundle")
        )
        _apply_element_contract(self.diagnostics_button, "SH-DIAG-BUTTON")
        row2.addWidget(self.diagnostics_button)

        compare_button = QtWidgets.QPushButton("Открыть сравнение")
        compare_button.clicked.connect(lambda: self.run_command("results.compare.open"))
        row2.addWidget(compare_button)

        animator_button = QtWidgets.QPushButton("Открыть анимацию")
        animator_button.clicked.connect(
            lambda: self.run_command("animation.animator.open")
        )
        row2.addWidget(animator_button)
        header_layout.addLayout(row2)

        row3 = QtWidgets.QHBoxLayout()
        self.contract_label = QtWidgets.QLabel(
            "Контракт: StageRunner primary | diagnostics always visible"
        )
        _apply_element_contract(self.contract_label, "SH-OBJECTIVE-CONTRACT")
        row3.addWidget(self.contract_label, 1)
        self.warning_label = QtWidgets.QLabel(
            "Hard gate: baseline provenance обязан быть видимым"
        )
        self.warning_label.setStyleSheet("color: #8e5a00;")
        row3.addWidget(self.warning_label)
        header_layout.addLayout(row3)
        central_layout.addWidget(header)

        self.page_stack = QtWidgets.QStackedWidget()
        central_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(central)

        self._build_left_dock()
        self._build_right_dock()
        self._build_status_bar()
        self._apply_shell_state_contracts()
        self._refresh_search_results("")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        open_legacy = file_menu.addAction("Открыть legacy Tk shell")
        open_legacy.triggered.connect(lambda: self.run_command("tools.legacy_shell.open"))
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        workspace_menu = self.menuBar().addMenu("Рабочие пространства")
        for workspace in self.workspaces:
            action = workspace_menu.addAction(workspace.title)
            action.triggered.connect(
                lambda _checked=False, wid=workspace.workspace_id: self.open_workspace(wid)
            )

        diagnostics_menu = self.menuBar().addMenu("Диагностика")
        for command_id in (
            "diagnostics.collect_bundle",
            "diagnostics.verify_bundle",
            "diagnostics.send_results",
        ):
            command = self.command_by_id[command_id]
            action = diagnostics_menu.addAction(command.title)
            action.triggered.connect(
                lambda _checked=False, cid=command.command_id: self.run_command(cid)
            )
        diagnostics_menu.addSeparator()
        legacy_action = diagnostics_menu.addAction("Открыть legacy diagnostics center")
        legacy_action.triggered.connect(
            lambda: self.run_command("diagnostics.legacy_center.open")
        )

        help_menu = self.menuBar().addMenu("Справка")
        about_action = help_menu.addAction("О shell по GUI-spec")
        about_action.triggered.connect(self._show_about_dialog)

    def _build_left_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Маршрут и действия", self)
        dock.setObjectName("route_dock")
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QtWidgets.QLabel("Рабочие пространства"))
        self.workspace_list = QtWidgets.QListWidget()
        self.workspace_list.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.workspace_list.itemSelectionChanged.connect(self._on_workspace_selected)
        _apply_element_contract(self.workspace_list, "SH-NAV-TREE")
        layout.addWidget(self.workspace_list, 2)

        layout.addWidget(QtWidgets.QLabel("Закреплённые действия"))
        self.pinned_list = QtWidgets.QListWidget()
        self.pinned_list.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.pinned_list.itemActivated.connect(self._activate_recent_item)
        layout.addWidget(self.pinned_list, 1)

        layout.addWidget(QtWidgets.QLabel("Недавние действия"))
        self.recent_list = QtWidgets.QListWidget()
        self.recent_list.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.recent_list.itemActivated.connect(self._activate_recent_item)
        layout.addWidget(self.recent_list, 1)

        dock.setWidget(body)
        self._configure_dock(dock, "левая_навигация", QtCore.Qt.LeftDockWidgetArea)
        self.route_dock = dock
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

    def _build_right_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Свойства, помощь и provenance", self)
        dock.setObjectName("inspector_dock")
        self.inspector = InspectorPanel()
        self.inspector.setFocusPolicy(QtCore.Qt.StrongFocus)
        _apply_element_contract(self.inspector, "SH-INSPECTOR-CONTENT")
        dock.setWidget(self.inspector)
        self._configure_dock(dock, "правая_панель_свойств_и_справки", QtCore.Qt.RightDockWidgetArea)
        self.inspector_dock = dock
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

    def _build_status_bar(self) -> None:
        status = QtWidgets.QStatusBar()
        status.setObjectName("status_bar")
        status.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setStatusBar(status)
        self.status_primary_label = QtWidgets.QLabel("Готово")
        self.status_mode_label = QtWidgets.QLabel("Mode: GUI-spec shell")
        self.status_progress = QtWidgets.QProgressBar()
        self.status_progress.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.status_progress.setRange(0, 100)
        self.status_progress.setValue(0)
        self.status_progress.setVisible(False)
        _apply_element_contract(self.status_progress, "SH-STATUS-PROGRESS")
        status.addWidget(self.status_primary_label, 1)
        status.addPermanentWidget(self.status_mode_label)
        status.addPermanentWidget(self.status_progress)

    def _configure_dock(
        self,
        dock: QtWidgets.QDockWidget,
        panel_id: str,
        default_area: QtCore.Qt.DockWidgetArea,
    ) -> None:
        rule = self._dock_rules_by_panel.get(panel_id)
        features = QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        if rule is None or rule.can_dock:
            features |= QtWidgets.QDockWidget.DockWidgetMovable
        if rule is not None and rule.can_float:
            features |= QtWidgets.QDockWidget.DockWidgetFloatable
        dock.setFeatures(features)
        dock.setAllowedAreas(default_area | QtCore.Qt.TopDockWidgetArea | QtCore.Qt.BottomDockWidgetArea)
        dock.setProperty("spec_panel_id", panel_id)
        dock.setProperty("spec_can_auto_hide", bool(rule.can_auto_hide) if rule is not None else False)
        dock.setProperty(
            "spec_can_second_monitor",
            bool(rule.can_second_monitor) if rule is not None else False,
        )
        if rule is not None and rule.note:
            dock.setToolTip(rule.note)
        self._dock_widget_by_panel[panel_id] = dock
        dock.topLevelChanged.connect(lambda _floating, self=self: self._save_window_state())
        dock.dockLocationChanged.connect(lambda _area, self=self: self._save_window_state())
        dock.visibilityChanged.connect(lambda _visible, self=self: self._save_window_state())

    def _apply_state_style(self, widget: QtWidgets.QWidget, state_id: str) -> None:
        entry = self._ui_state_palette.get(state_id)
        widget.setProperty("ui_state_id", state_id)
        if entry is None:
            return
        border = _COLOR_BY_TOKEN.get(entry.border, "#d9e2ec")
        background = _COLOR_BY_TOKEN.get(entry.background, "#ffffff")
        text_color = _COLOR_BY_TOKEN.get(entry.text, "#16202a")
        widget.setStyleSheet(
            f"border: 1px solid {border}; background: {background}; color: {text_color}; padding: 4px 8px;"
        )

    def _apply_shell_state_contracts(self) -> None:
        self._apply_state_style(self.workspace_badge, "STATE-COMPUTED")
        self._apply_state_style(self.contract_label, "STATE-READONLY")
        self._apply_state_style(self.warning_label, "STATE-WARNING")
        self._apply_state_style(self.status_primary_label, "STATE-DEFAULT")
        self._apply_state_style(self.status_mode_label, "STATE-COMPUTED")

    def _register_shortcut(self, key_sequence: str, handler: Callable[[], None]) -> None:
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key_sequence), self)
        shortcut.activated.connect(handler)
        self._shortcut_objects.append(shortcut)

    def _apply_shell_shortcuts(self) -> None:
        self._register_shortcut(
            self._keyboard_shortcut_by_name.get("Поиск команд", "Ctrl+K"),
            self._focus_command_search,
        )
        self._register_shortcut(
            self._keyboard_shortcut_by_name.get("Главное действие шага", "Ctrl+Enter"),
            self._run_primary_action,
        )
        self._register_shortcut(
            self._keyboard_shortcut_by_name.get("Собрать диагностику", "Ctrl+Shift+D"),
            lambda: self.run_command("diagnostics.collect_bundle"),
        )
        self._register_shortcut(
            self._keyboard_shortcut_by_name.get("Помощь по выбранному элементу", "F1"),
            self._focus_help_inspector,
        )
        self._register_shortcut("F6", self._focus_next_region)
        self._register_shortcut("Shift+F6", self._focus_previous_region)

    def _focus_command_search(self) -> None:
        line_edit = self.command_search.lineEdit()
        line_edit.selectAll()
        line_edit.setFocus(QtCore.Qt.ShortcutFocusReason)
        self._active_shell_region = "верхняя_командная_панель"

    def _focus_help_inspector(self) -> None:
        if hasattr(self, "inspector_dock"):
            self.inspector_dock.show()
            self.inspector_dock.raise_()
        self.inspector.setFocus(QtCore.Qt.ShortcutFocusReason)
        self._active_shell_region = "правая_панель_свойств_и_справки"
        self.set_shell_status("Фокус перенесён в inspector/help pane", busy=False, state_id="STATE-COMPUTED")

    def _focus_target_for_region(self, region_id: str) -> QtWidgets.QWidget | None:
        if region_id == "верхняя_командная_командная_панель":
            region_id = "верхняя_командная_панель"
        mapping: dict[str, QtWidgets.QWidget] = {
            "верхняя_командная_панель": self.command_search.lineEdit(),
            "левая_навигация": self.workspace_list,
            "центральная_рабочая_область": self._page_widget_by_workspace_id.get(self._current_workspace_id, self.page_stack),
            "правая_панель_свойств_и_справки": self.inspector,
            "нижняя_строка_состояния": self.statusBar(),
        }
        return mapping.get(region_id)

    def _region_id_for_widget(self, widget: QtWidgets.QWidget | None) -> str | None:
        if widget is None:
            return None
        for region_id in self._f6_region_order:
            target = self._focus_target_for_region(region_id)
            current = widget
            while current is not None:
                if current is target:
                    return region_id
                current = current.parentWidget()
        return None

    def _focus_region_by_offset(self, offset: int) -> None:
        if not self._f6_region_order:
            return
        current_region = self._region_id_for_widget(self.focusWidget()) or self._active_shell_region
        try:
            current_index = self._f6_region_order.index(current_region)
        except ValueError:
            current_index = 0
        next_region = self._f6_region_order[(current_index + offset) % len(self._f6_region_order)]
        target = self._focus_target_for_region(next_region)
        if target is None:
            return
        if next_region == "правая_панель_свойств_и_справки" and hasattr(self, "inspector_dock"):
            self.inspector_dock.show()
            self.inspector_dock.raise_()
        if next_region == "левая_навигация" and hasattr(self, "route_dock"):
            self.route_dock.show()
            self.route_dock.raise_()
        target.setFocus(QtCore.Qt.ShortcutFocusReason)
        self._active_shell_region = next_region
        self.set_shell_status(
            f"Фокус региона: {next_region}",
            busy=False,
            state_id="STATE-FOCUS",
        )

    def _focus_next_region(self) -> None:
        self._focus_region_by_offset(1)

    def _focus_previous_region(self) -> None:
        self._focus_region_by_offset(-1)

    def _restore_window_state(self) -> None:
        geometry = self._settings.value("window/geometry")
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)
        state = self._settings.value("window/state")
        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)

    def _save_window_state(self) -> None:
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())
        self._settings.setValue("window/last_workspace", self._current_workspace_id)
        self._settings.sync()

    def _populate_pinned_actions(self) -> None:
        self.pinned_list.clear()
        for command_id in DEFAULT_PINNED_COMMAND_IDS:
            command = self.command_by_id.get(command_id)
            if command is None:
                continue
            item = QtWidgets.QListWidgetItem(command.title)
            item.setToolTip(command.route_label)
            item.setData(QtCore.Qt.UserRole, command_id)
            self.pinned_list.addItem(item)

    def _populate_workspaces(self) -> None:
        self.workspace_list.clear()
        for workspace in self.workspaces:
            item = QtWidgets.QListWidgetItem(workspace.title)
            item.setToolTip(workspace.summary)
            item.setData(QtCore.Qt.UserRole, workspace.workspace_id)
            if workspace.kind == "support":
                item.setForeground(QtGui.QColor("#576574"))
            self.workspace_list.addItem(item)

        overview_page = OverviewPage(self.repo_root, self.run_command)
        self.page_stack.addWidget(overview_page)
        self._page_index_by_workspace_id = {"overview": 0}
        self._page_widget_by_workspace_id = {"overview": overview_page}
        for workspace in self.workspaces:
            if workspace.workspace_id == "overview":
                continue
            page = self._build_workspace_page(workspace)
            self._page_index_by_workspace_id[workspace.workspace_id] = self.page_stack.count()
            self._page_widget_by_workspace_id[workspace.workspace_id] = page
            self.page_stack.addWidget(page)

    def _command_specs_for_workspace(self, workspace: DesktopWorkspaceSpec) -> tuple[DesktopShellCommandSpec, ...]:
        command_ids = workspace.quick_action_ids or ()
        seen: set[str] = set()
        commands: list[DesktopShellCommandSpec] = []
        for command_id in command_ids:
            command = self.command_by_id.get(command_id)
            if command is None or command.command_id in seen:
                continue
            seen.add(command.command_id)
            commands.append(command)
        return tuple(commands)

    def _build_workspace_page(self, workspace: DesktopWorkspaceSpec) -> QtWidgets.QWidget:
        actions = self._command_specs_for_workspace(workspace)
        if workspace.workspace_id == "input_data":
            return InputWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
            )
        if workspace.workspace_id == "baseline_run":
            return BaselineWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
            )
        if workspace.workspace_id == "optimization":
            return OptimizationWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
            )
        if workspace.workspace_id == "results_analysis":
            return ResultsWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
            )
        if workspace.workspace_id == "diagnostics":
            return DiagnosticsWorkspacePage(
                workspace,
                repo_root=self.repo_root,
                on_shell_status=self.set_shell_status,
                on_command=self.run_command,
            )
        return ControlHubWorkspacePage(workspace, actions, self.run_command)

    def _refresh_search_results(self, query: str) -> None:
        text = query if isinstance(query, str) else self.command_search.currentText()
        line_edit = self.command_search.lineEdit()
        results = search_command_palette(self.search_entries, text, limit=10)
        blocker = QtCore.QSignalBlocker(self.command_search)
        self.command_search.clear()
        self._search_ids_by_index = []
        for entry in results:
            self.command_search.addItem(f"{entry.title} | {entry.subtitle}")
            self._search_ids_by_index.append(entry.command_id)
        line_edit.setText(text)
        line_edit.setCursorPosition(len(text))
        del blocker
        if results and text:
            self.command_search.showPopup()

    def _activate_first_search_result(self) -> None:
        if self._search_ids_by_index:
            self.run_command(self._search_ids_by_index[0])

    def _activate_search_index(self, index: int) -> None:
        if 0 <= index < len(self._search_ids_by_index):
            self.run_command(self._search_ids_by_index[index])

    def _on_workspace_selected(self) -> None:
        items = self.workspace_list.selectedItems()
        if items:
            workspace_id = str(items[0].data(QtCore.Qt.UserRole) or "")
            if workspace_id:
                self.open_workspace(workspace_id)

    def _activate_recent_item(self, item: QtWidgets.QListWidgetItem) -> None:
        command_id = str(item.data(QtCore.Qt.UserRole) or "")
        if command_id:
            self.run_command(command_id)

    def _push_recent_action(self, command_id: str) -> None:
        if command_id in self.recent_command_ids:
            self.recent_command_ids.remove(command_id)
        self.recent_command_ids.appendleft(command_id)
        self.recent_list.clear()
        for recent_command_id in self.recent_command_ids:
            command = self.command_by_id.get(recent_command_id)
            if command is None:
                continue
            item = QtWidgets.QListWidgetItem(command.title)
            item.setToolTip(command.route_label)
            item.setData(QtCore.Qt.UserRole, recent_command_id)
            self.recent_list.addItem(item)

    def _show_busy(self, message: str) -> None:
        self.set_shell_status(message, busy=True, state_id="STATE-COMPUTED")
        QtCore.QTimer.singleShot(1400, self._hide_busy)

    def _hide_busy(self) -> None:
        self.status_progress.setVisible(False)
        self.status_progress.setRange(0, 100)
        self.status_progress.setValue(0)

    def set_shell_status(
        self,
        primary_text: str,
        busy: bool = False,
        *,
        mode_text: str | None = None,
        state_id: str | None = None,
    ) -> None:
        self.status_primary_label.setText(primary_text)
        if mode_text is not None:
            self.status_mode_label.setText(mode_text)
        self._apply_state_style(
            self.status_primary_label,
            state_id or ("STATE-COMPUTED" if busy else "STATE-DEFAULT"),
        )
        self.status_progress.setVisible(bool(busy))
        if busy:
            self.status_progress.setRange(0, 0)
        else:
            self.status_progress.setRange(0, 100)
            self.status_progress.setValue(0)

    def _update_primary_action(self, workspace: DesktopWorkspaceSpec) -> None:
        self._primary_command_id = None
        self.primary_action_button.setEnabled(False)
        self.primary_action_button.setText("Главное действие")
        for command_id in workspace.quick_action_ids:
            command = self.command_by_id.get(command_id)
            if command is None:
                continue
            self._primary_command_id = command.command_id
            self.primary_action_button.setEnabled(True)
            self.primary_action_button.setText(command.title)
            self.primary_action_button.setToolTip(command.summary)
            return

    def _run_primary_action(self) -> None:
        if self._primary_command_id:
            self.run_command(self._primary_command_id)

    def _dispatch_hosted_action(self, command: DesktopShellCommandSpec) -> None:
        self.open_workspace(command.workspace_id)
        page = self._page_widget_by_workspace_id.get(command.workspace_id)
        handler = getattr(page, "handle_command", None)
        if callable(handler):
            handler(command.command_id)
            self.status_mode_label.setText(f"Последняя команда: {command.title}")
            self._push_recent_action(command.command_id)
            return
        self.set_shell_status(
            f"Hosted action недоступен для workspace: {command.workspace_id}",
            busy=False,
            state_id="STATE-ERROR",
        )

    def open_workspace(self, workspace_id: str) -> None:
        workspace = self.workspace_by_id[workspace_id]
        self._current_workspace_id = workspace_id
        self.page_stack.setCurrentIndex(self._page_index_by_workspace_id[workspace_id])
        page = self._page_widget_by_workspace_id.get(workspace_id)
        if page is not None:
            page.setFocusPolicy(QtCore.Qt.StrongFocus)
        refresh = getattr(page, "refresh_view", None)
        if callable(refresh):
            refresh()
        self.workspace_badge.setText(f"Workspace: {workspace.title}")
        self.contract_label.setText(f"Контракт: {workspace.summary}")
        self.warning_label.setText(f"Hard gate: {workspace.hard_gate}")
        self.set_shell_status(
            f"Открыт workspace: {workspace.title}",
            busy=False,
            state_id="STATE-VALID",
        )
        self.status_mode_label.setText(f"Mode: {workspace.title}")
        self._update_primary_action(workspace)
        self._save_window_state()

        blocker = QtCore.QSignalBlocker(self.workspace_list)
        for index in range(self.workspace_list.count()):
            item = self.workspace_list.item(index)
            if str(item.data(QtCore.Qt.UserRole) or "") == workspace_id:
                self.workspace_list.setCurrentRow(index)
                break
        del blocker

        topic = self.help_topics.get(workspace_id)
        if topic is not None:
            self.inspector.show_topic(
                topic,
                route_label=f"Рабочие пространства -> {workspace.title}",
            )

    def run_command(self, command_id: str) -> None:
        command = self.command_by_id[command_id]
        if command.kind == "open_workspace" and command.target_workspace_id:
            self.open_workspace(command.target_workspace_id)
            self._push_recent_action(command_id)
            return

        topic = self.help_topics.get(command.help_topic_id or command.workspace_id)
        if topic is not None:
            self.inspector.show_topic(
                topic,
                route_label=command.route_label,
                command_status=command.status_label,
            )

        if command.kind == "hosted_action":
            self._dispatch_hosted_action(command)
            return

        if command.module:
            try:
                spawn_module(command.module)
                self._show_busy(f"Запуск: {command.title}")
                self.status_mode_label.setText(f"Последняя команда: {command.title}")
                self.open_workspace(command.workspace_id)
                self._push_recent_action(command_id)
            except Exception as exc:
                self.set_shell_status(
                    f"Ошибка запуска: {command.title}",
                    busy=False,
                    state_id="STATE-ERROR",
                )
                QtWidgets.QMessageBox.critical(
                    self,
                    "PneumoApp Desktop Shell",
                    f"Не удалось запустить «{command.title}».\n\n{exc}\n\n{traceback.format_exc()}",
                )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._save_window_state()
        super().closeEvent(event)

    def _show_about_dialog(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "О GUI-spec shell",
            (
                "Этот shell следует GUI-spec (17/18) и удерживает spec-driven маршрут.\n\n"
                "Route-critical workspaces постепенно переводятся в hosted surfaces,\n"
                "а legacy Tk shell остаётся fallback/debug surface."
            ),
        )


def main() -> int:
    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication([])
    window = DesktopGuiSpecMainWindow()
    window.show()
    if owns_app:
        return app.exec()
    return 0
