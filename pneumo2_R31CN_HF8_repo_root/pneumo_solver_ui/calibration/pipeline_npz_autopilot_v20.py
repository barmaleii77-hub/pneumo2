# -*- coding: utf-8 -*-
"""pipeline_npz_autopilot_v20.py

Autopilot v20 = v19 (bootstrap + autopilot v18) + post-processing:
- System Influence report (пневматика + кинематика)
- Influence-guided parameter staging plan
- Rebuild REPORT_FULL.md to include these sections

Зачем:
- "вшить" физический анализ влияния в стандартный автопилот,
  чтобы оптимизация была направленной, а не вслепую.

Запуск (из корня pneumo_solver_ui):
  python calibration/pipeline_npz_autopilot_v20.py --osc_dir <OSC_DIR> --signals_csv auto --run_time_align --run_oed

Примечание:
- Это обёртка поверх v19, которая не ломает старые сценарии.
- Все нераспознанные аргументы пробрасываются в v19/v18.

"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Set


def _run(cmd: List[str], cwd: Path) -> None:
    print("\n>>>", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _strip_duplicate_args(extra: List[str], keys_with_value: Set[str], keys_flag: Set[str]) -> List[str]:
    out: List[str] = []
    i = 0
    while i < len(extra):
        a = extra[i]
        if a in keys_flag:
            i += 1
            continue
        if a in keys_with_value:
            i += 2
            continue
        out.append(a)
        i += 1
    return out


def _load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser(description="Autopilot v20 (v19 + System Influence + influence staging)")

    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--out_dir", default="")
    ap.add_argument("--signals_csv", default="auto")

    # same as v19 defaults
    ap.add_argument("--no_bootstrap", action="store_true")
    ap.add_argument("--bootstrap_mode", default="minimal", choices=["minimal", "main_all", "extended"])

    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", default="default_suite.json")
    ap.add_argument("--base_json", default="default_base.json")
    ap.add_argument("--fit_ranges_json", default="default_ranges.json")
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    # v20 additions
    ap.add_argument("--skip_system_influence", action="store_true", help="Не запускать system_influence_report")
    ap.add_argument("--skip_influence_staging", action="store_true", help="Не строить план стадий по влиянию")
    ap.add_argument("--rebuild_report_full", action="store_true", help="Пересобрать REPORT_FULL.md (рекомендуется)")
    ap.add_argument("--run_influence_staged_refine", action="store_true", help="После staging запустить staged refine (долго)")

    args, extra = ap.parse_known_args()

    project_root = Path(".")
    osc_dir = Path(args.osc_dir)
    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")

    # out_dir (фиксируем здесь, чтобы знать куда писать пост-отчёты)
    if str(args.out_dir).strip():
        out_dir = Path(args.out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_dir = project_root / "calibration_runs" / f"RUN_{ts}_autopilot_v20"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run v19 as subprocess
    v19_cmd = [
        sys.executable,
        str(project_root / "calibration" / "pipeline_npz_autopilot_v19.py"),
        "--osc_dir",
        str(osc_dir),
        "--out_dir",
        str(out_dir),
        "--signals_csv",
        str(args.signals_csv),
        "--bootstrap_mode",
        str(args.bootstrap_mode),
        "--model",
        str(args.model),
        "--worker",
        str(args.worker),
        "--suite_json",
        str(args.suite_json),
        "--base_json",
        str(args.base_json),
        "--fit_ranges_json",
        str(args.fit_ranges_json),
    ]
    if bool(args.no_bootstrap):
        v19_cmd.append("--no_bootstrap")
    if bool(args.use_smoothing_defaults):
        v19_cmd.append("--use_smoothing_defaults")

    # Remove duplicates if caller already added them.
    keys_with_value = {
        "--osc_dir", "--out_dir", "--signals_csv",
        "--bootstrap_mode",
        "--model", "--worker", "--suite_json", "--base_json", "--fit_ranges_json",
    }
    keys_flag = {"--no_bootstrap", "--use_smoothing_defaults"}
    extra_f = _strip_duplicate_args(list(extra), keys_with_value, keys_flag)

    v19_cmd.extend(extra_f)
    _run(v19_cmd, cwd=project_root)

    # v20 meta
    meta = {
        "version": "v20_wrapper",
        "ts": time.time(),
        "osc_dir": str(osc_dir),
        "out_dir": str(out_dir),
        "signals_csv": str(args.signals_csv),
        "model": str(args.model),
        "worker": str(args.worker),
        "suite_json": str(args.suite_json),
        "base_json": str(args.base_json),
        "fit_ranges_json": str(args.fit_ranges_json),
        "use_smoothing_defaults": bool(args.use_smoothing_defaults),
        "skip_system_influence": bool(args.skip_system_influence),
        "skip_influence_staging": bool(args.skip_influence_staging),
        "rebuild_report_full": bool(args.rebuild_report_full),
        "run_influence_staged_refine": bool(args.run_influence_staged_refine),
        "extra": list(extra_f),
    }
    (out_dir / "AUTOPILOT_V20_WRAPPER.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Post: System influence
    if not bool(args.skip_system_influence):
        try:
            _run([
                sys.executable,
                str(project_root / "calibration" / "system_influence_report_v1.py"),
                "--run_dir",
                str(out_dir),
            ], cwd=project_root)
        except Exception as e:
            print(f"[WARN] system_influence_report failed: {e}")

    # Post: Influence staging
    if not bool(args.skip_influence_staging):
        try:
            # choose fit_ranges: pruned if available
            fit_ranges_p = None
            pruned = out_dir / "param_prune" / "fit_ranges_pruned.json"
            if pruned.exists():
                fit_ranges_p = pruned
            else:
                # try to read from wrapper meta (v19)
                v19m = out_dir / "AUTOPILOT_V19_WRAPPER.json"
                if v19m.exists():
                    m = _load_json(v19m)
                    fr = str(m.get("fit_ranges_json", ""))
                    if fr:
                        cand = (project_root / fr).resolve() if not Path(fr).is_absolute() else Path(fr)
                        if cand.exists():
                            fit_ranges_p = cand
                if fit_ranges_p is None:
                    # fallback to project default
                    cand = project_root / str(args.fit_ranges_json)
                    fit_ranges_p = cand if cand.exists() else None

            sysinf_json = out_dir / "system_influence.json"
            oed_json = out_dir / "oed_report.json"

            if fit_ranges_p is not None and fit_ranges_p.exists():
                stage_out = out_dir / "param_staging_influence"
                cmd = [
                    sys.executable,
                    str(project_root / "calibration" / "param_staging_v3_influence.py"),
                    "--fit_ranges_json",
                    str(fit_ranges_p),
                    "--out_dir",
                    str(stage_out),
                ]
                if oed_json.exists():
                    cmd += ["--oed_report_json", str(oed_json)]
                if sysinf_json.exists():
                    cmd += ["--system_influence_json", str(sysinf_json)]
                _run(cmd, cwd=project_root)
            else:
                print("[WARN] fit_ranges_json not found, skip influence staging")
        except Exception as e:
            print(f"[WARN] influence staging failed: {e}")

    # Optional: staged refine based on influence staging (can be long)
    if bool(args.run_influence_staged_refine):
        try:
            _run([
                sys.executable,
                str(project_root / "calibration" / "pipeline_npz_influence_staged_refine_v1.py"),
                "--run_dir",
                str(out_dir),
            ], cwd=project_root)
        except Exception as e:
            print(f"[WARN] staged refine failed: {e}")

    # Rebuild REPORT_FULL (include new sections)
    if bool(args.rebuild_report_full):
        try:
            _run([
                sys.executable,
                str(project_root / "calibration" / "report_full_from_run_v1.py"),
                "--run_dir",
                str(out_dir),
            ], cwd=project_root)
        except Exception as e:
            print(f"[WARN] rebuild REPORT_FULL failed: {e}")

    print(f"[OK] Autopilot v20 done: {out_dir}")


if __name__ == "__main__":
    main()
