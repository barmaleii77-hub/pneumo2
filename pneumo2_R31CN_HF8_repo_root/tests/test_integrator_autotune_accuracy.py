import numpy as np

from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    """Гладкий подъём дороги: 0 -> A за dur, далее держим A."""
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def test_integrator_dt_int_max_convergence_worldroad():
    """Проверка, что уменьшение max внутреннего шага действительно повышает точность.

    Мы ожидаем, что при RK2 (Heun) ошибка убывает при уменьшении h.
    Тест не требует идеального порядка 2 (модель нелинейная и с проекциями),
    но должен показать устойчивую тенденцию: mid лучше coarse.
    """

    scenario = {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }

    base_params = {
        # держим самопроверку включённой, чтобы тест ловил регрессии механики
        "mechanics_selfcheck": True,
        "mechanics_selfcheck_tol_m": 1e-6,
        # не требуем строгого преднатяга (в некоторых режимах может давать дискретности)
        "пружина_преднатяг_на_отбое_строго": False,
    }

    def run(dt_int_max: float):
        params = dict(base_params)
        params["макс_шаг_интегрирования_с"] = float(dt_int_max)
        df_main, *_ = m.simulate(params, scenario, dt=2e-3, t_end=0.05, record_full=False)
        return df_main


    def _max_h(df):
        if 'интегратор_подшаг_макс_с' not in df.columns:
            return None
        a = df['интегратор_подшаг_макс_с'].to_numpy(dtype=float)
        a = a[np.isfinite(a)]
        if a.size == 0:
            return None
        return float(a.max())

    # fine — условный эталон
    df_fine = run(7.5e-5)
    df_mid = run(1.5e-4)
    df_coarse = run(3.0e-4)

    # sanity: если модель логирует статистику подшагов, проверяем что h_max не превышает dt_int_max
    h_fine = _max_h(df_fine)
    h_mid = _max_h(df_mid)
    h_coarse = _max_h(df_coarse)
    if h_fine is not None:
        assert h_fine <= 7.5e-5 * (1.0 + 1e-9) + 1e-15
    if h_mid is not None:
        assert h_mid <= 1.5e-4 * (1.0 + 1e-9) + 1e-15
    if h_coarse is not None:
        assert h_coarse <= 3.0e-4 * (1.0 + 1e-9) + 1e-15

    # одинаковая сетка логирования
    assert len(df_fine) == len(df_mid) == len(df_coarse)

    col = "давление_ресивер2_Па"
    for df in (df_fine, df_mid, df_coarse):
        assert col in df.columns
        assert np.all(np.isfinite(df[col].to_numpy()))

    e_coarse = float(np.max(np.abs(df_coarse[col].to_numpy() - df_fine[col].to_numpy())))
    e_mid = float(np.max(np.abs(df_mid[col].to_numpy() - df_fine[col].to_numpy())))

    # mid должен быть лучше coarse
    assert e_mid < e_coarse

    # и улучшение должно быть заметным (не «на шум»)
    assert (e_coarse / (e_mid + 1e-12)) > 2.0


def test_integrator_local_error_control_step_doubling_worldroad():
    """Проверка опционального контроля локальной ошибки.

    В Matematika6455 добавлен режим `интегратор_контроль_локальной_ошибки`,
    который использует step-doubling для Heun (RK2): 1 шаг h vs 2 шага h/2.

    Ожидаем, что при том же `макс_шаг_интегрирования_с` результат станет ближе
    к «fine» (меньший dt_int_max), чем без контроля ошибки.
    """

    scenario = {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }

    base_params = {
        "mechanics_selfcheck": True,
        "mechanics_selfcheck_tol_m": 1e-6,
        "пружина_преднатяг_на_отбое_строго": False,
    }

    def run(dt_int_max: float, *, err_control: bool = False):
        params = dict(base_params)
        params["макс_шаг_интегрирования_с"] = float(dt_int_max)
        if err_control:
            params["интегратор_контроль_локальной_ошибки"] = True
            # оставляем дефолтные atol/rtol, но явно задаём для устойчивости теста
            params["интегратор_rtol"] = 1e-4
            params["интегратор_atol"] = 1e-8

        df_main, *_ = m.simulate(params, scenario, dt=2e-3, t_end=0.05, record_full=False)
        return df_main

    col = "давление_ресивер2_Па"

    df_fine = run(7.5e-5, err_control=False)
    df_coarse = run(3.0e-4, err_control=False)
    df_coarse_ec = run(3.0e-4, err_control=True)

    assert len(df_fine) == len(df_coarse) == len(df_coarse_ec)
    for df in (df_fine, df_coarse, df_coarse_ec):
        assert col in df.columns
        assert np.all(np.isfinite(df[col].to_numpy(dtype=float)))

    e_coarse = float(np.max(np.abs(df_coarse[col].to_numpy() - df_fine[col].to_numpy())))
    e_coarse_ec = float(np.max(np.abs(df_coarse_ec[col].to_numpy() - df_fine[col].to_numpy())))

    # контроль ошибки должен улучшать (не ухудшать)
    assert e_coarse_ec < e_coarse
    assert (e_coarse / (e_coarse_ec + 1e-12)) > 1.5

    # и должен логировать диагностические колонки
    assert 'интегратор_отклонения_N' in df_coarse_ec.columns
    assert 'интегратор_ошибка_max' in df_coarse_ec.columns
