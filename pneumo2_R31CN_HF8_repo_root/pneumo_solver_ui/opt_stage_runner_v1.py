#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Staged optimization orchestrator for UnifiedPneumoApp.

Why:
- Resume-friendly: keeps a stable run directory and stage outputs.
- Multi-stage (multi-fidelity) pipeline: Stage0 (cheap relevance), Stage1 (long tests), Stage2 (final).
- Parameter dimension grows by stages using influence-based staging (pneumatics/kinematics aware).
- Reuses all previous results via a global JSONL archive to warm-start CEM state.

This runner is designed to be launched by the Streamlit UI.

It orchestrates the existing worker (opt_worker_v3_margins_energy.py) via subprocess calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from pneumo_dist.trial_hash import hash_file, stable_hash_problem

_THIS = Path(__file__).resolve()
_PNEUMO_ROOT = _THIS.parent  # .../pneumo_solver_ui
_PROJECT_ROOT = _PNEUMO_ROOT.parent  # .../project root
for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _prepend_pythonpath(env: Dict[str, str], *paths: Path) -> None:
    extras = [str(Path(p).resolve()) for p in paths if str(p)]
    existing = [x for x in str(env.get("PYTHONPATH", "")).split(os.pathsep) if x]
    merged = []
    for item in [*extras, *existing]:
        if item and item not in merged:
            merged.append(item)
    if merged:
        env["PYTHONPATH"] = os.pathsep.join(merged)


try:
    from sklearn.ensemble import ExtraTreesRegressor
except Exception:  # pragma: no cover
    ExtraTreesRegressor = None


from pneumo_solver_ui.name_sanitize import sanitize_id
from pneumo_solver_ui.optimization_baseline_source import (
    resolve_workspace_baseline_source,
    write_baseline_source_artifact,
)
from pneumo_solver_ui.optimization_problem_hash_mode import (
    problem_hash_mode_from_env,
    write_problem_hash_mode_artifact,
)
from pneumo_solver_ui.optimization_input_contract import (
    describe_runtime_stage,
    infer_suite_stage,
    sanitize_optimization_inputs,
)
from pneumo_solver_ui.optimization_defaults import (
    build_stage_aware_influence_profile,
    influence_eps_grid_text,
    parse_influence_eps_grid,
)
from pneumo_solver_ui.optimization_objective_contract import (
    lexicographic_is_better,
    normalize_objective_keys,
    normalize_penalty_key,
    objective_contract_payload,
    parse_saved_score_payload,
    scalarize_score_tuple,
    score_contract_matches,
    score_payload,
    score_tuple_from_row,
)
from pneumo_solver_ui.optimization_stage_policy import (
    DEFAULT_STAGE_POLICY_MODE,
    build_stage_seed_budget_plan,
    build_stage_specific_influence_summary,
    compute_param_delta_norm,
    compute_stage_alignment,
    promotion_sort_key,
)
from pneumo_solver_ui.optimization_progress_live import csv_data_row_count
from pneumo_solver_ui.optimization_result_rows import (
    BASELINE_ROLE,
    is_baseline_row,
    is_promotable_row,
)
from pneumo_solver_ui.optimization_runtime_paths import (
    console_python_executable,
    stage_fs_name,
    stage_out_csv_name,
    stage_worker_progress_path,
)


from pneumo_solver_ui.process_tree import terminate_process_tree

from pneumo_solver_ui.atomic_write_retry import atomic_write_json_retry


def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _sha1_bytes(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(data)
    return h.hexdigest()


def _file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_obj_hash(obj: Any) -> str:
    return _sha1_bytes(_stable_json_dumps(obj).encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_jsonish(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (dict, list)):
        return x
    if isinstance(x, (int, float, bool)):
        return x
    if not isinstance(x, str):
        return x
    s = x.strip()
    if not s:
        return ""
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            return x
    return x


def infer_test_stage(rec: Dict[str, Any]) -> int:
    """Compatibility wrapper over the canonical suite-stage contract.

    Convention:
      0 - cheap relevance (micro + inertia)
      1 - long tests, road profiles
      2 - final robustness (more scenarios)

    Runtime must use exactly the same inference/clamp logic as the UI/editor and
    autosave state. Negative stages are forbidden and missing stages are inferred
    explicitly instead of being left as NaN/None in one layer and re-guessed in another.
    """
    return int(infer_suite_stage(rec))


def _suite_test_name(rec: Dict[str, Any]) -> str:
    """Return canonical suite-row name across RU/EN historical schemas."""
    if not isinstance(rec, dict):
        return ""
    for key in ("имя", "name", "id"):
        try:
            value = rec.get(key, "")
        except Exception:
            value = ""
        s = str(value or "").strip()
        if s:
            return s
    return ""


@dataclass
class Scenario:
    sid: str
    title: str
    mods: Dict[str, Dict[str, Any]]  # {param: {op: 'mul'/'add'/'set', value: ...}}


def build_default_scenarios(base_params: Dict[str, Any]) -> List[Scenario]:
    """Return a robust yet safe scenario matrix.

    NOTE: we resolve operations against base_params to produce explicit overrides.
    """
    # Helpers to pick base values safely
    def _base(k: str, default: float) -> float:
        try:
            return float(base_params.get(k, default))
        except Exception:
            return float(default)

    p_acc0 = _base("начальное_давление_аккумулятора", 4.053e5)

    return [
        Scenario(
            sid="nominal",
            title="Номинал",
            mods={},
        ),
        Scenario(
            sid="heavy",
            title="Пассажиры/груз",
            mods={
                # New optional param supported by the model (added in v6.26+):
                "добавочная_масса_кг": {"op": "set", "value": 400.0},
            },
        ),
        Scenario(
            sid="cold",
            title="Холод",
            mods={
                "T_AIR_К": {"op": "set", "value": 253.15},
                "начальное_давление_аккумулятора": {"op": "set", "value": 0.92 * p_acc0},
            },
        ),
        Scenario(
            sid="hot",
            title="Жара",
            mods={
                "T_AIR_К": {"op": "set", "value": 313.15},
            },
        ),
        Scenario(
            sid="lowP",
            title="Низкое начальное давление",
            mods={
                "начальное_давление_аккумулятора": {"op": "set", "value": 0.80 * p_acc0},
            },
        ),
    ]


def resolve_overrides(base_params: Dict[str, Any], scenario: Scenario) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, spec in (scenario.mods or {}).items():
        op = str(spec.get("op", "set")).lower().strip()
        val = spec.get("value", None)
        if op == "set":
            out[k] = val
            continue
        base_v = base_params.get(k, 0.0)
        try:
            base_f = float(base_v)
        except Exception:
            base_f = 0.0
        try:
            v = float(val)
        except Exception:
            v = 0.0
        if op == "mul":
            out[k] = base_f * v
        elif op == "add":
            out[k] = base_f + v
        else:
            out[k] = val
    return out


def filter_and_scale_suite(
    suite: List[Dict[str, Any]],
    *,
    max_stage: int,
    dt_scale: float,
    t_end_scale: float,
    keep_enabled_only: bool = True,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in suite:
        if not isinstance(rec, dict):
            continue
        if keep_enabled_only and not bool(rec.get("включен", True)):
            continue
        stg = infer_test_stage(rec)
        if stg > max_stage:
            continue
        r = dict(rec)
        # Make stage explicit for future reuse
        r["стадия"] = stg
        # Fidelity scaling
        try:
            if r.get("dt", None) not in (None, ""):
                r["dt"] = float(r["dt"]) * float(dt_scale)
        except Exception:
            pass
        try:
            if r.get("t_end", None) not in (None, ""):
                r["t_end"] = float(r["t_end"]) * float(t_end_scale)
        except Exception:
            pass
        out.append(r)
    return out


def expand_suite_by_scenarios(
    suite_tests: List[Dict[str, Any]],
    scenario_matrix: List[Scenario] | Dict[str, Any],
    base_params: Optional[Dict[str, Any]] = None,
    scenario_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Expand suite tests by scenario matrix.

    Supports both:
      - List[Scenario] returned by ``build_default_scenarios``
      - Dict[str, dict] with already-resolved ``params_override`` payloads

    ``base_params`` is only required when scenario entries still contain relative
    operations (mul/add/set) and must be resolved against the current base.
    """

    scenario_map: Dict[str, Any] = {}
    if isinstance(scenario_matrix, dict):
        scenario_map = {str(k): v for k, v in scenario_matrix.items()}
    else:
        for sc in scenario_matrix or []:
            if isinstance(sc, Scenario):
                scenario_map[str(sc.sid)] = sc

    if scenario_ids is None:
        scenario_ids = list(scenario_map.keys())

    nominal_aliases = {"nominal", "base", "default", ""}
    out: List[Dict[str, Any]] = []

    for t in suite_tests:
        base_name = _suite_test_name(t)
        if not base_name:
            continue

        for scenario_id in scenario_ids:
            scenario_id_s = str(scenario_id)
            scenario_obj = scenario_map.get(scenario_id_s)

            overrides: Dict[str, Any] = {}
            if isinstance(scenario_obj, Scenario):
                overrides = resolve_overrides(base_params or {}, scenario_obj)
            elif isinstance(scenario_obj, dict):
                overrides = dict(scenario_obj)

            if scenario_id_s in nominal_aliases:
                name = base_name
            else:
                name = f"{base_name}__sc_{scenario_id_s}"

            r = dict(t)
            r["name"] = name
            r["имя"] = name
            r["_meta_base_test"] = base_name
            r["_meta_scenario_id"] = scenario_id_s

            po = parse_jsonish(r.get("params_override"))
            if isinstance(po, dict) and po:
                merged = dict(po)
                merged.update(overrides)
                overrides = merged

            r["params_override"] = overrides
            out.append(r)

    return out


def score_row(
    row: Dict[str, Any],
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
) -> Tuple[float, ...]:
    """Return a lexicographic score tuple under the shared objective contract.

    Penalty stays first, then the active objective stack in the exact order used by
    the distributed coordinator / UI. Historical alias keys are still accepted by
    ``score_tuple_from_row`` so old CSV/archive rows remain readable.
    """

    return tuple(
        score_tuple_from_row(
            row,
            objective_keys=objective_keys,
            penalty_key=penalty_key,
        )
    )


def pick_best_row(
    csv_path: Path,
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
) -> Optional[Dict[str, Any]]:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None
    if df.empty:
        return None

    # Фильтруем строки с ошибками. В разных версиях воркера колонка могла называться
    # "ошибка" (RU) или "error" (EN).
    mask_ok = pd.Series(True, index=df.index)
    for col in ("ошибка", "error"):
        if col in df.columns:
            s = df[col]
            # ok: NaN, пусто, или строка 'nan'
            ok = s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower().str.strip() == "nan")
            mask_ok &= ok
    df2 = df[mask_ok].copy()
    if not df2.empty:
        df = df2

    rows = df.to_dict(orient="records")
    promotable_rows = [r for r in rows if is_promotable_row(r)]
    rows_eff = promotable_rows or rows
    rows_sorted = sorted(
        rows_eff,
        key=lambda row: score_row(row, objective_keys=objective_keys, penalty_key=penalty_key),
    )
    return rows_sorted[0] if rows_sorted else None


def extract_params_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if not isinstance(k, str):
            continue
        if k.startswith("параметр__"):
            pname = k.split("__", 1)[1]
            out[pname] = v
    return out


def _clip_params_to_ranges(params: Dict[str, Any], ranges: Dict[str, Any]) -> Dict[str, float]:
    """Оставляет только параметры из ranges и клипает значения к [lo, hi]."""
    out: Dict[str, float] = {}
    for pnm, bnd in (ranges or {}).items():
        try:
            lo, hi = float(bnd[0]), float(bnd[1])
        except Exception:
            continue
        if hi <= lo:
            continue
        if pnm not in params:
            continue
        try:
            v = float(params.get(pnm))
        except Exception:
            continue
        if not np.isfinite(v):
            continue
        v = float(np.clip(v, lo, hi))
        out[pnm] = v
    return out


def _archive_contract_payload(rec: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(rec, Mapping):
        return None
    raw = rec.get("objective_contract")
    if isinstance(raw, Mapping):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, Mapping):
                return parsed
    raw_score_payload = rec.get("score_payload")
    if isinstance(raw_score_payload, Mapping):
        return raw_score_payload
    if "objective_keys" in rec or "penalty_key" in rec:
        return rec
    return None


def archive_record_compatibility_kind(
    rec: Mapping[str, Any] | None,
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    problem_hash: str | None = None,
) -> str:
    if not isinstance(rec, Mapping):
        return "invalid"
    contract_payload = _archive_contract_payload(rec)
    if contract_payload is not None and not score_contract_matches(
        contract_payload,
        objective_keys=objective_keys,
        penalty_key=penalty_key,
    ):
        return "contract_mismatch"
    current_problem_hash = str(problem_hash or "").strip()
    saved_problem_hash = str(rec.get("problem_hash") or "").strip()
    if current_problem_hash and saved_problem_hash and current_problem_hash == saved_problem_hash:
        return "same_problem"
    if contract_payload is not None:
        return "same_contract"
    return "legacy_unknown"


def _preferred_archive_bucket_name(
    bucketed: Mapping[str, Sequence[Any]] | None,
    *,
    min_count: int = 1,
) -> str:
    buckets = dict(bucketed or {})
    same_problem = list(buckets.get("same_problem") or [])
    same_contract = list(buckets.get("same_contract") or [])
    legacy_unknown = list(buckets.get("legacy_unknown") or [])
    min_n = int(max(1, min_count))

    if len(same_problem) >= min_n:
        return "same_problem"
    if len(same_contract) >= min_n:
        return "same_contract"
    if same_problem:
        return "same_problem"
    if same_contract:
        return "same_contract"
    if len(legacy_unknown) >= min_n:
        return "legacy_unknown"
    if legacy_unknown:
        return "legacy_unknown"
    return ""


def baseline_problem_scope_dir(baseline_dir: Path, problem_hash: str | None) -> Path:
    token = sanitize_id(str(problem_hash or "").strip()) or "unknown_problem"
    return Path(baseline_dir) / "by_problem" / f"p_{token}"


def baseline_best_meta_payload(
    *,
    problem_hash: str | None,
    objective_contract: Mapping[str, Any] | None,
    run_dir: Path,
    stage_name: str,
    score: Sequence[float],
    score_payload_obj: Mapping[str, Any] | None,
    params: Mapping[str, Any] | None,
    source: str = "opt_stage_runner_v1_baseline",
) -> Dict[str, Any]:
    return {
        "version": "baseline_best_meta_v1",
        "source": str(source or "opt_stage_runner_v1_baseline"),
        "problem_hash": str(problem_hash or "").strip(),
        "run_dir": str(Path(run_dir)),
        "stage_name": str(stage_name or "").strip(),
        "objective_contract": dict(objective_contract or {}),
        "score": [float(x) for x in score],
        "score_payload": dict(score_payload_obj or {}),
        "params": dict(params or {}),
    }


def load_baseline_best_meta(
    baseline_dir: Path,
    *,
    prev_score_raw: Any = None,
) -> Dict[str, Any]:
    meta_path = Path(baseline_dir) / "baseline_best_meta.json"
    if meta_path.exists():
        try:
            payload = load_json(meta_path)
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            return dict(payload)

    raw = prev_score_raw if isinstance(prev_score_raw, Mapping) else {}
    if not isinstance(raw, Mapping):
        return {}

    objective_contract = _archive_contract_payload(raw)
    problem_hash = str(raw.get("problem_hash") or "").strip()
    if not problem_hash and objective_contract is None:
        return {}

    return {
        "version": "baseline_best_meta_fallback_v1",
        "source": str(raw.get("source") or "baseline_best_score_fallback"),
        "problem_hash": problem_hash,
        "run_dir": str(raw.get("run_dir") or "").strip(),
        "stage_name": str(raw.get("stage_name") or "").strip(),
        "objective_contract": dict(objective_contract or {}),
        "score_payload": dict(raw) if isinstance(raw, dict) else {},
    }


def decide_baseline_autoupdate(
    *,
    new_score: Sequence[float],
    objective_keys: Sequence[str] | None,
    penalty_key: str | None,
    problem_hash: str | None,
    prev_score_payload: Mapping[str, Any] | None,
    prev_meta: Mapping[str, Any] | None,
) -> Tuple[bool, str]:
    prev_meta_dict = dict(prev_meta or {})
    prev_problem_hash = str(prev_meta_dict.get("problem_hash") or "").strip()
    prev_contract = _archive_contract_payload(prev_meta_dict)
    prev_scope_explicit = bool(prev_problem_hash or prev_contract)
    current_problem_hash = str(problem_hash or "").strip()

    if prev_problem_hash and current_problem_hash and prev_problem_hash != current_problem_hash:
        return False, "different_problem_hash"
    if prev_contract is not None and not score_contract_matches(
        prev_contract,
        objective_keys=objective_keys,
        penalty_key=penalty_key,
    ):
        return False, "different_objective_contract"

    if isinstance(prev_score_payload, Mapping):
        prev_score_vals = list(prev_score_payload.get("score") or [])
        if score_contract_matches(prev_score_payload, objective_keys=objective_keys, penalty_key=penalty_key):
            better = lexicographic_is_better(new_score, prev_score_vals)
            return better, "better_same_contract" if better else "not_better_same_contract"
        if prev_scope_explicit:
            return False, "scoped_baseline_without_comparable_score"
        return True, "objective_contract_changed"

    if prev_scope_explicit:
        return False, "scoped_baseline_without_score"
    return True, "first_score"


def collect_seed_points(
    stage_idx: int,
    stage_csvs: List[Tuple[str, Path]],
    archive_path: Path,
    ranges: Dict[str, Any],
    *,
    base_params: Optional[Dict[str, Any]] = None,
    stage_name: str = "",
    stage_policy_mode: str = "static",
    stage_influence_summary: Optional[Dict[str, Any]] = None,
    budget_plan: Optional[Dict[str, Any]] = None,
    promotion_log_path: Optional[Path] = None,
    seed_manifest_json_path: Optional[Path] = None,
    seed_manifest_csv_path: Optional[Path] = None,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    problem_hash: str | None = None,
    max_prev: int = 24,
    max_archive: int = 24,
    max_total: int = 48,
    min_coverage: float = 0.6,
) -> List[Dict[str, Any]]:
    """Prepare seed points for the worker (``--seed_points_json``).

    Static mode preserves the historical behaviour:
    - promote best rows from the previous stage first;
    - then append best rows from the global archive.

    Influence-weighted mode adds a stage-specific policy layer on top:
    - stage summaries restrict attention to currently active parameters;
    - later stages get a smaller top-k and lower exploratory seed budget;
    - promotion ranking favours candidates whose parameter deltas align with the
      current stage priorities instead of relying only on raw score order.
    """
    max_prev = int(max(0, max_prev))
    max_archive = int(max(0, max_archive))
    max_total = int(max(1, max_total))

    try:
        min_cov = float(os.environ.get("PNEUMO_WARMSTART_MIN_COVERAGE", str(min_coverage)))
    except Exception:
        min_cov = float(min_coverage)
    min_cov = max(0.0, min(1.0, float(min_cov)))

    names = list((ranges or {}).keys())
    d = int(len(names))
    base_params_map = dict(base_params or {})
    stage_summary = dict(stage_influence_summary or {})
    stage_name_s = str(stage_name or "").strip() or (stage_csvs[stage_idx][0] if stage_idx < len(stage_csvs) else "")
    requested_mode = str(stage_policy_mode or "static").strip() or "static"
    budget = dict(budget_plan or {})
    effective_mode = str(budget.get("effective_mode") or requested_mode).strip() or requested_mode

    def _candidate_from_row(
        rec: Dict[str, Any],
        *,
        source: str,
        source_stage: str,
        source_order: int,
        coverage_override: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        params_raw = extract_params_from_row(rec)
        params_clipped = _clip_params_to_ranges(params_raw, ranges)
        if not params_clipped:
            return None
        coverage = float(coverage_override) if coverage_override is not None else (float(len(params_clipped)) / float(d) if d > 0 else 0.0)
        if coverage < float(min_cov):
            return None
        delta_norm = compute_param_delta_norm(params_clipped, base_params=base_params_map, ranges=ranges)
        alignment = compute_stage_alignment(stage_summary, delta_norm)
        score_t = tuple(float(x) for x in score_row(rec, objective_keys=objective_keys, penalty_key=penalty_key))
        rid = None
        try:
            rid = int(rec.get("id"))
        except Exception:
            rid = None
        clean = dict(params_clipped)
        param_hash = stable_obj_hash(clean)
        source_pref = 0 if str(source).startswith("prev") else 1
        return {
            "source": str(source),
            "source_stage": str(source_stage),
            "source_order": int(source_order),
            "source_pref": int(source_pref),
            "row_id": rid,
            "score_tuple": score_t,
            "coverage": float(coverage),
            "clean_params": clean,
            "param_hash": str(param_hash),
            "delta_norm": dict(delta_norm),
            "alignment": float(alignment.get("alignment", 0.0) or 0.0),
            "off_axis_sprawl": float(alignment.get("off_axis_sprawl", 0.0) or 0.0),
            "dominant_stage_params": list(alignment.get("dominant_stage_params") or []),
            "priority_touched_count": int(alignment.get("priority_touched_count", 0) or 0),
        }

    prev_candidates: List[Dict[str, Any]] = []
    archive_candidates: List[Dict[str, Any]] = []

    # --- 1) Promotion: collect promotable rows from the previous stage ---
    if stage_idx > 0 and max_prev > 0 and len(stage_csvs) >= stage_idx:
        prev_name, prev_csv = stage_csvs[stage_idx - 1]
        try:
            if prev_csv.exists() and prev_csv.stat().st_size > 0:
                dfp = pd.read_csv(prev_csv)
                if not dfp.empty:
                    mask_ok = pd.Series(True, index=dfp.index)
                    for col in ("ошибка", "error"):
                        if col in dfp.columns:
                            s = dfp[col]
                            ok = s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower().str.strip() == "nan")
                            mask_ok &= ok
                    dfp = dfp[mask_ok].copy()
                    rows = dfp.to_dict(orient="records") if not dfp.empty else []
                    promotable_rows = [r for r in rows if is_promotable_row(r)]
                    promotable_rows.sort(key=lambda row: score_row(row, objective_keys=objective_keys, penalty_key=penalty_key))
                    for idx_row, rec in enumerate(promotable_rows[: max_prev]):
                        cand = _candidate_from_row(
                            rec,
                            source=f"prev:{prev_name}",
                            source_stage=prev_name,
                            source_order=idx_row,
                        )
                        if cand is not None:
                            prev_candidates.append(cand)
        except Exception:
            pass

    # --- 2) Global archive: collect best promotable rows with sufficient overlap ---
    if max_archive > 0 and archive_path.exists() and archive_path.stat().st_size > 0:
        try:
            ranked_archive_by_kind: Dict[str, List[Tuple[Tuple[float, ...], float, Dict[str, Any], int]]] = {
                "same_problem": [],
                "same_contract": [],
                "legacy_unknown": [],
            }

            def _maybe_trim(kind: str) -> None:
                bucket = ranked_archive_by_kind.setdefault(str(kind), [])
                if len(bucket) > max_archive * 10:
                    bucket.sort(key=lambda t: (t[0], -t[1], t[3]))
                    del bucket[max_archive * 5 :]

            with archive_path.open("r", encoding="utf-8") as f:
                for archive_order, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    compat_kind = archive_record_compatibility_kind(
                        rec,
                        objective_keys=objective_keys,
                        penalty_key=penalty_key,
                        problem_hash=problem_hash,
                    )
                    if compat_kind == "contract_mismatch":
                        continue
                    if not is_promotable_row(rec):
                        continue
                    s = score_row(rec, objective_keys=objective_keys, penalty_key=penalty_key)
                    if not (np.isfinite(s[0]) and np.isfinite(s[1]) and np.isfinite(s[2])):
                        continue
                    present = 0
                    p: Dict[str, Any] = {}
                    for pnm in names:
                        key = f"параметр__{pnm}"
                        if key not in rec:
                            continue
                        try:
                            v = float(rec.get(key))
                        except Exception:
                            continue
                        if not np.isfinite(v):
                            continue
                        p[pnm] = v
                        present += 1
                    coverage = float(present) / float(d) if d > 0 else 0.0
                    if coverage < float(min_cov):
                        continue
                    cand = _candidate_from_row(
                        dict(rec, **{f"параметр__{k}": v for k, v in p.items()}),
                        source="archive",
                        source_stage="archive",
                        source_order=int(archive_order),
                        coverage_override=coverage,
                    )
                    if cand is None:
                        continue
                    cand["archive_match_kind"] = str(compat_kind)
                    ranked_archive_by_kind.setdefault(str(compat_kind), []).append((s, coverage, cand, int(archive_order)))
                    _maybe_trim(str(compat_kind))

            chosen_kind = _preferred_archive_bucket_name(ranked_archive_by_kind, min_count=1)
            ranked_archive = list(ranked_archive_by_kind.get(chosen_kind) or [])
            if ranked_archive:
                ranked_archive.sort(key=lambda t: (t[0], -t[1], t[3]))
                archive_candidates = [cand for _s, _cov, cand, _ord in ranked_archive[:max_archive]]
        except Exception:
            pass

    # --- Historical/static ordering: previous stage first, archive second ---
    def _static_key(cand: Dict[str, Any]) -> Tuple[Any, ...]:
        return (tuple(cand.get("score_tuple") or (float("inf"),)), -float(cand.get("coverage", 0.0) or 0.0), int(cand.get("source_order", 0) or 0))

    candidates_all = list(prev_candidates) + list(archive_candidates)
    selected_static: List[Dict[str, Any]] = []
    selected_hashes_static: set[str] = set()
    for source_list in (sorted(prev_candidates, key=_static_key), sorted(archive_candidates, key=_static_key)):
        for cand in source_list:
            h = str(cand.get("param_hash") or "")
            if not h or h in selected_hashes_static:
                continue
            selected_hashes_static.add(h)
            selected_static.append(cand)
            if len(selected_static) >= max_total:
                break
        if len(selected_static) >= max_total:
            break

    selected_bucket_by_hash: Dict[str, str] = {}
    selected_order_by_hash: Dict[str, int] = {}
    selected_candidates: List[Dict[str, Any]] = []

    if effective_mode == "influence_weighted" and candidates_all:
        target_total = int(min(max_total, max(0, int(budget.get("total_seed_cap", max_total) or max_total))))
        focus_budget = int(max(0, int(budget.get("focus_budget", 0) or 0)))
        explore_budget = int(max(0, int(budget.get("explore_budget", target_total) or target_total)))
        focus_param_budgets = {
            str(k): int(max(0, int(v)))
            for k, v in dict(budget.get("focus_param_budgets") or {}).items()
            if str(k)
        }

        def _policy_key(cand: Dict[str, Any]) -> Tuple[Any, ...]:
            return (
                promotion_sort_key(
                    stage_name_s,
                    score_tuple=tuple(cand.get("score_tuple") or (float("inf"),)),
                    alignment=float(cand.get("alignment", 0.0) or 0.0),
                    off_axis_sprawl=float(cand.get("off_axis_sprawl", 0.0) or 0.0),
                ),
                int(cand.get("source_pref", 1) or 1),
                -float(cand.get("coverage", 0.0) or 0.0),
                int(cand.get("source_order", 0) or 0),
            )

        selected_hashes: set[str] = set()
        focus_selected: List[Dict[str, Any]] = []

        for pname, alloc in focus_param_budgets.items():
            if alloc <= 0 or len(focus_selected) >= target_total:
                continue
            ranked = [
                cand for cand in candidates_all
                if str(cand.get("param_hash") or "") not in selected_hashes
                and float((cand.get("delta_norm") or {}).get(pname, 0.0) or 0.0) > 0.0
            ]
            ranked.sort(key=_policy_key)
            taken = 0
            for cand in ranked:
                if taken >= int(alloc) or len(focus_selected) >= target_total or len(focus_selected) >= focus_budget:
                    break
                h = str(cand.get("param_hash") or "")
                if not h or h in selected_hashes:
                    continue
                selected_hashes.add(h)
                focus_selected.append(cand)
                selected_bucket_by_hash[h] = "focus"
                taken += 1

        if len(focus_selected) < focus_budget:
            ranked = [
                cand for cand in candidates_all
                if str(cand.get("param_hash") or "") not in selected_hashes
                and float(cand.get("alignment", 0.0) or 0.0) > 0.0
            ]
            ranked.sort(key=_policy_key)
            for cand in ranked:
                if len(focus_selected) >= focus_budget or len(focus_selected) >= target_total:
                    break
                h = str(cand.get("param_hash") or "")
                if not h or h in selected_hashes:
                    continue
                selected_hashes.add(h)
                focus_selected.append(cand)
                selected_bucket_by_hash[h] = "focus"

        explore_selected: List[Dict[str, Any]] = []
        ranked_explore = [cand for cand in selected_static if str(cand.get("param_hash") or "") not in selected_hashes]
        for cand in ranked_explore:
            if len(explore_selected) >= explore_budget or (len(focus_selected) + len(explore_selected)) >= target_total:
                break
            h = str(cand.get("param_hash") or "")
            if not h or h in selected_hashes:
                continue
            selected_hashes.add(h)
            explore_selected.append(cand)
            selected_bucket_by_hash[h] = "explore"

        policy_name = str(budget.get("policy_name") or "")
        if policy_name == "broad_relevance":
            selected_candidates = list(explore_selected) + list(focus_selected)
        else:
            selected_candidates = list(focus_selected) + list(explore_selected)
        for order, cand in enumerate(selected_candidates, start=1):
            h = str(cand.get("param_hash") or "")
            if h:
                selected_order_by_hash[h] = int(order)
    else:
        selected_candidates = list(selected_static)
        for order, cand in enumerate(selected_candidates, start=1):
            h = str(cand.get("param_hash") or "")
            if h:
                selected_bucket_by_hash[h] = "static"
                selected_order_by_hash[h] = int(order)

    # Selected seed manifest: actual seeds with provenance/bucket/alignment.
    if seed_manifest_json_path is not None or seed_manifest_csv_path is not None:
        try:
            manifest_rows: List[Dict[str, Any]] = []
            for order, cand in enumerate(selected_candidates, start=1):
                h = str(cand.get("param_hash") or "")
                if not h:
                    continue
                manifest_rows.append({
                    "stage_name": stage_name_s,
                    "requested_mode": requested_mode,
                    "effective_mode": effective_mode,
                    "policy_name": str(budget.get("policy_name") or ""),
                    "seed_order": int(order),
                    "selected_bucket": str(selected_bucket_by_hash.get(h, "")),
                    "source": str(cand.get("source") or ""),
                    "source_stage": str(cand.get("source_stage") or ""),
                    "row_id": cand.get("row_id"),
                    "coverage": float(cand.get("coverage", 0.0) or 0.0),
                    "archive_match_kind": str(cand.get("archive_match_kind") or ""),
                    "influence_alignment": float(cand.get("alignment", 0.0) or 0.0),
                    "off_axis_sprawl": float(cand.get("off_axis_sprawl", 0.0) or 0.0),
                    "priority_touched_count": int(cand.get("priority_touched_count", 0) or 0),
                    "dominant_stage_params": list(cand.get("dominant_stage_params") or []),
                    "param_hash": h,
                    "params": dict(cand.get("clean_params") or {}),
                })
            if seed_manifest_json_path is not None:
                if manifest_rows:
                    save_json(manifest_rows, seed_manifest_json_path)
                elif Path(seed_manifest_json_path).exists():
                    try:
                        Path(seed_manifest_json_path).unlink()
                    except Exception:
                        pass
            if seed_manifest_csv_path is not None:
                if manifest_rows:
                    Path(seed_manifest_csv_path).parent.mkdir(parents=True, exist_ok=True)
                    pd.DataFrame([
                        {
                            **{k: v for k, v in rec.items() if k != "params"},
                            "dominant_stage_params": "|".join(str(x) for x in (rec.get("dominant_stage_params") or [])),
                            "params_json": json.dumps(rec.get("params") or {}, ensure_ascii=False, sort_keys=True),
                        }
                        for rec in manifest_rows
                    ]).to_csv(seed_manifest_csv_path, index=False)
                elif Path(seed_manifest_csv_path).exists():
                    try:
                        Path(seed_manifest_csv_path).unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    # Diagnostics/audit rows for promotion policy
    if promotion_log_path is not None:
        try:
            decision_rows: List[Dict[str, Any]] = []
            for cand in candidates_all:
                h = str(cand.get("param_hash") or "")
                score_t = tuple(cand.get("score_tuple") or ())
                decision_rows.append({
                    "stage_name": stage_name_s,
                    "requested_mode": requested_mode,
                    "effective_mode": effective_mode,
                    "source": str(cand.get("source") or ""),
                    "source_stage": str(cand.get("source_stage") or ""),
                    "row_id": cand.get("row_id"),
                    "coverage": float(cand.get("coverage", 0.0) or 0.0),
                    "penalty_total": float(score_t[0]) if len(score_t) > 0 else float("inf"),
                    "objective_keys_json": json.dumps(list(normalize_objective_keys(objective_keys)), ensure_ascii=False),
                    "penalty_key": str(normalize_penalty_key(penalty_key)),
                    "score_json": json.dumps([float(x) for x in score_t], ensure_ascii=False),
                    "objective_1_key": str((normalize_objective_keys(objective_keys) + ("", "", ""))[0]),
                    "objective_1": float(score_t[1]) if len(score_t) > 1 else float("inf"),
                    "objective_2_key": str((normalize_objective_keys(objective_keys) + ("", "", ""))[1]),
                    "objective_2": float(score_t[2]) if len(score_t) > 2 else float("inf"),
                    "objective_3_key": str((normalize_objective_keys(objective_keys) + ("", "", ""))[2]),
                    "objective_3": float(score_t[3]) if len(score_t) > 3 else float("inf"),
                    "influence_alignment": float(cand.get("alignment", 0.0) or 0.0),
                    "off_axis_sprawl": float(cand.get("off_axis_sprawl", 0.0) or 0.0),
                    "priority_touched_count": int(cand.get("priority_touched_count", 0) or 0),
                    "dominant_stage_params": "|".join(str(x) for x in (cand.get("dominant_stage_params") or [])),
                    "selected": bool(h in selected_order_by_hash),
                    "selected_bucket": str(selected_bucket_by_hash.get(h, "")),
                    "selected_order": int(selected_order_by_hash.get(h, 0) or 0),
                    "param_hash": h,
                })
            if decision_rows:
                promotion_log_path.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(decision_rows).sort_values(["selected", "selected_order", "source", "row_id"], ascending=[False, True, True, True]).to_csv(promotion_log_path, index=False)
        except Exception:
            pass

    out: List[Dict[str, Any]] = []
    seen_out: set[str] = set()
    for cand in selected_candidates:
        h = str(cand.get("param_hash") or "")
        clean = dict(cand.get("clean_params") or {})
        if not clean or not h or h in seen_out:
            continue
        seen_out.add(h)
        out.append(clean)
        if len(out) >= max_total:
            break

    return out


def append_csv_to_archive_jsonl(
    archive_path: Path,
    csv_path: Path,
    *,
    meta: Dict[str, Any],
    stage_name: str,
    archived_ids_path: Path,
) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return
    if df.empty:
        return

    archived: Dict[str, List[int]] = {}
    if archived_ids_path.exists():
        try:
            archived = load_json(archived_ids_path)
        except Exception:
            archived = {}
    if not isinstance(archived, dict):
        archived = {}
    ids = set(int(x) for x in archived.get(stage_name, []) if str(x).strip().isdigit())

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("a", encoding="utf-8") as f:
        for _, r in df.iterrows():
            row_rec = r.to_dict()
            if is_baseline_row(row_rec):
                continue
            try:
                rid = int(r.get("id"))
            except Exception:
                rid = None
            if rid is not None and rid in ids:
                continue
            rec = {**meta, "stage": stage_name}
            # include row fields (convert to python)
            for col in df.columns:
                val = r.get(col)
                if isinstance(val, np.generic):
                    val = val.item()
                rec[col] = val
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if rid is not None:
                ids.add(rid)

    archived[stage_name] = sorted(ids)
    save_json(archived, archived_ids_path)


def make_initial_cem_state_from_archive(
    cem_state_path: Path,
    archive_path: Path,
    *,
    ranges: Dict[str, Any],
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    problem_hash: str | None = None,
    top_k: int = 64,
    min_coverage: float = 0.6,
) -> bool:
    """Create initial CEM mu/cov using top rows from global archive.

    Важно: история/архив могут быть собраны при другом наборе диапазонов.
    Поэтому:
      - допускаем частичное перекрытие параметров (coverage)
      - отсутствующие параметры заполняем 0.5 (середина диапазона)

    Returns True if state was written.
    """
    if cem_state_path.exists():
        return False
    if not archive_path.exists() or archive_path.stat().st_size == 0:
        return False

    names = list(ranges.keys())
    d = int(len(names))
    if d <= 0:
        return False

    # Можно переопределить через env (удобно для экспериментов из UI/StageRunner)
    try:
        min_cov = float(os.environ.get("PNEUMO_WARMSTART_MIN_COVERAGE", str(min_coverage)))
    except Exception:
        min_cov = float(min_coverage)
    min_cov = max(0.0, min(1.0, float(min_cov)))

    def _bounds(p: str) -> Tuple[float, float]:
        lo, hi = ranges.get(p, (0.0, 1.0))
        return float(lo), float(hi)

    candidates_by_kind: Dict[str, List[Tuple[Tuple[float, ...], Dict[str, Any]]]] = {
        "same_problem": [],
        "same_contract": [],
        "legacy_unknown": [],
    }
    with archive_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            compat_kind = archive_record_compatibility_kind(
                rec,
                objective_keys=objective_keys,
                penalty_key=penalty_key,
                problem_hash=problem_hash,
            )
            if compat_kind == "contract_mismatch":
                continue

            s = score_row(rec, objective_keys=objective_keys, penalty_key=penalty_key)
            if not (np.isfinite(s[0]) and np.isfinite(s[1]) and np.isfinite(s[2])):
                continue

            present = 0
            x: List[float] = []
            ok = True
            for pnm in names:
                lo, hi = _bounds(pnm)
                if hi <= lo:
                    ok = False
                    break
                key = f"параметр__{pnm}"
                if key in rec:
                    try:
                        v = float(rec.get(key))
                        xn = (v - lo) / (hi - lo)
                        x.append(float(np.clip(xn, 0.0, 1.0)))
                        present += 1
                        continue
                    except Exception:
                        # если значение битое — считаем что параметра нет
                        pass
                # отсутствующий параметр → середина диапазона
                x.append(0.5)

            if not ok:
                continue
            coverage = float(present) / float(d)
            if coverage < float(min_cov):
                continue

            rec2 = dict(rec)
            rec2["_x_norm"] = x
            rec2["_coverage"] = coverage
            rec2["_archive_match_kind"] = str(compat_kind)
            candidates_by_kind.setdefault(str(compat_kind), []).append((s, rec2))

    chosen_kind = _preferred_archive_bucket_name(candidates_by_kind, min_count=1)
    candidates = list(candidates_by_kind.get(chosen_kind) or [])
    if not candidates:
        return False

    # Сортировка по метрикам (лексикографически)
    candidates.sort(key=lambda t: t[0])

    # Предпочтение более «полным» записям (если score одинаковый)
    # Вставляем лёгкий tie-breaker: coverage (больше лучше).
    # (Т.к. sorting python стабильный, можно просто пересортировать на коротком списке.)
    top = candidates[: max(8, min(int(top_k), len(candidates)))]
    top.sort(key=lambda t: (t[0], -float(t[1].get("_coverage", 0.0))))

    X = np.array([t[1]["_x_norm"] for t in top], dtype=float)
    mu = X.mean(axis=0)
    cov = np.cov(X.T)
    if cov.ndim == 0:
        cov = np.eye(len(mu)) * float(cov)
    if cov.shape != (len(mu), len(mu)):
        cov = np.eye(len(mu))

    cov = cov + np.eye(len(mu)) * 1e-4

    state = {
        "mu": mu.tolist(),
        "cov": cov.tolist(),
        "iteration": 0,
        "from_archive": True,
        "n_used": int(X.shape[0]),
        "min_coverage": float(min_cov),
        "archive_match_kind": str(chosen_kind),
    }
    save_json(state, cem_state_path)
    return True



def make_initial_cem_state_from_surrogate(
    cem_state_path: Path,
    archive_path: Path,
    *,
    ranges: Dict[str, Any],
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
    problem_hash: str | None = None,
    model_sha_prefix: str = "",
    n_samples: int = 8000,
    top_k: int = 64,
    seed: int = 1,
    max_train: int = 20000,
) -> bool:
    """Create initial CEM mu/cov using a cheap surrogate trained on the global archive.

    Strategy:
      1) Build training dataset (X=params normalized to 0..1, y=scalarized score).
      2) Fit ExtraTreesRegressor (fast, robust).
      3) Sample many random points in [0,1]^d and rank by predicted y.
      4) Use top_k predicted points as 'elite' to compute mu/cov.

    Returns True if state was written.
    """
    if cem_state_path.exists():
        return False
    if ExtraTreesRegressor is None:
        return False
    if not archive_path.exists() or archive_path.stat().st_size == 0:
        return False

    names = list(ranges.keys())
    if not names:
        return False

    d = int(len(names))
    try:
        min_cov = float(os.environ.get("PNEUMO_WARMSTART_MIN_COVERAGE", "0.6"))
    except Exception:
        min_cov = 0.6
    min_cov = max(0.0, min(1.0, float(min_cov)))

    def _bounds(p: str) -> Tuple[float, float]:
        lo, hi = ranges.get(p, (0.0, 1.0))
        return float(lo), float(hi)

    rng = np.random.default_rng(int(seed))

    def _iter_records(filter_model: bool) -> Dict[str, List[Tuple[List[float], float]]]:
        data_by_kind: Dict[str, List[Tuple[List[float], float]]] = {
            "same_problem": [],
            "same_contract": [],
            "legacy_unknown": [],
        }
        seen_by_kind = {key: 0 for key in data_by_kind}
        with archive_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if filter_model and model_sha_prefix:
                    msha = str(rec.get("model_sha1", ""))
                    if not msha.startswith(model_sha_prefix):
                        continue
                compat_kind = archive_record_compatibility_kind(
                    rec,
                    objective_keys=objective_keys,
                    penalty_key=penalty_key,
                    problem_hash=problem_hash,
                )
                if compat_kind == "contract_mismatch":
                    continue

                s = score_row(rec, objective_keys=objective_keys, penalty_key=penalty_key)
                if not (np.isfinite(s[0]) and np.isfinite(s[1]) and np.isfinite(s[2])):
                    continue
                # Extract normalized x (допускаем частичное перекрытие параметров)
                present = 0
                ok = True
                x = []
                for p in names:
                    lo, hi = _bounds(p)
                    if hi <= lo:
                        ok = False
                        break
                    key = f"параметр__{p}"
                    if key in rec:
                        try:
                            v = float(rec.get(key))
                            xn = (v - lo) / (hi - lo)
                            x.append(float(np.clip(xn, 0.0, 1.0)))
                            present += 1
                            continue
                        except Exception:
                            pass
                    x.append(0.5)

                if not ok:
                    continue
                coverage = float(present) / float(d) if d > 0 else 0.0
                if coverage < float(min_cov):
                    continue

                # Scalarize under the shared objective contract: penalty dominates,
                # then earlier objectives outweigh later tie-breakers without hard-coding
                # legacy semantic names.
                y = scalarize_score_tuple(s)

                # Reservoir sampling to cap train size
                bucket = data_by_kind.setdefault(str(compat_kind), [])
                seen = int(seen_by_kind.get(str(compat_kind), 0))
                if len(bucket) < int(max_train):
                    bucket.append((x, float(y)))
                else:
                    j = int(rng.integers(0, seen + 1))
                    if j < int(max_train):
                        bucket[j] = (x, float(y))
                seen_by_kind[str(compat_kind)] = seen + 1
        return data_by_kind

    preferred_train_n = max(50, 5 * len(names))

    # Prefer same model sha (transfer learning), but fallback to all if too small
    used_model_filter = bool(bool(model_sha_prefix))
    data_by_kind = _iter_records(filter_model=True)
    selected_kind = _preferred_archive_bucket_name(data_by_kind, min_count=preferred_train_n)
    data = list(data_by_kind.get(selected_kind) or [])
    if len(data) < preferred_train_n:
        used_model_filter = False
        data_by_kind = _iter_records(filter_model=False)
        selected_kind = _preferred_archive_bucket_name(data_by_kind, min_count=preferred_train_n)
        data = list(data_by_kind.get(selected_kind) or [])

    if len(data) < max(20, 3 * len(names)):
        return False

    X = np.array([d[0] for d in data], dtype=float)
    y = np.array([d[1] for d in data], dtype=float)

    # Fit surrogate
    reg = ExtraTreesRegressor(
        n_estimators=200,
        random_state=int(seed),
        n_jobs=-1,
        min_samples_leaf=2,
    )
    reg.fit(X, y)

    d = len(names)
    n_samples = int(max(1000, n_samples))
    top_k = int(max(8, min(top_k, n_samples)))

    Xcand = rng.random((n_samples, d))
    ypred = reg.predict(Xcand)
    elite = Xcand[np.argsort(ypred)[:top_k]]

    mu = elite.mean(axis=0)
    cov = np.cov(elite.T)
    if cov.shape != (d, d):
        cov = np.eye(d) * 0.05
    cov = cov + np.eye(d) * 1e-4

    state = {
        "mu": mu.tolist(),
        "cov": cov.tolist(),
        "iteration": 0,
        "from_surrogate": True,
        "train_n": int(X.shape[0]),
        "samples": int(n_samples),
        "top_k": int(top_k),
        "model_filter": bool(used_model_filter),
        "archive_match_kind": str(selected_kind),
    }
    save_json(state, cem_state_path)
    return True


def rebuild_combined_csv(out_csv: Path, stage_csvs: List[Tuple[str, Path]]) -> None:
    frames = []
    for stage_name, p in stage_csvs:
        if not p.exists() or p.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if df.empty:
            continue
        df.insert(0, "stage", stage_name)
        frames.append(df)
    if not frames:
        return
    df_all = pd.concat(frames, axis=0, ignore_index=True, sort=False)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(out_csv, index=False)


def estimate_stage_seed_cap(
    *,
    stage_idx: int,
    stage_plan: List[Dict[str, Any]],
    stage_preview: List[Dict[str, Any]],
    stage_csvs: List[Tuple[str, Path]],
    reserve_frac: float = 0.30,
    hard_cap: int = 6,
) -> int:
    """Budget-aware upper bound for warm-start seed evaluations.

    A long/heavy stage can appear frozen if we spend most of its budget on a
    large seed prelude before any iterative search starts. Estimate the current
    stage per-candidate cost from the previous stage pace and the previewed
    solver-step ratio, then reserve only a small fraction of the stage budget
    for seed points.
    """
    if int(stage_idx) <= 0:
        return 0
    try:
        stage_budget_sec = max(1.0, float(stage_plan[stage_idx].get("minutes", 0.0)) * 60.0)
    except Exception:
        stage_budget_sec = 60.0
    budget_for_seeds = max(1.0, stage_budget_sec * max(0.05, min(0.8, float(reserve_frac))))

    prev_csv = stage_csvs[stage_idx - 1][1]
    prev_rows = csv_data_row_count(prev_csv)
    prev_prog = prev_csv.with_name(prev_csv.stem + "_progress.json")
    prev_elapsed = None
    if prev_prog.exists():
        try:
            prev_elapsed = float(load_json(prev_prog).get("прошло_сек", 0.0) or 0.0)
        except Exception:
            prev_elapsed = None

    if not prev_elapsed or prev_elapsed <= 0.0 or prev_rows <= 0:
        return int(max(1, min(int(hard_cap), 2)))

    try:
        prev_steps = float(stage_preview[stage_idx - 1].get("approx_solver_steps", 1.0) or 1.0)
        cur_steps = float(stage_preview[stage_idx].get("approx_solver_steps", prev_steps) or prev_steps)
        ratio = max(1.0, cur_steps / max(1.0, prev_steps))
    except Exception:
        ratio = 1.0

    prev_avg_sec = float(prev_elapsed) / max(1, int(prev_rows))
    est_cur_candidate_sec = max(2.0, prev_avg_sec * ratio)
    cap = int(math.floor(budget_for_seeds / est_cur_candidate_sec))
    cap = max(1, min(int(hard_cap), cap))
    return int(cap)


def write_progress(progress_json: Path, payload: Dict[str, Any]) -> bool:
    payload = dict(payload)
    payload.setdefault("ts", _now_ts())
    return atomic_write_json_retry(
        progress_json,
        payload,
        ensure_ascii=False,
        indent=2,
        encoding="utf-8",
        max_wait_sec=3.0,
        retry_sleep_sec=0.05,
        label="stage-progress",
    )


def _safe_close_fileobj(fh: Optional[object]) -> None:
    try:
        if fh is not None:
            fh.close()  # type: ignore[attr-defined]
    except Exception:
        pass


def build_stage_worker_env(
    workspace_dir: Path,
    problem_hash: str | None,
    *,
    base_env: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    env = dict(base_env) if base_env is not None else os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    _prepend_pythonpath(env, _PROJECT_ROOT, _PNEUMO_ROOT)
    env.setdefault("PNEUMO_GUIDED_MODE", "auto")
    env["PNEUMO_OPT_PROBLEM_HASH_MODE"] = problem_hash_mode_from_env(env)
    current_problem_hash = str(problem_hash or "").strip()
    if current_problem_hash:
        env["PNEUMO_OPT_PROBLEM_HASH"] = current_problem_hash
    else:
        env.pop("PNEUMO_OPT_PROBLEM_HASH", None)
    env["PNEUMO_WORKSPACE_DIR"] = str(Path(workspace_dir))
    try:
        cache_dir = (Path(workspace_dir) / "cache" / "worldroad")
        cache_dir.mkdir(parents=True, exist_ok=True)
        env.setdefault("WORLDROAD_CACHE_DIR", str(cache_dir))
    except Exception:
        pass
    return env



def run_subprocess(cmd: List[str], cwd: Path, *, check: bool = True, log_dir: Optional[Path] = None) -> int:
    # Use the same environment; ensure UTF-8 output for logs.
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    _prepend_pythonpath(env, _PROJECT_ROOT, _PNEUMO_ROOT)
    run_cmd = list(cmd)
    if run_cmd:
        try:
            run_cmd[0] = console_python_executable(run_cmd[0]) or str(run_cmd[0])
        except Exception:
            pass
    stdout_f = None
    stderr_f = None
    try:
        if log_dir is not None:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(str(run_cmd[1] if len(run_cmd) > 1 else 'subprocess')).stem
            short = (stem[:8] or 'sub')
            stdout_f = (log_dir / f'{short}.out.log').open('ab')
            stderr_f = (log_dir / f'{short}.err.log').open('ab')
    except Exception:
        stdout_f = None
        stderr_f = None
    try:
        proc = subprocess.Popen(run_cmd, cwd=str(cwd), env=env, stdout=stdout_f, stderr=stderr_f)
        rc = proc.wait()
    finally:
        _safe_close_fileobj(stdout_f)
        _safe_close_fileobj(stderr_f)
    if check and rc != 0:
        raise RuntimeError(f"Subprocess failed rc={rc}: {' '.join(run_cmd)}")
    return rc


def build_system_influence_cmd(
    *,
    worker_path: Path,
    staging_dir: Path,
    model_path: Path,
    base_json: Path,
    ranges_json: Path,
    eps_rel: float,
    adaptive_eps: bool = False,
    adaptive_eps_grid: str = "",
    adaptive_eps_strategy: str = "balanced",
    stage_name: str = "",
) -> List[str]:
    def _cli_arg_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    cmd = [
        console_python_executable(sys.executable) or sys.executable,
        _cli_arg_path(worker_path.parent / "calibration" / "system_influence_report_v1.py"),
        "--run_dir",
        _cli_arg_path(staging_dir),
        "--model",
        _cli_arg_path(model_path),
        "--base_json",
        _cli_arg_path(base_json),
        "--fit_ranges_json",
        _cli_arg_path(ranges_json),
        "--eps_rel",
        str(float(eps_rel)),
    ]
    if bool(adaptive_eps):
        cmd.append("--adaptive_eps")
    if str(adaptive_eps_grid).strip():
        cmd += ["--adaptive_eps_grid", str(adaptive_eps_grid).strip()]
    if str(adaptive_eps_strategy).strip():
        cmd += ["--adaptive_eps_strategy", str(adaptive_eps_strategy).strip()]
    if str(stage_name).strip():
        cmd += ["--stage_name", str(stage_name).strip()]
    return cmd


def stage_aware_influence_output_dir(staging_dir: Path, stage_name: str) -> Path:
    return staging_dir / "stage_aware" / str(stage_name or "stage").strip()


def stage_aware_influence_report_matches(
    report_json: Path,
    *,
    requested_eps_rel: float,
    adaptive_grid: Sequence[float],
    adaptive_strategy: str,
    stage_name: str,
) -> bool:
    if not report_json.exists():
        return False
    try:
        payload = load_json(report_json)
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    config = dict(payload.get("config") or {})
    try:
        existing_req = float(config.get("requested_eps_rel"))
    except Exception:
        return False
    try:
        existing_grid = tuple(float(x) for x in (config.get("adaptive_eps_grid") or []))
    except Exception:
        existing_grid = ()
    existing_strategy = str(config.get("adaptive_eps_strategy") or "balanced").strip().lower() or "balanced"
    existing_stage_name = str(config.get("stage_name") or "").strip()
    target_grid = tuple(float(x) for x in adaptive_grid)
    if abs(existing_req - float(requested_eps_rel)) > 1e-15:
        return False
    if existing_grid != target_grid:
        return False
    if existing_strategy != str(adaptive_strategy).strip().lower():
        return False
    if existing_stage_name != str(stage_name).strip():
        return False
    return True


def ensure_stage_aware_influence_reports(
    *,
    worker_path: Path,
    staging_dir: Path,
    model_path: Path,
    base_json: Path,
    stage_plan: Sequence[Dict[str, Any]],
    requested_eps_rel: float,
    adaptive_eps_grid_raw: str,
    progress_json: Path,
) -> List[Dict[str, Any]]:
    base_grid = parse_influence_eps_grid(
        adaptive_eps_grid_raw,
        requested_eps_rel=float(requested_eps_rel),
    )
    profiles: List[Dict[str, Any]] = []
    for idx, stg in enumerate(stage_plan):
        stage_name = str(stg.get("name") or f"stage{idx}")
        ranges_json = Path(stg.get("ranges_json") or base_json)
        profile = build_stage_aware_influence_profile(
            stage_name,
            requested_eps_rel=float(requested_eps_rel),
            base_grid=base_grid,
        )
        out_dir = stage_aware_influence_output_dir(staging_dir, stage_name)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_json = out_dir / "system_influence.json"
        report_md = out_dir / "SYSTEM_INFLUENCE.md"
        if not stage_aware_influence_report_matches(
            report_json,
            requested_eps_rel=float(profile["requested_eps_rel"]),
            adaptive_grid=tuple(profile["adaptive_grid"]),
            adaptive_strategy=str(profile["adaptive_strategy"]),
            stage_name=stage_name,
        ):
            cmd = build_system_influence_cmd(
                worker_path=worker_path,
                staging_dir=out_dir,
                model_path=model_path,
                base_json=base_json,
                ranges_json=ranges_json,
                eps_rel=float(profile["requested_eps_rel"]),
                adaptive_eps=True,
                adaptive_eps_grid=str(profile["adaptive_grid_text"]),
                adaptive_eps_strategy=str(profile["adaptive_strategy"]),
                stage_name=stage_name,
            )
            write_progress(progress_json, {
                "status": "stage_aware_influence",
                "stage": stage_name,
                "stage_idx": int(idx),
                "stage_total": int(len(stage_plan)),
                "cmd": cmd,
                "ranges_json": str(ranges_json),
                "profile": dict(profile),
                "expected_output": str(report_json),
            })
            run_subprocess(cmd, cwd=_PROJECT_ROOT, log_dir=out_dir)
            if not report_json.exists():
                raise RuntimeError(f"stage-aware system influence report was not created for {stage_name}: {report_json}")

        selected_eps_counts: Dict[str, int] = {}
        try:
            payload = load_json(report_json)
            selected_eps_counts = dict(((payload.get("adaptive_summary") or {}).get("selected_eps_counts") or {}))
        except Exception:
            selected_eps_counts = {}
        profiles.append({
            **dict(profile),
            "stage_idx": int(idx),
            "ranges_json": str(ranges_json),
            "output_dir": str(out_dir),
            "report_json": str(report_json),
            "report_md": str(report_md),
            "selected_eps_counts": selected_eps_counts,
        })

    save_json({
        "requested_eps_rel": float(requested_eps_rel),
        "base_grid": [float(x) for x in base_grid],
        "profiles": profiles,
    }, staging_dir / "stage_aware_influence_profiles.json")
    return profiles


def build_param_staging_cmd(*, worker_path: Path, ranges_json: Path, system_influence_json: Path, staging_dir: Path) -> List[str]:
    def _cli_arg_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    return [
        console_python_executable(sys.executable) or sys.executable,
        _cli_arg_path(worker_path.parent / "calibration" / "param_staging_v3_influence.py"),
        "--fit_ranges_json",
        _cli_arg_path(ranges_json),
        "--system_influence_json",
        _cli_arg_path(system_influence_json),
        "--out_dir",
        _cli_arg_path(staging_dir),
    ]


def staging_plan_ready(staging_dir: Path) -> bool:
    return (staging_dir / "stages_influence.json").exists() and any(staging_dir.glob("fit_ranges_stage_*.json"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--base_json", required=True)
    ap.add_argument("--ranges_json", required=True)
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--objective", action="append", default=[], help="Objective key in worker metrics row. Repeat to keep StageRunner ranking/baseline aligned with coordinator.")
    ap.add_argument("--penalty-key", default="штраф_физичности_сумма", help="Penalty/feasibility key used as the hard gate before objectives.")
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--progress_json", required=True)
    ap.add_argument("--stop_file", required=True)

    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--seed_candidates", type=int, default=64)
    ap.add_argument("--seed_conditions", type=int, default=16)
    ap.add_argument("--jobs", type=int, default=int(max(1, min((61 if sys.platform.startswith("win") else 128), (os.cpu_count() or 4)))))
    ap.add_argument("--flush_every", type=int, default=10)
    ap.add_argument("--progress_every_sec", type=float, default=2.0)
    ap.add_argument("--autoupdate_baseline", type=int, default=1)
    ap.add_argument("--warmstart_mode", choices=["surrogate", "archive", "none"], default="surrogate", help="Как инициализировать распределение (CEM): surrogate (RF/ET) / archive (топ из истории) / none")
    ap.add_argument("--surrogate_samples", type=int, default=8000, help="Сколько случайных точек прогнать через surrogate для выбора элиты (warm-start)")
    ap.add_argument("--surrogate_top_k", type=int, default=64, help="Сколько лучших по surrogate взять как elite для mu/cov")
    ap.add_argument("--stop_pen_stage1", type=float, default=25.0, help="Early-stop порог по суммарному штрафу для stage1")
    ap.add_argument("--stop_pen_stage2", type=float, default=15.0, help="Early-stop порог по суммарному штрафу для stage2")
    ap.add_argument("--sort_tests_by_cost", type=int, default=1, help="Сортировать тесты по dt*t_end (дешёвые первыми) в worker")
    ap.add_argument("--eps_rel", "--influence_eps_rel", dest="influence_eps_rel", type=float, default=1e-2, help="Относительный шаг возмущения для system_influence_report_v1")
    ap.add_argument("--adaptive_influence_eps", action="store_true", help="Включить adaptive epsilon scan в system_influence_report_v1")
    ap.add_argument("--adaptive_influence_eps_grid", default="", help="Опциональная сетка eps_rel для adaptive epsilon в system_influence_report_v1")
    ap.add_argument(
        "--stage_policy_mode",
        choices=("influence_weighted", "static"),
        default=DEFAULT_STAGE_POLICY_MODE,
        help="Политика seed budgeting / promotion для StageRunner: influence_weighted использует stage-specific influence summary, static сохраняет историческое поведение.",
    )

    args = ap.parse_args()

    objective_keys = tuple(normalize_objective_keys(args.objective))
    penalty_key = normalize_penalty_key(args.penalty_key)

    model_path = Path(args.model).resolve()
    worker_path = Path(args.worker).resolve()
    run_dir = Path(args.run_dir).resolve()
    base_json = Path(args.base_json).resolve()
    ranges_json = Path(args.ranges_json).resolve()
    suite_json = Path(args.suite_json).resolve()
    out_csv = Path(args.out_csv).resolve()
    progress_json = Path(args.progress_json).resolve()
    stop_file = Path(args.stop_file).resolve()

    run_dir.mkdir(parents=True, exist_ok=True)

    objective_contract = objective_contract_payload(
        objective_keys=objective_keys,
        penalty_key=penalty_key,
        source="opt_stage_runner_v1",
    )
    save_json(objective_contract, run_dir / "objective_contract.json")

    # Workspace is the ancestor "workspace" (expected run_dir/.../workspace/opt_runs/...)
    workspace_dir = run_dir
    for _ in range(4):
        if workspace_dir.name.lower() == "workspace":
            break
        workspace_dir = workspace_dir.parent

    archive_path = workspace_dir / "opt_archive" / "global_history.jsonl"
    archived_ids_path = run_dir / "_archived_ids.json"

    base_params_raw = load_json(base_json)
    suite_full_raw = load_json(suite_json)
    ranges_raw = load_json(ranges_json)
    base_params, ranges_sanitized, suite_full, optimization_input_audit = sanitize_optimization_inputs(
        base_params_raw,
        ranges_raw,
        suite_full_raw,
    )
    if base_params != base_params_raw:
        save_json(base_params, base_json)
    if ranges_sanitized != ranges_raw:
        save_json(ranges_sanitized, ranges_json)
    if suite_full != suite_full_raw:
        save_json(suite_full, suite_json)
    save_json(optimization_input_audit, run_dir / "optimization_input_audit.json")
    problem_hash_mode = problem_hash_mode_from_env()
    problem_hash = str(
        stable_hash_problem(
            base=base_params,
            ranges=ranges_sanitized,
            suite=suite_full,
            model_sha256=str(hash_file(model_path)),
            worker_sha256=str(hash_file(worker_path)),
            extra={
                "objective_keys": list(objective_keys),
                "penalty_key": str(penalty_key),
            },
            mode=problem_hash_mode,
        )
    )
    (run_dir / "problem_hash.txt").write_text(problem_hash, encoding="utf-8")
    write_problem_hash_mode_artifact(run_dir, problem_hash_mode)
    write_baseline_source_artifact(
        run_dir,
        resolve_workspace_baseline_source(
            problem_hash=problem_hash,
            workspace_dir=workspace_dir,
        ),
    )

    # Influence-based parameter staging (pneumatics/kinematics aware)
    staging_dir = run_dir / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    system_influence_json = staging_dir / "system_influence.json"

    # Run system influence report if missing.
    # Staged optimization must fail loudly when the influence report is absent;
    # otherwise the stage planner degenerates into zero-score alphabetical groups.
    if not system_influence_json.exists():
        cmd = build_system_influence_cmd(
            worker_path=worker_path,
            staging_dir=staging_dir,
            model_path=model_path,
            base_json=base_json,
            ranges_json=ranges_json,
            eps_rel=float(args.influence_eps_rel),
            adaptive_eps=bool(args.adaptive_influence_eps),
            adaptive_eps_grid=str(args.adaptive_influence_eps_grid or ""),
            adaptive_eps_strategy="balanced",
        )
        write_progress(progress_json, {
            "status": "system_influence",
            "cmd": cmd,
            "expected_output": str(system_influence_json),
            "eps_rel": float(args.influence_eps_rel),
            "adaptive_influence_eps": bool(args.adaptive_influence_eps),
            "adaptive_influence_eps_grid": str(args.adaptive_influence_eps_grid or ""),
        })
        try:
            run_subprocess(cmd, cwd=_PROJECT_ROOT, log_dir=staging_dir)
        except Exception as exc:
            write_progress(progress_json, {
                "status": "failed_system_influence",
                "cmd": cmd,
                "expected_output": str(system_influence_json),
                "eps_rel": float(args.influence_eps_rel),
                "adaptive_influence_eps": bool(args.adaptive_influence_eps),
                "adaptive_influence_eps_grid": str(args.adaptive_influence_eps_grid or ""),
                "error": repr(exc),
            })
            return 2
        if not system_influence_json.exists():
            write_progress(progress_json, {
                "status": "failed_system_influence",
                "cmd": cmd,
                "expected_output": str(system_influence_json),
                "eps_rel": float(args.influence_eps_rel),
                "adaptive_influence_eps": bool(args.adaptive_influence_eps),
                "adaptive_influence_eps_grid": str(args.adaptive_influence_eps_grid or ""),
                "error": "system_influence.json was not created",
            })
            return 2

    # Build parameter stages. The planner writes `stages_influence.json`, not `plan.json`.
    if not staging_plan_ready(staging_dir):
        cmd = build_param_staging_cmd(
            worker_path=worker_path,
            ranges_json=ranges_json,
            system_influence_json=system_influence_json,
            staging_dir=staging_dir,
        )
        write_progress(progress_json, {
            "status": "param_staging",
            "cmd": cmd,
            "expected_plan": str(staging_dir / "stages_influence.json"),
        })
        try:
            run_subprocess(cmd, cwd=_PROJECT_ROOT, log_dir=staging_dir)
        except Exception as exc:
            write_progress(progress_json, {
                "status": "failed_param_staging",
                "cmd": cmd,
                "expected_plan": str(staging_dir / "stages_influence.json"),
                "error": repr(exc),
            })
            return 3
        if not staging_plan_ready(staging_dir):
            write_progress(progress_json, {
                "status": "failed_param_staging",
                "cmd": cmd,
                "expected_plan": str(staging_dir / "stages_influence.json"),
                "error": "staging plan files were not created",
            })
            return 3

    # Discover staged ranges
    stage_ranges_files = sorted(staging_dir.glob("fit_ranges_stage_*.json"))
    if not stage_ranges_files:
        stage_ranges_files = [ranges_json]

    # Scenarios
    scenarios = build_default_scenarios(base_params)

    # Stage plan (3 stages)
    minutes_total = max(0.1, float(args.minutes))
    stage_plan = [
        {
            "name": "stage0_relevance",
            "max_stage": 0,
            "dt_scale": 2.5,
            "t_end_scale": 0.35,
            "minutes": minutes_total * 0.22,
            "ranges_json": stage_ranges_files[min(0, len(stage_ranges_files) - 1)],
            "scenario_ids": ["nominal"],
            "stop_if_pen_gt": float("inf"),
        },
        {
            "name": "stage1_long",
            "max_stage": 1,
            "dt_scale": 1.5,
            "t_end_scale": 1.0,
            "minutes": minutes_total * 0.33,
            "ranges_json": stage_ranges_files[min(1, len(stage_ranges_files) - 1)],
            "scenario_ids": ["nominal", "heavy"],
            "stop_if_pen_gt": float(args.stop_pen_stage1),
        },
        {
            "name": "stage2_final",
            "max_stage": 2,
            "dt_scale": 1.0,
            "t_end_scale": 2.0,
            "minutes": minutes_total * 0.45,
            "ranges_json": stage_ranges_files[-1],
            "scenario_ids": ["nominal", "heavy", "cold", "hot", "lowP"],
            "stop_if_pen_gt": float(args.stop_pen_stage2),
        },
    ]

    stage_aware_profiles: List[Dict[str, Any]] = []
    if bool(args.adaptive_influence_eps):
        try:
            stage_aware_profiles = ensure_stage_aware_influence_reports(
                worker_path=worker_path,
                staging_dir=staging_dir,
                model_path=model_path,
                base_json=base_json,
                stage_plan=stage_plan,
                requested_eps_rel=float(args.influence_eps_rel),
                adaptive_eps_grid_raw=str(args.adaptive_influence_eps_grid or ""),
                progress_json=progress_json,
            )
        except Exception as exc:
            write_progress(progress_json, {
                "status": "failed_stage_aware_influence",
                "requested_eps_rel": float(args.influence_eps_rel),
                "adaptive_influence_eps_grid": str(args.adaptive_influence_eps_grid or ""),
                "error": repr(exc),
            })
            return 8
    stage_aware_by_name = {
        str(rec.get("stage_name") or ""): dict(rec)
        for rec in stage_aware_profiles
        if isinstance(rec, dict)
    }

    try:
        base_system_influence_payload = load_json(system_influence_json)
    except Exception:
        base_system_influence_payload = {}

    stage_influence_summaries: Dict[str, Dict[str, Any]] = {}
    for stg in stage_plan:
        stage_name = str(stg.get("name") or "")
        try:
            stage_ranges_payload = load_json(Path(stg.get("ranges_json") or ranges_json))
        except Exception:
            stage_ranges_payload = {}
        report_payload = base_system_influence_payload
        report_source_label = "base_system_influence"
        report_json_path = str(system_influence_json)
        profile = dict(stage_aware_by_name.get(stage_name, {}))
        profile_json_raw = str(profile.get("report_json") or "").strip()
        if profile_json_raw:
            try:
                report_payload = load_json(Path(profile_json_raw))
                report_source_label = "stage_aware_influence"
                report_json_path = profile_json_raw
            except Exception:
                report_payload = base_system_influence_payload
                report_source_label = "base_system_influence"
                report_json_path = str(system_influence_json)
        summary = build_stage_specific_influence_summary(
            stage_name,
            active_params=list((stage_ranges_payload or {}).keys()),
            influence_payload=report_payload,
            source_label=report_source_label,
        )
        summary["report_json"] = str(report_json_path)
        stage_influence_summaries[stage_name] = summary

    stage_specific_summary_payload = {
        "version": "stage_specific_influence_summary_v1",
        "requested_mode": str(args.stage_policy_mode),
        "base_system_influence_json": str(system_influence_json),
        "stages": stage_influence_summaries,
    }
    save_json(stage_specific_summary_payload, staging_dir / "stage_specific_influence_summary.json")
    save_json(stage_specific_summary_payload, run_dir / "stage_specific_influence_summary.json")

    stage_preview: List[Dict[str, Any]] = []
    for stg in stage_plan:
        suite_fs_preview = filter_and_scale_suite(
            suite_full,
            max_stage=int(stg["max_stage"]),
            dt_scale=float(stg["dt_scale"]),
            t_end_scale=float(stg["t_end_scale"]),
        )
        suite_exp_preview = expand_suite_by_scenarios(
            suite_fs_preview,
            scenarios,
            base_params,
            scenario_ids=list(stg["scenario_ids"]),
        )
        approx_solver_steps = 0.0
        for row in suite_exp_preview:
            try:
                dt_loc = float(row.get("dt") or 0.01)
                t_end_loc = float(row.get("t_end") or 0.0)
                if dt_loc > 0.0:
                    approx_solver_steps += float(t_end_loc / dt_loc)
            except Exception:
                pass
        stage_preview.append({
            "name": str(stg["name"]),
            "description": describe_runtime_stage(stg.get("name")),
            "max_stage": int(stg["max_stage"]),
            "scenario_ids": list(stg["scenario_ids"]),
            "dt_scale": float(stg["dt_scale"]),
            "t_end_scale": float(stg["t_end_scale"]),
            "minutes_budget": float(stg["minutes"]),
            "expanded_test_count": int(len(suite_exp_preview)),
            "approx_solver_steps": float(approx_solver_steps),
            "influence_profile": dict(stage_aware_by_name.get(str(stg["name"]), {})),
            "stage_influence_summary": dict(stage_influence_summaries.get(str(stg["name"]), {})),
            "stage_policy_mode": str(args.stage_policy_mode),
        })
    save_json(stage_preview, run_dir / "stage_plan_preview.json")

    stage_csvs: List[Tuple[str, Path]] = []

    for i, stg in enumerate(stage_plan):
        stage_name = stg["name"]
        stage_dir = run_dir / stage_fs_name(i, stage_name)
        stage_dir.mkdir(parents=True, exist_ok=True)

        stage_out_csv = stage_dir / stage_out_csv_name(i)
        stage_suite_json = stage_dir / "suite.json"
        stage_ranges_json = stage_dir / "ranges.json"
        stage_done_flag = stage_dir / "DONE.txt"

        stage_csvs.append((stage_name, stage_out_csv))

        # Prepare suite (filter + scale + scenario expansion)
        suite_fs = filter_and_scale_suite(
            suite_full,
            max_stage=int(stg["max_stage"]),
            dt_scale=float(stg["dt_scale"]),
            t_end_scale=float(stg["t_end_scale"]),
        )
        suite_exp = expand_suite_by_scenarios(
            suite_fs,
            scenarios,
            base_params,
            scenario_ids=list(stg["scenario_ids"]),
        )
        if not suite_exp:
            write_progress(progress_json, {
                "status": "stage_skipped_empty_suite",
                "stage": stage_name,
                "idx": i,
                "stage_total": len(stage_plan),
                "reason": "expanded stage suite is empty for this max_stage/scenario set; explicit suite stages are preserved and earlier empty stages are skipped",
                "max_stage": int(stg["max_stage"]),
                "scenario_ids": list(stg.get("scenario_ids") or []),
            })
            continue
        save_json(suite_exp, stage_suite_json)

        # Ranges for this stage
        try:
            rj = load_json(Path(stg["ranges_json"]))
        except Exception:
            rj = load_json(ranges_json)
        save_json(rj, stage_ranges_json)

        # Warm-start: инициализация распределения поиска (cem_state) ДО первого запуска worker
        cem_state_path = Path(str(stage_out_csv) + "_cem_state.json")
        if not cem_state_path.exists():
            try:
                mode = str(args.warmstart_mode).strip().lower()
                model_sha = _file_sha1(model_path)[:12] if model_path.exists() else ""
                if mode == "surrogate":
                    ok = make_initial_cem_state_from_surrogate(
                        cem_state_path,
                        archive_path,
                        ranges=rj,
                        objective_keys=objective_keys,
                        penalty_key=penalty_key,
                        problem_hash=problem_hash,
                        model_sha_prefix=model_sha,
                        n_samples=int(args.surrogate_samples),
                        top_k=int(args.surrogate_top_k),
                        seed=int(1 + i),
                        max_train=20000,
                    )
                    if not ok:
                        make_initial_cem_state_from_archive(
                            cem_state_path,
                            archive_path,
                            ranges=rj,
                            objective_keys=objective_keys,
                            penalty_key=penalty_key,
                            problem_hash=problem_hash,
                            top_k=64,
                        )
                elif mode == "archive":
                    make_initial_cem_state_from_archive(
                        cem_state_path,
                        archive_path,
                        ranges=rj,
                        objective_keys=objective_keys,
                        penalty_key=penalty_key,
                        problem_hash=problem_hash,
                        top_k=64,
                    )
                else:
                    pass
            except Exception:
                pass

        # Skip fully completed stage
        if stage_done_flag.exists():
            write_progress(progress_json, {
                "status": "stage_skipped",
                "stage": stage_name,
                "idx": i,
                "stage_total": len(stage_plan),
                "reason": "DONE.txt exists",
            })
            continue

        if stop_file.exists():
            write_progress(progress_json, {
                "status": "stopped",
                "reason": "stop_file exists before stage",
                "stage": stage_name,
            })
            break

        # Seed-points (promotion from prev stage + best from global archive)
        seed_points_json = stage_dir / "seed_points.json"
        seed_manifest_json = stage_dir / "seed_points_manifest.json"
        seed_manifest_csv = stage_dir / "seed_points_manifest.csv"
        promotion_log_path = stage_dir / "promotion_policy_decisions.csv"
        stage_influence_summary = dict(stage_influence_summaries.get(stage_name, {}))
        seed_cap = estimate_stage_seed_cap(
            stage_idx=i,
            stage_plan=stage_plan,
            stage_preview=stage_preview,
            stage_csvs=stage_csvs,
        )
        stage_seed_plan = build_stage_seed_budget_plan(
            stage_name,
            total_seed_cap=int(seed_cap),
            requested_mode=str(args.stage_policy_mode),
            stage_influence_summary=stage_influence_summary,
        )
        seeds: List[Dict[str, Any]] = []
        try:
            if int(seed_cap) > 0:
                seeds = collect_seed_points(
                    stage_idx=i,
                    stage_csvs=stage_csvs,
                    archive_path=archive_path,
                    ranges=rj,
                    base_params=base_params,
                    stage_name=stage_name,
                    stage_policy_mode=str(stage_seed_plan.get("effective_mode") or args.stage_policy_mode),
                    stage_influence_summary=stage_influence_summary,
                    budget_plan=stage_seed_plan,
                    promotion_log_path=promotion_log_path,
                    seed_manifest_json_path=seed_manifest_json,
                    seed_manifest_csv_path=seed_manifest_csv,
                    objective_keys=objective_keys,
                    penalty_key=penalty_key,
                    problem_hash=problem_hash,
                    max_prev=int(seed_cap),
                    max_archive=int(seed_cap),
                    max_total=int(seed_cap),
                )
            if seeds:
                save_json(seeds, seed_points_json)
            else:
                # если нечего сеять — удаляем старый файл, чтобы не вводить в заблуждение
                if seed_points_json.exists():
                    try:
                        seed_points_json.unlink()
                    except Exception:
                        pass
            stage_seed_plan_payload = {
                **dict(stage_seed_plan),
                "stage": stage_name,
                "stage_idx": int(i),
                "seed_cap": int(seed_cap),
                "seed_count": int(len(seeds)),
                "minutes_budget": float(stg.get("minutes", 0.0) or 0.0),
                "influence_summary_status": str(stage_influence_summary.get("summary_status") or ""),
                "priority_params": list(stage_influence_summary.get("top_params") or []),
                "priority_mass": dict(stage_influence_summary.get("priority_mass") or {}),
                "promotion_log_csv": str(promotion_log_path),
                "seed_points_json": str(seed_points_json),
                "seed_manifest_json": str(seed_manifest_json),
                "seed_manifest_csv": str(seed_manifest_csv),
                "seed_bucket_counts": {
                    "focus": int(sum(1 for _rec in (load_json(seed_manifest_json) if seed_manifest_json.exists() else []) if str(_rec.get("selected_bucket") or "") == "focus")),
                    "explore": int(sum(1 for _rec in (load_json(seed_manifest_json) if seed_manifest_json.exists() else []) if str(_rec.get("selected_bucket") or "") == "explore")),
                },
            }
            save_json(stage_seed_plan_payload, stage_dir / "seed_budget_plan.json")
            save_json(stage_influence_summary, stage_dir / "stage_influence_summary.json")
        except Exception as exc:
            save_json({
                "stage": stage_name,
                "stage_idx": int(i),
                "seed_cap": int(seed_cap),
                "seed_count": int(len(seeds)),
                "minutes_budget": float(stg.get("minutes", 0.0) or 0.0),
                "requested_mode": str(args.stage_policy_mode),
                "effective_mode": "error",
                "error": repr(exc),
            }, stage_dir / "seed_budget_plan.json")

        if int(i) > 0 and int(len(seeds)) <= 0:
            prev_promotable_rows = 0
            try:
                prev_csv = stage_csvs[i - 1][1]
                if prev_csv.exists() and prev_csv.stat().st_size > 0:
                    df_prev = pd.read_csv(prev_csv)
                    prev_promotable_rows = int(sum(1 for _r in df_prev.to_dict(orient="records") if is_promotable_row(_r)))
            except Exception:
                prev_promotable_rows = 0
            if prev_promotable_rows <= 0:
                write_progress(progress_json, {
                    "status": "stage_skipped_no_promotable_candidates",
                    "stage": stage_name,
                    "idx": i,
                    "stage_total": len(stage_plan),
                    "reason": "previous stage produced no promotable candidates; later stage would only repeat baseline/service rows",
                    "stage_seed_points_count": 0,
                    "prev_promotable_rows": int(prev_promotable_rows),
                })
                continue

        # Run worker for this stage (resume-safe: same out_csv)
        cmd = [
            console_python_executable(sys.executable) or sys.executable,
            str(worker_path),
            "--model",
            str(model_path),
            "--out",
            str(stage_out_csv),
            "--suite_json",
            str(stage_suite_json),
            "--minutes",
            str(max(0.05, float(stg["minutes"]))),
            "--seed_candidates",
            str(int(args.seed_candidates)),
            "--seed_conditions",
            str(int(args.seed_conditions)),
            "--jobs",
            str(int(args.jobs)),
            "--flush_every",
            str(int(args.flush_every)),
            "--progress_every_sec",
            str(float(args.progress_every_sec)),
            "--base_json",
            str(base_json),
            "--ranges_json",
            str(stage_ranges_json),
            "--stop_if_pen_gt",
            str(float(stg.get("stop_if_pen_gt", float("inf")))),
            "--sort_tests_by_cost",
            str(int(args.sort_tests_by_cost)),
            "--stop_file",
            str(stop_file),
            "--skip_baseline",
            "1" if int(i) > 0 else "0",
        ]

        # Подмешиваем seed_points_json (если есть)
        if seed_points_json.exists() and seed_points_json.stat().st_size > 0:
            cmd += ["--seed_points_json", str(seed_points_json)]

        # Start worker
        stage_started_ts = float(time.time())
        stage_budget_sec = float(max(0.0, float(stg.get("minutes", 0.0) or 0.0)) * 60.0)
        write_progress(progress_json, {
            "status": "stage_running",
            "stage": stage_name,
            "idx": i,
            "stage_total": len(stage_plan),
            "cmd": cmd,
            "worker_out_csv": str(stage_out_csv),
            "stage_started_ts": float(stage_started_ts),
            "stage_budget_sec": float(stage_budget_sec),
            "stage_seed_points_count": int(len(seeds)),
            "stage_policy_mode": str(args.stage_policy_mode),
            "stage_policy_effective_mode": str(stage_seed_plan.get("effective_mode") or args.stage_policy_mode),
            "stage_seed_explore_budget": int(stage_seed_plan.get("explore_budget", 0) or 0),
            "objective_keys": list(objective_keys),
            "penalty_key": str(penalty_key),
            "stage_seed_focus_budget": int(stage_seed_plan.get("focus_budget", 0) or 0),
            "stage_policy_name": str(stage_seed_plan.get("policy_name") or ""),
            "stage_priority_params": list(stage_influence_summary.get("top_params") or []),
            "stage_seed_manifest_json": str(seed_manifest_json) if seed_manifest_json.exists() else "",
            "stage_seed_manifest_csv": str(seed_manifest_csv) if seed_manifest_csv.exists() else "",
            "stage_seed_bucket_counts": {
                "focus": int(sum(1 for _rec in (load_json(seed_manifest_json) if seed_manifest_json.exists() else []) if str(_rec.get("selected_bucket") or "") == "focus")),
                "explore": int(sum(1 for _rec in (load_json(seed_manifest_json) if seed_manifest_json.exists() else []) if str(_rec.get("selected_bucket") or "") == "explore")),
            },
            "stage_rows_done_before": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i])),
            "stage_rows_current": int(csv_data_row_count(stage_out_csv)),
            "готово_кандидатов_суммарно": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i])) + int(csv_data_row_count(stage_out_csv)),
            "готово_кандидатов_в_файле_суммарно": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i])) + int(csv_data_row_count(stage_out_csv)),
        })

        # Worker environment (defaults): guided_mode=auto + worldroad disk-cache
        env = build_stage_worker_env(
            workspace_dir,
            problem_hash,
        )

        worker_stdout_log = stage_dir / "w_out.log"
        worker_stderr_log = stage_dir / "w_err.log"
        _worker_stdout_f = None
        _worker_stderr_f = None
        try:
            _worker_stdout_f = worker_stdout_log.open('ab')
            _worker_stderr_f = worker_stderr_log.open('ab')
        except Exception:
            _worker_stdout_f = None
            _worker_stderr_f = None
        proc = subprocess.Popen(cmd, cwd=str(stage_dir), env=env, stdout=_worker_stdout_f, stderr=_worker_stderr_f)
        # Родителю не нужно держать дескрипторы открытыми после старта дочернего процесса:
        # child already inherited handles, а открытые fd у родителя создают ResourceWarning на Windows.
        _safe_close_fileobj(_worker_stdout_f)
        _safe_close_fileobj(_worker_stderr_f)
        _worker_stdout_f = None
        _worker_stderr_f = None
        worker_progress_path = stage_worker_progress_path(stage_out_csv)
        try:
            if not worker_progress_path.exists():
                write_json({
                    "статус": "bootstrapping",
                    "phase": "startup",
                    "ts_start": float(stage_started_ts),
                    "ts_last_write": float(time.time()),
                    "готово_кандидатов": 0,
                    "готово_кандидатов_в_файле": 0,
                    "прошло_сек": 0.0,
                    "лимит_минут": float(stg.get("minutes", 0.0) or 0.0),
                    "последний_batch": 0,
                }, worker_progress_path)
        except Exception:
            pass
        last_live_merge_sig: Optional[Tuple[int, int]] = None
        startup_grace_sec = float(min(180.0, max(90.0, stage_budget_sec * 0.50)))
        idle_timeout_sec = float(max(60.0, min(180.0, stage_budget_sec * 0.75 if stage_budget_sec > 0 else 60.0)))
        hard_timeout_sec = float(max(stage_budget_sec + idle_timeout_sec, stage_budget_sec * 2.5, startup_grace_sec + idle_timeout_sec))
        last_activity_ts = float(stage_started_ts)
        last_progress_ts_seen = 0.0

        # Poll
        while proc.poll() is None:
            if stop_file.exists():
                # Let the worker notice stop_file and exit.
                pass
            stage_rows_before = int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i]))
            current_stage_rows = int(csv_data_row_count(stage_out_csv))
            try:
                if stage_out_csv.exists():
                    stage_sig_now = (int(current_stage_rows), int(stage_out_csv.stat().st_size))
                    if stage_sig_now != last_live_merge_sig:
                        last_activity_ts = float(time.time())
                elif current_stage_rows > 0:
                    last_activity_ts = float(time.time())
            except Exception:
                pass
            worker_progress_payload: Optional[Dict[str, Any]] = None
            if worker_progress_path.exists():
                try:
                    worker_progress_payload = load_json(worker_progress_path)
                    last_progress_ts = float(worker_progress_payload.get("ts_last_write", 0.0) or 0.0)
                    if last_progress_ts > last_progress_ts_seen:
                        last_progress_ts_seen = last_progress_ts
                        last_activity_ts = max(last_activity_ts, last_progress_ts)
                except Exception:
                    worker_progress_payload = None
            if (current_stage_rows <= 0) and (not worker_progress_path.exists()) and (float(max(0.0, time.time() - stage_started_ts)) > startup_grace_sec):
                try:
                    terminate_process_tree(proc, grace_sec=0.8, reason="stage_runner_worker_startup_timeout")
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                write_progress(progress_json, {
                    "status": "failed_worker_startup",
                    "stage": stage_name,
                    "idx": i,
                    "stage_total": len(stage_plan),
                    "worker_out_csv": str(stage_out_csv),
                    "worker_progress_json": str(worker_progress_path),
                    "worker_stdout_log": str(worker_stdout_log),
                    "worker_stderr_log": str(worker_stderr_log),
                    "stage_elapsed_sec": float(max(0.0, time.time() - stage_started_ts)),
                    "stage_budget_sec": float(stage_budget_sec),
                    "error": "worker produced neither CSV rows nor progress within startup grace window",
                })
                return 5
            elapsed_sec = float(max(0.0, time.time() - stage_started_ts))
            idle_sec = float(max(0.0, time.time() - last_activity_ts))
            if (elapsed_sec > hard_timeout_sec) and (idle_sec > idle_timeout_sec):
                try:
                    terminate_process_tree(proc, grace_sec=0.8, reason="stage_runner_worker_stall_timeout")
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                write_progress(progress_json, {
                    "status": "failed_stage_timeout",
                    "stage": stage_name,
                    "idx": i,
                    "stage_total": len(stage_plan),
                    "worker_out_csv": str(stage_out_csv),
                    "worker_progress_json": str(worker_progress_path),
                    "worker_stdout_log": str(worker_stdout_log),
                    "worker_stderr_log": str(worker_stderr_log),
                    "stage_elapsed_sec": float(elapsed_sec),
                    "stage_budget_sec": float(stage_budget_sec),
                    "stage_idle_sec": float(idle_sec),
                    "worker_last_progress_ts": float(last_progress_ts_seen),
                    "error": "worker exceeded hard timeout and stopped making progress; likely stalled",
                })
                return 6
            payload = {
                "status": "stage_running",
                "stage": stage_name,
                "idx": i,
                "stage_total": len(stage_plan),
                "worker_out_csv": str(stage_out_csv),
                "stage_started_ts": float(stage_started_ts),
                "stage_budget_sec": float(stage_budget_sec),
                "stage_elapsed_sec": float(max(0.0, time.time() - stage_started_ts)),
                "stage_seed_points_count": int(len(seeds)),
                "stage_rows_done_before": int(stage_rows_before),
                "stage_rows_current": int(current_stage_rows),
                "готово_кандидатов_суммарно": int(stage_rows_before + current_stage_rows),
                "готово_кандидатов_в_файле_суммарно": int(stage_rows_before + current_stage_rows),
            }
            if worker_progress_payload is not None:
                try:
                    wp = dict(worker_progress_payload)
                    try:
                        wp_done = int(wp.get("готово_кандидатов", 0) or 0)
                    except Exception:
                        wp_done = 0
                    try:
                        wp_written = int(wp.get("готово_кандидатов_в_файле", wp_done) or wp_done)
                    except Exception:
                        wp_written = wp_done
                    if current_stage_rows > max(wp_done, wp_written):
                        wp["готово_кандидатов"] = int(current_stage_rows)
                        wp["готово_кандидатов_в_файле"] = int(current_stage_rows)
                        wp["worker_progress_stale"] = True
                    payload["worker_progress"] = wp
                except Exception:
                    pass
            try:
                if stage_out_csv.exists():
                    sig = (int(current_stage_rows), int(stage_out_csv.stat().st_size))
                    if sig != last_live_merge_sig:
                        rebuild_combined_csv(out_csv, stage_csvs)
                        last_live_merge_sig = sig
                elif last_live_merge_sig is None:
                    rebuild_combined_csv(out_csv, stage_csvs)
                    last_live_merge_sig = (0, 0)
            except Exception:
                pass
            # best so far
            best = pick_best_row(stage_out_csv, objective_keys=objective_keys, penalty_key=penalty_key)
            if best:
                payload["best"] = {
                    "score": list(score_row(best)),
                    "id": best.get("id"),
                }
            write_progress(progress_json, payload)
            time.sleep(max(0.5, float(args.progress_every_sec)))

        rc = int(proc.returncode or 0)

        # Archive results
        append_csv_to_archive_jsonl(
            archive_path,
            stage_out_csv,
            meta={
                "ts": _now_ts(),
                "run_dir": str(run_dir),
                "model_sha1": _file_sha1(model_path)[:12] if model_path.exists() else "",
                "base_hash": stable_obj_hash(base_params)[:12],
                "suite_hash": stable_obj_hash(suite_exp)[:12],
                "ranges_hash": stable_obj_hash(rj)[:12],
                "problem_hash": str(problem_hash),
                "objective_contract": dict(objective_contract),
            },
            stage_name=stage_name,
            archived_ids_path=archived_ids_path,
        )

        # Mark stage done if not stopped and worker exited cleanly
        if (rc == 0) and (not stop_file.exists()):
            stage_done_flag.write_text(f"DONE rc={rc} { _now_ts() }\n", encoding="utf-8")

        # Update combined CSV
        rebuild_combined_csv(out_csv, stage_csvs)

        if rc != 0:
            write_progress(progress_json, {
                "status": "failed_worker_rc",
                "stage": stage_name,
                "idx": i,
                "stage_total": len(stage_plan),
                "returncode": rc,
                "worker_out_csv": str(stage_out_csv),
                "worker_progress_json": str(worker_progress_path),
                "worker_stdout_log": str(worker_stdout_log),
                "worker_stderr_log": str(worker_stderr_log),
                "stage_started_ts": float(stage_started_ts),
                "stage_budget_sec": float(stage_budget_sec),
                "stage_elapsed_sec": float(max(0.0, time.time() - stage_started_ts)),
                "stage_rows_done_before": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i])),
                "stage_rows_current": int(csv_data_row_count(stage_out_csv)),
                "error": "worker exited with non-zero return code",
            })
            return 7

        # Update progress
        write_progress(progress_json, {
            "status": "stage_finished",
            "stage": stage_name,
            "idx": i,
            "stage_total": len(stage_plan),
            "returncode": rc,
            "stage_started_ts": float(stage_started_ts),
            "stage_budget_sec": float(stage_budget_sec),
            "stage_elapsed_sec": float(max(0.0, time.time() - stage_started_ts)),
            "stage_rows_done_before": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i])),
            "stage_rows_current": int(csv_data_row_count(stage_out_csv)),
            "готово_кандидатов_суммарно": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i+1])),
            "готово_кандидатов_в_файле_суммарно": int(sum(csv_data_row_count(p) for _, p in stage_csvs[:i+1])),
        })

        if stop_file.exists():
            write_progress(progress_json, {
                "status": "stopped",
                "stage": stage_name,
                "idx": i,
                "stage_total": len(stage_plan),
                "reason": "stop_file",
            })
            break

    if not any(p.exists() and p.stat().st_size > 0 for _, p in stage_csvs):
        write_progress(progress_json, {
            "status": "failed_all_stage_suites_empty",
            "error": "All expanded stage suites are empty. Проверьте явные stage номера suite относительно stage0/stage1/stage2.",
            "stage_total": len(stage_plan),
        })
        return 4

    # Final baseline update
    if int(args.autoupdate_baseline) == 1:
        # pick best row from the last finished stage with actual file
        best_row: Optional[Dict[str, Any]] = None
        best_stage_name = ""
        for stage_name, p in reversed(stage_csvs):
            br = pick_best_row(p, objective_keys=objective_keys, penalty_key=penalty_key)
            if br is not None:
                best_row = br
                best_stage_name = str(stage_name or "")
                break
        if best_row is not None:
            baseline_dir = workspace_dir / "baselines"
            baseline_dir.mkdir(parents=True, exist_ok=True)
            best_params = extract_params_from_row(best_row)
            # Keep only plain numeric values
            clean: Dict[str, Any] = {}
            for k, v in best_params.items():
                try:
                    clean[k] = float(v)
                except Exception:
                    continue
            new_score = list(score_row(best_row, objective_keys=objective_keys, penalty_key=penalty_key))
            new_score_payload = score_payload(
                new_score,
                objective_keys=objective_keys,
                penalty_key=penalty_key,
                source="opt_stage_runner_v1_baseline",
            )
            new_score_payload["problem_hash"] = str(problem_hash)
            new_score_payload["run_dir"] = str(run_dir)
            new_score_payload["stage_name"] = str(best_stage_name)
            new_score_payload["objective_contract"] = dict(objective_contract)
            score_path = baseline_dir / "baseline_best_score.json"
            meta_path = baseline_dir / "baseline_best_meta.json"
            prev_score_raw = None
            prev_score_payload = None
            if score_path.exists():
                try:
                    prev_score_raw = load_json(score_path)
                    prev_score_payload = parse_saved_score_payload(prev_score_raw)
                except Exception:
                    prev_score_raw = None
                    prev_score_payload = None

            prev_baseline_meta = load_baseline_best_meta(
                baseline_dir,
                prev_score_raw=prev_score_raw,
            )
            baseline_meta = baseline_best_meta_payload(
                problem_hash=problem_hash,
                objective_contract=objective_contract,
                run_dir=run_dir,
                stage_name=best_stage_name,
                score=new_score,
                score_payload_obj=new_score_payload,
                params=clean,
            )
            scoped_baseline_dir = baseline_problem_scope_dir(baseline_dir, problem_hash)
            scoped_baseline_dir.mkdir(parents=True, exist_ok=True)
            save_json(clean, scoped_baseline_dir / "baseline_best.json")
            save_json(new_score_payload, scoped_baseline_dir / "baseline_best_score.json")
            save_json(baseline_meta, scoped_baseline_dir / "baseline_best_meta.json")

            apply_update, apply_reason = decide_baseline_autoupdate(
                new_score=new_score,
                objective_keys=objective_keys,
                penalty_key=penalty_key,
                problem_hash=problem_hash,
                prev_score_payload=prev_score_payload,
                prev_meta=prev_baseline_meta,
            )

            if apply_update:
                save_json(clean, baseline_dir / "baseline_best.json")
                save_json(new_score_payload, score_path)
                save_json(baseline_meta, meta_path)

            # history
            hist_path = baseline_dir / "baseline_history.jsonl"
            with hist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": _now_ts(),
                    "run_dir": str(run_dir),
                    "score": new_score,
                    "score_payload": new_score_payload,
                    "applied": bool(apply_update),
                    "apply_reason": str(apply_reason),
                    "prev_score": prev_score_raw,
                    "prev_score_payload": prev_score_payload,
                    "problem_hash": str(problem_hash),
                    "objective_contract": dict(objective_contract),
                    "baseline_meta": baseline_meta,
                    "prev_baseline_meta": prev_baseline_meta,
                    "scoped_baseline_dir": str(scoped_baseline_dir),
                    "params": clean,
                }, ensure_ascii=False) + "\n")

    write_progress(progress_json, {
        "status": "done",
        "run_dir": str(run_dir),
        "combined_csv": str(out_csv),
        "archive": str(archive_path),
    })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
