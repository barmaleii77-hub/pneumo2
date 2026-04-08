from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_selection_helpers import (
    apply_pending_svg_route_label_pick,
    resolve_svg_route_label_picks,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SEARCH_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_search_panel_helpers.py"


def test_apply_pending_svg_route_label_pick_updates_session_state_by_index() -> None:
    session_state: dict[str, object] = {
        "svg_route_label_pick_pending": {"mode": "start", "ti": 2, "x": 0, "y": 0, "name": "ignored"},
    }
    items = [
        (1, "A", 10.0, 20.0),
        (2, "B", 30.0, 40.0),
    ]
    options = ["#001 | A | (10,20)"]
    option_to_index = {"#001 | A | (10,20)": 1}

    updated_options, updated_index = apply_pending_svg_route_label_pick(
        session_state,
        session_state.get("svg_route_label_pick_pending"),
        items,
        options,
        option_to_index,
        format_item_fn=lambda item: f"#{item[0]:03d} | {item[1]} | ({int(item[2])},{int(item[3])})",
    )

    assert updated_options == [
        "#001 | A | (10,20)",
        "#002 | B | (30,40)",
    ]
    assert updated_index["#002 | B | (30,40)"] == 2
    assert session_state["svg_route_start_opt"] == "#002 | B | (30,40)"
    assert session_state["svg_route_label_picks"] == {
        "start": {"ti": 2, "name": "B", "x": 30.0, "y": 40.0}
    }
    assert "svg_route_label_pick_pending" not in session_state


def test_apply_pending_svg_route_label_pick_uses_nearest_fallback() -> None:
    session_state: dict[str, object] = {
        "svg_route_label_pick_pending": {"mode": "end", "x": 101.0, "y": 49.0, "name": "ValveB"},
    }
    items = [
        (1, "ValveA", 10.0, 20.0),
        (2, "ValveB", 100.0, 50.0),
        (3, "ValveB", 200.0, 150.0),
    ]
    options = ["#001 | ValveA | (10,20)"]
    option_to_index = {"#001 | ValveA | (10,20)": 1}

    updated_options, updated_index = apply_pending_svg_route_label_pick(
        session_state,
        session_state.get("svg_route_label_pick_pending"),
        items,
        options,
        option_to_index,
        format_item_fn=lambda item: f"#{item[0]:03d} | {item[1]} | ({int(item[2])},{int(item[3])})",
    )

    assert updated_options[-1] == "#002 | ValveB | (100,50)"
    assert updated_index["#002 | ValveB | (100,50)"] == 2
    assert session_state["svg_route_end_opt"] == "#002 | ValveB | (100,50)"
    assert session_state["svg_route_label_picks"] == {
        "end": {"ti": 2, "name": "ValveB", "x": 100.0, "y": 50.0}
    }


def test_resolve_svg_route_label_picks_returns_current_start_end() -> None:
    items = [
        (1, "StartA", 10.0, 20.0),
        (2, "EndB", 30.0, 40.0),
    ]
    picks = resolve_svg_route_label_picks(
        items,
        "#001 | StartA | (10,20)",
        "#002 | EndB | (30,40)",
        {
            "#001 | StartA | (10,20)": 1,
            "#002 | EndB | (30,40)": 2,
        },
    )

    assert picks == {
        "start": {"ti": 1, "name": "StartA", "x": 10.0, "y": 20.0},
        "end": {"ti": 2, "name": "EndB", "x": 30.0, "y": 40.0},
    }


def test_entrypoints_use_shared_svg_route_selection_helpers() -> None:
    search_panel_text = SEARCH_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_route_selection_helpers import (" in search_panel_text
    assert "apply_pending_svg_route_label_pick(" in search_panel_text
    assert "resolve_svg_route_label_picks(" in search_panel_text
    assert 'pending = st.session_state.get("svg_route_label_pick_pending")' not in search_panel_text
    assert "ti_s = opt_to_idx.get(start_opt)" not in search_panel_text
