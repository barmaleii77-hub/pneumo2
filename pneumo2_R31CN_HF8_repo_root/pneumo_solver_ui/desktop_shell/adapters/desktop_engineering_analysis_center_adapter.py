from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from pneumo_solver_ui.desktop_engineering_analysis_runtime import (
    DesktopEngineeringAnalysisRuntime,
)
from pneumo_solver_ui.tools.desktop_engineering_analysis_center import (
    DesktopEngineeringAnalysisCenter,
)

from ..contracts import DesktopShellToolSpec


def create_hosted_engineering_analysis_center(parent: tk.Misc) -> DesktopEngineeringAnalysisCenter:
    repo_root = Path(__file__).resolve().parents[3]
    runtime = DesktopEngineeringAnalysisRuntime(
        repo_root=repo_root,
        python_executable=sys.executable,
    )
    return DesktopEngineeringAnalysisCenter(parent, runtime=runtime)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_engineering_analysis_center",
        title="Инженерный анализ",
        description=(
            "Анализ результатов оптимизации: влияние параметров, контроль целостности "
            "сравнения и подготовка материалов для проверки и отправки."
        ),
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="analysis",
        entry_kind="contextual",
        capability_ids=(
            "analysis.influence_and_exploration",
            "analysis.selected_run_contract",
            "analysis.evidence_handoff",
        ),
        launch_contexts=("analysis", "optimization", "results"),
        menu_section="Результаты",
        nav_section="Результаты",
        details=(
            "Открывает выбранный прогон как неизменяемую основу анализа, показывает цель, "
            "ограничения и связь с базовым прогоном, затем готовит подтверждающие материалы "
            "без автоматической финализации архива для отправки."
        ),
        menu_order=55,
        nav_order=55,
        primary=False,
        standalone_module="pneumo_solver_ui.tools.desktop_engineering_analysis_center",
        create_hosted=create_hosted_engineering_analysis_center,
        source_of_truth_role="derived",
        search_aliases=(
            "engineering analysis",
            "HO-007",
            "HO-009",
            "influence",
            "sensitivity",
            "инженерный анализ",
            "выбранный прогон",
            "влияние параметров",
        ),
        context_handoff_keys=(
            "selected_tool_key",
            "workflow_stage",
            "selected_run_dir",
            "selected_artifact",
            "source_of_truth_role",
            "project_name",
            "project_dir",
            "workspace_dir",
            "repo_root",
            "selected_run_contract_path",
            "selected_run_contract_hash",
            "objective_contract_hash",
            "active_baseline_hash",
            "suite_snapshot_hash",
        ),
    )
