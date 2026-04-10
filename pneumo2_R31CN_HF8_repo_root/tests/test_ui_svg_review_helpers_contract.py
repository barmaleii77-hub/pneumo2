from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_review_helpers import (
    build_svg_review_conveyor_state,
    render_svg_review_controls,
    step_svg_review_pending_edge,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_review_helpers.py"
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

    def metric(self, label: str, value: int) -> None:
        self.owner.metrics.append((label, value))


class _FakeStreamlit:
    def __init__(self, *, button_presses: dict[str, bool] | None = None) -> None:
        self.button_presses = dict(button_presses or {})
        self.expanders: list[tuple[str, bool]] = []
        self.metrics: list[tuple[str, int]] = []
        self.captions: list[str] = []
        self.checkboxes: list[tuple[str, object, str | None]] = []
        self.multiselects: list[tuple[str, tuple[str, ...], tuple[str, ...], str | None]] = []
        self.rerun_calls = 0

    def columns(self, spec) -> list[_FakeBlock]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeBlock(self) for _ in range(count)]

    def expander(self, label: str, expanded: bool = False) -> _FakeBlock:
        self.expanders.append((label, expanded))
        return _FakeBlock(self)

    def checkbox(self, label: str, value=False, key: str | None = None, help: str | None = None):
        self.checkboxes.append((label, value, key))
        return value

    def multiselect(self, label: str, options, default, key: str | None = None):
        self.multiselects.append((label, tuple(options), tuple(default), key))
        return list(default)

    def button(self, label: str, key: str | None = None):
        return bool(self.button_presses.get(str(key), False))

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def rerun(self) -> None:
        self.rerun_calls += 1


def test_build_svg_review_conveyor_state_counts_and_pending_edges() -> None:
    counts, pending = build_svg_review_conveyor_state(
        '{"edges":{"edge-a":[[[0,0],[1,1]]],"edge-b":[[[1,1],[2,2]]],"edge-c":[[[2,2],[3,3]]],"edge-d":[]},'
        '"edges_meta":{"edge-a":{"review":{"status":"approved"}},"edge-b":{"review":{"status":"pending"}},'
        '"edge-c":{"review":{"status":"rejected"}}}}'
    )

    assert counts == {
        "approved": 1,
        "pending": 1,
        "rejected": 1,
        "unknown": 0,
        "total": 3,
    }
    assert pending == ["edge-b"]

    counts_bad, pending_bad = build_svg_review_conveyor_state("not-json")
    assert counts_bad == {
        "approved": 0,
        "pending": 0,
        "rejected": 0,
        "unknown": 0,
        "total": 0,
    }
    assert pending_bad == []


def test_step_svg_review_pending_edge_wraps_and_clears_node() -> None:
    state = {
        "svg_selected_edge": "edge-b",
        "svg_selected_node": "node-z",
    }
    pending = ["edge-a", "edge-b", "edge-c"]

    assert step_svg_review_pending_edge(state, pending, direction=1) == "edge-c"
    assert state["svg_selected_edge"] == "edge-c"
    assert state["svg_selected_node"] == ""

    assert step_svg_review_pending_edge(state, pending, direction=1) == "edge-a"
    assert step_svg_review_pending_edge(state, pending, direction=-1) == "edge-c"
    assert step_svg_review_pending_edge(state, [], direction=1) is None


def test_render_svg_review_controls_handles_pending_navigation_and_last_review() -> None:
    fake_st = _FakeStreamlit(button_presses={"btn_next_pending": True})
    session_state = {
        "svg_selected_edge": "edge-a",
        "svg_selected_node": "node-a",
        "svg_review_last": {"edge": "edge-b", "status": "approved"},
    }

    render_svg_review_controls(
        fake_st,
        session_state,
        mapping_text='{"edges":{"edge-a":[[[0,0],[1,1]]],"edge-b":[[[1,1],[2,2]]]},'
        '"edges_meta":{"edge-a":{"review":{"status":"unknown"}},"edge-b":{"review":{"status":"pending"}}}}',
    )

    assert fake_st.expanders == [("Review conveyor (pending-first)", False)]
    assert ("approved", 0) in fake_st.metrics
    assert ("pending", 1) in fake_st.metrics
    assert ("unknown", 1) in fake_st.metrics
    assert fake_st.rerun_calls == 1
    assert session_state["svg_selected_edge"] == "edge-b"
    assert session_state["svg_selected_node"] == ""
    assert any("Последнее review: edge-b → approved" == text for text in fake_st.captions)


def test_entrypoints_use_shared_svg_review_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    post_mapping_text = POST_MAPPING_HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "render_svg_review_controls(" not in app_text
    assert "render_svg_review_controls(" not in heavy_text
    assert 'with st.expander("Review conveyor (pending-first)", expanded=False):' not in app_text
    assert 'with st.expander("Review conveyor (pending-first)", expanded=False):' not in heavy_text
    assert 'key="svg_review_auto_advance"' not in app_text
    assert 'key="svg_review_auto_advance"' not in heavy_text
    assert 'key="btn_prev_pending"' not in app_text
    assert 'key="btn_prev_pending"' not in heavy_text
    assert 'key="btn_next_pending"' not in app_text
    assert 'key="btn_next_pending"' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_animation_section_helpers import (" in post_mapping_text
    assert "render_svg_animation_section(" in post_mapping_text
    assert "from pneumo_solver_ui.ui_svg_review_helpers import (" in section_text
    assert "render_svg_review_controls(" in section_text
    assert "build_svg_review_conveyor_state(" in helper_text
    assert "step_svg_review_pending_edge(" in helper_text
