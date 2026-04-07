# -*- coding: utf-8 -*-
"""
diagnose_fit_v1.py

Автоматическая диагностика результатов калибровки (fit_worker_v3_suite_identify)
и генерация "плана действий" (action_plan.md).

Зачем:
- после автоматического fit и итеративной очистки сигналов всё равно нужны ответы:
    * какие параметры упёрлись в границы;
    * какие параметры плохо определяются (большая неопределённость);
    * какие параметры "слиплись" (|corr| ~ 1);
    * какие тесты / сигналы доминируют в ошибке;
    * какие следующие шаги (OED, profile, расширить bounds, фиксировать...).

Входы:
- fit_report.json   (от fit_worker_v3_suite_identify)
- fit_details.json  (детализация по тестам/сигналам)
- fitted_base.json  (итоговые параметры, которые реально попали в модель)
- fit_ranges_json   (границы параметров)

Опционально:
- oed_report.json   (от oed_worker_v1_fim) — добавим в план показатели идентифицируемости.

Выход:
- action_plan.md (по умолчанию рядом)
- action_plan.json (опционально)

Примечание:
- Это эвристическая диагностика. Для строгих доверительных интервалов используйте profile likelihood.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def _fmt(x: Any, nd: int = 6) -> str:
    try:
        xf = float(x)
    except Exception:
        return str(x)
    if math.isfinite(xf):
        # adaptive
        ax = abs(xf)
        if ax != 0 and (ax < 1e-3 or ax > 1e6):
            return f"{xf:.{nd}e}"
        return f"{xf:.{nd}f}"
    return str(x)


def _param_table(report: Dict[str, Any], fitted: Dict[str, Any], ranges: Dict[str, List[float]],
                 bound_tol_frac: float = 0.01) -> pd.DataFrame:
    keys = list(report.get("keys", []))
    x = list(report.get("x", []))
    cov = report.get("cov", None)

    stds: Optional[np.ndarray] = None
    if cov is not None:
        try:
            C = np.asarray(cov, dtype=float)
            if C.ndim == 2 and C.shape[0] == C.shape[1] and C.shape[0] == len(keys):
                stds = np.sqrt(np.maximum(0.0, np.diag(C)))
        except Exception:
            stds = None

    rows = []
    for i, k in enumerate(keys):
        val = fitted.get(k, x[i] if i < len(x) else None)
        lohi = ranges.get(k, [None, None])
        lo = float(lohi[0]) if lohi and lohi[0] is not None else np.nan
        hi = float(lohi[1]) if lohi and lohi[1] is not None else np.nan
        span = hi - lo if (np.isfinite(lo) and np.isfinite(hi)) else np.nan

        at_lo = False
        at_hi = False
        if np.isfinite(span) and span > 0 and val is not None:
            try:
                vf = float(val)
                at_lo = (vf - lo) <= bound_tol_frac * span
                at_hi = (hi - vf) <= bound_tol_frac * span
            except Exception:
                pass

        std = float(stds[i]) if (stds is not None and i < len(stds)) else np.nan
        rel_std = np.nan
        try:
            vf = float(val)
            if vf != 0 and math.isfinite(std):
                rel_std = abs(std / vf)
        except Exception:
            pass

        rows.append({
            "param": k,
            "value": float(val) if val is not None else np.nan,
            "min": lo,
            "max": hi,
            "at_lower": bool(at_lo),
            "at_upper": bool(at_hi),
            "std": std,
            "rel_std": rel_std,
        })
    df = pd.DataFrame(rows)
    return df


def _corr_pairs(report: Dict[str, Any], corr_thr: float = 0.95, max_pairs: int = 30) -> pd.DataFrame:
    keys = list(report.get("keys", []))
    corr = report.get("corr", None)
    if corr is None:
        return pd.DataFrame([])
    try:
        R = np.asarray(corr, dtype=float)
        if R.ndim != 2 or R.shape[0] != R.shape[1] or R.shape[0] != len(keys):
            return pd.DataFrame([])
    except Exception:
        return pd.DataFrame([])

    pairs = []
    n = len(keys)
    for i in range(n):
        for j in range(i + 1, n):
            c = float(R[i, j])
            if not math.isfinite(c):
                continue
            if abs(c) >= corr_thr:
                pairs.append({
                    "p1": keys[i],
                    "p2": keys[j],
                    "corr": c,
                    "abs_corr": abs(c),
                })
    if not pairs:
        return pd.DataFrame([])
    df = pd.DataFrame(pairs).sort_values("abs_corr", ascending=False).head(max_pairs)
    return df


def _aggregate_signals(details: Dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(details.get("signals", []))
    if df.empty:
        return df
    # numeric coercion
    for c in ["n", "sse", "rmse", "w", "w_raw", "scale"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    g = df.groupby(["meas_table", "meas_col", "model_key"], as_index=False).agg(
        n_sum=("n", "sum"),
        sse_sum=("sse", "sum"),
        scale_med=("scale", "median"),
        w_raw_med=("w_raw", "median"),
        w_med=("w", "median"),
    )
    g["rmse"] = np.sqrt(g["sse_sum"] / np.maximum(1.0, g["n_sum"]))
    g["nrmse"] = g["rmse"] / np.maximum(1e-12, g["scale_med"])
    g = g.sort_values("sse_sum", ascending=False)
    return g


def _aggregate_tests(details: Dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(details.get("tests", []))
    if df.empty:
        return df
    for c in ["n", "sse", "rmse"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    g = df.groupby(["test", "group"], as_index=False).agg(
        n_sum=("n", "sum"),
        sse_sum=("sse", "sum"),
    )
    g["rmse"] = np.sqrt(g["sse_sum"] / np.maximum(1.0, g["n_sum"]))
    g = g.sort_values("sse_sum", ascending=False)
    return g


def _oed_summary(oed: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    suite = oed.get("suite_total", {}) if isinstance(oed, dict) else {}
    if suite:
        for k in ["rank", "n_params", "logdet", "cond", "trace", "min_eig"]:
            if k in suite:
                out[k] = suite[k]
    greedy = oed.get("greedy_D_opt", {}) if isinstance(oed, dict) else {}
    if greedy and "order" in greedy:
        out["D_opt_order"] = greedy.get("order", [])
        out["D_opt_logdet_cum"] = greedy.get("logdet_cum", [])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit_report", required=True)
    ap.add_argument("--fit_details", required=True)
    ap.add_argument("--fitted_json", required=True)
    ap.add_argument("--fit_ranges_json", required=True)
    ap.add_argument("--oed_report", default="")
    ap.add_argument("--out_md", default="")
    ap.add_argument("--out_json", default="")
    ap.add_argument("--corr_thr", type=float, default=0.95)
    ap.add_argument("--bound_tol_frac", type=float, default=0.01)
    ap.add_argument("--bad_nrmse", type=float, default=2.0)
    ap.add_argument("--top_k", type=int, default=12)
    args = ap.parse_args()

    fit_report = _load_json(Path(args.fit_report))
    fit_details = _load_json(Path(args.fit_details))
    fitted = _load_json(Path(args.fitted_json))
    ranges = _load_json(Path(args.fit_ranges_json))

    oed = _load_json(Path(args.oed_report)) if args.oed_report else None

    df_params = _param_table(fit_report, fitted, ranges, bound_tol_frac=float(args.bound_tol_frac))
    df_pairs = _corr_pairs(fit_report, corr_thr=float(args.corr_thr))
    df_sig = _aggregate_signals(fit_details)
    df_tst = _aggregate_tests(fit_details)

    # flags
    at_bounds = df_params[(df_params["at_lower"]) | (df_params["at_upper"])].copy()
    high_rel = df_params[np.isfinite(df_params["rel_std"]) & (df_params["rel_std"] >= 0.5)].copy().sort_values("rel_std", ascending=False)
    bad_signals = df_sig[np.isfinite(df_sig["nrmse"]) & (df_sig["nrmse"] >= float(args.bad_nrmse))].copy().sort_values("nrmse", ascending=False)

    # build markdown
    md: List[str] = []
    md.append("# Action plan / диагностика калибровки\n")
    md.append(f"- best_rmse: **{_fmt(fit_report.get('best_rmse', float('nan')))}**")
    md.append(f"- n_params: **{len(fit_report.get('keys', []))}**")
    md.append(f"- n_runs: **{len(fit_report.get('runs', []))}**")
    md.append("")

    if oed is not None:
        s = _oed_summary(oed)
        md.append("## OED/FIM summary")
        if s:
            md.append("```json")
            md.append(json.dumps(s, ensure_ascii=False, indent=2))
            md.append("```")
        else:
            md.append("_OED report found but no recognizable fields._")
        md.append("")

    md.append("## Параметры (value / bounds / std)")
    md.append("Топ-таблица параметров (все):")
    cols = ["param", "value", "min", "max", "at_lower", "at_upper", "std", "rel_std"]
    md.append("")
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, r in df_params.iterrows():
        md.append("| " + " | ".join([
            str(r["param"]),
            _fmt(r["value"]),
            _fmt(r["min"]),
            _fmt(r["max"]),
            "1" if r["at_lower"] else "0",
            "1" if r["at_upper"] else "0",
            _fmt(r["std"]),
            _fmt(r["rel_std"]),
        ]) + " |")
    md.append("")

    md.append("## Что вызывает тревогу")
    if not at_bounds.empty:
        md.append(f"### Параметры у границ (tol={args.bound_tol_frac*100:.1f}% диапазона)")
        for _, r in at_bounds.iterrows():
            side = "LOW" if r["at_lower"] else "HIGH"
            md.append(f"- `{r['param']}` = { _fmt(r['value']) } (near {side} bound [{_fmt(r['min'])}, {_fmt(r['max'])}])")
        md.append("")
    else:
        md.append("- ✅ Нет параметров, упёршихся в границы (по выбранному tol).")
        md.append("")

    if not df_pairs.empty:
        md.append(f"### Сильно коррелирующие параметры (|corr| >= {args.corr_thr})")
        for _, r in df_pairs.iterrows():
            md.append(f"- corr({r['p1']}, {r['p2']}) = { _fmt(r['corr'], 4) }")
        md.append("")
    else:
        md.append(f"- ✅ Нет пар с |corr| >= {args.corr_thr} (или corr не рассчитан).")
        md.append("")

    if not high_rel.empty:
        md.append("### Параметры с большой относительной неопределённостью (rel_std >= 0.5)")
        for _, r in high_rel.head(args.top_k).iterrows():
            md.append(f"- `{r['param']}`: value={_fmt(r['value'])}, std={_fmt(r['std'])}, rel_std={_fmt(r['rel_std'])}")
        md.append("")
    else:
        md.append("- ✅ Не найдено параметров с rel_std >= 0.5 (или cov не рассчитан).")
        md.append("")

    md.append("## Вклад тестов (top)")
    if not df_tst.empty:
        md.append("| test | group | n | sse | rmse |")
        md.append("|---|---:|---:|---:|---:|")
        for _, r in df_tst.head(args.top_k).iterrows():
            md.append(f"| {r['test']} | {r['group']} | {int(r['n_sum'])} | {_fmt(r['sse_sum'])} | {_fmt(r['rmse'])} |")
        md.append("")
    else:
        md.append("_Нет данных tests в fit_details._\n")

    md.append("## Вклад сигналов (top by SSE)")
    if not df_sig.empty:
        md.append("| meas_table | meas_col | model_key | n | sse | rmse | scale | nrmse |")
        md.append("|---|---|---|---:|---:|---:|---:|---:|")
        for _, r in df_sig.head(args.top_k).iterrows():
            md.append(f"| {r['meas_table']} | {r['meas_col']} | {r['model_key']} | {int(r['n_sum'])} | {_fmt(r['sse_sum'])} | {_fmt(r['rmse'])} | {_fmt(r['scale_med'])} | {_fmt(r['nrmse'])} |")
        md.append("")
    else:
        md.append("_Нет данных signals в fit_details._\n")

    if not bad_signals.empty:
        md.append(f"### Сигналы с NRMSE >= {args.bad_nrmse} (возможные проблемы: единицы, смещение, неверный mapping, дрейф)")
        for _, r in bad_signals.head(args.top_k).iterrows():
            md.append(f"- `{r['model_key']}` (meas={r['meas_table']}.{r['meas_col']}): NRMSE={_fmt(r['nrmse'])}, RMSE={_fmt(r['rmse'])}, scale={_fmt(r['scale_med'])}")
        md.append("")

    md.append("## Рекомендации (авто)")
    md.append("1) Если параметры у границ: сначала проверь физический смысл и единицы; затем либо расширь bounds, либо зафиксируй параметр.")
    md.append("2) Если есть сильные корреляции: не фитить эти параметры одновременно; добавь тесты/наблюдения (см. OED D-opt order) или зафиксируй один из пары.")
    md.append("3) Если NRMSE сигналов огромный: проверь единицы (Па vs бар), знаки, time alignment, наличие bias датчика.")
    md.append("4) Для строгих интервалов: запусти profile likelihood по параметрам из разделов 'границы/корреляции/rel_std'.")
    md.append("")

    out_md = Path(args.out_md) if args.out_md else Path(args.fit_report).with_name("action_plan.md")
    _save_text("\n".join(md), out_md)

    if args.out_json:
        out = {
            "best_rmse": fit_report.get("best_rmse"),
            "params": df_params.to_dict(orient="records"),
            "at_bounds": at_bounds.to_dict(orient="records"),
            "high_corr_pairs": df_pairs.to_dict(orient="records"),
            "high_rel_std": high_rel.head(args.top_k).to_dict(orient="records"),
            "top_tests": df_tst.head(args.top_k).to_dict(orient="records"),
            "top_signals": df_sig.head(args.top_k).to_dict(orient="records"),
            "bad_signals": bad_signals.head(args.top_k).to_dict(orient="records"),
        }
        if oed is not None:
            out["oed_summary"] = _oed_summary(oed)
        _save_json(out, Path(args.out_json))

    print("Wrote:", out_md)


if __name__ == "__main__":
    main()
