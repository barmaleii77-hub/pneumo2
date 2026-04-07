from __future__ import annotations

import os
import uuid
from typing import Any

import streamlit as st

from pneumo_solver_ui.streamlit_compat import request_rerun

try:
    import psutil  # type: ignore

    _HAS_PSUTIL = True
except Exception:
    psutil = None  # type: ignore
    _HAS_PSUTIL = False


def get_ui_nonce() -> str:
    """Короткий nonce на сессию UI."""
    n = st.session_state.get("_ui_nonce")
    if not n:
        n = uuid.uuid4().hex[:8]
        st.session_state["_ui_nonce"] = n
    return str(n)


def proc_metrics() -> dict[str, Any]:
    """Снимок метрик процесса (CPU/RAM) — best effort."""
    if not _HAS_PSUTIL or psutil is None:
        return {}
    out: dict[str, Any] = {}
    try:
        p = psutil.Process(os.getpid())
        out["pid"] = p.pid
    except Exception:
        return {}
    try:
        mem = p.memory_info()
        out["rss_mb"] = round(mem.rss / 1024 / 1024, 1)
        out["vms_mb"] = round(mem.vms / 1024 / 1024, 1)
    except Exception:
        pass
    try:
        out["cpu_num"] = p.cpu_num()
    except Exception:
        pass
    try:
        out["cpu_count"] = psutil.cpu_count(logical=True)
    except Exception:
        pass
    try:
        out["cpu_percent"] = p.cpu_percent(interval=None)
    except Exception:
        pass
    return out


def is_any_fallback_anim_playing() -> bool:
    """True если где-либо активен Play в fallback-анимации (2D/3D)."""
    try:
        for k, v in st.session_state.items():
            if not isinstance(k, str):
                continue
            if not k.endswith("::play"):
                continue
            if not (k.startswith("mech2d_fb_") or k.startswith("mech3d_fb_")):
                continue
            if bool(v):
                return True
    except Exception:
        return False
    return False


def pid_alive(p: Any | None) -> bool:
    return p is not None and (p.poll() is None)


def do_rerun() -> None:
    """Best-effort rerun helper for old/new Streamlit builds."""
    request_rerun(st)
    return


__all__ = [
    "do_rerun",
    "get_ui_nonce",
    "is_any_fallback_anim_playing",
    "pid_alive",
    "proc_metrics",
]
