# -*- coding: utf-8 -*-
"""pipeline_npz_group_balance_v3.py

Адаптивный компромисс по группам сигналов (sig_group) для multiobjective калибровки.

v3 (FIM-aware update + minimax/softmax + auto-stop)
--------------------------------
В v1 был только один multiplicative update, по сути "баланс вкладов".
На практике часто нужен другой режим: *минимизация худшей группы*
(minimax / Chebyshev-скаляризация) — например, не допустить, чтобы
kinematics стала сильно хуже ради давления.

Этот скрипт добавляет три стратегии:

1) equalize_contrib (как v1):
   gain_g <- gain_g * (target/rmse_g)^alpha
   Усиливает группы с МАЛОЙ ошибкой и ослабляет группы с БОЛЬШОЙ ошибкой,
   выравнивая вклад в суммарный cost.

2) minimax:
   gain_g <- gain_g * (rmse_g/target)^alpha
   Усиливает группы с БОЛЬШОЙ ошибкой (приближает к minimax: "подтяни худшее").

3) softmax:
   p_g ∝ (rmse_g/target)^beta  (эквивалент softmax по log(rmse/target))
   gain_g <- gain_g * (p_g * |G|)^alpha
   Более агрессивный minimax, когда beta > 1.

После обновления gains нормируются так, чтобы geometric_mean(gain)=1,
и клиппятся в [gain_min, gain_max].

Добавлена авто-остановка:
- если spread ошибок между группами мал
- и/или улучшение max_rmse незначительно
- и/или gains почти не меняются

Это уменьшает количество лишних итераций.

Запуск (из корня pneumo_v7):
  python calibration/pipeline_npz_group_balance_v3.py \
    --osc_dir osc_logs/RUN_... \
    --signals_csv calibration_runs/RUN.../iterative/FINAL_SIGNALS.csv \
    --out_dir calibration_runs/RUN.../group_balance \
    --strategy minimax \
    --iters 6 --patience 2

Выход (out_dir):
  - signals_grouped.csv
  - mapping_from_signals.json
  - iter01/, iter02/, ...
  - group_balance_history.csv
  - group_weights_final.json
  - fitted_base_balanced.json
  - group_balance_report.md

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

    if any(k in s for k in ["давлен", "pressure", "_pa", " pa", "bar", "кпа", "mpa"]):
        return "pressure"

    if any(k in s for k in [
        "крен", "тангаж", "рыск", "roll", "pitch", "yaw",
        "угол", "angle", "theta", "phi", "psi",
        "высот", "height", "ход", "stroke", "z_", "x_", "y_",
        "скор", "vel", "acc",
    ]):
        return "kinematics"

    if any(k in s for k in ["расход", "flow", "q_"]):
        return "flow"

    if any(k in s for k in ["клапан", "valve", "open", "duty"]):
        return "valves"

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
    return sorted(set(g.tolist()))


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



def load_group_sensitivity(report_json: Path) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Load per-group sensitivity metrics from fit_report.json (if present).

    We expect fit_worker_v3_suite_identify.py to provide:
      report['group_sensitivity'][group]['jac_row_rms_unb']
      report['group_sensitivity'][group]['fim_rank_unb'] and 'n_params' (optional)

    Returns:
        sens_unb: group -> jac_row_rms_unb
        rank_frac: group -> fim_rank_unb / n_params  (0..1) if available
    """
    try:
        rep = _load_json(report_json)
    except Exception:
        return {}, {}

    gs = rep.get("group_sensitivity", None)
    if not isinstance(gs, dict):
        return {}, {}

    sens: Dict[str, float] = {}
    rank_frac: Dict[str, float] = {}

    for g, st in gs.items():
        if not isinstance(st, dict):
            continue
        gg = str(g).strip() or "default"
        try:
            v = float(st.get("jac_row_rms_unb", float("nan")))
            if math.isfinite(v) and v > 0:
                sens[gg] = float(v)
        except Exception:
            pass
        try:
            r = int(st.get("fim_rank_unb", st.get("fim_rank", 0)))
            n = int(st.get("n_params", 0))
            if n > 0 and r >= 0:
                rank_frac[gg] = float(r) / float(n)
        except Exception:
            pass

    return sens, rank_frac


def compute_fim_factors(
    groups: List[str],
    sens_unb: Dict[str, float],
    rank_frac: Dict[str, float],
    *,
    gamma: float,
    min_factor: float,
    max_factor: float,
    rank_min_frac: float,
) -> Dict[str, float]:
    """Compute per-group alpha multipliers based on (unbiased) Jacobian sensitivity.

    Idea:
      - If a group is weakly sensitive to parameters (low jac_row_rms_unb),
        aggressive gain updates often cause collateral damage: optimizer can't
        improve that group much, but other groups deteriorate.
      - Поэтому уменьшаем «скорость» изменения gains для низко-чувствительных групп.

    factor_g = clip( (sens_g / median_sens)^gamma, [min_factor, max_factor] )
    optional: additional gate by FIM rank fraction.
    """
    vals = [float(sens_unb.get(g, float("nan"))) for g in groups]
    vals = [v for v in vals if math.isfinite(v) and v > 0]
    med = float(np.median(np.asarray(vals, dtype=float))) if vals else 1.0
    if not (math.isfinite(med) and med > 0):
        med = 1.0

    out: Dict[str, float] = {}
    for g in groups:
        s = float(sens_unb.get(g, float("nan")))
        if math.isfinite(s) and s > 0:
            norm = float(s / med)
            f = float(norm ** float(gamma))
        else:
            f = 1.0

        rf = rank_frac.get(g, None)
        if rf is not None and math.isfinite(float(rf)) and float(rank_min_frac) > 0:
            gate = float(min(1.0, max(0.0, float(rf) / float(rank_min_frac))))
            f *= gate

        f = float(min(float(max_factor), max(float(min_factor), f)))
        out[str(g)] = f

    return out


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
    strategy: str,
    alpha: float,
    beta: float,
    gain_min: float,
    gain_max: float,
    alpha_by_group: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Update group gains based on unbiased RMSE.

    Returns:
        gains_new, stats dict with target/max/min/spread
    """
    # collect valid rmse
    vals = []
    for g in groups:
        r = float(rmse_unb.get(g, float("nan")))
        if math.isfinite(r) and r > 0:
            vals.append(r)
    target = geom_mean(vals)
    if not (math.isfinite(target) and target > 0):
        return dict(gains), {"target": float("nan"), "max_rmse": float("nan"), "min_rmse": float("nan"), "spread": float("nan")}

    # stats
    r_max = max(vals) if vals else float("nan")
    r_min = min(vals) if vals else float("nan")
    spread = (r_max / max(1e-30, r_min) - 1.0) if (math.isfinite(r_max) and math.isfinite(r_min) and r_min > 0) else float("nan")

    out = dict(gains)

    if strategy == "equalize_contrib":
        # emphasize small-rmse groups
        for g in groups:
            r = float(rmse_unb.get(g, float("nan")))
            if not (math.isfinite(r) and r > 0):
                continue
            alpha_g = float(alpha_by_group.get(g, alpha)) if alpha_by_group else float(alpha)
            mul = (target / r) ** float(alpha_g)
            out[g] = float(out.get(g, 1.0) * mul)

    elif strategy == "minimax":
        # emphasize large-rmse groups
        for g in groups:
            r = float(rmse_unb.get(g, float("nan")))
            if not (math.isfinite(r) and r > 0):
                continue
            alpha_g = float(alpha_by_group.get(g, alpha)) if alpha_by_group else float(alpha)
            mul = (r / target) ** float(alpha_g)
            out[g] = float(out.get(g, 1.0) * mul)

    elif strategy == "softmax":
        # p_g ∝ (r/target)^beta
        r_norm: Dict[str, float] = {}
        for g in groups:
            r = float(rmse_unb.get(g, float("nan")))
            if math.isfinite(r) and r > 0:
                r_norm[g] = float(r / target)
        # weights
        z: Dict[str, float] = {}
        for g, rn in r_norm.items():
            # rn^beta can overflow if rn huge; clamp
            rn_c = min(1e6, max(1e-12, float(rn)))
            z[g] = float(rn_c ** float(beta))
        s = float(sum(z.values()))
        if not (math.isfinite(s) and s > 0):
            return dict(gains), {"target": target, "max_rmse": r_max, "min_rmse": r_min, "spread": spread}
        m = float(len(groups))
        for g in groups:
            p = float(z.get(g, 0.0) / s)
            # average of (p*m) is 1
            alpha_g = float(alpha_by_group.get(g, alpha)) if alpha_by_group else float(alpha)
            mul = float(max(1e-9, p * m) ** float(alpha_g))
            out[g] = float(out.get(g, 1.0) * mul)

    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    out = normalize_geomean_one(out, groups)

    # clip
    gmin = float(gain_min)
    gmax = float(gain_max)
    for g in groups:
        v = float(out.get(g, 1.0))
        if math.isfinite(v):
            out[g] = float(min(gmax, max(gmin, v)))

    out = normalize_geomean_one(out, groups)

    return out, {"target": target, "max_rmse": r_max, "min_rmse": r_min, "spread": spread}


def gain_delta_log_inf(g_old: Dict[str, float], g_new: Dict[str, float], groups: List[str]) -> float:
    """max |log(new/old)| across groups."""
    mx = 0.0
    for g in groups:
        a = float(g_old.get(g, 1.0))
        b = float(g_new.get(g, 1.0))
        if a <= 0 or b <= 0:
            continue
        try:
            d = abs(math.log(b / a))
            if math.isfinite(d):
                mx = max(mx, d)
        except Exception:
            pass
    return float(mx)


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

    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--strategy", default="minimax", choices=["equalize_contrib", "minimax", "softmax"])
    ap.add_argument("--alpha", type=float, default=0.6)
    ap.add_argument("--beta", type=float, default=4.0, help="Используется только в strategy=softmax")
    # FIM-aware (Jacobian sensitivity) damping for gain updates
    ap.add_argument("--fim_aware", action="store_true", help="Учитывать чувствительность (Jacobian/FIM) при обновлении gains.")
    ap.add_argument("--fim_gamma", type=float, default=0.5, help="Степень в (sens/median)^gamma (0 -> без эффекта).")
    ap.add_argument("--fim_min_factor", type=float, default=0.2, help="Минимальный множитель alpha по группе (можно 0 чтобы заморозить).")
    ap.add_argument("--fim_max_factor", type=float, default=1.0, help="Максимальный множитель alpha по группе.")
    ap.add_argument("--fim_rank_min_frac", type=float, default=0.25, help="Порог доли ранга FIM (rank/n_params) для полной скорости; ниже — доп. демпфирование.")

    ap.add_argument("--gain_min", type=float, default=0.05)
    ap.add_argument("--gain_max", type=float, default=20.0)

    # auto-stop
    ap.add_argument("--min_iters", type=int, default=2)
    ap.add_argument("--patience", type=int, default=2)
    ap.add_argument("--tol_gain_log", type=float, default=0.05, help="max |log(g_new/g_old)|")
    ap.add_argument("--tol_spread", type=float, default=0.05, help="(max_rmse/min_rmse - 1)")
    ap.add_argument("--tol_max_rmse_rel", type=float, default=0.01, help="relative improvement of max_rmse")

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
    base_current.write_text(base_json.read_text(encoding="utf-8"), encoding="utf-8")

    last_it_dir: Optional[Path] = None
    prev_max_rmse: Optional[float] = None
    stable_cnt = 0
    noimp_cnt = 0
    stop_reason = "max_iters"

    iters = int(args.iters)
    for it in range(1, iters + 1):
        if _should_stop(stop_file):
            stop_reason = "stop_file"
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
        rmse_sel = {g: float(rmse_unb.get(g, float("nan"))) for g in groups}

        # optional: FIM/Jacobian-aware damping of gain updates (per-group alpha)
        alpha_by_group: Optional[Dict[str, float]] = None
        fim_factors: Optional[Dict[str, float]] = None
        if bool(getattr(args, "fim_aware", False)):
            sens_unb, rank_frac = load_group_sensitivity(rep_p)
            fim_factors = compute_fim_factors(
                groups,
                sens_unb,
                rank_frac,
                gamma=float(getattr(args, "fim_gamma", 0.5)),
                min_factor=float(getattr(args, "fim_min_factor", 0.2)),
                max_factor=float(getattr(args, "fim_max_factor", 1.0)),
                rank_min_frac=float(getattr(args, "fim_rank_min_frac", 0.25)),
            )
            alpha_by_group = {g: float(args.alpha) * float(fim_factors.get(g, 1.0)) for g in groups}

        gains_new, stats = update_gains(
            gains,
            rmse_sel,
            groups,
            strategy=str(args.strategy),
            alpha=float(args.alpha),
            beta=float(args.beta),
            gain_min=float(args.gain_min),
            gain_max=float(args.gain_max),
            alpha_by_group=alpha_by_group,
        )

        # diagnostics for auto-stop
        max_rmse = float(stats.get("max_rmse", float("nan")))
        min_rmse = float(stats.get("min_rmse", float("nan")))
        spread = float(stats.get("spread", float("nan")))
        gdelta = gain_delta_log_inf(gains, gains_new, groups)

        rel_improve = None
        if prev_max_rmse is not None and math.isfinite(prev_max_rmse) and prev_max_rmse > 0 and math.isfinite(max_rmse):
            rel_improve = float((prev_max_rmse - max_rmse) / prev_max_rmse)

        # update counters
        if rel_improve is not None and rel_improve < float(args.tol_max_rmse_rel):
            noimp_cnt += 1
        else:
            noimp_cnt = 0

        if (math.isfinite(gdelta) and gdelta < float(args.tol_gain_log)) and (math.isfinite(spread) and spread < float(args.tol_spread)):
            stable_cnt += 1
        else:
            stable_cnt = 0

        # history row
        row: Dict[str, Any] = {
            "iter": int(it),
            "time_sec": float(dt),
            "strategy": str(args.strategy),
            "alpha": float(args.alpha),
            "beta": float(args.beta),
            "fim_aware": bool(getattr(args, "fim_aware", False)),
            "fim_gamma": float(getattr(args, "fim_gamma", 0.0)),
            "fim_min_factor": float(getattr(args, "fim_min_factor", 0.0)),
            "fim_max_factor": float(getattr(args, "fim_max_factor", 0.0)),
            "fim_rank_min_frac": float(getattr(args, "fim_rank_min_frac", 0.0)),
            "target_rmse_gm": float(stats.get("target")) if math.isfinite(float(stats.get("target", float("nan")))) else None,
            "max_rmse": max_rmse if math.isfinite(max_rmse) else None,
            "min_rmse": min_rmse if math.isfinite(min_rmse) else None,
            "spread_rel": spread if math.isfinite(spread) else None,
            "gain_delta_log_inf": gdelta if math.isfinite(gdelta) else None,
            "rel_improve_max_rmse": rel_improve,
            "stable_cnt": int(stable_cnt),
            "noimp_cnt": int(noimp_cnt),
        }

        for g in groups:
            rv = rmse_sel.get(g, float("nan"))
            row[f"rmse_unb_{g}"] = float(rv) if math.isfinite(float(rv)) else None
            row[f"n_{g}"] = int(nn.get(g, 0))
            row[f"gain_{g}"] = float(gains.get(g, 1.0))
            row[f"gain_new_{g}"] = float(gains_new.get(g, 1.0))
            if fim_factors is not None:
                row[f"fim_factor_{g}"] = float(fim_factors.get(g, 1.0))
            else:
                row[f"fim_factor_{g}"] = None
            if alpha_by_group is not None:
                row[f"alpha_eff_{g}"] = float(alpha_by_group.get(g, float(args.alpha)))
            else:
                row[f"alpha_eff_{g}"] = float(args.alpha)

        try:
            rep = _load_json(rep_p)
            row["best_rmse"] = float(rep.get("best_rmse"))
            row["best_cost"] = float(rep.get("best_cost"))
        except Exception:
            pass

        hist_rows.append(row)

        # prepare next iter
        base_current.write_text(fitted_p.read_text(encoding="utf-8"), encoding="utf-8")
        prev_max_rmse = max_rmse if math.isfinite(max_rmse) else prev_max_rmse
        gains = gains_new

        # auto-stop check
        if it >= int(args.min_iters):
            if stable_cnt >= int(args.patience):
                stop_reason = "stable"
                break
            if noimp_cnt >= int(args.patience):
                stop_reason = "no_improve"
                break

    # copy last fit artifacts
    if last_it_dir is not None and last_it_dir.exists():
        for src, dst in [
            (last_it_dir / "fit_report.json", out_dir / "fit_report_balanced.json"),
            (last_it_dir / "fit_details.json", out_dir / "fit_details_balanced.json"),
            (last_it_dir / "fitted_base.json", out_dir / "fitted_base_last_iter.json"),
        ]:
            if src.exists():
                try:
                    dst.write_bytes(src.read_bytes())
                except Exception:
                    pass

    # write outputs
    hist_csv = out_dir / "group_balance_history.csv"
    if hist_rows:
        pd.DataFrame(hist_rows).to_csv(hist_csv, index=False, encoding="utf-8-sig")

    final_gw = out_dir / "group_weights_final.json"
    _save_json(gains, final_gw)

    fitted_final = out_dir / "fitted_base_balanced.json"
    fitted_final.write_text(base_current.read_text(encoding="utf-8"), encoding="utf-8")

    # report
    md: List[str] = []
    md.append("# Group balance report (v3)")
    md.append("")
    md.append("## Settings")
    md.append(f"- strategy: `{args.strategy}`")
    md.append(f"- iters (max): `{iters}`")
    md.append(f"- alpha: `{float(args.alpha)}`")
    md.append(f"- beta: `{float(args.beta)}`")
    md.append(f"- gain_min..gain_max: `{float(args.gain_min)}` .. `{float(args.gain_max)}`")
    md.append(f"- fim_aware: `{bool(getattr(args, 'fim_aware', False))}`")
    if bool(getattr(args, "fim_aware", False)):
        md.append(f"- fim_gamma: `{float(getattr(args, 'fim_gamma', 0.5))}`")
        md.append(f"- fim_min_factor..fim_max_factor: `{float(getattr(args, 'fim_min_factor', 0.2))}` .. `{float(getattr(args, 'fim_max_factor', 1.0))}`")
        md.append(f"- fim_rank_min_frac: `{float(getattr(args, 'fim_rank_min_frac', 0.25))}`")
    md.append(f"- groups: `{', '.join(groups)}`")
    md.append("")
    md.append("## Auto-stop")
    md.append(f"- stop_reason: `{stop_reason}`")
    md.append(f"- min_iters: `{int(args.min_iters)}`")
    md.append(f"- patience: `{int(args.patience)}`")
    md.append(f"- tol_gain_log: `{float(args.tol_gain_log)}`")
    md.append(f"- tol_spread: `{float(args.tol_spread)}`")
    md.append(f"- tol_max_rmse_rel: `{float(args.tol_max_rmse_rel)}`")
    md.append("")
    md.append("## Outputs")
    md.append(f"- group_balance_history.csv: `{hist_csv.name}`")
    md.append(f"- group_weights_final.json: `{final_gw.name}`")
    md.append(f"- fitted_base_balanced.json: `{fitted_final.name}`")

    if hist_rows:
        last = hist_rows[-1]
        md.append("")
        md.append("## Last iteration snapshot")
        md.append("")
        md.append(f"- max_rmse: `{last.get('max_rmse')}`")
        md.append(f"- spread_rel: `{last.get('spread_rel')}`")
        md.append(f"- gain_delta_log_inf: `{last.get('gain_delta_log_inf')}`")
        md.append("")
        md.append("| group | rmse_unb | fim_factor | alpha_eff | gain -> gain_new |")
        md.append("|---|---:|---:|---:|---:|")
        for g in groups:
            md.append(f"| {g} | {last.get('rmse_unb_'+g)} | {last.get('fim_factor_'+g)} | {last.get('alpha_eff_'+g)} | {last.get('gain_'+g)} -> {last.get('gain_new_'+g)} |")

    _save_text("\n".join(md) + "\n", out_dir / "group_balance_report.md")

    print("DONE. Outputs in:", out_dir)


if __name__ == "__main__":
    main()
