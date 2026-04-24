# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import deque
import math
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable, Mapping

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
from .help_registry import build_help_registry, _operator_text
from .overview_state import OverviewCardState, build_overview_snapshot
from .registry import (
    build_command_map,
    build_shell_commands,
    build_shell_workspaces,
    build_workspace_map,
)
from .search import build_search_entries, search_command_palette
from .v16_guidance_widgets import build_v16_visibility_priority_box
from .workspace_pages import (
    AnimationWorkspacePage,
    BaselineWorkspacePage,
    ControlHubWorkspacePage,
    InputWorkspacePage,
    OptimizationWorkspacePage,
    ResultsWorkspacePage,
    RingWorkspacePage,
    SuiteWorkspacePage,
    ToolsWorkspacePage,
)

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = "GUI_SPEC_SHELL"


DEFAULT_PINNED_COMMAND_IDS = (
    "input.editor.open",
    "ring.editor.open",
    "test.center.open",
    "baseline.run.execute",
    "optimization.primary_launch.execute",
    "diagnostics.collect_bundle",
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


_REGION_LABELS: dict[str, str] = {
    "верхняя_командная_панель": "быстрый поиск",
    "левая_навигация": "список рабочих шагов",
    "центральная_рабочая_область": "рабочая область",
    "правая_панель_свойств_и_справки": "свойства и справка",
    "нижняя_строка_состояния": "строка состояния",
}


def _apply_cyrillic_operator_font(app: QtWidgets.QApplication | None) -> str:
    if app is None:
        return ""
    preferred_families = ("Segoe UI", "Tahoma", "Arial", "Noto Sans", "DejaVu Sans")
    known_families = set(QtGui.QFontDatabase.families())
    family = next((name for name in preferred_families if name in known_families), "")
    if not family:
        windir = Path(os.environ.get("WINDIR") or "C:/Windows")
        for font_name in ("segoeui.ttf", "tahoma.ttf", "arial.ttf", "ARIALUNI.ttf"):
            font_path = windir / "Fonts" / font_name
            if not font_path.exists():
                continue
            font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
            if font_id < 0:
                continue
            loaded_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
            if loaded_families:
                family = loaded_families[0]
                break
    if not family:
        return ""
    current_font = app.font()
    point_size = current_font.pointSize()
    app.setFont(QtGui.QFont(family, point_size if point_size > 0 else 10))
    return family


def _region_label(region_id: str) -> str:
    return _REGION_LABELS.get(region_id, str(region_id or "").replace("_", " "))


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
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
        widget.setToolTip(_operator_text(tooltip.text))
        widget.setWhatsThis(_operator_text(tooltip.rule))
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

        self.title_label = QtWidgets.QLabel("Свойства и происхождение данных")
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
            summary_text = f"{summary_text}\nПодсказка. {topic.tooltip_text}"
        self.summary_label.setText(summary_text)
        self.why_label.setText(f"Почему это важно. {topic.why_it_matters}" if topic.why_it_matters else "")
        self.source_label.setText(f"Источник данных. {topic.source_of_truth}")
        self.units_label.setText(f"Единицы и подписи. {topic.units_policy}")
        self.next_step_label.setText(f"Следующий шаг. {topic.next_step}")
        self.hard_gate_label.setText(f"Обязательное условие. {topic.hard_gate}")
        self.result_label.setText(
            f"Где виден результат. {topic.result_location}" if topic.result_location else ""
        )
        graphics_text = topic.graphics_policy
        if command_status:
            graphics_text = f"{graphics_text}\nСостояние окна. {command_status}"
        self.graphics_label.setText(f"Честность графики. {graphics_text}")
        self.route_label.setText(f"Расположение. {route_label}" if route_label else "")


class OverviewPage(QtWidgets.QWidget):
    def __init__(
        self,
        repo_root: Path,
        workspace: DesktopWorkspaceSpec,
        on_command: Callable[[str], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo_root = repo_root
        self.workspace = workspace
        self.on_command = on_command

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("Панель проекта")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Порядок работы: исходные данные -> сценарии -> набор испытаний -> опорный прогон -> оптимизация -> анализ -> анимация -> проверка проекта."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.cards_layout = QtWidgets.QVBoxLayout()
        self.cards_layout.setSpacing(14)
        layout.addLayout(self.cards_layout)
        v16_box = build_v16_visibility_priority_box(workspace)
        if v16_box is not None:
            layout.addWidget(v16_box)
        layout.addStretch(1)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_view()

    def _render_card(self, card: OverviewCardState) -> None:
        box = QtWidgets.QGroupBox(card.title)
        box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        box_layout = QtWidgets.QVBoxLayout(box)
        value = QtWidgets.QLabel(card.value)
        value_font = value.font()
        value_font.setBold(True)
        value_font.setPointSize(value_font.pointSize() + 1)
        value.setFont(value_font)
        value.setWordWrap(True)
        detail = QtWidgets.QLabel(card.detail)
        detail.setWordWrap(True)
        button = QtWidgets.QPushButton(card.action_text)
        button.clicked.connect(
            lambda _checked=False, cid=card.command_id: self.on_command(cid)
        )
        box_layout.addWidget(value)
        box_layout.addWidget(detail)
        box_layout.addWidget(button)
        self.cards_layout.addWidget(box)

    def refresh_view(self) -> None:
        snapshot = build_overview_snapshot(self.repo_root)
        _clear_layout(self.cards_layout)
        for card in snapshot.cards:
            self._render_card(card)


class DesktopGuiSpecMainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.repo_root = legacy_repo_root()
        self._settings = QtCore.QSettings(
            str(_default_shell_state_path(self.repo_root)),
            QtCore.QSettings.IniFormat,
        )
        self._state_save_suppressed = True
        self._state_save_timer = QtCore.QTimer(self)
        self._state_save_timer.setSingleShot(True)
        self._state_save_timer.setInterval(750)
        self._state_save_timer.timeout.connect(self._sync_window_state)
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
        self._workspace_dock_by_workspace_id: dict[str, QtWidgets.QDockWidget] = {}
        self._child_dock_by_command_id: dict[str, QtWidgets.QDockWidget] = {}
        self._child_dock_by_object_name: dict[str, QtWidgets.QDockWidget] = {}
        self._shortcut_objects: list[QtGui.QShortcut] = []
        self._primary_command_id: str | None = None
        self._current_workspace_id = "overview"
        self._active_shell_region = "верхняя_командная_панель"
        self._operator_font_family = _apply_cyrillic_operator_font(
            QtWidgets.QApplication.instance()
        )
        if self._operator_font_family:
            point_size = self.font().pointSize()
            self.setFont(QtGui.QFont(self._operator_font_family, point_size if point_size > 0 else 10))

        self.setWindowTitle(f"PneumoApp - Рабочее место инженера ({RELEASE})")
        self.resize(1680, 980)
        self.setMinimumSize(1320, 840)
        self._build_ui()
        self._populate_workspaces()
        self._populate_pinned_actions()
        self._apply_shell_shortcuts()
        self._restore_window_state()
        self.open_workspace(_startup_workspace_id(self._settings, self.workspace_by_id))
        self._state_save_suppressed = False

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
        title = QtWidgets.QLabel("PneumoApp")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        row1.addWidget(title)
        self.project_label = QtWidgets.QLabel(str(self.repo_root))
        self.project_label.setStyleSheet("color: #576574;")
        row1.addWidget(self.project_label, 1)
        self.workspace_badge = QtWidgets.QLabel("Текущий рабочий шаг: Панель проекта")
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
            "Быстрый поиск действий"
        )
        self.command_search.lineEdit().textEdited.connect(self._refresh_search_results)
        self.command_search.lineEdit().returnPressed.connect(
            self._activate_first_search_result
        )
        self.command_search.activated[int].connect(self._activate_search_index)
        _apply_element_contract(self.command_search, "SH-CMD-SEARCH")
        self.command_search.setAccessibleName("Быстрый поиск")
        self.command_search.setAccessibleDescription(
            "Поиск по рабочим шагам, действиям, проверке проекта, архиву и файлам."
        )
        self.command_search.setToolTip(
            "Ctrl+K. Найдите окно, действие, проверку проекта, архив или файл."
        )
        self.command_search.setWhatsThis("")
        row2.addWidget(self.command_search, 1)

        self.primary_action_button = QtWidgets.QPushButton("Действие шага")
        self.primary_action_button.clicked.connect(self._run_primary_action)
        _apply_element_contract(self.primary_action_button, "SH-PRIMARY-ACTION")
        row2.addWidget(self.primary_action_button)

        self.diagnostics_button = QtWidgets.QPushButton("Сохранить архив проекта")
        self.diagnostics_button.clicked.connect(
            lambda: self.run_command("diagnostics.collect_bundle")
        )
        _apply_element_contract(self.diagnostics_button, "SH-DIAG-BUTTON")
        row2.addWidget(self.diagnostics_button)

        compare_button = QtWidgets.QPushButton("Сравнить прогоны")
        compare_button.clicked.connect(lambda: self.run_command("results.compare.open"))
        row2.addWidget(compare_button)

        animator_button = QtWidgets.QPushButton("Анимировать результат")
        animator_button.clicked.connect(
            lambda: self.run_command("animation.animator.open")
        )
        row2.addWidget(animator_button)
        header_layout.addLayout(row2)

        info_panel = QtWidgets.QFrame()
        info_layout = QtWidgets.QVBoxLayout(info_panel)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        self.contract_label = QtWidgets.QLabel(
            "Цели и ограничения: основные показатели расчёта | проверка проекта всегда видима"
        )
        self.contract_label.setWordWrap(True)
        self.contract_label.setMinimumHeight(30)
        _apply_element_contract(self.contract_label, "SH-OBJECTIVE-CONTRACT")
        info_layout.addWidget(self.contract_label)
        self.warning_label = QtWidgets.QLabel(
            "Обязательное условие. Происхождение опорного прогона должно быть видимо"
        )
        self.warning_label.setWordWrap(True)
        self.warning_label.setMinimumHeight(42)
        self.warning_label.setStyleSheet("color: #8e5a00;")
        info_layout.addWidget(self.warning_label)
        header_layout.addWidget(info_panel)
        central_layout.addWidget(header)

        self.workspace_center_placeholder = QtWidgets.QLabel(
            "Выберите этап в дереве слева. Рабочие поверхности открываются как дочерние dock-окна этого рабочего места."
        )
        self.workspace_center_placeholder.setObjectName("dock_center_placeholder")
        self.workspace_center_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self.workspace_center_placeholder.setWordWrap(True)
        self.workspace_center_placeholder.setStyleSheet(
            "QLabel{color:#6b778c;background:#f8fafc;border:1px dashed #ccd6e0;border-radius:12px;padding:18px;}"
        )
        central_layout.addWidget(self.workspace_center_placeholder, 1)
        self.setCentralWidget(central)

        self._build_left_dock()
        self._build_right_dock()
        self._build_status_bar()
        self._apply_shell_state_contracts()
        self._refresh_search_results("")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        self.windows_menu = self.menuBar().addMenu("Окна")

        diagnostics_menu = self.menuBar().addMenu("Проверка проекта")
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
        if self._legacy_tools_visible():
            service_menu = self.menuBar().addMenu("Сервис")
            for command_id in (
                "input.legacy_editor.open",
                "ring.legacy_editor.open",
                "test.legacy_center.open",
                "baseline.legacy_run_setup.open",
                "optimization.legacy_center.open",
                "results.legacy_center.open",
                "results.legacy_compare.open",
                "animation.legacy_animator.open",
                "animation.legacy_mnemo.open",
                "diagnostics.legacy_center.open",
                "tools.geometry_reference.legacy_open",
                "tools.autotest.legacy_open",
                "tools.qt_main_shell.open",
                "tools.legacy_shell.open",
            ):
                command = self.command_by_id[command_id]
                action = service_menu.addAction(command.title)
                action.triggered.connect(
                    lambda _checked=False, cid=command.command_id: self.run_command(cid)
                )

        help_menu = self.menuBar().addMenu("Справка")
        about_action = help_menu.addAction("О рабочем месте")
        about_action.triggered.connect(self._show_about_dialog)

    def _legacy_tools_visible(self) -> bool:
        return os.environ.get("PNEUMO_SHOW_LEGACY_TOOLS", "").strip() == "1"

    def _build_left_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Маршрут работы", self)
        dock.setObjectName("route_dock")
        dock.setMinimumWidth(280)
        body = QtWidgets.QWidget()
        body.setMinimumWidth(260)
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QtWidgets.QLabel("Дерево маршрута"))
        self.workspace_list = QtWidgets.QTreeWidget()
        self.workspace_list.setHeaderHidden(True)
        self.workspace_list.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.workspace_list.itemClicked.connect(self._activate_route_tree_item)
        self.workspace_list.itemActivated.connect(self._activate_route_tree_item)
        _apply_element_contract(self.workspace_list, "SH-NAV-TREE")
        layout.addWidget(self.workspace_list, 3)

        layout.addWidget(QtWidgets.QLabel("Прямые действия этапов"))
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
        dock = QtWidgets.QDockWidget("Свойства, справка и происхождение данных", self)
        dock.setObjectName("inspector_dock")
        dock.setMinimumWidth(360)
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
        self.status_mode_label = QtWidgets.QLabel("Рабочее место инженера")
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

    def _register_window_toggle(self, dock: QtWidgets.QDockWidget, title: str) -> None:
        menu = getattr(self, "windows_menu", None)
        if menu is None:
            return
        action = dock.toggleViewAction()
        try:
            action.setText(title)
        except Exception:
            pass
        menu.addAction(action)

    @staticmethod
    def _safe_dock_object_name(prefix: str, raw_id: str) -> str:
        cleaned = "".join(
            char if char.isalnum() or char in {"_"} else "_"
            for char in str(raw_id or "").replace(".", "_").replace("-", "_")
        ).strip("_")
        return f"{prefix}_{cleaned or 'surface'}"

    def _install_workspace_dock(
        self,
        workspace: DesktopWorkspaceSpec,
        page: QtWidgets.QWidget,
    ) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(workspace.title, self)
        dock.setObjectName(self._safe_dock_object_name("workspace_dock", workspace.workspace_id))
        dock.setWidget(page)
        dock.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        dock.setProperty("spec_panel_id", f"workspace:{workspace.workspace_id}")
        dock.setProperty("spec_workspace_id", workspace.workspace_id)
        dock.setProperty("spec_child_window_role", "workspace")
        dock.setToolTip(
            "Дочернее окно рабочего этапа. Его можно пристыковать, вынести на второй монитор и вернуть в рабочее место."
        )
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        existing_docks = tuple(self._workspace_dock_by_workspace_id.values())
        if existing_docks:
            try:
                self.tabifyDockWidget(existing_docks[0], dock)
            except Exception:
                pass
        self._workspace_dock_by_workspace_id[workspace.workspace_id] = dock
        self._register_window_toggle(dock, workspace.title)
        dock.topLevelChanged.connect(lambda _floating, self=self: self._save_window_state())
        dock.dockLocationChanged.connect(lambda _area, self=self: self._save_window_state())
        dock.visibilityChanged.connect(lambda _visible, self=self: self._save_window_state())
        dock.hide()
        return dock

    @staticmethod
    def _child_dock_plot_points(raw_points: object) -> tuple[tuple[float, float], ...]:
        points: list[tuple[float, float]] = []
        for raw_point in raw_points if isinstance(raw_points, (list, tuple)) else ():
            if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
                continue
            try:
                x_value = float(raw_point[0])
                y_value = float(raw_point[1])
            except Exception:
                continue
            if not (math.isfinite(x_value) and math.isfinite(y_value)):
                continue
            points.append((x_value, y_value))
        return tuple(points)

    def _build_child_dock_plot_widget(
        self,
        plot_preview: Mapping[str, object],
        command: DesktopShellCommandSpec,
    ) -> QtWidgets.QWidget | None:
        raw_series = plot_preview.get("series")
        series_rows: list[dict[str, object]] = []
        all_x_values: list[float] = []
        all_y_values: list[float] = []
        for raw_entry in raw_series if isinstance(raw_series, (list, tuple)) else ():
            if not isinstance(raw_entry, Mapping):
                continue
            points = self._child_dock_plot_points(raw_entry.get("points"))
            if not points:
                continue
            series_rows.append(
                {
                    "label": str(raw_entry.get("label") or "").strip() or "series",
                    "color": str(raw_entry.get("color") or "#2563eb").strip() or "#2563eb",
                    "points": points,
                }
            )
            all_x_values.extend(point[0] for point in points)
            all_y_values.extend(point[1] for point in points)
        if not series_rows or not all_x_values or not all_y_values:
            return None

        x_min = min(all_x_values)
        x_max = max(all_x_values)
        y_min = min(all_y_values)
        y_max = max(all_y_values)
        if x_min == x_max:
            x_min -= 1.0
            x_max += 1.0
        if y_min == y_max:
            y_min -= 1.0
            y_max += 1.0

        width = 520.0
        height = 188.0
        margin_left = 44.0
        margin_right = 18.0
        margin_top = 26.0
        margin_bottom = 30.0
        plot_width = width - margin_left - margin_right
        plot_height = height - margin_top - margin_bottom

        def _px(x_value: float) -> float:
            return margin_left + plot_width * ((x_value - x_min) / max(1e-9, x_max - x_min))

        def _py(y_value: float) -> float:
            return margin_top + plot_height * (1.0 - ((y_value - y_min) / max(1e-9, y_max - y_min)))

        container = QtWidgets.QWidget()
        container.setObjectName(
            str(
                plot_preview.get("container_object_name")
                or self._safe_dock_object_name("child_dock_plot_box", command.command_id)
            )
        )
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = str(plot_preview.get("title") or "").strip()
        summary = str(plot_preview.get("summary") or "").strip()
        if title or summary:
            title_label = QtWidgets.QLabel(" | ".join(part for part in (title, summary) if part))
            title_label.setObjectName(
                str(
                    plot_preview.get("title_object_name")
                    or self._safe_dock_object_name("child_dock_plot_title", command.command_id)
                )
            )
            title_label.setWordWrap(True)
            title_label.setStyleSheet("color:#334e68; font-weight:600;")
            layout.addWidget(title_label)

        scene = QtWidgets.QGraphicsScene(container)
        scene.setSceneRect(0.0, 0.0, width, height)
        scene.addRect(
            0.0,
            0.0,
            width,
            height,
            QtGui.QPen(QtGui.QColor("#d5dde6")),
            QtGui.QBrush(QtGui.QColor("#f8fafc")),
        )
        axis_pen = QtGui.QPen(QtGui.QColor("#7f8fa6"))
        scene.addLine(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, axis_pen)
        scene.addLine(margin_left, margin_top, margin_left, height - margin_bottom, axis_pen)

        raw_window = plot_preview.get("window")
        if isinstance(raw_window, (list, tuple)) and len(raw_window) >= 2:
            try:
                window_start = float(raw_window[0])
                window_end = float(raw_window[1])
            except Exception:
                window_start = None
                window_end = None
            if window_start is not None and window_end is not None:
                left = _px(min(window_start, window_end))
                right = _px(max(window_start, window_end))
                scene.addRect(
                    left,
                    margin_top,
                    max(2.0, right - left),
                    plot_height,
                    QtGui.QPen(QtCore.Qt.NoPen),
                    QtGui.QBrush(QtGui.QColor(191, 219, 254, 70)),
                )

        if y_min < 0.0 < y_max:
            zero_pen = QtGui.QPen(QtGui.QColor("#cbd5e1"))
            zero_pen.setStyle(QtCore.Qt.DashLine)
            zero_y = _py(0.0)
            scene.addLine(margin_left, zero_y, width - margin_right, zero_y, zero_pen)

        legend_x = margin_left
        legend_y = 6.0
        for index, series in enumerate(series_rows):
            color = QtGui.QColor(str(series["color"]))
            legend_pen = QtGui.QPen(color, 2.0)
            y_pos = legend_y + index * 12.0
            scene.addLine(legend_x, y_pos + 5.0, legend_x + 14.0, y_pos + 5.0, legend_pen)
            text_item = scene.addText(str(series["label"]))
            text_item.setDefaultTextColor(QtGui.QColor("#334e68"))
            text_item.setPos(legend_x + 18.0, y_pos - 4.0)

            path = QtGui.QPainterPath()
            points = tuple(series["points"])
            for point_index, (x_value, y_value) in enumerate(points):
                x_pos = _px(x_value)
                y_pos = _py(y_value)
                if point_index == 0:
                    path.moveTo(x_pos, y_pos)
                else:
                    path.lineTo(x_pos, y_pos)
                scene.addEllipse(
                    x_pos - 1.8,
                    y_pos - 1.8,
                    3.6,
                    3.6,
                    QtGui.QPen(color),
                    QtGui.QBrush(color),
                )
            scene.addPath(path, QtGui.QPen(color, 2.0))

        focus_value = plot_preview.get("focus_x")
        try:
            focus_x = float(focus_value)
        except Exception:
            focus_x = None
        if focus_x is not None and math.isfinite(focus_x):
            focus_pen = QtGui.QPen(QtGui.QColor("#ea580c"), 1.6)
            focus_pen.setStyle(QtCore.Qt.DashLine)
            x_pos = _px(focus_x)
            scene.addLine(x_pos, margin_top, x_pos, height - margin_bottom, focus_pen)

        x_text = scene.addText(f"{x_min:.3f} .. {x_max:.3f} s")
        x_text.setDefaultTextColor(QtGui.QColor("#52606d"))
        x_text.setPos(margin_left, height - margin_bottom + 2.0)
        y_text = scene.addText(f"{y_min:.3g} .. {y_max:.3g}")
        y_text.setDefaultTextColor(QtGui.QColor("#52606d"))
        y_text.setPos(width - margin_right - 104.0, height - margin_bottom + 2.0)

        view = QtWidgets.QGraphicsView(scene, container)
        view.setObjectName(
            str(
                plot_preview.get("object_name")
                or self._safe_dock_object_name("child_dock_plot", command.command_id)
            )
        )
        view.setMinimumHeight(int(height + 2.0))
        view.setRenderHint(QtGui.QPainter.Antialiasing, True)
        view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        view.setFrameShape(QtWidgets.QFrame.NoFrame)
        tooltip = str(plot_preview.get("tooltip") or "").strip()
        if tooltip:
            view.setToolTip(tooltip)
        layout.addWidget(view)
        return container

    def _show_child_dock_from_result(
        self,
        command: DesktopShellCommandSpec,
        result: object,
    ) -> None:
        if not isinstance(result, Mapping):
            return
        payload = result.get("child_dock")
        if not isinstance(payload, Mapping):
            return
        title = str(payload.get("title") or command.title)
        summary = str(payload.get("summary") or command.summary)
        rows = payload.get("rows") or ()

        body = QtWidgets.QWidget()
        body.setObjectName(str(payload.get("content_object_name") or self._safe_dock_object_name("child_dock_content", command.command_id)))
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        label = QtWidgets.QLabel(summary)
        label.setWordWrap(True)
        label.setStyleSheet("color:#334e68;")
        layout.addWidget(label)

        plot_preview = payload.get("plot_preview")
        if isinstance(plot_preview, Mapping):
            plot_widget = self._build_child_dock_plot_widget(plot_preview, command)
            if plot_widget is not None:
                layout.addWidget(plot_widget)

        table = QtWidgets.QTableWidget(0, 2)
        table.setObjectName(str(payload.get("table_object_name") or self._safe_dock_object_name("child_dock_table", command.command_id)))
        table.setHorizontalHeaderLabels(("Пункт", "Значение"))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        normalized_rows: list[tuple[str, str]] = []
        for raw in rows:
            if isinstance(raw, Mapping):
                key = str(raw.get("label") or raw.get("name") or raw.get("key") or "").strip()
                value = str(raw.get("value") or raw.get("detail") or "").strip()
            elif isinstance(raw, (tuple, list)) and len(raw) >= 2:
                key = str(raw[0]).strip()
                value = " | ".join(str(part).strip() for part in raw[1:] if str(part).strip())
            else:
                key = "Состояние"
                value = str(raw).strip()
            if key or value:
                normalized_rows.append((key or "Пункт", value or "нет данных"))
        table.setRowCount(len(normalized_rows))
        for row_index, (key, value) in enumerate(normalized_rows):
            table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(key))
            table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)

        dock_object_name = str(
            payload.get("object_name")
            or self._safe_dock_object_name("child_dock", command.command_id)
        )
        dock = self._child_dock_by_object_name.get(dock_object_name)
        if dock is None:
            dock = self._child_dock_by_command_id.get(command.command_id)
        if dock is None:
            dock = QtWidgets.QDockWidget(title, self)
            dock.setObjectName(dock_object_name)
            dock.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
            dock.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
                | QtWidgets.QDockWidget.DockWidgetClosable
            )
            self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
            self._register_window_toggle(dock, title)
            self._child_dock_by_object_name[dock_object_name] = dock
            dock.topLevelChanged.connect(lambda _floating, self=self: self._save_window_state())
            dock.dockLocationChanged.connect(lambda _area, self=self: self._save_window_state())
            dock.visibilityChanged.connect(lambda _visible, self=self: self._save_window_state())
        self._child_dock_by_command_id[command.command_id] = dock
        self._child_dock_by_object_name[dock_object_name] = dock
        dock.setProperty("spec_panel_id", f"child:{command.command_id}")
        dock.setProperty("spec_command_id", command.command_id)
        dock.setProperty("spec_workspace_id", command.workspace_id)
        dock.setProperty("spec_child_window_role", "detail")
        old_widget = dock.widget()
        if old_widget is not None:
            old_widget.setParent(None)
            old_widget.deleteLater()
        dock.setWindowTitle(title)
        dock.setWidget(body)
        dock.show()
        dock.raise_()
        body.setFocus(QtCore.Qt.OtherFocusReason)
        self._save_window_state()

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
            self._keyboard_shortcut_by_name.get(
                "Быстрый поиск",
                self._keyboard_shortcut_by_name.get("Поиск команд", "Ctrl+K"),
            ),
            self._focus_command_search,
        )
        self._register_shortcut(
            self._keyboard_shortcut_by_name.get("Главное действие шага", "Ctrl+Enter"),
            self._run_primary_action,
        )
        self._register_shortcut(
            self._keyboard_shortcut_by_name.get("Сохранить архив проекта", "Ctrl+Shift+D"),
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
        self.set_shell_status("Фокус перенесён в панель свойств и справки", busy=False, state_id="STATE-COMPUTED")

    def _focus_target_for_region(self, region_id: str) -> QtWidgets.QWidget | None:
        if region_id == "верхняя_командная_командная_панель":
            region_id = "верхняя_командная_панель"
        mapping: dict[str, QtWidgets.QWidget] = {
            "верхняя_командная_панель": self.command_search.lineEdit(),
            "левая_навигация": self.workspace_list,
            "центральная_рабочая_область": self._page_widget_by_workspace_id.get(
                self._current_workspace_id,
                self.workspace_center_placeholder,
            ),
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
            f"Фокус: {_region_label(next_region)}",
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
        QtCore.QTimer.singleShot(0, self._ensure_window_visible)

    def _ensure_window_visible(self) -> None:
        screens = QtGui.QGuiApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        available_rects = [screen.availableGeometry() for screen in screens]
        if any(rect.intersects(frame) for rect in available_rects):
            return
        primary = QtGui.QGuiApplication.primaryScreen() or screens[0]
        target = primary.availableGeometry()
        width = min(max(self.minimumWidth(), self.width()), max(self.minimumWidth(), target.width() - 80))
        height = min(max(self.minimumHeight(), self.height()), max(self.minimumHeight(), target.height() - 80))
        self.resize(width, height)
        center = target.center()
        self.move(center.x() - width // 2, center.y() - height // 2)

    def _save_window_state(self) -> None:
        if getattr(self, "_state_save_suppressed", False):
            return
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())
        self._settings.setValue("window/last_workspace", self._current_workspace_id)
        self._state_save_timer.start()

    def _sync_window_state(self) -> None:
        try:
            self._settings.sync()
        except Exception:
            pass

    def _compact_command_title(self, command: DesktopShellCommandSpec) -> str:
        if command.kind == "open_workspace" and command.target_workspace_id:
            workspace = self.workspace_by_id.get(command.target_workspace_id)
            if workspace is not None:
                return workspace.title
        return command.title

    def _primary_command_title(self, command: DesktopShellCommandSpec) -> str:
        if command.kind == "open_workspace" and command.target_workspace_id:
            workspace = self.workspace_by_id.get(command.target_workspace_id)
            if workspace is not None:
                return f"Перейти: {workspace.title}"
        return command.title

    def _populate_pinned_actions(self) -> None:
        self.pinned_list.clear()
        for command_id in DEFAULT_PINNED_COMMAND_IDS:
            command = self.command_by_id.get(command_id)
            if command is None:
                continue
            item = QtWidgets.QListWidgetItem(self._compact_command_title(command))
            item.setToolTip(command.route_label)
            item.setData(QtCore.Qt.UserRole, command_id)
            self.pinned_list.addItem(item)

    def _populate_workspaces(self) -> None:
        self.workspace_list.clear()
        main_index = 1
        support_root: QtWidgets.QTreeWidgetItem | None = None
        for workspace in self.workspaces:
            if workspace.kind == "support":
                if support_root is None:
                    support_root = QtWidgets.QTreeWidgetItem(["Сервис и справка"])
                    support_root.setData(0, QtCore.Qt.UserRole, "")
                    support_root.setForeground(0, QtGui.QColor("#576574"))
                    self.workspace_list.addTopLevelItem(support_root)
                item = QtWidgets.QTreeWidgetItem([workspace.title])
                item.setForeground(0, QtGui.QColor("#576574"))
                support_root.addChild(item)
            else:
                item = QtWidgets.QTreeWidgetItem([f"{main_index}. {workspace.title}"])
                self.workspace_list.addTopLevelItem(item)
                main_index += 1
            item.setToolTip(0, workspace.summary)
            item.setData(0, QtCore.Qt.UserRole, workspace.workspace_id)
            item.setData(0, QtCore.Qt.UserRole + 1, "")
            for command in self._command_specs_for_workspace(workspace):
                if command.availability == "support_fallback":
                    continue
                child = QtWidgets.QTreeWidgetItem([command.title])
                child.setToolTip(0, command.summary)
                child.setData(0, QtCore.Qt.UserRole, workspace.workspace_id)
                child.setData(0, QtCore.Qt.UserRole + 1, command.command_id)
                item.addChild(child)
            item.setExpanded(workspace.kind == "main")
        if support_root is not None:
            support_root.setExpanded(False)

        overview_page = OverviewPage(
            self.repo_root,
            self.workspace_by_id["overview"],
            self.run_command,
        )
        self._page_index_by_workspace_id = {"overview": 0}
        self._page_widget_by_workspace_id = {"overview": overview_page}
        self._install_workspace_dock(self.workspace_by_id["overview"], overview_page)
        for workspace in self.workspaces:
            if workspace.workspace_id == "overview":
                continue
            page = self._build_workspace_page(workspace)
            self._page_index_by_workspace_id[workspace.workspace_id] = len(self._page_index_by_workspace_id)
            self._page_widget_by_workspace_id[workspace.workspace_id] = page
            self._install_workspace_dock(workspace, page)

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
        if workspace.workspace_id == "ring_editor":
            return RingWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
                python_executable=sys.executable,
            )
        if workspace.workspace_id == "baseline_run":
            return BaselineWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
                on_shell_status=self.set_shell_status,
            )
        if workspace.workspace_id == "test_matrix":
            return SuiteWorkspacePage(
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
                on_shell_status=self.set_shell_status,
            )
        if workspace.workspace_id == "results_analysis":
            return ResultsWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
            )
        if workspace.workspace_id == "animation":
            return AnimationWorkspacePage(
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
        if workspace.workspace_id == "tools":
            return ToolsWorkspacePage(
                workspace,
                actions,
                self.run_command,
                repo_root=self.repo_root,
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

    def _activate_route_tree_item(self, item: QtWidgets.QTreeWidgetItem, _column: int = 0) -> None:
        command_id = str(item.data(0, QtCore.Qt.UserRole + 1) or "")
        workspace_id = str(item.data(0, QtCore.Qt.UserRole) or "")
        if command_id:
            self.run_command(command_id)
            return
        if workspace_id:
            self.open_workspace(workspace_id)

    def _iter_route_tree_items(self) -> list[QtWidgets.QTreeWidgetItem]:
        items: list[QtWidgets.QTreeWidgetItem] = []
        stack = [
            self.workspace_list.topLevelItem(index)
            for index in range(self.workspace_list.topLevelItemCount())
        ]
        while stack:
            item = stack.pop(0)
            if item is None:
                continue
            items.append(item)
            stack[0:0] = [item.child(index) for index in range(item.childCount())]
        return items

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
            item = QtWidgets.QListWidgetItem(self._compact_command_title(command))
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
        self.primary_action_button.setText("Действие шага")
        for command_id in workspace.quick_action_ids:
            command = self.command_by_id.get(command_id)
            if command is None:
                continue
            self._primary_command_id = command.command_id
            self.primary_action_button.setEnabled(True)
            self.primary_action_button.setText(self._primary_command_title(command))
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
            result = handler(command.command_id)
            self._show_child_dock_from_result(command, result)
            self.status_mode_label.setText(f"Последнее действие: {command.title}")
            self._push_recent_action(command.command_id)
            return
        workspace = self.workspace_by_id.get(command.workspace_id)
        workspace_title = workspace.title if workspace is not None else command.workspace_id
        self.set_shell_status(
                f"Действие пока недоступно в рабочем шаге: {workspace_title}",
            busy=False,
            state_id="STATE-ERROR",
        )

    def open_workspace(self, workspace_id: str) -> None:
        workspace = self.workspace_by_id[workspace_id]
        self._current_workspace_id = workspace_id
        dock = self._workspace_dock_by_workspace_id.get(workspace_id)
        if dock is not None:
            dock.show()
            dock.raise_()
        page = self._page_widget_by_workspace_id.get(workspace_id)
        if page is not None:
            page.setFocusPolicy(QtCore.Qt.StrongFocus)
        refresh = getattr(page, "refresh_view", None)
        if callable(refresh):
            refresh()
        self.workspace_badge.setText(f"Текущий рабочий шаг: {workspace.title}")
        self.contract_label.setText(f"Краткая сводка. {workspace.summary}")
        self.warning_label.setText(f"Обязательное условие. {workspace.hard_gate}")
        self.set_shell_status(
            f"Текущий рабочий шаг: {workspace.title}",
            busy=False,
            state_id="STATE-VALID",
        )
        self.status_mode_label.setText(f"Рабочий шаг «{workspace.title}»")
        self._update_primary_action(workspace)
        self._save_window_state()

        blocker = QtCore.QSignalBlocker(self.workspace_list)
        for item in self._iter_route_tree_items():
            item_workspace_id = str(item.data(0, QtCore.Qt.UserRole) or "")
            item_command_id = str(item.data(0, QtCore.Qt.UserRole + 1) or "")
            if item_workspace_id == workspace_id and not item_command_id:
                self.workspace_list.setCurrentItem(item)
                break
        del blocker

        topic = self.help_topics.get(workspace_id)
        if topic is not None:
            self.inspector.show_topic(
                topic,
                route_label=f"Окна -> {workspace.title}",
            )

    def run_command(self, command_id: str) -> None:
        command = self.command_by_id[command_id]
        if command.availability == "support_fallback" and not self._legacy_tools_visible():
            self.set_shell_status(
                "Старое окно скрыто из основного маршрута. Вся работа должна выполняться в текущем рабочем месте.",
                busy=False,
                state_id="STATE-WARNING",
            )
            return
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
                self._show_busy(f"Открываю: {command.title}")
                self.status_mode_label.setText(f"Последнее действие: {command.title}")
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
                    "PneumoApp",
                    f"Не удалось запустить «{command.title}».\n\n{exc}\n\n{traceback.format_exc()}",
                )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._save_window_state()
        if self._state_save_timer.isActive():
            self._state_save_timer.stop()
        self._sync_window_state()
        super().closeEvent(event)

    def _show_about_dialog(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "О рабочем месте",
            (
                "Рабочее место собирает основные инженерные окна приложения в одном классическом интерфейсе.\n\n"
                "Рабочие участки открываются из общего меню и остаются доступными без скрытых шагов."
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
