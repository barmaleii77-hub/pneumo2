from __future__ import annotations

import json
import time
from typing import Any


def recompute_svg_mapping_route_quality(
    session_state: dict[str, Any],
    *,
    edges_geo: dict[str, Any] | None,
    edges_meta: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
    first_poly_fn: Any,
    evaluate_quality_fn: Any,
) -> None:
    edges_geo = edges_geo if isinstance(edges_geo, dict) else {}
    edges_meta = edges_meta if isinstance(edges_meta, dict) else {}
    mapping = mapping if isinstance(mapping, dict) else {}

    for edge_name in list(edges_geo.keys()):
        poly = first_poly_fn(str(edge_name))
        if not poly:
            continue
        quality = evaluate_quality_fn(
            poly,
            attach_start=None,
            attach_end=None,
            min_turn_deg=float(session_state.get("route_q_min_turn_deg", 45.0)),
            max_detour=float(session_state.get("route_q_max_detour", 8.0)),
            max_attach_dist=float(session_state.get("route_q_max_attach_dist", 35.0)),
        )
        edge_meta = edges_meta.get(str(edge_name), {})
        if not isinstance(edge_meta, dict):
            edge_meta = {}
        edge_meta["quality"] = quality
        edge_meta.setdefault("review", {})
        if isinstance(edge_meta.get("review"), dict):
            edge_meta["review"].setdefault("status", "pending")
            edge_meta["review"].setdefault("by", "quality_recompute")
            edge_meta["review"]["ts"] = float(time.time())
        edges_meta[str(edge_name)] = edge_meta

    mapping["edges_meta"] = edges_meta
    session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)


def approve_all_pass_svg_mapping_routes(
    session_state: dict[str, Any],
    *,
    edges_meta: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
) -> int:
    edges_meta = edges_meta if isinstance(edges_meta, dict) else {}
    mapping = mapping if isinstance(mapping, dict) else {}

    approved = 0
    for edge_name, edge_meta in list(edges_meta.items()):
        if not isinstance(edge_meta, dict):
            continue
        quality = edge_meta.get("quality")
        if isinstance(quality, dict) and str(quality.get("grade", "")).upper() == "PASS":
            edge_meta.setdefault("review", {})
            if isinstance(edge_meta.get("review"), dict):
                edge_meta["review"]["status"] = "approved"
                edge_meta["review"]["by"] = "approve_pass"
                edge_meta["review"]["ts"] = float(time.time())
                approved += 1
            edges_meta[str(edge_name)] = edge_meta

    mapping["edges_meta"] = edges_meta
    session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)
    return approved


def render_svg_mapping_review_actions(
    st: Any,
    session_state: dict[str, Any],
    *,
    edges_geo: dict[str, Any] | None,
    edges_meta: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
    first_poly_fn: Any,
    evaluate_quality_fn: Any,
) -> None:
    col_rq1, col_rq2, col_rq3 = st.columns([1.2, 1.2, 2.0])
    with col_rq1:
        btn_recompute_q = st.button("Recompute quality (all)", key="btn_map_recompute_quality")
    with col_rq2:
        btn_approve_pass = st.button("Approve all PASS", key="btn_map_approve_pass")
    with col_rq3:
        st.caption("Quality хранится в edges_meta[edge].quality; статусы — в edges_meta[edge].review.status.")

    if btn_recompute_q:
        try:
            recompute_svg_mapping_route_quality(
                session_state,
                edges_geo=edges_geo,
                edges_meta=edges_meta,
                mapping=mapping,
                first_poly_fn=first_poly_fn,
                evaluate_quality_fn=evaluate_quality_fn,
            )
            st.success("Quality пересчитан и сохранён в mapping JSON (text area ниже обновится после rerun).")
            st.rerun()
        except Exception as exc:
            st.error(f"Не удалось пересчитать quality: {exc}")

    if btn_approve_pass:
        try:
            approved = approve_all_pass_svg_mapping_routes(
                session_state,
                edges_meta=edges_meta,
                mapping=mapping,
            )
            st.success(f"Approved PASS: {approved}")
            st.rerun()
        except Exception as exc:
            st.error(f"Approve PASS: ошибка: {exc}")
