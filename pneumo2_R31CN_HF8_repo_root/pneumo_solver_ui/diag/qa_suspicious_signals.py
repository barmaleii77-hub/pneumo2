# -*- coding: utf-8 -*-
"""qa_suspicious_signals.py

Автоматический анализ «подозрительных» сигналов (QA) для визуализации.

Зачем
----
В инженерном UI пользователь чаще доверяет картинке, чем цифрам. Если данные
содержат NaN/Inf, не монотонное время, «пики», скачки или сильные дрейфы,
красивые графики будут вводить в заблуждение.

Этот модуль делает *лёгкие*, быстрые и достаточно общие проверки:
  - NaN/Inf (в сигнале)
  - резкие скачки/пики (по diff)
  - грубые выбросы (robust z-score)
  - заметный дрейф между началом и концом окна

Важно
-----
* Это НЕ физическая валидация модели.
* Это «QA для UI», ориентированная на быстрый качественный анализ.
* Без тяжёлых зависимостей. Только numpy/pandas.

Использование
------------
Web/Qt:
  - вызывайте :func:`scan_run_tables` для каждого run
  - агрегируйте список issues в DataFrame через :func:`issues_to_frame`
  - строите матрицу severity через :func:`severity_matrix`
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ------------------------------
# Datamodel
# ------------------------------


@dataclass
class QAIssue:
    run_label: str
    table: str
    signal: str
    code: str
    severity: int  # 1..3 (1=minor, 2=warn, 3=error)
    message: str
    t0: Optional[float] = None
    t1: Optional[float] = None
    details: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("details") is None:
            d["details"] = {}
        return d


# ------------------------------
# Helpers
# ------------------------------


def _safe_time_vector(df: pd.DataFrame) -> np.ndarray:
    """Best-effort: достать t без падений."""
    try:
        try:
            from pneumo_solver_ui.compare_ui import detect_time_col, extract_time_vector  # type: ignore
        except Exception:
            from compare_ui import detect_time_col, extract_time_vector  # type: ignore
    except Exception:
        if df is None or df.empty:
            return np.zeros(0, dtype=float)
        try:
            return np.asarray(df.iloc[:, 0].values, dtype=float)
        except Exception:
            return np.zeros(0, dtype=float)

    if df is None or df.empty:
        return np.zeros(0, dtype=float)
    tcol = None
    try:
        tcol = detect_time_col(df)
    except Exception:
        tcol = None
    try:
        return np.asarray(extract_time_vector(df, tcol), dtype=float)
    except Exception:
        try:
            return np.asarray(extract_time_vector(df), dtype=float)
        except Exception:
            try:
                return np.asarray(df.iloc[:, 0].values, dtype=float)
            except Exception:
                return np.zeros(0, dtype=float)


def _robust_scale(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        return float(np.nanstd(x)) if x.size else 0.0
    med = float(np.nanmedian(x))
    mad = float(np.nanmedian(np.abs(x - med)))
    return 1.4826 * mad


def _group_consecutive(idxs: np.ndarray) -> List[Tuple[int, int]]:
    """Group sorted indices into [start,end] inclusive."""
    if idxs is None:
        return []
    idxs = np.asarray(idxs, dtype=int)
    if idxs.size == 0:
        return []
    idxs = np.unique(idxs)
    idxs.sort()
    groups: List[Tuple[int, int]] = []
    s = int(idxs[0])
    e = int(idxs[0])
    for v in idxs[1:]:
        v = int(v)
        if v == e + 1:
            e = v
        else:
            groups.append((s, e))
            s = v
            e = v
    groups.append((s, e))
    return groups


def _preset_thresholds(sensitivity: str) -> Dict[str, float]:
    s = str(sensitivity or "normal").strip().lower()
    if s in ("low", "низкая", "low_sensitivity"):
        return {"spike_z": 12.0, "outlier_z": 10.0, "drift_frac": 0.35}
    if s in ("high", "высокая", "high_sensitivity"):
        return {"spike_z": 6.0, "outlier_z": 6.0, "drift_frac": 0.18}
    # normal
    return {"spike_z": 8.0, "outlier_z": 8.0, "drift_frac": 0.25}


# ------------------------------
# Core
# ------------------------------


def scan_run_tables(
    tables: Dict[str, pd.DataFrame],
    *,
    run_label: str,
    table: str,
    signals: Sequence[str],
    sensitivity: str = "normal",
    time_window: Optional[Tuple[float, float]] = None,
    max_signals: int = 60,
    max_issues: int = 800,
) -> List[QAIssue]:
    """Scan one run for suspicious signal patterns.

    Args:
        tables: mapping table->DataFrame.
        run_label: pretty run name.
        table: table to scan.
        signals: candidate signals.
        sensitivity: 'low'|'normal'|'high'.
        time_window: optional (t0,t1) to restrict analysis.
        max_signals: limit for performance.
        max_issues: safety limit.

    Returns:
        list of QAIssue.
    """

    out: List[QAIssue] = []

    df = tables.get(str(table))
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        out.append(
            QAIssue(
                run_label=str(run_label),
                table=str(table),
                signal="*",  # table-level
                code="table_missing",
                severity=2,
                message=f"Таблица '{table}' отсутствует или пуста",
                details={},
            )
        )
        return out

    thr = _preset_thresholds(sensitivity)
    spike_z = float(thr["spike_z"])
    outlier_z = float(thr["outlier_z"])
    drift_frac = float(thr["drift_frac"])

    # Build mask for window once (index-aligned)
    time_mask = None
    if time_window is not None:
        t_full = _safe_time_vector(df)
        t_full = np.asarray(t_full, dtype=float).ravel()
        if t_full.size:
            a, b = float(time_window[0]), float(time_window[1])
            if np.isfinite(a) and np.isfinite(b):
                time_mask = (t_full >= min(a, b)) & (t_full <= max(a, b))
                if not bool(time_mask.any()):
                    time_mask = None

    sigs = list(signals)[: max(1, int(max_signals))]

    for s in sigs:
        if s not in df.columns:
            continue
        try:
            y = np.asarray(df[s].values, dtype=float)
        except Exception:
            continue

        if time_mask is not None and time_mask.shape[0] == y.shape[0]:
            y_use = y[time_mask]
            t_use = _safe_time_vector(df)
            t_use = np.asarray(t_use, dtype=float).ravel()[time_mask]
        else:
            y_use = y
            t_use = _safe_time_vector(df)
            t_use = np.asarray(t_use, dtype=float).ravel()

        if y_use.size < 12:
            continue

        finite = np.isfinite(y_use)
        bad = int(np.sum(~finite))
        if bad > 0:
            frac = float(bad) / max(1, int(y_use.size))
            sev = 3 if frac >= 0.01 else 2
            out.append(
                QAIssue(
                    run_label=str(run_label),
                    table=str(table),
                    signal=str(s),
                    code="nan_inf",
                    severity=sev,
                    message=f"NaN/Inf = {bad} ({frac*100:.2f}%)",
                    details={"bad": bad, "n": int(y_use.size), "frac": frac},
                )
            )
            if len(out) >= max_issues:
                break

        # Work only with finite part
        yv = np.asarray(y_use[finite], dtype=float)
        tv = np.asarray(t_use[finite], dtype=float) if t_use.size == y_use.size else None
        if yv.size < 16:
            continue

        # --- robust outliers on values
        sc = _robust_scale(yv)
        if np.isfinite(sc) and sc > 0:
            med = float(np.nanmedian(yv))
            z = np.abs(yv - med) / max(sc, 1e-12)
            idx = np.where(np.isfinite(z) & (z > outlier_z))[0]
            if idx.size:
                frac = float(idx.size) / max(1, int(yv.size))
                sev = 2 if frac < 0.02 else 3
                t0 = float(tv[int(idx[0])]) if tv is not None and tv.size else None
                t1 = float(tv[int(idx[-1])]) if tv is not None and tv.size else None
                out.append(
                    QAIssue(
                        run_label=str(run_label),
                        table=str(table),
                        signal=str(s),
                        code="outliers",
                        severity=sev,
                        message=f"Выбросы по значению: {idx.size} ({frac*100:.2f}%)",
                        t0=t0,
                        t1=t1,
                        details={"n": int(yv.size), "n_out": int(idx.size), "z_thr": outlier_z},
                    )
                )
                if len(out) >= max_issues:
                    break

        # --- spikes/jumps on diff
        dy = np.diff(yv)
        if dy.size >= 12:
            scd = _robust_scale(dy)
            if np.isfinite(scd) and scd > 0:
                med_dy = float(np.nanmedian(dy))
                z2 = np.abs(dy - med_dy) / max(scd, 1e-12)
                idx2 = np.where(np.isfinite(z2) & (z2 > spike_z))[0]
                if idx2.size:
                    groups = _group_consecutive(idx2)
                    n_groups = len(groups)
                    sev = 2 if n_groups <= 3 else 3
                    if tv is not None and tv.size == yv.size:
                        s0, e0 = groups[0]
                        t0 = float(tv[int(s0)])
                        t1 = float(tv[int(min(e0 + 1, tv.size - 1))])
                    else:
                        t0, t1 = None, None
                    out.append(
                        QAIssue(
                            run_label=str(run_label),
                            table=str(table),
                            signal=str(s),
                            code="spikes",
                            severity=sev,
                            message=f"Резкие скачки/пики: групп={n_groups} (threshold={spike_z:g}σ)",
                            t0=t0,
                            t1=t1,
                            details={"groups": n_groups, "spike_z": spike_z},
                        )
                    )
                    if len(out) >= max_issues:
                        break

        # --- drift between start and end of window
        w = int(max(8, min(400, round(0.12 * float(yv.size)))))
        if yv.size >= w * 2:
            a0 = yv[:w]
            a1 = yv[-w:]
            if np.isfinite(a0).any() and np.isfinite(a1).any():
                m0 = float(np.nanmean(a0))
                m1 = float(np.nanmean(a1))
                p5 = float(np.nanpercentile(yv, 5))
                p95 = float(np.nanpercentile(yv, 95))
                amp = float(p95 - p5)
                if np.isfinite(amp) and amp > 1e-12:
                    d = abs(m1 - m0)
                    if d > drift_frac * amp:
                        sev = 2
                        if d > 0.6 * amp:
                            sev = 3
                        t0 = float(tv[0]) if tv is not None and tv.size else None
                        t1 = float(tv[-1]) if tv is not None and tv.size else None
                        out.append(
                            QAIssue(
                                run_label=str(run_label),
                                table=str(table),
                                signal=str(s),
                                code="drift",
                                severity=sev,
                                message=f"Дрейф (start→end): {d:.4g} (~{d/amp*100:.1f}% амплитуды)",
                                t0=t0,
                                t1=t1,
                                details={
                                    "mean_start": m0,
                                    "mean_end": m1,
                                    "amp_p95_p5": amp,
                                    "drift_frac": drift_frac,
                                },
                            )
                        )
                        if len(out) >= max_issues:
                            break

    if len(out) > max_issues:
        out = out[:max_issues]
    return out


def issues_to_frame(issues: Iterable[QAIssue | Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for it in issues:
        if isinstance(it, QAIssue):
            rows.append(it.to_dict())
        elif isinstance(it, dict):
            rows.append(dict(it))
    if not rows:
        return pd.DataFrame(
            columns=[
                "run_label",
                "table",
                "signal",
                "code",
                "severity",
                "message",
                "t0",
                "t1",
                "details",
            ]
        )
    df = pd.DataFrame(rows)
    cols = ["run_label", "table", "signal", "code", "severity", "message", "t0", "t1", "details"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]
    try:
        df = df.sort_values(["severity", "run_label", "signal", "code"], ascending=[False, True, True, True])
    except Exception:
        pass
    return df


def severity_matrix(
    df_issues: pd.DataFrame,
    *,
    run_labels: Sequence[str],
    signals: Sequence[str],
) -> Tuple[np.ndarray, Dict[Tuple[str, str], float]]:
    """Build severity matrix [signals × runs] and first-issue-time map."""

    runs = [str(r) for r in run_labels]
    sigs = [str(s) for s in signals]
    Z = np.zeros((len(sigs), len(runs)), dtype=float)
    first_t: Dict[Tuple[str, str], float] = {}
    if df_issues is None or df_issues.empty:
        return Z, first_t

    try:
        # Faster lookup maps
        run_idx = {r: i for i, r in enumerate(runs)}
        sig_idx = {s: i for i, s in enumerate(sigs)}

        for _, row in df_issues.iterrows():
            r = str(row.get("run_label", ""))
            s = str(row.get("signal", ""))
            if r not in run_idx or s not in sig_idx:
                continue
            i = sig_idx[s]
            j = run_idx[r]
            sev = float(row.get("severity", 0) or 0)
            if sev > Z[i, j]:
                Z[i, j] = sev
            t0 = row.get("t0")
            if t0 is not None and isinstance(t0, (int, float)) and np.isfinite(float(t0)):
                key = (r, s)
                if key not in first_t or float(t0) < float(first_t[key]):
                    first_t[key] = float(t0)
    except Exception:
        pass

    return Z, first_t


def summarize(df_issues: pd.DataFrame) -> Dict[str, Any]:
    if df_issues is None or df_issues.empty:
        return {"ok": True, "n": 0, "n_warn": 0, "n_err": 0}
    sev = pd.to_numeric(df_issues.get("severity"), errors="coerce").fillna(0)
    n = int(len(df_issues))
    n_err = int((sev >= 3).sum())
    n_warn = int(((sev >= 2) & (sev < 3)).sum())
    return {"ok": n_err == 0, "n": n, "n_warn": n_warn, "n_err": n_err}
