from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_worldroad_hotpath_bench_runs_as_module():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.worldroad_hotpath_bench",
            "--reps",
            "2",
            "--warmup",
            "0",
            "--profile-top",
            "0",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "simulate_best_s=" in proc.stdout
    assert "simulate_median_s=" in proc.stdout
