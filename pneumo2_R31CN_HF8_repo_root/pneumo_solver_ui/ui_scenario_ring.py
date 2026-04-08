"""ui_scenario_ring.py

UI‑обвязка для кольцевого генератора сценариев/тестов.

Цели:
- последовательность: создание -> валидация -> добавление в набор -> прогон
- манёвры задаются инженерно (радиус/скорость/время), а не «сырой ay»
- профиль дороги: ISO 8608 или синус по сторонам + события «яма/препятствие»
- все данные сохраняются (session_state + autosave) и попадают в suite_override
"""

from __future__ import annotations

import copy
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from .scenario_ring import (
    _resolve_initial_speed_kph,
    _segment_motion_contract,
    generate_ring_scenario_bundle,
    summarize_ring_track_segments,
    validate_ring_spec,
)
from .ui_persistence import autosave_if_enabled


log = logging.getLogger(__name__)



def _new_uid() -> str:
    """Короткий идентификатор сегмента/объекта для стабильных ключей UI."""
    return uuid.uuid4().hex[:8]


def _ensure_segment_uids(segments: List[Dict[str, Any]]) -> None:
    """Гарантирует наличие уникальных seg['uid'] для каждого сегмента."""
    used = set()
    for seg in segments:
        uid = str(seg.get("uid") or "")
        if (not uid) or (uid in used):
            uid = _new_uid()
            seg["uid"] = uid
        used.add(uid)

def _format_sine_amplitude_semantics(a_mm: float) -> str:
    """Пояснение к амплитуде синуса без двусмысленности A vs p-p."""
    a_mm = float(max(0.0, a_mm))
    return (
        f"A={a_mm:.1f} мм = полуразмах: профиль идёт от {-a_mm:.1f} до +{a_mm:.1f} мм "
        f"относительно локального нуля; полный размах p-p = {2.0 * a_mm:.1f} мм."
    )


def _default_ring_spec() -> Dict[str, Any]:
    """Дефолт: пользовательский канон кольца из последнего принятого ring editor setup."""
    spec = {
        "schema_version": "ring_v2",
        "closure_policy": "closed_c1_periodic",
        "v0_kph": 40.0,
        "seed": 123,
        "dx_m": 0.02,
        "dt_s": 0.01,
        "n_laps": 1,
        "wheelbase_m": 1.5,
        "track_m": 1.0,
        "segments": [
            {
                "name": "S1_прямо",
                "duration_s": 5.0,
                "drive_mode": "STRAIGHT",
                "speed_kph": 40.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 40.0,
                "road": {
                    "center_height_start_mm": 0.0,
                    "center_height_end_mm": 0.0,
                    "cross_slope_start_pct": 0.0,
                    "cross_slope_end_pct": 0.0,
                    "mode": "ISO8608",
                    "iso_class": "E",
                    "gd_pick": "mid",
                    "gd_n0_scale": 1.0,
                    "waviness_w": 2.0,
                    "left_right_coherence": 0.5,
                    "seed": 12345,
                },
                "events": [
                    {
                        "kind": "яма",
                        "side": "left",
                        "start_m": 8.0,
                        "length_m": 0.6,
                        "depth_mm": -35.0,
                        "ramp_m": 0.15,
                    },
                    {
                        "kind": "препятствие",
                        "side": "both",
                        "start_m": 14.0,
                        "length_m": 0.35,
                        "depth_mm": 25.0,
                        "ramp_m": 0.08,
                    },
                ],
            },
            {
                "name": "S2_поворот",
                "duration_s": 4.0,
                "drive_mode": "TURN_LEFT",
                "speed_kph": 40.0,
                "turn_direction": "LEFT",
                "speed_end_kph": 40.0,
                "turn_radius_m": 60.0,
                "road": {
                    "center_height_end_mm": 0.0,
                    "cross_slope_end_pct": 0.0,
                    "mode": "SINE",
                    "aL_mm": 50.0,
                    "aR_mm": 50.0,
                    "lambdaL_m": 1.5,
                    "lambdaR_m": 1.5,
                    "phaseL_deg": 0.0,
                    "phaseR_deg": 180.0,
                    "rand_aL": False,
                    "rand_aL_p": 0.5,
                    "rand_aL_lo_mm": 4.0,
                    "rand_aL_hi_mm": 4.0,
                    "rand_aR": False,
                    "rand_aR_p": 0.5,
                    "rand_aR_lo_mm": 4.0,
                    "rand_aR_hi_mm": 4.0,
                    "rand_lL": False,
                    "rand_lL_p": 0.5,
                    "rand_lL_lo_m": 2.5,
                    "rand_lL_hi_m": 2.5,
                    "rand_lR": False,
                    "rand_lR_p": 0.5,
                    "rand_lR_lo_m": 2.5,
                    "rand_lR_hi_m": 2.5,
                    "rand_pL": True,
                    "rand_pL_p": 0.5,
                    "rand_pL_lo_deg": 0.0,
                    "rand_pL_hi_deg": 360.0,
                    "rand_pR": True,
                    "rand_pR_p": 0.5,
                    "rand_pR_lo_deg": 0.0,
                    "rand_pR_hi_deg": 360.0,
                },
                "events": [],
            },
            {
                "name": "S3_разгон",
                "duration_s": 3.0,
                "drive_mode": "ACCEL",
                "v_end_kph": 55.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 55.0,
                "road": {
                    "center_height_end_mm": 0.0,
                    "cross_slope_end_pct": 0.0,
                    "mode": "ISO8608",
                    "iso_class": "E",
                    "gd_pick": "mid",
                    "gd_n0_scale": 1.0,
                    "waviness_w": 2.0,
                    "left_right_coherence": 0.5,
                    "seed": 54321,
                },
                "events": [],
            },
            {
                "name": "S4_торможение",
                "duration_s": 3.0,
                "drive_mode": "BRAKE",
                "v_end_kph": 40.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 40.0,
                "road": {
                    "center_height_end_mm": 0.0,
                    "cross_slope_end_pct": 0.0,
                    "mode": "ISO8608",
                    "iso_class": "E",
                    "gd_pick": "mid",
                    "gd_n0_scale": 1.0,
                    "waviness_w": 2.0,
                    "left_right_coherence": 0.5,
                    "seed": 999,
                },
                "events": [],
            },
        ],
    }
    _ensure_segment_uids(spec["segments"])
    return spec



def _segment_length_estimate_m(v_start_kph: float, seg: Dict[str, Any]) -> float:
    """Rough segment length estimate (for preview only).

    ABSOLUTE LAW: alias keys are forbidden.
      * speed_kph is the only accepted cruise speed key.
      * v_end_kph is the only accepted accel/brake target speed key.
    """
    dur = float(seg.get("duration_s", 0.0))
    if dur <= 0:
        return 0.0

    motion = _segment_motion_contract(seg, v_start_kph)
    v0 = max(0.0, float(motion["speed_start_kph"]) / 3.6)
    v1 = max(0.0, float(motion["speed_end_kph"]) / 3.6)
    if motion["vary_speed"]:
        return float(0.5 * (v0 + v1) * dur)
    return float(v1 * dur)


def _segment_end_speed_kph(v_start_kph: float, seg: Dict[str, Any]) -> float:
    """Segment end speed (for preview only)."""
    return float(_segment_motion_contract(seg, v_start_kph)["speed_end_kph"])


def _turn_direction_label(direction: str) -> str:
    return {
        "STRAIGHT": "Прямо",
        "LEFT": "Поворот влево",
        "RIGHT": "Поворот вправо",
    }.get(str(direction).upper(), str(direction))


def _derive_ring_road_state_flow(segments: List[Dict[str, Any]]) -> Tuple[List[Dict[str, float]], List[Dict[str, float]]]:
    starts: List[Dict[str, float]] = []
    ends: List[Dict[str, float]] = []
    if not segments:
        return starts, ends
    road0 = dict((segments[0] or {}).get("road", {}) or {})
    first_center = float(road0.get("center_height_start_mm", 0.0) or 0.0)
    first_cross = float(road0.get("cross_slope_start_pct", 0.0) or 0.0)
    prev_center = first_center
    prev_cross = first_cross
    for idx, seg in enumerate(segments):
        road = dict((seg or {}).get("road", {}) or {})
        if idx == 0:
            start_center = first_center
            start_cross = first_cross
        else:
            start_center = prev_center
            start_cross = prev_cross
        is_last = idx >= len(segments) - 1
        end_center_default = first_center if is_last else start_center
        end_cross_default = first_cross if is_last else start_cross
        end_center = float(road.get("center_height_end_mm", end_center_default) or end_center_default)
        end_cross = float(road.get("cross_slope_end_pct", end_cross_default) or end_cross_default)
        if is_last:
            end_center = first_center
            end_cross = first_cross
        starts.append({"center_height_mm": float(start_center), "cross_slope_pct": float(start_cross)})
        ends.append({"center_height_mm": float(end_center), "cross_slope_pct": float(end_cross)})
        prev_center = float(end_center)
        prev_cross = float(end_cross)
    return starts, ends



def _ensure_ring_spec_in_state() -> Dict[str, Any]:
    spec = st.session_state.get("ring_scenario_spec")
    if not isinstance(spec, dict) or "segments" not in spec:
        spec = _default_ring_spec()
        st.session_state["ring_scenario_spec"] = spec
    # defensive
    if not isinstance(spec.get("segments"), list):
        spec["segments"] = []
    _ensure_segment_uids(spec["segments"])
    return spec


def _guess_suite_stage(df_suite_edit: pd.DataFrame) -> int:
    """Подсказка стадии для нового ring-теста без скрытой магии.

    Канон staged-optimization в проекте 0-based: первая стадия = 0.
    Поэтому ring-editor не должен тайком форсировать stage>=1.
    """
    try:
        flt = st.session_state.get("ui_suite_stage_filter")
        if isinstance(flt, list) and len(flt) == 1:
            return max(0, int(flt[0]))
    except Exception:
        pass

    try:
        if "стадия" in df_suite_edit.columns:
            vals = pd.to_numeric(df_suite_edit["стадия"], errors="coerce").dropna().astype(int)
            if not vals.empty:
                return max(0, int(vals.min()))
    except Exception:
        pass

    return 0


def _render_segment_editor(
    seg: Dict[str, Any],
    *,
    idx: int,
    v_start_kph: float,
    ring_start_speed_kph: float,
    is_first: bool,
    is_last: bool,
    road_start_center_mm: float,
    road_start_cross_pct: float,
    ring_start_center_mm: float,
    ring_start_cross_pct: float,
) -> Tuple[Dict[str, Any], float]:
    """Возвращает (updated_seg, v_end_kph)."""
    uid = str(seg.get("uid") or f"s{idx+1}")
    name = str(seg.get("name", f"S{idx+1}"))
    motion = _segment_motion_contract(seg, v_start_kph)
    turn_direction = str(motion["turn_direction"]).upper()
    dur = float(seg.get("duration_s", 5.0))

    # Заголовок‑сводка
    v_end_preview = _segment_end_speed_kph(v_start_kph, seg)
    est_len = _segment_length_estimate_m(v_start_kph, seg)
    summary = (
        f"{name} · {_turn_direction_label(turn_direction)} · {dur:.1f} c · "
        f"v: {v_start_kph:.1f}→{v_end_preview:.1f} км/ч · ≈{est_len:.1f} м"
    )

    # Важно: label expander должен быть стабильным, иначе Streamlit будет
    # пересоздавать блок после каждого изменения полей сегмента и панель
    # визуально «схлопывается сама». Краткую сводку показываем внутри.
    with st.expander(f"Сегмент {idx + 1}", expanded=False):
        st.caption(summary)
        colA, colB, colC = st.columns([2.2, 1.2, 1.2])
        with colA:
            seg["name"] = st.text_input(
                "Название сегмента",
                value=name,
                key=f"seg_name_{uid}",
                help="Короткое имя для удобства. Влияет только на читаемость набора тестов.",
            )
        with colB:
            seg["duration_s"] = st.number_input(
                "Длительность, с",
                min_value=0.1,
                value=float(max(0.1, dur)),
                step=0.5,
                key=f"seg_dur_{uid}",
                help="Сколько времени длится сегмент в одном круге. Длина сегмента вычисляется из скорости.",
            )
        with colC:
            allowed_turns = ["STRAIGHT", "LEFT", "RIGHT"]
            turn_direction = st.selectbox(
                "Направление движения",
                options=allowed_turns,
                index=allowed_turns.index(turn_direction if turn_direction in allowed_turns else "STRAIGHT"),
                key=f"seg_turn_direction_{uid}",
                format_func=_turn_direction_label,
                help=(
                    "Канонический пользовательский смысл сегмента: прямо, поворот влево или поворот вправо. "
                    "Разгон/торможение задаются не типом сегмента, а изменением конечной скорости."
                ),
            )
            seg["turn_direction"] = turn_direction

        # Параметры режима
        c1, c2, c3 = st.columns([1.2, 1.2, 1.2])
        with c1:
            start_label = "Начальная скорость кольца" if is_first else "Скорость на входе"
            if is_first:
                st.metric(start_label, f"{ring_start_speed_kph:.1f} км/ч")
                st.caption(
                    "Это начало первого сегмента и одновременно скорость замыкания кольца. "
                    "Редактируется в верхнем поле `Начальная скорость кольца`."
                )
            else:
                st.metric(start_label, f"{v_start_kph:.1f} км/ч")
                st.caption("Для сегментов 2..N начальная скорость берётся автоматически из конца предыдущего сегмента.")
        with c2:
            if is_last:
                seg["speed_end_kph"] = float(ring_start_speed_kph)
                st.metric("Конечная скорость", f"{float(ring_start_speed_kph):.1f} км/ч")
                st.caption("Последний сегмент автоматически замыкается в начальную скорость первого.")
            else:
                seg["speed_end_kph"] = st.number_input(
                    "Конечная скорость, км/ч",
                    min_value=0.0,
                    value=float(seg.get("speed_end_kph", motion["speed_end_kph"])),
                    step=1.0,
                    key=f"seg_speed_end_{uid}",
                    help=(
                        "Конечная скорость сегмента. Если отличается от входной скорости, это и есть разгон/торможение. "
                        "Отдельный тип сегмента для этого не нужен."
                    ),
                )
        with c3:
            if turn_direction in ("LEFT", "RIGHT"):
                seg["turn_radius_m"] = st.number_input(
                    "Радиус поворота, м",
                    min_value=1.0,
                    value=float(seg.get("turn_radius_m", 60.0)),
                    step=5.0,
                    key=f"seg_r_{uid}",
                    help=(
                        "Радиус траектории для этого сегмента. Направление задаётся отдельно: влево или вправо. "
                        "Внутри именно из скорости и радиуса вычисляется боковое ускорение."
                    ),
                )
            else:
                seg.pop("turn_radius_m", None)
                st.info("Поворота нет", icon="ℹ️")

        start_speed_kph = float(ring_start_speed_kph if is_first else v_start_kph)
        end_speed_kph = float(seg.get("speed_end_kph", start_speed_kph))
        if turn_direction == "STRAIGHT":
            if abs(end_speed_kph - start_speed_kph) <= 1e-9:
                seg["drive_mode"] = "STRAIGHT"
                seg["speed_kph"] = float(end_speed_kph)
                seg.pop("v_end_kph", None)
            else:
                seg["drive_mode"] = "ACCEL" if end_speed_kph > start_speed_kph else "BRAKE"
                seg["v_end_kph"] = float(end_speed_kph)
                seg["speed_kph"] = float(end_speed_kph)
        else:
            seg["drive_mode"] = "TURN_LEFT" if turn_direction == "LEFT" else "TURN_RIGHT"
            seg["speed_kph"] = float(end_speed_kph)
            seg.pop("v_end_kph", None)

        seg["speed_start_kph"] = float(start_speed_kph)

        c4, c5 = st.columns([1.2, 1.2])
        with c4:
            delta_v = float(end_speed_kph - start_speed_kph)
            st.metric("Δv по сегменту", f"{delta_v:+.1f} км/ч")
        with c5:
            if turn_direction in ("LEFT", "RIGHT"):
                try:
                    v_ref_mps = max(float(start_speed_kph), float(end_speed_kph)) / 3.6
                    r_m = max(float(seg.get("turn_radius_m", 1.0) or 1.0), 1e-6)
                    ay = (v_ref_mps * v_ref_mps) / r_m
                    ay_g = ay / 9.80665
                    sign = 1.0 if turn_direction == "LEFT" else -1.0
                    st.metric("Оценка ay", f"{sign * ay:.2f} м/с²")
                    st.caption(f"≈ {sign * ay_g:.2f} g при v≈max(v0,v1) и R={r_m:.1f} м")
                    if abs(ay_g) > 1.0:
                        st.warning(
                            "Боковое ускорение > 1g. Проверьте радиус/скорость: это может быть нецелевой режим и приводить к нечестным тестам.",
                            icon="⚠️",
                        )
                except Exception:
                    st.info("Не удалось оценить ay", icon="ℹ️")
            else:
                st.info("Для прямого сегмента ay = 0", icon="ℹ️")

        # Дорога
        st.markdown("#### Профиль дороги")
        road = dict(seg.get("road", {}))
        road_mode = str(road.get("mode", "ISO8608")).upper()
        cR1, cR2, cR3 = st.columns([1.2, 1.2, 1.2])
        with cR1:
            road_mode = st.selectbox(
                "Тип профиля",
                options=["ISO8608", "SINE"],
                index=0 if road_mode.startswith("ISO") else 1,
                key=f"seg_road_mode_{uid}",
                help="ISO8608 — спектральная шероховатость по классу дороги. SINE — синус по каждой стороне отдельно.",
            )
        road["mode"] = road_mode

        st.caption(
            "Канон геометрии кольца: продольный уклон задаётся через высоту дороги в начале первого и в конце сегментов; "
            "разбегание левой/правой колеи по высоте задаётся через поперечный уклон сегмента."
        )
        cG1, cG2 = st.columns(2)
        with cG1:
            if is_first:
                road["center_height_start_mm"] = st.number_input(
                    "Высота дороги в начале сегмента, мм",
                    value=float(road.get("center_height_start_mm", road_start_center_mm)),
                    step=5.0,
                    key=f"seg_center_start_{uid}",
                    help=(
                        "Абсолютная высота центра дороги в начале первого сегмента. "
                        "Для сегментов 2..N начало берётся автоматически из конца предыдущего, потому что кольцо непрерывно."
                    ),
                )
            else:
                st.metric("Высота дороги на входе", f"{float(road_start_center_mm):.1f} мм")
                st.caption("Старт сегмента наследуется из конца предыдущего.")
        with cG2:
            if is_last:
                road["center_height_end_mm"] = float(ring_start_center_mm)
                st.metric("Высота дороги в конце", f"{float(ring_start_center_mm):.1f} мм")
                st.caption("Последний сегмент автоматически замыкается в высоту начала первого.")
            else:
                road["center_height_end_mm"] = st.number_input(
                    "Высота дороги в конце сегмента, мм",
                    value=float(road.get("center_height_end_mm", road_start_center_mm)),
                    step=5.0,
                    key=f"seg_center_end_{uid}",
                    help=(
                        "Высота центра дороги в конце сегмента. "
                        "Именно через это поле задаётся продольный уклон, а не через тип «разгон/торможение»."
                    ),
                )

        cG3, cG4 = st.columns(2)
        with cG3:
            if is_first:
                road["cross_slope_start_pct"] = st.number_input(
                    "Поперечный уклон в начале, %",
                    value=float(road.get("cross_slope_start_pct", road_start_cross_pct)),
                    step=0.1,
                    key=f"seg_cross_start_{uid}",
                    help=(
                        "Поперечный уклон дороги в начале первого сегмента. "
                        "Положительное значение означает: правая колея выше левой; отрицательное — левая выше правой."
                    ),
                )
            else:
                st.metric("Поперечный уклон на входе", f"{float(road_start_cross_pct):.2f} %")
                st.caption("Стартовый поперечный уклон наследуется из конца предыдущего сегмента.")
        with cG4:
            if is_last:
                road["cross_slope_end_pct"] = float(ring_start_cross_pct)
                st.metric("Поперечный уклон в конце", f"{float(ring_start_cross_pct):.2f} %")
                st.caption("Последний сегмент автоматически замыкается в поперечный уклон начала первого.")
            else:
                road["cross_slope_end_pct"] = st.number_input(
                    "Поперечный уклон в конце, %",
                    value=float(road.get("cross_slope_end_pct", road_start_cross_pct)),
                    step=0.1,
                    key=f"seg_cross_end_{uid}",
                    help=(
                        "Поперечный уклон в конце сегмента. "
                        "Так задаётся расхождение левой/правой колеи по высоте вместо ручного раздельного дрейфа колей."
                    ),
                )

        if road_mode == "ISO8608":
            iso_class = str(road.get("iso_class", "C")).upper()
            if iso_class not in list("ABCDEFGH"):
                st.warning(f"Сегмент {idx+1}: iso_class={iso_class!r} вне диапазона A..H. Использую 'C'.", icon="⚠️")
                iso_class = "C"

            gd_pick = str(road.get("gd_pick", "mid")).lower()
            gd_pick_options = ["lower", "mid", "upper"]
            if gd_pick not in gd_pick_options:
                st.warning(
                    f"Сегмент {idx+1}: gd_pick={gd_pick!r} неканоничен. Использую 'mid'.",
                    icon="⚠️",
                )
                gd_pick = "mid"

            cI1, cI2, cI3 = st.columns(3)
            with cI1:
                road["iso_class"] = st.selectbox(
                    "Класс ISO",
                    options=list("ABCDEFGH"),
                    index=list("ABCDEFGH").index(iso_class),
                    key=f"seg_iso_class_{uid}",
                    help="Класс A — ровная, H — очень грубая. Внутри используется ISO 8608 спектр.",
                )
            with cI2:
                road["gd_pick"] = st.selectbox(
                    "Уровень внутри класса",
                    options=gd_pick_options,
                    index=gd_pick_options.index(gd_pick),
                    key=f"seg_iso_gd_pick_{uid}",
                    format_func=lambda x: {"lower": "нижний", "mid": "средний", "upper": "верхний"}.get(x, x),
                    help="Выбор нижней/средней/верхней границы диапазона класса ISO 8608.",
                )
            with cI3:
                road["gd_n0_scale"] = st.number_input(
                    "Масштаб Gd(n0), ×",
                    min_value=0.05,
                    max_value=10.0,
                    value=float(road.get("gd_n0_scale", 1.0)),
                    step=0.05,
                    key=f"seg_iso_gd_scale_{uid}",
                    help="Множитель шероховатости внутри выбранного класса.",
                )

            cI4, cI5, cI6 = st.columns(3)
            with cI4:
                road["waviness_w"] = st.number_input(
                    "Показатель waviness w",
                    min_value=1.0,
                    max_value=3.0,
                    value=float(road.get("waviness_w", 2.0)),
                    step=0.1,
                    key=f"seg_iso_w_{uid}",
                    help="Показатель степенного закона PSD. Типичный инженерный выбор — около 2.",
                )
            with cI5:
                road["left_right_coherence"] = st.slider(
                    "Связь левый/правый трек",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(road.get("left_right_coherence", 0.5)),
                    step=0.05,
                    key=f"seg_iso_coh_{uid}",
                    help="0 = независимые треки, 1 = одинаковые треки.",
                )
            with cI6:
                road["seed"] = int(
                    st.number_input(
                        "Seed сегмента",
                        min_value=0,
                        value=int(road.get("seed", 0) or 0),
                        step=1,
                        key=f"seg_iso_seed_{uid}",
                        help="Локальный seed для сегмента. Если не менять — воспроизводимость задаётся этим значением.",
                    )
                )

            st.caption(
                "`dx_m` задаётся один раз для всего кольца вверху редактора и сохраняется в ring_v2 spec как технический параметр генерации."
            )
        else:
            # SINE: лев/прав отдельно
            cS1, cS2 = st.columns(2)
            with cS1:
                st.markdown("**Левая сторона**")
                road["aL_mm"] = st.number_input(
                    "Амплитуда A (полуразмах), мм",
                    min_value=0.0,
                    value=float(road.get("aL_mm", 5.0)),
                    step=0.5,
                    key=f"seg_sine_aL_{uid}",
                    help=(
                        "Амплитуда A синусоидальной неровности для **левой** колеи. "
                        "Важно: A=100 мм означает профиль от -100 до +100 мм относительно локального нуля; "
                        "полный размах p-p = 200 мм. 0 мм — ровная дорога."
                    ),
                )
                road["lambdaL_m"] = st.number_input(
                    "Длина волны, м",
                    min_value=0.1,
                    value=float(road.get("lambdaL_m", 2.0)),
                    step=0.1,
                    key=f"seg_sine_lL_{uid}",
                    help=(
                        "Пространственный период синусоиды (по оси движения) для левой колеи. "
                        "Меньше λ → более «частые» неровности. Типичный диапазон: 0.5…30 м."
                    ),
                )
                road["phaseL_deg"] = st.number_input(
                    "Фаза, °",
                    min_value=0.0,
                    max_value=360.0,
                    value=float(road.get("phaseL_deg", 0.0)),
                    step=5.0,
                    key=f"seg_sine_pL_{uid}",
                    help=(
                        "Начальная фаза синусоиды для левой колеи. "
                        "Используйте, если нужно сдвинуть профиль относительно начала сегмента."
                    ),
                )
            with cS2:
                st.markdown("**Правая сторона**")
                road["aR_mm"] = st.number_input(
                    "Амплитуда A (полуразмах), мм",
                    min_value=0.0,
                    value=float(road.get("aR_mm", 5.0)),
                    step=0.5,
                    key=f"seg_sine_aR_{uid}",
                    help=(
                        "Амплитуда A синусоидальной неровности для **правой** колеи. "
                        "Важно: A=100 мм означает профиль от -100 до +100 мм относительно локального нуля; "
                        "полный размах p-p = 200 мм. Если задать иначе, чем слева — получите «косую» дорогу."
                    ),
                )
                road["lambdaR_m"] = st.number_input(
                    "Длина волны, м",
                    min_value=0.1,
                    value=float(road.get("lambdaR_m", 2.0)),
                    step=0.1,
                    key=f"seg_sine_lR_{uid}",
                    help="Пространственный период синусоиды (по оси движения) для правой колеи.",
                )
                road["phaseR_deg"] = st.number_input(
                    "Фаза, °",
                    min_value=0.0,
                    max_value=360.0,
                    value=float(road.get("phaseR_deg", 0.0)),
                    step=5.0,
                    key=f"seg_sine_pR_{uid}",
                    help="Начальная фаза синусоиды для правой колеи.",
                )

            cSem1, cSem2 = st.columns(2)
            with cSem1:
                st.metric("Левая p-p (из A)", f"{2.0 * float(road.get('aL_mm', 0.0)):.1f} мм")
                st.caption(_format_sine_amplitude_semantics(float(road.get("aL_mm", 0.0))))
            with cSem2:
                st.metric("Правая p-p (из A)", f"{2.0 * float(road.get('aR_mm', 0.0)):.1f} мм")
                st.caption(_format_sine_amplitude_semantics(float(road.get("aR_mm", 0.0))))

            st.info(
                "Для SINE параметр 'Амплитуда A' = полуразмах. Если вы хотите получить профиль от -100 до +100 мм, задавайте A=100 мм. "
                "Если нужен общий перепад 100 мм от минимума до максимума, задавайте A=50 мм."
            )

            with st.expander("Случайность параметров синуса", expanded=False):
                st.caption(
                    "Если включить, то параметр будет случайно выбран из диапазона с вероятностью p. "
                    "Это удобно для генерации семейства сценариев." 
                    "Если не нужно — оставьте выключенным (детерминированный сценарий)."
                )
                st.markdown("**Амплитуда A (мм)**")
                cA = st.columns(2)
                with cA[0]:
                    road["rand_aL"] = st.checkbox(
                        "Случ. A_L",
                        value=bool(road.get("rand_aL", False)),
                        key=f"seg_rand_aL_{uid}",
                        help=(
                            "Если включено — амплитуда A_L (левая колея) может быть выбрана случайно (min/max) "
                            "с вероятностью p(A_L) для данного сегмента/прогона."
                        ),
                    )
                    road["rand_aL_p"] = st.slider(
                        "p(A_L)",
                        0.0,
                        1.0,
                        float(road.get("rand_aL_p", 0.5)),
                        0.05,
                        key=f"seg_rand_aL_p_{uid}",
                        help="Вероятность случайного выбора A_L (0 — никогда, 1 — всегда).",
                    )
                    road["rand_aL_lo_mm"] = st.number_input(
                        "A_L min, мм",
                        value=float(road.get("rand_aL_lo_mm", road.get("aL_mm", 5.0))),
                        step=0.5,
                        key=f"seg_rand_aL_lo_{uid}",
                        help="Нижняя граница случайной амплитуды A_L.",
                    )
                    road["rand_aL_hi_mm"] = st.number_input(
                        "A_L max, мм",
                        value=float(road.get("rand_aL_hi_mm", road.get("aL_mm", 5.0))),
                        step=0.5,
                        key=f"seg_rand_aL_hi_{uid}",
                        help="Верхняя граница случайной амплитуды A_L.",
                    )
                with cA[1]:
                    road["rand_aR"] = st.checkbox(
                        "Случ. A_R",
                        value=bool(road.get("rand_aR", False)),
                        key=f"seg_rand_aR_{uid}",
                        help="Если включено — A_R (правая) может быть выбрана случайно (min/max) по вероятности p(A_R).",
                    )
                    road["rand_aR_p"] = st.slider(
                        "p(A_R)",
                        0.0,
                        1.0,
                        float(road.get("rand_aR_p", 0.5)),
                        0.05,
                        key=f"seg_rand_aR_p_{uid}",
                        help="Вероятность случайного выбора A_R.",
                    )
                    road["rand_aR_lo_mm"] = st.number_input(
                        "A_R min, мм",
                        value=float(road.get("rand_aR_lo_mm", road.get("aR_mm", 5.0))),
                        step=0.5,
                        key=f"seg_rand_aR_lo_{uid}",
                        help="Нижняя граница случайной амплитуды A_R.",
                    )
                    road["rand_aR_hi_mm"] = st.number_input(
                        "A_R max, мм",
                        value=float(road.get("rand_aR_hi_mm", road.get("aR_mm", 5.0))),
                        step=0.5,
                        key=f"seg_rand_aR_hi_{uid}",
                        help="Верхняя граница случайной амплитуды A_R.",
                    )

                st.markdown("**Длина волны λ (м)**")
                cL = st.columns(2)
                with cL[0]:
                    road["rand_lL"] = st.checkbox(
                        "Случ. λ_L",
                        value=bool(road.get("rand_lL", False)),
                        key=f"seg_rand_lL_{uid}",
                        help="Если включено — λ_L (левая) может быть выбрана случайно (min/max) по вероятности p(λ_L).",
                    )
                    road["rand_lL_p"] = st.slider(
                        "p(λ_L)",
                        0.0,
                        1.0,
                        float(road.get("rand_lL_p", 0.5)),
                        0.05,
                        key=f"seg_rand_lL_p_{uid}",
                        help="Вероятность случайного выбора λ_L.",
                    )
                    road["rand_lL_lo_m"] = st.number_input(
                        "λ_L min, м",
                        value=float(road.get("rand_lL_lo_m", road.get("lambdaL_m", 2.0))),
                        step=0.1,
                        key=f"seg_rand_lL_lo_{uid}",
                        help="Нижняя граница случайной длины волны λ_L.",
                    )
                    road["rand_lL_hi_m"] = st.number_input(
                        "λ_L max, м",
                        value=float(road.get("rand_lL_hi_m", road.get("lambdaL_m", 2.0))),
                        step=0.1,
                        key=f"seg_rand_lL_hi_{uid}",
                        help="Верхняя граница случайной длины волны λ_L.",
                    )
                with cL[1]:
                    road["rand_lR"] = st.checkbox(
                        "Случ. λ_R",
                        value=bool(road.get("rand_lR", False)),
                        key=f"seg_rand_lR_{uid}",
                        help="Если включено — λ_R (правая) может быть выбрана случайно (min/max) по вероятности p(λ_R).",
                    )
                    road["rand_lR_p"] = st.slider(
                        "p(λ_R)",
                        0.0,
                        1.0,
                        float(road.get("rand_lR_p", 0.5)),
                        0.05,
                        key=f"seg_rand_lR_p_{uid}",
                        help="Вероятность случайного выбора λ_R.",
                    )
                    road["rand_lR_lo_m"] = st.number_input(
                        "λ_R min, м",
                        value=float(road.get("rand_lR_lo_m", road.get("lambdaR_m", 2.0))),
                        step=0.1,
                        key=f"seg_rand_lR_lo_{uid}",
                        help="Нижняя граница случайной длины волны λ_R.",
                    )
                    road["rand_lR_hi_m"] = st.number_input(
                        "λ_R max, м",
                        value=float(road.get("rand_lR_hi_m", road.get("lambdaR_m", 2.0))),
                        step=0.1,
                        key=f"seg_rand_lR_hi_{uid}",
                        help="Верхняя граница случайной длины волны λ_R.",
                    )

                st.markdown("**Фаза φ (°)**")
                cPh = st.columns(2)
                with cPh[0]:
                    road["rand_pL"] = st.checkbox(
                        "Случ. φ_L",
                        value=bool(road.get("rand_pL", False)),
                        key=f"seg_rand_pL_{uid}",
                        help="Если включено — фаза φ_L (левая) может быть выбрана случайно (min/max) по вероятности p(φ_L).",
                    )
                    road["rand_pL_p"] = st.slider(
                        "p(φ_L)",
                        0.0,
                        1.0,
                        float(road.get("rand_pL_p", 0.5)),
                        0.05,
                        key=f"seg_rand_pL_p_{uid}",
                        help="Вероятность случайного выбора φ_L.",
                    )
                    road["rand_pL_lo_deg"] = st.number_input(
                        "φ_L min, °",
                        value=float(road.get("rand_pL_lo_deg", 0.0)),
                        step=5.0,
                        key=f"seg_rand_pL_lo_{uid}",
                        help="Нижняя граница случайной фазы φ_L.",
                    )
                    road["rand_pL_hi_deg"] = st.number_input(
                        "φ_L max, °",
                        value=float(road.get("rand_pL_hi_deg", 360.0)),
                        step=5.0,
                        key=f"seg_rand_pL_hi_{uid}",
                        help="Верхняя граница случайной фазы φ_L.",
                    )
                with cPh[1]:
                    road["rand_pR"] = st.checkbox(
                        "Случ. φ_R",
                        value=bool(road.get("rand_pR", False)),
                        key=f"seg_rand_pR_{uid}",
                        help="Если включено — фаза φ_R (правая) может быть выбрана случайно (min/max) по вероятности p(φ_R).",
                    )
                    road["rand_pR_p"] = st.slider(
                        "p(φ_R)",
                        0.0,
                        1.0,
                        float(road.get("rand_pR_p", 0.5)),
                        0.05,
                        key=f"seg_rand_pR_p_{uid}",
                        help="Вероятность случайного выбора φ_R.",
                    )
                    road["rand_pR_lo_deg"] = st.number_input(
                        "φ_R min, °",
                        value=float(road.get("rand_pR_lo_deg", 0.0)),
                        step=5.0,
                        key=f"seg_rand_pR_lo_{uid}",
                        help="Нижняя граница случайной фазы φ_R.",
                    )
                    road["rand_pR_hi_deg"] = st.number_input(
                        "φ_R max, °",
                        value=float(road.get("rand_pR_hi_deg", 360.0)),
                        step=5.0,
                        key=f"seg_rand_pR_hi_{uid}",
                        help="Верхняя граница случайной фазы φ_R.",
                    )

        seg["road"] = road

        # События дороги
        st.markdown("#### События профиля (яма/препятствие)")
        events = list(seg.get("events", []))
        # таблица существующих
        if events:
            ev_df = pd.DataFrame(events)
            st.dataframe(ev_df, width="stretch", hide_index=True)
        else:
            st.caption("Событий пока нет.")

        with st.expander("Добавить событие", expanded=False):
            cE1, cE2, cE3, cE4 = st.columns([1.0, 1.0, 1.0, 1.0])
            with cE1:
                ev_kind = st.selectbox(
                    "Тип",
                    options=["яма", "препятствие"],
                    key=f"ev_kind_{uid}",
                    help="Яма — отрицательная глубина, препятствие — положительная.",
                )
            with cE2:
                ev_side = st.selectbox(
                    "Сторона",
                    options=["left", "right", "both"],
                    key=f"ev_side_{uid}",
                    help="left — левая колея, right — правая, both — обе.",
                )
            with cE3:
                ev_start = st.number_input(
                    "Начало, м",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key=f"ev_start_{uid}",
                    help="Позиция события внутри сегмента, в метрах от начала сегмента.",
                )
            with cE4:
                ev_len = st.number_input(
                    "Длина, м",
                    min_value=0.05,
                    value=0.3,
                    step=0.05,
                    key=f"ev_len_{uid}",
                    help="Длина события по координате дороги. Будет сглажено на краях.",
                )

            cE5, cE6 = st.columns([1.0, 1.0])
            with cE5:
                ev_depth = st.number_input(
                    "Глубина/высота, мм",
                    value=-30.0 if ev_kind == "яма" else 20.0,
                    step=1.0,
                    key=f"ev_depth_{uid}",
                    help="Для ямы — отрицательное значение (например −30 мм).",
                )
            with cE6:
                ev_ramp = st.number_input(
                    "Сглаживание края, м",
                    min_value=0.0,
                    value=0.1,
                    step=0.02,
                    key=f"ev_ramp_{uid}",
                    help="Длина «фаски» на входе/выходе. 0 — резче, но могут быть рывки. Рекомендуется 0.05–0.2 м.",
                )

            if st.button("Добавить событие", key=f"ev_add_{uid}"):
                events.append(
                    {
                        "kind": ev_kind,
                        "side": ev_side,
                        "start_m": float(ev_start),
                        "length_m": float(ev_len),
                        "depth_mm": float(ev_depth),
                        "ramp_m": float(ev_ramp),
                    }
                )
                seg["events"] = events
                st.success("Событие добавлено.")
                autosave_if_enabled(st)
                st.rerun()

        if events:
            def _road_event_short(ev: Dict[str, Any]) -> str:
                kind = str(ev.get("kind", ""))
                side = str(ev.get("side", ""))
                start = float(ev.get("start_m", 0.0))
                length = float(ev.get("length_m", 0.0))
                depth = float(ev.get("depth_mm", 0.0))
                if kind == "pothole":
                    return f"Яма {side}: s={start:.1f} м, L={length:.1f} м, глуб={depth:.0f} мм"
                if kind == "bump":
                    return f"Препятствие {side}: s={start:.1f} м, L={length:.1f} м, выс={depth:.0f} мм"
                return f"{kind or 'Событие'} {side}: s={start:.1f} м"

            cDel1, cDel2 = st.columns([3.0, 1.0])
            with cDel1:
                options = list(range(1, len(events) + 1))
                del_idx = st.selectbox(
                    "Событие для удаления",
                    options,
                    index=0,
                    format_func=lambda i: f"№{i}: {_road_event_short(events[i-1])}",
                    key=f"ev_del_idx_{uid}",
                    help=(
                        "Удаляет дорожное событие (яма/препятствие) из сегмента. "
                        "Исходные файлы на диске не затрагиваются — меняется только текущая конфигурация генератора."
                    ),
                )
            with cDel2:
                if st.button("Удалить", width="stretch", key=f"ev_del_btn_{uid}"):
                    try:
                        events.pop(int(del_idx) - 1)
                        seg["events"] = events
                        st.success("Событие удалено.")
                        autosave_if_enabled(st)
                        st.rerun()
                    except Exception:
                        st.error("Не удалось удалить событие.")

    v_end = _segment_end_speed_kph(v_start_kph, seg)
    seg["length_m"] = _segment_length_estimate_m(v_start_kph, seg)
    return seg, float(v_end)


def render_ring_scenario_generator(
    df_suite_edit: pd.DataFrame,
    *,
    work_dir: Path,
    wheelbase_m: float,
    default_dt_s: float,
) -> pd.DataFrame:
    """Рендерит секцию генератора и возвращает (возможно) обновлённый df_suite_edit.

    Важно: схема колонок должна соответствовать редактору тест‑набора (pneumo_ui_app).
    """
    spec = _ensure_ring_spec_in_state()

    st.subheader("Генератор сценариев/тестов: кольцо из сегментов")
    st.caption(
        "Последовательность: **1) описать кольцо → 2) проверить → 3) добавить в набор → 4) прогнать**. "
        "Канонический путь сценариев в проекте — именно ring editor: пользователь задаёт сегменты, повороты, скорости, "
        "продольный и поперечный уклоны дороги, а генератор уже строит совместимый профиль/ax/ay."
    )
    st.info(
        "Новая каноническая семантика сегмента: тип сегмента больше не является главным пользовательским понятием. "
        "Пользователь задаёт направление (прямо / влево / вправо), конечную скорость сегмента и параметры дороги. "
        "Legacy `drive_mode` сохраняется только как внутренний совместимый слой.",
        icon="ℹ️",
    )

    pending_n_seg_key = "_ring_n_segments_pending"
    if pending_n_seg_key in st.session_state:
        try:
            st.session_state["ring_n_segments"] = int(st.session_state.pop(pending_n_seg_key))
        except Exception:
            st.session_state.pop(pending_n_seg_key, None)

    colTop1, colTop2, colTop3, colTop4, colTop5 = st.columns([1.2, 1.0, 1.0, 1.0, 1.0])
    with colTop1:
        spec["v0_kph"] = st.number_input(
            "Начальная скорость кольца, км/ч",
            min_value=0.0,
            value=float(spec.get("v0_kph", _resolve_initial_speed_kph(spec) or 40.0)),
            step=1.0,
            help=(
                "Скорость в начале первого сегмента. "
                "Конец последнего сегмента автоматически замыкается в это же значение, чтобы кольцо было непрерывным по скорости."
            ),
        )
    v0_eff_kph = float(_resolve_initial_speed_kph(spec))
    if float(spec.get("v0_kph", 0.0) or 0.0) <= 0.0 and v0_eff_kph > 0.0:
        st.info(f"Начальная скорость кольца не задана явно: для расчёта и экспорта будет использована эффективная v0_kph={v0_eff_kph:.1f} км/ч (из первого сегмента).")

    with colTop2:
        n_laps = st.number_input(
            "Количество кругов (раз)",
            min_value=1,
            value=int(st.session_state.get("ring_n_laps", spec.get("n_laps", 1))),
            step=1,
            help="Тест повторяет кольцо N раз. Это удобно для установившихся режимов и статистики.",
        )
    with colTop3:
        seed = st.number_input(
            "Seed сценария",
            min_value=0,
            value=int(st.session_state.get("ring_seed", spec.get("seed", 123))),
            step=1,
            help="Общий seed (если сегмент не задаёт свой). Для воспроизводимости.",
        )
    with colTop4:
        dx_m = st.number_input(
            "Шаг профиля dx, м",
            min_value=0.005,
            max_value=0.2,
            value=float(st.session_state.get("ring_dx_m", spec.get("dx_m", 0.02))),
            step=0.005,
            format="%.3f",
            help="Шаг дискретизации профиля дороги. Меньше dx — детальнее профиль и тяжелее CSV.",
        )
    with colTop5:
        track_m = st.number_input(
            "Колея, м",
            min_value=0.2,
            max_value=3.5,
            value=float(spec.get("track_m", 1.0) or 1.0),
            step=0.05,
            help=(
                "Колея используется для перевода поперечного уклона сегмента в реальную разницу высот между левой и правой колеёй."
            ),
        )

    spec["schema_version"] = "ring_v2"
    spec["seed"] = int(seed)
    spec["dx_m"] = float(dx_m)
    spec["n_laps"] = int(n_laps)
    spec["wheelbase_m"] = float(wheelbase_m)
    spec["track_m"] = float(track_m)
    spec["closure_policy"] = str(spec.get("closure_policy", "closed_c1_periodic") or "closed_c1_periodic")

    # 1) Сегменты
    st.markdown("### 1) Сегменты кольца")
    n_seg = st.slider(
        "Количество сегментов",
        min_value=1,
        max_value=12,
        value=int(st.session_state.get("ring_n_segments", max(1, len(spec.get("segments", []))))),
        step=1,
        help="Если нужен сложный сценарий — лучше больше коротких сегментов, чем один «комбайн».",
    )

    segs = list(spec.get("segments", []))
    _ensure_segment_uids(segs)

    # Синхронизация количества сегментов с контролом (и наоборот)
    target_n = int(n_seg)
    if len(segs) < target_n:
        # Добавляем новые сегменты как "копию" последнего (с новым uid), чтобы сохранялась логика набора.
        while len(segs) < target_n:
            if segs:
                new_seg = copy.deepcopy(segs[-1])
            else:
                new_seg = _default_ring_spec()["segments"][0]
            new_seg["uid"] = _new_uid()
            # имя — по умолчанию, чтобы пользователь сразу видел новый сегмент
            new_seg["name"] = str(new_seg.get("name") or "Новый сегмент")
            segs.append(new_seg)
        _ensure_segment_uids(segs)
    elif len(segs) > target_n:
        segs = segs[:target_n]

    # --- Выбор сегмента (по uid, чтобы не "прыгал" при вставках/перестановках) ---
    sel_uid_key = "ring_sel_seg_uid"

    # Back-compat: если где-то остался индекс, пробуем перевести его в uid.
    if (sel_uid_key not in st.session_state) and ("ring_sel_seg_idx" in st.session_state):
        try:
            old_idx = int(st.session_state.get("ring_sel_seg_idx") or 0)
        except Exception:
            old_idx = 0
        if 0 <= old_idx < len(segs):
            st.session_state[sel_uid_key] = str(segs[old_idx].get("uid") or "")
        elif segs:
            st.session_state[sel_uid_key] = str(segs[0].get("uid") or "")

    uids = [str(s.get("uid") or "") for s in segs]
    _ensure_segment_uids(segs)
    uids = [str(s.get("uid") or "") for s in segs]

    if not uids:
        st.warning("Сегменты отсутствуют. Добавьте хотя бы один сегмент.")
        st.session_state["ring_scenario_spec"] = spec
        st.stop()

    # Гарантируем валидный выбор
    cur_uid = str(st.session_state.get(sel_uid_key) or "")
    if cur_uid not in uids:
        cur_uid = uids[0]
        st.session_state[sel_uid_key] = cur_uid

    uid_to_idx = {uid: i for i, uid in enumerate(uids)}

    # Сводка для списка выбора (и компактная таблица)
    # Важно: v_start_kph меняется от сегмента к сегменту (цепочка скоростей по кольцу).
    v0_kph = float(_resolve_initial_speed_kph(spec))
    v_flow_kph = float(v0_kph)

    v_starts: List[float] = []
    v_ends: List[float] = []
    seg_lens_m: List[float] = []
    road_state_starts, road_state_ends = _derive_ring_road_state_flow(segs)

    seg_summaries: List[str] = []
    seg_rows: List[Dict[str, Any]] = []

    for i, seg in enumerate(segs):
        v_start_i = float(v_flow_kph)
        v_starts.append(v_start_i)

        seg_len = _segment_length_estimate_m(v_start_i, seg)
        v_end = _segment_end_speed_kph(v_start_i, seg)

        seg_lens_m.append(float(seg_len))
        v_ends.append(float(v_end))
        turn_i = str((seg.get("turn_direction") or _segment_motion_contract(seg, v_start_i)["turn_direction"]) or "STRAIGHT").upper()
        road_end_i = road_state_ends[i] if i < len(road_state_ends) else {"center_height_mm": 0.0, "cross_slope_pct": 0.0}

        name_i = str(seg.get("name") or f"S{i+1}")
        seg_summaries.append(
            f"{i+1}. {name_i} • {_turn_direction_label(turn_i)} • {seg_len:.0f} м • "
            f"v {v_start_i:.0f}→{v_end:.0f} км/ч • z1 {float(road_end_i['center_height_mm']):.0f} мм"
        )
        seg_rows.append(
            {
                "№": i + 1,
                "Название": name_i,
                "Поворот": _turn_direction_label(turn_i),
                "v0, км/ч": float(f"{v_start_i:.1f}"),
                "v1, км/ч": float(f"{v_end:.1f}"),
                "≈длина, м": float(f"{seg_len:.1f}"),
                "z конца, мм": float(f"{float(road_end_i['center_height_mm']):.1f}"),
                "поперечный уклон конца, %": float(f"{float(road_end_i['cross_slope_pct']):.2f}"),
            }
        )

        # проталкиваем скорость дальше по цепочке
        v_flow_kph = float(v_end)

    uid_to_summary = {seg.get("uid"): seg_summaries[i] for i, seg in enumerate(segs)}

    # --- Действия с сегментом ---
    st.markdown("**Действия с сегментом**")
    btn1, btn2, btn3 = st.columns(3)
    btn4, btn5 = st.columns(2)

    def _clone_segment(src: Dict[str, Any], name_suffix: str = " (копия)") -> Dict[str, Any]:
        out = copy.deepcopy(src)
        out["uid"] = _new_uid()
        nm = str(out.get("name") or "").strip()
        out["name"] = (nm + name_suffix) if nm else "Копия сегмента"
        return out

    def _blank_after(src: Dict[str, Any]) -> Dict[str, Any]:
        out = copy.deepcopy(src)
        out["uid"] = _new_uid()
        out["name"] = "Новый сегмент"
        # Стартовая скорость — логично брать из конца предыдущего
        try:
            v_prev = float(src.get("speed_end_kph", src.get("speed_start_kph", 60.0)) or 60.0)
        except Exception:
            v_prev = 60.0
        out["speed_start_kph"] = v_prev
        out["speed_end_kph"] = v_prev
        out["turn_direction"] = str(out.get("turn_direction") or "STRAIGHT").upper()
        out["accel_time_s"] = 0.0
        out["brake_time_s"] = 0.0
        return out

    # Двухшаговое подтверждение удаления (опасная операция)
    del_arm_key = "ring_seg_delete_arm_uid"
    armed_uid = str(st.session_state.get(del_arm_key) or "")
    if armed_uid and armed_uid != cur_uid:
        st.session_state[del_arm_key] = ""

    if btn1.button("Добавить", help="Добавить новый сегмент сразу после выбранного (на основе текущего)."):
        i = uid_to_idx.get(cur_uid, 0)
        new_seg = _blank_after(segs[i])
        segs.insert(i + 1, new_seg)
        _ensure_segment_uids(segs)
        st.session_state[sel_uid_key] = str(new_seg.get("uid"))
        st.session_state[pending_n_seg_key] = len(segs)
        st.session_state[del_arm_key] = ""
        st.rerun()

    if btn2.button("Дублировать", help="Создать копию выбранного сегмента и вставить её сразу после него."):
        i = uid_to_idx.get(cur_uid, 0)
        new_seg = _clone_segment(segs[i])
        segs.insert(i + 1, new_seg)
        _ensure_segment_uids(segs)
        st.session_state[sel_uid_key] = str(new_seg.get("uid"))
        st.session_state[pending_n_seg_key] = len(segs)
        st.session_state[del_arm_key] = ""
        st.rerun()

    if btn3.button("Удалить", help="Удалить выбранный сегмент. Требуется повторное нажатие для подтверждения.", disabled=(len(segs) <= 1)):
        if str(st.session_state.get(del_arm_key) or "") != cur_uid:
            st.session_state[del_arm_key] = cur_uid
            st.warning("Подтверждение: нажмите «Удалить» ещё раз, чтобы удалить сегмент.")
            st.stop()
        else:
            i = uid_to_idx.get(cur_uid, 0)
            segs.pop(i)
            _ensure_segment_uids(segs)
            # Новый выбор — ближайший сегмент
            new_i = min(i, len(segs) - 1)
            st.session_state[sel_uid_key] = str(segs[new_i].get("uid"))
            st.session_state[pending_n_seg_key] = len(segs)
            st.session_state[del_arm_key] = ""
            st.rerun()

    if btn4.button("Вверх", help="Переместить сегмент на одну позицию вверх (в начало кольца).", disabled=(uid_to_idx.get(cur_uid, 0) <= 0)):
        i = uid_to_idx.get(cur_uid, 0)
        segs[i - 1], segs[i] = segs[i], segs[i - 1]
        _ensure_segment_uids(segs)
        st.session_state[del_arm_key] = ""
        st.rerun()

    if btn5.button("Вниз", help="Переместить сегмент на одну позицию вниз (к концу кольца).", disabled=(uid_to_idx.get(cur_uid, 0) >= len(segs) - 1)):
        i = uid_to_idx.get(cur_uid, 0)
        segs[i + 1], segs[i] = segs[i], segs[i + 1]
        _ensure_segment_uids(segs)
        st.session_state[del_arm_key] = ""
        st.rerun()

    # --- Выбор сегмента ---
    # (значение хранится в st.session_state[sel_uid_key])
    st.radio(
        "Выберите сегмент",
        options=uids,
        index=uids.index(cur_uid),
        format_func=lambda uid: uid_to_summary.get(uid, str(uid)),
        key=sel_uid_key,
    )

    cur_uid = str(st.session_state.get(sel_uid_key) or uids[0])
    cur_idx = uid_to_idx.get(cur_uid, 0)

    # Таблица-сводка (быстро воспринимается)
    st.dataframe(pd.DataFrame(seg_rows), width="stretch", hide_index=True)

    # --- Редактор выбранного сегмента ---
    # v_start_kph для текущего сегмента берём из цепочки скоростей (v0_kph + пред. сегменты)
    v_start_cur = float(v_starts[cur_idx] if 0 <= cur_idx < len(v_starts) else v0_kph)
    road_start_cur = road_state_starts[cur_idx] if 0 <= cur_idx < len(road_state_starts) else {"center_height_mm": 0.0, "cross_slope_pct": 0.0}
    ring_road_start = road_state_starts[0] if road_state_starts else {"center_height_mm": 0.0, "cross_slope_pct": 0.0}

    updated_seg, v_end_cur = _render_segment_editor(
        segs[cur_idx],
        idx=cur_idx,
        v_start_kph=v_start_cur,
        ring_start_speed_kph=float(v0_kph),
        is_first=bool(cur_idx == 0),
        is_last=bool(cur_idx == len(segs) - 1),
        road_start_center_mm=float(road_start_cur["center_height_mm"]),
        road_start_cross_pct=float(road_start_cur["cross_slope_pct"]),
        ring_start_center_mm=float(ring_road_start["center_height_mm"]),
        ring_start_cross_pct=float(ring_road_start["cross_slope_pct"]),
    )
    if not isinstance(updated_seg, dict):
        updated_seg = dict(segs[cur_idx])
    updated_seg["uid"] = cur_uid  # фиксируем uid, чтобы не потерялся
    segs[cur_idx] = updated_seg

    spec["segments"] = segs
    st.session_state["ring_scenario_spec"] = spec

    # 2) Валидация
    st.markdown("### 2) Проверка сценария")
    report = validate_ring_spec(spec)
    if report["errors"]:
        for e in report["errors"]:
            st.error(e)
    if report["warnings"]:
        for w in report["warnings"]:
            st.warning(w)

    # быстрые метрики кольца
    # (пересчитываем длины/скорости по обновлённым сегментам)
    try:
        v_flow_kph2 = float(_resolve_initial_speed_kph(spec))
        lap_len_m = 0.0
        for seg in segs:
            lap_len_m += float(_segment_length_estimate_m(v_flow_kph2, seg))
            v_flow_kph2 = float(_segment_end_speed_kph(v_flow_kph2, seg))
    except Exception:
        lap_len_m = 0.0

    lap_time_s = float(sum(float(s.get("duration_s", 0.0) or 0.0) for s in segs))
    m1, m2, m3 = st.columns(3)
    m1.metric("Длительность 1 круга", f"{lap_time_s:.1f} c")
    m2.metric("Длина 1 круга", f"≈ {lap_len_m:.1f} м")
    m3.metric("Всего время теста", f"≈ {lap_time_s*int(n_laps):.1f} c")

    show_preview = st.checkbox(
        "Показать предпросмотр (скорость/ay + дорога)",
        value=False,
        help="Графики могут быть тяжёлыми. По умолчанию выключено (гейт).",
    )
    if show_preview and not report["errors"]:
        try:
            from .scenario_ring import generate_ring_drive_profile, generate_ring_tracks
            import numpy as np

            drive = generate_ring_drive_profile(spec, dt_s=0.02, n_laps=1)
            tracks = generate_ring_tracks(spec, dx_m=float(spec.get("dx_m", 0.02)), seed=int(seed))
            x = tracks["x_m"]
            zL = tracks["zL_m"]
            zR = tracks["zR_m"]

            try:
                spanL_mm = float(1000.0 * (np.nanmax(zL) - np.nanmin(zL)))
                spanR_mm = float(1000.0 * (np.nanmax(zR) - np.nanmin(zR)))
                medL = float(np.nanmedian(zL))
                medR = float(np.nanmedian(zR))
                ampL_mm = float(1000.0 * np.nanmax(np.abs(zL - medL)))
                ampR_mm = float(1000.0 * np.nanmax(np.abs(zR - medR)))
                seamL_mm = float(1000.0 * abs(float(zL[-1] - zL[0]))) if len(zL) else 0.0
                seamR_mm = float(1000.0 * abs(float(zR[-1] - zR[0]))) if len(zR) else 0.0
                seam_mm = float(max(seamL_mm, seamR_mm))
                x_end_m = float(x[-1] - x[0]) if len(x) else 0.0
                closure_policy = str((tracks.get("meta", {}) or {}).get("closure_policy", spec.get("closure_policy", "strict_exact")) or "strict_exact")
            except Exception:
                spanL_mm = 0.0
                spanR_mm = 0.0
                ampL_mm = 0.0
                ampR_mm = 0.0
                seamL_mm = 0.0
                seamR_mm = 0.0
                seam_mm = 0.0
                x_end_m = 0.0
                closure_policy = str(spec.get("closure_policy", "strict_exact") or "strict_exact")

            rawSeamL_mm = float(1000.0 * abs(float((tracks.get("meta", {}) or {}).get("raw_seam_jump_left_m", 0.0) or 0.0)))
            rawSeamR_mm = float(1000.0 * abs(float((tracks.get("meta", {}) or {}).get("raw_seam_jump_right_m", 0.0) or 0.0)))
            corrL_mm = float(1000.0 * abs(float((tracks.get("meta", {}) or {}).get("closure_correction_left_max_m", 0.0) or 0.0)))
            corrR_mm = float(1000.0 * abs(float((tracks.get("meta", {}) or {}).get("closure_correction_right_max_m", 0.0) or 0.0)))
            v_end_ring_kph = float(v_flow_kph2)
            cM1, cM2, cM3, cM4 = st.columns(4)
            cM1.metric("Профиль ВСЕГО кольца: amplitude A L/R (служ.)", f"{ampL_mm:.1f} / {ampR_mm:.1f} мм")
            cM2.metric("Профиль ВСЕГО кольца: p-p=max-min L/R (НЕ A)", f"{spanL_mm:.1f} / {spanR_mm:.1f} мм")
            cM3.metric("Шов круга L/R (после closure)", f"{seamL_mm:.1f} / {seamR_mm:.1f} мм")
            cM4.metric("Стык скорости start→end", f"{v0_eff_kph:.1f} → {v_end_ring_kph:.1f} км/ч")
            if str(closure_policy) == "closed_c1_periodic":
                st.caption(
                    f"closure_policy={closure_policy}. Кольцо замыкается плавной C1-коррекцией без линейной скрытой 'подтяжки': raw seam L/R = {rawSeamL_mm:.1f}/{rawSeamR_mm:.1f} мм, post seam = {seamL_mm:.1f}/{seamR_mm:.1f} мм, max correction = {corrL_mm:.1f}/{corrR_mm:.1f} мм. Коорд. x конца = {x_end_m:.2f} м."
                )
            else:
                st.caption(
                    f"closure_policy={closure_policy}. Генератор не делает скрытых closure/baseline/mean корректировок: whole-ring p-p и amplitude A разделены намеренно, а шов показывается как есть. Коорд. x конца = {x_end_m:.2f} м."
                )
            if max(spanL_mm, spanR_mm) > 300.0:
                st.warning(
                    f"Подозрительно большой перепад дороги по ВСЕМУ кольцу: L/R = {spanL_mm:.1f} / {spanR_mm:.1f} мм. Это не амплитуда выбранного сегмента. Проверьте единицы в aL_mm/aR_mm/depth_mm и параметры событий. Канон ожидает миллиметры, не метры."
                )
            if str(closure_policy) == "strict_exact" and seam_mm > 20.0:
                st.warning(
                    f"Профиль не замыкается по высоте: шов круга L/R = {seamL_mm:.1f} / {seamR_mm:.1f} мм. Выбран strict_exact — генератор сохраняет профиль строго как задано и не скрывает это closure-коррекцией."
                )
            if abs(v_end_ring_kph - v0_eff_kph) > 0.5:
                st.warning(
                    f"Стык скорости кольца не замкнут: start={v0_eff_kph:.1f} км/ч, end={v_end_ring_kph:.1f} км/ч. Для настоящего кольца скорости начала и конца должны совпадать."
                )
            st.caption("Важно: start_m и length_m у событий профиля задаются в метрах ВНУТРИ текущего сегмента, не по длине всего кольца.")

            # Локальный предпросмотр выбранного сегмента: помогает не путать амплитуду
            # выбранного SINE-сегмента с полным перепадом кольца после стыковки сегментов.
            try:
                seg_lengths = []
                for jj, seg_obj in enumerate(segs):
                    Ljj = float(seg_obj.get("length_m", 0.0) or 0.0)
                    if Ljj <= 0.0:
                        vj = float(v_starts[jj] if 0 <= jj < len(v_starts) else _resolve_initial_speed_kph(spec))
                        Ljj = float(_segment_length_estimate_m(vj, seg_obj))
                    seg_lengths.append(max(0.0, Ljj))
                cur_start_m = float(sum(seg_lengths[:cur_idx]))
                cur_len_m = float(seg_lengths[cur_idx] if 0 <= cur_idx < len(seg_lengths) else 0.0)
                mask_cur = (np.asarray(x, dtype=float) >= cur_start_m - 1e-9) & (np.asarray(x, dtype=float) <= cur_start_m + cur_len_m + 1e-9)
                x_cur = np.asarray(x, dtype=float)[mask_cur] - cur_start_m
                zL_cur = np.asarray(zL, dtype=float)[mask_cur]
                zR_cur = np.asarray(zR, dtype=float)[mask_cur]
                if x_cur.size >= 2 and zL_cur.size == x_cur.size and zR_cur.size == x_cur.size:
                    zL_med = float(np.nanmedian(zL_cur))
                    zR_med = float(np.nanmedian(zR_cur))
                    aL_local_mm = float(1000.0 * np.nanmax(np.abs(zL_cur - zL_med)))
                    aR_local_mm = float(1000.0 * np.nanmax(np.abs(zR_cur - zR_med)))
                    spanL_local_mm = float(1000.0 * (np.nanmax(zL_cur) - np.nanmin(zL_cur)))
                    spanR_local_mm = float(1000.0 * (np.nanmax(zR_cur) - np.nanmin(zR_cur)))
                    cur_road = dict(segs[cur_idx].get("road", {}))
                    cur_mode = str(cur_road.get("mode", "ISO8608")).upper()
                    st.markdown("#### Локальный предпросмотр выбранного сегмента")
                    cS1, cS2, cS3 = st.columns(3)
                    cS1.metric("Локальная x длина", f"{float(x_cur[-1] - x_cur[0]):.2f} м")
                    cS2.metric("Локал. amplitude A L/R", f"{aL_local_mm:.1f} / {aR_local_mm:.1f} мм")
                    cS3.metric("Локал. p-p=max-min L/R (НЕ A)", f"{spanL_local_mm:.1f} / {spanR_local_mm:.1f} мм")
                    if cur_mode in ("SIN", "SINE", "SINUS", "SINUSOID"):
                        req_aL_mm = float(cur_road.get("aL_mm", 0.0) or 0.0)
                        req_aR_mm = float(cur_road.get("aR_mm", 0.0) or 0.0)
                        st.caption(
                            f"SINE-контроль для выбранного сегмента: запрос L/R = {req_aL_mm:.1f} / {req_aR_mm:.1f} мм; "
                            f"локально получено ≈ {aL_local_mm:.1f} / {aR_local_mm:.1f} мм (оценка по |z - median|, без влияния общего сдвига кольца)."
                        )
                        if req_aL_mm > 0.0 and abs(aL_local_mm - req_aL_mm) > max(2.0, 0.15 * req_aL_mm):
                            st.warning(f"Левая SINE-амплитуда выбранного сегмента выглядит подозрительно: запрос {req_aL_mm:.1f} мм, локально ≈ {aL_local_mm:.1f} мм.")
                        if req_aR_mm > 0.0 and abs(aR_local_mm - req_aR_mm) > max(2.0, 0.15 * req_aR_mm):
                            st.warning(f"Правая SINE-амплитуда выбранного сегмента выглядит подозрительно: запрос {req_aR_mm:.1f} мм, локально ≈ {aR_local_mm:.1f} мм.")

                    try:
                        seg_rows = summarize_ring_track_segments(spec, tracks)
                    except Exception:
                        seg_rows = []
                    if seg_rows:
                        df_seg = pd.DataFrame(seg_rows)
                        df_view = pd.DataFrame({
                            "Сегмент": df_seg["seg_idx"],
                            "Имя": df_seg["name"],
                            "Поворот": df_seg["turn_direction"],
                            "v0, км/ч": df_seg["speed_start_kph"].round(2),
                            "v1, км/ч": df_seg["speed_end_kph"].round(2),
                            "Дорога": df_seg["road_mode"],
                            "x0, м": df_seg["x_start_m"].round(3),
                            "x1, м": df_seg["x_end_m"].round(3),
                            "L сегм., м": df_seg["length_m"].round(3),
                            "z центра 0→1, мм": (df_seg["center_height_end_mm"] - df_seg["center_height_start_mm"]).round(2),
                            "поперечный уклон 0→1, %": (df_seg["cross_slope_end_pct"] - df_seg["cross_slope_start_pct"]).round(2),
                            "x факт, м": df_seg["generated_x_local_end_m"].round(3),
                            "Л A зад., мм": df_seg["aL_req_mm"].round(2),
                            "Л A факт, мм": df_seg["L_amp_mm"].round(2),
                            "Л p-p, мм": df_seg["L_p2p_mm"].round(2),
                            "Л z0→z1, мм": (df_seg["L_z_end_mm"] - df_seg["L_z_start_mm"]).round(2),
                            "П A зад., мм": df_seg["aR_req_mm"].round(2),
                            "П A факт, мм": df_seg["R_amp_mm"].round(2),
                            "П p-p, мм": df_seg["R_p2p_mm"].round(2),
                            "П z0→z1, мм": (df_seg["R_z_end_mm"] - df_seg["R_z_start_mm"]).round(2),
                        })
                        st.caption("Сводка ниже специально разделяет amplitude A и peak-to-peak (p-p = max-min). Для синуса p-p = 2A, поэтому p-p нельзя читать как амплитуду A.")
                        st.dataframe(df_view, width="stretch", hide_index=True)

                    try:
                        import plotly.graph_objects as go
                        palette = [
                            "#ff6b6b", "#4ecdc4", "#ffe66d", "#5dade2", "#af7ac5", "#58d68d",
                            "#f5b041", "#ec7063", "#48c9b0", "#85c1e9", "#c39bd3", "#7dcea0",
                        ]
                        with st.expander("DEBUG: кольцо целиком (не основной способ подсветки сегментов)", expanded=False):
                            st.caption("Основная цветовая подсветка сегментов должна быть в 3D и в cockpit animator. Этот график оставлен только для отладки whole-ring seam/segment continuity.")
                            fig_ring = go.Figure()
                            for jj, row_seg in enumerate(seg_rows):
                                xs0 = float(row_seg.get("x_start_m", 0.0) or 0.0)
                                xs1 = float(row_seg.get("x_end_m", xs0) or xs0)
                                mseg = (np.asarray(x, dtype=float) >= xs0 - 1e-9) & (np.asarray(x, dtype=float) <= xs1 + 1e-9)
                                xxs = np.asarray(x, dtype=float)[mseg]
                                zls = np.asarray(zL, dtype=float)[mseg]
                                zrs = np.asarray(zR, dtype=float)[mseg]
                                if xxs.size < 2:
                                    continue
                                col_seg = palette[jj % len(palette)]
                                name_seg = str(row_seg.get("name", f"S{jj+1}"))
                                fig_ring.add_trace(go.Scatter(x=xxs, y=zls, mode="lines", line={"color": col_seg, "width": 4}, name=f"{name_seg} / левая", legendgroup=name_seg, showlegend=True))
                                fig_ring.add_trace(go.Scatter(x=xxs, y=zrs, mode="lines", line={"color": col_seg, "width": 4, "dash": "solid"}, opacity=0.72, name=f"{name_seg} / правая", legendgroup=name_seg, showlegend=False))
                                if jj > 0:
                                    fig_ring.add_vline(x=xs0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.22)")
                            fig_ring.update_layout(
                                title="DEBUG: кольцо целиком — толстые крайние линии по сегментам",
                                xaxis_title="x вдоль кольца, м",
                                yaxis_title="z дороги, м",
                                legend_title="Сегменты",
                                margin=dict(l=10, r=10, t=40, b=10),
                                height=360,
                            )
                            st.plotly_chart(fig_ring, width="stretch", key=f"ring_plot_segments_{cur_idx}_{int(seed)}")
                    except Exception:
                        pass

                    cP1, cP2 = st.columns(2)
                    with cP1:
                        st.line_chart(pd.DataFrame({"скорость, м/с": drive["v_mps"], "ay, м/с²": drive["ay_mps2"]}, index=drive["t_s"]))
                    with cP2:
                        st.line_chart(pd.DataFrame({"левая, м": zL, "правая, м": zR}, index=x))

                    cP3, cP4 = st.columns(2)
                    with cP3:
                        st.line_chart(pd.DataFrame({"левая, м": zL_cur, "правая, м": zR_cur}, index=x_cur))
                    with cP4:
                        st.line_chart(pd.DataFrame({"левая- median, м": zL_cur - zL_med, "правая- median, м": zR_cur - zR_med}, index=x_cur))
                else:
                    cP1, cP2 = st.columns(2)
                    with cP1:
                        st.line_chart(pd.DataFrame({"скорость, м/с": drive["v_mps"], "ay, м/с²": drive["ay_mps2"]}, index=drive["t_s"]))
                    with cP2:
                        st.line_chart(pd.DataFrame({"левая, м": zL, "правая, м": zR}, index=x))
            except Exception:
                cP1, cP2 = st.columns(2)
                with cP1:
                    st.line_chart(pd.DataFrame({"скорость, м/с": drive["v_mps"], "ay, м/с²": drive["ay_mps2"]}, index=drive["t_s"]))
                with cP2:
                    st.line_chart(pd.DataFrame({"левая, м": zL, "правая, м": zR}, index=x))
        except Exception as e:
            st.error(f"Не удалось построить предпросмотр: {e}")

    # 3) Добавить в набор
    st.markdown("### 3) Добавить в набор тестов")
    colAdd1, colAdd2, colAdd3, colAdd4 = st.columns([1.2, 1.2, 1.0, 0.9])
    with colAdd1:
        test_name = st.text_input(
            "Имя теста",
            value=str(st.session_state.get("ring_test_name", "ring_test_01")),
            help="Короткое имя теста. Будет видно в наборе тестов и логах.",
        )
    with colAdd2:
        desc = st.text_input(
            "Описание",
            value=str(st.session_state.get("ring_test_desc", "Кольцо (сегменты)")),
            help="Короткая инженерная пометка: что проверяем этим тестом.",
        )
    with colAdd3:
        dt_s = st.number_input(
            "Шаг dt, с",
            min_value=0.001,
            value=float(st.session_state.get("ring_dt_s", default_dt_s)),
            step=0.001,
            format="%.3f",
            help="Шаг интегрирования для симуляции. Обычно совпадает с dt в наборе тестов.",
        )
    with colAdd4:
        try:
            _ring_stage_default = max(0, int(st.session_state.get("ring_stage_num", _guess_suite_stage(df_suite_edit)) or 0))
        except Exception:
            _ring_stage_default = max(0, int(_guess_suite_stage(df_suite_edit) or 0))
        st.session_state["ring_stage_num"] = int(_ring_stage_default)
        stage_num = int(
            st.number_input(
                "Стадия",
                min_value=0,
                value=int(_ring_stage_default),
                step=1,
                key="ring_stage_num",
                help="Явный номер стадии для строки suite. Нумерация 0-based: первая стадия = 0. Никакой скрытой автоподстановки больше нет.",
            )
        )

    spec["dt_s"] = float(dt_s)
    spec["n_laps"] = int(n_laps)
    spec["seed"] = int(seed)
    spec["dx_m"] = float(dx_m)
    spec["wheelbase_m"] = float(wheelbase_m)

    # 4) Генерация файлов и вставка в suite
    can_generate = (not report["errors"]) and (len(str(test_name).strip()) > 0)
    if not can_generate:
        st.info("Заполните сценарий без ошибок и задайте ID теста — тогда появится кнопка генерации.")

    if st.button(
        "Сгенерировать файлы (road_csv + axay_csv) и добавить в набор",
        disabled=not can_generate,
        help="Создаёт файлы сценария и добавляет/обновляет строку в наборе тестов.",
    ):
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_dir = Path(work_dir) / "scenarios" / f"{test_name}_{ts}"
            out = generate_ring_scenario_bundle(
                spec,
                out_dir=out_dir,
                dt_s=float(dt_s),
                n_laps=int(n_laps),
                wheelbase_m=float(wheelbase_m),
                dx_m=float(spec.get("dx_m", 0.02)),
                seed=int(seed),
                tag=str(test_name),
            )

            # Указатель «последний сценарий» (для автоподхвата в других страницах/модулях)
            try:
                from pneumo_solver_ui.run_artifacts import save_last_scenario_ptr

                save_last_scenario_ptr(
                    Path(out["scenario_json"]),
                    meta={
                        "scenario_kind": "ring",
                        "test_name": str(test_name),
                        "n_segments": int(n_seg),
                        "n_laps": int(n_laps),
                        "seed": int(seed),
                        "dt_s": float(dt_s),
                        "work_dir": str(Path(work_dir)),
                    },
                )
            except Exception:
                # Не критично для генерации; это «удобство».
                pass

            # добавить / обновить строку в suite
            df = df_suite_edit.copy()
            # R154+ canonical suite schema columns (no compatibility bridges)
            for col in [
                "включен",
                "стадия",
                "имя",
                "описание",
                "тип",
                "dt",
                "t_end",
                "road_len_m",
                "vx0_м_с",
                "ax0_м_с2",
                "road_csv",
                "axay_csv",
                "scenario_json",
            ]:
                if col not in df.columns:
                    df[col] = ""
            mask = df["имя"].astype(str) == str(test_name)

            # Timeline end
            t_end_s = float(out["meta"].get("dt_s", dt_s) * (out["meta"].get("n_samples", 0) - 1))
            v0_mps = max(float(_resolve_initial_speed_kph(spec)) / 3.6, 0.0)

            row = {
                "id": str(uuid.uuid4()),
                "включен": True,
                "стадия": int(stage_num),
                "имя": str(test_name),
                "описание": str(desc),
                # Ring bundle contains BOTH road_csv + axay_csv -> canonical type is maneuver_csv
                "тип": "maneuver_csv",
                "dt": float(dt_s),
                "t_end": float(t_end_s),
                # Derived helper for UI filtering only (still derived from model inputs)
                "road_len_m": float(out["meta"].get("ring_length_m", 0.0)) * float(n_laps),
                # Initial speed (derived from scenario spec, used by some runners)
                "vx0_м_с": float(v0_mps),
                "ax0_м_с2": 0.0,
                "road_csv": str(out["road_csv"]),
                "axay_csv": str(out["axay_csv"]),
                "scenario_json": str(out["scenario_json"]),
            }


            if mask.any():
                for k, v in row.items():
                    df.loc[mask, k] = v
                try:
                    sel_ids = [str(x).strip() for x in df.loc[mask, "id"].astype(str).tolist() if str(x).strip()]
                    st.session_state["ui_suite_selected_id"] = sel_ids[0] if sel_ids else str(row.get("id") or "")
                    st.session_state.pop("ui_suite_selected_row", None)
                    # Also preselect this test for detailed run page.
                    st.session_state["detail_test_pick"] = str(test_name)
                except Exception:
                    pass
            else:
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                # Select newly created test row in the suite UI.
                st.session_state["ui_suite_selected_id"] = str(row.get("id") or "")
                st.session_state.pop("ui_suite_selected_row", None)
                # Also preselect this test for detailed run page.
                st.session_state["detail_test_pick"] = str(test_name)

            # Make the scenario stage visible in the suite list filter.
            try:
                stage_i = int(row.get("стадия", 0))
            except Exception:
                stage_i = 0

            flt = st.session_state.get("ui_suite_stage_filter")
            if isinstance(flt, list) and stage_i not in flt:
                try:
                    pend = list(st.session_state.get("_ui_suite_stage_filter_extend_pending") or [])
                    pend.append(int(stage_i))
                    st.session_state["_ui_suite_stage_filter_extend_pending"] = sorted(set(int(x) for x in pend))
                except Exception:
                    pass

            # Remember snapshot of "all stages" for the suite UI auto-extend logic.
            try:
                all_stages = sorted(
                    set(
                        int(x)
                        for x in pd.to_numeric(df.get("стадия", 0), errors="coerce").fillna(0).tolist()
                    )
                )
                st.session_state["ui_suite_stage_all_prev"] = all_stages
            except Exception:
                pass

            st.session_state["df_suite_edit"] = df
            autosave_if_enabled(st)
            st.success(f"Сценарий создан и добавлен в набор. Папка: {out_dir}")
            st.rerun()
        except Exception as e:
            st.exception(e)

    return st.session_state.get("df_suite_edit", df_suite_edit)
