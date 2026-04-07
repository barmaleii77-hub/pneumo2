# -*- coding: utf-8 -*-
"""
pipeline_npz_epsilon_constraint_v3.py

Epsilon-constraint sweep (bi-objective) with:
- parallel evaluation of epsilon points (n_jobs),
- HV early stop (optional),
- resume per epsilon point,
- endpoints estimation via group_weights_json:
    - primary-only endpoint (constraint gain=0)
    - constraint-only endpoint (primary gain=0)

This version is intentionally simpler than v2 (no adaptive insertion).
If you need adaptive epsilon grid -> use pipeline_npz_epsilon_constraint_v2.py.
v3 focuses on: speed (parallel) + robust baseline behaviour.

Objectives (min-min):
- primary_rmse (unbiased)
- constraint_rmse (unbiased)

Constraint enforced via penalty term using fit_worker --epsilon_constraints_json:
- constraint_rmse <= epsilon

"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from hv_early_stop_v1 import HVStopState, update_hv_stop
from mo_metrics_v1 import pareto_nondominated_2d, hypervolume_2d_min, knee_point_distance_to_line_2d

from pipeline_npz_pareto_tradeoff_v1 import (
    _save_json, _save_text, _should_stop,
    ensure_sig_groups, compute_group_rmse_unbiased
)


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _run(cmd: List[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _make_mapping(project_root: Path, osc_dir: Path, signals_csv: Path, out_dir: Path) -> Path:
    signals_grouped = ensure_sig_groups(signals_csv, out_dir / "signals_with_groups.csv")
    mapping_json = out_dir / "mapping_from_signals.json"
    cmd_map = [
        sys.executable, str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
        "--signals_csv", str(signals_grouped),
        "--out_mapping", str(mapping_json),
        "--drop_missing",
        "--osc_dir", str(osc_dir),
    ]
    _run(cmd_map, project_root)
    return mapping_json


def _fit_point(
    project_root: Path,
    osc_dir: Path,
    mapping_json: Path,
    args: argparse.Namespace,
    run_dir: Path,
    group_weights: Dict[str, float],
    epsilon_constraints: Optional[List[Dict[str, Any]]] = None,
    stop_file: Optional[Path] = None,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)

    gw_json = run_dir / "group_weights.json"
    _save_json(group_weights, gw_json)

    ec_json = None
    if epsilon_constraints is not None:
        ec_json = run_dir / "epsilon_constraints.json"
        _save_json(epsilon_constraints, ec_json)

    out_base = run_dir / "fitted_base.json"
    rep_json = run_dir / "fit_report.json"
    det_json = run_dir / "fit_details.json"

    if args.resume and out_base.exists() and rep_json.exists() and det_json.exists():
        return det_json

    cmd_fit = [
        sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
        "--model", str(project_root / args.model),
        "--worker", str(project_root / args.worker),
        "--suite_json", str(project_root / args.suite_json),
        "--osc_dir", str(osc_dir),
        "--base_json", str(project_root / args.base_json),
        "--fit_ranges_json", str(project_root / args.fit_ranges_json),
        "--mapping_json", str(mapping_json),
        "--group_weights_json", str(gw_json),
        "--out_json", str(out_base),
        "--report_json", str(rep_json),
        "--details_json", str(det_json),
        "--auto_scale", str(args.auto_scale),
        "--loss", str(args.loss),
        "--f_scale", str(float(args.f_scale)),
        "--n_init", str(int(args.n_init)),
        "--n_best", str(int(args.n_best)),
        "--max_nfev", str(int(args.max_nfev)),
    ]
    if args.use_smoothing_defaults:
        cmd_fit.append("--use_smoothing_defaults")
    if stop_file is not None:
        cmd_fit += ["--stop_file", str(stop_file)]
    if ec_json is not None:
        cmd_fit += ["--epsilon_constraints_json", str(ec_json)]

    _run(cmd_fit, project_root)
    return det_json


def _eval_eps_worker(spec: Dict[str, Any]) -> Dict[str, Any]:
    project_root = Path(spec["project_root"])
    osc_dir = Path(spec["osc_dir"])
    mapping_json = Path(spec["mapping_json"])
    run_dir = Path(spec["run_dir"])
    stop_file = Path(spec["stop_file"]) if spec.get("stop_file") else None

    if _should_stop(stop_file):
        return {"eps": spec["eps"], "stopped": True, "run_dir": str(run_dir)}

    args = spec["args_obj"]
    # group_weights primary only (constraint excluded from objective; enforced via penalty)
    group_weights = {spec["primary_group"]: 1.0, spec["constraint_group"]: 0.0}
    epsilon_constraints = [{
        "sig_group": str(spec["constraint_group"]),
        "epsilon": float(spec["eps"]),
        "penalty": float(spec["penalty"]),
        "smooth": str(spec.get("smooth", "softplus")),
        "beta": float(spec.get("beta", 10.0)),
    }]

    det_json = _fit_point(
        project_root=project_root,
        osc_dir=osc_dir,
        mapping_json=mapping_json,
        args=args,
        run_dir=run_dir,
        group_weights=group_weights,
        epsilon_constraints=epsilon_constraints,
        stop_file=stop_file,
    )

    rmse_p_tr = compute_group_rmse_unbiased(det_json, str(spec["primary_group"]), which="train")
    rmse_c_tr = compute_group_rmse_unbiased(det_json, str(spec["constraint_group"]), which="train")
    rmse_p_ho = compute_group_rmse_unbiased(det_json, str(spec["primary_group"]), which="holdout")
    rmse_c_ho = compute_group_rmse_unbiased(det_json, str(spec["constraint_group"]), which="holdout")

    use_holdout = math.isfinite(rmse_p_ho) and math.isfinite(rmse_c_ho)
    pkey = "primary_holdout" if use_holdout else "primary_train"
    ckey = "constraint_holdout" if use_holdout else "constraint_train"

    return {
        "eps": float(spec["eps"]),
        "run_dir": str(run_dir),
        "primary_train": float(rmse_p_tr),
        "constraint_train": float(rmse_c_tr),
        "primary_holdout": float(rmse_p_ho),
        "constraint_holdout": float(rmse_c_ho),
        "feasible_train": bool(rmse_c_tr <= float(spec["eps"]) + 1e-12) if math.isfinite(rmse_c_tr) else False,
        "feasible_holdout": bool(rmse_c_ho <= float(spec["eps"]) + 1e-12) if math.isfinite(rmse_c_ho) else False,
        "stopped": False,
        "primary_key": pkey,
        "constraint_key": ckey,
    }


def _plot(points: List[Dict[str, Any]], front: List[Dict[str, Any]], knee: Optional[Dict[str, Any]], objA: str, objB: str, out_png: Path):
    xs = [p.get(objA, np.nan) for p in points]
    ys = [p.get(objB, np.nan) for p in points]
    plt.figure()
    plt.scatter(xs, ys, alpha=0.7, label="eps points")
    if front:
        xf = [p.get(objA, np.nan) for p in front]
        yf = [p.get(objB, np.nan) for p in front]
        plt.scatter(xf, yf, marker="x", label="front")
    if knee:
        plt.scatter([knee.get(objA, np.nan)], [knee.get(objB, np.nan)], marker="*", s=140, label="knee")
    plt.grid(True, alpha=0.3)
    plt.xlabel(objA)
    plt.ylabel(objB)
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
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

    ap.add_argument("--primary_group", default="pressure")
    ap.add_argument("--constraint_group", default="kinematics")
    ap.add_argument("--points", type=int, default=9)

    ap.add_argument("--penalty", type=float, default=2000.0)
    ap.add_argument("--smooth", default="softplus", choices=["softplus", "hinge"])
    ap.add_argument("--beta", type=float, default=10.0)

    ap.add_argument("--auto_scale", default="mad")
    ap.add_argument("--use_smoothing_defaults", action="store_true")
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--n_init", type=int, default=24)
    ap.add_argument("--n_best", type=int, default=4)
    ap.add_argument("--max_nfev", type=int, default=220)

    ap.add_argument("--n_jobs", type=int, default=1)
    ap.add_argument("--stop_file", default="")
    ap.add_argument("--resume", action="store_true")

    ap.add_argument("--hv_stop", action="store_true")
    ap.add_argument("--hv_min_rel_improv", type=float, default=0.005)
    ap.add_argument("--hv_patience", type=int, default=3)
    ap.add_argument("--hv_margin", type=float, default=0.05)

    ap.add_argument("--eps_min_factor", type=float, default=0.98, help="epsilon_min = eps_min_factor * best_constraint_rmse")
    ap.add_argument("--eps_max_factor", type=float, default=1.02, help="epsilon_max = eps_max_factor * worst_constraint_rmse")

    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else None
    osc_dir = Path(args.osc_dir)

    mapping_json = _make_mapping(project_root, osc_dir, Path(args.signals_csv), out_dir)

    # endpoints
    ep_dir = out_dir / "endpoints"
    ep_dir.mkdir(parents=True, exist_ok=True)

    det_primary = _fit_point(project_root, osc_dir, mapping_json, args, ep_dir / "primary_only",
                             group_weights={str(args.primary_group): 1.0, str(args.constraint_group): 0.0},
                             epsilon_constraints=None, stop_file=stop_file)
    det_constraint = _fit_point(project_root, osc_dir, mapping_json, args, ep_dir / "constraint_only",
                                group_weights={str(args.primary_group): 0.0, str(args.constraint_group): 1.0},
                                epsilon_constraints=None, stop_file=stop_file)

    # compute eps range (prefer holdout if finite)
    c_prim = compute_group_rmse_unbiased(det_primary, str(args.constraint_group), which="holdout")
    c_cons = compute_group_rmse_unbiased(det_constraint, str(args.constraint_group), which="holdout")
    if not math.isfinite(c_prim):
        c_prim = compute_group_rmse_unbiased(det_primary, str(args.constraint_group), which="train")
    if not math.isfinite(c_cons):
        c_cons = compute_group_rmse_unbiased(det_constraint, str(args.constraint_group), which="train")

    if not (math.isfinite(c_prim) and math.isfinite(c_cons)):
        raise RuntimeError("Не удалось оценить constraint group RMSE на endpoints. Проверь signals/group names.")

    eps_min = float(args.eps_min_factor) * float(min(c_prim, c_cons))
    eps_max = float(args.eps_max_factor) * float(max(c_prim, c_cons))
    if eps_max <= eps_min:
        eps_max = eps_min * 1.05

    eps_list = np.linspace(eps_min, eps_max, max(3, int(args.points))).tolist()
    _save_json({"eps_min": eps_min, "eps_max": eps_max, "eps_list": eps_list}, out_dir / "epsilon_grid.json")

    # prepare point specs
    sweep_dir = out_dir / "sweep"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    specs: List[Dict[str, Any]] = []
    for i, eps in enumerate(eps_list):
        specs.append({
            "eps": float(eps),
            "run_dir": str(sweep_dir / f"eps_{i+1:02d}_{eps:.6g}".replace(".", "p")),
            "project_root": str(project_root),
            "osc_dir": str(osc_dir),
            "mapping_json": str(mapping_json),
            "primary_group": str(args.primary_group),
            "constraint_group": str(args.constraint_group),
            "penalty": float(args.penalty),
            "smooth": str(args.smooth),
            "beta": float(args.beta),
            "stop_file": str(stop_file) if stop_file is not None else "",
            "args_obj": args,  # picklable namespace for worker
        })

    points: List[Dict[str, Any]] = []
    hv_state = HVStopState(hv_history=[])
    n_jobs = max(1, int(args.n_jobs))

    cursor = 0
    while cursor < len(specs):
        if _should_stop(stop_file):
            _save_text("STOPPED by stop_file\n", out_dir / "STOPPED.txt")
            break

        batch = specs[cursor: cursor + n_jobs]
        cursor += n_jobs

        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            futs = [ex.submit(_eval_eps_worker, s) for s in batch]
            for fut in as_completed(futs):
                points.append(fut.result())

        # HV stop on current non-dominated points (min primary, min constraint)
        # choose holdout keys if present (all points have keys)
        objA = points[-1].get("primary_key", "primary_holdout")
        objB = points[-1].get("constraint_key", "constraint_holdout")

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

    # final front
    objA = points[-1].get("primary_key", "primary_holdout") if points else "primary_holdout"
    objB = points[-1].get("constraint_key", "constraint_holdout") if points else "constraint_holdout"
    front = pareto_nondominated_2d(points, objA, objB)
    knee = knee_point_distance_to_line_2d(front, objA, objB) if front else None

    pd.DataFrame(points).to_csv(out_dir / "epsilon_points.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(front).to_csv(out_dir / "epsilon_front.csv", index=False, encoding="utf-8-sig")
    _plot(points, front, knee, objA, objB, out_dir / "epsilon_front.png")

    if knee is not None:
        try:
            src = Path(knee["run_dir"]) / "fitted_base.json"
            if src.exists():
                (out_dir / "epsilon_selected_base.json").write_bytes(src.read_bytes())
        except Exception:
            pass

    _save_text(f"# Epsilon-constraint v3\n\nHV history: {hv_state.hv_history}\n", out_dir / "epsilon_report.md")
    print("DONE:", out_dir)


if __name__ == "__main__":
    main()
