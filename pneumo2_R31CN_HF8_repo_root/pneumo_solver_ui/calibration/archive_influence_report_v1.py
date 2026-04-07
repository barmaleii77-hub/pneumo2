#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""archive_influence_report_v1

Цель:
  Построить data-driven оценку важности параметров (pneumo+geometry params) по глобальному архиву оптимизаций.

Вход:
  --archive_jsonl  global_history.jsonl (jsonl, одна запись = одна строка CSV + meta)
  --ranges_json    fit_ranges.json (границы параметров)

Выход:
  --out_json       archive_influence.json
  --out_csv        archive_influence_params.csv

Метод:
  - Извлекаем (X,y) из архива:
      X: параметры нормализованы в [0,1] по fit_ranges
      y: скаляризация целей (penalty доминирует)
  - Обучаем ExtraTreesRegressor
  - Берём feature_importances_ (MDI) как быстрый индикатор влияния.

Примечание:
  Это не строгая глобальная чувствительность; цель — практическое ранжирование параметров
  для активного набора (active-set) и coarse→fine оптимизации.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from pneumo_solver_ui.optimization_objective_contract import (
    normalize_objective_keys,
    normalize_penalty_key,
    scalarize_score_tuple,
    score_tuple_from_row,
)

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore

try:
    from sklearn.ensemble import ExtraTreesRegressor
except Exception:  # pragma: no cover
    ExtraTreesRegressor = None  # type: ignore


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_csv(rows: List[Dict[str, Any]], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if pd is None:
        # fallback: very small CSV writer
        if not rows:
            p.write_text("", encoding="utf-8")
            return
        cols = list(rows[0].keys())
        lines = [",".join(cols)]
        for r in rows:
            lines.append(",".join(str(r.get(c, "")) for c in cols))
        p.write_text("\n".join(lines), encoding="utf-8")
        return
    df = pd.DataFrame(rows)
    df.to_csv(p, index=False)


def _score_row(
    row: Dict[str, Any],
    *,
    objective_keys: Sequence[str] | None = None,
    penalty_key: str | None = None,
) -> Tuple[float, ...]:
    return tuple(score_tuple_from_row(row, objective_keys=objective_keys, penalty_key=penalty_key))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive_jsonl", required=True)
    ap.add_argument("--ranges_json", required=True)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--out_csv", default="")
    ap.add_argument("--objective", action="append", default=[], help="Objective key(s) used for archive ranking / scalarization.")
    ap.add_argument("--penalty-key", default="штраф_физичности_сумма")
    ap.add_argument("--model_sha_prefix", default="")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max_train", type=int, default=20000)
    ap.add_argument("--min_cov", type=float, default=0.25)

    args = ap.parse_args()

    objective_keys = tuple(normalize_objective_keys(args.objective))
    penalty_key = normalize_penalty_key(args.penalty_key)

    if ExtraTreesRegressor is None:
        raise SystemExit("scikit-learn is required for archive_influence_report_v1")

    archive_p = Path(args.archive_jsonl)
    ranges_p = Path(args.ranges_json)
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv) if str(args.out_csv).strip() else None

    ranges = _load_json(ranges_p)
    if not isinstance(ranges, dict) or not ranges:
        raise SystemExit("ranges_json must be a non-empty dict")

    names = list(ranges.keys())
    d = int(len(names))
    if d <= 0:
        raise SystemExit("no parameters in ranges")

    def _bounds(p: str) -> Tuple[float, float]:
        lo, hi = ranges.get(p, (0.0, 1.0))
        return float(lo), float(hi)

    rng = np.random.default_rng(int(args.seed))

    max_train = int(max(100, args.max_train))
    min_cov = float(max(0.0, min(1.0, args.min_cov)))
    model_sha_prefix = str(args.model_sha_prefix).strip()

    data: List[Tuple[List[float], float]] = []
    seen = 0

    # Reservoir sampling for stable training size
    with archive_p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            if model_sha_prefix:
                try:
                    msha = str(rec.get("model_sha1", ""))
                    if not msha.startswith(model_sha_prefix):
                        continue
                except Exception:
                    pass

            s = _score_row(rec, objective_keys=objective_keys, penalty_key=penalty_key)
            if not (np.isfinite(s[0]) and np.isfinite(s[1]) and np.isfinite(s[2])):
                continue

            present = 0
            ok = True
            x: List[float] = []
            for p in names:
                lo, hi = _bounds(p)
                if hi <= lo:
                    ok = False
                    break
                key = f"параметр__{p}"
                if key in rec:
                    try:
                        v = float(rec.get(key))
                        xn = (v - lo) / (hi - lo)
                        x.append(float(np.clip(xn, 0.0, 1.0)))
                        present += 1
                        continue
                    except Exception:
                        pass
                x.append(0.5)

            if not ok:
                continue

            coverage = float(present) / float(d) if d > 0 else 0.0
            if coverage < float(min_cov):
                continue

            y = scalarize_score_tuple(s)

            if len(data) < int(max_train):
                data.append((x, float(y)))
            else:
                j = int(rng.integers(0, seen + 1))
                if j < int(max_train):
                    data[j] = (x, float(y))
            seen += 1

    if len(data) < max(50, 5 * len(names)):
        # fallback: ignore model filter
        if model_sha_prefix:
            model_sha_prefix = ""
            data = []
            seen = 0
            with archive_p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    s = _score_row(rec, objective_keys=objective_keys, penalty_key=penalty_key)
                    if not (np.isfinite(s[0]) and np.isfinite(s[1]) and np.isfinite(s[2])):
                        continue
                    present = 0
                    ok = True
                    x: List[float] = []
                    for p in names:
                        lo, hi = _bounds(p)
                        if hi <= lo:
                            ok = False
                            break
                        key = f"параметр__{p}"
                        if key in rec:
                            try:
                                v = float(rec.get(key))
                                xn = (v - lo) / (hi - lo)
                                x.append(float(np.clip(xn, 0.0, 1.0)))
                                present += 1
                                continue
                            except Exception:
                                pass
                        x.append(0.5)
                    if not ok:
                        continue
                    coverage = float(present) / float(d) if d > 0 else 0.0
                    if coverage < float(min_cov):
                        continue
                    y = scalarize_score_tuple(s)
                    if len(data) < int(max_train):
                        data.append((x, float(y)))
                    else:
                        j = int(rng.integers(0, seen + 1))
                        if j < int(max_train):
                            data[j] = (x, float(y))
                    seen += 1

    if len(data) < max(20, 3 * len(names)):
        # not enough data
        out = {
            "version": "archive_influence_report_v1",
            "penalty_key": str(penalty_key),
            "objective_keys": list(objective_keys),
            "ts": time.time(),
            "archive": str(archive_p),
            "ranges": str(ranges_p),
            "model_sha_prefix": str(args.model_sha_prefix),
            "train_n": int(len(data)),
            "max_train": int(max_train),
            "min_cov": float(min_cov),
            "status": "not_enough_data",
            "importance": {},
        }
        _save_json(out, out_json)
        if out_csv is not None:
            _save_csv([], out_csv)
        return 0

    X = np.array([r[0] for r in data], dtype=float)
    y = np.array([r[1] for r in data], dtype=float)

    reg = ExtraTreesRegressor(
        n_estimators=300,
        random_state=int(args.seed),
        n_jobs=-1,
        min_samples_leaf=2,
    )
    reg.fit(X, y)

    imp = reg.feature_importances_
    importance = {names[i]: float(imp[i]) for i in range(len(names))}

    # Sort
    ranked = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)

    out = {
        "version": "archive_influence_report_v1",
        "penalty_key": str(penalty_key),
        "objective_keys": list(objective_keys),
        "ts": time.time(),
        "archive": str(archive_p),
        "ranges": str(ranges_p),
        "model_sha_prefix": str(args.model_sha_prefix),
        "train_n": int(X.shape[0]),
        "max_train": int(max_train),
        "min_cov": float(min_cov),
        "status": "ok",
        "importance": {k: float(v) for k, v in ranked},
        "top": [{"param": k, "importance": float(v)} for k, v in ranked[:50]],
    }

    _save_json(out, out_json)

    if out_csv is not None:
        rows = [{"param": k, "importance": float(v)} for k, v in ranked]
        _save_csv(rows, out_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
