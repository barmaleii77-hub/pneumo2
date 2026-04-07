import math

import numpy as np
import pandas as pd

from pneumo_solver_ui.desktop_animator.geom3d_helpers import orthonormal_frame_from_corners
from pneumo_solver_ui.solver_points_geometry import append_solver_points_full_dw2d


CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _body_local(out: pd.DataFrame, kind: str, corner: str) -> np.ndarray:
    pts = out[[f"{kind}_{corner}_x_м", f"{kind}_{corner}_y_м", f"{kind}_{corner}_z_м"]].to_numpy(dtype=float)
    lp = out[["frame_corner_ЛП_x_м", "frame_corner_ЛП_y_м", "frame_corner_ЛП_z_м"]].to_numpy(dtype=float)
    pp = out[["frame_corner_ПП_x_м", "frame_corner_ПП_y_м", "frame_corner_ПП_z_м"]].to_numpy(dtype=float)
    lz = out[["frame_corner_ЛЗ_x_м", "frame_corner_ЛЗ_y_м", "frame_corner_ЛЗ_z_м"]].to_numpy(dtype=float)
    pz = out[["frame_corner_ПЗ_x_м", "frame_corner_ПЗ_y_м", "frame_corner_ПЗ_z_м"]].to_numpy(dtype=float)
    local = np.zeros_like(pts)
    for i in range(len(pts)):
        center, rot = orthonormal_frame_from_corners(lp[i], pp[i], lz[i], pz[i])
        local[i] = (pts[i] - center) @ rot
    return local


def _segment_distance(points_xyz: np.ndarray, a_xyz: np.ndarray, b_xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ab = b_xyz - a_xyz
    lab2 = np.sum(ab * ab, axis=1)
    t = np.zeros(len(points_xyz), dtype=float)
    mask = lab2 > 1e-12
    if np.any(mask):
        t[mask] = np.sum((points_xyz - a_xyz)[mask] * ab[mask], axis=1) / lab2[mask]
    t = np.clip(t, 0.0, 1.0)
    proj = a_xyz + ab * t[:, None]
    dist = np.linalg.norm(points_xyz - proj, axis=1)
    return dist, t


def test_full_dw2d_frame_mounts_stay_rigid_in_body_frame() -> None:
    n = 5
    df = pd.DataFrame({
        'рама_угол_ЛП_z_м': np.array([0.40, 0.41, 0.43, 0.42, 0.39]),
        'рама_угол_ПП_z_м': np.array([0.20, 0.22, 0.25, 0.23, 0.21]),
        'рама_угол_ЛЗ_z_м': np.array([0.38, 0.39, 0.41, 0.40, 0.37]),
        'рама_угол_ПЗ_z_м': np.array([0.19, 0.20, 0.22, 0.21, 0.18]),
        'перемещение_колеса_ЛП_м': np.array([0.30, 0.31, 0.33, 0.32, 0.29]),
        'перемещение_колеса_ПП_м': np.array([0.31, 0.32, 0.34, 0.33, 0.30]),
        'перемещение_колеса_ЛЗ_м': np.array([0.29, 0.30, 0.32, 0.31, 0.28]),
        'перемещение_колеса_ПЗ_м': np.array([0.30, 0.31, 0.33, 0.32, 0.29]),
        'дорога_ЛП_м': np.zeros(n),
        'дорога_ПП_м': np.zeros(n),
        'дорога_ЛЗ_м': np.zeros(n),
        'дорога_ПЗ_м': np.zeros(n),
        'путь_x_м': np.linspace(0.0, 2.0, n),
        'путь_y_м': np.linspace(0.0, 0.4, n),
        'yaw_рад': np.linspace(0.0, 0.35, n),
    })
    out = append_solver_points_full_dw2d(
        df,
        x_pos=[0.75, 0.75, -0.75, -0.75],
        y_pos=[0.5, -0.5, 0.5, -0.5],
        frame_z_cols={c: f'рама_угол_{c}_z_м' for c in CORNERS},
        wheel_z_cols={c: f'перемещение_колеса_{c}_м' for c in CORNERS},
        road_z_cols={c: f'дорога_{c}_м' for c in CORNERS},
        x_path_col='путь_x_м',
        y_path_col='путь_y_м',
        yaw_col='yaw_рад',
        inboard_front_m=0.35,
        inboard_rear_m=0.35,
        pivot_z_front_m=0.0,
        pivot_z_rear_m=0.0,
        lower_arm_len_front_m=0.35,
        lower_arm_len_rear_m=0.35,
        upper_inboard_front_m=0.35,
        upper_inboard_rear_m=0.35,
        upper_pivot_z_front_m=0.10,
        upper_pivot_z_rear_m=0.10,
        upper_arm_len_front_m=0.35,
        upper_arm_len_rear_m=0.35,
        topsep_c1_m=[0.30, 0.30, 0.30, 0.30],
        topz_c1_m=[0.60, 0.60, 0.60, 0.60],
        lowfrac_c1=[0.65, 0.65, 0.65, 0.65],
        topsep_c2_m=[0.30, 0.30, 0.30, 0.30],
        topz_c2_m=[0.60, 0.60, 0.60, 0.60],
        lowfrac_c2=[0.45, 0.45, 0.45, 0.45],
        topx_c1_m=[0.02, 0.02, -0.02, -0.02],
        topx_c2_m=[-0.02, -0.02, 0.02, 0.02],
        lower_frame_branch_front_x_m=[0.08, 0.08, 0.08, 0.08],
        lower_frame_branch_rear_x_m=[-0.08, -0.08, -0.08, -0.08],
        lower_hub_branch_front_x_m=[0.04, 0.04, 0.04, 0.04],
        lower_hub_branch_rear_x_m=[-0.04, -0.04, -0.04, -0.04],
        upper_frame_branch_front_x_m=[0.08, 0.08, 0.08, 0.08],
        upper_frame_branch_rear_x_m=[-0.08, -0.08, -0.08, -0.08],
        upper_hub_branch_front_x_m=[0.04, 0.04, 0.04, 0.04],
        upper_hub_branch_rear_x_m=[-0.04, -0.04, -0.04, -0.04],
    )

    for kind in ('cyl1_top', 'cyl2_top', 'lower_arm_frame_front', 'upper_arm_frame_rear', 'arm_pivot', 'arm2_pivot'):
        loc = _body_local(out, kind, 'ЛП')
        drift = float(np.max(np.linalg.norm(loc - loc[0], axis=1)))
        assert drift <= 1e-9, (kind, drift)

    # Regression guard: frame corners must no longer be forced onto wheel-center XY.
    wheel_xy = out[['wheel_center_ЛП_x_м', 'wheel_center_ЛП_y_м']].to_numpy(dtype=float)
    frame_xy = out[['frame_corner_ЛП_x_м', 'frame_corner_ЛП_y_м']].to_numpy(dtype=float)
    assert np.max(np.linalg.norm(frame_xy - wheel_xy, axis=1)) > 1e-3


def test_full_dw2d_cylinder_bots_stay_on_selected_arm_branches() -> None:
    n = 4
    df = pd.DataFrame({
        'рама_угол_ЛП_z_м': np.array([0.40, 0.42, 0.41, 0.39]),
        'рама_угол_ПП_z_м': np.array([0.20, 0.22, 0.21, 0.19]),
        'рама_угол_ЛЗ_z_м': np.array([0.38, 0.40, 0.39, 0.37]),
        'рама_угол_ПЗ_z_м': np.array([0.19, 0.21, 0.20, 0.18]),
        'перемещение_колеса_ЛП_м': np.array([0.30, 0.33, 0.31, 0.29]),
        'перемещение_колеса_ПП_м': np.array([0.31, 0.34, 0.32, 0.30]),
        'перемещение_колеса_ЛЗ_м': np.array([0.29, 0.32, 0.30, 0.28]),
        'перемещение_колеса_ПЗ_м': np.array([0.30, 0.33, 0.31, 0.29]),
        'дорога_ЛП_м': np.zeros(n),
        'дорога_ПП_м': np.zeros(n),
        'дорога_ЛЗ_м': np.zeros(n),
        'дорога_ПЗ_м': np.zeros(n),
        'путь_x_м': np.linspace(0.0, 1.0, n),
        'путь_y_м': np.linspace(0.0, 0.2, n),
        'yaw_рад': np.linspace(0.0, 0.2, n),
    })
    out = append_solver_points_full_dw2d(
        df,
        x_pos=[0.75, 0.75, -0.75, -0.75],
        y_pos=[0.5, -0.5, 0.5, -0.5],
        frame_z_cols={c: f'рама_угол_{c}_z_м' for c in CORNERS},
        wheel_z_cols={c: f'перемещение_колеса_{c}_м' for c in CORNERS},
        road_z_cols={c: f'дорога_{c}_м' for c in CORNERS},
        x_path_col='путь_x_м',
        y_path_col='путь_y_м',
        yaw_col='yaw_рад',
        inboard_front_m=0.35,
        inboard_rear_m=0.35,
        pivot_z_front_m=0.0,
        pivot_z_rear_m=0.0,
        lower_arm_len_front_m=0.35,
        lower_arm_len_rear_m=0.35,
        upper_inboard_front_m=0.35,
        upper_inboard_rear_m=0.35,
        upper_pivot_z_front_m=0.10,
        upper_pivot_z_rear_m=0.10,
        upper_arm_len_front_m=0.35,
        upper_arm_len_rear_m=0.35,
        topsep_c1_m=[0.30, 0.30, 0.30, 0.30],
        topz_c1_m=[0.60, 0.60, 0.60, 0.60],
        lowfrac_c1=[0.65, 0.65, 0.65, 0.65],
        topsep_c2_m=[0.30, 0.30, 0.30, 0.30],
        topz_c2_m=[0.60, 0.60, 0.60, 0.60],
        lowfrac_c2=[0.45, 0.45, 0.45, 0.45],
        c1_mount_arm=['нижний_рычаг'] * 4,
        c2_mount_arm=['верхний_рычаг'] * 4,
        c1_branch=['перед'] * 4,
        c2_branch=['зад'] * 4,
        lower_frame_branch_front_x_m=[0.08, 0.08, 0.08, 0.08],
        lower_frame_branch_rear_x_m=[-0.08, -0.08, -0.08, -0.08],
        lower_hub_branch_front_x_m=[0.04, 0.04, 0.04, 0.04],
        lower_hub_branch_rear_x_m=[-0.04, -0.04, -0.04, -0.04],
        upper_frame_branch_front_x_m=[0.08, 0.08, 0.08, 0.08],
        upper_frame_branch_rear_x_m=[-0.08, -0.08, -0.08, -0.08],
        upper_hub_branch_front_x_m=[0.04, 0.04, 0.04, 0.04],
        upper_hub_branch_rear_x_m=[-0.04, -0.04, -0.04, -0.04],
    )

    c1_bot = out[[f'cyl1_bot_ЛП_{a}_м' for a in ('x', 'y', 'z')]].to_numpy(dtype=float)
    lower_front_a = out[[f'lower_arm_frame_front_ЛП_{a}_м' for a in ('x', 'y', 'z')]].to_numpy(dtype=float)
    lower_front_b = out[[f'lower_arm_hub_front_ЛП_{a}_м' for a in ('x', 'y', 'z')]].to_numpy(dtype=float)
    dist1, frac1 = _segment_distance(c1_bot, lower_front_a, lower_front_b)
    assert float(np.max(dist1)) <= 1e-9
    assert float(np.max(np.abs(frac1 - frac1[0]))) <= 1e-9

    c2_bot = out[[f'cyl2_bot_ЛП_{a}_м' for a in ('x', 'y', 'z')]].to_numpy(dtype=float)
    upper_rear_a = out[[f'upper_arm_frame_rear_ЛП_{a}_м' for a in ('x', 'y', 'z')]].to_numpy(dtype=float)
    upper_rear_b = out[[f'upper_arm_hub_rear_ЛП_{a}_м' for a in ('x', 'y', 'z')]].to_numpy(dtype=float)
    dist2, frac2 = _segment_distance(c2_bot, upper_rear_a, upper_rear_b)
    assert float(np.max(dist2)) <= 1e-9
    assert float(np.max(np.abs(frac2 - frac2[0]))) <= 1e-9
