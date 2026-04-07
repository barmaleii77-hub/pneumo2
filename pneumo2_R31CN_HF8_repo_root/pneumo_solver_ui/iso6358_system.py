# -*- coding: utf-8 -*-
"""iso6358_system.py

Инструменты для расчёта эквивалентных характеристик системы по ISO 6358 (серия/параллель).

Зачем это нужно в проекте «пневматика + механика»
-----------------------------------------------
Динамический солвер в проекте работает по узлам/рёбрам (ODE по массе/температуре/координатам),
а каждый дросселирующий элемент задаётся либо:
- геометрией (A, Cd) и уравнением сопла, либо
- ISO 6358 параметрами (C, b, m, Δpc).

На практике реальные магистрали часто состоят из нескольких элементов последовательно:
штуцер → трубка → обратный клапан → дроссель → фитинг → порт цилиндра.
Для инженерной проверки полезно уметь:
1) посчитать «эквивалентный» элемент (Ceq, beq, meq, Δpc_eq) для серии/параллели;
2) увидеть, кто «самый ограничивающий»;
3) построить кривую qm(p2/p1) для системы и сравнить с упрощениями.

Реализация ниже следует принципу ISO 6358-3:2014:
- одинаковая стагнационная температура Te по всей системе (адиабатическая гипотеза),
- для серии: один и тот же массовый расход через все элементы,
- для параллели: одинаковые pe и pf у ветвей, суммарный расход = сумма расходов ветвей.
См. описание принципа расчёта и шаги 6.6 (серия) в ISO 6358-3.

Важно про cracking pressure Δpc
------------------------------
ISO 6358 вводит Δpc как порог открытия (для check / one-way элементов).
В динамической модели проекта Δpc использовался как «порог открытия» (сглаженный).
Для *инженерно ближней к ISO* трактовки здесь (и в патче модели) Δpc также
уменьшает доступный перепад для течения:
    Δp_eff = max(0, (p1 - p2) - Δpc)
то есть эффективное входное давление для расчёта расхода:
    p1_eff = p2 + Δp_eff = p1 - Δpc   (при хорошо открытом клапане).

Скорость не приоритет: используются устойчивые численные методы (бисекция/сетка).

Единицы
-------
C: м^3/(с·Па) при ANR (p0=100 kPa, T0=293.15 K, ρ0≈1.185 kg/m^3).
b: безразмерная (0..1).
m: безразмерная (>0).
Δpc: Па.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Callable
import math

# --- Single source of truth for ISO reference conditions & φ(pr) ---
#
# В проекте важно, чтобы ANR (ISO 8778) и φ(pr) (ISO 6358)
# не расходились между модулями. Поэтому здесь мы переиспользуем
# iso6358_core как единый источник констант и формы φ(pr).
try:
    from .iso6358_core import (
        T_ANR,
        RHO_ANR,
        rho_ANR_ref,
        ISO6358_BETA_LAM_DEFAULT,
        iso6358_phi as _iso6358_phi_core,
    )
except Exception:
    from iso6358_core import (
        T_ANR,
        RHO_ANR,
        rho_ANR_ref,
        ISO6358_BETA_LAM_DEFAULT,
        iso6358_phi as _iso6358_phi_core,
    )


@dataclass(frozen=True)
class ISOElement:
    """Параметры одного элемента в модели ISO 6358."""
    name: str
    C: float               # m^3/(s·Pa)
    b: float = 0.3         # critical pressure ratio
    m: float = 0.5         # subsonic index
    dp_crack: float = 0.0  # Pa


def iso6358_phi(pr: float, b: float, m: float, beta_lam: float = ISO6358_BETA_LAM_DEFAULT) -> float:
    """Обёртка над iso6358_core.iso6358_phi.

    Важно: pr<=0 трактуем как сильный перепад (вакуум) => choked => φ=1.
    Это согласовано с остальными частями проекта и защищает от NaN при вакууме.

    Сигнатура сохранена для обратной совместимости с существующим кодом.
    """
    return float(_iso6358_phi_core(pr, b, m, beta_lam=beta_lam))

def mdot_iso6358(p_up: float, p_dn: float, elem: ISOElement, Te: float,
                beta_lam: float = ISO6358_BETA_LAM_DEFAULT) -> float:
    """Массовый расход через элемент ISO 6358 (только направление p_up → p_dn, p_up>p_dn).

    Учитывает cracking pressure как «съеденный» перепад: Δp_eff = max(0, Δp - Δpc).
    """
    if p_up <= p_dn:
        return 0.0
    dp = p_up - p_dn
    if dp <= elem.dp_crack:
        return 0.0

    p_up_eff = p_up - elem.dp_crack
    if p_up_eff <= p_dn:
        return 0.0

    pr = p_dn / p_up_eff
    phi = iso6358_phi(pr, elem.b, elem.m, beta_lam=beta_lam)
    # qn = C * p_up_eff * phi * sqrt(T_ANR/Te); mdot = rho_ANR * qn
    return rho_ANR_ref(True) * elem.C * p_up_eff * phi * math.sqrt(T_ANR / Te)


def p_down_from_mdot(p_up: float, mdot: float, elem: ISOElement, Te: float,
                     beta_lam: float = ISO6358_BETA_LAM_DEFAULT,
                     iters: int = 80) -> Optional[float]:
    """Инверсия ISO 6358: по mdot и p_up найти p_down (только *субзвуковой* режим).

    Возвращает p_down (Па) или None, если mdot недостижим без захлёба (choked) на элементе.

    Примечание:
    - для элемента с Δpc используем p_up_eff = p_up - Δpc (если mdot>0).
    - условие «subsonic» для элемента (см. ISO 6358-3, формула (26)) эквивалентно mdot < mdot_choked.
    """
    if mdot <= 0.0:
        # В пределах ISO кривой это означает отсутствие течения; p_down не определён однозначно.
        return p_up

    # Для течения нужно dp > Δpc, иначе mdot=0
    p_up_eff = p_up - elem.dp_crack
    if p_up_eff <= 0.0:
        return None

    mdot_choked = rho_ANR_ref(True) * elem.C * p_up_eff * math.sqrt(T_ANR / Te)
    if mdot >= mdot_choked:
        return None

    # Target phi in (0,1)
    phi_target = mdot / mdot_choked
    phi_target = min(0.999999999, max(0.0, phi_target))

    lo = max(0.0, elem.b)
    hi = 1.0

    # Bisection on pr_eff in [b, 1]
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        phi_mid = iso6358_phi(mid, elem.b, elem.m, beta_lam=beta_lam)
        if phi_mid > phi_target:
            lo = mid
        else:
            hi = mid
    pr_eff = 0.5 * (lo + hi)
    p_dn = pr_eff * p_up_eff
    return p_dn


def series_pf_from_mdot(pe: float, Te: float, elems: Sequence[ISOElement], mdot: float,
                        beta_lam: float = ISO6358_BETA_LAM_DEFAULT) -> Optional[float]:
    """Серия: вычислить pf для заданного mdot.

    Возвращает pf или None, если mdot слишком велик (на каком-то элементе начинается choked).
    """
    p = float(pe)
    for e in elems:
        p2 = p_down_from_mdot(p, mdot, e, Te, beta_lam=beta_lam)
        if p2 is None or not math.isfinite(p2) or p2 < 0.0:
            return None
        # Санитарная проверка: давление не должно расти на пассивном элементе
        if p2 > p + 1e-9:
            return None
        p = p2
    return p


def series_choked_mdot(pe: float, Te: float, elems: Sequence[ISOElement],
                       beta_lam: float = ISO6358_BETA_LAM_DEFAULT,
                       iters: int = 80) -> Tuple[float, float]:
    """Серия: найти максимальный *субзвуковой* расход mdot* (ISO 6358-3, шаг 6.6).

    Возвращает (mdot_star, pf_star).
    """
    if not elems:
        return 0.0, pe

    Cmin = min(e.C for e in elems)
    mdot_max_theory = rho_ANR_ref(True) * Cmin * pe * math.sqrt(T_ANR / Te)  # ISO 6358-3 (22)
    lo = 0.0
    hi = mdot_max_theory

    # Ensure hi is infeasible or at least not smaller than lo; if hi feasible, expand a bit (rare)
    pf_hi = series_pf_from_mdot(pe, Te, elems, hi, beta_lam=beta_lam)
    if pf_hi is not None:
        # theoretically shouldn't happen for series if Cmin is from an element without Δpc, but keep safe
        hi *= 1.5

    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        pf_mid = series_pf_from_mdot(pe, Te, elems, mid, beta_lam=beta_lam)
        if pf_mid is None:
            hi = mid
        else:
            lo = mid
    mdot_star = lo
    pf_star = series_pf_from_mdot(pe, Te, elems, mdot_star, beta_lam=beta_lam)
    if pf_star is None:
        pf_star = 0.0
    return mdot_star, float(pf_star)


def fit_b_m_from_points(pr_list: Sequence[float], phi_list: Sequence[float],
                        beta_lam: float = ISO6358_BETA_LAM_DEFAULT) -> Tuple[float, float]:
    """Подбор (b,m) по точкам (pr,phi) с грубой→точной сеткой.

    pr_list: p_down/p_up (в субзвуке: обычно pr> b).
    phi_list: нормированный расход (0..1).
    """
    # Clean points
    pts = [(float(pr), float(phi)) for pr, phi in zip(pr_list, phi_list)
           if 0.0 < pr < 1.0 and 0.0 <= phi <= 1.0 and math.isfinite(pr) and math.isfinite(phi)]
    if len(pts) < 2:
        return 0.3, 0.5

    def loss(b: float, m: float) -> float:
        s = 0.0
        for pr, phi in pts:
            pred = iso6358_phi(pr, b, m, beta_lam=beta_lam)
            d = pred - phi
            s += d * d
        return s / len(pts)

    best_b, best_m = 0.3, 0.5
    best_L = float("inf")

    # Coarse grid
    for b in [i / 200.0 for i in range(10, 195)]:  # 0.05..0.975 step 0.005
        for m in [0.2 + 0.02 * j for j in range(0, 91)]:  # 0.2..2.0 step 0.02
            L = loss(b, m)
            if L < best_L:
                best_L, best_b, best_m = L, b, m

    # Local refine around best
    b0, m0 = best_b, best_m
    for b in [b0 + 0.001 * i for i in range(-20, 21)]:
        if b <= 0.01 or b >= 0.999:
            continue
        for m in [m0 + 0.01 * j for j in range(-20, 21)]:
            if m <= 0.05 or m >= 5.0:
                continue
            L = loss(b, m)
            if L < best_L:
                best_L, best_b, best_m = L, b, m

    return float(best_b), float(best_m)


def series_equivalent_iso(pe: float, Te: float, elems: Sequence[ISOElement],
                          beta_lam: float = ISO6358_BETA_LAM_DEFAULT,
                          sample_fracs: Sequence[float] = (0.95, 0.8, 0.6, 0.4, 0.2)
                          ) -> ISOElement:
    """Эквивалентные ISO параметры для системы *последовательно* соединённых элементов.

    Возвращает ISOElement(name='series_eq', C=..., b=..., m=..., dp_crack=ΣΔpc).
    """
    if not elems:
        return ISOElement("series_eq", C=0.0, b=0.3, m=0.5, dp_crack=0.0)

    dp_total = sum(float(e.dp_crack) for e in elems)

    mdot_star, pf_star = series_choked_mdot(pe, Te, elems, beta_lam=beta_lam)
    if mdot_star <= 0.0:
        return ISOElement("series_eq", C=0.0, b=0.3, m=0.5, dp_crack=dp_total)

    # Equivalent C from definition (ISO 6358: qm* = rho0 * C * pe * sqrt(T0/Te))
    C_eq = mdot_star / (rho_ANR_ref(True) * pe * math.sqrt(T_ANR / Te))

    pr_pts = []
    phi_pts = []
    for f in sample_fracs:
        md = max(1e-12, float(f) * mdot_star)
        pf = series_pf_from_mdot(pe, Te, elems, md, beta_lam=beta_lam)
        if pf is None:
            continue
        pr = pf / pe
        phi = md / (rho_ANR_ref(True) * C_eq * pe * math.sqrt(T_ANR / Te))
        pr_pts.append(pr)
        phi_pts.append(phi)

    b_eq, m_eq = fit_b_m_from_points(pr_pts, phi_pts, beta_lam=beta_lam)

    return ISOElement("series_eq", C=float(C_eq), b=b_eq, m=m_eq, dp_crack=float(dp_total))


# --- Parallel support: branches as series chains ---

def series_mdot_for_pf(pe: float, Te: float, elems: Sequence[ISOElement], pf: float,
                       beta_lam: float = ISO6358_BETA_LAM_DEFAULT,
                       iters: int = 80) -> float:
    """Найти mdot для серии при заданном pf (монотонная бисекция).

    Если pf ниже pf_star (в зоне захлёба), возвращает mdot_star.
    """
    pf = float(pf)
    if pf >= pe:
        return 0.0
    mdot_star, pf_star = series_choked_mdot(pe, Te, elems, beta_lam=beta_lam)
    if pf <= pf_star:
        return mdot_star

    lo, hi = 0.0, mdot_star
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        pf_mid = series_pf_from_mdot(pe, Te, elems, mid, beta_lam=beta_lam)
        if pf_mid is None:
            hi = mid
        else:
            # pf_mid decreases with mdot; if pf_mid > pf, need more mdot
            if pf_mid > pf:
                lo = mid
            else:
                hi = mid
    return 0.5 * (lo + hi)


def parallel_total_mdot(pe: float, Te: float, branches: Sequence[Sequence[ISOElement]], pf: float,
                        beta_lam: float = ISO6358_BETA_LAM_DEFAULT) -> float:
    """Параллель: суммарный расход через набор ветвей (ветви могут быть сериями)."""
    total = 0.0
    for br in branches:
        total += series_mdot_for_pf(pe, Te, br, pf, beta_lam=beta_lam)
    return total


def parallel_equivalent_iso(pe: float, Te: float, branches: Sequence[Sequence[ISOElement]],
                            beta_lam: float = ISO6358_BETA_LAM_DEFAULT,
                            pr_samples: Sequence[float] = (0.95, 0.85, 0.7, 0.5, 0.3, 0.2)
                            ) -> ISOElement:
    """Эквивалентные ISO параметры для параллельного соединения ветвей.

    Каждая ветвь задаётся списком ISOElement (серия внутри ветви).
    """
    if not branches:
        return ISOElement("parallel_eq", C=0.0, b=0.3, m=0.5, dp_crack=0.0)

    # Cracking pressure для параллели: берём минимум порога по ветвям (если ветви независимы),
    # но для сохранения совместимости возвращаем 0 и предлагаем учитывать пороги на уровне ветвей.
    dp_eq = 0.0

    # Оценка C: при очень малом pf почти все ветви будут в захлёбе ⇒ qm ≈ rho0 * pe * sqrt(T0/Te) * sum(C_branch_eq)
    # Поэтому считаем C_eq как qm(pf->0)/[rho0*pe*sqrt(T0/Te)].
    pf_low = pe * 0.05
    mdot_low = parallel_total_mdot(pe, Te, branches, pf_low, beta_lam=beta_lam)
    C_eq = mdot_low / (rho_ANR_ref(True) * pe * math.sqrt(T_ANR / Te))

    pr_pts = []
    phi_pts = []
    for pr in pr_samples:
        pf = pe * float(pr)
        md = parallel_total_mdot(pe, Te, branches, pf, beta_lam=beta_lam)
        phi = md / (rho_ANR_ref(True) * C_eq * pe * math.sqrt(T_ANR / Te)) if C_eq > 0 else 0.0
        pr_pts.append(pf / pe)
        phi_pts.append(phi)

    b_eq, m_eq = fit_b_m_from_points(pr_pts, phi_pts, beta_lam=beta_lam)

    return ISOElement("parallel_eq", C=float(C_eq), b=b_eq, m=m_eq, dp_crack=float(dp_eq))


if __name__ == "__main__":
    # Мини-демо: две одинаковые «дырки» последовательно и параллельно.
    pe = 7.0e5   # Pa abs
    Te = 293.15  # K

    e1 = ISOElement("or1", C=1.0e-8, b=0.3, m=0.5)
    e2 = ISOElement("or2", C=1.0e-8, b=0.3, m=0.5)

    s_eq = series_equivalent_iso(pe, Te, [e1, e2])
    p_eq = parallel_equivalent_iso(pe, Te, [[e1], [e2]])

    print("Series eq:", s_eq)
    print("Parallel eq:", p_eq)
