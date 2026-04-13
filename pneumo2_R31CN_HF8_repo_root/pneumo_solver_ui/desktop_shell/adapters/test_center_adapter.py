from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.test_center_gui import App

from ..contracts import DesktopShellToolSpec


def create_hosted_test_center(parent: tk.Misc) -> App:
    return App(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="test_center",
        title="Центр проверок",
        description="Автотесты, диагностика и переход к отправке результатов.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.test_center_gui",
        create_hosted=create_hosted_test_center,
    )
