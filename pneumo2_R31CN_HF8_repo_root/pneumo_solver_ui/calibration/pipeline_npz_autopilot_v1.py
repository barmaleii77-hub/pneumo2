# -*- coding: utf-8 -*-
"""
pipeline_npz_autopilot_v1.py

Автопилот калибровки по NPZ (one-command):

1) Итеративная калибровка:
   - signals.csv (если есть) или bootstrap из NPZ
   - fit -> report -> refine signals
   - повторить N итераций

2) После финала:
   - построить observables.json из FINAL_SIGNALS.csv
   - (опционально) прогнать OED/FIM на базе найденных параметров
   - сгенерировать action_plan.md (диагностика результатов)

Опционально:
- profile likelihood (дорого) — оставлено как отдельный шаг, чтобы автопилот
  не был слишком тяжёлым по умолчанию.

Запуск:
python calibration/pipeline_npz_autopilot_v1.py --osc_dir <...>

Выход:
calibration_runs/RUN_..._autopilot/
  iterative/ (iter0/iter1/...)
  FINAL_SIGNALS.csv
  mapping_final.json
  fit_report_final.json
  fit_details_final.json
  fitted_base_final.json
  observables_from_signals.json
  (optional) oed_report.json
  action_plan.md
  AUTOPILOT_SUMMARY.md
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def _run(cmd: List[str], cwd: Path):
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _find_last_iter_dir(iterative_dir: Path) -> Path:
    iters = [p for p in iterative_dir.iterdir() if p.is_dir() and p.name.startswith("iter")]
    if not iters:
        raise RuntimeError(f"No iter* folders in {iterative_dir}")
    iters_sorted = sorted(iters, key=lambda p: int(p.name.replace("iter", "")))
    return iters_sorted[-1]


def _signals_to_observables(signals_csv: Path, out_json: Path, weight_col: str = "w_raw") -> None:
    import pandas as pd
    df = pd.read_csv(signals_csv, encoding="utf-8-sig")
    if "enabled" in df.columns:
        df = df[df["enabled"].astype(int) == 1].copy()
    if weight_col not in df.columns:
        # fallback to any weight-like columns
        for c in ["weight", "w", "w_raw_med"]:
            if c in df.columns:
                weight_col = c
                break
    obs = []
    for _, r in df.iterrows():
        mk = str(r.get("model_key", "")).strip()
        if not mk:
            continue
        w = float(r.get(weight_col, 1.0))
        obs.append({"model_key": mk, "weight": w})
    _save_json(obs, out_json)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", default="default_suite.json")
    ap.add_argument("--base_json", default="default_base.json")
    ap.add_argument("--fit_ranges_json", default="default_ranges.json")
    ap.add_argument("--signals_csv", default="auto", help="auto|path. Если auto — ищем osc_dir/signals.csv или последний calibration_runs/*/signals.csv")
    ap.add_argument("--iters", type=int, default=2)

    ap.add_argument("--auto_scale", default="mad", help="none|mad|std|range")
    ap.add_argument("--use_smoothing_defaults", action="store_true")
    ap.add_argument("--holdout_frac", type=float, default=0.2)
    ap.add_argument("--holdout_seed", type=int, default=1)

    ap.add_argument("--n_init", type=int, default=32)
    ap.add_argument("--n_best", type=int, default=6)
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)

    ap.add_argument("--run_oed", action="store_true", help="После финала запустить OED/FIM")
    ap.add_argument("--oed_sample_stride", type=int, default=8)

    ap.add_argument("--out_dir", default="")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    osc_dir = Path(args.osc_dir)

    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")

    # prepare out_dir
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_dir = project_root / "calibration_runs" / f"RUN_{ts}_autopilot"
    out_dir.mkdir(parents=True, exist_ok=True)

    iterative_dir = out_dir / "iterative"
    iterative_dir.mkdir(parents=True, exist_ok=True)

    # 1) iterative pipeline
    cmd_iter = [
        sys.executable, str(project_root / "calibration" / "pipeline_npz_iterative_signals_v1.py"),
        "--osc_dir", str(osc_dir),
        "--model", str(args.model),
        "--worker", str(args.worker),
        "--suite_json", str(args.suite_json),
        "--base_json", str(args.base_json),
        "--fit_ranges_json", str(args.fit_ranges_json),
        "--signals_csv", str(args.signals_csv),
        "--iters", str(int(args.iters)),
        "--auto_scale", str(args.auto_scale),
        "--n_init", str(int(args.n_init)),
        "--n_best", str(int(args.n_best)),
        "--loss", str(args.loss),
        "--f_scale", str(float(args.f_scale)),
        "--holdout_frac", str(float(args.holdout_frac)),
        "--holdout_seed", str(int(args.holdout_seed)),
        "--out_dir", str(iterative_dir),
    ]
    if args.use_smoothing_defaults:
        cmd_iter.append("--use_smoothing_defaults")
    _run(cmd_iter, cwd=project_root)

    # locate final iteration artifacts
    last_iter = _find_last_iter_dir(iterative_dir)
    final_fit_report = last_iter / "fit_report.json"
    final_fit_details = last_iter / "fit_details.json"
    final_fit_params = last_iter / "fitted_base.json"
    final_mapping = last_iter / "mapping.json"
    final_signals = iterative_dir / "FINAL_SIGNALS.csv"
    if not final_signals.exists():
        # fallback: last iter refined signals
        final_signals = last_iter / "signals_refined.csv"

    # copy pointers (not duplicating large data)
    for src, dst in [
        (final_fit_report, out_dir / "fit_report_final.json"),
        (final_fit_details, out_dir / "fit_details_final.json"),
        (final_fit_params, out_dir / "fitted_base_final.json"),
        (final_mapping, out_dir / "mapping_final.json"),
        (final_signals, out_dir / "FINAL_SIGNALS.csv"),
    ]:
        if src.exists():
            out_dir.joinpath(dst.name).write_bytes(src.read_bytes())

    # 2) build observables from signals
    obs_json = out_dir / "observables_from_signals.json"
    _signals_to_observables(out_dir / "FINAL_SIGNALS.csv", obs_json)

    # 3) run OED
    oed_report = out_dir / "oed_report.json"
    if args.run_oed:
        cmd_oed = [
            sys.executable, str(project_root / "calibration" / "oed_worker_v1_fim.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--base_json", str(out_dir / "fitted_base_final.json"),
            "--fit_ranges_json", str(project_root / args.fit_ranges_json),
            "--observables_json", str(obs_json),
            "--suite_json", str(project_root / args.suite_json),
            "--sample_stride", str(int(args.oed_sample_stride)),
            "--report_json", str(oed_report),
        ]
        if args.use_smoothing_defaults:
            cmd_oed.append("--use_smoothing_defaults")
        _run(cmd_oed, cwd=project_root)

    # 4) diagnose + action plan
    cmd_diag = [
        sys.executable, str(project_root / "calibration" / "diagnose_fit_v1.py"),
        "--fit_report", str(out_dir / "fit_report_final.json"),
        "--fit_details", str(out_dir / "fit_details_final.json"),
        "--fitted_json", str(out_dir / "fitted_base_final.json"),
        "--fit_ranges_json", str(project_root / args.fit_ranges_json),
        "--out_md", str(out_dir / "action_plan.md"),
        "--out_json", str(out_dir / "action_plan.json"),
    ]
    if args.run_oed and oed_report.exists():
        cmd_diag += ["--oed_report", str(oed_report)]
    _run(cmd_diag, cwd=project_root)

    # summary
    summary = []
    summary.append("# Autopilot summary\n")
    summary.append(f"- osc_dir: `{osc_dir}`")
    summary.append(f"- out_dir: `{out_dir}`\n")
    summary.append("## Outputs\n")
    summary.append(f"- FINAL_SIGNALS.csv: `{(out_dir / 'FINAL_SIGNALS.csv').name}`")
    summary.append(f"- mapping_final.json: `{(out_dir / 'mapping_final.json').name}`")
    summary.append(f"- fit_report_final.json: `{(out_dir / 'fit_report_final.json').name}`")
    summary.append(f"- action_plan.md: `{(out_dir / 'action_plan.md').name}`")
    if args.run_oed:
        summary.append(f"- oed_report.json: `{(out_dir / 'oed_report.json').name}`")
    summary.append("\n## Next\n")
    summary.append("1) Открой action_plan.md и посмотри: параметры у границ / корреляции / плохие сигналы.")
    summary.append("2) Если нужно — запусти profile likelihood по параметрам из action_plan.")
    _save_text("\n".join(summary), out_dir / "AUTOPILOT_SUMMARY.md")

    print("\nDONE. Autopilot outputs in:", out_dir)


if __name__ == "__main__":
    main()
