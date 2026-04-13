from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_ring_scenario_editor import DesktopRingScenarioEditor

from ..contracts import DesktopShellToolSpec


def create_hosted_ring_editor(parent: tk.Misc) -> DesktopRingScenarioEditor:
    return DesktopRingScenarioEditor(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_ring_editor",
        title="Редактор кольцевых сценариев",
        description="Сегменты, road/motion/events, diagnostics, preview и генерация spec/road/axay.",
        group="Встроенные окна",
        mode="hosted",
        standalone_module="pneumo_solver_ui.tools.desktop_ring_scenario_editor",
        create_hosted=create_hosted_ring_editor,
    )
