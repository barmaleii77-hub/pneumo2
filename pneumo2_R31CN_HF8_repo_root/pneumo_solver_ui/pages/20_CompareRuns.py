import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
bootstrap(st)
autosave_if_enabled(st)

"""Legacy: Сравнение запусков.

Файл нужен для совместимости с legacy-навигацией (app.py). В некоторых мерджах
legacy-страницы были удалены/переименованы, из-за чего включение режима legacy
ломало запуск приложения.

Здесь используем существующий веб-инструмент сравнения NPZ как наиболее близкий
по смыслу функционал.
"""

from pathlib import Path
import runpy

_target = Path(__file__).with_name("06_CompareNPZ_Web.py")
runpy.run_path(str(_target))
