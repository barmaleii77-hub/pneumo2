import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "pneumo_solver_ui" / "default_base.json"


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def _scenario():
    return {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _run(
    dt_int_max: float,
    *,
    err_control: bool = False,
    rtol: float | None = None,
    atol: float | None = None,
    mass_rtol_scale_factor: float | None = None,
    err_group_weight_mass: float | None = None,
):
    params = {
        "mechanics_selfcheck": True,
        "mechanics_selfcheck_tol_m": 1e-6,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": float(dt_int_max),
    }
    if err_control:
        params["интегратор_контроль_локальной_ошибки"] = True
        if rtol is not None:
            params["интегратор_rtol"] = float(rtol)
        if atol is not None:
            params["интегратор_atol"] = float(atol)
        if mass_rtol_scale_factor is not None:
            params["интегратор_mass_rtol_scale_factor"] = float(mass_rtol_scale_factor)
        if err_group_weight_mass is not None:
            params["интегратор_err_group_weight_mass"] = float(err_group_weight_mass)
    df_main, *_, df_atm = m.simulate(params, _scenario(), dt=2e-3, t_end=0.05, record_full=False)
    return df_main, df_atm


def test_default_base_uses_practical_integrator_error_control_tolerances() -> None:
    data = json.loads(DEFAULT_BASE.read_text(encoding="utf-8"))

    assert data["интегратор_контроль_локальной_ошибки"] is False
    assert data["интегратор_rtol"] == 1e-3
    assert data["интегратор_atol"] == 1e-7
    assert data["интегратор_mass_rtol_scale_factor"] == 2.0
    assert data["интегратор_err_group_weight_mass"] == 0.92


def test_default_error_control_profile_is_accuracy_positive_without_pathological_rejects() -> None:
    data = json.loads(DEFAULT_BASE.read_text(encoding="utf-8"))
    col = "давление_ресивер2_Па"

    df_fine, _ = _run(7.5e-5, err_control=False)
    df_coarse, _ = _run(3.0e-4, err_control=False)
    df_default_ec, _ = _run(
        3.0e-4,
        err_control=True,
        rtol=float(data["интегратор_rtol"]),
        atol=float(data["интегратор_atol"]),
        mass_rtol_scale_factor=float(data["интегратор_mass_rtol_scale_factor"]),
        err_group_weight_mass=float(data["интегратор_err_group_weight_mass"]),
    )

    y_fine = df_fine[col].to_numpy(dtype=float)
    e_coarse = float(np.max(np.abs(df_coarse[col].to_numpy(dtype=float) - y_fine)))
    e_default_ec = float(np.max(np.abs(df_default_ec[col].to_numpy(dtype=float) - y_fine)))

    rejects = float(np.nansum(df_default_ec["интегратор_отклонения_N"].to_numpy(dtype=float)))
    nsub_mean = float(np.nanmean(df_default_ec["интегратор_подшаги_N"].to_numpy(dtype=float)))

    assert e_default_ec < e_coarse
    assert (e_coarse / (e_default_ec + 1e-12)) > 10.0
    assert rejects < 700.0
    assert nsub_mean < 30.0


def test_mass_group_weight_improves_reject_profile_without_hurting_accuracy() -> None:
    data = json.loads(DEFAULT_BASE.read_text(encoding="utf-8"))
    col = "давление_ресивер2_Па"

    df_fine, _ = _run(7.5e-5, err_control=False)
    y_fine = df_fine[col].to_numpy(dtype=float)

    df_unweighted, _ = _run(
        3.0e-4,
        err_control=True,
        rtol=float(data["интегратор_rtol"]),
        atol=float(data["интегратор_atol"]),
        mass_rtol_scale_factor=float(data["интегратор_mass_rtol_scale_factor"]),
        err_group_weight_mass=1.0,
    )
    df_weighted, _ = _run(
        3.0e-4,
        err_control=True,
        rtol=float(data["интегратор_rtol"]),
        atol=float(data["интегратор_atol"]),
        mass_rtol_scale_factor=float(data["интегратор_mass_rtol_scale_factor"]),
        err_group_weight_mass=float(data["интегратор_err_group_weight_mass"]),
    )

    e_unweighted = float(np.max(np.abs(df_unweighted[col].to_numpy(dtype=float) - y_fine)))
    e_weighted = float(np.max(np.abs(df_weighted[col].to_numpy(dtype=float) - y_fine)))
    rejects_unweighted = float(np.nansum(df_unweighted["интегратор_отклонения_N"].to_numpy(dtype=float)))
    rejects_weighted = float(np.nansum(df_weighted["интегратор_отклонения_N"].to_numpy(dtype=float)))
    nsub_unweighted = float(np.nanmean(df_unweighted["интегратор_подшаги_N"].to_numpy(dtype=float)))
    nsub_weighted = float(np.nanmean(df_weighted["интегратор_подшаги_N"].to_numpy(dtype=float)))

    assert rejects_weighted < rejects_unweighted
    assert nsub_weighted < nsub_unweighted
    assert e_weighted < e_unweighted


def test_error_control_df_atm_reports_group_diagnostics() -> None:
    data = json.loads(DEFAULT_BASE.read_text(encoding="utf-8"))
    _, df_atm = _run(
        3.0e-4,
        err_control=True,
        rtol=float(data["интегратор_rtol"]),
        atol=float(data["интегратор_atol"]),
        mass_rtol_scale_factor=float(data["интегратор_mass_rtol_scale_factor"]),
        err_group_weight_mass=float(data["интегратор_err_group_weight_mass"]),
    )

    row = df_atm.iloc[0]
    labels = ("body_pos", "wheel_pos", "body_vel", "wheel_vel", "mass")

    reject_sum = 0
    weighted_reject_sum = 0
    for label in labels:
        max_col = f"интегратор_err_group_max_{label}"
        reject_col = f"интегратор_err_reject_dominant_{label}_N"
        reject_weighted_col = f"интегратор_err_reject_weighted_dominant_{label}_N"
        assert max_col in df_atm.columns
        assert reject_col in df_atm.columns
        assert reject_weighted_col in df_atm.columns
        assert np.isfinite(float(row[max_col]))
        reject_value = int(row[reject_col])
        reject_weighted_value = int(row[reject_weighted_col])
        assert reject_value >= 0
        assert reject_weighted_value >= 0
        reject_sum += reject_value
        weighted_reject_sum += reject_weighted_value

    assert "интегратор_err_reject_dominant_group" in df_atm.columns
    assert "интегратор_err_reject_weighted_dominant_group" in df_atm.columns
    assert "интегратор_mass_rtol_scale_factor" in df_atm.columns
    assert "интегратор_err_group_weight_mass" in df_atm.columns
    assert float(row["интегратор_mass_rtol_scale_factor"]) == 2.0
    assert float(row["интегратор_err_group_weight_mass"]) == 0.92
    assert row["интегратор_err_reject_dominant_group"] in set(labels) | {"none"}
    assert row["интегратор_err_reject_weighted_dominant_group"] in set(labels) | {"none"}
    assert reject_sum == int(row["интегратор_total_rejects"])
    assert weighted_reject_sum == int(row["интегратор_total_rejects"])
