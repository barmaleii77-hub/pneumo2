from __future__ import annotations

from dataclasses import dataclass

from .registry import build_desktop_shell_specs


@dataclass(frozen=True)
class DesktopLaunchCatalogItem:
    key: str
    title: str
    module: str
    description: str
    group: str
    runtime_kind: str
    workspace_role: str
    source_of_truth_role: str
    migration_status: str
    search_aliases: tuple[str, ...]
    context_handoff_keys: tuple[str, ...]


def build_desktop_launch_catalog(*, include_mnemo: bool = True) -> tuple[DesktopLaunchCatalogItem, ...]:
    items: list[DesktopLaunchCatalogItem] = [
        DesktopLaunchCatalogItem(
            key="desktop_main_shell_qt",
            title="Desktop Main Shell",
            module="pneumo_solver_ui.tools.desktop_main_shell_qt",
            description=(
                "Главное Windows-окно оператора: верхнее меню, поиск команд, дерево маршрута, "
                "инспектор, status/progress strip и единый запуск GUI-модулей."
            ),
            group="Главное окно",
            runtime_kind="qt",
            workspace_role="workspace",
            source_of_truth_role="launcher",
            migration_status="native",
            search_aliases=(
                "desktop main shell",
                "desktop shell",
                "qt main shell",
                "главное окно",
                "рабочее место инженера",
                "WS-SHELL",
            ),
            context_handoff_keys=(
                "selected_tool_key",
                "workflow_stage",
                "active_optimization_mode",
                "selected_run_dir",
                "selected_artifact",
                "selected_scenario",
                "source_of_truth_role",
            ),
        ),
        DesktopLaunchCatalogItem(
            key="desktop_gui_spec_shell",
            title="Резервный GUI-spec shell",
            module="pneumo_solver_ui.tools.desktop_gui_spec_shell",
            description=(
                "Legacy/reference shell surface. Primary operator launch target is Desktop Main Shell."
            ),
            group="Резервные окна",
            runtime_kind="qt",
            workspace_role="workspace",
            source_of_truth_role="launcher",
            migration_status="in_development",
            search_aliases=(
                "gui spec shell",
                "legacy shell",
                "reference shell",
            ),
            context_handoff_keys=(
                "selected_tool_key",
                "workflow_stage",
                "active_optimization_mode",
                "selected_run_dir",
                "selected_artifact",
                "selected_scenario",
                "source_of_truth_role",
            ),
        )
    ]
    for spec in build_desktop_shell_specs():
        if not include_mnemo and spec.key == "desktop_mnemo":
            continue
        if not spec.standalone_module:
            continue
        items.append(
            DesktopLaunchCatalogItem(
                key=spec.key,
                title=spec.title,
                module=spec.standalone_module,
                description=spec.description,
                group=spec.group,
                runtime_kind=spec.effective_runtime_kind,
                workspace_role=spec.effective_workspace_role,
                source_of_truth_role=spec.effective_source_of_truth_role,
                migration_status=spec.effective_migration_status,
                search_aliases=spec.effective_search_aliases,
                context_handoff_keys=spec.effective_context_handoff_keys,
            )
        )
    return tuple(items)
