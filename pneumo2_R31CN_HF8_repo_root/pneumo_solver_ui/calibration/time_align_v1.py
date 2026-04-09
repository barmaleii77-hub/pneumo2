# -*- coding: utf-8 -*-
"""
time_align_v1.py

Оценка постоянного временного сдвига (time_shift_s) между измерениями (NPZ из UI) и
выходами модели для каждого сигнала / группы / глобально.

Зачем:
- В реальных логах часто есть лаги: фильтрация датчиков, логгер, задержка клапанов, etc.
- При калибровке без учёта time-shift модель может "портить" параметры, пытаясь
  компенсировать задержку динамикой.
- Быстрая оценка constant-delay позволяет улучшить совпадение формы и устойчивость fit.

Идея:
- Для каждого теста и сигнала ищем shift (секунды), который минимизирует SSE между
  y_meas(t) и y_sim(t + shift).
- Затем агрегируем shifts по тестам (median) и (опционально) по группам.

Выход:
- time_shifts.json / time_shifts.csv — оценённые сдвиги
- mapping_time_aligned.json — копия mapping.json, где у каждого элемента добавлен time_shift_s

Примечание про знак:
- shift оценивается как аргумент в y_sim(t + shift) ≈ y_meas(t).
- Этот же shift записывается в mapping.time_shift_s и далее применяется в fit_worker
  как сдвиг оси времени измерений: t_meas_aligned = t_meas + time_shift_s.

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


# ---------------- utils ----------------

def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _save_json(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


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


def detect_time_col(df_main: pd.DataFrame) -> str:
    for c in ("время_с", "t", "time", "Time", "timestamp", "Timestamp"):
        if c in df_main.columns:
            return str(c)
    return str(df_main.columns[0])


def ensure_sorted_by_time(t: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if t.size <= 1:
        return t, y
    if np.all(np.diff(t) >= 0):
        return t, y
    idx = np.argsort(t)
    return t[idx], y[idx]


def extract_time_vector(df: pd.DataFrame, time_col: str, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    if time_col in df.columns:
        v = np.asarray(df[time_col], dtype=float)
        if v.size >= 1:
            return v
    # fallback: first column
    try:
        v = np.asarray(df.iloc[:, 0], dtype=float)
        if v.size >= 1:
            return v
    except Exception:
        pass
    if fallback is not None:
        return np.asarray(fallback, dtype=float)
    raise RuntimeError(f"Cannot extract time vector: time_col='{time_col}', cols={list(df.columns)}")


def _npz_to_df(cols_key: str, values_key: str, z: np.lib.npyio.NpzFile) -> Optional[pd.DataFrame]:
    if cols_key not in z or values_key not in z:
        return None
    cols = z[cols_key].tolist()
    vals = z[values_key]
    return pd.DataFrame(vals, columns=cols)


def load_meas_npz(path: Path) -> Dict[str, pd.DataFrame]:
    z = np.load(path, allow_pickle=True)
    out: Dict[str, Optional[pd.DataFrame]] = {
        "main": _npz_to_df("main_cols", "main_values", z),
        "p": _npz_to_df("p_cols", "p_values", z),
        "q": _npz_to_df("q_cols", "q_values", z),
        "open": _npz_to_df("open_cols", "open_values", z),
        "Eedges": _npz_to_df("Eedges_cols", "Eedges_values", z),
        "Egroups": _npz_to_df("Egroups_cols", "Egroups_values", z),
        "atm": _npz_to_df("atm_cols", "atm_values", z),
    }
    return {k: v for k, v in out.items() if isinstance(v, pd.DataFrame)}


def tables_from_out(out: Any, record_full: bool) -> Dict[str, Optional[pd.DataFrame]]:
    # Compatible with project model.simulate return convention used in fit_worker/plot_fit_timeseries
    if not isinstance(out, (tuple, list)) or len(out) < 1:
        raise RuntimeError("model.simulate() returned unexpected object (expected tuple/list).")
    df_main = out[0]
    df_atm = out[7] if (record_full and len(out) > 7) else None
    df_p = out[8] if (record_full and len(out) > 8) else None
    df_q = out[9] if (record_full and len(out) > 9) else None
    df_open = out[10] if (record_full and len(out) > 10) else None
    df_Eedges = out[5] if (record_full and len(out) > 5) else None
    df_Egroups = out[6] if (record_full and len(out) > 6) else None
    return {
        "main": df_main,
        "p": df_p,
        "q": df_q,
        "open": df_open,
        "Eedges": df_Eedges,
        "Egroups": df_Egroups,
        "atm": df_atm,
    }


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


def load_osc_index(osc_dir: Path) -> pd.DataFrame:
    idx_path = osc_dir / "tests_index.csv"
    if not idx_path.exists():
        raise FileNotFoundError(f"Не найден {idx_path}. Ожидается папка из UI save_oscillograms_bundle(...).")
    df = pd.read_csv(idx_path, encoding="utf-8-sig")
    df = df.rename(columns={c: c.strip() for c in df.columns})
    need = ["номер", "имя_теста", "dt_с", "t_end_с"]
    for c in need:
        if c not in df.columns:
            raise RuntimeError(f"В tests_index.csv нет колонки '{c}'. Есть: {list(df.columns)}")
    return df.sort_values("номер").reset_index(drop=True)


def robust_center_scale(y: np.ndarray) -> Tuple[float, float]:
    y = np.asarray(y, dtype=float)
    if y.size < 2:
        return 0.0, 1.0
    med = float(np.median(y))
    mad = float(np.median(np.abs(y - med)))
    scale = float(1.4826 * mad) if mad > 0 else float(np.std(y))
    if (not np.isfinite(scale)) or scale <= 1e-12:
        scale = 1.0
    return med, scale


def estimate_shift_sse(
    t_meas: np.ndarray,
    y_meas: np.ndarray,
    t_sim: np.ndarray,
    y_sim: np.ndarray,
    *,
    max_shift_s: float,
    step_s: float,
    min_points: int,
    improve_min_rel: float,
    weight: float = 1.0,
    normalize: bool = True,
) -> Tuple[float, Dict[str, Any]]:
    """
    Solve: minimize SSE(shift) = Σ (w*( y_sim(t_meas + shift) - y_meas(t_meas) ))^2
    Returns best shift and meta.
    """
    t_meas = np.asarray(t_meas, dtype=float)
    y_meas = np.asarray(y_meas, dtype=float)
    t_sim = np.asarray(t_sim, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)

    if t_meas.size < min_points or t_sim.size < 2:
        return 0.0, {"ok": False, "reason": "too_few_points"}

    # Normalization for shape-based alignment
    if normalize:
        m0, s0 = robust_center_scale(y_meas)
        y_meas_n = (y_meas - m0) / s0
        m1, s1 = robust_center_scale(y_sim)
        y_sim_n = (y_sim - m1) / s1
    else:
        y_meas_n = y_meas
        y_sim_n = y_sim

    if step_s <= 0:
        # fallback: infer from meas median dt
        dts = np.diff(t_meas)
        dts = dts[np.isfinite(dts) & (dts > 0)]
        step_s = float(np.median(dts)) if dts.size else 1e-3

    max_shift_s = float(abs(max_shift_s))
    n = int(math.floor(max_shift_s / step_s))
    shifts = np.arange(-n, n + 1, dtype=float) * float(step_s)

    # baseline (shift=0)
    def _sse_for_shift(shift: float) -> Tuple[float, int]:
        t_eval = t_meas + float(shift)
        mask = np.isfinite(t_eval) & np.isfinite(y_meas_n)
        mask &= (t_eval >= float(t_sim[0])) & (t_eval <= float(t_sim[-1]))
        if mask.sum() < min_points:
            return float("inf"), int(mask.sum())
        y_sim_eval = np.interp(t_eval[mask], t_sim, y_sim_n)
        r = (y_sim_eval - y_meas_n[mask])
        w = float(weight)
        sse = float(np.dot(w * r, w * r))
        return sse, int(mask.sum())

    sse0, n0 = _sse_for_shift(0.0)

    best_shift = 0.0
    best_sse = sse0
    best_n = n0

    for sh in shifts:
        sse, nn = _sse_for_shift(float(sh))
        if sse < best_sse:
            best_sse = sse
            best_shift = float(sh)
            best_n = int(nn)

    ok = bool(np.isfinite(best_sse)) and best_n >= min_points

    improve_rel = 0.0
    if np.isfinite(sse0) and sse0 > 0 and np.isfinite(best_sse):
        improve_rel = float((sse0 - best_sse) / max(1e-12, sse0))

    # accept only if improvement is meaningful
    if ok and (improve_rel < float(improve_min_rel)):
        best_shift = 0.0
        best_sse = sse0
        best_n = n0
        ok = bool(np.isfinite(best_sse)) and best_n >= min_points

    meta = {
        "ok": ok,
        "best_shift_s": float(best_shift),
        "best_sse": float(best_sse) if np.isfinite(best_sse) else None,
        "sse0": float(sse0) if np.isfinite(sse0) else None,
        "n_used": int(best_n),
        "n0": int(n0),
        "step_s": float(step_s),
        "max_shift_s": float(max_shift_s),
        "improve_rel": float(improve_rel),
        "normalize": bool(normalize),
    }
    return float(best_shift), meta


def slug_key(m: Dict[str, Any]) -> str:
    meas_table = str(m.get("meas_table", "main"))
    meas_col = str(m.get("meas_col", ""))
    model_key = str(m.get("model_key", ""))
    return f"{meas_table}.{meas_col}__{model_key}"


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--suite_json", required=True)
    ap.add_argument("--base_json", required=True, help="Параметры для симуляции (обычно fitted_base_*.json)")
    ap.add_argument("--mapping_json", required=True)
    ap.add_argument("--out_dir", required=True)

    ap.add_argument("--time_col", default="auto", help="auto -> время_с / t / первый столбец")
    ap.add_argument("--record_stride", type=int, default=1)

    ap.add_argument("--only_tests", default="", help="Опционально: имена тестов через запятую")
    ap.add_argument("--use_groups", default="train", choices=["train", "all", "holdout"], help="Какие тесты брать для оценки shift")
    ap.add_argument("--holdout_tests", default="", help="Опционально: список holdout тестов (как в fit_worker)")

    ap.add_argument("--mode", default="per_group", choices=["per_signal", "per_group", "global"])
    ap.add_argument("--max_shift_s", type=float, default=0.25)
    ap.add_argument("--step_s", type=float, default=0.0, help="0 -> auto from meas dt")
    ap.add_argument("--min_points", type=int, default=25)
    ap.add_argument("--improve_min_rel", type=float, default=0.01)
    ap.add_argument("--normalize", action="store_true", help="Нормировать сигналы (robust) перед поиском shift")

    ap.add_argument("--max_signals", type=int, default=0, help="Ограничить кол-во сигналов (0=все)")
    ap.add_argument("--meas_stride", type=int, default=1, help="Прореживание измерений при оценке shift")

    args = ap.parse_args()

    osc_dir = Path(args.osc_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    project_root = Path(__file__).resolve().parents[1]

    model_mod = load_python_module_from_path(Path(args.model), "model_mod_time_align")
    worker_mod = load_python_module_from_path(Path(args.worker), "worker_mod_time_align")

    suite_obj = _load_json(Path(args.suite_json) if Path(args.suite_json).is_absolute() else (project_root / args.suite_json))
    suite_tests = load_suite(worker_mod, suite_obj)
    tests_by_name = {name: (test, float(dt), float(t_end)) for name, test, dt, t_end, _targets in suite_tests}

    mapping = _load_json(Path(args.mapping_json))
    if not isinstance(mapping, list):
        raise SystemExit("mapping_json должен быть списком")

    if int(args.max_signals) > 0:
        mapping = mapping[: int(args.max_signals)]

    record_full = need_record_full(mapping)
    record_stride = max(1, int(args.record_stride))
    meas_stride = max(1, int(args.meas_stride))

    # detect time_col from first NPZ main table (if auto)
    df_idx = load_osc_index(osc_dir)
    if df_idx.empty:
        raise SystemExit("tests_index.csv пуст")

    first_npz = osc_dir / f"T{int(df_idx.iloc[0]['номер']):02d}_osc.npz"
    if not first_npz.exists():
        raise SystemExit(f"Первый NPZ не найден: {first_npz}")
    meas0 = load_meas_npz(first_npz)
    if "main" not in meas0:
        raise SystemExit("В NPZ нет main")
    time_col = str(args.time_col)
    if time_col == "auto":
        time_col = detect_time_col(meas0["main"])

    fitted = _load_json(Path(args.base_json))

    # holdout selection
    holdout_set = set()
    if str(args.holdout_tests).strip():
        holdout_set = {s.strip() for s in str(args.holdout_tests).split(",") if s.strip()}

    only_tests = []
    if str(args.only_tests).strip():
        only_tests = [s.strip() for s in str(args.only_tests).split(",") if s.strip()]

    rows: List[Dict[str, Any]] = []

    def simulate(params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float):
        if record_full:
            return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=True, record_stride=record_stride)
        return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=False)

    t0 = time.time()

    # compute per-test per-signal shift
    for _, row in df_idx.iterrows():
        test_name = str(row["имя_теста"])
        if only_tests and (test_name not in only_tests):
            continue
        is_holdout = test_name in holdout_set
        if args.use_groups == "train" and is_holdout:
            continue
        if args.use_groups == "holdout" and (not is_holdout):
            continue
        if test_name not in tests_by_name:
            continue

        dt_i = float(row["dt_с"])
        t_end_i = float(row["t_end_с"])
        idx_i = int(row["номер"])

        npz_path = osc_dir / f"T{idx_i:02d}_osc.npz"
        if not npz_path.exists():
            continue
        meas_tables = load_meas_npz(npz_path)
        if "main" not in meas_tables:
            continue

        # simulate
        out = simulate(fitted, tests_by_name[test_name][0], dt=dt_i, t_end=t_end_i)
        tables_sim = tables_from_out(out, record_full=record_full)
        if tables_sim.get("main", None) is None:
            continue
        t_sim_main = extract_time_vector(tables_sim["main"], time_col)

        for m in mapping:
            meas_table = str(m.get("meas_table", "main"))
            meas_col = str(m.get("meas_col", "")).strip()
            model_key = str(m.get("model_key", "")).strip()
            sig_group = str(m.get("sig_group", m.get("group", "default"))).strip() or "default"
            w = float(m.get("weight", 1.0))
            t_min = m.get("t_min", None)
            t_max = m.get("t_max", None)
            t_min = float(t_min) if t_min is not None else None
            t_max = float(t_max) if t_max is not None else None

            if (not meas_col) or (not model_key):
                continue
            if meas_table not in meas_tables:
                continue
            df_meas = meas_tables[meas_table]
            if meas_col not in df_meas.columns:
                continue
            y_meas = np.asarray(df_meas[meas_col], dtype=float)

            # meas time
            if time_col in df_meas.columns:
                t_meas = np.asarray(df_meas[time_col], dtype=float)
            else:
                # fallback: main time if length matches
                df_main = meas_tables["main"]
                t_main = extract_time_vector(df_main, time_col)
                if len(t_main) == len(y_meas):
                    t_meas = np.asarray(t_main, dtype=float)
                else:
                    t_meas = extract_time_vector(df_meas, time_col, fallback=t_main)

            if len(t_meas) != len(y_meas):
                continue
            t_meas, y_meas = ensure_sorted_by_time(np.asarray(t_meas, dtype=float), y_meas)

            mask = np.isfinite(t_meas) & np.isfinite(y_meas)
            if t_min is not None:
                mask &= (t_meas >= float(t_min))
            if t_max is not None:
                mask &= (t_meas <= float(t_max))
            if not np.any(mask):
                continue

            # sim signal
            sim_table, sim_col = parse_model_key(model_key)
            df_sim = tables_sim.get(sim_table, None)
            if df_sim is None or sim_col not in df_sim.columns:
                continue
            y_sim = np.asarray(df_sim[sim_col], dtype=float)
            if time_col in df_sim.columns and len(df_sim) == len(y_sim):
                t_sim = np.asarray(df_sim[time_col], dtype=float)
            else:
                if len(y_sim) == len(t_sim_main):
                    t_sim = np.asarray(t_sim_main, dtype=float)
                else:
                    t_sim = extract_time_vector(df_sim, time_col, fallback=t_sim_main)
            if len(t_sim) != len(y_sim):
                continue
            t_sim, y_sim = ensure_sorted_by_time(np.asarray(t_sim, dtype=float), y_sim)

            t_use = np.asarray(t_meas[mask], dtype=float)
            y_use = np.asarray(y_meas[mask], dtype=float)
            if meas_stride > 1 and t_use.size > 2:
                t_use = t_use[::meas_stride]
                y_use = y_use[::meas_stride]

            shift, meta = estimate_shift_sse(
                t_use, y_use, t_sim, y_sim,
                max_shift_s=float(args.max_shift_s),
                step_s=float(args.step_s),
                min_points=int(args.min_points),
                improve_min_rel=float(args.improve_min_rel),
                weight=float(w),
                normalize=bool(args.normalize),
            )

            rows.append({
                "test": test_name,
                "is_holdout": bool(is_holdout),
                "sig_group": sig_group,
                "signal_key": slug_key(m),
                "meas_table": meas_table,
                "meas_col": meas_col,
                "model_key": model_key,
                "weight": float(w),
                "shift_s": float(shift),
                "ok": bool(meta.get("ok", False)),
                "n_used": int(meta.get("n_used", 0) or 0),
                "improve_rel": float(meta.get("improve_rel", 0.0) or 0.0),
            })

    df = pd.DataFrame(rows)
    out_csv = out_dir / "time_shifts_raw.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    # Aggregate
    shift_map: Dict[str, float] = {}
    if df.empty:
        print("No shifts computed (empty). Writing mapping unchanged.")
        shift_map = {}
    else:
        df_ok = df[df["ok"] == True].copy()
        if df_ok.empty:
            df_ok = df.copy()

        mode = str(args.mode)
        if mode == "per_signal":
            g = df_ok.groupby("signal_key", as_index=False)["shift_s"].median()
            shift_map = {str(r["signal_key"]): float(r["shift_s"]) for _, r in g.iterrows()}
        elif mode == "per_group":
            g = df_ok.groupby("sig_group", as_index=False)["shift_s"].median()
            shift_map = {str(r["sig_group"]): float(r["shift_s"]) for _, r in g.iterrows()}
        else:
            shift_map = {"global": float(df_ok["shift_s"].median())}

    _save_json(out_dir / "time_shifts.json", shift_map)

    # Build aligned mapping
    mapping_aligned: List[Dict[str, Any]] = []
    for m in mapping:
        mm = dict(m)
        key = slug_key(m)
        grp = str(m.get("sig_group", m.get("group", "default"))).strip() or "default"
        base_shift = float(mm.get("time_shift_s", mm.get("dt_shift_s", 0.0)) or 0.0)
        add_shift = 0.0
        if shift_map:
            if args.mode == "per_signal":
                add_shift = float(shift_map.get(key, 0.0))
            elif args.mode == "per_group":
                add_shift = float(shift_map.get(grp, 0.0))
            else:
                add_shift = float(shift_map.get("global", 0.0))
        mm["time_shift_s"] = float(base_shift + add_shift)
        mapping_aligned.append(mm)

    _save_json(out_dir / "mapping_time_aligned.json", mapping_aligned)

    # human-friendly summary
    summ_rows = []
    if shift_map:
        for k,v in shift_map.items():
            summ_rows.append({"key": k, "shift_s": float(v)})
    pd.DataFrame(summ_rows).to_csv(out_dir / "time_shifts.csv", index=False, encoding="utf-8-sig")

    # report md
    md = []
    md.append("# Time alignment report (time_align_v1)\n")
    md.append(f"- osc_dir: `{osc_dir}`\n")
    md.append(f"- base_json: `{args.base_json}`\n")
    md.append(f"- mapping_json: `{args.mapping_json}`\n")
    md.append(f"- mode: `{args.mode}`\n")
    md.append(f"- max_shift_s: `{args.max_shift_s}`\n")
    md.append(f"- step_s: `{args.step_s}` (0->auto)\n")
    md.append(f"- min_points: `{args.min_points}`\n")
    md.append(f"- improve_min_rel: `{args.improve_min_rel}`\n")
    md.append(f"- normalize: `{bool(args.normalize)}`\n")
    md.append("\n## Shift map\n")
    if shift_map:
        for k,v in shift_map.items():
            md.append(f"- **{k}**: {float(v):+.6f} s\n")
    else:
        md.append("_empty_\n")
    md.append("\n## Raw samples\n")
    md.append(f"- raw csv: `{out_csv.name}`\n")
    md.append(f"- n_rows: {int(len(df))}\n")
    md.append(f"\nElapsed: {time.time()-t0:.1f} s\n")
    (out_dir / "TIME_ALIGN_REPORT.md").write_text("".join(md), encoding="utf-8")

    print("Wrote:", out_dir)


if __name__ == "__main__":
    main()
