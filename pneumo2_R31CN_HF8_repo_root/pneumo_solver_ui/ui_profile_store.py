# -*- coding: utf-8 -*-
"""ui_profile_store.py

Локальное хранилище «профилей настроек UI».

Зачем это нужно
---------------
Пользователь (инженер) вводит много параметров/таблиц. Требование проекта:
введённые значения не должны пропадать при перезапуске/обновлении.

Автосохранение решает 80% задач, но полезно иметь *несколько* именованных профилей:
- разные машины / варианты геометрии;
- разные сценарии дороги;
- «перед/зад отдельно» и т.д.

Формат
------
Профиль — обычный JSON со стейтом, который формирует ui_persistence.build_state_dict().
Мы добавляем метаданные:
- _profile_name
- _profile_saved_utc
- _profile_file

Файлы хранятся в:
  <state_dir>/profiles/*.json

Примечание
----------
Имена файлов делаем безопасными (ASCII + хэш), чтобы Windows/ZIP не ломались.
Отображаемое имя профиля хранится в самом JSON.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ui_persistence import pick_state_dir


def profiles_dir(state_dir: Path) -> Path:
    d = state_dir / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


_SAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_file_stem(name: str) -> str:
    """Безопасное имя файла (без расширения).

    - режем пробелы
    - оставляем ASCII a-zA-Z0-9._-
    - если осталось пусто — используем хэш
    """

    n = (name or "").strip()
    n = _SAFE_CHARS_RE.sub("_", n)
    n = re.sub(r"_+", "_", n).strip("_ .")
    if not n:
        n = "profile"
    # ограничим длину, остальное — в хэш
    if len(n) > 48:
        n = n[:48].rstrip("_ .")
    return n or "profile"


def make_profile_filename(name: str, content_hash: Optional[str] = None) -> str:
    """Сделать имя файла профиля.

    Используем: <stem>__<hash12>.json
    """

    stem = _safe_file_stem(name)
    h = (content_hash or hashlib.sha1(name.encode("utf-8", errors="ignore")).hexdigest())[:12]
    return f"{stem}__{h}.json"


def save_named_profile(state: Dict[str, Any], name: str, *, state_dir: Optional[Path] = None) -> Path:
    sd = state_dir or pick_state_dir()
    if sd is None:
        raise RuntimeError("state_dir недоступен (нет прав записи?)")

    # метаданные
    state = dict(state)
    state["_profile_name"] = str(name or "")
    state["_profile_saved_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # хэш для имени файла: зависит от полезной части
    try:
        payload = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except Exception:
        payload = repr(state).encode("utf-8", errors="ignore")
    h = hashlib.sha1(payload).hexdigest()

    fn = make_profile_filename(name, content_hash=h)
    d = profiles_dir(sd)
    p = d / fn

    # атомарно
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

    try:
        state["_profile_file"] = str(p)
    except Exception:
        pass
    return p


def list_named_profiles(*, state_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    sd = state_dir or pick_state_dir()
    if sd is None:
        return []
    d = profiles_dir(sd)
    out: List[Dict[str, Any]] = []
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text("utf-8"))
        except Exception:
            obj = {}
        name = str(obj.get("_profile_name") or p.stem)
        ts = str(obj.get("_profile_saved_utc") or "")
        out.append({
            "name": name,
            "saved_utc": ts,
            "path": str(p),
            "file": p.name,
            "size_kb": int(p.stat().st_size // 1024),
        })
    return out


def load_profile(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    obj = json.loads(p.read_text("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("profile JSON должен быть объектом")
    obj.setdefault("_profile_file", str(p))
    return obj


def delete_profile(path: str) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    p.unlink()
    return True


def diff_states(old: Dict[str, Any], new: Dict[str, Any], *, max_rows: int = 200) -> List[Dict[str, str]]:
    """Сравнить два state-dict и вернуть список изменений (для UI-превью)."""

    def _pv(v: Any) -> str:
        try:
            if v is None:
                return ""
            if isinstance(v, (int, float, bool, str)):
                s = str(v)
            else:
                s = json.dumps(v, ensure_ascii=False)
        except Exception:
            s = repr(v)
        if len(s) > 160:
            s = s[:157] + "…"
        return s

    keys = sorted(set(old.keys()) | set(new.keys()))
    rows: List[Dict[str, str]] = []
    for k in keys:
        if k.startswith("_"):
            continue
        ov = old.get(k, None)
        nv = new.get(k, None)
        if ov == nv:
            continue
        rows.append({"key": str(k), "old": _pv(ov), "new": _pv(nv)})
        if len(rows) >= max_rows:
            break
    return rows
