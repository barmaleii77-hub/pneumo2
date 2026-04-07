#!/usr/bin/env python3
"""
Stabilizer / modal probe runner (headless).

Зачем
-----
Схема пневмоподвески в проекте должна одновременно работать как:
  1) «мягкая» подвеска по ходу (heave) — глотает неровности,
  2) «стабилизатор» по крену/тангажу (roll/pitch) — сопротивляется наклонам,
  3) демпфер — гасит колебания за счёт диссипации в дросселях/выхлопе,
  4) самонакачка/автоадаптация — за счёт насосной ступени и регуляторов.

Ключевой физический принцип взаимосвязанной подвески:
  • heave (все колёса вверх/вниз синфазно) ≠ roll/pitch (противофазные движения).
  • правильная пневмо‑связь может сделать heave «мягким», а roll/pitch «жёсткими»
    за счёт знака dV в связанных камерах (на heave одна камера сжимается, другая
    разжимается; на roll/pitch — обе сжимаются/разжимаются одновременно).

Этот скрипт делает *малосигнальный* частотный «пробник»:
  - возбуждаем систему синусом малой амплитуды в режимах heave/roll/pitch,
  - по установившимся данным подбираем эквивалентную модель момента:
        M(t) ≈ K*phi(t) + C*phi_dot(t)   (roll)
        M(t) ≈ K*theta(t) + C*theta_dot(t) (pitch)
    и силы:
        Fz(t) ≈ K*z(t) + C*z_dot(t)     (heave)
  - получаем эффективные (K,C) на выбранных частотах.

Запуск
-----
Из корня проекта:
  python pneumo_solver_ui/tools/stabilizer_modal_probe.py --freq 0.5 1.0 2.0 4.0

Артефакты пишутся в:
  pneumo_solver_ui/modal_probe_runs/<timestamp>/

"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@dataclass
class ProbeResult:
    mode: str
    freq_hz: float
    K: float
    C: float
    # вспомогательные
    amp_state: float
    amp_input: float
    r2: float
    E_drossels_J: float
    E_exhaust_J: float


def _ensure_repo_importable() -> Path:
    here = Path(__file__).resolve()
    ui_root = here.parents[1]  # pneumo_solver_ui
    sys.path.insert(0, str(ui_root))
    return ui_root


def _load_params(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _road_func_sine(mode: str, A: float, w: float) -> Callable[[float], np.ndarray]:
    """Возвращает road_func(t) -> zroad[4] (ЛП,ПП,ЛЗ,ПЗ)"""
    # Соглашение: positive zroad = подъём дороги -> сжимает шину/подвеску.
    # Для roll/pitch берём противофазу.
    if mode == "heave":
        signs = np.array([1, 1, 1, 1], dtype=float)
    elif mode == "roll":
        signs = np.array([1, -1, 1, -1], dtype=float)  # левый +, правый -
    elif mode == "pitch":
        signs = np.array([1, 1, -1, -1], dtype=float)  # перед +, зад -
    else:
        raise ValueError(f"Unknown mode: {mode}")

    def road_func(t: float) -> np.ndarray:
        return (A * math.sin(w * t)) * signs

    return road_func


def _fit_linear(KC_X: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """LS fit y ≈ K*x1 + C*x2 ; returns (K,C,r2)"""
    # Solve least squares
    coef, *_ = np.linalg.lstsq(KC_X, y, rcond=None)
    y_hat = KC_X @ coef
    # R^2
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2)) + 1e-12
    r2 = 1.0 - ss_res / ss_tot
    return float(coef[0]), float(coef[1]), float(r2)


def _extract_energy_groups(df_Ecat: pd.DataFrame) -> Tuple[float, float]:
    """Возвращает (E_drossels, E_exhaust) по итогам прогона."""
    if df_Ecat is None or len(df_Ecat) == 0:
        return 0.0, 0.0
    # Ожидаемые имена групп в модели:
    #   «дроссель»  — диссипация в регулирующих сечениях (в т.ч. диагональные)
    #   «выхлоп»    — диссипация в выхлопной ветви/сбросе
    # В разных версиях может называться чуть иначе, поэтому делаем contains.
    def _sum_like(pattern: str) -> float:
        mask = df_Ecat["группа"].astype(str).str.contains(pattern, case=False, regex=False)
        if "энергия_потерь_Дж" in df_Ecat.columns:
            return float(df_Ecat.loc[mask, "энергия_потерь_Дж"].sum())
        if "энергия_Дж" in df_Ecat.columns:
            return float(df_Ecat.loc[mask, "энергия_Дж"].sum())
        # fallback: ищем любую колонку с Дж
        for c in df_Ecat.columns:
            if "Дж" in c:
                return float(df_Ecat.loc[mask, c].sum())
        return 0.0

    return _sum_like("дрос"), _sum_like("вых")


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """Минимальный markdown‑table без внешних зависимостей (без tabulate)."""
    if df is None or len(df) == 0:
        return "_no data_"
    cols = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                vals.append(f"{float(v):.6g}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)



def run_probe(params: Dict, mode: str, freq_hz: float, A: float, settle_cycles: int, fit_cycles: int, dt: float) -> ProbeResult:
    ui_root = _ensure_repo_importable()
    import model_pneumo_v8_energy_audit_vacuum as model  # noqa

    w = 2 * math.pi * freq_hz
    T = 1.0 / freq_hz
    t_end = (settle_cycles + fit_cycles) * T

    road_func = _road_func_sine(mode=mode, A=A, w=w)

    # Запуск модели. Ось: используем пустые функции ax/ay (инерции нет), только base excitation.
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

    # Окно для фитинга: последние fit_cycles
    t = df_main["время_с"].to_numpy()
    t0_fit = t_end - fit_cycles * T
    mask = t >= t0_fit
    dfw = df_main.loc[mask].copy()

    # Амплитуда входа: A
    amp_in = A

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
    elif mode == "heave":
        # Сила подвески — сумма по колёсам
        y = (dfw["сила_подвески_ЛП_Н"] + dfw["сила_подвески_ПП_Н"] + dfw["сила_подвески_ЛЗ_Н"] + dfw["сила_подвески_ПЗ_Н"]).to_numpy()
        x1 = dfw["перемещение_рамы_z_м"].to_numpy()
        x2 = dfw["скорость_рамы_z_м_с"].to_numpy()
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))
    else:
        raise ValueError(mode)

    KC_X = np.column_stack([x1, x2])
    K, C, r2 = _fit_linear(KC_X, y)

    E_dross, E_exh = _extract_energy_groups(df_Ecat)

    return ProbeResult(
        mode=mode,
        freq_hz=float(freq_hz),
        K=float(K),
        C=float(C),
        amp_state=amp_state,
        amp_input=amp_in,
        r2=float(r2),
        E_drossels_J=float(E_dross),
        E_exhaust_J=float(E_exh),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=str, default="pneumo_solver_ui/default_base.json", help="Путь к json параметров")
    ap.add_argument("--freq", type=float, nargs="+", default=[0.5, 1.0, 2.0, 4.0], help="Частоты, Гц")
    ap.add_argument("--A", type=float, default=0.002, help="Амплитуда входа (м)")
    ap.add_argument("--dt", type=float, default=0.002, help="Шаг интегрирования (с)")
    ap.add_argument("--settle_cycles", type=int, default=6, help="Сколько циклов на установление")
    ap.add_argument("--fit_cycles", type=int, default=6, help="Сколько циклов брать в фит")
    ap.add_argument("--modes", type=str, nargs="+", default=["heave", "roll", "pitch"], help="Режимы: heave roll pitch")
    args = ap.parse_args()

    ui_root = _ensure_repo_importable()
    repo_root = ui_root.parent

    params_path = (repo_root / args.params).resolve() if not Path(args.params).is_absolute() else Path(args.params)
    params = _load_params(params_path)

    out_dir = ui_root / "modal_probe_runs" / _ts()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[ProbeResult] = []
    for mode in args.modes:
        for f in args.freq:
            print(f"[probe] mode={mode} f={f}Hz A={args.A}m dt={args.dt}s")
            res = run_probe(params=params, mode=mode, freq_hz=f, A=float(args.A), settle_cycles=int(args.settle_cycles), fit_cycles=int(args.fit_cycles), dt=float(args.dt))
            results.append(res)

    df = pd.DataFrame([r.__dict__ for r in results])
    df.to_csv(out_dir / "modal_probe_results.csv", index=False, encoding="utf-8")

    # Markdown report
    md = []
    md.append(f"# Modal probe report\n\n")
    md.append(f"- params: `{params_path}`\n")
    md.append(f"- A: {args.A} m, dt: {args.dt} s\n")
    md.append(f"- settle_cycles: {args.settle_cycles}, fit_cycles: {args.fit_cycles}\n\n")

    for mode in args.modes:
        md.append(f"## {mode}\n\n")
        sub = df[df["mode"] == mode].copy().sort_values("freq_hz")
        if len(sub) == 0:
            md.append("_no data_\n\n")
            continue
        md.append(_df_to_markdown_table(sub))
        md.append("\n\n")
        md.append("Примечание: `K,C` — эквивалентные коэффициенты линейной модели по методу МНК на установившемся участке.\n\n")

    (out_dir / "modal_probe_report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[ok] wrote: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
