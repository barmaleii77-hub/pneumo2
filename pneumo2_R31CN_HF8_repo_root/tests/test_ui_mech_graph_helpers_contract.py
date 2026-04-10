from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_mech_graph_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
GRAPH_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_graph_section_helpers.py"
SURFACE_SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_collect_mech_metric_columns_and_render_mech_overview_graphs() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "нормальная_сила_шины_ЛП_Н": [1.0, 2.0],
            "нормальная_сила_шины_ПП_Н": [3.0, 4.0],
            "положение_штока_ЛП_м": [0.1, 0.2],
            "скорость_штока_ПП_м_с": [0.3, 0.4],
        }
    )

    assert ui_mech_graph_helpers.collect_mech_metric_columns(
        df_main,
        corners=["ЛП", "ПП"],
        name_template="нормальная_сила_шины_{corner}_Н",
        fallback_prefix="нормальная_сила_шины_",
    ) == ["нормальная_сила_шины_ЛП_Н", "нормальная_сила_шины_ПП_Н"]

    calls: list[dict[str, object]] = []
    markdowns: list[str] = []
    captions: list[str] = []

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def plot_lines_fn(df, tcol, cols, **kwargs):
        calls.append({"df": df, "tcol": tcol, "cols": list(cols), **kwargs})

    picked = ui_mech_graph_helpers.render_mech_overview_graphs(
        plot_lines_fn=plot_lines_fn,
        df_main=df_main,
        tcol="время_с",
        playhead_x=0.5,
        events=[{"t": 0.5, "label": "A"}],
        events_max=8,
        events_show_labels=True,
        session_state={"mech_plot_corners": ["ЛП", "ПП"]},
        markdown_fn=markdowns.append,
        columns_fn=lambda spec, gap=None: [_Ctx(), _Ctx()],
        multiselect_fn=lambda *args, **kwargs: ["ЛП", "ПП"],
        caption_fn=captions.append,
    )

    assert picked == ["ЛП", "ПП"]
    assert markdowns == ["**Углы (механика) — синхронизация с анимацией**"]
    assert len(captions) == 1
    assert [call["title"] for call in calls] == [
        "Нормальные силы шин",
        "Положение штоков",
        "Скорость штоков",
    ]
    assert calls[0]["cols"] == ["нормальная_сила_шины_ЛП_Н", "нормальная_сила_шины_ПП_Н"]
    assert calls[1]["cols"] == ["положение_штока_ЛП_м"]
    assert calls[2]["cols"] == ["скорость_штока_ПП_м_с"]


def test_entrypoints_use_shared_mech_graph_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.ui_mech_graph_helpers import render_mech_overview_graphs" in surface_text
    assert "render_mech_overview_graphs(" not in app_text
    assert "render_mech_overview_graphs(" not in heavy_text
    assert '"render_mech_overview_graphs_fn": render_mech_overview_graphs' in surface_text
    assert 'key="mech_plot_corners"' not in app_text
    assert 'key="mech_plot_corners"' not in heavy_text
    assert 'title="Нормальные силы шин"' not in app_text
    assert 'title="Нормальные силы шин"' not in heavy_text
    assert 'title="Положение штоков"' not in app_text
    assert 'title="Положение штоков"' not in heavy_text
    assert 'title="Скорость штоков"' not in app_text
    assert 'title="Скорость штоков"' not in heavy_text
