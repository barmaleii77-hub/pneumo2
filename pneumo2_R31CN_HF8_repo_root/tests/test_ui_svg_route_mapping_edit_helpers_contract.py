from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_mapping_edit_helpers import (
    apply_svg_route_mapping_edit,
    load_svg_mapping_for_route_edit,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
ASSIGNMENT_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_assignment_panel_helpers.py"


def test_load_svg_mapping_for_route_edit_raises_on_non_dict_json() -> None:
    try:
        load_svg_mapping_for_route_edit("[]", view_box="0 0 10 10")
    except ValueError as exc:
        assert str(exc) == "mapping JSON должен быть объектом (dict)."
    else:
        raise AssertionError("ValueError was expected")


def test_load_svg_mapping_for_route_edit_builds_skeleton_when_empty() -> None:
    mapping = load_svg_mapping_for_route_edit("", view_box="0 0 10 10")
    assert mapping == {"version": 2, "viewBox": "0 0 10 10", "edges": {}, "nodes": {}}


def test_apply_svg_route_mapping_edit_clears_edge_and_persists_mapping() -> None:
    session_state: dict[str, object] = {
        "route_auto_next": True,
        "route_clear_after_assign": True,
        "svg_route_paths": [[[1.0, 2.0], [3.0, 4.0]]],
        "svg_route_report": {"length": 12.5},
    }
    mapping_text = '{"version":2,"viewBox":"vb","edges":{"edge-a":[[[1,2],[3,4]]],"edge-b":[[[5,6],[7,8]]]},"nodes":{},"edges_meta":{"edge-a":{"keep":1}}}'

    mapping, message = apply_svg_route_mapping_edit(
        session_state,
        mapping_text,
        "edge-a",
        ["edge-a", "edge-b"],
        mapping_view_box="vb",
        route_write_view_box="route-vb",
        clear_edge=True,
        assign_route=False,
        polyline=None,
        mode="Заменить",
        route_report={},
        evaluate_quality_fn=lambda *args, **kwargs: {"grade": "PASS"},
    )

    assert message == "Очищено: mapping.edges['edge-a']"
    assert mapping["edges"] == {"edge-b": [[[5, 6], [7, 8]]]}
    assert mapping["edges_meta"] == {"edge-a": {"keep": 1}}
    assert session_state["route_advance_to_unmapped"] == "edge-a"
    assert "svg_route_paths" in session_state
    assert "svg_route_report" in session_state
    assert '"edge-b"' in str(session_state["svg_mapping_text"])


def test_apply_svg_route_mapping_edit_assigns_route_and_clears_preview() -> None:
    session_state: dict[str, object] = {
        "route_auto_next": True,
        "route_clear_after_assign": True,
        "svg_route_paths": [[[1.0, 2.0], [3.0, 4.0]]],
        "svg_route_report": {"length": 12.5},
        "svg_route_label_picks": {"start": {"ti": 1}},
    }

    mapping, message = apply_svg_route_mapping_edit(
        session_state,
        "",
        "edge-a",
        ["edge-a", "edge-b"],
        mapping_view_box="map-vb",
        route_write_view_box="route-vb",
        clear_edge=False,
        assign_route=True,
        polyline=[[10.0, 10.0], [20.0, 20.0]],
        mode="Добавить сегмент",
        route_report={"length": 99.0, "attach_start": {"x": 1}, "attach_end": {"x": 2}},
        evaluate_quality_fn=lambda *args, **kwargs: {"grade": "PASS"},
    )

    assert message == "Маршрут записан в mapping.edges['edge-a'] (Добавить сегмент)."
    assert mapping["viewBox"] == "map-vb"
    assert mapping["edges"]["edge-a"] == [[[10.0, 10.0], [20.0, 20.0]]]
    assert mapping["meta"]["last_route_assign"]["edge"] == "edge-a"
    assert session_state["svg_route_quality"] == {"grade": "PASS"}
    assert session_state["route_advance_to_unmapped"] == "edge-b"
    assert "svg_route_paths" not in session_state
    assert "svg_route_report" not in session_state


def test_entrypoints_use_shared_svg_route_mapping_edit_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    assignment_panel_text = ASSIGNMENT_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_route_mapping_edit_helpers import apply_svg_route_mapping_edit" in assignment_panel_text
    assert "apply_svg_route_mapping_edit(" in assignment_panel_text
    assert 'mapping2 = json.loads(mtxt)' not in app_text
    assert 'mapping2 = json.loads(mtxt)' not in heavy_text
    assert 'if btn_clear_edge:' not in app_text
    assert 'if btn_clear_edge:' not in heavy_text
    assert 'if btn_assign:' not in app_text
    assert 'if btn_assign:' not in heavy_text
    assert 'st.success(f"Очищено: mapping.edges' not in app_text
    assert 'st.success(f"Очищено: mapping.edges' not in heavy_text
    assert 'st.success(f"Маршрут записан в mapping.edges' not in app_text
    assert 'st.success(f"Маршрут записан в mapping.edges' not in heavy_text
