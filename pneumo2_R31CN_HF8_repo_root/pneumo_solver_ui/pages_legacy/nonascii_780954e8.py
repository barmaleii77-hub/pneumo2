# ORIGINAL_FILENAME: 09_╨Æ╨░╨╗╨╕╨┤╨░╤å╨╕╤Å_╨Æ╨╡╨▒.py
# -*- coding: utf-8 -*-
"""08_ValidationCockpit_Web.py

Один экран проверки одного прогона (NPZ): анимация + ключевые графики.
"""
from __future__ import annotations

import streamlit as st
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
from pneumo_solver_ui.validation_cockpit_web import render_validation_cockpit_web

bootstrap(st)
autosave_if_enabled(st)

safe_set_page_config(page_title="Валидация (Web)", layout="wide")
render_validation_cockpit_web()
