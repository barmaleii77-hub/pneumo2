# -*- coding: utf-8 -*-
"""ui_css.py

Минимальный слой CSS для Streamlit UI.

Задачи:
- помочь длинным подписям/подсказкам помещаться и не "наезжать" друг на друга;
- сделать подписи компактнее, но читабельнее;
- не ломать тему Streamlit и не требовать внешних зависимостей.

CSS внедряется best-effort через `st.markdown(..., unsafe_allow_html=True)`.
"""

from __future__ import annotations

from typing import Any


_CSS = r"""
<style>
/* Светлый фон (по ISA/HMI best practice) — только для light mode */
@media (prefers-color-scheme: light) {
  .stApp {
    background-color: rgba(240, 242, 245, 0.85);
  }
}

/* Длинные подписи виджетов: перенос строк вместо обрезки */
div[data-testid="stWidgetLabel"] > label {
  white-space: normal !important;
  line-height: 1.15 !important;
}

/* Чуть компактнее вертикальные отступы у подписей */
div[data-testid="stWidgetLabel"] {
  margin-bottom: 0.15rem;
}

/* Подсказки (caption) под полями: компактнее */
div[data-testid="stCaptionContainer"] p {
  margin-top: 0.10rem;
  margin-bottom: 0.10rem;
}

/* НОВОЕ: заметные inline‑подсказки (включается переключателем "Показывать подсказки под полями") */
.ui-help-inline {
  margin: 0.10rem 0 0.20rem 0;
  padding: 0.25rem 0.55rem;
  border-left: 4px solid rgba(0,0,0,0.25);
  background: rgba(0,0,0,0.03);
  border-radius: 0.25rem;
  line-height: 1.25;
  font-size: 0.92rem;
  word-break: break-word;
}

@media (prefers-color-scheme: dark) {
  .ui-help-inline {
    border-left-color: rgba(255,255,255,0.25);
    background: rgba(255,255,255,0.06);
  }
}

/* В таблицах/датафреймах: разрешаем перенос заголовков */
div[data-testid="stDataFrame"] * {
  word-break: break-word;
}
</style>
"""


def inject_global_css(st_mod: Any) -> None:
    """Внедрить CSS один раз за сессию."""
    try:
        if hasattr(st_mod, 'session_state'):
            if st_mod.session_state.get('ui_css_injected', False):
                return
            st_mod.session_state['ui_css_injected'] = True
    except Exception:
        # даже если session_state недоступен, просто продолжаем
        pass

    try:
        st_mod.markdown(_CSS, unsafe_allow_html=True)
    except Exception:
        pass
