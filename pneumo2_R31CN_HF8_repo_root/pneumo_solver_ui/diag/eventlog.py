# -*- coding: utf-8 -*-
"""pneumo_solver_ui.diag.eventlog

Единый обязательный журнал событий (warnings/errors/diagnostics).

Почему это важно
----------------
В проекте есть строгая валидация логов (tools/loglint.py) в режимах:
- autotest (tools/run_autotest.py)
- send-bundle (tools/make_send_bundle.py)

Обе системы ожидают, что JSONL-логи в папке логов будут:
- **строгим JSON** (без NaN/Inf), чтобы их уверенно читали анализаторы;
- совместимыми со схемой `ui` в режиме `--strict`.

Поэтому этот модуль пишет события сразу в schema=ui (даже если событие не из UI),
чтобы не ломать строгую проверку по папке логов.

Файлы
-----
По умолчанию:
  <repo>/pneumo_solver_ui/logs/events.jsonl
  <repo>/pneumo_solver_ui/logs/events.log

Если задана переменная окружения PNEUMO_LOG_DIR, пишем туда.

Гарантии
--------
Best-effort: любые ошибки логирования подавляются.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict


@dataclass
class EventLogPaths:
    jsonl_path: Path
    text_path: Path


def _repo_root_from(project_root: Path) -> Path:
    try:
        return project_root.resolve()
    except Exception:
        return project_root


def default_event_paths(project_root: Path) -> EventLogPaths:
    """Resolve default paths, preferring session override (PNEUMO_LOG_DIR)."""
    # prefer launcher-provided log dir (per-run isolation)
    p = (os.environ.get("PNEUMO_LOG_DIR") or "").strip()
    if p:
        try:
            log_dir = Path(p).expanduser().resolve()
            return EventLogPaths(jsonl_path=log_dir / "events.jsonl", text_path=log_dir / "events.log")
        except Exception:
            pass

    root = _repo_root_from(project_root)
    log_dir = (root / "pneumo_solver_ui" / "logs").resolve()
    return EventLogPaths(jsonl_path=log_dir / "events.jsonl", text_path=log_dir / "events.log")


class EventLogger:
    """Best-effort event logger writing strict JSONL + fallback text."""

    SCHEMA = "ui"
    SCHEMA_VERSION = "1.2.0"

    def __init__(self, project_root: Path, paths: Optional[EventLogPaths] = None):
        self.project_root = _repo_root_from(project_root)
        self.paths = paths or default_event_paths(self.project_root)

        self._seq = 0
        self._start_ts = time.time()

        # lock is optional (should not break even if threading is unavailable)
        self._lock = None
        try:
            import threading

            self._lock = threading.Lock()
        except Exception:
            self._lock = None

        # stable per-process session_id (prefer launcher run_id)
        self._session_id = self._pick_session_id()
        self._trace_id = self._pick_trace_id(self._session_id)
        self._release = self._pick_release()

        try:
            self.paths.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _pick_session_id(self) -> str:
        # Prefer run id used everywhere else (UI_YYYY...)
        for k in ("PNEUMO_RUN_ID", "PNEUMO_SESSION_ID"):
            v = (os.environ.get(k) or "").strip()
            if v:
                return v
        # Fallback: process-based id
        return f"PROC_{os.getpid()}_{int(self._start_ts)}"

    def _pick_trace_id(self, fallback: str) -> str:
        v = (os.environ.get("PNEUMO_TRACE_ID") or "").strip()
        return v or fallback or "trace"

    def _pick_release(self) -> str:
        v = (os.environ.get("PNEUMO_RELEASE") or "").strip()
        if v:
            return v
        try:
            from pneumo_solver_ui.release_info import get_release

            v2 = get_release()
            if v2:
                return str(v2)
        except Exception:
            pass
        return "UNIFIED_v6_67"

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def emit(self, event: str, message: str = "", **fields: Any) -> None:
        """Append one event record.

        Record is schema=ui strict JSONL so loglint can validate the entire log dir.
        """
        try:
            seq = self._next_seq()
            reserved = {
                "ts",
                "schema",
                "schema_version",
                "event",
                "event_id",
                "seq",
                "trace_id",
                "session_id",
                "pid",
                "release",
            }
            payload: Dict[str, Any] = {}
            extra_reserved: Dict[str, Any] = {}
            for k, v in (fields or {}).items():
                try:
                    ks = str(k)
                except Exception:
                    ks = repr(k)
                if ks in reserved:
                    extra_reserved[ks] = v
                else:
                    payload[ks] = v

            rec: Dict[str, Any] = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "schema": self.SCHEMA,
                "schema_version": self.SCHEMA_VERSION,
                "event": str(event),
                "event_id": f"e_{seq:06d}_{uuid.uuid4().hex[:8]}",
                "seq": int(seq),
                "trace_id": str(self._trace_id),
                "session_id": str(self._session_id),
                "pid": int(os.getpid()),
                "release": str(self._release),
            }
            if message:
                rec["message"] = str(message)
            if payload:
                rec.update(payload)
            if extra_reserved:
                rec["_extra_reserved"] = extra_reserved

            # strict JSONL (no NaN/Inf)
            try:
                from pneumo_solver_ui.diag.json_safe import json_dumps

                line = json_dumps(rec)
            except Exception:
                import json

                line = json.dumps(rec, ensure_ascii=False, default=str, allow_nan=False)

            # JSONL append
            self._append_jsonl(line)

            # also write compact text line (human-friendly)
            self._append_text(f"[{rec['ts']}] {event}: {message} {payload}\n")

        except Exception:
            return

    def _append_jsonl(self, line: str) -> None:
        try:
            if self._lock is not None:
                with self._lock:
                    self.paths.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.paths.jsonl_path, "a", encoding="utf-8", errors="replace") as f:
                        f.write(line + "\n")
            else:
                self.paths.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.paths.jsonl_path, "a", encoding="utf-8", errors="replace") as f:
                    f.write(line + "\n")
        except Exception:
            return

    def _append_text(self, text: str) -> None:
        try:
            if self._lock is not None:
                with self._lock:
                    self.paths.text_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.paths.text_path, "a", encoding="utf-8", errors="replace") as f:
                        f.write(text)
            else:
                self.paths.text_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.paths.text_path, "a", encoding="utf-8", errors="replace") as f:
                    f.write(text)
        except Exception:
            return


_GLOBAL: Optional[EventLogger] = None


def get_global_logger(project_root: Path) -> EventLogger:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = EventLogger(project_root)
    return _GLOBAL
