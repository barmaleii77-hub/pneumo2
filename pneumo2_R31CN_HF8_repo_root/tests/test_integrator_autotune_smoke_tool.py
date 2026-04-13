from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.tools.integrator_autotune_smoke_check import _stats_from_df, run_check


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_integrator_autotune_smoke_direct_script_runs_ok() -> None:
    proc = subprocess.run(
        [sys.executable, str(UI_ROOT / "tools" / "integrator_autotune_smoke_check.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "PASS integrator_autotune:" in proc.stdout


def test_integrator_autotune_stats_reads_canonical_h_mean_column() -> None:
    df = pd.DataFrame(
        {
            "интегратор_подшаги_N": [1.0, 2.0, 3.0],
            "интегратор_подшаг_мин_с": [1e-4, 1.1e-4, 1.2e-4],
            "интегратор_подшаг_макс_с": [2e-4, 2.1e-4, 2.2e-4],
            "интегратор_подшаг_средн_с": [1.5e-4, 1.6e-4, 1.7e-4],
        }
    )

    stats = _stats_from_df(df)

    assert stats is not None
    assert np.isclose(stats["h_mean"], np.mean(df["интегратор_подшаг_средн_с"].to_numpy(dtype=float)))


def test_integrator_autotune_stats_keeps_legacy_h_mean_fallback() -> None:
    df = pd.DataFrame(
        {
            "интегратор_подшаги_N": [1.0, 2.0, 3.0],
            "интегратор_подшаг_мин_с": [1e-4, 1.1e-4, 1.2e-4],
            "интегратор_подшаг_макс_с": [2e-4, 2.1e-4, 2.2e-4],
            "интегратор_подшаг_средний_с": [1.5e-4, 1.6e-4, 1.7e-4],
        }
    )

    stats = _stats_from_df(df)

    assert stats is not None
    assert np.isclose(stats["h_mean"], np.mean(df["интегратор_подшаг_средний_с"].to_numpy(dtype=float)))


def test_integrator_autotune_run_check_uses_current_err_control_defaults() -> None:
    res = run_check(check_err_control=True)

    assert res["ok"] is True
    assert res["err_control_total_rejects"] >= 0
    assert res["err_control_total_substeps"] >= 0
    assert res["err_control_dominant_group"] in {"body_pos", "wheel_pos", "body_vel", "wheel_vel", "mass", "none"}
    assert res["err_control_weighted_dominant_group"] in {"body_pos", "wheel_pos", "body_vel", "wheel_vel", "mass", "none"}
    assert np.isclose(res["err_control_mass_rtol_scale_factor"], 2.0)
    assert np.isclose(res["err_control_err_group_weight_mass"], 0.92)
    assert np.isclose(res["err_control_rtol"], 1e-3)
    assert np.isclose(res["err_control_atol"], 1e-7)
    assert res["err_rtol_override"] is None
    assert res["err_atol_override"] is None
    assert res["err_mass_rtol_scale_factor_override"] is None


def test_integrator_autotune_run_check_accepts_explicit_err_control_overrides() -> None:
    res = run_check(
        check_err_control=True,
        err_rtol=2e-3,
        err_atol=5e-7,
        err_mass_rtol_scale_factor=2.5,
        err_group_weight_mass=0.9,
    )

    assert res["ok"] is True
    assert np.isclose(res["err_control_rtol"], 2e-3)
    assert np.isclose(res["err_control_atol"], 5e-7)
    assert np.isclose(res["err_control_mass_rtol_scale_factor"], 2.5)
    assert np.isclose(res["err_control_err_group_weight_mass"], 0.9)
    assert np.isclose(res["err_rtol_override"], 2e-3)
    assert np.isclose(res["err_atol_override"], 5e-7)
    assert np.isclose(res["err_mass_rtol_scale_factor_override"], 2.5)
    assert np.isclose(res["err_group_weight_mass_override"], 0.9)
