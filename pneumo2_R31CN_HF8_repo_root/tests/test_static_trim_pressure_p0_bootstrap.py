# -*- coding: utf-8 -*-

import json
import numpy as np

from pneumo_solver_ui.suspension_family_contract import cylinder_precharge_key


BODY_HEIGHT_COLS = [
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041b\u041f_z_\u043c",
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041f\u041f_z_\u043c",
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041b\u0417_z_\u043c",
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041f\u0417_z_\u043c",
]

LEFT_HEIGHT_PATTERN_M = np.array([0.002, 0.0, 0.002, 0.0], dtype=float)
KIN_MODE_KEY = "\u043a\u0438\u043d\u0435\u043c\u0430\u0442\u0438\u043a\u0430_\u0440\u0435\u0436\u0438\u043c"


def _flat_test_case():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _run_target_case(
    mod,
    extra_params=None,
    *,
    enable_pressure_trim: bool,
    precharge_override=None,
    bootstrap_rerun: bool = False,
):
    base_params = {
        "static_trim_force": True,
        "static_trim_target_midstroke_enable": False,
        "static_trim_target_spring_gap_enable": False,
        "static_trim_target_spring_coil_enable": False,
        "static_trim_bound_z_m": 0.001,
        "static_trim_bound_zw_m": 0.001,
        "static_trim_bound_angle_rad": 0.01,
        "static_trim_scale_body_height_m": 0.001,
        "static_trim_pressure_trim_mode": "per_corner",
        "static_trim_pressure_trim_reg_scale": 100.0,
        "static_trim_pressure_trim_max_scale": 50.0,
    }
    if extra_params:
        base_params.update(extra_params)

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        base_params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    target = (
        np.array([float(df_main.loc[0, col]) for col in BODY_HEIGHT_COLS], dtype=float)
        + LEFT_HEIGHT_PATTERN_M
    ).tolist()

    params = dict(base_params)
    params["static_trim_target_body_height_m"] = target
    params["static_trim_target_body_height_enable"] = True
    params["static_trim_pressure_trim_enable"] = enable_pressure_trim
    if precharge_override is not None:
        params["precharge_override"] = dict(precharge_override)
    if bootstrap_rerun:
        params["static_trim_pressure_trim_bootstrap_rerun"] = True

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    return df_atm.loc[0]


def _assert_explicit_and_bootstrap_flow(mod, extra_params=None):
    row_off = _run_target_case(mod, extra_params, enable_pressure_trim=False)
    row_learn = _run_target_case(mod, extra_params, enable_pressure_trim=True)

    err_off = float(row_off["static_trim_body_height_err_max_m"])
    err_learn = float(row_learn["static_trim_body_height_err_max_m"])
    precharge_override = json.loads(str(row_learn["static_trim_pressure_trim_precharge_override_json"]))

    assert int(row_off["static_trim_success"]) == 1
    assert int(row_learn["static_trim_success"]) == 1
    assert isinstance(precharge_override, dict)
    assert len(precharge_override) > 0
    assert err_learn < err_off

    row_apply = _run_target_case(
        mod,
        extra_params,
        enable_pressure_trim=False,
        precharge_override=precharge_override,
    )
    err_apply = float(row_apply["static_trim_body_height_err_max_m"])

    assert int(row_apply["static_trim_success"]) == 1
    assert int(row_apply["precharge_override_applied"]) > 0
    assert err_apply < err_off

    row_boot = _run_target_case(
        mod,
        extra_params,
        enable_pressure_trim=True,
        bootstrap_rerun=True,
    )
    err_boot = float(row_boot["static_trim_body_height_err_max_m"])

    assert int(row_boot["static_trim_success"]) == 1
    assert int(row_boot["static_trim_pressure_trim_bootstrap_applied"]) == 1
    assert int(row_boot["precharge_override_applied"]) > 0
    assert err_boot < err_off


def _assert_precharge_policy_contract(mod, extra_params=None):
    params = {
        "precharge_override": {
            "C1_CAP": {"front": "2.2bar", "rear": "2.1bar"},
            "C2": {"ROD": {"LP": "1.2bar", "PP": "1.3bar", "LZ": "1.4bar", "PZ": "1.5bar"}},
        },
    }
    if extra_params:
        params.update(extra_params)

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    row = df_atm.loc[0]
    rep = json.loads(str(row["precharge_override_json"]))

    assert int(row["precharge_override_applied"]) == 8
    assert int(row["precharge_override_errors"]) == 0
    assert isinstance(rep, dict)
    assert isinstance(rep.get("normalized_policy", {}), dict)
    assert "C1" in rep.get("normalized_policy", {})
    assert "C2" in rep.get("normalized_policy", {})


def _assert_family_precharge_contract(mod, extra_params=None):
    params = {
        cylinder_precharge_key("Ц1", "CAP", "перед"): "2.2bar",
        cylinder_precharge_key("Ц1", "CAP", "зад"): "2.1bar",
        cylinder_precharge_key("Ц2", "ROD", "перед"): "1.2bar",
        cylinder_precharge_key("Ц2", "ROD", "зад"): "1.4bar",
    }
    if extra_params:
        params.update(extra_params)

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    row = df_atm.loc[0]
    rep = json.loads(str(row["precharge_override_json"]))

    assert int(row["precharge_override_applied"]) == 8
    assert int(row["precharge_override_errors"]) == 0
    assert isinstance(rep, dict)
    assert np.isclose(rep.get("family_policy", {}).get("C1", {}).get("CAP", {}).get("front"), 220000.0)
    assert np.isclose(rep.get("family_policy", {}).get("C1", {}).get("CAP", {}).get("rear"), 210000.0)
    assert np.isclose(rep.get("family_policy", {}).get("C2", {}).get("ROD", {}).get("front"), 120000.0)
    assert np.isclose(rep.get("family_policy", {}).get("C2", {}).get("ROD", {}).get("rear"), 140000.0)


def test_worldroad_static_trim_pressure_trim_exports_precharge_override_and_bootstraps():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    _assert_explicit_and_bootstrap_flow(m)
    _assert_precharge_policy_contract(m)
    _assert_family_precharge_contract(m)


def test_camozzi_static_trim_pressure_trim_exports_precharge_override_and_bootstraps():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    _assert_explicit_and_bootstrap_flow(
        m,
        extra_params={KIN_MODE_KEY: "dw2d_mounts"},
    )
    _assert_precharge_policy_contract(
        m,
        extra_params={KIN_MODE_KEY: "dw2d_mounts"},
    )
    _assert_family_precharge_contract(
        m,
        extra_params={KIN_MODE_KEY: "dw2d_mounts"},
    )
