import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
bootstrap(st)
autosave_if_enabled(st)

"""Legacy: Desktop Animator.

Совместимый алиас для legacy-навигации.

В Streamlit-варианте используем веб-кабину анимации (11_AnimationCockpit_Web.py).
Отдельный Desktop Animator остаётся доступен как самостоятельное приложение.
"""

from pathlib import Path
import runpy

_target = Path(__file__).with_name("11_AnimationCockpit_Web.py")
runpy.run_path(str(_target))
