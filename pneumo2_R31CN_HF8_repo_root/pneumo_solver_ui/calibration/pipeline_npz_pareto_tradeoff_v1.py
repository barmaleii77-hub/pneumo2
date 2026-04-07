# -*- coding: utf-8 -*-
"""
pipeline_npz_pareto_tradeoff_v1.py

Multi-objective калибровка через Pareto sweep по "пост-множителям" групп сигналов.

Почему так:
- В проекте часто есть конфликтующие группы измерений (например, давления vs кинематика).
- Простое суммирование residual может "утащить" решение в сторону одной группы.
- Мы добавили в fit_worker параметр --group_weights_json, который умножает веса ПОСЛЕ auto_scale,
  поэтому его не "съедает" нормировка и им можно реально управлять компромиссом.

Что делает этот скрипт:
1) Берёт signals.csv (обычно из автопилота/отчёта), убеждается что есть колонка sig_group.
   Если её нет — пытается добавить (эвристика по model_key/meas_col).
2) Делает sweep по лог-шкале: lambda in [-S, +S]
      gain_A = 10**lambda
      gain_B = 10**(-lambda)
   (произведение 1, симметричный компромисс)
3) Для каждой точки запускает fit_worker_v3_suite_identify.py с --group_weights_json.
4) Считает метрики по группам сигналов (unbiased: делим SSE на gain^2).
5) Строит Pareto front, выбирает knee-point (макс. расстояние до линии между экстремумами).
6) Пишет отчёт: pareto_points.csv, pareto_front.csv, pareto_front.png, pareto_report.md,
   и копирует выбранный fitted_base.json -> pareto_selected_base.json.

Ограничения:
- Это НЕ NSGA-II (Deb 2002), а практичный "scalarization sweep" (weighted-sum analogue).
  Для невыпуклых Pareto фронтов weighted-sum может не находить "unsupported" решения;
  в таких случаях можно расширять подход epsilon-constraint-методом (в планах).

Запуск (из корня pneumo_v7):
python calibration/pipeline_npz_pareto_tradeoff_v1.py --osc_dir <OSC_DIR> --signals_csv <signals.csv> --out_dir <OUT_DIR>

"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------
# helpers
# ---------------------------
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

    # valve states
    if any(k in s for k in ["клапан", "valve", "open", "duty"]):
        return "valves"

    # energy / power (если есть)
    if any(k in s for k in ["энерг", "energy", "power", "eedges", "egroups"]):
        return "energy"

    return "default"


def ensure_sig_groups(signals_csv: Path, out_csv: Path) -> Path:
    df = pd.read_csv(signals_csv, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]

    if "sig_group" not in df.columns:
        # build
        mk = df.get("model_key", pd.Series([""] * len(df))).astype(str)
        mc = df.get("meas_col", pd.Series([""] * len(df))).astype(str)
        df["sig_group"] = [infer_sig_group(a, b) for a, b in zip(mk.tolist(), mc.tolist())]
    else:
        df["sig_group"] = df["sig_group"].astype(str).str.strip().replace({"": "default"}).fillna("default")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_csv


def compute_group_rmse_unbiased(details_json: Path, group_name: str, which: str = "holdout") -> float:
    """RMSE (unbiased) для группы сигналов.

    Предпочтительный путь: если details содержит поля sse_unb/rmse_unb (без group_gain), используем их напрямую.
    Fallback (для старых logs): делим SSE на gain^2 (если gain != 0).
    """
    det = _load_json(details_json)
    df = pd.DataFrame(det.get("signals", []))
    if df.empty:
        return float("nan")
    if "sig_group" not in df.columns:
        return float("nan")

    # subset by train/holdout
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
        # Fallback: SSE computed with w that includes group_gain -> divide by gain^2
        if "group_gain" not in df.columns:
            gg = pd.Series([1.0] * len(df))
        else:
            gg = pd.to_numeric(df["group_gain"], errors="coerce").fillna(1.0)
        gg = gg.replace(0.0, np.nan)
        sse = pd.to_numeric(df.get("sse", 0), errors="coerce").fillna(0.0)
        sse_u = float((sse / (gg ** 2)).fillna(0.0).sum())

    return float(math.sqrt(sse_u / max(1.0, n)))


def pareto_nondominated(points: List[Dict[str, Any]], objA: str, objB: str) -> List[Dict[str, Any]]:
    """Вернуть список non-dominated (min-min) точек."""
    out = []
    for i, pi in enumerate(points):
        ai = pi.get(objA)
        bi = pi.get(objB)
        if ai is None or bi is None or not np.isfinite(ai) or not np.isfinite(bi):
            continue
        dominated = False
        for j, pj in enumerate(points):
            if i == j:
                continue
            aj = pj.get(objA)
            bj = pj.get(objB)
            if aj is None or bj is None or not np.isfinite(aj) or not np.isfinite(bj):
                continue
            if (aj <= ai and bj <= bi) and (aj < ai or bj < bi):
                dominated = True
                break
        if not dominated:
            out.append(pi)
    return out


def knee_point_2d(front: List[Dict[str, Any]], objA: str, objB: str) -> Optional[Dict[str, Any]]:
    """Knee point по 2D фронту: максимум расстояния до линии между экстремумами.

    Работает для min-min.
    """
    if not front:
        return None
    A = np.array([[float(p[objA]), float(p[objB])] for p in front], dtype=float)
    # normalize to [0,1]
    mn = A.min(axis=0)
    mx = A.max(axis=0)
    span = np.maximum(mx - mn, 1e-12)
    An = (A - mn) / span

    # extremes
    i1 = int(np.argmin(An[:, 0]))
    i2 = int(np.argmin(An[:, 1]))
    p1 = An[i1]
    p2 = An[i2]

    v = p2 - p1
    nv = float(np.linalg.norm(v))
    if nv < 1e-12:
        # front collapsed
        return front[int(np.argmin(An.sum(axis=1)))]

    # distance from point to line segment (in normalized space)
    dmax = -1.0
    imax = 0
    for i, p in enumerate(An):
        t = float(np.dot(p - p1, v) / (nv ** 2))
        t = max(0.0, min(1.0, t))
        proj = p1 + t * v
        d = float(np.linalg.norm(p - proj))
        if d > dmax:
            dmax = d
            imax = i
    return front[imax]


def plot_pareto(points: List[Dict[str, Any]], front: List[Dict[str, Any]], knee: Optional[Dict[str, Any]], objA: str, objB: str, out_png: Path):
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
        plt.scatter([knee.get(objA, np.nan)], [knee.get(objB, np.nan)], marker="*", s=200, label="knee")

    plt.xlabel(objA)
    plt.ylabel(objB)
    plt.title("Pareto trade-off")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
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

    # fit settings
    ap.add_argument("--n_init", type=int, default=24)
    ap.add_argument("--n_best", type=int, default=4)
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--max_nfev", type=int, default=220)

    # global init / block refine passthrough
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

    # pareto sweep
    ap.add_argument("--groupA", default="pressure")
    ap.add_argument("--groupB", default="kinematics")
    ap.add_argument("--points", type=int, default=9)
    ap.add_argument("--log_gain_span", type=float, default=1.0, help="S: lambda in [-S,+S], gains=10^lambda and 10^-lambda")

    ap.add_argument("--stop_file", default="")
    ap.add_argument("--resume", action="store_true", help="Если run_dir уже есть — пропустить пересчёт (resume)")

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
    ]
    subprocess.run(cmd_map, cwd=str(project_root), check=True)

    # sweep lambdas
    n = max(3, int(args.points))
    span = float(args.log_gain_span)
    lambdas = np.linspace(-span, span, n)

    points: List[Dict[str, Any]] = []

    for i, lam in enumerate(lambdas):
        if _should_stop(stop_file):
            _save_text("STOPPED by stop_file\n", out_dir / "STOPPED.txt")
            break

        gA = float(10.0 ** float(lam))
        gB = float(10.0 ** float(-lam))

        run_dir = out_dir / f"pareto_run_{i+1:02d}_lam_{lam:+.3f}"
        run_dir.mkdir(parents=True, exist_ok=True)

        gw_json = run_dir / "group_weights.json"
        _save_json({str(args.groupA): gA, str(args.groupB): gB}, gw_json)

        out_base = run_dir / "fitted_base.json"
        rep_json = run_dir / "fit_report.json"
        det_json = run_dir / "fit_details.json"
        md_rep = run_dir / "report.md"
        sig_csv = run_dir / "signals.csv"

        if args.resume and rep_json.exists() and det_json.exists() and out_base.exists():
            print(f"[resume] {run_dir.name}")
        else:
            # run fit_worker
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
                "--f_scale", str(args.f_scale),
                "--n_init", str(int(args.n_init)),
                "--n_best", str(int(args.n_best)),
                "--max_nfev", str(int(args.max_nfev)),
            ]
            if args.use_smoothing_defaults:
                cmd_fit.append("--use_smoothing_defaults")
            if stop_file is not None:
                cmd_fit += ["--stop_file", str(stop_file)]
            if str(args.global_init).lower() == "de":
                cmd_fit += ["--global_init", "de",
                            "--de_maxiter", str(int(args.de_maxiter)),
                            "--de_popsize", str(int(args.de_popsize)),
                            "--de_tol", str(float(args.de_tol))]
                if args.de_polish:
                    cmd_fit.append("--de_polish")
            if args.block_refine:
                cmd_fit += ["--block_refine",
                            "--block_corr_thr", str(float(args.block_corr_thr)),
                            "--block_max_size", str(int(args.block_max_size)),
                            "--block_sweeps", str(int(args.block_sweeps)),
                            "--block_max_nfev", str(int(args.block_max_nfev)),
                            "--block_polish_nfev", str(int(args.block_polish_nfev))]

            print(">", " ".join(cmd_fit))
            subprocess.run(cmd_fit, cwd=str(project_root), check=True)

            # build md+signals.csv for convenience
            cmd_rep = [
                sys.executable, str(project_root / "calibration" / "report_from_details_v1.py"),
                "--fit_report", str(rep_json),
                "--fit_details", str(det_json),
                "--out_md", str(md_rep),
                "--out_signals_csv", str(sig_csv),
            ]
            subprocess.run(cmd_rep, cwd=str(project_root), check=True)

        # compute objectives (unbiased)
        objA_tr = compute_group_rmse_unbiased(det_json, str(args.groupA), which="train")
        objB_tr = compute_group_rmse_unbiased(det_json, str(args.groupB), which="train")
        objA_ho = compute_group_rmse_unbiased(det_json, str(args.groupA), which="holdout")
        objB_ho = compute_group_rmse_unbiased(det_json, str(args.groupB), which="holdout")

        p = {
            "idx": int(i + 1),
            "lambda": float(lam),
            "gainA": float(gA),
            "gainB": float(gB),
            "run_dir": str(run_dir),
            "objA_train": float(objA_tr),
            "objB_train": float(objB_tr),
            "objA_holdout": float(objA_ho),
            "objB_holdout": float(objB_ho),
        }
        points.append(p)

    # choose objective columns (prefer holdout if finite)
    use_holdout = any(np.isfinite(p.get("objA_holdout", np.nan)) and np.isfinite(p.get("objB_holdout", np.nan)) for p in points)
    objA = "objA_holdout" if use_holdout else "objA_train"
    objB = "objB_holdout" if use_holdout else "objB_train"

    front = pareto_nondominated(points, objA, objB)
    knee = knee_point_2d(front, objA, objB) if front else None

    # save tables
    df_points = pd.DataFrame(points)
    df_points.to_csv(out_dir / "pareto_points.csv", index=False, encoding="utf-8-sig")

    df_front = pd.DataFrame(front)
    df_front.to_csv(out_dir / "pareto_front.csv", index=False, encoding="utf-8-sig")

    if knee is not None:
        _save_json(knee, out_dir / "pareto_knee.json")
        # copy selected base
        try:
            src = Path(knee["run_dir"]) / "fitted_base.json"
            dst = out_dir / "pareto_selected_base.json"
            if src.exists():
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass

    # plot
    plot_pareto(points, front, knee, objA=objA, objB=objB, out_png=out_dir / "pareto_front.png")

    # report md
    lines = []
    lines.append("# Pareto trade-off report")
    lines.append("")
    lines.append(f"- groupA: `{args.groupA}`")
    lines.append(f"- groupB: `{args.groupB}`")
    lines.append(f"- points: {len(points)}")
    lines.append(f"- objective columns: A=`{objA}`, B=`{objB}` (prefer holdout if present)")
    lines.append("")
    if knee is not None:
        lines.append("## Selected knee point")
        lines.append("")
        lines.append(f"- run_dir: `{knee.get('run_dir')}`")
        lines.append(f"- lambda: {knee.get('lambda')}")
        lines.append(f"- gainA: {knee.get('gainA')}, gainB: {knee.get('gainB')}")
        lines.append(f"- {objA}: {knee.get(objA)}, {objB}: {knee.get(objB)}")
        lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("- pareto_points.csv")
    lines.append("- pareto_front.csv")
    lines.append("- pareto_front.png")
    lines.append("- pareto_knee.json (если найден knee)")
    lines.append("- pareto_selected_base.json (если найден knee)")
    lines.append("")
    _save_text("\n".join(lines) + "\n", out_dir / "pareto_report.md")

    print("DONE pareto. out_dir=", out_dir)


if __name__ == "__main__":
    main()