from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_flow_animation_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


class _FakeStreamlit:
    def __init__(self, *, selected_edges=None) -> None:
        self.selected_edges = list(selected_edges or [])
        self.infos: list[str] = []
        self.captions: list[str] = []

    def info(self, text):
        self.infos.append(text)

    def caption(self, text):
        self.captions.append(text)

    def multiselect(self, label, *, options, default, key):
        assert label == "Ветки для анимации"
        assert key == "anim_edges"
        assert default == ui_flow_animation_helpers.default_flow_animation_edges(options)
        return [item for item in self.selected_edges if item in options]


def test_flow_animation_defaults_and_series_builder() -> None:
    edge_columns = ["edge_a", "выхлоп_main", "edge_b"]
    assert ui_flow_animation_helpers.default_flow_animation_edges(edge_columns) == ["выхлоп_main"]
    assert ui_flow_animation_helpers.default_flow_animation_edges(["a", "b"], limit=1) == ["a"]

    df_mdot = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_a": [1.0, 2.0],
            "edge_b": [3.0, 4.0],
        }
    )
    df_open = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_b": [0, 1],
        }
    )
    time_s, edge_series = ui_flow_animation_helpers.build_flow_animation_edge_series(
        df_mdot,
        selected_edges=["edge_b"],
        scale=60.0,
        unit="Нл/мин",
        df_open=df_open,
    )
    assert time_s == [0.0, 1.0]
    assert edge_series == [
        {"name": "edge_b", "q": [180.0, 240.0], "open": [0, 1], "unit": "Нл/мин"}
    ]


def test_render_flow_animation_panel() -> None:
    df_mdot = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_a": [1.0, 2.0],
            "edge_b": [3.0, 4.0],
        }
    )
    df_open = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_b": [0, 1],
        }
    )
    fake_st = _FakeStreamlit(selected_edges=["edge_b"])
    render_calls: list[dict[str, object]] = []

    def _scale_and_unit(*, p_atm, model_module):
        assert p_atm == 101325.0
        assert model_module == "model"
        return 60.0, "Нл/мин"

    def _render_flow_panel_html(*, time_s, edge_series, height):
        render_calls.append(
            {
                "time_s": time_s,
                "edge_series": edge_series,
                "height": height,
            }
        )

    result = ui_flow_animation_helpers.render_flow_animation_panel(
        fake_st,
        df_mdot=df_mdot,
        df_open=df_open,
        p_atm=101325.0,
        model_module="model",
        flow_scale_and_unit_fn=_scale_and_unit,
        render_flow_panel_html_fn=_render_flow_panel_html,
    )

    assert result == {
        "status": "ok",
        "edge_columns": ["edge_a", "edge_b"],
        "selected_edges": ["edge_b"],
        "unit": "Нл/мин",
        "scale": 60.0,
    }
    assert fake_st.infos == []
    assert fake_st.captions == ["MVP: каждая выбранная ветка рисуется отдельной линией, по ней бегает маркер."]
    assert render_calls == [
        {
            "time_s": [0.0, 1.0],
            "edge_series": [{"name": "edge_b", "q": [180.0, 240.0], "open": [0, 1], "unit": "Нл/мин"}],
            "height": 560,
        }
    ]


def test_render_flow_animation_panel_empty_states() -> None:
    fake_st = _FakeStreamlit()

    result_no_data = ui_flow_animation_helpers.render_flow_animation_panel(
        fake_st,
        df_mdot=None,
        df_open=None,
        p_atm=0.0,
        model_module=None,
        flow_scale_and_unit_fn=lambda **kwargs: (1.0, "x"),
        render_flow_panel_html_fn=lambda **kwargs: None,
    )
    assert result_no_data == {"status": "no_data", "selected_edges": []}
    assert fake_st.infos == ["Анимация потоков доступна только при record_full=True (df_mdot)."]

    df_mdot = pd.DataFrame({"время_с": [0.0], "edge_a": [1.0]})
    fake_st_empty = _FakeStreamlit(selected_edges=[])
    result_empty = ui_flow_animation_helpers.render_flow_animation_panel(
        fake_st_empty,
        df_mdot=df_mdot,
        df_open=None,
        p_atm=0.0,
        model_module=None,
        flow_scale_and_unit_fn=lambda **kwargs: (1.0, "x"),
        render_flow_panel_html_fn=lambda **kwargs: None,
    )
    assert result_empty == {"status": "no_selection", "selected_edges": []}
    assert fake_st_empty.infos == ["Выберите хотя бы одну ветку."]


def test_entrypoints_use_shared_flow_animation_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_flow_animation_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_flow_animation_helpers import (" in heavy_text
    assert "render_flow_animation_panel(" in app_text
    assert "render_flow_animation_panel(" in heavy_text
    assert 'pick_edges = st.multiselect("Ветки для анимации"' not in app_text
    assert 'pick_edges = st.multiselect("Ветки для анимации"' not in heavy_text
    assert 'render_flow_panel_html(time_s=time_s, edge_series=edge_series, height=560)' not in app_text
    assert 'render_flow_panel_html(time_s=time_s, edge_series=edge_series, height=560)' not in heavy_text
    assert 'st.caption("MVP: каждая выбранная ветка рисуется отдельной линией, по ней бегает маркер.")' not in app_text
    assert 'st.caption("MVP: каждая выбранная ветка рисуется отдельной линией, по ней бегает маркер.")' not in heavy_text
