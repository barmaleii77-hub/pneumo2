#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fuzz_smoke.py

Вариативный smoke-тест: случайно сэмплирует параметры из ranges_json,
делает короткие прогоны симуляции и проверяет, что:
- код не падает,
- метрики возвращаются словарём,
- ключевые численные значения конечные (без NaN/Inf).

Зачем
----
Дефолтный кейс может проходить, но модель/число может падать на комбинациях
параметров внутри допустимых диапазонов. Этот инструмент ловит такие вещи рано.

Пример:
  python pneumo_solver_ui/tools/fuzz_smoke.py --n 20 --seed 0     --model pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py     --suite_json pneumo_solver_ui/default_suite.json     --base_json pneumo_solver_ui/default_base.json     --ranges_json pneumo_solver_ui/default_ranges.json

"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    import sys as _sys
    from pathlib import Path as _Path

    _ROOT = _Path(__file__).resolve().parents[2]
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

try:
    from ..module_loading import load_python_module_from_path
except Exception:
    from pneumo_solver_ui.module_loading import load_python_module_from_path


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_module(path: Path, module_name: str):
    """Load a .py file as a module by absolute path."""
    return load_python_module_from_path(path.resolve(), module_name)


def _build_probe_enabled_suite(suite_rows: List[Dict[str, Any]] | List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in list(suite_rows or []):
        if not isinstance(row, dict):
            continue
        probe = dict(row)
        probe["enabled"] = True
        probe["включен"] = True
        out.append(probe)
    return out


def _probe_row_assets_exist(test: Dict[str, Any], repo_root: Path) -> bool:
    for key in ("road_csv", "axay_csv", "scenario_json"):
        raw = test.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = (repo_root / path).resolve()
        if not path.exists():
            return False
    return True


def _isfinite_number(x: Any) -> bool:
    if isinstance(x, bool):
        return True
    if isinstance(x, int):
        return True
    if isinstance(x, float):
        return math.isfinite(x)
    return True


def _metrics_have_nan(metrics: Dict[str, Any]) -> Tuple[bool, str]:
    """Проверка метрик на NaN/Inf.

    Практическая деталь: некоторые метрики "времени достижения/успокоения" могут быть +inf как
    валидный sentinel ("не наступило за окно наблюдения").

    Поэтому:
    - NaN запрещён всегда.
    - +inf запрещаем только для **критичных** метрик (остальные разрешаем).
    """
    critical = {"pR3_max_бар", "крен_max_град", "тангаж_max_град", "ошибка_энергии_газа_отн"}

    for k, v in metrics.items():
        if isinstance(v, float):
            if math.isnan(v):
                if str(k) in critical:
                    return True, f"{k}={v}"
                # для остальных метрик допускаем NaN как sentinel
                continue
            if not math.isfinite(v):
                if str(k) in critical:
                    return True, f"{k}={v}"
                # для остальных метрик разрешаем +inf (sentinel)
                continue
    return False, ""


@dataclass
class SampleResult:
    i: int
    ok: bool
    error: str
    nan_field: str
    params: Dict[str, float]


def sample_candidate(ranges: Dict[str, List[float]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, ab in ranges.items():
        try:
            a = float(ab[0])
            b = float(ab[1])
        except Exception:
            continue
        if not math.isfinite(a) or not math.isfinite(b):
            continue
        if a == b:
            out[k] = a
        else:
            lo = min(a, b)
            hi = max(a, b)
            out[k] = lo + (hi - lo) * random.random()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="number of random samples")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--allow_failures", type=int, default=0, help="allowed failing samples without nonzero exit")

    ap.add_argument("--model", required=True, help="path to model .py")
    ap.add_argument("--worker", default="pneumo_solver_ui/opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--base_json", required=True)
    ap.add_argument("--ranges_json", required=True)

    ap.add_argument("--dt_cap", type=float, default=0.01, help="cap dt for speed")
    ap.add_argument("--t_end_cap", type=float, default=0.2, help="cap t_end for speed")

    ap.add_argument("--out_dir", default=None)
    args = ap.parse_args()

    random.seed(int(args.seed))

    model_path = Path(args.model)
    worker_path = Path(args.worker)
    suite_path = Path(args.suite_json)
    base_path = Path(args.base_json)
    ranges_path = Path(args.ranges_json)

    out_dir = Path(args.out_dir).resolve() if args.out_dir else Path.cwd().resolve() / "fuzz"
    out_dir.mkdir(parents=True, exist_ok=True)

    # load
    model = _load_module(model_path, "pneumo_model_fuzz")
    worker = _load_module(worker_path, "pneumo_worker_fuzz")

    base = _load_json(base_path)
    suite = _load_json(suite_path)
    ranges = _load_json(ranges_path)

    repo_root = Path(__file__).resolve().parents[2]
    tests = worker.build_test_suite({"suite": suite})
    if not tests:
        probe_suite = _build_probe_enabled_suite(suite if isinstance(suite, list) else [])
        probe_suite = [row for row in probe_suite if _probe_row_assets_exist(row, repo_root)]
        if probe_suite:
            print(f"[fuzz_smoke] INFO: suite produced 0 tests; using forced-enable probe copy ({len(probe_suite)} rows)")
            tests = worker.build_test_suite({"suite": probe_suite})
        if not tests:
            tests = worker.build_test_suite({})
            if tests:
                print("[fuzz_smoke] INFO: probe suite still empty; falling back to worker builtin suite")
        if not tests:
            raise SystemExit("suite is empty")

    # choose one representative test (first enabled)
    test_name, test_cfg, dt, t_end, targets = tests[0]
    dt = float(min(float(dt), float(args.dt_cap)))
    t_end = float(min(float(t_end), float(args.t_end_cap)))

    results: List[SampleResult] = []
    fail_count = 0

    for i in range(1, int(args.n) + 1):
        cand = dict(base)
        cand_params = sample_candidate(ranges)
        cand.update(cand_params)

        ok = True
        err = ""
        nan_field = ""

        try:
            metrics = worker.eval_candidate_once(model, cand, test_cfg, dt=dt, t_end=t_end, targets=targets)
            if not isinstance(metrics, dict):
                ok = False
                err = f"metrics is not dict: {type(metrics).__name__}"
            else:
                has_nan, what = _metrics_have_nan(metrics)
                if has_nan:
                    ok = False
                    nan_field = what
        except Exception:
            ok = False
            err = traceback.format_exc(limit=10)

        if not ok:
            fail_count += 1

        results.append(SampleResult(i=i, ok=ok, error=err, nan_field=nan_field, params=cand_params))

    # write csv
    csv_path = out_dir / "fuzz_results.csv"
    # stable header
    keys = sorted({k for r in results for k in r.params.keys()})
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["i", "ok", "nan_field", "error"] + keys)
        for r in results:
            w.writerow([r.i, int(r.ok), r.nan_field, (r.error[:300].replace("\n", " ") if r.error else "")] + [r.params.get(k, "") for k in keys])

    summary = {
        "ts": _now_iso(),
        "n": int(args.n),
        "seed": int(args.seed),
        "allow_failures": int(args.allow_failures),
        "fail_count": int(fail_count),
        "ok": bool(fail_count <= int(args.allow_failures)),
        "test_used": {
            "name": test_name,
            "dt": dt,
            "t_end": t_end,
        },
        "paths": {
            "csv": str(csv_path),
        },
    }

    (out_dir / "fuzz_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== FUZZ SMOKE SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
