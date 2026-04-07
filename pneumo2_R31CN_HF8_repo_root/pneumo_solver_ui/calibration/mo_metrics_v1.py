# -*- coding: utf-8 -*-
"""mo_metrics_v1.py

Утилиты для **2D multiobjective** анализа (min-min) результатов.

Функции:
- pareto_nondominated_2d: фильтр недоминируемых точек
- knee_point_distance_to_line: knee-point (макс. расстояние до линии экстремумов
  в нормализованном пространстве целей; NBI-style для bi-objective)
- hypervolume_2d_min: hypervolume в 2D для минимизации
- hypervolume_contrib_2d_min: вклад каждой точки фронта в HV (наивно O(n^2))
- spacing_cv_2d: грубая метрика равномерности распределения точек по фронту
- compute_front_metrics_2d: собирает метрики в dataclass
- suggest_reference_point: простой выбор reference point (чуть хуже надирной)

Сделано специально без внешних зависимостей кроме numpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import math
import numpy as np


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def pareto_nondominated_2d(points: Sequence[Dict[str, Any]], objA: str, objB: str) -> List[Dict[str, Any]]:
    """Pareto filter для 2D min-min.

    Возвращает non-dominated множество, отсортированное по objA (возрастание).
    """
    pts = [p for p in points if _finite(p.get(objA)) and _finite(p.get(objB))]
    out: List[Dict[str, Any]] = []
    for i, p in enumerate(pts):
        a, b = float(p[objA]), float(p[objB])
        dominated = False
        for j, q in enumerate(pts):
            if i == j:
                continue
            aq, bq = float(q[objA]), float(q[objB])
            if (aq <= a and bq <= b) and (aq < a or bq < b):
                dominated = True
                break
        if not dominated:
            out.append(dict(p))
    out.sort(key=lambda r: float(r[objA]))
    return out


def knee_point_distance_to_line(front: Sequence[Dict[str, Any]], objA: str, objB: str) -> Optional[Dict[str, Any]]:
    """Knee point: max distance to the line between extremes in normalized objective space.

    Для bi-objective это практичный и устойчивый выбор компромиссной точки.

    Возвращает копию dict точки + поле 'knee_dist_norm'.
    """
    if not front:
        return None

    xs = np.asarray([float(p[objA]) for p in front], dtype=float)
    ys = np.asarray([float(p[objB]) for p in front], dtype=float)

    # normalize to [0,1]
    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())
    dx = max(1e-12, x1 - x0)
    dy = max(1e-12, y1 - y0)
    xn = (xs - x0) / dx
    yn = (ys - y0) / dy

    p0 = np.array([xn[0], yn[0]], dtype=float)
    p1 = np.array([xn[-1], yn[-1]], dtype=float)
    v = p1 - p0
    nv = float(np.linalg.norm(v))
    if nv < 1e-12:
        mid = dict(front[len(front) // 2])
        mid["knee_dist_norm"] = 0.0
        return mid
    v = v / nv

    best_i = 0
    best_d = -1.0
    for i in range(len(front)):
        w = np.array([xn[i], yn[i]], dtype=float) - p0
        proj = float(np.dot(w, v))
        perp = w - proj * v
        d = float(np.linalg.norm(perp))
        if d > best_d:
            best_d = d
            best_i = i

    knee = dict(front[best_i])
    knee["knee_dist_norm"] = float(best_d)
    knee["knee_objA_key"] = str(objA)
    knee["knee_objB_key"] = str(objB)
    return knee


def hypervolume_2d_min(front: Sequence[Dict[str, Any]], objA: str, objB: str, refA: float, refB: float) -> float:
    """Hypervolume для 2D minimization.

    refA/refB должны быть хуже всех точек (>= max по каждой цели).
    """
    pts = [(float(p[objA]), float(p[objB])) for p in front if _finite(p.get(objA)) and _finite(p.get(objB))]
    if not pts:
        return 0.0
    pts.sort(key=lambda t: t[0])

    hv = 0.0
    cur_y = float(refB)
    for a, b in pts:
        b = float(b)
        if b >= cur_y:
            continue
        hv += max(0.0, float(refA) - float(a)) * max(0.0, cur_y - b)
        cur_y = b
    return float(hv)


def hypervolume_contrib_2d_min(front: Sequence[Dict[str, Any]], objA: str, objB: str, refA: float, refB: float) -> List[float]:
    """HV contribution: HV(S) - HV(S\\{i}). Naive O(n^2), n обычно маленькое."""
    base = hypervolume_2d_min(front, objA, objB, refA, refB)
    contrib: List[float] = []
    for i in range(len(front)):
        sub = [dict(front[j]) for j in range(len(front)) if j != i]
        sub_nd = pareto_nondominated_2d(sub, objA, objB)
        hv_sub = hypervolume_2d_min(sub_nd, objA, objB, refA, refB)
        contrib.append(float(base - hv_sub))
    return contrib


def spacing_cv_2d(front: Sequence[Dict[str, Any]], objA: str, objB: str) -> float:
    """Spacing CV = std(dist)/mean(dist) по соседним точкам фронта в норм. 2D."""
    if len(front) < 3:
        return float("nan")

    xs = np.asarray([float(p[objA]) for p in front], dtype=float)
    ys = np.asarray([float(p[objB]) for p in front], dtype=float)

    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())
    dx = max(1e-12, x1 - x0)
    dy = max(1e-12, y1 - y0)
    xn = (xs - x0) / dx
    yn = (ys - y0) / dy

    idx = np.argsort(xn)
    xn = xn[idx]
    yn = yn[idx]

    d = np.sqrt(np.diff(xn) ** 2 + np.diff(yn) ** 2)
    m = float(np.mean(d))
    if m <= 1e-12:
        return float("nan")
    return float(np.std(d) / m)


@dataclass
class FrontMetrics2D:
    objA_key: str
    objB_key: str
    refA: float
    refB: float
    hv: float
    hv_norm: float
    spacing_cv: float
    n_points: int


def compute_front_metrics_2d(front: Sequence[Dict[str, Any]], objA: str, objB: str, refA: float, refB: float) -> FrontMetrics2D:
    hv = hypervolume_2d_min(front, objA, objB, refA, refB)

    if front:
        minA = float(min(float(p[objA]) for p in front))
        minB = float(min(float(p[objB]) for p in front))
    else:
        minA, minB = 0.0, 0.0

    denom = max(1e-12, (float(refA) - minA) * (float(refB) - minB))
    hv_norm = float(hv / denom)

    sp = spacing_cv_2d(front, objA, objB)

    return FrontMetrics2D(
        objA_key=str(objA),
        objB_key=str(objB),
        refA=float(refA),
        refB=float(refB),
        hv=float(hv),
        hv_norm=float(hv_norm),
        spacing_cv=float(sp),
        n_points=int(len(front)),
    )


def suggest_reference_point(points: Sequence[Dict[str, Any]], objA: str, objB: str, margin: float = 0.05) -> Tuple[float, float]:
    """Reference point = (maxA, maxB) with multiplicative margin."""
    valsA = [float(p[objA]) for p in points if _finite(p.get(objA))]
    valsB = [float(p[objB]) for p in points if _finite(p.get(objB))]
    if not valsA or not valsB:
        return 1.0, 1.0

    refA = max(valsA) * (1.0 + float(margin))
    refB = max(valsB) * (1.0 + float(margin))

    # if everything is zero-ish
    if refA == 0.0:
        refA = float(margin)
    if refB == 0.0:
        refB = float(margin)

    return float(refA), float(refB)
