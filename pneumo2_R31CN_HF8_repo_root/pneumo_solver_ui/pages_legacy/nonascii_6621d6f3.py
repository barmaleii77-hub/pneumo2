# ORIGINAL_FILENAME: 06_╨í╤Ç╨░╨▓╨╜╨╡╨╜╨╕╨╡_NPZ_╨Æ╨╡╨▒.py
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)


from pneumo_solver_ui.compare_ui import (

    detect_time_col,
    extract_time_vector,
    load_npz_bundle,
    _infer_unit_and_transform,
)


# -------------------------
# Helpers
# -------------------------

def _repo_root() -> Path:
    # .../pneumo_solver_ui/pages/<this_file>
    return Path(__file__).resolve().parents[2]


def _default_npz_dirs() -> List[Path]:
    root = _repo_root()
    ui = root / "pneumo_solver_ui"
    cands = [
        ui / "workspace" / "exports",
        ui / "workspace" / "osc",
        root / "workspace" / "exports",
        root / "workspace" / "osc",
    ]
    out = []
    for p in cands:
        if p.exists() and p.is_dir():
            out.append(p)
    # de-dup while preserving order
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


@st.cache_data(show_spinner=False)
def _load_npz(path_str: str) -> Dict:
    return load_npz_bundle(path_str)


def _is_pos_like_unit(unit: str) -> bool:
    u = (unit or "").lower().strip()
    return u in {"m", "mm", "deg", "rad"}


def _baseline_zero(x: np.ndarray, y: np.ndarray, window_s: float) -> np.ndarray:
    if y.size == 0:
        return y
    y0 = float(y[0])
    try:
        w = float(window_s or 0.0)
        if w > 0 and x.size == y.size:
            x0 = float(x[0])
            mask = x <= (x0 + w)
            if np.any(mask):
                y0 = float(np.nanmedian(y[mask]))
    except Exception:
        pass
    if np.isfinite(y0):
        return y - y0
    return y


def _get_xy(
    bundle: Dict,
    table: str,
    sig: str,
    *,
    dist_unit: str,
    angle_unit: str,
    P_ATM: float,
    BAR_PA: float,
    zero_baseline: bool,
    baseline_window_s: float,
) -> Tuple[np.ndarray, np.ndarray, str]:
    df = bundle.get(table)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return np.asarray([], dtype=float), np.asarray([], dtype=float), ""

    tcol = detect_time_col(df)
    x = extract_time_vector(df, tcol)
    if sig not in df.columns:
        return x, np.asarray([], dtype=float), ""

    y = np.asarray(df[sig].values, dtype=float)

    unit, tr = _infer_unit_and_transform(
        sig,
        P_ATM=P_ATM,
        BAR_PA=BAR_PA,
        dist_unit=dist_unit,
        angle_unit=angle_unit,
    )

    try:
        if callable(tr):
            y = np.asarray(tr(y), dtype=float)
    except Exception:
        pass

    if zero_baseline and _is_pos_like_unit(unit):
        y = _baseline_zero(x, y, baseline_window_s)

    return x, y, unit


def _fig_compare(
    runs: List[Tuple[str, Dict]],
    table: str,
    sigs: List[str],
    *,
    mode_delta: bool,
    ref_label: str,
    dist_unit: str,
    angle_unit: str,
    P_ATM: float,
    BAR_PA: float,
    zero_baseline: bool,
    baseline_window_s: float,
    lock_y: bool,
    lock_y_by_unit: bool,
    sym_y: bool,
    idx_play: int,
    x_range: Optional[Tuple[float, float]] = None,
) -> Tuple[go.Figure, Dict[str, Tuple[str, float, float]]]:
    # Reference
    ref_bundle = dict(runs)[ref_label]

    # Precompute for ranges
    sig_ranges: Dict[str, Tuple[str, float, float]] = {}

    # Figure layout
    fig = make_subplots(
        rows=len(sigs),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
    )

    # For unit-wide locking
    unit_ranges: Dict[str, Tuple[float, float]] = {}

    # We also need reference x-grid per signal for delta; to keep UI consistent,
    # we interpolate everything to the reference time for that signal.
    for r_i, sig in enumerate(sigs, start=1):
        x_ref, y_ref, unit = _get_xy(
            ref_bundle,
            table,
            sig,
            dist_unit=dist_unit,
            angle_unit=angle_unit,
            P_ATM=P_ATM,
            BAR_PA=BAR_PA,
            zero_baseline=zero_baseline,
            baseline_window_s=baseline_window_s,
        )

        y_all = []

        # Reference trace
        if x_ref.size and y_ref.size:
            if mode_delta and len(runs) > 1:
                y0 = np.zeros_like(y_ref)
                fig.add_trace(
                    go.Scatter(
                        x=x_ref,
                        y=y0,
                        mode="lines",
                        name=f"0 ({ref_label})",
                        legendgroup=ref_label,
                        line=dict(width=1),
                    ),
                    row=r_i,
                    col=1,
                )
                y_all.append(y0)
            else:
                fig.add_trace(
                    go.Scatter(
                        x=x_ref,
                        y=y_ref,
                        mode="lines",
                        name=ref_label,
                        legendgroup=ref_label,
                        line=dict(width=2),
                    ),
                    row=r_i,
                    col=1,
                )
                y_all.append(y_ref)

        # Other runs
        for j, (lbl, bun) in enumerate(runs):
            if lbl == ref_label:
                continue
            x, y, unit2 = _get_xy(
                bun,
                table,
                sig,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=P_ATM,
                BAR_PA=BAR_PA,
                zero_baseline=zero_baseline,
                baseline_window_s=baseline_window_s,
            )
            if not x.size or not y.size:
                continue

            if mode_delta and x_ref.size and y_ref.size and len(runs) > 1:
                try:
                    y_i = np.interp(x_ref, x, y, left=np.nan, right=np.nan)
                    y_d = y_i - y_ref
                except Exception:
                    y_d = y
                    x_ref = x
                fig.add_trace(
                    go.Scatter(
                        x=x_ref,
                        y=y_d,
                        mode="lines",
                        name=f"Δ {lbl}-{ref_label}",
                        legendgroup=lbl,
                        line=dict(width=1, dash="dash"),
                    ),
                    row=r_i,
                    col=1,
                )
                y_all.append(y_d)
            else:
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="lines",
                        name=lbl,
                        legendgroup=lbl,
                        line=dict(width=1),
                    ),
                    row=r_i,
                    col=1,
                )
                y_all.append(y)
            if unit2:
                unit = unit2

        # Ranges
        try:
            ycat = np.concatenate([np.asarray(a, dtype=float).ravel() for a in y_all if a is not None and np.asarray(a).size])
            ycat = ycat[np.isfinite(ycat)]
            if ycat.size:
                ymin = float(np.nanmin(ycat))
                ymax = float(np.nanmax(ycat))
            else:
                ymin = np.nan
                ymax = np.nan
        except Exception:
            ymin = np.nan
            ymax = np.nan

        sig_ranges[sig] = (unit, ymin, ymax)
        if lock_y_by_unit and np.isfinite(ymin) and np.isfinite(ymax):
            key = unit or sig
            lo, hi = unit_ranges.get(key, (ymin, ymax))
            unit_ranges[key] = (min(lo, ymin), max(hi, ymax))

        # Axis labels
        ylabel = sig
        if unit:
            ylabel = f"{sig} [{unit}]"
        fig.update_yaxes(title_text=ylabel, row=r_i, col=1)

        # Apply y range now if only per-signal lock
        if lock_y and not lock_y_by_unit and np.isfinite(ymin) and np.isfinite(ymax):
            lo, hi = ymin, ymax
            if sym_y:
                m = max(abs(lo), abs(hi))
                if not np.isfinite(m) or m == 0:
                    m = 1.0
                lo, hi = -m, m
            if lo == hi:
                d = max(1e-9, abs(lo) * 0.05)
                lo -= d
                hi += d
            pad = 0.02 * (hi - lo)
            fig.update_yaxes(range=[lo - pad, hi + pad], row=r_i, col=1)

    # Apply y ranges by unit (after all subplots)
    if lock_y_by_unit and unit_ranges:
        for r_i, sig in enumerate(sigs, start=1):
            unit, ymin, ymax = sig_ranges.get(sig, ("", np.nan, np.nan))
            key = unit or sig
            lo, hi = unit_ranges.get(key, (ymin, ymax))
            if np.isfinite(lo) and np.isfinite(hi):
                if sym_y:
                    m = max(abs(lo), abs(hi))
                    if not np.isfinite(m) or m == 0:
                        m = 1.0
                    lo, hi = -m, m
                if lo == hi:
                    d = max(1e-9, abs(lo) * 0.05)
                    lo -= d
                    hi += d
                pad = 0.02 * (hi - lo)
                fig.update_yaxes(range=[lo - pad, hi + pad], row=r_i, col=1)

    # Global layout
    fig.update_layout(
        height=min(2400, 240 + 220 * max(1, len(sigs))),
        margin=dict(l=30, r=15, t=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
        hovermode="x unified",
    )

    # X-range + playhead
    if x_ref.size:
        idx = int(np.clip(idx_play, 0, max(0, len(x_ref) - 1)))
        x_play = float(x_ref[idx]) if len(x_ref) else 0.0
        fig.add_vline(x=x_play, line_width=1, line_dash="dot")

        if x_range is not None:
            fig.update_xaxes(range=list(x_range))

    fig.update_xaxes(title_text="t [s]", row=len(sigs), col=1)

    return fig, sig_ranges


def _delta_heatmap(
    runs: List[Tuple[str, Dict]],
    table: str,
    sigs: List[str],
    *,
    ref_label: str,
    dist_unit: str,
    angle_unit: str,
    P_ATM: float,
    BAR_PA: float,
    zero_baseline: bool,
    baseline_window_s: float,
) -> Tuple[pd.DataFrame, go.Figure]:
    ref_bundle = dict(runs)[ref_label]

    z = []
    row_labels = []

    for lbl, bun in runs:
        row_labels.append(lbl)
        row = []
        for sig in sigs:
            x_ref, y_ref, _unit = _get_xy(
                ref_bundle,
                table,
                sig,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=P_ATM,
                BAR_PA=BAR_PA,
                zero_baseline=zero_baseline,
                baseline_window_s=baseline_window_s,
            )
            x, y, _u2 = _get_xy(
                bun,
                table,
                sig,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                P_ATM=P_ATM,
                BAR_PA=BAR_PA,
                zero_baseline=zero_baseline,
                baseline_window_s=baseline_window_s,
            )
            if not x_ref.size or not y_ref.size or not x.size or not y.size:
                row.append(np.nan)
                continue
            try:
                y_i = np.interp(x_ref, x, y, left=np.nan, right=np.nan)
                d = y_i - y_ref
                row.append(float(np.nanmax(np.abs(d))))
            except Exception:
                row.append(np.nan)
        z.append(row)

    df = pd.DataFrame(z, index=row_labels, columns=sigs)

    fig = go.Figure(
        data=go.Heatmap(
            z=df.values,
            x=df.columns,
            y=df.index,
            colorbar=dict(title="max |Δ|"),
        )
    )
    fig.update_layout(
        height=min(900, 220 + 26 * max(1, len(runs))),
        margin=dict(l=30, r=15, t=30, b=30),
    )
    return df, fig


# -------------------------
# Page
# -------------------------

safe_set_page_config(page_title="Сравнение NPZ (Web)", layout="wide")

st.title("Сравнение NPZ (Web): сравнительные диаграммы (overlay/Δ), одинаковые шкалы")

# Sidebar controls
with st.sidebar:
    st.header("Данные")
    default_dirs = _default_npz_dirs()
    dir_choice = st.selectbox(
        "Папка с .npz",
        options=[str(p) for p in default_dirs] + ["(другая папка)"] if default_dirs else ["(другая папка)"],
        index=0 if default_dirs else 0,
    )
    if dir_choice == "(другая папка)":
        dir_path = st.text_input("Путь", value=str(default_dirs[0] if default_dirs else _repo_root()))
    else:
        dir_path = dir_choice

    p_dir = Path(dir_path).expanduser().resolve() if dir_path else None
    if not p_dir or not p_dir.exists():
        st.error("Папка не найдена")
        st.stop()

    npz_files = sorted([p for p in p_dir.glob("*.npz") if p.is_file()])
    if not npz_files:
        st.warning("В выбранной папке нет .npz файлов")
        st.stop()

    labels = [f.name for f in npz_files]
    chosen = st.multiselect("Выберите прогоны", options=labels, default=labels[: min(2, len(labels))])
    if not chosen:
        st.stop()

    chosen_map = {lab: npz_files[labels.index(lab)] for lab in chosen}

    # Load selected bundles
    bundles = []
    for lab, path in chosen_map.items():
        try:
            bun = _load_npz(str(path))
            bundles.append((lab, bun))
        except Exception as e:
            st.error(f"Не удалось загрузить {lab}: {e}")

    if not bundles:
        st.stop()

    # Table selection (intersection)
    tables = None
    for _, bun in bundles:
        keys = {k for k, v in bun.items() if isinstance(v, pd.DataFrame)}
        tables = keys if tables is None else (tables & keys)
    tables = sorted(list(tables or []))
    if not tables:
        st.error("В выбранных .npz нет таблиц")
        st.stop()

    table = st.selectbox("Таблица", options=tables, index=0)

    st.header("Отображение")
    mode = st.radio("Режим", options=["Overlay", "Δ to reference"], index=0)
    mode_delta = mode.startswith("Δ")

    ref_label = st.selectbox("Reference run", options=[lab for lab, _ in bundles], index=0)

    dist_unit = st.selectbox("Ед. расстояний", options=["mm", "m"], index=0)
    angle_unit = st.selectbox("Ед. углов", options=["deg", "rad"], index=0)

    zero_baseline = st.checkbox("Нулевая базовая поза (позиции/углы)", value=True)
    baseline_window_s = st.number_input("Окно базы (медиана), s", min_value=0.0, max_value=5.0, value=0.0, step=0.05)

    lock_y = st.checkbox("Одинаковая шкала Y (по сигналу)", value=True)
    lock_y_by_unit = st.checkbox("Одинаковая шкала Y (по единице)", value=False)
    sym_y = st.checkbox("Симметрия Y вокруг 0", value=True)

    st.header("Параметры давления")
    P_ATM = st.number_input("P_ATM, Pa", min_value=0.0, value=100000.0, step=1000.0)
    BAR_PA = st.number_input("Pa на 1 bar", min_value=1.0, value=100000.0, step=1000.0)

# Signal list in main area
ref_bundle = dict(bundles)[ref_label]
df_ref = ref_bundle.get(table)
if df_ref is None or not isinstance(df_ref, pd.DataFrame) or df_ref.empty:
    st.error("Reference таблица пустая")
    st.stop()

# Determine time and available signals
try:
    tcol = detect_time_col(df_ref)
except Exception:
    tcol = df_ref.columns[0]

cols = [c for c in df_ref.columns if c != tcol]

# Filter + choose signals
c1, c2 = st.columns([2, 1])
with c2:
    filt = st.text_input("Фильтр сигналов", value="")

fcols = [c for c in cols if (filt.lower() in c.lower())] if filt else cols

with c1:
    sigs = st.multiselect(
        "Сигналы (лучше 2–12 для читаемости)",
        options=fcols,
        default=fcols[: min(6, len(fcols))],
    )

if not sigs:
    st.stop()

# Build time vector for playhead + range
x_ref_full = extract_time_vector(df_ref, tcol)
if x_ref_full.size:
    max_idx = int(max(0, len(x_ref_full) - 1))
    cpl1, cpl2, cpl3 = st.columns([1, 2, 2])
    with cpl1:
        idx_play = st.slider("Playhead idx", min_value=0, max_value=max_idx, value=0, step=1)
    with cpl2:
        t_play = float(x_ref_full[idx_play])
        st.caption(f"t = {t_play:.4f} s")
    with cpl3:
        # Range in seconds
        t0 = float(x_ref_full[0])
        t1 = float(x_ref_full[-1])
        t_rng = st.slider("Окно времени (s)", min_value=t0, max_value=t1, value=(t0, t1))
else:
    idx_play = 0
    t_rng = None

# Main compare figure
with st.spinner("Рисуем графики..."):
    fig, sig_ranges = _fig_compare(
        bundles,
        table,
        sigs,
        mode_delta=mode_delta,
        ref_label=ref_label,
        dist_unit=dist_unit,
        angle_unit=angle_unit,
        P_ATM=float(P_ATM),
        BAR_PA=float(BAR_PA),
        zero_baseline=zero_baseline,
        baseline_window_s=float(baseline_window_s),
        lock_y=lock_y,
        lock_y_by_unit=lock_y_by_unit,
        sym_y=sym_y,
        idx_play=int(idx_play),
        x_range=t_rng if isinstance(t_rng, tuple) else None,
    )

# Streamlit API: width='stretch' is new; fallback handled in main app, but here we keep safe.
try:
    st.plotly_chart(fig, width="stretch")
except TypeError:
    st.plotly_chart(fig, width="stretch")

# Heatmap (N signals × N runs): max |Δ| relative to reference
st.subheader("Heatmap: max |Δ| (по каждому сигналу относительно reference)")
heat_df, heat_fig = _delta_heatmap(
    bundles,
    table,
    sigs,
    ref_label=ref_label,
    dist_unit=dist_unit,
    angle_unit=angle_unit,
    P_ATM=float(P_ATM),
    BAR_PA=float(BAR_PA),
    zero_baseline=zero_baseline,
    baseline_window_s=float(baseline_window_s),
)

try:
    st.plotly_chart(heat_fig, width="stretch")
except TypeError:
    st.plotly_chart(heat_fig, width="stretch")

st.dataframe(heat_df, width="stretch")

st.caption(
    "Подсказка: для корректного визуального сравнения включайте 'Одинаковая шкала Y'. "
    "Для временных рядов удобен unified hover (Plotly hovermode='x unified')."
)
