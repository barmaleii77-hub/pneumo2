# -*- coding: utf-8 -*-
"""bootstrap_utils_v1.py

Утилиты для *быстрого* bootstrap-анализа устойчивости multiobjective метрик
без повторной симуляции.

Идея:
- fit_worker_v3_suite_identify.py сохраняет fit_details.json, где каждая строка
  содержит вклад сигнала в SSE (unbiased и effective) по каждому тесту.
- Если нам нужно оценить устойчивость целей (например, RMSE по группам pressure/kinematics)
  к изменению набора тестов, можно делать bootstrap по тестам:
  пересэмплировать тесты с возвращением и агрегировать SSE/n.

Это очень дешёвая операция по сравнению с повторным прогоном симуляции.

Примечание:
- Мы используем *unbiased* SSE (sse_unb), чтобы оценивать физическую ошибку
  без влияния выбранных group_gain для trade-off.

"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def load_details_signals_df(details_json: Path) -> pd.DataFrame:
    """Загрузить fit_details.json и вернуть DataFrame signals."""
    with open(details_json, "r", encoding="utf-8") as f:
        det = json.load(f)
    df = pd.DataFrame(det.get("signals", []))
    if not df.empty:
        df.columns = [str(c).strip() for c in df.columns]
    return df


def filter_group(df_signals: pd.DataFrame, which: str) -> pd.DataFrame:
    """Фильтр по train/holdout.

    which:
      - 'train'   -> group == 'train'
      - 'holdout' -> group != 'train'
      - 'all'     -> без фильтра
    """
    which = str(which).lower().strip()
    if df_signals.empty:
        return df_signals
    if "group" not in df_signals.columns:
        return df_signals
    if which == "train":
        return df_signals[df_signals["group"].astype(str) == "train"]
    if which == "holdout":
        return df_signals[df_signals["group"].astype(str) != "train"]
    return df_signals


@dataclass
class GroupByTestArrays:
    tests: List[str]
    sseA: np.ndarray
    nA: np.ndarray
    sseB: np.ndarray
    nB: np.ndarray


def build_group_by_test_arrays(
    df_signals: pd.DataFrame,
    groupA: str,
    groupB: str,
    which: str = "holdout",
) -> GroupByTestArrays:
    """Преобразовать signals DataFrame в компактные массивы по тестам.

    Возвращает:
      tests: список имён тестов
      sseA/nA: unbiased SSE и n для группы groupA по каждому тесту
      sseB/nB: то же для groupB

    Если в тесте нет сигналов группы -> n=0, sse=0.
    """
    df = filter_group(df_signals, which=which)
    if df.empty:
        return GroupByTestArrays(tests=[], sseA=np.zeros(0), nA=np.zeros(0), sseB=np.zeros(0), nB=np.zeros(0))

    for c in ("test", "sig_group", "n"):
        if c not in df.columns:
            raise ValueError(f"details signals df missing column '{c}'")

    if "sse_unb" not in df.columns:
        # legacy fallback
        if "sse" in df.columns and "group_gain" in df.columns:
            gg = pd.to_numeric(df["group_gain"], errors="coerce").fillna(1.0).replace(0.0, np.nan)
            sse = pd.to_numeric(df["sse"], errors="coerce").fillna(0.0)
            df = df.copy()
            df["sse_unb"] = (sse / (gg ** 2)).fillna(0.0)
        else:
            raise ValueError("details signals df missing sse_unb and no legacy fallback")

    df = df.copy()
    df["n"] = pd.to_numeric(df["n"], errors="coerce").fillna(0.0)
    df["sse_unb"] = pd.to_numeric(df["sse_unb"], errors="coerce").fillna(0.0)
    df["sig_group"] = df["sig_group"].astype(str)
    df["test"] = df["test"].astype(str)

    tests = sorted(df["test"].unique().tolist())
    idx = {t: i for i, t in enumerate(tests)}

    sseA = np.zeros(len(tests), dtype=float)
    nA = np.zeros(len(tests), dtype=float)
    sseB = np.zeros(len(tests), dtype=float)
    nB = np.zeros(len(tests), dtype=float)

    for grp, sse_arr, n_arr in ((groupA, sseA, nA), (groupB, sseB, nB)):
        sub = df[df["sig_group"] == str(grp)]
        if sub.empty:
            continue
        g = sub.groupby("test", as_index=False).agg(sse=("sse_unb", "sum"), n=("n", "sum"))
        for _, r in g.iterrows():
            i = idx.get(str(r["test"]))
            if i is None:
                continue
            sse_arr[i] = float(r["sse"])
            n_arr[i] = float(r["n"])

    return GroupByTestArrays(tests=tests, sseA=sseA, nA=nA, sseB=sseB, nB=nB)


def rmse_from_sse_n(sse: float, n: float) -> float:
    if n <= 0.0:
        return float("nan")
    return float(math.sqrt(float(sse) / float(n)))


def bootstrap_two_group_rmse(
    arrays: GroupByTestArrays,
    reps: int = 200,
    seed: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Bootstrap по тестам (с возвращением).

    Возвращает массивы:
      rmseA[reps], rmseB[reps]

    Если список тестов пуст -> массивы nan.
    """
    m = len(arrays.tests)
    if m <= 0:
        return (np.full(int(reps), np.nan, dtype=float), np.full(int(reps), np.nan, dtype=float))

    rng = np.random.default_rng(int(seed))
    rmseA = np.full(int(reps), np.nan, dtype=float)
    rmseB = np.full(int(reps), np.nan, dtype=float)

    for k in range(int(reps)):
        idx = rng.integers(0, m, size=m, endpoint=False)
        sseA = float(np.sum(arrays.sseA[idx]))
        nA = float(np.sum(arrays.nA[idx]))
        sseB = float(np.sum(arrays.sseB[idx]))
        nB = float(np.sum(arrays.nB[idx]))
        rmseA[k] = rmse_from_sse_n(sseA, nA)
        rmseB[k] = rmse_from_sse_n(sseB, nB)

    return rmseA, rmseB


def summarize_bootstrap(x: np.ndarray) -> Dict[str, float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"mean": float("nan"), "std": float("nan"), "p50": float("nan"), "p90": float("nan"), "p95": float("nan")}
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x, ddof=1)) if x.size > 1 else 0.0,
        "p50": float(np.percentile(x, 50)),
        "p90": float(np.percentile(x, 90)),
        "p95": float(np.percentile(x, 95)),
    }


def feasibility_prob(xB: np.ndarray, eps: float, tol: float = 0.0) -> float:
    x = np.asarray(xB, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    try:
        thr = float(eps) * (1.0 + float(tol))
    except Exception:
        return float("nan")
    if not math.isfinite(thr):
        return float("nan")
    return float(np.mean(x <= thr))
