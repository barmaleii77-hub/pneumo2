"""Shared dependency bootstrap for root-level desktop launchers.

Desktop root launchers are shipped beside the source tree in the portable
release. When an operator starts them directly, Windows can pick a system
Python that does not yet have the project dependencies installed. The historic
web launcher already owns the shared-venv workflow, so these desktop launchers
reuse that bootstrap and then re-exec themselves inside the shared runtime.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
from collections.abc import Sequence
from pathlib import Path
from typing import Any


ROOT_BOOTSTRAP_ENV = "PNEUMO_ROOT_LAUNCHER_BOOTSTRAPPED"


def _normalize_path(value: str | os.PathLike[str] | None) -> str:
    if value is None:
        return ""
    try:
        return str(Path(value).resolve()).casefold()
    except Exception:
        return str(value).casefold()


def _same_python(current: str | os.PathLike[str] | None, expected: str | os.PathLike[str] | None) -> bool:
    current_norm = _normalize_path(current)
    expected_norm = _normalize_path(expected)
    return bool(current_norm) and current_norm == expected_norm


def _infer_prefer_gui(prefer_gui: bool | None = None) -> bool:
    if prefer_gui is not None:
        return bool(prefer_gui)
    exe_name = Path(sys.executable).name.casefold()
    return exe_name == "pythonw.exe"


def _fallback_log(root: Path, message: str) -> None:
    try:
        log_path = root / "pneumo_solver_ui" / "logs" / "desktop_root_launcher_bootstrap.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def _show_error(title: str, message: str) -> None:
    try:
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000010)
            return
    except Exception:
        pass
    try:
        print(title, file=sys.stderr)
        print(message, file=sys.stderr)
    except Exception:
        pass


def _load_web_launcher_module(root: Path) -> Any:
    cwd = Path.cwd()
    try:
        os.chdir(str(root))
        import START_PNEUMO_APP as launcher_module

        return launcher_module
    finally:
        try:
            os.chdir(str(cwd))
        except Exception:
            pass


class _HeadlessBootstrapRunner:
    """Minimal adapter over START_PNEUMO_APP.LauncherGUI dependency helpers."""

    _DELEGATED_METHODS = (
        "_run_cmd",
        "ensure_venv",
        "_load_deps_state",
        "_save_deps_state",
        "_preflight_imports",
        "_requirements_satisfied",
        "_import_smoke_check",
        "_install_deps_sync",
    )

    def __init__(self, launcher_module: Any, *, root: Path) -> None:
        self.launcher_module = launcher_module
        self.root = Path(root)

        launcher_gui = getattr(launcher_module, "LauncherGUI", None)
        if launcher_gui is None:
            raise RuntimeError("START_PNEUMO_APP.LauncherGUI is unavailable")

        for name in self._DELEGATED_METHODS:
            method = getattr(launcher_gui, name, None)
            if callable(method):
                setattr(self, name, types.MethodType(method, self))

    def _log(self, message: str) -> None:
        line = f"[desktop-root] {message}"
        try:
            top_level_log = getattr(self.launcher_module, "_log", None)
            if callable(top_level_log):
                top_level_log(line)
        except Exception:
            pass
        try:
            boot_log = getattr(self.launcher_module, "_boot_log", None)
            if callable(boot_log):
                boot_log(line)
        except Exception:
            pass
        _fallback_log(self.root, line)

    def _ui_status(self, text: str) -> None:
        self._log(f"status: {text}")

    def _pbar_set(self, _value: float) -> None:
        return None

    def _pbar_start_indeterminate(self) -> None:
        return None

    def _pbar_stop(self) -> None:
        return None

    def install_deps_sync(self) -> bool:
        installer = getattr(self, "_install_deps_sync", None)
        if not callable(installer):
            raise RuntimeError("START_PNEUMO_APP bootstrap installer is unavailable")
        return bool(installer())


def ensure_root_launcher_runtime(
    *,
    root: Path,
    script_path: Path,
    module: str,
    prefer_gui: bool | None = None,
    argv: Sequence[str] | None = None,
    current_executable: str | os.PathLike[str] | None = None,
    launcher_module: Any | None = None,
) -> int | None:
    """Ensure root launcher runs inside the shared project runtime.

    Returns:
        ``None`` when the caller should continue locally and run the target
        module in the current process.
        Integer exit code when the helper already handled re-exec or reported
        a fatal bootstrap error.
    """

    root = Path(root).resolve()
    script_path = Path(script_path).resolve()
    runtime_argv = list(argv if argv is not None else sys.argv[1:])
    use_gui_python = _infer_prefer_gui(prefer_gui)
    active_python = Path(current_executable or sys.executable)

    try:
        launcher_module = launcher_module or _load_web_launcher_module(root)
    except Exception as exc:
        tb = f"Failed to import START_PNEUMO_APP for {module}: {exc!r}"
        _fallback_log(root, tb)
        _show_error(
            "Desktop launcher bootstrap failed",
            "Не удалось подключить bootstrap исторического launcher.\n\n"
            f"Модуль: {module}\n"
            f"Ошибка: {exc!r}\n\n"
            f"Лог: {root / 'pneumo_solver_ui' / 'logs' / 'desktop_root_launcher_bootstrap.log'}",
        )
        return 1

    desired_python = Path(launcher_module._venv_python(prefer_gui=use_gui_python))
    if _same_python(active_python, desired_python):
        return None

    runner = _HeadlessBootstrapRunner(launcher_module, root=root)
    runner._log(
        "Preparing shared runtime "
        f"for {module}: current={active_python} desired={desired_python} gui={use_gui_python}"
    )

    if not runner.install_deps_sync():
        runner._log(f"Dependency bootstrap failed for {module}")
        return 1

    desired_python = Path(launcher_module._venv_python(prefer_gui=use_gui_python))
    if not desired_python.exists():
        runner._log(f"Desired shared python missing after bootstrap: {desired_python}")
        safe_messagebox_error = getattr(launcher_module, "_safe_messagebox_error", None)
        message = (
            "Не удалось найти Python в shared venv после подготовки зависимостей.\n\n"
            f"Модуль: {module}\n"
            f"Ожидался путь: {desired_python}"
        )
        if callable(safe_messagebox_error):
            try:
                safe_messagebox_error("Desktop launcher bootstrap failed", message)
            except Exception:
                _show_error("Desktop launcher bootstrap failed", message)
        else:
            _show_error("Desktop launcher bootstrap failed", message)
        return 1

    if _same_python(active_python, desired_python):
        return None

    env = os.environ.copy()
    env[ROOT_BOOTSTRAP_ENV] = "1"
    env.setdefault(
        "PNEUMO_SHARED_VENV_PYTHON",
        str(launcher_module._venv_python(prefer_gui=False)),
    )
    cmd = [str(desired_python), str(script_path), *runtime_argv]
    runner._log(f"Re-exec via shared runtime: {' '.join(cmd)}")

    if use_gui_python:
        creationflags = 0
        no_window = getattr(launcher_module, "_creationflags_no_window", None)
        if callable(no_window):
            try:
                creationflags = int(no_window())
            except Exception:
                creationflags = 0
        subprocess.Popen(
            cmd,
            cwd=str(root),
            env=env,
            creationflags=creationflags,
        )
        return 0

    completed = subprocess.run(
        cmd,
        cwd=str(root),
        env=env,
        check=False,
    )
    return int(completed.returncode)
