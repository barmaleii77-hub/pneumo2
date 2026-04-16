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
    return DesktopEngineeringAnalysisCenter(
        host=parent,
        runtime=runtime,
        repo_root=repo_root,
        hosted=True,
    )


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_engineering_analysis_center",
        title="Engineering Analysis",
        description="Consumer HO-007: selected optimization run, influence artifacts, compare integrity and HO-009 evidence handoff.",
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
            "Открывает frozen selected_run_contract.json из HO-007 как master-source "
            "для анализа, показывает objective/hard-gate/baseline lineage и готовит "
            "HO-009 evidence manifest без финализации diagnostics bundle."
        ),
        menu_order=55,
        nav_order=55,
        primary=False,
        standalone_module="pneumo_solver_ui.tools.desktop_engineering_analysis_center",
        create_hosted=create_hosted_engineering_analysis_center,
        source_of_truth_role="derived",
        search_aliases=(
            "engineering analysis",
            "selected_run_contract",
            "HO-007",
            "HO-009",
            "influence",
            "sensitivity",
            "инженерный анализ",
            "контракт выбранного прогона",
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
