#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_ui.py

Единый слой для сравнительных диаграмм (Web + Qt).

Зачем этот файл
---------------
В проекте часть UI запускается:
- через Streamlit (web)
- отдельным Qt‑окном под Windows

Обе реализации должны:
- одинаково трактовать единицы (m/mm, rad/deg, Pa→bar(g))
- одинаково обнулять «нулевую статику» (baseline)
- одинаково фиксировать шкалы (lock Y по сигналу и/или по единице)
- поддерживать матрицы Δ и N→N анализ.

Поэтому базовые функции (NPZ‑loader, baseline, resampling, locked ranges, Δ‑матрицы)
держим здесь, без зависимостей от Streamlit/Qt.

Совместимость
------------
Исторически часть кода ожидала, что `load_npz_bundle()` возвращает таблицы прямо
на верхнем уровне dict (`bundle['main']`), а новая логика хранит их в
`bundle['tables']['main']`.

Чтобы не ломать старые страницы/скрипты, `load_npz_bundle()` возвращает ОБА вида:
- `bundle['tables']` — основной источник истины
- `bundle['main']`, `bundle['p']`, ... — алиасы для совместимости

"""

from __future__ import annotations

import json
import math
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from pneumo_solver_ui.data_contract import normalize_npz_meta
from pneumo_solver_ui.visual_contract import collect_visual_cache_dependencies, collect_visual_contract_status, load_visual_road_sidecar
from pneumo_solver_ui.npz_anim_diagnostics import collect_npz_anim_diagnostics
from pneumo_solver_ui.geometry_acceptance_contract import collect_geometry_acceptance_from_frame

logger = logging.getLogger(__name__)


# -----------------------------
# Constants (display / conversions)
# -----------------------------

# 1 bar = 100000 Pa (definition)
BAR_PA: float = 100000.0

# Default atmospheric pressure for gauge conversion (Pa - P_ATM)
P_ATM_DEFAULT: float = 101325.0


@dataclass
class RangeSpec:
    """Y-range specification.

    Notes:
    - Web code often expects `.ymin/.ymax`
    - Some self-checks historically expect `.lo/.hi`
    """

    ymin: float
    ymax: float

    @property
    def lo(self) -> float:
        return float(self.ymin)

    @property
    def hi(self) -> float:
        return float(self.ymax)


# -----------------------------
# NPZ loading
# -----------------------------


def _npz_to_df(npz: Any, cols_key: str, values_key: str) -> pd.DataFrame:
    if cols_key not in npz or values_key not in npz:
        return pd.DataFrame()
    try:
        cols = [str(c) for c in npz[cols_key].tolist()]
        vals = np.asarray(npz[values_key])
        try:
            return pd.DataFrame(vals, columns=cols)
        except Exception:
            return pd.DataFrame(vals)
    except Exception:
        return pd.DataFrame()


def load_npz_bundle(path: str | Path) -> Dict[str, Any]:
    """Загрузить экспортированный NPZ.

    Возвращает dict:
      {
        'tables': {'main': df, 'p': df, 'q': df, 'open': df, ...},
        'meta': {...},

        # совместимость:
        'main': df, 'p': df, ...
      }

    Функция максимально tolerant к старым/урезанным NPZ.
    """

    p = Path(path).expanduser().resolve()
    npz = np.load(p, allow_pickle=True)

    # --- meta ---
    meta: Dict[str, Any] = {}
    try:
        if "meta_json" in npz:
            raw = npz["meta_json"].tolist()
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            if isinstance(raw, str):
                meta = json.loads(raw)
            elif isinstance(raw, dict):
                meta = dict(raw)
    except Exception:
        meta = {}

    try:
        meta = normalize_npz_meta(meta, log=lambda m: logger.warning("[compare_ui] %s", m))
    except Exception:
        meta = dict(meta or {})

    tables: Dict[str, pd.DataFrame] = {}

    # main
    df_main = _npz_to_df(npz, "main_cols", "main_values")
    if not df_main.empty:
        tables["main"] = df_main

    # p/q/open/debug/full (may be absent)
    for key in ["p", "q", "open", "debug", "full", "atm", "mdot"]:
        df = _npz_to_df(npz, f"{key}_cols", f"{key}_values")
        if not df.empty:
            tables[key] = df

    t_main = None
    if not df_main.empty and "время_с" in df_main.columns:
        try:
            t_main = np.asarray(df_main["время_с"], dtype=float)
        except Exception:
            t_main = None

    cache_deps = collect_visual_cache_dependencies(
        p,
        meta=meta,
        context="compare_ui NPZ",
        log=lambda m: logger.warning("[compare_ui] %s", m),
    )

    anim_diagnostics = collect_npz_anim_diagnostics(
        p,
        meta=meta,
        context="compare_ui NPZ",
        log=lambda m: logger.warning("[compare_ui] %s", m),
    )
    geometry_acceptance = collect_geometry_acceptance_from_frame(df_main)

    road_sidecar = load_visual_road_sidecar(
        p,
        meta,
        time_vector=t_main,
        context="compare_ui NPZ",
        log=lambda m: logger.warning("[compare_ui] %s", m),
    )
    visual_contract = collect_visual_contract_status(
        df_main if not df_main.empty else [],
        meta=meta,
        npz_path=p,
        time_vector=t_main,
        road_sidecar=road_sidecar,
        context="compare_ui NPZ",
        log=lambda m: logger.warning("[compare_ui] %s", m),
    )
    meta["_geometry_contract_issues"] = list(visual_contract.get("geometry_contract_issues") or [])
    meta["_geometry_contract_ok"] = bool(visual_contract.get("geometry_contract_ok"))
    meta["_visual_contract"] = dict(visual_contract)
    meta["_visual_cache_dependencies"] = dict(cache_deps)

    meta["_anim_diagnostics"] = dict(anim_diagnostics)
    meta["_visual_cache_token"] = str(anim_diagnostics.get("bundle_visual_cache_token") or "")
    meta["_visual_reload_inputs"] = list(anim_diagnostics.get("bundle_visual_reload_inputs") or [])
    meta["_geometry_acceptance"] = dict(geometry_acceptance)
    meta["_geometry_acceptance_ok"] = bool(geometry_acceptance.get("ok", False))
    meta["_geometry_acceptance_level"] = str(geometry_acceptance.get("level") or "missing")
    meta["_geometry_acceptance_gate"] = str(geometry_acceptance.get("release_gate") or "MISSING")
    meta["_geometry_acceptance_reason"] = str(geometry_acceptance.get("release_gate_reason") or "")

    # build output + compatibility aliases
    out: Dict[str, Any] = {
        "tables": tables,
        "meta": meta,
        "visual_contract": visual_contract,
        "anim_diagnostics": anim_diagnostics,
        "geometry_acceptance": geometry_acceptance,
        "road_sidecar_wheels": dict(road_sidecar.get("wheels") or {}),
        "road_sidecar": road_sidecar,
        "cache_deps": cache_deps,
    }
    for k, df in tables.items():
        out[k] = df
    return out


# -----------------------------
# Meta helpers (for N→N analysis)
# -----------------------------


def flatten_meta_numeric(meta: Any, *, limit: int = 500) -> Dict[str, float]:
    """Извлечь численные значения из meta dict.

    Возвращает плоский dict вида:
        {"a": 1.0, "b.c": 2.0, ...}

    Используется для корреляционного N→N анализа:
    meta-параметры прогона (X) ↔ метрики выходных сигналов (Y).
    """

    out: Dict[str, float] = {}
    if not isinstance(meta, dict):
        return out

    def rec(prefix: str, obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                rec(f"{prefix}{k}.", v)
        elif isinstance(obj, (int, float)):
            try:
                fv = float(obj)
            except Exception:
                return
            if np.isfinite(fv):
                key = prefix[:-1] if prefix.endswith(".") else prefix
                out[key] = fv

    try:
        rec("", meta)
    except Exception:
        return {}

    if int(limit) > 0 and len(out) > int(limit):
        keys = sorted(out.keys())[: int(limit)]
        out = {k: out[k] for k in keys}
    return out


# -----------------------------
# Time helpers
# -----------------------------


def detect_time_col(df: pd.DataFrame) -> str | None:
    """Найти колонку времени в DataFrame (best-effort)."""
    if df is None or df.empty:
        return None

    cand = [
        "t",
        "time",
        "sec",
        "seconds",
        "время_с",
        "время",
        "сек",
        "секунды",
    ]
    cols_l = {str(c).lower(): str(c) for c in df.columns}
    for c in cand:
        if c in cols_l:
            return cols_l[c]

    for c in df.columns:
        cl = str(c).lower()
        if cl == "t" or cl.startswith("t_") or cl.startswith("time") or cl.startswith("время"):
            return str(c)

    return None


def extract_time_vector(df: pd.DataFrame, time_col: Optional[str] = None) -> np.ndarray:
    """Вернуть вектор времени.

    Логика:
    1) Если time_col задан и есть в df.columns — используем его
    2) Иначе пытаемся определить автоматически
    3) Иначе используем индекс
    """

    if df is None or df.empty:
        return np.zeros(0, dtype=float)

    if time_col:
        tc = str(time_col)
        if tc in df.columns:
            try:
                return df[tc].to_numpy(dtype=float)
            except Exception:
                pass

    tcol = detect_time_col(df)
    if tcol and tcol in df.columns:
        try:
            return df[tcol].to_numpy(dtype=float)
        except Exception:
            pass

    try:
        return df.index.to_numpy(dtype=float)
    except Exception:
        return np.arange(len(df), dtype=float)


# -----------------------------
# Units / transforms (display-only)
# -----------------------------


def _infer_unit_and_transform(
    col: str,
    *,
    P_ATM: float = P_ATM_DEFAULT,
    BAR_PA: float = BAR_PA,
    ATM_PA: float | None = None,
    dist_unit: str = "mm",
    angle_unit: str = "deg",
) -> Tuple[str, Callable[[np.ndarray], np.ndarray]]:
    """Угадать единицы и вернуть (unit, transform).

    Используется ТОЛЬКО для визуализации.

    Давление:
      * *_Pa_abs -> bar(abs)
      * *_Pa / 'давление' -> bar(g) = (Pa - P_ATM)/BAR_PA
      * *_bar_abs, *_bar_g -> уже bar

    Угол:
      * *_rad -> rad или deg (по angle_unit)
      * *_deg -> deg

    Перемещения:
      * *_m / *_mm -> m или mm (по dist_unit)

    ATM_PA оставлен для обратной совместимости (раньше им иногда ошибочно называли BAR_PA).
    """

    name = str(col or "")
    low = name.lower()

    # Backward-compat: если ATM_PA передали как делитель Pa→bar, допускаем только ~1e5
    if ATM_PA is not None:
        try:
            v = float(ATM_PA)
            if abs(v - 100000.0) <= 500.0:
                BAR_PA = v
        except Exception:
            pass

    def as_arr(x: Any) -> np.ndarray:
        try:
            return np.asarray(x, dtype=float)
        except Exception:
            return np.asarray([], dtype=float)

    # --- pressure ---
    if "_bar_abs" in low or "bar_abs" in low:
        return "bar(abs)", lambda x: as_arr(x)

    if "_bar_g" in low or "bar_g" in low or "gauge" in low:
        return "bar(g)", lambda x: as_arr(x)

    if low.endswith("_pa_abs") or "pa_abs" in low or "па_abs" in low:
        return "bar(abs)", lambda x: as_arr(x) / float(BAR_PA)

    if low.endswith("_pa") or "_pa_" in low or "давление" in low or ("па" in low and "комп" not in low):
        return "bar(g)", lambda x: (as_arr(x) - float(P_ATM)) / float(BAR_PA)

    # --- angles ---
    if low.endswith("_deg") or "град" in low:
        return "deg", lambda x: as_arr(x)

    if low.endswith("_rad"):
        if str(angle_unit).lower().startswith("deg"):
            return "deg", lambda x: as_arr(x) * (180.0 / math.pi)
        return "rad", lambda x: as_arr(x)

    # --- accel / velocity ---
    if "ускор" in low or low.endswith("_m_s2") or low.endswith("_m/s2") or low.endswith("_m_s^2"):
        return "m/s²", lambda x: as_arr(x)

    if low.endswith("_m_s") or low.endswith("_m/s") or low.endswith("_m_s-1"):
        return "m/s", lambda x: as_arr(x)

    # --- displacement ---
    is_mm = low.endswith("_mm") or "мм" in low
    is_m = (low.endswith("_m") or low.endswith("_м")) and (not is_mm)

    du = str(dist_unit or "").lower().strip()
    if is_mm:
        if du == "m":
            return "m", lambda x: as_arr(x) * 0.001
        return "mm", lambda x: as_arr(x)

    if is_m or "ход" in low or "шток" in low or "stroke" in low:
        if du == "mm":
            return "mm", lambda x: as_arr(x) * 1000.0
        return "m", lambda x: as_arr(x)

    # default
    return "", lambda x: as_arr(x)


# -----------------------------
# Baseline / scaling helpers
# -----------------------------


def is_zeroable_unit(unit: str) -> bool:
    u = (unit or "").strip().lower()
    return u in {"m", "mm", "rad", "deg"}


def apply_zero_baseline(
    t: np.ndarray,
    y: np.ndarray,
    *,
    unit: str,
    enable: bool,
    mode: str = "t0",
    window_s: float = 0.0,
    first_n: int = 0,
) -> np.ndarray:
    """Обнулить сигнал относительно базовой статики.

    mode:
      - t0
      - median_window / mean_window  (окно от t0)
      - median_first_n / mean_first_n
    """

    if not enable:
        return y
    if y is None:
        return y
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return y

    if not is_zeroable_unit(unit):
        return y

    mode = str(mode or "t0").strip().lower()
    y0 = float(y[0])

    try:
        if mode in {"median_window", "mean_window"} and t is not None and np.asarray(t).size == y.size:
            w = float(window_s or 0.0)
            if w > 0:
                t = np.asarray(t, dtype=float)
                t0 = float(t[0])
                m = t <= (t0 + w)
                if np.any(m):
                    if mode.startswith("median"):
                        y0 = float(np.nanmedian(y[m]))
                    else:
                        y0 = float(np.nanmean(y[m]))
        elif mode in {"median_first_n", "mean_first_n"}:
            n = int(first_n or 0)
            if n > 0:
                n = min(n, y.size)
                if mode.startswith("median"):
                    y0 = float(np.nanmedian(y[:n]))
                else:
                    y0 = float(np.nanmean(y[:n]))
        else:
            # t0
            y0 = float(y[0])
    except Exception:
        y0 = float(y[0])

    if np.isfinite(y0):
        return y - y0
    return y


def robust_minmax(y: np.ndarray, p_lo: float = 1.0, p_hi: float = 99.0) -> Tuple[float, float]:
    """Robust min/max by percentiles (ignoring NaN/Inf)."""
    a = np.asarray(y, dtype=float).ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return (float("nan"), float("nan"))
    try:
        lo = float(np.percentile(a, float(p_lo)))
        hi = float(np.percentile(a, float(p_hi)))
    except Exception:
        lo = float(np.nanmin(a))
        hi = float(np.nanmax(a))

    if not np.isfinite(lo) or not np.isfinite(hi):
        return (float("nan"), float("nan"))
    if lo == hi:
        d = max(1e-12, abs(lo) * 0.05)
        lo -= d
        hi += d
    return (lo, hi)


def _pad_range(lo: float, hi: float, frac: float = 0.02) -> Tuple[float, float]:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return lo, hi
    if lo == hi:
        d = max(1e-12, abs(lo) * 0.05)
        lo -= d
        hi += d
    pad = float(frac) * (hi - lo)
    return (lo - pad, hi + pad)


def resample_linear(x: np.ndarray, y: np.ndarray, x_new: np.ndarray) -> np.ndarray:
    """Линейная интерполяция y(x) на новую сетку x_new.

    Возвращает массив длины len(x_new), с NaN за пределами исходного диапазона.
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    x_new = np.asarray(x_new, dtype=float).ravel()

    if x_new.size == 0:
        return np.asarray([], dtype=float)
    if x.size == 0 or y.size == 0 or x.size != y.size:
        return np.full_like(x_new, np.nan, dtype=float)

    # sort and drop non-finite
    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]
    if x.size < 2:
        return np.full_like(x_new, np.nan, dtype=float)

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    # np.interp doesn't handle NaN; we already removed
    out = np.interp(x_new, x, y, left=np.nan, right=np.nan)
    return np.asarray(out, dtype=float)


def common_time_grid(times: Sequence[np.ndarray], *, max_points: int = 5000) -> np.ndarray:
    """Построить общую временную сетку по нескольким прогонам.

    Стратегия (простая и предсказуемая):
    - берём min(t0) и max(t1)
    - шаг = минимальная медианная dt среди входных сеток

    Если данных мало — возвращаем сетку первого элемента.
    """
    times = [np.asarray(t, dtype=float).ravel() for t in (times or []) if t is not None and np.asarray(t).size]
    if not times:
        return np.zeros(0, dtype=float)

    if len(times) == 1:
        return times[0]

    t0 = float(np.nanmin([t[0] for t in times if t.size]))
    t1 = float(np.nanmax([t[-1] for t in times if t.size]))

    dts = []
    for t in times:
        if t.size >= 3:
            dt = np.diff(t)
            dt = dt[np.isfinite(dt) & (dt > 0)]
            if dt.size:
                dts.append(float(np.nanmedian(dt)))
    if not dts:
        return times[0]

    dt0 = max(1e-6, float(np.nanmin(dts)))
    n = int(max(2, min(int((t1 - t0) / dt0) + 1, int(max_points))))
    return np.linspace(t0, t1, n)


def locked_ranges_by_unit(
    series_by_sig: Mapping[str, Tuple[str, np.ndarray]],
    *,
    robust: bool = True,
    symmetric: bool = False,
) -> Dict[str, RangeSpec]:
    """Посчитать фиксированные Y‑диапазоны по единицам."""
    by_unit: Dict[str, List[np.ndarray]] = {}
    for _sig, (unit, y) in series_by_sig.items():
        u = str(unit or "")
        by_unit.setdefault(u, []).append(np.asarray(y, dtype=float).ravel())

    out: Dict[str, RangeSpec] = {}
    for unit, arrs in by_unit.items():
        cat = np.concatenate([a[np.isfinite(a)] for a in arrs if a.size], axis=0) if arrs else np.asarray([], dtype=float)
        if cat.size == 0:
            continue
        if robust:
            lo, hi = robust_minmax(cat)
        else:
            lo = float(np.nanmin(cat))
            hi = float(np.nanmax(cat))
        if symmetric:
            m = max(abs(lo), abs(hi))
            if not np.isfinite(m) or m == 0:
                m = 1.0
            lo, hi = -m, m
        lo, hi = _pad_range(lo, hi)
        out[unit] = RangeSpec(ymin=float(lo), ymax=float(hi))
    return out


def compute_locked_ranges(
    series_by_sig: Mapping[str, Sequence[np.ndarray] | np.ndarray],
    unit_by_sig: Mapping[str, str],
    *,
    lock_mode: str = "by_signal",
    robust: bool = True,
    sym_zero: bool = False,
) -> Dict[str, RangeSpec]:
    """Locked ranges for a set of signals.

    series_by_sig:
        sig -> list of arrays (e.g. all runs) OR a single array
    unit_by_sig:
        sig -> unit

    lock_mode:
        - 'by_signal': each signal gets own range
        - 'by_unit'  : all signals with same unit share range
    """

    lock_mode = str(lock_mode or "by_signal").strip().lower()

    # Normalize series list
    norm: Dict[str, List[np.ndarray]] = {}
    for sig, ys in series_by_sig.items():
        if isinstance(ys, np.ndarray):
            norm[sig] = [np.asarray(ys, dtype=float)]
        else:
            norm[sig] = [np.asarray(a, dtype=float) for a in (ys or [])]

    if lock_mode == "by_unit":
        # build per-unit concatenated arrays
        series_unit: Dict[str, np.ndarray] = {}
        for sig, arrs in norm.items():
            unit = str(unit_by_sig.get(sig, "") or "")
            cat = np.concatenate([a[np.isfinite(a)] for a in arrs if a.size], axis=0) if arrs else np.asarray([], dtype=float)
            if cat.size == 0:
                continue
            if unit not in series_unit:
                series_unit[unit] = cat
            else:
                series_unit[unit] = np.concatenate([series_unit[unit], cat], axis=0)

        unit_ranges: Dict[str, RangeSpec] = {}
        for unit, cat in series_unit.items():
            if robust:
                lo, hi = robust_minmax(cat)
            else:
                lo = float(np.nanmin(cat))
                hi = float(np.nanmax(cat))
            if sym_zero:
                m = max(abs(lo), abs(hi))
                if not np.isfinite(m) or m == 0:
                    m = 1.0
                lo, hi = -m, m
            lo, hi = _pad_range(lo, hi)
            unit_ranges[unit] = RangeSpec(ymin=float(lo), ymax=float(hi))

        # assign back to signals
        out: Dict[str, RangeSpec] = {}
        for sig in norm.keys():
            unit = str(unit_by_sig.get(sig, "") or "")
            if unit in unit_ranges:
                out[sig] = unit_ranges[unit]
        return out

    # by_signal
    out: Dict[str, RangeSpec] = {}
    for sig, arrs in norm.items():
        cat = np.concatenate([a[np.isfinite(a)] for a in arrs if a.size], axis=0) if arrs else np.asarray([], dtype=float)
        if cat.size == 0:
            continue
        if robust:
            lo, hi = robust_minmax(cat)
        else:
            lo = float(np.nanmin(cat))
            hi = float(np.nanmax(cat))
        if sym_zero:
            m = max(abs(lo), abs(hi))
            if not np.isfinite(m) or m == 0:
                m = 1.0
            lo, hi = -m, m
        lo, hi = _pad_range(lo, hi)
        out[sig] = RangeSpec(ymin=float(lo), ymax=float(hi))
    return out


# -----------------------------
# Flow conversion
# -----------------------------


def massflow_to_Nl_min_ANR(mdot_kg_s: np.ndarray, *, p_ref_pa: float = P_ATM_DEFAULT, T_ref_K: float = 293.15) -> np.ndarray:
    """Перевод массового расхода воздуха (kg/s) → Nl/min (ANR).

    ANR условия в проекте: T_ref = 293.15 K (20°C), p_ref ≈ 101325 Pa.

    Qn [m^3/s] = mdot / rho_ref,  rho_ref = p_ref/(R*T_ref)
    Nl/min = Qn * 60 * 1000
    """
    md = np.asarray(mdot_kg_s, dtype=float)
    R = 287.05  # J/(kg*K) for dry air
    rho = float(p_ref_pa) / (R * float(T_ref_K))
    if rho <= 0:
        rho = 1.204  # fallback
    q_m3_s = md / rho
    return q_m3_s * 60.0 * 1000.0


# -----------------------------
# Unified XY extractor (bundle/table/signal)
# -----------------------------


def _get_tables_from_bundle(bundle: Any) -> Dict[str, pd.DataFrame]:
    if isinstance(bundle, dict):
        t = bundle.get("tables")
        if isinstance(t, dict):
            return t
        # compatibility: assume bundle itself is {table: df}
        # collect only dataframes
        out = {k: v for k, v in bundle.items() if isinstance(v, pd.DataFrame)}
        if out:
            return out
    return {}


def get_xy(
    bundle: Dict[str, Any] | Dict[str, pd.DataFrame],
    table: str,
    sig: str,
    *,
    dist_unit: str = "mm",
    angle_unit: str = "deg",
    P_ATM: float = P_ATM_DEFAULT,
    BAR_PA: float = BAR_PA,
    baseline_mode: str = "t0",
    baseline_window_s: float = 0.0,
    baseline_first_n: int = 0,
    zero_positions: bool = True,
    flow_unit: str = "raw",
    time_window: Optional[Tuple[float, float]] = None,
) -> Tuple[np.ndarray, np.ndarray, str]:
    """Достать (t, y, unit) из bundle/table/signal для сравнения/построения.

    - применяет transform единиц
    - опционально переводит массовый расход в Nl/min (ANR)
    - опционально обнуляет baseline для позиционных величин
    - опционально вырезает окно времени (display-only)
    """
    tables = _get_tables_from_bundle(bundle)
    df = tables.get(table)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return np.asarray([], dtype=float), np.asarray([], dtype=float), ""

    tcol = detect_time_col(df)
    x = extract_time_vector(df, tcol)
    if sig not in df.columns:
        return x, np.asarray([], dtype=float), ""

    y0 = np.asarray(df[sig].values, dtype=float)
    unit, tr = _infer_unit_and_transform(sig, P_ATM=float(P_ATM), BAR_PA=float(BAR_PA), dist_unit=dist_unit, angle_unit=angle_unit)
    try:
        y = np.asarray(tr(y0), dtype=float)
    except Exception:
        y = y0

    # flows
    if str(flow_unit).lower().startswith("nl") and (unit == "" or "kg" in unit.lower()):
        low = str(sig).lower()
        if ("kg_s" in low) or ("kg/s" in low) or low.endswith("_kg_s") or low.endswith("_kg/s") or ("массов" in low) or ("mdot" in low) or ("m_dot" in low):
            y = massflow_to_Nl_min_ANR(y)
            unit = "Nl/min (ANR)"

    # time window
    if time_window and x.size == y.size and x.size:
        t0, t1 = float(time_window[0]), float(time_window[1])
        m = (x >= t0) & (x <= t1)
        if np.any(m):
            x = x[m]
            y = y[m]

    # baseline
    if bool(zero_positions) and is_zeroable_unit(unit):
        y = apply_zero_baseline(
            x,
            y,
            unit=unit,
            enable=True,
            mode=str(baseline_mode),
            window_s=float(baseline_window_s or 0.0),
            first_n=int(baseline_first_n or 0),
        )

    return x, y, unit


# -----------------------------
# Δ matrices (run × signal)
# -----------------------------


def _metric_of_series(y: np.ndarray, metric: str) -> float:
    y = np.asarray(y, dtype=float).ravel()
    y = y[np.isfinite(y)]
    if y.size == 0:
        return float("nan")
    metric = str(metric or "maxabs").strip().lower()
    if metric in {"rms", "l2"}:
        return float(np.sqrt(np.mean(y * y)))
    if metric in {"meanabs", "mae", "l1"}:
        return float(np.mean(np.abs(y)))
    # default: max abs
    return float(np.max(np.abs(y)))


def delta_run_signal_metric(
    runs: Sequence[Tuple[str, Dict[str, Any] | Dict[str, pd.DataFrame]]],
    *,
    table: str,
    sigs: Sequence[str],
    ref_label: str,
    dist_unit: str,
    angle_unit: str,
    P_ATM: float,
    BAR_PA: float = BAR_PA,
    baseline_mode: str = "t0",
    baseline_window_s: float = 0.0,
    baseline_first_n: int = 0,
    zero_positions: bool = True,
    flow_unit: str = "raw",
    metric: str = "maxabs",
    time_window: Optional[Tuple[float, float]] = None,
) -> pd.DataFrame:
    """Матрица метрик по Δ относительно reference (runs × sigs).

    metric:
      - maxabs (по умолчанию)
      - rms
      - meanabs

    Reference строка включается и содержит 0.0 (для режима Δ).
    """

    runs = list(runs)
    if not runs or not sigs:
        return pd.DataFrame(index=[lab for lab, _ in runs], columns=list(sigs))

    # find reference bundle
    ref_bundle = None
    for lab, bun in runs:
        if lab == ref_label:
            ref_bundle = bun
            break
    if ref_bundle is None:
        ref_label = runs[0][0]
        ref_bundle = runs[0][1]

    out = np.full((len(runs), len(sigs)), np.nan, dtype=float)

    for j, sig in enumerate(sigs):
        x_ref, y_ref, _unit = get_xy(
            ref_bundle,
            table,
            sig,
            dist_unit=dist_unit,
            angle_unit=angle_unit,
            P_ATM=float(P_ATM),
            BAR_PA=float(BAR_PA),
            baseline_mode=baseline_mode,
            baseline_window_s=baseline_window_s,
            baseline_first_n=baseline_first_n,
            zero_positions=zero_positions,
            flow_unit=flow_unit,
            time_window=time_window,
        )
        if x_ref.size == 0 or y_ref.size == 0:
            continue

        for i, (lab, bun) in enumerate(runs):
            if lab == ref_label:
                out[i, j] = 0.0
                continue
            x, y, _u = get_xy(
                bun,
                table,
                sig,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=float(P_ATM),
                BAR_PA=float(BAR_PA),
                baseline_mode=baseline_mode,
                baseline_window_s=baseline_window_s,
                baseline_first_n=baseline_first_n,
                zero_positions=zero_positions,
                flow_unit=flow_unit,
                time_window=time_window,
            )
            if x.size == 0 or y.size == 0:
                continue
            y_i = resample_linear(x, y, x_ref)
            d = y_i - y_ref
            out[i, j] = _metric_of_series(d, metric)

    df = pd.DataFrame(out, index=[lab for lab, _ in runs], columns=list(sigs))
    return df


def delta_run_signal_maxabs(
    runs: Sequence[Tuple[str, Dict[str, Any] | Dict[str, pd.DataFrame]]],
    *,
    table: str,
    sigs: Sequence[str],
    ref_label: str,
    dist_unit: str,
    angle_unit: str,
    P_ATM: float,
    BAR_PA: float = BAR_PA,
    baseline_mode: str = "t0",
    baseline_window_s: float = 0.0,
    baseline_first_n: int = 0,
    zero_positions: bool = True,
    flow_unit: str = "raw",
    time_window: Optional[Tuple[float, float]] = None,
) -> pd.DataFrame:
    """Совместимый wrapper: матрица max|Δ| (runs × sigs)."""
    return delta_run_signal_metric(
        runs,
        table=table,
        sigs=sigs,
        ref_label=ref_label,
        dist_unit=dist_unit,
        angle_unit=angle_unit,
        P_ATM=P_ATM,
        BAR_PA=BAR_PA,
        baseline_mode=baseline_mode,
        baseline_window_s=baseline_window_s,
        baseline_first_n=baseline_first_n,
        zero_positions=zero_positions,
        flow_unit=flow_unit,
        metric="maxabs",
        time_window=time_window,
    )


# -----------------------------
# Metric matrices (runs × signals)
# -----------------------------


def _normalize_metric_kind(metric_kind: str) -> str:
    mk = str(metric_kind or "maxabs").strip().lower()
    if mk in {"max", "maxabs", "max|x|", "max_abs"}:
        return "maxabs"
    if mk in {"rms", "l2", "std"}:
        return "rms"
    if mk in {"meanabs", "mae", "l1", "mean_abs"}:
        return "meanabs"
    return "maxabs"


def run_signal_metric_matrix(
    runs: Sequence[Tuple[str, Dict[str, Any] | Dict[str, pd.DataFrame]]],
    *,
    table: str,
    sigs: Sequence[str],
    metric_code: str,
    ref_label: Optional[str] = None,
    dist_unit: str = "mm",
    angle_unit: str = "deg",
    P_ATM: float = P_ATM_DEFAULT,
    BAR_PA: float = BAR_PA,
    baseline_mode: str = "t0",
    baseline_window_s: float = 0.0,
    baseline_first_n: int = 0,
    zero_positions: bool = True,
    flow_unit: str = "raw",
    time_window: Optional[Tuple[float, float]] = None,
) -> pd.DataFrame:
    """Матрица метрик runs×signals для сравнения и N→N анализа.

    metric_code:
      - delta_maxabs | delta_rms | delta_meanabs
      - abs_maxabs   | abs_rms   | abs_meanabs

    Для delta_* требуется reference (ref_label). Reference строка всегда 0.0.
    Для abs_* reference не нужен: метрика берётся по самому сигналу.
    """

    runs = list(runs)
    sigs = list(sigs)
    if not runs or not sigs:
        return pd.DataFrame(index=[lab for lab, _ in runs], columns=sigs)

    code = str(metric_code or "delta_maxabs").strip().lower()
    mode_delta = code.startswith("delta_")
    if "_" in code:
        _, kind = code.split("_", 1)
    else:
        kind = "maxabs"
    kind = _normalize_metric_kind(kind)

    # resolve reference
    if mode_delta:
        ref_label = str(ref_label or "")
        ref_bundle = None
        for lab, bun in runs:
            if lab == ref_label:
                ref_bundle = bun
                break
        if ref_bundle is None:
            ref_label = runs[0][0]
            ref_bundle = runs[0][1]
    else:
        ref_bundle = None
        ref_label = None

    out = np.full((len(runs), len(sigs)), np.nan, dtype=float)

    for j, sig in enumerate(sigs):
        if mode_delta and ref_bundle is not None and ref_label is not None:
            x_ref, y_ref, _u = get_xy(
                ref_bundle,
                table,
                sig,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=float(P_ATM),
                BAR_PA=float(BAR_PA),
                baseline_mode=baseline_mode,
                baseline_window_s=baseline_window_s,
                baseline_first_n=baseline_first_n,
                zero_positions=zero_positions,
                flow_unit=flow_unit,
                time_window=time_window,
            )
            if x_ref.size == 0 or y_ref.size == 0:
                continue

            for i, (lab, bun) in enumerate(runs):
                if lab == ref_label:
                    out[i, j] = 0.0
                    continue
                x, y, _u2 = get_xy(
                    bun,
                    table,
                    sig,
                    dist_unit=dist_unit,
                    angle_unit=angle_unit,
                    P_ATM=float(P_ATM),
                    BAR_PA=float(BAR_PA),
                    baseline_mode=baseline_mode,
                    baseline_window_s=baseline_window_s,
                    baseline_first_n=baseline_first_n,
                    zero_positions=zero_positions,
                    flow_unit=flow_unit,
                    time_window=time_window,
                )
                if x.size == 0 or y.size == 0:
                    continue
                y_i = resample_linear(x, y, x_ref)
                d = y_i - y_ref
                out[i, j] = _metric_of_series(d, kind)
        else:
            # abs metrics
            for i, (_lab, bun) in enumerate(runs):
                x, y, _u = get_xy(
                    bun,
                    table,
                    sig,
                    dist_unit=dist_unit,
                    angle_unit=angle_unit,
                    P_ATM=float(P_ATM),
                    BAR_PA=float(BAR_PA),
                    baseline_mode=baseline_mode,
                    baseline_window_s=baseline_window_s,
                    baseline_first_n=baseline_first_n,
                    zero_positions=zero_positions,
                    flow_unit=flow_unit,
                    time_window=time_window,
                )
                if x.size == 0 or y.size == 0:
                    continue
                out[i, j] = _metric_of_series(y, kind)

    return pd.DataFrame(out, index=[lab for lab, _ in runs], columns=sigs)


# -----------------------------
# Correlation helpers (Pearson / Spearman)
# -----------------------------


def corr_1d(x: np.ndarray, y: np.ndarray, *, method: str = "pearson", min_n: int = 3) -> float:
    """Корреляция между 1D массивами с NaN/Inf фильтрацией.

    method:
      - pearson
      - spearman (корреляция рангов)
    """

    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    m = np.isfinite(x) & np.isfinite(y)
    if int(m.sum()) < int(min_n):
        return float("nan")
    a = x[m]
    b = y[m]

    if str(method).lower().startswith("s"):
        # Spearman = Pearson(ranks)
        a = pd.Series(a).rank(method="average").to_numpy(dtype=float)
        b = pd.Series(b).rank(method="average").to_numpy(dtype=float)

    sa = float(np.std(a))
    sb = float(np.std(b))
    if not (np.isfinite(sa) and np.isfinite(sb)) or sa <= 0 or sb <= 0:
        return float("nan")

    try:
        return float(np.corrcoef(a, b)[0, 1])
    except Exception:
        return float("nan")


def topk_meta_by_corr(
    meta_df: pd.DataFrame,
    y: np.ndarray,
    *,
    method: str = "pearson",
    k: int = 10,
    min_n: int = 3,
) -> List[str]:
    """Выбрать top-K meta колонок по |corr(meta_i, y)|.

    Зачем:
      Parallel coordinates и другие high-D виды быстро становятся нечитаемыми,
      поэтому выбираем небольшой набор самых "влияющих" (по корреляции).

    Notes:
      - meta_df: индекс — runs, колонки — численные meta параметры
      - y: 1D метрика по выбранному сигналу (в том же порядке индекса)
    """
    if meta_df is None or meta_df.empty:
        return []

    y = np.asarray(y, dtype=float).ravel()
    if y.size != int(meta_df.shape[0]):
        # caller responsibility: align indices
        n = min(int(meta_df.shape[0]), int(y.size))
        if n <= 0:
            return []
        meta_df = meta_df.iloc[:n, :]
        y = y[:n]

    cols: List[str] = []
    scores: List[float] = []
    for c in list(meta_df.columns):
        try:
            x = meta_df[c].to_numpy(dtype=float)
        except Exception:
            continue
        cc = corr_1d(x, y, method=method, min_n=min_n)
        if np.isfinite(cc):
            cols.append(str(c))
            scores.append(float(abs(cc)))

    if not cols:
        return []

    order = np.argsort(np.asarray(scores, dtype=float))[::-1]
    k = int(max(0, k))
    out = [cols[int(i)] for i in order[:k]]
    return out


def robust_clip_1d(x: np.ndarray, *, p_lo: float = 1.0, p_hi: float = 99.0) -> Tuple[np.ndarray, float, float]:
    """Robust-clipped copy of x and the (lo, hi) used.

    Useful for:
      - parallel coordinates (to reduce outlier domination)
      - consistent scaling across runs
    """
    x = np.asarray(x, dtype=float).ravel()
    lo, hi = robust_minmax(x, p_lo=p_lo, p_hi=p_hi)
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        try:
            lo = float(np.nanmin(x))
            hi = float(np.nanmax(x))
        except Exception:
            lo, hi = 0.0, 1.0
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        lo, hi = 0.0, 1.0
    x2 = np.clip(x, lo, hi)
    return x2, float(lo), float(hi)


def corr_matrix(X: np.ndarray, Y: np.ndarray, *, method: str = "pearson", min_n: int = 3) -> np.ndarray:
    """Корреляционная матрица между колонками X и колонками Y.

    X: shape (n_samples, n_features)
    Y: shape (n_samples, n_targets)
    Returns: shape (n_features, n_targets)
    """

    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)
    if X.ndim != 2 or Y.ndim != 2 or X.shape[0] != Y.shape[0] or X.shape[0] < int(min_n):
        return np.full((max(0, X.shape[1] if X.ndim == 2 else 0), max(0, Y.shape[1] if Y.ndim == 2 else 0)), np.nan)

    out = np.full((X.shape[1], Y.shape[1]), np.nan, dtype=float)
    for i in range(X.shape[1]):
        xi = X[:, i]
        for j in range(Y.shape[1]):
            out[i, j] = corr_1d(xi, Y[:, j], method=method, min_n=min_n)
    return out



# -----------------------------
# Metric matrix helpers (display / linking)
# -----------------------------


def infer_units_for_signals(
    sigs: Sequence[str],
    *,
    dist_unit: str,
    angle_unit: str,
    P_ATM: float = P_ATM_DEFAULT,
    BAR_PA: float = BAR_PA,
    flow_unit: str = "raw",
) -> Dict[str, str]:
    """Быстро получить unit для сигналов по тем же правилам, что и get_xy().

    Важно: для нормализаций heatmap (per-unit) не нужны сами данные,
    достаточно единиц измерения.

    Примечание про расход:
      - если выбран flow_unit="Nl/min (ANR)" и сигнал похож на массовый расход (kg/s),
        считаем unit = "Nl/min (ANR)".
    """

    out: Dict[str, str] = {}
    for s in sigs:
        unit, _tr = _infer_unit_and_transform(
            str(s),
            P_ATM=float(P_ATM),
            BAR_PA=float(BAR_PA),
            dist_unit=str(dist_unit),
            angle_unit=str(angle_unit),
        )
        # mirror get_xy(): massflow -> Nl/min (ANR)
        if str(flow_unit).lower().startswith("nl"):
            low = str(s).lower()
            if ("kg_s" in low) or ("kg/s" in low) or low.endswith("_kg_s") or low.endswith("_kg/s") or ("массов" in low) or ("mdot" in low) or ("m_dot" in low):
                unit = "Nl/min (ANR)"
        out[str(s)] = str(unit or "")
    return out


def metric_matrix_to_long(
    df: pd.DataFrame,
    *,
    top_k: int = 200,
    sort_by: str = "abs",
) -> pd.DataFrame:
    """Развернуть матрицу (runs×signals) в таблицу для linked selection.

    Возвращает DataFrame с колонками: run, signal, value.

    sort_by:
      - "abs"  : сортировка по abs(value) desc
      - "value": сортировка по value desc
      - "none" : без сортировки
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["run", "signal", "value"])

    try:
        # Pandas >=2.1: new stack implementation
        long = df.stack(future_stack=True).reset_index()
    except (TypeError, ValueError):
        # Older pandas (or older stack API)
        long = df.stack(dropna=False).reset_index()
    long.columns = ["run", "signal", "value"]

    # keep finite only
    try:
        v = pd.to_numeric(long["value"], errors="coerce")
        long["value"] = v
        long = long[np.isfinite(long["value"].to_numpy(dtype=float))]
    except Exception:
        pass

    sb = str(sort_by or "abs").lower().strip()
    if sb == "value":
        long = long.sort_values("value", ascending=False)
    elif sb == "abs":
        long = long.assign(_abs=long["value"].abs()).sort_values("_abs", ascending=False).drop(columns=["_abs"])

    if int(top_k) > 0:
        long = long.head(int(top_k))

    # stable index for selection widgets
    long = long.reset_index(drop=True)
    return long


def normalize_metric_matrix(
    df: pd.DataFrame,
    *,
    mode: str = "none",
    unit_by_sig: Optional[Mapping[str, str]] = None,
    p: float = 99.0,
    eps: float = 1e-12,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Нормализация матрицы метрик для сопоставимости разных сигналов.

    mode:
      - "none"        : без изменений
      - "per_signal"  : каждую колонку делим на p-перцентиль abs(col)
      - "per_unit"    : колонки одной unit делим на общий p-перцентиль abs(values)

    Возвращает (df_norm, scales), где scales:
      - per_signal: scale для каждого signal
      - per_unit  : scale для каждой unit
    """

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(), {}

    m = str(mode or "none").lower().strip()
    if m in {"none", "raw", "off"}:
        return df.copy(), {}

    # helper percentile
    def _pctl(a: np.ndarray) -> float:
        a = np.asarray(a, dtype=float).ravel()
        a = a[np.isfinite(a)]
        if a.size == 0:
            return float("nan")
        try:
            return float(np.nanpercentile(np.abs(a), float(p)))
        except Exception:
            return float(np.nanmax(np.abs(a)))

    df_out = df.copy()

    if m.startswith("per_sig") or m.startswith("per_signal"):
        scales: Dict[str, float] = {}
        for c in df_out.columns:
            sc = _pctl(df_out[c].to_numpy(dtype=float))
            if not np.isfinite(sc) or sc <= eps:
                sc = 1.0
            scales[str(c)] = float(sc)
            df_out[c] = df_out[c] / float(sc)
        return df_out, scales

    if m.startswith("per_unit"):
        ub = dict(unit_by_sig or {})
        # group columns by unit
        groups: Dict[str, List[str]] = {}
        for c in df_out.columns:
            u = str(ub.get(str(c), "") or "")
            groups.setdefault(u, []).append(str(c))

        scales_u: Dict[str, float] = {}
        for u, cols in groups.items():
            cat = []
            for c in cols:
                try:
                    cat.append(df_out[c].to_numpy(dtype=float))
                except Exception:
                    pass
            if not cat:
                continue
            sc = _pctl(np.concatenate(cat, axis=0))
            if not np.isfinite(sc) or sc <= eps:
                sc = 1.0
            scales_u[str(u)] = float(sc)
            for c in cols:
                df_out[c] = df_out[c] / float(sc)

        return df_out, scales_u

    # unknown mode -> no changes
    return df.copy(), {}
