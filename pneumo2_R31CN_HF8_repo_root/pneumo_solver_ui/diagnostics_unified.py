# -*- coding: utf-8 -*-
"""pneumo_solver_ui.diagnostics_unified

Единая точка сборки *полной* диагностической информации.

Ключевая цель (из требований к UI):
- в интерфейсе должна быть **одна** понятная кнопка «Сохранить диагностику (ZIP)»;
- при падении (Unhandled exception) должен быть best‑effort автосейв диагностики на диск.

Что считаем «полной диагностикой»
---------------------------------
- пользовательские/изменённые артефакты (workspace, runs, calibration_runs и т.п.);
- результаты расчётов/оптимизаций/валидаций (если они лежат в workspace/runs);
- логи UI и системные логи;
- снимок окружения (Python/OS/пакеты) + манифест;
- runtime snapshot (процесс, память/CPU — best‑effort);
- снимок введённых значений UI (persistable state).

Реализация
----------
Мы используем существующий упаковщик `pneumo_solver_ui/tools/make_send_bundle.py`.
Он уже умеет собирать ZIP по структуре проекта, делать env‑snapshot и писать манифест.
В эту обвязку мы добавляем 2 файла‑снимка в logs/ перед упаковкой:
- ui_state_snapshot_*.json
- runtime_snapshot_*.json

Best‑effort: любые ошибки диагностики не должны «ронять» приложение.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class UnifiedDiagResult:
    ok: bool
    zip_path: Optional[Path] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# --- Defaults / tuning ---

_DEFAULT_KEEP_LAST_N = 3

# Пользователь просит «всю диагностику»; max_file_mb делаем больше дефолтных 80MB.
_DEFAULT_MAX_FILE_MB = 200

# Защита от «циклического падения» (не плодить десятки ZIP подряд)
_CRASH_MIN_INTERVAL_S = 120.0


def _repo_root_from_here() -> Path:
    # .../<repo>/pneumo_solver_ui/diagnostics_unified.py -> parents[1] == <repo>
    return Path(__file__).resolve().parents[1]


def _logs_dir(repo_root: Path) -> Path:
    p = (os.environ.get("PNEUMO_LOG_DIR") or "").strip()
    if p:
        try:
            return Path(p).expanduser().resolve()
        except Exception:
            return Path(p)
    return (repo_root / "pneumo_solver_ui" / "logs").resolve()


def _bundles_dir(repo_root: Path) -> Path:
    # исторически make_send_bundle кладёт сюда
    return (repo_root / "send_bundles").resolve()


def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _safe_json_dumps(obj: Any) -> str:
    # Prefer project strict json to avoid NaN/Inf.
    try:
        from pneumo_solver_ui.diag.json_safe import json_dumps

        return json_dumps(obj)
    except Exception:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str, allow_nan=False)


def _atomic_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8", errors="replace")
        try:
            os.replace(str(tmp), str(path))
        except Exception:
            # fallback
            path.write_text(text, encoding="utf-8", errors="replace")
            try:
                tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
    except Exception:
        return


def _try_open_folder(folder: Path) -> bool:
    """Best-effort: открыть папку с результатом (для удобства человека)."""
    try:
        folder = folder.expanduser().resolve()
    except Exception:
        pass

    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        # linux
        import subprocess

        subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _collect_persistable_state(st_mod: Any) -> Dict[str, Any]:
    """Берём только то, что действительно нужно восстановить/проанализировать."""
    try:
        from pneumo_solver_ui.ui_persistence import _extract_persistable_state

        return _extract_persistable_state(getattr(st_mod, "session_state", {}))
    except Exception:
        ss = getattr(st_mod, "session_state", {})
        out: Dict[str, Any] = {}
        try:
            for k, v in dict(ss).items():
                try:
                    json.dumps(v, ensure_ascii=False, allow_nan=False)
                    out[str(k)] = v
                except Exception:
                    out[str(k)] = {"__type__": str(type(v)), "__repr__": (repr(v)[:500] + "…")}
        except Exception:
            pass
        return out


def write_ui_state_snapshot(
    repo_root: Optional[Path] = None,
    *,
    st_mod: Optional[Any] = None,
    reason: str = "manual",
) -> Optional[Path]:
    """Сохраняет снимок введённых значений UI (persistable state) в logs/.

    Возвращает путь к созданному файлу (или None).
    """
    if st_mod is None:
        return None

    try:
        repo_root = (repo_root or _repo_root_from_here()).resolve()
        logs = _logs_dir(repo_root)
        logs.mkdir(parents=True, exist_ok=True)

        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": str(reason),
            "app": "pneumo_solver_ui",
            "persistable_state": _collect_persistable_state(st_mod),
        }

        # Дополнительно: список ключей (для отладки)
        try:
            payload["session_state_keys"] = sorted([str(k) for k in getattr(st_mod, "session_state", {}).keys()])
        except Exception:
            pass

        p = logs / f"ui_state_snapshot_{reason}_{_now_stamp()}.json"
        _atomic_write_text(p, _safe_json_dumps(payload))

        latest = logs / "latest_ui_state_snapshot.json"
        _atomic_write_text(latest, _safe_json_dumps(payload))

        return p
    except Exception:
        return None


def write_runtime_snapshot(repo_root: Optional[Path] = None, *, reason: str = "manual") -> Optional[Path]:
    """Сохраняет runtime snapshot (мониторинг) в logs/."""
    try:
        repo_root = (repo_root or _repo_root_from_here()).resolve()
        logs = _logs_dir(repo_root)
        logs.mkdir(parents=True, exist_ok=True)

        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": str(reason),
            "platform": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "pid": os.getpid(),
            "cwd": os.getcwd(),
        }

        # psutil (если есть)
        try:
            import psutil  # type: ignore

            p = psutil.Process(os.getpid())
            payload["psutil"] = {
                "cpu_percent": float(p.cpu_percent(interval=0.0)),
                "num_threads": int(p.num_threads()),
                "memory_rss": int(getattr(p.memory_info(), "rss", 0) or 0),
                "memory_vms": int(getattr(p.memory_info(), "vms", 0) or 0),
            }
        except Exception:
            pass

        # env — только «наши» переменные, без утечек
        try:
            env = {k: str(v) for k, v in os.environ.items() if k.startswith("PNEUMO_")}
            if env:
                payload["env_pneumo"] = env
        except Exception:
            pass

        pth = logs / f"runtime_snapshot_{reason}_{_now_stamp()}.json"
        _atomic_write_text(pth, _safe_json_dumps(payload))
        return pth
    except Exception:
        return None


def build_unified_diagnostics(
    repo_root: Optional[Path] = None,
    *,
    st_mod: Optional[Any] = None,
    reason: str = "manual",
    open_folder: bool = True,
    keep_last_n: Optional[int] = None,
    max_file_mb: Optional[int] = None,
    include_workspace_osc: Optional[bool] = None,
) -> UnifiedDiagResult:
    """Собирает диагностический ZIP на диск (send_bundles/) и возвращает результат."""

    repo_root = (repo_root or _repo_root_from_here()).resolve()

    # 1) snapshots
    if st_mod is not None:
        write_ui_state_snapshot(repo_root, st_mod=st_mod, reason=reason)
    write_runtime_snapshot(repo_root, reason=reason)

    out_dir = _bundles_dir(repo_root)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    keep_last_n = int(
        keep_last_n
        if keep_last_n is not None
        else int(os.environ.get("PNEUMO_SEND_BUNDLE_KEEP_LAST_N", str(_DEFAULT_KEEP_LAST_N)) or _DEFAULT_KEEP_LAST_N)
    )
    max_file_mb = int(
        max_file_mb
        if max_file_mb is not None
        else int(os.environ.get("PNEUMO_SEND_BUNDLE_MAX_FILE_MB", str(_DEFAULT_MAX_FILE_MB)) or _DEFAULT_MAX_FILE_MB)
    )

    if include_workspace_osc is None:
        include_workspace_osc = str(os.environ.get("PNEUMO_SEND_BUNDLE_INCLUDE_OSC", "0")).strip() == "1"

    primary_session_dir: Optional[Path] = None

    # 1) явный путь (если пользователь/пакет сборки его выставил)
    try:
        psd = (os.environ.get("PNEUMO_UI_SESSION_DIR") or "").strip()
        if psd:
            primary_session_dir = Path(psd).expanduser().resolve()
    except Exception:
        primary_session_dir = None

    # 2) fallback: основной каталог UI-состояния (там лежит autosave_profile.json)
    if primary_session_dir is None:
        try:
            from pneumo_solver_ui.ui_persistence import pick_state_dir

            sd = pick_state_dir(app_here=(repo_root / "pneumo_solver_ui"))
            if sd is not None:
                primary_session_dir = Path(sd).expanduser().resolve()
                os.environ.setdefault("PNEUMO_UI_SESSION_DIR", str(primary_session_dir))
        except Exception:
            primary_session_dir = None

    try:
        from pneumo_solver_ui.tools.make_send_bundle import make_send_bundle

        zpath = make_send_bundle(
            repo_root=repo_root,
            out_dir=out_dir,
            keep_last_n=keep_last_n,
            max_file_mb=max_file_mb,
            include_workspace_osc=bool(include_workspace_osc),
            primary_session_dir=primary_session_dir,
        )

        # event log (не критично)
        try:
            from pneumo_solver_ui.diag.eventlog import EventLogger

            EventLogger(repo_root).emit(
                "ui.diagnostics.bundle_built",
                message="Unified diagnostics bundle built",
                reason=str(reason),
                zip_path=str(zpath),
                keep_last_n=int(keep_last_n),
                max_file_mb=int(max_file_mb),
                include_workspace_osc=bool(include_workspace_osc),
            )
        except Exception:
            pass

        if open_folder:
            _try_open_folder(Path(zpath).parent)

        return UnifiedDiagResult(ok=True, zip_path=Path(zpath), message="OK")

    except Exception as e:
        try:
            from pneumo_solver_ui.diag.eventlog import EventLogger

            EventLogger(repo_root).emit(
                "ui.diagnostics.bundle_failed",
                message=str(e),
                reason=str(reason),
                traceback=traceback.format_exc(limit=30),
            )
        except Exception:
            pass

        return UnifiedDiagResult(ok=False, zip_path=None, message=str(e), details={"traceback": traceback.format_exc()})


def _last_crash_meta_path(repo_root: Path) -> Path:
    return _logs_dir(repo_root) / "last_crash_bundle.json"


def _read_last_crash_meta(repo_root: Path) -> Dict[str, Any]:
    try:
        p = _last_crash_meta_path(repo_root)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return {}


def _write_last_crash_meta(repo_root: Path, meta: Dict[str, Any]) -> None:
    try:
        _atomic_write_text(_last_crash_meta_path(repo_root), _safe_json_dumps(meta))
    except Exception:
        return


def autosave_diagnostics_on_exception(
    repo_root: Optional[Path] = None,
    *,
    st_mod: Optional[Any] = None,
    where: str = "unknown",
    exc: Optional[BaseException] = None,
    min_interval_s: float = _CRASH_MIN_INTERVAL_S,
) -> UnifiedDiagResult:
    """Best-effort автосейв диагностики при краше.

    Делает:
    - пишет traceback в logs/
    - пишет ui_state + runtime snapshot
    - собирает send-bundle в send_bundles/

    Чтобы не плодить ZIP при циклических падениях, есть троттлинг.
    """

    repo_root = (repo_root or _repo_root_from_here()).resolve()

    tb = traceback.format_exc()
    if exc is not None:
        tb = tb or "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    h = hashlib.sha256(tb.encode("utf-8", errors="replace")).hexdigest()[:16]

    last = _read_last_crash_meta(repo_root)
    try:
        last_hash = str(last.get("hash") or "")
        last_ts = float(last.get("ts_epoch") or 0.0)
        last_zip = str(last.get("zip_path") or "")
        if last_hash == h and (time.time() - last_ts) < float(min_interval_s):
            zp = Path(last_zip) if last_zip else None
            return UnifiedDiagResult(
                ok=bool(zp and zp.exists()),
                zip_path=zp if (zp and zp.exists()) else None,
                message="throttled",
                details={"hash": h, "where": where},
            )
    except Exception:
        pass

    # 1) записать traceback
    try:
        logs = _logs_dir(repo_root)
        logs.mkdir(parents=True, exist_ok=True)
        tb_path = logs / f"crash_trace_{where}_{_now_stamp()}.txt"
        _atomic_write_text(tb_path, tb)
    except Exception:
        tb_path = None  # type: ignore

    # 2) собрать ZIP
    res = build_unified_diagnostics(repo_root, st_mod=st_mod, reason=f"crash_{where}", open_folder=False)

    # 3) meta
    meta = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ts_epoch": float(time.time()),
        "where": str(where),
        "hash": str(h),
        "zip_path": str(res.zip_path) if res.zip_path else "",
        "traceback_path": str(tb_path) if tb_path else "",
        "ok": bool(res.ok),
    }
    _write_last_crash_meta(repo_root, meta)

    return res


# --- Public wrappers for app.py (backward-compatible API) ---

def build_unified_diagnostics_bundle(
    repo_root: Optional[Path] = None,
    *,
    st_mod=None,
    reason: str = "manual",
    include_workspace_osc: bool = False,
) -> UnifiedDiagResult:
    """Alias for build_unified_diagnostics.

    app.py historically imported this name. Keep it to avoid breaking UI.
    """
    return build_unified_diagnostics(
        repo_root=repo_root,
        st_mod=st_mod,
        reason=reason,
        include_workspace_osc=include_workspace_osc,
    )


def find_latest_bundle(repo_root: Optional[Path] = None) -> Optional[Path]:
    """Return latest diagnostics bundle (*.zip) from send_bundles directory."""
    try:
        if repo_root is None:
            repo_root = _repo_root_from_here()
        out_dir = Path(repo_root) / "send_bundles"
        if not out_dir.exists():
            return None
        zips = sorted(out_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        return zips[0] if zips else None
    except Exception:
        return None


def reveal_in_file_manager(path: Path) -> bool:
    """Try to open file location in OS file manager."""
    try:
        if path is None:
            return False
        return _try_open_folder(Path(path))
    except Exception:
        return False


def install_streamlit_uncaught_exception_hook(
    *,
    st_mod=None,
    repo_root: Optional[Path] = None,
    where: str = "streamlit_uncaught",
) -> bool:
    """Best-effort hook: autosave unified diagnostics on uncaught Streamlit exceptions.

    Why: Streamlit handles exceptions internally before they reach sys.excepthook.
    Поэтому для автосохранения диагностики на «краше» нужен прямой хук на
    error_util.handle_uncaught_app_exception.

    This is best-effort and intentionally tolerant to Streamlit version drift.
    """
    try:
        import streamlit.error_util as error_util
    except Exception:
        return False

    try:
        if getattr(error_util, "_pneumo_diag_hook_installed", False):
            return True
    except Exception:
        pass

    try:
        orig = getattr(error_util, "handle_uncaught_app_exception")
    except Exception:
        return False

    def _wrapped(exc, *args, **kwargs):
        # Не считаем «крашем» управляемые исключения Streamlit.
        try:
            n = getattr(exc, "__class__", type(exc)).__name__
            if n in {"StopException", "RerunException"}:
                return orig(exc, *args, **kwargs)
        except Exception:
            pass

        try:
            autosave_diagnostics_on_exception(
                repo_root=repo_root,
                st_mod=st_mod,
                where=where,
                exc=exc,
            )
        except Exception:
            pass

        return orig(exc, *args, **kwargs)

    try:
        setattr(error_util, "handle_uncaught_app_exception", _wrapped)
        setattr(error_util, "_pneumo_diag_hook_installed", True)
        return True
    except Exception:
        return False
