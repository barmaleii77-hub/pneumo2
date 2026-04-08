from __future__ import annotations

"""One-click optimization preset for fresh UI sessions.

Goal:
- after a fresh app launch the user should be able to open the optimization section
  and start a meaningful 30-minute run without hand-enabling tests or generating
  missing sidecars;
- keep the preset explicit and reproducible: suite rows get real stage numbers,
  generated road/maneuver artifacts live inside the current session workspace,
  and file paths are absolute so validation does not depend on repo-relative hacks.

This module intentionally keeps logic separate from Streamlit pages so the same
preset can be consumed by the classic UI, the multipage optimization screen and
unit tests.
"""

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from .optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIAGNOSTIC_CALIB_MODE,
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    DIAGNOSTIC_PROBLEM_HASH_MODE,
    DIAGNOSTIC_SEED_CANDIDATES,
    DIAGNOSTIC_SEED_CONDITIONS,
    DIAGNOSTIC_SORT_TESTS_BY_COST,
    DIAGNOSTIC_SURROGATE_SAMPLES,
    DIAGNOSTIC_SURROGATE_TOP_K,
    DIAGNOSTIC_USE_STAGED_OPT,
    DIAGNOSTIC_WARMSTART_MODE,
    diagnostics_jobs_default,
    objectives_text,
)
from .optimization_input_contract import normalize_suite_stage_numbers
from .optimization_stage_policy import DEFAULT_STAGE_POLICY_MODE
from .scenario_generator import ISO8608Spec, generate_iso8608_road_csv
from .scenario_ring import generate_ring_scenario_bundle

READY_PRESET_SCHEMA_VERSION = "pneumo_opt_ready_preset_v1"
READY_PRESET_NAME = "fullcheck_30min"
READY_PRESET_DIRNAME = "optimization_ready_fullcheck_30min"
READY_PRESET_META_FILENAME = "preset_meta.json"
READY_PRESET_SUITE_FILENAME = "suite_ready_fullcheck_30min.json"

READY_OPT_MINUTES = 30.0
READY_PROFILE_SPEED_MPS = 20.0 / 3.6
READY_PROFILE_DT = 0.01
READY_PROFILE_T_END = 6.0
READY_PROFILE_ID = "0b62f508-f0a4-4b67-a8c7-2d1e8d8d5af1"
READY_PROFILE_NAME = "road_profile_iso8608_E_20кмч_6s"
READY_RING_TAG = "OPT_READY_RING_SHORT_CITY_ROUGH_20kmh"

CANONICAL_OPTIMIZATION_TEST_TYPES: tuple[str, ...] = (
    "инерция_крен",
    "инерция_тангаж",
    "микро_синфаза",
    "микро_разнофаза",
    "микро_разнофаза_лево_право",
    "микро_разнофаза_перед_зад",
    "микро_разнофаза_передзад",
    "микро_разнофаза_диаг",
    "микро_разнофаза_диагональ",
    "микро_разнофаза_диагональ_1",
    "микро_разнофаза_FL_RR",
    "микро_разнофаза_диагональ_2",
    "микро_разнофаза_FR_RL",
    "кочка_одно_колесо",
    "кочка_диагональ",
    "комбо_крен_плюс_микро",
    "worldroad",
    "road_profile_csv",
    "maneuver_csv",
)

# Explicit stage/enable policy for the shipped suite rows.
# Stage 0 = cheap signal tests for quick relevance.
# Stage 1 = medium-cost road/contact/worldroad checks.
# Stage 2 = heavy external-profile / ring validation inside the 30-minute preset.
# Stage 3 = kept configured but excluded from the default 30-minute StageRunner path.
_READY_STAGE_ENABLE_BY_NAME: dict[str, tuple[int, bool]] = {
    "ring_город_неровная_дорога_20кмч_15s": (2, True),
    "инерция_крен_ay2": (0, False),
    "инерция_крен_ay3": (0, True),
    "микро_pitch": (0, True),
    "микро_diagonal": (0, True),
    "инерция_тангаж_ax3": (0, True),
    "микро_синфаза": (0, True),
    "микро_разнофаза": (0, False),
    "кочка_ЛП_короткая": (1, True),
    "кочка_ЛП_длинная": (1, False),
    "кочка_диагональ": (1, False),
    "комбо_ay3_плюс_микро": (1, True),
    "world_ridge_bump_demo": (1, True),
    "микро_разнофаза_передзад": (1, False),
    "микро_разнофаза_диаг": (1, False),
    "macro_разнофаза_передзад": (3, False),
    "macro_разнофаза_диаг": (3, False),
}


_DEF_SUITE_ROW_DEFAULTS: dict[str, Any] = {
    "id": "",
    "имя": "",
    "тип": "",
    "включен": False,
    "комментарий": "",
    "стадия": 0,
    "dt": 0.005,
    "t_end": 5.0,
    "auto_t_end_from_len": True,
    "road_len_m": 3000.0,
    "vx0_м_с": READY_PROFILE_SPEED_MPS,
    "road_csv": "",
    "axay_csv": "",
    "scenario_json": "",
    "road_surface": "rough",
    "slope_deg": 0.0,
    "track_m": float("nan"),
    "wheelbase_m": float("nan"),
    "yaw0_рад": float("nan"),
    "save_npz": True,
    "save_csv": True,
}


def _safe_float(value: Any, default: float) -> float:
    try:
        out = float(value)
        if out != out or out in (float("inf"), float("-inf")):
            return float(default)
        return out
    except Exception:
        return float(default)


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_mtime_ns(path: Path) -> int:
    try:
        return int(Path(path).stat().st_mtime_ns)
    except Exception:
        return 0


def _read_wheelbase_m(base_json_path: Path) -> float:
    try:
        obj = _read_json(base_json_path)
    except Exception:
        obj = {}
    if isinstance(obj, Mapping):
        return _safe_float(obj.get("база"), 1.5)
    return 1.5


def _preset_paths(workspace_dir: Path) -> dict[str, Path]:
    root = Path(workspace_dir).resolve() / "ui_state" / READY_PRESET_DIRNAME
    generated = root / "generated_scenarios"
    return {
        "root": root,
        "generated": generated,
        "suite": root / READY_PRESET_SUITE_FILENAME,
        "meta": root / READY_PRESET_META_FILENAME,
        "profile_road": generated / "profile" / "scenario_optready_iso8608_E_20kmh_6s_road.csv",
        "profile_meta": generated / "profile" / "scenario_optready_iso8608_E_20kmh_6s_spec.json",
        "ring_dir": generated / "ring",
        "ring_road": generated / "ring" / f"scenario_{READY_RING_TAG}_road.csv",
        "ring_axay": generated / "ring" / f"scenario_{READY_RING_TAG}_axay.csv",
        "ring_meta": generated / "ring" / f"scenario_{READY_RING_TAG}_spec.json",
    }


def _normalize_suite_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    norm_rows: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        rec = dict(_DEF_SUITE_ROW_DEFAULTS)
        rec.update(dict(raw))
        # Keep common flags explicit and json-friendly.
        rec["включен"] = bool(rec.get("включен", False))
        rec["dt"] = _safe_float(rec.get("dt"), float(_DEF_SUITE_ROW_DEFAULTS["dt"]))
        rec["t_end"] = _safe_float(rec.get("t_end"), float(_DEF_SUITE_ROW_DEFAULTS["t_end"]))
        rec["vx0_м_с"] = _safe_float(rec.get("vx0_м_с"), float(_DEF_SUITE_ROW_DEFAULTS["vx0_м_с"]))
        rec["auto_t_end_from_len"] = bool(rec.get("auto_t_end_from_len", True))
        for key in ("road_csv", "axay_csv", "scenario_json"):
            val = rec.get(key, "")
            rec[key] = "" if val is None else str(val)
        norm_rows.append(rec)

    norm_rows2, _audit = normalize_suite_stage_numbers(norm_rows)
    out: list[dict[str, Any]] = []
    for rec in norm_rows2:
        item = dict(rec)
        name = str(item.get("имя") or "").strip()
        stage, enabled = _READY_STAGE_ENABLE_BY_NAME.get(name, (int(item.get("стадия", 0) or 0), False))
        item["стадия"] = int(stage)
        item["включен"] = bool(enabled)
        out.append(item)
    return out


def _ready_ring_spec(*, wheelbase_m: float) -> dict[str, Any]:
    """15-second rough-city ring for final stage validation."""
    return {
        "schema_version": "ring_v2",
        "closure_policy": "closed_c1_periodic",
        "v0_kph": 20.0,
        "seed": 123,
        "dx_m": 0.02,
        "dt_s": 0.01,
        "n_laps": 1,
        "wheelbase_m": float(max(0.5, wheelbase_m)),
        "segments": [
            {
                "name": "S1_прямо_rough",
                "duration_s": 4.0,
                "drive_mode": "STRAIGHT",
                "speed_kph": 20.0,
                "road": {
                    "mode": "ISO8608",
                    "iso_class": "E",
                    "gd_pick": "mid",
                    "gd_n0_scale": 1.0,
                    "waviness_w": 2.0,
                    "left_right_coherence": 0.6,
                    "seed": 12345,
                },
                "events": [
                    {
                        "kind": "яма",
                        "side": "left",
                        "start_m": 6.0,
                        "length_m": 0.45,
                        "depth_mm": -22.0,
                        "ramp_m": 0.08,
                    },
                    {
                        "kind": "препятствие",
                        "side": "both",
                        "start_m": 12.0,
                        "length_m": 0.25,
                        "depth_mm": 16.0,
                        "ramp_m": 0.06,
                    },
                ],
            },
            {
                "name": "S2_поворот_влево",
                "duration_s": 3.5,
                "drive_mode": "TURN_LEFT",
                "speed_kph": 20.0,
                "turn_radius_m": 35.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 18.0,
                    "aR_mm": 18.0,
                    "lambdaL_m": 1.4,
                    "lambdaR_m": 1.4,
                    "phaseL_deg": 0.0,
                    "phaseR_deg": 180.0,
                },
                "events": [],
            },
            {
                "name": "S3_прямо_city",
                "duration_s": 4.0,
                "drive_mode": "STRAIGHT",
                "speed_kph": 20.0,
                "road": {
                    "mode": "ISO8608",
                    "iso_class": "D",
                    "gd_pick": "upper",
                    "gd_n0_scale": 1.0,
                    "waviness_w": 2.0,
                    "left_right_coherence": 0.55,
                    "seed": 23456,
                },
                "events": [
                    {
                        "kind": "яма",
                        "side": "right",
                        "start_m": 4.0,
                        "length_m": 0.35,
                        "depth_mm": -18.0,
                        "ramp_m": 0.06,
                    },
                    {
                        "kind": "препятствие",
                        "side": "left",
                        "start_m": 9.0,
                        "length_m": 0.3,
                        "depth_mm": 14.0,
                        "ramp_m": 0.07,
                    },
                ],
            },
            {
                "name": "S4_поворот_вправо",
                "duration_s": 3.5,
                "drive_mode": "TURN_RIGHT",
                "speed_kph": 20.0,
                "turn_radius_m": 35.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 14.0,
                    "aR_mm": 14.0,
                    "lambdaL_m": 1.8,
                    "lambdaR_m": 1.8,
                    "phaseL_deg": 180.0,
                    "phaseR_deg": 0.0,
                },
                "events": [],
            },
        ],
    }


def _materialize_generated_profile(paths: Mapping[str, Path], *, wheelbase_m: float) -> dict[str, str]:
    road_csv = Path(paths["profile_road"])
    meta_json = Path(paths["profile_meta"])
    road_csv.parent.mkdir(parents=True, exist_ok=True)
    spec = ISO8608Spec(road_class="E", gd_pick="mid", gd_n0_scale=1.0, waviness_w=2.0)
    out_path, meta = generate_iso8608_road_csv(
        out_csv=road_csv,
        dt=READY_PROFILE_DT,
        t_end=READY_PROFILE_T_END,
        speed_mps=READY_PROFILE_SPEED_MPS,
        wheelbase_m=float(max(0.5, wheelbase_m)),
        spec=spec,
        dx_m=0.02,
        left_right_coherence=0.55,
        seed=431,
    )
    meta_json.write_text(
        json.dumps(
            {
                "schema_version": READY_PRESET_SCHEMA_VERSION,
                "preset_name": READY_PRESET_NAME,
                "scenario_type": "road_profile_csv",
                "name": READY_PROFILE_NAME,
                "road_csv": str(Path(out_path).resolve()),
                "meta": meta,
                "generator": {
                    "road_class": spec.road_class,
                    "gd_pick": spec.gd_pick,
                    "gd_n0_scale": spec.gd_n0_scale,
                    "waviness_w": spec.waviness_w,
                    "speed_mps": READY_PROFILE_SPEED_MPS,
                    "dt": READY_PROFILE_DT,
                    "t_end": READY_PROFILE_T_END,
                    "left_right_coherence": 0.55,
                    "seed": 431,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "road_csv": str(Path(out_path).resolve()),
        "scenario_json": str(meta_json.resolve()),
    }


def _materialize_generated_ring(paths: Mapping[str, Path], *, wheelbase_m: float) -> dict[str, Any]:
    ring_dir = Path(paths["ring_dir"])
    ring_dir.mkdir(parents=True, exist_ok=True)
    spec = _ready_ring_spec(wheelbase_m=wheelbase_m)
    out = generate_ring_scenario_bundle(
        spec,
        out_dir=ring_dir,
        dt_s=0.01,
        n_laps=1,
        wheelbase_m=float(max(0.5, wheelbase_m)),
        dx_m=0.02,
        seed=123,
        tag=READY_RING_TAG,
    )
    resolved = dict(out)
    for key in ("road_csv", "axay_csv", "scenario_json"):
        if key in resolved:
            resolved[key] = str(Path(str(resolved[key])).resolve())
    return resolved


def _append_generated_rows(rows: list[dict[str, Any]], *, generated_profile: Mapping[str, str]) -> list[dict[str, Any]]:
    out = list(rows)
    out.append(
        {
            "id": READY_PROFILE_ID,
            "имя": READY_PROFILE_NAME,
            "тип": "road_profile_csv",
            "включен": True,
            "стадия": 2,
            "комментарий": "Автогенерируемый rough ISO8608 профиль для one-click проверки file-based optimization path.",
            "dt": READY_PROFILE_DT,
            "t_end": READY_PROFILE_T_END,
            "vx0_м_с": READY_PROFILE_SPEED_MPS,
            "auto_t_end_from_len": False,
            "road_csv": str(generated_profile.get("road_csv") or ""),
            "axay_csv": "",
            "scenario_json": str(generated_profile.get("scenario_json") or ""),
            "road_surface": "rough",
            "target_макс_доля_отрыва": 0.25,
            "target_мин_запас_до_Pmid_бар": -0.2,
            "target_мин_Fmin_Н": 0.0,
            "target_мин_запас_до_упора_штока_м": 0.001,
            "target_лимит_скорости_штока_м_с": 3.0,
            "target_мин_зазор_пружина_цилиндр_м": 0.001,
            "target_мин_зазор_пружина_пружина_м": 0.001,
            "target_макс_ошибка_midstroke_t0_м": 0.03,
            "target_мин_запас_до_coil_bind_пружины_м": 0.003,
            "save_npz": True,
            "save_csv": True,
        }
    )
    return out


def build_optimization_ready_suite_rows(
    workspace_dir: str | os.PathLike[str] | Path,
    *,
    base_json_path: str | os.PathLike[str] | Path,
    suite_source_path: str | os.PathLike[str] | Path,
) -> list[dict[str, Any]]:
    """Build suite rows for the fresh one-click 30-minute optimization preset."""
    workspace_dir = Path(workspace_dir).resolve()
    base_json_path = Path(base_json_path).resolve()
    suite_source_path = Path(suite_source_path).resolve()

    paths = _preset_paths(workspace_dir)
    for key in ("root", "generated"):
        Path(paths[key]).mkdir(parents=True, exist_ok=True)

    wheelbase_m = _read_wheelbase_m(base_json_path)
    try:
        source_rows = _read_json(suite_source_path)
    except Exception:
        source_rows = []
    if not isinstance(source_rows, list):
        source_rows = []

    rows = _normalize_suite_rows(source_rows)
    generated_profile = _materialize_generated_profile(paths, wheelbase_m=wheelbase_m)
    generated_ring = _materialize_generated_ring(paths, wheelbase_m=wheelbase_m)

    updated_rows: list[dict[str, Any]] = []
    for rec in rows:
        item = dict(rec)
        name = str(item.get("имя") or "").strip()
        if name == "ring_город_неровная_дорога_20кмч_15s":
            item["тип"] = "maneuver_csv"
            item["включен"] = True
            item["стадия"] = 2
            item["dt"] = _safe_float(generated_ring.get("dt_s"), 0.01)
            item["t_end"] = _safe_float(generated_ring.get("lap_time_s"), 15.0)
            item["vx0_м_с"] = READY_PROFILE_SPEED_MPS
            item["auto_t_end_from_len"] = False
            item["road_csv"] = str(generated_ring.get("road_csv") or "")
            item["axay_csv"] = str(generated_ring.get("axay_csv") or "")
            item["scenario_json"] = str(generated_ring.get("scenario_json") or "")
            item["комментарий"] = (
                "Автогенерируемое кольцо short city rough 20 км/ч для final-stage one-click проверки манёвра и sidecar paths."
            )
            item.setdefault("target_мин_зазор_пружина_цилиндр_м", 0.001)
            item.setdefault("target_мин_зазор_пружина_пружина_м", 0.001)
            item.setdefault("target_макс_ошибка_midstroke_t0_м", 0.03)
            item.setdefault("target_мин_запас_до_coil_bind_пружины_м", 0.003)
        updated_rows.append(item)

    return _append_generated_rows(updated_rows, generated_profile=generated_profile)


def materialize_optimization_ready_suite_json(
    workspace_dir: str | os.PathLike[str] | Path,
    *,
    base_json_path: str | os.PathLike[str] | Path,
    suite_source_path: str | os.PathLike[str] | Path,
) -> Path:
    """Write/update the one-click preset suite JSON inside the current workspace."""
    workspace_dir = Path(workspace_dir).resolve()
    base_json_path = Path(base_json_path).resolve()
    suite_source_path = Path(suite_source_path).resolve()
    paths = _preset_paths(workspace_dir)
    root = Path(paths["root"])
    root.mkdir(parents=True, exist_ok=True)

    meta_expected = {
        "schema_version": READY_PRESET_SCHEMA_VERSION,
        "preset_name": READY_PRESET_NAME,
        "base_json": str(base_json_path),
        "base_json_mtime_ns": _json_mtime_ns(base_json_path),
        "suite_source_json": str(suite_source_path),
        "suite_source_json_mtime_ns": _json_mtime_ns(suite_source_path),
        "wheelbase_m": _read_wheelbase_m(base_json_path),
    }
    current_meta: Mapping[str, Any] = {}
    try:
        raw_meta = _read_json(Path(paths["meta"]))
        if isinstance(raw_meta, Mapping):
            current_meta = raw_meta
    except Exception:
        current_meta = {}

    suite_path = Path(paths["suite"])
    generated_paths = [
        Path(paths["profile_road"]),
        Path(paths["profile_meta"]),
        Path(paths["ring_road"]),
        Path(paths["ring_axay"]),
        Path(paths["ring_meta"]),
    ]
    if suite_path.exists():
        # Fast path: if the preset signature matches and generated files still exist,
        # avoid re-writing the suite on every Streamlit rerun.
        if all(current_meta.get(k) == v for k, v in meta_expected.items()) and all(p.exists() for p in generated_paths):
            try:
                rows = _read_json(suite_path)
                if isinstance(rows, list):
                    has_enabled = any(bool((row or {}).get("включен")) for row in rows if isinstance(row, Mapping))
                    has_profile = any(str((row or {}).get("имя") or "").strip() == READY_PROFILE_NAME for row in rows if isinstance(row, Mapping))
                    if has_enabled and has_profile:
                        return suite_path
            except Exception:
                pass

    rows = build_optimization_ready_suite_rows(
        workspace_dir,
        base_json_path=base_json_path,
        suite_source_path=suite_source_path,
    )
    suite_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(paths["meta"]).write_text(json.dumps(meta_expected, ensure_ascii=False, indent=2), encoding="utf-8")
    return suite_path


def load_optimization_ready_suite_rows(
    workspace_dir: str | os.PathLike[str] | Path,
    *,
    base_json_path: str | os.PathLike[str] | Path,
    suite_source_path: str | os.PathLike[str] | Path,
) -> list[dict[str, Any]]:
    suite_path = materialize_optimization_ready_suite_json(
        workspace_dir,
        base_json_path=base_json_path,
        suite_source_path=suite_source_path,
    )
    raw = _read_json(suite_path)
    return list(raw) if isinstance(raw, list) else []


def optimization_ready_session_defaults(
    *,
    cpu_count: int | None = None,
    platform_name: str | None = None,
) -> dict[str, Any]:
    cpu_n = int(cpu_count or os.cpu_count() or 4)
    platform_norm = str(platform_name or os.sys.platform)
    return {
        "ui_opt_minutes": READY_OPT_MINUTES,
        "ui_jobs": int(diagnostics_jobs_default(cpu_n, platform_name=platform_norm)),
        "opt_use_staged": bool(DIAGNOSTIC_USE_STAGED_OPT),
        "use_staged_opt": bool(DIAGNOSTIC_USE_STAGED_OPT),
        "opt_autoupdate_baseline": True,
        "autoupdate_baseline": True,
        "warmstart_mode": str(DIAGNOSTIC_WARMSTART_MODE),
        "surrogate_samples": int(DIAGNOSTIC_SURROGATE_SAMPLES),
        "surrogate_top_k": int(DIAGNOSTIC_SURROGATE_TOP_K),
        "sort_tests_by_cost": bool(DIAGNOSTIC_SORT_TESTS_BY_COST),
        "ui_seed_candidates": int(DIAGNOSTIC_SEED_CANDIDATES),
        "ui_seed_conditions": int(DIAGNOSTIC_SEED_CONDITIONS),
        "influence_eps_rel": float(DIAGNOSTIC_INFLUENCE_EPS_REL),
        "adaptive_influence_eps": False,
        "stage_policy_mode": str(DEFAULT_STAGE_POLICY_MODE),
        "settings_opt_problem_hash_mode": str(DIAGNOSTIC_PROBLEM_HASH_MODE),
        "opt_objectives": objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES),
        "opt_run_name": "integration_30m",
        "ui_out_prefix": "results_opt_fullcheck",
        "calib_mode_pick": str(DIAGNOSTIC_CALIB_MODE),
    }


def seed_optimization_ready_session_state(
    session_state: MutableMapping[str, Any],
    *,
    cpu_count: int | None = None,
    platform_name: str | None = None,
) -> dict[str, Any]:
    """Fill missing optimization keys for a fresh session without overwriting user state."""
    defaults = optimization_ready_session_defaults(cpu_count=cpu_count, platform_name=platform_name)
    for key, value in defaults.items():
        session_state.setdefault(key, value)
    return defaults
