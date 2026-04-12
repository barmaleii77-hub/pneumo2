from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import pandas as pd

from pneumo_solver_ui.optimization_auto_tuner_plan import analyze_suite_family
from pneumo_solver_ui.optimization_objective_contract import score_tuple_from_row
from pneumo_solver_ui.optimization_result_rows import is_promotable_row


COORDINATOR_HANDOFF_SCHEMA_VERSION = "pneumo_opt_coordinator_handoff_v1"
COORDINATOR_HANDOFF_DIRNAME = "coordinator_handoff"
COORDINATOR_HANDOFF_PLAN_FILENAME = "coordinator_handoff_plan.json"
COORDINATOR_HANDOFF_SEED_FILENAME = "coordinator_seed_points.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def _stable_obj_hash(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _read_json_mapping(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _extract_params_from_row(row: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in dict(row or {}).items():
        if not isinstance(key, str) or not key.startswith("параметр__"):
            continue
        name = str(key.split("__", 1)[1] or "").strip()
        if not name:
            continue
        try:
            out[name] = float(value)
        except Exception:
            continue
    return out


def _row_ok_mask(df: pd.DataFrame) -> pd.Series:
    mask_ok = pd.Series(True, index=df.index)
    for col in ("ошибка", "error"):
        if col in df.columns:
            s = df[col]
            ok = s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower().str.strip() == "nan")
            mask_ok &= ok
    return mask_ok


def _clip_params_to_ranges(params: Mapping[str, Any], ranges: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    ranges_map = dict(ranges or {})
    for name, bounds in ranges_map.items():
        if name not in params:
            continue
        if not isinstance(bounds, (list, tuple)) or len(bounds) < 2:
            continue
        try:
            lo = float(bounds[0])
            hi = float(bounds[1])
            cur = float(params[name])
        except Exception:
            continue
        if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
            continue
        out[str(name)] = float(min(max(cur, lo), hi))
    return out


def _select_handoff_seed_bridge(
    staged_results_csv: str | Path,
    *,
    ranges_payload: Mapping[str, Any] | None = None,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    seed_limit: int = 16,
) -> dict[str, Any]:
    limit = max(1, int(seed_limit))
    info: dict[str, Any] = {
        "seed_limit": int(limit),
        "staged_rows_total": 0,
        "staged_rows_ok": 0,
        "promotable_rows": 0,
        "selection_pool": "none",
        "unique_param_candidates": 0,
        "seed_count": 0,
    }
    csv_path = Path(staged_results_csv)
    if not csv_path.exists() or csv_path.stat().st_size <= 0:
        return {"seed_params": [], "seed_bridge": info}
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return {"seed_params": [], "seed_bridge": info}
    if df.empty:
        return {"seed_params": [], "seed_bridge": info}
    info["staged_rows_total"] = int(len(df))
    df = df[_row_ok_mask(df)].copy()
    info["staged_rows_ok"] = int(len(df))
    rows = df.to_dict(orient="records")
    promotable_rows = [row for row in rows if is_promotable_row(row)]
    info["promotable_rows"] = int(len(promotable_rows))
    rows_eff = promotable_rows or rows
    info["selection_pool"] = "promotable" if promotable_rows else ("ok_rows" if rows else "none")
    rows_eff = sorted(
        rows_eff,
        key=lambda row: tuple(score_tuple_from_row(row, objective_keys=objective_keys, penalty_key=penalty_key)),
    )

    seen: set[str] = set()
    out: list[dict[str, float]] = []
    for row in rows_eff:
        params = _extract_params_from_row(row)
        if ranges_payload:
            params = _clip_params_to_ranges(params, ranges_payload)
        if not params:
            continue
        sig = _stable_obj_hash(params)
        if sig in seen:
            continue
        seen.add(sig)
        if len(out) < limit:
            out.append(dict(params))
    info["unique_param_candidates"] = int(len(seen))
    info["seed_count"] = int(len(out))
    return {"seed_params": out, "seed_bridge": info}


def select_handoff_seed_params(
    staged_results_csv: str | Path,
    *,
    ranges_payload: Mapping[str, Any] | None = None,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    seed_limit: int = 16,
) -> list[dict[str, float]]:
    return list(
        _select_handoff_seed_bridge(
            staged_results_csv,
            ranges_payload=ranges_payload,
            objective_keys=objective_keys,
            penalty_key=penalty_key,
            seed_limit=seed_limit,
        ).get("seed_params")
        or []
    )


def _recommended_budget(
    *,
    suite_info: Mapping[str, Any],
    seed_count: int,
    requested_budget: Any = None,
) -> int:
    try:
        if requested_budget is not None:
            return max(1, int(requested_budget))
    except Exception:
        pass
    fragment_count = int(suite_info.get("fragment_count") or 0)
    has_full_ring = bool(suite_info.get("has_full_ring"))
    base = 40 + 4 * max(0, fragment_count) + 2 * max(0, int(seed_count))
    if has_full_ring:
        base += 24
    return int(max(48, min(192, base)))


def materialize_coordinator_handoff_plan(
    run_dir: str | Path,
    *,
    model_path: str | Path,
    worker_path: str | Path,
    base_json_path: str | Path,
    ranges_json_path: str | Path,
    suite_json_path: str | Path,
    staged_results_csv: str | Path,
    objective_keys: Sequence[str] | None,
    penalty_key: str,
    stage_tuner_plan: Mapping[str, Any] | None = None,
    budget: Any = None,
    seed_limit: int = 16,
) -> Path:
    run_root = Path(run_dir).resolve()
    handoff_dir = run_root / COORDINATOR_HANDOFF_DIRNAME
    handoff_dir.mkdir(parents=True, exist_ok=True)

    suite_path = Path(suite_json_path).resolve()
    ranges_payload = _read_json_mapping(ranges_json_path)
    suite_info = analyze_suite_family(suite_path)
    tuner_payload = dict(stage_tuner_plan or {})
    handoff_cfg = dict(tuner_payload.get("coordinator_handoff") or {}) if isinstance(tuner_payload.get("coordinator_handoff"), Mapping) else {}

    seed_selection = _select_handoff_seed_bridge(
        staged_results_csv,
        ranges_payload=ranges_payload,
        objective_keys=objective_keys,
        penalty_key=penalty_key,
        seed_limit=max(1, int(seed_limit)),
    )
    seed_params = list(seed_selection.get("seed_params") or [])
    seed_bridge = dict(seed_selection.get("seed_bridge") or {})
    seed_json_path = handoff_dir / COORDINATOR_HANDOFF_SEED_FILENAME
    seed_json_path.write_text(json.dumps(seed_params, ensure_ascii=False, indent=2), encoding="utf-8")

    budget_eff = _recommended_budget(
        suite_info=suite_info,
        seed_count=len(seed_params),
        requested_budget=budget,
    )
    proposer = str(handoff_cfg.get("recommended_proposer") or "auto").strip() or "auto"
    q_eff = max(1, int(handoff_cfg.get("recommended_q") or 1))
    backend_eff = str(handoff_cfg.get("recommended_backend") or "ray").strip().lower() or "ray"
    requires_full_ring_validation = bool(handoff_cfg.get("requires_full_ring_validation", False))
    pipeline_hint = str(handoff_cfg.get("recommended_pipeline") or "").strip() or (
        "staged_then_coordinator" if requires_full_ring_validation else "staged_only"
    )
    fragment_count = int(suite_info.get("fragment_count") or 0)
    has_full_ring = bool(suite_info.get("has_full_ring"))
    budget_formula = {
        "base": 40,
        "per_fragment": 4,
        "per_seed": 2,
        "full_ring_bonus": 24 if has_full_ring else 0,
    }

    cmd_args: list[str] = [
        "--backend",
        str(backend_eff),
        "--run-dir",
        str((handoff_dir / "run").resolve()),
        "--model",
        str(Path(model_path).resolve()),
        "--worker",
        str(Path(worker_path).resolve()),
        "--base-json",
        str(Path(base_json_path).resolve()),
        "--ranges-json",
        str(Path(ranges_json_path).resolve()),
        "--suite-json",
        str(suite_path),
        "--budget",
        str(int(budget_eff)),
        "--proposer",
        str(proposer),
        "--q",
        str(int(q_eff)),
        "--seed-json",
        str(seed_json_path.resolve()),
        "--penalty-key",
        str(penalty_key),
    ]
    for key in list(objective_keys or ()):
        cmd_args += ["--objective", str(key)]

    payload = {
        "schema_version": COORDINATOR_HANDOFF_SCHEMA_VERSION,
        "run_dir": str(run_root),
        "staged_results_csv": str(Path(staged_results_csv).resolve()),
        "suite_json": str(suite_path),
        "suite_analysis": dict(suite_info),
        "seed_json": str(seed_json_path.resolve()),
        "seed_count": int(len(seed_params)),
        "seed_limit": int(max(1, int(seed_limit))),
        "objective_keys": list(objective_keys or ()),
        "penalty_key": str(penalty_key),
        "coordinator_handoff": dict(handoff_cfg),
        "recommended_backend": str(backend_eff),
        "recommended_proposer": str(proposer),
        "recommended_q": int(q_eff),
        "recommended_budget": int(budget_eff),
        "requires_full_ring_validation": requires_full_ring_validation,
        "recommendation_reason": {
            "suite_family": str(suite_info.get("family") or ""),
            "fragment_count": int(fragment_count),
            "has_full_ring": bool(has_full_ring),
            "stage_counts": dict(suite_info.get("stage_counts") or {}),
            "seed_bridge": dict(seed_bridge),
            "budget_formula": dict(budget_formula),
            "pipeline_hint": str(pipeline_hint),
            "proposer_source": "auto_tuner" if str(handoff_cfg.get("recommended_proposer") or "").strip() else "default",
            "q_source": "auto_tuner" if "recommended_q" in handoff_cfg else "default",
        },
        "cmd_args": list(cmd_args),
    }
    plan_path = handoff_dir / COORDINATOR_HANDOFF_PLAN_FILENAME
    plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path


__all__ = [
    "COORDINATOR_HANDOFF_DIRNAME",
    "COORDINATOR_HANDOFF_PLAN_FILENAME",
    "COORDINATOR_HANDOFF_SCHEMA_VERSION",
    "COORDINATOR_HANDOFF_SEED_FILENAME",
    "materialize_coordinator_handoff_plan",
    "select_handoff_seed_params",
]
