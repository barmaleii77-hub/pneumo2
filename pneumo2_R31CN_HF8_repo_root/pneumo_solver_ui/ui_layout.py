# -*- coding: utf-8 -*-
"""pneumo_solver_ui.ui_layout

Небольшие (безопасные) улучшения компоновки для Streamlit UI.

Цели:
- уменьшить «пустые поля» по краям в wide-layout;
- сделать таблицы/редакторы более предсказуемыми по ширине;
- НЕ ломать set_page_config (то есть вызывать после него!).
"""

from __future__ import annotations

from typing import Any


def apply_global_css(st_mod: Any) -> None:
    """Inject small global CSS rules.

    IMPORTANT: call only after st.set_page_config().
    """

    st_mod.markdown(
        """
<style>
/* меньше пустоты по краям */
div.block-container {
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
    padding-top: 1.0rem !important;
    max-width: 100% !important;
}

/* таблицы/редакторы тянем по ширине контейнера */
div[data-testid='stDataFrame'] { width: 100% !important; }
section[data-testid='stSidebar'] div[data-testid='stDataFrame'] { width: 100% !important; }

/* data_editor тоже тянем по ширине (в разных версиях разные test-id) */
div[data-testid='stDataEditor'] { width: 100% !important; }
section[data-testid='stSidebar'] div[data-testid='stDataEditor'] { width: 100% !important; }

/* некоторые версии используют stDataFrameResizable */
div[data-testid='stDataFrameResizable'] { width: 100% !important; }
section[data-testid='stSidebar'] div[data-testid='stDataFrameResizable'] { width: 100% !important; }

/* чуть компактнее заголовки в sidebar */
section[data-testid='stSidebar'] h3 { margin-bottom: 0.4rem; }
</style>
""",
        unsafe_allow_html=True,
    )
