# -*- coding: utf-8 -*-
"""persist_state.py

Автосохранение состояния Streamlit UI на диск (best-effort).

Зачем:
- st.session_state живёт только в рамках текущей сессии браузера.
- при обновлении вкладки/перезапуске приложения состояние теряется.

Решение:
- сохраняем JSON-совместимые ключи st.session_state в файл
- при старте приложения восстанавливаем значения (только если ключ отсутствует)

Ограничения:
- бинарные объекты, большие DataFrame/ndarray и прочие не-JSON значения пропускаются.
- это не БД и не "истина в последней инстанции"; цель — сохранение UI настроек.
"""

from __future__ import annotations

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional

import numpy as np


DEFAULT_DIRNAME = "USER_STATE"
DEFAULT_FILENAME = "streamlit_session_state.json"


def _default_state_path() -> Path:
    """Где хранить состояние.

    По умолчанию: ./USER_STATE/streamlit_session_state.json
    """
    base = Path.cwd() / DEFAULT_DIRNAME
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        # fallback: домашняя папка
        base = Path.home() / ".pneumo_solver_ui" / DEFAULT_DIRNAME
        base.mkdir(parents=True, exist_ok=True)
    return base / DEFAULT_FILENAME


def _to_jsonable(x: Any, *, max_list: int = 5000, _depth: int = 0) -> Any:
    """Best-effort конвертация значения в JSON-совместимый тип."""
    if _depth > 6:
        return None

    if x is None:
        return None

    # primitives
    if isinstance(x, (bool, int, float, str)):
        if isinstance(x, float) and (not np.isfinite(x)):
            return None
        return x

    # pathlib
    if isinstance(x, Path):
        return str(x)

    # numpy scalars
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        v = float(x)
        return v if np.isfinite(v) else None

    # numpy arrays (small only)
    if isinstance(x, np.ndarray):
        arr = np.asarray(x)
        if arr.size > max_list:
            return None
        try:
            return _to_jsonable(arr.tolist(), max_list=max_list, _depth=_depth + 1)
        except Exception:
            return None

    # mappings
    if isinstance(x, Mapping):
        out: Dict[str, Any] = {}
        for k, v in x.items():
            ks = str(k)
            out[ks] = _to_jsonable(v, max_list=max_list, _depth=_depth + 1)
        return out

    # sequences
    if isinstance(x, (list, tuple, set)):
        seq = list(x)
        if len(seq) > max_list:
            seq = seq[:max_list]
        return [_to_jsonable(v, max_list=max_list, _depth=_depth + 1) for v in seq]

    # fallthrough: not serializable
    return None


def _sanitize_session_state(state: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Отобрать/привести значения, которые реально имеет смысл сохранять."""
    out: Dict[str, Any] = {}
    for k, v in dict(state).items():
        ks = str(k)
        # internal / system keys
        if ks.startswith("_"):
            continue
        if ks in {"_persist_last_hash", "_persist_last_save_ts"}:
            continue

        vv = _to_jsonable(v)
        if vv is None:
            continue

        # additionally filter by encoded size (avoid megabytes)
        try:
            s = json.dumps(vv, ensure_ascii=False)
        except Exception:
            continue
        if len(s) > 250_000:
            continue

        out[ks] = vv

    return out


def load_session_state(
    *,
    state_path: Optional[Path] = None,
    target: Optional[MutableMapping[str, Any]] = None,
    overwrite: bool = False,
) -> bool:
    """Загрузить значения из файла в st.session_state (или другой target).

    overwrite=False: не перезаписывать существующие ключи.
    """
    state_path = Path(state_path) if state_path is not None else _default_state_path()
    target = target if target is not None else None

    try:
        if not state_path.exists():
            return False
        raw = state_path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return False
    except Exception:
        return False

    if target is None:
        # late import to avoid hard dependency if module used outside Streamlit
        import streamlit as st

        target = st.session_state

    for k, v in data.items():
        if not overwrite and k in target:
            continue
        target[k] = v

    return True


def _hash_dict(d: Dict[str, Any]) -> str:
    s = json.dumps(d, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def autosave_session_state(
    *,
    state_path: Optional[Path] = None,
    source: Optional[MutableMapping[str, Any]] = None,
    min_interval_s: float = 1.0,
) -> bool:
    """Автосохранение state на диск (throttled).

    Возвращает True, если реально записали файл.
    """
    state_path = Path(state_path) if state_path is not None else _default_state_path()

    if source is None:
        import streamlit as st

        source = st.session_state

    try:
        now = time.time()
        last_ts = float(source.get("_persist_last_save_ts", 0.0) or 0.0)
        if (now - last_ts) < float(min_interval_s):
            return False

        payload = _sanitize_session_state(source)
        h = _hash_dict(payload)
        last_h = str(source.get("_persist_last_hash", "") or "")
        if h == last_h:
            return False

        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(state_path))

        source["_persist_last_hash"] = h
        source["_persist_last_save_ts"] = now
        return True
    except Exception:
        return False
