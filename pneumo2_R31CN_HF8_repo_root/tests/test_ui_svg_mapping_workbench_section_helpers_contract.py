from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_mapping_workbench_section_helpers as workbench_helpers
from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (
    default_svg_mapper_node_names,
    render_svg_mapping_workbench_section,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
HELPERS_PATH = (
    REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
)


class _FakeBlock:
    def __enter__(self) -> "_FakeBlock":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.expanders: list[tuple[str, bool]] = []
        self.infos: list[str] = []

    def expander(self, label: str, expanded: bool = False) -> _FakeBlock:
        self.expanders.append((label, expanded))
        return _FakeBlock()

    def info(self, text: str) -> None:
        self.infos.append(text)


def test_default_svg_mapper_node_names_prefers_selected_nodes() -> None:
    assert default_svg_mapper_node_names(["n1", "n2"], ["x", "y"]) == ["n1", "n2"]
    assert default_svg_mapper_node_names(None, [f"n{i}" for i in range(25)]) == [
        f"n{i}" for i in range(20)
    ]
    assert default_svg_mapper_node_names(None, []) == []


def test_render_svg_mapping_workbench_section_delegates_to_mapper_and_tools(
    monkeypatch,
    tmp_path,
) -> None:
    fake_st = _FakeStreamlit()
    session_state = {"svg_mapping_text": '{"edges":{}}'}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        workbench_helpers,
        "render_svg_edge_mapper_html",
        lambda **kwargs: calls.append(("edge", kwargs)),
    )
    monkeypatch.setattr(
        workbench_helpers,
        "render_svg_node_mapper_html",
        lambda **kwargs: calls.append(("node", kwargs)),
    )
    monkeypatch.setattr(
        workbench_helpers,
        "render_svg_mapping_tools_section",
        lambda *args, **kwargs: calls.append(("tools", kwargs)) or {"edges": {}},
    )

    mapping = render_svg_mapping_workbench_section(
        fake_st,
        session_state,
        default_svg_mapping_path=tmp_path / "default.json",
        do_rerun_fn="rerun",
        log_event_fn="log",
        edge_columns=["edge-a", "edge-b"],
        node_columns=[f"node-{idx}" for idx in range(30)],
        selected_node_names=None,
        df_mdot="df_mdot",
        df_open="df_open",
        df_p="df_p",
        p_atm=101325.0,
        model_module="model",
        pressure_divisor=101325.0,
        pressure_unit="atm",
        dataset_id="dataset-1",
        safe_dataframe_fn="safe_df",
        flow_scale_and_unit_fn="flow_fn",
        get_component_fn="component_fn",
        render_svg_flow_animation_html_fn="html_fn",
        svg_inline="<svg />",
        evaluate_quality_fn="quality_fn",
    )

    assert mapping == {"edges": {}}
    assert fake_st.expanders == [
        ("Разметка веток (edges)", False),
        ("Разметка узлов давления (nodes)", False),
    ]
    assert len(fake_st.infos) == 2
    assert [name for name, _payload in calls] == ["edge", "node", "tools"]
    assert calls[0][1]["edge_names"] == ["edge-a", "edge-b"]
    assert calls[1][1]["node_names"] == [f"node-{idx}" for idx in range(20)]
    assert calls[1][1]["edge_names"] == ["edge-a", "edge-b"]
    assert calls[2][1]["edge_columns"] == ["edge-a", "edge-b"]
    assert calls[2][1]["selected_node_names"] is None


def test_entrypoints_use_shared_svg_mapping_workbench_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "render_svg_mapping_workbench_section(" not in app_text
    assert "render_svg_mapping_workbench_section(" not in heavy_text
    assert 'with st.expander("Разметка веток (edges)", expanded=False):' not in app_text
    assert 'with st.expander("Разметка веток (edges)", expanded=False):' not in heavy_text
    assert 'with st.expander("Разметка узлов давления (nodes)", expanded=False):' not in app_text
    assert 'with st.expander("Разметка узлов давления (nodes)", expanded=False):' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in section_text
    assert "render_svg_mapping_workbench_section(" in section_text
    assert "from pneumo_solver_ui.ui_svg_html_builders import (" in helper_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in helper_text
    assert "render_svg_edge_mapper_html(" in helper_text
    assert "render_svg_node_mapper_html(" in helper_text
    assert "render_svg_mapping_tools_section(" in helper_text
