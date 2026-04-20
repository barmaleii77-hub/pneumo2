from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.run_full_diagnostics_gui import App

from ..contracts import DesktopShellToolSpec


def create_hosted_full_diagnostics(parent: tk.Misc) -> App:
    return App(parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="full_diagnostics_gui",
        title="Расширенная проверка проекта",
        description="Проверка архива проекта, прогонов и расширенной технической информации.",
        group="Встроенные окна",
        mode="hosted",
        menu_section="Инструменты",
        nav_section="Инструменты",
        details="Расширенная проверка для углублённого разбора состояния проекта и файлов.",
        menu_order=140,
        nav_order=140,
        standalone_module="pneumo_solver_ui.tools.run_full_diagnostics_gui",
        create_hosted=create_hosted_full_diagnostics,
    )
