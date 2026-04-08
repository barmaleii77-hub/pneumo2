from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_launch_plan_runtime import (
    build_optimization_launch_plan,
    new_optimization_run_dir,
    ui_root_from_page_path,
    workspace_dir_for_ui_root,
)


def _repo_ui_root() -> Path:
    return Path(__file__).resolve().parents[1] / "pneumo_solver_ui"


def test_launch_plan_runtime_builds_stage_runner_command_with_workspace_override(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    session_state = {
        "opt_use_staged": True,
        "opt_objectives": "comfort\nroll",
        "ui_opt_minutes": 3.0,
        "ui_seed_candidates": 4,
        "ui_seed_conditions": 5,
        "ui_jobs": 6,
        "warmstart_mode": "archive",
        "surrogate_samples": 1000,
        "surrogate_top_k": 16,
        "adaptive_influence_eps": True,
        "opt_penalty_key": "penalty_total",
    }

    run_dir = new_optimization_run_dir(
        workspace_dir_for_ui_root(ui_root, env={"PNEUMO_WORKSPACE_DIR": str(workspace)}),
        "staged",
        now_text="20260409_120000",
    )
    plan = build_optimization_launch_plan(
        session_state,
        run_dir=run_dir,
        ui_root=ui_root,
        python_executable="python",
        ui_jobs_default=7,
        env={"PNEUMO_WORKSPACE_DIR": str(workspace)},
    )

    cmd = " ".join(plan.cmd)
    assert plan.pipeline_mode == "staged"
    assert plan.stop_file == run_dir / "STOP_OPTIMIZATION.txt"
    assert "opt_stage_runner_v1.py" in cmd
    assert "--objective comfort" in cmd
    assert "--objective roll" in cmd
    assert "--adaptive_influence_eps" in cmd
    assert str(workspace) in str(plan.stop_file)


def test_launch_plan_runtime_builds_coordinator_command_and_uses_real_ui_root() -> None:
    ui_root = _repo_ui_root()
    session_state = {
        "opt_use_staged": False,
        "opt_backend": "Ray",
        "opt_objectives": "comfort,energy",
        "opt_budget": 11,
        "opt_seed": 12,
        "opt_max_inflight": 13,
        "opt_proposer": "auto",
        "opt_q": 2,
        "opt_device": "cpu",
        "opt_penalty_key": "penalty_total",
        "opt_penalty_tol": 0.0,
        "ray_mode": "Подключиться к кластеру",
        "ray_address": "auto",
    }

    run_dir = Path("C:/tmp/RUN_COORD")
    plan = build_optimization_launch_plan(
        session_state,
        run_dir=run_dir,
        ui_root=ui_root_from_page_path(ui_root / "pages" / "03_Optimization.py"),
        python_executable="python",
        ui_jobs_default=7,
    )

    cmd = " ".join(plan.cmd)
    assert plan.pipeline_mode == "coordinator"
    assert plan.budget == 11
    assert "dist_opt_coordinator.py" in cmd
    assert "--backend ray" in cmd
    assert "--objective comfort" in cmd
    assert "--objective energy" in cmd
