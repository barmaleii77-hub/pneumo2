# -*- coding: utf-8 -*-
"""select_informative_tests_v1.py

Утилита: автоматический выбор "информативных" тестов из osc_dir (NPZ-логи)
для ускоренных coarse/multi-fidelity прогонов.

Зачем:
- В coarse-to-fine часто хочется сначала фитить не по всем тестам, а по подмножеству,
  которое реально возбуждает наблюдаемые сигналы.
- Этот скрипт строит ранжирование тестов по "энергии возбуждения" сигналов и
  возвращает top-K (или top-fraction).

Режимы:
- meas_variation (по умолчанию): оцениваем по измерениям из NPZ: суммарная
  робастная амплитуда (MAD) по сигналам из mapping_json с учётом weight.

Вход:
- osc_dir: папка с tests_index.csv и Txx_osc.npz.
- mapping_json: список сигналов (meas_table/meas_col/weight). Обычно из signals.csv.

Выход:
- out_json: JSON с выбранными тестами и таблицей score.

Пример:
python calibration/select_informative_tests_v1.py \
  --osc_dir osc_logs/RUN_... \
  --mapping_json calibration_runs/RUN_.../iter0/mapping.json \
  --mode meas_variation \
  --frac 0.5 --max_tests 6 --min_tests 3 \
  --out_json coarse_tests.json

"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _robust_scale(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        return 0.0
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    # 1.4826 ~ согласование MAD со σ при нормальности
    return 1.4826 * mad


def _read_tests_index(osc_dir: Path) -> List[Tuple[int, str]]:
    p = osc_dir / "tests_index.csv"
    if not p.exists():
        raise FileNotFoundError(f"tests_index.csv not found: {p}")
    df = pd.read_csv(p, encoding="utf-8-sig")
    if "номер" not in df.columns or "имя_теста" not in df.columns:
        raise ValueError("tests_index.csv must contain columns 'номер' and 'имя_теста'")
    out = []
    for _, r in df.iterrows():
        try:
            num = int(r["номер"])
        except Exception:
            continue
        name = str(r["имя_теста"]).strip()
        if name:
            out.append((num, name))
    return out


def _npz_get_table(z: np.lib.npyio.NpzFile, table: str) -> Tuple[List[str], np.ndarray]:
    cols_key = f"{table}_cols"
    vals_key = f"{table}_values"
    if cols_key not in z or vals_key not in z:
        return [], np.empty((0, 0), dtype=float)
    cols = z[cols_key].tolist()
    vals = z[vals_key]
    return [str(c) for c in cols], np.asarray(vals)


def _score_test(npz_path: Path, mapping: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """Возвращает (score, details)."""
    z = np.load(npz_path, allow_pickle=True)

    # кэш таблиц (cols->idx)
    table_cache: Dict[str, Tuple[List[str], np.ndarray, Dict[str, int]]] = {}

    def get_col(table: str, col: str) -> np.ndarray | None:
        if table not in table_cache:
            cols, vals = _npz_get_table(z, table)
            idx = {c: i for i, c in enumerate(cols)}
            table_cache[table] = (cols, vals, idx)
        cols, vals, idx = table_cache[table]
        j = idx.get(col)
        if j is None:
            return None
        try:
            v = vals[:, int(j)]
        except Exception:
            return None
        # пропускаем нечисловые
        try:
            v = np.asarray(v, dtype=float)
        except Exception:
            return None
        return v

    total = 0.0
    used = 0
    missing = 0
    per_sig = []

    for m in mapping:
        if int(m.get("enabled", 1)) != 1:
            continue
        table = str(m.get("meas_table", "main")).strip() or "main"
        col = str(m.get("meas_col", "")).strip()
        if not col:
            continue
        w = float(m.get("weight", m.get("w_raw", 1.0)))
        v = get_col(table, col)
        if v is None:
            missing += 1
            continue
        sc = _robust_scale(v)
        if sc <= 0:
            continue
        n_eff = int(np.sum(np.isfinite(v)))
        # score: scale * weight * sqrt(n)
        contrib = float(sc) * float(w) * math.sqrt(max(1, n_eff))
        total += contrib
        used += 1
        per_sig.append({"table": table, "col": col, "w": w, "scale": sc, "n": n_eff, "contrib": contrib})

    details = {
        "signals_used": int(used),
        "signals_missing": int(missing),
        "contribs_top": sorted(per_sig, key=lambda d: float(d.get("contrib", 0.0)), reverse=True)[:12],
    }
    return float(total), details


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--mapping_json", required=True)
    ap.add_argument("--mode", default="meas_variation", choices=["meas_variation"], help="Scoring mode")

    ap.add_argument("--exclude_tests", default="", help="Comma-separated test names to exclude")
    ap.add_argument("--frac", type=float, default=0.5)
    ap.add_argument("--max_tests", type=int, default=6)
    ap.add_argument("--min_tests", type=int, default=3)

    ap.add_argument("--out_json", required=True)

    args = ap.parse_args()

    osc_dir = Path(args.osc_dir)
    mapping_json = Path(args.mapping_json)
    out_json = Path(args.out_json)

    tests = _read_tests_index(osc_dir)
    mapping = _load_json(mapping_json)
    if not isinstance(mapping, list):
        raise ValueError("mapping_json must be a list")

    exclude = {s.strip() for s in str(args.exclude_tests).split(",") if s.strip()}

    rows = []
    for num, name in tests:
        if name in exclude:
            continue
        npz = osc_dir / f"T{num:02d}_osc.npz"
        if not npz.exists():
            continue
        score, details = _score_test(npz, mapping)
        rows.append({
            "test_num": int(num),
            "test": str(name),
            "score": float(score),
            **details,
        })

    rows_sorted = sorted(rows, key=lambda r: float(r.get("score", 0.0)), reverse=True)
    n_total = len(rows_sorted)

    frac = float(args.frac)
    k = int(math.ceil(max(0.0, min(1.0, frac)) * n_total)) if n_total > 0 else 0
    k = max(int(args.min_tests), k)
    k = min(int(args.max_tests), k)
    k = min(k, n_total)

    selected = [r["test"] for r in rows_sorted[:k]]

    out = {
        "mode": str(args.mode),
        "osc_dir": str(osc_dir),
        "mapping_json": str(mapping_json),
        "exclude_tests": sorted(list(exclude)),
        "frac": float(frac),
        "max_tests": int(args.max_tests),
        "min_tests": int(args.min_tests),
        "n_total": int(n_total),
        "k_selected": int(k),
        "selected_tests": selected,
        "scores": rows_sorted,
    }

    _save_json(out, out_json)
    print(f"Selected tests: {k}/{n_total} -> {out_json}")


if __name__ == "__main__":
    main()
