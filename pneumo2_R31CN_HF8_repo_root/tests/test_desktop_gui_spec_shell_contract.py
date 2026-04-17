from __future__ import annotations

import csv
from pathlib import Path

from pneumo_solver_ui.desktop_shell.launcher_catalog import build_desktop_launch_catalog
from pneumo_solver_ui.desktop_spec_shell.help_registry import build_help_registry
from pneumo_solver_ui.desktop_spec_shell.overview_state import build_overview_snapshot
from pneumo_solver_ui.desktop_spec_shell.registry import (
    SHELL_WORKSPACE_CODE,
    build_command_map,
    build_shell_workspaces,
)
from pneumo_solver_ui.desktop_spec_shell.search import build_search_entries, search_command_palette


ROOT = Path(__file__).resolve().parents[1]


def test_gui_spec_shell_workspace_order_matches_canonical_route() -> None:
    workspaces = build_shell_workspaces()
    assert [workspace.title for workspace in workspaces] == [
        "Обзор",
        "Исходные данные",
        "Сценарии и редактор кольца",
        "Набор испытаний",
        "Базовый прогон",
        "Оптимизация",
        "Анализ результатов",
        "Анимация",
        "Диагностика",
        "Параметры приложения",
        "Инструменты",
    ]


def test_gui_spec_shell_registry_is_catalog_driven_for_route_critical_surfaces() -> None:
    commands = build_command_map()
    workspaces = {workspace.workspace_id: workspace for workspace in build_shell_workspaces()}

    assert workspaces["input_data"].workspace_owner == "WS-INPUTS"
    assert workspaces["ring_editor"].workspace_owner == "WS-RING"
    assert workspaces["test_matrix"].workspace_owner == "WS-SUITE"
    assert workspaces["baseline_run"].workspace_owner == "WS-BASELINE"
    assert workspaces["optimization"].workspace_owner == "WS-OPTIMIZATION"
    assert workspaces["overview"].workspace_owner == "WS-PROJECT"
    assert workspaces["results_analysis"].workspace_owner == "WS-ANALYSIS"
    assert workspaces["diagnostics"].workspace_owner == "WS-DIAGNOSTICS"
    assert workspaces["tools"].workspace_owner == "WS-TOOLS"
    assert "WS-RESULTS" in workspaces["results_analysis"].catalog_owner_aliases
    assert "WS-ANALYTICS" in workspaces["results_analysis"].catalog_owner_aliases

    assert workspaces["baseline_run"].automation_id == "BL-CONTRACT-CARD"
    assert workspaces["optimization"].automation_id == "OP-STAGERUNNER-BLOCK"
    assert workspaces["results_analysis"].automation_id == "RS-LEADERBOARD"
    assert workspaces["diagnostics"].automation_id == "DG-LAST-BUNDLE"
    assert workspaces["input_data"].launch_surface == "workspace"

    assert commands["diagnostics.collect_bundle"].kind == "hosted_action"
    assert commands["diagnostics.collect_bundle"].automation_id == "DG-BTN-COLLECT"
    assert commands["baseline.center.open"].automation_id == "BL-BTN-RUN"
    assert commands["optimization.center.open"].automation_id == "OP-BTN-LAUNCH"
    assert commands["input.editor.open"].launch_surface == "legacy_bridge"
    assert commands["ring.editor.open"].launch_surface == "legacy_bridge"
    assert commands["test.center.open"].launch_surface == "legacy_bridge"
    assert commands["baseline.center.open"].launch_surface == "legacy_bridge"
    assert commands["optimization.center.open"].launch_surface == "legacy_bridge"
    assert commands["results.center.open"].launch_surface == "legacy_bridge"
    assert commands["diagnostics.legacy_center.open"].launch_surface == "legacy_bridge"
    assert commands["diagnostics.legacy_center.open"].module == "pneumo_solver_ui.tools.desktop_diagnostics_center"


def test_gui_spec_shell_launch_module_commands_do_not_claim_native_workspace_surface() -> None:
    commands = build_command_map()
    allowed_surfaces = {"legacy_bridge", "external_window", "tooling"}

    for command in commands.values():
        if command.kind != "launch_module":
            continue
        assert command.launch_surface in allowed_surfaces, command.command_id
        if command.launch_surface == "legacy_bridge":
            assert command.status_label in {"Legacy bridge", "Legacy fallback", "Fallback / debug"}


def test_gui_spec_shell_runtime_workspace_owners_cover_v37_contract_matrix() -> None:
    matrix_path = ROOT / "docs" / "context" / "gui_spec_imports" / "v37_github_kb_supplement" / "WORKSPACE_CONTRACT_MATRIX.csv"
    with matrix_path.open("r", encoding="utf-8-sig", newline="") as handle:
        v37_workspace_ids = {row["workspace_id"] for row in csv.DictReader(handle)}

    runtime_workspace_ids = {
        workspace.workspace_owner
        for workspace in build_shell_workspaces()
        if workspace.workspace_owner
    }
    runtime_workspace_ids.add(SHELL_WORKSPACE_CODE)

    assert v37_workspace_ids <= runtime_workspace_ids
    assert "GLOBAL" not in runtime_workspace_ids
    assert "WS-RESULTS" not in runtime_workspace_ids
    assert "WS-ANALYTICS" not in runtime_workspace_ids


def test_gui_spec_shell_search_indexes_migration_aliases_and_visual_routes() -> None:
    workspaces = build_shell_workspaces()
    commands = tuple(build_command_map().values())
    entries = build_search_entries(workspaces, commands)

    diagnostics_hits = search_command_palette(entries, "собрать диагностику")
    stiffness_hits = search_command_palette(entries, "жёсткость")
    mnemo_hits = search_command_palette(entries, "пневмосхема")

    assert diagnostics_hits
    assert diagnostics_hits[0].command_id == "diagnostics.collect_bundle"
    assert stiffness_hits
    assert stiffness_hits[0].command_id == "workspace.input_data.open"
    assert mnemo_hits
    assert any(hit.command_id == "animation.mnemo.open" for hit in mnemo_hits)


def test_gui_spec_shell_help_registry_covers_every_workspace_with_catalog_text() -> None:
    workspaces = build_shell_workspaces()
    help_registry = build_help_registry()

    for workspace in workspaces:
        assert workspace.workspace_id in help_registry
        topic = help_registry[workspace.workspace_id]
        assert topic.source_of_truth
        assert topic.next_step
        assert topic.hard_gate

    assert help_registry["diagnostics"].tooltip_text
    assert help_registry["optimization"].why_it_matters
    assert help_registry["results_analysis"].result_location


def test_gui_spec_shell_overview_snapshot_exposes_project_baseline_results_and_diagnostics() -> None:
    snapshot = build_overview_snapshot(ROOT)
    titles = [card.title for card in snapshot.cards]

    assert "Текущий проект" in titles
    assert "Активный baseline" in titles
    assert "Optimization contract" in titles
    assert "Последние результаты" in titles
    assert "Последний diagnostics bundle" in titles
    assert "Health / self-check" in titles


def test_gui_spec_overview_snapshot_does_not_recursively_scan_user_desktop() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_spec_shell" / "overview_state.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'desktop_root = Path.home() / "Desktop"' in src
    assert "recursive=False" in src
    assert "desktop_root.rglob" not in src
    assert "_latest_path(desktop_root" not in src


def test_gui_spec_shell_main_window_uses_hosted_hubs_and_single_dispatcher() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_spec_shell" / "main_window.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopGuiSpecMainWindow(QtWidgets.QMainWindow):" in src
    assert "self.command_search = QtWidgets.QComboBox()" in src
    assert 'diagnostics_button = QtWidgets.QPushButton("Собрать диагностику")' in src
    assert "self.primary_action_button = QtWidgets.QPushButton(" in src
    assert "self.pinned_list = QtWidgets.QListWidget()" in src
    assert "ControlHubWorkspacePage" in src
    assert "InputWorkspacePage" in src
    assert "BaselineWorkspacePage" in src
    assert "OptimizationWorkspacePage" in src
    assert "ResultsWorkspacePage" in src
    assert "DiagnosticsWorkspacePage" in src
    assert src.count("def open_workspace(") == 1
    assert src.count("def run_command(") == 1


def test_gui_spec_shell_is_available_in_shared_launch_catalog() -> None:
    catalog = build_desktop_launch_catalog(include_mnemo=True)
    modules = {item.module for item in catalog}

    assert "pneumo_solver_ui.tools.desktop_gui_spec_shell" in modules
