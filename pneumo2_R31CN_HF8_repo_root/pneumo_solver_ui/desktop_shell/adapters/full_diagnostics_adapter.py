from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.run_full_diagnostics_gui import App

from ..contracts import DesktopShellToolSpec


def create_hosted_full_diagnostics(parent: tk.Misc) -> App:
    return App(parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="full_diagnostics_gui",
        title="Полная диагностика",
        description="Диагностический прогон с выбором уровня, путей и smoke-опций.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.run_full_diagnostics_gui",
        create_hosted=create_hosted_full_diagnostics,
    )
