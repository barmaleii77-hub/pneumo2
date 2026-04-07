# -*- coding: utf-8 -*-
"""pneumo_gas_stiffness.py

Утилиты для малосигнальной (линеаризованной) жёсткости газа в полостях.

Зачем
-----
В проекте требуется физически правдоподобная «нулевая поза» (t=0, ровная дорога),
в т.ч. корректное распределение веса по 4 углам в режиме
`corner_loads_mode="stiffness"`.

Если включена авто‑оценка `corner_stiffness_auto`, подвеска в углу может быть
аппроксимирована эквивалентной вертикальной жёсткостью.

Эта жёсткость складывается из:
- механической пружины (табличная характеристика → dF/dx),
- **газовой жёсткости пневмоцилиндров** (сжатие воздуха в полостях),
- далее последовательно с жёсткостью шины.

Модель газа здесь намеренно простая:
- малые колебания;
- **герметичная** полость (масса газа постоянна);
- политропический процесс с показателем `n` (1…γ).

Для идеального газа: p V^n = const → dp/dV = -(n p)/V.
Если F = p A, V изменяется как V = V0 ± A s,
то |dF/ds| ≈ n p A^2 / V.

Для двустороннего цилиндра (две полости) малосигнальная осевая жёсткость
приближённо равна сумме вкладов обеих камер.

Важно
------
Это используется **только для инициализации** (corner stiffness для распределения веса).
Точную динамику (в т.ч. перетекание через клапаны/дроссели/регуляторы)
считает полная дифференциальная модель.
"""

from __future__ import annotations

import math
from typing import Optional


def _finite(x: float) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def p_abs_from_param(p_value: Optional[float], *, p_atm_Pa: float = 101325.0, gauge_if_below_Pa: float = 5e4) -> float:
    """Интерпретирует давление из параметра.

    Если p_value подозрительно малое (< gauge_if_below_Pa), считаем что это *избыточное* (gauge)
    и переводим в абсолютное добавлением p_atm.

    Иначе считаем, что p_value уже абсолютное.

    Возвращает неотрицательное абсолютное давление.
    """
    if p_value is None:
        return float(p_atm_Pa)
    try:
        p = float(p_value)
    except Exception:
        return float(p_atm_Pa)

    if not _finite(p):
        return float(p_atm_Pa)

    if p < 0.0:
        # не валим расчёт, но не даём отрицательным величинам лезть в жёсткость
        p = 0.0

    if p < float(gauge_if_below_Pa):
        p = p + float(p_atm_Pa)

    return float(max(0.0, p))


def gas_stiffness_axial_double_acting(
    *,
    p_cap_abs_Pa: float,
    p_rod_abs_Pa: float,
    A_cap_m2: float,
    A_rod_m2: float,
    V_cap_m3: float,
    V_rod_m3: float,
    n_poly: float = 1.4,
    volume_factor: float = 1.0,
    min_V_m3: float = 1e-12,
    min_p_Pa: float = 1.0,
) -> float:
    """Малосигнальная осевая жёсткость двустороннего цилиндра (N/m).

    Предполагается:
    - обе камеры герметичны (масса постоянна),
    - политропа с показателем n_poly,
    - давление абсолютное.

    Формула (по модулю):
      k_ax = n * ( p_cap * A_cap^2 / V_cap + p_rod * A_rod^2 / V_rod )

    volume_factor позволяет «увеличить» эффективный объём (например, если камера
    соединена с ресивером и в малых колебаниях масса считается общей).
    При volume_factor > 1 жёсткость уменьшается.

    Возвращает >= 0.
    """
    p_cap = float(max(min_p_Pa, p_cap_abs_Pa))
    p_rod = float(max(min_p_Pa, p_rod_abs_Pa))

    A_cap = float(max(0.0, A_cap_m2))
    A_rod = float(max(0.0, A_rod_m2))

    V_cap = float(max(min_V_m3, V_cap_m3))
    V_rod = float(max(min_V_m3, V_rod_m3))

    n = float(n_poly)
    if not _finite(n):
        n = 1.4
    n = float(max(1.0, min(n, 2.0)))

    vf = float(volume_factor)
    if not _finite(vf):
        vf = 1.0
    vf = float(max(1e-6, vf))

    k = n * (p_cap * (A_cap * A_cap) / V_cap + p_rod * (A_rod * A_rod) / V_rod)
    k = k / vf

    if not _finite(k):
        return 0.0
    return float(max(0.0, k))


def gas_stiffness_axial_from_geometry(
    *,
    p_ref_abs_Pa: float,
    A_cap_m2: float,
    A_rod_m2: float,
    V_dead_m3: float,
    stroke_m: float,
    s_ref_m: Optional[float] = None,
    n_poly: float = 1.4,
    volume_factor: float = 1.0,
) -> float:
    """Упрощённая жёсткость оси цилиндра по геометрии (N/m).

    Камеры считаются:
      V_cap = V_dead + A_cap * s
      V_rod = V_dead + A_rod * (stroke - s)

    По умолчанию берём s=0.5*stroke (середина хода).

    p_ref_abs_Pa — опорное абсолютное давление (используется одинаковым для обеих камер).
    """
    stroke = float(max(0.0, stroke_m))
    if s_ref_m is None:
        s = 0.5 * stroke
    else:
        try:
            s = float(s_ref_m)
        except Exception:
            s = 0.5 * stroke
    # clip
    s = float(min(max(0.0, s), stroke))

    V_dead = float(max(0.0, V_dead_m3))
    A_cap = float(max(0.0, A_cap_m2))
    A_rod = float(max(0.0, A_rod_m2))

    V_cap = V_dead + A_cap * s
    V_rod = V_dead + A_rod * (stroke - s)

    return gas_stiffness_axial_double_acting(
        p_cap_abs_Pa=float(p_ref_abs_Pa),
        p_rod_abs_Pa=float(p_ref_abs_Pa),
        A_cap_m2=A_cap,
        A_rod_m2=A_rod,
        V_cap_m3=V_cap,
        V_rod_m3=V_rod,
        n_poly=float(n_poly),
        volume_factor=float(volume_factor),
    )


# --- Backward/short alias (used in tests/docs) ---

def gas_stiffness_axial_double(
    p_cap_abs_Pa: float,
    p_rod_abs_Pa: float,
    A_cap_m2: float,
    A_rod_m2: float,
    V_cap_m3: float,
    V_rod_m3: float,
    n_poly: float = 1.4,
    volume_factor: float = 1.0,
) -> float:
    """Alias for :func:`gas_stiffness_axial_double_acting`.

    Kept for convenience and to avoid churn in call sites.
    """
    return gas_stiffness_axial_double_acting(
        p_cap_abs_Pa=p_cap_abs_Pa,
        p_rod_abs_Pa=p_rod_abs_Pa,
        A_cap_m2=A_cap_m2,
        A_rod_m2=A_rod_m2,
        V_cap_m3=V_cap_m3,
        V_rod_m3=V_rod_m3,
        n_poly=n_poly,
        volume_factor=volume_factor,
    )
