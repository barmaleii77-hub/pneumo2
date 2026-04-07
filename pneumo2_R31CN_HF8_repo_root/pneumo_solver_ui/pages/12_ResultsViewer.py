"""Просмотр результатов.

Страница добавлена как совместимый алиас.

В некоторых сборках отдельная страница "Просмотр результатов" была
случайно утеряна при мердже, из-за чего Streamlit не мог создать Page
и приложение падало на старте.

Здесь намеренно сделан тонкий алиас на существующую страницу сравнения
результатов (NPZ) — функциональность не дублируется и не теряется.
"""

from __future__ import annotations
import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

from pathlib import Path
import runpy


bootstrap(st)
autosave_if_enabled(st)

_target = Path(__file__).with_name("06_CompareNPZ_Web.py")
runpy.run_path(str(_target))
