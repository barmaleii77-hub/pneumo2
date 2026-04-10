from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_route_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
CONNECTIVITY_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_connectivity_panel_helpers.py"
GUIDED_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_guided_panel_helpers.py"
AUTO_PANEL_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_route_auto_panel_helpers.py"


def test_svg_route_noise_filter_and_items_builder() -> None:
    texts = [
        {"text": "P", "x": 1, "y": 2},
        {"text": "Reservoir1", "x": 10, "y": 20},
        {"text": "LP2", "x": 30, "y": 40},
        {"text": "Q", "x": 50, "y": 60},
        {"text": "", "x": 70, "y": 80},
    ]

    assert ui_svg_route_helpers.is_noise_svg_route_label("P")
    assert ui_svg_route_helpers.is_noise_svg_route_label(" q ")
    assert ui_svg_route_helpers.is_noise_svg_route_label("")
    assert not ui_svg_route_helpers.is_noise_svg_route_label("Reservoir1")

    items = ui_svg_route_helpers.build_svg_route_label_items(texts, filter_text="res", limit=10)
    assert items == [(1, "Reservoir1", 10.0, 20.0)]

    all_items = ui_svg_route_helpers.build_svg_route_label_items(texts, filter_text="", limit=10)
    assert all_items == [
        (1, "Reservoir1", 10.0, 20.0),
        (2, "LP2", 30.0, 40.0),
    ]


def test_svg_route_format_and_options_builder() -> None:
    items = [
        (3, "Reservoir1", 10.0, 20.0),
        (4, "LP2", 30.0, 40.0),
    ]

    assert ui_svg_route_helpers.format_svg_route_item(items[0]) == "#003 | Reservoir1 | (10,20)"
    options, option_index = ui_svg_route_helpers.build_svg_route_options(items)
    assert options == [
        "#003 | Reservoir1 | (10,20)",
        "#004 | LP2 | (30,40)",
    ]
    assert option_index == {
        "#003 | Reservoir1 | (10,20)": 3,
        "#004 | LP2 | (30,40)": 4,
    }


def test_svg_route_candidate_builder_sorts_and_filters() -> None:
    items = [
        (1, "main-start", 0.0, 0.0),
        (2, "main-end", 50.0, 0.0),
        (3, "aux-node", 100.0, 100.0),
    ]

    def fake_name_score(edge_name: str, label: str) -> float:
        scores = {
            ("edge-main", "main-start"): 0.94,
            ("edge-main", "main-end"): 0.82,
            ("edge-main", "aux-node"): 0.31,
        }
        return scores.get((edge_name, label), 0.0)

    candidates = ui_svg_route_helpers.build_svg_route_candidates(
        items,
        "edge-main",
        min_score=0.5,
        top_k=5,
        name_score_fn=fake_name_score,
    )

    assert candidates == [
        (0.94, items[0]),
        (0.82, items[1]),
    ]
    assert ui_svg_route_helpers.score_svg_route_edge_label(
        "edge-main",
        "main-start",
        name_score_fn=fake_name_score,
    ) == 0.94


def test_svg_route_candidate_pair_strategies() -> None:
    candidates = [
        (0.95, (1, "best", 0.0, 0.0)),
        (0.88, (2, "near", 20.0, 0.0)),
        (0.77, (3, "far", 200.0, 0.0)),
    ]

    assert ui_svg_route_helpers.choose_svg_route_candidate_pair([], "Top2") is None
    assert ui_svg_route_helpers.choose_svg_route_candidate_pair(candidates[:1], "Top2") is None
    assert ui_svg_route_helpers.choose_svg_route_candidate_pair(candidates, "Top2") == (
        candidates[0],
        candidates[1],
    )
    assert ui_svg_route_helpers.choose_svg_route_candidate_pair(candidates, "Best+Farthest") == (
        candidates[0],
        candidates[2],
    )
    assert ui_svg_route_helpers.choose_svg_route_candidate_pair(candidates, "FarthestPair") == (
        candidates[0],
        candidates[2],
    )


def test_svg_route_coverage_and_autofilter_helpers() -> None:
    edges_map = ui_svg_route_helpers.extract_svg_route_edges_map(
        '{"edges":{"edge-a":[[[0,0],[1,1]]],"edge-b":[[[2,2],[3,3]],[[4,4],[5,5]]]}}'
    )
    mapped_set, unmapped, rows = ui_svg_route_helpers.build_svg_route_coverage(
        ["edge-a", "edge-b", "edge-c"],
        edges_map,
    )

    assert mapped_set == {"edge-a", "edge-b"}
    assert unmapped == ["edge-c"]
    assert rows == [
        {"edge": "edge-a", "mapped": True, "segments": 1},
        {"edge": "edge-b", "mapped": True, "segments": 2},
        {"edge": "edge-c", "mapped": False, "segments": 0},
    ]
    assert ui_svg_route_helpers.extract_svg_route_edges_map("not-json") == {}
    assert ui_svg_route_helpers.suggest_svg_route_filter_text("ЛП 12 main branch") == "ЛП12"
    assert ui_svg_route_helpers.suggest_svg_route_filter_text("Reservoir inlet feed") == "Reservoir"
    assert ui_svg_route_helpers.suggest_svg_route_filter_text("   ") == ""


def test_entrypoints_use_shared_svg_route_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    connectivity_panel_text = CONNECTIVITY_PANEL_HELPERS_PATH.read_text(encoding="utf-8")
    guided_panel_text = GUIDED_PANEL_HELPERS_PATH.read_text(encoding="utf-8")
    auto_panel_text = AUTO_PANEL_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "from pneumo_solver_ui.ui_svg_connectivity_panel_helpers import (" in section_text
    assert "from pneumo_solver_ui.ui_svg_route_helpers import (" in connectivity_panel_text
    assert "build_svg_route_label_items(" in connectivity_panel_text
    assert "build_svg_route_options(" in connectivity_panel_text
    assert "format_svg_route_item" in connectivity_panel_text
    assert "is_noise_svg_route_label(label)" in auto_panel_text
    assert "build_svg_route_candidates(" in guided_panel_text
    assert "build_svg_route_candidates(" in auto_panel_text
    assert "choose_svg_route_candidate_pair(" in auto_panel_text
    assert "extract_svg_route_edges_map(" in guided_panel_text
    assert "build_svg_route_coverage(edge_options, edges_map)" in guided_panel_text
    assert "suggest_svg_route_filter_text(" in guided_panel_text
    assert "def _is_noise_label(s: str) -> bool:" not in app_text
    assert "def _is_noise_label(s: str) -> bool:" not in heavy_text
    assert "def _fmt_item(it):" not in app_text
    assert "def _fmt_item(it):" not in heavy_text
    assert "def _latinize_sig(" not in app_text
    assert "def _latinize_sig(" not in heavy_text
    assert "def _score_edge_label(" not in app_text
    assert "def _score_edge_label(" not in heavy_text
    assert "def _latinize_sig_auto(" not in app_text
    assert "def _latinize_sig_auto(" not in heavy_text
    assert "def _score_edge_label_auto(" not in app_text
    assert "def _score_edge_label_auto(" not in heavy_text
    assert "def _choose_pair(" not in app_text
    assert "def _choose_pair(" not in heavy_text
    assert "_edges_map = extract_svg_route_edges_map(" not in app_text
    assert "_edges_map = extract_svg_route_edges_map(" not in heavy_text
