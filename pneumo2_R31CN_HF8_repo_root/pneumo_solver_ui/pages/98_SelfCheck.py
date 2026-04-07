# -*- coding: utf-8 -*-

import json
from datetime import datetime

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

from pneumo_solver_ui.tools.selfcheck import run_quick_selfcheck, summarize_selfcheck


bootstrap(st)
autosave_if_enabled(st)

st.title("Самопроверка")
st.caption("Быстрые проверки целостности проекта и окружения. Не запускает долгих расчётов модели.")

# Run once per session
if "quick_selfcheck" not in st.session_state:
    st.session_state["quick_selfcheck"] = run_quick_selfcheck(".")

results = st.session_state.get("quick_selfcheck", [])
ok, n_err, n_warn = summarize_selfcheck(results)

if ok:
    st.success("Самопроверка: ошибок не найдено.")
elif n_err > 0:
    st.error(f"Самопроверка: {n_err} ошибок, {n_warn} предупреждений.")
else:
    st.warning(f"Самопроверка: {n_warn} предупреждений (критичных ошибок нет).")

colA, colB = st.columns([1, 2], gap="large")

with colA:
    st.subheader("Сводка")
    st.metric("Ошибки", n_err)
    st.metric("Предупреждения", n_warn)
    st.markdown(
        """
Если есть ошибки:
1) Перезапустите приложение через `START_PNEUMO_APP.py` (он умеет ставить зависимости).
2) Откройте **Инструменты → Диагностика** и соберите диагностический zip.
3) Проверьте, что распаковка архива не была «частичной».
"""
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = json.dumps({"ts": ts, "results": results}, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(
        "Скачать отчёт (JSON)",
        data=payload,
        file_name=f"selfcheck_{ts}.json",
        mime="application/json",
        width="stretch",
    )

with colB:
    st.subheader("Результаты")
    # Show only important fields, without forcing horizontal scroll
    rows = []
    for r in results:
        rows.append(
            {
                "OK": "✅" if r.get("ok") else "❌",
                "Уровень": r.get("level", ""),
                "Проверка": r.get("title", ""),
                "Детали": r.get("details", ""),
                "Подсказка": r.get("hint", ""),
            }
        )

    st.dataframe(rows, width="stretch", hide_index=True)
