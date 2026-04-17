from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .desktop_input_model import describe_desktop_inputs_handoff_for_workspace
from .scenario_ring import (
    _resolve_initial_speed_kph,
    _segment_length_canonical_m,
    _segment_motion_contract,
)


TURN_DIRECTIONS = ("STRAIGHT", "LEFT", "RIGHT")
ROAD_MODES = ("ISO8608", "SINE")
ISO_CLASSES = tuple("ABCDEFGH")
GD_PICKS = ("lower", "mid", "upper")
EVENT_KINDS = ("яма", "препятствие")
EVENT_SIDES = ("left", "right", "both")
CLOSURE_POLICIES = ("closed_c1_periodic", "closed_exact", "strict_exact", "preview_open_only")
PASSAGE_MODES = ("steady", "accel", "brake", "custom")

RING_PRESET_DEFAULT_KEY = "Demo: mixed ISO+SINE"
SEGMENT_PRESET_DEFAULT_KEY = "Straight ISO cruise"


@dataclass(frozen=True)
class PresetPresentation:
    title_ru: str
    hint_ru: str = ""


RING_PRESET_DEFAULT = "Демо: смешанное ISO 8608 и синусоида"
SEGMENT_PRESET_DEFAULT = "Прямой участок ISO 8608"


def new_uid() -> str:
    return uuid.uuid4().hex[:8]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _turn_label(value: object) -> str:
    return {
        "STRAIGHT": "Прямо",
        "LEFT": "Влево",
        "RIGHT": "Вправо",
    }.get(str(value or "").upper(), str(value or ""))


def _road_mode_label(value: object) -> str:
    return {
        "ISO8608": "ISO 8608",
        "SINE": "Синусоида",
    }.get(str(value or "").upper(), str(value or ""))


def _passage_mode_label(value: object) -> str:
    return {
        "steady": "постоянный",
        "accel": "разгон",
        "brake": "торможение",
        "custom": "пользовательский",
    }.get(str(value or "").lower(), str(value or ""))


def build_default_iso_road(*, seed: int = 12345) -> dict[str, Any]:
    return {
        "mode": "ISO8608",
        "center_height_start_mm": 0.0,
        "center_height_end_mm": 0.0,
        "cross_slope_start_pct": 0.0,
        "cross_slope_end_pct": 0.0,
        "iso_class": "E",
        "gd_pick": "mid",
        "gd_n0_scale": 1.0,
        "waviness_w": 2.0,
        "left_right_coherence": 0.5,
        "seed": int(seed),
    }


def build_default_sine_road() -> dict[str, Any]:
    return {
        "mode": "SINE",
        "center_height_start_mm": 0.0,
        "center_height_end_mm": 0.0,
        "cross_slope_start_pct": 0.0,
        "cross_slope_end_pct": 0.0,
        "aL_mm": 50.0,
        "aR_mm": 50.0,
        "lambdaL_m": 1.5,
        "lambdaR_m": 1.5,
        "phaseL_deg": 0.0,
        "phaseR_deg": 180.0,
        "rand_aL": False,
        "rand_aL_p": 0.5,
        "rand_aL_lo_mm": 4.0,
        "rand_aL_hi_mm": 4.0,
        "rand_aR": False,
        "rand_aR_p": 0.5,
        "rand_aR_lo_mm": 4.0,
        "rand_aR_hi_mm": 4.0,
        "rand_lL": False,
        "rand_lL_p": 0.5,
        "rand_lL_lo_m": 2.5,
        "rand_lL_hi_m": 2.5,
        "rand_lR": False,
        "rand_lR_p": 0.5,
        "rand_lR_lo_m": 2.5,
        "rand_lR_hi_m": 2.5,
        "rand_pL": True,
        "rand_pL_p": 0.5,
        "rand_pL_lo_deg": 0.0,
        "rand_pL_hi_deg": 360.0,
        "rand_pR": True,
        "rand_pR_p": 0.5,
        "rand_pR_lo_deg": 0.0,
        "rand_pR_hi_deg": 360.0,
    }


def build_blank_event() -> dict[str, Any]:
    return {
        "kind": "яма",
        "side": "left",
        "start_m": 0.0,
        "length_m": 0.4,
        "depth_mm": -25.0,
        "ramp_m": 0.1,
    }


def build_blank_segment(*, name: str = "Новый сегмент", seed: int = 12345) -> dict[str, Any]:
    return {
        "uid": new_uid(),
        "name": name,
        "duration_s": 3.0,
        "turn_direction": "STRAIGHT",
        "passage_mode": "steady",
        "speed_end_kph": 40.0,
        "road": build_default_iso_road(seed=seed),
        "events": [],
    }


def ensure_segment_uids(segments: list[dict[str, Any]]) -> None:
    used: set[str] = set()
    for segment in segments:
        uid = str(segment.get("uid") or "")
        if (not uid) or (uid in used):
            uid = new_uid()
            segment["uid"] = uid
        used.add(uid)


def ensure_road_defaults(segment: dict[str, Any]) -> dict[str, Any]:
    road = dict(segment.get("road", {}) or {})
    mode = str(road.get("mode", "ISO8608") or "ISO8608").upper()
    if mode == "SINE":
        defaults = build_default_sine_road()
    else:
        defaults = build_default_iso_road(seed=safe_int(road.get("seed", 12345), 12345))
        mode = "ISO8608"
    merged = dict(defaults)
    merged.update(road)
    merged["mode"] = mode
    segment["road"] = merged
    segment["events"] = list(segment.get("events", []) or [])
    return merged


def normalize_spec(spec: dict[str, Any] | None) -> dict[str, Any]:
    base = build_default_ring_spec()
    if not isinstance(spec, dict):
        return base

    merged = dict(base)
    merged.update(spec)
    merged["schema_version"] = str(spec.get("schema_version", "ring_v2") or "ring_v2")
    merged["closure_policy"] = str(spec.get("closure_policy", base["closure_policy"]) or base["closure_policy"])
    merged["v0_kph"] = safe_float(spec.get("v0_kph", base["v0_kph"]), base["v0_kph"])
    merged["seed"] = safe_int(spec.get("seed", base["seed"]), base["seed"])
    merged["dx_m"] = safe_float(spec.get("dx_m", base["dx_m"]), base["dx_m"])
    merged["dt_s"] = safe_float(spec.get("dt_s", base["dt_s"]), base["dt_s"])
    merged["n_laps"] = max(1, safe_int(spec.get("n_laps", base["n_laps"]), base["n_laps"]))
    merged["wheelbase_m"] = safe_float(spec.get("wheelbase_m", base["wheelbase_m"]), base["wheelbase_m"])
    merged["track_m"] = safe_float(spec.get("track_m", base["track_m"]), base["track_m"])

    segments_raw = list(spec.get("segments", []) or [])
    segments: list[dict[str, Any]] = []
    for idx, segment in enumerate(segments_raw):
        if not isinstance(segment, dict):
            continue
        normalized = copy.deepcopy(segment)
        normalized.setdefault("name", f"S{idx + 1}")
        normalized.setdefault("duration_s", 3.0)
        normalized.setdefault("turn_direction", "STRAIGHT")
        normalized.setdefault("passage_mode", "steady")
        normalized.setdefault("speed_end_kph", safe_float(segment.get("speed_kph", 40.0), 40.0))
        ensure_road_defaults(normalized)
        segments.append(normalized)
    if not segments:
        segments = list(base["segments"])
    ensure_segment_uids(segments)
    merged["segments"] = segments
    return merged


def build_default_ring_spec() -> dict[str, Any]:
    spec = {
        "schema_version": "ring_v2",
        "closure_policy": "closed_c1_periodic",
        "v0_kph": 40.0,
        "seed": 123,
        "dx_m": 0.02,
        "dt_s": 0.01,
        "n_laps": 1,
        "wheelbase_m": 1.5,
        "track_m": 1.0,
        "segments": [
            {
                "uid": new_uid(),
                "name": "S1_прямо",
                "duration_s": 5.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "steady",
                "speed_end_kph": 40.0,
                "road": build_default_iso_road(seed=12345),
                "events": [
                    {
                        "kind": "яма",
                        "side": "left",
                        "start_m": 8.0,
                        "length_m": 0.6,
                        "depth_mm": -35.0,
                        "ramp_m": 0.15,
                    },
                    {
                        "kind": "препятствие",
                        "side": "both",
                        "start_m": 14.0,
                        "length_m": 0.35,
                        "depth_mm": 25.0,
                        "ramp_m": 0.08,
                    },
                ],
            },
            {
                "uid": new_uid(),
                "name": "S2_поворот",
                "duration_s": 4.0,
                "turn_direction": "LEFT",
                "passage_mode": "steady",
                "speed_end_kph": 40.0,
                "turn_radius_m": 60.0,
                "road": build_default_sine_road(),
                "events": [],
            },
            {
                "uid": new_uid(),
                "name": "S3_прямо_55",
                "duration_s": 3.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "accel",
                "speed_end_kph": 55.0,
                "road": build_default_iso_road(seed=54321),
                "events": [],
            },
            {
                "uid": new_uid(),
                "name": "S4_замыкание",
                "duration_s": 3.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "brake",
                "speed_end_kph": 40.0,
                "road": build_default_iso_road(seed=999),
                "events": [],
            },
        ],
    }
    ensure_segment_uids(spec["segments"])
    return spec


def _segment_preset_straight_iso(*, seed: int) -> dict[str, Any]:
    return {
        "uid": new_uid(),
        "name": "Прямой участок ISO",
        "duration_s": 4.0,
        "turn_direction": "STRAIGHT",
        "passage_mode": "steady",
        "speed_end_kph": 45.0,
        "road": {
            **build_default_iso_road(seed=seed + 101),
            "iso_class": "D",
            "gd_pick": "mid",
        },
        "events": [],
    }


def _segment_preset_left_sine(*, seed: int) -> dict[str, Any]:
    _ = seed
    return {
        "uid": new_uid(),
        "name": "Левый поворот, синусоида",
        "duration_s": 4.0,
        "turn_direction": "LEFT",
        "passage_mode": "steady",
        "speed_end_kph": 38.0,
        "turn_radius_m": 55.0,
        "road": {
            **build_default_sine_road(),
            "aL_mm": 40.0,
            "aR_mm": 36.0,
            "lambdaL_m": 1.8,
            "lambdaR_m": 1.8,
            "phaseL_deg": 0.0,
            "phaseR_deg": 140.0,
        },
        "events": [],
    }


def _segment_preset_brake_rough(*, seed: int) -> dict[str, Any]:
    return {
        "uid": new_uid(),
        "name": "Торможение на грубом ISO",
        "duration_s": 3.5,
        "turn_direction": "STRAIGHT",
        "passage_mode": "brake",
        "speed_end_kph": 20.0,
        "road": {
            **build_default_iso_road(seed=seed + 202),
            "iso_class": "G",
            "gd_pick": "upper",
            "gd_n0_scale": 1.25,
            "left_right_coherence": 0.35,
        },
        "events": [
            {
                "kind": "яма",
                "side": "left",
                "start_m": 5.5,
                "length_m": 0.5,
                "depth_mm": -30.0,
                "ramp_m": 0.12,
            }
        ],
    }


def _segment_preset_obstacle_both(*, seed: int) -> dict[str, Any]:
    return {
        "uid": new_uid(),
        "name": "Участок с препятствиями",
        "duration_s": 3.0,
        "turn_direction": "STRAIGHT",
        "passage_mode": "steady",
        "speed_end_kph": 30.0,
        "road": {
            **build_default_iso_road(seed=seed + 303),
            "iso_class": "E",
            "gd_pick": "mid",
        },
        "events": [
            {
                "kind": "препятствие",
                "side": "both",
                "start_m": 4.0,
                "length_m": 0.35,
                "depth_mm": 22.0,
                "ramp_m": 0.08,
            },
            {
                "kind": "яма",
                "side": "right",
                "start_m": 7.0,
                "length_m": 0.45,
                "depth_mm": -25.0,
                "ramp_m": 0.1,
            },
        ],
    }


SEGMENT_PRESET_BUILDERS: dict[str, Any] = {
    "Straight ISO cruise": _segment_preset_straight_iso,
    "Left turn sine": _segment_preset_left_sine,
    "Brake rough ISO": _segment_preset_brake_rough,
    "Obstacle stress": _segment_preset_obstacle_both,
}

SEGMENT_PRESET_PRESENTATIONS: dict[str, PresetPresentation] = {
    "Straight ISO cruise": PresetPresentation(
        title_ru="Прямой участок ISO 8608",
        hint_ru="Ровный прямой участок с профилем ISO 8608 и постоянной скоростью.",
    ),
    "Left turn sine": PresetPresentation(
        title_ru="Левый поворот с синусоидой",
        hint_ru="Поворот влево с синусоидальным дорожным профилем.",
    ),
    "Brake rough ISO": PresetPresentation(
        title_ru="Торможение на грубом ISO",
        hint_ru="Замедление на шероховатом участке ISO 8608.",
    ),
    "Obstacle stress": PresetPresentation(
        title_ru="Препятствия и ямы",
        hint_ru="Стрессовый участок с препятствиями и ямой.",
    ),
}


def _ring_preset_iso_endurance(*, seed: int) -> dict[str, Any]:
    return {
        "schema_version": "ring_v2",
        "closure_policy": "closed_c1_periodic",
        "v0_kph": 36.0,
        "seed": int(seed),
        "dx_m": 0.02,
        "dt_s": 0.01,
        "n_laps": 3,
        "wheelbase_m": 1.5,
        "track_m": 1.0,
        "segments": [
            {
                "name": "Ресурсный прямой участок",
                "duration_s": 6.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "steady",
                "speed_end_kph": 36.0,
                "road": {**build_default_iso_road(seed=seed + 11), "iso_class": "D", "gd_pick": "mid"},
                "events": [],
            },
            {
                "name": "Ресурсный левый поворот",
                "duration_s": 4.5,
                "turn_direction": "LEFT",
                "passage_mode": "steady",
                "speed_end_kph": 36.0,
                "turn_radius_m": 78.0,
                "road": {**build_default_iso_road(seed=seed + 12), "iso_class": "E", "gd_pick": "upper"},
                "events": [],
            },
            {
                "name": "Ресурсный прямой быстрый",
                "duration_s": 5.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "accel",
                "speed_end_kph": 42.0,
                "road": {**build_default_iso_road(seed=seed + 13), "iso_class": "D"},
                "events": [],
            },
            {
                "name": "Ресурсное замыкание",
                "duration_s": 4.0,
                "turn_direction": "RIGHT",
                "passage_mode": "brake",
                "speed_end_kph": 36.0,
                "turn_radius_m": 82.0,
                "road": {**build_default_iso_road(seed=seed + 14), "iso_class": "E", "left_right_coherence": 0.45},
                "events": [],
            },
        ],
    }


def _ring_preset_sine_handling(*, seed: int) -> dict[str, Any]:
    return {
        "schema_version": "ring_v2",
        "closure_policy": "closed_c1_periodic",
        "v0_kph": 32.0,
        "seed": int(seed),
        "dx_m": 0.02,
        "dt_s": 0.01,
        "n_laps": 2,
        "wheelbase_m": 1.5,
        "track_m": 1.0,
        "segments": [
            {
                "name": "Подход к синусоиде",
                "duration_s": 4.5,
                "turn_direction": "STRAIGHT",
                "passage_mode": "accel",
                "speed_end_kph": 34.0,
                "road": {**build_default_sine_road(), "aL_mm": 28.0, "aR_mm": 28.0, "lambdaL_m": 2.2, "lambdaR_m": 2.2},
                "events": [],
            },
            {
                "name": "Левый манёвр",
                "duration_s": 4.0,
                "turn_direction": "LEFT",
                "passage_mode": "brake",
                "speed_end_kph": 32.0,
                "turn_radius_m": 52.0,
                "road": {**build_default_sine_road(), "aL_mm": 42.0, "aR_mm": 36.0, "phaseR_deg": 150.0},
                "events": [],
            },
            {
                "name": "Правый манёвр",
                "duration_s": 4.0,
                "turn_direction": "RIGHT",
                "passage_mode": "steady",
                "speed_end_kph": 32.0,
                "turn_radius_m": 52.0,
                "road": {**build_default_sine_road(), "aL_mm": 36.0, "aR_mm": 42.0, "phaseL_deg": 150.0, "phaseR_deg": 0.0},
                "events": [],
            },
            {
                "name": "Выход и замыкание",
                "duration_s": 3.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "steady",
                "speed_end_kph": 32.0,
                "road": {**build_default_iso_road(seed=seed + 23), "iso_class": "D"},
                "events": [],
            },
        ],
    }


def _ring_preset_events_stress(*, seed: int) -> dict[str, Any]:
    return {
        "schema_version": "ring_v2",
        "closure_policy": "strict_exact",
        "v0_kph": 28.0,
        "seed": int(seed),
        "dx_m": 0.02,
        "dt_s": 0.01,
        "n_laps": 2,
        "wheelbase_m": 1.5,
        "track_m": 1.0,
        "segments": [
            {
                "name": "Разогрев перед событиями",
                "duration_s": 4.0,
                "turn_direction": "STRAIGHT",
                "passage_mode": "steady",
                "speed_end_kph": 28.0,
                "road": {**build_default_iso_road(seed=seed + 31), "iso_class": "F", "gd_pick": "upper"},
                "events": [
                    {"kind": "яма", "side": "left", "start_m": 3.0, "length_m": 0.55, "depth_mm": -32.0, "ramp_m": 0.12}
                ],
            },
            {
                "name": "Пара препятствий",
                "duration_s": 3.5,
                "turn_direction": "STRAIGHT",
                "passage_mode": "brake",
                "speed_end_kph": 24.0,
                "road": {**build_default_iso_road(seed=seed + 32), "iso_class": "E"},
                "events": [
                    {"kind": "препятствие", "side": "both", "start_m": 2.5, "length_m": 0.3, "depth_mm": 18.0, "ramp_m": 0.06},
                    {"kind": "яма", "side": "right", "start_m": 5.0, "length_m": 0.45, "depth_mm": -26.0, "ramp_m": 0.1},
                ],
            },
            {
                "name": "Замыкающий участок событий",
                "duration_s": 4.0,
                "turn_direction": "LEFT",
                "passage_mode": "accel",
                "speed_end_kph": 28.0,
                "turn_radius_m": 68.0,
                "road": {**build_default_sine_road(), "aL_mm": 18.0, "aR_mm": 22.0, "lambdaL_m": 1.7, "lambdaR_m": 1.7},
                "events": [],
            },
        ],
    }


RING_PRESET_BUILDERS: dict[str, Any] = {
    "Demo: mixed ISO+SINE": lambda *, seed: build_default_ring_spec(),
    "ISO endurance": _ring_preset_iso_endurance,
    "SINE handling": _ring_preset_sine_handling,
    "Events stress": _ring_preset_events_stress,
}

RING_PRESET_PRESENTATIONS: dict[str, PresetPresentation] = {
    "Demo: mixed ISO+SINE": PresetPresentation(
        title_ru="Демо: смешанное ISO 8608 и синусоида",
        hint_ru="Базовое демонстрационное кольцо с прямыми участками, поворотом и смешанным профилем.",
    ),
    "ISO endurance": PresetPresentation(
        title_ru="Ресурсный круг ISO 8608",
        hint_ru="Длинный кольцевой сценарий для ресурсной проверки на профиле ISO 8608.",
    ),
    "SINE handling": PresetPresentation(
        title_ru="Управляемость на синусоиде",
        hint_ru="Кольцо с синусоидальными участками и манёврами влево/вправо.",
    ),
    "Events stress": PresetPresentation(
        title_ru="События и препятствия",
        hint_ru="Кольцо с ямами, препятствиями и стрессовыми дорожными участками.",
    ),
}


def _resolve_preset_key(
    name: str,
    *,
    builders: dict[str, Any],
    presentations: dict[str, PresetPresentation],
    label: str,
) -> str:
    value = str(name or "").strip()
    if value in builders:
        return value
    for key, presentation in presentations.items():
        if value == presentation.title_ru:
            return key
    raise KeyError(f"Unknown {label} preset: {name}")


def list_ring_preset_names() -> tuple[str, ...]:
    return tuple(RING_PRESET_PRESENTATIONS[key].title_ru for key in RING_PRESET_BUILDERS.keys())


def list_segment_preset_names() -> tuple[str, ...]:
    return tuple(SEGMENT_PRESET_PRESENTATIONS[key].title_ru for key in SEGMENT_PRESET_BUILDERS.keys())


def build_ring_preset(name: str, *, seed: int) -> dict[str, Any]:
    builder = RING_PRESET_BUILDERS.get(
        _resolve_preset_key(name, builders=RING_PRESET_BUILDERS, presentations=RING_PRESET_PRESENTATIONS, label="ring")
    )
    return normalize_spec(builder(seed=int(seed)))


def build_segment_preset(name: str, *, seed: int) -> dict[str, Any]:
    builder = SEGMENT_PRESET_BUILDERS.get(
        _resolve_preset_key(name, builders=SEGMENT_PRESET_BUILDERS, presentations=SEGMENT_PRESET_PRESENTATIONS, label="segment")
    )
    segment = copy.deepcopy(builder(seed=int(seed)))
    segment["uid"] = new_uid()
    ensure_road_defaults(segment)
    return segment


def canonicalize_ring_source_spec(spec: dict[str, Any] | None) -> dict[str, Any]:
    """Return the WS-RING source payload with derived closure fields locked.

    The editor may show inherited starts and auto-close endpoints, but the saved
    master copy must not keep those values as independent downstream-editable
    geometry.
    """
    normalized = normalize_spec(spec)
    out = copy.deepcopy(normalized)
    segments = get_segments(out)
    if not segments:
        return out
    v_current = float(_resolve_initial_speed_kph(out))
    ring_start = float(v_current)
    first_road = ensure_road_defaults(segments[0])
    first_center_start = safe_float(first_road.get("center_height_start_mm", 0.0), 0.0)
    first_cross_start = safe_float(first_road.get("cross_slope_start_pct", 0.0), 0.0)
    for index, segment in enumerate(segments):
        is_last = index >= len(segments) - 1
        forced_end_kph = ring_start if is_last else None
        motion = _segment_motion_contract(
            segment,
            v_current,
            allow_segment_start_override=(index == 0),
            forced_end_kph=forced_end_kph,
        )
        segment["segment_id"] = int(index + 1)
        segment["turn_direction"] = str(motion.get("turn_direction", "STRAIGHT") or "STRAIGHT").upper()
        segment["passage_mode"] = str(motion.get("passage_mode", segment.get("passage_mode", "steady")) or "steady")
        if index == 0:
            segment["speed_start_kph"] = float(motion.get("speed_start_kph", v_current))
        else:
            segment.pop("speed_start_kph", None)
        segment["speed_end_kph"] = float(motion.get("speed_end_kph", v_current))
        segment.pop("drive_mode", None)
        segment.pop("speed_kph", None)
        segment.pop("v_end_kph", None)

        road = ensure_road_defaults(segment)
        if index > 0:
            road.pop("center_height_start_mm", None)
            road.pop("cross_slope_start_pct", None)
        if is_last:
            road["center_height_end_mm"] = float(first_center_start)
            road["cross_slope_end_pct"] = float(first_cross_start)
        v_current = float(motion.get("speed_end_kph", v_current))
    out["segments"] = segments
    out["_source_contract"] = {
        "workspace": "WS-RING",
        "source_of_truth": True,
        "editable_owner": "WS-RING",
        "handoff_id": "HO-004",
        "downstream_geometry_editing_allowed": False,
    }
    return out


def load_spec_from_path(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("JSON spec должен быть объектом.")
    return normalize_spec(obj)


def save_spec_to_path(spec: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.write_text(json.dumps(canonicalize_ring_source_spec(spec), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def resolve_ring_inputs_handoff(
    *,
    workspace_dir: Path | str | None = None,
    snapshot_path: Path | str | None = None,
    snapshot: dict[str, Any] | None = None,
    current_inputs_snapshot_hash: str = "",
) -> dict[str, Any]:
    """Resolve the WS-INPUTS -> WS-RING frozen input ref without rebinding inputs."""

    return describe_desktop_inputs_handoff_for_workspace(
        "WS-RING",
        workspace_dir=workspace_dir,
        snapshot_path=snapshot_path,
        snapshot=snapshot,
        current_payload_hash=current_inputs_snapshot_hash,
    )


@dataclass
class RingEditorExportState:
    output_dir: str = ""
    tag: str = "ring"
    opt_workspace_dir: str = ""
    opt_window_s: float = 4.0
    artifacts_stale: bool = True
    opt_suite_stale: bool = True
    last_bundle: dict[str, Any] = field(default_factory=dict)
    last_error: str = ""


@dataclass
class RingEditorState:
    spec: dict[str, Any] = field(default_factory=build_default_ring_spec)
    selected_segment_uid: str = ""
    export: RingEditorExportState = field(default_factory=RingEditorExportState)
    spec_path: str = ""
    dirty: bool = False
    status_message: str = ""

    def ensure_selection(self) -> None:
        raw = self.spec.get("segments")
        if not isinstance(raw, list):
            raw = []
            self.spec["segments"] = raw
        segments = raw
        ensure_segment_uids(segments)
        self.spec["segments"] = segments
        if not segments:
            self.selected_segment_uid = ""
            return
        uids = {str(segment.get("uid") or "") for segment in segments}
        if not self.selected_segment_uid or self.selected_segment_uid not in uids:
            self.selected_segment_uid = str(segments[0].get("uid") or "")


def create_editor_state(*, output_dir: str = "") -> RingEditorState:
    state = RingEditorState()
    state.export.output_dir = output_dir
    state.ensure_selection()
    return state


def get_segments(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw = spec.get("segments")
    if not isinstance(raw, list):
        raw = []
        spec["segments"] = raw
    segments = raw
    ensure_segment_uids(segments)
    spec["segments"] = segments
    return segments


def find_selected_segment_index(state: RingEditorState) -> int:
    state.ensure_selection()
    for index, segment in enumerate(get_segments(state.spec)):
        if str(segment.get("uid") or "") == state.selected_segment_uid:
            return index
    return 0


def get_selected_segment(state: RingEditorState) -> dict[str, Any] | None:
    segments = get_segments(state.spec)
    if not segments:
        return None
    return segments[find_selected_segment_index(state)]


def select_segment_by_index(state: RingEditorState, index: int) -> None:
    segments = get_segments(state.spec)
    if not segments:
        state.selected_segment_uid = ""
        return
    safe_index = max(0, min(int(index), len(segments) - 1))
    state.selected_segment_uid = str(segments[safe_index].get("uid") or "")


def clone_segment(segment: dict[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(segment)
    cloned["uid"] = new_uid()
    cloned["name"] = f"{str(segment.get('name') or 'Сегмент')} (копия)"
    return cloned


def blank_segment_after(segment: dict[str, Any] | None, *, seed: int = 12345) -> dict[str, Any]:
    new_segment = build_blank_segment(seed=seed)
    if not isinstance(segment, dict):
        return new_segment
    road = dict(segment.get("road", {}) or {})
    new_segment["road"] = build_default_sine_road() if str(road.get("mode", "")).upper() == "SINE" else build_default_iso_road(seed=seed)
    new_segment["speed_end_kph"] = safe_float(segment.get("speed_end_kph", 40.0), 40.0)
    return new_segment


def add_segment_after_selection(state: RingEditorState) -> None:
    segments = get_segments(state.spec)
    index = find_selected_segment_index(state)
    seed = safe_int(state.spec.get("seed", 123), 123)
    base_segment = segments[index] if segments else None
    new_segment = blank_segment_after(base_segment, seed=seed)
    insert_at = index + 1 if segments else 0
    segments.insert(insert_at, new_segment)
    state.selected_segment_uid = str(new_segment.get("uid") or "")


def apply_ring_preset(state: RingEditorState, preset_name: str) -> None:
    seed = safe_int(state.spec.get("seed", 123), 123)
    state.spec = build_ring_preset(preset_name, seed=seed)
    state.ensure_selection()


def apply_segment_preset_to_selected(state: RingEditorState, preset_name: str) -> None:
    segments = get_segments(state.spec)
    if not segments:
        insert_segment_preset_after_selection(state, preset_name)
        return
    index = find_selected_segment_index(state)
    current_uid = str(segments[index].get("uid") or new_uid())
    preset = build_segment_preset(preset_name, seed=safe_int(state.spec.get("seed", 123), 123))
    preset["uid"] = current_uid
    segments[index] = preset
    state.selected_segment_uid = current_uid


def insert_segment_preset_after_selection(state: RingEditorState, preset_name: str) -> None:
    segments = get_segments(state.spec)
    index = find_selected_segment_index(state) if segments else -1
    preset = build_segment_preset(preset_name, seed=safe_int(state.spec.get("seed", 123), 123))
    insert_at = index + 1 if segments else 0
    segments.insert(insert_at, preset)
    state.selected_segment_uid = str(preset.get("uid") or "")


def clone_selected_segment(state: RingEditorState) -> None:
    segments = get_segments(state.spec)
    if not segments:
        add_segment_after_selection(state)
        return
    index = find_selected_segment_index(state)
    new_segment = clone_segment(segments[index])
    segments.insert(index + 1, new_segment)
    state.selected_segment_uid = str(new_segment.get("uid") or "")


def delete_selected_segment(state: RingEditorState) -> None:
    segments = get_segments(state.spec)
    if len(segments) <= 1:
        return
    index = find_selected_segment_index(state)
    segments.pop(index)
    select_segment_by_index(state, max(0, index - 1))


def move_selected_segment(state: RingEditorState, delta: int) -> None:
    segments = get_segments(state.spec)
    if len(segments) <= 1:
        return
    index = find_selected_segment_index(state)
    target = max(0, min(index + int(delta), len(segments) - 1))
    if target == index:
        return
    segment = segments.pop(index)
    segments.insert(target, segment)
    state.selected_segment_uid = str(segment.get("uid") or "")


def add_event_to_selected_segment(state: RingEditorState, event: dict[str, Any] | None = None) -> None:
    segment = get_selected_segment(state)
    if segment is None:
        return
    events = list(segment.get("events", []) or [])
    events.append(copy.deepcopy(event or build_blank_event()))
    segment["events"] = events


def replace_selected_event(state: RingEditorState, event_index: int, event: dict[str, Any]) -> None:
    segment = get_selected_segment(state)
    if segment is None:
        return
    events = list(segment.get("events", []) or [])
    if not (0 <= int(event_index) < len(events)):
        return
    events[int(event_index)] = copy.deepcopy(event)
    segment["events"] = events


def delete_selected_event(state: RingEditorState, event_index: int) -> None:
    segment = get_selected_segment(state)
    if segment is None:
        return
    events = list(segment.get("events", []) or [])
    if not (0 <= int(event_index) < len(events)):
        return
    events.pop(int(event_index))
    segment["events"] = events


def build_segment_flow_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    segments = get_segments(spec)
    if not segments:
        return []
    rows: list[dict[str, Any]] = []
    v_current = float(_resolve_initial_speed_kph(spec))
    ring_start = float(v_current)
    dt_s = safe_float(spec.get("dt_s", 0.01), 0.01)
    dx_m = safe_float(spec.get("dx_m", 0.02), 0.02)
    for index, segment in enumerate(segments):
        forced_end_kph = ring_start if index >= len(segments) - 1 else None
        motion = _segment_motion_contract(
            segment,
            v_current,
            allow_segment_start_override=(index == 0),
            forced_end_kph=forced_end_kph,
        )
        try:
            length_m = _segment_length_canonical_m(
                v_current,
                segment,
                fallback_dt_s=dt_s,
                dx_m=dx_m,
                forced_end_kph=forced_end_kph,
            )
        except Exception:
            length_m = max(dx_m, safe_float(segment.get("length_m", 0.0), 0.0))
        row = {
            "uid": str(segment.get("uid") or ""),
            "index": index,
            "name": str(segment.get("name") or f"S{index + 1}"),
            "duration_s": safe_float(segment.get("duration_s", 0.0), 0.0),
            "length_m": float(length_m),
            "turn_direction": str(motion.get("turn_direction", "STRAIGHT") or "STRAIGHT"),
            "passage_mode": str(motion.get("passage_mode", "steady") or "steady"),
            "speed_start_kph": float(motion.get("speed_start_kph", v_current)),
            "speed_end_kph": float(motion.get("speed_end_kph", v_current)),
            "turn_radius_m": float(motion.get("turn_radius_m", 0.0) or 0.0),
            "road_mode": str(dict(segment.get("road", {}) or {}).get("mode", "ISO8608") or "ISO8608"),
            "event_count": len(list(segment.get("events", []) or [])),
        }
        rows.append(row)
        v_current = float(row["speed_end_kph"])
    return rows


def build_segment_label(row: dict[str, Any]) -> str:
    turn = _turn_label(row.get("turn_direction") or "")
    passage = _passage_mode_label(row.get("passage_mode") or "steady")
    road = _road_mode_label(row.get("road_mode") or "ISO8608")
    return (
        f"{int(row.get('index', 0)) + 1:02d}. "
        f"{str(row.get('name') or 'Сегмент')} | "
        f"{turn} | "
        f"{passage} | "
        f"{float(row.get('speed_start_kph', 0.0)):.0f}->{float(row.get('speed_end_kph', 0.0)):.0f} км/ч | "
        f"{float(row.get('length_m', 0.0)):.1f} м | "
        f"{road} | событий: {int(row.get('event_count', 0) or 0)}"
    )
