"""Canonical optimization defaults.

These defaults are intentionally small and dependency-free so they can be used by
both Streamlit pages and CLI coordinators without importing the whole UI.

Why this module exists:
- the diagnostics archive already established a stable set of optimization/UI
  defaults that should survive release repacks;
- objective defaults on the distributed optimization page drifted away from the
  worker/coordinator metric keys;
- some CLIs still defaulted to stale v8 model files instead of the current
  canonical v9 double-wishbone model.
"""

from __future__ import annotations

import json
import os
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

# Diagnostics-archive aligned UI defaults
DIAGNOSTIC_OPT_MINUTES_DEFAULT: float = 10.0
# Do not underutilize larger Windows workstations: the runtime already clamps to
# the ProcessPoolExecutor hard limit (61 on Windows), so the default hint should
# reach that platform cap instead of stopping at a stale archive-era value 24.
DIAGNOSTIC_OPT_JOBS_HINT: int = 61
DIAGNOSTIC_USE_STAGED_OPT: bool = True
DIAGNOSTIC_WARMSTART_MODE: str = "surrogate"
DIAGNOSTIC_SURROGATE_SAMPLES: int = 8000
DIAGNOSTIC_SURROGATE_TOP_K: int = 64
DIAGNOSTIC_SORT_TESTS_BY_COST: bool = True
DIAGNOSTIC_INFLUENCE_EPS_REL: float = 1e-2
DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS: bool = False
DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID: tuple[float, ...] = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2)
DIAGNOSTIC_SEED_CANDIDATES: int = 1
DIAGNOSTIC_SEED_CONDITIONS: int = 1
DIAGNOSTIC_SUITE_PRESET: str = "worldroad_flat"
DIAGNOSTIC_SUITE_SELECTED_ID: str = "75ea0ffc-2fa0-4bed-82da-e4f77aab1779"
DIAGNOSTIC_PROBLEM_HASH_MODE: str = "stable"
DIAGNOSTIC_CALIB_MODE: str = "minimal"
DIAGNOSTIC_SELFCHECK_LEVEL: str = "standard"

# Adaptive epsilon policies for runtime stages.
# Intent:
# - stage0_relevance: coarser/stabler scan is acceptable because this stage only
#   needs a robust relevance ordering;
# - stage1_long: balanced profile around the requested epsilon;
# - stage2_final: finer scan, biased toward smaller stable eps, because the final
#   stage is where subtle parameter influence matters most.
_STAGE_AWARE_INFLUENCE_PROFILE_SPECS: dict[str, dict[str, Any]] = {
    "stage0_relevance": {
        "label": "coarse",
        "adaptive_strategy": "coarse",
        "min_scale": 0.10,
        "max_scale": 3.00,
        "anchor_scales": (0.10, 0.30, 1.00, 3.00),
    },
    "stage1_long": {
        "label": "balanced",
        "adaptive_strategy": "balanced",
        "min_scale": 0.03,
        "max_scale": 3.00,
        "anchor_scales": (0.03, 0.10, 0.30, 1.00, 3.00),
    },
    "stage2_final": {
        "label": "fine",
        "adaptive_strategy": "fine",
        "min_scale": 0.01,
        "max_scale": 1.00,
        "anchor_scales": (0.01, 0.03, 0.10, 0.30, 1.00),
    },
}

# Distributed optimization page defaults
DIST_OPT_BUDGET_DEFAULT: int = 300
DIST_OPT_SEED_DEFAULT: int = 42
DIST_OPT_MAX_INFLIGHT_DEFAULT: int = 0
DIST_OPT_PROPOSER_DEFAULT: str = "auto"
DIST_OPT_Q_DEFAULT: int = 1
DIST_OPT_DEVICE_DEFAULT: str = "auto"
DIST_OPT_PENALTY_KEY_DEFAULT: str = "штраф_физичности_сумма"
DIST_OPT_PENALTY_TOL_DEFAULT: float = 0.0
DIST_OPT_DB_ENGINE_DEFAULT: str = "sqlite"
DIST_OPT_STALE_TTL_SEC_DEFAULT: int = 3600
DIST_OPT_HV_LOG_DEFAULT: bool = True
DIST_OPT_EXPORT_EVERY_DEFAULT: int = 50
DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT: int = 1
DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT: str = ":0"
DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT: str = "auto"
DIST_OPT_BOTORCH_N_INIT_DEFAULT: int = 0
DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT: int = 0
DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT: int = 10
DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT: int = 512
DIST_OPT_BOTORCH_MAXITER_DEFAULT: int = 200
DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT: float = 0.10
DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT: bool = True

# Optimization priority requested by the user:
# 1) minimal vertical frame acceleration
# 2) minimal lateral/transverse frame response
# 3) energy only as a soft tie-breaker
DEFAULT_OPTIMIZATION_OBJECTIVES: tuple[str, ...] = (
    "метрика_комфорт__RMS_ускор_рамы_микро_м_с2",
    "метрика_крен_ay3_град",
    "метрика_энергия_дроссели_микро_Дж",
)


def objectives_text(objectives: Sequence[str] | None = None) -> str:
    seq = tuple(objectives or DEFAULT_OPTIMIZATION_OBJECTIVES)
    return "\n".join(str(x) for x in seq)


def _uniq_sorted_positive(values: Iterable[float], *, lo: float = 1e-6, hi: float = 0.25) -> tuple[float, ...]:
    cleaned: list[float] = []
    for raw in values:
        try:
            val = float(raw)
        except Exception:
            continue
        if not math.isfinite(val) or val <= 0.0:
            continue
        cleaned.append(float(min(max(val, lo), hi)))
    cleaned.sort()
    uniq: list[float] = []
    for val in cleaned:
        if not uniq or abs(val - uniq[-1]) > 1e-15:
            uniq.append(val)
    return tuple(uniq)


def parse_influence_eps_grid(raw: str | None, *, requested_eps_rel: float | None = None) -> tuple[float, ...]:
    vals: list[float] = []
    if isinstance(raw, str) and raw.strip():
        for chunk in raw.replace(";", ",").split(","):
            piece = chunk.strip()
            if not piece:
                continue
            try:
                vals.append(float(piece))
            except Exception:
                continue
    if requested_eps_rel is not None:
        try:
            vals.append(float(requested_eps_rel))
        except Exception:
            pass
    if not vals:
        vals = list(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID)
        if requested_eps_rel is not None:
            try:
                vals.append(float(requested_eps_rel))
            except Exception:
                pass
    return _uniq_sorted_positive(vals)


def influence_eps_grid_text(values: Sequence[float] | None = None) -> str:
    seq = tuple(float(x) for x in (values or DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID))
    return ", ".join(f"{x:g}" for x in seq)


def build_stage_aware_influence_profile(
    stage_name: str,
    *,
    requested_eps_rel: float,
    base_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    stage_key = str(stage_name or "").strip() or "stage1_long"
    spec = dict(_STAGE_AWARE_INFLUENCE_PROFILE_SPECS.get(stage_key, _STAGE_AWARE_INFLUENCE_PROFILE_SPECS["stage1_long"]))
    requested = max(float(requested_eps_rel), 1e-6)
    seed_grid = tuple(float(x) for x in (base_grid or DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID))
    lo = requested * float(spec["min_scale"])
    hi = requested * float(spec["max_scale"])

    vals: list[float] = [requested]
    vals.extend(seed_grid)
    vals.extend(requested * float(scale) for scale in tuple(spec.get("anchor_scales") or (1.0,)))

    filtered = [
        float(v)
        for v in vals
        if math.isfinite(float(v)) and (float(v) >= lo * (1.0 - 1e-12)) and (float(v) <= hi * (1.0 + 1e-12))
    ]
    grid = _uniq_sorted_positive(filtered)
    if not grid:
        grid = _uniq_sorted_positive([requested])

    return {
        "stage_name": stage_key,
        "profile_label": str(spec.get("label") or spec.get("adaptive_strategy") or "balanced"),
        "adaptive_strategy": str(spec.get("adaptive_strategy") or "balanced"),
        "requested_eps_rel": float(requested),
        "adaptive_grid": list(grid),
        "adaptive_grid_text": influence_eps_grid_text(grid),
        "min_scale": float(spec.get("min_scale", 1.0)),
        "max_scale": float(spec.get("max_scale", 1.0)),
        "anchor_scales": [float(x) for x in tuple(spec.get("anchor_scales") or ())],
    }


def stage_aware_influence_profiles_text(
    *,
    requested_eps_rel: float = DIAGNOSTIC_INFLUENCE_EPS_REL,
    base_grid: Sequence[float] | None = None,
) -> str:
    parts: list[str] = []
    for stage_name in ("stage0_relevance", "stage1_long", "stage2_final"):
        prof = build_stage_aware_influence_profile(
            stage_name,
            requested_eps_rel=float(requested_eps_rel),
            base_grid=base_grid,
        )
        parts.append(
            f"{stage_name}={prof['adaptive_grid_text']} [{prof['adaptive_strategy']}]"
        )
    return " · ".join(parts)


def diagnostics_jobs_default(cpu_count: int | None = None, *, platform_name: str | None = None) -> int:
    if cpu_count is None:
        cpu_count = os.cpu_count()
    cpu_n = max(1, int(cpu_count or 1))
    plat = str(platform_name or sys.platform)
    platform_cap = 61 if plat.startswith("win") else 128
    return int(max(1, min(cpu_n, platform_cap, DIAGNOSTIC_OPT_JOBS_HINT)))


def _read_scheme_fingerprint_meta(ui_root: Path) -> dict:
    fp = ui_root / "scheme_fingerprint.json"
    if not fp.exists():
        return {}
    try:
        obj = json.loads(fp.read_text("utf-8"))
        meta = obj.get("meta", {}) if isinstance(obj, dict) else {}
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def canonical_model_path(ui_root: Path) -> Path:
    meta = _read_scheme_fingerprint_meta(ui_root)
    mf = meta.get("model_file")
    if isinstance(mf, str) and mf.strip():
        p = Path(mf.strip())
        if not p.is_absolute():
            p = ui_root / p
        if p.exists():
            return p.resolve()
    p_cam = ui_root / "model_pneumo_v9_doublewishbone_camozzi.py"
    if p_cam.exists():
        return p_cam.resolve()
    p_world = ui_root / "model_pneumo_v9_mech_doublewishbone_worldroad.py"
    if p_world.exists():
        return p_world.resolve()
    return (ui_root / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py").resolve()


def canonical_worker_path(ui_root: Path) -> Path:
    return (ui_root / "opt_worker_v3_margins_energy.py").resolve()


def canonical_base_json_path(ui_root: Path) -> Path:
    return (ui_root / "default_base.json").resolve()


def canonical_ranges_json_path(ui_root: Path) -> Path:
    return (ui_root / "default_ranges.json").resolve()


def canonical_suite_json_path(ui_root: Path) -> Path:
    return (ui_root / "default_suite.json").resolve()


def diagnostics_suite_selected_id_if_present(records: Iterable[dict] | None) -> str:
    target = DIAGNOSTIC_SUITE_SELECTED_ID
    if not records:
        return ""
    try:
        for row in records:
            if str((row or {}).get("id") or "").strip() == target:
                return target
    except Exception:
        return ""
    return ""
