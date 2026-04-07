#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_ray_distributed_opt.py (R57)

Ray-based distributed evaluator for simulation-driven multi-objective optimization.

Why this exists
---------------
- Evaluation (simulation) is expensive and CPU-heavy -> parallelize across CPUs / PCs.
- Candidate proposal (MOBO with BoTorch) can use 1+ GPUs on the coordinator.
- We want reproducibility + dedup -> ExperimentDB (sqlite/duckdb) tracks everything.

This script is intentionally CLI-first. A Streamlit page can read the DB for
monitoring, but the coordinator should stay in CLI.

Usage (local, single PC)
------------------------
  python pneumo_solver_ui/tools/run_ray_distributed_opt.py \
    --model model_pneumo_v8_energy_audit_vacuum.py \
    --worker pneumo_solver_ui/opt_worker_v3_margins_energy.py \
    --budget 400 --num-workers 8 --queue-target 24 --botorch

Usage (multi-PC)
----------------
1) Start head:
     ray start --head --port=6379
2) Start workers on other PCs (point to head IP):
     ray start --address=<HEAD_IP>:6379
3) Run coordinator:
     python pneumo_solver_ui/tools/run_ray_distributed_opt.py --ray-address <HEAD_IP>:6379 ...

Notes
-----
- For multi-PC, either copy this repo to every machine OR use --ship-code to let
  Ray upload working_dir (simplest but can be heavy).

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# Ensure repo root is on sys.path even when called as a file.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _now_ts() -> float:
    return float(time.time())


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401

        return True
    except Exception:
        return False


def _make_run_id(prefix: str, problem_hash: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}_{problem_hash[:8]}"


def _parse_devices(s: str) -> List[str]:
    s = (s or "auto").strip()
    if s.lower() in ("auto", ""):
        return ["auto"]
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts if parts else ["auto"]


def main() -> int:
    db = None  # ExperimentDB (init later)
    token = None  # RunToken (init later)
    ap = argparse.ArgumentParser()

    ap.add_argument("--model", required=True, help="Path to model .py")
    ap.add_argument("--worker", default=str(REPO_ROOT / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py"), help="Path to opt_worker .py")
    ap.add_argument("--base-json", default=None)
    ap.add_argument("--ranges-json", default=None)
    ap.add_argument("--suite-json", default=None)

    ap.add_argument("--budget", type=int, default=200, help="Total number of completed (done+cached) trials")
    ap.add_argument("--num-workers", type=int, default=8, help="Number of Ray evaluator actors")
    ap.add_argument("--queue-target", type=int, default=24, help="Desired in-flight evaluations")

    ap.add_argument("--ray-address", default=None, help="Ray cluster address, e.g. 192.168.0.10:6379")
    ap.add_argument("--ship-code", action="store_true", help="Use Ray runtime_env working_dir=repo root (helps multi-PC)")

    ap.add_argument("--out-dir", default=None, help="Run directory. If omitted -> runs/dist_runs/")
    ap.add_argument("--resume", action="store_true", help="Resume existing run-dir (expects run_config.json + DB)")

    ap.add_argument("--stop-file", default="STOP_DIST_OPT.txt", help="If exists in run_dir -> graceful stop")
    ap.add_argument("--ttl-sec", type=float, default=900.0, help="Requeue RUNNING trials with heartbeat older than TTL")
    ap.add_argument("--requeue-errors", action="store_true", help="Also requeue ERROR trials with attempt < max-attempt")
    ap.add_argument("--max-attempt", type=int, default=3)

    # eval cfg (matches worker defaults)
    ap.add_argument("--dt", type=float, default=0.003)
    ap.add_argument("--t-end-short", type=float, default=1.2)
    ap.add_argument("--t-end-micro", type=float, default=1.6)
    ap.add_argument("--t-end-inertia", type=float, default=1.2)
    ap.add_argument("--t-step", type=float, default=0.4)
    ap.add_argument("--settle-band-min-deg", type=float, default=0.5)
    ap.add_argument("--settle-band-ratio", type=float, default=0.20)

    # proposer
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-init", type=int, default=24)
    ap.add_argument("--botorch", action="store_true", help="Enable BoTorch proposer")
    ap.add_argument("--proposer-devices", default="auto", help="Comma-separated devices for proposer, e.g. cuda:0,cuda:1")
    ap.add_argument("--feasible-tol", type=float, default=1e-9)
    ap.add_argument("--min-feasible", type=int, default=8)
    ap.add_argument("--no-constraints", action="store_true", help="Disable constraint modeling")

    args = ap.parse_args()

    from pneumo_solver_ui.run_registry import end_run, env_context, start_run
    from pneumo_solver_ui.pneumo_dist.eval_core import Evaluator
    from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
    from pneumo_solver_ui.pneumo_dist.hv_tools import hypervolume_from_min
    from pneumo_solver_ui.pneumo_dist.mobo_propose import ProposeOptions, propose_next
    from pneumo_solver_ui.pneumo_dist.trial_hash import stable_hash_params, stable_hash_problem

    model_py = str(Path(args.model))
    worker_py = str(Path(args.worker))

    cfg_extra = {
        "dt": float(args.dt),
        "t_end_short": float(args.t_end_short),
        "t_end_micro": float(args.t_end_micro),
        "t_end_inertia": float(args.t_end_inertia),
        "t_step": float(args.t_step),
        "settle_band_min_deg": float(args.settle_band_min_deg),
        "settle_band_ratio": float(args.settle_band_ratio),
    }

    # Evaluator (local) for dimension and param order
    evaluator_local = Evaluator(
        model_py=model_py,
        worker_py=worker_py,
        base_json=args.base_json,
        ranges_json=args.ranges_json,
        suite_json=args.suite_json,
        cfg_extra=cfg_extra,
    )

    # Hash the full problem definition
    problem_hash = stable_hash_problem(
        model_py=model_py,
        worker_py=worker_py,
        base=evaluator_local.base,
        ranges={k: list(v) for k, v in evaluator_local.ranges.items()},
        suite=evaluator_local.suite,
        extra={
            "cfg": cfg_extra,
            "objectives": ["obj1", "obj2"],
            "constraint": "penalty<=tol",
            "release": "R57",
        },
    )

    # Resolve run_dir
    if args.out_dir:
        run_dir = Path(args.out_dir)
    else:
        run_dir = REPO_ROOT / "runs" / "dist_runs" / _make_run_id("DIST_RAY", problem_hash)

    run_dir.mkdir(parents=True, exist_ok=True)

    # DB path
    db_path = run_dir / ("experiments.duckdb" if _duckdb_available() else "experiments.sqlite")

    # Resume logic
    run_id = None
    if args.resume:
        cfg_path = run_dir / "run_config.json"
        if cfg_path.exists():
            try:
                prev = _read_json(cfg_path)
                run_id = str(prev.get("run_id") or "")
                prev_ph = str(prev.get("problem_hash") or "")
                if prev_ph and prev_ph != problem_hash:
                    print("WARNING: problem_hash differs from run_config.json; using current hash")
            except Exception:
                run_id = None
        if not run_id:
            run_id = _make_run_id("DIST_RAY", problem_hash)
    else:
        run_id = _make_run_id("DIST_RAY", problem_hash)

    # Save run_config.json
    _write_json_atomic(
        run_dir / "run_config.json",
        {
            "release": "R57",
            "run_id": run_id,
            "problem_hash": problem_hash,
            "model_py": model_py,
            "worker_py": worker_py,
            "base_json": args.base_json,
            "ranges_json": args.ranges_json,
            "suite_json": args.suite_json,
            "cfg_extra": cfg_extra,
            "budget": int(args.budget),
            "num_workers": int(args.num_workers),
            "queue_target": int(args.queue_target),
            "seed": int(args.seed),
            "n_init": int(args.n_init),
            "botorch": bool(args.botorch),
            "proposer_devices": str(args.proposer_devices),
            "feasible_tol": float(args.feasible_tol),
            "min_feasible": int(args.min_feasible),
            "use_constraints": (not bool(args.no_constraints)),
            "ray_address": args.ray_address,
            "ship_code": bool(args.ship_code),
        },
    )

    # Start run registry
    token = start_run(
        run_type="dist_ray_opt",
        run_dir=str(run_dir),
        meta={
            "run_id": run_id,
            "problem_hash": problem_hash,
            "db_path": str(db_path),
            "ray_address": args.ray_address,
            "num_workers": int(args.num_workers),
            "queue_target": int(args.queue_target),
        },
        env=env_context(),
    )

    # Experiment DB
    db = ExperimentDB(str(db_path))
    db.connect()
    db.init_schema()

    # Create run row if not exists
    try:
        db.add_run(run_id=run_id, problem_hash=problem_hash, meta={"run_dir": str(run_dir)}, status="running")
    except Exception:
        # already exists
        pass

    # Ray init
    try:
        import ray  # type: ignore

        runtime_env = None
        if bool(args.ship_code):
            runtime_env = {"working_dir": str(REPO_ROOT)}
        if args.ray_address:
            ray.init(address=str(args.ray_address), ignore_reinit_error=True, runtime_env=runtime_env)
        else:
            ray.init(ignore_reinit_error=True, runtime_env=runtime_env)
    except Exception as e:
        end_run(token, status="error", error=f"Ray init failed: {e}")
        raise

    from pneumo_solver_ui.pneumo_dist.eval_core import evaluate_xu_to_row

    # Remote evaluator actor
    import ray  # type: ignore

    @ray.remote(num_cpus=1)
    class EvalActor:
        def __init__(self, actor_id: str, model_py: str, worker_py: str, base_json: Optional[str], ranges_json: Optional[str], suite_json: Optional[str], cfg_extra: Dict[str, Any]):
            self.actor_id = actor_id
            self.evaluator = Evaluator(
                model_py=model_py,
                worker_py=worker_py,
                base_json=base_json,
                ranges_json=ranges_json,
                suite_json=suite_json,
                cfg_extra=cfg_extra,
            )

        def evaluate(self, trial_id: int, param_hash: str, x_u: List[float], idx: int) -> Dict[str, Any]:
            return evaluate_xu_to_row(self.evaluator, trial_id=int(trial_id), param_hash=str(param_hash), x_u=list(x_u), worker_id=str(self.actor_id), idx=int(idx))

        def ping(self) -> str:
            return "ok"

    # create actors
    actors = [EvalActor.remote(f"ray_worker_{i}", model_py, worker_py, args.base_json, args.ranges_json, args.suite_json, cfg_extra) for i in range(int(args.num_workers))]

    # ping actors
    try:
        ray.get([a.ping.remote() for a in actors])
    except Exception as e:
        print("WARNING: some actors failed to start:", e)

    # Proposer options
    popt = ProposeOptions(
        method="botorch" if args.botorch else "auto",
        seed=int(args.seed),
        n_init=int(args.n_init),
        allow_botorch=bool(args.botorch),
        feasible_tol=float(args.feasible_tol),
        min_feasible_for_mobo=int(args.min_feasible),
        use_constraints=(not bool(args.no_constraints)),
    )

    proposer_devices = _parse_devices(args.proposer_devices)

    # Resume maintenance
    if args.resume:
        try:
            rc = db.requeue_stale_trials(run_id, ttl_sec=float(args.ttl_sec), max_attempt=int(args.max_attempt))
            if rc:
                print(f"Requeued stale RUNNING trials: {rc}")
        except Exception as e:
            print("WARNING: requeue stale trials failed:", e)

    # State
    budget = int(args.budget)
    queue_target = max(1, int(args.queue_target))

    inflight: Dict[Any, Tuple[int, str, List[float]]] = {}
    submitted = 0

    # Completed counts include cached + done (not error)
    def _count_completed() -> int:
        st = db.count_status(run_id)
        return int(st.get("done", 0) + st.get("cached", 0))

    def _count_feasible() -> int:
        # from dataset arrays
        X_u, Y_min, pen = db.fetch_dataset_arrays(run_id)
        if pen.size == 0:
            return 0
        return int(np.sum(np.isfinite(pen) & (pen <= float(popt.feasible_tol))))

    last_metric_ts = 0.0
    last_maint_ts = 0.0

    progress_path = run_dir / "progress.json"

    def _update_progress(status: str, msg: str = "") -> None:
        st = db.count_status(run_id)
        completed = int(st.get("done", 0) + st.get("cached", 0))
        X_u, Y_min, pen = db.fetch_dataset_arrays(run_id)
        hv = float("nan")
        try:
            hv = float(hypervolume_from_min(Y_min, pen, feasible_tol=float(popt.feasible_tol), normalize=True))
        except Exception:
            hv = float("nan")

        _write_json_atomic(
            progress_path,
            {
                "ts": _now_ts(),
                "status": status,
                "message": msg,
                "run_id": run_id,
                "problem_hash": problem_hash,
                "db_path": str(db_path),
                "completed": completed,
                "submitted": int(submitted),
                "inflight": int(len(inflight)),
                "status_counts": st,
                "n_feasible": _count_feasible(),
                "hypervolume_norm": hv,
            },
        )

    _update_progress("running", "started")

    try:
        while True:
            completed = _count_completed()
            if completed >= budget:
                break

            # stop file
            if (run_dir / str(args.stop_file)).exists():
                print("Stop file detected -> stopping")
                break

            # periodic maintenance: requeue stale
            if _now_ts() - last_maint_ts > 30.0:
                last_maint_ts = _now_ts()
                try:
                    db.requeue_stale_trials(run_id, ttl_sec=float(args.ttl_sec), max_attempt=int(args.max_attempt))
                    if bool(args.requeue_errors):
                        db._execute(
                            """
                            UPDATE trials
                            SET status='reserved', worker_id=NULL, started_ts=NULL, heartbeat_ts=NULL
                            WHERE run_id=? AND status='error' AND COALESCE(attempt,0) < ?;
                            """,
                            (str(run_id), int(args.max_attempt)),
                        )
                        db.commit()
                except Exception:
                    pass

            # fill queue
            fill_guard = 0
            while len(inflight) < queue_target and completed + len(inflight) < budget and fill_guard < 200:
                fill_guard += 1

                # dataset for proposer
                X_hist, Y_hist, pen_hist = db.fetch_dataset_arrays(run_id)

                # choose device round-robin
                dev = proposer_devices[(submitted + len(inflight)) % len(proposer_devices)]
                popt.device = dev

                # propose
                x_next, info = propose_next(X_u=X_hist, Y_min=Y_hist, penalty=pen_hist, opt=popt, bounds_u=evaluator_local.bounds_u(), X_pending=np.asarray([v[2] for v in inflight.values()], dtype=float) if inflight else None)

                # hash candidate
                xq = [float(round(float(v), 12)) for v in np.asarray(x_next, dtype=float).reshape(-1).tolist()]
                param_hash = stable_hash_params({"x_u": xq, "problem_hash": problem_hash})

                # check global cache
                cached = db.get_cached(problem_hash, param_hash)

                # build params for storage
                params_partial = evaluator_local.denormalize(xq)

                trial_id, inserted = db.reserve_trial(
                    run_id=run_id,
                    problem_hash=problem_hash,
                    param_hash=param_hash,
                    params=params_partial,
                    x_u=xq,
                    source="cache" if cached else "propose",
                )

                if not inserted:
                    # duplicate within run -> propose again
                    continue

                if cached:
                    # write cached result
                    db.mark_done(
                        trial_id,
                        metrics=cached.get("metrics", {}),
                        obj1=float(cached.get("obj1", float("nan"))),
                        obj2=float(cached.get("obj2", float("nan"))),
                        penalty=float(cached.get("penalty", float("nan"))),
                        status="cached",
                    )
                    completed = _count_completed()
                    continue

                # dispatch
                actor = actors[(submitted + len(inflight)) % len(actors)]
                worker_id = f"ray_actor_{(submitted + len(inflight)) % len(actors)}"
                db.mark_started(trial_id, worker_id)

                fut = actor.evaluate.remote(trial_id, param_hash, xq, int(trial_id))
                inflight[fut] = (trial_id, param_hash, xq)
                submitted += 1

            # wait for results
            if inflight:
                done, pending = ray.wait(list(inflight.keys()), num_returns=1, timeout=2.0)
                if not done:
                    _update_progress("running", "waiting")
                    continue

                fut = done[0]
                trial_id, param_hash, xq = inflight.pop(fut)

                # get result
                try:
                    res = ray.get(fut)
                except Exception as e:
                    db.mark_error(trial_id, error=str(e), traceback_str=traceback.format_exc())
                    _update_progress("running", f"trial {trial_id} error")
                    continue

                if isinstance(res, dict) and res.get("status") == "done":
                    obj1 = float(res.get("obj1", float("nan")))
                    obj2 = float(res.get("obj2", float("nan")))
                    pen = float(res.get("penalty", float("nan")))
                    metrics = res.get("metrics", {}) if isinstance(res.get("metrics", {}), dict) else {"metrics": res.get("metrics")}

                    db.mark_done(trial_id, metrics=metrics, obj1=obj1, obj2=obj2, penalty=pen, status="done")
                    # store to cache for future runs
                    try:
                        db.put_cache(problem_hash, param_hash, metrics=metrics, obj1=obj1, obj2=obj2, penalty=pen)
                    except Exception:
                        pass
                else:
                    db.mark_error(trial_id, error=str(res.get("error") if isinstance(res, dict) else "worker_error"), traceback_str=str(res.get("traceback") if isinstance(res, dict) else ""))

            # metrics tick
            if _now_ts() - last_metric_ts > 5.0:
                last_metric_ts = _now_ts()
                try:
                    st = db.count_status(run_id)
                    completed = int(st.get("done", 0) + st.get("cached", 0))
                    X_h, Y_h, p_h = db.fetch_dataset_arrays(run_id)
                    hv = float(hypervolume_from_min(Y_h, p_h, feasible_tol=float(popt.feasible_tol), normalize=True))
                    best1 = float(np.nanmin(Y_h[:, 0])) if Y_h.size else float("nan")
                    best2 = float(np.nanmin(Y_h[:, 1])) if Y_h.size else float("nan")
                    n_feas = int(np.sum(np.isfinite(p_h) & (p_h <= float(popt.feasible_tol)))) if p_h.size else 0
                    db.add_metric(
                        run_id,
                        completed=completed,
                        submitted=int(submitted),
                        n_feasible=n_feas,
                        hypervolume=hv,
                        best_obj1=best1,
                        best_obj2=best2,
                        info={"inflight": int(len(inflight))},
                    )
                except Exception:
                    pass

                _update_progress("running", "tick")

        # end loop
        db.update_run_status(run_id, "done")
        _update_progress("done", "completed")
        end_run(token, status="done")
        return 0

    except KeyboardInterrupt:
        try:
            if db is not None and "run_id" in locals():
                db.update_run_status(run_id, "stopped")
        except Exception:
            pass
        _update_progress("stopped", "KeyboardInterrupt")
        try:
            if token is not None:
                end_run(token, status="stopped", error="KeyboardInterrupt")
        except Exception:
            pass
        return 130

    except Exception as e:
        try:
            if db is not None and "run_id" in locals():
                db.update_run_status(run_id, "error", error=str(e))
        except Exception:
            pass
        _update_progress("error", str(e))
        try:
            if token is not None:
                end_run(token, status="error", error=str(e))
        except Exception:
            pass
        print("FATAL:", e)
        print(traceback.format_exc())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
