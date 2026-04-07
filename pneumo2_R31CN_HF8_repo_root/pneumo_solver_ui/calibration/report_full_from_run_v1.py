# -*- coding: utf-8 -*-
"""
report_full_from_run_v1.py

Собирает "единый" markdown-отчёт по папке автопилота, включая:
- summary fit (fit_report_final.json)
- top tests/signals (fit_details_final.json)
- action_plan.md
- OED summary (если есть)
- profile summary + картинки (если есть)
- time-series plots index + врезка картинок (если есть)

Вход:
--run_dir: папка вида calibration_runs/RUN_..._autopilot/

Выход:
- REPORT_FULL.md в run_dir
- (опционально) REPORT_FULL.html, если установлен пакет markdown (не обязателен)

"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return p.read_text(encoding="utf-8", errors="ignore")


def _fmt(x: Any, nd: int = 6) -> str:
    try:
        xf = float(x)
    except Exception:
        return str(x)
    if math.isfinite(xf):
        ax = abs(xf)
        if ax != 0 and (ax < 1e-3 or ax > 1e6):
            return f"{xf:.{nd}e}"
        return f"{xf:.{nd}f}"
    return str(x)


def _save_text(txt: str, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--max_plots", type=int, default=12, help="Сколько картинок вставлять в отчёт максимум")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    fit_report_p = run_dir / "fit_report_final.json"
    fit_details_p = run_dir / "fit_details_final.json"
    action_md_p = run_dir / "action_plan.md"
    oed_p = run_dir / "oed_report.json"
    prof_p = run_dir / "profile_report.json"
    plots_index_p = run_dir / "plots" / "plots_index.csv"
    prof_index_p = run_dir / "profile_plots" / "profile_index.csv"
    pareto_dir = run_dir / "pareto_tradeoff"
    pareto_report_p = pareto_dir / "pareto_report.md"
    pareto_png_p = pareto_dir / "pareto_front.png"
    pareto_front_p = pareto_dir / "pareto_front.csv"
    pareto_knee_p = pareto_dir / "pareto_knee.json"
    pareto_sel_p = pareto_dir / "pareto_selected_base.json"

    epsilon_dir = run_dir / "epsilon_tradeoff"
    epsilon_report_p = epsilon_dir / "epsilon_report.md"
    epsilon_png_p = epsilon_dir / "epsilon_front.png"
    epsilon_front_p = epsilon_dir / "epsilon_front.csv"
    epsilon_knee_p = epsilon_dir / "epsilon_knee.json"
    epsilon_sel_p = epsilon_dir / "epsilon_selected_base.json"

    group_balance_dir = run_dir / "group_balance"
    group_balance_md_p = group_balance_dir / "group_balance_report.md"
    group_balance_hist_p = group_balance_dir / "group_balance_history.csv"
    group_weights_p = group_balance_dir / "group_weights_final.json"

    # Param prune / active set (optional)
    param_prune_dir = run_dir / "param_prune"
    param_prune_md_p = param_prune_dir / "param_prune.md"
    param_prune_report_p = param_prune_dir / "param_prune_report.json"
    param_prune_ranges_p = param_prune_dir / "fit_ranges_pruned.json"
    param_prune_base_p = param_prune_dir / "fitted_base_pruned.json"

    # Trade-off decision support (auto)
    tradeoff_md_p = run_dir / "tradeoff_decision.md"
    tradeoff_png_p = run_dir / "tradeoff_front_compare.png"
    tradeoff_json_p = run_dir / "tradeoff_decision.json"
    tradeoff_base_p = run_dir / "tradeoff_selected_base.json"

    md: List[str] = []
    md.append("# REPORT_FULL (autopilot)\n")
    md.append(f"Run dir: `{run_dir.name}`\n")

    # fit summary
    if fit_report_p.exists():
        rep = _load_json(fit_report_p)
        md.append("## Fit summary")
        md.append(f"- best_rmse: **{_fmt(rep.get('best_rmse'))}**")
        md.append(f"- best_sse: `{_fmt(rep.get('best_sse'))}`")
        md.append(f"- success: `{rep.get('success')}`")
        md.append(f"- nfev: `{rep.get('nfev')}`")
        md.append(f"- loss: `{rep.get('loss')}`, f_scale={_fmt(rep.get('f_scale'))}")
        md.append(f"- record_full: `{rep.get('record_full')}`, record_stride={rep.get('record_stride')}")
        md.append("")
    else:
        md.append("⚠️ fit_report_final.json not found.\n")

    # top tests/signals from fit_details
    if fit_details_p.exists():
        det = _load_json(fit_details_p)
        df_t = pd.DataFrame(det.get("tests", []))
        df_s = pd.DataFrame(det.get("signals", []))

    # time alignment summary (optional)
    time_align_dir = run_dir / "time_align"
    if time_align_dir.exists():
        md.append("## Time alignment (sensor delay)")
        shifts_json = time_align_dir / "time_shifts.json"
        shifts_csv = time_align_dir / "time_shifts.csv"
        rep_md = time_align_dir / "TIME_ALIGN_REPORT.md"
        map_aligned = time_align_dir / "mapping_time_aligned.json"
        if shifts_json.exists():
            try:
                smap = _load_json(shifts_json)
                if isinstance(smap, dict):
                    md.append(f"- shift items: `{len(smap)}`")
                    items = []
                    for k, v in smap.items():
                        try:
                            items.append((str(k), float(v)))
                        except Exception:
                            pass
                    items = sorted(items, key=lambda kv: abs(kv[1]), reverse=True)[:20]
                    if items:
                        md.append("### Largest |shift| (top 20)")
                        for k, v in items:
                            md.append(f"- `{k}`: **{v:+.6f} s**")
            except Exception:
                md.append("- shift map: (failed to parse)")
        if shifts_csv.exists():
            md.append(f"- shifts csv: `time_align/{shifts_csv.name}`")
        if rep_md.exists():
            md.append(f"- report: `time_align/{rep_md.name}`")
        if map_aligned.exists():
            md.append(f"- aligned mapping: `time_align/{map_aligned.name}`")

        md.append("## Top tests / signals by SSE")

        if not df_t.empty:
            df_t["sse"] = pd.to_numeric(df_t.get("sse", 0), errors="coerce")
            g = df_t.groupby(["test", "group"], as_index=False).agg(sse=("sse", "sum"), n=("n", "sum"))
            g["rmse"] = (g["sse"] / g["n"].clip(lower=1)).pow(0.5)
            g = g.sort_values("sse", ascending=False).head(12)
            md.append("### Tests (top 12)")
            md.append("| test | group | n | sse | rmse |")
            md.append("|---|---:|---:|---:|---:|")
            for _, r in g.iterrows():
                md.append(f"| {r['test']} | {r['group']} | {int(r['n'])} | {_fmt(r['sse'])} | {_fmt(r['rmse'])} |")
            md.append("")
        if not df_s.empty and all(c in df_s.columns for c in ["meas_table", "meas_col", "model_key"]):
            df_s["sse"] = pd.to_numeric(df_s.get("sse", 0), errors="coerce")
            g = df_s.groupby(["meas_table", "meas_col", "model_key"], as_index=False).agg(sse=("sse", "sum"), n=("n", "sum"))
            g["rmse"] = (g["sse"] / g["n"].clip(lower=1)).pow(0.5)
            g = g.sort_values("sse", ascending=False).head(15)
            md.append("### Signals (top 15)")
            md.append("| meas_table | meas_col | model_key | n | sse | rmse |")
            md.append("|---|---|---|---:|---:|---:|")
            for _, r in g.iterrows():
                md.append(f"| {r['meas_table']} | {r['meas_col']} | {r['model_key']} | {int(r['n'])} | {_fmt(r['sse'])} | {_fmt(r['rmse'])} |")
            md.append("")
    else:
        md.append("⚠️ fit_details_final.json not found.\n")

    # action plan
    if action_md_p.exists():
        md.append("## Action plan (diagnose_fit)")
        md.append("")
        md.append(_load_text(action_md_p))
        md.append("")
    else:
        md.append("⚠️ action_plan.md not found.\n")

    # OED summary (small)
    if oed_p.exists():
        md.append("## OED/FIM (summary)")
        oed = _load_json(oed_p)
        suite = oed.get("suite_total", {})
        if suite:
            for k in ["rank", "n_params", "logdet", "cond", "trace", "min_eig"]:
                if k in suite:
                    md.append(f"- {k}: `{suite[k]}`")
        greedy = oed.get("greedy_D_opt", {})
        if greedy and "order" in greedy:
            md.append("")
            md.append("Top-10 tests by greedy D-opt order:")
            md.append("")
            for name in greedy.get("order", [])[:10]:
                md.append(f"- {name}")
        md.append("")
    else:
        md.append("")

    # Profile summary + plots
    if prof_p.exists():
        md.append("## Profile likelihood")
        prof = _load_json(prof_p)
        md.append(f"- loss: `{prof.get('loss')}`")
        md.append(f"- sse_star: `{_fmt(prof.get('sse_star'))}`")
        md.append(f"- dof: `{prof.get('dof')}`")
        md.append("")
        profiles = prof.get("profiles", {})
        if isinstance(profiles, dict):
            md.append("| param | theta* | CI95 | CI68 |")
            md.append("|---|---:|---:|---:|")
            for pname, pdata in profiles.items():
                ci95 = pdata.get("ci_95", [None, None])
                ci68 = pdata.get("ci_68", [None, None])
                md.append(f"| {pname} | {_fmt(pdata.get('theta_star'))} | [{ci95[0]}, {ci95[1]}] | [{ci68[0]}, {ci68[1]}] |")
            md.append("")
        # embed plots if index exists
        if prof_index_p.exists():
            dfp = pd.read_csv(prof_index_p, encoding="utf-8-sig")
            md.append("### Profile plots")
            for _, r in dfp.head(int(args.max_plots)).iterrows():
                png = str(r.get("plot_png", "")).strip()
                if png:
                    md.append(f"**{r.get('param','')}**")
                    md.append(f"![](profile_plots/{png})\n")
        md.append("")
    else:
        md.append("")


    # Adaptive group balance (sig_group)
    if group_balance_dir.exists():
        md.append("## Adaptive group balance (sig_group)")
        md.append("")
        if group_balance_md_p.exists():
            md.append(_load_text(group_balance_md_p))
            md.append("")
        if group_weights_p.exists():
            md.append(f"- group_weights_final: `group_balance/{group_weights_p.name}`")
        if group_balance_hist_p.exists():
            md.append(f"- history: `group_balance/{group_balance_hist_p.name}`")
        md.append("")
    else:
        md.append("")

    # Param prune (active set)
    if param_prune_dir.exists():
        md.append("## Param prune (active set)")
        md.append("")
        if param_prune_md_p.exists():
            md.append(_load_text(param_prune_md_p))
            md.append("")
        if param_prune_ranges_p.exists():
            md.append(f"- pruned ranges: `param_prune/{param_prune_ranges_p.name}`")
        if param_prune_base_p.exists():
            md.append(f"- pruned base: `param_prune/{param_prune_base_p.name}`")
        if param_prune_report_p.exists():
            md.append(f"- report: `param_prune/{param_prune_report_p.name}`")
        md.append("")
    else:
        md.append("")

    # Pareto trade-off
    if pareto_dir.exists():
        md.append("## Pareto trade-off (multiobjective)")
        md.append("")
        if pareto_report_p.exists():
            md.append(_load_text(pareto_report_p))
            md.append("")
        if pareto_png_p.exists():
            md.append("### Pareto front")
            md.append(f"![](pareto_tradeoff/{pareto_png_p.name})\n")

        # bootstrap stability (if available)
        pareto_bs_p = pareto_dir / "pareto_bootstrap_summary.csv"
        if pareto_bs_p.exists():
            md.append("### Bootstrap stability (p90)")
            md.append(f"- bootstrap_summary: `pareto_tradeoff/{pareto_bs_p.name}`")
            try:
                dfb = pd.read_csv(pareto_bs_p, encoding="utf-8-sig")
                # show top few rows by holdout if exists, else train
                colA = "holdout_A_p90" if ("holdout_A_p90" in dfb.columns and np.isfinite(pd.to_numeric(dfb["holdout_A_p90"], errors='coerce')).any()) else "train_A_p90"
                colB = "holdout_B_p90" if ("holdout_B_p90" in dfb.columns and np.isfinite(pd.to_numeric(dfb["holdout_B_p90"], errors='coerce')).any()) else "train_B_p90"
                for c in [colA, colB]:
                    if c in dfb.columns:
                        dfb[c] = pd.to_numeric(dfb[c], errors='coerce')
                dfb = dfb.sort_values(colA, ascending=True).head(int(args.max_tables))
                md.append(f"| run_dir | {colA} | {colB} |\n|---|---:|---:|" )
                for _, r in dfb.iterrows():
                    md.append(f"| {r.get('run_dir','')} | {_fmt(r.get(colA))} | {_fmt(r.get(colB))} |")
                md.append("")
            except Exception:
                md.append("")
            md.append("")
        if pareto_knee_p.exists():
            try:
                knee = _load_json(pareto_knee_p)
                md.append("### Knee point")
                md.append(f"- run_dir: `{knee.get('run_dir')}`")
                md.append(f"- objA_holdout: `{knee.get('objA_holdout', knee.get('objA_train'))}`")
                md.append(f"- objB_holdout: `{knee.get('objB_holdout', knee.get('objB_train'))}`")
                md.append("")
            except Exception:
                pass
        if pareto_sel_p.exists():
            md.append(f"- Selected base: `pareto_tradeoff/{pareto_sel_p.name}`")
            md.append("")
    else:
        md.append("")


    # Epsilon-constraint trade-off
    if epsilon_dir.exists():
        md.append("## Epsilon-constraint trade-off (multiobjective)")
        md.append("")
        if epsilon_report_p.exists():
            md.append(_load_text(epsilon_report_p))
            md.append("")
        if epsilon_png_p.exists():
            md.append("### Epsilon front")
            md.append(f"![](epsilon_tradeoff/{epsilon_png_p.name})\n")

        # bootstrap stability + robust front (if available)
        eps_bs_p = epsilon_dir / "epsilon_bootstrap_summary.csv"
        eps_p90_png = epsilon_dir / "epsilon_front_p90.png"
        eps_rob_point_p = epsilon_dir / "epsilon_robust_point.json"
        eps_sel_rob_p = epsilon_dir / "epsilon_selected_base_robust.json"

        if eps_bs_p.exists():
            md.append("### Bootstrap stability (p90)")
            md.append(f"- bootstrap_summary: `epsilon_tradeoff/{eps_bs_p.name}`")
            if eps_p90_png.exists():
                md.append("### Robust epsilon front (p90)")
                md.append(f"![](epsilon_tradeoff/{eps_p90_png.name})\n")
            try:
                if eps_rob_point_p.exists():
                    rp = _load_json(eps_rob_point_p)
                    md.append("### Robust selected point")
                    md.append(f"- robust_select: `{rp.get('robust_select')}`")
                    md.append(f"- robust_score: `{rp.get('robust_score')}`")
                    md.append(f"- objA_rob: `{rp.get('objA_rob')}`")
                    md.append(f"- objB_rob: `{rp.get('objB_rob')}`")
                    if eps_sel_rob_p.exists():
                        md.append(f"- Selected base (robust): `epsilon_tradeoff/{eps_sel_rob_p.name}`")
                    md.append("")
            except Exception:
                pass
            md.append("")
        if epsilon_knee_p.exists():
            try:
                knee = _load_json(epsilon_knee_p)
                md.append("### Knee point")
                md.append(f"- run_dir: `{knee.get('run_dir')}`")
                md.append(f"- objA_holdout: `{knee.get('objA_holdout', knee.get('objA_train'))}`")
                md.append(f"- objB_holdout: `{knee.get('objB_holdout', knee.get('objB_train'))}`")
                md.append("")
            except Exception:
                pass
        if epsilon_sel_p.exists():
            md.append(f"- Selected base: `epsilon_tradeoff/{epsilon_sel_p.name}`")
            md.append("")
    else:
        md.append("")

    # Trade-off decision (auto)
    if tradeoff_md_p.exists():
        md.append("## Trade-off decision (auto)")
        md.append("")
        md.append(_load_text(tradeoff_md_p))
        md.append("")
    elif (pareto_dir.exists() or epsilon_dir.exists()):
        md.append("## Trade-off decision (auto)")
        md.append("")
        md.append("ℹ️ tradeoff_decision.md not found (decision support step not executed).")
        md.append("")

    # Timeseries plots
    if plots_index_p.exists():
        md.append("## Measured vs simulated plots")
        df = pd.read_csv(plots_index_p, encoding="utf-8-sig")
        md.append(f"- total plots: `{len(df)}`\n")
        show = df.sort_values("sse", ascending=False).head(int(args.max_plots))
        for _, r in show.iterrows():
            md.append(f"**{r.get('test','')} | {r.get('model_key','')}**  ")
            md.append(f"RMSE={_fmt(r.get('rmse'))}, NRMSE={_fmt(r.get('nrmse'))}")
            md.append(f"![](plots/{r.get('plot_png')})\n")
            # optional resid
            resid = str(r.get("resid_png", "")).strip()
            if resid:
                md.append(f"![](plots/{resid})\n")
        md.append("")
    else:
        md.append("")

    md.append("## Notes")
    md.append("- NPZ load uses allow_pickle=True. Используйте только доверенные NPZ-логи (из вашего UI).")
    md.append("- Если графики отсутствуют — установите matplotlib и перезапустите автопилот с --run_plots.")
    md.append("")

    out_md = run_dir / "REPORT_FULL.md"
    _save_text("\n".join(md), out_md)
    print("Wrote:", out_md)


if __name__ == "__main__":
    main()