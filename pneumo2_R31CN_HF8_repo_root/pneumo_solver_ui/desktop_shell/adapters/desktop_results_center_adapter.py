from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
from pneumo_solver_ui.tools.desktop_results_center import DesktopResultsCenter

from ..contracts import DesktopShellToolSpec


def create_hosted_results_center(parent: tk.Misc) -> DesktopResultsCenter:
    runtime = DesktopResultsRuntime(
        repo_root=Path(__file__).resolve().parents[3],
        python_executable=sys.executable,
    )
    return DesktopResultsCenter(parent, runtime=runtime)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_results_center",
        title="Анализ результатов",
        description="Окно результатов, проверки расчёта и переходов к сравнению, визуализации, проверке и отправке.",
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="results",
        entry_kind="main",
        capability_ids=(
            "results.center",
            "results.compare",
            "results.animator",
            "results.mnemo",
            "results.validation",
            "results.bundle_handoff",
        ),
        launch_contexts=("home", "calculation", "optimization", "analysis"),
        menu_section="Результаты",
        nav_section="Результаты",
        details="Здесь пользователь видит, что именно считалось, какие замечания нашлись, какой следующий шаг рекомендован и как перейти к сравнению, аниматору, проверке и отправке.",
        menu_order=50,
        nav_order=50,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.desktop_results_center",
        create_hosted=create_hosted_results_center,
        search_aliases=(
            "analysis и результаты",
            "analysis",
            "results",
            "compare",
            "проверка расчёта",
        ),
    )
