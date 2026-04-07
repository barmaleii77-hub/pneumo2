# -*- coding: utf-8 -*-
"""pipeline_npz_iterative_signals_v4.py

Итеративная полностью автоматическая калибровка по NPZ (v4):

v4 добавляет к v3 ещё одну инженерно‑практичную вещь:
4) Multi-fidelity по тестам: в coarse шаге можно автоматически выбрать подмножество наиболее "информативных" тестов (по NPZ измерениям),
   чтобы ускорить заход в правильный бассейн решения.

v3 добавляет к v2:
3) Coarse-to-fine (multi-fidelity): сначала быстрый fit на прореженных измерениях (meas_stride>1), затем уточнение на полном сигнале.

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
python calibration/pipeline_npz_iterative_signals_v4.py --osc_dir <OSC_DIR> --iters 2 --param_staging auto --staging_only_final

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


def _maybe_select_coarse_tests(
    project_root: Path,
    osc_dir: Path,
    mapping_path: Path,
    it_dir: Path,
    args: argparse.Namespace,
    holdout_tests: List[str],
    stop_file: Optional[Path],
) -> List[str]:
    """Автоматический выбор поднабора тестов для coarse шага.

    Реализация — через select_informative_tests_v1.py (по NPZ измерениям).
    Результат кэшируется в it_dir/coarse_tests.json и переиспользуется при --resume.
    """
    mode = str(getattr(args, "coarse_test_subset_mode", "none")).lower().strip()
    if mode in ("", "none", "off", "0", "false"):
        return []
    if not bool(getattr(args, "coarse_to_fine", False)):
        return []
    if int(getattr(args, "coarse_meas_stride", 1)) <= 1:
        return []

    cache_json = it_dir / "coarse_tests.json"
    if bool(getattr(args, "resume", False)) and cache_json.exists():
        try:
            obj = json.loads(cache_json.read_text(encoding="utf-8"))
            sel = obj.get("selected_tests", [])
            if isinstance(sel, list) and sel:
                return [str(s) for s in sel if str(s).strip()]
        except Exception:
            pass

    # build
    cmd = [
        sys.executable, str(project_root / "calibration" / "select_informative_tests_v1.py"),
        "--osc_dir", str(osc_dir),
        "--mapping_json", str(mapping_path),
        "--mode", "meas_variation",
        "--exclude_tests", ",".join([t for t in holdout_tests if t]),
        "--frac", str(float(getattr(args, "coarse_test_subset_frac", 0.5))),
        "--max_tests", str(int(getattr(args, "coarse_test_subset_max_tests", 6))),
        "--min_tests", str(int(getattr(args, "coarse_test_subset_min_tests", 3))),
        "--out_json", str(cache_json),
    ]
    if stop_file is not None and stop_file.exists():
        raise SystemExit("STOP requested")
    _run(cmd, cwd=project_root)

    try:
        obj = json.loads(cache_json.read_text(encoding="utf-8"))
        sel = obj.get("selected_tests", [])
        if isinstance(sel, list):
            return [str(s) for s in sel if str(s).strip()]
    except Exception:
        pass
    return []



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
    """Последовательный staged fit (stage0->stageK) с опциональным coarse-to-fine.

    Идея coarse-to-fine:
    - coarse: meas_stride>1 + меньшие бюджеты (n_init/n_best/max_nfev) для быстрого входа в «бассейн»
    - fine: meas_stride=1 (или args.meas_stride) + полноценные бюджеты для точного доводочного фита

    Финальный результат кладёт в it_dir/fit_report.json, it_dir/fit_details.json, it_dir/fitted_base.json.
    Дополнительно сохраняет артефакты coarse шагов (если включено).
    """
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
    stage_files = sorted(
        ranges_dir.glob("stage*_ranges.json"),
        key=lambda p: int(p.stem.replace("stage", "").replace("_ranges", "")),
    )
    if not stage_files:
        raise RuntimeError(f"No stage*_ranges.json in {ranges_dir}")

    # 3) sequential fit
    stage_base = base_json
    last_out = None
    last_rep = None
    last_det = None

    coarse_tests: List[str] = []
    # coarse test subset is chosen once per iteration and reused across stages
    if bool(getattr(args, "coarse_to_fine", False)) and int(getattr(args, "coarse_meas_stride", 1)) > 1:
        coarse_tests = _maybe_select_coarse_tests(project_root, osc_dir, mapping_path, it_dir, args, holdout_tests, stop_file)
        if coarse_tests:
            (it_dir / "coarse_tests_selected.txt").write_text("\n".join(coarse_tests) + "\n", encoding="utf-8")

    for si, rng_json in enumerate(stage_files):
        if _should_stop(stop_file):
            raise SystemExit("STOP requested")

        out_json = it_dir / f"fitted_base_stage{si}.json"
        rep_json = it_dir / f"fit_report_stage{si}.json"
        det_json = it_dir / f"fit_details_stage{si}.json"

        # resume per stage (fine output is the canonical stage output)
        if args.resume and out_json.exists() and rep_json.exists() and det_json.exists():
            print(f"[resume] stage{si}: skip (exists)")
            stage_base = out_json
            last_out, last_rep, last_det = out_json, rep_json, det_json
            continue

        do_coarse = bool(getattr(args, "coarse_to_fine", False)) and int(getattr(args, "coarse_meas_stride", 1)) > 1
        if do_coarse and (not bool(getattr(args, "coarse_each_stage", False))) and si != 0:
            do_coarse = False

        base_for_fine = stage_base

        # --- coarse step (optional)
        if do_coarse:
            coarse_out = it_dir / f"fitted_base_stage{si}_coarse.json"
            coarse_rep = it_dir / f"fit_report_stage{si}_coarse.json"
            coarse_det = it_dir / f"fit_details_stage{si}_coarse.json"

            if not (args.resume and coarse_out.exists() and coarse_rep.exists() and coarse_det.exists()):
                cmd_coarse = [
                    sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
                    "--model", str(project_root / args.model),
                    "--worker", str(project_root / args.worker),
                    "--suite_json", str(project_root / args.suite_json),
                    "--osc_dir", str(osc_dir),
                    "--base_json", str(stage_base),
                    "--fit_ranges_json", str(rng_json),
                    "--mapping_json", str(mapping_path),
                    "--time_col", str(args.time_col),
                    "--meas_stride", str(int(getattr(args, "coarse_meas_stride", 5))),
                    "--n_init", str(int(getattr(args, "coarse_n_init", 12))),
                    "--n_best", str(int(getattr(args, "coarse_n_best", 2))),
                    "--loss", str(args.loss),
                    "--f_scale", str(float(args.f_scale)),
                    "--max_nfev", str(int(getattr(args, "coarse_max_nfev", 80))),
                    "--global_init", str(getattr(args, "coarse_global_init", "none")),
                    "--de_maxiter", str(int(args.de_maxiter)),
                    "--de_popsize", str(int(args.de_popsize)),
                    "--de_tol", str(float(args.de_tol)),
        "--cem_pop", str(int(args.cem_pop)),
        "--cem_iters", str(int(args.cem_iters)),
        "--cem_elite_frac", str(float(args.cem_elite_frac)),
        "--cem_alpha", str(float(args.cem_alpha)),
        "--cem_init_sigma", str(float(args.cem_init_sigma)),
        "--cem_min_sigma", str(float(args.cem_min_sigma)),
        "--cem_time_budget_sec", str(float(args.cem_time_budget_sec)),
        "--cem_patience", str(int(args.cem_patience)),
        "--cem_min_improve_rel", str(float(args.cem_min_improve_rel)),
                    "--surr_model", str(getattr(args, "surr_model", "rf")),
                    "--surr_init_samples", str(int(getattr(args, "coarse_surr_init_samples", getattr(args, "surr_init_samples", 24)))),
                    "--surr_iters", str(int(getattr(args, "coarse_surr_iters", getattr(args, "surr_iters", 8)))),
                    "--surr_batch", str(int(getattr(args, "coarse_surr_batch", getattr(args, "surr_batch", 2)))),
                    "--surr_candidate_pool", str(int(getattr(args, "coarse_surr_candidate_pool", getattr(args, "surr_candidate_pool", 3000)))),
                    "--surr_kappa", str(float(getattr(args, "surr_kappa", 2.0))),
                    "--surr_random_frac", str(float(getattr(args, "surr_random_frac", 0.2))),
                    "--surr_max_evals", str(int(getattr(args, "coarse_surr_max_evals", getattr(args, "surr_max_evals", 0)))),
                    "--surr_n_estimators", str(int(getattr(args, "surr_n_estimators", 200))),
                    "--surr_gp_alpha", str(float(getattr(args, "surr_gp_alpha", 1e-6))),
                    "--surr_gp_restarts", str(int(getattr(args, "surr_gp_restarts", 2))),
                    "--surr_patience", str(int(getattr(args, "coarse_surr_patience", getattr(args, "surr_patience", 3)))),
                    "--surr_min_improve_abs", str(float(getattr(args, "coarse_surr_min_improve_abs", getattr(args, "surr_min_improve_abs", 0.0)))),
                    "--surr_min_improve_rel", str(float(getattr(args, "coarse_surr_min_improve_rel", getattr(args, "surr_min_improve_rel", 0.001)))),
                    "--surr_time_budget_sec", str(float(getattr(args, "coarse_surr_time_budget_sec", getattr(args, "surr_time_budget_sec", 0.0)))),
                    "--surr_save_csv", str(getattr(args, "surr_save_csv", "")),
                    "--block_corr_thr", str(float(args.block_corr_thr)),

                    "--block_max_size", str(int(args.block_max_size)),
                    "--block_sweeps", str(int(args.block_sweeps)),
                    "--block_max_nfev", str(int(args.block_max_nfev)),
                    "--block_polish_nfev", str(int(args.block_polish_nfev)),
                    "--record_stride", str(int(args.record_stride)),
                    "--auto_scale", str(args.auto_scale),
                    "--details_json", str(coarse_det),
                    "--out_json", str(coarse_out),
                    "--report_json", str(coarse_rep),
                ]
                if stop_file is not None:
                    cmd_coarse += ["--stop_file", str(stop_file)]
                if holdout_tests:
                    cmd_coarse += ["--holdout_tests", ",".join(holdout_tests)]
                if coarse_tests:
                    cmd_coarse += ["--only_tests", ",".join(coarse_tests)]
                if args.use_smoothing_defaults:
                    cmd_coarse.append("--use_smoothing_defaults")
                if bool(getattr(args, "de_polish", False)) and str(getattr(args, "coarse_global_init", "none")).lower().strip() == "de":
                    cmd_coarse.append("--de_polish")

                # deliberately skip block_refine in coarse step (экономим)
                _run(cmd_coarse, cwd=project_root)

            if coarse_out.exists():
                base_for_fine = coarse_out

        # --- fine step (stage output)
        cmd_fit = [
            sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--suite_json", str(project_root / args.suite_json),
            "--osc_dir", str(osc_dir),
            "--base_json", str(base_for_fine),
            "--fit_ranges_json", str(rng_json),
            "--mapping_json", str(mapping_path),
            "--time_col", str(args.time_col),
            "--meas_stride", str(int(getattr(args, "meas_stride", 1))),
            "--n_init", str(int(args.n_init)),
            "--n_best", str(int(args.n_best)),
            "--loss", str(args.loss),
            "--f_scale", str(float(args.f_scale)),
            "--max_nfev", str(int(args.max_nfev)),
            "--global_init", str(args.global_init),
            "--de_maxiter", str(int(args.de_maxiter)),
            "--de_popsize", str(int(args.de_popsize)),
            "--de_tol", str(float(args.de_tol)),
        "--cem_pop", str(int(args.cem_pop)),
        "--cem_iters", str(int(args.cem_iters)),
        "--cem_elite_frac", str(float(args.cem_elite_frac)),
        "--cem_alpha", str(float(args.cem_alpha)),
        "--cem_init_sigma", str(float(args.cem_init_sigma)),
        "--cem_min_sigma", str(float(args.cem_min_sigma)),
        "--cem_time_budget_sec", str(float(args.cem_time_budget_sec)),
        "--cem_patience", str(int(args.cem_patience)),
        "--cem_min_improve_rel", str(float(args.cem_min_improve_rel)),
            "--surr_model", str(getattr(args, "surr_model", "rf")),
            "--surr_init_samples", str(int(getattr(args, "surr_init_samples", 24))),
            "--surr_iters", str(int(getattr(args, "surr_iters", 8))),
            "--surr_batch", str(int(getattr(args, "surr_batch", 2))),
            "--surr_candidate_pool", str(int(getattr(args, "surr_candidate_pool", 3000))),
            "--surr_kappa", str(float(getattr(args, "surr_kappa", 2.0))),
            "--surr_random_frac", str(float(getattr(args, "surr_random_frac", 0.2))),
            "--surr_max_evals", str(int(getattr(args, "surr_max_evals", 0))),
            "--surr_n_estimators", str(int(getattr(args, "surr_n_estimators", 200))),
            "--surr_gp_alpha", str(float(getattr(args, "surr_gp_alpha", 1e-6))),
            "--surr_gp_restarts", str(int(getattr(args, "surr_gp_restarts", 2))),
            "--surr_patience", str(int(getattr(args, "surr_patience", 3))),
            "--surr_min_improve_abs", str(float(getattr(args, "surr_min_improve_abs", 0.0))),
            "--surr_min_improve_rel", str(float(getattr(args, "surr_min_improve_rel", 0.001))),
            "--surr_time_budget_sec", str(float(getattr(args, "surr_time_budget_sec", 0.0))),
            "--surr_save_csv", str(getattr(args, "surr_save_csv", "")),
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
    """Один fit (без staging), но с опциональным coarse-to-fine."""
    fit_out = it_dir / "fitted_base.json"
    fit_report = it_dir / "fit_report.json"
    fit_details = it_dir / "fit_details.json"

    if args.resume and fit_out.exists() and fit_report.exists() and fit_details.exists():
        print("[resume] single fit: skip (exists)")
        return

    base_for_fine = base_json

    do_coarse = bool(getattr(args, "coarse_to_fine", False)) and int(getattr(args, "coarse_meas_stride", 1)) > 1
    coarse_tests: List[str] = []
    if do_coarse:
        coarse_tests = _maybe_select_coarse_tests(project_root, osc_dir, mapping_path, it_dir, args, holdout_tests, stop_file)
        if coarse_tests:
            (it_dir / "coarse_tests_selected.txt").write_text("\n".join(coarse_tests) + "\n", encoding="utf-8")
    if do_coarse:
        coarse_out = it_dir / "fitted_base_coarse.json"
        coarse_report = it_dir / "fit_report_coarse.json"
        coarse_details = it_dir / "fit_details_coarse.json"

        if not (args.resume and coarse_out.exists() and coarse_report.exists() and coarse_details.exists()):
            cmd_coarse = [
                sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
                "--model", str(project_root / args.model),
                "--worker", str(project_root / args.worker),
                "--suite_json", str(project_root / args.suite_json),
                "--osc_dir", str(osc_dir),
                "--base_json", str(base_json),
                "--fit_ranges_json", str(fit_ranges_json),
                "--mapping_json", str(mapping_path),
                "--time_col", str(args.time_col),
                "--meas_stride", str(int(getattr(args, "coarse_meas_stride", 5))),
                "--n_init", str(int(getattr(args, "coarse_n_init", 12))),
                "--n_best", str(int(getattr(args, "coarse_n_best", 2))),
                "--loss", str(args.loss),
                "--f_scale", str(float(args.f_scale)),
                "--max_nfev", str(int(getattr(args, "coarse_max_nfev", 80))),
                "--global_init", str(getattr(args, "coarse_global_init", "none")),
                "--de_maxiter", str(int(args.de_maxiter)),
                "--de_popsize", str(int(args.de_popsize)),
                "--de_tol", str(float(args.de_tol)),
        "--cem_pop", str(int(args.cem_pop)),
        "--cem_iters", str(int(args.cem_iters)),
        "--cem_elite_frac", str(float(args.cem_elite_frac)),
        "--cem_alpha", str(float(args.cem_alpha)),
        "--cem_init_sigma", str(float(args.cem_init_sigma)),
        "--cem_min_sigma", str(float(args.cem_min_sigma)),
        "--cem_time_budget_sec", str(float(args.cem_time_budget_sec)),
        "--cem_patience", str(int(args.cem_patience)),
        "--cem_min_improve_rel", str(float(args.cem_min_improve_rel)),
                "--surr_model", str(getattr(args, "surr_model", "rf")),
                "--surr_init_samples", str(int(getattr(args, "coarse_surr_init_samples", getattr(args, "surr_init_samples", 24)))),
                "--surr_iters", str(int(getattr(args, "coarse_surr_iters", getattr(args, "surr_iters", 8)))),
                "--surr_batch", str(int(getattr(args, "coarse_surr_batch", getattr(args, "surr_batch", 2)))),
                "--surr_candidate_pool", str(int(getattr(args, "coarse_surr_candidate_pool", getattr(args, "surr_candidate_pool", 3000)))),
                "--surr_kappa", str(float(getattr(args, "surr_kappa", 2.0))),
                "--surr_random_frac", str(float(getattr(args, "surr_random_frac", 0.2))),
                "--surr_max_evals", str(int(getattr(args, "coarse_surr_max_evals", getattr(args, "surr_max_evals", 0)))),
                "--surr_n_estimators", str(int(getattr(args, "surr_n_estimators", 200))),
                "--surr_gp_alpha", str(float(getattr(args, "surr_gp_alpha", 1e-6))),
                "--surr_gp_restarts", str(int(getattr(args, "surr_gp_restarts", 2))),
                "--surr_patience", str(int(getattr(args, "coarse_surr_patience", getattr(args, "surr_patience", 3)))),
                "--surr_min_improve_abs", str(float(getattr(args, "coarse_surr_min_improve_abs", getattr(args, "surr_min_improve_abs", 0.0)))),
                "--surr_min_improve_rel", str(float(getattr(args, "coarse_surr_min_improve_rel", getattr(args, "surr_min_improve_rel", 0.001)))),
                "--surr_time_budget_sec", str(float(getattr(args, "coarse_surr_time_budget_sec", getattr(args, "surr_time_budget_sec", 0.0)))),
                "--surr_save_csv", str(getattr(args, "surr_save_csv", "")),
                "--block_corr_thr", str(float(args.block_corr_thr)),
                "--block_max_size", str(int(args.block_max_size)),
                "--block_sweeps", str(int(args.block_sweeps)),
                "--block_max_nfev", str(int(args.block_max_nfev)),
                "--block_polish_nfev", str(int(args.block_polish_nfev)),
                "--record_stride", str(int(args.record_stride)),
                "--auto_scale", str(args.auto_scale),
                "--details_json", str(coarse_details),
                "--out_json", str(coarse_out),
                "--report_json", str(coarse_report),
            ]
            if stop_file is not None:
                cmd_coarse += ["--stop_file", str(stop_file)]
            if holdout_tests:
                cmd_coarse += ["--holdout_tests", ",".join(holdout_tests)]
            if coarse_tests:
                cmd_coarse += ["--only_tests", ",".join(coarse_tests)]
            if args.use_smoothing_defaults:
                cmd_coarse.append("--use_smoothing_defaults")
            if bool(getattr(args, "de_polish", False)) and str(getattr(args, "coarse_global_init", "none")).lower().strip() == "de":
                cmd_coarse.append("--de_polish")
            # deliberately skip block_refine in coarse step

            _run(cmd_coarse, cwd=project_root)

        if coarse_out.exists():
            base_for_fine = coarse_out

    cmd = [
        sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
        "--model", str(project_root / args.model),
        "--worker", str(project_root / args.worker),
        "--suite_json", str(project_root / args.suite_json),
        "--osc_dir", str(osc_dir),
        "--base_json", str(base_for_fine),
        "--fit_ranges_json", str(fit_ranges_json),
        "--mapping_json", str(mapping_path),
        "--time_col", str(args.time_col),
        "--meas_stride", str(int(getattr(args, "meas_stride", 1))),
        "--n_init", str(int(args.n_init)),
        "--n_best", str(int(args.n_best)),
        "--loss", str(args.loss),
        "--f_scale", str(float(args.f_scale)),
        "--max_nfev", str(int(args.max_nfev)),
        "--global_init", str(args.global_init),
        "--de_maxiter", str(int(args.de_maxiter)),
        "--de_popsize", str(int(args.de_popsize)),
        "--de_tol", str(float(args.de_tol)),
        "--cem_pop", str(int(args.cem_pop)),
        "--cem_iters", str(int(args.cem_iters)),
        "--cem_elite_frac", str(float(args.cem_elite_frac)),
        "--cem_alpha", str(float(args.cem_alpha)),
        "--cem_init_sigma", str(float(args.cem_init_sigma)),
        "--cem_min_sigma", str(float(args.cem_min_sigma)),
        "--cem_time_budget_sec", str(float(args.cem_time_budget_sec)),
        "--cem_patience", str(int(args.cem_patience)),
        "--cem_min_improve_rel", str(float(args.cem_min_improve_rel)),
        "--surr_model", str(getattr(args, "surr_model", "rf")),
        "--surr_init_samples", str(int(getattr(args, "surr_init_samples", 24))),
        "--surr_iters", str(int(getattr(args, "surr_iters", 8))),
        "--surr_batch", str(int(getattr(args, "surr_batch", 2))),
        "--surr_candidate_pool", str(int(getattr(args, "surr_candidate_pool", 3000))),
        "--surr_kappa", str(float(getattr(args, "surr_kappa", 2.0))),
        "--surr_random_frac", str(float(getattr(args, "surr_random_frac", 0.2))),
        "--surr_max_evals", str(int(getattr(args, "surr_max_evals", 0))),
        "--surr_n_estimators", str(int(getattr(args, "surr_n_estimators", 200))),
        "--surr_gp_alpha", str(float(getattr(args, "surr_gp_alpha", 1e-6))),
        "--surr_gp_restarts", str(int(getattr(args, "surr_gp_restarts", 2))),
        "--surr_patience", str(int(getattr(args, "surr_patience", 3))),
        "--surr_min_improve_abs", str(float(getattr(args, "surr_min_improve_abs", 0.0))),
        "--surr_min_improve_rel", str(float(getattr(args, "surr_min_improve_rel", 0.001))),
        "--surr_time_budget_sec", str(float(getattr(args, "surr_time_budget_sec", 0.0))),
        "--surr_save_csv", str(getattr(args, "surr_save_csv", "")),
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
    ap.add_argument("--global_init", default="none", choices=["none", "de", "surrogate", "cem"], help="Глобальная инициализация перед least_squares: none|de")
    ap.add_argument("--de_maxiter", type=int, default=8)
    ap.add_argument("--de_popsize", type=int, default=10)
    ap.add_argument("--de_tol", type=float, default=0.01)
    
    # CEM global init (Cross-Entropy Method)
    ap.add_argument("--cem_pop", type=int, default=64)
    ap.add_argument("--cem_iters", type=int, default=8)
    ap.add_argument("--cem_elite_frac", type=float, default=0.15)
    ap.add_argument("--cem_alpha", type=float, default=0.7)
    ap.add_argument("--cem_init_sigma", type=float, default=0.35)
    ap.add_argument("--cem_min_sigma", type=float, default=0.05)
    ap.add_argument("--cem_diag_only", action="store_true")
    ap.add_argument("--cem_time_budget_sec", type=float, default=0.0)
    ap.add_argument("--cem_patience", type=int, default=3)
    ap.add_argument("--cem_min_improve_rel", type=float, default=0.001)

    # Surrogate global init (SMBO-like). Используется только если --global_init surrogate (или coarse_global_init surrogate).
    ap.add_argument("--surr_model", default="rf", choices=["rf", "gp"])
    ap.add_argument("--surr_init_samples", type=int, default=24)
    ap.add_argument("--surr_iters", type=int, default=8)
    ap.add_argument("--surr_batch", type=int, default=2)
    ap.add_argument("--surr_candidate_pool", type=int, default=3000)
    ap.add_argument("--surr_kappa", type=float, default=2.0)
    ap.add_argument("--surr_random_frac", type=float, default=0.2)
    ap.add_argument("--surr_max_evals", type=int, default=0)
    ap.add_argument("--surr_n_estimators", type=int, default=200)
    ap.add_argument("--surr_gp_alpha", type=float, default=1e-6)
    ap.add_argument("--surr_gp_restarts", type=int, default=2)
    ap.add_argument("--surr_save_csv", default="")

    ap.add_argument("--surr_patience", type=int, default=3)
    ap.add_argument("--surr_min_improve_abs", type=float, default=0.0)
    ap.add_argument("--surr_min_improve_rel", type=float, default=0.001)
    ap.add_argument("--surr_time_budget_sec", type=float, default=0.0)

    # Coarse overrides (используются только в coarse шаге, если coarse_global_init=surrogate)
    ap.add_argument("--coarse_surr_init_samples", type=int, default=16)
    ap.add_argument("--coarse_surr_iters", type=int, default=6)
    ap.add_argument("--coarse_surr_batch", type=int, default=2)
    ap.add_argument("--coarse_surr_candidate_pool", type=int, default=2000)
    ap.add_argument("--coarse_surr_max_evals", type=int, default=0)

    ap.add_argument("--coarse_surr_patience", type=int, default=2)
    ap.add_argument("--coarse_surr_min_improve_abs", type=float, default=0.0)
    ap.add_argument("--coarse_surr_min_improve_rel", type=float, default=0.002)
    ap.add_argument("--coarse_surr_time_budget_sec", type=float, default=0.0)




    # Block refine (optional)
    ap.add_argument("--block_refine", action="store_true", help="Включить block coordinate refinement внутри fit_worker")
    ap.add_argument("--block_corr_thr", type=float, default=0.85)
    ap.add_argument("--block_max_size", type=int, default=6)
    ap.add_argument("--block_sweeps", type=int, default=2)
    ap.add_argument("--block_max_nfev", type=int, default=120)
    ap.add_argument("--block_polish_nfev", type=int, default=120)
    ap.add_argument("--record_stride", type=int, default=1)
    ap.add_argument("--meas_stride", type=int, default=1, help="Проредить измерения по времени (перед интерполяцией): брать каждый N-й отсчёт. 1=без прореживания.")

    # coarse-to-fine (multi-fidelity)
    ap.add_argument("--coarse_to_fine", action="store_true", help="Coarse-to-fine: сначала быстрый fit на прореженных измерениях (meas_stride>1), затем уточнение на полном сигнале.")
    ap.add_argument("--coarse_meas_stride", type=int, default=5, help="meas_stride для coarse шага")
    ap.add_argument("--coarse_n_init", type=int, default=12, help="n_init для coarse шага")
    ap.add_argument("--coarse_n_best", type=int, default=2, help="n_best для coarse шага")
    ap.add_argument("--coarse_max_nfev", type=int, default=80, help="max_nfev для coarse шага")
    ap.add_argument("--coarse_global_init", default="none", choices=["none", "de", "surrogate", "cem"], help="global_init для coarse шага (обычно none)")
    ap.add_argument("--coarse_each_stage", action="store_true", help="Если включён param_staging: делать coarse-to-fine на каждой стадии (дороже). По умолчанию — только на stage0.")

    # coarse test subset (multi-fidelity by tests)
    ap.add_argument("--coarse_test_subset_mode", default="meas_variation", choices=["none", "meas_variation"],
                    help="Подмножество тестов в coarse шаге. meas_variation=по амплитуде измерений (NPZ) с учётом weight")
    ap.add_argument("--coarse_test_subset_frac", type=float, default=0.5)
    ap.add_argument("--coarse_test_subset_max_tests", type=int, default=6)
    ap.add_argument("--coarse_test_subset_min_tests", type=int, default=3)

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
