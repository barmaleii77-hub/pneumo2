from __future__ import annotations

import time
from typing import Any, Callable, Iterable, Mapping, MutableMapping

import pandas as pd
import streamlit as st

from pneumo_solver_ui.ui_svg_mapping_helpers import (
    load_svg_mapping_or_empty,
    write_svg_edge_route,
)
from pneumo_solver_ui.ui_svg_mapping_state_helpers import (
    clear_svg_route_preview,
    persist_svg_mapping_text,
    request_next_unmapped_svg_edge,
    store_svg_route_preview,
    update_svg_mapping_meta,
)
from pneumo_solver_ui.ui_svg_route_helpers import (
    build_svg_route_candidates,
    choose_svg_route_candidate_pair,
    is_noise_svg_route_label,
)
from pneumo_solver_ui.ui_svg_route_report_helpers import resolve_svg_route_quality_params


SvgRouteItem = tuple[int, str, float, float]


def build_svg_auto_all_label_items(texts: Iterable[object]) -> list[SvgRouteItem]:
    items: list[SvgRouteItem] = []
    for text_index, text_row in enumerate(texts):
        try:
            label = str(text_row.get("text", "")).strip()
            if is_noise_svg_route_label(label):
                continue
            x_coord = float(text_row.get("x", 0.0))
            y_coord = float(text_row.get("y", 0.0))
            items.append((int(text_index), label, x_coord, y_coord))
        except Exception:
            continue
    return items


def resolve_svg_auto_review_status(quality_report: Mapping[str, Any] | Any) -> str:
    try:
        if isinstance(quality_report, Mapping) and str(quality_report.get("grade", "")).upper() == "PASS":
            return "approved"
    except Exception:
        pass
    return "pending"


def store_svg_auto_route_selection(
    session_state: MutableMapping[str, Any],
    start_item: SvgRouteItem,
    end_item: SvgRouteItem,
    *,
    format_item_fn: Callable[[SvgRouteItem], str],
) -> None:
    session_state["svg_route_start_opt"] = format_item_fn(start_item)
    session_state["svg_route_end_opt"] = format_item_fn(end_item)
    session_state["svg_route_label_picks"] = {
        "start": {
            "ti": int(start_item[0]),
            "name": str(start_item[1]),
            "x": float(start_item[2]),
            "y": float(start_item[3]),
        },
        "end": {
            "ti": int(end_item[0]),
            "name": str(end_item[1]),
            "x": float(end_item[2]),
            "y": float(end_item[3]),
        },
    }


def evaluate_svg_auto_route_quality(
    session_state: MutableMapping[str, Any],
    polyline: list[list[float]],
    route_report: Mapping[str, Any] | Any,
    *,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    quality_params = resolve_svg_route_quality_params(session_state)
    try:
        return evaluate_quality_fn(
            polyline,
            attach_start=route_report.get("attach_start") if isinstance(route_report, Mapping) else None,
            attach_end=route_report.get("attach_end") if isinstance(route_report, Mapping) else None,
            min_turn_deg=float(quality_params.get("min_turn_deg", 45.0)),
            max_detour=float(quality_params.get("max_detour", 8.0)),
            max_attach_dist=float(quality_params.get("max_attach_dist", 35.0)),
        )
    except Exception:
        return None


def build_svg_auto_route_meta(
    start_item: SvgRouteItem,
    end_item: SvgRouteItem,
    *,
    start_score: float,
    end_score: float,
    route_report: Mapping[str, Any] | Any,
    strategy: str,
    quality_report: Mapping[str, Any] | None,
    auto_batch: bool,
    timestamp: float,
) -> dict[str, Any]:
    length_px = float(route_report.get("length", 0.0) or 0.0) if isinstance(route_report, Mapping) else 0.0
    meta = {
        "auto_batch" if auto_batch else "auto": True,
        "strategy": str(strategy),
        "start": {
            "label": str(start_item[1]),
            "ti": int(start_item[0]),
            "score": float(start_score),
            "x": float(start_item[2]),
            "y": float(start_item[3]),
        },
        "end": {
            "label": str(end_item[1]),
            "ti": int(end_item[0]),
            "score": float(end_score),
            "x": float(end_item[2]),
            "y": float(end_item[3]),
        },
        "route": {
            "length_px": length_px,
            "points": int(len(route_report.get("path_xy", []))) if isinstance(route_report, Mapping) else 0,
        },
        "ts": float(timestamp),
    }
    if quality_report is not None:
        meta["quality"] = quality_report
    meta["review"] = {
        "status": resolve_svg_auto_review_status(quality_report),
        "by": "auto_batch" if auto_batch else "auto",
        "ts": float(timestamp),
    }
    return meta


def propose_svg_auto_route(
    items: Iterable[SvgRouteItem],
    edge_name: str,
    analysis: Mapping[str, Any] | Any,
    *,
    min_score: float,
    top_k: int,
    strategy: str,
    simplify_epsilon: float,
    max_length: float,
    name_score_fn: Callable[[str, str], float],
    shortest_path_fn: Callable[..., Mapping[str, Any]],
    not_enough_message: str,
    pair_error_message: str,
    empty_route_message: str,
    too_long_message: str,
) -> dict[str, Any]:
    candidates = build_svg_route_candidates(
        items,
        str(edge_name),
        min_score=float(min_score),
        top_k=int(top_k),
        name_score_fn=name_score_fn,
    )
    if len(candidates) < 2:
        raise ValueError(not_enough_message)

    pair = choose_svg_route_candidate_pair(candidates, str(strategy))
    if not pair:
        raise ValueError(pair_error_message)

    (start_score, start_item), (end_score, end_item) = pair
    start_point = (float(start_item[2]), float(start_item[3]))
    end_point = (float(end_item[2]), float(end_item[3]))
    route_report = shortest_path_fn(
        nodes_coords=analysis.get("nodes", []) if isinstance(analysis, Mapping) else [],
        edges_ab=analysis.get("edges", []) if isinstance(analysis, Mapping) else [],
        p_start=start_point,
        p_end=end_point,
        snap_eps_px=0.25,
        simplify_epsilon=float(simplify_epsilon),
    )
    polyline = route_report.get("path_xy", []) if isinstance(route_report, Mapping) else []
    if not (isinstance(polyline, list) and len(polyline) >= 2):
        raise ValueError(empty_route_message)

    route_length = float(route_report.get("length", 0.0) or 0.0) if isinstance(route_report, Mapping) else 0.0
    if float(max_length) > 0 and route_length > float(max_length):
        raise ValueError(too_long_message)

    return {
        "start_item": start_item,
        "end_item": end_item,
        "start_score": float(start_score),
        "end_score": float(end_score),
        "route_report": route_report,
        "polyline": polyline,
        "length_px": route_length,
    }


def build_svg_auto_batch_report_row(
    edge_name: str,
    *,
    status: str,
    error: str,
    chosen: tuple[SvgRouteItem, SvgRouteItem, float, float, float, int] | None,
    quality_report: Mapping[str, Any] | None,
    review_status: str,
) -> dict[str, Any]:
    if not chosen:
        return {
            "edge": str(edge_name),
            "status": status,
            "review_status": "",
            "grade": "",
            "detour": None,
            "start": "",
            "end": "",
            "score_start": 0.0,
            "score_end": 0.0,
            "len_px": 0.0,
            "points": 0,
            "error": error,
        }

    start_item, end_item, start_score, end_score, length_px, point_count = chosen
    return {
        "edge": str(edge_name),
        "status": status,
        "review_status": str(review_status),
        "grade": str(quality_report.get("grade", "")) if isinstance(quality_report, Mapping) else "",
        "detour": quality_report.get("detour_ratio") if isinstance(quality_report, Mapping) else None,
        "start": str(start_item[1]),
        "end": str(end_item[1]),
        "score_start": float(start_score),
        "score_end": float(end_score),
        "len_px": float(length_px),
        "points": int(point_count),
        "error": error,
    }


def render_svg_route_auto_panel(
    session_state: MutableMapping[str, Any],
    items: Iterable[SvgRouteItem],
    texts: list[dict[str, Any]],
    analysis: Mapping[str, Any] | Any,
    edge_columns: Iterable[str],
    *,
    format_item_fn: Callable[[SvgRouteItem], str],
    name_score_fn: Callable[[str, str], float],
    shortest_path_fn: Callable[..., Mapping[str, Any]],
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
    safe_dataframe_fn: Callable[..., Any],
) -> None:
    edge_options = list(edge_columns)
    with st.expander("AUTO: propose -> route -> mapping (beta)", expanded=False):
        if not edge_options:
            st.info("Нет df_mdot веток (edge_cols пуст). Запустите детальный прогон с **record_full=True**.")
            return

        edge_auto = str(session_state.get("svg_route_assign_edge", "") or "")
        if not edge_auto:
            st.warning("Сначала выберите целевую ветку в ассистенте выше (guided).")
            return

        st.caption(f"Текущая целевая ветка: **{edge_auto}**")
        view_box = analysis.get("viewBox") if isinstance(analysis, Mapping) else None

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            auto_strategy = st.selectbox(
                "Стратегия выбора START/END (из top-K по score)",
                options=["Top2", "Best+Farthest", "FarthestPair"],
                index=1,
                key="route_auto_strategy",
                help=(
                    "Top2: берем 2 лучших по score. "
                    "Best+Farthest: START=лучший, END=самый дальний из top-K. "
                    "FarthestPair: выбираем самую далекую пару из top-K."
                ),
            )
        with col_a2:
            auto_write_mode = st.radio(
                "Режим записи (AUTO)",
                options=["Заменить", "Добавить сегмент"],
                horizontal=True,
                key="route_auto_write_mode",
            )

        col_b1, col_b2, col_b3, col_b4 = st.columns([1, 1, 1, 1])
        with col_b1:
            auto_thr = st.slider(
                "Мин. score",
                0.0,
                1.0,
                float(session_state.get("route_label_sugg_thr", 0.55)),
                step=0.01,
                key="route_auto_thr",
            )
        with col_b2:
            auto_k = st.slider(
                "Top-K",
                2,
                80,
                int(session_state.get("route_label_sugg_k", 12)),
                step=1,
                key="route_auto_k",
            )
        with col_b3:
            auto_simplify = st.slider(
                "Simplify (RDP, px)",
                0.0,
                10.0,
                float(session_state.get("svg_route_simplify_eps", 1.0)),
                step=0.1,
                key="route_auto_simplify",
            )
        with col_b4:
            auto_max_len = st.number_input(
                "MaxLen (px, 0=inf)",
                min_value=0.0,
                max_value=30000.0,
                value=float(session_state.get("route_auto_max_len", 0.0)),
                step=50.0,
                key="route_auto_max_len",
            )

        col_c1, col_c2, col_c3 = st.columns([1.2, 1.2, 2.0])
        with col_c1:
            btn_auto_one = st.button("AUTO: текущая", key="btn_route_auto_one")
        with col_c2:
            batch_n = st.number_input(
                "Batch N (неразм.)",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
                key="route_auto_batch_n",
            )
            btn_auto_batch = st.button("AUTO: batch", key="btn_route_auto_batch")
        with col_c3:
            st.caption(
                "AUTO использует fuzzy-score по текстовым меткам SVG. "
                "Лучше работает, если предварительно нажать **«Автофильтр по имени ветки»** в guided-блоке."
            )

        if btn_auto_one:
            try:
                auto_route = propose_svg_auto_route(
                    items,
                    edge_auto,
                    analysis,
                    min_score=float(auto_thr),
                    top_k=int(auto_k),
                    strategy=str(auto_strategy),
                    simplify_epsilon=float(auto_simplify),
                    max_length=float(auto_max_len),
                    name_score_fn=name_score_fn,
                    shortest_path_fn=shortest_path_fn,
                    not_enough_message="Недостаточно кандидатов меток для AUTO. Попробуйте снизить порог или очистить фильтр.",
                    pair_error_message="Не удалось выбрать пару меток.",
                    empty_route_message="AUTO: маршрут пустой или слишком короткий.",
                    too_long_message="AUTO: маршрут слишком длинный. Проверьте метки/фильтр.",
                )
                start_item = auto_route["start_item"]
                end_item = auto_route["end_item"]
                polyline = auto_route["polyline"]
                route_report = auto_route["route_report"]

                store_svg_auto_route_selection(
                    session_state,
                    start_item,
                    end_item,
                    format_item_fn=format_item_fn,
                )

                mapping = load_svg_mapping_or_empty(session_state.get("svg_mapping_text", ""), view_box=view_box)
                timestamp = float(time.time())
                quality_report = evaluate_svg_auto_route_quality(
                    session_state,
                    polyline,
                    route_report,
                    evaluate_quality_fn=evaluate_quality_fn,
                )
                meta = build_svg_auto_route_meta(
                    start_item,
                    end_item,
                    start_score=float(auto_route["start_score"]),
                    end_score=float(auto_route["end_score"]),
                    route_report=route_report,
                    strategy=str(auto_strategy),
                    quality_report=quality_report,
                    auto_batch=False,
                    timestamp=timestamp,
                )
                write_svg_edge_route(
                    mapping,
                    edge_auto,
                    polyline,
                    str(auto_write_mode),
                    meta,
                    view_box=view_box,
                )
                update_svg_mapping_meta(
                    mapping,
                    "last_auto_route_assign",
                    {"edge": edge_auto, "ts": timestamp},
                )
                persist_svg_mapping_text(session_state, mapping)
                store_svg_route_preview(session_state, polyline, route_report)

                st.success(
                    f"AUTO OK: {edge_auto} <- '{start_item[1]}' -> '{end_item[1]}' | "
                    f"len~{float(auto_route['length_px']):.0f}px, pts={len(polyline)}."
                )

                if session_state.get("route_auto_next", True):
                    request_next_unmapped_svg_edge(session_state, mapping, edge_options)
                if session_state.get("route_clear_after_assign", False):
                    clear_svg_route_preview(session_state)
            except Exception as exc:
                st.error(f"AUTO: не удалось: {exc}")

        if btn_auto_batch:
            try:
                mapping = load_svg_mapping_or_empty(session_state.get("svg_mapping_text", ""), view_box=view_box)
                edges_map = mapping.get("edges") if isinstance(mapping, dict) else {}
                if not isinstance(edges_map, dict):
                    edges_map = {}
                mapped_edges = set(edges_map.keys())
                todo = [edge_name for edge_name in edge_options if edge_name not in mapped_edges][: int(batch_n)]
                if not todo:
                    st.info("AUTO batch: нет неразмеченных веток (или N=0).")
                else:
                    all_items = build_svg_auto_all_label_items(texts)
                    progress_bar = st.progress(0.0)
                    report_rows: list[dict[str, Any]] = []
                    ok_count = 0
                    for index, edge_name in enumerate(todo):
                        status = "fail"
                        error = ""
                        chosen = None
                        quality_report = None
                        review_status = ""
                        try:
                            auto_route = propose_svg_auto_route(
                                all_items,
                                str(edge_name),
                                analysis,
                                min_score=float(auto_thr),
                                top_k=int(auto_k),
                                strategy=str(auto_strategy),
                                simplify_epsilon=float(auto_simplify),
                                max_length=float(auto_max_len),
                                name_score_fn=name_score_fn,
                                shortest_path_fn=shortest_path_fn,
                                not_enough_message="not enough label candidates",
                                pair_error_message="pair selection failed",
                                empty_route_message="empty route",
                                too_long_message="route too long",
                            )
                            timestamp = float(time.time())
                            quality_report = evaluate_svg_auto_route_quality(
                                session_state,
                                auto_route["polyline"],
                                auto_route["route_report"],
                                evaluate_quality_fn=evaluate_quality_fn,
                            )
                            review_status = resolve_svg_auto_review_status(quality_report)
                            meta = build_svg_auto_route_meta(
                                auto_route["start_item"],
                                auto_route["end_item"],
                                start_score=float(auto_route["start_score"]),
                                end_score=float(auto_route["end_score"]),
                                route_report=auto_route["route_report"],
                                strategy=str(auto_strategy),
                                quality_report=quality_report,
                                auto_batch=True,
                                timestamp=timestamp,
                            )
                            write_svg_edge_route(
                                mapping,
                                str(edge_name),
                                auto_route["polyline"],
                                str(auto_write_mode),
                                meta,
                                view_box=view_box,
                            )
                            status = "ok"
                            ok_count += 1
                            chosen = (
                                auto_route["start_item"],
                                auto_route["end_item"],
                                float(auto_route["start_score"]),
                                float(auto_route["end_score"]),
                                float(auto_route["length_px"]),
                                int(len(auto_route["polyline"])),
                            )
                        except Exception as exc:
                            error = str(exc)

                        report_rows.append(
                            build_svg_auto_batch_report_row(
                                str(edge_name),
                                status=status,
                                error=error,
                                chosen=chosen,
                                quality_report=quality_report,
                                review_status=review_status,
                            )
                        )
                        progress_bar.progress((index + 1) / max(1, len(todo)))

                    update_svg_mapping_meta(
                        mapping,
                        "auto_batch_last",
                        {"ok": int(ok_count), "total": int(len(todo)), "ts": float(time.time())},
                    )
                    persist_svg_mapping_text(session_state, mapping)

                    st.success(f"AUTO batch завершен: OK {ok_count}/{len(todo)}")
                    try:
                        report_frame = pd.DataFrame(report_rows)
                        safe_dataframe_fn(report_frame, height=260)
                        st.download_button(
                            "Скачать отчет AUTO batch (csv)",
                            data=report_frame.to_csv(index=False).encode("utf-8"),
                            file_name="svg_auto_batch_report.csv",
                            mime="text/csv",
                        )
                    except Exception:
                        pass
            except Exception as exc:
                st.error(f"AUTO batch: не удалось: {exc}")
