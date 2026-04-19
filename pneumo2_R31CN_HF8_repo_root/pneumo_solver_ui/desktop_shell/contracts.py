from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol
import tkinter as tk


HostedFactory = Callable[[tk.Misc], object]
ExternalLauncher = Callable[[], object]
ToolMode = Literal["hosted", "external"]
ToolkitRuntimeKind = Literal["", "tk", "qt", "process"]
SourceOfTruthRole = Literal["", "master", "derived", "launcher", "support"]
MigrationStatus = Literal["", "native", "managed_external", "in_development"]
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
    runtime_kind: ToolkitRuntimeKind = ""
    workspace_role: str = ""
    source_of_truth_role: SourceOfTruthRole = ""
    search_aliases: tuple[str, ...] = ()
    tooltip: str = ""
    help_topic: str = ""
    context_handoff_keys: tuple[str, ...] = ()
    migration_status: MigrationStatus = ""

    @property
    def is_hosted(self) -> bool:
        return self.mode == "hosted"

    @property
    def is_primary_entry(self) -> bool:
        return self.entry_kind == "main"

    @property
    def is_contextual_entry(self) -> bool:
        return self.entry_kind == "contextual"

    @property
    def effective_runtime_kind(self) -> ToolkitRuntimeKind:
        if self.runtime_kind:
            return self.runtime_kind
        module = str(self.standalone_module or "").lower()
        if self.mode == "hosted":
            return "tk"
        if any(token in module for token in ("qt_compare_viewer", "desktop_animator", "desktop_mnemo")):
            return "qt"
        return "process"

    @property
    def effective_workspace_role(self) -> str:
        if self.workspace_role:
            return self.workspace_role
        if self.entry_kind == "main":
            return "workspace"
        if self.entry_kind == "external":
            return "specialized_window"
        if self.entry_kind == "contextual":
            return "contextual_tool"
        return "tool"

    @property
    def effective_source_of_truth_role(self) -> SourceOfTruthRole:
        if self.source_of_truth_role:
            return self.source_of_truth_role
        by_key: dict[str, SourceOfTruthRole] = {
            "desktop_input_editor": "master",
            "desktop_ring_editor": "master",
            "test_center": "master",
            "desktop_optimizer_center": "master",
            "desktop_results_center": "derived",
            "desktop_engineering_analysis_center": "derived",
            "compare_viewer": "derived",
            "desktop_animator": "derived",
            "desktop_mnemo": "derived",
            "desktop_diagnostics_center": "support",
            "desktop_geometry_reference_center": "support",
            "autotest_gui": "support",
        }
        return by_key.get(self.key, "support")

    @property
    def effective_search_aliases(self) -> tuple[str, ...]:
        base_aliases: dict[str, tuple[str, ...]] = {
            "desktop_input_editor": ("исходные данные", "настройка", "параметры"),
            "desktop_ring_editor": ("сценарии", "редактор кольца", "дорога"),
            "test_center": ("набор испытаний", "проверки", "опорный прогон"),
            "desktop_optimizer_center": ("оптимизация", "опорный прогон", "распределённый расчёт"),
            "desktop_results_center": ("анализ", "результаты", "сравнение", "проверка расчёта"),
            "desktop_engineering_analysis_center": (
                "engineering analysis",
                "calibration",
                "influence",
                "sensitivity",
                "system influence",
                "калибровка",
                "влияние",
                "чувствительность",
            ),
            "desktop_diagnostics_center": ("диагностика", "архив диагностики", "отправка", "самопроверка"),
            "compare_viewer": ("compare viewer", "сравнение прогонов", "npz"),
            "desktop_animator": ("animator", "3d", "viewcube"),
            "desktop_mnemo": ("mnemo", "мнемосхема", "пневмосхема"),
        }
        merged = {item for item in self.search_aliases if str(item or "").strip()}
        merged.update(base_aliases.get(self.key, ()))
        return tuple(sorted(merged))

    @property
    def effective_tooltip(self) -> str:
        return str(self.tooltip or self.description or self.title).strip()

    @property
    def effective_help_topic(self) -> str:
        return str(self.help_topic or self.details or self.description or self.title).strip()

    @property
    def effective_context_handoff_keys(self) -> tuple[str, ...]:
        if self.context_handoff_keys:
            return self.context_handoff_keys
        return (
            "selected_tool_key",
            "workflow_stage",
            "active_optimization_mode",
            "selected_run_dir",
            "selected_artifact",
            "selected_scenario",
            "source_of_truth_role",
            "project_name",
            "project_dir",
            "workspace_dir",
            "repo_root",
        )

    @property
    def effective_migration_status(self) -> MigrationStatus:
        if self.migration_status:
            return self.migration_status
        if self.mode == "hosted" and self.effective_runtime_kind == "tk":
            return "managed_external"
        if self.effective_runtime_kind == "qt":
            return "native"
        return "native"
