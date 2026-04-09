from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_animation_mode_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_animation_mode_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_animation_results_section_helpers.py"


class _FakeStreamlit:
    def __init__(self, selected_view: str) -> None:
        self.selected_view = selected_view
        self.subheaders: list[str] = []
        self.radios: list[tuple[str, list[str], bool, str]] = []

    def subheader(self, text: str) -> None:
        self.subheaders.append(text)

    def radio(self, label: str, *, options, horizontal: bool, key: str) -> str:
        self.radios.append((label, list(options), horizontal, key))
        return self.selected_view


def test_render_animation_view_selector_uses_shared_radio_contract() -> None:
    fake_st = _FakeStreamlit(helpers.ANIMATION_VIEW_SVG_SCHEME)

    selected = helpers.render_animation_view_selector(
        fake_st,
        cur_hash="hash-1",
        test_pick="test-1",
    )

    assert selected == helpers.ANIMATION_VIEW_SVG_SCHEME
    assert fake_st.subheaders == ["Анимация"]
    assert fake_st.radios == [
        (
            "Подраздел",
            helpers.ANIMATION_VIEW_OPTIONS,
            True,
            "anim_view_hash-1::test-1",
        )
    ]


def test_render_non_mechanical_animation_subsection_dispatches_by_view() -> None:
    calls: list[str] = []

    handled_flow = helpers.render_non_mechanical_animation_subsection(
        helpers.ANIMATION_VIEW_FLOW_TOOL,
        render_flow_tool_fn=lambda: calls.append("flow"),
        render_svg_scheme_fn=lambda: calls.append("svg"),
    )
    handled_svg = helpers.render_non_mechanical_animation_subsection(
        helpers.ANIMATION_VIEW_SVG_SCHEME,
        render_flow_tool_fn=lambda: calls.append("flow-2"),
        render_svg_scheme_fn=lambda: calls.append("svg-2"),
    )
    handled_mech = helpers.render_non_mechanical_animation_subsection(
        helpers.ANIMATION_VIEW_MECHANICS,
        render_flow_tool_fn=lambda: calls.append("flow-3"),
        render_svg_scheme_fn=lambda: calls.append("svg-3"),
    )

    assert handled_flow is True
    assert handled_svg is True
    assert handled_mech is False
    assert calls == ["flow", "svg-2"]


def test_render_animation_section_dispatches_mechanics_and_non_mechanics() -> None:
    calls: list[str] = []

    helpers.render_animation_section(
        _FakeStreamlit(helpers.ANIMATION_VIEW_MECHANICS),
        cur_hash="hash-2",
        test_pick="test-2",
        render_mechanics_fn=lambda: calls.append("mech"),
        render_flow_tool_fn=lambda: calls.append("flow"),
        render_svg_scheme_fn=lambda: calls.append("svg"),
    )
    helpers.render_animation_section(
        _FakeStreamlit(helpers.ANIMATION_VIEW_FLOW_TOOL),
        cur_hash="hash-3",
        test_pick="test-3",
        render_mechanics_fn=lambda: calls.append("mech-2"),
        render_flow_tool_fn=lambda: calls.append("flow-2"),
        render_svg_scheme_fn=lambda: calls.append("svg-2"),
    )
    helpers.render_animation_section(
        _FakeStreamlit(helpers.ANIMATION_VIEW_SVG_SCHEME),
        cur_hash="hash-4",
        test_pick="test-4",
        render_mechanics_fn=lambda: calls.append("mech-3"),
        render_flow_tool_fn=lambda: calls.append("flow-3"),
        render_svg_scheme_fn=lambda: calls.append("svg-3"),
    )

    assert calls == ["mech", "flow-2", "svg-3"]


def test_render_animation_results_section_builds_flow_and_svg_dispatch() -> None:
    calls: list[tuple[str, object]] = []

    selected = helpers.render_animation_results_section(
        _FakeStreamlit(helpers.ANIMATION_VIEW_FLOW_TOOL),
        cur_hash="hash-5",
        test_pick="test-5",
        render_mechanics_panel_fn=lambda st, **kwargs: calls.append(("mech", kwargs["token"])),
        mechanics_panel_kwargs={"token": "mech-token"},
        render_flow_tool_panel_fn=lambda st, **kwargs: calls.append(("flow", kwargs["token"])),
        flow_panel_kwargs={"token": "flow-token"},
        render_svg_scheme_section_fn=lambda st, session_state, **kwargs: calls.append(("svg", kwargs["token"])),
        svg_scheme_args=({"session": True},),
        svg_scheme_kwargs={"token": "svg-token"},
    )

    assert selected == helpers.ANIMATION_VIEW_FLOW_TOOL
    assert calls == [("flow", "flow-token")]


def test_entrypoints_use_shared_animation_mode_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_animation_mode_helpers import render_animation_results_section" not in app_text
    assert "from pneumo_solver_ui.ui_animation_mode_helpers import render_animation_results_section" not in heavy_text
    assert "render_animation_results_section(" not in app_text
    assert "render_animation_results_section(" not in heavy_text
    assert "def _render_mechanical_animation" not in app_text
    assert "def _render_mechanical_animation" not in heavy_text
    assert "render_animation_section(" not in app_text
    assert "render_animation_section(" not in heavy_text
    assert "render_animation_view_selector(" not in app_text
    assert "render_animation_view_selector(" not in heavy_text
    assert "render_non_mechanical_animation_subsection(" not in app_text
    assert "render_non_mechanical_animation_subsection(" not in heavy_text
    assert "ANIMATION_VIEW_MECHANICS" not in app_text
    assert "ANIMATION_VIEW_MECHANICS" not in heavy_text
    assert 'key=f"anim_view_{cur_hash}::{test_pick}"' not in app_text
    assert 'key=f"anim_view_{cur_hash}::{test_pick}"' not in heavy_text
    assert "from pneumo_solver_ui.ui_animation_mode_helpers import render_animation_results_section" in section_text
    assert "render_animation_results_section(" in section_text
    assert "ANIMATION_VIEW_OPTIONS = [" in helper_text
    assert "return st.radio(" in helper_text
    assert "render_mechanics_fn()" in helper_text
    assert "render_flow_tool_fn()" in helper_text
    assert "render_svg_scheme_fn()" in helper_text
    assert "render_mechanics_panel_fn(st, **mechanics_panel_kwargs)" in helper_text
    assert "render_flow_tool_panel_fn(st, **flow_panel_kwargs)" in helper_text
    assert "render_svg_scheme_section_fn(st, *svg_scheme_args, **svg_scheme_kwargs)" in helper_text
