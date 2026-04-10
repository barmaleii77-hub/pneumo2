from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_svg_animation_panel_helpers import render_svg_animation_panel


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_animation_panel_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_animation_section_helpers.py"
POST_MAPPING_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.captions: list[str] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)


def test_render_svg_animation_panel_uses_component_when_available() -> None:
    fake_st = _FakeStreamlit()
    session_state = {
        "svg_selected_edge": "edge-a",
        "svg_selected_node": "node-b",
        "svg_show_review_overlay": True,
        "svg_review_pick_mode": False,
        "svg_review_statuses": ["approved", "pending"],
        "svg_review_hud": True,
        "svg_route_paths": [[[1.0, 2.0], [3.0, 4.0]]],
        "svg_label_pick_mode": "start",
        "svg_route_label_picks": {"start": "edge-a"},
        "svg_label_pick_radius": 21,
    }
    calls: list[dict[str, object]] = []

    def _component(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    result = render_svg_animation_panel(
        fake_st,
        session_state,
        svg_inline="<svg />",
        mapping={"edges": {}},
        time_s=[0.0, 1.0],
        edge_series=[{"name": "edge-a"}],
        node_series=[{"name": "node-b"}],
        dataset_id="dataset-1",
        get_component_fn=lambda: _component,
        render_svg_flow_animation_html_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("fallback not expected")),
    )

    assert result == {"ok": True}
    assert len(calls) == 1
    call = calls[0]
    assert call["title"] == "Анимация по схеме (SVG)"
    assert call["selected"] == {"edge": "edge-a", "node": "node-b"}
    assert call["playhead_storage_key"] == "pneumo_play_state"
    assert call["dataset_id"] == "dataset-1"
    assert call["height"] == 760
    assert call["key"] == "svg_pick_event"
    assert fake_st.captions == ["Клик по ветке/узлу на схеме добавляет/заменяет выбор в графиках (см. переключатель выше)."]


def test_render_svg_animation_panel_falls_back_to_html_renderer() -> None:
    fake_st = _FakeStreamlit()
    fallback_calls: list[dict[str, object]] = []

    result = render_svg_animation_panel(
        fake_st,
        {},
        svg_inline="<svg />",
        mapping={"nodes": {}},
        time_s=[0.0],
        edge_series=[{"name": "edge-a", "q": [1.0]}],
        node_series=[],
        dataset_id="dataset-2",
        get_component_fn=lambda: None,
        render_svg_flow_animation_html_fn=lambda **kwargs: fallback_calls.append(kwargs),
    )

    assert result is None
    assert fallback_calls == [
        {
            "svg_inline": "<svg />",
            "mapping": {"nodes": {}},
            "time_s": [0.0],
            "edge_series": [{"name": "edge-a", "q": [1.0]}],
            "node_series": [],
            "height": 760,
        }
    ]
    assert fake_st.captions == []


def test_entrypoints_use_shared_svg_animation_panel_helper() -> None:
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
    assert "render_svg_animation_panel(" not in app_text
    assert "render_svg_animation_panel(" not in heavy_text
    assert "comp = get_pneumo_svg_flow_component()" not in app_text
    assert "comp = get_pneumo_svg_flow_component()" not in heavy_text
    assert "_evt = comp(" not in app_text
    assert "_evt = comp(" not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_animation_section_helpers import (" in post_mapping_text
    assert "render_svg_animation_section(" in post_mapping_text
    assert "from pneumo_solver_ui.ui_svg_animation_panel_helpers import (" in section_text
    assert "render_svg_animation_panel(" in section_text
    assert "get_component_fn=get_component_fn," in section_text
    assert "render_svg_flow_animation_html_fn=render_svg_flow_animation_html_fn," in section_text
    assert "playhead_storage_key=\"pneumo_play_state\"" in helper_text
    assert "key=\"svg_pick_event\"" in helper_text
