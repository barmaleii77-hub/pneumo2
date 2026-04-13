from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_optimizer_center import DesktopOptimizerCenter

from ..contracts import DesktopShellToolSpec


def create_hosted_optimizer_center(parent: tk.Misc) -> DesktopOptimizerCenter:
    return DesktopOptimizerCenter(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_optimizer_center",
        title="Центр оптимизации",
        description="Scope, search-space, objectives, stage policy, distributed runtime, history и handoff.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.desktop_optimizer_center",
        create_hosted=create_hosted_optimizer_center,
    )
