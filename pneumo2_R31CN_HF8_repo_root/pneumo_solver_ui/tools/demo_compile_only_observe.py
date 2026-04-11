# -*- coding: utf-8 -*-
"""Demo: compile_only + observe core API

Запуск (из корня приложения):
    python pneumo_solver_ui/tools/demo_compile_only_observe.py

Зачем:
- получить «ядро» модели (rhs + rk2_step) и observe() без построения больших DataFrame;
- быстрые KPI можно агрегировать на лету (максимумы/интегралы), экономя RAM;
- удобная точка расширения под автодифф/JAX/CasADi (в будущем).

Важно:
- это демонстрационный скрипт (не часть UI);
- использует модель world-road: model_pneumo_v9_mech_doublewishbone_worldroad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np


if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    """C1-бамп: 0 -> A на [t0, t0+dur] с нулевой производной на концах."""
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - math.cos(math.pi * x))


@dataclass
class KPIs:
    max_abs_phi: float = 0.0
    max_abs_theta: float = 0.0
    max_abs_z: float = 0.0
    max_Fz: float = 0.0
    min_pen: float = 0.0


def main():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    # Параметры: включаем fully_smooth_mode и гладкие контакты/упоры.
    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'fully_smooth_mode': True,
        'smooth_contacts': True,
        'smooth_stops': True,
        # selfcheck выключим — здесь мы показываем работу compile_only.
        'mechanics_selfcheck': False,
    }

    # Тест: плавный "бамп" под ЛП колесом.
    test = {
        'road_func': lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    dt = 2e-3
    t_end = 0.05
    n_steps = int(t_end / dt) + 1

    core = m.simulate(params, test, dt=dt, t_end=t_end, compile_only=True)

    state = np.asarray(core['state0'], dtype=float).copy()
    kpis = KPIs(min_pen=1e9)

    for k in range(n_steps):
        t = k * dt

        # Снимок: давления/контакт/пенетрация/силы.
        obs = core['observe'](state, t)

        # Глобальные координаты рамы: state = [z, phi, theta, z_wheels(4), m_nodes(N)]
        z = float(state[0])
        phi = float(state[1])
        theta = float(state[2])

        kpis.max_abs_z = max(kpis.max_abs_z, abs(z))
        kpis.max_abs_phi = max(kpis.max_abs_phi, abs(phi))
        kpis.max_abs_theta = max(kpis.max_abs_theta, abs(theta))

        Fz = np.asarray(obs['tire_Fz_N'], dtype=float)
        pen = np.asarray(obs['tire_pen_m'], dtype=float)

        kpis.max_Fz = max(kpis.max_Fz, float(np.max(Fz)))
        kpis.min_pen = min(kpis.min_pen, float(np.min(pen)))

        # RK2 шаг
        state = core['rk2_step'](state, t, dt)

    print('=== compile_only demo summary ===')
    print(f'dt = {dt:g} s, t_end = {t_end:g} s, n_steps = {n_steps}')
    print(f'max |z_body| = {kpis.max_abs_z:.6g} m')
    print(f'max |phi| = {kpis.max_abs_phi:.6g} rad  (={math.degrees(kpis.max_abs_phi):.4g} deg)')
    print(f'max |theta| = {kpis.max_abs_theta:.6g} rad  (={math.degrees(kpis.max_abs_theta):.4g} deg)')
    print(f'max Fz = {kpis.max_Fz:.6g} N')
    print(f'min penetration = {kpis.min_pen:.6g} m')


if __name__ == '__main__':
    main()
