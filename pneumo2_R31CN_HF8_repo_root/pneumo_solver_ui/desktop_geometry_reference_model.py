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
from pneumo_solver_ui.geometry_acceptance_contract import (
    GEOMETRY_ACCEPTANCE_JSON_NAME,
    build_geometry_acceptance_rows,
    collect_geometry_acceptance_from_frame,
    format_geometry_acceptance_summary_lines,
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
    canonical_axle_slug,
    canonical_cylinder_slug,
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
COMPONENT_PASSPORT_JSON = Path(__file__).resolve().parent / "component_passport.json"
REFERENCE_GUIDE_SECTION_TITLES: tuple[str, ...] = (
    "Геометрия",
    "Пневматика",
    "Компоненты",
    "Справочные данные",
)
ATM_PA = 101325.0
TRUTH_STATE_SOURCE_DATA_CONFIRMED = "source_data_confirmed"
TRUTH_STATE_APPROXIMATE = "approximate_inferred_with_warning"
TRUTH_STATE_UNAVAILABLE = "unavailable"

GEOMETRY_REFERENCE_PRODUCER_EVIDENCE_OWNER = "producer_export"
GEOMETRY_REFERENCE_REQUIRED_PRODUCER_ARTIFACTS: tuple[str, ...] = (
    "workspace/_pointers/anim_latest.json or workspace/exports/anim_latest.json",
    "workspace/exports/anim_latest.npz",
    "workspace/exports/CYLINDER_PACKAGING_PASSPORT.json",
    "workspace/exports/geometry_acceptance_report.json",
)
GEOMETRY_REFERENCE_PRODUCER_NEXT_ACTION = (
    "Run producer/solver anim_latest export so NPZ meta.geometry/meta.packaging, "
    "CYLINDER_PACKAGING_PASSPORT.json and geometry_acceptance_report.json are written; "
    "Reference Center must not fabricate producer geometry evidence."
)

CYLINDER_PACKAGING_BASIC_FIELDS: tuple[str, ...] = (
    "bore_diameter_m",
    "rod_diameter_m",
    "stroke_m",
    "outer_diameter_m",
    "dead_cap_length_m",
    "dead_rod_length_m",
    "dead_height_m",
    "body_length_m",
)
CYLINDER_PACKAGING_ADVANCED_FIELDS: tuple[str, ...] = (
    "gland_length_m",
    "rod_eye_length_m",
    "retracted_pin_to_pin_m",
    "extended_pin_to_pin_m",
    "piston_length_m",
)
CYLINDER_PACKAGING_REQUIRED_FIELDS: tuple[str, ...] = (
    *CYLINDER_PACKAGING_BASIC_FIELDS,
    *CYLINDER_PACKAGING_ADVANCED_FIELDS,
)


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
class ComponentPassportCatalogRow:
    component_id: str
    manufacturer: str
    family: str
    category: str
    ports: str
    status: str
    missing_data_count: int
    iso6358_status: str
    help_text: str


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
    status: str = "unknown"
    truth_state: str = TRUTH_STATE_UNAVAILABLE
    completeness_pct: float = 0.0
    missing_fields: tuple[str, ...] = ()
    hidden_elements: tuple[str, ...] = ()
    passport_id: str = ""
    explanation: str = ""


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


@dataclass(frozen=True)
class RoadWidthReference:
    parameter_key: str
    label: str
    unit_label: str
    explicit_road_width_m: float
    effective_road_width_m: float
    track_m: float
    wheel_width_m: float
    status: str
    source: str
    explanation: str


@dataclass(frozen=True)
class GeometryAcceptanceEvidenceRow:
    corner: str
    gate: str
    reason: str
    sigma_err_mm: float
    xy_wheel_road_err_mm: float
    wf_err_mm: float
    wr_err_mm: float
    fr_err_mm: float
    missing: str


@dataclass(frozen=True)
class GeometryAcceptanceEvidenceSnapshot:
    gate: str
    reason: str
    available: bool
    source_label: str
    evidence_required: str
    summary_lines: tuple[str, ...]
    rows: tuple[GeometryAcceptanceEvidenceRow, ...]
    artifact_status: str = "missing"
    source_path: str = ""
    updated_utc: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactReferenceContext:
    status: str
    source_label: str
    pointer_path: str
    npz_path: str
    exports_dir: str
    updated_utc: str
    visual_cache_token: str
    meta: Mapping[str, Any]
    issues: tuple[str, ...]
    packaging_passport_path: str
    packaging_passport_exists: bool
    geometry_acceptance_path: str
    geometry_acceptance_exists: bool


@dataclass(frozen=True)
class RoadWidthEvidence:
    parameter_key: str
    unit_label: str
    status: str
    preferred_source: str
    base_status: str
    base_effective_m: float
    meta_road_width_m: float
    effective_road_width_m: float
    mismatch_mm: float
    explanation: str


@dataclass(frozen=True)
class PackagingPassportEvidenceRow:
    cylinder: str
    base_status: str
    export_status: str
    export_truth_mode: str
    base_completeness_pct: float
    contract_complete: bool
    full_mesh_allowed: bool
    consumer_geometry_fabrication_allowed: bool
    mismatch_status: str
    missing_advanced_fields: tuple[str, ...]
    missing_geometry_fields: tuple[str, ...]
    length_status_summary: str


@dataclass(frozen=True)
class PackagingPassportEvidenceSnapshot:
    artifact_status: str
    source_label: str
    passport_path: str
    schema: str
    packaging_status: str
    packaging_contract_hash: str
    mismatch_status: str
    complete_cylinders: tuple[str, ...]
    axis_only_cylinders: tuple[str, ...]
    missing_advanced_fields: tuple[str, ...]
    consumer_geometry_fabrication_allowed: bool
    warnings: tuple[str, ...]
    rows: tuple[PackagingPassportEvidenceRow, ...]


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


def _is_positive_finite(value: Any) -> bool:
    try:
        out = float(value)
    except Exception:
        return False
    return math.isfinite(out) and out > 0.0


def cylinder_packaging_passport_key(field: str, cyl: str, axle: str) -> str:
    field_name = str(field or "").strip()
    if field_name in CYLINDER_AXLE_GEOMETRY_FIELDS:
        return cylinder_axle_geometry_key(field_name, cyl, axle)
    stem = field_name[:-2] if field_name.endswith("_m") else field_name
    return f"{canonical_cylinder_slug(cyl)}_{stem}_{canonical_axle_slug(axle)}_m"


def _component_passport_status(component: Mapping[str, Any]) -> tuple[str, str]:
    missing_data = component.get("missing_data") if isinstance(component, Mapping) else ()
    missing_count = len(missing_data) if isinstance(missing_data, (list, tuple)) else 0
    iso = component.get("iso6358") if isinstance(component.get("iso6358"), Mapping) else {}
    status_map = dict(iso.get("_status") or {}) if isinstance(iso, Mapping) else {}
    status_text = "; ".join(f"{key}={value}" for key, value in sorted(status_map.items())) or "not_declared"
    lowered = status_text.lower()
    if missing_count:
        status = "needs_datasheet"
    elif "assumed" in lowered or "estimated" in lowered:
        status = "estimated"
    else:
        status = "ok"
    return status, status_text


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


def load_component_passport_catalog_rows(
    passport_path: Path | str | None = None,
) -> tuple[ComponentPassportCatalogRow, ...]:
    path = Path(passport_path or COMPONENT_PASSPORT_JSON)
    if not path.exists():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    components = raw.get("components") if isinstance(raw, Mapping) else ()
    if not isinstance(components, (list, tuple)):
        return ()
    rows: list[ComponentPassportCatalogRow] = []
    for component in components:
        if not isinstance(component, Mapping):
            continue
        status, iso_status = _component_passport_status(component)
        missing_data = component.get("missing_data")
        missing_count = len(missing_data) if isinstance(missing_data, (list, tuple)) else 0
        component_id = str(component.get("id") or "").strip()
        family = str(component.get("family") or "").strip()
        category = str(component.get("category") or "").strip()
        rows.append(
            ComponentPassportCatalogRow(
                component_id=component_id,
                manufacturer=str(component.get("manufacturer") or "").strip(),
                family=family,
                category=category,
                ports=str(component.get("ports") or "").strip(),
                status=status,
                missing_data_count=int(missing_count),
                iso6358_status=iso_status,
                help_text=(
                    "component_passport.json is the pneumatic component data passport "
                    "for catalog values and ISO 6358 estimates. It is separate from the "
                    "cylinder packaging passport used for body/rod/piston geometry truth."
                ),
            )
        )
    return tuple(rows)


def build_road_width_reference(base_payload: Mapping[str, Any]) -> RoadWidthReference:
    explicit = _safe_float(base_payload.get("road_width_m"), default=float("nan"))
    track = _safe_float(base_payload.get("колея", base_payload.get("track_m")), default=float("nan"))
    wheel_width = _safe_float(base_payload.get("wheel_width_m"), default=0.0)
    if not math.isfinite(wheel_width) or wheel_width < 0.0:
        wheel_width = 0.0

    if math.isfinite(explicit) and explicit > 0.0:
        effective = float(explicit)
        status = "explicit"
        source = "base.road_width_m"
    elif math.isfinite(track) and track > 0.0:
        effective = float(max(track, track + max(0.0, wheel_width)))
        status = "derived_from_track_and_wheel_width"
        source = "derived: колея + wheel_width_m"
    else:
        effective = float("nan")
        status = "missing"
        source = "missing: need road_width_m or колея"

    if status == "explicit":
        explanation = (
            "GAP-008 visibility: road_width_m is explicit and can be passed to nested "
            "meta.geometry without a consumer-side derived fallback."
        )
    elif status == "derived_from_track_and_wheel_width":
        explanation = (
            "GAP-008 visibility: road_width_m is not explicit here, so the reference "
            "center shows the exporter-side derivation from track/колея plus wheel_width_m. "
            "This is a declared supplement, not hidden animator behavior."
        )
    else:
        explanation = (
            "GAP-008 visibility: road_width_m cannot be confirmed or derived. WS-RING "
            "should own scenario.root.road_width_m, and exports should surface it in "
            "meta.geometry before visual consumers read the run."
        )

    return RoadWidthReference(
        parameter_key="road_width_m",
        label="Ширина дороги",
        unit_label="м",
        explicit_road_width_m=float(explicit),
        effective_road_width_m=float(effective),
        track_m=float(track),
        wheel_width_m=float(wheel_width),
        status=status,
        source=source,
        explanation=explanation,
    )


def build_geometry_acceptance_evidence(
    frame_or_mapping: Any | None = None,
    *,
    source_label: str = "",
    tol_m: float = 1e-6,
) -> GeometryAcceptanceEvidenceSnapshot:
    summary = collect_geometry_acceptance_from_frame(
        {} if frame_or_mapping is None else frame_or_mapping,
        tol_m=tol_m,
    )
    rows: list[GeometryAcceptanceEvidenceRow] = []
    for row in build_geometry_acceptance_rows(summary):
        rows.append(
            GeometryAcceptanceEvidenceRow(
                corner=str(row.get("угол") or ""),
                gate=str(row.get("gate") or "MISSING"),
                reason=str(row.get("reason") or ""),
                sigma_err_mm=_safe_float(row.get("Σ err, мм")),
                xy_wheel_road_err_mm=_safe_float(row.get("XY wheel-road err, мм")),
                wf_err_mm=_safe_float(row.get("WF err, мм")),
                wr_err_mm=_safe_float(row.get("WR err, мм")),
                fr_err_mm=_safe_float(row.get("FR err, мм")),
                missing=str(row.get("missing") or ""),
            )
        )
    available = bool(summary.get("available", False))
    label = str(source_label or ("runtime frame" if frame_or_mapping is not None else "no runtime frame selected"))
    return GeometryAcceptanceEvidenceSnapshot(
        gate=str(summary.get("release_gate") or "MISSING"),
        reason=str(summary.get("release_gate_reason") or ""),
        available=available,
        source_label=label,
        evidence_required=(
            "geometry_acceptance_report requires solver-point triplets "
            "frame_corner/wheel_center/road_contact plus scalar FR/WR/WF columns."
        ),
        summary_lines=tuple(format_geometry_acceptance_summary_lines(summary, label=label)),
        rows=tuple(rows),
    )


def _read_json_mapping(path: Path | str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        p = Path(path).expanduser().resolve(strict=False)
    except Exception:
        return {}
    try:
        if not p.exists():
            return {}
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _safe_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item).strip())
    if value in (None, ""):
        return ()
    return (str(value),)


def _path_exists(path_text: str) -> bool:
    if not str(path_text or "").strip():
        return False
    try:
        return Path(path_text).expanduser().resolve(strict=False).exists()
    except Exception:
        return False


def _npz_main_mapping(npz_path: Path | str | None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if not npz_path:
        return {}, {}
    try:
        path = Path(npz_path).expanduser().resolve(strict=False)
    except Exception:
        return {}, {}
    if not path.exists():
        return {}, {}
    try:
        with np.load(path, allow_pickle=True) as data:
            if "main_cols" not in data or "main_values" not in data:
                return {}, {}
            cols = [str(col) for col in np.asarray(data["main_cols"]).tolist()]
            values = np.asarray(data["main_values"], dtype=float)
            if values.ndim == 1 and len(cols) == 1:
                values = values.reshape((-1, 1))
            if values.ndim != 2:
                return {}, {}
            mapping = {
                str(col): np.asarray(values[:, idx], dtype=float)
                for idx, col in enumerate(cols[: values.shape[1]])
            }
            meta: dict[str, Any] = {}
            if "meta_json" in data:
                raw = data["meta_json"].tolist()
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", errors="replace")
                if isinstance(raw, str):
                    loaded = json.loads(raw)
                    meta = dict(loaded) if isinstance(loaded, Mapping) else {}
                elif isinstance(raw, Mapping):
                    meta = dict(raw)
            return mapping, meta
    except Exception:
        return {}, {}


def build_artifact_reference_context(summary: Mapping[str, Any] | None = None) -> ArtifactReferenceContext:
    data = dict(summary or {})
    pointer_path = str(data.get("anim_latest_pointer_json") or data.get("pointer_json") or "")
    npz_path = str(data.get("anim_latest_npz_path") or data.get("npz_path") or "")
    pointer_exists = data.get("anim_latest_pointer_json_exists")
    npz_exists = data.get("anim_latest_npz_exists")
    if pointer_exists is None and pointer_path:
        pointer_exists = _path_exists(pointer_path)
    if npz_exists is None and npz_path:
        npz_exists = _path_exists(npz_path)
    pointer_in_workspace = data.get("anim_latest_pointer_json_in_workspace")
    npz_in_workspace = data.get("anim_latest_npz_in_workspace")
    usable = bool(data.get("anim_latest_usable"))
    if not pointer_path and not npz_path:
        status = "missing"
    elif pointer_exists is False or npz_exists is False:
        status = "stale"
    elif usable and (pointer_in_workspace is False or npz_in_workspace is False):
        status = "historical"
    elif usable or (npz_path and npz_exists is True):
        status = "current"
    else:
        status = "stale"

    meta = data.get("anim_latest_meta")
    if not isinstance(meta, Mapping):
        meta = data.get("meta") if isinstance(data.get("meta"), Mapping) else {}
    if not meta and npz_path and npz_exists is True:
        _mapping, npz_meta = _npz_main_mapping(npz_path)
        meta = npz_meta

    exports_dir = ""
    for candidate in (pointer_path, npz_path):
        if candidate:
            try:
                exports_dir = str(Path(candidate).expanduser().resolve(strict=False).parent)
                break
            except Exception:
                pass

    artifact_refs = dict(meta.get("anim_export_contract_artifacts") or {}) if isinstance(meta, Mapping) and isinstance(meta.get("anim_export_contract_artifacts"), Mapping) else {}

    def _resolve_ref(explicit_key: str, ref_key: str, default_name: str) -> tuple[str, bool]:
        explicit = str(data.get(explicit_key) or "").strip()
        raw = explicit or str(artifact_refs.get(ref_key) or default_name or "").strip()
        if not raw:
            return "", False
        try:
            path = Path(raw)
            if not path.is_absolute() and exports_dir:
                path = Path(exports_dir) / path
            resolved = str(path.expanduser().resolve(strict=False))
        except Exception:
            resolved = raw
        exists_value = data.get(explicit_key.replace("_path", "_exists"))
        exists = bool(exists_value) if isinstance(exists_value, bool) else _path_exists(resolved)
        return resolved, exists

    packaging_path, packaging_exists = _resolve_ref(
        "anim_latest_cylinder_packaging_passport_path",
        "cylinder_packaging_passport",
        "CYLINDER_PACKAGING_PASSPORT.json",
    )
    acceptance_path, acceptance_exists = _resolve_ref(
        "anim_latest_geometry_acceptance_json_path",
        "geometry_acceptance_json",
        GEOMETRY_ACCEPTANCE_JSON_NAME,
    )
    issues = _safe_strings(data.get("anim_latest_issues"))
    source_label_override = str(data.get("source_label") or data.get("artifact_source_label") or "").strip()
    source_label = source_label_override or (
        f"anim_latest {status}: {npz_path or pointer_path or 'no artifact'}"
        if status != "missing"
        else "anim_latest missing"
    )
    return ArtifactReferenceContext(
        status=status,
        source_label=source_label,
        pointer_path=pointer_path,
        npz_path=npz_path,
        exports_dir=exports_dir,
        updated_utc=str(data.get("anim_latest_updated_utc") or data.get("updated_utc") or data.get("updated_at") or ""),
        visual_cache_token=str(data.get("anim_latest_visual_cache_token") or data.get("visual_cache_token") or ""),
        meta=dict(meta or {}) if isinstance(meta, Mapping) else {},
        issues=issues,
        packaging_passport_path=packaging_path,
        packaging_passport_exists=bool(packaging_exists),
        geometry_acceptance_path=acceptance_path,
        geometry_acceptance_exists=bool(acceptance_exists),
    )


def build_geometry_acceptance_evidence_from_artifact(
    artifact: ArtifactReferenceContext,
    *,
    tol_m: float = 1e-6,
) -> GeometryAcceptanceEvidenceSnapshot:
    warnings: list[str] = []
    mapping: dict[str, np.ndarray] = {}
    meta_from_npz: dict[str, Any] = {}
    if artifact.npz_path and _path_exists(artifact.npz_path):
        mapping, meta_from_npz = _npz_main_mapping(artifact.npz_path)
    if not mapping:
        if artifact.status == "missing":
            warnings.append("No latest anim artifact is registered; geometry acceptance remains MISSING.")
        elif artifact.npz_path:
            warnings.append(f"NPZ artifact is unavailable or unreadable: {artifact.npz_path}")
        evidence = build_geometry_acceptance_evidence(
            None,
            source_label=artifact.source_label,
            tol_m=tol_m,
        )
    else:
        evidence = build_geometry_acceptance_evidence(
            mapping,
            source_label=artifact.source_label,
            tol_m=tol_m,
        )

    missing = sorted({part for row in evidence.rows for part in _safe_strings(row.missing)})
    if missing:
        warnings.append("Missing solver-point triplets: " + ", ".join(missing[:8]))
    scalar_mismatch = any(
        max(
            abs(value)
            for value in (row.wf_err_mm, row.wr_err_mm, row.fr_err_mm)
            if math.isfinite(value)
        )
        > 0.001
        for row in evidence.rows
        if any(math.isfinite(value) for value in (row.wf_err_mm, row.wr_err_mm, row.fr_err_mm))
    )
    if scalar_mismatch:
        warnings.append("Scalar FR/WR/WF columns diverge from exported XYZ solver-point evidence.")
    if meta_from_npz and artifact.status == "current":
        # Keep this as a cheap confidence marker for diagnostics consumers.
        pass
    return GeometryAcceptanceEvidenceSnapshot(
        gate=evidence.gate,
        reason=evidence.reason,
        available=evidence.available,
        source_label=evidence.source_label,
        evidence_required=evidence.evidence_required,
        summary_lines=evidence.summary_lines,
        rows=evidence.rows,
        artifact_status=artifact.status,
        source_path=artifact.npz_path,
        updated_utc=artifact.updated_utc,
        warnings=tuple(dict.fromkeys((*artifact.issues, *warnings))),
    )


def build_road_width_evidence(
    base_payload: Mapping[str, Any],
    *,
    artifact_meta: Mapping[str, Any] | None = None,
) -> RoadWidthEvidence:
    base = build_road_width_reference(base_payload)
    meta = dict(artifact_meta or {})
    geometry = dict(meta.get("geometry") or {}) if isinstance(meta.get("geometry"), Mapping) else {}
    meta_width = _safe_float(geometry.get("road_width_m"), default=float("nan"))
    if math.isfinite(meta_width) and meta_width > 0.0:
        mismatch = (
            (float(meta_width) - float(base.effective_road_width_m)) * 1000.0
            if math.isfinite(base.effective_road_width_m)
            else float("nan")
        )
        mismatch_text = (
            f" Base/reference differs by {mismatch:+.1f} mm."
            if math.isfinite(mismatch) and abs(mismatch) > 1e-6
            else ""
        )
        return RoadWidthEvidence(
            parameter_key="road_width_m",
            unit_label="м",
            status="explicit_meta",
            preferred_source="meta.geometry.road_width_m",
            base_status=base.status,
            base_effective_m=base.effective_road_width_m,
            meta_road_width_m=float(meta_width),
            effective_road_width_m=float(meta_width),
            mismatch_mm=float(mismatch),
            explanation=(
                "Exporter evidence wins for visual consumers: road_width_m is explicit in "
                "meta.geometry. WS-RING should own scenario.root.road_width_m; Animator must not "
                "derive it silently."
                + mismatch_text
            ),
        )
    if base.status != "missing":
        return RoadWidthEvidence(
            parameter_key="road_width_m",
            unit_label=base.unit_label,
            status=base.status,
            preferred_source=base.source,
            base_status=base.status,
            base_effective_m=base.effective_road_width_m,
            meta_road_width_m=float("nan"),
            effective_road_width_m=base.effective_road_width_m,
            mismatch_mm=float("nan"),
            explanation=base.explanation + " Export meta did not provide explicit meta.geometry.road_width_m.",
        )
    return RoadWidthEvidence(
        parameter_key="road_width_m",
        unit_label=base.unit_label,
        status="missing",
        preferred_source="missing",
        base_status=base.status,
        base_effective_m=base.effective_road_width_m,
        meta_road_width_m=float("nan"),
        effective_road_width_m=float("nan"),
        mismatch_mm=float("nan"),
        explanation=base.explanation + " No export meta.geometry.road_width_m evidence is available.",
    )


def _base_packaging_by_cylinder(
    base_rows: tuple[CylinderPackageReferenceRow, ...],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[CylinderPackageReferenceRow]] = {"cyl1": [], "cyl2": []}
    for row in base_rows:
        family = str(row.family)
        if "Ц1" in family or "cyl1" in family.lower():
            grouped["cyl1"].append(row)
        elif "Ц2" in family or "cyl2" in family.lower():
            grouped["cyl2"].append(row)
    out: dict[str, dict[str, Any]] = {}
    for cyl, rows in grouped.items():
        if not rows:
            out[cyl] = {
                "status": "missing",
                "completeness_pct": 0.0,
                "axis_only_families": (),
                "missing_fields": (),
            }
            continue
        complete = all(row.status == "complete" for row in rows)
        out[cyl] = {
            "status": "complete" if complete else "axis_only",
            "completeness_pct": float(sum(float(row.completeness_pct) for row in rows) / max(1, len(rows))),
            "axis_only_families": tuple(row.family for row in rows if row.status != "complete"),
            "missing_fields": tuple(
                dict.fromkeys(field for row in rows for field in row.missing_fields)
            ),
        }
    return out


def _passport_from_meta_packaging(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    meta_dict = dict(meta or {})
    packaging = dict(meta_dict.get("packaging") or {}) if isinstance(meta_dict.get("packaging"), Mapping) else {}
    if not packaging:
        return {}
    cylinders = dict(packaging.get("cylinders") or {}) if isinstance(packaging.get("cylinders"), Mapping) else {}
    out_cylinders: dict[str, Any] = {}
    for cyl_name, block in cylinders.items():
        cyl = dict(block or {}) if isinstance(block, Mapping) else {}
        out_cylinders[str(cyl_name)] = {
            "contract_complete": bool(cyl.get("contract_complete")),
            "length_status_by_corner": dict(cyl.get("length_status_by_corner") or {}) if isinstance(cyl.get("length_status_by_corner"), Mapping) else {},
            "missing_geometry_fields": list(cyl.get("missing_geometry_fields") or []),
            "advanced_fields_present": list(cyl.get("advanced_fields_present") or []),
            "advanced_fields_missing": list(cyl.get("advanced_fields_missing") or []),
            "truth_mode": str(cyl.get("truth_mode") or ""),
            "graphics_truth_state": str(cyl.get("graphics_truth_state") or ""),
            "axis_only_honesty_mode": bool(cyl.get("axis_only_honesty_mode", not bool(cyl.get("contract_complete")))),
            "full_mesh_allowed": bool(cyl.get("full_mesh_allowed", bool(cyl.get("contract_complete")))),
            "consumer_geometry_fabrication_allowed": bool(cyl.get("consumer_geometry_fabrication_allowed", False)),
        }
    return {
        "schema": "meta.packaging.inline",
        "packaging_status": str(packaging.get("status") or ""),
        "packaging_contract_hash": str(packaging.get("packaging_contract_hash") or ""),
        "required_advanced_fields": list(packaging.get("required_advanced_fields") or []),
        "missing_advanced_fields": list(packaging.get("missing_advanced_fields") or []),
        "complete_cylinders": list(packaging.get("complete_cylinders") or []),
        "axis_only_cylinders": list(packaging.get("axis_only_cylinders") or []),
        "cylinders": out_cylinders,
        "consumer_policy": dict(packaging.get("policy") or {}) if isinstance(packaging.get("policy"), Mapping) else {},
    }


def build_packaging_passport_evidence(
    base_rows: tuple[CylinderPackageReferenceRow, ...],
    *,
    artifact_context: ArtifactReferenceContext | None = None,
    artifact_meta: Mapping[str, Any] | None = None,
    passport_path: Path | str | None = None,
) -> PackagingPassportEvidenceSnapshot:
    context = artifact_context
    meta = dict(artifact_meta or (context.meta if context is not None else {}) or {})
    raw_path = str(passport_path or (context.packaging_passport_path if context is not None else "") or "")
    passport = _read_json_mapping(raw_path)
    source_label = "CYLINDER_PACKAGING_PASSPORT.json"
    if not passport:
        passport = _passport_from_meta_packaging(meta)
        source_label = "meta.packaging inline" if passport else "missing packaging passport"
    artifact_status = context.status if context is not None else ("current" if passport else "missing")
    base_by_cyl = _base_packaging_by_cylinder(base_rows)
    warnings: list[str] = []
    if not passport:
        warnings.append("Missing CYLINDER_PACKAGING_PASSPORT.json and meta.packaging; packaging truth remains evidence-missing.")

    cylinders = dict(passport.get("cylinders") or {}) if isinstance(passport.get("cylinders"), Mapping) else {}
    cyl_names = tuple(dict.fromkeys(("cyl1", "cyl2", *[str(name) for name in cylinders.keys()])))
    rows: list[PackagingPassportEvidenceRow] = []
    for cyl_name in cyl_names:
        base = dict(base_by_cyl.get(cyl_name) or {})
        cyl = dict(cylinders.get(cyl_name) or {}) if isinstance(cylinders.get(cyl_name), Mapping) else {}
        contract_complete = bool(cyl.get("contract_complete"))
        full_mesh_allowed = bool(cyl.get("full_mesh_allowed", contract_complete))
        fabrication = bool(cyl.get("consumer_geometry_fabrication_allowed", False))
        base_complete = str(base.get("status") or "") == "complete"
        if not passport:
            mismatch = "missing_artifact"
        elif fabrication:
            mismatch = "fabrication_violation"
        elif base_complete and not contract_complete:
            mismatch = "export_missing"
        elif (not base_complete) and contract_complete:
            mismatch = "base_missing"
        else:
            mismatch = "match"
        length_status = dict(cyl.get("length_status_by_corner") or {}) if isinstance(cyl.get("length_status_by_corner"), Mapping) else {}
        if length_status:
            status_counts: dict[str, int] = {}
            for value in length_status.values():
                key = str(value or "missing")
                status_counts[key] = status_counts.get(key, 0) + 1
            length_summary = ", ".join(f"{key}:{count}" for key, count in sorted(status_counts.items()))
        else:
            length_summary = "—"
        rows.append(
            PackagingPassportEvidenceRow(
                cylinder=cyl_name,
                base_status=str(base.get("status") or "missing"),
                export_status="complete" if contract_complete else ("axis_only" if cyl else "missing"),
                export_truth_mode=str(cyl.get("truth_mode") or ("full_mesh_allowed" if contract_complete else "axis_only_honesty_mode")),
                base_completeness_pct=float(base.get("completeness_pct") or 0.0),
                contract_complete=contract_complete,
                full_mesh_allowed=full_mesh_allowed,
                consumer_geometry_fabrication_allowed=fabrication,
                mismatch_status=mismatch,
                missing_advanced_fields=_safe_strings(cyl.get("advanced_fields_missing") or passport.get("missing_advanced_fields")),
                missing_geometry_fields=_safe_strings(cyl.get("missing_geometry_fields")),
                length_status_summary=length_summary,
            )
        )
    consumer_policy = dict(passport.get("consumer_policy") or passport.get("policy") or {}) if isinstance(passport.get("consumer_policy") or passport.get("policy"), Mapping) else {}
    fabrication_allowed = bool(consumer_policy.get("consumer_geometry_fabrication_allowed", False))
    if fabrication_allowed:
        warnings.append("Packaging consumer policy allows geometry fabrication; this violates Reference Center truth policy.")
    mismatch_rows = [row for row in rows if row.mismatch_status != "match"]
    if mismatch_rows:
        warnings.append("Base/reference packaging differs from export/runtime passport for: " + ", ".join(row.cylinder for row in mismatch_rows))
    return PackagingPassportEvidenceSnapshot(
        artifact_status=artifact_status,
        source_label=source_label,
        passport_path=raw_path,
        schema=str(passport.get("schema") or ""),
        packaging_status=str(passport.get("packaging_status") or passport.get("status") or ""),
        packaging_contract_hash=str(passport.get("packaging_contract_hash") or ""),
        mismatch_status="mismatch" if mismatch_rows else ("missing" if not passport else "match"),
        complete_cylinders=_safe_strings(passport.get("complete_cylinders")),
        axis_only_cylinders=_safe_strings(passport.get("axis_only_cylinders")),
        missing_advanced_fields=_safe_strings(passport.get("missing_advanced_fields")),
        consumer_geometry_fabrication_allowed=fabrication_allowed,
        warnings=tuple(dict.fromkeys(warnings)),
        rows=tuple(rows),
    )


def build_geometry_reference_diagnostics_handoff(
    *,
    artifact_context: ArtifactReferenceContext,
    component_rows: tuple[ComponentPassportCatalogRow, ...],
    road_width: RoadWidthEvidence,
    packaging: PackagingPassportEvidenceSnapshot,
    acceptance: GeometryAcceptanceEvidenceSnapshot,
) -> dict[str, Any]:
    missing: list[str] = []
    if artifact_context.status in {"missing", "stale"}:
        missing.append("artifact_context")
    if road_width.status == "missing":
        missing.append("road_width_m")
    if packaging.mismatch_status == "missing":
        missing.append("cylinder_packaging_passport")
    if acceptance.gate == "MISSING":
        missing.append("geometry_acceptance")
    producer_artifact_status = "ready"
    if artifact_context.status in {"missing", "stale"}:
        producer_artifact_status = "missing"
    elif (
        acceptance.gate != "PASS"
        or packaging.packaging_status != "complete"
        or packaging.mismatch_status != "match"
    ):
        producer_artifact_status = "partial"
    return {
        "schema": "geometry_reference_evidence.v1",
        "producer_owned": False,
        "reference_center_role": "reader_and_evidence_surface",
        "does_not_render_animator_meshes": True,
        "producer_evidence_owner": GEOMETRY_REFERENCE_PRODUCER_EVIDENCE_OWNER,
        "producer_artifact_status": producer_artifact_status,
        "producer_required_artifacts": list(GEOMETRY_REFERENCE_REQUIRED_PRODUCER_ARTIFACTS),
        "producer_next_action": GEOMETRY_REFERENCE_PRODUCER_NEXT_ACTION,
        "reference_center_can_close_producer_gaps": False,
        "consumer_may_fabricate_geometry": False,
        "artifact_status": artifact_context.status,
        "artifact_source_label": artifact_context.source_label,
        "artifact_npz_path": artifact_context.npz_path,
        "artifact_pointer_path": artifact_context.pointer_path,
        "updated_utc": artifact_context.updated_utc,
        "road_width_status": road_width.status,
        "road_width_source": road_width.preferred_source,
        "road_width_effective_m": road_width.effective_road_width_m,
        "packaging_status": packaging.packaging_status,
        "packaging_contract_hash": packaging.packaging_contract_hash,
        "packaging_mismatch_status": packaging.mismatch_status,
        "packaging_axis_only_cylinders": list(packaging.axis_only_cylinders),
        "geometry_acceptance_gate": acceptance.gate,
        "geometry_acceptance_available": acceptance.available,
        "component_passport_components": len(component_rows),
        "component_passport_needs_data": sum(1 for row in component_rows if row.status != "ok"),
        "evidence_missing": list(dict.fromkeys(missing)),
    }


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
        raw_values: dict[str, Any] = {
            "bore_diameter_m": normalized_base.get(cylinder_family_key("bore", cyl, axle)),
            "rod_diameter_m": normalized_base.get(cylinder_family_key("rod", cyl, axle)),
            "stroke_m": normalized_base.get(cylinder_family_key("stroke", cyl, axle)),
        }
        for field in (
            "outer_diameter_m",
            "dead_cap_length_m",
            "dead_rod_length_m",
            "dead_height_m",
            "body_length_m",
            *CYLINDER_PACKAGING_ADVANCED_FIELDS,
        ):
            raw_values[field] = normalized_base.get(cylinder_packaging_passport_key(field, cyl, axle))
        present_fields = tuple(
            field for field in CYLINDER_PACKAGING_REQUIRED_FIELDS if _is_positive_finite(raw_values.get(field))
        )
        missing_fields = tuple(
            field for field in CYLINDER_PACKAGING_REQUIRED_FIELDS if field not in present_fields
        )
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
        if missing_fields:
            notes.append("packaging passport incomplete")
        if math.isfinite(body_length_gap_mm):
            if body_length_gap_mm < -0.5:
                notes.append("body меньше stroke+dead")
            elif body_length_gap_mm > 5.0:
                notes.append("body с запасом к stroke+dead")
            else:
                notes.append("body ~= stroke+dead")

        completeness_pct = (
            float(len(present_fields)) / float(len(CYLINDER_PACKAGING_REQUIRED_FIELDS)) * 100.0
            if CYLINDER_PACKAGING_REQUIRED_FIELDS
            else 0.0
        )
        body_conflict = math.isfinite(body_length_gap_mm) and body_length_gap_mm < -0.5
        if not present_fields:
            status = "unavailable"
            truth_state = TRUTH_STATE_UNAVAILABLE
        elif not missing_fields and not body_conflict:
            status = "complete"
            truth_state = TRUTH_STATE_SOURCE_DATA_CONFIRMED
        elif body_conflict:
            status = "inconsistent"
            truth_state = TRUTH_STATE_APPROXIMATE
        else:
            status = "axis_only"
            truth_state = TRUTH_STATE_APPROXIMATE
        hidden_elements = () if status == "complete" else ("body", "rod", "piston", "gland")
        explanation = (
            "Packaging passport complete: source-data body/rod/piston/gland dimensions are present."
            if status == "complete"
            else (
                "Packaging passport is incomplete or inconsistent, so visual consumers must stay in "
                "axis-only honesty mode. Missing fields: "
                + (", ".join(missing_fields) if missing_fields else "none")
                + "."
            )
        )

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
                status=status,
                truth_state=truth_state,
                completeness_pct=float(completeness_pct),
                missing_fields=missing_fields,
                hidden_elements=hidden_elements,
                passport_id=f"cylinder_packaging::{canonical_cylinder_slug(cyl)}::{canonical_axle_slug(axle)}",
                explanation=explanation,
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
    road_width_row = _build_road_width_parameter_guide_row(normalized_base)
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
        family_rows = (*_build_family_parameter_guide_rows(normalized_base), road_width_row)
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
    rows.append(road_width_row)
    return tuple(rows[: max(1, int(limit))])


def _build_road_width_parameter_guide_row(
    base_payload: Mapping[str, Any],
) -> ParameterGuideRow:
    reference = build_road_width_reference(base_payload)
    current = (
        f"{reference.effective_road_width_m:.3f} {reference.unit_label} ({reference.status})"
        if math.isfinite(reference.effective_road_width_m)
        else f"— ({reference.status})"
    )
    return ParameterGuideRow(
        key=reference.parameter_key,
        label=reference.label,
        unit_label=reference.unit_label,
        section_title="Справочные данные",
        description=reference.explanation,
        display=f"{reference.label} — GAP-008 road_width_m",
        current_value_text=current,
    )


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
    "COMPONENT_PASSPORT_JSON",
    "CYLINDER_PACKAGING_ADVANCED_FIELDS",
    "CYLINDER_PACKAGING_BASIC_FIELDS",
    "CYLINDER_PACKAGING_REQUIRED_FIELDS",
    "REFERENCE_GUIDE_SECTION_TITLES",
    "ATM_PA",
    "TRUTH_STATE_APPROXIMATE",
    "TRUTH_STATE_SOURCE_DATA_CONFIRMED",
    "TRUTH_STATE_UNAVAILABLE",
    "ArtifactReferenceContext",
    "CylinderCatalogRow",
    "CylinderForceBiasEstimate",
    "CylinderFamilyReferenceRow",
    "CylinderMatchRecommendation",
    "CylinderPackageReferenceRow",
    "CylinderPrechargeReferenceRow",
    "CylinderPressureEstimate",
    "ComponentPassportCatalogRow",
    "ComponentFitReferenceRow",
    "GeometryAcceptanceEvidenceRow",
    "GeometryAcceptanceEvidenceSnapshot",
    "GeometryFamilyReferenceRow",
    "GEOMETRY_REFERENCE_PRODUCER_EVIDENCE_OWNER",
    "GEOMETRY_REFERENCE_PRODUCER_NEXT_ACTION",
    "GEOMETRY_REFERENCE_REQUIRED_PRODUCER_ARTIFACTS",
    "GeometryReferenceSnapshot",
    "PackagingPassportEvidenceRow",
    "PackagingPassportEvidenceSnapshot",
    "ParameterGuideRow",
    "RoadWidthEvidence",
    "RoadWidthReference",
    "SpringFamilyReferenceRow",
    "SpringReferenceSnapshot",
    "build_artifact_reference_context",
    "build_geometry_acceptance_evidence_from_artifact",
    "build_geometry_acceptance_evidence",
    "build_current_cylinder_package_rows",
    "build_current_cylinder_precharge_rows",
    "build_current_cylinder_reference_rows",
    "build_current_spring_reference_snapshot",
    "build_cylinder_force_bias_estimate",
    "build_cylinder_match_recommendations",
    "build_cylinder_pressure_estimate",
    "build_component_fit_reference_rows",
    "build_geometry_reference_diagnostics_handoff",
    "build_geometry_reference_snapshot",
    "build_packaging_passport_evidence",
    "build_parameter_guide_rows",
    "build_road_width_evidence",
    "build_road_width_reference",
    "cylinder_packaging_passport_key",
    "load_camozzi_catalog_rows",
    "load_camozzi_stroke_options_mm",
    "load_component_passport_catalog_rows",
]
