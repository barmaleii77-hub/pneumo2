from __future__ import annotations

"""Helpers for explicit anim_latest truth-contract export.

This module keeps the exporter honest and machine-checkable:
- hardpoints are exposed as explicit family -> corner -> axis NPZ column refs;
- cylinder packaging is surfaced as explicit mount families + geometry refs;
- broken/all-NaN cylinder length series can be backfilled from exact endpoint
  distances without inventing synthetic geometry inside Animator.
"""

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .solver_points_contract import CORNERS, KNOWN_POINT_KINDS, point_cols
from .suspension_family_contract import (
    FAMILY_ORDER,
    canonical_axle_slug,
    canonical_cylinder_slug,
    cylinder_axle_geometry_key,
    spring_geometry_key,
)
from .suspension_family_runtime import spring_family_active_flag_column, spring_family_runtime_column

LogFn = Callable[[str], None]
AXES: tuple[str, str, str] = ("x", "y", "z")

VISIBLE_SUSPENSION_FAMILIES: tuple[str, ...] = (
    "frame_corner",
    "wheel_center",
    "road_contact",
    "lower_arm_frame_front",
    "lower_arm_frame_rear",
    "lower_arm_hub_front",
    "lower_arm_hub_rear",
    "upper_arm_frame_front",
    "upper_arm_frame_rear",
    "upper_arm_hub_front",
    "upper_arm_hub_rear",
    "cyl1_top",
    "cyl1_bot",
    "cyl2_top",
    "cyl2_bot",
)

LEGACY_ALIAS_FAMILIES: tuple[str, ...] = (
    "arm_pivot",
    "arm_joint",
    "arm2_pivot",
    "arm2_joint",
)

HARDPOINT_ROLE_MAP: dict[str, str] = {
    "frame_corner": "rigid frame corner",
    "wheel_center": "wheel center",
    "road_contact": "road contact point",
    "lower_arm_frame_front": "lower arm frame-front mount",
    "lower_arm_frame_rear": "lower arm frame-rear mount",
    "lower_arm_hub_front": "lower arm hub-front mount",
    "lower_arm_hub_rear": "lower arm hub-rear mount",
    "upper_arm_frame_front": "upper arm frame-front mount",
    "upper_arm_frame_rear": "upper arm frame-rear mount",
    "upper_arm_hub_front": "upper arm hub-front mount",
    "upper_arm_hub_rear": "upper arm hub-rear mount",
    "arm_pivot": "legacy lower arm inboard pivot alias",
    "arm_joint": "legacy lower arm outboard joint alias",
    "arm2_pivot": "legacy upper arm inboard pivot alias",
    "arm2_joint": "legacy upper arm outboard joint alias",
    "cyl1_top": "cylinder 1 top mount on frame",
    "cyl1_bot": "cylinder 1 bottom mount on arm",
    "cyl2_top": "cylinder 2 top mount on frame",
    "cyl2_bot": "cylinder 2 bottom mount on arm",
}

CYLINDER_ADVANCED_FIELDS: tuple[str, ...] = (
    "gland_or_sleeve_position_m",
    "rod_eye_length_m",
    "retracted_mount_length_m",
    "extended_mount_length_m",
    "cup_or_seat_points_world_m",
    "explicit_body_axis_world_m",
    "explicit_piston_pose_inside_body",
    "cap_side_vs_rod_side_contract",
)

CYLINDER_CONFIG: dict[str, dict[str, Any]] = {
    "cyl1": {
        "top_family": "cyl1_top",
        "bottom_family": "cyl1_bot",
        "stroke_columns": {corner: f"положение_штока_{corner}_м" for corner in CORNERS},
        "length_candidates": {corner: [f"длина_цилиндра_{corner}_м", f"длина_цилиндра_Ц1_{corner}_м"] for corner in CORNERS},
        "geometry_keys": {
            "bore_diameter_m": "cyl1_bore_diameter_m",
            "rod_diameter_m": "cyl1_rod_diameter_m",
            "outer_diameter_m": "cyl1_outer_diameter_m",
            "stroke_front_m": "cyl1_stroke_front_m",
            "stroke_rear_m": "cyl1_stroke_rear_m",
            "dead_cap_length_m": "cyl1_dead_cap_length_m",
            "dead_rod_length_m": "cyl1_dead_rod_length_m",
            "dead_height_m": "cyl1_dead_height_m",
            "body_length_front_m": "cyl1_body_length_front_m",
            "body_length_rear_m": "cyl1_body_length_rear_m",
            "wall_thickness_m": "cylinder_wall_thickness_m",
            "dead_volume_chamber_m3": "dead_volume_chamber_m3",
        },
    },
    "cyl2": {
        "top_family": "cyl2_top",
        "bottom_family": "cyl2_bot",
        "stroke_columns": {corner: f"положение_штока_Ц2_{corner}_м" for corner in CORNERS},
        "length_candidates": {corner: [f"длина_цилиндра_Ц2_{corner}_м"] for corner in CORNERS},
        "geometry_keys": {
            "bore_diameter_m": "cyl2_bore_diameter_m",
            "rod_diameter_m": "cyl2_rod_diameter_m",
            "outer_diameter_m": "cyl2_outer_diameter_m",
            "stroke_front_m": "cyl2_stroke_front_m",
            "stroke_rear_m": "cyl2_stroke_rear_m",
            "dead_cap_length_m": "cyl2_dead_cap_length_m",
            "dead_rod_length_m": "cyl2_dead_rod_length_m",
            "dead_height_m": "cyl2_dead_height_m",
            "body_length_front_m": "cyl2_body_length_front_m",
            "body_length_rear_m": "cyl2_body_length_rear_m",
            "wall_thickness_m": "cylinder_wall_thickness_m",
            "dead_volume_chamber_m3": "dead_volume_chamber_m3",
        },
    },
}

SPRING_FAMILY_CONFIG: dict[str, dict[str, Any]] = {
    f"{canonical_cylinder_slug(cyl)}_{canonical_axle_slug(axle)}": {
        "cyl": str(cyl),
        "cyl_name": canonical_cylinder_slug(cyl),
        "axle": str(axle),
        "axle_slug": canonical_axle_slug(axle),
        "label": f"{str(cyl)} {str(axle)}",
        "corners": ("ЛП", "ПП") if canonical_axle_slug(axle) == "front" else ("ЛЗ", "ПЗ"),
        "geometry_keys": {
            "wire_diameter_m": spring_geometry_key("wire_diameter_m", cyl, axle),
            "mean_diameter_m": spring_geometry_key("mean_diameter_m", cyl, axle),
            "inner_diameter_m": spring_geometry_key("inner_diameter_m", cyl, axle),
            "outer_diameter_m": spring_geometry_key("outer_diameter_m", cyl, axle),
            "free_length_m": spring_geometry_key("free_length_m", cyl, axle),
            "solid_length_m": spring_geometry_key("solid_length_m", cyl, axle),
            "top_offset_m": spring_geometry_key("top_offset_m", cyl, axle),
            "coil_bind_margin_min_m": spring_geometry_key("coil_bind_margin_min_m", cyl, axle),
            "rebound_preload_min_m": spring_geometry_key("rebound_preload_min_m", cyl, axle),
        },
        "host_geometry_keys": {
            "outer_diameter_m": cylinder_axle_geometry_key("outer_diameter_m", cyl, axle),
            "stroke_m": cylinder_axle_geometry_key("stroke_m", cyl, axle),
            "body_length_m": cylinder_axle_geometry_key("body_length_m", cyl, axle),
        },
    }
    for cyl, axle in FAMILY_ORDER
}

SHARED_SPRING_RUNTIME_AXLES: dict[str, dict[str, Any]] = {
    "front": {
        "axle": "перед",
        "corners": ("ЛП", "ПП"),
    },
    "rear": {
        "axle": "зад",
        "corners": ("ЛЗ", "ПЗ"),
    },
}


def _emit(msg: str, log: LogFn | None) -> None:
    if log is None:
        return
    try:
        log(str(msg))
    except Exception:
        pass


def _columns_set(df_or_columns: Any) -> set[str]:
    if isinstance(df_or_columns, pd.DataFrame):
        return {str(c) for c in df_or_columns.columns}
    if df_or_columns is None:
        return set()
    try:
        return {str(c) for c in df_or_columns}
    except Exception:
        return set()


def _present_triplet(df_or_columns: Any, family: str, corner: str) -> tuple[dict[str, str], bool, bool]:
    cols = _columns_set(df_or_columns)
    mapping: dict[str, str] = {}
    present = []
    for axis, col in zip(AXES, point_cols(family, corner)):
        have = col in cols
        present.append(have)
        mapping[axis] = col if have else ""
    return mapping, all(present), any(present)


def _finite_float_or_none(x: Any) -> float | None:
    try:
        if isinstance(x, bool):
            return None
        v = float(x)
    except Exception:
        return None
    if not np.isfinite(v):
        return None
    return float(v)


def _coerce_series(df: pd.DataFrame, col: str) -> np.ndarray:
    try:
        return np.asarray(df[col], dtype=float).reshape(-1)
    except Exception:
        return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float, copy=True).reshape(-1)


def _distance_from_mounts(df: pd.DataFrame, *, top_family: str, bottom_family: str, corner: str) -> np.ndarray | None:
    top_cols = point_cols(top_family, corner)
    bot_cols = point_cols(bottom_family, corner)
    needed = list(top_cols) + list(bot_cols)
    if any(col not in df.columns for col in needed):
        return None
    try:
        top = np.column_stack([_coerce_series(df, col) for col in top_cols])
        bot = np.column_stack([_coerce_series(df, col) for col in bot_cols])
    except Exception:
        return None
    diff = np.asarray(top - bot, dtype=float)
    dist = np.linalg.norm(diff, axis=1)
    bad = ~np.all(np.isfinite(diff), axis=1)
    if np.any(bad):
        dist = np.asarray(dist, dtype=float)
        dist[bad] = np.nan
    return np.asarray(dist, dtype=float)


def ensure_cylinder_length_columns(
    df_main: pd.DataFrame,
    *,
    log: LogFn | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fill broken cylinder length series from exact endpoint distances when possible.

    Policy:
    - never invent absolute geometry;
    - only derive the scalar length from already-exported explicit mount points;
    - patch existing columns when they contain NaN holes or are entirely NaN;
    - do not create brand-new columns silently when the producer never exported one.
    """
    if not isinstance(df_main, pd.DataFrame):
        return df_main, {"schema": "anim_export.length_repair.v1", "cylinders": {}}

    out = df_main
    copied = False
    summary: dict[str, Any] = {"schema": "anim_export.length_repair.v1", "cylinders": {}}

    for cyl_name, cfg in CYLINDER_CONFIG.items():
        cyl_block: dict[str, Any] = {"corners": {}}
        top_family = str(cfg["top_family"])
        bottom_family = str(cfg["bottom_family"])
        repaired_columns: list[str] = []
        for corner in CORNERS:
            candidates = list((cfg.get("length_candidates") or {}).get(corner) or [])
            existing = next((name for name in candidates if name in out.columns), "")
            derived = _distance_from_mounts(out, top_family=top_family, bottom_family=bottom_family, corner=corner)
            item: dict[str, Any] = {
                "column": existing,
                "candidate_columns": candidates,
                "top_family": top_family,
                "bottom_family": bottom_family,
                "status": "missing",
            }
            if existing:
                arr = _coerce_series(out, existing)
                finite = np.isfinite(arr)
                if finite.all() and arr.size:
                    item["status"] = "already_finite"
                elif derived is not None and derived.shape == arr.shape and np.isfinite(derived).any():
                    fill_mask = ~finite & np.isfinite(derived)
                    if np.any(fill_mask):
                        if not copied:
                            out = out.copy()
                            copied = True
                        patched = np.asarray(arr, dtype=float).copy()
                        patched[fill_mask] = derived[fill_mask]
                        out[existing] = patched
                        item["status"] = "filled_from_endpoint_distance" if not finite.any() else "patched_nonfinite_from_endpoint_distance"
                        item["filled_points"] = int(np.sum(fill_mask))
                        item["finite_points_after"] = int(np.isfinite(patched).sum())
                        repaired_columns.append(existing)
                    else:
                        item["status"] = "no_finite_mount_distance"
                else:
                    item["status"] = "no_finite_mount_distance"
            else:
                if derived is not None and np.isfinite(derived).any():
                    item["status"] = "missing_can_be_derived_from_mount_distance"
                else:
                    item["status"] = "missing_and_no_mount_distance"
            cyl_block["corners"][corner] = item
        cyl_block["repaired_columns"] = repaired_columns
        summary["cylinders"][cyl_name] = cyl_block

    if copied:
        repaired_preview = []
        for cyl_name, cyl_block in summary["cylinders"].items():
            for col in cyl_block.get("repaired_columns") or []:
                repaired_preview.append(f"{cyl_name}:{col}")
        if repaired_preview:
            _emit(
                "[anim_export_contract] backfilled cylinder length columns from explicit mount distances: "
                + ", ".join(repaired_preview),
                log,
            )
    return out, summary


def build_solver_points_block(df_or_columns: Any) -> dict[str, Any]:
    cols = _columns_set(df_or_columns)
    full_families: list[str] = []
    partial_families: list[str] = []
    visible_full: list[str] = []
    visible_partial: list[str] = []
    legacy_full: list[str] = []
    legacy_partial: list[str] = []
    for family in KNOWN_POINT_KINDS:
        family_has_full = False
        family_has_any = False
        for corner in CORNERS:
            _mapping, full, any_present = _present_triplet(cols, family, corner)
            family_has_full = family_has_full or full
            family_has_any = family_has_any or any_present
        if family_has_full:
            full_families.append(family)
            if family in VISIBLE_SUSPENSION_FAMILIES:
                visible_full.append(family)
            if family in LEGACY_ALIAS_FAMILIES:
                legacy_full.append(family)
        elif family_has_any:
            partial_families.append(family)
            if family in VISIBLE_SUSPENSION_FAMILIES:
                visible_partial.append(family)
            if family in LEGACY_ALIAS_FAMILIES:
                legacy_partial.append(family)
    return {
        "schema": "solver_points.contract.v1",
        "representation": "explicit_world_xyz_columns_in_npz",
        "space": "world_m",
        "source_ref": {"matrix": "main_values", "cols": "main_cols"},
        "families_present": full_families,
        "families_partial": partial_families,
        "visible_suspension_skeleton_families": visible_full,
        "partial_visible_suspension_skeleton_families": visible_partial,
        "legacy_alias_families": legacy_full,
        "partial_legacy_alias_families": legacy_partial,
        "hardpoints_block_ref": "meta.hardpoints",
        "notes": [
            "Animator should prefer explicit family refs from meta.hardpoints when present.",
            "This block intentionally references NPZ columns and does not duplicate time-series payload.",
        ],
    }


def build_hardpoints_block(df_or_columns: Any) -> dict[str, Any]:
    cols = _columns_set(df_or_columns)
    families: dict[str, Any] = {}
    canonical_full: list[str] = []
    partial_families: list[str] = []
    for family in tuple(VISIBLE_SUSPENSION_FAMILIES) + tuple(LEGACY_ALIAS_FAMILIES):
        fam_block: dict[str, Any] = {
            "role": HARDPOINT_ROLE_MAP.get(family, family.replace("_", " ")),
            "kind": "dynamic_world_point",
            "coverage": "missing",
            "corners": {},
            "missing_corners": [],
            "partial_corners": [],
        }
        full_count = 0
        any_count = 0
        for corner in CORNERS:
            column_map, full, any_present = _present_triplet(cols, family, corner)
            corner_block = {"column_map": column_map}
            fam_block["corners"][corner] = corner_block
            if full:
                full_count += 1
                any_count += 1
            elif any_present:
                any_count += 1
                fam_block["partial_corners"].append(corner)
            else:
                fam_block["missing_corners"].append(corner)
        if full_count == len(CORNERS):
            fam_block["coverage"] = "full"
            if family in VISIBLE_SUSPENSION_FAMILIES:
                canonical_full.append(family)
        elif any_count > 0:
            fam_block["coverage"] = "partial"
            partial_families.append(family)
        else:
            fam_block["coverage"] = "missing"
        if fam_block["coverage"] != "missing":
            families[family] = fam_block
    return {
        "schema": "hardpoints.export.v1",
        "space": "world_m",
        "corner_order": list(CORNERS),
        "canonical_families": canonical_full,
        "partial_families": partial_families,
        "families": families,
        "notes": [
            "Each family points back to canonical NPZ columns; no geometry is reconstructed here.",
            "Family coverage may be partial on older bundles that do not export optional wishbone hardpoints.",
        ],
    }


def _geometry_value_map(geometry: Mapping[str, Any], key_map: Mapping[str, str]) -> tuple[dict[str, float], list[str]]:
    resolved: dict[str, float] = {}
    missing: list[str] = []
    for public_key, geom_key in key_map.items():
        value = _finite_float_or_none(geometry.get(geom_key))
        if value is None:
            missing.append(public_key)
        else:
            resolved[public_key] = float(value)
    return resolved, missing


def _geometry_value_or_none(geometry: Mapping[str, Any], key: str) -> float | None:
    return _finite_float_or_none(geometry.get(key))


def _finite_min_over_columns(df: pd.DataFrame, columns: Sequence[str]) -> float | None:
    mins: list[float] = []
    for col in columns:
        if not col or col not in df.columns:
            continue
        arr = _coerce_series(df, col)
        finite = arr[np.isfinite(arr)]
        if finite.size:
            mins.append(float(np.min(finite)))
    if not mins:
        return None
    return float(min(mins))


def _finite_mean_t0_over_columns(df: pd.DataFrame, columns: Sequence[str]) -> float | None:
    vals: list[float] = []
    for col in columns:
        if not col or col not in df.columns:
            continue
        arr = _coerce_series(df, col)
        finite = arr[np.isfinite(arr)]
        if finite.size:
            vals.append(float(finite[0]))
    if not vals:
        return None
    return float(np.mean(vals))


def _point_t0_xyz(df: pd.DataFrame, *, family: str, corner: str) -> np.ndarray | None:
    cols = point_cols(family, corner)
    if any(col not in df.columns for col in cols):
        return None
    values: list[float] = []
    for col in cols:
        arr = _coerce_series(df, col)
        if arr.size <= 0:
            return None
        value = _finite_float_or_none(arr[0])
        if value is None:
            return None
        values.append(float(value))
    return np.asarray(values, dtype=float)


def _point_segment_distance(point: np.ndarray, seg_a: np.ndarray, seg_b: np.ndarray) -> float:
    seg = np.asarray(seg_b - seg_a, dtype=float)
    denom = float(np.dot(seg, seg))
    if denom <= 1e-24:
        return float(np.linalg.norm(np.asarray(point - seg_a, dtype=float)))
    t = float(np.dot(np.asarray(point - seg_a, dtype=float), seg) / denom)
    t = min(1.0, max(0.0, t))
    proj = np.asarray(seg_a + t * seg, dtype=float)
    return float(np.linalg.norm(np.asarray(point - proj, dtype=float)))


def _segment_segment_distance(seg1_a: np.ndarray, seg1_b: np.ndarray, seg2_a: np.ndarray, seg2_b: np.ndarray) -> float:
    # Exact shortest distance between 3D segments; needed for same-corner spring pair clearance.
    u = np.asarray(seg1_b - seg1_a, dtype=float)
    v = np.asarray(seg2_b - seg2_a, dtype=float)
    w = np.asarray(seg1_a - seg2_a, dtype=float)
    a = float(np.dot(u, u))
    b = float(np.dot(u, v))
    c = float(np.dot(v, v))
    d = float(np.dot(u, w))
    e = float(np.dot(v, w))
    denom = a * c - b * b
    small = 1e-12

    if a <= small and c <= small:
        return float(np.linalg.norm(np.asarray(seg1_a - seg2_a, dtype=float)))
    if a <= small:
        return _point_segment_distance(np.asarray(seg1_a, dtype=float), np.asarray(seg2_a, dtype=float), np.asarray(seg2_b, dtype=float))
    if c <= small:
        return _point_segment_distance(np.asarray(seg2_a, dtype=float), np.asarray(seg1_a, dtype=float), np.asarray(seg1_b, dtype=float))

    s_num = 0.0
    s_den = denom
    t_num = 0.0
    t_den = denom
    if denom <= small:
        s_num = 0.0
        s_den = 1.0
        t_num = e
        t_den = c
    else:
        s_num = b * e - c * d
        t_num = a * e - b * d
        if s_num < 0.0:
            s_num = 0.0
            t_num = e
            t_den = c
        elif s_num > s_den:
            s_num = s_den
            t_num = e + b
            t_den = c

    if t_num < 0.0:
        t_num = 0.0
        if -d < 0.0:
            s_num = 0.0
        elif -d > a:
            s_num = s_den
        else:
            s_num = -d
            s_den = a
    elif t_num > t_den:
        t_num = t_den
        if (-d + b) < 0.0:
            s_num = 0.0
        elif (-d + b) > a:
            s_num = s_den
        else:
            s_num = -d + b
            s_den = a

    sc = 0.0 if abs(s_num) <= small else float(s_num / s_den)
    tc = 0.0 if abs(t_num) <= small else float(t_num / t_den)
    delta = np.asarray(w + sc * u - tc * v, dtype=float)
    return float(np.linalg.norm(delta))


def _cylinder_geometry_by_axle(geometry: Mapping[str, Any], cyl_name: str) -> tuple[dict[str, dict[str, float]], dict[str, list[str]]]:
    cyl = "Ц1" if str(cyl_name) == "cyl1" else "Ц2"
    resolved_by_axle: dict[str, dict[str, float]] = {}
    missing_by_axle: dict[str, list[str]] = {}
    for axle in ("перед", "зад"):
        axle_slug = canonical_axle_slug(axle)
        primary_map = {
            "bore_diameter_m": cylinder_axle_geometry_key("bore_diameter_m", cyl, axle),
            "rod_diameter_m": cylinder_axle_geometry_key("rod_diameter_m", cyl, axle),
            "outer_diameter_m": cylinder_axle_geometry_key("outer_diameter_m", cyl, axle),
            "stroke_m": cylinder_axle_geometry_key("stroke_m", cyl, axle),
            "dead_cap_length_m": cylinder_axle_geometry_key("dead_cap_length_m", cyl, axle),
            "dead_rod_length_m": cylinder_axle_geometry_key("dead_rod_length_m", cyl, axle),
            "dead_height_m": cylinder_axle_geometry_key("dead_height_m", cyl, axle),
            "body_length_m": cylinder_axle_geometry_key("body_length_m", cyl, axle),
        }
        fallback_map = {
            "bore_diameter_m": f"{cyl_name}_bore_diameter_m",
            "rod_diameter_m": f"{cyl_name}_rod_diameter_m",
            "outer_diameter_m": f"{cyl_name}_outer_diameter_m",
            "dead_cap_length_m": f"{cyl_name}_dead_cap_length_m",
            "dead_rod_length_m": f"{cyl_name}_dead_rod_length_m",
            "dead_height_m": f"{cyl_name}_dead_height_m",
        }
        resolved: dict[str, float] = {}
        missing: list[str] = []
        for public_key, primary_key in primary_map.items():
            value = _geometry_value_or_none(geometry, primary_key)
            if value is None and public_key in fallback_map:
                value = _geometry_value_or_none(geometry, fallback_map[public_key])
            if value is None:
                missing.append(public_key)
            else:
                resolved[public_key] = float(value)
        resolved_by_axle[axle_slug] = resolved
        missing_by_axle[axle_slug] = missing
    return resolved_by_axle, missing_by_axle


def _cylinder_midstroke_diagnostics(
    df: pd.DataFrame,
    *,
    cyl_name: str,
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    cyl = "Ц1" if str(cyl_name) == "cyl1" else "Ц2"
    stroke_columns = CYLINDER_CONFIG[cyl_name]["stroke_columns"]
    out: dict[str, Any] = {}
    for axle in ("перед", "зад"):
        axle_slug = canonical_axle_slug(axle)
        corners = ("ЛП", "ПП") if axle_slug == "front" else ("ЛЗ", "ПЗ")
        t0_mean = _finite_mean_t0_over_columns(df, [str(stroke_columns[c]) for c in corners])
        stroke_len = _geometry_value_or_none(geometry, cylinder_axle_geometry_key("stroke_m", cyl, axle))
        item: dict[str, Any] = {
            "stroke_position_t0_mean_m": t0_mean,
            "stroke_length_m": stroke_len,
            "midstroke_target_m": (0.5 * stroke_len) if stroke_len is not None else None,
        }
        if t0_mean is not None and stroke_len is not None and stroke_len > 0.0:
            item["midstroke_error_t0_m"] = float(t0_mean - 0.5 * stroke_len)
            item["midstroke_error_ratio_t0"] = float((t0_mean - 0.5 * stroke_len) / stroke_len)
        out[axle_slug] = item
    return out


def _build_shared_spring_runtime_block(df_or_columns: Any) -> dict[str, Any]:
    cols = _columns_set(df_or_columns)
    if not isinstance(df_or_columns, pd.DataFrame):
        return {
            axle_slug: {
                "axle": cfg["axle"],
                "corners": list(cfg["corners"]),
                "spring_length_columns": [f"пружина_длина_{corner}_м" if f"пружина_длина_{corner}_м" in cols else "" for corner in cfg["corners"]],
                "gap_to_cap_columns": [f"пружина_зазор_до_крышки_{corner}_м" if f"пружина_зазор_до_крышки_{corner}_м" in cols else "" for corner in cfg["corners"]],
                "coil_bind_margin_columns": [f"пружина_запас_до_coil_bind_{corner}_м" if f"пружина_запас_до_coil_bind_{corner}_м" in cols else "" for corner in cfg["corners"]],
                "min_gap_to_cap_m": None,
                "min_coil_bind_margin_m": None,
                "notes": [
                    "Current runtime spring columns are shared by axle and do not encode C1/C2 ownership explicitly.",
                ],
            }
            for axle_slug, cfg in SHARED_SPRING_RUNTIME_AXLES.items()
        }

    out: dict[str, Any] = {}
    for axle_slug, cfg in SHARED_SPRING_RUNTIME_AXLES.items():
        length_cols = [f"пружина_длина_{corner}_м" for corner in cfg["corners"] if f"пружина_длина_{corner}_м" in df_or_columns.columns]
        gap_cols = [f"пружина_зазор_до_крышки_{corner}_м" for corner in cfg["corners"] if f"пружина_зазор_до_крышки_{corner}_м" in df_or_columns.columns]
        bind_cols = [f"пружина_запас_до_coil_bind_{corner}_м" for corner in cfg["corners"] if f"пружина_запас_до_coil_bind_{corner}_м" in df_or_columns.columns]
        out[axle_slug] = {
            "axle": cfg["axle"],
            "corners": list(cfg["corners"]),
            "spring_length_columns": length_cols,
            "gap_to_cap_columns": gap_cols,
            "coil_bind_margin_columns": bind_cols,
            "spring_length_t0_mean_m": _finite_mean_t0_over_columns(df_or_columns, length_cols),
            "min_gap_to_cap_m": _finite_min_over_columns(df_or_columns, gap_cols),
            "min_coil_bind_margin_m": _finite_min_over_columns(df_or_columns, bind_cols),
            "notes": [
                "Current runtime spring columns are shared by axle and do not encode C1/C2 ownership explicitly.",
            ],
        }
    return out


def _build_family_spring_runtime_block(df_or_columns: Any, *, cyl: str, corners: Sequence[str]) -> dict[str, Any]:
    cols = _columns_set(df_or_columns)
    active_flag_columns = [spring_family_active_flag_column(cyl, corner) for corner in corners]
    compression_columns = [spring_family_runtime_column("компрессия_м", cyl, corner) for corner in corners]
    length_columns = [spring_family_runtime_column("длина_м", cyl, corner) for corner in corners]
    gap_columns = [spring_family_runtime_column("зазор_до_крышки_м", cyl, corner) for corner in corners]
    coil_columns = [spring_family_runtime_column("запас_до_coil_bind_м", cyl, corner) for corner in corners]
    installed_columns = [spring_family_runtime_column("длина_установленная_м", cyl, corner) for corner in corners]

    if not isinstance(df_or_columns, pd.DataFrame):
        return {
            "active_flag_columns": [col if col in cols else "" for col in active_flag_columns],
            "compression_columns": [col if col in cols else "" for col in compression_columns],
            "length_columns": [col if col in cols else "" for col in length_columns],
            "gap_to_cap_columns": [col if col in cols else "" for col in gap_columns],
            "coil_bind_margin_columns": [col if col in cols else "" for col in coil_columns],
            "installed_length_columns": [col if col in cols else "" for col in installed_columns],
            "runtime_source": "explicit_family_columns" if any(col in cols for col in active_flag_columns + length_columns + gap_columns + coil_columns + installed_columns) else "missing",
            "active_t0_mean": None,
            "compression_t0_mean_m": None,
            "length_t0_mean_m": None,
            "installed_length_t0_mean_m": None,
            "min_gap_to_cap_m": None,
            "min_coil_bind_margin_m": None,
        }

    active_present = [col for col in active_flag_columns if col in df_or_columns.columns]
    compression_present = [col for col in compression_columns if col in df_or_columns.columns]
    length_present = [col for col in length_columns if col in df_or_columns.columns]
    gap_present = [col for col in gap_columns if col in df_or_columns.columns]
    coil_present = [col for col in coil_columns if col in df_or_columns.columns]
    installed_present = [col for col in installed_columns if col in df_or_columns.columns]
    runtime_source = (
        "explicit_family_columns"
        if any([active_present, compression_present, length_present, gap_present, coil_present, installed_present])
        else "missing"
    )
    return {
        "active_flag_columns": active_present,
        "compression_columns": compression_present,
        "length_columns": length_present,
        "gap_to_cap_columns": gap_present,
        "coil_bind_margin_columns": coil_present,
        "installed_length_columns": installed_present,
        "runtime_source": runtime_source,
        "active_t0_mean": _finite_mean_t0_over_columns(df_or_columns, active_present),
        "compression_t0_mean_m": _finite_mean_t0_over_columns(df_or_columns, compression_present),
        "length_t0_mean_m": _finite_mean_t0_over_columns(df_or_columns, length_present),
        "installed_length_t0_mean_m": _finite_mean_t0_over_columns(df_or_columns, installed_present),
        "min_gap_to_cap_m": _finite_min_over_columns(df_or_columns, gap_present),
        "min_coil_bind_margin_m": _finite_min_over_columns(df_or_columns, coil_present),
    }


def _build_spring_pair_clearance_block(
    df_or_columns: Any,
    *,
    spring_families: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(df_or_columns, pd.DataFrame):
        return {}, []

    out: dict[str, Any] = {}
    interference_corners: list[str] = []
    for axle_slug, corners in (("front", ("ЛП", "ПП")), ("rear", ("ЛЗ", "ПЗ"))):
        family_1 = f"cyl1_{axle_slug}"
        family_2 = f"cyl2_{axle_slug}"
        block_1 = dict(spring_families.get(family_1) or {})
        block_2 = dict(spring_families.get(family_2) or {})
        geom_1 = dict(block_1.get("resolved_geometry") or {})
        geom_2 = dict(block_2.get("resolved_geometry") or {})
        outer_1 = _finite_float_or_none(geom_1.get("outer_diameter_m"))
        outer_2 = _finite_float_or_none(geom_2.get("outer_diameter_m"))
        for corner in corners:
            top_1 = _point_t0_xyz(df_or_columns, family="cyl1_top", corner=corner)
            bot_1 = _point_t0_xyz(df_or_columns, family="cyl1_bot", corner=corner)
            top_2 = _point_t0_xyz(df_or_columns, family="cyl2_top", corner=corner)
            bot_2 = _point_t0_xyz(df_or_columns, family="cyl2_bot", corner=corner)
            centerline_distance = None
            radial_clearance = None
            clearance_ok = None
            if top_1 is not None and bot_1 is not None and top_2 is not None and bot_2 is not None:
                centerline_distance = _segment_segment_distance(top_1, bot_1, top_2, bot_2)
                if outer_1 is not None and outer_2 is not None:
                    radial_clearance = float(centerline_distance - 0.5 * (outer_1 + outer_2))
                    clearance_ok = bool(radial_clearance >= -1e-12)
                    if not clearance_ok:
                        interference_corners.append(str(corner))
            out[str(corner)] = {
                "corner": str(corner),
                "axle_slug": str(axle_slug),
                "family_pair": [family_1, family_2],
                "mount_family_pair": {
                    family_1: {"top": "cyl1_top", "bottom": "cyl1_bot"},
                    family_2: {"top": "cyl2_top", "bottom": "cyl2_bot"},
                },
                "spring_outer_diameter_m": {
                    family_1: outer_1,
                    family_2: outer_2,
                },
                "centerline_distance_t0_m": centerline_distance,
                "radial_clearance_t0_m": radial_clearance,
                "clearance_ok": clearance_ok,
            }
    return out, interference_corners


def _nonempty_value(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, str):
        return bool(x.strip())
    if isinstance(x, (list, tuple, dict, set)):
        return bool(x)
    return True


def build_packaging_block(
    meta: Mapping[str, Any] | None,
    df_or_columns: Any,
    *,
    length_repair: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    geometry = dict(meta_dict.get("geometry") or {}) if isinstance(meta_dict.get("geometry"), Mapping) else {}
    existing_packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    existing_cylinders = dict(existing_packaging.get("cylinders") or {}) if isinstance(existing_packaging.get("cylinders"), Mapping) else {}
    cols = _columns_set(df_or_columns)
    length_repair_dict = dict(length_repair or {})
    length_repair_cyl = dict(length_repair_dict.get("cylinders") or {}) if isinstance(length_repair_dict.get("cylinders"), Mapping) else {}
    shared_spring_runtime = _build_shared_spring_runtime_block(df_or_columns)

    cylinders_out: dict[str, Any] = {}
    cylinder_geometry_by_name: dict[str, dict[str, dict[str, float]]] = {}
    all_missing_advanced: list[str] = []
    complete_flags: list[bool] = []

    for cyl_name, cfg in CYLINDER_CONFIG.items():
        existing_cyl = dict(existing_cylinders.get(cyl_name) or {}) if isinstance(existing_cylinders.get(cyl_name), Mapping) else {}
        resolved_geometry, missing_geometry = _geometry_value_map(geometry, cfg["geometry_keys"])
        resolved_geometry_by_axle, missing_geometry_by_axle = _cylinder_geometry_by_axle(geometry, cyl_name)
        length_corner_summary = dict((length_repair_cyl.get(cyl_name) or {}).get("corners") or {}) if isinstance(length_repair_cyl.get(cyl_name), Mapping) else {}
        stroke_position_columns = {
            corner: (str(cfg["stroke_columns"][corner]) if str(cfg["stroke_columns"][corner]) in cols else "")
            for corner in CORNERS
        }
        length_columns = {
            corner: str((length_corner_summary.get(corner) or {}).get("column") or "")
            for corner in CORNERS
        }
        length_status_by_corner = {
            corner: str((length_corner_summary.get(corner) or {}).get("status") or "missing")
            for corner in CORNERS
        }
        advanced_present = [name for name in CYLINDER_ADVANCED_FIELDS if _nonempty_value(existing_cyl.get(name))]
        advanced_missing = [name for name in CYLINDER_ADVANCED_FIELDS if name not in advanced_present]
        all_missing_advanced.extend([name for name in advanced_missing if name not in all_missing_advanced])
        length_ok = all(
            length_status_by_corner.get(corner) in {
                "already_finite",
                "filled_from_endpoint_distance",
                "patched_nonfinite_from_endpoint_distance",
            }
            for corner in CORNERS
        )
        axle_geometry_complete = all(not bool(missing) for missing in missing_geometry_by_axle.values())
        geometry_ok = not bool(missing_geometry) or axle_geometry_complete
        advanced_ok = not bool(advanced_missing)
        contract_complete = bool(length_ok and geometry_ok and advanced_ok)
        complete_flags.append(contract_complete)
        cylinder_geometry_by_name[cyl_name] = resolved_geometry_by_axle

        cyl_block: dict[str, Any] = {
            "mount_families": {
                "top": str(cfg["top_family"]),
                "bottom": str(cfg["bottom_family"]),
            },
            "mount_roles": {
                "top": HARDPOINT_ROLE_MAP.get(str(cfg["top_family"]), str(cfg["top_family"])),
                "bottom": HARDPOINT_ROLE_MAP.get(str(cfg["bottom_family"]), str(cfg["bottom_family"])),
            },
            "stroke_position_columns": stroke_position_columns,
            "length_columns": length_columns,
            "length_status_by_corner": length_status_by_corner,
            "geometry_key_refs": {public_key: f"geometry.{geom_key}" for public_key, geom_key in dict(cfg["geometry_keys"]).items()},
            "resolved_geometry": resolved_geometry,
            "missing_geometry_fields": missing_geometry,
            "geometry_key_refs_by_axle": {
                axle_slug: {
                    public_key: f"geometry.{geom_key}"
                    for public_key, geom_key in {
                        "bore_diameter_m": cylinder_axle_geometry_key("bore_diameter_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "rod_diameter_m": cylinder_axle_geometry_key("rod_diameter_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "outer_diameter_m": cylinder_axle_geometry_key("outer_diameter_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "stroke_m": cylinder_axle_geometry_key("stroke_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "dead_cap_length_m": cylinder_axle_geometry_key("dead_cap_length_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "dead_rod_length_m": cylinder_axle_geometry_key("dead_rod_length_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "dead_height_m": cylinder_axle_geometry_key("dead_height_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                        "body_length_m": cylinder_axle_geometry_key("body_length_m", "Ц1" if cyl_name == "cyl1" else "Ц2", "перед" if axle_slug == "front" else "зад"),
                    }.items()
                }
                for axle_slug in ("front", "rear")
            },
            "resolved_geometry_by_axle": resolved_geometry_by_axle,
            "missing_geometry_fields_by_axle": missing_geometry_by_axle,
            "stroke_midstroke_t0_by_axle": _cylinder_midstroke_diagnostics(
                df_or_columns if isinstance(df_or_columns, pd.DataFrame) else pd.DataFrame(),
                cyl_name=cyl_name,
                geometry=geometry,
            ) if isinstance(df_or_columns, pd.DataFrame) else {},
            "advanced_fields_present": advanced_present,
            "advanced_fields_missing": advanced_missing,
            "contract_complete": contract_complete,
            "notes": [
                "Animator must not invent missing absolute packaging geometry.",
                "When advanced fields are absent, consumers should stay in simplified body/rod truth mode and warn explicitly.",
            ],
        }
        for field in CYLINDER_ADVANCED_FIELDS:
            if field in existing_cyl:
                cyl_block[field] = deepcopy(existing_cyl[field])
        cylinders_out[cyl_name] = cyl_block

    spring_families_out: dict[str, Any] = {}
    spring_host_interference_families: list[str] = []
    for family_name, cfg in SPRING_FAMILY_CONFIG.items():
        resolved_geometry, missing_geometry = _geometry_value_map(geometry, cfg["geometry_keys"])
        host_geometry_all = dict(cylinder_geometry_by_name.get(str(cfg["cyl_name"])) or {})
        host_geometry = dict(host_geometry_all.get(str(cfg["axle_slug"])) or {})
        runtime_family = _build_family_spring_runtime_block(
            df_or_columns,
            cyl=str(cfg["cyl"]),
            corners=list(cfg["corners"]),
        )
        shared_runtime_block = dict(shared_spring_runtime.get(str(cfg["axle_slug"])) or {})
        runtime_source = str(runtime_family.get("runtime_source") or "missing")
        if runtime_source == "missing" and shared_runtime_block:
            runtime_source = "shared_axle_fallback"
        host_missing = [
            field
            for field in ("outer_diameter_m", "stroke_m", "body_length_m")
            if field not in host_geometry
        ]
        host_clearance = None
        host_ok = None
        if "inner_diameter_m" in resolved_geometry and "outer_diameter_m" in host_geometry:
            host_clearance = float(0.5 * (resolved_geometry["inner_diameter_m"] - host_geometry["outer_diameter_m"]))
            host_ok = bool(host_clearance >= -1e-12)
            if not host_ok:
                spring_host_interference_families.append(family_name)
        spring_families_out[family_name] = {
            "label": str(cfg["label"]),
            "axle": str(cfg["axle"]),
            "axle_slug": str(cfg["axle_slug"]),
            "corners": list(cfg["corners"]),
            "host_cylinder": str(cfg["cyl_name"]),
            "geometry_key_refs": {
                public_key: f"geometry.{geom_key}"
                for public_key, geom_key in dict(cfg["geometry_keys"]).items()
            },
            "host_geometry_key_refs": {
                public_key: f"geometry.{geom_key}"
                for public_key, geom_key in dict(cfg["host_geometry_keys"]).items()
            },
            "resolved_geometry": resolved_geometry,
            "missing_geometry_fields": missing_geometry,
            "resolved_host_geometry": host_geometry,
            "missing_host_geometry_fields": host_missing,
            "host_radial_clearance_m": host_clearance,
            "host_clearance_ok": host_ok,
            "runtime_family": runtime_family,
            "runtime_shared_axle": shared_runtime_block,
            "shared_runtime_axle_ref": str(cfg["axle_slug"]),
            "runtime_source": runtime_source,
            "notes": [
                "Spring family geometry is explicit by C1/C2 × front/rear and keeps project-side longitudinal symmetry.",
                "When explicit family runtime columns are absent, exporter falls back to shared axle runtime instead of inventing a hidden C1/C2 owner.",
            ],
        }

    spring_pair_clearance_by_corner, spring_pair_interference_corners = _build_spring_pair_clearance_block(
        df_or_columns,
        spring_families=spring_families_out,
    )

    status = "complete" if complete_flags and all(complete_flags) else "partial"
    return {
        "schema": "cylinder_packaging.contract.v1",
        "status": status,
        "representation": "geometry_scalars_plus_mount_refs",
        "required_advanced_fields": list(CYLINDER_ADVANCED_FIELDS),
        "missing_advanced_fields": all_missing_advanced,
        "cylinders": cylinders_out,
        "spring_families": spring_families_out,
        "shared_spring_runtime_by_axle": shared_spring_runtime,
        "spring_host_interference_families": spring_host_interference_families,
        "spring_pair_clearance_by_corner": spring_pair_clearance_by_corner,
        "spring_pair_interference_corners": spring_pair_interference_corners,
        "notes": [
            "Scalar geometry lives in meta.geometry and is referenced here explicitly.",
            "Mount points are referenced through meta.hardpoints families and main_values/main_cols NPZ refs.",
            "Length columns may be backfilled from explicit endpoint distance during anim_latest export when the producer emitted NaN-only series.",
            "Spring runtime prefers explicit family columns and falls back to shared axle diagnostics only when older bundles do not export the family owner yet.",
        ],
    }


def augment_anim_latest_meta(
    meta: Mapping[str, Any] | None,
    *,
    df_main: pd.DataFrame,
    length_repair: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(meta or {})
    out["solver_points"] = build_solver_points_block(df_main)
    out["hardpoints"] = build_hardpoints_block(df_main)
    out["packaging"] = build_packaging_block(out, df_main, length_repair=length_repair)
    return out


def summarize_anim_export_contract(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    solver_points = dict(meta_dict.get("solver_points") or {}) if isinstance(meta_dict.get("solver_points"), Mapping) else {}
    hardpoints = dict(meta_dict.get("hardpoints") or {}) if isinstance(meta_dict.get("hardpoints"), Mapping) else {}
    packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    cylinders = dict(packaging.get("cylinders") or {}) if isinstance(packaging.get("cylinders"), Mapping) else {}
    spring_families = dict(packaging.get("spring_families") or {}) if isinstance(packaging.get("spring_families"), Mapping) else {}
    shared_spring_runtime = dict(packaging.get("shared_spring_runtime_by_axle") or {}) if isinstance(packaging.get("shared_spring_runtime_by_axle"), Mapping) else {}
    spring_pair_clearance = dict(packaging.get("spring_pair_clearance_by_corner") or {}) if isinstance(packaging.get("spring_pair_clearance_by_corner"), Mapping) else {}
    truth_ready = bool(packaging.get("status") == "complete")
    missing_advanced = [str(x) for x in list(packaging.get("missing_advanced_fields") or []) if str(x).strip()]
    complete_cylinders = [name for name, block in cylinders.items() if bool(dict(block or {}).get("contract_complete"))]
    spring_host_interference_families = [
        str(name)
        for name, block in spring_families.items()
        if dict(block or {}).get("host_clearance_ok") is False
    ]
    spring_runtime_negative_families = [
        str(name)
        for name, block in spring_families.items()
        if (
            (_finite_float_or_none(dict(dict(block or {}).get("runtime_family") or {}).get("min_gap_to_cap_m")) is not None and float(dict(dict(block or {}).get("runtime_family") or {}).get("min_gap_to_cap_m")) < 0.0)
            or (_finite_float_or_none(dict(dict(block or {}).get("runtime_family") or {}).get("min_coil_bind_margin_m")) is not None and float(dict(dict(block or {}).get("runtime_family") or {}).get("min_coil_bind_margin_m")) < 0.0)
        )
    ]
    spring_runtime_fallback_families = [
        str(name)
        for name, block in spring_families.items()
        if str(dict(block or {}).get("runtime_source") or "missing") == "shared_axle_fallback"
    ]
    spring_pair_interference_corners = [
        str(name)
        for name, block in spring_pair_clearance.items()
        if dict(block or {}).get("clearance_ok") is False
    ]
    shared_spring_runtime_negative_axes = [
        str(name)
        for name, block in shared_spring_runtime.items()
        if (
            (_finite_float_or_none(dict(block or {}).get("min_gap_to_cap_m")) is not None and float(dict(block or {}).get("min_gap_to_cap_m")) < 0.0)
            or (_finite_float_or_none(dict(block or {}).get("min_coil_bind_margin_m")) is not None and float(dict(block or {}).get("min_coil_bind_margin_m")) < 0.0)
        )
    ]
    return {
        "has_solver_points_block": bool(solver_points),
        "has_hardpoints_block": bool(hardpoints),
        "has_packaging_block": bool(packaging),
        "packaging_status": str(packaging.get("status") or ""),
        "packaging_missing_advanced_fields": missing_advanced,
        "packaging_truth_ready": truth_ready,
        "visible_hardpoint_family_count": int(len(list((solver_points.get("visible_suspension_skeleton_families") or [])))),
        "hardpoints_family_count": int(len(list((hardpoints.get("families") or {}).keys()))),
        "complete_cylinders": complete_cylinders,
        "complete_cylinder_count": int(len(complete_cylinders)),
        "spring_family_count": int(len(spring_families)),
        "spring_host_interference_families": spring_host_interference_families,
        "spring_pair_interference_corners": spring_pair_interference_corners,
        "spring_runtime_negative_families": spring_runtime_negative_families,
        "spring_runtime_fallback_families": spring_runtime_fallback_families,
        "shared_spring_runtime_negative_axes": shared_spring_runtime_negative_axes,
    }


def summarize_anim_export_objective_metrics(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    cylinders = dict(packaging.get("cylinders") or {}) if isinstance(packaging.get("cylinders"), Mapping) else {}
    spring_families = dict(packaging.get("spring_families") or {}) if isinstance(packaging.get("spring_families"), Mapping) else {}
    spring_pair_clearance = dict(packaging.get("spring_pair_clearance_by_corner") or {}) if isinstance(packaging.get("spring_pair_clearance_by_corner"), Mapping) else {}

    host_clearances = [
        value
        for value in (
            _finite_float_or_none(dict(block or {}).get("host_radial_clearance_m"))
            for block in spring_families.values()
        )
        if value is not None
    ]
    pair_clearances = [
        value
        for value in (
            _finite_float_or_none(dict(block or {}).get("radial_clearance_t0_m"))
            for block in spring_pair_clearance.values()
        )
        if value is not None
    ]
    midstroke_errors = [
        abs(value)
        for value in (
            _finite_float_or_none(dict(axle_block or {}).get("midstroke_error_t0_m"))
            for cyl_block in cylinders.values()
            for axle_block in dict(dict(cyl_block or {}).get("stroke_midstroke_t0_by_axle") or {}).values()
        )
        if value is not None
    ]
    family_gap_margins: list[float] = []
    family_coil_margins: list[float] = []
    fallback_count = 0
    for block in spring_families.values():
        block_dict = dict(block or {})
        runtime_family = dict(block_dict.get("runtime_family") or {})
        runtime_shared = dict(block_dict.get("runtime_shared_axle") or {})
        runtime_source = str(block_dict.get("runtime_source") or runtime_family.get("runtime_source") or "missing")
        if runtime_source == "shared_axle_fallback":
            fallback_count += 1
        gap = _finite_float_or_none(runtime_family.get("min_gap_to_cap_m"))
        if gap is None:
            gap = _finite_float_or_none(runtime_shared.get("min_gap_to_cap_m"))
        if gap is not None:
            family_gap_margins.append(float(gap))
        coil = _finite_float_or_none(runtime_family.get("min_coil_bind_margin_m"))
        if coil is None:
            coil = _finite_float_or_none(runtime_shared.get("min_coil_bind_margin_m"))
        if coil is not None:
            family_coil_margins.append(float(coil))

    host_interference_count = sum(1 for block in spring_families.values() if dict(block or {}).get("host_clearance_ok") is False)
    pair_interference_count = sum(1 for block in spring_pair_clearance.values() if dict(block or {}).get("clearance_ok") is False)
    return {
        "anim_export_packaging_status": str(packaging.get("status") or ""),
        "anim_export_packaging_truth_ready": bool(packaging.get("status") == "complete"),
        "мин_зазор_пружина_цилиндр_м": float(min(host_clearances)) if host_clearances else float("nan"),
        "мин_зазор_пружина_пружина_м": float(min(pair_clearances)) if pair_clearances else float("nan"),
        "макс_ошибка_midstroke_t0_м": float(max(midstroke_errors)) if midstroke_errors else float("nan"),
        "мин_зазор_пружина_до_крышки_м": float(min(family_gap_margins)) if family_gap_margins else float("nan"),
        "мин_запас_до_coil_bind_пружины_м": float(min(family_coil_margins)) if family_coil_margins else float("nan"),
        "число_пересечений_пружина_цилиндр": int(host_interference_count),
        "число_пересечений_пружина_пружина": int(pair_interference_count),
        "число_runtime_fallback_пружины": int(fallback_count),
    }


from pathlib import Path
import json

ANIM_EXPORT_CONTRACT_SIDECAR_NAME = "anim_latest.contract.sidecar.json"
ANIM_EXPORT_CONTRACT_VALIDATION_JSON_NAME = "anim_latest.contract.validation.json"
ANIM_EXPORT_CONTRACT_VALIDATION_MD_NAME = "anim_latest.contract.validation.md"
HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME = "HARDPOINTS_SOURCE_OF_TRUTH.json"
CYLINDER_PACKAGING_PASSPORT_JSON_NAME = "CYLINDER_PACKAGING_PASSPORT.json"


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def build_hardpoints_source_of_truth(
    meta: Mapping[str, Any] | None,
    *,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    hardpoints = dict(meta_dict.get("hardpoints") or {}) if isinstance(meta_dict.get("hardpoints"), Mapping) else {}
    families = dict(hardpoints.get("families") or {}) if isinstance(hardpoints.get("families"), Mapping) else {}
    visible_present = [name for name in VISIBLE_SUSPENSION_FAMILIES if dict(families.get(name) or {}).get("coverage") == "full"]
    visible_partial = [name for name in VISIBLE_SUSPENSION_FAMILIES if dict(families.get(name) or {}).get("coverage") == "partial"]
    visible_missing = [name for name in VISIBLE_SUSPENSION_FAMILIES if name not in visible_present and name not in visible_partial]
    legacy_present = [name for name in LEGACY_ALIAS_FAMILIES if name in families]
    complete = bool(not visible_partial and not visible_missing and bool(visible_present))
    return {
        "schema": "hardpoints.source_of_truth.v1",
        "updated_utc": str(updated_utc or meta_dict.get("updated_utc") or ""),
        "npz_path": str(npz_path or ""),
        "pointer_path": str(pointer_path or ""),
        "space": str(hardpoints.get("space") or "world_m"),
        "representation": "explicit_npz_column_refs_only",
        "complete": complete,
        "visible_required_families": list(VISIBLE_SUSPENSION_FAMILIES),
        "visible_present_families": visible_present,
        "visible_partial_families": visible_partial,
        "visible_missing_families": visible_missing,
        "legacy_alias_families_present": legacy_present,
        "families": _jsonable(families),
        "notes": [
            "Animator and downstream consumers must use these explicit family/corner/axis refs as source-of-truth.",
            "No hidden alias reconstruction or fabricated hardpoints are allowed downstream.",
        ],
    }


def build_cylinder_packaging_passport(
    meta: Mapping[str, Any] | None,
    *,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    cylinders = dict(packaging.get("cylinders") or {}) if isinstance(packaging.get("cylinders"), Mapping) else {}
    spring_families = dict(packaging.get("spring_families") or {}) if isinstance(packaging.get("spring_families"), Mapping) else {}
    shared_spring_runtime = dict(packaging.get("shared_spring_runtime_by_axle") or {}) if isinstance(packaging.get("shared_spring_runtime_by_axle"), Mapping) else {}
    spring_pair_clearance = dict(packaging.get("spring_pair_clearance_by_corner") or {}) if isinstance(packaging.get("spring_pair_clearance_by_corner"), Mapping) else {}
    cyl_statuses: dict[str, Any] = {}
    complete_cylinders: list[str] = []
    axis_only_cylinders: list[str] = []
    for cyl_name, block in cylinders.items():
        cyl_block = dict(block or {}) if isinstance(block, Mapping) else {}
        contract_complete = bool(cyl_block.get("contract_complete"))
        if contract_complete:
            complete_cylinders.append(str(cyl_name))
        else:
            axis_only_cylinders.append(str(cyl_name))
        cyl_statuses[str(cyl_name)] = {
            "contract_complete": contract_complete,
            "mount_families": _jsonable(cyl_block.get("mount_families") or {}),
            "mount_roles": _jsonable(cyl_block.get("mount_roles") or {}),
            "length_columns": _jsonable(cyl_block.get("length_columns") or {}),
            "length_status_by_corner": _jsonable(cyl_block.get("length_status_by_corner") or {}),
            "resolved_geometry": _jsonable(cyl_block.get("resolved_geometry") or {}),
            "missing_geometry_fields": list(cyl_block.get("missing_geometry_fields") or []),
            "advanced_fields_present": list(cyl_block.get("advanced_fields_present") or []),
            "advanced_fields_missing": list(cyl_block.get("advanced_fields_missing") or []),
            "truth_mode": "full_mesh_allowed" if contract_complete else "axis_only_honesty_mode",
        }
    return {
        "schema": "cylinder_packaging_passport.v1",
        "updated_utc": str(updated_utc or meta_dict.get("updated_utc") or ""),
        "npz_path": str(npz_path or ""),
        "pointer_path": str(pointer_path or ""),
        "packaging_status": str(packaging.get("status") or ""),
        "required_advanced_fields": list(packaging.get("required_advanced_fields") or list(CYLINDER_ADVANCED_FIELDS)),
        "missing_advanced_fields": list(packaging.get("missing_advanced_fields") or []),
        "complete_cylinders": complete_cylinders,
        "axis_only_cylinders": axis_only_cylinders,
        "cylinders": cyl_statuses,
        "spring_families": _jsonable(spring_families),
        "shared_spring_runtime_by_axle": _jsonable(shared_spring_runtime),
        "spring_host_interference_families": list(packaging.get("spring_host_interference_families") or []),
        "spring_pair_clearance_by_corner": _jsonable(spring_pair_clearance),
        "spring_pair_interference_corners": list(packaging.get("spring_pair_interference_corners") or []),
        "consumer_policy": {
            "complete_contract": "Desktop Animator may render body/rod/piston meshes.",
            "partial_contract": "Desktop Animator must stay in axis-only honesty mode and warn explicitly.",
        },
        "notes": [
            "This passport is exporter-owned truth and must be preferred over renderer heuristics.",
            "Missing advanced fields are a producer/export gap, not a license for fabricated geometry.",
            "Spring family geometry addendum is explicit even when runtime spring ownership remains axle-shared.",
        ],
    }


def build_anim_export_contract_sidecar(
    meta: Mapping[str, Any] | None,
    *,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    geometry = dict(meta_dict.get("geometry") or {}) if isinstance(meta_dict.get("geometry"), Mapping) else {}
    solver_points = dict(meta_dict.get("solver_points") or {}) if isinstance(meta_dict.get("solver_points"), Mapping) else {}
    hardpoints = dict(meta_dict.get("hardpoints") or {}) if isinstance(meta_dict.get("hardpoints"), Mapping) else {}
    packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    validation = dict(meta_dict.get("anim_export_validation") or {}) if isinstance(meta_dict.get("anim_export_validation"), Mapping) else {}
    scenario = {
        key: _jsonable(meta_dict.get(key))
        for key in (
            "scenario_kind",
            "test_type",
            "test_name",
            "road_len_m",
            "vx0_м_с",
            "dt",
            "t_end",
            "road_csv",
            "axay_csv",
            "scenario_json",
        )
        if key in meta_dict
    }
    return {
        "schema": "anim_export_contract.sidecar.v1",
        "updated_utc": str(updated_utc or meta_dict.get("updated_utc") or ""),
        "npz_path": str(npz_path or ""),
        "pointer_path": str(pointer_path or ""),
        "scenario": _jsonable(scenario),
        "geometry": _jsonable(geometry),
        "solver_points": _jsonable(solver_points),
        "hardpoints": _jsonable(hardpoints),
        "packaging": _jsonable(packaging),
        "validation": _jsonable(validation),
    }


def validate_anim_export_contract_meta(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    solver_summary = summarize_anim_export_contract(meta_dict)
    hardpoints = dict(meta_dict.get("hardpoints") or {}) if isinstance(meta_dict.get("hardpoints"), Mapping) else {}
    packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    hardpoint_families = dict(hardpoints.get("families") or {}) if isinstance(hardpoints.get("families"), Mapping) else {}
    spring_families = dict(packaging.get("spring_families") or {}) if isinstance(packaging.get("spring_families"), Mapping) else {}
    shared_spring_runtime = dict(packaging.get("shared_spring_runtime_by_axle") or {}) if isinstance(packaging.get("shared_spring_runtime_by_axle"), Mapping) else {}
    spring_pair_clearance = dict(packaging.get("spring_pair_clearance_by_corner") or {}) if isinstance(packaging.get("spring_pair_clearance_by_corner"), Mapping) else {}
    visible_present = [name for name in VISIBLE_SUSPENSION_FAMILIES if dict(hardpoint_families.get(name) or {}).get("coverage") == "full"]
    visible_partial = [name for name in VISIBLE_SUSPENSION_FAMILIES if dict(hardpoint_families.get(name) or {}).get("coverage") == "partial"]
    visible_missing = [name for name in VISIBLE_SUSPENSION_FAMILIES if name not in visible_present and name not in visible_partial]
    messages: list[str] = []
    failures: list[str] = []
    warnings: list[str] = []

    if not solver_summary.get("has_solver_points_block"):
        failures.append("missing meta.solver_points")
    if not solver_summary.get("has_hardpoints_block"):
        failures.append("missing meta.hardpoints")
    if visible_partial:
        failures.append("partial visible hardpoint families: " + ", ".join(visible_partial))
    if visible_missing:
        failures.append("missing visible hardpoint families: " + ", ".join(visible_missing))
    if not solver_summary.get("has_packaging_block"):
        warnings.append("missing meta.packaging")
    elif str(packaging.get("status") or "") != "complete":
        warnings.append(
            "packaging truth-contract is partial: "
            + (", ".join(str(x) for x in (packaging.get("missing_advanced_fields") or [])) or "advanced packaging fields missing")
        )

    spring_host_interference = [
        str(name)
        for name, block in spring_families.items()
        if dict(block or {}).get("host_clearance_ok") is False
    ]
    if spring_host_interference:
        failures.append("spring/cylinder interference by family: " + ", ".join(spring_host_interference))

    spring_pair_interference = [
        str(name)
        for name, block in spring_pair_clearance.items()
        if dict(block or {}).get("clearance_ok") is False
    ]
    if spring_pair_interference:
        failures.append("spring/spring interference by corner: " + ", ".join(spring_pair_interference))

    spring_runtime_failures: list[str] = []
    spring_runtime_fallback_families: list[str] = []
    for family_name, block in spring_families.items():
        runtime_family = dict(dict(block or {}).get("runtime_family") or {})
        runtime_source = str(dict(block or {}).get("runtime_source") or runtime_family.get("runtime_source") or "missing")
        gap = _finite_float_or_none(runtime_family.get("min_gap_to_cap_m"))
        if gap is not None and gap < 0.0:
            spring_runtime_failures.append(f"{family_name}: negative family gap-to-cap {gap:.6g} m")
        coil = _finite_float_or_none(runtime_family.get("min_coil_bind_margin_m"))
        if coil is not None and coil < 0.0:
            spring_runtime_failures.append(f"{family_name}: negative family coil-bind margin {coil:.6g} m")
        if runtime_source == "explicit_family_columns":
            active = _finite_float_or_none(runtime_family.get("active_t0_mean"))
            if active is not None and active not in (0.0, 1.0):
                warnings.append(f"{family_name}: spring active flag is not binary at t0")
        elif runtime_source == "shared_axle_fallback":
            spring_runtime_fallback_families.append(str(family_name))
    if spring_runtime_failures:
        failures.append("spring family runtime violations: " + ", ".join(spring_runtime_failures))
    if spring_runtime_fallback_families:
        warnings.append("spring runtime still uses shared axle fallback: " + ", ".join(sorted(set(spring_runtime_fallback_families))))

    shared_spring_failures: list[str] = []
    explicit_runtime_present = any(
        str(dict(dict(block or {}).get("runtime_family") or {}).get("runtime_source") or "missing") == "explicit_family_columns"
        for block in spring_families.values()
    )
    for axle_name, block in shared_spring_runtime.items():
        gap = _finite_float_or_none(dict(block or {}).get("min_gap_to_cap_m"))
        if gap is not None and gap < 0.0 and not explicit_runtime_present:
            shared_spring_failures.append(f"{axle_name}: negative gap-to-cap {gap:.6g} m")
        coil = _finite_float_or_none(dict(block or {}).get("min_coil_bind_margin_m"))
        if coil is not None and coil < 0.0 and not explicit_runtime_present:
            shared_spring_failures.append(f"{axle_name}: negative coil-bind margin {coil:.6g} m")
    if shared_spring_failures:
        failures.append("shared spring runtime violations: " + ", ".join(shared_spring_failures))

    if failures:
        level = "FAIL"
        messages.extend(failures)
        messages.extend(warnings)
    elif warnings:
        level = "WARN"
        messages.extend(warnings)
    else:
        level = "PASS"
        messages.append("anim_export contract is explicit and truth-ready")

    return {
        "schema": "anim_export_contract.validation.v1",
        "level": level,
        "summary": {
            **{k: _jsonable(v) for k, v in solver_summary.items()},
            "visible_required_family_count": len(VISIBLE_SUSPENSION_FAMILIES),
            "visible_present_family_count": len(visible_present),
            "visible_present_families": visible_present,
            "visible_partial_families": visible_partial,
            "visible_missing_families": visible_missing,
            "validation_level": level,
        },
        "messages": messages,
        "failures": failures,
        "warnings": warnings,
    }


def render_anim_export_contract_validation_md(report: Mapping[str, Any] | None) -> str:
    rep = dict(report or {})
    summary = dict(rep.get("summary") or {}) if isinstance(rep.get("summary"), Mapping) else {}
    lines = [
        "# anim export contract validation",
        "",
        f"- level: **{rep.get('level') or 'FAIL'}**",
        f"- has_solver_points_block: {summary.get('has_solver_points_block')}",
        f"- has_hardpoints_block: {summary.get('has_hardpoints_block')}",
        f"- has_packaging_block: {summary.get('has_packaging_block')}",
        f"- packaging_status: {summary.get('packaging_status') or '—'}",
        f"- packaging_truth_ready: {summary.get('packaging_truth_ready')}",
        f"- visible_present_family_count: {summary.get('visible_present_family_count')} / {summary.get('visible_required_family_count')}",
        f"- spring_family_count: {summary.get('spring_family_count')}",
    ]
    msgs = [str(x) for x in (rep.get("messages") or []) if str(x).strip()]
    if msgs:
        lines.extend(["", "## messages", *[f"- {x}" for x in msgs]])
    missing_adv = [str(x) for x in (summary.get("packaging_missing_advanced_fields") or []) if str(x).strip()]
    if missing_adv:
        lines.extend(["", "## packaging_missing_advanced_fields", *[f"- {x}" for x in missing_adv]])
    missing_vis = [str(x) for x in (summary.get("visible_missing_families") or []) if str(x).strip()]
    if missing_vis:
        lines.extend(["", "## visible_missing_families", *[f"- {x}" for x in missing_vis]])
    partial_vis = [str(x) for x in (summary.get("visible_partial_families") or []) if str(x).strip()]
    if partial_vis:
        lines.extend(["", "## visible_partial_families", *[f"- {x}" for x in partial_vis]])
    spring_interference = [str(x) for x in (summary.get("spring_host_interference_families") or []) if str(x).strip()]
    if spring_interference:
        lines.extend(["", "## spring_host_interference_families", *[f"- {x}" for x in spring_interference]])
    spring_pair_interference = [str(x) for x in (summary.get("spring_pair_interference_corners") or []) if str(x).strip()]
    if spring_pair_interference:
        lines.extend(["", "## spring_pair_interference_corners", *[f"- {x}" for x in spring_pair_interference]])
    spring_runtime_families = [str(x) for x in (summary.get("spring_runtime_negative_families") or []) if str(x).strip()]
    if spring_runtime_families:
        lines.extend(["", "## spring_runtime_negative_families", *[f"- {x}" for x in spring_runtime_families]])
    spring_runtime_fallback = [str(x) for x in (summary.get("spring_runtime_fallback_families") or []) if str(x).strip()]
    if spring_runtime_fallback:
        lines.extend(["", "## spring_runtime_fallback_families", *[f"- {x}" for x in spring_runtime_fallback]])
    spring_runtime_axes = [str(x) for x in (summary.get("shared_spring_runtime_negative_axes") or []) if str(x).strip()]
    if spring_runtime_axes:
        lines.extend(["", "## shared_spring_runtime_negative_axes", *[f"- {x}" for x in spring_runtime_axes]])
    return "\n".join(lines).rstrip() + "\n"


def write_anim_export_contract_artifacts(
    exports_dir: str | Path,
    *,
    meta: Mapping[str, Any] | None,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
) -> dict[str, Any]:
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)
    report = validate_anim_export_contract_meta(meta)
    sidecar = build_anim_export_contract_sidecar(
        meta,
        updated_utc=updated_utc,
        npz_path=npz_path,
        pointer_path=pointer_path,
    )
    hardpoints_sot = build_hardpoints_source_of_truth(
        meta,
        updated_utc=updated_utc,
        npz_path=npz_path,
        pointer_path=pointer_path,
    )
    packaging_passport = build_cylinder_packaging_passport(
        meta,
        updated_utc=updated_utc,
        npz_path=npz_path,
        pointer_path=pointer_path,
    )
    sidecar_path = exports_dir / ANIM_EXPORT_CONTRACT_SIDECAR_NAME
    report_json_path = exports_dir / ANIM_EXPORT_CONTRACT_VALIDATION_JSON_NAME
    report_md_path = exports_dir / ANIM_EXPORT_CONTRACT_VALIDATION_MD_NAME
    hardpoints_sot_path = exports_dir / HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME
    packaging_passport_path = exports_dir / CYLINDER_PACKAGING_PASSPORT_JSON_NAME
    sidecar_path.write_text(json.dumps(_jsonable(sidecar), ensure_ascii=False, indent=2), encoding="utf-8")
    report_json_path.write_text(json.dumps(_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(render_anim_export_contract_validation_md(report), encoding="utf-8")
    hardpoints_sot_path.write_text(json.dumps(_jsonable(hardpoints_sot), ensure_ascii=False, indent=2), encoding="utf-8")
    packaging_passport_path.write_text(json.dumps(_jsonable(packaging_passport), ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "sidecar_path": str(sidecar_path),
        "validation_json_path": str(report_json_path),
        "validation_md_path": str(report_md_path),
        "hardpoints_source_of_truth_path": str(hardpoints_sot_path),
        "cylinder_packaging_passport_path": str(packaging_passport_path),
        "report": report,
    }


def summarize_anim_export_validation(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    validation = dict(meta_dict.get("anim_export_validation") or {}) if isinstance(meta_dict.get("anim_export_validation"), Mapping) else {}
    if not validation:
        report = validate_anim_export_contract_meta(meta_dict)
        validation = dict(report.get("summary") or {}) if isinstance(report.get("summary"), Mapping) else {}
        validation.setdefault("validation_level", report.get("level"))
    return {
        "validation_level": str(validation.get("validation_level") or ""),
        "validation_visible_present_family_count": int(validation.get("visible_present_family_count") or 0),
        "validation_visible_required_family_count": int(validation.get("visible_required_family_count") or 0),
        "validation_visible_missing_families": list(validation.get("visible_missing_families") or []),
        "validation_visible_partial_families": list(validation.get("visible_partial_families") or []),
        "validation_packaging_status": str(validation.get("packaging_status") or ""),
        "validation_packaging_truth_ready": bool(validation.get("packaging_truth_ready")),
    }


__all__ = [
    "AXES",
    "ANIM_EXPORT_CONTRACT_SIDECAR_NAME",
    "ANIM_EXPORT_CONTRACT_VALIDATION_JSON_NAME",
    "ANIM_EXPORT_CONTRACT_VALIDATION_MD_NAME",
    "CYLINDER_PACKAGING_PASSPORT_JSON_NAME",
    "HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME",
    "CYLINDER_ADVANCED_FIELDS",
    "LEGACY_ALIAS_FAMILIES",
    "VISIBLE_SUSPENSION_FAMILIES",
    "augment_anim_latest_meta",
    "build_anim_export_contract_sidecar",
    "build_cylinder_packaging_passport",
    "build_hardpoints_block",
    "build_hardpoints_source_of_truth",
    "build_packaging_block",
    "build_solver_points_block",
    "ensure_cylinder_length_columns",
    "render_anim_export_contract_validation_md",
    "summarize_anim_export_contract",
    "summarize_anim_export_objective_metrics",
    "summarize_anim_export_validation",
    "validate_anim_export_contract_meta",
    "write_anim_export_contract_artifacts",
]
