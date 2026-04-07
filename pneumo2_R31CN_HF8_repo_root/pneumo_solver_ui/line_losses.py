# -*- coding: utf-8 -*-
"""line_losses.py

Очень лёгкая (и намеренно *приближённая*) модель потерь на пневмолиниях
(шланги/трубки/фитинги) для сети, описанной в build_network_full.

Задача модуля:
- дать параметрическую ручку, чтобы учитывать, что между узлами модели в
  реальном железе есть длина шланга, фитинги, переходы и т.п.;
- не ломать топологию графа (никаких дополнительных узлов/рёбер), а просто
  вносить «штраф» в проводимость/проходное сечение существующих рёбер;
- позволить быстро включать/выключать это приближение через параметры.

⚠ Важно:
Это не Fanno-flow и не точная модель сжимаемого течения в трубопроводе.
Это инженерное приближение для быстрых прогонов и оптимизации.

Формула штрафа (в долях 0..1):
    f = max(min_factor, 1 / (1 + Klen*(L/D) + Kfit*Nfit))

Где:
- L — длина линии (м)
- D — внутренний диаметр (м)
- Nfit — число фитингов/локальных сопротивлений
- Klen, Kfit — эмпирические коэффициенты (по умолчанию из JSON)

Далее мы умножаем:
- A (и A_мин/A_макс) на f
- C_iso (и C_min/C_max) на f

Смысл: уменьшаем эквивалентную пропускную способность «как будто» линия
добавляет серию сопротивлений.

JSON формат (см. lines_map_default.json):
{
  "defaults": {"Klen":0.25, "Kfit":0.15, "min_factor":0.05},
  "segments": [
      {"match": "prefix...", "L_m": 2.0, "D_mm": 6.0, "n_fittings": 4, "note": "..."}
  ]
}

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json


@dataclass
class LineSegment:
    match: str
    L_m: float
    D_mm: float
    n_fittings: int = 0
    note: str = ""


def _to_float(x: Any, default: float) -> float:
    try:
        v = float(x)
        if v != v:  # NaN
            return default
        return v
    except Exception:
        return default


def _to_int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default


def load_lines_map(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('lines map JSON must be an object')
    data.setdefault('defaults', {})
    data.setdefault('segments', [])
    return data


def _pick_segment(edge_name: str, segments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Выбираем сегмент по самому длинному prefix-match."""
    best = None
    best_len = -1
    for seg in segments:
        m = str(seg.get('match', '') or '')
        if not m:
            continue
        if edge_name.startswith(m) and len(m) > best_len:
            best = seg
            best_len = len(m)
    return best


def compute_factor(L_m: float, D_mm: float, n_fittings: int, *, Klen: float, Kfit: float, min_factor: float) -> float:
    D_m = max(1e-6, float(D_mm) * 1e-3)
    L_m = max(0.0, float(L_m))
    n_fittings = max(0, int(n_fittings))

    denom = 1.0 + float(Klen) * (L_m / D_m) + float(Kfit) * n_fittings
    if denom <= 0:
        f = 1.0
    else:
        f = 1.0 / denom
    return float(max(float(min_factor), min(1.0, f)))


def _scale_attr(obj: Any, attr: str, f: float) -> None:
    if not hasattr(obj, attr):
        return
    v = getattr(obj, attr)
    if v is None:
        return
    try:
        setattr(obj, attr, float(v) * float(f))
    except Exception:
        # если поле нечисловое — игнор
        return


def apply_line_losses_to_edges(edges: List[Any], params: Dict[str, Any], *, base_dir: Path) -> Dict[str, Any]:
    """Применить штраф к рёбрам согласно lines_map.

    Возвращает отчёт (dict), который можно записать в df_atm / лог.
    """

    enabled = bool(params.get('учет_потерь_линий', params.get('line_losses_enable', False)))
    if not enabled:
        return {
            'enabled': False,
            'n_edges_affected': 0,
            'map_file': None,
            'note': 'disabled'
        }

    map_file = str(params.get('потери_линий_json', params.get('line_losses_json', 'lines_map_default.json')))
    path = Path(map_file)
    if not path.is_absolute():
        path = (base_dir / path).resolve()

    if not path.exists():
        return {
            'enabled': True,
            'n_edges_affected': 0,
            'map_file': str(path),
            'error': 'lines_map_not_found'
        }

    data = load_lines_map(path)
    defaults = data.get('defaults', {}) or {}
    segments = data.get('segments', []) or []

    Klen = _to_float(params.get('потери_линий_Klen', defaults.get('Klen', 0.25)), 0.25)
    Kfit = _to_float(params.get('потери_линий_Kfit', defaults.get('Kfit', 0.15)), 0.15)
    min_factor = _to_float(params.get('потери_линий_min_factor', defaults.get('min_factor', 0.05)), 0.05)

    affected = []

    for e in edges:
        seg = _pick_segment(getattr(e, 'name', ''), segments)
        if not seg:
            continue

        L_m = _to_float(seg.get('L_m', 0.0), 0.0)
        D_mm = _to_float(seg.get('D_mm', 0.0), 0.0)
        n_fit = _to_int(seg.get('n_fittings', 0), 0)

        if D_mm <= 0:
            continue

        f = compute_factor(L_m, D_mm, n_fit, Klen=Klen, Kfit=Kfit, min_factor=min_factor)
        if f >= 0.999999:
            continue

        # Масштабируем поля, которые присутствуют в Edge (в разных моделях набор разный)
        _scale_attr(e, 'A', f)
        _scale_attr(e, 'A_мин', f)
        _scale_attr(e, 'A_макс', f)

        _scale_attr(e, 'C_iso', f)
        _scale_attr(e, 'C_min', f)
        _scale_attr(e, 'C_max', f)

        affected.append({
            'edge': getattr(e, 'name', ''),
            'factor': f,
            'L_m': L_m,
            'D_mm': D_mm,
            'n_fittings': n_fit,
            'note': str(seg.get('note', '') or '')
        })

    return {
        'enabled': True,
        'map_file': str(path),
        'Klen': Klen,
        'Kfit': Kfit,
        'min_factor': min_factor,
        'n_edges_affected': len(affected),
        'affected': affected
    }
