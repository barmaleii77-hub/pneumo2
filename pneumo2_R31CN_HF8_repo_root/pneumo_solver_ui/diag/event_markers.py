# -*- coding: utf-8 -*-
"""event_markers.py

Дискретные события ("галька") для визуализации результатов симуляции.

Зачем
-----
Во многих тестах пневмоподвески важны **пороговые события**:
отрыв колеса, открытие/закрытие клапана, пробой/упор в отбойник,
смена контакта колесо‑дорога и т.п.

Если их не показывать, пользователь видит "кривые" и вынужден угадывать,
где именно сработало событие. Этот модуль:

1) автоматически ищет дискретные (boolean/int) сигналы,
2) извлекает моменты переключения,
3) даёт удобный DataFrame/JSON для UI (Web + Qt).

Принципы
---------
- Без тяжёлых зависимостей.
- Best‑effort эвристики по данным и по имени сигнала.
- Без "экспертных" настроек — разумные дефолты + возможность выбрать.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class Event:
    table: str
    signal: str
    t: float
    v_from: float
    v_to: float


DEFAULT_NAME_HINTS: Tuple[str, ...] = (
    # RU
    "клапан",
    "отрыв",
    "контакт",
    "пробой",
    "отбой",
    "упор",
    "бамп",
    # EN
    "valve",
    "open",
    "close",
    "lift",
    "contact",
    "ground",
    "bump",
    "limit",
    "saturation",
    "hit",
)


DEFAULT_EXCLUDE_HINTS: Tuple[str, ...] = (
    "index",
    "idx",
    "id",
    "seed",
    "hash",
    "step",
)


def _safe_time_col(df: pd.DataFrame) -> Optional[str]:
    """Best-effort time column detection (локально, без compare_ui)."""
    if df is None or df.empty:
        return None

    for c in ("t", "time", "Time", "sec", "s"):
        if c in df.columns:
            return c
    for c in df.columns:
        try:
            v = np.asarray(df[c].values, dtype=float)
            if v.size >= 2 and np.isfinite(v).any():
                return c
        except Exception:
            continue
    return None


def _is_small_discrete(values: np.ndarray, *, max_unique: int = 4) -> bool:
    """True если массив похож на дискретный (0/1/2...) сигнал."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return False

    try:
        uniq = np.unique(v)
    except Exception:
        return False
    if uniq.size <= 1 or uniq.size > int(max_unique):
        return False

    if np.max(np.abs(uniq - np.round(uniq))) > 1e-9:
        return False
    return True


def _name_score(name: str, *, hints: Sequence[str], exclude: Sequence[str]) -> float:
    n = (name or "").strip().lower()
    if not n:
        return 0.0
    for bad in exclude:
        if bad in n:
            return 0.0
    score = 0.0
    for h in hints:
        if h in n:
            score += 1.0
    if n.startswith("is_") or n.startswith("has_") or n.endswith("_flag"):
        score += 0.25
    return score


def _transition_events(t: np.ndarray, v: np.ndarray, *, rising_only: bool) -> List[Event]:
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    if t.size < 2 or v.size < 2:
        return []
    n = min(t.size, v.size)
    t = t[:n]
    v = v[:n]

    m = np.isfinite(t) & np.isfinite(v)
    if int(m.sum()) < 2:
        return []

    t2 = t[m]
    v2 = v[m]

    dv = np.diff(v2)
    idx = np.where(dv != 0)[0]
    if idx.size == 0:
        return []

    out: List[Event] = []
    for i in idx.tolist():
        v_from = float(v2[i])
        v_to = float(v2[i + 1])
        if rising_only and not (v_to > v_from):
            continue
        out.append(Event(table="", signal="", t=float(t2[i + 1]), v_from=v_from, v_to=v_to))
    return out


def scan_run_tables(
    tables: Dict[str, pd.DataFrame],
    *,
    max_signals: int = 80,
    max_events: int = 4000,
    max_unique: int = 4,
    name_hints: Sequence[str] = DEFAULT_NAME_HINTS,
    exclude_hints: Sequence[str] = DEFAULT_EXCLUDE_HINTS,
    rising_only: bool = True,
) -> List[Event]:
    """Найти события (переключения) по таблицам одного прогона."""

    if not isinstance(tables, dict) or not tables:
        return []

    candidates: List[Tuple[float, str, str, np.ndarray, np.ndarray]] = []
    for tname, df in tables.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        tcol = _safe_time_col(df)
        if not tcol or tcol not in df.columns:
            continue
        try:
            t = np.asarray(df[tcol].values, dtype=float)
        except Exception:
            continue
        if t.size < 2:
            continue

        for col in df.columns:
            if col == tcol:
                continue
            score = _name_score(str(col), hints=name_hints, exclude=exclude_hints)
            try:
                v = np.asarray(df[col].values, dtype=float)
            except Exception:
                continue

            if not _is_small_discrete(v, max_unique=int(max_unique)):
                # если имя выглядит "очень событийным" — расширим порог
                if score >= 2.0 and _is_small_discrete(v, max_unique=min(int(max_unique) + 2, 8)):
                    pass
                else:
                    continue

            v_fin = v[np.isfinite(v)]
            if v_fin.size < 2:
                continue
            if np.nanmin(v_fin) == np.nanmax(v_fin):
                continue

            try:
                uniq = np.unique(np.round(v_fin).astype(int))
                if uniq.size <= 2 and set(uniq.tolist()).issubset({0, 1}):
                    score += 0.75
            except Exception:
                pass

            candidates.append((float(score), str(tname), str(col), t, v))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    candidates = candidates[: int(max_signals)]

    out: List[Event] = []
    for _score, tname, col, t, v in candidates:
        evs = _transition_events(t, v, rising_only=bool(rising_only))
        for e in evs:
            e.table = tname
            e.signal = col
        out.extend(evs)
        if len(out) >= int(max_events):
            break

    out.sort(key=lambda e: (float(e.t), e.table, e.signal))
    return out[: int(max_events)]


def events_to_frame(events: Sequence[Event]) -> pd.DataFrame:
    rows = []
    for e in events or []:
        rows.append(
            {
                "table": str(e.table),
                "signal": str(e.signal),
                "t": float(e.t),
                "from": float(e.v_from),
                "to": float(e.v_to),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["t", "table", "signal"], kind="mergesort").reset_index(drop=True)
    return df


def summarize(events: Sequence[Event]) -> pd.DataFrame:
    df = events_to_frame(events)
    if df.empty:
        return pd.DataFrame(columns=["signal", "table", "count", "t_first", "t_last"])
    g = df.groupby(["signal", "table"], as_index=False)
    out = g.agg(count=("t", "size"), t_first=("t", "min"), t_last=("t", "max"))
    out = out.sort_values(["count", "signal"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    return out


def pick_top_signals(events: Sequence[Event], k: int = 6) -> List[str]:
    k = int(max(0, k))
    if k <= 0:
        return []
    s = summarize(events)
    if s.empty:
        return []
    return [str(x) for x in s.head(k)["signal"].tolist()]
