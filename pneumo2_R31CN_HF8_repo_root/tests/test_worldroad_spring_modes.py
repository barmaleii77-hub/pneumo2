# -*- coding: utf-8 -*-

import numpy as np


def test_worldroad_spring_pchip_per_corner_smoke():
    """Опциональные режимы не должны ломать статическую инициализацию."""
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'spring_interp_mode': 'pchip',
        'spring_x0_mode': 'per_corner',
        'mechanics_selfcheck': True,
    }

    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=1e-3, t_end=0.0, record_full=False
    )

    assert int(df_atm.loc[0, 'mech_selfcheck_ok']) == 1

    # Должны появиться расширенные метрики геометрии
    assert float(df_atm.loc[0, 'mech_selfcheck_err_wheel_contact_m']) <= 1e-9
    assert float(df_atm.loc[0, 'mech_selfcheck_err_tire_pen_m']) <= 1e-9


def test_worldroad_dual_spring_runtime_exports_explicit_family_columns():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'механика_пружина_режим': 'dual',
        'пружина_преднатяг_на_отбое_строго': False,
        'spring_interp_mode': 'pchip',
        'spring_x0_mode': 'per_corner',
        'mechanics_selfcheck': True,
        'пружина_Ц1_перед_масштаб': 1.1,
        'пружина_Ц1_зад_масштаб': 1.2,
        'пружина_Ц2_перед_масштаб': 1.3,
        'пружина_Ц2_зад_масштаб': 1.4,
    }
    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=1e-3, t_end=0.0, record_full=False
    )

    assert int(df_atm.loc[0, 'mech_selfcheck_ok']) == 1
    assert float(df_main.loc[0, 'пружина_режим_семейства_id']) == 3.0
    assert float(df_main.loc[0, 'пружина_Ц1_ЛП_активна']) == 1.0
    assert float(df_main.loc[0, 'пружина_Ц2_ЛП_активна']) == 1.0
    assert np.isfinite(float(df_main.loc[0, 'пружина_Ц1_ЛП_длина_м']))
    assert np.isfinite(float(df_main.loc[0, 'пружина_Ц2_ЛП_длина_м']))
