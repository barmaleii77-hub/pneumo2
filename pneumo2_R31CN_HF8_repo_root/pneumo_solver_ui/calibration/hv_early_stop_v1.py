# -*- coding: utf-8 -*-
"""hv_early_stop_v1.py

Утилита для ранней остановки multiobjective sweep по прогрессу hypervolume (HV).

Сценарий:
- при Pareto/epsilon sweep мы постепенно добавляем точки,
- считаем HV недоминируемого фронта,
- если относительное улучшение HV слишком мало на протяжении `patience` шагов — прекращаем
  добавлять новые точки (экономим симуляции).

Важно:
- HV корректен, если ref point заведомо хуже всех точек (для min-min целей).
- В проекте HV используется в 2D (давления vs кинематика), поэтому реализовано 2D.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class HVStopState:
    hv_history: List[float]
    no_improve_steps: int = 0


def update_hv_stop(
    state: HVStopState,
    hv_new: float,
    min_rel_improv: float = 0.005,
    patience: int = 3,
) -> bool:
    """Update HV history and return True if should stop."""
    hv_new = float(hv_new)
    if not state.hv_history:
        state.hv_history.append(hv_new)
        state.no_improve_steps = 0
        return False

    hv_prev = float(state.hv_history[-1])
    denom = abs(hv_prev) if abs(hv_prev) > 1e-12 else 1.0
    rel = (hv_new - hv_prev) / denom

    state.hv_history.append(hv_new)
    if rel < float(min_rel_improv):
        state.no_improve_steps += 1
    else:
        state.no_improve_steps = 0

    return state.no_improve_steps >= int(patience)
