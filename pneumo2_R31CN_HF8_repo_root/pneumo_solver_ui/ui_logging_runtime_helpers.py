from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, MutableMapping, Optional


_UI_LOG_WRITE_LOCK: Any = None


def prepare_runtime_log_dir(log_dir: Optional[Path]) -> Optional[Path]:
    """Create the UI log directory when possible, otherwise disable file logging."""

    if log_dir is None:
        return None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return log_dir


def configure_runtime_ui_logger(
    name: str = "pneumo_ui",
    *,
    level: int = logging.INFO,
) -> logging.Logger:
    """Return a non-propagating logger configured for UI file logging."""

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def publish_session_callback(
    session_state: MutableMapping[str, Any],
    key: str,
    callback: Any,
) -> bool:
    """Best-effort publication of a callable into session state."""

    try:
        session_state[key] = callback
    except Exception:
        return False
    return True


def ensure_runtime_file_logger(
    session_state: MutableMapping[str, Any],
    *,
    logger: logging.Logger,
    log_dir: Optional[Path],
    prefer_env_run_id: bool = False,
    set_session_started: bool = False,
    now_fn: Callable[[], datetime] = datetime.now,
    time_fn: Callable[[], float] = time.time,
) -> Optional[str]:
    """Ensure a single rotating UI log handler is attached for this session."""

    if log_dir is None:
        return None

    if "_log_path" not in session_state:
        sid = session_state.get("_session_id")
        if not sid:
            sid = ""
            if prefer_env_run_id:
                sid = (os.environ.get("PNEUMO_RUN_ID") or "").strip()
            if not sid:
                sid = now_fn().strftime("%Y%m%d_%H%M%S") + f"_pid{os.getpid()}"
            session_state["_session_id"] = sid
            if set_session_started:
                session_state.setdefault("_session_started", time_fn())
        session_state["_log_path"] = str((log_dir / f"ui_{sid}.log").resolve())

    log_path = session_state.get("_log_path")
    if not log_path:
        return None

    for handler in list(logger.handlers):
        if isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", None) == log_path:
            return str(log_path)

    try:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    except Exception:
        return None
    return str(log_path)


def append_ui_log_lines(
    log_dir: Optional[Path],
    *,
    session_id: str,
    session_metrics_line: str,
    combined_metrics_line: Optional[str] = None,
    combined_text_line: Optional[str] = None,
    use_lock: bool = False,
    errors: Optional[str] = None,
) -> None:
    if log_dir is None:
        return

    mp = log_dir / f"metrics_{session_id}.jsonl"
    mcp = log_dir / "metrics_combined.jsonl"
    ucp = log_dir / "ui_combined.log"
    if combined_metrics_line is None:
        combined_metrics_line = session_metrics_line

    open_kwargs = {"encoding": "utf-8"}
    if errors is not None:
        open_kwargs["errors"] = errors

    def _write_lines() -> None:
        with open(mp, "a", **open_kwargs) as handle:
            handle.write(session_metrics_line + "\n")
        with open(mcp, "a", **open_kwargs) as handle:
            handle.write(str(combined_metrics_line) + "\n")
        if combined_text_line is not None:
            try:
                with open(ucp, "a", **open_kwargs) as handle:
                    handle.write(combined_text_line + "\n")
            except Exception:
                pass

    if not use_lock:
        _write_lines()
        return

    global _UI_LOG_WRITE_LOCK
    if _UI_LOG_WRITE_LOCK is None:
        try:
            import threading

            _UI_LOG_WRITE_LOCK = threading.Lock()
        except Exception:
            _UI_LOG_WRITE_LOCK = False

    try:
        if _UI_LOG_WRITE_LOCK:
            with _UI_LOG_WRITE_LOCK:
                _write_lines()
        else:
            _write_lines()
    except Exception:
        pass
