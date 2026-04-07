# -*- coding: utf-8 -*-
"""Distributed optimization runner (Ray) — async / multi-PC.

This script is a *coordinator*:
- connects to a Ray cluster (local or multi-PC),
- proposes candidates (LHS warmup + optional BoTorch MOBO),
- dispatches expensive evaluations to evaluator actors,
- writes all results into a single ExperimentDB (DuckDB/SQLite),
- computes hypervolume progress and stores progress.json (+ DB metrics).

Key design choice
-----------------
To keep DuckDB/SQLite safe on Windows, we use **single-writer DB**:
only the coordinator writes to the DB file. Evaluator actors return results.

Resume
------
Use --resume --run-id <id> to continue a previous run in the same DB.

GPU
---
If you have GPUs and BoTorch+PyTorch installed, you can run one or more
proposer actors on GPUs to offload GP fitting / acquisition optimization.

Example (single PC):
  python tools/run_ray_distributed_async.py --address local ^
    --model ..\\pneumo_v7\\pneumo_model.py ^
    --budget 300 --num-evaluators 8 --use-botorch --proposer-actors 1

Example (multi-PC):
  # head:
  ray start --head --port=6379
  # workers:
  ray start --address=<HEAD_IP>:6379
  # coordinator on head:
  python tools/run_ray_distributed_async.py --address auto --budget 1000 --use-botorch

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Make `pneumo_solver_ui` importable when running as a script
THIS = Path(__file__).resolve()
ROOT = THIS.parents[1]  # pneumo_solver_ui
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pneumo_dist.eval_core import Evaluator
from pneumo_dist.expdb import ExperimentDB
from pneumo_dist.hv_tools import hv_progress
from pneumo_dist.mobo_propose import ProposeOptions, propose_next
from pneumo_dist.trial_hash import stable_hash_params, stable_hash_problem


def _ts_str() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _progress_summary(Y_min: np.ndarray, penalty: np.ndarray, feasible_tol: float) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "n_done": int(len(Y_min)),
        "n_feasible": 0,
        "best_obj1": None,
        "best_obj2": None,
        "hypervolume": None,
    }
    if len(Y_min) == 0:
        return out

    feas = np.isfinite(penalty) & (penalty <= float(feasible_tol))
    out["n_feasible"] = int(np.sum(feas))

    if np.any(feas):
        yy = Y_min[feas]
        out["best_obj1"] = float(np.nanmin(yy[:, 0]))
        out["best_obj2"] = float(np.nanmin(yy[:, 1]))

    hv = hv_progress(Y_min, penalty, feasible_tol=float(feasible_tol), scale=0.1, normalize=True)
    out["hypervolume"] = None if (hv is None or not np.isfinite(hv)) else float(hv)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", default="auto", help="Ray cluster address: auto|local|<ip>:<port>")

    ap.add_argument("--model", required=True, help="Path to pneumo_model.py")
    ap.add_argument(
        "--worker",
        default=str((ROOT / "opt_worker_v3_margins_energy.py").resolve()),
        help="Path to opt_worker_*.py used for evaluation core",
    )
    ap.add_argument("--base-json", default="", help="Override base JSON path")
    ap.add_argument("--ranges-json", default="", help="Override ranges JSON path")
    ap.add_argument("--suite-json", default="", help="Override suite JSON path")

    ap.add_argument("--db", default="", help="DB path (*.duckdb or *.sqlite). Default: <out_dir>/experiments.duckdb")
    ap.add_argument("--out-dir", default="", help="Run directory. Default: runs/dist_ray_<ts>")
    ap.add_argument("--run-id", default="", help="Run ID. Default: dist_ray_<ts>")

    ap.add_argument("--resume", action="store_true", help="Resume an existing run (requires --run-id and existing DB)")
    ap.add_argument("--resume-requeue-ttl", type=float, default=3600.0, help="Requeue RUNNING trials older than TTL (sec)")

    ap.add_argument("--budget", type=int, default=200, help="Number of NEW completed evals to add in this run")
    ap.add_argument("--num-evaluators", type=int, default=0, help="Number of evaluator actors (default: auto)")
    ap.add_argument("--queue-target", type=int, default=0, help="Max pending tasks (default: 2*num_evaluators)")

    ap.add_argument("--n-init", type=int, default=24, help="LHS warmup count before MOBO")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--feasible-tol", type=float, default=1e-9, help="Penalty threshold for feasibility")

    ap.add_argument("--use-botorch", action="store_true", help="Enable BoTorch proposer if installed")
    ap.add_argument("--proposer-on-gpu", action="store_true", help="Run proposer as Ray actor with num_gpus=1")
    ap.add_argument("--proposer-actors", type=int, default=0, help="Number of GPU proposer actors (uses all if >0)")
    ap.add_argument("--proposer-prefetch", type=int, default=0, help="Prefetch proposals (default: proposer_actors)")

    ap.add_argument("--progress-every", type=int, default=10, help="Write progress.json every N NEW completed trials")

    args = ap.parse_args()

    model_py = str(Path(args.model).resolve())
    worker_py = str(Path(args.worker).resolve())
    if not Path(model_py).exists():
        raise SystemExit(f"Model not found: {model_py}")
    if not Path(worker_py).exists():
        raise SystemExit(f"Worker not found: {worker_py}")

    out_dir = args.out_dir.strip() or str((ROOT / "runs" / f"dist_ray_{_ts_str()}").resolve())
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    run_id = args.run_id.strip() or f"dist_ray_{_ts_str()}"
    db_path = args.db.strip() or str(Path(out_dir) / "experiments.duckdb")

    # ---------- DB ----------
    db = ExperimentDB(db_path)
    db.init_schema()

    # Coordinator-side evaluator (for ranges + denormalize + hashes)
    ev0 = Evaluator(
        model_py=model_py,
        worker_py=worker_py,
        base_json=args.base_json or None,
        ranges_json=args.ranges_json or None,
        suite_json=args.suite_json or None,
    )

    problem_hash = stable_hash_problem(
        model_py=model_py,
        worker_py=worker_py,
        base=ev0.base,
        ranges=ev0.ranges,
        suite=ev0.suite,
        extra={"runner": "ray", "version": "R55"},
    )

    meta = {
        "runner": "ray",
        "model_py": model_py,
        "worker_py": worker_py,
        "base_json": args.base_json,
        "ranges_json": args.ranges_json,
        "suite_json": args.suite_json,
        "seed": int(args.seed),
        "n_init": int(args.n_init),
        "use_botorch": bool(args.use_botorch),
        "proposer_on_gpu": bool(args.proposer_on_gpu),
        "proposer_actors": int(args.proposer_actors),
    }

    # Resume safety: check run existence + problem_hash consistency.
    if args.resume:
        if not args.run_id:
            raise SystemExit("--resume requires --run-id")
        run_meta = db.get_run(run_id)
        if not run_meta:
            raise SystemExit(f"Run not found in DB: {run_id}")
        if str(run_meta.get("problem_hash", "")) != str(problem_hash):
            raise SystemExit(
                "Problem hash mismatch for resume.\n"
                f"DB has:  {run_meta.get('problem_hash')}\n"
                f"Now is:  {problem_hash}\n"
                "Start a new run-id if model/base/ranges/suite changed."
            )
        db.update_run_status(run_id, status="running")
        # Requeue stale running trials (best-effort)
        db.requeue_stale_trials(run_id, ttl_sec=float(args.resume_requeue_ttl))
    else:
        db.add_run(run_id, problem_hash=problem_hash, meta=meta, status="running")

    _write_json(Path(out_dir) / "run_config.json", {"run_id": run_id, "problem_hash": problem_hash, **meta})

    # ---------- Ray init ----------
    try:
        import ray
    except Exception as e:
        raise SystemExit(
            "Ray is not installed. Install optional deps: pip install -r requirements_distributed_ray.txt\n"
            f"Import error: {e}"
        )

    if args.address == "local":
        ray.init(ignore_reinit_error=True)
    else:
        ray.init(address=None if args.address in ("auto", "") else args.address, ignore_reinit_error=True)

    # Infer evaluators count
    if args.num_evaluators and args.num_evaluators > 0:
        n_eval = int(args.num_evaluators)
    else:
        try:
            n_eval = max(1, int(ray.available_resources().get("CPU", 1)))
        except Exception:
            n_eval = 1

    queue_target = int(args.queue_target) if args.queue_target and args.queue_target > 0 else max(1, 2 * n_eval)

    # ---------- Ray actors ----------
    @ray.remote(num_cpus=1)
    class EvaluatorActor:
        def __init__(self, model_py: str, worker_py: str, base_json: str, ranges_json: str, suite_json: str):
            self.ev = Evaluator(
                model_py=model_py,
                worker_py=worker_py,
                base_json=base_json or None,
                ranges_json=ranges_json or None,
                suite_json=suite_json or None,
            )

        def ping(self) -> Dict[str, Any]:
            return {"ok": True, "dim": int(self.ev.dim)}

        def evaluate(self, trial_id: int, params_partial: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
            res = self.ev.eval_params(int(trial_id), params_partial)
            return int(trial_id), asdict(res)

    @ray.remote(num_cpus=1, num_gpus=1)
    class ProposerActor:
        def __init__(self, dim: int):
            self.dim = int(dim)
            try:
                import ray as _ray  # noqa

                gids = _ray.get_gpu_ids()
            except Exception:
                gids = []
            self.gpu_ids = gids

        def propose(
            self,
            X_u: List[List[float]],
            Y_min: List[List[float]],
            penalty: List[float],
            X_pending: List[List[float]],
            *,
            seed: int,
            n_init: int,
            feasible_tol: float,
        ) -> Tuple[List[float], Dict[str, Any]]:
            opt = ProposeOptions(
                seed=int(seed),
                n_init=int(n_init),
                method="botorch",
                allow_botorch=True,
                device="cuda",
                feasible_tol=float(feasible_tol),
            )
            Xu = np.asarray(X_u, dtype=float) if len(X_u) else np.empty((0, self.dim), dtype=float)
            Y = np.asarray(Y_min, dtype=float) if len(Y_min) else np.empty((0, 2), dtype=float)
            p = np.asarray(penalty, dtype=float) if len(penalty) else np.empty((0,), dtype=float)
            Xp = np.asarray(X_pending, dtype=float) if len(X_pending) else None
            bounds = np.stack([np.zeros(self.dim, dtype=float), np.ones(self.dim, dtype=float)], axis=0)
            x, info = propose_next(X_u=Xu, Y_min=Y, penalty=p, opt=opt, bounds=bounds, X_pending=Xp)
            info = dict(info)
            info["gpu_ids"] = list(self.gpu_ids)
            return list(map(float, x.tolist())), info

    evaluators = [EvaluatorActor.remote(model_py, worker_py, args.base_json, args.ranges_json, args.suite_json) for _ in range(n_eval)]
    ray.get([a.ping.remote() for a in evaluators])

    # proposer actors (GPU) — optional
    proposer_actors: List[Any] = []
    n_prop = int(args.proposer_actors) if int(args.proposer_actors) > 0 else (1 if (args.use_botorch and args.proposer_on_gpu) else 0)
    if args.use_botorch and n_prop > 0:
        proposer_actors = [ProposerActor.remote(ev0.dim) for _ in range(n_prop)]

    proposer_prefetch = int(args.proposer_prefetch) if int(args.proposer_prefetch) > 0 else max(0, len(proposer_actors))

    # dataset from DB (DONE/CACHED)
    X_u_np, Y_min_np, penalty_np = db.fetch_dataset_arrays(run_id)
    X_u: List[List[float]] = X_u_np.tolist() if X_u_np.size else []
    Y_min: List[List[float]] = Y_min_np.tolist() if Y_min_np.size else []
    penalty: List[float] = penalty_np.tolist() if penalty_np.size else []

    # proposer options for CPU/local propose
    opt_cpu = ProposeOptions(
        seed=int(args.seed),
        n_init=int(args.n_init),
        method="auto" if args.use_botorch else "lhs",
        allow_botorch=bool(args.use_botorch),
        device="auto",
        feasible_tol=float(args.feasible_tol),
    )
    bounds_u = ev0.bounds_u()

    # proposal buffering
    propose_buffer: List[Tuple[List[float], Dict[str, Any]]] = []
    propose_inflight: List[Any] = []  # ObjectRef

    def _submit_propose_requests() -> None:
        """Keep propose_inflight filled up to proposer_prefetch."""
        nonlocal propose_inflight
        if not proposer_actors or proposer_prefetch <= 0:
            return

        # Use current pending points snapshot
        X_pending = [m[2] for m in pending_meta.values()] if pending_meta else []

        while (len(propose_inflight) + len(propose_buffer)) < proposer_prefetch:
            actor = proposer_actors[(len(propose_inflight) + len(propose_buffer)) % len(proposer_actors)]
            fut = actor.propose.remote(
                X_u,
                Y_min,
                penalty,
                X_pending,
                seed=int(args.seed) + int(submitted) + int(len(propose_inflight)),
                n_init=int(args.n_init),
                feasible_tol=float(args.feasible_tol),
            )
            propose_inflight.append(fut)

    def _drain_one_proposal(timeout: float = 0.0) -> bool:
        """Try to move one finished proposal from inflight -> buffer."""
        nonlocal propose_inflight
        if not propose_inflight:
            return False
        done, not_done = ray.wait(propose_inflight, num_returns=1, timeout=timeout)
        if not done:
            return False
        fut = done[0]
        propose_inflight = list(not_done)
        try:
            x_u, info = ray.get(fut)
            propose_buffer.append((list(map(float, x_u)), dict(info)))
            return True
        except Exception:
            # ignore propose errors; will fallback to CPU proposer
            return False

    def _get_next_candidate() -> Tuple[List[float], Dict[str, Any]]:
        """Return (x_u, info). Uses GPU proposer buffer if available."""
        # keep proposer inflight filled
        _submit_propose_requests()
        # drain without blocking
        _drain_one_proposal(timeout=0.0)

        if propose_buffer:
            return propose_buffer.pop(0)

        # if we have GPU proposers, wait briefly for one
        if proposer_actors:
            if _drain_one_proposal(timeout=5.0):
                return propose_buffer.pop(0) if propose_buffer else (ev0.bounds_u()[0].tolist(), {"method": "fallback"})
        # fallback: local proposer
        Xp = np.asarray([m[2] for m in pending_meta.values()], dtype=float) if pending_meta else None
        x, info = propose_next(
            X_u=np.asarray(X_u, dtype=float) if len(X_u) else np.empty((0, ev0.dim), dtype=float),
            Y_min=np.asarray(Y_min, dtype=float) if len(Y_min) else np.empty((0, 2), dtype=float),
            penalty=np.asarray(penalty, dtype=float) if len(penalty) else np.empty((0,), dtype=float),
            opt=ProposeOptions(
                **{
                    **asdict(opt_cpu),
                    "seed": int(args.seed) + int(submitted),
                }
            ),
            bounds=bounds_u,
            X_pending=Xp,
        )
        return list(map(float, x.tolist())), dict(info)

    # ---------- main loop ----------
    submitted = 0
    new_completed = 0  # completed in THIS invocation (budget refers to this)
    pending: List[Any] = []  # ObjectRef list
    # fut -> (trial_id, param_hash, x_u, submit_ts)
    pending_meta: Dict[Any, Tuple[int, str, List[float], float]] = {}

    try:
        while new_completed < int(args.budget):
            # fill queue
            while submitted < int(args.budget) and len(pending) < queue_target:
                x_u, pinfo = _get_next_candidate()
                params = ev0.denormalize(x_u)
                p_hash = stable_hash_params(params)

                cached = db.get_cached(problem_hash=problem_hash, param_hash=p_hash)
                if cached is not None:
                    trial_id, inserted = db.reserve_trial(
                        run_id=run_id,
                        problem_hash=problem_hash,
                        param_hash=p_hash,
                        params=params,
                        x_u=x_u,
                        source="cache",
                    )
                    if inserted:
                        db.mark_done(
                            trial_id,
                            metrics=cached.get("metrics") or {},
                            obj1=_safe_float(cached.get("obj1")),
                            obj2=_safe_float(cached.get("obj2")),
                            penalty=_safe_float(cached.get("penalty")),
                            status="cached",
                        )
                        X_u.append(x_u)
                        Y_min.append([_safe_float(cached.get("obj1")), _safe_float(cached.get("obj2"))])
                        penalty.append(_safe_float(cached.get("penalty")))
                        new_completed += 1
                    continue

                trial_id, inserted = db.reserve_trial(
                    run_id=run_id,
                    problem_hash=problem_hash,
                    param_hash=p_hash,
                    params=params,
                    x_u=x_u,
                    source=str(pinfo.get("method", "propose")),
                )
                if not inserted:
                    continue

                db.mark_started(trial_id, worker_id="ray")
                actor = evaluators[submitted % len(evaluators)]
                fut = actor.evaluate.remote(trial_id, params)
                pending.append(fut)
                pending_meta[fut] = (trial_id, p_hash, x_u, _now := time.time())
                submitted += 1

                # keep proposer pipeline warm
                _submit_propose_requests()

            if not pending:
                time.sleep(0.2)
                continue

            done, not_done = ray.wait(pending, num_returns=1, timeout=5)
            pending = list(not_done)
            if not done:
                continue

            fut = done[0]
            trial_id, p_hash, x_u, _t0 = pending_meta.pop(fut, (0, "", [], time.time()))
            try:
                tid, res_d = ray.get(fut)
                assert int(tid) == int(trial_id)
            except Exception as e:
                tb = traceback.format_exc()
                db.mark_error(trial_id, error=str(e), traceback_str=tb)
                new_completed += 1
                continue

            # res_d is EvalResult as dict
            status = str(res_d.get("status", "done"))
            if status != "done":
                # keep as error row, but record traceback
                db.mark_error(trial_id, error=str(res_d.get("error", "error")), traceback_str=str(res_d.get("traceback", "")))
                new_completed += 1
                continue

            obj1 = _safe_float(res_d.get("obj1"))
            obj2 = _safe_float(res_d.get("obj2"))
            pen = _safe_float(res_d.get("penalty"))
            metrics = res_d.get("metrics") or {}
            db.mark_done(trial_id, metrics=metrics, obj1=obj1, obj2=obj2, penalty=pen, status="done")
            db.put_cache(problem_hash=problem_hash, param_hash=p_hash, metrics=metrics, obj1=obj1, obj2=obj2, penalty=pen)

            X_u.append(x_u)
            Y_min.append([obj1, obj2])
            penalty.append(pen)

            new_completed += 1

            if new_completed % max(1, int(args.progress_every)) == 0:
                Ynp = np.asarray(Y_min, dtype=float) if len(Y_min) else np.empty((0, 2), dtype=float)
                pnp = np.asarray(penalty, dtype=float) if len(penalty) else np.empty((0,), dtype=float)
                summ = _progress_summary(Ynp, pnp, float(args.feasible_tol))
                summ.update({"run_id": run_id, "new_completed": int(new_completed), "submitted": int(submitted)})
                _write_json(Path(out_dir) / "progress.json", summ)

                # store metrics in DB too
                db.add_metric(
                    run_id,
                    completed=int(len(Y_min)),
                    submitted=int(len(Y_min) + len(pending)),
                    n_feasible=int(summ.get("n_feasible") or 0),
                    hypervolume=float(summ.get("hypervolume") or float("nan")),
                    best_obj1=float(summ.get("best_obj1") or float("nan")),
                    best_obj2=float(summ.get("best_obj2") or float("nan")),
                    info={"runner": "ray"},
                )

        db.update_run_status(run_id, status="done")
        Ynp = np.asarray(Y_min, dtype=float) if len(Y_min) else np.empty((0, 2), dtype=float)
        pnp = np.asarray(penalty, dtype=float) if len(penalty) else np.empty((0,), dtype=float)
        summ = _progress_summary(Ynp, pnp, float(args.feasible_tol))
        summ.update({"run_id": run_id, "new_completed": int(new_completed), "submitted": int(submitted)})
        _write_json(Path(out_dir) / "progress_final.json", summ)

    except KeyboardInterrupt:
        db.update_run_status(run_id, status="interrupted")
        Ynp = np.asarray(Y_min, dtype=float) if len(Y_min) else np.empty((0, 2), dtype=float)
        pnp = np.asarray(penalty, dtype=float) if len(penalty) else np.empty((0,), dtype=float)
        summ = _progress_summary(Ynp, pnp, float(args.feasible_tol))
        summ.update({"run_id": run_id, "new_completed": int(new_completed), "submitted": int(submitted)})
        _write_json(Path(out_dir) / "progress.json", summ)
        print("Interrupted.")


if __name__ == "__main__":
    main()
