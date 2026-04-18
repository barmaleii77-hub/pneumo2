from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .contracts import DesktopShellToolSpec
from .lifecycle import (
    HostedToolSession,
    create_hosted_session,
    dispose_hosted_session,
    selected_hosted_session,
)
from .navigation import (
    HOME_WORKSPACE_KEY,
    describe_workspace_state,
    find_neighbor_hosted_session,
    find_neighbor_workflow_session,
    hosted_session_at_index,
    home_tab_title,
    numbered_session_label,
    ordered_open_workflow_sessions,
    ordered_hosted_sessions,
    selected_workspace_key,
    workspace_key_at_tab_index,
    workspace_tab_index_at_pointer,
)

MAX_RECENTLY_CLOSED_HOSTED_SESSIONS = 12


class DesktopWorkspaceManager:
    def __init__(
        self,
        root: tk.Misc,
        notebook: ttk.Notebook,
        home_tab: ttk.Frame,
        *,
        workflow_specs: tuple[DesktopShellToolSpec, ...] = (),
        set_status: Callable[[str], None],
        on_state_changed: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.notebook = notebook
        self.home_tab = home_tab
        self.workflow_specs = workflow_specs
        self._set_status = set_status
        self._on_state_changed = on_state_changed or (lambda: None)
        self.hosted_sessions: dict[str, HostedToolSession] = {}
        self._recently_closed_specs: list[DesktopShellToolSpec] = []

    def _remember_closed_spec(self, spec: DesktopShellToolSpec) -> None:
        self._recently_closed_specs.append(spec)
        if len(self._recently_closed_specs) > MAX_RECENTLY_CLOSED_HOSTED_SESSIONS:
            self._recently_closed_specs = self._recently_closed_specs[-MAX_RECENTLY_CLOSED_HOSTED_SESSIONS:]

    def _notify_state_changed(self) -> None:
        self._refresh_notebook_titles()
        self._on_state_changed()

    def _refresh_notebook_titles(self) -> None:
        sessions = self.list_open_sessions()
        if int(self.home_tab.winfo_exists()):
            self.notebook.tab(self.home_tab, text=home_tab_title(len(sessions)))
        for index, session in enumerate(sessions, start=1):
            if int(session.frame.winfo_exists()):
                self.notebook.tab(session.frame, text=numbered_session_label(session, index))

    def _dispose_session(
        self,
        session: HostedToolSession,
        *,
        update_status: bool,
        remember_closed: bool,
    ) -> None:
        self.hosted_sessions.pop(session.key, None)
        if remember_closed:
            self._remember_closed_spec(session.spec)
        dispose_hosted_session(self.notebook, session)
        if update_status:
            self._set_status(f"Закрыто окно: {session.spec.title}")

    def current_session(self) -> HostedToolSession | None:
        return selected_hosted_session(self.root, self.notebook, self.hosted_sessions)

    def selected_workspace_key(self) -> str | None:
        return selected_workspace_key(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
        )

    def workspace_key_at_index(self, index: int) -> str | None:
        return workspace_key_at_tab_index(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
            index,
        )

    def workspace_tab_index_at_pointer(self, x: int, y: int) -> int | None:
        return workspace_tab_index_at_pointer(self.notebook, x, y)

    def list_open_sessions(self) -> tuple[HostedToolSession, ...]:
        return ordered_hosted_sessions(self.notebook, self.hosted_sessions)

    def list_open_workflow_sessions(self) -> tuple[HostedToolSession, ...]:
        return ordered_open_workflow_sessions(self.hosted_sessions, self.workflow_specs)

    def describe_workspace(self) -> str:
        return describe_workspace_state(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
        )

    def has_recently_closed_sessions(self) -> bool:
        return bool(self._recently_closed_specs)

    def has_open_workflow_sessions(self) -> bool:
        return bool(self.list_open_workflow_sessions())

    def list_recently_closed_specs(self) -> tuple[DesktopShellToolSpec, ...]:
        return tuple(reversed(self._recently_closed_specs))

    def handle_tab_changed(self) -> HostedToolSession | None:
        session = self.current_session()
        if session is None:
            self._set_status("Открыта стартовая страница shell.")
            self._notify_state_changed()
            return None
        self._set_status(f"Активно окно: {session.spec.title}")
        self._notify_state_changed()
        return session

    def select_home_tab(self) -> None:
        self.notebook.select(self.home_tab)
        self._set_status("Открыта стартовая страница shell.")
        self._notify_state_changed()

    def open_hosted_tool(self, spec: DesktopShellToolSpec) -> HostedToolSession:
        existing = self.hosted_sessions.get(spec.key)
        if existing is not None and int(existing.frame.winfo_exists()):
            self.notebook.select(existing.frame)
            self._set_status(f"Окно уже открыто: {spec.title}")
            return existing

        session = create_hosted_session(self.notebook, spec)
        self.hosted_sessions[spec.key] = session
        self.notebook.select(session.frame)
        self._set_status(f"Открыто окно: {spec.title}")
        self._notify_state_changed()
        return session

    def select_hosted_session(self, key: str) -> bool:
        session = self.hosted_sessions.get(key)
        if session is None or not int(session.frame.winfo_exists()):
            self._set_status("Окно уже закрыто или ещё не открыто.")
            return False
        self.notebook.select(session.frame)
        self._set_status(f"Активно окно: {session.spec.title}")
        self._notify_state_changed()
        return True

    def select_hosted_session_at_index(self, index: int) -> bool:
        session = hosted_session_at_index(self.notebook, self.hosted_sessions, index)
        if session is None:
            self._set_status(f"Встроенное окно #{index} пока не открыто.")
            return False
        return self.select_hosted_session(session.key)

    def select_workspace_at_index(self, index: int) -> bool:
        key = self.workspace_key_at_index(index)
        if key == HOME_WORKSPACE_KEY:
            self.select_home_tab()
            return True
        if key is None:
            self._set_status("Вкладка по позиции уже недоступна.")
            return False
        return self.select_hosted_session(key)

    def select_next_hosted_tab(self) -> bool:
        session = find_neighbor_hosted_session(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
            step=1,
        )
        if session is None:
            self._set_status("Нет открытых встроенных окон для перехода.")
            return False
        return self.select_hosted_session(session.key)

    def select_previous_hosted_tab(self) -> bool:
        session = find_neighbor_hosted_session(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
            step=-1,
        )
        if session is None:
            self._set_status("Нет открытых встроенных окон для перехода.")
            return False
        return self.select_hosted_session(session.key)

    def select_next_workflow_tab(self) -> bool:
        session = find_neighbor_workflow_session(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
            self.workflow_specs,
            step=1,
        )
        if session is None:
            self._set_status("Разделы основного маршрута пока не открыты.")
            return False
        return self.select_hosted_session(session.key)

    def select_previous_workflow_tab(self) -> bool:
        session = find_neighbor_workflow_session(
            self.root,
            self.notebook,
            self.home_tab,
            self.hosted_sessions,
            self.workflow_specs,
            step=-1,
        )
        if session is None:
            self._set_status("Разделы основного маршрута пока не открыты.")
            return False
        return self.select_hosted_session(session.key)

    def close_session(self, session: HostedToolSession) -> None:
        self._dispose_session(session, update_status=True, remember_closed=True)
        self._notify_state_changed()

    def dispose_all_hosted_sessions(self, *, remember_closed: bool = False) -> int:
        sessions = list(self.hosted_sessions.values())
        for session in sessions:
            self._dispose_session(
                session,
                update_status=False,
                remember_closed=remember_closed,
            )
        if sessions:
            self._notify_state_changed()
        return len(sessions)

    def shutdown(self) -> int:
        return self.dispose_all_hosted_sessions()

    def close_current_tab(self) -> bool:
        if not self.notebook.select():
            return False
        session = self.current_session()
        if session is None:
            self._set_status("Стартовая страница не закрывается.")
            return False
        self.close_session(session)
        self.select_home_tab()
        return True

    def close_all_hosted_tabs(self) -> int:
        closed_count = self.dispose_all_hosted_sessions(remember_closed=True)
        if int(self.home_tab.winfo_exists()):
            self.notebook.select(self.home_tab)
        if closed_count:
            self._set_status(f"Закрыто встроенных окон: {closed_count}")
        else:
            self._set_status("Встроенные окна уже закрыты.")
        return closed_count

    def reload_current_tab(self) -> bool:
        session = self.current_session()
        if session is None:
            self._set_status("Перезагрузка доступна только для встроенного окна.")
            return False
        spec = session.spec
        self._dispose_session(session, update_status=False, remember_closed=False)
        self.open_hosted_tool(spec)
        self._set_status(f"Перезагружено окно: {spec.title}")
        return True

    def close_other_hosted_tabs(self) -> int:
        current = self.current_session()
        if current is None:
            self._set_status("Закрывать остальные можно только для встроенного окна.")
            return 0

        other_sessions = [
            session
            for session in self.list_open_sessions()
            if session.key != current.key
        ]
        if not other_sessions:
            self._set_status("Других встроенных окон нет.")
            return 0

        for session in other_sessions:
            self._dispose_session(session, update_status=False, remember_closed=True)
        self.notebook.select(current.frame)
        self._notify_state_changed()
        self._set_status(f"Закрыто остальных встроенных окон: {len(other_sessions)}")
        return len(other_sessions)

    def reopen_recently_closed_at_index(self, index: int) -> bool:
        if index < 1 or index > len(self._recently_closed_specs):
            self._set_status(f"Недавно закрытое окно #{index} недоступно.")
            return False

        history_index = len(self._recently_closed_specs) - index
        spec = self._recently_closed_specs.pop(history_index)
        self.open_hosted_tool(spec)
        self._set_status(f"Повторно открыто окно: {spec.title}")
        return True

    def reopen_last_closed_tab(self) -> bool:
        if not self._recently_closed_specs:
            self._set_status("Нет недавно закрытых встроенных окон.")
            return False
        return self.reopen_recently_closed_at_index(1)
