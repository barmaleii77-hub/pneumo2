from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_animation_mode_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_animation_mode_helpers.py"


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


def test_entrypoints_use_shared_animation_mode_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_animation_mode_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_animation_mode_helpers import (" in heavy_text
    assert "render_animation_view_selector(" in app_text
    assert "render_animation_view_selector(" in heavy_text
    assert "render_non_mechanical_animation_subsection(" in app_text
    assert "render_non_mechanical_animation_subsection(" in heavy_text
    assert 'key=f"anim_view_{cur_hash}::{test_pick}"' not in app_text
    assert 'key=f"anim_view_{cur_hash}::{test_pick}"' not in heavy_text
    assert "ANIMATION_VIEW_OPTIONS = [" in helper_text
    assert "return st.radio(" in helper_text
    assert "render_flow_tool_fn()" in helper_text
    assert "render_svg_scheme_fn()" in helper_text
