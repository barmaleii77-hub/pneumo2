from __future__ import annotations

"""Pure helpers for per-cylinder truth-mode gating in Desktop Animator.

Project intent for the current phase:
- if explicit packaging truth is missing, Animator must stay honest and render only
  the solver-derived cylinder axis;
- body/rod/piston volumes are allowed only when the exporter marks the cylinder
  packaging passport complete and all required resolved fields are present;
- partial packaging is useful provenance, but it stays axis-only and carries an
  approximate/unavailable warning instead of invented geometry.
"""

import math
from typing import Any, Mapping

_ALLOWED_LENGTH_STATUSES = {
    "already_finite",
    "filled_from_endpoint_distance",
    "patched_nonfinite_from_endpoint_distance",
}

TRUTH_STATE_SOLVER_CONFIRMED = "solver_confirmed"
TRUTH_STATE_SOURCE_DATA_CONFIRMED = "source_data_confirmed"
TRUTH_STATE_APPROXIMATE = "approximate_inferred_with_warning"
TRUTH_STATE_UNAVAILABLE = "unavailable"
ALLOWED_GRAPHICS_TRUTH_STATES: tuple[str, ...] = (
    TRUTH_STATE_SOLVER_CONFIRMED,
    TRUTH_STATE_SOURCE_DATA_CONFIRMED,
    TRUTH_STATE_APPROXIMATE,
    TRUTH_STATE_UNAVAILABLE,
)


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(x) for x in value if str(x).strip()]


def _finite_positive(value: Any) -> bool:
    try:
        vv = float(value)
    except Exception:
        return False
    return math.isfinite(vv) and vv > 0.0


def evaluate_cylinder_truth_gate(meta: Mapping[str, Any] | None, cyl_name: str) -> dict[str, Any]:
    """Return explicit truth-mode decision for one cylinder.

    Output fields are intentionally JSON-friendly so they can be reused in self-checks
    and diagnostics. ``enabled=True`` means Animator may render body/rod/piston meshes.
    ``enabled=False`` means Animator must keep this cylinder in axis-only honesty mode.
    """
    cyl_key = str(cyl_name or "").strip().lower()
    if cyl_key not in {"cyl1", "cyl2"}:
        raise ValueError(f"Unsupported cylinder key: {cyl_name!r}")

    meta_dict = _as_mapping(meta)
    packaging = _as_mapping(meta_dict.get("packaging"))
    cylinders = _as_mapping(packaging.get("cylinders"))
    cyl_block = _as_mapping(cylinders.get(cyl_key))
    resolved_geometry = _as_mapping(cyl_block.get("resolved_geometry"))
    length_status_by_corner = {
        str(k): str(v)
        for k, v in _as_mapping(cyl_block.get("length_status_by_corner")).items()
        if str(k).strip()
    }
    advanced_missing = _as_str_list(cyl_block.get("advanced_fields_missing"))
    packaging_status = str(packaging.get("status") or "")
    contract_complete = bool(cyl_block.get("contract_complete"))
    length_ok = bool(length_status_by_corner) and all(v in _ALLOWED_LENGTH_STATUSES for v in length_status_by_corner.values())
    basic_geometry_ready = bool(
        _finite_positive(resolved_geometry.get("bore_diameter_m"))
        and _finite_positive(resolved_geometry.get("rod_diameter_m"))
        and _finite_positive(resolved_geometry.get("outer_diameter_m"))
        and (
            _finite_positive(resolved_geometry.get("body_length_front_m"))
            or _finite_positive(resolved_geometry.get("body_length_rear_m"))
        )
    )
    has_packaging_block = bool(packaging)
    has_cylinder_block = bool(cyl_block)
    advanced_geometry_ready = not advanced_missing
    enabled = bool(
        has_packaging_block
        and has_cylinder_block
        and contract_complete
        and length_ok
        and basic_geometry_ready
        and advanced_geometry_ready
    )
    partial_truth_signal = bool(
        packaging_status
        or length_status_by_corner
        or resolved_geometry
        or advanced_missing
        or _as_mapping(cyl_block.get("mount_families"))
    )

    if not has_packaging_block:
        reason = "missing_meta_packaging"
    elif not has_cylinder_block:
        reason = f"missing_{cyl_key}_packaging_block"
    elif enabled:
        reason = f"{cyl_key}_packaging_complete"
    elif contract_complete and advanced_missing:
        reason = f"{cyl_key}_contract_marked_complete_but_missing_advanced_fields"
    elif not contract_complete:
        reason = f"{cyl_key}_packaging_incomplete_axis_only"
    elif advanced_missing:
        reason = f"{cyl_key}_advanced_packaging_missing"
    elif not length_ok:
        reason = f"{cyl_key}_length_contract_incomplete"
    elif not basic_geometry_ready:
        reason = f"{cyl_key}_basic_geometry_missing"
    else:
        reason = f"{cyl_key}_packaging_partial"

    truth_state = (
        TRUTH_STATE_SOLVER_CONFIRMED
        if enabled
        else (TRUTH_STATE_APPROXIMATE if partial_truth_signal and has_cylinder_block else TRUTH_STATE_UNAVAILABLE)
    )

    return {
        "cyl_name": cyl_key,
        "enabled": enabled,
        "mode": "body_rod_piston" if bool(enabled) else "axis_only",
        "reason": reason,
        "truth_state": truth_state,
        "truth_badge": truth_state,
        "warning_required": not bool(enabled),
        "hidden_elements": [] if bool(enabled) else ["body", "rod", "piston"],
        "has_packaging_block": has_packaging_block,
        "has_cylinder_block": has_cylinder_block,
        "packaging_status": packaging_status,
        "contract_complete": contract_complete,
        "length_status_by_corner": length_status_by_corner,
        "length_contract_ready": length_ok,
        "basic_geometry_ready": basic_geometry_ready,
        "advanced_geometry_ready": advanced_geometry_ready,
        "resolved_geometry": resolved_geometry,
        "advanced_fields_missing": advanced_missing,
        "mount_families": _as_mapping(cyl_block.get("mount_families")),
    }


def evaluate_all_cylinder_truth_gates(meta: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        "cyl1": evaluate_cylinder_truth_gate(meta, "cyl1"),
        "cyl2": evaluate_cylinder_truth_gate(meta, "cyl2"),
    }


def render_cylinder_truth_gate_message(gate: Mapping[str, Any] | None) -> str:
    info = _as_mapping(gate)
    cyl = str(info.get("cyl_name") or "cyl?").upper()
    if bool(info.get("enabled")) and str(info.get("mode") or "") == "body_rod_piston":
        return f"{cyl} packaging contract complete -> body/rod/piston truth mode enabled."

    reason = str(info.get("reason") or "axis_only")
    missing_adv = _as_str_list(info.get("advanced_fields_missing"))
    if reason == "missing_meta_packaging":
        tail = "bundle does not export meta.packaging"
    elif reason.startswith("missing_") and reason.endswith("_packaging_block"):
        tail = "bundle does not export explicit cylinder packaging block"
    elif reason.endswith("advanced_packaging_missing") and missing_adv:
        tail = "missing advanced packaging fields: " + ", ".join(missing_adv)
    elif reason.endswith("length_contract_incomplete"):
        tail = "length columns are not explicit/finite for all corners"
    elif reason.endswith("basic_geometry_missing"):
        tail = "resolved basic bore/rod/outer/body geometry is incomplete"
    elif reason.endswith("packaging_incomplete_axis_only") and missing_adv:
        tail = "approximate packaging only; missing advanced fields: " + ", ".join(missing_adv)
    elif reason.endswith("packaging_incomplete_axis_only"):
        tail = "packaging passport is not complete"
    elif "contract_marked_complete_but_missing_advanced_fields" in reason and missing_adv:
        tail = "contract is inconsistent; missing advanced fields: " + ", ".join(missing_adv)
    else:
        tail = "explicit packaging truth is partial"
    return f"{cyl} -> axis-only honesty mode (body/rod/piston meshes disabled): {tail}."


__all__ = [
    "ALLOWED_GRAPHICS_TRUTH_STATES",
    "TRUTH_STATE_SOLVER_CONFIRMED",
    "TRUTH_STATE_SOURCE_DATA_CONFIRMED",
    "TRUTH_STATE_APPROXIMATE",
    "TRUTH_STATE_UNAVAILABLE",
    "evaluate_cylinder_truth_gate",
    "evaluate_all_cylinder_truth_gates",
    "render_cylinder_truth_gate_message",
]
