from __future__ import annotations

"""Best-effort readiness helpers for the Streamlit launcher.

Why:
- Windows runs showed false negatives from the HTTP health probe (``/_stcore/health``
  returning 502) while the UI session had already bootstrapped and produced
  normal session logs.
- Killing/marking such runs as failed makes the optimization pipeline look dead
  even when Streamlit is alive and the user can work in the browser.

This helper provides a secondary readiness signal based on session logs that are
created by the child process under ``PNEUMO_LOG_DIR``.
"""

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

_READY_EVENTS: tuple[str, ...] = (
    "autoselfcheck_v1",
    "ui_start",
)

_STREAMLIT_READY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bLocal URL:\b", re.IGNORECASE),
    re.compile(r"\bNetwork URL:\b", re.IGNORECASE),
    re.compile(r"You can now view your Streamlit app", re.IGNORECASE),
)


def _tail_lines(path: Path, max_lines: int = 160) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    if not text:
        return []
    lines = text.splitlines()
    if max_lines > 0:
        lines = lines[-max_lines:]
    return [line for line in lines if line.strip()]


def _scan_jsonl_for_ready(path: Path, max_lines: int) -> tuple[bool, Dict[str, Any]]:
    events_seen: List[str] = []
    for line in _tail_lines(path, max_lines=max_lines):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        evt = str(obj.get("event") or "").strip()
        if evt:
            events_seen.append(evt)
        if evt in _READY_EVENTS:
            return True, {
                "source": str(path),
                "ready_via": "event",
                "ready_event": evt,
                "ready_ts": obj.get("ts"),
                "events_seen_tail": events_seen[-20:],
            }
    return False, {
        "source": str(path),
        "ready_via": None,
        "ready_event": None,
        "ready_ts": None,
        "events_seen_tail": events_seen[-20:],
    }


def _scan_text_for_ready(path: Path, max_lines: int) -> tuple[bool, Dict[str, Any]]:
    lines = _tail_lines(path, max_lines=max_lines)
    for line in lines:
        for pat in _STREAMLIT_READY_PATTERNS:
            if pat.search(line):
                return True, {
                    "source": str(path),
                    "ready_via": "streamlit_log",
                    "ready_event": pat.pattern,
                    "ready_ts": None,
                    "events_seen_tail": [],
                }
    return False, {
        "source": str(path),
        "ready_via": None,
        "ready_event": None,
        "ready_ts": None,
        "events_seen_tail": [],
    }


def session_log_ready(log_dir: str | Path, *, max_lines: int = 160) -> tuple[bool, Dict[str, Any]]:
    """Return a secondary readiness signal derived from child session logs.

    The launcher sets ``PNEUMO_LOG_DIR`` for the child process. Once the child
    gets far enough to emit ``autoselfcheck_v1`` / ``ui_start`` events, the UI is
    effectively bootstrapped even if the HTTP health endpoint still answers 502.
    """
    root = Path(log_dir)
    candidates: list[tuple[Path, str]] = [
        (root / "events.jsonl", "jsonl"),
        (root / "ui_combined.log", "jsonl"),
        (root / "streamlit_stdout.log", "text"),
    ]
    checked: List[str] = []
    best_diag: Dict[str, Any] = {
        "checked_files": checked,
        "ready_via": None,
        "ready_event": None,
        "ready_ts": None,
        "source": None,
        "events_seen_tail": [],
    }
    for path, mode in candidates:
        checked.append(str(path))
        if not path.exists():
            continue
        if mode == "jsonl":
            ok, diag = _scan_jsonl_for_ready(path, max_lines=max_lines)
        else:
            ok, diag = _scan_text_for_ready(path, max_lines=max_lines)
        diag["checked_files"] = checked[:]
        if ok:
            return True, diag
        # keep the richest diagnostic from the last existing file we checked
        if diag.get("events_seen_tail") or path.exists():
            best_diag = diag
    best_diag["checked_files"] = checked
    return False, best_diag


__all__ = ["session_log_ready"]
