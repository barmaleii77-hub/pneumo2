from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from pneumo_solver_ui.desktop_input_model import (
    DESKTOP_INPUT_SECTIONS,
    desktop_field_search_display_name,
    field_spec_map,
    find_desktop_field_matches,
)
from pneumo_solver_ui.dw2d_kinematics import (
    build_dw2d_mounts_params_from_base,
    dw2d_mounts_delta_rod_and_drod,
)
from pneumo_solver_ui.spring_table import (
    SpringGeometryReference,
    build_spring_geometry_reference,
)
from pneumo_solver_ui.suspension_family_contract import (
    CYLINDER_AXLE_GEOMETRY_FIELDS,
    CYLINDER_PRECHARGE_CHAMBERS,
    FAMILY_ORDER,
    SPRING_GEOMETRY_FIELDS,
    SPRING_STATIC_MODE_KEY,
    cylinder_axle_geometry_key,
    cylinder_family_key,
    cylinder_precharge_key,
    family_name,
    family_param_meta,
    normalize_component_family_contract,
    spring_geometry_key,
    spring_family_key,
)


CATALOG_JSON = Path(__file__).resolve().parent / "catalogs" / "camozzi_catalog.json"
REFERENCE_GUIDE_SECTION_TITLES: tuple[str, ...] = (
    "Геометрия",
    "Пневматика",
    "Компоненты",
    "Справочные данные",
)
ATM_PA = 101325.0


@dataclass(frozen=True)
class GeometryFamilyReferenceRow:
    family: str
    stroke_mm: float
    rod_rebound_mm: float
    rod_static_mm: float
    rod_bump_mm: float
    motion_ratio_mid: float
    motion_ratio_peak: float
    stroke_usage_pct: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class GeometryReferenceSnapshot:
    base_path: Path
    wheelbase_mm: float
    track_mm: float
    mechanics_mode: str
    wheel_coord_mode: str
    dw_min_mm: float
    dw_max_mm: float
    families: tuple[GeometryFamilyReferenceRow, ...]


@dataclass(frozen=True)
class CylinderCatalogRow:
    variant_key: str
    variant_label: str
    bore_mm: int
    rod_mm: int
    port_thread: str
    rod_thread: str
    B_mm: float
    E_mm: float
    TG_mm: float
    cap_area_m2: float
    annulus_area_m2: float
    cap_area_cm2: float
    annulus_area_cm2: float


@dataclass(frozen=True)
class CylinderFamilyReferenceRow:
    family: str
    bore_mm: float
    rod_mm: float
    stroke_mm: float
    cap_area_cm2: float
    annulus_area_cm2: float


@dataclass(frozen=True)
class CylinderPressureEstimate:
    pressure_bar_gauge: float
    cap_force_N: float
    rod_force_N: float
    cap_force_kgf: float
    rod_force_kgf: float


@dataclass(frozen=True)
class CylinderForceBiasEstimate:
    cap_pressure_bar_gauge: float
    rod_pressure_bar_gauge: float
    cap_force_N: float
    rod_force_N: float
    net_force_N: float
    net_force_kgf: float
    bias_direction: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class CylinderPrechargeReferenceRow:
    family: str
    cap_precharge_abs_kpa: float
    rod_precharge_abs_kpa: float
    cap_precharge_bar_g: float
    rod_precharge_bar_g: float
    cap_force_N: float
    rod_force_N: float
    net_force_N: float
    net_force_kgf: float
    bias_direction: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class CylinderPackageReferenceRow:
    family: str
    outer_diameter_mm: float
    dead_cap_length_mm: float
    dead_rod_length_mm: float
    dead_height_mm: float
    body_length_mm: float
    expected_body_length_mm: float
    body_length_gap_mm: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class CylinderMatchRecommendation:
    family: str
    variant_key: str
    variant_label: str
    bore_mm: int
    rod_mm: int
    recommended_stroke_mm: float
    bore_delta_mm: float
    rod_delta_mm: float
    stroke_delta_mm: float
    net_force_N: float
    net_force_delta_N: float
    bias_direction: str
    score: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ComponentFitReferenceRow:
    family: str
    status: str
    stroke_usage_pct: float
    motion_ratio_peak: float
    current_stroke_mm: float
    cylinder_outer_diameter_mm: float
    spring_inner_diameter_mm: float
    spring_outer_diameter_mm: float
    spring_to_cylinder_clearance_mm: float
    recommended_catalog_label: str
    recommended_stroke_mm: float
    current_net_force_N: float
    recommended_net_force_N: float
    recommended_net_force_delta_N: float
    recommended_bias_direction: str
    spring_bind_margin_mm: float
    spring_bind_target_mm: float
    action_summary: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class SpringFamilyReferenceRow:
    family: str
    wire_mm: float
    mean_diameter_mm: float
    inner_diameter_mm: float
    outer_diameter_mm: float
    active_turns: float
    total_turns: float
    pitch_mm: float
    shear_modulus_GPa: float
    rate_N_per_mm: float
    free_length_mm: float
    solid_length_mm: float
    free_length_from_pitch_mm: float
    free_length_pitch_gap_mm: float
    top_offset_mm: float
    rebound_preload_min_mm: float
    bind_travel_margin_mm: float
    bind_margin_target_mm: float


@dataclass(frozen=True)
class SpringReferenceSnapshot:
    static_mode: str
    families: tuple[SpringFamilyReferenceRow, ...]


@dataclass(frozen=True)
class ParameterGuideRow:
    key: str
    label: str
    unit_label: str
    section_title: str
    description: str
    display: str
    current_value_text: str


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _meters_to_mm(value_m: float) -> float:
    return float(value_m) * 1000.0


def _area_to_cm2(value_m2: float) -> float:
    return float(value_m2) * 1.0e4


def _format_current_value(value: Any, *, unit_label: str = "", digits: int = 3) -> str:
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if value is None:
        return "—"
    try:
        out = float(value)
    except Exception:
        text = str(value).strip()
        return text or "—"
    if not math.isfinite(out):
        return "—"
    return f"{out:.{digits}f}" + (f" {unit_label}" if unit_label else "")


def _format_family_current_value(value: Any, meta: Mapping[str, Any]) -> str:
    unit_label = str(meta.get("ед") or "").strip()
    kind = str(meta.get("kind") or "").strip()
    try:
        numeric = float(value)
    except Exception:
        text = str(value).strip()
        return text or "—"
    if not math.isfinite(numeric):
        return "—"
    if kind == "length_mm":
        return f"{numeric * 1000.0:.1f} {unit_label}".strip()
    if kind == "pressure_kPa_abs":
        return f"{numeric * 0.001:.1f} {unit_label}".strip()
    if kind == "raw":
        return str(value)
    if abs(numeric) >= 100.0:
        return f"{numeric:.1f}" + (f" {unit_label}" if unit_label else "")
    return f"{numeric:.3f}" + (f" {unit_label}" if unit_label else "")


def _cylinder_variant_label(key: str) -> str:
    lowered = str(key or "").strip().lower()
    if "round" in lowered:
        return "Round tube (tie-rod)"
    if "profile" in lowered:
        return "Profile"
    return str(key or "")


def _catalog_area_bundle(bore_mm: float, rod_mm: float) -> tuple[float, float, float, float]:
    bore_m = float(bore_mm) / 1000.0
    rod_m = float(rod_mm) / 1000.0
    cap_area_m2 = math.pi * (bore_m ** 2) / 4.0
    rod_area_m2 = math.pi * (rod_m ** 2) / 4.0
    annulus_area_m2 = max(cap_area_m2 - rod_area_m2, 0.0)
    return cap_area_m2, annulus_area_m2, _area_to_cm2(cap_area_m2), _area_to_cm2(annulus_area_m2)


@lru_cache(maxsize=1)
def load_camozzi_catalog_rows() -> tuple[CylinderCatalogRow, ...]:
    if not CATALOG_JSON.exists():
        return ()
    raw = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    cylinders = dict((raw or {}).get("cylinders") or {})
    variants = dict(cylinders.get("variants") or {})
    rows: list[CylinderCatalogRow] = []
    for variant_key, payload in sorted(variants.items()):
        for item in payload.get("items", []) or []:
            bore_mm = int(item.get("bore_mm", 0) or 0)
            rod_mm = int(item.get("rod_mm", 0) or 0)
            cap_area_m2, annulus_area_m2, cap_area_cm2, annulus_area_cm2 = _catalog_area_bundle(
                bore_mm,
                rod_mm,
            )
            rows.append(
                CylinderCatalogRow(
                    variant_key=str(variant_key),
                    variant_label=_cylinder_variant_label(str(variant_key)),
                    bore_mm=bore_mm,
                    rod_mm=rod_mm,
                    port_thread=str(item.get("port_thread", "") or ""),
                    rod_thread=str(item.get("rod_thread", "") or ""),
                    B_mm=_safe_float(item.get("B_mm")),
                    E_mm=_safe_float(item.get("E_mm")),
                    TG_mm=_safe_float(item.get("TG_mm")),
                    cap_area_m2=cap_area_m2,
                    annulus_area_m2=annulus_area_m2,
                    cap_area_cm2=cap_area_cm2,
                    annulus_area_cm2=annulus_area_cm2,
                )
            )
    return tuple(rows)


@lru_cache(maxsize=1)
def load_camozzi_stroke_options_mm() -> tuple[int, ...]:
    if not CATALOG_JSON.exists():
        return ()
    raw = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    cylinders = dict((raw or {}).get("cylinders") or {})
    options = cylinders.get("stroke_options_mm") or ()
    cleaned = sorted({int(option) for option in options if _safe_float(option, default=float("nan")) > 0.0})
    return tuple(cleaned)


def build_cylinder_pressure_estimate(
    row: CylinderCatalogRow | CylinderFamilyReferenceRow,
    pressure_bar_gauge: float,
    *,
    clamp_negative: bool = True,
) -> CylinderPressureEstimate:
    gauge_bar = float(pressure_bar_gauge)
    if clamp_negative:
        gauge_bar = max(0.0, gauge_bar)
    pressure_pa = gauge_bar * 1.0e5
    cap_area_m2 = (
        float(row.cap_area_m2)
        if isinstance(row, CylinderCatalogRow)
        else (math.pi * (float(row.bore_mm) / 1000.0) ** 2 / 4.0)
    )
    annulus_area_m2 = (
        float(row.annulus_area_m2)
        if isinstance(row, CylinderCatalogRow)
        else max(cap_area_m2 - math.pi * (float(row.rod_mm) / 1000.0) ** 2 / 4.0, 0.0)
    )
    cap_force_N = pressure_pa * cap_area_m2
    rod_force_N = pressure_pa * annulus_area_m2
    return CylinderPressureEstimate(
        pressure_bar_gauge=float(gauge_bar),
        cap_force_N=float(cap_force_N),
        rod_force_N=float(rod_force_N),
        cap_force_kgf=float(cap_force_N / 9.80665),
        rod_force_kgf=float(rod_force_N / 9.80665),
    )


def build_cylinder_force_bias_estimate(
    row: CylinderCatalogRow | CylinderFamilyReferenceRow,
    *,
    cap_pressure_bar_gauge: float,
    rod_pressure_bar_gauge: float,
    clamp_negative: bool = True,
) -> CylinderForceBiasEstimate:
    cap_estimate = (
        build_cylinder_pressure_estimate(
            row,
            cap_pressure_bar_gauge,
            clamp_negative=clamp_negative,
        )
        if math.isfinite(cap_pressure_bar_gauge)
        else None
    )
    rod_estimate = (
        build_cylinder_pressure_estimate(
            row,
            rod_pressure_bar_gauge,
            clamp_negative=clamp_negative,
        )
        if math.isfinite(rod_pressure_bar_gauge)
        else None
    )
    cap_force_N = float(cap_estimate.cap_force_N) if cap_estimate is not None else float("nan")
    rod_force_N = float(rod_estimate.rod_force_N) if rod_estimate is not None else float("nan")
    net_force_N = (
        cap_force_N - rod_force_N
        if math.isfinite(cap_force_N) and math.isfinite(rod_force_N)
        else float("nan")
    )

    notes: list[str] = []
    if math.isfinite(cap_pressure_bar_gauge) and cap_pressure_bar_gauge < 0.0:
        notes.append("CAP ниже атмосферы")
    if math.isfinite(rod_pressure_bar_gauge) and rod_pressure_bar_gauge < 0.0:
        notes.append("ROD ниже атмосферы")

    bias_direction = "нет данных"
    if math.isfinite(net_force_N):
        if abs(net_force_N) < 1.0:
            bias_direction = "neutral"
            notes.append("силы почти сбалансированы")
        elif net_force_N > 0.0:
            bias_direction = "extend"
            notes.append("bias на выдвижение")
        else:
            bias_direction = "retract"
            notes.append("bias на втягивание")

    return CylinderForceBiasEstimate(
        cap_pressure_bar_gauge=float(cap_pressure_bar_gauge),
        rod_pressure_bar_gauge=float(rod_pressure_bar_gauge),
        cap_force_N=float(cap_force_N),
        rod_force_N=float(rod_force_N),
        net_force_N=float(net_force_N),
        net_force_kgf=float(net_force_N / 9.80665) if math.isfinite(net_force_N) else float("nan"),
        bias_direction=bias_direction,
        notes=tuple(notes),
    )


def build_geometry_reference_snapshot(
    base_payload: Mapping[str, Any],
    *,
    base_path: Path,
    dw_min_mm: float = -100.0,
    dw_max_mm: float = 100.0,
    sample_count: int = 81,
) -> GeometryReferenceSnapshot:
    normalized_base, _normalized_ranges, _meta = normalize_component_family_contract(base_payload, {})
    dw_start_mm = float(min(dw_min_mm, dw_max_mm))
    dw_stop_mm = float(max(dw_min_mm, dw_max_mm))
    samples = max(5, int(sample_count))
    dw_samples_m = np.linspace(dw_start_mm / 1000.0, dw_stop_mm / 1000.0, samples)
    zero_idx = int(np.argmin(np.abs(dw_samples_m)))
    families: list[GeometryFamilyReferenceRow] = []
    for cyl, axle in FAMILY_ORDER:
        cyl_code = "C1" if cyl == "Ц1" else "C2"
        delta_rod_m, motion_ratio, _aux = dw2d_mounts_delta_rod_and_drod(
            dw_samples_m,
            build_dw2d_mounts_params_from_base(normalized_base, cyl=cyl_code, axle=axle),
            sign_lr=+1.0,
        )
        stroke_m = _safe_float(normalized_base.get(cylinder_family_key("stroke", cyl, axle)), default=0.0)
        stroke_usage_pct = (
            float(np.nanmax(np.abs(delta_rod_m))) / stroke_m * 100.0
            if stroke_m > 0.0
            else float("nan")
        )
        notes: list[str] = []
        if not math.isfinite(stroke_usage_pct):
            notes.append("stroke не задан")
        elif stroke_usage_pct > 100.0:
            notes.append("ход штока превышен")
        elif stroke_usage_pct > 80.0:
            notes.append("высокое использование хода")
        families.append(
            GeometryFamilyReferenceRow(
                family=family_name(cyl, axle),
                stroke_mm=_meters_to_mm(stroke_m),
                rod_rebound_mm=_meters_to_mm(float(delta_rod_m[0])),
                rod_static_mm=_meters_to_mm(float(delta_rod_m[zero_idx])),
                rod_bump_mm=_meters_to_mm(float(delta_rod_m[-1])),
                motion_ratio_mid=float(motion_ratio[zero_idx]),
                motion_ratio_peak=float(np.nanmax(np.abs(motion_ratio))),
                stroke_usage_pct=float(stroke_usage_pct),
                notes=tuple(notes),
            )
        )
    return GeometryReferenceSnapshot(
        base_path=Path(base_path).resolve(),
        wheelbase_mm=_meters_to_mm(_safe_float(normalized_base.get("база"), default=0.0)),
        track_mm=_meters_to_mm(_safe_float(normalized_base.get("колея"), default=0.0)),
        mechanics_mode=str(normalized_base.get("механика_кинематика", "") or ""),
        wheel_coord_mode=str(normalized_base.get("колесо_координата", "") or ""),
        dw_min_mm=float(dw_start_mm),
        dw_max_mm=float(dw_stop_mm),
        families=tuple(families),
    )


def build_current_cylinder_reference_rows(
    base_payload: Mapping[str, Any],
) -> tuple[CylinderFamilyReferenceRow, ...]:
    normalized_base, _normalized_ranges, _meta = normalize_component_family_contract(base_payload, {})
    rows: list[CylinderFamilyReferenceRow] = []
    for cyl, axle in FAMILY_ORDER:
        bore_m = _safe_float(normalized_base.get(cylinder_family_key("bore", cyl, axle)), default=0.0)
        rod_m = _safe_float(normalized_base.get(cylinder_family_key("rod", cyl, axle)), default=0.0)
        stroke_m = _safe_float(normalized_base.get(cylinder_family_key("stroke", cyl, axle)), default=0.0)
        cap_area_m2 = math.pi * max(bore_m, 0.0) ** 2 / 4.0
        annulus_area_m2 = max(cap_area_m2 - math.pi * max(rod_m, 0.0) ** 2 / 4.0, 0.0)
        rows.append(
            CylinderFamilyReferenceRow(
                family=family_name(cyl, axle),
                bore_mm=_meters_to_mm(bore_m),
                rod_mm=_meters_to_mm(rod_m),
                stroke_mm=_meters_to_mm(stroke_m),
                cap_area_cm2=_area_to_cm2(cap_area_m2),
                annulus_area_cm2=_area_to_cm2(annulus_area_m2),
            )
        )
    return tuple(rows)


def build_current_cylinder_precharge_rows(
    base_payload: Mapping[str, Any],
    *,
    atmospheric_pressure_pa: float = ATM_PA,
) -> tuple[CylinderPrechargeReferenceRow, ...]:
    normalized_base, _normalized_ranges, _meta = normalize_component_family_contract(base_payload, {})
    cylinder_rows = {row.family: row for row in build_current_cylinder_reference_rows(normalized_base)}
    p_atm = float(atmospheric_pressure_pa)
    rows: list[CylinderPrechargeReferenceRow] = []
    for cyl, axle in FAMILY_ORDER:
        family = family_name(cyl, axle)
        cylinder = cylinder_rows.get(family)
        cap_abs_pa = _safe_float(
            normalized_base.get(cylinder_precharge_key(cyl, "CAP", axle)),
            default=float("nan"),
        )
        rod_abs_pa = _safe_float(
            normalized_base.get(cylinder_precharge_key(cyl, "ROD", axle)),
            default=float("nan"),
        )
        cap_bar_g = (
            (cap_abs_pa - p_atm) / 1.0e5
            if math.isfinite(cap_abs_pa)
            else float("nan")
        )
        rod_bar_g = (
            (rod_abs_pa - p_atm) / 1.0e5
            if math.isfinite(rod_abs_pa)
            else float("nan")
        )
        force_bias = (
            build_cylinder_force_bias_estimate(
                cylinder,
                cap_pressure_bar_gauge=cap_bar_g,
                rod_pressure_bar_gauge=rod_bar_g,
                clamp_negative=False,
            )
            if cylinder is not None
            else None
        )

        notes: list[str] = []
        if not math.isfinite(cap_abs_pa):
            notes.append("нет CAP precharge")
        if not math.isfinite(rod_abs_pa):
            notes.append("нет ROD precharge")
        if cylinder is None:
            notes.append("нет cylinder bore/rod")
        if force_bias is not None:
            notes.extend(force_bias.notes)

        rows.append(
            CylinderPrechargeReferenceRow(
                family=family,
                cap_precharge_abs_kpa=cap_abs_pa * 1.0e-3 if math.isfinite(cap_abs_pa) else float("nan"),
                rod_precharge_abs_kpa=rod_abs_pa * 1.0e-3 if math.isfinite(rod_abs_pa) else float("nan"),
                cap_precharge_bar_g=cap_bar_g,
                rod_precharge_bar_g=rod_bar_g,
                cap_force_N=float(force_bias.cap_force_N) if force_bias is not None else float("nan"),
                rod_force_N=float(force_bias.rod_force_N) if force_bias is not None else float("nan"),
                net_force_N=float(force_bias.net_force_N) if force_bias is not None else float("nan"),
                net_force_kgf=float(force_bias.net_force_kgf) if force_bias is not None else float("nan"),
                bias_direction=str(force_bias.bias_direction) if force_bias is not None else "нет данных",
                notes=tuple(notes),
            )
        )
    return tuple(rows)


def build_current_cylinder_package_rows(
    base_payload: Mapping[str, Any],
) -> tuple[CylinderPackageReferenceRow, ...]:
    normalized_base, _normalized_ranges, _meta = normalize_component_family_contract(base_payload, {})
    cylinder_rows = {row.family: row for row in build_current_cylinder_reference_rows(normalized_base)}
    rows: list[CylinderPackageReferenceRow] = []
    for cyl, axle in FAMILY_ORDER:
        family = family_name(cyl, axle)
        cylinder = cylinder_rows.get(family)
        outer_diameter_m = _safe_float(
            normalized_base.get(cylinder_axle_geometry_key("outer_diameter_m", cyl, axle)),
            default=float("nan"),
        )
        if not math.isfinite(outer_diameter_m) or outer_diameter_m <= 0.0:
            outer_diameter_m = _safe_float(
                normalized_base.get(cylinder_family_key("bore", cyl, axle)),
                default=float("nan"),
            )
        dead_cap_length_m = _safe_float(
            normalized_base.get(cylinder_axle_geometry_key("dead_cap_length_m", cyl, axle)),
            default=float("nan"),
        )
        dead_rod_length_m = _safe_float(
            normalized_base.get(cylinder_axle_geometry_key("dead_rod_length_m", cyl, axle)),
            default=float("nan"),
        )
        dead_height_m = _safe_float(
            normalized_base.get(cylinder_axle_geometry_key("dead_height_m", cyl, axle)),
            default=float("nan"),
        )
        reported_body_length_m = _safe_float(
            normalized_base.get(cylinder_axle_geometry_key("body_length_m", cyl, axle)),
            default=float("nan"),
        )
        stroke_m = (float(cylinder.stroke_mm) / 1000.0) if cylinder is not None else float("nan")
        expected_body_length_m = (
            stroke_m + dead_cap_length_m + dead_rod_length_m
            if (
                math.isfinite(stroke_m)
                and math.isfinite(dead_cap_length_m)
                and math.isfinite(dead_rod_length_m)
            )
            else float("nan")
        )
        body_length_m = (
            reported_body_length_m
            if math.isfinite(reported_body_length_m) and reported_body_length_m > 0.0
            else expected_body_length_m
        )
        body_length_gap_mm = (
            _meters_to_mm(body_length_m - expected_body_length_m)
            if math.isfinite(body_length_m) and math.isfinite(expected_body_length_m)
            else float("nan")
        )

        notes: list[str] = []
        if not math.isfinite(reported_body_length_m) and math.isfinite(expected_body_length_m):
            notes.append("body derived from stroke+dead")
        if not math.isfinite(dead_cap_length_m) or not math.isfinite(dead_rod_length_m):
            notes.append("неполный dead-length contract")
        if math.isfinite(body_length_gap_mm):
            if body_length_gap_mm < -0.5:
                notes.append("body меньше stroke+dead")
            elif body_length_gap_mm > 5.0:
                notes.append("body с запасом к stroke+dead")
            else:
                notes.append("body ~= stroke+dead")

        rows.append(
            CylinderPackageReferenceRow(
                family=family,
                outer_diameter_mm=_meters_to_mm(outer_diameter_m),
                dead_cap_length_mm=_meters_to_mm(dead_cap_length_m),
                dead_rod_length_mm=_meters_to_mm(dead_rod_length_m),
                dead_height_mm=_meters_to_mm(dead_height_m),
                body_length_mm=_meters_to_mm(body_length_m),
                expected_body_length_mm=_meters_to_mm(expected_body_length_m),
                body_length_gap_mm=body_length_gap_mm,
                notes=tuple(notes),
            )
        )
    return tuple(rows)


def build_current_cylinder_outer_diameter_rows(
    base_payload: Mapping[str, Any],
) -> dict[str, float]:
    normalized_base, _normalized_ranges, _meta = normalize_component_family_contract(base_payload, {})
    rows: dict[str, float] = {}
    for cyl, axle in FAMILY_ORDER:
        outer_diameter_m = _safe_float(
            normalized_base.get(cylinder_axle_geometry_key("outer_diameter_m", cyl, axle)),
            default=float("nan"),
        )
        if not math.isfinite(outer_diameter_m) or outer_diameter_m <= 0.0:
            # Conservative degraded fallback: real outer diameter cannot be smaller than bore.
            outer_diameter_m = _safe_float(
                normalized_base.get(cylinder_family_key("bore", cyl, axle)),
                default=float("nan"),
            )
        rows[family_name(cyl, axle)] = _meters_to_mm(outer_diameter_m)
    return rows


def _recommended_stroke_option_mm(
    target_stroke_mm: float,
    stroke_options_mm: tuple[int, ...],
) -> float:
    if not stroke_options_mm:
        return float("nan")
    valid = tuple(float(option) for option in stroke_options_mm if float(option) > 0.0)
    if not valid:
        return float("nan")
    target = max(0.0, float(target_stroke_mm))
    acceptable = [option for option in valid if option >= target]
    if acceptable:
        return float(min(acceptable))
    return float(max(valid))


def build_cylinder_match_recommendations(
    current_row: CylinderFamilyReferenceRow,
    catalog_rows: tuple[CylinderCatalogRow, ...],
    *,
    current_precharge: CylinderPrechargeReferenceRow | None = None,
    stroke_options_mm: tuple[int, ...] | None = None,
    limit: int = 5,
) -> tuple[CylinderMatchRecommendation, ...]:
    stroke_options = tuple(stroke_options_mm or load_camozzi_stroke_options_mm())
    recommendations: list[CylinderMatchRecommendation] = []
    target_bore = float(current_row.bore_mm)
    target_rod = float(current_row.rod_mm)
    target_stroke = float(current_row.stroke_mm)
    for row in catalog_rows:
        recommended_stroke_mm = _recommended_stroke_option_mm(target_stroke, stroke_options)
        bore_delta_mm = float(row.bore_mm) - target_bore
        rod_delta_mm = float(row.rod_mm) - target_rod
        stroke_delta_mm = (
            float(recommended_stroke_mm) - target_stroke
            if math.isfinite(recommended_stroke_mm)
            else float("nan")
        )
        force_bias = (
            build_cylinder_force_bias_estimate(
                row,
                cap_pressure_bar_gauge=float(current_precharge.cap_precharge_bar_g),
                rod_pressure_bar_gauge=float(current_precharge.rod_precharge_bar_g),
                clamp_negative=False,
            )
            if (
                current_precharge is not None
                and math.isfinite(float(current_precharge.cap_precharge_bar_g))
                and math.isfinite(float(current_precharge.rod_precharge_bar_g))
            )
            else None
        )
        net_force_N = float(force_bias.net_force_N) if force_bias is not None else float("nan")
        net_force_delta_N = (
            net_force_N - float(current_precharge.net_force_N)
            if (
                force_bias is not None
                and current_precharge is not None
                and math.isfinite(float(current_precharge.net_force_N))
            )
            else float("nan")
        )
        notes: list[str] = []
        understroke_penalty = 0.0
        if math.isfinite(stroke_delta_mm):
            if stroke_delta_mm < 0.0:
                notes.append("stroke ниже target")
                understroke_penalty = 1000.0 + abs(stroke_delta_mm)
            elif stroke_delta_mm > 0.0:
                notes.append("stroke с запасом")
            else:
                notes.append("stroke в target")
        else:
            notes.append("stroke options не заданы")
            understroke_penalty = 1000.0
        if abs(bore_delta_mm) <= 0.5:
            notes.append("bore совпадает")
        if abs(rod_delta_mm) <= 0.5:
            notes.append("rod совпадает")
        force_penalty = 0.0
        bias_direction = str(force_bias.bias_direction) if force_bias is not None else "нет данных"
        if math.isfinite(net_force_delta_N):
            force_penalty = abs(net_force_delta_N) * 0.002
            if abs(net_force_delta_N) <= 150.0:
                notes.append("bias близок к current")
            elif abs(net_force_delta_N) > 800.0:
                notes.append("bias заметно смещается")
            else:
                notes.append("bias смещается")
            current_bias_direction = str(current_precharge.bias_direction) if current_precharge is not None else "нет данных"
            if (
                current_bias_direction in {"extend", "retract"}
                and bias_direction in {"extend", "retract"}
                and bias_direction != current_bias_direction
            ):
                notes.append("bias direction меняется")
                force_penalty += 25.0
        elif current_precharge is not None:
            notes.append("bias не оценен")
        score = (
            abs(bore_delta_mm) * 4.0
            + abs(rod_delta_mm) * 6.0
            + (abs(stroke_delta_mm) * 0.25 if math.isfinite(stroke_delta_mm) else 250.0)
            + understroke_penalty
            + force_penalty
        )
        recommendations.append(
            CylinderMatchRecommendation(
                family=current_row.family,
                variant_key=row.variant_key,
                variant_label=row.variant_label,
                bore_mm=row.bore_mm,
                rod_mm=row.rod_mm,
                recommended_stroke_mm=float(recommended_stroke_mm),
                bore_delta_mm=float(bore_delta_mm),
                rod_delta_mm=float(rod_delta_mm),
                stroke_delta_mm=float(stroke_delta_mm),
                net_force_N=float(net_force_N),
                net_force_delta_N=float(net_force_delta_N),
                bias_direction=bias_direction,
                score=float(score),
                notes=tuple(notes),
            )
        )
    recommendations.sort(
        key=lambda item: (
            float(item.score),
            abs(float(item.bore_delta_mm)),
            abs(float(item.rod_delta_mm)),
            abs(float(item.stroke_delta_mm)) if math.isfinite(item.stroke_delta_mm) else float("inf"),
            item.variant_label,
            item.bore_mm,
            item.rod_mm,
        )
    )
    return tuple(recommendations[: max(1, int(limit))])


def build_current_spring_reference_snapshot(
    base_payload: Mapping[str, Any],
) -> SpringReferenceSnapshot:
    normalized_base, _normalized_ranges, _meta = normalize_component_family_contract(base_payload, {})
    families: list[SpringFamilyReferenceRow] = []
    for cyl, axle in FAMILY_ORDER:
        geometry: SpringGeometryReference = build_spring_geometry_reference(
            d_wire_m=_safe_float(normalized_base.get(spring_family_key("геом_диаметр_проволоки_м", cyl, axle)), default=0.0),
            D_mean_m=_safe_float(normalized_base.get(spring_family_key("геом_диаметр_средний_м", cyl, axle)), default=0.0),
            N_active=_safe_float(normalized_base.get(spring_family_key("геом_число_витков_активных", cyl, axle)), default=0.0),
            N_total=_safe_float(normalized_base.get(spring_family_key("геом_число_витков_полное", cyl, axle)), default=0.0),
            pitch_m=_safe_float(normalized_base.get(spring_family_key("геом_шаг_витка_м", cyl, axle)), default=0.0),
            G_Pa=_safe_float(normalized_base.get(spring_family_key("геом_G_Па", cyl, axle)), default=0.0),
            F_max_N=0.0,
        )
        explicit_solid_m = _safe_float(
            normalized_base.get(spring_family_key("длина_солид_м", cyl, axle)),
            default=float("nan"),
        )
        solid_length_m = (
            explicit_solid_m
            if math.isfinite(explicit_solid_m) and explicit_solid_m > 0.0
            else geometry.solid_length_m
        )
        free_length_m = _safe_float(
            normalized_base.get(spring_family_key("длина_свободная_м", cyl, axle)),
            default=float("nan"),
        )
        top_offset_m = _safe_float(
            normalized_base.get(spring_family_key("верхний_отступ_от_крышки_м", cyl, axle)),
            default=float("nan"),
        )
        rebound_preload_min_m = _safe_float(
            normalized_base.get(spring_family_key("преднатяг_на_отбое_минимум_м", cyl, axle)),
            default=float("nan"),
        )
        inner_diameter_m = _safe_float(
            normalized_base.get(spring_geometry_key("inner_diameter_m", cyl, axle)),
            default=float("nan"),
        )
        outer_diameter_m = _safe_float(
            normalized_base.get(spring_geometry_key("outer_diameter_m", cyl, axle)),
            default=float("nan"),
        )
        has_mean_and_wire = (
            math.isfinite(float(geometry.D_mean_m))
            and math.isfinite(float(geometry.d_wire_m))
            and float(geometry.D_mean_m) > 0.0
            and float(geometry.d_wire_m) > 0.0
        )
        if not math.isfinite(inner_diameter_m) or inner_diameter_m <= 0.0:
            inner_diameter_m = (
                float(geometry.D_mean_m - geometry.d_wire_m)
                if has_mean_and_wire and float(geometry.D_mean_m) > float(geometry.d_wire_m)
                else float("nan")
            )
        if not math.isfinite(outer_diameter_m) or outer_diameter_m <= 0.0:
            outer_diameter_m = (
                float(geometry.D_mean_m + geometry.d_wire_m)
                if has_mean_and_wire
                else float("nan")
            )
        families.append(
            SpringFamilyReferenceRow(
                family=family_name(cyl, axle),
                wire_mm=_meters_to_mm(geometry.d_wire_m),
                mean_diameter_mm=_meters_to_mm(geometry.D_mean_m),
                inner_diameter_mm=_meters_to_mm(inner_diameter_m),
                outer_diameter_mm=_meters_to_mm(outer_diameter_m),
                active_turns=float(geometry.N_active),
                total_turns=float(geometry.N_total),
                pitch_mm=_meters_to_mm(geometry.pitch_m),
                shear_modulus_GPa=float(geometry.G_Pa / 1.0e9) if math.isfinite(geometry.G_Pa) else float("nan"),
                rate_N_per_mm=float(geometry.rate_N_per_mm),
                free_length_mm=_meters_to_mm(free_length_m),
                solid_length_mm=_meters_to_mm(solid_length_m),
                free_length_from_pitch_mm=_meters_to_mm(geometry.free_length_from_pitch_m),
                free_length_pitch_gap_mm=(
                    _meters_to_mm(free_length_m - geometry.free_length_from_pitch_m)
                    if math.isfinite(free_length_m) and math.isfinite(geometry.free_length_from_pitch_m)
                    else float("nan")
                ),
                top_offset_mm=_meters_to_mm(top_offset_m),
                rebound_preload_min_mm=_meters_to_mm(rebound_preload_min_m),
                bind_travel_margin_mm=_meters_to_mm(geometry.bind_travel_margin_m),
                bind_margin_target_mm=_meters_to_mm(
                    _safe_float(
                        normalized_base.get(spring_family_key("запас_до_coil_bind_минимум_м", cyl, axle)),
                        default=0.0,
                    )
                ),
            )
        )
    return SpringReferenceSnapshot(
        static_mode=str(normalized_base.get(SPRING_STATIC_MODE_KEY, "") or ""),
        families=tuple(families),
    )


def build_component_fit_reference_rows(
    base_payload: Mapping[str, Any],
    *,
    base_path: Path,
    dw_min_mm: float = -100.0,
    dw_max_mm: float = 100.0,
) -> tuple[ComponentFitReferenceRow, ...]:
    geometry_rows = {
        row.family: row
        for row in build_geometry_reference_snapshot(
            base_payload,
            base_path=base_path,
            dw_min_mm=dw_min_mm,
            dw_max_mm=dw_max_mm,
        ).families
    }
    cylinder_rows = {row.family: row for row in build_current_cylinder_reference_rows(base_payload)}
    cylinder_precharge_rows = {row.family: row for row in build_current_cylinder_precharge_rows(base_payload)}
    cylinder_outer_diameters_mm = build_current_cylinder_outer_diameter_rows(base_payload)
    spring_rows = {row.family: row for row in build_current_spring_reference_snapshot(base_payload).families}
    catalog_rows = load_camozzi_catalog_rows()

    rows: list[ComponentFitReferenceRow] = []
    for cyl, axle in FAMILY_ORDER:
        family = family_name(cyl, axle)
        geometry = geometry_rows.get(family)
        current_cylinder = cylinder_rows.get(family)
        current_precharge = cylinder_precharge_rows.get(family)
        spring = spring_rows.get(family)
        recommendation = None
        if current_cylinder is not None:
            recommendations = build_cylinder_match_recommendations(
                current_cylinder,
                catalog_rows,
                current_precharge=current_precharge,
                limit=1,
            )
            recommendation = recommendations[0] if recommendations else None

        notes: list[str] = []
        action_summary = "Семейство выглядит согласованным."
        warn = False

        stroke_usage_pct = float(geometry.stroke_usage_pct) if geometry is not None else float("nan")
        motion_ratio_peak = float(geometry.motion_ratio_peak) if geometry is not None else float("nan")
        current_stroke_mm = float(current_cylinder.stroke_mm) if current_cylinder is not None else float("nan")
        cylinder_outer_diameter_mm = float(cylinder_outer_diameters_mm.get(family, float("nan")))
        spring_inner_diameter_mm = float(spring.inner_diameter_mm) if spring is not None else float("nan")
        spring_outer_diameter_mm = float(spring.outer_diameter_mm) if spring is not None else float("nan")
        spring_to_cylinder_clearance_mm = (
            spring_inner_diameter_mm - cylinder_outer_diameter_mm
            if math.isfinite(spring_inner_diameter_mm) and math.isfinite(cylinder_outer_diameter_mm)
            else float("nan")
        )

        if not math.isfinite(stroke_usage_pct):
            warn = True
            notes.append("нет geometry stroke usage")
            action_summary = "Сначала проверьте geometry и stroke текущего семейства."
        elif stroke_usage_pct > 100.0:
            warn = True
            notes.append("ход штока превышен")
            action_summary = "Нужно увеличить stroke или пересмотреть wheel-travel / точки крепления."
        elif stroke_usage_pct > 85.0:
            warn = True
            notes.append("запас хода мал")
            action_summary = "Запас хода мал: подтвердите stroke и геометрию до выбора цилиндра."

        recommended_catalog_label = "—"
        recommended_stroke_mm = float("nan")
        current_net_force_N = float(current_precharge.net_force_N) if current_precharge is not None else float("nan")
        recommended_net_force_N = float("nan")
        recommended_net_force_delta_N = float("nan")
        recommended_bias_direction = "нет данных"
        if recommendation is None:
            warn = True
            notes.append("нет каталожного match")
            if action_summary == "Семейство выглядит согласованным.":
                action_summary = "Не найден близкий каталожный match: ослабьте фильтр или подтвердите размеры."
        else:
            recommended_catalog_label = (
                f"{recommendation.variant_label} {recommendation.bore_mm}/{recommendation.rod_mm}"
            )
            recommended_stroke_mm = float(recommendation.recommended_stroke_mm)
            recommended_net_force_N = float(recommendation.net_force_N)
            recommended_net_force_delta_N = float(recommendation.net_force_delta_N)
            recommended_bias_direction = str(recommendation.bias_direction)
            if abs(float(recommendation.bore_delta_mm)) > 1.0 or abs(float(recommendation.rod_delta_mm)) > 1.0:
                warn = True
                notes.append("Camozzi match требует смены bore/rod")
                if action_summary == "Семейство выглядит согласованным.":
                    action_summary = "Ближайший Camozzi требует изменения bore/rod относительно текущего base."
            else:
                notes.append("Camozzi bore/rod близок")
            if math.isfinite(float(recommendation.stroke_delta_mm)):
                if float(recommendation.stroke_delta_mm) < 0.0:
                    warn = True
                    notes.append("catalog stroke ниже target")
                    action_summary = "Каталожный stroke ниже target: увеличьте target stroke или смените семейство."
                elif float(recommendation.stroke_delta_mm) > 0.0:
                    notes.append("catalog stroke с запасом")
            if math.isfinite(recommended_net_force_delta_N):
                if (
                    current_precharge is not None
                    and current_precharge.bias_direction in {"extend", "retract"}
                    and recommended_bias_direction in {"extend", "retract"}
                    and recommended_bias_direction != current_precharge.bias_direction
                ):
                    warn = True
                    notes.append("Camozzi меняет direction bias")
                    if action_summary == "Семейство выглядит согласованным.":
                        action_summary = "Каталожный цилиндр меняет направление precharge bias: проверьте CAP/ROD contract."
                elif abs(recommended_net_force_delta_N) > 800.0:
                    warn = True
                    notes.append("Camozzi сильно смещает precharge bias")
                    if action_summary == "Семейство выглядит согласованным.":
                        action_summary = "Каталожный цилиндр заметно меняет Fnet при текущем precharge: подтвердите силовой баланс."
                elif abs(recommended_net_force_delta_N) > 150.0:
                    notes.append("Camozzi умеренно смещает precharge bias")
                else:
                    notes.append("Camozzi bias близок к current")
            elif current_precharge is not None:
                notes.append("нет bias-сравнения с Camozzi")

        spring_bind_margin_mm = float(spring.bind_travel_margin_mm) if spring is not None else float("nan")
        spring_bind_target_mm = float(spring.bind_margin_target_mm) if spring is not None else float("nan")
        if not math.isfinite(spring_bind_margin_mm):
            warn = True
            notes.append("нет spring reserve")
            if action_summary == "Семейство выглядит согласованным.":
                action_summary = "Нужно задать spring geometry, чтобы проверить coil-bind reserve."
        elif spring_bind_margin_mm < 0.0:
            warn = True
            notes.append("spring geometry невозможна")
            action_summary = "Пружина нереализуема: Lfree из pitch меньше Lsolid."
        elif math.isfinite(spring_bind_target_mm) and spring_bind_margin_mm < spring_bind_target_mm:
            warn = True
            notes.append("coil-bind reserve ниже target")
            if action_summary == "Семейство выглядит согласованным.":
                action_summary = "Увеличьте reserve до coil-bind или пересоберите spring geometry."
        else:
            notes.append("coil-bind reserve ok")

        if not math.isfinite(spring_to_cylinder_clearance_mm):
            warn = True
            notes.append("нет spring/cylinder clearance")
            if action_summary == "Семейство выглядит согласованным.":
                action_summary = "Не хватает данных по диаметрам spring/cylinder для проверки посадки."
        elif spring_to_cylinder_clearance_mm < 0.0:
            warn = True
            notes.append("spring ID меньше cylinder OD")
            action_summary = "Пружина не надевается на цилиндр: увеличьте ID spring или уменьшите OD цилиндра."
        elif spring_to_cylinder_clearance_mm < 2.0:
            warn = True
            notes.append("малый diametral clearance")
            if action_summary == "Семейство выглядит согласованным.":
                action_summary = "Зазор между spring ID и cylinder OD мал: подтвердите посадку и технологический запас."
        else:
            notes.append("diameter clearance ok")

        rows.append(
            ComponentFitReferenceRow(
                family=family,
                status="warn" if warn else "ok",
                stroke_usage_pct=stroke_usage_pct,
                motion_ratio_peak=motion_ratio_peak,
                current_stroke_mm=current_stroke_mm,
                cylinder_outer_diameter_mm=cylinder_outer_diameter_mm,
                spring_inner_diameter_mm=spring_inner_diameter_mm,
                spring_outer_diameter_mm=spring_outer_diameter_mm,
                spring_to_cylinder_clearance_mm=spring_to_cylinder_clearance_mm,
                recommended_catalog_label=recommended_catalog_label,
                recommended_stroke_mm=recommended_stroke_mm,
                current_net_force_N=current_net_force_N,
                recommended_net_force_N=recommended_net_force_N,
                recommended_net_force_delta_N=recommended_net_force_delta_N,
                recommended_bias_direction=recommended_bias_direction,
                spring_bind_margin_mm=spring_bind_margin_mm,
                spring_bind_target_mm=spring_bind_target_mm,
                action_summary=action_summary,
                notes=tuple(notes),
            )
        )
    return tuple(rows)


def build_parameter_guide_rows(
    query: str = "",
    *,
    base_payload: Mapping[str, Any] | None = None,
    limit: int = 80,
) -> tuple[ParameterGuideRow, ...]:
    spec_by_key = field_spec_map()
    normalized_base = dict(base_payload or {})
    query_text = str(query or "").strip()
    rows: list[ParameterGuideRow] = []
    if query_text:
        for match in find_desktop_field_matches(query_text, limit=limit):
            key = str(match.get("key") or "").strip()
            spec = spec_by_key.get(key)
            if spec is None:
                continue
            rows.append(
                ParameterGuideRow(
                    key=key,
                    label=str(match.get("label") or spec.label),
                    unit_label=str(spec.unit_label or ""),
                    section_title=str(match.get("section_title") or ""),
                    description=str(match.get("description") or spec.description),
                    display=str(match.get("display") or desktop_field_search_display_name(spec, str(match.get("section_title") or ""))),
                    current_value_text=_format_current_value(
                        spec.to_ui(normalized_base.get(key)),
                        unit_label=str(spec.unit_label or ""),
                        digits=int(spec.digits),
                    ),
                )
            )
        family_rows = _build_family_parameter_guide_rows(normalized_base)
        tokens = tuple(part for part in query_text.lower().replace("ё", "е").split() if part)
        matched_keys = {row.key for row in rows}
        for row in family_rows:
            haystack = " ".join(
                (
                    row.label,
                    row.unit_label,
                    row.section_title,
                    row.key,
                    row.description,
                    row.display,
                    row.current_value_text,
                )
            ).lower().replace("ё", "е")
            if row.key in matched_keys:
                continue
            if all(token in haystack for token in tokens):
                rows.append(row)
        return tuple(rows[: max(1, int(limit))])

    for section in DESKTOP_INPUT_SECTIONS:
        if section.title not in REFERENCE_GUIDE_SECTION_TITLES:
            continue
        for spec in section.fields:
            rows.append(
                ParameterGuideRow(
                    key=str(spec.key),
                    label=str(spec.label),
                    unit_label=str(spec.unit_label),
                    section_title=str(section.title),
                    description=str(spec.description),
                    display=desktop_field_search_display_name(spec, section.title),
                    current_value_text=_format_current_value(
                        spec.to_ui(normalized_base.get(spec.key)),
                        unit_label=str(spec.unit_label or ""),
                        digits=int(spec.digits),
                    ),
                )
            )
    rows.extend(_build_family_parameter_guide_rows(normalized_base))
    return tuple(rows[: max(1, int(limit))])


def _build_family_parameter_guide_rows(
    base_payload: Mapping[str, Any],
) -> tuple[ParameterGuideRow, ...]:
    keys: list[str] = [SPRING_STATIC_MODE_KEY]
    for cyl, axle in FAMILY_ORDER:
        keys.extend(
            [
                cylinder_family_key("bore", cyl, axle),
                cylinder_family_key("rod", cyl, axle),
                cylinder_family_key("stroke", cyl, axle),
            ]
        )
        for chamber in CYLINDER_PRECHARGE_CHAMBERS:
            keys.append(cylinder_precharge_key(cyl, chamber, axle))
        for field in CYLINDER_AXLE_GEOMETRY_FIELDS:
            keys.append(cylinder_axle_geometry_key(field, cyl, axle))
        for suffix in (
            "геом_диаметр_проволоки_м",
            "геом_диаметр_средний_м",
            "геом_число_витков_активных",
            "геом_число_витков_полное",
            "геом_шаг_витка_м",
            "геом_G_Па",
            "длина_солид_м",
            "запас_до_coil_bind_минимум_м",
        ):
            keys.append(spring_family_key(suffix, cyl, axle))
        for field in SPRING_GEOMETRY_FIELDS:
            keys.append(spring_geometry_key(field, cyl, axle))

    rows: list[ParameterGuideRow] = []
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        meta = family_param_meta(key)
        if not isinstance(meta, dict):
            continue
        section_title = str(meta.get("группа") or "Family contract")
        unit_label = str(meta.get("ед") or "")
        description = str(meta.get("описание") or "").strip()
        label = str(key)
        rows.append(
            ParameterGuideRow(
                key=str(key),
                label=label,
                unit_label=unit_label,
                section_title=section_title,
                description=description,
                display=f"{label} — {section_title}",
                current_value_text=_format_family_current_value(base_payload.get(key), meta),
            )
        )
    return tuple(rows)


__all__ = [
    "CATALOG_JSON",
    "REFERENCE_GUIDE_SECTION_TITLES",
    "ATM_PA",
    "CylinderCatalogRow",
    "CylinderForceBiasEstimate",
    "CylinderFamilyReferenceRow",
    "CylinderMatchRecommendation",
    "CylinderPackageReferenceRow",
    "CylinderPrechargeReferenceRow",
    "CylinderPressureEstimate",
    "ComponentFitReferenceRow",
    "GeometryFamilyReferenceRow",
    "GeometryReferenceSnapshot",
    "ParameterGuideRow",
    "SpringFamilyReferenceRow",
    "SpringReferenceSnapshot",
    "build_current_cylinder_package_rows",
    "build_current_cylinder_precharge_rows",
    "build_current_cylinder_reference_rows",
    "build_current_spring_reference_snapshot",
    "build_cylinder_force_bias_estimate",
    "build_cylinder_match_recommendations",
    "build_cylinder_pressure_estimate",
    "build_component_fit_reference_rows",
    "build_geometry_reference_snapshot",
    "build_parameter_guide_rows",
    "load_camozzi_catalog_rows",
    "load_camozzi_stroke_options_mm",
]
