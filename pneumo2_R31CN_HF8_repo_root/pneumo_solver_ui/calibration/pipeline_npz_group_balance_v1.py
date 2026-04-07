# -*- coding: utf-8 -*-
"""pipeline_npz_group_balance_v1.py

Адаптивная балансировка групп сигналов (sig_group) для multiobjective калибровки.

Зачем
-----
В идентификации параметров матмодели часто есть конфликтующие группы измерений
(например, давления vs кинематика). В проекте уже поддержан механизм
`--group_weights_json` в fit_worker_v3_suite_identify.py: это множитель, который
применяется ПОСЛЕ auto_scale, поэтому он не "съедается" нормировкой.

Этот скрипт делает практичный автоматический компромисс без дорогого Pareto sweep:

Итеративная схема (group-level reweighting, multiplicative update):
  1) стартуем с gains[g] = 1
  2) фитим параметры
  3) считаем unbiased RMSE по группам (без group_gain)
  4) обновляем gains так, чтобы группы с большим RMSE усиливались

Обновление (по умолчанию):
  target = geometric_mean(RMSE_g)
  gain_g <- gain_g * (RMSE_g / target)^(-alpha)
  затем нормируем gains так, чтобы geometric_mean(gain)=1
  затем клиппинг gain_min..gain_max

Это даёт быстрый "баланс" между группами за 3..6 итераций и сильно дешевле,
чем полный Pareto/epsilon sweep.

Запуск (из корня pneumo_v7):
  python calibration/pipeline_npz_group_balance_v1.py \
    --osc_dir osc_logs/RUN_... \
    --signals_csv calibration_runs/RUN.../iterative/FINAL_SIGNALS.csv \
    --out_dir calibration_runs/RUN.../group_balance \
    --base_json calibration_runs/RUN.../fitted_base_final.json

Выход (out_dir):
  - signals_grouped.csv                 (signals.csv + sig_group)
  - mapping_from_signals.json
  - iter01/, iter02/, ... (fit_worker outputs)
  - group_balance_history.csv
  - group_weights_final.json
  - fitted_base_balanced.json
  - group_balance_report.md

Примечание
----------
- Это не заменяет Pareto фронт, если нужен полный спектр компромиссов.
- Это хороший "автопилот"-вариант: быстро получить разумную точку.

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
    if any(k in s for k in [
        "крен", "тангаж", "рыск", "roll", "pitch", "yaw",
        "угол", "angle", "theta", "phi", "psi",
        "высот", "height", "ход", "stroke", "z_", "x_", "y_",
        "скор", "vel", "acc",
    ]):
        return "kinematics"

    # flow
    if any(k in s for k in ["расход", "flow", "q_"]):
        return "flow"

    # valves
    if any(k in s for k in ["клапан", "valve", "open", "duty"]):
        return "valves"

    # energy
    if any(k in s for k in ["энерг", "energy", "power", "eedges", "egroups"]):
        return "energy"

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


def groups_from_signals(signals_csv: Path) -> List[str]:
    df = pd.read_csv(signals_csv, encoding="utf-8-sig")
    if "sig_group" not in df.columns:
        return []
    g = df["sig_group"].astype(str).str.strip().replace({"": "default"}).fillna("default")
    uniq = sorted(set(g.tolist()))
    return uniq


def compute_group_rmse_unb(details_json: Path) -> Tuple[Dict[str, float], Dict[str, int]]:
    """Вернуть RMSE_unb по группам на базе fit_details.json.

    Используем поля signals[*].sse_unb и signals[*].n.
    """
    det = _load_json(details_json)
    rows = det.get("signals", [])
    if not isinstance(rows, list):
        return {}, {}

    sse: Dict[str, float] = {}
    nn: Dict[str, int] = {}

    for r in rows:
        g = str(r.get("sig_group", r.get("group", "default"))).strip() or "default"
        try:
            sse_unb = float(r.get("sse_unb", float("nan")))
            n = int(r.get("n", 0))
        except Exception:
            continue
        if not (math.isfinite(sse_unb) and n > 0):
            continue
        sse[g] = sse.get(g, 0.0) + sse_unb
        nn[g] = nn.get(g, 0) + n

    rmse: Dict[str, float] = {}
    for g, ss in sse.items():
        n = max(1, int(nn.get(g, 0)))
        rmse[g] = float(math.sqrt(max(0.0, ss) / n))

    return rmse, nn


def geom_mean(values: List[float], eps: float = 1e-30) -> float:
    vals = [max(eps, float(v)) for v in values if math.isfinite(float(v))]
    if not vals:
        return float("nan")
    return float(math.exp(sum(math.log(v) for v in vals) / len(vals)))


def normalize_geomean_one(gains: Dict[str, float], groups: List[str]) -> Dict[str, float]:
    vals = [float(gains.get(g, 1.0)) for g in groups]
    gm = geom_mean(vals)
    if not math.isfinite(gm) or gm <= 0:
        return dict(gains)
    out = dict(gains)
    for g in groups:
        out[g] = float(out.get(g, 1.0) / gm)
    return out


def update_gains(
    gains: Dict[str, float],
    rmse_unb: Dict[str, float],
    groups: List[str],
    alpha: float,
    gain_min: float,
    gain_max: float,
) -> Tuple[Dict[str, float], float]:
    """Multiplicative update gains by current group RMSE."""
    vals = [float(rmse_unb.get(g, float("nan"))) for g in groups]
    vals = [v for v in vals if math.isfinite(v) and v > 0]
    target = geom_mean(vals)
    if not (math.isfinite(target) and target > 0):
        return dict(gains), float("nan")

    out = dict(gains)
    for g in groups:
        r = float(rmse_unb.get(g, float("nan")))
        if not (math.isfinite(r) and r > 0):
            continue
        # gain *= (r/target)^(-alpha) == (target/r)^alpha
        mul = (target / r) ** float(alpha)
        out[g] = float(out.get(g, 1.0) * mul)

    out = normalize_geomean_one(out, groups)

    # clip
    gmin = float(gain_min)
    gmax = float(gain_max)
    for g in groups:
        v = float(out.get(g, 1.0))
        if math.isfinite(v):
            out[g] = float(min(gmax, max(gmin, v)))

    out = normalize_geomean_one(out, groups)
    return out, target


def run_fit_worker(
    project_root: Path,
    *,
    osc_dir: Path,
    model: str,
    worker: str,
    suite_json: str,
    base_json: Path,
    fit_ranges_json: str,
    mapping_json: Path,
    out_dir: Path,
    group_weights_json: Path,
    auto_scale: str,
    loss: str,
    f_scale: float,
    n_init: int,
    n_best: int,
    max_nfev: int,
    global_init: str,
    meas_stride: int,
    use_smoothing_defaults: bool,
    stop_file: Optional[Path],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(project_root / "calibration" / "fit_worker_v3_suite_identify.py"),
        "--model", model,
        "--worker", worker,
        "--suite_json", suite_json,
        "--osc_dir", str(osc_dir),
        "--base_json", str(base_json),
        "--fit_ranges_json", fit_ranges_json,
        "--mapping_json", str(mapping_json),
        "--group_weights_json", str(group_weights_json),
        "--auto_scale", str(auto_scale),
        "--loss", str(loss),
        "--f_scale", str(float(f_scale)),
        "--n_init", str(int(n_init)),
        "--n_best", str(int(n_best)),
        "--max_nfev", str(int(max_nfev)),
        "--global_init", str(global_init),
        "--meas_stride", str(int(meas_stride)),
        "--out_json", str(out_dir / "fitted_base.json"),
        "--report_json", str(out_dir / "fit_report.json"),
        "--details_json", str(out_dir / "fit_details.json"),
    ]
    if use_smoothing_defaults:
        cmd.append("--use_smoothing_defaults")
    if stop_file is not None:
        cmd += ["--stop_file", str(stop_file)]

    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=str(project_root), check=True)


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
    ap.add_argument("--loss", default="soft_l1")
    ap.add_argument("--f_scale", type=float, default=1.0)

    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--gain_min", type=float, default=0.05)
    ap.add_argument("--gain_max", type=float, default=20.0)

    ap.add_argument("--groups", default="", help="Опционально: список групп через запятую. Если пусто — берём все из signals.csv, кроме 'default'.")

    ap.add_argument("--n_init", type=int, default=12)
    ap.add_argument("--n_best", type=int, default=2)
    ap.add_argument("--max_nfev", type=int, default=120)
    ap.add_argument("--global_init", default="none", choices=["none", "de", "surrogate", "cem"])

    ap.add_argument("--meas_stride", type=int, default=1)
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    ap.add_argument("--stop_file", default="", help="Если файл существует — мягко остановиться")

    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    osc_dir = Path(args.osc_dir)
    signals_csv = Path(args.signals_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stop_file = Path(args.stop_file) if str(args.stop_file).strip() else None

    # 0) ensure sig_group in signals
    signals_grouped = out_dir / "signals_grouped.csv"
    ensure_sig_groups(signals_csv, signals_grouped)

    # groups to balance
    if str(args.groups).strip():
        groups = [g.strip() for g in str(args.groups).split(",") if g.strip()]
    else:
        allg = groups_from_signals(signals_grouped)
        groups = [g for g in allg if g != "default"]

    if not groups:
        raise SystemExit("Не найдено ни одной группы для балансировки (sig_group).")

    # 1) mapping.json from signals
    mapping_json = out_dir / "mapping_from_signals.json"
    cmd_map = [
        sys.executable,
        str(project_root / "calibration" / "signals_csv_to_mapping_v1.py"),
        "--signals_csv", str(signals_grouped),
        "--out_mapping", str(mapping_json),
        "--osc_dir", str(osc_dir),
        "--test_num", "1",
        "--drop_missing",
    ]
    print(">", " ".join(cmd_map))
    subprocess.run(cmd_map, cwd=str(project_root), check=True)

    # 2) loop
    gains: Dict[str, float] = {g: 1.0 for g in groups}
    hist_rows: List[Dict[str, Any]] = []

    base_json = Path(args.base_json)
    base_current = out_dir / "base_current.json"
    # copy initial base
    base_current.write_text(base_json.read_text(encoding="utf-8"), encoding="utf-8")

    last_it_dir = None  # Path
    for it in range(1, int(args.iters) + 1):
        if _should_stop(stop_file):
            print("STOP requested before iteration", it)
            break

        it_dir = out_dir / f"iter{it:02d}"
        last_it_dir = it_dir
        it_dir.mkdir(parents=True, exist_ok=True)

        gw_path = it_dir / "group_weights.json"
        _save_json(gains, gw_path)

        t0 = time.time()
        run_fit_worker(
            project_root,
            osc_dir=osc_dir,
            model=str(args.model),
            worker=str(args.worker),
            suite_json=str(args.suite_json),
            base_json=base_current,
            fit_ranges_json=str(args.fit_ranges_json),
            mapping_json=mapping_json,
            out_dir=it_dir,
            group_weights_json=gw_path,
            auto_scale=str(args.auto_scale),
            loss=str(args.loss),
            f_scale=float(args.f_scale),
            n_init=int(args.n_init),
            n_best=int(args.n_best),
            max_nfev=int(args.max_nfev),
            global_init=str(args.global_init),
            meas_stride=int(args.meas_stride),
            use_smoothing_defaults=bool(args.use_smoothing_defaults),
            stop_file=stop_file,
        )
        dt = time.time() - t0

        det_p = it_dir / "fit_details.json"
        rep_p = it_dir / "fit_report.json"
        fitted_p = it_dir / "fitted_base.json"

        rmse_unb, nn = compute_group_rmse_unb(det_p)
        # keep only selected groups
        rmse_sel = {g: float(rmse_unb.get(g, float("nan"))) for g in groups}

        gains_new, target = update_gains(
            gains,
            rmse_sel,
            groups,
            alpha=float(args.alpha),
            gain_min=float(args.gain_min),
            gain_max=float(args.gain_max),
        )

        row: Dict[str, Any] = {
            "iter": int(it),
            "time_sec": float(dt),
            "target_rmse_gm": float(target) if math.isfinite(target) else None,
        }
        # metrics
        for g in groups:
            row[f"rmse_unb_{g}"] = float(rmse_sel.get(g)) if math.isfinite(float(rmse_sel.get(g, float('nan')))) else None
            row[f"n_{g}"] = int(nn.get(g, 0))
            row[f"gain_{g}"] = float(gains.get(g, 1.0))
            row[f"gain_new_{g}"] = float(gains_new.get(g, 1.0))

        # also store best cost
        try:
            rep = _load_json(rep_p)
            row["best_rmse"] = float(rep.get("best_rmse"))
            row["best_cost"] = float(rep.get("best_cost"))
        except Exception:
            pass

        hist_rows.append(row)

        # prepare next iter: base_current <- fitted from this iter
        base_current.write_text(fitted_p.read_text(encoding="utf-8"), encoding="utf-8")
        gains = gains_new



    # keep a pointer to the last successful iteration folder
    if last_it_dir is None:
        try:
            last_it_dir = out_dir / f"iter{int(args.iters)}"
        except Exception:
            last_it_dir = None

    # copy last fit artifacts (useful for autopilot/reporting)
    try:
        if last_it_dir is not None and last_it_dir.exists():
            for src, dst in [
                (last_it_dir / 'fit_report.json', out_dir / 'fit_report_balanced.json'),
                (last_it_dir / 'fit_details.json', out_dir / 'fit_details_balanced.json'),
                (last_it_dir / 'fitted_base.json', out_dir / 'fitted_base_last_iter.json'),
            ]:
                if src.exists():
                    dst.write_bytes(src.read_bytes())
    except Exception:
        pass

    # 3) write outputs
    hist_csv = out_dir / "group_balance_history.csv"
    if hist_rows:
        dfh = pd.DataFrame(hist_rows)
        dfh.to_csv(hist_csv, index=False, encoding="utf-8-sig")

    final_gw = out_dir / "group_weights_final.json"
    _save_json(gains, final_gw)

    # best is last base_current (already)
    fitted_final = out_dir / "fitted_base_balanced.json"
    fitted_final.write_text(base_current.read_text(encoding="utf-8"), encoding="utf-8")

    # report md
    md: List[str] = []
    md.append("# Group balance report")
    md.append("")
    md.append("## Settings")
    md.append(f"- iters: `{int(args.iters)}`")
    md.append(f"- alpha: `{float(args.alpha)}`")
    md.append(f"- gain_min..gain_max: `{float(args.gain_min)}` .. `{float(args.gain_max)}`")
    md.append(f"- groups: `{', '.join(groups)}`")
    md.append("")
    md.append("## Outputs")
    md.append(f"- group_balance_history.csv: `{hist_csv.name}`")
    md.append(f"- group_weights_final.json: `{final_gw.name}`")
    md.append(f"- fitted_base_balanced.json: `{fitted_final.name}`")
    md.append("")

    if hist_rows:
        md.append("## Last iteration snapshot")
        last = hist_rows[-1]
        md.append("")
        md.append(f"- target_rmse_gm: `{last.get('target_rmse_gm')}`")
        md.append("")
        md.append("| group | rmse_unb | gain | gain_new |")
        md.append("|---|---:|---:|---:|")
        for g in groups:
            md.append(
                f"| {g} | {last.get('rmse_unb_'+g)} | {last.get('gain_'+g)} | {last.get('gain_new_'+g)} |"
            )
        md.append("")

    _save_text("\n".join(md) + "\n", out_dir / "group_balance_report.md")

    print("DONE. Outputs in:", out_dir)


if __name__ == "__main__":
    main()
