# -*- coding: utf-8 -*-
"""pipeline_npz_smooth_continuation_v1.py

Post-fit "smooth-to-sharp" continuation (homotopy) для калибровки по NPZ.

Контекст проекта:
- Модель `*_patched_smooth_all.py` содержит набор параметров сглаживания:
    smooth_eps_* и k_smooth_valves, а также флаги smooth_*
- При калибровке (особенно при большом числе параметров) даже сглаженная модель
  может иметь сложный ландшафт (локальные минимумы/плохая обусловленность).
- Инженерный подход: решить последовательность задач от более гладкой к менее
  гладкой, используя warm-start (решение предыдущего шага) — это классический
  continuation/homotopy приём.

Вход:
- start_base_json: базовые параметры (обычно fitted_base.json из iterative пайплайна)
- signals_csv: список сигналов (обычно iterative/FINAL_SIGNALS.csv)
- osc_dir: папка с NPZ-осциллограммами

Выход (out_dir):
- step*/fit_report.json, step*/fit_details.json, step*/fitted_base.json
- fitted_base_final.json, fit_report_final.json, fit_details_final.json
- schedule.json, summary.json

Пример:
  python calibration/pipeline_npz_smooth_continuation_v1.py \
      --osc_dir osc_logs/RUN_... \
      --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py \
      --worker opt_worker_v3_margins_energy.py \
      --suite_json default_suite.json \
      --fit_ranges_json default_ranges.json \
      --signals_csv calibration_runs/RUN_.../iterative/FINAL_SIGNALS.csv \
      --start_base_json calibration_runs/RUN_.../fitted_base_final.json \
      --out_dir calibration_runs/RUN_.../smooth_continuation \
      --n_steps 3 --k_start 20 --k_end 80 --eps_mult_start 8 --eps_mult_end 1

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


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _should_stop(stop_file: Optional[Path]) -> bool:
    try:
        return stop_file is not None and stop_file.exists()
    except Exception:
        return False


def _run(cmd: List[str], cwd: Path) -> None:
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd))


def _merge_overrides(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in overrides.items():
        # meta keys
        if str(k) in ("label", "stage"):
            continue
        out[str(k)] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--fit_ranges_json", required=True)
    ap.add_argument("--signals_csv", required=True)
    ap.add_argument("--start_base_json", required=True)
    ap.add_argument("--out_dir", required=True)

    # schedule
    ap.add_argument("--schedule_json", default="", help="Если задан — используем готовое расписание overrides")
    ap.add_argument("--n_steps", type=int, default=3)
    ap.add_argument("--k_start", type=float, default=20.0)
    ap.add_argument("--k_end", type=float, default=80.0)
    ap.add_argument("--eps_mult_start", type=float, default=8.0)
    ap.add_argument("--eps_mult_end", type=float, default=1.0)

    # fit budgets (обычно меньше, чем основной iterative)
    ap.add_argument("--n_init", type=int, default=12)
    ap.add_argument("--n_best", type=int, default=3)
    ap.add_argument("--max_nfev", type=int, default=140)
    ap.add_argument("--meas_stride", type=int, default=1)

    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--auto_scale", default="mad")
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    ap.add_argument("--holdout_tests", default="", help="CSV names; used to keep metrics consistent")

    ap.add_argument("--stop_file", default="")
    ap.add_argument("--resume", action="store_true")

    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    osc_dir = Path(args.osc_dir)
    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else (out_dir / "STOP_SMOOTH_CONTINUATION.txt")

    # schedule
    if str(args.schedule_json).strip():
        sched = _load_json(Path(args.schedule_json))
        if not isinstance(sched, list) or not sched:
            raise SystemExit("schedule_json должен быть непустым list")
    else:
        # generate schedule
        from smoothing_schedule_v1 import make_smoothing_schedule  # same folder

        sched = make_smoothing_schedule(
            n_steps=int(args.n_steps),
            k_start=float(args.k_start),
            k_end=float(args.k_end),
            eps_mult_start=float(args.eps_mult_start),
            eps_mult_end=float(args.eps_mult_end),
            enable_all_flags=True,
            labels=True,
        )

    _save_json(sched, out_dir / "schedule.json")

    # mapping built from signals (refined) to avoid mismatch
    mapping_path = out_dir / "mapping.json"
    if (not args.resume) or (not mapping_path.exists()):
        cmd_map = [
            sys.executable, str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
            "--signals_csv", str(Path(args.signals_csv)),
            "--out_mapping", str(mapping_path),
            "--osc_dir", str(osc_dir),
            "--test_num", "1",
            "--drop_missing",
        ]
        _run(cmd_map, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / "STOPPED.txt").write_text("stopped before fit\n", encoding="utf-8")
        print("STOP requested before continuation fit")
        return

    # starting base
    base_cur = _load_json(Path(args.start_base_json))

    summary_steps = []
    t0 = time.time()

    for i, overrides in enumerate(sched):
        if _should_stop(stop_file):
            (out_dir / "STOPPED.txt").write_text("stopped\n", encoding="utf-8")
            print("STOP requested. Breaking continuation.")
            break

        label = str(overrides.get("label", f"step{i}"))
        step_dir = out_dir / f"step{i:02d}_{label}"
        step_dir.mkdir(parents=True, exist_ok=True)

        # resume step
        if args.resume and (step_dir / "fitted_base.json").exists() and (step_dir / "fit_report.json").exists():
            print(f"[resume] {step_dir.name}: skip")
            base_cur = _load_json(step_dir / "fitted_base.json")
            try:
                rep = _load_json(step_dir / "fit_report.json")
            except Exception:
                rep = {}
            summary_steps.append({
                "step": int(i),
                "label": label,
                "skipped": True,
                "best_sse": rep.get("best_sse", None),
            })
            continue

        base_step = _merge_overrides(base_cur, overrides)
        base_path = step_dir / "base_for_step.json"
        _save_json(base_step, base_path)

        cmd_fit = [
            sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--suite_json", str(project_root / args.suite_json),
            "--osc_dir", str(osc_dir),
            "--base_json", str(base_path),
            "--fit_ranges_json", str(project_root / args.fit_ranges_json),
            "--mapping_json", str(mapping_path),
            "--out_json", str(step_dir / "fitted_base.json"),
            "--report_json", str(step_dir / "fit_report.json"),
            "--details_json", str(step_dir / "fit_details.json"),
            "--n_init", str(int(args.n_init)),
            "--n_best", str(int(args.n_best)),
            "--max_nfev", str(int(args.max_nfev)),
            "--meas_stride", str(int(args.meas_stride)),
            "--loss", str(args.loss),
            "--f_scale", str(float(args.f_scale)),
            "--auto_scale", str(args.auto_scale),
            "--global_init", "none",
            "--stop_file", str(stop_file),
        ]
        if args.use_smoothing_defaults:
            cmd_fit.append("--use_smoothing_defaults")
        if str(args.holdout_tests).strip():
            cmd_fit += ["--holdout_tests", str(args.holdout_tests)]

        _run(cmd_fit, cwd=project_root)

        # update base
        base_cur = _load_json(step_dir / "fitted_base.json")

        rep = _load_json(step_dir / "fit_report.json")
        summary_steps.append({
            "step": int(i),
            "label": label,
            "k_smooth_valves": float(base_step.get("k_smooth_valves", float("nan"))),
            "eps_pos": float(base_step.get("smooth_eps_pos_m", float("nan"))),
            "best_sse": rep.get("best_sse", None),
            "best_rmse": rep.get("best_rmse", None),
            "nfev": rep.get("nfev", None),
        })

    # pick last completed step
    last_fit = None
    last_rep = None
    last_det = None
    # find last step with fitted_base
    step_dirs = sorted([p for p in out_dir.glob("step*_") if p.is_dir()])
    # the glob above is too strict; fallback to all dirs starting with step
    step_dirs = sorted([p for p in out_dir.iterdir() if p.is_dir() and p.name.startswith("step")])
    for p in reversed(step_dirs):
        if (p / "fitted_base.json").exists():
            last_fit = p / "fitted_base.json"
            last_rep = p / "fit_report.json"
            last_det = p / "fit_details.json"
            break

    if last_fit is not None:
        (out_dir / "fitted_base_final.json").write_bytes(last_fit.read_bytes())
    if last_rep is not None and last_rep.exists():
        (out_dir / "fit_report_final.json").write_bytes(last_rep.read_bytes())
    if last_det is not None and last_det.exists():
        (out_dir / "fit_details_final.json").write_bytes(last_det.read_bytes())

    summary = {
        "n_steps": int(len(sched)),
        "elapsed_sec": float(time.time() - t0),
        "start_base_json": str(args.start_base_json),
        "signals_csv": str(args.signals_csv),
        "mapping_json": str(mapping_path),
        "steps": summary_steps,
        "stopped": bool(_should_stop(stop_file) and (out_dir / "STOPPED.txt").exists()),
    }
    _save_json(summary, out_dir / "summary.json")
    print("DONE. Smooth continuation outputs in:", out_dir)


if __name__ == "__main__":
    main()
