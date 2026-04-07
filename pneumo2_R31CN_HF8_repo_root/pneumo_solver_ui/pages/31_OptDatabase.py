import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
bootstrap(st)
autosave_if_enabled(st)

"""Legacy: База оптимизаций.

Совместимый алиас для legacy-навигации.

Функциональность базы экспериментов/оптимизаций реализована в странице
21_ExperimentDB.py.
"""

from pathlib import Path
import runpy

_target = Path(__file__).with_name("21_ExperimentDB.py")
runpy.run_path(str(_target))
