import warnings

import numpy as np
from pandas.errors import PerformanceWarning


def test_worldroad_no_fragmentation_warnings_and_service_columns_present():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,
        'use_rel0': True,
    }
    test = {
        'road_func': lambda t: np.zeros(4),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        df_main, *_ = m.simulate(params, test, dt=1e-3, t_end=0.05, record_full=False)

    perf_warnings = [w for w in caught if isinstance(w.message, PerformanceWarning)]
    assert perf_warnings == []

    rel0_cols = [c for c in df_main.columns if c.endswith('_rel0')]
    assert rel0_cols, 'worldroad must still emit service *_rel0 columns when use_rel0=True'

    assert 'ошибка_энергии_мех_Дж' in df_main.columns
    assert 'ошибка_энергии_мех_отн' in df_main.columns
    assert 'ошибка_мощности_p_dV_Вт' in df_main.columns

    first_rel0_abs_max = float(np.max(np.abs(df_main[rel0_cols].iloc[0].to_numpy(dtype=float))))
    assert first_rel0_abs_max <= 1e-12
