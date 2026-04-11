from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pneumo_solver_ui import opt_selfcheck_v1 as mod


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_import_module_from_path_loads_stage_runner_dataclass_module() -> None:
    stage_runner = mod._import_module_from_path(
        "opt_stage_runner_v1_probe",
        UI_ROOT / "opt_stage_runner_v1.py",
    )
    assert hasattr(stage_runner, "build_default_scenarios")
    assert hasattr(stage_runner, "expand_suite_by_scenarios")


def test_opt_selfcheck_fast_runs_scenario_expansion_check_without_skip(tmp_path: Path) -> None:
    report_json = tmp_path / "opt_selfcheck_fast.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.opt_selfcheck_v1",
            "--model",
            str(UI_ROOT / "model_pneumo_v9_mech_doublewishbone_worldroad.py"),
            "--worker",
            str(UI_ROOT / "opt_worker_v3_margins_energy.py"),
            "--base_json",
            str(UI_ROOT / "default_base.json"),
            "--ranges_json",
            str(UI_ROOT / "default_ranges.json"),
            "--suite_json",
            str(UI_ROOT / "default_suite.json"),
            "--report_json",
            str(report_json),
            "--mode",
            "fast",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert bool(payload["ok"]) is True
    scenario = payload["checks"]["scenario_expansion"]
    assert bool(scenario["ok"]) is True
    assert scenario["warnings"] == []
