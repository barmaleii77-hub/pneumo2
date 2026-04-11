from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_preflight_gate_runs_as_module_and_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.preflight_gate"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "=== PREFLIGHT GATE ===" in proc.stdout
    assert "STATUS: PASS" in proc.stdout
    assert "iso_network_bottleneck_report: OK" in proc.stdout
