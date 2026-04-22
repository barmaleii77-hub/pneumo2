import numpy as np
import pytest

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m_cam
from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_r48_reference as m_r48


LEGACY_DT_INT_MAX_KEY = "\u043c\u0430\u043a\u0441_\u0448\u0430\u0433_\u0438\u043d\u0442\u0435\u0433\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f_\u0441"
LEGACY_MAX_INTERNAL_STEPS_KEY = "\u043c\u0430\u043a\u0441_\u0447\u0438\u0441\u043b\u043e_\u0432\u043d\u0443\u0442\u0440\u0435\u043d\u043d\u0438\u0445_\u0448\u0430\u0433\u043e\u0432_\u043d\u0430_dt"
LEGACY_LIM_REL_V_KEY = "\u043b\u0438\u043c\u0438\u0442_\u043e\u0442\u043d\u043e\u0441\u0438\u0442_\u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f_\u043e\u0431\u044a\u0451\u043c\u0430_\u0437\u0430_\u0448\u0430\u0433"
ATM_MAX_INTERNAL_STEPS_COL = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_max_internal_steps"
ATM_LIM_REL_V_COL = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_lim_rel_V"


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def _mk_scenario():
    return {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _mk_scenario_nonfinite_ax():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: float("nan"),
        "ay_func": lambda t: 0.0,
    }


def _mk_scenario_scalar_road():
    return {
        "road_func": lambda t: float(0.01 * np.sin(2.0 * np.pi * t)),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _mk_scenario_bad_road_shape():
    return {
        "road_func": lambda t: np.zeros(3, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _max_h(df):
    col_name = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_\u043f\u043e\u0434\u0448\u0430\u0433_\u043c\u0430\u043a\u0441_\u0441"
    if col_name in df.columns:
        a = df[col_name].to_numpy(dtype=float)
    elif df.shape[1] > 3:
        # Stable fallback by position: h_max is column #3 in integrator diagnostics block.
        a = df.iloc[:, 3].to_numpy(dtype=float)
    else:
        return None
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return float(a.max())


def _assert_runtime_qc_flags(df_main, df_atm, dt_int_max: float) -> None:
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

    assert int(row["integrator_active_rows_N"]) > 0
    assert float(row["integrator_hmax_limit_s"]) > 0.0
    assert int(row["integrator_hmax_violation_count"]) >= 0
    assert float(row["integrator_hmax_violation_max_over_s"]) >= 0.0
    assert float(row["integrator_reject_rate"]) >= 0.0
    assert int(row["solver_core_nonfinite_count"]) >= 0
    assert int(row["solver_pressure_nonfinite_count"]) >= 0
    assert np.isfinite(float(row["solver_pressure_min_pa"]))
    assert np.isfinite(float(row["solver_pressure_max_pa"]))
    assert float(row["solver_pressure_min_pa"]) > 0.0
    assert float(row["solver_pressure_max_pa"]) >= float(row["solver_pressure_min_pa"])
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

    nsub_col = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_\u043f\u043e\u0434\u0448\u0430\u0433\u0438_N"
    hmax_col = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_\u043f\u043e\u0434\u0448\u0430\u0433_\u043c\u0430\u043a\u0441_\u0441"
    if (nsub_col in df_main.columns) and (hmax_col in df_main.columns):
        nsub = df_main[nsub_col].to_numpy(dtype=float)
        hmax = df_main[hmax_col].to_numpy(dtype=float)
    else:
        nsub = df_main.iloc[:, 1].to_numpy(dtype=float)
        hmax = df_main.iloc[:, 3].to_numpy(dtype=float)
    mask = nsub > 0.0
    hmax_limit = float(dt_int_max) * (1.0 + 1e-9) + 1e-15
    if np.any(mask):
        assert int(row["integrator_hmax_violation_count"]) == int(np.sum(hmax[mask] > hmax_limit))


def test_camozzi_dt_int_max_logged_and_bounded():
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
    }

    df_main, *_, df_atm = m_cam.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)

    h = _max_h(df_main)
    assert h is not None
    assert h <= 3.0e-4 * (1.0 + 1e-9) + 1e-15
    nsub_col = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_\u043f\u043e\u0434\u0448\u0430\u0433\u0438_N"
    nsub_arr = df_main[nsub_col].to_numpy(dtype=float) if nsub_col in df_main.columns else df_main.iloc[:, 1].to_numpy(dtype=float)
    assert int(np.nanmax(nsub_arr)) >= 1
    _assert_runtime_qc_flags(df_main, df_atm, 3.0e-4)


def test_r48_reference_dt_int_max_logged_and_bounded():
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
    }

    df_main, *_, df_atm = m_r48.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)

    h = _max_h(df_main)
    assert h is not None
    assert h <= 3.0e-4 * (1.0 + 1e-9) + 1e-15
    nsub_col = "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440_\u043f\u043e\u0434\u0448\u0430\u0433\u0438_N"
    nsub_arr = df_main[nsub_col].to_numpy(dtype=float) if nsub_col in df_main.columns else df_main.iloc[:, 1].to_numpy(dtype=float)
    assert int(np.nanmax(nsub_arr)) >= 1
    _assert_runtime_qc_flags(df_main, df_atm, 3.0e-4)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_runtime_qc_strict_raises_when_pressure_threshold_is_unreachable(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
        "integrator_runtime_qc_strict": True,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_runtime_qc_strict_raises_when_pressure_ceiling_is_too_low(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
        "integrator_runtime_qc_strict": True,
        "integrator_runtime_qc_max_pressure_pa": 1.0,
    }
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_runtime_qc_invalid_string_params_are_safely_sanitized(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_min_pressure_pa": "bad",
        "integrator_runtime_qc_max_pressure_pa": "bad",
        "integrator_runtime_qc_max_reject_rate": "bad",
        "integrator_runtime_qc_max_mass_balance_residual_kg": "bad",
        "integrator_runtime_qc_max_mass_balance_residual_rel": "bad",
        "integrator_runtime_qc_require_active_rows": "false",
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == pytest.approx(0.0, rel=0.0, abs=0.0)
    assert np.isinf(float(row["integrator_runtime_qc_max_pressure_pa"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_reject_rate"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_kg"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_rel"]))
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 0
    assert int(row["integrator_runtime_qc_ok"]) == 1


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_runtime_qc_nan_and_negative_limits_are_safely_normalized(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_min_pressure_pa": float("nan"),
        "integrator_runtime_qc_max_reject_rate": -1.0,
        "integrator_runtime_qc_max_mass_balance_residual_kg": -1.0,
        "integrator_runtime_qc_max_mass_balance_residual_rel": -1.0,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == pytest.approx(0.0, rel=0.0, abs=0.0)
    assert np.isinf(float(row["integrator_runtime_qc_max_reject_rate"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_kg"]))
    assert np.isinf(float(row["integrator_runtime_qc_max_mass_balance_residual_rel"]))
    assert int(row["integrator_runtime_qc_ok"]) == 1


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize(("min_p_raw", "max_p_raw"), [(-1.0, 0.0), (-100.0, -5.0)])
def test_runtime_qc_finite_out_of_bounds_pressure_limits_are_safely_normalized(
    module_under_test, min_p_raw, max_p_raw
):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "integrator_runtime_qc_min_pressure_pa": min_p_raw,
        "integrator_runtime_qc_max_pressure_pa": max_p_raw,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert float(row["integrator_runtime_qc_min_pressure_req_pa"]) == pytest.approx(0.0, rel=0.0, abs=0.0)
    assert np.isinf(float(row["integrator_runtime_qc_max_pressure_pa"]))
    assert int(row["integrator_runtime_qc_ok"]) == 1


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("strict_token", ["false", "0", "no", "off"])
def test_runtime_qc_strict_false_tokens_do_not_raise(module_under_test, strict_token):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_strict": strict_token,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize(("strict_token", "must_raise"), [(" TRUE ", True), (" off ", False)])
def test_runtime_qc_strict_tokens_are_case_insensitive_and_trimmed(module_under_test, strict_token, must_raise):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_strict": strict_token,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    if must_raise:
        with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
            module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    else:
        _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
        row = df_atm.iloc[0]
        assert int(row["integrator_runtime_qc_ok"]) == 0
        assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize(("raw_value", "expected"), [(" FALSE ", 0), (" TrUe ", 1), (" maybe ", 1)])
def test_runtime_qc_require_active_rows_tokens_are_case_insensitive_and_default_safe(
    module_under_test, raw_value, expected
):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
        "integrator_runtime_qc_require_active_rows": raw_value,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == int(expected)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize(("raw_value", "expected"), [(0.0, 0), (1.0, 1), (float("nan"), 1)])
def test_runtime_qc_require_active_rows_numeric_values_are_parsed_predictably(
    module_under_test, raw_value, expected
):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
        "integrator_runtime_qc_require_active_rows": raw_value,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == int(expected)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_runtime_qc_bool_nan_values_fall_back_to_safe_defaults(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_strict": float("nan"),
        "integrator_runtime_qc_require_active_rows": float("nan"),
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("strict_raw", [float("inf"), -float("inf")])
def test_runtime_qc_strict_nonfinite_numeric_values_fall_back_to_false(module_under_test, strict_raw):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "integrator_runtime_qc_strict": strict_raw,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("require_raw", [float("inf"), -float("inf")])
def test_runtime_qc_require_active_rows_nonfinite_numeric_values_fall_back_to_default_true(
    module_under_test, require_raw
):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "integrator_runtime_qc_require_active_rows": require_raw,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_runtime_qc_bool_nonscalar_values_fall_back_to_safe_defaults(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_strict": [1],
        "integrator_runtime_qc_require_active_rows": [0],
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("strict_token", ["true", "1", "yes", "on"])
def test_runtime_qc_strict_true_tokens_raise(module_under_test, strict_token):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "integrator_runtime_qc_strict": strict_token,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("strict_raw", [0.0])
def test_runtime_qc_strict_zero_numeric_value_falls_back_to_false(module_under_test, strict_raw):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
        "integrator_runtime_qc_strict": strict_raw,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert "pressure_min_pa" in str(row["integrator_runtime_qc_msg"])


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("strict_raw", [1.0, -1.0, 1.0e-12])
def test_runtime_qc_strict_nonzero_numeric_values_enable_strict_mode(module_under_test, strict_raw):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
        "integrator_runtime_qc_strict": strict_raw,
        "integrator_runtime_qc_min_pressure_pa": 1.0e9,
    }
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_zero_duration_runtime_qc_requires_active_rows_by_default(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
    }
    df_main, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.0, record_full=False)
    row = df_atm.iloc[0]
    assert len(df_main) == 1
    assert int(row["integrator_active_rows_N"]) == 0
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 1
    assert int(row["integrator_runtime_qc_ok"]) == 0
    assert str(row["integrator_runtime_qc_msg"]) == "no_active_integrator_rows"


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_zero_duration_runtime_qc_can_disable_active_rows_requirement(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
        "integrator_runtime_qc_require_active_rows": False,
    }
    df_main, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.0, record_full=False)
    row = df_atm.iloc[0]
    assert len(df_main) == 1
    assert int(row["integrator_active_rows_N"]) == 0
    assert int(row["integrator_runtime_qc_require_active_rows"]) == 0
    assert int(row["integrator_runtime_qc_ok"]) == 1
    assert str(row["integrator_runtime_qc_msg"]) == "ok"


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_zero_duration_runtime_qc_strict_raises_unless_active_rows_requirement_is_disabled(module_under_test):
    scenario = _mk_scenario()
    base_params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
        "integrator_runtime_qc_strict": True,
    }
    with pytest.raises(AssertionError, match="integrator_runtime_qc_strict"):
        module_under_test.simulate(dict(base_params), scenario, dt=2e-3, t_end=0.0, record_full=False)

    params_relaxed = dict(base_params)
    params_relaxed["integrator_runtime_qc_require_active_rows"] = False
    module_under_test.simulate(params_relaxed, scenario, dt=2e-3, t_end=0.0, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_integrator_raises_on_nonfinite_state_from_input_signal(module_under_test):
    scenario = _mk_scenario_nonfinite_ax()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
    }
    with pytest.raises(RuntimeError, match="Non-finite"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("bad_dt", [float("nan"), float("inf"), -float("inf"), 0.0, -1.0])
def test_simulate_rejects_nonfinite_or_nonpositive_dt(module_under_test, bad_dt):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
    }
    with pytest.raises(ValueError, match="dt must be finite and > 0"):
        module_under_test.simulate(params, scenario, dt=bad_dt, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("bad_t_end", [float("nan"), float("inf"), -float("inf")])
def test_simulate_rejects_nonfinite_t_end(module_under_test, bad_t_end):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "РїСЂСѓР¶РёРЅР°_РїСЂРµРґРЅР°С‚СЏРі_РЅР°_РѕС‚Р±РѕРµ_СЃС‚СЂРѕРіРѕ": False,
    }
    with pytest.raises(ValueError, match="t_end must be finite"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=bad_t_end, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_integrator_accepts_scalar_road_input(module_under_test):
    scenario = _mk_scenario_scalar_road()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    df_main, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    h = _max_h(df_main)
    assert h is not None
    assert np.isfinite(h)
    row = df_atm.iloc[0]
    assert int(row["solver_core_finite_ok"]) == 1
    assert int(row["solver_pressure_finite_ok"]) == 1
    assert float(row["solver_pressure_min_pa"]) > 0.0


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_integrator_raises_on_invalid_road_shape(module_under_test):
    scenario = _mk_scenario_bad_road_shape()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    with pytest.raises(RuntimeError, match="must return 4 values"):
        module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_integrator_ascii_dt_int_max_alias_has_priority_over_legacy_key(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 1.0e-4,
        LEGACY_DT_INT_MAX_KEY: 5.0e-4,
    }
    df_main, *_ = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    h = _max_h(df_main)
    assert h is not None
    assert h <= 1.0e-4 * (1.0 + 1e-9) + 1e-15


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_integrator_ascii_max_internal_steps_alias_has_priority_over_legacy_key(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-3,
        "integrator_max_internal_steps_per_dt": 7,
        LEGACY_MAX_INTERNAL_STEPS_KEY: 1000,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert ATM_MAX_INTERNAL_STEPS_COL in df_atm.columns
    assert int(row[ATM_MAX_INTERNAL_STEPS_COL]) == 7


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
def test_integrator_ascii_lim_rel_volume_alias_has_priority_over_legacy_key(module_under_test):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "integrator_lim_rel_volume_per_step": 0.02,
        LEGACY_LIM_REL_V_KEY: 0.30,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert ATM_LIM_REL_V_COL in df_atm.columns
    assert float(row[ATM_LIM_REL_V_COL]) == pytest.approx(0.02, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf"), -1.0e-3, 0.0, "bad"])
def test_integrator_invalid_dt_int_max_falls_back_to_safe_default(module_under_test, bad_value):
    scenario = _mk_scenario()
    dt = 2e-3
    safe_default = min(5.0e-4, dt)
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": bad_value,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    df_main, *_, df_atm = module_under_test.simulate(params, scenario, dt=dt, t_end=0.02, record_full=False)
    h = _max_h(df_main)
    assert h is not None
    assert h <= safe_default * (1.0 + 1e-9) + 1e-15
    row = df_atm.iloc[0]
    assert float(row["integrator_hmax_limit_s"]) == pytest.approx(
        safe_default * (1.0 + 1e-9) + 1e-15,
        rel=1e-12,
        abs=1e-18,
    )


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("bad_steps", [float("nan"), float("inf"), -float("inf"), 0.0, -3.0, "bad"])
def test_integrator_invalid_max_internal_steps_is_sanitized(module_under_test, bad_steps):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        # Keep dt_int_max above dt so this test isolates max_internal_steps sanitization
        # instead of triggering an intentional substep-overflow runtime error.
        "integrator_dt_int_max_s": 3.0e-3,
        "integrator_max_internal_steps_per_dt": bad_steps,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    df_main, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    h = _max_h(df_main)
    assert h is not None
    assert np.isfinite(h)
    row = df_atm.iloc[0]
    assert ATM_MAX_INTERNAL_STEPS_COL in df_atm.columns
    if isinstance(bad_steps, str) or (isinstance(bad_steps, float) and (not np.isfinite(bad_steps))):
        expected_steps = 500000
    else:
        expected_steps = 1
    assert int(row[ATM_MAX_INTERNAL_STEPS_COL]) == expected_steps


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf"), 0.0, -0.1, "bad"])
def test_integrator_invalid_lim_rel_volume_is_sanitized(module_under_test, bad_value):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "integrator_lim_rel_volume_per_step": bad_value,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert ATM_LIM_REL_V_COL in df_atm.columns
    assert float(row[ATM_LIM_REL_V_COL]) == pytest.approx(0.05, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("module_under_test", [m_cam, m_r48])
@pytest.mark.parametrize(("raw_value", "expected"), [(1.0e-8, 1.0e-4), (1.0, 0.5)])
def test_integrator_lim_rel_volume_is_clipped_to_physical_bounds(module_under_test, raw_value, expected):
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "integrator_dt_int_max_s": 3.0e-4,
        "integrator_lim_rel_volume_per_step": raw_value,
        "пружина_преднатяг_на_отбое_строго": False,
    }
    _, *_, df_atm = module_under_test.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)
    row = df_atm.iloc[0]
    assert ATM_LIM_REL_V_COL in df_atm.columns
    assert float(row[ATM_LIM_REL_V_COL]) == pytest.approx(expected, rel=1e-12, abs=1e-15)
