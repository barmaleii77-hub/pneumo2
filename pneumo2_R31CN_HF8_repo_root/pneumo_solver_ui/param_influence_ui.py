# -*- coding: utf-8 -*-
"""param_influence_ui.py

UI-модуль для анализа вида:
  "как изменения N параметров (входов) влияют на изменения N показателей/метрик (выходов)"

Источник данных:
  - CSV оптимизации/экспериментов, где обычно есть колонки:
      * параметр__<имя>
      * метрика_* / цель* / штраф_* / свод__*

Ключевые идеи визуализации (инженерный workflow):
  1) **Overview → Filter → Details**:
     - сначала обзор (матрица влияний, сеть влияний, облако целей),
     - затем быстрый отбор (lasso/box + квантильные фильтры),
     - затем детализация (pairs, parallel, importance, PDP/ICE, Δ).
  2) **Brushing & linking**:
     - выделение в "Explorer" (scatter) становится активным подмножеством и
       применяется во всех вкладках (по желанию).

Зависимости:
  - streamlit
  - plotly
  - numpy, pandas
  - scikit-learn (опционально: importance + PDP/ICE на surrogate)
  - scipy (опционально: кластеризация осей матрицы)

"""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# NPZ index / traceability (optional)
try:
    from osc_index import (
        default_index_path as _osc_default_index_path,
        build_or_update_index as _osc_build_or_update_index,
        load_index as _osc_load_index,
        map_rows_to_npz as _osc_map_rows_to_npz,
        resolve_paths as _osc_resolve_paths,
    )
    _HAS_OSC_INDEX = True
except Exception:
    _osc_default_index_path = None  # type: ignore
    _osc_build_or_update_index = None  # type: ignore
    _osc_load_index = None  # type: ignore
    _osc_map_rows_to_npz = None  # type: ignore
    _osc_resolve_paths = None  # type: ignore
    _HAS_OSC_INDEX = False

# Plotly is required for this module
try:
    import plotly.express as px  # type: ignore
    import plotly.graph_objects as go  # type: ignore
    from plotly.subplots import make_subplots  # type: ignore
    _HAS_PLOTLY = True
except Exception:
    px = None  # type: ignore
    go = None  # type: ignore
    make_subplots = None  # type: ignore
    _HAS_PLOTLY = False

# scikit-learn: optional but recommended
try:
    from sklearn.ensemble import RandomForestRegressor  # type: ignore
    from sklearn.inspection import permutation_importance  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore
    from sklearn.metrics import r2_score  # type: ignore
    from sklearn.feature_selection import mutual_info_regression  # type: ignore
    from sklearn.preprocessing import StandardScaler  # type: ignore
    _HAS_SKLEARN = True
except Exception:
    RandomForestRegressor = None  # type: ignore
    permutation_importance = None  # type: ignore
    train_test_split = None  # type: ignore
    r2_score = None  # type: ignore
    mutual_info_regression = None  # type: ignore
    StandardScaler = None  # type: ignore
    _HAS_SKLEARN = False

# SciPy: optional (for clustering)
try:
    from scipy.cluster.hierarchy import linkage, leaves_list  # type: ignore
    from scipy.spatial.distance import squareform  # type: ignore
    _HAS_SCIPY = True
except Exception:
    linkage = None  # type: ignore
    leaves_list = None  # type: ignore
    squareform = None  # type: ignore
    _HAS_SCIPY = False


# -----------------------------
# Small helpers
# -----------------------------


def _safe_int(x, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _as_float(x) -> float:
    try:
        if x is None:
            return float("nan")
        if isinstance(x, (float, int, np.floating, np.integer)):
            return float(x)
        s = str(x).strip()
        if not s:
            return float("nan")
        return float(s)
    except Exception:
        return float("nan")


def _is_number_series(s: pd.Series) -> bool:
    try:
        return pd.api.types.is_numeric_dtype(s)
    except Exception:
        return False


def _short_name(col: str) -> str:
    c = str(col)
    return c.replace("параметр__", "")


def _slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(name or "session"))
    s = s.strip("_")
    return s or "session"


def safe_plotly_chart(st, fig, *, key: Optional[str] = None, on_select=None, selection_mode=None):
    """Совместимость со старыми/новыми Streamlit API для Plotly.

    Streamlit постепенно менял сигнатуру plotly_chart:
      * более новые версии поддерживают width="stretch" + (on_select/selection_mode)
      * более старые — width="stretch"

    Здесь мы делаем progressive fallback так, чтобы UI не падал.
    """
    base_kwargs = {}
    if key is not None:
        base_kwargs["key"] = key

    # New API first
    kwargs = dict(base_kwargs)
    kwargs["width"] = "stretch"
    if on_select is not None:
        kwargs["on_select"] = on_select
    if selection_mode is not None:
        kwargs["selection_mode"] = selection_mode
    try:
        return st.plotly_chart(fig, **kwargs)
    except TypeError:
        pass

    # Retry without selection extras
    try:
        return st.plotly_chart(fig, width="stretch", **base_kwargs)
    except TypeError:
        pass

    # Old API fallback
    try:
        return st.plotly_chart(fig, width="stretch", **base_kwargs)
    except TypeError:
        return st.plotly_chart(fig, **base_kwargs)

def _extract_plotly_selection_points(selection_state: Any) -> List[dict]:
    """Best-effort extract list of selected points from Streamlit Plotly selection state."""
    if selection_state is None:
        return []
    # New API may return object with `.selection`
    try:
        if hasattr(selection_state, "selection"):
            selection_state = getattr(selection_state, "selection")
    except Exception:
        pass

    # Sometimes selection_state itself already is selection-dict
    sel = selection_state
    if isinstance(sel, dict) and "selection" in sel and isinstance(sel.get("selection"), dict):
        sel = sel.get("selection")

    if isinstance(sel, dict):
        pts = sel.get("points")
        if isinstance(pts, list):
            return [p for p in pts if isinstance(p, dict)]
        # alt key
        pts = sel.get("point_indices") or sel.get("pointIndices")
        if isinstance(pts, list):
            return [{"pointIndex": int(i)} for i in pts if isinstance(i, (int, np.integer))]
    return []


def _selection_points_to_rows(points: List[dict]) -> List[int]:
    """Convert Plotly selected points -> our row ids (customdata)."""
    rows: List[int] = []
    for p in points:
        if not isinstance(p, dict):
            continue
        # Prefer customdata
        cd = p.get("customdata", None)
        if isinstance(cd, (list, tuple)) and cd:
            cd = cd[0]
        if isinstance(cd, (int, np.integer)):
            rows.append(int(cd))
            continue
        # Plotly sometimes provides customdata directly
        if isinstance(cd, (float, np.floating)) and float(cd).is_integer():
            rows.append(int(cd))
            continue
        # Fallback to pointIndex (index in trace)
        for k in ("pointIndex", "point_index", "pointNumber", "point_number"):
            v = p.get(k, None)
            if isinstance(v, (int, np.integer)):
                rows.append(int(v))
                break
    # unique preserve order
    seen = set()
    out = []
    for r in rows:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)
    return out


@dataclass
class ColGroups:
    id_col: Optional[str]
    param_cols: List[str]
    out_cols: List[str]
    other_numeric: List[str]


def detect_column_groups(df: pd.DataFrame) -> ColGroups:
    cols = list(df.columns)

    id_col = None
    for cand in ["id", "iter", "iteration", "step"]:
        if cand in cols:
            id_col = cand
            break

    param_cols = [c for c in cols if isinstance(c, str) and c.startswith("параметр__")]

    out_cols = [c for c in cols if isinstance(c, str) and (
        c.startswith("метрика_")
        or c.startswith("цель")
        or c.startswith("штраф_")
        or c.startswith("свод__")
    )]

    other_numeric: List[str] = []
    for c in cols:
        if c in (id_col,) or c in param_cols or c in out_cols:
            continue
        try:
            if _is_number_series(df[c]):
                other_numeric.append(c)
        except Exception:
            continue

    return ColGroups(id_col=id_col, param_cols=param_cols, out_cols=out_cols, other_numeric=other_numeric)


def _read_csv_robust(path: Path) -> pd.DataFrame:
    for enc in ["utf-8-sig", "utf-8", "cp1251"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path)


def _glob_candidate_csvs(base_dirs: List[Path]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for d in base_dirs:
        try:
            d = Path(d)
            if not d.exists():
                continue
            for p in sorted(d.glob("*.csv")):
                try:
                    rp = p.resolve()
                except Exception:
                    rp = p
                if str(rp) in seen:
                    continue
                seen.add(str(rp))
                out.append(p)
        except Exception:
            continue
    return out


def _sample_df(df: pd.DataFrame, max_rows: int, *, seed: int = 0) -> pd.DataFrame:
    if max_rows <= 0:
        return df
    if len(df) <= max_rows:
        return df
    return df.sample(n=int(max_rows), random_state=int(seed)).sort_index()


def _corr_submatrix(df_num: pd.DataFrame, inputs: List[str], outputs: List[str], method: str) -> pd.DataFrame:
    cols = [c for c in (inputs + outputs) if c in df_num.columns]
    if not cols:
        return pd.DataFrame()
    cm = df_num[cols].corr(method=method)
    rows = [o for o in outputs if o in cm.index]
    cols = [p for p in inputs if p in cm.columns]
    if not rows or not cols:
        return pd.DataFrame()
    return cm.loc[rows, cols]


def _hash_int_list(xs: List[int]) -> str:
    """Compact stable hash for caching/keys (selection can be long)."""
    try:
        b = ",".join(str(int(x)) for x in xs).encode("utf-8", errors="ignore")
        return hashlib.md5(b).hexdigest()
    except Exception:
        return "0"


def _pareto_front_mask_2d(x: np.ndarray, y: np.ndarray, *, minimize_x: bool = True, minimize_y: bool = True) -> np.ndarray:
    """Fast 2D Pareto front mask.

    Returns boolean mask of non-dominated points.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n == 0:
        return np.zeros((0,), dtype=bool)
    # Convert to minimization
    xx = x if minimize_x else -x
    yy = y if minimize_y else -y
    # Sort by x asc, then scan best y
    order = np.argsort(xx, kind="mergesort")
    best_y = np.inf
    mask = np.zeros(n, dtype=bool)
    for idx in order:
        v = yy[idx]
        if not np.isfinite(v):
            continue
        if v < best_y:
            mask[idx] = True
            best_y = v
    return mask


def _mutual_info_submatrix(
    df_num: pd.DataFrame,
    inputs: List[str],
    outputs: List[str],
    *,
    n_neighbors: int = 5,
    seed: int = 0,
    max_rows: int = 5000,
    normalize_per_output: bool = True,
) -> pd.DataFrame:
    """Compute MI matrix: rows=outputs, cols=inputs.

    Uses sklearn.feature_selection.mutual_info_regression (kNN-based estimator).
    We standardize X to reduce scale bias.
    """
    if (not _HAS_SKLEARN) or mutual_info_regression is None:
        return pd.DataFrame()

    in_cols = [c for c in inputs if c in df_num.columns]
    out_cols = [c for c in outputs if c in df_num.columns]
    if not in_cols or not out_cols:
        return pd.DataFrame()

    df_s = df_num[in_cols + out_cols].replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if len(df_s) == 0:
        return pd.DataFrame()
    if max_rows > 0 and len(df_s) > int(max_rows):
        df_s = df_s.sample(n=int(max_rows), random_state=int(seed))

    X = df_s[in_cols].to_numpy(dtype=float)
    # Standardize X for distance-based estimator
    try:
        if StandardScaler is not None:
            X = StandardScaler().fit_transform(X)
        else:
            mu = np.nanmean(X, axis=0)
            sd = np.nanstd(X, axis=0)
            sd = np.where(sd < 1e-12, 1.0, sd)
            X = (X - mu) / sd
    except Exception:
        pass

    res: Dict[str, np.ndarray] = {}
    for ycol in out_cols:
        y = df_s[ycol].to_numpy(dtype=float)
        try:
            mi = mutual_info_regression(X, y, n_neighbors=int(n_neighbors), random_state=int(seed), n_jobs=-1)
        except TypeError:
            mi = mutual_info_regression(X, y, n_neighbors=int(n_neighbors), random_state=int(seed))
        res[ycol] = np.asarray(mi, dtype=float)

    mat = pd.DataFrame(res, index=in_cols).T  # outputs x inputs
    mat = mat.replace([np.inf, -np.inf], np.nan)
    if normalize_per_output:
        try:
            denom = mat.max(axis=1).replace(0.0, np.nan)
            mat = mat.div(denom, axis=0)
        except Exception:
            pass
    return mat


_NPZ_CELL_RE = re.compile(r"(?P<path>[^;\n\r\t\"]+?\.npz)", flags=re.IGNORECASE)


def _extract_npz_candidates(v: Any) -> List[str]:
    """Extract one or more *.npz paths from a cell value."""
    if v is None:
        return []
    if isinstance(v, (Path,)):
        v = str(v)
    if not isinstance(v, str):
        return []
    s = v.strip().strip("\"").strip("'")
    if not s:
        return []
    hits = [m.group("path").strip() for m in _NPZ_CELL_RE.finditer(s) if m.group("path")]
    # Also split by separators and keep exact endswith
    if not hits:
        parts = re.split(r"[;,\n\r]+", s)
        for p in parts:
            p = p.strip().strip("\"").strip("'")
            if p.lower().endswith(".npz"):
                hits.append(p)
    # de-dup keep order
    out: List[str] = []
    seen = set()
    for h in hits:
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
    return out


def _resolve_npz_paths(raw_paths: List[str], *, roots: List[Path]) -> Tuple[List[str], pd.DataFrame]:
    """Resolve (possibly relative) npz paths against roots. Returns (existing_paths, status_df)."""
    rows = []
    existing: List[str] = []
    for rp in raw_paths:
        rp_s = str(rp).strip().strip("\"").strip("'")
        if not rp_s:
            continue
        p0 = Path(rp_s).expanduser()
        cand: Optional[Path] = None
        tried: List[str] = []
        if p0.is_absolute():
            tried.append(str(p0))
            if p0.exists() and p0.is_file():
                cand = p0
        else:
            for r in roots:
                try:
                    c = (Path(r) / p0).expanduser()
                    tried.append(str(c))
                    if c.exists() and c.is_file():
                        cand = c
                        break
                except Exception:
                    continue
        ok = cand is not None
        resolved = str(cand.resolve()) if ok else ""
        if ok:
            existing.append(resolved)
        rows.append({
            "raw": rp_s,
            "resolved": resolved,
            "exists": bool(ok),
            "tried": "\n".join(tried[:5]) + ("\n..." if len(tried) > 5 else ""),
        })
    df_status = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["raw", "resolved", "exists", "tried"])
    # de-dup existing preserve order
    out_exist: List[str] = []
    seen2 = set()
    for p in existing:
        if p in seen2:
            continue
        seen2.add(p)
        out_exist.append(p)
    return out_exist, df_status


def _cluster_order_abs_corr(df_num: pd.DataFrame, cols: List[str], method: str) -> List[str]:
    """Order columns by hierarchical clustering on |corr|. Requires SciPy."""
    if (not _HAS_SCIPY) or linkage is None or leaves_list is None or squareform is None:
        return cols
    cols = [c for c in cols if c in df_num.columns]
    if len(cols) < 3:
        return cols
    try:
        cmat = df_num[cols].corr(method=method).abs().to_numpy(dtype=float)
        # replace nan with 0 corr => dist=1
        cmat = np.nan_to_num(cmat, nan=0.0, posinf=0.0, neginf=0.0)
        dist = 1.0 - cmat
        # squareform requires zeros on diag
        np.fill_diagonal(dist, 0.0)
        z = linkage(squareform(dist, checks=False), method="average")
        order = leaves_list(z).tolist()
        return [cols[i] for i in order if 0 <= i < len(cols)]
    except Exception:
        return cols


def _rank_top_abs(mat: pd.DataFrame, *, top_k: int = 8) -> pd.DataFrame:
    rows = []
    for o in mat.index:
        s = mat.loc[o].dropna()
        if s.empty:
            continue
        ss = s.abs().sort_values(ascending=False).head(int(top_k))
        for p, vabs in ss.items():
            rows.append({"output": o, "param": p, "corr": float(mat.loc[o, p]), "abs_corr": float(vabs)})
    if not rows:
        return pd.DataFrame(columns=["output", "param", "corr", "abs_corr"])
    return pd.DataFrame(rows).sort_values(["output", "abs_corr"], ascending=[True, False]).reset_index(drop=True)


def _bar_figure(names: List[str], values: List[float], title: str, *, horizontal: bool = True):
    if not _HAS_PLOTLY:
        return None
    if horizontal:
        fig = go.Figure(go.Bar(x=values, y=names, orientation='h'))
        fig.update_layout(title=title, height=max(420, 20 * len(names)))
    else:
        fig = go.Figure(go.Bar(x=names, y=values))
        fig.update_layout(title=title, height=420)
    fig.update_layout(margin=dict(l=40, r=10, t=50, b=40))
    return fig


def _detect_npz_path_column(df: pd.DataFrame) -> Optional[str]:
    """Heuristic: find a column that likely contains path to an NPZ file."""
    cols = [str(c) for c in df.columns]
    # explicit candidates first
    for cand in ["npz_path", "npz_file", "npz", "osc_npz", "log_npz", "path_npz"]:
        if cand in cols:
            return cand
    # heuristic
    for c in cols:
        cl = c.lower()
        if "npz" in cl and ("path" in cl or "file" in cl or "путь" in cl or "файл" in cl):
            return c
    return None


def _is_jsonable(v: Any) -> bool:
    if v is None or isinstance(v, (str, int, float, bool)):
        return True
    if isinstance(v, (list, tuple)):
        return all(_is_jsonable(x) for x in v)
    if isinstance(v, dict):
        return all(isinstance(k, str) and _is_jsonable(val) for k, val in v.items())
    return False


def _dump_pi_session(st) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for k, v in st.session_state.items():
        if not isinstance(k, str):
            continue
        if not k.startswith("pi_"):
            continue
        if k.startswith("pi_cache") or k.startswith("pi__cache"):
            continue
        if "fig" in k.lower():
            continue
        if "cache" in k.lower():
            continue
        if _is_jsonable(v):
            state[k] = v
    return {
        "version": 1,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "state": state,
    }


def _apply_pi_session(st, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    st_state = payload.get("state")
    if isinstance(st_state, dict):
        for k, v in st_state.items():
            try:
                st.session_state[k] = v
            except Exception:
                pass


# -----------------------------
# Surrogate / PDP helpers
# -----------------------------


def _prepare_xy(df_num: pd.DataFrame, inputs: List[str], y: str) -> Tuple[np.ndarray, np.ndarray]:
    X = df_num[inputs].to_numpy(dtype=float)
    Y = df_num[y].to_numpy(dtype=float)
    m = np.isfinite(X).all(axis=1) & np.isfinite(Y)
    return X[m], Y[m]


def _train_rf_regressor(X: np.ndarray, y: np.ndarray, *, seed: int, n_estimators: int) -> Tuple[Any, float]:
    """Train RF on train/test split. Return model and R² on holdout."""
    if not _HAS_SKLEARN or RandomForestRegressor is None:
        raise RuntimeError("scikit-learn not available")
    if len(y) < 30:
        raise RuntimeError("too few rows")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=int(seed))
    model = RandomForestRegressor(
        n_estimators=int(n_estimators),
        random_state=int(seed),
        n_jobs=-1,
        max_features=1.0,
    )
    model.fit(X_train, y_train)
    try:
        y_pred = model.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
    except Exception:
        r2 = float("nan")
    return model, r2


def _pdp_1d(model: Any, X_base: np.ndarray, feat_i: int, grid: np.ndarray, *, max_base: int = 1200, seed: int = 0) -> np.ndarray:
    """Compute 1D PDP by replacing feature column with grid values and averaging predictions."""
    Xb = np.asarray(X_base, dtype=float)
    if len(Xb) > int(max_base):
        rng = np.random.default_rng(int(seed))
        idx = rng.choice(len(Xb), size=int(max_base), replace=False)
        Xb = Xb[idx]
    out = []
    for v in grid:
        Xt = Xb.copy()
        Xt[:, int(feat_i)] = float(v)
        try:
            yp = model.predict(Xt)
            out.append(float(np.nanmean(np.asarray(yp, dtype=float))))
        except Exception:
            out.append(float("nan"))
    return np.asarray(out, dtype=float)



def _pdp_2d(
    model: Any,
    X_base: np.ndarray,
    feat_i: int,
    feat_j: int,
    grid_i: np.ndarray,
    grid_j: np.ndarray,
    *,
    max_base: int = 800,
    seed: int = 0,
) -> np.ndarray:
    """Compute 2D PDP surface by replacing two feature columns with grid values and averaging predictions.

    Returns array shape (len(grid_i), len(grid_j)).
    """
    Xb = np.asarray(X_base, dtype=float)
    if len(Xb) > int(max_base):
        rng = np.random.default_rng(int(seed))
        idxs = rng.choice(len(Xb), size=int(max_base), replace=False)
        Xb = Xb[idxs]

    gi = np.asarray(grid_i, dtype=float)
    gj = np.asarray(grid_j, dtype=float)
    out = np.zeros((len(gi), len(gj)), dtype=float)

    Xtmp = Xb.copy()
    for a, vi in enumerate(gi):
        Xtmp[:, int(feat_i)] = float(vi)
        for b, vj in enumerate(gj):
            Xtmp[:, int(feat_j)] = float(vj)
            yp = model.predict(Xtmp)
            try:
                out[a, b] = float(np.nanmean(np.asarray(yp, dtype=float)))
            except Exception:
                out[a, b] = float("nan")
    return out


def _friedman_h_statistic(pdp_2d: np.ndarray, pdp_i: np.ndarray, pdp_j: np.ndarray) -> float:
    """Friedman H-statistic (interaction strength) from centered PDPs.

    H = sqrt( Var( f_ij - f_i - f_j ) / Var( f_ij ) )
    """
    f_ij = np.asarray(pdp_2d, dtype=float)
    if f_ij.size == 0:
        return float("nan")
    fi = np.asarray(pdp_i, dtype=float).reshape(-1, 1)
    fj = np.asarray(pdp_j, dtype=float).reshape(1, -1)

    # Center terms
    f_ij_c = f_ij - np.nanmean(f_ij)
    fi_c = fi - np.nanmean(fi)
    fj_c = fj - np.nanmean(fj)

    inter = f_ij_c - fi_c - fj_c

    v_ij = float(np.nanvar(f_ij_c))
    if not (v_ij > 1e-18):
        return 0.0
    v_int = float(np.nanvar(inter))
    h2 = max(0.0, min(1.0, v_int / v_ij))
    return float(np.sqrt(h2))


def _ice_1d(model: Any, X_rows: np.ndarray, feat_i: int, grid: np.ndarray) -> np.ndarray:
    """ICE curves: for each row, vary feat across grid."""
    Xr = np.asarray(X_rows, dtype=float)
    curves = np.zeros((len(Xr), len(grid)), dtype=float)
    curves[:] = np.nan
    for i in range(len(Xr)):
        base = Xr[i].copy()
        for j, v in enumerate(grid):
            Xt = base.copy()
            Xt[int(feat_i)] = float(v)
            try:
                curves[i, j] = float(model.predict(Xt.reshape(1, -1))[0])
            except Exception:
                curves[i, j] = float("nan")
    return curves


# -----------------------------
# Multi-output surrogate + local sensitivity helpers
# -----------------------------


def _prepare_xy_multi(df_num: pd.DataFrame, inputs: List[str], outputs: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    """Prepare X/Y for multi-output regression. Drops rows with any NaN/inf."""
    X = df_num[inputs].to_numpy(dtype=float)
    Y = df_num[outputs].to_numpy(dtype=float)
    m = np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1)
    return X[m], Y[m]


def _train_rf_multioutput(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    seed: int,
    n_estimators: int,
    test_size: float = 0.25,
) -> Tuple[Any, np.ndarray, float]:
    """Train RandomForestRegressor for multi-output regression.

    Returns (model, r2_per_output, r2_mean).
    """
    if not _HAS_SKLEARN or RandomForestRegressor is None or train_test_split is None or r2_score is None:
        raise RuntimeError("scikit-learn not available")

    if len(Y) < 60:
        raise RuntimeError("too few rows")

    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=float(test_size), random_state=int(seed))

    model = RandomForestRegressor(
        n_estimators=int(n_estimators),
        random_state=int(seed),
        n_jobs=-1,
        max_features=1.0,
    )
    model.fit(X_train, Y_train)

    try:
        Y_pred = model.predict(X_test)
        r2_raw = r2_score(Y_test, Y_pred, multioutput="raw_values")
        r2_raw = np.asarray(r2_raw, dtype=float).reshape(-1)
        r2_mean = float(np.nanmean(r2_raw))
    except Exception:
        r2_raw = np.full((Y.shape[1],), np.nan, dtype=float)
        r2_mean = float("nan")

    return model, r2_raw, r2_mean


def _local_sensitivity_matrix(
    model: Any,
    x0: np.ndarray,
    step: np.ndarray,
    *,
    mode: str = "forward",
    clip_min: Optional[np.ndarray] = None,
    clip_max: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Approximate local sensitivity of multi-output model around point x0.

    Returns:
      y0: (n_outputs,)
      dy: (n_outputs, n_inputs)  -- derivative approx dY/dX
      delta: (n_outputs, n_inputs) -- finite delta for +step (Y(x+step) - Y(x))
    """
    x0 = np.asarray(x0, dtype=float).reshape(-1)
    step = np.asarray(step, dtype=float).reshape(-1)
    y0 = np.asarray(model.predict(x0.reshape(1, -1))[0], dtype=float).reshape(-1)

    n_inputs = len(x0)
    n_outputs = len(y0)

    dy = np.full((n_outputs, n_inputs), np.nan, dtype=float)
    delta = np.full((n_outputs, n_inputs), np.nan, dtype=float)

    mode = str(mode or "forward").lower().strip()
    use_central = mode.startswith("c")

    for j in range(n_inputs):
        h = float(step[j])
        if not np.isfinite(h) or abs(h) < 1e-12:
            continue

        xp = x0.copy()
        xp[j] = xp[j] + h

        if clip_min is not None and clip_max is not None:
            xp[j] = float(np.clip(xp[j], clip_min[j], clip_max[j]))

        if use_central:
            xm = x0.copy()
            xm[j] = xm[j] - h
            if clip_min is not None and clip_max is not None:
                xm[j] = float(np.clip(xm[j], clip_min[j], clip_max[j]))

            yp = np.asarray(model.predict(xp.reshape(1, -1))[0], dtype=float).reshape(-1)
            ym = np.asarray(model.predict(xm.reshape(1, -1))[0], dtype=float).reshape(-1)

            denom = float(xp[j] - xm[j])
            if abs(denom) < 1e-12:
                continue
            dy[:, j] = (yp - ym) / denom
            delta[:, j] = yp - y0
        else:
            yp = np.asarray(model.predict(xp.reshape(1, -1))[0], dtype=float).reshape(-1)
            denom = float(xp[j] - x0[j])
            if abs(denom) < 1e-12:
                continue
            dy[:, j] = (yp - y0) / denom
            delta[:, j] = yp - y0

    return y0, dy, delta


# -----------------------------
# Main UI
# -----------------------------


def render_param_influence_ui(
    *,
    st,
    default_csv_path: str = "",
    app_dir: Optional[Path] = None,
    allow_upload: bool = True,
):
    """Render Param Influence Dashboard (N→N)."""

    st.header("Влияние параметров (N→N)")

    if not _HAS_PLOTLY:
        st.error("Plotly не установлен — модуль влияния параметров требует plotly.")
        return

    app_dir = Path(app_dir) if app_dir is not None else Path(__file__).resolve().parent
    workspace_dir = app_dir / "workspace"
    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # -----------------------------
    # Data source (CSV)
    # -----------------------------
    with st.expander("Загрузка данных (CSV оптимизации/экспериментов)", expanded=True):
        cand_dirs = [
            app_dir,
            app_dir / "calibration_runs",
            app_dir.parent / "calibration_runs",
            workspace_dir / "imports",
        ]
        csvs = _glob_candidate_csvs(cand_dirs)
        opts = ["(выбрать файл вручную)"] + [str(p) for p in csvs]

        colA, colB = st.columns([1.4, 1.0], gap="large")
        with colA:
            pick = st.selectbox("Найденные CSV", options=opts, index=0, key="pi_csv_pick")
            path_text = st.text_input(
                "Путь к CSV",
                value=(st.session_state.get("pi_csv_path") or default_csv_path or "") if pick == "(выбрать файл вручную)" else pick,
                key="pi_csv_path",
                help="Обычно это opt_*.csv рядом с приложением (пишет оптимизатор).",
            )
        with colB:
            upload = None
            if allow_upload:
                upload = st.file_uploader("Или загрузите CSV", type=["csv"], accept_multiple_files=False, key="pi_csv_upload")

        csv_path: Optional[Path] = None
        if upload is not None:
            try:
                imp_dir = workspace_dir / "imports"
                imp_dir.mkdir(parents=True, exist_ok=True)
                out = imp_dir / f"uploaded_{upload.name}"
                out.write_bytes(upload.getvalue())
                csv_path = out
                st.success(f"CSV сохранён: {out}")
            except Exception as e:
                st.error(f"Не удалось сохранить загруженный CSV: {e}")
                return
        else:
            if path_text and str(path_text).strip():
                p = Path(str(path_text)).expanduser()
                if p.exists() and p.is_file():
                    csv_path = p
                else:
                    st.warning("Укажите существующий CSV файл.")
        if csv_path is None:
            st.stop()

        st.markdown("---")
        st.subheader("Reference CSV (опционально)")
        use_ref = st.checkbox(
            "Подключить reference CSV для сравнительных диаграмм",
            value=bool(st.session_state.get("pi_ref_enable") or False),
            key="pi_ref_enable",
            help="Позволяет сравнивать влияние/матрицы (A vs B) и видеть Δ (разницу).",
        )

        csv_ref_path: Optional[Path] = None
        if use_ref:
            colR1, colR2 = st.columns([1.4, 1.0], gap="large")
            with colR1:
                pick_ref = st.selectbox("Найденные CSV (reference)", options=opts, index=0, key="pi_csv_ref_pick")
                path_ref_text = st.text_input(
                    "Путь к reference CSV",
                    value=(st.session_state.get("pi_csv_ref_path") or "") if pick_ref == "(выбрать файл вручную)" else pick_ref,
                    key="pi_csv_ref_path",
                    help="Например: opt_*.csv от другого прогона/итерации.",
                )
            with colR2:
                upload_ref = None
                if allow_upload:
                    upload_ref = st.file_uploader(
                        "Или загрузите reference CSV",
                        type=["csv"],
                        accept_multiple_files=False,
                        key="pi_csv_ref_upload",
                    )

            if upload_ref is not None:
                try:
                    imp_dir = workspace_dir / "imports"
                    imp_dir.mkdir(parents=True, exist_ok=True)
                    out = imp_dir / f"uploaded_ref_{upload_ref.name}"
                    out.write_bytes(upload_ref.getvalue())
                    csv_ref_path = out
                    st.success(f"Reference CSV сохранён: {out}")
                except Exception as e:
                    st.error(f"Не удалось сохранить reference CSV: {e}")
                    csv_ref_path = None
            else:
                if path_ref_text and str(path_ref_text).strip():
                    pr = Path(str(path_ref_text)).expanduser()
                    if pr.exists() and pr.is_file():
                        csv_ref_path = pr
                    else:
                        st.warning("Reference CSV: укажите существующий файл или загрузите его.")

    # -----------------------------
    # Sessions (save/load)
    # -----------------------------
    session_dir = workspace_dir / "param_influence_sessions"
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        session_dir = None  # type: ignore

    with st.expander("Сессии анализа влияния (save/load) — чтобы быстро возвращаться к одному виду", expanded=False):
        st.caption("Сохраняет выбранные колонки, фильтры, настройки вкладок и активное выделение.")
        if session_dir is None:
            st.warning("Не могу создать папку param_influence_sessions (нет прав).")
        else:
            sess_files = sorted(session_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            cols_s1, cols_s2 = st.columns([1.2, 1.0], gap="medium")
            with cols_s1:
                new_name = st.text_input(
                    "Имя новой сессии (латиница/цифры/_)",
                    value=st.session_state.get("pi_sess_new_name") or f"pi_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    key="pi_sess_new_name",
                )
                if st.button("💾 Сохранить сессию", key="pi_sess_save"):
                    safe = _slugify(str(new_name or "session"))
                    out = session_dir / f"{safe}.json"
                    try:
                        out.write_text(json.dumps(_dump_pi_session(st), ensure_ascii=False, indent=2), encoding="utf-8")
                        st.success(f"Сессия сохранена: {out.name}")
                    except Exception as e:
                        st.error(f"Не удалось сохранить: {e}")
            with cols_s2:
                if sess_files:
                    opt = [p.name for p in sess_files]
                    pick_sess = st.selectbox("Загрузить сессию", options=opt, index=0, key="pi_sess_pick")
                    if st.button("📂 Загрузить", key="pi_sess_load"):
                        p = session_dir / str(pick_sess)
                        try:
                            payload = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                            _apply_pi_session(st, payload)
                            st.success("Сессия загружена. Перерисовываю…")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Не удалось загрузить: {e}")
                else:
                    st.info("Пока нет сохранённых сессий.")
            st.write("Папка сессий:", str(session_dir))

    # -----------------------------
    # Load CSV (cached)
    # -----------------------------
    @st.cache_data(show_spinner=False)
    def _load_csv_cached(p: str) -> pd.DataFrame:
        return _read_csv_robust(Path(p))

    with st.spinner("Читаю CSV..."):
        df_raw = _load_csv_cached(str(csv_path))

    # Optional: reference CSV for comparative views (A vs B)
    df_raw_ref: Optional[pd.DataFrame] = None
    groups_ref: Optional[ColGroups] = None
    if csv_ref_path is not None:
        try:
            with st.spinner("Читаю reference CSV..."):
                df_raw_ref = _load_csv_cached(str(csv_ref_path))
        except Exception as e:
            st.warning(f"Reference CSV не прочитался: {e}")
            df_raw_ref = None

        if df_raw_ref is not None and len(df_raw_ref) > 0:
            groups_ref = detect_column_groups(df_raw_ref)
        else:
            df_raw_ref = None
            groups_ref = None

    if df_raw is None or len(df_raw) == 0:
        st.warning("CSV пустой или не прочитался.")
        return

    groups = detect_column_groups(df_raw)

    # -----------------------------
    # Filters / column selection
    # -----------------------------
    with st.expander("Фильтры, выделение и выбор колонок", expanded=True):
        colF1, colF2, colF3 = st.columns([1.0, 1.0, 1.0], gap="large")
        with colF1:
            drop_errors = st.checkbox("Убрать строки с ошибкой (ошибка != пусто)", value=True, key="pi_drop_errors")
            drop_inf = st.checkbox("Убрать inf", value=True, key="pi_drop_inf")
        with colF2:
            max_rows_plot = st.number_input(
                "Макс. строк для интерактивных графиков (scatter/parallel)",
                min_value=300,
                max_value=50000,
                value=int(st.session_state.get("pi_max_rows_plot") or 6000),
                step=300,
                key="pi_max_rows_plot",
            )
            seed = st.number_input("Seed сэмплинга", min_value=0, max_value=999999, value=int(st.session_state.get("pi_seed") or 0), step=1, key="pi_seed")
        with colF3:
            corr_method = st.selectbox("Корреляция", options=["spearman", "pearson"], index=0, key="pi_corr_method")
            top_k = st.number_input("Топ‑K параметров на выход", min_value=3, max_value=40, value=int(st.session_state.get("pi_top_k") or 10), step=1, key="pi_top_k")

        # Work DF
        df = df_raw.copy()
        if drop_errors and "ошибка" in df.columns:
            try:
                mask = df["ошибка"].isna() | (df["ошибка"].astype(str).str.strip() == "")
                df = df.loc[mask].copy()
            except Exception:
                pass
        if drop_inf:
            df = df.replace([np.inf, -np.inf], np.nan)

        # add stable row id for linking
        df = df.reset_index(drop=True)
        df["_row"] = np.arange(len(df), dtype=int)

        # numeric columns
        num_cols = [c for c in df.columns if _is_number_series(df[c])]
        df_num = df[num_cols].copy()

        # Reference dataset (optional): apply the same basic cleaning so that
        # comparative matrices are meaningful.
        df_ref: Optional[pd.DataFrame] = None
        df_num_ref: Optional[pd.DataFrame] = None
        if df_raw_ref is not None and len(df_raw_ref) > 0:
            df_ref = df_raw_ref.copy()
            if drop_errors and "ошибка" in df_ref.columns:
                try:
                    maskr = df_ref["ошибка"].isna() | (df_ref["ошибка"].astype(str).str.strip() == "")
                    df_ref = df_ref.loc[maskr].copy()
                except Exception:
                    pass
            if drop_inf:
                df_ref = df_ref.replace([np.inf, -np.inf], np.nan)

            df_ref = df_ref.reset_index(drop=True)
            df_ref["_row_ref"] = np.arange(len(df_ref), dtype=int)

            num_cols_ref = [c for c in df_ref.columns if _is_number_series(df_ref[c])]
            df_num_ref = df_ref[num_cols_ref].copy()

        # defaults (keep only varying columns)
        default_inputs = groups.param_cols[:]
        default_outputs = groups.out_cols[:]
        try:
            if default_inputs:
                var = df_num[default_inputs].var(numeric_only=True)
                default_inputs = var.sort_values(ascending=False).head(24).index.tolist()
        except Exception:
            pass
        try:
            if default_outputs:
                var = df_num[default_outputs].var(numeric_only=True)
                default_outputs = var.sort_values(ascending=False).head(24).index.tolist()
        except Exception:
            pass

        inputs = st.multiselect(
            "Входы: параметры (X)",
            options=groups.param_cols,
            default=st.session_state.get("pi_inputs") or default_inputs,
            key="pi_inputs",
            help="Колонки вида параметр__...",
        )

        outputs_all = groups.out_cols + [c for c in groups.other_numeric if c.startswith("огр__") or c.startswith("запас")]
        outputs = st.multiselect(
            "Выходы: метрики/цели (Y)",
            options=outputs_all,
            default=st.session_state.get("pi_outputs") or default_outputs,
            key="pi_outputs",
            help="Обычно метрика_*, цель*, штраф_*, свод__*",
        )

        if not inputs or not outputs:
            st.warning("Выберите хотя бы 1 параметр и 1 выходную метрику.")
            st.stop()

        # Selection (active subset)
        sel_rows = st.session_state.get("pi_selected_rows") or []
        if not isinstance(sel_rows, list):
            sel_rows = []
        sel_rows = [int(x) for x in sel_rows if isinstance(x, (int, np.integer))]
        apply_sel = st.checkbox("Применять выделение из Explorer как активный фильтр", value=bool(sel_rows), key="pi_apply_selection")

        colS1, colS2, colS3 = st.columns([1.0, 1.0, 1.4], gap="medium")
        with colS1:
            if st.button("🧹 Очистить выделение", key="pi_clear_selection", disabled=(len(sel_rows) == 0)):
                st.session_state["pi_selected_rows"] = []
                st.session_state["pi_apply_selection"] = False
                st.rerun()
        with colS2:
            st.write("Выделено:", int(len(sel_rows)))
        with colS3:
            st.caption("Выделение делается лассом/боксом в первой вкладке (Explorer).")

        if apply_sel and sel_rows:
            df_sel = df[df["_row"].isin(sel_rows)].copy()
            df_num_sel = df_sel[[c for c in df_sel.columns if c in df_num.columns]].copy()
        else:
            df_sel = df
            df_num_sel = df_num

        # reference (do NOT apply Explorer selection by default)
        df_ref_sel = df_ref
        df_num_ref_sel = df_num_ref
        has_ref = bool(df_ref_sel is not None and df_num_ref_sel is not None and len(df_ref_sel) > 0)
        if has_ref:
            st.caption(f"Reference CSV: строк после фильтров: {len(df_ref_sel)}")
            missing_x = [c for c in inputs if c not in df_num_ref_sel.columns]
            missing_y = [c for c in outputs if c not in df_num_ref_sel.columns]
            if missing_x or missing_y:
                st.info(
                    "Reference CSV: часть выбранных колонок отсутствует (в сравнительных матрицах будут использованы только общие колонки)."\
                )

        st.caption(f"Строк после фильтров: {len(df_sel)} (из {len(df_raw)})")

    # Visual sample
    df_vis = _sample_df(df_sel, int(max_rows_plot), seed=int(seed))
    df_vis_ref = _sample_df(df_ref_sel, int(max_rows_plot), seed=int(seed)) if has_ref else None

    # Detect id column for hover/labels
    id_col = groups.id_col if (groups.id_col in df_sel.columns if groups.id_col else False) else None
    id_col_ref = None
    if has_ref and groups_ref is not None:
        try:
            id_col_ref = groups_ref.id_col if (groups_ref.id_col in df_ref_sel.columns if groups_ref.id_col else False) else None
        except Exception:
            id_col_ref = None

    # NPZ path mapping (optional)
    npz_col = _detect_npz_path_column(df_sel)

    # -----------------------------
    # Tabs (coordinated multiple views)
    # -----------------------------
    tab_labels = [
        "Explorer (выбор/парето)",
        "Корреляции (матрица)",
        "Нелинейные связи (MI)",
        "SPLOM (матрица scatter)",
        "Сеть влияний (Sankey)",
        "Пары (scatter)",
        "Параллельные координаты",
        "N×N чувствительность",
        "Важность (модель)",
        "PDP/ICE (surrogate)",
        "ALE (surrogate)",
        "Сравнение групп",
        "Δ двух прогонов",
        "История",
        "Таблица",
    ]
    (
        tab_explorer,
        tab_matrix,
        tab_mi,
        tab_splom,
        tab_sankey,
        tab_pairs,
        tab_parcoords,
        tab_sens,
        tab_importance,
        tab_pdp,
        tab_ale,
        tab_group,
        tab_delta,
        tab_history,
        tab_table,
    ) = st.tabs(tab_labels)

    # -----------------------------
    # Tab 0: Explorer (selection)
    # -----------------------------
    with tab_explorer:
        st.subheader("Explorer: облако решений + выделение (brushing)")
        st.caption("Лассо/бокс‑выделение здесь становится активным фильтром для остальных вкладок (если включено).")

        colE1, colE2, colE3, colE4 = st.columns([1.1, 1.1, 1.1, 1.1], gap="medium")
        with colE1:
            x_out = st.selectbox("X (метрика)", options=outputs, index=0, key="pi_explorer_x")
        with colE2:
            y_out = st.selectbox("Y (метрика)", options=outputs, index=1 if len(outputs) > 1 else 0, key="pi_explorer_y")
        with colE3:
            color_by = st.selectbox("Цвет", options=[*outputs, "штраф_физичности_сумма"] if "штраф_физичности_сумма" in df_vis.columns else outputs, index=0, key="pi_explorer_color")
        with colE4:
            show_labels = st.checkbox("Подписи id", value=False, key="pi_explorer_labels")

        # Extra controls: Pareto highlight and reference overlay
        colE5, colE6, colE7, colE8 = st.columns([1.1, 1.0, 1.0, 1.1], gap="medium")
        with colE5:
            pareto_on = st.checkbox("Подсветить Pareto-front", value=True, key="pi_explorer_pareto")
        with colE6:
            pareto_x = st.selectbox("Pareto по X", options=["minimize", "maximize"], index=0, key="pi_explorer_pareto_x")
        with colE7:
            pareto_y = st.selectbox("Pareto по Y", options=["minimize", "maximize"], index=0, key="pi_explorer_pareto_y")
        with colE8:
            show_ref_bg = st.checkbox(
                "Фон: reference",
                value=bool(has_ref),
                disabled=(not has_ref or df_vis_ref is None),
                key="pi_explorer_ref_bg",
            )

        dfx = df_vis.copy()
        # Keep finite
        keep_cols = [c for c in [x_out, y_out, color_by] if c in dfx.columns]
        dfx = dfx.replace([np.inf, -np.inf], np.nan)
        dfx = dfx.dropna(subset=[c for c in keep_cols if c in dfx.columns], how="any")
        if len(dfx) < 5:
            st.info("Слишком мало строк после фильтрации NaN/inf. Увеличьте max_rows или ослабьте фильтры.")
        else:
            hover = {}
            if id_col is not None:
                hover[id_col] = True
            hover["_row"] = True
            # add a few params to hover (top 6 by variance)
            try:
                varp = df_num_sel[inputs].var(numeric_only=True).sort_values(ascending=False).head(6).index.tolist()
            except Exception:
                varp = inputs[:6]
            for p in varp:
                hover[p] = True

            fig = px.scatter(
                dfx,
                x=x_out,
                y=y_out,
                color=color_by if color_by in dfx.columns else None,
                custom_data=["_row"],
                hover_data=hover,
                title=f"Explorer (n={len(dfx)}) — lasso/box выделение",
            )

            # Optional overlay: reference background ("B")
            df_pareto: Optional[pd.DataFrame] = None
            if show_ref_bg and (df_vis_ref is not None):
                try:
                    df_bg = df_vis_ref.copy()
                    df_bg = df_bg.replace([np.inf, -np.inf], np.nan)
                    df_bg = df_bg.dropna(subset=[c for c in [x_out, y_out] if c in df_bg.columns], how="any")
                    if len(df_bg) > 0 and (x_out in df_bg.columns) and (y_out in df_bg.columns):
                        ref_trace = go.Scatter(
                            x=df_bg[x_out],
                            y=df_bg[y_out],
                            mode="markers",
                            name="reference",
                            marker=dict(size=5, opacity=0.12, color="rgba(120,120,120,0.7)"),
                            customdata=np.full((len(df_bg), 1), np.nan),
                            hoverinfo="skip",
                        )
                        fig.add_trace(ref_trace)
                        # put background first so primary stays on top
                        fig.data = (fig.data[-1],) + tuple(fig.data[:-1])
                except Exception:
                    pass

            # Optional highlight: 2D Pareto-front for current X/Y
            if pareto_on and (x_out in dfx.columns) and (y_out in dfx.columns):
                try:
                    minimize_x = (str(pareto_x) == "minimize")
                    minimize_y = (str(pareto_y) == "minimize")
                    mask_pf = _pareto_front_mask_2d(
                        dfx[x_out].to_numpy(dtype=float),
                        dfx[y_out].to_numpy(dtype=float),
                        minimize_x=minimize_x,
                        minimize_y=minimize_y,
                    )
                    if mask_pf is not None and np.any(mask_pf):
                        df_pareto = dfx.loc[mask_pf].copy()
                        pf_trace = go.Scatter(
                            x=df_pareto[x_out],
                            y=df_pareto[y_out],
                            mode="markers",
                            name="Pareto-front",
                            marker=dict(size=12, symbol="circle-open", line=dict(width=2)),
                            customdata=df_pareto[["_row"]].to_numpy(),
                            hovertemplate=f"Pareto<br>{x_out}=%{{x}}<br>{y_out}=%{{y}}<extra></extra>",
                        )
                        fig.add_trace(pf_trace)
                except Exception:
                    df_pareto = None
            fig.update_traces(marker=dict(size=7, opacity=0.75), selector=dict(mode="markers"))
            fig.update_layout(height=640, margin=dict(l=40, r=10, t=70, b=40))

            if show_labels and id_col is not None and id_col in dfx.columns:
                try:
                    fig.update_traces(text=dfx[id_col].astype(str), textposition="top center")
                except Exception:
                    pass

            sel_state = safe_plotly_chart(
                st,
                fig,
                key="pi_explorer_scatter",
                on_select="rerun",
                selection_mode=("lasso", "box"),
            )
            points = _extract_plotly_selection_points(sel_state)
            sel = _selection_points_to_rows(points)
            if sel:
                st.session_state["pi_selected_rows"] = sel
                # auto-enable apply selection for convenience
                st.session_state["pi_apply_selection"] = True
                st.success(f"Выделено точек: {len(sel)} (сохранено как активное выделение)")

            # quick summary for current selection (if any)
            sel_rows = st.session_state.get("pi_selected_rows") or []
            if isinstance(sel_rows, list) and len(sel_rows) > 0:
                df_sel2 = df_sel[df_sel["_row"].isin([int(x) for x in sel_rows if isinstance(x, (int, np.integer))])].copy()
                st.markdown("**Сводка по выделению:**")
                cols_sum = [c for c in [x_out, y_out, color_by] if c in df_sel2.columns]
                if cols_sum:
                    desc = df_sel2[cols_sum].describe(percentiles=[0.1, 0.5, 0.9]).T
                    st.dataframe(desc, width="stretch", height=260)

                # export selection
                try:
                    csv_bytes = df_sel2.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Скачать выделение (CSV)",
                        data=csv_bytes,
                        file_name="pi_selection.csv",
                        mime="text/csv",
                        key="pi_download_selection_csv",
                    )
                except Exception:
                    pass

                # optional: show Pareto-front points table (for current X/Y)
                if df_pareto is not None and len(df_pareto) > 0:
                    with st.expander("Pareto-front точки", expanded=False):
                        st.caption(f"Точек на Pareto-front: {len(df_pareto)}")
                        cols_show = [c for c in [id_col, x_out, y_out] if c is not None and c in df_pareto.columns]
                        st.dataframe(df_pareto[cols_show] if cols_show else df_pareto, width="stretch", height=260)

                # optional: push NPZ list to Compare UI (resolve relative/dirty values)
                if npz_col is not None and npz_col in df_sel2.columns:
                    with st.expander("Связь с Compare UI (NPZ) — если в CSV есть путь к NPZ", expanded=False):
                        st.caption(
                            "Если CSV содержит путь к NPZ (например, npz_path), можно передать выбранные файлы в Compare UI. "
                            "Мы пытаемся извлечь *.npz из строки и разрешить относительные пути (от папки CSV / workspace/osc)."
                        )

                        raw_npz: List[str] = []
                        for v in df_sel2[npz_col].tolist():
                            raw_npz.extend(_extract_npz_candidates(v))
                        raw_npz = [p for p in raw_npz if isinstance(p, str) and p.strip()]

                        if not raw_npz:
                            st.info(f"Колонка {npz_col} найдена, но в выделении нет распознаваемых *.npz.")
                        else:
                            roots: List[Path] = []
                            try:
                                roots.append(Path(csv_path).expanduser().resolve().parent)
                            except Exception:
                                pass
                            if csv_ref_path is not None:
                                try:
                                    roots.append(Path(csv_ref_path).expanduser().resolve().parent)
                                except Exception:
                                    pass
                            roots.append(Path(app_dir) / "workspace" / "osc")
                            roots.append(Path(app_dir) / "workspace")
                            roots.append(Path.cwd())
                            roots = [r for r in roots if isinstance(r, Path) and r.exists()]

                            resolved, status_df = _resolve_npz_paths(raw_npz, roots=roots)
                            st.caption(f"Найдено ссылок: {len(raw_npz)}. Существующих файлов: {len(resolved)}.")
                            if status_df is not None and len(status_df) > 0:
                                st.dataframe(status_df, width="stretch", height=220)

                            if resolved:
                                colP1, colP2 = st.columns([1.2, 1.0], gap="medium")
                                with colP1:
                                    if st.button("➡️ Передать выбранные NPZ в Compare UI", key="pi_push_to_compare_resolved"):
                                        st.session_state["cmp_external_paths"] = resolved
                                        st.session_state["cmp_ext_active"] = True
                                        # suggest a directory for Compare UI
                                        try:
                                            common = os.path.commonpath(resolved)
                                            if common:
                                                p = Path(common)
                                                st.session_state["cmp_npz_dir"] = str(p if p.is_dir() else p.parent)
                                        except Exception:
                                            pass
                                        st.success("Передано. Перейдите ниже к Compare UI (якорь #compare_npz).")
                                with colP2:
                                    st.markdown("[Перейти к Compare UI](#compare_npz)")

                                st.download_button(
                                    "⬇️ Скачать список путей (txt)",
                                    data="\n".join(resolved),
                                    file_name="pi_npz_paths.txt",
                                    mime="text/plain",
                                    key="pi_download_npz_list",
                                )
                            else:
                                st.info("Не удалось найти существующие NPZ. Проверьте относительные пути и корни.")
                elif npz_col is None:
                    st.caption("В CSV не обнаружена колонка с путями к NPZ (npz_path/npz_file/…).")

                # --- Alternative: traceability via NPZ index (no npz_path column required) ---
                with st.expander("Связь с Compare UI (NPZ) — через индекс осциллограмм (не требует колонки npz_path)", expanded=False):
                    st.caption(
                        "Здесь мы строим/загружаем индекс NPZ (workspace/osc_index_full.jsonl) и пытаемся сопоставить "
                        "выделенные строки CSV с NPZ по meta_json (run_id/seed/test_*/params_hash) и/или явным полям."
                    )

                    if not _HAS_OSC_INDEX or _osc_load_index is None:
                        st.info("Модуль osc_index.py недоступен (unexpected).")
                    else:
                        osc_dir_default = workspace_dir / "osc"
                        idx_path = _osc_default_index_path(app_dir) if _osc_default_index_path is not None else (workspace_dir / "osc_index_full.jsonl")

                        colI1, colI2, colI3 = st.columns([1.2, 1.0, 1.0], gap="medium")
                        with colI1:
                            extra_dirs_text = st.text_area(
                                "Доп. папки для сканирования NPZ (по одной на строку)",
                                value=str(osc_dir_default),
                                height=90,
                                key="pi_idx_extra_dirs",
                            )
                        with colI2:
                            idx_max = st.number_input("Max NPZ при индексации", min_value=50, max_value=50000, value=int(st.session_state.get("pi_idx_max") or 3000), step=50, key="pi_idx_max")
                            idx_quick = st.checkbox("Quick (не читать meta_json)", value=False, key="pi_idx_quick")
                        with colI3:
                            if st.button("🔄 Обновить индекс NPZ", key="pi_idx_build"):
                                dirs = []
                                for line in str(extra_dirs_text).splitlines():
                                    line = line.strip()
                                    if not line:
                                        continue
                                    pdir = Path(line).expanduser()
                                    if pdir.exists():
                                        dirs.append(pdir)
                                if not dirs:
                                    dirs = [osc_dir_default]
                                try:
                                    df_idx_new = _osc_build_or_update_index(
                                        dirs,
                                        index_path=Path(idx_path),
                                        recursive=True,
                                        max_files=int(idx_max),
                                        quick=bool(idx_quick),
                                    )
                                    st.session_state["pi_idx_df_cache"] = df_idx_new
                                    st.success(f"Индекс обновлён: записей {len(df_idx_new)}")
                                except Exception as e:
                                    st.error(f"Не удалось обновить индекс: {e}")

                        # Load cached or from disk
                        df_idx = None
                        try:
                            df_idx = st.session_state.get("pi_idx_df_cache")
                        except Exception:
                            df_idx = None
                        if df_idx is None or not isinstance(df_idx, pd.DataFrame):
                            try:
                                df_idx = _osc_load_index(Path(idx_path))
                            except Exception:
                                df_idx = pd.DataFrame()

                        if df_idx is None:
                            df_idx = pd.DataFrame()

                        if len(df_idx) == 0:
                            st.info("Индекс пуст. Нажмите «Обновить индекс NPZ» и проверьте папку workspace/osc.")
                        else:
                            st.caption(f"Индекс: {len(df_idx)} NPZ. Файл: {Path(idx_path).name}")

                            # roots for resolving explicit paths inside CSV rows
                            roots: List[Path] = []
                            try:
                                roots.append(Path(csv_path).expanduser().resolve().parent)
                            except Exception:
                                pass
                            if csv_ref_path is not None:
                                try:
                                    roots.append(Path(csv_ref_path).expanduser().resolve().parent)
                                except Exception:
                                    pass
                            roots.append(osc_dir_default)
                            roots.append(workspace_dir)
                            roots.append(Path.cwd())
                            roots = [r for r in roots if r.exists()]

                            # Map current selection -> npz
                            try:
                                map_df = _osc_map_rows_to_npz(df_sel2, df_idx, roots=roots, max_per_row=3)
                            except Exception as e:
                                st.error(f"Ошибка маппинга CSV→NPZ: {e}")
                                map_df = pd.DataFrame()

                            if map_df is not None and len(map_df) > 0:
                                ok_best = [p for p in map_df.get("npz_best", []).tolist() if isinstance(p, str) and p]
                                ok_best = list(dict.fromkeys(ok_best))  # uniq
                                st.write(f"Найдено NPZ для выделения: {len(ok_best)} (из {len(map_df)})")

                                with st.expander("Таблица маппинга (CSV _row → NPZ)", expanded=False):
                                    st.dataframe(map_df, width="stretch", height=240)

                                if ok_best:
                                    colT1, colT2 = st.columns([1.2, 1.0], gap="medium")
                                    with colT1:
                                        if st.button("➡️ Передать найденные NPZ в Compare UI", key="pi_push_to_compare_index"):
                                            st.session_state["cmp_external_paths"] = ok_best
                                            st.session_state["cmp_ext_active"] = True
                                            # suggest a directory for Compare UI
                                            try:
                                                common = os.path.commonpath(ok_best)
                                                if common:
                                                    pcommon = Path(common)
                                                    st.session_state["cmp_npz_dir"] = str(pcommon if pcommon.is_dir() else pcommon.parent)
                                            except Exception:
                                                pass
                                            st.success("Передано. Перейдите ниже к Compare UI (якорь #compare_npz).")
                                    with colT2:
                                        st.markdown("[Перейти к Compare UI](#compare_npz)")

                                    st.download_button(
                                        "⬇️ Скачать список NPZ (txt)",
                                        data="\n".join(ok_best),
                                        file_name="pi_npz_best_paths.txt",
                                        mime="text/plain",
                                        key="pi_download_npz_best_txt",
                                    )
                            else:
                                st.info("Не удалось сопоставить выделение с NPZ по индексу. "
                                        "Проверьте, что NPZ экспортировались с meta_json (run_id/test_*/seed/params_hash) или добавьте npz_path в CSV.")


    # -----------------------------
    # Tab 1: Overview matrix
    # -----------------------------
    with tab_matrix:
        st.subheader("Матрица влияний: корреляции inputs×outputs")
        st.caption("Подходит для быстрого «скрининга»: какие параметры монотонно связаны с какими выходами.")

        colM1, colM2, colM3 = st.columns([1.0, 1.0, 1.2], gap="medium")
        with colM1:
            cluster_axes = st.checkbox("Кластеризовать оси (|corr|) для читаемости", value=False, key="pi_cluster_axes", disabled=(not _HAS_SCIPY))
            if not _HAS_SCIPY:
                st.caption("SciPy не установлен — кластеризация недоступна.")
        with colM2:
            show_abs = st.checkbox("Показывать |corr| (вместо signed)", value=False, key="pi_show_abs")
        with colM3:
            st.caption("Сильная корреляция ≠ причинность. Но это хорошая отправная точка для инженерного анализа.")

        matA = _corr_submatrix(df_num_sel, inputs, outputs, str(corr_method))
        matB = _corr_submatrix(df_num_ref_sel, inputs, outputs, str(corr_method)) if (has_ref and df_num_ref_sel is not None) else pd.DataFrame()

        if matA.empty:
            st.info("Недостаточно данных/пересечения колонок для корреляций.")
        else:
            view_opts = ["A: primary"]
            if has_ref and not matB.empty:
                view_opts += ["B: reference", "Δ: A-B"]
            view = st.radio("Показать", options=view_opts, index=0, horizontal=True, key="pi_matrix_view")

            if view.startswith("B") and not matB.empty:
                mat_base = matB
                df_for_order = df_num_ref_sel
                subtitle = f"reference (n={len(df_num_ref_sel)})"
            elif view.startswith("Δ") and (not matB.empty):
                # Align on common columns
                common_out = [o for o in matA.index if o in matB.index]
                common_in = [p for p in matA.columns if p in matB.columns]
                mat_base = matA.loc[common_out, common_in] - matB.loc[common_out, common_in]
                df_for_order = df_num_sel
                subtitle = f"Δ (A-B), primary n={len(df_num_sel)}, ref n={len(df_num_ref_sel)}"
            else:
                mat_base = matA
                df_for_order = df_num_sel
                subtitle = f"primary (n={len(df_num_sel)})"

            # reorder
            in_order = [p for p in inputs if p in mat_base.columns]
            out_order = [o for o in outputs if o in mat_base.index]
            if cluster_axes and df_for_order is not None:
                in_order = _cluster_order_abs_corr(df_for_order, in_order, str(corr_method))
                out_order = _cluster_order_abs_corr(df_for_order, out_order, str(corr_method))

            mat2 = mat_base.loc[out_order, in_order].copy()

            if view.startswith("Δ"):
                # Δ-correlation has range [-2, 2], but usually within [-1, 1].
                mat_plot = mat2.abs() if show_abs else mat2
                scale = "RdBu" if not show_abs else "Viridis"
                if show_abs:
                    zmin, zmax = 0.0, float(min(2.0, np.nanmax(mat_plot.to_numpy(dtype=float)))) if np.isfinite(mat_plot.to_numpy(dtype=float)).any() else 1.0
                else:
                    lim = float(np.nanquantile(np.abs(mat_plot.to_numpy(dtype=float)), 0.98)) if np.isfinite(mat_plot.to_numpy(dtype=float)).any() else 1.0
                    lim = float(max(0.25, min(2.0, lim)))
                    zmin, zmax = -lim, lim
                title = f"Δ корреляции ({corr_method}) outputs×inputs — {subtitle}"
            else:
                if show_abs:
                    mat_plot = mat2.abs()
                    zmin, zmax = 0.0, 1.0
                    scale = "Viridis"
                else:
                    mat_plot = mat2
                    zmin, zmax = -1.0, 1.0
                    scale = "RdBu"
                title = f"Корреляция ({corr_method}) outputs×inputs — {subtitle}"

            fig = px.imshow(
                mat_plot,
                aspect="auto",
                color_continuous_scale=scale,
                zmin=float(zmin),
                zmax=float(zmax),
                title=title,
            )
            fig.update_layout(height=max(560, 18 * len(mat_plot.index) + 180), margin=dict(l=40, r=10, t=70, b=40))
            safe_plotly_chart(st, fig, key="pi_corr_heatmap")

            if view.startswith("Δ"):
                topd = _rank_top_abs(mat2, top_k=int(top_k))
                if len(topd):
                    st.markdown("**Где связи изменились сильнее всего (top |Δ corr| на output):**")
                    topd2 = topd.copy()
                    topd2["param"] = topd2["param"].map(_short_name)
                    topd2 = topd2.rename(columns={"corr": "delta_corr"})
                    st.dataframe(topd2, width="stretch", height=420)
            else:
                top = _rank_top_abs(mat2, top_k=int(top_k))
                if len(top):
                    st.markdown("**Топ влияний по |corr| (на каждый output):**")
                    top2 = top.copy()
                    top2["param"] = top2["param"].map(_short_name)
                    st.dataframe(top2, width="stretch", height=420)

    # -----------------------------
    # Tab 2: Mutual Information (nonlinear N→N)
    # -----------------------------
    with tab_mi:
        st.subheader("Нелинейные связи: Mutual Information (MI) inputs×outputs")
        st.caption(
            "MI помогает ловить нелинейные зависимости, которые корреляция может пропустить. "
            "Оценка через kNN чувствительна к масштабу — поэтому X стандартизируется."
        )

        if (not _HAS_SKLEARN) or mutual_info_regression is None:
            st.warning("scikit-learn недоступен — MI вкладка отключена.")
        else:
            colMI1, colMI2, colMI3, colMI4 = st.columns([1.0, 1.1, 1.1, 1.0], gap="medium")
            with colMI1:
                mi_neighbors = st.slider(
                    "kNN (n_neighbors)",
                    min_value=2,
                    max_value=20,
                    value=int(st.session_state.get("pi_mi_neighbors") or 5),
                    step=1,
                    key="pi_mi_neighbors",
                )
            with colMI2:
                mi_max_rows = st.number_input(
                    "Макс. строк для MI (сэмплинг)",
                    min_value=200,
                    max_value=50000,
                    value=int(st.session_state.get("pi_mi_max_rows") or 5000),
                    step=200,
                    key="pi_mi_max_rows",
                )
            with colMI3:
                mi_norm = st.checkbox("Нормировать по каждому output (0..1)", value=True, key="pi_mi_norm")
                mi_sort = st.checkbox("Сортировать оси по суммарной MI", value=True, key="pi_mi_sort")
            with colMI4:
                view_opts = ["A: primary"]
                if has_ref and df_num_ref_sel is not None:
                    view_opts += ["B: reference", "Δ: A-B"]
                mi_view = st.radio("Показать", options=view_opts, index=0, horizontal=True, key="pi_mi_view")

            with st.spinner("Считаю MI..."):
                matA = _mutual_info_submatrix(
                    df_num_sel,
                    inputs,
                    outputs,
                    n_neighbors=int(mi_neighbors),
                    seed=int(seed),
                    max_rows=int(mi_max_rows),
                    normalize_per_output=bool(mi_norm),
                )
                matB = (
                    _mutual_info_submatrix(
                        df_num_ref_sel,
                        inputs,
                        outputs,
                        n_neighbors=int(mi_neighbors),
                        seed=int(seed),
                        max_rows=int(mi_max_rows),
                        normalize_per_output=bool(mi_norm),
                    )
                    if (has_ref and df_num_ref_sel is not None)
                    else pd.DataFrame()
                )

            if matA.empty:
                st.info("Недостаточно данных/пересечения колонок для MI.")
            else:
                if mi_view.startswith("B") and (not matB.empty):
                    mat_base = matB
                    subtitle = f"reference (n={len(df_num_ref_sel)})"
                elif mi_view.startswith("Δ") and (not matB.empty):
                    common_out = [o for o in matA.index if o in matB.index]
                    common_in = [p for p in matA.columns if p in matB.columns]
                    mat_base = matA.loc[common_out, common_in] - matB.loc[common_out, common_in]
                    subtitle = f"Δ (A-B), primary n={len(df_num_sel)}, ref n={len(df_num_ref_sel)}"
                else:
                    mat_base = matA
                    subtitle = f"primary (n={len(df_num_sel)})"

                # order by selection order, then optional sort by sums
                in_order = [p for p in inputs if p in mat_base.columns]
                out_order = [o for o in outputs if o in mat_base.index]
                mat2 = mat_base.loc[out_order, in_order].copy()
                if mi_sort:
                    try:
                        in_order = mat2.sum(axis=0).sort_values(ascending=False).index.tolist()
                        out_order = mat2.sum(axis=1).sort_values(ascending=False).index.tolist()
                        mat2 = mat2.loc[out_order, in_order]
                    except Exception:
                        pass

                if mi_view.startswith("Δ"):
                    scale = "RdBu"
                    arr = mat2.to_numpy(dtype=float)
                    lim = float(np.nanquantile(np.abs(arr), 0.98)) if np.isfinite(arr).any() else 1.0
                    lim = float(max(0.05, min(2.0, lim)))
                    zmin, zmax = -lim, lim
                    title = f"Δ MI (A-B) outputs×inputs — {subtitle}"
                else:
                    scale = "Viridis"
                    if bool(mi_norm):
                        zmin, zmax = 0.0, 1.0
                    else:
                        arr = mat2.to_numpy(dtype=float)
                        zmax = float(np.nanquantile(arr, 0.98)) if np.isfinite(arr).any() else 1.0
                        zmax = float(max(1e-9, zmax))
                        zmin = 0.0
                    title = f"Mutual Information outputs×inputs — {subtitle}"

                fig = px.imshow(
                    mat2,
                    aspect="auto",
                    color_continuous_scale=scale,
                    zmin=float(zmin),
                    zmax=float(zmax),
                    title=title,
                )
                fig.update_layout(height=max(560, 18 * len(mat2.index) + 180), margin=dict(l=40, r=10, t=70, b=40))
                safe_plotly_chart(st, fig, key="pi_mi_heatmap")

                # top edges table
                rows = []
                for o in mat2.index:
                    s = mat2.loc[o].dropna()
                    if s.empty:
                        continue
                    if mi_view.startswith("Δ"):
                        ss = s.abs().sort_values(ascending=False).head(int(top_k))
                        for p, vabs in ss.items():
                            rows.append({"output": o, "param": p, "delta_mi": float(mat2.loc[o, p]), "abs_delta": float(vabs)})
                    else:
                        ss = s.sort_values(ascending=False).head(int(top_k))
                        for p, v in ss.items():
                            rows.append({"output": o, "param": p, "mi": float(v)})
                if rows:
                    topmi = pd.DataFrame(rows)
                    topmi["param"] = topmi["param"].map(_short_name)
                    if mi_view.startswith("Δ"):
                        topmi = topmi.sort_values(["output", "abs_delta"], ascending=[True, False])
                        st.markdown("**Топ изменений по |Δ MI| (на output):**")
                    else:
                        topmi = topmi.sort_values(["output", "mi"], ascending=[True, False])
                        st.markdown("**Топ влияний по MI (на output):**")
                    st.dataframe(topmi, width="stretch", height=420)

    # -----------------------------
    # Tab 3: SPLOM (scatter matrix / small multiples)
    # -----------------------------
    with tab_splom:
        st.subheader("SPLOM: матрица scatter (small multiples) для выбранных колонок")
        st.caption("Полезно, когда надо быстро увидеть парные зависимости в малом подмножестве переменных (2–8).")

        if not _HAS_PLOTLY:
            st.warning("Plotly недоступен.")
        else:
            dset_opts = ["A: primary"] + (["B: reference"] if (has_ref and df_vis_ref is not None) else [])
            dset = st.radio("Набор", options=dset_opts, index=0, horizontal=True, key="pi_splom_dataset")
            df_base = df_vis_ref if dset.startswith("B") else df_vis

            all_dims = [c for c in (inputs + outputs) if c in df_base.columns]
            default_dims = all_dims[:4] if len(all_dims) >= 4 else all_dims[:]
            dims = st.multiselect(
                "Колонки (2–8)",
                options=all_dims,
                default=st.session_state.get("pi_splom_dims") or default_dims,
                key="pi_splom_dims",
            )
            if len(dims) < 2:
                st.info("Выберите хотя бы 2 колонки.")
            else:
                if len(dims) > 8:
                    st.warning("Выбрано слишком много колонок для SPLOM — будет использовано первые 8.")
                    dims = dims[:8]

                color_opt = ["(нет)"] + [c for c in outputs if c in df_base.columns]
                color = st.selectbox("Цвет", options=color_opt, index=0, key="pi_splom_color")
                color_col = None if color == "(нет)" else color

                dfx = df_base.replace([np.inf, -np.inf], np.nan).dropna(subset=dims, how="any")
                if len(dfx) < 5:
                    st.info("Слишком мало строк после фильтрации NaN/inf.")
                else:
                    fig = px.scatter_matrix(
                        dfx,
                        dimensions=dims,
                        color=color_col,
                        title=f"SPLOM (n={len(dfx)}) — {dset}",
                    )
                    fig.update_traces(diagonal_visible=False, marker=dict(size=3, opacity=0.65))
                    fig.update_layout(height=820, margin=dict(l=40, r=10, t=70, b=40))
                    safe_plotly_chart(st, fig, key="pi_splom")

    # -----------------------------
    # Tab 4: Sankey influence map
    # -----------------------------
    with tab_sankey:
        st.subheader("Сеть влияний (Sankey): параметры → метрики")
        st.caption("Наглядно показывает N→N связи: какие параметры чаще всего «кормят» какие метрики.")

        df_num_net = df_num_sel
        if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
            ds = st.radio(
                "Датасет",
                options=["A: primary", "B: reference"],
                index=0,
                horizontal=True,
                key="pi_sankey_dataset",
            )
            df_num_net = df_num_ref_sel if ds.startswith("B") else df_num_sel

        mat = _corr_submatrix(df_num_net, inputs, outputs, str(corr_method))
        if mat.empty:
            st.info("Нет данных для построения Sankey.")
        else:
            colS1, colS2, colS3 = st.columns([1.1, 1.1, 1.0], gap="medium")
            with colS1:
                thr = st.slider("Порог |corr|", min_value=0.0, max_value=1.0, value=float(st.session_state.get("pi_sankey_thr") or 0.35), step=0.05, key="pi_sankey_thr")
            with colS2:
                edges_cap = st.number_input("Макс. рёбер", min_value=20, max_value=800, value=int(st.session_state.get("pi_sankey_cap") or 200), step=20, key="pi_sankey_cap")
            with colS3:
                per_out = st.number_input("Топ на output", min_value=2, max_value=40, value=int(st.session_state.get("pi_sankey_per_out") or 10), step=1, key="pi_sankey_per_out")

            # build edges list
            edges = []
            for o in mat.index:
                s = mat.loc[o].dropna()
                if s.empty:
                    continue
                s_abs = s.abs().sort_values(ascending=False).head(int(per_out))
                for p, vabs in s_abs.items():
                    v = float(mat.loc[o, p])
                    if not np.isfinite(v):
                        continue
                    if float(abs(v)) < float(thr):
                        continue
                    edges.append((p, o, float(abs(v)), float(v)))

            if not edges:
                st.info("Нет рёбер выше порога. Уменьшите порог или увеличьте данные.")
            else:
                # cap edges
                edges.sort(key=lambda t: t[2], reverse=True)
                edges = edges[: int(edges_cap)]

                # nodes: params first, outputs after (so flow left->right)
                params = sorted({e[0] for e in edges})
                outs = sorted({e[1] for e in edges})

                nodes = [_short_name(p) for p in params] + [str(o) for o in outs]
                node_index = {name: i for i, name in enumerate(nodes)}

                sources = []
                targets = []
                values = []
                # optional: sign for hover
                signs = []
                for p, o, w, v in edges:
                    src = node_index.get(_short_name(p))
                    tgt = node_index.get(str(o))
                    if src is None or tgt is None:
                        continue
                    sources.append(int(src))
                    targets.append(int(tgt))
                    values.append(float(w))
                    signs.append(float(v))

                fig = go.Figure(
                    data=[
                        go.Sankey(
                            arrangement="snap",
                            node=dict(
                                pad=12,
                                thickness=14,
                                line=dict(width=0.5),
                                label=nodes,
                            ),
                            link=dict(
                                source=sources,
                                target=targets,
                                value=values,
                                customdata=signs,
                                hovertemplate="|corr|=%{value:.3f}<br>signed=%{customdata:.3f}<extra></extra>",
                            ),
                        )
                    ]
                )
                fig.update_layout(title=f"Sankey influence map (|corr|≥{thr:.2f}, edges={len(values)})", height=720, margin=dict(l=20, r=20, t=70, b=20))
                safe_plotly_chart(st, fig, key="pi_sankey")

                with st.expander("Список рёбер (таблица)", expanded=False):
                    df_edges = pd.DataFrame(edges, columns=["param", "output", "abs_corr", "corr"])
                    df_edges["param"] = df_edges["param"].map(_short_name)
                    st.dataframe(df_edges, width="stretch", height=420)

    # -----------------------------
    # Tab 3: Pairs scatter
    # -----------------------------
    with tab_pairs:
        st.subheader("Small‑multiples scatter: выбранная метрика vs набор параметров")
        y = st.selectbox("Выход (Y)", options=outputs, index=0, key="pi_pairs_y")

        mat = _corr_submatrix(df_num_sel, inputs, outputs, str(corr_method))
        suggested = []
        try:
            if not mat.empty and y in mat.index:
                s = mat.loc[y].dropna().abs().sort_values(ascending=False)
                suggested = s.head(12).index.tolist()
        except Exception:
            suggested = []

        x_params = st.multiselect("Параметры (X) для парного просмотра", options=inputs, default=(st.session_state.get("pi_pairs_x") or (suggested or inputs[:8])), key="pi_pairs_x")

        if not x_params:
            st.info("Выберите параметры.")
        else:
            dfx = _sample_df(df_sel, int(max_rows_plot), seed=int(seed))
            n = len(x_params)
            ncols = 2
            nrows = int(math.ceil(n / ncols))
            fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=[_short_name(p) for p in x_params])

            color_vals = dfx[y] if y in dfx.columns else None
            cmin = float(np.nanmin(color_vals)) if color_vals is not None and len(color_vals) else None
            cmax = float(np.nanmax(color_vals)) if color_vals is not None and len(color_vals) else None

            for i, p in enumerate(x_params):
                r = i // ncols + 1
                c = i % ncols + 1
                if p not in dfx.columns or y not in dfx.columns:
                    continue
                x = dfx[p]
                yy = dfx[y]

                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=yy,
                        mode="markers",
                        marker=dict(size=5, opacity=0.6, color=color_vals, cmin=cmin, cmax=cmax, colorscale="Viridis", showscale=False),
                        hovertemplate=f"{_short_name(p)}=%{{x:.4g}}<br>{y}=%{{y:.4g}}<extra></extra>",
                    ),
                    row=r,
                    col=c,
                )

                # linear trend (quick)
                try:
                    xs = np.asarray(x, dtype=float)
                    ys = np.asarray(yy, dtype=float)
                    m = np.isfinite(xs) & np.isfinite(ys)
                    if m.sum() >= 10:
                        a, b = np.polyfit(xs[m], ys[m], deg=1)
                        xline = np.linspace(float(np.nanmin(xs[m])), float(np.nanmax(xs[m])), 60)
                        yline = a * xline + b
                        fig.add_trace(go.Scatter(x=xline, y=yline, mode="lines", line=dict(width=2), showlegend=False, hoverinfo='skip'), row=r, col=c)
                except Exception:
                    pass

                fig.update_xaxes(title_text=_short_name(p), row=r, col=c)
                fig.update_yaxes(title_text=y if c == 1 else "", row=r, col=c)

            fig.update_layout(
                height=max(560, 320 * nrows),
                title=f"{y}: зависимость от параметров (выборка до {len(dfx)} строк)",
                hovermode="closest",
                margin=dict(l=40, r=10, t=80, b=40),
            )
            safe_plotly_chart(st, fig, key="pi_pairs_grid")

    # -----------------------------
    # Tab 4: Parallel coordinates
    # -----------------------------
    with tab_parcoords:
        st.subheader("Параллельные координаты (многомерное сравнение)")
        st.caption("Полезно, когда нужно одновременно увидеть, как несколько параметров связаны с несколькими выходами.")

        color_by = st.selectbox("Цвет по метрике", options=outputs, index=0, key="pi_pc_color")
        cols_pc_default = []
        cols_pc_default.extend(inputs[: min(8, len(inputs))])
        cols_pc_default.append(color_by)
        for o in outputs:
            if o != color_by:
                cols_pc_default.append(o)
                break

        cols_pc = st.multiselect("Оси (колонки)", options=[*inputs, *outputs], default=(st.session_state.get("pi_pc_cols") or cols_pc_default), key="pi_pc_cols")
        scale_01 = st.checkbox("Нормировать оси в [0..1] (для читаемости)", value=True, key="pi_pc_scale01")

        dfp = _sample_df(df_sel, int(max_rows_plot), seed=int(seed)).copy()
        cols_pc = [c for c in cols_pc if c in dfp.columns]
        if len(cols_pc) < 2:
            st.info("Выберите минимум 2 колонки.")
        else:
            dfp = dfp[cols_pc].copy()
            dfp = dfp.replace([np.inf, -np.inf], np.nan).dropna(how="any")
            if len(dfp) < 5:
                st.info("Слишком мало строк после фильтрации NaN.")
            else:
                if scale_01:
                    for c in cols_pc:
                        v = dfp[c].to_numpy(dtype=float)
                        vmin = float(np.nanmin(v))
                        vmax = float(np.nanmax(v))
                        if np.isfinite(vmin) and np.isfinite(vmax) and (vmax - vmin) > 1e-12:
                            dfp[c] = (dfp[c] - vmin) / (vmax - vmin)

                fig = px.parallel_coordinates(
                    dfp,
                    dimensions=cols_pc,
                    color=(dfp[color_by] if color_by in dfp.columns else None),
                    color_continuous_scale=px.colors.sequential.Viridis,
                    title=f"Parallel coordinates (n={len(dfp)})",
                )
                fig.update_layout(height=680, margin=dict(l=40, r=20, t=70, b=40))
                safe_plotly_chart(st, fig, key="pi_parallel")

    # -----------------------------
    # Tab 5: N×N Sensitivity (глобальная важность + локальная чувствительность)
    # -----------------------------
    with tab_sens:
        st.subheader("N×N чувствительность: входы ↔ выходы (surrogate‑анализ)")
        st.caption(
            "Этот раздел отвечает на вопрос: **как изменение N параметров влияет на N показателей**. "
            "Мы совмещаем: (1) *глобальную* матрицу важностей (N×N) и (2) *локальную* чувствительность вокруг выбранного прогона "
            "(Jacobian/what‑if)."
        )

        if not _HAS_SKLEARN:
            st.warning("scikit-learn не установлен — surrogate/чувствительность недоступны.")
        else:
            tab_g, tab_l, tab_w, tab_i = st.tabs([
                "Глобальная матрица важностей (N×N)",
                "Локальная чувствительность (Jacobian)",
                "What‑if (быстрое сравнение)",
                "Интеракции (H) — пары параметров",
            ])

            # -------------------------
            # Helper: cached importance matrix (per-output)
            # -------------------------
            @st.cache_data(show_spinner=False)
            def _calc_importance_matrix_cached(
                df_num_in: pd.DataFrame,
                inputs_sel: tuple,
                outputs_sel: tuple,
                *,
                seed_i: int,
                n_estimators_i: int,
                test_size_f: float,
                n_repeats_i: int,
                method: str,
                max_rows_train: int,
            ) -> Tuple[pd.DataFrame, pd.Series]:
                # keep only required columns
                cols = list(inputs_sel) + list(outputs_sel)
                cols = [c for c in cols if c in df_num_in.columns]
                if not cols:
                    return pd.DataFrame(), pd.Series(dtype=float)

                df_s = df_num_in[cols].replace([np.inf, -np.inf], np.nan).dropna(how="any")
                if len(df_s) == 0:
                    return pd.DataFrame(), pd.Series(dtype=float)

                if max_rows_train > 0 and len(df_s) > int(max_rows_train):
                    df_s = df_s.sample(n=int(max_rows_train), random_state=int(seed_i))

                X_all = df_s[list(inputs_sel)].to_numpy(dtype=float)

                mats = {}
                r2_map = {}

                for ycol in outputs_sel:
                    if ycol not in df_s.columns:
                        continue
                    y_all = df_s[ycol].to_numpy(dtype=float)

                    # drop any NaN just in case
                    m = np.isfinite(X_all).all(axis=1) & np.isfinite(y_all)
                    X = X_all[m]
                    y = y_all[m]
                    if len(y) < 60:
                        continue

                    X_train, X_test, y_train, y_test = train_test_split(
                        X, y, test_size=float(test_size_f), random_state=int(seed_i)
                    )
                    model = RandomForestRegressor(
                        n_estimators=int(n_estimators_i),
                        random_state=int(seed_i),
                        n_jobs=-1,
                        max_features=1.0,
                    )
                    model.fit(X_train, y_train)

                    try:
                        y_pred = model.predict(X_test)
                        r2_map[ycol] = float(r2_score(y_test, y_pred))
                    except Exception:
                        r2_map[ycol] = float('nan')

                    meth = str(method or "permutation").lower()
                    if meth.startswith("imp"):
                        try:
                            imp = np.asarray(getattr(model, "feature_importances_", None), dtype=float)
                        except Exception:
                            imp = np.full((len(inputs_sel),), np.nan)
                    else:
                        try:
                            pi = permutation_importance(
                                model,
                                X_test,
                                y_test,
                                n_repeats=int(n_repeats_i),
                                random_state=int(seed_i),
                                n_jobs=-1,
                            )
                            imp = np.asarray(pi.importances_mean, dtype=float)
                        except Exception:
                            imp = np.full((len(inputs_sel),), np.nan)

                    mats[ycol] = imp

                if not mats:
                    return pd.DataFrame(), pd.Series(dtype=float)

                mat = pd.DataFrame(mats, index=list(inputs_sel)).T
                r2s = pd.Series(r2_map).reindex(mat.index)
                return mat, r2s

            # -------------------------
            # Helper: cached multi-output surrogate for local Jacobian/what-if
            # -------------------------
            @st.cache_resource(show_spinner=False)
            def _train_multi_surrogate_cached(
                df_num_in: pd.DataFrame,
                inputs_sel: tuple,
                outputs_sel: tuple,
                *,
                seed_i: int,
                n_estimators_i: int,
                test_size_f: float,
                max_rows_train: int,
            ) -> dict:
                cols = list(inputs_sel) + list(outputs_sel)
                cols = [c for c in cols if c in df_num_in.columns]
                if not cols:
                    return {}
                df_s = df_num_in[cols].replace([np.inf, -np.inf], np.nan).dropna(how="any")
                if len(df_s) == 0:
                    return {}
                if max_rows_train > 0 and len(df_s) > int(max_rows_train):
                    df_s = df_s.sample(n=int(max_rows_train), random_state=int(seed_i))

                X, Y = _prepare_xy_multi(df_s, list(inputs_sel), list(outputs_sel))
                if len(Y) < 60:
                    return {}

                model, r2_raw, r2_mean = _train_rf_multioutput(
                    X,
                    Y,
                    seed=int(seed_i),
                    n_estimators=int(n_estimators_i),
                    test_size=float(test_size_f),
                )

                # stats for steps and normalization
                x_min = np.nanmin(X, axis=0)
                x_max = np.nanmax(X, axis=0)
                try:
                    x_q05 = np.nanquantile(X, 0.05, axis=0)
                    x_q95 = np.nanquantile(X, 0.95, axis=0)
                except Exception:
                    x_q05 = x_min
                    x_q95 = x_max

                y_min = np.nanmin(Y, axis=0)
                y_max = np.nanmax(Y, axis=0)
                try:
                    y_q05 = np.nanquantile(Y, 0.05, axis=0)
                    y_q95 = np.nanquantile(Y, 0.95, axis=0)
                except Exception:
                    y_q05 = y_min
                    y_q95 = y_max

                return {
                    "model": model,
                    "r2_raw": np.asarray(r2_raw, dtype=float),
                    "r2_mean": float(r2_mean),
                    "x_min": np.asarray(x_min, dtype=float),
                    "x_max": np.asarray(x_max, dtype=float),
                    "x_q05": np.asarray(x_q05, dtype=float),
                    "x_q95": np.asarray(x_q95, dtype=float),
                    "y_min": np.asarray(y_min, dtype=float),
                    "y_max": np.asarray(y_max, dtype=float),
                    "y_q05": np.asarray(y_q05, dtype=float),
                    "y_q95": np.asarray(y_q95, dtype=float),
                }

            # =============================================================
            # TAB G: GLOBAL IMPORTANCE MATRIX
            # =============================================================
            with tab_g:
                view_opts = ["A: primary"]
                if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                    view_opts += ["B: reference", "Δ: A-B"]

                view = st.radio(
                    "Вид матрицы",
                    options=view_opts,
                    index=0,
                    horizontal=True,
                    key="pi_sens_view",
                )

                colG1, colG2, colG3, colG4 = st.columns([1.2, 1.1, 1.0, 1.0], gap="medium")
                with colG1:
                    imp_method = st.radio(
                        "Метод важности",
                        options=["Permutation (holdout)", "Impurity (fast)"],
                        index=0,
                        horizontal=True,
                        key="pi_sens_imp_method",
                        help="Permutation importance устойчивее (считает на holdout), но медленнее. Impurity быстрее, но более смещённый.",
                    )
                with colG2:
                    n_estimators = st.slider(
                        "RF деревья",
                        min_value=80,
                        max_value=900,
                        value=int(st.session_state.get("pi_sens_rf_n") or 260),
                        step=40,
                        key="pi_sens_rf_n",
                    )
                with colG3:
                    test_size = st.slider(
                        "Holdout доля",
                        min_value=0.1,
                        max_value=0.5,
                        value=float(st.session_state.get("pi_sens_test") or 0.25),
                        step=0.05,
                        key="pi_sens_test",
                    )
                with colG4:
                    max_rows_train = st.number_input(
                        "Строк для обучения (0 = все)",
                        min_value=0,
                        max_value=200000,
                        value=int(st.session_state.get("pi_sens_train_rows") or 12000),
                        step=1000,
                        key="pi_sens_train_rows",
                    )

                n_repeats = 10
                if imp_method.startswith("Permutation"):
                    n_repeats = st.slider(
                        "Permutation repeats",
                        min_value=3,
                        max_value=40,
                        value=int(st.session_state.get("pi_sens_rep") or 12),
                        step=1,
                        key="pi_sens_rep",
                    )

                # Defaults: keep UI readable
                def_out = st.session_state.get("pi_sens_outs") or outputs[: min(8, len(outputs))]
                def_in = st.session_state.get("pi_sens_ins") or inputs[: min(14, len(inputs))]

                outs_sel = st.multiselect(
                    "Выходы (строки матрицы)",
                    options=outputs,
                    default=def_out,
                    key="pi_sens_outs",
                )
                ins_sel = st.multiselect(
                    "Параметры (колонки матрицы)",
                    options=inputs,
                    default=def_in,
                    key="pi_sens_ins",
                )

                if len(outs_sel) < 1 or len(ins_sel) < 1:
                    st.info("Выберите хотя бы 1 выход и 1 параметр.")
                else:
                    auto = st.checkbox(
                        "Автообновление (может быть тяжёлым)",
                        value=bool(st.session_state.get("pi_sens_auto") or False),
                        key="pi_sens_auto",
                    )
                    go = auto or st.button("Построить/обновить матрицу", key="pi_sens_run")

                    if go:
                        method_key = "impurity" if imp_method.startswith("Imp") else "permutation"

                        with st.spinner("Считаю матрицу важностей..."):
                            matA, r2A = _calc_importance_matrix_cached(
                                df_num_sel,
                                tuple(ins_sel),
                                tuple(outs_sel),
                                seed_i=int(seed),
                                n_estimators_i=int(n_estimators),
                                test_size_f=float(test_size),
                                n_repeats_i=int(n_repeats),
                                method=method_key,
                                max_rows_train=int(max_rows_train),
                            )

                            matB = pd.DataFrame()
                            r2B = pd.Series(dtype=float)
                            if view.startswith("B") or view.startswith("Δ"):
                                if has_ref and (df_num_ref_sel is not None):
                                    matB, r2B = _calc_importance_matrix_cached(
                                        df_num_ref_sel,
                                        tuple(ins_sel),
                                        tuple(outs_sel),
                                        seed_i=int(seed),
                                        n_estimators_i=int(n_estimators),
                                        test_size_f=float(test_size),
                                        n_repeats_i=int(n_repeats),
                                        method=method_key,
                                        max_rows_train=int(max_rows_train),
                                    )

                        # choose view
                        mat = matA
                        subtitle = f"A: n={len(df_num_sel)}"
                        if view.startswith("B"):
                            mat = matB
                            subtitle = f"B: n={len(df_num_ref_sel) if df_num_ref_sel is not None else 0}"
                        elif view.startswith("Δ"):
                            # align common
                            common_out = [o for o in outs_sel if (o in matA.index and o in matB.index)]
                            common_in = [x for x in ins_sel if (x in matA.columns and x in matB.columns)]
                            if common_out and common_in:
                                mat = matA.loc[common_out, common_in] - matB.loc[common_out, common_in]
                            else:
                                mat = pd.DataFrame()
                            subtitle = "Δ (A-B)"

                        if mat is None or mat.empty:
                            st.warning("Матрица пустая (мало данных после фильтрации/нет общих колонок).")
                        else:
                            # optionally normalize rows for comparability
                            colN1, colN2, colN3 = st.columns([1.0, 1.0, 1.2], gap="medium")
                            with colN1:
                                show_abs = st.checkbox("|значения|", value=not view.startswith("Δ"), key="pi_sens_abs")
                            with colN2:
                                norm_row = st.checkbox("Нормировать по строкам", value=True, key="pi_sens_norm_row")
                            with colN3:
                                order_mode = st.selectbox(
                                    "Порядок осей",
                                    options=["как выбрано", "по сумме |влияния|"],
                                    index=1,
                                    key="pi_sens_order",
                                )

                            mat_v = mat.copy()
                            if show_abs:
                                mat_v = mat_v.abs()

                            if norm_row:
                                try:
                                    denom = mat_v.max(axis=1).replace(0.0, np.nan)
                                    mat_v = mat_v.div(denom, axis=0)
                                except Exception:
                                    pass

                            if order_mode.startswith("по"):
                                try:
                                    in_order = mat_v.abs().mean(axis=0).sort_values(ascending=False).index.tolist()
                                    out_order = mat_v.abs().mean(axis=1).sort_values(ascending=False).index.tolist()
                                    mat_v = mat_v.loc[out_order, in_order]
                                except Exception:
                                    pass

                            # Heatmap
                            try:
                                z = mat_v.to_numpy(dtype=float)
                                vmax = float(np.nanmax(np.abs(z))) if np.isfinite(z).any() else 1.0
                                if view.startswith("Δ") and (not show_abs):
                                    zmin, zmax = -vmax, vmax
                                    colorscale = "RdBu"
                                else:
                                    zmin, zmax = 0.0, vmax
                                    colorscale = "Viridis"

                                fig = go.Figure(
                                    data=go.Heatmap(
                                        z=z,
                                        x=[_short_name(c) for c in mat_v.columns],
                                        y=[str(r) for r in mat_v.index],
                                        colorscale=colorscale,
                                        zmin=zmin,
                                        zmax=zmax,
                                        hovertemplate="%{y}<br>%{x}: %{z:.4g}<extra></extra>",
                                    )
                                )
                                fig.update_layout(
                                    title=f"Матрица важностей outputs×inputs — {subtitle}",
                                    height=max(520, 24 * len(mat_v.index) + 120),
                                    margin=dict(l=40, r=10, t=70, b=40),
                                )
                                safe_plotly_chart(st, fig, key="pi_sens_heatmap")
                            except Exception as e:
                                st.error(f"Heatmap: ошибка: {e}")

                            # Aggregated importance per input
                            try:
                                agg_in = mat_v.abs().mean(axis=0).sort_values(ascending=False)
                                topn = min(30, len(agg_in))
                                fig2 = _bar_figure(
                                    names=[_short_name(x) for x in agg_in.index[:topn]][::-1],
                                    values=[float(v) for v in agg_in.values[:topn]][::-1],
                                    title="Суммарное влияние по параметрам (mean |row|)",
                                    horizontal=True,
                                )
                                if fig2 is not None:
                                    safe_plotly_chart(st, fig2, key="pi_sens_bar_in")
                            except Exception:
                                pass

                            # R² table (only makes sense for A/B)
                            with st.expander("Качество surrogate (R² на holdout)", expanded=False):
                                if view.startswith("B") and (not r2B.empty):
                                    st.dataframe(r2B.rename("r2").to_frame(), width="stretch", height=220)
                                else:
                                    st.dataframe(r2A.rename("r2").to_frame(), width="stretch", height=220)

                            # Export
                            try:
                                st.download_button(
                                    "⬇️ Скачать матрицу (CSV)",
                                    data=mat.to_csv(index=True).encode("utf-8"),
                                    file_name="pi_sensitivity_matrix.csv",
                                    mime="text/csv",
                                    key="pi_sens_dl_mat",
                                )
                            except Exception:
                                pass

            # =============================================================
            # TAB L: LOCAL JACOBIAN
            # =============================================================
            with tab_l:
                st.markdown('**Локальная чувствительность** ≈ "Jacobian" вокруг выбранной строки CSV: меняем вход на небольшой шаг и смотрим Δ выходов через surrogate.')

                ds_opts = ["A: primary"]
                if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                    ds_opts.append("B: reference")

                colL0, colL1, colL2, colL3 = st.columns([1.0, 1.2, 1.0, 1.0], gap="medium")
                with colL0:
                    ds = st.radio("Датасет", options=ds_opts, index=0, horizontal=True, key="pi_loc_ds")
                with colL1:
                    n_estimators_l = st.slider(
                        "RF деревья",
                        min_value=80,
                        max_value=900,
                        value=int(st.session_state.get("pi_loc_rf_n") or 300),
                        step=40,
                        key="pi_loc_rf_n",
                    )
                with colL2:
                    test_size_l = st.slider(
                        "Holdout",
                        min_value=0.1,
                        max_value=0.5,
                        value=float(st.session_state.get("pi_loc_test") or 0.25),
                        step=0.05,
                        key="pi_loc_test",
                    )
                with colL3:
                    max_rows_l = st.number_input(
                        "Строк для обучения",
                        min_value=0,
                        max_value=200000,
                        value=int(st.session_state.get("pi_loc_train_rows") or 15000),
                        step=1000,
                        key="pi_loc_train_rows",
                    )

                # columns selection (reuse from global if possible)
                outs_default = st.session_state.get("pi_sens_outs") or outputs[: min(8, len(outputs))]
                ins_default = st.session_state.get("pi_sens_ins") or inputs[: min(14, len(inputs))]

                outs_loc = st.multiselect(
                    "Выходы (для Jacobian)",
                    options=outputs,
                    default=outs_default,
                    key="pi_loc_outs",
                )
                ins_loc = st.multiselect(
                    "Параметры (для Jacobian)",
                    options=inputs,
                    default=ins_default,
                    key="pi_loc_ins",
                )

                if len(outs_loc) < 1 or len(ins_loc) < 1:
                    st.info("Выберите хотя бы 1 выход и 1 параметр.")
                else:
                    # pick baseline row
                    if ds.startswith("B") and (df_ref_sel is not None):
                        df_base = df_ref_sel
                        row_col = "_row_ref" if "_row_ref" in df_base.columns else (groups_ref.id_col if groups_ref and groups_ref.id_col in df_base.columns else df_base.columns[0])
                        id_base = id_col_ref
                    else:
                        df_base = df_sel
                        row_col = "_row"
                        id_base = id_col

                    # if we have a selection (only for A), prefer it
                    base_options = df_base[row_col].tolist() if row_col in df_base.columns else list(range(len(df_base)))

                    def _fmt_row(v):
                        try:
                            if row_col in df_base.columns:
                                rr = df_base.loc[df_base[row_col] == v].head(1)
                            else:
                                rr = df_base.iloc[int(v): int(v) + 1]
                            if len(rr) == 0:
                                return str(v)
                            s = f"{v}"
                            if id_base is not None and id_base in rr.columns:
                                s += f" | id={rr[id_base].iloc[0]}"
                            return s
                        except Exception:
                            return str(v)

                    # default baseline: first selected row (for A)
                    idx0 = 0
                    if (not ds.startswith("B")) and isinstance(sel_rows, list) and len(sel_rows) > 0 and row_col == "_row":
                        try:
                            idx0 = max(0, base_options.index(int(sel_rows[0])))
                        except Exception:
                            idx0 = 0

                    baseline = st.selectbox(
                        "Базовая строка",
                        options=base_options,
                        index=int(idx0) if base_options else 0,
                        format_func=_fmt_row,
                        key="pi_loc_baseline",
                    )

                    colS1, colS2, colS3, colS4 = st.columns([1.0, 1.0, 1.0, 1.2], gap="medium")
                    with colS1:
                        eps = st.slider(
                            "Шаг (доля диапазона)",
                            min_value=0.002,
                            max_value=0.20,
                            value=float(st.session_state.get("pi_loc_eps") or 0.02),
                            step=0.002,
                            key="pi_loc_eps",
                            help="ΔX = eps * (q95-q05) по каждому параметру.",
                        )
                    with colS2:
                        diff_mode = st.radio(
                            "Разность",
                            options=["forward", "central"],
                            index=0,
                            horizontal=True,
                            key="pi_loc_diff",
                        )
                    with colS3:
                        show_mode = st.radio(
                            "Показывать",
                            options=["ΔY (+step)", "dY/dX"],
                            index=0,
                            horizontal=True,
                            key="pi_loc_show",
                        )
                    with colS4:
                        norm_y = st.checkbox(
                            "Нормировать по диапазону Y (q95-q05)",
                            value=True,
                            key="pi_loc_norm_y",
                        )

                    clip_to_data = st.checkbox(
                        "Ограничивать X в [min..max] обучающей выборки", value=True, key="pi_loc_clip"
                    )

                    # Train surrogate
                    df_num_base = df_num_ref_sel if (ds.startswith("B") and df_num_ref_sel is not None) else df_num_sel
                    pack = _train_multi_surrogate_cached(
                        df_num_base,
                        tuple(ins_loc),
                        tuple(outs_loc),
                        seed_i=int(seed),
                        n_estimators_i=int(n_estimators_l),
                        test_size_f=float(test_size_l),
                        max_rows_train=int(max_rows_l),
                    )

                    if not pack:
                        st.warning("Не удалось обучить multi-output surrogate (мало данных/NaN).")
                    else:
                        model = pack["model"]
                        r2_raw = pack["r2_raw"]
                        r2_mean = pack["r2_mean"]

                        st.caption(f"Multi-output surrogate: mean R²≈{r2_mean:.3f} (по выбранным выходам)")

                        # x0
                        try:
                            if row_col in df_base.columns:
                                rr = df_base.loc[df_base[row_col] == baseline].head(1)
                            else:
                                rr = df_base.iloc[int(baseline): int(baseline) + 1]
                            x0 = rr[list(ins_loc)].to_numpy(dtype=float).reshape(-1)
                        except Exception:
                            st.error("Не удалось извлечь x0 из выбранной строки")
                            x0 = None

                        if x0 is not None and len(x0) == len(ins_loc):
                            # step per feature
                            step = float(eps) * (pack["x_q95"] - pack["x_q05"])
                            # fallback for degenerate ranges
                            step = np.where(np.abs(step) < 1e-12, float(eps) * (pack["x_max"] - pack["x_min"]), step)
                            step = np.where(np.abs(step) < 1e-12, 1e-6, step)

                            clip_min = pack["x_min"] if clip_to_data else None
                            clip_max = pack["x_max"] if clip_to_data else None

                            y0, dy, delta = _local_sensitivity_matrix(
                                model,
                                x0,
                                step,
                                mode=str(diff_mode),
                                clip_min=clip_min,
                                clip_max=clip_max,
                            )

                            # choose shown matrix
                            mat_show = delta if show_mode.startswith("Δ") else dy

                            if norm_y:
                                y_rng = (pack["y_q95"] - pack["y_q05"]).astype(float)
                                y_rng = np.where(np.abs(y_rng) < 1e-12, (pack["y_max"] - pack["y_min"]), y_rng)
                                y_rng = np.where(np.abs(y_rng) < 1e-12, 1.0, y_rng)
                                mat_show = mat_show / y_rng.reshape(-1, 1)

                            df_mat = pd.DataFrame(mat_show, index=list(outs_loc), columns=list(ins_loc))

                            # order for readability
                            try:
                                in_order = df_mat.abs().mean(axis=0).sort_values(ascending=False).index.tolist()
                                out_order = df_mat.abs().mean(axis=1).sort_values(ascending=False).index.tolist()
                                df_mat = df_mat.loc[out_order, in_order]
                            except Exception:
                                pass

                            # heatmap
                            try:
                                z = df_mat.to_numpy(dtype=float)
                                vmax = float(np.nanmax(np.abs(z))) if np.isfinite(z).any() else 1.0
                                fig = go.Figure(
                                    data=go.Heatmap(
                                        z=z,
                                        x=[_short_name(c) for c in df_mat.columns],
                                        y=[str(r) for r in df_mat.index],
                                        colorscale="RdBu",
                                        zmin=-vmax,
                                        zmax=vmax,
                                        hovertemplate="%{y}<br>%{x}: %{z:.4g}<extra></extra>",
                                    )
                                )
                                title = "Jacobian (локальная чувствительность)" if show_mode.startswith("d") else "ΔY при +step"
                                fig.update_layout(
                                    title=f"{title} — baseline={baseline}",
                                    height=max(520, 24 * len(df_mat.index) + 120),
                                    margin=dict(l=40, r=10, t=70, b=40),
                                )
                                safe_plotly_chart(st, fig, key="pi_loc_heat")
                            except Exception as e:
                                st.error(f"Heatmap: ошибка: {e}")

                            # quick table of baseline predicted outputs
                            with st.expander("Предсказанные выходы в базовой точке (surrogate)", expanded=False):
                                df_y0 = pd.DataFrame({
                                    "output": list(outs_loc),
                                    "y_pred": [float(v) for v in y0],
                                    "r2_holdout": [float(v) for v in r2_raw],
                                })
                                st.dataframe(df_y0, width="stretch", height=240)

                            # export
                            try:
                                st.download_button(
                                    "⬇️ Скачать Jacobian/Δ матрицу (CSV)",
                                    data=df_mat.to_csv(index=True).encode("utf-8"),
                                    file_name="pi_local_sensitivity.csv",
                                    mime="text/csv",
                                    key="pi_loc_dl",
                                )
                            except Exception:
                                pass

            # =============================================================
            # TAB W: WHAT-IF
            # =============================================================
            with tab_w:
                st.markdown("**What‑if**: быстро меняйте несколько параметров (слайдерами) и смотрите изменение нескольких выходов по surrogate.")
                st.info(
                    "Важно: это *модельный* what‑if по данным CSV. Это не прямой расчёт физики, "
                    "но хорошо подходит для ‘куда двигать параметры’ перед дорогими симуляциями."
                )

                ds_opts = ["A: primary"]
                if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                    ds_opts.append("B: reference")
                ds = st.radio("Датасет", options=ds_opts, index=0, horizontal=True, key="pi_wi_ds")

                # use same selections as local tab by default
                outs_w = st.session_state.get("pi_loc_outs") or (outputs[: min(6, len(outputs))])
                ins_w = st.session_state.get("pi_loc_ins") or (inputs[: min(10, len(inputs))])

                outs_w = st.multiselect("Выходы", options=outputs, default=outs_w, key="pi_wi_outs")
                ins_w = st.multiselect("Параметры", options=inputs, default=ins_w, key="pi_wi_ins")

                if len(outs_w) < 1 or len(ins_w) < 1:
                    st.info("Выберите хотя бы 1 выход и 1 параметр.")
                else:
                    # baseline data
                    if ds.startswith("B") and (df_ref_sel is not None):
                        df_base = df_ref_sel
                        row_col = "_row_ref" if "_row_ref" in df_base.columns else "_row"
                        id_base = id_col_ref
                        df_num_base = df_num_ref_sel
                    else:
                        df_base = df_sel
                        row_col = "_row"
                        id_base = id_col
                        df_num_base = df_num_sel

                    base_options = df_base[row_col].tolist() if row_col in df_base.columns else list(range(len(df_base)))

                    def _fmt_row(v):
                        try:
                            rr = df_base.loc[df_base[row_col] == v].head(1)
                            if len(rr) == 0:
                                return str(v)
                            s = f"{v}"
                            if id_base is not None and id_base in rr.columns:
                                s += f" | id={rr[id_base].iloc[0]}"
                            return s
                        except Exception:
                            return str(v)

                    baseline = st.selectbox(
                        "Базовая строка",
                        options=base_options,
                        index=0,
                        format_func=_fmt_row,
                        key="pi_wi_baseline",
                    )

                    # surrogate
                    n_estimators_w = st.slider(
                        "RF деревья",
                        min_value=80,
                        max_value=900,
                        value=int(st.session_state.get("pi_wi_rf_n") or 320),
                        step=40,
                        key="pi_wi_rf_n",
                    )
                    max_rows_w = st.number_input(
                        "Строк для обучения",
                        min_value=0,
                        max_value=200000,
                        value=int(st.session_state.get("pi_wi_train_rows") or 20000),
                        step=1000,
                        key="pi_wi_train_rows",
                    )

                    pack = _train_multi_surrogate_cached(
                        df_num_base,
                        tuple(ins_w),
                        tuple(outs_w),
                        seed_i=int(seed),
                        n_estimators_i=int(n_estimators_w),
                        test_size_f=0.25,
                        max_rows_train=int(max_rows_w),
                    )

                    if not pack:
                        st.warning("Не удалось обучить surrogate (мало данных/NaN).")
                    else:
                        model = pack["model"]

                        rr = df_base.loc[df_base[row_col] == baseline].head(1)
                        x0 = rr[list(ins_w)].to_numpy(dtype=float).reshape(-1)
                        y0 = model.predict(x0.reshape(1, -1))[0]

                        st.caption(f"Surrogate mean R²≈{float(pack['r2_mean']):.3f}")

                        # sliders for chosen subset of params
                        st.markdown("### Слайдеры параметров")
                        adj_default = st.session_state.get("pi_wi_adj") or list(ins_w[: min(6, len(ins_w))])
                        adj = st.multiselect(
                            "Какие параметры крутить?",
                            options=list(ins_w),
                            default=adj_default,
                            key="pi_wi_adj",
                        )

                        x_new = x0.copy()
                        for p_name in adj:
                            j = list(ins_w).index(p_name)
                            vmin = float(pack["x_min"][j])
                            vmax = float(pack["x_max"][j])
                            v0 = float(x0[j])
                            if not (np.isfinite(vmin) and np.isfinite(vmax)):
                                continue
                            if vmax - vmin < 1e-12:
                                continue
                            # streamlit slider can be finicky with tiny ranges — keep sane
                            val = st.slider(
                                _short_name(p_name),
                                min_value=float(vmin),
                                max_value=float(vmax),
                                value=float(np.clip(v0, vmin, vmax)),
                                key=f"pi_wi_slider_{_slugify(p_name)}",
                            )
                            x_new[j] = float(val)

                        y_new = model.predict(x_new.reshape(1, -1))[0]
                        dy = np.asarray(y_new, dtype=float) - np.asarray(y0, dtype=float)

                        df_out = pd.DataFrame({
                            "output": list(outs_w),
                            "baseline_pred": [float(v) for v in y0],
                            "new_pred": [float(v) for v in y_new],
                            "delta": [float(v) for v in dy],
                        })

                        st.dataframe(df_out, width="stretch", height=320)

                        # bar of |delta|
                        try:
                            dfb = df_out.copy()
                            dfb["abs_delta"] = dfb["delta"].abs()
                            dfb = dfb.sort_values("abs_delta", ascending=False)
                            topn = min(20, len(dfb))
                            fig = _bar_figure(
                                names=dfb["output"].tolist()[:topn][::-1],
                                values=dfb["delta"].tolist()[:topn][::-1],
                                title="Δ выходов (new - baseline)",
                                horizontal=True,
                            )
                            if fig is not None:
                                safe_plotly_chart(st, fig, key="pi_wi_bar")
                        except Exception:
                            pass

                        # If we have NPZ path in this baseline row, offer quick open in Compare
                        if npz_col is not None and npz_col in rr.columns:
                            raw_npz = []
                            for v in rr[npz_col].tolist():
                                raw_npz.extend(_extract_npz_candidates(v))
                            raw_npz = [p for p in raw_npz if isinstance(p, str) and p.strip()]
                            if raw_npz:
                                roots = []
                                try:
                                    roots.append(Path(csv_path).expanduser().resolve().parent)
                                except Exception:
                                    pass
                                roots.append(Path(app_dir) / "workspace" / "osc")
                                roots.append(Path(app_dir) / "workspace")
                                roots.append(Path.cwd())
                                roots = [r for r in roots if isinstance(r, Path) and r.exists()]
                                resolved, _ = _resolve_npz_paths(raw_npz, roots=roots)
                                if resolved:
                                    if st.button("➡️ Открыть baseline NPZ в Compare UI", key="pi_wi_open_compare"):
                                        st.session_state["cmp_external_paths"] = resolved
                                        st.session_state["cmp_ext_active"] = True
                                        st.success("Передано в Compare UI. Прокрутите вниз к #compare_npz")

                        st.download_button(
                            "⬇️ Скачать what‑if результат (CSV)",
                            data=df_out.to_csv(index=False).encode("utf-8"),
                            file_name="pi_whatif_outputs.csv",
                            mime="text/csv",
                            key="pi_wi_dl",
                        )


            # =============================================================
            # TAB I: INTERACTIONS (2D PDP + Friedman H)
            # =============================================================
            with tab_i:
                st.markdown("**Интеракции параметров**: какие *пары* входов дают «синергетический» эффект на выход.")
                st.caption(
                    "Используем surrogate (RandomForest) и считаем 2D PDP для пар параметров. "
                    "Сила интеракции оценивается через **Friedman H-statistic** (0..1). "
                    "Полезно для анализа «N параметров → N метрик», когда важны сочетания."
                )
                st.info(
                    "Замечание: PDP может искажаться при сильной корреляции параметров. "
                    "Для таких случаев часто используют ALE (Accumulated Local Effects) — см. вкладку \"ALE (surrogate)\"."
                )

                ds_opts_i = ["A: primary"]
                if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                    ds_opts_i.append("B: reference")
                ds_i = st.radio("Датасет", options=ds_opts_i, index=0, horizontal=True, key="pi_int_ds")
                df_num_i = df_num_ref_sel if (ds_i.startswith("B") and df_num_ref_sel is not None) else df_num_sel

                inputs_i_all = [p for p in inputs if p in df_num_i.columns]
                outputs_i_all = [o for o in outputs if o in df_num_i.columns]

                if not inputs_i_all or not outputs_i_all:
                    st.warning("Нет общих inputs/outputs в выбранном датасете.")
                else:
                    colI1, colI2, colI3, colI4 = st.columns([1.2, 1.0, 1.0, 1.0], gap="medium")
                    with colI1:
                        y_i = st.selectbox("Выход (Y)", options=outputs_i_all, index=0, key="pi_int_y")
                    with colI2:
                        max_features = st.slider("Параметров для перебора", min_value=4, max_value=min(30, len(inputs_i_all)), value=min(10, len(inputs_i_all)), step=1, key="pi_int_maxf")
                    with colI3:
                        grid_n = st.slider("Сетка PDP", min_value=6, max_value=25, value=int(st.session_state.get("pi_int_grid") or 12), step=1, key="pi_int_grid")
                    with colI4:
                        n_estimators_i = st.slider("RF деревья", min_value=80, max_value=900, value=int(st.session_state.get("pi_int_rf_n") or 260), step=40, key="pi_int_rf_n")

                    colI5, colI6, colI7 = st.columns([1.0, 1.0, 1.0], gap="medium")
                    with colI5:
                        max_base_i = st.number_input("Сэмпл для PDP (строк)", min_value=200, max_value=10000, value=int(st.session_state.get("pi_int_base") or 800), step=200, key="pi_int_base")
                    with colI6:
                        top_pairs = st.slider("Top пар", min_value=5, max_value=60, value=int(st.session_state.get("pi_int_top") or 20), step=5, key="pi_int_top")
                    with colI7:
                        do_rank = st.checkbox("Считать рейтинг интеракций", value=True, key="pi_int_rank")

                    # Choose features (by simple heuristic: correlation / MI rank could be added; for now: user pick + first max_features)
                    default_feats = st.session_state.get("pi_int_feats") or inputs_i_all[: int(max_features)]
                    feats = st.multiselect("Кандидаты (X)", options=inputs_i_all, default=default_feats, key="pi_int_feats")
                    if len(feats) < 2:
                        st.info("Нужно выбрать хотя бы 2 параметра.")
                    else:
                        feats = feats[: int(max_features)]
                        X_i, Y_i = _prepare_xy(df_num_i, list(feats), y_i)

                        if len(Y_i) < 50:
                            st.warning("Мало данных после фильтрации NaN/inf. Нужно хотя бы ~50 строк.")
                        else:
                            # model cache in session_state
                            model_key = ("pi_int_model", ds_i, y_i, tuple(feats), int(seed), int(n_estimators_i), int(len(Y_i)))
                            model = st.session_state.get("pi_int_model_obj")
                            model_key_prev = st.session_state.get("pi_int_model_key")
                            r2_i = st.session_state.get("pi_int_model_r2")

                            if model is None or model_key_prev != model_key:
                                with st.spinner("Обучаю surrogate (RF) для интеракций..."):
                                    try:
                                        model, r2_i = _train_rf_regressor(X_i, Y_i, seed=int(seed), n_estimators=int(n_estimators_i))
                                        st.session_state["pi_int_model_obj"] = model
                                        st.session_state["pi_int_model_key"] = model_key
                                        st.session_state["pi_int_model_r2"] = float(r2_i)
                                    except Exception as _e:
                                        st.error(f"Не удалось обучить surrogate: {_e}")
                                        model = None

                            if model is not None:
                                st.caption(f"Surrogate R² (holdout) ≈ {float(r2_i):.3f}")

                                # Precompute grids + 1D PDP for each feature
                                rng = np.random.default_rng(int(seed))
                                pdp1 = {}
                                grids = {}
                                for j, name in enumerate(feats):
                                    col = X_i[:, j]
                                    qs = np.linspace(0.05, 0.95, int(grid_n))
                                    try:
                                        g = np.quantile(col[np.isfinite(col)], qs)
                                    except Exception:
                                        g = np.linspace(float(np.nanmin(col)), float(np.nanmax(col)), int(grid_n))
                                    g = np.unique(np.asarray(g, dtype=float))
                                    if len(g) < 4:
                                        # broaden
                                        g = np.linspace(float(np.nanmin(col)), float(np.nanmax(col)), max(4, int(grid_n)))
                                    grids[name] = g
                                    try:
                                        pdp1[name] = _pdp_1d(model, X_i, j, g, max_base=int(max_base_i), seed=int(seed))
                                    except Exception:
                                        pdp1[name] = np.full_like(g, np.nan, dtype=float)

                                pairs = []
                                if do_rank:
                                    with st.spinner("Считаю H‑statistic для пар (может занять время)..."):
                                        names = list(feats)
                                        for a in range(len(names)):
                                            for b in range(a + 1, len(names)):
                                                na, nb = names[a], names[b]
                                                gi = grids[na]
                                                gj = grids[nb]
                                                try:
                                                    pdp2 = _pdp_2d(model, X_i, a, b, gi, gj, max_base=int(max_base_i), seed=int(seed))
                                                    h = _friedman_h_statistic(pdp2, pdp1[na], pdp1[nb])
                                                except Exception:
                                                    h = float("nan")
                                                pairs.append((na, nb, float(h)))
                                    df_pairs = pd.DataFrame(pairs, columns=["x1", "x2", "H"])
                                    df_pairs = df_pairs.replace([np.inf, -np.inf], np.nan).dropna(subset=["H"])
                                    df_pairs = df_pairs.sort_values("H", ascending=False).head(int(top_pairs))
                                    st.dataframe(df_pairs, width="stretch", height=320)

                                    if len(df_pairs) == 0:
                                        st.info("Не удалось оценить интеракции (проверьте данные/NaN).")
                                        st.stop()
                                else:
                                    df_pairs = pd.DataFrame(pairs, columns=["x1", "x2", "H"])

                                # pick a pair for visualization
                                if do_rank and len(df_pairs) > 0:
                                    opts = [f"{r.x1} × {r.x2} (H={r.H:.3f})" for r in df_pairs.itertuples()]
                                    pick = st.selectbox("Пара для визуализации", options=opts, index=0, key="pi_int_pick")
                                    # parse back to names
                                    try:
                                        left = pick.split("×")[0].strip()
                                        right = pick.split("×")[1].split("(")[0].strip()
                                    except Exception:
                                        left, right = df_pairs.iloc[0]["x1"], df_pairs.iloc[0]["x2"]
                                else:
                                    left, right = feats[0], feats[1]

                                # compute 2D PDP for chosen pair
                                a = list(feats).index(left)
                                b = list(feats).index(right)
                                gi = grids[left]
                                gj = grids[right]
                                with st.spinner("Считаю 2D PDP для выбранной пары..."):
                                    pdp2 = _pdp_2d(model, X_i, a, b, gi, gj, max_base=int(max_base_i), seed=int(seed))
                                    h_val = _friedman_h_statistic(pdp2, pdp1[left], pdp1[right])

                                st.caption(f"Пара: {left} × {right} — H≈{h_val:.3f}")

                                # heatmap
                                try:
                                    import plotly.graph_objects as go  # type: ignore

                                    fig_h = go.Figure(
                                        data=go.Heatmap(
                                            z=pdp2,
                                            x=[float(v) for v in gj],
                                            y=[float(v) for v in gi],
                                            colorbar=dict(title=y_i),
                                        )
                                    )
                                    fig_h.update_layout(
                                        title=f"2D PDP: {y_i} = f({left}, {right})",
                                        xaxis_title=_short_name(right),
                                        yaxis_title=_short_name(left),
                                        height=560,
                                        margin=dict(l=60, r=20, t=70, b=50),
                                    )
                                    safe_plotly_chart(st, fig_h, key="pi_int_heat")
                                except Exception:
                                    pass

                                # 1D PDP curves for context
                                try:
                                    fig1 = _line_figure(
                                        x=[float(v) for v in gi],
                                        y=[float(v) for v in pdp1[left]],
                                        title=f"1D PDP: {y_i} vs {left}",
                                        x_title=_short_name(left),
                                        y_title=y_i,
                                    )
                                    fig2 = _line_figure(
                                        x=[float(v) for v in gj],
                                        y=[float(v) for v in pdp1[right]],
                                        title=f"1D PDP: {y_i} vs {right}",
                                        x_title=_short_name(right),
                                        y_title=y_i,
                                    )
                                    colC1, colC2 = st.columns([1.0, 1.0], gap="medium")
                                    with colC1:
                                        if fig1 is not None:
                                            safe_plotly_chart(st, fig1, key="pi_int_pdp1")
                                    with colC2:
                                        if fig2 is not None:
                                            safe_plotly_chart(st, fig2, key="pi_int_pdp2")
                                except Exception:
                                    pass

                                # export
                                try:
                                    df_export = pd.DataFrame(pdp2, index=[float(v) for v in gi], columns=[float(v) for v in gj])
                                    st.download_button(
                                        "⬇️ Скачать 2D PDP (CSV)",
                                        data=df_export.to_csv(index=True).encode("utf-8"),
                                        file_name="pi_pdp2d.csv",
                                        mime="text/csv",
                                        key="pi_int_dl",
                                    )
                                except Exception:
                                    pass


    # -----------------------------
    # Tab 6: Importance
    # -----------------------------
    with tab_importance:
        st.subheader("Важность параметров (surrogate‑модель + permutation importance)")

        if not _HAS_SKLEARN:
            st.warning("scikit-learn не установлен — важность параметров недоступна.")
        else:
            ds_opts = ["A: primary"]
            if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                ds_opts.append("B: reference")
            ds = st.radio(
                "Данные для surrogate",
                options=ds_opts,
                index=0,
                horizontal=True,
                key="pi_imp_dataset",
            )
            df_num_imp = df_num_ref_sel if (ds.startswith("B") and df_num_ref_sel is not None) else df_num_sel
            inputs_imp = [p for p in inputs if p in df_num_imp.columns]

            y = st.selectbox("Метрика для обучения surrogate", options=outputs, index=0, key="pi_imp_y")
            n_estimators = st.slider("RandomForest: деревья", min_value=50, max_value=800, value=int(st.session_state.get("pi_imp_n") or 250), step=50, key="pi_imp_n")
            test_size = st.slider("Доля теста", min_value=0.1, max_value=0.5, value=float(st.session_state.get("pi_imp_test") or 0.25), step=0.05, key="pi_imp_test")
            n_repeats = st.slider("Permutation repeats", min_value=3, max_value=30, value=int(st.session_state.get("pi_imp_rep") or 10), step=1, key="pi_imp_rep")

            if not inputs_imp:
                st.info("Нет общих входных параметров (inputs) в выбранном датасете.")
                st.stop()

            X = df_num_imp[inputs_imp].copy()
            Y = df_num_imp[y].copy() if y in df_num_imp.columns else None
            if Y is None:
                st.info("Выбранная метрика отсутствует в численных колонках.")
            else:
                m = np.isfinite(X.to_numpy(dtype=float)).all(axis=1) & np.isfinite(Y.to_numpy(dtype=float))
                X2 = X.loc[m].to_numpy(dtype=float)
                y2 = Y.loc[m].to_numpy(dtype=float)

                if len(y2) < 50:
                    st.info("Мало данных после фильтрации NaN/inf. Нужно хотя бы ~50 строк.")
                else:
                    X_train, X_test, y_train, y_test = train_test_split(X2, y2, test_size=float(test_size), random_state=int(seed))
                    model = RandomForestRegressor(
                        n_estimators=int(n_estimators),
                        random_state=int(seed),
                        n_jobs=-1,
                        max_features=1.0,
                    )
                    model.fit(X_train, y_train)
                    try:
                        y_pred = model.predict(X_test)
                        r2 = float(r2_score(y_test, y_pred))
                    except Exception:
                        r2 = float("nan")
                    st.caption(f"R² на holdout: {r2:.3f} (чем выше, тем надёжнее интерпретация важности)")

                    with st.spinner("Считаю permutation importance..."):
                        imp = permutation_importance(
                            model,
                            X_test,
                            y_test,
                            n_repeats=int(n_repeats),
                            random_state=int(seed),
                            n_jobs=-1,
                        )

                    importances = imp.importances_mean
                    order = np.argsort(np.abs(importances))[::-1]
                    topn = min(40, len(order))
                    names = [inputs_imp[i] for i in order[:topn]]
                    vals = [float(importances[i]) for i in order[:topn]]

                    fig = _bar_figure(
                        names=[_short_name(n) for n in names][::-1],
                        values=vals[::-1],
                        title=f"Permutation importance для {y}",
                        horizontal=True,
                    )
                    if fig is not None:
                        safe_plotly_chart(st, fig, key="pi_perm_importance")

                    st.caption("Permutation importance: ухудшение качества при перемешивании признака (на holdout).")

    # -----------------------------
    # Tab 7: PDP/ICE
    # -----------------------------
    with tab_pdp:
        st.subheader("PDP/ICE: как параметр влияет на метрику (через surrogate)")
        st.caption("Это «what‑if» анализ: меняем один параметр, остальные усредняем по данным. Полезно для нелинейностей.")

        if not _HAS_SKLEARN:
            st.warning("scikit-learn не установлен — PDP/ICE недоступны.")
        else:
            ds_opts = ["A: primary"]
            if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                ds_opts.append("B: reference")
            ds = st.radio(
                "Данные для surrogate",
                options=ds_opts,
                index=0,
                horizontal=True,
                key="pi_pdp_dataset",
            )
            df_num_pdp = df_num_ref_sel if (ds.startswith("B") and df_num_ref_sel is not None) else df_num_sel
            inputs_pdp = [pp for pp in inputs if pp in df_num_pdp.columns]
            outputs_pdp = [oo for oo in outputs if oo in df_num_pdp.columns]
            if not inputs_pdp or not outputs_pdp:
                st.info("В выбранном датасете нет общих inputs/outputs для PDP/ICE.")
                st.stop()

            colP1, colP2, colP3, colP4 = st.columns([1.0, 1.0, 1.0, 1.0], gap="medium")
            with colP1:
                y = st.selectbox("Метрика (Y)", options=outputs_pdp, index=0, key="pi_pdp_y")
            with colP2:
                p = st.selectbox("Параметр (X)", options=inputs_pdp, index=0, key="pi_pdp_p")
            with colP3:
                n_grid = st.slider("Точек сетки", min_value=10, max_value=60, value=int(st.session_state.get("pi_pdp_grid") or 25), step=5, key="pi_pdp_grid")
            with colP4:
                n_estimators = st.slider("RF деревья", min_value=80, max_value=800, value=int(st.session_state.get("pi_pdp_n") or 250), step=40, key="pi_pdp_n")

            colP5, colP6, colP7 = st.columns([1.0, 1.0, 1.0], gap="medium")
            with colP5:
                max_base = st.number_input("Сэмпл для PDP (строк)", min_value=200, max_value=10000, value=int(st.session_state.get("pi_pdp_max_base") or 1200), step=200, key="pi_pdp_max_base")
            with colP6:
                show_ice = st.checkbox("Показать ICE (несколько траекторий)", value=False, key="pi_pdp_show_ice")
            with colP7:
                ice_n = st.number_input("ICE траекторий", min_value=5, max_value=120, value=int(st.session_state.get("pi_pdp_ice_n") or 30), step=5, key="pi_pdp_ice_n")

            try:
                X, Y = _prepare_xy(df_num_pdp, inputs_pdp, y)
                if len(Y) < 80:
                    st.info("Мало данных для устойчивого surrogate (желательно 80+ строк).")
                else:
                    model, r2 = _train_rf_regressor(X, Y, seed=int(seed), n_estimators=int(n_estimators))
                    st.caption(f"Surrogate R² (holdout): {r2:.3f}")

                    feat_i = inputs_pdp.index(p)
                    # grid by quantiles for robustness
                    xcol = X[:, feat_i]
                    q = np.linspace(0.02, 0.98, int(n_grid))
                    grid = np.quantile(xcol[np.isfinite(xcol)], q) if np.isfinite(xcol).any() else np.linspace(0.0, 1.0, int(n_grid))
                    grid = np.unique(grid)
                    if len(grid) < 5:
                        grid = np.linspace(float(np.nanmin(xcol)), float(np.nanmax(xcol)), int(n_grid))

                    pdp = _pdp_1d(model, X, feat_i, grid, max_base=int(max_base), seed=int(seed))

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=grid, y=pdp, mode="lines+markers", name="PDP (mean)"))

                    if show_ice:
                        # sample rows
                        rng = np.random.default_rng(int(seed))
                        n_take = min(int(ice_n), len(X))
                        idx = rng.choice(len(X), size=n_take, replace=False)
                        ice = _ice_1d(model, X[idx], feat_i, grid)
                        for i in range(len(ice)):
                            fig.add_trace(go.Scatter(x=grid, y=ice[i], mode="lines", line=dict(width=1), opacity=0.25, name="ICE", showlegend=(i == 0)))

                    fig.update_layout(
                        title=f"{_short_name(p)} → {y} (PDP/ICE)",
                        xaxis_title=_short_name(p),
                        yaxis_title=y,
                        height=620,
                        margin=dict(l=40, r=10, t=70, b=40),
                    )
                    safe_plotly_chart(st, fig, key="pi_pdp_fig")

                    st.caption("Важно: PDP/ICE показывает модельные зависимости по данным CSV, а не истинную физику. Используйте как подсказку.")
            except Exception as e:
                st.error(f"PDP/ICE: ошибка: {e}")

    # -----------------------------
    # Tab 7b: ALE (Accumulated Local Effects)
    # -----------------------------
    with tab_ale:
        st.subheader("ALE (Accumulated Local Effects): эффект параметра при коррелированных входах")
        st.caption(
            "ALE — альтернатива PDP: эффект считается локально по данным и обычно стабильнее, когда параметры коррелированы. "
            "Ниже — 1D ALE по surrogate-модели (RandomForest) и, при желании, рейтинг параметров по амплитуде эффекта."
        )

        if not _HAS_SKLEARN:
            st.warning("scikit-learn не установлен — ALE недоступен.")
        else:
            ds_opts = ["A: primary"]
            if has_ref and (df_num_ref_sel is not None) and len(df_num_ref_sel) > 0:
                ds_opts.append("B: reference")
            ds = st.radio("Данные для surrogate", options=ds_opts, index=0, horizontal=True, key="pi_ale_dataset")
            df_num_ale = df_num_ref_sel if (ds.startswith('B') and df_num_ref_sel is not None) else df_num_sel
            inputs_ale = [pp for pp in inputs if pp in df_num_ale.columns]
            outputs_ale = [oo for oo in outputs if oo in df_num_ale.columns]
            if not inputs_ale or not outputs_ale:
                st.info("В выбранном датасете нет общих inputs/outputs для ALE.")
            else:
                c1, c2, c3, c4 = st.columns([1.1, 1.0, 1.0, 1.0], gap='medium')
                with c1:
                    y = st.selectbox('Выход (Y) для ALE', options=outputs_ale, index=0, key='pi_ale_y')
                with c2:
                    bins_i = st.number_input('Бины (ALE)', min_value=6, max_value=60, value=int(st.session_state.get('pi_ale_bins') or 20), step=2, key='pi_ale_bins')
                with c3:
                    max_base = st.number_input('Сэмпл строк (ускорение)', min_value=200, max_value=20000, value=int(st.session_state.get('pi_ale_max_base') or 2000), step=200, key='pi_ale_max_base')
                with c4:
                    show_rank = st.checkbox('Показать рейтинг параметров по амплитуде ALE', value=True, key='pi_ale_rank')

                # choose params
                params_pick = st.multiselect('Параметры (X) для ALE', options=inputs_ale, default=inputs_ale[: min(6, len(inputs_ale))], key='pi_ale_params')
                if not params_pick:
                    st.info("Выберите хотя бы один параметр.")
                elif y not in df_num_ale.columns:
                    st.info("Выход отсутствует в датасете.")
                else:
                    # Prepare data
                    X, Y = _prepare_xy(df_num_ale, inputs_ale, y)
                    # sample for speed
                    if len(Y) > int(max_base):
                        rng = np.random.default_rng(int(seed))
                        idx = rng.choice(len(Y), size=int(max_base), replace=False)
                        X = X[idx]
                        Y = Y[idx]

                    try:
                        model, r2 = _train_rf_regressor(X, Y, seed=int(seed), n_estimators=int(st.session_state.get('pi_ale_n_estimators') or 300))
                    except Exception as e:
                        st.error(f'ALE: не удалось обучить surrogate: {e}')
                        model = None
                        r2 = float('nan')

                    if model is not None:
                        st.caption(f'Surrogate R² (holdout): {r2:.3f}')

                        def _ale_1d(model_in, X_in: np.ndarray, feat_i: int, *, bins_i: int) -> Tuple[np.ndarray, np.ndarray]:
                            # quantile bins
                            x = np.asarray(X_in[:, feat_i], dtype=float)
                            x = x[np.isfinite(x)]
                            if x.size < 30:
                                return np.asarray([], dtype=float), np.asarray([], dtype=float)
                            qs = np.linspace(0.0, 1.0, int(bins_i) + 1)
                            edges = np.quantile(x, qs)
                            edges = np.unique(edges)
                            if edges.size < 4:
                                edges = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), int(bins_i) + 1)
                            # recompute bins count after unique
                            nb = max(2, int(len(edges) - 1))
                            eff = np.zeros(nb, dtype=float)
                            counts = np.zeros(nb, dtype=int)
                            x_full = np.asarray(X_in[:, feat_i], dtype=float)
                            for bi in range(nb):
                                lo = float(edges[bi])
                                hi = float(edges[bi + 1])
                                m = (x_full >= lo) & (x_full <= hi if bi == nb - 1 else x_full < hi)
                                if not np.any(m):
                                    continue
                                Xb = np.asarray(X_in[m], dtype=float)
                                X_lo = Xb.copy(); X_lo[:, feat_i] = lo
                                X_hi = Xb.copy(); X_hi[:, feat_i] = hi
                                try:
                                    y_hi = model_in.predict(X_hi)
                                    y_lo = model_in.predict(X_lo)
                                    d = np.asarray(y_hi, dtype=float) - np.asarray(y_lo, dtype=float)
                                    eff[bi] = float(np.nanmean(d))
                                    counts[bi] = int(np.sum(np.isfinite(d)))
                                except Exception:
                                    continue
                            ale = np.cumsum(eff)
                            # center
                            ale = ale - float(np.nanmean(ale))
                            centers = 0.5 * (edges[:-1] + edges[1:])
                            centers = centers[: ale.size]
                            return centers, ale

                        figs = []
                        rank_rows = []
                        for p_name in params_pick:
                            feat_i = int(inputs_ale.index(p_name))
                            xg, ale = _ale_1d(model, X, feat_i, bins_i=int(bins_i))
                            if xg.size < 2 or ale.size < 2:
                                continue
                            amp = float(np.nanmax(ale) - np.nanmin(ale))
                            rank_rows.append({'param': p_name, 'amplitude': amp})
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=xg, y=ale, mode='lines+markers', name='ALE'))
                            fig.update_layout(title=f'ALE: {_short_name(p_name)} → {y}', xaxis_title=_short_name(p_name), yaxis_title='ALE', height=420, margin=dict(l=40,r=10,t=60,b=40))
                            figs.append(fig)

                        if show_rank and rank_rows:
                            rdf = pd.DataFrame(rank_rows).sort_values('amplitude', ascending=False).reset_index(drop=True)
                            st.markdown('**Рейтинг параметров (амплитуда ALE):**')
                            st.dataframe(rdf, width='stretch', height=260)

                        if not figs:
                            st.info('Не удалось построить ALE (слишком мало данных/вариативности).')
                        else:
                            # small-multiples
                            ncol = 2
                            for i0 in range(0, len(figs), ncol):
                                cols = st.columns(ncol, gap='medium')
                                for j0 in range(ncol):
                                    if i0 + j0 >= len(figs):
                                        break
                                    with cols[j0]:
                                        safe_plotly_chart(st, figs[i0 + j0], key=f'pi_ale_fig_{i0+j0}')


    # Tab 8: Group comparison
    # -----------------------------
    with tab_group:
        st.subheader("Сравнение групп: какие параметры отличают «лучшие» от «худших»")
        st.caption("Быстрый способ понять, что «двигает» метрику: сравнить распределения параметров между группами.")

        metric = st.selectbox("Метрика для разбиения на группы", options=outputs, index=0, key="pi_group_metric")
        direction = st.selectbox("Что считаем «лучшим»?", options=["минимум метрики", "максимум метрики"], index=0, key="pi_group_direction")
        q = st.slider("Размер группы (квантиль)", min_value=0.02, max_value=0.40, value=float(st.session_state.get("pi_group_q") or 0.10), step=0.02, key="pi_group_q")

        if metric not in df_num_sel.columns:
            st.info("Метрика отсутствует в численных колонках.")
        else:
            dfg = df_num_sel[[metric, *[p for p in inputs if p in df_num_sel.columns]]].copy()
            dfg = dfg.replace([np.inf, -np.inf], np.nan).dropna(subset=[metric], how="any")
            if len(dfg) < 50:
                st.info("Слишком мало строк.")
            else:
                yv = dfg[metric].to_numpy(dtype=float)
                if direction == "минимум метрики":
                    thr_lo = float(np.nanquantile(yv, q))
                    thr_hi = float(np.nanquantile(yv, 1.0 - q))
                    A = dfg[yv <= thr_lo]
                    B = dfg[yv >= thr_hi]
                    labelA = f"best (≤ q{q:.2f})"
                    labelB = f"worst (≥ q{1-q:.2f})"
                else:
                    thr_lo = float(np.nanquantile(yv, q))
                    thr_hi = float(np.nanquantile(yv, 1.0 - q))
                    A = dfg[yv >= thr_hi]
                    B = dfg[yv <= thr_lo]
                    labelA = f"best (≥ q{1-q:.2f})"
                    labelB = f"worst (≤ q{q:.2f})"

                if len(A) < 8 or len(B) < 8:
                    st.info("Группы слишком маленькие. Увеличьте квантиль.")
                else:
                    rows = []
                    for p in inputs:
                        if p not in dfg.columns:
                            continue
                        a = A[p].to_numpy(dtype=float)
                        b = B[p].to_numpy(dtype=float)
                        a = a[np.isfinite(a)]
                        b = b[np.isfinite(b)]
                        if len(a) < 5 or len(b) < 5:
                            continue
                        ma = float(np.mean(a))
                        mb = float(np.mean(b))
                        sda = float(np.std(a))
                        sdb = float(np.std(b))
                        pooled = math.sqrt(0.5 * (sda * sda + sdb * sdb))
                        d = (ma - mb) / pooled if pooled > 1e-12 else float("nan")
                        meda = float(np.median(a))
                        medb = float(np.median(b))
                        rows.append({
                            "param": _short_name(p),
                            "mean_A": ma,
                            "mean_B": mb,
                            "median_A": meda,
                            "median_B": medb,
                            "delta_median": meda - medb,
                            "effect_d": d,
                            "n_A": int(len(a)),
                            "n_B": int(len(b)),
                        })
                    if not rows:
                        st.info("Не удалось посчитать эффекты (возможно, много NaN).")
                    else:
                        df_eff = pd.DataFrame(rows)
                        df_eff["abs_d"] = df_eff["effect_d"].abs()
                        df_eff = df_eff.sort_values("abs_d", ascending=False)

                        topn = st.number_input("Показать топ‑N параметров", min_value=5, max_value=60, value=20, step=5, key="pi_group_topn")
                        show = df_eff.head(int(topn)).copy()

                        fig = _bar_figure(
                            names=show["param"].tolist()[::-1],
                            values=show["effect_d"].tolist()[::-1],
                            title=f"Effect size (Cohen's d): {labelA} vs {labelB}",
                            horizontal=True,
                        )
                        if fig is not None:
                            safe_plotly_chart(st, fig, key="pi_group_effect_bar")

                        st.dataframe(df_eff.drop(columns=["abs_d"]), width="stretch", height=520)

                        with st.expander("Детальный просмотр распределений (1 параметр)", expanded=False):
                            p_pick = st.selectbox("Параметр", options=df_eff["param"].tolist(), index=0, key="pi_group_param_pick")
                            # find original col
                            orig = None
                            for p0 in inputs:
                                if _short_name(p0) == p_pick:
                                    orig = p0
                                    break
                            if orig and orig in dfg.columns:
                                dfa = A[[orig]].copy()
                                dfa["group"] = labelA
                                dfb = B[[orig]].copy()
                                dfb["group"] = labelB
                                dfv = pd.concat([dfa, dfb], ignore_index=True)
                                dfv = dfv.rename(columns={orig: p_pick}).dropna()
                                fig2 = px.box(dfv, x="group", y=p_pick, points="all", title=f"{p_pick}: {labelA} vs {labelB}")
                                fig2.update_layout(height=520, margin=dict(l=40, r=10, t=70, b=40))
                                safe_plotly_chart(st, fig2, key="pi_group_box")

    # -----------------------------
    # Tab 9: Delta explorer (two runs)
    # -----------------------------
    with tab_delta:
        st.subheader("Δ двух прогонов: какие параметры изменили — и что изменилось в выходах")

        # determine IDs for selection
        id_use = id_col or "_row"
        ids = df_sel[id_use].tolist()
        if len(ids) < 2:
            st.info("Недостаточно строк.")
        else:
            colD1, colD2 = st.columns([1.0, 1.0], gap="large")
            with colD1:
                id_a = st.selectbox("Прогон A", options=ids, index=0, key="pi_delta_a")
            with colD2:
                id_b = st.selectbox("Прогон B", options=ids, index=min(1, len(ids)-1), key="pi_delta_b")

            row_a = df_sel.loc[df_sel[id_use] == id_a].head(1)
            row_b = df_sel.loc[df_sel[id_use] == id_b].head(1)

            if len(row_a) == 0 or len(row_b) == 0:
                st.info("Не удалось найти выбранные строки.")
            else:
                da = row_a.iloc[0]
                db = row_b.iloc[0]

                d_params = []
                for p in inputs:
                    if p not in df_num_sel.columns:
                        continue
                    va = _as_float(da.get(p))
                    vb = _as_float(db.get(p))
                    if np.isfinite(va) and np.isfinite(vb):
                        d_params.append((p, vb - va))

                d_out = []
                for o in outputs:
                    if o not in df_num_sel.columns:
                        continue
                    va = _as_float(da.get(o))
                    vb = _as_float(db.get(o))
                    if np.isfinite(va) and np.isfinite(vb):
                        d_out.append((o, vb - va))

                d_params.sort(key=lambda t: abs(t[1]), reverse=True)
                d_out.sort(key=lambda t: abs(t[1]), reverse=True)

                max_show = st.slider("Показать топ‑N по |Δ|", min_value=5, max_value=80, value=25, step=5, key="pi_delta_topn")

                colP, colY = st.columns([1.0, 1.0], gap="large")
                with colP:
                    names = [_short_name(p) for p, _ in d_params[: int(max_show)]][::-1]
                    vals = [float(v) for _, v in d_params[: int(max_show)]][::-1]
                    fig = _bar_figure(names, vals, title="Δ параметров (B − A)")
                    if fig is not None:
                        safe_plotly_chart(st, fig, key="pi_delta_params")

                with colY:
                    names = [o for o, _ in d_out[: int(max_show)]][::-1]
                    vals = [float(v) for _, v in d_out[: int(max_show)]][::-1]
                    fig = _bar_figure(names, vals, title="Δ выходов/метрик (B − A)")
                    if fig is not None:
                        safe_plotly_chart(st, fig, key="pi_delta_out")

                with st.expander("Подробные таблицы Δ", expanded=False):
                    st.dataframe(pd.DataFrame([( _short_name(p), d) for p, d in d_params], columns=["param", "delta"]).head(int(max_show)), width='stretch', height=280)
                    st.dataframe(pd.DataFrame(d_out, columns=["output", "delta"]).head(int(max_show)), width='stretch', height=280)

    # -----------------------------
    # Tab 9: History
    # -----------------------------
    with tab_history:
        st.subheader("История: метрика/параметры по id")

        if id_col is None or id_col not in df_num_sel.columns:
            st.info("В CSV нет численного столбца id/iter — история недоступна.")
        else:
            y = st.selectbox("Метрика (Y)", options=outputs, index=0, key="pi_hist_y")
            show_params = st.multiselect("Параметры для истории", options=inputs, default=inputs[:3], key="pi_hist_params")

            dfh = df_num_sel[[id_col, y, *[p for p in show_params if p in df_num_sel.columns]]].copy()
            dfh = dfh.replace([np.inf, -np.inf], np.nan).dropna(how="any")
            dfh = dfh.sort_values(id_col)

            fig = make_subplots(rows=1 + len(show_params), cols=1, shared_xaxes=True, vertical_spacing=0.03)
            fig.add_trace(go.Scatter(x=dfh[id_col], y=dfh[y], mode="lines+markers", name=y), row=1, col=1)
            fig.update_yaxes(title_text=y, row=1, col=1)

            for i, p in enumerate(show_params, start=1):
                if p not in dfh.columns:
                    continue
                fig.add_trace(go.Scatter(x=dfh[id_col], y=dfh[p], mode="lines", name=_short_name(p)), row=1+i, col=1)
                fig.update_yaxes(title_text=_short_name(p), row=1+i, col=1)

            fig.update_xaxes(title_text=id_col, row=1+len(show_params), col=1)
            fig.update_layout(height=max(560, 240 * (1 + len(show_params))), title="История (id → значения)", hovermode="x unified")
            safe_plotly_chart(st, fig, key="pi_history")

    # -----------------------------
    # Tab 10: Table + export
    # -----------------------------
    with tab_table:
        st.subheader("Таблица (фильтрованные данные)")
        st.caption("Подсказка: Ctrl+F (поиск в браузере) помогает быстро найти колонку/метрику.")

        df_table = df_sel
        id_table = id_col
        if has_ref and (df_ref_sel is not None) and len(df_ref_sel) > 0:
            ds = st.radio(
                "Датасет",
                options=["A: primary", "B: reference"],
                index=0,
                horizontal=True,
                key="pi_table_dataset",
            )
            if ds.startswith("B"):
                df_table = df_ref_sel
                id_table = id_col_ref

        show_cols = []
        if id_table and id_table in df_table.columns:
            show_cols.append(id_table)
        for c in ["_row", "ошибка", "ошибка_тест", "ошибка_тип", "штраф_физичности_сумма"]:
            if c in df_table.columns and c not in show_cols:
                show_cols.append(c)
        show_cols += [c for c in outputs if c in df_table.columns and c not in show_cols]
        show_cols += [c for c in inputs if c in df_table.columns and c not in show_cols]

        max_cols = st.slider("Макс. колонок в таблице", min_value=10, max_value=250, value=min(90, len(show_cols)), step=10, key="pi_table_maxcols")
        show_cols = show_cols[: int(max_cols)]

        # show selected rows on top (if any)
        df_show = df_table
        # show selected rows on top only for primary dataset
        if df_table is df_sel:
            sel_rows = st.session_state.get("pi_selected_rows") or []
            if isinstance(sel_rows, list) and sel_rows:
                sel_set = {int(x) for x in sel_rows if isinstance(x, (int, np.integer))}
                df_show = pd.concat(
                    [df_sel[df_sel["_row"].isin(sel_set)], df_sel[~df_sel["_row"].isin(sel_set)]],
                    ignore_index=True,
                )

        st.dataframe(df_show[show_cols].copy(), width='stretch', height=640)

        with st.expander("Экспорт (CSV)", expanded=False):
            out_name = st.text_input("Имя файла", value="param_influence_filtered.csv", key="pi_export_name")
            if st.button("Скачать CSV", key="pi_export_csv_btn"):
                try:
                    csv_bytes = df_table[show_cols].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    st.download_button("Сохранить", data=csv_bytes, file_name=out_name, mime="text/csv", key="pi_export_download")
                except Exception as e:
                    st.error(f"Экспорт не удался: {e}")

