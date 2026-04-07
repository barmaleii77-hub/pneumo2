# -*- coding: utf-8 -*-
"""pipeline_npz_influence_staged_refine_v1.py

Пост-пайплайн: staged refine на основе param_staging_influence.

Идея:
- autopilot/v18/v19 даёт "глобально" хорошую точку и набор артефактов;
- далее мы делаем короткую серию локальных fit прогонов,
  постепенно увеличивая число оптимизируемых параметров (cumulative ranges):
    stage0 -> stage1 -> ... -> stageN

Плюсы:
- устойчивее к плохой обусловленности и корреляциям;
- проще отладить по стадиям;
- согласуется с физическими отчётами System Influence и FIM.

Вход:
  --run_dir: папка RUN_...
  --stage_dir: (опц.) где лежит stages_influence.json и fit_ranges_stage_XX.json
  --max_stages: ограничить число стадий (0 = все)
  --global_init: none|surrogate|de (см. fit_worker_v3_suite_identify)
  --seed: seed

Выход:
  run_dir/influence_staged_refine/stage_XX/*
  run_dir/influence_staged_refine/REFINE_SUMMARY.md

Важно:
- скрипт не трогает исходные файлы в run_dir, всё пишет в подпапку.

"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _save_text(txt: str, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def _run(cmd: List[str], cwd: Path) -> None:
    print("\n>>>", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _detect_wrapper_meta(run_dir: Path) -> Dict[str, Any]:
    for name in ["AUTOPILOT_V20_WRAPPER.json", "AUTOPILOT_V19_WRAPPER.json"]:
        p = run_dir / name
        if p.exists():
            try:
                obj = _load_json(p)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
    return {}


def main() -> None:
    ap = argparse.ArgumentParser(description="Influence staged refine (post-run)")
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--stage_dir", default="", help="по умолчанию run_dir/param_staging_influence")
    ap.add_argument("--max_stages", type=int, default=0)
    ap.add_argument("--global_init", default="surrogate", choices=["none", "surrogate", "de"])
    ap.add_argument("--seed", type=int, default=123)

    args = ap.parse_args()

    project_root = Path(".")
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"run_dir not found: {run_dir}")

    meta = _detect_wrapper_meta(run_dir)
    model = str(meta.get("model", "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"))
    worker = str(meta.get("worker", "opt_worker_v3_margins_energy.py"))
    suite_json = str(meta.get("suite_json", "default_suite.json"))
    osc_dir = str(meta.get("osc_dir", ""))
    use_smoothing = bool(meta.get("use_smoothing_defaults", False))

    if not osc_dir:
        raise SystemExit("wrapper meta not found or osc_dir missing. Provide AUTOPILOT_V19/20_WRAPPER.json in run_dir.")

    mapping_json = run_dir / "mapping_final.json"
    if not mapping_json.exists():
        raise SystemExit(f"mapping_final.json not found in run_dir: {run_dir}")

    # stage dir
    stage_dir = Path(args.stage_dir).resolve() if str(args.stage_dir).strip() else (run_dir / "param_staging_influence")
    stages_plan = stage_dir / "stages_influence.json"
    if not stages_plan.exists():
        raise SystemExit(
            f"stages_influence.json not found: {stages_plan}. "
            f"Сначала запустите param_staging_v3_influence (или autopilot v20)."
        )

    plan = _load_json(stages_plan)
    stages = plan.get("stages", [])
    if not isinstance(stages, list) or not stages:
        raise SystemExit("stages_influence.json has no stages")

    n_stages = len(stages)
    if int(args.max_stages) > 0:
        n_stages = min(n_stages, int(args.max_stages))

    out_root = run_dir / "influence_staged_refine"
    out_root.mkdir(parents=True, exist_ok=True)

    base_candidates = [
        run_dir / "tradeoff_selected_base.json",
        run_dir / "epsilon_tradeoff" / "epsilon_selected_base_robust.json",
        run_dir / "epsilon_tradeoff" / "epsilon_selected_base.json",
        run_dir / "pareto_tradeoff" / "pareto_selected_base.json",
        run_dir / "fitted_base_final.json",
    ]
    cur_base = None
    for c in base_candidates:
        if c.exists():
            cur_base = c
            break
    if cur_base is None:
        raise SystemExit("No base json found in run_dir (tradeoff_selected_base / fitted_base_final)")

    md: List[str] = []
    md.append("# Influence staged refine\n")
    md.append(f"run_dir: `{run_dir}`\n")
    md.append("## Inputs\n")
    md.append(f"- model: `{model}`")
    md.append(f"- worker: `{worker}`")
    md.append(f"- suite_json: `{suite_json}`")
    md.append(f"- osc_dir: `{osc_dir}`")
    md.append(f"- mapping_json: `{mapping_json.name}`")
    md.append(f"- stage_dir: `{stage_dir}`")
    md.append(f"- global_init: `{args.global_init}`")
    md.append("")

    for si in range(n_stages):
        stage_ranges = stage_dir / f"fit_ranges_stage_{si:02d}.json"
        if not stage_ranges.exists():
            raise SystemExit(f"missing {stage_ranges}")

        out_dir = out_root / f"stage_{si:02d}"
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--suite_json",
            str(suite_json),
            "--osc_dir",
            str(osc_dir),
            "--base_json",
            str(cur_base),
            "--fit_ranges_json",
            str(stage_ranges),
            "--mapping_json",
            str(mapping_json),
            "--out_json",
            str(out_dir / "fitted_base.json"),
            "--report_json",
            str(out_dir / "fit_report.json"),
            "--seed",
            str(int(args.seed) + si),
            "--max_nfev",
            "200",
        ]
        if use_smoothing:
            cmd.append("--use_smoothing_defaults")

        if args.global_init == "surrogate":
            cmd += ["--global_init", "surrogate", "--surrogate_init", "24", "--surrogate_iters", "6", "--surrogate_batch", "2"]
        elif args.global_init == "de":
            cmd += ["--global_init", "de", "--de_maxiter", "20", "--de_popsize", "10"]

        t0 = time.time()
        _run(cmd, cwd=project_root)
        dt = time.time() - t0

        cur_base = out_dir / "fitted_base.json"
        md.append(f"## Stage {si:02d}\n")
        md.append(f"- ranges: `{stage_ranges.name}`")
        md.append(f"- out_dir: `{out_dir.relative_to(run_dir)}`")
        md.append(f"- fitted_base: `{cur_base.relative_to(run_dir)}`")
        md.append(f"- wall_time_sec: `{dt:.1f}`")
        md.append("")

    _save_text("\n".join(md), out_root / "REFINE_SUMMARY.md")
    print(f"[OK] influence staged refine done: {out_root}")


if __name__ == "__main__":
    main()
