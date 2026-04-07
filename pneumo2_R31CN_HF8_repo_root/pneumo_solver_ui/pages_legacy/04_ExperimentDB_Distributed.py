# -*- coding: utf-8 -*-
"""Streamlit page: Experiment DB (distributed runs).

Lets you:
- open a DuckDB/SQLite experiment DB,
- inspect runs and trial status,
- visualize Pareto scatter and hypervolume progress.

This page is optional: it works even if distributed libraries (Ray/Dask)
are not installed, because it only reads the DB.
"""

from __future__ import annotations

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

import json
from pathlib import Path
import sys

bootstrap(st)
autosave_if_enabled(st)
