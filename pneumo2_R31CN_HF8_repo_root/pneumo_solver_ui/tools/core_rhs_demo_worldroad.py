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

import json
import os
import math
from pathlib import Path


def _load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    model_path = root / 'model_pneumo_v9_mech_doublewishbone_worldroad.py'
    base_json = root / 'default_base.json'
    suite_json = root / 'default_suite.json'

    # Загрузка модели через importlib (Windows-safe)
    import importlib.util

    spec = importlib.util.spec_from_file_location('pneumo_model_worldroad', str(model_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Не удалось загрузить модель: {model_path}')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore

    params = _load_json(base_json)
    suite = _load_json(suite_json)
    if not suite:
        raise RuntimeError('default_suite.json пустой')

    test = dict(suite[0])
    dt = float(test.get('dt', 1e-3))
    t_end = float(test.get('t_end', 1.0))

    # Включаем «гладкий режим» для демонстрации дифференцируемости (опционально)
    params['fully_smooth_mode'] = True

    ctx = m.simulate(params, test, dt=dt, t_end=t_end, compile_only=True)

    state = ctx['state0']
    rhs = ctx['rhs']
    step = ctx['rk2_step']

    dst0 = rhs(state, 0.0)
    z_ddot = float(dst0[7])
    phi_ddot = float(dst0[8])
    theta_ddot = float(dst0[9])
    zw_ddot = dst0[10:14]

    print('--- compile_only core exported ---')
    print('dt =', ctx['dt'], 't_end =', ctx['t_end'])
    print('wheel_coord_mode =', ctx['wheel_coord_mode'], 'wheel_radius_m =', ctx['wheel_radius_m'])
    print('road_offset0_m =', ctx['road_offset0_m'])
    print('smooth flags:', ctx['smooth'])

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
    p, *_ = ctx['compute_pressures'](state)
    node_index = ctx['node_index']
    if 'Аккумулятор' in node_index:
        print('P_acc =', float(p[node_index['Аккумулятор']]) / 1e5, 'bar(abs)')

    # Пример observe(): ключевые величины в точке времени без DataFrame
    if 'observe' in ctx:
        obs = ctx['observe'](state, t)
        pen = obs.get('penetration')
        Ft = obs.get('F_tire')
        if pen is not None and Ft is not None:
            print('\n--- observe() snapshot ---')
            print('penetration[m] =', [float(x) for x in pen])
            print('F_tire[N]      =', [float(x) for x in Ft])


if __name__ == '__main__':
    main()
