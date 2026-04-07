# -*- coding: utf-8 -*-
"""compare_trust.py

Небольшая диагностика доверия к данным (trust) для UI‑графиков.

Зачем
-----
При визуальном анализе инженерных симуляций пользователь часто смотрит
на *картинку*, а не на числа. Если данные «плохие» (не монотонное время,
сломанный dt, NaN/Inf), любые красивые графики будут вводить в заблуждение.

Этот модуль даёт единый, очень лёгкий слой проверок:
  - t не монотонно возрастает
  - dt имеет некорректные значения / сильную неравномерность
  - в выбранных сигналах есть NaN/Inf

Результат предназначен для вывода статус‑баннера в Web (Streamlit)
и в Desktop (Qt).

Принципы
--------
* Без «экспертного» языка: коротко и по делу.
* Проверки best‑effort: модуль не должен ломать UI.
* Нет тяжёлых зависимостей — только numpy/pandas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class TrustIssue:
    level: str  # 'error' | 'warn'
    code: str
    message: str
    run_label: Optional[str] = None
    table: Optional[str] = None
    signal: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


def _get_tables(bundle: Any) -> Dict[str, pd.DataFrame]:
    if isinstance(bundle, dict):
        t = bundle.get("tables")
        if isinstance(t, dict):
            return {k: v for k, v in t.items() if isinstance(v, pd.DataFrame)}
        # compatibility: bundle itself may be {table: df}
        out = {k: v for k, v in bundle.items() if isinstance(v, pd.DataFrame)}
        if out:
            return out
    return {}


def _safe_time_vector(df: pd.DataFrame) -> np.ndarray:
    """Best‑effort: достать t без падений."""
    try:
        try:
            from pneumo_solver_ui.compare_ui import detect_time_col, extract_time_vector  # type: ignore
        except Exception:
            from compare_ui import detect_time_col, extract_time_vector  # type: ignore
    except Exception:
        # fallback: first column
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


def inspect_bundle(
    bundle: Any,
    *,
    run_label: str = "",
    table: str = "main",
    signals: Optional[Sequence[str]] = None,
    max_signals_check: int = 24,
) -> List[TrustIssue]:
    """Проверить один bundle на проблемы доверия.

    Важно: это *UI-диагностика*, не физическая валидация модели.
    """

    issues: List[TrustIssue] = []
    tables = _get_tables(bundle)
    df = tables.get(str(table))
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        issues.append(
            TrustIssue(
                level="warn",
                code="table_missing",
                message=f"Таблица '{table}' отсутствует или пуста",
                run_label=run_label or None,
                table=str(table),
            )
        )
        return issues

    t = _safe_time_vector(df)
    t = np.asarray(t, dtype=float).ravel()
    t = t[np.isfinite(t)]
    if t.size < 2:
        issues.append(
            TrustIssue(
                level="warn",
                code="time_short",
                message="Слишком мало точек времени для анализа dt",
                run_label=run_label or None,
                table=str(table),
                details={"n": int(t.size)},
            )
        )
    else:
        dt = np.diff(t)
        bad_nonmono = int(np.sum(dt <= 0))
        if bad_nonmono > 0:
            issues.append(
                TrustIssue(
                    level="error",
                    code="time_nonmonotonic",
                    message=f"Время не монотонно (dt<=0: {bad_nonmono})",
                    run_label=run_label or None,
                    table=str(table),
                )
            )

        # dt stats (only for dt>0)
        dtp = dt[np.isfinite(dt) & (dt > 0)]
        if dtp.size:
            dt_med = float(np.nanmedian(dtp))
            dt_min = float(np.nanmin(dtp))
            dt_max = float(np.nanmax(dtp))
            if dt_med > 0 and dt_max / max(dt_med, 1e-12) > 50.0:
                issues.append(
                    TrustIssue(
                        level="warn",
                        code="dt_irregular",
                        message=(
                            "Сетка времени сильно неравномерна "
                            f"(dt min/med/max: {dt_min:.3g}/{dt_med:.3g}/{dt_max:.3g})"
                        ),
                        run_label=run_label or None,
                        table=str(table),
                        details={"dt_min": dt_min, "dt_med": dt_med, "dt_max": dt_max},
                    )
                )
        else:
            issues.append(
                TrustIssue(
                    level="error",
                    code="dt_invalid",
                    message="Не найдено корректных dt>0 (время повреждено)",
                    run_label=run_label or None,
                    table=str(table),
                )
            )

    # NaN/Inf in signals
    if signals:
        sigs = list(signals)[: max(1, int(max_signals_check))]
        for s in sigs:
            if s not in df.columns:
                continue
            try:
                y = np.asarray(df[s].values, dtype=float)
            except Exception:
                continue
            bad = int(np.sum(~np.isfinite(y)))
            if bad > 0:
                frac = float(bad) / max(1, int(y.size))
                lvl = "error" if frac >= 0.01 else "warn"
                issues.append(
                    TrustIssue(
                        level=lvl,
                        code="nan_inf",
                        message=f"{s}: NaN/Inf = {bad} ({frac*100:.2f}%)",
                        run_label=run_label or None,
                        table=str(table),
                        signal=str(s),
                        details={"bad": bad, "n": int(y.size), "frac": frac},
                    )
                )

    return issues


def inspect_runs(
    runs: Iterable[Tuple[str, Any]],
    *,
    table: str,
    signals: Optional[Sequence[str]] = None,
) -> List[TrustIssue]:
    """Проверить несколько прогонов."""
    out: List[TrustIssue] = []
    for lab, bun in runs:
        try:
            out.extend(inspect_bundle(bun, run_label=str(lab), table=str(table), signals=signals))
        except Exception:
            out.append(
                TrustIssue(
                    level="warn",
                    code="trust_exception",
                    message="Не удалось проверить trust (исключение)",
                    run_label=str(lab),
                    table=str(table),
                )
            )
    return out


def summarize_issues(issues: Sequence[TrustIssue]) -> Tuple[str, str]:
    """Вернуть (level, one-line summary)."""
    if not issues:
        return "ok", "Данные выглядят консистентными (быстрая UI‑проверка)."
    lvl = "warn"
    if any(i.level == "error" for i in issues):
        lvl = "error"
    codes = sorted({i.code for i in issues if i.code})
    if lvl == "error":
        return lvl, "Данным нельзя доверять: " + ", ".join(codes)
    return lvl, "Есть предупреждения по данным: " + ", ".join(codes)


def format_banner_text(issues: Sequence[TrustIssue], *, max_lines: int = 6) -> str:
    """Короткий текст для баннера (Qt/statusbar)."""
    lvl, head = summarize_issues(issues)
    if lvl == "ok":
        return head
    lines = [head]
    errs = [i for i in issues if i.level == "error"]
    warns = [i for i in issues if i.level != "error"]
    ordered = errs + warns
    for it in ordered[: max(0, int(max_lines))]:
        lab = f"[{it.run_label}] " if it.run_label else ""
        lines.append(f"• {lab}{it.message}")
    return "\n".join(lines)


def render_streamlit_banner(st_mod: Any, issues: Sequence[TrustIssue]) -> None:
    """Единый trust‑баннер в Streamlit (жёлтый/красный)."""
    try:
        lvl, head = summarize_issues(issues)
        if lvl == "ok":
            st_mod.caption(head)
            return
        if lvl == "error":
            st_mod.error(head)
        else:
            st_mod.warning(head)
        with st_mod.expander("Почему нельзя/опасно доверять данным", expanded=False):
            for it in issues:
                lab = f"[{it.run_label}] " if it.run_label else ""
                st_mod.write(f"- {lab}{it.message}")
    except Exception:
        return
