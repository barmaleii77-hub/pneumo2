from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_full_diagnostics_script_help_bootstraps_package_context() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "run_full_diagnostics.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "run_full_diagnostics.py" in proc.stdout
    assert "--skip_ui_smoke" in proc.stdout
