from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.run_autotest_gui import App

from ..contracts import DesktopShellToolSpec


def create_hosted_autotest(parent: tk.Misc) -> App:
    return App(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="autotest_gui",
        title="Автотесты",
        description="Отдельный запуск автотестов и пакетной проверки без отвлечения от основного рабочего маршрута.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="tools",
        entry_kind="tool",
        capability_ids=("tools.autotest",),
        launch_contexts=("results", "tools"),
        menu_section="Инструменты",
        nav_section="Инструменты",
        details="Нужен для регрессионной проверки, когда требуется полный прогон тестового контура.",
        menu_order=130,
        nav_order=130,
        standalone_module="pneumo_solver_ui.tools.run_autotest_gui",
        create_hosted=create_hosted_autotest,
    )
