# -*- coding: utf-8 -*-
"""06_CompareViewer_QT.py

Страница-инструкция для запуска десктопного QT compare viewer.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "pneumo_solver_ui"
VIEWER = UI / "qt_compare_viewer.py"

safe_set_page_config(page_title="Compare Viewer (QT)", layout="wide")
st.title("Compare Viewer (QT) — сравнение прогонов (desktop)")

st.markdown(
    """
    Этот модуль — **десктопный** (Qt). Он удобен для инженерного сравнения нескольких прогонов по NPZ.

    **Как пользоваться:**
    - Сделайте несколько запусков симуляции/оптимизации → появятся результаты `*.npz`.
    - Нажмите кнопку ниже — viewer откроется и **сам** подхватит последние файлы из `workspace/osc` или `workspace/exports`.

    Если Qt/зависимости не установлены — установите их на странице **Setup** (одна кнопка) и попробуйте снова.
    """
)

if not VIEWER.exists():
    st.error(f"Файл viewer не найден: {VIEWER}")
else:
    if st.button("Открыть QT Compare Viewer"):
        try:
            subprocess.Popen([sys.executable, str(VIEWER)], cwd=str(UI))
            st.success("Viewer запущен (если среда позволяет запуск GUI).")
        except Exception as e:
            st.exception(e)
