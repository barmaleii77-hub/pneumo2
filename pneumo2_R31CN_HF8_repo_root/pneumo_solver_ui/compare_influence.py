# -*- coding: utf-8 -*-
"""compare_influence.py

Общий (Web + Qt) набор утилит для анализа влияний
"параметры (meta) → эффекты/сигналы".

Зачем:
- N→N анализ: множество входных параметров → множество выходных метрик/сигналов.
- Используется в Streamlit страницах сравнения и в Qt compare viewer.

Принципы:
- Никаких тяжёлых зависимостей.
- Robust к отсутствующим/частично заполненным meta.
- Стабильный порядок + ограничения размера (чтобы UI не превращался в кашу).

NOTE:
- Здесь только математика/подготовка данных. Отрисовка — в UI слоях.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


def flatten_meta_numeric(meta: Any, *, max_items: int = 500) -> Dict[str, float]:
    """Плоское представление meta (nested dict) → {"a.b.c": float}.

    Игнорируем:
    - строки, списки, None
    - NaN/Inf

    max_items: ограничение, чтобы не убить UI.
    """

    out: Dict[str, float] = {}
    if not isinstance(meta, dict):
        return out

    def rec(prefix: str, obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                rec(f"{prefix}{k}.", v)
            return
        if isinstance(obj, (int, float)):
            try:
                fv = float(obj)
            except Exception:
                return
            if not np.isfinite(fv):
                return
            key = prefix[:-1] if prefix.endswith(".") else prefix
            out[key] = fv
            return
        # everything else ignored

    rec("", meta)

    if len(out) > int(max_items):
        keys = sorted(out.keys())[: int(max_items)]
        out = {k: out[k] for k in keys}

    return out


def build_feature_matrix(
    metas_by_label: Mapping[str, Any],
    feature_names: Sequence[str],
) -> np.ndarray:
    """Собрать матрицу X: runs × features."""

    feats: List[List[float]] = []
    for _lab, meta in metas_by_label.items():
        flat = flatten_meta_numeric(meta)
        row = [float(flat.get(k, np.nan)) for k in feature_names]
        feats.append(row)
    return np.asarray(feats, dtype=float)


def _nanvar(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    m = np.isfinite(x)
    if int(m.sum()) < 2:
        return float("nan")
    return float(np.nanvar(x[m]))


def prefilter_features_by_variance(
    X: np.ndarray,
    feature_names: Sequence[str],
    *,
    keep: int = 200,
) -> List[str]:
    """Предфильтр по дисперсии, чтобы не крутить тысячи фич.

    keep: сколько оставить (верх по дисперсии, NaN → в конец).
    """

    X = np.asarray(X, dtype=float)
    nF = int(X.shape[1]) if X.ndim == 2 else 0
    if nF == 0:
        return []

    vars_ = np.array([_nanvar(X[:, i]) for i in range(nF)], dtype=float)
    # nan vars go to end
    order = np.argsort(np.nan_to_num(vars_, nan=-1.0))[::-1]
    keep = max(1, min(int(keep), int(nF)))
    idx = order[:keep]
    return [str(feature_names[i]) for i in idx]


def pearson_corr(x: np.ndarray, y: np.ndarray, *, min_n: int = 3) -> float:
    """Pearson correlation, robust к NaN/Inf."""

    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    m = np.isfinite(x) & np.isfinite(y)
    if int(m.sum()) < int(min_n):
        return float("nan")
    try:
        return float(np.corrcoef(x[m], y[m])[0, 1])
    except Exception:
        return float("nan")


def corr_matrix(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    min_n: int = 3,
) -> np.ndarray:
    """Матрица корреляций: features × targets.

    X: (n_runs, n_features)
    Y: (n_runs, n_targets)

    Return: (n_features, n_targets)
    """

    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)

    if X.ndim != 2 or Y.ndim != 2:
        return np.zeros((0, 0), dtype=float)

    n_runs, nF = X.shape
    n_runs2, nT = Y.shape
    if n_runs != n_runs2 or n_runs < min_n or nF == 0 or nT == 0:
        return np.zeros((nF, nT), dtype=float)

    out = np.full((nF, nT), np.nan, dtype=float)
    for i in range(nF):
        xi = X[:, i]
        for j in range(nT):
            out[i, j] = pearson_corr(xi, Y[:, j], min_n=min_n)
    return out


def rank_features_by_max_abs_corr(
    corr: np.ndarray,
    feature_names: Sequence[str],
) -> List[str]:
    """Сортировка фич по силе влияния: max(|corr|) по target'ам."""

    corr = np.asarray(corr, dtype=float)
    if corr.ndim != 2 or corr.size == 0:
        return list(feature_names)

    scores = np.nanmax(np.abs(corr), axis=1)
    scores = np.nan_to_num(scores, nan=-1.0)
    order = np.argsort(scores)[::-1]
    return [str(feature_names[i]) for i in order]


def top_cells(
    corr: np.ndarray,
    feature_names: Sequence[str],
    target_names: Sequence[str],
    *,
    top_k: int = 20,
) -> List[Tuple[str, str, float]]:
    """Top-K ячеек (feature, target, corr) по |corr|."""

    corr = np.asarray(corr, dtype=float)
    if corr.ndim != 2 or corr.size == 0:
        return []

    nF, nT = corr.shape
    items: List[Tuple[str, str, float]] = []
    for i in range(nF):
        for j in range(nT):
            c = float(corr[i, j])
            if not np.isfinite(c):
                continue
            items.append((str(feature_names[i]), str(target_names[j]), c))

    items.sort(key=lambda t: abs(float(t[2])), reverse=True)
    return items[: max(1, int(top_k))]
