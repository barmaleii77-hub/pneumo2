from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .contracts import DesktopShellToolSpec
from .lifecycle import HostedToolSession


HOME_WORKSPACE_KEY = "__home__"
MAX_DIRECT_SESSION_SHORTCUT = 9
PRIMARY_WORKFLOW_KEYS = (
    "desktop_input_editor",
    "desktop_ring_editor",
    "test_center",
    "desktop_optimizer_center",
    "desktop_results_center",
)


def ordered_hosted_sessions(
    notebook: ttk.Notebook,
    sessions: dict[str, HostedToolSession],
) -> tuple[HostedToolSession, ...]:
    frame_to_session = {str(session.frame): session for session in sessions.values()}
    ordered: list[HostedToolSession] = []
    for tab_id in notebook.tabs():
        session = frame_to_session.get(str(tab_id))
        if session is not None:
            ordered.append(session)
    return tuple(ordered)


def workflow_step_index(key: str) -> int | None:
    try:
        return PRIMARY_WORKFLOW_KEYS.index(key) + 1
    except ValueError:
        return None


def workflow_step_badge(key: str) -> str | None:
    step_index = workflow_step_index(key)
    if step_index is None:
        return None
    return f"(Шаг {step_index})"


def numbered_session_label(session: HostedToolSession, index: int) -> str:
    workflow_badge = workflow_step_badge(session.key)
    if workflow_badge is None:
        return f"{index}. {session.spec.title}"
    return f"{index}. {workflow_badge} {session.spec.title}"


def numbered_recently_closed_label(spec: DesktopShellToolSpec, index: int) -> str:
    workflow_badge = workflow_step_badge(spec.key)
    if workflow_badge is None:
        return f"{index}. {spec.title}"
    return f"{index}. {workflow_badge} {spec.title}"


def ordered_workflow_specs(
    specs: tuple[DesktopShellToolSpec, ...],
) -> tuple[DesktopShellToolSpec, ...]:
    spec_by_key = {spec.key: spec for spec in specs}
    return tuple(
        spec_by_key[key]
        for key in PRIMARY_WORKFLOW_KEYS
        if key in spec_by_key
    )


def next_workflow_spec(
    specs: tuple[DesktopShellToolSpec, ...],
    open_keys: set[str],
) -> DesktopShellToolSpec | None:
    workflow_specs = ordered_workflow_specs(specs)
    if not workflow_specs:
        return None
    for spec in workflow_specs:
        if spec.key not in open_keys:
            return spec
    return workflow_specs[-1]


def describe_workflow_progress(
    specs: tuple[DesktopShellToolSpec, ...],
    open_keys: set[str],
) -> str:
    workflow_specs = ordered_workflow_specs(specs)
    if not workflow_specs:
        return "Основной маршрут пока недоступен в текущей сборке shell."

    open_count = sum(1 for spec in workflow_specs if spec.key in open_keys)
    next_spec = next_workflow_spec(workflow_specs, open_keys)
    if open_count < len(workflow_specs) and next_spec is not None:
        return (
            f"Открыто этапов маршрута: {open_count}/{len(workflow_specs)}. "
            f"Следующий рекомендуемый этап: {next_spec.title}."
        )
    return (
        f"Все этапы маршрута уже открыты: {open_count}/{len(workflow_specs)}. "
        "Можно вернуться к нужному шагу в любой момент."
    )


def describe_workflow_status(
    specs: tuple[DesktopShellToolSpec, ...],
    open_keys: set[str],
) -> str:
    workflow_specs = ordered_workflow_specs(specs)
    if not workflow_specs:
        return "Маршрут: недоступен"

    open_count = sum(1 for spec in workflow_specs if spec.key in open_keys)
    next_spec = next_workflow_spec(workflow_specs, open_keys)
    if open_count < len(workflow_specs) and next_spec is not None:
        return f"Маршрут: {open_count}/{len(workflow_specs)} -> {next_spec.title}"
    return f"Маршрут: {open_count}/{len(workflow_specs)} открыто"


def ordered_open_workflow_sessions(
    sessions: dict[str, HostedToolSession],
    workflow_specs: tuple[DesktopShellToolSpec, ...],
) -> tuple[HostedToolSession, ...]:
    ordered_workflow = ordered_workflow_specs(workflow_specs)
    ordered: list[HostedToolSession] = []
    for spec in ordered_workflow:
        session = sessions.get(spec.key)
        if session is not None and int(session.frame.winfo_exists()):
            ordered.append(session)
    return tuple(ordered)


def home_tab_title(open_count: int) -> str:
    if open_count <= 0:
        return "Главная"
    return f"Главная ({open_count})"


def hosted_session_at_index(
    notebook: ttk.Notebook,
    sessions: dict[str, HostedToolSession],
    index: int,
) -> HostedToolSession | None:
    if index < 1:
        return None
    ordered = ordered_hosted_sessions(notebook, sessions)
    if index > len(ordered):
        return None
    return ordered[index - 1]


def selected_workspace_key(
    root: tk.Misc,
    notebook: ttk.Notebook,
    home_tab: ttk.Frame,
    sessions: dict[str, HostedToolSession],
) -> str | None:
    current = notebook.select()
    if not current:
        return None
    widget = root.nametowidget(current)
    if widget == home_tab:
        return HOME_WORKSPACE_KEY
    for session in sessions.values():
        if session.frame == widget:
            return session.key
    return None


def workspace_key_at_tab_index(
    root: tk.Misc,
    notebook: ttk.Notebook,
    home_tab: ttk.Frame,
    sessions: dict[str, HostedToolSession],
    tab_index: int,
) -> str | None:
    tabs = notebook.tabs()
    if tab_index < 0 or tab_index >= len(tabs):
        return None

    try:
        widget = root.nametowidget(tabs[tab_index])
    except Exception:
        return None
    if widget == home_tab:
        return HOME_WORKSPACE_KEY
    for session in sessions.values():
        if session.frame == widget:
            return session.key
    return None


def workspace_tab_index_at_pointer(
    notebook: ttk.Notebook,
    x: int,
    y: int,
) -> int | None:
    try:
        return int(notebook.index(f"@{x},{y}"))
    except Exception:
        return None


def describe_workspace_state(
    root: tk.Misc,
    notebook: ttk.Notebook,
    home_tab: ttk.Frame,
    sessions: dict[str, HostedToolSession],
) -> str:
    ordered = ordered_hosted_sessions(notebook, sessions)
    current_key = selected_workspace_key(root, notebook, home_tab, sessions)
    open_count = len(ordered)

    if current_key == HOME_WORKSPACE_KEY:
        return f"Главная | Встроенных окон: {open_count}"
    if current_key is None:
        return f"Рабочая область не выбрана | Встроенных окон: {open_count}"

    session = sessions.get(current_key)
    if session is None:
        return f"Вкладка не распознана | Встроенных окон: {open_count}"
    return f"Активно: {session.spec.title} | Встроенных окон: {open_count}"


def find_neighbor_hosted_session(
    root: tk.Misc,
    notebook: ttk.Notebook,
    home_tab: ttk.Frame,
    sessions: dict[str, HostedToolSession],
    *,
    step: int,
) -> HostedToolSession | None:
    ordered = ordered_hosted_sessions(notebook, sessions)
    if not ordered:
        return None

    current_key = selected_workspace_key(root, notebook, home_tab, sessions)
    if current_key == HOME_WORKSPACE_KEY:
        return ordered[0] if step >= 0 else ordered[-1]

    keys = [session.key for session in ordered]
    if current_key not in keys:
        return ordered[0] if step >= 0 else ordered[-1]

    current_index = keys.index(current_key)
    next_index = (current_index + step) % len(ordered)
    return ordered[next_index]


def find_neighbor_workflow_session(
    root: tk.Misc,
    notebook: ttk.Notebook,
    home_tab: ttk.Frame,
    sessions: dict[str, HostedToolSession],
    workflow_specs: tuple[DesktopShellToolSpec, ...],
    *,
    step: int,
) -> HostedToolSession | None:
    ordered = ordered_open_workflow_sessions(sessions, workflow_specs)
    if not ordered:
        return None

    current_key = selected_workspace_key(root, notebook, home_tab, sessions)
    if current_key == HOME_WORKSPACE_KEY:
        return ordered[0] if step >= 0 else ordered[-1]

    keys = [session.key for session in ordered]
    if current_key not in keys:
        return ordered[0] if step >= 0 else ordered[-1]

    current_index = keys.index(current_key)
    next_index = (current_index + step) % len(ordered)
    return ordered[next_index]
