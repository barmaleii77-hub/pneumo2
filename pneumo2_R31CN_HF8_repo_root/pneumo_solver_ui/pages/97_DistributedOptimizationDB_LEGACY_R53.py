# -*- coding: utf-8 -*-
import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

st.header('Legacy: DistributedOptimizationDB (R53)')
st.warning(
    'Эта страница оставлена только для совместимости. '
    'Актуальные функции находятся в разделах "Оптимизация" и "База экспериментов".'
)

st.markdown(
    """
    Что делать дальше:
    1) Откройте **Оптимизация → Распределённая оптимизация**
    2) Или **Оптимизация → База экспериментов**

    Если вам нужен именно старый workflow R53 — сообщите, и мы добавим миграцию с сохранением данных.
    """
)
