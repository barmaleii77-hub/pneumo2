from __future__ import annotations

from typing import Any, Callable, Iterable, MutableMapping

import pandas as pd
import streamlit as st

from pneumo_solver_ui.ui_svg_route_helpers import (
    build_svg_route_candidates,
    build_svg_route_coverage,
    extract_svg_route_edges_map,
    suggest_svg_route_filter_text,
)


def apply_svg_route_edge_advance(
    session_state: MutableMapping[str, Any],
    edge_columns: Iterable[str],
) -> None:
    edge_options = list(edge_columns)
    advance_target = session_state.pop("route_advance_to_unmapped", None)
    if isinstance(advance_target, str) and advance_target in edge_options:
        session_state["svg_route_assign_edge"] = advance_target


def swap_svg_route_label_options(session_state: MutableMapping[str, Any]) -> None:
    start_option = session_state.get("svg_route_start_opt")
    end_option = session_state.get("svg_route_end_opt")
    if start_option is None or end_option is None:
        return
    session_state["svg_route_start_opt"] = end_option
    session_state["svg_route_end_opt"] = start_option


def render_svg_route_guided_panel(
    session_state: MutableMapping[str, Any],
    items: Iterable[tuple[int, str, float, float]],
    edge_columns: Iterable[str],
    *,
    name_score_fn: Callable[[str, str], float],
    format_item_fn: Callable[[tuple[int, str, float, float]], str],
    safe_dataframe_fn: Callable[..., Any],
) -> str:
    edge_options = list(edge_columns)
    with st.expander("Ассистент разметки веток (guided)", expanded=False):
        if not edge_options:
            st.info("Нет df_mdot веток (edge_cols пуст). Запустите детальный прогон с **record_full=True**.")
            return str(session_state.get("svg_route_assign_edge", "") or "")

        apply_svg_route_edge_advance(session_state, edge_options)

        edges_map = extract_svg_route_edges_map(session_state.get("svg_mapping_text", "{}") or "{}")
        mapped_set, unmapped, coverage_rows = build_svg_route_coverage(edge_options, edges_map)
        st.caption(f"Покрытие mapping.edges: {len(mapped_set)}/{len(edge_options)} веток. Неразмечено: {len(unmapped)}.")

        col_w1, col_w2, col_w3, col_w4 = st.columns([1, 1, 1, 2])
        with col_w1:
            if st.button("Следующая неразмеченная", key="btn_route_next_unmapped") and unmapped:
                session_state["svg_route_assign_edge"] = unmapped[0]
        with col_w2:
            st.checkbox("Автопереход после записи", value=True, key="route_auto_next")
        with col_w3:
            st.checkbox("Показать таблицу покрытия", value=False, key="route_show_cov")
        with col_w4:
            if st.button("Автофильтр по имени ветки", key="btn_route_autofilter_edge"):
                filter_text = suggest_svg_route_filter_text(session_state.get("svg_route_assign_edge", ""))
                if filter_text:
                    session_state["svg_route_filter"] = filter_text

        st.checkbox("Очистить маршрут после записи", value=False, key="route_clear_after_assign")

        if session_state.get("route_show_cov"):
            try:
                coverage_frame = pd.DataFrame(coverage_rows)
                safe_dataframe_fn(coverage_frame.sort_values(["mapped", "edge"]), height=220)
            except Exception as exc:
                st.warning(f"Не удалось построить таблицу покрытия: {exc}")

        edge_target = st.selectbox(
            "Целевая ветка модели (df_mdot) для разметки",
            options=edge_options,
            key="svg_route_assign_edge",
        )

        st.markdown("**Подсказки START/END меток по имени ветки (fuzzy):**")
        col_s1, col_s2, col_s3 = st.columns([1, 1, 2])
        with col_s1:
            suggestion_threshold = st.slider("Порог", 0.0, 1.0, 0.55, step=0.01, key="route_label_sugg_thr")
        with col_s2:
            suggestion_limit = st.slider("Top-K", 3, 30, 12, step=1, key="route_label_sugg_k")
        with col_s3:
            if st.button("↔ Поменять START/END", key="btn_swap_route_labels"):
                swap_svg_route_label_options(session_state)

        try:
            candidates = build_svg_route_candidates(
                items,
                str(edge_target or ""),
                min_score=float(suggestion_threshold),
                top_k=int(suggestion_limit),
                name_score_fn=name_score_fn,
            )
            if not candidates:
                st.caption("Подсказки не найдены (попробуйте снизить порог или используйте фильтр/клик по схеме).")
            else:
                for candidate_index, (score_value, item) in enumerate(candidates):
                    text_index, _, _, _ = item
                    col_1, col_2, col_3, col_4 = st.columns([4, 1, 1, 1])
                    option_label = format_item_fn(item)
                    col_1.write(option_label)
                    col_2.metric("score", f"{score_value:.2f}")
                    if col_3.button("START", key=f"btn_sugg_start_{text_index}_{candidate_index}"):
                        session_state["svg_route_start_opt"] = option_label
                    if col_4.button("END", key=f"btn_sugg_end_{text_index}_{candidate_index}"):
                        session_state["svg_route_end_opt"] = option_label
        except Exception as exc:
            st.warning(f"Не удалось построить подсказки: {exc}")

        return str(edge_target or "")
