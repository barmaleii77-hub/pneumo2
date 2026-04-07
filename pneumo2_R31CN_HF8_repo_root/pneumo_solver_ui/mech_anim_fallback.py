
# -*- coding: utf-8 -*-
"""
mech_anim_fallback.py

Fallback визуализация механики (2D/3D) без Streamlit Components.

Зачем:
- в некоторых окружениях Streamlit Custom Components могут не грузиться
  (типичная ошибка: "Unrecognized component API version: 'undefined'");
- matplotlib-рендер работает офлайн и проще в установке.

Идея:
- 2D: фронтальный и боковой "срез" подвески по данным df_main.
- 3D: wireframe "машинка" + след профиля дороги по траектории (визуализация),
  используя path_payload из UI (x/z/yaw/s), если он доступен.

NOTE: это визуализация. Она НЕ влияет на расчёт ODE.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional

import math
import time as _time

import numpy as np
import streamlit as st

# Optional dependency: gives us non-blocking animation via periodic reruns.
try:
    from streamlit_autorefresh import st_autorefresh as _st_autorefresh  # type: ignore
except Exception:  # pragma: no cover
    _st_autorefresh = None


def _as_np(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def _median_dt(t: np.ndarray) -> float:
    if t.size < 2:
        return 0.01
    dt = np.diff(t)
    dt = dt[np.isfinite(dt)]
    if dt.size == 0:
        return 0.01
    return float(np.median(dt))


def _nearest_index(t: np.ndarray, x: float) -> int:
    if t.size == 0:
        return 0
    return int(np.argmin(np.abs(t - float(x))))


def _cumtrapz(y: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integral with y,t same length; returns integral with zero at t[0]."""
    y = _as_np(y)
    t = _as_np(t)
    if t.size < 2:
        return np.zeros_like(t)
    dt = np.diff(t)
    avg = 0.5 * (y[1:] + y[:-1])
    out = np.concatenate([[0.0], np.cumsum(avg * dt)])
    return out


def compute_path_from_payload(path: Optional[Dict[str, Any]], time: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Extract path arrays from path_payload used in UI 3D component.

    Expected keys in payload:
      - x: list (forward)
      - z: list (lateral)
      - yaw: list (heading)
      - s: list (arc length) [optional]

    If payload missing, returns zero arrays.
    """
    n = int(time.size)
    if not path:
        return {
            "x": np.zeros(n, dtype=float),
            "y": np.zeros(n, dtype=float),
            "yaw": np.zeros(n, dtype=float),
        }

    def _get(k: str) -> np.ndarray:
        v = path.get(k, None)
        if v is None:
            return np.zeros(n, dtype=float)
        a = _as_np(v)
        if a.size == n:
            return a
        # interpolate to time size if mismatch
        # assume provided arrays are sampled at same time grid length
        if a.size < 2:
            return np.full(n, float(a[0]) if a.size else 0.0)
        x0 = np.linspace(float(time[0]), float(time[-1]), num=a.size)
        return np.interp(time, x0, a).astype(float)

    x = _get("x")
    y = _get("z")  # payload uses x/z plane, where z is lateral
    yaw = _get("yaw")
    return {"x": x, "y": y, "yaw": yaw}


def _init_state(key: str, default: Any) -> None:
    """Initialize st.session_state[key] if missing."""
    if key not in st.session_state:
        st.session_state[key] = default

def _log_anim(event: str, **fields: Any) -> None:
    """Опциональное логирование в общий log_event, если оно прокинуто через st.session_state."""
    cb = st.session_state.get('_log_event_cb', None)
    if callable(cb):
        try:
            cb(event, **fields)
        except Exception:
            pass


def _st_pyplot(fig) -> None:
    """Совместимость Streamlit: use_container_width -> width='stretch'."""
    try:
        st.pyplot(fig, width="stretch")
    except TypeError:
        st.pyplot(fig, width='stretch')


def _playhead_idx_control(
    t: np.ndarray,
    *,
    prefix: str,
    label: str,
    default_idx: int = 0,
    show_time_caption: bool = True,
) -> int:
    """
    Общий контроллер "времени" для fallback-анимаций.

    Важно про Streamlit Session State:
    - значение виджета (slider) нельзя менять через st.session_state *после* того, как виджет создан
      в текущем прогоне скрипта — будет StreamlitAPIException.
    - поэтому авто-шаг (play) делаем так: *до* создания slider обновляем st.session_state[idx_key].

    Почему по индексу, а не по float-времени:
    - меньше риск конфликтов Session State;
    - проще делать play/pause/шаг/loop;
    - стабильнее при неравномерной сетке времени.
    """
    n = int(t.size)
    if n <= 0:
        return 0

    dt_sim = _median_dt(t)

    play_key = f"{prefix}::play"          # non-widget state
    last_key = f"{prefix}::last_wall"     # non-widget state
    idx_key = f"{prefix}::idx"            # slider widget
    loop_key = f"{prefix}::loop"          # checkbox widget
    speed_key = f"{prefix}::speed"        # selectbox widget
    fps_key = f"{prefix}::fps"            # slider widget
    tick_key = f"{prefix}::autorefresh"   # st_autorefresh widget
    tick_last_key = f"{prefix}::autorefresh_last"  # non-widget state

    # Non-widget state: safe to init directly.
    _init_state(play_key, False)
    _init_state(last_key, float(_time.time()))
    _init_state(tick_last_key, -1)

    # Widget-backed state init (before widget creation).
    if idx_key not in st.session_state:
        st.session_state[idx_key] = int(default_idx)

    # --- controls row ---
    c1, c2, c3, c4, c5 = st.columns([1.0, 1.0, 2.0, 2.0, 2.0])
    with c1:
        if st.button("▶", key=f"{prefix}::btn_play", help="Play"):
            st.session_state[play_key] = True
            st.session_state[last_key] = float(_time.time())
            _log_anim("anim_play", prefix=prefix)
    with c2:
        if st.button("⏸", key=f"{prefix}::btn_pause", help="Pause"):
            st.session_state[play_key] = False
            _log_anim("anim_pause", prefix=prefix)
    with c3:
        speeds = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
        st.selectbox("Скорость (x)", speeds, index=2, key=speed_key)  # default = 1.0x
    with c4:
        # Streamlit-анимация = rerun всего скрипта. Дефолт держим низким, иначе выглядит как "вечный расчёт".
        st.slider("FPS", min_value=2, max_value=30, value=8, step=1, key=fps_key)
    with c5:
        st.checkbox("Loop", value=False, key=loop_key)

    # --- autorefresh tick (чтобы play работал без while True) ---
    tick = None
    if bool(st.session_state.get(play_key)):
        fps = int(st.session_state.get(fps_key, 4) or 8)
        fps = max(1, min(60, fps))
        if _st_autorefresh is None:
            st.warning("Для режима Play нужен пакет streamlit-autorefresh.")
            st.session_state[play_key] = False
            _log_anim("anim_autorefresh_missing", prefix=prefix)
        else:
            # Авто‑троттлинг. Если реальная длительность прогона/рендера > желаемого
            # интервала, то st_autorefresh начнёт копить rerun'ы и UI может выглядеть
            # как "повисший". Поэтому увеличиваем интервал до фактического (с запасом).
            base_interval_ms = int(max(15, 1000 / max(1.0, float(fps))))
            now_s = float(_time.time())
            last_s = float(st.session_state.get(last_key, now_s) or now_s)
            dt_wall_ms = int(max(0.0, now_s - last_s) * 1000.0)
            interval_ms = base_interval_ms
            if dt_wall_ms > int(base_interval_ms * 1.25):
                interval_ms = min(1500, dt_wall_ms)
            tick = int(_st_autorefresh(interval=int(interval_ms), key=tick_key) or 0)

    # --- advance if playing (IMPORTANT: must happen BEFORE slider widget instantiation) ---
    if bool(st.session_state.get(play_key)) and n > 1 and tick is not None:
        last_tick = int(st.session_state.get(tick_last_key, -1) or -1)
        if tick != last_tick:
            st.session_state[tick_last_key] = int(tick)
            now = float(_time.time())
            last = float(st.session_state.get(last_key, now))
            dt_wall = max(0.0, now - last)
            st.session_state[last_key] = now

            speed = float(st.session_state.get(speed_key, 1.0) or 1.0)

            # Реальное время: двигаем playhead по wall-clock (dt_wall), а индекс получаем
            # через searchsorted. При маленьком dt_sim будут пропуски кадров (это нормально),
            # зато скорость будет 1:1.
            idx = int(st.session_state.get(idx_key, 0) or 0)
            idx = max(0, min(n - 1, idx))
            t_cur = float(t[idx])
            t_new = t_cur + dt_wall * max(0.0, speed)

            # loop/stop
            if t_new >= float(t[-1]):
                if bool(st.session_state.get(loop_key)) and n > 1:
                    t0 = float(t[0])
                    dur = float(t[-1] - t[0])
                    if dur > 0:
                        t_new = ((t_new - t0) % dur) + t0
                    else:
                        t_new = float(t0)
                else:
                    t_new = float(t[-1])
                    st.session_state[play_key] = False
                    _log_anim("anim_stop_end", prefix=prefix)

            # convert time -> index
            import numpy as _np
            idx_new = int(_np.searchsorted(t, t_new, side="left"))
            idx_new = max(0, min(n - 1, idx_new))
            st.session_state[idx_key] = int(idx_new)

    # --- main slider (index) ---
    # NOTE: do NOT set value=... when we also rely on st.session_state[idx_key].
    st.slider(label, min_value=0, max_value=n - 1, step=1, key=idx_key)
    idx = int(st.session_state.get(idx_key, 0) or 0)
    idx = max(0, min(n - 1, idx))

    if show_time_caption:
        st.caption(f"t = {float(t[idx]):.4f} s (dt≈{dt_sim:.4g}s, N={n})")

    return idx



def render_mech2d_fallback(
    *,
    time: List[float],
    body: Dict[str, List[float]],
    wheel: Dict[str, List[float]],
    road: Dict[str, List[float]],
    stroke: Dict[str, List[float]],
    wheelbase_m: float,
    track_m: float,
    L_stroke_m: float,
    dataset_id: str = "",
    idx: int | None = None,
    show_controls: bool = True,
    log_cb: Optional[Any] = None,
) -> tuple[float, list[str]]:
    """2D фронт/бок: matplotlib snapshot + play/pause (fallback, без компонентов)."""
    import matplotlib.pyplot as plt

    if log_cb is not None:
        # Позволяем UI-приложению прокидывать единый callback логирования,
        # чтобы в логах было видно, что делает анимация.
        st.session_state["_log_event_cb"] = log_cb

    t = _as_np(time)
    if t.size == 0:
        st.info("Нет данных для 2D fallback.")
        return (0.0, ["ЛП", "ПП", "ЛЗ", "ПЗ"])

    # Playhead (индекс по времени) — отдельный для 2D, чтобы не конфликтовать ключами с 3D.
    prefix = f"mech2d_fb::{dataset_id}" if dataset_id else "mech2d_fb"
    if idx is None:
        idx = _playhead_idx_control(
            t,
            prefix=f"mech2d_fb_{dataset_id}",
            label="Время",
            init_idx=max(0, min(len(t) - 1, int(len(t) * 0.30))),
            dt_s=float(np.median(np.diff(t))) if len(t) > 1 else 0.01,
        )
    else:
        try:
            idx = int(idx)
        except Exception:
            idx = 0
        idx = max(0, min(len(t) - 1, idx))
        if show_controls:
            st.caption(f"t = {float(t[idx]):.3f} s")

    # corners: ЛП, ПП, ЛЗ, ПЗ
    def g(d: Dict[str, List[float]], k: str) -> float:
        arr = d.get(k, None)
        if arr is None:
            return float("nan")
        a = _as_np(arr)
        if a.size == 0:
            return float("nan")
        return float(a[min(idx, a.size - 1)])

    # side averages (front/rear)
    body_L = 0.5 * (g(body, "ЛП") + g(body, "ЛЗ"))
    body_R = 0.5 * (g(body, "ПП") + g(body, "ПЗ"))
    wheel_L = 0.5 * (g(wheel, "ЛП") + g(wheel, "ЛЗ"))
    wheel_R = 0.5 * (g(wheel, "ПП") + g(wheel, "ПЗ"))
    road_L = 0.5 * (g(road, "ЛП") + g(road, "ЛЗ"))
    road_R = 0.5 * (g(road, "ПП") + g(road, "ПЗ"))

    body_F = 0.5 * (g(body, "ЛП") + g(body, "ПП"))
    body_Re = 0.5 * (g(body, "ЛЗ") + g(body, "ПЗ"))
    wheel_F = 0.5 * (g(wheel, "ЛП") + g(wheel, "ПП"))
    wheel_Re = 0.5 * (g(wheel, "ЛЗ") + g(wheel, "ПЗ"))
    road_F = 0.5 * (g(road, "ЛП") + g(road, "ПП"))
    road_Re = 0.5 * (g(road, "ЛЗ") + g(road, "ПЗ"))

    # strokes
    s_lp = g(stroke, "ЛП")
    s_pp = g(stroke, "ПП")
    s_lz = g(stroke, "ЛЗ")
    s_pz = g(stroke, "ПЗ")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # ---- front view (y-z) ----
    ax = axes[0]
    yL = +0.5 * float(track_m)
    yR = -0.5 * float(track_m)
    ax.set_title("Front view (крен): средние по осям")
    ax.plot([yL, yR], [road_L, road_R], linestyle="--", linewidth=1.5, label="road")
    ax.plot([yL, yR], [wheel_L, wheel_R], marker="o", linewidth=2, label="wheel")
    ax.plot([yL, yR], [body_L, body_R], marker="s", linewidth=2, label="body")
    ax.plot([yL, yL], [wheel_L, body_L], linewidth=1.0)
    ax.plot([yR, yR], [wheel_R, body_R], linewidth=1.0)
    ax.set_xlabel("Y (м)")
    ax.set_ylabel("Z (м)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    # ---- side view (x-z) ----
    ax2 = axes[1]
    xF = +0.5 * float(wheelbase_m)
    xRr = -0.5 * float(wheelbase_m)
    ax2.set_title("Side view (тангаж): средние по сторонам")
    ax2.plot([xRr, xF], [road_Re, road_F], linestyle="--", linewidth=1.5, label="road")
    ax2.plot([xRr, xF], [wheel_Re, wheel_F], marker="o", linewidth=2, label="wheel")
    ax2.plot([xRr, xF], [body_Re, body_F], marker="s", linewidth=2, label="body")
    ax2.plot([xF, xF], [wheel_F, body_F], linewidth=1.0)
    ax2.plot([xRr, xRr], [wheel_Re, body_Re], linewidth=1.0)
    ax2.set_xlabel("X (м)")
    ax2.set_ylabel("Z (м)")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="best")

    plt.tight_layout()
    _st_pyplot(fig)

    # quick numeric panel (roll/pitch + strokes)
    try:
        phi_est = math.atan2((body_L - body_R), max(float(track_m), 1e-9))
        theta_est = -math.atan2((body_F - body_Re), max(float(wheelbase_m), 1e-9))
        st.caption(
            f"t={float(t[idx]):.3f} s | крен φ≈{math.degrees(phi_est):+.2f}° (φ>0: левый борт вверх) | "
            f"тангаж θ≈{math.degrees(theta_est):+.2f}° (θ>0: нос вниз) | "
            f"stroke (м): ЛП={s_lp:.3f}, ПП={s_pp:.3f}, ЛЗ={s_lz:.3f}, ПЗ={s_pz:.3f} | "
            f"ход штока L={float(L_stroke_m):.3f} м"
        )
    except Exception:
        st.caption(
            f"stroke (м): ЛП={s_lp:.3f}, ПП={s_pp:.3f}, ЛЗ={s_lz:.3f}, ПЗ={s_pz:.3f} | ход штока L={float(L_stroke_m):.3f} м"
        )

    # Возвращаем выбранное время и "выбранные" углы (fallback не умеет интерактивный selection).
    return (float(t[idx]), ["ЛП", "ПП", "ЛЗ", "ПЗ"])


def render_mech3d_fallback(
    *,
    time: List[float],
    body: Dict[str, List[float]],
    wheel: Dict[str, List[float]],
    road: Dict[str, List[float]],
    phi: List[float],
    theta: List[float],
    path: Optional[Dict[str, Any]],
    wheelbase_m: float,
    track_m: float,
    dataset_id: str = "",
    log_cb: Optional[Any] = None,
) -> tuple[float, list[str]]:
    """3D wireframe fallback (matplotlib)."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    if log_cb is not None:
        st.session_state["_log_event_cb"] = log_cb

    t = _as_np(time)
    if t.size == 0:
        st.info("Нет данных для 3D fallback.")
        return (0.0, ["ЛП", "ПП", "ЛЗ", "ПЗ"])

    # Playhead (индекс по времени) — отдельный для 3D.
    prefix = f"mech3d_fb::{dataset_id}" if dataset_id else "mech3d_fb"
    idx = _playhead_idx_control(
        t,
        prefix=prefix,
        label="Время (3D): индекс",
        default_idx=0,
        show_time_caption=True,
    )
    # Пояснение: в 3D мы можем рисовать не только положение в точке t,
    # но и «след колёс» по дороге (траектория точек контакта). Это помогает увидеть,
    # что «машинка едет по дороге», а не «дорога двигается под машинкой».
    show_tracks = st.checkbox(
        "Показывать трассу дороги (след колёс)",
        value=True,
        key=f"{prefix}::show_tracks",
        help="Рисует траекторию точек контакта колёс с дорогой в мировых координатах.",
    )
    trail_sec = st.slider(
        "Окно трассы (сек)",
        min_value=1.0,
        max_value=60.0,
        value=15.0,
        step=1.0,
        key=f"{prefix}::trail_sec",
        help="Сколько секунд вокруг текущего времени показывать (меньше = быстрее).",
    )


    # path arrays (x,y,yaw) for "машинка едет по дороге"
    p = compute_path_from_payload(path, t)
    x_c = float(p["x"][idx])
    y_c = float(p["y"][idx])
    yaw = float(p["yaw"][idx])

    # corner offsets in body frame
    xF = +0.5 * float(wheelbase_m)
    xRr = -0.5 * float(wheelbase_m)
    yL = +0.5 * float(track_m)
    yR = -0.5 * float(track_m)

    corners = {
        "ЛП": (xF, yL),
        "ПП": (xF, yR),
        "ЛЗ": (xRr, yL),
        "ПЗ": (xRr, yR),
    }

    def rot(x: float, y: float, a: float) -> tuple[float, float]:
        ca = math.cos(a)
        sa = math.sin(a)
        return (ca * x - sa * y, sa * x + ca * y)

    def g(d: Dict[str, List[float]], k: str) -> float:
        arr = d.get(k, None)
        if arr is None:
            return float("nan")
        a = _as_np(arr)
        if a.size == 0:
            return float("nan")
        return float(a[min(idx, a.size - 1)])

    # build points
    body_pts = {}
    wheel_pts = {}
    road_pts = {}
    for k, (ox, oy) in corners.items():
        rx, ry = rot(float(ox), float(oy), float(yaw))
        X = x_c + rx
        Y = y_c + ry
        body_pts[k] = (X, Y, g(body, k))
        wheel_pts[k] = (X, Y, g(wheel, k))
        road_pts[k] = (X, Y, g(road, k))

    fig = plt.figure(figsize=(9, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title("3D fallback (wireframe) — положение в момент t")

    # --- След колёс / трасса дороги ---
    # Это не «дорога двигается», а история мировых координат точек контакта колёс с дорогой.
    if show_tracks:
        try:
            t0 = float(t[idx])
            t_min = t0 - float(trail_sec)
            t_max = t0 + float(trail_sec)
            mask = (t >= t_min) & (t <= t_max)
            ii = np.nonzero(mask)[0]
            if ii.size < 2:
                ii = np.arange(t.size)
            # ограничим число точек, чтобы не тормозить при Play
            if ii.size > 2500:
                step = int(math.ceil(ii.size / 2500))
                ii = ii[::step]

            x_arr = _as_np(p.get("x", []))
            y_arr = _as_np(p.get("y", []))
            yaw_arr = _as_np(p.get("yaw", []))
            if x_arr.size == t.size and y_arr.size == t.size and yaw_arr.size == t.size:
                ca = np.cos(yaw_arr)
                sa = np.sin(yaw_arr)
                for k, (ox, oy) in corners.items():
                    zr = _as_np(road.get(k, []))
                    if zr.size == 0:
                        continue
                    if zr.size != t.size:
                        # грубая подгонка размера (если road пришёл другой длины)
                        zr = np.interp(t, np.linspace(float(t[0]), float(t[-1]), int(zr.size)), zr)
                    X = x_arr + ca * float(ox) - sa * float(oy)
                    Y = y_arr + sa * float(ox) + ca * float(oy)
                    ax.plot(X[ii], Y[ii], zr[ii], linewidth=1.0, linestyle=":")
        except Exception:
            pass


    # draw road points
    for k in ["ЛП", "ПП", "ЛЗ", "ПЗ"]:
        X, Y, Zr = road_pts[k]
        ax.scatter([X], [Y], [Zr], marker="x")

    # draw wheels/body and links
    for k in ["ЛП", "ПП", "ЛЗ", "ПЗ"]:
        Xw, Yw, Zw = wheel_pts[k]
        Xb, Yb, Zb = body_pts[k]
        ax.scatter([Xw], [Yw], [Zw], marker="o")
        ax.scatter([Xb], [Yb], [Zb], marker="s")
        ax.plot([Xw, Xb], [Yw, Yb], [Zw, Zb], linewidth=1.0)

    # connect body rectangle
    order = ["ЛП", "ПП", "ПЗ", "ЛЗ", "ЛП"]
    ax.plot(
        [body_pts[k][0] for k in order],
        [body_pts[k][1] for k in order],
        [body_pts[k][2] for k in order],
        linewidth=2.0,
    )

    # connect wheel rectangle
    ax.plot(
        [wheel_pts[k][0] for k in order],
        [wheel_pts[k][1] for k in order],
        [wheel_pts[k][2] for k in order],
        linewidth=1.5,
        linestyle="--",
    )

    ax.set_xlabel("X (м)")
    ax.set_ylabel("Y (м)")
    ax.set_zlabel("Z (м)")
    ax.grid(True, alpha=0.2)

    # equal-ish scaling
    try:
        xs = [v[0] for v in body_pts.values()] + [v[0] for v in wheel_pts.values()]
        ys = [v[1] for v in body_pts.values()] + [v[1] for v in wheel_pts.values()]
        zs = [v[2] for v in body_pts.values()] + [v[2] for v in wheel_pts.values()]
        xmid = 0.5 * (max(xs) + min(xs))
        ymid = 0.5 * (max(ys) + min(ys))
        zmid = 0.5 * (max(zs) + min(zs))
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1e-6)
        ax.set_xlim(xmid - 0.6 * span, xmid + 0.6 * span)
        ax.set_ylim(ymid - 0.6 * span, ymid + 0.6 * span)
        ax.set_zlim(zmid - 0.6 * span, zmid + 0.6 * span)
    except Exception:
        pass

    _st_pyplot(fig)

    # quick status
    phi_v = float(_as_np(phi)[idx]) if len(phi) == t.size else float("nan")
    th_v = float(_as_np(theta)[idx]) if len(theta) == t.size else float("nan")
    st.caption(f"t={float(t[idx]):.3f}s | x={x_c:.2f} м, y={y_c:.2f} м, yaw={math.degrees(yaw):.1f}° | крен φ={math.degrees(phi_v):.2f}°, тангаж θ={math.degrees(th_v):.2f}°")

    return (float(t[idx]), ["ЛП", "ПП", "ЛЗ", "ПЗ"])
