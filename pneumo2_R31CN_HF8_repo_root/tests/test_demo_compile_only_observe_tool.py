from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_demo_compile_only_observe_runs_as_module() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.demo_compile_only_observe"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "=== compile_only demo summary ===" in proc.stdout
    assert "max |z_body|" in proc.stdout


def test_demo_compile_only_observe_runs_as_script() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "demo_compile_only_observe.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "=== compile_only demo summary ===" in proc.stdout
    assert "max |z_body|" in proc.stdout
