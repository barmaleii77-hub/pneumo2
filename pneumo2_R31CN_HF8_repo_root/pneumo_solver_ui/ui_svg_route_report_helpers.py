from __future__ import annotations

import json
from typing import Any, Callable, Mapping, MutableMapping

import streamlit as st


DEFAULT_SVG_ROUTE_QUALITY_PARAMS = {
    "min_turn_deg": 45.0,
    "max_detour": 8.0,
    "max_attach_dist": 35.0,
}


def build_svg_route_report_details(route_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": route_report.get("ok"),
        "length_px": route_report.get("length"),
        "node_count": route_report.get("node_count"),
        "attach_start": route_report.get("attach_start"),
        "attach_end": route_report.get("attach_end"),
        "params": route_report.get("params"),
    }


def resolve_svg_route_quality_params(session_state: MutableMapping[str, Any]) -> dict[str, float]:
    try:
        return {
            "min_turn_deg": float(session_state.get("route_q_min_turn_deg", 45.0)),
            "max_detour": float(session_state.get("route_q_max_detour", 8.0)),
            "max_attach_dist": float(session_state.get("route_q_max_attach_dist", 35.0)),
        }
    except Exception:
        return dict(DEFAULT_SVG_ROUTE_QUALITY_PARAMS)


def evaluate_svg_route_quality_report(
    session_state: MutableMapping[str, Any],
    route_report: Mapping[str, Any],
    *,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> Mapping[str, Any]:
    params = resolve_svg_route_quality_params(session_state)
    try:
        quality_report = evaluate_quality_fn(
            route_report.get("path_xy", []),
            attach_start=route_report.get("attach_start"),
            attach_end=route_report.get("attach_end"),
            min_turn_deg=float(params["min_turn_deg"]),
            max_detour=float(params["max_detour"]),
            max_attach_dist=float(params["max_attach_dist"]),
        )
        session_state["svg_route_quality"] = quality_report
        return quality_report
    except Exception as exc:
        return {"grade": "FAIL", "reasons": [f"Не удалось оценить: {exc}"]}


def build_svg_route_quality_details(quality_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "grade": quality_report.get("grade"),
        "length_px": quality_report.get("length_px"),
        "detour_ratio": quality_report.get("detour_ratio"),
        "points": quality_report.get("points"),
        "turns": quality_report.get("turns"),
        "self_intersections": quality_report.get("self_intersections"),
        "attach_start_dist": quality_report.get("attach_start_dist"),
        "attach_end_dist": quality_report.get("attach_end_dist"),
    }


def render_svg_route_report_panel(
    session_state: MutableMapping[str, Any],
    route_report: Mapping[str, Any],
    *,
    evaluate_quality_fn: Callable[..., Mapping[str, Any]],
) -> None:
    with st.expander("Маршрут: детали", expanded=False):
        st.write(build_svg_route_report_details(route_report))
        st.download_button(
            "Скачать маршрут (json)",
            data=json.dumps(route_report, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="svg_route.json",
            mime="application/json",
        )

    q_params = resolve_svg_route_quality_params(session_state)
    with st.expander("Проверка качества маршрута (beta)", expanded=False):
        col_q1, col_q2, col_q3 = st.columns(3)
        with col_q1:
            st.slider(
                "Порог поворота (deg)",
                20.0,
                120.0,
                float(q_params["min_turn_deg"]),
                step=5.0,
                key="route_q_min_turn_deg",
            )
        with col_q2:
            st.slider(
                "Max detour",
                2.0,
                20.0,
                float(q_params["max_detour"]),
                step=0.5,
                key="route_q_max_detour",
            )
        with col_q3:
            st.slider(
                "Max dist метка→трубка (px)",
                5.0,
                120.0,
                float(q_params["max_attach_dist"]),
                step=5.0,
                key="route_q_max_attach_dist",
            )

        quality_report = evaluate_svg_route_quality_report(
            session_state,
            route_report,
            evaluate_quality_fn=evaluate_quality_fn,
        )
        grade = str(quality_report.get("grade", ""))
        if grade == "PASS":
            st.success("PASS: маршрут выглядит адекватно.")
        elif grade == "FAIL":
            st.error("FAIL: маршрут подозрительный (см. причины ниже).")
        else:
            st.warning("WARN: маршрут требует проверки.")

        st.write(build_svg_route_quality_details(quality_report))
        if quality_report.get("reasons"):
            st.markdown("**Причины / предупреждения:**")
            for reason in quality_report.get("reasons", []):
                st.write(f"- {reason}")
        st.download_button(
            "Скачать quality report (json)",
            data=json.dumps(quality_report, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="svg_route_quality.json",
            mime="application/json",
        )
