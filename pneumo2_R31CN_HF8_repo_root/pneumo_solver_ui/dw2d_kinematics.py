"""DW2D kinematics helpers (double wishbone – simplified 2D Y–Z).

Project context
---------------
The main mechanical model in this repository is a 7-DOF full-car vertical model
(heave + roll + pitch + 4 wheel vertical coordinates). It does *not* solve a full
multi-body double wishbone.

However, the suspension *mount geometry* is still important because it defines:

* the mapping wheel vertical travel -> cylinder stroke (motion ratio),
* the local nonlinearity of this mapping,
* the valid travel range (geometry must remain feasible).

The `dw2d_mounts_*` functions below implement a fully differentiable analytic
approximation in the Y–Z plane.

Assumptions
-----------
* Wheel vertical coordinate is the main independent coordinate: `dw`.
* Lower arm pivot point is fixed in the body frame: (y_piv, z_piv).
* The lower arm is a rigid link of length `L` between pivot and upright joint.
* The upright joint follows `z_joint = dw` and `y_joint` is resolved from arm length.
* Cylinder bottom mount is placed on the lower arm by a fraction `f` (0..1).
* Cylinder top mount is fixed in body frame: (±top_sep/2, top_z).

The mapping is symmetric between left/right – we use `sign_lr` (+1 right, -1 left).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class DW2DMountsParams:
    track_m: float
    pivot_inboard_m: float
    pivot_z_m: float
    lower_arm_len_m: float
    top_sep_m: float
    top_z_m: float
    low_frac: float


def dw2d_mounts_delta_rod_and_drod(
    dw: np.ndarray,
    p: DW2DMountsParams,
    sign_lr: float,
    eps_len_m: float = 1e-9,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
    """Return (delta_rod, drod_ddw, aux) for a DW2D mounts geometry.

    Convention (matches model_pneumo_v9_doublewishbone_camozzi):
    * Compression = dw > 0
    * Rod travel for compression should be positive: delta_rod(dw>0) > 0
    * Cylinder stroke variable `s` is computed as: s = s0 - delta_rod

    Parameters
    ----------
    dw:
        Wheel travel relative to body corner z_body [m]. Can be scalar or vector.
    p:
        Geometry parameters.
    sign_lr:
        +1 for right side, -1 for left side.

    Returns
    -------
    delta_rod:
        Positive for compression.
    drod_ddw:
        d(delta_rod)/d(dw).
    aux:
        Useful intermediate arrays (Lc, Lc0, y_bot, z_bot, y_joint, etc.).
    """
    dw = np.asarray(dw, dtype=float)

    # Wheel lateral position (center-to-center = track)
    y_wheel = float(sign_lr) * 0.5 * float(p.track_m)

    # Lower arm pivot point (inboard from wheel)
    y_piv = y_wheel - float(sign_lr) * float(p.pivot_inboard_m)
    z_piv = float(p.pivot_z_m)

    # Upright joint point (on the arm end)
    z_joint = dw
    dz = z_joint - z_piv
    L = float(p.lower_arm_len_m)

    # Geometric feasibility: L^2 - dz^2 must be > 0.
    rad2 = L * L - dz * dz
    rad2_clamped = np.maximum(rad2, eps_len_m * eps_len_m)
    root = np.sqrt(rad2_clamped)
    y_joint = y_piv + float(sign_lr) * root

    # d(y_joint)/d(dw)
    # y_joint = y_piv + sign * sqrt(L^2 - dz^2)
    # dy/dw = sign * (-dz) / sqrt(L^2 - dz^2)
    dyj_ddw = float(sign_lr) * (-dz) / root

    # Bottom mount along the lower arm (fraction f)
    f = float(p.low_frac)
    y_bot = y_piv + f * (y_joint - y_piv)
    z_bot = z_piv + f * (z_joint - z_piv)
    dy_bot_ddw = f * dyj_ddw
    dz_bot_ddw = f * np.ones_like(dw)

    # Top mount is fixed in body frame
    y_top = float(sign_lr) * 0.5 * float(p.top_sep_m)
    z_top = float(p.top_z_m)

    # Cylinder length
    dy = y_top - y_bot
    dz2 = z_top - z_bot
    Lc = np.sqrt(dy * dy + dz2 * dz2 + eps_len_m * eps_len_m)

    # dLc/ddw
    dL_ddw = -(dy * dy_bot_ddw + dz2 * dz_bot_ddw) / Lc

    # Choose sign so that delta_rod grows with compression (dw>0).
    # IMPORTANT: sign must be defined using derivative at dw=0 (static), not the
    # first sample of the provided dw array.
    dw0 = 0.0
    dz0 = dw0 - z_piv
    rad2_0 = L * L - dz0 * dz0
    root0 = float(np.sqrt(max(rad2_0, eps_len_m * eps_len_m)))
    y_joint0 = y_piv + float(sign_lr) * root0
    dyj_ddw0 = float(sign_lr) * (-dz0) / root0

    y_bot0 = y_piv + f * (y_joint0 - y_piv)
    z_bot0 = z_piv + f * (dw0 - z_piv)
    dy0 = y_top - y_bot0
    dz20 = z_top - z_bot0
    Lc0 = float(np.sqrt(dy0 * dy0 + dz20 * dz20 + eps_len_m * eps_len_m))

    dy_bot_ddw0 = f * dyj_ddw0
    dz_bot_ddw0 = f
    dL_ddw0 = float(-(dy0 * dy_bot_ddw0 + dz20 * dz_bot_ddw0) / Lc0)
    sign_s = -1.0 if dL_ddw0 > 0.0 else 1.0

    delta_rod = -sign_s * (Lc - Lc0)
    drod_ddw = -sign_s * dL_ddw

    aux = {
        "y_piv": np.asarray(y_piv, dtype=float),
        "z_piv": np.asarray(z_piv, dtype=float),
        "y_joint": y_joint,
        "z_joint": z_joint,
        "rad2": rad2,
        "y_bot": y_bot,
        "z_bot": z_bot,
        "y_top": np.asarray(y_top, dtype=float),
        "z_top": np.asarray(z_top, dtype=float),
        "Lc": Lc,
        "Lc0": np.asarray(Lc0, dtype=float),
        "dL_ddw": dL_ddw,
        "delta_rod": delta_rod,
        "drod_ddw": drod_ddw,
    }
    return delta_rod, drod_ddw, aux


def _pick(params: Dict, key: str, fallback: float) -> float:
    try:
        v = params.get(key, fallback)
        if v is None:
            return float(fallback)
        return float(v)
    except Exception:
        return float(fallback)


def build_dw2d_mounts_params_from_base(
    params: Dict,
    cyl: str,
    axle: str,
) -> DW2DMountsParams:
    """Extract geometry parameters for one cylinder (C1/C2) and axle (перед/зад)."""
    cyl = str(cyl).strip().upper()
    axle = str(axle).strip().lower()
    if axle not in ("перед", "зад"):
        raise ValueError(f"axle must be 'перед' or 'зад', got {axle!r}")
    if cyl not in ("C1", "C2"):
        raise ValueError(f"cyl must be 'C1' or 'C2', got {cyl!r}")

    track_m = _pick(params, "колея", 1.0)

    # Lower arm geometry (front/rear)
    if axle == "перед":
        pivot_inboard_m = _pick(params, "dw_lower_pivot_inboard_перед_м", 0.25)
        pivot_z_m = _pick(params, "dw_lower_pivot_z_перед_м", 0.0)
        lower_arm_len_m = _pick(params, "dw_lower_arm_len_перед_м", 0.55)
    else:
        pivot_inboard_m = _pick(params, "dw_lower_pivot_inboard_зад_м", 0.25)
        pivot_z_m = _pick(params, "dw_lower_pivot_z_зад_м", -0.02)
        lower_arm_len_m = _pick(params, "dw_lower_arm_len_зад_м", 0.52)

    # Cylinder mount geometry
    if axle == "перед":
        top_sep_m = _pick(params, f"верх_{cyl}_перед_между_ЛП_ПП_м", 0.55)
        top_z_m = _pick(params, f"верх_{cyl}_перед_z_относительно_рамы_м", 0.25)
        low_frac = _pick(params, f"низ_{cyl}_перед_доля_рычага", 0.7)
    else:
        top_sep_m = _pick(params, f"верх_{cyl}_зад_между_ЛЗ_ПЗ_м", 0.55)
        top_z_m = _pick(params, f"верх_{cyl}_зад_z_относительно_рамы_м", 0.25)
        low_frac = _pick(params, f"низ_{cyl}_зад_доля_рычага", 0.7)

    return DW2DMountsParams(
        track_m=track_m,
        pivot_inboard_m=pivot_inboard_m,
        pivot_z_m=pivot_z_m,
        lower_arm_len_m=lower_arm_len_m,
        top_sep_m=top_sep_m,
        top_z_m=top_z_m,
        low_frac=low_frac,
    )


def validate_dw2d_mounts(
    p: DW2DMountsParams,
    dw_samples_m: np.ndarray,
    name: str = "",
    eps_len_m: float = 1e-9,
) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) for one mounts configuration.

    The checks are intentionally conservative – they are meant to prevent silent
    clamping of invalid geometry (sqrt of negative).
    """
    errors: List[str] = []
    warnings: List[str] = []
    prefix = f"[{name}] " if name else ""

    if not np.isfinite(p.track_m) or p.track_m <= 0:
        errors.append(prefix + f"track_m must be >0, got {p.track_m}")
    if not np.isfinite(p.lower_arm_len_m) or p.lower_arm_len_m <= 0:
        errors.append(prefix + f"lower_arm_len_m must be >0, got {p.lower_arm_len_m}")
    if not np.isfinite(p.pivot_inboard_m) or p.pivot_inboard_m < 0:
        errors.append(prefix + f"pivot_inboard_m must be >=0, got {p.pivot_inboard_m}")
    if not np.isfinite(p.top_sep_m) or p.top_sep_m <= 0:
        errors.append(prefix + f"top_sep_m must be >0, got {p.top_sep_m}")
    if not np.isfinite(p.top_z_m):
        errors.append(prefix + f"top_z_m must be finite, got {p.top_z_m}")
    if not np.isfinite(p.low_frac) or not (0.0 <= p.low_frac <= 1.0):
        errors.append(prefix + f"low_frac must be in [0..1], got {p.low_frac}")

    if errors:
        return errors, warnings

    dw_samples_m = np.asarray(dw_samples_m, dtype=float)
    if dw_samples_m.size == 0:
        warnings.append(prefix + "dw_samples is empty; skipping travel feasibility checks")
        return errors, warnings

    # Use right side for feasibility (left is symmetric)
    sign_lr = +1.0
    _, drod_ddw, aux = dw2d_mounts_delta_rod_and_drod(dw_samples_m, p, sign_lr=sign_lr, eps_len_m=eps_len_m)

    rad2 = aux.get("rad2")
    if rad2 is not None:
        rad2 = np.asarray(rad2, dtype=float)
        if np.any(rad2 <= 0.0):
            # Provide worst-case
            m = float(np.min(rad2))
            errors.append(prefix + f"lower arm geometry infeasible in dw range: min(L^2-dz^2)={m:.6g} <= 0")
        elif float(np.min(rad2)) < (0.01 * p.lower_arm_len_m) ** 2:
            warnings.append(prefix + "geometry close to singularity (L^2-dz^2 small) in the chosen dw range")

    drod_ddw = np.asarray(drod_ddw, dtype=float)
    if np.any(~np.isfinite(drod_ddw)):
        errors.append(prefix + "non-finite drod_ddw detected")
    else:
        if np.any(drod_ddw <= 0.0):
            warnings.append(prefix + "drod_ddw became <= 0 in the chosen range (rod travel not monotonic)")
        # derivative at static (dw=0)
        try:
            _, drod0_arr, _ = dw2d_mounts_delta_rod_and_drod(np.asarray([0.0]), p, sign_lr=sign_lr, eps_len_m=eps_len_m)
            drod0 = float(np.asarray(drod0_arr, dtype=float).ravel()[0])
        except Exception:
            drod0 = float(drod_ddw.ravel()[len(drod_ddw.ravel()) // 2])
        if drod0 < 1e-6:
            warnings.append(prefix + f"very small drod_ddw at dw=0: {drod0:.3e} (motion ratio is huge)")

    return errors, warnings


def dw2d_geometry_report_from_params(
    params: Dict,
    dw_test_range_m: Tuple[float, float] = (-0.15, 0.15),
    n_samples: int = 101,
) -> Dict[str, Dict[str, List[str]]]:
    """Build a structured report (errors/warnings) for all DW2D mount groups.

    Returns dict like:
    {
      "C1_перед": {"errors": [...], "warnings": [...]},
      "C2_перед": ...,
      ...
    }
    """
    a, b = float(dw_test_range_m[0]), float(dw_test_range_m[1])
    if n_samples < 3:
        n_samples = 3
    dw_samples = np.linspace(a, b, int(n_samples))

    report: Dict[str, Dict[str, List[str]]] = {}
    for axle in ("перед", "зад"):
        for cyl in ("C1", "C2"):
            name = f"{cyl}_{axle}"
            try:
                p = build_dw2d_mounts_params_from_base(params, cyl=cyl, axle=axle)
                errors, warnings = validate_dw2d_mounts(p, dw_samples_m=dw_samples, name=name)
            except Exception as e:
                errors, warnings = [f"[{name}] failed to build/validate: {e}"], []
            report[name] = {"errors": errors, "warnings": warnings}

    return report
