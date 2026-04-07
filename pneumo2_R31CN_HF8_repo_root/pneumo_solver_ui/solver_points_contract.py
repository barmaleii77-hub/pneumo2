# -*- coding: utf-8 -*-
"""Canonical solver-point contract for visual bundles.

ABSOLUTE LAW
------------
- Visual suspension geometry must come from explicit model outputs.
- No aliases, no synthetic reconstruction in consumers.
- Producer must emit one canonical name per point/axis.
"""

from __future__ import annotations

from typing import Any, Callable

LogFn = Callable[[str], None]

CORNERS: tuple[str, str, str, str] = ("ЛП", "ПП", "ЛЗ", "ПЗ")
AXES: tuple[str, str, str] = ("x", "y", "z")

# Required baseline contract that every visual bundle must satisfy.
POINT_KINDS: tuple[str, ...] = (
    "arm_pivot",
    "arm_joint",
    "arm2_pivot",
    "arm2_joint",
    "cyl1_top",
    "cyl1_bot",
    "cyl2_top",
    "cyl2_bot",
    "frame_corner",
    "wheel_center",
    "road_contact",
)

# Optional explicit hardpoints for trapezoid wishbone geometry.
# These are accepted by consumers and validated when present, but are not
# required for older bundles that only satisfy the baseline contract.
OPTIONAL_POINT_KINDS: tuple[str, ...] = (
    "lower_arm_frame_front",
    "lower_arm_frame_rear",
    "lower_arm_hub_front",
    "lower_arm_hub_rear",
    "upper_arm_frame_front",
    "upper_arm_frame_rear",
    "upper_arm_hub_front",
    "upper_arm_hub_rear",
)

KNOWN_POINT_KINDS: tuple[str, ...] = POINT_KINDS + OPTIONAL_POINT_KINDS


def _emit(msg: str, log: LogFn | None = None) -> None:
    if log is None:
        return
    try:
        log(msg)
    except Exception:
        pass


def _columns_set(columns: Any) -> set[str]:
    if hasattr(columns, "columns"):
        columns = getattr(columns, "columns")
    if columns is None:
        return set()
    return {str(c) for c in columns}


def point_cols(kind: str, corner: str) -> tuple[str, str, str]:
    if kind not in KNOWN_POINT_KINDS:
        raise ValueError(f"Unknown solver-point kind: {kind!r}")
    if corner not in CORNERS:
        raise ValueError(f"Unknown corner: {corner!r}")
    return tuple(f"{kind}_{corner}_{axis}_м" for axis in AXES)  # type: ignore[return-value]


def _audit_triplet_group(
    cols: set[str],
    *,
    kinds: tuple[str, ...],
    context: str,
    issues: list[str],
    missing_triplets: list[str],
    partial_triplets: list[str],
    present_triplets: list[str],
    missing_columns: list[str],
    required: bool,
) -> None:
    for kind in kinds:
        for corner in CORNERS:
            triplet = point_cols(kind, corner)
            present = [c in cols for c in triplet]
            tag = f"{kind}/{corner}"
            if all(present):
                present_triplets.append(tag)
                continue
            if any(present):
                partial_triplets.append(tag)
                miss = [c for c in triplet if c not in cols]
                missing_columns.extend(miss)
                issues.append(
                    f"[contract] {context}: partial solver-point triplet '{tag}'. Missing columns: {', '.join(miss)}"
                )
                continue
            if required:
                missing_triplets.append(tag)
                missing_columns.extend(list(triplet))


def collect_solver_points_contract_issues(
    columns: Any,
    *,
    context: str = "solver-points contract",
) -> dict[str, Any]:
    cols = _columns_set(columns)
    issues: list[str] = []
    missing_triplets: list[str] = []
    partial_triplets: list[str] = []
    present_triplets: list[str] = []
    missing_columns: list[str] = []

    _audit_triplet_group(
        cols,
        kinds=POINT_KINDS,
        context=context,
        issues=issues,
        missing_triplets=missing_triplets,
        partial_triplets=partial_triplets,
        present_triplets=present_triplets,
        missing_columns=missing_columns,
        required=True,
    )
    _audit_triplet_group(
        cols,
        kinds=OPTIONAL_POINT_KINDS,
        context=context,
        issues=issues,
        missing_triplets=missing_triplets,
        partial_triplets=partial_triplets,
        present_triplets=present_triplets,
        missing_columns=missing_columns,
        required=False,
    )

    if missing_triplets:
        preview = ", ".join(missing_triplets[:4])
        if len(missing_triplets) > 4:
            preview += f", +{len(missing_triplets) - 4} more"
        issues.append(
            f"[contract] {context}: missing canonical solver-point triplets: {preview}"
        )

    return {
        "ok": not issues,
        "issues": issues,
        "missing_triplets": missing_triplets,
        "partial_triplets": partial_triplets,
        "present_triplets": present_triplets,
        "missing_columns": missing_columns,
        "required_point_kinds": list(POINT_KINDS),
        "optional_point_kinds": list(OPTIONAL_POINT_KINDS),
        "known_point_kinds": list(KNOWN_POINT_KINDS),
    }



def assert_required_solver_points_contract(
    columns: Any,
    *,
    context: str,
    log: LogFn | None = None,
) -> dict[str, Any]:
    status = collect_solver_points_contract_issues(columns, context=context)
    issues = list(status.get("issues") or [])
    for msg in issues:
        _emit(msg, log)
    if issues:
        raise ValueError(f"{context}: solver-point contract failed: " + " | ".join(issues))
    return status
