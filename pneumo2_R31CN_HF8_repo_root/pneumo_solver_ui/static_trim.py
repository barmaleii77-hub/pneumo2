# -*- coding: utf-8 -*-
"""static_trim.py

Статический «трим» (уточнение) начального состояния t=0.

Зачем
-----
Даже при аналитической инициализации (x0, p0, геометрия) иногда остаются
небольшие несогласования сил/моментов (из‑за нелинейностей, сглаживаний,
упоров, контактной модели, численных floor/clip и т.п.).

Этот модуль даёт лёгкий универсальный помощник для:
  - оценки «качества статики» (ускорения в t=0),
  - (опционально) подстройки 7 механических переменных: z,phi,theta,zw[4]
    через least_squares так, чтобы ускорения стали близки к нулю,
    при этом удерживая δ (ход колеса относительно рамы) около 0
    и углы около 0.

Важно
-----
Модуль не знает структуры state конкретной модели. Модель должна дать
callable residual(x)->np.ndarray и builder(x)->state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

import math
import numpy as np


@dataclass
class StaticTrimReport:
    ok: bool
    attempted: bool
    success: bool
    nfev: int
    cost: float
    message: str
    x0: Sequence[float]
    x: Sequence[float]
    max_abs_res0: float
    max_abs_res: float
    rms_res0: float
    rms_res: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_float(x: Any, default: float = float('nan')) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _rms(v: np.ndarray) -> float:
    v = np.asarray(v, dtype=float).reshape(-1)
    if v.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(v * v))))


def run_least_squares(
    residual: Callable[[np.ndarray], np.ndarray],
    x0: Sequence[float],
    *,
    bounds: Optional[Tuple[Sequence[float], Sequence[float]]] = None,
    max_nfev: int = 80,
    ftol: float = 1e-10,
    xtol: float = 1e-10,
    gtol: float = 1e-10,
    verbose: int = 0,
) -> StaticTrimReport:
    """Запустить least_squares (если scipy доступен) и вернуть отчёт.

    Если scipy недоступен или solver упал — ok=False.
    """

    x0 = np.asarray(list(x0), dtype=float)
    r0 = np.asarray(residual(x0), dtype=float)
    max0 = float(np.max(np.abs(r0))) if r0.size else 0.0
    rms0 = _rms(r0)

    try:
        from scipy.optimize import least_squares  # type: ignore
    except Exception as ex:
        return StaticTrimReport(
            ok=False,
            attempted=False,
            success=False,
            nfev=0,
            cost=float('nan'),
            message=f"scipy.optimize.least_squares not available: {ex!r}",
            x0=x0.tolist(),
            x=x0.tolist(),
            max_abs_res0=max0,
            max_abs_res=max0,
            rms_res0=rms0,
            rms_res=rms0,
        )

    try:
        if bounds is None:
            lb = -np.inf * np.ones_like(x0)
            ub = np.inf * np.ones_like(x0)
        else:
            lb = np.asarray(bounds[0], dtype=float)
            ub = np.asarray(bounds[1], dtype=float)

        sol = least_squares(
            fun=lambda x: np.asarray(residual(np.asarray(x, dtype=float)), dtype=float),
            x0=x0,
            bounds=(lb, ub),
            max_nfev=int(max_nfev),
            ftol=float(ftol),
            xtol=float(xtol),
            gtol=float(gtol),
            verbose=int(verbose),
        )
        x = np.asarray(sol.x, dtype=float)
        r = np.asarray(sol.fun, dtype=float)
        max1 = float(np.max(np.abs(r))) if r.size else 0.0
        rms1 = _rms(r)
        return StaticTrimReport(
            ok=True,
            attempted=True,
            success=bool(sol.success),
            nfev=int(getattr(sol, 'nfev', 0) or 0),
            cost=_safe_float(getattr(sol, 'cost', float('nan'))),
            message=str(getattr(sol, 'message', '')),
            x0=x0.tolist(),
            x=x.tolist(),
            max_abs_res0=max0,
            max_abs_res=max1,
            rms_res0=rms0,
            rms_res=rms1,
        )
    except Exception as ex:
        # solver crashed
        return StaticTrimReport(
            ok=False,
            attempted=True,
            success=False,
            nfev=0,
            cost=float('nan'),
            message=f"least_squares failed: {ex!r}",
            x0=x0.tolist(),
            x=x0.tolist(),
            max_abs_res0=max0,
            max_abs_res=max0,
            rms_res0=rms0,
            rms_res=rms0,
        )
