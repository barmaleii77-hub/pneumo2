from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


def load_packaging_params_from_base_json(path_like: str | Path | None) -> dict[str, Any]:
    text = str(path_like or "").strip()
    if not text:
        return {}
    try:
        path = Path(text)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def render_packaging_surface_metrics(st: Any, df: pd.DataFrame | None) -> None:
    if df is None or df.empty or "pass_packaging" not in df.columns:
        return
    pack_pass = int(pd.to_numeric(df["pass_packaging"], errors="coerce").fillna(0).sum())
    pack_fail = int(len(df) - pack_pass)
    pack_truth = int(
        pd.to_numeric(df["packaging_truth_ready"], errors="coerce").fillna(0).sum()
    ) if "packaging_truth_ready" in df.columns else 0
    pack_fallback = int(
        (pd.to_numeric(df["число_runtime_fallback_пружины"], errors="coerce").fillna(0) > 0).sum()
    ) if "число_runtime_fallback_пружины" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Геометрия OK", pack_pass)
    with c2:
        st.metric("Геометрия: есть проблемы", pack_fail)
    with c3:
        st.metric("Данных достаточно", pack_truth)
    with c4:
        st.metric("Служебный fallback", pack_fallback)


def apply_packaging_surface_filters(
    st: Any,
    df: pd.DataFrame | None,
    *,
    key_prefix: str,
    compact: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    out = df.copy()
    use_pass = st.checkbox(
        "Только с OK по геометрии",
        value=bool(st.session_state.get(f"{key_prefix}_packaging_pass_filter", False)),
        key=f"{key_prefix}_packaging_pass_filter",
    )
    if use_pass and "pass_packaging" in out.columns:
        out = out[pd.to_numeric(out["pass_packaging"], errors="coerce").fillna(0) >= 1.0]

    use_truth = st.checkbox(
        "Только с достаточными данными",
        value=bool(st.session_state.get(f"{key_prefix}_packaging_truth_ready", False)),
        key=f"{key_prefix}_packaging_truth_ready",
    )
    if use_truth and "packaging_truth_ready" in out.columns:
        out = out[pd.to_numeric(out["packaging_truth_ready"], errors="coerce").fillna(0) >= 1.0]

    hide_fallback = st.checkbox(
        "Скрыть служебный fallback пружин",
        value=bool(st.session_state.get(f"{key_prefix}_packaging_no_fallback", False)),
        key=f"{key_prefix}_packaging_no_fallback",
    )
    if hide_fallback and "число_runtime_fallback_пружины" in out.columns:
        out = out[pd.to_numeric(out["число_runtime_fallback_пружины"], errors="coerce").fillna(0) <= 0.0]

    no_interference = st.checkbox(
        "Только без пересечений пружин",
        value=bool(st.session_state.get(f"{key_prefix}_packaging_no_interference", False)),
        key=f"{key_prefix}_packaging_no_interference",
    )
    if no_interference:
        if "число_пересечений_пружина_цилиндр" in out.columns:
            out = out[pd.to_numeric(out["число_пересечений_пружина_цилиндр"], errors="coerce").fillna(0) <= 0.0]
        if "число_пересечений_пружина_пружина" in out.columns:
            out = out[pd.to_numeric(out["число_пересечений_пружина_пружина"], errors="coerce").fillna(0) <= 0.0]

    if not compact:
        st.caption(f"После фильтров по геометрии узлов: {len(out)} / {len(df)}")
    return out


def packaging_surface_result_columns(
    df: pd.DataFrame | None,
    *,
    leading: list[str] | None = None,
    include_metrics: bool = True,
) -> list[str]:
    if df is None or df.empty:
        return list(leading or [])

    cols: list[str] = []
    for c in list(leading or []):
        if c in df.columns and c not in cols:
            cols.append(c)

    for c in [
        "pass_packaging",
        "pass_packaging_верификация",
        "packaging_truth_ready",
        "packaging_верификация_статус",
    ]:
        if c in df.columns and c not in cols:
            cols.append(c)

    if include_metrics:
        for c in [
            "мин_зазор_пружина_цилиндр_м",
            "мин_зазор_пружина_пружина_м",
            "макс_ошибка_midstroke_t0_м",
            "мин_запас_до_coil_bind_пружины_м",
            "число_runtime_fallback_пружины",
            "число_пересечений_пружина_цилиндр",
            "число_пересечений_пружина_пружина",
        ]:
            if c in df.columns and c not in cols:
                cols.append(c)

    return cols


__all__ = [
    "apply_packaging_surface_filters",
    "load_packaging_params_from_base_json",
    "packaging_surface_result_columns",
    "render_packaging_surface_metrics",
]
