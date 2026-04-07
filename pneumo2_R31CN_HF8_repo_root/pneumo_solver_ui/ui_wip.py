"""UI helpers for WIP / IN_DEV pages.

This module is intentionally lightweight and safe to import from `page_registry`.
It provides a consistent banner that makes "в разработке" status explicit without
silently disabling execution.

Design goals:
- No heavy imports (model/solver).
- Works with Streamlit module passed explicitly (to match call sites).
- Safe to call multiple times.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WipInfo:
    """Metadata shown in the WIP banner."""

    title: str
    reason: str = ""
    what_next: str = ""


def render_wip_banner(st, info: WipInfo) -> None:
    """Render a WIP banner at the top of a page.

    Parameters
    ----------
    st:
        Streamlit module (usually imported as `import streamlit as st`).
        We accept it as a parameter to avoid global imports and to be compatible
        with call sites that pass the module explicitly.
    info:
        WipInfo structure.
    """

    try:
        st.warning(f"🚧 В разработке: {info.title}")
    except Exception:
        # If Streamlit API changed, do not crash the page.
        return

    if info.reason:
        try:
            st.caption(info.reason)
        except Exception:
            pass

    if info.what_next:
        try:
            st.info(info.what_next)
        except Exception:
            pass

    try:
        st.markdown("---")
    except Exception:
        pass
