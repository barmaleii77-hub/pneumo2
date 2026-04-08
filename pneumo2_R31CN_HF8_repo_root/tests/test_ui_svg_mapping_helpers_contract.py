from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_mapping_helpers import (
    SVG_ROUTE_APPEND_SEGMENT_MODE,
    clear_svg_edge_route,
    ensure_svg_edge_mapping_store,
    load_svg_mapping_or_empty,
    write_svg_edge_route,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
CONNECTIVITY_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"
AUTO_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_auto_panel_helpers.py"


def test_load_svg_mapping_or_empty_uses_existing_mapping() -> None:
    mapping = load_svg_mapping_or_empty(
        '{"version": 7, "edges": {"e1": [[[1, 2], [3, 4]]]}, "nodes": {"n1": [1, 2]}}',
        view_box="0 0 100 100",
    )
    assert mapping["version"] == 7
    assert mapping["edges"]["e1"] == [[[1, 2], [3, 4]]]
    assert mapping["nodes"]["n1"] == [1, 2]


def test_load_svg_mapping_or_empty_builds_skeleton_on_invalid_json() -> None:
    mapping = load_svg_mapping_or_empty("not-json", view_box="0 0 320 240")
    assert mapping == {
        "version": 2,
        "viewBox": "0 0 320 240",
        "edges": {},
        "nodes": {},
    }


def test_ensure_svg_edge_mapping_store_initializes_expected_keys() -> None:
    mapping = {"viewBox": "keep-box", "edges": "bad", "nodes": {"n1": [1, 2]}}

    ensure_svg_edge_mapping_store(mapping, view_box="new-box")

    assert mapping == {
        "version": 2,
        "viewBox": "keep-box",
        "edges": {},
        "nodes": {"n1": [1, 2]},
    }


def test_clear_svg_edge_route_removes_edge_but_keeps_edges_meta() -> None:
    mapping = {
        "version": 2,
        "viewBox": "0 0 100 100",
        "edges": {"edge-a": [[[1, 2], [3, 4]]], "edge-b": [[[5, 6], [7, 8]]]},
        "nodes": {},
        "edges_meta": {"edge-a": {"keep": 1}},
    }

    clear_svg_edge_route(mapping, "edge-a", view_box="ignored-box")

    assert mapping["edges"] == {"edge-b": [[[5, 6], [7, 8]]]}
    assert mapping["edges_meta"] == {"edge-a": {"keep": 1}}


def test_write_svg_edge_route_appends_and_merges_meta() -> None:
    mapping = {
        "version": 2,
        "viewBox": "old-box",
        "edges": {"edge-a": [[[0.0, 0.0], [1.0, 1.0]]]},
        "nodes": {},
        "edges_meta": {
            "edge-a": {
                "review": {"status": "pending", "by": "human"},
                "route": {"points": 2},
                "keep": 1,
            }
        },
    }

    write_svg_edge_route(
        mapping,
        "edge-a",
        [[2.0, 2.0], [3.0, 3.0]],
        SVG_ROUTE_APPEND_SEGMENT_MODE,
        {
            "review": {"status": "approved"},
            "route": {"length_px": 42.0},
            "extra": True,
        },
        view_box="new-box",
    )

    assert mapping["viewBox"] == "old-box"
    assert mapping["edges"]["edge-a"] == [
        [[0.0, 0.0], [1.0, 1.0]],
        [[2.0, 2.0], [3.0, 3.0]],
    ]
    assert mapping["edges_meta"]["edge-a"] == {
        "review": {"status": "approved", "by": "human"},
        "route": {"points": 2, "length_px": 42.0},
        "keep": 1,
        "extra": True,
    }


def test_write_svg_edge_route_replaces_segments_for_other_modes() -> None:
    mapping: dict[str, object] = {}

    write_svg_edge_route(
        mapping,
        "edge-b",
        [[10.0, 10.0], [20.0, 20.0]],
        "replace",
        {"route": {"points": 2}},
        view_box="0 0 640 480",
    )

    assert mapping["version"] == 2
    assert mapping["viewBox"] == "0 0 640 480"
    assert mapping["edges"] == {"edge-b": [[[10.0, 10.0], [20.0, 20.0]]]}
    assert mapping["nodes"] == {}
    assert mapping["edges_meta"] == {"edge-b": {"route": {"points": 2}}}


def test_entrypoints_use_shared_svg_mapping_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    connectivity_text = CONNECTIVITY_PANEL_HELPERS_PATH.read_text(encoding="utf-8")
    auto_panel_text = AUTO_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "from pneumo_solver_ui.ui_svg_route_auto_panel_helpers import (" in connectivity_text
    assert "from pneumo_solver_ui.ui_svg_mapping_helpers import (" in auto_panel_text
    assert "load_svg_mapping_or_empty(" in auto_panel_text
    assert "write_svg_edge_route(" in auto_panel_text
    assert "def _load_mapping_or_empty() -> Dict[str, Any]:" not in app_text
    assert "def _load_mapping_or_empty() -> Dict[str, Any]:" not in heavy_text
    assert "def _write_edge_route(mapping2: Dict[str, Any], edge_name: str, poly_xy: List[List[float]], mode: str, meta: Dict[str, Any]):" not in app_text
    assert "def _write_edge_route(mapping2: Dict[str, Any], edge_name: str, poly_xy: List[List[float]], mode: str, meta: Dict[str, Any]):" not in heavy_text
