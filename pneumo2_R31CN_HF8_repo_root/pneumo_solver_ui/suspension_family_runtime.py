from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

try:
    from .suspension_family_contract import (
        FAMILY_ORDER,
        SPRING_STATIC_MODE_AUTO_MIDSTROKE,
        SPRING_STATIC_MODE_KEY,
        canonical_cylinder_slug,
        cylinder_axle_geometry_key,
        cylinder_generic_key,
        cylinder_family_key,
        cylinder_precharge_key,
        normalize_spring_static_mode,
        spring_family_key,
    )
except Exception:
    from suspension_family_contract import (
        FAMILY_ORDER,
        SPRING_STATIC_MODE_AUTO_MIDSTROKE,
        SPRING_STATIC_MODE_KEY,
        canonical_cylinder_slug,
        cylinder_axle_geometry_key,
        cylinder_generic_key,
        cylinder_family_key,
        cylinder_precharge_key,
        normalize_spring_static_mode,
        spring_family_key,
    )

CORNER_NAMES: tuple[str, str, str, str] = ("ЛП", "ПП", "ЛЗ", "ПЗ")
CORNER_AXLES: tuple[str, str, str, str] = ("перед", "перед", "зад", "зад")
CORNER_AXLE_BY_NAME: dict[str, str] = dict(zip(CORNER_NAMES, CORNER_AXLES))
SPRING_RUNTIME_METRICS: tuple[str, ...] = (
    "компрессия_м",
    "длина_м",
    "зазор_до_крышки_м",
    "запас_до_coil_bind_м",
    "длина_установленная_м",
)


def _finite_float(value: Any, default: float) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def _first_numeric(params: Mapping[str, Any], keys: list[str], default: float) -> float:
    for key in keys:
        if key not in params:
            continue
        value = _finite_float(params.get(key), float("nan"))
        if math.isfinite(value):
            return value
    return float(default)


def _expand_front_rear(front: float, rear: float) -> np.ndarray:
    return np.array([front, front, rear, rear], dtype=float)


def resolve_spring_static_mode(
    params: Mapping[str, Any],
    *,
    default: str = SPRING_STATIC_MODE_AUTO_MIDSTROKE,
) -> str:
    for key in (SPRING_STATIC_MODE_KEY, "spring_static_mode"):
        if key in params:
            return normalize_spring_static_mode(params.get(key))
    return normalize_spring_static_mode(default)


def _shared_cylinder_geometry_key(field: str, cyl: str) -> str | None:
    cyl_slug = canonical_cylinder_slug(cyl)
    mapping = {
        "dead_cap_length_m": f"{cyl_slug}_dead_cap_length_m",
        "dead_rod_length_m": f"{cyl_slug}_dead_rod_length_m",
        "dead_height_m": f"{cyl_slug}_dead_height_m",
        "body_length_m": f"{cyl_slug}_body_length_m",
        "outer_diameter_m": f"{cyl_slug}_outer_diameter_m",
    }
    return mapping.get(str(field).strip())


def _shared_cylinder_precharge_key(cyl: str, chamber: str) -> str:
    return f"{canonical_cylinder_slug(cyl)}_{str(chamber).strip().lower()}_precharge_pa"


def _first_abs_pressure(
    params: Mapping[str, Any],
    keys: list[str],
    *,
    default: float,
    p_atm_Pa: float,
) -> float:
    try:
        from .pneumo_gas_stiffness import p_abs_from_param as _p_abs_from_param
    except Exception:
        from pneumo_gas_stiffness import p_abs_from_param as _p_abs_from_param

    for key in keys:
        if key not in params:
            continue
        try:
            value = float(_p_abs_from_param(params.get(key), p_atm_Pa=float(p_atm_Pa)))
        except Exception:
            value = float("nan")
        if math.isfinite(value):
            return float(value)
    return float(default)


def _policy_cylinder_name(cyl: str) -> str:
    raw = str(cyl).strip().upper()
    if raw in {"Ц1", "C1"}:
        return "C1"
    if raw in {"Ц2", "C2"}:
        return "C2"
    return raw


def resolve_cylinder_precharge_axle_values(
    params: Mapping[str, Any],
    cyl: str,
    chamber: str,
    *,
    default: float = float("nan"),
    p_atm_Pa: float = 101325.0,
) -> np.ndarray:
    cyl = str(cyl).strip().upper()
    chamber = str(chamber).strip().upper()

    def _family_candidates(axle: str) -> list[str]:
        return [
            cylinder_precharge_key(cyl, chamber, axle),
            _shared_cylinder_precharge_key(cyl, chamber),
        ]

    front = _first_abs_pressure(
        params,
        _family_candidates("перед"),
        default=default,
        p_atm_Pa=p_atm_Pa,
    )
    rear = _first_abs_pressure(
        params,
        _family_candidates("зад"),
        default=default,
        p_atm_Pa=p_atm_Pa,
    )
    return _expand_front_rear(front, rear)


def resolve_cylinder_precharge_policy(
    params: Mapping[str, Any],
    *,
    p_atm_Pa: float = 101325.0,
) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = {}
    for cyl in ("Ц1", "Ц2"):
        cyl_policy: dict[str, dict[str, float]] = {}
        for chamber in ("CAP", "ROD"):
            values = resolve_cylinder_precharge_axle_values(
                params,
                cyl,
                chamber,
                default=float("nan"),
                p_atm_Pa=p_atm_Pa,
            )
            chamber_policy: dict[str, float] = {}
            if math.isfinite(float(values[0])):
                chamber_policy["front"] = float(values[0])
            if math.isfinite(float(values[2])):
                chamber_policy["rear"] = float(values[2])
            if chamber_policy:
                cyl_policy[chamber] = chamber_policy
        if cyl_policy:
            out[_policy_cylinder_name(cyl)] = cyl_policy
    return out


def normalize_spring_attachment_mode(value: Any, default: str = "c1") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"", "c1", "ц1", "coilover", "rod", "шток"}:
        return "c1"
    if raw in {"c2", "ц2", "rod2", "aux", "secondary", "secondary_rod", "шток2"}:
        return "c2"
    if raw in {"dual", "both", "c1+c2", "c1_c2", "parallel", "dual_family", "оба", "две"}:
        return "dual"
    if raw in {"delta", "legacy"}:
        return "delta"
    return str(default).strip().lower() or "c1"


def active_spring_family_cylinders(mode: Any, default: tuple[str, ...] = ("Ц1",)) -> tuple[str, ...]:
    normalized = normalize_spring_attachment_mode(mode, default="c1")
    if normalized == "c1":
        return ("Ц1",)
    if normalized == "c2":
        return ("Ц2",)
    if normalized == "dual":
        return ("Ц1", "Ц2")
    return tuple(default)


def active_spring_family_cylinder(mode: Any, default: str = "Ц1") -> str | None:
    normalized = normalize_spring_attachment_mode(mode, default="c1")
    if normalized == "c1":
        return "Ц1"
    if normalized == "c2":
        return "Ц2"
    return None


def spring_family_runtime_column(metric: str, cyl: str, corner: str) -> str:
    return f"пружина_{str(cyl).strip().upper()}_{str(corner).strip().upper()}_{str(metric).strip()}"


def spring_family_active_flag_column(cyl: str, corner: str) -> str:
    return f"пружина_{str(cyl).strip().upper()}_{str(corner).strip().upper()}_активна"


def spring_family_mode_id(normalized_mode: Any) -> int:
    mode = normalize_spring_attachment_mode(normalized_mode)
    if mode == "c1":
        return 1
    if mode == "c2":
        return 2
    if mode == "dual":
        return 3
    return 0


def spring_family_active_mask(cyl: str, spring_mode: Any) -> np.ndarray:
    active_cyls = {str(x).strip().upper() for x in active_spring_family_cylinders(spring_mode, default=())}
    active = 1.0 if str(cyl).strip().upper() in active_cyls else 0.0
    return np.full(4, active, dtype=float)


def split_dual_spring_force_target(
    target_vec: np.ndarray,
    capability_1: np.ndarray,
    capability_2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    target = np.maximum(0.0, np.asarray(target_vec, dtype=float))
    cap1 = np.maximum(0.0, np.asarray(capability_1, dtype=float))
    cap2 = np.maximum(0.0, np.asarray(capability_2, dtype=float))
    total = cap1 + cap2
    w1 = np.where(total > 1e-12, cap1 / np.maximum(1e-12, total), 0.5)
    w2 = np.where(total > 1e-12, cap2 / np.maximum(1e-12, total), 0.5)
    return target * w1, target * w2


def spring_family_runtime_series_template(n_steps: int) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for cyl, axle in FAMILY_ORDER:
        for corner in CORNER_NAMES:
            if CORNER_AXLE_BY_NAME.get(corner) != axle:
                continue
            out[spring_family_active_flag_column(cyl, corner)] = np.zeros(int(n_steps), dtype=float)
            out[spring_family_runtime_column("компрессия_м", cyl, corner)] = np.full(int(n_steps), np.nan, dtype=float)
            out[spring_family_runtime_column("длина_м", cyl, corner)] = np.full(int(n_steps), np.nan, dtype=float)
            out[spring_family_runtime_column("зазор_до_крышки_м", cyl, corner)] = np.full(int(n_steps), np.nan, dtype=float)
            out[spring_family_runtime_column("запас_до_coil_bind_м", cyl, corner)] = np.full(int(n_steps), np.nan, dtype=float)
            out[spring_family_runtime_column("длина_установленная_м", cyl, corner)] = np.full(int(n_steps), np.nan, dtype=float)
    return out


def build_spring_family_runtime_snapshot(
    *,
    spring_mode: Any,
    compression_m: np.ndarray | None = None,
    length_m: np.ndarray | None = None,
    gap_to_cap_m: np.ndarray | None = None,
    coil_bind_margin_m: np.ndarray | None = None,
    installed_length_m: np.ndarray | None = None,
    metrics_by_cyl: Mapping[str, Mapping[str, np.ndarray | None]] | None = None,
) -> dict[str, float]:
    out: dict[str, float] = {}
    normalized_mode = normalize_spring_attachment_mode(spring_mode)
    active_cyls = {str(x).strip().upper() for x in active_spring_family_cylinders(normalized_mode, default=())}
    if metrics_by_cyl is None:
        arrays: dict[str, np.ndarray | None] = {
            "компрессия_м": compression_m,
            "длина_м": length_m,
            "зазор_до_крышки_м": gap_to_cap_m,
            "запас_до_coil_bind_м": coil_bind_margin_m,
            "длина_установленная_м": installed_length_m,
        }
        family_arrays = {
            cyl: arrays
            for cyl in active_cyls
        }
    else:
        family_arrays = {
            str(cyl).strip().upper(): dict(metric_map or {})
            for cyl, metric_map in dict(metrics_by_cyl).items()
        }
    for cyl, axle in FAMILY_ORDER:
        cyl_key = str(cyl).strip().upper()
        arrays = dict(family_arrays.get(cyl_key) or {})
        active_flag = 1.0 if cyl_key in active_cyls else 0.0
        for corner_index, corner in enumerate(CORNER_NAMES):
            if CORNER_AXLE_BY_NAME.get(corner) != axle:
                continue
            out[spring_family_active_flag_column(cyl, corner)] = active_flag
            for metric in SPRING_RUNTIME_METRICS:
                arr = arrays.get(metric)
                value = float("nan")
                if arr is not None and active_flag > 0.5:
                    vec = np.asarray(arr, dtype=float).reshape(-1)
                    if corner_index < vec.size and np.isfinite(vec[corner_index]):
                        value = float(vec[corner_index])
                out[spring_family_runtime_column(metric, cyl, corner)] = value
    return out


def resolve_cylinder_corner_values(
    params: Mapping[str, Any],
    field: str,
    cyl: str,
    *,
    default: float,
) -> np.ndarray:
    cyl = str(cyl).strip().upper()
    if field == "bore":
        prefix = "диаметр_поршня"
        generic_default = _first_numeric(params, [cylinder_generic_key("bore", cyl)], default)
    elif field == "rod":
        prefix = "диаметр_штока"
        generic_default = _first_numeric(params, [cylinder_generic_key("rod", cyl)], default)
    elif field == "stroke":
        prefix = "ход_штока"
        generic_default = _first_numeric(params, ["ход_штока"], default)
    else:
        raise KeyError(field)

    def _family_candidates(axle: str) -> list[str]:
        if field == "stroke":
            return [
                cylinder_family_key("stroke", cyl, axle),
                f"{prefix}_{cyl}_{axle}",
                f"ход_{cyl}_{axle}_м",
                f"ход_{cyl}_{axle}",
            ]
        return [
            cylinder_family_key(field, cyl, axle),
            f"{prefix}_{cyl}_{axle}",
        ]

    front = _first_numeric(params, _family_candidates("перед"), generic_default)
    rear = _first_numeric(params, _family_candidates("зад"), generic_default)
    return _expand_front_rear(front, rear)


def resolve_cylinder_axle_geometry_values(
    params: Mapping[str, Any],
    field: str,
    cyl: str,
    *,
    default: float,
) -> np.ndarray:
    cyl = str(cyl).strip().upper()

    def _family_candidates(axle: str) -> list[str]:
        keys = [cylinder_axle_geometry_key(field, cyl, axle)]
        shared_key = _shared_cylinder_geometry_key(field, cyl)
        if shared_key:
            keys.append(shared_key)
        return keys

    front = _first_numeric(params, _family_candidates("перед"), default)
    rear = _first_numeric(params, _family_candidates("зад"), default)
    return _expand_front_rear(front, rear)


def resolve_cylinder_corner_geometry(
    params: Mapping[str, Any],
    cyl: str,
    *,
    default_bore: float,
    default_rod: float,
    default_stroke: float,
    default_dead_volume_m3: float = 0.0,
) -> dict[str, np.ndarray]:
    bore_m = resolve_cylinder_corner_values(params, "bore", cyl, default=default_bore)
    rod_m = resolve_cylinder_corner_values(params, "rod", cyl, default=default_rod)
    stroke_m = resolve_cylinder_corner_values(params, "stroke", cyl, default=default_stroke)
    cap_area_m2 = math.pi * (bore_m * 0.5) ** 2
    rod_area_m2 = np.maximum(1e-12, cap_area_m2 - math.pi * (rod_m * 0.5) ** 2)
    dead_cap_length_m = resolve_cylinder_axle_geometry_values(
        params,
        "dead_cap_length_m",
        cyl,
        default=float("nan"),
    )
    dead_rod_length_m = resolve_cylinder_axle_geometry_values(
        params,
        "dead_rod_length_m",
        cyl,
        default=float("nan"),
    )
    dead_height_raw_m = resolve_cylinder_axle_geometry_values(
        params,
        "dead_height_m",
        cyl,
        default=float("nan"),
    )
    body_length_m = resolve_cylinder_axle_geometry_values(
        params,
        "body_length_m",
        cyl,
        default=float("nan"),
    )

    shared_dead_volume_m3 = float(
        max(
            0.0,
            _first_numeric(
                params,
                ["dead_volume_chamber_m3", "corner_pneumo_dead_volume_m3", "мёртвый_объём_камеры"],
                default_dead_volume_m3,
            ),
        )
    )
    shared_dead_cap_length_m = np.where(
        cap_area_m2 > 1e-12,
        shared_dead_volume_m3 / np.maximum(cap_area_m2, 1e-12),
        0.0,
    )
    shared_dead_rod_length_m = np.where(
        rod_area_m2 > 1e-12,
        shared_dead_volume_m3 / np.maximum(rod_area_m2, 1e-12),
        0.0,
    )
    dead_height_from_volume_m = np.where(
        cap_area_m2 > 1e-12,
        shared_dead_volume_m3 / np.maximum(cap_area_m2, 1e-12),
        0.0,
    )
    dead_height_m = np.where(np.isfinite(dead_height_raw_m), dead_height_raw_m, dead_height_from_volume_m)
    dead_cap_length_m = np.where(
        np.isfinite(dead_cap_length_m),
        dead_cap_length_m,
        np.where(np.isfinite(dead_height_raw_m), dead_height_raw_m, shared_dead_cap_length_m),
    )
    dead_rod_length_m = np.where(
        np.isfinite(dead_rod_length_m),
        dead_rod_length_m,
        np.where(np.isfinite(dead_height_raw_m), dead_height_raw_m, shared_dead_rod_length_m),
    )
    dead_cap_length_m = np.maximum(0.0, np.where(np.isfinite(dead_cap_length_m), dead_cap_length_m, 0.0))
    dead_rod_length_m = np.maximum(0.0, np.where(np.isfinite(dead_rod_length_m), dead_rod_length_m, 0.0))
    dead_height_m = np.maximum(0.0, np.where(np.isfinite(dead_height_m), dead_height_m, 0.0))

    body_length_fallback_m = stroke_m + dead_cap_length_m + dead_rod_length_m
    body_length_m = np.where(np.isfinite(body_length_m), body_length_m, body_length_fallback_m)
    body_length_m = np.maximum(0.0, np.where(np.isfinite(body_length_m), body_length_m, 0.0))

    dead_cap_volume_m3 = np.maximum(0.0, cap_area_m2 * dead_cap_length_m)
    dead_rod_volume_m3 = np.maximum(0.0, rod_area_m2 * dead_rod_length_m)
    return {
        "bore_m": bore_m.astype(float),
        "rod_m": rod_m.astype(float),
        "stroke_m": stroke_m.astype(float),
        "cap_area_m2": cap_area_m2.astype(float),
        "rod_area_m2": rod_area_m2.astype(float),
        "dead_cap_length_m": dead_cap_length_m.astype(float),
        "dead_rod_length_m": dead_rod_length_m.astype(float),
        "dead_height_m": dead_height_m.astype(float),
        "body_length_m": body_length_m.astype(float),
        "dead_cap_volume_m3": dead_cap_volume_m3.astype(float),
        "dead_rod_volume_m3": dead_rod_volume_m3.astype(float),
    }


def resolve_spring_corner_values(
    params: Mapping[str, Any],
    suffix: str,
    *,
    spring_mode: Any = "c1",
    default: float,
) -> np.ndarray:
    generic_key = f"пружина_{str(suffix).strip()}"
    generic_default = _first_numeric(params, [generic_key], default)
    cyl = active_spring_family_cylinder(spring_mode)
    if cyl is None:
        return np.full(4, generic_default, dtype=float)
    front = _first_numeric(params, [spring_family_key(suffix, cyl, "перед")], generic_default)
    rear = _first_numeric(params, [spring_family_key(suffix, cyl, "зад")], generic_default)
    return _expand_front_rear(front, rear)


def resolve_spring_corner_geometry(
    params: Mapping[str, Any],
    *,
    spring_mode: Any = "c1",
    default_scale: float = 1.0,
    default_free_length: float = 0.30,
    default_solid_length: float = 0.0,
    default_top_offset: float = 0.02,
    default_rebound_preload_min: float = 0.0,
    default_coil_bind_margin_min: float = 0.0,
) -> dict[str, Any]:
    normalized_mode = normalize_spring_attachment_mode(spring_mode)
    static_mode = resolve_spring_static_mode(params)
    scale = resolve_spring_corner_values(
        params,
        "масштаб",
        spring_mode=normalized_mode,
        default=default_scale,
    )
    free_length = np.maximum(
        0.0,
        resolve_spring_corner_values(
            params,
            "длина_свободная_м",
            spring_mode=normalized_mode,
            default=default_free_length,
        ),
    )
    solid_length_raw = resolve_spring_corner_values(
        params,
        "длина_солид_м",
        spring_mode=normalized_mode,
        default=default_solid_length,
    )
    solid_length = np.where(
        np.isfinite(solid_length_raw) & (solid_length_raw > 0.0),
        solid_length_raw,
        np.nan,
    )
    top_offset = np.maximum(
        0.0,
        resolve_spring_corner_values(
            params,
            "верхний_отступ_от_крышки_м",
            spring_mode=normalized_mode,
            default=default_top_offset,
        ),
    )
    rebound_preload_min = np.maximum(
        0.0,
        resolve_spring_corner_values(
            params,
            "преднатяг_на_отбое_минимум_м",
            spring_mode=normalized_mode,
            default=default_rebound_preload_min,
        ),
    )
    coil_bind_margin_min = np.maximum(
        0.0,
        resolve_spring_corner_values(
            params,
            "запас_до_coil_bind_минимум_м",
            spring_mode=normalized_mode,
            default=default_coil_bind_margin_min,
        ),
    )
    return {
        "mode": normalized_mode,
        "static_mode": static_mode,
        "family_cyl": active_spring_family_cylinder(normalized_mode),
        "scale": scale.astype(float),
        "free_length_m": free_length.astype(float),
        "solid_length_m": solid_length.astype(float),
        "top_offset_m": top_offset.astype(float),
        "rebound_preload_min_m": rebound_preload_min.astype(float),
        "coil_bind_margin_min_m": coil_bind_margin_min.astype(float),
    }


__all__ = [
    "CORNER_AXLE_BY_NAME",
    "CORNER_NAMES",
    "CORNER_AXLES",
    "active_spring_family_cylinder",
    "active_spring_family_cylinders",
    "build_spring_family_runtime_snapshot",
    "spring_family_active_flag_column",
    "spring_family_mode_id",
    "spring_family_runtime_column",
    "spring_family_runtime_series_template",
    "normalize_spring_attachment_mode",
    "resolve_spring_static_mode",
    "resolve_cylinder_corner_geometry",
    "resolve_cylinder_corner_values",
    "resolve_cylinder_precharge_axle_values",
    "resolve_cylinder_precharge_policy",
    "resolve_spring_corner_geometry",
    "resolve_spring_corner_values",
    "split_dual_spring_force_target",
]
