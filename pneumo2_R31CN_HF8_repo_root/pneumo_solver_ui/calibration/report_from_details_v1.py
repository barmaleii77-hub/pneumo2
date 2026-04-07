# -*- coding: utf-8 -*-
"""report_from_details_v1.py

Генератор человекочитаемого отчёта из результатов fit_worker_v3_suite_identify.py.

Вход:
  - fit_report.json    (основной отчёт: параметры, cov/corr, список тестов)
  - fit_details.json   (детализация по тестам/сигналам: SSE/RMSE/scale/weights)

Выход:
  - markdown отчёт (по умолчанию report.md)
  - (опционально) CSV-таблицы: tests.csv и signals.csv

Зачем:
  details_json формально удобен машине, но неудобен человеку. Этот скрипт
  превращает его в краткий отчёт:
    * train vs holdout
    * худшие тесты/сигналы
    * параметры + std + сильные корреляции

"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _load_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _fmt(x: Any, nd: int = 6) -> str:
    try:
        if x is None:
            return "-"
        xf = float(x)
        if not np.isfinite(xf):
            return str(x)
        # integer-like
        if abs(xf - round(xf)) < 1e-12 and abs(xf) < 1e12:
            return str(int(round(xf)))
        return f"{xf:.{nd}g}"
    except Exception:
        return str(x)


def _top_corr_pairs(corr: np.ndarray, keys: List[str], k: int = 12, thr: float = 0.90) -> List[Tuple[str, str, float]]:
    if corr.size == 0:
        return []
    n = corr.shape[0]
    pairs: List[Tuple[str, str, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            c = float(corr[i, j])
            if np.isfinite(c) and abs(c) >= thr:
                pairs.append((keys[i], keys[j], c))
    pairs.sort(key=lambda t: abs(t[2]), reverse=True)
    return pairs[:k]


def _df_to_markdown(df: pd.DataFrame, index: bool = False, max_rows: int = 200) -> str:
    """Безопасный вывод DataFrame в markdown.

    pandas.DataFrame.to_markdown() требует опциональную зависимость `tabulate`.
    Чтобы отчёт работал «из коробки», делаем fallback на простой markdown-генератор.
    """
    if df is None:
        return "(empty)"
    df2 = df.copy()
    if max_rows is not None and max_rows > 0 and len(df2) > max_rows:
        df2 = df2.head(int(max_rows))
    # Try tabulate-backed markdown first
    try:
        return df2.to_markdown(index=index)
    except Exception:
        pass
    # Fallback: minimal markdown table
    cols = list(df2.columns)
    if not cols:
        return "(no columns)"
    def esc(v: Any) -> str:
        s = "" if v is None else str(v)
        return s.replace("|", "\\|")
    header = "| " + " | ".join(esc(c) for c in cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for _, row in df2.iterrows():
        lines.append("| " + " | ".join(esc(row[c]) for c in cols) + " |")
    if max_rows is not None and max_rows > 0 and len(df) > max_rows:
        lines.append(f"\n*(показаны первые {max_rows} строк из {len(df)})*\n")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fit_report', required=True)
    ap.add_argument('--fit_details', required=True)
    ap.add_argument('--out_md', default='report.md')
    ap.add_argument('--out_tests_csv', default='')
    ap.add_argument('--out_signals_csv', default='')
    ap.add_argument('--top_tests', type=int, default=10)
    ap.add_argument('--top_signals', type=int, default=15)
    ap.add_argument('--corr_threshold', type=float, default=0.90)
    args = ap.parse_args()

    rep = _load_json(Path(args.fit_report))
    det = _load_json(Path(args.fit_details))

    df_tests = pd.DataFrame(det.get('tests', []))
    df_signals = pd.DataFrame(det.get('signals', []))

    # aggregate
    lines: List[str] = []
    lines.append('# Отчёт калибровки (fit_worker_v3_suite_identify)')
    lines.append('')

    lines.append('## Итог по оптимизации')
    lines.append('')
    lines.append(f"- best_rmse: **{_fmt(rep.get('best_rmse'))}**")
    lines.append(f"- best_sse: {_fmt(rep.get('best_sse'))}")
    lines.append(f"- loss: `{rep.get('loss')}`, f_scale: {_fmt(rep.get('f_scale'))}")
    lines.append(f"- record_full: {rep.get('record_full')}, record_stride: {rep.get('record_stride')}")
    lines.append(f"- auto_scale: `{rep.get('auto_scale')}`")
    lines.append(f"- tests_fit: {len(rep.get('tests_fit', []))}, tests_holdout: {len(rep.get('tests_holdout', []))}")
    lines.append('')

    # parameters
    keys = rep.get('keys', [])
    x = rep.get('x', [])
    lines.append('## Параметры')
    lines.append('')
    if keys and x and len(keys) == len(x):
        df_params = pd.DataFrame({'param': keys, 'value': x})
        cov = rep.get('cov')
        corr = rep.get('corr')
        if cov is not None:
            cov_arr = np.asarray(cov, dtype=float)
            if cov_arr.ndim == 2 and cov_arr.shape[0] == cov_arr.shape[1] == len(keys):
                std = np.sqrt(np.clip(np.diag(cov_arr), 0.0, np.inf))
                df_params['std'] = std
        # print table
        lines.append(_df_to_markdown(df_params, index=False))
    else:
        lines.append('Параметры отсутствуют в отчёте.')

    lines.append('')

    # correlations
    if rep.get('corr') is not None and keys:
        corr_arr = np.asarray(rep['corr'], dtype=float)
        pairs = _top_corr_pairs(corr_arr, list(keys), k=20, thr=float(args.corr_threshold))
        lines.append(f"## Сильные корреляции (|corr| >= {args.corr_threshold})")
        lines.append('')
        if pairs:
            dfp = pd.DataFrame(pairs, columns=['param1', 'param2', 'corr'])
            lines.append(_df_to_markdown(dfp, index=False))
        else:
            lines.append('Сильных корреляций выше порога не найдено (или cov/corr не рассчитаны).')
        lines.append('')

    # tests summary
    if not df_tests.empty:
        lines.append('## Качество по тестам')
        lines.append('')
        # overall aggregates
        for grp in ['train', 'holdout']:
            dfg = df_tests[df_tests.get('group', 'train') == grp]
            if len(dfg) == 0:
                continue
            rmse_w = np.sqrt(dfg['sse'].sum() / max(1, dfg['n'].sum()))
            lines.append(f"- {grp}: tests={len(dfg)}, RMSE={_fmt(rmse_w)}")
        lines.append('')

        df_show = df_tests.sort_values('rmse', ascending=False).head(int(args.top_tests))
        lines.append(f"### Худшие {len(df_show)} тестов по RMSE")
        lines.append('')
        lines.append(_df_to_markdown(df_show[['test', 'group', 'n', 'rmse', 'sse']], index=False))
        lines.append('')
    else:
        lines.append('## Качество по тестам')
        lines.append('')
        lines.append('details_json не содержит таблицу tests.')
        lines.append('')

    # signals summary
    if not df_signals.empty:
        lines.append('## Вклад сигналов в ошибку')
        lines.append('')

        # --- group summary (если есть sig_group/group_gain) ---
        if 'sig_group' in df_signals.columns:
            df_s = df_signals.copy()
            if 'group_gain' not in df_s.columns:
                df_s['group_gain'] = 1.0
            df_s['group_gain'] = pd.to_numeric(df_s['group_gain'], errors='coerce').fillna(1.0)
            df_s.loc[df_s['group_gain'] == 0.0, 'group_gain'] = 1.0

            # "unbiased" вклад: убираем множитель group_gain (который задаёт trade-off)
            # sse ~ (group_gain^2) * base_sse, поэтому делим на gain^2
            df_s['sse_u'] = df_s['sse'] / (df_s['group_gain'] ** 2)

            gagg = df_s.groupby(['sig_group', 'group'], as_index=False).agg(
                n=('n', 'sum'),
                sse_u=('sse_u', 'sum'),
            )
            gagg['rmse_u'] = np.sqrt(gagg['sse_u'] / gagg['n'].clip(lower=1))
            gagg = gagg.sort_values(['group', 'rmse_u'], ascending=[True, False])

            lines.append('### Качество по группам сигналов (unbiased: без множителя group_gain)')
            lines.append('')
            lines.append(_df_to_markdown(gagg[['sig_group', 'group', 'n', 'rmse_u', 'sse_u']], index=False))
            lines.append('')

        # --- aggregate over all tests (per signal) ---
        agg_cols = ['meas_table', 'meas_col', 'model_key']
        if 'sig_group' in df_signals.columns:
            agg_cols = ['sig_group'] + agg_cols

        df_agg = df_signals.groupby(agg_cols, as_index=False).agg({'sse': 'sum', 'n': 'sum'})
        df_agg['rmse'] = np.sqrt(df_agg['sse'] / df_agg['n'].clip(lower=1))
        df_agg = df_agg.sort_values('sse', ascending=False)

        topN = df_agg.head(int(args.top_signals))
        lines.append(f"### Топ-{len(topN)} сигналов по SSE (суммарно по всем тестам)")
        lines.append('')
        lines.append(_df_to_markdown(topN, index=False))
        lines.append('')

        # --- worst signals inside each test ---
        lines.append('### Худшие сигналы внутри каждого теста (по SSE)')
        lines.append('')

        # columns to show (safe intersection)
        base_cols = ['meas_table', 'meas_col', 'model_key']
        if 'sig_group' in df_signals.columns:
            base_cols += ['sig_group']
        if 'group_gain' in df_signals.columns:
            base_cols += ['group_gain']
        base_cols += ['n', 'rmse', 'sse', 'w_raw', 'scale', 'w']
        base_cols = [c for c in base_cols if c in df_signals.columns]

        for test_name, dft in df_signals.groupby('test'):
            dft2 = dft.sort_values('sse', ascending=False).head(3)
            lines.append(f"**{test_name}**")
            lines.append('')
            lines.append(_df_to_markdown(dft2[base_cols], index=False))
            lines.append('')
    else:
        lines.append('## Вклад сигналов в ошибку')
        lines.append('')
        lines.append('details_json не содержит signals.')

    out_md = Path(args.out_md)
    _save_text(out_md, '\n'.join(lines) + '\n')

    if args.out_tests_csv:
        Path(args.out_tests_csv).parent.mkdir(parents=True, exist_ok=True)
        df_tests.to_csv(args.out_tests_csv, index=False, encoding='utf-8-sig')

    if args.out_signals_csv:
        Path(args.out_signals_csv).parent.mkdir(parents=True, exist_ok=True)
        df_signals.to_csv(args.out_signals_csv, index=False, encoding='utf-8-sig')

    print(f"Wrote: {out_md}")


if __name__ == '__main__':
    main()
