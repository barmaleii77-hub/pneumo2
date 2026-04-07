# -*- coding: utf-8 -*-
"""Streamlit page: Validation Cockpit (Web).

Страница ориентирована на **валидацию**:
- сравнение расчёта и измерений
- сводные панели и диагностические графики

Примечание: значения виджетов автосохраняются (ui_bootstrap).
"""

from __future__ import annotations

import streamlit as st

from pneumo_solver_ui.ui_persistence import autosave_if_enabled

# --- UI bootstrap (persist + defaults + run artifacts) ---
try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    # bootstrap не должен ломать запуск
    pass

# --- Автосохранение (если включено в UI) ---
autosave_if_enabled(st)

from pneumo_solver_ui.validation_cockpit_web import render_validation_cockpit_web

render_validation_cockpit_web()
