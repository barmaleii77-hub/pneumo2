from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_autotest_quick_computation_path_passes(tmp_path: Path) -> None:
    out_root = tmp_path / "autotest_runs"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.run_autotest",
            "--level",
            "quick",
            "--no_zip",
            "--out_root",
            str(out_root),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "=== AUTOTEST FINISHED ===" in proc.stdout

    run_dirs = [p for p in out_root.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    summary = json.loads((run_dirs[0] / "summary" / "summary.json").read_text(encoding="utf-8"))
    assert bool(summary["ok"]) is True
    assert int(summary["rc"]) == 0


def test_run_autotest_script_help_bootstraps_package_context() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "run_autotest.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "run_autotest.py" in proc.stdout
    assert "--level" in proc.stdout
