# -*- coding: utf-8 -*-
"""
npz_inspect_v1.py

Утилита для осциллограмм формата NPZ (которые пишет UI в osc_dir).

Что делает:
- печатает, какие таблицы есть в Txx_osc.npz и какие в них колонки,
- показывает колонку времени (auto детект), диапазон времени, примерный dt,
- (опционально) пишет "минимальный" mapping JSON по нескольким базовым сигналам.

Примеры:
  python npz_inspect_v1.py --osc_dir osc_logs/RUN_2026_01_10_120000 --test_num 1
  python npz_inspect_v1.py --npz osc_logs/RUN_.../T01_osc.npz
  python npz_inspect_v1.py --npz ... --out_mapping mapping_suggest.json

"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


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


def detect_time_col(df_main: pd.DataFrame) -> str:
    for c in ("время_с", "t", "time", "Time", "timestamp", "Timestamp"):
        if c in df_main.columns:
            return str(c)
    return str(df_main.columns[0])


def extract_time_vector(df: pd.DataFrame, time_col: str) -> np.ndarray:
    if time_col in df.columns:
        return np.asarray(df[time_col], dtype=float)
    return np.asarray(df.iloc[:, 0], dtype=float)


def summarize_table(name: str, df: pd.DataFrame, time_col: str):
    cols = list(df.columns)
    n = len(df)
    print(f"\n[{name}] rows={n}, cols={len(cols)}")
    if n == 0:
        return

    t = None
    try:
        t = extract_time_vector(df, time_col)
    except Exception:
        t = None

    if t is not None and t.size >= 2 and np.all(np.isfinite(t)):
        t0, t1 = float(t[0]), float(t[-1])
        dt_med = float(np.median(np.diff(t))) if t.size >= 3 else float(t1 - t0)
        print(f"  time_col='{time_col}', t0={t0:.6g}, t1={t1:.6g}, dt~{dt_med:.6g}")
    else:
        print(f"  time_col='{time_col}' (не удалось извлечь/проверить t)")

    # print columns (trim)
    if len(cols) <= 60:
        print("  columns:")
        for c in cols:
            print(f"    - {c}")
    else:
        print("  columns (first 40):")
        for c in cols[:40]:
            print(f"    - {c}")
        print(f"  ... +{len(cols)-40} more")


def build_suggested_mapping(df_main: pd.DataFrame) -> list[dict[str, Any]]:
    # минимальный набор, чтобы начать калибровку (можно расширять)
    suggest = [
        "давление_ресивер1_Па",
        "давление_ресивер2_Па",
        "давление_ресивер3_Па",
        "давление_аккумулятор_Па",
        "крен_phi_рад",
        "тангаж_theta_рад",
    ]

    mapping: list[dict[str, Any]] = []
    for col in suggest:
        if col not in df_main.columns:
            continue
        if "давление" in col:
            w = 1e-5  # Па -> бар
        else:
            w = 1.0
        mapping.append({
            "meas_table": "main",
            "meas_col": col,
            "model_key": f"main:{col}",
            "weight": float(w),
        })
    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="", help="Путь к Txx_osc.npz")
    ap.add_argument("--osc_dir", default="", help="Папка osc_logs/RUN_... (с tests_index.csv)")
    ap.add_argument("--test_num", type=int, default=1, help="номер теста (как в имени Txx_osc.npz)")
    ap.add_argument("--time_col", default="auto", help="Колонка времени: auto -> время_с / t / первый столбец")
    ap.add_argument("--out_mapping", default="", help="Если задано — записать предложенный mapping JSON")
    args = ap.parse_args()

    if args.npz:
        npz_path = Path(args.npz)
    else:
        if not args.osc_dir:
            raise SystemExit("Нужно указать --npz или --osc_dir")
        osc_dir = Path(args.osc_dir)
        npz_path = osc_dir / f"T{int(args.test_num):02d}_osc.npz"

    if not npz_path.exists():
        raise SystemExit(f"Не найден файл: {npz_path}")

    meas = load_meas_npz(npz_path)
    if "main" not in meas:
        raise SystemExit("В NPZ нет таблицы 'main' — не могу определить время")

    time_col = str(args.time_col).strip()
    if time_col.lower() in ("auto", ""):
        time_col = detect_time_col(meas["main"])

    print(f"NPZ: {npz_path}")
    print(f"Detected time_col: {time_col}")

    for k in ("main", "p", "q", "open", "Eedges", "Egroups", "atm"):
        if k in meas:
            summarize_table(k, meas[k], time_col=time_col)

    if args.out_mapping:
        mapping = build_suggested_mapping(meas["main"])
        out_path = Path(args.out_mapping)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote suggested mapping: {out_path} (items={len(mapping)})")


if __name__ == "__main__":
    main()
