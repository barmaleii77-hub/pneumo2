# -*- coding: utf-8 -*-
"""osc_csv_to_npz_v1.py

Конвертер осциллограмм формата CSV (которые пишет Streamlit UI в baseline)
в формат NPZ, который использует калибровка по осциллограммам.

Контекст проекта:
- UI умеет сохранять осциллограммы как CSV (много файлов, удобно в Excel)
  или как NPZ (один файл на тест, компактно, быстро).
- Все пайплайны калибровки в папке calibration/ ожидают NPZ вида Txx_osc.npz
  с ключами main_cols/main_values, p_cols/p_values, q_cols/q_values, open_cols/open_values,
  (опционально) Eedges/Egroups/atm.

Этот скрипт позволяет НЕ переделывать старые логи/архивы:
вы можете конвертировать уже записанные CSV-осциллограммы в NPZ и сразу запускать Autopilot.

Пример:
  python calibration/osc_csv_to_npz_v1.py --osc_dir osc_logs/baseline_20260119_150356

Параметры:
  --osc_dir      папка с tests_index.csv и файлами Txx_main.csv / Txx_p_nodes_Pa.csv ...
  --out_dir      куда писать NPZ (по умолчанию = osc_dir)
  --overwrite    перезаписать существующие Txx_osc.npz

Ограничения:
- Скрипт рассчитан на CSV-структуру, которую пишет save_oscillograms_bundle() в pneumo_ui_app.py.
- Если каких-то CSV нет — соответствующая таблица пропускается (NPZ будет частичным).

"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _read_csv(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        # fallback (редко, но бывает если кто-то пересохранил)
        return pd.read_csv(path, encoding="utf-8")


def _df_to_np_payload(df: pd.DataFrame, cols_key: str, values_key: str, numeric: bool = True) -> Dict[str, np.ndarray]:
    cols = np.array(list(df.columns), dtype=object)
    if numeric:
        # Принудительно в float, но бережно: ошибки -> NaN
        vals = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float, copy=False)
    else:
        # Для таблиц с текстовыми колонками (Eedges/Egroups)
        vals = df.to_numpy(copy=False)
    return {cols_key: cols, values_key: vals}


def _detect_test_nums(osc_dir: Path) -> List[int]:
    # Ищем Txx_main.csv (самый надёжный маркер)
    nums: List[int] = []
    for p in osc_dir.glob("T*_main.csv"):
        name = p.stem  # T01_main
        try:
            # ожидаем T01_main
            t = name.split("_")[0]
            if t.startswith("T"):
                nums.append(int(t[1:]))
        except Exception:
            pass
    nums = sorted(list(dict.fromkeys(nums)))
    return nums


def convert_one_test(osc_dir: Path, out_dir: Path, test_num: int, overwrite: bool) -> Tuple[Path, Dict[str, str]]:
    prefix = f"T{int(test_num):02d}"

    out_npz = out_dir / f"{prefix}_osc.npz"
    if out_npz.exists() and not overwrite:
        return out_npz, {"skipped": "exists"}

    # CSV paths from UI
    p_main = osc_dir / f"{prefix}_main.csv"
    p_p = osc_dir / f"{prefix}_p_nodes_Pa.csv"
    p_q = osc_dir / f"{prefix}_q_edges_kg_s.csv"
    p_open = osc_dir / f"{prefix}_open_edges_0_1.csv"
    p_Eedges = osc_dir / f"{prefix}_energy_edges_J.csv"
    p_Egroups = osc_dir / f"{prefix}_energy_groups_J.csv"
    p_atm = osc_dir / f"{prefix}_atm_mass_kg.csv"

    df_main = _read_csv(p_main)
    if df_main is None:
        raise FileNotFoundError(f"Не найден обязательный файл: {p_main}")

    payload: Dict[str, np.ndarray] = {}
    payload.update(_df_to_np_payload(df_main, "main_cols", "main_values", numeric=True))

    df_p = _read_csv(p_p)
    if isinstance(df_p, pd.DataFrame):
        payload.update(_df_to_np_payload(df_p, "p_cols", "p_values", numeric=True))

    df_q = _read_csv(p_q)
    if isinstance(df_q, pd.DataFrame):
        payload.update(_df_to_np_payload(df_q, "q_cols", "q_values", numeric=True))

    df_open = _read_csv(p_open)
    if isinstance(df_open, pd.DataFrame):
        payload.update(_df_to_np_payload(df_open, "open_cols", "open_values", numeric=True))

    # Energy tables can contain text columns -> store object array
    df_Eedges = _read_csv(p_Eedges)
    if isinstance(df_Eedges, pd.DataFrame):
        payload.update(_df_to_np_payload(df_Eedges, "Eedges_cols", "Eedges_values", numeric=False))

    df_Egroups = _read_csv(p_Egroups)
    if isinstance(df_Egroups, pd.DataFrame):
        payload.update(_df_to_np_payload(df_Egroups, "Egroups_cols", "Egroups_values", numeric=False))

    df_atm = _read_csv(p_atm)
    if isinstance(df_atm, pd.DataFrame):
        payload.update(_df_to_np_payload(df_atm, "atm_cols", "atm_values", numeric=True))

    # write
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, **payload)

    meta = {
        "main": str(p_main.name),
        "p": str(p_p.name) if p_p.exists() else "",
        "q": str(p_q.name) if p_q.exists() else "",
        "open": str(p_open.name) if p_open.exists() else "",
        "Eedges": str(p_Eedges.name) if p_Eedges.exists() else "",
        "Egroups": str(p_Egroups.name) if p_Egroups.exists() else "",
        "atm": str(p_atm.name) if p_atm.exists() else "",
    }
    return out_npz, meta


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert osc_dir CSV logs to NPZ format used by calibration")
    ap.add_argument("--osc_dir", required=True)
    ap.add_argument("--out_dir", default="")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    osc_dir = Path(str(args.osc_dir)).expanduser()
    if not osc_dir.exists():
        raise SystemExit(f"osc_dir не существует: {osc_dir}")

    out_dir = Path(str(args.out_dir)).expanduser() if str(args.out_dir).strip() else osc_dir

    nums = _detect_test_nums(osc_dir)
    if not nums:
        raise SystemExit(
            "Не удалось найти T*_main.csv. "
            "Ожидалась структура UI-логов: T01_main.csv, T01_p_nodes_Pa.csv, ..."
        )

    print(f"osc_dir: {osc_dir}")
    print(f"out_dir: {out_dir}")
    print(f"tests detected: {nums}")

    converted = 0
    skipped = 0
    for n in nums:
        try:
            out_npz, meta = convert_one_test(osc_dir, out_dir, test_num=n, overwrite=bool(args.overwrite))
            if meta.get("skipped") == "exists":
                print(f"  - T{n:02d}: SKIP (exists) -> {out_npz.name}")
                skipped += 1
            else:
                print(f"  - T{n:02d}: OK -> {out_npz.name}")
                converted += 1
        except Exception as e:
            print(f"  - T{n:02d}: ERROR: {e}")

    print(f"Done. converted={converted}, skipped={skipped}")


if __name__ == "__main__":
    main()
