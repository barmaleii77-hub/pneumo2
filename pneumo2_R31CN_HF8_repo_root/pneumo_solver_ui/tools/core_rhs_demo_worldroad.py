# -*- coding: utf-8 -*-
"""core_rhs_demo_worldroad.py

Демонстрация режима `compile_only=True` для модели world-road v9.

Запуск:
    python -m pneumo_solver_ui.tools.core_rhs_demo_worldroad

Что показывает:
- получение `state0`, `rhs`, `rk2_step` без построения DataFrame/Excel;
- первый вызов RHS (ускорения/проверка статики);
- несколько шагов интегрирования.

Важно:
- Это демонстрационный скрипт. Он не является частью UI.
"""

from __future__ import annotations

# Allow direct execution (`python pneumo_solver_ui/tools/core_rhs_demo_worldroad.py`)
# in addition to package execution (`python -m pneumo_solver_ui.tools.core_rhs_demo_worldroad`).
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    import sys as _sys
    from pathlib import Path as _Path

    _ROOT = _Path(__file__).resolve().parents[2]
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

import json
import math
from pathlib import Path


def _load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _first_present(mapping: dict, *keys: str):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    base_json = root / 'default_base.json'
    suite_json = root / 'default_suite.json'
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = _load_json(base_json)
    suite = _load_json(suite_json)
    if not suite:
        raise RuntimeError('default_suite.json пустой')

    test = dict(next((row for row in suite if isinstance(row, dict) and bool(row.get("включен"))), suite[0]))
    dt = float(test.get('dt', 1e-3))
    t_end = float(test.get('t_end', 1.0))

    # Включаем «гладкий режим» для демонстрации дифференцируемости (опционально)
    params['fully_smooth_mode'] = True

    ctx = m.simulate(params, test, dt=dt, t_end=t_end, compile_only=True)

    state = ctx['state0']
    rhs = ctx['rhs']
    step = ctx['rk2_step']
    observe = ctx.get('observe')

    dst0 = rhs(state, 0.0)
    obs0 = observe(state, 0.0) if callable(observe) else {}
    z_ddot = float(dst0[7])
    phi_ddot = float(dst0[8])
    theta_ddot = float(dst0[9])
    zw_ddot = dst0[10:14]

    print('--- compile_only core exported ---')
    print('dt =', ctx['dt'], 't_end =', ctx['t_end'])
    print('wheel_coord_mode =', ctx['wheel_coord_mode'], 'wheel_radius_m =', ctx['wheel_radius_m'])
    road_offset0 = _first_present(ctx, 'road_offset0_m', 'road0_offset_m')
    if road_offset0 is not None:
        print('road_offset0_m =', road_offset0)
    else:
        road0 = _first_present(obs0, 'z_road', 'road')
        if road0 is not None:
            print('road0_contact_m =', [float(x) for x in road0])
    smooth_info = ctx.get('smooth')
    if smooth_info is None:
        smooth_info = {
            'fully_smooth_mode': bool(params.get('fully_smooth_mode', params.get('полностью_гладкий_режим', False))),
            'smooth_contacts': bool(params.get('smooth_contacts', False)),
            'smooth_valves': bool(params.get('smooth_valves', False)),
        }
    print('smooth flags:', smooth_info)

    print('\n--- RHS at t=0 ---')
    print('z_ddot =', z_ddot, 'm/s^2')
    print('phi_ddot =', phi_ddot, 'rad/s^2')
    print('theta_ddot =', theta_ddot, 'rad/s^2')
    print('zw_ddot =', [float(x) for x in zw_ddot], 'm/s^2')

    # Несколько шагов RK2
    t = 0.0
    n = 10
    for _ in range(n):
        state = step(state, t, dt)
        t += dt

    print('\n--- After', n, 'RK2 steps ---')
    print('t =', t)
    print('z =', float(state[0]), 'm')
    print('phi =', float(state[1]) * 180.0 / math.pi, 'deg')
    print('theta =', float(state[2]) * 180.0 / math.pi, 'deg')

    # Пример чтения давлений (через compute_pressures)
    p = None
    if 'compute_pressures' in ctx:
        p, *_ = ctx['compute_pressures'](state)
    elif callable(observe):
        obs_after = observe(state, t)
        p = obs_after.get('p')
    node_index = ctx.get('node_index', {})
    if p is not None and 'Аккумулятор' in node_index:
        print('P_acc =', float(p[node_index['Аккумулятор']]) / 1e5, 'bar(abs)')

    # Пример observe(): ключевые величины в точке времени без DataFrame
    if callable(observe):
        obs = observe(state, t)
        pen = obs.get('penetration')
        if pen is None:
            pen = _first_present(obs, 'tire_pen_m', 'pen')
        Ft = _first_present(obs, 'F_tire', 'tire_Fz_N')
        if pen is not None and Ft is not None:
            print('\n--- observe() snapshot ---')
            print('penetration[m] =', [float(x) for x in pen])
            print('F_tire[N]      =', [float(x) for x in Ft])


if __name__ == '__main__':
    main()
