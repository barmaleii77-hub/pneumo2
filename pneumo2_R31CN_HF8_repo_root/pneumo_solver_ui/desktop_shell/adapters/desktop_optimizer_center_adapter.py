from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_optimizer_center import DesktopOptimizerCenter

from ..contracts import DesktopShellToolSpec


def create_hosted_optimizer_center(parent: tk.Misc) -> DesktopOptimizerCenter:
    return DesktopOptimizerCenter(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_optimizer_center",
        title="Оптимизация",
        description="Автоматизированная стадийная оптимизация по кольцевым сценариям с возможностью раскрыть и настроить весь маршрут вручную.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="optimization",
        entry_kind="main",
        capability_ids=(
            "optimization.auto_pipeline",
            "optimization.distributed",
            "optimization.handoff",
            "optimization.packaging",
        ),
        launch_contexts=("home", "scenarios", "results"),
        menu_section="Оптимизация",
        nav_section="Оптимизация",
        details="Окно собирает автоматическую нарезку кольца, спецсценарии, стадии поиска, распределённые вычисления и итоговую инженерную сводку.",
        menu_order=40,
        nav_order=40,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.desktop_optimizer_center",
        create_hosted=create_hosted_optimizer_center,
    )
