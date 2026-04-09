# -*- coding: utf-8 -*-
"""
profile_worker_v1_likelihood.py

Profile likelihood (профиль правдоподобия) для параметров матмодели по набору тестов (suite)
и осциллограммам из UI (NPZ).

Идея (как у Raue et al., 2009):
- берём оптимальные параметры θ* (обычно после fit_worker),
- для параметра φ строим сетку значений φ_j,
- на каждом φ_j фиксируем φ=φ_j и переоптимизируем остальные параметры,
- получаем профиль функции правдоподобия (или SSE) и оцениваем практическую
  идентифицируемость + доверительные интервалы.

Важно:
- Статистическая интерпретация (Δχ² пороги) корректнее при loss="linear"
  (классическое LS под гауссов шум).
- При робастных loss (soft_l1/huber/...) профиль всё равно полезен как
  "диагностика формы/плоскости", но доверительные интервалы становятся эвристикой.

Зависимости: numpy, pandas, scipy.

Пример:
  python profile_worker_v1_likelihood.py ^
    --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py ^
    --worker opt_worker_v3_margins_energy.py ^
    --suite_json default_suite.json ^
    --osc_dir osc_logs/RUN_... ^
    --theta_star_json fitted_base.json ^
    --fit_ranges_json fit_ranges.json ^
    --mapping_json mapping_npz_example_v2.json ^
    --profile_params "пружина_масштаб,дроссель_коэф_..." ^
    --out_json profile_report.json ^
    --out_dir profile_out ^
    --use_smoothing_defaults

"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.stats import chi2
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
    """Выбрать колонку времени в df_main (обычно: время_с)."""
    for c in ("время_с", "t", "time", "Time", "timestamp", "Timestamp"):
        if c in df_main.columns:
            return str(c)
    return str(df_main.columns[0])


def extract_time_vector(df: pd.DataFrame, time_col: str, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    """Достать вектор времени из таблицы; если нет time_col — пробуем первый столбец."""
    if time_col in df.columns:
        try:
            return np.asarray(df[time_col], dtype=float)
        except Exception:
            pass
    try:
        return np.asarray(df.iloc[:, 0], dtype=float)
    except Exception:
        if fallback is not None:
            return np.asarray(fallback, dtype=float)
        raise


def ensure_sorted_by_time(t: np.ndarray, *arrs: np.ndarray) -> Tuple[np.ndarray, ...]:
    """Если t не монотонен — сортируем t и все массивы одинаково."""
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
# tests / suite
# --------------------------
def load_suite(worker_mod, suite_obj: Any) -> List[Tuple[str, Dict[str, Any], float, float, Dict[str, Any]]]:
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

    return worker_mod.build_test_suite(cfg)


def load_osc_dir(osc_dir: Path) -> pd.DataFrame:
    idx_path = osc_dir / "tests_index.csv"
    if not idx_path.exists():
        raise FileNotFoundError(f"Не найден {idx_path}")
    df = pd.read_csv(idx_path, encoding="utf-8-sig")
    cols = {c: c.strip() for c in df.columns}
    df = df.rename(columns=cols)
    need = ["номер", "имя_теста", "dt_с", "t_end_с"]
    for c in need:
        if c not in df.columns:
            raise RuntimeError(f"В tests_index.csv нет колонки '{c}'. Есть: {list(df.columns)}")
    return df.sort_values("номер").reset_index(drop=True)


def build_objective(
    model_mod,
    theta_base: Dict[str, Any],
    fit_keys: List[str],
    fit_lo: np.ndarray,
    fit_hi: np.ndarray,
    tests_compiled: List[Dict[str, Any]],
    mapping_specs: List[Tuple[str, str, str, float, Optional[float], Optional[float]]],
    record_full: bool,
    record_stride: int,
    time_col: str,
    stop_file: Optional[Path],
):
    """Собрать функцию residuals(x_full) -> r (склейка по тестам/сигналам)."""
    # precompile meas vectors already done in tests_compiled

    def simulate(params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float):
        if record_full:
            return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=True, record_stride=record_stride)
        return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=False)

    def residuals_full(x_full: np.ndarray) -> np.ndarray:
        if stop_file is not None and stop_file.exists():
            raise StopRequested("STOP file detected")

        params = dict(theta_base)
        for k, v in zip(fit_keys, x_full):
            params[k] = float(v)

        parts: List[np.ndarray] = []
        for t in tests_compiled:
            out = simulate(params, t["test"], dt=float(t["dt"]), t_end=float(t["t_end"]))
            tables = tables_from_out(out, record_full=record_full)
            df_main = tables["main"]
            if df_main is None:
                raise RuntimeError(f"[{t['имя']}] Модель не вернула df_main")
            t_sim_main = extract_time_vector(df_main, time_col)

            for (meas_table, t_meas, y_meas, mask, w, model_key) in t["meas_vecs"]:
                table, col = parse_model_key(model_key)
                df = tables.get(table, None)
                if df is None:
                    raise RuntimeError(f"[{t['имя']}] Нужна таблица '{table}', но модель её не вернула.")
                if col not in df.columns:
                    raise RuntimeError(f"[{t['имя']}] В ({table}) нет колонки '{col}'")
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
                        f"len(t_sim)={len(t_sim)}, len(y_sim)={len(y_sim)}"
                    )

                t_sim, y_sim = ensure_sorted_by_time(np.asarray(t_sim, dtype=float), y_sim)

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

                parts.append(float(w) * (y_sim_i - y_meas_i))

        if not parts:
            return np.zeros(0, dtype=float)
        return np.concatenate(parts, axis=0)

    return residuals_full


def find_ci_from_profile(vals: np.ndarray, stat: np.ndarray, thr: float, x_star: float) -> Tuple[Optional[float], Optional[float]]:
    """
    vals: grid values (sorted ascending)
    stat: profile statistic (e.g., delta_chi2) same length
    thr: threshold
    returns (lo, hi) around x_star where stat<=thr (approx, by nearest points)
    """
    if len(vals) != len(stat) or len(vals) == 0:
        return None, None
    ok = stat <= thr
    if not np.any(ok):
        return None, None
    # choose connected region containing point closest to x_star
    i0 = int(np.argmin(np.abs(vals - x_star)))
    if not ok[i0]:
        # find nearest ok
        ok_idx = np.where(ok)[0]
        i0 = int(ok_idx[np.argmin(np.abs(ok_idx - i0))])
    # expand left/right while ok
    lo_i = i0
    hi_i = i0
    while lo_i - 1 >= 0 and ok[lo_i - 1]:
        lo_i -= 1
    while hi_i + 1 < len(ok) and ok[hi_i + 1]:
        hi_i += 1
    return float(vals[lo_i]), float(vals[hi_i])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--osc_dir", required=True)

    ap.add_argument("--theta_star_json", required=True, help="Оптимальные параметры θ* (обычно out_json из fit_worker)")
    ap.add_argument("--fit_ranges_json", required=True, help="Границы/список параметров, которые считаем 'свободными'")

    ap.add_argument("--mapping_json", required=True, help="mapping (meas_col/meas_table/model_key/weight)")
    ap.add_argument("--time_col", default="auto", help="Колонка времени: auto -> время_с / t / первый столбец")

    ap.add_argument("--profile_params", required=True, help="Список параметров через запятую (подмножество fit_ranges)")
    ap.add_argument("--span", type=float, default=0.35, help="Доля ширины диапазона [lo,hi] вокруг θ* для сетки профиля")
    ap.add_argument("--n_points", type=int, default=21, help="Число точек сетки профиля (рекомендуется 15..31)")

    ap.add_argument("--loss", default="linear", help="loss для least_squares при переоптимизации профиля (лучше linear)")
    ap.add_argument("--f_scale", type=float, default=1.0)
    ap.add_argument("--max_nfev", type=int, default=160)

    ap.add_argument("--record_stride", type=int, default=1)
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    ap.add_argument("--out_json", required=True, help="Отчёт JSON")
    ap.add_argument("--out_dir", default="", help="Папка для CSV (по параметрам)")
    ap.add_argument("--progress_json", default="")
    ap.add_argument("--progress_every_sec", type=float, default=1.0)
    ap.add_argument("--stop_file", default="")

    args = ap.parse_args()

    model_mod = load_python_module_from_path(Path(args.model), "model_mod_profile")
    worker_mod = load_python_module_from_path(Path(args.worker), "worker_mod_profile")

    suite_obj = _load_json(Path(args.suite_json))
    tests_suite = load_suite(worker_mod, suite_obj)
    tests_by_name = {name: (test, float(dt), float(t_end)) for name, test, dt, t_end, _targets in tests_suite}

    osc_dir = Path(args.osc_dir)
    df_idx = load_osc_dir(osc_dir)

    # build tests list by osc_dir order (as fit_worker)
    tests = []
    for _, row in df_idx.iterrows():
        name = str(row["имя_теста"])
        if name not in tests_by_name:
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
            "dt": dt_i,
            "t_end": t_end_i,
            "test": test,
            "meas": meas_tables,
        })
    if not tests:
        raise SystemExit("Нет сопоставленных тестов (suite_json vs tests_index.csv).")

    theta_star: Dict[str, Any] = _load_json(Path(args.theta_star_json))
    fit_ranges: Dict[str, Any] = _load_json(Path(args.fit_ranges_json))
    mapping: List[Dict[str, Any]] = _load_json(Path(args.mapping_json))

    # smoothing defaults (в theta_star, чтобы симуляция совпадала)
    if args.use_smoothing_defaults:
        theta_star.setdefault("smooth_dynamics", True)
        theta_star.setdefault("smooth_mechanics", True)
        theta_star.setdefault("smooth_pressure_floor", True)
        theta_star.setdefault("smooth_valves", True)
        theta_star.setdefault("k_smooth_valves", 80.0)

    fit_keys = list(fit_ranges.keys())
    fit_lo = np.array([float(fit_ranges[k][0]) for k in fit_keys], dtype=float)
    fit_hi = np.array([float(fit_ranges[k][1]) for k in fit_keys], dtype=float)
    if np.any(fit_hi <= fit_lo):
        bad = [k for k in fit_keys if not (float(fit_ranges[k][1]) > float(fit_ranges[k][0]))]
        raise SystemExit(f"Некорректные границы (hi<=lo) для: {bad}")

    # compile mapping specs (same format as fit)
    time_col = str(args.time_col)
    record_full = need_record_full(mapping)
    record_stride = max(1, int(args.record_stride))

    mapping_specs = []
    for m in mapping:
        meas_col = str(m.get("meas_col", "")).strip()
        model_key = str(m.get("model_key", "")).strip()
        meas_table = str(m.get("meas_table", "main")).strip()
        weight = float(m.get("weight", 1.0))
        t_min = m.get("t_min", None)
        t_max = m.get("t_max", None)
        t_min = float(t_min) if t_min is not None else None
        t_max = float(t_max) if t_max is not None else None
        if not meas_col or not model_key:
            raise SystemExit(f"Плохой mapping item: {m}")
        mapping_specs.append((meas_table, meas_col, model_key, weight, t_min, t_max))

    # resolve time_col (auto)
    time_col_arg = str(args.time_col).strip()
    if time_col_arg.lower() in ("auto", ""):
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

    # precompile measurement vectors per test
    # ВАЖНО: в UI (record_stride=N) таблицы p/q/open часто пишутся реже, чем main.
    # Поэтому для каждого сигнала берём СВОЙ t_meas из meas_table (если есть), иначе fallback на main.
    tests_compiled = []
    for t in tests:
        meas = t["meas"]
        if "main" not in meas or not isinstance(meas["main"], pd.DataFrame):
            raise RuntimeError(f"[{t['имя']}] В NPZ нет таблицы 'main'.")

        df_main = meas["main"]
        t_main = extract_time_vector(df_main, time_col)
        if t_main.size < 2:
            raise RuntimeError(f"[{t['имя']}] слишком мало точек времени в main.")

        meas_vecs = []
        for meas_table, meas_col, model_key, w, t_min, t_max in mapping_specs:
            if meas_table not in meas:
                raise RuntimeError(f"[{t['имя']}] В NPZ нет таблицы '{meas_table}'.")
            df_tbl = meas[meas_table]
            if meas_col not in df_tbl.columns:
                raise RuntimeError(f"[{t['имя']}] В NPZ({meas_table}) нет колонки '{meas_col}'.")

            y = np.asarray(df_tbl[meas_col], dtype=float)

            # time vector for this table
            if time_col in df_tbl.columns:
                t_vec = np.asarray(df_tbl[time_col], dtype=float)
            else:
                if len(y) == len(t_main):
                    t_vec = np.asarray(t_main, dtype=float)
                else:
                    t_vec = extract_time_vector(df_tbl, time_col, fallback=t_main)

            if len(t_vec) != len(y):
                raise RuntimeError(
                    f"[{t['имя']}] Длины t и y не совпали для {meas_table}.{meas_col}: len(t)={len(t_vec)}, len(y)={len(y)}"
                )

            t_vec, y = ensure_sorted_by_time(np.asarray(t_vec, dtype=float), y)

            mask = np.isfinite(y) & np.isfinite(t_vec)
            if t_min is not None:
                mask = mask & (t_vec >= float(t_min))
            if t_max is not None:
                mask = mask & (t_vec <= float(t_max))

            meas_vecs.append((meas_table, t_vec, y, mask, float(w), model_key))

        tests_compiled.append({
            "имя": t["имя"],
            "dt": float(t["dt"]),
            "t_end": float(t["t_end"]),
            "test": t["test"],
            "meas_vecs": meas_vecs,
        })
    stop_file = Path(args.stop_file) if args.stop_file else None
    progress = ProgressWriter(Path(args.progress_json) if args.progress_json else None, every_sec=float(args.progress_every_sec))

    # x* vector in fit_keys order
    x_star = np.array([float(theta_star.get(k, (fit_lo[i] + fit_hi[i]) * 0.5)) for i, k in enumerate(fit_keys)], dtype=float)
    # clamp into bounds (safety)
    x_star = np.minimum(np.maximum(x_star, fit_lo + 1e-12), fit_hi - 1e-12)

    residuals_full = build_objective(
        model_mod=model_mod,
        theta_base=theta_star,
        fit_keys=fit_keys,
        fit_lo=fit_lo,
        fit_hi=fit_hi,
        tests_compiled=tests_compiled,
        mapping_specs=mapping_specs,
        record_full=record_full,
        record_stride=record_stride,
        time_col=time_col,
        stop_file=stop_file,
    )

    # baseline SSE at x_star
    r0 = residuals_full(x_star)
    sse0 = float(np.dot(r0, r0))
    m = int(r0.size)
    p = int(len(fit_keys))
    dof = max(1, m - p)
    sigma2_hat = float(sse0 / dof) if dof > 0 else float("nan")

    # thresholds (LRT)
    thr95 = float(chi2.ppf(0.95, df=1))
    thr68 = float(chi2.ppf(0.6827, df=1))
    # convert to ΔSSE threshold under gaussian noise assumption:
    # -2ΔlogL = ΔSSE / sigma2
    delta_sse_95 = float(thr95 * sigma2_hat) if math.isfinite(sigma2_hat) else float("nan")
    delta_sse_68 = float(thr68 * sigma2_hat) if math.isfinite(sigma2_hat) else float("nan")

    prof_names = [s.strip() for s in str(args.profile_params).split(",") if s.strip()]
    if not prof_names:
        raise SystemExit("profile_params пустой")

    # indices
    key_to_idx = {k: i for i, k in enumerate(fit_keys)}
    unknown = [k for k in prof_names if k not in key_to_idx]
    if unknown:
        raise SystemExit(f"profile_params содержит параметры не из fit_ranges: {unknown}")

    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "method": "profile_likelihood_v1",
        "loss": str(args.loss),
        "f_scale": float(args.f_scale),
        "sse_star": float(sse0),
        "sigma2_hat": float(sigma2_hat),
        "dof": int(dof),
        "chi2_thr_95": float(thr95),
        "chi2_thr_68": float(thr68),
        "delta_sse_thr_95": float(delta_sse_95),
        "delta_sse_thr_68": float(delta_sse_68),
        "tests_used": [t["имя"] for t in tests_compiled],
        "profiles": {},
        "notes": [],
    }

    if str(args.loss).strip().lower() != "linear":
        report["notes"].append(
            "loss != linear: статистическая интерпретация CI по χ² становится эвристической. "
            "Используйте профили как диагностику формы/плоскости."
        )

    span = max(0.0, float(args.span))
    n_points = max(5, int(args.n_points))

    # main loop
    total_jobs = len(prof_names) * n_points
    done_jobs = 0

    for pname in prof_names:
        idx = key_to_idx[pname]
        x0 = float(x_star[idx])
        lo = float(fit_lo[idx])
        hi = float(fit_hi[idx])

        width = span * (hi - lo)
        g_lo = max(lo, x0 - width)
        g_hi = min(hi, x0 + width)
        if g_hi <= g_lo:
            g_lo = lo
            g_hi = hi

        grid = np.linspace(g_lo, g_hi, n_points, dtype=float)
        # ensure x0 included
        if np.min(np.abs(grid - x0)) > 1e-9 * max(1.0, abs(x0)):
            grid = np.unique(np.sort(np.concatenate([grid, np.array([x0])])))

        # warm-start order: from closest to x0 outwards
        order = np.argsort(np.abs(grid - x0))
        grid_ordered = grid[order]

        free_mask = np.ones(len(fit_keys), dtype=bool)
        free_mask[idx] = False
        free_keys = [k for k in fit_keys if k != pname]
        x_free_lo = fit_lo[free_mask]
        x_free_hi = fit_hi[free_mask]

        # initial guess for free vars from x_star
        x_free = x_star[free_mask].copy()

        prof_rows = []

        for v in grid_ordered:
            if stop_file is not None and stop_file.exists():
                raise SystemExit("Остановлено пользователем (STOP file).")

            v = float(v)

            def residuals_free(x_free_vec: np.ndarray) -> np.ndarray:
                x_full = x_star.copy()  # base from x_star; we override free and fixed
                x_full[idx] = v
                x_full[free_mask] = x_free_vec
                return residuals_full(x_full)

            t0 = time.time()
            res = least_squares(
                residuals_free,
                x_free,
                bounds=(x_free_lo, x_free_hi),
                method="trf",
                loss=str(args.loss),
                f_scale=float(args.f_scale),
                x_scale="jac",
                jac="2-point",
                max_nfev=int(args.max_nfev),
            )
            dt_run = time.time() - t0
            sse = float(np.dot(res.fun, res.fun))
            # update warm start
            x_free = res.x.copy()

            row = {
                "fixed_value": v,
                "success": bool(res.success),
                "status": int(res.status),
                "message": str(res.message),
                "cost": float(res.cost),
                "sse": float(sse),
                "nfev": int(res.nfev),
                "time_sec": float(dt_run),
            }
            prof_rows.append(row)

            done_jobs += 1
            progress.write({
                "stage": "profile",
                "param": pname,
                "done": int(done_jobs),
                "total": int(total_jobs),
                "last_fixed_value": v,
                "last_sse": float(sse),
            })

        # sort rows by fixed value
        prof_rows.sort(key=lambda r: float(r["fixed_value"]))
        vals = np.array([r["fixed_value"] for r in prof_rows], dtype=float)
        sses = np.array([r["sse"] for r in prof_rows], dtype=float)

        # compute delta chi2 statistic (approx)
        if math.isfinite(sigma2_hat) and sigma2_hat > 0:
            delta_chi2 = (sses - sse0) / sigma2_hat
        else:
            delta_chi2 = np.full_like(sses, np.nan)

        # CIs
        ci95 = find_ci_from_profile(vals, delta_chi2, thr95, x0) if np.all(np.isfinite(delta_chi2)) else (None, None)
        ci68 = find_ci_from_profile(vals, delta_chi2, thr68, x0) if np.all(np.isfinite(delta_chi2)) else (None, None)

        report["profiles"][pname] = {
            "theta_star": float(x0),
            "bounds": [float(lo), float(hi)],
            "grid_min": float(vals.min()),
            "grid_max": float(vals.max()),
            "ci_95": [ci95[0], ci95[1]],
            "ci_68": [ci68[0], ci68[1]],
            "rows": prof_rows,
        }

        # write CSV for plotting
        if out_dir is not None:
            df = pd.DataFrame({
                "fixed_value": vals,
                "sse": sses,
                "delta_sse": sses - sse0,
                "delta_chi2": delta_chi2,
            })
            safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in pname)
            df.to_csv(out_dir / f"profile_{safe}.csv", index=False, encoding="utf-8-sig")

    _save_json(report, Path(args.out_json))
    progress.write({"stage": "done", "out_json": str(Path(args.out_json).resolve())}, force=True)
    print("DONE. wrote", args.out_json)


if __name__ == "__main__":
    main()
