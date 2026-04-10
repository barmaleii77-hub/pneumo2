"""Static weight distribution helper for 4-corner suspension models.

The project requires a *zero pose* with a flat road and a physically consistent
static state. For realistic initial conditions we often want the sprung mass
(body/frame) weight to be distributed per corner based on CG offsets instead of
always m*g/4.

Why there are multiple modes
----------------------------
A rigid body supported at four points is *statically indeterminate* if we only
use the 3 equilibrium equations (sum of forces and two moments). To pick a
unique set of corner reactions we need extra information. In this project we
use the reactions mostly for:

  - initial tyre deflection (zw0) in the zero pose;
  - preload targets (x0) for springs / cylinders;
  - diagnostics in df_atm (so we can see what initialisation assumed).

Therefore we implement two modes:

  1) mode="cg" (default):
     Separable approximation front/rear × left/right derived from CG offsets.

  2) mode="stiffness":
     Choose a unique set of reactions by assuming each corner has an effective
     vertical stiffness k_i (N/m) between the body and the ground and solving
     the *minimum strain energy* equilibrium for (z, roll, pitch) in a linear
     small-angle model. This resolves the indeterminacy and is useful to model
     cross-weight effects for asymmetric k_i.

Coordinate convention
---------------------
We assume the same body coordinate system as the mechanical models:
  x: forward  (front axle at +wheelbase/2, rear at -wheelbase/2)
  y: left     (left wheels at +track/2, right at -track/2)

CG offsets are defined relative to the midpoint between axles and the vehicle
centerline:
  cg_x_m > 0  -> CG shifted forward
  cg_y_m > 0  -> CG shifted to the left

Corner order is project convention:
  [FL, FR, RL, RR]  which corresponds to  ['ЛП','ПП','ЛЗ','ПЗ'].

"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Dict, Iterable, Tuple, Optional

import numpy as np


@dataclass
class CornerLoadReport:
    """Diagnostic report for weight distribution."""

    F_body_corner_N: np.ndarray
    cg_x_m: float
    cg_y_m: float
    cg_x_used_m: float
    cg_y_used_m: float
    cg_x_clipped: bool
    cg_y_clipped: bool
    front_frac: float
    rear_frac: float
    left_frac: float
    right_frac: float
    msg: str

    # New (v659): indeterminacy-resolving mode and diagnostics
    mode: str = 'cg'
    cross_weight_frac: float = float('nan')   # (FL+RR)/W
    diag_bias_N: float = float('nan')         # (FL+RR) - (FR+RL)
    k_corner_N_m: Optional[np.ndarray] = None
    q_z_m: float = float('nan')
    q_phi_rad: float = float('nan')
    q_theta_rad: float = float('nan')
    cond_M: float = float('nan')
    solver_kind: str = 'n/a'
    active_support_mask: Optional[np.ndarray] = None
    active_support_count: int = 0
    eq_force_residual_N: float = float('nan')
    eq_roll_residual_Nm: float = float('nan')
    eq_pitch_residual_Nm: float = float('nan')
    strain_energy_J: float = float('nan')

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            'F_body_corner_N': [float(x) for x in np.asarray(self.F_body_corner_N, dtype=float).ravel().tolist()],
            'cg_x_m': float(self.cg_x_m),
            'cg_y_m': float(self.cg_y_m),
            'cg_x_used_m': float(self.cg_x_used_m),
            'cg_y_used_m': float(self.cg_y_used_m),
            'cg_x_clipped': bool(self.cg_x_clipped),
            'cg_y_clipped': bool(self.cg_y_clipped),
            'front_frac': float(self.front_frac),
            'rear_frac': float(self.rear_frac),
            'left_frac': float(self.left_frac),
            'right_frac': float(self.right_frac),
            'msg': str(self.msg),
            'mode': str(self.mode),
            'cross_weight_frac': float(self.cross_weight_frac),
            'diag_bias_N': float(self.diag_bias_N),
            'q_z_m': float(self.q_z_m),
            'q_phi_rad': float(self.q_phi_rad),
            'q_theta_rad': float(self.q_theta_rad),
            'cond_M': float(self.cond_M),
            'solver_kind': str(self.solver_kind),
            'active_support_count': int(self.active_support_count),
            'eq_force_residual_N': float(self.eq_force_residual_N),
            'eq_roll_residual_Nm': float(self.eq_roll_residual_Nm),
            'eq_pitch_residual_Nm': float(self.eq_pitch_residual_Nm),
            'strain_energy_J': float(self.strain_energy_J),
        }
        if self.k_corner_N_m is not None:
            out['k_corner_N_m'] = [float(x) for x in np.asarray(self.k_corner_N_m, dtype=float).ravel().tolist()]
        if self.active_support_mask is not None:
            out['active_support_mask'] = [bool(x) for x in np.asarray(self.active_support_mask, dtype=bool).ravel().tolist()]
        return out


def parse_cg_offsets(params: Dict[str, Any]) -> Tuple[float, float]:
    """Parse CG offsets from params.

    Supported keys (synonyms):
      cg_x_м, cg_y_м, cg_x_m, cg_y_m,
      x_cg_м, y_cg_м, x_cg_m, y_cg_m,
      смещение_цт_x_м, смещение_цт_y_м,
      цт_x_м, цт_y_м.

    Missing keys default to 0.
    """

    def _get(keys: Iterable[str]) -> float:
        for k in keys:
            if k in params:
                try:
                    return float(params.get(k, 0.0))
                except Exception:
                    return 0.0
        return 0.0

    cg_x = _get(['cg_x_м', 'cg_x_m', 'x_cg_м', 'x_cg_m', 'смещение_цт_x_м', 'цт_x_м'])
    cg_y = _get(['cg_y_м', 'cg_y_m', 'y_cg_м', 'y_cg_m', 'смещение_цт_y_м', 'цт_y_м'])
    return float(cg_x), float(cg_y)


def parse_cg_offsets_with_geom(
    params: Dict[str, Any],
    wheelbase_m: Optional[float] = None,
    track_m: Optional[float] = None,
) -> Tuple[float, float]:
    """Parse CG offsets with optional geometry-aware conversions.

    Primary convention (recommended)
    -------------------------------
    Use cg_x_м / cg_y_м (or *_m) as offsets relative to the midpoint between
    axles and the vehicle centerline:
      cg_x_m > 0 -> CG forward
      cg_y_m > 0 -> CG left

    Additional supported key
    ------------------------
    Some models already use *distance from the front axle*:
      x_cg_от_передней_оси_м / x_cg_from_front_m

    If cg_x_* keys are not provided but x_cg_from_front is provided and
    wheelbase_m is known, we convert:
      cg_x = wheelbase/2 - x_from_front

    (x_from_front is assumed positive rearwards along the wheelbase.)

    This helper keeps backward compatibility across project versions.
    """

    cg_x_keys = ['cg_x_м', 'cg_x_m', 'x_cg_м', 'x_cg_m', 'смещение_цт_x_м', 'цт_x_м']
    cg_y_keys = ['cg_y_м', 'cg_y_m', 'y_cg_м', 'y_cg_m', 'смещение_цт_y_м', 'цт_y_м']

    has_cg_x = any(k in params for k in cg_x_keys)
    has_cg_y = any(k in params for k in cg_y_keys)

    cg_x_m, cg_y_m = parse_cg_offsets(params)

    # Geometry-aware fallback for longitudinal CG
    if (not has_cg_x):
        for k in ['x_cg_от_передней_оси_м', 'x_cg_from_front_m', 'cg_x_from_front_m']:
            if k in params and (wheelbase_m is not None) and (float(wheelbase_m) > 0.0):
                try:
                    x_from_front = float(params.get(k, 0.5*float(wheelbase_m)))
                except Exception:
                    x_from_front = 0.5*float(wheelbase_m)
                # Clip inside [0, wheelbase] for safety
                x_from_front = float(np.clip(x_from_front, 0.0, float(wheelbase_m)))
                cg_x_m = 0.5*float(wheelbase_m) - x_from_front
                break

    # Optional alternative y key (from centerline)
    if (not has_cg_y):
        for k in ['y_cg_от_центра_м', 'y_cg_from_center_m']:
            if k in params:
                try:
                    cg_y_m = float(params.get(k, 0.0))
                except Exception:
                    cg_y_m = 0.0
                break

    return float(cg_x_m), float(cg_y_m)


def parse_corner_loads_mode(params: Dict[str, Any], default: str = 'cg') -> str:
    """Parse corner loads mode from params with backward-compatible keys."""
    keys = [
        'corner_loads_mode',
        'режим_нагрузки_углы',
        'углы_нагрузка_режим',
        'corner_load_mode',
        'corner_loads',
    ]
    for k in keys:
        if k in params:
            try:
                return str(params.get(k, default)).strip().lower()
            except Exception:
                return str(default).strip().lower()
    return str(default).strip().lower()


def parse_corner_stiffness(
    params: Dict[str, Any],
    k_default_N_m: float,
    corner_order: Optional[Iterable[str]] = None,
) -> np.ndarray:
    """Parse per-corner effective vertical stiffness k_i (N/m).

    Supported inputs:
      - k_corner_N_m / k_corner_loads_N_m : list/tuple length 4
      - жёсткость_угла_Н_м / жесткость_угла_Н_м : list/tuple length 4
      - per-corner keys (if corner_order provided):
          k_corner_ЛП_Н_м, k_corner_ПП_Н_м, k_corner_ЛЗ_Н_м, k_corner_ПЗ_Н_м
          жёсткость_угла_ЛП_Н_м, ...
          k_corner_FL_N_m, k_corner_FR_N_m, k_corner_RL_N_m, k_corner_RR_N_m

    Missing values fall back to k_default_N_m.
    """
    k_default = float(k_default_N_m) if (k_default_N_m is not None) else 0.0
    k_default = float(k_default) if np.isfinite(k_default) and (k_default > 0.0) else 0.0

    # 1) vector form
    for k in [
        'k_corner_N_m', 'k_corner_loads_N_m',
        'жёсткость_угла_Н_м', 'жесткость_угла_Н_м',
        'жёсткость_угла_н_м', 'жесткость_угла_н_м',
    ]:
        if k in params:
            try:
                arr = np.asarray(params.get(k), dtype=float).ravel()
                if arr.size == 4:
                    out = arr.astype(float).copy()
                    out[~np.isfinite(out)] = k_default
                    out = np.where(out > 0.0, out, k_default)
                    return out
            except Exception:
                pass

    # 2) per-corner keys
    if corner_order is None:
        corner_order = ['ЛП', 'ПП', 'ЛЗ', 'ПЗ']

    mapping_ru = {
        'ЛП': ('FL', 'LF'),
        'ПП': ('FR', 'RF'),
        'ЛЗ': ('RL', 'LR'),
        'ПЗ': ('RR', 'RR'),
    }

    out = np.ones(4, dtype=float) * k_default
    for i, cname in enumerate(list(corner_order)[:4]):
        keys = []
        keys += [f'k_corner_{cname}_Н_м', f'k_corner_{cname}_N_m']
        keys += [f'жёсткость_угла_{cname}_Н_м', f'жесткость_угла_{cname}_Н_м']
        keys += [f'жёсткость_угла_{cname}_N_m', f'жесткость_угла_{cname}_N_m']
        if cname in mapping_ru:
            for en in mapping_ru[cname]:
                keys += [f'k_corner_{en}_N_m', f'k_corner_{en}_Н_м']
                keys += [f'corner_k_{en}_N_m', f'corner_k_{en}_Н_м']
        for kk in keys:
            if kk in params:
                try:
                    v = float(params.get(kk))
                    if np.isfinite(v) and (v > 0.0):
                        out[i] = v
                except Exception:
                    pass
                break
    out[~np.isfinite(out)] = k_default
    out = np.where(out > 0.0, out, k_default)
    return out



def corner_stiffness_user_provided(params: Dict[str, Any], corner_order: Optional[Iterable[str]] = None) -> bool:
    """Return True if user explicitly provided any k_corner* parameter.

    Важно:
    - Проверка нужна, чтобы отличить *дефолт* (k_default) от явного ввода.
    - Значения должны быть конечными и >0.
    """
    # vector forms
    for k in [
        'k_corner_N_m', 'k_corner_loads_N_m',
        'жёсткость_угла_Н_м', 'жесткость_угла_Н_м',
        'жёсткость_угла_н_м', 'жесткость_угла_н_м',
    ]:
        if k in params:
            try:
                arr = np.asarray(params.get(k), dtype=float).ravel()
                if arr.size == 4 and np.all(np.isfinite(arr)) and np.all(arr > 0.0):
                    return True
                # даже если часть задана — считаем, что пользователь пытался задать
                if arr.size == 4 and np.any(np.isfinite(arr) & (arr > 0.0)):
                    return True
            except Exception:
                return True

    if corner_order is None:
        corner_order = ['ЛП', 'ПП', 'ЛЗ', 'ПЗ']

    mapping_ru = {
        'ЛП': ('FL', 'LF'),
        'ПП': ('FR', 'RF'),
        'ЛЗ': ('RL', 'LR'),
        'ПЗ': ('RR', 'RR'),
    }

    for cname in list(corner_order)[:4]:
        keys = []
        keys += [f'k_corner_{cname}_Н_м', f'k_corner_{cname}_N_m']
        keys += [f'жёсткость_угла_{cname}_Н_м', f'жесткость_угла_{cname}_Н_м']
        keys += [f'жёсткость_угла_{cname}_N_m', f'жесткость_угла_{cname}_N_m']
        if cname in mapping_ru:
            for en in mapping_ru[cname]:
                keys += [f'k_corner_{en}_N_m', f'k_corner_{en}_Н_м']
                keys += [f'corner_k_{en}_N_m', f'corner_k_{en}_Н_м']
        for kk in keys:
            if kk in params:
                try:
                    v = float(params.get(kk))
                    if np.isfinite(v) and (v > 0.0):
                        return True
                    return True
                except Exception:
                    return True

    return False


def compute_body_corner_loads(
    m_body: float,
    g: float,
    wheelbase_m: float,
    track_m: float,
    cg_x_m: float = 0.0,
    cg_y_m: float = 0.0,
    clip_frac: float = 0.49,
    mode: str = 'cg',
    k_corner_N_m: Optional[Iterable[float]] = None,
    corner_xy_m: Optional[Tuple[Iterable[float], Iterable[float]]] = None,
    reg_eps: float = 1e-12,
) -> Tuple[np.ndarray, CornerLoadReport]:
    """Compute approximate static sprung-mass (body) corner loads.

    Parameters
    ----------
    mode : {"cg","stiffness"}
        "cg"       - separable approximation front/rear × left/right (default)
        "stiffness"- resolve statical indeterminacy with effective stiffness k_i

    k_corner_N_m : iterable of 4 floats, optional
        Effective corner vertical stiffnesses (N/m) for mode="stiffness".
        Order: [FL,FR,RL,RR] = ['ЛП','ПП','ЛЗ','ПЗ'].

    corner_xy_m : (x_pos, y_pos), optional
        Corner coordinates relative to body reference. If not provided, uses
        +/-wheelbase/2 and +/-track/2.

    Returns
    -------
    F_body_corner_N : np.ndarray, shape (4,)
        Corner loads in N in order [FL, FR, RL, RR].
    report : CornerLoadReport
        Diagnostics including clipping info and (for stiffness) solved q.
    """
    mode_s = str(mode or 'cg').strip().lower()
    if mode_s in ('stiffness', 'energy', 'k', 'k_stiffness'):
        return _compute_body_corner_loads_stiffness(
            m_body=m_body,
            g=g,
            wheelbase_m=wheelbase_m,
            track_m=track_m,
            cg_x_m=cg_x_m,
            cg_y_m=cg_y_m,
            clip_frac=clip_frac,
            k_corner_N_m=k_corner_N_m,
            corner_xy_m=corner_xy_m,
            reg_eps=reg_eps,
        )
    # Default: CG separable
    return _compute_body_corner_loads_cg(
        m_body=m_body,
        g=g,
        wheelbase_m=wheelbase_m,
        track_m=track_m,
        cg_x_m=cg_x_m,
        cg_y_m=cg_y_m,
        clip_frac=clip_frac,
    )


def _fallback_equal(m_body: float, g: float, cg_x_m: float, cg_y_m: float, msg: str) -> Tuple[np.ndarray, CornerLoadReport]:
    W = float(m_body) * float(g)
    F = np.ones(4, dtype=float) * (W / 4.0 if W > 0 else 0.0)
    rep = CornerLoadReport(
        F_body_corner_N=F,
        cg_x_m=float(cg_x_m),
        cg_y_m=float(cg_y_m),
        cg_x_used_m=0.0,
        cg_y_used_m=0.0,
        cg_x_clipped=False,
        cg_y_clipped=False,
        front_frac=0.5,
        rear_frac=0.5,
        left_frac=0.5,
        right_frac=0.5,
        msg=str(msg),
        mode='fallback_equal',
        cross_weight_frac=float((F[0] + F[3]) / max(1e-12, float(W))),
        diag_bias_N=float((F[0] + F[3]) - (F[1] + F[2])),
        solver_kind='equal_fallback',
        active_support_mask=np.ones(4, dtype=bool),
        active_support_count=4,
        eq_force_residual_N=float(np.sum(F) - W),
        eq_roll_residual_Nm=0.0,
        eq_pitch_residual_Nm=0.0,
    )
    return F, rep


def _compute_body_corner_loads_cg(
    m_body: float,
    g: float,
    wheelbase_m: float,
    track_m: float,
    cg_x_m: float,
    cg_y_m: float,
    clip_frac: float,
) -> Tuple[np.ndarray, CornerLoadReport]:

    W = float(m_body) * float(g)
    wheelbase_m = float(wheelbase_m)
    track_m = float(track_m)
    cg_x_m = float(cg_x_m)
    cg_y_m = float(cg_y_m)

    # Fallback if geometry not available
    if (wheelbase_m <= 0.0) or (track_m <= 0.0) or (not np.isfinite(wheelbase_m)) or (not np.isfinite(track_m)):
        return _fallback_equal(m_body, g, cg_x_m, cg_y_m, msg='fallback_equal: invalid wheelbase/track')

    # Convert offsets to fractions (clip inside support polygon)
    fx = cg_x_m / wheelbase_m
    fy = cg_y_m / track_m

    fx_used = float(np.clip(fx, -clip_frac, clip_frac))
    fy_used = float(np.clip(fy, -clip_frac, clip_frac))

    front_frac = 0.5 + fx_used
    rear_frac = 0.5 - fx_used
    left_frac = 0.5 + fy_used
    right_frac = 0.5 - fy_used

    # Corner loads (separable approximation)
    F_FL = W * front_frac * left_frac
    F_FR = W * front_frac * right_frac
    F_RL = W * rear_frac * left_frac
    F_RR = W * rear_frac * right_frac

    F = np.array([F_FL, F_FR, F_RL, F_RR], dtype=float)

    msg_parts = []
    cg_x_clipped = bool(abs(fx_used - fx) > 1e-12)
    cg_y_clipped = bool(abs(fy_used - fy) > 1e-12)
    if cg_x_clipped:
        msg_parts.append(f'cg_x clipped: fx={fx:.3g} -> {fx_used:.3g}')
    if cg_y_clipped:
        msg_parts.append(f'cg_y clipped: fy={fy:.3g} -> {fy_used:.3g}')

    # Numerical safety: ensure non-negative
    if np.any(F < 0.0):
        # This can happen if CG is outside support polygon; keep model stable.
        F = np.maximum(0.0, F)
        # Re-normalise to keep total weight (if possible)
        s = float(np.sum(F))
        if s > 0.0:
            F *= (W / s)
        msg_parts.append('negative corner load clamped and renormalised')

    msg = '; '.join(msg_parts) if msg_parts else 'ok'

    cross = float((F[0] + F[3]) / max(1e-12, W)) if np.isfinite(W) and (W > 0.0) else float('nan')
    diag_bias = float((F[0] + F[3]) - (F[1] + F[2])) if np.all(np.isfinite(F)) else float('nan')
    x = np.array([ wheelbase_m/2,  wheelbase_m/2, -wheelbase_m/2, -wheelbase_m/2], dtype=float)
    y = np.array([ track_m/2,    -track_m/2,      track_m/2,      -track_m/2   ], dtype=float)

    rep = CornerLoadReport(
        F_body_corner_N=F,
        cg_x_m=cg_x_m,
        cg_y_m=cg_y_m,
        cg_x_used_m=fx_used * wheelbase_m,
        cg_y_used_m=fy_used * track_m,
        cg_x_clipped=cg_x_clipped,
        cg_y_clipped=cg_y_clipped,
        front_frac=float(front_frac),
        rear_frac=float(rear_frac),
        left_frac=float(left_frac),
        right_frac=float(right_frac),
        msg=msg,
        mode='cg',
        cross_weight_frac=cross,
        diag_bias_N=diag_bias,
        solver_kind='separable_cg',
        active_support_mask=np.ones(4, dtype=bool),
        active_support_count=4,
        eq_force_residual_N=float(np.sum(F) - W),
        eq_roll_residual_Nm=float(np.dot(y, F) - (W * fy_used * track_m)),
        eq_pitch_residual_Nm=float(np.dot(-x, F) - (-W * fx_used * wheelbase_m)),
    )

    return F, rep


def _equilibrium_residual(A: np.ndarray, F: np.ndarray, Q: np.ndarray) -> np.ndarray:
    return np.asarray(A.T @ F - Q, dtype=float).ravel()


def _strain_energy(F: np.ndarray, k: np.ndarray) -> float:
    denom = np.maximum(np.asarray(k, dtype=float), 1e-30)
    val = 0.5 * np.sum((np.asarray(F, dtype=float) ** 2) / denom)
    return float(val) if np.isfinite(val) else float('nan')


def _solve_minimum_energy_subset(
    A: np.ndarray,
    k: np.ndarray,
    Q: np.ndarray,
    active_idx: np.ndarray,
    reg_eps: float,
) -> Optional[Dict[str, Any]]:
    """Solve the reduced minimum-energy problem for a fixed active support set."""
    if active_idx.size < 3:
        return None

    A_sub = np.asarray(A[active_idx, :], dtype=float)
    k_sub = np.asarray(k[active_idx], dtype=float)
    M = A_sub.T @ (k_sub[:, None] * A_sub)
    try:
        cond_M = float(np.linalg.cond(M))
    except Exception:
        cond_M = float('nan')

    q = None
    linear_solver = 'solve'
    M_use = M
    if np.isfinite(reg_eps) and (float(reg_eps) > 0.0):
        M_use = M + float(reg_eps) * np.eye(3, dtype=float)

    try:
        q = np.linalg.solve(M_use, Q)
    except Exception:
        linear_solver = 'lstsq'
        try:
            q = np.linalg.lstsq(M_use, Q, rcond=None)[0]
        except Exception:
            return None

    F_sub = k_sub * (A_sub @ q)
    F = np.zeros(4, dtype=float)
    F[active_idx] = F_sub
    residual = _equilibrium_residual(A, F, Q)
    return {
        'F': np.asarray(F, dtype=float),
        'q': np.asarray(q, dtype=float),
        'residual': np.asarray(residual, dtype=float),
        'cond_M': cond_M,
        'linear_solver': linear_solver,
        'strain_energy_J': _strain_energy(F_sub, k_sub),
    }


def _select_unilateral_minimum_energy_solution(
    A: np.ndarray,
    k: np.ndarray,
    Q: np.ndarray,
    reg_eps: float,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Enumerate feasible active sets and choose the minimum-energy unilateral solution."""
    full_candidate = _solve_minimum_energy_subset(A, k, Q, np.arange(4, dtype=int), reg_eps)

    force_scale = max(1.0, abs(float(Q[0])))
    support_tol_N = max(1e-6, 1e-10 * force_scale)
    residual_scale = np.array([
        force_scale,
        max(1.0, abs(float(Q[1])), force_scale * float(np.max(np.abs(A[:, 1])))),
        max(1.0, abs(float(Q[2])), force_scale * float(np.max(np.abs(A[:, 2])))),
    ], dtype=float)
    residual_tol = np.maximum(1e-8 * residual_scale, np.array([1e-6, 1e-6, 1e-6], dtype=float))

    feasible = []
    for active_size in (4, 3):
        for combo in combinations(range(4), active_size):
            candidate = _solve_minimum_energy_subset(A, k, Q, np.asarray(combo, dtype=int), reg_eps)
            if candidate is None:
                continue
            F = np.asarray(candidate['F'], dtype=float)
            residual = np.asarray(candidate['residual'], dtype=float)
            if np.min(F[list(combo)]) < (-support_tol_N):
                continue
            if np.any(np.abs(residual) > residual_tol):
                continue
            F = np.where(np.abs(F) <= support_tol_N, 0.0, F)
            positive_mask = np.asarray(F > support_tol_N, dtype=bool)
            candidate['F'] = F
            candidate['residual'] = _equilibrium_residual(A, F, Q)
            candidate['active_support_mask'] = positive_mask
            candidate['active_support_count'] = int(np.count_nonzero(positive_mask))
            candidate['solver_kind'] = (
                'minimum_energy_full_support'
                if active_size == 4 and int(np.count_nonzero(positive_mask)) == 4
                else f'minimum_energy_active_set_{int(np.count_nonzero(positive_mask))}of4'
            )
            feasible.append(candidate)

    if not feasible:
        return None, full_candidate

    best = min(
        feasible,
        key=lambda c: (
            float(c.get('strain_energy_J', float('inf'))),
            int(c.get('active_support_count', 4)),
            0 if c.get('linear_solver') == 'solve' else 1,
        ),
    )
    return best, full_candidate


def _compute_body_corner_loads_stiffness(
    m_body: float,
    g: float,
    wheelbase_m: float,
    track_m: float,
    cg_x_m: float,
    cg_y_m: float,
    clip_frac: float,
    k_corner_N_m: Optional[Iterable[float]],
    corner_xy_m: Optional[Tuple[Iterable[float], Iterable[float]]],
    reg_eps: float,
) -> Tuple[np.ndarray, CornerLoadReport]:
    """Resolve corner loads using an effective stiffness model.

    Linear small-angle model:
        δ_i = z + φ*y_i - θ*x_i
        F_i = k_i * δ_i

    Equilibrium in generalized coordinates q=[z,φ,θ]:
        A^T F = [W, W*cg_y, -W*cg_x]
        where A = [1, y, -x].

    This yields a 3x3 system:
        (A^T K A) q = Q
    """
    W = float(m_body) * float(g)
    wheelbase_m = float(wheelbase_m)
    track_m = float(track_m)
    cg_x_m = float(cg_x_m)
    cg_y_m = float(cg_y_m)

    # Validate geometry
    if (wheelbase_m <= 0.0) or (track_m <= 0.0) or (not np.isfinite(wheelbase_m)) or (not np.isfinite(track_m)):
        return _fallback_equal(m_body, g, cg_x_m, cg_y_m, msg='fallback_equal: invalid wheelbase/track (stiffness mode)')

    if k_corner_N_m is None:
        # Without stiffness info we cannot resolve the indeterminacy; keep stable.
        F, rep = _compute_body_corner_loads_cg(m_body, g, wheelbase_m, track_m, cg_x_m, cg_y_m, clip_frac)
        rep.mode = 'cg_fallback_from_stiffness'
        rep.msg = (rep.msg + '; ' if rep.msg else '') + 'k_corner_N_m not provided'
        return F, rep

    # Clip CG offsets inside support polygon (same as cg-mode safety)
    fx = cg_x_m / wheelbase_m
    fy = cg_y_m / track_m
    fx_used = float(np.clip(fx, -clip_frac, clip_frac))
    fy_used = float(np.clip(fy, -clip_frac, clip_frac))
    cg_x_used_m = fx_used * wheelbase_m
    cg_y_used_m = fy_used * track_m
    cg_x_clipped = bool(abs(fx_used - fx) > 1e-12)
    cg_y_clipped = bool(abs(fy_used - fy) > 1e-12)

    # Corner coordinates
    if corner_xy_m is None:
        x = np.array([ wheelbase_m/2,  wheelbase_m/2, -wheelbase_m/2, -wheelbase_m/2], dtype=float)
        y = np.array([ track_m/2,    -track_m/2,      track_m/2,      -track_m/2   ], dtype=float)
    else:
        try:
            x = np.asarray(corner_xy_m[0], dtype=float).ravel()
            y = np.asarray(corner_xy_m[1], dtype=float).ravel()
        except Exception:
            return _fallback_equal(m_body, g, cg_x_m, cg_y_m, msg='fallback_equal: invalid corner_xy_m')
        if x.size != 4 or y.size != 4:
            return _fallback_equal(m_body, g, cg_x_m, cg_y_m, msg='fallback_equal: corner_xy_m must have 4 elements')

    k = np.asarray(list(k_corner_N_m), dtype=float).ravel()
    if k.size != 4:
        # Try to broadcast scalar
        if k.size == 1:
            k = np.ones(4, dtype=float) * float(k[0])
        else:
            return _fallback_equal(m_body, g, cg_x_m, cg_y_m, msg='fallback_equal: k_corner_N_m must be length 4')
    # Clean stiffness
    k = np.where(np.isfinite(k) & (k > 0.0), k, np.nan)
    if np.any(~np.isfinite(k)):
        k_med = float(np.nanmedian(k))
        if not (np.isfinite(k_med) and (k_med > 0.0)):
            k_med = 1.0
        k = np.where(np.isfinite(k), k, k_med)

    # Build A (4x3): [1, y, -x]
    A = np.stack([np.ones(4, dtype=float), y.astype(float), (-x).astype(float)], axis=1)

    reg_eps = float(reg_eps) if np.isfinite(reg_eps) else 0.0
    Q = np.array([W, W * cg_y_used_m, -W * cg_x_used_m], dtype=float)

    msg_parts = []
    if cg_x_clipped:
        msg_parts.append(f'cg_x clipped: fx={fx:.3g}->{fx_used:.3g}')
    if cg_y_clipped:
        msg_parts.append(f'cg_y clipped: fy={fy:.3g}->{fy_used:.3g}')

    solution, full_candidate = _select_unilateral_minimum_energy_solution(A, k, Q, reg_eps)
    if solution is None and full_candidate is None:
        F, rep = _compute_body_corner_loads_cg(m_body, g, wheelbase_m, track_m, cg_x_m, cg_y_m, clip_frac)
        rep.mode = 'cg_fallback_solve_failed'
        rep.msg = (rep.msg + '; ' if rep.msg else '') + 'stiffness solve failed'
        return F, rep

    if solution is not None:
        F = np.asarray(solution['F'], dtype=float)
        q = np.asarray(solution['q'], dtype=float)
        residual = np.asarray(solution['residual'], dtype=float)
        cond_M = float(solution.get('cond_M', float('nan')))
        solver_kind = str(solution.get('solver_kind', 'minimum_energy_full_support'))
        active_support_mask = np.asarray(solution.get('active_support_mask', F > 0.0), dtype=bool)
        active_support_count = int(solution.get('active_support_count', np.count_nonzero(active_support_mask)))
        strain_energy_J = float(solution.get('strain_energy_J', float('nan')))
        if active_support_count < 4:
            msg_parts.append(f'unilateral active-set selected ({active_support_count}/4 supports)')
    else:
        F = np.maximum(0.0, np.asarray(full_candidate['F'], dtype=float))
        s = float(np.sum(F))
        if s > 0.0 and np.isfinite(W) and (W > 0.0):
            F *= (W / s)
        q = np.asarray(full_candidate['q'], dtype=float)
        residual = _equilibrium_residual(A, F, Q)
        cond_M = float(full_candidate.get('cond_M', float('nan')))
        solver_kind = 'clamped_full_renormalized'
        active_support_mask = np.asarray(F > 0.0, dtype=bool)
        active_support_count = int(np.count_nonzero(active_support_mask))
        strain_energy_J = float(_strain_energy(F, k))
        msg_parts.append('no feasible unilateral active-set solution; negative corner load clamped and renormalised')

    cross = float((F[0] + F[3]) / max(1e-12, W)) if np.isfinite(W) and (W > 0.0) else float('nan')
    diag_bias = float((F[0] + F[3]) - (F[1] + F[2])) if np.all(np.isfinite(F)) else float('nan')

    # For compatibility we still compute separable fractions (front/rear, left/right)
    front_frac = 0.5 + fx_used
    rear_frac = 0.5 - fx_used
    left_frac = 0.5 + fy_used
    right_frac = 0.5 - fy_used

    rep = CornerLoadReport(
        F_body_corner_N=np.asarray(F, dtype=float),
        cg_x_m=cg_x_m,
        cg_y_m=cg_y_m,
        cg_x_used_m=float(cg_x_used_m),
        cg_y_used_m=float(cg_y_used_m),
        cg_x_clipped=cg_x_clipped,
        cg_y_clipped=cg_y_clipped,
        front_frac=float(front_frac),
        rear_frac=float(rear_frac),
        left_frac=float(left_frac),
        right_frac=float(right_frac),
        msg=('; '.join(msg_parts) if msg_parts else 'ok'),
        mode='stiffness',
        cross_weight_frac=cross,
        diag_bias_N=diag_bias,
        k_corner_N_m=np.asarray(k, dtype=float),
        q_z_m=float(q[0]),
        q_phi_rad=float(q[1]),
        q_theta_rad=float(q[2]),
        cond_M=cond_M,
        solver_kind=solver_kind,
        active_support_mask=active_support_mask,
        active_support_count=active_support_count,
        eq_force_residual_N=float(residual[0]),
        eq_roll_residual_Nm=float(residual[1]),
        eq_pitch_residual_Nm=float(residual[2]),
        strain_energy_J=strain_energy_J,
    )
    return np.asarray(F, dtype=float), rep
