# -*- coding: utf-8 -*-
"""Experiment database (DuckDB or SQLite) for reproducibility + dedup.

Why this module exists
----------------------
Distributed optimization needs a durable *single source of truth* that can:
- store evaluated candidates and their metrics;
- deduplicate expensive evaluations (cache);
- resume safely after crashes / PC restarts;
- support analysis (Pareto / hypervolume / progress).

Concurrency model
-----------------
For embedded DBs (DuckDB / SQLite) the safest pattern is **single-writer**:
- only the coordinator process performs writes;
- workers return results to the coordinator.

DuckDB documents its single-writer concurrency model; SQLite also behaves best
with a single writer + WAL mode for concurrent reads.

This file also provides a small *read API* used by Streamlit pages.

Schema
------
Tables:
- runs: one row per optimization run
- trials: one row per candidate evaluation
- cache: global cache by (problem_hash, param_hash) to reuse results
- run_metrics: time series of progress metrics (HV, best values, counts)

"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

JsonDict = Dict[str, Any]


def _now() -> float:
    return float(time.time())


def _json_dumps(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _json_load(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


@dataclass
class TrialRow:
    trial_id: int
    run_id: str
    param_hash: str
    status: str
    obj1: Optional[float]
    obj2: Optional[float]
    penalty: Optional[float]


class ExperimentDB:
    """Unified DB wrapper (DuckDB preferred, SQLite fallback)."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)
        self.engine = self._choose_engine(self.db_path)
        self._duck = None
        self._sqlite = None

    # -----------------------
    # Connection management
    # -----------------------

    @staticmethod
    def _choose_engine(path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext in (".duckdb", ".ddb"):
            return "duckdb"
        if ext in (".sqlite", ".db", ".sqlite3"):
            return "sqlite"
        # default: duckdb if installed, else sqlite
        try:
            import duckdb  # type: ignore  # noqa: F401

            return "duckdb"
        except Exception:
            return "sqlite"

    def _ensure_connected(self) -> None:
        if self._duck is None and self._sqlite is None:
            self.connect()

    def connect(self) -> None:
        """Open a connection (read/write)."""
        if self.engine == "duckdb":
            try:
                import duckdb  # type: ignore

                self._duck = duckdb.connect(self.db_path)
                self._sqlite = None
            except Exception:
                # fallback to sqlite if duckdb import fails
                self.engine = "sqlite"
                self._duck = None
                self._sqlite = sqlite3.connect(self.db_path, timeout=30)
        else:
            self._sqlite = sqlite3.connect(self.db_path, timeout=30)
            self._duck = None
            # Better concurrent read patterns.
            try:
                self._sqlite.execute("PRAGMA journal_mode=WAL;")
            except Exception:
                pass
            try:
                self._sqlite.execute("PRAGMA synchronous=NORMAL;")
            except Exception:
                pass

    def close(self) -> None:
        if self._duck is not None:
            try:
                self._duck.close()
            except Exception:
                pass
            self._duck = None
        if self._sqlite is not None:
            try:
                self._sqlite.close()
            except Exception:
                pass
            self._sqlite = None

    # -----------------------
    # SQL helpers
    # -----------------------

    def _execute(self, sql: str, params: Tuple[Any, ...] = ()) -> None:
        self._ensure_connected()
        if self._duck is not None:
            self._duck.execute(sql, params)
        elif self._sqlite is not None:
            self._sqlite.execute(sql, params)
        else:
            raise RuntimeError("DB is not connected")

    def _fetchall(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        self._ensure_connected()
        if self._duck is not None:
            return list(self._duck.execute(sql, params).fetchall())
        if self._sqlite is not None:
            cur = self._sqlite.execute(sql, params)
            return list(cur.fetchall())
        raise RuntimeError("DB is not connected")

    def _fetchone(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[Tuple[Any, ...]]:
        rows = self._fetchall(sql, params)
        return rows[0] if rows else None

    def commit(self) -> None:
        if self._sqlite is not None:
            self._sqlite.commit()
        # duckdb autocommits by default

    # -----------------------
    # Schema
    # -----------------------

    def init_schema(self) -> None:
        """Create tables if not exist."""
        self._ensure_connected()

        self._execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              created_ts DOUBLE,
              status TEXT,
              problem_hash TEXT,
              meta_json TEXT
            );
            """
        )

        self._execute(
            """
            CREATE TABLE IF NOT EXISTS trials (
              trial_id INTEGER PRIMARY KEY,
              run_id TEXT,
              problem_hash TEXT,
              param_hash TEXT,
              params_json TEXT,
              x_u_json TEXT,
              status TEXT,
              source TEXT,
              created_ts DOUBLE,
              started_ts DOUBLE,
              finished_ts DOUBLE,
              worker_id TEXT,
              error TEXT,
              traceback TEXT,
              metrics_json TEXT,
              obj1 DOUBLE,
              obj2 DOUBLE,
              penalty DOUBLE
            );
            """
        )

        self._execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
              problem_hash TEXT,
              param_hash TEXT,
              created_ts DOUBLE,
              metrics_json TEXT,
              obj1 DOUBLE,
              obj2 DOUBLE,
              penalty DOUBLE,
              PRIMARY KEY(problem_hash, param_hash)
            );
            """
        )

        # progress metrics (time series)
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS run_metrics (
              metric_id INTEGER PRIMARY KEY,
              run_id TEXT,
              ts DOUBLE,
              completed INTEGER,
              submitted INTEGER,
              n_feasible INTEGER,
              hypervolume DOUBLE,
              best_obj1 DOUBLE,
              best_obj2 DOUBLE,
              info_json TEXT
            );
            """
        )

        # Indices (best-effort across engines)
        for sql in (
            "CREATE INDEX IF NOT EXISTS idx_trials_run_id ON trials(run_id);",
            "CREATE INDEX IF NOT EXISTS idx_trials_param_hash ON trials(param_hash);",
            "CREATE INDEX IF NOT EXISTS idx_trials_status ON trials(status);",
            "CREATE INDEX IF NOT EXISTS idx_cache_param_hash ON cache(param_hash);",
            "CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON run_metrics(run_id);",
        ):
            try:
                self._execute(sql)
            except Exception:
                pass

        self.commit()

    # -----------------------
    # Runs
    # -----------------------

    def add_run(self, run_id: str, problem_hash: str, meta: Optional[JsonDict] = None, status: str = "running") -> None:
        """Insert a run if missing (idempotent)."""
        meta_json = _json_dumps(meta or {})
        row = self._fetchone("SELECT run_id FROM runs WHERE run_id=?;", (run_id,))
        if row:
            # Update problem_hash/meta if changed, but do not clobber status unless explicitly set.
            self._execute(
                "UPDATE runs SET problem_hash=?, meta_json=? WHERE run_id=?;",
                (problem_hash, meta_json, run_id),
            )
            self.commit()
            return

        if self.engine == "sqlite":
            self._execute(
                "INSERT INTO runs(run_id, created_ts, status, problem_hash, meta_json) VALUES(?,?,?,?,?);",
                (run_id, _now(), status, problem_hash, meta_json),
            )
        else:
            self._execute(
                "INSERT INTO runs(run_id, created_ts, status, problem_hash, meta_json) VALUES(?,?,?,?,?);",
                (run_id, _now(), status, problem_hash, meta_json),
            )
        self.commit()

    def update_run_status(self, run_id: str, status: str) -> None:
        self._execute("UPDATE runs SET status=? WHERE run_id=?;", (status, run_id))
        self.commit()

    def list_runs(self, limit: int = 100) -> List[str]:
        rows = self._fetchall(
            "SELECT run_id FROM runs ORDER BY created_ts DESC LIMIT ?;",
            (int(limit),),
        )
        return [str(r[0]) for r in rows]

    def get_run(self, run_id: str) -> JsonDict:
        row = self._fetchone(
            "SELECT run_id, created_ts, status, problem_hash, meta_json FROM runs WHERE run_id=?;",
            (run_id,),
        )
        if not row:
            return {}
        rid, created_ts, status, problem_hash, meta_json = row
        return {
            "run_id": str(rid),
            "created_ts": float(created_ts) if created_ts is not None else None,
            "status": str(status),
            "problem_hash": str(problem_hash),
            "meta": _json_load(meta_json) or {},
        }

    # -----------------------
    # Cache
    # -----------------------

    def get_cached(self, problem_hash: str, param_hash: str) -> Optional[JsonDict]:
        row = self._fetchone(
            "SELECT metrics_json, obj1, obj2, penalty FROM cache WHERE problem_hash=? AND param_hash=?;",
            (problem_hash, param_hash),
        )
        if not row:
            return None
        metrics_json, obj1, obj2, penalty = row
        return {
            "metrics": _json_load(metrics_json) or {},
            "obj1": obj1,
            "obj2": obj2,
            "penalty": penalty,
        }

    def put_cache(self, problem_hash: str, param_hash: str, metrics: JsonDict, obj1: float, obj2: float, penalty: float) -> None:
        if self.engine == "sqlite":
            self._execute(
                """
                INSERT OR REPLACE INTO cache(problem_hash,param_hash,created_ts,metrics_json,obj1,obj2,penalty)
                VALUES(?,?,?,?,?,?,?);
                """,
                (problem_hash, param_hash, _now(), _json_dumps(metrics), float(obj1), float(obj2), float(penalty)),
            )
        else:
            # DuckDB supports INSERT OR REPLACE in recent versions, but we keep a safe fallback.
            try:
                self._execute(
                    """
                    INSERT OR REPLACE INTO cache(problem_hash,param_hash,created_ts,metrics_json,obj1,obj2,penalty)
                    VALUES(?,?,?,?,?,?,?);
                    """,
                    (problem_hash, param_hash, _now(), _json_dumps(metrics), float(obj1), float(obj2), float(penalty)),
                )
            except Exception:
                try:
                    self._execute("DELETE FROM cache WHERE problem_hash=? AND param_hash=?;", (problem_hash, param_hash))
                except Exception:
                    pass
                self._execute(
                    "INSERT INTO cache(problem_hash,param_hash,created_ts,metrics_json,obj1,obj2,penalty) VALUES(?,?,?,?,?,?,?);",
                    (problem_hash, param_hash, _now(), _json_dumps(metrics), float(obj1), float(obj2), float(penalty)),
                )
        self.commit()

    # -----------------------
    # Trials
    # -----------------------

    def _next_id(self, table: str, id_col: str) -> int:
        r = self._fetchone(f"SELECT COALESCE(MAX({id_col}), 0) + 1 FROM {table};")
        return int(r[0]) if r else 1

    def reserve_trial(
        self,
        run_id: str,
        problem_hash: str,
        param_hash: str,
        params: JsonDict,
        x_u: Optional[Sequence[float]] = None,
        source: str = "propose",
    ) -> Tuple[int, bool]:
        """Reserve a trial id.

        Returns (trial_id, inserted_new).
        If a trial already exists for this (run_id, param_hash), returns existing trial_id and inserted_new=False.
        """
        ex = self._fetchone("SELECT trial_id FROM trials WHERE run_id=? AND param_hash=?;", (run_id, param_hash))
        if ex:
            return int(ex[0]), False

        trial_id = None
        if self.engine == "duckdb":
            trial_id = self._next_id("trials", "trial_id")

        if self.engine == "sqlite":
            self._execute(
                """
                INSERT INTO trials(run_id,problem_hash,param_hash,params_json,x_u_json,status,source,created_ts)
                VALUES(?,?,?,?,?,?,?,?);
                """,
                (
                    run_id,
                    problem_hash,
                    param_hash,
                    _json_dumps(params),
                    _json_dumps(list(x_u)) if x_u is not None else None,
                    "reserved",
                    source,
                    _now(),
                ),
            )
            r = self._fetchone("SELECT last_insert_rowid();")
            trial_id = int(r[0]) if r else -1
        else:
            assert trial_id is not None
            self._execute(
                """
                INSERT INTO trials(trial_id,run_id,problem_hash,param_hash,params_json,x_u_json,status,source,created_ts)
                VALUES(?,?,?,?,?,?,?,?,?);
                """,
                (
                    int(trial_id),
                    run_id,
                    problem_hash,
                    param_hash,
                    _json_dumps(params),
                    _json_dumps(list(x_u)) if x_u is not None else None,
                    "reserved",
                    source,
                    _now(),
                ),
            )

        self.commit()
        return int(trial_id), True

    def mark_started(self, trial_id: int, worker_id: str) -> None:
        self._execute(
            "UPDATE trials SET status=?, started_ts=?, worker_id=? WHERE trial_id=?;",
            ("running", _now(), worker_id, int(trial_id)),
        )
        self.commit()

    def mark_done(
        self,
        trial_id: int,
        *,
        metrics: JsonDict,
        obj1: float,
        obj2: float,
        penalty: float,
        status: str = "done",
    ) -> None:
        self._execute(
            """
            UPDATE trials
            SET status=?, finished_ts=?, metrics_json=?, obj1=?, obj2=?, penalty=?
            WHERE trial_id=?;
            """,
            (status, _now(), _json_dumps(metrics), float(obj1), float(obj2), float(penalty), int(trial_id)),
        )
        self.commit()

    def mark_error(self, trial_id: int, error: str, traceback_str: str = "") -> None:
        self._execute(
            """
            UPDATE trials
            SET status=?, finished_ts=?, error=?, traceback=?
            WHERE trial_id=?;
            """,
            ("error", _now(), str(error)[:4000], str(traceback_str)[:20000], int(trial_id)),
        )
        self.commit()

    # Backward-compatible aliases used by older coordinator scripts
    def mark_trial_started(self, trial_id: int, worker_id: str = "") -> None:
        self.mark_started(trial_id, worker_id or "worker")

    def mark_trial_done(
        self,
        trial_id: int,
        *,
        obj1: float,
        obj2: float,
        penalty: float,
        metrics: JsonDict,
        status: str = "done",
    ) -> None:
        self.mark_done(trial_id, metrics=metrics, obj1=obj1, obj2=obj2, penalty=penalty, status=status)

    def mark_trial_error(self, trial_id: int, error: str, tb: str = "") -> None:
        self.mark_error(trial_id, error=error, traceback_str=tb)

    # -----------------------
    # Query helpers (UI)
    # -----------------------

    def fetch_trials(self, run_id: str, limit: int = 20000) -> List[JsonDict]:
        rows = self._fetchall(
            """
            SELECT trial_id, param_hash, status, source,
                   created_ts, started_ts, finished_ts, worker_id,
                   obj1, obj2, penalty, error
            FROM trials
            WHERE run_id=?
            ORDER BY trial_id ASC
            LIMIT ?;
            """,
            (run_id, int(limit)),
        )
        out: List[JsonDict] = []
        for r in rows:
            (
                trial_id,
                param_hash,
                status,
                source,
                created_ts,
                started_ts,
                finished_ts,
                worker_id,
                obj1,
                obj2,
                penalty,
                error,
            ) = r
            out.append(
                {
                    "trial_id": int(trial_id),
                    "param_hash": str(param_hash),
                    "status": str(status),
                    "source": str(source) if source is not None else "",
                    "created_ts": float(created_ts) if created_ts is not None else None,
                    "started_ts": float(started_ts) if started_ts is not None else None,
                    "finished_ts": float(finished_ts) if finished_ts is not None else None,
                    "worker_id": str(worker_id) if worker_id is not None else "",
                    "obj1": obj1,
                    "obj2": obj2,
                    "penalty": penalty,
                    "error": str(error) if error is not None else "",
                }
            )
        return out

    def fetch_dataset_arrays(self, run_id: str):
        """Fetch dataset arrays for BO/HV from DONE/CACHED trials.

        Returns:
          X_u: (n,d) float
          Y_min: (n,2) float
          penalty: (n,) float
        """
        rows = self._fetchall(
            """
            SELECT x_u_json, obj1, obj2, penalty
            FROM trials
            WHERE run_id=? AND status IN ('done','cached')
            ORDER BY trial_id ASC;
            """,
            (run_id,),
        )
        xs: List[List[float]] = []
        ys: List[List[float]] = []
        ps: List[float] = []
        for x_u_json, obj1, obj2, pen in rows:
            xu = _json_load(x_u_json)
            if not isinstance(xu, list):
                continue
            try:
                xu_f = [float(v) for v in xu]
            except Exception:
                continue
            xs.append(xu_f)
            ys.append([float(obj1) if obj1 is not None else float("nan"), float(obj2) if obj2 is not None else float("nan")])
            ps.append(float(pen) if pen is not None else float("nan"))

        import numpy as np

        if not xs:
            return np.empty((0, 0), dtype=float), np.empty((0, 2), dtype=float), np.empty((0,), dtype=float)

        X_u = np.asarray(xs, dtype=float)
        Y_min = np.asarray(ys, dtype=float)
        penalty = np.asarray(ps, dtype=float)
        return X_u, Y_min, penalty

    # -----------------------
    # Resume / maintenance
    # -----------------------

    def requeue_stale_trials(self, run_id: str, ttl_sec: float) -> int:
        """Mark old RUNNING trials back to RESERVED (best-effort).

        Useful after crashes: workers died, coordinator restarted.
        """
        cutoff = _now() - float(ttl_sec)
        # Only trials with started_ts set and no finished_ts.
        self._execute(
            """
            UPDATE trials
            SET status='reserved', worker_id=NULL
            WHERE run_id=? AND status='running' AND started_ts IS NOT NULL AND started_ts < ? AND (finished_ts IS NULL);
            """,
            (run_id, cutoff),
        )
        # rowcount works for sqlite; duckdb returns -1 sometimes.
        try:
            n = int(getattr(self._sqlite, "total_changes", 0)) if self._sqlite is not None else 0
        except Exception:
            n = 0
        self.commit()
        return n

    # -----------------------
    # Metrics time series
    # -----------------------

    def add_metric(
        self,
        run_id: str,
        *,
        completed: int,
        submitted: int,
        n_feasible: int,
        hypervolume: float,
        best_obj1: float,
        best_obj2: float,
        info: Optional[JsonDict] = None,
    ) -> None:
        metric_id = self._next_id("run_metrics", "metric_id") if self.engine == "duckdb" else None
        if self.engine == "sqlite":
            self._execute(
                """
                INSERT INTO run_metrics(run_id, ts, completed, submitted, n_feasible, hypervolume, best_obj1, best_obj2, info_json)
                VALUES(?,?,?,?,?,?,?,?,?);
                """,
                (
                    run_id,
                    _now(),
                    int(completed),
                    int(submitted),
                    int(n_feasible),
                    float(hypervolume),
                    float(best_obj1),
                    float(best_obj2),
                    _json_dumps(info or {}),
                ),
            )
        else:
            assert metric_id is not None
            self._execute(
                """
                INSERT INTO run_metrics(metric_id, run_id, ts, completed, submitted, n_feasible, hypervolume, best_obj1, best_obj2, info_json)
                VALUES(?,?,?,?,?,?,?,?,?,?);
                """,
                (
                    int(metric_id),
                    run_id,
                    _now(),
                    int(completed),
                    int(submitted),
                    int(n_feasible),
                    float(hypervolume),
                    float(best_obj1),
                    float(best_obj2),
                    _json_dumps(info or {}),
                ),
            )
        self.commit()

    def fetch_metrics(self, run_id: str, limit: int = 10000) -> List[JsonDict]:
        rows = self._fetchall(
            """
            SELECT ts, completed, submitted, n_feasible, hypervolume, best_obj1, best_obj2, info_json
            FROM run_metrics
            WHERE run_id=?
            ORDER BY ts ASC
            LIMIT ?;
            """,
            (run_id, int(limit)),
        )
        out: List[JsonDict] = []
        for ts, completed, submitted, n_feasible, hv, b1, b2, info_json in rows:
            out.append(
                {
                    "ts": float(ts) if ts is not None else None,
                    "completed": int(completed) if completed is not None else 0,
                    "submitted": int(submitted) if submitted is not None else 0,
                    "n_feasible": int(n_feasible) if n_feasible is not None else 0,
                    "hypervolume": float(hv) if hv is not None else float("nan"),
                    "best_obj1": float(b1) if b1 is not None else float("nan"),
                    "best_obj2": float(b2) if b2 is not None else float("nan"),
                    "info": _json_load(info_json) or {},
                }
            )
        return out

    # -----------------------
    # Export
    # -----------------------

    def export_trials_csv(self, run_id: str, out_csv: Union[str, Path]) -> None:
        """Export trials to a CSV (flat)."""
        import csv

        out_csv = str(out_csv)

        rows = self._fetchall(
            """
            SELECT trial_id, run_id, problem_hash, param_hash, status, source,
                   created_ts, started_ts, finished_ts,
                   worker_id, obj1, obj2, penalty, error, metrics_json, params_json
            FROM trials
            WHERE run_id=?
            ORDER BY trial_id ASC;
            """,
            (run_id,),
        )
        fieldnames = [
            "trial_id",
            "run_id",
            "problem_hash",
            "param_hash",
            "status",
            "source",
            "created_ts",
            "started_ts",
            "finished_ts",
            "worker_id",
            "obj1",
            "obj2",
            "penalty",
            "error",
            "metrics_json",
            "params_json",
        ]
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow({k: v for k, v in zip(fieldnames, r)})
