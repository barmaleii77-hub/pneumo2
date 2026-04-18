# -*- coding: utf-8 -*-
"""START_PNEUMO_APP.pyw

Unified PneumoApp launcher (Windows-friendly):
- без консоли (pyw)
- кнопка "Запустить" ВСЕГДА пытается установить/обновить зависимости автоматически
- показ прогресса установки (чтобы было понятно, что процесс не завис)
- запуск Streamlit UI одной кнопкой
- ничего не теряем: stdout/stderr pip/streamlit пишем в логи

Логи:
  pneumo_solver_ui/logs/launcher_gui.log
  pneumo_solver_ui/logs/deps_install.log
  pneumo_solver_ui/logs/streamlit_stdout.log
"""

from __future__ import annotations

import os
import shutil
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
import uuid
import datetime
import urllib.error
import urllib.request
from pathlib import Path

# Run Registry (best-effort)
try:
    from pneumo_solver_ui.run_registry import start_run, end_run, append_event, env_context
except Exception:
    start_run = None  # type: ignore
    end_run = None  # type: ignore
    append_event = None  # type: ignore
    env_context = None  # type: ignore

# Secondary readiness fallback for Streamlit launcher (best-effort)
try:
    from pneumo_solver_ui.launcher_readiness import session_log_ready as _session_log_ready
except Exception:
    _session_log_ready = None  # type: ignore

# Best-effort recursive process-tree shutdown (Windows-safe)
try:
    from pneumo_solver_ui.process_tree import terminate_process_tree
except Exception:
    terminate_process_tree = None  # type: ignore

# Workspace contract bootstrap (best-effort)
try:
    from pneumo_solver_ui.workspace_contract import ensure_workspace_contract_dirs
except Exception:
    def ensure_workspace_contract_dirs(workspace_dir, *, include_optional: bool = True):
        try:
            p = Path(workspace_dir)
            p.mkdir(parents=True, exist_ok=True)
            names = ['exports', 'uploads', 'road_profiles', 'maneuvers', 'opt_runs', 'ui_state']
            if include_optional:
                names += ['_pointers', 'baselines', 'opt_archive', 'osc']
            for name in names:
                (p / name).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return []

# Crash guard (faulthandler + excepthooks) — best-effort
try:
    from pneumo_solver_ui.crash_guard import install as _install_crash_guard
    _install_crash_guard(label="launcher_gui")
except Exception:
    pass

# Tkinter может отсутствовать в некоторых Python-сборках.
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except Exception as _tk_e:  # pragma: no cover
    _msg = (
        "Не удалось импортировать Tkinter (нужен для GUI-лаунчера).\n\n"
        f"Ошибка: {_tk_e!r}\n\n"
        "Установи стандартный Python с python.org (включая tcl/tk), "
        "или запусти приложение через консоль: python -m streamlit run app.py"
    )
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, _msg, "PneumoApp launcher error", 0x10)
        except Exception:
            pass
    raise


ROOT = Path(__file__).resolve().parent

APP_NAME = "UnifiedPneumoApp"


def _collect_anim_latest_registry_fields() -> dict:
    """Best-effort snapshot of the current anim_latest diagnostics for launcher events."""
    try:
        from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary

        return dict(collect_anim_latest_diagnostics_summary() or {})
    except Exception:
        return {}


def _is_windows_store_python() -> bool:
    """Best-effort detection of Microsoft Store Python.

    Why we care:
      - Store Python is packaged and Windows can transparently redirect %LOCALAPPDATA%
        into the package LocalCache.
      - venv's native launcher (python.exe inside venv) is *not* packaged and expects
        a physical pyvenv.cfg next to the interpreter.
      - If we mix redirected paths with physical paths, we get RC=106 +
        "failed to locate pyvenv.cfg".
    """

    if os.name != "nt":
        return False
    exe_l = str(Path(sys.executable)).lower()
    return ("\\microsoft\\windowsapps\\" in exe_l) and ("pythonsoftwarefoundation.python" in exe_l)


def _windows_store_pkg_family_name() -> str | None:
    """Extract package family name from sys.executable path, if possible."""

    if not _is_windows_store_python():
        return None

    exe = Path(sys.executable)
    parts = list(exe.parts)
    for i, p in enumerate(parts):
        if p.lower() == "windowsapps" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def _windows_store_localcache_local_dir() -> Path | None:
    """Return ...\\AppData\\Local\\Packages\\<pkg>\\LocalCache\\Local for Store Python."""

    pkg = _windows_store_pkg_family_name()
    if not pkg:
        return None

    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Local"))
    p = base / "Packages" / pkg / "LocalCache" / "Local"
    return p

def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

def _default_appdata_dir() -> Path:
    """Где хранить общие данные на одной машине (per-user).

    Windows: %LOCALAPPDATA%/UnifiedPneumoApp
    Linux/macOS: ~/.cache/unifiedpneumoapp (или XDG_* если задано)
    """
    override = os.environ.get("PNEUMO_APPDATA_DIR")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Local")

        # Microsoft Store Python: avoid %LOCALAPPDATA% redirection mismatch.
        store_local = _windows_store_localcache_local_dir()
        if store_local is not None:
            return store_local / APP_NAME

        return Path(base) / APP_NAME

    xdg = os.environ.get("XDG_CACHE_HOME") or os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_NAME.lower()

    return Path.home() / ".cache" / APP_NAME.lower()

def _default_shared_venv_dir(root: Path) -> Path:
    """Shared venv: одна виртуальная среда на машине (на версию Python).

    Можно override:
      - PNEUMO_VENV_DIR / PNEUMO_SHARED_VENV_DIR
      - или вернуть старое поведение: PNEUMO_USE_LOCAL_VENV=1 -> .venv рядом с релизом
    """
    override = os.environ.get("PNEUMO_VENV_DIR") or os.environ.get("PNEUMO_SHARED_VENV_DIR")
    if override:
        return Path(override).expanduser()

    if _truthy(os.environ.get("PNEUMO_USE_LOCAL_VENV")):
        return root / ".venv"

    py_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    return _default_appdata_dir() / "venvs" / py_tag

def _safe_read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    return {}

def _safe_write_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass



def _now_utc_iso() -> str:
    """Timezone-aware UTC timestamp (ISO8601)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
def _acquire_install_lock(lock_path: Path, timeout_s: float = 900.0) -> int | None:
    """Простейший межпроцессный lock (best-effort).

    Нужен, чтобы два релиза не пытались одновременно делать pip install в одну shared-venv.
    """
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    deadline = time.time() + float(timeout_s)
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode("utf-8"))
            except Exception:
                pass
            return fd
        except FileExistsError:
            # If a previous launcher crashed, the lock file can remain and block new starts.
            # We try to detect stale locks more intelligently:
            #  - if PID from the lock is not running -> remove lock immediately
            #  - else fall back to time-based stale cleanup (6h)
            try:
                txt = lock_path.read_text(encoding="utf-8", errors="ignore")
                _lines = txt.splitlines()
                pid = int(_lines[0]) if len(_lines) > 0 and _lines[0].strip().isdigit() else None
                ts = float(_lines[1]) if len(_lines) > 1 else None

                def _pid_exists(p: int) -> bool:
                    if p is None or p <= 0:
                        return False
                    if os.name == "nt":
                        try:
                            import ctypes
                            kernel32 = ctypes.windll.kernel32
                            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, int(p))
                            if handle:
                                kernel32.CloseHandle(handle)
                                return True
                            err = kernel32.GetLastError()
                            # Access denied usually means the process exists but we cannot query it.
                            return err == 5
                        except Exception:
                            # In doubt, assume it exists (safer).
                            return True
                    else:
                        try:
                            os.kill(int(p), 0)
                            return True
                        except Exception:
                            return False

                if pid is not None and not _pid_exists(pid):
                    try:
                        lock_path.unlink()
                    except Exception:
                        pass
                    continue

                # time-based stale cleanup (6h)
                if ts is not None and (time.time() - ts) > 6 * 3600:
                    try:
                        lock_path.unlink()
                    except Exception:
                        pass
                    continue
            except Exception:
                pass

            if time.time() > deadline:
                return None
            time.sleep(0.5)
        except Exception:
            return None

def _release_install_lock(lock_path: Path, fd: int | None) -> None:
    try:
        if fd is not None:
            os.close(fd)
    except Exception:
        pass
    try:
        lock_path.unlink()
    except Exception:
        pass

try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    # Fallback must never be stale: it is used in logs/state files if release_info import fails.
    RELEASE = os.environ.get("PNEUMO_RELEASE", "PneumoApp_v6_80_R176") or "PneumoApp_v6_80_R176"
os.environ.setdefault("PNEUMO_RELEASE", RELEASE)
os.environ.setdefault("PNEUMO_AUTO_SEND_BUNDLE", os.environ.get("PNEUMO_AUTO_SEND_BUNDLE", "1") or "1")
APPDATA_DIR = _default_appdata_dir()


# --- bootstrap logging (must work even before GUI init) ---
# The launcher must NEVER fail silently. Even import-time issues must leave a trace.
BOOT_LOG_DIR = APPDATA_DIR / "logs"
BOOT_LOG_FILE = BOOT_LOG_DIR / "launcher_bootstrap.log"

def _boot_log(msg: str) -> None:
    try:
        BOOT_LOG_DIR.mkdir(parents=True, exist_ok=True)

        with open(BOOT_LOG_FILE, "a", encoding="utf-8", errors="replace") as _fh:
            _fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        # absolutely best-effort; never raise from logger
        pass

_boot_log(f"START_PNEUMO_APP import: RELEASE={RELEASE} ROOT={ROOT} exe={sys.executable}")

PIP_CACHE_DIR = APPDATA_DIR / "pip_cache"

def _with_pip_cache_env(env: dict | None) -> dict:
    """Return environment dict with stable pip/cache + UTF-8 settings.

    This helper is used for subprocess calls where we want:
    - consistent UTF-8 output (logs)
    - pip cache in %LOCALAPPDATA%/UnifiedPneumoApp/pip_cache
    """
    try:
        e = dict(env or {})
    except Exception:
        e = {}
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    e["PIP_NO_PYTHON_VERSION_WARNING"] = "1"
    e["PIP_NO_COLOR"] = "1"
    e["PIP_PROGRESS_BAR"] = "off"
    try:
        e["PIP_CACHE_DIR"] = str(PIP_CACHE_DIR)
    except Exception:
        pass
    return e


# Python tag for shared venvs/locks, e.g. "py313".
PY_TAG = f"py{sys.version_info.major}{sys.version_info.minor}"
VENV_DIR = _default_shared_venv_dir(ROOT)
DEPS_STATE_FILE = VENV_DIR / "pneumo_deps_state.json"

# IMPORTANT (stability): the inter-process lock MUST NOT live inside the venv directory.
# If the lock is inside VENV_DIR then lock acquisition can create VENV_DIR early
# (lock_path.parent.mkdir), and another process can observe a half-created venv.
# That race manifests on Windows as: "failed to locate pyvenv.cfg" (RC=106).
LOCKS_DIR = APPDATA_DIR / "locks"
_venv_hash = hashlib.sha1(str(VENV_DIR).encode("utf-8", errors="ignore")).hexdigest()[:10]
DEPS_LOCK_FILE = LOCKS_DIR / f"pneumo_deps_install_{PY_TAG}_{_venv_hash}.lock"
REQ_FILE = ROOT / "requirements.txt"
LOG_DIR = ROOT / "pneumo_solver_ui" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LAUNCHER_LOG = LOG_DIR / "launcher_gui.log"
DEPS_LOG = LOG_DIR / "deps_install.log"
STREAMLIT_LOG = LOG_DIR / "streamlit_stdout.log"


# TOUCH_LOG_FILES: create log files early so that even early-stage failures are visible
for _p in (LAUNCHER_LOG, DEPS_LOG, STREAMLIT_LOG):
    try:
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.touch(exist_ok=True)
    except Exception:
        pass


DEFAULT_PORT = 8505

def _ts_compact() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())

def _new_run_id(prefix: str = "UI") -> str:
    return f"{prefix}_{_ts_compact()}"

def _new_session_dir(run_id: str) -> Path:
    base = (ROOT / "runs" / "ui_sessions").resolve()
    session = base / str(run_id)
    (session / "logs").mkdir(parents=True, exist_ok=True)
    ensure_workspace_contract_dirs(session / "workspace", include_optional=True)
    try:
        (session / "_launcher_session.txt").write_text("created by START_PNEUMO_APP\n", encoding="utf-8")
    except Exception:
        pass
    return session


def _creationflags_no_window() -> int:
    """Флаг для скрытого запуска процессов на Windows."""
    if sys.platform.startswith("win"):
        return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return 0


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """True если кто-то слушает порт.

    Важно: на Windows/localhost часть процессов может слушать только IPv6 (::1),
    поэтому при host in ('127.0.0.1', 'localhost') дополнительно проверяем ::1.
    Это устраняет ситуацию, когда UI печатает один порт, а Streamlit тихо
    переезжает на следующий из-за занятости на IPv6.
    """
    hosts = [host]
    if host in ("127.0.0.1", "localhost"):
        hosts.append("::1")
    for h in hosts:
        try:
            with socket.create_connection((h, port), timeout=0.25):
                return True
        except OSError:
            pass
    return False


def _pick_free_port(preferred: int, max_tries: int = 50) -> int:
    """Pick a free localhost port starting from preferred.

    Users often leave an old Streamlit instance running (even from another release).
    Re-using an occupied port silently attaches the browser to the old server, leading
    to mismatched code/venv and the typical "everything is red" failure mode.
    """
    port = max(1, int(preferred))
    for _ in range(max_tries):
        if not _is_port_open(port):
            return port
        port += 1
    return max(1, int(preferred))


def _http_probe_status(url: str, timeout: float = 0.75) -> tuple[bool, str]:
    """Probe Streamlit via HTTP, not only via a raw socket.

    A listening TCP port is not enough: the browser may open while Streamlit still
    cannot serve the page. We require an actual HTTP response from the health
    endpoint or the root page.
    """
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            return (200 <= code < 500), f"http_{code}"
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        return (200 <= code < 500), f"http_{code}"
    except Exception as e:
        return False, f"{type(e).__name__}:{e}"


def _http_ready_once(port: int, host: str = "127.0.0.1") -> tuple[bool, list[str]]:
    urls = [
        f"http://{host}:{port}/_stcore/health",
        f"http://{host}:{port}/",
    ]
    notes: list[str] = []
    for url in urls:
        ok, msg = _http_probe_status(url)
        notes.append(f"{url} -> {msg}")
        if ok:
            return True, notes
    return False, notes


def _open_url_best_effort(url: str) -> bool:
    try:
        if webbrowser.open(url, new=2):
            return True
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            os.startfile(url)  # noqa: S606
            return True
        except Exception:
            pass
    return False


def _venv_python(prefer_gui: bool = False) -> Path:
    """Возвращает python из .venv (если есть), иначе sys.executable."""
    if sys.platform.startswith("win"):
        scripts = VENV_DIR / "Scripts"
        if prefer_gui:
            pyw = scripts / "pythonw.exe"
            if pyw.exists():
                return pyw
        py = scripts / "python.exe"
        if py.exists():
            return py
    else:
        py = VENV_DIR / "bin" / "python"
        if py.exists():
            return py
    return Path(sys.executable)



def _python_in_venv() -> Path:
    """Вернуть путь к python.exe внутри venv (без fallback на системный python).

    Важно: этот helper используется для диагностики «битого venv».
    Нельзя возвращать sys.executable: иначе можно не заметить, что venv повреждён
    (например, отсутствует pyvenv.cfg), и дальше запуск/установка зависимостей будут
    работать непредсказуемо.
    """
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"



def _wipe_venv_best_effort() -> bool:
    """Best-effort очистка venv перед пересозданием.

    Это критичный шаг для shared-venv: если среда повреждена (например, python.exe
    внутри неё выдаёт `failed to locate pyvenv.cfg`, RC=106), любые `pip install` будут
    бесконечно падать.

    Правила безопасности:
    - Удаляем ТОЛЬКО ожидаемый каталог окружения (shared-venv внутри APPDATA или локальный `.venv`).
    - Никаких «умных» удалений произвольных путей по ошибке.
    - Все действия логируются в launcher_gui.log.

    Возвращает True, если среда удалена/перемещена (или её не было), иначе False.
    """

    def _log(msg: str) -> None:
        try:
            with open(LAUNCHER_LOG, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"[wipe_venv] {msg}\n")
        except Exception:
            pass

    try:
        if not VENV_DIR.exists():
            return True

        # --- safety fence ---
        try:
            venv_abs = VENV_DIR.resolve()
            root_abs = ROOT.resolve()
            appdata_abs = _default_appdata_dir().resolve()
        except Exception:
            venv_abs = VENV_DIR
            root_abs = ROOT
            appdata_abs = _default_appdata_dir()

        # Разрешаем чистку только для:
        # 1) shared-venv: <APPDATA>/venvs/pyXY
        # 2) локальный venv: <ROOT>/.venv
        safe = False
        try:
            if str(venv_abs).startswith(str(appdata_abs / "venvs")):
                safe = True
            elif venv_abs == (root_abs / ".venv"):
                safe = True
        except Exception:
            safe = False

        if not safe and not _truthy(os.environ.get("PNEUMO_ALLOW_CUSTOM_VENV_WIPE")):
            _log(
                "REFUSED to wipe VENV_DIR (safety fence). "
                f"VENV_DIR={VENV_DIR} (set PNEUMO_ALLOW_CUSTOM_VENV_WIPE=1 to override)"
            )
            return False

        # --- attempt 1: direct delete ---
        def _onerror(func, p, exc):
            # Windows: часто попадаются read-only файлы.
            try:
                os.chmod(p, 0o700)
                func(p)
            except Exception:
                pass

        _log(f"Attempt rmtree: {VENV_DIR}")
        try:
            shutil.rmtree(VENV_DIR, onerror=_onerror)
            _log("rmtree OK")
            return True
        except Exception as e:
            _log(f"rmtree failed: {e!r}")

        # --- attempt 2: move aside to trash (helps when some files are locked) ---
        try:
            trash = _default_appdata_dir() / "venvs_trash"
            trash.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            dst = trash / f"{VENV_DIR.name}_{stamp}_{uuid.uuid4().hex[:8]}"
            _log(f"Attempt move -> {dst}")
            shutil.move(str(VENV_DIR), str(dst))
            _log("move OK")

            # Best-effort cleanup of moved dir.
            try:
                shutil.rmtree(dst, onerror=_onerror)
                _log("trash rmtree OK")
            except Exception as e2:
                _log(f"trash rmtree failed (left in place): {e2!r}")
            return True
        except Exception as e:
            _log(f"move failed: {e!r}")

        return False
    except Exception as e:
        _log(f"wipe_venv unexpected error: {e!r}")
        return False
def _safe_messagebox_error(title: str, text: str) -> None:
    """Показать ошибку без риска «тихого» закрытия pyw."""
    try:
        messagebox.showerror(title, text)
        return
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
        except Exception:
            pass


def _safe_messagebox_warning(title: str, text: str) -> None:
    """Показать предупреждение без риска «тихого» закрытия pyw."""
    try:
        messagebox.showwarning(title, text)
        return
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, title, 0x30)  # MB_ICONWARNING
        except Exception:
            pass


class LauncherGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Unified PneumoApp — Launcher")
        self.root.geometry("980x700")

        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.open_browser_var = tk.BooleanVar(value=True)
        self.show_console_var = tk.BooleanVar(value=False)  # по умолчанию запуск без отдельного чёрного окна Streamlit

        self.status_var = tk.StringVar(value="Готово.")
        self._pbar_mode = "determinate"

        self.proc: subprocess.Popen | None = None
        self.proc_kind: str | None = None
        self.session_dir: Path | None = None
        self.run_id: str | None = None
        self.trace_id: str | None = None
        self.rr_token: str | None = None
        self.watchdog_proc: subprocess.Popen | None = None
        self._exit_handled: bool = False
        self._close_requested: bool = False
        self._launcher_stop_requested: bool = False
        self._launcher_stop_source: str | None = None
        self._child_env: dict | None = None
        self.stream_log_fh = None
        self.active_log_path: Path | None = None
        self._lock = threading.Lock()
        self.launch_http_ready: bool = False
        self.launch_ready_source: str | None = None
        self.launch_http_notes: list[str] = []
        self.launch_readiness_diag: dict | None = None

        self._build_ui()
        self._log(f"PY_EXE={sys.executable}")
        if _is_windows_store_python():
            self._log("PYTHON_DIST=Microsoft Store Python (packaged): shared venv/appdata will live in package LocalCache")
        self._log(f"APPDATA_DIR={APPDATA_DIR}")
        self._log(f"ROOT={ROOT}")
        self._log(f"VENV_DIR={VENV_DIR}")
        self._log(f"REQ_FILE={REQ_FILE}")

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="Порт:").pack(side="left")
        ttk.Entry(top, textvariable=self.port_var, width=8).pack(side="left", padx=(6, 12))
        ttk.Checkbutton(top, text="Открыть браузер", variable=self.open_browser_var).pack(side="left")
        ttk.Checkbutton(top, text="Показать консоль Streamlit", variable=self.show_console_var).pack(side="left", padx=(12, 0))

        ttk.Button(top, text="Запустить (с авто-установкой зависимостей)", command=self.start_app).pack(
            side="right", padx=6
        )
        ttk.Button(top, text="Запустить Desktop Main Shell", command=self.start_desktop_shell).pack(side="right", padx=6)
        ttk.Button(top, text="Остановить", command=lambda: self.stop_app(reason="button_stop")).pack(side="right", padx=6)
        ttk.Button(top, text="Только установить зависимости", command=self.install_deps).pack(side="right", padx=6)

        # status + progress
        status = ttk.Frame(self.root)
        status.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(status, textvariable=self.status_var).pack(side="left")

        self.pbar = ttk.Progressbar(status, mode="determinate", maximum=100)
        self.pbar.pack(side="right", fill="x", expand=True, padx=(12, 0))

        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, padx=10, pady=8)

        self.logbox = scrolledtext.ScrolledText(mid, height=26, wrap="word")
        self.logbox.pack(fill="both", expand=True)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(bottom, text="Открыть папку логов", command=self.open_logs_dir).pack(side="left")
        ttk.Button(bottom, text="Открыть deps_install.log", command=self.open_deps_log).pack(side="left", padx=6)
        ttk.Button(bottom, text="Открыть streamlit_stdout.log", command=self.open_streamlit_log).pack(side="left", padx=6)
        ttk.Button(bottom, text="Открыть desktop_main_shell_qt.log", command=self.open_desktop_log).pack(side="left", padx=6)
        ttk.Button(bottom, text="Выход", command=self.on_close).pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI helpers (thread-safe) ----------------
    def _ui_status(self, text: str) -> None:
        def _set() -> None:
            self.status_var.set(text)

        self.root.after(0, _set)

    def _pbar_set(self, value: float) -> None:
        def _set() -> None:
            try:
                self.pbar.config(mode="determinate")
                self._pbar_mode = "determinate"
                self.pbar["value"] = max(0.0, min(100.0, float(value)))
            except Exception:
                pass

        self.root.after(0, _set)

    def _pbar_start_indeterminate(self) -> None:
        def _set() -> None:
            try:
                if self._pbar_mode != "indeterminate":
                    self.pbar.config(mode="indeterminate")
                    self._pbar_mode = "indeterminate"
                self.pbar.start(10)
            except Exception:
                pass

        self.root.after(0, _set)

    def _pbar_stop(self) -> None:
        def _set() -> None:
            try:
                self.pbar.stop()
                self.pbar.config(mode="determinate")
                self._pbar_mode = "determinate"
            except Exception:
                pass

        self.root.after(0, _set)

    def _reset_launch_state(self) -> None:
        self._exit_handled = False
        self._close_requested = False
        self._launcher_stop_requested = False
        self._launcher_stop_source = None
        self.launch_http_ready = False
        self.launch_ready_source = None
        self.launch_http_notes = []
        self.launch_readiness_diag = None
        self.proc_kind = None
        self.rr_token = None

    def _prepare_child_session_env(
        self,
        *,
        run_prefix: str = "UI",
        extra_env: dict[str, str] | None = None,
    ) -> tuple[str, Path, Path, Path, str, dict[str, str]]:
        self._reset_launch_state()
        run_id = _new_run_id(run_prefix)
        session_dir = _new_session_dir(run_id)
        trace_id = uuid.uuid4().hex[:12]
        self.run_id = run_id
        self.session_dir = session_dir
        self.trace_id = trace_id

        log_dir = session_dir / "logs"
        workspace_dir = session_dir / "workspace"

        env = os.environ.copy()
        env.update(
            {
                "PNEUMO_RELEASE": RELEASE,
                "PNEUMO_RUN_ID": run_id,
                "PNEUMO_TRACE_ID": trace_id,
                "PNEUMO_SESSION_DIR": str(session_dir),
                "PNEUMO_LOG_DIR": str(log_dir),
                "PNEUMO_WORKSPACE_DIR": str(workspace_dir),
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONWARNINGS": "default",
                "PNEUMO_SHARED_VENV_PYTHON": str(_venv_python(prefer_gui=False)),
                "PYTHONPATH": str(ROOT)
                + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else ""),
            }
        )
        normalized_extra_env = {str(k): str(v) for k, v in (extra_env or {}).items()}
        transient_keys = {
            "PNEUMO_UI_PORT",
            "PNEUMO_AUTO_SEND_BUNDLE",
            "PNEUMO_DESKTOP_MAIN_SHELL_QT",
            "PNEUMO_DESKTOP_GUI_SPEC_SHELL",
            "PNEUMO_LAUNCH_SURFACE",
        }
        for key in transient_keys:
            if key not in normalized_extra_env:
                env.pop(key, None)
                os.environ.pop(key, None)
        env.update(normalized_extra_env)

        os.environ.update({k: v for k, v in env.items() if k.startswith("PNEUMO_")})
        self._child_env = env
        return run_id, session_dir, log_dir, workspace_dir, trace_id, env

    def _close_active_log_handle(self) -> None:
        try:
            if self.stream_log_fh:
                self.stream_log_fh.close()
        except Exception:
            pass
        self.stream_log_fh = None

    def _attach_process_log(self, log_path: Path, cmd: list[str]) -> None:
        self._close_active_log_handle()
        self.active_log_path = log_path
        try:
            self.stream_log_fh = open(log_path, "a", encoding="utf-8", errors="replace")
            self.stream_log_fh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            self.stream_log_fh.write(" ".join(cmd) + "\n")
            self.stream_log_fh.flush()
        except Exception:
            self.stream_log_fh = None

    def _launch_logged_process(
        self,
        *,
        cmd: list[str],
        env: dict[str, str],
        log_path: Path,
        show_console: bool,
    ) -> subprocess.Popen:
        self._attach_process_log(log_path, cmd)
        creationflags = subprocess.CREATE_NEW_CONSOLE if show_console else _creationflags_no_window()
        popen_kwargs = {}
        if not show_console:
            popen_kwargs["stdout"] = self.stream_log_fh or subprocess.DEVNULL
            popen_kwargs["stderr"] = self.stream_log_fh or subprocess.DEVNULL
        return subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            creationflags=creationflags,
            env=env,
            **popen_kwargs,
        )

    # ---------------- logging ----------------
    def _log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        try:
            self.logbox.insert("end", line)
            self.logbox.see("end")
        except Exception:
            pass
        try:
            with open(LAUNCHER_LOG, "a", encoding="utf-8", errors="replace") as f:
                f.write(line)
        except Exception:
            pass

    def _run_cmd(self, cmd: list[str], *, cwd: Path | None = None, tee_file: Path | None = None) -> int:
        """Запустить команду скрыто и залогировать stdout/stderr."""
        self._log("CMD: " + " ".join(cmd))
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        env["PIP_NO_PYTHON_VERSION_WARNING"] = "1"
        env["PIP_NO_COLOR"] = "1"
        env["PIP_PROGRESS_BAR"] = "off"
        env["PIP_CACHE_DIR"] = str(PIP_CACHE_DIR)
        env["PYTHONWARNINGS"] = env.get("PYTHONWARNINGS", "default")

        p = subprocess.Popen(
            cmd,
            cwd=str(cwd or ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags_no_window(),
        )
        assert p.stdout is not None

        fh = None
        try:
            if tee_file is not None:
                tee_file.parent.mkdir(parents=True, exist_ok=True)
                fh = open(tee_file, "a", encoding="utf-8", errors="replace")
                fh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                fh.write(" ".join(cmd) + "\n")
        except Exception:
            fh = None

        last_output = time.time()
        for line in p.stdout:
            last_output = time.time()
            s = line.rstrip("\n")
            self._log(s)
            try:
                if fh:
                    fh.write(s + "\n")
            except Exception:
                pass

        rc = int(p.wait())
        try:
            if fh:
                fh.write(f"RC={rc}\n")
                fh.close()
        except Exception:
            pass

        # Если pip "молчит" долго — индикатор всё равно крутится, но добавим запись
        if time.time() - last_output > 8.0:
            self._log("... (нет вывода несколько секунд — процесс всё ещё может работать)")
        return rc

    # ---------------- helpers ----------------
    def ensure_venv(self, *, force_recreate: bool = False) -> bool:
        """Ensure that VENV_DIR exists and is a healthy Python venv.

        IMPORTANT:
        - Никаких "догадок" и скрытых допущений: venv должен быть либо корректным, либо
          пересозданным. Если Python внутри venv не стартует — это считается повреждением.
        - На Windows встречается состояние: python.exe существует, но pyvenv.cfg отсутствует/
          не читается. Тогда `python -m pip ...` падает с RC=106 ("failed to locate pyvenv.cfg").
          Мы обязаны детектировать это заранее и самовосстанавливаться (пересоздать venv),
          а не молча продолжать и плодить неочевидные ошибки.
        """
        cfg = VENV_DIR / "pyvenv.cfg"
        py_cli = _venv_python(prefer_gui=False)

        def _probe_python_health(py_exe: Path) -> tuple[int, str]:
            try:
                env = os.environ.copy()
                env["PYTHONUTF8"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                p = subprocess.run(
                    [str(py_exe), "-c", "import sys; print(sys.prefix)"],
                    cwd=str(ROOT),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=_creationflags_no_window(),
                )
                return int(p.returncode), (p.stdout or "")
            except Exception as e:
                return 999, f"{type(e).__name__}: {e}"

        # If venv dir exists, verify it is structurally present AND Python can actually стартовать.
        if VENV_DIR.exists():
            if (not force_recreate) and cfg.exists() and py_cli.exists():
                rc_probe, out_probe = _probe_python_health(py_cli)
                if rc_probe == 0:
                    return True
                self._log(
                    "⚠️ Venv найден, но python внутри не запускается корректно "
                    f"(rc={rc_probe}). Буду пересоздавать.\n{out_probe.strip()}"
                )

            self._log(f"⚠️ Venv выглядит повреждённым: cfg={cfg.exists()} py={py_cli.exists()} -> пересоздаю")
            self._ui_status("Venv повреждён — пересоздаю … (см. logs/launcher_gui.log)")
            self._pbar_start_indeterminate()
            ok_wipe = _wipe_venv_best_effort()
            self._pbar_stop()
            if not ok_wipe:
                _safe_messagebox_error(
                    "Ошибка",
                    "Не удалось удалить повреждённую виртуальную среду.\n\n"
                    "Закройте все процессы приложения (Streamlit/Animator/другие релизы) и повторите.\n"
                    f"Путь: {VENV_DIR}",
                )
                return False

        # Create venv
        self._log("Creating venv …")
        self._ui_status("Создаю виртуальную среду … (первый раз может быть долго)")
        self._pbar_start_indeterminate()
        rc = self._run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=ROOT, tee_file=DEPS_LOG)
        self._pbar_stop()
        if rc != 0:
            _safe_messagebox_error(
                "Ошибка",
                "Не удалось создать виртуальную среду.\n\n"
                f"RC={rc}\n\nСм. лог: {DEPS_LOG}",
            )
            return False

        # Final structure check
        cfg2 = VENV_DIR / "pyvenv.cfg"
        py2 = _venv_python(prefer_gui=False)
        if not cfg2.exists() or not py2.exists():
            _safe_messagebox_error(
                "Ошибка",
                "Venv создан, но структура неполная.\n\n"
                f"cfg={cfg2.exists()} py={py2.exists()}\n\n"
                f"Путь: {VENV_DIR}\nСм. лог: {DEPS_LOG}",
            )
            return False

        rc_probe2, out_probe2 = _probe_python_health(py2)
        if rc_probe2 != 0:
            self._log(f"❌ Python в новом venv не запускается (rc={rc_probe2}).\n{out_probe2.strip()}")
            _safe_messagebox_error(
                "Ошибка",
                "Создана виртуальная среда, но python внутри неё не запускается.\n\n"
                "Это обычно означает повреждение venv или конфликт процессов.\n\n"
                f"Путь: {VENV_DIR}\nСм. лог: {DEPS_LOG}",
            )
            return False

        return True

    # ---------------- deps state & validation ----------------
    def _load_deps_state(self) -> dict:
        """Load last dependency installation state.

        Notes:
        - Это *служебные* данные лаунчера (не параметры модели). Они не участвуют в расчётах,
          но повышают UX: сохраняем факт успешной установки для быстрых последующих запусков.
        - Ошибки чтения/парсинга не должны приводить к падению лаунчера.
          Любые проблемы → предупреждение в лог и возврат пустого состояния.
        """
        try:
            if not DEPS_STATE_FILE.exists():
                return {}
            raw = DEPS_STATE_FILE.read_text(encoding="utf-8", errors="replace")
            import json

            obj = json.loads(raw) if raw.strip() else {}
            if isinstance(obj, dict):
                return obj
            self._log(f"[deps] WARN: deps state is not a dict: {DEPS_STATE_FILE}")
            return {}
        except Exception as e:
            self._log(f"[deps] WARN: cannot read deps state {DEPS_STATE_FILE}: {e!r}")
            return {}

    def _save_deps_state(self, state: dict) -> None:
        """Persist dependency installation state (best-effort, never crash)."""
        try:
            import json

            DEPS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = DEPS_STATE_FILE.with_suffix(DEPS_STATE_FILE.suffix + ".tmp")
            tmp.write_text(
                json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
                errors="replace",
            )
            os.replace(tmp, DEPS_STATE_FILE)
        except Exception as e:
            self._log(f"[deps] WARN: cannot write deps state {DEPS_STATE_FILE}: {e!r}")

    def _preflight_imports(self, py_cli: Path) -> dict:
        """Quick sanity check that the venv Python can import the basic tooling.

        This is intentionally minimal and offline.

        Returns:
            {"ok": bool, "error": str|None}
        """
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            script = (
                "import json,sys; "
                "import pip; "
                "print(json.dumps({'ok': True, 'py': sys.version.split()[0]}))"
            )
            r = subprocess.run(
                [str(py_cli), "-c", script],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_creationflags_no_window(),
            )
            out = (r.stdout or "") + ("\n" + (r.stderr or "") if r.stderr else "")
            if r.returncode != 0:
                return {"ok": False, "error": out.strip() or f"rc={r.returncode}"}
            # Parse last non-empty line as JSON (defensive against noisy outputs)
            import json

            last = ""
            for line in (out or "").splitlines():
                if line.strip():
                    last = line.strip()
            if not last:
                return {"ok": False, "error": "no output"}
            try:
                payload = json.loads(last)
            except Exception:
                payload = {"ok": True}
            if not isinstance(payload, dict):
                return {"ok": False, "error": f"unexpected output: {last[:200]}"}
            if not payload.get("ok", False):
                return {"ok": False, "error": str(payload)}
            return {"ok": True, "error": None}
        except Exception as e:
            return {"ok": False, "error": repr(e)}


    def _import_smoke_check(self, py_cli: Path) -> dict[str, str]:
        """Try importing the main 3rd‑party modules that the app relies on.

        This is *not* a substitute for requirements solving. Its purpose is to make
        post-install warnings truthful and actionable.

        Returns:
            dict[module_name] = error_string  (only for failed imports)
        """
        modules = [
            # Core UI + numerics
            "streamlit",
            "numpy",
            "pandas",
            "scipy",
            "matplotlib",
            "yaml",
            "PIL",
            "requests",
            "psutil",
            # Parallel + optimisation stack
            "dask",
            "distributed",
            "torch",
            "botorch",
            "pyro",
            # Desktop animator stack
            "PySide6",
            "pyqtgraph",
            "OpenGL",
            # Threadpool control
            "threadpoolctl",
        ]
        script = (
            "import importlib, json\n"
            "mods = " + json.dumps(modules) + "\n"
            "bad = {}\n"
            "for m in mods:\n"
            "    try:\n"
            "        importlib.import_module(m)\n"
            "    except Exception as e:\n"
            "        bad[m] = repr(e)\n"
            "print(json.dumps(bad, ensure_ascii=False))\n"
        )
        try:
            cp = subprocess.run(
                [str(py_cli), "-c", script],
                capture_output=True,
                text=True,
                env=_with_pip_cache_env(os.environ.copy()),
                timeout=120,
            )
        except Exception as e:
            self._log(f"⚠️ import smoke check failed to run: {e!r}")
            return {"__smoke_check_runner__": repr(e)}

        if cp.returncode != 0:
            self._log("⚠️ import smoke check returned non-zero exit code")
            self._log(cp.stdout or "")
            self._log(cp.stderr or "")
            return {"__smoke_check_runner__": f"nonzero_exit:{cp.returncode}"}

        try:
            return json.loads((cp.stdout or "{}").strip() or "{}")
        except Exception:
            # If something printed extra lines, do not crash the launcher.
            self._log("⚠️ import smoke check produced non-JSON output")
            self._log(cp.stdout or "")
            self._log(cp.stderr or "")
            return {"__smoke_check_runner__": "non_json_output"}

    def _requirements_satisfied(self, py_cli: Path, req_file: Path) -> tuple[bool, list[str]]:
        """Offline check: are requirements from `req_file` already satisfied in venv?

        We do NOT call pip here to avoid slow network operations. Instead we parse the requirements
        and compare against installed distributions using importlib.metadata.

        If the check cannot be performed reliably, we return (False, issues) (forces pip install).
        """
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            # Run inside venv. Prefer external `packaging`, but fall back to pip's vendored packaging
            # to avoid requiring extra deps in a fresh venv.
            script = r"""
import json, sys
from pathlib import Path
from importlib import metadata

try:
    from packaging.requirements import Requirement
except Exception:
    try:
        from pip._vendor.packaging.requirements import Requirement
    except Exception as e:
        print(json.dumps({"ok": False, "issues": [f"packaging_import_failed: {e!r}"]}, ensure_ascii=False))
        raise SystemExit(0)


def iter_req_lines(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        yield f"__READ_ERROR__:{path}:{e!r}"
        return
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        # strip inline comments
        if ' #' in s:
            s = s.split(' #', 1)[0].rstrip()
        if s.startswith('-r') or s.startswith('--requirement'):
            parts = s.split()
            if len(parts) >= 2:
                sub = (path.parent / parts[1]).resolve()
                yield from iter_req_lines(sub)
            continue
        if s.startswith('-'):
            # Options like --extra-index-url, --index-url, --find-links, etc.
            # They do not affect whether already-installed distributions satisfy the requirements,
            # so we ignore them for the offline "already satisfied?" check.
            continue
        yield s


def ok_for_req(req: Requirement) -> tuple[bool, str]:
    # markers
    try:
        if req.marker is not None and not req.marker.evaluate():
            return True, "marker_skip"
    except Exception:
        pass
    name = req.name
    try:
        v = metadata.version(name)
    except Exception:
        return False, f"missing:{name}"
    try:
        if req.specifier and (v not in req.specifier):
            return False, f"mismatch:{name} installed={v} required={str(req.specifier)}"
    except Exception as e:
        return False, f"specifier_check_failed:{name}:{e!r}"
    return True, f"ok:{name}=={v}"


path = Path(sys.argv[1])
issues = []
for line in iter_req_lines(path):
    if line.startswith('__READ_ERROR__'):
        issues.append(line)
        continue
    if line.startswith('__UNSUPPORTED_LINE__'):
        issues.append(line)
        continue
    try:
        req = Requirement(line)
    except Exception as e:
        issues.append(f"parse_failed:{line}:{e!r}")
        continue
    ok, msg = ok_for_req(req)
    if not ok:
        issues.append(msg)

print(json.dumps({"ok": (len(issues) == 0), "issues": issues}, ensure_ascii=False))
"""
            r = subprocess.run(
                [str(py_cli), "-c", script, str(req_file)],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_creationflags_no_window(),
            )
            out = (r.stdout or "") + ("\n" + (r.stderr or "") if r.stderr else "")
            if r.returncode != 0:
                self._log(f"[deps] requirements check failed (rc={r.returncode}): {req_file}")
                if out.strip():
                    self._log(out.strip())
                return False, [f"check_rc:{r.returncode}"]

            # Parse last non-empty line as JSON
            import json

            last = ""
            for line in (out or "").splitlines():
                if line.strip():
                    last = line.strip()
            if not last:
                self._log(f"[deps] requirements check produced no output: {req_file}")
                return False, ["no_output"]
            try:
                payload = json.loads(last)
            except Exception:
                self._log(f"[deps] requirements check invalid output: {last[:200]}")
                return False, ["invalid_output"]
            if not isinstance(payload, dict):
                self._log(f"[deps] requirements check invalid payload type: {type(payload)}")
                return False, ["invalid_payload_type"]
            ok = bool(payload.get("ok", False))
            issues = payload.get("issues") or []
            if not isinstance(issues, list):
                try:
                    issues = list(issues)
                except Exception:
                    issues = [f"issues_not_list:{type(payload.get('issues')).__name__}"]
            if not ok:
                self._log(f"[deps] requirements NOT satisfied: {req_file}")
                try:
                    for it in list(issues)[:50]:
                        self._log(f"  - {it}")
                except Exception:
                    pass
                return False, [str(x) for x in issues]
            self._log(f"[deps] requirements satisfied: {req_file}")
            return True, []
        except Exception as e:
            self._log(f"[deps] WARN: requirements check crashed: {e!r}")
            return False, [f"check_crashed:{e!r}"]

    def _install_deps_sync(self) -> bool:
        """Install/validate dependencies in the shared venv.

        ABSOLUTE RULE (project policy):
        - There is NO "minimal" dependency mode.
        - The launcher installs ONLY `requirements.txt` and must never silently
          downgrade/skip features by switching to a smaller dependency set.

        Returns:
            True  -> deps are usable (installed or already satisfied)
            False -> deps are NOT usable (pip/venv failure). A human-readable message
                     must be shown and the failure must be logged.
        """
        if not REQ_FILE.exists():
            msg = f"requirements.txt не найден: {REQ_FILE}"
            self._log(f"❌ {msg}")
            _safe_messagebox_error("Ошибка зависимостей", msg)
            return False

        # Prevent concurrent pip on the same shared venv (different releases, same PC).
        lock_fd = _acquire_install_lock(DEPS_LOCK_FILE, timeout_s=45.0)
        if lock_fd is None:
            msg = (
                "Установка зависимостей уже выполняется другим процессом/релизом.\n\n"
                f"Lock: {DEPS_LOCK_FILE}\n\n"
                "Подожди завершения или закрой другой лаунчер."
            )
            self._log("❌ deps install lock busy")
            _safe_messagebox_warning("Зависимости заняты", msg)
            return False

        try:
            self._ui_status("Проверяю виртуальную среду…")

            if not self.ensure_venv():
                return False

            py_cli = _venv_python(prefer_gui=False)
            self._log(f"Python (shared venv) = {py_cli}")
            self._log(f"VENV_DIR = {VENV_DIR}")
            self._log(f"PIP_CACHE_DIR = {PIP_CACHE_DIR}")

            # If venv tooling is broken, try to repair pip (ensurepip) before anything else.
            pre = self._preflight_imports(py_cli)
            if not pre.get("ok", False):
                self._log(f"[deps] preflight failed before install: {pre.get('error')}")
                self._ui_status("Восстанавливаю pip (ensurepip)…")
                rc_ensure = self._run_cmd(
                    [str(py_cli), "-m", "ensurepip", "--upgrade"],
                    tee_file=DEPS_LOG,
                )
                if rc_ensure != 0:
                    msg = (
                        "Не удалось восстановить pip (ensurepip).\n\n"
                        f"rc={rc_ensure}\n"
                        f"Подробности см. {DEPS_LOG}"
                    )
                    self._log("❌ ensurepip failed")
                    _safe_messagebox_error("Ошибка зависимостей", msg)
                    return False            # Fast offline check: if already satisfied -> still verify that imports really work.
            # Shared venvs may contain stale dist-info after a broken install; metadata alone can lie.
            ok_full, issues_full = self._requirements_satisfied(py_cli, REQ_FILE)
            if ok_full:
                missing_pre = self._import_smoke_check(py_cli)
                if missing_pre:
                    self._log("⚠️ requirements metadata says OK, but import smoke failed; shared venv looks inconsistent")
                    for mod, err in list(missing_pre.items())[:50]:
                        self._log(f"  - {mod}: {err}")
                    self._ui_status("Окружение выглядит повреждённым — пересоздаю venv и переустанавливаю зависимости…")
                    if not self.ensure_venv(force_recreate=True):
                        return False
                    py_cli = _venv_python(prefer_gui=False)
                    self._log(f"Python (recreated shared venv) = {py_cli}")
                    self._log(f"VENV_DIR = {VENV_DIR}")
                    self._log(f"PIP_CACHE_DIR = {PIP_CACHE_DIR}")

                    pre = self._preflight_imports(py_cli)
                    if not pre.get("ok", False):
                        self._log(f"[deps] preflight failed after recreate: {pre.get('error')}")
                        self._ui_status("Восстанавливаю pip (ensurepip)…")
                        rc_ensure = self._run_cmd(
                            [str(py_cli), "-m", "ensurepip", "--upgrade"],
                            tee_file=DEPS_LOG,
                        )
                        if rc_ensure != 0:
                            msg = (
                                "Не удалось восстановить pip (ensurepip) после пересоздания venv.\n\n"
                                f"rc={rc_ensure}\n"
                                f"Подробности см. {DEPS_LOG}"
                            )
                            self._log("❌ ensurepip failed after recreate")
                            _safe_messagebox_error("Ошибка зависимостей", msg)
                            return False

                    ok_full, issues_full = self._requirements_satisfied(py_cli, REQ_FILE)
                    # Fresh venv is expected to fail this check until pip install completes.
                else:
                    self._log(f"✅ requirements satisfied: {REQ_FILE}")
                    self._ui_status("✅ Зависимости уже установлены (pip install пропущен)")
                    st = self._load_deps_state()
                    st.update(
                        {
                            "last_ok_release": RELEASE,
                            "last_ok_time": _now_utc_iso(),
                            "python": str(py_cli),
                            "req": str(REQ_FILE),
                        }
                    )
                    self._save_deps_state(st)
                    return True

            self._log(f"[deps] requirements NOT satisfied: {REQ_FILE}")
            for it in issues_full[:50]:
                self._log(f"  - {it}")
            if len(issues_full) > 50:
                self._log(f"  ... +{len(issues_full)-50} more")

            # Upgrade pip tooling (safe even if already latest)
            self._ui_status("Шаг 1/2: обновляю pip / setuptools / wheel…")
            rc = self._run_cmd(
                [
                    str(py_cli),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--progress-bar",
                    "off",
                    "--upgrade",
                    "pip",
                    "setuptools",
                    "wheel",
                ],
                tee_file=DEPS_LOG,
            )
            if rc != 0:
                msg = (
                    "Не удалось обновить pip/setuptools/wheel.\n\n"
                    f"rc={rc}\n"
                    f"Подробности см. {DEPS_LOG}"
                )
                self._log("❌ pip tooling upgrade failed")
                _safe_messagebox_error("Ошибка зависимостей", msg)
                return False

            # Install FULL requirements
            self._ui_status("Шаг 2/2: устанавливаю зависимости (pip install -r requirements.txt)…")
            rc = self._run_cmd(
                [
                    str(py_cli),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--progress-bar",
                    "off",
                    "--prefer-binary",
                    "-r",
                    str(REQ_FILE),
                ],
                tee_file=DEPS_LOG,
            )
            if rc != 0:
                msg = (
                    "pip install -r requirements.txt завершился с ошибкой.\n\n"
                    f"rc={rc}\n"
                    f"Подробности см. {DEPS_LOG}"
                )
                self._log("❌ pip install requirements.txt failed")
                _safe_messagebox_error("Ошибка установки", msg)
                return False

            # Re-check requirements to avoid false positives
            ok2, issues2 = self._requirements_satisfied(py_cli, REQ_FILE)
            if not ok2:
                self._log("⚠️ After install, requirements still NOT satisfied (unexpected)")
                for it in issues2[:50]:
                    self._log(f"  - {it}")
                msg = (
                    "Установка завершилась, но проверка требований всё ещё находит проблемы.\n\n"
                    "Это означает, что окружение может быть частично установлено или повреждено.\n\n"
                    f"Подробности см. {DEPS_LOG}"
                )
                _safe_messagebox_warning("Проверка зависимостей", msg)

            # Smoke import check for the main feature modules.
            # This is a hard gate: if imports still fail after install, launching the app would
            # produce a partially broken runtime and silent regressions.
            missing = self._import_smoke_check(py_cli)
            if missing:
                self._log("❌ Some modules failed to import after install:")
                for m, err in missing.items():
                    self._log(f"  - {m}: {err}")
                msg = (
                    "После установки часть обязательных модулей всё ещё не импортируется.\n\n"
                    "Запуск продолжать нельзя: окружение неполное или повреждено.\n\n"
                    + "\n".join([f"- {k}: {v}" for k, v in list(missing.items())[:12]])
                    + ("\n..." if len(missing) > 12 else "")
                    + "\n\nЧто делать:\n"
                    + f"1) Закрой все релизы приложения.\n2) Удали shared venv: {VENV_DIR}\n3) Запусти лаунчер снова.\n\n"
                    + f"Подробности см. {DEPS_LOG}"
                )
                _safe_messagebox_error("Ошибка зависимостей", msg)
                return False

            st = self._load_deps_state()
            st.update(
                {
                    "last_ok_release": RELEASE,
                    "last_ok_time": _now_utc_iso(),
                    "python": str(py_cli),
                    "req": str(REQ_FILE),
                }
            )
            self._save_deps_state(st)

            self._ui_status("✅ Зависимости установлены / проверены")
            return True
        finally:
            _release_install_lock(DEPS_LOCK_FILE, lock_fd)
    def install_deps(self) -> None:
        def worker() -> None:
            with self._lock:
                try:
                    self._install_deps_sync()
                except Exception as e:
                    tb = traceback.format_exc()
                    self._log("❌ install_deps crashed: " + repr(e))
                    try:
                        with open(DEPS_LOG, "a", encoding="utf-8", errors="replace") as f:
                            f.write("\nCRASH:\n" + tb + "\n")
                    except Exception:
                        pass
                    _safe_messagebox_error("Ошибка", f"Сбой установки зависимостей. См. логи в {LOG_DIR}")
                finally:
                    self._pbar_stop()

        threading.Thread(target=worker, daemon=True).start()

    def start_app(self) -> None:
        # guard
        with self._lock:
            if self.proc and self.proc.poll() is None:
                messagebox.showinfo("Уже запущено", "Приложение уже запущено.")
                return

        def worker() -> None:
            with self._lock:
                try:
                    # ВАЖНО: всегда пытаемся установить зависимости перед запуском
                    self._ui_status("Готовлю окружение: установка зависимостей …")
                    self._pbar_set(0)
                    ok = self._install_deps_sync()
                    if not ok:
                        return

                    show_console = bool(self.show_console_var.get())
                    py = _venv_python(prefer_gui=(not show_console))

                    try:
                        port = int(self.port_var.get().strip())
                    except Exception:
                        port = DEFAULT_PORT

                    # If port is occupied, start on the next free one.
                    # Otherwise we might silently attach the browser to an old instance
                    # (possibly another release / another venv) and get a fully broken UI.
                    preferred_port = port
                    port = _pick_free_port(preferred_port)
                    if port != preferred_port:
                        self._log(
                            f"Порт {preferred_port} уже занят (возможно запущена старая копия). "
                            f"Запускаю новый экземпляр на порту {port}..."
                        )
                        try:
                            self.port_var.set(str(port))
                        except Exception:
                            pass
                    elif _is_port_open(port):
                        # Extremely unlikely: could not find a free port in the scan window.
                        self._log(f"Порт {port} уже занят и не удалось подобрать свободный. Открываю браузер ...")
                        if self.open_browser_var.get():
                            _open_url_best_effort(f"http://127.0.0.1:{port}")
                        return

                    app_py = ROOT / "app.py"
                    if not app_py.exists():
                        _safe_messagebox_error("Ошибка", f"Не найден {app_py}")
                        return

                    # --- Testy R56: UI session isolation (logs/workspace) ---
                    run_id, session_dir, log_dir, workspace_dir, trace_id, env = self._prepare_child_session_env(
                        extra_env={
                            "PNEUMO_UI_PORT": str(port),
                            "PNEUMO_AUTO_SEND_BUNDLE": "1",
                            "PNEUMO_LAUNCH_SURFACE": "web_streamlit",
                        }
                    )
                    streamlit_log_path = log_dir / "streamlit_stdout.log"

                    # Run Registry: фиксируем старт UI-сессии (best-effort)
                    if start_run is not None:
                        try:
                            ctx = env_context() if env_context is not None else {}
                            anim_diag_event = _collect_anim_latest_registry_fields()
                            self.rr_token = start_run(
                                "ui_session",
                                run_id,
                                **ctx,
                                port=int(port),
                                session_dir=str(session_dir),
                                **anim_diag_event,
                            )
                        except Exception:
                            self.rr_token = None

                    # Стартуем Streamlit (при желании — с отдельной консолью)
                    cmd = [
                        str(py),
                        "-m",
                        "streamlit",
                        "run",
                        str(app_py),
                        "--server.address",
                        "127.0.0.1",
                        "--server.port",
                        str(port),
                        "--server.headless",
                        "true",
                        "--browser.gatherUsageStats",
                        "false",
                        "--server.runOnSave",
                        "false",
                        "--logger.level",
                        "warning",
                    ]

                    self._ui_status("Запускаю Streamlit сервер …")
                    self._pbar_start_indeterminate()
                    self.proc_kind = "web"
                    self.proc = self._launch_logged_process(
                        cmd=cmd,
                        env=env,
                        log_path=streamlit_log_path,
                        show_console=show_console,
                    )

                    # Мониторим завершение процесса, чтобы *всегда* собрать ZIP после закрытия UI
                    try:
                        self._start_proc_monitor(self.proc, kind="web")
                    except Exception:
                        pass

                    # Postmortem watchdog: если launcher упадёт, он сам соберёт ZIP (best-effort)
                    try:
                        self._spawn_watchdog(target_pid=int(self.proc.pid), session_dir=session_dir, env=env)
                    except Exception:
                        pass

                    # Ждём реального HTTP-ответа Streamlit, а не только открытого сокета.
                    # На Windows встречались ложные HTTP 502 при уже живом UI-сеансе,
                    # поэтому используем secondary readiness через session logs.
                    t0 = time.time()
                    ok_http = False
                    http_notes: list[str] = []
                    log_ready = False
                    log_ready_diag: dict | None = None
                    ready_source: str | None = None
                    while time.time() - t0 < 20.0:
                        ok_http, http_notes = _http_ready_once(port, host="127.0.0.1")
                        if ok_http:
                            ready_source = "http"
                            break
                        if _session_log_ready is not None:
                            try:
                                log_ready, log_ready_diag = _session_log_ready(log_dir)
                            except Exception:
                                log_ready, log_ready_diag = False, None
                            if log_ready:
                                ready_source = "session_log"
                                break
                        if self.proc and (self.proc.poll() is not None):
                            break
                        time.sleep(0.15)

                    self.launch_http_ready = bool(ok_http)
                    self.launch_http_notes = list(http_notes)
                    self.launch_ready_source = ready_source
                    self.launch_readiness_diag = dict(log_ready_diag or {}) if log_ready_diag else None

                    self._pbar_stop()
                    self._pbar_set(100)

                    if (not ok_http) and (not log_ready):
                        self._ui_status("❌ Streamlit не ответил по HTTP (см. streamlit log)")
                        self._log("❌ Streamlit не ответил по HTTP — см. streamlit_stdout.log")
                        try:
                            for note in http_notes[-6:]:
                                self._log(f"   probe: {note}")
                        except Exception:
                            pass
                        _safe_messagebox_error(
                            "Не удалось запустить",
                            "Streamlit не поднял рабочую веб-страницу.\n\n"
                            f"Проверь лог: {streamlit_log_path}\n"
                            f"Проверь адрес: http://127.0.0.1:{port}",
                        )
                        return

                    url_ipv4 = f"http://127.0.0.1:{port}"
                    url_localhost = f"http://localhost:{port}"
                    if ok_http:
                        self._ui_status(f"✅ UI запущен: {url_ipv4} (alt: {url_localhost})")
                        self._log(f"✅ UI запущен: {url_ipv4} (alt: {url_localhost})")
                    else:
                        self._ui_status(f"⚠️ UI запущен по логу сеанса: {url_ipv4} (HTTP probe failed)")
                        self._log(f"⚠️ HTTP probe failed; using session-log readiness fallback: {url_ipv4} (alt: {url_localhost})")
                        try:
                            for note in http_notes[-6:]:
                                self._log(f"   probe: {note}")
                            if log_ready_diag:
                                self._log(f"   session_ready: {json.dumps(log_ready_diag, ensure_ascii=False)}")
                        except Exception:
                            pass
                    if self.open_browser_var.get():
                        opened = _open_url_best_effort(url_ipv4)
                        if not opened:
                            self._log(f"⚠️ Не удалось автоматически открыть браузер: {url_ipv4}")


                except Exception as e:
                    tb = traceback.format_exc()
                    self._pbar_stop()
                    self._log("❌ start_app crashed: " + repr(e))
                    try:
                        with open(LAUNCHER_LOG, "a", encoding="utf-8", errors="replace") as f:
                            f.write("\nCRASH:\n" + tb + "\n")
                    except Exception:
                        pass
                    _safe_messagebox_error("Ошибка", f"Сбой запуска. См. логи в {LOG_DIR}")

        threading.Thread(target=worker, daemon=True).start()

    def start_desktop_shell(self) -> None:
        with self._lock:
            if self.proc and self.proc.poll() is None:
                messagebox.showinfo("Уже запущено", "Сначала остановите текущий процесс запуска.")
                return

        def worker() -> None:
            with self._lock:
                try:
                    self._ui_status("Готовлю окружение для главного Desktop Main Shell …")
                    self._pbar_set(0)
                    ok = self._install_deps_sync()
                    if not ok:
                        return

                    py = _venv_python(prefer_gui=False)
                    show_console = bool(self.show_console_var.get())
                    _, _, log_dir, _, _, env = self._prepare_child_session_env(
                        run_prefix="DESKTOP",
                        extra_env={
                            "PNEUMO_LAUNCH_SURFACE": "desktop_main_shell_qt",
                            "PNEUMO_DESKTOP_MAIN_SHELL_QT": "1",
                        },
                    )
                    desktop_log_path = log_dir / "desktop_main_shell_qt.log"
                    cmd = [
                        str(py),
                        "-m",
                        "pneumo_solver_ui.tools.desktop_main_shell_qt",
                    ]

                    self._ui_status("Запускаю главное Desktop Main Shell …")
                    self._pbar_start_indeterminate()
                    self.proc_kind = "desktop"
                    self.proc = self._launch_logged_process(
                        cmd=cmd,
                        env=env,
                        log_path=desktop_log_path,
                        show_console=show_console,
                    )
                    self._start_proc_monitor(self.proc, kind="desktop")

                    deadline = time.time() + 2.0
                    exited_early = False
                    while time.time() < deadline:
                        if self.proc and (self.proc.poll() is not None):
                            exited_early = True
                            break
                        time.sleep(0.1)

                    self._pbar_stop()
                    self._pbar_set(100)

                    if exited_early:
                        self._ui_status("❌ Desktop Main Shell завершился сразу (см. desktop log)")
                        self._log(f"❌ Desktop Main Shell завершился сразу — проверь лог: {desktop_log_path}")
                        _safe_messagebox_error(
                            "Не удалось запустить",
                            "Desktop Main Shell завершился сразу после старта.\n\n"
                            f"Проверь лог: {desktop_log_path}",
                        )
                        return

                    self._ui_status("✅ Desktop Main Shell запущен (через тот же bootstrap и venv).")
                    self._log(f"✅ Desktop Main Shell запущен. Лог: {desktop_log_path}")
                except Exception as e:
                    tb = traceback.format_exc()
                    self._pbar_stop()
                    self._log("❌ start_desktop_shell crashed: " + repr(e))
                    try:
                        with open(LAUNCHER_LOG, "a", encoding="utf-8", errors="replace") as f:
                            f.write("\nCRASH:\n" + tb + "\n")
                    except Exception:
                        pass
                    _safe_messagebox_error("Ошибка", f"Сбой запуска Desktop Main Shell. См. логи в {LOG_DIR}")

        threading.Thread(target=worker, daemon=True).start()

    def _stop_watchdog_proc(self) -> None:
        with self._lock:
            wp = self.watchdog_proc
            self.watchdog_proc = None
        if not wp:
            return
        try:
            if terminate_process_tree is not None:
                info = terminate_process_tree(wp, grace_sec=0.4, reason="launcher_watchdog_stop", log=lambda m: self._log(str(m)))
                self._log(f"[watchdog stop] {json.dumps(info, ensure_ascii=False)}")
            else:
                wp.terminate()
        except Exception as e:
            self._log(f"[WARN] watchdog stop failed: {e!r}")

    def stop_app(self, *, reason: str = "launcher_stop_app") -> None:
        with self._lock:
            p = self.proc
            self.proc = None
            proc_kind = self.proc_kind
        self._launcher_stop_requested = True
        self._launcher_stop_source = str(reason or "launcher_stop_app")
        self._log(f"[stop_app request] source={self._launcher_stop_source} kind={proc_kind or 'unknown'}")
        if p is not None:
            try:
                if terminate_process_tree is not None:
                    info = terminate_process_tree(
                        p,
                        grace_sec=1.2,
                        reason=f"launcher_stop_app:{self._launcher_stop_source or reason}",
                        log=lambda m: self._log(str(m)),
                    )
                    self._log(f"[stop_app tree] {json.dumps(info, ensure_ascii=False)}")
                else:
                    p.terminate()
                    try:
                        p.wait(timeout=1.2)
                    except Exception:
                        p.kill()
                self._log("Остановил процесс Streamlit и его дочернее дерево.")
                self._ui_status("Остановлено.")
            except Exception as e:
                self._log(f"Не удалось остановить: {e}")
        self._stop_watchdog_proc()
        self._close_active_log_handle()

    def _start_proc_monitor(self, proc: subprocess.Popen, *, kind: str) -> None:
        """Ждём завершения streamlit процесса и запускаем postmortem сборку (UI-thread safe)."""

        def _waiter():
            rc = None
            try:
                rc = proc.wait()
            except Exception:
                rc = None
            try:
                # schedule on Tk main thread
                self.root.after(0, lambda: self._handle_child_exit(kind, rc))
            except Exception:
                # last resort
                try:
                    self._handle_child_exit(kind, rc)
                except Exception:
                    pass

        threading.Thread(target=_waiter, daemon=True).start()

    def _handle_child_exit(self, kind: str, rc: int | None) -> None:
        if kind == "desktop":
            self._handle_desktop_exit(rc)
            return
        self._handle_streamlit_exit(rc)

    def _spawn_watchdog(self, *, target_pid: int, session_dir: Path, env: dict) -> None:
        """Запускаем watchdog, который вмешается, если launcher умрёт раньше streamlit."""
        try:
            pyw = _venv_python(prefer_gui=True)
            wd = ROOT / "pneumo_solver_ui" / "tools" / "postmortem_watchdog.py"
            cmd = [
                str(pyw),
                str(wd),
                "--target_pid",
                str(int(target_pid)),
                "--launcher_pid",
                str(int(os.getpid())),
                "--session_dir",
                str(session_dir),
                "--open_send_gui",
            ]
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            self.watchdog_proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, creationflags=creationflags)
        except Exception as e:
            self._log("[WARN] watchdog spawn failed: " + repr(e) + "\n")

    def _handle_streamlit_exit(self, rc: int | None) -> None:
        """Выполняется один раз при завершении streamlit. Собирает ZIP и открывает 1-кнопочный GUI."""
        if self._exit_handled:
            return
        self._exit_handled = True

        stop_src = self._launcher_stop_source or ""
        self._log(
            f"[UI EXIT] streamlit terminated rc={rc} stop_requested={self._launcher_stop_requested} stop_source={stop_src or 'none'}\n"
        )
        self._ui_status("Завершено. Собираю ZIP результатов…")

        # launcher-side helpers must not linger after explicit stop/exit
        try:
            self._stop_watchdog_proc()
        except Exception:
            pass
        self.proc_kind = None
        self._close_active_log_handle()

        # Run Registry: фиксируем завершение
        try:
            if self.rr_token is not None and end_run is not None:
                if rc in (0, None):
                    status = "ok"
                elif self._launcher_stop_requested:
                    status = "stopped"
                elif self.launch_ready_source == "session_log":
                    status = "degraded"
                else:
                    status = "fail"
                anim_diag_event = _collect_anim_latest_registry_fields()
                end_run(
                    self.rr_token,
                    status=status,
                    rc=rc if rc is not None else 0,
                    launcher_http_ready=bool(self.launch_http_ready),
                    launcher_ready_source=self.launch_ready_source or "none",
                    launcher_http_notes=list(self.launch_http_notes or []),
                    launcher_log_readiness=dict(self.launch_readiness_diag or {}),
                    launcher_stop_requested=bool(self._launcher_stop_requested),
                    launcher_stop_source=(self._launcher_stop_source or None),
                    **anim_diag_event,
                )
        except Exception:
            pass

        # Запускаем send_results_gui (оно само соберёт ZIP на диск и даст 1 кнопку копирования)
        try:
            # Use console python.exe (hidden window on Windows) instead of pythonw.exe.
            # Reason: this helper performs substantial diagnostics/ZIP work and must share
            # the exact shared-venv package set with pip/log helpers. CREATE_NO_WINDOW keeps
            # the UX windowless without relying on pythonw-specific runtime behaviour.
            py_cli = _venv_python(prefer_gui=False)
            send_gui = ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py"
            env = self._child_env or os.environ.copy()
            env["PNEUMO_SHARED_VENV_PYTHON"] = str(py_cli)
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            self._log(f"[send_results_gui] PY={py_cli}\n")
            subprocess.Popen([str(py_cli), str(send_gui)], cwd=str(ROOT), env=env, creationflags=creationflags)
            try:
                if append_event is not None:
                    anim_diag_event = _collect_anim_latest_registry_fields()
                    append_event(
                        {
                            "event": "send_results_gui_spawned",
                            "run_type": "ui_session",
                            "run_id": self.run_id or "UI",
                            "session_dir": str(self.session_dir) if self.session_dir else None,
                            "send_results_gui_python": str(py_cli),
                            **anim_diag_event,
                        }
                    )
            except Exception:
                pass
        except Exception as e:
            self._log(f"[WARN] cannot launch send_results_gui: {e!r}\n")

        self._ui_status("ZIP собран/собирается. Окно отправки откроется отдельно.")

        # Если закрытие инициировано пользователем — закрываем launcher после запуска send GUI
        if self._close_requested:
            try:
                self.root.after(250, self.root.destroy)
            except Exception:
                pass

    def _handle_desktop_exit(self, rc: int | None) -> None:
        if self._exit_handled:
            return
        self._exit_handled = True

        log_path = self.active_log_path
        self.proc_kind = None
        self._close_active_log_handle()

        stop_src = self._launcher_stop_source or ""
        self._log(
            f"[DESKTOP EXIT] rc={rc} stop_requested={self._launcher_stop_requested} stop_source={stop_src or 'none'}\n"
        )
        if self._launcher_stop_requested:
            self._ui_status("Остановлено.")
        elif rc in (0, None):
            self._ui_status("Desktop Main Shell завершён.")
        else:
            self._ui_status("❌ Desktop Main Shell завершился с ошибкой (см. desktop log)")
            if log_path is not None:
                _safe_messagebox_error(
                    "Desktop Main Shell",
                    "Desktop Main Shell завершился с ошибкой.\n\n"
                    f"Проверь лог: {log_path}",
                )
        if self._close_requested:
            try:
                self.root.destroy()
            except Exception:
                pass


    def open_logs_dir(self) -> None:
        try:
            target = None
            if self.session_dir is not None:
                target = self.session_dir / "logs"
            else:
                # fallback
                target = LOG_DIR
            if os.name == "nt":
                os.startfile(target)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:
            _safe_messagebox_error("Логи", f"Не удалось открыть папку логов: {e}")


    def open_deps_log(self) -> None:
        """Открыть deps_install.log (журнал авто‑установки зависимостей).

        Это callback для кнопки в UI лаунчера. Если метода нет, Tkinter
        падает ещё при сборке интерфейса. Поэтому держим реализацию максимально
        простой и надёжной.
        """

        # install_deps() пишет в общий LOG_DIR/deps_install.log,
        # но если в будущем появится сессионный лог — открываем его в приоритете.
        candidates: list[Path] = []
        try:
            if self.session_dir is not None:
                candidates.append(self.session_dir / "logs" / "deps_install.log")
        except Exception:
            pass
        candidates.append(DEPS_LOG)

        target: Path | None = None
        for p in candidates:
            try:
                if p.exists():
                    target = p
                    break
            except Exception:
                continue

        if target is None:
            messagebox.showinfo(
                "Нет файла",
                "deps_install.log пока не создан.\n\n"
                "Нажмите 'Только установить зависимости' или 'Запустить'.",
            )
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", str(target)])  # noqa: S603,S607
        except Exception as e:
            self._log(f"open_deps_log failed: {e}")


    def open_streamlit_log(self) -> None:
        if not STREAMLIT_LOG.exists():
            messagebox.showinfo("Нет файла", f"{STREAMLIT_LOG} пока не создан.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(STREAMLIT_LOG))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(STREAMLIT_LOG)])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", str(STREAMLIT_LOG)])  # noqa: S603,S607
        except Exception as e:
            self._log(f"open_streamlit_log failed: {e}")

    def open_desktop_log(self) -> None:
        candidates: list[Path] = []
        try:
            if self.active_log_path is not None and self.active_log_path.name == "desktop_main_shell_qt.log":
                candidates.append(self.active_log_path)
        except Exception:
            pass
        try:
            if self.session_dir is not None:
                candidates.append(self.session_dir / "logs" / "desktop_main_shell_qt.log")
        except Exception:
            pass

        target: Path | None = None
        for p in candidates:
            try:
                if p.exists():
                    target = p
                    break
            except Exception:
                continue

        if target is None:
            messagebox.showinfo("Нет файла", "desktop_main_shell_qt.log пока не создан.")
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", str(target)])  # noqa: S603,S607
        except Exception as e:
            self._log(f"open_desktop_log failed: {e}")

    def on_close(self) -> None:
        # Testy R56: если UI запущен — корректно останавливаем и после этого собираем ZIP.
        try:
            if self.proc is not None and self.proc.poll() is None:
                self._close_requested = True
                self.stop_app(reason="window_close")
                # _handle_streamlit_exit закроет launcher после запуска send_results_gui
                return
        except Exception:
            pass
        self.root.destroy()



def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    LauncherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc()
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(LAUNCHER_LOG, "a", encoding="utf-8", errors="replace") as f:
                f.write("\nFATAL:\n" + tb + "\n")
        except Exception:
            pass
        _safe_messagebox_error(
            "Launcher crashed",
            "Лаунчер упал ещё до открытия окна.\n\n"
            f"Ошибка: {e!r}\n\n"
            f"Лог: {LAUNCHER_LOG}",
        )
