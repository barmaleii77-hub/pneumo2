from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_integrator_autotune_smoke_direct_script_runs_ok() -> None:
    proc = subprocess.run(
        [sys.executable, str(UI_ROOT / "tools" / "integrator_autotune_smoke_check.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "PASS integrator_autotune:" in proc.stdout
