# -*- coding: utf-8 -*-
"""compare_influence_time.py

Influence(t) cube builder (Web + Qt).

Задача
------
Показать, как меняется связь/влияние "meta параметры" → "сигналы" во времени.

Идея
----
- Берём N прогонов (runs)
- Берём матрицу X: runs × features (meta)
- Берём значения сигналов Y(t): runs × sigs × time
- Для набора временных кадров считаем корреляцию Pearson:
      corr(X[:,i], Y[:,j,t_k])
  получаем куб:
      C[t_k, i, j]

В UI это рендерится как анимированная heatmap: features × sigs, меняется по времени.

Важно
------
- Не тащим тяжёлые зависимости.
- Ограничиваем размер (LOD): max_time_points, max_frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .compare_influence import corr_matrix
from .compare_deltat_heatmap import pick_frame_indices

try:
    # compare_ui = single source of truth for units/baselines.
    from .compare_ui import get_xy, BAR_PA
except Exception:  # pragma: no cover
    # defensive fallback (qt_compare_viewer manipulates sys.path)
    from pneumo_solver_ui.compare_ui import get_xy, BAR_PA  # type: ignore


@dataclass
class InfluenceTCube:
    """Time-cube of correlations.

    cube shape: (T, n_features, n_sigs)
    """

    t: np.ndarray
    cube: np.ndarray
    feat_names: List[str]
    sigs: List[str]
    mode: str
    ref_label: str


def _tables(bundle: Any) -> Dict[str, pd.DataFrame]:
    if isinstance(bundle, dict):
        t = bundle.get("tables")
        if isinstance(t, dict):
            return {k: v for k, v in t.items() if isinstance(v, pd.DataFrame)}
        # sometimes tables are stored directly
        if any(isinstance(v, pd.DataFrame) for v in bundle.values()):
            return {k: v for k, v in bundle.items() if isinstance(v, pd.DataFrame)}
    return {}


def _safe_time(df: Optional[pd.DataFrame]) -> np.ndarray:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return np.asarray([], dtype=float)

    for c in ("t", "time", "Time", "sec", "s"):
        if c in df.columns:
            try:
                return np.asarray(df[c].values, dtype=float)
            except Exception:
                pass

    # fallback: first numeric column
    for c in df.columns:
        try:
            v = np.asarray(df[c].values, dtype=float)
            if v.size >= 2 and np.isfinite(v).any():
                return v
        except Exception:
            continue

    return np.asarray([], dtype=float)


def _downsample_time(x: np.ndarray, *, max_points: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size <= 0:
        return x

    max_points = int(max(10, max_points))
    if x.size <= max_points:
        return x

    idx = np.linspace(0, x.size - 1, max_points)
    idx = np.unique(np.round(idx).astype(int))
    return x[idx]


def _resample_linear(x: np.ndarray, y: np.ndarray, x_ref: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x_ref = np.asarray(x_ref, dtype=float)

    if x.size < 2 or y.size < 2 or x_ref.size == 0:
        return np.full_like(x_ref, np.nan, dtype=float)

    try:
        return np.interp(x_ref, x, y, left=np.nan, right=np.nan)
    except Exception:
        out = np.full_like(x_ref, np.nan, dtype=float)
        try:
            m = np.isfinite(x) & np.isfinite(y)
            if int(m.sum()) >= 2:
                out = np.interp(x_ref, x[m], y[m], left=np.nan, right=np.nan)
        except Exception:
            pass
        return out


def build_influence_t_cube(
    runs: Sequence[Tuple[str, Any]],
    *,
    X: np.ndarray,
    feat_names: Sequence[str],
    table: str,
    sigs: Sequence[str],
    ref_label: str,
    mode: str = "value",  # "value" | "delta"
    dist_unit: str = "mm",
    angle_unit: str = "deg",
    p_atm: float = 101325.0,
    baseline_mode: str = "t0",
    baseline_window_s: float = 0.0,
    baseline_first_n: int = 0,
    zero_positions: bool = True,
    flow_unit: str = "raw",
    time_window: Optional[Tuple[float, float]] = None,
    max_time_points: int = 2000,
    max_frames: int = 120,
    min_n: int = 3,
) -> InfluenceTCube:
    """Build Influence(t) correlation cube.

    Parameters
    ----------
    runs:
        List of (label, bundle) for runs.
    X, feat_names:
        Feature matrix runs×features aligned with `runs` order.
    table, sigs:
        Which table and signals to sample.
    ref_label:
        Reference run label (used for mode="delta").
    mode:
        "value" or "delta" (delta relative to reference run).
    time_window:
        Optional (t0, t1) window.

    Returns
    -------
    InfluenceTCube
    """

    X = np.asarray(X, dtype=float)
    feat_names = list(map(str, list(feat_names)))
    sigs = list(map(str, list(sigs)))
    mode = str(mode or "value").strip().lower()

    if X.ndim != 2 or X.shape[0] != len(runs) or X.shape[1] == 0 or len(runs) < int(min_n):
        return InfluenceTCube(
            t=np.asarray([], dtype=float),
            cube=np.zeros((0, int(X.shape[1]) if X.ndim == 2 else 0, len(sigs)), dtype=float),
            feat_names=feat_names,
            sigs=sigs,
            mode=mode,
            ref_label=str(ref_label),
        )

    # find reference
    ref_bundle = None
    for lab, bun in runs:
        if str(lab) == str(ref_label):
            ref_bundle = bun
            break
    if ref_bundle is None and runs:
        ref_bundle = runs[0][1]
        ref_label = str(runs[0][0])

    # time grid from reference
    try:
        df_ref = _tables(ref_bundle).get(table)  # type: ignore[arg-type]
        t = _safe_time(df_ref)
    except Exception:
        t = np.asarray([], dtype=float)

    if t.size < 2:
        return InfluenceTCube(
            t=np.asarray([], dtype=float),
            cube=np.zeros((0, X.shape[1], len(sigs)), dtype=float),
            feat_names=feat_names,
            sigs=sigs,
            mode=mode,
            ref_label=str(ref_label),
        )

    # window + downsample
    if time_window is not None and t.size:
        a, b = float(time_window[0]), float(time_window[1])
        m = (t >= a) & (t <= b)
        if np.any(m):
            t = t[m]

    t = _downsample_time(t, max_points=int(max_time_points))
    if t.size < 2:
        return InfluenceTCube(
            t=np.asarray([], dtype=float),
            cube=np.zeros((0, X.shape[1], len(sigs)), dtype=float),
            feat_names=feat_names,
            sigs=sigs,
            mode=mode,
            ref_label=str(ref_label),
        )

    frame_idx = np.asarray(pick_frame_indices(t, max_frames=int(max_frames)), dtype=int)
    frame_idx = frame_idx[(frame_idx >= 0) & (frame_idx < t.size)]
    if frame_idx.size == 0:
        frame_idx = np.array([0, int(t.size - 1)], dtype=int)

    tF = t[frame_idx]

    # precompute reference resampled values (for delta)
    ref_vals = np.full((len(sigs), tF.size), np.nan, dtype=float)
    try:
        for j, s in enumerate(sigs):
            x0, y0, _u = get_xy(
                ref_bundle,  # type: ignore[arg-type]
                table,
                s,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=float(p_atm),
                BAR_PA=float(BAR_PA),
                baseline_mode=str(baseline_mode),
                baseline_window_s=float(baseline_window_s or 0.0),
                baseline_first_n=int(baseline_first_n or 0),
                zero_positions=bool(zero_positions),
                flow_unit=str(flow_unit or "raw"),
                time_window=time_window,
            )
            ref_vals[j, :] = _resample_linear(x0, y0, tF)
    except Exception:
        pass

    # Y_all: runs × sigs × T
    Y_all = np.full((len(runs), len(sigs), tF.size), np.nan, dtype=float)
    for i, (lab, bun) in enumerate(runs):
        for j, s in enumerate(sigs):
            try:
                x, y, _u = get_xy(
                    bun,
                    table,
                    s,
                    dist_unit=dist_unit,
                    angle_unit=angle_unit,
                    P_ATM=float(p_atm),
                    BAR_PA=float(BAR_PA),
                    baseline_mode=str(baseline_mode),
                    baseline_window_s=float(baseline_window_s or 0.0),
                    baseline_first_n=int(baseline_first_n or 0),
                    zero_positions=bool(zero_positions),
                    flow_unit=str(flow_unit or "raw"),
                    time_window=time_window,
                )
                v = _resample_linear(x, y, tF)

                if mode.startswith("del"):
                    if str(lab) == str(ref_label):
                        v = np.zeros_like(v, dtype=float)
                    else:
                        v = v - ref_vals[j, :]

                Y_all[i, j, :] = v
            except Exception:
                continue

    # cube: T × features × sigs
    cube = np.full((tF.size, X.shape[1], len(sigs)), np.nan, dtype=float)
    for k in range(int(tF.size)):
        Yk = Y_all[:, :, k]
        cube[k, :, :] = corr_matrix(X, Yk, min_n=int(min_n))

    return InfluenceTCube(
        t=tF,
        cube=cube,
        feat_names=list(feat_names),
        sigs=list(sigs),
        mode=mode,
        ref_label=str(ref_label),
    )
