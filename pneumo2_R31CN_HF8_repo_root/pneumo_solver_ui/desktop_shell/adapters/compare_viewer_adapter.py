from __future__ import annotations

from ..contracts import DesktopShellToolSpec
from ..external_launch import spawn_module


def _launch_compare_viewer() -> object:
    return spawn_module("pneumo_solver_ui.qt_compare_viewer")


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="compare_viewer",
        title="Сравнение прогонов",
        description="Внешнее окно сравнения прогонов, трасс и характерных отличий между вариантами.",
        group="Внешние окна",
        mode="external",
        workflow_stage="analysis",
        entry_kind="external",
        capability_ids=("results.compare", "analysis.compare_runs"),
        launch_contexts=("results", "analysis"),
        menu_section="Анализ",
        nav_section="Анализ",
        details="Сравнение результатов расчёта по нескольким прогонам и вариантам настройки.",
        menu_order=60,
        nav_order=60,
        standalone_module="pneumo_solver_ui.qt_compare_viewer",
        launch_external=_launch_compare_viewer,
    )
