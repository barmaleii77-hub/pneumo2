# -*- coding: utf-8 -*-
"""DW2D Geometry UI.

Страница служит для настройки и проверки **текущего канонического контракта DW2D**:
- ввод размеров в мм для удобства человека;
- хранение/patch JSON строго в СИ;
- никаких выдуманных или устаревших параметров.

Важно:
- `колесо_координата` в действующем контракте — это **режим интерпретации** (`center` / `contact`),
  а не числовая координата X.
- Страница не должна создавать фантомный параметр "X колеса" и не должна подменять
  канонические параметры какими-либо legacy-алиасами.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from . import dw2d_mounts
from .dw2d_kinematics import build_dw2d_mounts_params_from_base, dw2d_mounts_delta_rod_and_drod
from . import opt_worker_v3_margins_energy as worker_mod


P_ATM = 101325.0  # Pa


# -------------------------------
# Helpers
# -------------------------------


def _h10(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def _ui_key(name: str) -> str:
    """Streamlit key: короткий ASCII, но стабильный для данного параметра."""
    return f"ui_dw2d_{_h10(name)}"


def _m_to_mm(x_m: float) -> float:
    return float(x_m) * 1000.0


def _mm_to_m(x_mm: float) -> float:
    return float(x_mm) / 1000.0


def _jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _normalize_wheel_coord_mode(value: Any) -> Tuple[str, List[str]]:
    raw = str(value or "center").strip().lower()
    if raw in ("center", "contact"):
        return raw, []
    return "center", [
        f"`колесо_координата` имеет некорректное значение {value!r}; использован canonical mode `center`."
    ]


def _build_dw2d_curve_bundle(params: Dict[str, Any], dw_samples: np.ndarray) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Return canonical DW2D curves for the current model contract.

    Current contract contains four mount groups:
    - Ц1 перед
    - Ц2 перед
    - Ц1 зад
    - Ц2 зад
    """
    specs = [
        ("Ц1 перед", "C1", "перед"),
        ("Ц2 перед", "C2", "перед"),
        ("Ц1 зад", "C1", "зад"),
        ("Ц2 зад", "C2", "зад"),
    ]
    delta_rod_m: Dict[str, np.ndarray] = {}
    drod_ddw: Dict[str, np.ndarray] = {}
    for label, cyl, axle in specs:
        mounts = build_dw2d_mounts_params_from_base(params, cyl=cyl, axle=axle)
        delta_arr, deriv_arr, _aux = dw2d_mounts_delta_rod_and_drod(np.asarray(dw_samples, dtype=float), mounts, sign_lr=+1.0)
        delta_rod_m[label] = np.asarray(delta_arr, dtype=float)
        drod_ddw[label] = np.asarray(deriv_arr, dtype=float)
    return delta_rod_m, drod_ddw


# -------------------------------
# UI
# -------------------------------


def run() -> None:
    st.title("Геометрия подвески: DW2D")

    base0, _ranges0 = worker_mod.make_base_and_ranges(P_ATM)

    # базовые значения (СИ)
    track_m0 = float(base0.get("колея", 1.0))
    wheelbase_m0 = float(base0.get("база", 1.5))
    wheel_coord_mode0, mode_warnings0 = _normalize_wheel_coord_mode(base0.get("колесо_координата", "center"))

    colA, colB, colC = st.columns([1.2, 1.2, 1.6])

    with colA:
        track_mm = st.number_input(
            "Колея, мм",
            value=float(st.session_state.get("ui_dw2d_track_mm", _m_to_mm(track_m0))),
            step=5.0,
            format="%.1f",
            key="ui_dw2d_track_mm",
            help="Ширина по колёсам. Внутри модели хранится в метрах.",
        )
        wheelbase_mm = st.number_input(
            "База, мм",
            value=float(st.session_state.get("ui_dw2d_wheelbase_mm", _m_to_mm(wheelbase_m0))),
            step=5.0,
            format="%.1f",
            key="ui_dw2d_wheelbase_mm",
            help="Колёсная база. Внутри модели хранится в метрах.",
        )

    with colB:
        mech = st.selectbox(
            "Кинематика",
            options=["dw2d", "stub"],
            index=0 if str(base0.get("механика_кинематика", "dw2d")) == "dw2d" else 1,
            key="ui_dw2d_mech",
            help="dw2d — кинематическая модель через DW2D. stub — заглушка.",
        )
        wheel_coord_mode = st.selectbox(
            "Режим `колесо_координата`",
            options=["center", "contact"],
            index=0 if wheel_coord_mode0 == "center" else 1,
            key="ui_dw2d_wheel_coord_mode",
            help="center = zw задаёт центр колеса; contact = zw задаёт пятно контакта. Это канонический параметр модели, не числовая X-координата.",
        )
        dw_range_mm = st.slider(
            "Диапазон dw, мм (для кривых)",
            min_value=-250.0,
            max_value=250.0,
            value=tuple(st.session_state.get("ui_dw2d_dw_range_mm", (-100.0, 100.0))),
            step=5.0,
            key="ui_dw2d_dw_range_mm",
            help="Диапазон перемещения колеса для построения Δшток(dw).",
        )

    with colC:
        st.info(
            """**Единицы и контракт страницы**

- Ввод: **мм**
- Patch JSON / base.json: **м** (СИ)
- `колесо_координата`: **режим** (`center` / `contact`), а не числовой X-параметр

Страница работает только с текущими каноническими параметрами DW2D: Ц1/Ц2 спереди и Ц1/Ц2 сзади."""
        )
        for msg in mode_warnings0:
            st.warning(msg)

    # Перевод в СИ
    track_m = _mm_to_m(track_mm)
    wheelbase_m = _mm_to_m(wheelbase_mm)
    dw_min_m, dw_max_m = _mm_to_m(dw_range_mm[0]), _mm_to_m(dw_range_mm[1])

    # Соберём словарь параметров (СИ)
    params: Dict[str, Any] = dict(base0)
    params["колея"] = float(track_m)
    params["база"] = float(wheelbase_m)
    params["колесо_координата"] = str(wheel_coord_mode)
    params["механика_кинематика"] = mech

    st.subheader("Параметры креплений DW2D")

    key_help = {
        "dw_lower_pivot_inboard_перед_м": "Расстояние от колеса до inboard pivot переднего нижнего рычага.",
        "dw_lower_pivot_z_перед_м": "Z-положение inboard pivot переднего нижнего рычага.",
        "dw_lower_arm_len_перед_м": "Длина переднего нижнего рычага.",
        "dw_upper_pivot_inboard_перед_м": "Расстояние от колеса до inboard pivot переднего верхнего рычага.",
        "dw_upper_pivot_z_перед_м": "Z-положение inboard pivot переднего верхнего рычага.",
        "dw_upper_arm_len_перед_м": "Длина переднего верхнего рычага.",
        "верх_Ц1_перед_между_ЛП_ПП_м": "Span между верхними точками крепления переднего цилиндра Ц1.",
        "верх_Ц1_перед_z_относительно_рамы_м": "Z верхней точки крепления переднего цилиндра Ц1 относительно рамы.",
        "низ_Ц1_перед_доля_рычага": "Доля длины переднего нижнего рычага до нижнего крепления Ц1 (0..1).",
        "ход_штока_Ц1_перед_м": "Полный ход штока переднего цилиндра Ц1.",
        "верх_Ц2_перед_между_ЛП_ПП_м": "Span между верхними точками крепления переднего цилиндра Ц2.",
        "верх_Ц2_перед_z_относительно_рамы_м": "Z верхней точки крепления переднего цилиндра Ц2 относительно рамы.",
        "низ_Ц2_перед_доля_рычага": "Доля длины переднего нижнего рычага до нижнего крепления Ц2 (0..1).",
        "ход_штока_Ц2_перед_м": "Полный ход штока переднего цилиндра Ц2.",
        "dw_lower_pivot_inboard_зад_м": "Расстояние от колеса до inboard pivot заднего нижнего рычага.",
        "dw_lower_pivot_z_зад_м": "Z-положение inboard pivot заднего нижнего рычага.",
        "dw_lower_arm_len_зад_м": "Длина заднего нижнего рычага.",
        "dw_upper_pivot_inboard_зад_м": "Расстояние от колеса до inboard pivot заднего верхнего рычага.",
        "dw_upper_pivot_z_зад_м": "Z-положение inboard pivot заднего верхнего рычага.",
        "dw_upper_arm_len_зад_м": "Длина заднего верхнего рычага.",
        "верх_Ц1_зад_между_ЛЗ_ПЗ_м": "Span между верхними точками крепления заднего цилиндра Ц1.",
        "верх_Ц1_зад_z_относительно_рамы_м": "Z верхней точки крепления заднего цилиндра Ц1 относительно рамы.",
        "низ_Ц1_зад_доля_рычага": "Доля длины заднего нижнего рычага до нижнего крепления Ц1 (0..1).",
        "ход_штока_Ц1_зад_м": "Полный ход штока заднего цилиндра Ц1.",
        "верх_Ц2_зад_между_ЛЗ_ПЗ_м": "Span между верхними точками крепления заднего цилиндра Ц2.",
        "верх_Ц2_зад_z_относительно_рамы_м": "Z верхней точки крепления заднего цилиндра Ц2 относительно рамы.",
        "низ_Ц2_зад_доля_рычага": "Доля длины заднего нижнего рычага до нижнего крепления Ц2 (0..1).",
        "ход_штока_Ц2_зад_м": "Полный ход штока заднего цилиндра Ц2.",
    }

    geo_keys = list(key_help.keys())

    for k in geo_keys:
        v0 = float(params.get(k, 0.0))
        help_txt = key_help.get(k, "")
        if k.endswith("_м") or k.endswith("_m"):
            v_mm0 = _m_to_mm(v0)
            v_mm = st.number_input(
                f"{k} (мм)",
                value=float(v_mm0),
                step=1.0,
                format="%.1f",
                help=help_txt,
                key=_ui_key(k) + "_mm",
            )
            params[k] = _mm_to_m(v_mm)
        else:
            params[k] = st.number_input(
                f"{k}",
                value=float(v0),
                step=0.01,
                format="%.4f",
                help=help_txt,
                key=_ui_key(k),
            )

    try:
        dw2d_mounts.validate_dw2d_params(params)
    except Exception as e:
        st.error(f"DW2D параметры не прошли валидацию: {e}")
        return

    # Расчёт кривых
    dw_samples = np.linspace(dw_min_m, dw_max_m, 201)
    delta_rod_m, drod_ddw = _build_dw2d_curve_bundle(params, dw_samples)

    # Графики в мм
    dw_mm = dw_samples * 1000.0
    df = pd.DataFrame(index=dw_mm)
    df.index.name = "dw, мм"

    for label, arr in delta_rod_m.items():
        df[f"Δшток {label}, мм"] = np.asarray(arr, dtype=float) * 1000.0
    for label, arr in drod_ddw.items():
        df[f"d(шток)/d(dw) {label}"] = np.asarray(arr, dtype=float)

    st.subheader("Кривые Δшток(dw) и motion ratio")
    st.line_chart(df, height=360)

    st.subheader("Patch JSON")
    st.caption("Patch создаётся в СИ (метры), чтобы корректно применяться к base.json.")

    patch = {k: params[k] for k in geo_keys + ["колея", "база", "колесо_координата", "механика_кинематика"]}

    st.download_button(
        "Скачать patch_dw2d.json",
        data=_jdump(patch).encode("utf-8"),
        file_name="patch_dw2d.json",
        mime="application/json",
        width="stretch",
    )

    with st.expander("Показать patch JSON", expanded=False):
        st.code(_jdump(patch), language="json")
