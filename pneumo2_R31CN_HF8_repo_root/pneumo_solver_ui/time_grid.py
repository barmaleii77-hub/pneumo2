# -*- coding: utf-8 -*-
"""pneumo_solver_ui.time_grid

Единый генератор временной сетки для моделей.

Зачем это нужно
---------------
Ранее в нескольких местах использовался шаблон:

    n = int(t_end/dt) + 1
    time = np.linspace(0, t_end, n)

Если t_end/dt не целое, то шаг time становится dt_eff=t_end/(n-1),
а интегратор/интегралы выполняются с заданным dt.
Это создаёт рассинхрон оси времени и динамики.

Правило build_time_grid:
- шаг равен dt (кроме опциональных режимов),
- последний момент времени t_last <= t_end (режим floor по умолчанию).

Таким образом, dt в расчёте и dt в time согласованы.
"""

from __future__ import annotations

import numpy as np


def build_time_grid(*, dt: float, t_end: float, t0: float = 0.0, mode: str = "floor") -> np.ndarray:
    """Построить 1D массив времени.

    Parameters
    ----------
    dt : float
        Шаг интегрирования (>0)
    t_end : float
        Требуемый горизонт моделирования (>=t0)
    t0 : float
        Начальное время
    mode : {"floor", "ceil"}
        - floor: t_last <= t_end
        - ceil:  t_last >= t_end

    Returns
    -------
    np.ndarray
        time[0]=t0, шаг ~ dt.
    """
    dt = float(dt)
    t_end = float(t_end)
    t0 = float(t0)

    if dt <= 0.0:
        raise ValueError(f"dt must be > 0, got {dt}")

    if t_end <= t0:
        return np.array([t0], dtype=float)

    horizon = t_end - t0
    if mode not in {"floor", "ceil"}:
        raise ValueError(f"Unknown mode: {mode}")

    if mode == "ceil":
        n = int(np.ceil(horizon / dt)) + 1
    else:
        n = int(np.floor(horizon / dt)) + 1

    n = max(1, int(n))
    time = t0 + dt * np.arange(n, dtype=float)
    return time
