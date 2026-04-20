from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.send_results_gui import SendResultsGUI

from ..contracts import DesktopShellToolSpec


def create_hosted_send_results(parent: tk.Misc) -> SendResultsGUI:
    return SendResultsGUI(parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="send_results_gui",
        title="Скопировать архив",
        description="Копирование сохранённого архива проекта и сопроводительных материалов.",
        group="Встроенные окна",
        mode="hosted",
        menu_section="Инструменты",
        nav_section="Инструменты",
        details="Копирование архива проекта и сопроводительных файлов для ручной передачи.",
        menu_order=150,
        nav_order=150,
        standalone_module="pneumo_solver_ui.tools.send_results_gui",
        create_hosted=create_hosted_send_results,
    )
