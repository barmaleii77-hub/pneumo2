# -*- coding: utf-8 -*-
"""
pipeline_npz_epsilon_constraint_v1.py

Multi-objective калибровка через epsilon-constraint (ε-constraint) метод.

Задача:
- Есть конфликтующие группы сигналов (например, давления vs кинематика).
- Weighted-sum (веса) часто не покрывает "невыпуклые" участки Pareto-фронта.
- ε-constraint метод решает серию подзадач вида:
    minimize   f_A(x)
    subject to f_B(x) <= ε
  сканируя ε.

В этом проекте f_A/f_B считаются как RMSE по группе сигналов в "unbiased" шкале:
- сначала авто-нормировка по сигналу (MAD/STD/RANGE) -> weight_eff = w_raw/scale
- затем (опционально) group_gain умножает веса ПОСЛЕ auto_scale (для weighted-sum)
- unbiased метрики берутся без group_gain.

Ограничение реализовано через penalty-резидуал в fit_worker:
- добавляется дополнительный резидуал:
    r_eps = sqrt(penalty) * pos( RMSE_group - ε )
  где pos(z) = max(0,z) или smooth softplus.

Это НЕ строгий constrained-solver, но сохраняет структуру least_squares и хорошо
работает для инженерной калибровки с дорогой симуляцией.

Выход:
- epsilon_points.csv: все точки (включая endpoints)
- epsilon_front.csv: Pareto-недоминируемые точки
- epsilon_front.png: график
- epsilon_knee.json: выбранная knee-point (2D)
- epsilon_selected_base.json: base параметров для knee-point

"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def _should_stop(stop_file: Optional[Path]) -> bool:
    try:
        return stop_file is not None and stop_file.exists()
    except Exception:
        return False


def infer_sig_group(model_key: str, meas_col: str = "") -> str:
    s = f"{model_key}|{meas_col}".lower()

    # pressure
    if any(k in s for k in ["давлен", "pressure", "_pa", " pa", "bar", "кпа", "mpa"]):
        return "pressure"

    # kinematics / geometry
    if any(k in s for k in ["крен", "тангаж", "roll", "pitch", "yaw", "угол", "angle", "theta", "phi", "psi",
                            "высот", "height", "ход", "stroke", "z_", "x_", "y_", "скор", "vel", "acc"]):
        return "kinematics"

    # flow
    if any(k in s for k in ["расход", "flow", "q_"]):
        return "flow"

    return "default"


def ensure_sig_groups(signals_csv: Path, out_csv: Path) -> Path:
    df = pd.read_csv(signals_csv, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]

    if "sig_group" not in df.columns:
        mk = df.get("model_key", pd.Series([""] * len(df))).astype(str)
        mc = df.get("meas_col", pd.Series([""] * len(df))).astype(str)
        df["sig_group"] = [infer_sig_group(a, b) for a, b in zip(mk.tolist(), mc.tolist())]
    else:
        df["sig_group"] = df["sig_group"].astype(str).str.strip().replace({"": "default"}).fillna("default")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_csv


def compute_group_rmse_unbiased(details_json: Path, group_name: str, which: str = "holdout") -> float:
    """RMSE (unbiased) по группе: предпочтительно по sse_unb; fallback по sse/(gain^2)."""
    det = _load_json(details_json)
    df = pd.DataFrame(det.get("signals", []))
    if df.empty:
        return float("nan")
    if "sig_group" not in df.columns:
        return float("nan")

    if "group" in df.columns and which:
        if which == "train":
            df = df[df["group"] == "train"]
        elif which == "holdout":
            df = df[df["group"] != "train"]

    df = df[df["sig_group"].astype(str) == str(group_name)]
    if df.empty:
        return float("nan")

    n = float(pd.to_numeric(df.get("n", 0), errors="coerce").fillna(0.0).sum())
    if n <= 0.0:
        return float("nan")

    if "sse_unb" in df.columns:
        sse_u = float(pd.to_numeric(df["sse_unb"], errors="coerce").fillna(0.0).sum())
    else:
        # legacy fallback
        if "group_gain" not in df.columns:
            gg = pd.Series([1.0] * len(df))
        else:
            gg = pd.to_numeric(df["group_gain"], errors="coerce").fillna(1.0)
        gg = gg.replace(0.0, np.nan)
        sse = pd.to_numeric(df.get("sse", 0), errors="coerce").fillna(0.0)
        sse_u = float((sse / (gg ** 2)).fillna(0.0).sum())

    return float(math.sqrt(sse_u / max(1.0, n)))


def pareto_nondominated(points: List[Dict[str, Any]], objA: str, objB: str) -> List[Dict[str, Any]]:
    """Простой Pareto filter (минимизация objA/objB)."""
    pts = [p for p in points if np.isfinite(p.get(objA, np.nan)) and np.isfinite(p.get(objB, np.nan))]
    out = []
    for i, p in enumerate(pts):
        a, b = float(p[objA]), float(p[objB])
        dominated = False
        for j, q in enumerate(pts):
            if j == i:
                continue
            aq, bq = float(q[objA]), float(q[objB])
            if (aq <= a and bq <= b) and (aq < a or bq < b):
                dominated = True
                break
        if not dominated:
            out.append(p)
    out.sort(key=lambda x: float(x[objA]))
    return out


def knee_point_2d(front: List[Dict[str, Any]], objA: str, objB: str) -> Optional[Dict[str, Any]]:
    """Knee-point: max distance to line between extremes in normalized space."""
    if not front:
        return None
    xs = np.asarray([float(p[objA]) for p in front], dtype=float)
    ys = np.asarray([float(p[objB]) for p in front], dtype=float)
    # normalize
    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())
    dx = max(1e-12, x1 - x0)
    dy = max(1e-12, y1 - y0)
    xn = (xs - x0) / dx
    yn = (ys - y0) / dy
    # line between first and last in normalized space
    p0 = np.array([xn[0], yn[0]], dtype=float)
    p1 = np.array([xn[-1], yn[-1]], dtype=float)
    v = p1 - p0
    nv = np.linalg.norm(v)
    if nv < 1e-12:
        return front[len(front) // 2]
    v = v / nv
    # distance
    best_i = 0
    best_d = -1.0
    for i in range(len(front)):
        w = np.array([xn[i], yn[i]], dtype=float) - p0
        proj = float(np.dot(w, v))
        perp = w - proj * v
        d = float(np.linalg.norm(perp))
        if d > best_d:
            best_d = d
            best_i = i
    knee = dict(front[best_i])
    knee["knee_dist_norm"] = float(best_d)
    return knee


def hypervolume_2d(front: List[Dict[str, Any]], objA: str, objB: str, refA: float, refB: float) -> float:
    """Hypervolume for 2D minimization. ref must be worse than all points."""
    pts = [(float(p[objA]), float(p[objB])) for p in front if np.isfinite(p.get(objA, np.nan)) and np.isfinite(p.get(objB, np.nan))]
    if not pts:
        return 0.0
    pts.sort(key=lambda t: t[0])
    hv = 0.0
    cur_y = float(refB)
    for a, b in pts:
        b = float(b)
        if b >= cur_y:
            continue
        hv += max(0.0, float(refA) - float(a)) * max(0.0, cur_y - b)
        cur_y = b
    return float(hv)


def eps_tag(eps: float) -> str:
    """Стабильный тег для имени папки по значению epsilon."""
    s = f"{float(eps):.6g}"
    # safe-ish for paths on Windows
    s = s.replace(".", "p").replace("-", "m").replace("+", "p")
    return s


def _run(cmd: List[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


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

    # fit settings
    ap.add_argument("--n_init", type=int, default=24)
    ap.add_argument("--n_best", type=int, default=4)
    ap.add_argument("--max_nfev", type=int, default=220)
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)

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

    # epsilon settings
    ap.add_argument("--primary", default="pressure", help="Группа, которую минимизируем (f_A)")
    ap.add_argument("--constraint", default="kinematics", help="Группа, которую ограничиваем (f_B)")
    ap.add_argument("--points", type=int, default=9, help="Сколько epsilon-точек (включая endpoints)")
    ap.add_argument("--epsilon_space", default="auto", choices=["auto", "linear", "log"])
    ap.add_argument("--epsilon_penalty", type=float, default=2000.0)
    ap.add_argument("--epsilon_tol", type=float, default=0.02, help="Допуск по выполнению epsilon: B <= eps*(1+tol)")
    ap.add_argument("--max_retries", type=int, default=2, help="Сколько раз повышать penalty, если constraint не выполнен")
    ap.add_argument("--penalty_growth", type=float, default=5.0)

    # adaptive epsilon grid + bootstrap stability
    ap.add_argument("--adaptive", action="store_true", help="Адаптивно уплотнять epsilon-сетку по форме фронта (экономит прогоны)")
    ap.add_argument("--min_points", type=int, default=5, help="Стартовое число epsilon-точек (только sweep, без endpoints)")
    ap.add_argument("--max_points", type=int, default=0, help="Максимум epsilon-точек в sweep (0 -> использовать --points)")
    ap.add_argument("--min_gap_norm", type=float, default=0.18, help="Порог нормированной дистанции между соседними точками фронта для остановки адаптации")
    ap.add_argument("--bootstrap_reps", type=int, default=200, help="Сколько bootstrap-пересэмплирований тестов для оценки устойчивости (0 -> выключить)")
    ap.add_argument("--bootstrap_seed", type=int, default=0)

    ap.add_argument("--stop_file", default="")
    ap.add_argument("--resume", action="store_true")

    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    osc_dir = Path(args.osc_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else None

    # prepare grouped signals.csv
    sig_in = Path(args.signals_csv)
    sig_grouped = ensure_sig_groups(sig_in, out_dir / "signals_with_groups.csv")

    # mapping.json from signals
    mapping_json = out_dir / "mapping_from_signals.json"
    cmd_map = [
        sys.executable, str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
        "--signals_csv", str(sig_grouped),
        "--out_mapping", str(mapping_json),
        "--drop_missing",
    ]
    _run(cmd_map, cwd=project_root)

    if _should_stop(stop_file):
        _save_text("stopped before endpoints\n", out_dir / "STOPPED.txt")
        return

    # discover groups present
    df_sig = pd.read_csv(sig_grouped, encoding="utf-8-sig")
    groups_present = sorted(set(df_sig.get("sig_group", pd.Series(["default"])).astype(str).tolist()))
    if args.primary not in groups_present or args.constraint not in groups_present:
        # auto fallback
        if "pressure" in groups_present and "kinematics" in groups_present:
            primary = "pressure"
            constraint = "kinematics"
        elif len(groups_present) >= 2:
            primary, constraint = groups_present[0], groups_present[1]
        else:
            primary, constraint = groups_present[0] if groups_present else "default", "default"
    else:
        primary, constraint = str(args.primary), str(args.constraint)

    _save_json({"groups_present": groups_present, "primary": primary, "constraint": constraint}, out_dir / "groups_used.json")

    # group weights template: objective only on primary
    group_weights = {g: (1.0 if g == primary else 0.0) for g in groups_present}
    _save_json(group_weights, out_dir / "group_weights_primary_only.json")

    group_weights_B = {g: (1.0 if g == constraint else 0.0) for g in groups_present}
    _save_json(group_weights_B, out_dir / "group_weights_constraint_only.json")

    def run_fit(run_subdir: Path, base_json: Path, gw_json: Path, eps_json: Optional[Path]) -> Tuple[Path, Path, Path]:
        run_subdir.mkdir(parents=True, exist_ok=True)
        out_base = run_subdir / "fitted_base.json"
        rep_json = run_subdir / "fit_report.json"
        det_json = run_subdir / "fit_details.json"

        if args.resume and out_base.exists() and rep_json.exists() and det_json.exists():
            return out_base, rep_json, det_json

        cmd_fit = [
            sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--suite_json", str(project_root / args.suite_json),
            "--osc_dir", str(osc_dir),
            "--base_json", str(base_json),
            "--fit_ranges_json", str(project_root / args.fit_ranges_json),
            "--mapping_json", str(mapping_json),
            "--auto_scale", str(args.auto_scale),
            "--n_init", str(int(args.n_init)),
            "--n_best", str(int(args.n_best)),
            "--max_nfev", str(int(args.max_nfev)),
            "--loss", str(args.loss),
            "--f_scale", str(float(args.f_scale)),
            "--out_json", str(out_base),
            "--report_json", str(rep_json),
            "--details_json", str(det_json),
            "--group_weights_json", str(gw_json),
            "--global_init", str(args.global_init),
            "--de_maxiter", str(int(args.de_maxiter)),
            "--de_popsize", str(int(args.de_popsize)),
            "--de_tol", str(float(args.de_tol)),
            "--block_corr_thr", str(float(args.block_corr_thr)),
            "--block_max_size", str(int(args.block_max_size)),
            "--block_sweeps", str(int(args.block_sweeps)),
            "--block_max_nfev", str(int(args.block_max_nfev)),
            "--block_polish_nfev", str(int(args.block_polish_nfev)),
            "--stop_file", str(stop_file) if stop_file else "",
        ]
        if args.use_smoothing_defaults:
            cmd_fit.append("--use_smoothing_defaults")
        if args.de_polish:
            cmd_fit.append("--de_polish")
        if args.block_refine:
            cmd_fit.append("--block_refine")
        if eps_json is not None:
            cmd_fit.extend(["--epsilon_constraints_json", str(eps_json)])

        _run(cmd_fit, cwd=project_root)
        return out_base, rep_json, det_json

    # 1) endpoints
    endpoints_dir = out_dir / "endpoints"
    epA_dir = endpoints_dir / "primary_only"
    epB_dir = endpoints_dir / "constraint_only"

    gwA_json = out_dir / "group_weights_primary_only.json"
    gwB_json = out_dir / "group_weights_constraint_only.json"

    base0 = project_root / args.base_json

    outA, repA, detA = run_fit(epA_dir, base0, gwA_json, None)
    if _should_stop(stop_file):
        _save_text("stopped at endpoint A\n", out_dir / "STOPPED.txt")
        return

    outB, repB, detB = run_fit(epB_dir, base0, gwB_json, None)
    if _should_stop(stop_file):
        _save_text("stopped at endpoint B\n", out_dir / "STOPPED.txt")
        return

    # evaluate endpoints metrics
    A_train = compute_group_rmse_unbiased(detA, primary, which="train")
    B_train = compute_group_rmse_unbiased(detA, constraint, which="train")
    A_hold = compute_group_rmse_unbiased(detA, primary, which="holdout")
    B_hold = compute_group_rmse_unbiased(detA, constraint, which="holdout")

    A2_train = compute_group_rmse_unbiased(detB, primary, which="train")
    B2_train = compute_group_rmse_unbiased(detB, constraint, which="train")
    A2_hold = compute_group_rmse_unbiased(detB, primary, which="holdout")
    B2_hold = compute_group_rmse_unbiased(detB, constraint, which="holdout")

    # epsilon range based on constraint group best/worst
    B_best = float(B2_train)  # best B when optimizing B
    B_at_Aopt = float(B_train)  # B at A-only optimum
    if not np.isfinite(B_best) or not np.isfinite(B_at_Aopt):
        raise SystemExit("Не удалось вычислить RMSE по группам для endpoints. Проверь signals.csv и sig_group.")

    lo = min(B_best, B_at_Aopt)
    hi = max(B_best, B_at_Aopt)
    if hi <= 0:
        hi = lo + 1.0

    # points budget (sweep only; endpoints идут отдельными точками)
    pts_target = max(3, int(args.max_points) if int(args.max_points) > 0 else int(args.points))
    pts_init = max(3, min(int(args.min_points), int(pts_target)))

    space = str(args.epsilon_space).lower()
    if space == "auto":
        ratio = hi / max(1e-12, lo)
        space = "log" if ratio > 3.0 else "linear"

    def make_eps_list(npts: int) -> List[float]:
        if space == "log":
            lst = np.geomspace(max(1e-12, lo), max(1e-12, hi), num=int(npts)).tolist()
        else:
            lst = np.linspace(lo, hi, num=int(npts)).tolist()
        # uniq+sorted with mild quantization for stable folder names
        out = sorted({float(f"{float(e):.12g}") for e in lst})
        return [float(e) for e in out]

    eps_list = make_eps_list(int(pts_init))

    _save_json({
        "primary": primary,
        "constraint": constraint,
        "B_best_train": B_best,
        "B_at_Aopt_train": B_at_Aopt,
        "epsilon_space": space,
        "adaptive": bool(args.adaptive),
        "pts_init": int(pts_init),
        "pts_target": int(pts_target),
        "min_gap_norm": float(args.min_gap_norm),
        "eps_list": eps_list,
    }, out_dir / "epsilon_grid.json")

    points: List[Dict[str, Any]] = []

    # include endpoints as points too
    points.append({
        "kind": "endpoint_primary_only",
        "run_dir": str(epA_dir.name),
        "epsilon": float("nan"),
        "objA_train": float(A_train),
        "objB_train": float(B_train),
        "objA_holdout": float(A_hold),
        "objB_holdout": float(B_hold),
        "base_json": str(outA),
    })
    points.append({
        "kind": "endpoint_constraint_only",
        "run_dir": str(epB_dir.name),
        "epsilon": float("nan"),
        "objA_train": float(A2_train),
        "objB_train": float(B2_train),
        "objA_holdout": float(A2_hold),
        "objB_holdout": float(B2_hold),
        "base_json": str(outB),
    })

    # 2) epsilon sweep
    sweep_dir = out_dir / "sweep"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    prev_base = outB  # warm start from constraint-only optimum (feasible)
    for k, eps in enumerate(eps_list):
        if _should_stop(stop_file):
            _save_text("stopped at epsilon sweep\n", out_dir / "STOPPED.txt")
            break

        run_subdir = sweep_dir / f"eps_{eps_tag(eps)}"
        run_subdir.mkdir(parents=True, exist_ok=True)

        # write group weights and epsilon constraint config
        gw_json = run_subdir / "group_weights.json"
        _save_json(group_weights, gw_json)

        eps_cfg = {
            "constraints": [{
                "sig_group": constraint,
                "epsilon": float(eps),
                "penalty": float(args.epsilon_penalty),
                "smooth": "softplus",
                "beta": 50.0,
                "apply_to": "train",
            }]
        }
        eps_json = run_subdir / "epsilon_constraints.json"
        _save_json(eps_cfg, eps_json)

        # retries if constraint not satisfied
        pen = float(args.epsilon_penalty)
        best_out = None
        best_rep = None
        best_det = None

        for attempt in range(max(1, int(args.max_retries) + 1)):
            eps_cfg["constraints"][0]["penalty"] = float(pen)
            _save_json(eps_cfg, eps_json)

            out_base, rep_json, det_json = run_fit(run_subdir, prev_base, gw_json, eps_json)

            A_tr = compute_group_rmse_unbiased(det_json, primary, which="train")
            B_tr = compute_group_rmse_unbiased(det_json, constraint, which="train")
            A_ho = compute_group_rmse_unbiased(det_json, primary, which="holdout")
            B_ho = compute_group_rmse_unbiased(det_json, constraint, which="holdout")

            best_out, best_rep, best_det = out_base, rep_json, det_json

            if np.isfinite(B_tr) and B_tr <= float(eps) * (1.0 + float(args.epsilon_tol)):
                # ok
                break

            # increase penalty and retry
            pen *= float(args.penalty_growth)

        prev_base = best_out if best_out is not None else prev_base

        points.append({
            "kind": "epsilon",
            "run_dir": str(run_subdir.relative_to(out_dir)),
            "epsilon": float(eps),
            "epsilon_penalty_final": float(pen),
            "objA_train": float(A_tr),
            "objB_train": float(B_tr),
            "objA_holdout": float(A_ho),
            "objB_holdout": float(B_ho),
            "base_json": str(best_out) if best_out else "",
        })


    # --- adaptive refinement of epsilon grid (optional) ---
    if bool(args.adaptive):
        # collect unique epsilon points
        eps_done: Dict[float, Dict[str, Any]] = {}
        for pnt in points:
            if str(pnt.get("kind", "")).lower() != "epsilon":
                continue
            try:
                e = float(pnt.get("epsilon", float("nan")))
            except Exception:
                continue
            if not np.isfinite(e):
                continue
            e = float(f"{e:.12g}")
            eps_done[e] = pnt

        # adaptive loop: add points until pts_target or until gaps small
        iter_guard = 0
        while (len(eps_done) < int(pts_target)) and (iter_guard < 2000):
            iter_guard += 1
            if _should_stop(stop_file):
                _save_text("stopped during adaptive epsilon refinement\n", out_dir / "STOPPED.txt")
                break
            eps_sorted = sorted(eps_done.keys())
            if len(eps_sorted) < 2:
                break

            # objectives for gap metric: use train (always available) for exploration
            A_vals = np.asarray([float(eps_done[e].get("objA_train", np.nan)) for e in eps_sorted], dtype=float)
            B_vals = np.asarray([float(eps_done[e].get("objB_train", np.nan)) for e in eps_sorted], dtype=float)

            if not np.isfinite(A_vals).any() or not np.isfinite(B_vals).any():
                break

            A0, A1 = float(np.nanmin(A_vals)), float(np.nanmax(A_vals))
            B0, B1 = float(np.nanmin(B_vals)), float(np.nanmax(B_vals))
            dA = max(1e-12, A1 - A0)
            dB = max(1e-12, B1 - B0)

            # distances between neighbors (skip nan)
            dists = []
            for i in range(len(eps_sorted) - 1):
                a0, a1 = A_vals[i], A_vals[i + 1]
                b0, b1 = B_vals[i], B_vals[i + 1]
                if not (np.isfinite(a0) and np.isfinite(a1) and np.isfinite(b0) and np.isfinite(b1)):
                    dists.append(np.nan)
                    continue
                da = (a1 - a0) / dA
                db = (b1 - b0) / dB
                dists.append(float(math.sqrt(da * da + db * db)))

            if not np.isfinite(dists).any():
                break

            i_best = int(np.nanargmax(np.asarray(dists, dtype=float)))
            best_gap = float(np.asarray(dists, dtype=float)[i_best])
            if not np.isfinite(best_gap) or best_gap < float(args.min_gap_norm):
                break

            e0 = float(eps_sorted[i_best])
            e1 = float(eps_sorted[i_best + 1])
            if space == "log" and e0 > 0 and e1 > 0:
                new_eps = float(math.sqrt(e0 * e1))
            else:
                new_eps = float(0.5 * (e0 + e1))
            new_eps = float(f"{new_eps:.12g}")

            # already exists?
            if any(abs(new_eps - ee) <= 1e-12 * max(1.0, abs(ee)) for ee in eps_done.keys()):
                break

            # warm start: from tighter epsilon (e0)
            warm = Path(str(eps_done[e0].get("base_json", ""))).resolve()
            if not warm.exists():
                warm = Path(str(outB)).resolve()

            run_subdir = sweep_dir / f"eps_{eps_tag(new_eps)}"
            run_subdir.mkdir(parents=True, exist_ok=True)

            # write group weights and epsilon constraint config
            gw_json = run_subdir / "group_weights.json"
            _save_json(group_weights, gw_json)

            eps_cfg = {
                "constraints": [{
                    "sig_group": constraint,
                    "epsilon": float(new_eps),
                    "penalty": float(args.epsilon_penalty),
                    "smooth": "softplus",
                    "beta": 50.0,
                    "apply_to": "train",
                }]
            }
            eps_json = run_subdir / "epsilon_constraints.json"
            _save_json(eps_cfg, eps_json)

            pen = float(args.epsilon_penalty)
            best_out = None

            for attempt in range(max(1, int(args.max_retries) + 1)):
                eps_cfg["constraints"][0]["penalty"] = float(pen)
                _save_json(eps_cfg, eps_json)

                out_base, rep_json, det_json = run_fit(run_subdir, warm, gw_json, eps_json)

                A_tr = compute_group_rmse_unbiased(det_json, primary, which="train")
                B_tr = compute_group_rmse_unbiased(det_json, constraint, which="train")
                A_ho = compute_group_rmse_unbiased(det_json, primary, which="holdout")
                B_ho = compute_group_rmse_unbiased(det_json, constraint, which="holdout")

                best_out = out_base

                if np.isfinite(B_tr) and B_tr <= float(new_eps) * (1.0 + float(args.epsilon_tol)):
                    break
                pen *= float(args.penalty_growth)

            new_point = {
                "kind": "epsilon",
                "run_dir": str(run_subdir.relative_to(out_dir)),
                "epsilon": float(new_eps),
                "epsilon_penalty_final": float(pen),
                "objA_train": float(A_tr),
                "objB_train": float(B_tr),
                "objA_holdout": float(A_ho),
                "objB_holdout": float(B_ho),
                "base_json": str(best_out) if best_out else "",
                "adaptive_added": True,
                "adaptive_gap_norm": float(best_gap),
            }
            points.append(new_point)
            eps_done[new_eps] = new_point

        # update grid file with final eps list
        try:
            grid = _load_json(out_dir / "epsilon_grid.json")
        except Exception:
            grid = {}
        grid["eps_list_final"] = sorted([float(e) for e in eps_done.keys()])
        grid["pts_done"] = int(len(eps_done))
        _save_json(grid, out_dir / "epsilon_grid.json")

    # choose objectives on holdout if available
    use_holdout = any(np.isfinite(p.get("objA_holdout", np.nan)) and np.isfinite(p.get("objB_holdout", np.nan)) for p in points)
    objA = "objA_holdout" if use_holdout else "objA_train"
    objB = "objB_holdout" if use_holdout else "objB_train"

    front = pareto_nondominated(points, objA, objB)
    knee = knee_point_2d(front, objA, objB) if front else None

    # hypervolume (2D)
    refA = float(max([float(p.get(objA, np.nan)) for p in points if np.isfinite(p.get(objA, np.nan))] + [1.0]) * 1.05)
    refB = float(max([float(p.get(objB, np.nan)) for p in points if np.isfinite(p.get(objB, np.nan))] + [1.0]) * 1.05)
    hv = hypervolume_2d(front, objA, objB, refA=refA, refB=refB)

    # save tables
    df_points = pd.DataFrame(points)
    df_points.to_csv(out_dir / "epsilon_points.csv", index=False, encoding="utf-8-sig")

    df_front = pd.DataFrame(front)
    df_front.to_csv(out_dir / "epsilon_front.csv", index=False, encoding="utf-8-sig")

    if knee is not None:
        knee["objA_key"] = objA
        knee["objB_key"] = objB
        knee["use_holdout"] = bool(use_holdout)
        knee["hypervolume_2d"] = float(hv)
        knee["ref_point"] = {"refA": refA, "refB": refB}
        _save_json(knee, out_dir / "epsilon_knee.json")

        # copy selected base
        try:
            sel_base = Path(knee.get("base_json", ""))
            if sel_base.exists():
                _save_json(_load_json(sel_base), out_dir / "epsilon_selected_base.json")
        except Exception:
            pass

    # plot
    try:
        plt.figure()
        # all points (train/holdout)
        xs = [float(p.get(objA, np.nan)) for p in points]
        ys = [float(p.get(objB, np.nan)) for p in points]
        plt.scatter(xs, ys, label="points")
        if front:
            xf = [float(p[objA]) for p in front]
            yf = [float(p[objB]) for p in front]
            plt.plot(xf, yf, marker="o", linestyle="-", label="front")
        if knee is not None:
            plt.scatter([float(knee[objA])], [float(knee[objB])], marker="x", s=120, label="knee")
        plt.xlabel(objA)
        plt.ylabel(objB)
        plt.title(f"Epsilon-constraint front (use_holdout={use_holdout})")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "epsilon_front.png", dpi=140)
        plt.close()
    except Exception:
        pass


    # bootstrap stability (fast; no re-simulation)
    bootstrap_csv = out_dir / "epsilon_bootstrap_summary.csv"
    robust_point: Optional[Dict[str, Any]] = None

    if int(getattr(args, "bootstrap_reps", 0)) > 0:
        try:
            cmd_bs = [
                sys.executable, str(project_root / "calibration" / "tradeoff_bootstrap_stability_v1.py"),
                "--points_csv", str(out_dir / "epsilon_points.csv"),
                "--points_base_dir", str(out_dir),
                "--groupA", str(primary),
                "--groupB", str(constraint),
                "--reps", str(int(args.bootstrap_reps)),
                "--seed", str(int(args.bootstrap_seed)),
                "--epsilon_tol", str(float(args.epsilon_tol)),
                "--out_csv", str(bootstrap_csv),
            ]
            _run(cmd_bs, cwd=project_root)
        except Exception as e:
            _save_text(f"bootstrap failed: {e}\n", out_dir / "epsilon_bootstrap_FAILED.txt")

        # robust selection on bootstrap p90 (holdout if available else train)
        try:
            if bootstrap_csv.exists():
                df_bs = pd.read_csv(bootstrap_csv, encoding="utf-8-sig")
                colA = "holdout_A_p90" if use_holdout else "train_A_p90"
                colB = "holdout_B_p90" if use_holdout else "train_B_p90"
                colP = "p_feasible_holdout" if use_holdout else "p_feasible_train"

                for c in [colA, colB, colP]:
                    if c in df_bs.columns:
                        df_bs[c] = pd.to_numeric(df_bs[c], errors="coerce")

                # optional feasibility filter (only where epsilon is finite)
                if colP in df_bs.columns and "epsilon" in df_bs.columns:
                    eps_num = pd.to_numeric(df_bs["epsilon"], errors="coerce")
                    mask_eps = np.isfinite(eps_num.values)
                    mask_ok = (~mask_eps) | (pd.to_numeric(df_bs[colP], errors="coerce").fillna(0.0) >= 0.8)
                    df_use = df_bs[mask_ok].copy()
                else:
                    df_use = df_bs.copy()

                pts_rob: List[Dict[str, Any]] = []
                for _, r in df_use.iterrows():
                    a = float(r.get(colA, np.nan))
                    b = float(r.get(colB, np.nan))
                    if not (np.isfinite(a) and np.isfinite(b)):
                        continue
                    d = r.to_dict()
                    d["objA_rob"] = float(a)
                    d["objB_rob"] = float(b)
                    pts_rob.append(d)

                front_rob = pareto_nondominated(pts_rob, "objA_rob", "objB_rob") if pts_rob else []
                if front_rob:
                    xs = np.asarray([float(p["objA_rob"]) for p in front_rob], dtype=float)
                    ys = np.asarray([float(p["objB_rob"]) for p in front_rob], dtype=float)
                    x0, x1 = float(xs.min()), float(xs.max())
                    y0, y1 = float(ys.min()), float(ys.max())
                    dx = max(1e-12, x1 - x0)
                    dy = max(1e-12, y1 - y0)
                    score = np.maximum((xs - x0) / dx, (ys - y0) / dy)
                    i = int(np.argmin(score))
                    robust_point = dict(front_rob[i])
                    robust_point["robust_select"] = "minimax_p90"
                    robust_point["robust_score"] = float(score[i])
                    robust_point["objA_key"] = colA
                    robust_point["objB_key"] = colB
                    _save_json(robust_point, out_dir / "epsilon_robust_point.json")

                    # copy base
                    try:
                        sel_base = Path(str(robust_point.get("base_json", ""))).resolve()
                        if sel_base.exists():
                            _save_json(_load_json(sel_base), out_dir / "epsilon_selected_base_robust.json")
                    except Exception:
                        pass

                # plot robust front
                try:
                    if pts_rob:
                        plt.figure()
                        xa = [float(p["objA_rob"]) for p in pts_rob]
                        yb = [float(p["objB_rob"]) for p in pts_rob]
                        plt.scatter(xa, yb, label="points_p90")
                        if front_rob:
                            xf = [float(p["objA_rob"]) for p in front_rob]
                            yf = [float(p["objB_rob"]) for p in front_rob]
                            plt.plot(xf, yf, marker="o", linestyle="-", label="front_p90")
                        if robust_point is not None:
                            plt.scatter([float(robust_point["objA_rob"])], [float(robust_point["objB_rob"])], marker="x", s=120, label="selected_robust")
                        plt.xlabel(f"{colA}")
                        plt.ylabel(f"{colB}")
                        plt.title(f"Robust epsilon front (p90, use_holdout={use_holdout})")
                        plt.grid(True)
                        plt.legend()
                        plt.tight_layout()
                        plt.savefig(out_dir / "epsilon_front_p90.png", dpi=140)
                        plt.close()
                except Exception:
                    pass

        except Exception:
            pass

    # report md
    md = []
    md.append("# Epsilon-constraint trade-off\n")
    md.append(f"- primary: `{primary}`\n- constraint: `{constraint}`\n- use_holdout: `{use_holdout}`\n")
    md.append(f"- points: `{len(points)}` (eps sweep: init={int(pts_init)}, target={int(pts_target)}, adaptive={bool(args.adaptive)})\n")
    md.append(f"- hypervolume_2d: `{hv:.6g}` (ref=({refA:.3g},{refB:.3g}))\n")
    if knee is not None:
        md.append("## Knee point\n")
        md.append(f"- {objA}: `{float(knee[objA]):.6g}`\n")
        md.append(f"- {objB}: `{float(knee[objB]):.6g}`\n")
        md.append(f"- run_dir: `{knee.get('run_dir','')}`\n")
        if (out_dir / 'epsilon_selected_base.json').exists():
            md.append(f"- selected base: `epsilon_selected_base.json`\n")

    if bootstrap_csv.exists():
        md.append("\n## Bootstrap stability (by tests)\n")
        md.append(f"- bootstrap_reps: `{int(getattr(args, 'bootstrap_reps', 0))}`\n")
        md.append(f"- bootstrap_seed: `{int(getattr(args, 'bootstrap_seed', 0))}`\n")
        md.append(f"- bootstrap_summary: `{bootstrap_csv.name}`\n")
        colA = "holdout_A_p90" if use_holdout else "train_A_p90"
        colB = "holdout_B_p90" if use_holdout else "train_B_p90"
        md.append(f"- robust_objectives: A=`{colA}`, B=`{colB}` (p90)\n")
        if (out_dir / "epsilon_front_p90.png").exists():
            md.append("\n### Robust front (p90)\n")
            md.append("![](epsilon_front_p90.png)\n")
        if robust_point is not None:
            md.append("\n### Robust selected point\n")
            md.append(f"- robust_select: `{robust_point.get('robust_select')}`\n")
            md.append(f"- robust_score: `{robust_point.get('robust_score')}`\n")
            md.append(f"- objA_rob: `{robust_point.get('objA_rob')}`\n")
            md.append(f"- objB_rob: `{robust_point.get('objB_rob')}`\n")
            if (out_dir / 'epsilon_selected_base_robust.json').exists():
                md.append("- selected base (robust): `epsilon_selected_base_robust.json`\n")

    md.append("\n## Files\n")
    md.append("- epsilon_grid.json\n- epsilon_points.csv\n- epsilon_front.csv\n- epsilon_front.png\n- epsilon_knee.json (optional)\n- epsilon_selected_base.json (optional)\n- epsilon_bootstrap_summary.csv (optional)\n- epsilon_front_p90.png (optional)\n- epsilon_robust_point.json (optional)\n- epsilon_selected_base_robust.json (optional)\n")

    _save_text("\n".join(md), out_dir / "epsilon_report.md")


if __name__ == "__main__":
    main()
