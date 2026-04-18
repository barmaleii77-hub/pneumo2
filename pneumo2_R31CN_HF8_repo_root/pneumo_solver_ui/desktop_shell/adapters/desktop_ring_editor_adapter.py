from __future__ import annotations

import tkinter as tk

from pneumo_solver_ui.tools.desktop_ring_scenario_editor import DesktopRingScenarioEditor

from ..contracts import DesktopShellToolSpec


def create_hosted_ring_editor(parent: tk.Misc) -> DesktopRingScenarioEditor:
    return DesktopRingScenarioEditor(host=parent, hosted=True)


def build_spec() -> DesktopShellToolSpec:
    return DesktopShellToolSpec(
        key="desktop_ring_editor",
        title="Сценарии и редактор кольца",
        description=(
            "WS-RING источник сценариев: редактирование канонического кольца, "
            "проверки, HO-004 export set и handoff в набор испытаний."
        ),
        group="Встроенные окна",
        mode="hosted",
        workflow_stage="scenarios",
        entry_kind="main",
        capability_ids=(
            "scenarios.ring_editor",
            "scenarios.coverage_review",
            "scenarios.handoff_ho004",
            "suite.source_ring_export",
            "optimization.source_ring",
        ),
        launch_contexts=("home", "data", "scenarios", "calculation", "optimization"),
        menu_section="Сценарии",
        nav_section="Сценарии",
        details=(
            "Прямой hosted entry для WS-RING: выбор в дереве/поиске сразу открывает "
            "редактор сценария без дополнительной навигации. ring_source_of_truth_json "
            "остаётся editable source, а scenario_json, road_csv, axay_csv, meta_json, "
            "HO-004 export set и HO-005 suite link являются derived/consumer handoff."
        ),
        menu_order=20,
        nav_order=20,
        primary=True,
        standalone_module="pneumo_solver_ui.tools.desktop_ring_scenario_editor",
        create_hosted=create_hosted_ring_editor,
        workspace_role="workspace",
        source_of_truth_role="master",
        search_aliases=(
            "WS-RING",
            "HO-004",
            "HO-005",
            "ring source",
            "ring export",
            "source-of-truth",
            "validated suite",
            "test suite и сценарии",
            "ring editor",
            "road scenario",
            "сценарии",
            "редактор кольца",
        ),
        context_handoff_keys=(
            "ring_source_of_truth_json",
            "ring_source_hash",
            "ring_export_set_hash",
            "scenario_json",
            "road_csv",
            "axay_csv",
            "meta_json",
            "validated_suite_snapshot",
            "suite_snapshot_hash",
            "handoff_id",
            "workspace_dir",
            "repo_root",
        ),
    )
