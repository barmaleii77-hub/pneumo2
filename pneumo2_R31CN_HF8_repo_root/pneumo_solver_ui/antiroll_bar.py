# -*- coding: utf-8 -*-
"""antiroll_bar.py

Опциональная модель стабилизатора поперечной устойчивости (анти-ролл бар).

Контекст проекта
----------------
В этой ветке проекта «Механика» у нас 7-DOF кузов (z, φ, θ) + 4 колеса zw.
Силы подвески считаются в углах и суммируются в уравнения движения.

Стабилизатор поперечной устойчивости связывает левую и правую сторону одной оси
и даёт *дополнительную* вертикальную силу в углах, пропорциональную разности
ходов подвески (delta_L - delta_R). В идеале:

  - в чистом heave (delta_L == delta_R) стабилизатор не влияет (F=0);
  - в крене (delta_L != delta_R) добавляет жёсткость по крену;
  - сумма сил на оси равна 0 (F_L + F_R = 0), т.е. стабилизатор не меняет
    вертикальную силу на кузов в среднем, а только перераспределяет её.

Почему по умолчанию выключен
----------------------------
По вашему ТЗ пневмосхема сама выполняет функцию стабилизатора (за счёт
диагональных/поперечных связей), поэтому механический ARB включается
только по явному флагу.

Знак и соглашения
-----------------
В модели используется:

  delta = z_колеса - z_рамы_в_углу   (м)
  delta > 0  => сжатие подвески

Функция возвращает силы *на кузов* (F_susp-совместимый знак):

  F_arb_left  =  k*(delta_L - delta_R) + c*(delta_dot_L - delta_dot_R)
  F_arb_right = -F_arb_left

Тогда:
  - при delta_L > delta_R на левом углу добавляется сила вверх,
    на правом — вниз (сумма 0);
  - на колёса сила действует с противоположным знаком (в уравнении колеса
    она появляется как -F_susp).
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np


def _get_bool(params: Dict[str, Any], *keys: str, default: bool = False) -> bool:
    for k in keys:
        if k in params:
            try:
                return bool(params[k])
            except Exception:
                pass
    return bool(default)


def _get_float(params: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in params and (params[k] is not None):
            try:
                return float(params[k])
            except Exception:
                pass
    return float(default)


def antiroll_forces(
    delta: np.ndarray,
    delta_dot: np.ndarray,
    *,
    params: Dict[str, Any],
    corner_order: Sequence[str] = ("ЛП", "ПП", "ЛЗ", "ПЗ"),
) -> np.ndarray:
    """Вернуть вектор сил стабилизатора на кузов в углах (Н).

    Параметры (RU + EN алиасы)
    --------------------------
      - стабилизатор_перед_вкл (bool) / arb_front_enable
      - стабилизатор_перед_k_Н_м (float) / arb_front_k_N_m
      - стабилизатор_перед_c_Н_с_м (float) / arb_front_c_N_s_m

      - стабилизатор_зад_вкл (bool) / arb_rear_enable
      - стабилизатор_зад_k_Н_м (float) / arb_rear_k_N_m
      - стабилизатор_зад_c_Н_с_м (float) / arb_rear_c_N_s_m
    """

    delta = np.asarray(delta, dtype=float)
    delta_dot = np.asarray(delta_dot, dtype=float)
    F = np.zeros_like(delta, dtype=float)

    # Индексы углов
    try:
        i_LF = int(corner_order.index("ЛП"))
        i_RF = int(corner_order.index("ПП"))
        i_LR = int(corner_order.index("ЛЗ"))
        i_RR = int(corner_order.index("ПЗ"))
    except Exception:
        # Если порядок неожиданный — fallback на стандартный (как в моделях)
        i_LF, i_RF, i_LR, i_RR = 0, 1, 2, 3

    # --- Front axle ---
    en_f = _get_bool(params, "стабилизатор_перед_вкл", "arb_front_enable", "antiroll_front_enable", default=False)
    k_f = _get_float(params, "стабилизатор_перед_k_Н_м", "arb_front_k_N_m", "antiroll_front_k_N_m", default=0.0)
    c_f = _get_float(params, "стабилизатор_перед_c_Н_с_м", "arb_front_c_N_s_m", "antiroll_front_c_N_s_m", default=0.0)
    if en_f and (k_f != 0.0 or c_f != 0.0):
        diff = float(delta[i_LF] - delta[i_RF])
        diff_dot = float(delta_dot[i_LF] - delta_dot[i_RF])
        f = k_f * diff + c_f * diff_dot
        F[i_LF] += f
        F[i_RF] -= f

    # --- Rear axle ---
    en_r = _get_bool(params, "стабилизатор_зад_вкл", "arb_rear_enable", "antiroll_rear_enable", default=False)
    k_r = _get_float(params, "стабилизатор_зад_k_Н_м", "arb_rear_k_N_m", "antiroll_rear_k_N_m", default=0.0)
    c_r = _get_float(params, "стабилизатор_зад_c_Н_с_м", "arb_rear_c_N_s_m", "antiroll_rear_c_N_s_m", default=0.0)
    if en_r and (k_r != 0.0 or c_r != 0.0):
        diff = float(delta[i_LR] - delta[i_RR])
        diff_dot = float(delta_dot[i_LR] - delta_dot[i_RR])
        f = k_r * diff + c_r * diff_dot
        F[i_LR] += f
        F[i_RR] -= f

    return F
