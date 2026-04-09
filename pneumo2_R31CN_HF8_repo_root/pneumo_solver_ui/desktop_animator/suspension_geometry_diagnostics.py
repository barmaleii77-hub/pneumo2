from __future__ import annotations

"""Diagnostics for suspension geometry exported to Desktop Animator.

The goal is honest observability, not visual invention:
- report how many arm geometries are actually serialized per corner;
- report how many cylinder channels exist and how many distinct axes they form;
- warn when C1/C2 are geometrically coincident, because two channels then look like one cylinder.
"""

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from .data_bundle import DataBundle
from .geom3d_helpers import orthonormal_frame_from_corners

CORNERS: tuple[str, str, str, str] = ("ЛП", "ПП", "ЛЗ", "ПЗ")


@dataclass(frozen=True)
class CornerSuspensionSummary:
    corner: str
    lower_arm_present: bool
    upper_arm_present: bool
    arm_geometries_present: int
    expected_arm_geometries: int
    coincident_arm_joints: bool
    max_lower_upper_joint_delta_m: float
    cylinder_channels_present: int
    distinct_cylinder_axes: int
    coincident_cylinder_axes: bool
    max_c1_c2_top_delta_m: float
    max_c1_c2_bot_delta_m: float
    frame_mounts_rigid: bool
    max_frame_mount_body_local_drift_m: float
    wheel_mounts_rigid: bool
    max_hub_mount_pairwise_drift_m: float
    cyl1_bot_on_arm: bool
    max_cyl1_bot_arm_offset_m: float
    cyl2_bot_on_arm: bool
    max_cyl2_bot_arm_offset_m: float


def _derived_cache(bundle: Any) -> Optional[dict[str, Any]]:
    cache = getattr(bundle, "_derived", None)
    if isinstance(cache, dict):
        return cache
    try:
        setattr(bundle, "_derived", {})
    except Exception:
        return None
    cache = getattr(bundle, "_derived", None)
    return cache if isinstance(cache, dict) else None


def _point(bundle: DataBundle, kind: str, corner: str) -> Optional[np.ndarray]:
    try:
        arr = bundle.point_xyz(kind, corner)
    except Exception:
        return None
    if arr is None:
        return None
    out = np.asarray(arr, dtype=float)
    if out.ndim != 2 or out.shape[1] != 3:
        return None
    return out


def _axis_present(bundle: DataBundle, prefix: str, corner: str) -> bool:
    return _point(bundle, f"{prefix}_top", corner) is not None and _point(bundle, f"{prefix}_bot", corner) is not None


def _world_to_body_local(points_xyz: np.ndarray, *, lp: np.ndarray, pp: np.ndarray, lz: np.ndarray, pz: np.ndarray) -> np.ndarray:
    pts = np.asarray(points_xyz, dtype=float)
    out = np.zeros_like(pts)
    for i in range(len(pts)):
        center, rot = orthonormal_frame_from_corners(lp[i], pp[i], lz[i], pz[i])
        out[i] = (pts[i] - center) @ rot
    return out


def _pairwise_distance_drift(point_map: dict[str, np.ndarray]) -> float:
    keys = list(point_map)
    if len(keys) < 2:
        return 0.0
    worst = 0.0
    for i, ka in enumerate(keys):
        for kb in keys[i + 1:]:
            pa = np.asarray(point_map[ka], dtype=float)
            pb = np.asarray(point_map[kb], dtype=float)
            dist = np.linalg.norm(pa - pb, axis=1)
            worst = max(worst, float(np.nanmax(np.abs(dist - dist[0]))))
    return float(worst)


def _segment_distance_and_fraction(points_xyz: np.ndarray, a_xyz: np.ndarray, b_xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(points_xyz, dtype=float)
    a = np.asarray(a_xyz, dtype=float)
    b = np.asarray(b_xyz, dtype=float)
    ab = b - a
    lab2 = np.sum(ab * ab, axis=1)
    t = np.zeros(len(p), dtype=float)
    mask = lab2 > 1e-12
    if np.any(mask):
        t[mask] = np.sum((p - a)[mask] * ab[mask], axis=1) / lab2[mask]
    t = np.clip(t, 0.0, 1.0)
    proj = a + ab * t[:, None]
    d = np.linalg.norm(p - proj, axis=1)
    return d, t


def _min_arm_branch_offset(bundle: DataBundle, corner: str, cyl_kind: str) -> float:
    p = _point(bundle, cyl_kind, corner)
    if p is None:
        return 0.0
    candidates: list[float] = []
    for arm in ("lower", "upper"):
        for branch in ("front", "rear"):
            a = _point(bundle, f"{arm}_arm_frame_{branch}", corner)
            b = _point(bundle, f"{arm}_arm_hub_{branch}", corner)
            if a is None or b is None:
                continue
            dist, _frac = _segment_distance_and_fraction(p, a, b)
            candidates.append(float(np.nanmax(dist)))
    if not candidates:
        return float("inf")
    return float(min(candidates))


def collect_suspension_geometry_status(bundle: DataBundle, tol_m: float = 1e-9) -> dict[str, Any]:
    cache_key = f"_suspension_geometry_status::{float(tol_m):.12g}"
    cache = _derived_cache(bundle)
    cached = cache.get(cache_key) if isinstance(cache, dict) else None
    if isinstance(cached, dict):
        return cached

    rows: list[CornerSuspensionSummary] = []
    issues: list[str] = []
    coincident_corners: list[str] = []
    missing_second_arm: list[str] = []
    coincident_arm_joint_corners: list[str] = []
    frame_drift_corners: list[str] = []
    wheel_drift_corners: list[str] = []
    cyl1_detached_corners: list[str] = []
    cyl2_detached_corners: list[str] = []

    lp = _point(bundle, 'frame_corner', 'ЛП')
    pp = _point(bundle, 'frame_corner', 'ПП')
    lz = _point(bundle, 'frame_corner', 'ЛЗ')
    pz = _point(bundle, 'frame_corner', 'ПЗ')
    frame_basis_ready = lp is not None and pp is not None and lz is not None and pz is not None

    for corner in CORNERS:
        arm_pivot = _point(bundle, "arm_pivot", corner)
        arm_joint = _point(bundle, "arm_joint", corner)
        arm2_pivot = _point(bundle, "arm2_pivot", corner)
        arm2_joint = _point(bundle, "arm2_joint", corner)
        lower_arm_present = arm_pivot is not None and arm_joint is not None
        upper_arm_present = arm2_pivot is not None and arm2_joint is not None
        arm_geometries_present = int(lower_arm_present) + int(upper_arm_present)
        expected_arm_geometries = 2  # project requirement: double wishbone
        if arm_geometries_present < expected_arm_geometries:
            missing_second_arm.append(corner)

        max_joint_delta = 0.0
        coincident_arm_joints = False
        if lower_arm_present and upper_arm_present:
            max_joint_delta = float(np.nanmax(np.linalg.norm(arm_joint - arm2_joint, axis=1)))
            coincident_arm_joints = bool(max_joint_delta <= float(tol_m))
            if coincident_arm_joints:
                coincident_arm_joint_corners.append(corner)

        c1_top = _point(bundle, "cyl1_top", corner)
        c1_bot = _point(bundle, "cyl1_bot", corner)
        c2_top = _point(bundle, "cyl2_top", corner)
        c2_bot = _point(bundle, "cyl2_bot", corner)
        c1_present = c1_top is not None and c1_bot is not None
        c2_present = c2_top is not None and c2_bot is not None
        cylinder_channels_present = int(c1_present) + int(c2_present)

        max_top = 0.0
        max_bot = 0.0
        distinct_axes = 0
        coincident = False
        if c1_present:
            distinct_axes += 1
        if c2_present:
            distinct_axes += 1
        if c1_present and c2_present:
            max_top = float(np.nanmax(np.linalg.norm(c1_top - c2_top, axis=1)))
            max_bot = float(np.nanmax(np.linalg.norm(c1_bot - c2_bot, axis=1)))
            coincident = bool(max(max_top, max_bot) <= float(tol_m))
            if coincident:
                distinct_axes = 1
                coincident_corners.append(corner)

        frame_mounts_rigid = True
        max_frame_drift = 0.0
        if frame_basis_ready:
            frame_local_kinds = [
                'arm_pivot', 'arm2_pivot',
                'lower_arm_frame_front', 'lower_arm_frame_rear',
                'upper_arm_frame_front', 'upper_arm_frame_rear',
                'cyl1_top', 'cyl2_top',
            ]
            for kind in frame_local_kinds:
                pts = _point(bundle, kind, corner)
                if pts is None:
                    continue
                loc = _world_to_body_local(pts, lp=lp, pp=pp, lz=lz, pz=pz)
                drift = float(np.nanmax(np.linalg.norm(loc - loc[0], axis=1)))
                max_frame_drift = max(max_frame_drift, drift)
            frame_mounts_rigid = bool(max_frame_drift <= float(tol_m))
            if not frame_mounts_rigid:
                frame_drift_corners.append(corner)

        wheel_mounts_rigid = True
        max_hub_pair_drift = 0.0
        hub_points = {}
        for kind in ('lower_arm_hub_front', 'lower_arm_hub_rear', 'upper_arm_hub_front', 'upper_arm_hub_rear', 'wheel_center', 'arm_joint', 'arm2_joint'):
            pts = _point(bundle, kind, corner)
            if pts is not None:
                hub_points[kind] = pts
        if hub_points:
            max_hub_pair_drift = _pairwise_distance_drift(hub_points)
            wheel_mounts_rigid = bool(max_hub_pair_drift <= float(tol_m))
            if not wheel_mounts_rigid:
                wheel_drift_corners.append(corner)

        max_cyl1_arm_offset = _min_arm_branch_offset(bundle, corner, 'cyl1_bot')
        max_cyl2_arm_offset = _min_arm_branch_offset(bundle, corner, 'cyl2_bot')
        cyl1_bot_on_arm = bool(max_cyl1_arm_offset <= float(tol_m))
        cyl2_bot_on_arm = bool(max_cyl2_arm_offset <= float(tol_m))
        if c1_present and not cyl1_bot_on_arm:
            cyl1_detached_corners.append(corner)
        if c2_present and not cyl2_bot_on_arm:
            cyl2_detached_corners.append(corner)

        rows.append(
            CornerSuspensionSummary(
                corner=corner,
                lower_arm_present=lower_arm_present,
                upper_arm_present=upper_arm_present,
                arm_geometries_present=arm_geometries_present,
                expected_arm_geometries=expected_arm_geometries,
                coincident_arm_joints=coincident_arm_joints,
                max_lower_upper_joint_delta_m=max_joint_delta,
                cylinder_channels_present=cylinder_channels_present,
                distinct_cylinder_axes=distinct_axes,
                coincident_cylinder_axes=coincident,
                max_c1_c2_top_delta_m=max_top,
                max_c1_c2_bot_delta_m=max_bot,
                frame_mounts_rigid=frame_mounts_rigid,
                max_frame_mount_body_local_drift_m=max_frame_drift,
                wheel_mounts_rigid=wheel_mounts_rigid,
                max_hub_mount_pairwise_drift_m=max_hub_pair_drift,
                cyl1_bot_on_arm=cyl1_bot_on_arm,
                max_cyl1_bot_arm_offset_m=max_cyl1_arm_offset,
                cyl2_bot_on_arm=cyl2_bot_on_arm,
                max_cyl2_bot_arm_offset_m=max_cyl2_arm_offset,
            )
        )

    if missing_second_arm:
        issues.append(
            "double-wishbone visual contract is incomplete: only one arm geometry is serialized for corners "
            + ", ".join(missing_second_arm)
        )
    if coincident_arm_joint_corners:
        issues.append(
            "double-wishbone visual contract is still degenerate: upper/lower arm joints coincide for corners "
            + ", ".join(coincident_arm_joint_corners)
        )
    if coincident_corners:
        issues.append(
            "two cylinder channels are present but their axes are geometrically coincident for corners "
            + ", ".join(coincident_corners)
        )
    if frame_drift_corners:
        issues.append(
            "frame-mounted hardpoints drift relative to the rigid frame for corners "
            + ", ".join(frame_drift_corners)
        )
    if wheel_drift_corners:
        issues.append(
            "hub/wheel-mounted hardpoints drift relative to the wheel/upright for corners "
            + ", ".join(wheel_drift_corners)
        )
    if cyl1_detached_corners:
        issues.append(
            "cyl1_bot is not geometrically attached to an arm branch for corners "
            + ", ".join(cyl1_detached_corners)
        )
    if cyl2_detached_corners:
        issues.append(
            "cyl2_bot is not geometrically attached to an arm branch for corners "
            + ", ".join(cyl2_detached_corners)
        )

    out = {
        "ok": not issues,
        "issues": issues,
        "coincident_cylinder_corners": coincident_corners,
        "missing_second_arm_corners": missing_second_arm,
        "coincident_arm_joint_corners": coincident_arm_joint_corners,
        "frame_drift_corners": frame_drift_corners,
        "wheel_drift_corners": wheel_drift_corners,
        "cyl1_detached_corners": cyl1_detached_corners,
        "cyl2_detached_corners": cyl2_detached_corners,
        "rows": [r.__dict__ for r in rows],
    }
    if isinstance(cache, dict):
        cache[cache_key] = out
    return out


def format_suspension_hud_lines(bundle: DataBundle, tol_m: float = 1e-9) -> list[str]:
    st = collect_suspension_geometry_status(bundle, tol_m=tol_m)
    rows = list(st.get("rows") or [])
    if not rows:
        return []

    arm_present_vals = sorted({int(r.get("arm_geometries_present", 0)) for r in rows})
    arm_expected_vals = sorted({int(r.get("expected_arm_geometries", 0)) for r in rows})
    cyl_channels_vals = sorted({int(r.get("cylinder_channels_present", 0)) for r in rows})
    cyl_distinct_vals = sorted({int(r.get("distinct_cylinder_axes", 0)) for r in rows})
    max_frame_drift = max(float(r.get("max_frame_mount_body_local_drift_m", 0.0)) for r in rows)
    max_hub_drift = max(float(r.get("max_hub_mount_pairwise_drift_m", 0.0)) for r in rows)
    max_c1_offset = max(float(r.get("max_cyl1_bot_arm_offset_m", 0.0)) for r in rows)
    max_c2_offset = max(float(r.get("max_cyl2_bot_arm_offset_m", 0.0)) for r in rows)

    def _fmt(vals: list[int]) -> str:
        return str(vals[0]) if len(vals) == 1 else "/".join(str(v) for v in vals)

    lines = [
        f"Подвеска: рычагов/угол {_fmt(arm_present_vals)}/{_fmt(arm_expected_vals)}, каналов цилиндров {_fmt(cyl_channels_vals)}, осей {_fmt(cyl_distinct_vals)}"
    ]
    if st.get("missing_second_arm_corners"):
        lines.append("DW: второй рычаг не сериализован solver-points")
    if st.get("coincident_arm_joint_corners"):
        lines.append("DW: верхний и нижний рычаг сходятся в одну точку")
    if st.get("coincident_cylinder_corners"):
        lines.append("Цилиндры: C1/C2 совпадают по оси")
    if st.get("frame_drift_corners"):
        lines.append(f"Рама: точки крепления дрейфуют, max {max_frame_drift:.4f} м")
    if st.get("wheel_drift_corners"):
        lines.append(f"Ступицы: точки крепления дрейфуют, max {max_hub_drift:.4f} м")
    if st.get("cyl1_detached_corners") or st.get("cyl2_detached_corners"):
        lines.append(f"Шток→рычаг: off-arm C1/C2 {max_c1_offset:.4f}/{max_c2_offset:.4f} м")
    return lines
