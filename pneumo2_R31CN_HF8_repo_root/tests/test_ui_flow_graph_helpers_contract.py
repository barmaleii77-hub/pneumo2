from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui import ui_flow_graph_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


class _FakeStreamlit:
    def __init__(self, *, selected_edges=None) -> None:
        self.selected_edges = list(selected_edges or [])
        self.subheaders: list[str] = []
        self.infos: list[str] = []
        self.captions: list[str] = []

    def subheader(self, text):
        self.subheaders.append(text)

    def info(self, text):
        self.infos.append(text)

    def caption(self, text):
        self.captions.append(text)

    def multiselect(self, label, *, options, default, key):
        assert label == "Ветки/элементы"
        assert key == "flow_graph_edges"
        assert default == options[: min(6, len(options))]
        return [item for item in self.selected_edges if item in options]


def test_flow_edge_helpers() -> None:
    df_mdot = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_a": [1.0, 2.0],
            "edge_b": [3.0, 4.0],
        }
    )
    assert ui_flow_graph_helpers.flow_edge_columns(df_mdot) == ["edge_a", "edge_b"]
    assert ui_flow_graph_helpers.default_flow_edge_selection(["a", "b", "c"], limit=2) == ["a", "b"]


def test_render_flow_edge_graphs_section() -> None:
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
            "edge_b": [0.0, 1.0],
        }
    )
    fake_st = _FakeStreamlit(selected_edges=["edge_b"])
    plot_calls: list[dict[str, object]] = []

    def _plot_lines(*args, **kwargs):
        plot_calls.append({"args": args, "kwargs": kwargs})

    def _scale_and_unit(*, p_atm, model_module):
        assert p_atm == 101325.0
        assert model_module == "model"
        return 60.0, "Нл/мин"

    result = ui_flow_graph_helpers.render_flow_edge_graphs_section(
        fake_st,
        df_mdot=df_mdot,
        df_open=df_open,
        playhead_x=1.25,
        events_for_graphs=[{"t": 0.5}],
        events_graph_max=120,
        events_graph_labels=True,
        p_atm=101325.0,
        model_module="model",
        plot_lines_fn=_plot_lines,
        flow_scale_and_unit_fn=_scale_and_unit,
        has_plotly=True,
    )

    assert result == {
        "status": "ok",
        "edge_columns": ["edge_a", "edge_b"],
        "selected_edges": ["edge_b"],
        "unit": "Нл/мин",
        "scale": 60.0,
    }
    assert fake_st.subheaders == ["Потоки по веткам"]
    assert fake_st.infos == []
    assert fake_st.captions == ["Клик по графику выбирает ветку и подсвечивает её на SVG схеме (вкладка ‘Анимация’)."]
    assert len(plot_calls) == 2
    flow_call = plot_calls[0]
    assert flow_call["args"][0] is df_mdot
    assert flow_call["args"][1] == "время_с"
    assert flow_call["args"][2] == ["edge_b"]
    assert flow_call["kwargs"]["title"] == "Расход по веткам (Нл/мин)"
    assert flow_call["kwargs"]["yaxis_title"] == "Нл/мин"
    assert np.allclose(flow_call["kwargs"]["transform_y"](np.array([1.0, 2.0])), np.array([60.0, 120.0]))
    assert flow_call["kwargs"]["plot_key"] == "plot_flow_edges"
    assert flow_call["kwargs"]["enable_select"] is True
    assert flow_call["kwargs"]["playhead_x"] == 1.25
    assert flow_call["kwargs"]["events"] == [{"t": 0.5}]
    assert flow_call["kwargs"]["events_max"] == 120
    assert flow_call["kwargs"]["events_show_labels"] is True
    open_call = plot_calls[1]
    assert open_call["args"][0] is df_open
    assert open_call["args"][2] == ["edge_b"]
    assert open_call["kwargs"]["title"] == "Состояния элементов (open=1)"
    assert np.allclose(open_call["kwargs"]["transform_y"](np.array([0.0, 1.0])), np.array([0.0, 1.0]))


def test_render_flow_edge_graphs_section_without_data() -> None:
    fake_st = _FakeStreamlit()

    result = ui_flow_graph_helpers.render_flow_edge_graphs_section(
        fake_st,
        df_mdot=None,
        df_open=None,
        playhead_x=0.0,
        events_for_graphs=None,
        events_graph_max=0,
        events_graph_labels=False,
        p_atm=0.0,
        model_module=None,
        plot_lines_fn=lambda *args, **kwargs: None,
        flow_scale_and_unit_fn=lambda **kwargs: (1.0, "x"),
        has_plotly=False,
    )

    assert result == {"status": "no_data", "selected_edges": []}
    assert fake_st.subheaders == ["Потоки по веткам"]
    assert fake_st.infos == ["Потоки доступны только при record_full=True."]
    assert fake_st.captions == []


def test_entrypoints_use_shared_flow_graph_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_flow_graph_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_flow_graph_helpers import (" in heavy_text
    assert "render_flow_edge_graphs_section(" in app_text
    assert "render_flow_edge_graphs_section(" in heavy_text
    assert 'pick_edges = st.multiselect("Ветки/элементы"' not in app_text
    assert 'pick_edges = st.multiselect("Ветки/элементы"' not in heavy_text
    assert 'title=f"Расход по веткам ({unit})"' not in app_text
    assert 'title=f"Расход по веткам ({unit})"' not in heavy_text
    assert 'open_cols = [c for c in pick_edges if c in df_open.columns]' not in app_text
    assert 'open_cols = [c for c in pick_edges if c in df_open.columns]' not in heavy_text
