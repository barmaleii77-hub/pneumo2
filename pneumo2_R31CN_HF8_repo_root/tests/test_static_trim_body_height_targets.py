# -*- coding: utf-8 -*-

import numpy as np


BODY_HEIGHT_COLS = [
    "рама_угол_ЛП_z_м",
    "рама_угол_ПП_z_м",
    "рама_угол_ЛЗ_z_м",
    "рама_угол_ПЗ_z_м",
]


def _flat_test_case():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _run_with_body_height_target(mod, extra_params=None, *, enable_target: bool):
    base_params = {
        "static_trim_force": True,
        "static_trim_target_midstroke_enable": False,
        "static_trim_target_spring_gap_enable": False,
        "static_trim_target_spring_coil_enable": False,
    }
    if extra_params:
        base_params.update(extra_params)

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        base_params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    target = [float(df_main.loc[0, col]) + 0.015 for col in BODY_HEIGHT_COLS]

    params = dict(base_params)
    params["static_trim_target_body_height_m"] = target
    params["static_trim_target_body_height_enable"] = enable_target
    params["static_trim_scale_body_height_m"] = 0.005

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = mod.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )
    return df_atm.loc[0]


def test_worldroad_static_trim_body_height_target_reduces_height_error():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    row_off = _run_with_body_height_target(m, enable_target=False)
    row_on = _run_with_body_height_target(m, enable_target=True)

    assert int(row_off["static_trim_success"]) == 1
    assert int(row_on["static_trim_success"]) == 1
    assert int(row_off["static_trim_target_body_height_enable"]) == 0
    assert int(row_on["static_trim_target_body_height_enable"]) == 1
    assert float(row_off["static_trim_body_height_err_max_m"]) > 0.01
    assert float(row_on["static_trim_body_height_err_max_m"]) < float(row_off["static_trim_body_height_err_max_m"])


def test_camozzi_static_trim_body_height_target_reduces_height_error():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    extra = {"кинематика_режим": "dw2d_mounts"}
    row_off = _run_with_body_height_target(m, extra_params=extra, enable_target=False)
    row_on = _run_with_body_height_target(m, extra_params=extra, enable_target=True)

    assert int(row_off["static_trim_success"]) == 1
    assert int(row_on["static_trim_success"]) == 1
    assert int(row_off["static_trim_target_body_height_enable"]) == 0
    assert int(row_on["static_trim_target_body_height_enable"]) == 1
    assert float(row_off["static_trim_body_height_err_max_m"]) > 0.01
    assert float(row_on["static_trim_body_height_err_max_m"]) < float(row_off["static_trim_body_height_err_max_m"])
