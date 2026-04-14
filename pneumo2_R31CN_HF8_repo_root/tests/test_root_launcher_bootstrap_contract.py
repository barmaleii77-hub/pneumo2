from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pneumo_solver_ui.root_launcher_bootstrap as bootstrap


ROOT = Path(__file__).resolve().parents[1]


class _FakeLauncherGUI:
    def _run_cmd(self, *_args, **_kwargs) -> int:
        return 0

    def ensure_venv(self, *_args, **_kwargs) -> bool:
        return True

    def _load_deps_state(self) -> dict:
        return {}

    def _save_deps_state(self, _state: dict) -> None:
        return None

    def _preflight_imports(self, _py_cli: Path) -> dict[str, object]:
        return {"ok": True, "error": None}

    def _requirements_satisfied(self, _py_cli: Path, _req_file: Path) -> tuple[bool, list[str]]:
        return True, []

    def _import_smoke_check(self, _py_cli: Path) -> dict[str, str]:
        return {}

    def _install_deps_sync(self) -> bool:
        return True


def _fake_launcher(*, cli_python: Path, gui_python: Path | None = None) -> SimpleNamespace:
    gui_value = gui_python or cli_python
    return SimpleNamespace(
        LauncherGUI=_FakeLauncherGUI,
        _venv_python=lambda *, prefer_gui=False: gui_value if prefer_gui else cli_python,
        _creationflags_no_window=lambda: 0x08000000,
        _safe_messagebox_error=lambda *_args, **_kwargs: None,
        _boot_log=lambda *_args, **_kwargs: None,
        _log=lambda *_args, **_kwargs: None,
    )


def test_root_launcher_bootstrap_skips_reexec_when_current_python_matches_shared_runtime() -> None:
    shared_python = Path("C:/runtime/Scripts/python.exe")
    result = bootstrap.ensure_root_launcher_runtime(
        root=ROOT,
        script_path=ROOT / "START_DESKTOP_MAIN_SHELL.py",
        module="pneumo_solver_ui.tools.desktop_main_shell_qt",
        argv=("--list-tools",),
        current_executable=shared_python,
        launcher_module=_fake_launcher(cli_python=shared_python),
        prefer_gui=False,
    )

    assert result is None


def test_root_launcher_bootstrap_skips_shared_venv_when_current_runtime_can_import_target(
    monkeypatch,
    tmp_path: Path,
) -> None:
    shared_python = tmp_path / "shared" / "Scripts" / "python.exe"
    shared_python.parent.mkdir(parents=True, exist_ok=True)
    shared_python.write_text("", encoding="utf-8")

    install_called = {"value": False}

    class _FailIfInstalledLauncherGUI(_FakeLauncherGUI):
        def _install_deps_sync(self) -> bool:
            install_called["value"] = True
            return True

    launcher = SimpleNamespace(
        LauncherGUI=_FailIfInstalledLauncherGUI,
        _venv_python=lambda *, prefer_gui=False: shared_python,
        _creationflags_no_window=lambda: 0x08000000,
        _safe_messagebox_error=lambda *_args, **_kwargs: None,
        _boot_log=lambda *_args, **_kwargs: None,
        _log=lambda *_args, **_kwargs: None,
    )

    monkeypatch.setattr(bootstrap, "_current_runtime_can_import", lambda _module: True)

    result = bootstrap.ensure_root_launcher_runtime(
        root=ROOT,
        script_path=ROOT / "START_DESKTOP_MAIN_SHELL.py",
        module="pneumo_solver_ui.tools.desktop_main_shell_qt",
        argv=(),
        current_executable=Path("C:/Python313/python.exe"),
        launcher_module=launcher,
        prefer_gui=False,
    )

    assert result is None
    assert install_called["value"] is False


def test_root_launcher_bootstrap_reexecs_console_launcher_through_shared_runtime(
    monkeypatch,
    tmp_path: Path,
) -> None:
    shared_python = tmp_path / "shared" / "Scripts" / "python.exe"
    shared_python.parent.mkdir(parents=True, exist_ok=True)
    shared_python.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_run(cmd: list[str], **kwargs) -> SimpleNamespace:
        captured["cmd"] = list(cmd)
        captured["kwargs"] = dict(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bootstrap.subprocess, "run", _fake_run)
    monkeypatch.setattr(bootstrap, "_current_runtime_can_import", lambda _module: False)

    result = bootstrap.ensure_root_launcher_runtime(
        root=ROOT,
        script_path=ROOT / "START_DESKTOP_MAIN_SHELL.py",
        module="pneumo_solver_ui.tools.desktop_main_shell_qt",
        argv=("--list-tools",),
        current_executable=Path("C:/Python314/python.exe"),
        launcher_module=_fake_launcher(cli_python=shared_python),
        prefer_gui=False,
    )

    assert result == 0
    assert captured["cmd"] == [
        str(shared_python),
        str(ROOT / "START_DESKTOP_MAIN_SHELL.py"),
        "--list-tools",
    ]


def test_root_launcher_bootstrap_reexecs_gui_launcher_hidden(
    monkeypatch,
    tmp_path: Path,
) -> None:
    shared_python = tmp_path / "shared" / "Scripts" / "python.exe"
    shared_pythonw = tmp_path / "shared" / "Scripts" / "pythonw.exe"
    shared_python.parent.mkdir(parents=True, exist_ok=True)
    shared_python.write_text("", encoding="utf-8")
    shared_pythonw.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_popen(cmd: list[str], **kwargs) -> SimpleNamespace:
        captured["cmd"] = list(cmd)
        captured["kwargs"] = dict(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(bootstrap.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(bootstrap, "_current_runtime_can_import", lambda _module: False)

    result = bootstrap.ensure_root_launcher_runtime(
        root=ROOT,
        script_path=ROOT / "START_DESKTOP_MAIN_SHELL.py",
        module="pneumo_solver_ui.tools.desktop_main_shell_qt",
        argv=(),
        current_executable=Path("C:/Python314/pythonw.exe"),
        launcher_module=_fake_launcher(
            cli_python=shared_python,
            gui_python=shared_pythonw,
        ),
        prefer_gui=True,
    )

    assert result == 0
    assert captured["cmd"] == [
        str(shared_pythonw),
        str(ROOT / "START_DESKTOP_MAIN_SHELL.py"),
    ]
    assert int(captured["kwargs"]["creationflags"]) == 0x08000000
