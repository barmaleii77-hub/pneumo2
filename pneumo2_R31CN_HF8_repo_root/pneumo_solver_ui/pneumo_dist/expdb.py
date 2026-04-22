# -*- coding: utf-8 -*-
"""pneumo_dist.expdb

Experiment database for deduplication, reproducibility and distributed execution.

Release 60 highlights
---------------------
- Adds **optional PostgreSQL backend** (engine="postgres") for multi-machine / multi-writer.
- Adds a **queue-style claim API** (`claim_pending`) to enable pull-based workers
  (agents) without Ray/Dask.

Design goals
------------
- Keep a **stable, tiny API** used by coordinators and agents.
- Support embedded engines for quick local runs:
  - SQLite (stdlib)
  - DuckDB (optional)
- Support server DB for distributed runs:
  - PostgreSQL (optional)

Schema (logical)
----------------
- runs(run_id, created_ts, problem_hash, spec_json, meta_json)
- trials(trial_id, run_id, created_ts, status, attempt, param_hash,
        x_u_json, params_json, y_json, g_json, metrics_json, error_text,
        started_ts, finished_ts, heartbeat_ts, worker_tag, host)
- cache(problem_hash, param_hash) -> y/g/metrics (cross-run dedup)
- run_metrics(run-level metric time series: HV, best, etc)

Notes
-----
We store complex objects as JSON TEXT for portability.

PostgreSQL driver
-----------------
We try psycopg (v3) first, then psycopg2 as fallback. Both are supported.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import socket
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# NOTE: We keep schema migrations lightweight and embedded.
#       For multi-machine distributed evaluation the DB is the single
#       source of truth for reproducibility and dedup.
LATEST_SCHEMA_VERSION = 3
_SCOPE_SPLIT_RE = re.compile(r"[\n,;]+")


def _now_ts() -> float:
    return time.time()


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _json_loads(s: str | None) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _normalize_problem_hash_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in {"stable", "legacy"} else ""


def _problem_hash_short_label(problem_hash: Any, *, max_len: int = 12) -> str:
    value = str(problem_hash or "").strip()
    if not value:
        return ""
    return value if len(value) <= max_len else value[:max_len]


def _collect_scope_items(raw: Any, out: List[str]) -> None:
    if raw is None:
        return
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return
        if text[:1] in {"[", '"'}:
            parsed = _json_loads(text)
            if parsed is not None and parsed is not raw:
                _collect_scope_items(parsed, out)
                return
        for piece in _SCOPE_SPLIT_RE.split(text):
            item = str(piece or "").strip()
            if item and item not in out:
                out.append(item)
        return
    if isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
        for item in raw:
            _collect_scope_items(item, out)


def _normalize_scope_list(raw: Any) -> List[str]:
    out: List[str] = []
    _collect_scope_items(raw, out)
    return out


def _finite_float_or_none(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _json_dumps_safe(obj: Any) -> str:
    """JSON dump with a defensive fallback for legacy/corrupted payloads."""
    try:
        return _json_dumps(obj)
    except Exception:
        return _json_dumps({"_raw": str(obj), "_encode_error": True})


def _export_run_scope_payload(run: Dict[str, Any] | None, *, run_id_default: str = "") -> Dict[str, Any]:
    run_payload = dict(run or {}) if isinstance(run, dict) else {}
    spec = dict(run_payload.get("spec") or {}) if isinstance(run_payload.get("spec"), dict) else {}
    meta = dict(run_payload.get("meta") or {}) if isinstance(run_payload.get("meta"), dict) else {}
    cfg = dict(spec.get("cfg") or {}) if isinstance(spec.get("cfg"), dict) else {}
    objective_contract = (
        dict(meta.get("objective_contract") or {})
        if isinstance(meta.get("objective_contract"), dict)
        else {}
    )

    objective_keys_raw = None
    if "objective_keys" in objective_contract:
        objective_keys_raw = objective_contract.get("objective_keys")
    elif "objective_keys" in cfg:
        objective_keys_raw = cfg.get("objective_keys")
    penalty_key_raw = objective_contract.get("penalty_key")
    if not str(penalty_key_raw or "").strip():
        penalty_key_raw = cfg.get("penalty_key")
    penalty_tol_raw = objective_contract.get("penalty_tol")
    if penalty_tol_raw is None and "penalty_tol" in cfg:
        penalty_tol_raw = cfg.get("penalty_tol")

    problem_hash = str(run_payload.get("problem_hash") or meta.get("problem_hash") or "").strip()
    payload: Dict[str, Any] = {
        "schema": "expdb_run_scope_v1",
        "run_id": str(run_payload.get("run_id") or run_id_default or ""),
        "created_ts": run_payload.get("created_ts"),
        "problem_hash": problem_hash,
        "problem_hash_short": _problem_hash_short_label(problem_hash),
        "problem_hash_mode": "",
        "backend": str(meta.get("backend") or ""),
        "created_by": str(meta.get("created_by") or ""),
        "objective_keys": _normalize_scope_list(objective_keys_raw),
        "penalty_key": str(penalty_key_raw or "").strip(),
    }

    for raw_mode in (
        meta.get("problem_hash_mode"),
        spec.get("problem_hash_mode"),
        cfg.get("problem_hash_mode"),
    ):
        mode = _normalize_problem_hash_mode(raw_mode)
        if mode:
            payload["problem_hash_mode"] = mode
            break

    penalty_tol = _finite_float_or_none(penalty_tol_raw)
    if penalty_tol is not None:
        payload["penalty_tol"] = float(penalty_tol)
    if objective_contract:
        payload["objective_contract"] = objective_contract
    return payload


def _qmark_to_pyformat(sql: str) -> str:
    """Convert sqlite qmark placeholders ('?') to postgres pyformat ('%s')."""
    return sql.replace("?", "%s")

_SAFE_CH_RE = __import__("re").compile(r"[^a-zA-Z0-9_]+")

def safe_channel(name: str) -> str:
    """Make a safe PostgreSQL LISTEN/NOTIFY channel identifier.

    PostgreSQL identifiers are limited to 63 bytes and must start with a letter/underscore.
    We aggressively replace unsafe chars with '_' and truncate.

    This function is harmless for sqlite/duckdb too.
    """
    n = str(name)
    n = _SAFE_CH_RE.sub("_", n)
    if not n:
        n = "c"
    if n[0].isdigit():
        n = "c_" + n
    # Postgres identifier length limit is 63 bytes (we keep it simple: chars).
    return n[:63]

def channel_evt(run_id: str) -> str:
    """Event channel: wake agents/controller/proposer when queue/results change."""
    return safe_channel(f"pneumo_evt_{run_id}")

def channel_ctl(run_id: str) -> str:
    """Control channel: wake processes when run state changes (pause/stop/resume)."""
    return safe_channel(f"pneumo_ctl_{run_id}")


@dataclass
class ReserveResult:
    trial_id: str
    status: str
    from_cache: bool
    inserted: bool = False
    y: Optional[List[float]] = None
    g: Optional[List[float]] = None
    metrics: Optional[Dict[str, Any]] = None

    def __iter__(self):
        # Legacy callers unpack reserve_trial() as: trial_id, inserted = ...
        yield self.trial_id
        yield self.inserted


@dataclass
class TrialRecord:
    trial_id: str
    run_id: str
    status: str
    attempt: int
    param_hash: str
    x_u: List[float]
    params: Dict[str, Any]
    y: Optional[List[float]] = None
    g: Optional[List[float]] = None
    metrics: Optional[Dict[str, Any]] = None
    error_text: str = ""


@dataclass
class ClaimedTrial:
    """A minimal payload returned by claim_pending()."""

    trial_id: str
    run_id: str
    attempt: int
    param_hash: str
    x_u: List[float]
    params: Dict[str, Any]


class ExperimentDB:
    """A tiny DB wrapper with a stable API for the coordinator + agents."""

    def __init__(
        self,
        db_path: str | os.PathLike,
        *,
        engine: str = "sqlite",
        timeout_s: float = 30.0,
        pragmas_sqlite: bool = True,
    ):
        # NOTE: for postgres, `db_path` is treated as DSN/URL:
        #   postgresql://user:pass@host:5432/dbname
        self.db_path = str(db_path)
        self.engine = str(engine).lower().strip()
        self.timeout_s = float(timeout_s)
        self.pragmas_sqlite = bool(pragmas_sqlite)

        self._conn: Any = None
        self._pg_driver: str = ""  # "psycopg" | "psycopg2" | ""

        # Historical callers expect ExperimentDB(...).init_schema() to work
        # without an explicit open().
        self.open()

    # ---- connection management ----

    def __enter__(self) -> "ExperimentDB":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.close()
        except Exception:
            pass

    @property
    def conn(self):
        if self._conn is None:
            raise RuntimeError("DB is not opened")
        return self._conn

    def open(self) -> None:
        # idempotent
        if self._conn is not None:
            return

        if self.engine in {"sqlite", "duckdb"}:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        if self.engine == "sqlite":
            self._conn = sqlite3.connect(
                self.db_path,
                timeout=self.timeout_s,
                isolation_level=None,  # autocommit
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA foreign_keys=ON;")
            if self.pragmas_sqlite:
                # WAL improves read concurrency on a single host.
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
                self._conn.execute("PRAGMA temp_store=MEMORY;")
                self._conn.execute("PRAGMA busy_timeout=30000;")

        elif self.engine == "duckdb":
            try:
                import duckdb  # type: ignore
            except Exception as e:
                raise RuntimeError(
                    "DuckDB engine requested, but 'duckdb' package is not installed. "
                    "Install optional deps: pip install duckdb"
                ) from e
            self._conn = duckdb.connect(self.db_path)

        elif self.engine == "postgres":
            self._open_postgres()

        else:
            raise ValueError(f"Unknown DB engine: {self.engine}")

        self.init_schema()

    def connect(self) -> None:
        # Legacy alias used by older distributed runners.
        self.open()

    def _open_postgres(self) -> None:
        dsn = self.db_path
        # psycopg v3 preferred
        try:
            import psycopg  # type: ignore

            self._conn = psycopg.connect(dsn, autocommit=True)
            self._pg_driver = "psycopg"
            return
        except Exception:
            pass

        # fallback psycopg2
        try:
            import psycopg2  # type: ignore

            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            self._conn = conn
            self._pg_driver = "psycopg2"
            return
        except Exception as e:
            raise RuntimeError(
                "Postgres engine requested, but neither 'psycopg' nor 'psycopg2' is installed. "
                "Install optional deps: pip install psycopg[binary] (recommended)"
            ) from e

    def open_secondary_postgres(self):
        """Open an extra PostgreSQL connection (for LISTEN/NOTIFY wait loops).

        The main `ExperimentDB.conn` is used for normal queries. For `LISTEN`
        we want a dedicated connection which can block on notifications.
        """
        if self.engine != "postgres":
            raise RuntimeError("open_secondary_postgres is only valid for postgres engine")
        dsn = self.db_path
        try:
            import psycopg  # type: ignore

            return psycopg.connect(dsn, autocommit=True)
        except Exception:
            try:
                import psycopg2  # type: ignore

                c = psycopg2.connect(dsn)
                c.autocommit = True
                return c
            except Exception as e:
                raise RuntimeError(
                    "Postgres engine requested but neither psycopg (v3) nor psycopg2 is installed. "
                    "Install optional deps: pip install psycopg[binary]  (or pip install psycopg2-binary)"
                ) from e

    def notify(self, channel: str, payload: str = "") -> None:
        """Send NOTIFY on a channel (postgres only).

        For sqlite/duckdb this is a no-op.
        """
        if self.engine != "postgres":
            return
        ch = safe_channel(channel)
        # NOTIFY payload max is 8000 bytes in PostgreSQL.
        pl = str(payload or "")
        try:
            if len(pl.encode("utf-8")) > 8000:
                pl = pl.encode("utf-8")[:8000].decode("utf-8", errors="ignore")
        except Exception:
            pl = pl[:8000]
        try:
            if self._pg_driver == "psycopg":
                # psycopg3 supports conn.execute()
                self.conn.execute(f"NOTIFY {ch}, %s;", (pl,))
                return
        except Exception:
            pass
        try:
            cur = self.conn.cursor()
            cur.execute(f"NOTIFY {ch}, %s;", (pl,))
        except Exception:
            # best-effort: ignore notify failures (should never break optimization loop)
            pass

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
                self._pg_driver = ""

    # ---- low-level helpers ----

    def execute(self, sql: str, params: Sequence[Any] | None = None):
        if self.engine == "postgres":
            sql2 = _qmark_to_pyformat(sql)
            params2 = list(params) if params is not None else []
            if self._pg_driver == "psycopg" and hasattr(self.conn, "execute"):
                return self.conn.execute(sql2, params2)
            # psycopg2
            cur = self.conn.cursor()
            cur.execute(sql2, params2)
            return cur

        # sqlite / duckdb
        if params is None:
            return self.conn.execute(sql)
        return self.conn.execute(sql, params)

    def _execute(self, sql: str, params: Sequence[Any] | None = None):
        # Legacy alias used by older runners.
        return self.execute(sql, params)

    def commit(self) -> None:
        # Compatibility helper for callers that manage transactions manually.
        try:
            fn = getattr(self.conn, "commit", None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def fetchone(self, sql: str, params: Sequence[Any] | None = None):
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql: str, params: Sequence[Any] | None = None):
        cur = self.execute(sql, params)
        return cur.fetchall()

    def _table_columns(self, table: str) -> List[str]:
        table = str(table)
        cols: List[str] = []
        try:
            if self.engine == "sqlite":
                rows = self.fetchall(f"PRAGMA table_info({table});")
                cols = [str(r[1]) for r in rows]
            elif self.engine == "duckdb":
                rows = self.fetchall(f"PRAGMA table_info('{table}');")
                cols = [str(r[1]) for r in rows]
            elif self.engine == "postgres":
                rows = self.fetchall(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=?;",
                    [table],
                )
                cols = [str(r[0]) for r in rows]
        except Exception:
            cols = []
        return cols

    def _ensure_column(self, table: str, col: str, coltype_sql: str = "TEXT") -> None:
        cols = self._table_columns(table)
        if cols and col in cols:
            return
        try:
            if self.engine == "postgres":
                self.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype_sql};")
            else:
                self.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype_sql};")
        except Exception:
            # May fail if ALTER not supported or column exists.
            pass

    # ---- schema versioning / migrations ----

    def _get_schema_version(self) -> int:
        try:
            row = self.fetchone("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;")
            if not row:
                return 0
            return int(row[0] or 0)
        except Exception:
            return 0

    def _set_schema_version(self, version: int) -> None:
        ts = _now_ts()
        try:
            self.execute("INSERT INTO schema_version(version, updated_ts) VALUES(?,?);", [int(version), float(ts)])
        except Exception:
            # Some engines may not like adding rows before commit; ignore.
            pass

    def migrate_schema(self) -> None:
        """Bring the DB schema up to LATEST_SCHEMA_VERSION.

        We avoid external migration tools to keep the project "one-folder runnable".
        """

        cur_ver = self._get_schema_version()
        if cur_ver >= LATEST_SCHEMA_VERSION:
            return

        # v1 -> v2: queue improvements + agents table.
        if cur_ver < 2:
            # Trials: scheduling/priority + explicit lease.
            self._ensure_column("trials", "priority", "INTEGER")
            self._ensure_column("trials", "scheduled_ts", "DOUBLE")
            self._ensure_column("trials", "lease_expires_ts", "DOUBLE")

            # Agents (for multi-machine observability)
            dbl = "DOUBLE PRECISION" if self.engine == "postgres" else "DOUBLE"
            self.execute(
                f"""
                CREATE TABLE IF NOT EXISTS agents (
                    worker_tag TEXT PRIMARY KEY,
                    host TEXT,
                    pid INTEGER,
                    started_ts {dbl},
                    heartbeat_ts {dbl},
                    last_trial_id TEXT,
                    meta_json TEXT
                );
                """
            )
            self.execute("CREATE INDEX IF NOT EXISTS idx_agents_heartbeat ON agents(heartbeat_ts);")

            # Helpful index for queue claiming.
            try:
                self.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_trials_queue
                    ON trials(run_id, status, scheduled_ts, priority, created_ts);
                    """
                )
            except Exception:
                pass

            # Postgres partial index for faster PENDING selection.
            if self.engine == "postgres":
                try:
                    self.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_trials_pending_queue
                        ON trials(run_id, scheduled_ts, priority, created_ts)
                        WHERE status='PENDING';
                        """
                    )
                except Exception:
                    pass

            self._set_schema_version(2)


        # v2 -> v3: run control table (pause/stop/resume) + optional NOTIFY channels.
        if cur_ver < 3:
            dbl = "DOUBLE PRECISION" if self.engine == "postgres" else "DOUBLE"
            self.execute(
                f"""
                CREATE TABLE IF NOT EXISTS run_control (
                    run_id TEXT PRIMARY KEY,
                    state TEXT,
                    updated_ts {dbl},
                    message TEXT
                );
                """
            )
            try:
                self.execute("CREATE INDEX IF NOT EXISTS idx_run_control_state ON run_control(state);")
            except Exception:
                pass
            self._set_schema_version(3)

    # ---- schema ----

    def init_schema(self) -> None:
        # A compatible schema across engines (types adjusted per engine).
        dbl = "DOUBLE PRECISION" if self.engine == "postgres" else "DOUBLE"

        # schema versioning
        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER,
                updated_ts {dbl}
            );
            """
        )

        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                created_ts {dbl},
                problem_hash TEXT,
                spec_json TEXT,
                meta_json TEXT
            );
            """
        )

        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS trials (
                trial_id TEXT PRIMARY KEY,
                run_id TEXT,
                created_ts {dbl},
                status TEXT,
                attempt INTEGER,
                param_hash TEXT,
                priority INTEGER,
                scheduled_ts {dbl},
                lease_expires_ts {dbl},
                x_u_json TEXT,
                params_json TEXT,
                y_json TEXT,
                g_json TEXT,
                metrics_json TEXT,
                error_text TEXT,
                started_ts {dbl},
                finished_ts {dbl},
                heartbeat_ts {dbl},
                worker_tag TEXT,
                host TEXT
            );
            """
        )

        # unique candidate per run
        self.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_trials_run_param
            ON trials(run_id, param_hash);
            """
        )
        self.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trials_run_status
            ON trials(run_id, status);
            """
        )

        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS cache (
                problem_hash TEXT,
                param_hash TEXT,
                created_ts {dbl},
                y_json TEXT,
                g_json TEXT,
                metrics_json TEXT,
                PRIMARY KEY(problem_hash, param_hash)
            );
            """
        )

        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS run_metrics (
                run_id TEXT,
                ts {dbl},
                key TEXT,
                value {dbl},
                json TEXT
            );
            """
        )
        self.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_run_metrics_run_ts
            ON run_metrics(run_id, ts);
            """
        )

        # Migration safety
        self._ensure_column("trials", "g_json", "TEXT")
        self._ensure_column("cache", "g_json", "TEXT")

        # Bring DB to the latest schema version (idempotent).
        self.migrate_schema()

        # Ensure latest schema (new columns/indexes/tables)
        self.migrate_schema()

        # Apply forward migrations if needed.
        self.migrate_schema()

    # ---- runs ----

    def run_exists(self, run_id: str) -> bool:
        row = self.fetchone("SELECT 1 FROM runs WHERE run_id=?;", [str(run_id)])
        return bool(row)

    def create_run(
        self,
        *,
        problem_hash: str,
        spec: Dict[str, Any],
        meta: Dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> str:
        rid = run_id or uuid.uuid4().hex
        ts = _now_ts()
        meta2 = dict(meta or {})
        meta2.setdefault("host", socket.gethostname())
        meta2.setdefault("created_utc", ts)
        self.execute(
            """INSERT INTO runs(run_id, created_ts, problem_hash, spec_json, meta_json)
               VALUES(?,?,?,?,?);""",
            [rid, ts, str(problem_hash), _json_dumps(spec), _json_dumps(meta2)],
        )
        return rid

    def add_run(
        self,
        run_id: str,
        *,
        problem_hash: str,
        meta: Dict[str, Any] | None = None,
        status: str | None = None,
        spec: Dict[str, Any] | None = None,
    ) -> str:
        """Legacy-compatible helper used by older distributed runners."""
        if self.run_exists(run_id):
            if status:
                self.update_run_status(run_id, status=status)
            return str(run_id)
        meta2 = dict(meta or {})
        if status:
            meta2["status"] = str(status)
        return self.create_run(
            problem_hash=str(problem_hash),
            spec=dict(spec or {}),
            meta=meta2,
            run_id=str(run_id),
        )

    def update_run_status(self, run_id: str, status: str, *, error: str = "", error_text: str = "") -> None:
        """Persist run-level status in run.meta for compatibility."""
        row = self.get_run(run_id)
        if not row:
            return
        meta = dict(row.get("meta") or {})
        meta["status"] = str(status or "").strip() or "unknown"
        meta["updated_utc"] = float(_now_ts())
        err = str(error_text or error or "").strip()
        if err:
            meta["error"] = err
        try:
            self.execute(
                "UPDATE runs SET meta_json=? WHERE run_id=?;",
                [_json_dumps(meta), str(run_id)],
            )
        except Exception:
            pass

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self.fetchone(
            "SELECT run_id, created_ts, problem_hash, spec_json, meta_json FROM runs WHERE run_id=?;",
            [str(run_id)],
        )
        if not row:
            return None
        return {
            "run_id": str(row[0]),
            "created_ts": float(row[1]),
            "problem_hash": str(row[2]),
            "spec": _json_loads(row[3]) or {},
            "meta": _json_loads(row[4]) or {},
        }

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.fetchall(
            "SELECT run_id, created_ts, problem_hash, meta_json FROM runs ORDER BY created_ts DESC LIMIT ?;",
            [int(limit)],
        )
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "run_id": str(r[0]),
                    "created_ts": float(r[1]),
                    "problem_hash": str(r[2]),
                    "meta": _json_loads(r[3]) or {},
                }
            )
        return out

    def find_latest_run(self, problem_hash: str) -> Optional[str]:
        row = self.fetchone(
            "SELECT run_id FROM runs WHERE problem_hash=? ORDER BY created_ts DESC LIMIT 1;",
            [str(problem_hash)],
        )
        return str(row[0]) if row else None

    def problem_hash_of_run(self, run_id: str) -> str:
        row = self.fetchone("SELECT problem_hash FROM runs WHERE run_id=?;", [str(run_id)])
        if not row:
            raise RuntimeError(f"run_id not found: {run_id}")
        return str(row[0])

    def ensure_run_problem_hash(self, run_id: str, problem_hash: str) -> None:
        row = self.fetchone("SELECT problem_hash FROM runs WHERE run_id=?;", [str(run_id)])
        if not row:
            raise RuntimeError(f"run_id not found: {run_id}")
        existing = str(row[0] or "")
        if existing and existing != str(problem_hash):
            raise RuntimeError(f"Problem hash mismatch for run {run_id}: DB has {existing}, expected {problem_hash}")
        if not existing:
            self.execute("UPDATE runs SET problem_hash=? WHERE run_id=?;", [str(problem_hash), str(run_id)])

    # ---- cache ----

    def _cache_get(
        self, *, problem_hash: str, param_hash: str
    ) -> Tuple[Optional[List[float]], Optional[List[float]], Optional[Dict[str, Any]]]:
        row = self.fetchone(
            "SELECT y_json, g_json, metrics_json FROM cache WHERE problem_hash=? AND param_hash=?;",
            [str(problem_hash), str(param_hash)],
        )
        if not row:
            return None, None, None
        y = _json_loads(row[0])
        g = _json_loads(row[1])
        metrics = _json_loads(row[2])
        return (
            y if isinstance(y, list) else None,
            g if isinstance(g, list) else None,
            metrics if isinstance(metrics, dict) else None,
        )

    def upsert_cache(
        self,
        *,
        problem_hash: str,
        param_hash: str,
        y: List[float],
        g: Optional[List[float]],
        metrics: Dict[str, Any],
    ) -> None:
        ts = _now_ts()
        self.execute(
            """INSERT INTO cache(problem_hash, param_hash, created_ts, y_json, g_json, metrics_json)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(problem_hash, param_hash) DO UPDATE SET
                 created_ts=excluded.created_ts,
                 y_json=excluded.y_json,
                 g_json=excluded.g_json,
                 metrics_json=excluded.metrics_json;""",
            [
                str(problem_hash),
                str(param_hash),
                float(ts),
                _json_dumps(list(y)),
                _json_dumps(list(g)) if g is not None else None,
                _json_dumps(metrics),
            ],
        )

    def get_cached(self, problem_hash: str, param_hash: str) -> Optional[Dict[str, Any]]:
        """Legacy cache reader returning obj1/obj2/penalty fields."""
        y, g, metrics = self._cache_get(problem_hash=str(problem_hash), param_hash=str(param_hash))
        if y is None and metrics is None:
            return None
        metrics_map = dict(metrics or {})
        obj1 = _finite_float_or_none(y[0] if isinstance(y, list) and len(y) >= 1 else metrics_map.get("obj1"))
        obj2 = _finite_float_or_none(y[1] if isinstance(y, list) and len(y) >= 2 else metrics_map.get("obj2"))
        penalty = _finite_float_or_none(
            g[0] if isinstance(g, list) and len(g) >= 1 else metrics_map.get("penalty")
        )
        if penalty is None:
            penalty = _finite_float_or_none(metrics_map.get("penalty_total"))
        # Legacy runners parse these through float(...), so None would crash.
        # Use NaN as the "unknown" sentinel for numeric compatibility.
        if obj1 is None:
            obj1 = float("nan")
        if obj2 is None:
            obj2 = float("nan")
        if penalty is None:
            penalty = float("nan")
        return {
            "obj1": obj1,
            "obj2": obj2,
            "penalty": penalty,
            "metrics": metrics_map,
            "y": list(y or []),
            "g": list(g or []) if isinstance(g, list) else None,
        }

    def put_cache(
        self,
        problem_hash: str,
        param_hash: str,
        *,
        metrics: Dict[str, Any] | None = None,
        obj1: Any = None,
        obj2: Any = None,
        penalty: Any = None,
    ) -> None:
        """Legacy cache writer."""
        metrics_map = dict(metrics or {})
        y: List[float] = []
        obj1_f = _finite_float_or_none(obj1)
        obj2_f = _finite_float_or_none(obj2)
        if obj1_f is not None:
            metrics_map.setdefault("obj1", float(obj1_f))
            y.append(float(obj1_f))
        if obj2_f is not None:
            metrics_map.setdefault("obj2", float(obj2_f))
            y.append(float(obj2_f))
        g: Optional[List[float]] = None
        pen_f = _finite_float_or_none(penalty)
        if pen_f is not None:
            metrics_map.setdefault("penalty", float(pen_f))
            g = [float(pen_f)]
        self.upsert_cache(
            problem_hash=str(problem_hash),
            param_hash=str(param_hash),
            y=y,
            g=g,
            metrics=metrics_map,
        )

    # ---- trials ----

    def reserve_trial(
        self,
        *args,
        run_id: str | None = None,
        problem_hash: str | None = None,
        param_hash: str | None = None,
        x_u: List[float] | None = None,
        params: Dict[str, Any] | None = None,
        meta: Dict[str, Any] | None = None,
        source: str | None = None,
    ) -> ReserveResult:
        """Reserve a trial (dedup within run, optional cache hit).

        - If (problem_hash,param_hash) in cache -> insert DONE trial and return.
        - Else insert PENDING trial (dedup within run). Return current status.
        """
        if args:
            if len(args) > 5:
                raise TypeError(
                    "reserve_trial() accepts up to 5 positional args: "
                    "(run_id, problem_hash, param_hash, x_u, params)"
                )
            if len(args) >= 1 and run_id is None:
                run_id = str(args[0])
            if len(args) >= 2 and problem_hash is None:
                problem_hash = str(args[1])
            if len(args) >= 3 and param_hash is None:
                param_hash = str(args[2])
            if len(args) >= 4 and x_u is None:
                x_u = list(args[3] or [])
            if len(args) >= 5 and params is None:
                params = dict(args[4] or {})

        if run_id is None or problem_hash is None or param_hash is None or x_u is None or params is None:
            raise TypeError(
                "reserve_trial() missing required arguments: "
                "run_id, problem_hash, param_hash, x_u, params"
            )

        meta = dict(meta or {})
        if source is not None and "source" not in meta:
            meta["source"] = str(source)
        host = meta.get("host") or socket.gethostname()
        ts = _now_ts()

        # 1) cache hit? We only accept cache entries with a usable objective vector.
        y_cached, g_cached, metrics_cached = self._cache_get(problem_hash=problem_hash, param_hash=param_hash)
        metrics_cached_map = dict(metrics_cached or {}) if isinstance(metrics_cached, dict) else {}
        y_cached_norm: List[float] = []
        if isinstance(y_cached, list):
            for item in y_cached:
                val = _finite_float_or_none(item)
                if val is not None:
                    y_cached_norm.append(float(val))

        if not y_cached_norm:
            obj1_f = _finite_float_or_none(metrics_cached_map.get("obj1"))
            obj2_f = _finite_float_or_none(metrics_cached_map.get("obj2"))
            if obj1_f is not None and obj2_f is not None:
                y_cached_norm = [float(obj1_f), float(obj2_f)]

        g_cached_norm: Optional[List[float]] = None
        if isinstance(g_cached, list):
            g_items: List[float] = []
            for item in g_cached:
                val = _finite_float_or_none(item)
                if val is not None:
                    g_items.append(float(val))
            if g_items:
                g_cached_norm = g_items
        if g_cached_norm is None:
            penalty_f = _finite_float_or_none(metrics_cached_map.get("penalty"))
            if penalty_f is None:
                penalty_f = _finite_float_or_none(metrics_cached_map.get("penalty_total"))
            if penalty_f is not None:
                g_cached_norm = [float(penalty_f)]

        if y_cached_norm:
            trial_id = uuid.uuid4().hex
            self.execute(
                """INSERT INTO trials(
                       trial_id, run_id, created_ts, status, attempt, param_hash,
                       priority, scheduled_ts, lease_expires_ts,
                       x_u_json, params_json, y_json, g_json, metrics_json,
                       error_text, started_ts, finished_ts, heartbeat_ts, worker_tag, host
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id, param_hash) DO NOTHING;""",
                [
                    str(trial_id),
                    str(run_id),
                    float(ts),
                    "DONE",
                    0,
                    str(param_hash),
                    0,
                    float(ts),
                    float(ts),
                    _json_dumps(list(x_u)),
                    _json_dumps(dict(params)),
                    _json_dumps(list(y_cached_norm)),
                    _json_dumps(list(g_cached_norm)) if g_cached_norm is not None else None,
                    _json_dumps(metrics_cached_map),
                    "",
                    float(ts),
                    float(ts),
                    float(ts),
                    "cache",
                    str(host),
                ],
            )
            row = self.fetchone(
                "SELECT trial_id, status, y_json, g_json, metrics_json FROM trials WHERE run_id=? AND param_hash=?;",
                [str(run_id), str(param_hash)],
            )
            if row:
                return ReserveResult(
                    trial_id=str(row[0]),
                    status=str(row[1]),
                    from_cache=True,
                    inserted=(str(row[0]) == str(trial_id)),
                    y=_json_loads(row[2]),
                    g=_json_loads(row[3]),
                    metrics=_json_loads(row[4]),
                )
            return ReserveResult(
                trial_id=str(trial_id),
                status="DONE",
                from_cache=True,
                inserted=True,
                y=y_cached_norm,
                g=g_cached_norm,
                metrics=metrics_cached_map,
            )

        # 2) insert as PENDING (dedup within run)
        trial_id = uuid.uuid4().hex
        self.execute(
            """INSERT INTO trials(
                   trial_id, run_id, created_ts, status, attempt, param_hash,
                   priority, scheduled_ts, lease_expires_ts,
                   x_u_json, params_json, y_json, g_json, metrics_json,
                   error_text, started_ts, finished_ts, heartbeat_ts, worker_tag, host
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(run_id, param_hash) DO NOTHING;""",
            [
                str(trial_id),
                str(run_id),
                float(ts),
                "PENDING",
                0,
                str(param_hash),
                0,
                float(ts),
                None,
                _json_dumps(list(x_u)),
                _json_dumps(dict(params)),
                None,
                None,
                None,
                "",
                None,
                None,
                None,
                "",
                str(host),
            ],
        )

        row = self.fetchone(
            "SELECT trial_id, status, y_json, g_json, metrics_json FROM trials WHERE run_id=? AND param_hash=?;",
            [str(run_id), str(param_hash)],
        )
        if row:
            return ReserveResult(
                trial_id=str(row[0]),
                status=str(row[1]),
                from_cache=False,
                inserted=(str(row[0]) == str(trial_id)),
                y=_json_loads(row[2]),
                g=_json_loads(row[3]),
                metrics=_json_loads(row[4]),
            )

        return ReserveResult(trial_id=str(trial_id), status="PENDING", from_cache=False, inserted=True)

    def mark_running(self, trial_id: str, worker_tag: str = "") -> None:
        ts = _now_ts()
        self.execute(
            """UPDATE trials
               SET status='RUNNING', started_ts=COALESCE(started_ts, ?), heartbeat_ts=?, worker_tag=?
               WHERE trial_id=?;""",
            [float(ts), float(ts), str(worker_tag), str(trial_id)],
        )

    def mark_started(self, trial_id: str, worker_id: str = "") -> None:
        # Legacy alias used by older runners.
        self.mark_running(str(trial_id), worker_tag=str(worker_id))

    def heartbeat(self, trial_id: str, *, extend_lease_sec: float | None = None) -> None:
        """Update heartbeat timestamp, optionally extending the lease.

        Lease is useful for multi-machine job-queue semantics where the DB acts
        as the only coordinator.
        """

        ts = _now_ts()
        if extend_lease_sec is not None and "lease_expires_ts" in self._table_columns("trials"):
            lease = float(ts) + float(extend_lease_sec)
            self.execute(
                "UPDATE trials SET heartbeat_ts=?, lease_expires_ts=? WHERE trial_id=?;",
                [float(ts), float(lease), str(trial_id)],
            )
            return

        self.execute(
            "UPDATE trials SET heartbeat_ts=? WHERE trial_id=?;",
            [float(ts), str(trial_id)],
        )

    def mark_done(
        self,
        trial_id: str,
        *,
        y: Optional[List[float]] = None,
        g: Optional[List[float]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        obj1: Any = None,
        obj2: Any = None,
        penalty: Any = None,
        status: str = "DONE",
        error_text: str = "",
    ) -> None:
        metrics_map = dict(metrics or {})
        if y is None:
            y_vals: List[float] = []
            obj1_f = _finite_float_or_none(obj1)
            obj2_f = _finite_float_or_none(obj2)
            if obj1_f is not None:
                y_vals.append(float(obj1_f))
                metrics_map.setdefault("obj1", float(obj1_f))
            if obj2_f is not None:
                y_vals.append(float(obj2_f))
                metrics_map.setdefault("obj2", float(obj2_f))
            y = y_vals
        else:
            y = [float(v) for v in list(y)]

        if g is None:
            pen_f = _finite_float_or_none(penalty)
            if pen_f is not None:
                g = [float(pen_f)]
                metrics_map.setdefault("penalty", float(pen_f))
        else:
            g = [float(v) for v in list(g)]

        status_text = str(status or "DONE").strip().upper() or "DONE"
        ts = _now_ts()
        self.execute(
            """UPDATE trials
               SET status=?, finished_ts=?, heartbeat_ts=?, y_json=?, g_json=?, metrics_json=?, error_text=?, lease_expires_ts=NULL
               WHERE trial_id=?;""",
            [
                status_text,
                float(ts),
                float(ts),
                _json_dumps(list(y)),
                _json_dumps(list(g)) if g is not None else None,
                _json_dumps(metrics_map),
                (error_text or "")[:50000],
                str(trial_id),
            ],
        )

    def mark_error(
        self,
        trial_id: str,
        error_text: str = "",
        *,
        error: str = "",
        traceback_str: str = "",
    ) -> None:
        base_error = str(error_text or error or "").strip()
        trace = str(traceback_str or "").strip()
        msg = base_error
        if trace:
            msg = f"{base_error}\n{trace}" if base_error else trace
        ts = _now_ts()
        self.execute(
            """UPDATE trials
               SET status='ERROR', finished_ts=?, heartbeat_ts=?, error_text=?, lease_expires_ts=NULL
               WHERE trial_id=?;""",
            [float(ts), float(ts), msg[:50000], str(trial_id)],
        )

    def requeue_stale(self, run_id: str, ttl_sec: float) -> int:
        now = float(_now_ts())
        cutoff = now - float(ttl_sec)
        has_lease = "lease_expires_ts" in self._table_columns("trials")

        # Requeue RUNNING tasks that stopped heartbeating or whose lease expired.
        if has_lease:
            sql = """UPDATE trials
               SET status='PENDING', attempt=attempt+1, worker_tag='', started_ts=NULL,
                   lease_expires_ts=NULL, scheduled_ts=?
               WHERE run_id=? AND status='RUNNING'
                 AND (COALESCE(heartbeat_ts, 0) < ? OR (COALESCE(lease_expires_ts, 0) > 0 AND lease_expires_ts < ?));"""
            params = [float(now), str(run_id), float(cutoff), float(now)]
        else:
            sql = """UPDATE trials
               SET status='PENDING', attempt=attempt+1, worker_tag='', started_ts=NULL, scheduled_ts=?
               WHERE run_id=? AND status='RUNNING' AND COALESCE(heartbeat_ts, 0) < ?;"""
            params = [float(now), str(run_id), float(cutoff)]

        cur = self.execute(sql, params)
        try:
            rc = int(getattr(cur, "rowcount", -1))
            if rc >= 0:
                return rc
        except Exception:
            pass
        row = self.fetchone(
            "SELECT COUNT(*) FROM trials WHERE run_id=? AND status='PENDING';",
            [str(run_id)],
        )
        return int(row[0]) if row else 0

    def requeue_stale_trials(self, run_id: str, *, ttl_sec: float, max_attempt: int | None = None) -> int:
        # Legacy alias; max_attempt is accepted for signature compatibility.
        _ = max_attempt
        return int(self.requeue_stale(str(run_id), float(ttl_sec)))

    def requeue_errors(self, run_id: str, *, max_attempts: int = 3, base_delay_sec: float = 60.0) -> int:
        """Move ERROR trials back to PENDING with exponential backoff.

        This is intentionally conservative:
        - only trials with attempt < max_attempts are retried
        - schedule uses: delay = base_delay_sec * (2 ** attempt)

        Return: number of trials requeued.
        """

        now = float(_now_ts())
        rows = self.fetchall(
            "SELECT trial_id, attempt FROM trials WHERE run_id=? AND status='ERROR' AND attempt < ? ORDER BY finished_ts ASC;",
            [str(run_id), int(max_attempts)],
        )
        n = 0
        for trial_id, attempt in rows:
            try:
                a = int(attempt or 0)
            except Exception:
                a = 0
            delay = float(base_delay_sec) * (2.0**float(a))
            sched = now + delay
            try:
                self.execute(
                    """UPDATE trials
                       SET status='PENDING', scheduled_ts=?, lease_expires_ts=NULL,
                           attempt=attempt+1, worker_tag='', started_ts=NULL
                       WHERE trial_id=? AND status='ERROR';""",
                    [float(sched), str(trial_id)],
                )
                n += 1
            except Exception:
                pass
        return n

    # ---- agents ----

    def upsert_agent(
        self,
        worker_tag: str,
        *,
        host: str | None = None,
        pid: int | None = None,
        last_trial_id: str | None = None,
        meta: Dict[str, Any] | None = None,
    ) -> None:
        """Register or heartbeat an agent (worker).

        This is a lightweight observability layer for multi-machine setups.
        """

        host = host or socket.gethostname()
        pid = int(pid) if pid is not None else None
        ts = float(_now_ts())
        started_ts = ts
        meta2 = dict(meta or {})

        try:
            self.execute(
                """INSERT INTO agents(worker_tag, host, pid, started_ts, heartbeat_ts, last_trial_id, meta_json)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(worker_tag) DO UPDATE SET
                     host=excluded.host,
                     pid=excluded.pid,
                     started_ts=COALESCE(agents.started_ts, excluded.started_ts),
                     heartbeat_ts=excluded.heartbeat_ts,
                     last_trial_id=excluded.last_trial_id,
                     meta_json=excluded.meta_json;""",
                [
                    str(worker_tag),
                    str(host),
                    pid,
                    float(started_ts),
                    float(ts),
                    str(last_trial_id or ""),
                    _json_dumps(meta2),
                ],
            )
        except Exception:
            # fallback best-effort: update then insert
            try:
                self.execute(
                    "UPDATE agents SET host=?, pid=?, heartbeat_ts=?, last_trial_id=?, meta_json=? WHERE worker_tag=?;",
                    [str(host), pid, float(ts), str(last_trial_id or ""), _json_dumps(meta2), str(worker_tag)],
                )
                return
            except Exception:
                pass
            try:
                self.execute(
                    "INSERT INTO agents(worker_tag, host, pid, started_ts, heartbeat_ts, last_trial_id, meta_json) VALUES(?,?,?,?,?,?,?);",
                    [str(worker_tag), str(host), pid, float(started_ts), float(ts), str(last_trial_id or ""), _json_dumps(meta2)],
                )
            except Exception:
                pass

    def list_agents(self, *, active_within_sec: float = 300.0, limit: int = 200) -> List[Dict[str, Any]]:
        now = float(_now_ts())
        cutoff = now - float(active_within_sec)
        rows = self.fetchall(
            """SELECT worker_tag, host, pid, started_ts, heartbeat_ts, last_trial_id, meta_json
               FROM agents
               WHERE COALESCE(heartbeat_ts, 0) >= ?
               ORDER BY heartbeat_ts DESC
               LIMIT ?;""",
            [float(cutoff), int(limit)],
        )
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "worker_tag": str(r[0] or ""),
                    "host": str(r[1] or ""),
                    "pid": int(r[2]) if r[2] is not None else None,
                    "started_ts": r[3],
                    "heartbeat_ts": r[4],
                    "last_trial_id": str(r[5] or ""),
                    "meta": _json_loads(r[6]) or {},
                }
            )
        return out

    # ---- run control (R64) ----

    def get_run_state(self, run_id: str) -> str:
        """Get run state: 'running' | 'paused' | 'stop'.

        If the control record doesn't exist yet, returns 'running'.
        """
        try:
            row = self.fetchone("SELECT state FROM run_control WHERE run_id=?;", [str(run_id)])
            if not row:
                return "running"
            st = str(row[0] or "running").strip().lower()
            return st or "running"
        except Exception:
            return "running"

    def set_run_state(self, run_id: str, state: str, message: str = "") -> None:
        """Set run state (idempotent)."""
        st = str(state).strip().lower()
        if st not in {"running", "paused", "stop"}:
            raise ValueError(f"Invalid run state: {state}")
        ts = float(_now_ts())
        try:
            self.execute(
                """INSERT INTO run_control(run_id, state, updated_ts, message)
                   VALUES(?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET
                     state=excluded.state,
                     updated_ts=excluded.updated_ts,
                     message=excluded.message;""",
                [str(run_id), str(st), float(ts), str(message or "")],
            )
            return
        except Exception:
            # Fallback: update then insert
            try:
                self.execute(
                    "UPDATE run_control SET state=?, updated_ts=?, message=? WHERE run_id=?;",
                    [str(st), float(ts), str(message or ""), str(run_id)],
                )
                return
            except Exception:
                pass
            try:
                self.execute(
                    "INSERT INTO run_control(run_id, state, updated_ts, message) VALUES(?,?,?,?);",
                    [str(run_id), str(st), float(ts), str(message or "")],
                )
            except Exception:
                pass

    # ---- pull-queue helpers (R60) ----

    def claim_pending(
        self,
        run_id: str,
        *,
        worker_tag: str = "agent",
        host: str | None = None,
        order: str = "queue",
        lease_sec: float = 600.0,
    ) -> Optional[ClaimedTrial]:
        """Atomically claim 1 PENDING trial (if exists) and mark it RUNNING.

        This enables a pull-based worker model:
        - Coordinator(s) fill DB with PENDING trials.
        - Agents poll DB and claim work.

        Concurrency strategy:
        - PostgreSQL: `SELECT ... FOR UPDATE SKIP LOCKED` in a CTE + `UPDATE ... RETURNING`.
        - SQLite/DuckDB: best-effort transaction claim (single host recommended).
        """
        host = host or socket.gethostname()
        ts = float(_now_ts())
        order = order if order in {"queue", "created_ts", "started_ts", "finished_ts"} else "queue"
        lease = float(ts) + float(lease_sec)

        if order == "queue":
            order_sql = "priority DESC, COALESCE(scheduled_ts, 0) ASC, created_ts ASC"
        else:
            order_sql = f"{order} ASC"

        if self.engine == "postgres":
            row = self.fetchone(
                f"""
                WITH cte AS (
                    SELECT trial_id
                    FROM trials
                    WHERE run_id=? AND status='PENDING'
                      AND (scheduled_ts IS NULL OR scheduled_ts <= ?)
                    ORDER BY {order_sql}
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE trials
                SET status='RUNNING',
                    started_ts=COALESCE(started_ts, ?),
                    heartbeat_ts=?,
                    worker_tag=?,
                    host=?,
                    lease_expires_ts=?
                WHERE trial_id IN (SELECT trial_id FROM cte)
                RETURNING trial_id, run_id, attempt, param_hash, x_u_json, params_json;
                """,
                [str(run_id), float(ts), ts, ts, str(worker_tag), str(host), float(lease)],
            )
            if not row:
                return None
            x_u = _json_loads(row[4]) or []
            params = _json_loads(row[5]) or {}
            return ClaimedTrial(
                trial_id=str(row[0]),
                run_id=str(row[1]),
                attempt=int(row[2] or 0),
                param_hash=str(row[3] or ""),
                x_u=list(x_u) if isinstance(x_u, list) else [],
                params=dict(params) if isinstance(params, dict) else {},
            )

        # sqlite / duckdb: transaction claim
        begin_sql = "BEGIN IMMEDIATE;" if self.engine == "sqlite" else "BEGIN TRANSACTION;"
        commit_sql = "COMMIT;"
        rollback_sql = "ROLLBACK;"

        try:
            self.execute(begin_sql)
            row = self.fetchone(
                f"""SELECT trial_id, run_id, attempt, param_hash, x_u_json, params_json
                    FROM trials
                    WHERE run_id=? AND status='PENDING'
                      AND (scheduled_ts IS NULL OR scheduled_ts <= ?)
                    ORDER BY {order_sql}
                    LIMIT 1;""",
                [str(run_id), float(ts)],
            )
            if not row:
                self.execute(commit_sql)
                return None

            trial_id = str(row[0])
            self.execute(
                """UPDATE trials
                   SET status='RUNNING', started_ts=COALESCE(started_ts, ?), heartbeat_ts=?, worker_tag=?, host=?, lease_expires_ts=?
                   WHERE trial_id=?;""",
                [ts, ts, str(worker_tag), str(host), float(lease), trial_id],
            )
            self.execute(commit_sql)

            x_u = _json_loads(row[4]) or []
            params = _json_loads(row[5]) or {}
            return ClaimedTrial(
                trial_id=trial_id,
                run_id=str(row[1]),
                attempt=int(row[2] or 0),
                param_hash=str(row[3] or ""),
                x_u=list(x_u) if isinstance(x_u, list) else [],
                params=dict(params) if isinstance(params, dict) else {},
            )
        except Exception:
            try:
                self.execute(rollback_sql)
            except Exception:
                pass
            return None

    # ---- queries ----

    def get_trial(self, trial_id: str) -> Optional[TrialRecord]:
        row = self.fetchone(
            """SELECT trial_id, run_id, status, attempt, param_hash, x_u_json, params_json, y_json, g_json, metrics_json, error_text
               FROM trials WHERE trial_id=?;""",
            [str(trial_id)],
        )
        if not row:
            return None
        return TrialRecord(
            trial_id=str(row[0]),
            run_id=str(row[1]),
            status=str(row[2]),
            attempt=int(row[3] or 0),
            param_hash=str(row[4] or ""),
            x_u=_json_loads(row[5]) or [],
            params=_json_loads(row[6]) or {},
            y=_json_loads(row[7]),
            g=_json_loads(row[8]),
            metrics=_json_loads(row[9]),
            error_text=str(row[10] or ""),
        )

    def fetch_trials(
        self,
        run_id: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        order: str = "finished_ts",
    ) -> List[Dict[str, Any]]:
        order = order if order in {"created_ts", "started_ts", "finished_ts"} else "finished_ts"
        sql = (
            "SELECT trial_id, status, attempt, param_hash, priority, scheduled_ts, lease_expires_ts, "
            "x_u_json, y_json, g_json, metrics_json, error_text, "
            "created_ts, started_ts, finished_ts, heartbeat_ts, worker_tag, host "
            "FROM trials WHERE run_id=?"
        )
        params: List[Any] = [str(run_id)]
        if status:
            sql += " AND status=?"
            params.append(str(status))
        sql += f" ORDER BY {order} ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = self.fetchall(sql, params)
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "trial_id": str(r[0]),
                    "status": str(r[1]),
                    "attempt": int(r[2] or 0),
                    "param_hash": str(r[3] or ""),
                    "priority": int(r[4] or 0),
                    "scheduled_ts": r[5],
                    "lease_expires_ts": r[6],
                    "x_u": _json_loads(r[7]),
                    "y": _json_loads(r[8]),
                    "g": _json_loads(r[9]),
                    "metrics": _json_loads(r[10]),
                    "error_text": str(r[11] or ""),
                    "created_ts": r[12],
                    "started_ts": r[13],
                    "finished_ts": r[14],
                    "heartbeat_ts": r[15],
                    "worker_tag": str(r[16] or ""),
                    "host": str(r[17] or ""),
                }
            )
        return out

    def fetch_done_trials(self, run_id: str) -> List[Dict[str, Any]]:
        return self.fetch_trials(run_id, status="DONE", limit=None, order="finished_ts")

    def count_by_status(self, run_id: str) -> Dict[str, int]:
        rows = self.fetchall(
            "SELECT status, COUNT(*) FROM trials WHERE run_id=? GROUP BY status;",
            [str(run_id)],
        )
        out: Dict[str, int] = {"PENDING": 0, "RUNNING": 0, "DONE": 0, "ERROR": 0}
        for st, cnt in rows:
            out[str(st)] = int(cnt)
        return out

    def count_status(self, run_id: str) -> Dict[str, int]:
        """Legacy status map with lower-case keys."""
        raw = self.count_by_status(run_id)
        out: Dict[str, int] = {}
        for st, cnt in raw.items():
            key = str(st or "").strip().lower()
            if not key:
                continue
            out[key] = int(out.get(key, 0) + int(cnt))
        for key in ("pending", "running", "done", "error", "cached", "reserved"):
            out.setdefault(key, 0)
        return out

    def fetch_dataset_arrays(self, run_id: str):
        """Legacy helper returning (X_u, Y_min, penalty) numpy arrays."""
        import numpy as np

        done_like = {"DONE", "CACHED", "CACHE", "SUCCESS", "COMPLETED"}
        xs: List[List[float]] = []
        ys: List[List[float]] = []
        ps: List[float] = []
        dim: Optional[int] = None

        for trial in self.fetch_trials(str(run_id), status=None, limit=None, order="created_ts"):
            status_text = str(trial.get("status") or "").strip().upper()
            if status_text not in done_like:
                continue
            x_raw = trial.get("x_u")
            if not isinstance(x_raw, list):
                continue
            x_vals: List[float] = []
            for item in x_raw:
                val = _finite_float_or_none(item)
                if val is None:
                    x_vals = []
                    break
                x_vals.append(float(val))
            if not x_vals:
                continue
            if dim is None:
                dim = len(x_vals)
            if len(x_vals) != int(dim):
                continue

            y_raw = trial.get("y")
            y_vals = list(y_raw) if isinstance(y_raw, list) else []
            metrics_map = dict(trial.get("metrics") or {}) if isinstance(trial.get("metrics"), dict) else {}
            obj1 = _finite_float_or_none(y_vals[0] if len(y_vals) >= 1 else metrics_map.get("obj1"))
            obj2 = _finite_float_or_none(y_vals[1] if len(y_vals) >= 2 else metrics_map.get("obj2"))
            if obj1 is None or obj2 is None:
                continue

            g_raw = trial.get("g")
            g_vals = list(g_raw) if isinstance(g_raw, list) else []
            penalty = _finite_float_or_none(g_vals[0] if g_vals else metrics_map.get("penalty"))
            if penalty is None:
                penalty = _finite_float_or_none(metrics_map.get("penalty_total"))
            if penalty is None:
                penalty = float("nan")

            xs.append(x_vals)
            ys.append([float(obj1), float(obj2)])
            ps.append(float(penalty))

        x_dim = int(dim or 0)
        X_u = np.asarray(xs, dtype=float) if xs else np.empty((0, x_dim), dtype=float)
        Y_min = np.asarray(ys, dtype=float) if ys else np.empty((0, 2), dtype=float)
        penalty = np.asarray(ps, dtype=float) if ps else np.empty((0,), dtype=float)
        return X_u, Y_min, penalty

    # ---- metrics ----

    def add_run_metric(self, run_id: str, *, key: str, value: float | None = None, json_blob: Any | None = None) -> None:
        self.log_metric(run_id, key=key, value=value, json_obj=json_blob)

    def log_metric(self, run_id: str, *, key: str, value: float | None = None, json_obj: Any | None = None) -> None:
        ts = _now_ts()
        self.execute(
            "INSERT INTO run_metrics(run_id, ts, key, value, json) VALUES(?,?,?,?,?);",
            [
                str(run_id),
                float(ts),
                str(key),
                float(value) if value is not None else None,
                _json_dumps(json_obj) if json_obj is not None else None,
            ],
        )

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
        info: Dict[str, Any] | None = None,
    ) -> None:
        """Legacy metric sink used by older distributed runners."""
        payload = {
            "completed": int(completed),
            "submitted": int(submitted),
            "n_feasible": int(n_feasible),
            "hypervolume": float(hypervolume),
            "best_obj1": float(best_obj1),
            "best_obj2": float(best_obj2),
            "info": dict(info or {}),
        }
        self.log_metric(str(run_id), key="progress", value=float(completed), json_obj=payload)
        if math.isfinite(float(hypervolume)):
            self.log_metric(str(run_id), key="hv", value=float(hypervolume), json_obj=payload)

    def fetch_metrics(self, run_id: str, *, key: str | None = None, limit: int = 2000) -> List[Dict[str, Any]]:
        if key:
            rows = self.fetchall(
                "SELECT ts, key, value, json FROM run_metrics WHERE run_id=? AND key=? ORDER BY ts ASC LIMIT ?;",
                [str(run_id), str(key), int(limit)],
            )
        else:
            rows = self.fetchall(
                "SELECT ts, key, value, json FROM run_metrics WHERE run_id=? ORDER BY ts ASC LIMIT ?;",
                [str(run_id), int(limit)],
            )
        out: List[Dict[str, Any]] = []
        for ts, k, v, js in rows:
            ts_f = _finite_float_or_none(ts)
            value_f = _finite_float_or_none(v) if v is not None else None
            out.append(
                {
                    "ts": float(ts_f) if ts_f is not None else 0.0,
                    "key": str(k or ""),
                    "value": value_f,
                    "json": _json_loads(js),
                }
            )
        return out

    # ---- exports ----

    def export_run_to_csv(self, run_id: str, *args, out_dir: str | None = None) -> None:
        legacy_trials_path: Optional[Path] = None
        legacy_metrics_path: Optional[Path] = None
        if len(args) > 2:
            raise TypeError(
                "export_run_to_csv() accepts at most 2 positional args: "
                "(trials_csv_path, run_metrics_csv_path)"
            )
        if out_dir is None:
            if len(args) == 1:
                out_dir = str(args[0])
            elif len(args) == 2:
                legacy_trials_path = Path(str(args[0]))
                legacy_metrics_path = Path(str(args[1]))
                out_dir = str(legacy_trials_path.parent)
            else:
                raise TypeError("export_run_to_csv() requires out_dir or legacy csv paths")
        elif len(args) == 2:
            legacy_trials_path = Path(str(args[0]))
            legacy_metrics_path = Path(str(args[1]))

        outp = Path(out_dir)
        outp.mkdir(parents=True, exist_ok=True)

        run_detail = self.get_run(run_id) or {}
        run_scope = _export_run_scope_payload(run_detail, run_id_default=run_id)
        trials = self.fetch_trials(run_id, status=None, limit=None, order="created_ts")
        metrics = self.fetch_metrics(run_id, key=None, limit=10_000)

        def _write_run_scope_sidecars() -> None:
            run_scope_json = outp / "run_scope.json"
            with open(run_scope_json, "w", encoding="utf-8", newline="") as f_json:
                f_json.write(_json_dumps(run_scope))

            run_scope_csv = outp / "run_scope.csv"
            with open(run_scope_csv, "w", encoding="utf-8", newline="") as f_csv:
                w = csv.writer(f_csv)
                w.writerow(
                    [
                        "run_id",
                        "created_ts",
                        "backend",
                        "created_by",
                        "problem_hash",
                        "problem_hash_short",
                        "problem_hash_mode",
                        "objective_keys_json",
                        "penalty_key",
                        "penalty_tol",
                    ]
                )
                w.writerow(
                    [
                        run_scope.get("run_id", ""),
                        run_scope.get("created_ts"),
                        run_scope.get("backend", ""),
                        run_scope.get("created_by", ""),
                        run_scope.get("problem_hash", ""),
                        run_scope.get("problem_hash_short", ""),
                        run_scope.get("problem_hash_mode", ""),
                        _json_dumps(run_scope.get("objective_keys") or []),
                        run_scope.get("penalty_key", ""),
                        run_scope.get("penalty_tol"),
                    ]
                )

        _write_run_scope_sidecars()

        # Trials CSV
        trials_csv = outp / "trials.csv"
        with trials_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "run_id",
                    "problem_hash",
                    "problem_hash_mode",
                    "trial_id",
                    "status",
                    "attempt",
                    "param_hash",
                    "priority",
                    "scheduled_ts",
                    "lease_expires_ts",
                    "created_ts",
                    "started_ts",
                    "finished_ts",
                    "heartbeat_ts",
                    "worker_tag",
                    "host",
                    "x_u_json",
                    "y_json",
                    "g_json",
                    "metrics_json",
                    "error_text",
                ]
            )
            for t in trials:
                w.writerow(
                    [
                        run_scope.get("run_id", ""),
                        run_scope.get("problem_hash", ""),
                        run_scope.get("problem_hash_mode", ""),
                        t.get("trial_id", ""),
                        t.get("status", ""),
                        t.get("attempt", 0),
                        t.get("param_hash", ""),
                        t.get("priority", 0),
                        t.get("scheduled_ts"),
                        t.get("lease_expires_ts"),
                        t.get("created_ts"),
                        t.get("started_ts"),
                        t.get("finished_ts"),
                        t.get("heartbeat_ts"),
                        t.get("worker_tag", ""),
                        t.get("host", ""),
                        _json_dumps_safe(t.get("x_u")),
                        _json_dumps_safe(t.get("y")),
                        _json_dumps_safe(t.get("g")),
                        _json_dumps_safe(t.get("metrics")),
                        t.get("error_text", ""),
                    ]
                )

        # Metrics CSV
        metrics_csv = outp / "run_metrics.csv"
        with metrics_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["run_id", "problem_hash", "problem_hash_mode", "ts", "key", "value", "json"])
            for m in metrics:
                w.writerow(
                    [
                        run_scope.get("run_id", ""),
                        run_scope.get("problem_hash", ""),
                        run_scope.get("problem_hash_mode", ""),
                        m.get("ts"),
                        m.get("key"),
                        m.get("value"),
                        _json_dumps_safe(m.get("json")),
                    ]
                )

        if legacy_trials_path is not None:
            try:
                legacy_trials_path.parent.mkdir(parents=True, exist_ok=True)
                if legacy_trials_path.resolve() != trials_csv.resolve():
                    legacy_trials_path.write_bytes(trials_csv.read_bytes())
            except Exception:
                pass
        if legacy_metrics_path is not None:
            try:
                legacy_metrics_path.parent.mkdir(parents=True, exist_ok=True)
                if legacy_metrics_path.resolve() != metrics_csv.resolve():
                    legacy_metrics_path.write_bytes(metrics_csv.read_bytes())
            except Exception:
                pass

        if not (outp / "run_scope.json").exists() or not (outp / "run_scope.csv").exists():
            _write_run_scope_sidecars()
