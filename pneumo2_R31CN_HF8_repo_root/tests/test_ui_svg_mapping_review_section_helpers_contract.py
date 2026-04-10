from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_mapping_review_section_helpers as section_helpers
from pneumo_solver_ui.ui_svg_mapping_review_section_helpers import (
    make_svg_edge_first_poly_reader,
    normalize_svg_mapping_review_payload,
    render_svg_mapping_review_section,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_review_section_helpers.py"
POST_MAPPING_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeExpander:
    def __enter__(self) -> "_FakeExpander":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.expanders: list[tuple[str, bool]] = []

    def expander(self, label: str, expanded: bool = False) -> _FakeExpander:
        self.expanders.append((label, expanded))
        return _FakeExpander()


def test_normalize_svg_mapping_review_payload_repairs_shape() -> None:
    mapping_copy, edges_geo, edges_meta = normalize_svg_mapping_review_payload(
        {"edges": [], "edges_meta": None}
    )

    assert mapping_copy["version"] == 2
    assert mapping_copy["edges"] == {}
    assert mapping_copy["nodes"] == {}
    assert mapping_copy["edges_meta"] == {}
    assert edges_geo == {}
    assert edges_meta == {}


def test_make_svg_edge_first_poly_reader_returns_first_polyline() -> None:
    first_poly = make_svg_edge_first_poly_reader(
        {"edge-a": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]], "edge-b": []}
    )

    assert first_poly("edge-a") == [[0, 0], [1, 1]]
    assert first_poly("edge-b") is None
    assert first_poly("missing") is None


def test_render_svg_mapping_review_section_delegates_to_child_helpers(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        section_helpers,
        "render_svg_mapping_review_actions",
        lambda *args, **kwargs: calls.append(("actions", kwargs)),
    )
    monkeypatch.setattr(
        section_helpers,
        "render_svg_mapping_review_panel",
        lambda *args, **kwargs: calls.append(("panel", kwargs)),
    )

    render_svg_mapping_review_section(
        fake_st,
        {"state": "ok"},
        mapping={"edges": {"edge-a": [[[1, 2], [3, 4]]]}, "edges_meta": {}},
        edge_columns=["edge-a"],
        evaluate_quality_fn="quality_fn",
        safe_dataframe_fn="safe_df",
    )

    assert fake_st.expanders == [("Review / Quality: mapping.edges_meta (approve/reject)", False)]
    assert [name for name, _payload in calls] == ["actions", "panel"]
    actions_kwargs = calls[0][1]
    panel_kwargs = calls[1][1]
    assert actions_kwargs["evaluate_quality_fn"] == "quality_fn"
    assert panel_kwargs["edge_columns"] == ["edge-a"]
    assert panel_kwargs["safe_dataframe_fn"] == "safe_df"
    assert actions_kwargs["first_poly_fn"]("edge-a") == [[1, 2], [3, 4]]


def test_entrypoints_use_shared_svg_mapping_review_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    post_mapping_text = POST_MAPPING_HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "render_svg_mapping_review_section(" not in app_text
    assert "render_svg_mapping_review_section(" not in heavy_text
    assert 'with st.expander("Review / Quality: mapping.edges_meta (approve/reject)", expanded=False):' not in app_text
    assert 'with st.expander("Review / Quality: mapping.edges_meta (approve/reject)", expanded=False):' not in heavy_text
    assert "mapping2 = copy.deepcopy(mapping)" not in app_text
    assert "mapping2 = copy.deepcopy(mapping)" not in heavy_text
    assert "def _first_poly(edge_name: str):" not in app_text
    assert "def _first_poly(edge_name: str):" not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_mapping_review_section_helpers import (" in post_mapping_text
    assert "render_svg_mapping_review_section(" in post_mapping_text
    assert "render_svg_mapping_review_actions(" in helper_text
    assert "render_svg_mapping_review_panel(" in helper_text
