"""pneumo_solver_ui.data_contract

ABSOLUTE LAW (summary)
---------------------
- **No invented parameters**: UI/Animator must not "guess" missing model outputs.
- **No aliases**: one parameter name == one meaning across the whole pipeline.
- **No silent compatibility bridges**: if legacy / wrong keys appear, we **log a warning**
  with a clear fix, but we do **not** rename them automatically.

Why so strict?
- Any auto-renaming ("speed_mps" -> "vx0_м_с") eventually becomes a quiet bug.
- If a module starts accepting multiple spellings, producers stop being fixed.

This module therefore provides **auditing** and **explicit contract validation** helpers only.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable, Mapping

import json
import math

# Pointer/meta schema identifiers used by NPZ bundles (desktop animator integration).
ANIM_POINTER_SCHEMA = "pneumo_npz_meta_pointer"
ANIM_META_SCHEMA = "pneumo_npz_meta"
# Currently we keep a single version string for both pointer and meta.
ANIM_LATEST_POINTER_SCHEMA_VERSION = "pneumo_npz_meta_v1"
ANIM_LATEST_META_SCHEMA_VERSION = "pneumo_npz_meta_v1"

# Canonical nested geometry container used by new NPZ meta_json.
# IMPORTANT:
#   - This is NOT a compatibility bridge.
#   - It is the single intended place for geometry metadata in new bundles.
CANONICAL_META_GEOMETRY_KEYS: tuple[str, ...] = (
    "wheelbase_m",
    "track_m",
    "wheel_radius_m",
    "wheel_radius_front_m",
    "wheel_radius_rear_m",
    "wheel_width_m",
    "wheel_width_front_m",
    "wheel_width_rear_m",
    "road_width_m",
    "frame_length_m",
    "frame_width_m",
    "frame_height_m",
    # Cylinder visual contract (optional, but canonical when present)
    "cyl1_bore_diameter_m",
    "cyl1_rod_diameter_m",
    "cyl2_bore_diameter_m",
    "cyl2_rod_diameter_m",
    "cyl1_stroke_front_m",
    "cyl1_stroke_rear_m",
    "cyl2_stroke_front_m",
    "cyl2_stroke_rear_m",
    "dead_volume_chamber_m3",
    "cylinder_wall_thickness_m",
    "cyl1_outer_diameter_m",
    "cyl2_outer_diameter_m",
    "cyl1_dead_cap_length_m",
    "cyl1_dead_rod_length_m",
    "cyl2_dead_cap_length_m",
    "cyl2_dead_rod_length_m",
    "cyl1_dead_height_m",
    "cyl2_dead_height_m",
    "cyl1_body_length_front_m",
    "cyl1_body_length_rear_m",
    "cyl2_body_length_front_m",
    "cyl2_body_length_rear_m",
)

REQUIRED_META_GEOMETRY_KEYS_MIN: tuple[str, ...] = (
    "wheelbase_m",
    "track_m",
)

# Optional fields allowed to be zero (visuals may disable them explicitly).
NONNEGATIVE_META_GEOMETRY_KEYS: frozenset[str] = frozenset(
    {
        "wheel_width_m",
        "wheel_width_front_m",
        "wheel_width_rear_m",
        "road_width_m",
        "dead_volume_chamber_m3",
        "cylinder_wall_thickness_m",
        "cyl1_dead_cap_length_m",
        "cyl1_dead_rod_length_m",
        "cyl2_dead_cap_length_m",
        "cyl2_dead_rod_length_m",
        "cyl1_dead_height_m",
        "cyl2_dead_height_m",
        "cyl1_body_length_front_m",
        "cyl1_body_length_rear_m",
        "cyl2_body_length_front_m",
        "cyl2_body_length_rear_m",
    }
)

LogFn = Callable[[str], None]


def dumps_meta_json(meta: Mapping[str, Any]) -> str:
    """Serialize *meta* to JSON for sidecar files.

    Must never crash the app: if an object is not JSON-serializable, we fall back to str().
    """

    def _default(o: Any) -> Any:
        # numpy scalars
        try:
            import numpy as _np  # type: ignore

            if isinstance(o, _np.generic):
                return o.item()
        except Exception:
            pass
        return str(o)

    return json.dumps(
        meta,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        default=_default,
    )


# NOTE:
# These legacy keys are kept **ONLY** to produce actionable warnings.
# They are NOT used for runtime renaming/migration.
LEGACY_KEY_SUGGESTIONS: dict[str, str] = {
    # speed
    "road_speed_mps": "vx0_м_с",
    "speed_mps": "vx0_м_с",
    "v0_м_с": "vx0_м_с",
    "скорость_м_с": "vx0_м_с",
    # road / profiles
    "road_profile_path": "road_csv",
    "road_profile_csv": "road_csv",
    # maneuvers
    "road_ay_csv": "axay_csv",
    "road_axay_csv": "axay_csv",
}

# Legacy/wrong keys that sometimes leak into meta_json.geometry.
LEGACY_GEOMETRY_KEY_SUGGESTIONS: dict[str, str] = {
    "база": "wheelbase_m",
    "база_м": "wheelbase_m",
    "колея": "track_m",
    "колея_м": "track_m",
    "радиус_колеса_м": "wheel_radius_m",
    "радиус_колеса_перед_м": "wheel_radius_front_m",
    "радиус_колеса_зад_м": "wheel_radius_rear_m",
    "ширина_рамы": "frame_width_m",
    "высота_рамы": "frame_height_m",
    "длина_рамы": "frame_length_m",
    "wheelbase": "wheelbase_m",
    "track": "track_m",
    "wheel_radius": "wheel_radius_m",
}

# Audit-only legacy df_main columns. No runtime renaming.
LEGACY_MAIN_COLUMN_SUGGESTIONS: dict[str, str] = {
    "vx_м_с": "скорость_vx_м_с",
    "v_м_с": "скорость_vx_м_с",
    "speed_m_s": "скорость_vx_м_с",
    "рыскание_yaw_рад": "yaw_рад",
    "yaw_rad": "yaw_рад",
    "psi_рад": "yaw_рад",
    "курс_рад": "yaw_рад",
    "рыскание_скорость_r_рад_с": "yaw_rate_рад_с",
    "yaw_rate_r_рад_с": "yaw_rate_рад_с",
    "psi_dot_рад_с": "yaw_rate_рад_с",
}

# Frame-corner geometry is canonicalized as `рама_угол_{corner}_*`.
# Legacy `рама_{corner}_*` / `рама_{corner}_vz|az_*` names are audit-only.
for _corner in ("ЛП", "ПП", "ЛЗ", "ПЗ"):
    LEGACY_MAIN_COLUMN_SUGGESTIONS[f"рама_{_corner}_z_м"] = f"рама_угол_{_corner}_z_м"
    LEGACY_MAIN_COLUMN_SUGGESTIONS[f"рама_{_corner}_v_м_с"] = f"рама_угол_{_corner}_v_м_с"
    LEGACY_MAIN_COLUMN_SUGGESTIONS[f"рама_{_corner}_a_м_с2"] = f"рама_угол_{_corner}_a_м_с2"
    LEGACY_MAIN_COLUMN_SUGGESTIONS[f"рама_{_corner}_vz_м_с"] = f"рама_угол_{_corner}_v_м_с"
    LEGACY_MAIN_COLUMN_SUGGESTIONS[f"рама_{_corner}_az_м_с2"] = f"рама_угол_{_corner}_a_м_с2"


def extract_geometry_meta(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of ``meta['geometry']`` if it is a dict.

    No mutation, no fallback guessing, no renaming.
    """
    if not isinstance(meta, Mapping):
        return {}
    geom = meta.get("geometry")
    if isinstance(geom, Mapping):
        return dict(geom)
    return {}


def _finite_float_or_none(x: Any) -> float | None:
    try:
        v = float(x)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return float(v)


def _emit(msg: str, log: LogFn | None) -> None:
    if log is None:
        return
    try:
        log(msg)
    except Exception:
        # Logging must never break the app.
        pass


def _pick_numeric_from_base(
    base: Mapping[str, Any],
    source_keys: tuple[str, ...],
    *,
    target_key: str,
    allow_zero: bool,
    log: LogFn | None = None,
) -> float | None:
    """Pick a numeric value from *base* by explicit canonical source keys only.

    Missing keys are silent. Present-but-invalid keys produce warnings.
    """
    for key in source_keys:
        if key not in base:
            continue
        raw = base.get(key)
        value = _finite_float_or_none(raw)
        if value is None:
            _emit(
                f"[contract] Base key '{key}' is present, but value {raw!r} for geometry '{target_key}' "
                "is not a finite number. Исправьте исходные данные.",
                log,
            )
            continue
        ok = value >= 0.0 if allow_zero else value > 0.0
        if ok:
            return float(value)
        _emit(
            f"[contract] Base key '{key}' is present, but value {value!r} for geometry '{target_key}' "
            f"must be {'>= 0' if allow_zero else '> 0'}.",
            log,
        )
    return None


def _dead_lengths_from_bore_rod_and_volume(
    *,
    bore_diameter_m: float | None,
    rod_diameter_m: float | None,
    dead_volume_m3: float | None,
    target_prefix: str,
    log: LogFn | None = None,
) -> dict[str, float]:
    """Return exact dead lengths derived from canonical chamber volume + areas.

    These lengths are part of the explicit cylinder packaging contract used by visual
    consumers. They are not guessed in the animator. When the physical inputs are
    missing or invalid, nothing is invented and the caller simply omits the keys.
    """
    bore = _finite_float_or_none(bore_diameter_m)
    rod = _finite_float_or_none(rod_diameter_m)
    dead = _finite_float_or_none(dead_volume_m3)
    if bore is None or rod is None or dead is None:
        return {}
    if bore <= 0.0 or rod <= 0.0 or dead < 0.0:
        return {}
    a_cap = math.pi * (0.5 * float(bore)) ** 2
    a_rod = a_cap - math.pi * (0.5 * float(rod)) ** 2
    if not (math.isfinite(a_cap) and a_cap > 0.0):
        return {}
    if not (math.isfinite(a_rod) and a_rod > 0.0):
        _emit(
            f"[contract] Cylinder '{target_prefix}' has invalid bore/rod combination for packaging contract: "
            f"bore={bore!r}, rod={rod!r}. Исправьте исходные данные.",
            log,
        )
        return {}
    return {
        f"{target_prefix}_dead_cap_length_m": float(max(0.0, dead) / a_cap),
        f"{target_prefix}_dead_rod_length_m": float(max(0.0, dead) / a_rod),
    }

def _dead_height_and_body_lengths_from_bore_stroke_dead_and_wall(
    *,
    bore_diameter_m: float | None,
    stroke_front_m: float | None,
    stroke_rear_m: float | None,
    dead_volume_m3: float | None,
    wall_thickness_m: float | None,
    target_prefix: str,
) -> dict[str, float]:
    """Return simplified cylinder body geometry accepted by the current project law.

    User-approved formula for the current contract layer:
      - dead height = dead_volume / piston_area
      - outer diameter = bore + 2 * wall_thickness (already exported elsewhere)
      - body length = stroke + 2 * dead_height + 2 * wall_thickness

    Piston thickness is intentionally treated as negligible here.
    """
    bore = _finite_float_or_none(bore_diameter_m)
    dead = _finite_float_or_none(dead_volume_m3)
    wall = _finite_float_or_none(wall_thickness_m)
    if bore is None or dead is None or wall is None:
        return {}
    if bore <= 0.0 or dead < 0.0 or wall < 0.0:
        return {}
    area = math.pi * (0.5 * float(bore)) ** 2
    if not (math.isfinite(area) and area > 1e-12):
        return {}
    dead_h = float(max(0.0, dead) / area)
    out = {f"{target_prefix}_dead_height_m": dead_h}
    sf = _finite_float_or_none(stroke_front_m)
    sr = _finite_float_or_none(stroke_rear_m)
    if sf is not None and sf > 0.0:
        out[f"{target_prefix}_body_length_front_m"] = float(sf + 2.0 * dead_h + 2.0 * wall)
    if sr is not None and sr > 0.0:
        out[f"{target_prefix}_body_length_rear_m"] = float(sr + 2.0 * dead_h + 2.0 * wall)
    return out


def build_geometry_meta_from_base(base: Mapping[str, Any] | None, *, log: LogFn | None = None) -> dict[str, float]:
    """Build canonical ``meta_json.geometry`` from canonical model/base parameters.

    Important:
    - source keys are read strictly from the current model/base contract;
    - no aliases are accepted here;
    - no defaults are invented;
    - missing optional fields are simply omitted.

    For animator/export-only supplementation (currently ``road_width_m`` from
    ``track_m`` + ``wheel_width_m`` when visual consumers would otherwise have to
    fall back at runtime), use :func:`supplement_animator_geometry_meta` explicitly
    at the export layer.
    """
    if not isinstance(base, Mapping):
        return {}

    out: dict[str, float] = {}

    wheelbase = _pick_numeric_from_base(base, ("база",), target_key="wheelbase_m", allow_zero=False, log=log)
    if wheelbase is not None:
        out["wheelbase_m"] = float(wheelbase)

    track = _pick_numeric_from_base(base, ("колея",), target_key="track_m", allow_zero=False, log=log)
    if track is not None:
        out["track_m"] = float(track)

    radius_front = _pick_numeric_from_base(
        base,
        ("радиус_колеса_перед_м", "радиус_колеса_м"),
        target_key="wheel_radius_front_m",
        allow_zero=False,
        log=log,
    )
    radius_rear = _pick_numeric_from_base(
        base,
        ("радиус_колеса_зад_м", "радиус_колеса_м"),
        target_key="wheel_radius_rear_m",
        allow_zero=False,
        log=log,
    )
    if radius_front is not None:
        out["wheel_radius_front_m"] = float(radius_front)
    if radius_rear is not None:
        out["wheel_radius_rear_m"] = float(radius_rear)
    if radius_front is not None and radius_rear is not None:
        if math.isclose(float(radius_front), float(radius_rear), rel_tol=0.0, abs_tol=1e-12):
            out["wheel_radius_m"] = float(radius_front)
    elif radius_front is not None:
        out["wheel_radius_m"] = float(radius_front)
    elif radius_rear is not None:
        out["wheel_radius_m"] = float(radius_rear)

    wheel_width = _pick_numeric_from_base(base, ("wheel_width_m",), target_key="wheel_width_m", allow_zero=True, log=log)
    if wheel_width is not None:
        out["wheel_width_m"] = float(wheel_width)

    wheel_width_front = _pick_numeric_from_base(
        base,
        ("wheel_width_front_m",),
        target_key="wheel_width_front_m",
        allow_zero=True,
        log=log,
    )
    wheel_width_rear = _pick_numeric_from_base(
        base,
        ("wheel_width_rear_m",),
        target_key="wheel_width_rear_m",
        allow_zero=True,
        log=log,
    )
    if wheel_width_front is not None:
        out["wheel_width_front_m"] = float(wheel_width_front)
    if wheel_width_rear is not None:
        out["wheel_width_rear_m"] = float(wheel_width_rear)

    road_width = _pick_numeric_from_base(base, ("road_width_m",), target_key="road_width_m", allow_zero=True, log=log)
    if road_width is not None:
        out["road_width_m"] = float(road_width)

    frame_length = _pick_numeric_from_base(base, ("длина_рамы",), target_key="frame_length_m", allow_zero=False, log=log)
    frame_width = _pick_numeric_from_base(base, ("ширина_рамы",), target_key="frame_width_m", allow_zero=False, log=log)
    frame_height = _pick_numeric_from_base(base, ("высота_рамы",), target_key="frame_height_m", allow_zero=False, log=log)
    if frame_length is not None:
        out["frame_length_m"] = float(frame_length)
    if frame_width is not None:
        out["frame_width_m"] = float(frame_width)
    if frame_height is not None:
        out["frame_height_m"] = float(frame_height)

    cyl1_bore = _pick_numeric_from_base(base, ("диаметр_поршня_Ц1",), target_key="cyl1_bore_diameter_m", allow_zero=False, log=log)
    cyl1_rod = _pick_numeric_from_base(base, ("диаметр_штока_Ц1",), target_key="cyl1_rod_diameter_m", allow_zero=False, log=log)
    cyl2_bore = _pick_numeric_from_base(base, ("диаметр_поршня_Ц2",), target_key="cyl2_bore_diameter_m", allow_zero=False, log=log)
    cyl2_rod = _pick_numeric_from_base(base, ("диаметр_штока_Ц2",), target_key="cyl2_rod_diameter_m", allow_zero=False, log=log)
    cyl1_stroke_front = _pick_numeric_from_base(base, ("ход_штока_Ц1_перед_м", "ход_штока"), target_key="cyl1_stroke_front_m", allow_zero=False, log=log)
    cyl1_stroke_rear = _pick_numeric_from_base(base, ("ход_штока_Ц1_зад_м", "ход_штока"), target_key="cyl1_stroke_rear_m", allow_zero=False, log=log)
    cyl2_stroke_front = _pick_numeric_from_base(base, ("ход_штока_Ц2_перед_м", "ход_штока"), target_key="cyl2_stroke_front_m", allow_zero=False, log=log)
    cyl2_stroke_rear = _pick_numeric_from_base(base, ("ход_штока_Ц2_зад_м", "ход_штока"), target_key="cyl2_stroke_rear_m", allow_zero=False, log=log)
    dead_vol = _pick_numeric_from_base(base, ("мёртвый_объём_камеры",), target_key="dead_volume_chamber_m3", allow_zero=True, log=log)
    wall_thickness = _pick_numeric_from_base(base, ("стенка_толщина_м",), target_key="cylinder_outer_diameter", allow_zero=False, log=log)
    cyl_packaging: dict[str, float] = {}
    if wall_thickness is not None:
        out["cylinder_wall_thickness_m"] = float(wall_thickness)
    if cyl1_bore is not None and wall_thickness is not None:
        cyl_packaging["cyl1_outer_diameter_m"] = float(cyl1_bore + 2.0 * wall_thickness)
    if cyl2_bore is not None and wall_thickness is not None:
        cyl_packaging["cyl2_outer_diameter_m"] = float(cyl2_bore + 2.0 * wall_thickness)
    cyl_packaging.update(
        _dead_lengths_from_bore_rod_and_volume(
            bore_diameter_m=cyl1_bore,
            rod_diameter_m=cyl1_rod,
            dead_volume_m3=dead_vol,
            target_prefix="cyl1",
            log=log,
        )
    )
    cyl_packaging.update(
        _dead_lengths_from_bore_rod_and_volume(
            bore_diameter_m=cyl2_bore,
            rod_diameter_m=cyl2_rod,
            dead_volume_m3=dead_vol,
            target_prefix="cyl2",
            log=log,
        )
    )
    cyl_packaging.update(
        _dead_height_and_body_lengths_from_bore_stroke_dead_and_wall(
            bore_diameter_m=cyl1_bore,
            stroke_front_m=cyl1_stroke_front,
            stroke_rear_m=cyl1_stroke_rear,
            dead_volume_m3=dead_vol,
            wall_thickness_m=wall_thickness,
            target_prefix="cyl1",
        )
    )
    cyl_packaging.update(
        _dead_height_and_body_lengths_from_bore_stroke_dead_and_wall(
            bore_diameter_m=cyl2_bore,
            stroke_front_m=cyl2_stroke_front,
            stroke_rear_m=cyl2_stroke_rear,
            dead_volume_m3=dead_vol,
            wall_thickness_m=wall_thickness,
            target_prefix="cyl2",
        )
    )
    if cyl1_bore is not None:
        out["cyl1_bore_diameter_m"] = float(cyl1_bore)
    if cyl1_rod is not None:
        out["cyl1_rod_diameter_m"] = float(cyl1_rod)
    if cyl2_bore is not None:
        out["cyl2_bore_diameter_m"] = float(cyl2_bore)
    if cyl2_rod is not None:
        out["cyl2_rod_diameter_m"] = float(cyl2_rod)
    if cyl1_stroke_front is not None:
        out["cyl1_stroke_front_m"] = float(cyl1_stroke_front)
    if cyl1_stroke_rear is not None:
        out["cyl1_stroke_rear_m"] = float(cyl1_stroke_rear)
    if cyl2_stroke_front is not None:
        out["cyl2_stroke_front_m"] = float(cyl2_stroke_front)
    if cyl2_stroke_rear is not None:
        out["cyl2_stroke_rear_m"] = float(cyl2_stroke_rear)
    if dead_vol is not None:
        out["dead_volume_chamber_m3"] = float(dead_vol)
    out.update(cyl_packaging)

    return out


def audit_legacy_keys(meta: Mapping[str, Any], *, log: LogFn | None = None) -> list[str]:
    """Scan *meta* for legacy top-level keys.

    Returns a list of human-readable warnings.

    Important:
    - This function does **not** change the input.
    - It exists to prevent silent bugs and to localize "expectation vs reality".
    """

    issues: list[str] = []

    if not meta:
        return issues

    for legacy, canonical in LEGACY_KEY_SUGGESTIONS.items():
        if legacy not in meta:
            continue

        if canonical in meta:
            msg = (
                f"[contract] Legacy meta key '{legacy}' is present вместе с canonical '{canonical}'. "
                "Это запрещено (двойное имя одного параметра). "
                f"Исправьте источник данных: оставьте только '{canonical}'."
            )
        else:
            msg = (
                f"[contract] Legacy meta key '{legacy}' is present. "
                "Авто-миграция запрещена. "
                f"Переименуйте ключ в источнике данных в '{canonical}'."
            )

        issues.append(msg)
        _emit(msg, log)

    return issues


def audit_geometry_meta(meta: Mapping[str, Any] | None, *, log: LogFn | None = None) -> list[str]:
    """Audit nested ``meta_json.geometry``.

    Only warnings, never renaming.
    """
    issues: list[str] = []
    if not isinstance(meta, Mapping):
        return issues

    if "geometry" in meta and not isinstance(meta.get("geometry"), Mapping):
        msg = "[contract] meta.geometry exists but is not an object/dict. Исправьте producer/exporter."
        issues.append(msg)
        _emit(msg, log)
        return issues

    geom = extract_geometry_meta(meta)
    if not geom:
        return issues

    for legacy, canonical in LEGACY_GEOMETRY_KEY_SUGGESTIONS.items():
        if legacy not in geom:
            continue
        if canonical in geom:
            msg = (
                f"[contract] meta.geometry contains legacy key '{legacy}' together with canonical '{canonical}'. "
                "Это запрещено. Удалите legacy key из producer/exporter."
            )
        else:
            msg = (
                f"[contract] meta.geometry contains legacy key '{legacy}'. "
                f"Авто-миграция запрещена. Используйте только '{canonical}'."
            )
        issues.append(msg)
        _emit(msg, log)

    for key in geom.keys():
        if key in CANONICAL_META_GEOMETRY_KEYS:
            continue
        if key in LEGACY_GEOMETRY_KEY_SUGGESTIONS:
            continue
        msg = (
            f"[contract] meta.geometry contains undeclared key '{key}'. "
            "Не вводите новые geometry-параметры без документирования и обновления реестра."
        )
        issues.append(msg)
        _emit(msg, log)

    return issues


def audit_main_columns(columns: Iterable[str] | None, *, log: LogFn | None = None) -> list[str]:
    """Scan df_main column names for forbidden aliases/duplicates.

    Only warnings, never renaming.
    """
    issues: list[str] = []
    cols = [str(c) for c in (columns or [])]
    if not cols:
        return issues

    counter = Counter(cols)
    for name, count in sorted(counter.items()):
        if count > 1:
            msg = (
                f"[contract] df_main contains duplicate column '{name}' ({count}x). "
                "Это запрещено: одно имя параметра должно встречаться ровно один раз."
            )
            issues.append(msg)
            _emit(msg, log)

    colset = set(cols)
    for legacy, canonical in LEGACY_MAIN_COLUMN_SUGGESTIONS.items():
        if legacy not in colset:
            continue
        if canonical in colset:
            msg = (
                f"[contract] df_main contains legacy column '{legacy}' together with canonical '{canonical}'. "
                "Это запрещено. Исправьте producer/exporter."
            )
        else:
            msg = (
                f"[contract] df_main contains legacy column '{legacy}'. "
                f"Авто-миграция запрещена. Используйте только '{canonical}'."
            )
        issues.append(msg)
        _emit(msg, log)

    return issues


def collect_geometry_contract_issues(
    meta: Mapping[str, Any] | None,
    *,
    require_nested: bool,
    require_required: bool = True,
    context: str = "meta_json",
    log: LogFn | None = None,
) -> list[str]:
    """Collect strict geometry-contract violations.

    This is stricter than :func:`audit_geometry_meta`:
    - can require nested ``meta_json.geometry`` to exist;
    - validates required keys and numeric ranges;
    - intended for pre-export / pre-load contract gates.
    """
    issues: list[str] = []

    if not isinstance(meta, Mapping):
        msg = f"[contract] {context} must be a mapping/dict."
        issues.append(msg)
        _emit(msg, log)
        return issues

    has_geometry_key = "geometry" in meta
    geometry_obj = meta.get("geometry")
    if require_nested and not has_geometry_key:
        msg = (
            f"[contract] {context} must contain nested object 'geometry' with required keys "
            f"{', '.join(REQUIRED_META_GEOMETRY_KEYS_MIN)}."
        )
        issues.append(msg)
        _emit(msg, log)
        return issues

    if has_geometry_key and not isinstance(geometry_obj, Mapping):
        msg = f"[contract] {context}.geometry must be an object/dict."
        issues.append(msg)
        _emit(msg, log)
        return issues

    geom = extract_geometry_meta(meta)
    if not geom:
        if require_nested:
            msg = f"[contract] {context}.geometry is empty. Bundle is not export/load ready."
            issues.append(msg)
            _emit(msg, log)
        return issues

    # Reuse audit warnings inside the strict collector too.
    for msg in audit_geometry_meta(meta, log=None):
        issues.append(msg)
        _emit(msg, log)

    if require_required:
        for key in REQUIRED_META_GEOMETRY_KEYS_MIN:
            if key not in geom:
                msg = f"[contract] {context}.geometry is missing required key '{key}'."
                issues.append(msg)
                _emit(msg, log)

    for key, raw in geom.items():
        if key not in CANONICAL_META_GEOMETRY_KEYS:
            continue
        value = _finite_float_or_none(raw)
        if value is None:
            msg = f"[contract] {context}.geometry['{key}']={raw!r} is not a finite number."
            issues.append(msg)
            _emit(msg, log)
            continue

        if key in NONNEGATIVE_META_GEOMETRY_KEYS:
            ok = value >= 0.0
            bound_txt = ">= 0"
        else:
            ok = value > 0.0
            bound_txt = "> 0"
        if not ok:
            msg = f"[contract] {context}.geometry['{key}']={value!r} must be {bound_txt}."
            issues.append(msg)
            _emit(msg, log)

    return issues


def _first_finite_geometry_value(
    geom: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    allow_zero: bool,
) -> float | None:
    """Pick the first finite canonical geometry value from ``geom``.

    The input is assumed to be already audited. This helper never invents defaults
    and never reads from legacy / top-level / base keys.
    """
    for key in keys:
        if key not in geom:
            continue
        value = _finite_float_or_none(geom.get(key))
        if value is None:
            continue
        ok = value >= 0.0 if allow_zero else value > 0.0
        if ok:
            return float(value)
    return None


def read_visual_geometry_meta(
    meta: Mapping[str, Any] | None,
    *,
    context: str,
    log: LogFn | None = None,
) -> dict[str, Any]:
    """Read geometry for visual consumers strictly from nested ``meta_json.geometry``.

    Important:
    - Visual consumers must not fall back to top-level meta keys, ``base``/``base_override``
      provenance, or ``default_base.json``.
    - Missing data stays missing and must be surfaced via warnings/self-checks.
    - ``road_width_m`` may still be derived later by the consumer as SERVICE/DERIVED from
      canonical values that are present in nested geometry.

    Returns a plain dict with canonical visual geometry values (or ``None`` when absent)
    plus two lists:
      - ``issues``: strict nested-geometry contract violations
      - ``warnings``: non-fatal suspicious situations (e.g. ignored top-level duplicates)
    """
    meta_dict = dict(meta or {})
    issues = collect_geometry_contract_issues(
        meta_dict,
        require_nested=True,
        require_required=True,
        context=context,
        log=log,
    )

    geom = extract_geometry_meta(meta_dict)
    warnings: list[str] = []
    seen: set[str] = set()

    def _warn(msg: str) -> None:
        if msg in seen:
            return
        seen.add(msg)
        warnings.append(msg)
        _emit(msg, log)

    # Top-level canonical geometry is intentionally ignored by visual consumers.
    # If it is present, we surface it explicitly instead of silently using it.
    for key in CANONICAL_META_GEOMETRY_KEYS:
        if key not in meta_dict:
            continue
        top_value = _finite_float_or_none(meta_dict.get(key))
        nested_has_key = key in geom
        nested_value = _finite_float_or_none(geom.get(key)) if nested_has_key else None

        if not nested_has_key:
            _warn(
                f"[contract] {context} contains top-level geometry key '{key}', but visual consumers "
                f"read only nested 'geometry.{key}'. Top-level value is ignored."
            )
            continue

        if top_value is None or nested_value is None:
            _warn(
                f"[contract] {context} duplicates geometry key '{key}' at top-level and in nested geometry. "
                "Visual consumers use nested geometry only."
            )
            continue

        if not math.isclose(float(top_value), float(nested_value), rel_tol=0.0, abs_tol=1e-12):
            _warn(
                f"[contract] {context} has conflicting top-level '{key}'={top_value!r} and "
                f"nested geometry['{key}']={nested_value!r}. Visual consumers use nested geometry only."
            )
        else:
            _warn(
                f"[contract] {context} duplicates canonical geometry key '{key}' at top-level and in nested geometry. "
                "Visual consumers use nested geometry only; remove the top-level duplicate."
            )

    wheelbase = _first_finite_geometry_value(geom, ("wheelbase_m",), allow_zero=False)
    track = _first_finite_geometry_value(geom, ("track_m",), allow_zero=False)
    wheel_radius = _first_finite_geometry_value(
        geom,
        ("wheel_radius_m", "wheel_radius_front_m", "wheel_radius_rear_m"),
        allow_zero=False,
    )
    wheel_width = _first_finite_geometry_value(
        geom,
        ("wheel_width_m", "wheel_width_front_m", "wheel_width_rear_m"),
        allow_zero=True,
    )
    road_width = _first_finite_geometry_value(geom, ("road_width_m",), allow_zero=False)
    frame_length = _first_finite_geometry_value(geom, ("frame_length_m",), allow_zero=False)
    frame_width = _first_finite_geometry_value(geom, ("frame_width_m",), allow_zero=False)
    frame_height = _first_finite_geometry_value(geom, ("frame_height_m",), allow_zero=False)
    cyl1_bore = _first_finite_geometry_value(geom, ("cyl1_bore_diameter_m",), allow_zero=False)
    cyl1_rod = _first_finite_geometry_value(geom, ("cyl1_rod_diameter_m",), allow_zero=False)
    cyl2_bore = _first_finite_geometry_value(geom, ("cyl2_bore_diameter_m",), allow_zero=False)
    cyl2_rod = _first_finite_geometry_value(geom, ("cyl2_rod_diameter_m",), allow_zero=False)
    cyl1_stroke_front = _first_finite_geometry_value(geom, ("cyl1_stroke_front_m",), allow_zero=False)
    cyl1_stroke_rear = _first_finite_geometry_value(geom, ("cyl1_stroke_rear_m",), allow_zero=False)
    cyl2_stroke_front = _first_finite_geometry_value(geom, ("cyl2_stroke_front_m",), allow_zero=False)
    cyl2_stroke_rear = _first_finite_geometry_value(geom, ("cyl2_stroke_rear_m",), allow_zero=False)
    dead_volume = _first_finite_geometry_value(geom, ("dead_volume_chamber_m3",), allow_zero=True)
    cyl1_outer = _first_finite_geometry_value(geom, ("cyl1_outer_diameter_m",), allow_zero=False)
    cyl2_outer = _first_finite_geometry_value(geom, ("cyl2_outer_diameter_m",), allow_zero=False)
    cyl1_dead_cap = _first_finite_geometry_value(geom, ("cyl1_dead_cap_length_m",), allow_zero=True)
    cyl1_dead_rod = _first_finite_geometry_value(geom, ("cyl1_dead_rod_length_m",), allow_zero=True)
    cyl2_dead_cap = _first_finite_geometry_value(geom, ("cyl2_dead_cap_length_m",), allow_zero=True)
    cyl2_dead_rod = _first_finite_geometry_value(geom, ("cyl2_dead_rod_length_m",), allow_zero=True)
    wall_thickness = _first_finite_geometry_value(geom, ("cylinder_wall_thickness_m",), allow_zero=True)
    cyl1_dead_height = _first_finite_geometry_value(geom, ("cyl1_dead_height_m",), allow_zero=True)
    cyl2_dead_height = _first_finite_geometry_value(geom, ("cyl2_dead_height_m",), allow_zero=True)
    cyl1_body_front = _first_finite_geometry_value(geom, ("cyl1_body_length_front_m",), allow_zero=True)
    cyl1_body_rear = _first_finite_geometry_value(geom, ("cyl1_body_length_rear_m",), allow_zero=True)
    cyl2_body_front = _first_finite_geometry_value(geom, ("cyl2_body_length_front_m",), allow_zero=True)
    cyl2_body_rear = _first_finite_geometry_value(geom, ("cyl2_body_length_rear_m",), allow_zero=True)

    return {
        "wheelbase_m": wheelbase,
        "track_m": track,
        "wheel_radius_m": wheel_radius,
        "wheel_width_m": wheel_width,
        "road_width_m": road_width,
        "frame_length_m": frame_length,
        "frame_width_m": frame_width,
        "frame_height_m": frame_height,
        "cyl1_bore_diameter_m": cyl1_bore,
        "cyl1_rod_diameter_m": cyl1_rod,
        "cyl2_bore_diameter_m": cyl2_bore,
        "cyl2_rod_diameter_m": cyl2_rod,
        "cyl1_stroke_front_m": cyl1_stroke_front,
        "cyl1_stroke_rear_m": cyl1_stroke_rear,
        "cyl2_stroke_front_m": cyl2_stroke_front,
        "cyl2_stroke_rear_m": cyl2_stroke_rear,
        "dead_volume_chamber_m3": dead_volume,
        "cyl1_outer_diameter_m": cyl1_outer,
        "cyl2_outer_diameter_m": cyl2_outer,
        "cyl1_dead_cap_length_m": cyl1_dead_cap,
        "cyl1_dead_rod_length_m": cyl1_dead_rod,
        "cyl2_dead_cap_length_m": cyl2_dead_cap,
        "cyl2_dead_rod_length_m": cyl2_dead_rod,
        "cylinder_wall_thickness_m": wall_thickness,
        "cyl1_dead_height_m": cyl1_dead_height,
        "cyl2_dead_height_m": cyl2_dead_height,
        "cyl1_body_length_front_m": cyl1_body_front,
        "cyl1_body_length_rear_m": cyl1_body_rear,
        "cyl2_body_length_front_m": cyl2_body_front,
        "cyl2_body_length_rear_m": cyl2_body_rear,
        "issues": issues,
        "warnings": warnings,
    }


def assert_required_geometry_meta(
    meta: Mapping[str, Any] | None,
    *,
    context: str,
    log: LogFn | None = None,
    require_nested: bool = True,
) -> dict[str, Any]:
    """Validate required geometry contract and raise ``ValueError`` on violations.

    Returns a plain ``dict`` copy when contract is satisfied.
    """
    out = dict(meta or {})
    issues = collect_geometry_contract_issues(
        out,
        require_nested=require_nested,
        require_required=True,
        context=context,
        log=log,
    )
    if issues:
        raise ValueError(f"{context}: " + " | ".join(issues))
    return out


def supplement_animator_geometry_meta(
    geom: Mapping[str, Any] | None,
    *,
    log: LogFn | None = None,
) -> dict[str, float]:
    """Return export-ready animator geometry without consumer-side road-width fallback.

    This helper is intentionally **not** part of the strict base->geometry builder.
    It exists for exporter/UI call-sites that already produced canonical nested
    ``meta_json.geometry`` and want to persist an explicit visual road width instead of
    forcing Desktop Animator to re-derive it at runtime and warn in every SEND bundle.

    Current policy:
    - preserve existing canonical geometry values as-is;
    - if ``road_width_m`` is missing or non-positive, and ``track_m`` is known, derive
      a visual road width from ``track_m + wheel_width_m`` (never narrower than track);
    - do nothing when even ``track_m`` is unavailable.
    """
    if not isinstance(geom, Mapping):
        return {}

    out: dict[str, float] = {}
    for key, value in geom.items():
        if str(key) not in CANONICAL_META_GEOMETRY_KEYS:
            continue
        try:
            if isinstance(value, bool):
                continue
            fv = float(value)
        except Exception:
            continue
        if math.isfinite(fv):
            out[str(key)] = float(fv)

    road_width = float(out.get("road_width_m", 0.0) or 0.0)
    if road_width > 0.0:
        return out

    track = float(out.get("track_m", 0.0) or 0.0)
    if track <= 0.0:
        return out

    wheel_width = 0.0
    for key in ("wheel_width_m", "wheel_width_front_m", "wheel_width_rear_m"):
        raw = out.get(key)
        if raw is None:
            continue
        try:
            candidate = float(raw)
        except Exception:
            continue
        if math.isfinite(candidate):
            wheel_width = max(0.0, candidate)
            break

    derived = float(max(track, track + max(0.0, wheel_width)))
    out["road_width_m"] = derived
    if log is not None:
        log(
            "[contract] animator export supplemented geometry['road_width_m']="            f"{derived:.6g} m from track_m + wheel_width_m to avoid runtime derived-road-width fallback."
        )
    return out


def normalize_npz_meta(meta: Mapping[str, Any] | None, *, log: LogFn | None = None) -> dict[str, Any]:
    """Return meta as a plain dict and audit it.

    Despite the historical name, this function is intentionally **NOT** doing any
    normalization/renaming. It only audits for legacy keys and returns a copy.
    """

    out = dict(meta or {})
    audit_legacy_keys(out, log=log)
    audit_geometry_meta(out, log=log)
    return out
