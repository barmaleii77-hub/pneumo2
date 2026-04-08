from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd


def build_svg_mapping_review_rows(
    edge_columns: list[str] | None,
    edges_geo: dict[str, Any] | None,
    edges_meta: dict[str, Any] | None,
    *,
    first_poly_fn: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    edges_geo = edges_geo if isinstance(edges_geo, dict) else {}
    edges_meta = edges_meta if isinstance(edges_meta, dict) else {}
    try:
        edges_list = list(edge_columns) if edge_columns else list(edges_geo.keys())
    except Exception:
        edges_list = list(edges_geo.keys())

    for edge_name in edges_list:
        edge_name = str(edge_name)
        poly = first_poly_fn(edge_name)
        edge_meta = edges_meta.get(edge_name, {})
        if not isinstance(edge_meta, dict):
            edge_meta = {}
        review = edge_meta.get("review", {})
        if not isinstance(review, dict):
            review = {}
        quality = edge_meta.get("quality", {})
        if not isinstance(quality, dict):
            quality = {}
        rows.append(
            {
                "edge": edge_name,
                "has_geom": bool(poly),
                "status": str(review.get("status", "")) if review else "",
                "grade": quality.get("grade", ""),
                "len_px": quality.get("length_px", None),
                "detour": quality.get("detour_ratio", None),
                "points": quality.get("points", None),
            }
        )
    return rows


def render_svg_mapping_review_panel(
    st: Any,
    session_state: dict[str, Any],
    *,
    edge_columns: list[str] | None,
    edges_geo: dict[str, Any] | None,
    edges_meta: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
    first_poly_fn: Any,
    safe_dataframe_fn: Any,
) -> None:
    edges_meta = edges_meta if isinstance(edges_meta, dict) else {}
    mapping = mapping if isinstance(mapping, dict) else {}

    rows = build_svg_mapping_review_rows(
        edge_columns,
        edges_geo,
        edges_meta,
        first_poly_fn=first_poly_fn,
    )
    df_rev = pd.DataFrame(rows)
    if len(df_rev) == 0:
        st.info("Нет данных для review.")
        return

    col_f1, col_f2 = st.columns([1.2, 2.0])
    with col_f1:
        status_filter = st.multiselect(
            "Фильтр по status",
            options=sorted([item for item in df_rev["status"].unique().tolist() if item != ""]),
            default=[],
            key="map_review_status_filter",
        )
    with col_f2:
        grade_filter = st.multiselect(
            "Фильтр по grade",
            options=sorted([item for item in df_rev["grade"].unique().tolist() if item != ""]),
            default=[],
            key="map_review_grade_filter",
        )

    df_show = df_rev.copy()
    if status_filter:
        df_show = df_show[df_show["status"].isin(status_filter)]
    if grade_filter:
        df_show = df_show[df_show["grade"].isin(grade_filter)]

    safe_dataframe_fn(
        df_show.sort_values(
            ["has_geom", "status", "grade", "edge"],
            ascending=[False, True, True, True],
        ),
        height=280,
    )
    st.download_button(
        "Скачать review table (csv)",
        data=df_show.to_csv(index=False).encode("utf-8"),
        file_name="mapping_review_table.csv",
        mime="text/csv",
    )

    st.markdown("#### Изменить статус / заметку для одной ветки")
    edge_sel = ""
    if rows:
        edge_sel = st.selectbox(
            "Edge",
            options=[row["edge"] for row in rows],
            index=0,
            key="map_review_edge_select",
        )
    else:
        st.info("Нет веток для выбора (rows пуст).")

    if not edge_sel:
        return

    edge_meta = edges_meta.get(str(edge_sel), {})
    if not isinstance(edge_meta, dict):
        edge_meta = {}
    review = edge_meta.get("review", {})
    if not isinstance(review, dict):
        review = {}
    cur_status = str(review.get("status", "pending") or "pending")
    note = str(review.get("note", "") or "")

    col_e1, col_e2 = st.columns([1.0, 2.0])
    with col_e1:
        new_status = st.radio(
            "status",
            options=["approved", "pending", "rejected"],
            index=["approved", "pending", "rejected"].index(cur_status)
            if cur_status in ["approved", "pending", "rejected"]
            else 1,
            horizontal=True,
            key="map_review_status_set",
        )
    with col_e2:
        new_note = st.text_input("note", value=note, key="map_review_note_set")

    col_a1, col_a2, col_a3 = st.columns([1.2, 1.2, 2.0])
    with col_a1:
        btn_save_status = st.button("Save review", key="btn_map_review_save")
    with col_a2:
        btn_clear_geom = st.button("Clear geometry", key="btn_map_review_clear_geom")
    with col_a3:
        st.caption("Clear geometry удаляет mapping.edges[edge], но оставляет edges_meta (для истории).")

    if btn_save_status:
        try:
            edge_meta.setdefault("review", {})
            if not isinstance(edge_meta.get("review"), dict):
                edge_meta["review"] = {}
            edge_meta["review"]["status"] = str(new_status)
            edge_meta["review"]["note"] = str(new_note)
            edge_meta["review"]["by"] = "user"
            edge_meta["review"]["ts"] = float(time.time())
            edges_meta[str(edge_sel)] = edge_meta
            mapping["edges_meta"] = edges_meta
            session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)
            st.success("Review сохранён.")
            st.rerun()
        except Exception as exc:
            st.error(f"Save review: ошибка: {exc}")

    if btn_clear_geom:
        try:
            if isinstance(mapping.get("edges"), dict):
                mapping["edges"].pop(str(edge_sel), None)
            edge_meta.setdefault("review", {})
            if not isinstance(edge_meta.get("review"), dict):
                edge_meta["review"] = {}
            edge_meta["review"]["status"] = "rejected"
            edge_meta["review"]["by"] = "clear_geom"
            edge_meta["review"]["ts"] = float(time.time())
            edges_meta[str(edge_sel)] = edge_meta
            mapping["edges_meta"] = edges_meta
            session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)
            st.success("Геометрия удалена (и помечено rejected).")
            st.rerun()
        except Exception as exc:
            st.error(f"Clear geometry: ошибка: {exc}")
