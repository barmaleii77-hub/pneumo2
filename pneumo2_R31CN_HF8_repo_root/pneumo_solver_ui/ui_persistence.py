# -*- coding: utf-8 -*-
"""ui_persistence.py

Надёжное сохранение/восстановление введённых пользователем данных в UI.

Требование проекта
------------------
Все значения, которые пользователь ввёл в UI, не должны пропадать при
обновлении страниц и повторном запуске приложения.

Решение
-------
- Сохраняем полезную часть `st.session_state` в небольшой JSON.
- Загружаем её один раз в начале сессии.
- Сохраняем на каждом rerun (best‑effort) с дебаунсом по хэшу.

Важно
-----
- НЕ сохраняем тяжёлые результаты расчётов (baseline/npz/cache/logs/figures).
- НЕ сохраняем триггеры (кнопки/подтверждения), чтобы действия не
  «самонажимались» после автозагрузки.
- Запись атомарная (tmp + os.replace) + резервная копия
  (autosave_profile.bak.json).

Этот модуль не зависит от Streamlit напрямую: ему достаточно объекта `st_mod`
с полем `session_state`, который ведёт себя как dict.
"""

from __future__ import annotations

import hashlib
import json
from pneumo_solver_ui.diag.json_safe import json_dumps
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd


# -------------------------------
# Константы / фильтры
# -------------------------------

STATE_SCHEMA_VERSION = 4

# Явно сохраняемые объекты (структурированные вводы)
PERSIST_EXACT_KEYS = {
    "df_params_edit",
    "df_suite_edit",
    "spring_table_df",
}

# Префиксы «пользовательских» ключей UI (их безопасно сохранять, если они JSON‑совместимы)
PERSIST_PREFIXES = (
    "ui_",
    "baseline_",
    "events_",
    "playhead_",
    "gs_",
    "cal_",
    "compare_",
    "opt_",
    "osc_",
    "spring_",
    "detail_",
    "pareto_",
    "pi_",
    "mech_",
    "node_",
    "anim_",
    "oneclick_",
    "calib_",
    "csv_",
    "map_",
    # мелкие пользовательские флаги без префикса ui_
    "use_",
    "skip_",
    "auto_",
    "route_",
    "svg_",
    "road_",
    "drive_",
    "dask_",
    "algo_",
    "plot_",
    "warmstart_",
    "surrogate_",
    "stop_pen_",
    "sort_tests_",
    # diagnostics / send-bundle settings (must persist)
    "diag_",
)
# Префиксы, по которым ключи исключаются из сохранения (тяжёлое/кэш/результаты)
BLACKLIST_PREFIXES = (
    "_EV",
    "_autoselfcheck",
    # Иногда в session_state появляются большие объекты графиков
    "fig_",
    "trace_",
)

# Эфемерные ключи UI: их показываем пользователю, но НЕ переносим между перезапусками
BLACKLIST_EXACT_KEYS = {
    "ui_autosave_available",
    "ui_autosave_state_dir",
    "ui_autosave_loaded",
    "ui_autosave_loaded_ts",
    "ui_autosave_load_error",
    "ui_autosave_last_saved",
    "ui_autosave_last_path",
    "ui_autosave_last_error",
    "ui_reset_input_confirm",
    "df_params_signature",
    # runtime/session-derived paths and caches must never leak across release trees
    "anim_latest_pointer",
    "anim_latest_npz",
    "anim_latest_visual_cache_dependencies",
    "anim_latest_visual_reload_inputs",
    "anim_latest_visual_cache_token",
    "anim_latest_updated_utc",
    "baseline_cache_dir",
    "opt_progress_path",
    "svg_detail_cache",
    "svg_mapping_source",
    "osc_dir_path",
    "opt_run_dir",
    "opt_stop_file",
    "ui_model_path",
    "ui_worker_path",
}

PATHLIKE_KEY_TOKENS = (
    "_path",
    "_dir",
    "_file",
    "_json",
    "_pointer",
    "_cache",
    "_source",
    "dependencies",
)

# Ключи‑триггеры (кнопки/действия), которые **нельзя** сохранять между перезапусками,
# иначе возможны повторные срабатывания действий после autoload.
TRIGGER_PREFIXES = (
    "btn_",
    "run_",
    "apply_",
)

TRIGGER_EXACT_KEYS = {
    # кнопки "сохранить/сбросить"
    "ui_save_now",
    "ui_reset_input_yes",
    "ui_reset_input_no",
    # служебные
    "progress_autorefresh",

    # diagnostics triggers (must not persist between restarts)
    "diag_build_bundle",
    "btn_diag_build_bundle",
}

# Флаг в session_state: уже делали автозагрузку
AUTOLOAD_FLAG = "_ui_persist_autoload_done"


# -------------------------------
# Каталоги / пути
# -------------------------------

def _env_dir(key: str, default: Path) -> Path:
    v = (os.environ.get(key) or "").strip()
    if not v:
        return default
    try:
        return Path(v).expanduser().resolve()
    except Exception:
        return Path(v)


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    try:
        test = p / "._write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _project_root(app_here: Optional[Path] = None) -> Path:
    here = (app_here or Path(__file__).resolve().parent).resolve()
    if here.name == "pneumo_solver_ui":
        return here.parent.resolve()
    if (here / "pneumo_solver_ui").exists():
        return here.resolve()
    return here.resolve()


def _release_tag() -> str:
    rel = (os.environ.get("PNEUMO_RELEASE") or "").strip()
    m = re.search(r"\bv\d+_\d+\b", rel)
    return m.group(0) if m else "v6_80"


def _context_metadata(app_here: Optional[Path] = None) -> Dict[str, Any]:
    project_root = _project_root(app_here)
    try:
        workspace_root = workspace_state_dir(app_here).parent.resolve()
    except Exception:
        workspace_root = (project_root / "workspace").resolve()
    return {
        "_repo_root": str(project_root),
        "_workspace_root": str(workspace_root),
        "_release": str(os.environ.get("PNEUMO_RELEASE") or "").strip(),
    }


def _path_norm_for_compare(value: str) -> str:
    s = str(value or "").strip().replace('\\', '/')
    while '//' in s:
        s = s.replace('//', '/')
    return s.rstrip('/').lower()


def _looks_absolute_path(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = str(value or '').strip()
    if not s:
        return False
    if re.match(r'^[A-Za-z]:[\/]', s):
        return True
    if s.startswith('\\') or s.startswith('/'):
        return True
    return False


def _allowed_root_norms(app_here: Optional[Path] = None) -> list[str]:
    ctx = _context_metadata(app_here)
    roots = [ctx.get('_repo_root') or '', ctx.get('_workspace_root') or '']
    out: list[str] = []
    for raw in roots:
        norm = _path_norm_for_compare(str(raw))
        if norm and norm not in out:
            out.append(norm)
    return out


def _is_under_allowed_roots(path_value: str, allowed_roots: list[str]) -> bool:
    norm = _path_norm_for_compare(path_value)
    if not norm:
        return False
    for root in allowed_roots:
        if not root:
            continue
        if norm == root or norm.startswith(root + '/'):
            return True
    return False


def _contains_foreign_absolute_path(value: Any, allowed_roots: list[str]) -> bool:
    if isinstance(value, str):
        return _looks_absolute_path(value) and (not _is_under_allowed_roots(value, allowed_roots))
    if isinstance(value, dict):
        return any(_contains_foreign_absolute_path(sub, allowed_roots) for sub in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_foreign_absolute_path(sub, allowed_roots) for sub in value)
    return False


def _key_looks_pathlike(key: str) -> bool:
    k = str(key or '').strip().lower()
    return bool(k) and any(tok in k for tok in PATHLIKE_KEY_TOKENS)


def sanitize_loaded_state(data: Dict[str, Any], app_here: Optional[Path] = None) -> Dict[str, Any]:
    """Drop runtime/session-derived entries that point into foreign release trees."""
    if not isinstance(data, dict):
        return {}

    allowed_roots = _allowed_root_norms(app_here)
    current_ctx = _context_metadata(app_here)
    saved_repo = _path_norm_for_compare(str(data.get('_repo_root') or ''))
    saved_ws = _path_norm_for_compare(str(data.get('_workspace_root') or ''))
    cur_repo = _path_norm_for_compare(current_ctx.get('_repo_root') or '')
    cur_ws = _path_norm_for_compare(current_ctx.get('_workspace_root') or '')
    context_mismatch = bool((saved_repo and saved_repo != cur_repo) or (saved_ws and saved_ws != cur_ws))

    out: Dict[str, Any] = {}
    for k, v in data.items():
        if k in BLACKLIST_EXACT_KEYS:
            continue
        if k.startswith('_'):
            out[k] = v
            continue
        if not _should_persist_key(k):
            continue
        if _key_looks_pathlike(k) and _contains_foreign_absolute_path(v, allowed_roots):
            continue
        if context_mismatch and _contains_foreign_absolute_path(v, allowed_roots):
            continue
        out[k] = v
    return out


def pick_state_dir(app_here: Optional[Path] = None) -> Optional[Path]:
    """Выбрать папку для сохранения состояния.

    Windows-only / no-backward-compat policy for this project:
    1) explicit `PNEUMO_STATE_DIR` / `PNEUMO_UI_STATE_DIR`
    2) current launch workspace `workspace/ui_state`
    3) current repo-local `persistent_state/`

    Global AppData / home-level caches are intentionally NOT used by default,
    because they silently mix different unpacked releases and old absolute paths.
    """

    here = app_here or Path(__file__).resolve().parent

    # 1) explicit env
    v_state = (os.environ.get("PNEUMO_STATE_DIR") or os.environ.get("PNEUMO_UI_STATE_DIR") or "").strip()
    if v_state:
        try:
            p1 = Path(v_state).expanduser().resolve()
        except Exception:
            p1 = Path(v_state)
        if _is_writable_dir(p1):
            return p1

    # 2) session/project workspace mirror (source of truth for current unpacked tree)
    p_ws = workspace_state_dir(app_here=here)
    if _is_writable_dir(p_ws):
        return p_ws

    # 3) current repo-local persistent_state
    p_repo = _project_root(here) / "persistent_state"
    if _is_writable_dir(p_repo):
        return p_repo

    return None


def workspace_state_dir(app_here: Optional[Path] = None) -> Path:
    """Canonical workspace/ui_state directory for send-bundle reproducibility."""
    v_ws = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if v_ws:
        try:
            workspace = Path(v_ws).expanduser().resolve()
        except Exception:
            workspace = Path(v_ws)
    else:
        workspace = _project_root(app_here) / "workspace"
    return workspace / "ui_state"



def autosave_path(state_dir: Path) -> Path:
    return state_dir / "autosave_profile.json"


def autosave_backup_path(state_dir: Path) -> Path:
    return state_dir / "autosave_profile.bak.json"


def autosave_lock_path(state_dir: Path) -> Path:
    return state_dir / ".autosave_profile.lock"


# -------------------------------
# JSON encoding helpers
# -------------------------------

def _df_to_payload(df: pd.DataFrame) -> Dict[str, Any]:
    # Не сохраняем индекс (в UI он обычно не важен)
    recs = df.copy()
    recs = recs.where(pd.notnull(recs), None)  # NaN -> None
    return {
        "__type__": "dataframe",
        "columns": list(recs.columns),
        "records": recs.to_dict(orient="records"),
    }


def _payload_to_df(obj: Any) -> Optional[pd.DataFrame]:
    if not isinstance(obj, dict):
        return None
    if obj.get("__type__") != "dataframe":
        return None
    cols = obj.get("columns")
    recs = obj.get("records")
    if not isinstance(cols, list) or not isinstance(recs, list):
        return None
    try:
        df = pd.DataFrame(recs)
        df = df.reindex(columns=cols)
        return df
    except Exception:
        return None


def _jsonable(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, (bool, int, float, str)):
        return True
    if isinstance(v, (list, tuple)):
        return all(_jsonable(x) for x in v)
    if isinstance(v, dict):
        return all(isinstance(k, str) and _jsonable(x) for k, x in v.items())
    return False


def _stable_hash(obj: Any) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        s = repr(obj)
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

# -------------------------------
# Ограничения размера (предохранитель от сохранения мегабайт случайных данных)
# -------------------------------

_MAX_STR_LEN = 20_000
_MAX_LIST_LEN = 2_000
_MAX_DICT_KEYS = 2_000
_MAX_DF_ROWS = 5_000


def _is_reasonable_size(v: Any) -> bool:
    """Грубая оценка «не слишком ли большой объект для автосохранения».

    Нам нужно сохранять настройки пользователя, а не результаты расчётов.
    """
    try:
        if isinstance(v, str):
            return len(v) <= _MAX_STR_LEN
        if isinstance(v, (list, tuple)):
            return len(v) <= _MAX_LIST_LEN
        if isinstance(v, dict):
            return len(v.keys()) <= _MAX_DICT_KEYS
    except Exception:
        return False
    return True


# -------------------------------
# Фильтр ключей
# -------------------------------

def _should_persist_key(k: str) -> bool:
    if not isinstance(k, str):
        return False

    # 0) Явный blacklist (эфемерные статусы)
    if k in BLACKLIST_EXACT_KEYS:
        return False

    # 1) Не сохраняем кнопки/триггеры
    if k in TRIGGER_EXACT_KEYS:
        return False
    if k.endswith("_btn"):
        return False
    if k.startswith(TRIGGER_PREFIXES):
        return False

    # 2) Явные структурированные вводы
    if k in PERSIST_EXACT_KEYS:
        return True

    # 3) Тяжёлое/кэш/результаты
    if any(k.startswith(pref) for pref in BLACKLIST_PREFIXES):
        return False

    # 4) «Пользовательские» префиксы
    if k.startswith(PERSIST_PREFIXES):
        return True

    return False


# -------------------------------
# Сбор/применение состояния
# -------------------------------

def build_state_dict(session_state: Any) -> Dict[str, Any]:
    """Собрать состояние из st.session_state (без тяжёлых объектов)."""

    out: Dict[str, Any] = {
        "_schema": STATE_SCHEMA_VERSION,
        "_ts": time.time(),
    }
    out.update(_context_metadata(Path(__file__).resolve().parent))

    for k in list(session_state.keys()):
        if not _should_persist_key(k):
            continue

        v = session_state.get(k)

        # DataFrame (может быть большой — ограничиваем размер)
        if k in PERSIST_EXACT_KEYS and isinstance(v, pd.DataFrame):
            try:
                if len(v) <= _MAX_DF_ROWS:
                    out[k] = _df_to_payload(v)
                else:
                    out[k] = _df_to_payload(v.head(_MAX_DF_ROWS))
                    out[k]["__truncated__"] = True
                    out[k]["__truncated_rows__"] = int(len(v))
            except Exception:
                pass
            continue

        # Path
        if isinstance(v, Path):
            out[k] = str(v)
            continue

        # простые JSON значения (с предохранителем по размеру)
        if _jsonable(v) and _is_reasonable_size(v):
            out[k] = v
            continue

        # numpy / прочее — пропускаем

    return out


def apply_state_dict(session_state: Any, state: Dict[str, Any]) -> None:
    """Применить сохранённое состояние в st.session_state."""

    if not isinstance(state, dict):
        return

    for k, v in state.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_"):
            continue
        if not _should_persist_key(k):
            continue

        if isinstance(v, dict) and v.get("__type__") == "dataframe":
            df = _payload_to_df(v)
            if df is not None:
                session_state[k] = df
            continue

        try:
            session_state[k] = v
        except Exception:
            pass


# -------------------------------
# Файловая запись: lock + atomic replace + backup
# -------------------------------

def _try_acquire_lock(lock_path: Path, timeout_s: float = 1.0) -> bool:
    """Best‑effort lock через файл.

    Возвращает True, если lock взят. Если lock занят и не смогли дождаться — False.
    """

    t0 = time.time()
    while True:
        try:
            # O_EXCL гарантирует эксклюзивное создание
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"pid={os.getpid()} ts={time.time():.3f}".encode("utf-8"))
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            # stale lock?
            try:
                if lock_path.exists() and (time.time() - lock_path.stat().st_mtime) > 30:
                    lock_path.unlink(missing_ok=True)
                    continue
            except Exception:
                pass

            if (time.time() - t0) > timeout_s:
                return False
            time.sleep(0.05)
        except Exception:
            return False


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def load_autosave(state_dir: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Загрузить JSON автосохранения.

    Возвращает (data, err). err=None если всё ОК.

    При повреждении основного файла пробуем backup.
    """

    p = autosave_path(state_dir)
    if not p.exists():
        return None, None

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return sanitize_loaded_state(data, app_here=Path(__file__).resolve().parent), None
        return None, "autosave is not a dict"
    except Exception as e:
        err = repr(e)

        # Переименуем битый файл, чтобы не пытаться читать его снова
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            bad = p.with_name(f"{p.stem}.corrupt_{ts}{p.suffix}")
            p.rename(bad)
        except Exception:
            pass

        # Попробуем backup
        bak = autosave_backup_path(state_dir)
        if bak.exists():
            try:
                data = json.loads(bak.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return sanitize_loaded_state(data, app_here=Path(__file__).resolve().parent), f"{err} (загружен backup)"
            except Exception:
                pass

        return None, err


def save_autosave(state_dir: Path, state: Dict[str, Any]) -> Tuple[bool, str]:
    """Сохранить автосохранение атомарно.

    Возвращает (ok, info).
    info = путь (если ok) или текст ошибки.

    Дополнительно best-effort зеркалирует тот же JSON в canonical
    ``workspace/ui_state/autosave_profile.json``. Это не отдельное состояние,
    а точная копия primary autosave, чтобы send-bundle мог включить UI state
    даже если primary path живёт во внешнем per-user appdata.
    """

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    p = autosave_path(state_dir)
    bak = autosave_backup_path(state_dir)
    lock = autosave_lock_path(state_dir)

    if not _try_acquire_lock(lock, timeout_s=1.0):
        return False, "autosave lock busy"

    try:
        payload = json_dumps(state, indent=2)

        # резервная копия предыдущей версии
        try:
            if p.exists():
                shutil.copy2(p, bak)
        except Exception:
            # backup best-effort
            pass

        # атомарная запись через tmp в той же папке
        tmp = p.with_name(p.name + ".tmp")
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(str(tmp), str(p))
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

        # Canonical workspace mirror for bundle reproducibility.
        try:
            ws_dir = workspace_state_dir(app_here=Path(__file__).resolve().parent)
            mp = autosave_path(ws_dir)
            try:
                same_target = mp.resolve() == p.resolve()
            except Exception:
                same_target = False
            if not same_target:
                ws_dir.mkdir(parents=True, exist_ok=True)
                mtmp = mp.with_name(mp.name + ".tmp")
                try:
                    mtmp.write_text(payload, encoding="utf-8")
                    os.replace(str(mtmp), str(mp))
                finally:
                    try:
                        mtmp.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception:
            # Mirror is best-effort only; primary autosave is source of truth.
            pass

        return True, str(p)
    except Exception as e:
        return False, repr(e)
    finally:
        _release_lock(lock)


# -------------------------------
# Высокоуровневые функции для UI
# -------------------------------

def autoload_once(st_mod: Any, state_dir: Optional[Path] = None) -> None:
    """Автозагрузка состояния один раз на сессию Streamlit."""

    try:
        if st_mod.session_state.get(AUTOLOAD_FLAG):
            return
    except Exception:
        return

    sd = state_dir or pick_state_dir()
    if sd is None:
        # Нет writable папки — отключим автосохранение, но не ломаем UI
        try:
            st_mod.session_state[AUTOLOAD_FLAG] = True
            st_mod.session_state["ui_autosave_available"] = False
        except Exception:
            pass
        return

    try:
        st_mod.session_state["ui_autosave_available"] = True
        st_mod.session_state["ui_autosave_state_dir"] = str(sd)
        st_mod.session_state.setdefault("ui_autosave_enabled", True)
    except Exception:
        pass

    data, err = load_autosave(sd)
    if err:
        try:
            st_mod.session_state["ui_autosave_load_error"] = err
        except Exception:
            pass

    if data and isinstance(data, dict):
        try:
            apply_state_dict(st_mod.session_state, data)
            st_mod.session_state["ui_autosave_loaded"] = True
            st_mod.session_state["ui_autosave_loaded_ts"] = float(data.get("_ts") or 0.0)
        except Exception:
            pass

    try:
        st_mod.session_state[AUTOLOAD_FLAG] = True
    except Exception:
        pass


def autosave_if_enabled(st_mod: Any, state_dir: Optional[Path] = None) -> None:
    """Сохранить состояние (если включено)."""

    try:
        if not bool(st_mod.session_state.get("ui_autosave_enabled", True)):
            return
    except Exception:
        return

    sd = state_dir or pick_state_dir()
    if sd is None:
        return

    try:
        # Иногда важно сохранить изменения *сразу* (например после нажатия кнопки/submit),
        # иначе пользователь может обновить страницу раньше, чем сработает троттлинг,
        # и будет ощущение что "настройки пропали".
        #
        # Мы поддерживаем одноразовый bypass троттлинга через флаг в session_state.
        try:
            force_once = bool(st_mod.session_state.pop("_ui_autosave_force_once", False))
        except Exception:
            force_once = False

        # Throttle: JSON-сериализация DataFrame'ов может быть дорогой и вызывать "тормоза" UI.
        # По умолчанию сохраняем не чаще, чем раз в ~0.8 сек.
        try:
            throttle_s = float(os.environ.get("PNEUMO_AUTOSAVE_THROTTLE_S") or "0.8")
        except Exception:
            throttle_s = 0.8

        if (not force_once) and (throttle_s > 0):
            last_try = float(st_mod.session_state.get("_ui_autosave_last_try") or 0.0)
            now = time.time()
            if (now - last_try) < throttle_s:
                return
            st_mod.session_state["_ui_autosave_last_try"] = now
        else:
            # Даже при принудительном сохранении обновим таймстемп,
            # чтобы не спамить диск при частых событиях.
            try:
                st_mod.session_state["_ui_autosave_last_try"] = time.time()
            except Exception:
                pass

        state = build_state_dict(st_mod.session_state)
        h = _stable_hash(state)
        if st_mod.session_state.get("_ui_autosave_hash") == h:
            return

        ok, info = save_autosave(sd, state)
        if ok:
            st_mod.session_state["_ui_autosave_hash"] = h
            st_mod.session_state["ui_autosave_last_saved"] = time.time()
            st_mod.session_state["ui_autosave_last_path"] = info
            st_mod.session_state.pop("ui_autosave_last_error", None)
        else:
            # не спамим, но сохраним последнюю ошибку
            st_mod.session_state["ui_autosave_last_error"] = info
    except Exception:
        return


def force_autosave_next(st_mod: Any) -> None:
    """Запросить автосохранение на ближайшем autosave_if_enabled().

    Используется страницами UI после критичных изменений (например, сохранение suite/params),
    чтобы изменения гарантированно попали на диск в этом же rerun, даже если включён троттлинг.
    """

    try:
        st_mod.session_state["_ui_autosave_force_once"] = True
        # Сбросим таймер, чтобы старые ветки логики троттлинга не блокировали сохранение.
        st_mod.session_state["_ui_autosave_last_try"] = 0.0
    except Exception:
        pass




def autosave_now(st_mod: Any, state_dir: Optional[Path] = None) -> None:
    """Принудительно сохранить UI-состояние *сразу* (best effort).

    Важно: st.rerun() прерывает выполнение скрипта, поэтому autosave в конце страницы
    может не выполниться. Вызывайте autosave_now() перед st.rerun() после критичных изменений.
    """
    try:
        force_autosave_next(st_mod)
        autosave_if_enabled(st_mod, state_dir=state_dir)
    except Exception:
        return

# -----------------------------------------------------------------------------
# Backward-compat helpers (imported by diagnostics_unified / older pages)
# -----------------------------------------------------------------------------

def _extract_persistable_state(st_mod: Any) -> Dict[str, Any]:
    """Extract only the UI state that we consider safe to persist.

    NOTE: This function is intentionally lightweight and tolerant to failures.
    It is used by unified diagnostics to embed UI settings into the diagnostic bundle.
    """
    try:
        return build_state_dict(st_mod.session_state)
    except Exception:
        try:
            return dict(st_mod.session_state)
        except Exception:
            return {}


def load_ui_settings(state_dir: Optional[Path] = None) -> Tuple[bool, Any]:
    """Compatibility alias for older code: load persisted UI state."""
    sd = state_dir or pick_state_dir()
    if sd is None:
        return False, "no_state_dir"
    return load_autosave(sd)


def save_ui_settings(state: Dict[str, Any], state_dir: Optional[Path] = None) -> Tuple[bool, Any]:
    """Compatibility alias for older code: save persisted UI state."""
    sd = state_dir or pick_state_dir()
    if sd is None:
        return False, "no_state_dir"
    return save_autosave(sd, state)
