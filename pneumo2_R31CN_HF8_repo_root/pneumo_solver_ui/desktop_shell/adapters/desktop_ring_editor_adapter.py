from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_ring_scenario_editor import DesktopRingScenarioEditor

from ..contracts import DesktopShellToolSpec


def create_hosted_ring_editor(parent: tk.Misc) -> DesktopRingScenarioEditor:
    return DesktopRingScenarioEditor(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_ring_editor",
        title="Сценарии",
        description="Редактор дорожных и кольцевых сценариев с разметкой участков, событий и проверкой сценарного покрытия.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="scenarios",
        entry_kind="main",
        capability_ids=(
            "scenarios.ring_editor",
            "scenarios.coverage_review",
            "optimization.source_ring",
        ),
        launch_contexts=("home", "data", "optimization"),
        menu_section="Сценарии",
        nav_section="Сценарии",
        details="Кольцевой сценарий остаётся главным пользовательским входом для расчёта и автоматической оптимизации.",
        menu_order=20,
        nav_order=20,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.desktop_ring_scenario_editor",
        create_hosted=create_hosted_ring_editor,
    )
