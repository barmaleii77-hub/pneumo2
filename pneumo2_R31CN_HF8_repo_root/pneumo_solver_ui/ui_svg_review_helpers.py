from __future__ import annotations

import json
from collections.abc import MutableMapping, Sequence
from typing import Any


SVG_REVIEW_STATUSES = ["approved", "pending", "rejected", "unknown"]


def build_svg_review_conveyor_state(mapping_text: Any) -> tuple[dict[str, int], list[str]]:
    mapping_obj = None
    try:
        if isinstance(mapping_text, str) and mapping_text.strip():
            mapping_obj = json.loads(mapping_text)
        elif isinstance(mapping_text, dict):
            mapping_obj = mapping_text
    except Exception:
        mapping_obj = None

    counts = {"approved": 0, "pending": 0, "rejected": 0, "unknown": 0, "total": 0}
    pending_list: list[str] = []
    try:
        if isinstance(mapping_obj, dict):
            edges_geo = mapping_obj.get("edges", {})
            edges_meta = mapping_obj.get("edges_meta", {})
            if not isinstance(edges_geo, dict):
                edges_geo = {}
            if not isinstance(edges_meta, dict):
                edges_meta = {}
            for edge_name, segments in edges_geo.items():
                if not isinstance(segments, list) or not segments:
                    continue
                status = "unknown"
                try:
                    meta = edges_meta.get(str(edge_name), {})
                    review = meta.get("review", {}) if isinstance(meta, dict) else {}
                    status_value = review.get("status", "") if isinstance(review, dict) else ""
                    status = str(status_value) if status_value else "unknown"
                except Exception:
                    status = "unknown"
                counts["total"] += 1
                if status in counts:
                    counts[status] += 1
                else:
                    counts["unknown"] += 1
                if status in ("pending", "unknown", ""):
                    pending_list.append(str(edge_name))
    except Exception:
        pass
    return counts, sorted(set(pending_list))


def step_svg_review_pending_edge(
    session_state: MutableMapping[str, Any],
    pending_list: Sequence[str],
    *,
    direction: int,
) -> str | None:
    if not pending_list:
        return None
    current = str(session_state.get("svg_selected_edge") or "")
    if direction < 0:
        index = pending_list.index(current) if current in pending_list else 0
        next_index = (index - 1) if index > 0 else (len(pending_list) - 1)
    else:
        index = pending_list.index(current) if current in pending_list else -1
        next_index = (index + 1) if (index + 1) < len(pending_list) else 0
    target = str(pending_list[next_index])
    session_state["svg_selected_edge"] = target
    session_state["svg_selected_node"] = ""
    return target


def render_svg_review_controls(
    st_module: Any,
    session_state: MutableMapping[str, Any],
    *,
    mapping_text: Any,
) -> None:
    col1, col2, col3 = st_module.columns([1.2, 1.2, 2.2])
    with col1:
        st_module.checkbox(
            "Показать review overlay",
            value=True,
            key="svg_show_review_overlay",
            help="Раскраска mapping.edges по edges_meta.review.status поверх SVG.",
        )
    with col2:
        st_module.checkbox(
            "Review hotkeys",
            value=False,
            key="svg_review_pick_mode",
            help="Включает горячие клики по линиям overlay: Shift=approved, Ctrl/Cmd=rejected, Alt=pending.",
        )
    with col3:
        st_module.multiselect(
            "Показывать статусы",
            options=list(SVG_REVIEW_STATUSES),
            default=["approved", "pending", "rejected"],
            key="svg_review_statuses",
        )
    with col3:
        st_module.checkbox(
            "HUD на схеме",
            value=True,
            key="svg_review_hud",
            help="Показывает небольшую панель статистики review прямо поверх SVG (с кнопками Next/Prev pending).",
        )

    with st_module.expander("Review conveyor (pending-first)", expanded=False):
        counts, pending_list = build_svg_review_conveyor_state(mapping_text)

        c1, c2, c3, c4, c5 = st_module.columns(5)
        c1.metric("approved", counts["approved"])
        c2.metric("pending", counts["pending"])
        c3.metric("rejected", counts["rejected"])
        c4.metric("unknown", counts["unknown"])
        c5.metric("total", counts["total"])

        st_module.checkbox(
            "Auto-advance после approve/reject",
            value=True,
            key="svg_review_auto_advance",
            help="После Shift/Ctrl-клика по линии overlay автоматически выбирается следующая pending/unknown ветка.",
        )

        nav1, nav2, nav3 = st_module.columns([1.2, 1.2, 2.4])
        with nav1:
            if st_module.button("◀ Prev pending", key="btn_prev_pending"):
                if step_svg_review_pending_edge(session_state, pending_list, direction=-1) is not None:
                    st_module.rerun()
        with nav2:
            if st_module.button("Next pending ▶", key="btn_next_pending"):
                if step_svg_review_pending_edge(session_state, pending_list, direction=1) is not None:
                    st_module.rerun()
        with nav3:
            if pending_list:
                st_module.caption(
                    f"pending/unknown: {len(pending_list)} | текущая: {session_state.get('svg_selected_edge')}"
                )
            else:
                st_module.caption("pending/unknown: 0")

    last_review = session_state.get("svg_review_last")
    if isinstance(last_review, dict) and last_review.get("edge"):
        st_module.caption(f"Последнее review: {last_review.get('edge')} → {last_review.get('status')}")
