from __future__ import annotations

import json
from typing import Any, Callable

import numpy as np
import pandas as pd

from pneumo_solver_ui.ui_suite_card_shell_helpers import (
    render_app_suite_right_card_shell,
    render_heavy_suite_right_card_shell,
)
from pneumo_solver_ui.ui_suite_editor_shell_helpers import (
    format_suite_test_type_label,
    render_suite_empty_card_state,
    render_suite_missing_card_state,
)


WidgetKeyFn = Callable[[str, str], str]
SeedStateFn = Callable[[str, dict[str, Any]], None]
InferStageFn = Callable[[dict[str, Any]], int]
SaveUploadFn = Callable[[Any, str], str | None]
QueueSelectedIdFn = Callable[[str], None]
EnsureStageVisibleFn = Callable[[int], None]
SetFlashFn = Callable[[str, str], None]
EnsureSuiteColumnsFn = Callable[[pd.DataFrame], pd.DataFrame]


ENABLED_KEYS = ("включен", "РІРєР»СЋС‡РµРЅ")
NAME_KEYS = ("имя", "РёРјСЏ")
TYPE_KEYS = ("тип", "С‚РёРї")
SPEED_KEYS = ("vx0_м_с", "vx0_Рј_СЃ")
ANGLE_KEYS = ("угол_град", "СѓРіРѕР»_РіСЂР°Рґ")
SMOOTH_SHARE_KEYS = ("доля_плавной_стыковки", "РґРѕР»СЏ_РїР»Р°РІРЅРѕР№_СЃС‚С‹РєРѕРІРєРё")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


def _row_get(row: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in row:
            value = row.get(key)
            if value is not None:
                return value
    return default


def _write_alias_value(df: pd.DataFrame, idx: int, keys: tuple[str, ...], value: Any) -> None:
    written = False
    for key in keys:
        if key in df.columns:
            df.at[idx, key] = value
            written = True
    if not written:
        df.at[idx, keys[0]] = value


def render_app_suite_right_card_panel(
    st: Any,
    *,
    df_suite_edit: pd.DataFrame,
    sel_i: int | None,
    allowed_test_types: list[str],
    expected_suite_cols: list[str],
) -> None:
    if sel_i is None or len(df_suite_edit) == 0:
        render_suite_empty_card_state(st)
        return

    row = df_suite_edit.loc[sel_i].to_dict()
    enabled = bool(_row_get(row, ENABLED_KEYS, True))
    name = str(_row_get(row, NAME_KEYS, f"test_{sel_i}") or f"test_{sel_i}")
    typ = str(_row_get(row, TYPE_KEYS, (allowed_test_types[0] if allowed_test_types else "")) or "")

    dt0 = _safe_float(row.get("dt"), 0.01)
    tend0 = _safe_float(row.get("t_end"), 3.0)
    dt_presets = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1]
    te_presets = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]
    dt = float(dt0)
    t_end = float(tend0)
    ax = _safe_float(row.get("ax"), 0.0)
    ay = _safe_float(row.get("ay"), 0.0)
    speed = _safe_float(_row_get(row, SPEED_KEYS, 0.0), 0.0)
    amplitude = _safe_float(row.get("A"), 0.0)
    freq_hz = _safe_float(row.get("f"), 0.0)
    angle_deg = _safe_float(_row_get(row, ANGLE_KEYS, 0.0), 0.0)

    def _render_primary_section() -> None:
        c_a, c_b = st.columns([1.0, 1.0], gap="medium")
        with c_a:
            st.checkbox("Включён", value=enabled, key=f"suite_enabled__{sel_i}")
            st.text_input("Имя", value=name, key=f"suite_name__{sel_i}")
        with c_b:
            st.selectbox(
                "Тип",
                options=allowed_test_types,
                index=(allowed_test_types.index(typ) if typ in allowed_test_types else 0),
                key=f"suite_type__{sel_i}",
                format_func=format_suite_test_type_label,
            )

    def _render_timing_section() -> None:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            dt_choice = st.selectbox(
                "Шаг dt (с)",
                options=dt_presets + ["другое"],
                index=(dt_presets.index(dt0) if dt0 in dt_presets else len(dt_presets)),
                key=f"suite_dt_choice__{sel_i}",
            )
            if dt_choice == "другое":
                st.number_input("dt (с)", value=float(dt0), step=None, key=f"suite_dt__{sel_i}")
        with c2:
            te_choice = st.selectbox(
                "Длительность t_end (с)",
                options=te_presets + ["другое"],
                index=(te_presets.index(tend0) if tend0 in te_presets else len(te_presets)),
                key=f"suite_te_choice__{sel_i}",
            )
            if te_choice == "другое":
                st.number_input("t_end (с)", value=float(tend0), step=None, key=f"suite_te__{sel_i}")

    def _render_motion_section() -> None:
        c3, c4, c5 = st.columns(3, gap="small")
        with c3:
            st.slider("ax (м/с²)", min_value=-20.0, max_value=20.0, value=float(max(-20.0, min(20.0, ax))), step=0.1, key=f"suite_ax__{sel_i}")
        with c4:
            st.slider("ay (м/с²)", min_value=-20.0, max_value=20.0, value=float(max(-20.0, min(20.0, ay))), step=0.1, key=f"suite_ay__{sel_i}")
        with c5:
            st.slider("Скорость (м/с)", min_value=0.0, max_value=40.0, value=float(max(0.0, min(40.0, speed))), step=0.5, key=f"suite_speed__{sel_i}")

        c6, c7, c8 = st.columns(3, gap="small")
        with c6:
            st.slider("A (м)", min_value=0.0, max_value=0.3, value=float(max(0.0, min(0.3, amplitude))), step=0.001, key=f"suite_A__{sel_i}")
        with c7:
            st.slider("f (Гц)", min_value=0.0, max_value=25.0, value=float(max(0.0, min(25.0, freq_hz))), step=0.1, key=f"suite_f__{sel_i}")
        with c8:
            st.slider("Угол (град)", min_value=-45.0, max_value=45.0, value=float(max(-45.0, min(45.0, angle_deg))), step=0.5, key=f"suite_angle__{sel_i}")

    def _render_targets_section() -> None:
        with st.expander("Порог, уставки и расширенные параметры", expanded=True):
            for key in expected_suite_cols:
                if not key.startswith("target_"):
                    continue
                value0 = row.get(key, np.nan)
                if isinstance(value0, float) and pd.isna(value0):
                    value0 = 0.0
                row[key] = st.number_input(key, value=float(value0) if value0 is not None else 0.0, step=None, key=f"suite_tgt__{key}__{sel_i}")

            for key_group in [
                ("t_step",),
                ("settle_band_min_deg",),
                ("settle_band_ratio",),
                ("dur",),
                ("t0",),
                ("idx",),
                SMOOTH_SHARE_KEYS,
            ]:
                value0 = _row_get(row, key_group, np.nan)
                if isinstance(value0, float) and pd.isna(value0):
                    value0 = 0.0
                if value0 is np.nan:
                    continue
                row[key_group[0]] = st.number_input(
                    key_group[0],
                    value=float(value0) if value0 is not None else 0.0,
                    step=None,
                    key=f"suite_extra__{key_group[0]}__{sel_i}",
                )

    render_app_suite_right_card_shell(
        st,
        name=name,
        render_primary_section=_render_primary_section,
        render_timing_section=_render_timing_section,
        render_motion_section=_render_motion_section,
        render_targets_section=_render_targets_section,
    )

    enabled = bool(st.session_state.get(f"suite_enabled__{sel_i}", enabled))
    name = str(st.session_state.get(f"suite_name__{sel_i}", name) or name)
    typ = str(st.session_state.get(f"suite_type__{sel_i}", typ) or typ)

    dt_choice_state = st.session_state.get(f"suite_dt_choice__{sel_i}", dt0 if dt0 in dt_presets else "другое")
    dt = float(st.session_state.get(f"suite_dt__{sel_i}", dt0)) if dt_choice_state == "другое" else float(dt_choice_state)

    te_choice_state = st.session_state.get(f"suite_te_choice__{sel_i}", tend0 if tend0 in te_presets else "другое")
    t_end = float(st.session_state.get(f"suite_te__{sel_i}", tend0)) if te_choice_state == "другое" else float(te_choice_state)

    ax = float(st.session_state.get(f"suite_ax__{sel_i}", ax))
    ay = float(st.session_state.get(f"suite_ay__{sel_i}", ay))
    speed = float(st.session_state.get(f"suite_speed__{sel_i}", speed))
    amplitude = float(st.session_state.get(f"suite_A__{sel_i}", amplitude))
    freq_hz = float(st.session_state.get(f"suite_f__{sel_i}", freq_hz))
    angle_deg = float(st.session_state.get(f"suite_angle__{sel_i}", angle_deg))

    if st.button("✅ Применить", key=f"suite_apply__{sel_i}"):
        df2 = st.session_state["df_suite_edit"].copy()
        _write_alias_value(df2, sel_i, ENABLED_KEYS, bool(enabled))
        _write_alias_value(df2, sel_i, NAME_KEYS, str(name))
        _write_alias_value(df2, sel_i, TYPE_KEYS, str(typ))
        df2.loc[sel_i, "dt"] = float(dt)
        df2.loc[sel_i, "t_end"] = float(t_end)

        for key_group, value in {
            ("ax",): ax,
            ("ay",): ay,
            SPEED_KEYS: speed,
            ("A",): amplitude,
            ("f",): freq_hz,
            ANGLE_KEYS: angle_deg,
        }.items():
            _write_alias_value(df2, sel_i, key_group, float(value))

        for key in expected_suite_cols:
            if key.startswith("target_") and (key in df2.columns):
                try:
                    df2.loc[sel_i, key] = float(row.get(key, 0.0))
                except Exception:
                    pass

        for key_group in [
            ("t_step",),
            ("settle_band_min_deg",),
            ("settle_band_ratio",),
            ("dur",),
            ("t0",),
            ("idx",),
            SMOOTH_SHARE_KEYS,
        ]:
            key_name = key_group[0]
            try:
                value = float(row.get(key_name, 0.0))
            except Exception:
                continue
            _write_alias_value(df2, sel_i, key_group, value)

        st.session_state["df_suite_edit"] = df2
        st.success("Сохранено.")
        st.rerun()


def render_heavy_suite_right_card_panel(
    st: Any,
    *,
    df_suite_edit: pd.DataFrame,
    row_ids: list[str],
    allowed_test_types: list[str],
    suite_editor_widget_key_fn: WidgetKeyFn,
    seed_suite_editor_state_fn: SeedStateFn,
    infer_suite_stage_fn: InferStageFn,
    save_upload_fn: SaveUploadFn,
    queue_suite_selected_id_fn: QueueSelectedIdFn,
    ensure_stage_visible_in_filter_fn: EnsureStageVisibleFn,
    set_flash_fn: SetFlashFn,
    ensure_suite_columns_fn: EnsureSuiteColumnsFn,
) -> None:
    if not row_ids:
        render_suite_empty_card_state(st)
        return

    selected_id = str(st.session_state.get("ui_suite_selected_id") or "").strip()
    idx = None
    try:
        matches = df_suite_edit.index[df_suite_edit["id"].astype(str) == selected_id].tolist()
        if matches:
            idx = int(matches[0])
    except Exception:
        idx = None

    if idx is None:
        render_suite_missing_card_state(st)
        st.stop()
        return

    rec = df_suite_edit.loc[idx].to_dict()
    sid = str(rec.get("id") or selected_id or idx)
    title = str(_row_get(rec, NAME_KEYS, "Тест") or "Тест")

    seed_suite_editor_state_fn(sid, rec)

    enabled_key = suite_editor_widget_key_fn(sid, "enabled")
    name_key = suite_editor_widget_key_fn(sid, "name")
    stage_key = suite_editor_widget_key_fn(sid, "stage")
    type_key = suite_editor_widget_key_fn(sid, "type")
    dt_key = suite_editor_widget_key_fn(sid, "dt")
    t_end_key = suite_editor_widget_key_fn(sid, "t_end")
    road_csv_key = suite_editor_widget_key_fn(sid, "road_csv")
    axay_csv_key = suite_editor_widget_key_fn(sid, "axay_csv")
    road_len_key = suite_editor_widget_key_fn(sid, "road_len_m")
    vx0_key = suite_editor_widget_key_fn(sid, "vx0_mps")
    auto_t_end_key = suite_editor_widget_key_fn(sid, "auto_t_end_from_len")
    surface_type_key = suite_editor_widget_key_fn(sid, "road_surface_type")
    surface_sine_a_key = suite_editor_widget_key_fn(sid, "road_surface_sine_a")
    surface_sine_wl_key = suite_editor_widget_key_fn(sid, "road_surface_sine_wavelength")
    surface_hw_h_key = suite_editor_widget_key_fn(sid, "road_surface_hw_h")
    surface_hw_w_key = suite_editor_widget_key_fn(sid, "road_surface_hw_w")
    surface_cos_h_key = suite_editor_widget_key_fn(sid, "road_surface_cos_h")
    surface_cos_w_key = suite_editor_widget_key_fn(sid, "road_surface_cos_w")
    surface_cos_k_key = suite_editor_widget_key_fn(sid, "road_surface_cos_k")
    ax_key = suite_editor_widget_key_fn(sid, "ax")
    ay_key = suite_editor_widget_key_fn(sid, "ay")
    params_override_key = suite_editor_widget_key_fn(sid, "params_override")

    def _apply_uploaded_paths(uploaded_road_csv: str | None, uploaded_axay_csv: str | None) -> None:
        if uploaded_road_csv:
            st.session_state[road_csv_key] = str(uploaded_road_csv)
        if uploaded_axay_csv:
            st.session_state[axay_csv_key] = str(uploaded_axay_csv)

    enabled = bool(st.session_state.get(enabled_key, _row_get(rec, ENABLED_KEYS, True)))
    name = str(st.session_state.get(name_key, _row_get(rec, NAME_KEYS, title)) or title)
    try:
        stage_default = max(0, int(st.session_state.get(stage_key, infer_suite_stage_fn(rec)) or 0))
    except Exception:
        stage_default = 0
        st.session_state[stage_key] = 0
    stage = int(stage_default)

    type_default = str(st.session_state.get(type_key, _row_get(rec, TYPE_KEYS, "worldroad")) or "worldroad")
    if type_default not in allowed_test_types:
        type_default = "worldroad"
        st.session_state[type_key] = type_default
    test_type = type_default

    dt = float(_safe_float(st.session_state.get(dt_key, rec.get("dt", 0.01)), 0.01))
    t_end = float(_safe_float(st.session_state.get(t_end_key, rec.get("t_end", 3.0)), 3.0))
    road_csv = str(st.session_state.get(road_csv_key, rec.get("road_csv", "")) or "")
    axay_csv = str(st.session_state.get(axay_csv_key, rec.get("axay_csv", "")) or "")
    road_len_m = float(_safe_float(st.session_state.get(road_len_key, rec.get("road_len_m", 200.0)), 200.0))
    vx0_mps = float(_safe_float(st.session_state.get(vx0_key, _row_get(rec, SPEED_KEYS, 20.0)), 20.0))
    auto_t_end_from_len = bool(st.session_state.get(auto_t_end_key, rec.get("auto_t_end_from_len", False)))
    road_surface = str(rec.get("road_surface", "flat") or "flat")
    ax = float(_safe_float(st.session_state.get(ax_key, rec.get("ax", 0.0)), 0.0))
    ay = float(_safe_float(st.session_state.get(ay_key, rec.get("ay", 0.0)), 0.0))
    params_override = str(st.session_state.get(params_override_key, rec.get("params_override", "")) or "")

    def _render_primary_section() -> None:
        st.checkbox("Включён", key=enabled_key)
        st.text_input("Имя", key=name_key)
        st.number_input(
            "Стадия",
            value=int(stage_default),
            min_value=0,
            step=1,
            key=stage_key,
            help=(
                "С какой стадии тест начинает участвовать в оптимизации по стадиям. "
                "Логика накопительная: стадия 0 участвует только в S0; стадия 1 впервые "
                "включается в S1 и затем остаётся в S2; стадия 2 участвует только в "
                "финальной стадии. Нумерация начинается с 0: первая стадия = 0. "
                "Явно заданная стадия 1 не должна молча переписываться в 0."
            ),
        )
        st.selectbox(
            "Тип",
            options=allowed_test_types,
            index=max(0, allowed_test_types.index(type_default)),
            key=type_key,
            format_func=format_suite_test_type_label,
        )

    def _render_timing_section() -> None:
        st.number_input("Шаг интегрирования, с", min_value=1e-5, step=0.001, format="%.6g", key=dt_key)
        st.number_input("Длительность теста, с", min_value=0.01, step=0.1, format="%.6g", key=t_end_key)

    def _render_motion_section() -> None:
        st.markdown("##### Дорога и режим движения")

        if test_type == "worldroad":
            c1, c2 = st.columns([1, 1], gap="small")
            with c1:
                st.number_input("Начальная скорость, м/с", min_value=0.0, step=0.5, key=vx0_key)
            with c2:
                st.number_input("Длина участка, м", min_value=1.0, step=10.0, key=road_len_key)

            st.checkbox(
                "Авто: длительность = длина / скорость",
                key=auto_t_end_key,
                help="Если включено, длительность теста будет вычисляться автоматически по длине участка и начальной скорости с защитой от деления на ноль.",
            )

            current_speed = float(_safe_float(st.session_state.get(vx0_key, vx0_mps), vx0_mps))
            current_road_len = float(_safe_float(st.session_state.get(road_len_key, road_len_m), road_len_m))
            auto_enabled = bool(st.session_state.get(auto_t_end_key, auto_t_end_from_len))
            current_t_end = float(_safe_float(st.session_state.get(t_end_key, t_end), t_end))
            eps_v = 1e-6
            if auto_enabled:
                auto_t_end = float(current_road_len) / max(float(current_speed), eps_v)
                st.info(
                    f"Длительность теста будет вычислена автоматически: **{auto_t_end:.6g} с** "
                    f"(вместо введённого значения {float(current_t_end):.6g} с)."
                )
            else:
                length_effective = float(current_speed) * float(current_t_end)
                st.caption(
                    f"Расчётная длина проезда = скорость × длительность = {length_effective:.6g} м. "
                    f"Поле длины участка используется только в авто-режиме."
                )
                try:
                    if float(current_road_len) > 1e-9:
                        rel = abs(length_effective - float(current_road_len)) / max(float(current_road_len), 1e-9)
                        if rel > 0.05:
                            st.warning(
                                f"Длина участка {float(current_road_len):.6g} м сейчас **не влияет**, потому что авто-режим выключен. "
                                f"По скорости и длительности получается {length_effective:.6g} м."
                            )
                except Exception:
                    pass

            st.caption("Профиль дороги для сценария с дорожным профилем")
            surface_map = {
                "flat": "Ровная дорога",
                "sine_x": "Синус вдоль",
                "sine_y": "Синус поперёк",
                "bump": "Бугор",
                "ridge_x": "Порог",
                "ridge_cosine_bump": "Косинусный бугор",
            }
            surface_type_default = str(st.session_state.get(surface_type_key, "flat") or "flat")
            if surface_type_default not in surface_map:
                surface_type_default = "flat"
                st.session_state[surface_type_key] = surface_type_default
            surface_type = st.selectbox(
                "Тип поверхности",
                options=list(surface_map.keys()),
                index=list(surface_map.keys()).index(surface_type_default),
                format_func=lambda key: surface_map.get(str(key), str(key)),
                key=surface_type_key,
            )

            if surface_type in {"sine_x", "sine_y"}:
                amplitude = st.number_input("Амплитуда A (полуразмах), м", min_value=0.0, step=0.005, format="%.6g", key=surface_sine_a_key)
                st.caption(
                    f"Амплитуда A задаёт полуразмах синусоиды: профиль идёт от {-float(amplitude):.6g} до +{float(amplitude):.6g} м, "
                    f"а полный размах между минимумом и максимумом равен 2A = {2.0 * float(amplitude):.6g} м."
                )
                wavelength = st.number_input("Длина волны, м", min_value=0.01, step=0.1, format="%.6g", key=surface_sine_wl_key)
                spec_obj = {"type": surface_type, "A": float(amplitude), "wavelength": float(wavelength)}
            elif surface_type in {"bump", "ridge_x"}:
                height = st.number_input("Высота, м", min_value=0.0, step=0.005, format="%.6g", key=surface_hw_h_key)
                width = st.number_input("Ширина, м", min_value=0.01, step=0.05, format="%.6g", key=surface_hw_w_key)
                spec_obj = {"type": surface_type, "h": float(height), "w": float(width)}
            elif surface_type == "ridge_cosine_bump":
                height = st.number_input("Высота, м", min_value=0.0, step=0.005, format="%.6g", key=surface_cos_h_key)
                width = st.number_input("Ширина, м", min_value=0.01, step=0.05, format="%.6g", key=surface_cos_w_key)
                shape = st.number_input("Коэффициент формы", min_value=0.1, step=0.1, format="%.6g", key=surface_cos_k_key)
                spec_obj = {"type": surface_type, "h": float(height), "w": float(width), "k": float(shape)}
            else:
                spec_obj = {"type": "flat"}

            nonlocal_road_surface = "flat" if spec_obj.get("type") == "flat" else json.dumps(spec_obj, ensure_ascii=False)
            st.session_state[suite_editor_widget_key_fn(sid, "derived_road_surface")] = nonlocal_road_surface
        else:
            st.text_input("Путь к CSV дороги", key=road_csv_key)
            st.text_input("Путь к CSV манёвра (ax/ay)", key=axay_csv_key)
            st.session_state[suite_editor_widget_key_fn(sid, "derived_road_surface")] = str(rec.get("road_surface", "flat") or "flat")

        st.markdown("##### Манёвр (если применимо)")
        st.number_input("Продольное ускорение ax, м/с²", step=0.1, format="%.6g", key=ax_key)
        st.number_input("Поперечное ускорение ay, м/с²", step=0.1, format="%.6g", key=ay_key)

    def _render_targets_section() -> None:
        st.caption(
            "Оптимизация учитывает только включённые ниже ограничения и целевые значения. "
            "Если здесь ничего не включено, этот сценарий почти не будет влиять на итоговую оценку."
        )

        try:
            from pneumo_solver_ui.opt_worker_v3_margins_energy import PENALTY_TARGET_SPECS
        except Exception:
            PENALTY_TARGET_SPECS = []

        with st.expander("Что проверять в этом сценарии", expanded=True):
            for spec in (PENALTY_TARGET_SPECS or []):
                key = str(spec.get("key", "") or "").strip()
                if not key:
                    continue
                label = str(spec.get("label", key))
                unit = str(spec.get("unit", "")).strip()
                help_text = str(spec.get("help", "") or "")
                enabled_key_local = suite_editor_widget_key_fn(sid, f"pen_tgt_en_{key}")
                value_key_local = suite_editor_widget_key_fn(sid, f"pen_tgt_val_{key}")
                enabled_local = st.checkbox(
                    f"{label}{(' [' + unit + ']') if unit else ''}",
                    key=enabled_key_local,
                    help=help_text or None,
                )
                if enabled_local:
                    st.number_input(
                        "Порог или целевое значение",
                        step=0.1,
                        format="%.6g",
                        key=value_key_local,
                        help=help_text or None,
                    )

        with st.expander("Переопределения параметров (сценарий)", expanded=True):
            st.text_area(
                "Переопределения параметров в формате JSON (необязательно)",
                height=120,
                key=params_override_key,
                help="Здесь можно задать JSON со значениями параметров, которые будут применены только в этом сценарии.",
            )

    render_heavy_suite_right_card_shell(
        st,
        title=title,
        sid=sid,
        save_upload_fn=save_upload_fn,
        apply_uploaded_paths_fn=_apply_uploaded_paths,
        render_primary_section=_render_primary_section,
        render_timing_section=_render_timing_section,
        render_motion_section=_render_motion_section,
        render_targets_section=_render_targets_section,
    )

    enabled = bool(st.session_state.get(enabled_key, enabled))
    name = str(st.session_state.get(name_key, name) or name)
    stage = int(st.session_state.get(stage_key, stage) or 0)
    test_type = str(st.session_state.get(type_key, test_type) or test_type)
    dt = float(_safe_float(st.session_state.get(dt_key, dt), dt))
    t_end = float(_safe_float(st.session_state.get(t_end_key, t_end), t_end))
    road_csv = str(st.session_state.get(road_csv_key, road_csv) or "")
    axay_csv = str(st.session_state.get(axay_csv_key, axay_csv) or "")
    road_len_m = float(_safe_float(st.session_state.get(road_len_key, road_len_m), road_len_m))
    vx0_mps = float(_safe_float(st.session_state.get(vx0_key, vx0_mps), vx0_mps))
    auto_t_end_from_len = bool(st.session_state.get(auto_t_end_key, auto_t_end_from_len))
    ax = float(_safe_float(st.session_state.get(ax_key, ax), ax))
    ay = float(_safe_float(st.session_state.get(ay_key, ay), ay))
    params_override = str(st.session_state.get(params_override_key, params_override) or "")

    if test_type == "worldroad":
        road_surface = str(st.session_state.get(suite_editor_widget_key_fn(sid, "derived_road_surface"), "flat") or "flat")
    else:
        road_surface = str(rec.get("road_surface", "flat") or "flat")

    t_end_effective = float(road_len_m) / max(float(vx0_mps), 1e-6) if auto_t_end_from_len else float(t_end)

    try:
        from pneumo_solver_ui.opt_worker_v3_margins_energy import PENALTY_TARGET_SPECS
    except Exception:
        PENALTY_TARGET_SPECS = []

    penalty_targets_cols: dict[str, Any] = {}
    for spec in (PENALTY_TARGET_SPECS or []):
        key = str(spec.get("key", "") or "").strip()
        if not key:
            continue
        col = f"target_{key}"
        enabled_key_local = suite_editor_widget_key_fn(sid, f"pen_tgt_en_{key}")
        value_key_local = suite_editor_widget_key_fn(sid, f"pen_tgt_val_{key}")
        if bool(st.session_state.get(enabled_key_local, False)):
            penalty_targets_cols[col] = float(_safe_float(st.session_state.get(value_key_local, 0.0), 0.0))
        else:
            penalty_targets_cols[col] = None

    deprecated_target_cols = [
        "target_clearance",
        "target_pmax_atm",
        "target_pmin_atm",
        "target_povershoot_frac",
    ]

    if st.button("Применить изменения", key=f"ui_suite_apply_btn_{sid}", width="stretch"):
        _write_alias_value(df_suite_edit, idx, ENABLED_KEYS, bool(enabled))
        df_suite_edit.at[idx, "стадия"] = int(stage)
        _write_alias_value(df_suite_edit, idx, NAME_KEYS, str(name))
        _write_alias_value(df_suite_edit, idx, TYPE_KEYS, str(test_type))
        df_suite_edit.at[idx, "dt"] = float(dt)
        df_suite_edit.at[idx, "t_end"] = float(t_end_effective)
        df_suite_edit.at[idx, "auto_t_end_from_len"] = bool(auto_t_end_from_len)
        df_suite_edit.at[idx, "road_csv"] = str(road_csv)
        df_suite_edit.at[idx, "axay_csv"] = str(axay_csv)
        df_suite_edit.at[idx, "road_surface"] = str(road_surface)
        df_suite_edit.at[idx, "road_len_m"] = float(road_len_m)
        _write_alias_value(df_suite_edit, idx, SPEED_KEYS, float(vx0_mps))
        df_suite_edit.at[idx, "ax"] = float(ax)
        df_suite_edit.at[idx, "ay"] = float(ay)

        for col, value in penalty_targets_cols.items():
            df_suite_edit.at[idx, col] = value

        for col in deprecated_target_cols:
            if col in df_suite_edit.columns:
                df_suite_edit.at[idx, col] = None

        df_suite_edit.at[idx, "params_override"] = str(params_override)
        df_suite_edit = ensure_suite_columns_fn(df_suite_edit)
        st.session_state["df_suite_edit"] = df_suite_edit
        queue_suite_selected_id_fn(sid)
        ensure_stage_visible_in_filter_fn(stage)
        st.session_state["_ui_suite_autosave_pending"] = True
        set_flash_fn("success", "Тест обновлён.")
        st.rerun()
