# -*- coding: utf-8 -*-
"""Streamlit compatibility helpers.

This module exists to make multi-page navigation robust.

Key rule: in a Streamlit multi-page app, `st.set_page_config()` should be executed only once
(by the main entry-point). Many legacy pages historically called it themselves.

`safe_set_page_config()` makes those pages usable both standalone and under the unified app.
"""

from __future__ import annotations

from typing import Any


def safe_set_page_config(**kwargs: Any) -> None:
    """Call `st.set_page_config` but don't crash if it was already called.

    Streamlit throws StreamlitAPIException: 'set_page_config can only be called once'
    when a page script tries to call it after the main app already configured the page.

    We intentionally silence only that specific situation.
    """

    # Import inside function to keep non-Streamlit tools (CLI/QC) lightweight.
    import streamlit as st

    try:
        st.set_page_config(**kwargs)
        return
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        # Typical Streamlit messages (may change across versions):
        if (
            'set_page_config' in msg
            and ('can only be called once' in msg or 'must be called as the first' in msg)
        ):
            return
        raise

def request_rerun(st_mod: Any | None = None) -> bool:
    """Request a Streamlit script rerun across old/new Streamlit versions.

    Returns True when a rerun API is available and was invoked.
    Returns False when the current Streamlit build exposes neither rerun entrypoint.

    Important: when a rerun API exists, this function intentionally lets Streamlit's
    internal rerun exception propagate so the current script stops immediately.
    """

    if st_mod is None:
        import streamlit as st_mod  # local import keeps non-UI tools lightweight

    rerun_fn = getattr(st_mod, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return True

    legacy_rerun_fn = getattr(st_mod, "experimental_rerun", None)
    if callable(legacy_rerun_fn):
        legacy_rerun_fn()
        return True

    return False

