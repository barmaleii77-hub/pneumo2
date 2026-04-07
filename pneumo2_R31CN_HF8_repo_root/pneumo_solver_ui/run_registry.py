# -*- coding: utf-8 -*-
"""pneumo_solver_ui.run_registry (Testy R56)

Единый "реестр прогонов" (run registry) + журнал событий уровня системы.

Зачем
-----
В проекте есть множество независимых процессов/скриптов:
- Streamlit UI
- autotest harness
- full diagnostics
- postmortem watchdog
- сборка send bundle

Нужно иметь *один* устойчивый источник правды "что запускалось / чем завершилось / где артефакты".
Этот модуль пишет append-only JSONL, а отчёты (triage/dashboard) его читают.

Файлы (в корне репозитория)
---------------------------
runs/
  run_registry.jsonl   # append-only JSON lines
  index.json           # маленький индекс (последнее событие + счётчики)
  README_RUNS.txt      # человекочитаемое описание

Требования
----------
- best-effort: модуль никогда не должен ронять вызывающий код
- минимум зависимостей (stdlib only)
- корректная работа и на Windows, и на Linux

Формат событий
--------------
Минимально ожидаемые поля:
  ts: ISO-время (строка)
  ts_unix: float (unix time)
  event: "run_start" | "run_end" | "send_bundle_created" | ...
  run_type: "ui_session" | "autotest" | "diagnostics" | ...
  run_id: строковый идентификатор (например UI_20260127_040000)

Дополнительные поля приветствуются (rc, status, zip_path, sha256 и т.д.).

"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


def _repo_root() -> Path:
    # .../<repo>/pneumo_solver_ui/run_registry.py -> parents[1] == <repo>
    return Path(__file__).resolve().parents[1]


def _runs_root() -> Path:
    return _repo_root() / "runs"


def _now_unix() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_runs_files() -> None:
    """Create runs/ folder and README if absent (best-effort)."""
    runs = _runs_root()
    try:
        runs.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    readme = runs / "README_RUNS.txt"
    if not readme.exists():
        try:
            readme.write_text(
                (
                    "runs/ — системный реестр прогонов (Testy R56)\n"
                    "\n"
                    "Файлы:\n"
                    "  run_registry.jsonl — append-only JSONL события\n"
                    "  index.json         — индекс: last_event + counters\n"
                    "\n"
                    "Это *не* замена подробным логам, а слой 'кто/когда/чем кончил'.\n"
                ),
                encoding="utf-8",
            )
        except Exception:
            pass


@contextmanager
def _maybe_lock(timeout_s: float = 1.5):
    """Best-effort межпроцессный lock (чтобы JSONL не перемешивался).

    Если lock взять нельзя — всё равно продолжаем (журнал не должен блокировать систему).
    """
    try:
        from pneumo_solver_ui.tools.bundle_lock import SendBundleLock

        lock_path = _runs_root() / "._run_registry.lock"
        lk = SendBundleLock(lock_path, timeout_s=float(timeout_s), poll_s=0.05, stale_ttl_s=60.0, release=RELEASE)
        try:
            lk.acquire()
            try:
                yield
            finally:
                try:
                    lk.release_lock()
                except Exception:
                    pass
        except Exception:
            # lock timeout / file issues -> proceed without lock
            yield
    except Exception:
        yield


def _json_dumps(obj: Any) -> str:
    """Strict JSON (best-effort).

    Важно: артефакты реестра используются при сборке send-bundle и диагностике.
    Не допускаем NaN/Inf и не ломаемся на не-сериализуемых объектах.
    """
    try:
        from pneumo_solver_ui.diag.json_safe import json_dumps as _json_dumps_strict
        return _json_dumps_strict(obj)
    except Exception:
        return json.dumps(obj, ensure_ascii=False, default=str)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _write_json_atomic(path: Path, payload: dict) -> None:
    """Atomic write (best-effort)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(_json_dumps(payload), encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception:
        # fallback
        try:
            path.write_text(_json_dumps(payload), encoding="utf-8")
        except Exception:
            pass


def env_context() -> Dict[str, Any]:
    """Снимок окружения (не огромный) для репродукции и triage."""
    keys = [
        "PNEUMO_RELEASE",
        "PNEUMO_RUN_ID",
        "PNEUMO_TRACE_ID",
        "PNEUMO_SESSION_DIR",
        "PNEUMO_LOG_DIR",
        "PNEUMO_WORKSPACE_DIR",
        "PNEUMO_UI_PORT",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTHONWARNINGS",
    ]
    env = {k: os.environ.get(k) for k in keys if os.environ.get(k) is not None}
    return {
        "release": env.get("PNEUMO_RELEASE") or RELEASE,
        "pid": os.getpid(),
        "ppid": os.getppid() if hasattr(os, "getppid") else None,
        "cwd": os.getcwd(),
        "exe": sys.executable,
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "env": env,
    }


def _event_summary(rec: Dict[str, Any]) -> Dict[str, Any]:
    keep = [
        "ts",
        "event",
        "run_type",
        "run_id",
        "status",
        "rc",
        "zip_path",
        "latest_zip_path",
        "sha256",
        "validation_ok",
        "dashboard_created",
        "anim_latest_visual_cache_token",
        "anim_latest_visual_reload_inputs",
        "anim_latest_updated_utc",
        "anim_latest_pointer_json",
        "anim_latest_npz_path",
    ]
    out: Dict[str, Any] = {}
    for k in keep:
        v = rec.get(k)
        if v is not None:
            out[k] = v
    return out


def append_event(record: Dict[str, Any]) -> None:
    """Append one record to runs/run_registry.jsonl (best-effort)."""
    try:
        _ensure_runs_files()
        runs = _runs_root()
        jsonl_path = runs / "run_registry.jsonl"
        index_path = runs / "index.json"

        # normalize timestamps
        rec = dict(record or {})
        ts_val = rec.get("ts")
        if isinstance(ts_val, (int, float)):
            rec.setdefault("ts_unix", float(ts_val))
        rec["ts"] = rec.get("ts") if isinstance(rec.get("ts"), str) else _now_iso()
        rec.setdefault("ts_unix", float(rec.get("ts_unix") or _now_unix()))

        rec.setdefault("pid", os.getpid())
        rec.setdefault("release", RELEASE)

        line = _json_dumps(rec)

        with _maybe_lock():
            try:
                with open(jsonl_path, "a", encoding="utf-8", errors="replace") as f:
                    f.write(line + "\n")
            except Exception:
                pass

            # update index.json (small)
            try:
                idx = _read_json(index_path)
                if not isinstance(idx, dict):
                    idx = {}
                counters = idx.get("counters")
                if not isinstance(counters, dict):
                    counters = {}
                counters["events_total"] = int(counters.get("events_total") or 0) + 1
                idx["counters"] = counters
                idx["updated_at"] = _now_iso()
                idx["last_event"] = _event_summary(rec)
                _write_json_atomic(index_path, idx)
            except Exception:
                pass

    except Exception:
        # never raise
        return


def start_run(run_type: str, run_id: str, **fields: Any) -> str:
    """Write run_start and return token for end_run()."""
    try:
        token = f"{run_type}|{run_id}|{uuid.uuid4().hex[:12]}"
        rec = {
            "event": "run_start",
            "run_type": str(run_type),
            "run_id": str(run_id),
            "token": token,
            "status": "running",
            **fields,
        }
        append_event(rec)
        return token
    except Exception:
        return f"{run_type}|{run_id}|{uuid.uuid4().hex[:12]}"


def end_run(token: str, *, status: str = "done", rc: Optional[int] = None, **fields: Any) -> None:
    """Write run_end for a token returned from start_run()."""
    try:
        run_type = "unknown"
        run_id = "unknown"
        try:
            parts = str(token).split("|", 2)
            if len(parts) >= 2:
                run_type, run_id = parts[0], parts[1]
        except Exception:
            pass

        rec: Dict[str, Any] = {
            "event": "run_end",
            "run_type": str(run_type),
            "run_id": str(run_id),
            "token": str(token),
            "status": str(status),
            **fields,
        }
        if rc is not None:
            rec["rc"] = int(rc)
        append_event(rec)
    except Exception:
        return


def log_send_bundle_created(
    *,
    zip_path: str,
    sha256: Optional[str] = None,
    meta: Optional[dict] = None,
    validation_ok: Optional[bool] = None,
    validation_errors: Optional[int] = None,
    validation_warnings: Optional[int] = None,
    latest_zip_path: Optional[str] = None,
    size_bytes: Optional[int] = None,
    release: Optional[str] = None,
    primary_session_dir: Optional[str] = None,
    dashboard_created: Optional[bool] = None,
    dashboard_html_path: Optional[str] = None,
    env: Optional[dict] = None,
    anim_latest_available: Optional[bool] = None,
    anim_latest_global_pointer_json: Optional[str] = None,
    anim_latest_pointer_json: Optional[str] = None,
    anim_latest_npz_path: Optional[str] = None,
    anim_latest_visual_cache_token: Optional[str] = None,
    anim_latest_visual_reload_inputs: Optional[list] = None,
    anim_latest_visual_cache_dependencies: Optional[dict] = None,
    anim_latest_updated_utc: Optional[str] = None,
    **extra: Any,
) -> None:
    """Convenience event for send bundle creation.

    The helper is intentionally permissive: make_send_bundle / launcher / watchdog
    may evolve independently, so unknown future fields must not break registry
    logging.
    """
    try:
        rec: Dict[str, Any] = {
            "event": "send_bundle_created",
            "run_type": "send_bundle",
            "run_id": os.environ.get("PNEUMO_RUN_ID") or "SEND_BUNDLE",
            "zip_path": str(zip_path),
        }
        if sha256 is not None:
            rec["sha256"] = str(sha256)
        if latest_zip_path is not None:
            rec["latest_zip_path"] = str(latest_zip_path)
        if size_bytes is not None:
            rec["size_bytes"] = int(size_bytes)
        if release is not None:
            rec["release"] = str(release)
        if primary_session_dir is not None:
            rec["primary_session_dir"] = str(primary_session_dir)
        if dashboard_created is not None:
            rec["dashboard_created"] = bool(dashboard_created)
        if dashboard_html_path is not None:
            rec["dashboard_html_path"] = str(dashboard_html_path)
        if env is not None:
            rec["env"] = env
        if meta is not None:
            rec["meta"] = meta
        if validation_ok is not None:
            rec["validation_ok"] = bool(validation_ok)
        if validation_errors is not None:
            rec["validation_errors"] = int(validation_errors)
        if validation_warnings is not None:
            rec["validation_warnings"] = int(validation_warnings)
        if anim_latest_available is not None:
            rec["anim_latest_available"] = bool(anim_latest_available)
        if anim_latest_global_pointer_json is not None:
            rec["anim_latest_global_pointer_json"] = str(anim_latest_global_pointer_json)
        if anim_latest_pointer_json is not None:
            rec["anim_latest_pointer_json"] = str(anim_latest_pointer_json)
        if anim_latest_npz_path is not None:
            rec["anim_latest_npz_path"] = str(anim_latest_npz_path)
        if anim_latest_visual_cache_token is not None:
            rec["anim_latest_visual_cache_token"] = str(anim_latest_visual_cache_token)
        if anim_latest_visual_reload_inputs is not None:
            rec["anim_latest_visual_reload_inputs"] = list(anim_latest_visual_reload_inputs)
        if anim_latest_visual_cache_dependencies is not None:
            rec["anim_latest_visual_cache_dependencies"] = dict(anim_latest_visual_cache_dependencies)
        if anim_latest_updated_utc is not None:
            rec["anim_latest_updated_utc"] = str(anim_latest_updated_utc)
        if extra:
            rec.update({str(k): v for k, v in extra.items() if v is not None})
        append_event(rec)
    except Exception:
        return


def safe_log_exception(where: str, exc: BaseException) -> None:
    """Helper: log exception as event (best-effort)."""
    try:
        append_event(
            {
                "event": "exception",
                "where": str(where),
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )
    except Exception:
        return
