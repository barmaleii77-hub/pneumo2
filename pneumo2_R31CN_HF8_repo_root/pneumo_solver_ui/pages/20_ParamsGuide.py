# -*- coding: utf-8 -*-

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled


bootstrap(st)
autosave_if_enabled(st)

st.title("Параметры")
st.info(
    "Параметры редактируются в странице «Симулятор» (раздел «Прогон»). "
    "Там используется подход «список/поиск → карточка параметра», без горизонтального скролла."
)
