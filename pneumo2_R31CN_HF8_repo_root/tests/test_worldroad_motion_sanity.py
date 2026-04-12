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


def test_worldroad_exports_force_breakdown_without_mechanical_arb():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'стабилизатор_вкл': False,
    }
    test = {
        'road_func': lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, *_ = m.simulate(params, test, dt=2e-3, t_end=0.05, record_full=False)

    expected_cols = [
        'сила_подвески_ЛП_Н',
        'сила_подвески_итого_Н',
        'сила_пружины_ЛП_Н',
        'сила_пружины_итого_Н',
        'сила_пневматики_ЛП_Н',
        'сила_пневматики_итого_Н',
        'сила_пневматики_Ц1_ЛП_Н',
        'сила_пневматики_Ц2_ЛП_Н',
        'сила_отбойника_ЛП_Н',
        'момент_крен_подвеска_Нм',
        'момент_тангаж_итого_Нм',
    ]
    for col in expected_cols:
        assert col in df_main.columns
        vals = np.asarray(df_main[col], dtype=float)
        assert np.all(np.isfinite(vals))

    assert np.allclose(np.asarray(df_main['сила_стабилизатора_перед_Н'], dtype=float), 0.0)
    assert np.allclose(np.asarray(df_main['сила_стабилизатора_зад_Н'], dtype=float), 0.0)


def test_worldroad_default_diagonal_antiphase_keeps_energy_in_stabilizing_branch():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    A = 0.015
    w = 2.0 * np.pi * 1.5
    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'стабилизатор_вкл': False,
    }
    test = {
        # Canonical diagonal: right-front + left-rear.
        'road_func': lambda t: np.array([0.0, A * np.sin(w * t), -A * np.sin(w * t), 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    _, _, df_energy, _, _, df_energy_edges, _, _ = m.simulate(
        params, test, dt=5e-3, t_end=4.0, record_full=False
    )

    diag_mask = df_energy['дроссель'].astype(str).str.contains('дроссель‑диагональ‑Ц2', regex=False)
    exh_mask = df_energy_edges['элемент'].astype(str).str.contains('дроссель_выхлоп_', regex=False)
    diag_energy = float(df_energy.loc[diag_mask, 'энергия_рассеяна_Дж'].sum())
    exhaust_energy = float(df_energy_edges.loc[exh_mask, 'энергия_Дж'].sum())

    assert diag_energy > 0.0
    assert exhaust_energy >= 0.0
    assert diag_energy > exhaust_energy * 1.25
