# -*- coding: utf-8 -*-
"""
fit_worker_v3_suite_identify.py

Идентификация параметров матмодели (подгонка) по набору тестов (suite) и
осциллограммам из UI (папка с tests_index.csv + Txx_osc.npz).

Зачем этот файл:
- v2 умеет фитить по одному тесту, но не умеет собирать test-функции из suite_json.
- В проекте тесты задаются в suite_json и превращаются в функции через build_test_suite()
  из opt_worker. Именно это нужно, чтобы "fit по NPZ из UI" был честным.

Поддерживаемый источник данных:
- osc_dir: папка, которую пишет UI через save_oscillograms_bundle(..., log_format="NPZ").
  В ней лежит:
    - tests_index.csv
    - kpi_by_test.csv
    - T01_osc.npz, T02_osc.npz, ...

Оптимизация:
- мультистарт (LHS) для выбора стартовых точек,
- затем локальная оптимизация SciPy least_squares(method="trf") с bounds и робастной loss.

Зависимости: numpy, pandas, scipy.

Пример:
  python fit_worker_v3_suite_identify.py ^
    --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py ^
    --worker opt_worker_v3_margins_energy.py ^
    --suite_json default_suite.json ^
    --osc_dir osc_logs/RUN_... ^
    --base_json default_base.json ^
    --fit_ranges_json fit_ranges.json ^
    --mapping_json mapping_npz_example_v2.json ^
    --out_json fitted_base.json ^
    --report_json fit_report.json ^
    --use_smoothing_defaults

"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, differential_evolution
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
# LHS sampling
# --------------------------
def lhs(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """Latin Hypercube Sampling: n точек в d-мерном кубе [0,1]^d."""
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.random((n, d))
    a = cut[:n]
    b = cut[1:n + 1]
    rd = u * (b - a)[:, None] + a[:, None]
    H = np.empty_like(rd)
    for j in range(d):
        order = rng.permutation(n)
        H[:, j] = rd[order, j]
    return H



# --------------------------
# Surrogate global initialization (SMBO-like)
# --------------------------
def surrogate_global_init(
    obj_fn,
    lo: np.ndarray,
    hi: np.ndarray,
    seed: int,
    model: str = "rf",
    init_samples: int = 24,
    iters: int = 8,
    batch: int = 2,
    candidate_pool: int = 3000,
    kappa: float = 2.0,
    random_frac: float = 0.2,
    n_estimators: int = 200,
    gp_alpha: float = 1e-6,
    gp_restarts: int = 2,
    patience: int = 3,
    min_improve_abs: float = 0.0,
    min_improve_rel: float = 1e-3,
    time_budget_sec: float = 0.0,
    max_evals: int = 0,
    save_csv: Optional[Path] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Surrogate-based global search to produce a good starting point.

    Подходит как global_init перед least_squares, когда есть много локальных минимумов
    и функция дорогая (много тестов/сигналов).

    Алгоритм в стиле SMBO/BO:
      1) space-filling дизайн (LHS) -> первые оценки
      2) обучаем surrogate (RF или GP) по (x, sse)
      3) выбираем новые точки минимизируя LCB: mu(x) - kappa*sigma(x)
      4) повторяем до исчерпания бюджета

    Важно: это НЕ «магия BO», а практичная эвристика. По умолчанию RF, потому что:
      - устойчивее к шуму/нелинейностям,
      - не требует тонкой настройки kernel и хорошо работает при d ~ 10..40.

    Возвращает best_x и info.
    """
    rng = np.random.default_rng(int(seed))
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    d = int(lo.size)
    span = np.clip(hi - lo, 1e-30, np.inf)

    def to_unit(x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, dtype=float) - lo) / span

    def from_unit(u: np.ndarray) -> np.ndarray:
        return lo + span * np.asarray(u, dtype=float)

    init_samples = max(1, int(init_samples))
    iters = max(0, int(iters))
    batch = max(1, int(batch))
    candidate_pool = max(50, int(candidate_pool))
    kappa = float(kappa)
    random_frac = float(random_frac)
    if max_evals and int(max_evals) > 0:
        budget = int(max_evals)
    else:
        budget = init_samples + iters * batch

    # --- initial design
    U0 = lhs(init_samples, d, rng)
    X0 = from_unit(U0)
    y0 = []
    for x in X0:
        try:
            y0.append(float(obj_fn(np.asarray(x, dtype=float))))
        except Exception:
            y0.append(float("inf"))

    X = np.asarray([to_unit(x) for x in X0], dtype=float)
    y = np.asarray(y0, dtype=float)

    best_idx = int(np.nanargmin(y)) if np.any(np.isfinite(y)) else 0
    best_u = np.asarray(X[best_idx], dtype=float)
    best_y = float(y[best_idx]) if np.isfinite(y[best_idx]) else float("inf")

    history = []
    n_evals = int(len(y))
    t_start = time.time()
    no_improve = 0
    early_stop_reason = ""

    def fit_surrogate(xu: np.ndarray, yy: np.ndarray):
        mm = str(model).strip().lower()
        if mm == "gp":
            try:
                from sklearn.gaussian_process import GaussianProcessRegressor
                from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel as C
            except Exception as e:
                raise RuntimeError(f"scikit-learn required for GP surrogate: {e}")
            # простая устойчиво-стабильная GP конфигурация
            kernel = C(1.0, (1e-3, 1e3)) * RBF(length_scale=np.ones(d), length_scale_bounds=(1e-2, 10.0)) + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-8, 1e-1))
            gp = GaussianProcessRegressor(
                kernel=kernel,
                alpha=float(gp_alpha),
                normalize_y=True,
                n_restarts_optimizer=int(gp_restarts),
                random_state=int(seed),
            )
            gp.fit(xu, yy)
            return gp
        else:
            try:
                from sklearn.ensemble import RandomForestRegressor
            except Exception as e:
                raise RuntimeError(f"scikit-learn required for RF surrogate: {e}")
            rf = RandomForestRegressor(
                n_estimators=int(max(10, n_estimators)),
                random_state=int(seed),
                n_jobs=1,
            )
            rf.fit(xu, yy)
            return rf

    def predict_mu_sigma(model_obj, xu: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        mm = str(model).strip().lower()
        if mm == "gp":
            mu, std = model_obj.predict(xu, return_std=True)
            return np.asarray(mu, dtype=float), np.asarray(std, dtype=float)
        # RF: mean is predict(); sigma by per-tree spread
        mu = np.asarray(model_obj.predict(xu), dtype=float)
        try:
            trees = getattr(model_obj, "estimators_", None)
            if trees:
                preds = np.stack([np.asarray(t.predict(xu), dtype=float) for t in trees], axis=1)
                std = np.std(preds, axis=1)
            else:
                std = np.zeros_like(mu)
        except Exception:
            std = np.zeros_like(mu)
        return mu, std

    # --- SMBO loop
    for it in range(int(iters)):
        if n_evals >= budget:
            break
        if float(time_budget_sec) > 0.0 and (time.time() - t_start) >= float(time_budget_sec):
            early_stop_reason = "time_budget"
            break
        best_before_iter = float(best_y)

        # fit only on finite observations
        mask = np.isfinite(y)
        if int(np.sum(mask)) < max(4, min(2 * d, 20)):
            # если слишком мало валидных точек — добавим случайных
            U_more = rng.random((max(4, d), d))
            X_more = from_unit(U_more)
            y_more = []
            for x in X_more:
                try:
                    y_more.append(float(obj_fn(np.asarray(x, dtype=float))))
                except Exception:
                    y_more.append(float("inf"))
            X = np.vstack([X, U_more])
            y = np.concatenate([y, np.asarray(y_more, dtype=float)])
            n_evals = int(len(y))
            mask = np.isfinite(y)

        model_obj = fit_surrogate(X[mask], y[mask])

        # candidates
        Uc = rng.random((candidate_pool, d))
        mu, sig = predict_mu_sigma(model_obj, Uc)
        sig = np.clip(sig, 0.0, np.inf)
        # Lower Confidence Bound for minimization
        acq = mu - float(kappa) * sig
        order = np.argsort(acq)

        n_exploit = int(round(batch * max(0.0, 1.0 - random_frac)))
        n_exploit = max(1, min(batch, n_exploit))
        n_rand = int(batch - n_exploit)

        chosen = []
        for idx in order[: max(10, n_exploit * 5)]:
            u = np.asarray(Uc[int(idx)], dtype=float)
            chosen.append(u)
            if len(chosen) >= n_exploit:
                break
        if n_rand > 0:
            chosen += [rng.random(d) for _ in range(n_rand)]

        # evaluate chosen
        for u in chosen:
            if n_evals >= budget:
                break
            x = from_unit(u)
            try:
                val = float(obj_fn(np.asarray(x, dtype=float)))
            except Exception:
                val = float("inf")
            X = np.vstack([X, np.asarray(u, dtype=float)[None, :]])
            y = np.concatenate([y, np.asarray([val], dtype=float)])
            n_evals += 1
            if np.isfinite(val) and val < best_y:
                best_y = float(val)
                best_u = np.asarray(u, dtype=float)

        history.append({
            "iter": int(it),
            "n_evals": int(n_evals),
            "best_sse_before": float(best_before_iter),
            "best_sse": float(best_y),
        })

        # early stop by lack of significant improvement
        thr = float(min_improve_abs)
        if np.isfinite(best_before_iter):
            thr = max(thr, float(min_improve_rel) * abs(float(best_before_iter)))

        significant = (np.isfinite(float(best_y)) and ((not np.isfinite(best_before_iter)) or (float(best_y) < float(best_before_iter) - thr)))
        if significant:
            no_improve = 0
        else:
            no_improve += 1

        if int(patience) > 0 and no_improve >= int(patience):
            early_stop_reason = "patience"
            break

    best_x = from_unit(best_u)

    info = {
        "model": str(model),
        "init_samples": int(init_samples),
        "iters": int(iters),
        "batch": int(batch),
        "candidate_pool": int(candidate_pool),
        "kappa": float(kappa),
        "random_frac": float(random_frac),
        "n_estimators": int(n_estimators),
        "gp_alpha": float(gp_alpha),
        "gp_restarts": int(gp_restarts),
        "patience": int(patience),
        "min_improve_abs": float(min_improve_abs),
        "min_improve_rel": float(min_improve_rel),
        "time_budget_sec": float(time_budget_sec),
        "budget": int(budget),
        "n_evals": int(n_evals),
        "best_sse": float(best_y),
        "early_stop_reason": (str(early_stop_reason) if str(early_stop_reason) else None),
        "no_improve": int(no_improve),
        "history": history,
    }

    # optionally save dataset for offline analysis/debug
    if save_csv is not None:
        try:
            import pandas as _pd
            rows = []
            for uu, yy in zip(X.tolist(), y.tolist()):
                rows.append({f"u{i}": float(uu[i]) for i in range(d)} | {"sse": float(yy)})
            df = _pd.DataFrame(rows)
            save_csv.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(save_csv, index=False, encoding="utf-8-sig")
            info["dataset_csv"] = str(save_csv)
        except Exception:
            pass

    return best_x, info



# --------------------------
# NPZ osc loading
# --------------------------
def _npz_to_df(cols_key: str, values_key: str, z: np.lib.npyio.NpzFile) -> Optional[pd.DataFrame]:
    if cols_key not in z or values_key not in z:
        return None
    cols = z[cols_key].tolist()
    vals = z[values_key]
    return pd.DataFrame(vals, columns=cols)


def load_meas_npz(path: Path) -> Dict[str, pd.DataFrame]:
    z = np.load(path, allow_pickle=True)
    out: Dict[str, pd.DataFrame] = {}
    out["main"] = _npz_to_df("main_cols", "main_values", z)
    out["p"] = _npz_to_df("p_cols", "p_values", z)
    out["q"] = _npz_to_df("q_cols", "q_values", z)
    out["open"] = _npz_to_df("open_cols", "open_values", z)
    out["Eedges"] = _npz_to_df("Eedges_cols", "Eedges_values", z)
    out["Egroups"] = _npz_to_df("Egroups_cols", "Egroups_values", z)
    out["atm"] = _npz_to_df("atm_cols", "atm_values", z)
    out = {k: v for k, v in out.items() if isinstance(v, pd.DataFrame)}
    return out


# --------------------------
# mapping helpers
# --------------------------
def parse_model_key(model_key: str) -> Tuple[str, str]:
    if ":" in model_key:
        pref, col = model_key.split(":", 1)
        pref = pref.strip() or "main"
        return pref, col.strip()
    return "main", model_key.strip()


def need_record_full(mapping: List[Dict[str, Any]]) -> bool:
    for m in mapping:
        mk = str(m.get("model_key", "")).strip()
        table, _ = parse_model_key(mk)
        if table != "main":
            return True
    return False


def tables_from_out(out: Tuple[Any, ...], record_full: bool) -> Dict[str, Optional[pd.DataFrame]]:
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




# --------------------------
# time helpers (NPZ может быть с разными частотами записи по таблицам)
# --------------------------
def detect_time_col(df_main: pd.DataFrame) -> str:
    """Выбрать колонку времени в df_main.

    В UI/модели обычно это 'время_с'. В некоторых старых версиях — 't'.
    """
    for c in ("время_с", "t", "time", "Time", "timestamp", "Timestamp"):
        if c in df_main.columns:
            return str(c)
    # fallback: первый столбец
    return str(df_main.columns[0])


def extract_time_vector(df: pd.DataFrame, time_col: str, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    """Достать вектор времени из таблицы.

    Если time_col отсутствует — пробуем первый столбец. Если не получилось и есть fallback — используем fallback.
    """
    if time_col in df.columns:
        try:
            t = np.asarray(df[time_col], dtype=float)
            return t
        except Exception:
            pass
    # fallback to first col
    try:
        t0 = np.asarray(df.iloc[:, 0], dtype=float)
        return t0
    except Exception:
        if fallback is not None:
            return np.asarray(fallback, dtype=float)
        raise


def ensure_sorted_by_time(t: np.ndarray, *arrs: np.ndarray) -> Tuple[np.ndarray, ...]:
    """Гарантировать неубывающий t; при необходимости отсортировать и остальные массивы одинаково."""
    if t.size < 2:
        return (t,) + arrs
    if np.any(np.diff(t) < 0):
        order = np.argsort(t)
        out = [t[order]]
        for a in arrs:
            out.append(a[order])
        return tuple(out)
    return (t,) + arrs
class StopRequested(RuntimeError):
    pass


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
# Cross-Entropy Method (CEM) global initialization
# --------------------------

def cem_global_init(
    obj_fn,
    lo: np.ndarray,
    hi: np.ndarray,
    seed: int,
    pop: int = 64,
    iters: int = 8,
    elite_frac: float = 0.15,
    alpha: float = 0.7,
    init_sigma: float = 0.35,
    min_sigma: float = 0.05,
    diag_only: bool = False,
    time_budget_sec: float = 0.0,
    patience: int = 3,
    min_improve_rel: float = 1e-3,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Cross-Entropy Method (continuous) to propose a good starting point.

    Идея: поддерживаем распределение N(mu, Sigma) в единичном кубе u∈[0,1]^d.
    На каждом шаге:
      - сэмплируем популяцию,
      - считаем objective (SSE),
      - берём элиту (лучшие elite_frac),
      - обновляем mu/Sigma (с EMA-сглаживанием alpha).

    Это простой, но очень практичный глобальный инициализатор для дорогих функций
    с множеством локальных минимумов.

    Возвращает best_x в физических координатах и info.
    """

    rng = np.random.default_rng(int(seed))
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    d = int(lo.size)
    span = np.clip(hi - lo, 1e-30, np.inf)

    def to_unit(x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, dtype=float) - lo) / span

    def from_unit(u: np.ndarray) -> np.ndarray:
        return lo + span * np.asarray(u, dtype=float)

    pop = max(4, int(pop))
    iters = max(1, int(iters))
    elite_frac = float(elite_frac)
    elite_frac = min(0.9, max(0.02, elite_frac))
    n_elite = max(2, int(round(pop * elite_frac)))

    alpha = float(alpha)
    alpha = min(1.0, max(0.05, alpha))

    init_sigma = float(init_sigma)
    min_sigma = float(min_sigma)
    init_sigma = max(min(1.0, init_sigma), 1e-6)
    min_sigma = max(min(1.0, min_sigma), 1e-8)

    # distribution in unit cube
    mu = np.full(d, 0.5, dtype=float)
    sig = np.full(d, init_sigma, dtype=float)
    cov = np.diag(sig * sig)

    best_u = mu.copy()
    best_y = float('inf')
    history = []

    t0 = time.time()
    no_improve = 0
    early_stop_reason = ''

    for it in range(iters):
        if time_budget_sec and (time.time() - t0) > float(time_budget_sec):
            early_stop_reason = 'time_budget'
            break

        # sample U ~ N(mu,cov), clip to [0,1]
        if bool(diag_only):
            Z = rng.normal(size=(pop, d))
            U = mu[None, :] + Z * np.sqrt(np.clip(np.diag(cov), 1e-18, np.inf))[None, :]
        else:
            # add tiny jitter for numerical stability
            cov_j = cov + np.eye(d) * 1e-12
            U = rng.multivariate_normal(mean=mu, cov=cov_j, size=pop)

        U = np.clip(U, 0.0, 1.0)
        X = from_unit(U)

        Y = np.empty(pop, dtype=float)
        for i in range(pop):
            try:
                Y[i] = float(obj_fn(np.asarray(X[i], dtype=float)))
            except Exception:
                Y[i] = float('inf')

        # update best
        finite = np.isfinite(Y)
        if np.any(finite):
            j = int(np.nanargmin(Y))
            yj = float(Y[j])
            if yj < best_y:
                rel = (best_y - yj) / max(1e-12, abs(best_y)) if np.isfinite(best_y) else 1.0
                best_y = yj
                best_u = U[j].copy()
                if rel >= float(min_improve_rel):
                    no_improve = 0
                else:
                    no_improve += 1
            else:
                no_improve += 1
        else:
            no_improve += 1

        # elites
        order = np.argsort(Y)
        elites = U[order[:n_elite]]

        mu_new = np.mean(elites, axis=0)
        if bool(diag_only):
            var_new = np.var(elites, axis=0) + (min_sigma ** 2)
            cov_new = np.diag(var_new)
        else:
            cov_new = np.cov(elites.T) + np.eye(d) * (min_sigma ** 2)

        # EMA smoothing
        mu = (1.0 - alpha) * mu + alpha * mu_new
        cov = (1.0 - alpha) * cov + alpha * cov_new

        # keep in cube
        mu = np.clip(mu, 0.0, 1.0)

        history.append({
            'iter': int(it + 1),
            'best_sse': float(best_y) if np.isfinite(best_y) else None,
            'mean_u_min': float(np.min(mu)),
            'mean_u_max': float(np.max(mu)),
        })

        if patience and int(patience) > 0 and no_improve >= int(patience):
            early_stop_reason = 'patience'
            break

    info = {
        'pop': int(pop),
        'iters': int(iters),
        'elite_frac': float(elite_frac),
        'alpha': float(alpha),
        'diag_only': bool(diag_only),
        'best_sse': float(best_y) if np.isfinite(best_y) else None,
        'early_stop_reason': str(early_stop_reason),
        'history': history,
        'time_sec': float(time.time() - t0),
    }

    return from_unit(best_u), info

# --------------------------
# tests / suite
# --------------------------
def load_suite(worker_mod, suite_obj: Any) -> List[Tuple[str, Dict[str, Any], float, float, Dict[str, Any]]]:
    """
    Возвращает список (name, test, dt, t_end, targets) через build_test_suite(cfg).
    suite_obj может быть:
      - list (как default_suite.json)
      - dict с ключом 'suite'
    """
    if isinstance(suite_obj, list):
        cfg = {"suite": suite_obj}
    elif isinstance(suite_obj, dict):
        cfg = dict(suite_obj)
        if "suite" not in cfg and isinstance(cfg.get("tests", None), list):
            cfg["suite"] = cfg["tests"]
    else:
        raise ValueError("suite_json должен быть списком или словарём")

    if not hasattr(worker_mod, "build_test_suite"):
        raise RuntimeError("В worker модуле нет функции build_test_suite(cfg)")

    tests = worker_mod.build_test_suite(cfg)
    # ожидается список (name, test, dt, t_end, targets)
    return tests


def load_osc_dir(osc_dir: Path) -> pd.DataFrame:
    idx_path = osc_dir / "tests_index.csv"
    if not idx_path.exists():
        raise FileNotFoundError(f"Не найден {idx_path}. Ожидается папка из UI save_oscillograms_bundle(...).")
    df = pd.read_csv(idx_path, encoding="utf-8-sig")
    # нормализуем имена колонок (вдруг пользователь руками менял)
    cols = {c: c.strip() for c in df.columns}
    df = df.rename(columns=cols)
    need = ["номер", "имя_теста", "dt_с", "t_end_с"]
    for c in need:
        if c not in df.columns:
            raise RuntimeError(f"В tests_index.csv нет колонки '{c}'. Есть: {list(df.columns)}")
    df = df.sort_values("номер").reset_index(drop=True)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Путь к .py файлу модели (simulate(params,test,dt,t_end,...))")
    ap.add_argument("--worker", required=True, help="Путь к opt_worker (нужен build_test_suite)")
    ap.add_argument("--suite_json", required=True, help="suite JSON (как default_suite.json)")

    ap.add_argument("--osc_dir", required=True, help="Папка осциллограмм из UI (tests_index.csv + Txx_osc.npz)")
    ap.add_argument("--base_json", required=True, help="Базовые параметры модели")
    ap.add_argument("--fit_ranges_json", required=True, help="Границы подгонки: {param:[min,max],...}")
    ap.add_argument("--mapping_json", required=True, help="Соответствие измерений и выходов модели (как в v2)")

    ap.add_argument("--group_weights_json", default="", help="Опционально: JSON словарь {sig_group: gain,...}. Множитель применяется ПОСЛЕ auto_scale, чтобы управлять компромиссом между группами сигналов (multi-objective trade-off).")
    ap.add_argument("--epsilon_constraints_json", default="", help="Опционально: JSON с epsilon-constraints (ограничения на качество по группам сигналов). Каждое ограничение: sig_group/group, epsilon (RMSE в unbiased шкале), penalty (вес штрафа), smooth(softplus|hinge), beta (для softplus).")

    ap.add_argument("--time_col", default="auto", help="Колонка времени: auto -> время_с / t / первый столбец")
    ap.add_argument("--meas_stride", type=int, default=1, help="Проредить измерения по времени: брать каждый N-й отсчёт (ускоряет фит). 1 = без прореживания.")

    ap.add_argument("--only_tests", default="", help="Опционально: список имён тестов через запятую. Если пусто — все из osc_dir.")
    ap.add_argument("--holdout_tests", default="", help="Опционально: список имён тестов через запятую, которые НЕ участвуют в fit, но будут посчитаны в отчёте как holdout.")
    ap.add_argument("--auto_scale", default="none", help="Автонормировка сигналов: none/mad/std/range. Применяется к already weighted сигналу (weight*y), чтобы вклад разных сигналов был сопоставим.")
    ap.add_argument("--auto_scale_eps", type=float, default=1e-12, help="Эпсилон для авто-нормировки (защита от деления на 0)")
    ap.add_argument("--details_json", default="", help="Опционально: куда сохранить детализацию по тестам/сигналам (JSON)")

    ap.add_argument("--n_init", type=int, default=24, help="Сколько стартов оценить LHS перед локальной оптимизацией")
    ap.add_argument("--n_best", type=int, default=4, help="Сколько лучших стартов запускать в least_squares")
    ap.add_argument("--seed", type=int, default=1, help="Seed LHS")

    ap.add_argument("--loss", default="soft_l1", help="loss для least_squares (linear/soft_l1/huber/cauchy/arctan)")
    ap.add_argument("--f_scale", type=float, default=1.0, help="f_scale для робастных loss")
    ap.add_argument("--max_nfev", type=int, default=220, help="max_nfev на один локальный старт")


    # Глобальная инициализация (опционально): помогает, если много локальных минимумов
    ap.add_argument("--global_init", default="none", choices=["none", "de", "surrogate", "cem"],
                    help="Глобальная инициализация перед least_squares: none|de|surrogate|cem|cem")
    ap.add_argument("--de_maxiter", type=int, default=8, help="DE: maxiter (осторожно, дорого)")
    ap.add_argument("--de_popsize", type=int, default=10, help="DE: popsize")
    ap.add_argument("--de_tol", type=float, default=0.01, help="DE: tol")
    ap.add_argument("--de_polish", action="store_true", help="DE: polish (может быть очень дорого)")

    # Cross-Entropy Method (CEM) global init (continuous). Используется только если --global_init cem.
    ap.add_argument("--cem_pop", type=int, default=64, help="CEM: population per iteration")
    ap.add_argument("--cem_iters", type=int, default=8, help="CEM: number of iterations")
    ap.add_argument("--cem_elite_frac", type=float, default=0.15, help="CEM: elite fraction (0..1)")
    ap.add_argument("--cem_alpha", type=float, default=0.7, help="CEM: EMA smoothing for mean/cov update (0..1)")
    ap.add_argument("--cem_init_sigma", type=float, default=0.35, help="CEM: initial sigma in unit space [0..1]")
    ap.add_argument("--cem_min_sigma", type=float, default=0.05, help="CEM: floor sigma in unit space")
    ap.add_argument("--cem_diag_only", action="store_true", help="CEM: use diagonal covariance only")
    ap.add_argument("--cem_time_budget_sec", type=float, default=0.0, help="CEM: optional time budget (0=off)")
    ap.add_argument("--cem_patience", type=int, default=3, help="CEM: early-stop patience (iters without improvement). 0=off")
    ap.add_argument("--cem_min_improve_rel", type=float, default=1e-3, help="CEM: min relative improvement to reset patience")



    # Surrogate global init (SMBO-like). Используется только если --global_init surrogate.
    ap.add_argument("--surr_model", default="rf", choices=["rf", "gp"], help="Surrogate model: rf (RandomForest) | gp (GaussianProcess)")
    ap.add_argument("--surr_init_samples", type=int, default=24, help="Surrogate: initial LHS samples")
    ap.add_argument("--surr_iters", type=int, default=8, help="Surrogate: SMBO iterations")
    ap.add_argument("--surr_batch", type=int, default=2, help="Surrogate: points evaluated per iteration")
    ap.add_argument("--surr_candidate_pool", type=int, default=3000, help="Surrogate: random candidate pool size per iteration")
    ap.add_argument("--surr_kappa", type=float, default=2.0, help="Surrogate: LCB kappa (mu - kappa*sigma) for minimization")
    ap.add_argument("--surr_random_frac", type=float, default=0.2, help="Surrogate: fraction of random exploration points in each batch [0..1]")
    ap.add_argument("--surr_max_evals", type=int, default=0, help="Surrogate: max evaluations (0=auto: init + iters*batch)")
    ap.add_argument("--surr_n_estimators", type=int, default=200, help="Surrogate RF: n_estimators")
    ap.add_argument("--surr_gp_alpha", type=float, default=1e-6, help="Surrogate GP: alpha (nugget)")
    ap.add_argument("--surr_gp_restarts", type=int, default=2, help="Surrogate GP: n_restarts_optimizer")
    ap.add_argument("--surr_save_csv", default="", help="Опционально: сохранить датасет (u0..u{d-1}, sse) в CSV для анализа")
    ap.add_argument("--surr_patience", type=int, default=3, help="Surrogate: early-stop patience (итерации без улучшения). 0=выкл")
    ap.add_argument("--surr_min_improve_abs", type=float, default=0.0, help="Surrogate: минимум абсолютного улучшения SSE для сброса patience")
    ap.add_argument("--surr_min_improve_rel", type=float, default=0.001, help="Surrogate: минимум относительного улучшения SSE (доля от best_before)")
    ap.add_argument("--surr_time_budget_sec", type=float, default=0.0, help="Surrogate: бюджет времени (сек) на глобальную инициализацию. 0=без ограничения")



    # Блочная доводка (опционально): снижает эффект 'слипания' параметров (сильные corr)
    ap.add_argument("--block_refine", action="store_true",
                    help="После лучшего least_squares сделать block coordinate refinement по corr")
    ap.add_argument("--block_corr_thr", type=float, default=0.85, help="Порог |corr| для объединения параметров в блок")
    ap.add_argument("--block_max_size", type=int, default=6, help="Максимальный размер блока")
    ap.add_argument("--block_sweeps", type=int, default=2, help="Количество проходов по блокам")
    ap.add_argument("--block_max_nfev", type=int, default=120, help="max_nfev на один блок")
    ap.add_argument("--block_polish_nfev", type=int, default=120, help="max_nfev на финальный polish после блоков")

    ap.add_argument("--record_stride", type=int, default=1, help="record_stride при record_full=True (обычно 1)")
    ap.add_argument("--use_smoothing_defaults", action="store_true", help="Включить smooth_* параметры (если модель их знает)")

    ap.add_argument("--out_json", required=True, help="Куда сохранить найденные параметры (полный base+замены)")
    ap.add_argument("--report_json", required=True, help="Куда сохранить отчёт")
    ap.add_argument("--progress_json", default="", help="Куда писать прогресс (JSON)")
    ap.add_argument("--progress_every_sec", type=float, default=1.0, help="Период обновления progress_json")
    ap.add_argument("--stop_file", default="", help="Если файл существует — мягко остановиться")

    args = ap.parse_args()

    model_mod = load_py_module(Path(args.model), "model_mod_fit_v3")
    worker_mod = load_py_module(Path(args.worker), "worker_mod_fit_v3")

    suite_obj = _load_json(Path(args.suite_json))
    tests_suite = load_suite(worker_mod, suite_obj)
    tests_by_name = {name: (test, float(dt), float(t_end)) for name, test, dt, t_end, _targets in tests_suite}

    osc_dir = Path(args.osc_dir)
    df_idx = load_osc_dir(osc_dir)

    only = [s.strip() for s in str(args.only_tests).split(",") if s.strip()]
    only_set = set(only)

    holdout = [s.strip() for s in str(args.holdout_tests).split(",") if s.strip()]
    holdout_set = set(holdout)

    # align tests: by osc_dir index
    tests = []
    for _, row in df_idx.iterrows():
        name = str(row["имя_теста"])
        group = "holdout" if (holdout_set and (name in holdout_set)) else "train"
        if only_set and name not in only_set:
            continue
        if name not in tests_by_name:
            # возможно suite_json отличается от того, чем писали osc_dir
            continue
        test, _dt_suite, _t_end_suite = tests_by_name[name]
        dt_i = float(row["dt_с"])
        t_end_i = float(row["t_end_с"])
        idx_i = int(row["номер"])
        npz_path = osc_dir / f"T{idx_i:02d}_osc.npz"
        if not npz_path.exists():
            raise FileNotFoundError(f"Не найден {npz_path}")
        meas_tables = load_meas_npz(npz_path)

        tests.append({
            "номер": idx_i,
            "имя": name,
            "group": group,
            "dt": dt_i,
            "t_end": t_end_i,
            "test": test,
            "meas": meas_tables,
        })

    if not tests:
        raise SystemExit("Не удалось сопоставить ни одного теста (suite_json vs tests_index.csv).")

    n_train = sum(1 for tt in tests if tt.get("group") == "train")
    if n_train == 0:
        raise SystemExit("Все выбранные тесты помечены как holdout; не осталось тестов для fit.")

    base_params: Dict[str, Any] = _load_json(Path(args.base_json))
    fit_ranges: Dict[str, Any] = _load_json(Path(args.fit_ranges_json))
    mapping: List[Dict[str, Any]] = _load_json(Path(args.mapping_json))

    # Optional: per-signal-group gains applied AFTER auto_scale.
    # This allows multi-objective trade-offs (e.g., pressure vs kinematics) without being normalized away by auto_scale.
    group_weights: Dict[str, float] = {}
    if str(args.group_weights_json).strip():
        try:
            gw = _load_json(Path(args.group_weights_json))
            if not isinstance(gw, dict):
                raise ValueError("group_weights_json must be a JSON object/dict")
            group_weights = {str(k): float(v) for k, v in gw.items()}
        except Exception as e:
            raise SystemExit(f"Не удалось прочитать --group_weights_json={args.group_weights_json}: {e}")


    # Optional: epsilon-constraints on groups (multiobjective via constraints).
    # Each constraint limits unbiased RMSE of a group (computed with w_raw/scale, without group_gain).
    epsilon_constraints: List[Dict[str, Any]] = []
    if str(args.epsilon_constraints_json).strip():
        try:
            ec = _load_json(Path(args.epsilon_constraints_json))
            if isinstance(ec, dict) and "constraints" in ec:
                ec_list = ec.get("constraints")
            else:
                ec_list = ec
            if not isinstance(ec_list, list):
                raise ValueError("epsilon_constraints_json must be a list or {constraints:[...]}")
            for c in ec_list:
                if not isinstance(c, dict):
                    continue
                g = str(c.get("sig_group", c.get("group", ""))).strip()
                if not g:
                    continue
                eps = float(c.get("epsilon"))
                pen = float(c.get("penalty", 1000.0))
                if not np.isfinite(eps) or not np.isfinite(pen):
                    continue
                smooth = str(c.get("smooth", "softplus")).strip().lower()
                beta = float(c.get("beta", 50.0))
                apply_to = str(c.get("apply_to", "train")).strip().lower()
                epsilon_constraints.append({
                    "sig_group": g,
                    "epsilon": float(eps),
                    "penalty": float(pen),
                    "smooth": smooth,
                    "beta": float(beta),
                    "apply_to": apply_to,
                })
        except Exception as e:
            raise SystemExit(f"Не удалось прочитать --epsilon_constraints_json={args.epsilon_constraints_json}: {e}")

    auto_scale = str(args.auto_scale).strip().lower()
    if auto_scale not in ("none", "mad", "std", "range"):
        raise SystemExit(f"Неверный --auto_scale={auto_scale}. Допустимо: none/mad/std/range.")
    auto_scale_eps = float(args.auto_scale_eps)

    # smoothing defaults
    if args.use_smoothing_defaults:
        base_params.setdefault("smooth_dynamics", True)
        base_params.setdefault("smooth_mechanics", True)
        base_params.setdefault("smooth_pressure_floor", True)
        base_params.setdefault("smooth_valves", True)
        base_params.setdefault("k_smooth_valves", 80.0)

    # x vector
    keys = list(fit_ranges.keys())
    lo = np.array([float(fit_ranges[k][0]) for k in keys], dtype=float)
    hi = np.array([float(fit_ranges[k][1]) for k in keys], dtype=float)
    if np.any(hi <= lo):
        bad = [k for k in keys if not (float(fit_ranges[k][1]) > float(fit_ranges[k][0]))]
        raise SystemExit(f"Некорректные границы (hi<=lo) для: {bad}")

    x_base = np.array([float(base_params.get(k, (lo[i] + hi[i]) * 0.5)) for i, k in enumerate(keys)], dtype=float)

    # compile mapping
    record_full = need_record_full(mapping)
    record_stride = max(1, int(args.record_stride))
    meas_stride = max(1, int(args.meas_stride))
    time_col = str(args.time_col)

    map_specs = []
    for m in mapping:
        meas_col = str(m.get("meas_col", "")).strip()
        model_key = str(m.get("model_key", "")).strip()
        # signal group (optional): used with --group_weights_json
        sig_group = str(m.get("sig_group", m.get("group", ""))).strip() or "default"
        meas_table = str(m.get("meas_table", "main")).strip()
        weight = float(m.get("weight", 1.0))
        t_min = m.get("t_min", None)
        t_max = m.get("t_max", None)
        # optional time shift (seconds): shifts measurement time axis by +time_shift_s
        time_shift_s = m.get("time_shift_s", m.get("dt_shift_s", 0.0))
        t_min = float(t_min) if t_min is not None else None
        t_max = float(t_max) if t_max is not None else None
        try:
            time_shift_s = float(time_shift_s)
        except Exception:
            time_shift_s = 0.0
        if not meas_col or not model_key:
            raise SystemExit(f"Плохой mapping item (нужны meas_col и model_key): {m}")
        map_specs.append((meas_table, meas_col, model_key, sig_group, weight, t_min, t_max, time_shift_s))

    # resolve time_col (auto)
    time_col_arg = str(args.time_col).strip()
    if time_col_arg.lower() in ("auto", ""):
        # try detect from first test main table
        df0 = None
        for tt in tests:
            mm = tt.get("meas", {})
            if isinstance(mm, dict) and isinstance(mm.get("main", None), pd.DataFrame):
                df0 = mm["main"]
                break
        if df0 is None:
            raise RuntimeError("Не найдено ни одной main таблицы в NPZ (нужно для времени).")
        time_col = detect_time_col(df0)
    else:
        time_col = time_col_arg

    # precompile measurement arrays per test
    # ВАЖНО: в UI (record_stride=N) таблицы p/q/open часто пишутся реже, чем main.
    # Поэтому для каждого сигнала берём СВОЙ t_meas из meas_table (если есть), иначе fallback на main.
    tests_compiled = []
    for t in tests:
        meas: Dict[str, pd.DataFrame] = t["meas"]
        if "main" not in meas or not isinstance(meas["main"], pd.DataFrame):
            raise RuntimeError(f"[{t['имя']}] В NPZ нет таблицы 'main'.")

        df_main = meas["main"]
        t_main = extract_time_vector(df_main, time_col)
        if t_main.size < 2:
            raise RuntimeError(f"[{t['имя']}] слишком мало точек времени в main.")

        meas_vecs = []
        for meas_table, meas_col, model_key, sig_group, w, t_min, t_max, time_shift_s in map_specs:
            if meas_table not in meas:
                raise RuntimeError(f"[{t['имя']}] В NPZ нет таблицы '{meas_table}' (mapping {meas_table}:{meas_col}).")
            df_tbl = meas[meas_table]
            if meas_col not in df_tbl.columns:
                raise RuntimeError(f"[{t['имя']}] В NPZ({meas_table}) нет колонки '{meas_col}'.")

            y = np.asarray(df_tbl[meas_col], dtype=float)

            # time vector for this meas_table
            t_vec = None
            if time_col in df_tbl.columns:
                t_vec = np.asarray(df_tbl[time_col], dtype=float)
            else:
                # fallback: если длина совпадает — используем main time
                if len(y) == len(t_main):
                    t_vec = np.asarray(t_main, dtype=float)
                else:
                    t_vec = extract_time_vector(df_tbl, time_col, fallback=t_main)

            if len(t_vec) != len(y):
                raise RuntimeError(
                    f"[{t['имя']}] Длины t и y не совпали для {meas_table}.{meas_col}: "
                    f"len(t)={len(t_vec)}, len(y)={len(y)}. "
                    f"Проверьте log_stride/формат NPZ."
                )

            # ensure sorted
            t_vec, y = ensure_sorted_by_time(np.asarray(t_vec, dtype=float), y)

            mask = np.isfinite(y) & np.isfinite(t_vec)
            if t_min is not None:
                mask = mask & (t_vec >= float(t_min))
            if t_max is not None:
                mask = mask & (t_vec <= float(t_max))

            if not np.any(mask):
                # Нечего фитить по этому сигналу в данном тесте (всё NaN/вне окна)
                continue

            # фильтруем + (опционально) прореживаем по времени для ускорения
            t_use = np.asarray(t_vec[mask], dtype=float)
            y_use = np.asarray(y[mask], dtype=float)
            if meas_stride > 1 and t_use.size > 2:
                t_use = t_use[::meas_stride]
                y_use = y_use[::meas_stride]

            # после фильтрации/прореживания все точки валидны
            # optional constant time shift (seconds) for this signal (meas time axis)
            if float(time_shift_s) != 0.0:
                t_use = t_use + float(time_shift_s)
            mask_use = np.ones_like(t_use, dtype=bool)

            w_raw = float(w)
            w_eff = w_raw
            scale = 1.0
            if auto_scale != "none":
                y_w = (w_raw * y_use)
                if y_w.size >= 2:
                    try:
                        if auto_scale == "mad":
                            med = np.median(y_w)
                            mad = np.median(np.abs(y_w - med))
                            scale = float(1.4826 * mad)
                        elif auto_scale == "std":
                            scale = float(np.std(y_w))
                        elif auto_scale == "range":
                            q95, q05 = np.percentile(y_w, [95.0, 5.0])
                            scale = float(q95 - q05)
                        else:
                            scale = 1.0
                    except Exception:
                        scale = 1.0
                    if (not np.isfinite(scale)) or (scale < auto_scale_eps):
                        scale = 1.0
                w_eff = w_raw / float(scale)

            group_gain = float(group_weights.get(str(sig_group), 1.0))
            w_eff = float(w_eff) * float(group_gain)
            meas_vecs.append((meas_table, meas_col, str(model_key), str(sig_group), float(group_gain), float(time_shift_s), t_use, y_use, mask_use, float(w_eff), float(w_raw), float(scale)))

        tests_compiled.append({
            "имя": t["имя"],
            "dt": float(t["dt"]),
            "t_end": float(t["t_end"]),
            "group": str(t.get("group", "train")),
            "test": t["test"],
            "meas_vecs": meas_vecs,
        })


    tests_compiled_train = [tc for tc in tests_compiled if tc.get("group", "train") == "train"]
    tests_compiled_holdout = [tc for tc in tests_compiled if tc.get("group", "train") != "train"]

    stop_file = Path(args.stop_file) if args.stop_file else None
    progress = ProgressWriter(Path(args.progress_json) if args.progress_json else None, every_sec=float(args.progress_every_sec))

    # Optional: collect residual block meta (signal/group slices) for Jacobian/FIM diagnostics
    res_meta_blocks: Optional[List[Dict[str, Any]]] = None

    def simulate(params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float):
        if record_full:
            return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=True, record_stride=record_stride)
        return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=False)

    def residuals(x: np.ndarray) -> np.ndarray:
        if stop_file is not None and stop_file.exists():
            raise StopRequested("STOP file detected")

        params = dict(base_params)
        for k, v in zip(keys, x):
            params[k] = float(v)

        res_parts: List[np.ndarray] = []
        cursor = 0  # residual row cursor (for optional meta)
        # For epsilon-constraints we need unbiased group RMSE (w_raw/scale, без group_gain)
        group_sse_unb: Dict[str, float] = {}
        group_n_unb: Dict[str, int] = {}
        need_groups = set([c.get('sig_group') for c in epsilon_constraints]) if epsilon_constraints else None
        for t in tests_compiled_train:
            out = simulate(params, t["test"], dt=float(t["dt"]), t_end=float(t["t_end"]))
            tables = tables_from_out(out, record_full=record_full)
            df_main = tables["main"]
            if df_main is None:
                raise RuntimeError(f"[{t['имя']}] Модель не вернула df_main")
            # time in main
            t_sim_main = extract_time_vector(df_main, time_col)

            for (meas_table, meas_col, model_key, sig_group, group_gain, time_shift_s, t_meas, y_meas, mask, w, w_raw, scale) in t["meas_vecs"]:
                table, col = parse_model_key(model_key)
                df = tables.get(table, None)
                if df is None:
                    raise RuntimeError(f"[{t['имя']}] Модель не вернула таблицу '{table}' (нужно для {model_key}).")
                if col not in df.columns:
                    raise RuntimeError(f"[{t['имя']}] В выходе модели ({table}) нет колонки '{col}'.")

                y_sim = np.asarray(df[col], dtype=float)
                # time for this sim table (если нет — fallback на main)
                if (time_col in df.columns) and (len(df) == len(y_sim)):
                    t_sim = np.asarray(df[time_col], dtype=float)
                else:
                    # fallback: если длины совпадают — используем main
                    if len(y_sim) == len(t_sim_main):
                        t_sim = np.asarray(t_sim_main, dtype=float)
                    else:
                        t_sim = extract_time_vector(df, time_col, fallback=t_sim_main)

                if len(t_sim) != len(y_sim):
                    raise RuntimeError(
                        f"[{t['имя']}] Длины t_sim и y_sim не совпали для {table}.{col}: "
                        f"len(t_sim)={len(t_sim)}, len(y_sim)={len(y_sim)}. "
                        f"Проверьте record_stride и/или time_col."
                    )

                # ensure sorted
                t_sim, y_sim = ensure_sorted_by_time(np.asarray(t_sim, dtype=float), y_sim)

                # interp to this signal time
                y_sim_i = np.interp(np.asarray(t_meas, dtype=float), t_sim, y_sim)

                # extra safety: exclude points outside sim range (иначе np.interp зажмёт на концах)
                if t_sim.size >= 2:
                    mask2 = mask & (t_meas >= float(t_sim[0])) & (t_meas <= float(t_sim[-1]))
                else:
                    mask2 = mask

                if not np.all(mask2):
                    y_sim_i = y_sim_i[mask2]
                    y_meas_i = y_meas[mask2]
                else:
                    y_meas_i = y_meas

                diff = (y_sim_i - y_meas_i)
                # unbiased group accumulation (without group_gain): w_raw/scale
                gname = str(sig_group)
                if (need_groups is not None) and (gname in need_groups):
                    w_unb = float(w_raw) / float(scale) if float(scale) != 0.0 else float(w_raw)
                    rr = w_unb * diff
                    group_sse_unb[gname] = group_sse_unb.get(gname, 0.0) + float(np.dot(rr, rr))
                    group_n_unb[gname] = group_n_unb.get(gname, 0) + int(rr.size)
                if float(w) != 0.0:
                    if res_meta_blocks is not None:
                        # store mapping of this residual block to signal/group for Jacobian diagnostics
                        w_unb_meta = float(w_raw) / float(scale) if float(scale) != 0.0 else float(w_raw)
                        res_meta_blocks.append({
                            "block_type": "signal",
                            "test": str(t["имя"]),
                            "sig_group": str(gname),
                            "meas_table": str(meas_table),
                            "meas_col": str(meas_col),
                            "model_key": str(model_key),
                            "time_shift_s": float(time_shift_s),
                            "group_gain": float(group_gain),
                            "w_eff": float(w),
                            "w_unb": float(w_unb_meta),
                            "n": int(diff.size),
                            "start": int(cursor),
                            "end": int(cursor + int(diff.size)),
                        })
                    res_parts.append(float(w) * diff)
                    cursor += int(diff.size)

        # epsilon-constraints (global, aggregated over train tests)
        if epsilon_constraints:
            for c in epsilon_constraints:
                if str(c.get('apply_to', 'train')).lower() not in ('train', 'all'):
                    continue
                g = str(c.get('sig_group', '')).strip()
                if not g:
                    continue
                n_g = int(group_n_unb.get(g, 0))
                if n_g <= 0:
                    raise RuntimeError(f"Epsilon-constraint group '{g}' has no samples. Проверь sig_group в signals.csv/mapping.")
                rmse_g = float(math.sqrt(float(group_sse_unb.get(g, 0.0)) / max(1, n_g)))
                eps = float(c.get('epsilon', 0.0))
                viol = rmse_g - eps
                if str(c.get('smooth', 'softplus')).lower() == 'softplus':
                    beta = float(c.get('beta', 50.0))
                    z = beta * viol
                    if z > 50.0:
                        pos = float(viol)
                    elif z < -50.0:
                        pos = float(math.exp(z) / max(1e-12, beta))
                    else:
                        pos = float(math.log1p(math.exp(z)) / max(1e-12, beta))
                else:
                    pos = float(max(0.0, viol))
                pen = float(c.get('penalty', 1000.0))
                if pen > 0.0:
                    if res_meta_blocks is not None:
                        res_meta_blocks.append({
                            "block_type": "epsilon",
                            "sig_group": str(g),
                            "penalty": float(pen),
                            "epsilon": float(eps),
                            "n": 1,
                            "start": int(cursor),
                            "end": int(cursor + 1),
                        })
                    res_parts.append(np.asarray([math.sqrt(pen) * pos], dtype=float))
                    cursor += 1
        if not res_parts:
            return np.zeros(0, dtype=float)
        return np.concatenate(res_parts, axis=0)



    # --- global init (optional): differential evolution
    de_info = None
    de_x = None
    if str(args.global_init).lower().strip() == "de":
        progress.write({
            "stage": "global_init_de",
            "maxiter": int(args.de_maxiter),
            "popsize": int(args.de_popsize),
            "tol": float(args.de_tol),
            "polish": bool(args.de_polish),
        }, force=True)

        bounds = [(float(a), float(b)) for a, b in zip(lo.tolist(), hi.tolist())]

        def sse_obj(x):
            # differential_evolution expects scalar objective
            r = residuals(np.asarray(x, dtype=float))
            return float(np.dot(r, r))

        try:
            de_res = differential_evolution(
                sse_obj,
                bounds=bounds,
                maxiter=int(args.de_maxiter),
                popsize=int(args.de_popsize),
                tol=float(args.de_tol),
                polish=bool(args.de_polish),
                seed=int(args.seed),
                updating="deferred",
                workers=1,
            )
            de_x = np.asarray(de_res.x, dtype=float)
            de_info = {
                "success": bool(de_res.success),
                "message": str(de_res.message),
                "fun_sse": float(de_res.fun),
                "nfev": int(getattr(de_res, "nfev", -1)),
            }
        except StopRequested:
            progress.write({"stage": "stopped_in_de"}, force=True)
            raise SystemExit("Остановлено пользователем (STOP file) во время DE.")
        except Exception as e:
            de_info = {"success": False, "error": str(e)}

        progress.write({"stage": "global_init_de_done", "de_info": de_info}, force=True)

    
    # --- global init (optional): surrogate (SMBO-like)
    surr_info = None
    surr_x = None
    if str(args.global_init).lower().strip() == "surrogate":
        progress.write({
            "stage": "global_init_surrogate",
            "model": str(args.surr_model),
            "init_samples": int(args.surr_init_samples),
            "iters": int(args.surr_iters),
            "batch": int(args.surr_batch),
            "candidate_pool": int(args.surr_candidate_pool),
            "kappa": float(args.surr_kappa),
            "random_frac": float(args.surr_random_frac),
            "max_evals": int(args.surr_max_evals),
            "patience": int(args.surr_patience),
            "min_improve_abs": float(args.surr_min_improve_abs),
            "min_improve_rel": float(args.surr_min_improve_rel),
            "time_budget_sec": float(args.surr_time_budget_sec),
        }, force=True)

        def sse_obj(x):
            r = residuals(np.asarray(x, dtype=float))
            return float(np.dot(r, r))

        save_csv = Path(args.surr_save_csv) if str(args.surr_save_csv).strip() else None
        try:
            surr_x, info0 = surrogate_global_init(
                sse_obj,
                lo=lo,
                hi=hi,
                seed=int(args.seed),
                model=str(args.surr_model),
                init_samples=int(args.surr_init_samples),
                iters=int(args.surr_iters),
                batch=int(args.surr_batch),
                candidate_pool=int(args.surr_candidate_pool),
                kappa=float(args.surr_kappa),
                random_frac=float(args.surr_random_frac),
                n_estimators=int(args.surr_n_estimators),
                gp_alpha=float(args.surr_gp_alpha),
                gp_restarts=int(args.surr_gp_restarts),
                patience=int(args.surr_patience),
                min_improve_abs=float(args.surr_min_improve_abs),
                min_improve_rel=float(args.surr_min_improve_rel),
                time_budget_sec=float(args.surr_time_budget_sec),
                max_evals=int(args.surr_max_evals),
                save_csv=save_csv,
            )
            surr_info = {"success": True, **(info0 if isinstance(info0, dict) else {})}
        except StopRequested:
            progress.write({"stage": "stopped_in_surrogate"}, force=True)
            raise SystemExit("Остановлено пользователем (STOP file) во время surrogate global init.")
        except Exception as e:
            surr_info = {"success": False, "error": str(e)}

        progress.write({"stage": "global_init_surrogate_done", "surrogate_info": surr_info}, force=True)

    # --- global init (optional): CEM (Cross-Entropy Method)
    cem_info = None
    cem_x = None
    if str(args.global_init).lower().strip() == "cem":
        progress.write({
            "stage": "global_init_cem",
            "pop": int(args.cem_pop),
            "iters": int(args.cem_iters),
            "elite_frac": float(args.cem_elite_frac),
            "alpha": float(args.cem_alpha),
            "init_sigma": float(args.cem_init_sigma),
            "min_sigma": float(args.cem_min_sigma),
            "diag_only": bool(args.cem_diag_only),
            "time_budget_sec": float(args.cem_time_budget_sec),
            "patience": int(args.cem_patience),
            "min_improve_rel": float(args.cem_min_improve_rel),
        }, force=True)

        def sse_obj(x):
            r = residuals(np.asarray(x, dtype=float))
            return float(np.dot(r, r))

        try:
            cem_x, info0 = cem_global_init(
                sse_obj,
                lo=lo,
                hi=hi,
                seed=int(args.seed),
                pop=int(args.cem_pop),
                iters=int(args.cem_iters),
                elite_frac=float(args.cem_elite_frac),
                alpha=float(args.cem_alpha),
                init_sigma=float(args.cem_init_sigma),
                min_sigma=float(args.cem_min_sigma),
                diag_only=bool(args.cem_diag_only),
                time_budget_sec=float(args.cem_time_budget_sec),
                patience=int(args.cem_patience),
                min_improve_rel=float(args.cem_min_improve_rel),
            )
            cem_info = {"success": True, **(info0 if isinstance(info0, dict) else {})}
        except StopRequested:
            progress.write({"stage": "stopped_in_cem"}, force=True)
            raise SystemExit("Остановлено пользователем (STOP file) во время CEM global init.")
        except Exception as e:
            cem_info = {"success": False, "error": str(e)}

        progress.write({"stage": "global_init_cem_done", "cem_info": cem_info}, force=True)

    # --- init eval (LHS)
    rng = np.random.default_rng(int(args.seed))
    n_init = max(1, int(args.n_init))
    d = len(keys)
    U = lhs(n_init, d, rng)
    X_lhs = lo + (hi - lo) * U

    extras = [np.asarray(x_base, dtype=float)[None, :]]
    if (de_x is not None) and (np.asarray(de_x).shape == np.asarray(x_base).shape):
        extras.append(np.asarray(de_x, dtype=float)[None, :])
    if (surr_x is not None) and (np.asarray(surr_x).shape == np.asarray(x_base).shape):
        extras.append(np.asarray(surr_x, dtype=float)[None, :])
    if (cem_x is not None) and (np.asarray(cem_x).shape == np.asarray(x_base).shape):
        extras.append(np.asarray(cem_x, dtype=float)[None, :])

    X = np.vstack(extras + [X_lhs])

    scored: List[Tuple[float, np.ndarray]] = []
    progress.write({"stage": "init_eval", "n_total": int(len(X))}, force=True)

    for i, x in enumerate(X):
        try:
            r = residuals(x)
            sse = float(np.dot(r, r))
        except StopRequested:
            progress.write({"stage": "stopped_in_init", "i": int(i)}, force=True)
            raise SystemExit("Остановлено пользователем (STOP file).")
        except Exception:
            sse = float("inf")
        scored.append((sse, x.copy()))
        if math.isfinite(sse):
            best_sse = float(min(s for s, _ in scored))
        else:
            best_sse = None
        progress.write({"stage": "init_eval", "i": int(i + 1), "n_total": int(len(X)), "best_sse": best_sse})

    scored.sort(key=lambda t: t[0])
    seeds = [x for s, x in scored[: max(1, int(args.n_best))]]

    best = None
    best_cost = float("inf")
    runs = []

    progress.write({"stage": "local_search", "n_starts": int(len(seeds))}, force=True)

    for j, x_start in enumerate(seeds, start=1):
        try:
            t0 = time.time()
            res = least_squares(
                residuals,
                x_start,
                bounds=(lo, hi),
                method="trf",
                loss=str(args.loss),
                f_scale=float(args.f_scale),
                x_scale="jac",
                jac="2-point",
                max_nfev=int(args.max_nfev),
            )
            dt_run = time.time() - t0
            run_row = {
                "start_idx": int(j),
                "success": bool(res.success),
                "status": int(res.status),
                "message": str(res.message),
                "cost": float(res.cost),
                "sse": float(np.dot(res.fun, res.fun)),
                "rmse": float(math.sqrt(2.0 * res.cost / max(1, res.fun.size))),
                "nfev": int(res.nfev),
                "time_sec": float(dt_run),
            }
            runs.append(run_row)

            if float(res.cost) < best_cost:
                best_cost = float(res.cost)
                best = res

            progress.write({
                "stage": "local_search",
                "start_idx": int(j),
                "n_starts": int(len(seeds)),
                "best_cost": float(best_cost),
                "last_cost": float(res.cost),
                "last_nfev": int(res.nfev),
            })
        except StopRequested:
            progress.write({"stage": "stopped_in_local", "start_idx": int(j)}, force=True)
            raise SystemExit("Остановлено пользователем (STOP file).")

    if best is None:
        raise SystemExit("Не удалось получить результат least_squares (все старты упали).")

    # --- optional: block coordinate refinement (уменьшает сильные корреляции параметров)
    block_refine_info = None

    def _corr_from_res(res):
        """Оценка cov/corr по Якобиану (Gauss-Newton)."""
        try:
            J = np.asarray(res.jac, dtype=float)
            m = int(J.shape[0])
            n = int(J.shape[1])
            if m <= n or n <= 0:
                return None, None
            JTJ = J.T @ J
            s2 = float(2.0 * res.cost / max(1, (m - n)))
            cov = np.linalg.pinv(JTJ) * s2
            dstd = np.sqrt(np.clip(np.diag(cov), 1e-30, np.inf))
            corr = cov / np.outer(dstd, dstd)
            return cov, corr
        except Exception:
            return None, None

    if bool(args.block_refine):
        _cov0, _corr0 = _corr_from_res(best)
        if _corr0 is None:
            block_refine_info = {"enabled": True, "skipped": "corr unavailable"}
        else:
            thr = float(args.block_corr_thr)
            max_size = int(args.block_max_size)
            sweeps = int(args.block_sweeps)

            npar = int(_corr0.shape[0])
            # adjacency list where |corr| >= thr
            adj = [set() for _ in range(npar)]
            for i in range(npar):
                for j in range(i + 1, npar):
                    if abs(float(_corr0[i, j])) >= thr:
                        adj[i].add(j)
                        adj[j].add(i)

            # connected components
            seen = set()
            comps = []
            for i in range(npar):
                if i in seen:
                    continue
                stack = [i]
                seen.add(i)
                comp = []
                while stack:
                    u = stack.pop()
                    comp.append(u)
                    for v in adj[u]:
                        if v not in seen:
                            seen.add(v)
                            stack.append(v)
                comps.append(sorted(comp))

            blocks = [c for c in comps if len(c) >= 2]
            # split too-large blocks
            out_blocks = []
            for b in blocks:
                if len(b) <= max_size:
                    out_blocks.append(b)
                else:
                    # split by degree (heuristic)
                    b_sorted = sorted(b, key=lambda idx: len(adj[idx]), reverse=True)
                    for k in range(0, len(b_sorted), max_size):
                        out_blocks.append(sorted(b_sorted[k:k + max_size]))
            blocks = out_blocks

            if not blocks:
                block_refine_info = {"enabled": True, "skipped": f"no blocks above thr={thr}"}
            else:
                x_curr = np.asarray(best.x, dtype=float).copy()
                cost_before = float(best.cost)
                hist = []

                progress.write({"stage": "block_refine", "n_blocks": int(len(blocks)), "sweeps": sweeps}, force=True)

                try:
                    for sw in range(sweeps):
                        for bi, idxs in enumerate(blocks):
                            idxs = np.asarray(idxs, dtype=int)
                            x0b = x_curr[idxs]
                            lob = lo[idxs]
                            hib = hi[idxs]

                            def residuals_block(xb):
                                x_full = x_curr.copy()
                                x_full[idxs] = np.asarray(xb, dtype=float)
                                return residuals(x_full)

                            t0 = time.time()
                            resb = least_squares(
                                residuals_block,
                                x0b,
                                bounds=(lob, hib),
                                method="trf",
                                loss=str(args.loss),
                                f_scale=float(args.f_scale),
                                x_scale="jac",
                                jac="2-point",
                                max_nfev=int(args.block_max_nfev),
                            )
                            dt_run = time.time() - t0

                            x_curr[idxs] = np.asarray(resb.x, dtype=float)
                            hist.append({
                                "sweep": int(sw + 1),
                                "block_idx": int(bi + 1),
                                "block_size": int(len(idxs)),
                                "params": [keys[int(k)] for k in idxs.tolist()],
                                "cost": float(resb.cost),
                                "rmse": float(math.sqrt(2.0 * resb.cost / max(1, resb.fun.size))),
                                "nfev": int(resb.nfev),
                                "success": bool(resb.success),
                                "time_sec": float(dt_run),
                            })

                            progress.write({
                                "stage": "block_refine",
                                "sweep": int(sw + 1),
                                "block": int(bi + 1),
                                "n_blocks": int(len(blocks)),
                                "best_cost": float(min(cost_before, resb.cost)),
                                "last_cost": float(resb.cost),
                            })

                except StopRequested:
                    progress.write({"stage": "stopped_in_block_refine"}, force=True)
                    raise SystemExit("Остановлено пользователем (STOP file) во время block refine.")

                # финальный polish (full vector)
                try:
                    t0 = time.time()
                    resp = least_squares(
                        residuals,
                        x_curr,
                        bounds=(lo, hi),
                        method="trf",
                        loss=str(args.loss),
                        f_scale=float(args.f_scale),
                        x_scale="jac",
                        jac="2-point",
                        max_nfev=int(args.block_polish_nfev),
                    )
                    dtp = time.time() - t0
                except StopRequested:
                    progress.write({"stage": "stopped_in_block_polish"}, force=True)
                    raise SystemExit("Остановлено пользователем (STOP file) во время polish.")

                cost_after = float(resp.cost)
                if cost_after <= cost_before:
                    best = resp

                block_refine_info = {
                    "enabled": True,
                    "thr": thr,
                    "max_size": max_size,
                    "sweeps": sweeps,
                    "n_blocks": int(len(blocks)),
                    "blocks": [[keys[int(k)] for k in b] for b in blocks],
                    "cost_before": cost_before,
                    "cost_after": float(best.cost),
                    "polish_time_sec": float(dtp),
                    "history": hist,
                }

    fitted = dict(base_params)
    for k, v in zip(keys, best.x):
        fitted[k] = float(v)

    _save_json(fitted, Path(args.out_json))

    # covariance/correlation approx
    cov = None
    corr = None
    try:
        J = np.asarray(best.jac, dtype=float)
        m = int(J.shape[0])
        n = int(J.shape[1])
        if m > n and n > 0:
            JTJ = J.T @ J
            s2 = float(2.0 * best.cost / max(1, (m - n)))
            cov = np.linalg.pinv(JTJ) * s2
            dstd = np.sqrt(np.clip(np.diag(cov), 1e-30, np.inf))
            corr = cov / np.outer(dstd, dstd)
    except Exception:
        cov = None
        corr = None


    # group sensitivity diagnostics from Jacobian slices (by sig_group)
    group_sensitivity = None
    jac_col_norm_eff = None
    jac_col_norm_unb = None
    jac_col_rms_eff = None
    jac_col_rms_unb = None
    param_std = None
    param_rel_std = None
    try:
        J_best = np.asarray(best.jac, dtype=float)
        n_params = int(J_best.shape[1]) if (J_best is not None and getattr(J_best, "ndim", 0) == 2) else 0

        # collect residual blocks once at optimum (train residual vector)
        res_meta_blocks = []
        try:
            _ = residuals(np.asarray(best.x, dtype=float))
            blocks = list(res_meta_blocks)
        finally:
            res_meta_blocks = None

        stats: Dict[str, Any] = {}
        if (J_best is not None) and getattr(J_best, "ndim", 0) == 2 and blocks:
            for b in blocks:
                if str(b.get("block_type", "")) != "signal":
                    continue
                g = str(b.get("sig_group", "default")).strip() or "default"
                s = int(b.get("start", 0))
                e = int(b.get("end", 0))
                if e <= s:
                    continue
                sl = slice(s, e)
                Jb = np.asarray(J_best[sl, :], dtype=float)

                gg = float(b.get("group_gain", 1.0))
                if (not math.isfinite(gg)) or abs(gg) < 1e-12:
                    gg = 1.0
                Jbu = Jb / float(gg)

                st = stats.setdefault(g, {
                    "n_rows": 0,
                    "jac_sq_eff": 0.0,
                    "jac_sq_unb": 0.0,
                    "fim_unb": (np.zeros((n_params, n_params), dtype=float) if n_params > 0 else None),
                    "col_sq_unb": (np.zeros((n_params,), dtype=float) if n_params > 0 else None),
                })

                st["n_rows"] = int(st.get("n_rows", 0)) + int(Jb.shape[0])
                st["jac_sq_eff"] = float(st.get("jac_sq_eff", 0.0)) + float(np.sum(Jb * Jb))
                st["jac_sq_unb"] = float(st.get("jac_sq_unb", 0.0)) + float(np.sum(Jbu * Jbu))

                if n_params > 0:
                    st["fim_unb"] += (Jbu.T @ Jbu)
                    st["col_sq_unb"] += np.sum(Jbu * Jbu, axis=0)

        out: Dict[str, Any] = {}
        for g, st in stats.items():
            n_rows = int(st.get("n_rows", 0))
            if n_rows <= 0:
                continue
            sq_eff = float(st.get("jac_sq_eff", 0.0))
            sq_unb = float(st.get("jac_sq_unb", 0.0))

            gg_out = {
                "n_rows": int(n_rows),
                "n_params": int(n_params),
                "jac_row_rms_eff": float(math.sqrt(max(0.0, sq_eff) / max(1, n_rows))),
                "jac_row_rms_unb": float(math.sqrt(max(0.0, sq_unb) / max(1, n_rows))),
                "jac_fro_eff": float(math.sqrt(max(0.0, sq_eff))),
                "jac_fro_unb": float(math.sqrt(max(0.0, sq_unb))),
                "fim_trace_unb": float(max(0.0, sq_unb)),
            }

            if n_params > 0 and isinstance(st.get("fim_unb", None), np.ndarray):
                try:
                    eig = np.linalg.eigvalsh(np.asarray(st["fim_unb"], dtype=float))
                    mx = float(np.max(eig)) if eig.size else 0.0
                    tol = 1e-12
                    rank = int(np.sum(eig > tol * mx)) if mx > 0 else 0
                    gg_out["fim_rank_unb"] = int(rank)
                    gg_out["fim_eigvals_unb"] = [float(v) for v in eig.tolist()]
                except Exception:
                    pass

            if n_params > 0 and isinstance(st.get("col_sq_unb", None), np.ndarray):
                try:
                    cn = np.sqrt(np.clip(np.asarray(st["col_sq_unb"], dtype=float), 0.0, np.inf))
                    order = np.argsort(-cn)[: min(6, int(cn.size))]
                    gg_out["top_params_unb"] = [
                        {"param": str(keys[int(i)]), "col_norm": float(cn[int(i)])}
                        for i in order.tolist()
                        if float(cn[int(i)]) > 0.0
                    ]
                except Exception:
                    pass

            out[str(g)] = gg_out


        # global Jacobian column norms (useful for automatic parameter pruning)
        try:
            if n_params > 0:
                # Effective norms: full Jacobian as used in optimization (includes penalty rows)
                col_sq_eff = np.sum(J_best * J_best, axis=0)
                col_norm_eff = np.sqrt(np.clip(col_sq_eff, 0.0, np.inf))
                jac_col_norm_eff = {keys[i]: float(col_norm_eff[i]) for i in range(n_params)}
                m_eff = int(J_best.shape[0]) if getattr(J_best, 'ndim', 0) == 2 else 0
                if m_eff <= 0:
                    m_eff = 1
                jac_col_rms_eff = {keys[i]: float(col_norm_eff[i] / math.sqrt(float(m_eff))) for i in range(n_params)}

                # Unbiased norms: sum over signal-block Jacobians divided by group_gain
                col_sq_unb = np.zeros((n_params,), dtype=float)
                n_rows_sig = 0
                for _st in stats.values():
                    if isinstance(_st.get('col_sq_unb', None), np.ndarray):
                        col_sq_unb += np.asarray(_st['col_sq_unb'], dtype=float)
                        n_rows_sig += int(_st.get('n_rows', 0))
                col_norm_unb = np.sqrt(np.clip(col_sq_unb, 0.0, np.inf))
                jac_col_norm_unb = {keys[i]: float(col_norm_unb[i]) for i in range(n_params)}
                if n_rows_sig <= 0:
                    n_rows_sig = 1
                jac_col_rms_unb = {keys[i]: float(col_norm_unb[i] / math.sqrt(float(n_rows_sig))) for i in range(n_params)}
        except Exception:
            pass

        group_sensitivity = out

    except Exception as e:
        group_sensitivity = {"error": str(e)}


    # per-parameter uncertainty proxies from cov (if available)
    try:
        if cov is not None:
            cov_m = np.asarray(cov, dtype=float)
            if getattr(cov_m, 'ndim', 0) == 2 and cov_m.shape[0] == cov_m.shape[1] and cov_m.shape[0] == len(keys):
                std = np.sqrt(np.clip(np.diag(cov_m), 1e-30, np.inf))
                param_std = {keys[i]: float(std[i]) for i in range(len(keys))}
                x_abs = np.abs(np.asarray(best.x, dtype=float))
                denom = np.maximum(x_abs, 1e-12)
                rel = std / denom
                param_rel_std = {keys[i]: float(rel[i]) for i in range(len(keys))}
    except Exception:
        pass

    report = {
        "best_cost": float(best.cost),
        "best_sse": float(np.dot(best.fun, best.fun)),
        "best_rmse": float(math.sqrt(2.0 * best.cost / max(1, best.fun.size))),
        "success": bool(best.success),
        "status": int(best.status),
        "message": str(best.message),
        "nfev": int(best.nfev),
        "keys": keys,
        "x": [float(v) for v in best.x],
        "runs": runs,
        "cov": cov.tolist() if cov is not None else None,
        "corr": corr.tolist() if corr is not None else None,
        "loss": str(args.loss),
        "f_scale": float(args.f_scale),
        "record_full": bool(record_full),
        "record_stride": int(record_stride),
        "meas_stride": int(meas_stride),
        "tests_fit": [t["имя"] for t in tests_compiled_train],
        "tests_holdout": [t["имя"] for t in tests_compiled_holdout],
        "tests_all": [t["имя"] for t in tests_compiled],
        "auto_scale": str(auto_scale),
        "global_init": {"method": str(args.global_init), "de": de_info, "surrogate": surr_info},
        "block_refine": block_refine_info,
        "auto_scale_eps": float(auto_scale_eps),
        "group_weights_json": str(args.group_weights_json),
        "epsilon_constraints_json": str(args.epsilon_constraints_json),
        "epsilon_constraints": epsilon_constraints,

        "group_weights": group_weights if group_weights else None,

        "jac_col_norm_eff": jac_col_norm_eff,
        "jac_col_norm_unb": jac_col_norm_unb,
        "jac_col_rms_eff": jac_col_rms_eff,
        "jac_col_rms_unb": jac_col_rms_unb,
        "param_std": param_std,
        "param_rel_std": param_rel_std,

        "group_sensitivity": group_sensitivity,
    }
    _save_json(report, Path(args.report_json))

    if args.details_json:
        details = {
            "auto_scale": str(auto_scale),
            "auto_scale_eps": float(auto_scale_eps),
            "group_weights_json": str(args.group_weights_json),
            "epsilon_constraints_json": str(args.epsilon_constraints_json),
            "epsilon_constraints": epsilon_constraints,
            "group_weights": group_weights if group_weights else None,
            "loss": str(args.loss),
            "f_scale": float(args.f_scale),
            "record_full": bool(record_full),
            "record_stride": int(record_stride),
        "meas_stride": int(meas_stride),
            "tests": [],
            "signals": [],
        }

        for t in tests_compiled:
            out = simulate(fitted, t["test"], dt=float(t["dt"]), t_end=float(t["t_end"]))
            tables = tables_from_out(out, record_full=record_full)
            df_main = tables["main"]
            if df_main is None:
                raise RuntimeError(f"[{t['имя']}] Модель не вернула df_main")
            # time in main
            t_sim_main = extract_time_vector(df_main, time_col)

            sse_test = 0.0
            n_test = 0

            for (meas_table, meas_col, model_key, sig_group, group_gain, time_shift_s, t_meas, y_meas, mask, w, w_raw, scale) in t["meas_vecs"]:
                table, col = parse_model_key(model_key)
                df = tables.get(table, None)
                if df is None:
                    raise RuntimeError(f"[{t['имя']}] Модель не вернула таблицу '{table}' (нужно для {model_key}).")
                if col not in df.columns:
                    raise RuntimeError(f"[{t['имя']}] В выходе модели ({table}) нет колонки '{col}'.")

                y_sim = np.asarray(df[col], dtype=float)
                # time for this sim table (если нет — fallback на main)
                if (time_col in df.columns) and (len(df) == len(y_sim)):
                    t_sim = np.asarray(df[time_col], dtype=float)
                else:
                    if len(y_sim) == len(t_sim_main):
                        t_sim = np.asarray(t_sim_main, dtype=float)
                    else:
                        t_sim = extract_time_vector(df, time_col, fallback=t_sim_main)

                if len(t_sim) != len(y_sim):
                    raise RuntimeError(
                        f"[{t['имя']}] Длины t_sim и y_sim не совпали для {table}.{col}: "
                        f"len(t_sim)={len(t_sim)}, len(y_sim)={len(y_sim)}."
                    )

                # ensure sorted
                t_sim, y_sim = ensure_sorted_by_time(np.asarray(t_sim, dtype=float), y_sim)

                # interp to this signal time
                y_sim_i = np.interp(np.asarray(t_meas, dtype=float), t_sim, y_sim)

                # extra safety: exclude points outside sim range
                if t_sim.size >= 2:
                    mask2 = mask & (t_meas >= float(t_sim[0])) & (t_meas <= float(t_sim[-1]))
                else:
                    mask2 = mask

                if not np.all(mask2):
                    y_sim_i = y_sim_i[mask2]
                    y_meas_i = y_meas[mask2]
                else:
                    y_meas_i = y_meas

                diff = (y_sim_i - y_meas_i)
                n_sig = int(diff.size)

                # unbiased residual (без group_gain): w_raw/scale
                w_unb = float(w_raw) / float(scale) if float(scale) != 0.0 else float(w_raw)
                r_unb = w_unb * diff
                sse_unb = float(np.dot(r_unb, r_unb))
                rmse_unb = float(math.sqrt(sse_unb / max(1, n_sig)))

                # effective residual (с учётом group_gain)
                r_sig = float(w) * diff
                sse_sig = float(np.dot(r_sig, r_sig))
                rmse_sig = float(math.sqrt(sse_sig / max(1, n_sig)))

                details["signals"].append({
                    "test": t["имя"],
                    "group": t.get("group", "train"),
                    "meas_table": str(meas_table),
                    "meas_col": str(meas_col),
                    "model_key": str(model_key),
                    "sig_group": str(sig_group),
                    "group_gain": float(group_gain),
                    "n": n_sig,
                    "sse": sse_sig,
                    "rmse": rmse_sig,
                    "sse_unb": sse_unb,
                    "rmse_unb": rmse_unb,
                    "w_unb": float(w_unb),
                    "w": float(w),
                    "w_raw": float(w_raw),
                    "scale": float(scale),
                })

                sse_test += sse_sig
                n_test += n_sig

            details["tests"].append({
                "test": t["имя"],
                "group": t.get("group", "train"),
                "n": int(n_test),
                "sse": float(sse_test),
                "rmse": float(math.sqrt(sse_test / max(1, n_test))),
            })

        _save_json(details, Path(args.details_json))


    progress.write({"stage": "done", "best_cost": float(best.cost), "best_rmse": report["best_rmse"]}, force=True)
    print("DONE. best_cost=", report["best_cost"], "best_rmse=", report["best_rmse"])


if __name__ == "__main__":
    main()