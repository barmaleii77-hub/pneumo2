# ORIGINAL_FILENAME: 21_╨æ╨░╨╖╨░_╤ì╨║╤ü╨┐╨╡╤Ç╨╕╨╝╨╡╨╜╤é╨╛╨▓.py
# -*- coding: utf-8 -*-
"""21_База_экспериментов.py — аналитика распределённых прогонов.

Позволяет:
- открыть DuckDB/SQLite ExperimentDB;
- посмотреть список запусков (runs) и таблицу испытаний (trials);
- построить Pareto‑фронт и прогресс гиперобъёма.

Важно: страница read-only и не требует Ray/Dask — она лишь читает DB.
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
