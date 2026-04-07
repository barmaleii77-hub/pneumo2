# -*- coding: utf-8 -*-
"""ui_bootstrap.py

Небольшой «бутстрап» для всех страниц Streamlit.

Что делает:
- включает единый патч подсказок (ui_tooltips_ru);
- выполняет автозагрузку сохранённого состояния UI (ui_persistence).

Подключать как можно раньше на странице (до создания виджетов),
чтобы восстановленные значения попадали в value=... по умолчанию.
"""

from __future__ import annotations

from typing import Any


def bootstrap(st_mod: Any) -> None:
    """Best‑effort bootstrap. Никогда не должен ломать UI."""

    # 0) Global CSS (лучше UX): курсор-pointer на кликабельных элементах и пр.
    try:
        if hasattr(st_mod, "session_state") and hasattr(st_mod, "markdown"):
            if "_ui_global_css_injected_v1" not in st_mod.session_state:
                st_mod.markdown(
                    """<style>
                    /* Cursor: make clickable UI elements feel clickable */
                    div[data-testid="stSelectbox"] div[role="button"],
                    div[data-testid="stMultiSelect"] div[role="button"],
                    div[data-testid="stSelectbox"] input,
                    div[data-testid="stMultiSelect"] input,
                    div[data-baseweb="select"] input,
                    div[data-testid="stExpander"] summary,
                    div[data-testid="stRadio"] label,
                    div[data-testid="stCheckbox"] label {
                        cursor: pointer !important;
                    }
                    </style>""",
                    unsafe_allow_html=True,
                )
                st_mod.session_state["_ui_global_css_injected_v1"] = True
    except Exception:
        pass

    # 1) tooltips
    try:
        from pneumo_solver_ui.ui_tooltips_ru import install_tooltips_ru

        install_tooltips_ru()
    except Exception:
        pass

    # 2) persistence (autoload once)
    try:
        from pneumo_solver_ui.ui_persistence import autoload_once

        autoload_once(st_mod)
    except Exception:
        pass

    # 2b) Ensure at least one autosave snapshot exists on disk.
    #     This makes support bundles reproducible even if the session crashes early.
    try:
        if hasattr(st_mod, "session_state") and "_ui_bootstrap_initial_autosave_v1" not in st_mod.session_state:
            from pneumo_solver_ui.ui_persistence import autosave_now

            autosave_now(st_mod)
            st_mod.session_state["_ui_bootstrap_initial_autosave_v1"] = True
    except Exception:
        pass

    # 3) UI performance defaults (heavy charts cache)
    try:
        from pneumo_solver_ui.ui_heavy_cache import init_perf_defaults

        init_perf_defaults(st_mod)
    except Exception:
        pass

    # 4) Cross-page run artifacts (baseline/optimization pointers)
    #    Important: no strictness here – must never break UI.
    try:
        from pneumo_solver_ui.run_artifacts import autoload_to_session

        autoload_to_session(st_mod)
    except Exception:
        pass
