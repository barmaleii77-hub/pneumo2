from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore


def resolve_osc_dir(default_dir: Path, session_state: Mapping[str, Any] | None = None) -> Path:
    """Return current osc_dir from session state or fall back to workspace default."""
    state = session_state
    if state is None:
        try:
            state = getattr(st, "session_state", None)
        except Exception:
            state = None
    try:
        p = state.get("osc_dir_path") if state is not None else None
        if isinstance(p, str) and p.strip():
            return Path(p).expanduser()
    except Exception:
        pass
    return Path(default_dir)


def load_suite(path: Path) -> list[dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            suite = json.load(f)
        if isinstance(suite, list):
            return suite
    except Exception:
        pass
    return []


def load_default_suite_disabled(path: Path) -> list[dict[str, Any]]:
    rows = load_suite(path)
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            rec = dict(row)
        except Exception:
            continue
        rec["включен"] = False
        out.append(rec)
    return out


__all__ = [
    "load_default_suite_disabled",
    "load_suite",
    "resolve_osc_dir",
]
