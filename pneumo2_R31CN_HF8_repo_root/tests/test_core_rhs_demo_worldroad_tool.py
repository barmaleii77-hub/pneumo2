from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_core_rhs_demo_worldroad_runs_as_module() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.core_rhs_demo_worldroad"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "--- compile_only core exported ---" in proc.stdout
    assert "--- RHS at t=0 ---" in proc.stdout


def test_worldroad_compile_only_demo_emits_json_summary() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.worldroad_compile_only_demo"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    assert payload["note"] == "compile_only demo (no pandas DataFrame build)"
    assert float(payload["dt_s"]) > 0.0
    assert int(payload["n_steps"]) >= 1
