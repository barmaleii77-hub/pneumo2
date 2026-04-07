"""📐 Геометрия подвески (DW2D)

Streamlit multipage: обёртка страницы.

Что делает:
- Показывает параметры геометрии DW2D (нижний рычаг + точки крепления цилиндров).
- Проверяет корректность кинематики в заданном диапазоне хода колеса.
- Строит графики `dw → delta_rod` и производную (motion ratio).

Примечания по UX:
- На странице включён общий bootstrap (подсказки + автозагрузка состояния).
- В конце страницы вызывается автосохранение, чтобы пользовательские значения
  не пропадали при перезапуске/переключении страниц.
"""

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

from pneumo_solver_ui.suspension_geometry_ui import run

run()

# Автосохранение (если включено)
