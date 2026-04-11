from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_fuzz_smoke_runs_with_worldroad_model_and_disabled_default_suite(tmp_path: Path) -> None:
    out_dir = tmp_path / "fuzz_out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.fuzz_smoke",
            "--model",
            str(UI_ROOT / "model_pneumo_v9_mech_doublewishbone_worldroad.py"),
            "--worker",
            str(UI_ROOT / "opt_worker_v3_margins_energy.py"),
            "--suite_json",
            str(UI_ROOT / "default_suite.json"),
            "--base_json",
            str(UI_ROOT / "default_base.json"),
            "--ranges_json",
            str(UI_ROOT / "default_ranges.json"),
            "--n",
            "1",
            "--seed",
            "1",
            "--dt_cap",
            "0.005",
            "--t_end_cap",
            "0.05",
            "--out_dir",
            str(out_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "=== FUZZ SMOKE SUMMARY ===" in proc.stdout
    assert "RuntimeWarning" not in proc.stderr

    summary = json.loads((out_dir / "fuzz_summary.json").read_text(encoding="utf-8"))
    assert bool(summary["ok"]) is True
    assert int(summary["n"]) == 1
    assert int(summary["fail_count"]) == 0
    assert str(summary["test_used"]["name"]).strip()
