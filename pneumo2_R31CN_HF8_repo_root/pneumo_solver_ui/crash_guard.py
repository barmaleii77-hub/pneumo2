# -*- coding: utf-8 -*-
"""pneumo_solver_ui.crash_guard (Testy R56)

Набор "страхующих" хуков, чтобы *не терять* аварийные исключения.

Что делает
----------
- включает faulthandler (дамп traceback при фатальных ошибках/сигналах)
- ставит sys.excepthook для main-thread исключений
- ставит threading.excepthook (Python 3.8+) для исключений из потоков
- ставит sys.unraisablehook (Python 3.8+) для "unraisable" (в __del__ и т.п.)

Все действия best-effort: если что-то не получилось — не мешаем приложению.

Логи
----
Пишем в PNEUMO_LOG_DIR (если задан), иначе в <repo>/pneumo_solver_ui/logs.

"""

from __future__ import annotations

import os
import sys
import atexit
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_INSTALLED = False
_ATEXIT_INSTALLED = False
_PROJECT_ROOT_OVERRIDE: Optional[Path] = None
_EXTRA_META: Dict[str, Any] = {}
_ORIG_SYS_HOOK = None
_ORIG_THREAD_HOOK = None
_ORIG_UNRAISABLE_HOOK = None
_FAULT_FH = None

try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "PneumoApp_v6_80_R168") or "PneumoApp_v6_80_R168"

# --------------------
# Autosave toggles + params (env-driven)
# --------------------

def _env_flag(name: str, default: bool) -> bool:
    """Parse boolean env flag.

    Accepted false: 0, false, no, off, empty
    Anything else -> True.
    """
    v = os.environ.get(name)
    if v is None:
        return default
    s = str(v).strip().lower()
    return s not in ('0', 'false', 'no', 'off', '')


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


def _auto_send_bundle_enabled() -> bool:
    # Legacy master switch: default enabled unless explicitly disabled
    return _env_flag('PNEUMO_AUTO_SEND_BUNDLE', True)


def _load_diag_cfg() -> Any:
    """Best-effort load diagnostics settings from persistent_state.

    Must not raise.
    """
    try:
        from pneumo_solver_ui.diagnostics_entrypoint import load_diagnostics_config

        return load_diagnostics_config(_repo_root())
    except Exception:
        return None


def _cfg_to_session_override(cfg: Any, *, tag_override: Optional[str] = None) -> Dict[str, Any]:
    """Convert DiagnosticsConfig -> dict compatible with diagnostics_entrypoint loader."""
    d: Dict[str, Any] = {}
    try:
        d["diag_output_dir"] = str(getattr(cfg, "out_dir", "send_bundles"))
        d["diag_keep_last_n"] = int(getattr(cfg, "keep_last_n", 10))
        d["diag_max_file_mb"] = int(getattr(cfg, "max_file_mb", 200))
        d["diag_include_workspace_osc"] = bool(getattr(cfg, "include_workspace_osc", False))
        d["diag_run_selfcheck"] = bool(getattr(cfg, "run_selfcheck_before_bundle", True))
        d["diag_selfcheck_level"] = str(getattr(cfg, "selfcheck_level", "standard"))
        d["diag_autosave_on_crash"] = bool(getattr(cfg, "autosave_on_crash", True))
        d["diag_autosave_on_exit"] = bool(getattr(cfg, "autosave_on_exit", True))
        d["diag_autosave_on_watchdog"] = bool(getattr(cfg, "autosave_on_watchdog", True))
        d["diag_reason"] = str(getattr(cfg, "reason", ""))
        if tag_override is not None:
            d["diag_tag"] = str(tag_override)
        else:
            d["diag_tag"] = str(getattr(cfg, "tag", ""))
    except Exception:
        pass
    return d


def should_autosave_on_crash() -> bool:
    if not _auto_send_bundle_enabled():
        return False
    cfg = _load_diag_cfg()
    if cfg is not None:
        try:
            return bool(getattr(cfg, "autosave_on_crash", True))
        except Exception:
            pass
    return _env_flag('PNEUMO_AUTOSAVE_BUNDLE_ON_CRASH', True)


def should_autosave_on_exit() -> bool:
    if not _auto_send_bundle_enabled():
        return False
    cfg = _load_diag_cfg()
    if cfg is not None:
        try:
            return bool(getattr(cfg, "autosave_on_exit", True))
        except Exception:
            pass
    # Default: enabled (R59 requires exit autosave path)
    return _env_flag('PNEUMO_AUTOSAVE_BUNDLE_ON_EXIT', True)


def _bundle_params_from_env() -> tuple[int, float, bool, str]:
    """Return (keep_last_n, max_file_mb, include_workspace, tag_suffix)."""
    keep_last_n = _env_int('PNEUMO_BUNDLE_KEEP_LAST_N', 50)
    max_file_mb = _env_float('PNEUMO_BUNDLE_MAX_FILE_MB', 80.0)
    include_workspace = _env_flag('PNEUMO_BUNDLE_INCLUDE_WORKSPACE', True)
    tag_suffix = str(os.environ.get('PNEUMO_BUNDLE_TAG_SUFFIX', '')).strip()
    return keep_last_n, max_file_mb, include_workspace, tag_suffix
import logging

logger = logging.getLogger(__name__)


def _bundle_summary_event_fields(res: Any) -> Dict[str, Any]:
    meta = dict(getattr(res, "meta", {}) or {})
    lines = [str(x) for x in (meta.get("summary_lines") or []) if str(x).strip()]
    fields: Dict[str, Any] = {
        "bundle_ok": bool(getattr(res, "ok", False)),
        "zip_path": str(getattr(res, "zip_path", "") or ""),
        "summary_lines": lines,
    }
    diag_path = str(meta.get("anim_pointer_diagnostics_path") or "").strip()
    if diag_path:
        fields["anim_pointer_diagnostics_path"] = diag_path
    return fields


def _emit_bundle_summary_event(event_name: str, *, where: str, res: Any) -> None:
    try:
        _event(
            event_name,
            f"autosave bundle {where}",
            where=str(where),
            **_bundle_summary_event_fields(res),
        )
    except Exception:
        pass


def _auto_bundle_on_crash(where: str = "crash", exc: Exception | None = None) -> Path | None:
    """Autosave a diagnostic bundle on crash.

    Controlled by env vars:
      - PNEUMO_AUTO_SEND_BUNDLE (legacy master, default 1)
      - PNEUMO_AUTOSAVE_BUNDLE_ON_CRASH (default 1)
      - PNEUMO_BUNDLE_KEEP_LAST_N (default 50)
      - PNEUMO_BUNDLE_MAX_FILE_MB (default 80)
      - PNEUMO_BUNDLE_INCLUDE_WORKSPACE (default 1)
      - PNEUMO_BUNDLE_TAG_SUFFIX (optional)
    """
    if not should_autosave_on_crash():
        return None

    try:
        from pneumo_solver_ui.diagnostics_entrypoint import build_full_diagnostics_bundle

        cfg = _load_diag_cfg()
        ss_override = None
        if cfg is not None:
            user_tag = str(getattr(cfg, "tag", "") or "").strip()
            auto_tag = f"auto-{where}" + (f"_{user_tag}" if user_tag else "")
            ss_override = _cfg_to_session_override(cfg, tag_override=auto_tag)

        res = build_full_diagnostics_bundle(
            trigger=f"auto-{where}",
            repo_root=_repo_root(),
            session_state=ss_override,
            open_folder=False,
        )
        _emit_bundle_summary_event("autosave_bundle_on_crash", where=where, res=res)
        if res.ok and res.zip_path:
            return Path(res.zip_path)
        raise RuntimeError(res.message or "bundle build failed")
    except Exception:
        print("[crash_guard] Failed to autosave diagnostic bundle", file=sys.stderr)
        if exc is not None:
            print(f"[crash_guard] original exception: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return None

def _repo_root() -> Path:
    global _PROJECT_ROOT_OVERRIDE
    if _PROJECT_ROOT_OVERRIDE is not None:
        return _PROJECT_ROOT_OVERRIDE
    return Path(__file__).resolve().parents[1]


def _default_log_dir() -> Path:
    # prefer session log dir
    p = os.environ.get("PNEUMO_LOG_DIR")
    if p:
        try:
            return Path(p).resolve()
        except Exception:
            pass
    return (_repo_root() / "pneumo_solver_ui" / "logs").resolve()


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(text.rstrip() + "\n")
    except Exception:
        pass


def _event(event: str, message: str = "", **fields: Any) -> None:
    """Send event to diag.eventlog if available, else to text file."""
    try:
        from pneumo_solver_ui.diag.eventlog import get_global_logger

        logger = get_global_logger(_repo_root())
        logger.emit(event, message, **fields)
        return
    except Exception:
        pass

    # fallback
    try:
        log_dir = _default_log_dir()
        _safe_write_text(log_dir / "crash_guard.log", f"[{event}] {message} {fields}")
    except Exception:
        pass


def _format_exc(etype, value, tb) -> str:
    try:
        return "".join(traceback.format_exception(etype, value, tb))
    except Exception:
        return f"{etype!r}: {value!r}"




def try_autosave_bundle(*, reason: str = "exit", fatal: bool = False) -> Path | None:
    """Best-effort autosave bundle on exit or crash.

    This is used by the atexit hook. It never raises.
    """
    try:
        if reason == "exit":
            if not should_autosave_on_exit():
                return None
        else:
            if not should_autosave_on_crash():
                return None

        from pneumo_solver_ui.diagnostics_entrypoint import build_full_diagnostics_bundle

        cfg = _load_diag_cfg()
        ss_override = None
        if cfg is not None:
            user_tag = str(getattr(cfg, "tag", "") or "").strip()
            auto_tag = f"auto-{reason}" + (f"_{user_tag}" if user_tag else "")
            ss_override = _cfg_to_session_override(cfg, tag_override=auto_tag)

        res = build_full_diagnostics_bundle(
            trigger=f"auto-{reason}",
            repo_root=_repo_root(),
            session_state=ss_override,
            open_folder=False,
        )
        _emit_bundle_summary_event("autosave_bundle", where=reason, res=res)
        if res.ok and res.zip_path:
            return Path(res.zip_path)
        return None
    except Exception:
        if fatal:
            print("[crash_guard] FATAL: autosave bundle failed", file=sys.stderr)
        else:
            print("[crash_guard] autosave bundle failed", file=sys.stderr)
        traceback.print_exc()
        return None
def install(*, label: str = "crash", project_root: Optional[Path] = None, extra_meta: Optional[Dict[str, Any]] = None, **_ignored) -> None:
    """Install hooks once (safe to call many times)."""
    global _INSTALLED, _ORIG_SYS_HOOK, _ORIG_THREAD_HOOK, _ORIG_UNRAISABLE_HOOK, _FAULT_FH
    global _PROJECT_ROOT_OVERRIDE, _EXTRA_META
    if _INSTALLED:
        return
    _INSTALLED = True
    # optional overrides from caller (streamlit/app wrapper)
    if project_root is not None:
        try:
            _PROJECT_ROOT_OVERRIDE = Path(project_root).resolve()
        except Exception:
            _PROJECT_ROOT_OVERRIDE = Path(str(project_root))
    if extra_meta:
        # ensure JSON-safe payload (event log uses json.dumps without default=)
        safe: Dict[str, Any] = {}
        for k, v in dict(extra_meta).items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe[str(k)] = v
            else:
                safe[str(k)] = str(v)
        _EXTRA_META = safe

    log_dir = _default_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # --- faulthandler ---
    try:
        import faulthandler

        fh_path = log_dir / "faulthandler.log"
        _FAULT_FH = open(fh_path, "a", encoding="utf-8", errors="replace")
        faulthandler.enable(file=_FAULT_FH, all_threads=True)
        _event("crash_guard", "faulthandler enabled", path=str(fh_path), label=label, release=RELEASE)
    except Exception as e:
        _event("crash_guard", "faulthandler enable failed", error=repr(e), label=label, release=RELEASE)

    # --- sys.excepthook ---
    try:
        _ORIG_SYS_HOOK = sys.excepthook

        def _sys_hook(etype, value, tb):
            try:
                _event(
                    "unhandled_exception",
                    "sys.excepthook",
                    label=label,
                    release=RELEASE,
                    etype=getattr(etype, "__name__", str(etype)),
                    error=repr(value),
                    traceback=_format_exc(etype, value, tb),
                )
            except Exception:
                pass
            try:
                _auto_bundle_on_crash("sys.excepthook", value)
            except Exception:
                pass
            try:
                if _ORIG_SYS_HOOK:
                    _ORIG_SYS_HOOK(etype, value, tb)
            except Exception:
                pass

        sys.excepthook = _sys_hook  # type: ignore[assignment]
    except Exception as e:
        _event("crash_guard", "sys.excepthook install failed", error=repr(e), label=label, release=RELEASE)

    # --- threading.excepthook (3.8+) ---
    try:
        if hasattr(threading, "excepthook"):
            _ORIG_THREAD_HOOK = threading.excepthook  # type: ignore[attr-defined]

            def _thr_hook(args):  # type: ignore[no-redef]
                try:
                    _event(
                        "thread_exception",
                        "threading.excepthook",
                        label=label,
                        release=RELEASE,
                        thread=str(getattr(args, "thread", None)),
                        etype=getattr(getattr(args, "exc_type", None), "__name__", str(getattr(args, "exc_type", None))),
                        error=repr(getattr(args, "exc_value", None)),
                        traceback=_format_exc(getattr(args, "exc_type", None), getattr(args, "exc_value", None), getattr(args, "exc_traceback", None)),
                    )
                except Exception:
                    pass
                try:
                    _auto_bundle_on_crash("threading.excepthook", getattr(args, "exc_value", None))
                except Exception:
                    pass
                try:
                    if _ORIG_THREAD_HOOK:
                        _ORIG_THREAD_HOOK(args)  # type: ignore[misc]
                except Exception:
                    pass

            threading.excepthook = _thr_hook  # type: ignore[assignment]
    except Exception as e:
        _event("crash_guard", "threading.excepthook install failed", error=repr(e), label=label, release=RELEASE)

    # --- sys.unraisablehook (3.8+) ---
    try:
        if hasattr(sys, "unraisablehook"):
            _ORIG_UNRAISABLE_HOOK = sys.unraisablehook  # type: ignore[attr-defined]

            def _unraisable_hook(unraisable):  # type: ignore[no-redef]
                try:
                    _event(
                        "unraisable_exception",
                        "sys.unraisablehook",
                        label=label,
                        release=RELEASE,
                        error=repr(getattr(unraisable, "exc_value", None)),
                        traceback=_format_exc(getattr(unraisable, "exc_type", None), getattr(unraisable, "exc_value", None), getattr(unraisable, "exc_traceback", None)),
                        object=repr(getattr(unraisable, "object", None)),
                        err_msg=str(getattr(unraisable, "err_msg", "")),
                    )
                except Exception:
                    pass
                try:
                    _auto_bundle_on_crash("sys.unraisablehook", getattr(unraisable, "exc_value", None))
                except Exception:
                    pass
                try:
                    if _ORIG_UNRAISABLE_HOOK:
                        _ORIG_UNRAISABLE_HOOK(unraisable)  # type: ignore[misc]
                except Exception:
                    pass

            sys.unraisablehook = _unraisable_hook  # type: ignore[assignment]
    except Exception as e:
        _event("crash_guard", "sys.unraisablehook install failed", error=repr(e), label=label, release=RELEASE)

    # --- atexit autosave ---
    # This covers "normal" process shutdown (e.g. user closes the terminal window, Ctrl+C, etc.).
    # NOTE: In Streamlit some shutdown paths are not clean; still useful as best-effort.
    global _ATEXIT_INSTALLED
    if not _ATEXIT_INSTALLED:

        def _atexit_autosave() -> None:
            try:
                # Same flag as crash autosave, but reason is different.
                try_autosave_bundle(reason="exit", fatal=False)
            except Exception:
                pass

        try:
            atexit.register(_atexit_autosave)
            _ATEXIT_INSTALLED = True
        except Exception:
            pass


def flush() -> None:
    """Best-effort flush of fault handler file."""
    global _FAULT_FH
    try:
        if _FAULT_FH:
            _FAULT_FH.flush()
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Backward-compatible entrypoint expected by app.py (and older bundles)
# -----------------------------------------------------------------------------

def install_crash_guard(
    *,
    repo_root=None,
    base_dir=None,
    app_label=None,
    label=None,
    extra_meta=None,
    **kwargs,
):
    """Backward-compatible wrapper around :func:`install`.

    The project historically used a helper named ``install_crash_guard`` which
    accepted ``repo_root`` (and sometimes ``base_dir`` / ``app_label``). During
    merges some bundles imported this symbol from ``pneumo_solver_ui.crash_guard``.

    Current implementation exposes :func:`install(label=..., project_root=...)`.
    This wrapper maps old argument names onto the new API.
    """

    # Old bundles used base_dir instead of repo_root.
    if repo_root is None and base_dir is not None:
        repo_root = base_dir

    # Old bundles used app_label which roughly matches install(label=...).
    if label is None and app_label is not None:
        label = str(app_label)

    call_kwargs = dict(kwargs)
    if label is not None:
        call_kwargs['label'] = label
    if extra_meta is not None:
        call_kwargs['extra_meta'] = extra_meta

    # install() is tolerant to unknown kwargs (it has **_ignored).
    return install(project_root=repo_root, **call_kwargs)
