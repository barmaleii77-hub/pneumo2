import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
# ORIGINAL_FILENAME: 10_Геометрия_подвески.py
# coding: utf-8
bootstrap(st)
autosave_if_enabled(st)

"""Страница Streamlit: Геометрия подвески (DW2D).

Русское имя файла оставлено для удобства, но для совместимости с путями/кодировками
в Windows рядом есть ASCII-страница `10_SuspensionGeometry.py`.
"""

from pneumo_solver_ui.suspension_geometry_ui import run


if __name__ == "__main__":
    run()
else:
    run()
