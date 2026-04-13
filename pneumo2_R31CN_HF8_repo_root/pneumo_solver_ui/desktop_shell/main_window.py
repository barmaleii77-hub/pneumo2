from __future__ import annotations

import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from pneumo_solver_ui.release_info import get_release

from .contracts import DesktopShellToolSpec
from .home_view import ShellHomeViewController, build_shell_home_view
from .menu_builder import (
    ShellWorkspaceContextMenuController,
    build_shell_menubar,
    build_shell_workspace_context_menu,
)
from .navigation import describe_workflow_status, next_workflow_spec, ordered_workflow_specs
from .registry import build_desktop_shell_specs
from .toolbar import ShellToolbarController, build_shell_toolbar
from .workspace import DesktopWorkspaceManager


RELEASE = get_release()


class DesktopMainShell:
    def __init__(self, *, startup_tool_keys: tuple[str, ...] = ()) -> None:
        self.root = tk.Tk()
        self.root.title(f"Pneumo Desktop Shell - {RELEASE}")
        self.root.geometry("1380x900")
        self.root.minsize(1180, 760)

        self.specs = build_desktop_shell_specs()
        self.spec_by_key = {spec.key: spec for spec in self.specs}
        self.status_var = tk.StringVar(
            value="Готово. Откройте инструмент через верхнее меню или стартовую страницу."
        )
        self.workflow_var = tk.StringVar(value="Маршрут: недоступен")
        self.workspace_var = tk.StringVar(value="Главная | Встроенных окон: 0")
        self.home_view: ShellHomeViewController | None = None
        self.toolbar: ShellToolbarController | None = None
        self.workspace_context_menu: ShellWorkspaceContextMenuController | None = None
        self._startup_tool_keys = startup_tool_keys
        self._startup_route_applied = False
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.home_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.home_tab, text="Главная")
        self.workspace = DesktopWorkspaceManager(
            self.root,
            self.notebook,
            self.home_tab,
            workflow_specs=self._workflow_specs(),
            set_status=self.status_var.set,
            on_state_changed=self._refresh_shell_state,
        )
        self.home_view = build_shell_home_view(
            self.home_tab,
            hosted_specs=self._specs_for_group("Встроенные окна"),
            external_specs=self._specs_for_group("Внешние окна"),
            open_tool=self.open_tool,
            continue_workflow=self.continue_workflow_route,
            list_open_sessions=self.workspace.list_open_sessions,
            select_hosted_session=self.select_hosted_session,
            list_recently_closed_specs=self.workspace.list_recently_closed_specs,
            reopen_recently_closed_at_index=self.workspace.reopen_recently_closed_at_index,
        )
        self.toolbar = build_shell_toolbar(
            outer,
            hosted_specs=self._specs_for_group("Встроенные окна"),
            external_specs=self._specs_for_group("Внешние окна"),
            list_open_sessions=self.workspace.list_open_sessions,
            selected_workspace_key=self.workspace.selected_workspace_key,
            select_hosted_session=self.select_hosted_session,
            continue_workflow=self.continue_workflow_route,
            has_open_workflow_sessions=self.workspace.has_open_workflow_sessions,
            select_previous_workflow=self.select_previous_workflow_tab,
            select_next_workflow=self.select_next_workflow_tab,
            list_recently_closed_specs=self.workspace.list_recently_closed_specs,
            reopen_recently_closed_at_index=self.workspace.reopen_recently_closed_at_index,
            select_home=self._select_home_tab,
            select_previous_hosted=self.select_previous_hosted_tab,
            select_next_hosted=self.select_next_hosted_tab,
            reload_current=self.reload_current_tab,
            close_current=self.close_current_tab,
            open_tool=self.open_tool,
        )
        self.toolbar.frame.pack(fill="x", before=self.notebook)
        self._build_menu()
        self.workspace_context_menu = build_shell_workspace_context_menu(
            self.root,
            self.notebook,
            workflow_specs=self._workflow_specs(),
            list_open_sessions=self.workspace.list_open_sessions,
            selected_workspace_key=self.workspace.selected_workspace_key,
            workspace_tab_index_at_pointer=self.workspace.workspace_tab_index_at_pointer,
            select_workspace_at_index=self.workspace.select_workspace_at_index,
            continue_workflow=self.continue_workflow_route,
            has_open_workflow_sessions=self.workspace.has_open_workflow_sessions,
            select_previous_workflow=self.select_previous_workflow_tab,
            select_next_workflow=self.select_next_workflow_tab,
            select_home=self._select_home_tab,
            select_next_hosted=self.select_next_hosted_tab,
            select_previous_hosted=self.select_previous_hosted_tab,
            reload_current=self.reload_current_tab,
            close_current=self.close_current_tab,
            close_other_hosted=self.close_other_hosted_tabs,
            close_all_hosted=self.close_all_hosted_tabs,
            reopen_last_closed=self.reopen_last_closed_tab,
            has_recently_closed_sessions=self.workspace.has_recently_closed_sessions,
        )
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self._refresh_shell_state()
        self.root.after_idle(self._open_startup_route)

        status = ttk.Frame(self.root, padding=(10, 6))
        status.pack(fill="x")
        status.columnconfigure(0, weight=1)
        status.columnconfigure(1, weight=0)
        status.columnconfigure(2, weight=0)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.workflow_var).grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Label(status, textvariable=self.workspace_var).grid(row=0, column=2, sticky="e", padx=(12, 0))
        ttk.Sizegrip(status).grid(row=0, column=3, sticky="se", padx=(12, 0))

    def _build_menu(self) -> None:
        menubar = build_shell_menubar(
            self.root,
            workflow_specs=self._workflow_specs(),
            hosted_specs=self._specs_for_group("Встроенные окна"),
            external_specs=self._specs_for_group("Внешние окна"),
            open_tool=self.open_tool,
            continue_workflow=self.continue_workflow_route,
            has_open_workflow_sessions=self.workspace.has_open_workflow_sessions,
            select_previous_workflow=self.select_previous_workflow_tab,
            select_next_workflow=self.select_next_workflow_tab,
            select_home=self._select_home_tab,
            select_next_hosted=self.select_next_hosted_tab,
            select_previous_hosted=self.select_previous_hosted_tab,
            select_hosted_session=self.select_hosted_session,
            select_hosted_session_at_index=self.select_hosted_session_at_index,
            list_open_sessions=self.workspace.list_open_sessions,
            selected_workspace_key=self.workspace.selected_workspace_key,
            reload_current=self.reload_current_tab,
            close_current=self.close_current_tab,
            close_other_hosted=self.close_other_hosted_tabs,
            close_all_hosted=self.close_all_hosted_tabs,
            reopen_last_closed=self.reopen_last_closed_tab,
            has_recently_closed_sessions=self.workspace.has_recently_closed_sessions,
            show_about=self._show_about,
            quit_app=self.quit_app,
        )
        self.root.config(menu=menubar)

    def _refresh_shell_state(self) -> None:
        open_keys = {session.key for session in self.workspace.list_open_sessions()}
        if self.home_view is not None:
            self.home_view.refresh()
        if self.toolbar is not None:
            self.toolbar.refresh()
        self.workflow_var.set(describe_workflow_status(self._workflow_specs(), open_keys))
        self.workspace_var.set(self.workspace.describe_workspace())

    def _specs_for_group(self, group: str) -> tuple[DesktopShellToolSpec, ...]:
        return tuple(spec for spec in self.specs if spec.group == group)

    def _workflow_specs(self) -> tuple[DesktopShellToolSpec, ...]:
        return ordered_workflow_specs(self._specs_for_group("Встроенные окна"))

    def continue_workflow_route(self) -> None:
        open_keys = {session.key for session in self.workspace.list_open_sessions()}
        spec = next_workflow_spec(self._workflow_specs(), open_keys)
        if spec is None:
            self.status_var.set("Основной маршрут пока недоступен в shell.")
            return
        self.open_tool(spec.key)

    def select_next_workflow_tab(self) -> None:
        self.workspace.select_next_workflow_tab()

    def select_previous_workflow_tab(self) -> None:
        self.workspace.select_previous_workflow_tab()

    def _select_home_tab(self) -> None:
        self.workspace.select_home_tab()

    def _show_about(self) -> None:
        messagebox.showinfo(
            "Pneumo Desktop Shell",
            "Pneumo Desktop Shell\n\n"
            "Классическое главное окно с верхним меню, модульным registry и отдельными адаптерами.\n"
            "Цель: подтягивать GUI по одному, без нового монолита.",
        )

    def _on_tab_changed(self, _event: object | None = None) -> None:
        self.workspace.handle_tab_changed()

    def open_tool(self, key: str) -> None:
        spec = self.spec_by_key.get(key)
        if spec is None:
            self.status_var.set(f"Неизвестный ключ окна: {key}")
            return
        if spec.is_hosted:
            self._open_hosted_tool(spec)
            return
        self._launch_external_tool(spec)

    def _open_startup_route(self) -> None:
        if self._startup_route_applied:
            return
        self._startup_route_applied = True
        for key in self._startup_tool_keys:
            self.open_tool(key)

    def _open_hosted_tool(self, spec: DesktopShellToolSpec) -> None:
        try:
            self.workspace.open_hosted_tool(spec)
        except Exception:
            tb = traceback.format_exc()
            messagebox.showerror(
                "Pneumo Desktop Shell",
                f"Не удалось открыть окно «{spec.title}»:\n\n{tb}",
            )
            self.status_var.set(f"Ошибка открытия: {spec.title}")

    def _launch_external_tool(self, spec: DesktopShellToolSpec) -> None:
        try:
            launched = spec.launch_external() if spec.launch_external else None
            pid = getattr(launched, "pid", None)
            if pid:
                self.status_var.set(f"Запущено внешнее окно: {spec.title} (pid={pid})")
            else:
                self.status_var.set(f"Запущено внешнее окно: {spec.title}")
        except Exception:
            tb = traceback.format_exc()
            messagebox.showerror(
                "Pneumo Desktop Shell",
                f"Не удалось запустить внешнее окно «{spec.title}»:\n\n{tb}",
            )
            self.status_var.set(f"Ошибка запуска: {spec.title}")

    def close_current_tab(self) -> None:
        self.workspace.close_current_tab()

    def reload_current_tab(self) -> None:
        self.workspace.reload_current_tab()

    def close_all_hosted_tabs(self) -> None:
        self.workspace.close_all_hosted_tabs()

    def close_other_hosted_tabs(self) -> None:
        self.workspace.close_other_hosted_tabs()

    def select_next_hosted_tab(self) -> None:
        self.workspace.select_next_hosted_tab()

    def select_previous_hosted_tab(self) -> None:
        self.workspace.select_previous_hosted_tab()

    def select_hosted_session(self, key: str) -> bool:
        return self.workspace.select_hosted_session(key)

    def select_hosted_session_at_index(self, index: int) -> bool:
        return self.workspace.select_hosted_session_at_index(index)

    def reopen_last_closed_tab(self) -> None:
        try:
            self.workspace.reopen_last_closed_tab()
        except Exception:
            tb = traceback.format_exc()
            messagebox.showerror(
                "Pneumo Desktop Shell",
                f"Не удалось повторно открыть окно:\n\n{tb}",
            )
            self.status_var.set("Ошибка повторного открытия окна.")

    def quit_app(self) -> None:
        try:
            self.workspace.shutdown()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main(*, startup_tool_keys: tuple[str, ...] = ()) -> int:
    app = DesktopMainShell(startup_tool_keys=startup_tool_keys)
    app.run()
    return 0
