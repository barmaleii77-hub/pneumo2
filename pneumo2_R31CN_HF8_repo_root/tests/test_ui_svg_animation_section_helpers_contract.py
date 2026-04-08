from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_animation_section_helpers as section_helpers
from pneumo_solver_ui.ui_svg_animation_section_helpers import (
    default_svg_animation_edges,
    filter_svg_animation_edges_by_review,
    render_svg_animation_section,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_animation_section_helpers.py"
POST_MAPPING_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warning_messages: list[str] = []
        self.checkbox_calls: list[tuple[str, bool, str | None]] = []
        self.multiselect_calls: list[tuple[str, tuple[str, ...], tuple[str, ...], str | None]] = []

    def checkbox(self, label: str, value: bool = False, key: str | None = None):
        self.checkbox_calls.append((label, value, key))
        return value

    def slider(self, label: str, min_value, max_value, value, step, key: str | None = None):
        return value

    def multiselect(self, label: str, options, default, key: str | None = None):
        self.multiselect_calls.append((label, tuple(options), tuple(default), key))
        return list(default)

    def info(self, text: str) -> None:
        self.info_messages.append(text)

    def warning(self, text: str) -> None:
        self.warning_messages.append(text)


def test_filter_svg_animation_edges_by_review_respects_approved_only() -> None:
    mapping = {
        "edges_meta": {
            "edge-a": {"review": {"status": "approved"}},
            "edge-b": {"review": {"status": "pending"}},
            "edge-c": {"review": {"status": "approved"}},
        }
    }
    edge_columns = ["edge-a", "edge-b", "edge-c"]

    assert filter_svg_animation_edges_by_review(edge_columns, mapping, approved_only=False) == edge_columns
    assert filter_svg_animation_edges_by_review(edge_columns, mapping, approved_only=True) == [
        "edge-a",
        "edge-c",
    ]
    assert filter_svg_animation_edges_by_review(["edge-x"], {"edges_meta": {}}, approved_only=True) == [
        "edge-x"
    ]


def test_default_svg_animation_edges_falls_back_to_first_six() -> None:
    edge_options = [f"edge-{idx}" for idx in range(8)]
    assert default_svg_animation_edges(edge_options) == edge_options[:6]


def test_render_svg_animation_section_orchestrates_child_helpers(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    calls: dict[str, object] = {}

    def _prepare_selection(st_module, mapping, **kwargs):
        calls["prepare_selection"] = {
            "st_module": st_module,
            "mapping": mapping,
            **kwargs,
        }
        return {"edges": {"edge-a": []}, "nodes": {"node-a": [0.0, 1.0]}}, {"edges": [], "nodes": []}

    def _prepare_series(**kwargs):
        calls["prepare_series"] = kwargs
        return {
            "time_s": [0.0, 1.0],
            "edge_series": [{"name": "edge-a"}],
            "node_series": [{"name": "node-a"}],
            "missing_edges": ["edge-a"],
            "missing_nodes": ["node-a"],
        }

    def _render_review_controls(st_module, session_state, **kwargs):
        calls["review"] = {
            "st_module": st_module,
            "session_state": session_state,
            **kwargs,
        }

    def _render_animation_panel(st_module, session_state, **kwargs):
        calls["panel"] = {
            "st_module": st_module,
            "session_state": session_state,
            **kwargs,
        }

    monkeypatch.setattr(section_helpers, "prepare_svg_mapping_selection", _prepare_selection)
    monkeypatch.setattr(section_helpers, "prepare_svg_animation_series", _prepare_series)
    monkeypatch.setattr(section_helpers, "render_svg_review_controls", _render_review_controls)
    monkeypatch.setattr(section_helpers, "render_svg_animation_panel", _render_animation_panel)

    session_state = {"svg_mapping_text": '{"edges":{}}'}
    result = render_svg_animation_section(
        fake_st,
        session_state,
        mapping={"edges": {}, "nodes": {}},
        edge_columns=["edge-a", "edge-b"],
        selected_node_names=["node-a"],
        df_mdot="df_mdot",
        df_open="df_open",
        df_p="df_p",
        p_atm=101325.0,
        model_module="model",
        pressure_divisor=101325.0,
        pressure_unit="atm",
        dataset_id="dataset-1",
        safe_dataframe_fn="safe_df",
        flow_scale_and_unit_fn=lambda **kwargs: (60.0, "Nl/min"),
        get_component_fn="component_factory",
        render_svg_flow_animation_html_fn="html_renderer",
        svg_inline="<svg />",
    )

    assert result["status"] == "ok"
    assert result["selected_edges"] == ["edge-a", "edge-b"]
    assert result["scale"] == 60.0
    assert result["unit"] == "Nl/min"
    assert calls["prepare_selection"]["need_edges"] == ["edge-a", "edge-b"]
    assert calls["prepare_selection"]["need_nodes"] == ["node-a"]
    assert calls["prepare_series"]["selected_edges"] == ["edge-a", "edge-b"]
    assert calls["prepare_series"]["pressure_divisor"] == 101325.0
    assert calls["review"]["mapping_text"] == '{"edges":{}}'
    assert calls["panel"]["dataset_id"] == "dataset-1"
    assert calls["panel"]["svg_inline"] == "<svg />"
    assert len(fake_st.warning_messages) == 2


def test_entrypoints_use_svg_animation_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    post_mapping_text = POST_MAPPING_HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "render_svg_animation_section(" not in app_text
    assert "render_svg_animation_section(" not in heavy_text
    assert "edge_options_anim = edge_cols" not in app_text
    assert "edge_options_anim = edge_cols" not in heavy_text
    assert "auto_match = st.checkbox(" not in app_text
    assert "auto_match = st.checkbox(" not in heavy_text
    assert "min_score = st.slider(" not in app_text
    assert "min_score = st.slider(" not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_animation_section_helpers import (" in post_mapping_text
    assert "render_svg_animation_section(" in post_mapping_text
    assert "prepare_svg_mapping_selection(" in helper_text
    assert "prepare_svg_animation_series(" in helper_text
    assert "render_svg_review_controls(" in helper_text
    assert "render_svg_animation_panel(" in helper_text
