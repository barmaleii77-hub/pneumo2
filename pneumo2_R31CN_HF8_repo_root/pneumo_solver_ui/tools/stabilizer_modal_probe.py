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
import importlib
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


def _select_fit_window(df_main: pd.DataFrame, fit_cycles: int, period_s: float) -> pd.DataFrame:
    if df_main is None or len(df_main) <= 0:
        raise RuntimeError("simulate() returned empty df_main")
    t = np.asarray(df_main["время_с"].to_numpy(), dtype=float).reshape(-1)
    if t.size <= 0:
        raise RuntimeError("df_main has empty time axis")
    t_last = float(np.nanmax(t))
    fit_span = max(0.0, float(fit_cycles) * float(period_s))
    t0_fit = t_last - fit_span
    mask = t >= t0_fit - 1e-12
    dfw = df_main.loc[mask].copy()
    if len(dfw) >= 3:
        return dfw
    tail_rows = max(3, min(len(df_main), 256))
    return df_main.tail(tail_rows).copy()


def _require_series(df: pd.DataFrame, *names: str) -> np.ndarray:
    for name in names:
        if name in df.columns:
            return np.asarray(df[name].to_numpy(), dtype=float).reshape(-1)
    raise KeyError(names[0] if names else "required column is missing")


def _optional_series(df: pd.DataFrame, *names: str) -> np.ndarray | None:
    for name in names:
        if name in df.columns:
            return np.asarray(df[name].to_numpy(), dtype=float).reshape(-1)
    return None


def _numeric_derivative(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    t = np.asarray(t, dtype=float).reshape(-1)
    x = np.asarray(x, dtype=float).reshape(-1)
    if x.size <= 1 or t.size != x.size:
        return np.zeros_like(x, dtype=float)
    if float(np.nanmax(t) - np.nanmin(t)) <= 1e-12:
        return np.zeros_like(x, dtype=float)
    return np.asarray(np.gradient(x, t), dtype=float).reshape(-1)


def _corner_force_matrix(df: pd.DataFrame) -> np.ndarray:
    cols_susp = [
        "сила_подвески_ЛП_Н",
        "сила_подвески_ПП_Н",
        "сила_подвески_ЛЗ_Н",
        "сила_подвески_ПЗ_Н",
    ]
    cols_tire = [
        "нормальная_сила_шины_ЛП_Н",
        "нормальная_сила_шины_ПП_Н",
        "нормальная_сила_шины_ЛЗ_Н",
        "нормальная_сила_шины_ПЗ_Н",
    ]
    for cols in (cols_susp, cols_tire):
        if all(col in df.columns for col in cols):
            return np.column_stack([np.asarray(df[col].to_numpy(), dtype=float) for col in cols])
    raise KeyError("corner force columns are missing")


def _support_moment_from_forces(forces: np.ndarray, params: Dict, axis: str) -> np.ndarray:
    track = float(params.get("колея", params.get("track", 1.2)) or 1.2)
    wheelbase = float(params.get("база", params.get("wheelbase", 2.3)) or 2.3)
    x_pos = np.array([wheelbase / 2.0, wheelbase / 2.0, -wheelbase / 2.0, -wheelbase / 2.0], dtype=float)
    y_pos = np.array([track / 2.0, -track / 2.0, track / 2.0, -track / 2.0], dtype=float)
    if axis == "roll":
        return np.asarray(forces @ y_pos, dtype=float).reshape(-1)
    if axis == "pitch":
        return np.asarray(forces @ (-x_pos), dtype=float).reshape(-1)
    raise ValueError(axis)


def _centered_fit_arrays(x1: np.ndarray, x2: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x1 = np.asarray(x1, dtype=float).reshape(-1)
    x2 = np.asarray(x2, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)
    mask = np.isfinite(x1) & np.isfinite(x2) & np.isfinite(y)
    x1 = x1[mask]
    x2 = x2[mask]
    y = y[mask]
    if x1.size < 3:
        raise RuntimeError("not enough finite samples for modal fit")
    X = np.column_stack([x1 - float(np.mean(x1)), x2 - float(np.mean(x2))])
    y0 = y - float(np.mean(y))
    return X, y0


def _load_modal_model(model_name: str):
    _ensure_repo_importable()
    return importlib.import_module(str(model_name))


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



def run_probe(params: Dict, mode: str, freq_hz: float, A: float, settle_cycles: int, fit_cycles: int, dt: float, model_name: str = "model_pneumo_v8_energy_audit_vacuum") -> ProbeResult:
    model = _load_modal_model(model_name)

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
        dt=dt,
        t_end=t_end,
    )

    # Окно для фитинга: последние fit_cycles
    dfw = _select_fit_window(df_main, fit_cycles=fit_cycles, period_s=T)
    t_fit = _require_series(dfw, "время_с")

    # Амплитуда входа: A
    amp_in = A

    if mode == "roll":
        y = _optional_series(dfw, "момент_крен_подвеска_Нм")
        if y is None:
            y = _support_moment_from_forces(_corner_force_matrix(dfw), params, axis="roll")
        x1 = _require_series(dfw, "крен_phi_рад")
        x2 = _optional_series(dfw, "скорость_крен_phi_рад_с")
        if x2 is None:
            x2 = _numeric_derivative(t_fit, x1)
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))
    elif mode == "pitch":
        y = _optional_series(dfw, "момент_тангаж_подвеска_Нм")
        if y is None:
            y = _support_moment_from_forces(_corner_force_matrix(dfw), params, axis="pitch")
        x1 = _require_series(dfw, "тангаж_theta_рад")
        x2 = _optional_series(dfw, "скорость_тангаж_theta_рад_с")
        if x2 is None:
            x2 = _numeric_derivative(t_fit, x1)
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))
    elif mode == "heave":
        # Сила поддержки в heave: предпочтительно сумма сил подвески, fallback — сумма
        # нормальных сил шин, если модель не экспортирует отдельный suspension-force канал.
        y = np.sum(_corner_force_matrix(dfw), axis=1)
        x1 = _require_series(dfw, "перемещение_рамы_z_м")
        x2 = _optional_series(dfw, "скорость_рамы_z_м_с")
        if x2 is None:
            x2 = _numeric_derivative(t_fit, x1)
        amp_state = float(0.5 * (np.max(x1) - np.min(x1)))
    else:
        raise ValueError(mode)

    KC_X, y_fit = _centered_fit_arrays(x1, x2, y)
    K, C, r2 = _fit_linear(KC_X, y_fit)

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
    ap.add_argument("--model", type=str, default="model_pneumo_v8_energy_audit_vacuum", help="Имя python-модуля модели")
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
            res = run_probe(params=params, mode=mode, freq_hz=f, A=float(args.A), settle_cycles=int(args.settle_cycles), fit_cycles=int(args.fit_cycles), dt=float(args.dt), model_name=str(args.model))
            results.append(res)

    df = pd.DataFrame([r.__dict__ for r in results])
    df.to_csv(out_dir / "modal_probe_results.csv", index=False, encoding="utf-8")

    # Markdown report
    md = []
    md.append(f"# Modal probe report\n\n")
    md.append(f"- model: `{args.model}`\n")
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
