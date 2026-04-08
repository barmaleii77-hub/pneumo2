from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_interaction_helpers import (
    apply_pick_list,
    ensure_mapping_for_selection,
    extract_plotly_selection_points,
    plotly_points_signature,
    strip_svg_xml_header,
)


ROOT = Path(__file__).resolve().parents[1]


class _AttrSelection:
    def __init__(self, points):
        self.points = points


class _AttrPlotState:
    def __init__(self, points):
        self.selection = _AttrSelection(points)


def test_apply_pick_list_and_signature_helpers_are_stable() -> None:
    assert apply_pick_list(None, "edge_1", "replace") == ["edge_1"]
    assert apply_pick_list(["edge_1"], "edge_2", "add") == ["edge_1", "edge_2"]
    assert apply_pick_list(("edge_1",), "edge_1", "add") == ["edge_1"]

    points_a = [{"curve_number": 2, "point_index": 5}, {"curve_number": 1, "point_index": 3}]
    points_b = [{"curve_number": 1, "point_index": 3}, {"curve_number": 2, "point_index": 5}]
    assert plotly_points_signature(points_a) == plotly_points_signature(points_b)


def test_extract_plotly_selection_points_supports_dict_and_attr_access() -> None:
    dict_state = {"selection": {"points": [{"curve_number": 1, "point_index": 2}]}}
    attr_state = _AttrPlotState([{"curve_number": 3, "pointIndex": 4}])

    assert extract_plotly_selection_points(dict_state) == [{"curve_number": 1, "point_index": 2}]
    assert extract_plotly_selection_points(attr_state) == [{"curve_number": 3, "pointIndex": 4}]
    assert extract_plotly_selection_points(None) == []


def test_strip_svg_xml_header_and_mapping_autofill() -> None:
    svg = "<?xml version='1.0'?><!--x--><svg viewBox='0 0 1 1'></svg>"
    assert strip_svg_xml_header(svg) == "<svg viewBox='0 0 1 1'></svg>"

    mapping, report = ensure_mapping_for_selection(
        {
            "edges": {"Line A": [{"x1": 0, "y1": 0, "x2": 1, "y2": 1}]},
            "nodes": {"Node Main": [10, 20]},
        },
        need_edges=["line-a"],
        need_nodes=["node_main"],
        min_score=0.60,
    )

    assert mapping["edges"]["line-a"] == [{"x1": 0, "y1": 0, "x2": 1, "y2": 1}]
    assert mapping["nodes"]["node_main"] == [10, 20]
    assert report["edges"][0]["from"] == "Line A"
    assert report["nodes"][0]["from"] == "Node Main"


def test_large_ui_entrypoints_import_shared_interaction_helpers() -> None:
    for rel in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_interaction_helpers import (" in src
        assert "apply_pick_list as _apply_pick_list" in src
        assert "extract_plotly_selection_points as _extract_plotly_selection_points" in src
        assert "plotly_points_signature as _plotly_points_signature" in src
        assert "def _apply_pick_list(" not in src
        assert "def _extract_plotly_selection_points(" not in src
        assert "def _plotly_points_signature(" not in src
        assert "def ensure_mapping_for_selection(" not in src
