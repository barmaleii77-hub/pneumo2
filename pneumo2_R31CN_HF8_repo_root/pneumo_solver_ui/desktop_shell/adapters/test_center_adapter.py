from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.test_center_gui import App

from ..contracts import DesktopShellToolSpec


def create_hosted_test_center(parent: tk.Misc) -> App:
    return App(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="test_center",
        title="Baseline и проверки",
        description="Baseline-прогоны, контрольные тесты и первичная проверка результатов из одного понятного места.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="calculation",
        entry_kind="main",
        capability_ids=(
            "calculation.runs",
            "calculation.preflight",
            "calculation.validation",
        ),
        launch_contexts=("home", "data", "scenarios", "results"),
        menu_section="Расчёт",
        nav_section="Расчёт",
        details="Раздел держит baseline-прогон, контрольные тесты, проверку готовности и прямой переход к анализу результатов без скрытых маршрутов.",
        menu_order=30,
        nav_order=30,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.test_center_gui",
        create_hosted=create_hosted_test_center,
    )
