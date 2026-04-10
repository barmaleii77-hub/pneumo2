# -*- coding: utf-8 -*-
"""pneumo_solver_ui.animation_cockpit_web

Новая web-страница, ориентированная на **анимацию** и одновременное
наблюдение нескольких параметров.

Ключевая идея:
- Один общий Playhead (components/playhead_ctrl) пишет состояние в localStorage.
- 2D мех-анимация (components/mech_anim), 3D (components/mech_car3d) и
  живые панели (напр. corner_heatmap_live) читают тот же localStorage.
- Получаем синхронную анимацию *без* серверных rerun на каждый кадр.

Эта страница не заменяет "Validation Cockpit", а дополняет:
- Validation = проверка качества прогона
- Animation Cockpit = визуальный "приборный щиток" (multi-view)
"""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Dict, Tuple

import numpy as np
import streamlit as st

from pneumo_solver_ui.data_contract import read_visual_geometry_meta
from pneumo_solver_ui.validation_cockpit_web import (
    CORNERS,
    P_ATM_DEFAULT,
    _default_npz_dirs,
    _extract_mech_arrays,
    _load_npz,
)
from pneumo_solver_ui.visual_contract import (
    collect_visual_cache_dependencies,
    collect_visual_contract_status as _collect_visual_contract_status,
    filter_road_payload as _filter_road_payload,
)
from pneumo_solver_ui.ring_visuals import (
    load_ring_spec_from_npz,
    build_ring_visual_payload_from_spec,
    build_nominal_ring_progress_from_spec,
    build_segment_ranges_from_progress,
    embed_path_payload_on_ring,
)

# Streamlit custom components factories (safe wrappers)
logger = logging.getLogger(__name__)

from pneumo_solver_ui.ui_components import (
    get_corner_heatmap_live_component,
    get_mech_anim_component,
    get_mech_anim_quad_component,
    get_mech_car3d_component,
    get_minimap_live_component,
    get_road_profile_live_component,
    get_playhead_ctrl_component,
)


def _robust_minmax(series_by_corner: Dict[str, np.ndarray]) -> Tuple[float, float]:
    """Robust global min/max across corners (percentiles to ignore spikes)."""
    arrs = []
    for c in CORNERS:
        a = np.asarray(series_by_corner.get(c, []), dtype=float)
        if a.size:
            arrs.append(a)
    if not arrs:
        return -1.0, 1.0
    vals = np.concatenate([a[np.isfinite(a)] for a in arrs if a.size])
    if vals.size == 0:
        return -1.0, 1.0
    lo = float(np.nanpercentile(vals, 2.0))
    hi = float(np.nanpercentile(vals, 98.0))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        m = float(np.nanmax(np.abs(vals)))
        if not np.isfinite(m) or m == 0.0:
            m = 1.0
        lo, hi = -m, m
    return lo, hi


def _series_for_metric(
    metric: str,
    *,
    t: np.ndarray,
    body: Dict[str, list[float]],
    wheel: Dict[str, list[float]],
    road: Dict[str, list[float]],
    stroke: Dict[str, list[float]],
    dist_unit: str,
) -> Tuple[Dict[str, np.ndarray], str, str]:
    """Build {corner -> series} for heatmap component."""
    series: Dict[str, np.ndarray] = {}
    title = metric
    unit = dist_unit

    if metric == "Кузов: положение z":
        for c in CORNERS:
            series[c] = np.asarray(body.get(c, []), dtype=float)
        unit = dist_unit

    elif metric == "Кузов: скорость dz/dt":
        for c in CORNERS:
            series[c] = np.gradient(np.asarray(body.get(c, []), dtype=float), t)
        unit = f"{dist_unit}/s"

    elif metric == "Кузов: ускорение d²z/dt²":
        for c in CORNERS:
            z = np.asarray(body.get(c, []), dtype=float)
            v = np.gradient(z, t)
            series[c] = np.gradient(v, t)
        unit = f"{dist_unit}/s²"

    elif metric == "Колесо: положение z":
        for c in CORNERS:
            series[c] = np.asarray(wheel.get(c, []), dtype=float)
        unit = dist_unit

    elif metric == "Шток: ход":
        for c in CORNERS:
            series[c] = np.asarray(stroke.get(c, []), dtype=float)
        unit = dist_unit

    elif metric == "Дорога: профиль":
        for c in CORNERS:
            series[c] = np.asarray(road.get(c, []), dtype=float)
        unit = dist_unit

    else:
        # fallback: body z
        for c in CORNERS:
            series[c] = np.asarray(body.get(c, []), dtype=float)
        unit = dist_unit

    return series, unit, title


def _safe_float(v, default: float) -> float:
    try:
        x = float(v)
        if not np.isfinite(x):
            return float(default)
        return float(x)
    except Exception:
        return float(default)



def _infer_geometry_from_meta(meta: dict) -> Dict[str, object]:
    """Infer visualization geometry strictly from nested ``meta_json.geometry``.

    Returns a dict with canonical values and contract messages. Missing values stay at
    ``0.0`` instead of borrowing from any non-canonical source.
    """
    if not isinstance(meta, dict):
        meta = {}

    vis_geom = read_visual_geometry_meta(
        meta,
        context="Animation Cockpit NPZ meta_json",
        log=lambda m: logger.warning("[Animation Cockpit] %s", m),
    )

    wheelbase = float(vis_geom.get("wheelbase_m") or 0.0)
    track = float(vis_geom.get("track_m") or 0.0)
    wheel_radius = float(vis_geom.get("wheel_radius_m") or 0.0)
    wheel_width = float(vis_geom.get("wheel_width_m") or 0.0)
    frame_length = float(vis_geom.get("frame_length_m") or 0.0)
    frame_width = float(vis_geom.get("frame_width_m") or 0.0)
    frame_height = float(vis_geom.get("frame_height_m") or 0.0)
    road_width = float(vis_geom.get("road_width_m") or 0.0)
    if road_width <= 0.0 and track > 0.0:
        road_width = float(max(track, track + max(0.0, wheel_width)))

    issues = list(vis_geom.get("issues") or [])
    warnings = list(vis_geom.get("warnings") or [])
    return {
        "wheelbase_m": wheelbase,
        "track_m": track,
        "wheel_radius_m": wheel_radius,
        "wheel_width_m": max(0.0, wheel_width),
        "frame_length_m": max(0.0, frame_length),
        "frame_width_m": max(0.0, frame_width),
        "frame_height_m": max(0.0, frame_height),
        "road_width_m": max(0.0, road_width),
        "issues": issues,
        "warnings": warnings,
    }


def _build_path_payload(
    df_main,
    t: np.ndarray,
    *,
    path_mode: str,
    v0: float,
    slalom_amp: float,
    slalom_period: float,
    turn_R: float,
    turn_dir: str,
    lateral_scale: float,
    yaw_smooth: float,
    wheelbase_m: float,
    steer_gain: float,
    steer_max_deg: float,
) -> dict:
    """Build a visualization-only path payload for the 3D component + mini-map.

    We follow the same logic as the main app's 3D visualization:
    - either integrate from model columns (vx + yaw),
    - or generate a straight/slalom/turn path.
    """
    t_np = np.asarray(t, dtype=float)
    n = len(t_np)
    if n <= 0:
        return {"x": [], "z": [], "yaw": [], "s": [], "v": [], "steer": []}

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

    # --- path mode ---
    if path_mode == "Статика (без движения)":
        pass

    elif path_mode == "По vx/yaw из модели":
        speed_col = "скорость_vx_м_с"
        yaw_col = "yaw_рад"
        try:
            v_body = df_main[speed_col].to_numpy(dtype=float) if speed_col in df_main.columns else np.full(n, float(v0), dtype=float)
            yaw = df_main[yaw_col].to_numpy(dtype=float) if yaw_col in df_main.columns else np.zeros(n, dtype=float)
        except Exception:
            v_body = np.full(n, float(v0), dtype=float)
            yaw = np.zeros(n, dtype=float)
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
        z[:] = 0.0
        yaw[:] = 0.0

    elif path_mode == "Слалом":
        vx[:] = float(v0)
        # lateral (z) oscillation
        z = float(slalom_amp) * np.sin(2.0 * np.pi * t_np / max(1e-6, float(slalom_period)))
        vz = float(slalom_amp) * (2.0 * np.pi / max(1e-6, float(slalom_period))) * np.cos(
            2.0 * np.pi * t_np / max(1e-6, float(slalom_period))
        )
        x = np.cumsum(vx * dt)
        x = x - x[0]
        yaw = np.arctan2(vz, np.maximum(vx, 1e-6))

    elif path_mode == "Поворот (радиус)":
        R = float(max(1e-6, float(turn_R)))
        dir_left = str(turn_dir).strip().lower().startswith("в")  # 'влево'
        sign = 1.0 if dir_left else -1.0
        vx[:] = float(v0)
        omega = (float(v0) / R) * sign
        yaw = omega * (t_np - t_np[0])
        x = R * np.sin(yaw)
        z = sign * R * (1.0 - np.cos(yaw))
        # v components (approx)
        vx = float(v0) * np.cos(yaw)
        vz = float(v0) * np.sin(yaw) * sign

    else:
        # fallback: straight
        vx[:] = float(v0)
        x = np.cumsum(vx * dt)
        x = x - x[0]
        z[:] = 0.0
        yaw[:] = 0.0

    # apply visualization lateral scale (helps when integrating ay)
    z = z * float(lateral_scale)

    # yaw from vel direction if not explicitly meaningful
    if path_mode not in ("Поворот (радиус)", "По vx/yaw из модели"):
        yaw = np.arctan2(vz * float(lateral_scale), np.maximum(vx, 1e-6))

    # smooth yaw to make camera nicer
    if n >= 3 and float(yaw_smooth) > 0.0:
        a = float(yaw_smooth)
        for i in range(1, n):
            yaw[i] = (1 - a) * yaw[i - 1] + a * yaw[i]

    # traveled distance
    vabs = np.sqrt(vx * vx + (vz * float(lateral_scale)) * (vz * float(lateral_scale)))
    s = np.cumsum(vabs * dt)
    s = s - s[0]

    # Steering angle (kinematic bicycle) from yaw_rate
    if n >= 3:
        yaw_u = np.unwrap(yaw)
        yaw_rate = np.gradient(yaw_u, t_np)
    else:
        yaw_rate = np.zeros(n, dtype=float)

    steer = np.arctan2(float(wheelbase_m) * yaw_rate, np.maximum(vabs, 0.1))
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


def render_animation_cockpit_web() -> None:
    st.title("🎛️ Animation Cockpit (web) — синхронная multi‑view анимация")
    st.caption(
        "Один общий таймлайн управляет **2D механикой**, **3D машинкой** и **живыми панелями** (2×2 теплокарта). "
        "Синхронизация делается через localStorage — плавно и без серверных перерисовок."
    )

    dirs = _default_npz_dirs()
    if not dirs:
        st.warning("Не найдены папки с NPZ. Сначала выполните экспорт (NPZ bundle).")
        return

    # Sidebar (1/2): dataset + basic units + playhead
    with st.sidebar:
        st.subheader("Данные")
        base_dir = st.selectbox(
            "Папка с NPZ",
            options=[str(p) for p in dirs],
            index=0,
            key="anim_base_dir",
            help="Папки auto-экспорта (workspace/exports и аналоги).",
        )
        files = sorted(Path(base_dir).glob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            st.warning("В папке нет NPZ")
            return
        pick = st.selectbox(
            "NPZ файл",
            options=[str(p) for p in files],
            index=0,
            key="anim_pick_npz",
            help="Выберите выгрузку прогона. Для auto-follow используйте anim_latest.npz.",
        )

        st.subheader("Единицы и ноль")
        dist_unit = st.selectbox("Ед. расстояний", options=["mm", "m"], index=0, key="anim_dist_unit")
        angle_unit = st.selectbox("Ед. углов", options=["deg", "rad"], index=0, key="anim_angle_unit")
        zero_baseline = st.checkbox(
            "Нулевая база (дорога=0, статика=0)",
            value=True,
            key="anim_zero_baseline",
            help=(
                "Если включено — позиционные сигналы приводятся к нулю относительно статики/нулевой дороги. "
                "Это делает сравнение визуально честным."
            ),
        )

        st.subheader("Таймлайн")
        fps_browser = st.slider(
            "Плавность (FPS в браузере)",
            min_value=10,
            max_value=60,
            value=30,
            step=5,
            key="anim_fps_browser",
            help=(
                "Это НЕ FPS симуляции. Это частота обновления playhead в localStorage, "
                "по которой 2D/3D панели двигаются синхронно."
            ),
        )
        sync_to_server = st.checkbox(
            "Синхронизировать графики с сервером",
            value=False,
            key="anim_sync_server",
            help=(
                "Если включить — playhead будет иногда отправлять положение на сервер Streamlit, "
                "чтобы можно было двигать курсоры на Plotly/таблицах. "
                "Но это может ухудшать плавность."
            ),
        )
        send_hz = 1 if sync_to_server else 0

    cache_deps = collect_visual_cache_dependencies(pick, context="Animation Cockpit NPZ cache")
    bun = _load_npz(pick, cache_deps)
    tables = bun.get("tables") if isinstance(bun, dict) else {}
    meta = bun.get("meta") if isinstance(bun, dict) else {}
    visual_contract = bun.get("visual_contract") if isinstance(bun, dict) else {}
    road_sidecar_wheels = bun.get("road_sidecar_wheels") if isinstance(bun, dict) else {}
    if not isinstance(tables, dict) or not tables:
        st.error("NPZ не содержит таблиц")
        return
    df_main = tables.get("main") or tables.get("full")
    if df_main is None or df_main.empty:
        st.error("В NPZ нет таблицы main/full")
        return

    path = Path(pick).expanduser().resolve()
    dataset_id = path.stem
    bundle_cache_deps = bun.get("cache_deps") if isinstance(bun, dict) else {}
    if not isinstance(bundle_cache_deps, dict) or not bundle_cache_deps:
        bundle_cache_deps = collect_visual_cache_dependencies(path, meta=meta if isinstance(meta, dict) else {}, context="Animation Cockpit NPZ")

    # Defaults from strict nested meta_json.geometry + main columns (speed/yaw)
    geom0 = _infer_geometry_from_meta(meta if isinstance(meta, dict) else {})
    wb0 = float(geom0.get("wheelbase_m") or 0.0)
    tr0 = float(geom0.get("track_m") or 0.0)
    rr0 = float(geom0.get("wheel_radius_m") or 0.0)
    rw0 = float(geom0.get("wheel_width_m") or 0.0)
    fl0 = float(geom0.get("frame_length_m") or 0.0)
    fw0 = float(geom0.get("frame_width_m") or 0.0)
    fh0 = float(geom0.get("frame_height_m") or 0.0)

    legacy_speed_cols = [c for c in ("vx_м_с", "v_м_с", "speed_m_s") if c in df_main.columns]
    legacy_yaw_cols = [c for c in ("рыскание_yaw_рад", "yaw_rad", "psi_рад", "курс_рад") if c in df_main.columns]

    speed_col = "скорость_vx_м_с" if "скорость_vx_м_с" in df_main.columns else None
    yaw_col = "yaw_рад" if "yaw_рад" in df_main.columns else None
    has_model_path = bool(speed_col and yaw_col)

    v0_def = 10.0
    try:
        if speed_col:
            v0_def = float(np.nanmedian(df_main[speed_col].to_numpy(dtype=float)))
            if not np.isfinite(v0_def):
                v0_def = 10.0
    except Exception:
        v0_def = 10.0

    if legacy_speed_cols or legacy_yaw_cols:
        legacy_cols = legacy_speed_cols + legacy_yaw_cols
        msg = (
            "Animation Cockpit нашёл legacy-колонки "
            + ", ".join(legacy_cols)
            + "; они не используются. Нужны канонические df_main-ключи: скорость_vx_м_с и yaw_рад."
        )
        logger.warning(msg)
        st.warning(msg)

    contract_msgs = []
    contract_msgs.extend(list((meta or {}).get("_geometry_contract_issues") or []))
    contract_msgs.extend(list(geom0.get("issues") or []))
    contract_msgs.extend(list(geom0.get("warnings") or []))
    if contract_msgs:
        uniq_msgs = []
        seen_msgs = set()
        for _m in contract_msgs:
            s = str(_m)
            if s in seen_msgs:
                continue
            seen_msgs.add(s)
            uniq_msgs.append(s)
        st.warning("Geometry contract warnings:\n- " + "\n- ".join(uniq_msgs[:8]))
        if len(uniq_msgs) > 8:
            st.caption(f"Ещё предупреждений по geometry contract: {len(uniq_msgs) - 8}")

    if rw0 <= 0.0:
        msg = (
            "wheel_width_m отсутствует в meta_json.geometry → ширина колеса по умолчанию отключена (0.0 м, без скрытого 0.22). "
            "Можно задать явное значение вручную только для визуализации."
        )
        logger.warning(msg)
        st.warning(msg)
    missing_frame_dims = [name for name, value in (("frame_length_m", fl0), ("frame_width_m", fw0), ("frame_height_m", fh0)) if value <= 0.0]
    if missing_frame_dims:
        msg = (
            "В meta_json.geometry отсутствуют габариты рамы/кузова "
            + ", ".join(missing_frame_dims)
            + ". Web 3D не должен дорисовывать их скрытыми дефолтами; задайте их в base/exporter."
        )
        logger.warning(msg)
        st.warning(msg)

    # Sidebar (2/2): viz + trajectory + heatmap
    with st.sidebar:
        st.subheader("Визуализация")
        h_anim = st.slider("Высота 2D/3D", 380, 980, 620, 10, key="anim_h_anim")

        show_minimap = st.checkbox(
            "Показывать mini-map (траектория)",
            value=True,
            key="anim_show_minimap",
            help="2D карта пути: показывает поворот/радиус, скорость и позволяет перематывать клик/drag.",
        )
        h_minimap = st.slider("Высота mini-map", 240, 740, 360, 10, key="anim_h_minimap")
        h_heat = st.slider("Высота теплокарты", 220, 520, 320, 10, key="anim_h_heat")

        st.markdown("—")
        with st.expander("Профиль дороги (вперёд)", expanded=True):
            show_profile = st.checkbox(
                "Показывать профиль дороги",
                value=True,
                key="anim_show_road_profile",
                help="График высоты дороги по дистанции (Δs, м) для всех 4 колёс. "
                     "Линия x=0 — положение CG, пунктирные линии — фронт/тыл (колёсная база). "
                     "Drag по графику перемещает общий playhead (без перезапуска сервера).",
            )
            h_profile = st.slider(
                "Высота панели профиля, px",
                min_value=160,
                max_value=520,
                value=220,
                step=10,
                key="anim_h_road_profile",
                help="Высота канваса профиля дороги. При уменьшении окна лучше поднять значение.",
            )
            cpr1, cpr2 = st.columns(2)
            with cpr1:
                win_back_m = st.slider(
                    "Окно назад, м",
                    min_value=1.0,
                    max_value=40.0,
                    value=8.0,
                    step=0.5,
                    key="anim_road_profile_back_m",
                )
            with cpr2:
                win_ahead_m = st.slider(
                    "Окно вперёд, м",
                    min_value=5.0,
                    max_value=120.0,
                    value=25.0,
                    step=1.0,
                    key="anim_road_profile_ahead_m",
                )
            y_exag = st.slider(
                "Вертикальное преувеличение (y×)",
                min_value=0.0,
                max_value=10.0,
                value=1.5,
                step=0.1,
                key="anim_road_profile_y_exag",
                help="Увеличивает читаемость мелких неровностей. Значение >1 усиливает профиль по вертикали.",
            )


        with st.expander("3D: отображение и камера", expanded=True):
            geo_multi_view = st.checkbox(
                "Multi-view (ISO + TOP + FRONT + SIDE)",
                value=True,
                key="anim_3d_multi_view",
                help="Одна 3D‑панель показывает сразу 4 вида (как в CAD/HMI).",
            )
            geo_camera_follow = st.checkbox(
                "Камера: следовать за машинкой",
                value=False,
                key="anim_3d_camera_follow",
                help="Камера держит машинку в центре — визуально дорога 'бежит' навстречу.",
            )
            geo_show_road_mesh = st.checkbox(
                "Показывать сетку дороги",
                value=True,
                key="anim_3d_show_road_mesh",
                help="Сетка подчёркивает профиль дороги и помогает видеть нулевой уровень.",
            )
            geo_road_mesh_step = st.slider(
                "Сетка дороги: шаг (разрежение)",
                min_value=1,
                max_value=40,
                value=2,
                step=1,
                key="anim_3d_road_mesh_step",
                help="Чем меньше — тем плотнее сетка, но тяжелее для браузера.",
            )
            geo_path_window = st.slider(
                "Окно отрисовки пути (точек вокруг позиции)",
                min_value=40,
                max_value=400,
                value=160,
                step=10,
                key="anim_3d_path_window",
                help="Сколько точек дороги рисовать вокруг текущего кадра.",
            )

            geo_show_trail = st.checkbox(
                "Показывать след (траекторию)",
                value=True,
                key="anim_3d_show_trail",
                help="След помогает видеть манёвры и повороты.",
            )
            geo_trail_len = st.slider(
                "След: длина (точек)",
                min_value=50,
                max_value=3000,
                value=600,
                step=50,
                key="anim_3d_trail_len",
            )
            geo_trail_step = st.slider(
                "След: шаг (разрежение)",
                min_value=1,
                max_value=20,
                value=3,
                step=1,
                key="anim_3d_trail_step",
            )

        with st.expander("Траектория/дорога (для 3D + mini-map)", expanded=True):
            st.caption(
                "Это **только визуализация** (не влияет на расчёт). Нужна, чтобы дорога "
                "двигалась и показывала повороты/манёвры." 
            )

            path_mode_options = [
                "По vx/yaw из модели",
                "Прямая",
                "Слалом",
                "Поворот (радиус)",
                "Статика (без движения)",
            ]
            default_idx = 0 if has_model_path else 1
            path_mode = st.selectbox(
                "Режим траектории",
                options=path_mode_options,
                index=int(default_idx),
                key="anim_path_mode",
                help=(
                    "Если в данных есть скорость и yaw — выбирайте 'По vx/yaw из модели'. "
                    "Иначе используйте генераторы (Прямая/Слалом/Поворот)."
                ),
            )

            v0 = st.number_input(
                "Скорость v0, m/s",
                min_value=0.0,
                value=float(max(0.0, v0_def)),
                step=0.5,
                key="anim_v0",
                help="Используется для Прямой/Слалома/Поворота. Для 'По vx/yaw' берётся из данных.",
            )
            slalom_amp = st.number_input(
                "Слалом: амплитуда, m",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key="anim_slalom_amp",
            )
            slalom_period = st.number_input(
                "Слалом: период, s",
                min_value=0.2,
                value=4.0,
                step=0.1,
                key="anim_slalom_period",
            )
            turn_R = st.number_input(
                "Поворот: радиус R, m",
                min_value=0.5,
                value=40.0,
                step=1.0,
                key="anim_turn_R",
            )
            turn_dir = st.selectbox(
                "Поворот: направление",
                options=["Влево", "Вправо"],
                index=0,
                key="anim_turn_dir",
            )

            lateral_scale = st.slider(
                "Масштаб поперечного смещения (визуально)",
                min_value=0.1,
                max_value=5.0,
                value=1.0,
                step=0.1,
                key="anim_lateral_scale",
                help="Полезно, если боковое смещение слишком маленькое/большое для восприятия.",
            )
            yaw_smooth = st.slider(
                "Сглаживание yaw (визуально)",
                min_value=0.0,
                max_value=0.5,
                value=0.15,
                step=0.05,
                key="anim_yaw_smooth",
                help="Сглаживает рывки курса для более читаемой анимации.",
            )
            steer_gain = st.slider(
                "Руль: усиление (визуально)",
                min_value=0.2,
                max_value=2.0,
                value=1.0,
                step=0.1,
                key="anim_steer_gain",
            )
            steer_max_deg = st.slider(
                "Руль: ограничение, deg",
                min_value=5.0,
                max_value=45.0,
                value=25.0,
                step=1.0,
                key="anim_steer_max_deg",
            )

            st.markdown("**Геометрия 3D (м, влияет только на масштаб отрисовки)**")
            wheelbase_m = st.number_input(
                "Колёсная база L, m",
                min_value=0.5,
                value=float(wb0),
                step=0.05,
                key="anim_wheelbase_m",
                help="Берётся только из meta_json.geometry. Если bundle сломан, будет 0.0 и warning; можно поправить вручную только для visual-only режима.",
            )
            track_m = st.number_input(
                "Колея, m",
                min_value=0.0,
                value=float(tr0),
                step=0.05,
                key="anim_track_m",
                help="Берётся только из meta_json.geometry. Если bundle сломан, будет 0.0 и warning; можно поправить вручную только для visual-only режима.",
            )
            wheel_radius_m = st.number_input(
                "Радиус колеса, m",
                min_value=0.0,
                value=float(rr0),
                step=0.01,
                key="anim_wheel_radius_m",
                help="Берётся только из meta_json.geometry. При отсутствии будет 0.0 и wheel-масштаб визуально схлопнется до исправления exporter или ручного visual-only override.",
            )
            wheel_width_m = st.number_input(
                "Ширина колеса, m",
                min_value=0.0,
                value=float(rw0),
                step=0.01,
                key="anim_wheel_width_m",
                help="Берётся только из meta_json.geometry. При отсутствии скрытый дефолт не подставляется: 0.0 м = ширина отключена, можно задать вручную только для visual-only режима.",
            )
            frame_length_m = st.number_input(
                "Длина рамы / кузова, m",
                min_value=0.0,
                value=float(fl0),
                step=0.01,
                key="anim_frame_length_m",
                help="Габаритная длина тела в 3D. Это не клиренс и не положение над дорогой; берётся только из meta_json.geometry.",
            )
            frame_width_m = st.number_input(
                "Ширина рамы / кузова, m",
                min_value=0.0,
                value=float(fw0),
                step=0.01,
                key="anim_frame_width_m",
                help="Габаритная ширина тела в 3D; берётся только из meta_json.geometry.",
            )
            frame_height_m = st.number_input(
                "Высота рамы / кузова, m",
                min_value=0.0,
                value=float(fh0),
                step=0.01,
                key="anim_frame_height_m",
                help="Габаритная высота (толщина) тела в 3D. Не равна высоте над дорогой; высота над дорогой считается по результатам.",
            )

        with st.expander("Mini-map: поведение", expanded=True):
            minimap_mode = st.selectbox(
                "Режим отображения",
                options=["follow", "global"],
                index=0,
                key="anim_minimap_mode",
                help="follow — авто‑зум вокруг текущей позиции. global — весь путь целиком.",
            )
            minimap_ahead_m = st.slider(
                "Окно вперёд, m",
                min_value=10.0,
                max_value=200.0,
                value=80.0,
                step=5.0,
                key="anim_minimap_ahead",
            )
            minimap_back_m = st.slider(
                "Окно назад, m",
                min_value=5.0,
                max_value=150.0,
                value=40.0,
                step=5.0,
                key="anim_minimap_back",
            )
            minimap_points = st.slider(
                "Точек в окне",
                min_value=120,
                max_value=2400,
                value=600,
                step=40,
                key="anim_minimap_points",
            )
            minimap_grid = st.checkbox("Сетка", value=True, key="anim_minimap_grid")
            minimap_scrub = st.checkbox(
                "Перемотка кликом/drag",
                value=True,
                key="anim_minimap_scrub",
                help="Кликните по траектории, чтобы перемотать ВСЕ панели на нужный кадр.",
            )

        st.subheader("Теплокарта")
        metric = st.selectbox(
            "Сигнал",
            options=[
                "Кузов: положение z",
                "Кузов: скорость dz/dt",
                "Кузов: ускорение d²z/dt²",
                "Колесо: положение z",
                "Шток: ход",
                "Дорога: профиль",
            ],
            index=2,
            key="anim_heat_metric",
            help="2×2 = (перед/зад) × (лево/право). Цвет и цифры обновляются синхронно с playhead.",
        )
        show_text = st.checkbox(
            "Показывать числа",
            value=True,
            key="anim_heat_show_text",
            help="Показывает значения прямо в ячейках 2×2. Для скорости/ускорения видно знак и направление.",
        )
        show_sign = st.checkbox(
            "Показывать стрелки знака (↑/↓)",
            value=True,
            key="anim_heat_show_sign",
            help="Для сигналов со знаком (скорость/ускорение) показывает направление изменения.",
        )
        digits = st.slider("Округление", 1, 6, 3, 1, key="anim_heat_digits")

        st.subheader("Давление")
        p_atm = st.number_input(
            "P_ATM, Pa",
            min_value=0.0,
            value=float(P_ATM_DEFAULT),
            step=1000.0,
            key="anim_p_atm",
            help="Нужно для приведения давлений к избыточным/абсолютным (если в данных есть p).",
        )

    # Now we can extract time-series with the selected display settings.
    # Важно: это дорого на больших NPZ. Используем единый UI-кэш, чтобы не пересчитывать на каждом «чихе».
    try:
        from pneumo_solver_ui.ui_heavy_cache import cached_pickle, stable_hash

        fp = dict(bundle_cache_deps)
        key_mech = "anim_mech_" + stable_hash(
            {
                "fp": fp,
                "dist_unit": str(dist_unit),
                "angle_unit": str(angle_unit),
                "p_atm": float(p_atm),
                "zero": bool(zero_baseline),
            }
        )
        t, body, wheel, road, stroke, phi, theta = cached_pickle(
            st,
            key=key_mech,
            build=lambda: _extract_mech_arrays(
                df_main,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                p_atm=float(p_atm),
                zero_baseline=bool(zero_baseline),
                road_override=road_sidecar_wheels if isinstance(road_sidecar_wheels, dict) else {},
            ),
        )
    except Exception:
        t, body, wheel, road, stroke, phi, theta = _extract_mech_arrays(
            df_main,
            dist_unit=dist_unit,
            angle_unit=angle_unit,
            p_atm=float(p_atm),
            zero_baseline=bool(zero_baseline),
            road_override=road_sidecar_wheels if isinstance(road_sidecar_wheels, dict) else {},
        )

    if not isinstance(visual_contract, dict) or not visual_contract:
        visual_contract = _collect_visual_contract_status(
            df_main,
            meta=meta if isinstance(meta, dict) else {},
            npz_path=pick,
            context="Animation Cockpit NPZ",
        )
    road_payload = _filter_road_payload(road, visual_contract)

    if visual_contract.get("road_overlay_text"):
        st.warning(str(visual_contract["road_overlay_text"]))
    if visual_contract.get("solver_points_overlay_text"):
        st.warning(str(visual_contract["solver_points_overlay_text"]))

    # Build path + 3D geometry (keep X/Z scale consistent with dist_unit).
    dist_scale = 1000.0 if str(dist_unit).lower().strip() == "mm" else 1.0

    try:
        from pneumo_solver_ui.ui_heavy_cache import cached_pickle, stable_hash

        fp = dict(bundle_cache_deps)
        key_path = "anim_path_" + stable_hash(
            {
                "fp": fp,
                "dist_unit": str(dist_unit),
                "path_mode": str(path_mode),
                "v0": float(v0),
                "slalom_amp": float(slalom_amp),
                "slalom_period": float(slalom_period),
                "turn_R": float(turn_R),
                "turn_dir": str(turn_dir),
                "lateral_scale": float(lateral_scale),
                "yaw_smooth": float(yaw_smooth),
                "wheelbase_m": float(wheelbase_m),
                "steer_gain": float(steer_gain),
                "steer_max_deg": float(steer_max_deg),
            }
        )

        def _build_path_payload_scaled():
            pp = _build_path_payload(
                df_main,
                t,
                path_mode=str(path_mode),
                v0=float(v0),
                slalom_amp=float(slalom_amp),
                slalom_period=float(slalom_period),
                turn_R=float(turn_R),
                turn_dir=str(turn_dir),
                lateral_scale=float(lateral_scale),
                yaw_smooth=float(yaw_smooth),
                wheelbase_m=float(wheelbase_m),
                steer_gain=float(steer_gain),
                steer_max_deg=float(steer_max_deg),
            )
            # scale coordinates for 3D if user uses mm
            try:
                if dist_scale != 1.0:
                    for k in ("x", "z", "s"):
                        if k in pp and isinstance(pp[k], list):
                            pp[k] = (np.asarray(pp[k], dtype=float) * float(dist_scale)).tolist()
            except Exception:
                pass
            return pp

        path_payload = cached_pickle(st, key=key_path, build=_build_path_payload_scaled)
    except Exception:
        path_payload = _build_path_payload(
            df_main,
            t,
            path_mode=str(path_mode),
            v0=float(v0),
            slalom_amp=float(slalom_amp),
            slalom_period=float(slalom_period),
            turn_R=float(turn_R),
            turn_dir=str(turn_dir),
            lateral_scale=float(lateral_scale),
            yaw_smooth=float(yaw_smooth),
            wheelbase_m=float(wheelbase_m),
            steer_gain=float(steer_gain),
            steer_max_deg=float(steer_max_deg),
        )
        # scale coordinates for 3D if user uses mm
        try:
            if dist_scale != 1.0:
                for k in ("x", "z", "s"):
                    if k in path_payload and isinstance(path_payload[k], list):
                        path_payload[k] = (np.asarray(path_payload[k], dtype=float) * float(dist_scale)).tolist()
        except Exception:
            pass

    ring_visual = None
    try:
        _ring_spec = load_ring_spec_from_npz(pick)
        if isinstance(_ring_spec, dict) and isinstance(_ring_spec.get("segments"), list):
            ring_visual = build_ring_visual_payload_from_spec(
                _ring_spec,
                track_m=float(track_m),
                wheel_width_m=float(wheel_width_m),
                seed=int(_ring_spec.get("seed", 0) or 0),
            )
            if ring_visual:
                _nominal_prog = build_nominal_ring_progress_from_spec(_ring_spec, t)
                if _nominal_prog.get("distance_m"):
                    path_payload["s"] = list(_nominal_prog.get("distance_m") or [])
                    path_payload["v"] = list(_nominal_prog.get("v_mps") or path_payload.get("v") or [])
                path_payload = embed_path_payload_on_ring(
                    path_payload,
                    ring_visual,
                    wheelbase_m=float(wheelbase_m),
                )
    except Exception as _e_ring_visual:
        logger.warning("Animation Cockpit: ring visual payload failed: %s", _e_ring_visual)
        ring_visual = None

    geo_payload = {
        "road_mode": "track",
        "multi_view": bool(geo_multi_view),
        "camera_follow": bool(geo_camera_follow),
        "show_road_mesh": bool(geo_show_road_mesh),
        "road_mesh_step": int(geo_road_mesh_step),
        "path_window_points": int(geo_path_window),
        "show_trail": bool(geo_show_trail),
        "trail_len": int(geo_trail_len),
        "trail_step": int(geo_trail_step),
        "base_m": float(wheelbase_m) * float(dist_scale),
        "track_m": float(track_m) * float(dist_scale),
        "wheel_radius_m": float(wheel_radius_m) * float(dist_scale),
        "wheel_width_m": float(wheel_width_m) * float(dist_scale),
        "body_L_m": float(frame_length_m) * float(dist_scale),
        "body_W_m": float(frame_width_m) * float(dist_scale),
        "body_H_m": float(frame_height_m) * float(dist_scale),
        "frame_length_m": float(frame_length_m) * float(dist_scale),
        "frame_width_m": float(frame_width_m) * float(dist_scale),
        "frame_height_m": float(frame_height_m) * float(dist_scale),
        "show_suspension": bool(visual_contract.get("solver_points_complete")),
        "visual_contract": visual_contract,
        "ring_visual": ring_visual,
    }
    if ring_visual:
        _ring_meta = dict(ring_visual.get("meta") or {})
        _ring_closure = str(
            ring_visual.get("closure_policy")
            or _ring_meta.get("closure_policy")
            or ring_visual.get("source_closure_policy")
            or ""
        ).strip().lower()
        _ring_closure_label = (
            "strict_exact (шов как задан)"
            if _ring_closure == "strict_exact"
            else "closed_c1_periodic (плавное замыкание C1)"
        )
        _ring_seam_label = "шов открыт" if bool(_ring_meta.get("seam_open", False)) else "шов замкнут"
        st.info(
            f"3D ring-view: {_ring_closure_label}, {_ring_seam_label}, толстые крайние линии по сегментам, heatmap кривизны. "
            f"Длина кольца ≈ {float(ring_visual.get('ring_length_m', 0.0)):.2f} м."
        )

    # --------------------
    # Performance policy for follower panes
    # --------------------
    perf_caps = {
        "anim2d_play_fps_cap": 20,
        "minimap_play_fps_cap": 12,
        "heatmap_play_fps_cap": 10,
        "road_profile_play_fps_cap": 12,
    }

    # --------------------
    # Global playhead control
    # --------------------
    playhead_segment_ranges: list[dict] = []
    try:
        if ring_visual and isinstance(path_payload, dict) and path_payload.get("s") is not None:
            playhead_segment_ranges = build_segment_ranges_from_progress(
                ring_visual,
                path_payload.get("s") or [],
            )
    except Exception as _e_seg_tl:
        logger.warning("Animation Cockpit: playhead segment ranges failed: %s", _e_seg_tl)
        playhead_segment_ranges = []

    ph = get_playhead_ctrl_component()
    if ph is not None and len(t) > 1:
        ph(
            title="Playhead",
            time=t.tolist(),
            dataset_id=str(dataset_id),
            storage_key="pneumo_play_state",
            send_hz=int(send_hz),
            storage_hz=int(fps_browser),
            height=88,
            events=[],
            events_max=0,
            segment_ranges=playhead_segment_ranges,
            hint=(
                "▶︎/⏸ управляет всеми панелями. "
                "Цветные полосы на таймлайне = сегменты кольца. "
                "Если анимация стала дёргаться — выключите синхронизацию с сервером."
            ),
            restore_state=False,
            key=f"playhead_{dataset_id}",
            default=None,
        )
    else:
        st.info("Playhead недоступен или нет времени в данных. Панели будут статичными.")

    # --------------------
    # Multi-view: 2D + 3D
    # --------------------
    st.subheader("Multi‑view: механика и дорога")
    c2d, c3d = st.columns([1.15, 1.0], gap="small")

    with c2d:
        # Наложения (стрелки v/a) — чтобы инженер сразу видел удары/пробои и динамику по углам.
        with st.expander("Наложения 2D (стрелки скорости/ускорения)", expanded=True):
            show_v = st.checkbox(
                "Показывать скорость v (стрелки)",
                value=False,
                key="anim_overlay_show_v",
                help=(
                    "Вертикальная скорость точек (колёса/углы рамы) в виде стрелок. "
                    "Если экран перегружен — выключите." 
                ),
            )
            show_a = st.checkbox(
                "Показывать ускорение a (стрелки)",
                value=True,
                key="anim_overlay_show_a",
                help=(
                    "Вертикальное ускорение точек (колёса/углы рамы) в виде стрелок. "
                    "Очень полезно для оценки ударов, пробоев и 'клевков'."
                ),
            )

            if str(dist_unit).lower().strip() == "mm":
                _v_def, _a_def = 0.03, 0.002
                v_scale = st.slider(
                    "Масштаб v (px на 1 мм/с)",
                    0.0,
                    0.20,
                    float(_v_def),
                    0.005,
                    key="anim_overlay_v_scale",
                    help="Чем больше — тем длиннее стрелки скорости.",
                )
                a_scale = st.slider(
                    "Масштаб a (px на 1 мм/с²)",
                    0.0,
                    0.020,
                    float(_a_def),
                    0.0005,
                    key="anim_overlay_a_scale",
                    help="Чем больше — тем длиннее стрелки ускорения.",
                )
            else:
                _v_def, _a_def = 30.0, 2.0
                v_scale = st.slider(
                    "Масштаб v (px на 1 м/с)",
                    0.0,
                    200.0,
                    float(_v_def),
                    5.0,
                    key="anim_overlay_v_scale",
                    help="Чем больше — тем длиннее стрелки скорости.",
                )
                a_scale = st.slider(
                    "Масштаб a (px на 1 м/с²)",
                    0.0,
                    20.0,
                    float(_a_def),
                    0.5,
                    key="anim_overlay_a_scale",
                    help="Чем больше — тем длиннее стрелки ускорения.",
                )

        comp2d = get_mech_anim_quad_component()
        if comp2d is None:
            st.warning("Компонент mech_anim_quad недоступен (components/mech_anim_quad).")
            st.info("Проверьте, что папка components/mech_anim_quad присутствует рядом с приложением.")
        else:
            body_clearance_u = 0.0
            try:
                _clr_chunks = []
                for _c in CORNERS:
                    _bz = np.asarray((body or {}).get(_c, []), dtype=float)
                    _rz = np.asarray((road or {}).get(_c, []), dtype=float)
                    if (_bz.size == 0) or (_rz.size == 0):
                        continue
                    _n = min(_bz.size, _rz.size)
                    _d = _bz[:_n] - _rz[:_n]
                    _d = _d[np.isfinite(_d)]
                    if _d.size:
                        _clr_chunks.append(_d)
                if _clr_chunks:
                    body_clearance_u = float(np.nanmedian(np.concatenate(_clr_chunks)))
                    if not np.isfinite(body_clearance_u):
                        body_clearance_u = 0.0
            except Exception:
                body_clearance_u = 0.0
            meta2d = {
                "frame_dt_s": float(np.nanmedian(np.diff(t))) if len(t) > 2 else 0.0,
                "dist_unit": str(dist_unit),
                "dist_scale": float(dist_scale),
                "wheelbase_u": float(wheelbase_m) * float(dist_scale),
                "track_u": float(track_m) * float(dist_scale),
                "wheel_radius_u": float(wheel_radius_m) * float(dist_scale),
                "wheel_width_u": float(wheel_width_m) * float(dist_scale),
                "body_clearance_u": float(body_clearance_u),
                "visual_contract": visual_contract,
            }
            comp2d(
                title="2D механика (4 вида: перед/зад + лево/право)",
                time=t.tolist(),
                body=body,
                wheel=wheel,
                road=road_payload,
                stroke=stroke,
                phi=phi.tolist(),
                theta=theta.tolist(),
                selected=[],
                meta=meta2d,
                path=path_payload,
                show_v=bool(show_v),
                show_a=bool(show_a),
                arrow_scale_v=float(v_scale),
                arrow_scale_a=float(a_scale),
                sync_playhead=True,
                playhead_storage_key="pneumo_play_state",
                dataset_id=str(dataset_id),
                play_fps_cap=int(perf_caps.get("anim2d_play_fps_cap", 20)),
                height=int(h_anim),
                key=f"anim2d4_{dataset_id}",
                default=None,
            )

    with c3d:
        comp3d = get_mech_car3d_component()
        if comp3d is None:
            st.warning("Компонент mech_car3d недоступен (components/mech_car3d).")
        else:
            # body z center (avoid using one corner)
            zs = []
            for c in CORNERS:
                arr = np.asarray(body.get(c, []), dtype=float)
                if arr.size == len(t):
                    zs.append(arr)
            z_center = np.mean(np.vstack(zs), axis=0) if zs else np.zeros_like(t)
            comp3d(
                title="3D машинка (wireframe)",
                time=t.tolist(),
                body={"z": z_center.tolist(), "phi": phi.tolist(), "theta": theta.tolist()},
                wheel=wheel,
                road=road_payload,
                stroke=stroke,
                path=path_payload,
                geo=geo_payload,
                sync_playhead=True,
                playhead_storage_key="pneumo_play_state",
                dataset_id=str(dataset_id),
                height=int(h_anim),
                key=f"anim3d_{dataset_id}",
                default=None,
            )

    # --------------------
    # Live 2×2 heatmap (synced)
    # --------------------
    st.subheader("Живые индикаторы")

    # mini-map (optional) + heatmap side-by-side
    if bool(show_minimap):
        cmini, cheat = st.columns([1.05, 1.0], gap="small")
    else:
        cmini, cheat = None, st.container()

    if cmini is not None:
        with cmini:
            mini = get_minimap_live_component()
            if mini is None:
                st.warning("Компонент minimap_live недоступен (components/minimap_live).")
            else:
                mini(
                    title="Mini-map (траектория + манёвры)",
                    time=t.tolist(),
                    path=path_payload,
                    ring_visual=ring_visual,
                    mode=str(minimap_mode),
                    window_m_ahead=float(minimap_ahead_m) * float(dist_scale),
                    window_m_back=float(minimap_back_m) * float(dist_scale),
                    window_points=int(minimap_points),
                    show_grid=bool(minimap_grid),
                    allow_scrub=bool(minimap_scrub),
                    show_hud=True,
                    sync_playhead=True,
                    playhead_storage_key="pneumo_play_state",
                    dataset_id=str(dataset_id),
                    play_fps_cap=int(perf_caps.get("minimap_play_fps_cap", 12)),
                    height=int(h_minimap),
                    hint=(
                        "Клик/drag по траектории → перемотка ВСЕХ панелей. "
                        "HUD показывает скорость/руль/оценку радиуса поворота." 
                    ),
                    key=f"minimap_{dataset_id}",
                    default=None,
                )

    series, unit, title = _series_for_metric(
        metric,
        t=t,
        body=body,
        wheel=wheel,
        road=road,
        stroke=stroke,
        dist_unit=dist_unit,
    )
    zlo, zhi = _robust_minmax(series)

    with cheat:
        heat = get_corner_heatmap_live_component()
        if heat is None:
            st.warning("Компонент corner_heatmap_live недоступен (components/corner_heatmap_live).")
        else:
            heat(
                title=f"2×2 теплокарта — {title}",
                time=t.tolist(),
                series={c: np.asarray(series.get(c, np.zeros_like(t)), dtype=float).tolist() for c in CORNERS},
                unit=str(unit),
                zmin=float(zlo),
                zmax=float(zhi),
                show_text=bool(show_text),
                show_sign=bool(show_sign),
                digits=int(digits),
                height=int(h_heat),
                sync_playhead=True,
                playhead_storage_key="pneumo_play_state",
                dataset_id=str(dataset_id),
                play_fps_cap=int(perf_caps.get("heatmap_play_fps_cap", 10)),
                hint=(
                    "Эта панель следует за playhead. Управление — через таймлайн сверху. "
                    "Цветовая шкала фиксирована на весь интервал (robust 2..98%)."
                ),
                key=f"heat_live_{dataset_id}",
                default=None,
            )

    
    # ---- Road profile (distance window) ----
    if bool(show_profile):
        st.subheader("Профиль дороги по дистанции (вперёд)", anchor=False)
        road_profile_live = get_road_profile_live_component()
        if road_profile_live is None:
            st.warning("Компонент road_profile_live недоступен (components/road_profile_live).")
        else:
            rp_meta = {
                "dist_unit": meta2d.get("dist_unit", "m"),
                "dist_scale": meta2d.get("dist_scale", 1.0),
                "wheelbase_u": meta2d.get("wheelbase_u", 0.0),
                "visual_contract": visual_contract,
            }
            road_profile_live(
                title="Профиль дороги (Δs)",
                hint="Drag по графику → перемотка общего playhead (без server rerun).",
                time=payload_anim.get("time", []),
                road=road_payload,
                path=path_payload,
                ring_visual=ring_visual,
                meta=rp_meta,
                height=int(h_profile),
                window_m_ahead=float(win_ahead_m),
                window_m_back=float(win_back_m),
                y_exag=float(y_exag),
                allow_scrub=True,
                sync_playhead=bool(sync_playhead),
                playhead_storage_key=storage_key,
                dataset_id=dataset_id,
                play_fps_cap=int(perf_caps.get("road_profile_play_fps_cap", 12)),
            )

    st.caption(
        "Подсказка: mini‑map позволяет перематывать анимацию без серверных rerun. "
        "Следующий шаг — добавить вторую теплокарту (например давление/расход) и/или "
        "встроить схему пневматики (SVG flow) в этот же cockpit."
    )
