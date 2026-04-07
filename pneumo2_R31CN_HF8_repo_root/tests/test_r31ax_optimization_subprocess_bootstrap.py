from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PNEUMO = ROOT / "pneumo_solver_ui"


def _run_help(rel_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, rel_path, "--help"],
        cwd=str(PNEUMO),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _run_help_from_root(rel_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, rel_path, "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_r31ax_worker_help_runs_from_package_cwd() -> None:
    proc = _run_help("opt_worker_v3_margins_energy.py")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "--model" in proc.stdout
    assert "--out" in proc.stdout


def test_r31ax_system_influence_help_runs_from_package_cwd() -> None:
    proc = _run_help("calibration/system_influence_report_v1.py")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "--run_dir" in proc.stdout
    assert "--base_json" in proc.stdout


def test_r31ax_time_align_help_runs_from_package_cwd() -> None:
    proc = _run_help("calibration/time_align_v1.py")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "--osc_dir" in proc.stdout


def test_r31ax_stage_runner_injects_pythonpath_for_subprocesses() -> None:
    src = (PNEUMO / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert "def _prepend_pythonpath" in src
    assert 'env["PYTHONPATH"]' in src
    assert "_prepend_pythonpath(env, _PROJECT_ROOT, _PNEUMO_ROOT)" in src


def test_r31ax_stage_runner_help_runs_from_project_root() -> None:
    proc = _run_help_from_root("pneumo_solver_ui/opt_stage_runner_v1.py")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "--model" in proc.stdout
    assert "--run_dir" in proc.stdout


def test_r31ax_stage_runner_no_longer_passes_unsupported_out_json() -> None:
    src = (PNEUMO / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert "--out_json" not in src
    assert "check: bool = True" in src
    assert "_prepend_pythonpath(env, _PROJECT_ROOT, _PNEUMO_ROOT)" in src
