# -*- coding: utf-8 -*-
"""pipeline_npz_autopilot_v19.py

Autopilot "всё автоматически" для калибровки по NPZ + multiobjective.

v19 = v18 + bootstrap, когда signals.csv отсутствует.

Зачем bootstrap:
- В первом запуске у вас часто есть только osc_dir с NPZ-логами.
- Нормальный рабочий процесс в проекте опирается на signals.csv (список сигналов, веса и группы).
- Если signals.csv нет, v19 делает "seed" прогон через pipeline_npz_oneclick_v1.py (эвристическая привязка сигналов
  по именам столбцов в NPZ) и получает первый signals.csv. Затем запускается полноценный autopilot v18.

Запуск (из корня pneumo_v7):
  python calibration/pipeline_npz_autopilot_v19.py --osc_dir <OSC_DIR> --run_time_align --run_oed --run_profile_auto --run_plots

Важно:
- Этот файл — обёртка. Основной пайплайн живёт в pipeline_npz_autopilot_v18.py.
- Все аргументы, которые не распознаны v19, пробрасываются в v18 как есть.

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


def _find_latest_signals_csv(project_root: Path) -> Optional[Path]:
    cr = project_root / "calibration_runs"
    if not cr.exists():
        return None
    cands = list(cr.glob("RUN_*/signals.csv"))
    if not cands:
        return None
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def _resolve_signals_csv(sig_arg: str, osc_dir: Path, project_root: Path) -> Optional[Path]:
    s = str(sig_arg).strip()
    if s.lower() != "auto":
        p = Path(s)
        if p.is_dir():
            p = p / "signals.csv"
        return p if p.exists() else None

    # auto: prefer osc_dir/signals.csv, else latest from calibration_runs
    cand1 = osc_dir / "signals.csv"
    if cand1.exists():
        return cand1
    return _find_latest_signals_csv(project_root)


def _strip_duplicate_args(extra: List[str], keys_with_value: Set[str], keys_flag: Set[str]) -> List[str]:
    """Удалить из extra аргументы, которые мы задаём сами.

    Это защита от двойной передачи в v18 (например, если внешний слой уже добавил --out_dir).
    """
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Autopilot v19 (v18 + bootstrap for missing signals.csv)")

    # Required / routing
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--out_dir", default="")
    ap.add_argument("--signals_csv", default="auto", help="auto|path|dir. auto: osc_dir/signals.csv or latest calibration_runs")

    # Bootstrap controls
    ap.add_argument("--no_bootstrap", action="store_true", help="Если signals.csv не найден — не запускать seed oneclick, а падать")
    ap.add_argument("--bootstrap_mode", default="minimal", choices=["minimal", "main_all", "extended"],
                    help="Режим автосопоставления сигналов для seed oneclick")

    # Project files (keep in sync with v18/v1 defaults)
    ap.add_argument("--model", default="model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py")
    ap.add_argument("--worker", default="opt_worker_v3_margins_energy.py")
    ap.add_argument("--suite_json", default="default_suite.json")
    ap.add_argument("--base_json", default="default_base.json")
    ap.add_argument("--fit_ranges_json", default="default_ranges.json")
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    args, extra = ap.parse_known_args()

    project_root = Path(".")
    osc_dir = Path(args.osc_dir)
    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")

    # Частый кейс: пользователь запускает autopilot в корне проекта или до экспорта NPZ.
    # Тогда лучше мягко завершиться с подсказкой, чем сваливаться в CalledProcessError.
    if not list(osc_dir.glob("T*_osc.npz")):
        print(f"[WARN] В osc_dir нет файлов Txx_osc.npz: {osc_dir}. Нечего калибровать. Завершаю без ошибки.")
        return 0

    # out_dir
    if str(args.out_dir).strip():
        out_dir = Path(args.out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_dir = project_root / "calibration_runs" / f"RUN_{ts}_autopilot_v19"
    out_dir.mkdir(parents=True, exist_ok=True)

    # resolve signals.csv
    signals_csv = _resolve_signals_csv(str(args.signals_csv), osc_dir, project_root)
    bootstrap_meta = {}

    if signals_csv is None:
        if bool(args.no_bootstrap):
            raise SystemExit(
                "signals_csv=auto: не найден signals.csv ни в osc_dir, ни в calibration_runs. "
                "Добавьте signals.csv или уберите --no_bootstrap (разрешите seed oneclick)."
            )

        bootstrap_dir = out_dir / "bootstrap_oneclick_seed"
        bootstrap_dir.mkdir(parents=True, exist_ok=True)

        seed_cmd = [
            sys.executable, str(project_root / "calibration" / "pipeline_npz_oneclick_v1.py"),
            "--osc_dir", str(osc_dir),
            "--out_dir", str(bootstrap_dir),
            "--mode", str(args.bootstrap_mode),
            "--model", str(args.model),
            "--worker", str(args.worker),
            "--suite_json", str(args.suite_json),
            "--base_json", str(args.base_json),
            "--fit_ranges_json", str(args.fit_ranges_json),
            "--auto_scale", "mad",
            "--holdout_frac", "0.0",
        ]
        if bool(args.use_smoothing_defaults):
            seed_cmd.append("--use_smoothing_defaults")

        _run(seed_cmd, cwd=project_root)

        signals_csv = bootstrap_dir / "signals.csv"
        if not signals_csv.exists():
            raise SystemExit(
                f"Seed oneclick завершился, но не найден {signals_csv}. "
                "Проверьте лог oneclick и структуру osc_dir."
            )

        # copy for convenience
        try:
            (out_dir / "SEED_SIGNALS.csv").write_bytes(signals_csv.read_bytes())
        except Exception:
            pass

        bootstrap_meta = {
            "bootstrap_used": True,
            "bootstrap_mode": str(args.bootstrap_mode),
            "bootstrap_dir": str(bootstrap_dir),
            "seed_signals_csv": str(signals_csv),
        }
    else:
        bootstrap_meta = {
            "bootstrap_used": False,
            "signals_csv_resolved": str(signals_csv),
        }

        # copy resolved signals.csv into out_dir for traceability (non-fatal)
        try:
            if signals_csv.exists():
                (out_dir / "INPUT_SIGNALS.csv").write_bytes(signals_csv.read_bytes())
        except Exception:
            pass

    # wrapper meta
    meta = {
        "version": "v19_wrapper",
        "ts": time.time(),
        "osc_dir": str(osc_dir),
        "out_dir": str(out_dir),
        "model": str(args.model),
        "worker": str(args.worker),
        "suite_json": str(args.suite_json),
        "base_json": str(args.base_json),
        "fit_ranges_json": str(args.fit_ranges_json),
        "use_smoothing_defaults": bool(args.use_smoothing_defaults),
        "signals_csv": str(signals_csv) if signals_csv else None,
    }
    meta.update(bootstrap_meta)
    (out_dir / "AUTOPILOT_V19_WRAPPER.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # call v18
    v18_cmd = [
        sys.executable, str(project_root / "calibration" / "pipeline_npz_autopilot_v18.py"),
        "--osc_dir", str(osc_dir),
        "--out_dir", str(out_dir),
        "--signals_csv", str(signals_csv),
        "--model", str(args.model),
        "--worker", str(args.worker),
        "--suite_json", str(args.suite_json),
        "--base_json", str(args.base_json),
        "--fit_ranges_json", str(args.fit_ranges_json),
    ]
    if bool(args.use_smoothing_defaults):
        v18_cmd.append("--use_smoothing_defaults")

    # Remove duplicates if caller already added them.
    keys_with_value = {
        "--osc_dir", "--out_dir", "--signals_csv",
        "--model", "--worker", "--suite_json", "--base_json", "--fit_ranges_json",
    }
    keys_flag = {"--use_smoothing_defaults"}
    extra_f = _strip_duplicate_args(list(extra), keys_with_value, keys_flag)

    v18_cmd.extend(extra_f)
    _run(v18_cmd, cwd=project_root)


if __name__ == "__main__":
    main()
