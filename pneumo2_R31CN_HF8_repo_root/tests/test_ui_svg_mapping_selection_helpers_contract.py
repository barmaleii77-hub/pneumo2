from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_mapping_selection_helpers import (
    prepare_svg_mapping_selection,
    render_svg_mapping_selection_report,
    resolve_svg_mapping_selection,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_selection_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_animation_section_helpers.py"
POST_MAPPING_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeBlock:
    def __init__(self, owner: "_FakeStreamlit") -> None:
        self.owner = owner

    def __enter__(self) -> "_FakeBlock":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.expanders: list[tuple[str, bool]] = []
        self.markdowns: list[str] = []

    def expander(self, label: str, expanded: bool = False) -> _FakeBlock:
        self.expanders.append((label, expanded))
        return _FakeBlock(self)

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)


def test_resolve_svg_mapping_selection_respects_auto_match_flag() -> None:
    base_mapping = {"edges": {}, "nodes": {}}

    mapping_keep, report_keep = resolve_svg_mapping_selection(
        base_mapping,
        need_edges=["edge-a"],
        need_nodes=["node-a"],
        auto_match=False,
        min_score=0.7,
    )
    assert mapping_keep is base_mapping
    assert report_keep == {"edges": [], "nodes": []}

    mapping_auto, report_auto = resolve_svg_mapping_selection(
        {
            "edges": {"Line A": [{"x1": 0, "y1": 0, "x2": 1, "y2": 1}]},
            "nodes": {"Node Main": [10, 20]},
        },
        need_edges=["line-a"],
        need_nodes=["node_main"],
        auto_match=True,
        min_score=0.6,
    )
    assert mapping_auto["edges"]["line-a"] == [{"x1": 0, "y1": 0, "x2": 1, "y2": 1}]
    assert mapping_auto["nodes"]["node_main"] == [10, 20]
    assert report_auto["edges"][0]["from"] == "Line A"
    assert report_auto["nodes"][0]["from"] == "Node Main"


def test_render_and_prepare_svg_mapping_selection_report() -> None:
    fake_st = _FakeStreamlit()
    frames: list[tuple[list[str], int]] = []
    report = {
        "edges": [{"from": "a", "to": "b", "score": 0.9}],
        "nodes": [{"from": "x", "to": "y", "score": 0.8}],
    }

    render_svg_mapping_selection_report(
        fake_st,
        report,
        safe_dataframe_fn=lambda frame, height: frames.append((list(frame.columns), height)),
    )

    assert fake_st.expanders == [("Отчёт автосопоставления", False)]
    assert fake_st.markdowns == ["**Ветки (edges)**", "**Узлы (nodes)**"]
    assert frames == [
        (["from", "to", "score"], 220),
        (["from", "to", "score"], 220),
    ]

    frames.clear()
    fake_st_2 = _FakeStreamlit()
    mapping_use, report_use = prepare_svg_mapping_selection(
        fake_st_2,
        {"edges": {}, "nodes": {}},
        need_edges=["edge-a"],
        need_nodes=["node-a"],
        auto_match=False,
        min_score=0.6,
        safe_dataframe_fn=lambda frame, height: frames.append((list(frame.columns), height)),
    )
    assert mapping_use == {"edges": {}, "nodes": {}}
    assert report_use == {"edges": [], "nodes": []}
    assert fake_st_2.expanders == []
    assert frames == []


def test_entrypoints_use_shared_svg_mapping_selection_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    post_mapping_text = POST_MAPPING_HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "prepare_svg_mapping_selection(" not in app_text
    assert "prepare_svg_mapping_selection(" not in heavy_text
    assert "ensure_mapping_for_selection," not in app_text
    assert "ensure_mapping_for_selection," not in heavy_text
    assert 'with st.expander("Отчёт автосопоставления", expanded=False):' not in app_text
    assert 'with st.expander("Отчёт автосопоставления", expanded=False):' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_animation_section_helpers import (" in post_mapping_text
    assert "render_svg_animation_section(" in post_mapping_text
    assert "from pneumo_solver_ui.ui_svg_mapping_selection_helpers import (" in section_text
    assert "prepare_svg_mapping_selection(" in section_text
    assert "from pneumo_solver_ui.ui_interaction_helpers import (" in helper_text
    assert "ensure_mapping_for_selection(" in helper_text
