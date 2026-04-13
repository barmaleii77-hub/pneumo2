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

from .spring_table import build_spring_geometry_reference

from .suspension_family_contract import (
    FAMILY_ORDER,
    SPRING_STATIC_MODE_AUTO_MIDSTROKE,
    SPRING_STATIC_MODE_KEY,
    SPRING_STATIC_MODE_MANUAL,
    family_name,
    normalize_spring_static_mode,
    spring_family_key,
    spring_static_mode_description,
)


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


def build_spring_family_overrides(
    *,
    target: str,
    static_mode: str,
    d_wire_m: float,
    D_mean_m: float,
    N_active: float,
    N_total: float,
    pitch_m: float,
    G_Pa: float,
    L_solid_m: float,
    margin_bind_m: float,
) -> Dict[str, float | str]:
    mode = normalize_spring_static_mode(static_mode)
    generic_overrides: Dict[str, float | str] = {
        SPRING_STATIC_MODE_KEY: mode,
        "пружина_геом_диаметр_проволоки_м": d_wire_m,
        "пружина_геом_диаметр_средний_м": D_mean_m,
        "пружина_геом_число_витков_активных": float(N_active),
        "пружина_геом_число_витков_полное": float(N_total),
        "пружина_геом_шаг_витка_м": pitch_m,
        "пружина_геом_G_Па": float(G_Pa),
        "пружина_длина_солид_м": float(L_solid_m) if math.isfinite(L_solid_m) else 0.0,
        "пружина_запас_до_coil_bind_минимум_м": float(margin_bind_m),
    }
    suffix_map = {
        "геом_диаметр_проволоки_м": d_wire_m,
        "геом_диаметр_средний_м": D_mean_m,
        "геом_число_витков_активных": float(N_active),
        "геом_число_витков_полное": float(N_total),
        "геом_шаг_витка_м": pitch_m,
        "геом_G_Па": float(G_Pa),
        "длина_солид_м": float(L_solid_m) if math.isfinite(L_solid_m) else 0.0,
        "запас_до_coil_bind_минимум_м": float(margin_bind_m),
    }
    if str(target).strip() == "Все 4 семейства":
        out = dict(generic_overrides)
        for cyl, axle in FAMILY_ORDER:
            for suffix, value in suffix_map.items():
                out[spring_family_key(suffix, cyl, axle)] = value
        return out

    cyl, axle = str(target).split(" ", 1)
    out = {SPRING_STATIC_MODE_KEY: mode}
    for suffix, value in suffix_map.items():
        out[spring_family_key(suffix, cyl, axle)] = value
    return out


def run() -> None:
    st.title("Пружины: геометрия / материал / coil-bind")

    st.info(
        "Эта страница нужна для инженерной увязки характеристики пружины с геометрией витков. "
        "Результат — параметры pruzhina_геом_* и корректная проверка coil-bind в модели/оптимизаторе."
    )
    st.caption(
        "Канонический режим проекта: пружины можно задавать отдельно для семейств "
        "`Ц1 перед`, `Ц2 перед`, `Ц1 зад`, `Ц2 зад`, либо применить один набор ко всем четырём семействам."
    )

    top_a, top_b = st.columns([1.2, 1.8])
    with top_a:
        target = st.selectbox(
            "Семейство пружины",
            ["Все 4 семейства", *[family_name(cyl, axle) for cyl, axle in FAMILY_ORDER]],
            index=0,
            help=(
                "По новому канону перед/зад и Ц1/Ц2 могут иметь разные пружины. "
                "Если пока нужна прежняя схема, выберите «Все 4 семейства»."
            ),
        )
    with top_b:
        static_mode_ui = st.selectbox(
            "Режим настройки в статике",
            ["Авто: шток около середины хода", "Ручной: семейство задаёт инженер"],
            index=0,
            help=(
                "Авто-режим нужен для концепции «машина стоит ровно, текущая масса, поршни примерно в середине хода». "
                "Ручной режим сохраняет геометрию как задано пользователем."
            ),
        )
        static_mode = (
            SPRING_STATIC_MODE_AUTO_MIDSTROKE
            if static_mode_ui.startswith("Авто")
            else SPRING_STATIC_MODE_MANUAL
        )
        st.caption(spring_static_mode_description(static_mode))

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

    geometry = build_spring_geometry_reference(
        d_wire_m=d_wire_m,
        D_mean_m=D_mean_m,
        N_active=float(N_active),
        N_total=float(N_total),
        pitch_m=pitch_m,
        G_Pa=G_Pa,
        F_max_N=float(F_max),
    )

    st.subheader("Расчёт")

    cA, cB, cC = st.columns([1, 1, 1])
    with cA:
        st.metric(
            "k (N/mm)",
            f"{geometry.rate_N_per_mm:.3g}" if math.isfinite(geometry.rate_N_per_mm) else "—",
        )
        st.metric(
            "k (N/m)",
            f"{geometry.rate_N_per_m:.3g}" if math.isfinite(geometry.rate_N_per_m) else "—",
        )

    with cB:
        st.metric(
            "L_solid (mm)",
            f"{geometry.solid_length_m * 1000.0:.2f}"
            if math.isfinite(geometry.solid_length_m)
            else "—",
        )
        st.metric(
            "L_free из pitch (mm)",
            f"{geometry.free_length_from_pitch_m * 1000.0:.2f}"
            if math.isfinite(geometry.free_length_from_pitch_m)
            else "—",
        )

    with cC:
        st.metric(
            "τ_max (МПа)",
            f"{geometry.max_shear_stress_Pa / 1e6:.1f}"
            if math.isfinite(geometry.max_shear_stress_Pa)
            else "—",
        )
        st.metric(
            "Spring index C=D/d",
            f"{geometry.spring_index:.2f}" if math.isfinite(geometry.spring_index) else "—",
        )

    if math.isfinite(geometry.solid_length_m) and math.isfinite(geometry.free_length_from_pitch_m):
        st.write(
            {
                "delta_to_bind_mm": float(geometry.bind_travel_margin_m * 1000.0),
                "note": "Если delta_to_bind отрицательная — витки уже 'в солиде' при свободной длине (невозможно).",
            }
        )

    st.divider()

    st.subheader("Применение к базе")

    overrides = build_spring_family_overrides(
        target=target,
        static_mode=static_mode,
        d_wire_m=d_wire_m,
        D_mean_m=D_mean_m,
        N_active=float(N_active),
        N_total=float(N_total),
        pitch_m=pitch_m,
        G_Pa=float(G_Pa),
        L_solid_m=float(geometry.solid_length_m) if math.isfinite(geometry.solid_length_m) else 0.0,
        margin_bind_m=float(margin_bind_mm) / 1000.0,
    )

    st.json(overrides)

    if st.button("Сохранить overrides (pending)", type="primary"):
        numeric_overrides = {
            str(k): float(v)
            for k, v in overrides.items()
            if not isinstance(v, str)
        }
        _queue_overrides_si(numeric_overrides)
        st.session_state[SPRING_STATIC_MODE_KEY] = str(overrides.get(SPRING_STATIC_MODE_KEY) or static_mode)
        st.session_state[f"mode__{SPRING_STATIC_MODE_KEY}"] = str(overrides.get(SPRING_STATIC_MODE_KEY) or static_mode)
        st.success(
            "Overrides сохранены. Числовые параметры попадут в pending_overrides, "
            "а режим статики сохранён в session_state и в строковом editor-state главной страницы."
        )

    st.caption(
        "Подсказка: если в модели включена 'пружина_геометрия_согласовать_с_цилиндром', "
        "свободная длина пружины L_free вычисляется из геометрии цилиндра и x0. "
        "Pitch в этом случае служит для проверки реализуемости (какой pitch нужен для такого L_free)."
    )
