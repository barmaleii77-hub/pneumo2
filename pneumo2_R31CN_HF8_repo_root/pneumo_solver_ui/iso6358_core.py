# -*- coding: utf-8 -*-
"""iso6358_core.py

Единый набор функций/констант для:
- ISO 8778 (ANR: 100 kPa, 20°C, RH=65%)
- ISO 6358 (практическая функция φ(pr; b,m) + численная ламинаризация у pr→1)

Цель: убрать рассинхронизацию между разными копиями iso6358_phi и ρ_ANR.

Важно:
- pr<=0 трактуем как сильный перепад (вакуум/ошибка чисел) => режим choked => φ=1.
- pr>=1 => Δp→0 => φ=0.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional

# --- ISO 8778:2003 Standard reference atmosphere (ANR) ---
P_ANR: float = 100_000.0   # Pa
T_ANR: float = 293.15      # K (20°C)
RH_ANR: float = 65.0       # %

# --- ISO 8778 Annex A: "engineering reference atmosphere" (humidity ignored) ---
RH_AER: float = 0.0        # %

# Gas constants
R_DRY_AIR: float = 287.05      # J/(kg*K)
R_WATER_VAPOR: float = 461.495 # J/(kg*K)

# Default smoothing parameter used by project’s ISO‑6358 helper
ISO6358_BETA_LAM_DEFAULT: float = 0.999


def p_sat_water_buck_Pa(T_K: float) -> float:
    """Насыщенное давление водяного пара над водой (Buck, 1981), Па.

    Вход: T_K (К). Выход: Па.
    """
    T_C = float(T_K) - 273.15
    return 611.21 * math.exp((18.678 - T_C / 234.5) * (T_C / (257.14 + T_C)))


def rho_humid_air_kg_m3(p_Pa: float, T_K: float, RH_percent: Optional[float]) -> float:
    """Плотность влажного воздуха как идеальной смеси, кг/м^3.

    ρ = p_d/(R_d*T) + p_v/(R_v*T)
    где p_v = RH*p_sat(T), p_d = p - p_v.

    Если RH_percent=None или NaN -> сухой воздух: ρ = p/(R*T).
    """
    p_Pa = float(p_Pa)
    T_K = float(T_K)
    if (not math.isfinite(p_Pa)) or p_Pa <= 0.0 or (not math.isfinite(T_K)) or T_K <= 1.0:
        return float('nan')

    if RH_percent is None:
        return p_Pa / (R_DRY_AIR * T_K)

    try:
        RH = float(RH_percent)
    except Exception:
        return p_Pa / (R_DRY_AIR * T_K)

    if not math.isfinite(RH):
        return p_Pa / (R_DRY_AIR * T_K)

    RH = max(0.0, min(100.0, RH))
    p_sat = p_sat_water_buck_Pa(T_K)
    p_v = (RH / 100.0) * p_sat
    p_v = max(0.0, min(0.99 * p_Pa, p_v))
    p_d = p_Pa - p_v

    return p_d / (R_DRY_AIR * T_K) + p_v / (R_WATER_VAPOR * T_K)


def rho_ANR_kg_m3(*, use_iso8778: bool = True) -> float:
    """Плотность воздуха при ANR.

    use_iso8778=True  -> ISO 8778:2003 (RH=65%)
    use_iso8778=False -> инженерная атмосфера (RH=0%), Annex A
    """
    RH = RH_ANR if use_iso8778 else RH_AER
    return float(rho_humid_air_kg_m3(P_ANR, T_ANR, RH))


# --- Плотность в стандартной референсной атмосфере (ANR) ---
#
# Важно: в ISO 6358-1 (2013) прямо фиксируется ρ0 = 1,185 kg/m^3 для
# стандартной атмосферы ISO 8778 (p0=100 kPa, T0=293.15 K, RH=65%).
#
# Для строгой инженерной совместимости с паспортами (C, Qn, ...) используем
# *нормативную* ρ0=1.185. При этом оставляем расчётную оценку плотности влажного
# воздуха (идеальная смесь) как справочную величину.
RHO_ANR_NORM: float = 1.185
RHO_ANR_CALC: float = rho_ANR_kg_m3(use_iso8778=True)
RHO_ANR: float = RHO_ANR_NORM


def rho_ANR_ref(use_iso8778: bool = True) -> float:
    """Reference density at ANR conditions.

    Controls:
      - PNEUMO_ISO6358_RHO_ANR_MODE=norm|calc

    Default is 'norm' (ISO 8778 normative 1.185 kg/m^3).
    Mode 'calc' uses ideal-gas rho = P_ANR/(R*T_ANR).

    If use_iso8778=False, we always use the calculated rho (legacy behaviour).
    """

    rho_calc = float(P_ANR) / (R_DRY_AIR * float(T_ANR))
    if not use_iso8778:
        return rho_calc

    mode = os.environ.get('PNEUMO_ISO6358_RHO_ANR_MODE', 'norm').strip().lower()
    if mode in ('calc', 'computed', 'rho', 'ideal'):
        return rho_calc
    return float(RHO_ANR_NORM)



def iso6358_phi(pr: float, b: float, m: float = 0.5, *, beta_lam: float = ISO6358_BETA_LAM_DEFAULT) -> float:
    """Безразмерная функция φ(pr) в ISO‑6358‑совместимой форме.

    pr = p_down / p_up (абсолютные давления).

    - pr<=b  -> choked -> φ=1
    - pr->1  -> Δp->0  -> φ->0

    Численная устойчивость:
    - pr<=0 -> трактуем как сильный перепад -> φ=1
    - pr∈(beta_lam,1) -> линейно гасим к 0
    """
    try:
        pr = float(pr)
        b = float(b)
        m = float(m)
        beta_lam = float(beta_lam)
    except Exception:
        return 0.0

    if (not math.isfinite(pr)) or (not math.isfinite(b)) or (not math.isfinite(m)) or (not math.isfinite(beta_lam)):
        return 0.0

    if pr <= 0.0:
        return 1.0

    b = min(max(b, 0.0), 0.999999)

    if pr <= b:
        return 1.0
    if pr >= 1.0:
        return 0.0

    denom = max(1e-12, 1.0 - b)
    x = (pr - b) / denom
    base = max(0.0, 1.0 - x * x)
    phi = base ** max(0.0, m)

    beta_lam = min(max(beta_lam, b + 1e-9), 0.999999)
    if pr > beta_lam:
        x_l = (beta_lam - b) / denom
        base_l = max(0.0, 1.0 - x_l * x_l)
        phi_l = base_l ** max(0.0, m)
        phi = phi_l * (1.0 - pr) / max(1e-12, 1.0 - beta_lam)

    return float(max(0.0, min(1.0, phi)))


def pr_from_pressures(p_up: float, p_dn: float) -> float:
    """pr = p_dn/p_up с защитами."""
    try:
        p_up = float(p_up)
        p_dn = float(p_dn)
    except Exception:
        return float('nan')

    if (not math.isfinite(p_up)) or p_up <= 0.0 or (not math.isfinite(p_dn)):
        return float('nan')
    return p_dn / p_up


@dataclass(frozen=True)
class ANRInfo:
    """Справка о выбранных условиях ANR."""
    p_Pa: float
    T_K: float
    RH_percent: float
    rho_kg_m3: float


def anr_info(*, use_iso8778: bool = True) -> ANRInfo:
    """Возвращает ANR условия и плотность."""
    RH = RH_ANR if use_iso8778 else RH_AER
    rho_calc = rho_humid_air_kg_m3(P_ANR, T_ANR, RH)
    rho_use = rho_ANR_ref(use_iso8778=use_iso8778)
    return ANRInfo(p_Pa=float(P_ANR), T_K=float(T_ANR), RH_percent=float(RH), rho_kg_m3=float(rho_use))
