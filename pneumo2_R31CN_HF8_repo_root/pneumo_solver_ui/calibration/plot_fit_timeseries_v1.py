# -*- coding: utf-8 -*-
"""
plot_fit_timeseries_v1.py

Автоматическая генерация графиков "measured vs simulated" по результатам калибровки
по NPZ-логам UI.

Зачем:
- fit_worker пишет fit_details.json, где есть SSE/RMSE по тестам и сигналам, но НЕ
  сохраняет сами временные ряды.
- Для диагностики нужны графики: совпадает ли форма, нет ли смещений/ошибок единиц,
  не "обрезаются" ли сигналы по времени, etc.

Что делает:
- читает osc_dir (tests_index.csv + Txx_osc.npz),
- читает fitted_json (параметры),
- читает mapping_json (соответствие meas_table.meas_col -> model_key),
- (опционально) читает fit_details_json, чтобы выбрать top-K тестов и top-K сигналов,
- для выбранных тестов прогоняет модель,
- для выбранных сигналов строит графики y_meas(t) и y_sim(t), а также остаток r(t).

Выход:
- PNG файлы в out_dir/plots/
- plots_index.csv (метаданные: тест, сигнал, rmse, nrmse, путь к файлу)

Важно:
- Скрипт использует np.load(..., allow_pickle=True), так как NPZ, созданные вашим UI,
  могут содержать object-массивы. НЕ используйте на недоверенных NPZ.

Зависимости: numpy, pandas, matplotlib

Пример:
python calibration/plot_fit_timeseries_v1.py ^
  --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py ^
  --worker opt_worker_v3_margins_energy.py ^
  --suite_json default_suite.json ^
  --osc_dir osc_logs/RUN_... ^
  --fitted_json calibration_runs/RUN_.../fitted_base_final.json ^
  --mapping_json calibration_runs/RUN_.../mapping_final.json ^
  --fit_details_json calibration_runs/RUN_.../fit_details_final.json ^
  --out_dir calibration_runs/RUN_.../plots ^
  --top_tests 3 --top_signals 6 ^
  --use_smoothing_defaults

"""

from __future__ import annotations

import argparse
import json
import math
import re
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


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


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
    return {k: v for k, v in out.items() if isinstance(v, pd.DataFrame)}


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


def detect_time_col(df_main: pd.DataFrame) -> str:
    for c in ("время_с", "t", "time", "Time", "timestamp", "Timestamp"):
        if c in df_main.columns:
            return str(c)
    return str(df_main.columns[0])


def extract_time_vector(df: pd.DataFrame, time_col: str, fallback: Optional[np.ndarray] = None) -> np.ndarray:
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
    if t.size < 2:
        return (t,) + arrs
    if np.any(np.diff(t) < 0):
        order = np.argsort(t)
        out = [t[order]]
        for a in arrs:
            out.append(a[order])
        return tuple(out)
    return (t,) + arrs


def slugify(text: str, max_len: int = 96) -> str:
    """Сделать безопасный кусок имени файла (ASCII-only)."""
    t = str(text)
    t = t.strip().replace("\\", "_").replace("/", "_")
    # replace spaces
    t = re.sub(r"\s+", "_", t)
    # keep only safe chars
    t2 = re.sub(r"[^0-9A-Za-z_\-]+", "_", t)
    t2 = re.sub(r"_+", "_", t2).strip("_")
    if not t2:
        # fallback to hash
        import hashlib
        t2 = hashlib.sha1(t.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return t2[:max_len]


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
    df = pd.read_csv(idx_path, encoding="utf-8-sig")
    df = df.rename(columns={c: c.strip() for c in df.columns})
    need = ["номер", "имя_теста", "dt_с", "t_end_с"]
    for c in need:
        if c not in df.columns:
            raise RuntimeError(f"В tests_index.csv нет колонки '{c}'. Есть: {list(df.columns)}")
    return df.sort_values("номер").reset_index(drop=True)


def aggregate_top_from_details(details_json: Path, top_tests: int, top_signals: int) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    details = _load_json(details_json)
    df_t = pd.DataFrame(details.get("tests", []))
    df_s = pd.DataFrame(details.get("signals", []))

    test_names: List[str] = []
    if not df_t.empty and "test" in df_t.columns:
        df_t["sse"] = pd.to_numeric(df_t.get("sse", df_t.get("sse_sum", 0)), errors="coerce")
        g = df_t.groupby("test", as_index=False).agg(sse=("sse", "sum"), n=("n", "sum"), group=("group", "first"))
        g = g.sort_values("sse", ascending=False)
        test_names = [str(x) for x in g["test"].head(max(1, top_tests)).tolist()]

    sig_triples: List[Tuple[str, str, str]] = []
    if not df_s.empty and all(c in df_s.columns for c in ["meas_table", "meas_col", "model_key"]):
        df_s["sse"] = pd.to_numeric(df_s.get("sse", df_s.get("sse_sum", 0)), errors="coerce")
        g = df_s.groupby(["meas_table", "meas_col", "model_key"], as_index=False).agg(sse=("sse", "sum"), n=("n", "sum"))
        g = g.sort_values("sse", ascending=False)
        for _, r in g.head(max(1, top_signals)).iterrows():
            sig_triples.append((str(r["meas_table"]), str(r["meas_col"]), str(r["model_key"])))
    return test_names, sig_triples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--suite_json", required=True)

    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--fitted_json", required=True)
    ap.add_argument("--mapping_json", required=True)
    ap.add_argument("--fit_details_json", default="", help="Если задано — выбираем top_tests/top_signals по SSE")
    ap.add_argument("--time_col", default="auto")
    ap.add_argument("--record_stride", type=int, default=1)
    ap.add_argument("--use_smoothing_defaults", action="store_true")

    ap.add_argument("--top_tests", type=int, default=3)
    ap.add_argument("--top_signals", type=int, default=6)
    ap.add_argument("--include_holdout", action="store_true")

    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    try:
        import matplotlib.pyplot as plt  # noqa: F401
    except Exception as e:
        raise SystemExit("matplotlib не установлен. Установите: pip install matplotlib") from e

    import matplotlib.pyplot as plt

    project_root = Path(__file__).resolve().parents[1]
    model_mod = load_python_module_from_path(project_root / args.model, "model_mod_plot_fit")
    worker_mod = load_python_module_from_path(project_root / args.worker, "worker_mod_plot_fit")

    osc_dir = Path(args.osc_dir)
    suite_obj = _load_json(project_root / args.suite_json)
    suite_tests = load_suite(worker_mod, suite_obj)
    tests_by_name = {name: (test, float(dt), float(t_end)) for name, test, dt, t_end, _targets in suite_tests}

    df_idx = load_osc_index(osc_dir)

    fitted = _load_json(Path(args.fitted_json))
    mapping = _load_json(Path(args.mapping_json))
    record_full = need_record_full(mapping)
    record_stride = max(1, int(args.record_stride))

    # smoothing defaults
    if args.use_smoothing_defaults:
        fitted.setdefault("smooth_dynamics", True)
        fitted.setdefault("smooth_mechanics", True)
        fitted.setdefault("smooth_pressure_floor", True)
        fitted.setdefault("smooth_valves", True)
        fitted.setdefault("k_smooth_valves", 80.0)

    # select tests/signals
    selected_tests: Optional[List[str]] = None
    selected_sigs: Optional[List[Tuple[str, str, str]]] = None
    if args.fit_details_json:
        selected_tests, selected_sigs = aggregate_top_from_details(Path(args.fit_details_json), int(args.top_tests), int(args.top_signals))

    # fallback: all mapping entries (danger: too many)
    if not selected_sigs:
        selected_sigs = [(str(m.get("meas_table", "main")), str(m.get("meas_col", "")), str(m.get("model_key", ""))) for m in mapping]

    # convert selected_sigs to mapping items
    sel_map: List[Dict[str, Any]] = []
    for mt, mc, mk in selected_sigs:
        # find first matching mapping row
        found = None
        for m in mapping:
            if str(m.get("meas_table", "main")) == mt and str(m.get("meas_col", "")) == mc and str(m.get("model_key", "")) == mk:
                found = m
                break
        if found is None:
            found = {"meas_table": mt, "meas_col": mc, "model_key": mk, "weight": 1.0}
        sel_map.append(found)

    # time col
    time_col = str(args.time_col).strip()
    if time_col.lower() in ("auto", ""):
        # use first NPZ main
        first_npz = osc_dir / f"T{int(df_idx.iloc[0]['номер']):02d}_osc.npz"
        meas0 = load_meas_npz(first_npz)
        time_col = detect_time_col(meas0["main"])

    out_dir = Path(args.out_dir)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    def simulate(params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float):
        if record_full:
            return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=True, record_stride=record_stride)
        return model_mod.simulate(params, test, dt=dt, t_end=t_end, record_full=False)

    # loop through osc_dir in order
    for _, row in df_idx.iterrows():
        test_name = str(row["имя_теста"])
        group = str(row.get("группа", ""))  # might not exist
        if selected_tests and (test_name not in selected_tests):
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
        out = simulate(fitted, tests_by_name[test_name][0], dt=dt_i, t_end=t_end_i)
        tables_sim = tables_from_out(out, record_full=record_full)
        if tables_sim.get("main", None) is None:
            continue
        t_sim_main = extract_time_vector(tables_sim["main"], time_col)

        # for each selected signal
        for m in sel_map:
            meas_table = str(m.get("meas_table", "main"))
            meas_col = str(m.get("meas_col", ""))
            model_key = str(m.get("model_key", ""))
            w = float(m.get("weight", 1.0))
            t_min = m.get("t_min", None)
            t_max = m.get("t_max", None)
            t_min = float(t_min) if t_min is not None else None
            t_max = float(t_max) if t_max is not None else None
            time_shift_s = m.get("time_shift_s", m.get("dt_shift_s", 0.0))
            try:
                time_shift_s = float(time_shift_s)
            except Exception:
                time_shift_s = 0.0

            if meas_table not in meas_tables:
                continue
            df_meas = meas_tables[meas_table]
            if meas_col not in df_meas.columns:
                continue

            y_meas = np.asarray(df_meas[meas_col], dtype=float)
            # time vector for meas
            if time_col in df_meas.columns:
                t_meas = np.asarray(df_meas[time_col], dtype=float)
            else:
                # fallback: if lengths match main -> use main time
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
                mask &= (t_meas >= t_min)
            if t_max is not None:
                mask &= (t_meas <= t_max)

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

            # restrict to overlap
            if t_sim.size >= 2:
                mask &= (t_meas >= float(t_sim[0])) & (t_meas <= float(t_sim[-1]))
            if not np.any(mask):
                continue

            t_use = t_meas[mask]
            y_meas_use = y_meas[mask]
            # apply optional time shift (seconds): shift meas time axis
            if float(time_shift_s) != 0.0:
                t_use = t_use + float(time_shift_s)
            y_sim_use = np.interp(t_use, t_sim, y_sim)
            r = (y_sim_use - y_meas_use)
            sse = float(np.dot(w * r, w * r))
            rmse = float(math.sqrt(sse / max(1, r.size)))
            # rough scale for nrmse: MAD of weighted meas
            med = float(np.median(w * y_meas_use))
            mad = float(np.median(np.abs(w * y_meas_use - med)))
            scale = float(1.4826 * mad) if mad > 0 else float(np.std(w * y_meas_use))
            if not np.isfinite(scale) or scale <= 1e-12:
                scale = 1.0
            nrmse = float(rmse / scale)

            test_slug = slugify(test_name)
            sig_slug = slugify(f"{meas_table}.{meas_col}__{model_key}")
            out_png = plots_dir / f"{test_slug}__{sig_slug}.png"

            # plot
            plt.figure()
            plt.plot(t_use, y_meas_use, label="meas")
            plt.plot(t_use, y_sim_use, label="sim")
            plt.legend()
            plt.xlabel("t, s")
            plt.title(f"{test_name} | {meas_table}.{meas_col} -> {model_key}")
            plt.tight_layout()
            plt.savefig(out_png, dpi=140)
            plt.close()

            # residual plot
            out_png_r = plots_dir / f"{test_slug}__{sig_slug}__resid.png"
            plt.figure()
            plt.plot(t_use, w * r, label="w*(sim-meas)")
            plt.axhline(0.0, linewidth=1)
            plt.legend()
            plt.xlabel("t, s")
            plt.title(f"Residual | {test_name} | {model_key}")
            plt.tight_layout()
            plt.savefig(out_png_r, dpi=140)
            plt.close()

            rows.append({
                "test": test_name,
                "meas_table": meas_table,
                "meas_col": meas_col,
                "model_key": model_key,
                "n": int(r.size),
                "sse": sse,
                "rmse": rmse,
                "nrmse": nrmse,
                "plot_png": str(out_png.relative_to(out_dir)),
                "time_shift_s": float(time_shift_s),
                "resid_png": str(out_png_r.relative_to(out_dir)),
                "time_shift_s": float(time_shift_s),
            })

    df_out = pd.DataFrame(rows)
    out_csv = out_dir / "plots_index.csv"
    df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("Wrote plots:", plots_dir)
    print("Wrote index:", out_csv)


if __name__ == "__main__":
    main()
