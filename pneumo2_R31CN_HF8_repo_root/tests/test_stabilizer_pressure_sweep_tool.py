from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.tools import stabilizer_pressure_sweep as sweep


def test_run_once_passes_explicit_t_end_and_handles_truncated_fit_window(monkeypatch) -> None:
    calls: dict[str, float] = {}

    class _FakeModel:
        def simulate(self, *, params, test, dt=None, t_end=None):
            calls["dt"] = float(dt)
            calls["t_end"] = float(t_end)
            calls["test_t_end"] = float(test["t_end"])
            t = np.linspace(0.0, 1.0, 6)
            phi = np.sin(2.0 * math.pi * t)
            phi_dot = np.gradient(phi, t)
            moment = 3.0 * phi + 2.0 * phi_dot
            df_main = pd.DataFrame(
                {
                    "время_с": t,
                    "момент_крен_подвеска_Нм": moment,
                    "крен_phi_рад": phi,
                    "скорость_крен_phi_рад_с": phi_dot,
                }
            )
            empty = pd.DataFrame()
            df_ecat = pd.DataFrame(
                {
                    "группа": ["дроссель", "выхлоп"],
                    "энергия_Дж": [1.5, 2.5],
                }
            )
            return df_main, empty, empty, [], [], empty, df_ecat, empty

    monkeypatch.setattr(sweep, "_ensure_repo_importable", lambda: Path("C:/tmp/pneumo_solver_ui"))
    monkeypatch.setattr(sweep.importlib, "import_module", lambda name: _FakeModel())

    res = sweep.run_once(
        model_name="fake_model",
        params={},
        mode="roll",
        freq_hz=1.0,
        A=0.001,
        dt=0.01,
        settle_cycles=6,
        fit_cycles=6,
    )

    assert calls["dt"] == 0.01
    assert calls["t_end"] == 12.0
    assert calls["test_t_end"] == 12.0
    assert res["amp_state"] > 0.0
    assert math.isfinite(res["K"])
    assert math.isfinite(res["C"])
    assert res["E_drossels_J"] == 1.5
    assert res["E_exhaust_J"] == 2.5


def test_energy_sum_by_group_supports_legacy_energy_column_name() -> None:
    df = pd.DataFrame(
        {
            "группа": ["дроссель", "выхлоп", "прочее"],
            "энергия_потерь_Дж": [3.0, 4.0, 5.0],
        }
    )

    assert sweep._energy_sum_by_group(df, "дрос") == 3.0
    assert sweep._energy_sum_by_group(df, "вых") == 4.0


def test_dataframe_to_markdown_fallback_does_not_require_tabulate(monkeypatch) -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})

    def _boom(*args, **kwargs):
        raise ImportError("Missing optional dependency 'tabulate'")

    monkeypatch.setattr(pd.DataFrame, "to_markdown", _boom)

    text = sweep._dataframe_to_markdown_fallback(df)
    assert "| a | b |" in text
    assert "| 1 | 2 |" in text
