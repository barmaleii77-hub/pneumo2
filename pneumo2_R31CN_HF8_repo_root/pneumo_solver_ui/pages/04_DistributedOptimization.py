# -*- coding: utf-8 -*-
import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
from pneumo_solver_ui.pages._page_runner import run_page

bootstrap(st)
autosave_if_enabled(st)

st.session_state['opt_variant'] = 'main'
run_page('20_Распределенная_оптимизация.py')
