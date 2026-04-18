from __future__ import annotations

from dataclasses import dataclass, field
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .contracts import DesktopShellToolSpec
from .lifecycle import HostedToolSession
from .navigation import (
    HOME_WORKSPACE_KEY,
    numbered_recently_closed_label,
    numbered_session_label,
    ordered_workflow_specs,
)


@dataclass
class ShellToolbarController:
    frame: ttk.Frame
    workflow_specs: tuple[DesktopShellToolSpec, ...]
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]]
    select_hosted_session: Callable[[str], bool]
    selected_workspace_key: Callable[[], str | None]
    has_open_workflow_sessions: Callable[[], bool]
    list_recently_closed_specs: Callable[[], tuple[DesktopShellToolSpec, ...]]
    reopen_recently_closed_at_index: Callable[[int], bool]
    continue_workflow_button: ttk.Button
    previous_workflow_button: ttk.Button
    next_workflow_button: ttk.Button
    previous_button: ttk.Button
    next_button: ttk.Button
    reload_button: ttk.Button
    close_button: ttk.Button
    session_picker_var: tk.StringVar
    session_picker: ttk.Combobox
    focus_button: ttk.Button
    recently_closed_picker_var: tk.StringVar
    recently_closed_picker: ttk.Combobox
    reopen_button: ttk.Button
    session_label_to_key: dict[str, str] = field(default_factory=dict)
    recently_closed_label_to_index: dict[str, int] = field(default_factory=dict)

    def refresh(self) -> None:
        sessions = self.list_open_sessions()
        current_key = self.selected_workspace_key()
        has_sessions = bool(sessions)
        has_workflow_sessions = self.has_open_workflow_sessions()
        has_active_hosted_session = bool(current_key and current_key != HOME_WORKSPACE_KEY)

        self.continue_workflow_button.configure(
            state="normal" if self.workflow_specs else "disabled"
        )
        self.previous_workflow_button.configure(state="normal" if has_workflow_sessions else "disabled")
        self.next_workflow_button.configure(state="normal" if has_workflow_sessions else "disabled")
        self.previous_button.configure(state="normal" if has_sessions else "disabled")
        self.next_button.configure(state="normal" if has_sessions else "disabled")
        self.reload_button.configure(state="normal" if has_active_hosted_session else "disabled")
        self.close_button.configure(state="normal" if has_active_hosted_session else "disabled")

        self.session_label_to_key = {
            numbered_session_label(session, index): session.key
            for index, session in enumerate(sessions, start=1)
        }
        recently_closed_specs = self.list_recently_closed_specs()
        self.recently_closed_label_to_index = {
            numbered_recently_closed_label(spec, index): index
            for index, spec in enumerate(recently_closed_specs, start=1)
        }
        labels = list(self.session_label_to_key.keys())
        if not labels:
            self.session_picker_var.set("")
            self.session_picker.configure(values=(), state="disabled")
            self.focus_button.configure(state="disabled")
        else:
            self.session_picker.configure(values=labels, state="readonly")
            current_label = None
            if current_key and current_key != HOME_WORKSPACE_KEY:
                for label, key in self.session_label_to_key.items():
                    if key == current_key:
                        current_label = label
                        break

            if current_label is not None:
                self.session_picker_var.set(current_label)
            elif self.session_picker_var.get() not in labels:
                self.session_picker_var.set(labels[0])
            self.focus_button.configure(state="normal")

        recently_closed_labels = list(self.recently_closed_label_to_index.keys())
        if not recently_closed_labels:
            self.recently_closed_picker_var.set("")
            self.recently_closed_picker.configure(values=(), state="disabled")
            self.reopen_button.configure(state="disabled")
            return

        self.recently_closed_picker.configure(values=recently_closed_labels, state="readonly")
        if self.recently_closed_picker_var.get() not in recently_closed_labels:
            self.recently_closed_picker_var.set(recently_closed_labels[0])
        self.reopen_button.configure(state="normal")

    def focus_selected_session(self) -> bool:
        key = self.session_label_to_key.get(self.session_picker_var.get().strip())
        if not key:
            self.refresh()
            return False
        return self.select_hosted_session(key)

    def reopen_selected_recently_closed(self) -> bool:
        index = self.recently_closed_label_to_index.get(
            self.recently_closed_picker_var.get().strip()
        )
        if index is None:
            self.refresh()
            return False
        return self.reopen_recently_closed_at_index(index)


def build_shell_toolbar(
    parent: tk.Misc,
    *,
    hosted_specs: tuple[DesktopShellToolSpec, ...],
    external_specs: tuple[DesktopShellToolSpec, ...],
    list_open_sessions: Callable[[], tuple[HostedToolSession, ...]],
    selected_workspace_key: Callable[[], str | None],
    select_hosted_session: Callable[[str], bool],
    continue_workflow: Callable[[], None],
    has_open_workflow_sessions: Callable[[], bool],
    select_previous_workflow: Callable[[], None],
    select_next_workflow: Callable[[], None],
    list_recently_closed_specs: Callable[[], tuple[DesktopShellToolSpec, ...]],
    reopen_recently_closed_at_index: Callable[[int], bool],
    select_home: Callable[[], None],
    select_previous_hosted: Callable[[], None],
    select_next_hosted: Callable[[], None],
    reload_current: Callable[[], None],
    close_current: Callable[[], None],
    open_tool: Callable[[str], None],
) -> ShellToolbarController:
    frame = ttk.Frame(parent, padding=(10, 8, 10, 6))
    workflow_specs = ordered_workflow_specs(hosted_specs)

    ttk.Button(frame, text="Главная", command=select_home).pack(side="left")
    continue_workflow_button = ttk.Button(
        frame,
        text="Следующий раздел",
        command=continue_workflow,
    )
    continue_workflow_button.pack(side="left", padx=(6, 0))
    previous_workflow_button = ttk.Button(
        frame,
        text="Раздел назад",
        command=select_previous_workflow,
    )
    previous_workflow_button.pack(side="left", padx=(6, 0))
    next_workflow_button = ttk.Button(
        frame,
        text="Раздел вперед",
        command=select_next_workflow,
    )
    next_workflow_button.pack(side="left", padx=(6, 0))
    previous_button = ttk.Button(frame, text="Предыдущее", command=select_previous_hosted)
    previous_button.pack(side="left", padx=(6, 0))
    next_button = ttk.Button(frame, text="Следующее", command=select_next_hosted)
    next_button.pack(side="left", padx=(6, 0))
    reload_button = ttk.Button(frame, text="Перезагрузить", command=reload_current)
    reload_button.pack(side="left", padx=(12, 0))
    close_button = ttk.Button(frame, text="Закрыть", command=close_current)
    close_button.pack(side="left", padx=(6, 0))

    ttk.Separator(frame, orient="vertical").pack(side="left", fill="y", padx=12)

    ttk.Label(frame, text="Быстро открыть:").pack(side="left")
    specs = hosted_specs + external_specs
    title_to_key = {
        f"{spec.group}: {spec.title}": spec.key
        for spec in specs
    }
    title_values = list(title_to_key.keys())
    quick_open_var = tk.StringVar(value=title_values[0] if title_values else "")
    picker = ttk.Combobox(
        frame,
        textvariable=quick_open_var,
        values=title_values,
        width=28,
        state="readonly" if title_values else "disabled",
    )
    picker.pack(side="left", padx=(6, 6))

    def _open_selected() -> None:
        key = title_to_key.get(quick_open_var.get().strip())
        if key:
            open_tool(key)

    ttk.Button(frame, text="Открыть окно", command=_open_selected).pack(side="left")
    ttk.Separator(frame, orient="vertical").pack(side="left", fill="y", padx=12)
    ttk.Label(frame, text="Окна:").pack(side="left")

    session_picker_var = tk.StringVar(value="")
    session_picker = ttk.Combobox(
        frame,
        textvariable=session_picker_var,
        values=(),
        width=22,
        state="disabled",
    )
    session_picker.pack(side="left", padx=(6, 6))
    focus_button = ttk.Button(frame, text="Перейти", state="disabled")
    focus_button.pack(side="left")
    ttk.Separator(frame, orient="vertical").pack(side="left", fill="y", padx=12)
    ttk.Label(frame, text="Недавние:").pack(side="left")

    recently_closed_picker_var = tk.StringVar(value="")
    recently_closed_picker = ttk.Combobox(
        frame,
        textvariable=recently_closed_picker_var,
        values=(),
        width=22,
        state="disabled",
    )
    recently_closed_picker.pack(side="left", padx=(6, 6))
    reopen_button = ttk.Button(frame, text="Вернуть", state="disabled")
    reopen_button.pack(side="left")

    controller = ShellToolbarController(
        frame=frame,
        workflow_specs=workflow_specs,
        list_open_sessions=list_open_sessions,
        select_hosted_session=select_hosted_session,
        selected_workspace_key=selected_workspace_key,
        has_open_workflow_sessions=has_open_workflow_sessions,
        list_recently_closed_specs=list_recently_closed_specs,
        reopen_recently_closed_at_index=reopen_recently_closed_at_index,
        continue_workflow_button=continue_workflow_button,
        previous_workflow_button=previous_workflow_button,
        next_workflow_button=next_workflow_button,
        previous_button=previous_button,
        next_button=next_button,
        reload_button=reload_button,
        close_button=close_button,
        session_picker_var=session_picker_var,
        session_picker=session_picker,
        focus_button=focus_button,
        recently_closed_picker_var=recently_closed_picker_var,
        recently_closed_picker=recently_closed_picker,
        reopen_button=reopen_button,
    )
    focus_button.configure(command=controller.focus_selected_session)
    session_picker.bind(
        "<<ComboboxSelected>>",
        lambda _event: controller.focus_selected_session(),
    )
    reopen_button.configure(command=controller.reopen_selected_recently_closed)
    recently_closed_picker.bind(
        "<<ComboboxSelected>>",
        lambda _event: controller.reopen_selected_recently_closed(),
    )
    controller.refresh()
    return controller
