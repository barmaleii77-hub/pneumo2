from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import Menu
from typing import Callable

from .contracts import DesktopShellToolSpec
from .lifecycle import HostedToolSession
from .navigation import (
    HOME_WORKSPACE_KEY,
    MAX_DIRECT_SESSION_SHORTCUT,
    describe_workflow_progress,
    describe_workflow_status,
    numbered_session_label,
)


def _bind_action(root: tk.Misc, sequence: str, handler: Callable[[], object]) -> None:
    def _callback(_event: object | None = None) -> str:
        handler()
        return "break"

    root.bind_all(sequence, _callback)


def _workflow_shortcut_label(index: int) -> str:
    return f"Ctrl+Alt+{index}"


@dataclass
class ShellWorkspaceContextMenuController:
    notebook: tk.Misc
    menu: Menu
    workflow_specs: tuple[DesktopShellToolSpec, ...]
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]]
    selected_workspace_key: Callable[[], str | None]
    workspace_tab_index_at_pointer: Callable[[int, int], int | None]
    select_workspace_at_index: Callable[[int], bool]
    continue_workflow: Callable[[], None]
    has_open_workflow_sessions: Callable[[], bool]
    select_previous_workflow: Callable[[], None]
    select_next_workflow: Callable[[], None]
    select_home: Callable[[], None]
    select_next_hosted: Callable[[], None]
    select_previous_hosted: Callable[[], None]
    reload_current: Callable[[], None]
    close_current: Callable[[], None]
    close_other_hosted: Callable[[], None]
    close_all_hosted: Callable[[], None]
    reopen_last_closed: Callable[[], None]
    has_recently_closed_sessions: Callable[[], bool]

    def bind(self) -> None:
        self.notebook.bind("<Button-3>", self._show_menu, add="+")

    def _show_menu(self, event: tk.Event) -> str | None:
        tab_index = self.workspace_tab_index_at_pointer(int(event.x), int(event.y))
        if tab_index is None:
            return None
        self.select_workspace_at_index(tab_index)
        self._rebuild_menu()
        try:
            self.menu.tk_popup(int(event.x_root), int(event.y_root))
        finally:
            self.menu.grab_release()
        return "break"

    def _rebuild_menu(self) -> None:
        self.menu.delete(0, "end")
        open_sessions = self.list_open_sessions()
        open_keys = {session.key for session in open_sessions}
        current_key = self.selected_workspace_key()
        has_sessions = bool(open_sessions)
        has_workflow_sessions = self.has_open_workflow_sessions()
        has_active_hosted_session = bool(current_key and current_key != HOME_WORKSPACE_KEY)
        has_recently_closed = self.has_recently_closed_sessions()

        if current_key == HOME_WORKSPACE_KEY:
            current_label = "Главная"
        elif has_active_hosted_session:
            current_label = next(
                (
                    session.spec.title
                    for session in open_sessions
                    if session.key == current_key
                ),
                "Неизвестная вкладка",
            )
        else:
            current_label = "Неизвестная вкладка"

        self.menu.add_command(label=f"Текущая вкладка: {current_label}", state="disabled")
        self.menu.add_command(
            label=describe_workflow_status(self.workflow_specs, open_keys),
            state="disabled",
        )
        self.menu.add_separator()
        self.menu.add_command(
            label="Продолжить основной маршрут\tCtrl+Shift+N",
            command=self.continue_workflow,
            state="normal" if self.workflow_specs else "disabled",
        )
        self.menu.add_command(
            label="Предыдущий открытый этап маршрута\tCtrl+Alt+Left",
            command=self.select_previous_workflow,
            state="normal" if has_workflow_sessions else "disabled",
        )
        self.menu.add_command(
            label="Следующий открытый этап маршрута\tCtrl+Alt+Right",
            command=self.select_next_workflow,
            state="normal" if has_workflow_sessions else "disabled",
        )
        self.menu.add_command(label="Перейти на главную", command=self.select_home)
        self.menu.add_command(
            label="Следующее встроенное окно",
            command=self.select_next_hosted,
            state="normal" if has_sessions else "disabled",
        )
        self.menu.add_command(
            label="Предыдущее встроенное окно",
            command=self.select_previous_hosted,
            state="normal" if has_sessions else "disabled",
        )
        self.menu.add_separator()
        self.menu.add_command(
            label="Перезагрузить текущее окно",
            command=self.reload_current,
            state="normal" if has_active_hosted_session else "disabled",
        )
        self.menu.add_command(
            label="Закрыть текущее окно",
            command=self.close_current,
            state="normal" if has_active_hosted_session else "disabled",
        )
        self.menu.add_command(
            label="Закрыть остальные встроенные окна",
            command=self.close_other_hosted,
            state="normal" if has_active_hosted_session and len(open_sessions) > 1 else "disabled",
        )
        self.menu.add_command(
            label="Закрыть все встроенные окна",
            command=self.close_all_hosted,
            state="normal" if has_sessions else "disabled",
        )
        self.menu.add_separator()
        self.menu.add_command(
            label="Повторно открыть последнее окно",
            command=self.reopen_last_closed,
            state="normal" if has_recently_closed else "disabled",
        )


def build_shell_workspace_context_menu(
    root: tk.Misc,
    notebook: tk.Misc,
    *,
    workflow_specs: tuple[DesktopShellToolSpec, ...],
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]],
    selected_workspace_key: Callable[[], str | None],
    workspace_tab_index_at_pointer: Callable[[int, int], int | None],
    select_workspace_at_index: Callable[[int], bool],
    continue_workflow: Callable[[], None],
    has_open_workflow_sessions: Callable[[], bool],
    select_previous_workflow: Callable[[], None],
    select_next_workflow: Callable[[], None],
    select_home: Callable[[], None],
    select_next_hosted: Callable[[], None],
    select_previous_hosted: Callable[[], None],
    reload_current: Callable[[], None],
    close_current: Callable[[], None],
    close_other_hosted: Callable[[], None],
    close_all_hosted: Callable[[], None],
    reopen_last_closed: Callable[[], None],
    has_recently_closed_sessions: Callable[[], bool],
) -> ShellWorkspaceContextMenuController:
    controller = ShellWorkspaceContextMenuController(
        notebook=notebook,
        menu=Menu(root, tearoff=False),
        workflow_specs=workflow_specs,
        list_open_sessions=list_open_sessions,
        selected_workspace_key=selected_workspace_key,
        workspace_tab_index_at_pointer=workspace_tab_index_at_pointer,
        select_workspace_at_index=select_workspace_at_index,
        continue_workflow=continue_workflow,
        has_open_workflow_sessions=has_open_workflow_sessions,
        select_previous_workflow=select_previous_workflow,
        select_next_workflow=select_next_workflow,
        select_home=select_home,
        select_next_hosted=select_next_hosted,
        select_previous_hosted=select_previous_hosted,
        reload_current=reload_current,
        close_current=close_current,
        close_other_hosted=close_other_hosted,
        close_all_hosted=close_all_hosted,
        reopen_last_closed=reopen_last_closed,
        has_recently_closed_sessions=has_recently_closed_sessions,
    )
    controller.bind()
    return controller


def build_shell_menubar(
    root: tk.Misc,
    *,
    workflow_specs: tuple[DesktopShellToolSpec, ...],
    hosted_specs: tuple[DesktopShellToolSpec, ...],
    external_specs: tuple[DesktopShellToolSpec, ...],
    open_tool: Callable[[str], None],
    continue_workflow: Callable[[], None],
    has_open_workflow_sessions: Callable[[], bool],
    select_previous_workflow: Callable[[], None],
    select_next_workflow: Callable[[], None],
    select_home: Callable[[], None],
    select_next_hosted: Callable[[], None],
    select_previous_hosted: Callable[[], None],
    select_hosted_session: Callable[[str], bool],
    select_hosted_session_at_index: Callable[[int], bool],
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]],
    selected_workspace_key: Callable[[], str | None],
    reload_current: Callable[[], None],
    close_current: Callable[[], None],
    close_other_hosted: Callable[[], None],
    close_all_hosted: Callable[[], None],
    reopen_last_closed: Callable[[], None],
    has_recently_closed_sessions: Callable[[], bool],
    show_about: Callable[[], None],
    quit_app: Callable[[], None],
) -> Menu:
    menubar = Menu(root)

    file_menu = Menu(menubar, tearoff=False)
    file_menu.add_command(label="Главная", command=select_home)
    file_menu.add_separator()
    file_menu.add_command(label="Выход", command=quit_app)
    menubar.add_cascade(label="Файл", menu=file_menu)

    hosted_menu = Menu(menubar, tearoff=False)
    for spec in hosted_specs:
        hosted_menu.add_command(label=spec.title, command=lambda key=spec.key: open_tool(key))
    menubar.add_cascade(label="Встроенные окна", menu=hosted_menu)

    external_menu = Menu(menubar, tearoff=False)
    for spec in external_specs:
        external_menu.add_command(label=spec.title, command=lambda key=spec.key: open_tool(key))
    menubar.add_cascade(label="Внешние окна", menu=external_menu)

    workflow_menu = Menu(menubar, tearoff=False)
    navigation_menu = Menu(menubar, tearoff=False)
    window_menu = Menu(menubar, tearoff=False)
    selected_window_var = tk.StringVar(master=root, value=HOME_WORKSPACE_KEY)

    def _current_workspace_title(open_sessions: tuple[HostedToolSession, ...]) -> str:
        current_key = selected_workspace_key()
        if current_key == HOME_WORKSPACE_KEY or not current_key:
            return "Главная"
        for session in open_sessions:
            if session.key == current_key:
                return session.spec.title
        return "Неизвестная вкладка"

    def _rebuild_navigation_menu() -> None:
        navigation_menu.delete(0, "end")
        open_sessions = list_open_sessions()
        has_sessions = bool(open_sessions)
        navigation_menu.add_command(label="Главная", command=select_home)
        navigation_menu.add_separator()
        navigation_menu.add_command(
            label=f"Текущий контекст: {_current_workspace_title(open_sessions)}",
            state="disabled",
        )
        navigation_menu.add_separator()
        navigation_menu.add_command(
            label="Следующее встроенное окно\tCtrl+Tab",
            command=select_next_hosted,
            state="normal" if has_sessions else "disabled",
        )
        navigation_menu.add_command(
            label="Предыдущее встроенное окно\tCtrl+Shift+Tab",
            command=select_previous_hosted,
            state="normal" if has_sessions else "disabled",
        )
        navigation_menu.add_separator()
        if not open_sessions:
            navigation_menu.add_command(label="Нет открытых встроенных окон", state="disabled")
            return
        for index, session in enumerate(open_sessions, start=1):
            accelerator = f"\tCtrl+{index}" if index <= MAX_DIRECT_SESSION_SHORTCUT else ""
            navigation_menu.add_command(
                label=f"{numbered_session_label(session, index)}{accelerator}",
                command=lambda key=session.key: select_hosted_session(key),
            )

    def _rebuild_workflow_menu() -> None:
        workflow_menu.delete(0, "end")
        open_sessions = list_open_sessions()
        open_keys = {session.key for session in open_sessions}
        has_workflow_sessions = has_open_workflow_sessions()
        if not workflow_specs:
            workflow_menu.add_command(label="Основной маршрут недоступен", state="disabled")
            return

        workflow_menu.add_command(
            label=describe_workflow_progress(workflow_specs, open_keys),
            state="disabled",
        )
        workflow_menu.add_separator()
        workflow_menu.add_command(
            label="Продолжить основной маршрут\tCtrl+Shift+N",
            command=continue_workflow,
        )
        workflow_menu.add_command(
            label="Предыдущий открытый этап маршрута\tCtrl+Alt+Left",
            command=select_previous_workflow,
            state="normal" if has_workflow_sessions else "disabled",
        )
        workflow_menu.add_command(
            label="Следующий открытый этап маршрута\tCtrl+Alt+Right",
            command=select_next_workflow,
            state="normal" if has_workflow_sessions else "disabled",
        )
        workflow_menu.add_separator()
        for index, spec in enumerate(workflow_specs, start=1):
            suffix = " (открыт)" if spec.key in open_keys else ""
            accelerator = f"\t{_workflow_shortcut_label(index)}"
            workflow_menu.add_command(
                label=f"Шаг {index}. {spec.title}{suffix}{accelerator}",
                command=lambda key=spec.key: open_tool(key),
            )

    def _rebuild_window_menu() -> None:
        window_menu.delete(0, "end")
        open_sessions = list_open_sessions()
        current_key = selected_workspace_key() or ""
        has_active_hosted_session = bool(current_key and current_key != HOME_WORKSPACE_KEY)
        has_recently_closed = has_recently_closed_sessions()
        selected_window_var.set(current_key)

        window_menu.add_command(
            label="Перезагрузить текущее окно\tF5",
            command=reload_current,
            state="normal" if has_active_hosted_session else "disabled",
        )
        window_menu.add_command(
            label="Закрыть текущее окно\tCtrl+W",
            command=close_current,
            state="normal" if has_active_hosted_session else "disabled",
        )
        window_menu.add_command(
            label="Закрыть остальные встроенные окна",
            command=close_other_hosted,
            state="normal" if has_active_hosted_session and len(open_sessions) > 1 else "disabled",
        )
        window_menu.add_command(
            label="Закрыть все встроенные окна",
            command=close_all_hosted,
            state="normal" if open_sessions else "disabled",
        )
        window_menu.add_command(
            label="Повторно открыть последнее окно\tCtrl+Shift+T",
            command=reopen_last_closed,
            state="normal" if has_recently_closed else "disabled",
        )
        window_menu.add_separator()

        window_menu.add_command(
            label=f"Открыто встроенных окон: {len(open_sessions)}",
            state="disabled",
        )
        window_menu.add_command(
            label=f"Текущее окно: {_current_workspace_title(open_sessions)}",
            state="disabled",
        )
        window_menu.add_radiobutton(
            label="Главная",
            value=HOME_WORKSPACE_KEY,
            variable=selected_window_var,
            command=select_home,
        )
        if not open_sessions:
            window_menu.add_command(label="Нет открытых встроенных окон", state="disabled")
            return

        window_menu.add_separator()
        for index, session in enumerate(open_sessions, start=1):
            window_menu.add_radiobutton(
                label=numbered_session_label(session, index),
                value=session.key,
                variable=selected_window_var,
                command=lambda key=session.key: select_hosted_session(key),
            )

    workflow_menu.configure(postcommand=_rebuild_workflow_menu)
    menubar.add_cascade(label="Маршрут", menu=workflow_menu)

    navigation_menu.configure(postcommand=_rebuild_navigation_menu)
    menubar.add_cascade(label="Навигация", menu=navigation_menu)

    window_menu.configure(postcommand=_rebuild_window_menu)
    menubar.add_cascade(label="Окно", menu=window_menu)

    help_menu = Menu(menubar, tearoff=False)
    help_menu.add_command(label="О приложении", command=show_about)
    menubar.add_cascade(label="Справка", menu=help_menu)

    _bind_action(root, "<Control-Tab>", select_next_hosted)
    _bind_action(root, "<Control-Shift-Tab>", select_previous_hosted)
    _bind_action(root, "<Control-ISO_Left_Tab>", select_previous_hosted)
    _bind_action(root, "<Control-w>", close_current)
    _bind_action(root, "<Control-Shift-T>", reopen_last_closed)
    _bind_action(root, "<Control-Shift-n>", continue_workflow)
    _bind_action(root, "<Control-Alt-Left>", select_previous_workflow)
    _bind_action(root, "<Control-Alt-Right>", select_next_workflow)
    _bind_action(root, "<F5>", reload_current)
    for index, spec in enumerate(workflow_specs, start=1):
        _bind_action(
            root,
            f"<Control-Alt-Key-{index}>",
            lambda key=spec.key: open_tool(key),
        )
    for index in range(1, MAX_DIRECT_SESSION_SHORTCUT + 1):
        _bind_action(
            root,
            f"<Control-Key-{index}>",
            lambda index=index: select_hosted_session_at_index(index),
        )

    return menubar
