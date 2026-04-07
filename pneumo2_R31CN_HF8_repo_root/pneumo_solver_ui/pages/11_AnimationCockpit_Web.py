# -*- coding: utf-8 -*-
"""Streamlit page: Animation Cockpit (Web).

Страница ориентирована на интерактивную анимацию/визуализацию сигналов.
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

from pneumo_solver_ui.animation_cockpit_web import render_animation_cockpit_web

render_animation_cockpit_web()
