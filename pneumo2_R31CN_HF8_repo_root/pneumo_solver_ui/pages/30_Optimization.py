import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
bootstrap(st)
autosave_if_enabled(st)

"""Legacy: Оптимизация.

Совместимый алиас для legacy-навигации.

Использует актуальную страницу оптимизации (03_Optimization.py).
"""

from pathlib import Path
import runpy

_target = Path(__file__).with_name("03_Optimization.py")
runpy.run_path(str(_target))
