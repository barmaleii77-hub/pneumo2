import numpy as np


def test_compile_only_returns_ctx_and_observe_consistent():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'compile_only': True,
        'mechanics_selfcheck': False,
    }

    test = {
        'road_func': lambda t: np.zeros(4),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    ctx = m.simulate(params, test, dt=1e-3, t_end=0.0, record_full=False, compile_only=True)

    assert isinstance(ctx, dict)
    for k in ['state0', 'rhs', 'rk2_step', 'observe', 'wheel_radius_m', 'wheel_coord_mode']:
        assert k in ctx

    state0 = ctx['state0']
    assert isinstance(state0, np.ndarray)

    obs0 = ctx['observe'](state0, 0.0)
    for k in ['zw_center', 'z_road', 'tire_pen_m']:
        assert k in obs0

    zw_center = np.asarray(obs0['zw_center'], dtype=float).reshape(-1)
    z_road = np.asarray(obs0['z_road'], dtype=float).reshape(-1)
    pen = np.asarray(obs0['tire_pen_m'], dtype=float).reshape(-1)

    assert zw_center.size == 4
    assert z_road.size == 4
    assert pen.size == 4

    R = float(ctx['wheel_radius_m'])
    # penetration is computed relative to wheel contact point
    pen_expected = z_road - (zw_center - R)
    assert np.allclose(pen, pen_expected, atol=1e-9, rtol=0.0)

    # One RK2 step should return a state vector of the same shape
    st1 = ctx['rk2_step'](state0, 0.0, 1e-3)
    assert isinstance(st1, np.ndarray)
    assert st1.shape == state0.shape
