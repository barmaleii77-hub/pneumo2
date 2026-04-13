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

import math
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Tuple, Union

import numpy as np

try:
    from scipy.interpolate import PchipInterpolator
except Exception:  # pragma: no cover
    PchipInterpolator = None  # type: ignore


SpringInterpMode = Literal['linear', 'pchip']


@dataclass(frozen=True)
class SpringGeometryReference:
    d_wire_m: float
    D_mean_m: float
    N_active: float
    N_total: float
    pitch_m: float
    G_Pa: float
    F_max_N: float
    spring_index: float
    rate_N_per_m: float
    rate_N_per_mm: float
    solid_length_m: float
    free_length_from_pitch_m: float
    bind_travel_margin_m: float
    max_shear_stress_Pa: float


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


def _build_pchip_interpolator(x_tab: np.ndarray, y_tab: np.ndarray):
    """Построить PCHIP один раз для уже подготовленной таблицы."""
    if (PchipInterpolator is None) or (x_tab.size < 2):
        return None
    try:
        return PchipInterpolator(x_tab, y_tab, extrapolate=True)
    except Exception:
        return None


def spring_rate_from_geometry(
    G_Pa: float,
    d_wire_m: float,
    D_mean_m: float,
    N_active: float,
) -> float:
    """k = G d^4 / (8 D^3 N)."""
    if G_Pa <= 0 or d_wire_m <= 0 or D_mean_m <= 0 or N_active <= 0:
        return float("nan")
    return float(G_Pa) * float(d_wire_m) ** 4 / (8.0 * float(D_mean_m) ** 3 * float(N_active))


def spring_wahl_factor(C: float) -> float:
    if C <= 1.0:
        return float("nan")
    return (4.0 * C - 1.0) / (4.0 * C - 4.0) + 0.615 / C


def spring_max_shear_stress(
    F_N: float,
    D_mean_m: float,
    d_wire_m: float,
) -> float:
    """tau_max ≈ (8 F D / (pi d^3)) * K_w."""
    if F_N <= 0 or D_mean_m <= 0 or d_wire_m <= 0:
        return float("nan")
    spring_index = float(D_mean_m) / float(d_wire_m)
    Kw = spring_wahl_factor(spring_index)
    if not math.isfinite(Kw):
        return float("nan")
    return (8.0 * float(F_N) * float(D_mean_m) / (math.pi * float(d_wire_m) ** 3)) * float(Kw)


def spring_solid_length(N_total: float, d_wire_m: float) -> float:
    if d_wire_m <= 0 or N_total <= 0:
        return float("nan")
    return float(max(1, int(round(N_total)))) * float(d_wire_m)


def spring_free_length_from_pitch(
    N_total: float,
    pitch_m: float,
    d_wire_m: float,
) -> float:
    if d_wire_m <= 0 or pitch_m <= 0 or N_total < 2:
        return float("nan")
    turns = max(2, int(round(N_total)))
    return float(turns - 1) * float(pitch_m) + float(d_wire_m)


def build_spring_geometry_reference(
    *,
    d_wire_m: float,
    D_mean_m: float,
    N_active: float,
    N_total: float,
    pitch_m: float,
    G_Pa: float,
    F_max_N: float = 0.0,
) -> SpringGeometryReference:
    spring_index = (
        float(D_mean_m) / float(d_wire_m)
        if d_wire_m > 0
        else float("nan")
    )
    rate_N_per_m = spring_rate_from_geometry(
        G_Pa,
        d_wire_m,
        D_mean_m,
        N_active,
    )
    solid_length_m = spring_solid_length(N_total, d_wire_m)
    free_length_from_pitch_m = spring_free_length_from_pitch(
        N_total,
        pitch_m,
        d_wire_m,
    )
    bind_travel_margin_m = (
        float(free_length_from_pitch_m) - float(solid_length_m)
        if math.isfinite(free_length_from_pitch_m) and math.isfinite(solid_length_m)
        else float("nan")
    )
    return SpringGeometryReference(
        d_wire_m=float(d_wire_m),
        D_mean_m=float(D_mean_m),
        N_active=float(N_active),
        N_total=float(N_total),
        pitch_m=float(pitch_m),
        G_Pa=float(G_Pa),
        F_max_N=float(F_max_N),
        spring_index=float(spring_index),
        rate_N_per_m=float(rate_N_per_m),
        rate_N_per_mm=(float(rate_N_per_m) / 1000.0) if math.isfinite(rate_N_per_m) else float("nan"),
        solid_length_m=float(solid_length_m),
        free_length_from_pitch_m=float(free_length_from_pitch_m),
        bind_travel_margin_m=float(bind_travel_margin_m),
        max_shear_stress_Pa=float(
            spring_max_shear_stress(
                F_max_N,
                D_mean_m,
                d_wire_m,
            )
        ),
    )


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


def _spring_force_prepared(
    x_query: Any,
    x_tab: np.ndarray,
    f_tab: np.ndarray,
    *,
    mode: SpringInterpMode = 'linear',
    interpolator: Any = None,
):
    xq = np.asarray(x_query, dtype=float)
    if x_tab.size == 0:
        return np.zeros_like(xq, dtype=float)

    xqc = np.clip(xq, float(x_tab[0]), float(x_tab[-1]))

    if (mode == 'pchip') and (interpolator is not None):
        try:
            return np.asarray(interpolator(xqc), dtype=float)
        except Exception:
            pass

    return np.asarray(np.interp(xqc, x_tab, f_tab), dtype=float)


def _spring_inverse_prepared(
    f_query: Any,
    x_tab: np.ndarray,
    f_tab: np.ndarray,
    *,
    mode: SpringInterpMode = 'linear',
    f_unique: Optional[np.ndarray] = None,
    x_for_f_unique: Optional[np.ndarray] = None,
    interpolator: Any = None,
):
    fq = np.asarray(f_query, dtype=float)
    if x_tab.size == 0:
        return np.zeros_like(fq, dtype=float)

    fqc = np.clip(fq, float(f_tab[0]), float(f_tab[-1]))
    if f_unique is None or x_for_f_unique is None:
        f_unique, x_for_f_unique = _unique_monotone(x_tab, f_tab)

    if f_unique.size < 2:
        if x_for_f_unique.size == 0:
            return np.zeros_like(fqc, dtype=float)
        return np.zeros_like(fqc, dtype=float) + float(x_for_f_unique[0])

    if (mode == 'pchip') and (interpolator is not None):
        try:
            return np.asarray(interpolator(fqc), dtype=float)
        except Exception:
            pass

    return np.asarray(np.interp(fqc, f_unique, x_for_f_unique), dtype=float)


def _spring_stiffness_prepared(
    x_query: Any,
    x_tab: np.ndarray,
    f_tab: np.ndarray,
    *,
    mode: SpringInterpMode = 'linear',
    derivative: Any = None,
):
    xq = np.asarray(x_query, dtype=float)
    if x_tab.size < 2:
        return np.zeros_like(xq, dtype=float)

    xqc = np.clip(xq, float(x_tab[0]), float(x_tab[-1]))

    if (mode == 'pchip') and (derivative is not None):
        try:
            k = derivative(xqc)
            return np.asarray(np.where(np.isfinite(k), k, 0.0), dtype=float)
        except Exception:
            pass

    dx = np.diff(x_tab)
    df = np.diff(f_tab)
    slopes = np.where(np.abs(dx) > 0.0, df / dx, 0.0)
    idx = np.searchsorted(x_tab, xqc, side='right') - 1
    idx = np.clip(idx, 0, len(slopes) - 1)
    return slopes[idx].astype(float)


def spring_force(x_query: Any, x_tab: Any, f_tab: Any, mode: SpringInterpMode = 'linear'):
    """F(x) по табличной кривой.

    Возвращает np.ndarray той же формы, что x_query.
    """
    xq = np.asarray(x_query, dtype=float)
    x, f = _prepare_table(x_tab, f_tab)
    if x.size == 0:
        return np.zeros_like(xq, dtype=float)
    return _spring_force_prepared(
        xq,
        x,
        f,
        mode=mode,
        interpolator=_build_pchip_interpolator(x, f) if mode == 'pchip' else None,
    )


def spring_inverse_force(f_query: Any, x_tab: Any, f_tab: Any, mode: SpringInterpMode = 'linear'):
    """x(F) — подобрать сжатие по заданной силе.

    Важно: предполагается, что F(x) монотонно неубывает.

    Возвращает np.ndarray той же формы, что f_query.
    """
    fq = np.asarray(f_query, dtype=float)
    x, f = _prepare_table(x_tab, f_tab)
    if x.size == 0:
        return np.zeros_like(fq, dtype=float)
    f_u, x_u = _unique_monotone(x, f)
    return _spring_inverse_prepared(
        fq,
        x,
        f,
        mode=mode,
        f_unique=f_u,
        x_for_f_unique=x_u,
        interpolator=_build_pchip_interpolator(f_u, x_u) if mode == 'pchip' else None,
    )


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
    force_interpolator = _build_pchip_interpolator(x, f) if mode == 'pchip' else None
    return _spring_stiffness_prepared(
        xq,
        x,
        f,
        mode=mode,
        derivative=force_interpolator.derivative() if force_interpolator is not None else None,
    )


@dataclass
class SpringTable:
    """Удобная обёртка над таблицей пружины."""

    x_tab_m: np.ndarray
    f_tab_N: np.ndarray
    mode: SpringInterpMode = 'linear'
    _force_interpolator: Any = field(init=False, repr=False, default=None)
    _force_derivative: Any = field(init=False, repr=False, default=None)
    _inverse_interpolator: Any = field(init=False, repr=False, default=None)
    _f_unique_N: np.ndarray = field(init=False, repr=False)
    _x_for_f_unique_m: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        self.x_tab_m, self.f_tab_N = _prepare_table(self.x_tab_m, self.f_tab_N)
        self._f_unique_N, self._x_for_f_unique_m = _unique_monotone(self.x_tab_m, self.f_tab_N)
        self._force_interpolator = _build_pchip_interpolator(self.x_tab_m, self.f_tab_N) if self.mode == 'pchip' else None
        self._force_derivative = self._force_interpolator.derivative() if self._force_interpolator is not None else None
        self._inverse_interpolator = (
            _build_pchip_interpolator(self._f_unique_N, self._x_for_f_unique_m)
            if self.mode == 'pchip'
            else None
        )

    @property
    def x_max(self) -> float:
        return float(self.x_tab_m[-1]) if self.x_tab_m.size else 0.0

    @property
    def f_max(self) -> float:
        return float(self.f_tab_N[-1]) if self.f_tab_N.size else 0.0

    def force(self, x_m: Any):
        return _spring_force_prepared(
            x_m,
            self.x_tab_m,
            self.f_tab_N,
            mode=self.mode,
            interpolator=self._force_interpolator,
        )

    def inverse(self, f_N: Any):
        return _spring_inverse_prepared(
            f_N,
            self.x_tab_m,
            self.f_tab_N,
            mode=self.mode,
            f_unique=self._f_unique_N,
            x_for_f_unique=self._x_for_f_unique_m,
            interpolator=self._inverse_interpolator,
        )

    def stiffness(self, x_m: Any):
        return _spring_stiffness_prepared(
            x_m,
            self.x_tab_m,
            self.f_tab_N,
            mode=self.mode,
            derivative=self._force_derivative,
        )
