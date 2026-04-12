from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from pneumo_solver_ui.optimization_auto_ring_suite import (
    AUTO_RING_META_FILENAME,
    AUTO_RING_SUITE_SCHEMA_VERSION,
)


AUTO_TUNER_PLAN_SCHEMA_VERSION = "pneumo_opt_auto_tuner_plan_v1"
AUTO_TUNER_PLAN_DIRNAME = "optimization_auto_tuner"
AUTO_TUNER_PLAN_FILENAME = "stage_tuner_plan.json"


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def _clamp_int(value: Any, *, lo: int, hi: int) -> int:
    try:
        out = int(round(float(value)))
    except Exception:
        out = int(lo)
    return int(max(int(lo), min(int(hi), out)))


def _suite_rows(suite_json_path: str | Path) -> list[dict[str, Any]]:
    try:
        raw = _read_json(suite_json_path)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for rec in raw:
        if isinstance(rec, Mapping):
            out.append(dict(rec))
    return out


def _suite_meta_path(suite_json_path: str | Path) -> Path:
    return Path(suite_json_path).with_name(AUTO_RING_META_FILENAME)


def _suite_meta(suite_json_path: str | Path) -> dict[str, Any]:
    meta_path = _suite_meta_path(suite_json_path)
    if not meta_path.exists():
        return {}
    try:
        raw = _read_json(meta_path)
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def analyze_suite_family(
    suite_json_path: str | Path,
    *,
    rows: Sequence[Mapping[str, Any]] | None = None,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row_list = [dict(rec) for rec in (rows or _suite_rows(suite_json_path)) if isinstance(rec, Mapping)]
    meta_map = dict(meta or _suite_meta(suite_json_path))
    names = {str((rec or {}).get("имя") or "").strip() for rec in row_list if isinstance(rec, Mapping)}
    fragment_names = sorted(name for name in names if name.startswith("ringfrag_"))
    stage_counts: dict[int, int] = {}
    for rec in row_list:
        try:
            stage = int((rec or {}).get("стадия", 0) or 0)
        except Exception:
            stage = 0
        stage_counts[stage] = int(stage_counts.get(stage, 0) + 1)

    schema_version = str(meta_map.get("schema_version") or "").strip()
    has_full_ring = "ring_auto_full" in names
    is_auto_ring = bool(
        fragment_names
        or has_full_ring
        or schema_version == AUTO_RING_SUITE_SCHEMA_VERSION
    )
    family = "auto_ring" if is_auto_ring else "generic"
    return {
        "family": family,
        "schema_version": schema_version,
        "row_count": int(len(row_list)),
        "stage_counts": {str(int(k)): int(v) for k, v in sorted(stage_counts.items())},
        "fragment_count": int(len(fragment_names)),
        "fragment_names": list(fragment_names),
        "has_full_ring": bool(has_full_ring),
        "meta_path": str(_suite_meta_path(suite_json_path).resolve()) if _suite_meta_path(suite_json_path).exists() else "",
    }


def is_auto_ring_suite_json(suite_json_path: str | Path) -> bool:
    return str(analyze_suite_family(suite_json_path).get("family") or "") == "auto_ring"


def resolve_stage_tuner_stage_config(
    plan_payload: Mapping[str, Any] | None,
    stage_name: str,
) -> dict[str, Any]:
    payload = dict(plan_payload or {})
    target = str(stage_name or "").strip()
    if not target:
        return {}
    stages_obj = payload.get("stages")
    if isinstance(stages_obj, Mapping):
        rec = stages_obj.get(target)
        return dict(rec) if isinstance(rec, Mapping) else {}
    if isinstance(stages_obj, Sequence) and not isinstance(stages_obj, (str, bytes)):
        for rec in stages_obj:
            if not isinstance(rec, Mapping):
                continue
            if str(rec.get("stage_name") or "").strip() == target:
                return dict(rec)
    return {}


def _surrogate_scales(
    *,
    minutes_total: float,
    jobs_hint: int,
    fragment_count: int,
    has_full_ring: bool,
) -> tuple[float, float, float]:
    minutes_scale = max(0.85, min(2.20, float(minutes_total) / 10.0))
    jobs_scale = max(0.75, min(1.75, float(max(1, int(jobs_hint))) / 8.0))
    complexity = 1.0 + 0.06 * float(max(0, min(int(fragment_count), 8)))
    if has_full_ring:
        complexity += 0.10
    return float(minutes_scale), float(jobs_scale), float(complexity)


def build_optimization_auto_tuner_plan(
    suite_json_path: str | Path,
    *,
    minutes_total: float = 10.0,
    jobs_hint: int = 8,
) -> dict[str, Any]:
    suite_path = Path(suite_json_path).resolve()
    suite_meta = _suite_meta(suite_path)
    suite_info = analyze_suite_family(suite_path, meta=suite_meta)
    family = str(suite_info.get("family") or "generic")
    fragment_count = int(suite_info.get("fragment_count") or 0)
    has_full_ring = bool(suite_info.get("has_full_ring"))
    jobs_eff = max(1, int(jobs_hint))
    minutes_eff = max(0.5, float(minutes_total))

    minutes_scale, jobs_scale, complexity = _surrogate_scales(
        minutes_total=minutes_eff,
        jobs_hint=jobs_eff,
        fragment_count=fragment_count,
        has_full_ring=has_full_ring,
    )

    if family == "auto_ring":
        stage1_samples = _clamp_int(
            4096.0 * minutes_scale * jobs_scale * complexity,
            lo=4096,
            hi=16384,
        )
        stage2_samples = _clamp_int(
            12288.0 * minutes_scale * jobs_scale * (complexity + 0.10),
            lo=max(stage1_samples + 2048, 8192),
            hi=32768,
        )
        stage1_top_k = _clamp_int(stage1_samples / 128.0, lo=32, hi=96)
        stage2_top_k = _clamp_int(stage2_samples / 128.0, lo=max(stage1_top_k + 8, 48), hi=128)
        stage_specs = [
            {
                "stage_name": "stage0_relevance",
                "profile_name": "ring_broad_archive",
                "warmstart_mode": "archive",
                "surrogate_samples": 0,
                "surrogate_top_k": 0,
                "sort_tests_by_cost": 1,
                "guided_mode": "mutation",
                "env_overrides": {
                    "PNEUMO_GUIDED_MODE": "mutation",
                },
            },
            {
                "stage_name": "stage1_long",
                "profile_name": "ring_fragment_surrogate",
                "warmstart_mode": "surrogate",
                "surrogate_samples": int(stage1_samples),
                "surrogate_top_k": int(stage1_top_k),
                "sort_tests_by_cost": 1,
                "guided_mode": "auto",
                "env_overrides": {
                    "PNEUMO_GUIDED_MODE": "auto",
                    "PNEUMO_CEM_MIX": "0.55",
                    "PNEUMO_AUTO_PATIENCE": "20",
                },
            },
            {
                "stage_name": "stage2_final",
                "profile_name": "ring_fullring_exploit",
                "warmstart_mode": "surrogate",
                "surrogate_samples": int(stage2_samples),
                "surrogate_top_k": int(stage2_top_k),
                "sort_tests_by_cost": 1,
                "guided_mode": "auto",
                "env_overrides": {
                    "PNEUMO_GUIDED_MODE": "auto",
                    "PNEUMO_CEM_ALPHA": "0.20",
                    "PNEUMO_CEM_MIX": "0.70",
                    "PNEUMO_AUTO_PATIENCE": "12",
                    "PNEUMO_AUTO_REHEAT_SIGMA": "0.25",
                },
            },
        ]
        handoff = {
            "recommended_pipeline": "staged_then_coordinator",
            "recommended_proposer": "portfolio",
            "recommended_q": int(2 if jobs_eff >= 8 else 1),
            "requires_full_ring_validation": True,
        }
    else:
        stage1_samples = _clamp_int(
            4096.0 * minutes_scale * jobs_scale,
            lo=2048,
            hi=12288,
        )
        stage2_samples = _clamp_int(
            8192.0 * minutes_scale * jobs_scale,
            lo=max(stage1_samples + 1024, 4096),
            hi=24576,
        )
        stage_specs = [
            {
                "stage_name": "stage0_relevance",
                "profile_name": "generic_archive",
                "warmstart_mode": "archive",
                "surrogate_samples": 0,
                "surrogate_top_k": 0,
                "sort_tests_by_cost": 1,
                "guided_mode": "mutation",
                "env_overrides": {
                    "PNEUMO_GUIDED_MODE": "mutation",
                },
            },
            {
                "stage_name": "stage1_long",
                "profile_name": "generic_surrogate",
                "warmstart_mode": "surrogate",
                "surrogate_samples": int(stage1_samples),
                "surrogate_top_k": int(_clamp_int(stage1_samples / 160.0, lo=24, hi=64)),
                "sort_tests_by_cost": 1,
                "guided_mode": "auto",
                "env_overrides": {
                    "PNEUMO_GUIDED_MODE": "auto",
                },
            },
            {
                "stage_name": "stage2_final",
                "profile_name": "generic_final_surrogate",
                "warmstart_mode": "surrogate",
                "surrogate_samples": int(stage2_samples),
                "surrogate_top_k": int(_clamp_int(stage2_samples / 160.0, lo=32, hi=96)),
                "sort_tests_by_cost": 1,
                "guided_mode": "auto",
                "env_overrides": {
                    "PNEUMO_GUIDED_MODE": "auto",
                    "PNEUMO_CEM_MIX": "0.60",
                },
            },
        ]
        handoff = {
            "recommended_pipeline": "staged_only",
            "recommended_proposer": "auto",
            "recommended_q": 1,
            "requires_full_ring_validation": False,
        }

    return {
        "schema_version": AUTO_TUNER_PLAN_SCHEMA_VERSION,
        "suite_json": str(suite_path),
        "suite_family": str(family),
        "suite_analysis": dict(suite_info),
        "minutes_total": float(minutes_eff),
        "jobs_hint": int(jobs_eff),
        "heuristics": {
            "minutes_scale": float(minutes_scale),
            "jobs_scale": float(jobs_scale),
            "complexity": float(complexity),
        },
        "stages": list(stage_specs),
        "coordinator_handoff": dict(handoff),
    }


def materialize_optimization_auto_tuner_plan_json(
    workspace_dir: str | Path,
    *,
    suite_json_path: str | Path,
    minutes_total: float = 10.0,
    jobs_hint: int = 8,
) -> Path:
    workspace = Path(workspace_dir).resolve()
    root = workspace / "ui_state" / AUTO_TUNER_PLAN_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    plan = build_optimization_auto_tuner_plan(
        suite_json_path,
        minutes_total=float(minutes_total),
        jobs_hint=int(jobs_hint),
    )
    out_path = root / AUTO_TUNER_PLAN_FILENAME
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


__all__ = [
    "AUTO_TUNER_PLAN_DIRNAME",
    "AUTO_TUNER_PLAN_FILENAME",
    "AUTO_TUNER_PLAN_SCHEMA_VERSION",
    "analyze_suite_family",
    "build_optimization_auto_tuner_plan",
    "is_auto_ring_suite_json",
    "materialize_optimization_auto_tuner_plan_json",
    "resolve_stage_tuner_stage_config",
]
