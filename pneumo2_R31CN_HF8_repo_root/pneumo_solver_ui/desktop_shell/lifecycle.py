from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from .contracts import DesktopShellToolSpec


HOST_CLOSE_METHOD_NAMES: tuple[str, ...] = (
    "on_host_close",
    "_on_stop",
    "_stop",
    "on_close",
)


@dataclass
class HostedToolSession:
    key: str
    spec: DesktopShellToolSpec
    frame: ttk.Frame
    controller: object | None = None


def create_hosted_session(
    notebook: ttk.Notebook,
    spec: DesktopShellToolSpec,
) -> HostedToolSession:
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=spec.title)
    try:
        controller = spec.create_hosted(frame) if spec.create_hosted else None
    except Exception:
        try:
            notebook.forget(frame)
        except Exception:
            pass
        if int(frame.winfo_exists()):
            frame.destroy()
        raise
    return HostedToolSession(
        key=spec.key,
        spec=spec,
        frame=frame,
        controller=controller,
    )


def close_hosted_controller(
    controller: object | None,
    spec: DesktopShellToolSpec,
) -> bool:
    if controller is None:
        return False

    if spec.on_close is not None:
        spec.on_close(controller)
        return True

    for method_name in HOST_CLOSE_METHOD_NAMES:
        handler = getattr(controller, method_name, None)
        if callable(handler):
            handler()
            return True
    return False


def dispose_hosted_session(
    notebook: ttk.Notebook,
    session: HostedToolSession,
) -> None:
    try:
        close_hosted_controller(session.controller, session.spec)
    except Exception:
        pass

    try:
        notebook.forget(session.frame)
    except Exception:
        pass

    if int(session.frame.winfo_exists()):
        session.frame.destroy()


def selected_hosted_session(
    root: tk.Misc,
    notebook: ttk.Notebook,
    sessions: dict[str, HostedToolSession],
) -> HostedToolSession | None:
    current = notebook.select()
    if not current:
        return None
    widget = root.nametowidget(current)
    for session in sessions.values():
        if session.frame == widget:
            return session
    return None
