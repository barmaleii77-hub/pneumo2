import numpy as np

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m_cam
from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_r48_reference as m_r48


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    """Гладкий подъём дороги: 0 -> A за dur, далее держим A."""
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def _mk_scenario():
    return {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def _max_h(df):
    if 'интегратор_подшаг_макс_с' not in df.columns:
        return None
    a = df['интегратор_подшаг_макс_с'].to_numpy(dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return float(a.max())


def test_camozzi_dt_int_max_logged_and_bounded():
    """Инвариант: max внутренний шаг не превышает `макс_шаг_интегрирования_с` (Camozzi model)."""
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
    }

    df_main, *_ = m_cam.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)

    h = _max_h(df_main)
    assert h is not None
    assert h <= 3.0e-4 * (1.0 + 1e-9) + 1e-15

    # хотя бы где-то были подшаги
    assert int(df_main['интегратор_подшаги_N'].max()) >= 1


def test_r48_reference_dt_int_max_logged_and_bounded():
    """Инвариант: max внутренний шаг не превышает `макс_шаг_интегрирования_с` (R48 reference model)."""
    scenario = _mk_scenario()
    params = {
        "mechanics_selfcheck": False,
        "пружина_преднатяг_на_отбое_строго": False,
        "макс_шаг_интегрирования_с": 3.0e-4,
    }

    df_main, *_ = m_r48.simulate(params, scenario, dt=2e-3, t_end=0.02, record_full=False)

    h = _max_h(df_main)
    assert h is not None
    assert h <= 3.0e-4 * (1.0 + 1e-9) + 1e-15

    assert int(df_main['интегратор_подшаги_N'].max()) >= 1
