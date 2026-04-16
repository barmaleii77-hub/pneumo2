from __future__ import annotations

import csv
import json
from pathlib import Path

from pneumo_solver_ui.desktop_spec_shell.registry import build_shell_commands, build_shell_workspaces


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "docs" / "context"
PARITY_JSON = CONTEXT / "desktop_web_parity_map.json"
MIGRATION_MATRIX = CONTEXT / "gui_spec_imports" / "v3" / "migration_matrix.csv"

REQUIRED_FIELDS = (
    "capability_id",
    "web_feature_id",
    "legacy_capability_group",
    "название_функции",
    "старое_место",
    "новое_место",
    "workspace",
    "source_of_truth",
    "сохранена_полностью",
    "улучшения",
    "как_найти_через_поиск_команд",
    "статус_миграции",
    "desktop_route_kind",
    "desktop_tool_keys",
)

WORKSPACE_CODE_MAP = {
    "WS-INPUTS": ("input_data",),
    "WS-RING": ("ring_editor",),
    "WS-SUITE": ("test_matrix",),
    "WS-BASELINE": ("baseline_run",),
    "WS-OPTIMIZATION": ("optimization",),
    "WS-MONITOR": ("optimization",),
    "WS-RESULTS": ("results_analysis",),
    "WS-ANALYTICS": ("results_analysis",),
    "WS-ANIMATOR": ("animation",),
    "WS-DIAGNOSTICS": ("diagnostics",),
    "WS-SETTINGS": ("app_settings", "tools"),
    "GLOBAL": (),
}


def _load_parity_entries() -> list[dict[str, object]]:
    return json.loads(PARITY_JSON.read_text(encoding="utf-8"))


def _load_migration_rows() -> list[dict[str, str]]:
    with MIGRATION_MATRIX.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_desktop_web_parity_registry_matches_v3_migration_matrix_rows() -> None:
    entries = _load_parity_entries()
    rows = _load_migration_rows()

    assert PARITY_JSON.exists()
    assert MIGRATION_MATRIX.exists()
    assert len(entries) == len(rows)
    assert {str(entry["web_feature_id"]) for entry in entries} == {row["web_feature_id"] for row in rows}


def test_desktop_web_parity_registry_keeps_required_v3_fields_and_statuses() -> None:
    entries = _load_parity_entries()
    allowed_statuses = {"обязательно", "новый_обязательный_слой"}

    assert entries
    for entry in entries:
        for field in REQUIRED_FIELDS:
            assert field in entry, f"missing {field} in {entry}"

        assert str(entry["статус_миграции"]) in allowed_statuses
        assert str(entry["capability_id"]).strip()
        assert str(entry["web_feature_id"]).strip()
        assert str(entry["legacy_capability_group"]).strip()
        assert str(entry["как_найти_через_поиск_команд"]).strip()
        assert str(entry["desktop_route_kind"]).strip()
        assert isinstance(entry["desktop_tool_keys"], list)


def test_desktop_web_parity_registry_matches_machine_readable_migration_content() -> None:
    entries = {str(entry["web_feature_id"]): entry for entry in _load_parity_entries()}
    rows = {row["web_feature_id"]: row for row in _load_migration_rows()}

    for web_feature_id, row in rows.items():
        entry = entries[web_feature_id]
        assert entry["capability_id"] == web_feature_id
        assert entry["web_feature_id"] == row["web_feature_id"]
        assert entry["название_функции"] == row["название_функции"]
        assert entry["старое_место"] == row["старое_место"]
        assert entry["новое_место"] == row["новое_место"]
        assert entry["workspace"] == row["workspace"]
        assert entry["source_of_truth"] == row["source_of_truth"]
        assert entry["сохранена_полностью"] is (row["сохранена_полностью"].strip().lower() == "true")
        assert entry["улучшения"] == row["улучшения"]
        assert entry["как_найти_через_поиск_команд"] == row["как_найти_через_поиск_команд"]
        assert entry["статус_миграции"] == row["статус_миграции"]


def test_desktop_web_parity_registry_uses_known_shell_workspaces() -> None:
    shell_workspace_ids = {workspace.workspace_id for workspace in build_shell_workspaces()}
    entries = _load_parity_entries()

    for entry in entries:
        raw_codes = [part.strip() for part in str(entry["workspace"]).split(";") if part.strip()]
        for code in raw_codes:
            assert code in WORKSPACE_CODE_MAP, f"unknown workspace code {code}"
            assert set(WORKSPACE_CODE_MAP[code]) <= shell_workspace_ids


def test_desktop_web_parity_registry_routes_keep_shell_and_tool_coverage() -> None:
    commands = {command.command_id for command in build_shell_commands()}
    entries = _load_parity_entries()

    assert "diagnostics.collect_bundle" in commands
    assert "workspace.diagnostics.open" in commands
    assert "workspace.baseline_run.open" in commands
    assert "workspace.optimization.open" in commands
    assert "workspace.results_analysis.open" in commands
    assert "analysis.engineering.open" in commands
    assert "workspace.animation.open" in commands

    for entry in entries:
        search_hint = str(entry["как_найти_через_поиск_команд"]).strip()
        assert search_hint
        if str(entry["workspace"]) != "GLOBAL":
            assert str(entry["desktop_route_kind"]).strip() != "global_command_surface"

    global_rows = {str(entry["web_feature_id"]) for entry in entries if str(entry["workspace"]) == "GLOBAL"}
    assert {"WEB-015", "WEB-016"} <= global_rows
