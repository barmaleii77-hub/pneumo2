#!/usr/bin/env python3
"""Pressure sweep wrapper around the modal probe.

We do not change the pneumatic scheme. We only vary *initial pressures* and
observe how the equivalent small-signal coefficients (K,C) change.

Example
-------
python pneumo_solver_ui/tools/stabilizer_pressure_sweep.py \
  --mode roll --freq 1.0 --A 0.002 \
  --p3_bar_g 1 2 3 4 5 \
  --pacc_bar_g 2 4 6 8

Outputs in pneumo_solver_ui/modal_probe_runs/<timestamp>/
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


P_ATM = 101325.0


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_repo_importable() -> Path:
    here = Path(__file__).resolve()
    ui_root = here.parents[1]  # pneumo_solver_ui
    sys.path.insert(0, str(ui_root))
    return ui_root


def _load_params(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _road_func_sine(mode: str, A: float, w: float):
    if mode == "heave":
        signs = np.array([1, 1, 1, 1], dtype=float)
    elif mode == "roll":
        signs = np.array([1, -1, 1, -1], dtype=float)
    elif mode == "pitch":
        signs = np.array([1, 1, -1, -1], dtype=float)
    else:
        raise ValueError(mode)

    def road_func(t: float) -> np.ndarray:
        return (A * math.sin(w * t)) * signs

    return road_func


def _fit_linear(X: np.ndarray, y: np.ndarray):
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coef
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2)) + 1e-12
    r2 = 1.0 - ss_res / ss_tot
    return float(coef[0]), float(coef[1]), float(r2)


def run_once(model_name: str, params: Dict, mode: str, freq_hz: float, A: float, dt: float, settle_cycles: int, fit_cycles: int) -> Dict:
    ui_root = _ensure_repo_importable()
    model = importlib.import_module(model_name)

    w = 2 * math.pi * float(freq_hz)
    T = 1.0 / float(freq_hz)
    t_end = (settle_cycles + fit_cycles) * T

    road_func = _road_func_sine(mode, A, w)

    df_main, df_drossel, df_energy, nodes, edges, df_Eedges, df_Ecat, df_atm = model.simulate(
        params=params,
        test={
            "dt": dt,
            "t_end": t_end,
            "road_mode": "time",
            "road_func": road_func,
            "ax_func": (lambda t: 0.0),
            "ay_func": (lambda t: 0.0),
        },
    )

    # fit window
    t = df_main["время_с"].to_numpy()
    t0_fit = t_end - fit_cycles * T
    mask = t >= t0_fit
    dfw = df_main.loc[mask].copy()

    if mode == "roll":
        y = dfw["момент_крен_подвеска_Нм"].to_numpy()
        x1 = dfw["крен_phi_рад"].to_numpy()
        x2 = dfw["скорость_крен_phi_рад_с"].to_numpy()
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))
    elif mode == "pitch":
        y = dfw["момент_тангаж_подвеска_Нм"].to_numpy()
        x1 = dfw["тангаж_theta_рад"].to_numpy()
        x2 = dfw["скорость_тангаж_theta_рад_с"].to_numpy()
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))
    else:
        y = (dfw["сила_подвески_ЛП_Н"] + dfw["сила_подвески_ПП_Н"] + dfw["сила_подвески_ЛЗ_Н"] + dfw["сила_подвески_ПЗ_Н"]).to_numpy()
        x1 = dfw["перемещение_рамы_z_м"].to_numpy()
        x2 = dfw["скорость_рамы_z_м_с"].to_numpy()
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))

    K, C, r2 = _fit_linear(np.column_stack([x1, x2]), y)

    # basic energy summary
    E_dross = float(df_Ecat.loc[df_Ecat["группа"].astype(str).str.contains("дрос", case=False, regex=False), "энергия_потерь_Дж"].sum()) if (df_Ecat is not None and len(df_Ecat)) else 0.0
    E_exh = float(df_Ecat.loc[df_Ecat["группа"].astype(str).str.contains("вых", case=False, regex=False), "энергия_потерь_Дж"].sum()) if (df_Ecat is not None and len(df_Ecat)) else 0.0

    return {
        "mode": mode,
        "freq_hz": float(freq_hz),
        "A_m": float(A),
        "K": float(K),
        "C": float(C),
        "r2": float(r2),
        "amp_state": float(amp_state),
        "E_drossels_J": float(E_dross),
        "E_exhaust_J": float(E_exh),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=str, default="model_pneumo_v9_doublewishbone_camozzi")
    ap.add_argument("--params", type=str, default="pneumo_solver_ui/default_base.json")
    ap.add_argument("--mode", type=str, default="roll", choices=["heave", "roll", "pitch"])
    ap.add_argument("--freq", type=float, default=1.0)
    ap.add_argument("--A", type=float, default=0.002)
    ap.add_argument("--dt", type=float, default=0.002)
    ap.add_argument("--settle_cycles", type=int, default=6)
    ap.add_argument("--fit_cycles", type=int, default=6)
    ap.add_argument("--p3_bar_g", type=float, nargs="+", default=[2, 3, 4])
    ap.add_argument("--pacc_bar_g", type=float, nargs="+", default=[4, 6, 8])
    args = ap.parse_args()

    ui_root = _ensure_repo_importable()
    repo_root = ui_root.parent

    model_name = str(args.model)
    try:
        importlib.import_module(model_name)
    except Exception:
        model_name = 'model_pneumo_v8_energy_audit_vacuum'

    params_path = (repo_root / args.params).resolve() if not Path(args.params).is_absolute() else Path(args.params)
    base_params = _load_params(params_path)

    out_dir = ui_root / "modal_probe_runs" / ("pressure_sweep_" + _ts())
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict] = []
    for p3_g in args.p3_bar_g:
        for pacc_g in args.pacc_bar_g:
            params = dict(base_params)
            params['начальное_давление_ресивер3'] = float(P_ATM + float(p3_g) * 1e5)
            params['начальное_давление_аккумулятора'] = float(P_ATM + float(pacc_g) * 1e5)
            res = run_once(
                model_name=model_name,
                params=params,
                mode=str(args.mode),
                freq_hz=float(args.freq),
                A=float(args.A),
                dt=float(args.dt),
                settle_cycles=int(args.settle_cycles),
                fit_cycles=int(args.fit_cycles),
            )
            res['p3_bar_g'] = float(p3_g)
            res['pacc_bar_g'] = float(pacc_g)
            rows.append(res)
            print(f"[sweep] p3={p3_g}bar_g pacc={pacc_g}bar_g -> K={res['K']:.3g} C={res['C']:.3g} r2={res['r2']:.3f}")

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "pressure_sweep.csv", index=False, encoding="utf-8")

    md = []
    md.append(f"# Pressure sweep ({args.mode})\n\n")
    md.append(f"- model: `{model_name}`\n")
    md.append(f"- params: `{params_path}`\n")
    md.append(f"- freq: {args.freq} Hz, A: {args.A} m, dt: {args.dt} s\n")
    md.append(f"- p3_bar_g: {args.p3_bar_g}\n")
    md.append(f"- pacc_bar_g: {args.pacc_bar_g}\n\n")
    md.append(df.sort_values(["p3_bar_g", "pacc_bar_g"]).to_markdown(index=False))
    md.append("\n")

    (out_dir / "pressure_sweep_report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[ok] wrote: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
