# -*- coding: utf-8 -*-
"""signals_csv_to_mapping_v1.py

Преобразование `signals.csv` (который генерит report_from_details_v1.py)
в `mapping.json` для fit_worker_v3_suite_identify.py.

Зачем:
Пайплайн "калибровать по NPZ" должен работать автоматически, а список сигналов/весов
задаваться через `signals.csv` (без ручного JSON).

Вход:
  signals.csv — таблица, которую пишет report_from_details_v1.py.
  Ожидаемые колонки:
    - meas_table, meas_col, model_key
    - w_raw (желательно) или weight / w
  Дополнительно могут быть:
    - enabled / use (0/1, true/false) — если есть, то берём только enabled==1
    - sse — если есть, можно выбрать топ-N сигналов
    - sig_group / signal_group — если есть, переносим в mapping (для multi-objective trade-off)

Выход:
  mapping.json — список объектов:
    {
      "meas_table": "main",
      "meas_col": "...",
      "model_key": "main:...",
      "sig_group": "pressure",
      "weight": 1.0
    }

Примечание:
  В `signals.csv` есть колонка `group` (train/holdout) — НЕ путать с `sig_group`
  (группа сигнала для multiobjective).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _to_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in ("1", "true", "yes", "y", "да", "on"):
        return True
    if s in ("0", "false", "no", "n", "нет", "off"):
        return False
    return None


def _load_signals_csv(path: Path) -> pd.DataFrame:
    # signals.csv в проекте пишется с utf-8-sig
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = set(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return None


def build_mapping_from_signals_csv(
    df: pd.DataFrame,
    *,
    top_n: int = 0,
    require_present_cols: bool = True,
) -> List[Dict[str, Any]]:
    """Собрать mapping из signals.csv.

    Возвращает уникальные тройки (meas_table, meas_col, model_key)
    с весом weight (=median(w_raw) или weight).
    """
    # required columns
    c_meas_table = _pick_col(df, ["meas_table", "table", "meas_tbl"])
    c_meas_col = _pick_col(df, ["meas_col", "col", "meas_column"])
    c_model_key = _pick_col(df, ["model_key", "key", "sim_key"])
    if require_present_cols and (c_meas_table is None or c_meas_col is None or c_model_key is None):
        raise SystemExit(
            "signals.csv должен содержать колонки meas_table, meas_col, model_key. "
            f"Есть: {list(df.columns)}"
        )

    # optional columns
    c_w_raw = _pick_col(df, ["w_raw", "weight", "w"])
    c_enabled = _pick_col(df, ["enabled", "use", "enabled_flag"])
    c_sse = _pick_col(df, ["sse", "SSE", "sum_sse"])
    c_sig_group = _pick_col(df, ["sig_group", "signal_group"])

    df2 = df.copy()

    # enabled filtering
    if c_enabled is not None:
        keep = []
        for v in df2[c_enabled].tolist():
            b = _to_bool(v)
            keep.append(True if (b is None) else bool(b))
        df2 = df2.loc[keep].copy()

    # keep only relevant columns
    cols = [c_meas_table, c_meas_col, c_model_key]
    if c_sig_group:
        cols.append(c_sig_group)
    if c_w_raw:
        cols.append(c_w_raw)
    if c_sse:
        cols.append(c_sse)
    df2 = df2[cols].copy()

    # rename
    rename_map = {c_meas_table: "meas_table", c_meas_col: "meas_col", c_model_key: "model_key"}
    if c_sig_group:
        rename_map[c_sig_group] = "sig_group"
    if c_w_raw:
        rename_map[c_w_raw] = "w_raw"
    if c_sse:
        rename_map[c_sse] = "sse"
    df2.rename(columns=rename_map, inplace=True)

    # defaults
    if "sig_group" not in df2.columns:
        df2["sig_group"] = "default"
    if "w_raw" not in df2.columns:
        df2["w_raw"] = 1.0
    if "sse" not in df2.columns:
        df2["sse"] = 0.0

    # strip & drop bad rows
    for c in ["meas_table", "meas_col", "model_key", "sig_group"]:
        df2[c] = df2[c].astype(str).str.strip()
    df2 = df2[(df2["meas_table"] != "") & (df2["meas_col"] != "") & (df2["model_key"] != "")].copy()

    # numeric
    df2["w_raw"] = pd.to_numeric(df2["w_raw"], errors="coerce").fillna(1.0)
    df2["sse"] = pd.to_numeric(df2["sse"], errors="coerce").fillna(0.0)

    # optional: per-signal constant time shift (seconds), if present in signals.csv
    if "time_shift_s" in df2.columns:
        df2["time_shift_s"] = pd.to_numeric(df2["time_shift_s"], errors="coerce").fillna(0.0)

    # aggregate (deduplicate across tests)
    agg_dict = {
        "sig_group": ("sig_group", "first"),
        "w_raw": ("w_raw", "median"),
        "sse": ("sse", "sum"),
        "n_rows": ("w_raw", "size"),
    }
    if "time_shift_s" in df2.columns:
        agg_dict["time_shift_s"] = ("time_shift_s", "median")

    g = df2.groupby(["meas_table", "meas_col", "model_key"], as_index=False).agg(**agg_dict)

    if top_n and top_n > 0:
        g = g.sort_values("sse", ascending=False).head(int(top_n))

    mapping: List[Dict[str, Any]] = []
    for _, row in g.iterrows():
        mapping.append({
            "meas_table": str(row["meas_table"]),
            "meas_col": str(row["meas_col"]),
            "model_key": str(row["model_key"]),
            "sig_group": str(row.get("sig_group", "default")),
            "weight": float(row["w_raw"]),
            **({"time_shift_s": float(row["time_shift_s"])} if "time_shift_s" in row else {}),
        })
    return mapping


def _npz_to_df(cols_key: str, values_key: str, z: np.lib.npyio.NpzFile) -> Optional[pd.DataFrame]:
    if cols_key not in z or values_key not in z:
        return None
    cols = z[cols_key].tolist()
    vals = z[values_key]
    return pd.DataFrame(vals, columns=cols)


def load_npz_tables(npz_path: Path) -> Dict[str, pd.DataFrame]:
    z = np.load(npz_path, allow_pickle=True)
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


def filter_mapping_by_npz(mapping: List[Dict[str, Any]], npz_tables: Dict[str, pd.DataFrame]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Удалить элементы mapping, которых нет в NPZ (meas_table/meas_col)."""
    kept: List[Dict[str, Any]] = []
    dropped: List[str] = []
    for m in mapping:
        tbl = str(m.get("meas_table", "main"))
        col = str(m.get("meas_col", ""))
        if tbl not in npz_tables:
            dropped.append(f"{tbl}:{col} (no table)")
            continue
        if col not in npz_tables[tbl].columns:
            dropped.append(f"{tbl}:{col} (no col)")
            continue
        kept.append(m)
    return kept, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals_csv", required=True)
    ap.add_argument("--out_mapping", required=True)
    ap.add_argument("--top_n", type=int, default=0, help="Если >0 — взять только топ-N сигналов по суммарному SSE")
    ap.add_argument("--osc_dir", default="", help="Если задано — проверять наличие meas_table/meas_col в NPZ")
    ap.add_argument("--test_num", type=int, default=1, help="Номер теста (Txx_osc.npz) для валидации mapping")
    ap.add_argument("--drop_missing", action="store_true", help="Если задано — удалить сигналы, которых нет в NPZ (иначе будет ошибка)")
    args = ap.parse_args()

    df = _load_signals_csv(Path(args.signals_csv))
    mapping = build_mapping_from_signals_csv(df, top_n=int(args.top_n))

    # optional validation against NPZ
    if args.osc_dir:
        osc_dir = Path(args.osc_dir)
        npz_path = osc_dir / f"T{int(args.test_num):02d}_osc.npz"
        if not npz_path.exists():
            raise SystemExit(f"NPZ не найден для валидации: {npz_path}")
        tables = load_npz_tables(npz_path)
        kept, dropped = filter_mapping_by_npz(mapping, tables)
        if dropped:
            msg = "\n".join(dropped[:50])
            if args.drop_missing:
                print("Dropped missing signals:\n", msg)
                mapping = kept
            else:
                raise SystemExit("В mapping есть сигналы, которых нет в NPZ:\n" + msg + "\n(используйте --drop_missing чтобы удалить)")
    out_path = Path(args.out_mapping)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote mapping: {out_path} ({len(mapping)} signals)")


if __name__ == "__main__":
    main()