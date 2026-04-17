from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


WorkspaceKind = Literal["main", "support"]
LaunchSurfaceKind = Literal["workspace", "external_window", "legacy_bridge", "tooling"]
CommandKind = Literal["open_workspace", "launch_module", "hosted_action"]


@dataclass(frozen=True)
class DesktopWorkspaceSpec:
    workspace_id: str
    title: str
    group: str
    route_order: int
    kind: WorkspaceKind
    summary: str
    source_of_truth: str
    launch_surface: LaunchSurfaceKind
    next_step: str
    hard_gate: str
    details: str = ""
    units_policy: str = ""
    graphics_policy: str = ""
    capability_ids: tuple[str, ...] = ()
    search_aliases: tuple[str, ...] = ()
    quick_action_ids: tuple[str, ...] = ()
    workspace_owner: str = ""
    region: str = ""
    automation_id: str = ""
    tooltip_id: str = ""
    help_id: str = ""
    availability: str = ""
    access_key: str = ""
    hotkey: str = ""
    tab_index: float | None = None
    catalog_owner_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DesktopShellCommandSpec:
    command_id: str
    title: str
    summary: str
    workspace_id: str
    kind: CommandKind
    route_label: str
    target_workspace_id: str | None = None
    module: str | None = None
    capability_ids: tuple[str, ...] = ()
    search_aliases: tuple[str, ...] = ()
    web_aliases: tuple[str, ...] = ()
    launch_surface: LaunchSurfaceKind = "workspace"
    status_label: str = "Доступно"
    help_topic_id: str | None = None
    automation_id: str = ""
    tooltip_id: str = ""
    availability: str = ""
    access_key: str = ""
    hotkey: str = ""


@dataclass(frozen=True)
class DesktopHelpTopicSpec:
    topic_id: str
    title: str
    summary: str
    source_of_truth: str
    units_policy: str
    next_step: str
    hard_gate: str
    graphics_policy: str
    tooltip_text: str = ""
    why_it_matters: str = ""
    result_location: str = ""
