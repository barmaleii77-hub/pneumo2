# -*- coding: utf-8 -*-
"""dist_opt_coordinator.py

Release 59: Distributed optimization coordinator (Ray / Dask).

Key features (R59)
-----------------
- **Integrated, working ExperimentDB API** (sqlite/duckdb) used consistently by coordinator.
- **Resume** with stale-trial requeue (heartbeat TTL).
- **Optional BoTorch qNEHVI proposer** (GPU-friendly) with proper X_pending handling.
- **(Ray) GPU proposer pool (portfolio)**: use 1..N GPU actors to generate candidates concurrently.
- **Artifacts**: every trial is additionally saved as JSON in run_dir/artifacts/trials/
  for post-mortem analysis even if the DB becomes damaged.
- **Exports**: periodic and final CSV exports for external analysis.

See:
- docs/31_DistributedOptimization_R59.md

Notes
-----
This script is intentionally separate from Streamlit UI.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np

# Ensure pneumo_solver_ui is importable regardless of current working directory
_THIS = Path(__file__).resolve()
_PNEUMO_ROOT = _THIS.parent.parent  # .../pneumo_solver_ui
_PROJECT_ROOT = _PNEUMO_ROOT.parent   # .../project root
for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pneumo_solver_ui.pneumo_dist.eval_core import EvaluatorCore, sample_lhs
from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
from pneumo_solver_ui.pneumo_dist.hv_tools import fit_normalizer, hypervolume_min, infer_reference_point_min
from pneumo_solver_ui.pneumo_dist.mobo_propose import propose_heuristic, propose_qnehvi, propose_random
from pneumo_solver_ui.pneumo_dist.trial_hash import (
    hash_params,
    hash_vector,
    make_problem_spec,
    hash_problem,
    stable_hash_problem,
)
from pneumo_solver_ui.optimization_problem_hash_mode import (
    normalize_problem_hash_mode,
    problem_hash_mode_from_env,
    write_problem_hash_mode_artifact,
)
from pneumo_solver_ui.optimization_objective_contract import objective_contract_payload
from pneumo_solver_ui.optimization_baseline_source import (
    resolve_workspace_baseline_source,
    write_baseline_source_artifact,
)
from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIST_OPT_BOTORCH_MAXITER_DEFAULT,
    DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT,
    DIST_OPT_BOTORCH_N_INIT_DEFAULT,
    DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT,
    DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT,
    DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT,
    DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT,
    DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT,
    DIST_OPT_DB_ENGINE_DEFAULT,
    DIST_OPT_EXPORT_EVERY_DEFAULT,
    DIST_OPT_HV_LOG_DEFAULT,
    DIST_OPT_HEURISTIC_EXPLORE_DEFAULT,
    DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT,
    DIST_OPT_PENALTY_KEY_DEFAULT,
    DIST_OPT_PENALTY_TOL_DEFAULT,
    DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT,
    DIST_OPT_STALE_TTL_SEC_DEFAULT,
)


def apply_problem_hash_env(
    problem_hash: str | None,
    env: Optional[MutableMapping[str, str]] = None,
) -> MutableMapping[str, str]:
    target = env if env is not None else os.environ
    current_problem_hash = str(problem_hash or "").strip()
    if current_problem_hash:
        target["PNEUMO_OPT_PROBLEM_HASH"] = current_problem_hash
    else:
        target.pop("PNEUMO_OPT_PROBLEM_HASH", None)
    return target


def build_run_record_meta(
    args: argparse.Namespace,
    *,
    objective_keys: Sequence[str],
    problem_hash_mode: str,
) -> Dict[str, Any]:
    return {
        "created_by": "dist_opt_coordinator_R59",
        "backend": str(getattr(args, "backend", "")),
        "seed": int(getattr(args, "seed", 0) or 0),
        "problem_hash_mode": normalize_problem_hash_mode(problem_hash_mode, default="stable"),
        "proposer": str(getattr(args, "proposer", "auto") or "auto"),
        "heuristic_pool_size": int(getattr(args, "heuristic_pool_size", DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT) or DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
        "heuristic_explore": float(getattr(args, "heuristic_explore", DIST_OPT_HEURISTIC_EXPLORE_DEFAULT) or DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
        "objective_contract": objective_contract_payload(
            objective_keys=objective_keys,
            penalty_key=str(getattr(args, "penalty_key", "")),
            penalty_tol=getattr(args, "penalty_tol", None),
            source="dist_opt_coordinator_run_meta_v1",
        ),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Distributed optimization coordinator (Release59)")

    p.add_argument("--backend", choices=["ray", "dask"], default="ray")

    # Ray
    p.add_argument("--ray-address", default="auto", help="Ray cluster address, e.g. auto / 127.0.0.1:6379 / local")
    p.add_argument(
        "--ray-runtime-env",
        choices=["auto", "on", "off"],
        default=DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT,
        help="Use Ray runtime_env working_dir to ship code to cluster. auto=on for cluster, off for local.",
    )
    p.add_argument(
        "--ray-runtime-env-json",
        default="",
        help="Optional JSON object merged into Ray runtime_env after working_dir/excludes are prepared.",
    )
    p.add_argument(
        "--ray-runtime-exclude",
        action="append",
        default=[],
        help="Pattern to exclude from runtime_env working_dir upload. Repeatable.",
    )
    p.add_argument("--ray-local-num-cpus", type=int, default=0, help="When --ray-address=local: num_cpus for ray.init(0=auto)")
    p.add_argument("--ray-local-dashboard", action="store_true", help="When --ray-address=local: request Ray dashboard")
    p.add_argument("--ray-local-dashboard-port", type=int, default=0, help="When --ray-address=local and dashboard enabled: 0=auto")
    p.add_argument("--ray-num-evaluators", type=int, default=0, help="0=auto (cpu count), else number of evaluator actors")
    p.add_argument("--ray-cpus-per-evaluator", type=float, default=1.0)

    # GPU proposer pool
    p.add_argument(
        "--ray-num-proposers",
        type=int,
        default=0,
        help="0=auto (use available GPUs if qNEHVI), N=spawn N proposer actors (Ray only).",
    )
    p.add_argument("--ray-gpus-per-proposer", type=float, default=1.0)
    p.add_argument(
        "--proposer-buffer",
        type=int,
        default=32,
        help="How many proposed candidates to keep in local buffer (Ray proposer pool).",
    )

    # Dask
    p.add_argument("--dask-scheduler", default="", help="Dask scheduler address (host:port). If empty, uses LocalCluster.")
    p.add_argument("--dask-workers", type=int, default=0, help="LocalCluster workers (0=auto)")
    p.add_argument("--dask-threads-per-worker", type=int, default=DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT)
    p.add_argument("--dask-memory-limit", default="", help="LocalCluster memory_limit. Empty=auto, 0/none=disable limit.")
    p.add_argument("--dask-dashboard-address", default=DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT, help="LocalCluster dashboard_address. Empty/none=disable, :0=auto port.")

    # Core problem (paths are relative to pneumo_solver_ui by default)
    p.add_argument(
        "--model",
        default="model_pneumo_v9_doublewishbone_camozzi.py",
        help="Model file path (relative to pneumo_solver_ui or absolute).",
    )
    p.add_argument(
        "--worker",
        default="opt_worker_v3_margins_energy.py",
        help="Worker evaluation file path (relative to pneumo_solver_ui or absolute).",
    )
    p.add_argument("--base-json", default="default_base.json", help="Override base JSON (defaults to canonical default_base.json)")
    p.add_argument("--ranges-json", default="default_ranges.json", help="Override ranges JSON (defaults to canonical default_ranges.json)")
    p.add_argument("--suite-json", default="default_suite.json", help="Override suite JSON (defaults to canonical default_suite.json)")

    # Objectives / constraints
    p.add_argument(
        "--objective",
        action="append",
        default=[],
        help="Objective key in metrics row. Repeat to set multiple objectives.",
    )
    p.add_argument("--penalty-key", default=DIST_OPT_PENALTY_KEY_DEFAULT)
    p.add_argument("--penalty-tol", type=float, default=DIST_OPT_PENALTY_TOL_DEFAULT)

    # Run config
    p.add_argument("--budget", type=int, default=200, help="Number of successful (DONE) trials to collect")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-inflight", type=int, default=0, help="0=auto (2*workers)")
    p.add_argument(
        "--seed-json",
        default="",
        help="Optional JSON with seed candidates from staged optimization. Supports [{params...}], [{'params': {...}}], or [{'x_u': [...]}].",
    )

    # Proposer
    p.add_argument("--proposer", choices=["random", "heuristic", "qnehvi", "auto", "portfolio"], default="auto")
    p.add_argument("--q", type=int, default=1, help="How many candidates to propose per call")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--n-init", type=int, default=DIST_OPT_BOTORCH_N_INIT_DEFAULT, help="Minimum DONE trials before qNEHVI may be used (0=auto threshold based on dim).")
    p.add_argument("--min-feasible", type=int, default=DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT, help="Minimum feasible DONE trials before qNEHVI may be used (0=disabled).")
    p.add_argument("--botorch-num-restarts", type=int, default=DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT)
    p.add_argument("--botorch-raw-samples", type=int, default=DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT)
    p.add_argument("--botorch-maxiter", type=int, default=DIST_OPT_BOTORCH_MAXITER_DEFAULT)
    p.add_argument("--botorch-ref-margin", type=float, default=DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT)
    p.add_argument("--botorch-no-normalize-objectives", action="store_true", help="Disable objective normalization before qNEHVI GP fit.")
    p.add_argument(
        "--heuristic-pool-size",
        type=int,
        default=DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT,
        help="Candidate pool size used by heuristic proposer and fallbacks.",
    )
    p.add_argument(
        "--heuristic-explore",
        type=float,
        default=DIST_OPT_HEURISTIC_EXPLORE_DEFAULT,
        help="Exploration weight (0..1) for heuristic proposer and fallbacks.",
    )

    # Experiment DB
    p.add_argument("--db", default="runs/expdb.sqlite", help="Path to experiment DB file (sqlite/duckdb) OR DSN for postgres (e.g. postgresql://user:pass@host:5432/dbname)")
    p.add_argument("--db-engine", choices=["sqlite", "duckdb", "postgres"], default=DIST_OPT_DB_ENGINE_DEFAULT)

    # Resume
    p.add_argument("--resume", action="store_true")
    p.add_argument("--run-id", default="", help="Explicit run_id to resume")
    p.add_argument("--stale-ttl-sec", type=int, default=DIST_OPT_STALE_TTL_SEC_DEFAULT)

    # Logging / artifacts
    p.add_argument("--run-dir", default="", help="Run output dir (default runs/run_<run_id>)")
    p.add_argument("--hv-log", dest="hv_log", action="store_true", help="Log hypervolume progress (feasible points)")
    p.add_argument("--no-hv-log", dest="hv_log", action="store_false", help="Disable hypervolume progress log")
    p.set_defaults(hv_log=DIST_OPT_HV_LOG_DEFAULT)
    p.add_argument("--export-every", type=int, default=DIST_OPT_EXPORT_EVERY_DEFAULT, help="Export CSV every N DONE trials")

    return p


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    return build_arg_parser().parse_args(list(argv) if argv is not None else None)



def _now() -> float:
    return time.time()


def _resolve_rel_or_abs(path_str: str) -> str:
    """Return normalized path string (keep absolute, keep relative as-is)."""
    p = Path(path_str)
    return str(p) if p.is_absolute() else str(Path(path_str))


def _abs_under(base_dir: Path, path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str((base_dir / p).resolve())


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _dump_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _load_seed_vectors(
    core: EvaluatorCore,
    seed_json: str | Path | None,
) -> Tuple[List[List[float]], Dict[str, Any]]:
    path_s = str(seed_json or "").strip()
    if not path_s:
        return [], {"seed_json": "", "loaded": 0, "invalid": 0, "duplicates": 0}
    path = Path(path_s)
    if not path.exists():
        return [], {"seed_json": str(path), "loaded": 0, "invalid": 0, "duplicates": 0, "missing": True}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], {"seed_json": str(path), "loaded": 0, "invalid": 1, "duplicates": 0, "error": repr(exc)}

    if not isinstance(raw, list):
        return [], {"seed_json": str(path), "loaded": 0, "invalid": 1, "duplicates": 0, "error": "seed json must be a list"}

    dim = int(core.dim())
    loaded: List[List[float]] = []
    invalid = 0
    duplicates = 0
    seen: set[str] = set()

    for item in raw:
        x_u: Optional[List[float]] = None
        try:
            if isinstance(item, Mapping):
                if isinstance(item.get("x_u"), list):
                    x_arr = np.asarray(item.get("x_u"), dtype=float)
                    if x_arr.shape == (dim,) and np.isfinite(x_arr).all():
                        x_u = [float(v) for v in np.clip(x_arr, 0.0, 1.0).tolist()]
                elif isinstance(item.get("params"), Mapping):
                    x_u = list(core.params_to_u(dict(item.get("params") or {})))
                else:
                    x_u = list(core.params_to_u(dict(item)))
            elif isinstance(item, list):
                x_arr = np.asarray(item, dtype=float)
                if x_arr.shape == (dim,) and np.isfinite(x_arr).all():
                    x_u = [float(v) for v in np.clip(x_arr, 0.0, 1.0).tolist()]
        except Exception:
            x_u = None

        if x_u is None:
            invalid += 1
            continue
        sig = str(hash_vector(x_u, float_ndigits=12))
        if sig in seen:
            duplicates += 1
            continue
        seen.add(sig)
        loaded.append(list(x_u))

    return loaded, {
        "seed_json": str(path.resolve()),
        "loaded": int(len(loaded)),
        "invalid": int(invalid),
        "duplicates": int(duplicates),
        "dim": int(dim),
    }


def _normalize_dask_memory_limit(raw: Any) -> Any:
    txt = str(raw or "").strip()
    if not txt or txt.lower() == "auto":
        return "auto"
    if txt.lower() in {"0", "none", "off", "disable", "disabled", "no"}:
        return None
    return txt


def _normalize_dashboard_address(raw: Any) -> Optional[str]:
    txt = str(raw or "").strip()
    if not txt or txt.lower() in {"none", "off", "disable", "disabled", "no"}:
        return None
    return txt


def _parse_runtime_env_json(raw: Any) -> Dict[str, Any]:
    txt = str(raw or "").strip()
    if not txt:
        return {}
    obj = json.loads(txt)
    if not isinstance(obj, dict):
        raise ValueError("--ray-runtime-env-json must be a JSON object")
    return dict(obj)



def _count_feasible_trials(g_rows: Sequence[Sequence[float]] | None) -> int:
    if g_rows is None:
        return 0
    try:
        rows = list(g_rows)
    except Exception:
        return 0
    if not rows:
        return 0

    feasible = 0
    for row in rows:
        try:
            arr = np.asarray(row, dtype=float).reshape(-1)
        except Exception:
            try:
                arr = np.asarray([row], dtype=float).reshape(-1)
            except Exception:
                continue
        if arr.size == 0:
            continue
        if not np.all(np.isfinite(arr)):
            continue
        if np.all(arr <= 0.0):
            feasible += 1
    return int(feasible)



def _heuristic_penalty_from_constraints(g_rows: Sequence[Sequence[float]] | None) -> Optional[np.ndarray]:
    """Convert constraint vectors (<=0 feasible) into one violation scalar per point."""
    if g_rows is None:
        return None
    try:
        rows = list(g_rows)
    except Exception:
        return None
    if not rows:
        return None

    penalties: List[float] = []
    for row in rows:
        try:
            arr = np.asarray(row, dtype=float).reshape(-1)
        except Exception:
            try:
                arr = np.asarray([row], dtype=float).reshape(-1)
            except Exception:
                arr = np.asarray([], dtype=float)
        if arr.size == 0 or not np.all(np.isfinite(arr)):
            penalties.append(float("nan"))
            continue
        penalties.append(float(np.max(arr)))
    if not penalties:
        return None
    return np.asarray(penalties, dtype=float)


def _clamp_unit_interval(value: Any, *, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    if not np.isfinite(out):
        out = float(default)
    if out < 0.0:
        return 0.0
    if out > 1.0:
        return 1.0
    return float(out)


def _adaptive_heuristic_explore_weight(
    base_explore: Any,
    *,
    stagnation_cycles: int,
    rescue_limit_cycles: int,
) -> float:
    base = _clamp_unit_interval(
        base_explore,
        default=float(DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
    )
    stagnation = max(0, int(stagnation_cycles))
    if stagnation <= 0:
        return float(base)
    limit = max(1, int(rescue_limit_cycles))
    ratio = min(1.0, float(stagnation) / float(limit))
    return float(min(1.0, base + (1.0 - base) * ratio))


def _coerce_positive_int(value: Any, *, default: int = 1) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    if out <= 0:
        out = int(default)
    return int(max(1, out))


def _coerce_nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    if out < 0:
        out = int(default)
    return int(max(0, out))


def _adaptive_heuristic_pool_size(
    base_pool_size: Any,
    *,
    stagnation_cycles: int,
    rescue_limit_cycles: int,
) -> int:
    base = _coerce_positive_int(
        base_pool_size,
        default=int(DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
    )
    stagnation = max(0, int(stagnation_cycles))
    if stagnation <= 0:
        return int(base)
    limit = max(1, int(rescue_limit_cycles))
    ratio = min(1.0, float(stagnation) / float(limit))
    boosted = int(math.ceil(float(base) * (1.0 + ratio)))
    cap = int(max(base, min(4096, 2 * base)))
    return int(max(base, min(cap, boosted)))


def _adaptive_heuristic_q(
    base_q: Any,
    *,
    need: int,
    stagnation_cycles: int,
    rescue_limit_cycles: int,
) -> int:
    base = _coerce_positive_int(base_q, default=1)
    need_i = _coerce_positive_int(need, default=1)
    stagnation = max(0, int(stagnation_cycles))
    if stagnation <= 0:
        return int(max(need_i, base))
    limit = max(1, int(rescue_limit_cycles))
    ratio = min(1.0, float(stagnation) / float(limit))
    boosted = int(math.ceil(float(base) * (1.0 + ratio)))
    cap = int(max(base, min(64, 4 * base)))
    effective = int(max(base, min(cap, boosted)))
    return int(max(need_i, effective))


def _adaptive_heuristic_buffer_target(
    base_buffer: Any,
    *,
    stagnation_cycles: int,
    rescue_limit_cycles: int,
) -> int:
    base = _coerce_positive_int(base_buffer, default=1)
    stagnation = max(0, int(stagnation_cycles))
    if stagnation <= 0:
        return int(base)
    limit = max(1, int(rescue_limit_cycles))
    ratio = min(1.0, float(stagnation) / float(limit))
    boosted = int(math.ceil(float(base) * (1.0 + ratio)))
    cap = int(max(base, min(256, 4 * base)))
    return int(max(base, min(cap, boosted)))


def _adaptive_portfolio_rand_q(
    need: Any,
    *,
    stagnation_cycles: int,
    rescue_limit_cycles: int,
) -> Tuple[int, int]:
    need_i = _coerce_positive_int(need, default=1)
    base = int(max(1, need_i // 4))
    stagnation = max(0, int(stagnation_cycles))
    if stagnation <= 0:
        return int(base), int(base)
    limit = max(1, int(rescue_limit_cycles))
    ratio = min(1.0, float(stagnation) / float(limit))
    bonus = int(max(1, math.ceil(ratio * max(1, base))))
    cap = int(max(base, min(64, max(2, 2 * base))))
    effective = int(max(base, min(cap, base + bonus)))
    return int(base), int(effective)


def _portfolio_record_event(
    history: List[Dict[str, Any]],
    *,
    mode: str,
    success: bool,
    maxlen: int = 12,
) -> None:
    mode_key = str(mode or "").strip().lower()
    if mode_key not in {"qnehvi", "heuristic"}:
        return
    history.append({"mode": mode_key, "success": bool(success)})
    cap = max(1, int(maxlen))
    if len(history) > cap:
        del history[:-cap]


def _portfolio_choose_primary_mode(
    history: Sequence[Mapping[str, Any]],
    *,
    lookback: int = 8,
    min_attempts_per_mode: int = 3,
    min_success_gap: float = 0.20,
    previous_choice: Optional[str] = None,
    switch_hysteresis_gap: float = 0.10,
    switch_cooldown_ticks: int = 0,
    cooldown_override_gap: float = 0.35,
) -> Tuple[str, str, Dict[str, int]]:
    records = list(history)[-max(1, int(lookback)) :]
    stats = {
        "qnehvi_attempts": 0,
        "qnehvi_successes": 0,
        "heuristic_attempts": 0,
        "heuristic_successes": 0,
    }
    for rec in records:
        mode_key = str(rec.get("mode") or "").strip().lower()
        ok = bool(rec.get("success"))
        if mode_key == "qnehvi":
            stats["qnehvi_attempts"] += 1
            if ok:
                stats["qnehvi_successes"] += 1
        elif mode_key == "heuristic":
            stats["heuristic_attempts"] += 1
            if ok:
                stats["heuristic_successes"] += 1

    q_att = int(stats["qnehvi_attempts"])
    h_att = int(stats["heuristic_attempts"])
    q_rate = (float(stats["qnehvi_successes"]) / float(q_att)) if q_att > 0 else 0.0
    h_rate = (float(stats["heuristic_successes"]) / float(h_att)) if h_att > 0 else 0.0

    min_att = max(1, int(min_attempts_per_mode))
    gap = max(0.0, float(min_success_gap))
    hysteresis = max(0.0, float(switch_hysteresis_gap))
    prev_key = str(previous_choice or "").strip().lower()
    cooldown = max(0, int(switch_cooldown_ticks))
    cooldown_boost = max(0.0, float(cooldown_override_gap))
    if q_att >= min_att and h_att >= min_att:
        decision = ""
        decision_reason = ""
        if prev_key == "heuristic":
            if h_rate >= (q_rate + gap):
                decision = "heuristic"
                decision_reason = "recent_heuristic_outperforming"
            elif q_rate >= (h_rate + gap + hysteresis):
                decision = "qnehvi"
                decision_reason = "recent_qnehvi_outperforming"
            else:
                decision = "heuristic"
                decision_reason = "sticky_hysteresis"
        elif prev_key == "qnehvi":
            if q_rate >= (h_rate + gap):
                decision = "qnehvi"
                decision_reason = "recent_qnehvi_outperforming"
            elif h_rate >= (q_rate + gap + hysteresis):
                decision = "heuristic"
                decision_reason = "recent_heuristic_outperforming"
            else:
                decision = "qnehvi"
                decision_reason = "sticky_hysteresis"
        else:
            if h_rate >= (q_rate + gap):
                decision = "heuristic"
                decision_reason = "recent_heuristic_outperforming"
            elif q_rate >= (h_rate + gap):
                decision = "qnehvi"
                decision_reason = "recent_qnehvi_outperforming"
        if decision:
            if prev_key in {"qnehvi", "heuristic"} and decision in {"qnehvi", "heuristic"} and decision != prev_key and cooldown > 0:
                rate_delta = abs(float(q_rate) - float(h_rate))
                strong_switch_gap = float(gap + hysteresis + cooldown_boost)
                if rate_delta < strong_switch_gap:
                    return str(prev_key), "cooldown_hold", stats
            return str(decision), str(decision_reason), stats
    if records and prev_key == "heuristic":
        return "heuristic", "sticky_previous_choice", stats
    return "qnehvi", "default_qnehvi", stats


def resolve_proposer_mode(
    args: argparse.Namespace,
    *,
    done_n: int,
    feasible_n: int,
    dim: int,
) -> Dict[str, Any]:
    requested = str(getattr(args, "proposer", "auto") or "auto").strip().lower()
    known_modes = {"auto", "random", "heuristic", "qnehvi", "portfolio"}
    auto_n_init = max(10, 2 * (int(dim) + 1))
    n_init = int(getattr(args, "n_init", 0) or 0)
    if n_init <= 0:
        n_init = int(auto_n_init)
    min_feasible = max(0, int(getattr(args, "min_feasible", 0) or 0))

    ready_by_done = int(done_n) >= int(n_init)
    ready_by_feasible = int(feasible_n) >= int(min_feasible) if min_feasible > 0 else True

    mode = requested
    portfolio_enabled = requested == "portfolio"
    unsupported_requested = requested not in known_modes
    if unsupported_requested:
        mode = "random"
        portfolio_enabled = False
    elif requested == "auto":
        mode = "qnehvi" if (ready_by_done and ready_by_feasible) else "random"
    elif requested in {"qnehvi", "portfolio"} and not (ready_by_done and ready_by_feasible):
        mode = "random"

    if requested == "portfolio" and not (ready_by_done and ready_by_feasible):
        portfolio_enabled = False

    return {
        "requested": requested,
        "mode": mode,
        "portfolio_enabled": bool(portfolio_enabled),
        "n_init": int(n_init),
        "min_feasible": int(min_feasible),
        "ready_by_done": bool(ready_by_done),
        "ready_by_feasible": bool(ready_by_feasible),
        "unsupported_requested": bool(unsupported_requested),
    }


def _random_mode_reason(mode_info: Dict[str, Any]) -> str:
    requested = str(mode_info.get("requested") or "").strip().lower()
    if bool(mode_info.get("unsupported_requested")):
        return "unsupported_mode"
    if requested == "random":
        return "forced_random"
    return "warmup_or_feasibility_gate"



def _select_objectives(args: argparse.Namespace) -> List[str]:
    if args.objective:
        return [str(x).strip() for x in args.objective if str(x).strip()]
    return list(DEFAULT_OPTIMIZATION_OBJECTIVES)


def _compute_hv(
    Y_done_min: np.ndarray,
    G_done_min: np.ndarray,
    *,
    obj_names: Sequence[str],
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Compute HV in normalized objective space for feasible points."""
    if Y_done_min.size == 0:
        return None, {"hv": None}

    if G_done_min.size == 0:
        feas_mask = np.ones((Y_done_min.shape[0],), dtype=bool)
    else:
        feas_mask = np.all(G_done_min <= 0.0, axis=1)

    Yf = Y_done_min[feas_mask]
    if Yf.shape[0] < 2:
        return None, {"hv": None, "feasible_n": int(Yf.shape[0])}

    norm = fit_normalizer(Yf, method="quantile", q_low=0.05, q_high=0.95)
    Yfn = norm.transform(Yf)

    # reference point in normalized minimization space
    ref = infer_reference_point_min(Yfn, margin=0.10)
    hv = hypervolume_min(Yfn, ref)

    meta = {
        "feasible_n": int(Yf.shape[0]),
        "obj": list(obj_names),
        "ref": ref.tolist(),
        "normalizer": {"offset": norm.offset.tolist(), "scale": norm.scale.tolist()},
        "hv": float(hv),
    }
    return float(hv), meta


def _write_trial_artifact(run_dir: Path, trial: Dict[str, Any]) -> None:
    """Best-effort JSON dump for a trial."""
    try:
        out_dir = run_dir / "artifacts" / "trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        tid = str(trial.get("trial_id", "unknown"))
        (out_dir / f"{tid}.json").write_text(json.dumps(trial, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ------------------------------
# Ray backend
# ------------------------------


def _run_ray(
    args: argparse.Namespace,
    *,
    core_local: EvaluatorCore,
    db: ExperimentDB,
    run_id: str,
    run_dir: Path,
    problem_hash: str,
    objective_keys: List[str],
) -> None:
    try:
        import ray
    except Exception as e:
        raise RuntimeError("Ray is not installed. Install with: pip install ray[default]") from e

    base_dir = _PNEUMO_ROOT

    # ---- Ray init (+ optional runtime_env working_dir) ----
    runtime_env = None
    addr = str(args.ray_address).strip()

    # Decide whether to ship code via runtime_env
    use_runtime_env = False
    if args.ray_runtime_env == "on":
        use_runtime_env = True
    elif args.ray_runtime_env == "off":
        use_runtime_env = False
    else:
        # auto
        use_runtime_env = True if (addr and addr not in {"local", ""}) else False

    if use_runtime_env:
        # Working dir is pneumo_solver_ui (contains model/worker + package code)
        excludes = list(args.ray_runtime_exclude or [])
        # Reasonable defaults (can be overridden)
        if not excludes:
            excludes = [
                "runs/",
                "__pycache__/",
                "**/__pycache__/",
                "*.pyc",
                "*.pyo",
                "*.sqlite*",
                "*.duckdb*",
                "*.db",
                "*.zip",
            ]
        runtime_env = {"working_dir": str(base_dir), "excludes": excludes}
        extra_runtime_env = _parse_runtime_env_json(getattr(args, "ray_runtime_env_json", ""))
        if extra_runtime_env:
            merged_runtime_env = dict(extra_runtime_env)
            merged_runtime_env.setdefault("working_dir", str(base_dir))
            extra_excludes = merged_runtime_env.get("excludes")
            if isinstance(extra_excludes, list):
                merged: list[str] = []
                for item in list(extra_excludes) + list(excludes):
                    sval = str(item).strip()
                    if sval and sval not in merged:
                        merged.append(sval)
                merged_runtime_env["excludes"] = merged
            else:
                merged_runtime_env["excludes"] = list(excludes)
            runtime_env = merged_runtime_env

    def _ray_local_init_kwargs() -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"ignore_reinit_error": True}
        if runtime_env is not None:
            kwargs["runtime_env"] = runtime_env
        if int(getattr(args, "ray_local_num_cpus", 0) or 0) > 0:
            kwargs["num_cpus"] = int(args.ray_local_num_cpus)
        if bool(getattr(args, "ray_local_dashboard", False)):
            kwargs["include_dashboard"] = True
        if int(getattr(args, "ray_local_dashboard_port", 0) or 0) > 0:
            kwargs["dashboard_port"] = int(args.ray_local_dashboard_port)
        return kwargs

    try:
        if addr and addr not in {"auto", "local"}:
            ray.init(address=addr, runtime_env=runtime_env, ignore_reinit_error=True)
        elif addr == "local":
            ray.init(**_ray_local_init_kwargs())
        else:
            ray.init(address="auto", runtime_env=runtime_env, ignore_reinit_error=True)
    except Exception as e:
        print(f"[ray] Could not connect to cluster (addr={addr!r}): {e}")
        print("[ray] Falling back to local ray.init()")
        ray.init(**_ray_local_init_kwargs())

    cluster = ray.cluster_resources()
    _dump_json(run_dir / "ray_cluster_resources.json", cluster)

    # Determine worker counts
    n_cpus = int(cluster.get("CPU", 1))
    n_gpus = float(cluster.get("GPU", 0.0))
    n_eval = int(args.ray_num_evaluators) if int(args.ray_num_evaluators) > 0 else max(1, n_cpus)
    max_inflight = int(args.max_inflight) if int(args.max_inflight) > 0 else max(2, 2 * n_eval)

    # ---- Evaluator actors ----
    @ray.remote
    class EvaluatorActor:
        def __init__(
            self,
            actor_tag: str,
            *,
            model_path: str,
            worker_path: str,
            base_json: str,
            ranges_json: str,
            suite_json: str,
            cfg: Dict[str, Any],
            problem_hash: str,
        ):
            os.environ.setdefault("OMP_NUM_THREADS", "1")
            os.environ.setdefault("MKL_NUM_THREADS", "1")
            apply_problem_hash_env(problem_hash)
            self.actor_tag = actor_tag
            self.core = EvaluatorCore(
                model_path=model_path,
                worker_path=worker_path,
                base_json=base_json or None,
                ranges_json=ranges_json or None,
                suite_json=suite_json or None,
                cfg=cfg,
            )

        def evaluate(self, trial_id: str, x_u: List[float]):
            y, g, row = self.core.evaluate(trial_id=trial_id, x_u=x_u)
            row["ray_actor"] = self.actor_tag
            return y, g, row

    # We keep paths relative if possible (portable with runtime_env).
    model_p = str(Path(args.model))
    worker_p = str(Path(args.worker))
    base_json_p = str(Path(args.base_json)) if args.base_json else ""
    ranges_json_p = str(Path(args.ranges_json)) if args.ranges_json else ""
    suite_json_p = str(Path(args.suite_json)) if args.suite_json else ""

    # Evaluator config override: objective_keys / penalty settings
    cfg_override: Dict[str, Any] = {
        "objective_keys": tuple(objective_keys),
        "penalty_key": str(args.penalty_key),
        "penalty_tol": float(args.penalty_tol),
    }

    evaluators = [
        EvaluatorActor.options(num_cpus=float(args.ray_cpus_per_evaluator)).remote(
            f"eval_{i}",
            model_path=model_p,
            worker_path=worker_p,
            base_json=base_json_p,
            ranges_json=ranges_json_p,
            suite_json=suite_json_p,
            cfg=cfg_override,
            problem_hash=problem_hash,
        )
        for i in range(n_eval)
    ]

    # ---- (R59) Proposer actors (GPU pool) ----
    proposer_actors = []
    proposer_pool_requested = 0
    proposer_pool_disabled_reason: Optional[str] = None
    proposer_mode = str(getattr(args, "proposer", "auto") or "auto")
    use_pool = (proposer_mode in {"qnehvi", "auto", "portfolio"}) and (float(n_gpus) > 0.0)
    if use_pool:
        if int(args.ray_num_proposers) > 0:
            n_prop = int(args.ray_num_proposers)
        else:
            # auto: try to use all visible GPUs, but cap a bit
            n_prop = int(max(1, min(4, int(math.floor(float(n_gpus))))))
        proposer_pool_requested = int(n_prop)
        # Cap proposer actor count by available GPU budget.
        # This prevents oversubscription when user asks for more proposers than can run.
        gpp = float(getattr(args, "ray_gpus_per_proposer", 1.0) or 1.0)
        if gpp <= 0.0:
            gpp = 1.0
        max_prop_by_gpu = int(math.floor(float(n_gpus) / gpp))
        if max_prop_by_gpu <= 0:
            n_prop = 0
            proposer_pool_disabled_reason = "gpu_budget_insufficient"
        else:
            n_prop = int(max(1, min(int(n_prop), int(max_prop_by_gpu))))
            if int(n_prop) < int(proposer_pool_requested):
                proposer_pool_disabled_reason = "gpu_budget_capped"

        if n_prop > 0:
            @ray.remote
            class ProposerActor:
                def __init__(self, tag: str):
                    os.environ.setdefault("OMP_NUM_THREADS", "1")
                    os.environ.setdefault("MKL_NUM_THREADS", "1")
                    self.tag = tag
                    try:
                        import ray as _ray

                        self.gpu_ids = _ray.get_gpu_ids()
                    except Exception:
                        self.gpu_ids = []

                def propose(
                    self,
                    *,
                    X_done: np.ndarray,
                    Y_done: np.ndarray,
                    G_done: Optional[np.ndarray],
                    X_pending: Optional[np.ndarray],
                    q: int,
                    seed: int,
                    device: str,
                    normalize_objectives: bool = True,
                    ref_margin: float = 0.10,
                    num_restarts: int = 10,
                    raw_samples: int = 512,
                    maxiter: int = 200,
                ):
                    pr = propose_qnehvi(
                        X_done=X_done,
                        Y_min_done=Y_done,
                        G_min_done=G_done,
                        q=int(q),
                        seed=int(seed),
                        X_pending=X_pending,
                        device=device,
                        normalize_objectives=bool(normalize_objectives),
                        ref_margin=float(ref_margin),
                        num_restarts=int(num_restarts),
                        raw_samples=int(raw_samples),
                        maxiter=int(maxiter),
                    )
                    meta = dict(pr.meta)
                    meta["actor"] = self.tag
                    meta["gpu_ids"] = list(self.gpu_ids)
                    return pr.X, meta

            proposer_actors = [
                ProposerActor.options(num_gpus=float(args.ray_gpus_per_proposer)).remote(f"prop_{i}")
                for i in range(n_prop)
            ]
    proposer_pool_effective = int(len(proposer_actors))
    proposer_pool_enabled = bool(proposer_pool_effective > 0)
    if proposer_pool_enabled:
        proposer_pool_disabled_reason = None

    rng = np.random.default_rng(int(args.seed))

    # ---- Load existing DONE trials (resume support) ----
    X_done: List[List[float]] = []
    Y_done: List[List[float]] = []
    G_done: List[List[float]] = []
    counted_done_trial_ids: set[str] = set()

    done_rows = db.fetch_done_trials(run_id)
    for r in done_rows:
        if not isinstance(r.get("x_u"), list) or not isinstance(r.get("y"), list):
            continue
        X_done.append(list(r["x_u"]))
        Y_done.append(list(r["y"]))
        if isinstance(r.get("g"), list):
            G_done.append(list(r["g"]))
        tid = str(r.get("trial_id") or "").strip()
        if tid:
            counted_done_trial_ids.add(tid)

    done_success = len(X_done)
    budget = int(args.budget)
    dim = int(core_local.dim())
    stall_rescue_limit_cycles = max(8, 2 * max(1, dim))
    stall_rescue_count = 0
    stall_last_cycles = 0
    stall_terminated = False
    stagnation_cycles = 0
    dedup_skip_done_count = 0
    dedup_skip_running_count = 0
    dedup_skip_inflight_count = 0
    proposer_effective_mode_counts: Dict[str, int] = {}
    proposer_reason_counts: Dict[str, int] = {}
    portfolio_rand_q_last_base = 0
    portfolio_rand_q_last_effective = 0
    portfolio_rand_q_boost_events = 0
    portfolio_history: List[Dict[str, Any]] = []
    portfolio_primary_last_choice = "qnehvi"
    portfolio_primary_last_reason = "default_qnehvi"
    portfolio_primary_switches = 0
    portfolio_primary_switch_cooldown_span = 2
    portfolio_primary_cooldown_ticks = 0
    portfolio_primary_cooldown_holds = 0
    portfolio_primary_choice_counts: Dict[str, int] = {"qnehvi": 0, "heuristic": 0}
    base_heuristic_buffer = int(max(0, int(getattr(args, "proposer_buffer", 0) or 0)))
    heuristic_buffer_last_effective = int(base_heuristic_buffer)
    heuristic_buffer_boost_events = 0
    base_heuristic_q = _coerce_positive_int(getattr(args, "q", 1), default=1)
    heuristic_q_last_effective = int(base_heuristic_q)
    heuristic_q_boost_events = 0
    base_heuristic_pool_size = _coerce_positive_int(
        getattr(args, "heuristic_pool_size", DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
        default=int(DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
    )
    heuristic_pool_size_last_effective = int(base_heuristic_pool_size)
    heuristic_pool_size_boost_events = 0
    base_heuristic_explore = _clamp_unit_interval(
        getattr(args, "heuristic_explore", DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
        default=float(DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
    )
    heuristic_explore_last_effective = float(base_heuristic_explore)
    heuristic_explore_boost_events = 0
    seed_vectors, seed_meta = _load_seed_vectors(core_local, getattr(args, "seed_json", ""))
    _dump_json(run_dir / "seed_info.json", dict(seed_meta))
    seed_queue = [] if bool(args.resume) else list(seed_vectors)

    # Resume: requeue stale and pick up pending from DB
    if args.resume:
        n_re = db.requeue_stale(run_id, ttl_sec=float(args.stale_ttl_sec))
        if n_re:
            print(f"[RESUME] requeued stale RUNNING trials: {n_re}")

    pending_rows = db.fetch_trials(run_id, status="PENDING") if args.resume else []

    # ---- Run metadata ----
    run_spec_path = run_dir / "run_spec.json"
    run_spec_payload: Dict[str, Any] = {
        "run_id": run_id,
        "backend": "ray",
        "dim": int(dim),
        "objective_keys": list(objective_keys),
        "penalty_key": str(args.penalty_key),
        "penalty_tol": float(args.penalty_tol),
        "seed": int(args.seed),
        "max_inflight": int(max_inflight),
        "proposer": proposer_mode,
        "q": int(getattr(args, "q", 1) or 1),
        "n_init": int(args.n_init),
        "min_feasible": _coerce_nonnegative_int(
            getattr(args, "min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
            default=int(DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
        ),
        "heuristic_buffer_base": int(base_heuristic_buffer),
        "heuristic_buffer_last_effective": int(heuristic_buffer_last_effective),
        "heuristic_buffer_boost_events": int(heuristic_buffer_boost_events),
        "heuristic_q_base": int(base_heuristic_q),
        "heuristic_q_last_effective": int(heuristic_q_last_effective),
        "heuristic_q_boost_events": int(heuristic_q_boost_events),
        "heuristic_pool_size": int(getattr(args, "heuristic_pool_size", DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT) or DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
        "heuristic_pool_size_base": int(base_heuristic_pool_size),
        "heuristic_pool_size_last_effective": int(heuristic_pool_size_last_effective),
        "heuristic_pool_size_boost_events": int(heuristic_pool_size_boost_events),
        "heuristic_explore": float(getattr(args, "heuristic_explore", DIST_OPT_HEURISTIC_EXPLORE_DEFAULT) or DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
        "heuristic_explore_base": float(base_heuristic_explore),
        "heuristic_explore_last_effective": float(heuristic_explore_last_effective),
        "heuristic_explore_boost_events": int(heuristic_explore_boost_events),
        "portfolio_rand_q_last_base": int(portfolio_rand_q_last_base),
        "portfolio_rand_q_last_effective": int(portfolio_rand_q_last_effective),
        "portfolio_rand_q_boost_events": int(portfolio_rand_q_boost_events),
        "portfolio_primary_last_choice": str(portfolio_primary_last_choice),
        "portfolio_primary_last_reason": str(portfolio_primary_last_reason),
        "portfolio_primary_switches": int(portfolio_primary_switches),
        "portfolio_primary_switch_cooldown_span": int(portfolio_primary_switch_cooldown_span),
        "portfolio_primary_cooldown_ticks": int(portfolio_primary_cooldown_ticks),
        "portfolio_primary_cooldown_holds": int(portfolio_primary_cooldown_holds),
        "portfolio_primary_choice_counts": dict(portfolio_primary_choice_counts),
        "portfolio_history_size": int(len(portfolio_history)),
        "ray_address": addr,
        "ray_runtime_env": runtime_env,
        "ray_cluster_resources": cluster,
        "ray_num_evaluators": int(n_eval),
        "ray_num_proposers": int(proposer_pool_effective),
        "ray_num_proposers_requested": int(proposer_pool_requested),
        "ray_proposer_pool_enabled": bool(proposer_pool_enabled),
        "ray_proposer_pool_disabled_reason": proposer_pool_disabled_reason,
        "seed_json": str(seed_meta.get("seed_json") or ""),
        "seed_loaded": int(seed_meta.get("loaded") or 0),
        "seed_invalid": int(seed_meta.get("invalid") or 0),
        "seed_duplicates": int(seed_meta.get("duplicates") or 0),
        "stall_rescue_limit_cycles": int(stall_rescue_limit_cycles),
        "stall_rescue_count": int(stall_rescue_count),
        "stall_last_cycles": int(stall_last_cycles),
        "stall_terminated": bool(stall_terminated),
        "dedup_skip_done_count": int(dedup_skip_done_count),
        "dedup_skip_running_count": int(dedup_skip_running_count),
        "dedup_skip_inflight_count": int(dedup_skip_inflight_count),
        "dedup_skip_total": int(dedup_skip_done_count + dedup_skip_running_count + dedup_skip_inflight_count),
        "proposer_effective_mode_counts": dict(proposer_effective_mode_counts),
        "proposer_reason_counts": dict(proposer_reason_counts),
        "proposer_meta_events": int(sum(int(v) for v in proposer_effective_mode_counts.values())),
    }
    _dump_json(run_spec_path, run_spec_payload)

    print(
        f"[RAY] run_id={run_id} dim={core_local.dim()} budget={budget} done={done_success} "
        f"max_inflight={max_inflight} evaluators={n_eval} proposers={len(proposer_actors)}"
    )

    # ---- Candidate buffer ----
    candidate_buf: List[List[float]] = []
    candidate_buf.extend(list(x_u) for x_u in seed_queue)

    # Seed LHS warmup for a new run
    auto_n_init = max(8, 2 * (dim + 1))
    lhs_target = max(auto_n_init, int(getattr(args, "n_init", 0) or 0))
    lhs_pool_n = max(0, int(lhs_target - done_success - len(seed_queue)))
    lhs_pool = sample_lhs(n=int(lhs_pool_n), d=dim, seed=int(args.seed))
    lhs_i = 0
    if args.resume:
        lhs_i = lhs_pool.shape[0]

    # Add pending from DB first (resume)
    for pr in pending_rows:
        if isinstance(pr.get("x_u"), list) and isinstance(pr.get("trial_id"), str):
            candidate_buf.append(list(pr["x_u"]))

    def _sync_run_spec_stall() -> None:
        run_spec_payload["stall_rescue_count"] = int(stall_rescue_count)
        run_spec_payload["stall_last_cycles"] = int(stall_last_cycles)
        run_spec_payload["stall_terminated"] = bool(stall_terminated)
        run_spec_payload["dedup_skip_done_count"] = int(dedup_skip_done_count)
        run_spec_payload["dedup_skip_running_count"] = int(dedup_skip_running_count)
        run_spec_payload["dedup_skip_inflight_count"] = int(dedup_skip_inflight_count)
        run_spec_payload["dedup_skip_total"] = int(
            dedup_skip_done_count + dedup_skip_running_count + dedup_skip_inflight_count
        )
        run_spec_payload["proposer_effective_mode_counts"] = dict(proposer_effective_mode_counts)
        run_spec_payload["proposer_reason_counts"] = dict(proposer_reason_counts)
        run_spec_payload["proposer_meta_events"] = int(
            sum(int(v) for v in proposer_effective_mode_counts.values())
        )
        run_spec_payload["heuristic_buffer_base"] = int(base_heuristic_buffer)
        run_spec_payload["heuristic_buffer_last_effective"] = int(heuristic_buffer_last_effective)
        run_spec_payload["heuristic_buffer_boost_events"] = int(heuristic_buffer_boost_events)
        run_spec_payload["heuristic_q_base"] = int(base_heuristic_q)
        run_spec_payload["heuristic_q_last_effective"] = int(heuristic_q_last_effective)
        run_spec_payload["heuristic_q_boost_events"] = int(heuristic_q_boost_events)
        run_spec_payload["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
        run_spec_payload["heuristic_pool_size_last_effective"] = int(heuristic_pool_size_last_effective)
        run_spec_payload["heuristic_pool_size_boost_events"] = int(heuristic_pool_size_boost_events)
        run_spec_payload["heuristic_explore_base"] = float(base_heuristic_explore)
        run_spec_payload["heuristic_explore_last_effective"] = float(heuristic_explore_last_effective)
        run_spec_payload["heuristic_explore_boost_events"] = int(heuristic_explore_boost_events)
        run_spec_payload["portfolio_rand_q_last_base"] = int(portfolio_rand_q_last_base)
        run_spec_payload["portfolio_rand_q_last_effective"] = int(portfolio_rand_q_last_effective)
        run_spec_payload["portfolio_rand_q_boost_events"] = int(portfolio_rand_q_boost_events)
        run_spec_payload["portfolio_primary_last_choice"] = str(portfolio_primary_last_choice)
        run_spec_payload["portfolio_primary_last_reason"] = str(portfolio_primary_last_reason)
        run_spec_payload["portfolio_primary_switches"] = int(portfolio_primary_switches)
        run_spec_payload["portfolio_primary_switch_cooldown_span"] = int(portfolio_primary_switch_cooldown_span)
        run_spec_payload["portfolio_primary_cooldown_ticks"] = int(portfolio_primary_cooldown_ticks)
        run_spec_payload["portfolio_primary_cooldown_holds"] = int(portfolio_primary_cooldown_holds)
        run_spec_payload["portfolio_primary_choice_counts"] = dict(portfolio_primary_choice_counts)
        run_spec_payload["portfolio_history_size"] = int(len(portfolio_history))
        _dump_json(run_spec_path, run_spec_payload)
        _sync_last_proposer_meta_diag()

    last_meta_path = run_dir / "last_proposer_meta.json"
    last_proposer_meta: Dict[str, Any] = {}

    def _sync_last_proposer_meta_diag() -> None:
        diag_nonzero = bool(
            (stall_rescue_count > 0)
            or (stall_last_cycles > 0)
            or bool(stall_terminated)
            or (dedup_skip_done_count > 0)
            or (dedup_skip_running_count > 0)
            or (dedup_skip_inflight_count > 0)
        )
        payload = dict(last_proposer_meta or {})
        if not payload and last_meta_path.exists():
            try:
                loaded = json.loads(last_meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = dict(loaded)
            except Exception:
                payload = {}
        if not payload and not diag_nonzero:
            return
        if not payload:
            payload = {
                "requested_mode": str(getattr(args, "proposer", "") or ""),
                "effective_mode": "random",
                "reason": "runtime_diagnostics_sync",
            }
        payload["stall_rescue_limit_cycles"] = int(stall_rescue_limit_cycles)
        payload["stall_rescue_count"] = int(stall_rescue_count)
        payload["stall_stagnation_cycles"] = int(stagnation_cycles)
        payload["stall_terminated"] = bool(stall_terminated)
        payload["dedup_skip_done_count"] = int(dedup_skip_done_count)
        payload["dedup_skip_running_count"] = int(dedup_skip_running_count)
        payload["dedup_skip_inflight_count"] = int(dedup_skip_inflight_count)
        payload["dedup_skip_total"] = int(
            dedup_skip_done_count + dedup_skip_running_count + dedup_skip_inflight_count
        )
        payload["heuristic_buffer_base"] = int(base_heuristic_buffer)
        payload["heuristic_buffer_last_effective"] = int(heuristic_buffer_last_effective)
        payload["heuristic_buffer_boost_events"] = int(heuristic_buffer_boost_events)
        payload["heuristic_q_base"] = int(base_heuristic_q)
        payload["heuristic_q_last_effective"] = int(heuristic_q_last_effective)
        payload["heuristic_q_boost_events"] = int(heuristic_q_boost_events)
        payload["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
        payload["heuristic_pool_size_last_effective"] = int(heuristic_pool_size_last_effective)
        payload["heuristic_pool_size_boost_events"] = int(heuristic_pool_size_boost_events)
        payload["heuristic_explore_base"] = float(base_heuristic_explore)
        payload["heuristic_explore_last_effective"] = float(heuristic_explore_last_effective)
        payload["heuristic_explore_boost_events"] = int(heuristic_explore_boost_events)
        payload["portfolio_rand_q_last_base"] = int(portfolio_rand_q_last_base)
        payload["portfolio_rand_q_last_effective"] = int(portfolio_rand_q_last_effective)
        payload["portfolio_rand_q_boost_events"] = int(portfolio_rand_q_boost_events)
        payload["portfolio_primary_last_choice"] = str(portfolio_primary_last_choice)
        payload["portfolio_primary_last_reason"] = str(portfolio_primary_last_reason)
        payload["portfolio_primary_switches"] = int(portfolio_primary_switches)
        payload["portfolio_primary_switch_cooldown_span"] = int(portfolio_primary_switch_cooldown_span)
        payload["portfolio_primary_cooldown_ticks"] = int(portfolio_primary_cooldown_ticks)
        payload["portfolio_primary_cooldown_holds"] = int(portfolio_primary_cooldown_holds)
        payload["portfolio_primary_choice_counts"] = dict(portfolio_primary_choice_counts)
        payload["portfolio_history_size"] = int(len(portfolio_history))
        _write_text(last_meta_path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _write_last_proposer_meta(meta_out: Dict[str, Any]) -> None:
        nonlocal last_proposer_meta
        last_proposer_meta = dict(meta_out or {})
        mode_key = str(last_proposer_meta.get("effective_mode") or "").strip().lower()
        if mode_key:
            proposer_effective_mode_counts[mode_key] = int(proposer_effective_mode_counts.get(mode_key, 0) + 1)
        reason_key = str(
            last_proposer_meta.get("reason")
            or last_proposer_meta.get("fallback_reason")
            or ""
        ).strip().lower()
        if reason_key:
            proposer_reason_counts[reason_key] = int(proposer_reason_counts.get(reason_key, 0) + 1)
        _sync_last_proposer_meta_diag()

    # Helper: fill buffer using proposers / local
    def fill_buffer():
        nonlocal lhs_i, heuristic_explore_last_effective, heuristic_explore_boost_events
        nonlocal heuristic_buffer_last_effective, heuristic_buffer_boost_events
        nonlocal heuristic_q_last_effective, heuristic_q_boost_events
        nonlocal heuristic_pool_size_last_effective, heuristic_pool_size_boost_events
        nonlocal portfolio_rand_q_last_base, portfolio_rand_q_last_effective, portfolio_rand_q_boost_events
        nonlocal portfolio_primary_last_choice, portfolio_primary_last_reason, portfolio_primary_switches
        nonlocal portfolio_primary_cooldown_ticks, portfolio_primary_cooldown_holds
        target = int(max(0, args.proposer_buffer))
        if len(candidate_buf) >= target:
            return

        # Warmup LHS first
        while lhs_i < lhs_pool.shape[0] and len(candidate_buf) < target:
            candidate_buf.append(lhs_pool[lhs_i].tolist())
            lhs_i += 1

        if len(candidate_buf) >= target:
            return

        # Pending points for acquisition
        X_pending = None
        if inflight:
            X_pending = np.asarray([meta["x_u"] for meta in inflight.values()], dtype=float)

        feasible_n = _count_feasible_trials(G_done) if G_done else len(X_done)
        mode_info = resolve_proposer_mode(
            args,
            done_n=len(X_done),
            feasible_n=feasible_n,
            dim=dim,
        )
        prop_mode = str(mode_info["mode"])
        want_portfolio = bool(mode_info["portfolio_enabled"])
        pool_fallback_error: Optional[str] = None

        def _next_heuristic_explore() -> float:
            nonlocal heuristic_explore_last_effective, heuristic_explore_boost_events
            effective = _adaptive_heuristic_explore_weight(
                base_heuristic_explore,
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_explore_last_effective = float(effective)
            if effective > (base_heuristic_explore + 1e-12):
                heuristic_explore_boost_events += 1
            return float(effective)

        def _next_heuristic_pool_size() -> int:
            nonlocal heuristic_pool_size_last_effective, heuristic_pool_size_boost_events
            effective = _adaptive_heuristic_pool_size(
                base_heuristic_pool_size,
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_pool_size_last_effective = int(effective)
            if int(effective) > int(base_heuristic_pool_size):
                heuristic_pool_size_boost_events += 1
            return int(effective)

        def _next_heuristic_q(*, need: int) -> int:
            nonlocal heuristic_q_last_effective, heuristic_q_boost_events
            effective = _adaptive_heuristic_q(
                base_heuristic_q,
                need=int(need),
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_q_last_effective = int(effective)
            if int(effective) > int(base_heuristic_q):
                heuristic_q_boost_events += 1
            return int(effective)

        def _next_heuristic_buffer() -> int:
            nonlocal heuristic_buffer_last_effective, heuristic_buffer_boost_events
            if int(base_heuristic_buffer) <= 0:
                heuristic_buffer_last_effective = 0
                return 0
            effective = _adaptive_heuristic_buffer_target(
                int(max(1, base_heuristic_buffer)),
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_buffer_last_effective = int(effective)
            if int(effective) > int(base_heuristic_buffer):
                heuristic_buffer_boost_events += 1
            return int(effective)

        def _next_portfolio_rand_q(*, need: int) -> int:
            nonlocal portfolio_rand_q_last_base, portfolio_rand_q_last_effective, portfolio_rand_q_boost_events
            base_q, effective_q = _adaptive_portfolio_rand_q(
                int(need),
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            portfolio_rand_q_last_base = int(base_q)
            portfolio_rand_q_last_effective = int(effective_q)
            if int(effective_q) > int(base_q):
                portfolio_rand_q_boost_events += 1
            return int(effective_q)

        def _record_portfolio_event(*, mode: str, success: bool) -> None:
            _portfolio_record_event(
                portfolio_history,
                mode=str(mode),
                success=bool(success),
                maxlen=12,
            )

        def _resolve_portfolio_primary() -> Tuple[str, str]:
            nonlocal portfolio_primary_last_choice, portfolio_primary_last_reason, portfolio_primary_switches
            nonlocal portfolio_primary_cooldown_ticks, portfolio_primary_cooldown_holds
            primary, reason, _stats = _portfolio_choose_primary_mode(
                portfolio_history,
                lookback=8,
                min_attempts_per_mode=3,
                min_success_gap=0.20,
                previous_choice=portfolio_primary_last_choice,
                switch_cooldown_ticks=int(portfolio_primary_cooldown_ticks),
            )
            primary_key = str(primary or "qnehvi").strip().lower()
            if primary_key not in {"qnehvi", "heuristic"}:
                primary_key = "qnehvi"
            prev_key = str(portfolio_primary_last_choice or "qnehvi").strip().lower()
            portfolio_primary_last_choice = str(primary_key)
            portfolio_primary_last_reason = str(reason or "default_qnehvi")
            if prev_key != primary_key:
                portfolio_primary_switches += 1
                portfolio_primary_cooldown_ticks = int(max(0, int(portfolio_primary_switch_cooldown_span)))
            elif int(portfolio_primary_cooldown_ticks) > 0:
                portfolio_primary_cooldown_ticks = int(portfolio_primary_cooldown_ticks) - 1
            if str(portfolio_primary_last_reason).strip().lower() == "cooldown_hold":
                portfolio_primary_cooldown_holds += 1
            portfolio_primary_choice_counts[primary_key] = int(portfolio_primary_choice_counts.get(primary_key, 0) + 1)
            return str(primary_key), str(portfolio_primary_last_reason)

        portfolio_primary = "qnehvi"
        portfolio_primary_reason = "not_portfolio"
        if want_portfolio:
            portfolio_primary, portfolio_primary_reason = _resolve_portfolio_primary()

        # If we have GPU proposer pool and mode includes qNEHVI, ask actors
        if proposer_actors and (prop_mode in {"qnehvi"} or (want_portfolio and portfolio_primary == "qnehvi")):
            need = max(1, target - len(candidate_buf))
            per_actor = int(max(1, math.ceil(need / max(1, len(proposer_actors)))))

            Xd = np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float)
            Yd = np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float)
            Gd = np.asarray(G_done, dtype=float) if G_done else None

            actor_futures: List[Tuple[Any, Any]] = []
            for i, pa in enumerate(proposer_actors):
                seed_i = int(rng.integers(0, 2**31 - 1))
                actor_futures.append(
                    (
                        pa,
                        pa.propose.remote(
                            X_done=Xd,
                            Y_done=Yd,
                            G_done=Gd,
                            X_pending=X_pending,
                            q=per_actor,
                            seed=seed_i,
                            device=str(args.device),
                            normalize_objectives=not bool(getattr(args, "botorch_no_normalize_objectives", False)),
                            ref_margin=float(getattr(args, "botorch_ref_margin", 0.10)),
                            num_restarts=int(getattr(args, "botorch_num_restarts", 10)),
                            raw_samples=int(getattr(args, "botorch_raw_samples", 512)),
                            maxiter=int(getattr(args, "botorch_maxiter", 200)),
                        ),
                    )
                )
            results: List[Tuple[np.ndarray, Any]] = []
            pool_errors: List[str] = []
            alive_actors: List[Any] = []
            for pa, fut in actor_futures:
                try:
                    got = ray.get(fut)
                    if not (isinstance(got, (tuple, list)) and len(got) == 2):
                        raise ValueError("invalid proposer pool result")
                    X_new = np.asarray(got[0], dtype=float)
                    results.append((X_new, got[1]))
                    alive_actors.append(pa)
                except Exception as pool_exc:
                    pool_errors.append(f"{type(pool_exc).__name__}: {pool_exc}")
            if pool_errors:
                # Degrade gracefully: drop failing actors; if none left, continue with local fallback.
                proposer_actors[:] = list(alive_actors)
                if len(pool_errors) == 1:
                    pool_fallback_error = pool_errors[0]
                else:
                    pool_fallback_error = f"{pool_errors[0]} (+{len(pool_errors) - 1} more)"
            pool_added = False
            for X_new, meta in results:
                for x_u in X_new.tolist():
                    candidate_buf.append(list(x_u))
                    pool_added = True
                meta_out = dict(meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = mode_info["mode"]
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                if want_portfolio:
                    meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                    meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                _write_last_proposer_meta(meta_out)
            if want_portfolio:
                if pool_added:
                    _record_portfolio_event(mode="qnehvi", success=True)
                elif pool_fallback_error:
                    _record_portfolio_event(mode="qnehvi", success=False)

            # Portfolio blend is added when we obtained at least one pool proposal.
            if want_portfolio and pool_added:
                n_rand = _next_portfolio_rand_q(need=need)
                Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                for x_u in Xr.tolist():
                    candidate_buf.append(list(x_u))

            if candidate_buf and (pool_added or not pool_fallback_error):
                return

        # No proposer pool (or random): run locally
        need = max(1, target - len(candidate_buf))
        if prop_mode in {"qnehvi", "portfolio"} and want_portfolio and portfolio_primary == "heuristic":
            try:
                heuristic_buffer_effective = _next_heuristic_buffer()
                heuristic_need = int(max(1, heuristic_buffer_effective - len(candidate_buf)))
                heuristic_q_effective = _next_heuristic_q(need=heuristic_need)
                heuristic_explore_effective = _next_heuristic_explore()
                heuristic_pool_size_effective = _next_heuristic_pool_size()
                pr = propose_heuristic(
                    X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                    Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                    penalty=_heuristic_penalty_from_constraints(G_done),
                    q=int(heuristic_q_effective),
                    seed=int(rng.integers(0, 2**31 - 1)),
                    X_pending=X_pending,
                    feasible_tol=float(args.penalty_tol),
                    pool_size=int(heuristic_pool_size_effective),
                    explore_weight=float(heuristic_explore_effective),
                )
                meta_out = dict(pr.meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = "heuristic"
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                meta_out["heuristic_buffer_base"] = int(base_heuristic_buffer)
                meta_out["heuristic_buffer_effective"] = int(heuristic_buffer_effective)
                meta_out["heuristic_q_base"] = int(base_heuristic_q)
                meta_out["heuristic_q_effective"] = int(heuristic_q_effective)
                meta_out["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
                meta_out["heuristic_pool_size_effective"] = int(heuristic_pool_size_effective)
                meta_out["heuristic_explore_base"] = float(base_heuristic_explore)
                meta_out["heuristic_explore_effective"] = float(heuristic_explore_effective)
                meta_out["heuristic_explore_stagnation_cycles"] = int(stagnation_cycles)
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                for x_u in pr.X.tolist():
                    candidate_buf.append(list(x_u))
                _record_portfolio_event(mode="heuristic", success=True)
                _write_last_proposer_meta(meta_out)
                n_rand = _next_portfolio_rand_q(need=need)
                Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                for x_u in Xr.tolist():
                    candidate_buf.append(list(x_u))
                return
            except Exception as h_exc:
                _record_portfolio_event(mode="heuristic", success=False)
                try:
                    pr = propose_qnehvi(
                        X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                        Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                        G_min_done=np.asarray(G_done, dtype=float) if G_done else None,
                        q=int(need),
                        seed=int(rng.integers(0, 2**31 - 1)),
                        X_pending=X_pending,
                        device=str(args.device),
                        normalize_objectives=not bool(getattr(args, "botorch_no_normalize_objectives", False)),
                        ref_margin=float(getattr(args, "botorch_ref_margin", 0.10)),
                        num_restarts=int(getattr(args, "botorch_num_restarts", 10)),
                        raw_samples=int(getattr(args, "botorch_raw_samples", 512)),
                        maxiter=int(getattr(args, "botorch_maxiter", 200)),
                    )
                    meta_out = dict(pr.meta or {})
                    meta_out["requested_mode"] = mode_info["requested"]
                    meta_out["effective_mode"] = "qnehvi"
                    meta_out["n_init"] = mode_info["n_init"]
                    meta_out["min_feasible"] = mode_info["min_feasible"]
                    meta_out["ready_by_done"] = mode_info["ready_by_done"]
                    meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                    meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                    meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                    meta_out["fallback_reason"] = "heuristic_primary_failed"
                    meta_out["fallback_error"] = f"{type(h_exc).__name__}: {h_exc}"
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    for x_u in pr.X.tolist():
                        candidate_buf.append(list(x_u))
                    _record_portfolio_event(mode="qnehvi", success=True)
                    _write_last_proposer_meta(meta_out)
                    n_rand = _next_portfolio_rand_q(need=need)
                    Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                    return
                except Exception as q_exc:
                    _record_portfolio_event(mode="qnehvi", success=False)
                    meta_out = {
                        "requested_mode": mode_info["requested"],
                        "effective_mode": "random",
                        "n_init": mode_info["n_init"],
                        "min_feasible": mode_info["min_feasible"],
                        "ready_by_done": mode_info["ready_by_done"],
                        "ready_by_feasible": mode_info["ready_by_feasible"],
                        "portfolio_primary_choice": str(portfolio_primary),
                        "portfolio_preference_reason": str(portfolio_primary_reason),
                        "reason": "heuristic_and_qnehvi_failed",
                        "fallback_error": f"{type(h_exc).__name__}: {h_exc}; {type(q_exc).__name__}: {q_exc}",
                    }
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    _write_last_proposer_meta(meta_out)
                    Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                    n_rand = _next_portfolio_rand_q(need=need)
                    Xr2 = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr2.tolist():
                        candidate_buf.append(list(x_u))
                    return
        if prop_mode in {"qnehvi", "portfolio"}:
            try:
                pr = propose_qnehvi(
                    X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                    Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                    G_min_done=np.asarray(G_done, dtype=float) if G_done else None,
                    q=int(need),
                    seed=int(rng.integers(0, 2**31 - 1)),
                    X_pending=X_pending,
                    device=str(args.device),
                    normalize_objectives=not bool(getattr(args, "botorch_no_normalize_objectives", False)),
                    ref_margin=float(getattr(args, "botorch_ref_margin", 0.10)),
                    num_restarts=int(getattr(args, "botorch_num_restarts", 10)),
                    raw_samples=int(getattr(args, "botorch_raw_samples", 512)),
                    maxiter=int(getattr(args, "botorch_maxiter", 200)),
                )
                meta_out = dict(pr.meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = mode_info["mode"]
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                if want_portfolio:
                    meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                    meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                for x_u in pr.X.tolist():
                    candidate_buf.append(list(x_u))
                if want_portfolio:
                    _record_portfolio_event(mode="qnehvi", success=True)
                _write_last_proposer_meta(meta_out)
                if want_portfolio:
                    n_rand = _next_portfolio_rand_q(need=need)
                    Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                return
            except Exception as q_exc:
                if want_portfolio:
                    _record_portfolio_event(mode="qnehvi", success=False)
                try:
                    heuristic_buffer_effective = _next_heuristic_buffer()
                    heuristic_need = int(max(1, heuristic_buffer_effective - len(candidate_buf)))
                    heuristic_q_effective = _next_heuristic_q(need=heuristic_need)
                    heuristic_explore_effective = _next_heuristic_explore()
                    heuristic_pool_size_effective = _next_heuristic_pool_size()
                    pr = propose_heuristic(
                        X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                        Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                        penalty=_heuristic_penalty_from_constraints(G_done),
                        q=int(heuristic_q_effective),
                        seed=int(rng.integers(0, 2**31 - 1)),
                        X_pending=X_pending,
                        feasible_tol=float(args.penalty_tol),
                        pool_size=int(heuristic_pool_size_effective),
                        explore_weight=float(heuristic_explore_effective),
                    )
                    meta_out = dict(pr.meta or {})
                    meta_out["requested_mode"] = mode_info["requested"]
                    meta_out["effective_mode"] = "heuristic"
                    meta_out["n_init"] = mode_info["n_init"]
                    meta_out["min_feasible"] = mode_info["min_feasible"]
                    meta_out["ready_by_done"] = mode_info["ready_by_done"]
                    meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                    meta_out["fallback_reason"] = "qnehvi_failed"
                    meta_out["fallback_error"] = f"{type(q_exc).__name__}: {q_exc}"
                    if want_portfolio:
                        meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                        meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                    meta_out["heuristic_buffer_base"] = int(base_heuristic_buffer)
                    meta_out["heuristic_buffer_effective"] = int(heuristic_buffer_effective)
                    meta_out["heuristic_q_base"] = int(base_heuristic_q)
                    meta_out["heuristic_q_effective"] = int(heuristic_q_effective)
                    meta_out["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
                    meta_out["heuristic_pool_size_effective"] = int(heuristic_pool_size_effective)
                    meta_out["heuristic_explore_base"] = float(base_heuristic_explore)
                    meta_out["heuristic_explore_effective"] = float(heuristic_explore_effective)
                    meta_out["heuristic_explore_stagnation_cycles"] = int(stagnation_cycles)
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    for x_u in pr.X.tolist():
                        candidate_buf.append(list(x_u))
                    if want_portfolio:
                        _record_portfolio_event(mode="heuristic", success=True)
                    _write_last_proposer_meta(meta_out)
                    if want_portfolio:
                        n_rand = _next_portfolio_rand_q(need=need)
                        Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                        for x_u in Xr.tolist():
                            candidate_buf.append(list(x_u))
                    return
                except Exception as h_exc:
                    if want_portfolio:
                        _record_portfolio_event(mode="heuristic", success=False)
                    meta_out = {
                        "requested_mode": mode_info["requested"],
                        "effective_mode": "random",
                        "n_init": mode_info["n_init"],
                        "min_feasible": mode_info["min_feasible"],
                        "ready_by_done": mode_info["ready_by_done"],
                        "ready_by_feasible": mode_info["ready_by_feasible"],
                        "reason": "qnehvi_and_heuristic_failed",
                        "fallback_error": f"{type(q_exc).__name__}: {q_exc}; {type(h_exc).__name__}: {h_exc}",
                    }
                    if want_portfolio:
                        meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                        meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    _write_last_proposer_meta(meta_out)
                    Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                    if want_portfolio:
                        n_rand = _next_portfolio_rand_q(need=need)
                        Xr2 = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                        for x_u in Xr2.tolist():
                            candidate_buf.append(list(x_u))
                    return
        if prop_mode == "heuristic":
            try:
                heuristic_buffer_effective = _next_heuristic_buffer()
                heuristic_need = int(max(1, heuristic_buffer_effective - len(candidate_buf)))
                heuristic_q_effective = _next_heuristic_q(need=heuristic_need)
                heuristic_explore_effective = _next_heuristic_explore()
                heuristic_pool_size_effective = _next_heuristic_pool_size()
                pr = propose_heuristic(
                    X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                    Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                    penalty=_heuristic_penalty_from_constraints(G_done),
                    q=int(heuristic_q_effective),
                    seed=int(rng.integers(0, 2**31 - 1)),
                    X_pending=X_pending,
                    feasible_tol=float(args.penalty_tol),
                    pool_size=int(heuristic_pool_size_effective),
                    explore_weight=float(heuristic_explore_effective),
                )
                meta_out = dict(pr.meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = mode_info["mode"]
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                meta_out["heuristic_buffer_base"] = int(base_heuristic_buffer)
                meta_out["heuristic_buffer_effective"] = int(heuristic_buffer_effective)
                meta_out["heuristic_q_base"] = int(base_heuristic_q)
                meta_out["heuristic_q_effective"] = int(heuristic_q_effective)
                meta_out["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
                meta_out["heuristic_pool_size_effective"] = int(heuristic_pool_size_effective)
                meta_out["heuristic_explore_base"] = float(base_heuristic_explore)
                meta_out["heuristic_explore_effective"] = float(heuristic_explore_effective)
                meta_out["heuristic_explore_stagnation_cycles"] = int(stagnation_cycles)
                for x_u in pr.X.tolist():
                    candidate_buf.append(list(x_u))
                _write_last_proposer_meta(meta_out)
                return
            except Exception as h_exc:
                meta_out = {
                    "requested_mode": mode_info["requested"],
                    "effective_mode": "random",
                    "n_init": mode_info["n_init"],
                    "min_feasible": mode_info["min_feasible"],
                    "ready_by_done": mode_info["ready_by_done"],
                    "ready_by_feasible": mode_info["ready_by_feasible"],
                    "reason": "heuristic_failed",
                    "fallback_error": f"{type(h_exc).__name__}: {h_exc}",
                }
                _write_last_proposer_meta(meta_out)
                Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
                for x_u in Xr.tolist():
                    candidate_buf.append(list(x_u))
                return

        # random fallback
        random_reason = _random_mode_reason(mode_info)
        meta_out = {
            "requested_mode": mode_info["requested"],
            "effective_mode": prop_mode,
            "n_init": mode_info["n_init"],
            "min_feasible": mode_info["min_feasible"],
            "ready_by_done": mode_info["ready_by_done"],
            "ready_by_feasible": mode_info["ready_by_feasible"],
            "reason": random_reason,
        }
        _write_last_proposer_meta(meta_out)
        Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
        for x_u in Xr.tolist():
            candidate_buf.append(list(x_u))

    # ---- Inflight tracking ----
    inflight: Dict[Any, Dict[str, Any]] = {}
    next_eval = 0
    last_export_done = done_success

    def _trial_is_inflight(trial_id: str) -> bool:
        tid = str(trial_id or "").strip()
        if not tid:
            return False
        for meta in inflight.values():
            if str(meta.get("trial_id") or "").strip() == tid:
                return True
        return False

    if args.hv_log:
        hv_csv = run_dir / "progress_hv.csv"
        if not hv_csv.exists():
            hv_csv.write_text("ts,done_success,hv\n", encoding="utf-8")

    def maybe_export():
        nonlocal last_export_done
        if int(args.export_every) <= 0:
            return
        if (done_success - last_export_done) >= int(args.export_every):
            out_dir = run_dir / "export"
            db.export_run_to_csv(run_id, out_dir=str(out_dir))
            last_export_done = done_success

    # ---- Main loop ----
    while done_success < budget:
        done_before_cycle = int(done_success)
        # Keep DB heartbeat for long-running trials
        if inflight:
            for meta in list(inflight.values()):
                try:
                    db.heartbeat(meta["trial_id"])
                except Exception:
                    pass

        # Fill inflight
        fill_buffer()

        while len(inflight) < max_inflight and done_success + len(inflight) < budget and candidate_buf:
            x_u = candidate_buf.pop(0)
            x_u = [float(v) for v in x_u]

            # Build params + hashes
            params = core_local.u_to_params(x_u)
            ph = hash_params(params, float_ndigits=12)

            # Reserve in DB (dedup + cache)
            res = db.reserve_trial(
                run_id=run_id,
                problem_hash=problem_hash,
                param_hash=ph,
                x_u=list(x_u),
                params=params,
            )
            res_status = str(res.status or "").strip().upper()
            trial_id = str(res.trial_id or "").strip()

            if res_status == "DONE" and res.y is not None:
                # Cache hit or already done in this run
                if trial_id and trial_id in counted_done_trial_ids:
                    dedup_skip_done_count += 1
                    _sync_last_proposer_meta_diag()
                    continue
                done_success += 1
                X_done.append(list(x_u))
                Y_done.append(list(res.y))
                if isinstance(res.g, list):
                    G_done.append(list(res.g))
                if trial_id:
                    counted_done_trial_ids.add(trial_id)

                _write_trial_artifact(
                    run_dir,
                    {
                        "trial_id": res.trial_id,
                        "status": "DONE",
                        "from_cache": bool(res.from_cache),
                        "x_u": list(x_u),
                        "params": params,
                        "y": res.y,
                        "g": res.g,
                        "metrics": res.metrics,
                    },
                )
                continue

            # Skip duplicate scheduling for a trial already running elsewhere
            # or already submitted in this coordinator loop.
            if res_status == "RUNNING":
                dedup_skip_running_count += 1
                _sync_last_proposer_meta_diag()
                continue
            if trial_id and _trial_is_inflight(trial_id):
                dedup_skip_inflight_count += 1
                _sync_last_proposer_meta_diag()
                continue

            # Submit evaluation
            db.mark_running(trial_id, worker_tag="ray")

            actor = evaluators[next_eval % len(evaluators)]
            next_eval += 1

            fut = actor.evaluate.remote(trial_id, list(x_u))
            inflight[fut] = {"trial_id": trial_id, "x_u": list(x_u), "param_hash": ph, "t0": _now()}

        if not inflight:
            # No active work. If we made progress this cycle, loop again;
            # otherwise inject a rescue random candidate to avoid duplicate stalls.
            if done_success > done_before_cycle:
                stagnation_cycles = 0
                stall_last_cycles = 0
                _sync_run_spec_stall()
                continue
            stagnation_cycles += 1
            stall_last_cycles = int(stagnation_cycles)
            if done_success < budget and stagnation_cycles <= int(stall_rescue_limit_cycles):
                x_rescue = [float(v) for v in rng.random(dim).tolist()]
                candidate_buf.append(x_rescue)
                stall_rescue_count += 1
                _sync_run_spec_stall()
                _write_last_proposer_meta(
                    {
                        "requested_mode": str(getattr(args, "proposer", "") or ""),
                        "effective_mode": "random",
                        "reason": "stall_rescue_random",
                    }
                )
                continue
            stall_terminated = True
            _sync_run_spec_stall()
            print(f"[RAY] stall detected (cycles={stagnation_cycles}); stopping before budget={budget}")
            break
        stagnation_cycles = 0
        stall_last_cycles = 0
        _sync_run_spec_stall()

        # Wait for one completion
        ready, _ = ray.wait(list(inflight.keys()), num_returns=1, timeout=5.0)
        if not ready:
            # loop back to heartbeat / fill
            continue

        fut = ready[0]
        meta = inflight.pop(fut)
        trial_id = meta["trial_id"]

        try:
            y, g, row = ray.get(fut)
            # Persist
            db.mark_done(trial_id, y=list(y), g=list(g) if g is not None else None, metrics=dict(row))
            db.upsert_cache(problem_hash=problem_hash, param_hash=meta["param_hash"], y=list(y), g=list(g) if g is not None else None, metrics=dict(row))

            # In-memory (count each trial_id at most once)
            if not (trial_id and trial_id in counted_done_trial_ids):
                X_done.append(list(meta["x_u"]))
                Y_done.append(list(y))
                if g is not None:
                    G_done.append(list(g))
                done_success += 1
                if trial_id:
                    counted_done_trial_ids.add(trial_id)
            else:
                dedup_skip_done_count += 1
                _sync_last_proposer_meta_diag()

            _write_trial_artifact(
                run_dir,
                {
                    "trial_id": trial_id,
                    "status": "DONE",
                    "x_u": list(meta["x_u"]),
                    "params": core_local.u_to_params(meta["x_u"]),
                    "y": list(y),
                    "g": list(g) if g is not None else None,
                    "metrics": row,
                },
            )

        except Exception as e:
            err = str(e)
            db.mark_error(trial_id, err)
            _write_trial_artifact(
                run_dir,
                {
                    "trial_id": trial_id,
                    "status": "ERROR",
                    "x_u": list(meta["x_u"]),
                    "params": core_local.u_to_params(meta["x_u"]),
                    "error": err,
                },
            )

        # HV logging
        hv = None
        if args.hv_log and Y_done:
            hv, hv_meta = _compute_hv(
                np.asarray(Y_done, dtype=float),
                np.asarray(G_done, dtype=float) if G_done else np.zeros((0, 1), dtype=float),
                obj_names=objective_keys,
            )
            if hv is not None:
                db.add_run_metric(run_id, key="hypervolume", value=float(hv), json_blob=hv_meta)
                with (run_dir / "progress_hv.csv").open("a", encoding="utf-8") as f:
                    f.write(f"{_now():.6f},{done_success},{hv:.12g}\n")

        maybe_export()

        print(f"done={done_success}/{budget} inflight={len(inflight)} hv={(hv if hv is not None else 'NA')}")

    # Final export
    _sync_run_spec_stall()
    db.export_run_to_csv(run_id, out_dir=str(run_dir / "export"))


# ------------------------------
# Dask backend
# ------------------------------


def _run_dask(
    args: argparse.Namespace,
    *,
    core_local: EvaluatorCore,
    db: ExperimentDB,
    run_id: str,
    run_dir: Path,
    problem_hash: str,
    objective_keys: List[str],
) -> None:
    try:
        from distributed import Client, LocalCluster, as_completed
    except Exception as e:
        raise RuntimeError("Dask distributed is not installed. Install with: pip install dask[distributed]") from e

    base_dir = _PNEUMO_ROOT

    model_p = str(Path(args.model))
    worker_p = str(Path(args.worker))
    base_json_p = str(Path(args.base_json)) if args.base_json else ""
    ranges_json_p = str(Path(args.ranges_json)) if args.ranges_json else ""
    suite_json_p = str(Path(args.suite_json)) if args.suite_json else ""

    cfg_override: Dict[str, Any] = {
        "objective_keys": tuple(objective_keys),
        "penalty_key": str(args.penalty_key),
        "penalty_tol": float(args.penalty_tol),
    }

    if args.dask_scheduler:
        client = Client(args.dask_scheduler)
    else:
        n_workers = int(args.dask_workers) if int(args.dask_workers) > 0 else None
        cluster_kwargs: Dict[str, Any] = {
            "n_workers": n_workers,
            "threads_per_worker": max(1, int(getattr(args, "dask_threads_per_worker", 1) or 1)),
            "processes": True,
        }
        memory_limit = _normalize_dask_memory_limit(getattr(args, "dask_memory_limit", ""))
        if memory_limit is not None:
            cluster_kwargs["memory_limit"] = memory_limit
        dashboard_address = _normalize_dashboard_address(getattr(args, "dask_dashboard_address", ""))
        cluster_kwargs["dashboard_address"] = dashboard_address
        cluster = LocalCluster(**cluster_kwargs)
        client = Client(cluster)

    _dump_json(run_dir / "dask_scheduler_info.json", client.scheduler_info())

    # Task function (each process loads its own core)
    def _eval_task(trial_id: str, x_u: List[float]):
        apply_problem_hash_env(problem_hash)
        core = EvaluatorCore(
            model_path=model_p,
            worker_path=worker_p,
            base_json=base_json_p or None,
            ranges_json=ranges_json_p or None,
            suite_json=suite_json_p or None,
            cfg=cfg_override,
        )
        y, g, row = core.evaluate(trial_id=trial_id, x_u=x_u)
        row["dask_worker"] = os.environ.get("DASK_WORKER_NAME", "")
        return y, g, row

    info = client.scheduler_info()
    n_workers = len(info.get("workers", {}))
    max_inflight = int(args.max_inflight) if int(args.max_inflight) > 0 else max(2, 2 * max(1, n_workers))

    rng = np.random.default_rng(int(args.seed))

    # Existing DONE
    X_done: List[List[float]] = []
    Y_done: List[List[float]] = []
    G_done: List[List[float]] = []
    counted_done_trial_ids: set[str] = set()

    done_rows = db.fetch_done_trials(run_id)
    for r in done_rows:
        if not isinstance(r.get("x_u"), list) or not isinstance(r.get("y"), list):
            continue
        X_done.append(list(r["x_u"]))
        Y_done.append(list(r["y"]))
        if isinstance(r.get("g"), list):
            G_done.append(list(r["g"]))
        tid = str(r.get("trial_id") or "").strip()
        if tid:
            counted_done_trial_ids.add(tid)

    done_success = len(X_done)
    budget = int(args.budget)
    dim = int(core_local.dim())
    stall_rescue_limit_cycles = max(8, 2 * max(1, dim))
    stall_rescue_count = 0
    stall_last_cycles = 0
    stall_terminated = False
    stagnation_cycles = 0
    dedup_skip_done_count = 0
    dedup_skip_running_count = 0
    dedup_skip_inflight_count = 0
    proposer_effective_mode_counts: Dict[str, int] = {}
    proposer_reason_counts: Dict[str, int] = {}
    portfolio_rand_q_last_base = 0
    portfolio_rand_q_last_effective = 0
    portfolio_rand_q_boost_events = 0
    portfolio_history: List[Dict[str, Any]] = []
    portfolio_primary_last_choice = "qnehvi"
    portfolio_primary_last_reason = "default_qnehvi"
    portfolio_primary_switches = 0
    portfolio_primary_switch_cooldown_span = 2
    portfolio_primary_cooldown_ticks = 0
    portfolio_primary_cooldown_holds = 0
    portfolio_primary_choice_counts: Dict[str, int] = {"qnehvi": 0, "heuristic": 0}
    base_heuristic_buffer = int(max(0, int(getattr(args, "proposer_buffer", 0) or 0)))
    heuristic_buffer_last_effective = int(base_heuristic_buffer)
    heuristic_buffer_boost_events = 0
    base_heuristic_q = _coerce_positive_int(getattr(args, "q", 1), default=1)
    heuristic_q_last_effective = int(base_heuristic_q)
    heuristic_q_boost_events = 0
    base_heuristic_pool_size = _coerce_positive_int(
        getattr(args, "heuristic_pool_size", DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
        default=int(DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
    )
    heuristic_pool_size_last_effective = int(base_heuristic_pool_size)
    heuristic_pool_size_boost_events = 0
    base_heuristic_explore = _clamp_unit_interval(
        getattr(args, "heuristic_explore", DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
        default=float(DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
    )
    heuristic_explore_last_effective = float(base_heuristic_explore)
    heuristic_explore_boost_events = 0
    seed_vectors, seed_meta = _load_seed_vectors(core_local, getattr(args, "seed_json", ""))
    _dump_json(run_dir / "seed_info.json", dict(seed_meta))
    seed_queue = [] if bool(args.resume) else list(seed_vectors)

    if args.resume:
        n_re = db.requeue_stale(run_id, ttl_sec=float(args.stale_ttl_sec))
        if n_re:
            print(f"[RESUME] requeued stale RUNNING trials: {n_re}")

    pending_rows = db.fetch_trials(run_id, status="PENDING") if args.resume else []

    candidate_buf: List[List[float]] = []
    candidate_buf.extend(list(x_u) for x_u in seed_queue)
    for pr in pending_rows:
        if isinstance(pr.get("x_u"), list):
            candidate_buf.append(list(pr["x_u"]))

    auto_n_init = max(8, 2 * (dim + 1))
    lhs_target = max(auto_n_init, int(getattr(args, "n_init", 0) or 0))
    lhs_pool_n = max(0, int(lhs_target - done_success - len(seed_queue)))
    lhs_pool = sample_lhs(n=int(lhs_pool_n), d=dim, seed=int(args.seed))
    lhs_i = lhs_pool.shape[0] if args.resume else 0

    run_spec_path = run_dir / "run_spec.json"
    run_spec_payload: Dict[str, Any] = {
        "run_id": run_id,
        "backend": "dask",
        "dim": int(dim),
        "objective_keys": list(objective_keys),
        "penalty_key": str(args.penalty_key),
        "penalty_tol": float(args.penalty_tol),
        "seed": int(args.seed),
        "max_inflight": int(max_inflight),
        "proposer": str(getattr(args, "proposer", "auto") or "auto"),
        "q": int(getattr(args, "q", 1) or 1),
        "n_init": int(args.n_init),
        "min_feasible": _coerce_nonnegative_int(
            getattr(args, "min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
            default=int(DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
        ),
        "heuristic_buffer_base": int(base_heuristic_buffer),
        "heuristic_buffer_last_effective": int(heuristic_buffer_last_effective),
        "heuristic_buffer_boost_events": int(heuristic_buffer_boost_events),
        "heuristic_q_base": int(base_heuristic_q),
        "heuristic_q_last_effective": int(heuristic_q_last_effective),
        "heuristic_q_boost_events": int(heuristic_q_boost_events),
        "heuristic_pool_size": int(getattr(args, "heuristic_pool_size", DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT) or DIST_OPT_HEURISTIC_POOL_SIZE_DEFAULT),
        "heuristic_pool_size_base": int(base_heuristic_pool_size),
        "heuristic_pool_size_last_effective": int(heuristic_pool_size_last_effective),
        "heuristic_pool_size_boost_events": int(heuristic_pool_size_boost_events),
        "heuristic_explore": float(getattr(args, "heuristic_explore", DIST_OPT_HEURISTIC_EXPLORE_DEFAULT) or DIST_OPT_HEURISTIC_EXPLORE_DEFAULT),
        "heuristic_explore_base": float(base_heuristic_explore),
        "heuristic_explore_last_effective": float(heuristic_explore_last_effective),
        "heuristic_explore_boost_events": int(heuristic_explore_boost_events),
        "portfolio_rand_q_last_base": int(portfolio_rand_q_last_base),
        "portfolio_rand_q_last_effective": int(portfolio_rand_q_last_effective),
        "portfolio_rand_q_boost_events": int(portfolio_rand_q_boost_events),
        "portfolio_primary_last_choice": str(portfolio_primary_last_choice),
        "portfolio_primary_last_reason": str(portfolio_primary_last_reason),
        "portfolio_primary_switches": int(portfolio_primary_switches),
        "portfolio_primary_switch_cooldown_span": int(portfolio_primary_switch_cooldown_span),
        "portfolio_primary_cooldown_ticks": int(portfolio_primary_cooldown_ticks),
        "portfolio_primary_cooldown_holds": int(portfolio_primary_cooldown_holds),
        "portfolio_primary_choice_counts": dict(portfolio_primary_choice_counts),
        "portfolio_history_size": int(len(portfolio_history)),
        "dask_scheduler": str(getattr(args, "dask_scheduler", "") or ""),
        "dask_scheduler_info": info,
        "dask_num_workers": int(n_workers),
        "seed_json": str(seed_meta.get("seed_json") or ""),
        "seed_loaded": int(seed_meta.get("loaded") or 0),
        "seed_invalid": int(seed_meta.get("invalid") or 0),
        "seed_duplicates": int(seed_meta.get("duplicates") or 0),
        "stall_rescue_limit_cycles": int(stall_rescue_limit_cycles),
        "stall_rescue_count": int(stall_rescue_count),
        "stall_last_cycles": int(stall_last_cycles),
        "stall_terminated": bool(stall_terminated),
        "dedup_skip_done_count": int(dedup_skip_done_count),
        "dedup_skip_running_count": int(dedup_skip_running_count),
        "dedup_skip_inflight_count": int(dedup_skip_inflight_count),
        "dedup_skip_total": int(dedup_skip_done_count + dedup_skip_running_count + dedup_skip_inflight_count),
        "proposer_effective_mode_counts": dict(proposer_effective_mode_counts),
        "proposer_reason_counts": dict(proposer_reason_counts),
        "proposer_meta_events": int(sum(int(v) for v in proposer_effective_mode_counts.values())),
    }
    _dump_json(run_spec_path, run_spec_payload)

    inflight: Dict[Any, Dict[str, Any]] = {}
    ac = as_completed([])

    def _trial_is_inflight(trial_id: str) -> bool:
        tid = str(trial_id or "").strip()
        if not tid:
            return False
        for meta in inflight.values():
            if str(meta.get("trial_id") or "").strip() == tid:
                return True
        return False

    if args.hv_log:
        hv_csv = run_dir / "progress_hv.csv"
        if not hv_csv.exists():
            hv_csv.write_text("ts,done_success,hv\n", encoding="utf-8")

    last_export_done = done_success

    def maybe_export():
        nonlocal last_export_done
        if int(args.export_every) <= 0:
            return
        if (done_success - last_export_done) >= int(args.export_every):
            out_dir = run_dir / "export"
            db.export_run_to_csv(run_id, out_dir=str(out_dir))
            last_export_done = done_success

    def _sync_run_spec_stall() -> None:
        run_spec_payload["stall_rescue_count"] = int(stall_rescue_count)
        run_spec_payload["stall_last_cycles"] = int(stall_last_cycles)
        run_spec_payload["stall_terminated"] = bool(stall_terminated)
        run_spec_payload["dedup_skip_done_count"] = int(dedup_skip_done_count)
        run_spec_payload["dedup_skip_running_count"] = int(dedup_skip_running_count)
        run_spec_payload["dedup_skip_inflight_count"] = int(dedup_skip_inflight_count)
        run_spec_payload["dedup_skip_total"] = int(
            dedup_skip_done_count + dedup_skip_running_count + dedup_skip_inflight_count
        )
        run_spec_payload["proposer_effective_mode_counts"] = dict(proposer_effective_mode_counts)
        run_spec_payload["proposer_reason_counts"] = dict(proposer_reason_counts)
        run_spec_payload["proposer_meta_events"] = int(
            sum(int(v) for v in proposer_effective_mode_counts.values())
        )
        run_spec_payload["heuristic_buffer_base"] = int(base_heuristic_buffer)
        run_spec_payload["heuristic_buffer_last_effective"] = int(heuristic_buffer_last_effective)
        run_spec_payload["heuristic_buffer_boost_events"] = int(heuristic_buffer_boost_events)
        run_spec_payload["heuristic_q_base"] = int(base_heuristic_q)
        run_spec_payload["heuristic_q_last_effective"] = int(heuristic_q_last_effective)
        run_spec_payload["heuristic_q_boost_events"] = int(heuristic_q_boost_events)
        run_spec_payload["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
        run_spec_payload["heuristic_pool_size_last_effective"] = int(heuristic_pool_size_last_effective)
        run_spec_payload["heuristic_pool_size_boost_events"] = int(heuristic_pool_size_boost_events)
        run_spec_payload["heuristic_explore_base"] = float(base_heuristic_explore)
        run_spec_payload["heuristic_explore_last_effective"] = float(heuristic_explore_last_effective)
        run_spec_payload["heuristic_explore_boost_events"] = int(heuristic_explore_boost_events)
        run_spec_payload["portfolio_rand_q_last_base"] = int(portfolio_rand_q_last_base)
        run_spec_payload["portfolio_rand_q_last_effective"] = int(portfolio_rand_q_last_effective)
        run_spec_payload["portfolio_rand_q_boost_events"] = int(portfolio_rand_q_boost_events)
        run_spec_payload["portfolio_primary_last_choice"] = str(portfolio_primary_last_choice)
        run_spec_payload["portfolio_primary_last_reason"] = str(portfolio_primary_last_reason)
        run_spec_payload["portfolio_primary_switches"] = int(portfolio_primary_switches)
        run_spec_payload["portfolio_primary_switch_cooldown_span"] = int(portfolio_primary_switch_cooldown_span)
        run_spec_payload["portfolio_primary_cooldown_ticks"] = int(portfolio_primary_cooldown_ticks)
        run_spec_payload["portfolio_primary_cooldown_holds"] = int(portfolio_primary_cooldown_holds)
        run_spec_payload["portfolio_primary_choice_counts"] = dict(portfolio_primary_choice_counts)
        run_spec_payload["portfolio_history_size"] = int(len(portfolio_history))
        _dump_json(run_spec_path, run_spec_payload)
        _sync_last_proposer_meta_diag()

    last_meta_path = run_dir / "last_proposer_meta.json"
    last_proposer_meta: Dict[str, Any] = {}

    def _sync_last_proposer_meta_diag() -> None:
        diag_nonzero = bool(
            (stall_rescue_count > 0)
            or (stall_last_cycles > 0)
            or bool(stall_terminated)
            or (dedup_skip_done_count > 0)
            or (dedup_skip_running_count > 0)
            or (dedup_skip_inflight_count > 0)
        )
        payload = dict(last_proposer_meta or {})
        if not payload and last_meta_path.exists():
            try:
                loaded = json.loads(last_meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = dict(loaded)
            except Exception:
                payload = {}
        if not payload and not diag_nonzero:
            return
        if not payload:
            payload = {
                "requested_mode": str(getattr(args, "proposer", "") or ""),
                "effective_mode": "random",
                "reason": "runtime_diagnostics_sync",
            }
        payload["stall_rescue_limit_cycles"] = int(stall_rescue_limit_cycles)
        payload["stall_rescue_count"] = int(stall_rescue_count)
        payload["stall_stagnation_cycles"] = int(stagnation_cycles)
        payload["stall_terminated"] = bool(stall_terminated)
        payload["dedup_skip_done_count"] = int(dedup_skip_done_count)
        payload["dedup_skip_running_count"] = int(dedup_skip_running_count)
        payload["dedup_skip_inflight_count"] = int(dedup_skip_inflight_count)
        payload["dedup_skip_total"] = int(
            dedup_skip_done_count + dedup_skip_running_count + dedup_skip_inflight_count
        )
        payload["heuristic_buffer_base"] = int(base_heuristic_buffer)
        payload["heuristic_buffer_last_effective"] = int(heuristic_buffer_last_effective)
        payload["heuristic_buffer_boost_events"] = int(heuristic_buffer_boost_events)
        payload["heuristic_q_base"] = int(base_heuristic_q)
        payload["heuristic_q_last_effective"] = int(heuristic_q_last_effective)
        payload["heuristic_q_boost_events"] = int(heuristic_q_boost_events)
        payload["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
        payload["heuristic_pool_size_last_effective"] = int(heuristic_pool_size_last_effective)
        payload["heuristic_pool_size_boost_events"] = int(heuristic_pool_size_boost_events)
        payload["heuristic_explore_base"] = float(base_heuristic_explore)
        payload["heuristic_explore_last_effective"] = float(heuristic_explore_last_effective)
        payload["heuristic_explore_boost_events"] = int(heuristic_explore_boost_events)
        payload["portfolio_rand_q_last_base"] = int(portfolio_rand_q_last_base)
        payload["portfolio_rand_q_last_effective"] = int(portfolio_rand_q_last_effective)
        payload["portfolio_rand_q_boost_events"] = int(portfolio_rand_q_boost_events)
        payload["portfolio_primary_last_choice"] = str(portfolio_primary_last_choice)
        payload["portfolio_primary_last_reason"] = str(portfolio_primary_last_reason)
        payload["portfolio_primary_switches"] = int(portfolio_primary_switches)
        payload["portfolio_primary_switch_cooldown_span"] = int(portfolio_primary_switch_cooldown_span)
        payload["portfolio_primary_cooldown_ticks"] = int(portfolio_primary_cooldown_ticks)
        payload["portfolio_primary_cooldown_holds"] = int(portfolio_primary_cooldown_holds)
        payload["portfolio_primary_choice_counts"] = dict(portfolio_primary_choice_counts)
        payload["portfolio_history_size"] = int(len(portfolio_history))
        _write_text(last_meta_path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _write_last_proposer_meta(meta_out: Dict[str, Any]) -> None:
        nonlocal last_proposer_meta
        last_proposer_meta = dict(meta_out or {})
        mode_key = str(last_proposer_meta.get("effective_mode") or "").strip().lower()
        if mode_key:
            proposer_effective_mode_counts[mode_key] = int(proposer_effective_mode_counts.get(mode_key, 0) + 1)
        reason_key = str(
            last_proposer_meta.get("reason")
            or last_proposer_meta.get("fallback_reason")
            or ""
        ).strip().lower()
        if reason_key:
            proposer_reason_counts[reason_key] = int(proposer_reason_counts.get(reason_key, 0) + 1)
        _sync_last_proposer_meta_diag()

    def fill_buffer():
        nonlocal lhs_i, heuristic_explore_last_effective, heuristic_explore_boost_events
        nonlocal heuristic_buffer_last_effective, heuristic_buffer_boost_events
        nonlocal heuristic_q_last_effective, heuristic_q_boost_events
        nonlocal heuristic_pool_size_last_effective, heuristic_pool_size_boost_events
        nonlocal portfolio_rand_q_last_base, portfolio_rand_q_last_effective, portfolio_rand_q_boost_events
        nonlocal portfolio_primary_last_choice, portfolio_primary_last_reason, portfolio_primary_switches
        nonlocal portfolio_primary_cooldown_ticks, portfolio_primary_cooldown_holds
        target = int(max(0, args.proposer_buffer))
        if len(candidate_buf) >= target:
            return

        while lhs_i < lhs_pool.shape[0] and len(candidate_buf) < target:
            candidate_buf.append(lhs_pool[lhs_i].tolist())
            lhs_i += 1

        if len(candidate_buf) >= target:
            return

        # Pending points
        X_pending = None
        if inflight:
            X_pending = np.asarray([meta["x_u"] for meta in inflight.values()], dtype=float)

        feasible_n = _count_feasible_trials(G_done) if G_done else len(X_done)
        mode_info = resolve_proposer_mode(
            args,
            done_n=len(X_done),
            feasible_n=feasible_n,
            dim=dim,
        )
        prop_mode = str(mode_info["mode"])
        want_portfolio = bool(mode_info["portfolio_enabled"])
        pool_fallback_error: Optional[str] = None

        def _next_heuristic_explore() -> float:
            nonlocal heuristic_explore_last_effective, heuristic_explore_boost_events
            effective = _adaptive_heuristic_explore_weight(
                base_heuristic_explore,
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_explore_last_effective = float(effective)
            if effective > (base_heuristic_explore + 1e-12):
                heuristic_explore_boost_events += 1
            return float(effective)

        def _next_heuristic_pool_size() -> int:
            nonlocal heuristic_pool_size_last_effective, heuristic_pool_size_boost_events
            effective = _adaptive_heuristic_pool_size(
                base_heuristic_pool_size,
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_pool_size_last_effective = int(effective)
            if int(effective) > int(base_heuristic_pool_size):
                heuristic_pool_size_boost_events += 1
            return int(effective)

        def _next_heuristic_q(*, need: int) -> int:
            nonlocal heuristic_q_last_effective, heuristic_q_boost_events
            effective = _adaptive_heuristic_q(
                base_heuristic_q,
                need=int(need),
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_q_last_effective = int(effective)
            if int(effective) > int(base_heuristic_q):
                heuristic_q_boost_events += 1
            return int(effective)

        def _next_heuristic_buffer() -> int:
            nonlocal heuristic_buffer_last_effective, heuristic_buffer_boost_events
            if int(base_heuristic_buffer) <= 0:
                heuristic_buffer_last_effective = 0
                return 0
            effective = _adaptive_heuristic_buffer_target(
                int(max(1, base_heuristic_buffer)),
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            heuristic_buffer_last_effective = int(effective)
            if int(effective) > int(base_heuristic_buffer):
                heuristic_buffer_boost_events += 1
            return int(effective)

        def _next_portfolio_rand_q(*, need: int) -> int:
            nonlocal portfolio_rand_q_last_base, portfolio_rand_q_last_effective, portfolio_rand_q_boost_events
            base_q, effective_q = _adaptive_portfolio_rand_q(
                int(need),
                stagnation_cycles=stagnation_cycles,
                rescue_limit_cycles=stall_rescue_limit_cycles,
            )
            portfolio_rand_q_last_base = int(base_q)
            portfolio_rand_q_last_effective = int(effective_q)
            if int(effective_q) > int(base_q):
                portfolio_rand_q_boost_events += 1
            return int(effective_q)

        def _record_portfolio_event(*, mode: str, success: bool) -> None:
            _portfolio_record_event(
                portfolio_history,
                mode=str(mode),
                success=bool(success),
                maxlen=12,
            )

        def _resolve_portfolio_primary() -> Tuple[str, str]:
            nonlocal portfolio_primary_last_choice, portfolio_primary_last_reason, portfolio_primary_switches
            nonlocal portfolio_primary_cooldown_ticks, portfolio_primary_cooldown_holds
            primary, reason, _stats = _portfolio_choose_primary_mode(
                portfolio_history,
                lookback=8,
                min_attempts_per_mode=3,
                min_success_gap=0.20,
                previous_choice=portfolio_primary_last_choice,
                switch_cooldown_ticks=int(portfolio_primary_cooldown_ticks),
            )
            primary_key = str(primary or "qnehvi").strip().lower()
            if primary_key not in {"qnehvi", "heuristic"}:
                primary_key = "qnehvi"
            prev_key = str(portfolio_primary_last_choice or "qnehvi").strip().lower()
            portfolio_primary_last_choice = str(primary_key)
            portfolio_primary_last_reason = str(reason or "default_qnehvi")
            if prev_key != primary_key:
                portfolio_primary_switches += 1
                portfolio_primary_cooldown_ticks = int(max(0, int(portfolio_primary_switch_cooldown_span)))
            elif int(portfolio_primary_cooldown_ticks) > 0:
                portfolio_primary_cooldown_ticks = int(portfolio_primary_cooldown_ticks) - 1
            if str(portfolio_primary_last_reason).strip().lower() == "cooldown_hold":
                portfolio_primary_cooldown_holds += 1
            portfolio_primary_choice_counts[primary_key] = int(portfolio_primary_choice_counts.get(primary_key, 0) + 1)
            return str(primary_key), str(portfolio_primary_last_reason)

        portfolio_primary = "qnehvi"
        portfolio_primary_reason = "not_portfolio"
        if want_portfolio:
            portfolio_primary, portfolio_primary_reason = _resolve_portfolio_primary()

        need = max(1, target - len(candidate_buf))
        if prop_mode in {"qnehvi", "portfolio"} and want_portfolio and portfolio_primary == "heuristic":
            try:
                heuristic_buffer_effective = _next_heuristic_buffer()
                heuristic_need = int(max(1, heuristic_buffer_effective - len(candidate_buf)))
                heuristic_q_effective = _next_heuristic_q(need=heuristic_need)
                heuristic_explore_effective = _next_heuristic_explore()
                heuristic_pool_size_effective = _next_heuristic_pool_size()
                pr = propose_heuristic(
                    X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                    Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                    penalty=_heuristic_penalty_from_constraints(G_done),
                    q=int(heuristic_q_effective),
                    seed=int(rng.integers(0, 2**31 - 1)),
                    X_pending=X_pending,
                    feasible_tol=float(args.penalty_tol),
                    pool_size=int(heuristic_pool_size_effective),
                    explore_weight=float(heuristic_explore_effective),
                )
                meta_out = dict(pr.meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = "heuristic"
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                meta_out["heuristic_buffer_base"] = int(base_heuristic_buffer)
                meta_out["heuristic_buffer_effective"] = int(heuristic_buffer_effective)
                meta_out["heuristic_q_base"] = int(base_heuristic_q)
                meta_out["heuristic_q_effective"] = int(heuristic_q_effective)
                meta_out["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
                meta_out["heuristic_pool_size_effective"] = int(heuristic_pool_size_effective)
                meta_out["heuristic_explore_base"] = float(base_heuristic_explore)
                meta_out["heuristic_explore_effective"] = float(heuristic_explore_effective)
                meta_out["heuristic_explore_stagnation_cycles"] = int(stagnation_cycles)
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                for x_u in pr.X.tolist():
                    candidate_buf.append(list(x_u))
                _record_portfolio_event(mode="heuristic", success=True)
                _write_last_proposer_meta(meta_out)
                n_rand = _next_portfolio_rand_q(need=need)
                Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                for x_u in Xr.tolist():
                    candidate_buf.append(list(x_u))
                return
            except Exception as h_exc:
                _record_portfolio_event(mode="heuristic", success=False)
                try:
                    pr = propose_qnehvi(
                        X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                        Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                        G_min_done=np.asarray(G_done, dtype=float) if G_done else None,
                        q=int(need),
                        seed=int(rng.integers(0, 2**31 - 1)),
                        X_pending=X_pending,
                        device=str(args.device),
                        normalize_objectives=not bool(getattr(args, "botorch_no_normalize_objectives", False)),
                        ref_margin=float(getattr(args, "botorch_ref_margin", 0.10)),
                        num_restarts=int(getattr(args, "botorch_num_restarts", 10)),
                        raw_samples=int(getattr(args, "botorch_raw_samples", 512)),
                        maxiter=int(getattr(args, "botorch_maxiter", 200)),
                    )
                    meta_out = dict(pr.meta or {})
                    meta_out["requested_mode"] = mode_info["requested"]
                    meta_out["effective_mode"] = "qnehvi"
                    meta_out["n_init"] = mode_info["n_init"]
                    meta_out["min_feasible"] = mode_info["min_feasible"]
                    meta_out["ready_by_done"] = mode_info["ready_by_done"]
                    meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                    meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                    meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                    meta_out["fallback_reason"] = "heuristic_primary_failed"
                    meta_out["fallback_error"] = f"{type(h_exc).__name__}: {h_exc}"
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    for x_u in pr.X.tolist():
                        candidate_buf.append(list(x_u))
                    _record_portfolio_event(mode="qnehvi", success=True)
                    _write_last_proposer_meta(meta_out)
                    n_rand = _next_portfolio_rand_q(need=need)
                    Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                    return
                except Exception as q_exc:
                    _record_portfolio_event(mode="qnehvi", success=False)
                    meta_out = {
                        "requested_mode": mode_info["requested"],
                        "effective_mode": "random",
                        "n_init": mode_info["n_init"],
                        "min_feasible": mode_info["min_feasible"],
                        "ready_by_done": mode_info["ready_by_done"],
                        "ready_by_feasible": mode_info["ready_by_feasible"],
                        "portfolio_primary_choice": str(portfolio_primary),
                        "portfolio_preference_reason": str(portfolio_primary_reason),
                        "reason": "heuristic_and_qnehvi_failed",
                        "fallback_error": f"{type(h_exc).__name__}: {h_exc}; {type(q_exc).__name__}: {q_exc}",
                    }
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    _write_last_proposer_meta(meta_out)
                    Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                    n_rand = _next_portfolio_rand_q(need=need)
                    Xr2 = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr2.tolist():
                        candidate_buf.append(list(x_u))
                    return
        if prop_mode in {"qnehvi", "portfolio"}:
            try:
                pr = propose_qnehvi(
                    X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                    Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                    G_min_done=np.asarray(G_done, dtype=float) if G_done else None,
                    q=int(need),
                    seed=int(rng.integers(0, 2**31 - 1)),
                    X_pending=X_pending,
                    device=str(args.device),
                    normalize_objectives=not bool(getattr(args, "botorch_no_normalize_objectives", False)),
                    ref_margin=float(getattr(args, "botorch_ref_margin", 0.10)),
                    num_restarts=int(getattr(args, "botorch_num_restarts", 10)),
                    raw_samples=int(getattr(args, "botorch_raw_samples", 512)),
                    maxiter=int(getattr(args, "botorch_maxiter", 200)),
                )
                meta_out = dict(pr.meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = mode_info["mode"]
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                if want_portfolio:
                    meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                    meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                for x_u in pr.X.tolist():
                    candidate_buf.append(list(x_u))
                if want_portfolio:
                    _record_portfolio_event(mode="qnehvi", success=True)
                _write_last_proposer_meta(meta_out)
                if want_portfolio:
                    n_rand = _next_portfolio_rand_q(need=need)
                    Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                return
            except Exception as q_exc:
                if want_portfolio:
                    _record_portfolio_event(mode="qnehvi", success=False)
                try:
                    heuristic_buffer_effective = _next_heuristic_buffer()
                    heuristic_need = int(max(1, heuristic_buffer_effective - len(candidate_buf)))
                    heuristic_q_effective = _next_heuristic_q(need=heuristic_need)
                    heuristic_explore_effective = _next_heuristic_explore()
                    heuristic_pool_size_effective = _next_heuristic_pool_size()
                    pr = propose_heuristic(
                        X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                        Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                        penalty=_heuristic_penalty_from_constraints(G_done),
                        q=int(heuristic_q_effective),
                        seed=int(rng.integers(0, 2**31 - 1)),
                        X_pending=X_pending,
                        feasible_tol=float(args.penalty_tol),
                        pool_size=int(heuristic_pool_size_effective),
                        explore_weight=float(heuristic_explore_effective),
                    )
                    meta_out = dict(pr.meta or {})
                    meta_out["requested_mode"] = mode_info["requested"]
                    meta_out["effective_mode"] = "heuristic"
                    meta_out["n_init"] = mode_info["n_init"]
                    meta_out["min_feasible"] = mode_info["min_feasible"]
                    meta_out["ready_by_done"] = mode_info["ready_by_done"]
                    meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                    meta_out["fallback_reason"] = "qnehvi_failed"
                    meta_out["fallback_error"] = f"{type(q_exc).__name__}: {q_exc}"
                    if want_portfolio:
                        meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                        meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                    meta_out["heuristic_buffer_base"] = int(base_heuristic_buffer)
                    meta_out["heuristic_buffer_effective"] = int(heuristic_buffer_effective)
                    meta_out["heuristic_q_base"] = int(base_heuristic_q)
                    meta_out["heuristic_q_effective"] = int(heuristic_q_effective)
                    meta_out["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
                    meta_out["heuristic_pool_size_effective"] = int(heuristic_pool_size_effective)
                    meta_out["heuristic_explore_base"] = float(base_heuristic_explore)
                    meta_out["heuristic_explore_effective"] = float(heuristic_explore_effective)
                    meta_out["heuristic_explore_stagnation_cycles"] = int(stagnation_cycles)
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    for x_u in pr.X.tolist():
                        candidate_buf.append(list(x_u))
                    if want_portfolio:
                        _record_portfolio_event(mode="heuristic", success=True)
                    _write_last_proposer_meta(meta_out)
                    if want_portfolio:
                        n_rand = _next_portfolio_rand_q(need=need)
                        Xr = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                        for x_u in Xr.tolist():
                            candidate_buf.append(list(x_u))
                    return
                except Exception as h_exc:
                    if want_portfolio:
                        _record_portfolio_event(mode="heuristic", success=False)
                    meta_out = {
                        "requested_mode": mode_info["requested"],
                        "effective_mode": "random",
                        "n_init": mode_info["n_init"],
                        "min_feasible": mode_info["min_feasible"],
                        "ready_by_done": mode_info["ready_by_done"],
                        "ready_by_feasible": mode_info["ready_by_feasible"],
                        "reason": "qnehvi_and_heuristic_failed",
                        "fallback_error": f"{type(q_exc).__name__}: {q_exc}; {type(h_exc).__name__}: {h_exc}",
                    }
                    if want_portfolio:
                        meta_out["portfolio_primary_choice"] = str(portfolio_primary)
                        meta_out["portfolio_preference_reason"] = str(portfolio_primary_reason)
                    if pool_fallback_error:
                        meta_out["pool_fallback_error"] = pool_fallback_error
                    _write_last_proposer_meta(meta_out)
                    Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
                    for x_u in Xr.tolist():
                        candidate_buf.append(list(x_u))
                    if want_portfolio:
                        n_rand = _next_portfolio_rand_q(need=need)
                        Xr2 = propose_random(d=dim, q=int(n_rand), seed=int(rng.integers(0, 2**31 - 1))).X
                        for x_u in Xr2.tolist():
                            candidate_buf.append(list(x_u))
                    return
        if prop_mode == "heuristic":
            try:
                heuristic_buffer_effective = _next_heuristic_buffer()
                heuristic_need = int(max(1, heuristic_buffer_effective - len(candidate_buf)))
                heuristic_q_effective = _next_heuristic_q(need=heuristic_need)
                heuristic_explore_effective = _next_heuristic_explore()
                heuristic_pool_size_effective = _next_heuristic_pool_size()
                pr = propose_heuristic(
                    X_done=np.asarray(X_done, dtype=float) if X_done else np.zeros((0, dim), dtype=float),
                    Y_min_done=np.asarray(Y_done, dtype=float) if Y_done else np.zeros((0, len(objective_keys)), dtype=float),
                    penalty=_heuristic_penalty_from_constraints(G_done),
                    q=int(heuristic_q_effective),
                    seed=int(rng.integers(0, 2**31 - 1)),
                    X_pending=X_pending,
                    feasible_tol=float(args.penalty_tol),
                    pool_size=int(heuristic_pool_size_effective),
                    explore_weight=float(heuristic_explore_effective),
                )
                meta_out = dict(pr.meta or {})
                meta_out["requested_mode"] = mode_info["requested"]
                meta_out["effective_mode"] = mode_info["mode"]
                meta_out["n_init"] = mode_info["n_init"]
                meta_out["min_feasible"] = mode_info["min_feasible"]
                meta_out["ready_by_done"] = mode_info["ready_by_done"]
                meta_out["ready_by_feasible"] = mode_info["ready_by_feasible"]
                meta_out["heuristic_buffer_base"] = int(base_heuristic_buffer)
                meta_out["heuristic_buffer_effective"] = int(heuristic_buffer_effective)
                meta_out["heuristic_q_base"] = int(base_heuristic_q)
                meta_out["heuristic_q_effective"] = int(heuristic_q_effective)
                meta_out["heuristic_pool_size_base"] = int(base_heuristic_pool_size)
                meta_out["heuristic_pool_size_effective"] = int(heuristic_pool_size_effective)
                meta_out["heuristic_explore_base"] = float(base_heuristic_explore)
                meta_out["heuristic_explore_effective"] = float(heuristic_explore_effective)
                meta_out["heuristic_explore_stagnation_cycles"] = int(stagnation_cycles)
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                for x_u in pr.X.tolist():
                    candidate_buf.append(list(x_u))
                _write_last_proposer_meta(meta_out)
                return
            except Exception as h_exc:
                meta_out = {
                    "requested_mode": mode_info["requested"],
                    "effective_mode": "random",
                    "n_init": mode_info["n_init"],
                    "min_feasible": mode_info["min_feasible"],
                    "ready_by_done": mode_info["ready_by_done"],
                    "ready_by_feasible": mode_info["ready_by_feasible"],
                    "reason": "heuristic_failed",
                    "fallback_error": f"{type(h_exc).__name__}: {h_exc}",
                }
                if pool_fallback_error:
                    meta_out["pool_fallback_error"] = pool_fallback_error
                _write_last_proposer_meta(meta_out)
                Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
                for x_u in Xr.tolist():
                    candidate_buf.append(list(x_u))
                return

        random_reason = _random_mode_reason(mode_info)
        meta_out = {
            "requested_mode": mode_info["requested"],
            "effective_mode": prop_mode,
            "n_init": mode_info["n_init"],
            "min_feasible": mode_info["min_feasible"],
            "ready_by_done": mode_info["ready_by_done"],
            "ready_by_feasible": mode_info["ready_by_feasible"],
            "reason": random_reason,
        }
        if pool_fallback_error:
            meta_out["pool_fallback_error"] = pool_fallback_error
        _write_last_proposer_meta(meta_out)
        Xr = propose_random(d=dim, q=int(need), seed=int(rng.integers(0, 2**31 - 1))).X
        for x_u in Xr.tolist():
            candidate_buf.append(list(x_u))

    print(f"[DASK] run_id={run_id} dim={dim} budget={budget} done={done_success} max_inflight={max_inflight}")

    while done_success < budget:
        done_before_cycle = int(done_success)
        fill_buffer()

        while len(inflight) < max_inflight and done_success + len(inflight) < budget and candidate_buf:
            x_u = candidate_buf.pop(0)
            x_u = [float(v) for v in x_u]
            params = core_local.u_to_params(x_u)
            ph = hash_params(params, float_ndigits=12)

            res = db.reserve_trial(
                run_id=run_id,
                problem_hash=problem_hash,
                param_hash=ph,
                x_u=list(x_u),
                params=params,
            )
            res_status = str(res.status or "").strip().upper()
            trial_id = str(res.trial_id or "").strip()

            if res_status == "DONE" and res.y is not None:
                if trial_id and trial_id in counted_done_trial_ids:
                    dedup_skip_done_count += 1
                    _sync_last_proposer_meta_diag()
                    continue
                done_success += 1
                X_done.append(list(x_u))
                Y_done.append(list(res.y))
                if isinstance(res.g, list):
                    G_done.append(list(res.g))
                if trial_id:
                    counted_done_trial_ids.add(trial_id)
                _write_trial_artifact(run_dir, {"trial_id": res.trial_id, "status": "DONE", "from_cache": bool(res.from_cache), "x_u": list(x_u), "params": params, "y": res.y, "g": res.g, "metrics": res.metrics})
                continue

            if res_status == "RUNNING":
                dedup_skip_running_count += 1
                _sync_last_proposer_meta_diag()
                continue
            if trial_id and _trial_is_inflight(trial_id):
                dedup_skip_inflight_count += 1
                _sync_last_proposer_meta_diag()
                continue

            db.mark_running(trial_id, worker_tag="dask")
            fut = client.submit(_eval_task, trial_id, list(x_u), pure=False)
            inflight[fut] = {"trial_id": trial_id, "x_u": list(x_u), "param_hash": ph}
            ac.add(fut)

        if not inflight:
            if done_success > done_before_cycle:
                stagnation_cycles = 0
                stall_last_cycles = 0
                _sync_run_spec_stall()
                continue
            stagnation_cycles += 1
            stall_last_cycles = int(stagnation_cycles)
            if done_success < budget and stagnation_cycles <= int(stall_rescue_limit_cycles):
                x_rescue = [float(v) for v in rng.random(dim).tolist()]
                candidate_buf.append(x_rescue)
                stall_rescue_count += 1
                _sync_run_spec_stall()
                _write_last_proposer_meta(
                    {
                        "requested_mode": str(getattr(args, "proposer", "") or ""),
                        "effective_mode": "random",
                        "reason": "stall_rescue_random",
                    }
                )
                continue
            stall_terminated = True
            _sync_run_spec_stall()
            print(f"[DASK] stall detected (cycles={stagnation_cycles}); stopping before budget={budget}")
            break
        stagnation_cycles = 0
        stall_last_cycles = 0
        _sync_run_spec_stall()

        fut = next(ac)
        meta = inflight.pop(fut)
        trial_id = meta["trial_id"]

        try:
            y, g, row = fut.result()
            db.mark_done(trial_id, y=list(y), g=list(g) if g is not None else None, metrics=dict(row))
            db.upsert_cache(problem_hash=problem_hash, param_hash=meta["param_hash"], y=list(y), g=list(g) if g is not None else None, metrics=dict(row))
            if not (trial_id and trial_id in counted_done_trial_ids):
                X_done.append(list(meta["x_u"]))
                Y_done.append(list(y))
                if g is not None:
                    G_done.append(list(g))
                done_success += 1
                if trial_id:
                    counted_done_trial_ids.add(trial_id)
            else:
                dedup_skip_done_count += 1
                _sync_last_proposer_meta_diag()
            _write_trial_artifact(run_dir, {"trial_id": trial_id, "status": "DONE", "x_u": list(meta["x_u"]), "params": core_local.u_to_params(meta["x_u"]), "y": list(y), "g": list(g) if g is not None else None, "metrics": row})
        except Exception as e:
            err = str(e)
            db.mark_error(trial_id, err)
            _write_trial_artifact(run_dir, {"trial_id": trial_id, "status": "ERROR", "x_u": list(meta["x_u"]), "params": core_local.u_to_params(meta["x_u"]), "error": err})

        hv = None
        if args.hv_log and Y_done:
            hv, hv_meta = _compute_hv(
                np.asarray(Y_done, dtype=float),
                np.asarray(G_done, dtype=float) if G_done else np.zeros((0, 1), dtype=float),
                obj_names=objective_keys,
            )
            if hv is not None:
                db.add_run_metric(run_id, key="hypervolume", value=float(hv), json_blob=hv_meta)
                with (run_dir / "progress_hv.csv").open("a", encoding="utf-8") as f:
                    f.write(f"{_now():.6f},{done_success},{hv:.12g}\n")

        maybe_export()
        print(f"done={done_success}/{budget} inflight={len(inflight)} hv={(hv if hv is not None else 'NA')}")

    _sync_run_spec_stall()
    db.export_run_to_csv(run_id, out_dir=str(run_dir / "export"))
    client.close()


def main() -> None:
    args = _parse_args()

    base_dir = _PNEUMO_ROOT

    # Make relative paths stable
    os.chdir(str(base_dir))

    objective_keys = _select_objectives(args)

    # Problem spec used for stable hashing (portable paths, file hashes)
    spec_cfg = {
        "objective_keys": list(objective_keys),
        "penalty_key": str(args.penalty_key),
        "penalty_tol": float(args.penalty_tol),
    }

    model_rel = _resolve_rel_or_abs(args.model)
    worker_rel = _resolve_rel_or_abs(args.worker)
    base_json_rel = _resolve_rel_or_abs(args.base_json) if args.base_json else ""
    ranges_json_rel = _resolve_rel_or_abs(args.ranges_json) if args.ranges_json else ""
    suite_json_rel = _resolve_rel_or_abs(args.suite_json) if args.suite_json else ""

    # Validate that files exist (resolve relative-to-base_dir).
    _ = _abs_under(base_dir, model_rel)
    _ = _abs_under(base_dir, worker_rel)
    if base_json_rel:
        _ = _abs_under(base_dir, base_json_rel)
    if ranges_json_rel:
        _ = _abs_under(base_dir, ranges_json_rel)
    if suite_json_rel:
        _ = _abs_under(base_dir, suite_json_rel)

    # IMPORTANT: use *portable* (typically relative) paths in the spec, but include file hashes.
    # This keeps `problem_hash` stable across machines (as long as relative paths match).
    problem_spec = make_problem_spec(
        model_path=model_rel,
        worker_path=worker_rel,
        base_json=base_json_rel or None,
        ranges_json=ranges_json_rel or None,
        suite_json=suite_json_rel or None,
        cfg=spec_cfg,
        include_file_hashes=True,
    )
    problem_hash_mode = problem_hash_mode_from_env()
    problem_hash = (
        hash_problem(problem_spec)
        if problem_hash_mode == "legacy"
        else stable_hash_problem(problem_spec)
    )

    # DB
    # For embedded engines the target is a file path; for postgres it is a DSN.
    if str(args.db_engine).lower() == "postgres":
        db_target = str(args.db).strip()
    else:
        db_target = str(Path(_abs_under(base_dir, args.db)).resolve())
        _ensure_dir(Path(db_target).parent)

    with ExperimentDB(db_target, engine=str(args.db_engine)) as db:
        db.init_schema()

        # Run selection / creation
        run_id = str(args.run_id).strip()
        if args.resume:
            if run_id:
                if not db.run_exists(run_id):
                    raise RuntimeError(f"--resume but run_id not found: {run_id}")
                db.ensure_run_problem_hash(run_id, problem_hash)
            else:
                run_id = db.find_latest_run(problem_hash) or ""
                if not run_id:
                    raise RuntimeError("--resume requested but no existing run found for this problem")
                db.ensure_run_problem_hash(run_id, problem_hash)
        else:
            run_id = db.create_run(
                problem_hash=problem_hash,
                spec=problem_spec.to_dict(),
                meta=build_run_record_meta(
                    args,
                    objective_keys=objective_keys,
                    problem_hash_mode=problem_hash_mode,
                ),
            )

        # Run dir
        run_dir = Path(args.run_dir) if args.run_dir else Path(_abs_under(base_dir, f"runs/run_{run_id}"))
        _ensure_dir(run_dir)

        _dump_json(run_dir / "problem_spec.json", problem_spec.to_dict())
        _write_text(run_dir / "problem_hash.txt", problem_hash)
        write_problem_hash_mode_artifact(run_dir, problem_hash_mode)
        _write_text(run_dir / "run_id.txt", run_id)
        write_baseline_source_artifact(
            run_dir,
            resolve_workspace_baseline_source(
                problem_hash=problem_hash,
                env=os.environ,
            ),
        )
        _dump_json(
            run_dir / "objective_contract.json",
            objective_contract_payload(
                objective_keys=objective_keys,
                penalty_key=str(args.penalty_key),
                penalty_tol=float(args.penalty_tol),
                source="dist_opt_coordinator_R59",
            ),
        )

        # Coordinator-side core for param mapping (fast)
        apply_problem_hash_env(problem_hash)
        core_local = EvaluatorCore(
            model_path=model_rel,
            worker_path=worker_rel,
            base_json=base_json_rel or None,
            ranges_json=ranges_json_rel or None,
            suite_json=suite_json_rel or None,
            cfg=spec_cfg,
        )

        if args.backend == "ray":
            _run_ray(
                args,
                core_local=core_local,
                db=db,
                run_id=run_id,
                run_dir=run_dir,
                problem_hash=problem_hash,
                objective_keys=objective_keys,
            )
        else:
            _run_dask(
                args,
                core_local=core_local,
                db=db,
                run_id=run_id,
                run_dir=run_dir,
                problem_hash=problem_hash,
                objective_keys=objective_keys,
            )

        print(f"DONE. Export in: {run_dir / 'export'}")


if __name__ == "__main__":
    main()
