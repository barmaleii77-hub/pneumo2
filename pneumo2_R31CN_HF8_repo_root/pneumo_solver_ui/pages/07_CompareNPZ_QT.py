# -*- coding: utf-8 -*-
"""06_CompareViewer_QT.py

Страница-инструкция для запуска десктопного QT compare viewer.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled



bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "pneumo_solver_ui"
VIEWER = UI / "qt_compare_viewer.py"

st.title("Сравнение прогонов (Qt) — десктопный просмотрщик")

st.markdown(
    """
    Этот модуль — **десктопный** (Qt). Он удобен для инженерного сравнения нескольких прогонов по NPZ.

    **Как пользоваться:**
    - Сделайте несколько запусков симуляции/оптимизации → появятся результаты `*.npz`.
    - Нажмите кнопку ниже — viewer откроется и **сам** подхватит последние файлы из `workspace/osc` или `workspace/exports`.

    Если Qt/зависимости не установлены — установите их на странице **Установка и проверка окружения** (одна кнопка) и попробуйте снова.
    """
)

if not VIEWER.exists():
    st.error(f"Файл viewer не найден: {VIEWER}")
else:
    st.caption("Запускатель: страница **07_CompareNPZ_QT** → модуль `pneumo_solver_ui.qt_compare_viewer` (Diagrammy / облака / галька).")
    if st.button("Открыть просмотрщик сравнения (Qt)"):
        try:
            subprocess.Popen([sys.executable, "-m", "pneumo_solver_ui.qt_compare_viewer"], cwd=str(ROOT))
            st.success("Просмотрщик запущен (если среда позволяет запуск GUI).")
        except Exception as e:
            st.exception(e)

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
