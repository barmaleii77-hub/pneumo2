# -*- coding: utf-8 -*-
"""Механо‑энергоаудит: регрессионный отчёт по suite.

Зачем
-----
Smoke‑check (tools/mech_energy_smoke_check.py) ловит грубые ошибки на одном тесте.
Но для матмодели важно видеть, что баланс энергии и проверка p·dV держатся
на разных возбуждениях (крен/тангаж/дорога/диагональ/вакуум и т.д.).

Этот скрипт:
- берёт `default_base.json` и `default_suite.json`,
- прогоняет включённые тесты (с ограничением по длительности),
- считает метрики баланса механической энергии и p·dV,
- пишет понятный отчёт в `pneumo_solver_ui/reports/`.

Запуск
------
Из папки `pneumo_solver_ui`:

    python tools/mech_energy_regression_report.py

Параметры
---------
    --model <py-module>     (по умолчанию: model_pneumo_v8_energy_audit_vacuum_patched_smooth_all)
    --suite <file.json>     (по умолчанию: default_suite.json)
    --params <file.json>    (по умолчанию: default_base.json)
    --limit N               ограничить число тестов (0 = без ограничений)
    --t-end-cap SEC         ограничить t_end каждого теста (по умолчанию 1.2с)
    --dt-min SEC            минимальный шаг dt (по умолчанию 0.003с) — ускоряет прогон
    --rel-th TH             порог относительной ошибки энергии (по умолчанию 0.25)
    --pdv-th TH             порог |ошибка_мощности_p_dV| (Вт) (по умолчанию 5e-3)
    --strict                возвращать non-zero код, если найден провал по порогам

Коды возврата
-------------
0 — всё ок (или --strict не задан)
2 — найден провал по порогам (--strict)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _ensure_sys_path(root: Path) -> None:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _import_model(root: Path, module_name: str):
    _ensure_sys_path(root)
    return importlib.import_module(module_name)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_enabled_suite(suite: Any) -> List[Dict[str, Any]]:
    if not isinstance(suite, list):
        return []
    out: List[Dict[str, Any]] = []
    for t in suite:
        if not isinstance(t, dict):
            continue
        if not t.get("включен", True):
            continue
        out.append(t)
    return out


def _metrics_from_df(df: pd.DataFrame) -> Dict[str, float]:
    def colmax_abs(name: str) -> float:
        if name not in df.columns:
            return 0.0
        v = df[name].to_numpy(dtype=float)
        if v.size == 0:
            return 0.0
        return float(np.nanmax(np.abs(v)))

    def col_last(name: str) -> float:
        if name not in df.columns or len(df) == 0:
            return 0.0
        try:
            return float(df[name].iloc[-1])
        except Exception:
            return 0.0

    return {
        "max_abs_err_E_J": colmax_abs("ошибка_энергии_мех_Дж"),
        "max_rel_err_E": colmax_abs("ошибка_энергии_мех_отн"),
        "end_rel_err_E": col_last("ошибка_энергии_мех_отн"),
        "max_pdv_err_W": colmax_abs("ошибка_мощности_p_dV_Вт"),
        "end_pdv_work_err_J": col_last("ошибка_работа_p_dV_Дж"),
    }


def _safe_name(test: Dict[str, Any], idx: int) -> str:
    return str(test.get("имя") or test.get("тип") or f"test_{idx}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all")
    ap.add_argument("--suite", default="default_suite.json")
    ap.add_argument("--params", default="default_base.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--t-end-cap", type=float, default=1.2)
    ap.add_argument("--dt-min", type=float, default=0.003)
    ap.add_argument("--rel-th", type=float, default=0.25)
    ap.add_argument("--pdv-th", type=float, default=5e-3)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]  # pneumo_solver_ui/
    model = _import_model(root, args.model)

    params_path = root / args.params
    suite_path = root / args.suite

    params = _load_json(params_path)
    suite_all = _load_json(suite_path)
    suite = _iter_enabled_suite(suite_all)

    if args.limit and args.limit > 0:
        suite = suite[: args.limit]

    rows: List[Dict[str, Any]] = []
    any_fail = False

    for i, test in enumerate(suite):
        name = _safe_name(test, i)
        dt = float(test.get("dt", args.dt_min))
        t_end = float(test.get("t_end", args.t_end_cap))

        # Ограничиваем время (быстро) и шаг (не мельчим, иначе будет медленно).
        if args.t_end_cap and args.t_end_cap > 0:
            t_end = min(t_end, float(args.t_end_cap))
        dt = max(dt, float(args.dt_min))

        try:
            df_main, *_ = model.simulate(params, test, dt=dt, t_end=t_end, record_full=False)
            met = _metrics_from_df(df_main)
            row = {
                "idx": i,
                "test": name,
                "dt": dt,
                "t_end": t_end,
                **met,
            }
            row["fail_rel"] = bool(met["max_rel_err_E"] > float(args.rel_th) or abs(met["end_rel_err_E"]) > float(args.rel_th))
            row["fail_pdv"] = bool(met["max_pdv_err_W"] > float(args.pdv_th))
            row["FAIL"] = bool(row["fail_rel"] or row["fail_pdv"])
            any_fail = any_fail or bool(row["FAIL"])
            rows.append(row)
        except Exception as e:
            rows.append(
                {
                    "idx": i,
                    "test": name,
                    "dt": dt,
                    "t_end": t_end,
                    "ERROR": repr(e),
                    "FAIL": True,
                }
            )
            any_fail = True

    df = pd.DataFrame(rows)
    if not df.empty:
        # Сортируем по проблемности
        sort_cols = [c for c in ("FAIL", "max_rel_err_E", "max_abs_err_E_J", "max_pdv_err_W") if c in df.columns]
        if sort_cols:
            df = df.sort_values(by=sort_cols, ascending=[False] + [False] * (len(sort_cols) - 1))

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"mech_energy_regression_{ts}.json"
    md_path = out_dir / f"mech_energy_regression_{ts}.md"
    last_json = out_dir / "mech_energy_regression_LAST.json"
    last_md = out_dir / "mech_energy_regression_LAST.md"

    # JSON
    payload = {
        "generated_at": ts,
        "model": args.model,
        "params": args.params,
        "suite": args.suite,
        "t_end_cap": args.t_end_cap,
        "dt_min": args.dt_min,
        "rel_th": args.rel_th,
        "pdv_th": args.pdv_th,
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    last_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    lines = []
    lines.append("# Mech Energy Regression Report")
    lines.append("")
    lines.append(f"- generated_at: `{ts}`")
    lines.append(f"- model: `{args.model}`")
    lines.append(f"- params: `{args.params}`")
    lines.append(f"- suite: `{args.suite}`")
    lines.append(f"- t_end_cap: `{args.t_end_cap}` s, dt_min: `{args.dt_min}` s")
    lines.append(f"- thresholds: rel_th={args.rel_th}, pdv_th={args.pdv_th} W")
    lines.append("")
    if df.empty:
        lines.append("_No tests found in suite._")
    else:
        show_cols = [c for c in ["test", "dt", "t_end", "max_rel_err_E", "end_rel_err_E", "max_abs_err_E_J", "max_pdv_err_W", "end_pdv_work_err_J", "FAIL"] if c in df.columns]
        lines.append(df[show_cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Notes")
    lines.append("- `max_rel_err_E` and `end_rel_err_E` относятся к проверке баланса механической энергии.")
    lines.append("- `max_pdv_err_W` — проверка p·dV (gauge) против F*ṡ по цилиндрам.")
    lines.append("- Для строгого режима используйте `--strict` (rc=2 при провале порогов).")
    md = "\n".join(lines) + "\n"
    md_path.write_text(md, encoding="utf-8")
    last_md.write_text(md, encoding="utf-8")

    print(f"[mech_energy_regression_report] wrote: {md_path.name}, {json_path.name} in {out_dir}")
    if not df.empty:
        worst = df.iloc[0].to_dict()
        print("[mech_energy_regression_report] worst:", worst)

    if args.strict and any_fail:
        print("[mech_energy_regression_report] FAIL (strict)")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
