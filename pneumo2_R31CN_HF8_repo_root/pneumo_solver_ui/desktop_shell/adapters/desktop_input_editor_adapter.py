from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_input_editor import DesktopInputEditor

from ..contracts import DesktopShellToolSpec


def create_hosted_input_editor(parent: tk.Misc) -> DesktopInputEditor:
    return DesktopInputEditor(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_input_editor",
        title="Исходные данные и расчет",
        description="Редактор геометрии, пневматики, механики и настроек расчета.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.desktop_input_editor",
        create_hosted=create_hosted_input_editor,
    )
