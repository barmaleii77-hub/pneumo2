# -*- coding: utf-8 -*-
"""Pure helpers for sub-frame playback sampling in the desktop animator.

The desktop player is intentionally display-oriented: the GUI wakes at a limited
cadence, while the exported bundle can contain much denser source samples.
These helpers let the renderer evaluate geometry at the *continuous* playhead
position instead of snapping every visible frame to the nearest source row.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np


def sample_time_bracket(
    t_axis: np.ndarray,
    *,
    sample_t: float | None,
    fallback_index: int,
) -> tuple[int, int, float, float]:
    """Return ``(i0, i1, alpha, sample_t_clamped)`` for a continuous playhead time.

    ``alpha`` is the interpolation fraction between source rows ``i0`` and ``i1``.
    Degenerate cases collapse to ``i0 == i1`` and ``alpha == 0``.
    """
    t = np.asarray(t_axis, dtype=float).reshape(-1)
    if t.size == 0:
        return 0, 0, 0.0, 0.0
    fb = int(max(0, min(int(fallback_index), int(t.size) - 1)))
    if sample_t is None or not math.isfinite(float(sample_t)):
        return fb, fb, 0.0, float(t[fb])
    if t.size == 1:
        return 0, 0, 0.0, float(t[0])

    ts = float(np.clip(float(sample_t), float(t[0]), float(t[-1])))
    right = int(np.searchsorted(t, ts, side="right"))
    if right <= 0:
        return 0, 0, 0.0, float(t[0])
    if right >= int(t.size):
        last = int(t.size) - 1
        return last, last, 0.0, float(t[last])

    i0 = max(0, right - 1)
    i1 = min(int(t.size) - 1, right)
    if i0 == i1:
        return i0, i1, 0.0, ts
    dt = float(t[i1] - t[i0])
    if not math.isfinite(dt) or dt <= 1e-12:
        return i0, i0, 0.0, ts
    alpha = float(np.clip((ts - float(t[i0])) / dt, 0.0, 1.0))
    if alpha <= 1e-12:
        return i0, i0, 0.0, ts
    if alpha >= 1.0 - 1e-12:
        return i1, i1, 0.0, ts
    return i0, i1, alpha, ts


def lerp_series_value(
    series: np.ndarray | list[float] | tuple[float, ...],
    *,
    i0: int,
    i1: int,
    alpha: float,
    default: float = 0.0,
) -> float:
    """Return a finite scalar sample from a 1D series.

    If one endpoint is finite and the other is not, the finite endpoint wins.
    """
    arr = np.asarray(series, dtype=float).reshape(-1)
    if arr.size == 0:
        return float(default)
    a = int(max(0, min(int(i0), int(arr.size) - 1)))
    b = int(max(0, min(int(i1), int(arr.size) - 1)))
    v0 = float(arr[a])
    if a == b or alpha <= 1e-12:
        return v0 if math.isfinite(v0) else float(default)
    v1 = float(arr[b])
    if math.isfinite(v0) and math.isfinite(v1):
        return float((1.0 - float(alpha)) * v0 + float(alpha) * v1)
    if math.isfinite(v0):
        return v0
    if math.isfinite(v1):
        return v1
    return float(default)


def lerp_wrapped_angle_value(
    series: np.ndarray | list[float] | tuple[float, ...],
    *,
    i0: int,
    i1: int,
    alpha: float,
    default: float = 0.0,
    period: float = 2.0 * math.pi,
) -> float:
    """Return a shortest-path interpolated angle from a wrapped 1D series.

    This avoids false large jumps when the source crosses the wrap boundary
    (for example, yaw moving from ``+pi`` to ``-pi``).
    """
    arr = np.asarray(series, dtype=float).reshape(-1)
    if arr.size == 0:
        return float(default)
    a = int(max(0, min(int(i0), int(arr.size) - 1)))
    b = int(max(0, min(int(i1), int(arr.size) - 1)))
    v0 = float(arr[a])
    if a == b or alpha <= 1e-12:
        return v0 if math.isfinite(v0) else float(default)
    v1 = float(arr[b])
    if not math.isfinite(v0) and not math.isfinite(v1):
        return float(default)
    if not math.isfinite(v0):
        return v1
    if not math.isfinite(v1):
        return v0
    period_v = float(abs(period))
    if not math.isfinite(period_v) or period_v <= 1e-12:
        return float((1.0 - float(alpha)) * v0 + float(alpha) * v1)
    half = 0.5 * period_v
    delta = float((v1 - v0 + half) % period_v) - half
    out = float(v0 + float(alpha) * delta)
    return float((out + half) % period_v) - half


def lerp_point_row(
    rows_xyz: np.ndarray,
    *,
    i0: int,
    i1: int,
    alpha: float,
) -> Optional[np.ndarray]:
    """Return an interpolated ``(3,)`` point from a ``(T,3)`` series or ``None``."""
    arr = np.asarray(rows_xyz, dtype=float)
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] != 3:
        return None
    a = int(max(0, min(int(i0), int(arr.shape[0]) - 1)))
    b = int(max(0, min(int(i1), int(arr.shape[0]) - 1)))
    p0 = np.asarray(arr[a], dtype=float).reshape(3)
    if a == b or alpha <= 1e-12:
        return p0 if np.all(np.isfinite(p0)) else None
    p1 = np.asarray(arr[b], dtype=float).reshape(3)
    p0_ok = bool(np.all(np.isfinite(p0)))
    p1_ok = bool(np.all(np.isfinite(p1)))
    if p0_ok and p1_ok:
        return ((1.0 - float(alpha)) * p0 + float(alpha) * p1).astype(float)
    if p0_ok:
        return p0.astype(float)
    if p1_ok:
        return p1.astype(float)
    return None
