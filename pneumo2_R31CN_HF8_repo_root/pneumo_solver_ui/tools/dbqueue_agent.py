# -*- coding: utf-8 -*-
"""dbqueue_agent.py

Release 60: DB-Queue worker agent.

This process connects to ExperimentDB and repeatedly:
1) claims a PENDING trial (atomically) using `ExperimentDB.claim_pending(...)`
2) evaluates it locally using the project evaluation code
3) writes results back to DB (DONE/ERROR) and updates the global cache.

This is a **pull** model. It is deliberately simple and works across machines
as long as:
- all machines can reach the DB (PostgreSQL recommended for multi-machine),
- the project code + model/worker files exist on the agent machine.

Notes
-----
- For multi-computer we recommend Postgres and using `SELECT ... FOR UPDATE SKIP LOCKED` semantics
  implemented in the DB backend.
- For SQLite/DuckDB this agent can still be useful on a single workstation
  (multiple processes), but do not put those DB files on a network share.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Ensure pneumo_solver_ui is importable regardless of current working directory
_THIS = Path(__file__).resolve()
_PNEUMO_ROOT = _THIS.parent.parent  # .../pneumo_solver_ui
if str(_PNEUMO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PNEUMO_ROOT))

from pneumo_dist.eval_core import EvaluatorCore
from pneumo_dist.expdb import ExperimentDB
from pneumo_dist.trial_hash import make_problem_spec, hash_problem


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


class _Heartbeat(threading.Thread):
    def __init__(self, db: ExperimentDB, trial_id: str, interval_s: float) -> None:
        super().__init__(daemon=True)
        self.db = db
        self.trial_id = str(trial_id)
        self.interval_s = float(interval_s)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self.db.heartbeat(self.trial_id)
            except Exception:
                pass
            self._stop.wait(self.interval_s)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DB-Queue agent worker (Release60)")

    # DB
    p.add_argument("--db", default="runs/expdb.sqlite", help="DB target (file path for sqlite/duckdb, DSN for postgres)")
    p.add_argument("--db-engine", choices=["sqlite", "duckdb", "postgres"], default="sqlite")

    # Run selection
    p.add_argument("--run-id", default="", help="Run id to work on. If empty, will resolve by problem_hash.")
    p.add_argument("--resume-latest", action="store_true", help="If run-id empty, use latest run for computed problem_hash")

    # Problem definition (needed only if run-id is empty)
    p.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum.py")
    p.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    p.add_argument("--base-json", default="", help="Optional base override JSON")
    p.add_argument("--ranges-json", default="", help="Optional ranges override JSON")
    p.add_argument("--suite-json", default="", help="Optional suite JSON")

    # Execution
    p.add_argument("--poll-sec", type=float, default=2.0)
    p.add_argument("--heartbeat-sec", type=float, default=20.0)
    p.add_argument("--artifact-dir", default="", help="Optional local dir to save per-trial artifacts")
    p.add_argument("--worker-tag", default="", help="Optional worker tag (e.g. GPU0, hostA)")

    return p.parse_args()


def _resolve_rel_or_abs(path: str) -> str:
    s = str(path).strip()
    if not s:
        return ""
    # keep relative paths portable (like in coordinator)
    p = Path(s)
    if p.is_absolute():
        try:
            return str(p.relative_to(_PNEUMO_ROOT))
        except Exception:
            return str(p)
    return str(p)


def _abs_under(base: Path, rel_or_abs: str) -> str:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return str(p)
    return str((base / p).resolve())


def _pick_run(db: ExperimentDB, args: argparse.Namespace, base_dir: Path) -> Tuple[str, Dict[str, Any]]:
    """Return (run_id, run_row)."""

    run_id = str(args.run_id).strip()
    if run_id:
        row = db.get_run(run_id)
        if not row:
            raise RuntimeError(f"run-id not found: {run_id}")
        return run_id, row

    if not args.resume_latest:
        raise RuntimeError("run-id is empty. Use --run-id <ID> or --resume-latest with model/worker files.")

    # Compute problem_hash from local files, same convention as coordinator.
    model_rel = _resolve_rel_or_abs(args.model)
    worker_rel = _resolve_rel_or_abs(args.worker)
    base_json_rel = _resolve_rel_or_abs(args.base_json) if args.base_json else ""
    ranges_json_rel = _resolve_rel_or_abs(args.ranges_json) if args.ranges_json else ""
    suite_json_rel = _resolve_rel_or_abs(args.suite_json) if args.suite_json else ""

    # Validate existence
    _ = _abs_under(base_dir, model_rel)
    _ = _abs_under(base_dir, worker_rel)
    if base_json_rel:
        _ = _abs_under(base_dir, base_json_rel)
    if ranges_json_rel:
        _ = _abs_under(base_dir, ranges_json_rel)
    if suite_json_rel:
        _ = _abs_under(base_dir, suite_json_rel)

    spec_cfg = {}  # agent doesn't know objective keys here, but the file hashes are still useful
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

    latest = db.find_latest_run(problem_hash)
    if not latest:
        raise RuntimeError(f"No runs found for problem_hash={problem_hash[:12]}...")

    row = db.get_run(latest)
    if not row:
        raise RuntimeError("Internal error: latest run row missing")

    return latest, row


def main() -> None:
    args = _parse_args()

    base_dir = _PNEUMO_ROOT
    os.chdir(str(base_dir))

    # DB target: file path for embedded, DSN for postgres.
    if str(args.db_engine).lower() == "postgres":
        db_target = str(args.db).strip()
    else:
        db_target = str(Path(_abs_under(base_dir, args.db)).resolve())
        _ensure_dir(Path(db_target).parent)

    worker_tag = str(args.worker_tag).strip() or f"{socket.gethostname()}:{os.getpid()}"

    with ExperimentDB(db_target, engine=str(args.db_engine)) as db:
        db.init_schema()

        run_id, run_row = _pick_run(db, args, base_dir)

        problem_hash = str(run_row.get("problem_hash") or "")
        spec = run_row.get("spec") or {}
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except Exception:
                spec = {}

        # Prefer run spec paths/cfg for full consistency
        model_path = str(spec.get("model_path") or _resolve_rel_or_abs(args.model))
        worker_path = str(spec.get("worker_path") or _resolve_rel_or_abs(args.worker))
        base_json = spec.get("base_json") or (str(_resolve_rel_or_abs(args.base_json)) if args.base_json else None)
        ranges_json = spec.get("ranges_json") or (str(_resolve_rel_or_abs(args.ranges_json)) if args.ranges_json else None)
        suite_json = spec.get("suite_json") or (str(_resolve_rel_or_abs(args.suite_json)) if args.suite_json else None)
        cfg = spec.get("cfg") or {}
        if not isinstance(cfg, dict):
            cfg = {}

        core = EvaluatorCore(
            model_path=model_path,
            worker_path=worker_path,
            base_json=str(base_json) if base_json else None,
            ranges_json=str(ranges_json) if ranges_json else None,
            suite_json=str(suite_json) if suite_json else None,
            cfg=cfg,
        )

        artifact_dir = Path(args.artifact_dir).resolve() if str(args.artifact_dir).strip() else None
        if artifact_dir:
            _ensure_dir(artifact_dir)

        print(f"[agent] run_id={run_id} db_engine={args.db_engine} worker_tag={worker_tag}")

        while True:
            claim = db.claim_pending(run_id, worker_tag=worker_tag)
            if claim is None:
                time.sleep(float(args.poll_sec))
                continue

            trial_id = claim.trial_id
            param_hash = claim.param_hash

            hb = _Heartbeat(db, trial_id, interval_s=float(args.heartbeat_sec))
            hb.start()

            try:
                y, g, metrics = core.evaluate(trial_id=trial_id, x_u=claim.x_u)
                # Update global cache (safe on conflict)
                if problem_hash:
                    db.upsert_cache(problem_hash, param_hash, y=y, g=g, metrics=metrics)

                db.mark_done(trial_id, y=y, g=g, metrics=metrics)

                if artifact_dir:
                    _write_json(artifact_dir / f"trial_{trial_id}.json", {"trial_id": trial_id, "param_hash": param_hash, "x_u": claim.x_u, "y": y, "g": g, "metrics": metrics})

                print(f"[agent] DONE trial={trial_id} y={y} g={g}")

            except Exception as e:
                try:
                    db.mark_error(trial_id, error=str(e))
                except Exception:
                    pass
                print(f"[agent] ERROR trial={trial_id}: {e}")

            finally:
                try:
                    hb.stop()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
