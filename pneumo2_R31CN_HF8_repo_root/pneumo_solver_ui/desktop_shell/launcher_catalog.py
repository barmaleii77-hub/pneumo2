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
    items: list[DesktopLaunchCatalogItem] = []
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
