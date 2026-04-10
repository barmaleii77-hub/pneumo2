from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_scheme_input_helpers as input_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_input_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.captions: list[str] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)


def test_render_svg_scheme_inputs_delegates_to_shared_flow_helpers(monkeypatch, tmp_path) -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        input_helpers,
        "render_svg_click_mode_selector",
        lambda st, *, key: calls.append(("click_mode", key)) or "add",
    )
    monkeypatch.setattr(
        input_helpers,
        "svg_edge_columns",
        lambda df: calls.append(("edge_columns", df)) or ["edge-a", "edge-b"],
    )
    monkeypatch.setattr(
        input_helpers,
        "svg_pressure_node_columns",
        lambda df: calls.append(("node_columns", df)) or ["node-a", "node-b"],
    )
    monkeypatch.setattr(
        input_helpers,
        "render_svg_pressure_node_selector",
        lambda st, node_columns, *, key: calls.append(("node_selector", (node_columns, key))) or ["node-b"],
    )
    monkeypatch.setattr(
        input_helpers,
        "render_svg_source_template_controls",
        lambda st, **kwargs: calls.append(("source", kwargs)) or ("<svg/>", "<svg/>"),
    )

    result = input_helpers.render_svg_scheme_inputs(
        fake_st,
        df_mdot="df_mdot",
        df_p="df_p",
        base_dir=tmp_path,
    )

    assert len(fake_st.captions) == 1
    assert result == {
        "edge_columns": ["edge-a", "edge-b"],
        "node_columns": ["node-a", "node-b"],
        "selected_node_names": ["node-b"],
        "svg_inline": "<svg/>",
    }
    assert [name for name, _payload in calls] == [
        "click_mode",
        "edge_columns",
        "node_columns",
        "node_selector",
        "source",
    ]
    assert calls[4][1]["edge_columns"] == ["edge-a", "edge-b"]
    assert calls[4][1]["selected_node_names"] == ["node-b"]


def test_render_svg_scheme_inputs_returns_none_without_svg_inline(monkeypatch, tmp_path) -> None:
    fake_st = _FakeStreamlit()

    monkeypatch.setattr(input_helpers, "render_svg_click_mode_selector", lambda *args, **kwargs: "add")
    monkeypatch.setattr(input_helpers, "svg_edge_columns", lambda df: ["edge-a"])
    monkeypatch.setattr(input_helpers, "svg_pressure_node_columns", lambda df: ["node-a"])
    monkeypatch.setattr(input_helpers, "render_svg_pressure_node_selector", lambda *args, **kwargs: ["node-a"])
    monkeypatch.setattr(
        input_helpers,
        "render_svg_source_template_controls",
        lambda st, **kwargs: (None, None),
    )

    result = input_helpers.render_svg_scheme_inputs(
        fake_st,
        df_mdot="df_mdot",
        df_p="df_p",
        base_dir=tmp_path,
    )

    assert result is None


def test_entrypoints_use_shared_svg_scheme_input_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "from pneumo_solver_ui.ui_svg_scheme_input_helpers import (" in section_text
    assert "render_svg_scheme_inputs(" in section_text
    assert "render_svg_click_mode_selector(" not in section_text
    assert "render_svg_pressure_node_selector(" not in section_text
    assert "render_svg_source_template_controls(" not in section_text
    assert "from pneumo_solver_ui.ui_svg_flow_helpers import (" in helper_text
    assert "render_svg_click_mode_selector(" in helper_text
    assert "render_svg_pressure_node_selector(" in helper_text
    assert "render_svg_source_template_controls(" in helper_text
