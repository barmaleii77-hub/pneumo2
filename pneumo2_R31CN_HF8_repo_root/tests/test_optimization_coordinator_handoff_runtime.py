from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.optimization_coordinator_handoff_runtime import (
    build_coordinator_handoff_launch_plan,
    coordinator_handoff_plan_path,
    coordinator_handoff_target_run_dir,
    load_coordinator_handoff_payload,
)


def test_coordinator_handoff_runtime_builds_launch_plan_from_source_run_dir(tmp_path: Path) -> None:
    source_run = tmp_path / "stage_run"
    handoff_dir = source_run / "coordinator_handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    target_run_dir = tmp_path / "coord_run"
    plan_path = handoff_dir / "coordinator_handoff_plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_proposer": "portfolio",
                "recommended_q": 2,
                "recommended_budget": 64,
                "cmd_args": [
                    "--backend",
                    "ray",
                    "--run-dir",
                    str(target_run_dir),
                    "--budget",
                    "64",
                    "--proposer",
                    "portfolio",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert coordinator_handoff_plan_path(source_run) == plan_path
    payload = load_coordinator_handoff_payload(source_run)
    assert coordinator_handoff_target_run_dir(payload) == target_run_dir.resolve()

    plan = build_coordinator_handoff_launch_plan(
        source_run,
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        python_executable="python",
    )

    cmd = " ".join(plan.cmd)
    assert plan.pipeline_mode == "coordinator"
    assert plan.label == "Handoff/ray/portfolio/q2"
    assert plan.budget == 64
    assert plan.launch_run_dir == target_run_dir.resolve()
    assert "dist_opt_coordinator.py" in cmd
    assert "--proposer portfolio" in cmd
