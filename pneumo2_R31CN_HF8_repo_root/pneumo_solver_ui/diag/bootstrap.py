# -*- coding: utf-8 -*-
"""pneumo_solver_ui.diag.bootstrap

Глобальные хуки для "ничего не теряется в логах":

1) ModuleNotFoundError / ImportError:
   - перехватываем builtins.__import__
   - логируем событие (dedup/throttle)
   - затем пробрасываем исключение дальше (поведение не меняем)

2) warnings:
   - перехватываем warnings.showwarning
   - логируем как событие (dedup/throttle)
   - по желанию можно показывать стандартный вывод

3) logging:
   - добавляем файловый handler на root-логгер (best-effort),
     чтобы сообщения streamlit/библиотек попадали в файл.

Использование:
  - app.py/desktop_animator/main.py вызывает bootstrap(app_name)
  - инструменты/CLI могут вызывать init_nonstreamlit() (внутренний alias)

Важно: Этот код должен быть максимально "лёгким" и не зависеть от сторонних пакетов.
"""

from __future__ import annotations

import builtins
import logging
import os
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .eventlog import get_global_logger

_INSTALLED = False

# keep original hooks
_ORIG_IMPORT: Optional[Callable[..., Any]] = None
_ORIG_SHOWWARNING: Optional[Callable[..., Any]] = None

# simple throttling
_SEEN: Dict[str, int] = {}
_MAX_SEEN = 4000

# POSIX-only stdlib modules are often imported in try/except blocks and are absent on Windows.
# Do not log them as errors to avoid noisy diagnostics.
_OPTIONAL_MISSING_ON_WINDOWS = {"fcntl", "pwd", "grp", "termios", "resource"}

# Optional scientific / thermo packages frequently probed by upstream stacks.
# They are not required for the default UI/runtime flows, so repeated import-hook
# events would only bury real faults in logs. We still emit a dedicated low-noise
# event, but no longer spam the generic ModuleNotFoundError channel.
_OPTIONAL_MISSING_GENERIC = {
    "CoolProp",
    "bottleneck",
    "cuda",
    "cython",
    "qdarktheme",
    "scikits",
    "sksparse",
    "uarray",
    "xarray",
}


def _project_root_from_here() -> Path:
    # .../pneumo_solver_ui/diag/bootstrap.py -> parents[2] is repo root
    return Path(__file__).resolve().parents[2]


def _key(event: str, msg: str, extra: str = "") -> str:
    s = f"{event}|{msg}|{extra}"
    if len(s) > 500:
        s = s[:500]
    return s


def _should_log(key: str, every: int = 20) -> Tuple[bool, int]:
    """Return (do_log, count). Logs first time and then each Nth repeat."""
    c = _SEEN.get(key, 0) + 1
    _SEEN[key] = c
    # prevent unbounded growth
    if len(_SEEN) > _MAX_SEEN:
        # drop some old keys (cheap)
        for k in list(_SEEN.keys())[: int(_MAX_SEEN * 0.2)]:
            _SEEN.pop(k, None)
    if c == 1:
        return True, c
    if every > 0 and (c % every == 0):
        return True, c
    return False, c


def _install_root_logger_filehandler(project_root: Path) -> None:
    """Attach a file handler to root logger so that Streamlit/library logs are persisted."""
    try:
        log_dir = project_root / "pneumo_solver_ui" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "python_root.log"

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # already attached?
        for h in list(root_logger.handlers):
            try:
                if isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")).resolve() == path.resolve():
                    return
            except Exception:
                continue

        fh = logging.FileHandler(path, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fmt)
        fh.setLevel(logging.INFO)
        root_logger.addHandler(fh)
    except Exception:
        # best-effort, never crash
        return


def _install_import_hook(project_root: Path) -> None:
    global _ORIG_IMPORT
    if _ORIG_IMPORT is not None:
        return

    ev = get_global_logger(project_root)
    _ORIG_IMPORT = builtins.__import__

    def _wrapped_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):  # type: ignore[override]
        try:
            return _ORIG_IMPORT(name, globals, locals, fromlist, level)  # type: ignore[misc]
        except ModuleNotFoundError as e:
            # Mandatory event in logs
            msg = repr(e)
            extra = getattr(e, "name", "") or name
            mod_root = str(extra).split(".")[0]
            if os.name == "nt" and mod_root in _OPTIONAL_MISSING_ON_WINDOWS:
                raise
            if mod_root in _OPTIONAL_MISSING_GENERIC:
                k = _key("OptionalModuleMissing", msg, extra)
                do_log, cnt = _should_log(k, every=100)
                if do_log:
                    ev.emit(
                        "OptionalModuleMissing",
                        msg,
                        module=str(extra),
                        import_name=str(name),
                        fromlist=list(fromlist) if fromlist else [],
                        level=int(level),
                        count=int(cnt),
                    )
                raise
            k = _key("ModuleNotFoundError", msg, extra)
            do_log, cnt = _should_log(k, every=10)
            if do_log:
                ev.emit(
                    "ModuleNotFoundError",
                    msg,
                    module=str(extra),
                    import_name=str(name),
                    fromlist=list(fromlist) if fromlist else [],
                    level=int(level),
                    count=int(cnt),
                    traceback=str(traceback.format_exc()),
                )
            raise
        except ImportError as e:
            # Also useful (cannot import name / DLL load failure, etc.)
            msg = repr(e)
            k = _key("ImportError", msg, name)
            do_log, cnt = _should_log(k, every=20)
            if do_log:
                ev.emit(
                    "ImportError",
                    msg,
                    import_name=str(name),
                    fromlist=list(fromlist) if fromlist else [],
                    level=int(level),
                    count=int(cnt),
                    traceback=str(traceback.format_exc()),
                )
            raise
        except Exception as e:
            # don't log all exceptions here (too noisy), but keep a safety net
            msg = repr(e)
            k = _key("ImportException", msg, name)
            do_log, cnt = _should_log(k, every=50)
            if do_log:
                ev.emit(
                    "ImportException",
                    msg,
                    import_name=str(name),
                    count=int(cnt),
                )
            raise

    builtins.__import__ = _wrapped_import  # type: ignore[assignment]


def _install_warning_hook(project_root: Path) -> None:
    global _ORIG_SHOWWARNING
    if _ORIG_SHOWWARNING is not None:
        return

    ev = get_global_logger(project_root)
    _ORIG_SHOWWARNING = warnings.showwarning

    def _wrapped_showwarning(message, category, filename, lineno, file=None, line=None):  # type: ignore[override]
        try:
            msg = str(message)
            cat = getattr(category, "__name__", str(category))
            key = _key("Warning", f"{cat}:{msg}", filename)
            do_log, cnt = _should_log(key, every=20)
            if do_log:
                ev.emit(
                    "Warning",
                    msg,
                    category=str(cat),
                    filename=str(filename),
                    lineno=int(lineno),
                    count=int(cnt),
                )
        except Exception:
            pass
        # By default: do NOT spam console/UI with warnings. We log them into events.jsonl.
        # If you need stderr warnings too, set PNEUMO_DIAG_ECHO_WARNINGS=1.
        if str(os.environ.get("PNEUMO_DIAG_ECHO_WARNINGS", "0")).lower() in ("1", "true", "yes", "y"):
            try:
                return _ORIG_SHOWWARNING(message, category, filename, lineno, file=file, line=line)  # type: ignore[misc]
            except Exception:
                return None
        return None

    warnings.showwarning = _wrapped_showwarning  # type: ignore[assignment]
    # Make sure warnings are not suppressed
    try:
        warnings.simplefilter("default")
    except Exception:
        pass


def bootstrap(app_name: str = "") -> None:
    """Canonical bootstrap entrypoint.

    Must be called as early as possible from any entrypoint (Streamlit or CLI).
    Installs import/warning hooks + root logger file handler.

    ABSOLUTE LAW:
      - Мы НЕ "додумываем" данные модели и НЕ вводим новые параметры данных.
      - Здесь только диагностика/логирование ошибок окружения и импорта.
      - Любая аномалия должна быть залогирована (но приложение не должно падать из‑за логгера).

    Args:
        app_name: Optional tag written to events.jsonl to trace which entrypoint booted.
    """
    init_streamlit_app()
    if app_name:
        try:
            project_root = _project_root_from_here()
            ev = get_global_logger(project_root)
            ev.emit(
                "BootstrapApp",
                "bootstrap",
                app=str(app_name),
                pid=os.getpid(),
                executable=sys.executable,
            )
        except Exception:
            # best-effort only
            pass


def init_streamlit_app() -> None:
    """Call early from app.py (Streamlit process)."""
    global _INSTALLED
    if _INSTALLED:
        return
    project_root = _project_root_from_here()

    # ensure import root
    try:
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
    except Exception:
        pass

    _install_root_logger_filehandler(project_root)
    _install_warning_hook(project_root)
    _install_import_hook(project_root)

    # record boot event
    try:
        ev = get_global_logger(project_root)
        ev.emit(
            "Bootstrap",
            "init_streamlit_app",
            pid=os.getpid(),
            executable=sys.executable,
            cwd=os.getcwd(),
        )
    except Exception:
        pass

    _INSTALLED = True


def init_nonstreamlit() -> None:
    """Call from CLI tools / launcher when Streamlit is not running."""
    init_streamlit_app()


def log_exception(context: str, exc: BaseException) -> None:
    """Best-effort exception logging for try/except blocks."""
    try:
        project_root = _project_root_from_here()
        ev = get_global_logger(project_root)
        ev.emit(
            "Exception",
            f"{context}: {exc!r}",
            context=str(context),
            traceback=str(traceback.format_exc()),
        )
    except Exception:
        pass
