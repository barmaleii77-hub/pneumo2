"""🌀 Springs geometry / material / coil-bind UI

Это инженерная страница, которая увязывает:
- выбранную характеристику пружины (по сути k и диапазон хода)
- с физически реализуемой геометрией витков

и подготавливает параметры для модели/оптимизации:
- пружина_геом_* (d_wire, D_mean, N_active, N_total, pitch, G)
- пружина_длина_солид_м (может выводиться из геометрии)

Важно:
- В текущей модели coil-bind проверяется через запас:
    пружина_запас_до_coil_bind = L_inst - (L_solid + margin_min)
  Поэтому без L_solid геометрия не полная.

- Pitch (шаг) мы закладываем как переменный параметр: если >0,
  то можно оценить свободную длину по формуле L_free ≈ (N_total-1)*pitch + d_wire.

Ссылки на формулы добавлены в README релиза (см. docs/SPRINGS_GEOMETRY.md).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple

import streamlit as st


def _spring_rate_N_per_m(G_Pa: float, d_wire_m: float, D_mean_m: float, N_active: float) -> float:
    """k = G d^4 / (8 D^3 N)"""
    if G_Pa <= 0 or d_wire_m <= 0 or D_mean_m <= 0 or N_active <= 0:
        return float("nan")
    return float(G_Pa) * float(d_wire_m) ** 4 / (8.0 * float(D_mean_m) ** 3 * float(N_active))


def _wahl_factor(C: float) -> float:
    # Wahl correction factor for shear stress (not stiffness)
    if C <= 1.0:
        return float("nan")
    return (4.0 * C - 1.0) / (4.0 * C - 4.0) + 0.615 / C


def _max_shear_stress_Pa(F_N: float, D_mean_m: float, d_wire_m: float) -> float:
    """tau_max ≈ (8 F D / (pi d^3)) * K_w"""
    if F_N <= 0 or D_mean_m <= 0 or d_wire_m <= 0:
        return float("nan")
    C = D_mean_m / d_wire_m
    Kw = _wahl_factor(C)
    if not math.isfinite(Kw):
        return float("nan")
    return (8.0 * float(F_N) * float(D_mean_m) / (math.pi * float(d_wire_m) ** 3)) * float(Kw)


def _solid_length_m(N_total: float, d_wire_m: float) -> float:
    if d_wire_m <= 0 or N_total <= 0:
        return float("nan")
    return float(max(1, int(round(N_total)))) * float(d_wire_m)


def _free_length_from_pitch_m(N_total: float, pitch_m: float, d_wire_m: float) -> float:
    if d_wire_m <= 0 or pitch_m <= 0 or N_total < 2:
        return float("nan")
    Nt = max(2, int(round(N_total)))
    return float(Nt - 1) * float(pitch_m) + float(d_wire_m)


def _queue_overrides_si(overrides: Dict[str, float]) -> None:
    bag = st.session_state.get("pending_overrides_si")
    if not isinstance(bag, dict):
        bag = {}
    bag.update({str(k): float(v) for k, v in overrides.items()})
    st.session_state["pending_overrides_si"] = bag


def run() -> None:
    st.title("Пружины: геометрия / материал / coil-bind")

    st.info(
        "Эта страница нужна для инженерной увязки характеристики пружины с геометрией витков. "
        "Результат — параметры pruzhina_геом_* и корректная проверка coil-bind в модели/оптимизаторе."
    )

    # --- Inputs ---
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        d_wire_mm = st.number_input("Диаметр проволоки d, мм", min_value=1.0, max_value=30.0, value=8.0, step=0.5)
        D_mean_mm = st.number_input("Средний диаметр D, мм", min_value=10.0, max_value=200.0, value=60.0, step=1.0)
        N_active = st.number_input("Активные витки N_active", min_value=1.0, max_value=30.0, value=8.0, step=1.0)

    with col2:
        N_total = st.number_input("Полные витки N_total", min_value=1.0, max_value=40.0, value=10.0, step=1.0)
        pitch_mm = st.number_input(
            "Шаг витка (pitch), мм (0 = вычислять/не задавать)",
            min_value=0.0,
            max_value=50.0,
            value=0.0,
            step=0.5,
        )
        margin_bind_mm = st.number_input(
            "Минимальный запас до coil-bind, мм (margin_min)",
            min_value=0.0,
            max_value=50.0,
            value=5.0,
            step=0.5,
        )

    with col3:
        G_GPa = st.number_input("Модуль сдвига G, ГПа", min_value=1.0, max_value=120.0, value=79.0, step=1.0)
        F_max = st.number_input("Оценка максимальной силы F_max, Н (для напряжений)", min_value=0.0, max_value=200000.0, value=15000.0, step=500.0)

    d_wire_m = float(d_wire_mm) / 1000.0
    D_mean_m = float(D_mean_mm) / 1000.0
    pitch_m = float(pitch_mm) / 1000.0
    G_Pa = float(G_GPa) * 1e9

    k_N_m = _spring_rate_N_per_m(G_Pa, d_wire_m, D_mean_m, N_active)
    k_N_mm = k_N_m / 1000.0 if math.isfinite(k_N_m) else float("nan")

    L_solid = _solid_length_m(N_total, d_wire_m)
    L_free_from_pitch = _free_length_from_pitch_m(N_total, pitch_m, d_wire_m)

    tau_max = _max_shear_stress_Pa(F_max, D_mean_m, d_wire_m)

    st.subheader("Расчёт")

    cA, cB, cC = st.columns([1, 1, 1])
    with cA:
        st.metric("k (N/mm)", f"{k_N_mm:.3g}" if math.isfinite(k_N_mm) else "—")
        st.metric("k (N/m)", f"{k_N_m:.3g}" if math.isfinite(k_N_m) else "—")

    with cB:
        st.metric("L_solid (mm)", f"{L_solid*1000.0:.2f}" if math.isfinite(L_solid) else "—")
        st.metric(
            "L_free из pitch (mm)",
            f"{L_free_from_pitch*1000.0:.2f}" if math.isfinite(L_free_from_pitch) else "—",
        )

    with cC:
        st.metric(
            "τ_max (МПа)",
            f"{tau_max/1e6:.1f}" if math.isfinite(tau_max) else "—",
        )
        if math.isfinite(d_wire_m) and d_wire_m > 0:
            C = D_mean_m / d_wire_m
            st.metric("Spring index C=D/d", f"{C:.2f}" if math.isfinite(C) else "—")

    if math.isfinite(L_solid) and math.isfinite(L_free_from_pitch):
        delta_bind = L_free_from_pitch - L_solid
        st.write(
            {
                "delta_to_bind_mm": float(delta_bind * 1000.0),
                "note": "Если delta_to_bind отрицательная — витки уже 'в солиде' при свободной длине (невозможно).",
            }
        )

    st.divider()

    st.subheader("Применение к базе")

    overrides = {
        "пружина_геом_диаметр_проволоки_м": d_wire_m,
        "пружина_геом_диаметр_средний_м": D_mean_m,
        "пружина_геом_число_витков_активных": float(N_active),
        "пружина_геом_число_витков_полное": float(N_total),
        "пружина_геом_шаг_витка_м": pitch_m,
        "пружина_геом_G_Па": float(G_Pa),
        "пружина_длина_солид_м": float(L_solid) if math.isfinite(L_solid) else 0.0,
        "пружина_запас_до_coil_bind_минимум_м": float(margin_bind_mm) / 1000.0,
    }

    st.json(overrides)

    if st.button("Сохранить overrides (pending)", type="primary"):
        _queue_overrides_si(overrides)
        st.success(
            "Overrides сохранены. Откройте главную страницу 'Расчёт' — они применятся автоматически."
        )

    st.caption(
        "Подсказка: если в модели включена 'пружина_геометрия_согласовать_с_цилиндром', "
        "свободная длина пружины L_free вычисляется из геометрии цилиндра и x0. "
        "Pitch в этом случае служит для проверки реализуемости (какой pitch нужен для такого L_free)."
    )
