# -*- coding: utf-8 -*-
"""signals_refine_v1.py

Автоматическая очистка/рефайн списка сигналов на основе результатов fit.

Задача:
  После прогона fit_worker_v3_suite_identify.py + report_from_details_v1.py
  у нас есть `signals.csv`, где каждая строка — (test, meas_table, meas_col, model_key)
  и метрики качества (sse/rmse/n) + служебные поля (scale, w_raw, w).

  Для полностью автоматического пайплайна нужно уметь:
    - агрегировать сигналы по всем тестам;
    - детектировать явно «битые» сигналы (константа, нет масштаба, огромный NRMSE);
    - (опционально) мягко понижать вес сигналов, которые пока плохо совпадают,
      чтобы они не ломали следующий проход оптимизации;
    - сформировать `signals_refined.csv`, который можно напрямую использовать
      как вход в signals_csv_to_mapping_v1.py (через enabled/w_raw).

Это НЕ заменяет OED/FIM и profile-likelihood, но делает 1–2 итерации
автокалибровки заметно устойчивее.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _to_float(x: Any, default: float = np.nan) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = set(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals_csv", required=True, help="signals.csv из report_from_details_v1.py")
    ap.add_argument("--out_signals_csv", required=True, help="куда писать signals_refined.csv")

    ap.add_argument("--min_total_points", type=int, default=20, help="минимум суммарных точек n по всем тестам")
    ap.add_argument("--eps_scale", type=float, default=1e-12, help="порог для scale, чтобы считать сигнал константным")
    ap.add_argument("--downweight_nrmse", type=float, default=10.0, help="при NRMSE выше этого — понижать вес")
    ap.add_argument("--disable_nrmse", type=float, default=25.0, help="при NRMSE выше этого — отключать сигнал")
    ap.add_argument("--min_keep", type=int, default=6, help="гарантированно оставить хотя бы столько сигналов")
    ap.add_argument("--keep_top_sse", type=int, default=0, help="если >0 — гарантированно оставить топ-N по SSE")
    ap.add_argument("--w_min", type=float, default=1e-12)
    ap.add_argument("--w_max", type=float, default=1e12)
    args = ap.parse_args()

    in_path = Path(args.signals_csv)
    df = pd.read_csv(in_path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]

    # required cols
    c_table = _pick_col(df, ["meas_table", "table", "meas_tbl"])
    c_col = _pick_col(df, ["meas_col", "col", "meas_column"])
    c_key = _pick_col(df, ["model_key", "key", "sim_key"])
    if c_table is None or c_col is None or c_key is None:
        raise SystemExit(f"signals.csv не содержит meas_table/meas_col/model_key. Есть: {list(df.columns)}")

    c_n = _pick_col(df, ["n", "N", "count"])
    c_sse = _pick_col(df, ["sse", "SSE"])
    c_rmse = _pick_col(df, ["rmse", "RMSE"])
    c_scale = _pick_col(df, ["scale", "auto_scale", "meas_scale"])
    c_w_raw = _pick_col(df, ["w_raw", "weight", "w0"])
    c_w = _pick_col(df, ["w", "weight_eff"])

    # numeric coercion
    for c in [c_n, c_sse, c_rmse, c_scale, c_w_raw, c_w]:
        if c is None:
            continue
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # ensure base weight exists
    if c_w_raw is None:
        df["w_raw"] = 1.0
        c_w_raw = "w_raw"

    # aggregate by signal
    g = df.groupby([c_table, c_col, c_key], as_index=False).agg(
        n_sum=(c_n, "sum") if c_n else (c_w_raw, "size"),
        sse_sum=(c_sse, "sum") if c_sse else (c_w_raw, "sum"),
        # robust: scale median across tests
        scale_med=(c_scale, "median") if c_scale else (c_w_raw, "median"),
        w_raw_med=(c_w_raw, "median"),
        w_med=(c_w, "median") if c_w else (c_w_raw, "median"),
    )

    # compute rmse/nrmse
    n_sum = np.asarray(g["n_sum"], dtype=float)
    sse_sum = np.asarray(g["sse_sum"], dtype=float)
    rmse = np.sqrt(np.clip(sse_sum, 0.0, np.inf) / np.clip(n_sum, 1.0, np.inf))
    scale = np.asarray(g["scale_med"], dtype=float)
    scale_safe = np.where(np.isfinite(scale) & (np.abs(scale) > float(args.eps_scale)), np.abs(scale), np.nan)
    nrmse = rmse / (scale_safe + 1e-30)
    g["rmse"] = rmse
    g["nrmse"] = nrmse

    # decide enabled + weight
    enabled = np.ones(len(g), dtype=int)
    reason = np.array(["ok"] * len(g), dtype=object)
    w_new = np.asarray(g["w_raw_med"], dtype=float)
    w_new = np.where(np.isfinite(w_new), w_new, 1.0)

    # rules
    # 1) too few points
    mask_few = n_sum < float(args.min_total_points)
    enabled[mask_few] = 0
    reason[mask_few] = "too_few_points"

    # 2) scale invalid/zero => likely constant / auto_scale failed
    mask_scale_bad = ~np.isfinite(scale_safe)
    enabled[mask_scale_bad] = 0
    reason[mask_scale_bad] = "scale_bad"

    # 3) nrmse rules
    mask_disable = np.isfinite(nrmse) & (nrmse >= float(args.disable_nrmse))
    enabled[mask_disable] = 0
    reason[mask_disable] = "nrmse_disable"

    mask_down = np.isfinite(nrmse) & (nrmse >= float(args.downweight_nrmse)) & (enabled == 1)
    # downweight factor <= 1
    factor = float(args.downweight_nrmse) / np.maximum(nrmse, float(args.downweight_nrmse))
    w_new = np.where(mask_down, w_new * factor, w_new)
    reason[mask_down] = "nrmse_downweight"

    # clip weights
    w_new = np.clip(w_new, float(args.w_min), float(args.w_max))

    # keep_top_sse / min_keep safety:
    # even if rules disabled many, we keep at least min_keep (and/or keep_top_sse)
    if int(args.keep_top_sse) > 0:
        order_sse = np.argsort(-sse_sum)
        must_keep = set(order_sse[: int(args.keep_top_sse)].tolist())
    else:
        must_keep = set()

    if int(args.min_keep) > 0:
        # keep top by SSE among currently enabled+disabled
        order_sse = np.argsort(-sse_sum)
        must_keep.update(order_sse[: int(args.min_keep)].tolist())

    if must_keep:
        for idx in must_keep:
            enabled[idx] = 1
            if reason[idx] != "ok":
                reason[idx] = "forced_keep"

    # output dataframe
    out = pd.DataFrame({
        "meas_table": g[c_table].astype(str),
        "meas_col": g[c_col].astype(str),
        "model_key": g[c_key].astype(str),
        "w_raw": w_new,
        "enabled": enabled,
        "reason": reason,
        "n": n_sum,
        "sse": sse_sum,
        "rmse": rmse,
        "scale": scale,
        "nrmse": nrmse,
    })
    out = out.sort_values(["enabled", "sse"], ascending=[False, False])

    out_path = Path(args.out_signals_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Wrote refined signals: {out_path} (enabled={int(out['enabled'].sum())}/{len(out)})")


if __name__ == "__main__":
    main()
