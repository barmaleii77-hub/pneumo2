# -*- coding: utf-8 -*-

import numpy as np


def _flat_test_case():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def test_camozzi_static_trim_midstroke_target_reduces_trim_drift():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    base_params = {
        "static_trim_force": True,
        "кинематика_режим": "dw2d_mounts",
        "static_trim_target_spring_gap_enable": False,
        "static_trim_target_spring_coil_enable": False,
    }

    rows = {}
    for enabled in (False, True):
        params = dict(base_params)
        params["static_trim_target_midstroke_enable"] = enabled
        df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
            params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
        )
        rows[enabled] = df_atm.loc[0]

    assert int(rows[False]["static_trim_success"]) == 1
    assert int(rows[True]["static_trim_success"]) == 1
    assert int(rows[False]["static_trim_applied"]) == 1
    assert int(rows[True]["static_trim_applied"]) == 1
    assert int(rows[False]["static_trim_target_midstroke_enable"]) == 0
    assert int(rows[True]["static_trim_target_midstroke_enable"]) == 1
    assert float(rows[False]["static_trim_midstroke_err0_max_m"]) == 0.0
    assert float(rows[True]["static_trim_midstroke_err_max_m"]) < float(rows[False]["static_trim_midstroke_err_max_m"])
