# -*- coding: utf-8 -*-
"""Hypervolume / Pareto utilities (2D) with robust reference point & normalization.

Why this exists
---------------
The pneumo optimization uses **minimization** objectives:
- obj1 = settle time (s) → minimize
- obj2 = RMS accel (m/s^2) → minimize

But many modern MOBO tools (BoTorch) treat optimization as **maximization**.
So we consistently convert:

    Y_max = -Y_min

Then:
- Pareto front: non-dominated in maximization space
- Hypervolume: computed w.r.t. a reference point dominated by all Pareto points

We also implement **robust normalization**:
objectives may have different magnitudes, so HV in raw units can be ill-scaled.
We normalize HV space based on quantiles and the reference point.

This module intentionally has *no* hard dependency on BoTorch.
If BoTorch is installed, we can use its `infer_reference_point`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import math

import numpy as np


def to_maximization(Y_min: np.ndarray) -> np.ndarray:
    """Convert minimization objectives to maximization."""
    Y = np.asarray(Y_min, dtype=float)
    return -Y


def _is_finite_rows(Y: np.ndarray) -> np.ndarray:
    return np.all(np.isfinite(Y), axis=1)


def pareto_mask_max(Y_max: np.ndarray) -> np.ndarray:
    """Return boolean mask of non-dominated points in maximization space.

    Works for any m>=2, but complexity is O(n^2) worst-case.
    For our usual 2D use it is fast.
    """
    Y = np.asarray(Y_max, dtype=float)
    n = Y.shape[0]
    if n == 0:
        return np.zeros((0,), dtype=bool)

    mask = np.ones((n,), dtype=bool)
    for i in range(n):
        if not mask[i]:
            continue
        yi = Y[i]
        # A point is dominated if there exists j with Y[j] >= yi in all dims and > in at least one.
        dom = np.all(Y >= yi, axis=1) & np.any(Y > yi, axis=1)
        dom[i] = False
        if np.any(dom):
            mask[i] = False
    return mask


def infer_reference_point_max(pareto_Y_max: np.ndarray, scale: float = 0.1) -> np.ndarray:
    """Infer a conservative reference point in maximization space.

    If BoTorch is available, uses its helper.
    Fallback heuristic:
      ref = nadir - scale * (ideal - nadir)

    where:
      ideal = componentwise max
      nadir = componentwise min
    """
    Yp = np.asarray(pareto_Y_max, dtype=float)
    if Yp.size == 0:
        return np.array([-1.0, -1.0], dtype=float)

    # Try BoTorch if installed.
    try:
        from botorch.utils.multi_objective.hypervolume import infer_reference_point

        ref = infer_reference_point(Yp)
        return np.asarray(ref, dtype=float)
    except Exception:
        pass

    ideal = np.max(Yp, axis=0)
    nadir = np.min(Yp, axis=0)
    span = ideal - nadir
    span = np.where(np.isfinite(span) & (span > 0), span, 1.0)
    ref = nadir - float(scale) * span
    return ref


def _quantile_safe(x: np.ndarray, q: float) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.quantile(x, q))


@dataclass
class NormalizationStats:
    ref: np.ndarray
    hi: np.ndarray


def normalize_for_hv(
    Y_max: np.ndarray,
    ref_point: np.ndarray,
    quantiles: Tuple[float, float] = (0.1, 0.9),
    eps: float = 1e-12,
) -> Tuple[np.ndarray, np.ndarray, NormalizationStats]:
    """Normalize maximization objectives for hypervolume stability.

    We map each objective dim independently to roughly [0,1] where:
    - 0 corresponds to the reference point
    - 1 corresponds to a robust "high" value (q_high quantile)

    Returns:
      Y_norm, ref_norm, stats
    """
    Y = np.asarray(Y_max, dtype=float)
    ref = np.asarray(ref_point, dtype=float)

    q_lo, q_hi = quantiles
    hi = np.empty_like(ref)
    for d in range(ref.size):
        v_hi = _quantile_safe(Y[:, d], q_hi)
        # Ensure hi is above ref to avoid division by ~0.
        if not np.isfinite(v_hi):
            v_hi = float(np.max(Y[:, d]))
        hi[d] = max(v_hi, ref[d] + eps)

    denom = np.maximum(hi - ref, eps)
    Y_norm = (Y - ref) / denom
    ref_norm = np.zeros_like(ref)
    return Y_norm, ref_norm, NormalizationStats(ref=ref, hi=hi)


def hypervolume_2d_max(pareto_Y_max: np.ndarray, ref_point: np.ndarray) -> float:
    """Hypervolume in 2D for maximization.

    Assumes `ref_point` is dominated by all Pareto points.
    """
    P = np.asarray(pareto_Y_max, dtype=float)
    if P.size == 0:
        return 0.0

    ref = np.asarray(ref_point, dtype=float)
    # filter points that are above ref in both dims
    good = np.all(P > ref, axis=1)
    P = P[good]
    if P.size == 0:
        return 0.0

    # Ensure Pareto (non-dominated)
    P = P[pareto_mask_max(P)]

    # Sort by obj1 increasing; obj2 should be decreasing on a proper Pareto front.
    P = P[np.argsort(P[:, 0])]

    hv = 0.0
    prev_x = ref[0]
    for x, y in P:
        width = max(0.0, float(x - prev_x))
        height = max(0.0, float(y - ref[1]))
        hv += width * height
        prev_x = float(x)
    return float(hv)


def hv_progress(
    Y_min: np.ndarray,
    penalty: np.ndarray,
    feasible_tol: float = 0.0,
    scale: float = 0.1,
    normalize: bool = True,
) -> float:
    """Compute hypervolume of feasible Pareto front.

    Parameters
    ----------
    Y_min : (n,2) minimization objectives
    penalty : (n,) feasibility penalty
    feasible_tol : penalty threshold
    scale : fallback reference point margin
    normalize : whether to normalize objectives for HV
    """
    Y_min = np.asarray(Y_min, dtype=float)
    penalty = np.asarray(penalty, dtype=float)

    if Y_min.ndim != 2 or Y_min.shape[1] != 2:
        return float("nan")

    ok_rows = _is_finite_rows(Y_min) & np.isfinite(penalty)
    feas = ok_rows & (penalty <= feasible_tol)
    if np.sum(feas) < 2:
        return float("nan")

    Y_max = to_maximization(Y_min[feas])
    pm = pareto_mask_max(Y_max)
    P = Y_max[pm]

    ref = infer_reference_point_max(P, scale=scale)

    if normalize:
        Pn, refn, _ = normalize_for_hv(P, ref)
        return hypervolume_2d_max(Pn, refn)
    return hypervolume_2d_max(P, ref)


# Backward-compatible aliases
pareto_mask_maximization = pareto_mask_max
infer_reference_point_maximization = infer_reference_point_max
hypervolume_2d_maximization = hypervolume_2d_max
normalize_for_hypervolume = normalize_for_hv



# -----------------------------------------------------------------------------
# Extra backward-compatible helpers (used by Streamlit analysis pages)
# -----------------------------------------------------------------------------

def y_min_to_max(Y_min: np.ndarray) -> np.ndarray:
    """Alias: minimization -> maximization."""
    return to_maximization(Y_min)


def pareto_front_2d_max(Y_max: np.ndarray) -> np.ndarray:
    """Return the Pareto (non-dominated) front in maximization space (2D)."""
    Y = np.asarray(Y_max, dtype=float)
    if Y.ndim != 2 or Y.shape[1] != 2:
        return np.empty((0, 2), dtype=float)
    m = pareto_mask_max(Y)
    return Y[m]


def choose_reference_point_max(Y_max: np.ndarray, scale: float = 0.1) -> np.ndarray:
    """Choose a dominated reference point for HV (maximization space)."""
    P = pareto_front_2d_max(Y_max)
    return infer_reference_point_max(P, scale=scale)


def hv_2d_max(pareto_Y_max: np.ndarray, ref_point: np.ndarray) -> float:
    """Alias: 2D hypervolume in maximization space."""
    return hypervolume_2d_max(pareto_Y_max, ref_point)
