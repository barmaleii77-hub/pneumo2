from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fast_kpi_worldroad_runs_as_module_and_emits_json() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.fast_kpi_worldroad",
            "--dt",
            "0.01",
            "--t-end",
            "0.05",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    assert float(payload["dt"]) > 0.0
    assert float(payload["t_end"]) >= 0.05
    assert payload["wheel_coord_mode"] in {"center", "contact"}
    assert "pR3_max_bar_abs" in payload
    assert "smooth" in payload
