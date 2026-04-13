from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_geometry_reference_center import (
    DesktopGeometryReferenceCenter,
)

from ..contracts import DesktopShellToolSpec


def create_hosted_geometry_reference(parent: tk.Misc) -> DesktopGeometryReferenceCenter:
    return DesktopGeometryReferenceCenter(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_geometry_reference_center",
        title="Справочники и геометрия",
        description="Каталоги цилиндров, геометрия пружин, схемы и справочник параметров рядом с вводом данных, без web-дублей.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="reference",
        entry_kind="tool",
        capability_ids=(
            "reference.geometry",
            "reference.components",
            "reference.guides",
        ),
        launch_contexts=("data", "optimization", "results"),
        menu_section="Данные",
        nav_section="Инструменты",
        details="Наглядный справочный центр для геометрии подвески, подбора цилиндров и пружин, схемных связей и инженерных пояснений к параметрам.",
        menu_order=15,
        nav_order=115,
        standalone_module="pneumo_solver_ui.tools.desktop_geometry_reference_center",
        create_hosted=create_hosted_geometry_reference,
    )
