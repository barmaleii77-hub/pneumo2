# -*- coding: utf-8 -*-
"""00_Preflight.py

Страница Streamlit: Preflight (чеклист готовности + подсказка следующего шага).

Важно: файл ASCII (для Windows/ZIP).
"""

from pathlib import Path

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

APP_DIR = Path(__file__).resolve().parents[2]

try:
    from pneumo_solver_ui.ui_preflight import render_preflight_page

    render_preflight_page(st, APP_DIR)
except Exception as e:
    st.error(f"Preflight недоступен: {e}")

# Автосохранение (в конце)
