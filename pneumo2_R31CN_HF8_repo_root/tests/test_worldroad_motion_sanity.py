# -*- coding: utf-8 -*-

import numpy as np


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    """C1-бамп: 0 -> A на интервале [t0, t0+dur] с нулевой производной на концах."""
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def test_worldroad_motion_selfcheck_ok():
    """Проверяем, что при движении сохраняются тождества колесо/рама/дорога и кинематика штоков."""
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,
        # чуть ослабим допуск в тесте, но оставим микрометровый уровень
        'mechanics_selfcheck_tol_m': 1e-6,
    }

    test = {
        'road_func': lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=2e-3, t_end=0.05, record_full=False
    )

    assert int(df_atm.loc[0, 'mech_selfcheck_ok']) == 1
    assert float(df_atm.loc[0, 'mech_selfcheck_err_wheel_frame_m']) <= 1e-6
    assert float(df_atm.loc[0, 'mech_selfcheck_err_wheel_road_m']) <= 1e-6
    assert float(df_atm.loc[0, 'mech_selfcheck_err_stroke_C1_m']) <= 1e-6
    assert float(df_atm.loc[0, 'mech_selfcheck_err_stroke_C2_m']) <= 1e-6

    # rel0(t0) должен быть около 0
    if 'mech_selfcheck_rel0_t0_maxabs' in df_atm.columns:
        assert float(df_atm.loc[0, 'mech_selfcheck_rel0_t0_maxabs']) <= 1e-9


def test_worldroad_exports_world_xy_path_when_yaw_is_nonzero():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,
    }
    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.8 if t > 0.05 else 0.0,
        'vx0_м_с': 8.0,
    }

    df_main, *_ = m.simulate(params, test, dt=2e-3, t_end=0.20, record_full=False)

    assert 'скорость_vy_м_с' in df_main.columns
    assert 'путь_y_м' in df_main.columns
    assert np.all(np.isfinite(np.asarray(df_main['скорость_vy_м_с'], dtype=float)))
    assert np.all(np.isfinite(np.asarray(df_main['путь_y_м'], dtype=float)))
    assert abs(float(df_main['путь_y_м'].iloc[-1])) > 1e-6
