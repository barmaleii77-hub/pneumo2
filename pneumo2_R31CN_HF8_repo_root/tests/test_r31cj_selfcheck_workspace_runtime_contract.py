from __future__ import annotations

import os
from pathlib import Path

from pneumo_solver_ui.tools import selfcheck_suite as ss
from pneumo_solver_ui.workspace_contract import (
    REQUIRED_WORKSPACE_DIRS,
    ensure_workspace_contract_dirs,
    missing_workspace_contract_dirs,
    resolve_effective_workspace_dir,
)

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_contract_helpers_resolve_env_and_bootstrap_required_dirs(tmp_path: Path, monkeypatch) -> None:
    ws = tmp_path / 'session_workspace'
    monkeypatch.setenv('PNEUMO_WORKSPACE_DIR', str(ws))

    resolved = resolve_effective_workspace_dir(tmp_path)
    assert resolved == ws.resolve()

    assert missing_workspace_contract_dirs(resolved) == list(REQUIRED_WORKSPACE_DIRS)
    ensure_workspace_contract_dirs(resolved, include_optional=False)
    assert missing_workspace_contract_dirs(resolved) == []


def test_selfcheck_prefers_shared_venv_python_envvar(tmp_path: Path, monkeypatch) -> None:
    scripts = tmp_path / 'Scripts'
    scripts.mkdir(parents=True, exist_ok=True)
    py = scripts / 'python.exe'
    py.write_text('', encoding='utf-8')
    monkeypatch.setenv('PNEUMO_SHARED_VENV_PYTHON', str(py))

    assert ss._resolve_cli_python_executable() == str(py)


def test_launcher_and_selfcheck_sources_wire_workspace_contract_and_integrator_smoke() -> None:
    launcher_src = (ROOT / 'START_PNEUMO_APP.py').read_text(encoding='utf-8', errors='replace')
    selfcheck_src = (ROOT / 'pneumo_solver_ui' / 'tools' / 'selfcheck_suite.py').read_text(encoding='utf-8', errors='replace')

    assert 'ensure_workspace_contract_dirs(session / "workspace", include_optional=True)' in launcher_src
    assert 'resolve_effective_workspace_dir(repo_root, env=env)' in selfcheck_src
    assert 'name="integrator_autotune_smoke"' in selfcheck_src
    assert 'pneumo_solver_ui.tools.integrator_autotune_smoke_check' in selfcheck_src
