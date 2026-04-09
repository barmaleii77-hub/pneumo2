from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_line_plot_helpers, ui_plot_studio_helpers
from pneumo_solver_ui.ui_plot_surface_profile_helpers import (
    build_line_plot_renderer,
    build_plot_studio_renderer,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_plot_surface_renderers_return_callable_profiles(monkeypatch) -> None:
    warnings: list[str] = []
    infos: list[str] = []
    monkeypatch.setattr(ui_plot_studio_helpers.st, "warning", warnings.append)
    monkeypatch.setattr(ui_plot_studio_helpers.st, "info", infos.append)

    plot_studio = build_plot_studio_renderer(
        has_plotly=False,
        go_module=None,
        make_subplots_fn=lambda **kwargs: None,
        safe_plotly_chart_fn=lambda *args, **kwargs: None,
        infer_unit_and_transform_fn=lambda name: ("", None, ""),
        extract_plotly_selection_points_fn=lambda state: [],
        plotly_points_signature_fn=lambda pts: "",
        decimate_minmax_fn=lambda x, y, max_points: (x, y),
        missing_plotly_message="Plotly missing for builder test",
    )
    plot_studio(
        df=pd.DataFrame({"время_с": [0.0], "signal": [1.0]}),
        tcol="время_с",
        y_cols=["signal"],
    )
    assert infos == []
    assert warnings == ["Plotly missing for builder test"]

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.infos: list[str] = []
            self.line_charts: list[tuple[pd.DataFrame, int]] = []
            self.session_state: dict[str, object] = {}

        def info(self, message: str) -> None:
            self.infos.append(message)

        def line_chart(self, data: pd.DataFrame, *, height: int) -> None:
            self.line_charts.append((data.copy(), height))

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ui_line_plot_helpers, "st", fake_st)
    plot_lines = build_line_plot_renderer(
        has_plotly=False,
        go_module=None,
        safe_plotly_chart_fn=lambda *args, **kwargs: None,
        is_any_fallback_anim_playing_fn=lambda: False,
        shorten_name_fn=lambda name, limit: name[:limit],
        preprocess_df_and_y_cols_fn=ui_line_plot_helpers.prefer_rel0_plot_columns,
    )
    result = plot_lines(
        df=pd.DataFrame({"t": [0.0, 1.0], "disp_m": [1.0, 2.0], "disp_rel0_m": [10.0, 12.0]}),
        x_col="t",
        y_cols=["disp_m"],
        title="Rel0 Plot",
        playhead_x=1.0,
    )
    assert fake_st.infos == []
    assert float(fake_st.line_charts[0][0].iloc[1]["disp_m"]) == 12.0
    assert result == {"idx": 1, "x": 1.0, "values": {"disp_m": 12.0}}


def test_active_entrypoints_use_shared_plot_surface_profile_builder() -> None:
    helper_source = (ROOT / "pneumo_solver_ui" / "ui_plot_surface_profile_helpers.py").read_text(encoding="utf-8")
    app_source = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def build_plot_studio_renderer" in helper_source
    assert "def build_line_plot_renderer" in helper_source
    assert "from pneumo_solver_ui.ui_plot_surface_profile_helpers import (" in app_source
    assert "from pneumo_solver_ui.ui_plot_surface_profile_helpers import (" in heavy_source
    assert "build_plot_studio_renderer(" in app_source
    assert "build_plot_studio_renderer(" in heavy_source
    assert "build_line_plot_renderer(" in app_source
    assert "build_line_plot_renderer(" in heavy_source
