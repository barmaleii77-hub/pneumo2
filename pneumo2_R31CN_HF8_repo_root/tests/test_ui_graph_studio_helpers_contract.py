from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_graph_studio_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
GRAPH_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_graph_section_helpers.py"
SURFACE_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(
        self,
        *,
        selection=None,
        source_name="df_main",
        preset="(нет)",
        text_value="",
        button_pressed=False,
    ) -> None:
        self.markdowns: list[str] = []
        self.downloads: list[dict[str, object]] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.subheaders: list[str] = []
        self.captions: list[str] = []
        self.expanders: list[tuple[str, bool]] = []
        self.divider_count = 0
        self.selection = list(selection or [])
        self.source_name = source_name
        self.preset = preset
        self.text_value = text_value
        self.button_pressed = button_pressed
        self.session_state: dict[str, list[str]] = {}

    def columns(self, specs, *, gap=None):
        return [_FakeColumn() for _ in specs]

    def radio(self, label, *, options, index, format_func, key):
        assert key.startswith("gs_mode_")
        assert format_func("stack")
        return options[1]

    def number_input(self, label, *, min_value, max_value, value, step, key):
        assert key.startswith("gs_maxp_")
        assert min_value == 400
        assert max_value == 20000
        assert step == 200
        return 3400

    def selectbox(self, label, *, options, index, key):
        if key.startswith("gs_src_"):
            return self.source_name
        if key.startswith("gs_preset_"):
            return self.preset
        if key.startswith("gs_dec_"):
            return options[1]
        if key.startswith("gs_render_"):
            return options[0]
        raise AssertionError(f"unexpected key: {key}")

    def checkbox(self, label, *, value, key):
        mapping = {
            "gs_auto_units_": False,
            "gs_hover_": True,
            "gs_events_": False,
        }
        for prefix, result in mapping.items():
            if key.startswith(prefix):
                return result
        raise AssertionError(f"unexpected checkbox key: {key}")

    def markdown(self, text):
        self.markdowns.append(text)

    def download_button(self, label, *, data, file_name, mime, key):
        self.downloads.append(
            {
                "label": label,
                "data": data,
                "file_name": file_name,
                "mime": mime,
                "key": key,
            }
        )

    def info(self, text):
        self.infos.append(text)

    def warning(self, text):
        self.warnings.append(text)

    def divider(self):
        self.divider_count += 1

    def subheader(self, text):
        self.subheaders.append(text)

    def caption(self, text):
        self.captions.append(text)

    def expander(self, label, *, expanded):
        self.expanders.append((label, expanded))
        return _FakeColumn()

    def slider(self, label, *, min_value, max_value, value, step, key):
        assert key.startswith("gs_tw_")
        assert min_value == value[0]
        assert max_value == value[1]
        assert step > 0
        return value

    def multiselect(self, label, *, options, key):
        assert key.startswith("gs_cols_")
        return [item for item in self.selection if item in options]

    def text_input(self, label, *, value, key):
        assert key.startswith("gs_filter_")
        return self.text_value

    def button(self, label, *, key):
        assert key.startswith("gs_apply_")
        return self.button_pressed


def test_graph_studio_source_and_column_helpers() -> None:
    df_main = pd.DataFrame({"время_с": [0.0], "sig": [1.0]})
    df_p = pd.DataFrame({"t": [0.0], "node_a": [1.0], "all_nan": [None]})

    sources = ui_graph_studio_helpers.build_graph_studio_sources(
        df_main=df_main,
        df_p=df_p,
        df_mdot=None,
        df_open=None,
    )
    assert list(sources.keys()) == [
        "df_main",
        "df_p (давления узлов)",
        "df_mdot (потоки)",
        "df_open (состояния клапанов)",
    ]

    avail = ui_graph_studio_helpers.filter_graph_studio_sources(sources)
    assert list(avail.keys()) == ["df_main", "df_p (давления узлов)"]

    assert ui_graph_studio_helpers.resolve_graph_studio_time_column(df_main) == "время_с"
    assert ui_graph_studio_helpers.resolve_graph_studio_time_column(df_p) == "t"
    assert ui_graph_studio_helpers.list_graph_studio_signal_columns(
        df_p,
        time_column="t",
    ) == ["node_a", "all_nan"]
    assert ui_graph_studio_helpers.list_graph_studio_signal_columns(
        df_p,
        time_column="t",
        drop_all_nan=True,
    ) == ["node_a"]


def test_graph_studio_selection_and_preset_helpers() -> None:
    all_cols = [
        "положение_штока_FL",
        "скорость_штока_FL",
        "перемещение_колеса_FR",
        "дорога_FR",
        "давление_ресивер_Па",
        "крен_phi_рад",
        "тангаж_theta_рад",
        "other_signal",
    ]

    assert ui_graph_studio_helpers.filter_graph_studio_signal_columns(all_cols, "штока") == [
        "положение_штока_FL",
        "скорость_штока_FL",
    ]
    assert ui_graph_studio_helpers.filter_graph_studio_signal_columns(all_cols, "[") == []

    pressure_preset_label = "Давления (Pa → атм изб.)"
    assert ui_graph_studio_helpers.graph_studio_preset_options(pressure_preset_label) == [
        "(нет)",
        "Механика: штоки (положение/скорость)",
        "Механика: колёса (z + дорога)",
        pressure_preset_label,
        "Крен/тангаж (рад → град)",
    ]

    assert ui_graph_studio_helpers.graph_studio_selection_key("cache", "df_main") == "gs_cols_cache::df_main"
    assert ui_graph_studio_helpers.sanitize_graph_studio_selection(
        ["missing", "скорость_штока_FL"],
        all_cols,
    ) == ["скорость_штока_FL"]

    session_state: dict[str, list[str]] = {}
    selection = ui_graph_studio_helpers.ensure_graph_studio_selection(
        session_state,
        selection_key="gs_cols_cache::df_main",
        available_columns=all_cols,
        default_limit=3,
    )
    assert selection == all_cols[:3]
    session_state["gs_cols_cache::df_main"] = ["missing", "дорога_FR"]
    assert ui_graph_studio_helpers.ensure_graph_studio_selection(
        session_state,
        selection_key="gs_cols_cache::df_main",
        available_columns=all_cols,
    ) == ["дорога_FR"]

    assert ui_graph_studio_helpers.graph_studio_preset_columns(
        all_cols,
        "Механика: штоки (положение/скорость)",
    ) == ["положение_штока_FL", "скорость_штока_FL"]
    assert ui_graph_studio_helpers.graph_studio_preset_columns(
        all_cols,
        "Механика: колёса (z + дорога)",
    ) == ["перемещение_колеса_FR", "дорога_FR"]
    assert ui_graph_studio_helpers.graph_studio_preset_columns(
        all_cols,
        "Давления (Pa → атм изб.)",
    ) == ["давление_ресивер_Па"]
    assert ui_graph_studio_helpers.graph_studio_preset_columns(
        all_cols,
        "Крен/тангаж (рад → град)",
    ) == ["крен_phi_рад", "тангаж_theta_рад"]
    assert ui_graph_studio_helpers.graph_studio_preset_columns(
        all_cols,
        "(нет)",
        current_selection=["other_signal"],
    ) == ["other_signal"]


def test_render_graph_studio_plot_controls() -> None:
    controls = ui_graph_studio_helpers.render_graph_studio_plot_controls(
        _FakeStreamlit(),
        cache_key="demo",
        auto_units_label="Auto-units",
    )

    assert controls == {
        "mode": "overlay",
        "max_points": 3400,
        "decimation": "stride",
        "render": "svg",
        "auto_units": False,
        "hover_unified": True,
        "show_events": False,
    }


def test_graph_studio_export_helpers() -> None:
    df_src = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "sig_a": [10.0, 11.0],
            "sig_b": [20.0, 21.0],
        }
    )
    df_export = ui_graph_studio_helpers.build_graph_studio_export_frame(
        df_src,
        time_column="время_с",
        selected_columns=["sig_b", "missing"],
    )
    assert list(df_export.columns) == ["время_с", "sig_b"]

    fake_st = _FakeStreamlit()
    excel_payloads: list[dict[str, pd.DataFrame]] = []

    def _excel_bytes(payloads):
        excel_payloads.append(payloads)
        return b"xlsx"

    ui_graph_studio_helpers.render_graph_studio_export_controls(
        fake_st,
        df_src=df_src,
        time_column="время_с",
        selected_columns=["sig_b", "missing"],
        cache_key="demo",
        excel_bytes_fn=_excel_bytes,
    )

    assert fake_st.markdowns == ["**Экспорт выбранных сигналов**"]
    assert fake_st.infos == []
    assert [item["file_name"] for item in fake_st.downloads] == [
        "graph_studio_signals.csv",
        "graph_studio_signals.xlsx",
    ]
    assert [item["key"] for item in fake_st.downloads] == ["gs_csv_demo", "gs_xlsx_demo"]
    assert fake_st.downloads[0]["data"].decode("utf-8").splitlines() == [
        "время_с,sig_b",
        "0.0,20.0",
        "1.0,21.0",
    ]
    assert fake_st.downloads[1]["data"] == b"xlsx"
    assert list(excel_payloads[0]["signals"].columns) == ["время_с", "sig_b"]


def test_graph_studio_quick_stats_helpers() -> None:
    df_src = pd.DataFrame(
        {
            "время_с": [0.0, 1.0, 2.0],
            "sig_a": [10.0, 20.0, 30.0],
            "sig_b": [1.0, 2.0, 3.0],
        }
    )
    df_stats = ui_graph_studio_helpers.build_graph_studio_stats_frame(
        df_src,
        time_column="время_с",
        selected_columns=["sig_a", "missing", "sig_b"],
        time_window=(0.5, 2.0),
    )
    assert df_stats.to_dict("records") == [
        {"сигнал": "sig_a", "min": 20.0, "max": 30.0, "mean": 25.0},
        {"сигнал": "sig_b", "min": 2.0, "max": 3.0, "mean": 2.5},
    ]

    fake_st = _FakeStreamlit()
    safe_calls: list[tuple[pd.DataFrame, int]] = []

    def _safe_dataframe(df, *, height):
        safe_calls.append((df.copy(), height))

    ui_graph_studio_helpers.render_graph_studio_quick_stats(
        fake_st,
        df_src=df_src,
        time_column="время_с",
        selected_columns=["sig_a", "sig_b"],
        cache_key="demo",
        safe_dataframe_fn=_safe_dataframe,
    )

    assert len(safe_calls) == 1
    assert safe_calls[0][0].to_dict("records") == [
        {"сигнал": "sig_a", "min": 10.0, "max": 30.0, "mean": 20.0},
        {"сигнал": "sig_b", "min": 1.0, "max": 3.0, "mean": 2.0},
    ]
    assert safe_calls[0][1] == 142


def test_render_graph_studio_selected_signals_panel() -> None:
    df_src = pd.DataFrame(
        {
            "время_с": [0.0, 1.0, 2.0],
            "sig_a": [10.0, 20.0, 30.0],
            "sig_b": [1.0, 2.0, 3.0],
        }
    )
    fake_st = _FakeStreamlit(selection=["sig_a", "sig_b"])
    plot_calls: list[dict[str, object]] = []
    safe_calls: list[tuple[pd.DataFrame, int]] = []

    def _plot_timeseries(**kwargs):
        plot_calls.append(kwargs)

    def _excel_bytes(payloads):
        return b"xlsx"

    def _safe_dataframe(df, *, height):
        safe_calls.append((df.copy(), height))

    selected = ui_graph_studio_helpers.render_graph_studio_selected_signals_panel(
        fake_st,
        df_src=df_src,
        source_name="df_main",
        time_column="время_с",
        available_columns=["sig_a", "sig_b"],
        selection_key="gs_cols_demo::df_main",
        cache_key="demo",
        playhead_x=1.5,
        events_for_graphs=[{"t": 1.0}],
        auto_units_label="Auto-units",
        plot_timeseries_fn=_plot_timeseries,
        excel_bytes_fn=_excel_bytes,
        safe_dataframe_fn=_safe_dataframe,
    )

    assert selected == ["sig_a", "sig_b"]
    assert fake_st.infos == []
    assert len(plot_calls) == 1
    assert plot_calls[0]["title"] == "Graph Studio: df_main"
    assert plot_calls[0]["y_cols"] == ["sig_a", "sig_b"]
    assert plot_calls[0]["mode"] == "overlay"
    assert plot_calls[0]["max_points"] == 3400
    assert plot_calls[0]["decimation"] == "stride"
    assert plot_calls[0]["auto_units"] is False
    assert plot_calls[0]["render"] == "svg"
    assert plot_calls[0]["hover_unified"] is True
    assert plot_calls[0]["events"] is None
    assert plot_calls[0]["plot_key"] == "plot_graph_studio_demo"
    assert [item["file_name"] for item in fake_st.downloads] == [
        "graph_studio_signals.csv",
        "graph_studio_signals.xlsx",
    ]
    assert len(safe_calls) == 1
    assert safe_calls[0][0].to_dict("records") == [
        {"сигнал": "sig_a", "min": 10.0, "max": 30.0, "mean": 20.0},
        {"сигнал": "sig_b", "min": 1.0, "max": 3.0, "mean": 2.0},
    ]


def test_render_graph_studio_panel() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0, 2.0],
            "sig_a": [10.0, 20.0, 30.0],
            "sig_b": [1.0, 2.0, 3.0],
        }
    )
    fake_st = _FakeStreamlit(
        selection=["sig_a", "sig_b"],
        source_name="df_main",
    )
    plot_calls: list[dict[str, object]] = []
    safe_calls: list[tuple[pd.DataFrame, int]] = []

    def _plot_timeseries(**kwargs):
        plot_calls.append(kwargs)

    def _excel_bytes(payloads):
        return b"xlsx"

    def _safe_dataframe(df, *, height):
        safe_calls.append((df.copy(), height))

    result = ui_graph_studio_helpers.render_graph_studio_panel(
        fake_st,
        df_main=df_main,
        df_p=None,
        df_mdot=None,
        df_open=None,
        cache_key="demo",
        pressure_preset_label="Давления (Pa → атм изб.)",
        auto_units_label="Auto-units",
        drop_all_nan=False,
        session_state=fake_st.session_state,
        playhead_x=1.5,
        events_for_graphs=[{"t": 1.0}],
        plot_timeseries_fn=_plot_timeseries,
        excel_bytes_fn=_excel_bytes,
        safe_dataframe_fn=_safe_dataframe,
    )

    assert result["status"] == "ok"
    assert result["source_name"] == "df_main"
    assert result["time_column"] == "время_с"
    assert result["selection_key"] == "gs_cols_demo::df_main"
    assert result["selected_columns"] == ["sig_a", "sig_b"]
    assert result["available_sources"] == ["df_main"]
    assert fake_st.infos == []
    assert fake_st.warnings == []
    assert fake_st.session_state["gs_cols_demo::df_main"] == ["sig_a", "sig_b"]
    assert len(plot_calls) == 1
    assert len(fake_st.downloads) == 2
    assert len(safe_calls) == 1


def test_render_graph_studio_section() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "sig_a": [10.0, 20.0],
        }
    )
    fake_st = _FakeStreamlit(
        selection=["sig_a"],
        source_name="df_main",
    )
    plot_calls: list[dict[str, object]] = []

    def _plot_timeseries(**kwargs):
        plot_calls.append(kwargs)

    result = ui_graph_studio_helpers.render_graph_studio_section(
        fake_st,
        df_main=df_main,
        df_p=None,
        df_mdot=None,
        df_open=None,
        cache_key="demo",
        pressure_preset_label="Давления (Pa → атм изб.)",
        auto_units_label="Auto-units",
        drop_all_nan=False,
        session_state=fake_st.session_state,
        playhead_x=0.5,
        events_for_graphs=None,
        plot_timeseries_fn=_plot_timeseries,
        excel_bytes_fn=lambda payloads: b"xlsx",
        safe_dataframe_fn=lambda df, *, height: None,
    )

    assert result["status"] == "ok"
    assert fake_st.divider_count == 1
    assert fake_st.subheaders == ["Конструктор графиков (Graph Studio)"]
    assert fake_st.captions == [
        "Выбирайте любые сигналы из df_main/df_p/df_mdot/df_open, стройте осциллограф (stack) или overlay, кликом прыгайте по времени."
    ]
    assert fake_st.expanders == [("Graph Studio: сигналы → график → экспорт", True)]
    assert len(plot_calls) == 1


def test_entrypoints_use_shared_graph_studio_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.ui_graph_studio_helpers import render_graph_studio_section" in surface_text
    assert "render_graph_studio_section(" not in app_text
    assert "render_graph_studio_section(" not in heavy_text
    assert '"render_graph_studio_section_fn": render_graph_studio_section' in surface_text
    assert 'sources = {' not in app_text
    assert 'sources = {' not in heavy_text
    assert 'avail_sources = {k: v for k, v in sources.items() if v is not None and hasattr(v, "columns") and len(v)}' not in app_text
    assert 'avail_sources = {k: v for k, v in sources.items() if v is not None and hasattr(v, "columns") and len(v)}' not in heavy_text
    assert 'tcol_gs = "время_с" if (df_src is not None and "время_с" in df_src.columns) else None' not in app_text
    assert 'tcol_gs = "время_с" if (df_src is not None and "время_с" in df_src.columns) else None' not in heavy_text
    assert "rx = re.compile(q, flags=re.IGNORECASE)" not in app_text
    assert "rx = re.compile(q, flags=re.IGNORECASE)" not in heavy_text
    assert 'gs_key = f"gs_cols_{cache_key}::{src_name}"' not in app_text
    assert 'gs_key = f"gs_cols_{cache_key}::{src_name}"' not in heavy_text
    assert "def _sanitize_cols(sel: list) -> list:" not in app_text
    assert "def _sanitize_cols(sel: list) -> list:" not in heavy_text
    assert "gs_mode = st.radio(" not in app_text
    assert "gs_mode = st.radio(" not in heavy_text
    assert "gs_maxp = st.number_input(" not in app_text
    assert "gs_maxp = st.number_input(" not in heavy_text
    assert "gs_auto_units = st.checkbox(" not in app_text
    assert "gs_auto_units = st.checkbox(" not in heavy_text
    assert "plot_studio_timeseries(" not in app_text
    assert "plot_studio_timeseries(" not in heavy_text
    assert "build_graph_studio_sources(" not in app_text
    assert "build_graph_studio_sources(" not in heavy_text
    assert "filter_graph_studio_sources(" not in app_text
    assert "filter_graph_studio_sources(" not in heavy_text
    assert "resolve_graph_studio_time_column(df_src)" not in app_text
    assert "resolve_graph_studio_time_column(df_src)" not in heavy_text
    assert "list_graph_studio_signal_columns(" not in app_text
    assert "list_graph_studio_signal_columns(" not in heavy_text
    assert "filter_graph_studio_signal_columns(all_cols, q)" not in app_text
    assert "filter_graph_studio_signal_columns(all_cols, q)" not in heavy_text
    assert 'graph_studio_preset_options("Давления (Pa → атм изб.)")' not in app_text
    assert 'graph_studio_preset_options("Давления (Pa → бар изб.)")' not in heavy_text
    assert "graph_studio_selection_key(cache_key, src_name)" not in app_text
    assert "graph_studio_selection_key(cache_key, src_name)" not in heavy_text
    assert "ensure_graph_studio_selection(" not in app_text
    assert "ensure_graph_studio_selection(" not in heavy_text
    assert "graph_studio_preset_columns(" not in app_text
    assert "graph_studio_preset_columns(" not in heavy_text
    assert "sanitize_graph_studio_selection(" not in app_text
    assert "sanitize_graph_studio_selection(" not in heavy_text
    assert "df_exp = df_src[[" not in app_text
    assert "df_exp = df_src[[" not in heavy_text
    assert 'file_name="graph_studio_signals.csv"' not in app_text
    assert 'file_name="graph_studio_signals.csv"' not in heavy_text
    assert "tarr = np.asarray(df_src[tcol_gs].to_numpy(), dtype=float)" not in app_text
    assert "tarr = np.asarray(df_src[tcol_gs].to_numpy(), dtype=float)" not in heavy_text
    assert 'key=f"gs_tw_{cache_key}"' not in app_text
    assert 'key=f"gs_tw_{cache_key}"' not in heavy_text
    assert "Выберите хотя бы один сигнал." not in app_text
    assert "Выберите хотя бы один сигнал." not in heavy_text
    assert 'title=f"Graph Studio: {src_name}"' not in app_text
    assert 'title=f"Graph Studio: {src_name}"' not in heavy_text
    assert 'st.subheader("Конструктор графиков (Graph Studio)")' not in app_text
    assert 'st.subheader("Конструктор графиков (Graph Studio)")' not in heavy_text
    assert 'with st.expander("Graph Studio: сигналы → график → экспорт", expanded=True):' not in app_text
    assert 'with st.expander("Graph Studio: сигналы → график → экспорт", expanded=True):' not in heavy_text
