# -*- coding: utf-8 -*-
"""compare_deltat_heatmap.py

Δ(t) Heatmap — «плеер» для быстрого качественного анализа различий
между прогонами.

Идея
-----
Строим 3D‑куб:
  cube[t, i_sig, j_run] = Δ value

и отображаем его как time‑scrubber (плеер) + 2D heatmap на каждом кадре.

Этот модуль **не рисует** графики сам — он только готовит данные.
Рендер:
  - Web: Plotly animation (frames)
  - Desktop: pyqtgraph.ImageView (3D cube → ImageView)

Важно
------
- Код должен быть предсказуемым и "не ломать" UI.
- Встроены лимиты, чтобы не получить гигантские массивы.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class DeltaTCube:
    t: np.ndarray  # shape (T,)
    cube: np.ndarray  # shape (T, n_sig, n_run)
    sigs: List[str]
    run_labels: List[str]
    units_by_sig: Dict[str, str]


def _tables(bundle: Any) -> Dict[str, pd.DataFrame]:
    if isinstance(bundle, dict):
        t = bundle.get("tables")
        if isinstance(t, dict):
            return {k: v for k, v in t.items() if isinstance(v, pd.DataFrame)}
        # compatibility: bundle itself may be {table: df}
        out = {k: v for k, v in bundle.items() if isinstance(v, pd.DataFrame)}
        if out:
            return out
    return {}


def _safe_extract_time(df: pd.DataFrame) -> np.ndarray:
    try:
        try:
            from pneumo_solver_ui.compare_ui import detect_time_col, extract_time_vector  # type: ignore
        except Exception:
            from compare_ui import detect_time_col, extract_time_vector  # type: ignore

        tcol = detect_time_col(df)
        try:
            return np.asarray(extract_time_vector(df, tcol), dtype=float)
        except Exception:
            return np.asarray(extract_time_vector(df), dtype=float)
    except Exception:
        try:
            return np.asarray(df.iloc[:, 0].values, dtype=float)
        except Exception:
            return np.zeros(0, dtype=float)


def _downsample_time(t: np.ndarray, max_points: int) -> np.ndarray:
    t = np.asarray(t, dtype=float).ravel()
    if t.size <= 0:
        return t
    max_points = int(max_points)
    if max_points <= 0 or t.size <= max_points:
        return t
    idx = np.linspace(0, t.size - 1, num=max_points)
    idx = np.unique(np.round(idx).astype(int))
    return np.asarray(t[idx], dtype=float)


def pick_frame_indices(t: np.ndarray, *, max_frames: int = 200) -> np.ndarray:
    """Выбрать индексы кадров для анимации (равномерно по времени)."""
    t = np.asarray(t, dtype=float).ravel()
    if t.size == 0:
        return np.zeros(0, dtype=int)
    max_frames = int(max_frames)
    if max_frames <= 0 or t.size <= max_frames:
        return np.arange(t.size, dtype=int)
    idx = np.linspace(0, t.size - 1, num=max_frames)
    idx = np.unique(np.round(idx).astype(int))
    return idx.astype(int)


def build_deltat_cube(
    runs: Sequence[Tuple[str, Any]],
    *,
    table: str,
    sigs: Sequence[str],
    ref_label: Optional[str] = None,
    mode: str = "delta",  # delta | value
    dist_unit: str = "mm",
    angle_unit: str = "deg",
    P_ATM: float = 100000.0,
    BAR_PA: float = 100000.0,
    baseline_mode: str = "t0",
    baseline_window_s: float = 0.0,
    baseline_first_n: int = 0,
    zero_positions: bool = True,
    flow_unit: str = "raw",
    time_window: Optional[Tuple[float, float]] = None,
    max_time_points: int = 2500,
) -> DeltaTCube:
    """Собрать Δ(t) cube.

    runs:
      список (label, bundle)
      bundle может быть "полный" dict с ключом 'tables' или просто {table: df}.

    mode:
      - 'delta': y_run - y_ref (ref строка будет 0)
      - 'value': просто y_run (полезно иногда как быстрый просмотр)

    max_time_points:
      ограничение по количеству точек времени (чтобы не создавать огромные кубы).
    """

    runs = list(runs)
    sigs = [str(s) for s in (sigs or []) if str(s)]
    if not runs or not sigs:
        return DeltaTCube(t=np.zeros(0, dtype=float), cube=np.zeros((0, 0, 0), dtype=float), sigs=sigs, run_labels=[lab for lab, _ in runs], units_by_sig={})

    # reference
    if not ref_label:
        ref_label = str(runs[0][0])
    ref_bundle = None
    for lab, bun in runs:
        if str(lab) == str(ref_label):
            ref_bundle = bun
            break
    if ref_bundle is None:
        ref_bundle = runs[0][1]
        ref_label = str(runs[0][0])

    # time grid from reference table
    t = np.zeros(0, dtype=float)
    try:
        df_ref = _tables(ref_bundle).get(str(table))
        if isinstance(df_ref, pd.DataFrame) and not df_ref.empty:
            t = _safe_extract_time(df_ref)
    except Exception:
        t = np.zeros(0, dtype=float)

    t = np.asarray(t, dtype=float).ravel()
    if time_window and t.size:
        t0, t1 = float(time_window[0]), float(time_window[1])
        m = np.isfinite(t) & (t >= t0) & (t <= t1)
        if np.any(m):
            t = t[m]

    t = t[np.isfinite(t)]
    if t.size:
        # enforce monotonic grid for interpolation (best effort)
        order = np.argsort(t)
        t = t[order]
        # drop duplicates
        _, idx_u = np.unique(t, return_index=True)
        t = t[np.sort(idx_u)]

    t = _downsample_time(t, int(max_time_points))

    if t.size == 0:
        return DeltaTCube(t=t, cube=np.zeros((0, len(sigs), len(runs)), dtype=float), sigs=sigs, run_labels=[str(lab) for lab, _ in runs], units_by_sig={})

    # import compare_ui helpers lazily
    try:
        try:
            from pneumo_solver_ui.compare_ui import get_xy, resample_linear  # type: ignore
        except Exception:
            from compare_ui import get_xy, resample_linear  # type: ignore
    except Exception:
        # cannot build cube
        return DeltaTCube(t=t, cube=np.full((len(t), len(sigs), len(runs)), np.nan, dtype=float), sigs=sigs, run_labels=[str(lab) for lab, _ in runs], units_by_sig={})

    cube = np.full((int(len(t)), int(len(sigs)), int(len(runs))), np.nan, dtype=float)
    units: Dict[str, str] = {}

    # precompute ref series for each signal
    y_ref_by_sig: Dict[str, np.ndarray] = {}
    for j, sig in enumerate(sigs):
        try:
            x_ref, y_ref, unit = get_xy(
                ref_bundle,
                str(table),
                str(sig),
                dist_unit=str(dist_unit),
                angle_unit=str(angle_unit),
                P_ATM=float(P_ATM),
                BAR_PA=float(BAR_PA),
                baseline_mode=str(baseline_mode),
                baseline_window_s=float(baseline_window_s or 0.0),
                baseline_first_n=int(baseline_first_n or 0),
                zero_positions=bool(zero_positions),
                flow_unit=str(flow_unit),
                time_window=time_window,
            )
            units[str(sig)] = str(unit or "")
            y_ref_i = resample_linear(np.asarray(x_ref, dtype=float), np.asarray(y_ref, dtype=float), t)
            y_ref_by_sig[str(sig)] = y_ref_i
        except Exception:
            units[str(sig)] = ""
            y_ref_by_sig[str(sig)] = np.full_like(t, np.nan, dtype=float)

    # fill cube
    for i, (lab, bun) in enumerate(runs):
        for j, sig in enumerate(sigs):
            try:
                x, y, _unit = get_xy(
                    bun,
                    str(table),
                    str(sig),
                    dist_unit=str(dist_unit),
                    angle_unit=str(angle_unit),
                    P_ATM=float(P_ATM),
                    BAR_PA=float(BAR_PA),
                    baseline_mode=str(baseline_mode),
                    baseline_window_s=float(baseline_window_s or 0.0),
                    baseline_first_n=int(baseline_first_n or 0),
                    zero_positions=bool(zero_positions),
                    flow_unit=str(flow_unit),
                    time_window=time_window,
                )
                y_i = resample_linear(np.asarray(x, dtype=float), np.asarray(y, dtype=float), t)
                if str(mode).lower().startswith("d"):
                    y_ref_i = y_ref_by_sig.get(str(sig))
                    if y_ref_i is None:
                        y_ref_i = np.full_like(t, np.nan, dtype=float)
                    cube[:, j, i] = y_i - y_ref_i
                else:
                    cube[:, j, i] = y_i
            except Exception:
                # keep NaN
                continue

    return DeltaTCube(t=t, cube=cube, sigs=sigs, run_labels=[str(lab) for lab, _ in runs], units_by_sig=units)
