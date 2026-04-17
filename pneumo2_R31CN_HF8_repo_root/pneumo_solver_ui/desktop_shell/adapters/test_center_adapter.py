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
            "suite.validated_snapshot",
            "suite.handoff_ho005",
        ),
        launch_contexts=("home", "data", "scenarios", "results"),
        menu_section="Расчёт",
        nav_section="Расчёт",
        details=(
            "Раздел держит матрицу испытаний, runtime overrides, validated_suite_snapshot, "
            "suite_snapshot_hash и HO-005 handoff в baseline без скрытых маршрутов."
        ),
        menu_order=30,
        nav_order=30,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.test_center_gui",
        create_hosted=create_hosted_test_center,
        search_aliases=(
            "набор испытаний",
            "test matrix",
            "validated suite",
            "validated_suite_snapshot",
            "suite snapshot",
            "suite_snapshot_hash",
            "HO-005",
            "заморозить HO-005",
            "расчетная настройка",
            "run setup",
        ),
        context_handoff_keys=(
            "validated_suite_snapshot",
            "suite_snapshot_hash",
            "inputs_snapshot_hash",
            "ring_source_hash",
            "handoff_id",
            "workspace_dir",
            "repo_root",
        ),
    )
