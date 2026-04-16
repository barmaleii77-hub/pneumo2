# -*- coding: utf-8 -*-
"""pneumo_solver_ui.scenario_generator

Генератор сценариев для UI:
  - дорожный профиль (в т.ч. случайная шероховатость по ISO 8608: классы A..H)
  - манёвры (ax/ay во времени) как стохастическая последовательность событий

Зачем этот модуль:
  UI (Streamlit) должен уметь «по-человечески» собирать тесты:
  - выбрать тип дороги/режим движения
  - задать скорость, длительность, вероятности/интенсивности манёвров
  - получить CSV, совместимый с opt_worker_v3_margins_energy._compile_timeseries_inputs()

Этот модуль НЕ зависит от streamlit и может использоваться в автотестах.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

import math
import numpy as np
import pandas as pd


# -----------------------------
# ISO 8608: roughness classes
# -----------------------------

# Значения в таблице ISO 8608 обычно приводятся для Gd(n0) при n0=0.1 cycles/m
# в единицах 1e-6 m^3. В UI мы используем эти значения как «встроенный пресет».
# Если нужно — пользователь может подстроить масштаб через коэффициент.

ISO8608_GD_N0_LIMITS_1E6: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    # class : (lower, upper) in 1e-6 m^3
    "A": (None, 32.0),
    "B": (32.0, 128.0),
    "C": (128.0, 512.0),
    "D": (512.0, 2048.0),
    "E": (2048.0, 8192.0),
    "F": (8192.0, 32768.0),
    "G": (32768.0, 131072.0),
    "H": (131072.0, None),
}


def iso8608_class_gd_n0(class_letter: str, *, mode: str = "mid") -> float:
    """Вернуть рекомендованное значение Gd(n0) [m^3] для класса ISO 8608.

    Параметры:
      class_letter: 'A'..'H'
      mode:
        - 'lower'  : нижняя граница (если нет — берём 0.5*upper)
        - 'upper'  : верхняя граница (если нет — берём 2*lower)
        - 'mid'    : геометрическое среднее (если граница отсутствует — 0.5*upper или 2*lower)

    Возврат:
      Gd(n0) в абсолютных единицах м^3.
    """
    c = (class_letter or "").strip().upper()
    if c not in ISO8608_GD_N0_LIMITS_1E6:
        raise ValueError(f"ISO 8608 class must be A..H, got: {class_letter!r}")
    lo, hi = ISO8608_GD_N0_LIMITS_1E6[c]

    if mode not in {"lower", "upper", "mid"}:
        raise ValueError("mode must be one of: lower, upper, mid")

    # fill missing bounds for A/H
    if lo is None and hi is None:
        raise ValueError("Invalid class bounds")
    if lo is None:
        lo = 0.5 * float(hi)
    if hi is None:
        hi = 2.0 * float(lo)

    lo = float(lo)
    hi = float(hi)

    if mode == "lower":
        gd_1e6 = lo
    elif mode == "upper":
        gd_1e6 = hi
    else:
        gd_1e6 = math.sqrt(max(lo, 1e-12) * max(hi, 1e-12))

    return float(gd_1e6) * 1e-6


@dataclass(frozen=True)
class ISO8608Spec:
    """Спецификация шероховатости по ISO 8608 для генерации профиля."""

    road_class: str = "C"
    waviness_w: float = 2.0
    n0_cyc_per_m: float = 0.1
    n_min_cyc_per_m: float = 0.011
    n_max_cyc_per_m: float = 2.83
    gd_n0_scale: float = 1.0
    gd_pick: str = "mid"  # lower|mid|upper

    def gd_n0(self) -> float:
        return iso8608_class_gd_n0(self.road_class, mode=self.gd_pick) * float(self.gd_n0_scale)


# -----------------------------
# Road profile generation
# -----------------------------


def _one_sided_psd_from_profile(z: np.ndarray, dx: float) -> Tuple[np.ndarray, np.ndarray]:
    """Оценка one-sided PSD Gd(n) для профиля z(x).

    Возвращает:
      n (cycles/m), Gd(n) (m^3)
    """
    z = np.asarray(z, dtype=float)
    z = z - float(np.mean(z))
    n_pts = int(z.size)
    if n_pts < 8:
        raise ValueError("Profile too short for PSD estimate")
    Z = np.fft.rfft(z)
    n = np.fft.rfftfreq(n_pts, d=float(dx))
    # Two-sided PSD estimate (similar to Welch w/o window): Pxx = (dx/N) * |Z|^2
    p2 = (float(dx) / float(n_pts)) * (np.abs(Z) ** 2)
    # Convert to one-sided: double all bins except DC and Nyquist (if present)
    p1 = p2.copy()
    if n_pts % 2 == 0:
        # even: last bin is Nyquist
        if p1.size > 2:
            p1[1:-1] *= 2.0
    else:
        if p1.size > 1:
            p1[1:] *= 2.0
    return n, p1


def generate_iso8608_profile(
    *,
    length_m: float,
    dx_m: float,
    spec: ISO8608Spec,
    seed: int = 1,
    enforce_z0_zero: bool = True,
    enforce_mean_zero: bool = True,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Сгенерировать 1D профиль z(x) по (упрощённой) модели ISO 8608.

    Алгоритм:
      1) формируем целевой PSD вида Gd(n)=Gd(n0)*(n/n0)^(-w)
      2) генерируем комплексный спектр со случайными фазами
      3) irfft -> профиль
      4) масштабируем профиль так, чтобы оценка PSD вблизи n0 совпала с Gd(n0)

    Это «инженерный генератор» для симуляций/оптимизации (не метрологический).
    """
    length_m = float(length_m)
    dx_m = float(dx_m)
    if not (length_m > 1e-3 and dx_m > 1e-6):
        raise ValueError("length_m and dx_m must be positive")
    n_pts = int(max(16, math.floor(length_m / dx_m) + 1))
    # Make n_pts even for cleaner Nyquist handling
    if n_pts % 2 == 1:
        n_pts += 1

    rng = np.random.default_rng(int(seed))

    n = np.fft.rfftfreq(n_pts, d=dx_m)
    df = 1.0 / (dx_m * n_pts)

    gd0 = float(spec.gd_n0())
    w = float(spec.waviness_w)
    n0 = float(spec.n0_cyc_per_m)

    # Target PSD
    G = np.zeros_like(n, dtype=float)
    mask = (n >= float(spec.n_min_cyc_per_m)) & (n <= float(spec.n_max_cyc_per_m)) & (n > 0.0)
    G[mask] = gd0 * (n[mask] / n0) ** (-w)

    # Random complex spectrum: amplitude ~ sqrt(G*df/2) * (N(0,1)+iN(0,1))
    # Later we re-scale to match Gd(n0) anyway.
    amp = np.sqrt(np.maximum(G, 0.0) * df / 2.0)
    re = rng.standard_normal(size=n.size)
    im = rng.standard_normal(size=n.size)
    X = amp * (re + 1j * im)
    X[0] = 0.0 + 0.0j
    if n_pts % 2 == 0 and X.size > 1:
        # Nyquist must be real
        X[-1] = complex(float(np.real(X[-1])), 0.0)

    # np.fft.irfft includes 1/N normalization
    z = np.fft.irfft(X, n=n_pts) * float(n_pts)
    z = np.asarray(z, dtype=float)

    if enforce_mean_zero:
        z = z - float(np.mean(z))
    if enforce_z0_zero:
        z = z - float(z[0])

    # Scale to match target Gd(n0)
    n_est, G_est = _one_sided_psd_from_profile(z, dx_m)
    # nearest bin to n0
    k0 = int(np.argmin(np.abs(n_est - n0)))
    g_est0 = float(G_est[k0]) if (0 <= k0 < G_est.size) else 0.0
    if g_est0 > 1e-18:
        scale = math.sqrt(gd0 / g_est0)
        z = z * float(scale)
    else:
        scale = 1.0

    meta = {
        "n_pts": float(n_pts),
        "dx_m": float(dx_m),
        "length_m": float(dx_m * (n_pts - 1)),
        "gd_n0_target_m3": float(gd0),
        "gd_n0_est_m3": float(g_est0),
        "scale_applied": float(scale),
        "seed": float(seed),
    }
    x = np.linspace(0.0, dx_m * (n_pts - 1), n_pts)
    return x, z, meta


def _interp_profile(x: np.ndarray, z: np.ndarray, xq: np.ndarray) -> np.ndarray:
    """Линейная интерполяция с выходом за границы -> крайние значения."""
    return np.interp(xq, x, z, left=float(z[0]), right=float(z[-1]))


def build_time_series_for_wheels(
    *,
    t: np.ndarray,
    speed_mps: float,
    wheelbase_m: float,
    left_track: Tuple[np.ndarray, np.ndarray],
    right_track: Tuple[np.ndarray, np.ndarray],
    x0_m: Optional[float] = None,
    enforce_rel0: bool = True,
) -> np.ndarray:
    """Преобразовать 2 дорожных трека z(x) -> z(t) для 4 колёс.

    Выход: массив shape=(len(t),4) в порядке [FL, FR, RL, RR].

    Примечание по нулю:
      enforce_rel0=True сдвигает каждую колонку так, что z(t0)=0.
      Это удобно для UI (нулевая дорога в момент старта).
    """
    t = np.asarray(t, dtype=float)
    v = float(speed_mps)
    L = float(wheelbase_m)
    if v <= 1e-9:
        raise ValueError("speed_mps must be > 0")

    xL, zL = left_track
    xR, zR = right_track
    xL = np.asarray(xL, dtype=float)
    zL = np.asarray(zL, dtype=float)
    xR = np.asarray(xR, dtype=float)
    zR = np.asarray(zR, dtype=float)

    # Choose x0 such that at t=0 both front and rear are inside [0, len]
    if x0_m is None:
        x0_m = float(L)
    x_front = float(x0_m) + v * t
    x_rear = x_front - L

    z_fl = _interp_profile(xL, zL, x_front)
    z_fr = _interp_profile(xR, zR, x_front)
    z_rl = _interp_profile(xL, zL, x_rear)
    z_rr = _interp_profile(xR, zR, x_rear)
    Z = np.vstack([z_fl, z_fr, z_rl, z_rr]).T

    if enforce_rel0:
        Z = Z - Z[0:1, :]
    return Z


# -----------------------------
# Maneuver generation (ax/ay)
# -----------------------------


@dataclass(frozen=True)
class ManeuverSpec:
    """Спецификация стохастических манёвров."""

    p_accel_per_s: float = 0.05
    p_brake_per_s: float = 0.05
    p_turn_per_s: float = 0.04

    ax_range: Tuple[float, float] = (0.5, 2.0)   # м/с^2
    brake_range: Tuple[float, float] = (0.8, 4.0)  # м/с^2 (модуль)
    ay_range: Tuple[float, float] = (0.5, 3.0)   # м/с^2 (модуль)

    dur_range_s: Tuple[float, float] = (0.6, 2.5)
    ramp_s: float = 0.25
    dt_event_s: float = 0.25


def _add_pulse(arr: np.ndarray, t: np.ndarray, t0: float, dur: float, amp: float, ramp: float) -> None:
    """Добавить в arr треугольно-полочный импульс с плавным фронтом/спадом."""
    t1 = t0 + max(0.0, float(dur))
    if t1 <= t0:
        return
    r = max(1e-6, float(ramp))
    # piecewise linear envelope
    # up: [t0, t0+r]
    # hold: [t0+r, t1-r]
    # down: [t1-r, t1]
    up_end = t0 + r
    down_start = t1 - r
    for i, ti in enumerate(t):
        if ti < t0 or ti > t1:
            continue
        if ti <= up_end:
            a = (ti - t0) / r
        elif ti >= down_start:
            a = (t1 - ti) / r
        else:
            a = 1.0
        if a > 0.0:
            arr[i] += float(amp) * float(a)


def generate_maneuver_time_series(
    *,
    t: np.ndarray,
    spec: ManeuverSpec,
    seed: int = 1,
    enforce_zero0: bool = True,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Сгенерировать ax(t), ay(t) как сумму случайных событий."""
    t = np.asarray(t, dtype=float)
    if t.size < 2:
        raise ValueError("t must have at least 2 points")
    rng = np.random.default_rng(int(seed))

    ax = np.zeros_like(t)
    ay = np.zeros_like(t)

    dt_event = max(0.05, float(spec.dt_event_s))
    t_grid = np.arange(float(t[0]), float(t[-1]) + 1e-9, dt_event)

    def _uniform(lo: float, hi: float) -> float:
        return float(lo) + (float(hi) - float(lo)) * float(rng.random())

    n_acc = n_brk = n_turn = 0
    for tg in t_grid:
        # accel
        if rng.random() < float(spec.p_accel_per_s) * dt_event:
            amp = _uniform(*spec.ax_range)
            dur = _uniform(*spec.dur_range_s)
            _add_pulse(ax, t, tg, dur, +amp, float(spec.ramp_s))
            n_acc += 1
        # brake
        if rng.random() < float(spec.p_brake_per_s) * dt_event:
            amp = _uniform(*spec.brake_range)
            dur = _uniform(*spec.dur_range_s)
            _add_pulse(ax, t, tg, dur, -amp, float(spec.ramp_s))
            n_brk += 1
        # turn
        if rng.random() < float(spec.p_turn_per_s) * dt_event:
            amp = _uniform(*spec.ay_range)
            sign = -1.0 if rng.random() < 0.5 else 1.0
            dur = _uniform(*spec.dur_range_s)
            _add_pulse(ay, t, tg, dur, sign * amp, float(spec.ramp_s))
            n_turn += 1

    if enforce_zero0:
        ax = ax - float(ax[0])
        ay = ay - float(ay[0])

    meta = {
        "seed": float(seed),
        "n_accel_events": float(n_acc),
        "n_brake_events": float(n_brk),
        "n_turn_events": float(n_turn),
    }
    return ax, ay, meta


# -----------------------------
# CSV helpers (compat with worker)
# -----------------------------


def write_road_csv(
    path: Path,
    t: np.ndarray,
    z4: np.ndarray,
    *,
    extra_columns: Optional[Mapping[str, Iterable[object]]] = None,
) -> Path:
    """Записать road_csv.

    Формат:
      t,z0,z1,z2,z3
    где z0..z3 — перемещения дороги под колёсами (м).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "t": np.asarray(t, dtype=float),
        "z0": np.asarray(z4[:, 0], dtype=float),
        "z1": np.asarray(z4[:, 1], dtype=float),
        "z2": np.asarray(z4[:, 2], dtype=float),
        "z3": np.asarray(z4[:, 3], dtype=float),
    })
    if extra_columns:
        for key, values in dict(extra_columns).items():
            df[str(key)] = list(values)
    df.to_csv(path, index=False)
    return path


def write_axay_csv(path: Path, t: np.ndarray, ax: np.ndarray, ay: np.ndarray) -> Path:
    """Записать axay_csv.

    Формат:
      t,ax,ay
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "t": np.asarray(t, dtype=float),
        "ax": np.asarray(ax, dtype=float),
        "ay": np.asarray(ay, dtype=float),
    })
    df.to_csv(path, index=False)
    return path


def make_time_grid(*, dt: float, t_end: float) -> np.ndarray:
    dt = float(dt)
    t_end = float(t_end)
    if dt <= 0:
        raise ValueError("dt must be > 0")
    if t_end <= 0:
        raise ValueError("t_end must be > 0")
    try:
        from .time_grid import build_time_grid
    except Exception:
        from time_grid import build_time_grid
    return build_time_grid(dt=dt, t_end=t_end, t0=0.0, mode="floor")


def generate_iso8608_road_csv(
    *,
    out_csv: Path,
    dt: float,
    t_end: float,
    speed_mps: float,
    wheelbase_m: float,
    spec: ISO8608Spec,
    dx_m: float = 0.02,
    left_right_coherence: float = 0.5,
    seed: int = 1,
) -> Tuple[Path, Dict[str, float]]:
    """Сгенерировать road_csv для теста road_profile_csv.

    left_right_coherence:
      0.0 -> левый и правый трек независимы
      1.0 -> левый=правый (идеальная корреляция)
    """
    t = make_time_grid(dt=dt, t_end=t_end)
    v = float(speed_mps)
    L = float(wheelbase_m)
    if v <= 1e-9:
        raise ValueError("speed_mps must be > 0")
    if L < 0:
        raise ValueError("wheelbase_m must be >= 0")

    # Generate profile length with запасом под wheelbase
    x_len = v * float(t[-1]) + float(L) + 5.0
    xL, zL, metaL = generate_iso8608_profile(length_m=x_len, dx_m=float(dx_m), spec=spec, seed=int(seed) * 101 + 1)
    # Right track: blend independent noise with left track
    xR, zR, metaR = generate_iso8608_profile(length_m=x_len, dx_m=float(dx_m), spec=spec, seed=int(seed) * 101 + 2)

    coh = float(left_right_coherence)
    coh = max(0.0, min(1.0, coh))
    zR = coh * zL + math.sqrt(max(0.0, 1.0 - coh * coh)) * zR

    z4 = build_time_series_for_wheels(
        t=t,
        speed_mps=v,
        wheelbase_m=L,
        left_track=(xL, zL),
        right_track=(xR, zR),
        enforce_rel0=True,
    )
    out_path = write_road_csv(out_csv, t, z4)

    meta = {
        "t_end": float(t_end),
        "dt": float(dt),
        "vx0_м_с": float(v),
        "wheelbase_m": float(L),
        "left_right_coherence": float(coh),
        **{f"L_{k}": float(vv) for k, vv in metaL.items()},
        **{f"R_{k}": float(vv) for k, vv in metaR.items()},
    }
    return out_path, meta


def generate_maneuver_csv(
    *,
    out_csv: Path,
    dt: float,
    t_end: float,
    spec: ManeuverSpec,
    seed: int = 1,
) -> Tuple[Path, Dict[str, float]]:
    t = make_time_grid(dt=dt, t_end=t_end)
    ax, ay, meta = generate_maneuver_time_series(t=t, spec=spec, seed=int(seed), enforce_zero0=True)
    out_path = write_axay_csv(out_csv, t, ax, ay)
    meta2 = {"t_end": float(t_end), "dt": float(dt), **{k: float(v) for k, v in meta.items()}}
    return out_path, meta2
