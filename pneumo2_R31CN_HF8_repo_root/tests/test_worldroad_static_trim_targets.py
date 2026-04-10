# -*- coding: utf-8 -*-

import numpy as np


def _flat_test_case():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def test_worldroad_static_trim_coil_target_improves_coil_bind_margin():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    base_params = {
        "static_trim_force": True,
        "static_trim_target_midstroke_enable": False,
        "static_trim_target_spring_gap_enable": False,
        "пружина_длина_солид_м": 0.285,
        "пружина_запас_до_coil_bind_минимум_м": 0.03,
    }

    rows = {}
    for enabled in (False, True):
        params = dict(base_params)
        params["static_trim_target_spring_coil_enable"] = enabled
        df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
            params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
        )
        rows[enabled] = df_atm.loc[0]

    assert int(rows[False]["static_trim_success"]) == 1
    assert int(rows[True]["static_trim_success"]) == 1
    assert int(rows[False]["static_trim_applied"]) == 1
    assert int(rows[True]["static_trim_applied"]) == 1
    assert int(rows[False]["static_trim_target_spring_coil_enable"]) == 0
    assert int(rows[True]["static_trim_target_spring_coil_enable"]) == 1
    assert float(rows[False]["static_trim_coil_margin0_min_m"]) < 0.0
    assert float(rows[True]["static_trim_coil_margin_min_m"]) > float(rows[False]["static_trim_coil_margin_min_m"])
