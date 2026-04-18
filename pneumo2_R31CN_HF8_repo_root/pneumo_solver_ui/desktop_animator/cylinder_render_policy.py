from __future__ import annotations

"""Truth-preserving render policy for Desktop Animator cylinders.

The policy separates solver-point axis visibility from full body/rod/piston
visibility. Axis lines may use explicit top/bottom solver-point pairs; full
cylinder meshes require a completed truth gate plus authored render geometry
from the packaging contract.
"""

import math
from typing import Any, Mapping, Sequence


REQUIRED_RENDER_GEOMETRY_FIELDS: tuple[str, ...] = (
    "bore_diameter_m",
    "rod_diameter_m",
    "outer_diameter_m",
    "stroke_m",
    "dead_cap_length_m",
    "dead_rod_length_m",
    "dead_height_m",
    "body_length_m",
)

CYLINDER_RENDER_HIDDEN_ELEMENTS: tuple[str, ...] = (
    "body",
    "rod",
    "piston",
    "chamber",
    "chrome",
    "glass",
    "bloom",
    "rings",
    "glints",
    "caustics",
)

_POSITIVE_FIELDS = {
    "bore_diameter_m",
    "rod_diameter_m",
    "outer_diameter_m",
    "stroke_m",
    "body_length_m",
}


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _normalize_cylinder_key(cyl_name: str | int) -> str:
    text = str(cyl_name or "").strip().lower()
    if text in {"1", "c1", "cyl1", "ц1"}:
        return "cyl1"
    if text in {"2", "c2", "cyl2", "ц2"}:
        return "cyl2"
    raise ValueError(f"Unsupported cylinder key: {cyl_name!r}")


def _normalize_axle_key(axle: str) -> str:
    text = str(axle or "").strip().lower()
    if text in {"front", "f", "перед", "front_axle"}:
        return "front"
    if text in {"rear", "r", "зад", "rear_axle"}:
        return "rear"
    raise ValueError(f"Unsupported cylinder axle key: {axle!r}")


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return out


def _point3(value: Any) -> tuple[float, float, float] | None:
    raw = value
    if hasattr(raw, "tolist"):
        try:
            raw = raw.tolist()
        except Exception:
            raw = value
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return None
    if len(raw) != 3:
        return None
    xyz: list[float] = []
    for component in raw:
        number = _finite_float(component)
        if number is None:
            return None
        xyz.append(float(number))
    return float(xyz[0]), float(xyz[1]), float(xyz[2])


def solver_point_axis_policy(
    top_xyz: Any,
    bottom_xyz: Any,
    *,
    min_length_m: float = 1e-9,
) -> dict[str, Any]:
    top = _point3(top_xyz)
    bottom = _point3(bottom_xyz)
    if top is None or bottom is None:
        return {
            "axis_visible": False,
            "axis_reason": "missing_explicit_solver_point_pair",
        }
    dx = float(bottom[0] - top[0])
    dy = float(bottom[1] - top[1])
    dz = float(bottom[2] - top[2])
    length_m = math.sqrt(dx * dx + dy * dy + dz * dz)
    if not math.isfinite(length_m) or length_m <= float(min_length_m):
        return {
            "axis_visible": False,
            "axis_reason": "degenerate_explicit_solver_point_pair",
            "axis_length_m": float(length_m) if math.isfinite(length_m) else None,
        }
    return {
        "axis_visible": True,
        "axis_reason": "explicit_solver_point_pair",
        "axis_length_m": float(length_m),
    }


def _render_geometry_source(
    meta: Mapping[str, Any] | None,
    *,
    cyl_key: str,
    axle_key: str,
) -> tuple[dict[str, Any], str]:
    packaging = _as_mapping(_as_mapping(meta).get("packaging"))
    cyl_block = _as_mapping(_as_mapping(packaging.get("cylinders")).get(cyl_key))
    explicit_render_by_axle = _as_mapping(cyl_block.get("render_geometry_by_axle"))
    if explicit_render_by_axle:
        return _as_mapping(explicit_render_by_axle.get(axle_key)), "render_geometry_by_axle"
    resolved_by_axle = _as_mapping(cyl_block.get("resolved_geometry_by_axle"))
    return _as_mapping(resolved_by_axle.get(axle_key)), "resolved_geometry_by_axle"


def _complete_render_geometry(raw: Mapping[str, Any]) -> tuple[dict[str, float], list[str]]:
    out: dict[str, float] = {}
    missing: list[str] = []
    for field in REQUIRED_RENDER_GEOMETRY_FIELDS:
        value = _finite_float(_as_mapping(raw).get(field))
        if value is None:
            missing.append(field)
            continue
        if field in _POSITIVE_FIELDS and value <= 0.0:
            missing.append(field)
            continue
        if field not in _POSITIVE_FIELDS and value < 0.0:
            missing.append(field)
            continue
        out[field] = float(value)
    bore = out.get("bore_diameter_m")
    rod = out.get("rod_diameter_m")
    outer = out.get("outer_diameter_m")
    if bore is not None and rod is not None and rod >= bore:
        missing.append("rod_diameter_m")
    if bore is not None and outer is not None and outer < bore:
        missing.append("outer_diameter_m")
    return out, list(dict.fromkeys(missing))


def evaluate_cylinder_render_policy(
    *,
    meta: Mapping[str, Any] | None,
    cyl_name: str | int,
    axle: str,
    top_xyz: Any,
    bottom_xyz: Any,
    truth_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cyl_key = _normalize_cylinder_key(cyl_name)
    axle_key = _normalize_axle_key(axle)
    axis = solver_point_axis_policy(top_xyz, bottom_xyz)
    gate = _as_mapping(truth_gate)
    raw_geometry, source = _render_geometry_source(meta, cyl_key=cyl_key, axle_key=axle_key)
    render_geometry, missing = _complete_render_geometry(raw_geometry)
    gate_enabled = bool(gate.get("enabled")) and str(gate.get("mode") or "") == "body_rod_piston"
    body_enabled = bool(axis.get("axis_visible")) and bool(gate_enabled) and not missing

    if body_enabled:
        reason = "body_rod_piston_ready"
    elif not bool(axis.get("axis_visible")):
        reason = str(axis.get("axis_reason") or "missing_explicit_solver_point_pair")
    elif not gate_enabled:
        reason = str(gate.get("reason") or "truth_gate_disabled")
    else:
        reason = "missing_explicit_render_geometry"

    out: dict[str, Any] = {
        "cyl_name": cyl_key,
        "axle": axle_key,
        "axis_visible": bool(axis.get("axis_visible")),
        "axis_reason": str(axis.get("axis_reason") or ""),
        "body_enabled": bool(body_enabled),
        "body_mode": "body_rod_piston" if body_enabled else ("axis_only" if bool(axis.get("axis_visible")) else "unavailable"),
        "reason": reason,
        "missing_render_geometry_fields": list(missing),
        "hidden_elements": [] if body_enabled else list(CYLINDER_RENDER_HIDDEN_ELEMENTS),
        "render_geometry_source": source,
    }
    if "axis_length_m" in axis:
        out["axis_length_m"] = axis.get("axis_length_m")
    if body_enabled:
        out["render_geometry"] = dict(render_geometry)
    return out


__all__ = [
    "CYLINDER_RENDER_HIDDEN_ELEMENTS",
    "REQUIRED_RENDER_GEOMETRY_FIELDS",
    "evaluate_cylinder_render_policy",
    "solver_point_axis_policy",
]
