from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.run_autotest_gui import App

from ..contracts import DesktopShellToolSpec


def create_hosted_autotest(parent: tk.Misc) -> App:
    return App(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="autotest_gui",
        title="Autotest Harness",
        description="Отдельное окно для запуска autotest без общего центра проверок.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.run_autotest_gui",
        create_hosted=create_hosted_autotest,
    )
