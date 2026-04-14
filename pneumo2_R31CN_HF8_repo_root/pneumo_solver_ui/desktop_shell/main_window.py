from __future__ import annotations

import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from pneumo_solver_ui.desktop_ui_core import ScrollableFrame
from pneumo_solver_ui.release_info import get_release

from .command_search import (
    build_shell_command_search_entries,
    rank_shell_command_search_entries,
)
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
        self.root.title(f"PneumoApp - Рабочее место инженера ({RELEASE})")
        self.root.geometry("1480x940")
        self.root.minsize(1220, 780)

        self.specs = build_desktop_shell_specs()
        self.spec_by_key = {spec.key: spec for spec in self.specs}
        self.command_search_entries = build_shell_command_search_entries(self.specs)
        self.status_var = tk.StringVar(
            value="Готово. Выберите раздел слева, верхнее меню или обзорную страницу."
        )
        self.runtime_var = tk.StringVar(
            value="Runtime: нет активной инженерной операции."
        )
        self.workflow_var = tk.StringVar(value="Маршрут: недоступен")
        self.workspace_var = tk.StringVar(value="Обзор | Открытых окон: 0")
        self.command_search_var = tk.StringVar(value="")
        self.command_search_hint_var = tk.StringVar(
            value="Поиск команд: начните вводить название экрана, команды или артефакта."
        )
        self.details_title_var = tk.StringVar(value="Обзор")
        self.details_meta_var = tk.StringVar(value="Основное рабочее место")
        self.details_body_var = tk.StringVar(
            value="Слева доступны разделы проекта: данные, сценарии, расчёт, оптимизация, результаты, анализ и визуализация."
        )
        self.details_hint_var = tk.StringVar(
            value="Подсказка: основные пользовательские разделы помечены как часть рабочего маршрута."
        )
        self.home_view: ShellHomeViewController | None = None
        self.toolbar: ShellToolbarController | None = None
        self.workspace_context_menu: ShellWorkspaceContextMenuController | None = None
        self._startup_tool_keys = startup_tool_keys
        self._startup_route_applied = False
        self._nav_item_to_key: dict[str, str] = {}
        self._runtime_trace_var: tk.Variable | None = None
        self._runtime_trace_id: str | None = None
        self._f6_region_widgets: tuple[tk.Widget, ...] = ()
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="PneumoApp",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=(
                "Классическое настольное рабочее место для ввода данных, задания сценариев, расчёта, оптимизации и анализа результатов."
            ),
            wraplength=1360,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        self.toolbar = build_shell_toolbar(
            outer,
            hosted_specs=self._specs_for_group("Встроенные окна"),
            external_specs=self._specs_for_group("Внешние окна"),
            list_open_sessions=self.workspace.list_open_sessions if hasattr(self, "workspace") else lambda: (),
            selected_workspace_key=self.workspace.selected_workspace_key if hasattr(self, "workspace") else lambda: None,
            select_hosted_session=self.select_hosted_session,
            continue_workflow=self.continue_workflow_route,
            has_open_workflow_sessions=self.workspace.has_open_workflow_sessions if hasattr(self, "workspace") else lambda: False,
            select_previous_workflow=self.select_previous_workflow_tab,
            select_next_workflow=self.select_next_workflow_tab,
            list_recently_closed_specs=self.workspace.list_recently_closed_specs if hasattr(self, "workspace") else lambda: (),
            reopen_recently_closed_at_index=self.workspace.reopen_recently_closed_at_index if hasattr(self, "workspace") else lambda _index: False,
            select_home=self._select_home_tab,
            select_previous_hosted=self.select_previous_hosted_tab,
            select_next_hosted=self.select_next_hosted_tab,
            reload_current=self.reload_current_tab,
            close_current=self.close_current_tab,
            open_tool=self.open_tool,
        )
        # Temporary placeholder above; real controller is rebuilt after workspace init below.
        self.toolbar.frame.destroy()

        for child in tuple(header.pack_slaves())[1:]:
            child.pack_forget()
        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 8, 0))
        center_panel = ttk.Frame(body)
        right_panel = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(left_panel, weight=0)
        body.add(center_panel, weight=1)
        body.add(right_panel, weight=0)

        self._build_navigation_panel(left_panel)
        self._build_details_panel(right_panel)

        self.toolbar = build_shell_toolbar(
            outer,
            hosted_specs=self._specs_for_group("Встроенные окна"),
            external_specs=self._specs_for_group("Внешние окна"),
            list_open_sessions=lambda: self.workspace.list_open_sessions() if hasattr(self, "workspace") else (),
            selected_workspace_key=lambda: self.workspace.selected_workspace_key() if hasattr(self, "workspace") else None,
            select_hosted_session=self.select_hosted_session,
            continue_workflow=self.continue_workflow_route,
            has_open_workflow_sessions=lambda: self.workspace.has_open_workflow_sessions() if hasattr(self, "workspace") else False,
            select_previous_workflow=self.select_previous_workflow_tab,
            select_next_workflow=self.select_next_workflow_tab,
            list_recently_closed_specs=lambda: self.workspace.list_recently_closed_specs() if hasattr(self, "workspace") else (),
            reopen_recently_closed_at_index=lambda index: self.workspace.reopen_recently_closed_at_index(index) if hasattr(self, "workspace") else False,
            select_home=self._select_home_tab,
            select_previous_hosted=self.select_previous_hosted_tab,
            select_next_hosted=self.select_next_hosted_tab,
            reload_current=self.reload_current_tab,
            close_current=self.close_current_tab,
            open_tool=self.open_tool,
        )
        self.toolbar.frame.pack(fill="x", before=body)
        self._build_command_strip(outer, before=body)

        self.notebook = ttk.Notebook(center_panel)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.home_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.home_tab, text="Обзор")
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
        self._bind_runtime_trace()
        self._configure_region_navigation()
        self._bind_shell_shortcuts()
        self.root.after_idle(self._open_startup_route)

        status = ttk.Frame(self.root, padding=(10, 6))
        status.pack(fill="x")
        status.columnconfigure(0, weight=1)
        status.columnconfigure(1, weight=0)
        status.columnconfigure(2, weight=0)
        self.status_primary_label = ttk.Label(status, textvariable=self.status_var)
        self.status_primary_label.grid(row=0, column=0, sticky="w")
        self.status_runtime_label = ttk.Label(
            status,
            textvariable=self.runtime_var,
            takefocus=True,
        )
        self.status_runtime_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(status, textvariable=self.workflow_var).grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Label(status, textvariable=self.workspace_var).grid(row=1, column=1, sticky="e", padx=(12, 0), pady=(4, 0))
        ttk.Sizegrip(status).grid(row=1, column=3, sticky="se", padx=(12, 0))
        self._f6_region_widgets = (
            self.command_search_combo,
            self.nav_tree,
            self.notebook,
            self.details_open_button,
            self.status_runtime_label,
        )

    def _build_navigation_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Разделы", padding=8)
        panel.pack(fill="both", expand=True)
        ttk.Label(
            panel,
            text="Основные пользовательские разделы проекта",
            wraplength=220,
            justify="left",
        ).pack(anchor="w")
        tree_frame = ttk.Frame(panel)
        tree_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.nav_tree = ttk.Treeview(tree_frame, show="tree", height=18)
        self.nav_tree.pack(side="left", fill="both", expand=True)
        nav_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.nav_tree.yview)
        nav_scroll.pack(side="right", fill="y")
        self.nav_tree.configure(yscrollcommand=nav_scroll.set)
        self.nav_tree.bind("<<TreeviewSelect>>", self._on_navigation_selected)
        ttk.Button(panel, text="Открыть выбранный раздел", command=self._open_selected_navigation_item).pack(
            fill="x",
            pady=(8, 0),
        )
        self._rebuild_navigation_tree()

    def _build_details_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Пояснение", padding=10)
        panel.pack(fill="both", expand=True)
        details_scroll = ScrollableFrame(panel)
        details_scroll.pack(fill="both", expand=True)
        body = details_scroll.body
        ttk.Label(
            body,
            textvariable=self.details_title_var,
            font=("Segoe UI", 12, "bold"),
            wraplength=280,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            body,
            textvariable=self.details_meta_var,
            foreground="#355c7d",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            body,
            textvariable=self.details_body_var,
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))
        ttk.Label(
            body,
            textvariable=self.details_hint_var,
            foreground="#555555",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))
        self.details_open_button = ttk.Button(
            body,
            text="Открыть текущий раздел",
            command=self._open_current_detail_target,
        )
        self.details_open_button.pack(
            fill="x",
            pady=(12, 0),
        )
        ttk.Button(body, text="Продолжить маршрут", command=self.continue_workflow_route).pack(
            fill="x",
            pady=(6, 0),
        )

    def _build_command_strip(self, parent: ttk.Frame, *, before: tk.Widget) -> None:
        command_strip = ttk.LabelFrame(parent, text="Командная зона", padding=8)
        command_strip.pack(fill="x", before=before, pady=(0, 8))
        command_strip.columnconfigure(1, weight=1)

        actions = ttk.Frame(command_strip)
        actions.grid(row=0, column=0, sticky="w")
        ttk.Button(
            actions,
            text="Собрать диагностику",
            command=self._open_global_diagnostics,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Открыть сравнение",
            command=self._open_compare_viewer,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Открыть в аниматоре",
            command=self._open_animator,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Остановить",
            command=self._request_stop_active_work,
        ).pack(side="left", padx=(8, 0))

        search = ttk.Frame(command_strip)
        search.grid(row=0, column=1, sticky="ew", padx=(16, 0))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Поиск команд").grid(row=0, column=0, sticky="w")
        self.command_search_combo = ttk.Combobox(
            search,
            textvariable=self.command_search_var,
            values=tuple(entry.label for entry in self.command_search_entries),
            width=42,
        )
        self.command_search_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.command_search_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._refresh_command_search_hint(),
        )
        self.command_search_combo.bind(
            "<KeyRelease>",
            lambda _event: self._refresh_command_search_hint(),
        )
        self.command_search_combo.bind(
            "<Return>",
            lambda _event: self._execute_command_search(),
        )
        ttk.Button(
            search,
            text="Открыть",
            command=self._execute_command_search,
        ).grid(row=0, column=2, sticky="e")
        ttk.Label(
            search,
            textvariable=self.command_search_hint_var,
            wraplength=620,
            justify="left",
            foreground="#4f5961",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._refresh_command_search_hint()

    def _rebuild_navigation_tree(self) -> None:
        self.nav_tree.delete(*self.nav_tree.get_children())
        self._nav_item_to_key = {}
        overview_id = self.nav_tree.insert("", "end", text="Обзор", open=True)
        self._nav_item_to_key[overview_id] = "__home__"
        sections: dict[str, list[DesktopShellToolSpec]] = {}
        for spec in self._main_nav_specs():
            sections.setdefault(spec.nav_section, []).append(spec)
        for section_label in (
            "Данные машины",
            "Сценарии",
            "Расчёт",
            "Оптимизация",
            "Результаты",
        ):
            specs = sections.get(section_label, [])
            if not specs:
                continue
            section_id = self.nav_tree.insert("", "end", text=section_label, open=True)
            for spec in sorted(specs, key=lambda item: (item.nav_order, item.title.lower())):
                item_id = self.nav_tree.insert(section_id, "end", text=spec.title)
                self._nav_item_to_key[item_id] = spec.key

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
        self._sync_navigation_selection()
        self._refresh_details_panel()
        self._bind_runtime_trace()
        self._refresh_runtime_from_active_tool()

    def _sync_navigation_selection(self) -> None:
        current_key = self.workspace.selected_workspace_key()
        target_key = current_key or "__home__"
        for item_id, item_key in self._nav_item_to_key.items():
            if item_key == target_key:
                self.nav_tree.selection_set(item_id)
                self.nav_tree.focus(item_id)
                break

    def _refresh_details_panel(self) -> None:
        current_key = self.workspace.selected_workspace_key() or "__home__"
        if current_key == "__home__":
            self.details_title_var.set("Обзор")
            self.details_meta_var.set(self.workflow_var.get())
            self.details_body_var.set(
                "Используйте разделы слева для перехода к данным, сценариям, расчёту, оптимизации и результатам."
            )
            self.details_hint_var.set(
                "Подсказка: сначала заполните данные машины, затем проверьте сценарии и только после этого переходите к расчёту и оптимизации."
            )
            return
        spec = self.spec_by_key.get(current_key)
        if spec is None:
            self.details_title_var.set("Неизвестный раздел")
            self.details_meta_var.set("")
            self.details_body_var.set("Текущее окно больше не связано с зарегистрированным разделом.")
            self.details_hint_var.set("")
            return
        self.details_title_var.set(spec.title)
        area = spec.menu_section
        kind = self._entry_kind_label(spec)
        self.details_meta_var.set(f"{area} | {kind}")
        self.details_body_var.set(spec.details or spec.description)
        self.details_hint_var.set(spec.description)

    def _specs_for_group(self, group: str) -> tuple[DesktopShellToolSpec, ...]:
        return tuple(spec for spec in self.specs if spec.group == group)

    def _main_nav_specs(self) -> tuple[DesktopShellToolSpec, ...]:
        return tuple(spec for spec in self.specs if spec.entry_kind == "main")

    def _workflow_specs(self) -> tuple[DesktopShellToolSpec, ...]:
        return ordered_workflow_specs(self._main_nav_specs())

    def _entry_kind_label(self, spec: DesktopShellToolSpec) -> str:
        if spec.entry_kind == "main":
            return "основной раздел"
        if spec.entry_kind == "contextual":
            return "контекстный переход"
        if spec.entry_kind == "external":
            return "внешнее специализированное окно"
        return "служебный инструмент"

    def _on_navigation_selected(self, _event: object | None = None) -> None:
        self._refresh_details_for_selected_navigation_item()

    def _refresh_details_for_selected_navigation_item(self) -> None:
        item_id = next(iter(self.nav_tree.selection()), "")
        key = self._nav_item_to_key.get(item_id, "")
        if key == "__home__":
            self.details_title_var.set("Обзор")
            self.details_meta_var.set("Главная страница")
            self.details_body_var.set(
                "Обзор собирает рабочий маршрут, открытые окна и быстрые переходы по основным этапам."
            )
            self.details_hint_var.set("Двойной щелчок или кнопка ниже откроют выбранный раздел.")
            return
        spec = self.spec_by_key.get(key)
        if spec is None:
            return
        self.details_title_var.set(spec.title)
        self.details_meta_var.set(
            f"{spec.menu_section} | {self._entry_kind_label(spec)}"
        )
        self.details_body_var.set(spec.details or spec.description)
        self.details_hint_var.set(spec.description)

    def _open_selected_navigation_item(self) -> None:
        item_id = next(iter(self.nav_tree.selection()), "")
        key = self._nav_item_to_key.get(item_id, "")
        if key == "__home__":
            self._select_home_tab()
            return
        if key:
            self.open_tool(key)

    def _open_current_detail_target(self) -> None:
        current_key = self.workspace.selected_workspace_key() or "__home__"
        if current_key == "__home__":
            self._open_selected_navigation_item()
            return
        self.open_tool(current_key)

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
            "PneumoApp",
            "PneumoApp\n\n"
            "Нативное Windows desktop-рабочее место инженера.\n"
            "Основной маршрут: исходные данные, сценарии, baseline и optimization, анализ, аниматор и диагностика.\n"
            "Главное shell-окно держит command surface, contextual browser, inspector и быстрые переходы к специализированным окнам.",
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

    def open_capability(self, capability_id: str) -> bool:
        capability = str(capability_id or "").strip()
        if not capability:
            return False
        if capability == "calculation.run_setup":
            input_spec = self.spec_by_key.get("desktop_input_editor")
            if input_spec is None:
                return False
            session = self.workspace.open_hosted_tool(input_spec)
            controller = getattr(session, "controller", None)
            opener = getattr(controller, "_open_run_setup_center", None)
            if callable(opener):
                opener()
                self.status_var.set("Открыта настройка расчёта из экрана данных.")
                return True
            return False
        for spec in self.specs:
            if capability in spec.capability_ids:
                self.open_tool(spec.key)
                return True
        self.status_var.set(f"Не найден маршрут для возможности: {capability}")
        return False

    def _open_global_diagnostics(self) -> None:
        self.open_tool("desktop_diagnostics_center")

    def _open_compare_viewer(self) -> None:
        self.open_tool("compare_viewer")

    def _open_animator(self) -> None:
        self.open_tool("desktop_animator")

    def _request_stop_active_work(self) -> None:
        session = self.workspace.current_session()
        if session is None:
            self.status_var.set("Останавливать пока нечего: активное рабочее окно не выбрано.")
            return
        controller = getattr(session, "controller", None)
        for method_name, caption in (
            ("soft_stop_job", "Запрошена мягкая остановка оптимизации."),
            ("_stop", "Запрошена остановка активной операции."),
            ("_on_stop", "Запрошена остановка активной операции."),
        ):
            method = getattr(controller, method_name, None)
            if callable(method):
                method()
                self.status_var.set(caption)
                return
        self.status_var.set(f"В окне «{session.spec.title}» нет поддерживаемой команды остановки.")

    def _refresh_command_search_hint(self) -> None:
        query = str(self.command_search_var.get() or "").strip()
        ranked = rank_shell_command_search_entries(query, self.command_search_entries)
        if not ranked:
            if query:
                self.command_search_hint_var.set(
                    f"Совпадений по запросу «{query}» нет. Попробуйте название раздела, bundle, animator или diagnostics."
                )
            else:
                self.command_search_hint_var.set(
                    "Поиск команд: начните вводить название экрана, команды или артефакта."
                )
            return
        best = ranked[0]
        self.command_search_hint_var.set(
            f"{best.label} -> {best.location}. {best.summary}"
        )

    def _execute_command_search(self) -> None:
        query = str(self.command_search_var.get() or "").strip()
        ranked = rank_shell_command_search_entries(query, self.command_search_entries)
        if not ranked:
            self.status_var.set(f"Команда по запросу «{query or '—'}» не найдена.")
            self._refresh_command_search_hint()
            return
        best = ranked[0]
        if best.action_kind == "tool":
            self.open_tool(best.action_value)
        elif best.action_value == "home":
            self._select_home_tab()
        else:
            self.status_var.set(f"Команда «{best.label}» пока не поддерживается.")
            return
        self.status_var.set(f"Выполнена команда: {best.label}")
        self.command_search_var.set(best.label)
        self._refresh_command_search_hint()

    def _compact_runtime_text(self, raw_text: str) -> str:
        text = " | ".join(part.strip() for part in str(raw_text or "").splitlines() if part.strip())
        if not text:
            return "Runtime: нет активной инженерной операции."
        if len(text) > 220:
            text = text[:217].rstrip() + "..."
        return f"Runtime: {text}"

    def _runtime_source_var(self, controller: object | None) -> tk.Variable | None:
        if controller is None:
            return None
        for attr_name in (
            "status_var",
            "machine_state_var",
            "workspace_summary_var",
            "mode_summary_var",
            "context_summary_var",
            "run_launch_summary_var",
        ):
            candidate = getattr(controller, attr_name, None)
            if isinstance(candidate, tk.Variable):
                return candidate
        return None

    def _unbind_runtime_trace(self) -> None:
        if self._runtime_trace_var is None or self._runtime_trace_id is None:
            self._runtime_trace_var = None
            self._runtime_trace_id = None
            return
        try:
            self._runtime_trace_var.trace_remove("write", self._runtime_trace_id)
        except Exception:
            pass
        self._runtime_trace_var = None
        self._runtime_trace_id = None

    def _bind_runtime_trace(self) -> None:
        self._unbind_runtime_trace()
        session = self.workspace.current_session()
        controller = getattr(session, "controller", None) if session is not None else None
        runtime_source = self._runtime_source_var(controller)
        if runtime_source is None:
            return
        self._runtime_trace_var = runtime_source
        self._runtime_trace_id = runtime_source.trace_add(
            "write",
            lambda *_args: self._refresh_runtime_from_active_tool(),
        )

    def _refresh_runtime_from_active_tool(self) -> None:
        session = self.workspace.current_session()
        if session is None:
            self.runtime_var.set("Runtime: shell ждёт открытия рабочего раздела.")
            return
        controller = getattr(session, "controller", None)
        runtime_source = self._runtime_source_var(controller)
        if runtime_source is not None:
            try:
                self.runtime_var.set(self._compact_runtime_text(str(runtime_source.get() or "")))
                return
            except Exception:
                pass
        self.runtime_var.set(self._compact_runtime_text(f"Активно окно: {session.spec.title}"))

    def _focus_next_region(self, *, step: int) -> str:
        widgets = tuple(
            widget
            for widget in self._f6_region_widgets
            if widget is not None and int(widget.winfo_exists())
        )
        if not widgets:
            return "break"
        focused = self.root.focus_get()
        try:
            current_index = widgets.index(focused)  # type: ignore[arg-type]
        except ValueError:
            current_index = -1 if step > 0 else 0
        target = widgets[(current_index + step) % len(widgets)]
        target.focus_set()
        return "break"

    def _configure_region_navigation(self) -> None:
        self.root.bind_all("<F6>", lambda _event: self._focus_next_region(step=1))
        self.root.bind_all("<Shift-F6>", lambda _event: self._focus_next_region(step=-1))

    def _bind_shell_shortcuts(self) -> None:
        self.root.bind_all("<Control-k>", lambda _event: self._focus_command_search())
        self.root.bind_all("<F7>", lambda _event: self._run_bound_action(self._open_global_diagnostics))
        self.root.bind_all("<F8>", lambda _event: self._run_bound_action(self._open_animator))
        self.root.bind_all("<Shift-F5>", lambda _event: self._run_bound_action(self._request_stop_active_work))

    def _focus_command_search(self) -> str:
        self.command_search_combo.focus_set()
        self.command_search_combo.selection_range(0, "end")
        return "break"

    def _run_bound_action(self, action: object) -> str:
        handler = action if callable(action) else None
        if handler is not None:
            handler()
        return "break"

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
                "PneumoApp",
                f"Не удалось открыть раздел «{spec.title}»:\n\n{tb}",
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
                "PneumoApp",
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
                "PneumoApp",
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
