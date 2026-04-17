# -*- coding: utf-8 -*-

import numpy as np


BODY_HEIGHT_COLS = [
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041b\u041f_z_\u043c",
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041f\u041f_z_\u043c",
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041b\u0417_z_\u043c",
    "\u0440\u0430\u043c\u0430_\u0443\u0433\u043e\u043b_\u041f\u0417_z_\u043c",
]

LEFT_HEIGHT_PATTERN_M = np.array([0.002, 0.0, 0.002, 0.0], dtype=float)


def _flat_test_case():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _run_with_pressure_trim_target(mod, extra_params=None, *, enable_pressure_trim: bool):
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

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    return df_atm.loc[0]


def test_worldroad_static_trim_pressure_trim_reduces_height_error():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    row_off = _run_with_pressure_trim_target(m, enable_pressure_trim=False)
    row_on = _run_with_pressure_trim_target(m, enable_pressure_trim=True)

    err_off = float(row_off["static_trim_body_height_err_max_m"])
    err_on = float(row_on["static_trim_body_height_err_max_m"])

    assert int(row_off["static_trim_success"]) == 1
    assert int(row_on["static_trim_success"]) == 1
    assert int(row_off["static_trim_pressure_trim_enable"]) == 0
    assert int(row_on["static_trim_pressure_trim_enable"]) == 1
    assert str(row_off["static_trim_pressure_trim_mode"]) == "off"
    assert str(row_on["static_trim_pressure_trim_mode"]) == "per_corner"
    assert err_on < err_off
    assert (err_off - err_on) > 1e-4
    assert float(row_on["static_trim_pressure_trim_max_abs_scale_delta"]) > 1e-2


def test_camozzi_static_trim_pressure_trim_reduces_height_error():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    extra = {"\u043a\u0438\u043d\u0435\u043c\u0430\u0442\u0438\u043a\u0430_\u0440\u0435\u0436\u0438\u043c": "dw2d_mounts"}
    row_off = _run_with_pressure_trim_target(m, extra_params=extra, enable_pressure_trim=False)
    row_on = _run_with_pressure_trim_target(m, extra_params=extra, enable_pressure_trim=True)

    err_off = float(row_off["static_trim_body_height_err_max_m"])
    err_on = float(row_on["static_trim_body_height_err_max_m"])

    assert int(row_off["static_trim_success"]) == 1
    assert int(row_on["static_trim_success"]) == 1
    assert int(row_off["static_trim_pressure_trim_enable"]) == 0
    assert int(row_on["static_trim_pressure_trim_enable"]) == 1
    assert str(row_off["static_trim_pressure_trim_mode"]) == "off"
    assert str(row_on["static_trim_pressure_trim_mode"]) == "per_corner"
    if err_on >= err_off:
        assert float(row_on["static_trim_max_abs_res"]) < float(row_off["static_trim_max_abs_res"])
    else:
        assert (err_off - err_on) > 1e-4
    assert float(row_on["static_trim_pressure_trim_max_abs_scale_delta"]) > 1e-2
