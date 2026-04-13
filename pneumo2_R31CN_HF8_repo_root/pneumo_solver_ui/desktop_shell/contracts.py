from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol
import tkinter as tk


HostedFactory = Callable[[tk.Misc], object]
ExternalLauncher = Callable[[], object]
ToolMode = Literal["hosted", "external"]


class ShellToolLifecycle(Protocol):
    def on_host_close(self) -> None: ...


@dataclass(frozen=True)
class DesktopShellToolSpec:
    key: str
    title: str
    description: str
    group: str
    mode: ToolMode
    standalone_module: str | None = None
    create_hosted: HostedFactory | None = None
    launch_external: ExternalLauncher | None = None
    on_close: Callable[[object], None] | None = None

    @property
    def is_hosted(self) -> bool:
        return self.mode == "hosted"
