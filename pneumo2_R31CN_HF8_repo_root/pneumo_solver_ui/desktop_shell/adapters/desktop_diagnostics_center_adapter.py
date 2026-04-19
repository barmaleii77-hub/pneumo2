from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_diagnostics_center import DesktopDiagnosticsCenter

from ..contracts import DesktopShellToolSpec


def create_hosted_diagnostics_center(parent: tk.Misc) -> DesktopDiagnosticsCenter:
    return DesktopDiagnosticsCenter(parent, hosted=True, initial_tab="restore")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_diagnostics_center",
        title="Диагностика",
        description="Единое окно проверки окружения, сборки архива диагностики и подготовки материалов к отправке.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="tools",
        entry_kind="tool",
        capability_ids=(
            "tools.diagnostics",
            "tools.send_bundle",
            "tools.environment",
        ),
        launch_contexts=("data", "results", "tools"),
        menu_section="Инструменты",
        nav_section="Инструменты",
        details="Сводит диагностику, сбор диагностических архивов и подготовку отправки в одно рабочее окно без рассыпания по нескольким экранам.",
        menu_order=140,
        nav_order=140,
        standalone_module="pneumo_solver_ui.tools.desktop_diagnostics_center",
        create_hosted=create_hosted_diagnostics_center,
        search_aliases=(
            "диагностика и отправка",
            "архив диагностики",
            "проверка окружения",
            "восстановление",
        ),
    )
