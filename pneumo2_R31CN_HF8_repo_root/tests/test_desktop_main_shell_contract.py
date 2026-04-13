from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pneumo_solver_ui.tools.run_autotest_gui as autotest_gui_module
import pneumo_solver_ui.tools.run_full_diagnostics_gui as full_diagnostics_gui_module
import pneumo_solver_ui.tools.send_results_gui as send_results_gui_module
import pneumo_solver_ui.tools.test_center_gui as test_center_gui_module
import pytest
from pneumo_solver_ui.desktop_shell.contracts import DesktopShellToolSpec
from pneumo_solver_ui.desktop_shell.lifecycle import close_hosted_controller
from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
from pneumo_solver_ui.desktop_shell.navigation import (
    describe_workflow_progress,
    describe_workflow_status,
    next_workflow_spec,
    numbered_recently_closed_label,
    numbered_session_label,
    ordered_open_workflow_sessions,
    ordered_workflow_specs,
    workflow_step_badge,
    workflow_step_index,
)
from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.desktop_shell.workspace import DesktopWorkspaceManager
from pneumo_solver_ui.tools import desktop_main_shell as desktop_main_shell_module
from pneumo_solver_ui.tools.desktop_input_editor import DesktopInputEditor


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_main_shell_registry_separates_hosted_and_external_tools() -> None:
    specs = build_desktop_shell_specs()
    by_key = {spec.key: spec for spec in specs}

    assert by_key["desktop_input_editor"].mode == "hosted"
    assert by_key["test_center"].mode == "hosted"
    assert by_key["autotest_gui"].mode == "hosted"
    assert by_key["desktop_geometry_reference_center"].mode == "hosted"
    assert by_key["desktop_diagnostics_center"].mode == "hosted"

    assert by_key["compare_viewer"].mode == "external"
    assert by_key["desktop_animator"].mode == "external"
    assert by_key["desktop_mnemo"].mode == "external"

    assert by_key["desktop_input_editor"].entry_kind == "main"
    assert by_key["desktop_geometry_reference_center"].entry_kind == "tool"
    assert by_key["desktop_diagnostics_center"].entry_kind == "tool"
    assert by_key["compare_viewer"].entry_kind == "external"

    assert by_key["desktop_input_editor"].group == "Встроенные окна"
    assert by_key["desktop_animator"].group == "Внешние окна"
    assert by_key["desktop_input_editor"].standalone_module == "pneumo_solver_ui.tools.desktop_input_editor"
    assert by_key["compare_viewer"].standalone_module == "pneumo_solver_ui.qt_compare_viewer"


def test_desktop_main_shell_registry_exposes_shared_standalone_launch_catalog() -> None:
    catalog = build_desktop_launch_catalog(include_mnemo=True)
    modules = {item.module for item in catalog}

    assert "pneumo_solver_ui.tools.desktop_input_editor" in modules
    assert "pneumo_solver_ui.tools.desktop_geometry_reference_center" in modules
    assert "pneumo_solver_ui.tools.test_center_gui" in modules
    assert "pneumo_solver_ui.tools.run_autotest_gui" in modules
    assert "pneumo_solver_ui.tools.desktop_diagnostics_center" in modules
    assert "pneumo_solver_ui.qt_compare_viewer" in modules
    assert "pneumo_solver_ui.desktop_animator.app" in modules
    assert "pneumo_solver_ui.desktop_mnemo.app" in modules


def test_desktop_main_shell_keeps_classic_menu_and_workspace_shell() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "main_window.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopMainShell" in src
    assert 'self.root.title(f"PneumoApp - Рабочее место инженера ({RELEASE})")' in src
    assert "ttk.Panedwindow" in src
    assert "ttk.Notebook" in src
    assert "build_shell_menubar" in src
    assert "build_shell_toolbar" in src
    assert "build_shell_home_view" in src
    assert "DesktopWorkspaceManager" in src
    assert "self.workspace = DesktopWorkspaceManager(" in src
    assert "self.home_view: ShellHomeViewController | None = None" in src
    assert "self.toolbar: ShellToolbarController | None = None" in src
    assert "self.workspace_context_menu: ShellWorkspaceContextMenuController | None = None" in src
    assert "self._startup_tool_keys = startup_tool_keys" in src
    assert "self._startup_route_applied = False" in src
    assert 'self.workflow_var = tk.StringVar(value="Маршрут: недоступен")' in src
    assert 'self.workspace_var = tk.StringVar(value="Обзор | Открытых окон: 0")' in src
    assert 'self.details_title_var = tk.StringVar(value="Обзор")' in src
    assert 'self.details_meta_var = tk.StringVar(value="Основное рабочее место")' in src
    assert "self.home_view = build_shell_home_view(" in src
    assert "self.toolbar = build_shell_toolbar(" in src
    assert "self.workspace_context_menu = build_shell_workspace_context_menu(" in src
    assert "workflow_specs=self._workflow_specs()" in src
    assert "continue_workflow=self.continue_workflow_route" in src
    assert "select_previous_workflow=self.select_previous_workflow_tab" in src
    assert "select_next_workflow=self.select_next_workflow_tab" in src
    assert "self._build_navigation_panel(left_panel)" in src
    assert "self._build_details_panel(right_panel)" in src
    assert "self._rebuild_navigation_tree()" in src
    assert "self._refresh_details_panel()" in src
    assert "self.toolbar.frame.pack(fill=\"x\", before=body)" in src
    assert 'external_specs=self._specs_for_group("Внешние окна")' in src
    assert "select_hosted_session=self.select_hosted_session" in src
    assert "select_hosted_session_at_index=self.select_hosted_session_at_index" in src
    assert "close_other_hosted=self.close_other_hosted_tabs" in src
    assert "reopen_last_closed=self.reopen_last_closed_tab" in src
    assert "has_recently_closed_sessions=self.workspace.has_recently_closed_sessions" in src
    assert 'self.root.protocol("WM_DELETE_WINDOW", self.quit_app)' in src
    assert "self.root.after_idle(self._open_startup_route)" in src
    assert "def _refresh_shell_state(self) -> None:" in src
    assert "self.toolbar.refresh()" in src
    assert "self.workflow_var.set(describe_workflow_status(self._workflow_specs(), open_keys))" in src
    assert "self.workspace_var.set(self.workspace.describe_workspace())" in src
    assert "ttk.Sizegrip(status)" in src
    assert "status.columnconfigure(1, weight=0)" in src
    assert "status.columnconfigure(2, weight=0)" in src
    assert "ttk.Label(status, textvariable=self.workflow_var)" in src
    assert "def _workflow_specs(self) -> tuple[DesktopShellToolSpec, ...]:" in src
    assert "def _main_nav_specs(self) -> tuple[DesktopShellToolSpec, ...]:" in src
    assert 'return tuple(spec for spec in self.specs if spec.entry_kind == "main")' in src
    assert "return ordered_workflow_specs(self._main_nav_specs())" in src
    assert "def _entry_kind_label(self, spec: DesktopShellToolSpec) -> str:" in src
    assert "def continue_workflow_route(self) -> None:" in src
    assert "def select_next_workflow_tab(self) -> None:" in src
    assert "def select_previous_workflow_tab(self) -> None:" in src
    assert "open_keys = {session.key for session in self.workspace.list_open_sessions()}" in src
    assert "spec = next_workflow_spec(self._workflow_specs(), open_keys)" in src
    assert 'self.status_var.set("Основной маршрут пока недоступен в shell.")' in src
    assert "self.workspace.select_next_workflow_tab()" in src
    assert "self.workspace.select_previous_workflow_tab()" in src
    assert "def _open_startup_route(self) -> None:" in src
    assert "if self._startup_route_applied:" in src
    assert "for key in self._startup_tool_keys:" in src
    assert "spec = self.spec_by_key.get(key)" in src
    assert 'self.status_var.set(f"Неизвестный ключ окна: {key}")' in src
    assert "def open_capability(self, capability_id: str) -> bool:" in src
    assert 'if capability == "calculation.run_setup":' in src
    assert 'if capability in spec.capability_ids:' in src
    assert "def close_current_tab(self) -> None:" in src
    assert "def reload_current_tab(self) -> None:" in src
    assert "def close_all_hosted_tabs(self) -> None:" in src
    assert "def close_other_hosted_tabs(self) -> None:" in src
    assert "def select_next_hosted_tab(self) -> None:" in src
    assert "def select_previous_hosted_tab(self) -> None:" in src
    assert "def select_hosted_session(self, key: str) -> bool:" in src
    assert "def select_hosted_session_at_index(self, index: int) -> bool:" in src
    assert "def reopen_last_closed_tab(self) -> None:" in src
    assert "self.workspace.close_other_hosted_tabs()" in src
    assert "self.workspace.reopen_last_closed_tab()" in src
    assert "def quit_app(self) -> None:" in src
    assert "self.workspace.shutdown()" in src
    assert "def main(*, startup_tool_keys: tuple[str, ...] = ()) -> int:" in src


def test_desktop_main_shell_extracts_hosted_lifecycle_into_dedicated_module() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "lifecycle.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "HOST_CLOSE_METHOD_NAMES" in src
    assert "class HostedToolSession" in src
    assert "def create_hosted_session(" in src
    assert "def close_hosted_controller(" in src
    assert "def dispose_hosted_session(" in src
    assert "def selected_hosted_session(" in src


def test_desktop_main_shell_extracts_workspace_manager_for_hosted_tabs() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "workspace.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopWorkspaceManager" in src
    assert "def open_hosted_tool(" in src
    assert "def close_current_tab(" in src
    assert "def close_all_hosted_tabs(" in src
    assert "def dispose_all_hosted_sessions(" in src
    assert "def shutdown(self) -> int:" in src
    assert "MAX_RECENTLY_CLOSED_HOSTED_SESSIONS = 12" in src
    assert "workflow_specs: tuple[DesktopShellToolSpec, ...] = ()" in src
    assert "on_state_changed: Callable[[], None] | None = None" in src
    assert "def _notify_state_changed(self) -> None:" in src
    assert "def _remember_closed_spec(self, spec: DesktopShellToolSpec) -> None:" in src
    assert "def has_recently_closed_sessions(self) -> bool:" in src
    assert "def has_open_workflow_sessions(self) -> bool:" in src
    assert "def list_recently_closed_specs(self) -> tuple[DesktopShellToolSpec, ...]:" in src
    assert "def list_open_workflow_sessions(self) -> tuple[HostedToolSession, ...]:" in src
    assert "def selected_workspace_key(self) -> str | None:" in src
    assert "def workspace_key_at_index(self, index: int) -> str | None:" in src
    assert "def workspace_tab_index_at_pointer(self, x: int, y: int) -> int | None:" in src
    assert "def describe_workspace(self) -> str:" in src
    assert "def _refresh_notebook_titles(self) -> None:" in src
    assert "self.notebook.tab(self.home_tab, text=home_tab_title(len(sessions)))" in src
    assert "self.notebook.tab(session.frame, text=numbered_session_label(session, index))" in src
    assert "def select_hosted_session_at_index(self, index: int) -> bool:" in src
    assert "def select_workspace_at_index(self, index: int) -> bool:" in src
    assert "def select_next_workflow_tab(self) -> bool:" in src
    assert "def select_previous_workflow_tab(self) -> bool:" in src
    assert "def close_other_hosted_tabs(self) -> int:" in src
    assert "def reopen_recently_closed_at_index(self, index: int) -> bool:" in src
    assert "def reopen_last_closed_tab(self) -> bool:" in src
    assert '"Закрывать остальные можно только для встроенного окна."' in src
    assert '"Других встроенных окон нет."' in src
    assert '"Нет недавно закрытых встроенных окон."' in src
    assert '"Этапы основного маршрута пока не открыты."' in src
    assert '"Недавно закрытое окно #{index} недоступно."' in src
    assert "return tuple(reversed(self._recently_closed_specs))" in src
    assert "history_index = len(self._recently_closed_specs) - index" in src
    assert "return self.reopen_recently_closed_at_index(1)" in src
    assert "ordered_open_workflow_sessions(self.hosted_sessions, self.workflow_specs)" in src
    assert "find_neighbor_workflow_session(" in src
    assert 'self._set_status(f"Повторно открыто окно: {spec.title}")' in src
    assert 'self._set_status(f"Встроенное окно #{index} пока не открыто.")' in src
    assert "describe_workspace_state" in src
    assert "hosted_session_at_index" in src
    assert "home_tab_title" in src
    assert "numbered_session_label" in src
    assert "workspace_key_at_tab_index" in src
    assert "workspace_tab_index_at_pointer" in src
    assert "selected_workspace_key(" in src
    assert "def reload_current_tab(" in src
    assert "create_hosted_session" in src
    assert "dispose_hosted_session" in src
    assert "selected_hosted_session" in src


def test_desktop_main_shell_extracts_navigation_helpers() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "navigation.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "HOME_WORKSPACE_KEY" in src
    assert "MAX_DIRECT_SESSION_SHORTCUT" in src
    assert "PRIMARY_WORKFLOW_KEYS" in src
    assert "def workflow_step_index(" in src
    assert "def workflow_step_badge(" in src
    assert "def numbered_session_label(" in src
    assert "def numbered_recently_closed_label(" in src
    assert "def ordered_workflow_specs(" in src
    assert "def next_workflow_spec(" in src
    assert "def describe_workflow_progress(" in src
    assert "def describe_workflow_status(" in src
    assert "def ordered_open_workflow_sessions(" in src
    assert "def home_tab_title(" in src
    assert "def hosted_session_at_index(" in src
    assert "def workspace_key_at_tab_index(" in src
    assert "def workspace_tab_index_at_pointer(" in src
    assert "def describe_workspace_state(" in src
    assert "def ordered_hosted_sessions(" in src
    assert "def selected_workspace_key(" in src
    assert "def find_neighbor_hosted_session(" in src
    assert "def find_neighbor_workflow_session(" in src


def test_desktop_main_shell_extracts_home_view_builder() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "home_view.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "WORKFLOW_KEYS" in src
    assert "class ShellHomeViewController" in src
    assert "def build_shell_home_view(" in src
    assert 'text="Pneumo Desktop Shell"' in src
    assert '"Классическое главное окно для модульных desktop-инструментов проекта. "' in src
    assert 'text="Основной маршрут"' in src
    assert 'text="Открытые встроенные окна"' in src
    assert 'text="Недавно закрытые окна"' in src
    assert 'text="Открыть этап"' in src
    assert 'text="Перейти"' in src
    assert 'text="Продолжить маршрут"' in src
    assert 'text="Вернуть"' in src
    assert "def refresh(self) -> None:" in src
    assert "def focus_selected_session(self) -> bool:" in src
    assert "def reopen_selected_recently_closed(self) -> bool:" in src
    assert "workflow_specs: tuple[DesktopShellToolSpec, ...]" in src
    assert "continue_workflow: Callable[[], None]" in src
    assert "workflow_summary_var: tk.StringVar" in src
    assert "continue_workflow_button: ttk.Button" in src
    assert "list_recently_closed_specs: Callable[[], tuple[DesktopShellToolSpec, ...]]" in src
    assert "reopen_recently_closed_at_index: Callable[[int], bool]" in src
    assert "recently_closed_summary_var: tk.StringVar" in src
    assert "recently_closed_picker_var: tk.StringVar" in src
    assert "recently_closed_picker: ttk.Combobox" in src
    assert "reopen_button: ttk.Button" in src
    assert "recently_closed_label_to_index: dict[str, int]" in src
    assert "workflow_status_vars: dict[str, tk.StringVar]" in src
    assert "workflow_buttons: dict[str, ttk.Button]" in src
    assert "session_label_to_key: dict[str, str]" in src
    assert 'status_var.set(' in src
    assert "describe_workflow_progress(self.workflow_specs, open_keys)" in src
    assert 'self.continue_workflow_button.configure(state="normal")' in src
    assert 'self.continue_workflow_button.configure(state="disabled")' in src
    assert 'main_specs = tuple(spec for spec in hosted_specs if spec.entry_kind == "main")' in src
    assert 'tool_specs = tuple(spec for spec in hosted_specs if spec.entry_kind != "main")' in src
    assert "workflow_specs = ordered_workflow_specs(main_specs)" in src
    assert "continue_workflow=continue_workflow" in src
    assert '"Открыто в рабочей области" if key in open_keys else "Готово к открытию"' in src
    assert 'button.configure(text="Перейти к окну" if key in open_keys else "Открыть этап")' in src
    assert 'status_var = tk.StringVar(value="Готово к открытию")' in src
    assert '_build_group_box(cards, 0, "Справочники и служебные центры", tool_specs, open_tool)' in src
    assert '_build_group_box(cards, 1, "Анализ и визуализация", external_specs, open_tool)' in src
    assert 'textvariable=status_var' in src
    assert "numbered_recently_closed_label(spec, index)" in src
    assert '"Недавно закрытых встроенных окон пока нет. История появится после закрытия вкладок."' in src
    assert '"Можно быстро вернуть: {listed_recent}."' in src
    assert "controller = ShellHomeViewController(" in src
    assert "reopen_button.configure(command=controller.reopen_selected_recently_closed)" in src
    assert "numbered_session_label(session, index)" in src
    assert '_build_group_box(cards, 0, "Справочники и служебные центры"' in src
    assert '_build_group_box(cards, 1, "Анализ и визуализация"' in src
    assert 'text="Открыть"' in src


def test_desktop_main_shell_extracts_classic_toolbar_builder() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "toolbar.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class ShellToolbarController" in src
    assert "def build_shell_toolbar(" in src
    assert 'text="Главная"' in src
    assert 'text="Предыдущее"' in src
    assert 'text="Следующее"' in src
    assert 'text="Перезагрузить"' in src
    assert 'text="Закрыть"' in src
    assert 'text="Быстро открыть:"' in src
    assert 'text="Открыть окно"' in src
    assert 'text="Окна:"' in src
    assert 'text="Перейти"' in src
    assert 'text="Следующий этап"' in src
    assert 'text="Этап назад"' in src
    assert 'text="Этап вперед"' in src
    assert 'text="Недавние:"' in src
    assert 'text="Вернуть"' in src
    assert "external_specs: tuple[DesktopShellToolSpec, ...]" in src
    assert "list_open_sessions: Callable[[], tuple[HostedToolSession, ...]]" in src
    assert "selected_workspace_key: Callable[[], str | None]" in src
    assert "select_hosted_session: Callable[[str], bool]" in src
    assert "continue_workflow: Callable[[], None]" in src
    assert "has_open_workflow_sessions: Callable[[], bool]" in src
    assert "select_previous_workflow: Callable[[], None]" in src
    assert "select_next_workflow: Callable[[], None]" in src
    assert "list_recently_closed_specs: Callable[[], tuple[DesktopShellToolSpec, ...]]" in src
    assert "reopen_recently_closed_at_index: Callable[[int], bool]" in src
    assert "workflow_specs: tuple[DesktopShellToolSpec, ...]" in src
    assert "continue_workflow_button: ttk.Button" in src
    assert "previous_workflow_button: ttk.Button" in src
    assert "next_workflow_button: ttk.Button" in src
    assert "previous_button: ttk.Button" in src
    assert "next_button: ttk.Button" in src
    assert "reload_button: ttk.Button" in src
    assert "close_button: ttk.Button" in src
    assert "recently_closed_picker_var: tk.StringVar" in src
    assert "recently_closed_picker: ttk.Combobox" in src
    assert "reopen_button: ttk.Button" in src
    assert "recently_closed_label_to_index: dict[str, int]" in src
    assert "specs = hosted_specs + external_specs" in src
    assert "workflow_specs = ordered_workflow_specs(hosted_specs)" in src
    assert 'f"{spec.group}: {spec.title}"' in src
    assert "def refresh(self) -> None:" in src
    assert "def focus_selected_session(self) -> bool:" in src
    assert "def reopen_selected_recently_closed(self) -> bool:" in src
    assert 'self.continue_workflow_button.configure(' in src
    assert 'self.previous_workflow_button.configure(state="normal" if has_workflow_sessions else "disabled")' in src
    assert 'self.next_workflow_button.configure(state="normal" if has_workflow_sessions else "disabled")' in src
    assert 'self.previous_button.configure(state="normal" if has_sessions else "disabled")' in src
    assert 'self.reload_button.configure(state="normal" if has_active_hosted_session else "disabled")' in src
    assert "numbered_recently_closed_label(spec, index)" in src
    assert 'self.reopen_button.configure(state="disabled")' in src
    assert 'self.reopen_button.configure(state="normal")' in src
    assert "reopen_button.configure(command=controller.reopen_selected_recently_closed)" in src
    assert "numbered_session_label(session, index)" in src
    assert "controller = ShellToolbarController(" in src


def test_desktop_main_shell_extracts_menu_builder_with_classic_navigation_commands() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "menu_builder.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class ShellWorkspaceContextMenuController" in src
    assert "def build_shell_workspace_context_menu(" in src
    assert "def build_shell_menubar(" in src
    assert "def _menu_sections(" in src
    assert "def _workflow_shortcut_label(index: int) -> str:" in src
    assert 'menubar.add_cascade(label="Файл", menu=file_menu)' in src
    assert '"Данные",' in src
    assert '"Сценарии",' in src
    assert '"Расчёт",' in src
    assert '"Оптимизация",' in src
    assert '"Результаты",' in src
    assert '"Анализ",' in src
    assert '"Визуализация",' in src
    assert '"Инструменты",' in src
    assert 'menubar.add_cascade(label="Окно", menu=window_menu)' in src
    assert 'menubar.add_cascade(label="Справка", menu=help_menu)' in src
    assert "workflow_specs: tuple[DesktopShellToolSpec, ...]" in src
    assert "continue_workflow: Callable[[], None]" in src
    assert "has_open_workflow_sessions: Callable[[], bool]" in src
    assert "select_previous_workflow: Callable[[], None]" in src
    assert "select_next_workflow: Callable[[], None]" in src
    assert "label=describe_workflow_status(self.workflow_specs, open_keys)" in src
    assert 'label="Продолжить основной маршрут\\tCtrl+Shift+N"' in src
    assert 'label="Предыдущий этап маршрута\\tCtrl+Alt+Left"' in src
    assert 'label="Следующий этап маршрута\\tCtrl+Alt+Right"' in src
    assert 'label="Следующее окно\\tCtrl+Tab"' in src
    assert 'label="Предыдущее окно\\tCtrl+Shift+Tab"' in src
    assert 'label="Перезагрузить текущее окно\\tF5"' in src
    assert 'label="Закрыть текущее окно\\tCtrl+W"' in src
    assert "select_hosted_session_at_index: Callable[[int], bool]" in src
    assert "MAX_DIRECT_SESSION_SHORTCUT" in src
    assert "def _current_workspace_title(open_sessions: tuple[HostedToolSession, ...]) -> str:" in src
    assert 'state="normal" if has_sessions else "disabled"' in src
    assert "selected_workspace_key: Callable[[], str | None]" in src
    assert "selected_window_var = tk.StringVar(master=root, value=HOME_WORKSPACE_KEY)" in src
    assert "numbered_session_label(session, index)" in src
    assert 'state="normal" if has_active_hosted_session else "disabled"' in src
    assert "close_other_hosted: Callable[[], None]" in src
    assert "reopen_last_closed: Callable[[], None]" in src
    assert "has_recently_closed_sessions: Callable[[], bool]" in src
    assert "window_menu.add_radiobutton(" in src
    assert "window_menu.configure(postcommand=_rebuild_window_menu)" in src
    assert 'self.notebook.bind("<Button-3>", self._show_menu, add="+")' in src
    assert "tab_index = self.workspace_tab_index_at_pointer(int(event.x), int(event.y))" in src
    assert "self.select_workspace_at_index(tab_index)" in src
    assert 'label=f"Текущая вкладка: {current_label}"' in src
    assert 'label=describe_workflow_status(self.workflow_specs, open_keys)' in src
    assert 'label="Перейти к обзору"' in src
    assert 'state="normal" if has_workflow_sessions else "disabled"' in src
    assert 'label="Закрыть остальные окна"' in src
    assert 'label="Вернуть последнее закрытое окно' in src
    assert 'label="Закрыть все окна"' in src
    assert 'def _bind_action(' in src
    assert '_bind_action(root, "<Control-Tab>"' in src
    assert '_bind_action(root, "<Control-Shift-Tab>"' in src
    assert '_bind_action(root, "<Control-Shift-T>"' in src
    assert '_bind_action(root, "<Control-Shift-n>"' in src
    assert '_bind_action(root, "<Control-Alt-Left>"' in src
    assert '_bind_action(root, "<Control-Alt-Right>"' in src
    assert 'f"<Control-Alt-Key-{index}>"' in src
    assert '_bind_action(root, "<F5>"' in src
    assert '_bind_action(root, "<Control-w>"' in src
    assert 'f"<Control-Key-{index}>"' in src


def test_close_hosted_controller_prefers_explicit_hook_and_falls_back_to_known_methods() -> None:
    calls: list[str] = []

    class WithExplicitClose:
        def _on_stop(self) -> None:
            calls.append("fallback")

    class WithFallbackClose:
        def on_host_close(self) -> None:
            calls.append("host")

    def explicit_close(_controller: object) -> None:
        calls.append("explicit")

    explicit_spec = DesktopShellToolSpec(
        key="explicit",
        title="Explicit",
        description="",
        group="Встроенные окна",
        mode="hosted",
        on_close=explicit_close,
    )
    fallback_spec = DesktopShellToolSpec(
        key="fallback",
        title="Fallback",
        description="",
        group="Встроенные окна",
        mode="hosted",
    )

    assert close_hosted_controller(WithExplicitClose(), explicit_spec) is True
    assert close_hosted_controller(WithFallbackClose(), fallback_spec) is True
    assert close_hosted_controller(object(), fallback_spec) is False
    assert calls == ["explicit", "host"]


def test_hosted_tools_keep_host_parameter_and_standalone_entrypoints() -> None:
    input_sig = inspect.signature(DesktopInputEditor.__init__)
    test_center_sig = inspect.signature(test_center_gui_module.App.__init__)
    autotest_sig = inspect.signature(autotest_gui_module.App.__init__)
    diag_sig = inspect.signature(full_diagnostics_gui_module.App.__init__)
    send_sig = inspect.signature(send_results_gui_module.SendResultsGUI.__init__)

    assert "host" in input_sig.parameters
    assert "hosted" in input_sig.parameters
    assert "host" in test_center_sig.parameters
    assert "hosted" in test_center_sig.parameters
    assert "host" in autotest_sig.parameters
    assert "hosted" in autotest_sig.parameters
    assert "hosted" in diag_sig.parameters
    assert "hosted" in send_sig.parameters

    autotest_src = (ROOT / "pneumo_solver_ui" / "tools" / "run_autotest_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    assert 'self.root.title(f"Autotest Harness GUI ({RELEASE})")' in autotest_src
    assert "def main() -> int:" in autotest_src


def test_hosted_tools_expose_explicit_on_host_close_contract() -> None:
    input_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_input_editor.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    test_center_src = (ROOT / "pneumo_solver_ui" / "tools" / "test_center_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    autotest_src = (ROOT / "pneumo_solver_ui" / "tools" / "run_autotest_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    diag_src = (ROOT / "pneumo_solver_ui" / "tools" / "run_full_diagnostics_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "def on_host_close(self) -> None:" in input_src
    assert "def on_host_close(self) -> None:" in test_center_src
    assert "def on_host_close(self) -> None:" in autotest_src
    assert "def on_host_close(self) -> None:" in diag_src
    assert "def on_host_close(self) -> None:" in send_src
    assert "self._host_closed = True" in input_src
    assert "self._host_closed = True" in test_center_src
    assert "self._host_closed = True" in autotest_src
    assert "self._host_closed = True" in diag_src
    assert "self._host_closed = True" in send_src


def test_hosted_adapters_no_longer_need_manual_close_handlers_for_known_tk_tools() -> None:
    autotest_adapter_src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "adapters" / "autotest_adapter.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    test_center_adapter_src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "adapters" / "test_center_adapter.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    diag_adapter_src = (ROOT / "pneumo_solver_ui" / "desktop_shell" / "adapters" / "full_diagnostics_adapter.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "on_close=" not in autotest_adapter_src
    assert "on_close=" not in test_center_adapter_src
    assert "on_close=" not in diag_adapter_src


def test_root_desktop_main_shell_wrappers_delegate_to_shell_launcher() -> None:
    cmd = (ROOT / "START_DESKTOP_MAIN_SHELL.cmd").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    vbs = (ROOT / "START_DESKTOP_MAIN_SHELL.vbs").read_text(
        encoding="utf-8",
        errors="replace",
    ).lower()
    pyw = (ROOT / "START_DESKTOP_MAIN_SHELL.pyw").read_text(
        encoding="utf-8",
        errors="replace",
    )
    py = (ROOT / "START_DESKTOP_MAIN_SHELL.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "start_desktop_main_shell.vbs" in cmd or "start_desktop_main_shell.pyw" in cmd
    assert "wscript.shell" in vbs
    assert "start_desktop_main_shell.pyw" in vbs
    assert 'Path(__file__).with_name("START_DESKTOP_MAIN_SHELL.py")' in pyw
    assert "ensure_root_launcher_runtime" in py
    assert 'MODULE = "pneumo_solver_ui.tools.desktop_main_shell"' in py


def test_desktop_main_shell_launcher_exposes_cli_for_startup_route() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_main_shell.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "def build_arg_parser() -> argparse.ArgumentParser:" in src
    assert '"--open"' in src
    assert '"--list-tools"' in src
    assert "def format_tool_catalog() -> str:" in src
    assert "def resolve_startup_tool_keys(keys: Sequence[str]) -> tuple[str, ...]:" in src
    assert "build_desktop_shell_specs()" in src
    assert "return run_shell_main(startup_tool_keys=startup_tool_keys)" in src


def test_desktop_main_shell_launcher_validates_registry_keys_and_formats_catalog() -> None:
    catalog = desktop_main_shell_module.format_tool_catalog()

    assert "Desktop shell tools:" in catalog
    assert "desktop_input_editor" in catalog
    assert "compare_viewer" in catalog

    assert desktop_main_shell_module.resolve_startup_tool_keys(
        ["desktop_input_editor", "compare_viewer"]
    ) == ("desktop_input_editor", "compare_viewer")

    with pytest.raises(SystemExit) as exc:
        desktop_main_shell_module.resolve_startup_tool_keys(["missing_tool"])

    assert "Unknown desktop shell tool key(s): missing_tool." in str(exc.value)


def test_navigation_helpers_keep_primary_workflow_order_and_progress_text() -> None:
    specs = (
        DesktopShellToolSpec(
            key="desktop_results_center",
            title="Результаты и анализ",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
        DesktopShellToolSpec(
            key="desktop_input_editor",
            title="Данные машины",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
        DesktopShellToolSpec(
            key="desktop_optimizer_center",
            title="Оптимизация",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
        DesktopShellToolSpec(
            key="test_center",
            title="Центр проверок",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
        DesktopShellToolSpec(
            key="desktop_ring_editor",
            title="Редактор кольцевых сценариев",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
    )

    ordered = ordered_workflow_specs(specs)
    assert tuple(spec.key for spec in ordered) == (
        "desktop_input_editor",
        "desktop_ring_editor",
        "test_center",
        "desktop_optimizer_center",
        "desktop_results_center",
    )
    assert next_workflow_spec(specs, {"desktop_input_editor"}) is not None
    assert next_workflow_spec(specs, {"desktop_input_editor"}).key == "desktop_ring_editor"

    progress = describe_workflow_progress(specs, {"desktop_input_editor"})
    assert "Открыто этапов маршрута: 1/5." in progress
    assert "Следующий рекомендуемый этап: Редактор кольцевых сценариев." in progress
    assert (
        describe_workflow_status(specs, {"desktop_input_editor"})
        == "Маршрут: 1/5 -> Редактор кольцевых сценариев"
    )
    assert workflow_step_index("desktop_input_editor") == 1
    assert workflow_step_index("desktop_ring_editor") == 2
    assert workflow_step_index("desktop_results_center") == 5
    assert workflow_step_index("send_results_gui") is None
    assert workflow_step_badge("desktop_ring_editor") == "(Шаг 2)"
    assert workflow_step_badge("desktop_results_center") == "(Шаг 5)"

    workflow_session = SimpleNamespace(
        key="desktop_results_center",
        spec=DesktopShellToolSpec(
            key="desktop_results_center",
            title="Результаты и анализ",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
    )
    non_workflow_session = SimpleNamespace(
        key="send_results_gui",
        spec=DesktopShellToolSpec(
            key="send_results_gui",
            title="Отправка результатов",
            description="",
            group="Встроенные окна",
            mode="hosted",
        ),
    )
    assert numbered_session_label(workflow_session, 3) == "3. (Шаг 5) Результаты и анализ"
    assert numbered_session_label(non_workflow_session, 2) == "2. Отправка результатов"
    assert (
        numbered_recently_closed_label(workflow_session.spec, 1)
        == "1. (Шаг 5) Результаты и анализ"
    )


def test_workspace_manager_tracks_recently_closed_history_and_can_reopen_by_index() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime is unavailable in this environment: {exc}")
    try:
        notebook = ttk.Notebook(root)
        notebook.pack()
        home_tab = ttk.Frame(notebook)
        notebook.add(home_tab, text="Главная")

        statuses: list[str] = []
        manager = DesktopWorkspaceManager(
            root,
            notebook,
            home_tab,
            set_status=statuses.append,
        )

        spec_a = DesktopShellToolSpec(
            key="a",
            title="Tool A",
            description="",
            group="Встроенные окна",
            mode="hosted",
            create_hosted=lambda _parent: object(),
        )
        spec_b = DesktopShellToolSpec(
            key="b",
            title="Tool B",
            description="",
            group="Встроенные окна",
            mode="hosted",
            create_hosted=lambda _parent: object(),
        )

        manager.open_hosted_tool(spec_a)
        manager.open_hosted_tool(spec_b)

        assert tuple(session.key for session in manager.list_open_sessions()) == ("a", "b")
        assert manager.close_other_hosted_tabs() == 1
        assert tuple(spec.key for spec in manager.list_recently_closed_specs()) == ("a",)
        assert tuple(session.key for session in manager.list_open_sessions()) == ("b",)
        assert manager.has_recently_closed_sessions() is True
        assert manager.close_current_tab() is True
        assert tuple(spec.key for spec in manager.list_recently_closed_specs()) == ("b", "a")
        assert manager.reopen_recently_closed_at_index(2) is True
        assert tuple(session.key for session in manager.list_open_sessions()) == ("a",)
        assert tuple(spec.key for spec in manager.list_recently_closed_specs()) == ("b",)
        assert manager.reopen_last_closed_tab() is True
        assert tuple(session.key for session in manager.list_open_sessions()) == ("a", "b")
        assert manager.reopen_recently_closed_at_index(3) is False
        assert statuses[-1] == "Недавно закрытое окно #3 недоступно."
    finally:
        root.destroy()


def test_navigation_helpers_keep_open_workflow_sessions_in_route_order() -> None:
    workflow_input = DesktopShellToolSpec(
        key="desktop_input_editor",
        title="Данные машины",
        description="",
        group="Встроенные окна",
        mode="hosted",
    )
    workflow_ring = DesktopShellToolSpec(
        key="desktop_ring_editor",
        title="Редактор кольцевых сценариев",
        description="",
        group="Встроенные окна",
        mode="hosted",
    )
    workflow_results = DesktopShellToolSpec(
        key="desktop_results_center",
        title="Результаты и анализ",
        description="",
        group="Встроенные окна",
        mode="hosted",
    )

    existing_frame = SimpleNamespace(winfo_exists=lambda: 1)
    missing_frame = SimpleNamespace(winfo_exists=lambda: 0)
    sessions = {
        "desktop_results_center": SimpleNamespace(
            key="desktop_results_center",
            spec=workflow_results,
            frame=existing_frame,
        ),
        "extra_tool": SimpleNamespace(
            key="extra_tool",
            spec=DesktopShellToolSpec(
                key="extra_tool",
                title="Extra Tool",
                description="",
                group="Встроенные окна",
                mode="hosted",
            ),
            frame=existing_frame,
        ),
        "desktop_input_editor": SimpleNamespace(
            key="desktop_input_editor",
            spec=workflow_input,
            frame=existing_frame,
        ),
        "desktop_ring_editor": SimpleNamespace(
            key="desktop_ring_editor",
            spec=workflow_ring,
            frame=existing_frame,
        ),
        "desktop_optimizer_center": SimpleNamespace(
            key="desktop_optimizer_center",
            spec=DesktopShellToolSpec(
                key="desktop_optimizer_center",
                title="Оптимизация",
                description="",
                group="Встроенные окна",
                mode="hosted",
            ),
            frame=missing_frame,
        ),
    }

    ordered = ordered_open_workflow_sessions(
        sessions,
        (workflow_results, workflow_input, workflow_ring),
    )
    assert tuple(session.key for session in ordered) == (
        "desktop_input_editor",
        "desktop_ring_editor",
        "desktop_results_center",
    )
