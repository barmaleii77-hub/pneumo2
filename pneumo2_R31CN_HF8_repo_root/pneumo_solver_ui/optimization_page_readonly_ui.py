from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Sequence

from pneumo_solver_ui.optimization_last_pointer_ui import (
    render_last_optimization_pointer_summary,
)


def current_objective_keys(
    session_state: Mapping[str, Any],
    *,
    default_objectives: Sequence[str],
    objectives_text_fn: Callable[[Sequence[str]], str],
) -> list[str]:
    raw = str(
        session_state.get(
            "opt_objectives",
            objectives_text_fn(default_objectives),
        )
        or ""
    ).strip()
    keys = [item.strip() for item in re.split(r"[\n,;]+", raw) if item.strip()]
    return keys or [str(item) for item in default_objectives]


def render_last_optimization_overview_block(
    st: Any,
    *,
    snapshot: Mapping[str, Any],
    results_page: str,
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    active_run_dir: Any = None,
    active_launch_context: Mapping[str, Any] | None = None,
    active_runtime_summary: Mapping[str, Any] | None = None,
    render_summary_fn: Callable[..., bool] = render_last_optimization_pointer_summary,
) -> None:
    if not render_summary_fn(
        st,
        snapshot,
        compact=False,
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
        active_run_dir=active_run_dir,
        active_launch_context=dict(active_launch_context or {}),
        active_runtime_summary=dict(active_runtime_summary or {}),
        missing_message="Последняя оптимизация пока не запускалась (или артефакты не найдены).",
        success_message="Найдены результаты последней оптимизации.",
        packaging_heading="Сводка по геометрии узлов (последний run)",
        packaging_interference_prefix="В последнем run есть признаки пересечений по геометрии узлов",
    ):
        return

    btn_cols = st.columns([1, 1, 2])
    with btn_cols[0]:
        if st.button("Открыть результаты", help="Перейти на страницу просмотра результатов оптимизации"):
            try:
                st.switch_page(results_page)
            except Exception:
                st.info("Откройте страницу 'Результаты оптимизации' в меню слева.")
    with btn_cols[1]:
        if st.button("Открыть папку", help="Показать путь к папке в виде текста"):
            st.code(str(snapshot.get("run_dir") or (snapshot.get("raw") or {}).get("run_dir") or ""))


def render_physical_workflow_block(
    st: Any,
    *,
    session_state: Mapping[str, Any],
    default_objectives: Sequence[str],
    penalty_key_default: str,
    objectives_text_fn: Callable[[Sequence[str]], str],
    rerun_fn: Callable[[Any], None],
) -> None:
    current_obj = current_objective_keys(
        session_state,
        default_objectives=default_objectives,
        objectives_text_fn=objectives_text_fn,
    )
    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.metric("Быстрый путь по физике", "StageRunner")
    with cols[1]:
        st.metric("Длинный перебор", "Distributed")
    with cols[2]:
        st.metric(
            "Жёсткий порог",
            str(session_state.get("opt_penalty_key", penalty_key_default) or penalty_key_default),
        )

    st.caption(
        "Отдельной powertrain / engine-map модели в live optimization contract сейчас нет. "
        "Честный физический scope текущего оптимизатора — сигналы подвески, дороги и реакции кузова."
    )
    st.caption(
        "StageRunner — быстрый путь по физике: дешёвые стадии и ранний отсев. Быстрый stop/fail на stage0/stage1 — это штатно, "
        "если кандидат сразу выбивается по физике или penalty gate."
    )
    st.caption(
        "Distributed coordinator — длинный перебор вариантов после того, как search-space и suite уже стабилизированы. "
        "Он нужен не вместо физического фильтра, а после него."
    )
    st.caption(
        "Канонический набор целей для coordinator и StageRunner promotion/baseline: "
        + ", ".join(str(item) for item in default_objectives)
    )
    st.caption("Текущий набор целей: " + ", ".join(current_obj))
    st.caption(
        "Если нужна другая постановка — правьте objective keys ниже вручную. И coordinator, и StageRunner будут читать один и тот же набор целей; блок ничего не скрывает и не режет настройки."
    )
    if st.button(
        "Вернуть канонический набор целей (comfort / roll / energy)",
        key="opt_restore_default_objectives",
        help="Подставляет текущий канонический стек целей в editable objective textarea ниже.",
    ):
        session_state["opt_objectives"] = objectives_text_fn(default_objectives)
        st.success("Канонический набор целей подставлен в editable поле ниже.")
        rerun_fn(st)


__all__ = [
    "current_objective_keys",
    "render_last_optimization_overview_block",
    "render_physical_workflow_block",
]
