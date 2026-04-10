from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_line_losses_report_runs_as_module() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.line_losses_report"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "# Line losses report" in proc.stdout
    assert "| edge | factor |" in proc.stdout
