from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from pneumo_solver_ui.process_tree import terminate_process_tree

ROOT = Path(__file__).resolve().parents[1]


def _spawn_parent_with_child() -> subprocess.Popen[str]:
    code = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print(child.pid, flush=True); time.sleep(30)"
    )
    return subprocess.Popen(
        [sys.executable, '-c', code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_r31bl_terminate_process_tree_kills_parent_and_child() -> None:
    parent = _spawn_parent_with_child()
    assert parent.stdout is not None
    child_pid_line = parent.stdout.readline().strip()
    assert child_pid_line
    child_pid = int(child_pid_line)
    info = terminate_process_tree(parent, grace_sec=0.4, reason='pytest')
    time.sleep(0.4)
    assert parent.poll() is not None
    try:
        import psutil  # type: ignore
        assert not psutil.pid_exists(child_pid)
    except Exception:
        pytest.skip('psutil unavailable')
    assert info['pid'] == parent.pid


def test_r31bl_launcher_uses_process_tree_shutdown() -> None:
    src = (ROOT / 'START_PNEUMO_APP.py').read_text(encoding='utf-8', errors='replace')
    assert 'terminate_process_tree' in src
    assert '_stop_watchdog_proc' in src
    assert 'Остановил процесс Streamlit и его дочернее дерево.' in src


def test_r31bl_optimization_hard_stop_uses_process_tree_shutdown() -> None:
    src_ui = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8', errors='replace')
    src_app = (ROOT / 'pneumo_solver_ui' / 'app.py').read_text(encoding='utf-8', errors='replace')
    assert 'terminate_process_tree(p, grace_sec=0.8, reason="optimization_hard_stop")' in src_ui
    assert 'terminate_process_tree(p, grace_sec=0.8, reason="optimization_hard_stop")' in src_app
