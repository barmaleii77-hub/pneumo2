# -*- coding: utf-8 -*-
"""iso6358_fit.py

Инструменты для идентификации параметров ISO 6358 (b, m) по измерениям.

Контекст
--------
ISO 6358-1 (ред. 2013) использует параметры C (sonic conductance), b (critical
back-pressure ratio), m (subsonic index) и Δpc (cracking pressure) для описания
расходной характеристики пневмокомпонентов. В проекте расходная характеристика
пассивных элементов описывается как:

    q_n(ANR) = C * p_up * φ(pr; b, m) * sqrt(T_ref / T_up)

где pr = p_dn/p_up, а φ(pr) = 1 в области choked и уменьшается в области subsonic.

Этот модуль решает прикладную задачу:
- имея набор измерений (p_up, p_dn, Qn) при фиксированном элементе,
  подобрать b и m наименее квадратично.

Ограничения
-----------
- Здесь используется «практическая» форма φ(pr), которую применяет проект
  (см. iso6358_core.iso6358_phi).
- Если у вас есть точные паспортные b,m по ISO 6358 — используйте их напрямую,
  этот фиттер нужен для случаев, когда есть только кривые/точки.

Запуск демо
-----------
См. iso_fit_demo.py

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple, Optional

import numpy as np

# Важно: φ(pr) и ANR-константы должны быть едиными во всём проекте.
# Поэтому для фита используем iso6358_core как source-of-truth.
try:
    from . import iso6358_core as model
except Exception:
    import iso6358_core as model


@dataclass
class FitResult:
    b: float
    m: float
    rmse: float
    n: int


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    d = a - b
    return float(np.sqrt(np.mean(d * d)))


def fit_b_m_from_ratio(
    pr: Iterable[float],
    ratio: Iterable[float],
    *,
    beta_lam: float = model.ISO6358_BETA_LAM_DEFAULT,
    b_bounds: Tuple[float, float] = (0.05, 0.95),
    m_bounds: Tuple[float, float] = (0.05, 2.0),
    b_step: float = 0.005,
    m_step: float = 0.01,
    refine_rounds: int = 2,
) -> FitResult:
    """Подбор (b,m) по данным в координатах (pr, ratio).

    pr      : массив p_dn/p_up (0..1)
    ratio   : массив относительного расхода q/q* (0..1)

    Важное: ratio должен быть уже нормирован к q* = C*p_up*sqrt(Tref/Tup).

    Алгоритм: грубая сетка (b_step, m_step) + несколько уточнений вокруг минимума.
    Скорость не приоритет, зато стабильность и предсказуемость.
    """
    pr = np.asarray(list(pr), dtype=float)
    ratio = np.asarray(list(ratio), dtype=float)

    mask = np.isfinite(pr) & np.isfinite(ratio) & (pr > 0.0) & (pr < 1.0)
    pr = pr[mask]
    ratio = ratio[mask]

    if pr.size < 5:
        raise ValueError("Недостаточно точек для фита b,m (нужно хотя бы 5).")

    ratio = np.clip(ratio, 0.0, 1.0)

    b_lo, b_hi = b_bounds
    m_lo, m_hi = m_bounds

    best_b = None
    best_m = None
    best_rmse = 1e9

    def grid_search(b_lo, b_hi, m_lo, m_hi, b_step, m_step):
        nonlocal best_b, best_m, best_rmse
        b_grid = np.arange(b_lo, b_hi + 1e-12, b_step)
        m_grid = np.arange(m_lo, m_hi + 1e-12, m_step)
        for b in b_grid:
            # быстро отбрасываем явно плохие b: если есть точки ниже b, ratio там обязано быть ~1
            # (но не навязываем жёстко, т.к. шум)
            for m in m_grid:
                pred = np.array([model.iso6358_phi(float(x), float(b), m=float(m), beta_lam=float(beta_lam)) for x in pr])
                r = _rmse(pred, ratio)
                if r < best_rmse:
                    best_rmse = r
                    best_b = float(b)
                    best_m = float(m)

    # грубый проход
    grid_search(b_lo, b_hi, m_lo, m_hi, b_step, m_step)

    # уточнения вокруг минимума
    for _ in range(int(refine_rounds)):
        b_span = max(0.02, 5 * b_step)
        m_span = max(0.05, 5 * m_step)
        b_lo2 = max(b_bounds[0], best_b - b_span)
        b_hi2 = min(b_bounds[1], best_b + b_span)
        m_lo2 = max(m_bounds[0], best_m - m_span)
        m_hi2 = min(m_bounds[1], best_m + m_span)
        b_step *= 0.2
        m_step *= 0.2
        grid_search(b_lo2, b_hi2, m_lo2, m_hi2, b_step, m_step)

    return FitResult(b=best_b, m=best_m, rmse=best_rmse, n=int(pr.size))


def fit_b_m_from_measurements(
    p_up: Iterable[float],
    p_dn: Iterable[float],
    qn_nl_min: Iterable[float],
    *,
    C_m3_s_Pa: Optional[float] = None,
    T_up: Optional[Iterable[float]] = None,
    beta_lam: float = model.ISO6358_BETA_LAM_DEFAULT,
) -> FitResult:
    """Подбор (b,m) по «сырым» измерениям.

    p_up, p_dn      : абсолютные давления (Па)
    qn_nl_min       : нормальный расход (Nl/min, ANR)
    C_m3_s_Pa       : если известен, используем как нормировку;
                      если None, оцениваем по максимальному qn как C ~= qn_max/(p_up_max*sqrt(Tref/T)).

    Возвращает FitResult(b,m,rmse,n).
    """
    p_up = np.asarray(list(p_up), dtype=float)
    p_dn = np.asarray(list(p_dn), dtype=float)
    qn = np.asarray(list(qn_nl_min), dtype=float)

    if T_up is None:
        T_up = np.ones_like(p_up) * model.T_AIR
    else:
        T_up = np.asarray(list(T_up), dtype=float)

    # фильтрация
    mask = np.isfinite(p_up) & np.isfinite(p_dn) & np.isfinite(qn) & (p_up > 1.0) & (p_dn > 0.0) & (p_up > p_dn)
    p_up = p_up[mask]
    p_dn = p_dn[mask]
    qn = qn[mask]
    T_up = T_up[mask]

    if p_up.size < 6:
        raise ValueError("Недостаточно валидных точек (нужно хотя бы 6 с p_up>p_dn).")

    pr = p_dn / p_up

    qn_m3_s = (qn / 1000.0) / 60.0

    if C_m3_s_Pa is None:
        # оценка C по максимальному расходу (предполагая, что в этих точках режим близок к choked)
        i = int(np.argmax(qn_m3_s))
        C_m3_s_Pa = float(qn_m3_s[i] / (p_up[i] * np.sqrt(model.T_ANR / T_up[i]) + 1e-30))

    # ratio = q / (C*p_up*sqrt(Tref/Tup))
    denom = (float(C_m3_s_Pa) * p_up * np.sqrt(model.T_ANR / T_up))
    ratio = np.where(denom > 0, qn_m3_s / denom, 0.0)

    return fit_b_m_from_ratio(pr, ratio, beta_lam=beta_lam)
