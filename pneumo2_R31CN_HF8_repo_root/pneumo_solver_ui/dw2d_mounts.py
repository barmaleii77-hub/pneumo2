# -*- coding: utf-8 -*-
"""dw2d_mounts.py

Compatibility layer for the DW2D (double wishbone simplified 2D) geometry helpers.

Why this file exists
--------------------
The project contains an analytic, fully differentiable approximation of a
(double wishbone) suspension *mount geometry* in the Y–Z plane. The
implementation lives in ``dw2d_kinematics.py``.

Historically the UI code imported these helpers from a module named
``dw2d_mounts``. Some distributions missed that module, which made the page
"Геометрия подвески (DW2D)" fail to import.

This file re-exports the implementation from ``dw2d_kinematics`` and provides a
small helper ``validate_dw2d_params(...)`` expected by the UI.

Notes
-----
* The geometry model is *not* a full multi-body double wishbone solver.
  It only defines the mapping ``dw -> delta_rod`` (motion ratio) for a cylinder
  mounted to the lower arm, with conservative feasibility checks.
* All functions here are pure / side-effect free (except for validation raising
  an error).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .dw2d_kinematics import (
    DW2DMountsParams,
    build_dw2d_mounts_params_from_base,
    dw2d_geometry_report_from_params,
    dw2d_mounts_delta_rod_and_drod,
    validate_dw2d_mounts,
)

__all__ = [
    'DW2DMountsParams',
    'dw2d_mounts_delta_rod_and_drod',
    'build_dw2d_mounts_params_from_base',
    'validate_dw2d_mounts',
    'dw2d_geometry_report_from_params',
    'validate_dw2d_params',
]


def validate_dw2d_params(
    params: Dict[str, Any],
    *,
    dw_test_range_m: Tuple[float, float] = (-0.15, 0.15),
    n_samples: int = 61,
) -> List[str]:
    """Validate that the current DW2D geometry parameters are usable.

    Returns a list of *warnings* (strings). If there are any errors, raises
    ``ValueError``.

    The UI uses this function to provide quick feedback and to prevent silent
    clamping of invalid geometry (sqrt of negative for the lower arm).
    """
    rep = dw2d_geometry_report_from_params(
        params,
        dw_test_range_m=dw_test_range_m,
        n_samples=int(n_samples),
    )

    errors: List[str] = []
    warnings: List[str] = []
    for _, r in (rep or {}).items():
        if isinstance(r, dict):
            errors.extend(list(r.get('errors', []) or []))
            warnings.extend(list(r.get('warnings', []) or []))

    if errors:
        # Keep the message compact but informative.
        msg = '; '.join(errors[:6]) + (' ...' if len(errors) > 6 else '')
        raise ValueError('DW2D geometry invalid: ' + msg)

    return warnings
