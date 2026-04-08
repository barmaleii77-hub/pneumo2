from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, MutableMapping

import streamlit as st

from pneumo_solver_ui.ui_svg_route_mapping_edit_helpers import apply_svg_route_mapping_edit


def is_svg_route_polyline_ready(route_paths: Any) -> bool:
    return bool(
        isinstance(route_paths, list)
        and route_paths
        and isinstance(route_paths[0], list)
        and len(route_paths[0]) >= 2
    )


def render_svg_route_assignment_panel(
    session_state: MutableMapping[str, Any],
    route_paths: Any,
    edge_columns: Iterable[str],
    route_report: Mapping[str, Any] | Any,
    *,
    analysis_view_box: Any,
    route_write_view_box: Any,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> None:
    st.markdown("#### Привязать найденный путь к ветке модели (mapping.edges)")
    if not is_svg_route_polyline_ready(route_paths):
        st.info("Сначала нажмите **«Найти путь»** — затем можно записать маршрут в mapping.edges.")
        return

    edge_target = str(session_state.get("svg_route_assign_edge", "") or "")
    if not edge_target:
        st.warning("Выберите целевую ветку в ассистенте выше (в этом же блоке).")
        return

    st.caption(f"Целевая ветка: **{edge_target}**")
    mode = st.radio(
        "Режим записи",
        options=["Заменить", "Добавить сегмент"],
        horizontal=True,
        key="svg_route_assign_mode",
    )
    col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
    with col_m1:
        btn_assign = st.button("Записать маршрут", key="btn_svg_route_assign")
    with col_m2:
        btn_clear_edge = st.button("Очистить ветку", key="btn_svg_route_clear_edge")
    with col_m3:
        st.caption(
            "Запись обновит текст в блоке **Анимация по схеме (mapping JSON)** ниже. "
            "Рекомендуется потом скачать mapping JSON файлом."
        )

    if not (btn_assign or btn_clear_edge):
        return

    polyline = route_paths[0] if btn_assign else None
    mapping, action_message = apply_svg_route_mapping_edit(
        session_state,
        session_state.get("svg_mapping_text", ""),
        edge_target,
        edge_columns,
        mapping_view_box=analysis_view_box,
        route_write_view_box=route_write_view_box,
        clear_edge=bool(btn_clear_edge),
        assign_route=bool(btn_assign),
        polyline=polyline,
        mode=mode,
        route_report=route_report,
        evaluate_quality_fn=evaluate_quality_fn,
    )
    st.success(action_message)
