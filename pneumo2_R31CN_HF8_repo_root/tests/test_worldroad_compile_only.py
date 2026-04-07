# -*- coding: utf-8 -*-

import numpy as np


def test_worldroad_compile_only_core_ok():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
    }
    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    ctx = m.simulate(params, test, dt=1e-3, t_end=0.0, record_full=False, compile_only=True)

    assert isinstance(ctx, dict)
    assert 'state0' in ctx and 'rhs' in ctx and 'rk2_step' in ctx and 'observe' in ctx

    s0 = ctx['state0']
    ds0 = ctx['rhs'](s0.copy(), 0.0)
    assert ds0.shape == s0.shape

    s1 = ctx['rk2_step'](s0.copy(), 0.0, float(ctx['dt']))
    assert np.all(np.isfinite(s1))

    obs = ctx['observe'](s0.copy(), 0.0)
    assert 'F_tire' in obs and np.asarray(obs['F_tire']).shape == (4,)
