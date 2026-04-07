# -*- coding: utf-8 -*-
"""Geometry acceptance helpers for Desktop Animator.

These checks tie together three explicit solver-point triplets for each corner:
- frame_corner
- wheel_center
- road_contact

No synthetic geometry is reconstructed here. If a triplet is missing, the caller
must surface the missing-data state explicitly.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from .data_bundle import CORNERS, DataBundle


def _series_or_none(bundle: DataBundle, name: str) -> np.ndarray | None:
    col = bundle.main.column(name, default=None)
    if col is None:
        return None
    try:
        return np.asarray(col, dtype=float)
    except Exception:
        return None


def _nanmax_abs(arr: np.ndarray | None) -> float:
    if arr is None:
        return 0.0
    try:
        a = np.asarray(arr, dtype=float)
        if a.size == 0:
            return 0.0
        mask = np.isfinite(a)
        if not np.any(mask):
            return 0.0
        return float(np.nanmax(np.abs(a[mask])))
    except Exception:
        return 0.0



def corner_acceptance_arrays(bundle: DataBundle, corner: str) -> Dict[str, Any]:
    """Return cached frame/wheel/road acceptance arrays for one corner.

    Keys:
      ok, missing_triplets,
      frame_xyz, wheel_xyz, road_xyz,
      frame_road_m, wheel_road_m, wheel_frame_m,
      invariant_err_m,
      xy_err_frame_wheel_m, xy_err_wheel_road_m, xy_err_frame_road_m,
      scalar_err_frame_road_m, scalar_err_wheel_road_m, scalar_err_wheel_frame_m
    """
    key = f"_geometry_acceptance::{corner}"
    cached = bundle._derived.get(key)  # pylint: disable=protected-access
    if isinstance(cached, dict):
        return cached

    frame_xyz = bundle.frame_corner_xyz(corner)
    wheel_xyz = bundle.wheel_center_xyz(corner)
    road_xyz = bundle.road_contact_xyz(corner)

    missing: List[str] = []
    if frame_xyz is None:
        missing.append(f"frame_corner/{corner}")
    if wheel_xyz is None:
        missing.append(f"wheel_center/{corner}")
    if road_xyz is None:
        missing.append(f"road_contact/{corner}")

    if missing:
        out: Dict[str, Any] = {
            "corner": corner,
            "ok": False,
            "missing_triplets": missing,
        }
        bundle._derived[key] = out  # pylint: disable=protected-access
        return out

    frame_xyz = np.asarray(frame_xyz, dtype=float)
    wheel_xyz = np.asarray(wheel_xyz, dtype=float)
    road_xyz = np.asarray(road_xyz, dtype=float)

    frame_road = frame_xyz[:, 2] - road_xyz[:, 2]
    wheel_road = wheel_xyz[:, 2] - road_xyz[:, 2]
    wheel_frame = wheel_xyz[:, 2] - frame_xyz[:, 2]
    invariant = wheel_road - (wheel_frame + frame_road)

    xy_fw = np.linalg.norm(frame_xyz[:, :2] - wheel_xyz[:, :2], axis=1)
    xy_wr = np.linalg.norm(wheel_xyz[:, :2] - road_xyz[:, :2], axis=1)
    xy_fr = np.linalg.norm(frame_xyz[:, :2] - road_xyz[:, :2], axis=1)

    scalar_fr = _series_or_none(bundle, f"рама_относительно_дороги_{corner}_м")
    scalar_wr = _series_or_none(bundle, f"колесо_относительно_дороги_{corner}_м")
    scalar_wf = _series_or_none(bundle, f"колесо_относительно_рамы_{corner}_м")

    out = {
        "corner": corner,
        "ok": True,
        "missing_triplets": [],
        "frame_xyz": frame_xyz,
        "wheel_xyz": wheel_xyz,
        "road_xyz": road_xyz,
        "frame_road_m": frame_road,
        "wheel_road_m": wheel_road,
        "wheel_frame_m": wheel_frame,
        "invariant_err_m": invariant,
        "xy_err_frame_wheel_m": xy_fw,
        "xy_err_wheel_road_m": xy_wr,
        "xy_err_frame_road_m": xy_fr,
        "scalar_err_frame_road_m": (scalar_fr - frame_road) if scalar_fr is not None else None,
        "scalar_err_wheel_road_m": (scalar_wr - wheel_road) if scalar_wr is not None else None,
        "scalar_err_wheel_frame_m": (scalar_wf - wheel_frame) if scalar_wf is not None else None,
    }
    bundle._derived[key] = out  # pylint: disable=protected-access
    return out



def collect_acceptance_status(bundle: DataBundle, *, tol_m: float = 1e-6) -> Dict[str, Any]:
    """Aggregate cached geometry acceptance status across all corners."""
    cache_key = "_geometry_acceptance_summary"
    cached = bundle._derived.get(cache_key)  # pylint: disable=protected-access
    if isinstance(cached, dict):
        return cached

    corners: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    max_inv = 0.0
    max_xy = 0.0
    max_xy_fw = 0.0
    max_xy_fr = 0.0
    max_fr = 0.0
    max_wr = 0.0
    max_wf = 0.0
    for c in CORNERS:
        acc = corner_acceptance_arrays(bundle, c)
        corners[c] = acc
        if not acc.get("ok", False):
            missing.extend(list(acc.get("missing_triplets") or []))
            continue
        max_inv = max(max_inv, _nanmax_abs(acc.get("invariant_err_m")))
        max_xy = max(max_xy, _nanmax_abs(acc.get("xy_err_wheel_road_m")))
        max_xy_fw = max(max_xy_fw, _nanmax_abs(acc.get("xy_err_frame_wheel_m")))
        max_xy_fr = max(max_xy_fr, _nanmax_abs(acc.get("xy_err_frame_road_m")))
        max_fr = max(max_fr, _nanmax_abs(acc.get("scalar_err_frame_road_m")))
        max_wr = max(max_wr, _nanmax_abs(acc.get("scalar_err_wheel_road_m")))
        max_wf = max(max_wf, _nanmax_abs(acc.get("scalar_err_wheel_frame_m")))

    ok = (not missing) and max(max_inv, max_xy, max_fr, max_wr, max_wf) <= float(tol_m)
    out = {
        "ok": bool(ok),
        "tol_m": float(tol_m),
        "missing_triplets": missing,
        "corners": corners,
        "max_invariant_err_m": float(max_inv),
        "max_xy_err_m": float(max_xy),
        "max_xy_frame_wheel_offset_m": float(max_xy_fw),
        "max_xy_frame_road_offset_m": float(max_xy_fr),
        "max_scalar_err_frame_road_m": float(max_fr),
        "max_scalar_err_wheel_road_m": float(max_wr),
        "max_scalar_err_wheel_frame_m": float(max_wf),
    }
    bundle._derived[cache_key] = out  # pylint: disable=protected-access
    return out



def format_acceptance_hud_lines(bundle: DataBundle, i: int) -> list[str]:
    """Compact Russian HUD lines for frame/wheel/road acceptance."""
    status = collect_acceptance_status(bundle)
    missing = list(status.get("missing_triplets") or [])
    if missing:
        preview = ", ".join(missing[:2])
        if len(missing) > 2:
            preview += f", +{len(missing) - 2}"
        return [f"Геом.check: отсутствуют triplet-ы ({preview})"]

    frame_road_vals = []
    wheel_road_vals = []
    for c in CORNERS:
        acc = corner_acceptance_arrays(bundle, c)
        frame_road_vals.append(float(np.asarray(acc["frame_road_m"], dtype=float)[i]))
        wheel_road_vals.append(float(np.asarray(acc["wheel_road_m"], dtype=float)[i]))

    fr_min = min(frame_road_vals) if frame_road_vals else float("nan")
    wr_min = min(wheel_road_vals) if wheel_road_vals else float("nan")
    max_inv_mm = float(status.get("max_invariant_err_m", 0.0)) * 1000.0
    max_xy_mm = float(status.get("max_xy_err_m", 0.0)) * 1000.0
    max_xy_fw_mm = float(status.get("max_xy_frame_wheel_offset_m", 0.0)) * 1000.0
    max_xy_fr_mm = float(status.get("max_xy_frame_road_offset_m", 0.0)) * 1000.0
    max_fr_mm = float(status.get("max_scalar_err_frame_road_m", 0.0)) * 1000.0
    max_wr_mm = float(status.get("max_scalar_err_wheel_road_m", 0.0)) * 1000.0
    max_wf_mm = float(status.get("max_scalar_err_wheel_frame_m", 0.0)) * 1000.0

    return [
        f"Геом.: рама‑дорога min {fr_min:+.3f} м   колесо‑дорога min {wr_min:+.3f} м",
        f"Check max: Σ {max_inv_mm:.3f} мм   XYwr {max_xy_mm:.3f} мм   XYfw/XYfr {max_xy_fw_mm:.3f}/{max_xy_fr_mm:.3f} мм   WF/WR/FR {max_wf_mm:.3f}/{max_wr_mm:.3f}/{max_fr_mm:.3f} мм",
    ]
