# -*- coding: utf-8 -*-
"""influence_tools.py (DiagrammyV639 Suite3)

Инструменты для анализа типа N→N:
  *X* = численные параметры (meta_json) прогонов
  *Y* = метрики выходных сигналов (RMS, max|·|, mean|·|, p2p, ...)

Задача:
- дать одинаковую основу для Web (Streamlit) и Desktop GUI (Qt) сравнения,
  чтобы пользователь мог быстро отвечать на вопросы вида:

  «как изменение N параметров влияет на N выходных параметров?»

Дизайн:
- возвращаем pandas.DataFrame для удобной фильтрации/срезов.
- корреляция считается nan-aware.
- Spearman реализован через ранги (без SciPy).

Важно:
- Метрики считаются по сигналам, уже приведённым к единицам отображения
  (см. compare_ui.get_xy): конверсия, нулевая база, режим давления.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from pneumo_solver_ui.compare_ui import (
    get_xy,
    resample_linear,
)


# ---------------------------- meta flatten ----------------------------

def flatten_meta_numeric(meta: Dict, *, max_items: int = 500) -> Dict[str, float]:
    """Развернуть meta_json в плоский dict только численных значений.

    Пример:
      {'params': {'k': 10, 'nested': {'a': 1}}} ->
        {'params.k': 10.0, 'params.nested.a': 1.0}

    Ограничение max_items защищает UI от огромных meta.
    """
    out: Dict[str, float] = {}
    if not isinstance(meta, dict):
        return out

    def rec(prefix: str, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                rec(f"{prefix}{k}.", v)
        elif isinstance(obj, (int, float)) and np.isfinite(obj):
            key = prefix[:-1] if prefix.endswith(".") else prefix
            out[str(key)] = float(obj)
        else:
            return

    rec("", meta)

    if len(out) > int(max_items):
        keys = sorted(out.keys())[: int(max_items)]
        out = {k: out[k] for k in keys}

    return out


def build_feature_df(
    metas: Dict[str, Dict],
    run_labels: List[str],
    *,
    max_features: int = 200,
    key_prefix_whitelist: Optional[List[str]] = None,
    key_regex: Optional[str] = None,
    drop_constant: bool = True,
) -> pd.DataFrame:
    """Собрать X-матрицу (runs × features) из meta.

    Параметры:
      - key_prefix_whitelist: оставить только ключи, начинающиеся с одного из префиксов
      - key_regex: regex-фильтр по имени ключа
      - drop_constant: удалить фичи, которые не меняются между прогонами

    Возвращает DataFrame индексом run_labels.
    """
    rows: List[Dict[str, float]] = []
    for lab in run_labels:
        m = metas.get(lab, {}) if isinstance(metas, dict) else {}
        flat = flatten_meta_numeric(m, max_items=max(500, max_features * 5))
        if key_prefix_whitelist:
            flat = {k: v for k, v in flat.items() if any(str(k).startswith(p) for p in key_prefix_whitelist)}
        rows.append(flat)

    df = pd.DataFrame(rows, index=run_labels, dtype=float)

    if key_regex:
        try:
            df = df.filter(regex=str(key_regex), axis=1)
        except Exception:
            pass

    if drop_constant and not df.empty:
        keep = []
        for c in df.columns:
            v = df[c].to_numpy(dtype=float)
            m = np.isfinite(v)
            if m.sum() < 2:
                continue
            uniq = np.unique(v[m])
            if uniq.size >= 2:
                keep.append(c)
        df = df[keep]

    # limit by variance (best-effort)
    if max_features and df.shape[1] > int(max_features):
        try:
            var = df.var(axis=0, numeric_only=True)
            cols = list(var.sort_values(ascending=False).index[: int(max_features)])
            df = df[cols]
        except Exception:
            df = df.iloc[:, : int(max_features)]

    return df


# ---------------------------- metrics ----------------------------

_METRICS = ["RMS", "MAXABS", "MEANABS", "P2P"]


def available_metrics() -> List[str]:
    return list(_METRICS)


def _metric_value(metric: str, y: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return float("nan")
    m = np.isfinite(y)
    if m.sum() == 0:
        return float("nan")
    yy = y[m]
    metric = str(metric).upper().strip()
    if metric == "RMS":
        return float(np.sqrt(np.mean(yy * yy)))
    if metric == "MAXABS":
        return float(np.max(np.abs(yy)))
    if metric == "MEANABS":
        return float(np.mean(np.abs(yy)))
    if metric == "P2P":
        return float(np.max(yy) - np.min(yy))
    return float("nan")


def build_metric_df(
    bundles: List[Tuple[str, Dict[str, pd.DataFrame]]],
    *,
    ref_label: str,
    table: str,
    sigs: List[str],
    metrics: List[str],
    mode_delta: bool,
    dist_unit: str,
    angle_unit: str,
    p_atm: float,
    pressure_mode: str,
    zero_baseline: bool,
    baseline_mode: str,
    baseline_window_s: float,
    baseline_first_n: int,
    flow_unit: str,
    time_window: Optional[Tuple[float, float]] = None,
) -> pd.DataFrame:
    """Собрать Y-матрицу (runs × metric(sig)).

    Если mode_delta=True, считаем метрики от Δ относительно ref.
    """
    bundles_dict = dict(bundles)
    if ref_label not in bundles_dict:
        raise KeyError(f"ref_label '{ref_label}' not in bundles")

    # reference series per signal (common x)
    ref_tables = bundles_dict[ref_label]

    metric_cols: List[str] = []
    # we compute per signal then append metrics
    out_rows = []

    # precompute reference grid per signal (allows per-signal time window masking)
    ref_cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for sig in sigs:
        x_ref, y_ref, _unit = get_xy(
            ref_tables,
            table,
            sig,
            dist_unit=dist_unit,
            angle_unit=angle_unit,
            p_atm=float(p_atm),
            zero_baseline=bool(zero_baseline),
            baseline_mode=str(baseline_mode),
            baseline_window_s=float(baseline_window_s),
            baseline_first_n=int(baseline_first_n),
            flow_unit=str(flow_unit),
            pressure_mode=str(pressure_mode),
        )
        if time_window and x_ref.size:
            m = (x_ref >= float(time_window[0])) & (x_ref <= float(time_window[1]))
            if m.any():
                x_ref = x_ref[m]
                y_ref = y_ref[m]
        ref_cache[str(sig)] = (np.asarray(x_ref, float), np.asarray(y_ref, float))

    for run_label, tables in bundles:
        row: Dict[str, float] = {}
        for sig in sigs:
            x_ref, y_ref = ref_cache.get(str(sig), (np.asarray([], float), np.asarray([], float)))
            x, y, _u = get_xy(
                tables,
                table,
                sig,
                dist_unit=dist_unit,
                angle_unit=angle_unit,
                p_atm=float(p_atm),
                zero_baseline=bool(zero_baseline),
                baseline_mode=str(baseline_mode),
                baseline_window_s=float(baseline_window_s),
                baseline_first_n=int(baseline_first_n),
                flow_unit=str(flow_unit),
                pressure_mode=str(pressure_mode),
            )
            if time_window and x.size:
                m = (x >= float(time_window[0])) & (x <= float(time_window[1]))
                if m.any():
                    x = x[m]
                    y = y[m]

            if x_ref.size and y_ref.size:
                y_i = resample_linear(x, y, x_ref)
            else:
                y_i = np.asarray(y, float)

            if mode_delta:
                if run_label == ref_label:
                    d = np.zeros_like(y_ref) if y_ref.size else np.zeros_like(y_i)
                else:
                    # align to ref window if present
                    if y_ref.size:
                        d = y_i - y_ref
                    else:
                        d = y_i
            else:
                d = y_i

            for met in metrics:
                name = f"{met.upper()}({sig})"
                row[name] = _metric_value(met, d)
        out_rows.append(row)

    df = pd.DataFrame(out_rows, index=[lab for lab, _ in bundles], dtype=float)
    # stable column order
    df = df.reindex(sorted(df.columns), axis=1)
    return df


# ---------------------------- correlation ----------------------------


def _pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return float("nan")
    xx = x[m]
    yy = y[m]
    if np.std(xx) < 1e-12 or np.std(yy) < 1e-12:
        return float("nan")
    return float(np.corrcoef(xx, yy)[0, 1])


def _spearman_corr(x: np.ndarray, y: np.ndarray) -> float:
    # nan-aware rank corr via pandas
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return float("nan")
    xs = pd.Series(x[m]).rank(method="average").to_numpy(dtype=float)
    ys = pd.Series(y[m]).rank(method="average").to_numpy(dtype=float)
    if np.std(xs) < 1e-12 or np.std(ys) < 1e-12:
        return float("nan")
    return float(np.corrcoef(xs, ys)[0, 1])


def corr_matrix(
    feature_df: pd.DataFrame,
    metric_df: pd.DataFrame,
    *,
    method: str = "pearson",
    min_pairs: int = 3,
) -> pd.DataFrame:
    """Посчитать корреляцию (features × metrics)."""
    if feature_df is None or metric_df is None or feature_df.empty or metric_df.empty:
        return pd.DataFrame()

    # align by index
    idx = feature_df.index.intersection(metric_df.index)
    X = feature_df.loc[idx]
    Y = metric_df.loc[idx]

    method = str(method).lower().strip()
    corr_fun = _spearman_corr if method.startswith("s") else _pearson_corr

    out = np.full((X.shape[1], Y.shape[1]), np.nan, dtype=float)

    for i, fc in enumerate(X.columns):
        xi = X[fc].to_numpy(dtype=float)
        for j, mc in enumerate(Y.columns):
            yj = Y[mc].to_numpy(dtype=float)
            m = np.isfinite(xi) & np.isfinite(yj)
            if m.sum() < int(min_pairs):
                continue
            out[i, j] = corr_fun(xi, yj)

    return pd.DataFrame(out, index=list(X.columns), columns=list(Y.columns), dtype=float)


# ---------------------------- helpers for UI ----------------------------


def topk_by_absmax(df: pd.DataFrame, *, k: int, axis: int = 0) -> List[str]:
    """Выбрать top-k по max(|.|) вдоль оси.

    axis=0 -> по колонкам (вернём имена колонок)
    axis=1 -> по строкам
    """
    if df is None or df.empty or k <= 0:
        return []

    try:
        if axis == 0:
            score = df.abs().max(axis=0)
        else:
            score = df.abs().max(axis=1)
        return list(score.sort_values(ascending=False).index[: int(k)])
    except Exception:
        return list(df.columns[: int(k)]) if axis == 0 else list(df.index[: int(k)])
