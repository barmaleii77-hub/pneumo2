# -*- coding: utf-8 -*-
"""
pipeline_npz_autopilot_v7.py

Автопилот "всё автоматически" для калибровки по NPZ + multiobjective:

1) Итеративная калибровка (signals.csv -> fit -> report -> refine signals) N итераций
2) Финальный набор сигналов/параметров копируется в out_dir
3) (опц.) OED/FIM
4) diagnose_fit -> action_plan.md + action_plan.json
5) (опц.) Авто-profile likelihood по параметрам из action_plan.json
6) (опц.) Графики measured vs simulated по top тестам/сигналам
7) (опц.) Pareto sweep по группам сигналов (pressure vs kinematics)
8) REPORT_FULL.md

Запуск (из корня pneumo_v7):
python calibration/pipeline_npz_autopilot_v7.py --osc_dir <OSC_DIR> --run_oed --run_profile_auto --run_plots

Выход: calibration_runs/RUN_..._autopilot_v7/

Примечание по производительности:
- profile likelihood может быть дорогим. Ограничивайте --profile_max_params и --profile_points.

"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


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


def _should_stop(stop_file: Optional[Path]) -> bool:
    try:
        return stop_file is not None and stop_file.exists()
    except Exception:
        return False


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


def _select_profile_params(action_plan_json: Path, max_params: int) -> List[str]:
    if not action_plan_json.exists():
        return []
    ap = _load_json(action_plan_json)

    picked: List[str] = []
    seen: Set[str] = set()

    def add(name: str):
        n = str(name).strip()
        if not n:
            return
        if n in seen:
            return
        seen.add(n)
        picked.append(n)

    # 1) bounds
    for row in ap.get("at_bounds", []):
        add(row.get("param", ""))

    # 2) high rel std
    for row in ap.get("high_rel_std", []):
        add(row.get("param", ""))

    # 3) correlated pairs
    for row in ap.get("high_corr_pairs", []):
        add(row.get("p1", ""))
        add(row.get("p2", ""))

    if max_params > 0:
        picked = picked[:max_params]
    return picked


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

    ap.add_argument("--stop_file", default="", help="Если файл существует — мягко остановиться")

    ap.add_argument("--auto_scale", default="mad", help="none|mad|std|range")
    ap.add_argument("--use_smoothing_defaults", action="store_true")
    ap.add_argument("--holdout_frac", type=float, default=0.2)
    ap.add_argument("--holdout_seed", type=int, default=1)

    ap.add_argument("--n_init", type=int, default=32)
    ap.add_argument("--n_best", type=int, default=6)
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)

    # Global init (optional)
    ap.add_argument("--global_init", default="none", choices=["none", "de"], help="Глобальная инициализация перед least_squares: none|de")
    ap.add_argument("--de_maxiter", type=int, default=8)
    ap.add_argument("--de_popsize", type=int, default=10)
    ap.add_argument("--de_tol", type=float, default=0.01)
    ap.add_argument("--de_polish", action="store_true")

    # Block refine (optional)
    ap.add_argument("--disable_block_refine", action="store_true", help="Отключить block coordinate refinement (если нужно ускорить)")
    ap.add_argument("--block_corr_thr", type=float, default=0.85)
    ap.add_argument("--block_max_size", type=int, default=6)
    ap.add_argument("--block_sweeps", type=int, default=2)
    ap.add_argument("--block_max_nfev", type=int, default=120)
    ap.add_argument("--block_polish_nfev", type=int, default=120)

    # OED
    ap.add_argument("--run_oed", action="store_true")
    ap.add_argument("--oed_sample_stride", type=int, default=8)

    # Reduced suite
    ap.add_argument("--make_reduced_suite", action="store_true")
    ap.add_argument("--reduced_suite_fraction", type=float, default=0.95)
    ap.add_argument("--reduced_suite_max_tests", type=int, default=12)

    # Profile
    ap.add_argument("--run_profile_auto", action="store_true")
    ap.add_argument("--profile_loss", default="linear", help="linear (для CI) или soft_l1/huber/...")
    ap.add_argument("--profile_span", type=float, default=0.35)
    ap.add_argument("--profile_points", type=int, default=13)
    ap.add_argument("--profile_max_params", type=int, default=4)
    ap.add_argument("--profile_max_nfev", type=int, default=120)

    # Plots
    ap.add_argument("--run_plots", action="store_true")
    ap.add_argument("--plots_top_tests", type=int, default=3)
    ap.add_argument("--plots_top_signals", type=int, default=6)

    # Pareto trade-off (optional)
    ap.add_argument("--run_pareto", action="store_true", help="Сделать Pareto sweep по группам сигналов (post-scale gains)")
    ap.add_argument("--run_epsilon", action="store_true", help="После pareto сделать epsilon-constraint sweep (multiobjective, покрывает невыпуклые участки фронта)")
    ap.add_argument("--epsilon_primary", default="pressure")
    ap.add_argument("--epsilon_constraint", default="kinematics")
    ap.add_argument("--epsilon_points", type=int, default=9)
    ap.add_argument("--epsilon_penalty", type=float, default=2000.0)
    ap.add_argument("--epsilon_resume", action="store_true")
    ap.add_argument("--epsilon_adaptive", action="store_true", help="Адаптивно уплотнять epsilon-сетку (pipeline_npz_epsilon_constraint_v2)")
    ap.add_argument("--epsilon_min_points", type=int, default=5)
    ap.add_argument("--epsilon_min_gap_norm", type=float, default=0.18)
    ap.add_argument("--tradeoff_bootstrap_reps", type=int, default=200, help="Bootstrap reps для устойчивости trade-off (0 -> выключить)")
    ap.add_argument("--tradeoff_bootstrap_seed", type=int, default=0)
    ap.add_argument("--no_tradeoff_bootstrap", action="store_true", help="Не считать bootstrap_summary для pareto/epsilon")
    ap.add_argument("--tradeoff_min_feasible_prob", type=float, default=0.8, help="Порог p_feasible_* для epsilon при выборе (bootstrap)")
    ap.add_argument("--pareto_groupA", default="pressure")
    ap.add_argument("--pareto_groupB", default="kinematics")
    ap.add_argument("--pareto_points", type=int, default=9)
    ap.add_argument("--pareto_log_gain_span", type=float, default=1.0)
    ap.add_argument("--pareto_resume", action="store_true", help="Если pareto_run_* уже посчитаны — не пересчитывать")


    # Trade-off decision support (Pareto vs ε-constraint)
    ap.add_argument("--skip_tradeoff_decision", action="store_true",
                    help="Не запускать автоматический выбор решения по trade-off (по умолчанию запускается, если есть pareto/epsilon)")
    ap.add_argument("--tradeoff_select_point", default="knee", choices=["knee", "hvcontrib", "minimax"],
                    help="Как выбирать финальную точку на выбранном фронте")
    ap.add_argument("--tradeoff_margin", type=float, default=0.05,
                    help="Зазор для reference point в hypervolume (например 0.05 = +5%)")

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
        out_dir = project_root / "calibration_runs" / f"RUN_{ts}_autopilot_v7"
    out_dir.mkdir(parents=True, exist_ok=True)

    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else (out_dir / "STOP_AUTOPILOT.txt")
    # Если stop_file существует уже сейчас — выходим сразу
    if _should_stop(stop_file):
        (out_dir / "STOPPED.txt").write_text("stopped before start\n", encoding="utf-8")
        print("STOP requested before start.")
        return

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
        "--global_init", str(args.global_init),
        "--de_maxiter", str(int(args.de_maxiter)),
        "--de_popsize", str(int(args.de_popsize)),
        "--de_tol", str(float(args.de_tol)),
        "--block_corr_thr", str(float(args.block_corr_thr)),
        "--block_max_size", str(int(args.block_max_size)),
        "--block_sweeps", str(int(args.block_sweeps)),
        "--block_max_nfev", str(int(args.block_max_nfev)),
        "--block_polish_nfev", str(int(args.block_polish_nfev)),
        "--holdout_frac", str(float(args.holdout_frac)),
        "--holdout_seed", str(int(args.holdout_seed)),
        "--out_dir", str(iterative_dir),
    ]
    if stop_file is not None:
        cmd_iter += ["--stop_file", str(stop_file)]
    if args.use_smoothing_defaults:
        cmd_iter.append("--use_smoothing_defaults")
    if bool(getattr(args, "de_polish", False)):
        cmd_iter.append("--de_polish")
    if not bool(getattr(args, "disable_block_refine", False)):
        cmd_iter.append("--block_refine")
    _run(cmd_iter, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / "STOPPED.txt").write_text("stopped after iterative\n", encoding="utf-8")
        print("STOP requested. Exiting after iterative stage.")
        return

    # locate final iteration artifacts
    last_iter = _find_last_iter_dir(iterative_dir)
    final_fit_report = last_iter / "fit_report.json"
    final_fit_details = last_iter / "fit_details.json"
    final_fit_params = last_iter / "fitted_base.json"
    final_mapping = last_iter / "mapping.json"
    final_signals = iterative_dir / "FINAL_SIGNALS.csv"
    if not final_signals.exists():
        final_signals = last_iter / "signals_refined.csv"

    # copy artifacts to out_dir root
    for src, dst_name in [
        (final_fit_report, "fit_report_final.json"),
        (final_fit_details, "fit_details_final.json"),
        (final_fit_params, "fitted_base_final.json"),
        (final_mapping, "mapping_final.json"),
        (final_signals, "FINAL_SIGNALS.csv"),
    ]:
        if src.exists():
            (out_dir / dst_name).write_bytes(src.read_bytes())

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
            "--stop_file", str(stop_file),
        ]
        if args.use_smoothing_defaults:
            cmd_oed.append("--use_smoothing_defaults")
        _run(cmd_oed, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at oed\n', encoding='utf-8')
        print('STOP requested at oed.')
        return


    # 4) diagnose + action plan
    action_md = out_dir / "action_plan.md"
    action_json = out_dir / "action_plan.json"
    cmd_diag = [
        sys.executable, str(project_root / "calibration" / "diagnose_fit_v1.py"),
        "--fit_report", str(out_dir / "fit_report_final.json"),
        "--fit_details", str(out_dir / "fit_details_final.json"),
        "--fitted_json", str(out_dir / "fitted_base_final.json"),
        "--fit_ranges_json", str(project_root / args.fit_ranges_json),
        "--out_md", str(action_md),
        "--out_json", str(action_json),
    ]
    if args.run_oed and oed_report.exists():
        cmd_diag += ["--oed_report", str(oed_report)]
    _run(cmd_diag, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at diagnose\n', encoding='utf-8')
        print('STOP requested at diagnose.')
        return


    # 5) reduced suite (optional)
    suite_reduced = out_dir / "suite_reduced.json"
    if args.make_reduced_suite and args.run_oed and oed_report.exists():
        cmd_prune = [
            sys.executable, str(project_root / "calibration" / "suite_prune_from_oed_v1.py"),
            "--oed_report", str(oed_report),
            "--suite_json", str(project_root / args.suite_json),
            "--out_suite_json", str(suite_reduced),
            "--fraction", str(float(args.reduced_suite_fraction)),
            "--max_tests", str(int(args.reduced_suite_max_tests)),
        ]
        _run(cmd_prune, cwd=project_root)

    # 6) profile likelihood (auto)
    profile_report = out_dir / "profile_report.json"
    profile_out_dir = out_dir / "profile_out"
    profile_plots_dir = out_dir / "profile_plots"

    selected_params: List[str] = []
    if args.run_profile_auto:
        selected_params = _select_profile_params(action_json, int(args.profile_max_params))
        (out_dir / "profile_params_selected.txt").write_text("\n".join(selected_params) + "\n", encoding="utf-8")

        if selected_params:
            cmd_prof = [
                sys.executable, str(project_root / "calibration" / "profile_worker_v1_likelihood.py"),
                "--model", str(project_root / args.model),
                "--worker", str(project_root / args.worker),
                "--suite_json", str(project_root / args.suite_json),
                "--osc_dir", str(osc_dir),
                "--theta_star_json", str(out_dir / "fitted_base_final.json"),
                "--fit_ranges_json", str(project_root / args.fit_ranges_json),
                "--mapping_json", str(out_dir / "mapping_final.json"),
                "--profile_params", ",".join(selected_params),
                "--span", str(float(args.profile_span)),
                "--n_points", str(int(args.profile_points)),
                "--loss", str(args.profile_loss),
                "--f_scale", str(float(args.f_scale)),
                "--max_nfev", str(int(args.profile_max_nfev)),
                "--out_json", str(profile_report),
                "--out_dir", str(profile_out_dir),
                "--stop_file", str(stop_file),
            ]
            if args.use_smoothing_defaults:
                cmd_prof.append("--use_smoothing_defaults")
            _run(cmd_prof, cwd=project_root)

            if _should_stop(stop_file):
                (out_dir / "STOPPED.txt").write_text("stopped at profile\n", encoding="utf-8")
                print("STOP requested at profile.")
                return

            # plots of profiles
            cmd_prof_plot = [
                sys.executable, str(project_root / "calibration" / "plot_profile_v1.py"),
                "--profile_json", str(profile_report),
                "--out_dir", str(profile_plots_dir),
            ]
            _run(cmd_prof_plot, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / "STOPPED.txt").write_text("stopped after profile\n", encoding="utf-8")
        print("STOP requested after profile stage.")
        return


    # 7) plots measured vs sim
    if args.run_plots:
        cmd_plots = [
            sys.executable, str(project_root / "calibration" / "plot_fit_timeseries_v1.py"),
            "--model", str(args.model),
            "--worker", str(args.worker),
            "--suite_json", str(args.suite_json),
            "--osc_dir", str(osc_dir),
            "--fitted_json", str(out_dir / "fitted_base_final.json"),
            "--mapping_json", str(out_dir / "mapping_final.json"),
            "--fit_details_json", str(out_dir / "fit_details_final.json"),
            "--out_dir", str(out_dir),
            "--top_tests", str(int(args.plots_top_tests)),
            "--top_signals", str(int(args.plots_top_signals)),
        ]
        if args.use_smoothing_defaults:
            cmd_plots.append("--use_smoothing_defaults")
        _run(cmd_plots, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at plots\n', encoding='utf-8')
        print('STOP requested at plots.')
        return


    # 7) Pareto trade-off (optional)
    if args.run_pareto:
        pareto_dir = out_dir / "pareto_tradeoff"
        cmd_pareto = [
            sys.executable, str(project_root / "calibration" / "pipeline_npz_pareto_tradeoff_v1.py"),
            "--osc_dir", str(osc_dir),
            "--signals_csv", str(out_dir / "FINAL_SIGNALS.csv"),
            "--out_dir", str(pareto_dir),
            "--model", str(args.model),
            "--worker", str(args.worker),
            "--suite_json", str(args.suite_json),
            "--base_json", str(out_dir / "fitted_base_final.json"),
            "--fit_ranges_json", str(args.fit_ranges_json),
            "--auto_scale", str(args.auto_scale),
            "--n_init", str(int(args.n_init)),
            "--n_best", str(int(args.n_best)),
            "--loss", str(args.loss),
            "--f_scale", str(float(args.f_scale)),
            "--max_nfev", str(int(getattr(args, "max_nfev", 220))),
            "--global_init", str(args.global_init),
            "--de_maxiter", str(int(args.de_maxiter)),
            "--de_popsize", str(int(args.de_popsize)),
            "--de_tol", str(float(args.de_tol)),
            "--block_corr_thr", str(float(args.block_corr_thr)),
            "--block_max_size", str(int(args.block_max_size)),
            "--block_sweeps", str(int(args.block_sweeps)),
            "--block_max_nfev", str(int(args.block_max_nfev)),
            "--block_polish_nfev", str(int(args.block_polish_nfev)),
            "--groupA", str(args.pareto_groupA),
            "--groupB", str(args.pareto_groupB),
            "--points", str(int(args.pareto_points)),
            "--log_gain_span", str(float(args.pareto_log_gain_span)),
            "--stop_file", str(stop_file),
        ]
        if args.use_smoothing_defaults:
            cmd_pareto.append("--use_smoothing_defaults")
        if bool(getattr(args, "de_polish", False)):
            cmd_pareto.append("--de_polish")
        if not bool(getattr(args, "disable_block_refine", False)):
            cmd_pareto.append("--block_refine")
        if args.pareto_resume:
            cmd_pareto.append("--resume")

        _run(cmd_pareto, cwd=project_root)

        # bootstrap stability for pareto points (fast; no re-simulation)
        if (not bool(getattr(args, "no_tradeoff_bootstrap", False))) and int(getattr(args, "tradeoff_bootstrap_reps", 0)) > 0:
            try:
                cmd_pbs = [
                    sys.executable, str(project_root / "calibration" / "tradeoff_bootstrap_stability_v1.py"),
                    "--points_csv", str(pareto_out_dir / "pareto_points.csv"),
                    "--points_base_dir", str(pareto_out_dir),
                    "--groupA", str(args.pareto_groupA),
                    "--groupB", str(args.pareto_groupB),
                    "--reps", str(int(args.tradeoff_bootstrap_reps)),
                    "--seed", str(int(args.tradeoff_bootstrap_seed)),
                    "--out_csv", str(pareto_out_dir / "pareto_bootstrap_summary.csv"),
                ]
                _run(cmd_pbs, cwd=project_root)
            except Exception:
                pass


    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at pareto\n', encoding='utf-8')
        print('STOP requested at pareto.')
        return



    
    # 7b) epsilon-constraint trade-off (optional)
    if getattr(args, 'run_epsilon', False):
        eps_out_dir = out_dir / 'epsilon_tradeoff'
        cmd_eps = [
            sys.executable, str(project_root / 'calibration' / 'pipeline_npz_epsilon_constraint_v2.py'),
            '--osc_dir', str(osc_dir),
            '--signals_csv', str(out_dir / 'FINAL_SIGNALS.csv'),
            '--out_dir', str(eps_out_dir),
            '--model', str(args.model),
            '--worker', str(args.worker),
            '--suite_json', str(args.suite_json),
            '--base_json', str(args.base_json),
            '--fit_ranges_json', str(args.fit_ranges_json),
            '--auto_scale', str(args.auto_scale),
            '--n_init', str(int(args.n_init)),
            '--n_best', str(int(args.n_best)),
            '--max_nfev', str(int(args.max_nfev)),
            '--loss', str(args.loss),
            '--f_scale', str(float(args.f_scale)),
            '--global_init', str(args.global_init),
            '--de_maxiter', str(int(args.de_maxiter)),
            '--de_popsize', str(int(args.de_popsize)),
            '--de_tol', str(float(args.de_tol)),
            '--block_corr_thr', str(float(args.block_corr_thr)),
            '--block_max_size', str(int(args.block_max_size)),
            '--block_sweeps', str(int(args.block_sweeps)),
            '--block_max_nfev', str(int(args.block_max_nfev)),
            '--block_polish_nfev', str(int(args.block_polish_nfev)),
            '--primary', str(getattr(args, 'epsilon_primary', 'pressure')),
            '--constraint', str(getattr(args, 'epsilon_constraint', 'kinematics')),
            '--points', str(int(getattr(args, 'epsilon_points', 9))),
            '--min_points', str(int(getattr(args, 'epsilon_min_points', 5))),
            '--max_points', str(int(getattr(args, 'epsilon_points', 9))),
            '--min_gap_norm', str(float(getattr(args, 'epsilon_min_gap_norm', 0.18))),
            '--bootstrap_reps', str(int(0 if bool(getattr(args, 'no_tradeoff_bootstrap', False)) else int(getattr(args, 'tradeoff_bootstrap_reps', 200)))),
            '--bootstrap_seed', str(int(getattr(args, 'tradeoff_bootstrap_seed', 0))),
            '--epsilon_penalty', str(float(getattr(args, 'epsilon_penalty', 2000.0))),
            '--stop_file', str(stop_file),
        ]
        if args.use_smoothing_defaults:
            cmd_eps.append('--use_smoothing_defaults')
        if bool(getattr(args, 'de_polish', False)):
            cmd_eps.append('--de_polish')
        if not bool(getattr(args, 'disable_block_refine', False)):
            cmd_eps.append('--block_refine')
        if bool(getattr(args, 'epsilon_adaptive', False)):
            cmd_eps.append('--adaptive')
        if bool(getattr(args, 'epsilon_resume', False)):
            cmd_eps.append('--resume')
        _run(cmd_eps, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at epsilon\n', encoding='utf-8')
        print('STOP requested at epsilon.')
        return


    # 7c) Trade-off decision support (auto, cheap)
    if (args.run_pareto or getattr(args, 'run_epsilon', False)) and (not bool(getattr(args, 'skip_tradeoff_decision', False))):
        cmd_dec = [
            sys.executable, str(project_root / "calibration" / "tradeoff_decision_support_v2.py"),
            "--run_dir", str(out_dir),
            "--select_point", str(getattr(args, "tradeoff_select_point", "knee")),
            "--margin", str(float(getattr(args, "tradeoff_margin", 0.05))),
            "--out_prefix", "tradeoff",
        ]
        if bool(getattr(args, "no_tradeoff_bootstrap", False)) or int(getattr(args, "tradeoff_bootstrap_reps", 0)) <= 0:
            cmd_dec += ["--use_bootstrap", "no"]
        else:
            cmd_dec += ["--use_bootstrap", "auto", "--min_feasible_prob", str(float(getattr(args, "tradeoff_min_feasible_prob", 0.8)))]
        _run(cmd_dec, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at tradeoff_decision\n', encoding='utf-8')
        print('STOP requested at tradeoff_decision.')
        return


    # 8) full report
    cmd_full = [
        sys.executable, str(project_root / "calibration" / "report_full_from_run_v1.py"),
        "--run_dir", str(out_dir),
    ]
    _run(cmd_full, cwd=project_root)

    if _should_stop(stop_file):
        (out_dir / 'STOPPED.txt').write_text('stopped at full_report\n', encoding='utf-8')
        print('STOP requested at full_report.')
        return


    # summary
    summary = []
    summary.append("# Autopilot v7 summary\n")
    summary.append(f"- osc_dir: `{osc_dir}`")
    summary.append(f"- out_dir: `{out_dir}`\n")
    summary.append("## Outputs\n")
    summary.append(f"- FINAL_SIGNALS.csv: `{(out_dir / 'FINAL_SIGNALS.csv').name}`")
    summary.append(f"- mapping_final.json: `{(out_dir / 'mapping_final.json').name}`")
    summary.append(f"- fit_report_final.json: `{(out_dir / 'fit_report_final.json').name}`")
    summary.append(f"- action_plan.md: `{(out_dir / 'action_plan.md').name}`")
    summary.append(f"- REPORT_FULL.md: `{(out_dir / 'REPORT_FULL.md').name}`")
    if args.run_oed:
        summary.append(f"- oed_report.json: `{(out_dir / 'oed_report.json').name}`")
    if args.make_reduced_suite and suite_reduced.exists():
        summary.append(f"- suite_reduced.json: `{suite_reduced.name}`")
    if args.run_profile_auto and selected_params:
        summary.append(f"- profile_report.json: `{profile_report.name}`")
        summary.append(f"- profile_plots/: `{profile_plots_dir.name}/`")
    if args.run_plots:
        summary.append(f"- plots/: `{(out_dir / 'plots').name}/`")
    if args.run_pareto:
        summary.append(f"- pareto_tradeoff/: `{(out_dir / 'pareto_tradeoff').name}/`")
    if getattr(args, 'run_epsilon', False):
        summary.append(f"- epsilon_tradeoff/: `{(out_dir / 'epsilon_tradeoff').name}/`")
    if (args.run_pareto or getattr(args, 'run_epsilon', False)) and (not bool(getattr(args, 'skip_tradeoff_decision', False))):
        summary.append(f"- tradeoff decision: `{(out_dir / 'tradeoff_decision.md').name}`, `{(out_dir / 'tradeoff_selected_base.json').name}`")

    summary.append("\n## Next\n")
    summary.append("1) Открой REPORT_FULL.md: там топ тесты/сигналы, графики, профили, action_plan.")
    summary.append("2) Если качество на holdout хуже: увеличь разнообразие тестов/пересмотри сигналы или используй suite_reduced только как ускоритель.")
    summary.append("3) Если параметры у границ/в сильной корреляции: либо фиксируй, либо добавляй тесты (см. OED D-opt order).")
    _save_text("\n".join(summary), out_dir / "AUTOPILOT_SUMMARY.md")

    print("\nDONE. Autopilot v6 outputs in:", out_dir)



if __name__ == "__main__":
    main()