# -*- coding: utf-8 -*-
"""Thin Streamlit launcher for the standalone Qt Compare Viewer."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled


bootstrap(st)
autosave_if_enabled(st)

ROOT = Path(__file__).resolve().parents[2]
VIEWER_MODULE = "pneumo_solver_ui.qt_compare_viewer"

st.title("Compare Viewer (Qt)")
st.caption("Standalone WS-ANALYSIS compare/objective window.")

if st.button("Open Compare Viewer"):
    try:
        subprocess.Popen([sys.executable, "-m", VIEWER_MODULE], cwd=str(ROOT))
        st.success("Compare Viewer started.")
    except Exception as exc:
        st.exception(exc)
