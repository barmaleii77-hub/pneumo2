from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_playhead_value_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SECTION_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_playhead_section_helpers.py"


def test_nearest_time_index_and_selection_helpers() -> None:
    df_time = pd.DataFrame({"время_с": [0.0, 1.0, 2.5, 4.0]})
    df_p = pd.DataFrame({"время_с": [0.0], "Ресивер2": [1.0], "Аккумулятор": [2.0]})
    df_mdot = pd.DataFrame({"время_с": [0.0], "edge_a": [1.0], "edge_b": [2.0], "edge_c": [3.0], "edge_d": [4.0], "edge_e": [5.0]})

    assert ui_playhead_value_helpers.nearest_time_index(df_time, 2.4) == 2
    assert ui_playhead_value_helpers.nearest_time_index(df_time, None) == 0
    assert ui_playhead_value_helpers.resolve_selected_corners({}) == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    assert ui_playhead_value_helpers.resolve_selected_corners({"mech_plot_corners": ["ЛП", "ПЗ"]}) == ["ЛП", "ПЗ"]
    assert ui_playhead_value_helpers.resolve_selected_nodes(df_p, {}) == ["Ресивер2", "Аккумулятор"]
    assert ui_playhead_value_helpers.resolve_selected_nodes(df_p, {"node_pressure_plot": ["NodeA"]}) == ["NodeA"]
    assert ui_playhead_value_helpers.resolve_selected_edges(df_mdot, {}) == ["edge_a", "edge_b", "edge_c", "edge_d"]
    assert ui_playhead_value_helpers.resolve_selected_edges(df_mdot, {"anim_edges_svg": ["x", "y"]}) == ["x", "y"]


def test_build_playhead_value_rows_respects_units_and_scaling() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "крен_phi_рад": [0.0, 0.5],
            "тангаж_theta_рад": [0.0, 0.25],
            "давление_ресивер1_Па": [101325.0, 201325.0],
            "положение_штока_ЛП_м": [0.0, 0.12],
        }
    )
    df_p = pd.DataFrame({"время_с": [0.0, 1.0], "Ресивер1": [101325.0, 151325.0]})
    df_mdot = pd.DataFrame({"время_с": [0.0, 1.0], "edge_a": [0.0, 1.5]})

    rows = ui_playhead_value_helpers.build_playhead_value_rows(
        df_main=df_main,
        df_p=df_p,
        df_mdot=df_mdot,
        playhead_x=0.9,
        session_state={},
        pressure_from_pa_fn=lambda value: float(value) / 100000.0,
        pressure_unit="bar(g)",
        stroke_scale=1000.0,
        stroke_unit="мм",
        flow_scale_and_unit_fn=lambda **_: (60.0, "Нл/мин"),
        p_atm=101325.0,
        model_module=object(),
    )

    by_label = {row["показатель"]: row for row in rows}
    assert by_label["крен φ"]["ед"] == "град"
    assert round(float(by_label["P ресивер1"]["значение"]), 4) == 2.0133
    assert by_label["P узел Ресивер1"]["ед"] == "bar(g)"
    assert by_label["шток ЛП"]["значение"] == 120.0
    assert by_label["шток ЛП"]["ед"] == "мм"
    assert by_label["Q edge_a"]["значение"] == 90.0
    assert by_label["Q edge_a"]["ед"] == "Нл/мин"


def test_render_playhead_value_content_uses_shared_rows_and_renderers() -> None:
    df_main = pd.DataFrame({"время_с": [0.0, 1.0], "крен_phi_рад": [0.0, 0.5]})
    captions: list[str] = []
    infos: list[str] = []
    dataframes: list[tuple[pd.DataFrame, int]] = []

    def safe_dataframe_fn(df: pd.DataFrame, *, height: int) -> None:
        dataframes.append((df.copy(), height))

    ui_playhead_value_helpers.render_playhead_value_content(
        df_main=df_main,
        df_p=None,
        df_mdot=None,
        playhead_x=1.0,
        session_state={},
        pressure_from_pa_fn=float,
        pressure_unit="unit",
        stroke_scale=1.0,
        stroke_unit="м",
        flow_scale_and_unit_fn=lambda **_: (1.0, "кг/с"),
        p_atm=101325.0,
        model_module=object(),
        safe_dataframe_fn=safe_dataframe_fn,
        caption_fn=captions.append,
        info_fn=infos.append,
    )

    assert captions == ["t = 1.000 s"]
    assert infos == []
    assert len(dataframes) == 1
    assert list(dataframes[0][0]["показатель"]) == ["крен φ"]
    assert dataframes[0][1] > 0


def test_render_playhead_value_panel_guards_and_wraps_expander() -> None:
    events: list[tuple[str, object]] = []

    class DummyExpander:
        def __enter__(self):
            events.append(("enter", None))
            return self

        def __exit__(self, exc_type, exc, tb):
            events.append(("exit", None))
            return False

    def expander_fn(title: str, *, expanded: bool = False):
        events.append(("expander", (title, expanded)))
        return DummyExpander()

    ui_playhead_value_helpers.render_playhead_value_panel(
        enabled=True,
        df_main=pd.DataFrame({"время_с": [0.0], "крен_phi_рад": [0.25]}),
        df_p=None,
        df_mdot=None,
        playhead_x=0.0,
        session_state={},
        pressure_from_pa_fn=float,
        pressure_unit="unit",
        stroke_scale=1.0,
        stroke_unit="м",
        flow_scale_and_unit_fn=lambda **_: (1.0, "кг/с"),
        p_atm=101325.0,
        model_module=object(),
        safe_dataframe_fn=lambda *args, **kwargs: events.append(("df", kwargs["height"])),
        caption_fn=lambda text: events.append(("caption", text)),
        info_fn=lambda text: events.append(("info", text)),
        expander_fn=expander_fn,
    )

    assert events[0] == ("expander", ("Текущие значения (playhead)", False))
    assert ("enter", None) in events
    assert ("exit", None) in events
    assert any(kind == "caption" for kind, _ in events)
    assert any(kind == "df" for kind, _ in events)

    events.clear()
    ui_playhead_value_helpers.render_playhead_value_panel(
        enabled=False,
        df_main=None,
        df_p=None,
        df_mdot=None,
        playhead_x=0.0,
        session_state={},
        pressure_from_pa_fn=float,
        pressure_unit="unit",
        stroke_scale=1.0,
        stroke_unit="м",
        flow_scale_and_unit_fn=lambda **_: (1.0, "кг/с"),
        p_atm=101325.0,
        model_module=object(),
        safe_dataframe_fn=lambda *args, **kwargs: events.append(("df", kwargs["height"])),
        caption_fn=lambda text: events.append(("caption", text)),
        info_fn=lambda text: events.append(("info", text)),
        expander_fn=expander_fn,
    )
    assert events == []


def test_render_playhead_display_settings_uses_two_columns_and_checkbox_keys() -> None:
    events: list[tuple[str, object]] = []

    class DummyColumn:
        def __init__(self, index: int) -> None:
            self.index = index

        def __enter__(self):
            events.append(("enter", self.index))
            return self

        def __exit__(self, exc_type, exc, tb):
            events.append(("exit", self.index))
            return False

    def columns_fn(count: int):
        events.append(("columns", count))
        return [DummyColumn(0), DummyColumn(1)]

    def checkbox_fn(label: str, *, value: bool, key: str) -> bool:
        events.append(("checkbox", (label, value, key)))
        return key == "playhead_show_markers"

    show_markers, show_values = ui_playhead_value_helpers.render_playhead_display_settings(
        columns_fn=columns_fn,
        checkbox_fn=checkbox_fn,
    )

    assert (show_markers, show_values) == (True, False)
    assert events[0] == ("columns", 2)
    assert ("checkbox", ("Маркеры на графиках (playhead)", True, "playhead_show_markers")) in events
    assert ("checkbox", ("Таблица значений (playhead)", True, "playhead_show_values")) in events


def test_entrypoints_use_shared_playhead_value_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    section_text = SECTION_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_playhead_value_helpers import (" in section_text
    assert "render_playhead_display_settings(" in section_text
    assert "render_playhead_value_panel(" in section_text
    assert "expander_fn=expander_fn" in section_text
    assert "safe_dataframe_fn=safe_dataframe_fn" in section_text
    assert "caption_fn=caption_fn" in section_text
    assert "checkbox_fn=checkbox_fn" in section_text
    assert "pressure_from_pa_fn=pa_abs_to_atm_g" in app_text
    assert 'stroke_unit="м"' in app_text
    assert "pressure_from_pa_fn=pa_abs_to_bar_g" in heavy_text
    assert 'stroke_unit="мм"' in heavy_text
    assert "from pneumo_solver_ui.ui_playhead_value_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_playhead_value_helpers import (" not in heavy_text
    assert "nearest_time_index(df_main, playhead_x)" not in app_text
    assert "nearest_time_index(df_main, playhead_x)" not in heavy_text
    assert "resolve_selected_corners(st.session_state)" not in app_text
    assert "resolve_selected_corners(st.session_state)" not in heavy_text
    assert "resolve_selected_nodes(df_p, st.session_state)" not in app_text
    assert "resolve_selected_nodes(df_p, st.session_state)" not in heavy_text
    assert "resolve_selected_edges(df_mdot, st.session_state)" not in app_text
    assert "resolve_selected_edges(df_mdot, st.session_state)" not in heavy_text
    assert "dfv = pd.DataFrame(rows)" not in app_text
    assert "dfv = pd.DataFrame(rows)" not in heavy_text
    assert 'with st.expander("Текущие значения (playhead)", expanded=False):' not in app_text
    assert 'with st.expander("Текущие значения (playhead)", expanded=False):' not in heavy_text
    assert "cols_ph = st.columns(2)" not in app_text
    assert "cols_ph = st.columns(2)" not in heavy_text
    assert 'idx0 = int(np.argmin(np.abs(arr - float(playhead_x))))' not in app_text
    assert 'idx0 = int(np.argmin(np.abs(arr - float(playhead_x))))' not in heavy_text
