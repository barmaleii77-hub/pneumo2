from __future__ import annotations

import math

import numpy as np
import pandas as pd

from pneumo_solver_ui.tools import stabilizer_modal_probe as probe


def test_run_probe_roll_uses_force_moment_fallback_and_passes_dt_t_end(monkeypatch) -> None:
    calls: dict[str, float] = {}

    class _FakeModel:
        def simulate(self, *, params, test, dt=None, t_end=None):
            calls["dt"] = float(dt)
            calls["t_end"] = float(t_end)
            calls["test_t_end"] = float(test["t_end"])
            t = np.linspace(0.0, 1.0, 9)
            phi = np.sin(2.0 * math.pi * t)
            phi_dot = np.gradient(phi, t)
            moment = 5.0 * phi + 2.0 * phi_dot
            base = 1000.0
            d = 0.5 * moment
            df_main = pd.DataFrame(
                {
                    "время_с": t,
                    "крен_phi_рад": phi,
                    "нормальная_сила_шины_ЛП_Н": base + d,
                    "нормальная_сила_шины_ПП_Н": base - d,
                    "нормальная_сила_шины_ЛЗ_Н": base + d,
                    "нормальная_сила_шины_ПЗ_Н": base - d,
                }
            )
            empty = pd.DataFrame()
            df_ecat = pd.DataFrame({"группа": ["дроссель", "выхлоп"], "энергия_Дж": [1.0, 2.0]})
            return df_main, empty, empty, [], [], empty, df_ecat, empty

    monkeypatch.setattr(probe, "_load_modal_model", lambda model_name: _FakeModel())

    res = probe.run_probe(
        params={"колея": 1.0},
        mode="roll",
        freq_hz=1.0,
        A=0.001,
        settle_cycles=6,
        fit_cycles=6,
        dt=0.01,
        model_name="fake_model",
    )

    assert calls["dt"] == 0.01
    assert calls["t_end"] == 12.0
    assert calls["test_t_end"] == 12.0
    assert math.isfinite(res.K)
    assert math.isfinite(res.C)
    assert res.amp_state > 0.0
    assert res.E_drossels_J == 1.0
    assert res.E_exhaust_J == 2.0


def test_run_probe_heave_uses_tire_force_and_numeric_velocity_fallback(monkeypatch) -> None:
    class _FakeModel:
        def simulate(self, *, params, test, dt=None, t_end=None):
            t = np.linspace(0.0, 1.0, 9)
            z = 0.02 * np.sin(2.0 * math.pi * t)
            z_dot = np.gradient(z, t)
            total_force = 4000.0 + 8.0 * z + 3.0 * z_dot
            per_corner = total_force / 4.0
            df_main = pd.DataFrame(
                {
                    "время_с": t,
                    "перемещение_рамы_z_м": z,
                    "нормальная_сила_шины_ЛП_Н": per_corner,
                    "нормальная_сила_шины_ПП_Н": per_corner,
                    "нормальная_сила_шины_ЛЗ_Н": per_corner,
                    "нормальная_сила_шины_ПЗ_Н": per_corner,
                }
            )
            empty = pd.DataFrame()
            return df_main, empty, empty, [], [], empty, empty, empty

    monkeypatch.setattr(probe, "_load_modal_model", lambda model_name: _FakeModel())

    res = probe.run_probe(
        params={},
        mode="heave",
        freq_hz=1.0,
        A=0.001,
        settle_cycles=2,
        fit_cycles=2,
        dt=0.01,
        model_name="fake_model",
    )

    assert math.isfinite(res.K)
    assert math.isfinite(res.C)
    assert res.amp_state > 0.0
