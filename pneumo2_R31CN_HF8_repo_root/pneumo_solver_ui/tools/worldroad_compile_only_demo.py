# -*- coding: utf-8 -*-
"""worldroad_compile_only_demo.py

Демо использования режима `compile_only` в модели
`model_pneumo_v9_mech_doublewishbone_worldroad.py`.

Зачем:
- получить RHS/шаг интегратора и наблюдатель (observe) без сборки pandas DataFrame;
- использовать это как базу для:
  * внешних интеграторов,
  * градиентных оптимизаторов,
  * минималистичных KPI-прогонов,
  * дальнейшего перехода к автодиффу.

Запуск (из корня UnifiedPneumoApp_UNIFIED_v6_42_WINSAFE):
    python -m pneumo_solver_ui.tools.worldroad_compile_only_demo --dt 0.002 --t_end 1.0

Вывод:
- JSON со сводкой (макс. углы, давление Р3, минимум силы шины и т.д.).

Важно:
- Это утилита для разработчика/оптимизации, UI её не использует напрямую.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np


if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"


def _load_json(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--params', type=str, default=str(Path(__file__).resolve().parents[1] / 'default_base.json'))
    ap.add_argument('--test', type=str, default=str(Path(__file__).resolve().parents[1] / 'default_suite.json'))
    ap.add_argument('--test_index', type=int, default=0)
    ap.add_argument('--dt', type=float, default=None)
    ap.add_argument('--t_end', type=float, default=None)
    ap.add_argument('--observe_each', type=int, default=1, help='Снимать observe каждый N шагов (>=1).')
    args = ap.parse_args()

    params_path = Path(args.params)
    test_path = Path(args.test)

    params = _load_json(params_path)

    tests = _load_json(test_path)
    if not isinstance(tests, list) or not tests:
        raise SystemExit(f"test file must be a non-empty list: {test_path}")

    test = dict(tests[int(args.test_index)])

    # dt/t_end берём из test, если не заданы явно
    dt = float(args.dt) if args.dt is not None else float(test.get('dt', 1e-3))
    t_end = float(args.t_end) if args.t_end is not None else float(test.get('t_end', 3.0))

    # Для демо: включим облегчённый лог (но compile_only всё равно не строит df)
    test.setdefault('log_level', 'kpi')

    # Импорт модели
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as model

    ctx = model.simulate(params=params, test=test, dt=dt, t_end=t_end, compile_only=True)

    state = np.asarray(ctx['state0'], dtype=float)
    step = ctx['rk2_step']
    observe = ctx['observe']

    n_steps = int(math.floor(t_end / dt)) + 1

    # KPI аккумуляторы
    max_phi = 0.0
    max_theta = 0.0
    max_pR3 = -1e99
    min_Ftire = +1e99
    max_pen = -1e99

    # Снимаем первую точку
    for k in range(n_steps):
        t = k * dt

        if (k % max(1, int(args.observe_each))) == 0 or (k == n_steps - 1):
            obs = observe(state, t)

            phi = float(obs.get('phi', 0.0))
            theta = float(obs.get('theta', 0.0))
            max_phi = max(max_phi, abs(phi))
            max_theta = max(max_theta, abs(theta))

            pR3 = float(obs.get('pR3', float('nan')))
            if not math.isnan(pR3):
                max_pR3 = max(max_pR3, pR3)

            Ft = np.asarray(obs.get('tire_Fz_N', np.zeros(4)), dtype=float)
            if Ft.size:
                min_Ftire = min(min_Ftire, float(np.min(Ft)))

            pen = np.asarray(obs.get('tire_pen_m', np.zeros(4)), dtype=float)
            if pen.size:
                max_pen = max(max_pen, float(np.max(pen)))

        # шаг интегратора
        if k < n_steps - 1:
            state = step(state, t, dt)

    out = {
        'dt_s': dt,
        't_end_s': t_end,
        'n_steps': n_steps,
        'max_abs_phi_deg': float(max_phi * 180.0 / math.pi),
        'max_abs_theta_deg': float(max_theta * 180.0 / math.pi),
        'max_pR3_Pa': float(max_pR3),
        'min_tire_Fz_N': float(min_Ftire),
        'max_tire_pen_m': float(max_pen),
        'note': 'compile_only demo (no pandas DataFrame build)'
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
