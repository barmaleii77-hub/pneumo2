# -*- coding: utf-8 -*-
"""pneumo_solver_ui.spring_table

Утилиты для табличной характеристики пружины.

Задача: обеспечить два режима работы с табличной кривой F(x):
- "linear"  : линейная интерполяция (np.interp), как в старых версиях.
- "pchip"   : монотонная кубическая интерполяция PCHIP (shape-preserving).

Также поддерживается обратная операция: x(F) для подбора предсжатия x0.

Требования:
- x_tab: массив ходов (м), x>=0, по возрастанию.
- f_tab: массив сил (Н), f>=0, монотонно неубывающий.

Если входные таблицы нарушают монотонность, функции стараются деградировать
в безопасный режим (через сортировку/accumulate/unique), вместо падения.

Важно:
- Эти функции не знают о масштабировании пружины. Масштаб применять снаружи.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple, Union

import numpy as np

try:
    from scipy.interpolate import PchipInterpolator
except Exception:  # pragma: no cover
    PchipInterpolator = None  # type: ignore


SpringInterpMode = Literal['linear', 'pchip']


def _prepare_table(x_tab: Any, f_tab: Any) -> Tuple[np.ndarray, np.ndarray]:
    """Нормализовать таблицу: фильтр >=0, сортировка по x, f:=cummax."""
    x = np.asarray(x_tab, dtype=float).reshape(-1)
    f = np.asarray(f_tab, dtype=float).reshape(-1)
    if x.size != f.size:
        raise ValueError('x_tab and f_tab must have same length')

    # фильтр на корректные значения
    mask = np.isfinite(x) & np.isfinite(f) & (x >= 0.0) & (f >= 0.0)
    if np.any(mask):
        x = x[mask]
        f = f[mask]

    if x.size == 0:
        return np.zeros(0, dtype=float), np.zeros(0, dtype=float)

    order = np.argsort(x)
    x = x[order]
    f = f[order]

    # монотонность силы (односторонняя пружина)
    f = np.maximum.accumulate(f)

    return x, f


def _unique_monotone(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Сжать повторы x (или y) в строго монотонный аргумент.

    Для обратной интерполяции нам часто нужно y -> x, где y может иметь повторы.
    Берём максимальное x для каждого уникального y (консервативно: большее сжатие
    для той же силы).
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)
    if x.size != y.size:
        raise ValueError('x and y must have same length')
    if x.size == 0:
        return x, y

    # y уже неубывающий, но может иметь повторы
    y_unique = np.unique(y)
    x_for_y = np.zeros_like(y_unique, dtype=float)
    for i, yu in enumerate(y_unique):
        x_for_y[i] = float(np.max(x[y == yu]))
    return y_unique, x_for_y


def spring_force(x_query: Any, x_tab: Any, f_tab: Any, mode: SpringInterpMode = 'linear'):
    """F(x) по табличной кривой.

    Возвращает np.ndarray той же формы, что x_query.
    """
    xq = np.asarray(x_query, dtype=float)
    x, f = _prepare_table(x_tab, f_tab)
    if x.size == 0:
        return np.zeros_like(xq, dtype=float)

    x_min = float(x[0])
    x_max = float(x[-1])
    xqc = np.clip(xq, x_min, x_max)

    if (mode == 'pchip') and (PchipInterpolator is not None) and (x.size >= 2):
        try:
            itp = PchipInterpolator(x, f, extrapolate=True)
            y = itp(xqc)
            return np.asarray(y, dtype=float)
        except Exception:
            # fallback
            pass

    return np.interp(xqc, x, f)


def spring_inverse_force(f_query: Any, x_tab: Any, f_tab: Any, mode: SpringInterpMode = 'linear'):
    """x(F) — подобрать сжатие по заданной силе.

    Важно: предполагается, что F(x) монотонно неубывает.

    Возвращает np.ndarray той же формы, что f_query.
    """
    fq = np.asarray(f_query, dtype=float)
    x, f = _prepare_table(x_tab, f_tab)
    if x.size == 0:
        return np.zeros_like(fq, dtype=float)

    f_min = float(f[0])
    f_max = float(f[-1])
    fqc = np.clip(fq, f_min, f_max)

    # Для обратной функции нужен строго возрастающий аргумент.
    f_u, x_u = _unique_monotone(x, f)
    if f_u.size < 2:
        return np.zeros_like(fqc, dtype=float) + float(x_u[0])

    if (mode == 'pchip') and (PchipInterpolator is not None) and (f_u.size >= 2):
        try:
            itp = PchipInterpolator(f_u, x_u, extrapolate=True)
            y = itp(fqc)
            return np.asarray(y, dtype=float)
        except Exception:
            pass

    return np.interp(fqc, f_u, x_u)


def spring_stiffness(x_query: Any, x_tab: Any, f_tab: Any, mode: SpringInterpMode = 'linear'):
    """dF/dx по табличной кривой.

    Для режима 'linear' возвращаем кусочно‑постоянный наклон сегмента.
    Для 'pchip' (если доступен SciPy) используем производную PchipInterpolator.

    Возвращает np.ndarray той же формы, что x_query.

    Замечание:
    - вне диапазона таблицы значения клиппируются по x.
    - если таблица вырождена (меньше 2 точек) — возвращаем 0.
    """
    xq = np.asarray(x_query, dtype=float)
    x, f = _prepare_table(x_tab, f_tab)
    if x.size < 2:
        return np.zeros_like(xq, dtype=float)

    x_min = float(x[0])
    x_max = float(x[-1])
    xqc = np.clip(xq, x_min, x_max)

    if (mode == 'pchip') and (PchipInterpolator is not None):
        try:
            itp = PchipInterpolator(x, f, extrapolate=True)
            ditp = itp.derivative()
            k = ditp(xqc)
            k = np.where(np.isfinite(k), k, 0.0)
            return np.asarray(k, dtype=float)
        except Exception:
            # fallback to linear slopes
            pass

    # piecewise-linear slope
    dx = np.diff(x)
    df = np.diff(f)
    # avoid div0
    slopes = np.where(np.abs(dx) > 0.0, df / dx, 0.0)

    # for each xqc choose the corresponding segment
    idx = np.searchsorted(x, xqc, side='right') - 1
    idx = np.clip(idx, 0, len(slopes) - 1)
    return slopes[idx].astype(float)


@dataclass
class SpringTable:
    """Удобная обёртка над таблицей пружины."""

    x_tab_m: np.ndarray
    f_tab_N: np.ndarray
    mode: SpringInterpMode = 'linear'

    def __post_init__(self):
        self.x_tab_m, self.f_tab_N = _prepare_table(self.x_tab_m, self.f_tab_N)

    @property
    def x_max(self) -> float:
        return float(self.x_tab_m[-1]) if self.x_tab_m.size else 0.0

    @property
    def f_max(self) -> float:
        return float(self.f_tab_N[-1]) if self.f_tab_N.size else 0.0

    def force(self, x_m: Any):
        return spring_force(x_m, self.x_tab_m, self.f_tab_N, mode=self.mode)

    def inverse(self, f_N: Any):
        return spring_inverse_force(f_N, self.x_tab_m, self.f_tab_N, mode=self.mode)

    def stiffness(self, x_m: Any):
        return spring_stiffness(x_m, self.x_tab_m, self.f_tab_N, mode=self.mode)
