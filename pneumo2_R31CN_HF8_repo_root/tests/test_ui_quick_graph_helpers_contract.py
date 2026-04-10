from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_quick_graph_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
GRAPH_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_graph_section_helpers.py"
SURFACE_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_present_main_pressure_columns_and_render_main_overview_graphs() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "крен_phi_рад": [0.0, 0.2],
            "тангаж_theta_рад": [0.1, 0.3],
            "давление_ресивер1_Па": [101325.0, 151325.0],
            "давление_аккумулятор_Па": [101325.0, 181325.0],
        }
    )

    assert ui_quick_graph_helpers.present_main_pressure_columns(df_main) == [
        "давление_ресивер1_Па",
        "давление_аккумулятор_Па",
    ]

    calls: list[dict[str, object]] = []

    def plot_lines_fn(df, tcol, y_cols, **kwargs):
        calls.append(
            {
                "df": df,
                "tcol": tcol,
                "y_cols": list(y_cols),
                **kwargs,
            }
        )

    ui_quick_graph_helpers.render_main_overview_graphs(
        plot_lines_fn=plot_lines_fn,
        df_main=df_main,
        tcol="время_с",
        playhead_x=0.5,
        events=[{"t": 0.5, "label": "A"}],
        events_max=12,
        events_show_labels=True,
        pressure_title="Давление (бар изб.)",
        pressure_yaxis_title="бар (изб.)",
        pressure_transform_fn=lambda values: values / 100000.0,
    )

    assert len(calls) == 2
    assert calls[0]["y_cols"] == ["крен_phi_рад", "тангаж_theta_рад"]
    assert calls[0]["title"] == "Крен/тангаж"
    assert calls[0]["yaxis_title"] == "град"
    assert calls[1]["y_cols"] == ["давление_ресивер1_Па", "давление_аккумулятор_Па"]
    assert calls[1]["title"] == "Давление (бар изб.)"
    assert calls[1]["yaxis_title"] == "бар (изб.)"
    assert calls[1]["events_max"] == 12
    assert calls[1]["events_show_labels"] is True


def test_entrypoints_use_shared_quick_graph_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.ui_quick_graph_helpers import render_main_overview_graphs" in surface_text
    assert "render_main_overview_graphs(" not in app_text
    assert "render_main_overview_graphs(" not in heavy_text
    assert '"render_main_overview_graphs_fn": render_main_overview_graphs' in surface_text
    assert 'title="Крен/тангаж"' not in app_text
    assert 'title="Крен/тангаж"' not in heavy_text
    assert "press_cols = [c for c in [" not in app_text
    assert "press_cols = [c for c in [" not in heavy_text
