# -*- coding: utf-8 -*-
"""05_ParamInfluence.py

Обёртка для запуска `param_influence_ui.py` как страницы Streamlit.
"""
from __future__ import annotations

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

st.title("Влияние параметров (N→N)")
with st.expander("Как пользоваться"):
    st.markdown(
        """
        Здесь можно **одновременно** анализировать влияние изменения N входных параметров
        на изменения N выходных метрик по результатам уже выполненных оптимизаций/прогонов.

        Рекомендации:
        - Сначала выберите **источник данных** (последний прогон / архив / baseline).
        - Затем выберите **набор метрик** и **фильтры** (стадия/тест/условия).
        - Используйте одинаковые масштабы/единицы измерения при сравнении разных прогонов.
        """
    )
st.divider()


import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "param_influence_ui.py"), run_name="__main__")
