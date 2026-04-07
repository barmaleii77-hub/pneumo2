# -*- coding: utf-8 -*-
"""tradeoff_bootstrap_stability_v1.py

Bootstrap-оценка устойчивости multiobjective метрик (objA/objB) по *тестам*.

Зачем:
- Pareto/epsilon sweep дают набор компромиссных точек.
- На практике хочется выбирать не "красивую" точку по средним метрикам,
  а устойчивую (не разваливается, если часть тестов заменить/убрать).

Ключевая идея: мы НЕ повторяем симуляцию.
Мы используем fit_details.json (unbiased SSE по тестам/сигналам) и делаем bootstrap
по тестам: пересэмплируем набор тестов с возвращением и пересчитываем RMSE по группам.

Вход:
- points_csv: pareto_points.csv или epsilon_points.csv
- points_base_dir: директория, относительно которой резолвятся run_dir (если run_dir не абсолютный)
- groupA/groupB: имена sig_group для целей A и B

Выход:
- CSV со сводкой по каждой точке: mean/std/p50/p90/p95 для A/B (train и holdout)
  + вероятность выполнимости constraint (если в points есть epsilon).

"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from bootstrap_utils_v1 import (
    GroupByTestArrays,
    build_group_by_test_arrays,
    bootstrap_two_group_rmse,
    feasibility_prob,
    load_details_signals_df,
    summarize_bootstrap,
)


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(path)


def _resolve_details_path(point: Dict[str, Any], points_base_dir: Path) -> Optional[Path]:
    """Найти fit_details.json для точки.

    Поддерживаем разные форматы:
    - pareto_points.csv: run_dir обычно указывает на папку lam_XX
    - epsilon_points.csv: run_dir может быть 'sweep/eps_00' (relative)
      или 'primary_only'/'constraint_only' (endpoint -> лежит в endpoints/)
    """
    run_dir_s = str(point.get("run_dir", "")).strip()
    kind = str(point.get("kind", "")).strip().lower()

    # 1) если есть base_json — часто это fitted_base.json; тогда details лежит рядом
    base_json_s = str(point.get("base_json", "")).strip()
    if base_json_s:
        bj = Path(base_json_s)
        if bj.exists():
            cand = bj.parent / "fit_details.json"
            if cand.exists():
                return cand

    # 2) run_dir
    if run_dir_s:
        rd = Path(run_dir_s)
        if rd.is_absolute() and rd.exists():
            cand = rd / "fit_details.json"
            if cand.exists():
                return cand
        # relative
        rd2 = points_base_dir / rd
        if rd2.exists():
            cand = rd2 / "fit_details.json"
            if cand.exists():
                return cand

        # epsilon endpoints special case
        if "endpoint" in kind and run_dir_s:
            rd3 = points_base_dir / "endpoints" / run_dir_s
            cand = rd3 / "fit_details.json"
            if cand.exists():
                return cand

    return None


def _bootstrap_for_point(details_json: Path,
                         groupA: str,
                         groupB: str,
                         reps: int,
                         seed: int,
                         which: str) -> Dict[str, float]:
    df = load_details_signals_df(details_json)
    arrays: GroupByTestArrays = build_group_by_test_arrays(df, groupA=groupA, groupB=groupB, which=which)
    rmseA, rmseB = bootstrap_two_group_rmse(arrays, reps=int(reps), seed=int(seed))
    sa = summarize_bootstrap(rmseA)
    sb = summarize_bootstrap(rmseB)
    out: Dict[str, float] = {}
    for k, v in sa.items():
        out[f"A_{k}"] = float(v)
    for k, v in sb.items():
        out[f"B_{k}"] = float(v)
    out["n_tests"] = float(len(arrays.tests))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points_csv", required=True)
    ap.add_argument("--points_base_dir", default="")
    ap.add_argument("--groupA", required=True)
    ap.add_argument("--groupB", required=True)
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epsilon_tol", type=float, default=0.02)
    ap.add_argument("--out_csv", required=True)
    args = ap.parse_args()

    points_csv = Path(args.points_csv)
    if not points_csv.exists():
        raise SystemExit(f"points_csv not found: {points_csv}")

    base_dir = Path(args.points_base_dir) if str(args.points_base_dir).strip() else points_csv.parent

    df_points = _read_csv(points_csv)
    if df_points.empty:
        raise SystemExit(f"points_csv is empty: {points_csv}")

    rows = []

    for _, r in df_points.iterrows():
        p = r.to_dict()
        details = _resolve_details_path(p, base_dir)
        row = dict(p)
        row["details_json"] = str(details) if details is not None else ""

        if details is None or not details.exists():
            # keep row, mark missing
            row["bootstrap_status"] = "missing_details"
            rows.append(row)
            continue

        # run both train and holdout
        try:
            tr = _bootstrap_for_point(details, args.groupA, args.groupB, reps=int(args.reps), seed=int(args.seed), which="train")
            ho = _bootstrap_for_point(details, args.groupA, args.groupB, reps=int(args.reps), seed=int(args.seed) + 1, which="holdout")

            for k, v in tr.items():
                row[f"train_{k}"] = float(v)
            for k, v in ho.items():
                row[f"holdout_{k}"] = float(v)

            # feasibility probability if epsilon exists
            eps = p.get("epsilon", np.nan)
            if isinstance(eps, str):
                try:
                    eps = float(eps)
                except Exception:
                    eps = float("nan")
            if math.isfinite(float(eps)):
                # need bootstrap arrays for B to compute feasibility
                df_det = load_details_signals_df(details)
                arr_tr = build_group_by_test_arrays(df_det, groupA=args.groupA, groupB=args.groupB, which="train")
                rmseA_tr, rmseB_tr = bootstrap_two_group_rmse(arr_tr, reps=int(args.reps), seed=int(args.seed))
                row["p_feasible_train"] = float(feasibility_prob(rmseB_tr, eps=float(eps), tol=float(args.epsilon_tol)))

                arr_ho = build_group_by_test_arrays(df_det, groupA=args.groupA, groupB=args.groupB, which="holdout")
                rmseA_ho, rmseB_ho = bootstrap_two_group_rmse(arr_ho, reps=int(args.reps), seed=int(args.seed) + 1)
                row["p_feasible_holdout"] = float(feasibility_prob(rmseB_ho, eps=float(eps), tol=float(args.epsilon_tol)))
            else:
                row["p_feasible_train"] = float("nan")
                row["p_feasible_holdout"] = float("nan")

            row["bootstrap_status"] = "ok"

        except Exception as e:
            row["bootstrap_status"] = f"error: {e}"

        rows.append(row)

    out_df = pd.DataFrame(rows)
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
