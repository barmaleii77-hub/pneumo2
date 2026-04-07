#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_long_suite.py

Генератор "длинного" набора тестов (long-suite) поверх базового suite JSON.

Зачем:
- проверять устойчивость найденных параметров к разбросу массы/температуры/начальных давлений;
- формировать сценарии для робастной пост‑валидации.

Ключевая идея:
- исходный suite содержит тесты с полями ("имя"/"тип"/dt/t_end/target_* ...);
- мы создаём варианты каждого теста и добавляем в строку поля:
    params_override: { ... }

Дальше opt_worker_v3_margins_energy умеет применять params_override для каждого теста.

Пример:
  python -m pneumo_solver_ui.tools.generate_long_suite \
      --suite_in pneumo_solver_ui/default_suite.json \
      --suite_out pneumo_solver_ui/default_suite_long.json \
      --base_params pneumo_solver_ui/default_base.json

По умолчанию режим "extremes":
- берём min/max по каждому измерению (масса/температура/Pacc), строим 2^3=8 комбинаций
- добавляем baseline
Итого 9 сценариев на каждый тест.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _as_float(x: Any, default: float) -> float:
    try:
        v = float(x)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return float(default)


def _token_mass_kg(m_kg: float) -> str:
    return f"M{int(round(m_kg))}kg"


def _token_temp_K(T: float) -> str:
    return f"T{int(round(T))}K"


def _token_press_kPa(p_pa: float) -> str:
    return f"Pacc{int(round(p_pa/1000.0))}kPa"


def _name_of_row(row: Dict[str, Any], idx: int) -> str:
    for k in ("имя", "name", "id"):
        if isinstance(row.get(k), str) and row.get(k).strip():
            return str(row.get(k)).strip()
    return f"test_{idx}" 


def _enabled_of_row(row: Dict[str, Any]) -> bool:
    # Совместимость: "включен" или "enabled".
    v = row.get("включен", row.get("enabled", True))
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        return v.strip().lower() not in {"0", "false", "no", "off", "нет"}
    return True


def build_scenarios(
    mass0: float,
    temp0: float,
    pacc0: float,
    mass_factors: List[float],
    temps: List[float],
    pacc_factors: List[float],
    mode: str,
) -> List[Dict[str, float]]:
    masses = [mass0 * f for f in mass_factors]
    paccs = [pacc0 * f for f in pacc_factors]

    # baseline всегда присутствует
    def _with_baseline(vals: List[float], baseline: float) -> List[float]:
        out = list(vals)
        if not any(abs(v - baseline) < 1e-12 for v in out):
            out.append(baseline)
        return sorted(out)

    masses = _with_baseline(masses, mass0)
    temps = _with_baseline(list(temps), temp0)
    paccs = _with_baseline(paccs, pacc0)

    if mode == "cartesian":
        grid = list(itertools.product(masses, temps, paccs))
    elif mode == "pairs":
        # baseline + по одному измерению в min/max (без комбинирования)
        m_min, m_max = min(masses), max(masses)
        t_min, t_max = min(temps), max(temps)
        p_min, p_max = min(paccs), max(paccs)
        grid = [
            (mass0, temp0, pacc0),
            (m_min, temp0, pacc0),
            (m_max, temp0, pacc0),
            (mass0, t_min, pacc0),
            (mass0, t_max, pacc0),
            (mass0, temp0, p_min),
            (mass0, temp0, p_max),
        ]
    else:
        # extremes (default): комбинации min/max по измерениям + baseline
        m_min, m_max = min(masses), max(masses)
        t_min, t_max = min(temps), max(temps)
        p_min, p_max = min(paccs), max(paccs)
        grid = list(itertools.product([m_min, m_max], [t_min, t_max], [p_min, p_max]))
        grid.append((mass0, temp0, pacc0))

    # Уникализация
    seen: set[Tuple[int, int, int]] = set()
    out: List[Dict[str, float]] = []
    for m, T, p in grid:
        key = (int(round(m)), int(round(T * 10)), int(round(p)))
        if key in seen:
            continue
        seen.add(key)
        out.append({"масса_рамы": float(m), "температура_окр_К": float(T), "начальное_давление_аккумулятора": float(p)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate long-suite with params_override scenarios")
    ap.add_argument("--suite_in", type=str, default="pneumo_solver_ui/default_suite.json")
    ap.add_argument("--suite_out", type=str, default="pneumo_solver_ui/default_suite_long.json")
    ap.add_argument("--base_params", type=str, default="pneumo_solver_ui/default_base.json")

    ap.add_argument("--mode", type=str, choices=["extremes", "pairs", "cartesian"], default="extremes")
    ap.add_argument("--mass_factors", type=str, default="0.8,1.0,1.2", help="comma-separated")
    ap.add_argument("--temps", type=str, default="273.15,293.15,313.15", help="comma-separated (Kelvin)")
    ap.add_argument("--pacc_factors", type=str, default="0.8,1.0,1.2", help="comma-separated")

    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")

    args = ap.parse_args()

    suite_in = Path(args.suite_in)
    suite_out = Path(args.suite_out)
    base_params_path = Path(args.base_params)

    suite = load_json(suite_in)
    if not isinstance(suite, list):
        raise SystemExit(f"suite_in must be a JSON list, got: {type(suite)}")

    base = load_json(base_params_path)
    if not isinstance(base, dict):
        raise SystemExit(f"base_params must be a JSON object, got: {type(base)}")

    mass0 = _as_float(base.get("масса_рамы", 600.0), 600.0)
    temp0 = _as_float(base.get("температура_окр_К", 293.15), 293.15)

    # Базовое давление: поддерживаем два ключа (исторически)
    pacc0 = base.get("начальное_давление_аккумулятора")
    if pacc0 is None:
        pacc0 = base.get("начальное_давление_аккумулятора_Па")
    if pacc0 is None:
        # fallback: Pmin (как наиболее близкий по смыслу)
        pacc0 = base.get("давление_Pmin_сброс", 100000.0)
    pacc0 = _as_float(pacc0, 100000.0)

    mass_factors = [float(x) for x in args.mass_factors.split(",") if x.strip()]
    temps = [float(x) for x in args.temps.split(",") if x.strip()]
    pacc_factors = [float(x) for x in args.pacc_factors.split(",") if x.strip()]

    scenarios = build_scenarios(
        mass0=mass0,
        temp0=temp0,
        pacc0=pacc0,
        mass_factors=mass_factors,
        temps=temps,
        pacc_factors=pacc_factors,
        mode=args.mode,
    )

    if args.limit and args.limit > 0:
        scenarios = scenarios[: int(args.limit)]

    out_rows: List[Dict[str, Any]] = []

    for i, row in enumerate(suite):
        if not isinstance(row, dict):
            continue
        if not _enabled_of_row(row):
            continue

        base_name = _name_of_row(row, i)
        # Важно: оставляем исходный тип/таргеты/параметры теста, меняется только params_override.
        for s in scenarios:
            m = float(s["масса_рамы"])
            T = float(s["температура_окр_К"])
            pacc = float(s["начальное_давление_аккумулятора"])

            new_row = copy.deepcopy(row)

            suffix = "__" + "__".join([
                _token_mass_kg(m),
                _token_temp_K(T),
                _token_press_kPa(pacc),
            ])

            # имя
            if "имя" in new_row and isinstance(new_row.get("имя"), str):
                new_row["имя"] = base_name + suffix
            elif "name" in new_row and isinstance(new_row.get("name"), str):
                new_row["name"] = base_name + suffix
            else:
                new_row["имя"] = base_name + suffix

            # params_override: merge (scenario overrides win)
            ov = {}
            if isinstance(new_row.get("params_override", None), dict):
                ov.update(new_row.get("params_override", {}))
            ov.update({
                "масса_рамы": m,
                "температура_окр_К": T,
                # Поддерживаем исторический ключ без _Па.
                "начальное_давление_аккумулятора": pacc,
            })
            new_row["params_override"] = ov

            out_rows.append(new_row)

    save_json(suite_out, out_rows)

    print(f"Wrote {len(out_rows)} rows to: {suite_out}")
    print(f"Scenarios per test: {len(scenarios)} (mode={args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
