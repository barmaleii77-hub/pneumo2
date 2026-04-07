"""Геометрия пружин / Coil Bind.

Multipage wrapper: реальный UI живёт в `pneumo_solver_ui/spring_geometry_ui.py`.

Ранее bootstrap ошибочно вызывался с `str`, что отключало автозагрузку
сохранённого состояния и общие UX‑патчи. Здесь исправлено на bootstrap(st).
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Пневмо‑UI | Пружины", layout="wide")
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.spring_geometry_ui import run


bootstrap(st)

run()

# best‑effort autosave
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled

    autosave_if_enabled(st)
except Exception:
    pass
