"""Каталог цилиндров Camozzi.

Это multipage wrapper: фактический UI живёт в `pneumo_solver_ui/camozzi_catalog_ui.py`.

Важно: bootstrap должен вызываться с объектом `streamlit` (st), иначе не включится
автозагрузка сохранённого состояния и общие UX‑патчи.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Пневмо‑UI | Camozzi", layout="wide")
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.camozzi_catalog_ui import run


bootstrap(st)

run()

# best‑effort autosave
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled

    autosave_if_enabled(st)
except Exception:
    pass
