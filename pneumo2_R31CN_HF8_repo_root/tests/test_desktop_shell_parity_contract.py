from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_shell.registry import build_desktop_shell_specs
from pneumo_solver_ui.page_registry import get_entries


ROOT = Path(__file__).resolve().parents[1]
PARITY_JSON = ROOT / "docs" / "context" / "desktop_web_parity_map.json"


def _load_parity_entries() -> list[dict[str, object]]:
    return json.loads(PARITY_JSON.read_text(encoding="utf-8"))


def test_desktop_web_parity_registry_covers_all_menu_visible_web_pages() -> None:
    entries = _load_parity_entries()
    covered_targets = {
        str(target).strip()
        for entry in entries
        for target in tuple(entry.get("web_targets") or ())
        if str(target).strip()
    }
    web_targets = {
        Path(str(entry.target)).name
        for entry in get_entries()
        if getattr(entry, "show_in_menu", True)
    }

    assert PARITY_JSON.exists()
    assert web_targets
    assert web_targets == covered_targets


def test_desktop_web_parity_registry_uses_supported_statuses_and_live_routes() -> None:
    entries = _load_parity_entries()
    allowed_statuses = {
        "перенесён",
        "сведён",
        "контекстный",
        "инструмент",
        "архивный legacy",
    }

    assert entries
    assert {str(entry.get("status") or "") for entry in entries} <= allowed_statuses
    for entry in entries:
        status = str(entry.get("status") or "")
        tool_keys = tuple(str(item) for item in tuple(entry.get("desktop_tool_keys") or ()))
        if status == "архивный legacy":
            assert not tool_keys
        else:
            assert tool_keys


def test_desktop_shell_registry_exposes_hidden_centers_without_polluting_main_route() -> None:
    specs = build_desktop_shell_specs()
    by_key = {spec.key: spec for spec in specs}
    main_keys = tuple(spec.key for spec in specs if spec.entry_kind == "main")

    assert "desktop_geometry_reference_center" in by_key
    assert "desktop_diagnostics_center" in by_key
    assert by_key["desktop_geometry_reference_center"].entry_kind == "tool"
    assert by_key["desktop_diagnostics_center"].entry_kind == "tool"
    assert by_key["desktop_input_editor"].entry_kind == "main"
    assert by_key["desktop_ring_editor"].entry_kind == "main"
    assert by_key["test_center"].entry_kind == "main"
    assert by_key["desktop_optimizer_center"].entry_kind == "main"
    assert by_key["desktop_results_center"].entry_kind == "main"
    assert main_keys == (
        "desktop_input_editor",
        "desktop_ring_editor",
        "test_center",
        "desktop_optimizer_center",
        "desktop_results_center",
    )


def test_desktop_shell_registry_covers_all_live_desktop_routes_from_parity_map() -> None:
    specs = build_desktop_shell_specs()
    keys = {spec.key for spec in specs}
    live_tool_keys = {
        str(tool_key)
        for entry in _load_parity_entries()
        if str(entry.get("status") or "") != "архивный legacy"
        for tool_key in tuple(entry.get("desktop_tool_keys") or ())
    }

    assert live_tool_keys <= keys
