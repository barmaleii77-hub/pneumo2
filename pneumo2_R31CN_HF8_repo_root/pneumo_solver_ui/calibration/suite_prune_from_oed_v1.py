# -*- coding: utf-8 -*-
"""
suite_prune_from_oed_v1.py

Сокращение набора тестов suite_json по результатам OED/FIM (oed_worker_v1_fim.py),
чтобы ускорять последующие калибровки.

Идея:
- oed_report.json содержит greedy_D_opt.order (порядок тестов) и logdet_cum.
- Берём первые N тестов, которые дают fraction*logdet_total (например 0.95),
  либо просто первые N (если logdet_cum нет).
- Формируем новый suite_json, сохраняя исходные настройки тестов, но оставляя
  только выбранные.

Ограничения:
- Это эвристика. Всегда проверяйте, что holdout качество не деградирует.

Пример:
python calibration/suite_prune_from_oed_v1.py ^
  --oed_report calibration_runs/RUN_.../oed_report.json ^
  --suite_json default_suite.json ^
  --out_suite_json calibration_runs/RUN_.../suite_reduced.json ^
  --fraction 0.95

"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _as_suite_list(suite_obj: Any) -> List[Dict[str, Any]]:
    if isinstance(suite_obj, list):
        return suite_obj
    if isinstance(suite_obj, dict):
        if "suite" in suite_obj and isinstance(suite_obj["suite"], list):
            return suite_obj["suite"]
        if "tests" in suite_obj and isinstance(suite_obj["tests"], list):
            return suite_obj["tests"]
    raise ValueError("suite_json должен быть list или dict{suite:[...]} / dict{tests:[...]}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oed_report", required=True)
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--out_suite_json", required=True)
    ap.add_argument("--fraction", type=float, default=0.95, help="Доля финального logdet, которую хотим сохранить (0..1)")
    ap.add_argument("--max_tests", type=int, default=9999, help="Ограничить абсолютное число тестов")
    args = ap.parse_args()

    oed = _load_json(Path(args.oed_report))
    suite_obj = _load_json(Path(args.suite_json))
    suite_list = _as_suite_list(suite_obj)

    greedy = oed.get("greedy_D_opt", {}) if isinstance(oed, dict) else {}
    order = greedy.get("order", [])
    logdet_cum = greedy.get("logdet_cum", [])

    if not order:
        raise SystemExit("В oed_report нет greedy_D_opt.order. Сначала запустите oed_worker_v1_fim.py.")

    # determine N
    N = min(len(order), int(args.max_tests))
    frac = float(args.fraction)
    frac = max(0.0, min(1.0, frac))

    if logdet_cum and isinstance(logdet_cum, list) and len(logdet_cum) == len(order) and len(order) > 1:
        try:
            total = float(logdet_cum[-1])
            target = total * frac
            for i, v in enumerate(logdet_cum):
                if float(v) >= target:
                    N = min(N, i + 1)
                    break
        except Exception:
            pass

    picked = set(str(x) for x in order[:N])

    # filter suite preserving order
    out_list = []
    skipped = []
    for t in suite_list:
        name = str(t.get("имя", t.get("name", ""))).strip()
        if not name:
            continue
        if name in picked:
            out_list.append(t)
        else:
            skipped.append(name)

    out_obj = {"suite": out_list}
    _save_json(out_obj, Path(args.out_suite_json))

    print("Selected tests:", len(out_list), "of", len(suite_list))
    print("Wrote:", args.out_suite_json)


if __name__ == "__main__":
    main()
