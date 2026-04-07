# -*- coding: utf-8 -*-
import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
from pneumo_solver_ui.pages._page_runner import run_page

bootstrap(st)
autosave_if_enabled(st)

st.info('Режим R58 открыт. Если в интерфейсе нет отличий — используйте те же элементы, что и в основной оптимизации.')
st.session_state['opt_variant'] = 'R58'
run_page('20_Распределенная_оптимизация.py')
