from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.send_results_gui import SendResultsGUI

from ..contracts import DesktopShellToolSpec


def create_hosted_send_results(parent: tk.Misc) -> SendResultsGUI:
    return SendResultsGUI(parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="send_results_gui",
        title="Отправка результатов",
        description="Подготовка архива результатов и сопроводительных материалов для передачи.",
        group="Встроенные окна",
        mode="hosted",
        menu_section="Инструменты",
        nav_section="Инструменты",
        details="Центр подготовки архива результатов, сопроводительных файлов и отправки.",
        menu_order=150,
        nav_order=150,
        standalone_module="pneumo_solver_ui.tools.send_results_gui",
        create_hosted=create_hosted_send_results,
    )
