# -*- coding: utf-8 -*-
"""
pipeline_npz_pareto_tradeoff_v2.py

v2: ускорение и устойчивость для multiobjective sweep:
- параллельная оценка точек (n_jobs > 1),
- ранняя остановка по hypervolume (HV) при стагнации,
- межплатформенный resume на уровне точек.

Смысл:
- weighted-sum sweep (через post-multiplier weights групп сигналов) остаётся быстрым
  способом получить компромиссное решение, но теперь он масштабируется по CPU и
  может останавливаться раньше, если прирост фронта стал "маленьким".

См. также:
- hv_early_stop_v1.py
- mo_metrics_v1.py (HV+Pareto)

Запуск:
python calibration/pipeline_npz_pareto_tradeoff_v2.py --osc_dir <OSC_DIR> --signals_csv <signals.csv> --out_dir <OUT_DIR> --n_jobs 4 --hv_stop

"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from hv_early_stop_v1 import HVStopState, update_hv_stop
from mo_metrics_v1 import pareto_nondominated_2d, hypervolume_2d_min, knee_point_distance_to_line_2d

# reuse helpers from v1
from pipeline_npz_pareto_tradeoff_v1 import (
    _load_json, _save_json, _save_text, _should_stop,
    ensure_sig_groups, compute_group_rmse_unbiased
)


def _interleave_indices(n: int) -> List[int]:
    """Order points to cover extremes early: 0, n-1, 1, n-2, ..."""
    out: List[int] = []
    i, j = 0, n - 1
    while i <= j:
        if i == j:
            out.append(i)
            break
        out.append(i)
        out.append(j)
        i += 1
        j -= 1
    return out


def _point_spec(
    project_root: Path,
    osc_dir: Path,
    mapping_json: Path,
    args: argparse.Namespace,
    i: int,
    lam: float,
) -> Dict[str, Any]:
    gA = float(10.0 ** float(lam))
    gB = float(10.0 ** float(-lam))
    run_dir = Path(args.out_dir) / f"pareto_run_{i+1:02d}_lam_{lam:+.3f}"
    return {
        "idx": int(i + 1),
        "lambda": float(lam),
        "gainA": float(gA),
        "gainB": float(gB),
        "run_dir": str(run_dir),
        # paths
        "project_root": str(project_root),
        "osc_dir": str(osc_dir),
        "mapping_json": str(mapping_json),
        # config
        "model": str(args.model),
        "worker": str(args.worker),
        "suite_json": str(args.suite_json),
        "base_json": str(args.base_json),
        "fit_ranges_json": str(args.fit_ranges_json),
        "auto_scale": str(args.auto_scale),
        "loss": str(args.loss),
        "f_scale": float(args.f_scale),
        "n_init": int(args.n_init),
        "n_best": int(args.n_best),
        "max_nfev": int(args.max_nfev),
        "use_smoothing_defaults": bool(args.use_smoothing_defaults),
        "stop_file": str(args.stop_file) if str(args.stop_file) else "",
        "resume": bool(args.resume),
        "groupA": str(args.groupA),
        "groupB": str(args.groupB),
        # global init / block refine
        "global_init": str(args.global_init),
        "de_maxiter": int(args.de_maxiter),
        "de_popsize": int(args.de_popsize),
        "de_tol": float(args.de_tol),
        "de_polish": bool(args.de_polish),
        "block_refine": bool(args.block_refine),
        "block_corr_thr": float(args.block_corr_thr),
        "block_max_size": int(args.block_max_size),
        "block_sweeps": int(args.block_sweeps),
        "block_max_nfev": int(args.block_max_nfev),
        "block_polish_nfev": int(args.block_polish_nfev),
    }


def _eval_point_worker(spec: Dict[str, Any]) -> Dict[str, Any]:
    project_root = Path(spec["project_root"])
    run_dir = Path(spec["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)

    stop_file = Path(spec["stop_file"]) if spec.get("stop_file") else None
    if _should_stop(stop_file):
        return {"idx": spec["idx"], "lambda": spec["lambda"], "stopped": True, "run_dir": str(run_dir)}

    gw_json = run_dir / "group_weights.json"
    _save_json({str(spec["groupA"]): float(spec["gainA"]), str(spec["groupB"]): float(spec["gainB"])}, gw_json)

    out_base = run_dir / "fitted_base.json"
    rep_json = run_dir / "fit_report.json"
    det_json = run_dir / "fit_details.json"
    md_rep = run_dir / "report.md"
    sig_csv = run_dir / "signals.csv"

    if spec.get("resume") and rep_json.exists() and det_json.exists() and out_base.exists():
        pass
    else:
        cmd_fit = [
            sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
            "--model", str(project_root / spec["model"]),
            "--worker", str(project_root / spec["worker"]),
            "--suite_json", str(project_root / spec["suite_json"]),
            "--osc_dir", str(spec["osc_dir"]),
            "--base_json", str(project_root / spec["base_json"]),
            "--fit_ranges_json", str(project_root / spec["fit_ranges_json"]),
            "--mapping_json", str(spec["mapping_json"]),
            "--group_weights_json", str(gw_json),
            "--out_json", str(out_base),
            "--report_json", str(rep_json),
            "--details_json", str(det_json),
            "--auto_scale", str(spec["auto_scale"]),
            "--loss", str(spec["loss"]),
            "--f_scale", str(spec["f_scale"]),
            "--n_init", str(int(spec["n_init"])),
            "--n_best", str(int(spec["n_best"])),
            "--max_nfev", str(int(spec["max_nfev"])),
        ]
        if spec.get("use_smoothing_defaults"):
            cmd_fit.append("--use_smoothing_defaults")
        if stop_file is not None:
            cmd_fit += ["--stop_file", str(stop_file)]
        if str(spec.get("global_init", "none")).lower() == "de":
            cmd_fit += ["--global_init", "de",
                        "--de_maxiter", str(int(spec["de_maxiter"])),
                        "--de_popsize", str(int(spec["de_popsize"])),
                        "--de_tol", str(float(spec["de_tol"]))]
            if spec.get("de_polish"):
                cmd_fit.append("--de_polish")
        if spec.get("block_refine"):
            cmd_fit += ["--block_refine",
                        "--block_corr_thr", str(float(spec["block_corr_thr"])),
                        "--block_max_size", str(int(spec["block_max_size"])),
                        "--block_sweeps", str(int(spec["block_sweeps"])),
                        "--block_max_nfev", str(int(spec["block_max_nfev"])),
                        "--block_polish_nfev", str(int(spec["block_polish_nfev"]))]

        subprocess.run(cmd_fit, cwd=str(project_root), check=True)

        cmd_rep = [
            sys.executable, str(project_root / "calibration" / "report_from_details_v1.py"),
            "--fit_report", str(rep_json),
            "--fit_details", str(det_json),
            "--out_md", str(md_rep),
            "--out_signals_csv", str(sig_csv),
        ]
        subprocess.run(cmd_rep, cwd=str(project_root), check=True)

    objA_tr = compute_group_rmse_unbiased(det_json, str(spec["groupA"]), which="train")
    objB_tr = compute_group_rmse_unbiased(det_json, str(spec["groupB"]), which="train")
    objA_ho = compute_group_rmse_unbiased(det_json, str(spec["groupA"]), which="holdout")
    objB_ho = compute_group_rmse_unbiased(det_json, str(spec["groupB"]), which="holdout")

    return {
        "idx": int(spec["idx"]),
        "lambda": float(spec["lambda"]),
        "gainA": float(spec["gainA"]),
        "gainB": float(spec["gainB"]),
        "run_dir": str(run_dir),
        "objA_train": float(objA_tr),
        "objB_train": float(objB_tr),
        "objA_holdout": float(objA_ho),
        "objB_holdout": float(objB_ho),
        "stopped": False,
    }


def _plot(points: List[Dict[str, Any]], front: List[Dict[str, Any]], knee: Optional[Dict[str, Any]], objA: str, objB: str, out_png: Path):
    out_png.parent.mkdir(parents=True, exist_ok=True)
    xs = [p.get(objA, np.nan) for p in points]
    ys = [p.get(objB, np.nan) for p in points]
    plt.figure()
    plt.scatter(xs, ys, label="sweep", alpha=0.7)

    if front:
        xf = [p.get(objA, np.nan) for p in front]
        yf = [p.get(objB, np.nan) for p in front]
        plt.scatter(xf, yf, marker="x", label="pareto front")

    if knee is not None:
        plt.scatter([knee.get(objA, np.nan)], [knee.get(objB, np.nan)], marker="*", s=140, label="knee")

    plt.xlabel(objA)
    plt.ylabel(objB)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--signals_csv", required=True)
    ap.add_argument("--out_dir", required=True)

    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", default="default_suite.json")
    ap.add_argument("--base_json", default="default_base.json")
    ap.add_argument("--fit_ranges_json", default="default_ranges.json")

    ap.add_argument("--auto_scale", default="mad")
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    ap.add_argument("--n_init", type=int, default=24)
    ap.add_argument("--n_best", type=int, default=4)
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--max_nfev", type=int, default=220)

    ap.add_argument("--global_init", default="none", choices=["none", "de"])
    ap.add_argument("--de_maxiter", type=int, default=8)
    ap.add_argument("--de_popsize", type=int, default=10)
    ap.add_argument("--de_tol", type=float, default=0.01)
    ap.add_argument("--de_polish", action="store_true")

    ap.add_argument("--block_refine", action="store_true")
    ap.add_argument("--block_corr_thr", type=float, default=0.85)
    ap.add_argument("--block_max_size", type=int, default=6)
    ap.add_argument("--block_sweeps", type=int, default=2)
    ap.add_argument("--block_max_nfev", type=int, default=120)
    ap.add_argument("--block_polish_nfev", type=int, default=120)

    ap.add_argument("--groupA", default="pressure")
    ap.add_argument("--groupB", default="kinematics")
    ap.add_argument("--points", type=int, default=9)
    ap.add_argument("--log_gain_span", type=float, default=1.0)

    ap.add_argument("--n_jobs", type=int, default=1)
    ap.add_argument("--stop_file", default="")
    ap.add_argument("--resume", action="store_true")

    # HV early stop
    ap.add_argument("--hv_stop", action="store_true")
    ap.add_argument("--hv_min_rel_improv", type=float, default=0.005)
    ap.add_argument("--hv_patience", type=int, default=3)
    ap.add_argument("--hv_margin", type=float, default=0.05)

    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else None
    osc_dir = Path(args.osc_dir)

    # Ensure groups and make mapping from signals
    signals_grouped = ensure_sig_groups(Path(args.signals_csv), out_dir / "signals_with_groups.csv")
    mapping_json = out_dir / "mapping_from_signals.json"
    cmd_map = [
        sys.executable, str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
        "--signals_csv", str(signals_grouped),
        "--out_mapping", str(mapping_json),
        "--drop_missing",
        "--osc_dir", str(osc_dir),
    ]
    subprocess.run(cmd_map, cwd=str(project_root), check=True)

    n = max(3, int(args.points))
    span = float(args.log_gain_span)
    lambdas = np.linspace(-span, span, n).tolist()
    order = _interleave_indices(len(lambdas))

    specs: List[Dict[str, Any]] = []
    for idx_in_grid in order:
        lam = float(lambdas[idx_in_grid])
        specs.append(_point_spec(project_root, osc_dir, mapping_json, args, idx_in_grid, lam))

    points: List[Dict[str, Any]] = []
    hv_state = HVStopState(hv_history=[])

    n_jobs = max(1, int(args.n_jobs))
    # evaluate in waves for HV stop
    cursor = 0
    while cursor < len(specs):
        if _should_stop(stop_file):
            _save_text("STOPPED by stop_file\n", out_dir / "STOPPED.txt")
            break

        batch = specs[cursor: cursor + n_jobs]
        cursor += n_jobs

        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            futs = [ex.submit(_eval_point_worker, s) for s in batch]
            for fut in as_completed(futs):
                p = fut.result()
                points.append(p)

        # check HV stop on current points
        use_holdout = any(np.isfinite(p.get("objA_holdout", np.nan)) and np.isfinite(p.get("objB_holdout", np.nan)) for p in points)
        objA = "objA_holdout" if use_holdout else "objA_train"
        objB = "objB_holdout" if use_holdout else "objB_train"

        front = pareto_nondominated_2d(points, objA, objB)
        if args.hv_stop and len(front) >= 2:
            amax = float(np.nanmax([float(p[objA]) for p in front]))
            bmax = float(np.nanmax([float(p[objB]) for p in front]))
            refA = amax * (1.0 + float(args.hv_margin))
            refB = bmax * (1.0 + float(args.hv_margin))
            hv = hypervolume_2d_min(front, objA, objB, refA=refA, refB=refB)
            if update_hv_stop(hv_state, hv, min_rel_improv=float(args.hv_min_rel_improv), patience=int(args.hv_patience)):
                _save_text("EARLY_STOP by HV stagnation\n", out_dir / "EARLY_STOP_HV.txt")
                break

    # finalize
    use_holdout = any(np.isfinite(p.get("objA_holdout", np.nan)) and np.isfinite(p.get("objB_holdout", np.nan)) for p in points)
    objA = "objA_holdout" if use_holdout else "objA_train"
    objB = "objB_holdout" if use_holdout else "objB_train"

    front = pareto_nondominated_2d(points, objA, objB)
    knee = knee_point_distance_to_line_2d(front, objA, objB) if front else None

    _save_json(points, out_dir / "pareto_points.json")
    pd.DataFrame(points).to_csv(out_dir / "pareto_points.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(front).to_csv(out_dir / "pareto_front.csv", index=False, encoding="utf-8-sig")
    _plot(points, front, knee, objA, objB, out_dir / "pareto_front.png")

    if knee is not None:
        # copy base
        try:
            src = Path(knee["run_dir"]) / "fitted_base.json"
            if src.exists():
                (out_dir / "pareto_selected_base.json").write_bytes(src.read_bytes())
        except Exception:
            pass

    rep_md = f"# Pareto sweep v2\n\n- objectives: **{objA}**, **{objB}**\n- points: {len(points)}\n- front: {len(front)}\n- hv_stop: {bool(args.hv_stop)}\n- hv_history: {hv_state.hv_history}\n"
    _save_text(rep_md, out_dir / "pareto_report.md")
    print("DONE:", out_dir)


if __name__ == "__main__":
    main()
