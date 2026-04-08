from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_mapping_state_helpers import (
    clear_svg_route_preview,
    finalize_svg_route_mapping_edit,
    persist_svg_mapping_text,
    request_next_unmapped_svg_edge,
    store_svg_route_preview,
    update_svg_mapping_meta,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
CONNECTIVITY_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"
AUTO_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_auto_panel_helpers.py"


def test_update_svg_mapping_meta_creates_meta_dict() -> None:
    mapping: dict[str, object] = {}
    update_svg_mapping_meta(mapping, "last_auto_route_assign", {"edge": "edge-a"})
    assert mapping == {"meta": {"last_auto_route_assign": {"edge": "edge-a"}}}


def test_persist_and_preview_helpers_update_session_state() -> None:
    session_state: dict[str, object] = {}
    mapping = {"version": 2, "edges": {"edge-a": [[[1.0, 2.0], [3.0, 4.0]]]}, "nodes": {}}

    persist_svg_mapping_text(session_state, mapping)
    store_svg_route_preview(session_state, [[10.0, 20.0], [30.0, 40.0]], {"length": 12.5})

    assert '"edge-a"' in str(session_state["svg_mapping_text"])
    assert session_state["svg_route_paths"] == [[[10.0, 20.0], [30.0, 40.0]]]
    assert session_state["svg_route_report"] == {"length": 12.5}

    clear_svg_route_preview(session_state)
    assert "svg_route_paths" not in session_state
    assert "svg_route_report" not in session_state


def test_request_next_unmapped_svg_edge_picks_first_gap() -> None:
    session_state: dict[str, object] = {}
    mapping = {"edges": {"edge-a": [[[0.0, 0.0], [1.0, 1.0]]]}}

    request_next_unmapped_svg_edge(session_state, mapping, ["edge-a", "edge-b", "edge-c"])
    assert session_state["route_advance_to_unmapped"] == "edge-b"


def test_request_next_unmapped_svg_edge_skips_when_all_mapped() -> None:
    session_state = {"route_advance_to_unmapped": "keep-me"}
    mapping = {"edges": {"edge-a": [], "edge-b": []}}

    request_next_unmapped_svg_edge(session_state, mapping, ["edge-a", "edge-b"])
    assert session_state["route_advance_to_unmapped"] == "keep-me"


def test_finalize_svg_route_mapping_edit_persists_requests_next_and_clears_preview() -> None:
    session_state: dict[str, object] = {
        "route_auto_next": True,
        "route_clear_after_assign": True,
        "svg_route_paths": [[[1.0, 2.0], [3.0, 4.0]]],
        "svg_route_report": {"length": 12.5},
    }
    mapping = {"version": 2, "edges": {"edge-a": [[[0.0, 0.0], [1.0, 1.0]]]}, "nodes": {}}

    finalize_svg_route_mapping_edit(
        session_state,
        mapping,
        ["edge-a", "edge-b"],
        assigned=True,
    )

    assert '"edge-a"' in str(session_state["svg_mapping_text"])
    assert session_state["route_advance_to_unmapped"] == "edge-b"
    assert "svg_route_paths" not in session_state
    assert "svg_route_report" not in session_state


def test_finalize_svg_route_mapping_edit_skips_preview_clear_when_not_assigned() -> None:
    session_state: dict[str, object] = {
        "route_auto_next": False,
        "route_clear_after_assign": True,
        "svg_route_paths": [[[1.0, 2.0], [3.0, 4.0]]],
        "svg_route_report": {"length": 12.5},
    }
    mapping = {"version": 2, "edges": {}, "nodes": {}}

    finalize_svg_route_mapping_edit(
        session_state,
        mapping,
        ["edge-a"],
        assigned=False,
    )

    assert "svg_mapping_text" in session_state
    assert "route_advance_to_unmapped" not in session_state
    assert "svg_route_paths" in session_state
    assert "svg_route_report" in session_state


def test_entrypoints_use_shared_svg_mapping_state_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    connectivity_text = CONNECTIVITY_PANEL_HELPERS_PATH.read_text(encoding="utf-8")
    auto_panel_text = AUTO_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "from pneumo_solver_ui.ui_svg_route_auto_panel_helpers import (" in connectivity_text
    assert "from pneumo_solver_ui.ui_svg_mapping_state_helpers import (" in auto_panel_text
    assert "update_svg_mapping_meta(" in auto_panel_text
    assert "persist_svg_mapping_text(" in auto_panel_text
    assert "request_next_unmapped_svg_edge(" in auto_panel_text
    assert "clear_svg_route_preview(" in auto_panel_text
    assert 'mapping2["meta"]["last_auto_route_assign"]' not in app_text
    assert 'mapping2["meta"]["last_auto_route_assign"]' not in heavy_text
    assert 'mapping2["meta"]["auto_batch_last"]' not in app_text
    assert 'mapping2["meta"]["auto_batch_last"]' not in heavy_text
    assert 'mapping2["meta"]["last_route_assign"]' not in app_text
    assert 'mapping2["meta"]["last_route_assign"]' not in heavy_text
