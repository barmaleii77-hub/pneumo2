import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
# -*- coding: utf-8 -*-
from pneumo_solver_ui.pages._page_runner import run_page

# В базе эта страница называется '04_Влияние_подсистем.py'
bootstrap(st)
autosave_if_enabled(st)

run_page('04_Влияние_подсистем.py')
