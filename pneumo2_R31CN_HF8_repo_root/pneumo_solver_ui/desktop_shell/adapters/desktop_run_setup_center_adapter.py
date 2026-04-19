from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pneumo_solver_ui.tools.desktop_input_editor import DesktopInputEditor
from pneumo_solver_ui.tools.desktop_run_setup_center import DesktopRunSetupCenter

from ..contracts import DesktopShellToolSpec


class HostedRunSetupCenter:
    def __init__(self, parent: tk.Misc) -> None:
        self._editor_host = ttk.Frame(parent)
        self.editor = DesktopInputEditor(host=self._editor_host, hosted=True)
        self.center = DesktopRunSetupCenter(self.editor, host=parent)

    def on_host_close(self) -> None:
        try:
            self.center.on_host_close()
        finally:
            self.editor.on_host_close()


def create_hosted_run_setup_center(parent: tk.Misc) -> HostedRunSetupCenter:
    return HostedRunSetupCenter(parent)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_run_setup_center",
        title="Базовый прогон",
        description="Настройка расчёта и запуск базового прогона после проверки набора испытаний.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="calculation",
        entry_kind="main",
        capability_ids=(
            "calculation.run_setup",
            "calculation.baseline_run",
            "calculation.launch",
        ),
        launch_contexts=("home", "suite", "optimization", "results"),
        menu_section="Расчёт",
        nav_section="Расчёт",
        details=(
            "Здесь выбираются профиль запуска, предпросмотр дороги, режим расчёта, "
            "поведение при предупреждениях и выгрузка результатов перед оптимизацией."
        ),
        menu_order=35,
        nav_order=35,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.desktop_run_setup_center",
        create_hosted=create_hosted_run_setup_center,
        search_aliases=(
            "базовый прогон",
            "опорный прогон",
            "настройка расчёта",
            "запуск расчёта",
            "предпросмотр дороги",
        ),
        tooltip="Настройте расчёт и создайте базовый прогон перед оптимизацией.",
        help_topic=(
            "Базовый прогон связывает проверенный набор испытаний с оптимизацией: "
            "сначала проверьте набор, затем настройте расчёт и запустите опорный прогон."
        ),
    )
