# -*- coding: utf-8 -*-
"""diag_bundle.py

Небольшой диагностический ZIP, который можно скачать прямо из UI.

Цель:
- дать пользователю один файл для отправки разработчику, когда "что-то сломалось";
- включить минимально достаточную информацию (логи + окружение + введённые настройки).

Важно:
- должен быть лёгким (не сотни мегабайт);
- должен собираться быстро, т.к. Streamlit перерисовывается часто.

Для полного "тяжёлого" архива используйте страницу
"Сборка архива (ZIP)" (она может включать больше артефактов).
"""

from __future__ import annotations

import io
import json
import os
import platform
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _env_dir(key: str, default: Path) -> Path:
    v = (os.environ.get(key) or "").strip()
    if not v:
        return default
    try:
        return Path(v).expanduser().resolve()
    except Exception:
        return Path(v)


def _safe_add_file(zf: zipfile.ZipFile, src: Path, arcname: str, *, max_file_mb: float) -> bool:
    try:
        if not src.exists() or not src.is_file():
            return False
        sz = src.stat().st_size
        if sz > int(max_file_mb * 1024 * 1024):
            return False
        zf.write(src, arcname=arcname)
        return True
    except Exception:
        return False


def build_diag_bundle_bytes(
    *,
    max_files: int = 200,
    max_file_mb: float = 10.0,
    max_total_mb: float = 35.0,
) -> Tuple[bytes, str]:
    """Собрать диагностический архив и вернуть (bytes, filename)."""

    here = Path(__file__).resolve().parent

    log_dir = _env_dir("PNEUMO_LOG_DIR", here / "logs")

    # Состояние UI (autosave)
    autosave_path: Optional[Path] = None
    try:
        from pneumo_solver_ui.ui_persistence import pick_state_dir, autosave_path as _autosave_path

        sd = pick_state_dir(here)
        if sd is not None:
            ap = _autosave_path(sd)
            if ap.exists():
                autosave_path = ap
    except Exception:
        autosave_path = None

    meta: Dict[str, Any] = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "python": sys.version,
        "platform": platform.platform(),
        "env": {
            "PNEUMO_RELEASE": os.environ.get("PNEUMO_RELEASE"),
            # пути редактируем до basename, чтобы не утекали абсолютные пути при отправке диагностики
            "PNEUMO_WORKSPACE_DIR": (Path(os.environ.get("PNEUMO_WORKSPACE_DIR")).name if os.environ.get("PNEUMO_WORKSPACE_DIR") else None),
            "PNEUMO_LOG_DIR": (Path(os.environ.get("PNEUMO_LOG_DIR")).name if os.environ.get("PNEUMO_LOG_DIR") else None),
            "PNEUMO_STATE_DIR": (Path(os.environ.get("PNEUMO_STATE_DIR")).name if os.environ.get("PNEUMO_STATE_DIR") else None),
        },
        "paths": {
            "log_dir": str(getattr(log_dir, "name", "")) if log_dir else None,
            "autosave": str(getattr(autosave_path, "name", "")) if autosave_path else None,
        },
        "notes": [
            "Абсолютные пути исключены/усечены (basename) для приватности при отправке диагностики.",
        ],
    }
    try:
        import streamlit as st  # type: ignore

        meta["streamlit"] = getattr(st, "__version__", "")
    except Exception:
        pass

    try:
        from pneumo_solver_ui.release_info import get_release

        meta["app_release"] = get_release(default=os.environ.get("PNEUMO_RELEASE", ""))
    except Exception:
        meta["app_release"] = os.environ.get("PNEUMO_RELEASE", "")

    buf = io.BytesIO()

    total = 0
    files_added = 0

    def _can_add(size: int) -> bool:
        return (total + size) <= int(max_total_mb * 1024 * 1024)

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # meta
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        # autosave
        if autosave_path is not None:
            try:
                _safe_add_file(zf, autosave_path, "ui/autosave_profile.json", max_file_mb=max_file_mb)
            except Exception:
                pass

        # configs (маленькие)
        for rel in [
            here / "default_base.json",
            here / "default_ranges.json",
            here / "default_suite.json",
            here / "default_suite_long.json",
        ]:
            try:
                if rel.exists():
                    _safe_add_file(zf, rel, f"ui/{rel.name}", max_file_mb=max_file_mb)
            except Exception:
                pass

        # logs (ограниченно)
        if log_dir and Path(log_dir).exists():
            try:
                # сортируем по времени (сначала свежие)
                log_files = [p for p in Path(log_dir).rglob("*") if p.is_file()]
                log_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                for p in log_files:
                    if files_added >= max_files:
                        break
                    try:
                        sz = int(p.stat().st_size)
                    except Exception:
                        continue
                    if sz > int(max_file_mb * 1024 * 1024):
                        continue
                    if not _can_add(sz):
                        continue
                    arcname = f"logs/{p.relative_to(Path(log_dir))}"
                    if _safe_add_file(zf, p, arcname, max_file_mb=max_file_mb):
                        total += sz
                        files_added += 1
            except Exception:
                pass

    fname = "PneumoApp_Diagnostics.zip"
    return buf.getvalue(), fname


def get_or_build_diag_bundle(st_mod: Any) -> Tuple[bytes, str]:
    """Вернуть кэшированный диагностический ZIP, чтобы не собирать на каждый rerun."""

    cache_key = "_ui_diag_bundle_bytes"
    name_key = "_ui_diag_bundle_name"
    ts_key = "_ui_diag_bundle_ts"

    try:
        # обновляем не чаще, чем раз в 2 секунды
        last_ts = float(st_mod.session_state.get(ts_key) or 0.0)
        if (time.time() - last_ts) < 2.0 and st_mod.session_state.get(cache_key):
            return st_mod.session_state[cache_key], st_mod.session_state.get(name_key, "PneumoApp_Diagnostics.zip")
    except Exception:
        pass

    data, fname = build_diag_bundle_bytes()
    try:
        st_mod.session_state[cache_key] = data
        st_mod.session_state[name_key] = fname
        st_mod.session_state[ts_key] = time.time()
    except Exception:
        pass
    return data, fname
