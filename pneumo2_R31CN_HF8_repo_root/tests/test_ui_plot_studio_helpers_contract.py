from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_plot_studio_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_plot_studio_timeseries_uses_injected_missing_plotly_message(monkeypatch) -> None:
    warnings: list[str] = []
    infos: list[str] = []

    monkeypatch.setattr(ui_plot_studio_helpers.st, "warning", warnings.append)
    monkeypatch.setattr(ui_plot_studio_helpers.st, "info", infos.append)

    ui_plot_studio_helpers.plot_studio_timeseries(
        df=pd.DataFrame({"время_с": [0.0], "signal": [1.0]}),
        tcol="время_с",
        y_cols=["signal"],
        has_plotly=False,
        go_module=None,
        make_subplots_fn=lambda **kwargs: None,
        safe_plotly_chart_fn=lambda *args, **kwargs: None,
        infer_unit_and_transform_fn=lambda name: ("", None, ""),
        extract_plotly_selection_points_fn=lambda state: [],
        plotly_points_signature_fn=lambda pts: "",
        decimate_minmax_fn=lambda x, y, max_points: (x, y),
        missing_plotly_message="Plotly missing for test",
    )

    assert infos == []
    assert warnings == ["Plotly missing for test"]


def test_entrypoints_use_shared_plot_studio_helper_without_local_duplicates() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_plot_studio_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_plot_studio_helpers import (" in heavy_text
    assert "def plot_studio_timeseries(" not in app_text
    assert "def plot_studio_timeseries(" not in heavy_text
    assert "def _legacy_plot_studio_timeseries_dead(" in app_text
    assert "def _legacy_plot_studio_timeseries_dead(" in heavy_text
    assert "plot_studio_timeseries = partial(" in app_text
    assert "plot_studio_timeseries = partial(" in heavy_text
    assert "missing_plotly_message=" in app_text
    assert "missing_plotly_message=" in heavy_text
