from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pneumo_solver_ui.ui_mech_backend_helpers import (
    render_mechanical_animation_backend_selector,
)
from pneumo_solver_ui.ring_visuals import (
    build_nominal_ring_progress_from_spec,
    build_ring_visual_payload_from_spec,
    embed_path_payload_on_ring,
    load_ring_spec_from_npz,
    load_ring_spec_from_test_cfg,
)

MECH_2D_COMPONENT_TITLE = "Механика (2D схема: крен/тангаж)"
MECH_2D_PICK_EVENT_KEY = "mech2d_pick_event"
MECH_2D_PLAYHEAD_STORAGE_KEY = "pneumo_play_state"
MECH_2D_COMPONENT_HEIGHT = 620
MECH_STATIC_SCHEME_CAPTION = "Механическая схема (статично)"
MECH_COMPONENT_MISSING_WARNING = "Компонент mech_anim не найден/не загружается (components/mech_anim). Покажу fallback (matplotlib)."
MECH_COMPONENT_DISABLED_INFO = "Компонентный режим отключён — показываю встроенную 2D визуализацию (matplotlib)."
MECH_FALLBACK_MISSING_WARNING = "Модуль mech_anim_fallback.py недоступен — показываю статическую схему."
MECH_3D_INTRO_CAPTION = (
    "3D-wireframe «машинка»: рама (параллелепипед), 4 колеса (цилиндры) и профили дороги под каждым колесом. "
    "Крутите сцену мышью, колёсики реально вращаются по пройденному пути."
)
MECH_3D_PATH_MODE_LABEL = "Траектория (для 3D)"
MECH_3D_STATIC_MODE = "Статика (без движения)"
MECH_3D_MODEL_PATH_MODE = "По vx/yaw из модели"
MECH_3D_COMPONENT_TITLE = "Механика 3D (машинка wireframe)"
MECH_3D_COMPONENT_KEY = "mech3d_pick_event"
MECH_3D_COMPONENT_HEIGHT = 680
MECH_3D_COMPONENT_MISSING_WARNING = "Компонент mech_car3d не найден/не загружается (components/mech_car3d). Покажу fallback (matplotlib)."
MECH_3D_COMPONENT_DISABLED_INFO = "Компонентный режим отключён — показываю встроенную 3D визуализацию (matplotlib)."
MECH_3D_FALLBACK_MISSING_ERROR = "Модуль mech_anim_fallback.py недоступен — 3D fallback не может быть показан."


def render_mechanical_animation_intro(st: Any, *, df_main) -> bool:
    st.caption(
        "Упрощённая анимация механики: фронтальный вид (крен) и боковой вид (тангаж). "
        "Показывает движение рамы/колёс и ход штока по данным df_main."
    )
    st.radio(
        "Клик по механике",
        options=["replace", "add"],
        format_func=lambda value: "Заменять выбор" if value == "replace" else "Добавлять к выбору",
        horizontal=True,
        index=0,
        key="mech_click_mode",
    )
    if df_main is None or "время_с" not in df_main.columns:
        st.warning("Нет df_main для анимации механики.")
        return False
    return True


def prepare_mechanical_animation_prelude(
    st: Any,
    *,
    df_main,
    intro_fn: Any = render_mechanical_animation_intro,
) -> dict[str, Any] | None:
    if not bool(intro_fn(st, df_main=df_main)):
        return None

    colM1, colM2, colM3 = st.columns(3)
    with colM1:
        px_per_m = st.slider("Масштаб (px/м)", 500, 4000, 2000, step=100, key="mech_px_per_m")
    with colM2:
        body_offset_px = st.slider("Отступ рамы над колёсами (px)", 40, 220, 110, step=5, key="mech_body_offset_px")
    with colM3:
        fps = st.slider("Скорость (FPS)", 10, 60, 30, step=5, key="mech_fps")

    frame_dt_s = 1.0 / max(1.0, float(fps))
    return {
        "px_per_m": float(px_per_m),
        "body_offset_px": float(body_offset_px),
        "fps": float(fps),
        "frame_dt_s": float(frame_dt_s),
        "time_s": df_main["время_с"].astype(float).tolist(),
        "corners": ["ЛП", "ПП", "ЛЗ", "ПЗ"],
    }


def render_mechanical_scheme_asset_expander(
    st: Any,
    *,
    base_dir: Path,
    safe_image_fn: Any,
) -> None:
    with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):
        png_path = base_dir / "assets" / "mech_scheme.png"
        if png_path.exists():
            safe_image_fn(str(png_path))
        svg_path = base_dir / "assets" / "mech_scheme.svg"
        if svg_path.exists():
            st.download_button(
                "Скачать mech_scheme.svg",
                data=svg_path.read_bytes(),
                file_name="mech_scheme.svg",
                mime="image/svg+xml",
            )


def _to_list(value: Any) -> list[Any]:
    try:
        return value.tolist()
    except Exception:
        return list(value)


def _float_array_from_df_column(
    df_main,
    *,
    column: str,
    time_len: int,
) -> np.ndarray:
    if df_main is not None and column in df_main.columns:
        return df_main[column].astype(float).to_numpy()
    return np.zeros(int(time_len), dtype=float)


def prepare_mechanical_animation_body_profiles(
    df_main,
    *,
    time_len: int,
    corners: list[str],
    wheelbase: float,
    track: float,
    z_column: str = "перемещение_рамы_z_м",
    phi_column: str = "крен_phi_рад",
    theta_column: str = "тангаж_theta_рад",
) -> dict[str, Any]:
    z = _float_array_from_df_column(df_main, column=z_column, time_len=time_len)
    phi = _float_array_from_df_column(df_main, column=phi_column, time_len=time_len)
    theta = _float_array_from_df_column(df_main, column=theta_column, time_len=time_len)

    x_pos = np.array([wheelbase / 2, wheelbase / 2, -wheelbase / 2, -wheelbase / 2], dtype=float)
    y_pos = np.array([track / 2, -track / 2, track / 2, -track / 2], dtype=float)
    z_body = (
        z[:, None]
        + np.sin(phi)[:, None] * y_pos[None, :] * np.cos(theta)[:, None]
        - np.sin(theta)[:, None] * x_pos[None, :]
    )
    body = {corners[i]: z_body[:, i].tolist() for i in range(len(corners))}
    return {
        "z": z,
        "phi": phi,
        "theta": theta,
        "body": body,
        "body3d": {"z": z.astype(float).tolist()},
    }


def prepare_mechanical_animation_corner_series(
    df_main,
    *,
    corners: list[str],
    time_len: int,
    wheel_column_resolver_fn: Any,
    road_column_resolver_fn: Any,
    stroke_column_resolver_fn: Any,
) -> dict[str, dict[str, list[float]]]:
    wheel: dict[str, list[float]] = {}
    road: dict[str, list[float]] = {}
    stroke: dict[str, list[float]] = {}
    for corner in corners:
        wheel_col = str(wheel_column_resolver_fn(corner))
        road_col = str(road_column_resolver_fn(corner))
        stroke_col = str(stroke_column_resolver_fn(corner))
        wheel[corner] = _float_array_from_df_column(df_main, column=wheel_col, time_len=time_len).tolist()
        road[corner] = _float_array_from_df_column(df_main, column=road_col, time_len=time_len).tolist()
        stroke[corner] = _float_array_from_df_column(df_main, column=stroke_col, time_len=time_len).tolist()
    return {
        "wheel": wheel,
        "road": road,
        "stroke": stroke,
    }


def should_restore_mechanical_road_profile(
    df_main,
    *,
    corners: list[str],
    test_cfg: dict[str, Any] | None,
    road_csv_key: str = "road_csv",
    road_func_key: str = "road_func",
) -> bool:
    try:
        cfg = test_cfg or {}
        has_road_input = bool(str(cfg.get(road_csv_key) or "").strip()) or callable(cfg.get(road_func_key))
        if any((f"дорога_{corner}_м" not in df_main.columns) for corner in corners):
            return True
        if not has_road_input:
            return False
        max_road = 0.0
        for corner in corners:
            col = f"дорога_{corner}_м"
            if col not in df_main.columns:
                continue
            try:
                arr = pd.to_numeric(df_main[col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
                max_road = max(max_road, float(np.max(np.abs(arr))))
            except Exception:
                pass
        return bool(max_road < 1e-9)
    except Exception:
        return False


def resolve_mechanical_road_profile(
    *,
    df_main,
    road: dict[str, list[float]],
    model_mod: Any,
    test_cfg: dict[str, Any] | None,
    time_s,
    wheelbase: float,
    track: float,
    corners: list[str],
    compute_road_profile_fn: Any,
    normalize_restored_road_fn: Any | None = None,
) -> dict[str, Any]:
    restored = False
    resolved_road = road
    if not should_restore_mechanical_road_profile(
        df_main,
        corners=corners,
        test_cfg=test_cfg,
    ):
        return {
            "road": resolved_road,
            "restored": False,
        }

    road_from_suite = compute_road_profile_fn(
        model_mod,
        test_cfg or {},
        time_s,
        wheelbase,
        track,
        corners,
    )
    if road_from_suite is not None:
        resolved_road = road_from_suite
        if normalize_restored_road_fn is not None:
            try:
                normalized = normalize_restored_road_fn(resolved_road)
                if normalized is not None:
                    resolved_road = normalized
            except Exception:
                pass
        restored = True
    return {
        "road": resolved_road,
        "restored": restored,
    }


def _resolve_mechanical_animation_override_float(
    base_override: dict[str, Any] | None,
    *,
    key: str,
    default: float,
    get_float_param_fn: Any | None = None,
) -> float:
    try:
        if get_float_param_fn is not None:
            return float(get_float_param_fn(base_override or {}, key, default=default))
    except Exception:
        pass
    try:
        return float((base_override or {}).get(key, default))
    except Exception:
        return float(default)


def prepare_mechanical_animation_runtime_inputs(
    *,
    df_main,
    base_override: dict[str, Any] | None,
    model_mod: Any,
    test_cfg: dict[str, Any] | None,
    time_s,
    corners: list[str],
    compute_road_profile_fn: Any,
    wheel_column_resolver_fn: Any,
    road_column_resolver_fn: Any,
    stroke_column_resolver_fn: Any,
    z_column: str = "перемещение_рамы_z_м",
    phi_column: str = "крен_phi_рад",
    theta_column: str = "тангаж_theta_рад",
    normalize_restored_road_fn: Any | None = None,
    get_float_param_fn: Any | None = None,
    wheelbase_key: str = "база",
    track_key: str = "колея",
    stroke_key: str = "ход_штока",
    wheelbase_default: float = 2.3,
    track_default: float = 1.2,
    stroke_default: float = 0.25,
) -> dict[str, Any]:
    wheelbase = _resolve_mechanical_animation_override_float(
        base_override,
        key=wheelbase_key,
        default=wheelbase_default,
        get_float_param_fn=get_float_param_fn,
    )
    track = _resolve_mechanical_animation_override_float(
        base_override,
        key=track_key,
        default=track_default,
        get_float_param_fn=get_float_param_fn,
    )
    L_stroke_m = _resolve_mechanical_animation_override_float(
        base_override,
        key=stroke_key,
        default=stroke_default,
    )

    mech_body = prepare_mechanical_animation_body_profiles(
        df_main,
        time_len=len(time_s),
        corners=corners,
        wheelbase=wheelbase,
        track=track,
        z_column=z_column,
        phi_column=phi_column,
        theta_column=theta_column,
    )
    mech_series = prepare_mechanical_animation_corner_series(
        df_main,
        corners=corners,
        time_len=len(time_s),
        wheel_column_resolver_fn=wheel_column_resolver_fn,
        road_column_resolver_fn=road_column_resolver_fn,
        stroke_column_resolver_fn=stroke_column_resolver_fn,
    )
    mech_road = resolve_mechanical_road_profile(
        df_main=df_main,
        road=mech_series["road"],
        model_mod=model_mod,
        test_cfg=test_cfg,
        time_s=time_s,
        wheelbase=wheelbase,
        track=track,
        corners=corners,
        compute_road_profile_fn=compute_road_profile_fn,
        normalize_restored_road_fn=normalize_restored_road_fn,
    )
    return {
        "wheelbase": wheelbase,
        "track": track,
        "L_stroke_m": L_stroke_m,
        "z": mech_body["z"],
        "phi": mech_body["phi"],
        "theta": mech_body["theta"],
        "body": mech_body["body"],
        "body3d": mech_body["body3d"],
        "wheel": mech_series["wheel"],
        "road": mech_road["road"],
        "stroke": mech_series["stroke"],
        "road_restored": bool(mech_road["restored"]),
    }


MECH_ROAD_RESTORED_CAPTION = (
    "ℹ️ Профиль дороги восстановлен из входного профиля теста (road_func), т.к. в логе нет колонок "
    "дороги или они заполнены нулями."
)


def render_mechanical_animation_results_panel(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    dataset_id: Any,
    df_main,
    base_override: dict[str, Any],
    model_mod: Any,
    test_cfg: dict[str, Any] | None,
    compute_road_profile_fn: Any,
    log_event_fn: Any,
    wheel_column_resolver_fn: Any,
    road_column_resolver_fn: Any,
    stroke_column_resolver_fn: Any,
    z_column: str = "перемещение_рамы_z_м",
    phi_column: str = "крен_phi_рад",
    theta_column: str = "тангаж_theta_рад",
    normalize_restored_road_fn: Any | None = None,
    get_float_param_fn: Any | None = None,
    wheelbase_default: float = 2.3,
    track_default: float = 1.2,
    playhead_idx: int | None = None,
    show_2d_controls: bool | None = None,
    road_restored_caption: str = MECH_ROAD_RESTORED_CAPTION,
    road_restored_log_event_name: str = "anim_road_from_suite",
    road_restored_log_kwargs: dict[str, Any] | None = None,
    prelude_fn: Any = prepare_mechanical_animation_prelude,
    runtime_inputs_fn: Any = prepare_mechanical_animation_runtime_inputs,
    section_fn: Any | None = None,
    section_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    mech_prelude = prelude_fn(
        st,
        df_main=df_main,
    )
    if mech_prelude is None:
        return None

    px_per_m = float(mech_prelude["px_per_m"])
    body_offset_px = float(mech_prelude["body_offset_px"])
    frame_dt_s = float(mech_prelude["frame_dt_s"])
    time_s = mech_prelude["time_s"]
    corners = mech_prelude["corners"]

    mech_inputs = runtime_inputs_fn(
        df_main=df_main,
        base_override=base_override,
        model_mod=model_mod,
        test_cfg=test_cfg,
        time_s=time_s,
        corners=corners,
        compute_road_profile_fn=compute_road_profile_fn,
        wheel_column_resolver_fn=wheel_column_resolver_fn,
        road_column_resolver_fn=road_column_resolver_fn,
        stroke_column_resolver_fn=stroke_column_resolver_fn,
        z_column=z_column,
        phi_column=phi_column,
        theta_column=theta_column,
        normalize_restored_road_fn=normalize_restored_road_fn,
        get_float_param_fn=get_float_param_fn,
        wheelbase_default=wheelbase_default,
        track_default=track_default,
    )

    if bool(mech_inputs["road_restored"]):
        st.caption(str(road_restored_caption))
        log_event_fn(
            road_restored_log_event_name,
            **dict(road_restored_log_kwargs or {}),
        )

    section_options = dict(section_kwargs or {})
    section_options.setdefault("intro_fn", lambda *_args, **_kwargs: True)
    active_section_fn = section_fn or render_mechanical_animation_section
    return active_section_fn(
        st,
        session_state=session_state,
        cache_key=cache_key,
        dataset_id=dataset_id,
        df_main=df_main,
        time=time_s,
        body_2d=mech_inputs["body"],
        body_3d=mech_inputs["body3d"],
        wheel=mech_inputs["wheel"],
        road=mech_inputs["road"],
        stroke=mech_inputs["stroke"],
        phi=mech_inputs["phi"],
        theta=mech_inputs["theta"],
        px_per_m=px_per_m,
        body_offset_px=body_offset_px,
        L_stroke_m=float(mech_inputs["L_stroke_m"]),
        frame_dt_s=frame_dt_s,
        wheelbase=float(mech_inputs["wheelbase"]),
        track=float(mech_inputs["track"]),
        playhead_idx=playhead_idx,
        show_2d_controls=show_2d_controls,
        base_override=base_override,
        **section_options,
    )


def build_mechanical_2d_component_payload(
    session_state: dict[str, Any],
    *,
    cache_key: str,
    dataset_id: Any,
    time,
    body,
    wheel,
    road,
    stroke,
    phi,
    theta,
    px_per_m: float,
    body_offset_px: float,
    L_stroke_m: float,
    frame_dt_s: float,
) -> dict[str, Any]:
    return {
        "title": MECH_2D_COMPONENT_TITLE,
        "time": time,
        "body": body,
        "wheel": wheel,
        "road": road,
        "stroke": stroke,
        "phi": _to_list(phi),
        "theta": _to_list(theta),
        "selected": session_state.get("mech_selected_corners", []),
        "meta": {
            "px_per_m": float(px_per_m),
            "body_offset_px": float(body_offset_px),
            "L_stroke_m": float(L_stroke_m),
            "frame_dt_s": float(frame_dt_s),
        },
        "sync_playhead": True,
        "playhead_storage_key": MECH_2D_PLAYHEAD_STORAGE_KEY,
        "dataset_id": dataset_id,
        "cmd": session_state.get(f"mech3d_cmd_{cache_key}"),
        "height": MECH_2D_COMPONENT_HEIGHT,
        "key": MECH_2D_PICK_EVENT_KEY,
        "default": None,
    }


def build_mechanical_2d_fallback_payload(
    *,
    dataset_id: str,
    time,
    body,
    wheel,
    road,
    stroke,
    wheelbase: float,
    track: float,
    L_stroke_m: float,
    log_cb: Any,
    idx: int | None = None,
    show_controls: bool | None = None,
) -> dict[str, Any]:
    payload = {
        "time": time,
        "body": body,
        "wheel": wheel,
        "road": road,
        "stroke": stroke,
        "wheelbase_m": float(wheelbase),
        "track_m": float(track),
        "L_stroke_m": float(L_stroke_m),
        "dataset_id": str(dataset_id),
        "log_cb": log_cb,
    }
    if idx is not None:
        payload["idx"] = int(idx)
    if show_controls is not None:
        payload["show_controls"] = bool(show_controls)
    return payload


def render_mechanical_static_scheme(
    safe_image_fn: Any,
    *,
    base_dir: Path,
    caption: str = MECH_STATIC_SCHEME_CAPTION,
) -> bool:
    png_path = base_dir / "assets" / "mech_scheme.png"
    if not png_path.exists():
        return False
    safe_image_fn(str(png_path), caption=caption)
    return True


def render_mechanical_2d_fallback_or_static(
    st: Any,
    mech_fallback_module: Any,
    fallback_payload: dict[str, Any],
    *,
    safe_image_fn: Any,
    base_dir: Path,
    on_fallback_missing: Any | None = None,
) -> str:
    if mech_fallback_module is not None:
        mech_fallback_module.render_mech2d_fallback(**fallback_payload)
        return "fallback"
    if on_fallback_missing is not None:
        on_fallback_missing()
    else:
        st.warning(MECH_FALLBACK_MISSING_WARNING)
    render_mechanical_static_scheme(safe_image_fn, base_dir=base_dir)
    return "static"


def render_mechanical_2d_component_or_fallback(
    st: Any,
    *,
    use_component_anim: bool,
    get_component_fn: Any,
    component_payload: dict[str, Any],
    mech_fallback_module: Any,
    fallback_payload: dict[str, Any],
    safe_image_fn: Any,
    base_dir: Path,
    on_component_runtime_error: Any | None = None,
    on_component_missing: Any | None = None,
    on_component_disabled: Any | None = None,
    on_fallback_missing: Any | None = None,
) -> str:
    mech_comp = get_component_fn() if use_component_anim else None
    if mech_comp is not None:
        try:
            mech_comp(**component_payload)
            return "component"
        except Exception as exc:
            if on_component_runtime_error is not None:
                on_component_runtime_error(exc)
            else:
                raise
            return render_mechanical_2d_fallback_or_static(
                st,
                mech_fallback_module,
                fallback_payload,
                safe_image_fn=safe_image_fn,
                base_dir=base_dir,
                on_fallback_missing=on_fallback_missing,
            )

    if use_component_anim:
        if on_component_missing is not None:
            on_component_missing()
        else:
            st.warning(MECH_COMPONENT_MISSING_WARNING)
    else:
        if on_component_disabled is not None:
            on_component_disabled()
        else:
            st.info(MECH_COMPONENT_DISABLED_INFO)

    return render_mechanical_2d_fallback_or_static(
        st,
        mech_fallback_module,
        fallback_payload,
        safe_image_fn=safe_image_fn,
        base_dir=base_dir,
        on_fallback_missing=on_fallback_missing,
    )


def _show_mechanical_component_diag(
    st: Any,
    *,
    label: str,
    error_obj: Any,
) -> None:
    if not error_obj:
        return
    with st.expander(label):
        if hasattr(st, "code"):
            st.code(str(error_obj))
        else:
            st.markdown(str(error_obj))


def build_mechanical_2d_runtime_callbacks(
    st: Any,
    *,
    component_last_error_fn: Any,
    log_cb: Any,
    proc_metrics_fn: Any,
    fallback_error: Any = None,
    component_name: str = "mech_anim",
    fallback_name: str = "mech_anim_fallback",
) -> dict[str, Any]:
    def _on_component_runtime_error(exc: Exception) -> None:
        st.warning("Компонент mech_anim упал во время выполнения. Показываю fallback (matplotlib).")
        log_cb(
            "component_runtime_error",
            component=component_name,
            error=repr(exc),
            traceback=traceback.format_exc(),
            proc=proc_metrics_fn(),
        )

    def _on_component_missing() -> None:
        st.warning(MECH_COMPONENT_MISSING_WARNING)
        component_err = component_last_error_fn(component_name)
        log_cb(
            "component_missing",
            component=component_name,
            detail=str(component_err) if component_err else None,
            proc=proc_metrics_fn(),
        )
        _show_mechanical_component_diag(
            st,
            label="Диагностика mech_anim",
            error_obj=component_err,
        )

    def _on_component_disabled() -> None:
        component_err = component_last_error_fn(component_name)
        if component_err:
            _show_mechanical_component_diag(
                st,
                label="Диагностика mech_anim",
                error_obj=component_err,
            )
        else:
            st.info(MECH_COMPONENT_DISABLED_INFO)

    def _on_fallback_missing() -> None:
        st.warning(MECH_FALLBACK_MISSING_WARNING)
        log_cb(
            "fallback_missing",
            component=fallback_name,
            detail=str(fallback_error) if fallback_error else None,
            proc=proc_metrics_fn(),
        )
        _show_mechanical_component_diag(
            st,
            label="Диагностика mech_anim_fallback",
            error_obj=fallback_error,
        )

    return {
        "on_component_runtime_error": _on_component_runtime_error,
        "on_component_missing": _on_component_missing,
        "on_component_disabled": _on_component_disabled,
        "on_fallback_missing": _on_fallback_missing,
    }


def render_mechanical_2d_animation_panel(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    dataset_id: Any,
    time,
    body,
    wheel,
    road,
    stroke,
    phi,
    theta,
    px_per_m: float,
    body_offset_px: float,
    L_stroke_m: float,
    frame_dt_s: float,
    wheelbase: float,
    track: float,
    use_component_anim: bool,
    get_component_fn: Any,
    mech_fallback_module: Any,
    log_cb: Any,
    safe_image_fn: Any,
    base_dir: Path,
    idx: int | None = None,
    show_controls: bool | None = None,
    component_last_error_fn: Any | None = None,
    proc_metrics_fn: Any | None = None,
    fallback_error: Any = None,
    build_component_payload_fn: Any = build_mechanical_2d_component_payload,
    build_fallback_payload_fn: Any = build_mechanical_2d_fallback_payload,
    build_callbacks_fn: Any = build_mechanical_2d_runtime_callbacks,
    render_component_or_fallback_fn: Any = render_mechanical_2d_component_or_fallback,
) -> dict[str, Any]:
    component_payload = build_component_payload_fn(
        session_state,
        cache_key=cache_key,
        dataset_id=dataset_id,
        time=time,
        body=body,
        wheel=wheel,
        road=road,
        stroke=stroke,
        phi=phi,
        theta=theta,
        px_per_m=px_per_m,
        body_offset_px=body_offset_px,
        L_stroke_m=L_stroke_m,
        frame_dt_s=frame_dt_s,
    )
    fallback_payload = build_fallback_payload_fn(
        dataset_id=str(dataset_id),
        time=time,
        body=body,
        wheel=wheel,
        road=road,
        stroke=stroke,
        wheelbase=wheelbase,
        track=track,
        L_stroke_m=L_stroke_m,
        idx=idx,
        show_controls=show_controls,
        log_cb=log_cb,
    )

    callbacks: dict[str, Any] = {}
    if component_last_error_fn is not None and proc_metrics_fn is not None:
        callbacks = build_callbacks_fn(
            st,
            component_last_error_fn=component_last_error_fn,
            log_cb=log_cb,
            proc_metrics_fn=proc_metrics_fn,
            fallback_error=fallback_error,
        )

    render_status = render_component_or_fallback_fn(
        st,
        use_component_anim=use_component_anim,
        get_component_fn=get_component_fn,
        component_payload=component_payload,
        mech_fallback_module=mech_fallback_module,
        fallback_payload=fallback_payload,
        safe_image_fn=safe_image_fn,
        base_dir=base_dir,
        on_component_runtime_error=callbacks.get("on_component_runtime_error"),
        on_component_missing=callbacks.get("on_component_missing"),
        on_component_disabled=callbacks.get("on_component_disabled"),
        on_fallback_missing=callbacks.get("on_fallback_missing"),
    )
    return {
        "component_payload": component_payload,
        "fallback_payload": fallback_payload,
        "callbacks": callbacks,
        "render_status": render_status,
    }


def render_mechanical_3d_intro(st: Any) -> None:
    st.caption(MECH_3D_INTRO_CAPTION)


def render_mechanical_3d_maneuver_controls(
    st: Any,
    *,
    cache_key: str,
    demo_paths: bool,
    path_mode: str,
    hidden_yaw_smooth: float = 0.15,
    model_path_mode_label: str = "По vx/yaw из модели",
) -> tuple[float, float, float, float, str]:
    if demo_paths:
        slalom_amp = st.number_input(
            "Слалом: амплитуда (м)",
            min_value=0.0,
            value=1.5,
            step=0.1,
            key=f"mech3d_slalom_amp_{cache_key}",
        )
        slalom_period = st.number_input(
            "Слалом: период (с)",
            min_value=0.2,
            value=4.0,
            step=0.2,
            key=f"mech3d_slalom_period_{cache_key}",
        )
        yaw_smooth = st.number_input(
            "Сглаживание yaw (0..1)",
            min_value=0.0,
            max_value=1.0,
            value=0.15,
            step=0.05,
            key=f"mech3d_yaw_smooth_{cache_key}",
        )
        st.markdown("**Поворот/радиус (для манёвра)**")
        turn_radius = st.number_input(
            "Поворот: радиус R (м)",
            min_value=1.0,
            value=35.0,
            step=1.0,
            key=f"mech3d_turn_R_{cache_key}",
        )
        turn_dir = st.selectbox(
            "Поворот: направление",
            options=["влево", "вправо"],
            index=0,
            key=f"mech3d_turn_dir_{cache_key}",
        )
        return (
            float(slalom_amp),
            float(slalom_period),
            float(yaw_smooth),
            float(turn_radius),
            str(turn_dir),
        )

    yaw_smooth = 0.0 if str(path_mode) == model_path_mode_label else float(hidden_yaw_smooth)
    return (1.5, 4.0, yaw_smooth, 35.0, "влево")


def render_mechanical_3d_path_controls(
    st: Any,
    *,
    cache_key: str,
    checkbox_label: str,
    demo_options: list[str],
    demo_info_text: str,
    non_demo_caption: str,
    model_path_available: bool = False,
    model_path_caption: str | None = None,
    model_speed_values: Any | None = None,
    model_path_mode_label: str = MECH_3D_MODEL_PATH_MODE,
) -> tuple[bool, str, float, float, float, float]:
    demo_paths = bool(
        st.checkbox(
            checkbox_label,
            value=False,
            key=f"mech3d_demo_paths_{cache_key}",
        )
    )

    if not demo_paths:
        if model_path_available:
            path_mode = model_path_mode_label
            if model_path_caption:
                st.caption(model_path_caption)
            try:
                v0 = float(np.nanmean(np.asarray(model_speed_values, dtype=float)))
            except Exception:
                v0 = 12.0
        else:
            path_mode = MECH_3D_STATIC_MODE
            st.caption(non_demo_caption)
            v0 = 12.0
        return (False, str(path_mode), float(v0), 1.0, 1.0, 35.0)

    path_mode = st.selectbox(
        MECH_3D_PATH_MODE_LABEL,
        demo_options,
        index=0,
        key=f"mech3d_path_mode_{cache_key}",
    )
    st.info(demo_info_text)
    v0 = st.number_input(
        "v0, м/с",
        min_value=0.0,
        max_value=60.0,
        value=12.0,
        step=0.5,
        key=f"mech3d_v0_{cache_key}",
    )
    lateral_scale = st.number_input(
        "масштаб бокового смещения",
        min_value=0.0,
        max_value=20.0,
        value=1.0,
        step=0.1,
        key=f"mech3d_lat_scale_{cache_key}",
    )
    steer_gain = st.number_input(
        "усиление руления (по φ)",
        min_value=0.0,
        max_value=10.0,
        value=1.0,
        step=0.1,
        key=f"mech3d_steer_gain_{cache_key}",
    )
    steer_max_deg = st.slider(
        "ограничение руления, град",
        min_value=0,
        max_value=60,
        value=35,
        step=1,
        key=f"mech3d_steer_max_deg_{cache_key}",
    )
    return (
        True,
        str(path_mode),
        float(v0),
        float(lateral_scale),
        float(steer_gain),
        float(steer_max_deg),
    )


def render_mechanical_3d_visual_controls(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    base_override: dict[str, Any],
    base_default: float,
    track_default: float,
    camera_follow_default: bool,
    road_mesh_step_default: int,
    get_float_param_fn: Any | None = None,
) -> dict[str, Any]:
    if get_float_param_fn is not None:
        base_m = float(get_float_param_fn(base_override, "база", default=base_default))
        track_m = float(get_float_param_fn(base_override, "колея", default=track_default))
    else:
        base_m = float(base_override.get("база", base_default))
        track_m = float(base_override.get("колея", track_default))

    wheel_r = st.number_input(
        "Радиус колеса (м)",
        min_value=0.05,
        value=0.32,
        step=0.01,
        key=f"mech3d_wheel_r_{cache_key}",
    )
    wheel_w = st.number_input(
        "Ширина колеса (м)",
        min_value=0.02,
        value=0.22,
        step=0.01,
        key=f"mech3d_wheel_w_{cache_key}",
    )
    body_y_off = st.number_input(
        "Поднять раму (м)",
        min_value=-5.0,
        value=0.60,
        step=0.05,
        key=f"mech3d_body_yoff_{cache_key}",
    )
    road_win = st.slider(
        "Окно дороги (точек)",
        min_value=60,
        max_value=600,
        value=220,
        step=10,
        key=f"mech3d_road_win_{cache_key}",
    )
    st.markdown("**Калибровка высот (3D)**")
    invert_y = st.checkbox("Инвертировать вертикаль (Y)", value=False, key=f"mech3d_invert_y_{cache_key}")
    y_sign = -1.0 if invert_y else 1.0
    wheel_center_offset = st.number_input(
        "Сдвиг центра колеса по Y (м)",
        min_value=-5.0,
        value=0.0,
        step=0.05,
        key=f"mech3d_wheel_center_off_{cache_key}",
    )
    road_y_offset = st.number_input(
        "Сдвиг дороги по Y (м)",
        min_value=-5.0,
        value=0.0,
        step=0.05,
        key=f"mech3d_road_y_off_{cache_key}",
    )
    road_subtract_radius = st.checkbox(
        "Дорога в df = уровень центра колеса (рисовать поверхность = road - R)",
        value=False,
        key=f"mech3d_road_subr_{cache_key}",
    )
    camera_follow = st.checkbox(
        "Камера следует за машиной (центр кадра)",
        value=bool(camera_follow_default),
        key=f"mech3d_cam_follow_{cache_key}",
    )
    camera_follow_heading = st.checkbox(
        "Камера поворачивается по yaw (удобно для поворотов/слалома)",
        value=False,
        key=f"mech3d_cam_follow_heading_{cache_key}",
    )
    camera_follow_selected = st.checkbox(
        "Камера следует за выбранным колесом/осью (если выбрано)",
        value=False,
        key=f"mech3d_cam_follow_selected_{cache_key}",
    )
    follow_smooth = st.slider(
        "Сглаживание target (камера/следование)",
        min_value=0.0,
        max_value=1.0,
        value=0.25,
        step=0.05,
        key=f"mech3d_follow_smooth_{cache_key}",
    )
    hover_tooltip = st.checkbox(
        "Hover-подсказки (колесо/ось): wheel/road/gap",
        value=True,
        key=f"mech3d_hover_tooltip_{cache_key}",
    )
    show_minimap = st.checkbox(
        "Мини-карта (вид сверху) поверх сцены",
        value=False,
        key=f"mech3d_show_minimap_{cache_key}",
    )
    minimap_size = st.slider(
        "Размер мини-карты (px)",
        min_value=80,
        max_value=320,
        value=160,
        step=10,
        key=f"mech3d_minimap_size_{cache_key}",
    )

    st.markdown("**Отрисовка дороги/подвески (3D)**")
    road_mode_ui = st.selectbox(
        "Режим дороги (как рисовать профиль под колёсами)",
        options=["track (след по траектории)", "local (под машиной)"],
        index=0,
        key=f"mech3d_road_mode_{cache_key}",
    )
    road_mode = "track" if str(road_mode_ui).startswith("track") else "local"
    spin_per_wheel = st.checkbox(
        "Крутить колёса по пути каждого колеса (в повороте внутр/наруж отличаются)",
        value=True,
        key=f"mech3d_spin_per_wheel_{cache_key}",
    )
    show_suspension = st.checkbox(
        "Показывать стойки/подвеску (линии от рамы к колёсам)",
        value=True,
        key=f"mech3d_show_susp_{cache_key}",
    )
    show_contact = st.checkbox(
        "Показывать контакт колеса с дорогой (gap/penetration)",
        value=True,
        key=f"mech3d_show_contact_{cache_key}",
    )
    show_gap_heat = st.checkbox(
        "Цвет по gap (контакт/зазор) — окрашивать колёса/контакт",
        value=True,
        key=f"mech3d_show_gap_heat_{cache_key}",
    )
    gap_scale_m = st.slider(
        "Шкала gap (м) для цвета",
        min_value=0.005,
        max_value=0.200,
        value=0.050,
        step=0.005,
        key=f"mech3d_gap_scale_{cache_key}",
    )
    show_gap_hud = st.checkbox(
        "Показывать gap/min-gap в HUD",
        value=True,
        key=f"mech3d_show_gap_hud_{cache_key}",
    )
    min_gap_window = st.slider(
        "Окно min-gap (точек назад, 0=выкл)",
        min_value=0,
        max_value=2000,
        value=300,
        step=50,
        key=f"mech3d_min_gap_window_{cache_key}",
    )
    min_gap_step = st.slider(
        "Шаг анализа min-gap (прореживание)",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
        key=f"mech3d_min_gap_step_{cache_key}",
    )
    hover_contact_marker = st.checkbox(
        "Маркер контакта при hover (крупнее, цвет по gap)",
        value=True,
        key=f"mech3d_hover_contact_{cache_key}",
    )

    st.markdown("**Камера/виды (3D)**")
    multi_view = st.checkbox(
        "Мультивид: 4 проекции (ISO/TOP/FRONT/SIDE)",
        value=False,
        key=f"mech3d_multi_view_{cache_key}",
    )
    allow_pan = st.checkbox(
        "Разрешить панорамирование (RMB/Shift+Drag)",
        value=True,
        key=f"mech3d_allow_pan_{cache_key}",
    )
    debug_overlay = st.checkbox(
        "DEBUG overlay (служебный текст на канве)",
        value=False,
        key=f"mech3d_debug_overlay_{cache_key}",
        help="Если 3D кажется пустым/«за пределами канвы»: включи overlay — он покажет dataset/idx/t и подтвердит, что сцена реально рисуется.",
    )
    if st.button(
        "Сбросить вид 3D (Reset view)",
        key=f"mech3d_reset_view_{cache_key}",
        help="Сбрасывает камеру/панорамирование (так же работает dblclick по 3D). Полезно, если сцену «увели» за экран.",
    ):
        session_state[f"mech3d_cmd_{cache_key}"] = {"reset_view": True, "ts": time.time()}

    st.markdown("**Дорога/траектория (3D)**")
    show_road_mesh = st.checkbox(
        "Показывать «сетку/перемычки» дороги (между левым и правым колесом)",
        value=True,
        key=f"mech3d_show_road_mesh_{cache_key}",
    )
    road_mesh_step = st.slider(
        "Шаг сетки дороги (точек)",
        min_value=1,
        max_value=30,
        value=int(road_mesh_step_default),
        step=1,
        key=f"mech3d_road_mesh_step_{cache_key}",
    )
    show_trail = st.checkbox(
        "Показывать траекторию (след кузова и колёс)",
        value=True,
        key=f"mech3d_show_trail_{cache_key}",
    )
    trail_len = st.slider(
        "Длина следа (точек назад)",
        min_value=20,
        max_value=2000,
        value=500,
        step=20,
        key=f"mech3d_trail_len_{cache_key}",
    )
    trail_step = st.slider(
        "Шаг следа (прореживание)",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
        key=f"mech3d_trail_step_{cache_key}",
    )

    return {
        "base_m": float(base_m),
        "track_m": float(track_m),
        "wheel_r": float(wheel_r),
        "wheel_w": float(wheel_w),
        "body_y_off": float(body_y_off),
        "road_win": int(road_win),
        "y_sign": float(y_sign),
        "wheel_center_offset": float(wheel_center_offset),
        "road_y_offset": float(road_y_offset),
        "road_subtract_radius": bool(road_subtract_radius),
        "camera_follow": bool(camera_follow),
        "camera_follow_heading": bool(camera_follow_heading),
        "camera_follow_selected": bool(camera_follow_selected),
        "follow_smooth": float(follow_smooth),
        "hover_tooltip": bool(hover_tooltip),
        "show_minimap": bool(show_minimap),
        "minimap_size": int(minimap_size),
        "road_mode": str(road_mode),
        "spin_per_wheel": bool(spin_per_wheel),
        "show_suspension": bool(show_suspension),
        "show_contact": bool(show_contact),
        "show_gap_heat": bool(show_gap_heat),
        "gap_scale_m": float(gap_scale_m),
        "show_gap_hud": bool(show_gap_hud),
        "min_gap_window": int(min_gap_window),
        "min_gap_step": int(min_gap_step),
        "hover_contact_marker": bool(hover_contact_marker),
        "multi_view": bool(multi_view),
        "allow_pan": bool(allow_pan),
        "debug_overlay": bool(debug_overlay),
        "show_road_mesh": bool(show_road_mesh),
        "road_mesh_step": int(road_mesh_step),
        "show_trail": bool(show_trail),
        "trail_len": int(trail_len),
        "trail_step": int(trail_step),
    }


def render_mechanical_3d_control_panel(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    df_main,
    time_s,
    base_override: dict[str, Any],
    path_checkbox_label: str,
    path_demo_options: list[str],
    path_demo_info_text: str,
    path_non_demo_caption: str,
    base_default: float,
    track_default: float,
    camera_follow_default: bool,
    road_mesh_step_default: int,
    get_float_param_fn: Any | None = None,
    model_path_available: bool = False,
    model_path_caption: str | None = None,
    model_speed_values: Any | None = None,
) -> dict[str, Any]:
    colA, colB, colC = st.columns(3)
    with colA:
        (
            _demo_paths,
            path_mode,
            v0,
            lateral_scale,
            steer_gain,
            steer_max_deg,
        ) = render_mechanical_3d_path_controls(
            st,
            cache_key=cache_key,
            checkbox_label=path_checkbox_label,
            demo_options=path_demo_options,
            demo_info_text=path_demo_info_text,
            non_demo_caption=path_non_demo_caption,
            model_path_available=bool(model_path_available),
            model_path_caption=model_path_caption,
            model_speed_values=model_speed_values,
        )

    with colB:
        (
            slalom_amp,
            slalom_period,
            yaw_smooth,
            _turn_radius,
            _turn_dir,
        ) = render_mechanical_3d_maneuver_controls(
            st,
            cache_key=cache_key,
            demo_paths=bool(_demo_paths),
            path_mode=str(path_mode),
        )

    with colC:
        mech3d_visual = render_mechanical_3d_visual_controls(
            st,
            session_state=session_state,
            cache_key=cache_key,
            base_override=base_override,
            base_default=base_default,
            track_default=track_default,
            camera_follow_default=camera_follow_default,
            road_mesh_step_default=road_mesh_step_default,
            get_float_param_fn=get_float_param_fn,
        )

    path_payload = build_mechanical_3d_path_payload(
        session_state=session_state,
        df_main=df_main,
        cache_key=cache_key,
        time_s=time_s,
        path_mode=str(path_mode),
        v0=float(v0),
        slalom_amp=float(slalom_amp),
        slalom_period=float(slalom_period),
        yaw_smooth=float(yaw_smooth),
        lateral_scale=float(lateral_scale),
        steer_gain=float(steer_gain),
        steer_max_deg=float(steer_max_deg),
        base_m=float(mech3d_visual["base_m"]),
    )
    return {
        **mech3d_visual,
        "path_payload": path_payload,
    }


def normalize_mechanical_3d_control_values(mech3d_controls: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_m": float(mech3d_controls["base_m"]),
        "track_m": float(mech3d_controls["track_m"]),
        "wheel_r": float(mech3d_controls["wheel_r"]),
        "wheel_w": float(mech3d_controls["wheel_w"]),
        "body_y_off": float(mech3d_controls["body_y_off"]),
        "road_win": int(mech3d_controls["road_win"]),
        "y_sign": float(mech3d_controls["y_sign"]),
        "wheel_center_offset": float(mech3d_controls["wheel_center_offset"]),
        "road_y_offset": float(mech3d_controls["road_y_offset"]),
        "road_subtract_radius": bool(mech3d_controls["road_subtract_radius"]),
        "camera_follow": bool(mech3d_controls["camera_follow"]),
        "camera_follow_heading": bool(mech3d_controls["camera_follow_heading"]),
        "camera_follow_selected": bool(mech3d_controls["camera_follow_selected"]),
        "follow_smooth": float(mech3d_controls["follow_smooth"]),
        "hover_tooltip": bool(mech3d_controls["hover_tooltip"]),
        "show_minimap": bool(mech3d_controls["show_minimap"]),
        "minimap_size": int(mech3d_controls["minimap_size"]),
        "road_mode": str(mech3d_controls["road_mode"]),
        "spin_per_wheel": bool(mech3d_controls["spin_per_wheel"]),
        "show_suspension": bool(mech3d_controls["show_suspension"]),
        "show_contact": bool(mech3d_controls["show_contact"]),
        "show_gap_heat": bool(mech3d_controls["show_gap_heat"]),
        "gap_scale_m": float(mech3d_controls["gap_scale_m"]),
        "show_gap_hud": bool(mech3d_controls["show_gap_hud"]),
        "min_gap_window": int(mech3d_controls["min_gap_window"]),
        "min_gap_step": int(mech3d_controls["min_gap_step"]),
        "hover_contact_marker": bool(mech3d_controls["hover_contact_marker"]),
        "multi_view": bool(mech3d_controls["multi_view"]),
        "allow_pan": bool(mech3d_controls["allow_pan"]),
        "debug_overlay": bool(mech3d_controls["debug_overlay"]),
        "show_road_mesh": bool(mech3d_controls["show_road_mesh"]),
        "road_mesh_step": int(mech3d_controls["road_mesh_step"]),
        "show_trail": bool(mech3d_controls["show_trail"]),
        "trail_len": int(mech3d_controls["trail_len"]),
        "trail_step": int(mech3d_controls["trail_step"]),
        "path_payload": mech3d_controls["path_payload"],
    }


def render_mechanical_3d_body_controls(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    base_m: float,
    track_m: float,
    body_h_default: float = 0.35,
) -> tuple[float, float, float]:
    body_L = float(session_state.get(f"mech3d_body_L_{cache_key}", float(base_m) * 0.85))
    body_W = float(session_state.get(f"mech3d_body_W_{cache_key}", float(track_m) * 0.55))
    body_H = float(session_state.get(f"mech3d_body_H_{cache_key}", float(body_h_default)))
    c1, c2, c3 = st.columns(3)
    with c1:
        body_L = st.number_input(
            "Длина рамы (м)",
            min_value=0.2,
            value=body_L,
            step=0.05,
            key=f"mech3d_body_L_{cache_key}",
        )
    with c2:
        body_W = st.number_input(
            "Ширина рамы (м)",
            min_value=0.2,
            value=body_W,
            step=0.05,
            key=f"mech3d_body_W_{cache_key}",
        )
    with c3:
        body_H = st.number_input(
            "Высота рамы (м)",
            min_value=0.05,
            value=body_H,
            step=0.02,
            key=f"mech3d_body_H_{cache_key}",
        )
    return (float(body_L), float(body_W), float(body_H))


def build_mechanical_3d_geo_payload(
    *,
    base_m: float,
    track_m: float,
    wheel_r: float,
    wheel_w: float,
    wheel_center_offset: float,
    road_y_offset: float,
    road_subtract_radius: bool,
    road_mode: str,
    spin_per_wheel: bool,
    show_suspension: bool,
    show_contact: bool,
    multi_view: bool,
    allow_pan: bool,
    show_road_mesh: bool,
    road_mesh_step: int,
    show_trail: bool,
    trail_len: int,
    trail_step: int,
    y_sign: float,
    camera_follow: bool,
    camera_follow_heading: bool,
    camera_follow_selected: bool,
    hover_tooltip: bool,
    debug_overlay: bool,
    follow_smooth: float,
    show_gap_heat: bool,
    gap_scale_m: float,
    show_gap_hud: bool,
    min_gap_window: int,
    min_gap_step: int,
    hover_contact_marker: bool,
    show_minimap: bool,
    minimap_size: int,
    body_y_off: float,
    body_L: float,
    body_W: float,
    body_H: float,
    road_win: int,
    extra_geo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    geo_payload = {
        "base_m": float(base_m),
        "track_m": float(track_m),
        "wheel_radius_m": float(wheel_r),
        "wheel_width_m": float(wheel_w),
        "wheel_center_offset_m": float(wheel_center_offset),
        "road_y_offset_m": float(road_y_offset),
        "road_subtract_radius": bool(road_subtract_radius),
        "road_mode": str(road_mode),
        "spin_per_wheel": bool(spin_per_wheel),
        "show_suspension": bool(show_suspension),
        "show_contact": bool(show_contact),
        "multi_view": bool(multi_view),
        "allow_pan": bool(allow_pan),
        "show_road_mesh": bool(show_road_mesh),
        "road_mesh_step": int(road_mesh_step),
        "show_trail": bool(show_trail),
        "trail_len": int(trail_len),
        "trail_step": int(trail_step),
        "y_sign": float(y_sign),
        "camera_follow": bool(camera_follow),
        "camera_follow_heading": bool(camera_follow_heading),
        "camera_follow_selected": bool(camera_follow_selected),
        "hover_tooltip": bool(hover_tooltip),
        "debug_overlay": bool(debug_overlay),
        "follow_smooth": float(follow_smooth),
        "show_gap_heat": bool(show_gap_heat),
        "gap_scale_m": float(gap_scale_m),
        "show_gap_hud": bool(show_gap_hud),
        "min_gap_window": int(min_gap_window),
        "min_gap_step": int(min_gap_step),
        "hover_contact_marker": bool(hover_contact_marker),
        "show_minimap": bool(show_minimap),
        "minimap_size": int(minimap_size),
        "body_y_offset_m": float(body_y_off),
        "body_L_m": float(body_L),
        "body_W_m": float(body_W),
        "body_H_m": float(body_H),
        "road_window_points": int(road_win),
        "path_window_points": 160,
        "roll_sign": 1.0,
        "pitch_sign": 1.0,
        "spin_sign": 1.0,
        "wheel_x_off_m": {
            "ЛП": float(base_m) * 0.5,
            "ПП": float(base_m) * 0.5,
            "ЛЗ": -float(base_m) * 0.5,
            "ПЗ": -float(base_m) * 0.5,
        },
        "wheel_z_off_m": {
            "ЛП": -float(track_m) * 0.5,
            "ПП": float(track_m) * 0.5,
            "ЛЗ": -float(track_m) * 0.5,
            "ПЗ": float(track_m) * 0.5,
        },
    }
    if extra_geo:
        geo_payload.update(extra_geo)
    return geo_payload


def build_mechanical_3d_component_payload(
    session_state: dict[str, Any],
    *,
    dataset_id: Any,
    time,
    body,
    wheel,
    road,
    phi,
    theta,
    path: dict[str, Any],
    geo: dict[str, Any],
    title: str = MECH_3D_COMPONENT_TITLE,
    playhead_storage_key: str = MECH_2D_PLAYHEAD_STORAGE_KEY,
    height: int = MECH_3D_COMPONENT_HEIGHT,
    key: str = MECH_3D_COMPONENT_KEY,
) -> dict[str, Any]:
    return {
        "title": title,
        "time": time,
        "body": body,
        "wheel": wheel,
        "road": road,
        "phi": _to_list(phi),
        "theta": _to_list(theta),
        "selected": session_state.get("mech_selected_corners", []),
        "path": path,
        "geo": geo,
        "dataset_id": dataset_id,
        "playhead_storage_key": playhead_storage_key,
        "height": int(height),
        "key": key,
        "default": None,
    }


def build_mechanical_3d_fallback_payload(
    *,
    dataset_id: str,
    time,
    body,
    wheel,
    road,
    phi,
    theta,
    path: dict[str, Any],
    wheelbase: float,
    track: float,
    log_cb: Any,
) -> dict[str, Any]:
    return {
        "time": time,
        "body": body,
        "wheel": wheel,
        "road": road,
        "phi": _to_list(phi),
        "theta": _to_list(theta),
        "path": path,
        "wheelbase_m": float(wheelbase),
        "track_m": float(track),
        "dataset_id": str(dataset_id),
        "log_cb": log_cb,
    }


def resolve_mechanical_3d_component_or_render_fallback(
    st: Any,
    *,
    use_component_anim: bool,
    get_component_fn: Any,
    mech_fallback_module: Any,
    fallback_payload: dict[str, Any],
    on_component_missing: Any | None = None,
    on_component_disabled: Any | None = None,
    on_fallback_missing: Any | None = None,
) -> tuple[str, Any | None]:
    mech_comp = get_component_fn() if use_component_anim else None
    if mech_comp is not None:
        return ("component", mech_comp)

    if use_component_anim:
        if on_component_missing is not None:
            on_component_missing()
        else:
            st.warning(MECH_3D_COMPONENT_MISSING_WARNING)
    else:
        if on_component_disabled is not None:
            on_component_disabled()
        else:
            st.info(MECH_3D_COMPONENT_DISABLED_INFO)

    if mech_fallback_module is not None:
        mech_fallback_module.render_mech3d_fallback(**fallback_payload)
        return ("fallback", None)

    if on_fallback_missing is not None:
        on_fallback_missing()
    else:
        st.error(MECH_3D_FALLBACK_MISSING_ERROR)
    return ("missing", None)


def prepare_mechanical_3d_component_runtime(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    dataset_id: Any,
    time,
    body,
    wheel,
    road,
    phi,
    theta,
    mech3d_values: dict[str, Any],
    use_component_anim: bool,
    get_component_fn: Any,
    mech_fallback_module: Any,
    log_cb: Any,
    extra_geo: dict[str, Any] | None = None,
    on_component_missing: Any | None = None,
    on_component_disabled: Any | None = None,
    on_fallback_missing: Any | None = None,
) -> dict[str, Any]:
    mech3d_fallback_payload = build_mechanical_3d_fallback_payload(
        dataset_id=str(dataset_id),
        time=time,
        body=body,
        wheel=wheel,
        road=road,
        phi=phi,
        theta=theta,
        path=mech3d_values["path_payload"],
        wheelbase=float(mech3d_values["base_m"]),
        track=float(mech3d_values["track_m"]),
        log_cb=log_cb,
    )
    status, mech3d_comp = resolve_mechanical_3d_component_or_render_fallback(
        st,
        use_component_anim=use_component_anim,
        get_component_fn=get_component_fn,
        mech_fallback_module=mech_fallback_module,
        fallback_payload=mech3d_fallback_payload,
        on_component_missing=on_component_missing,
        on_component_disabled=on_component_disabled,
        on_fallback_missing=on_fallback_missing,
    )
    result = {
        "status": status,
        "mech3d_comp": mech3d_comp,
        "fallback_payload": mech3d_fallback_payload,
        "geo_payload": None,
        "component_payload": None,
        "body_L": None,
        "body_W": None,
        "body_H": None,
    }
    if mech3d_comp is None:
        return result

    body_L, body_W, body_H = render_mechanical_3d_body_controls(
        st,
        session_state=session_state,
        cache_key=cache_key,
        base_m=float(mech3d_values["base_m"]),
        track_m=float(mech3d_values["track_m"]),
    )
    geo_payload = build_mechanical_3d_geo_payload(
        base_m=float(mech3d_values["base_m"]),
        track_m=float(mech3d_values["track_m"]),
        wheel_r=float(mech3d_values["wheel_r"]),
        wheel_w=float(mech3d_values["wheel_w"]),
        wheel_center_offset=float(mech3d_values["wheel_center_offset"]),
        road_y_offset=float(mech3d_values["road_y_offset"]),
        road_subtract_radius=bool(mech3d_values["road_subtract_radius"]),
        road_mode=str(mech3d_values["road_mode"]),
        spin_per_wheel=bool(mech3d_values["spin_per_wheel"]),
        show_suspension=bool(mech3d_values["show_suspension"]),
        show_contact=bool(mech3d_values["show_contact"]),
        multi_view=bool(mech3d_values["multi_view"]),
        allow_pan=bool(mech3d_values["allow_pan"]),
        show_road_mesh=bool(mech3d_values["show_road_mesh"]),
        road_mesh_step=int(mech3d_values["road_mesh_step"]),
        show_trail=bool(mech3d_values["show_trail"]),
        trail_len=int(mech3d_values["trail_len"]),
        trail_step=int(mech3d_values["trail_step"]),
        y_sign=float(mech3d_values["y_sign"]),
        camera_follow=bool(mech3d_values["camera_follow"]),
        camera_follow_heading=bool(mech3d_values["camera_follow_heading"]),
        camera_follow_selected=bool(mech3d_values["camera_follow_selected"]),
        hover_tooltip=bool(mech3d_values["hover_tooltip"]),
        debug_overlay=bool(mech3d_values["debug_overlay"]),
        follow_smooth=float(mech3d_values["follow_smooth"]),
        show_gap_heat=bool(mech3d_values["show_gap_heat"]),
        gap_scale_m=float(mech3d_values["gap_scale_m"]),
        show_gap_hud=bool(mech3d_values["show_gap_hud"]),
        min_gap_window=int(mech3d_values["min_gap_window"]),
        min_gap_step=int(mech3d_values["min_gap_step"]),
        hover_contact_marker=bool(mech3d_values["hover_contact_marker"]),
        show_minimap=bool(mech3d_values["show_minimap"]),
        minimap_size=int(mech3d_values["minimap_size"]),
        body_y_off=float(mech3d_values["body_y_off"]),
        body_L=float(body_L),
        body_W=float(body_W),
        body_H=float(body_H),
        road_win=int(mech3d_values["road_win"]),
        extra_geo=extra_geo,
    )
    component_payload = build_mechanical_3d_component_payload(
        session_state,
        dataset_id=dataset_id,
        time=time,
        body=body,
        wheel=wheel,
        road=road,
        phi=phi,
        theta=theta,
        path=mech3d_values["path_payload"],
        geo=geo_payload,
    )
    result.update(
        {
            "geo_payload": geo_payload,
            "component_payload": component_payload,
            "body_L": float(body_L),
            "body_W": float(body_W),
            "body_H": float(body_H),
        }
    )
    return result


def prepare_mechanical_3d_ring_visual(
    *,
    tests_map: Any,
    test_pick: Any,
    base_dir: Path,
    pick: Any,
    session_state: dict[str, Any],
    workspace_exports_dir: Path,
    time_s,
    path_payload: dict[str, Any],
    track_m: float,
    wheel_width_m: float,
    wheelbase_m: float,
    log_cb: Any,
    latest_export_paths_fn: Any,
    load_spec_from_test_cfg_fn: Any = load_ring_spec_from_test_cfg,
    load_spec_from_npz_fn: Any = load_ring_spec_from_npz,
    build_visual_payload_fn: Any = build_ring_visual_payload_from_spec,
    build_nominal_progress_fn: Any = build_nominal_ring_progress_from_spec,
    embed_path_payload_fn: Any = embed_path_payload_on_ring,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    ring_visual = None
    updated_path_payload = dict(path_payload or {})
    try:
        ring_spec = load_spec_from_test_cfg_fn(
            tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {},
            base_dir=base_dir,
        )
        if not (isinstance(ring_spec, dict) and isinstance(ring_spec.get("segments"), list)):
            npz_candidates: list[Path] = []
            try:
                pick_path = Path(str(pick))
                if pick_path.suffix.lower() == ".npz":
                    npz_candidates.append(pick_path)
            except Exception:
                pass
            try:
                npz_ss = str(session_state.get("anim_latest_npz") or "").strip()
                if npz_ss:
                    npz_candidates.append(Path(npz_ss))
            except Exception:
                pass
            latest_npz_path, _ = latest_export_paths_fn(
                workspace_exports_dir,
                ensure_exists=False,
            )
            npz_candidates.append(Path(latest_npz_path))
            for npz_cand in npz_candidates:
                try:
                    npz_cand = Path(npz_cand)
                    if npz_cand.exists():
                        ring_spec = load_spec_from_npz_fn(npz_cand)
                        if isinstance(ring_spec, dict) and isinstance(ring_spec.get("segments"), list):
                            try:
                                log_cb(
                                    "ring_visual_loaded_from_npz_sidecar",
                                    npz=str(npz_cand),
                                    test=str(test_pick),
                                )
                            except Exception:
                                pass
                            break
                except Exception:
                    continue
        if isinstance(ring_spec, dict) and isinstance(ring_spec.get("segments"), list):
            ring_visual = build_visual_payload_fn(
                ring_spec,
                track_m=float(track_m),
                wheel_width_m=float(wheel_width_m),
                seed=int(ring_spec.get("seed", 0) or 0),
            )
            if ring_visual:
                nominal_prog = build_nominal_progress_fn(ring_spec, time_s)
                if nominal_prog.get("distance_m"):
                    updated_path_payload["s"] = list(nominal_prog.get("distance_m") or [])
                    updated_path_payload["v"] = list(nominal_prog.get("v_mps") or updated_path_payload.get("v") or [])
                updated_path_payload = embed_path_payload_fn(
                    updated_path_payload,
                    ring_visual,
                    wheelbase_m=float(wheelbase_m),
                )
    except Exception as exc:
        ring_visual = None
        log_cb("ring_visual_payload_error", err=str(exc), test=str(test_pick))
    return ring_visual, updated_path_payload


def render_mechanical_3d_ring_visual_notice(st: Any, ring_visual: dict[str, Any] | None) -> None:
    if not ring_visual:
        return
    st.info(
        f"3D кольцо: замкнутый ring-view, сегменты подсвечены по краям, heatmap = кривизна. "
        f"Длина кольца ≈ {float(ring_visual.get('ring_length_m', 0.0)):.2f} м, "
        f"post-seam ≈ {1000.0 * float((ring_visual.get('meta', {}) or {}).get('seam_max_jump_m', 0.0) or 0.0):.1f} мм."
    )


def render_mechanical_3d_component_from_runtime(
    st: Any,
    mech3d_runtime: dict[str, Any],
    *,
    ring_visual: dict[str, Any] | None = None,
    on_runtime_error: Any | None = None,
) -> str:
    mech3d_comp = mech3d_runtime.get("mech3d_comp")
    if mech3d_comp is None:
        return str(mech3d_runtime.get("status") or "skipped")

    render_mechanical_3d_ring_visual_notice(st, ring_visual)
    try:
        mech3d_comp(**mech3d_runtime["component_payload"])
        return "component"
    except Exception as exc:
        if on_runtime_error is not None:
            on_runtime_error(exc)
            return "runtime_error"
        raise


def build_mechanical_3d_runtime_callbacks(
    st: Any,
    *,
    component_last_error_fn: Any,
    log_cb: Any,
    proc_metrics_fn: Any,
    safe_image_fn: Any,
    base_dir: Path,
    component_name: str = "mech_car3d",
) -> dict[str, Any]:
    def _on_component_missing() -> None:
        st.warning(MECH_3D_COMPONENT_MISSING_WARNING)
        component_err = component_last_error_fn(component_name)
        log_cb(
            "component_missing",
            component=component_name,
            detail=str(component_err) if component_err else None,
            proc=proc_metrics_fn(),
        )

    def _on_component_disabled() -> None:
        st.info(MECH_3D_COMPONENT_DISABLED_INFO)

    def _on_fallback_missing() -> None:
        st.error(MECH_3D_FALLBACK_MISSING_ERROR)

    def _on_runtime_error(exc: Exception) -> None:
        st.warning("Компонент мех. 3D (mech_car3d) упал во время выполнения. Показываю статическую схему.")
        log_cb(
            "component_runtime_error",
            component=component_name,
            error=repr(exc),
            traceback=traceback.format_exc(),
            proc=proc_metrics_fn(),
        )
        render_mechanical_static_scheme(safe_image_fn, base_dir=base_dir)

    return {
        "on_component_missing": _on_component_missing,
        "on_component_disabled": _on_component_disabled,
        "on_fallback_missing": _on_fallback_missing,
        "on_runtime_error": _on_runtime_error,
    }


def render_mechanical_3d_animation_panel(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    dataset_id: Any,
    time,
    body,
    wheel,
    road,
    phi,
    theta,
    df_main,
    base_override: dict[str, Any],
    use_component_anim: bool,
    get_component_fn: Any,
    mech_fallback_module: Any,
    log_cb: Any,
    path_checkbox_label: str,
    path_demo_options: list[str],
    path_demo_info_text: str,
    path_non_demo_caption: str,
    base_default: float,
    track_default: float,
    camera_follow_default: bool,
    road_mesh_step_default: int,
    get_float_param_fn: Any | None = None,
    model_path_available: bool = False,
    model_path_caption: str | None = None,
    model_speed_values: Any | None = None,
    component_last_error_fn: Any | None = None,
    proc_metrics_fn: Any | None = None,
    safe_image_fn: Any | None = None,
    base_dir: Path | None = None,
    ring_visual_tests_map: Any | None = None,
    ring_visual_test_pick: Any | None = None,
    ring_visual_pick: Any | None = None,
    ring_visual_workspace_exports_dir: Path | None = None,
    ring_visual_latest_export_paths_fn: Any | None = None,
    ring_visual_base_dir: Path | None = None,
    intro_fn: Any = render_mechanical_3d_intro,
    control_panel_fn: Any = render_mechanical_3d_control_panel,
    normalize_values_fn: Any = normalize_mechanical_3d_control_values,
    ring_visual_prepare_fn: Any = prepare_mechanical_3d_ring_visual,
    build_runtime_callbacks_fn: Any = build_mechanical_3d_runtime_callbacks,
    prepare_runtime_fn: Any = prepare_mechanical_3d_component_runtime,
    render_component_fn: Any = render_mechanical_3d_component_from_runtime,
) -> dict[str, Any]:
    intro_fn(st)
    mech3d_controls = control_panel_fn(
        st,
        session_state=session_state,
        cache_key=cache_key,
        df_main=df_main,
        time_s=time,
        base_override=base_override,
        path_checkbox_label=path_checkbox_label,
        path_demo_options=path_demo_options,
        path_demo_info_text=path_demo_info_text,
        path_non_demo_caption=path_non_demo_caption,
        base_default=base_default,
        track_default=track_default,
        camera_follow_default=camera_follow_default,
        road_mesh_step_default=road_mesh_step_default,
        get_float_param_fn=get_float_param_fn,
        model_path_available=bool(model_path_available),
        model_path_caption=model_path_caption,
        model_speed_values=model_speed_values,
    )
    mech3d_values = normalize_values_fn(mech3d_controls)

    ring_visual = None
    if (
        ring_visual_workspace_exports_dir is not None
        and ring_visual_latest_export_paths_fn is not None
        and ring_visual_pick is not None
    ):
        ring_visual, path_payload = ring_visual_prepare_fn(
            tests_map=ring_visual_tests_map,
            test_pick=ring_visual_test_pick,
            base_dir=ring_visual_base_dir if ring_visual_base_dir is not None else base_dir,
            pick=ring_visual_pick,
            session_state=session_state,
            workspace_exports_dir=ring_visual_workspace_exports_dir,
            time_s=time,
            path_payload=mech3d_values["path_payload"],
            track_m=float(mech3d_values["track_m"]),
            wheel_width_m=float(mech3d_values["wheel_w"]),
            wheelbase_m=float(mech3d_values["base_m"]),
            log_cb=log_cb,
            latest_export_paths_fn=ring_visual_latest_export_paths_fn,
        )
        mech3d_values["path_payload"] = path_payload

    mech3d_callbacks: dict[str, Any] = {}
    if (
        component_last_error_fn is not None
        and proc_metrics_fn is not None
        and safe_image_fn is not None
        and base_dir is not None
    ):
        mech3d_callbacks = build_runtime_callbacks_fn(
            st,
            component_last_error_fn=component_last_error_fn,
            log_cb=log_cb,
            proc_metrics_fn=proc_metrics_fn,
            safe_image_fn=safe_image_fn,
            base_dir=base_dir,
        )

    mech3d_runtime = prepare_runtime_fn(
        st,
        session_state=session_state,
        cache_key=cache_key,
        dataset_id=dataset_id,
        time=time,
        body=body,
        wheel=wheel,
        road=road,
        phi=phi,
        theta=theta,
        mech3d_values=mech3d_values,
        use_component_anim=use_component_anim,
        get_component_fn=get_component_fn,
        mech_fallback_module=mech_fallback_module,
        log_cb=log_cb,
        extra_geo={"ring_visual": ring_visual} if ring_visual is not None else None,
        on_component_missing=mech3d_callbacks.get("on_component_missing"),
        on_component_disabled=mech3d_callbacks.get("on_component_disabled"),
        on_fallback_missing=mech3d_callbacks.get("on_fallback_missing"),
    )
    render_status = render_component_fn(
        st,
        mech3d_runtime,
        ring_visual=ring_visual,
        on_runtime_error=mech3d_callbacks.get("on_runtime_error"),
    )
    return {
        "mech3d_controls": mech3d_controls,
        "mech3d_values": mech3d_values,
        "mech3d_runtime": mech3d_runtime,
        "mech3d_callbacks": mech3d_callbacks,
        "ring_visual": ring_visual,
        "render_status": render_status,
    }


def render_mechanical_animation_section(
    st: Any,
    *,
    session_state: dict[str, Any],
    cache_key: str,
    dataset_id: Any,
    df_main,
    time,
    body_2d,
    body_3d,
    wheel,
    road,
    stroke,
    phi,
    theta,
    px_per_m: float,
    body_offset_px: float,
    L_stroke_m: float,
    frame_dt_s: float,
    wheelbase: float,
    track: float,
    playhead_idx: int | None = None,
    show_2d_controls: bool | None = None,
    base_override: dict[str, Any],
    log_cb: Any,
    proc_metrics_fn: Any,
    safe_image_fn: Any,
    base_dir: Path,
    get_mech_anim_component_fn: Any,
    get_mech_car3d_component_fn: Any,
    mech_fallback_module: Any,
    backend_default_index: int,
    backend_description_text: str,
    path_checkbox_label: str,
    path_demo_options: list[str],
    path_demo_info_text: str,
    path_non_demo_caption: str,
    base_default: float,
    track_default: float,
    camera_follow_default: bool,
    road_mesh_step_default: int,
    get_float_param_fn: Any | None = None,
    enable_model_path_mode: bool = False,
    model_path_caption: str | None = None,
    component_last_error_fn: Any | None = None,
    fallback_error: Any = None,
    ring_visual_tests_map: Any | None = None,
    ring_visual_test_pick: Any | None = None,
    ring_visual_pick: Any | None = None,
    ring_visual_workspace_exports_dir: Path | None = None,
    ring_visual_latest_export_paths_fn: Any | None = None,
    ring_visual_base_dir: Path | None = None,
    intro_fn: Any = render_mechanical_animation_intro,
    backend_selector_fn: Any = render_mechanical_animation_backend_selector,
    render_2d_panel_fn: Any = render_mechanical_2d_animation_panel,
    render_3d_panel_fn: Any = render_mechanical_3d_animation_panel,
    asset_expander_fn: Any = render_mechanical_scheme_asset_expander,
) -> dict[str, Any]:
    proceed = bool(intro_fn(st, df_main=df_main))
    if not proceed:
        return {
            "proceed": False,
            "use_component_anim": None,
            "mech_view": None,
            "panel_result": None,
        }

    use_component_anim = backend_selector_fn(
        st,
        session_state,
        cache_key=cache_key,
        dataset_id=str(dataset_id),
        log_event_fn=log_cb,
        proc_metrics_fn=proc_metrics_fn,
        default_backend_index=int(backend_default_index),
        description_text=backend_description_text,
    )

    mech_view = st.radio(
        "Визуализация",
        options=["2D (схема)", "3D (машинка)"],
        horizontal=True,
        key=f"mech_view_{cache_key}",
    )

    panel_result = None
    if mech_view == "2D (схема)":
        panel_result = render_2d_panel_fn(
            st,
            session_state=session_state,
            cache_key=cache_key,
            dataset_id=dataset_id,
            time=time,
            body=body_2d,
            wheel=wheel,
            road=road,
            stroke=stroke,
            phi=phi,
            theta=theta,
            px_per_m=px_per_m,
            body_offset_px=body_offset_px,
            L_stroke_m=L_stroke_m,
            frame_dt_s=frame_dt_s,
            wheelbase=wheelbase,
            track=track,
            use_component_anim=use_component_anim,
            get_component_fn=get_mech_anim_component_fn,
            mech_fallback_module=mech_fallback_module,
            log_cb=log_cb,
            safe_image_fn=safe_image_fn,
            base_dir=base_dir,
            idx=(int(playhead_idx) if playhead_idx is not None else None),
            show_controls=show_2d_controls,
            component_last_error_fn=component_last_error_fn,
            proc_metrics_fn=proc_metrics_fn if component_last_error_fn is not None else None,
            fallback_error=fallback_error,
        )
    elif mech_view == "3D (машинка)":
        has_world_path = bool(
            enable_model_path_mode
            and df_main is not None
            and ("скорость_vx_м_с" in df_main.columns)
            and ("yaw_рад" in df_main.columns)
        )
        model_speed_values = (
            df_main["скорость_vx_м_с"].to_numpy(dtype=float)
            if bool(has_world_path)
            else None
        )
        panel_result = render_3d_panel_fn(
            st,
            session_state=session_state,
            cache_key=cache_key,
            dataset_id=dataset_id,
            time=time,
            body=body_3d,
            wheel=wheel,
            road=road,
            phi=phi,
            theta=theta,
            df_main=df_main,
            base_override=base_override,
            use_component_anim=use_component_anim,
            get_component_fn=get_mech_car3d_component_fn,
            mech_fallback_module=mech_fallback_module,
            log_cb=log_cb,
            path_checkbox_label=path_checkbox_label,
            path_demo_options=path_demo_options,
            path_demo_info_text=path_demo_info_text,
            path_non_demo_caption=path_non_demo_caption,
            base_default=base_default,
            track_default=track_default,
            camera_follow_default=camera_follow_default,
            road_mesh_step_default=road_mesh_step_default,
            get_float_param_fn=get_float_param_fn,
            model_path_available=bool(has_world_path),
            model_path_caption=model_path_caption,
            model_speed_values=model_speed_values,
            component_last_error_fn=component_last_error_fn,
            proc_metrics_fn=proc_metrics_fn if component_last_error_fn is not None else None,
            safe_image_fn=safe_image_fn if component_last_error_fn is not None else None,
            base_dir=base_dir if component_last_error_fn is not None else None,
            ring_visual_tests_map=ring_visual_tests_map,
            ring_visual_test_pick=ring_visual_test_pick,
            ring_visual_pick=ring_visual_pick,
            ring_visual_workspace_exports_dir=ring_visual_workspace_exports_dir,
            ring_visual_latest_export_paths_fn=ring_visual_latest_export_paths_fn,
            ring_visual_base_dir=ring_visual_base_dir,
        )

    asset_expander_fn(
        st,
        base_dir=base_dir,
        safe_image_fn=safe_image_fn,
    )
    return {
        "proceed": True,
        "use_component_anim": bool(use_component_anim),
        "mech_view": str(mech_view),
        "panel_result": panel_result,
    }


def build_mechanical_3d_path_payload(
    *,
    session_state: dict[str, Any],
    df_main,
    cache_key: str,
    time_s,
    path_mode: str,
    v0: float,
    slalom_amp: float,
    slalom_period: float,
    yaw_smooth: float,
    lateral_scale: float,
    steer_gain: float,
    steer_max_deg: float,
    base_m: float,
    model_path_mode_label: str = MECH_3D_MODEL_PATH_MODE,
    model_speed_col: str = "скорость_vx_м_с",
    model_yaw_col: str = "yaw_рад",
    ax_col: str = "ускорение_продольное_ax_м_с2",
    ay_col: str = "ускорение_поперечное_ay_м_с2",
) -> dict[str, list[float]]:
    t_np = np.asarray(time_s, dtype=float)
    n = len(t_np)
    if n >= 2:
        dt = np.diff(t_np, prepend=t_np[0])
        dt[0] = dt[1]
    else:
        dt = np.ones_like(t_np)

    x = np.zeros(n, dtype=float)
    z = np.zeros(n, dtype=float)
    vx = np.zeros(n, dtype=float)
    vz = np.zeros(n, dtype=float)
    yaw = np.zeros(n, dtype=float)

    if path_mode == MECH_3D_STATIC_MODE:
        pass
    elif path_mode == model_path_mode_label:
        v_body = (
            df_main[model_speed_col].to_numpy(dtype=float)
            if df_main is not None and model_speed_col in df_main.columns
            else np.full(n, float(v0), dtype=float)
        )
        yaw = (
            df_main[model_yaw_col].to_numpy(dtype=float)
            if df_main is not None and model_yaw_col in df_main.columns
            else np.zeros(n, dtype=float)
        )
        vx = v_body * np.cos(yaw)
        vz = v_body * np.sin(yaw)
        x = np.cumsum(vx * dt)
        z = np.cumsum(vz * dt)
        x = x - x[0]
        z = z - z[0]
    elif path_mode == "Прямая":
        vx[:] = float(v0)
        x = np.cumsum(vx * dt)
        x = x - x[0]
    elif path_mode == "Слалом":
        vx[:] = float(v0)
        z = float(slalom_amp) * np.sin(2.0 * np.pi * t_np / float(slalom_period))
        vz = float(slalom_amp) * (2.0 * np.pi / float(slalom_period)) * np.cos(
            2.0 * np.pi * t_np / float(slalom_period)
        )
        x = np.cumsum(vx * dt)
        x = x - x[0]
    elif path_mode == "Поворот (радиус)":
        turn_radius = float(session_state.get(f"mech3d_turn_R_{cache_key}", 35.0))
        dir_left = str(session_state.get(f"mech3d_turn_dir_{cache_key}", "влево")).startswith("влево")
        sign = 1.0 if dir_left else -1.0
        vx[:] = float(v0)
        omega = (float(v0) / max(1e-6, turn_radius)) * sign
        yaw = omega * (t_np - t_np[0])
        x = turn_radius * np.sin(yaw)
        z = sign * turn_radius * (1.0 - np.cos(yaw))
        vx = float(v0) * np.cos(yaw)
        vz = float(v0) * np.sin(yaw) * sign
    else:
        ax = (
            df_main[ax_col].to_numpy(dtype=float)
            if df_main is not None and ax_col in df_main.columns
            else np.zeros(n, dtype=float)
        )
        ay = (
            df_main[ay_col].to_numpy(dtype=float)
            if df_main is not None and ay_col in df_main.columns
            else np.zeros(n, dtype=float)
        )
        if n > 0:
            vx[0] = float(v0)
            vz[0] = 0.0
        for i in range(1, n):
            vx[i] = vx[i - 1] + ax[i] * dt[i]
            vz[i] = vz[i - 1] + ay[i] * dt[i]
            x[i] = x[i - 1] + vx[i] * dt[i]
            z[i] = z[i - 1] + vz[i] * dt[i]

    z = z * float(lateral_scale)

    if path_mode not in ("Поворот (радиус)", model_path_mode_label):
        yaw = np.arctan2(vz * float(lateral_scale), np.maximum(vx, 1e-6))

    if n >= 3 and float(yaw_smooth) > 0.0:
        alpha = float(yaw_smooth)
        for i in range(1, n):
            yaw[i] = (1 - alpha) * yaw[i - 1] + alpha * yaw[i]

    vabs = np.sqrt(vx * vx + (vz * float(lateral_scale)) * (vz * float(lateral_scale)))
    s = np.cumsum(vabs * dt)
    s = s - s[0]

    if n >= 3:
        yaw_u = np.unwrap(yaw)
        yaw_rate = np.gradient(yaw_u, t_np)
    else:
        yaw_rate = np.zeros(n, dtype=float)
    steer = np.arctan2(float(base_m) * yaw_rate, np.maximum(vabs, 0.1))
    steer = steer * float(steer_gain)
    steer_max = np.deg2rad(float(steer_max_deg))
    steer = np.clip(steer, -steer_max, steer_max)

    return {
        "x": x.tolist(),
        "z": z.tolist(),
        "yaw": yaw.tolist(),
        "s": s.tolist(),
        "v": vabs.tolist(),
        "steer": steer.tolist(),
    }
