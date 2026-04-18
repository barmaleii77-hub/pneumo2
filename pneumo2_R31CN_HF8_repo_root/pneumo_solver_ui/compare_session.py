# -*- coding: utf-8 -*-
"""compare_session.py

Единый формат "сессии сравнения" для Web и Qt viewer.

Зачем:
- сравнение результатов симуляций — это не только список NPZ, но и:
  * таблица (main/p/q/open/full)
  * набор сигналов
  * режим overlay/Δ
  * reference run
  * baseline и единицы
  * lock шкал и окно времени

Сессию можно сохранить в JSON и открыть в другом интерфейсе.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CompareSession:
    version: str = "diagrammy_compare_session_v1"

    # data
    npz_paths: List[str] = None  # type: ignore[assignment]
    labels: Optional[List[str]] = None

    # view
    table: str = "main"
    signals: List[str] = None  # type: ignore[assignment]

    mode: str = "overlay"  # overlay | delta
    reference_label: Optional[str] = None

    # units
    dist_unit: str = "mm"
    angle_unit: str = "deg"
    flow_unit: str = "raw"  # raw | Nl/min (ANR)
    p_atm_pa: float = 100000.0

    # baseline
    zero_baseline: bool = True
    baseline_mode: str = "t0"  # t0 | median_window | mean_window | median_first_n | mean_first_n
    baseline_window_s: float = 0.0
    baseline_first_n: int = 0

    # scales
    lock_y_signal: bool = True
    lock_y_unit: bool = True
    robust_y: bool = True
    sym_y: bool = True

    # time
    time_window: Optional[Tuple[float, float]] = None
    playhead_t: Optional[float] = None

    # v32 explicit compare context (consumer refs, not optimizer history)
    compare_contract: Optional[Dict[str, Any]] = None
    compare_contract_hash: str = ""
    baseline_ref: Optional[Dict[str, Any]] = None
    objective_ref: Optional[Dict[str, Any]] = None
    run_refs: Optional[List[Dict[str, Any]]] = None
    current_context_ref: Optional[Dict[str, Any]] = None
    current_context_path: str = ""
    current_context_ref_source_path: str = ""
    current_context_ref_source_status: str = ""
    mismatch_banner: Optional[Dict[str, Any]] = None
    session_source: str = ""

    def __post_init__(self):
        if self.npz_paths is None:
            self.npz_paths = []
        if self.signals is None:
            self.signals = []
        if self.run_refs is None:
            self.run_refs = []


def to_json_dict(sess: CompareSession) -> Dict[str, Any]:
    d = asdict(sess)
    # tuples become lists in json
    return d


def dumps(sess: CompareSession, *, indent: int = 2) -> str:
    return json.dumps(to_json_dict(sess), ensure_ascii=False, indent=indent)


def loads(text: str) -> CompareSession:
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("Session JSON must be an object")
    # tolerate missing and future fields
    allowed = {f.name for f in fields(CompareSession)}
    clean = {k: v for k, v in obj.items() if k in allowed}
    return CompareSession(**clean)


def load_file(path: str | Path) -> CompareSession:
    p = Path(path)
    return loads(p.read_text(encoding="utf-8"))


def save_file(sess: CompareSession, path: str | Path) -> None:
    p = Path(path)
    p.write_text(dumps(sess), encoding="utf-8")
