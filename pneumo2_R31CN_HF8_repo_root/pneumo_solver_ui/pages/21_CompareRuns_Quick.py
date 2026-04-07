import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
bootstrap(st)
autosave_if_enabled(st)

"""Legacy: Быстрое сравнение запусков.

Совместимый алиас для legacy-навигации.

На текущий момент используем ту же страницу сравнения NPZ.
"""

from pathlib import Path
import runpy

_target = Path(__file__).with_name("06_CompareNPZ_Web.py")
runpy.run_path(str(_target))
