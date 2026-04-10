from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_node_pressure_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
GRAPH_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_graph_section_helpers.py"
SURFACE_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_resolve_default_node_pressure_selection_and_render_expander() -> None:
    node_columns = ["Ресивер2", "УзелX", "УзелY"]
    assert ui_node_pressure_helpers.resolve_default_node_pressure_selection(
        node_columns,
        {},
    ) == ["Ресивер2"]
    assert ui_node_pressure_helpers.resolve_default_node_pressure_selection(
        node_columns,
        {"anim_nodes_svg": ["УзелX"]},
    ) == ["УзелX"]

    calls: list[tuple[str, object]] = []

    class _Ctx:
        def __enter__(self):
            calls.append(("enter", None))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("exit", None))
            return False

    def plot_lines_fn(df, tcol, cols, **kwargs):
        calls.append(("plot", {"df": df, "tcol": tcol, "cols": list(cols), **kwargs}))

    df_p = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "Ресивер1": [101325.0, 151325.0],
            "УзелX": [100000.0, 120000.0],
        }
    )
    ui_node_pressure_helpers.render_node_pressure_expander(
        df_p=df_p,
        plot_lines_fn=plot_lines_fn,
        session_state={"anim_nodes_svg": ["УзелX"]},
        playhead_x=0.5,
        events=[{"t": 0.5, "label": "A"}],
        events_max=9,
        events_show_labels=True,
        title="Давление узлов (df_p, бар изб.)",
        yaxis_title="бар (изб.)",
        transform_y_fn=lambda values: values / 100000.0,
        has_plotly=True,
        expander_fn=lambda *args, **kwargs: _Ctx(),
        multiselect_fn=lambda *args, **kwargs: ["УзелX"],
        info_fn=lambda text: calls.append(("info", text)),
        caption_fn=lambda text: calls.append(("caption", text)),
    )

    plot_call = [payload for kind, payload in calls if kind == "plot"][0]
    assert plot_call["cols"] == ["УзелX"]
    assert plot_call["title"] == "Давление узлов (df_p, бар изб.)"
    assert plot_call["plot_key"] == "plot_node_pressure"
    assert plot_call["enable_select"] is True
    assert any(kind == "caption" and payload == ui_node_pressure_helpers.PLOTLY_NODE_HINT for kind, payload in calls)


def test_entrypoints_use_shared_node_pressure_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.ui_node_pressure_helpers import render_node_pressure_expander" in surface_text
    assert "render_node_pressure_expander(" not in app_text
    assert "render_node_pressure_expander(" not in heavy_text
    assert '"render_node_pressure_expander_fn": render_node_pressure_expander' in surface_text
    assert 'with st.expander("Давление узлов (df_p)", expanded=False):' not in app_text
    assert 'with st.expander("Давление узлов (df_p)", expanded=False):' not in heavy_text
    assert 'key="node_pressure_plot"' not in app_text
    assert 'key="node_pressure_plot"' not in heavy_text
