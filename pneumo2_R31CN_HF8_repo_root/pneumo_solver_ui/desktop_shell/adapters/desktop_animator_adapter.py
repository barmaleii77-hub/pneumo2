from __future__ import annotations

from pathlib import Path

from ..contracts import DesktopShellToolSpec
from ..external_launch import repo_root, spawn_module


def _default_analysis_context_path() -> Path:
    return (
        repo_root()
        / "pneumo_solver_ui"
        / "workspace"
        / "handoffs"
        / "WS-ANALYSIS"
        / "analysis_context.json"
    ).resolve()


def _launch_desktop_animator() -> object:
    analysis_context = _default_analysis_context_path()
    if analysis_context.exists():
        return spawn_module(
            "pneumo_solver_ui.desktop_animator.app",
            args=("--analysis-context", str(analysis_context), "--no-follow"),
            env_updates={"PNEUMO_ANALYSIS_CONTEXT_PATH": str(analysis_context)},
        )
    return spawn_module("pneumo_solver_ui.desktop_animator.app")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_animator",
        title="Аниматор",
        description="Визуализация движения подвески, хода цилиндров и поведения модели по результатам расчёта.",
        group="Внешние окна",
        mode="external",
        workflow_stage="visualization",
        entry_kind="external",
        capability_ids=("results.animator", "visualization.suspension_motion"),
        launch_contexts=("data", "results", "analysis"),
        menu_section="Визуализация",
        nav_section="Визуализация",
        details="Наглядная анимированная проверка кинематики, хода и поведения подвески на дорожном профиле.",
        menu_order=70,
        nav_order=70,
        standalone_module="pneumo_solver_ui.desktop_animator.app",
        launch_external=_launch_desktop_animator,
        search_aliases=("HO-008", "analysis_context", "animator_link_contract"),
        context_handoff_keys=(
            "selected_tool_key",
            "workflow_stage",
            "selected_artifact",
            "source_of_truth_role",
            "analysis_context_path",
            "analysis_context_hash",
            "animator_link_contract_hash",
            "selected_run_contract_hash",
            "selected_result_artifact_pointer",
            "selected_npz_path",
            "run_id",
            "objective_contract_hash",
            "suite_snapshot_hash",
            "problem_hash",
            "project_name",
            "workspace_dir",
            "repo_root",
        ),
    )
