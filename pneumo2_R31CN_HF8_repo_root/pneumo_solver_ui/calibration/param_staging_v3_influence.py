# -*- coding: utf-8 -*-
"""param_staging_v3_influence.py

Построение стадий (staging) для подгонки параметров на основе:
- чувствительности/корреляций из OED/FIM отчёта (если есть),
- отчёта System Influence (пневматика + кинематика),

Зачем:
- уменьшить размерность задачи на ранних стадиях;
- сначала стабилизировать параметры с максимальным системным влиянием;
- учитывать корреляции (плохая обусловленность) при группировке.

Вход:
  --fit_ranges_json: JSON {param: [lo, hi]} (обязательно)
  --oed_report_json: oed_report.json (опционально)
  --system_influence_json: system_influence.json (опционально)
  --out_dir: куда писать результаты

Выход (out_dir):
  - stages_influence.json (список стадий)
  - fit_ranges_stage_00.json ... (накопительные диапазоны)
  - PARAM_STAGING_INFLUENCE.md

Алгоритм (по умолчанию):
- score_fim: mean_sens из OED по параметрам (нормируется)
- score_sys: сумма |эластичностей| по ключевым метрикам (нормируется)
- итоговый score = w_fim*score_fim + w_sys*score_sys
- greedy packing по стадиям с ограничением corr_abs <= corr_thr (если есть)

"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def _fmt(x: Any, nd: int = 6) -> str:
    try:
        xf = float(x)
    except Exception:
        return str(x)
    if not math.isfinite(xf):
        return str(x)
    ax = abs(xf)
    if ax != 0 and (ax < 1e-3 or ax > 1e6):
        return f"{xf:.{nd}e}"
    return f"{xf:.{nd}f}"


def _norm01(d: Dict[str, float]) -> Dict[str, float]:
    if not d:
        return {}
    vals = [abs(v) for v in d.values() if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if not vals:
        return {k: 0.0 for k in d}
    mx = max(vals)
    if mx <= 0:
        return {k: 0.0 for k in d}
    return {k: float(abs(v)) / mx if (isinstance(v, (int, float)) and math.isfinite(float(v))) else 0.0 for k, v in d.items()}


def _corr_map_from_oed(oed: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
    """Достаём |corr| из oed_report.json.

    Ожидаемые поля (как в oed_worker_v1_fim.py):
    - corrs: {"p1|p2": corr}

    Возвращает dict[(p1,p2)] = |corr|, симметричный.
    """
    out: Dict[Tuple[str, str], float] = {}
    corrs = oed.get("corrs")
    if isinstance(corrs, dict):
        for k, v in corrs.items():
            if not isinstance(k, str):
                continue
            if "|" not in k:
                continue
            p1, p2 = k.split("|", 1)
            try:
                cv = abs(float(v))
            except Exception:
                continue
            out[(p1, p2)] = cv
            out[(p2, p1)] = cv
    return out


def _mean_sens_from_oed(oed: Dict[str, Any]) -> Dict[str, float]:
    sens = oed.get("mean_sens")
    if isinstance(sens, dict):
        out = {}
        for k, v in sens.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                pass
        return out
    return {}


def _metric_candidates(metric_name: str) -> List[str]:
    names = [str(metric_name)]
    if metric_name.startswith("elas_"):
        bare = metric_name[5:]
        if bare:
            names.append(bare)
    else:
        names.append(f"elas_{metric_name}")
    # keep order but dedupe
    seen: set[str] = set()
    out: List[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _row_score_from_system_influence_record(record: Dict[str, Any], metrics: List[str]) -> float:
    if not isinstance(record, dict):
        return 0.0
    try:
        score_val = float(record.get("score", 0.0))
        if math.isfinite(score_val) and abs(score_val) > 0.0:
            return abs(score_val)
    except Exception:
        pass

    elastic = record.get("elasticity")
    metric_sources: List[Dict[str, Any]] = []
    if isinstance(record, dict):
        metric_sources.append(record)
    if isinstance(elastic, dict):
        metric_sources.append(elastic)

    s = 0.0
    for metric_name in metrics:
        found = False
        for source in metric_sources:
            if not isinstance(source, dict):
                continue
            for cand in _metric_candidates(metric_name):
                if cand in source:
                    try:
                        s += abs(float(source.get(cand, 0.0)))
                        found = True
                        break
                    except Exception:
                        pass
            if found:
                break
    return float(s)


def _sys_score_from_influence(sysinf: Dict[str, Any], metrics: Optional[List[str]] = None) -> Dict[str, float]:
    """Extract per-parameter influence score from System Influence report.

    Supports both schemas that appeared across releases:
    - legacy mapping: {"params": {param: {"elasticity": {...}}}}
    - current report v1: {"params": [{"param": ..., "score": ..., "elas_*": ...}, ...]}

    The current report already exports a combined `score`, so we prefer it when
    available. Falling back to explicit elasticity sums keeps backward
    compatibility with older payloads.
    """
    if metrics is None:
        metrics = [
            "elas_min_bottleneck_mdot",
            "elas_Kphi",
            "elas_Ktheta",
            "elas_phi_crit_deg",
            "elas_f_roll",
            "elas_f_pitch",
        ]

    params = sysinf.get("params")
    out: Dict[str, float] = {}

    if isinstance(params, dict):
        for pname, pdata in params.items():
            score = _row_score_from_system_influence_record(dict(pdata) if isinstance(pdata, dict) else {}, metrics)
            out[str(pname)] = float(score)
        return out

    if isinstance(params, list):
        for rec in params:
            if not isinstance(rec, dict):
                continue
            pname = str(rec.get("param") or rec.get("name") or "").strip()
            if not pname:
                continue
            out[pname] = _row_score_from_system_influence_record(rec, metrics)
    return out


def _build_stages(
    params: List[str],
    score: Dict[str, float],
    corr_map: Dict[Tuple[str, str], float],
    corr_thr: float,
    stage_size: int,
) -> List[List[str]]:
    """Greedy packing: набираем стадии, избегая сильнокоррелированных пар внутри стадии."""

    # sort by score desc
    ordered = sorted(params, key=lambda p: score.get(p, 0.0), reverse=True)

    stages: List[List[str]] = []
    used: set = set()

    for p in ordered:
        if p in used:
            continue
        # start new stage
        cur: List[str] = [p]
        used.add(p)

        # fill stage
        for q in ordered:
            if q in used:
                continue
            # corr check
            ok = True
            for r in cur:
                c = corr_map.get((q, r), 0.0)
                if c >= corr_thr:
                    ok = False
                    break
            if ok:
                cur.append(q)
                used.add(q)
            if len(cur) >= stage_size:
                break

        stages.append(cur)

    return stages


def _cumulative_ranges(fit_ranges: Dict[str, Any], stages: List[List[str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    acc: Dict[str, Any] = {}
    for stg in stages:
        for p in stg:
            if p in fit_ranges:
                acc[p] = fit_ranges[p]
        out.append(dict(acc))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit_ranges_json", required=True)
    ap.add_argument("--oed_report_json", default="")
    ap.add_argument("--system_influence_json", default="")
    ap.add_argument("--out_dir", required=True)

    ap.add_argument("--corr_thr", type=float, default=0.92)
    ap.add_argument("--stage_size", type=int, default=5)
    ap.add_argument("--w_fim", type=float, default=0.65)
    ap.add_argument("--w_sys", type=float, default=0.35)

    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fit_ranges = _load_json(Path(args.fit_ranges_json))
    if not isinstance(fit_ranges, dict) or not fit_ranges:
        raise SystemExit(f"fit_ranges_json пустой/некорректный: {args.fit_ranges_json}")

    params = sorted([str(k) for k in fit_ranges.keys()])

    # OED/FIM
    oed: Dict[str, Any] = {}
    corr_map: Dict[Tuple[str, str], float] = {}
    score_fim: Dict[str, float] = {}
    if str(args.oed_report_json).strip():
        p_oed = Path(args.oed_report_json)
        if p_oed.exists():
            oed = _load_json(p_oed)
            if isinstance(oed, dict):
                corr_map = _corr_map_from_oed(oed)
                score_fim = _mean_sens_from_oed(oed)

    # System influence
    sysinf: Dict[str, Any] = {}
    score_sys: Dict[str, float] = {}
    if str(args.system_influence_json).strip():
        p_sys = Path(args.system_influence_json)
        if p_sys.exists():
            sysinf = _load_json(p_sys)
            if isinstance(sysinf, dict):
                score_sys = _sys_score_from_influence(sysinf)

    score_fim_n = _norm01({p: score_fim.get(p, 0.0) for p in params})
    score_sys_n = _norm01({p: score_sys.get(p, 0.0) for p in params})

    w_fim = float(args.w_fim)
    w_sys = float(args.w_sys)
    w_sum = max(w_fim + w_sys, 1e-9)
    w_fim /= w_sum
    w_sys /= w_sum

    score: Dict[str, float] = {}
    for p in params:
        score[p] = w_fim * score_fim_n.get(p, 0.0) + w_sys * score_sys_n.get(p, 0.0)

    stages = _build_stages(
        params=params,
        score=score,
        corr_map=corr_map,
        corr_thr=float(args.corr_thr),
        stage_size=int(args.stage_size),
    )

    cum = _cumulative_ranges(fit_ranges, stages)

    plan = {
        "version": "param_staging_v3_influence",
        "ts": time.time(),
        "fit_ranges_json": str(Path(args.fit_ranges_json).resolve()),
        "oed_report_json": str(Path(args.oed_report_json).resolve()) if str(args.oed_report_json).strip() else "",
        "system_influence_json": str(Path(args.system_influence_json).resolve()) if str(args.system_influence_json).strip() else "",
        "corr_thr": float(args.corr_thr),
        "stage_size": int(args.stage_size),
        "weights": {"w_fim": w_fim, "w_sys": w_sys},
        "stages": stages,
    }

    _save_json(plan, out_dir / "stages_influence.json")

    for i, rj in enumerate(cum):
        _save_json(rj, out_dir / f"fit_ranges_stage_{i:02d}.json")

    # Markdown summary
    md: List[str] = []
    md.append("# Influence-guided parameter staging\n")
    md.append(f"out_dir: `{out_dir.name}`\n")
    md.append("## Inputs\n")
    md.append(f"- fit_ranges_json: `{Path(args.fit_ranges_json).name}`")
    if str(args.oed_report_json).strip():
        md.append(f"- oed_report_json: `{Path(args.oed_report_json).name}`")
    if str(args.system_influence_json).strip():
        md.append(f"- system_influence_json: `{Path(args.system_influence_json).name}`")
    md.append("")

    md.append("## Scoring\n")
    md.append(f"- corr_thr: `{args.corr_thr}`")
    md.append(f"- stage_size: `{args.stage_size}`")
    md.append(f"- weights: w_fim={_fmt(w_fim, nd=3)}, w_sys={_fmt(w_sys, nd=3)}\n")

    md.append("## Stages\n")
    for i, stg in enumerate(stages):
        md.append(f"### Stage {i:02d} (n={len(stg)})")
        for p in stg:
            md.append(
                f"- `{p}`: score={_fmt(score.get(p), nd=4)} (fim={_fmt(score_fim_n.get(p), nd=3)}, sys={_fmt(score_sys_n.get(p), nd=3)})"
            )
        md.append("")

    md.append("## Files\n")
    md.append("- stages_influence.json")
    md.append("- fit_ranges_stage_00.json ...")

    _save_text("\n".join(md), out_dir / "PARAM_STAGING_INFLUENCE.md")

    print(f"[OK] Influence staging written to: {out_dir}")


if __name__ == "__main__":
    main()
