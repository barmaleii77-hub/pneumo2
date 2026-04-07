# -*- coding: utf-8 -*-

import json
import numpy as np


def test_worldroad_p0_override_applied_count():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': False,
        'p0_override': {
            'Ресивер2': '2.0bar',
            'Аккумулятор': 1.0e6,
        },
    }

    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=1e-3, t_end=0.0, record_full=False
    )

    assert int(df_atm.loc[0, 'p0_override_applied']) == 2

    rep = json.loads(str(df_atm.loc[0, 'p0_override_json']))
    assert isinstance(rep, dict)
    assert len(rep.get('applied', [])) == 2
