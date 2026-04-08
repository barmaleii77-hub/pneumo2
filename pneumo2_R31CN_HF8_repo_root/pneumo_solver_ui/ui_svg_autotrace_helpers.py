from __future__ import annotations

import json
from typing import Any, Sequence

import pandas as pd


AUTOTRACE_SESSION_KEYS = (
    "svg_autotrace_analysis",
    "svg_autotrace_report",
    "svg_autotrace_components",
)


def _clear_autotrace_state(session_state) -> None:
    for key in AUTOTRACE_SESSION_KEYS:
        session_state.pop(key, None)


def render_svg_autotrace_panel(
    st_module,
    *,
    svg_inline: str,
    edge_columns: Sequence[str],
    selected_node_names: Sequence[str],
    node_columns: Sequence[str],
    has_svg_autotrace: bool,
    extract_polylines_fn,
    auto_build_mapping_from_svg_fn,
    detect_component_bboxes_fn,
    safe_dataframe_fn,
) -> dict[str, object]:
    with st_module.expander("Авторазметка из SVG (beta)", expanded=False):
        if not has_svg_autotrace:
            st_module.error(
                "pneumo_solver_ui.svg_autotrace не импортируется. Проверьте целостность пакета pneumo_solver_ui."
            )
            return {"status": "missing"}

        st_module.info(
            "Авторазметка пытается построить черновой mapping JSON по геометрии линий (<line>) "
            "и текстовым меткам (<text>, transform=matrix...). "
            "Это помогает быстро получить стартовый mapping без ручного клика по каждой ветке."
        )

        col1, col2, col3 = st_module.columns(3)
        with col1:
            tol_merge = st_module.slider(
                "Tol склейки концов (px)",
                0.5,
                8.0,
                2.1,
                step=0.1,
                key="svg_autotrace_tol_merge",
            )
        with col2:
            max_label_dist = st_module.slider(
                "Макс. расстояние метка → трубка (px)",
                10.0,
                300.0,
                80.0,
                step=5.0,
                key="svg_autotrace_max_label_dist",
            )
        with col3:
            min_name_score = st_module.slider(
                "Порог сходства имён (fuzzy)",
                0.50,
                0.95,
                0.75,
                step=0.05,
                key="svg_autotrace_min_name_score",
            )

        col4, col5, col6 = st_module.columns(3)
        with col4:
            simplify_eps = st_module.slider(
                "Упростить полилинии (epsilon, px)",
                0.0,
                5.0,
                0.0,
                step=0.2,
                key="svg_autotrace_simplify_eps",
            )
        with col5:
            snap_nodes = st_module.checkbox(
                "Snap узлы к графу",
                value=True,
                key="svg_autotrace_snap_nodes",
            )
        with col6:
            prefer_junc = st_module.checkbox(
                "Prefer junction (deg!=2)",
                value=True,
                key="svg_autotrace_prefer_junction",
            )
        node_snap_max_dist = st_module.slider(
            "Макс. dist метка→junction для snap (px)",
            5.0,
            160.0,
            40.0,
            step=5.0,
            key="svg_autotrace_snap_dist",
        )

        default_auto_edges = list(edge_columns[: min(16, len(edge_columns))])
        auto_edges = st_module.multiselect(
            "Ветки, для которых построить mapping.edges",
            options=list(edge_columns),
            default=default_auto_edges,
            key="svg_autotrace_edges",
        )
        auto_nodes = st_module.multiselect(
            "Узлы, для которых построить mapping.nodes (координаты подписей давления)",
            options=(list(selected_node_names) if selected_node_names else list(node_columns)),
            default=(list(selected_node_names) if selected_node_names else []),
            key="svg_autotrace_nodes",
        )

        btn_col1, btn_col2, btn_col3 = st_module.columns(3)
        with btn_col1:
            do_analyze = st_module.button("Проанализировать SVG", key="btn_svg_autotrace_analyze")
        with btn_col2:
            do_build = st_module.button("Сгенерировать mapping (auto)", key="btn_svg_autotrace_build")
        with btn_col3:
            do_clear = st_module.button("Очистить результаты", key="btn_svg_autotrace_clear")

        if do_clear:
            _clear_autotrace_state(st_module.session_state)
            st_module.success("Очищено.")

        if do_analyze:
            try:
                analysis = extract_polylines_fn(svg_inline, tol_merge=float(tol_merge))
                st_module.session_state["svg_autotrace_analysis"] = analysis
                st_module.success(
                    f"SVG разобран: polylines={len(analysis.get('polylines', []))}, "
                    f"nodes={len(analysis.get('nodes', []))}, edges={len(analysis.get('edges', []))}"
                )
            except Exception as exc:
                st_module.error(f"Ошибка анализа SVG: {exc}")

        if do_build:
            try:
                mapping_auto, report_auto = auto_build_mapping_from_svg_fn(
                    svg_text=svg_inline,
                    edge_names=list(auto_edges),
                    node_names=list(auto_nodes),
                    tol_merge=float(tol_merge),
                    max_label_dist=float(max_label_dist),
                    min_name_score=float(min_name_score),
                    simplify_epsilon=float(simplify_eps),
                    snap_nodes_to_graph=bool(snap_nodes),
                    prefer_junctions=bool(prefer_junc),
                    node_snap_max_dist=float(node_snap_max_dist),
                )
                st_module.session_state["svg_mapping_text"] = json.dumps(
                    mapping_auto,
                    ensure_ascii=False,
                    indent=2,
                )
                st_module.session_state["svg_autotrace_report"] = report_auto
                st_module.success(
                    f"mapping обновлён (edges={len(mapping_auto.get('edges', {}))}, "
                    f"nodes={len(mapping_auto.get('nodes', {}))}). "
                    "Прокрутите ниже - mapping уже подставлен в текстовое поле."
                )
            except Exception as exc:
                st_module.error(f"Ошибка авторазметки: {exc}")

        analysis = st_module.session_state.get("svg_autotrace_analysis")
        report_auto = st_module.session_state.get("svg_autotrace_report")

        if analysis:
            with st_module.expander("Результаты анализа SVG", expanded=False):
                try:
                    deg_counts = analysis.get("degree_counts", {})
                    st_module.write(
                        {
                            "viewBox": analysis.get("viewBox"),
                            "nodes": len(analysis.get("nodes", [])),
                            "edges": len(analysis.get("edges", [])),
                            "polylines": len(analysis.get("polylines", [])),
                            "degree_counts": deg_counts,
                            "junction_nodes": len(analysis.get("junction_nodes", [])),
                            "poly_endpoints": len(analysis.get("poly_endpoints", [])),
                        }
                    )
                    df_txt = pd.DataFrame(analysis.get("texts", []))
                    if len(df_txt):
                        df_show = df_txt.copy()
                        df_show["len"] = df_show["text"].astype(str).str.len()
                        df_show = df_show.sort_values(["len", "text"]).head(200)
                        safe_dataframe_fn(df_show[["text", "x", "y", "klass"]], height=280)
                    st_module.download_button(
                        "Скачать анализ SVG (json)",
                        data=json.dumps(analysis, ensure_ascii=False, indent=2).encode("utf-8"),
                        file_name="svg_analysis.json",
                        mime="application/json",
                    )
                except Exception as exc:
                    st_module.error(f"Не удалось показать анализ: {exc}")

        if report_auto:
            with st_module.expander("Отчёт авторазметки (mapping)", expanded=False):
                try:
                    st_module.write(report_auto.get("summary", {}))
                    df_edges = pd.DataFrame(report_auto.get("edges", []))
                    if len(df_edges):
                        safe_dataframe_fn(
                            df_edges.sort_values(["score", "dist"], ascending=[False, True]),
                            height=260,
                        )
                    df_nodes = pd.DataFrame(report_auto.get("nodes", []))
                    if len(df_nodes):
                        try:
                            df_nodes_show = df_nodes.sort_values(
                                ["score", "dist_label_poly"],
                                ascending=[False, True],
                            )
                        except Exception:
                            df_nodes_show = df_nodes
                        safe_dataframe_fn(df_nodes_show, height=240)
                    if report_auto.get("unmatched_nodes"):
                        st_module.warning(
                            f"Не сопоставлены {len(report_auto['unmatched_nodes'])} узлов."
                        )
                    if report_auto.get("unmatched_edges"):
                        st_module.warning(
                            f"Не сопоставлены {len(report_auto['unmatched_edges'])} веток."
                        )
                    st_module.download_button(
                        "Скачать отчёт авторазметки (json)",
                        data=json.dumps(report_auto, ensure_ascii=False, indent=2).encode("utf-8"),
                        file_name="svg_autotrace_report.json",
                        mime="application/json",
                    )
                except Exception as exc:
                    st_module.error(f"Не удалось показать отчёт: {exc}")

        with st_module.expander("Компоненты (bbox по текстовым меткам)", expanded=False):
            st_module.caption(
                "Грубая оценка bbox компонентов вокруг меток типа 'Ресивер', 'Аккумулятор', 'Рег.'."
            )
            comp_r = st_module.slider(
                "Радиус поиска линий вокруг метки (px)",
                40,
                260,
                120,
                step=10,
                key="svg_comp_radius",
            )
            if st_module.button("Найти компоненты", key="btn_svg_find_components"):
                try:
                    comps = detect_component_bboxes_fn(svg_inline, radius=float(comp_r))
                    st_module.session_state["svg_autotrace_components"] = comps
                    st_module.success(f"Найдено компонентов: {len(comps)}")
                except Exception as exc:
                    st_module.error(f"Ошибка поиска компонентов: {exc}")

            comps = st_module.session_state.get("svg_autotrace_components", [])
            if comps:
                dfc = pd.DataFrame(comps)
                safe_dataframe_fn(dfc, height=260)
                st_module.download_button(
                    "Скачать компоненты (json)",
                    data=json.dumps(comps, ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name="svg_components.json",
                    mime="application/json",
                )

        return {
            "status": "ok",
            "has_analysis": bool(analysis),
            "has_report": bool(report_auto),
            "components_count": len(st_module.session_state.get("svg_autotrace_components", [])),
        }
