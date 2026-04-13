from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol
import tkinter as tk


HostedFactory = Callable[[tk.Misc], object]
ExternalLauncher = Callable[[], object]
ToolMode = Literal["hosted", "external"]
WorkflowStage = Literal[
    "",
    "overview",
    "data",
    "reference",
    "scenarios",
    "calculation",
    "optimization",
    "results",
    "analysis",
    "visualization",
    "tools",
]
ShellEntryKind = Literal["main", "tool", "contextual", "external"]


class ShellToolLifecycle(Protocol):
    def on_host_close(self) -> None: ...


@dataclass(frozen=True)
class DesktopShellToolSpec:
    key: str
    title: str
    description: str
    group: str
    mode: ToolMode
    workflow_stage: WorkflowStage = ""
    entry_kind: ShellEntryKind = "tool"
    capability_ids: tuple[str, ...] = ()
    launch_contexts: tuple[str, ...] = ()
    menu_section: str = "Инструменты"
    nav_section: str = "Инструменты"
    details: str = ""
    menu_order: int = 100
    nav_order: int = 100
    primary: bool = False
    standalone_module: str | None = None
    create_hosted: HostedFactory | None = None
    launch_external: ExternalLauncher | None = None
    on_close: Callable[[object], None] | None = None

    @property
    def is_hosted(self) -> bool:
        return self.mode == "hosted"

    @property
    def is_primary_entry(self) -> bool:
        return self.entry_kind == "main"

    @property
    def is_contextual_entry(self) -> bool:
        return self.entry_kind == "contextual"
