from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_contact_models_property_check_help_and_run() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "contact_models_property_check.py"

    help_proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert help_proc.returncode == 0, help_proc.stderr or help_proc.stdout
    assert "Check energy-consistency of smooth contact models" in help_proc.stdout
    assert "--model-path" in help_proc.stdout

    run_proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run_proc.returncode == 0, run_proc.stderr or run_proc.stdout
    assert "OK: contact_models_property_check" in run_proc.stdout


def test_thermo_energy_smoke_check_help_and_run() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "thermo_energy_smoke_check.py"

    help_proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert help_proc.returncode == 0, help_proc.stderr or help_proc.stdout
    assert "Quick thermodynamic smoke-check for the v8 model." in help_proc.stdout
    assert "--t-end" in help_proc.stdout

    run_proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run_proc.returncode == 0, run_proc.stderr or run_proc.stdout
    assert "thermo_energy_smoke_check:" in run_proc.stdout
