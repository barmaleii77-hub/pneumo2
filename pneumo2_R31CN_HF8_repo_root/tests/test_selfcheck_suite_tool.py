from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _assert_report_created(out_dir: Path) -> None:
    report_path = out_dir / "selfcheck_report.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "selfcheck_report"
    assert payload["summary"]["level"] == "quick"
    assert payload["summary"]["steps_total"] >= 3


def test_selfcheck_suite_runs_as_module(tmp_path: Path) -> None:
    out_dir = tmp_path / "selfcheck_suite_module"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.selfcheck_suite",
            "--level",
            "quick",
            "--out_dir",
            str(out_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    _assert_report_created(out_dir)


def test_selfcheck_suite_runs_as_script(tmp_path: Path) -> None:
    out_dir = tmp_path / "selfcheck_suite_script"
    script = ROOT / "pneumo_solver_ui" / "tools" / "selfcheck_suite.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--level",
            "quick",
            "--out_dir",
            str(out_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    _assert_report_created(out_dir)
