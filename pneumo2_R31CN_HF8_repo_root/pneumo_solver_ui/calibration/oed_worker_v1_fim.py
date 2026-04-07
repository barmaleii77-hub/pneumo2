# -*- coding: utf-8 -*-
"""oed_worker_v1_fim.py

OED / Identifiability helper for the pneumatic suspension model.

Что делает:
- берёт список параметров (fit_ranges_json) и набор «наблюдаемых» сигналов (observables_json),
- прогоняет набор тестов (suite) и численно оценивает чувствительности выходов к параметрам,
- строит матрицу Fisher Information Matrix (FIM) и метрики идентифицируемости,
- предлагает порядок тестов (жадный D-opt) — какие эксперименты наиболее информативны.

Зачем:
- перед тем как "фитить" параметры, полезно понять, какие параметры вообще наблюдаемы,
  какие сильно коррелируют (практическая неидентифицируемость),
  и какие тесты/входы лучше всего "развязывают" параметры.

Входы:
- model.py: должен иметь simulate(params, test, dt, t_end, record_full=False, ...)
- base_json: базовые параметры модели
- fit_ranges_json: {param: [min,max], ...}
- observables_json: список наблюдаемых сигналов (можно в формате mapping_json из fit_worker)

observables_json формат (рекомендуемый минимальный):
[
  {"model_key": "перемещение_рамы_z_м", "weight": 1.0},
  {"model_key": "давление_ресивер3_Па", "weight": 1e-5},
  {"model_key": "p:Ц1_ЛП_БП", "weight": 1e-5}
]

model_key поддерживает префиксы таблиц:
- main:col  (или просто col)
- p:col
- q:col
- open:col
- Eedges:col
- Egroups:col
- atm:col

Зависимости: numpy, pandas.

"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import math
import os
import time
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
# Ensure project package is importable even when this script is launched directly
_THIS = Path(__file__).resolve()
if _THIS.parent.name == "calibration":
    _PNEUMO_ROOT = _THIS.parent.parent  # .../pneumo_solver_ui
else:
    _PNEUMO_ROOT = _THIS.parent  # .../pneumo_solver_ui
_PROJECT_ROOT = _PNEUMO_ROOT.parent  # .../project root
for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pneumo_solver_ui.module_loading import load_python_module_from_path


# --------------------------
# JSON IO
# --------------------------

def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_py_module(path: Path, module_name: str):
    return load_python_module_from_path(path, module_name)


# --------------------------
# model output helpers
# --------------------------

def parse_model_key(model_key: str) -> Tuple[str, str]:
    """Разбор model_key вида "p:NodeName" или просто "col"."""
    s = str(model_key).strip()
    if ":" in s:
        pref, col = s.split(":", 1)
        pref = pref.strip() or "main"
        col = col.strip()
        return pref, col
    return "main", s


def need_record_full(observables: List[Dict[str, Any]]) -> bool:
    for it in observables:
        mk = str(it.get("model_key", "") or it.get("key", "") or "").strip()
        if not mk:
            continue
        table, _ = parse_model_key(mk)
        if table != "main":
            return True
    return False


def _tables_from_out(out: Tuple[Any, ...], record_full: bool) -> Dict[str, Optional[pd.DataFrame]]:
    """Унифицировать доступ к таблицам выхода модели.

    По текущему проекту:
      out[0] = df_main
      if record_full:
        out[8] = df_p
        out[9] = df_q
        out[10]= df_open
        out[5] = df_Eedges
        out[6] = df_Egroups
        out[7] = df_atm

    Но на всякий случай — проверяем длины.
    """
    df_main = out[0] if len(out) > 0 else None

    df_Eedges = out[5] if (record_full and len(out) > 5) else None
    df_Egroups = out[6] if (record_full and len(out) > 6) else None
    df_atm = out[7] if (record_full and len(out) > 7) else None
    df_p = out[8] if (record_full and len(out) > 8) else None
    df_q = out[9] if (record_full and len(out) > 9) else None
    df_open = out[10] if (record_full and len(out) > 10) else None

    return {
        "main": df_main,
        "p": df_p,
        "q": df_q,
        "open": df_open,
        "Eedges": df_Eedges,
        "Egroups": df_Egroups,
        "atm": df_atm,
    }


def _get_time(df: pd.DataFrame, time_col: str) -> np.ndarray:
    if time_col in df.columns:
        return np.asarray(df[time_col], dtype=float)
    # fallback: первая колонка
    return np.asarray(df.iloc[:, 0], dtype=float)


def collect_observables_vector(
    out: Tuple[Any, ...],
    observables_triplets: List[Tuple[str, str, float]],
    t_grid: np.ndarray,
    time_col: str,
    record_full: bool,
) -> np.ndarray:
    """Вернуть вектор наблюдений (склеенный) на сетке времени t_grid.

    Важно: возвращаем УЖЕ взвешенный вектор (умноженный на weight).
    Это удобно: тогда FIM = J^T J соответствует WLS по этим весам.
    """
    tables = _tables_from_out(out, record_full=record_full)
    if tables["main"] is None:
        raise RuntimeError("Модель не вернула df_main")

    df_main = tables["main"]
    assert isinstance(df_main, pd.DataFrame)
    t_sim = _get_time(df_main, time_col)

    vec_parts: List[np.ndarray] = []
    for table, col, w in observables_triplets:
        df = tables.get(table, None)
        if df is None:
            raise RuntimeError(
                f"Нужна таблица '{table}', но record_full={record_full} и/или модель её не вернула. "
                f"Проверь model_key='{table}:{col}'."
            )
        assert isinstance(df, pd.DataFrame)
        if col not in df.columns:
            raise RuntimeError(
                f"В выходе модели ({table}) нет колонки '{col}'. "
                f"Доступно (первые 40): {list(df.columns)[:40]}"
            )
        y = np.asarray(df[col], dtype=float)
        # интерполяция на t_grid
        y_i = np.interp(t_grid, t_sim, y)
        y_i = np.where(np.isfinite(y_i), y_i, 0.0)
        vec_parts.append(float(w) * y_i)

    if not vec_parts:
        return np.zeros(0, dtype=float)

    return np.concatenate(vec_parts, axis=0)


# --------------------------
# progress
# --------------------------

class ProgressWriter:
    def __init__(self, path: Optional[Path], every_sec: float = 1.0):
        self.path = path
        self.every_sec = max(0.1, float(every_sec))
        self._last = 0.0

    def write(self, payload: Dict[str, Any], force: bool = False):
        if self.path is None:
            return
        now = time.time()
        if (not force) and (now - self._last) < self.every_sec:
            return
        self._last = now
        try:
            _save_json(payload, self.path)
        except Exception:
            pass


# --------------------------
# finite differences
# --------------------------

def _pick_fd_step(x: float, lo: float, hi: float, rel_step: float, abs_step: float) -> float:
    # базовый шаг: либо относительный, либо абсолютный
    base = max(abs_step, rel_step * max(abs(x), 1.0))
    # но не больше половины диапазона (чтобы центральная разность была возможна)
    span = max(hi - lo, 0.0)
    if span > 0:
        base = min(base, 0.45 * span)
    return max(base, 0.0)


def _fd_mode_and_steps(x: float, lo: float, hi: float, step: float) -> Tuple[str, float, float]:
    """Вернуть (mode, x_plus, x_minus) или (mode, x_plus, x0) для forward/backward."""
    if step <= 0:
        return "none", x, x

    can_plus = (x + step) <= hi
    can_minus = (x - step) >= lo

    if can_plus and can_minus:
        return "central", x + step, x - step
    if can_plus:
        return "forward", x + step, x
    if can_minus:
        return "backward", x, x - step
    # совсем у границы
    return "none", x, x


# --------------------------
# metrics
# --------------------------

def _fim_metrics(F: np.ndarray, lam: float) -> Dict[str, Any]:
    d = int(F.shape[0])
    Freg = F + float(lam) * np.eye(d)

    # eigenvalues for diagnostics
    try:
        eig = np.linalg.eigvalsh(Freg)
        eig = np.sort(np.asarray(eig, dtype=float))
    except Exception:
        eig = None

    sign, logdet = np.linalg.slogdet(Freg)
    if not np.isfinite(logdet) or sign <= 0:
        logdet_val = None
    else:
        logdet_val = float(logdet)

    rank = int(np.linalg.matrix_rank(Freg))

    cond = None
    if eig is not None:
        emax = float(np.max(eig))
        emin = float(np.min(eig))
        if emin <= 0 or not np.isfinite(emin) or not np.isfinite(emax):
            cond = None
        else:
            cond = float(emax / emin)

    out = {
        "rank": rank,
        "logdet": logdet_val,
        "eig_min": float(np.min(eig)) if eig is not None else None,
        "eig_max": float(np.max(eig)) if eig is not None else None,
        "cond": cond,
    }
    return out


def _cov_corr_from_fim(F: np.ndarray, lam: float) -> Tuple[np.ndarray, np.ndarray]:
    d = int(F.shape[0])
    Freg = F + float(lam) * np.eye(d)
    cov = np.linalg.pinv(Freg)
    diag = np.diag(cov)
    std = np.sqrt(np.clip(diag, 1e-30, np.inf))
    corr = cov / np.outer(std, std)
    corr = np.clip(corr, -1.0, 1.0)
    return cov, corr


# --------------------------
# main
# --------------------------

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--model", required=True, help="Путь к .py модели (simulate)")
    ap.add_argument("--worker", default="", help="opt_worker .py (нужен build_test_suite). По умолчанию ищется рядом.")

    ap.add_argument("--base_json", required=True, help="JSON базовых параметров")
    ap.add_argument("--fit_ranges_json", required=True, help="JSON границ: {param:[min,max]}")

    ap.add_argument("--observables_json", required=True,
                    help="JSON наблюдаемых сигналов (список объектов с model_key и weight). Можно дать mapping_json от fit_worker.")

    ap.add_argument("--suite_json", default="", help="JSON suite (список строк, как в UI). Если не задан — используется build_test_suite по умолчанию.")

    ap.add_argument("--time_col", default="t", help="Имя колонки времени в df_main")

    ap.add_argument("--sample_stride", type=int, default=5,
                    help="Брать каждый N-й момент времени из симуляции для FIM (ускоряет расчёт).")
    ap.add_argument("--record_stride", type=int, default=1,
                    help="Если модель поддерживает record_stride — уменьшить частоту записи осциллограмм (не ускоряет ODE, но уменьшает выход).")

    ap.add_argument("--rel_step", type=float, default=1e-2,
                    help="Относительный шаг конечных разностей (по параметрам)")
    ap.add_argument("--abs_step", type=float, default=0.0,
                    help="Абсолютный минимальный шаг конечных разностей")

    ap.add_argument("--lambda", dest="lam", type=float, default=0.0,
                    help="Регуляризация FIM: F_reg = F + lambda*I. Если 0 — будет взято автоматически (малое).")

    ap.add_argument("--max_tests", type=int, default=9999, help="Ограничить количество тестов для анализа")
    ap.add_argument("--only", default="", help="Список имён тестов через запятую (если хотите анализировать только часть)")

    ap.add_argument("--report_json", required=True, help="Куда сохранить отчёт")
    ap.add_argument("--progress_json", default="", help="Куда писать прогресс")
    ap.add_argument("--progress_every_sec", type=float, default=1.0)
    ap.add_argument("--stop_file", default="", help="Если файл существует — мягко остановиться")

    ap.add_argument("--use_smoothing_defaults", action="store_true",
                    help="Если модель поддерживает smooth_* — включить сглаживание (для стабильности чувствительностей).")

    args = ap.parse_args()

    model_path = Path(args.model)
    worker_path = Path(args.worker) if args.worker else (model_path.parent / "opt_worker_v3_margins_energy.py")

    base: Dict[str, Any] = _load_json(Path(args.base_json))
    fit_ranges: Dict[str, Any] = _load_json(Path(args.fit_ranges_json))
    observables_raw: Any = _load_json(Path(args.observables_json))

    if not isinstance(observables_raw, list):
        raise SystemExit("observables_json должен быть списком объектов")

    # поддержка двух форматов: {model_key, weight} или {meas_col, model_key, weight}
    observables: List[Dict[str, Any]] = []
    for it in observables_raw:
        if not isinstance(it, dict):
            continue
        mk = it.get("model_key", None)
        if mk is None:
            # fallback: кто-то мог назвать иначе
            mk = it.get("key", None)
        if mk is None:
            continue
        observables.append(it)

    if len(observables) == 0:
        raise SystemExit("В observables_json не найдено ни одного элемента с model_key")

    # params vector
    keys = list(fit_ranges.keys())
    if len(keys) == 0:
        raise SystemExit("fit_ranges_json пуст")

    lo = np.array([float(fit_ranges[k][0]) for k in keys], dtype=float)
    hi = np.array([float(fit_ranges[k][1]) for k in keys], dtype=float)

    if np.any(~np.isfinite(lo)) or np.any(~np.isfinite(hi)) or np.any(hi <= lo):
        raise SystemExit("Некорректные границы в fit_ranges_json")

    x_base = np.array([float(base.get(k, (lo[i] + hi[i]) * 0.5)) for i, k in enumerate(keys)], dtype=float)

    # optional smoothing for patched model
    if args.use_smoothing_defaults:
        base.setdefault("smooth_dynamics", True)
        base.setdefault("smooth_mechanics", True)
        base.setdefault("smooth_pressure_floor", True)
        base.setdefault("smooth_valves", True)
        base.setdefault("k_smooth_valves", 80.0)

    record_full = need_record_full(observables)
    time_col = str(args.time_col)
    sample_stride = max(1, int(args.sample_stride))
    record_stride = max(1, int(args.record_stride))

    stop_file = Path(args.stop_file) if args.stop_file else None
    progress = ProgressWriter(Path(args.progress_json) if args.progress_json else None, every_sec=args.progress_every_sec)

    # load model
    model_mod = load_py_module(model_path, "model_mod_oed")
    if not hasattr(model_mod, "simulate"):
        raise SystemExit("Модуль модели должен иметь функцию simulate")

    sim_sig = None
    try:
        sim_sig = inspect.signature(model_mod.simulate)
    except Exception:
        sim_sig = None

    def _simulate(params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float):
        if stop_file is not None and stop_file.exists():
            raise RuntimeError("STOP requested")
        kwargs = {"dt": float(dt), "t_end": float(t_end), "record_full": bool(record_full)}
        if sim_sig is not None and ("record_stride" in sim_sig.parameters):
            kwargs["record_stride"] = int(record_stride)
        return model_mod.simulate(params, test, **kwargs)

    # load worker (for suite)
    worker_mod = load_py_module(worker_path, "worker_mod_oed")
    if not hasattr(worker_mod, "build_test_suite"):
        raise SystemExit(f"В worker файле {worker_path} не найден build_test_suite")

    cfg: Dict[str, Any] = {}
    if args.suite_json:
        suite = _load_json(Path(args.suite_json))
        if not isinstance(suite, list):
            raise SystemExit("suite_json должен быть списком")
        cfg["suite"] = suite

    tests = worker_mod.build_test_suite(cfg)
    # tests: list[(name, test_dict, dt, t_end, targets)]

    only = [s.strip() for s in str(args.only).split(",") if s.strip()]
    if only:
        tests = [t for t in tests if str(t[0]) in set(only)]

    max_tests = max(1, int(args.max_tests))
    tests = tests[:max_tests]

    if len(tests) == 0:
        raise SystemExit("Не осталось тестов для анализа (проверьте --only/--suite_json)")

    # observables triplets
    obs_triplets: List[Tuple[str, str, float]] = []
    for it in observables:
        mk = str(it.get("model_key") or it.get("key") or "").strip()
        table, col = parse_model_key(mk)
        w = float(it.get("weight", 1.0))
        obs_triplets.append((table, col, w))

    # -------------------------
    # compute F for each test
    # -------------------------
    d = len(keys)
    test_F: Dict[str, np.ndarray] = {}
    test_info: Dict[str, Dict[str, Any]] = {}

    progress.write({
        "stage": "start",
        "n_tests": int(len(tests)),
        "n_params": int(d),
        "record_full": bool(record_full),
        "sample_stride": int(sample_stride),
        "record_stride": int(record_stride),
    }, force=True)

    t_start = time.time()

    for ti, (test_name, test, dt_i, t_end_i, _targets) in enumerate(tests, start=1):
        progress.write({
            "stage": "test",
            "test_idx": int(ti),
            "n_tests": int(len(tests)),
            "test": str(test_name),
        }, force=True)

        # baseline run
        params0 = dict(base)
        for k, v in zip(keys, x_base):
            params0[k] = float(v)

        out0 = _simulate(params0, test, dt=dt_i, t_end=t_end_i)
        df_main0 = out0[0]
        if not isinstance(df_main0, pd.DataFrame):
            raise RuntimeError("simulate() должен возвращать df_main как первый элемент")
        t_sim0 = _get_time(df_main0, time_col)
        if t_sim0.size < 2:
            raise RuntimeError(f"[{test_name}] слишком мало временных точек")

        # time grid for FIM
        t_grid = np.asarray(t_sim0[::sample_stride], dtype=float)
        if t_grid.size < 2:
            t_grid = np.asarray(t_sim0, dtype=float)

        y0 = collect_observables_vector(out0, obs_triplets, t_grid=t_grid, time_col=time_col, record_full=record_full)
        n_res = int(y0.size)
        if n_res == 0:
            raise RuntimeError("Наблюдаемые сигналы дали пустой вектор. Проверь observables_json")

        # sensitivity matrix S: n_res x d
        S = np.zeros((n_res, d), dtype=float)

        # compute each column
        for j, k in enumerate(keys):
            x = float(x_base[j])
            step = _pick_fd_step(x, float(lo[j]), float(hi[j]), rel_step=float(args.rel_step), abs_step=float(args.abs_step))
            mode, x_plus, x_minus = _fd_mode_and_steps(x, float(lo[j]), float(hi[j]), step)
            if mode == "none":
                # параметр невозможно пошевелить в границах — чувствительность ноль
                continue

            if mode == "central":
                p_plus = dict(params0)
                p_minus = dict(params0)
                p_plus[k] = float(x_plus)
                p_minus[k] = float(x_minus)

                out_p = _simulate(p_plus, test, dt=dt_i, t_end=t_end_i)
                out_m = _simulate(p_minus, test, dt=dt_i, t_end=t_end_i)

                y_p = collect_observables_vector(out_p, obs_triplets, t_grid=t_grid, time_col=time_col, record_full=record_full)
                y_m = collect_observables_vector(out_m, obs_triplets, t_grid=t_grid, time_col=time_col, record_full=record_full)

                denom = float(x_plus - x_minus)
                if denom == 0:
                    continue
                S[:, j] = (y_p - y_m) / denom

            elif mode == "forward":
                p_plus = dict(params0)
                p_plus[k] = float(x_plus)
                out_p = _simulate(p_plus, test, dt=dt_i, t_end=t_end_i)
                y_p = collect_observables_vector(out_p, obs_triplets, t_grid=t_grid, time_col=time_col, record_full=record_full)
                denom = float(x_plus - x)
                if denom == 0:
                    continue
                S[:, j] = (y_p - y0) / denom

            elif mode == "backward":
                p_minus = dict(params0)
                p_minus[k] = float(x_minus)
                out_m = _simulate(p_minus, test, dt=dt_i, t_end=t_end_i)
                y_m = collect_observables_vector(out_m, obs_triplets, t_grid=t_grid, time_col=time_col, record_full=record_full)
                denom = float(x - x_minus)
                if denom == 0:
                    continue
                S[:, j] = (y0 - y_m) / denom

            # optional: progress per param (не слишком часто)
            progress.write({
                "stage": "test",
                "test": str(test_name),
                "param": str(k),
                "param_idx": int(j + 1),
                "n_params": int(d),
            }, force=False)

        # FIM = S^T S
        F = S.T @ S
        test_F[str(test_name)] = F

        # per-test metrics
        sens_rms = np.sqrt(np.mean(np.square(S), axis=0))
        test_info[str(test_name)] = {
            "dt": float(dt_i),
            "t_end": float(t_end_i),
            "n_t": int(t_grid.size),
            "n_res": int(n_res),
            "sens_rms": {keys[i]: float(sens_rms[i]) for i in range(d)},
        }

    # automatic lambda
    F_total = np.zeros((d, d), dtype=float)
    for F in test_F.values():
        F_total += F

    lam = float(args.lam)
    if lam <= 0.0:
        tr = float(np.trace(F_total))
        # небольшая регуляризация относительно масштаба информации
        lam = max(1e-12, 1e-12 * (tr / max(1, d)) if tr > 0 else 1e-12)

    # metrics per test
    for name, F in test_F.items():
        test_info[name].update(_fim_metrics(F, lam=lam))

    total_metrics = _fim_metrics(F_total, lam=lam)
    cov_total, corr_total = _cov_corr_from_fim(F_total, lam=lam)

    # -------------------------
    # greedy D-opt test selection
    # -------------------------
    remaining = list(test_F.keys())
    selected: List[str] = []
    logdet_cum: List[Optional[float]] = []

    F_sel = np.zeros((d, d), dtype=float)

    for step in range(1, len(remaining) + 1):
        best_name = None
        best_logdet = None
        best_Fnew = None

        for cand in remaining:
            F_new = F_sel + test_F[cand]
            met = _fim_metrics(F_new, lam=lam)
            ld = met.get("logdet", None)
            if ld is None:
                continue
            if (best_logdet is None) or (float(ld) > float(best_logdet)):
                best_logdet = float(ld)
                best_name = cand
                best_Fnew = F_new

        if best_name is None or best_Fnew is None:
            break

        selected.append(best_name)
        logdet_cum.append(best_logdet)
        F_sel = best_Fnew
        remaining.remove(best_name)

    cov_sel, corr_sel = _cov_corr_from_fim(F_sel, lam=lam)

    elapsed = time.time() - t_start

    report = {
        "meta": {
            "model": str(model_path),
            "worker": str(worker_path),
            "elapsed_sec": float(elapsed),
            "record_full": bool(record_full),
            "sample_stride": int(sample_stride),
            "record_stride": int(record_stride),
            "rel_step": float(args.rel_step),
            "abs_step": float(args.abs_step),
            "lambda": float(lam),
        },
        "params": {
            "keys": keys,
            "lo": [float(v) for v in lo],
            "hi": [float(v) for v in hi],
            "base": [float(v) for v in x_base],
        },
        "observables": [
            {"model_key": f"{t}:{c}" if t != "main" else c, "weight": float(w)}
            for (t, c, w) in obs_triplets
        ],
        "tests": test_info,
        "suite_total": {
            **total_metrics,
            "cov": cov_total.tolist(),
            "corr": corr_total.tolist(),
        },
        "greedy_D_opt": {
            "order": selected,
            "logdet_cum": logdet_cum,
            "F_sel_cov": cov_sel.tolist(),
            "F_sel_corr": corr_sel.tolist(),
        },
    }

    _save_json(report, Path(args.report_json))
    progress.write({"stage": "done", "elapsed_sec": float(elapsed), "report_json": str(args.report_json)}, force=True)
    print("DONE. Report:", args.report_json)


if __name__ == "__main__":
    main()
