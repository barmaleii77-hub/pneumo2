# -*- coding: utf-8 -*-
"""param_staging_v2_fim_corr.py

FIM-driven parameter staging (поэтапное раскрытие параметров) с учётом:
- чувствительности (sens_rms из OED/FIM отчёта),
- корреляций (corr из suite_total),
- ограничений на размер стадий.

Инженерная логика:
- На ранних стадиях оптимизируем параметры, которые хорошо "видны" данным и не слишком
  коррелируют между собой, чтобы локальная оптимизация (NLLS/TRF) не топталась
  в вырожденных направлениях.
- На поздних стадиях добавляем плохо наблюдаемые и/или сильно коррелирующие параметры,
  используя warm-start из предыдущих стадий (continuation / staged optimization).

Вход:
- fit_ranges_json: {param:[lo,hi], ...}
- oed_report_json: отчёт oed_worker_v1_fim.py (tests[*].sens_rms + suite_total.corr)
- (опционально) signals_csv: пока не обязателен, но можно использовать для будущих эвристик.

Выход:
- out_dir/stages.json: список стадий и метрики
- out_dir/stage_ranges/stageK_ranges.json: "union ranges" для stage0..K

Запуск:
python calibration/param_staging_v2_fim_corr.py \
  --fit_ranges_json default_ranges.json \
  --oed_report_json calibration_runs/RUN_.../oed_report.json \
  --out_dir calibration_runs/RUN_.../param_staging_fim \
  --corr_thr 0.85 --max_stage_size 6 --min_stage_size 2

"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _mean_sens_from_oed(keys: List[str], oed: Dict[str, Any]) -> Dict[str, float]:
    tests = oed.get("tests", {}) if isinstance(oed, dict) else {}
    acc: Dict[str, List[float]] = {k: [] for k in keys}

    for _tname, tinfo in tests.items():
        if not isinstance(tinfo, dict):
            continue
        sens = tinfo.get("sens_rms", {})
        if not isinstance(sens, dict):
            continue
        for k in keys:
            v = sens.get(k, None)
            if v is None:
                continue
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isfinite(fv) and fv > 0:
                acc[k].append(fv)

    out: Dict[str, float] = {}
    for k, arr in acc.items():
        out[k] = float(np.mean(arr)) if arr else 0.0
    return out


def _corr_matrix_abs(keys: List[str], oed: Dict[str, Any]) -> np.ndarray:
    """|corr| aligned to keys order; fallback zeros if missing."""
    params = oed.get("params", {}) if isinstance(oed, dict) else {}
    rep_keys = params.get("keys", None)
    suite_total = oed.get("suite_total", {}) if isinstance(oed, dict) else {}
    corr = suite_total.get("corr", None) if isinstance(suite_total, dict) else None

    if rep_keys is None or corr is None:
        return np.zeros((len(keys), len(keys)), dtype=float)

    rep_keys = [str(k) for k in rep_keys]
    corr = np.asarray(corr, dtype=float)
    if corr.ndim != 2 or corr.shape[0] != corr.shape[1]:
        return np.zeros((len(keys), len(keys)), dtype=float)

    idx = {k: i for i, k in enumerate(rep_keys)}
    C = np.zeros((len(keys), len(keys)), dtype=float)
    for i, ki in enumerate(keys):
        ii = idx.get(ki)
        if ii is None:
            continue
        for j, kj in enumerate(keys):
            jj = idx.get(kj)
            if jj is None:
                continue
            C[i, j] = float(abs(corr[ii, jj]))
    return np.clip(C, 0.0, 1.0)


def _greedy_stages(
    keys: List[str],
    score: Dict[str, float],
    corr_abs: np.ndarray,
    corr_thr: float,
    max_stage_size: int,
    min_stage_size: int,
) -> List[Dict[str, Any]]:
    """Greedy packing: seed by score, then add high-score params with low corr to current stage."""
    unassigned = set(keys)
    order = sorted(keys, key=lambda k: float(score.get(k, 0.0)), reverse=True)

    idx = {k: i for i, k in enumerate(keys)}

    stages: List[Dict[str, Any]] = []
    while unassigned:
        # pick best remaining
        seed = None
        for k in order:
            if k in unassigned:
                seed = k
                break
        if seed is None:
            seed = next(iter(unassigned))

        stage_keys = [seed]
        unassigned.remove(seed)

        for k in order:
            if k not in unassigned:
                continue
            if len(stage_keys) >= max_stage_size:
                break
            ik = idx[k]
            ok = True
            for s in stage_keys:
                is_ = idx[s]
                if corr_abs[ik, is_] > corr_thr:
                    ok = False
                    break
            if ok:
                stage_keys.append(k)
                unassigned.remove(k)

        stages.append({"keys": stage_keys})

    # merge small tail
    if min_stage_size > 1 and len(stages) >= 2:
        i = 0
        while i < len(stages):
            if len(stages[i]["keys"]) >= min_stage_size:
                i += 1
                continue
            if i > 0:
                stages[i-1]["keys"].extend(stages[i]["keys"])
                stages.pop(i)
            elif len(stages) > 1:
                stages[i+1]["keys"] = stages[i]["keys"] + stages[i+1]["keys"]
                stages.pop(i)
            else:
                i += 1

    for i, st in enumerate(stages):
        st["idx"] = int(i)
        st["name"] = f"fim_stage_{i}"
    return stages


def _write_union_ranges(stages: List[Dict[str, Any]], fit_ranges: Dict[str, Any], out_dir: Path) -> List[str]:
    union: Dict[str, Any] = {}
    files: List[str] = []
    (out_dir / "stage_ranges").mkdir(parents=True, exist_ok=True)
    for i, st in enumerate(stages):
        for k in st.get("keys", []):
            if k in fit_ranges:
                union[k] = fit_ranges[k]
        p = out_dir / "stage_ranges" / f"stage{i}_ranges.json"
        _save_json(dict(union), p)
        files.append(str(p))
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit_ranges_json", required=True)
    ap.add_argument("--oed_report_json", required=True)
    ap.add_argument("--signals_csv", default="")
    ap.add_argument("--out_dir", required=True)

    ap.add_argument("--corr_thr", type=float, default=0.85)
    ap.add_argument("--max_stage_size", type=int, default=6)
    ap.add_argument("--min_stage_size", type=int, default=2)
    ap.add_argument("--score_power", type=float, default=1.0)
    args = ap.parse_args()

    fit_ranges = _load_json(Path(args.fit_ranges_json))
    if not isinstance(fit_ranges, dict) or not fit_ranges:
        raise RuntimeError("fit_ranges_json must be a non-empty dict {param:[lo,hi]}")

    keys = list(fit_ranges.keys())
    oed = _load_json(Path(args.oed_report_json))
    sens = _mean_sens_from_oed(keys, oed)
    corr_abs = _corr_matrix_abs(keys, oed)

    pwr = float(args.score_power)
    score = {k: float(sens.get(k, 0.0) ** pwr) if sens.get(k, 0.0) > 0 else 0.0 for k in keys}

    stages = _greedy_stages(
        keys=keys,
        score=score,
        corr_abs=corr_abs,
        corr_thr=float(args.corr_thr),
        max_stage_size=int(args.max_stage_size),
        min_stage_size=int(args.min_stage_size),
    )

    # diagnostics
    idx = {k: i for i, k in enumerate(keys)}
    for st in stages:
        st_keys = st.get("keys", [])
        st["score_sum"] = float(sum(score.get(k, 0.0) for k in st_keys))
        if len(st_keys) >= 2:
            ii = [idx[k] for k in st_keys]
            sub = corr_abs[np.ix_(ii, ii)]
            sub = sub - np.eye(len(ii), dtype=float)  # ignore diag (becomes 0)
            st["max_corr_in_stage"] = float(np.max(sub))
        else:
            st["max_corr_in_stage"] = 0.0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = _write_union_ranges(stages, fit_ranges, out_dir)

    report = {
        "method": "fim_corr_greedy",
        "fit_ranges_json": str(Path(args.fit_ranges_json)),
        "oed_report_json": str(Path(args.oed_report_json)),
        "settings": {
            "corr_thr": float(args.corr_thr),
            "max_stage_size": int(args.max_stage_size),
            "min_stage_size": int(args.min_stage_size),
            "score_power": float(args.score_power),
        },
        "scores": {k: float(score.get(k, 0.0)) for k in keys},
        "stages": stages,
        "union_ranges_files": files,
    }
    _save_json(report, out_dir / "stages.json")
    print("DONE:", out_dir)


if __name__ == "__main__":
    main()
