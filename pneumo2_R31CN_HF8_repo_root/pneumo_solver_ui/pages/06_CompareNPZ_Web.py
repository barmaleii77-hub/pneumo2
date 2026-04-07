# -*- coding: utf-8 -*-
"""06_CompareNPZ_Web.py

Единая страница сравнения прогонов (web).

Важно
-----
В проекте исторически появлялись дублирующиеся реализации compare‑страницы.
Чтобы не плодить "legacy" и не расходиться по функционалу,
страница является тонкой обёрткой над модулем:
    pneumo_solver_ui/compare_npz_web.py

Там находится "источник истины" для логики сравнения/диаграмм.
"""

from __future__ import annotations

import streamlit as st

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.compare_npz_web import render_compare_npz_web

    render_compare_npz_web(st)
except Exception as e:
    # Страница должна либо работать, либо явно показывать статус "в разработке".
    st.error("Страница 'Compare NPZ (Web)' временно недоступна (в разработке)")
    st.exception(e)
