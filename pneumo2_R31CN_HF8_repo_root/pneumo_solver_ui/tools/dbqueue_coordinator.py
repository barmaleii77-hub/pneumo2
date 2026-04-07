# -*- coding: utf-8 -*-
"""dbqueue_coordinator.py

Release 60: DB-Queue coordinator (Postgres/SQLite/DuckDB).

This coordinator does **NOT** evaluate candidates itself. Instead it:
1) Creates/resumes a run in ExperimentDB.
2) Keeps a target amount of work queued (`PENDING+RUNNING`) by inserting PENDING trials.
3) Optionally uses BO (qNEHVI via BoTorch) to propose candidates based on DONE trials.
4) Logs progress, exports CSV, tracks hypervolume.

Workers (agents) run separately and pull tasks from the same DB using
`tools/dbqueue_agent.py`.

When to use
-----------
- You want **multi-computer** distributed evaluation with a simple architecture:
  a shared DB is the rendezvous point.
- For multi-computer we recommend **PostgreSQL** because embedded DB files
  (SQLite/DuckDB) are not intended for concurrent writes over a network share.

Examples
--------
1) Local single PC (SQLite) with 4 agent processes:

    python tools/dbqueue_coordinator.py --db runs/expdb.sqlite --db-engine sqlite \
        --target-inflight 32 --budget 200 --export-every 25 --hv-log

    # in 4 terminals
    python tools/dbqueue_agent.py --db runs/expdb.sqlite --db-engine sqlite --run-id <RUN_ID>

2) Multi-PC with Postgres (recommended):

    python tools/dbqueue_coordinator.py --db-engine postgres \
        --db postgresql://user:pass@HOST:5432/pneumo \
        --target-inflight 256 --budget 2000

    # on each worker machine
    python tools/dbqueue_agent.py --db-engine postgres \
        --db postgresql://user:pass@HOST:5432/pneumo --run-id <RUN_ID>

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_THIS = Path(__file__).resolve()
_PNEUMO_ROOT = _THIS.parent.parent  # .../pneumo_solver_ui
_PROJECT_ROOT = _PNEUMO_ROOT.parent   # .../project root
for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pneumo_dist.eval_core import EvaluatorCore, EvaluatorConfig, sample_lhs
from pneumo_dist.expdb import ExperimentDB
from pneumo_dist.hv_tools import HVMonitor, pareto_mask_min
from pneumo_dist.mobo_propose import propose_qnehvi, propose_random
from pneumo_dist.trial_hash import hash_params, hash_vector, make_problem_spec, hash_problem


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DB-Queue coordinator (Release60)")

    # Problem definition (same as dist_opt_coordinator)
    p.add_argument("--model", default="model_pneumo_v9_doublewishbone_camozzi.py")
    p.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    p.add_argument("--base-json", default="default_base.json")
    p.add_argument("--ranges-json", default="default_ranges.json")
    p.add_argument("--suite-json", default="default_suite.json")

    p.add_argument(
        "--obj",
        action="append",
        default=[],
        help="Objective key in metrics row. Repeat to set multiple objectives. If omitted -> defaults from EvaluatorConfig.",
    )
    p.add_argument("--penalty-key", default="штраф_физичности_сумма")
    p.add_argument("--penalty-tol", type=float, default=0.0)

    # Optimization
    p.add_argument("--budget", type=int, default=200, help="Stop when DONE >= budget")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--proposer", choices=["random", "qnehvi", "auto", "portfolio"], default="auto")
    p.add_argument("--q", type=int, default=1, help="Candidates to propose per BO call")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")

    # Queue control
    p.add_argument(
        "--target-inflight",
        type=int,
        default=128,
        help="Keep roughly this many trials in DB as PENDING+RUNNING.",
    )
    p.add_argument("--poll-sec", type=float, default=2.0)
    p.add_argument("--stale-ttl-sec", type=int, default=6 * 3600)
    p.add_argument("--requeue-every-sec", type=int, default=60)

    # Experiment DB
    p.add_argument(
        "--db",
        default="runs/expdb.sqlite",
        help="Experiment DB target: file path (sqlite/duckdb) or DSN (postgresql://...) for postgres",
    )
    p.add_argument("--db-engine", choices=["sqlite", "duckdb", "postgres"], default="sqlite")

    # Resume
    p.add_argument("--resume", action="store_true")
    p.add_argument("--run-id", default="", help="Explicit run_id to resume")

    # Artifacts/logging
    p.add_argument("--run-dir", default="", help="Run output dir (default runs/run_<run_id>)")
    p.add_argument("--export-every", type=int, default=25)
    p.add_argument("--hv-log", action="store_true")
    p.add_argument("--hv-freeze-after", type=int, default=0, help="Freeze normalizer/ref after N feasible points (0=off)")

    return p.parse_args()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")


def _resolve_rel_or_abs(path_str: str) -> str:
    if not path_str:
        return ""
    p = Path(path_str)
    return str(p) if p.is_absolute() else str(Path(path_str))


def _abs_under(base_dir: Path, path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str((base_dir / p).resolve())


def _select_objectives(args: argparse.Namespace) -> Tuple[str, ...]:
    if args.obj:
        return tuple(str(x).strip() for x in args.obj if str(x).strip())
    return tuple(EvaluatorConfig().objective_keys)


def _arrays_from_done(done: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    Xs = []
    Ys = []
    Gs = []
    for t in done:
        x = t.get("x_u")
        y = t.get("y")
        g = t.get("g")
        if not isinstance(x, (list, tuple)) or not isinstance(y, (list, tuple)):
            continue
        Xs.append([float(v) for v in x])
        Ys.append([float(v) for v in y])
        if isinstance(g, (list, tuple)):
            Gs.append([float(v) for v in g])
    X = np.asarray(Xs, dtype=float) if Xs else np.zeros((0, 0), dtype=float)
    Y = np.asarray(Ys, dtype=float) if Ys else np.zeros((0, 0), dtype=float)
    G = np.asarray(Gs, dtype=float) if Gs else None
    return X, Y, G


def _feasible_mask(G: Optional[np.ndarray]) -> np.ndarray:
    if G is None or G.size == 0:
        return np.ones((0,), dtype=bool)
    return np.all(G <= 0.0, axis=1)


def main() -> int:
    args = _parse_args()

    base_dir = _PNEUMO_ROOT
    os.chdir(str(base_dir))

    objective_keys = _select_objectives(args)

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

    # Validate important files
    _ = _abs_under(base_dir, model_rel)
    _ = _abs_under(base_dir, worker_rel)
    if base_json_rel:
        _ = _abs_under(base_dir, base_json_rel)
    if ranges_json_rel:
        _ = _abs_under(base_dir, ranges_json_rel)
    if suite_json_rel:
        _ = _abs_under(base_dir, suite_json_rel)

    problem_spec = make_problem_spec(
        model_path=model_rel,
        worker_path=worker_rel,
        base_json=base_json_rel or None,
        ranges_json=ranges_json_rel or None,
        suite_json=suite_json_rel or None,
        cfg=spec_cfg,
        include_file_hashes=True,
    )
    problem_hash = hash_problem(problem_spec)

    # DB target handling
    if str(args.db_engine).lower() == "postgres":
        db_target = str(args.db).strip()
    else:
        db_target = str(Path(_abs_under(base_dir, args.db)).resolve())
        _ensure_dir(Path(db_target).parent)

    hvmon = HVMonitor(freeze_after=int(args.hv_freeze_after))

    with ExperimentDB(db_target, engine=str(args.db_engine)) as db:
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
                meta={
                    "created_by": "dbqueue_coordinator_R60",
                    "seed": int(args.seed),
                    "proposer": str(args.proposer),
                    "q": int(args.q),
                    "device": str(args.device),
                },
            )

        # Run dir
        run_dir = Path(args.run_dir) if args.run_dir else Path(_abs_under(base_dir, f"runs/run_{run_id}"))
        _ensure_dir(run_dir)
        _dump_json(run_dir / "problem_spec.json", problem_spec.to_dict())
        _write_text(run_dir / "problem_hash.txt", problem_hash)
        _write_text(run_dir / "run_id.txt", run_id)

        # Coordinator-side core for mapping (loads model+worker)
        core = EvaluatorCore(
            model_path=model_rel,
            worker_path=worker_rel,
            base_json=base_json_rel or None,
            ranges_json=ranges_json_rel or None,
            suite_json=suite_json_rel or None,
            cfg=spec_cfg,
        )
        d = core.dim()

        # Main loop
        t0 = time.time()
        last_export_done = -1
        last_requeue_ts = 0.0

        print(f"[DBQ] run_id={run_id} engine={args.db_engine} target_inflight={args.target_inflight} budget={args.budget}")

        while True:
            counts = db.count_by_status(run_id)
            n_done = int(counts.get("DONE", 0))
            n_err = int(counts.get("ERROR", 0))
            n_pending = int(counts.get("PENDING", 0))
            n_running = int(counts.get("RUNNING", 0))
            inflight = n_pending + n_running

            if n_done >= int(args.budget):
                break

            # periodic stale requeue (important if agents crash)
            now = time.time()
            if now - last_requeue_ts >= float(args.requeue_every_sec):
                try:
                    n_re = db.requeue_stale(run_id, float(args.stale_ttl_sec))
                    if n_re:
                        print(f"[DBQ] requeued stale: {n_re}")
                except Exception as e:
                    print(f"[DBQ] requeue_stale failed: {e}")
                last_requeue_ts = now

            # Fill queue
            need = int(args.target_inflight) - inflight
            if need > 0:
                # Pull DONE data for proposer
                done = db.fetch_done_trials(run_id)
                X_done, Y_done, G_done = _arrays_from_done(done)

                # Pending points for X_pending (avoid duplicates in qNEHVI)
                pend = db.fetch_trials(run_id, status="PENDING", limit=None, order="created_ts")
                runn = db.fetch_trials(run_id, status="RUNNING", limit=None, order="started_ts")
                X_pending = []
                for t in (pend + runn):
                    x = t.get("x_u")
                    if isinstance(x, (list, tuple)) and len(x) == d:
                        X_pending.append([float(v) for v in x])
                X_pending_arr = np.asarray(X_pending, dtype=float) if X_pending else None

                # Propose in batches
                reserved = 0
                attempts = 0
                while reserved < need and attempts < max(need * 4, 50):
                    attempts += 1
                    q = min(int(args.q), need - reserved)
                    q = max(1, min(q, 16))

                    if str(args.proposer) in {"qnehvi", "auto", "portfolio"} and X_done.size > 0:
                        pr = propose_qnehvi(
                            X_done=X_done,
                            Y_min_done=Y_done,
                            G_min_done=G_done,
                            q=q,
                            seed=int(args.seed + n_done + reserved + attempts),
                            X_pending=X_pending_arr,
                            device=str(args.device),
                        )
                        X_new = pr.X
                    else:
                        # LHS tends to be nicer than iid random early
                        X_new = sample_lhs(n=q, d=d, seed=int(args.seed + n_done + reserved + attempts))

                    for i in range(X_new.shape[0]):
                        x_u = X_new[i].tolist()
                        params = core.u_to_params(x_u)
                        param_hash = hash_params(params)
                        # reserve_trial will mark DONE if cache hit
                        rr = db.reserve_trial(run_id, problem_hash, x_u=x_u, params=params, param_hash=param_hash)
                        if rr.status in {"PENDING", "DONE"}:
                            reserved += 1
                        if reserved >= need:
                            break

                    # refresh X_pending to include newly reserved points
                    if X_pending_arr is not None:
                        X_pending_arr = np.vstack([X_pending_arr, X_new])
                    else:
                        X_pending_arr = X_new.copy()

                if reserved:
                    print(f"[DBQ] queued +{reserved} (need {need})  done={n_done} err={n_err} inflight={inflight+reserved}")

            # Progress export / hv
            if args.export_every and n_done - last_export_done >= int(args.export_every):
                try:
                    db.export_run_to_csv(run_id, str(run_dir / "trials.csv"), str(run_dir / "run_metrics.csv"))
                except Exception as e:
                    print(f"[DBQ] export failed: {e}")

                if args.hv_log:
                    try:
                        done = db.fetch_done_trials(run_id)
                        X_done, Y_done, G_done = _arrays_from_done(done)
                        if Y_done.size and G_done is not None and G_done.size:
                            feas = np.all(G_done <= 0.0, axis=1)
                        else:
                            feas = np.ones((Y_done.shape[0],), dtype=bool) if Y_done.size else np.zeros((0,), dtype=bool)

                        Yf = Y_done[feas] if Y_done.size else np.zeros((0, 0), dtype=float)
                        if Yf.shape[0] >= 2:
                            hv_val, hv_meta = hvmon.compute(Yf)
                            db.add_run_metric(run_id, key="hv", value=float(hv_val), json_obj=hv_meta)

                            # pareto size (minimization)
                            pm = pareto_mask_min(Yf)
                            db.add_run_metric(run_id, key="pareto_n", value=float(int(pm.sum())), json_obj=None)

                            print(f"[DBQ] HV={hv_val:.6g} pareto={int(pm.sum())} feasible={Yf.shape[0]}")
                    except Exception as e:
                        print(f"[DBQ] hv failed: {e}")

                last_export_done = n_done

            time.sleep(float(args.poll_sec))

        # Final export
        try:
            db.export_run_to_csv(run_id, str(run_dir / "trials.csv"), str(run_dir / "run_metrics.csv"))
        except Exception:
            pass

        dt = time.time() - t0
        print(f"[DBQ] finished: DONE={db.count_by_status(run_id).get('DONE',0)} in {dt:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
