import json
from pathlib import Path

import numpy as np
import pytest

from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "pneumo_solver_ui" / "default_base.json"
LEGACY_DT_INT_MAX_KEY = "\u043c\u0430\u043a\u0441_\u0448\u0430\u0433_\u0438\u043d\u0442\u0435\u0433\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f_\u0441"
LEGACY_MAX_INTERNAL_STEPS_KEY = "\u043c\u0430\u043a\u0441_\u0447\u0438\u0441\u043b\u043e_\u0432\u043d\u0443\u0442\u0440\u0435\u043d\u043d\u0438\u0445_\u0448\u0430\u0433\u043e\u0432_\u043d\u0430_dt"
LEGACY_LIM_REL_V_KEY = "\u043b\u0438\u043c\u0438\u0442_\u043e\u0442\u043d\u043e\u0441\u0438\u0442_\u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f_\u043e\u0431\u044a\u0451\u043c\u0430_\u0437\u0430_\u0448\u0430\u0433"


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


def _scenario_dynamic_stress():
    def smooth_step(t: float, t0: float, dur: float, amp: float) -> float:
        if t <= t0:
            return 0.0
        if t >= t0 + dur:
            return float(amp)
        x = (t - t0) / dur
        return float(amp) * 0.5 * (1.0 - np.cos(np.pi * x))

    return {
        "road_func": lambda t: np.array(
            [
                smooth_step(t, 0.02, 0.03, 0.04),
                smooth_step(t, 0.06, 0.025, 0.02),
                smooth_step(t, 0.04, 0.02, 0.03),
                smooth_step(t, 0.08, 0.03, 0.015),
            ],
            dtype=float,
        ),
        "ax_func": lambda t: 1.8 * np.sin(2.0 * np.pi * 2.0 * t),
        "ay_func": lambda t: 2.4 * np.sin(2.0 * np.pi * 1.6 * t + 0.2),
    }


def _scenario_nonfinite_ax():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: float("nan"),
        "ay_func": lambda t: 0.0,
    }


def _scenario_nonfinite_road():
    return {
        "road_func": lambda t: np.array([float("nan"), 0.0, 0.0, 0.0], dtype=float),
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
    scenario: dict | None = None,
    t_end: float = 0.05,
    runtime_qc_strict: bool = False,
    runtime_qc_min_pressure_pa: float | None = None,
    runtime_qc_max_pressure_pa: float | None = None,
    extra_params: dict | None = None,
):
    params = {
        "mechanics_selfcheck": True,
        "mechanics_selfcheck_tol_m": 1e-6,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_dt_int_max_s": float(dt_int_max),
        "integrator_runtime_qc_strict": bool(runtime_qc_strict),
    }
    if runtime_qc_min_pressure_pa is not None:
        params['integrator_runtime_qc_min_pressure_pa'] = float(runtime_qc_min_pressure_pa)
    if runtime_qc_max_pressure_pa is not None:
        params['integrator_runtime_qc_max_pressure_pa'] = float(runtime_qc_max_pressure_pa)
    if extra_params:
        params.update(dict(extra_params))
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
    scenario_obj = _scenario() if scenario is None else scenario
    df_main, *_, df_atm = m.simulate(params, scenario_obj, dt=2e-3, t_end=float(t_end), record_full=False)
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


def test_error_control_run_keeps_core_physics_geometry_and_pneumatics_finite() -> None:
    """Стресс-инварианты для данных модели при включенном error-control."""
    df_main, _ = _run(
        3.0e-4,
        err_control=True,
        rtol=1e-3,
        atol=1e-7,
        mass_rtol_scale_factor=2.0,
        err_group_weight_mass=0.92,
    )

    # Колонки [7:163] покрывают базовые перемещения/углы/силы/моменты/дорогу/давления.
    core_slice = df_main.iloc[:, 7:163].to_numpy(dtype=float)
    assert np.all(np.isfinite(core_slice))

    integrator_diag = df_main.iloc[:, 1:7].to_numpy(dtype=float)
    assert np.all(np.isfinite(integrator_diag))
    assert float(np.nanmax(df_main.iloc[:, 1].to_numpy(dtype=float))) >= 1.0  # N_sub
    assert float(np.nanmin(df_main.iloc[:, 2].to_numpy(dtype=float))) >= 0.0  # h_min
    assert float(np.nanmin(df_main.iloc[:, 3].to_numpy(dtype=float))) >= 0.0  # h_max
    assert float(np.nansum(df_main.iloc[:, 5].to_numpy(dtype=float))) >= 0.0  # rejects

    pa_suffix = "_\u041f\u0430"
    pressure_cols = [c for c in df_main.columns if c.endswith(pa_suffix)]
    assert len(pressure_cols) >= 4
    for col in pressure_cols:
        p = df_main[col].to_numpy(dtype=float)
        assert np.all(np.isfinite(p))
        assert float(np.min(p)) > 0.0


def test_error_control_long_run_dynamic_stress_remains_physical_and_stable() -> None:
    t_end = 0.30
    dt = 2e-3
    df_main, _ = _run(
        3.0e-4,
        err_control=True,
        rtol=1e-3,
        atol=1e-7,
        mass_rtol_scale_factor=2.0,
        err_group_weight_mass=0.92,
        scenario=_scenario_dynamic_stress(),
        t_end=t_end,
    )

    expected_rows = int(round(t_end / dt)) + 1
    assert len(df_main) == expected_rows

    core_slice = df_main.iloc[:, 7:163].to_numpy(dtype=float)
    assert np.all(np.isfinite(core_slice))

    integrator_diag = df_main.iloc[:, 1:7].to_numpy(dtype=float)
    assert np.all(np.isfinite(integrator_diag))
    assert float(np.nanmax(df_main.iloc[:, 1].to_numpy(dtype=float))) >= 1.0  # n_sub
    assert float(np.nanmax(df_main.iloc[:, 3].to_numpy(dtype=float))) <= 3.0e-4 * (1.0 + 1e-9) + 1e-15
    assert float(np.nansum(df_main.iloc[:, 5].to_numpy(dtype=float))) >= 0.0  # rejects
    assert float(np.nanmax(df_main.iloc[:, 6].to_numpy(dtype=float))) >= 0.0  # err_max

    pressure_slice = df_main.iloc[:, 111:115].to_numpy(dtype=float)
    assert np.all(np.isfinite(pressure_slice))
    assert float(np.nanmin(pressure_slice)) > 0.0

    roll = df_main.iloc[:, 8].to_numpy(dtype=float)
    pitch = df_main.iloc[:, 9].to_numpy(dtype=float)
    assert np.all(np.isfinite(roll))
    assert np.all(np.isfinite(pitch))
    assert float(np.nanmax(np.abs(roll))) < np.deg2rad(89.0)
    assert float(np.nanmax(np.abs(pitch))) < np.deg2rad(89.0)


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


def test_error_control_invalid_string_params_are_safely_sanitized() -> None:
    _, df_atm = _run(
        3.0e-4,
        err_control=True,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "интегратор_rtol": "bad",
            "интегратор_atol": "bad",
            "интегратор_safety": "bad",
            "интегратор_fac_min": "bad",
            "интегратор_fac_max": "bad",
            "интегратор_h_min_с": "bad",
            "интегратор_mass_rtol_scale_factor": "bad",
            "интегратор_err_group_weight_mass": "bad",
        },
    )
    row = df_atm.iloc[0]
    assert float(row["интегратор_rtol"]) == pytest.approx(1.0e-4, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_atol"]) == pytest.approx(1.0e-8, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_safety"]) == pytest.approx(0.9, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_fac_min"]) == pytest.approx(0.2, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_fac_max"]) == pytest.approx(5.0, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_h_min_param_с"]) == pytest.approx(1.0e-7, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_mass_rtol_scale_factor"]) == pytest.approx(2.0, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_err_group_weight_mass"]) == pytest.approx(0.92, rel=1e-12, abs=1e-18)


@pytest.mark.parametrize(
    ("raw_value", "expected_enabled"),
    [("false", 0), ("0", 0), ("true", 1), ("1", 1), ("bad", 0)],
)
def test_error_control_string_flag_is_parsed_predictably(raw_value, expected_enabled) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"интегратор_контроль_локальной_ошибки": raw_value},
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_error_control"]) == int(expected_enabled)


@pytest.mark.parametrize(("raw_value", "expected_enabled"), [(" TRUE ", 1), (" off ", 0), (" YeS ", 1)])
def test_error_control_string_flag_is_case_insensitive_and_trimmed(raw_value, expected_enabled) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_error_control": raw_value},
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_error_control"]) == int(expected_enabled)


@pytest.mark.parametrize(("raw_value", "expected_enabled"), [(1.0, 1), (0.0, 0), (float("nan"), 0)])
def test_error_control_numeric_flag_is_parsed_predictably(raw_value, expected_enabled) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_error_control": raw_value},
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_error_control"]) == int(expected_enabled)


def test_error_control_nonscalar_flag_falls_back_to_disabled() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_error_control": [1]},
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_error_control"]) == 0


def test_error_control_ascii_aliases_have_priority_over_legacy_keys() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_error_control": "true",
            "интегратор_контроль_локальной_ошибки": False,
            "integrator_rtol": 2.0e-3,
            "интегратор_rtol": 1.0e-4,
            "integrator_atol": 3.0e-7,
            "интегратор_atol": 1.0e-8,
            "integrator_safety": 0.85,
            "интегратор_safety": 0.9,
            "integrator_fac_min": 0.3,
            "интегратор_fac_min": 0.2,
            "integrator_fac_max": 4.0,
            "интегратор_fac_max": 5.0,
            "integrator_h_min_s": 2.0e-7,
            "интегратор_h_min_с": 1.0e-7,
            "integrator_mass_rtol_scale_factor": 2.5,
            "интегратор_mass_rtol_scale_factor": 2.0,
            "integrator_err_group_weight_mass": 0.88,
            "интегратор_err_group_weight_mass": 0.92,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_error_control"]) == 1
    assert float(row["интегратор_rtol"]) == pytest.approx(2.0e-3, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_atol"]) == pytest.approx(3.0e-7, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_safety"]) == pytest.approx(0.85, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_fac_min"]) == pytest.approx(0.3, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_fac_max"]) == pytest.approx(4.0, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_h_min_param_с"]) == pytest.approx(2.0e-7, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_mass_rtol_scale_factor"]) == pytest.approx(2.5, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_err_group_weight_mass"]) == pytest.approx(0.88, rel=1e-12, abs=1e-18)


def test_error_control_invalid_ascii_string_params_are_safely_sanitized() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_error_control": "bad",
            "integrator_rtol": "bad",
            "integrator_atol": "bad",
            "integrator_safety": "bad",
            "integrator_fac_min": "bad",
            "integrator_fac_max": "bad",
            "integrator_h_min_s": "bad",
            "integrator_mass_rtol_scale_factor": "bad",
            "integrator_err_group_weight_mass": "bad",
        },
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_error_control"]) == 0
    assert float(row["интегратор_rtol"]) == pytest.approx(1.0e-4, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_atol"]) == pytest.approx(1.0e-8, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_safety"]) == pytest.approx(0.9, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_fac_min"]) == pytest.approx(0.2, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_fac_max"]) == pytest.approx(5.0, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_h_min_param_с"]) == pytest.approx(1.0e-7, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_mass_rtol_scale_factor"]) == pytest.approx(2.0, rel=1e-12, abs=1e-18)
    assert float(row["интегратор_err_group_weight_mass"]) == pytest.approx(0.92, rel=1e-12, abs=1e-18)


def test_error_control_invalid_numeric_params_are_safely_sanitized() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_error_control": float("inf"),
            "integrator_rtol": float("nan"),
            "integrator_atol": float("inf"),
            "integrator_safety": float("-inf"),
            "integrator_fac_min": float("inf"),
            "integrator_fac_max": float("-inf"),
            "integrator_h_min_s": float("nan"),
            "integrator_mass_rtol_scale_factor": float("inf"),
            "integrator_err_group_weight_mass": float("-inf"),
        },
    )
    row = df_atm.iloc[0]

    def _pick_suffix(suffix: str) -> str:
        matches = [c for c in row.index if c.endswith(suffix)]
        assert len(matches) == 1
        return matches[0]

    def _pick_contains(token: str) -> str:
        matches = [c for c in row.index if token in c]
        assert len(matches) == 1
        return matches[0]

    assert int(row[_pick_suffix("_error_control")]) == 0
    assert float(row[_pick_suffix("_rtol")]) == pytest.approx(1.0e-4, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_atol")]) == pytest.approx(1.0e-8, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_safety")]) == pytest.approx(0.9, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_fac_min")]) == pytest.approx(0.2, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_fac_max")]) == pytest.approx(5.0, rel=1e-12, abs=1e-18)
    assert float(row[_pick_contains("h_min_param")]) == pytest.approx(1.0e-7, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_mass_rtol_scale_factor")]) == pytest.approx(2.0, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_err_group_weight_mass")]) == pytest.approx(0.92, rel=1e-12, abs=1e-18)


def test_error_control_nonscalar_numeric_params_are_safely_sanitized() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_error_control": [1],
            "integrator_rtol": [1e-3],
            "integrator_atol": [1e-7],
            "integrator_safety": [0.9],
            "integrator_fac_min": [0.2],
            "integrator_fac_max": [5.0],
            "integrator_h_min_s": [1e-7],
            "integrator_mass_rtol_scale_factor": [2.0],
            "integrator_err_group_weight_mass": [0.92],
        },
    )
    row = df_atm.iloc[0]

    def _pick_suffix(suffix: str) -> str:
        matches = [c for c in row.index if c.endswith(suffix)]
        assert len(matches) == 1
        return matches[0]

    def _pick_contains(token: str) -> str:
        matches = [c for c in row.index if token in c]
        assert len(matches) == 1
        return matches[0]

    assert int(row[_pick_suffix("_error_control")]) == 0
    assert float(row[_pick_suffix("_rtol")]) == pytest.approx(1.0e-4, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_atol")]) == pytest.approx(1.0e-8, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_safety")]) == pytest.approx(0.9, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_fac_min")]) == pytest.approx(0.2, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_fac_max")]) == pytest.approx(5.0, rel=1e-12, abs=1e-18)
    assert float(row[_pick_contains("h_min_param")]) == pytest.approx(1.0e-7, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_mass_rtol_scale_factor")]) == pytest.approx(2.0, rel=1e-12, abs=1e-18)
    assert float(row[_pick_suffix("_err_group_weight_mass")]) == pytest.approx(0.92, rel=1e-12, abs=1e-18)


@pytest.mark.parametrize(
    ("param_key", "raw_value", "metric_suffix", "expected"),
    [
        ("integrator_rtol", 0.0, "_rtol", 1.0e-4),
        ("integrator_rtol", -1.0e-6, "_rtol", 1.0e-4),
        ("integrator_atol", 0.0, "_atol", 1.0e-8),
        ("integrator_atol", -1.0e-9, "_atol", 1.0e-8),
        ("integrator_safety", 0.0, "_safety", 0.9),
        ("integrator_safety", 1.2, "_safety", 0.9),
        ("integrator_fac_min", 0.0, "_fac_min", 0.2),
        ("integrator_fac_min", 1.0, "_fac_min", 0.2),
        ("integrator_fac_max", 1.0, "_fac_max", 5.0),
        ("integrator_fac_max", -2.0, "_fac_max", 5.0),
        ("integrator_h_min_s", 0.0, "h_min_param", 1.0e-7),
        ("integrator_h_min_s", -1.0e-8, "h_min_param", 1.0e-7),
        ("integrator_mass_rtol_scale_factor", 0.5, "_mass_rtol_scale_factor", 2.0),
        ("integrator_err_group_weight_mass", 0.0, "_err_group_weight_mass", 0.92),
    ],
)
def test_error_control_finite_out_of_bounds_params_are_safely_sanitized(
    param_key, raw_value, metric_suffix, expected
) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_error_control": True,
            param_key: raw_value,
        },
    )
    row = df_atm.iloc[0]

    if metric_suffix.startswith("_"):
        matches = [c for c in row.index if c.endswith(metric_suffix)]
    else:
        matches = [c for c in row.index if metric_suffix in c]
    assert len(matches) == 1
    assert float(row[matches[0]]) == pytest.approx(float(expected), rel=1e-12, abs=1e-18)


def test_error_control_df_atm_runtime_qc_flags_are_physical_and_consistent() -> None:
    df_main, df_atm = _run(
        3.0e-4,
        err_control=True,
        rtol=1e-3,
        atol=1e-7,
        mass_rtol_scale_factor=2.0,
        err_group_weight_mass=0.92,
    )

    row = df_atm.iloc[0]
    expected_cols = (
        "integrator_active_rows_N",
        "integrator_hmax_limit_s",
        "integrator_hmax_violation_count",
        "integrator_hmax_violation_max_over_s",
        "integrator_hmax_le_dt_int_max_ok",
        "integrator_reject_rate",
        "solver_core_nonfinite_count",
        "solver_core_finite_ok",
        "solver_pressure_nonfinite_count",
        "solver_pressure_finite_ok",
        "solver_pressure_min_pa",
        "solver_pressure_max_pa",
        "solver_pressure_positive_ok",
        "solver_mass_state_initial_kg",
        "solver_mass_state_final_kg",
        "solver_mass_state_delta_kg",
        "solver_mass_atm_net_kg",
        "solver_mass_balance_residual_kg",
        "solver_mass_balance_residual_abs_kg",
        "solver_mass_balance_residual_rel",
        "solver_mass_balance_ok",
        "integrator_runtime_qc_min_pressure_req_pa",
        "integrator_runtime_qc_max_pressure_pa",
        "integrator_runtime_qc_max_reject_rate",
        "integrator_runtime_qc_max_mass_balance_residual_kg",
        "integrator_runtime_qc_max_mass_balance_residual_rel",
        "integrator_runtime_qc_require_active_rows",
        "integrator_runtime_qc_ok",
        "integrator_runtime_qc_msg",
    )
    for col in expected_cols:
        assert col in df_atm.columns

    active_rows = int(row["integrator_active_rows_N"])
    hmax_limit = float(row["integrator_hmax_limit_s"])
    hmax_violation_count = int(row["integrator_hmax_violation_count"])
    hmax_violation_max_over = float(row["integrator_hmax_violation_max_over_s"])
    reject_rate = float(row["integrator_reject_rate"])
    core_nonfinite_count = int(row["solver_core_nonfinite_count"])
    pressure_nonfinite_count = int(row["solver_pressure_nonfinite_count"])
    pressure_min = float(row["solver_pressure_min_pa"])
    pressure_max = float(row["solver_pressure_max_pa"])

    assert active_rows > 0
    assert hmax_limit > 0.0
    assert hmax_violation_count >= 0
    assert hmax_violation_max_over >= 0.0
    assert reject_rate >= 0.0
    assert core_nonfinite_count >= 0
    assert pressure_nonfinite_count >= 0
    assert np.isfinite(pressure_min)
    assert np.isfinite(pressure_max)
    assert pressure_min > 0.0
    assert pressure_max >= pressure_min

    assert int(row["integrator_hmax_le_dt_int_max_ok"]) == 1
    assert int(row["solver_core_finite_ok"]) == 1
    assert int(row["solver_pressure_finite_ok"]) == 1
    assert int(row["solver_pressure_positive_ok"]) == 1
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 1
    assert str(row["integrator_runtime_qc_msg"]) == "ok"
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == 0.0
    assert not np.isnan(float(row["integrator_runtime_qc_max_pressure_pa"]))
    assert not np.isnan(float(row["integrator_runtime_qc_max_reject_rate"]))
    assert not np.isnan(float(row["integrator_runtime_qc_max_mass_balance_residual_kg"]))
    assert not np.isnan(float(row["integrator_runtime_qc_max_mass_balance_residual_rel"]))
    assert np.isfinite(float(row["solver_mass_state_initial_kg"]))
    assert np.isfinite(float(row["solver_mass_state_final_kg"]))
    assert np.isfinite(float(row["solver_mass_state_delta_kg"]))
    assert np.isfinite(float(row["solver_mass_atm_net_kg"]))
    assert np.isfinite(float(row["solver_mass_balance_residual_kg"]))
    assert np.isfinite(float(row["solver_mass_balance_residual_abs_kg"]))
    assert np.isfinite(float(row["solver_mass_balance_residual_rel"]))
    assert int(row["solver_mass_balance_ok"]) == 1

    hmax = df_main.iloc[:, 3].to_numpy(dtype=float)
    nsub = df_main.iloc[:, 1].to_numpy(dtype=float)
    mask = nsub > 0.0
    hmax_limit_local = 3.0e-4 * (1.0 + 1e-9) + 1e-15
    if np.any(mask):
        violations = hmax[mask] > hmax_limit_local
        assert hmax_violation_count == int(np.sum(violations))



def test_runtime_qc_strict_raises_when_pressure_threshold_is_unreachable() -> None:
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        _run(
            3.0e-4,
            err_control=True,
            rtol=1e-3,
            atol=1e-7,
            mass_rtol_scale_factor=2.0,
            err_group_weight_mass=0.92,
            runtime_qc_strict=True,
            runtime_qc_min_pressure_pa=1.0e9,
        )


def test_runtime_qc_strict_raises_when_pressure_ceiling_is_too_low() -> None:
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        _run(
            3.0e-4,
            err_control=True,
            rtol=1e-3,
            atol=1e-7,
            mass_rtol_scale_factor=2.0,
            err_group_weight_mass=0.92,
            runtime_qc_strict=True,
            runtime_qc_min_pressure_pa=0.0,
            runtime_qc_max_pressure_pa=1.0,
        )


def test_runtime_qc_invalid_string_params_are_safely_sanitized() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_min_pressure_pa": "bad",
            "integrator_runtime_qc_max_pressure_pa": "bad",
            "integrator_runtime_qc_max_reject_rate": "bad",
            "integrator_runtime_qc_max_mass_balance_residual_kg": "bad",
            "integrator_runtime_qc_max_mass_balance_residual_rel": "bad",
            "integrator_runtime_qc_require_active_rows": "false",
        },
    )
    row = df_atm.iloc[0]
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == pytest.approx(0.0, rel=0.0, abs=0.0)
    assert np.isinf(float(row["integrator_runtime_qc_max_pressure_pa"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_reject_rate"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_kg"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_rel"]))
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 0
    assert int(row["integrator_runtime_qc_ok"]) == 1


def test_runtime_qc_nan_and_negative_limits_are_safely_normalized() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_min_pressure_pa": float("nan"),
            "integrator_runtime_qc_max_reject_rate": -1.0,
            "integrator_runtime_qc_max_mass_balance_residual_kg": -1.0,
            "integrator_runtime_qc_max_mass_balance_residual_rel": -1.0,
        },
    )
    row = df_atm.iloc[0]
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == pytest.approx(0.0, rel=0.0, abs=0.0)
    assert np.isinf(float(row["integrator_runtime_qc_max_reject_rate"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_kg"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_rel"]))
    assert int(row["integrator_runtime_qc_ok"]) == 1


@pytest.mark.parametrize(("min_p_raw", "max_p_raw"), [(-1.0, 0.0), (-100.0, -5.0)])
def test_runtime_qc_finite_out_of_bounds_pressure_limits_are_safely_normalized(min_p_raw, max_p_raw) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_min_pressure_pa": min_p_raw,
            "integrator_runtime_qc_max_pressure_pa": max_p_raw,
        },
    )
    row = df_atm.iloc[0]
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == pytest.approx(0.0, rel=0.0, abs=0.0)
    assert np.isinf(float(row["integrator_runtime_qc_max_pressure_pa"]))
    assert int(row["integrator_runtime_qc_ok"]) == 1


@pytest.mark.parametrize("strict_token", ["false", "0", "no", "off"])
def test_runtime_qc_strict_false_tokens_do_not_raise(strict_token) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_strict": strict_token,
            "integrator_runtime_qc_min_pressure_pa": 1.0e9,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


def test_runtime_qc_bool_nan_values_fall_back_to_safe_defaults() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_strict": float("nan"),
            "integrator_runtime_qc_require_active_rows": float("nan"),
            "integrator_runtime_qc_min_pressure_pa": 1.0e9,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("strict_raw", [float("inf"), -float("inf")])
def test_runtime_qc_strict_nonfinite_numeric_values_fall_back_to_false(strict_raw) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_strict": strict_raw,
            "integrator_runtime_qc_min_pressure_pa": 1.0e9,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("require_raw", [float("inf"), -float("inf")])
def test_runtime_qc_require_active_rows_nonfinite_numeric_values_fall_back_to_default_true(require_raw) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_require_active_rows": require_raw,
            "integrator_runtime_qc_min_pressure_pa": 1.0e9,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


def test_runtime_qc_bool_nonscalar_values_fall_back_to_safe_defaults() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_strict": [1],
            "integrator_runtime_qc_require_active_rows": [0],
            "integrator_runtime_qc_min_pressure_pa": 1.0e9,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("strict_token", ["true", "1", "yes", "on"])
def test_runtime_qc_strict_true_tokens_raise(strict_token) -> None:
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        _run(
            3.0e-4,
            scenario=_scenario(),
            t_end=0.02,
            extra_params={
                "integrator_runtime_qc_strict": strict_token,
                "integrator_runtime_qc_min_pressure_pa": 1.0e9,
            },
        )


@pytest.mark.parametrize("strict_raw", [0.0])
def test_runtime_qc_strict_zero_numeric_value_falls_back_to_false(strict_raw) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_runtime_qc_strict": strict_raw,
            "integrator_runtime_qc_min_pressure_pa": 1.0e9,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("strict_raw", [1.0, -1.0, 1.0e-12])
def test_runtime_qc_strict_nonzero_numeric_values_enable_strict_mode(strict_raw) -> None:
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        _run(
            3.0e-4,
            scenario=_scenario(),
            t_end=0.02,
            extra_params={
                "integrator_runtime_qc_strict": strict_raw,
                "integrator_runtime_qc_min_pressure_pa": 1.0e9,
            },
        )


@pytest.mark.parametrize(("strict_token", "must_raise"), [(" TRUE ", True), (" off ", False)])
def test_runtime_qc_strict_tokens_are_case_insensitive_and_trimmed(strict_token, must_raise) -> None:
    if must_raise:
        with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
            _run(
                3.0e-4,
                scenario=_scenario(),
                t_end=0.02,
                extra_params={
                    "integrator_runtime_qc_strict": strict_token,
                    "integrator_runtime_qc_min_pressure_pa": 1.0e9,
                },
            )
    else:
        _, df_atm = _run(
            3.0e-4,
            scenario=_scenario(),
            t_end=0.02,
            extra_params={
                "integrator_runtime_qc_strict": strict_token,
                "integrator_runtime_qc_min_pressure_pa": 1.0e9,
            },
        )
        row = df_atm.iloc[0]
        assert int(row["integrator_runtime_qc_ok"]) == 0
        assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize(("raw_value", "expected"), [(" FALSE ", 0), (" TrUe ", 1), (" maybe ", 1)])
def test_runtime_qc_require_active_rows_tokens_are_case_insensitive_and_default_safe(
    raw_value, expected
) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_runtime_qc_require_active_rows": raw_value},
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == int(expected)


@pytest.mark.parametrize(("raw_value", "expected"), [(0.0, 0), (1.0, 1), (float("nan"), 1)])
def test_runtime_qc_require_active_rows_numeric_values_are_parsed_predictably(raw_value, expected) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_runtime_qc_require_active_rows": raw_value},
    )
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == int(expected)


def test_worldroad_zero_duration_runtime_qc_requires_active_rows_by_default() -> None:
    df_main, df_atm = _run(3.0e-4, scenario=_scenario(), t_end=0.0)
    row = df_atm.iloc[0]
    assert len(df_main) == 1
    assert int(row["integrator_active_rows_N"]) == 0
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert str(row["integrator_runtime_qc_msg"]) == "no_active_integrator_rows"


def test_worldroad_zero_duration_runtime_qc_can_disable_active_rows_requirement() -> None:
    df_main, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.0,
        extra_params={"integrator_runtime_qc_require_active_rows": False},
    )
    row = df_atm.iloc[0]
    assert len(df_main) == 1
    assert int(row["integrator_active_rows_N"]) == 0
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 0
    assert int(row["integrator_runtime_qc_ok"]) == 1
    assert str(row["integrator_runtime_qc_msg"]) == "ok"


def test_worldroad_zero_duration_runtime_qc_strict_raises_unless_active_rows_requirement_is_disabled() -> None:
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        _run(
            3.0e-4,
            scenario=_scenario(),
            t_end=0.0,
            extra_params={"integrator_runtime_qc_strict": True},
        )

    _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.0,
        extra_params={
            "integrator_runtime_qc_strict": True,
            "integrator_runtime_qc_require_active_rows": False,
        },
    )


def test_worldroad_raises_on_nonfinite_ax_input_signal() -> None:
    with pytest.raises(RuntimeError, match="Non-finite ax_func input"):
        _run(3.0e-4, scenario=_scenario_nonfinite_ax(), t_end=0.02)


@pytest.mark.parametrize("bad_dt", [float("nan"), float("inf"), -float("inf"), 0.0, -1.0])
def test_worldroad_simulate_rejects_nonfinite_or_nonpositive_dt(bad_dt) -> None:
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
    }
    with pytest.raises(ValueError, match="dt must be finite and > 0"):
        m.simulate(params, _scenario(), dt=bad_dt, t_end=0.02, record_full=False)


@pytest.mark.parametrize("bad_t_end", [float("nan"), float("inf"), -float("inf")])
def test_worldroad_simulate_rejects_nonfinite_t_end(bad_t_end) -> None:
    with pytest.raises(ValueError, match="t_end must be finite"):
        _run(3.0e-4, scenario=_scenario(), t_end=bad_t_end)


def test_worldroad_raises_on_nonfinite_road_input_signal() -> None:
    with pytest.raises(RuntimeError, match="Non-finite road_func input"):
        _run(3.0e-4, scenario=_scenario_nonfinite_road(), t_end=0.02)


def test_worldroad_raises_on_nonfinite_state_after_substep(monkeypatch) -> None:
    def _nan_smooth_pos(x, eps):
        arr = np.asarray(x, dtype=float)
        out = np.full_like(arr, np.nan, dtype=float)
        if out.shape == ():
            return float("nan")
        return out

    monkeypatch.setattr(m, "smooth_pos", _nan_smooth_pos)
    with pytest.raises(RuntimeError, match="Non-finite gas mass state"):
        _run(
            3.0e-4,
            scenario=_scenario(),
            t_end=0.02,
            extra_params={"smooth_pressure_floor": True},
        )


def test_worldroad_ascii_dt_int_max_alias_has_priority_over_legacy_key() -> None:
    df_main, df_atm = _run(
        1.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={LEGACY_DT_INT_MAX_KEY: 5.0e-4},
    )
    hmax = float(np.nanmax(df_main.iloc[:, 3].to_numpy(dtype=float)))
    h_limit = 1.0e-4 * (1.0 + 1e-9) + 1e-15
    assert hmax <= h_limit
    row = df_atm.iloc[0]
    assert float(row["integrator_hmax_limit_s"]) == pytest.approx(
        h_limit,
        rel=1e-12,
        abs=1e-18,
    )


def test_worldroad_ascii_max_internal_steps_alias_has_priority_over_legacy_key() -> None:
    _, df_atm = _run(
        3.0e-3,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_max_internal_steps_per_dt": 7,
            LEGACY_MAX_INTERNAL_STEPS_KEY: 1000,
        },
    )
    row = df_atm.iloc[0]
    assert int(row["интегратор_max_internal_steps"]) == 7


@pytest.mark.parametrize("bad_steps", [float("nan"), float("inf"), -float("inf"), 0.0, -3.0, "bad"])
def test_worldroad_invalid_max_internal_steps_is_sanitized(bad_steps) -> None:
    _, df_atm = _run(
        3.0e-3,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_max_internal_steps_per_dt": bad_steps},
    )
    row = df_atm.iloc[0]
    if isinstance(bad_steps, str) or (isinstance(bad_steps, float) and (not np.isfinite(bad_steps))):
        expected_steps = 200000
    else:
        expected_steps = 1
    assert int(row["интегратор_max_internal_steps"]) == expected_steps


def test_worldroad_ascii_lim_rel_volume_alias_has_priority_over_legacy_key() -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={
            "integrator_lim_rel_volume_per_step": 0.02,
            LEGACY_LIM_REL_V_KEY: 0.30,
        },
    )
    row = df_atm.iloc[0]
    assert float(row["интегратор_lim_rel_V"]) == pytest.approx(0.02, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf"), 0.0, -0.1, "bad"])
def test_worldroad_invalid_lim_rel_volume_is_sanitized(bad_value) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_lim_rel_volume_per_step": bad_value},
    )
    row = df_atm.iloc[0]
    assert float(row["интегратор_lim_rel_V"]) == pytest.approx(0.05, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize(("raw_value", "expected"), [(1.0e-8, 1.0e-4), (1.0, 0.5)])
def test_worldroad_lim_rel_volume_is_clipped_to_physical_bounds(raw_value, expected) -> None:
    _, df_atm = _run(
        3.0e-4,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_lim_rel_volume_per_step": raw_value},
    )
    row = df_atm.iloc[0]
    assert float(row["интегратор_lim_rel_V"]) == pytest.approx(expected, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf"), -1.0e-3, 0.0, "bad"])
def test_worldroad_invalid_dt_int_max_falls_back_to_logging_dt(bad_value) -> None:
    dt = 2.0e-3
    df_main, df_atm = _run(
        dt,
        scenario=_scenario(),
        t_end=0.02,
        extra_params={"integrator_dt_int_max_s": bad_value},
    )
    hmax = float(np.nanmax(df_main.iloc[:, 3].to_numpy(dtype=float)))
    safe_default = dt
    h_limit = safe_default * (1.0 + 1e-9) + 1e-15
    assert hmax <= h_limit
    row = df_atm.iloc[0]
    assert float(row["integrator_hmax_limit_s"]) == pytest.approx(
        h_limit,
        rel=1e-12,
        abs=1e-18,
    )
