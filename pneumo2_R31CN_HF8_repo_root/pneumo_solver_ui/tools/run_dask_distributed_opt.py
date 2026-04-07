#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_dask_distributed_opt.py (R57)

Dask-based distributed evaluator for simulation-driven multi-objective optimization.

This is an alternative to the Ray coordinator. Some teams already run a Dask
scheduler/worker stack (e.g., on a cluster). The logic mirrors the Ray runner:
- ExperimentDB for dedup + resume
- BoTorch proposer on coordinator (optional GPU)
- Distributed evaluation via `client.submit` with `as_completed`.

Important: Dask workers must have the same project code + dependencies available.

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
from typing import Any, Dict, List, Optional

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


def _duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401

        return True
    except Exception:
        return False


def main() -> int:
    db = None
    token = None

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", default=str(REPO_ROOT / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py"))
    ap.add_argument("--base-json", default=None)
    ap.add_argument("--ranges-json", default=None)
    ap.add_argument("--suite-json", default=None)

    ap.add_argument("--scheduler", default=None, help="Dask scheduler address, e.g. tcp://127.0.0.1:8786")
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--num-workers", type=int, default=8)
    ap.add_argument("--queue-target", type=int, default=24)

    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--resume", action="store_true")

    ap.add_argument("--ttl-sec", type=float, default=600.0)
    ap.add_argument("--requeue-errors", action="store_true")
    ap.add_argument("--max-attempt", type=int, default=3)

    ap.add_argument("--dt", type=float, default=0.003)
    ap.add_argument("--t-end-short", type=float, default=1.2)
    ap.add_argument("--t-end-micro", type=float, default=1.6)
    ap.add_argument("--t-end-inertia", type=float, default=1.2)
    ap.add_argument("--t-step", type=float, default=0.4)
    ap.add_argument("--settle-band-min-deg", type=float, default=0.5)
    ap.add_argument("--settle-band-ratio", type=float, default=0.20)

    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-init", type=int, default=24)
    ap.add_argument("--botorch", action="store_true")
    ap.add_argument("--proposer-devices", default="auto")
    ap.add_argument("--feasible-tol", type=float, default=1e-9)
    ap.add_argument("--min-feasible", type=int, default=8)
    ap.add_argument("--no-constraints", action="store_true")

    args = ap.parse_args()

    from pneumo_solver_ui.run_registry import end_run, env_context, start_run
    from pneumo_solver_ui.pneumo_dist.eval_core import Evaluator, evaluate_xu_to_row
    from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
    from pneumo_solver_ui.pneumo_dist.hv_tools import hypervolume_from_min
    from pneumo_solver_ui.pneumo_dist.mobo_propose import ProposeOptions, propose_next
    from pneumo_solver_ui.pneumo_dist.trial_hash import stable_hash_params, stable_hash_problem

    cfg_extra = {
        "dt": float(args.dt),
        "t_end_short": float(args.t_end_short),
        "t_end_micro": float(args.t_end_micro),
        "t_end_inertia": float(args.t_end_inertia),
        "t_step": float(args.t_step),
        "settle_band_min_deg": float(args.settle_band_min_deg),
        "settle_band_ratio": float(args.settle_band_ratio),
    }

    model_py = str(Path(args.model))
    worker_py = str(Path(args.worker))

    evaluator_local = Evaluator(
        model_py=model_py,
        worker_py=worker_py,
        base_json=args.base_json,
        ranges_json=args.ranges_json,
        suite_json=args.suite_json,
        cfg_extra=cfg_extra,
    )

    problem_hash = stable_hash_problem(
        model_py=model_py,
        worker_py=worker_py,
        base=evaluator_local.base,
        ranges=evaluator_local.ranges,
        suite=evaluator_local.suite,
        extra={"cfg_extra": cfg_extra, "runner": "dask", "release": "R57"},
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out_dir:
        run_dir = Path(args.out_dir)
    else:
        run_dir = REPO_ROOT / "runs" / "dist_runs" / f"DIST_DASK_{ts}_{problem_hash[:8]}"

    run_dir.mkdir(parents=True, exist_ok=True)
    stop_file = run_dir / "STOP_DISTRIBUTED.txt"
    progress_path = run_dir / "progress.json"
    cfg_path = run_dir / "run_config.json"

    if args.resume:
        if cfg_path.exists():
            cfg_prev = json.loads(cfg_path.read_text(encoding="utf-8"))
            run_id = str(cfg_prev.get("run_id", f"DIST_DASK_{ts}_{problem_hash[:8]}"))
        else:
            run_id = f"DIST_DASK_{ts}_{problem_hash[:8]}"
    else:
        run_id = f"DIST_DASK_{ts}_{problem_hash[:8]}"

    db_path = run_dir / ("experiments.duckdb" if _duckdb_available() else "experiments.sqlite")

    _write_json_atomic(
        cfg_path,
        {
            "release": "R57",
            "run_id": run_id,
            "problem_hash": problem_hash,
            "runner": "dask",
            "db_path": str(db_path),
            "model": model_py,
            "worker": worker_py,
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
            "scheduler": args.scheduler,
        },
    )

    token = start_run(
        run_type="dist_dask_opt",
        run_dir=str(run_dir),
        meta={
            "run_id": run_id,
            "problem_hash": problem_hash,
            "db_path": str(db_path),
            "scheduler": args.scheduler,
            "num_workers": int(args.num_workers),
            "queue_target": int(args.queue_target),
        },
        env=env_context(),
    )

    db = ExperimentDB(str(db_path))
    db.connect()
    db.init_schema()
    try:
        db.add_run(run_id=run_id, problem_hash=problem_hash, meta={"run_dir": str(run_dir)}, status="running")
    except Exception:
        pass

    # Dask client
    try:
        from dask.distributed import Client, as_completed  # type: ignore

        client = Client(address=args.scheduler) if args.scheduler else Client()
    except Exception as e:
        try:
            end_run(token, status="error", error=f"Dask init failed: {e}")
        except Exception:
            pass
        raise

    proposer_devices = [p.strip() for p in str(args.proposer_devices).split(",") if p.strip()] or ["auto"]

    popt = ProposeOptions(
        method="auto",
        allow_botorch=bool(args.botorch),
        device="auto",
        q=1,
        num_restarts=8,
        raw_samples=64,
        seed=int(args.seed),
        feasible_tol=float(args.feasible_tol),
        min_feasible=int(args.min_feasible),
        use_constraint_model=(not bool(args.no_constraints)),
        n_init=int(args.n_init),
    )

    inflight = {}
    submitted = 0
    last_metric_ts = _now_ts()

    def _update_progress(status: str, note: str = "") -> None:
        try:
            st = db.count_status(run_id)
            _write_json_atomic(
                progress_path,
                {
                    "status": status,
                    "note": note,
                    "run_id": run_id,
                    "problem_hash": problem_hash,
                    "ts": _now_ts(),
                    "counts": st,
                    "inflight": int(len(inflight)),
                    "submitted": int(submitted),
                    "stop_file": str(stop_file),
                    "db_path": str(db_path),
                },
            )
        except Exception:
            pass

    def _count_completed() -> int:
        st = db.count_status(run_id)
        return int(st.get("done", 0) + st.get("cached", 0))

    try:
        _update_progress("running", "started")

        # as_completed helper
        ac = as_completed([])

        while True:
            if stop_file.exists():
                break

            # resume support
            if args.resume:
                try:
                    if args.ttl_sec > 0:
                        db.requeue_stale_trials(run_id, ttl_sec=float(args.ttl_sec), max_attempt=int(args.max_attempt))
                    if args.requeue_errors:
                        db._execute(
                            "UPDATE trials SET status='reserved', worker_id=NULL, started_ts=NULL, heartbeat_ts=NULL WHERE run_id=? AND status='error' AND COALESCE(attempt,0) < ?",
                            (run_id, int(args.max_attempt)),
                        )
                        db.commit()
                except Exception:
                    pass

            completed = _count_completed()
            if completed >= int(args.budget):
                break

            # fill queue
            fill_guard = 0
            while len(inflight) < int(args.queue_target) and completed + len(inflight) < int(args.budget) and fill_guard < 200:
                fill_guard += 1
                X_hist, Y_hist, pen_hist = db.fetch_dataset_arrays(run_id)

                dev = proposer_devices[(submitted + len(inflight)) % len(proposer_devices)]
                popt.device = dev

                x_next, info = propose_next(
                    X_u=X_hist,
                    Y_min=Y_hist,
                    penalty=pen_hist,
                    opt=popt,
                    bounds_u=evaluator_local.bounds_u(),
                    X_pending=np.asarray([v[2] for v in inflight.values()], dtype=float) if inflight else None,
                )

                xq = [float(round(float(v), 12)) for v in np.asarray(x_next, dtype=float).reshape(-1).tolist()]
                param_hash = stable_hash_params({"x_u": xq, "problem_hash": problem_hash})

                cached = db.get_cached(problem_hash, param_hash)
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
                    continue

                if cached:
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

                worker_id = f"dask_worker_{(submitted + len(inflight)) % int(args.num_workers)}"
                db.mark_started(trial_id, worker_id)

                fut = client.submit(_dask_eval_wrapper, model_py, worker_py, args.base_json, args.ranges_json, args.suite_json, cfg_extra, trial_id, param_hash, xq, int(trial_id), pure=False)
                inflight[fut] = (trial_id, param_hash, xq)
                submitted += 1
                ac.add(fut)

            # wait for one completion
            if inflight:
                try:
                    fut = next(ac)
                except StopIteration:
                    time.sleep(0.2)
                    continue

                trial_id, param_hash, xq = inflight.pop(fut, (None, None, None))
                if trial_id is None:
                    continue

                try:
                    res = fut.result()
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

        db.update_run_status(run_id, "done")
        _update_progress("done", "completed")
        try:
            if token is not None:
                end_run(token, status="done")
        except Exception:
            pass
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


def _dask_eval_wrapper(model_py: str, worker_py: str, base_json: Optional[str], ranges_json: Optional[str], suite_json: Optional[str], cfg_extra: Dict[str, Any], trial_id: int, param_hash: str, x_u: List[float], idx: int) -> Dict[str, Any]:
    """Worker-side wrapper.

    Dask will serialize this function + args to a worker process.
    The worker must have project code installed/available.
    """

    from pneumo_solver_ui.pneumo_dist.eval_core import Evaluator, evaluate_xu_to_row

    ev = Evaluator(
        model_py=model_py,
        worker_py=worker_py,
        base_json=base_json,
        ranges_json=ranges_json,
        suite_json=suite_json,
        cfg_extra=cfg_extra,
    )
    return evaluate_xu_to_row(ev, x_u=x_u, trial_id=trial_id, param_hash=param_hash, idx=idx)


if __name__ == "__main__":
    raise SystemExit(main())
