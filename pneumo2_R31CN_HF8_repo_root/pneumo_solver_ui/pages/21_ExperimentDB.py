import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

"""Legacy: База экспериментов / ExperimentDB.

Совместимый алиас для исторической навигации.

Канонический read-only DB viewer сейчас реализован в странице
03_DistributedOptimizationDB.py.
"""

from pathlib import Path
import runpy

_target = Path(__file__).with_name("03_DistributedOptimizationDB.py")
runpy.run_path(str(_target))
