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


def build_desktop_launch_catalog(*, include_mnemo: bool = True) -> tuple[DesktopLaunchCatalogItem, ...]:
    items: list[DesktopLaunchCatalogItem] = [
        DesktopLaunchCatalogItem(
            key="desktop_gui_spec_shell",
            title="PneumoApp Desktop Shell (GUI-spec)",
            module="pneumo_solver_ui.tools.desktop_gui_spec_shell",
            description=(
                "Канонический PySide6 shell по GUI-spec (17/18): workspace-first маршрут, "
                "global command search, overview dashboard и always-visible diagnostics."
            ),
            group="Главное окно",
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
            )
        )
    return tuple(items)
