#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""log2sqlite.py

Импорт JSONL-логов (UI/Harness) в SQLite для быстрых агрегаций, long-runs и RCA.

Почему SQLite
-------------
JSONL (NDJSON) идеален для потока событий и простого append, но на длинных прогонах
становится неудобно делать запросы вида:
- "топ событий по частоте",
- "все error-like события",
- "все span_end с длительностью > X",
- "сравнить несколько прогонов по KPI".

SQLite даёт:
- один файл-артефакт,
- SQL-агрегации без внешней БД,
- индексы и быстрые фильтры,
- удобную интеграцию в CI/harness.

Использование
-------------
Импорт одного файла:
  python pneumo_solver_ui/tools/log2sqlite.py --input path/to/log.jsonl --db run/metrics.sqlite --source ui

Импорт папки рекурсивно:
  python pneumo_solver_ui/tools/log2sqlite.py --input run/logs --recursive --db run/metrics.sqlite --source ui --append

Только отчёт по уже созданной БД:
  python pneumo_solver_ui/tools/log2sqlite.py --db run/metrics.sqlite --report_only

"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


TOOL_VERSION = "R39"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _to_jsonable(x: Any) -> Any:
    """Best-effort конвертация к JSON-совместимому виду + NaN/Inf -> None."""
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return bool(x)
        if isinstance(x, int):
            return int(x)
        if isinstance(x, float):
            try:
                if not math.isfinite(float(x)):
                    return None
            except Exception:
                return None
            return float(x)
        if isinstance(x, str):
            return x
        if isinstance(x, Path):
            return str(x)
        if isinstance(x, bytes):
            try:
                return x.decode("utf-8", errors="replace")
            except Exception:
                return repr(x)

        # numpy scalar / array-like
        try:
            import numpy as _np  # type: ignore

            if isinstance(x, _np.generic):
                return _to_jsonable(x.item())
        except Exception:
            pass

        if hasattr(x, "tolist"):
            try:
                return _to_jsonable(x.tolist())  # type: ignore[attr-defined]
            except Exception:
                pass

        if isinstance(x, dict):
            return {str(k): _to_jsonable(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [_to_jsonable(v) for v in list(x)]

        return str(x)
    except Exception:
        return repr(x)


def _json_dumps(obj: Any) -> str:
    try:
        return json.dumps(_to_jsonable(obj), ensure_ascii=False, allow_nan=False)
    except Exception:
        return json.dumps({"_nonserializable": repr(obj)}, ensure_ascii=False, allow_nan=False)


def _iter_jsonl_files(path: Path, recursive: bool) -> List[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    if recursive:
        return sorted([p for p in path.rglob("*.jsonl") if p.is_file()])
    return sorted([p for p in path.glob("*.jsonl") if p.is_file()])


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            file TEXT,
            line INTEGER,
            ts TEXT,
            schema TEXT,
            schema_version TEXT,
            event TEXT,
            level TEXT,
            run_id TEXT,
            session_id TEXT,
            trace_id TEXT,
            span_id TEXT,
            parent_span_id TEXT,
            span_name TEXT,
            duration_ms REAL,
            seq INTEGER,
            pid INTEGER,
            thread_id INTEGER,
            json TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);")
    conn.commit()


def _set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (str(key), _json_dumps(value)))


def _extract(rec: Dict[str, Any], key: str) -> Any:
    v = rec.get(key)
    if v is None:
        return None
    # normalize ints
    if key in {"seq", "pid", "thread_id", "line"}:
        try:
            return int(v)
        except Exception:
            return None
    if key in {"duration_ms"}:
        try:
            return float(v)
        except Exception:
            return None
    if isinstance(v, (str, int, float)):
        return v
    return _to_jsonable(v)


@dataclass
class ImportStats:
    files: int = 0
    records: int = 0
    errors: int = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None


def import_jsonl_to_sqlite(
    conn: sqlite3.Connection,
    input_path: Path,
    recursive: bool,
    source: str,
    max_errors: int = 50,
    commit_every: int = 2000,
) -> Tuple[ImportStats, List[str]]:
    """Импортирует jsonl-файлы в SQLite. Возвращает статистику и список ошибок."""
    files = _iter_jsonl_files(input_path, recursive)
    stats = ImportStats(files=len(files))
    errors: List[str] = []

    buf: List[Tuple[Any, ...]] = []

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        conn.executemany(
            """
            INSERT INTO events(
                source,file,line,ts,schema,schema_version,event,level,run_id,session_id,trace_id,
                span_id,parent_span_id,span_name,duration_ms,seq,pid,thread_id,json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            buf,
        )
        conn.commit()
        buf = []

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    line = line.strip("\n")
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                        if not isinstance(rec, dict):
                            raise ValueError("record is not an object")
                    except Exception as e:
                        stats.errors += 1
                        msg = f"{fp}:{i}: JSON parse error: {e}"
                        errors.append(msg)
                        if stats.errors >= max_errors:
                            flush()
                            return stats, errors
                        continue

                    ts = _extract(rec, "ts")
                    if isinstance(ts, str):
                        if stats.first_ts is None:
                            stats.first_ts = ts
                        stats.last_ts = ts

                    row = (
                        str(source),
                        str(fp),
                        int(i),
                        ts if isinstance(ts, str) else None,
                        _extract(rec, "schema"),
                        _extract(rec, "schema_version"),
                        _extract(rec, "event"),
                        _extract(rec, "level"),
                        _extract(rec, "run_id"),
                        _extract(rec, "session_id"),
                        _extract(rec, "trace_id"),
                        _extract(rec, "span_id"),
                        _extract(rec, "parent_span_id"),
                        _extract(rec, "span_name"),
                        _extract(rec, "duration_ms"),
                        _extract(rec, "seq"),
                        _extract(rec, "pid"),
                        _extract(rec, "thread_id"),
                        _json_dumps(rec),
                    )
                    buf.append(row)
                    stats.records += 1
                    if len(buf) >= commit_every:
                        flush()
        except Exception as e:
            stats.errors += 1
            errors.append(f"{fp}: file read error: {e}")
            if stats.errors >= max_errors:
                flush()
                return stats, errors

    flush()
    return stats, errors


def make_report(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Небольшой отчёт: counts, top events, error-like events, span durations."""
    rep: Dict[str, Any] = {"generated_at": _now_iso(), "tool_version": TOOL_VERSION}
    cur = conn.cursor()

    def q1(sql: str, params: Tuple[Any, ...] = ()) -> Any:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None

    rep["events_total"] = q1("SELECT COUNT(*) FROM events;")
    rep["events_by_source"] = []
    cur.execute("SELECT source, COUNT(*) c FROM events GROUP BY source ORDER BY c DESC;")
    for src, c in cur.fetchall():
        rep["events_by_source"].append({"source": src, "count": int(c)})

    rep["top_events"] = []
    cur.execute("SELECT event, COUNT(*) c FROM events GROUP BY event ORDER BY c DESC LIMIT 20;")
    for ev, c in cur.fetchall():
        rep["top_events"].append({"event": ev, "count": int(c)})

    # error-like: level == error OR event contains 'error'/'exception'
    rep["error_like"] = []
    cur.execute(
        """
        SELECT event, COUNT(*) c
        FROM events
        WHERE (LOWER(COALESCE(level,'')) IN ('error','fatal'))
           OR (LOWER(COALESCE(event,'')) LIKE '%error%')
           OR (LOWER(COALESCE(event,'')) LIKE '%exception%')
        GROUP BY event
        ORDER BY c DESC
        LIMIT 20;
        """
    )
    for ev, c in cur.fetchall():
        rep["error_like"].append({"event": ev, "count": int(c)})

    rep["spans_slowest"] = []
    cur.execute(
        """
        SELECT event, duration_ms, ts, source, file
        FROM events
        WHERE duration_ms IS NOT NULL
        ORDER BY duration_ms DESC
        LIMIT 20;
        """
    )
    for ev, d, ts, src, file in cur.fetchall():
        rep["spans_slowest"].append(
            {"event": ev, "duration_ms": float(d), "ts": ts, "source": src, "file": file}
        )

    rep["first_ts"] = q1("SELECT MIN(ts) FROM events WHERE ts IS NOT NULL;")
    rep["last_ts"] = q1("SELECT MAX(ts) FROM events WHERE ts IS NOT NULL;")

    return rep


def report_to_md(rep: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# SQLite log report")
    lines.append("")
    lines.append(f"- generated_at: `{rep.get('generated_at')}`")
    lines.append(f"- tool_version: `{rep.get('tool_version')}`")
    lines.append(f"- events_total: **{rep.get('events_total')}**")
    lines.append("")

    lines.append("## Events by source")
    for x in rep.get("events_by_source", []):
        lines.append(f"- {x.get('source')}: {x.get('count')}")

    lines.append("")
    lines.append("## Top events")
    for x in rep.get("top_events", [])[:20]:
        lines.append(f"- {x.get('event')}: {x.get('count')}")

    lines.append("")
    lines.append("## Error-like events")
    for x in rep.get("error_like", [])[:20]:
        lines.append(f"- {x.get('event')}: {x.get('count')}")

    lines.append("")
    lines.append("## Slowest spans (by duration_ms)")
    for x in rep.get("spans_slowest", [])[:20]:
        lines.append(f"- {x.get('duration_ms')} ms | {x.get('event')} | {x.get('source')} | {Path(str(x.get('file',''))).name}")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", default=[], help="Путь к jsonl-файлу или папке (можно несколько)")
    ap.add_argument("--recursive", action="store_true", help="Если input=папка, искать *.jsonl рекурсивно")
    ap.add_argument("--db", required=True, help="Путь к SQLite файлу (будет создан)")
    ap.add_argument("--source", default="auto", help="Метка источника (ui/harness/...)")
    ap.add_argument("--append", action="store_true", help="Не удалять БД перед импортом (добавлять)")
    ap.add_argument("--max_errors", type=int, default=50)
    ap.add_argument("--commit_every", type=int, default=2000)
    ap.add_argument("--no_indexes", action="store_true")
    ap.add_argument("--out_dir", default=None, help="Куда писать отчёты (по умолчанию рядом с db)")
    ap.add_argument("--report_only", action="store_true", help="Только отчёт по существующей БД, без импорта")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else db_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.append and not args.report_only and db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    conn = _connect(db_path)
    _init_db(conn)

    _set_meta(conn, "tool_version", TOOL_VERSION)
    _set_meta(
        conn,
        "env",
        {
            "python": sys.version,
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
    )
    _set_meta(conn, "updated_at", _now_iso())
    conn.commit()

    stats_all: List[Dict[str, Any]] = []
    errors_all: List[str] = []

    if not args.report_only:
        if not args.input:
            print("ERROR: --input is required unless --report_only is used", file=sys.stderr)
            return 2

        for inp in args.input:
            st, errs = import_jsonl_to_sqlite(
                conn,
                Path(inp).expanduser().resolve(),
                recursive=bool(args.recursive),
                source=str(args.source),
                max_errors=int(args.max_errors),
                commit_every=int(args.commit_every),
            )
            stats_all.append(
                {
                    "input": inp,
                    "files": st.files,
                    "records": st.records,
                    "errors": st.errors,
                    "first_ts": st.first_ts,
                    "last_ts": st.last_ts,
                }
            )
            errors_all.extend(errs)

    if not args.no_indexes:
        _ensure_indexes(conn)

    # report
    rep = make_report(conn)
    rep["imports"] = stats_all
    rep["errors"] = errors_all[: int(args.max_errors)]

    (out_dir / "sqlite_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "sqlite_report.md").write_text(report_to_md(rep), encoding="utf-8")

    # human-friendly stdout
    print(f"[log2sqlite] db={db_path}")
    print(f"[log2sqlite] events_total={rep.get('events_total')}")
    for x in rep.get("events_by_source", []):
        print(f"[log2sqlite] source {x.get('source')}: {x.get('count')}")

    if errors_all:
        print(f"[log2sqlite] errors={len(errors_all)} (see sqlite_report.json)", file=sys.stderr)
        return 10

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
