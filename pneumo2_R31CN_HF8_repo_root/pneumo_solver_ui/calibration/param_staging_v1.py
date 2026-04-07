# -*- coding: utf-8 -*-
"""param_staging_v1.py

Автоматический план поэтапной идентификации параметров (staged calibration).

Зачем:
- Многопараметрические динамические модели часто плохо "берутся" при одновременной
  оптимизации всех параметров: вырожденность, сильные корреляции, локальные минимумы.
- Практика: сначала подгонять наиболее "структурные" параметры (геометрия/объёмы),
  затем гидропневматику (дроссели), затем пороги логики, затем механику/прочее.
- Для данного проекта это особенно полезно, т.к. часть параметров влияет на давления
  почти монотонно (объёмы/сечения), а часть включается через дискретную логику
  (пороги Pmin/Pmid/Pmax), что создаёт рваный ландшафт стоимости.

Вход:
- fit_ranges_json: {param: [lo, hi], ...}
- (опционально) signals_csv: чтобы понять, какие группы сигналов доминируют
  (pressure vs kinematics) и не откладывать механику "в самый конец".
- (опционально) oed_report_json: если есть отчёт OED/FIM, можно построить стадии
  по чувствительности (sens_rms) вместо эвристики по имени.

Выход (out_dir):
- stages.json: описание стадий
- stage_ranges/stage0_ranges.json, stage1_ranges.json, ...
  (это "union" диапазоны: stage_k включает параметры стадий 0..k)

Запуск:
python calibration/param_staging_v1.py \
  --fit_ranges_json default_ranges.json \
  --signals_csv calibration_runs/RUN_.../FINAL_SIGNALS.csv \
  --out_dir calibration_runs/RUN_.../param_staging

"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_signals_groups(signals_csv: Path) -> Tuple[Dict[str, float], int]:
    """Вернуть (sum_weight_by_group, n_enabled)."""
    try:
        import pandas as pd
    except Exception:
        return {}, 0

    if not signals_csv.exists():
        return {}, 0

    df = pd.read_csv(signals_csv, encoding="utf-8-sig")
    if df.empty:
        return {}, 0

    if "enabled" in df.columns:
        try:
            df = df[df["enabled"].astype(int) == 1].copy()
        except Exception:
            pass

    if df.empty:
        return {}, 0

    # weight column
    w_col = None
    for c in ("w_raw", "weight", "w", "w_raw_med"):
        if c in df.columns:
            w_col = c
            break
    if w_col is None:
        w_col = "w_raw"
        df[w_col] = 1.0

    if "sig_group" not in df.columns:
        # нет групп — это нормально
        return {}, int(len(df))

    df["sig_group"] = df["sig_group"].astype(str).str.strip().replace({"": "default"}).fillna("default")
    df[w_col] = pd.to_numeric(df[w_col], errors="coerce").fillna(0.0)

    sums = df.groupby("sig_group")[w_col].sum().to_dict()
    sums = {str(k): float(v) for k, v in sums.items()}
    return sums, int(len(df))


# ---------------------------
# Heuristic categorization
# ---------------------------

_PAT_VOLUME = re.compile(r"(объ[её]м|volume|ресивер|ресивер_|accum|аккум|line_?volume|объём_линии)", re.I)
_PAT_THROTTLE = re.compile(r"(дроссел|throttle|orifice|открытие_дросселя|клапан_сечение|cd_)", re.I)
_PAT_PRESSURE = re.compile(r"(давлен|pressure|pmin|pmid|pmax|p_заряд|заряд_аккумулятора)", re.I)
_PAT_MECH = re.compile(r"(пружин|spring|жестк|stiff|демпф|damp)", re.I)


def _categorize_param(name: str) -> str:
    s = str(name)
    if _PAT_VOLUME.search(s):
        return "volumes"
    if _PAT_THROTTLE.search(s):
        return "throttles"
    if _PAT_PRESSURE.search(s):
        return "pressure_thresholds"
    if _PAT_MECH.search(s):
        return "mechanics"
    return "other"


def _merge_small_stages(stages: List[Dict[str, Any]], min_stage_size: int) -> List[Dict[str, Any]]:
    if min_stage_size <= 1:
        return stages

    out: List[Dict[str, Any]] = []
    buf: List[str] = []
    buf_name_parts: List[str] = []

    def flush():
        nonlocal buf, buf_name_parts
        if not buf:
            return
        out.append({"name": "+".join(buf_name_parts) if buf_name_parts else "stage", "keys": list(buf)})
        buf = []
        buf_name_parts = []

    for st in stages:
        keys = list(st.get("keys", []))
        nm = str(st.get("name", "stage"))
        if not keys:
            continue
        if len(keys) >= min_stage_size:
            flush()
            out.append({"name": nm, "keys": keys})
        else:
            buf.extend(keys)
            buf_name_parts.append(nm)
            if len(buf) >= min_stage_size:
                flush()

    flush()

    # если остался хвост маленький — приклеить к предыдущему
    if len(out) >= 2 and len(out[-1]["keys"]) < min_stage_size:
        tail = out.pop(-1)
        out[-1]["keys"].extend(tail["keys"])
        out[-1]["name"] = out[-1]["name"] + "+" + tail.get("name", "tail")

    return out


def _build_stages_heuristic(keys: List[str], signals_groups: Dict[str, float], min_stage_size: int) -> List[Dict[str, Any]]:
    by_cat: Dict[str, List[str]] = {"volumes": [], "throttles": [], "pressure_thresholds": [], "mechanics": [], "other": []}
    for k in keys:
        by_cat[_categorize_param(k)].append(k)

    # определяем доминирующую группу сигналов
    kin_share = 0.0
    if signals_groups:
        total = sum(max(0.0, float(v)) for v in signals_groups.values())
        if total > 0:
            kin = float(signals_groups.get("kinematics", 0.0))
            kin_share = kin / total

    # порядок стадий: если кинематика значима, механику не откладываем
    if kin_share >= 0.35:
        order = ["volumes", "mechanics", "throttles", "pressure_thresholds", "other"]
    else:
        order = ["volumes", "throttles", "pressure_thresholds", "mechanics", "other"]

    stages: List[Dict[str, Any]] = []
    for cat in order:
        ks = by_cat.get(cat, [])
        if not ks:
            continue
        stages.append({"name": cat, "keys": ks})

    stages = _merge_small_stages(stages, min_stage_size=min_stage_size)

    # sanity: все ключи должны присутствовать ровно 1 раз
    seen = []
    for st in stages:
        seen.extend(st["keys"])
    uniq = list(dict.fromkeys(seen))
    if set(uniq) != set(keys):
        missing = [k for k in keys if k not in uniq]
        if missing:
            stages.append({"name": "missing", "keys": missing})

    return stages


def _build_stages_sensitivity(keys: List[str], oed_report: Dict[str, Any], top_fraction: float, min_stage_size: int) -> List[Dict[str, Any]]:
    """Построить 2 стадии: top по sens_rms и остальные."""
    tests = oed_report.get("tests", {}) if isinstance(oed_report, dict) else {}

    # collect sens_rms per test
    sens_by_param: Dict[str, List[float]] = {k: [] for k in keys}
    for _tname, tinfo in tests.items():
        sens = tinfo.get("sens_rms", {}) if isinstance(tinfo, dict) else {}
        for k in keys:
            v = sens.get(k, None)
            try:
                if v is None:
                    continue
                sens_by_param[k].append(float(v))
            except Exception:
                continue

    # score = rms over tests
    scores: Dict[str, float] = {}
    for k in keys:
        arr = sens_by_param.get(k, [])
        if not arr:
            scores[k] = 0.0
        else:
            # rms across tests
            s2 = sum(float(x) * float(x) for x in arr) / max(1.0, float(len(arr)))
            scores[k] = float(s2) ** 0.5

    ranked = sorted(keys, key=lambda k: scores.get(k, 0.0), reverse=True)
    total = sum(max(0.0, scores.get(k, 0.0)) for k in ranked)

    stage0: List[str] = []
    cum = 0.0
    for k in ranked:
        stage0.append(k)
        cum += max(0.0, scores.get(k, 0.0))
        if total > 0 and (cum / total) >= float(top_fraction) and len(stage0) >= min_stage_size:
            break

    stage1 = [k for k in ranked if k not in stage0]
    stages: List[Dict[str, Any]] = []
    stages.append({"name": "sensitivity_top", "keys": stage0})
    if stage1:
        stages.append({"name": "sensitivity_rest", "keys": stage1})

    stages = _merge_small_stages(stages, min_stage_size=min_stage_size)
    return stages



def _build_stages_fim_corr(
    keys: List[str],
    oed_report: Dict[str, Any],
    corr_thr: float = 0.85,
    max_stage_size: int = 6,
    min_stage_size: int = 2,
) -> List[Dict[str, Any]]:
    """Greedy staging by sensitivity + low-correlation packing.

    Uses:
    - tests[*].sens_rms as score (mean over tests),
    - suite_total.corr as correlation matrix.

    Returns multiple stages; each stage tries to keep |corr| <= corr_thr within stage.
    """
    tests = oed_report.get("tests", {}) if isinstance(oed_report, dict) else {}

    acc: Dict[str, List[float]] = {k: [] for k in keys}
    for _, tinfo in tests.items():
        if not isinstance(tinfo, dict):
            continue
        sens = tinfo.get("sens_rms", {})
        if not isinstance(sens, dict):
            continue
        for k in keys:
            v = sens.get(k, None)
            try:
                fv = float(v) if v is not None else None
            except Exception:
                fv = None
            if fv is None:
                continue
            if math.isfinite(fv) and fv > 0:
                acc[k].append(fv)

    score = {k: float(sum(acc[k]) / max(1, len(acc[k]))) for k in keys}

    # corr aligned
    rep_keys = None
    corr = None
    try:
        rep_keys = oed_report.get("params", {}).get("keys", None)
        corr = oed_report.get("suite_total", {}).get("corr", None)
    except Exception:
        rep_keys, corr = None, None

    if rep_keys is None or corr is None:
        C = np.zeros((len(keys), len(keys)), dtype=float)
    else:
        rep_keys = [str(k) for k in rep_keys]
        idx = {k: i for i, k in enumerate(rep_keys)}
        corr = np.asarray(corr, dtype=float)
        C = np.zeros((len(keys), len(keys)), dtype=float)
        for i, ki in enumerate(keys):
            ii = idx.get(ki, None)
            if ii is None:
                continue
            for j, kj in enumerate(keys):
                jj = idx.get(kj, None)
                if jj is None:
                    continue
                C[i, j] = float(abs(corr[ii, jj]))
        C = np.clip(C, 0.0, 1.0)

    ranked = sorted(keys, key=lambda k: float(score.get(k, 0.0)), reverse=True)
    unassigned = set(ranked)
    key_idx = {k: i for i, k in enumerate(keys)}

    stages: List[Dict[str, Any]] = []
    while unassigned:
        seed = None
        for k in ranked:
            if k in unassigned:
                seed = k
                break
        if seed is None:
            seed = next(iter(unassigned))

        st = [seed]
        unassigned.remove(seed)

        for k in ranked:
            if k not in unassigned:
                continue
            if len(st) >= int(max_stage_size):
                break
            ik = key_idx[k]
            ok = True
            for s in st:
                is_ = key_idx[s]
                if C[ik, is_] > float(corr_thr):
                    ok = False
                    break
            if ok:
                st.append(k)
                unassigned.remove(k)

        stages.append({"name": "fim_corr", "keys": st})

    stages = _merge_small_stages(stages, min_stage_size=min_stage_size)
    return stages



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit_ranges_json", required=True)
    ap.add_argument("--signals_csv", default="")
    ap.add_argument("--oed_report_json", default="")
    ap.add_argument("--method", default="auto", choices=["auto", "heuristic", "sensitivity", "fim_corr"])
    ap.add_argument("--top_fraction", type=float, default=0.7, help="Для sensitivity: доля суммарной чувствительности в stage0")
    ap.add_argument("--min_stage_size", type=int, default=2)
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    fit_ranges_json = Path(args.fit_ranges_json)
    if not fit_ranges_json.exists():
        raise SystemExit(f"fit_ranges_json not found: {fit_ranges_json}")

    ranges = _load_json(fit_ranges_json)
    if not isinstance(ranges, dict) or not ranges:
        raise SystemExit("fit_ranges_json must be a non-empty dict")

    keys = list(ranges.keys())

    signals_groups: Dict[str, float] = {}
    n_sig = 0
    if str(args.signals_csv).strip():
        signals_groups, n_sig = _read_signals_groups(Path(args.signals_csv))

    oed_report = None
    if str(args.oed_report_json).strip():
        p = Path(args.oed_report_json)
        if p.exists():
            try:
                oed_report = _load_json(p)
            except Exception:
                oed_report = None

    method = str(args.method).strip().lower()
    if method == "auto":
        method = "fim_corr" if oed_report is not None else "heuristic"

    if method == "fim_corr":
        if oed_report is None:
            stages = _build_stages_heuristic(keys, signals_groups, min_stage_size=int(args.min_stage_size))
            method_used = "heuristic_fallback"
        else:
            stages = _build_stages_fim_corr(keys, oed_report, corr_thr=0.85, max_stage_size=6, min_stage_size=int(args.min_stage_size))
            method_used = "fim_corr"
    elif method == "sensitivity":
        if oed_report is None:
            stages = _build_stages_heuristic(keys, signals_groups, min_stage_size=int(args.min_stage_size))
            method_used = "heuristic_fallback"
        else:
            stages = _build_stages_sensitivity(keys, oed_report, top_fraction=float(args.top_fraction), min_stage_size=int(args.min_stage_size))
            method_used = "sensitivity"
    else:
        stages = _build_stages_heuristic(keys, signals_groups, min_stage_size=int(args.min_stage_size))(keys, signals_groups, min_stage_size=int(args.min_stage_size))
        method_used = "heuristic"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "method_requested": str(args.method),
        "method_used": method_used,
        "n_params": int(len(keys)),
        "signals_groups": signals_groups if signals_groups else None,
        "n_enabled_signals": int(n_sig),
        "top_fraction": float(args.top_fraction),
        "min_stage_size": int(args.min_stage_size),
    }

    stages_json = {"meta": meta, "stages": stages}
    _save_json(stages_json, out_dir / "stages.json")

    # write union ranges per stage
    stage_ranges_dir = out_dir / "stage_ranges"
    stage_ranges_dir.mkdir(parents=True, exist_ok=True)

    union_keys: List[str] = []
    for i, st in enumerate(stages):
        union_keys.extend([k for k in st.get("keys", []) if k not in union_keys])
        rr = {k: ranges[k] for k in union_keys if k in ranges}
        _save_json(rr, stage_ranges_dir / f"stage{i}_ranges.json")

    print("DONE. Stages written to:", out_dir)


if __name__ == "__main__":
    main()
