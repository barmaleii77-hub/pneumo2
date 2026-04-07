# -*- coding: utf-8 -*-
"""npz_autosuggest_mapping_v2.py

Автогенерация mapping JSON для калибровки по NPZ-логам (osc_dir из UI).

Зачем:
  В fit_worker_v3_suite_identify.py mapping задаётся вручную. Это правильно для
  реальных измерений, но при старте часто хочется «быстро начать» и потом
  постепенно расширять mapping.

Что делает:
  - читает один NPZ (Txx_osc.npz) и смотрит, какие таблицы/колонки есть;
  - по заданному режиму (mode) строит mapping:
      * minimal  : базовые сигналы из main (давления ресиверов/акк + крен/тангаж)
      * main_all : берёт ВСЕ колонки main, которые выглядят как давление/углы/ходы
      * extended : minimal + часть p/q/open по эвристикам (ключевые узлы/рёбра)

Важно:
  - это НЕ «магия»: итоговый mapping нужно проверять.
  - для давления в Па по умолчанию ставим weight=1e-5 (Па -> бар),
    чтобы не забивать углы/ходы.

Безопасность:
  NPZ может содержать object-массивы (Eedges/Egroups). Для чтения используем
  allow_pickle=True (как в fit_worker). Не загружайте NPZ из недоверенных источников.

Пример:
  python calibration/npz_autosuggest_mapping_v2.py --osc_dir osc_logs/RUN_... --test_num 1 \
      --mode extended --out_mapping mapping_auto.json

"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


def _weight_for_col(name: str) -> float:
    n = name.lower()
    if "давление" in n or n.endswith("_pa") or n.endswith("_па"):
        return 1e-5
    # открытия 0/1 и прочие дискреты лучше не задирать
    if "open" in n or "открыт" in n:
        return 1.0
    return 1.0


def _add_mapping(mapping: List[Dict[str, Any]], table: str, col: str, model_table: str, model_col: str):
    mapping.append({
        "meas_table": str(table),
        "meas_col": str(col),
        "model_key": f"{model_table}:{model_col}",
        "weight": float(_weight_for_col(col)),
    })


def _select_by_keywords(cols: Sequence[str], keywords: Sequence[str], max_items: int) -> List[str]:
    out: List[str] = []
    kws = [k.lower() for k in keywords if str(k).strip()]
    for c in cols:
        cl = str(c).lower()
        if any(k in cl for k in kws):
            out.append(str(c))
            if len(out) >= max_items:
                break
    return out


def build_mapping(meas: Dict[str, pd.DataFrame], mode: str = "minimal", max_p: int = 40, max_q: int = 30, max_open: int = 30) -> List[Dict[str, Any]]:
    if "main" not in meas:
        raise ValueError("NPZ не содержит таблицу 'main'")
    df_main = meas["main"]
    main_cols = list(df_main.columns)

    mapping: List[Dict[str, Any]] = []

    if mode == "minimal":
        # стабильные ключевые сигналы
        for col in (
            "давление_ресивер1_Па",
            "давление_ресивер2_Па",
            "давление_ресивер3_Па",
            "давление_аккумулятор_Па",
            "крен_phi_рад",
            "тангаж_theta_рад",
            "перемещение_рамы_z_м",
        ):
            if col in df_main.columns:
                _add_mapping(mapping, "main", col, "main", col)
        return mapping

    if mode == "main_all":
        # Давления/углы/позиции/скорости — всё из main
        # (time_col в mapping не добавляем)
        patterns = [
            r"давление_.*(_па|_pa)$",
            r"^(крен|тангаж)_.*_рад$",
            r"перемещение_.*_м$",
            r"положение_.*_м$",
            r"скорость_.*_м_с$",
            r"нормальная_сила_шины_.*_н$",
        ]
        rx = [re.compile(p, re.IGNORECASE) for p in patterns]
        for c in main_cols:
            if c == detect_time_col(df_main):
                continue
            if any(r.search(str(c)) for r in rx):
                _add_mapping(mapping, "main", str(c), "main", str(c))
        return mapping

    if mode != "extended":
        raise ValueError("mode должен быть minimal/main_all/extended")

    # extended = minimal + выборка из p/q/open
    mapping.extend(build_mapping(meas, mode="minimal"))

    # p-table: давление во всех узлах — огромно. Берём ключевые по словам.
    if "p" in meas:
        df_p = meas["p"]
        p_cols = [c for c in df_p.columns if str(c) not in ("время_с", "t", "time")]
        pick_p = _select_by_keywords(
            p_cols,
            keywords=[
                "ресивер",
                "акк",
                "acc",
                "cap",
                "rod",
                "ц1",
                "ц2",
            ],
            max_items=max_p,
        )
        for c in pick_p:
            _add_mapping(mapping, "p", c, "p", c)

    # q-table: расходы по рёбрам. Берём характерные элементы.
    if "q" in meas:
        df_q = meas["q"]
        q_cols = [c for c in df_q.columns if str(c) not in ("время_с", "t", "time")]
        pick_q = _select_by_keywords(
            q_cols,
            keywords=[
                "дрос",
                "orifice",
                "relief",
                "предохран",
                "check",
                "обрат",
                "reg",
                "рег",
                "атм",
                "atm",
                "выхлоп",
            ],
            max_items=max_q,
        )
        for c in pick_q:
            _add_mapping(mapping, "q", c, "q", c)

    # open-table: если есть — берём те же рёбра, что и q (первые max_open)
    if "open" in meas:
        df_o = meas["open"]
        o_cols = [c for c in df_o.columns if str(c) not in ("время_с", "t", "time")]
        # пересечение с q
        o_pick: List[str] = []
        if "q" in meas:
            q_set = set([m["meas_col"] for m in mapping if m.get("meas_table") == "q"])
            for c in o_cols:
                if c in q_set:
                    o_pick.append(str(c))
                    if len(o_pick) >= max_open:
                        break
        else:
            o_pick = _select_by_keywords(o_cols, keywords=["дрос", "reg", "клап"], max_items=max_open)
        for c in o_pick:
            _add_mapping(mapping, "open", c, "open", c)

    # удалить дубли (иногда minimal и main_all могут пересекаться)
    seen = set()
    dedup: List[Dict[str, Any]] = []
    for m in mapping:
        key = (m.get("meas_table"), m.get("meas_col"), m.get("model_key"))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(m)
    return dedup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="", help="Путь к Txx_osc.npz")
    ap.add_argument("--osc_dir", default="", help="Папка osc_logs/RUN_... (с tests_index.csv)")
    ap.add_argument("--test_num", type=int, default=1, help="номер теста (как в имени Txx_osc.npz)")
    ap.add_argument("--mode", default="extended", help="minimal/main_all/extended")
    ap.add_argument("--max_p", type=int, default=40)
    ap.add_argument("--max_q", type=int, default=30)
    ap.add_argument("--max_open", type=int, default=30)
    ap.add_argument("--out_mapping", required=True, help="Куда сохранить mapping JSON")
    args = ap.parse_args()

    if args.npz:
        npz_path = Path(args.npz)
    else:
        if not args.osc_dir:
            raise SystemExit("Нужно указать --npz или --osc_dir")
        osc_dir = Path(args.osc_dir)
        npz_path = osc_dir / f"T{int(args.test_num):02d}_osc.npz"

    if not npz_path.exists():
        # Важно: этот скрипт часто запускается из oneclick/autopilot.
        # Если пользователь указал неверный osc_dir (например, корень проекта)
        # или ещё не сохранил осциллограммы, не «роняем» всё трассировкой.
        # Делаем полезное действие: создаём шаблон mapping и завершаемся с кодом 0.
        out_path = Path(args.out_mapping)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            here = Path(__file__).resolve().parent
            tpl = (here / "mapping_npz_extended_template.json").read_text(encoding="utf-8")
            out_path.write_text(tpl, encoding="utf-8")
        except Exception:
            # ultra-safe fallback
            out_path.write_text(json.dumps({"__comment": "template (npz missing)", "signals": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
        miss = out_path.with_name("MISSING_NPZ.txt")
        try:
            miss.write_text(
                f"NPZ not found: {npz_path}\n"
                "Укажите корректный --osc_dir (папка с T01_osc.npz, tests_index.csv) или --npz.\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"[WARN] Не найден файл NPZ: {npz_path}. Записан шаблон mapping: {out_path}")
        return 0

    meas = load_meas_npz(npz_path)
    mapping = build_mapping(meas, mode=str(args.mode).strip().lower(), max_p=int(args.max_p), max_q=int(args.max_q), max_open=int(args.max_open))

    out_path = Path(args.out_mapping)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote mapping: {out_path} (items={len(mapping)})")


if __name__ == "__main__":
    main()
