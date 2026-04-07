# -*- coding: utf-8 -*-
"""road_surface.py

Утилиты для world-frame дорожного профиля z(x,y) и вычисления z(t) под каждым колесом.

Зачем:
- В старых тестах road_func(t) задавался как z(t) для каждого колеса напрямую.
- Для корректной динамики контакта нужна скорость профиля в точке контакта:
  pen_dot = z_road_dot - z_w_dot (а не просто -z_w_dot).
- При движении по пространственному профилю (поворот/рыскание) z_road(t)
  становится функцией траектории: z(x(t), y(t)).

Этот модуль предоставляет:
- несколько простых параметризованных поверхностей;
- предвычисление траектории кузова (x,y,yaw,v) по заданным ax(t), ay(t)
  (кинематическое приближение);
- построение road_func(t) и road_dfunc(t) через интерполяцию по сетке времени.

Ограничения/допущения (P0, рабочие):
- Плоское движение (x,y,yaw) кинематическое, без шинной модели и без скольжения.
- yaw_rate оценивается как ay / max(v,eps), что эквивалентно ay = v*yaw_rate
  для установившегося поворота.
- Влияние крена/тангажа на положение пятна контакта по x/y не учитывается.

Модуль не зависит от Streamlit и может использоваться в self_check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple, Any, Optional

import ast
import json

import math
import numpy as np


@dataclass
class RoadSurface:
    """Поверхность дороги z(x,y) и её градиенты."""

    z_and_grad: Callable[[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray]]

    def eval(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        z, _, _ = self.z_and_grad(x, y)
        return z

    # ---- convenience: scalar API (удобно для отладки/тестов) ----
    def h(self, x: float, y: float) -> float:
        z, _, _ = self.z_and_grad(np.asarray([float(x)]), np.asarray([float(y)]))
        return float(z[0])

    def grad(self, x: float, y: float):
        _, dzdx, dzdy = self.z_and_grad(np.asarray([float(x)]), np.asarray([float(y)]))
        return float(dzdx[0]), float(dzdy[0])


def _parse_surface_spec(spec: Any) -> Dict[str, Any]:
    """Нормализовать spec дороги.

    Поддерживает:
    - dict (как есть)
    - строку JSON/py-literal (например "{\"type\":\"flat\"}")
    - короткую строку типа "flat" (интерпретируется как {"type": "flat"})
    """
    if spec is None:
        return {"type": "flat"}
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, str):
        s = spec.strip()
        if not s:
            return {"type": "flat"}
        # Попробуем JSON
        if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
            # Попробуем python literal
            try:
                obj = ast.literal_eval(s)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        # Иначе воспринимаем как type
        return {"type": s}
    # fallback
    return {"type": "flat"}


def make_surface(spec: Optional[Dict[str, Any]] = None) -> RoadSurface:
    """Создать RoadSurface из spec.

    Поддерживаемые spec['type']:
    - 'flat'
    - 'sine_x'  (волна вдоль x)
    - 'sine_y'  (волна вдоль y)
    - 'bump'    (гауссов бугорок)
    - 'ridge_x' (ступенька/гребень по x через smoothstep)
    - 'ridge_cosine_bump' (гребень под углом, half-cosine подъём 0→A)

    Если spec=None или некорректен -> flat.
    """

    spec = _parse_surface_spec(spec)

    # -----------------------------------------------------------------
    # Legacy UI schema compatibility (R59 P0): {h, w, k} vs canonical keys
    # -----------------------------------------------------------------
    # In historical UI, road surfaces were encoded as:
    #   bump/ridge_x/ridge_cosine_bump: {"type": "...", "h": <амплитуда>, "w": <ширина>, "k": <форма>}
    # while this module expects:
    #   bump:  A, sigma
    #   ridge_x: A, width
    #   ridge_cosine_bump: A, length (+ optional k)
    #
    # If we do not map these keys, UI parameters are silently ignored and
    # the simulation runs with defaults — это самообман (P0).
    t = str(spec.get("type", "flat")).strip().lower()

    # Helper: interpret legacy width "w" for gaussian bump as FWHM.
    # sigma = FWHM / (2*sqrt(2*ln2))
    _FWHM_TO_SIGMA = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))

    if t in ("bump", "gauss", "gaussian"):
        if ("A" not in spec) and ("h" in spec):
            spec["A"] = spec.get("h")
        # Prefer explicit sigma; otherwise derive it from legacy width.
        if "sigma" not in spec:
            if ("w" in spec) and (spec.get("w") is not None):
                try:
                    w = float(spec.get("w"))
                    spec["sigma"] = float(w) * _FWHM_TO_SIGMA
                except Exception:
                    pass
            elif ("width" in spec) and (spec.get("width") is not None):
                # If someone passed width for bump, treat it as sigma.
                try:
                    spec["sigma"] = float(spec.get("width"))
                except Exception:
                    pass

    if t in ("ridge_x", "step_x", "step"):
        if ("A" not in spec) and ("h" in spec):
            spec["A"] = spec.get("h")
        if ("width" not in spec) and ("w" in spec):
            spec["width"] = spec.get("w")

    if t in ("ridge_cosine_bump", "cosine_ridge", "ridge_bump"):
        if ("A" not in spec) and ("h" in spec):
            spec["A"] = spec.get("h")
        if ("length" not in spec) and ("w" in spec):
            spec["length"] = spec.get("w")
        # Keep legacy "k" (shape) as-is; the implementation below supports it.

    if t == "flat":
        def z_and_grad(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            z = np.zeros_like(x)
            return z, np.zeros_like(x), np.zeros_like(x)
        return RoadSurface(z_and_grad=z_and_grad)

    if t in ("sine_x", "sin_x"):
        A = float(spec.get("A", 0.02))
        wavelength = float(spec.get("wavelength", 1.0))
        phase = float(spec.get("phase", 0.0))
        k = 2.0 * math.pi / max(1e-9, wavelength)
        def z_and_grad(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            arg = k * x + phase
            z = A * np.sin(arg)
            dzdx = A * k * np.cos(arg)
            dzdy = np.zeros_like(z)
            return z, dzdx, dzdy
        return RoadSurface(z_and_grad=z_and_grad)

    if t in ("sine_y", "sin_y"):
        A = float(spec.get("A", 0.02))
        wavelength = float(spec.get("wavelength", 1.0))
        phase = float(spec.get("phase", 0.0))
        k = 2.0 * math.pi / max(1e-9, wavelength)
        def z_and_grad(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            arg = k * y + phase
            z = A * np.sin(arg)
            dzdx = np.zeros_like(z)
            dzdy = A * k * np.cos(arg)
            return z, dzdx, dzdy
        return RoadSurface(z_and_grad=z_and_grad)

    if t in ("bump", "gauss", "gaussian"):
        A = float(spec.get("A", 0.03))
        x0 = float(spec.get("x0", 5.0))
        y0 = float(spec.get("y0", 0.0))
        sigma = float(spec.get("sigma", 0.25))
        inv2s2 = 1.0 / (2.0 * max(1e-9, sigma) ** 2)
        def z_and_grad(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            dx = x - x0
            dy = y - y0
            r2 = dx*dx + dy*dy
            e = np.exp(-r2 * inv2s2)
            z = A * e
            dzdx = z * (-dx * (1.0 / (max(1e-9, sigma) ** 2)))
            dzdy = z * (-dy * (1.0 / (max(1e-9, sigma) ** 2)))
            return z, dzdx, dzdy
        return RoadSurface(z_and_grad=z_and_grad)

    if t in ("ridge_x", "step_x", "step"):
        # Гладкая ступенька по x: z=0 до x0, z=A после x0
        A = float(spec.get("A", 0.03))
        x0 = float(spec.get("x0", 5.0))
        width = float(spec.get("width", 0.2))  # зона сглаживания
        w = max(1e-9, width)

        def smoothstep(u):
            # u in [0,1]
            return u*u*(3.0 - 2.0*u)

        def smoothstep_grad(u):
            return 6.0*u*(1.0-u)

        def z_and_grad(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            u = (x - x0) / w + 0.5
            u_clip = np.clip(u, 0.0, 1.0)
            s = smoothstep(u_clip)
            z = A * s
            dzdx = A * smoothstep_grad(u_clip) * (1.0 / w)
            dzdy = np.zeros_like(z)
            return z, dzdx, dzdy
        return RoadSurface(z_and_grad=z_and_grad)

    if t in ("ridge_cosine_bump", "cosine_ridge", "ridge_bump"):
        # Гребень (ridge) под углом: z зависит от u = cos(theta)*x + sin(theta)*y.
        # Профиль half-cosine: 0→A на участке [u0, u0+length].
        A = float(spec.get("A", 0.03))
        angle_deg = float(spec.get("angle_deg", 0.0))
        u0 = float(spec.get("u0", 5.0))
        length = float(spec.get("length", 0.2))
        k_shape = float(spec.get("k", spec.get("shape_k", 1.0)) or 1.0)
        L = max(1e-9, length)
        th = math.radians(angle_deg)
        cth = math.cos(th)
        sth = math.sin(th)

        def z_and_grad(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            u = cth * x + sth * y
            s = (u - u0) / L
            s_clip = np.clip(s, 0.0, 1.0)
            # base = 0.5*(1 - cos(pi*s)) in [0,1]
            base = 0.5 * (1.0 - np.cos(math.pi * s_clip))

            # Shape parameter k (legacy UI): z = A * base^k
            # k=1 -> original half-cosine. k>1 -> более "крутой" подъём.
            if abs(float(k_shape) - 1.0) < 1e-12:
                z = A * base
                dzdbase = A
            else:
                z = A * np.power(base, k_shape)
                # dz/dbase = A*k*base^(k-1), define 0 at base==0 to avoid inf.
                with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                    dzdbase = A * k_shape * np.where(base > 0.0, np.power(base, k_shape - 1.0), 0.0)

            # d(base)/du = 0.5*pi/L*sin(pi*s)
            dbase_du = 0.5 * (math.pi / L) * np.sin(math.pi * s_clip)
            dzdu = dzdbase * dbase_du
            dzdx = dzdu * cth
            dzdy = dzdu * sth
            return z, dzdx, dzdy

        return RoadSurface(z_and_grad=z_and_grad)

    # fallback
    return make_surface({"type": "flat"})


@dataclass
class WorldRoadCache:
    time: np.ndarray
    z_wheels: np.ndarray      # (n,4)
    zdot_wheels: np.ndarray   # (n,4)
    x: np.ndarray
    y: np.ndarray
    yaw: np.ndarray
    v: np.ndarray


def _interp_vec(time_grid: np.ndarray, values: np.ndarray, t: float) -> np.ndarray:
    """Векторная линейная интерполяция values(t) по time_grid.

    values: (n,4)
    """
    t = float(t)
    if t <= float(time_grid[0]):
        return values[0].copy()
    if t >= float(time_grid[-1]):
        return values[-1].copy()
    # np.interp работает с 1D, поэтому по столбцам
    out = np.zeros(values.shape[1], dtype=float)
    for j in range(values.shape[1]):
        out[j] = float(np.interp(t, time_grid, values[:, j]))
    return out


def precompute_world_road(
    *,
    dt: float,
    t_end: float,
    ax_func: Callable[[float], float],
    ay_func: Callable[[float], float],
    x_pos: np.ndarray,
    y_pos: np.ndarray,
    surface: RoadSurface,
    v0: float = 0.0,
    yaw0: float = 0.0,
    x0: float = 0.0,
    y0: float = 0.0,
    eps_v: float = 0.2,
    limit_yaw_rate: float = 5.0,
) -> WorldRoadCache:
    """Предвычислить z_road(t) и dz/dt под колесами.

    Кинематика:
    v_dot = ax
    yaw_rate = clamp(ay/max(v,eps_v), -limit_yaw_rate, +limit_yaw_rate)
    x_dot = v*cos(yaw)
    y_dot = v*sin(yaw)

    Скорость точки колеса учитывает вращение вокруг ЦМ:
    v_point = v_body + omega x r_world

    Параметры eps_v/limit_yaw_rate нужны для устойчивости при v~0.
    """

    dt = float(dt)
    t_end = float(t_end)

    # Временная сетка должна быть согласована с dt интегратора.
    try:
        from .time_grid import build_time_grid
    except Exception:
        from time_grid import build_time_grid
    time = build_time_grid(dt=dt, t_end=t_end, t0=0.0, mode="floor")
    n = len(time)

    x = np.zeros(n)
    y = np.zeros(n)
    yaw = np.zeros(n)
    v = np.zeros(n)

    x[0] = float(x0)
    y[0] = float(y0)
    yaw[0] = float(yaw0)
    v[0] = float(v0)

    # интеграция (semi-implicit Euler)
    for k in range(n - 1):
        t = float(time[k])
        ax = float(ax_func(t))
        ay = float(ay_func(t))

        v_next = v[k] + ax * dt
        # не даём скорости уйти в отрицательное в кинематике
        v_next = max(0.0, v_next)

        v_for_yaw = max(eps_v, v[k])
        yaw_rate = ay / v_for_yaw
        yaw_rate = float(np.clip(yaw_rate, -limit_yaw_rate, +limit_yaw_rate))

        yaw_next = yaw[k] + yaw_rate * dt

        # позиция по текущим v,yaw (semi-implicit)
        x_next = x[k] + v_next * math.cos(yaw_next) * dt
        y_next = y[k] + v_next * math.sin(yaw_next) * dt

        v[k + 1] = v_next
        yaw[k + 1] = yaw_next
        x[k + 1] = x_next
        y[k + 1] = y_next

    # колёса в мире
    z_wheels = np.zeros((n, 4), dtype=float)
    zdot_wheels = np.zeros((n, 4), dtype=float)

    # вычисляем по шагам
    for k in range(n):
        # базовая скорость кузова
        vx = v[k] * math.cos(yaw[k])
        vy = v[k] * math.sin(yaw[k])

        v_for_yaw = max(eps_v, v[k])
        yaw_rate = float(np.clip(float(ay_func(float(time[k]))) / v_for_yaw, -limit_yaw_rate, +limit_yaw_rate))

        cy = math.cos(yaw[k])
        sy = math.sin(yaw[k])

        # body->world rotation
        # r_world = R(yaw) * [x_pos, y_pos]
        rwx = cy * x_pos - sy * y_pos
        rwy = sy * x_pos + cy * y_pos

        # точка колеса
        xw = x[k] + rwx
        yw = y[k] + rwy

        z, dzdx, dzdy = surface.z_and_grad(xw, yw)
        z_wheels[k, :] = z

        # скорость точки с учетом вращения: v_point = v_body + omega x r_world
        # omega x r = [-omega*r_y, omega*r_x]
        vpx = vx - yaw_rate * rwy
        vpy = vy + yaw_rate * rwx

        zdot = dzdx * vpx + dzdy * vpy
        zdot_wheels[k, :] = zdot

    return WorldRoadCache(time=time, z_wheels=z_wheels, zdot_wheels=zdot_wheels, x=x, y=y, yaw=yaw, v=v)


def build_road_functions_from_world_cache(cache: WorldRoadCache):
    """Построить (road_func, road_dfunc) по кэшу."""

    def road_func(t: float) -> np.ndarray:
        return _interp_vec(cache.time, cache.z_wheels, t)

    def road_dfunc(t: float) -> np.ndarray:
        return _interp_vec(cache.time, cache.zdot_wheels, t)

    return road_func, road_dfunc
