# -*- coding: utf-8 -*-
"""Быстрые инварианты модели (sanity + property-like randomized checks).

Цель:
- быстро ловить NaN/Inf, отрицательные абсолютные давления, развал балансов энергии/массы
- не заменяет полноценную верификацию, но даёт «страховку» при правках математики

Запуск:
    python tools/property_invariants.py

Примечания:
- Использует default_base.json / default_ranges.json / default_suite.json.
- Для скорости запускает короткий прогон (t_end≈0.2s) на одном «мягком» тесте (микро-синус).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Tuple, List

import numpy as np


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _pick_smoke_test(worker: Any, suite_cfg: Dict[str, Any]) -> Tuple[str, Dict[str, Any], float, float]:
    """Pick one numerically soft test for property-style invariants.

    Current optimization-ready defaults may intentionally keep every suite row disabled.
    Preflight must not crash on that configuration, so we first try the explicit suite,
    then fall back to the worker's built-in canonical test set, and finally synthesize a
    minimal micro-sine scenario if even that is unavailable.
    """
    tests = list(worker.build_test_suite(suite_cfg) or [])
    if not tests:
        tests = list(worker.build_test_suite({}) or [])
    for name, test_dict, dt, t_end, _targets in tests:
        if "микро" in str(name).lower():
            return str(name), dict(test_dict), float(dt), float(t_end)
    if tests:
        name, test_dict, dt, t_end, _targets = tests[0]
        return str(name), dict(test_dict), float(dt), float(t_end)
    return (
        "микро_синфаза_fallback",
        dict(worker.make_test_micro_sin(A=0.004, f=3.0)),
        0.003,
        1.6,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    base = _load_json(root / "default_base.json")
    ranges = _load_json(root / "default_ranges.json")
    suite_cfg = _load_json(root / "default_suite.json")

    import importlib.util, sys

    spec_m = importlib.util.spec_from_file_location("model", str(root / "model_pneumo_v8_energy_audit_vacuum.py"))
    model = importlib.util.module_from_spec(spec_m)
    sys.modules["model"] = model
    spec_m.loader.exec_module(model)  # type: ignore

    spec_w = importlib.util.spec_from_file_location("worker", str(root / "opt_worker_v3_margins_energy.py"))
    worker = importlib.util.module_from_spec(spec_w)
    sys.modules["worker"] = worker
    spec_w.loader.exec_module(worker)  # type: ignore

    test_name, test_dict, dt0, t_end0 = _pick_smoke_test(worker, suite_cfg)
    dt = max(5e-4, min(0.01, dt0))
    t_end = min(0.2, t_end0)

    # Список параметров для рандомизации (подбираем «нейтральные», чтобы не взрывать модель)
    keys = [
        "k_tire_Н_м", "c_tire_Н_с_м",
        "k_stop_Н_м", "c_stop_Н_с_м",
        "C1_ресивер", "C2_ресивер", "C3_ресивер",
        "C_аккум",
    ]
    keys = [k for k in keys if k in base and k in ranges and _is_num(base[k])]

    rng = np.random.default_rng(12345)

    def check_case(params: Dict[str, Any], case_id: int) -> Tuple[bool, str]:
        try:
            df_main, df_dros, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = model.simulate(
                params, test_dict, dt=dt, t_end=t_end, record_full=False
            )
        except Exception as e:
            return False, f"case {case_id}: simulate() exception: {e}"

        # 1) NaN/Inf в df_main
        if not np.isfinite(df_main.select_dtypes(include=[float, int]).to_numpy()).all():
            return False, f"case {case_id}: NaN/Inf detected in df_main"

        # 2) давления в ресиверах должны быть >0
        p_cols = [c for c in df_main.columns if c.endswith("_Па") and "давление" in c]
        for c in p_cols:
            if (df_main[c] <= 0.0).any():
                return False, f"case {case_id}: non-positive pressure in {c}"

        # 3) ошибки баланса энергии должны быть конечными и не взрывными
        for c in ["баланс_энергии_ошибка_отн", "баланс_энергии_газ_стенка_ошибка_отн"]:
            if c in df_atm.columns:
                v = float(df_atm[c].iloc[0])
                if not math.isfinite(v):
                    return False, f"case {case_id}: {c} is not finite"
                if abs(v) > 0.2:
                    return False, f"case {case_id}: {c} too large: {v}"

        return True, "ok"

    # Базовый прогон
    ok, msg = check_case(dict(base), 0)
    if not ok:
        print("FAIL:", msg)
        return 1

    # Рандомизированные прогоны
    N = 12
    for i in range(1, N + 1):
        p = dict(base)
        for k in keys:
            lo, hi = ranges[k]
            lo = float(lo); hi = float(hi)
            v0 = float(p[k])
            # ±20% вокруг базового (с клипом по диапазону)
            v = v0 * (1.0 + 0.2 * rng.normal())
            p[k] = _clip(v, lo, hi)

        ok, msg = check_case(p, i)
        if not ok:
            print("FAIL:", msg)
            return 1

    print(f"property_invariants: OK (cases={N+1}, test='{test_name}', dt={dt}, t_end={t_end})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
