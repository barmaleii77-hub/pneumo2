# -*- coding: utf-8 -*-
"""pneumo_dist.hv_tools

Hypervolume & Pareto utilities (minimization).

Why this exists:
- BoTorch uses *maximization* conventions internally, but our model objectives
  are naturally *minimization* (time, RMS accel, energy... smaller is better).
- For monitoring optimization progress we want stable...

Features:
- Pareto filtering for minimization
- Robust objective normalization (quantile-based)
- "Smart" reference point inference in normalized space
- Hypervolume computation:
  - exact for 2D (no heavy deps)
  - for 3D+ uses BoTorch Hypervolume if available

NOTE: This module is for logging/monitoring and for acquisition (qNEHVI) support.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def pareto_mask_min(Y: np.ndarray) -> np.ndarray:
    """Return boolean mask of non-dominated points for *minimization*.

    A point i is non-dominated if there is no j such that:
      Y[j] <= Y[i] elementwise AND Y[j] < Y[i] for at least one dimension.
    """
    Y = np.asarray(Y, dtype=float)
    n = Y.shape[0]
    if n == 0:
        return np.zeros((0,), dtype=bool)
    mask = np.ones((n,), dtype=bool)
    for i in range(n):
        if not mask[i]:
            continue
        yi = Y[i]
        # any point that dominates i?
        dominates = np.all(Y <= yi, axis=1) & np.any(Y < yi, axis=1)
        if np.any(dominates):
            mask[i] = False
            continue
        # i may dominate others
        dominated_by_i = np.all(yi <= Y, axis=1) & np.any(yi < Y, axis=1)
        # keep i itself
        dominated_by_i[i] = False
        mask[dominated_by_i] = False
        mask[i] = True
    return mask


def pareto_front_min(Y: np.ndarray) -> np.ndarray:
    m = pareto_mask_min(Y)
    return np.asarray(Y, dtype=float)[m]


@dataclass
class Normalizer:
    """Affine normalizer: y_norm = (y - offset) / scale."""

    offset: np.ndarray
    scale: np.ndarray

    def transform(self, Y: np.ndarray) -> np.ndarray:
        Y = np.asarray(Y, dtype=float)
        return (Y - self.offset) / self.scale

    def inverse(self, Y_norm: np.ndarray) -> np.ndarray:
        Y_norm = np.asarray(Y_norm, dtype=float)
        return Y_norm * self.scale + self.offset


def fit_normalizer_quantile(Y: np.ndarray, q_lo: float = 0.05, q_hi: float = 0.95) -> Normalizer:
    """Robust normalization using quantiles.

    offset := quantile(q_lo)
    scale  := max(eps, quantile(q_hi) - quantile(q_lo))

    This is more stable than min-max early in a run.
    """
    Y = np.asarray(Y, dtype=float)
    if Y.size == 0:
        raise ValueError("Cannot fit normalizer on empty Y")
    lo = np.quantile(Y, q_lo, axis=0)
    hi = np.quantile(Y, q_hi, axis=0)
    scale = np.maximum(1e-12, hi - lo)
    return Normalizer(offset=lo, scale=scale)


def fit_normalizer(
    Y: np.ndarray,
    *,
    method: str = "quantile",
    q_low: float = 0.05,
    q_high: float = 0.95,
) -> Normalizer:
    """Fit a normalizer for objective vectors.

    The coordinator and proposer both call this helper.

    Parameters
    ----------
    Y:
        (n, m) array of objective values.
    method:
        - "quantile" (default): robust quantile-based scaling.
        - "minmax": classic min-max scaling (less stable early in a run).
    q_low, q_high:
        Quantiles for the "quantile" method.
    """

    Y = np.asarray(Y, dtype=float)
    m = str(method).lower().strip()
    if m in {"q", "quantile", "robust"}:
        return fit_normalizer_quantile(Y, q_lo=float(q_low), q_hi=float(q_high))
    if m in {"minmax", "mm"}:
        lo = np.min(Y, axis=0)
        hi = np.max(Y, axis=0)
        scale = np.maximum(1e-12, hi - lo)
        return Normalizer(offset=lo, scale=scale)
    raise ValueError(f"Unknown normalization method: {method}")


def infer_reference_point_min(
    Y: np.ndarray,
    *,
    normalizer: Optional[Normalizer] = None,
    margin: float = 0.10,
    quantile: float = 0.90,
) -> np.ndarray:
    """Infer a *minimization* reference point (worse than observed points).

    Strategy:
    - optionally normalize objectives
    - take per-objective q=0.9 (robust 'worst typical')
    - push it further by `margin` of the observed spread

    Returns ref in the *original* space (unless normalizer is None -> same).
    """
    Y = np.asarray(Y, dtype=float)
    if Y.size == 0:
        raise ValueError("Cannot infer reference point from empty Y")

    Yn = normalizer.transform(Y) if normalizer else Y

    q = np.quantile(Yn, float(quantile), axis=0)
    spread = np.maximum(1e-12, np.quantile(Yn, 0.95, axis=0) - np.quantile(Yn, 0.05, axis=0))
    ref_n = q + float(margin) * spread

    # Ensure strictly worse than all points
    ref_n = np.maximum(ref_n, np.max(Yn, axis=0) + 1e-9)

    return normalizer.inverse(ref_n) if normalizer else ref_n


def hypervolume_min_2d(Y: np.ndarray, ref: Sequence[float]) -> float:
    """Exact 2D hypervolume for minimization.

    Y: (n,2) non-dominated or arbitrary points.
    ref: length-2, must be worse (>=) than all points to be meaningful.
    """
    Y = np.asarray(Y, dtype=float)
    if Y.size == 0:
        return 0.0
    if Y.shape[1] != 2:
        raise ValueError("hypervolume_min_2d expects Y with shape (n,2)")
    ref = np.asarray(ref, dtype=float)

    # filter finite
    m = np.isfinite(Y).all(axis=1)
    Y = Y[m]
    if Y.size == 0:
        return 0.0

    # pareto
    Yp = pareto_front_min(Y)
    if Yp.size == 0:
        return 0.0

    # sort by f1 asc
    idx = np.argsort(Yp[:, 0])
    Yp = Yp[idx]

    hv = 0.0
    prev_f2 = ref[1]
    for f1, f2 in Yp:
        # clamp to ref
        f1c = min(float(f1), float(ref[0]))
        f2c = min(float(f2), float(ref[1]))
        w = float(ref[0] - f1c)
        h = float(prev_f2 - f2c)
        if w > 0 and h > 0:
            hv += w * h
        prev_f2 = min(prev_f2, f2c)
    return float(max(0.0, hv))


def hypervolume_min(Y: np.ndarray, ref: Sequence[float]) -> float:
    """Hypervolume for minimization in any dimension.

    - For 2D: exact implementation.
    - For 3D+: uses BoTorch Hypervolume if available.
      If BoTorch is not installed -> raises RuntimeError.
    """
    Y = np.asarray(Y, dtype=float)
    if Y.size == 0:
        return 0.0
    m = Y.shape[1]
    if m == 2:
        return hypervolume_min_2d(Y, ref)

    # 3D+ -> BoTorch (optional)
    try:
        import torch  # type: ignore
        from botorch.utils.multi_objective.hypervolume import Hypervolume  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Hypervolume for m>2 requires BoTorch (pip install torch botorch gpytorch)."
        ) from e

    # Convert minimization -> maximization
    Yp = pareto_front_min(Y)
    if Yp.size == 0:
        return 0.0

    Y_max = -torch.tensor(Yp, dtype=torch.double)
    ref_max = -torch.tensor(np.asarray(ref, dtype=float), dtype=torch.double)

    hv = Hypervolume(ref_point=ref_max)
    val = hv.compute(Y_max)
    return float(val.item())


def summarize_pareto(Y: np.ndarray) -> Dict[str, Any]:
    Y = np.asarray(Y, dtype=float)
    if Y.size == 0:
        return {"n": 0}
    m = np.isfinite(Y).all(axis=1)
    Y = Y[m]
    if Y.size == 0:
        return {"n": 0}
    mask = pareto_mask_min(Y)
    Yp = Y[mask]
    return {
        "n": int(Y.shape[0]),
        "n_pareto": int(Yp.shape[0]),
        "best": np.min(Yp, axis=0).tolist() if Yp.size else None,
        "worst": np.max(Yp, axis=0).tolist() if Yp.size else None,
    }


# ---------------------------------------------------------------------------

class HVMonitor:
    """Stateful hypervolume monitor.

    Computes hypervolume for *feasible* objective vectors in **normalized minimization
    space**. Optionally *freezes* the normalizer + reference point after `freeze_after`
    feasible points to make HV values comparable over time.

    Notes
    -----
    - HV is intended as a *progress metric* (logging/early stop), not as a strict
      correctness certificate.
    - We compute HV on the Pareto front (inside :func:`hypervolume_min`).
    """

    method: str = "quantile"
    q_low: float = 0.05
    q_high: float = 0.95
    ref_margin: float = 0.10
    ref_quantile: float = 0.90
    freeze_after: int = 0

    _frozen: bool = False
    _norm: Optional[Normalizer] = None
    _ref_n: Optional[np.ndarray] = None
    _frozen_at_feasible_n: int = 0

    def is_frozen(self) -> bool:
        return bool(self._frozen)

    def compute(self, Y_feasible: np.ndarray) -> Tuple[float, Dict[str, Any]]:
        """Compute HV for a set of feasible points.

        Parameters
        ----------
        Y_feasible:
            (n, m) objective array in *original* units.

        Returns
        -------
        hv:
            Hypervolume in normalized objective space.
        meta:
            JSON-serializable metadata (normalizer, ref, freeze state).
        """
        Y = np.asarray(Y_feasible, dtype=float)
        if Y.size == 0:
            return 0.0, {"hv": 0.0, "feasible_n": 0}
        # filter finite
        Y = Y[np.isfinite(Y).all(axis=1)]
        if Y.size == 0:
            return 0.0, {"hv": 0.0, "feasible_n": 0}

        feasible_n = int(Y.shape[0])

        if self._frozen and self._norm is not None and self._ref_n is not None:
            norm = self._norm
            ref_n = np.asarray(self._ref_n, dtype=float)
        else:
            norm = fit_normalizer(Y, method=self.method, q_low=self.q_low, q_high=self.q_high)
            Yn = norm.transform(Y)
            ref_n = infer_reference_point_min(
                Yn,
                normalizer=None,
                margin=float(self.ref_margin),
                quantile=float(self.ref_quantile),
            )

            if int(self.freeze_after) > 0 and feasible_n >= int(self.freeze_after):
                self._frozen = True
                self._norm = norm
                self._ref_n = ref_n
                self._frozen_at_feasible_n = feasible_n

        Yn = norm.transform(Y)
        hv = hypervolume_min(Yn, ref_n)

        meta = {
            "hv": float(hv),
            "feasible_n": feasible_n,
            "frozen": bool(self._frozen),
            "freeze_after": int(self.freeze_after),
            "frozen_at_feasible_n": int(self._frozen_at_feasible_n),
            "normalizer": {"offset": norm.offset.tolist(), "scale": norm.scale.tolist()},
            "ref_n": np.asarray(ref_n, dtype=float).tolist(),
            "method": str(self.method),
        }
        return float(hv), meta


# Backward-compatible API (maximization) for legacy pages/tools
# ---------------------------------------------------------------------------


def y_min_to_max(Y_min: np.ndarray) -> np.ndarray:
    """Convert minimization objectives to maximization (legacy API)."""
    return -np.asarray(Y_min, dtype=float)


def _pareto_mask_max(Y: np.ndarray) -> np.ndarray:
    """Non-dominated mask for *maximization* (legacy)."""
    Y = np.asarray(Y, dtype=float)
    n = Y.shape[0]
    if n == 0:
        return np.zeros((0,), dtype=bool)
    mask = np.ones((n,), dtype=bool)
    for i in range(n):
        if not mask[i]:
            continue
        yi = Y[i]
        dominates = np.all(Y >= yi, axis=1) & np.any(Y > yi, axis=1)
        if np.any(dominates):
            mask[i] = False
            continue
        dominated_by_i = np.all(yi >= Y, axis=1) & np.any(yi > Y, axis=1)
        dominated_by_i[i] = False
        mask[dominated_by_i] = False
        mask[i] = True
    return mask


def pareto_front_2d_max(Y_max: np.ndarray) -> np.ndarray:
    """Pareto front for 2D *maximization* (legacy name).

    Returns a subset of points (same space as input) that are non-dominated.
    """
    Y = np.asarray(Y_max, dtype=float)
    if Y.size == 0:
        return Y.reshape((0, 2))
    if Y.ndim != 2 or Y.shape[1] != 2:
        raise ValueError("pareto_front_2d_max expects shape (n,2)")
    m = _pareto_mask_max(Y)
    return Y[m]


def choose_reference_point_max(
    Y_max: np.ndarray,
    *,
    margin: float = 0.10,
    quantile: float = 0.10,
) -> np.ndarray:
    """Choose a *maximization* reference point (worse than observed points).

    For maximization, the reference point must be <= all points.
    We take a low quantile and push it further down by `margin` of spread.
    """
    Y = np.asarray(Y_max, dtype=float)
    if Y.size == 0:
        raise ValueError("Cannot infer reference point from empty Y")

    q = np.quantile(Y, float(quantile), axis=0)
    spread = np.maximum(1e-12, np.quantile(Y, 0.95, axis=0) - np.quantile(Y, 0.05, axis=0))
    ref = q - float(margin) * spread
    # Ensure strictly worse (smaller) than all points
    ref = np.minimum(ref, np.min(Y, axis=0) - 1e-9)
    return ref


def hv_2d_max(Y_max: np.ndarray, ref_max: Sequence[float]) -> float:
    """2D hypervolume for *maximization* (legacy name).

    We reuse the minimization implementation by negating space:
    HV_max(Y, ref) == HV_min(-Y, -ref)
    """
    Y = np.asarray(Y_max, dtype=float)
    ref = np.asarray(ref_max, dtype=float)
    if Y.size == 0:
        return 0.0
    if Y.ndim != 2 or Y.shape[1] != 2:
        raise ValueError("hv_2d_max expects Y with shape (n,2)")
    return hypervolume_min_2d(-Y, -ref)


# -----------------------------------------------------------------------------
# Backward-compat aliases
# -----------------------------------------------------------------------------

def hypervolume_from_min(points: np.ndarray, ref_min: np.ndarray) -> float:
    """Compatibility alias (older tools import this name)."""
    return hypervolume_min(points=points, ref_min=ref_min)
