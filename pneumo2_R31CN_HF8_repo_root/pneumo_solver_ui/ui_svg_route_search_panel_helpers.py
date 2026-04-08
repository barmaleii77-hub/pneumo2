from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, MutableMapping

import streamlit as st

from pneumo_solver_ui.ui_svg_mapping_state_helpers import clear_svg_route_preview
from pneumo_solver_ui.ui_svg_route_assignment_panel_helpers import (
    render_svg_route_assignment_panel,
)
from pneumo_solver_ui.ui_svg_route_find_helpers import find_svg_route_between_labels
from pneumo_solver_ui.ui_svg_route_report_helpers import render_svg_route_report_panel
from pneumo_solver_ui.ui_svg_route_selection_helpers import (
    apply_pending_svg_route_label_pick,
    resolve_svg_route_label_picks,
)


def resolve_svg_route_end_default_index(option_count: int) -> int:
    if option_count <= 1:
        return 0
    return 1


def format_svg_route_pick_mode_warning(pick_mode: Any) -> str | None:
    mode = str(pick_mode or "").strip().lower()
    if mode in ("start", "end"):
        return f"Режим выбора метки: **{mode.upper()}**. Кликните по текстовой подписи на схеме (SVG справа)."
    return None


def render_svg_route_search_panel(
    session_state: MutableMapping[str, Any],
    items: Iterable[tuple[int, str, float, float]],
    options: list[str],
    option_to_index: dict[str, int],
    texts: list[dict[str, Any]],
    analysis: Mapping[str, Any] | Any,
    edge_columns: Iterable[str],
    *,
    route_write_view_box: Any,
    format_item_fn: Callable[[tuple[int, str, float, float]], str],
    shortest_path_fn: Callable[..., Mapping[str, Any]],
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> None:
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Выбрать START кликом на схеме", key="btn_svg_pick_start_label"):
            session_state["svg_label_pick_mode"] = "start"
    with col_p2:
        if st.button("Выбрать END кликом на схеме", key="btn_svg_pick_end_label"):
            session_state["svg_label_pick_mode"] = "end"

    st.caption(
        "Горячие клавиши: **Shift+клик** = START, **Ctrl/Cmd+клик** = END. "
        "Можно кликать рядом с подписью (поиск ближайшей метки)."
    )
    st.slider(
        "Радиус поиска ближайшей метки (px)",
        min_value=6,
        max_value=60,
        value=18,
        key="svg_label_pick_radius",
    )

    pick_warning = format_svg_route_pick_mode_warning(session_state.get("svg_label_pick_mode", ""))
    if pick_warning:
        st.warning(pick_warning)

    options, option_to_index = apply_pending_svg_route_label_pick(
        session_state,
        session_state.get("svg_route_label_pick_pending"),
        items,
        options,
        option_to_index,
        format_item_fn=format_item_fn,
    )

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        start_option = st.selectbox("Стартовая метка", options, key="svg_route_start_opt")
    with col_r2:
        end_option = st.selectbox(
            "Конечная метка",
            options,
            index=resolve_svg_route_end_default_index(len(options)),
            key="svg_route_end_opt",
        )

    session_state["svg_route_label_picks"] = resolve_svg_route_label_picks(
        items,
        start_option,
        end_option,
        option_to_index,
    )

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        btn_find = st.button("Найти путь", key="btn_svg_route_find")
    with col_b2:
        btn_clear = st.button("Очистить путь", key="btn_svg_route_clear")
    with col_b3:
        simplify_epsilon = st.slider(
            "Упростить маршрут (RDP epsilon, px)",
            0.0,
            10.0,
            1.0,
            step=0.1,
            key="svg_route_simplify_eps",
        )

    if btn_clear:
        clear_svg_route_preview(session_state)
        st.success("Маршрут очищен.")

    if btn_find:
        ok, route_message = find_svg_route_between_labels(
            session_state,
            texts,
            start_option,
            end_option,
            option_to_index,
            analysis,
            float(simplify_epsilon),
            shortest_path_fn=shortest_path_fn,
        )
        if ok:
            st.success(route_message)
        else:
            st.error(route_message)

    route_report = session_state.get("svg_route_report")
    if isinstance(route_report, dict) and route_report:
        render_svg_route_report_panel(
            session_state,
            route_report,
            evaluate_quality_fn=evaluate_quality_fn,
        )
        try:
            render_svg_route_assignment_panel(
                session_state,
                session_state.get("svg_route_paths", []),
                edge_columns,
                route_report,
                analysis_view_box=analysis.get("viewBox") if isinstance(analysis, Mapping) else None,
                route_write_view_box=route_write_view_box,
                evaluate_quality_fn=evaluate_quality_fn,
            )
        except Exception as exc:
            st.error(f"Не удалось обновить mapping JSON: {exc}")
