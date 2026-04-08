from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_guided_panel_helpers import (
    apply_svg_route_edge_advance,
    swap_svg_route_label_options,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
CONNECTIVITY_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"
GUIDED_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_guided_panel_helpers.py"


def test_apply_svg_route_edge_advance_promotes_requested_unmapped_edge() -> None:
    session_state = {
        "route_advance_to_unmapped": "edge-b",
        "svg_route_assign_edge": "edge-a",
    }

    apply_svg_route_edge_advance(session_state, ["edge-a", "edge-b", "edge-c"])

    assert session_state["svg_route_assign_edge"] == "edge-b"
    assert "route_advance_to_unmapped" not in session_state


def test_swap_svg_route_label_options_swaps_only_when_both_are_present() -> None:
    session_state = {
        "svg_route_start_opt": "#001 | Start | (10,20)",
        "svg_route_end_opt": "#002 | End | (30,40)",
    }

    swap_svg_route_label_options(session_state)
    assert session_state["svg_route_start_opt"] == "#002 | End | (30,40)"
    assert session_state["svg_route_end_opt"] == "#001 | Start | (10,20)"

    incomplete_state = {"svg_route_start_opt": "#001 | Start | (10,20)"}
    swap_svg_route_label_options(incomplete_state)
    assert incomplete_state == {"svg_route_start_opt": "#001 | Start | (10,20)"}


def test_entrypoints_use_shared_svg_route_guided_panel_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    connectivity_text = CONNECTIVITY_PANEL_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = GUIDED_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "render_svg_connectivity_panel(" in section_text
    assert "render_svg_route_guided_panel(" in connectivity_text
    assert 'with st.expander("Ассистент разметки веток (guided)", expanded=False):' not in app_text
    assert 'with st.expander("Ассистент разметки веток (guided)", expanded=False):' not in heavy_text
    assert 'btn_route_next_unmapped' not in app_text
    assert 'btn_route_next_unmapped' not in heavy_text
    assert 'btn_route_autofilter_edge' not in app_text
    assert 'btn_route_autofilter_edge' not in heavy_text
    assert 'btn_swap_route_labels' not in app_text
    assert 'btn_swap_route_labels' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_route_helpers import (" in helper_text
    assert "build_svg_route_coverage(" in helper_text
    assert "build_svg_route_candidates(" in helper_text
    assert "suggest_svg_route_filter_text(" in helper_text
