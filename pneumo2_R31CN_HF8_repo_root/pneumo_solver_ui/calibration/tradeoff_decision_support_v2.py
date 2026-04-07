# -*- coding: utf-8 -*-
"""tradeoff_decision_support_v1.py

Автоматический *decision support* для multiobjective результатов калибровки.

После выполнения:
- Pareto sweep (weighted-sum) -> pareto_tradeoff/
- ε-constraint sweep          -> epsilon_tradeoff/

получаются наборы компромиссных решений. Инженерная проблема:
**какой фронт лучше и какое решение выбрать как финальное**.

Скрипт:
1) загружает *_points.csv;
2) выбирает objective columns (holdout если он реально посчитан в ОБОИХ методах, иначе train);
3) строит non-dominated fronts;
4) считает hypervolume и простую метрику равномерности (spacing CV);
5) выбирает лучший фронт (макс hv_norm_global, затем min spacing_cv);
6) выбирает точку на фронте (knee | hvcontrib | minimax);
7) копирует выбранный base.json в tradeoff_selected_base.json;
8) сохраняет отчёт tradeoff_decision.md/json и картинку tradeoff_front_compare.png.

См. SOURCES.md (hypervolume/knee definitions).
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from mo_metrics_v1 import (
    FrontMetrics2D,
    compute_front_metrics_2d,
    hypervolume_contrib_2d_min,
    knee_point_distance_to_line,
    pareto_nondominated_2d,
    suggest_reference_point,
)


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _detect_obj_cols(df_points: pd.DataFrame) -> Tuple[str, str, bool]:
    """Вернуть (objA_col, objB_col, have_holdout_values)."""
    if df_points.empty:
        return "objA_train", "objB_train", False

    if all(c in df_points.columns for c in ("objA_holdout", "objB_holdout")):
        a = pd.to_numeric(df_points["objA_holdout"], errors="coerce")
        b = pd.to_numeric(df_points["objB_holdout"], errors="coerce")
        if np.isfinite(a).any() and np.isfinite(b).any():
            return "objA_holdout", "objB_holdout", True

    return "objA_train", "objB_train", False


def _load_points_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(path)


def _as_dict_points(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df.empty:
        return []
    return df.to_dict(orient="records")


def _pick_point(front: List[Dict[str, Any]], objA: str, objB: str, refA: float, refB: float, method: str) -> Optional[Dict[str, Any]]:
    if not front:
        return None

    method = str(method).lower().strip()

    if method == "knee":
        return knee_point_distance_to_line(front, objA, objB)

    if method == "hvcontrib":
        contrib = hypervolume_contrib_2d_min(front, objA, objB, refA, refB)
        if not contrib:
            return knee_point_distance_to_line(front, objA, objB)
        i = int(np.argmax(np.asarray(contrib)))
        p = dict(front[i])
        p["hv_contribution"] = float(contrib[i])
        return p

    if method == "minimax":
        # minimize max(normalized objectives)
        xs = np.asarray([float(p[objA]) for p in front], dtype=float)
        ys = np.asarray([float(p[objB]) for p in front], dtype=float)
        x0, x1 = float(xs.min()), float(xs.max())
        y0, y1 = float(ys.min()), float(ys.max())
        dx = max(1e-12, x1 - x0)
        dy = max(1e-12, y1 - y0)
        xn = (xs - x0) / dx
        yn = (ys - y0) / dy
        score = np.maximum(xn, yn)
        i = int(np.argmin(score))
        p = dict(front[i])
        p["minimax_score"] = float(score[i])
        return p

    # fallback
    return knee_point_distance_to_line(front, objA, objB)


def _copy_selected_base(selected_point: Dict[str, Any], method: str, run_dir: Path, out_json: Path) -> bool:
    """Скопировать base.json выбранной точки в out_json."""
    method = str(method).lower().strip()
    try:
        if method == "pareto":
            rd = Path(str(selected_point.get("run_dir", "")))
            cand = rd / "fitted_base.json"
            if cand.exists():
                shutil.copyfile(str(cand), str(out_json))
                return True

        if method == "epsilon":
            bj = str(selected_point.get("base_json", "")).strip()
            if bj:
                cand = Path(bj)
                if cand.exists():
                    shutil.copyfile(str(cand), str(out_json))
                    return True
            # fallback: run_dir relative to epsilon dir
            rd = str(selected_point.get("run_dir", "")).strip()
            if rd:
                cand = run_dir / "epsilon_tradeoff" / rd / "fitted_base.json"
                if cand.exists():
                    shutil.copyfile(str(cand), str(out_json))
                    return True
    except Exception:
        return False

    return False


def _front_summary(method: str,
                   points: List[Dict[str, Any]],
                   front: List[Dict[str, Any]],
                   objA: str, objB: str,
                   refA: float, refB: float,
                   denom_global: float) -> Dict[str, Any]:
    m = compute_front_metrics_2d(front, objA, objB, refA, refB)
    hv_norm_global = float(m.hv / max(1e-12, denom_global))
    knee = knee_point_distance_to_line(front, objA, objB)
    best_hv = _pick_point(front, objA, objB, refA, refB, method="hvcontrib")

    return {
        "method": method,
        "objA_key": objA,
        "objB_key": objB,
        "front_metrics": {
            "hv": float(m.hv),
            "hv_norm": float(m.hv_norm),
            "hv_norm_global": float(hv_norm_global),
            "spacing_cv": float(m.spacing_cv),
            "n_front": int(m.n_points),
            "n_points": int(len(points)),
        },
        "knee": knee,
        "hv_best_point": best_hv,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True, help="папка RUN_*_autopilot_*")
    ap.add_argument("--select_point", default="knee", choices=["knee", "hvcontrib", "minimax"],
                    help="как выбирать финальную точку на фронте")
    ap.add_argument("--use_bootstrap", default="auto", choices=["auto", "yes", "no"],
                    help="Если есть *_bootstrap_summary.csv, использовать p90-метрики (устойчивый выбор). auto=только если есть для ОБОИХ методов")
    ap.add_argument("--min_feasible_prob", type=float, default=0.8,
                    help="Минимальная вероятность выполнимости (bootstrap) для epsilon-точек; применяется только при use_bootstrap!=no")
    ap.add_argument("--margin", type=float, default=0.05, help="зазор для reference point (например 0.05 = +5%)")
    ap.add_argument("--out_prefix", default="tradeoff", help="префикс выходных файлов")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    pareto_dir = run_dir / "pareto_tradeoff"
    eps_dir = run_dir / "epsilon_tradeoff"

    df_p = _load_points_csv(pareto_dir / "pareto_points.csv")
    df_e = _load_points_csv(eps_dir / "epsilon_points.csv")

    have_p = not df_p.empty
    have_e = not df_e.empty

    if not have_p and not have_e:
        raise SystemExit(f"No pareto_points.csv or epsilon_points.csv found in {run_dir}")

    # detect whether holdout exists for each method
    _, _, hold_p = _detect_obj_cols(df_p) if have_p else ("objA_train", "objB_train", False)
    _, _, hold_e = _detect_obj_cols(df_e) if have_e else ("objA_train", "objB_train", False)

    # compare mode:
    # - если есть оба метода -> holdout только если он есть у ОБОИХ (честное сравнение)
    # - если есть только один метод -> используем holdout этого метода (если он посчитан)
    if have_p and have_e:
        use_holdout = bool(hold_p and hold_e)
    elif have_p:
        use_holdout = bool(hold_p)
    else:
        use_holdout = bool(hold_e)

    objA_base = "objA_holdout" if use_holdout else "objA_train"
    objB_base = "objB_holdout" if use_holdout else "objB_train"

    # --- bootstrap summaries (optional) ---
    use_bootstrap_req = str(getattr(args, "use_bootstrap", "auto")).lower().strip()
    df_p_bs = _load_points_csv(pareto_dir / "pareto_bootstrap_summary.csv")
    df_e_bs = _load_points_csv(eps_dir / "epsilon_bootstrap_summary.csv")

    mode = "holdout" if use_holdout else "train"
    objA_boot = f"{mode}_A_p90"
    objB_boot = f"{mode}_B_p90"
    feas_boot = f"p_feasible_{mode}"

    def _has_boot(df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            return False
        if objA_boot not in df.columns or objB_boot not in df.columns:
            return False
        a = pd.to_numeric(df[objA_boot], errors="coerce")
        b = pd.to_numeric(df[objB_boot], errors="coerce")
        return bool(np.isfinite(a).any() and np.isfinite(b).any())

    have_p_boot = bool(have_p and _has_boot(df_p_bs))
    have_e_boot = bool(have_e and _has_boot(df_e_bs))

    use_bootstrap = False
    if use_bootstrap_req != "no":
        if have_p and have_e:
            # сравнение pareto vs epsilon -> используем bootstrap только если он есть у ОБОИХ
            use_bootstrap = bool(have_p_boot and have_e_boot) if use_bootstrap_req in ("auto", "yes") else False
        else:
            # один метод -> bootstrap можно использовать для выбора точки
            use_bootstrap = bool(have_p_boot or have_e_boot) if use_bootstrap_req in ("auto", "yes") else False

    # choose dataframe and objective columns
    if use_bootstrap:
        objA = objA_boot
        objB = objB_boot
        df_p_use = df_p_bs if have_p_boot else df_p
        df_e_use = df_e_bs if have_e_boot else df_e

        # feasibility filter for epsilon points (если колонка есть)
        if have_e and (feas_boot in df_e_use.columns) and ("epsilon" in df_e_use.columns):
            eps_num = pd.to_numeric(df_e_use["epsilon"], errors="coerce")
            p_ok = pd.to_numeric(df_e_use[feas_boot], errors="coerce")
            mask_eps = np.isfinite(eps_num.values)
            thr = float(getattr(args, "min_feasible_prob", 0.8))
            mask_keep = (~mask_eps) | (p_ok.fillna(0.0) >= thr)
            df_e_use = df_e_use[mask_keep].copy()

    else:
        objA = objA_base
        objB = objB_base
        df_p_use = df_p
        df_e_use = df_e

    pts_p = _as_dict_points(df_p_use) if have_p else []
    pts_e = _as_dict_points(df_e_use) if have_e else []

    front_p = pareto_nondominated_2d(pts_p, objA, objB) if have_p else []
    front_e = pareto_nondominated_2d(pts_e, objA, objB) if have_e else []

    refA, refB = suggest_reference_point(pts_p + pts_e, objA, objB, margin=float(args.margin))

    # global denom for normalized comparison
    all_front = front_p + front_e
    if all_front:
        gminA = float(min(float(p[objA]) for p in all_front))
        gminB = float(min(float(p[objB]) for p in all_front))
    else:
        gminA, gminB = 0.0, 0.0
    denom_global = max(1e-12, (refA - gminA) * (refB - gminB))

    decision: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "use_holdout": bool(use_holdout),
        "objA_key": objA,
        "objB_key": objB,
        "ref_point": {"refA": float(refA), "refB": float(refB)},
        "methods": {},
    }

    decision["bootstrap"] = {
        "requested": str(use_bootstrap_req),
        "used": bool(use_bootstrap),
        "mode": "p90" if bool(use_bootstrap) else "none",
        "min_feasible_prob": float(getattr(args, "min_feasible_prob", 0.0)),
        "objA_boot": str(objA_boot) if "objA_boot" in locals() else "",
        "objB_boot": str(objB_boot) if "objB_boot" in locals() else "",
    }

    scored: List[Tuple[str, float, float]] = []  # (method, hv_norm_global, spacing_cv)

    if have_p:
        summary_p = _front_summary("pareto", pts_p, front_p, objA, objB, refA, refB, denom_global)
        decision["methods"]["pareto"] = summary_p
        scored.append(("pareto", float(summary_p["front_metrics"]["hv_norm_global"]), float(summary_p["front_metrics"]["spacing_cv"])) )

    if have_e:
        summary_e = _front_summary("epsilon", pts_e, front_e, objA, objB, refA, refB, denom_global)
        decision["methods"]["epsilon"] = summary_e
        scored.append(("epsilon", float(summary_e["front_metrics"]["hv_norm_global"]), float(summary_e["front_metrics"]["spacing_cv"])) )

    # choose best method: max hv_norm_global then min spacing_cv
    scored.sort(key=lambda t: (-float(t[1]), float(t[2]) if _finite(t[2]) else 1e9))
    best_method = scored[0][0]
    front_sel = front_p if best_method == "pareto" else front_e

    selected_point = _pick_point(front_sel, objA, objB, refA, refB, method=str(args.select_point))

    out_base = run_dir / f"{args.out_prefix}_selected_base.json"
    copied = False
    if selected_point is not None:
        copied = _copy_selected_base(selected_point, best_method, run_dir, out_base)

    decision["selected"] = {
        "method": best_method,
        "select_point": str(args.select_point),
        "point": selected_point,
        "selected_base_json": str(out_base) if copied else "",
    }

    out_json = run_dir / f"{args.out_prefix}_decision.json"
    _save_json(decision, out_json)

    # plot compare
    out_png = run_dir / f"{args.out_prefix}_front_compare.png"
    try:
        plt.figure()
        if have_p and front_p:
            xp = [float(p[objA]) for p in front_p]
            yp = [float(p[objB]) for p in front_p]
            plt.plot(xp, yp, marker="o", linestyle="-", label="pareto_front")
        if have_e and front_e:
            xe = [float(p[objA]) for p in front_e]
            ye = [float(p[objB]) for p in front_e]
            plt.plot(xe, ye, marker="s", linestyle="-", label="epsilon_front")
        if selected_point is not None:
            plt.scatter([float(selected_point[objA])], [float(selected_point[objB])], marker="x", s=140, label=f"selected ({best_method})")
        plt.xlabel(objA)
        plt.ylabel(objB)
        plt.title(f"Trade-off fronts (use_holdout={use_holdout})")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_png, dpi=140)
        plt.close()
    except Exception:
        pass

    # md report
    md: List[str] = []
    md.append(f"# Trade-off decision ({args.out_prefix})\n\n")
    md.append(f"Run dir: `{run_dir.name}`\n\n")
    md.append(f"- compare_mode: `{'holdout' if use_holdout else 'train'}`\n")
    md.append(f"- objective columns: A=`{objA}`, B=`{objB}`\n")
    md.append(f"- bootstrap_used: `{bool(use_bootstrap)}` (mode=p90, requested={use_bootstrap_req})\n")
    if bool(use_bootstrap):
        md.append(f"- min_feasible_prob (epsilon): `{float(getattr(args, 'min_feasible_prob', 0.0))}`\n")
    md.append(f"- ref_point: ({refA:.6g}, {refB:.6g}) margin={float(args.margin):.3g}\n")

    md.append("\n## Methods summary\n\n")
    for m in ["pareto", "epsilon"]:
        if m not in decision["methods"]:
            continue
        fm = decision["methods"][m]["front_metrics"]
        md.append(f"### {m}\n\n")
        md.append(f"- points: {fm.get('n_points')} / front: {fm.get('n_front')}\n")
        md.append(f"- hypervolume: `{fm.get('hv'):.6g}`\n")
        md.append(f"- hv_norm_global: `{fm.get('hv_norm_global'):.6g}` (для сравнения)\n")
        md.append(f"- spacing_cv: `{fm.get('spacing_cv')}` (меньше = равномернее)\n\n")

    md.append("## Selected\n\n")
    md.append(f"- best_method: **{best_method}**\n")
    md.append(f"- point_select: `{args.select_point}`\n")
    if selected_point is not None:
        md.append(f"- {objA}: `{float(selected_point[objA]):.6g}`\n")
        md.append(f"- {objB}: `{float(selected_point[objB]):.6g}`\n")
        if "knee_dist_norm" in selected_point:
            md.append(f"- knee_dist_norm: `{float(selected_point['knee_dist_norm']):.6g}`\n")
        if "hv_contribution" in selected_point:
            md.append(f"- hv_contribution: `{float(selected_point['hv_contribution']):.6g}`\n")
        if "minimax_score" in selected_point:
            md.append(f"- minimax_score: `{float(selected_point['minimax_score']):.6g}`\n")

    if copied:
        md.append(f"- selected base: `{out_base.name}`\n")

    if out_png.exists():
        md.append("\n## Plot\n\n")
        md.append(f"![]({out_png.name})\n")

    md.append("\n## Files\n\n")
    md.append(f"- `{out_json.name}`\n")
    md.append(f"- `{out_png.name}`\n")
    if copied:
        md.append(f"- `{out_base.name}`\n")

    _save_text("".join(md), run_dir / f"{args.out_prefix}_decision.md")

    print("DONE decision support. saved:", out_json)


if __name__ == "__main__":
    main()
