# -*- coding: utf-8 -*-
"""pipeline_npz_from_signals_csv_v2.py

Автоматический пайплайн калибровки *по NPZ-логам* с использованием
*signals.csv* как источника списка сигналов (и базовых весов).

Почему отдельный pipeline:
  pipeline_npz_oneclick_v1.py умеет автогенерить mapping эвристикой.
  Здесь основной источник правды — signals.csv: что именно фитить,
  какие столбцы использовать и какие базовые веса.

Один запуск:
  1) mapping_auto.json <- signals.csv (с проверкой по NPZ)
  2) holdout выборка (опционально)
  3) fit_worker_v3_suite_identify.py
  4) report_from_details_v1.py -> report.md + tests.csv + signals.csv
  5) (опционально) OED/FIM (oed_worker_v1_fim.py)
  6) (опционально) profile likelihood

Пример:
  python calibration/pipeline_npz_from_signals_csv_v2.py \
    --osc_dir osc_logs/RUN_... \
    --signals_csv calibration_runs/RUN_xxx/signals.csv \
    --auto_scale mad --holdout_frac 0.2 \
    --use_smoothing_defaults \
    --run_oed --run_profile
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import numpy as np


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _run(cmd: List[str], cwd: Optional[Path] = None):
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def _read_tests_index(osc_dir: Path) -> List[str]:
    import pandas as pd
    idx_path = osc_dir / "tests_index.csv"
    if not idx_path.exists():
        raise FileNotFoundError(f"Не найден {idx_path}")
    df = pd.read_csv(idx_path, encoding="utf-8-sig")
    if "имя_теста" not in df.columns:
        raise RuntimeError(f"tests_index.csv не содержит 'имя_теста'. Есть: {list(df.columns)}")
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
    """Найти последний signals.csv в calibration_runs/RUN_*/signals.csv."""
    cr = project_root / "calibration_runs"
    if not cr.exists():
        return None
    cands = list(cr.glob("RUN_*/signals.csv"))
    if not cands:
        return None
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True, help="RUN_... с tests_index.csv и Txx_osc.npz")
    ap.add_argument("--signals_csv", required=True, help="signals.csv (из предыдущего run/report)")
    ap.add_argument("--out_dir", default="", help="куда писать результаты")

    # project files (defaults: запуск из корня)
    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", default="default_suite.json")
    ap.add_argument("--base_json", default="default_base.json")
    ap.add_argument("--fit_ranges_json", default="default_ranges.json")

    # fit options
    ap.add_argument("--time_col", default="auto")
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--n_init", type=int, default=32)
    ap.add_argument("--n_best", type=int, default=6)
    ap.add_argument("--max_nfev", type=int, default=220)
    ap.add_argument("--record_stride", type=int, default=1)
    ap.add_argument("--use_smoothing_defaults", action="store_true")
    ap.add_argument("--auto_scale", default="mad", help="none/mad/std/range")

    # holdout
    ap.add_argument("--holdout_tests", default="")
    ap.add_argument("--holdout_frac", type=float, default=0.0)
    ap.add_argument("--holdout_seed", type=int, default=1)

    # mapping from signals.csv
    ap.add_argument("--signals_top_n", type=int, default=0, help="если >0 — взять топ-N сигналов по SSE из signals.csv")

    # OED
    ap.add_argument("--run_oed", action="store_true", help="запустить OED/FIM после fit")
    ap.add_argument("--oed_sample_stride", type=int, default=8)
    ap.add_argument("--oed_record_stride", type=int, default=1)
    ap.add_argument("--oed_max_tests", type=int, default=10)
    ap.add_argument("--oed_rel_step", type=float, default=1e-2)

    # profile
    ap.add_argument("--run_profile", action="store_true")
    ap.add_argument("--profile_params", default="")
    ap.add_argument("--profile_span", type=float, default=0.35)
    ap.add_argument("--profile_n_points", type=int, default=21)

    args = ap.parse_args()

    osc_dir = Path(args.osc_dir)
    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")
    # signals.csv can be:
    #  - explicit path to file
    #  - directory containing signals.csv
    #  - 'auto' (take osc_dir/signals.csv if exists, else latest from calibration_runs)
    sig_arg = str(args.signals_csv).strip()
    if sig_arg.lower() == "auto":
        cand1 = osc_dir / "signals.csv"
        if cand1.exists():
            signals_csv = cand1
        else:
            cand2 = _find_latest_signals_csv(Path("."))
            if cand2 is None:
                raise SystemExit(
                    "signals_csv=auto: не найден signals.csv ни в osc_dir, ни в calibration_runs/RUN_*/signals.csv"
                )
            signals_csv = cand2
            print(f"signals_csv=auto -> {signals_csv}")
    else:
        signals_csv = Path(sig_arg)
        if signals_csv.is_dir():
            signals_csv = signals_csv / "signals.csv"
        if not signals_csv.exists():
            raise SystemExit(f"signals_csv не найден: {signals_csv}")

    project_root = Path(".")
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_dir = project_root / "calibration_runs" / f"RUN_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) mapping from signals.csv (validated against NPZ)
    mapping_path = out_dir / "mapping_from_signals.json"
    _run([
        sys.executable, str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
        "--signals_csv", str(signals_csv),
        "--out_mapping", str(mapping_path),
        "--top_n", str(int(args.signals_top_n)),
        "--osc_dir", str(osc_dir),
        "--test_num", "1",
        "--drop_missing",
    ], cwd=project_root)

    # holdout list
    holdout_tests = [s.strip() for s in str(args.holdout_tests).split(",") if s.strip()]
    if (not holdout_tests) and float(args.holdout_frac) > 0.0:
        tests = _read_tests_index(osc_dir)
        holdout_tests = _choose_holdout(tests, frac=float(args.holdout_frac), seed=int(args.holdout_seed))
    _save_json({"holdout_tests": holdout_tests}, out_dir / "holdout_selection.json")

    # 2) fit
    fit_out = out_dir / "fitted_base.json"
    fit_report = out_dir / "fit_report.json"
    fit_details = out_dir / "fit_details.json"
    fit_cmd = [
        sys.executable, str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
        "--model", str(project_root / args.model),
        "--worker", str(project_root / args.worker),
        "--suite_json", str(project_root / args.suite_json),
        "--osc_dir", str(osc_dir),
        "--base_json", str(project_root / args.base_json),
        "--fit_ranges_json", str(project_root / args.fit_ranges_json),
        "--mapping_json", str(mapping_path),
        "--time_col", str(args.time_col),
        "--n_init", str(int(args.n_init)),
        "--n_best", str(int(args.n_best)),
        "--loss", str(args.loss),
        "--f_scale", str(float(args.f_scale)),
        "--max_nfev", str(int(args.max_nfev)),
        "--record_stride", str(int(args.record_stride)),
        "--auto_scale", str(args.auto_scale),
        "--details_json", str(fit_details),
        "--out_json", str(fit_out),
        "--report_json", str(fit_report),
    ]
    if holdout_tests:
        fit_cmd += ["--holdout_tests", ",".join(holdout_tests)]
    if args.use_smoothing_defaults:
        fit_cmd += ["--use_smoothing_defaults"]
    _run(fit_cmd, cwd=project_root)

    # 3) report
    out_md = out_dir / "report.md"
    out_tests_csv = out_dir / "tests.csv"
    out_signals_csv = out_dir / "signals.csv"
    _run([
        sys.executable, str(project_root / "calibration" / "report_from_details_v1.py"),
        "--fit_report", str(fit_report),
        "--fit_details", str(fit_details),
        "--out_md", str(out_md),
        "--out_tests_csv", str(out_tests_csv),
        "--out_signals_csv", str(out_signals_csv),
    ], cwd=project_root)

    # 4) OED/FIM (optional)
    if args.run_oed:
        oed_report = out_dir / "oed_report.json"
        _run([
            sys.executable, str(project_root / "calibration" / "oed_worker_v1_fim.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--suite_json", str(project_root / args.suite_json),
            "--base_json", str(project_root / args.base_json),
            "--fit_ranges_json", str(project_root / args.fit_ranges_json),
            # observables_json допускает формат mapping.json
            "--observables_json", str(mapping_path),
            "--time_col", "время_с",
            "--sample_stride", str(int(args.oed_sample_stride)),
            "--record_stride", str(int(args.oed_record_stride)),
            "--max_tests", str(int(args.oed_max_tests)),
            "--rel_step", str(float(args.oed_rel_step)),
            "--report_json", str(oed_report),
        ] + ( ["--use_smoothing_defaults"] if args.use_smoothing_defaults else [] ), cwd=project_root)

    # 5) profile (optional)
    if args.run_profile:
        prof_dir = out_dir / "profile_out"
        prof_dir.mkdir(parents=True, exist_ok=True)
        prof_json = out_dir / "profile_report.json"
        # auto-pick top-3 by std if profile_params not set
        prof_params = [s.strip() for s in str(args.profile_params).split(",") if s.strip()]
        if not prof_params:
            try:
                rep = json.loads(Path(fit_report).read_text(encoding="utf-8"))
                keys = rep.get("keys", [])
                cov = rep.get("cov")
                if keys and cov is not None:
                    import numpy as np
                    cov_arr = np.asarray(cov, dtype=float)
                    if cov_arr.ndim == 2 and cov_arr.shape[0] == cov_arr.shape[1] == len(keys):
                        std = np.sqrt(np.clip(np.diag(cov_arr), 0.0, np.inf))
                        order = list(np.argsort(-std))
                        prof_params = [str(keys[i]) for i in order[: min(3, len(keys))] if np.isfinite(std[i]) and std[i] > 0]
            except Exception:
                prof_params = []

        if not prof_params:
            print("run_profile: пропущено, не удалось выбрать profile_params")
            print("  (передайте --profile_params или проверьте cov в fit_report.json)")
        else:
            _run([
            sys.executable, str(project_root / "calibration" / "profile_worker_v1_likelihood.py"),
            "--model", str(project_root / args.model),
            "--worker", str(project_root / args.worker),
            "--suite_json", str(project_root / args.suite_json),
            "--osc_dir", str(osc_dir),
            "--theta_star_json", str(fit_out),
            "--fit_ranges_json", str(project_root / args.fit_ranges_json),
            "--mapping_json", str(mapping_path),
            "--time_col", str(args.time_col),
            "--profile_params", ",".join(prof_params),
            "--span", str(float(args.profile_span)),
            "--n_points", str(int(args.profile_n_points)),
            "--loss", "linear",
            "--out_json", str(prof_json),
            "--out_dir", str(prof_dir),
            ] + ( ["--use_smoothing_defaults"] if args.use_smoothing_defaults else [] ), cwd=project_root)

    print("\nDONE. Outputs in:", out_dir)


if __name__ == "__main__":
    main()
