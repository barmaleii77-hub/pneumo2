#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""post_validate_robust.py

Робастная пост‑валидация результатов оптимизации.

Сценарий:
1) Вы запустили оптимизацию (opt_worker_v3_margins_energy.py) и получили CSV
   c найденными параметрами (включая колонки "параметр__...").
2) Вы сгенерировали long-suite (набор сценариев) с помощью generate_long_suite.py
   и хотите понять: какие найденные решения "держатся" по худшему случаю.

Этот скрипт:
- берет TOP-K кандидатов из results_csv (с наименьшим `штраф_физичности_сумма`);
- для каждого кандидата прогоняет long-suite,
- агрегирует штрафы робастно:
    * worst (default): для каждой базовой группы тестов (до суффикса "__")
      берётся max(штраф), затем суммируется по группам.
    * mean: средний штраф по группе, затем сумма.
    * cvar: среднее по худшим alpha‑долям внутри группы.
- пишет ранжированную таблицу.

Пример:
  python -m pneumo_solver_ui.tools.post_validate_robust \
      --results_csv runs/2026-01-25_.../results.csv \
      --base_json pneumo_solver_ui/default_base.json \
      --suite_json pneumo_solver_ui/default_suite_long.json \
      --model_path pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py \
      --top_k 10
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import pandas as pd

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

# Важно: используем логику метрик/штрафов из opt_worker, чтобы робастная
# проверка совпадала с оптимизацией.
from pneumo_solver_ui import opt_worker_v3_margins_energy as ow


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _isfinite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _group_key(test_name: str) -> str:
    # Базовая группа: всё до первого "__".
    # Под это заточен generate_long_suite.py.
    return test_name.split("__", 1)[0]


def _cvar(values: List[float], alpha: float) -> float:
    if not values:
        return 0.0
    vv = sorted(float(x) for x in values)
    # CVaR по худшим alpha долям (верхний хвост)
    alpha = max(1e-9, min(1.0, float(alpha)))
    k = max(1, int(math.ceil(alpha * len(vv))))
    tail = vv[-k:]
    return float(sum(tail) / max(1, len(tail)))


def robust_aggregate(penalties_by_group: Dict[str, List[float]], mode: str, cvar_alpha: float) -> Tuple[float, Dict[str, float]]:
    per_group: Dict[str, float] = {}
    for g, vals in penalties_by_group.items():
        if not vals:
            per_group[g] = 0.0
            continue
        if mode == "mean":
            per_group[g] = float(sum(vals) / len(vals))
        elif mode == "cvar":
            per_group[g] = _cvar(vals, cvar_alpha)
        else:
            per_group[g] = float(max(vals))
    total = float(sum(per_group.values()))
    return total, per_group


def extract_candidate_params(base: Dict[str, Any], row: pd.Series) -> Dict[str, Any]:
    params = dict(base)
    for col, v in row.items():
        if not isinstance(col, str):
            continue
        if not col.startswith("параметр__"):
            continue
        name = col[len("параметр__") :]
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        if _isfinite(v):
            params[name] = float(v)
        else:
            # Не числовое значение пропускаем
            continue
    return params


def main() -> int:
    ap = argparse.ArgumentParser(description="Robust post-validation over long-suite")
    ap.add_argument("--results_csv", type=str, required=True)
    ap.add_argument("--base_json", type=str, default="pneumo_solver_ui/default_base.json")
    ap.add_argument("--suite_json", type=str, default="pneumo_solver_ui/default_suite_long.json")
    ap.add_argument("--model_path", type=str, default="pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--top_k", type=int, default=10)
    ap.add_argument("--mode", type=str, choices=["worst", "mean", "cvar"], default="worst")
    ap.add_argument("--cvar_alpha", type=float, default=0.2)
    ap.add_argument("--out_csv", type=str, default="")

    args = ap.parse_args()

    results_path = Path(args.results_csv)
    base_path = Path(args.base_json)
    suite_path = Path(args.suite_json)
    model_path = Path(args.model_path)

    if not results_path.exists():
        raise SystemExit(f"results_csv not found: {results_path}")
    if not base_path.exists():
        raise SystemExit(f"base_json not found: {base_path}")
    if not suite_path.exists():
        raise SystemExit(f"suite_json not found: {suite_path}")
    if not model_path.exists():
        raise SystemExit(f"model_path not found: {model_path}")

    df = pd.read_csv(results_path)
    if df.empty:
        raise SystemExit("results_csv is empty")

    base = load_json(base_path)
    if not isinstance(base, dict):
        raise SystemExit("base_json must be JSON object")

    suite_rows = load_json(suite_path)
    if not isinstance(suite_rows, list):
        raise SystemExit("suite_json must be JSON list")

    # Выбираем TOP-K по базовому штрафу (если он есть)
    if "штраф_физичности_сумма" in df.columns:
        df = df[df["штраф_физичности_сумма"].apply(_isfinite)].copy()
        df.sort_values("штраф_физичности_сумма", ascending=True, inplace=True)

    df_top = df.head(int(max(1, args.top_k))).copy()

    # Загружаем модель
    model = ow.load_model(str(model_path))

    # Робастная оценка
    out_rows: List[Dict[str, Any]] = []
    for i, r in df_top.iterrows():
        params = extract_candidate_params(base, r)

        # ABSOLUTE LAW: no key aliases like "база_м"/"колея_м".
        # Geometry defaults must come from the canonical base (model inputs), not magic constants.
        _trk0 = float(base.get("колея", 1.0) or 1.0)
        _wb0 = float(base.get("база", 1.5) or 1.5)
        cfg = {
            "suite": suite_rows,
            # Геометрия для генерации профиля bump_diag (если есть)
            "колея": float(params.get("колея", _trk0) or _trk0),
            "база": float(params.get("база", _wb0) or _wb0),
        }

        row = ow.eval_candidate(model, idx=int(r.get("id", i)), params=params, cfg=cfg)

        # собираем пер‑тестовые штрафы
        penalties_by_group: Dict[str, List[float]] = {}
        for k, v in row.items():
            if not isinstance(k, str):
                continue
            if not k.endswith("__штраф"):
                continue
            test_name = k[: -len("__штраф")]
            g = _group_key(test_name)
            try:
                pv = float(v)
            except Exception:
                continue
            penalties_by_group.setdefault(g, []).append(pv)

        robust_total, per_group = robust_aggregate(penalties_by_group, mode=args.mode, cvar_alpha=float(args.cvar_alpha))

        out_row: Dict[str, Any] = {
            "src_id": int(r.get("id", i)) if _isfinite(r.get("id", i)) else int(i),
            "robust_total": float(robust_total),
            "mode": args.mode,
        }
        if "штраф_физичности_сумма" in r.index and _isfinite(r.get("штраф_физичности_сумма")):
            out_row["base_penalty_sum"] = float(r.get("штраф_физичности_сумма"))

        # Добавляем пару важных KPI если есть
        for kpi in [
            "штраф_физичности_сумма",
            "kpi__min_gap_pct_min",
            "kpi__contact_lost_any_max",
            "kpi__min_breakdown_roll_deg",
            "kpi__min_breakdown_pitch_deg",
        ]:
            if kpi in row and _isfinite(row.get(kpi)):
                out_row[kpi] = float(row.get(kpi))

        # Сохраним worst по группам (это удобно для диагностики)
        for g, pv in sorted(per_group.items()):
            out_row[f"group__{g}__robust"] = float(pv)

        out_rows.append(out_row)

        print(f"[{i}] robust_total={robust_total:.6g} groups={len(per_group)}")

    df_out = pd.DataFrame(out_rows)
    df_out.sort_values("robust_total", ascending=True, inplace=True)

    out_csv = Path(args.out_csv) if args.out_csv else results_path.with_name(results_path.stem + "_robust.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_csv, index=False)
    print(f"Wrote: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
