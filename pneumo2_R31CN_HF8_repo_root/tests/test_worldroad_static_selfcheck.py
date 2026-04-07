import numpy as np


def test_worldroad_static_selfcheck_ok():
    # Быстрый smoke‑тест: при плоской дороге и нулевых ускорениях система должна стартовать в статическом равновесии.
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        # важно: мы НЕ форсим преднатяг на полном отбое, иначе нулевая поза может потерять статическое равновесие
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,
    }

    test = {
        'road_func': lambda t: np.zeros(4),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    # t_end=0 → один шаг, но selfcheck проверяет t=0 через rhs(state0,0)
    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=1e-3, t_end=0.0, record_full=False
    )

    assert int(df_atm.loc[0, 'mech_selfcheck_ok']) == 1
    assert int(df_atm.loc[0, 'mech_selfcheck_t0_static_checked']) == 1
    assert abs(float(df_atm.loc[0, 'mech_selfcheck_t0_z_ddot_m_s2'])) <= 1e-9
    assert abs(float(df_atm.loc[0, 'mech_selfcheck_t0_wheel_ddot_max_m_s2'])) <= 1e-9
