from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_line_plot_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.line_charts: list[tuple[pd.DataFrame, int]] = []
        self.session_state: dict[str, object] = {}

    def info(self, message: str) -> None:
        self.infos.append(message)

    def line_chart(self, data: pd.DataFrame, *, height: int) -> None:
        self.line_charts.append((data.copy(), height))


def test_plot_lines_can_use_shared_rel0_preprocessor(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ui_line_plot_helpers, "st", fake_st)

    result = ui_line_plot_helpers.plot_lines(
        df=pd.DataFrame(
            {
                "t": [0.0, 1.0],
                "disp_m": [1.0, 2.0],
                "disp_rel0_m": [10.0, 12.0],
            }
        ),
        x_col="t",
        y_cols=["disp_m"],
        title="Rel0 Plot",
        playhead_x=1.0,
        has_plotly=False,
        go_module=None,
        safe_plotly_chart_fn=lambda *args, **kwargs: None,
        is_any_fallback_anim_playing_fn=lambda: False,
        shorten_name_fn=lambda name, limit: name[:limit],
        preprocess_df_and_y_cols_fn=ui_line_plot_helpers.prefer_rel0_plot_columns,
    )

    assert fake_st.infos == []
    assert len(fake_st.line_charts) == 1
    line_chart_df, height = fake_st.line_charts[0]
    assert height == 320
    assert list(line_chart_df.columns) == ["disp_m"]
    assert float(line_chart_df.iloc[1]["disp_m"]) == 12.0
    assert result == {"idx": 1, "x": 1.0, "values": {"disp_m": 12.0}}


def test_entrypoints_use_shared_plot_lines_helper_without_public_duplicates() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_line_plot_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_line_plot_helpers import (" in heavy_text
    assert "def plot_lines(" not in app_text
    assert "def plot_lines(" not in heavy_text
    assert "def _legacy_plot_lines_dead(" in app_text
    assert "def _legacy_plot_lines_dead(" in heavy_text
    assert "plot_lines = partial(" in app_text
    assert "plot_lines = partial(" in heavy_text
    assert "plot_lines_core" in app_text
    assert "plot_lines_core" in heavy_text
    assert "preprocess_df_and_y_cols_fn=_prepare_plot_lines_df_and_y_cols" in heavy_text
    assert "prefer_rel0_plot_columns" in heavy_text
