# -*- coding: utf-8 -*-
"""Helpers that append canonical solver-point triplets to model outputs.

Design rules:
- Only use resolved model geometry/state passed explicitly by the solver.
- No hidden defaults that diverge from the producing model.
- When geometry is impossible, warn and clamp exactly once instead of crashing.
"""

from __future__ import annotations

from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd


LogFn = Callable[[str], None]
CORNERS: tuple[str, str, str, str] = ("ЛП", "ПП", "ЛЗ", "ПЗ")
SIDE_SIGN_LEFT_POSITIVE = np.array([+1.0, -1.0, +1.0, -1.0], dtype=float)
IS_FRONT = np.array([1.0, 1.0, 0.0, 0.0], dtype=float)


def _emit(log: LogFn | None, message: str) -> None:
    if log is None:
        return
    try:
        log(str(message))
    except Exception:
        return


def _require_series(df: pd.DataFrame, col: str) -> np.ndarray:
    if col not in df.columns:
        raise KeyError(col)
    return np.asarray(df[col].to_numpy(dtype=float, copy=False), dtype=float)


def _optional_series(df: pd.DataFrame, col: str | None, n: int) -> np.ndarray:
    if not col or col not in df.columns:
        return np.zeros(n, dtype=float)
    return np.asarray(df[col].to_numpy(dtype=float, copy=False), dtype=float)


def _world_xy(
    *,
    x_local: float,
    y_local: np.ndarray,
    x_path: np.ndarray,
    y_path: np.ndarray,
    yaw: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    cy = np.cos(yaw)
    sy = np.sin(yaw)
    xw = x_path + cy * float(x_local) - sy * y_local
    yw = y_path + sy * float(x_local) + cy * y_local
    return xw, yw


def _frame_plane_z_bilinear(
    *,
    x_local: float,
    y_local: np.ndarray | float,
    x_front: float,
    x_rear: float,
    y_left: float,
    y_right: float,
    z_fl: np.ndarray,
    z_fr: np.ndarray,
    z_rl: np.ndarray,
    z_rr: np.ndarray,
) -> np.ndarray:
    """Interpolate the rigid frame lower plane at arbitrary local (x,y).

    This keeps frame-mounted hardpoints attached to the chassis when the frame
    rolls/pitches. Using the nearest corner Z makes inboard points visually detach
    from the frame because their world Z must follow the body plane at their own Y/X,
    not the wheel-corner Y/X.
    """
    x = float(x_local)
    y = np.asarray(y_local, dtype=float)
    dx = float(x_front) - float(x_rear)
    dy = float(y_left) - float(y_right)
    tx = 0.5 if abs(dx) <= 1e-12 else (x - float(x_rear)) / dx
    ty = np.full_like(y, 0.5, dtype=float) if abs(dy) <= 1e-12 else (y - float(y_right)) / dy
    tx = np.clip(tx, 0.0, 1.0)
    ty = np.clip(ty, 0.0, 1.0)
    z = (
        tx * ty * np.asarray(z_fl, dtype=float)
        + tx * (1.0 - ty) * np.asarray(z_fr, dtype=float)
        + (1.0 - tx) * ty * np.asarray(z_rl, dtype=float)
        + (1.0 - tx) * (1.0 - ty) * np.asarray(z_rr, dtype=float)
    )
    return np.asarray(z, dtype=float)


def _store_triplet(extra: dict[str, np.ndarray], *, kind: str, corner: str, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
    extra[f"{kind}_{corner}_x_м"] = np.asarray(x, dtype=float)
    extra[f"{kind}_{corner}_y_м"] = np.asarray(y, dtype=float)
    extra[f"{kind}_{corner}_z_м"] = np.asarray(z, dtype=float)


def _normalize_rows(v_xyz: np.ndarray, *, fallback_xyz: Sequence[float]) -> np.ndarray:
    arr = np.asarray(v_xyz, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("Expected (N,3) array")
    fb = np.asarray(fallback_xyz, dtype=float).reshape(3)
    out = np.tile(fb, (arr.shape[0], 1))
    n = np.linalg.norm(arr, axis=1)
    mask = np.isfinite(n) & (n > 1e-12)
    if np.any(mask):
        out[mask] = arr[mask] / n[mask, None]
    fn = float(np.linalg.norm(fb))
    if not (np.isfinite(fn) and fn > 1e-12):
        out[~mask] = np.array([0.0, 0.0, 1.0], dtype=float)
    else:
        out[~mask] = fb / fn
    return out


def _build_rigid_frame_support(
    *,
    n: int,
    x_pos: np.ndarray,
    y_pos: np.ndarray,
    x_path: np.ndarray,
    y_path: np.ndarray,
    yaw: np.ndarray,
    frame_z_map: Mapping[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Return rigid-frame support derived from canonical lower frame corners.

    The solver provides the lower frame contour through ``frame_corner_*`` points.
    Those corners define the body pose (yaw/pitch/roll + heave) seen by Animator.
    Every frame-mounted hardpoint must therefore be exported through the same rigid
    transform; otherwise mount points visibly drift relative to the chassis.
    """
    frame_points: dict[str, np.ndarray] = {}
    for i, corner in enumerate(CORNERS):
        y_local = np.full(n, float(y_pos[i]), dtype=float)
        xw, yw = _world_xy(
            x_local=float(x_pos[i]),
            y_local=y_local,
            x_path=x_path,
            y_path=y_path,
            yaw=yaw,
        )
        zw = np.asarray(frame_z_map[corner], dtype=float)
        frame_points[corner] = np.column_stack([
            np.asarray(xw, dtype=float),
            np.asarray(yw, dtype=float),
            zw,
        ])

    lp = frame_points["ЛП"]
    pp = frame_points["ПП"]
    lz = frame_points["ЛЗ"]
    pz = frame_points["ПЗ"]
    center = 0.25 * (lp + pp + lz + pz)
    front = 0.5 * (lp + pp)
    rear = 0.5 * (lz + pz)
    left = 0.5 * (lp + lz)
    right = 0.5 * (pp + pz)

    x_axis = _normalize_rows(front - rear, fallback_xyz=(1.0, 0.0, 0.0))
    y_raw = left - right
    y_proj = y_raw - x_axis * np.sum(x_axis * y_raw, axis=1, keepdims=True)
    y_axis = _normalize_rows(y_proj, fallback_xyz=(0.0, 1.0, 0.0))
    z_axis = _normalize_rows(np.cross(x_axis, y_axis), fallback_xyz=(0.0, 0.0, 1.0))
    flip = z_axis[:, 2] < 0.0
    if np.any(flip):
        y_axis[flip] *= -1.0
        z_axis = _normalize_rows(np.cross(x_axis, y_axis), fallback_xyz=(0.0, 0.0, 1.0))

    local_center_x = float(np.mean(np.asarray(x_pos, dtype=float)))
    local_center_y = float(np.mean(np.asarray(y_pos, dtype=float)))
    return frame_points, center, x_axis, y_axis, z_axis, local_center_x, local_center_y


def _rigid_local_to_world(
    *,
    x_local: np.ndarray | float,
    y_local: np.ndarray | float,
    z_local: np.ndarray | float,
    center_xyz: np.ndarray,
    x_axis_xyz: np.ndarray,
    y_axis_xyz: np.ndarray,
    z_axis_xyz: np.ndarray,
    local_center_x: float,
    local_center_y: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = center_xyz.shape[0]
    xl = np.asarray(x_local, dtype=float)
    yl = np.asarray(y_local, dtype=float)
    zl = np.asarray(z_local, dtype=float)
    if xl.ndim == 0:
        xl = np.full(n, float(xl), dtype=float)
    else:
        xl = xl.reshape(n,)
    if yl.ndim == 0:
        yl = np.full(n, float(yl), dtype=float)
    else:
        yl = yl.reshape(n,)
    if zl.ndim == 0:
        zl = np.full(n, float(zl), dtype=float)
    else:
        zl = zl.reshape(n,)
    pts = (
        np.asarray(center_xyz, dtype=float)
        + np.asarray(x_axis_xyz, dtype=float) * (xl - float(local_center_x))[:, None]
        + np.asarray(y_axis_xyz, dtype=float) * (yl - float(local_center_y))[:, None]
        + np.asarray(z_axis_xyz, dtype=float) * zl[:, None]
    )
    return pts[:, 0], pts[:, 1], pts[:, 2]


def _parallel_upper_joint_z(
    *,
    lower_joint_z_rel_frame: np.ndarray,
    lower_pivot_z_m: float,
    upper_pivot_z_m: float,
) -> np.ndarray:
    """Shift lower-arm joint motion by the explicit upper-arm pivot offset.

    The reduced vertical models do not solve a full upright body.  We therefore keep
    the upper arm parallel to the lower arm in the local YZ plane and let source-data
    define the upper-arm raw geometry (pivot and length).
    """
    z_joint = np.asarray(lower_joint_z_rel_frame, dtype=float)
    return np.asarray(float(upper_pivot_z_m) + (z_joint - float(lower_pivot_z_m)), dtype=float)


def _solve_arm_local_geometry(
    *,
    y_wheel: float,
    side: float,
    inboard_m: float,
    pivot_z_m: float,
    arm_len_m: float,
    z_joint_rel_frame: np.ndarray,
    eps_m: float,
    log: LogFn | None,
    context: str,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Return local Y/Z geometry for one arm.

    Returns ``(y_pivot, z_pivot, y_joint, z_joint)`` in the body frame.
    """
    y_pivot = float(side) * (abs(float(y_wheel)) - float(inboard_m))
    z_pivot = float(pivot_z_m)
    z_joint = np.asarray(z_joint_rel_frame, dtype=float)
    arm_len = float(arm_len_m)
    dz = z_joint - z_pivot
    rad2 = (arm_len * arm_len) - (dz * dz)
    if np.any(rad2 <= 0.0):
        _emit(
            log,
            (
                f"[solver-points] {context}: arm geometry became infeasible; "
                f"clamping sqrt argument. min(L^2-dz^2)={float(np.min(rad2)):.6g}"
            ),
        )
    root = np.sqrt(np.maximum(rad2, float(eps_m) * float(eps_m)))
    y_joint = y_pivot + float(side) * root
    return y_pivot, z_pivot, y_joint, z_joint


def append_solver_points_full_dw2d(
    df_main: pd.DataFrame,
    *,
    x_pos: Sequence[float],
    y_pos: Sequence[float],
    frame_z_cols: Mapping[str, str],
    wheel_z_cols: Mapping[str, str],
    road_z_cols: Mapping[str, str],
    x_path_col: str | None,
    y_path_col: str | None,
    yaw_col: str | None,
    inboard_front_m: float,
    inboard_rear_m: float,
    pivot_z_front_m: float,
    pivot_z_rear_m: float,
    lower_arm_len_front_m: float,
    lower_arm_len_rear_m: float,
    upper_inboard_front_m: float,
    upper_inboard_rear_m: float,
    upper_pivot_z_front_m: float,
    upper_pivot_z_rear_m: float,
    upper_arm_len_front_m: float,
    upper_arm_len_rear_m: float,
    topsep_c1_m: Sequence[float],
    topz_c1_m: Sequence[float],
    lowfrac_c1: Sequence[float],
    topsep_c2_m: Sequence[float],
    topz_c2_m: Sequence[float],
    lowfrac_c2: Sequence[float],
    topx_c1_m: Sequence[float] | None = None,
    topx_c2_m: Sequence[float] | None = None,
    c1_mount_arm: Sequence[str] | None = None,
    c2_mount_arm: Sequence[str] | None = None,
    c1_branch: Sequence[str] | None = None,
    c2_branch: Sequence[str] | None = None,
    lower_frame_branch_front_x_m: Sequence[float] | None = None,
    lower_frame_branch_rear_x_m: Sequence[float] | None = None,
    lower_hub_branch_front_x_m: Sequence[float] | None = None,
    lower_hub_branch_rear_x_m: Sequence[float] | None = None,
    upper_frame_branch_front_x_m: Sequence[float] | None = None,
    upper_frame_branch_rear_x_m: Sequence[float] | None = None,
    upper_hub_branch_front_x_m: Sequence[float] | None = None,
    upper_hub_branch_rear_x_m: Sequence[float] | None = None,
    eps_m: float = 1e-9,
    log: LogFn | None = None,
) -> pd.DataFrame:
    """Append solver points for explicit lower/upper DW2D geometry.

    R20 geometry release: when explicit branch/top-X source-data is available we export
    trapezoidal upper/lower arms and longitudinally separated cylinders directly from
    solver/export code. No animator-side invention is allowed.
    """
    n = len(df_main)
    x_path = _optional_series(df_main, x_path_col, n)
    y_path = _optional_series(df_main, y_path_col, n)
    yaw = _optional_series(df_main, yaw_col, n)

    def _num_seq(value: Sequence[float] | None, default: float = 0.0) -> np.ndarray:
        if value is None:
            return np.full(4, float(default), dtype=float)
        arr = np.asarray(value, dtype=float).reshape(4,)
        return arr

    def _str_seq(value: Sequence[str] | None, default: str) -> tuple[str, str, str, str]:
        if value is None:
            return (default, default, default, default)
        arr = tuple(str(v) for v in value)
        if len(arr) != 4:
            raise ValueError(f"Expected 4 string values, got {len(arr)}")
        return arr  # type: ignore[return-value]

    x_pos_arr = np.asarray(x_pos, dtype=float).reshape(4,)
    y_pos_arr = np.asarray(y_pos, dtype=float).reshape(4,)
    topsep_c1_arr = np.asarray(topsep_c1_m, dtype=float).reshape(4,)
    topsep_c2_arr = np.asarray(topsep_c2_m, dtype=float).reshape(4,)
    topz_c1_arr = np.asarray(topz_c1_m, dtype=float).reshape(4,)
    topz_c2_arr = np.asarray(topz_c2_m, dtype=float).reshape(4,)
    lowfrac_c1_arr = np.asarray(lowfrac_c1, dtype=float).reshape(4,)
    lowfrac_c2_arr = np.asarray(lowfrac_c2, dtype=float).reshape(4,)
    topx_c1_arr = _num_seq(topx_c1_m, 0.0)
    topx_c2_arr = _num_seq(topx_c2_m, 0.0)

    lower_frame_front_x_arr = _num_seq(lower_frame_branch_front_x_m, 0.0)
    lower_frame_rear_x_arr = _num_seq(lower_frame_branch_rear_x_m, 0.0)
    lower_hub_front_x_arr = _num_seq(lower_hub_branch_front_x_m, 0.0)
    lower_hub_rear_x_arr = _num_seq(lower_hub_branch_rear_x_m, 0.0)
    upper_frame_front_x_arr = _num_seq(upper_frame_branch_front_x_m, 0.0)
    upper_frame_rear_x_arr = _num_seq(upper_frame_branch_rear_x_m, 0.0)
    upper_hub_front_x_arr = _num_seq(upper_hub_branch_front_x_m, 0.0)
    upper_hub_rear_x_arr = _num_seq(upper_hub_branch_rear_x_m, 0.0)

    c1_mount_arr = _str_seq(c1_mount_arm, 'нижний_рычаг')
    c2_mount_arr = _str_seq(c2_mount_arm, 'верхний_рычаг')
    c1_branch_arr = _str_seq(c1_branch, 'перед')
    c2_branch_arr = _str_seq(c2_branch, 'зад')

    lower_inb = IS_FRONT * float(inboard_front_m) + (1.0 - IS_FRONT) * float(inboard_rear_m)
    lower_z_piv = IS_FRONT * float(pivot_z_front_m) + (1.0 - IS_FRONT) * float(pivot_z_rear_m)
    lower_L = IS_FRONT * float(lower_arm_len_front_m) + (1.0 - IS_FRONT) * float(lower_arm_len_rear_m)
    upper_inb = IS_FRONT * float(upper_inboard_front_m) + (1.0 - IS_FRONT) * float(upper_inboard_rear_m)
    upper_z_piv = IS_FRONT * float(upper_pivot_z_front_m) + (1.0 - IS_FRONT) * float(upper_pivot_z_rear_m)
    upper_L = IS_FRONT * float(upper_arm_len_front_m) + (1.0 - IS_FRONT) * float(upper_arm_len_rear_m)

    extra: dict[str, np.ndarray] = {}

    frame_z_map = {c: _require_series(df_main, frame_z_cols[c]) for c in CORNERS}
    wheel_z_map = {c: _require_series(df_main, wheel_z_cols[c]) for c in CORNERS}
    road_z_map = {c: _require_series(df_main, road_z_cols[c]) for c in CORNERS}
    x_front = float(max(x_pos_arr[0], x_pos_arr[1]))
    x_rear = float(min(x_pos_arr[2], x_pos_arr[3]))
    y_left = float(max(y_pos_arr[0], y_pos_arr[2]))
    y_right = float(min(y_pos_arr[1], y_pos_arr[3]))
    z_fl = frame_z_map['ЛП']
    z_fr = frame_z_map['ПП']
    z_rl = frame_z_map['ЛЗ']
    z_rr = frame_z_map['ПЗ']
    frame_points_world, frame_center_world, frame_x_axis_world, frame_y_axis_world, frame_z_axis_world, local_center_x, local_center_y = _build_rigid_frame_support(
        n=n,
        x_pos=x_pos_arr,
        y_pos=y_pos_arr,
        x_path=x_path,
        y_path=y_path,
        yaw=yaw,
        frame_z_map=frame_z_map,
    )

    for i, corner in enumerate(CORNERS):
        frame_z = frame_z_map[corner]
        wheel_z = wheel_z_map[corner]
        road_z = road_z_map[corner]
        delta_w = wheel_z - frame_z

        x_local = float(x_pos_arr[i])
        side = float(SIDE_SIGN_LEFT_POSITIVE[i])
        y_wheel = float(y_pos_arr[i])

        y_pivot, z_pivot, y_joint, z_joint = _solve_arm_local_geometry(
            y_wheel=y_wheel,
            side=side,
            inboard_m=float(lower_inb[i]),
            pivot_z_m=float(lower_z_piv[i]),
            arm_len_m=float(lower_L[i]),
            z_joint_rel_frame=delta_w,
            eps_m=eps_m,
            log=log,
            context=f"{corner}/arm1",
        )
        z_joint2 = _parallel_upper_joint_z(
            lower_joint_z_rel_frame=z_joint,
            lower_pivot_z_m=z_pivot,
            upper_pivot_z_m=float(upper_z_piv[i]),
        )
        y_pivot2, z_pivot2, y_joint2, z_joint2 = _solve_arm_local_geometry(
            y_wheel=y_wheel,
            side=side,
            inboard_m=float(upper_inb[i]),
            pivot_z_m=float(upper_z_piv[i]),
            arm_len_m=float(upper_L[i]),
            z_joint_rel_frame=z_joint2,
            eps_m=eps_m,
            log=log,
            context=f"{corner}/arm2",
        )

        y_top1 = np.full(n, side * 0.5 * float(topsep_c1_arr[i]), dtype=float)
        z_top1_local = np.full(n, float(topz_c1_arr[i]), dtype=float)
        y_top2 = np.full(n, side * 0.5 * float(topsep_c2_arr[i]), dtype=float)
        z_top2_local = np.full(n, float(topz_c2_arr[i]), dtype=float)

        lf_xf = float(x_local + lower_frame_front_x_arr[i])
        lf_xr = float(x_local + lower_frame_rear_x_arr[i])
        lh_xf = float(x_local + lower_hub_front_x_arr[i])
        lh_xr = float(x_local + lower_hub_rear_x_arr[i])
        uf_xf = float(x_local + upper_frame_front_x_arr[i])
        uf_xr = float(x_local + upper_frame_rear_x_arr[i])
        uh_xf = float(x_local + upper_hub_front_x_arr[i])
        uh_xr = float(x_local + upper_hub_rear_x_arr[i])

        y_pivot_arr = np.full(n, y_pivot, dtype=float)
        y_pivot2_arr = np.full(n, y_pivot2, dtype=float)
        y_wheel_arr = np.full(n, y_wheel, dtype=float)
        z_pivot_arr = np.full(n, z_pivot, dtype=float)
        z_pivot2_arr = np.full(n, z_pivot2, dtype=float)

        lower_frame_front_x, lower_frame_front_y, lower_frame_front_z = _rigid_local_to_world(
            x_local=lf_xf,
            y_local=y_pivot_arr,
            z_local=z_pivot_arr,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        lower_frame_rear_x, lower_frame_rear_y, lower_frame_rear_z = _rigid_local_to_world(
            x_local=lf_xr,
            y_local=y_pivot_arr,
            z_local=z_pivot_arr,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        upper_frame_front_x, upper_frame_front_y, upper_frame_front_z = _rigid_local_to_world(
            x_local=uf_xf,
            y_local=y_pivot2_arr,
            z_local=z_pivot2_arr,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        upper_frame_rear_x, upper_frame_rear_y, upper_frame_rear_z = _rigid_local_to_world(
            x_local=uf_xr,
            y_local=y_pivot2_arr,
            z_local=z_pivot2_arr,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        c1_top_x_local = x_local + float(topx_c1_arr[i])
        c2_top_x_local = x_local + float(topx_c2_arr[i])
        c1_top_x, c1_top_y, c1_top_z = _rigid_local_to_world(
            x_local=c1_top_x_local,
            y_local=y_top1,
            z_local=z_top1_local,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        c2_top_x, c2_top_y, c2_top_z = _rigid_local_to_world(
            x_local=c2_top_x_local,
            y_local=y_top2,
            z_local=z_top2_local,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )

        lower_hub_front_x, lower_hub_front_y = _world_xy(x_local=lh_xf, y_local=y_joint, x_path=x_path, y_path=y_path, yaw=yaw)
        lower_hub_rear_x, lower_hub_rear_y = _world_xy(x_local=lh_xr, y_local=y_joint, x_path=x_path, y_path=y_path, yaw=yaw)
        upper_hub_front_x, upper_hub_front_y = _world_xy(x_local=uh_xf, y_local=y_joint2, x_path=x_path, y_path=y_path, yaw=yaw)
        upper_hub_rear_x, upper_hub_rear_y = _world_xy(x_local=uh_xr, y_local=y_joint2, x_path=x_path, y_path=y_path, yaw=yaw)
        lower_hub_front_z = frame_z + z_joint
        lower_hub_rear_z = frame_z + z_joint
        upper_hub_front_z = frame_z + z_joint2
        upper_hub_rear_z = frame_z + z_joint2

        arm_pivot_x = 0.5 * (lower_frame_front_x + lower_frame_rear_x)
        arm_pivot_y = 0.5 * (lower_frame_front_y + lower_frame_rear_y)
        arm_pivot_z = 0.5 * (lower_frame_front_z + lower_frame_rear_z)
        arm_joint_x = 0.5 * (lower_hub_front_x + lower_hub_rear_x)
        arm_joint_y = 0.5 * (lower_hub_front_y + lower_hub_rear_y)
        arm_joint_z = 0.5 * (lower_hub_front_z + lower_hub_rear_z)
        arm2_pivot_x = 0.5 * (upper_frame_front_x + upper_frame_rear_x)
        arm2_pivot_y = 0.5 * (upper_frame_front_y + upper_frame_rear_y)
        arm2_pivot_z = 0.5 * (upper_frame_front_z + upper_frame_rear_z)
        arm2_joint_x = 0.5 * (upper_hub_front_x + upper_hub_rear_x)
        arm2_joint_y = 0.5 * (upper_hub_front_y + upper_hub_rear_y)
        arm2_joint_z = 0.5 * (upper_hub_front_z + upper_hub_rear_z)

        def _branch_world_triplet(arm_name: str, branch_name: str) -> tuple[np.ndarray, np.ndarray]:
            if arm_name == 'верхний_рычаг':
                if branch_name == 'перед':
                    return (
                        np.column_stack([upper_frame_front_x, upper_frame_front_y, upper_frame_front_z]),
                        np.column_stack([upper_hub_front_x, upper_hub_front_y, upper_hub_front_z]),
                    )
                return (
                    np.column_stack([upper_frame_rear_x, upper_frame_rear_y, upper_frame_rear_z]),
                    np.column_stack([upper_hub_rear_x, upper_hub_rear_y, upper_hub_rear_z]),
                )
            if branch_name == 'перед':
                return (
                    np.column_stack([lower_frame_front_x, lower_frame_front_y, lower_frame_front_z]),
                    np.column_stack([lower_hub_front_x, lower_hub_front_y, lower_hub_front_z]),
                )
            return (
                np.column_stack([lower_frame_rear_x, lower_frame_rear_y, lower_frame_rear_z]),
                np.column_stack([lower_hub_rear_x, lower_hub_rear_y, lower_hub_rear_z]),
            )

        def _bot_point_world(arm_name: str, branch_name: str, frac: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            p_in, p_out = _branch_world_triplet(arm_name, branch_name)
            p = p_in + float(frac) * (p_out - p_in)
            return p[:, 0], p[:, 1], p[:, 2]

        f1 = float(np.clip(lowfrac_c1_arr[i], 0.0, 1.0))
        arm_name_c1 = c1_mount_arr[i] if c1_mount_arr[i] in ('верхний_рычаг', 'нижний_рычаг') else 'нижний_рычаг'
        branch_name_c1 = c1_branch_arr[i] if c1_branch_arr[i] in ('перед', 'зад') else 'перед'
        c1_bot_x, c1_bot_y, c1_bot_z = _bot_point_world(arm_name_c1, branch_name_c1, f1)

        f2 = float(np.clip(lowfrac_c2_arr[i], 0.0, 1.0))
        arm_name_c2 = c2_mount_arr[i] if c2_mount_arr[i] in ('верхний_рычаг', 'нижний_рычаг') else 'верхний_рычаг'
        branch_name_c2 = c2_branch_arr[i] if c2_branch_arr[i] in ('перед', 'зад') else 'зад'
        c2_bot_x, c2_bot_y, c2_bot_z = _bot_point_world(arm_name_c2, branch_name_c2, f2)

        wheel_x = 0.25 * (lower_hub_front_x + lower_hub_rear_x + upper_hub_front_x + upper_hub_rear_x)
        wheel_y = 0.25 * (lower_hub_front_y + lower_hub_rear_y + upper_hub_front_y + upper_hub_rear_y)
        frame_world = np.asarray(frame_points_world[corner], dtype=float)
        frame_x = frame_world[:, 0]
        frame_y = frame_world[:, 1]
        frame_z_world = frame_world[:, 2]

        _store_triplet(extra, kind='arm_pivot', corner=corner, x=arm_pivot_x, y=arm_pivot_y, z=arm_pivot_z)
        _store_triplet(extra, kind='arm2_pivot', corner=corner, x=arm2_pivot_x, y=arm2_pivot_y, z=arm2_pivot_z)
        _store_triplet(extra, kind='frame_corner', corner=corner, x=frame_x, y=frame_y, z=frame_z_world)
        _store_triplet(extra, kind='arm_joint', corner=corner, x=arm_joint_x, y=arm_joint_y, z=arm_joint_z)
        _store_triplet(extra, kind='arm2_joint', corner=corner, x=arm2_joint_x, y=arm2_joint_y, z=arm2_joint_z)
        _store_triplet(extra, kind='cyl1_top', corner=corner, x=c1_top_x, y=c1_top_y, z=c1_top_z)
        _store_triplet(extra, kind='cyl1_bot', corner=corner, x=c1_bot_x, y=c1_bot_y, z=c1_bot_z)
        _store_triplet(extra, kind='cyl2_top', corner=corner, x=c2_top_x, y=c2_top_y, z=c2_top_z)
        _store_triplet(extra, kind='cyl2_bot', corner=corner, x=c2_bot_x, y=c2_bot_y, z=c2_bot_z)
        _store_triplet(extra, kind='wheel_center', corner=corner, x=wheel_x, y=wheel_y, z=wheel_z)
        _store_triplet(extra, kind='road_contact', corner=corner, x=wheel_x, y=wheel_y, z=road_z)
        _store_triplet(extra, kind='lower_arm_frame_front', corner=corner, x=lower_frame_front_x, y=lower_frame_front_y, z=lower_frame_front_z)
        _store_triplet(extra, kind='lower_arm_frame_rear', corner=corner, x=lower_frame_rear_x, y=lower_frame_rear_y, z=lower_frame_rear_z)
        _store_triplet(extra, kind='lower_arm_hub_front', corner=corner, x=lower_hub_front_x, y=lower_hub_front_y, z=lower_hub_front_z)
        _store_triplet(extra, kind='lower_arm_hub_rear', corner=corner, x=lower_hub_rear_x, y=lower_hub_rear_y, z=lower_hub_rear_z)
        _store_triplet(extra, kind='upper_arm_frame_front', corner=corner, x=upper_frame_front_x, y=upper_frame_front_y, z=upper_frame_front_z)
        _store_triplet(extra, kind='upper_arm_frame_rear', corner=corner, x=upper_frame_rear_x, y=upper_frame_rear_y, z=upper_frame_rear_z)
        _store_triplet(extra, kind='upper_arm_hub_front', corner=corner, x=upper_hub_front_x, y=upper_hub_front_y, z=upper_hub_front_z)
        _store_triplet(extra, kind='upper_arm_hub_rear', corner=corner, x=upper_hub_rear_x, y=upper_hub_rear_y, z=upper_hub_rear_z)

    if extra:
        df_main = pd.concat([df_main, pd.DataFrame(extra, index=df_main.index)], axis=1)
    return df_main


def append_solver_points_linear_arm(
    df_main: pd.DataFrame,
    *,
    x_pos: Sequence[float],
    y_pos: Sequence[float],
    frame_z_cols: Mapping[str, str],
    wheel_z_cols: Mapping[str, str],
    road_z_cols: Mapping[str, str],
    x_path_col: str | None,
    y_path_col: str | None,
    yaw_col: str | None,
    pivot_z_m: Sequence[float],
    topspan_c1_m: Sequence[float],
    topz_c1_m: Sequence[float],
    lowfrac_c1: Sequence[float],
    topspan_c2_m: Sequence[float],
    topz_c2_m: Sequence[float],
    lowfrac_c2: Sequence[float],
    upper_pivot_z_m: Sequence[float] | None = None,
    log: LogFn | None = None,
) -> pd.DataFrame:
    """Append solver points for reduced linear arm geometry.

    This matches models where:
    - lower-arm pivot lateral coordinate is fixed on the vehicle centerline (y=0);
    - outer joint lateral coordinate is the wheel lateral coordinate;
    - lower cylinder mount is an interpolation between pivot and outer joint.

    When explicit ``upper_pivot_z_m`` is provided, the second arm is sourced from raw/base
    geometry rather than derived from the C2 top mount.
    """
    n = len(df_main)
    x_path = _optional_series(df_main, x_path_col, n)
    y_path = _optional_series(df_main, y_path_col, n)
    yaw = _optional_series(df_main, yaw_col, n)

    x_pos_arr = np.asarray(x_pos, dtype=float).reshape(4,)
    y_pos_arr = np.asarray(y_pos, dtype=float).reshape(4,)
    pivot_z_arr = np.asarray(pivot_z_m, dtype=float).reshape(4,)
    topspan_c1_arr = np.asarray(topspan_c1_m, dtype=float).reshape(4,)
    topspan_c2_arr = np.asarray(topspan_c2_m, dtype=float).reshape(4,)
    topz_c1_arr = np.asarray(topz_c1_m, dtype=float).reshape(4,)
    topz_c2_arr = np.asarray(topz_c2_m, dtype=float).reshape(4,)
    lowfrac_c1_arr = np.asarray(lowfrac_c1, dtype=float).reshape(4,)
    lowfrac_c2_arr = np.asarray(lowfrac_c2, dtype=float).reshape(4,)
    upper_pivot_z_arr = None if upper_pivot_z_m is None else np.asarray(upper_pivot_z_m, dtype=float).reshape(4,)
    extra: dict[str, np.ndarray] = {}

    frame_z_map = {c: _require_series(df_main, frame_z_cols[c]) for c in CORNERS}
    wheel_z_map = {c: _require_series(df_main, wheel_z_cols[c]) for c in CORNERS}
    road_z_map = {c: _require_series(df_main, road_z_cols[c]) for c in CORNERS}
    x_front = float(max(x_pos_arr[0], x_pos_arr[1]))
    x_rear = float(min(x_pos_arr[2], x_pos_arr[3]))
    y_left = float(max(y_pos_arr[0], y_pos_arr[2]))
    y_right = float(min(y_pos_arr[1], y_pos_arr[3]))
    z_fl = frame_z_map['ЛП']
    z_fr = frame_z_map['ПП']
    z_rl = frame_z_map['ЛЗ']
    z_rr = frame_z_map['ПЗ']
    frame_points_world, frame_center_world, frame_x_axis_world, frame_y_axis_world, frame_z_axis_world, local_center_x, local_center_y = _build_rigid_frame_support(
        n=n,
        x_pos=x_pos_arr,
        y_pos=y_pos_arr,
        x_path=x_path,
        y_path=y_path,
        yaw=yaw,
        frame_z_map=frame_z_map,
    )

    for i, corner in enumerate(CORNERS):
        frame_z = frame_z_map[corner]
        wheel_z = wheel_z_map[corner]
        road_z = road_z_map[corner]
        delta_w = wheel_z - frame_z

        x_local = float(x_pos_arr[i])
        side = float(SIDE_SIGN_LEFT_POSITIVE[i])
        y_wheel = float(y_pos_arr[i])
        y_pivot = 0.0
        z_pivot = float(pivot_z_arr[i])
        y_joint_local = np.full(n, y_wheel, dtype=float)
        z_joint = delta_w

        y_top1_local = np.full(n, side * 0.5 * float(topspan_c1_arr[i]), dtype=float)
        z_top1_local = np.full(n, float(topz_c1_arr[i]), dtype=float)
        f1 = float(np.clip(lowfrac_c1_arr[i], 0.0, 1.0))
        y_bot1_local = np.full(n, y_pivot + f1 * (y_wheel - y_pivot), dtype=float)

        y_top2_local = np.full(n, side * 0.5 * float(topspan_c2_arr[i]), dtype=float)
        z_top2_local = np.full(n, float(topz_c2_arr[i]), dtype=float)
        f2 = float(np.clip(lowfrac_c2_arr[i], 0.0, 1.0))
        if upper_pivot_z_arr is None:
            z_pivot2 = 0.5 * (z_pivot + float(topz_c2_arr[i]))
            if not np.isfinite(z_pivot2):
                _emit(log, f"[solver-points] {corner}/arm2: non-finite derived upper pivot z; using lower pivot z.")
                z_pivot2 = z_pivot
        else:
            z_pivot2 = float(upper_pivot_z_arr[i])
        z_joint2 = _parallel_upper_joint_z(
            lower_joint_z_rel_frame=z_joint,
            lower_pivot_z_m=z_pivot,
            upper_pivot_z_m=z_pivot2,
        )
        y_bot2_local = np.full(n, y_pivot + f2 * (y_wheel - y_pivot), dtype=float)

        y_pivot_arr = np.full(n, y_pivot, dtype=float)
        y_pivot2_arr = np.full(n, y_pivot, dtype=float)
        z_pivot_arr = np.full(n, z_pivot, dtype=float)
        z_pivot2_arr = np.full(n, z_pivot2, dtype=float)

        arm_pivot_x, arm_pivot_y, arm_pivot_z = _rigid_local_to_world(
            x_local=x_local,
            y_local=y_pivot_arr,
            z_local=z_pivot_arr,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        arm2_pivot_x, arm2_pivot_y, arm2_pivot_z = _rigid_local_to_world(
            x_local=x_local,
            y_local=y_pivot2_arr,
            z_local=z_pivot2_arr,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        c1_top_x, c1_top_y, c1_top_z = _rigid_local_to_world(
            x_local=x_local,
            y_local=y_top1_local,
            z_local=z_top1_local,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )
        c2_top_x, c2_top_y, c2_top_z = _rigid_local_to_world(
            x_local=x_local,
            y_local=y_top2_local,
            z_local=z_top2_local,
            center_xyz=frame_center_world,
            x_axis_xyz=frame_x_axis_world,
            y_axis_xyz=frame_y_axis_world,
            z_axis_xyz=frame_z_axis_world,
            local_center_x=local_center_x,
            local_center_y=local_center_y,
        )

        arm_joint_x, arm_joint_y = _world_xy(x_local=x_local, y_local=y_joint_local, x_path=x_path, y_path=y_path, yaw=yaw)
        arm_joint_z = frame_z + z_joint
        arm2_joint_x, arm2_joint_y = arm_joint_x, arm_joint_y
        arm2_joint_z = frame_z + z_joint2
        c1_bot_x, c1_bot_y = _world_xy(x_local=x_local, y_local=y_bot1_local, x_path=x_path, y_path=y_path, yaw=yaw)
        c1_bot_z = arm_pivot_z + f1 * (arm_joint_z - arm_pivot_z)
        c2_bot_x, c2_bot_y = _world_xy(x_local=x_local, y_local=y_bot2_local, x_path=x_path, y_path=y_path, yaw=yaw)
        c2_bot_z = arm2_pivot_z + f2 * (arm2_joint_z - arm2_pivot_z)
        wheel_x, wheel_y = _world_xy(x_local=x_local, y_local=np.full(n, y_wheel, dtype=float), x_path=x_path, y_path=y_path, yaw=yaw)
        frame_world = np.asarray(frame_points_world[corner], dtype=float)
        frame_x = frame_world[:, 0]
        frame_y = frame_world[:, 1]
        frame_z_world = frame_world[:, 2]

        _store_triplet(extra, kind="arm_pivot", corner=corner, x=arm_pivot_x, y=arm_pivot_y, z=arm_pivot_z)
        _store_triplet(extra, kind="arm2_pivot", corner=corner, x=arm2_pivot_x, y=arm2_pivot_y, z=arm2_pivot_z)
        _store_triplet(extra, kind="frame_corner", corner=corner, x=frame_x, y=frame_y, z=frame_z_world)
        _store_triplet(extra, kind="arm_joint", corner=corner, x=arm_joint_x, y=arm_joint_y, z=arm_joint_z)
        _store_triplet(extra, kind="arm2_joint", corner=corner, x=arm2_joint_x, y=arm2_joint_y, z=arm2_joint_z)
        _store_triplet(extra, kind="cyl1_top", corner=corner, x=c1_top_x, y=c1_top_y, z=c1_top_z)
        _store_triplet(extra, kind="cyl1_bot", corner=corner, x=c1_bot_x, y=c1_bot_y, z=c1_bot_z)
        _store_triplet(extra, kind="cyl2_top", corner=corner, x=c2_top_x, y=c2_top_y, z=c2_top_z)
        _store_triplet(extra, kind="cyl2_bot", corner=corner, x=c2_bot_x, y=c2_bot_y, z=c2_bot_z)
        _store_triplet(extra, kind="wheel_center", corner=corner, x=wheel_x, y=wheel_y, z=wheel_z)
        _store_triplet(extra, kind="road_contact", corner=corner, x=wheel_x, y=wheel_y, z=road_z)
    if extra:
        df_main = pd.concat([df_main, pd.DataFrame(extra, index=df_main.index)], axis=1)
    return df_main
