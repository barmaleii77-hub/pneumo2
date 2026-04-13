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
        description="Сбор bundle и копирование ZIP в буфер обмена без WEB UI.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.send_results_gui",
        create_hosted=create_hosted_send_results,
    )
