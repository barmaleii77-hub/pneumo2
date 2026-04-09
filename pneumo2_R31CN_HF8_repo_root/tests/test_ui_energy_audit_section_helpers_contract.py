from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_energy_audit_section_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_energy_audit_section_helpers.py"
SECONDARY_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_secondary_views_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.subheaders: list[str] = []
        self.markdowns: list[str] = []

    def subheader(self, text: str) -> None:
        self.subheaders.append(text)

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)


class _FakePlotlyExpress:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def bar(self, frame, *, x: str, y: str, title: str):
        self.calls.append(
            {
                "rows": list(frame[y]),
                "x": x,
                "y": y,
                "title": title,
            }
        )
        return {"kind": "bar", "title": title}


class _FailingPlotlyExpress:
    def bar(self, frame, *, x: str, y: str, title: str):
        raise RuntimeError("plot failed")


def test_render_energy_audit_results_section_renders_sorted_tables_and_plot() -> None:
    fake_st = _FakeStreamlit()
    fake_px = _FakePlotlyExpress()
    dataframe_calls: list[tuple[list[float], int]] = []
    plot_calls: list[object] = []

    df_groups = pd.DataFrame(
        {
            "группа": ["b", "a"],
            "энергия_Дж": [2.0, 5.0],
        }
    )
    df_edges = pd.DataFrame(
        {
            "edge": ["e1", "e2", "e3"],
            "энергия_Дж": [3.0, 8.0, 1.0],
        }
    )

    helpers.render_energy_audit_results_section(
        fake_st,
        df_Egroups=df_groups,
        df_Eedges=df_edges,
        safe_dataframe_fn=lambda frame, *, height: dataframe_calls.append((list(frame["энергия_Дж"]), height)),
        has_plotly=True,
        px_module=fake_px,
        safe_plotly_chart_fn=lambda fig: plot_calls.append(fig),
        section_title="Энерго-аудит",
        top_edges_title="**TOP-20 элементов по энергии**",
    )

    assert fake_st.subheaders == ["Энерго-аудит"]
    assert fake_st.markdowns == ["**TOP-20 элементов по энергии**"]
    assert dataframe_calls == [([5.0, 2.0], 220), ([8.0, 3.0, 1.0], 320)]
    assert fake_px.calls == [
        {
            "rows": [5.0, 2.0],
            "x": "группа",
            "y": "энергия_Дж",
            "title": "Энергия по группам",
        }
    ]
    assert plot_calls == [{"kind": "bar", "title": "Энергия по группам"}]


def test_render_energy_audit_results_section_swallows_plotly_failures() -> None:
    fake_st = _FakeStreamlit()
    dataframe_calls: list[int] = []
    plot_calls: list[object] = []

    df_groups = pd.DataFrame(
        {
            "группа": ["a"],
            "энергия_Дж": [1.0],
        }
    )

    helpers.render_energy_audit_results_section(
        fake_st,
        df_Egroups=df_groups,
        df_Eedges=None,
        safe_dataframe_fn=lambda frame, *, height: dataframe_calls.append(height),
        has_plotly=True,
        px_module=_FailingPlotlyExpress(),
        safe_plotly_chart_fn=lambda fig: plot_calls.append(fig),
        section_title="Energy",
        top_edges_title="top",
    )

    assert fake_st.subheaders == ["Energy"]
    assert dataframe_calls == [220]
    assert plot_calls == []
    assert fake_st.markdowns == []


def test_entrypoints_use_shared_energy_audit_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    secondary_text = SECONDARY_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_energy_audit_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_energy_audit_section_helpers import (" in heavy_text
    assert "render_energy_audit_results_section(" not in app_text
    assert "render_energy_audit_results_section(" not in heavy_text
    assert 'st.subheader("Энерго‑аудит")' not in app_text
    assert 'st.subheader("Энерго-аудит")' not in heavy_text
    assert 'px.bar(df_Egroups.sort_values("энергия_Дж", ascending=False)' not in app_text
    assert 'px.bar(df_Egroups.sort_values("энергия_Дж", ascending=False)' not in heavy_text
    assert 'st.markdown("**TOP‑20 элементов по энергии**")' not in app_text
    assert 'st.markdown("**TOP-20 элементов по энергии**")' not in heavy_text
    assert '"render_energy_audit_section_fn": render_energy_audit_results_section' in app_text
    assert '"render_energy_audit_section_fn": render_energy_audit_results_section' in heavy_text
    assert "energy_audit_section_kwargs" in secondary_text
    assert "def render_energy_audit_results_section(" in helper_text
    assert "px_module.bar(" in helper_text
    assert "safe_plotly_chart_fn(fig)" in helper_text
