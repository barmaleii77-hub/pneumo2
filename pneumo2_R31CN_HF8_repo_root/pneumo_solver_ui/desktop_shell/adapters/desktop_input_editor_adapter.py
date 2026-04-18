from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_input_editor import DesktopInputEditor

from ..contracts import DesktopShellToolSpec


def create_hosted_input_editor(parent: tk.Misc) -> DesktopInputEditor:
    return DesktopInputEditor(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_input_editor",
        title="Исходные данные",
        description="Основной экран ввода исходных инженерных данных с единицами измерения, подсказками и графическим сопровождением.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="data",
        entry_kind="main",
        capability_ids=(
            "input.machine_data",
            "input.units_and_help",
            "input.graphic_context",
            "calculation.run_setup",
        ),
        launch_contexts=("home", "data", "results"),
        menu_section="Данные",
        nav_section="Исходные данные",
        details="Здесь вводятся геометрия, пневматика, механика, статическая настройка, компоненты и справочные данные без показа служебных JSON-потоков.",
        menu_order=10,
        nav_order=10,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.desktop_input_editor",
        create_hosted=create_hosted_input_editor,
    )
