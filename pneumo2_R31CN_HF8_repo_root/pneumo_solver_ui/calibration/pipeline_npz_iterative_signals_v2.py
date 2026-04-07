# -*- coding: utf-8 -*-
"""pipeline_npz_iterative_signals_v2.py

Итеративная полностью автоматическая калибровка по NPZ (v2):

v2 добавляет две инженерно‑практичные вещи:
1) Resume/checkpoint: можно перезапускать пайплайн и он пропустит уже
   посчитанные итерации/стадии (важно, когда симуляция дорогая).
2) Параметрический staging (поэтапное раскрытие параметров):
   вместо того чтобы фитить все параметры сразу, выполняется последовательность
   фитов по стадиям (например объёмы → дроссели → пороги → прочее).

Схема по сигналам (как в v1):
  - источник сигналов: signals.csv (или auto bootstrap из NPZ)
  - на каждой итерации:
      1) signals.csv -> mapping.json
      2) fit по suite (один раз или staged)
      3) report_from_details -> report.md + tests.csv + signals.csv (per-test)
      4) signals_refine -> signals_refined.csv
  - следующая итерация использует signals_refined.csv

Запуск:
python calibration/pipeline_npz_iterative_signals_v2.py --osc_dir <OSC_DIR> --iters 2 --param_staging auto --staging_only_final

"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _run(cmd: List[str], cwd: Optional[Path] = None):
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def _should_stop(stop_file: Optional[Path]) -> bool:
    try:
        return stop_file is not None and stop_file.exists()
    except Exception:
        return False


def _save_json(obj: Any, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_tests_index(osc_dir: Path) -> List[str]:
    idx_path = osc_dir / "tests_index.csv"
    if not idx_path.exists():
        return []
    df = pd.read_csv(idx_path, encoding="utf-8-sig")
    if "имя_теста" not in df.columns:
        return []
    return [str(x) for x in df["имя_теста"].tolist()]


def _choose_holdout(tests: List[str], frac: float, seed: int) -> List[str]:
    tests_u = list(dict.fromkeys([t.strip() for t in tests if t.strip()]))
    if not tests_u:
        return []
    k = int(round(len(tests_u) * float(frac)))
    k = max(0, min(k, len(tests_u)))
    rng = random.Random(int(seed))
    rng.shuffle(tests_u)
    return sorted(tests_u[:k])


def _find_latest_signals_csv(project_root: Path) -> Optional[Path]:
    cr = project_root / "calibration_runs"
    if not cr.exists():
        return None
    cands = list(cr.glob("RUN_*/signals.csv"))
    if not cands:
        return None
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def _bootstrap_signals_from_npz(osc_dir: Path, out_signals_csv: Path, project_root: Path, mode: str = "extended"):
    """Если signals.csv не задан — делаем bootstrap через npz_autosuggest_mapping_v2."""
    tmp_mapping = out_signals_csv.with_suffix(".mapping_bootstrap.json")
    _run([
        sys.executable, str(project_root / "calibration" / "npz_autosuggest_mapping_v2.py"),
        "--osc_dir", str(osc_dir),
        "--out_mapping", str(tmp_mapping),
        "--mode", str(mode),
    ], cwd=project_root)

    mapping = json.loads(tmp_mapping.read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = []
    for m in mapping:
        rows.append({
            "meas_table": m.get("meas_table", "main"),
            "meas_col": m.get("meas_col", ""),
            "model_key": m.get("model_key", ""),
            "w_raw": float(m.get("weight", 1.0)),
            "enabled": 1,
            "reason": "bootstrap",
        })
    df = pd.DataFrame(rows)
    out_signals_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_signals_csv, index=False, encoding="utf-8-sig")
    print(f"Bootstrapped signals.csv: {out_signals_csv} (n={len(df)})")


def _stage_fit(
    project_root: Path,
    osc_dir: Path,
    mapping_path: Path,
    base_json: Path,
    fit_ranges_json: Path,
    cur_signals: Path,
    it_dir: Path,
    args: argparse.Namespace,
    holdout_tests: List[str],
    stop_file: Optional[Path],
) -> None:
    """Последовательный staged fit (stage0->stageK). Финальный результат кладёт в fit_report.json etc."""
    staging_dir = it_dir / "param_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1) build stages
    cmd_stages = [
        sys.executable, str(project_root / "calibration" / "param_staging_v1.py"),
        "--fit_ranges_json", str(fit_ranges_json),
        "--signals_csv", str(cur_signals),
        "--method", str(args.param_staging),
        "--min_stage_size", str(int(args.staging_min_stage_size)),
        "--top_fraction", str(float(args.staging_top_fraction)),
        "--out_dir", str(staging_dir),
    ]
    _run(cmd_stages, cwd=project_root)

    # 2) enumerate stage ranges (union)
    ranges_dir = staging_dir / "stage_ranges"
    stage_files = sorted(ranges_dir.glob("stage*_ranges.json"), key=lambda p: int(p.stem.replace("stage", "").replace("_ranges", "")))
    if not stage_files:
        raise RuntimeError(f"No stage*_ranges.json in {ranges_dir}")

    # 3) sequential fit
    stage_base = base_json
    last_out = None
    last_rep = None
    last_det = None

    for si, rng_json in enumerate(stage_files):
        if _should_stop(stop_file):
            raise SystemExit("STOP requested")

        out_json = it_dir / f"fitted_base_stage{si}.json"
        rep_json = it_dir / f"fit_report_stage{si}.json"
        det_json = it_dir / f"fit_details_stage{si}.json"

        # resume per stage
        if args.resume and out_json.exists() and rep_json.exists() and det_json.exists():
            print(f"[resume] stage{si}: skip (exists)")
            stage_base = out_json
            last_out, last_rep, last_det = out_json, rep_json, det_json
            continue

        cmd_fit = [
            sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--suite_json", str(project_root / args.suite_json),
            "--osc_dir", str(osc_dir),
            "--base_json", str(stage_base),
            "--fit_ranges_json", str(rng_json),
            "--mapping_json", str(mapping_path),
            "--time_col", str(args.time_col),
            "--n_init", str(int(args.n_init)),
            "--n_best", str(int(args.n_best)),
            "--loss", str(args.loss),
            "--f_scale", str(float(args.f_scale)),
            "--max_nfev", str(int(args.max_nfev)),
            "--global_init", str(args.global_init),
            "--de_maxiter", str(int(args.de_maxiter)),
            "--de_popsize", str(int(args.de_popsize)),
            "--de_tol", str(float(args.de_tol)),
            "--block_corr_thr", str(float(args.block_corr_thr)),
            "--block_max_size", str(int(args.block_max_size)),
            "--block_sweeps", str(int(args.block_sweeps)),
            "--block_max_nfev", str(int(args.block_max_nfev)),
            "--block_polish_nfev", str(int(args.block_polish_nfev)),
            "--record_stride", str(int(args.record_stride)),
            "--auto_scale", str(args.auto_scale),
            "--details_json", str(det_json),
            "--out_json", str(out_json),
            "--report_json", str(rep_json),
        ]
        if stop_file is not None:
            cmd_fit += ["--stop_file", str(stop_file)]
        if holdout_tests:
            cmd_fit += ["--holdout_tests", ",".join(holdout_tests)]
        if args.use_smoothing_defaults:
            cmd_fit.append("--use_smoothing_defaults")
        if bool(getattr(args, "de_polish", False)) and str(args.global_init).lower().strip() == "de":
            cmd_fit.append("--de_polish")
        if bool(getattr(args, "block_refine", False)):
            cmd_fit.append("--block_refine")

        _run(cmd_fit, cwd=project_root)

        stage_base = out_json
        last_out, last_rep, last_det = out_json, rep_json, det_json

    assert last_out is not None and last_rep is not None and last_det is not None

    # 4) copy last stage -> canonical names
    (it_dir / "fitted_base.json").write_bytes(last_out.read_bytes())
    (it_dir / "fit_report.json").write_bytes(last_rep.read_bytes())
    (it_dir / "fit_details.json").write_bytes(last_det.read_bytes())


def _single_fit(
    project_root: Path,
    osc_dir: Path,
    mapping_path: Path,
    base_json: Path,
    fit_ranges_json: Path,
    it_dir: Path,
    args: argparse.Namespace,
    holdout_tests: List[str],
    stop_file: Optional[Path],
) -> None:
    fit_out = it_dir / "fitted_base.json"
    fit_report = it_dir / "fit_report.json"
    fit_details = it_dir / "fit_details.json"

    if args.resume and fit_out.exists() and fit_report.exists() and fit_details.exists():
        print("[resume] single fit: skip (exists)")
        return

    cmd = [
        sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
        "--model", str(project_root / args.model),
        "--worker", str(project_root / args.worker),
        "--suite_json", str(project_root / args.suite_json),
        "--osc_dir", str(osc_dir),
        "--base_json", str(base_json),
        "--fit_ranges_json", str(fit_ranges_json),
        "--mapping_json", str(mapping_path),
        "--time_col", str(args.time_col),
        "--n_init", str(int(args.n_init)),
        "--n_best", str(int(args.n_best)),
        "--loss", str(args.loss),
        "--f_scale", str(float(args.f_scale)),
        "--max_nfev", str(int(args.max_nfev)),
        "--global_init", str(args.global_init),
        "--de_maxiter", str(int(args.de_maxiter)),
        "--de_popsize", str(int(args.de_popsize)),
        "--de_tol", str(float(args.de_tol)),
        "--block_corr_thr", str(float(args.block_corr_thr)),
        "--block_max_size", str(int(args.block_max_size)),
        "--block_sweeps", str(int(args.block_sweeps)),
        "--block_max_nfev", str(int(args.block_max_nfev)),
        "--block_polish_nfev", str(int(args.block_polish_nfev)),
        "--record_stride", str(int(args.record_stride)),
        "--auto_scale", str(args.auto_scale),
        "--details_json", str(fit_details),
        "--out_json", str(fit_out),
        "--report_json", str(fit_report),
    ]
    if stop_file is not None:
        cmd += ["--stop_file", str(stop_file)]
    if holdout_tests:
        cmd += ["--holdout_tests", ",".join(holdout_tests)]
    if args.use_smoothing_defaults:
        cmd.append("--use_smoothing_defaults")
    if bool(getattr(args, "de_polish", False)) and str(args.global_init).lower().strip() == "de":
        cmd.append("--de_polish")
    if bool(getattr(args, "block_refine", False)):
        cmd.append("--block_refine")

    _run(cmd, cwd=project_root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--signals_csv", default="auto", help="path/dir/auto")
    ap.add_argument("--out_dir", default="")
    ap.add_argument("--bootstrap_mode", default="extended", help="minimal/main_all/extended")
    ap.add_argument("--iters", type=int, default=2)
    ap.add_argument("--stop_file", default="", help="Если файл существует — мягко остановиться")

    # resume/budget
    ap.add_argument("--resume", action="store_true", help="Пропускать уже посчитанные итерации/стадии")
    ap.add_argument("--time_budget_sec", type=float, default=0.0, help="Ограничение по времени (0 = без лимита)")

    # project defaults
    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", default="default_suite.json")
    ap.add_argument("--base_json", default="default_base.json")
    ap.add_argument("--fit_ranges_json", default="default_ranges.json")

    # fit
    ap.add_argument("--time_col", default="auto")
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--n_init", type=int, default=32)
    ap.add_argument("--n_best", type=int, default=6)
    ap.add_argument("--max_nfev", type=int, default=220)
    # Global init (optional)
    ap.add_argument("--global_init", default="none", choices=["none", "de"], help="Глобальная инициализация перед least_squares: none|de")
    ap.add_argument("--de_maxiter", type=int, default=8)
    ap.add_argument("--de_popsize", type=int, default=10)
    ap.add_argument("--de_tol", type=float, default=0.01)
    ap.add_argument("--de_polish", action="store_true")

    # Block refine (optional)
    ap.add_argument("--block_refine", action="store_true", help="Включить block coordinate refinement внутри fit_worker")
    ap.add_argument("--block_corr_thr", type=float, default=0.85)
    ap.add_argument("--block_max_size", type=int, default=6)
    ap.add_argument("--block_sweeps", type=int, default=2)
    ap.add_argument("--block_max_nfev", type=int, default=120)
    ap.add_argument("--block_polish_nfev", type=int, default=120)
    ap.add_argument("--record_stride", type=int, default=1)
    ap.add_argument("--use_smoothing_defaults", action="store_true")
    ap.add_argument("--auto_scale", default="mad")

    # holdout
    ap.add_argument("--holdout_frac", type=float, default=0.0)
    ap.add_argument("--holdout_seed", type=int, default=1)

    # refine rules
    ap.add_argument("--ref_min_total_points", type=int, default=20)
    ap.add_argument("--ref_downweight_nrmse", type=float, default=10.0)
    ap.add_argument("--ref_disable_nrmse", type=float, default=25.0)
    ap.add_argument("--ref_min_keep", type=int, default=6)
    ap.add_argument("--ref_keep_top_sse", type=int, default=0)

    # param staging
    ap.add_argument("--param_staging", default="off", choices=["off", "auto", "heuristic", "sensitivity", "fim_corr"],
                    help="поэтапная подгонка параметров: off|auto|heuristic|sensitivity")
    ap.add_argument("--staging_only_final", action="store_true", help="делать staging только на последней итерации")
    ap.add_argument("--staging_min_stage_size", type=int, default=2)
    ap.add_argument("--staging_top_fraction", type=float, default=0.7)

    args = ap.parse_args()

    t0 = time.time()
    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else None

    project_root = Path(".")
    osc_dir = Path(args.osc_dir)
    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")

    def budget_ok() -> bool:
        if float(args.time_budget_sec) <= 0:
            return True
        return (time.time() - t0) <= float(args.time_budget_sec)

    if _should_stop(stop_file):
        print("STOP requested before start.")
        return

    # out_dir
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_dir = project_root / "calibration_runs" / f"RUN_{ts}_iter"
    out_dir.mkdir(parents=True, exist_ok=True)

    # holdout selection (fixed across iters)
    holdout_tests: List[str] = []
    if float(args.holdout_frac) > 0.0:
        tests = _read_tests_index(osc_dir)
        holdout_tests = _choose_holdout(tests, frac=float(args.holdout_frac), seed=int(args.holdout_seed))
    _save_json({"holdout_tests": holdout_tests}, out_dir / "holdout_selection.json")

    # resolve initial signals.csv
    sig_arg = str(args.signals_csv).strip()
    if sig_arg.lower() == "auto":
        cand1 = osc_dir / "signals.csv"
        if cand1.exists():
            signals_csv = cand1
        else:
            cand2 = _find_latest_signals_csv(project_root)
            signals_csv = cand2 if cand2 is not None else None
    else:
        p = Path(sig_arg)
        if p.is_dir():
            p = p / "signals.csv"
        signals_csv = p if p.exists() else None

    # if still None -> bootstrap
    iter0_dir = out_dir / "iter0"
    iter0_dir.mkdir(parents=True, exist_ok=True)
    if signals_csv is None:
        signals_csv_path = iter0_dir / "signals_bootstrap.csv"
        _bootstrap_signals_from_npz(osc_dir, signals_csv_path, project_root, mode=str(args.bootstrap_mode))
    else:
        signals_csv_path = iter0_dir / "signals_input.csv"
        df0 = pd.read_csv(signals_csv, encoding="utf-8-sig")
        df0.to_csv(signals_csv_path, index=False, encoding="utf-8-sig")
        print(f"Using signals_csv: {signals_csv} -> {signals_csv_path}")

    # iterative runs
    cur_signals = signals_csv_path

    for it in range(int(args.iters)):
        if _should_stop(stop_file):
            (out_dir / "STOPPED.txt").write_text("stopped\n", encoding="utf-8")
            print("STOP requested. Exiting iterative loop.")
            break
        if not budget_ok():
            (out_dir / "STOPPED.txt").write_text("time budget reached\n", encoding="utf-8")
            print("Time budget reached. Exiting iterative loop.")
            break

        it_dir = out_dir / f"iter{it}"
        it_dir.mkdir(parents=True, exist_ok=True)

        # resume whole iteration
        if args.resume and (it_dir / "signals_refined.csv").exists() and (it_dir / "fit_report.json").exists():
            print(f"[resume] iter{it}: skip (signals_refined + fit_report exist)")
            cur_signals = it_dir / "signals_refined.csv"
            continue

        # 1) signals -> mapping
        mapping_path = it_dir / "mapping.json"
        if (not args.resume) or (not mapping_path.exists()):
            _run([
                sys.executable, str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
                "--signals_csv", str(cur_signals),
                "--out_mapping", str(mapping_path),
                "--osc_dir", str(osc_dir),
                "--test_num", "1",
                "--drop_missing",
            ], cwd=project_root)

        if _should_stop(stop_file) or (not budget_ok()):
            (out_dir / "STOPPED.txt").write_text("stopped\n", encoding="utf-8")
            print("STOP/budget requested after mapping. Exiting.")
            break

        # 2) fit (single or staged)
        do_staging = (str(args.param_staging).lower().strip() != "off")
        if args.staging_only_final and it != int(args.iters) - 1:
            do_staging = False

        base_json = project_root / args.base_json
        fit_ranges_json = project_root / args.fit_ranges_json

        if do_staging:
            _stage_fit(
                project_root=project_root,
                osc_dir=osc_dir,
                mapping_path=mapping_path,
                base_json=base_json,
                fit_ranges_json=fit_ranges_json,
                cur_signals=cur_signals,
                it_dir=it_dir,
                args=args,
                holdout_tests=holdout_tests,
                stop_file=stop_file,
            )
        else:
            _single_fit(
                project_root=project_root,
                osc_dir=osc_dir,
                mapping_path=mapping_path,
                base_json=base_json,
                fit_ranges_json=fit_ranges_json,
                it_dir=it_dir,
                args=args,
                holdout_tests=holdout_tests,
                stop_file=stop_file,
            )

        if _should_stop(stop_file) or (not budget_ok()):
            (out_dir / "STOPPED.txt").write_text("stopped\n", encoding="utf-8")
            print("STOP/budget requested after fit. Exiting.")
            break

        # 3) report
        out_md = it_dir / "report.md"
        out_tests_csv = it_dir / "tests.csv"
        out_signals_csv = it_dir / "signals.csv"  # per-test
        if (not args.resume) or (not out_md.exists()) or (not out_signals_csv.exists()):
            _run([
                sys.executable, str(project_root / "calibration" / "report_from_details_v1.py"),
                "--fit_report", str(it_dir / "fit_report.json"),
                "--fit_details", str(it_dir / "fit_details.json"),
                "--out_md", str(out_md),
                "--out_tests_csv", str(out_tests_csv),
                "--out_signals_csv", str(out_signals_csv),
            ], cwd=project_root)

        # 4) refine for next iteration
        refined = it_dir / "signals_refined.csv"
        if (not args.resume) or (not refined.exists()):
            _run([
                sys.executable, str(project_root / "calibration" / "signals_refine_v1.py"),
                "--signals_csv", str(out_signals_csv),
                "--out_signals_csv", str(refined),
                "--min_total_points", str(int(args.ref_min_total_points)),
                "--downweight_nrmse", str(float(args.ref_downweight_nrmse)),
                "--disable_nrmse", str(float(args.ref_disable_nrmse)),
                "--min_keep", str(int(args.ref_min_keep)),
                "--keep_top_sse", str(int(args.ref_keep_top_sse)),
            ], cwd=project_root)

        cur_signals = refined

    # final pointer
    (out_dir / "FINAL_SIGNALS.csv").write_text(Path(cur_signals).read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    print("\nDONE. Iterative outputs in:", out_dir)


if __name__ == "__main__":
    main()
