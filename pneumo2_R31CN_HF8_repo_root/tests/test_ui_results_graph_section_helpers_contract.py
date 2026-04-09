from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_graph_section_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_graph_section_helpers.py"
SURFACE_SECTION_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


class _FakeContainer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.subheaders: list[str] = []

    def subheader(self, text: str) -> None:
        self.subheaders.append(text)

    def markdown(self, text: str) -> None:
        pass

    def columns(self, specs):
        return list(specs)

    def multiselect(self, *args, **kwargs):
        return []

    def caption(self, text: str) -> None:
        pass

    def expander(self, *args, **kwargs):
        return _FakeContainer()

    def info(self, text: str) -> None:
        pass

    def container(self):
        return _FakeContainer()


def test_render_results_graph_section_wires_app_like_params() -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    helpers.render_results_graph_section(
        fake_st,
        df_main="df_main",
        df_p="df_p",
        df_mdot="df_mdot",
        df_open="df_open",
        cache_key="cache-1",
        session_state={"demo": True},
        playhead_x=1.5,
        events_for_graphs=[{"t": 1.0}],
        events_graph_max=12,
        events_graph_labels=True,
        plot_lines_fn="plot_lines_fn",
        plot_timeseries_fn="plot_timeseries_fn",
        excel_bytes_fn="excel_bytes_fn",
        safe_dataframe_fn="safe_dataframe_fn",
        pressure_title="Давление (атм изб.)",
        pressure_yaxis_title="атм (изб.)",
        pressure_transform_fn="pressure_transform_fn",
        node_pressure_title="Давление узлов (df_p, атм изб.)",
        node_pressure_yaxis_title="атм (изб.)",
        node_pressure_transform_fn="node_pressure_transform_fn",
        graph_studio_pressure_preset_label="Давления (Pa → атм изб.)",
        graph_studio_auto_units_label="Auto-units (Pa→атм, рад→град)",
        graph_studio_drop_all_nan=False,
        has_plotly=True,
        render_main_overview_graphs_fn=lambda **kwargs: calls.append(("main", kwargs)),
        render_mech_overview_graphs_fn=lambda **kwargs: calls.append(("mech", kwargs)),
        render_node_pressure_expander_fn=lambda **kwargs: calls.append(("node", kwargs)),
        render_graph_studio_section_fn=lambda st, **kwargs: calls.append(("studio", kwargs)),
    )

    assert fake_st.subheaders == ["Графики по времени"]
    assert calls[0][0] == "main"
    assert calls[0][1]["pressure_title"] == "Давление (атм изб.)"
    assert calls[1][0] == "mech"
    assert calls[1][1]["session_state"] == {"demo": True}
    assert calls[2][0] == "node"
    assert calls[2][1]["title"] == "Давление узлов (df_p, атм изб.)"
    assert calls[3] == (
        "studio",
        {
            "df_main": "df_main",
            "df_p": "df_p",
            "df_mdot": "df_mdot",
            "df_open": "df_open",
            "cache_key": "cache-1",
            "pressure_preset_label": "Давления (Pa → атм изб.)",
            "auto_units_label": "Auto-units (Pa→атм, рад→град)",
            "drop_all_nan": False,
            "session_state": {"demo": True},
            "playhead_x": 1.5,
            "events_for_graphs": [{"t": 1.0}],
            "plot_timeseries_fn": "plot_timeseries_fn",
            "excel_bytes_fn": "excel_bytes_fn",
            "safe_dataframe_fn": "safe_dataframe_fn",
        },
    )


def test_render_results_graph_section_wires_heavy_like_params() -> None:
    fake_st = _FakeStreamlit()
    studio_calls: list[dict[str, object]] = []

    helpers.render_results_graph_section(
        fake_st,
        df_main="df_main",
        df_p="df_p",
        df_mdot="df_mdot",
        df_open="df_open",
        cache_key="cache-2",
        session_state={"heavy": True},
        playhead_x=2.5,
        events_for_graphs=[],
        events_graph_max=20,
        events_graph_labels=False,
        plot_lines_fn="plot_lines_fn",
        plot_timeseries_fn="plot_timeseries_fn",
        excel_bytes_fn="excel_bytes_fn",
        safe_dataframe_fn="safe_dataframe_fn",
        pressure_title="Давление (бар изб.)",
        pressure_yaxis_title="бар (изб.)",
        pressure_transform_fn="pressure_transform_fn",
        node_pressure_title="Давление узлов (df_p, бар изб.)",
        node_pressure_yaxis_title="бар (изб.)",
        node_pressure_transform_fn="node_pressure_transform_fn",
        graph_studio_pressure_preset_label="Давления (Pa → бар изб.)",
        graph_studio_auto_units_label="Auto-units (Pa→бар, рад→град)",
        graph_studio_drop_all_nan=True,
        has_plotly=False,
        render_main_overview_graphs_fn=lambda **kwargs: None,
        render_mech_overview_graphs_fn=lambda **kwargs: None,
        render_node_pressure_expander_fn=lambda **kwargs: None,
        render_graph_studio_section_fn=lambda st, **kwargs: studio_calls.append(kwargs),
    )

    assert studio_calls == [
        {
            "df_main": "df_main",
            "df_p": "df_p",
            "df_mdot": "df_mdot",
            "df_open": "df_open",
            "cache_key": "cache-2",
            "pressure_preset_label": "Давления (Pa → бар изб.)",
            "auto_units_label": "Auto-units (Pa→бар, рад→град)",
            "drop_all_nan": True,
            "session_state": {"heavy": True},
            "playhead_x": 2.5,
            "events_for_graphs": [],
            "plot_timeseries_fn": "plot_timeseries_fn",
            "excel_bytes_fn": "excel_bytes_fn",
            "safe_dataframe_fn": "safe_dataframe_fn",
        }
    ]


def test_entrypoints_use_shared_results_graph_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    surface_section_text = SURFACE_SECTION_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_graph_section_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_graph_section_helpers import (" not in heavy_text
    assert "render_results_graph_section(" not in app_text
    assert "render_results_graph_section(" not in heavy_text
    assert 'st.subheader("Графики по времени")' not in app_text
    assert 'st.subheader("Графики по времени")' not in heavy_text
    assert "render_main_overview_graphs(" not in app_text
    assert "render_main_overview_graphs(" not in heavy_text
    assert "render_mech_overview_graphs(" not in app_text
    assert "render_mech_overview_graphs(" not in heavy_text
    assert "render_node_pressure_expander(" not in app_text
    assert "render_node_pressure_expander(" not in heavy_text
    assert "render_graph_studio_section(" not in app_text
    assert "render_graph_studio_section(" not in heavy_text
    assert '"render_results_graph_section_fn": render_results_graph_section' in surface_section_text
    assert "def render_results_graph_section(" in helper_text
    assert "render_main_overview_graphs_fn(" in helper_text
    assert "render_mech_overview_graphs_fn(" in helper_text
    assert "render_node_pressure_expander_fn(" in helper_text
    assert "render_graph_studio_section_fn(" in helper_text
