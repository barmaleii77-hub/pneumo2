
# -*- coding: utf-8 -*-
"""compare_npz_web.py

Streamlit UI: Compare NPZ (web)
- Overlay / Δ to reference
- Zero baseline for displacements/angles/road (static = 0)
- Locked Y scales (by signal / by unit)
- Heatmap: max |Δ|
- Influence: meta numeric params -> output metrics (correlation)

This module is imported by `pages/06_CompareNPZ_Web.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import hashlib
import json

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go  # type: ignore
    import plotly.express as px  # type: ignore
    from plotly.subplots import make_subplots  # type: ignore
    _HAS_PLOTLY = True
    _PLOTLY_IMPORT_ERR = None
except Exception as _e_plotly:  # pragma: no cover - depends on runtime env
    go = None  # type: ignore
    px = None  # type: ignore
    make_subplots = None  # type: ignore
    _HAS_PLOTLY = False
    _PLOTLY_IMPORT_ERR = _e_plotly

# Streamlit is optional at import-time (self-checks / CLI).
try:
    import streamlit as _st_real  # type: ignore
except Exception:
    _st_real = None

class _DummyStreamlit:
    """Минимальный stub для импорта модуля без Streamlit (нужен для self-checks)."""
    @staticmethod
    def cache_data(*_a, **_k):
        def _decor(fn):
            return fn
        return _decor

    @staticmethod
    def cache_resource(*_a, **_k):
        def _decor(fn):
            return fn
        return _decor

# `st` будет переопределён внутри render_compare_npz_web(st_mod).
st = _st_real if _st_real is not None else _DummyStreamlit()  # type: ignore

from pneumo_solver_ui.compare_ui import (
    BAR_PA,
    P_ATM_DEFAULT,
    apply_zero_baseline,
    common_time_grid,
    detect_time_col,
    extract_time_vector,
    is_zeroable_unit,
    load_npz_bundle,
    locked_ranges_by_unit,
    massflow_to_Nl_min_ANR,
    resample_linear,
    robust_minmax,
    _infer_unit_and_transform,
)

from pneumo_solver_ui.compare_trust import inspect_runs as trust_inspect_runs, render_streamlit_banner
from pneumo_solver_ui.compare_deltat_heatmap import build_deltat_cube, pick_frame_indices
from pneumo_solver_ui.compare_influence_time import build_influence_t_cube

from pneumo_solver_ui.diag.qa_suspicious_signals import (
    scan_run_tables as qa_scan_run_tables,
    issues_to_frame as qa_issues_to_frame,
    severity_matrix as qa_severity_matrix,
    summarize as qa_summarize,
)

from pneumo_solver_ui.diag.event_markers import (
    scan_run_tables as ev_scan_run_tables,
    events_to_frame as ev_events_to_frame,
    summarize as ev_summarize,
    pick_top_signals as ev_pick_top_signals,
)

from pneumo_solver_ui.visual_contract import collect_visual_cache_dependencies
from pneumo_solver_ui.geometry_acceptance_contract import (
    build_geometry_acceptance_rows,
    format_geometry_acceptance_summary_lines,
)

from pneumo_solver_ui.compare_influence import (
    flatten_meta_numeric as _flatten_meta_numeric_shared,
    corr_matrix as _corr_matrix,
    prefilter_features_by_variance,
    rank_features_by_max_abs_corr,
    top_cells,
)


# -------------------------
# Discrete signals helper
# -------------------------

def ev_detect_discrete_signals(df: pd.DataFrame, *, top_k: int = 8) -> List[str]:
    """Best-effort: detect event-like discrete signals inside a single table.

    Причина существования:
    - 3D "галька" (pebbles) слою нужен список дискретных сигналов.
    - В разных сборках этот хелпер появлялся/пропадал → ловили NameError.

    Реализация:
    - используем общую эвристику `diag.event_markers.scan_run_tables()`
      (она уже содержит name-hints и проверки «малодискретности»).
    - возвращаем топ-K сигналов по числу переключений.

    Никогда не должна ронять UI.
    """

    try:
        if df is None or getattr(df, "empty", True):
            return []
        if ev_scan_run_tables is None or ev_pick_top_signals is None:
            return []
        evs = ev_scan_run_tables({"tbl": df}, rising_only=True)
        return [str(x) for x in (ev_pick_top_signals(evs, k=int(top_k)) or [])]
    except Exception:
        return []


# -------------------------
# Streamlit compatibility helpers
# -------------------------

def _rerun() -> None:
    request_rerun(st)


def _render_geometry_acceptance_report(runs_full: List[Tuple[str, Dict]]) -> None:
    rows: List[Dict[str, object]] = []
    details: List[str] = []
    gate_rank = {"FAIL": 3, "WARN": 2, "PASS": 1, "MISSING": 0}
    worst_gate = "MISSING"
    worst_reason = ""
    for label, bundle in runs_full:
        acc = dict(bundle.get("geometry_acceptance") or {}) if isinstance(bundle, dict) else {}
        if not acc:
            continue
        gate = str(acc.get("release_gate") or "MISSING")
        if gate_rank.get(gate, 0) > gate_rank.get(worst_gate, 0):
            worst_gate = gate
            worst_reason = str(acc.get("release_gate_reason") or "")
        rows.append({
            "run": str(label),
            "gate": gate,
            "reason": str(acc.get("release_gate_reason") or ""),
            "worst_corner": str(acc.get("worst_corner") or ""),
            "worst_metric": str(acc.get("worst_metric") or ""),
            "worst_value, мм": (float(acc.get("worst_value_m", 0.0) or 0.0) * 1000.0) if acc.get("worst_value_m") is not None else None,
            "рама‑дорога min, м": acc.get("frame_road_min_m"),
            "рама‑дорога угол": str(acc.get("min_frame_road_corner") or ""),
            "колесо‑дорога min, м": acc.get("wheel_road_min_m"),
            "колесо‑дорога угол": str(acc.get("min_wheel_road_corner") or ""),
            "Σ err, мм": float(acc.get("max_invariant_err_m", 0.0) or 0.0) * 1000.0,
            "XY err, мм": float(acc.get("max_xy_err_m", 0.0) or 0.0) * 1000.0,
            "WF err, мм": float(acc.get("max_scalar_err_wheel_frame_m", 0.0) or 0.0) * 1000.0,
            "WR err, мм": float(acc.get("max_scalar_err_wheel_road_m", 0.0) or 0.0) * 1000.0,
            "FR err, мм": float(acc.get("max_scalar_err_frame_road_m", 0.0) or 0.0) * 1000.0,
            "missing_triplets": len(list(acc.get("missing_triplets") or [])),
        })
        details.extend(format_geometry_acceptance_summary_lines(acc, label=str(label)))
    if not rows:
        return
    if worst_gate == "FAIL":
        st.error(f"Геометрический acceptance gate=FAIL: {worst_reason or 'нарушен контракт рама / колесо / дорога'}. Проверьте таблицу ниже.")
    elif worst_gate == "WARN":
        st.warning(f"Геометрический acceptance gate=WARN: {worst_reason or 'есть предупреждения (missing triplets или XY-расхождения)'}." )
    elif worst_gate == "PASS":
        st.success("Геометрический acceptance gate=PASS: solver-point контракт рама / колесо / дорога согласован.")
    else:
        st.info("Геометрический acceptance gate=MISSING: данные solver-point triplet-ов отсутствуют.")
    with st.expander("Геометрический acceptance (рама / колесо / дорога)", expanded=False):
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        per_corner_rows: List[Dict[str, object]] = []
        for label, bundle in runs_full:
            acc = dict(bundle.get("geometry_acceptance") or {}) if isinstance(bundle, dict) else {}
            if not acc:
                continue
            for row in build_geometry_acceptance_rows(acc):
                row = dict(row)
                row["run"] = str(label)
                per_corner_rows.append(row)
        if per_corner_rows:
            st.caption("Per-corner breakdown")
            st.dataframe(pd.DataFrame(per_corner_rows), width="stretch", hide_index=True)
        if details:
            st.text("\n".join(details[:32]))


def _st_plotly(fig, *, key: str | None = None):
    # Render Plotly chart with best-effort container sizing across Streamlit versions.
    try:
        return st.plotly_chart(fig, width='stretch', key=key)  # type: ignore[call-arg]
    except TypeError:
        pass
    try:
        return st.plotly_chart(fig, use_container_width=True, key=key)
    except TypeError:
        pass
    return st.plotly_chart(fig, key=key)


def _st_plotly_select(fig, *, key: str, mode: str = 'rerun'):
    # Render Plotly chart and (if supported) return selection event.
    try:
        return st.plotly_chart(fig, width='stretch', on_select=mode, key=key)  # type: ignore[call-arg]
    except TypeError:
        try:
            return st.plotly_chart(fig, use_container_width=True, on_select=mode, key=key)  # type: ignore[call-arg]
        except TypeError:
            return _st_plotly(fig, key=key)


def _extract_first_xy_from_event(ev):
    # Extract (x,y) from Streamlit/Plotly selection event (best-effort).
    if ev is None:
        return None, None
    sel = None
    try:
        sel = getattr(ev, 'selection')
    except Exception:
        sel = None
    if sel is None and isinstance(ev, dict):
        sel = ev.get('selection') or ev
    if not sel:
        return None, None
    pts = None
    if isinstance(sel, dict):
        pts = sel.get('points')
    if pts is None and isinstance(sel, list):
        pts = sel
    if not pts:
        return None, None
    p0 = pts[0] if isinstance(pts, list) else None
    if not isinstance(p0, dict):
        return None, None
    return p0.get('x'), p0.get('y')


def _extract_selected_texts(ev) -> List[str]:
    """Extract list of 'text' fields from selection event (linked brushing)."""
    if ev is None:
        return []
    sel = None
    try:
        sel = getattr(ev, 'selection')
    except Exception:
        sel = None
    if sel is None and isinstance(ev, dict):
        sel = ev.get('selection') or ev
    if not sel:
        return []

    pts = None
    if isinstance(sel, dict):
        pts = sel.get('points')
    if pts is None and isinstance(sel, list):
        pts = sel
    if not pts:
        return []

    out: List[str] = []
    seen = set()
    for p in (pts if isinstance(pts, list) else []):
        if not isinstance(p, dict):
            continue
        txt = p.get('text')
        if txt is None:
            continue
        t = str(txt)
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def _trim_label(s: str, n: int = 36) -> str:
    s = str(s)
    return s if len(s) <= n else (s[: max(0, n - 1)] + '…')


def _wrap_label(s: str, width: int = 28, max_lines: int = 3) -> str:
    """Перенос длинных подписей, чтобы не налезали на графики.

    Plotly поддерживает <br> в title_text, поэтому возвращаем HTML-строку.
    """
    import textwrap
    s = str(s)
    if width <= 8 or len(s) <= width:
        return s
    # textwrap умеет переносить даже без пробелов, но сначала слегка «нормализуем» разделители
    s2 = s.replace('_', ' ').replace('/', ' / ').replace('|', ' | ').replace('\t', ' ')
    lines = textwrap.wrap(s2, width=width, break_long_words=True, break_on_hyphens=True)
    if not lines:
        return s
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        # добавим эллипсис, если ещё есть хвост
        if not lines[-1].endswith('…'):
            lines[-1] = (lines[-1][: max(0, width - 1)] + '…') if len(lines[-1]) >= width else (lines[-1] + '…')
    return '<br>'.join(lines)


def _wrap_tick_text(s: str, maxlen: int = 22) -> str:
    """Короткая подпись для осей/heatmap, чтобы не было наложений.

    - Делает компактный вариант строки.
    - Допускает <br> (Plotly), если удалось аккуратно разорвать по пробелу.
    """
    s = str(s)
    if maxlen <= 6:
        return _trim_label(s, n=maxlen)

    s2 = s.replace('_', ' ').replace('\t', ' ').strip()
    if len(s2) <= maxlen:
        return s2


def _sample_nearest(x: np.ndarray, y: np.ndarray, t: float) -> float:
    """Sample y(x) at time t using nearest neighbor (stable for discrete signals)."""
    if x.size == 0:
        return float('nan')
    if not np.isfinite(t):
        return float('nan')
    # if not monotonic, fallback to sorted nearest
    try:
        if np.any(np.diff(x) <= 0):
            xs = np.array(x, copy=True)
            ys = np.array(y, copy=True)
            idx = np.argsort(xs)
            xs = xs[idx]
            ys = ys[idx]
            j = int(np.searchsorted(xs, t))
            j = max(1, min(j, xs.size - 1))
            j0, j1 = j - 1, j
            return float(ys[j0] if abs(xs[j0] - t) <= abs(xs[j1] - t) else ys[j1])
    except Exception:
        pass

    j = int(np.searchsorted(x, t))
    j = max(1, min(j, x.size - 1))
    j0, j1 = j - 1, j
    return float(y[j0] if abs(x[j0] - t) <= abs(x[j1] - t) else y[j1])


def _knn_density(points01: np.ndarray, k: int = 5) -> np.ndarray:
    """Cheap kNN density proxy for interactive thinning.

    points01: Nx3 in [0..1] (normalized). Returns higher values for denser regions.
    """
    pts = np.asarray(points01, dtype=float)
    n = pts.shape[0]
    if n <= 2:
        return np.ones(n, dtype=float)
    # pairwise squared distances
    d2 = np.sum((pts[:, None, :] - pts[None, :, :]) ** 2, axis=2)
    # k-th neighbor distance (skip self=0 at rank 0)
    kk = max(1, min(int(k) + 1, n - 1))
    dk2 = np.partition(d2, kk, axis=1)[:, kk]
    dk = np.sqrt(np.maximum(dk2, 1e-12))
    return 1.0 / (dk + 1e-9)
    # Попытка сделать 2 строки, чтобы подпись стала уже
    half = max(6, int(maxlen // 2))
    cut = s2.rfind(' ', 0, half)
    if cut >= 4:
        a = s2[:cut].strip()
        b = s2[cut + 1 :].strip()
        b = _trim_label(b, n=maxlen)
        return f"{a}<br>{b}"

    return _trim_label(s2, n=maxlen)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_npz_dirs() -> List[Path]:
    root = _repo_root()
    ui = root / "pneumo_solver_ui"
    cands = [
        ui / "workspace" / "exports",
        ui / "workspace" / "osc",
        ui / "workspace" / "calibration_runs",
        root / "workspace" / "exports",
        root / "workspace" / "osc",
        root / "workspace",
    ]
    out: List[Path] = []
    for p in cands:
        if p.exists() and p.is_dir():
            out.append(p)
    seen = set()
    uniq: List[Path] = []
    for p in out:
        s = str(p.resolve())
        if s not in seen:
            uniq.append(p)
            seen.add(s)
    return uniq


@st.cache_data(show_spinner=False)
def _load_npz(path_str: str, cache_deps: Optional[Dict[str, object]] = None) -> Dict:
    _ = cache_deps
    return load_npz_bundle(path_str)


def _list_npz_files(base: Path, pattern: str = "*.npz", limit: int = 4000) -> List[Path]:
    if not base.exists():
        return []
    files = sorted(base.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def _flatten_meta_numeric(meta: Dict) -> Dict[str, float]:
    """Back-compat wrapper.

    Реальная реализация вынесена в `compare_influence.flatten_meta_numeric`,
    чтобы Web и Qt считали одинаково.
    """
    try:
        return _flatten_meta_numeric_shared(meta, max_items=500)
    except Exception:
        return {}


def _get_df_tables(bundle: Dict) -> Dict[str, pd.DataFrame]:
    t = bundle.get("tables") if isinstance(bundle, dict) else None
    if isinstance(t, dict):
        return t
    return {}


def _get_xy(
    tables: Dict[str, pd.DataFrame],
    table: str,
    sig: str,
    *,
    dist_unit: str,
    angle_unit: str,
    p_atm: float,
    zero_baseline: bool,
    baseline_mode: str,
    baseline_window_s: float,
    baseline_first_n: int,
    flow_unit: str,
) -> Tuple[np.ndarray, np.ndarray, str]:
    df = tables.get(table)
    if df is None or df.empty:
        return np.asarray([], dtype=float), np.asarray([], dtype=float), ""

    tcol = detect_time_col(df)
    x = extract_time_vector(df, tcol)
    if sig not in df.columns:
        return x, np.asarray([], dtype=float), ""

    y0 = np.asarray(df[sig].values, dtype=float)
    unit, tr = _infer_unit_and_transform(sig, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
    y = np.asarray(tr(y0), dtype=float)

    # flows: if want Nl/min (ANR) and data looks like kg/s -> convert
    if flow_unit.lower().startswith("nl") and unit == "":
        low = sig.lower()
        if "kg_s" in low or "kg/s" in low or low.endswith("_kg_s") or low.endswith("_kg/s") or "массов" in low:
            y = massflow_to_Nl_min_ANR(y)
            unit = "Nl/min (ANR)"

    if zero_baseline and is_zeroable_unit(unit):
        y = apply_zero_baseline(
            x,
            y,
            unit=unit,
            enable=True,
            mode=baseline_mode,
            window_s=float(baseline_window_s or 0.0),
            first_n=int(baseline_first_n or 0),
        )

    return x, y, unit


def _build_compare_figure(
    runs: List[Tuple[str, Dict[str, pd.DataFrame]]],
    table: str,
    sigs: List[str],
    *,
    mode_delta: bool,
    ref_label: str,
    dist_unit: str,
    angle_unit: str,
    p_atm: float,
    zero_baseline: bool,
    baseline_mode: str,
    baseline_window_s: float,
    baseline_first_n: int,
    lock_y_signal: bool,
    lock_y_unit: bool,
    robust_y: bool,
    sym_y: bool,
    flow_unit: str,
    time_window: Optional[Tuple[float, float]] = None,
    t_play: Optional[float] = None,
    event_lines: Optional[List[float]] = None,
) -> Tuple[go.Figure, Dict[str, Tuple[str, float, float]]]:
    ref_tables = dict(runs)[ref_label]

    fig = make_subplots(rows=len(sigs), cols=1, shared_xaxes=True, vertical_spacing=0.02)
    fig.update_layout(
        margin=dict(l=40, r=10, t=30, b=30),
        hovermode="x unified",
        clickmode="event+select",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=max(540, 220 * len(sigs)),
    )

    # playhead vertical line
    if t_play is not None and np.isfinite(t_play):
        try:
            for rr in range(1, len(sigs)+1):
                fig.add_vline(x=float(t_play), line_width=1, line_dash="dot", line_color="rgba(120,120,120,0.6)", row=rr, col=1)
        except Exception:
            pass

    # discrete events (vertical markers)
    if event_lines:
        try:
            # keep order and unique within tolerance
            evs = [float(x) for x in event_lines if isinstance(x, (int, float)) and np.isfinite(float(x))]
            evs = sorted(evs)
            evs_u: List[float] = []
            for x in evs:
                if not evs_u or abs(x - evs_u[-1]) > 1e-9:
                    evs_u.append(x)
            for t_ev in evs_u:
                for rr in range(1, len(sigs) + 1):
                    fig.add_vline(
                        x=float(t_ev),
                        line_width=1,
                        line_dash="dash",
                        line_color="rgba(255,140,0,0.30)",
                        row=rr,
                        col=1,
                    )
        except Exception:
            pass

    sig_ranges: Dict[str, Tuple[str, float, float]] = {}

    # Precompute per-unit ranges if needed
    if lock_y_unit:
        series_by_sig: Dict[str, Tuple[str, np.ndarray]] = {}
        for sig in sigs:
            ys_all: List[np.ndarray] = []
            unit0 = ""
            for lbl, tables in runs:
                x, y, unit = _get_xy(
                    tables, table, sig,
                    dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
                    zero_baseline=zero_baseline, baseline_mode=baseline_mode,
                    baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
                    flow_unit=flow_unit,
                )
                if time_window and x.size:
                    m = (x >= time_window[0]) & (x <= time_window[1])
                    y = y[m] if m.any() else y
                if y.size:
                    ys_all.append(y)
                unit0 = unit0 or unit
            if ys_all:
                cat = np.concatenate([a[np.isfinite(a)] for a in ys_all if a.size], axis=0) if ys_all else np.asarray([])
                series_by_sig[sig] = (unit0, cat)
        unit_ranges = locked_ranges_by_unit(series_by_sig, robust=robust_y, symmetric=(sym_y and mode_delta))
    else:
        unit_ranges = {}

    # Per-signal draw
    for r_i, sig in enumerate(sigs, start=1):
        x_ref, y_ref, unit = _get_xy(
            ref_tables, table, sig,
            dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
            zero_baseline=zero_baseline, baseline_mode=baseline_mode,
            baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
            flow_unit=flow_unit,
        )

        if x_ref.size == 0 or y_ref.size == 0:
            continue

        # Apply time window
        if time_window:
            mask = (x_ref >= time_window[0]) & (x_ref <= time_window[1])
            if mask.any():
                x_ref_w = x_ref[mask]
                y_ref_w = y_ref[mask]
            else:
                x_ref_w, y_ref_w = x_ref, y_ref
        else:
            x_ref_w, y_ref_w = x_ref, y_ref

        # reference trace
        if mode_delta:
            fig.add_trace(
                go.Scatter(x=x_ref_w, y=np.zeros_like(y_ref_w), mode="lines", name=f"0 ({ref_label})", legendgroup=ref_label, line=dict(width=1)),
                row=r_i, col=1
            )
        else:
            fig.add_trace(
                go.Scatter(x=x_ref_w, y=y_ref_w, mode="lines", name=ref_label, legendgroup=ref_label, line=dict(width=2)),
                row=r_i, col=1
            )

        # other runs
        for lbl, tables in runs:
            if lbl == ref_label:
                continue
            x, y, unit2 = _get_xy(
                tables, table, sig,
                dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
                zero_baseline=zero_baseline, baseline_mode=baseline_mode,
                baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
                flow_unit=flow_unit,
            )
            if x.size == 0 or y.size == 0:
                continue
            if time_window:
                m = (x_ref >= time_window[0]) & (x_ref <= time_window[1])
                x_ref_use = x_ref[m] if m.any() else x_ref
                y_ref_use = y_ref[m] if m.any() else y_ref
            else:
                x_ref_use = x_ref
                y_ref_use = y_ref

            y_i = resample_linear(x, y, x_ref_use)
            if mode_delta:
                y_plot = y_i - y_ref_use
                name = f"Δ {lbl}-{ref_label}"
                line = dict(width=1, dash="dash")
            else:
                y_plot = y_i
                name = lbl
                line = dict(width=1)
            fig.add_trace(
                go.Scatter(x=x_ref_use, y=y_plot, mode="lines", name=name, legendgroup=lbl, line=line),
                row=r_i, col=1
            )

        # play with Y ranges
        y_for_range: List[np.ndarray] = []
        if mode_delta:
            # include zeros and deltas
            y_for_range.append(np.zeros_like(y_ref_w))
            for lbl, tables in runs:
                if lbl == ref_label:
                    continue
                x, y, _u = _get_xy(
                    tables, table, sig,
                    dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
                    zero_baseline=zero_baseline, baseline_mode=baseline_mode,
                    baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
                    flow_unit=flow_unit,
                )
                if x.size and y.size:
                    y_i = resample_linear(x, y, x_ref_w)
                    y_for_range.append(y_i - y_ref_w)
        else:
            y_for_range.append(y_ref_w)
            for lbl, tables in runs:
                if lbl == ref_label:
                    continue
                x, y, _u = _get_xy(
                    tables, table, sig,
                    dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
                    zero_baseline=zero_baseline, baseline_mode=baseline_mode,
                    baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
                    flow_unit=flow_unit,
                )
                if x.size and y.size:
                    y_for_range.append(resample_linear(x, y, x_ref_w))

        if lock_y_unit and unit in unit_ranges:
            yr = unit_ranges[unit]
            lo, hi = yr.ymin, yr.ymax
        elif lock_y_signal:
            cat = np.concatenate([a[np.isfinite(a)] for a in y_for_range if a.size], axis=0) if y_for_range else np.asarray([])
            lo, hi = robust_minmax(cat) if robust_y else (float(np.nanmin(cat)), float(np.nanmax(cat)))
            if sym_y and mode_delta:
                m = max(abs(lo), abs(hi))
                lo, hi = -m, m
        else:
            lo, hi = None, None

        if lo is not None and hi is not None:
            fig.update_yaxes(range=[lo, hi], row=r_i, col=1)

        title_sig = _wrap_label(str(sig), width=30, max_lines=3)
        title_text = f"{title_sig}<br>[{unit}]" if unit else title_sig
        fig.update_yaxes(title_text=title_text, row=r_i, col=1)

        sig_ranges[sig] = (unit, float(lo) if lo is not None else float("nan"), float(hi) if hi is not None else float("nan"))

    fig.update_xaxes(title_text="t, s", row=len(sigs), col=1)
    return fig, sig_ranges


def _delta_heatmap(
    runs: List[Tuple[str, Dict[str, pd.DataFrame]]],
    table: str,
    sigs: List[str],
    *,
    ref_label: str,
    dist_unit: str,
    angle_unit: str,
    p_atm: float,
    zero_baseline: bool,
    baseline_mode: str,
    baseline_window_s: float,
    baseline_first_n: int,
    flow_unit: str,
) -> Tuple[pd.DataFrame, go.Figure]:
    ref_tables = dict(runs)[ref_label]
    # reference time per signal: take from reference run per signal
    mat = []
    col_names = []
    for lbl, tables in runs:
        if lbl == ref_label:
            continue
        col_names.append(lbl)

    for sig in sigs:
        x_ref, y_ref, unit = _get_xy(
            ref_tables, table, sig,
            dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
            zero_baseline=zero_baseline, baseline_mode=baseline_mode,
            baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
            flow_unit=flow_unit,
        )
        row = []
        for lbl, tables in runs:
            if lbl == ref_label:
                continue
            x, y, unit2 = _get_xy(
                tables, table, sig,
                dist_unit=dist_unit, angle_unit=angle_unit, p_atm=p_atm,
                zero_baseline=zero_baseline, baseline_mode=baseline_mode,
                baseline_window_s=baseline_window_s, baseline_first_n=baseline_first_n,
                flow_unit=flow_unit,
            )
            if x_ref.size == 0 or y_ref.size == 0 or x.size == 0 or y.size == 0:
                row.append(np.nan)
                continue
            y_i = resample_linear(x, y, x_ref)
            d = y_i - y_ref
            row.append(float(np.nanmax(np.abs(d))) if np.isfinite(d).any() else np.nan)
        mat.append(row)

    heat_df = pd.DataFrame(mat, index=sigs, columns=col_names)

    fig = go.Figure(data=go.Heatmap(z=heat_df.values, x=heat_df.columns, y=heat_df.index, colorscale="Viridis"))
    fig.update_layout(
        height=max(420, 18 * len(sigs) + 200),
        margin=dict(l=60, r=20, t=40, b=40),
        title="max |Δ| vs reference",
    )
    try:
        fig.update_xaxes(automargin=True)
        fig.update_yaxes(automargin=True)
    except Exception:
        pass
    return heat_df, fig


def _build_influence_cube_anim_fig(
    *,
    t: np.ndarray,
    cube: np.ndarray,
    feat_names: List[str],
    sigs: List[str],
    title_prefix: str = "Influence(t)",
) -> go.Figure:
    """Create Plotly animated heatmap for correlation cube.

    Parameters
    ----------
    t
        1D array of frame times (seconds).
    cube
        3D array: (T, n_feat, n_sig) with correlation values in [-1..1].
    feat_names, sigs
        Full labels (used in hover). Tick labels will be trimmed/wrapped to avoid overlap.
    """

    t = np.asarray(t, dtype=float)
    cube = np.asarray(cube, dtype=float)
    feat_names = list(map(str, feat_names))
    sigs = list(map(str, sigs))

    if t.size == 0 or cube.size == 0:
        return go.Figure()

    T, nf, ns = cube.shape

    # compact tick labels (full names go to hover)
    y_ticks = [_wrap_label(_trim_label(s, 40), width=28, max_lines=2) for s in feat_names]
    x_ticks = [_wrap_label(_trim_label(s, 40), width=26, max_lines=2) for s in sigs]

    # customdata: (nf, ns, 2) => [full_feat, full_sig]
    cd = np.empty((nf, ns, 2), dtype=object)
    for i in range(nf):
        for j in range(ns):
            cd[i, j, 0] = feat_names[i]
            cd[i, j, 1] = sigs[j]

    def _heat(z2d: np.ndarray, *, show_cbar: bool = False) -> go.Heatmap:
        return go.Heatmap(
            z=z2d,
            x=x_ticks,
            y=y_ticks,
            zmin=-1.0,
            zmax=+1.0,
            zmid=0.0,
            colorscale="RdBu",
            colorbar=dict(title="corr", len=0.85) if show_cbar else None,
            customdata=cd,
            hovertemplate=(
                "meta=%{customdata[0]}<br>"
                "sig=%{customdata[1]}<br>"
                "corr=%{z:.3f}<extra></extra>"
            ),
        )

    fig = go.Figure(data=[_heat(cube[0], show_cbar=True)])

    frames = []
    steps = []
    for k in range(int(T)):
        frames.append(go.Frame(data=[_heat(cube[k], show_cbar=False)], name=str(k)))
        steps.append(
            dict(
                method="animate",
                args=[[str(k)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                label=f"{t[k]:.2f}",
            )
        )

    fig.frames = frames

    fig.update_layout(
        title=f"{title_prefix} | frames={T} | corr in [-1..1]",
        margin=dict(l=220, r=20, t=60, b=90),
        xaxis=dict(tickangle=-35, automargin=True),
        yaxis=dict(automargin=True),
        height=560,
        sliders=[
            dict(
                active=0,
                currentvalue={"prefix": "t, s: ", "visible": True},
                pad={"t": 45, "b": 10},
                steps=steps,
            )
        ],
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                x=0.0,
                y=1.15,
                showactive=False,
                buttons=[
                    dict(
                        label="▶ Play",
                        method="animate",
                        args=[None, {"frame": {"duration": 60, "redraw": True}, "fromcurrent": True}],
                    ),
                    dict(
                        label="⏸ Pause",
                        method="animate",
                        args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                    ),
                ],
            )
        ],
    )

    return fig


def _static_stroke_report(tables: Dict[str, pd.DataFrame], *, dist_unit: str, angle_unit: str, p_atm: float) -> pd.DataFrame:
    df = tables.get("main") or tables.get("full") or None
    if df is None or df.empty:
        return pd.DataFrame()
    cols = list(df.columns)
    # heuristic: stroke columns contain 'шток' or 'stroke'
    stroke_cols = [c for c in cols if ("шток" in str(c).lower() or "stroke" in str(c).lower())]
    if not stroke_cols:
        return pd.DataFrame()

    tcol = detect_time_col(df)
    x = extract_time_vector(df, tcol)
    i0 = 0
    meta_L = None
    # best-effort read from meta inside bundle? not accessible here; handled in caller
    rows = []
    for c in stroke_cols[:24]:
        y0 = np.asarray(df[c].values, dtype=float)
        unit, tr = _infer_unit_and_transform(c, P_ATM=p_atm, dist_unit=dist_unit, angle_unit=angle_unit)
        y = np.asarray(tr(y0), dtype=float)
        v0 = float(y[i0]) if y.size else np.nan
        rows.append({"signal": c, "unit": unit, "t0": v0})
    return pd.DataFrame(rows)



def render_compare_npz_web(st_mod: Any) -> None:
    """Render Compare NPZ (Web) UI.

    st_mod should be the imported streamlit module passed from the page.
    This indirection keeps the module importable in non-Streamlit contexts (self-checks).
    """
    global st
    st = st_mod
    if st is None:
        raise RuntimeError("streamlit module was not provided")
    st.title("Compare NPZ (web) — сравнение прогонов")

    if not _HAS_PLOTLY:
        st.error(
            "Plotly не установлен в текущем окружении, поэтому Compare NPZ (web) не может "
            "построить интерактивные диаграммы. Launcher теперь устанавливает plotly из root requirements; "
            f"после обновления окружения страница должна открываться штатно. Ошибка импорта: {_PLOTLY_IMPORT_ERR!r}"
        )
        return
    st.caption(
        "Overlay / Δ, нулевая статика (перемещения/углы/дорога), одинаковые шкалы, "
        "heatmap max|Δ|, Δ(t) heatmap‑плеер, N→N influence."
    )

    # ------------------------------------------------------------
    # 0) Pending UI actions (from clicks) — apply BEFORE widgets
    # ------------------------------------------------------------
    # 0.1) Heatmap focus (sig/run) -> add signal into selected list
    if bool(st.session_state.get('compare_focus_pending', False)):
        focus_sig = st.session_state.get('compare_focus_sig')
        sig_key = 'compare_sigs'
        if focus_sig and sig_key in st.session_state:
            try:
                cur = list(st.session_state.get(sig_key) or [])
                if focus_sig not in cur:
                    cur = [focus_sig] + cur
                    st.session_state[sig_key] = cur[:12]
            except Exception:
                pass
        st.session_state['compare_focus_pending'] = False

    # 0.2) Linked brushing: pending update of active runs
    # (e.g. user selected points on scatter → filter runs)
    if bool(st.session_state.get('compare_active_runs_pending', False)):
        pending = st.session_state.get('compare_active_runs_pending_value')
        if isinstance(pending, (list, tuple)) and pending:
            st.session_state['compare_active_runs'] = list(pending)
        st.session_state['compare_active_runs_pending'] = False

    # ------------------------------------------------------------
    # 1) Sidebar — sources + modes (ALL keys have compare_ prefix)
    # ------------------------------------------------------------
    dirs = _default_npz_dirs()
    if not dirs:
        st.warning("Не найдены папки workspace с .npz. Сначала выполните расчёт и экспорт.")
        return

    with st.sidebar:
        st.header("Источники NPZ")
        base_dir = st.selectbox(
            "Папка",
            options=[str(p) for p in dirs],
            index=0,
            key='compare_npz_base_dir',
            help="Где искать результаты *.npz (обычно workspace/osc или workspace/exports).",
        )
        pat = st.text_input(
            "Шаблон файлов",
            value='*.npz',
            key='compare_npz_pattern',
            help="Напр.: *_osc.npz (осциллограммы) или *.npz (всё).",
        )

        files = _list_npz_files(Path(base_dir), pat)
        if not files:
            st.warning("В выбранной папке нет NPZ по заданному шаблону.")
            return

        options = [str(p) for p in files]
        pick_key = 'compare_npz_picked'
        prev = st.session_state.get(pick_key)
        if isinstance(prev, (list, tuple)):
            default_picked = [p for p in prev if p in options]
        else:
            default_picked = []
        if not default_picked:
            default_picked = options[: min(3, len(options))]
        st.session_state[pick_key] = default_picked

        picked = st.multiselect(
            "Выберите NPZ (1+)",
            options=options,
            default=default_picked,
            key=pick_key,
            help="Выберите несколько прогонов для сравнения.",
        )
        if len(picked) < 1:
            st.stop()

        st.header("Режим сравнения")
        mode = st.radio(
            "Сравнение",
            options=["Overlay (абсолютные)", "Δ to reference (разность)"],
            index=0,
            key='compare_mode',
            help="Overlay — абсолютные кривые. Δ — разность относительно reference.",
        )
        mode_delta = mode.startswith('Δ')

        st.header("Отображение / шкалы")
        dist_unit = st.selectbox("Ед. расстояний", options=["mm", "m"], index=0, key='compare_dist_unit')
        angle_unit = st.selectbox("Ед. углов", options=["deg", "rad"], index=0, key='compare_angle_unit')
        flow_unit = st.selectbox(
            "Ед. расходов",
            options=["raw", "Nl/min (ANR)"],
            index=0,
            key='compare_flow_unit',
        )

        zero_baseline = st.checkbox(
            "Нулевая база (позиции/углы/дорога)",
            value=True,
            key='compare_zero_baseline',
            help="Приводит перемещения/углы/дорогу к нулю в статике (t0 или окно).",
        )
        baseline_mode = st.selectbox(
            "Baseline mode",
            options=["t0", "median_window", "mean_window", "median_first_n", "mean_first_n"],
            index=0,
            key='compare_baseline_mode',
            help="Как вычислять статическую базу для обнуления.",
        )
        baseline_window_s = st.number_input(
            "Окно baseline, s",
            min_value=0.0,
            max_value=5.0,
            value=float(st.session_state.get('compare_baseline_window_s', 0.0) or 0.0),
            step=0.05,
            key='compare_baseline_window_s',
        )
        baseline_first_n = st.number_input(
            "Baseline first N",
            min_value=0,
            max_value=5000,
            value=int(st.session_state.get('compare_baseline_first_n', 0) or 0),
            step=50,
            key='compare_baseline_first_n',
        )

        lock_y_signal = st.checkbox("Lock Y (по сигналу)", value=True, key='compare_lock_y_signal')
        lock_y_unit = st.checkbox("Lock Y (по единице)", value=True, key='compare_lock_y_unit')
        robust_y = st.checkbox("Robust Y (1..99%)", value=True, key='compare_robust_y')
        sym_y = st.checkbox("Symmetric Y around 0 (Δ)", value=True, key='compare_sym_y')

        st.header("Давление")
        p_atm = st.number_input(
            "P_ATM, Pa",
            min_value=0.0,
            value=float(st.session_state.get('compare_p_atm', P_ATM_DEFAULT) or P_ATM_DEFAULT),
            step=1000.0,
            key='compare_p_atm',
        )

        st.header("QA / Качество")
        st.checkbox(
            "Авто‑проверка качества (подозрительные сигналы)",
            value=True,
            key='compare_qa_enable',
            help=(
                "Лёгкая QA‑проверка результатов для визуализаций: NaN/Inf, пики/скачки, "
                "выбросы, дрейф.\n"
                "Это не физическая валидация модели — только защита от 'красивых, но неверных' графиков."
            ),
        )
        _qa_labels = {
            "low": "Низкая (меньше ложных)",
            "normal": "Нормальная",
            "high": "Высокая (больше находок)",
        }
        st.selectbox(
            "Чувствительность",
            options=["low", "normal", "high"],
            index=1,
            format_func=lambda x: _qa_labels.get(str(x), str(x)),
            key='compare_qa_sensitivity',
            help="Чем выше — тем больше вероятных проблем найдём, но вырастет риск ложных срабатываний.",
        )
        st.checkbox(
            "Сканировать все сигналы (может быть дольше)",
            value=False,
            key='compare_qa_all_sigs',
            help="По умолчанию сканируются выбранные Signals (быстро).",
        )

        st.header("События")
        st.checkbox(
            'Показывать дискретные события ("галька" на графиках)',
            value=bool(st.session_state.get('compare_events_enable', False)),
            key='compare_events_enable',
            help=(
                "Автоматически ищет дискретные сигналы (0/1/2...) и показывает моменты переключения "
                "как вертикальные маркеры + timeline (raster).\n"
                "Полезно для порогов/срабатываний: клапан открылся, отрыв колеса, пробой и т.п."
            ),
        )

    # ------------------------------------------------------------
    # 2) Load NPZ bundles
    # ------------------------------------------------------------
    bundles: List[Tuple[str, Dict[str, pd.DataFrame]]] = []
    runs_full: List[Tuple[str, Dict]] = []
    metas: Dict[str, Dict] = {}

    for p in picked:
        cache_deps = collect_visual_cache_dependencies(p, context="Compare NPZ Web cache")
        b = _load_npz(p, cache_deps)
        tables = _get_df_tables(b)
        if not tables:
            continue
        label = Path(p).stem
        meta = b.get('meta') if isinstance(b, dict) else {}
        if isinstance(meta, dict):
            tn = meta.get('test_name') or meta.get('имя_теста') or meta.get('name') or None
            if tn:
                label = f"{tn} · {label}" if str(tn) not in label else label
        bundles.append((label, tables))
        metas[label] = meta if isinstance(meta, dict) else {}
        runs_full.append((label, b))

    if not bundles:
        st.error("Не удалось загрузить выбранные NPZ (нет таблиц).")
        return

    # ------------------------------------------------------------
    # 2.1) Active runs filter (within already picked NPZ)
    # ------------------------------------------------------------
    all_run_labels = [lab for (lab, _td) in bundles]
    # Init default (persisted) selection
    if 'compare_active_runs' not in st.session_state:
        st.session_state['compare_active_runs'] = list(all_run_labels)

    with st.sidebar:
        st.header("Фильтр прогонов")
        st.checkbox(
            "Связанные графики: выделение → фильтр runs",
            value=True,
            key='compare_linked_brushing',
            help=(
                "Если включено, выделение точек на некоторых графиках (lasso/box) "
                "автоматически обновит список 'Активные runs'."
            ),
        )
        active_runs = st.multiselect(
            "Активные runs (внутри выбранных NPZ)",
            options=all_run_labels,
            default=list(st.session_state.get('compare_active_runs') or list(all_run_labels)),
            key='compare_active_runs',
            help=(
                "Здесь можно быстро ограничить анализ подмножеством прогонов.\n"
                "Также этот список может обновляться автоматически (linked brushing) из некоторых графиков."
            ),
        )
        if not active_runs:
            st.warning("Не выбрано ни одного run — временно использую все.")
            active_runs = list(all_run_labels)
            st.session_state['compare_active_runs'] = list(active_runs)

    active_set = set(active_runs)
    bundles = [(lab, tdict) for (lab, tdict) in bundles if lab in active_set]
    runs_full = [(lab, b) for (lab, b) in runs_full if lab in active_set]
    metas = {lab: m for (lab, m) in metas.items() if lab in active_set}

    tables_set = None
    for _lab, tdict in bundles:
        keys = set(tdict.keys())
        tables_set = keys if tables_set is None else (tables_set & keys)
    tables_common = sorted(list(tables_set or []))
    if not tables_common:
        st.error("В выбранных NPZ нет общих таблиц (main/p/q/open/...).")
        return

    # ------------------------------------------------------------
    # 3) Sidebar — table + reference (guard against stale state)
    # ------------------------------------------------------------
    with st.sidebar:
        table_key = 'compare_table'
        old_table = st.session_state.get(table_key)
        idx_table = tables_common.index(old_table) if old_table in tables_common else 0
        table = st.selectbox("Таблица", options=tables_common, index=idx_table, key=table_key)

        ref_key = 'compare_ref_label'
        ref_opts = [lab for lab, _ in bundles]
        old_ref = st.session_state.get(ref_key)
        idx_ref = ref_opts.index(old_ref) if old_ref in ref_opts else 0
        ref_label = st.selectbox("Reference", options=ref_opts, index=idx_ref, key=ref_key)

    ref_tables = dict(bundles)[ref_label]
    df_ref = ref_tables.get(table)
    if df_ref is None or df_ref.empty:
        st.error("Reference таблица пустая")
        return

    tcol = detect_time_col(df_ref) or df_ref.columns[0]
    cols = [c for c in df_ref.columns if str(c) != str(tcol)]

    # ------------------------------------------------------------
    # 4) Signal selection
    # ------------------------------------------------------------
    c1, c2 = st.columns([2, 1])
    with c2:
        filt = st.text_input("Фильтр сигналов", value=str(st.session_state.get('compare_sig_filter', '')), key='compare_sig_filter')

    fcols = [c for c in cols if (filt.lower() in str(c).lower())] if filt else cols

    sig_key = 'compare_sigs'
    prev_sigs = st.session_state.get(sig_key)
    if isinstance(prev_sigs, (list, tuple)):
        default_sigs = [s for s in prev_sigs if s in fcols]
    else:
        default_sigs = []
    if not default_sigs:
        default_sigs = fcols[: min(6, len(fcols))]

    focus_sig = st.session_state.get('compare_focus_sig')
    if focus_sig and focus_sig in fcols and focus_sig not in default_sigs:
        default_sigs = [focus_sig] + default_sigs

    default_sigs = default_sigs[:12]
    st.session_state[sig_key] = default_sigs

    with c1:
        sigs = st.multiselect("Сигналы (2–12 для читаемости)", options=fcols, default=default_sigs, key=sig_key)
    if not sigs:
        st.stop()

    # ------------------------------------------------------------
    # 5) Trust diagnostics
    # ------------------------------------------------------------
    try:
        issues = trust_inspect_runs(runs_full, table=table, signals=sigs)
        render_streamlit_banner(st, issues)
    except Exception:
        pass

    try:
        _render_geometry_acceptance_report(runs_full)
    except Exception:
        pass

    # ------------------------------------------------------------
    # 6) Time window + playhead
    # ------------------------------------------------------------
    x_ref_full = extract_time_vector(df_ref, tcol)
    time_window = None
    if x_ref_full.size:
        t0, t1 = float(x_ref_full[0]), float(x_ref_full[-1])

        tw_key = 'compare_time_window'
        tw_prev = st.session_state.get(tw_key)
        if isinstance(tw_prev, (list, tuple)) and len(tw_prev) == 2:
            a, b = float(tw_prev[0]), float(tw_prev[1])
        else:
            a, b = t0, t1
        a = max(t0, min(a, t1))
        b = max(t0, min(b, t1))
        if b < a:
            a, b = t0, t1
        st.session_state[tw_key] = (a, b)

        time_window = st.slider("Окно времени (s)", min_value=t0, max_value=t1, value=(a, b), key=tw_key)

        max_idx = int(max(0, len(x_ref_full) - 1))
        idx_key = 'compare_playhead_idx'
        idx_prev = int(st.session_state.get(idx_key, 0) or 0)
        idx_prev = max(0, min(idx_prev, max_idx))
        st.session_state[idx_key] = idx_prev

        idx_play = st.slider("Playhead (индекс на reference)", min_value=0, max_value=max_idx, value=idx_prev, step=1, key=idx_key)
        t_play = float(x_ref_full[int(idx_play)]) if max_idx >= 0 else float(t0)
        st.caption(f"Playhead: t={t_play:.4f} s")

        # one-shot move playhead if click time stored
        t_click = st.session_state.get('compare_click_t')
        if isinstance(t_click, (int, float)) and np.isfinite(t_click):
            try:
                idx_new = int(np.argmin(np.abs(x_ref_full - float(t_click))))
                idx_new = max(0, min(idx_new, max_idx))
                if idx_new != int(idx_play):
                    st.session_state[idx_key] = idx_new
                    st.session_state['compare_click_t'] = None
                    _rerun()
            except Exception:
                pass
    else:
        idx_play = 0
        t_play = 0.0

    # ------------------------------------------------------------
    # 6.5) QA: suspicious signals (for visual trust)
    # ------------------------------------------------------------
    qa_enable = bool(st.session_state.get('compare_qa_enable', True))
    qa_df = None
    qa_first_t = {}
    if qa_enable:
        try:
            scan_all = bool(st.session_state.get('compare_qa_all_sigs', False))
            qa_sens = str(st.session_state.get('compare_qa_sensitivity', 'normal') or 'normal')
            scan_sigs = list(fcols if scan_all else sigs)
            scan_sigs = scan_sigs[: min(60, len(scan_sigs))]

            # Cache between reruns (playhead/zoom changes shouldn't rescan)
            cache_payload = {
                "runs": [lab for (lab, _t) in bundles],
                "table": str(table),
                "signals": list(scan_sigs),
                "sens": qa_sens,
                "tw": [float(time_window[0]), float(time_window[1])] if isinstance(time_window, (list, tuple)) and len(time_window) == 2 else None,
            }
            cache_key = hashlib.sha1(json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
            if st.session_state.get('compare_qa_cache_key') != cache_key:
                issues_all = []
                for lab, tables in bundles:
                    issues_all.extend(
                        qa_scan_run_tables(
                            tables,
                            run_label=str(lab),
                            table=str(table),
                            signals=scan_sigs,
                            sensitivity=qa_sens,
                            time_window=(float(time_window[0]), float(time_window[1])) if isinstance(time_window, (list, tuple)) and len(time_window) == 2 else None,
                        )
                    )
                qa_df_new = qa_issues_to_frame(issues_all)
                st.session_state['compare_qa_cache_key'] = cache_key
                # store as records for safer session serialization
                st.session_state['compare_qa_cache_records'] = qa_df_new.to_dict(orient='records')

            recs = st.session_state.get('compare_qa_cache_records')
            qa_df = pd.DataFrame(recs) if isinstance(recs, list) and recs else pd.DataFrame()
            qa_summary = qa_summarize(qa_df)

            # Banner
            if qa_summary.get('n', 0) > 0:
                if int(qa_summary.get('n_err', 0) or 0) > 0:
                    st.error(
                        f"QA: найдены критичные проблемы в сигналах (ошибок={qa_summary['n_err']}, предупреждений={qa_summary['n_warn']}). "
                        "Графики могут быть недостоверны. Откройте 'QA heatmap' ниже и кликните по проблемной ячейке."
                    )
                else:
                    st.warning(
                        f"QA: есть предупреждения в сигналах (предупреждений={qa_summary['n_warn']}). "
                        "Графики интерпретируйте осторожно."
                    )
            else:
                st.success("QA: явных проблем в выбранных сигналах не найдено.")

            # Heatmap + table (compact)
            if qa_df is not None and not qa_df.empty:
                st.subheader("QA heatmap: проблемы (run × signal)")
                st.caption(
                    "Цвет показывает максимальную серьёзность проблемы: 1 — мелкое, 2 — предупреждение, 3 — критично. "
                    "Клик по ячейке: фокус run+signal и (если известно) перенос playhead в место проблемы."
                )

                run_labels_hm = [lab for (lab, _t) in bundles]
                sig_labels_hm = list(scan_sigs)
                Z, first_t = qa_severity_matrix(qa_df, run_labels=run_labels_hm, signals=sig_labels_hm)
                qa_first_t = first_t or {}

                # wrap Y labels to prevent overlap
                # make y tick labels unique (even if wrapping makes them identical)
                y_wrapped = [f"{i+1:02d} {_wrap_tick_text(s, maxlen=22)}" for i, s in enumerate(sig_labels_hm)]

                # custom discrete-ish scale: 0=transparent, 1=yellow, 2=orange, 3=red
                colorscale = [
                    [0.0, "rgba(255,255,255,0.0)"],
                    [0.3333, "#fff3cd"],
                    [0.6666, "#ffd8a8"],
                    [1.0, "#fa5252"],
                ]
                fig_qa = go.Figure(
                    data=go.Heatmap(
                        z=Z,
                        x=run_labels_hm,
                        y=y_wrapped,
                        zmin=0,
                        zmax=3,
                        colorscale=colorscale,
                        colorbar=dict(title="severity"),
                        hovertemplate="run=%{x}<br>signal=%{y}<br>severity=%{z}<extra></extra>",
                    )
                )
                fig_qa.update_layout(
                    height=min(780, 220 + 18 * len(sig_labels_hm)),
                    margin=dict(l=10, r=10, t=30, b=10),
                    xaxis_title="run",
                    yaxis_title="signal",
                )

                ev_qa = _st_plotly_select(fig_qa, key="compare_qa_heatmap")
                click = _extract_first_xy_from_event(ev_qa)
                if click:
                    x_run, y_sig_wrapped = click
                    # unwrap by matching original
                    y_sig = None
                    try:
                        # y has a numeric prefix "NN "; use it if possible
                        y_txt = str(y_sig_wrapped)
                        pref = y_txt.split(' ', 1)[0].strip()
                        i = int(pref) - 1
                        if 0 <= i < len(sig_labels_hm):
                            y_sig = sig_labels_hm[i]
                    except Exception:
                        y_sig = None
                    if y_sig is None:
                        # fallback: match by exact label
                        try:
                            i = y_wrapped.index(str(y_sig_wrapped))
                            y_sig = sig_labels_hm[i]
                        except Exception:
                            y_sig = str(y_sig_wrapped)

                    st.session_state['compare_focus_run'] = str(x_run)
                    st.session_state['compare_focus_sig'] = str(y_sig)
                    st.session_state['compare_focus_pending'] = True
                    # move playhead to first known issue time
                    t0_issue = qa_first_t.get((str(x_run), str(y_sig)))
                    if isinstance(t0_issue, (int, float)) and np.isfinite(float(t0_issue)):
                        st.session_state['compare_click_t'] = float(t0_issue)
                    _rerun()

                # Filters
                cqa1, cqa2 = st.columns([1, 2])
                with cqa1:
                    min_sev = st.selectbox(
                        "Фильтр severity",
                        options=[1, 2, 3],
                        index=0,
                        key='compare_qa_min_sev',
                        help="Показывать только проблемы >= выбранной серьёзности.",
                    )
                with cqa2:
                    codes = sorted(list({str(c) for c in qa_df.get('code', []) if pd.notna(c)}))
                    pick_codes = st.multiselect(
                        "Типы проблем",
                        options=codes,
                        default=codes,
                        key='compare_qa_codes',
                    )
                qa_view = qa_df.copy()
                try:
                    qa_view = qa_view[pd.to_numeric(qa_view['severity'], errors='coerce').fillna(0) >= float(min_sev)]
                except Exception:
                    pass
                if pick_codes:
                    qa_view = qa_view[qa_view['code'].astype(str).isin([str(x) for x in pick_codes])]
                st.dataframe(
                    qa_view[["severity", "run_label", "signal", "code", "message", "t0", "t1"]].reset_index(drop=True),
                    width="stretch",
                    height=min(420, 38 + 22 * min(14, int(len(qa_view))))
                )
        except Exception:
            # QA should never crash the page
            pass

    # ------------------------------------------------------------
    # 7) Time-series compare
    # ------------------------------------------------------------
    # 7.0) Discrete events ("галька")
    show_events = bool(st.session_state.get('compare_events_enable', False))
    event_lines: List[float] = []

    def _get_events_df_cached(run_label: str, tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Compute discrete events for a run (cached in-memory, not persisted)."""
        cache = st.session_state.setdefault('_EV_events_cache', {})
        key = str(run_label)
        if key in cache:
            recs = cache.get(key)
            try:
                return pd.DataFrame(recs) if isinstance(recs, list) else pd.DataFrame()
            except Exception:
                return pd.DataFrame()
        try:
            evs = ev_scan_run_tables(tables, rising_only=True)
            df_e = ev_events_to_frame(evs)
            cache[key] = df_e.to_dict(orient='records')
            return df_e
        except Exception:
            cache[key] = []
            return pd.DataFrame()

    if show_events:
        with st.expander("События (дискретные) — переключения клапанов/контакта/упоров", expanded=False):
            st.caption(
                "События помогают быстро увидеть пороги/срабатывания (например: клапан открылся, колесо оторвалось). "
                "По умолчанию показываются только фронты (0→1), чтобы не захламлять графики." 
            )
            src = st.radio(
                "Источник событий",
                options=["Reference run", "Все активные runs"],
                index=0,
                key='compare_events_source',
                help="Reference — меньше шума. Все активные — больше информации, но риск визуального хаоса выше.",
                horizontal=True,
            )
            limit = st.slider(
                "Макс. маркеров (вертикальные линии) на time‑series",
                0,
                300,
                int(st.session_state.get('compare_events_limit', 60) or 60),
                step=10,
                key='compare_events_limit',
                help="Если событий слишком много — график станет нечитаемым. Уменьшите лимит или выберите меньше событий.",
            )

            # gather candidates from reference or all runs
            ev_pool: List[pd.DataFrame] = []
            if src.startswith('Reference'):
                ev_pool.append(_get_events_df_cached(ref_label, dict(bundles)[ref_label]))
            else:
                for lab, tdict in bundles:
                    ev_pool.append(_get_events_df_cached(lab, tdict))
            ev_all = pd.concat([d for d in ev_pool if isinstance(d, pd.DataFrame) and not d.empty], ignore_index=True) if ev_pool else pd.DataFrame()

            if ev_all.empty:
                st.info("Дискретные события не найдены (или таблицы не содержат дискретных сигналов).")
            else:
                # time window filter
                if isinstance(time_window, (tuple, list)) and len(time_window) == 2:
                    a, b = float(time_window[0]), float(time_window[1])
                    ev_all = ev_all[(pd.to_numeric(ev_all['t'], errors='coerce') >= a) & (pd.to_numeric(ev_all['t'], errors='coerce') <= b)]

                # available signals ranked by count
                s_counts = (
                    ev_all.groupby('signal', as_index=False)
                    .agg(count=('t', 'size'))
                    .sort_values(['count', 'signal'], ascending=[False, True], kind='mergesort')
                )
                sig_opts = [str(s) for s in s_counts['signal'].tolist()]
                top_default = sig_opts[: min(6, len(sig_opts))]
                pick = st.multiselect(
                    "Какие события показывать",
                    options=sig_opts,
                    default=list(st.session_state.get('compare_events_pick') or top_default),
                    key='compare_events_pick',
                    help="Список формируется автоматически по дискретным сигналам (0/1/2...).",
                )
                if pick:
                    ev_pick = ev_all[ev_all['signal'].astype(str).isin([str(x) for x in pick])]
                    times = [float(x) for x in pd.to_numeric(ev_pick['t'], errors='coerce').dropna().tolist()]
                    times.sort()
                    if limit <= 0:
                        event_lines = []
                    elif len(times) <= int(limit):
                        event_lines = times
                    else:
                        # равномерная подвыборка по времени (чтобы сохранялась "картина")
                        idx = np.linspace(0, len(times) - 1, int(limit)).astype(int)
                        event_lines = [times[i] for i in idx.tolist()]
                        st.warning(
                            f"Событий много ({len(times)}). Показываю подвыборку из {int(limit)} маркеров. "
                            "Уменьшите список событий или лимит, если стало шумно."
                        )

                # timeline (raster-like)
                show_tl = st.checkbox(
                    "Показать timeline событий (raster)",
                    value=bool(st.session_state.get('compare_events_timeline', True)),
                    key='compare_events_timeline',
                )
                if show_tl:
                    run_for_tl = st.selectbox(
                        "Run для timeline",
                        options=[lab for (lab, _t) in bundles],
                        index=[lab for (lab, _t) in bundles].index(ref_label) if ref_label in [lab for (lab, _t) in bundles] else 0,
                        key='compare_events_timeline_run',
                        help="Timeline показывает последовательность событий во времени для выбранного прогона.",
                    )
                    ev_df_run = _get_events_df_cached(run_for_tl, dict(bundles)[run_for_tl])
                    if isinstance(time_window, (tuple, list)) and len(time_window) == 2 and not ev_df_run.empty:
                        a, b = float(time_window[0]), float(time_window[1])
                        ev_df_run = ev_df_run[(pd.to_numeric(ev_df_run['t'], errors='coerce') >= a) & (pd.to_numeric(ev_df_run['t'], errors='coerce') <= b)]

                    if pick and not ev_df_run.empty:
                        ev_df_run = ev_df_run[ev_df_run['signal'].astype(str).isin([str(x) for x in pick])]

                    if ev_df_run.empty:
                        st.info("Для выбранного run нет событий в текущем окне времени.")
                    else:
                        # stable ordering of event types
                        ev_types = [str(x) for x in (pick or sorted(ev_df_run['signal'].astype(str).unique().tolist()))]
                        ev_types = ev_types[: min(20, len(ev_types))]
                        ymap = {s: i for i, s in enumerate(ev_types)}

                        ev_df_run = ev_df_run.copy()
                        ev_df_run['y'] = ev_df_run['signal'].astype(str).map(ymap)
                        ev_df_run = ev_df_run[pd.notna(ev_df_run['y'])]

                        ytick = [f"{i+1:02d} {_wrap_tick_text(s, maxlen=26)}" for i, s in enumerate(ev_types)]

                        fig_ev = go.Figure(
                            data=go.Scatter(
                                x=pd.to_numeric(ev_df_run['t'], errors='coerce'),
                                y=pd.to_numeric(ev_df_run['y'], errors='coerce'),
                                mode='markers',
                                marker=dict(size=10, symbol='circle'),
                                hovertemplate="t=%{x:.6g}s<br>event=%{customdata[0]}<br>%{customdata[1]}→%{customdata[2]}<extra></extra>",
                                customdata=np.stack(
                                    [
                                        ev_df_run['signal'].astype(str).values,
                                        pd.to_numeric(ev_df_run['from'], errors='coerce').fillna(np.nan).values,
                                        pd.to_numeric(ev_df_run['to'], errors='coerce').fillna(np.nan).values,
                                    ],
                                    axis=1,
                                ),
                            )
                        )
                        fig_ev.update_layout(
                            height=min(520, 180 + 22 * len(ytick)),
                            margin=dict(l=10, r=10, t=30, b=40),
                            xaxis_title='t, s',
                            yaxis_title='event',
                        )
                        fig_ev.update_yaxes(
                            tickmode='array',
                            tickvals=list(range(len(ev_types))),
                            ticktext=ytick,
                            autorange='reversed',
                        )

                        ev_click = _st_plotly_select(fig_ev, key='compare_events_timeline_plot')
                        x_ev, y_ev = _extract_first_xy_from_event(ev_click)
                        if x_ev is not None:
                            try:
                                st.session_state['compare_click_t'] = float(x_ev)
                                _rerun()
                            except Exception:
                                pass

                        # export
                        csv_bytes = ev_df_run.drop(columns=['y'], errors='ignore').to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "Скачать events.csv",
                            data=csv_bytes,
                            file_name=f"events_{str(run_for_tl).replace(' ', '_')}.csv",
                            mime='text/csv',
                            key='compare_events_download_csv',
                        )

    with st.spinner("Рисуем графики..."):
        fig, _sig_ranges = _build_compare_figure(
            bundles,
            table,
            sigs,
            mode_delta=mode_delta,
            ref_label=ref_label,
            dist_unit=dist_unit,
            angle_unit=angle_unit,
            p_atm=float(p_atm),
            zero_baseline=bool(zero_baseline),
            baseline_mode=str(baseline_mode),
            baseline_window_s=float(baseline_window_s),
            baseline_first_n=int(baseline_first_n),
            lock_y_signal=bool(lock_y_signal),
            lock_y_unit=bool(lock_y_unit),
            robust_y=bool(robust_y),
            sym_y=bool(sym_y),
            flow_unit=str(flow_unit),
            time_window=time_window if isinstance(time_window, tuple) else None,
            t_play=float(t_play) if 't_play' in locals() else None,
            event_lines=list(event_lines) if show_events and event_lines else None,
        )

    ev_ts = _st_plotly_select(fig, key='compare_ts_chart')
    x_sel, _y_sel = _extract_first_xy_from_event(ev_ts)
    if x_sel is not None:
        try:
            x_val = float(x_sel)
            if np.isfinite(x_val):
                prev = st.session_state.get('compare_click_t')
                if prev is None or abs(float(prev) - x_val) > 1e-12:
                    st.session_state['compare_click_t'] = x_val
                    _rerun()
        except Exception:
            pass

    # ------------------------------------------------------------
    # 7.5) Distributions / per-run metrics (quick qualitative compare)
    # ------------------------------------------------------------
    try:
        st.subheader("Распределения / статистика по run")
        st.caption(
            "Быстрый качественный анализ: для выбранного сигнала вычисляем одно число на каждый run "
            "(например, значение в playhead или RMS по окну) и показываем распределение/ранжирование."
        )

        cdd1, cdd2, cdd3 = st.columns([2, 2, 1])
        with cdd1:
            dist_sig = st.selectbox(
                "Сигнал",
                options=list(sigs),
                index=max(0, list(sigs).index(st.session_state.get('compare_focus_sig')))
                if st.session_state.get('compare_focus_sig') in sigs else 0,
                key='compare_dist_sig',
            )
        with cdd2:
            dist_mode = st.selectbox(
                "Метрика",
                options=[
                    "Значение @ playhead",
                    "Δ @ playhead (vs reference)",
                    "RMS по окну",
                    "RMS(Δ) по окну (vs reference)",
                    "max|Δ| по окну (vs reference)",
                ],
                index=0,
                key='compare_dist_mode',
                help="Метрика считается по каждому run и затем визуализируется как распределение/ранжирование.",
            )
        with cdd3:
            show_kde = st.checkbox(
                "KDE",
                value=False,
                key='compare_dist_kde',
                help="Попытаться дорисовать KDE (если доступен scipy).",
            )

        # Compute per-run values
        ref_tables = dict(bundles)[ref_label]
        x_ref, y_ref, unit_ref = _get_xy(
            ref_tables,
            table,
            dist_sig,
            dist_unit=str(dist_unit),
            angle_unit=str(angle_unit),
            p_atm=float(p_atm),
            zero_baseline=bool(zero_baseline),
            baseline_mode=str(baseline_mode),
            baseline_window_s=float(baseline_window_s),
            baseline_first_n=int(baseline_first_n),
            flow_unit=str(flow_unit),
        )

        vals: List[float] = []
        labs: List[str] = []

        # window on reference grid
        if isinstance(time_window, tuple) and x_ref.size:
            tw0, tw1 = float(time_window[0]), float(time_window[1])
            wmask_ref = (x_ref >= min(tw0, tw1)) & (x_ref <= max(tw0, tw1))
        else:
            wmask_ref = None

        for lab, tables in bundles:
            x, y, unit = _get_xy(
                tables,
                table,
                dist_sig,
                dist_unit=str(dist_unit),
                angle_unit=str(angle_unit),
                p_atm=float(p_atm),
                zero_baseline=bool(zero_baseline),
                baseline_mode=str(baseline_mode),
                baseline_window_s=float(baseline_window_s),
                baseline_first_n=int(baseline_first_n),
                flow_unit=str(flow_unit),
            )
            if x.size == 0 or y.size == 0:
                continue

            v = float('nan')
            if dist_mode.startswith("Значение"):
                v = float(np.interp(float(t_play), x, y, left=np.nan, right=np.nan))
            elif dist_mode.startswith("Δ @"):
                y0 = float(np.interp(float(t_play), x, y, left=np.nan, right=np.nan))
                yref0 = float(np.interp(float(t_play), x_ref, y_ref, left=np.nan, right=np.nan)) if x_ref.size and y_ref.size else float('nan')
                v = y0 - yref0
            elif dist_mode.startswith("RMS(Δ)"):
                if x_ref.size and y_ref.size:
                    y_itp = np.interp(x_ref, x, y, left=np.nan, right=np.nan)
                    d = y_itp - y_ref
                    if wmask_ref is not None and bool(wmask_ref.any()):
                        d = d[wmask_ref]
                    v = float(np.sqrt(np.nanmean(d * d)))
            elif dist_mode.startswith("max|Δ|"):
                if x_ref.size and y_ref.size:
                    y_itp = np.interp(x_ref, x, y, left=np.nan, right=np.nan)
                    d = y_itp - y_ref
                    if wmask_ref is not None and bool(wmask_ref.any()):
                        d = d[wmask_ref]
                    v = float(np.nanmax(np.abs(d)))
            else:  # RMS
                y_use = y
                if isinstance(time_window, tuple) and x.size:
                    tw0, tw1 = float(time_window[0]), float(time_window[1])
                    m = (x >= min(tw0, tw1)) & (x <= max(tw0, tw1))
                    if bool(m.any()):
                        y_use = y[m]
                v = float(np.sqrt(np.nanmean(y_use * y_use)))

            labs.append(str(lab))
            vals.append(v)

        if vals:
            df_dist = pd.DataFrame({"run": labs, "value": vals})
            df_dist = df_dist[np.isfinite(df_dist["value"].values)]
        else:
            df_dist = pd.DataFrame(columns=["run", "value"])

        if df_dist.empty:
            st.info("Недостаточно данных для распределений (проверьте Signals/окно времени).")
        else:
            # sort for bar
            df_bar = df_dist.sort_values("value", ascending=False).reset_index(drop=True)
            df_bar["run_short"] = df_bar["run"].map(lambda s: _trim_label(s, 22))

            tab1, tab2, tab3 = st.tabs(["Ранжирование", "Гистограмма", "Box"])
            with tab1:
                fig_bar = go.Figure(
                    data=go.Bar(
                        x=df_bar["run_short"],
                        y=df_bar["value"],
                        customdata=df_bar["run"],
                        hovertemplate="run=%{customdata}<br>value=%{y:.6g}<extra></extra>",
                    )
                )
                fig_bar.update_layout(
                    height=420,
                    margin=dict(l=20, r=10, t=30, b=90),
                    xaxis_tickangle=45,
                    yaxis_title=f"{dist_mode} [{unit_ref}]" if unit_ref else dist_mode,
                )
                _st_plotly(fig_bar, key="compare_dist_bar")

            with tab2:
                fig_h = go.Figure(
                    data=go.Histogram(
                        x=df_dist["value"],
                        nbinsx=min(40, max(10, int(np.sqrt(len(df_dist))))) ,
                        hovertemplate="value=%{x:.6g}<br>count=%{y}<extra></extra>",
                    )
                )
                fig_h.update_layout(
                    height=420,
                    margin=dict(l=20, r=10, t=30, b=40),
                    xaxis_title=f"{dist_mode} [{unit_ref}]" if unit_ref else dist_mode,
                    yaxis_title="count",
                )
                _st_plotly(fig_h, key="compare_dist_hist")

                if show_kde:
                    try:
                        from scipy.stats import gaussian_kde  # type: ignore

                        xs = np.linspace(float(df_dist["value"].min()), float(df_dist["value"].max()), 160)
                        kde = gaussian_kde(df_dist["value"].values)
                        ys = kde(xs)
                        fig_k = go.Figure(data=go.Scatter(x=xs, y=ys, mode='lines', name='KDE'))
                        fig_k.update_layout(
                            height=260,
                            margin=dict(l=20, r=10, t=10, b=40),
                            xaxis_title=f"{dist_mode} [{unit_ref}]" if unit_ref else dist_mode,
                            yaxis_title="density",
                        )
                        _st_plotly(fig_k, key="compare_dist_kde_plot")
                    except Exception:
                        st.info("KDE недоступна (scipy не установлен).")

            with tab3:
                fig_b = go.Figure(
                    data=go.Box(
                        y=df_dist["value"],
                        boxpoints='all',
                        jitter=0.35,
                        pointpos=0,
                        hovertemplate="value=%{y:.6g}<extra></extra>",
                    )
                )
                fig_b.update_layout(
                    height=420,
                    margin=dict(l=20, r=10, t=30, b=40),
                    yaxis_title=f"{dist_mode} [{unit_ref}]" if unit_ref else dist_mode,
                )
                _st_plotly(fig_b, key="compare_dist_box")
    except Exception:
        # distribution block should never break compare page
        pass

    # ------------------------------------------------------------
    # 8) Heatmap: max |Δ|
    # ------------------------------------------------------------
    st.subheader("Heatmap: max |Δ| относительно reference")

    heat_df, heat_fig = _delta_heatmap(
        bundles,
        table,
        sigs,
        ref_label=ref_label,
        dist_unit=dist_unit,
        angle_unit=angle_unit,
        p_atm=float(p_atm),
        zero_baseline=bool(zero_baseline),
        baseline_mode=str(baseline_mode),
        baseline_window_s=float(baseline_window_s),
        baseline_first_n=int(baseline_first_n),
        flow_unit=str(flow_unit),
    )

    ev_h0 = _st_plotly_select(heat_fig, key='compare_heat_maxabs')
    xr, ys = _extract_first_xy_from_event(ev_h0)
    if xr is not None and ys is not None:
        try:
            run_sel = str(xr)
            sig_sel = str(ys)
            if run_sel and sig_sel:
                if st.session_state.get('compare_focus_sig') != sig_sel:
                    st.session_state['compare_focus_run'] = run_sel
                    st.session_state['compare_focus_sig'] = sig_sel
                    st.session_state['compare_focus_pending'] = True
                    _rerun()
        except Exception:
            pass

    _st_plotly(heat_fig, key='compare_heat_maxabs_view')
    st.dataframe(heat_df, width="stretch")

    if st.session_state.get('compare_focus_sig'):
        st.info(
            f"Focus: run=**{st.session_state.get('compare_focus_run','–')}**, sig=**{st.session_state.get('compare_focus_sig')}**"
        )

    # ------------------------------------------------------------
    # 9) Δ(t) heatmap player
    # ------------------------------------------------------------
    st.subheader("Δ(t) heatmap player — сигнал × прогон во времени")
    st.caption(
        "Это **срез во времени**: видно *когда* и *по каким сигналам* различия возникают/исчезают. "
        "Время синхронизировано с playhead выше."
    )

    col_h1, col_h2 = st.columns([2, 3])
    with col_h1:
        show_deltat = st.checkbox(
            "Показать Δ(t) heatmap",
            value=bool(st.session_state.get('compare_deltat_show', False)),
            key='compare_deltat_show',
        )
    with col_h2:
        heat_mode = st.radio(
            "Режим",
            options=["Δ к reference", "Абсолютные значения"],
            index=0,
            key='compare_deltat_mode',
            horizontal=True,
        )

    if show_deltat:
        max_sigs_heat = st.slider(
            "Макс. сигналов в heatmap (читаемость)",
            4,
            30,
            int(st.session_state.get('compare_deltat_max_sigs', min(12, max(4, len(sigs))))),
            step=1,
            key='compare_deltat_max_sigs',
        )

        sigs_heat = list(sigs)[: int(max_sigs_heat)]
        abs_mode = st.checkbox("Показывать |значение| (без знака)", value=bool(st.session_state.get('compare_deltat_abs', False)), key='compare_deltat_abs')
        rel_mode = st.checkbox("Нормировать на амплитуду reference (относительно)", value=bool(st.session_state.get('compare_deltat_rel', False)), key='compare_deltat_rel')

        max_time_points = st.slider("LOD: макс. точек времени для куба", 200, 6000, int(st.session_state.get('compare_deltat_tpts', 2000)), step=200, key='compare_deltat_tpts')
        max_frames = st.slider("LOD: кадров для анимации", 20, 400, int(st.session_state.get('compare_deltat_frames', 120)), step=10, key='compare_deltat_frames')
        do_anim = st.checkbox("Анимация (play/pause)", value=bool(st.session_state.get('compare_deltat_anim', False)), key='compare_deltat_anim')

        run_map = {lab: bun for lab, bun in runs_full}
        runs_sel = [(lab, run_map.get(lab, {})) for lab, _ in bundles if lab in run_map]

        cube_mode = 'delta' if heat_mode.startswith('Δ') else 'value'

        with st.spinner("Готовим Δ(t) heatmap…"):
            cube_obj = build_deltat_cube(
                runs_sel,
                table=table,
                sigs=sigs_heat,
                ref_label=ref_label,
                mode=cube_mode,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=float(p_atm),
                BAR_PA=float(BAR_PA),
                baseline_mode=str(baseline_mode),
                baseline_window_s=float(baseline_window_s),
                baseline_first_n=int(baseline_first_n),
                zero_positions=bool(zero_baseline),
                flow_unit=str(flow_unit),
                time_window=time_window if isinstance(time_window, tuple) else None,
                max_time_points=int(max_time_points),
            )

        tH = cube_obj.t
        Z = np.asarray(cube_obj.cube, dtype=float)

        if rel_mode and cube_mode == 'delta':
            scales = []
            for s in sigs_heat:
                try:
                    xr0, yr0, _u = _get_xy(ref_tables, table, s,
                                           dist_unit=dist_unit, angle_unit=angle_unit, p_atm=float(p_atm),
                                           zero_baseline=bool(zero_baseline), baseline_mode=str(baseline_mode),
                                           baseline_window_s=float(baseline_window_s), baseline_first_n=int(baseline_first_n),
                                           flow_unit=str(flow_unit))
                    if time_window and xr0.size:
                        m = (xr0 >= time_window[0]) & (xr0 <= time_window[1])
                        yr_use = yr0[m] if m.any() else yr0
                    else:
                        yr_use = yr0
                    sc = float(np.nanmax(np.abs(yr_use))) if yr_use.size else 1.0
                    if not np.isfinite(sc) or sc <= 0:
                        sc = 1.0
                except Exception:
                    sc = 1.0
                scales.append(sc)
            scales = np.asarray(scales, dtype=float)
            Z = Z / scales.reshape(1, -1, 1)

        if abs_mode:
            Z = np.abs(Z)

        if tH.size:
            try:
                idxH = int(np.argmin(np.abs(tH - float(t_play))))
            except Exception:
                idxH = 0
            idxH = max(0, min(idxH, int(len(tH) - 1)))
        else:
            idxH = 0

        z_snap = Z[idxH, :, :] if Z.size else np.zeros((len(sigs_heat), len(bundles)), dtype=float)

        x_full = list(cube_obj.run_labels)
        y_full = list(cube_obj.sigs)

        def _trim(s: str, n: int = 36) -> str:
            s = str(s)
            return s if len(s) <= n else (s[: max(0, n - 1)] + '…')

        x_tickvals = x_full
        x_ticktext = [_trim(s, 28) for s in x_full]

        y_tickvals = y_full
        y_ticktext = [_trim(s, 42) for s in y_full]
        if len(y_full) > 18:
            step = int(np.ceil(len(y_full) / 18))
            keep = list(range(0, len(y_full), step))
            y_tickvals = [y_full[i] for i in keep]
            y_ticktext = [_trim(y_full[i], 42) for i in keep]

        z_abs = np.abs(Z[np.isfinite(Z)]) if np.isfinite(Z).any() else np.asarray([0.0])
        if z_abs.size:
            zmax = float(np.nanpercentile(z_abs, 98))
            if not np.isfinite(zmax) or zmax <= 0:
                zmax = float(np.nanmax(z_abs)) if z_abs.size else 1.0
        else:
            zmax = 1.0

        colorscale = 'Viridis' if (abs_mode or rel_mode or cube_mode == 'value') else 'RdBu'
        zmin, zmax_use = (0.0, zmax) if (abs_mode or rel_mode or cube_mode == 'value') else (-zmax, zmax)

        figH = go.Figure(data=go.Heatmap(z=z_snap, x=x_full, y=y_full, colorscale=colorscale, zmin=zmin, zmax=zmax_use,
                                         hovertemplate='run=%{x}<br>sig=%{y}<br>val=%{z:.4g}<extra></extra>'))
        height = max(520, 22 * len(y_full) + 240)
        figH.update_layout(height=height, margin=dict(l=260, r=20, t=40, b=80), title=f"t={float(tH[idxH]) if tH.size else 0.0:.4f} s")
        figH.update_xaxes(tickvals=x_tickvals, ticktext=x_ticktext, tickangle=0, automargin=True)
        figH.update_yaxes(tickvals=y_tickvals, ticktext=y_ticktext, automargin=True)

        ev_h = _st_plotly_select(figH, key='compare_deltat_snapshot')
        xr2, ys2 = _extract_first_xy_from_event(ev_h)
        if xr2 is not None and ys2 is not None:
            try:
                run_sel = str(xr2)
                sig_sel = str(ys2)
                if run_sel and sig_sel:
                    if st.session_state.get('compare_focus_sig') != sig_sel:
                        st.session_state['compare_focus_run'] = run_sel
                        st.session_state['compare_focus_sig'] = sig_sel
                        st.session_state['compare_focus_pending'] = True
                        _rerun()
            except Exception:
                pass

        _st_plotly(figH, key='compare_deltat_snapshot_view')

        if do_anim and tH.size and Z.size:
            idxs = pick_frame_indices(tH, max_frames=int(max_frames))
            frames = [go.Frame(name=f"{float(tH[ii]):.4f}", data=[go.Heatmap(z=Z[int(ii), :, :])]) for ii in idxs]
            figA = go.Figure(data=figH.data)
            figA.frames = frames
            steps = [dict(method='animate', label=fr.name,
                          args=[[fr.name], {'mode': 'immediate', 'frame': {'duration': 0, 'redraw': True}, 'transition': {'duration': 0}}]) for fr in frames]
            figA.update_layout(
                height=height,
                margin=dict(l=260, r=20, t=50, b=90),
                title='Δ(t) heatmap — animation',
                updatemenus=[dict(type='buttons', direction='left', x=0.0, y=1.18,
                                  buttons=[
                                      dict(label='▶', method='animate', args=[None, {'fromcurrent': True, 'frame': {'duration': 60, 'redraw': True}, 'transition': {'duration': 0}}]),
                                      dict(label='⏸', method='animate', args=[[None], {'mode': 'immediate', 'frame': {'duration': 0, 'redraw': False}, 'transition': {'duration': 0}}]),
                                  ])],
                sliders=[dict(active=0, y=1.08, x=0.0, len=1.0, pad={'t': 10, 'b': 0}, steps=steps)],
            )
            figA.update_xaxes(tickvals=x_tickvals, ticktext=x_ticktext, tickangle=0, automargin=True)
            figA.update_yaxes(tickvals=y_tickvals, ticktext=y_ticktext, automargin=True)
            _st_plotly(figA, key='compare_deltat_anim_view')

    # ------------------------------------------------------------
    # 10) Static report (stroke)
    # ------------------------------------------------------------
    st.subheader("Статика (t0): быстрая проверка штоков")
    meta_ref = metas.get(ref_label, {})
    Lstroke = float(meta_ref.get('L_stroke_m') or meta_ref.get('ход_штока_м') or 0.0)
    st.caption("Цель: шток ~ 50% хода в статике. Это проверка, а не принудительная коррекция.")
    rep = _static_stroke_report(ref_tables, dist_unit=dist_unit, angle_unit=angle_unit, p_atm=float(p_atm))
    if rep.empty:
        st.info("Не найдено сигналов штока (по имени колонки).")
    else:
        if Lstroke > 1e-9:
            rep['stroke_%'] = (rep['t0'] / (Lstroke * (1000.0 if dist_unit == 'mm' else 1.0))) * 100.0
            rep['dev_from_50_%'] = rep['stroke_%'] - 50.0
        st.dataframe(rep, width="stretch")

    # ------------------------------------------------------------
    # 11) N→N influence
    # ------------------------------------------------------------
    st.subheader("N→N influence: meta параметры → сигналы/метрики")
    st.caption("Цель: быстро увидеть *какие входные параметры (meta)* сильнее всего связаны с выбранными выходными сигналами.")

    # Подготовим meta → X один раз (используется в обеих вкладках).
    try:
        _flat_metas = {lab: _flatten_meta_numeric(metas.get(lab, {})) for lab, _ in bundles}
        _feat_names_all = sorted({k for d in _flat_metas.values() for k in d.keys()})
        _X_all = np.asarray(
            [[float(_flat_metas[lab].get(k, np.nan)) for k in _feat_names_all] for lab, _ in bundles],
            dtype=float,
        )
    except Exception:
        _flat_metas, _feat_names_all, _X_all = {}, [], np.zeros((0, 0), dtype=float)

    tab_rms, tab_t = st.tabs(["RMS (по окну / Δ)", "В момент времени (playhead)"])

    with tab_rms:
        st.caption("Корреляция: meta (X) ↔ RMS(сигнал) (Y). RMS считается по выбранному окну времени и текущему режиму (Value/Δ).")

        max_feat_rms = st.slider(
            "Сколько параметров meta показывать (топ по силе влияния)",
            min_value=5, max_value=80, value=int(st.session_state.get("compare_infl_rms_maxfeat", 30)),
            key="compare_infl_rms_maxfeat",
            help="Показываются только самые информативные параметры meta (сильнее всего коррелируют с метриками).",
        )

        try:
            if not _feat_names_all:
                st.info("В meta_json не найдено численных параметров → влияние считать не из чего.")
            elif len(bundles) < 3:
                st.info("Для корреляции нужно хотя бы 3 прогона (runs).")
            else:
                n_runs = len(bundles)
                n_sigs = len(sigs)
                if n_sigs == 0:
                    st.info("Сначала выберите хотя бы один сигнал (Signals).")
                else:
                    # Y: runs × signals (RMS)
                    Y_rms = np.full((n_runs, n_sigs), np.nan, dtype=float)
                    met_names = [f"RMS({s})" for s in sigs]

                    ref_tables2 = dict(bundles)[ref_label]

                    for j, sig in enumerate(sigs):
                        x_ref, y_ref, _unit = _get_xy(
                            ref_tables2, table, sig,
                            dist_unit=dist_unit, angle_unit=angle_unit, p_atm=float(p_atm),
                            zero_baseline=bool(zero_baseline), baseline_mode=str(baseline_mode),
                            baseline_window_s=float(baseline_window_s), baseline_first_n=int(baseline_first_n),
                            flow_unit=str(flow_unit),
                        )
                        if time_window and x_ref.size:
                            m = (x_ref >= time_window[0]) & (x_ref <= time_window[1])
                            x_ref_use = x_ref[m] if m.any() else x_ref
                            y_ref_use = y_ref[m] if m.any() else y_ref
                        else:
                            x_ref_use, y_ref_use = x_ref, y_ref

                        for i, (lab, tables) in enumerate(bundles):
                            x, y, _u = _get_xy(
                                tables, table, sig,
                                dist_unit=dist_unit, angle_unit=angle_unit, p_atm=float(p_atm),
                                zero_baseline=bool(zero_baseline), baseline_mode=str(baseline_mode),
                                baseline_window_s=float(baseline_window_s), baseline_first_n=int(baseline_first_n),
                                flow_unit=str(flow_unit),
                            )
                            if x_ref_use.size:
                                y_i = resample_linear(x, y, x_ref_use)
                            else:
                                y_i = y

                            if mode_delta:
                                if lab == ref_label:
                                    d = np.zeros_like(y_ref_use)
                                else:
                                    d = y_i - y_ref_use
                            else:
                                d = y_i

                            if d.size:
                                Y_rms[i, j] = float(np.sqrt(np.nanmean(d * d)))

                    # X: runs × features (prefilter if слишком много фич)
                    feat_names = list(_feat_names_all)
                    X_use = np.asarray(_X_all, dtype=float)

                    if len(feat_names) > 600:
                        # быстрый предфильтр по дисперсии, чтобы heatmap оставался читаемым
                        keep0 = max(200, int(max_feat_rms) * 8)
                        pref = prefilter_features_by_variance(X_use, feat_names, keep=keep0)
                        idx_map = {n: ii for ii, n in enumerate(feat_names)}
                        pref_idx = [idx_map[n] for n in pref if n in idx_map]
                        feat_names = [feat_names[ii] for ii in pref_idx]
                        X_use = X_use[:, pref_idx] if pref_idx else X_use

                    corr = _corr_matrix(X_use, Y_rms, min_n=3)  # features × metrics
                    feat_sorted = rank_features_by_max_abs_corr(corr, feat_names)
                    feat_sel = feat_sorted[: int(max_feat_rms)]

                    if not feat_sel:
                        st.info("Не удалось выбрать параметры meta для отображения (возможно, все NaN/константы).")
                    else:
                        idx_map2 = {n: ii for ii, n in enumerate(feat_names)}
                        sel_idx = [idx_map2[n] for n in feat_sel if n in idx_map2]
                        corr_sel = corr[sel_idx, :] if sel_idx else corr

                        # ticks (trim) — чтобы подписи не налезали друг на друга
                        y_ticktext = [_trim_label(n, 44) for n in feat_sel]
                        x_ticktext = [_trim_label(n, 42) for n in met_names]
                        if len(met_names) > 8:
                            x_angle = -35
                        else:
                            x_angle = 0

                        figc = go.Figure(
                            data=go.Heatmap(
                                z=corr_sel, x=met_names, y=feat_sel,
                                colorscale="RdBu", zmin=-1, zmax=1,
                                hovertemplate="meta=%{y}<br>metric=%{x}<br>corr=%{z:.3f}<extra></extra>",
                            )
                        )
                        figc.update_layout(height=max(520, 20 * len(feat_sel) + 260), margin=dict(l=260, r=20, t=30, b=90))
                        figc.update_xaxes(ticktext=x_ticktext, tickvals=met_names, tickangle=x_angle, automargin=True)
                        figc.update_yaxes(ticktext=y_ticktext, tickvals=feat_sel, automargin=True)

                        _st_plotly(figc, key="compare_influence_corr_rms")

                        st.caption(f"Meta параметров всего: {len(_feat_names_all)}. На карте показано: {len(feat_sel)}.")

                        with st.expander("Мультипараметрический Explorer (SPLOM / Parallel / 3D)", expanded=False):

                            st.caption(

                                "Быстрый качественный обзор взаимосвязей: meta‑параметры ↔ метрики (RMS/Δ). "

                                "Рекомендуемый путь: 1) heatmap корреляций → 2) SPLOM/Parallel → 3) 3D‑облако для обзора."

                            )


                            run_labels_all = [lab for lab, _td in bundles]


                            # --- выбор признаков ---

                            feat_default = list(st.session_state.get('compare_multi_feats') or feat_sel[: min(8, len(feat_sel))])

                            feat_multi = st.multiselect(

                                "Meta параметры (ось/анализ)",

                                options=list(feat_sel),

                                default=feat_default,

                                key='compare_multi_feats',

                                help=(

                                    "Это численные параметры из meta (включая параметры схемы/оптимизации). "

                                    "По умолчанию берём наиболее влияющие (по корреляции)."

                                ),

                            )


                            # --- выбор метрик (сигналы) ---

                            # score = средняя RMS (чтобы по умолчанию показывать наиболее 'живые' метрики)

                            try:

                                _ms = np.nanmean(np.abs(Y_rms), axis=0)

                                _ord = np.argsort(-_ms)

                                met_default = [met_names[i] for i in _ord[: min(10, len(met_names))]]

                            except Exception:

                                met_default = met_names[: min(10, len(met_names))]


                            met_multi = st.multiselect(

                                "Метрики (RMS по выбранным сигналам)",

                                options=list(met_names),

                                default=list(st.session_state.get('compare_multi_metrics') or met_default),

                                key='compare_multi_metrics',

                                help=(

                                    "Каждая метрика = RMS(сигнал) по текущим настройкам (Δ к ref/абсолют). "

                                    "Слишком много метрик ухудшает читаемость — начните с 6–12."

                                ),

                            )


                            cols_all = list(feat_multi) + list(met_multi)

                            if len(cols_all) < 2:

                                st.info("Выберите минимум 1 meta‑параметр и 1 метрику (или любые 2 оси).")

                            else:

                                # --- сбор df ---

                                dfm = pd.DataFrame({'run': run_labels_all})

                                # meta

                                for f in feat_multi:

                                    if f in idx_map2:

                                        dfm[f] = X_use[:, idx_map2[f]]

                                # metrics

                                met_idx_map = {n: j for j, n in enumerate(met_names)}

                                for m in met_multi:

                                    j = met_idx_map.get(m)

                                    if j is not None:

                                        dfm[m] = Y_rms[:, j]


                                # удаляем строки где нет данных по выбранным осям

                                dfm_num = dfm.dropna(subset=[c for c in cols_all if c in dfm.columns])


                                if len(dfm_num) < 3:

                                    st.warning("Недостаточно валидных точек (после удаления NaN) для мульти‑графиков.")

                                else:

                                    tab_m1, tab_m2, tab_m3 = st.tabs(["SPLOM", "Parallel", "3D облако"])


                                    # --- SPLOM ---

                                    with tab_m1:

                                        st.caption(

                                            "SPLOM (scatterplot matrix) быстро показывает нелинейности/кластеры/аномалии. "

                                            "Выделение точек (lasso/box) можно применить как фильтр прогонов (Compare filter сверху)."

                                        )


                                        max_dims = min(6, len(cols_all))

                                        dims_default = list(st.session_state.get('compare_multi_splom_dims') or cols_all[:max_dims])

                                        dims = st.multiselect(

                                            "Оси для SPLOM (до 6)",

                                            options=list(cols_all),

                                            default=dims_default,

                                            key='compare_multi_splom_dims',

                                            help="Рекомендация: 3–6 осей. Больше — перегруз восприятия.",

                                        )

                                        if len(dims) > 6:

                                            dims = list(dims)[:6]

                                            st.info("SPLOM ограничен 6 осями — лишнее отброшено.")


                                        color_candidates = list(met_multi) + [c for c in feat_multi if c not in met_multi]

                                        color_col = st.selectbox(

                                            "Цвет (градиент)",

                                            options=color_candidates,

                                            index=0,

                                            key='compare_multi_color',

                                            help="Цвет помогает увидеть области параметров, где метрика/сигнал резко меняется.",

                                        )


                                        # LOD

                                        keep_n = st.slider(

                                            "Сколько точек показывать (LOD)",

                                            min_value=3,

                                            max_value=int(max(3, len(dfm_num))),

                                            value=int(st.session_state.get('compare_multi_lod') or min(200, len(dfm_num))),

                                            step=1,

                                            key='compare_multi_lod',

                                            help="Уменьшайте, если график тяжёлый. Для 100–300 прогонов обычно OK.",

                                        )

                                        df_plot = dfm_num if keep_n >= len(dfm_num) else dfm_num.sample(n=int(keep_n), random_state=0)


                                        labels_map = {c: _trim_label(str(c), 22) for c in dims}

                                        fig_splom = px.scatter_matrix(

                                            df_plot,

                                            dimensions=dims,

                                            color=color_col,

                                            hover_name='run',

                                            labels=labels_map,

                                        )

                                        fig_splom.update_traces(diagonal_visible=False, marker=dict(size=6, opacity=0.65))

                                        fig_splom.update_layout(height=760, margin=dict(l=40, r=20, t=40, b=40))


                                        ev_sel = _st_plotly_select(fig_splom, key='compare_multi_splom_plot')

                                        sel_runs = _extract_selected_texts(ev_sel)

                                        if sel_runs:

                                            # сохраним как pending — пользователь может применить сверху через сравнение

                                            st.session_state['compare_active_runs_pending_value'] = [r for r in sel_runs if r in run_labels_all]

                                            st.success(f"Выделено прогонов: {len(sel_runs)} (pending фильтр).")


                                    # --- Parallel coordinates ---

                                    with tab_m2:

                                        st.caption(

                                            "Parallel coordinates (параллельные координаты) полезны, когда параметров много: "

                                            "видно, какие комбинации дают хорошие/плохие метрики. "

                                            "Это качественный обзор — затем уточняйте через heatmap и графики во времени."

                                        )


                                        dims_pc_default = list(st.session_state.get('compare_multi_par_dims') or cols_all[: min(10, len(cols_all))])

                                        dims_pc = st.multiselect(

                                            "Оси для parallel (рекомендовано 6–12)",

                                            options=list(cols_all),

                                            default=dims_pc_default,

                                            key='compare_multi_par_dims',

                                        )

                                        if len(dims_pc) < 2:

                                            st.info("Выберите минимум 2 оси.")

                                        else:

                                            labels_map2 = {c: _trim_label(str(c), 22) for c in dims_pc}

                                            fig_pc = px.parallel_coordinates(

                                                dfm_num,

                                                dimensions=dims_pc,

                                                color=color_col,

                                                labels=labels_map2,

                                            )

                                            fig_pc.update_layout(height=760, margin=dict(l=40, r=20, t=40, b=40))

                                            _st_plotly(fig_pc, key='compare_multi_parcoords_plot')


                                    # --- 3D cloud ---

                                    with tab_m3:

                                        st.caption(

                                            "3D используется для качественного обзора (вращение мышью). "

                                            "Чтобы не получить 'тёмный блин' — включено прореживание по плотности. "

                                            "Для строгих выводов используйте 2D heatmaps/корреляции."

                                        )


                                        def _safe_idx(i: int, n: int) -> int:

                                            return 0 if n <= 0 else max(0, min(i, n - 1))


                                        x3 = st.selectbox('X', options=list(cols_all), index=_safe_idx(0, len(cols_all)), key='compare_multi_3d_x')

                                        y3 = st.selectbox('Y', options=list(cols_all), index=_safe_idx(1, len(cols_all)), key='compare_multi_3d_y')

                                        z3 = st.selectbox('Z', options=list(cols_all), index=_safe_idx(2, len(cols_all)), key='compare_multi_3d_z')

                                        c3 = st.selectbox('Цвет', options=list(cols_all), index=_safe_idx(0, len(cols_all)), key='compare_multi_3d_color')


                                        keep_frac = st.slider(

                                            "Доля точек (облако 'тает')",

                                            0.05,

                                            1.0,

                                            float(st.session_state.get('compare_multi_3d_keepfrac') or 1.0),

                                            step=0.05,

                                            key='compare_multi_3d_keepfrac',

                                            help="Уменьшайте долю, чтобы видеть внутреннюю структуру и кластеры.",

                                        )

                                        keep_mode = st.radio(

                                            "Прореживание по плотности",

                                            options=["Сначала редкие (оболочка)", "Сначала плотные (ядро)"],

                                            index=0,

                                            key='compare_multi_3d_keepmode',

                                        )

                                        pt_size = st.slider('Размер точек', 2, 12, int(st.session_state.get('compare_multi_3d_size') or 5), key='compare_multi_3d_size')

                                        pt_op = st.slider('Прозрачность', 0.05, 1.0, float(st.session_state.get('compare_multi_3d_opacity') or 0.75), step=0.05, key='compare_multi_3d_opacity')


                                        # data

                                        arr = dfm_num[[x3, y3, z3, c3]].to_numpy(dtype=float)

                                        pts = arr[:, :3]


                                        # normalize to [0..1] for density

                                        pts01 = pts.copy()

                                        for k in range(3):

                                            v = pts01[:, k]

                                            mn, mx = np.nanmin(v), np.nanmax(v)

                                            if np.isfinite(mn) and np.isfinite(mx) and mx > mn:

                                                pts01[:, k] = (v - mn) / (mx - mn)

                                            else:

                                                pts01[:, k] = 0.0


                                        dens = _knn_density(pts01, k=5)

                                        n_all = len(dfm_num)

                                        keep_n3 = max(3, int(round(n_all * float(keep_frac))))

                                        order = np.argsort(dens)  # sparse first

                                        if str(keep_mode).startswith('Сначала плотные'):

                                            order = order[::-1]


                                        keep_idx = order[:keep_n3]

                                        df3 = dfm_num.iloc[keep_idx]


                                        # --- 'галька' (дискретные события) ---

                                        disc_opts = []

                                        try:

                                            df_ref_tbl = dict(bundles)[ref_label].get(table)

                                            if df_ref_tbl is not None:

                                                disc_opts = ev_detect_discrete_signals(df_ref_tbl)

                                        except Exception:

                                            disc_opts = []


                                        peb_runs = set()

                                        show_pebbles = False

                                        peb_sig = None

                                        peb_mode = 'occurred'


                                        if disc_opts:

                                            show_pebbles = st.checkbox(

                                                "Показывать 'гальку' по дискретному сигналу",

                                                value=bool(st.session_state.get('compare_multi_3d_pebbles', True)),

                                                key='compare_multi_3d_pebbles',

                                                help=(

                                                    "Крупные контрастные точки = прогон(ы), где событие срабатывало. "

                                                    "Это помогает увидеть пороги/области параметров, где включаются клапана/отрыв/пробой."

                                                ),

                                            )

                                            if show_pebbles:

                                                peb_sig = st.selectbox(

                                                    "Сигнал события",

                                                    options=disc_opts,

                                                    index=0,

                                                    key='compare_multi_3d_peb_sig',

                                                )

                                                peb_mode = st.radio(

                                                    "Критерий",

                                                    options=["Срабатывал в прогоне", "Активен в момент t"],

                                                    index=0,

                                                    key='compare_multi_3d_peb_mode',

                                                )


                                        if show_pebbles and peb_sig:

                                            t_cur = st.session_state.get('compare_click_t')

                                            t_cur = float(t_cur) if isinstance(t_cur, (int, float)) and np.isfinite(float(t_cur)) else float('nan')


                                            for lab, tdict in bundles:

                                                df_tbl = tdict.get(table)

                                                if df_tbl is None or peb_sig not in df_tbl.columns:

                                                    continue

                                                try:

                                                    x_e = extract_time_vector(df_tbl)

                                                    y_e = df_tbl[peb_sig].to_numpy(dtype=float)

                                                except Exception:

                                                    continue

                                                if y_e.size == 0:

                                                    continue

                                                y0 = float(y_e[0]) if np.isfinite(float(y_e[0])) else float('nan')

                                                occurred = (np.nanmin(y_e) != np.nanmax(y_e))

                                                if str(peb_mode).startswith('Срабатывал'):

                                                    if occurred:

                                                        peb_runs.add(lab)

                                                else:

                                                    if np.isfinite(t_cur):

                                                        v = _sample_nearest(x_e, y_e, t_cur)

                                                        if np.isfinite(v) and (not np.isfinite(y0) or v != y0):

                                                            peb_runs.add(lab)


                                        # --- build 3D ---

                                        fig3d = go.Figure()


                                        fig3d.add_trace(

                                            go.Scatter3d(

                                                x=df3[x3], y=df3[y3], z=df3[z3],

                                                mode='markers',

                                                marker=dict(size=pt_size, opacity=pt_op, color=df3[c3], colorscale='Viridis', showscale=True),

                                                text=df3['run'],

                                                hovertemplate=(

                                                    "run=%{text}<br>" +

                                                    f"{_trim_label(x3,24)}=%{{x:.6g}}<br>" +

                                                    f"{_trim_label(y3,24)}=%{{y:.6g}}<br>" +

                                                    f"{_trim_label(z3,24)}=%{{z:.6g}}<br>" +

                                                    f"{_trim_label(c3,24)}=%{{marker.color:.6g}}" +

                                                    "<extra></extra>"

                                                ),

                                                name='cloud',

                                            )

                                        )


                                        if show_pebbles and peb_runs:

                                            df_peb = dfm_num[dfm_num['run'].isin(sorted(peb_runs))]

                                            if len(df_peb) > 0:

                                                fig3d.add_trace(

                                                    go.Scatter3d(

                                                        x=df_peb[x3], y=df_peb[y3], z=df_peb[z3],

                                                        mode='markers',

                                                        marker=dict(size=max(pt_size + 4, 10), opacity=1.0, symbol='diamond',

                                                                    color='rgba(0,0,0,0.85)', line=dict(width=1, color='white')),

                                                        text=df_peb['run'],

                                                        hovertemplate="EVENT run=%{text}<extra></extra>",

                                                        name='event',

                                                    )

                                                )


                                        fig3d.update_layout(

                                            height=760,

                                            margin=dict(l=0, r=0, t=30, b=0),

                                            scene=dict(

                                                xaxis_title=_trim_label(x3, 26),

                                                yaxis_title=_trim_label(y3, 26),

                                                zaxis_title=_trim_label(z3, 26),

                                            ),

                                        )


                                        ev_3d = _st_plotly_select(fig3d, key='compare_multi_3d_plot')

                                        sel_runs_3d = _extract_selected_texts(ev_3d)

                                        if sel_runs_3d:

                                            st.session_state['compare_active_runs_pending_value'] = [r for r in sel_runs_3d if r in run_labels_all]

                                            st.success(f"Выделено прогонов: {len(sel_runs_3d)} (pending фильтр).")

        except Exception as e:
            st.warning(f"Influence (RMS) блок не построен: {e}")

    with tab_t:
        st.caption("Корреляция: meta (X) ↔ значение сигнала в момент времени t (playhead). Клик по ячейке даёт scatter ниже.")

        max_feat_t = st.slider(
            "Сколько параметров meta показывать (топ по силе влияния)",
            min_value=5, max_value=80, value=int(st.session_state.get("compare_infl_t_maxfeat", 30)),
            key="compare_infl_t_maxfeat",
            help="Чем меньше — тем читаемее. Обычно 20–40 достаточно для качественного анализа.",
        )

        show_trend = st.checkbox(
            "Показать тренд на scatter (линейная аппроксимация)",
            value=bool(st.session_state.get("compare_infl_t_trend", True)),
            key="compare_infl_t_trend",
            help="Показывает линию тренда (polyfit degree=1) для качественного понимания связи.",
        )

        try:
            if not _feat_names_all:
                st.info("В meta_json не найдено численных параметров → влияние считать не из чего.")
            elif len(bundles) < 3:
                st.info("Для корреляции нужно хотя бы 3 прогона (runs).")
            else:
                n_runs = len(bundles)
                n_sigs = len(sigs)
                if n_sigs == 0:
                    st.info("Сначала выберите хотя бы один сигнал (Signals).")
                else:
                    # Y: runs × signals (value at playhead)
                    t0 = float(t_play) if t_play is not None else 0.0
                    Y_t = np.full((n_runs, n_sigs), np.nan, dtype=float)

                    ref_tables2 = dict(bundles)[ref_label]
                    y_ref_at_t = np.full((n_sigs,), np.nan, dtype=float)
                    for j, sig in enumerate(sigs):
                        x_ref, y_ref, _unit = _get_xy(
                            ref_tables2, table, sig,
                            dist_unit=dist_unit, angle_unit=angle_unit, p_atm=float(p_atm),
                            zero_baseline=bool(zero_baseline), baseline_mode=str(baseline_mode),
                            baseline_window_s=float(baseline_window_s), baseline_first_n=int(baseline_first_n),
                            flow_unit=str(flow_unit),
                        )
                        if x_ref.size >= 2:
                            try:
                                y_ref_at_t[j] = float(np.interp(t0, x_ref, y_ref, left=np.nan, right=np.nan))
                            except Exception:
                                y_ref_at_t[j] = float("nan")

                    for i, (lab, tables) in enumerate(bundles):
                        for j, sig in enumerate(sigs):
                            x, y, _u = _get_xy(
                                tables, table, sig,
                                dist_unit=dist_unit, angle_unit=angle_unit, p_atm=float(p_atm),
                                zero_baseline=bool(zero_baseline), baseline_mode=str(baseline_mode),
                                baseline_window_s=float(baseline_window_s), baseline_first_n=int(baseline_first_n),
                                flow_unit=str(flow_unit),
                            )
                            if x.size >= 2:
                                try:
                                    v = float(np.interp(t0, x, y, left=np.nan, right=np.nan))
                                except Exception:
                                    v = float("nan")
                            elif y.size:
                                v = float(y[-1])
                            else:
                                v = float("nan")

                            if mode_delta:
                                # Δ к эталону в текущий момент
                                if lab == ref_label:
                                    v = 0.0
                                else:
                                    v = v - float(y_ref_at_t[j])
                            Y_t[i, j] = v

                    # X: runs × features (prefilter if нужно)
                    feat_names = list(_feat_names_all)
                    X_use = np.asarray(_X_all, dtype=float)

                    if len(feat_names) > 600:
                        keep0 = max(200, int(max_feat_t) * 8)
                        pref = prefilter_features_by_variance(X_use, feat_names, keep=keep0)
                        idx_map = {n: ii for ii, n in enumerate(feat_names)}
                        pref_idx = [idx_map[n] for n in pref if n in idx_map]
                        feat_names = [feat_names[ii] for ii in pref_idx]
                        X_use = X_use[:, pref_idx] if pref_idx else X_use

                    corr = _corr_matrix(X_use, Y_t, min_n=3)  # features × signals
                    feat_sorted = rank_features_by_max_abs_corr(corr, feat_names)
                    feat_sel = feat_sorted[: int(max_feat_t)]

                    if not feat_sel:
                        st.info("Не удалось выбрать параметры meta для отображения (возможно, все NaN/константы).")
                    else:
                        idx_map2 = {n: ii for ii, n in enumerate(feat_names)}
                        sel_idx = [idx_map2[n] for n in feat_sel if n in idx_map2]
                        corr_sel = corr[sel_idx, :] if sel_idx else corr

                        run_labels = [lab for lab, _ in bundles]

                        # ticks (trim) — чтобы подписи не налезали
                        y_ticktext = [_trim_label(n, 44) for n in feat_sel]
                        x_ticktext = [_trim_label(n, 42) for n in sigs]
                        x_angle = -35 if len(sigs) > 8 else 0

                        figt = go.Figure(
                            data=go.Heatmap(
                                z=corr_sel, x=sigs, y=feat_sel,
                                colorscale="RdBu", zmin=-1, zmax=1,
                                hovertemplate="meta=%{y}<br>sig=%{x}<br>corr=%{z:.3f}<extra></extra>",
                            )
                        )
                        figt.update_layout(
                            height=max(520, 20 * len(feat_sel) + 280),
                            margin=dict(l=260, r=20, t=40, b=110),
                            title=f"t = {t0:.4f} s",
                        )
                        figt.update_xaxes(ticktext=x_ticktext, tickvals=sigs, tickangle=x_angle, automargin=True)
                        figt.update_yaxes(ticktext=y_ticktext, tickvals=feat_sel, automargin=True)

                        ev_inf = _st_plotly_select(figt, key="compare_influence_t_heat")
                        xr, yr = _extract_first_xy_from_event(ev_inf)
                        if xr is not None and yr is not None:
                            try:
                                st.session_state["compare_infl_focus_sig"] = str(xr)
                                st.session_state["compare_infl_focus_feat"] = str(yr)
                                _rerun()
                            except Exception:
                                pass

                        st.caption(f"Meta параметров всего: {len(_feat_names_all)}. На карте показано: {len(feat_sel)}.")

                        with st.expander("Мультипараметрический Explorer (SPLOM / Parallel / 3D)", expanded=False):

                            st.caption(

                                "Быстрый качественный обзор взаимосвязей: meta‑параметры ↔ метрики (RMS/Δ). "

                                "Рекомендуемый путь: 1) heatmap корреляций → 2) SPLOM/Parallel → 3) 3D‑облако для обзора."

                            )


                            run_labels_all = [lab for lab, _td in bundles]


                            # --- выбор признаков ---

                            feat_default = list(st.session_state.get('compare_multi_feats') or feat_sel[: min(8, len(feat_sel))])

                            feat_multi = st.multiselect(

                                "Meta параметры (ось/анализ)",

                                options=list(feat_sel),

                                default=feat_default,

                                key='compare_multi_feats',

                                help=(

                                    "Это численные параметры из meta (включая параметры схемы/оптимизации). "

                                    "По умолчанию берём наиболее влияющие (по корреляции)."

                                ),

                            )


                            # --- выбор метрик (сигналы) ---

                            # score = средняя RMS (чтобы по умолчанию показывать наиболее 'живые' метрики)

                            try:

                                _ms = np.nanmean(np.abs(Y_rms), axis=0)

                                _ord = np.argsort(-_ms)

                                met_default = [met_names[i] for i in _ord[: min(10, len(met_names))]]

                            except Exception:

                                met_default = met_names[: min(10, len(met_names))]


                            met_multi = st.multiselect(

                                "Метрики (RMS по выбранным сигналам)",

                                options=list(met_names),

                                default=list(st.session_state.get('compare_multi_metrics') or met_default),

                                key='compare_multi_metrics',

                                help=(

                                    "Каждая метрика = RMS(сигнал) по текущим настройкам (Δ к ref/абсолют). "

                                    "Слишком много метрик ухудшает читаемость — начните с 6–12."

                                ),

                            )


                            cols_all = list(feat_multi) + list(met_multi)

                            if len(cols_all) < 2:

                                st.info("Выберите минимум 1 meta‑параметр и 1 метрику (или любые 2 оси).")

                            else:

                                # --- сбор df ---

                                dfm = pd.DataFrame({'run': run_labels_all})

                                # meta

                                for f in feat_multi:

                                    if f in idx_map2:

                                        dfm[f] = X_use[:, idx_map2[f]]

                                # metrics

                                met_idx_map = {n: j for j, n in enumerate(met_names)}

                                for m in met_multi:

                                    j = met_idx_map.get(m)

                                    if j is not None:

                                        dfm[m] = Y_rms[:, j]


                                # удаляем строки где нет данных по выбранным осям

                                dfm_num = dfm.dropna(subset=[c for c in cols_all if c in dfm.columns])


                                if len(dfm_num) < 3:

                                    st.warning("Недостаточно валидных точек (после удаления NaN) для мульти‑графиков.")

                                else:

                                    tab_m1, tab_m2, tab_m3 = st.tabs(["SPLOM", "Parallel", "3D облако"])


                                    # --- SPLOM ---

                                    with tab_m1:

                                        st.caption(

                                            "SPLOM (scatterplot matrix) быстро показывает нелинейности/кластеры/аномалии. "

                                            "Выделение точек (lasso/box) можно применить как фильтр прогонов (Compare filter сверху)."

                                        )


                                        max_dims = min(6, len(cols_all))

                                        dims_default = list(st.session_state.get('compare_multi_splom_dims') or cols_all[:max_dims])

                                        dims = st.multiselect(

                                            "Оси для SPLOM (до 6)",

                                            options=list(cols_all),

                                            default=dims_default,

                                            key='compare_multi_splom_dims',

                                            help="Рекомендация: 3–6 осей. Больше — перегруз восприятия.",

                                        )

                                        if len(dims) > 6:

                                            dims = list(dims)[:6]

                                            st.info("SPLOM ограничен 6 осями — лишнее отброшено.")


                                        color_candidates = list(met_multi) + [c for c in feat_multi if c not in met_multi]

                                        color_col = st.selectbox(

                                            "Цвет (градиент)",

                                            options=color_candidates,

                                            index=0,

                                            key='compare_multi_color',

                                            help="Цвет помогает увидеть области параметров, где метрика/сигнал резко меняется.",

                                        )


                                        # LOD

                                        keep_n = st.slider(

                                            "Сколько точек показывать (LOD)",

                                            min_value=3,

                                            max_value=int(max(3, len(dfm_num))),

                                            value=int(st.session_state.get('compare_multi_lod') or min(200, len(dfm_num))),

                                            step=1,

                                            key='compare_multi_lod',

                                            help="Уменьшайте, если график тяжёлый. Для 100–300 прогонов обычно OK.",

                                        )

                                        df_plot = dfm_num if keep_n >= len(dfm_num) else dfm_num.sample(n=int(keep_n), random_state=0)


                                        labels_map = {c: _trim_label(str(c), 22) for c in dims}

                                        fig_splom = px.scatter_matrix(

                                            df_plot,

                                            dimensions=dims,

                                            color=color_col,

                                            hover_name='run',

                                            labels=labels_map,

                                        )

                                        fig_splom.update_traces(diagonal_visible=False, marker=dict(size=6, opacity=0.65))

                                        fig_splom.update_layout(height=760, margin=dict(l=40, r=20, t=40, b=40))


                                        ev_sel = _st_plotly_select(fig_splom, key='compare_multi_splom_plot')

                                        sel_runs = _extract_selected_texts(ev_sel)

                                        if sel_runs:

                                            # сохраним как pending — пользователь может применить сверху через сравнение

                                            st.session_state['compare_active_runs_pending_value'] = [r for r in sel_runs if r in run_labels_all]

                                            st.success(f"Выделено прогонов: {len(sel_runs)} (pending фильтр).")


                                    # --- Parallel coordinates ---

                                    with tab_m2:

                                        st.caption(

                                            "Parallel coordinates (параллельные координаты) полезны, когда параметров много: "

                                            "видно, какие комбинации дают хорошие/плохие метрики. "

                                            "Это качественный обзор — затем уточняйте через heatmap и графики во времени."

                                        )


                                        dims_pc_default = list(st.session_state.get('compare_multi_par_dims') or cols_all[: min(10, len(cols_all))])

                                        dims_pc = st.multiselect(

                                            "Оси для parallel (рекомендовано 6–12)",

                                            options=list(cols_all),

                                            default=dims_pc_default,

                                            key='compare_multi_par_dims',

                                        )

                                        if len(dims_pc) < 2:

                                            st.info("Выберите минимум 2 оси.")

                                        else:

                                            labels_map2 = {c: _trim_label(str(c), 22) for c in dims_pc}

                                            fig_pc = px.parallel_coordinates(

                                                dfm_num,

                                                dimensions=dims_pc,

                                                color=color_col,

                                                labels=labels_map2,

                                            )

                                            fig_pc.update_layout(height=760, margin=dict(l=40, r=20, t=40, b=40))

                                            _st_plotly(fig_pc, key='compare_multi_parcoords_plot')


                                    # --- 3D cloud ---

                                    with tab_m3:

                                        st.caption(

                                            "3D используется для качественного обзора (вращение мышью). "

                                            "Чтобы не получить 'тёмный блин' — включено прореживание по плотности. "

                                            "Для строгих выводов используйте 2D heatmaps/корреляции."

                                        )


                                        def _safe_idx(i: int, n: int) -> int:

                                            return 0 if n <= 0 else max(0, min(i, n - 1))


                                        x3 = st.selectbox('X', options=list(cols_all), index=_safe_idx(0, len(cols_all)), key='compare_multi_3d_x')

                                        y3 = st.selectbox('Y', options=list(cols_all), index=_safe_idx(1, len(cols_all)), key='compare_multi_3d_y')

                                        z3 = st.selectbox('Z', options=list(cols_all), index=_safe_idx(2, len(cols_all)), key='compare_multi_3d_z')

                                        c3 = st.selectbox('Цвет', options=list(cols_all), index=_safe_idx(0, len(cols_all)), key='compare_multi_3d_color')


                                        keep_frac = st.slider(

                                            "Доля точек (облако 'тает')",

                                            0.05,

                                            1.0,

                                            float(st.session_state.get('compare_multi_3d_keepfrac') or 1.0),

                                            step=0.05,

                                            key='compare_multi_3d_keepfrac',

                                            help="Уменьшайте долю, чтобы видеть внутреннюю структуру и кластеры.",

                                        )

                                        keep_mode = st.radio(

                                            "Прореживание по плотности",

                                            options=["Сначала редкие (оболочка)", "Сначала плотные (ядро)"],

                                            index=0,

                                            key='compare_multi_3d_keepmode',

                                        )

                                        pt_size = st.slider('Размер точек', 2, 12, int(st.session_state.get('compare_multi_3d_size') or 5), key='compare_multi_3d_size')

                                        pt_op = st.slider('Прозрачность', 0.05, 1.0, float(st.session_state.get('compare_multi_3d_opacity') or 0.75), step=0.05, key='compare_multi_3d_opacity')


                                        # data

                                        arr = dfm_num[[x3, y3, z3, c3]].to_numpy(dtype=float)

                                        pts = arr[:, :3]


                                        # normalize to [0..1] for density

                                        pts01 = pts.copy()

                                        for k in range(3):

                                            v = pts01[:, k]

                                            mn, mx = np.nanmin(v), np.nanmax(v)

                                            if np.isfinite(mn) and np.isfinite(mx) and mx > mn:

                                                pts01[:, k] = (v - mn) / (mx - mn)

                                            else:

                                                pts01[:, k] = 0.0


                                        dens = _knn_density(pts01, k=5)

                                        n_all = len(dfm_num)

                                        keep_n3 = max(3, int(round(n_all * float(keep_frac))))

                                        order = np.argsort(dens)  # sparse first

                                        if str(keep_mode).startswith('Сначала плотные'):

                                            order = order[::-1]


                                        keep_idx = order[:keep_n3]

                                        df3 = dfm_num.iloc[keep_idx]


                                        # --- 'галька' (дискретные события) ---

                                        disc_opts = []

                                        try:

                                            df_ref_tbl = dict(bundles)[ref_label].get(table)

                                            if df_ref_tbl is not None:

                                                disc_opts = ev_detect_discrete_signals(df_ref_tbl)

                                        except Exception:

                                            disc_opts = []


                                        peb_runs = set()

                                        show_pebbles = False

                                        peb_sig = None

                                        peb_mode = 'occurred'


                                        if disc_opts:

                                            show_pebbles = st.checkbox(

                                                "Показывать 'гальку' по дискретному сигналу",

                                                value=bool(st.session_state.get('compare_multi_3d_pebbles', True)),

                                                key='compare_multi_3d_pebbles',

                                                help=(

                                                    "Крупные контрастные точки = прогон(ы), где событие срабатывало. "

                                                    "Это помогает увидеть пороги/области параметров, где включаются клапана/отрыв/пробой."

                                                ),

                                            )

                                            if show_pebbles:

                                                peb_sig = st.selectbox(

                                                    "Сигнал события",

                                                    options=disc_opts,

                                                    index=0,

                                                    key='compare_multi_3d_peb_sig',

                                                )

                                                peb_mode = st.radio(

                                                    "Критерий",

                                                    options=["Срабатывал в прогоне", "Активен в момент t"],

                                                    index=0,

                                                    key='compare_multi_3d_peb_mode',

                                                )


                                        if show_pebbles and peb_sig:

                                            t_cur = st.session_state.get('compare_click_t')

                                            t_cur = float(t_cur) if isinstance(t_cur, (int, float)) and np.isfinite(float(t_cur)) else float('nan')


                                            for lab, tdict in bundles:

                                                df_tbl = tdict.get(table)

                                                if df_tbl is None or peb_sig not in df_tbl.columns:

                                                    continue

                                                try:

                                                    x_e = extract_time_vector(df_tbl)

                                                    y_e = df_tbl[peb_sig].to_numpy(dtype=float)

                                                except Exception:

                                                    continue

                                                if y_e.size == 0:

                                                    continue

                                                y0 = float(y_e[0]) if np.isfinite(float(y_e[0])) else float('nan')

                                                occurred = (np.nanmin(y_e) != np.nanmax(y_e))

                                                if str(peb_mode).startswith('Срабатывал'):

                                                    if occurred:

                                                        peb_runs.add(lab)

                                                else:

                                                    if np.isfinite(t_cur):

                                                        v = _sample_nearest(x_e, y_e, t_cur)

                                                        if np.isfinite(v) and (not np.isfinite(y0) or v != y0):

                                                            peb_runs.add(lab)


                                        # --- build 3D ---

                                        fig3d = go.Figure()


                                        fig3d.add_trace(

                                            go.Scatter3d(

                                                x=df3[x3], y=df3[y3], z=df3[z3],

                                                mode='markers',

                                                marker=dict(size=pt_size, opacity=pt_op, color=df3[c3], colorscale='Viridis', showscale=True),

                                                text=df3['run'],

                                                hovertemplate=(

                                                    "run=%{text}<br>" +

                                                    f"{_trim_label(x3,24)}=%{{x:.6g}}<br>" +

                                                    f"{_trim_label(y3,24)}=%{{y:.6g}}<br>" +

                                                    f"{_trim_label(z3,24)}=%{{z:.6g}}<br>" +

                                                    f"{_trim_label(c3,24)}=%{{marker.color:.6g}}" +

                                                    "<extra></extra>"

                                                ),

                                                name='cloud',

                                            )

                                        )


                                        if show_pebbles and peb_runs:

                                            df_peb = dfm_num[dfm_num['run'].isin(sorted(peb_runs))]

                                            if len(df_peb) > 0:

                                                fig3d.add_trace(

                                                    go.Scatter3d(

                                                        x=df_peb[x3], y=df_peb[y3], z=df_peb[z3],

                                                        mode='markers',

                                                        marker=dict(size=max(pt_size + 4, 10), opacity=1.0, symbol='diamond',

                                                                    color='rgba(0,0,0,0.85)', line=dict(width=1, color='white')),

                                                        text=df_peb['run'],

                                                        hovertemplate="EVENT run=%{text}<extra></extra>",

                                                        name='event',

                                                    )

                                                )


                                        fig3d.update_layout(

                                            height=760,

                                            margin=dict(l=0, r=0, t=30, b=0),

                                            scene=dict(

                                                xaxis_title=_trim_label(x3, 26),

                                                yaxis_title=_trim_label(y3, 26),

                                                zaxis_title=_trim_label(z3, 26),

                                            ),

                                        )


                                        ev_3d = _st_plotly_select(fig3d, key='compare_multi_3d_plot')

                                        sel_runs_3d = _extract_selected_texts(ev_3d)

                                        if sel_runs_3d:

                                            st.session_state['compare_active_runs_pending_value'] = [r for r in sel_runs_3d if r in run_labels_all]

                                            st.success(f"Выделено прогонов: {len(sel_runs_3d)} (pending фильтр).")

                        # Top cells table
                        try:
                            tops = top_cells(corr_sel, feat_sel, list(sigs), top_k=12)
                            if tops:
                                df_top = pd.DataFrame(tops, columns=["meta", "signal", "corr"])
                                df_top["|corr|"] = df_top["corr"].abs()
                                st.dataframe(df_top, width="stretch", hide_index=True)
                        except Exception:
                            pass

                        # Detail scatter (meta vs signal at t)
                        feat_focus = st.session_state.get("compare_infl_focus_feat")
                        sig_focus = st.session_state.get("compare_infl_focus_sig")

                        if not feat_focus or feat_focus not in feat_sel:
                            feat_focus = feat_sel[0]
                        if not sig_focus or sig_focus not in sigs:
                            sig_focus = sigs[0]

                        ii = feat_names.index(feat_focus) if feat_focus in feat_names else None
                        jj = list(sigs).index(sig_focus) if sig_focus in sigs else None

                        if ii is not None and jj is not None:
                            x_feat = X_use[:, ii]
                            y_sig = Y_t[:, jj]

                            m = np.isfinite(x_feat) & np.isfinite(y_sig)
                            if int(m.sum()) >= 3:
                                c = float(np.corrcoef(x_feat[m], y_sig[m])[0, 1])
                            else:
                                c = float("nan")

                            fig_sc = go.Figure()
                            fig_sc.add_trace(
                                go.Scatter(
                                    x=x_feat, y=y_sig, mode="markers",
                                    text=run_labels,
                                    hovertemplate="run=%{text}<br>x=%{x:.4g}<br>y=%{y:.4g}<extra></extra>",
                                    name="runs",
                                )
                            )

                            if show_trend and int(m.sum()) >= 3:
                                try:
                                    coef = np.polyfit(x_feat[m], y_sig[m], 1)
                                    xs = np.linspace(float(np.nanmin(x_feat[m])), float(np.nanmax(x_feat[m])), 120)
                                    ys = coef[0] * xs + coef[1]
                                    fig_sc.add_trace(
                                        go.Scatter(
                                            x=xs, y=ys, mode="lines",
                                            name="trend (linear)",
                                            hoverinfo="skip",
                                        )
                                    )
                                except Exception:
                                    pass

                            xlab = _wrap_label(str(feat_focus), width=34, max_lines=2)
                            ylab = _wrap_label(str(sig_focus), width=34, max_lines=2)
                            fig_sc.update_layout(
                                height=520,
                                margin=dict(l=60, r=20, t=60, b=60),
                                title=f"Scatter: meta → signal @ t={t0:.4f}s (corr={c:.3f} если доступно)",
                                dragmode="lasso",
                            )
                            fig_sc.update_xaxes(title_text=xlab, automargin=True)
                            fig_sc.update_yaxes(title_text=ylab, automargin=True)

                            ev_sc = _st_plotly_select(fig_sc, key="compare_influence_t_scatter", mode='rerun')

                            # Linked brushing: selection of points → active runs filter
                            if bool(st.session_state.get('compare_linked_brushing', True)):
                                picked_runs = _extract_selected_texts(ev_sc)
                                if picked_runs:
                                    st.session_state['compare_active_runs_pending_value'] = picked_runs
                                    st.session_state['compare_active_runs_pending'] = True
                                    _rerun()

                            # Influence(t) HEATMAP PLAYER (анимация по времени)
                            with st.expander("Influence(t) heatmap player (анимация)", expanded=False):
                                st.caption(
                                    "Показывает, как меняется корреляция meta → signal по времени. "
                                    "Это качественный инструмент: при малом числе прогонов корреляции шумные. "
                                    "Используйте LOD-ползунки, чтобы держать график читаемым и быстрым."
                                )
                                show_infl_anim = st.checkbox(
                                    "Показать Influence(t) плеер",
                                    key="compare_infl_anim_show",
                                    help=(
                                        "Строит 3D-куб corr(t, meta, signal) и показывает анимированную heatmap. "
                                        "Рекомендуется: 12–30 meta × 6–12 signal × 60–140 кадров."
                                    ),
                                )
                                if show_infl_anim:
                                    colA, colB, colC, colD = st.columns([1, 1, 1, 1])
                                    with colA:
                                        max_frames = st.slider(
                                            "Кадров (frames)",
                                            20,
                                            240,
                                            value=int(st.session_state.get("compare_infl_anim_frames", 120)),
                                            step=10,
                                            key="compare_infl_anim_frames",
                                        )
                                    with colB:
                                        max_time_points = st.slider(
                                            "Max точек по времени (LOD)",
                                            200,
                                            10000,
                                            value=int(st.session_state.get("compare_infl_anim_tpts", 2000)),
                                            step=200,
                                            key="compare_infl_anim_tpts",
                                        )
                                    with colC:
                                        max_feat_anim = st.slider(
                                            "Meta параметров (N)",
                                            6,
                                            60,
                                            value=min(int(st.session_state.get("compare_infl_anim_maxfeat", 24)), len(feat_sel)),
                                            step=1,
                                            key="compare_infl_anim_maxfeat",
                                        )
                                    with colD:
                                        max_sig_anim = st.slider(
                                            "Сигналов (N)",
                                            2,
                                            max(2, min(20, len(sigs))),
                                            value=min(int(st.session_state.get("compare_infl_anim_maxsig", 12)), len(sigs)),
                                            step=1,
                                            key="compare_infl_anim_maxsig",
                                        )

                                    sigs_anim = list(sigs)[: int(max_sig_anim)]
                                    feat_anim = list(feat_sel)[: int(max_feat_anim)]

                                    # Align X columns to selected feature names
                                    feat_to_idx = {n: i for i, n in enumerate(feat_names)}
                                    idx_anim = [feat_to_idx.get(n, None) for n in feat_anim]
                                    idx_anim = [i for i in idx_anim if i is not None]

                                    if len(idx_anim) < 1 or len(sigs_anim) < 1:
                                        st.warning("Недостаточно данных для Influence(t) (нужны meta и сигналы).")
                                    else:
                                        X_anim = X_use[:, idx_anim]

                                        # simple in-session cache to avoid recompute on every rerun
                                        try:
                                            sig_payload = {
                                                "paths": [
                                                    {
                                                        "p": str(p),
                                                        "m": int(os.path.getmtime(p)) if os.path.exists(p) else 0,
                                                        "s": int(os.path.getsize(p)) if os.path.exists(p) else 0,
                                                    }
                                                    for p in run_paths
                                                ],
                                                "table": str(table),
                                                "sigs": sigs_anim,
                                                "feat": feat_anim,
                                                "mode": "delta" if mode_delta else "value",
                                                "dist": str(dist_unit),
                                                "angle": str(angle_unit),
                                                "baseline": {
                                                    "mode": str(baseline_mode),
                                                    "win": float(baseline_window_s),
                                                    "n": int(baseline_first_n),
                                                    "zero": bool(zero_positions),
                                                },
                                                "flow": str(flow_unit),
                                                "p_atm": float(P_ATM),
                                                "tw": list(time_window) if time_window else None,
                                                "tpts": int(max_time_points),
                                                "frames": int(max_frames),
                                            }
                                            sig_key = hashlib.sha1(
                                                json.dumps(sig_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
                                            ).hexdigest()
                                        except Exception:
                                            sig_key = None

                                        cube_obj = None
                                        cache = st.session_state.get("compare_infl_anim_cache")
                                        if isinstance(cache, dict) and sig_key and cache.get("sig") == sig_key:
                                            cube_obj = cache.get("cube")

                                        if cube_obj is None:
                                            cube_obj = build_influence_t_cube(
                                                run_tuples,
                                                X=X_anim,
                                                feat_names=feat_anim,
                                                table=table,
                                                sigs=sigs_anim,
                                                ref_label=ref_label,
                                                mode="delta" if mode_delta else "value",
                                                dist_unit=dist_unit,
                                                angle_unit=angle_unit,
                                                p_atm=P_ATM,
                                                baseline_mode=baseline_mode,
                                                baseline_window_s=baseline_window_s,
                                                baseline_first_n=baseline_first_n,
                                                zero_positions=zero_positions,
                                                flow_unit=flow_unit,
                                                time_window=time_window,
                                                max_time_points=max_time_points,
                                                max_frames=max_frames,
                                            )
                                            if sig_key:
                                                st.session_state["compare_infl_anim_cache"] = {"sig": sig_key, "cube": cube_obj}

                                        if cube_obj is None or cube_obj.t.size < 2 or cube_obj.cube.size == 0:
                                            st.warning("Influence(t) куб пустой (проверьте сигналы/окно времени).")
                                        else:
                                            fig_anim = _build_influence_cube_anim_fig(
                                                t=cube_obj.t,
                                                cube=cube_obj.cube,
                                                feat_names=cube_obj.feat_names,
                                                sigs=cube_obj.sigs,
                                                title_prefix=(
                                                    "Influence(t), Δ vs ref" if mode_delta else "Influence(t), value"
                                                ),
                                            )
                                            safe_plotly(fig_anim, key="compare_infl_anim_fig", height=560)

                                            # corr(t) for current focused pair (helps find thresholds / regime switches)
                                            if (focus_feat in feat_anim) and (focus_sig in sigs_anim):
                                                fi = feat_anim.index(focus_feat)
                                                si = sigs_anim.index(focus_sig)
                                                c_t = np.asarray(cube_obj.cube[:, fi, si], dtype=float)
                                                fig_ct = go.Figure()
                                                fig_ct.add_trace(
                                                    go.Scatter(x=cube_obj.t, y=c_t, mode="lines", name="corr(t)")
                                                )
                                                fig_ct.add_hline(y=0.0, line_dash="dot")
                                                fig_ct.update_layout(
                                                    title=f"corr(t) для пары: {focus_feat} → {focus_sig}",
                                                    height=320,
                                                    margin=dict(l=50, r=20, t=50, b=40),
                                                    xaxis_title="t, s",
                                                    yaxis_title="corr",
                                                    yaxis=dict(range=[-1.05, 1.05], automargin=True),
                                                )
                                                ev_ct = _st_plotly_select(fig_ct, key="compare_infl_corr_t")
                                                tt = _extract_first_xy_from_event(ev_ct)[0]
                                                if tt is not None and np.isfinite(tt):
                                                    st.session_state["compare_playhead"] = float(tt)
                                                    _rerun()



        except Exception as e:
            st.warning(f"Influence (t) блок не построен: {e}")
