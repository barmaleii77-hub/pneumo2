from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_route_auto_panel_helpers import (
    build_svg_auto_all_label_items,
    resolve_svg_auto_review_status,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
CONNECTIVITY_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"
AUTO_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_auto_panel_helpers.py"


def test_build_svg_auto_all_label_items_skips_noise_and_invalid_rows() -> None:
    texts = [
        {"text": "P", "x": 1, "y": 2},
        {"text": "MainStart", "x": 10, "y": 20},
        {"text": "ValveB", "x": 30, "y": 40},
        {"text": "", "x": 50, "y": 60},
        {"text": "BadCoords", "x": "oops", "y": 1},
    ]

    assert build_svg_auto_all_label_items(texts) == [
        (1, "MainStart", 10.0, 20.0),
        (2, "ValveB", 30.0, 40.0),
    ]


def test_resolve_svg_auto_review_status_matches_pass_pending_contract() -> None:
    assert resolve_svg_auto_review_status({"grade": "PASS"}) == "approved"
    assert resolve_svg_auto_review_status({"grade": "FAIL"}) == "pending"
    assert resolve_svg_auto_review_status(None) == "pending"


def test_entrypoints_use_shared_svg_route_auto_panel_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    connectivity_text = CONNECTIVITY_PANEL_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = AUTO_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "render_svg_connectivity_panel(" in section_text
    assert "render_svg_route_auto_panel(" in connectivity_text
    assert 'with st.expander("AUTO: propose → route → mapping (beta)", expanded=False):' not in app_text
    assert 'with st.expander("AUTO: propose → route → mapping (beta)", expanded=False):' not in heavy_text
    assert "AUTO pipeline legacy dead block" not in app_text
    assert "AUTO pipeline legacy dead block" not in heavy_text
    assert 'btn_auto_one = st.button("AUTO: текущая", key="btn_route_auto_one")' not in app_text
    assert 'btn_auto_one = st.button("AUTO: текущая", key="btn_route_auto_one")' not in heavy_text
    assert 'btn_auto_batch = st.button("AUTO: batch", key="btn_route_auto_batch")' not in app_text
    assert 'btn_auto_batch = st.button("AUTO: batch", key="btn_route_auto_batch")' not in heavy_text
    assert 'btn_route_auto_one' in helper_text
    assert 'btn_route_auto_batch' in helper_text
    assert "build_svg_route_candidates(" in helper_text
    assert "choose_svg_route_candidate_pair(" in helper_text
    assert "write_svg_edge_route(" in helper_text
    assert "persist_svg_mapping_text(" in helper_text
