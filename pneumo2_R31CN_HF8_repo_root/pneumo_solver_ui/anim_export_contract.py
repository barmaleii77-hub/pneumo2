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

    cylinders_out: dict[str, Any] = {}
    all_missing_advanced: list[str] = []
    complete_flags: list[bool] = []

    for cyl_name, cfg in CYLINDER_CONFIG.items():
        existing_cyl = dict(existing_cylinders.get(cyl_name) or {}) if isinstance(existing_cylinders.get(cyl_name), Mapping) else {}
        resolved_geometry, missing_geometry = _geometry_value_map(geometry, cfg["geometry_keys"])
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
        geometry_ok = not bool(missing_geometry)
        advanced_ok = not bool(advanced_missing)
        contract_complete = bool(length_ok and geometry_ok and advanced_ok)
        complete_flags.append(contract_complete)

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

    status = "complete" if complete_flags and all(complete_flags) else "partial"
    return {
        "schema": "cylinder_packaging.contract.v1",
        "status": status,
        "representation": "geometry_scalars_plus_mount_refs",
        "required_advanced_fields": list(CYLINDER_ADVANCED_FIELDS),
        "missing_advanced_fields": all_missing_advanced,
        "cylinders": cylinders_out,
        "notes": [
            "Scalar geometry lives in meta.geometry and is referenced here explicitly.",
            "Mount points are referenced through meta.hardpoints families and main_values/main_cols NPZ refs.",
            "Length columns may be backfilled from explicit endpoint distance during anim_latest export when the producer emitted NaN-only series.",
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
    truth_ready = bool(packaging.get("status") == "complete")
    missing_advanced = [str(x) for x in list(packaging.get("missing_advanced_fields") or []) if str(x).strip()]
    complete_cylinders = [name for name, block in cylinders.items() if bool(dict(block or {}).get("contract_complete"))]
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
        "consumer_policy": {
            "complete_contract": "Desktop Animator may render body/rod/piston meshes.",
            "partial_contract": "Desktop Animator must stay in axis-only honesty mode and warn explicitly.",
        },
        "notes": [
            "This passport is exporter-owned truth and must be preferred over renderer heuristics.",
            "Missing advanced fields are a producer/export gap, not a license for fabricated geometry.",
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
    "summarize_anim_export_validation",
    "validate_anim_export_contract_meta",
    "write_anim_export_contract_artifacts",
]
