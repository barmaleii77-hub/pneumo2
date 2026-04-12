from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.optimization_launch_plan_runtime import (
    build_optimization_launch_plan,
    current_problem_hash_for_launch,
    new_optimization_run_dir,
    ui_root_from_page_path,
    workspace_dir_for_ui_root,
)


def _repo_ui_root() -> Path:
    return Path(__file__).resolve().parents[1] / "pneumo_solver_ui"


def _write_workspace_anim_latest_ring_exports(exports_dir: Path) -> None:
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "anim_latest_road_csv.csv").write_text(
        "t,z0,z1,z2,z3\n0.0,0,0,0,0\n0.1,0.01,-0.01,-0.01,0.01\n0.2,0,0,0,0\n",
        encoding="utf-8",
    )
    (exports_dir / "anim_latest_axay_csv.csv").write_text(
        "t,ax,ay\n0.0,0,0\n0.1,0.3,1.1\n0.2,0,0\n",
        encoding="utf-8",
    )
    (exports_dir / "anim_latest_scenario_json.json").write_text(
        json.dumps(
            {
                "schema_version": "ring_v2",
                "v0_kph": 20.0,
                "dt_s": 0.1,
                "wheelbase_m": 1.5,
                "track_m": 1.0,
                "segments": [
                    {"name": "S1", "duration_s": 1.0, "turn_direction": "STRAIGHT", "road": {"mode": "ISO8608"}, "events": []},
                    {"name": "S2", "duration_s": 1.0, "turn_direction": "LEFT", "road": {"mode": "SINE"}, "events": []},
                ],
                "_generated_meta": {
                    "dt_s": 0.1,
                    "lap_time_s": 2.0,
                    "ring_length_m": 11.11111111111111,
                    "wheelbase_m": 1.5,
                    "track_m": 1.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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
    assert "--stage_tuner_json" not in cmd
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


def test_current_problem_hash_for_launch_honors_legacy_mode_for_coordinator() -> None:
    ui_root = _repo_ui_root()
    workspace = Path("C:/tmp/opt_workspace_mode_demo")
    session_state = {
        "opt_use_staged": False,
        "opt_objectives": "comfort,energy",
        "opt_penalty_key": "penalty_total",
        "opt_penalty_tol": 0.0,
    }

    stable_hash = current_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
        problem_hash_mode="stable",
    )
    legacy_hash = current_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
        problem_hash_mode="legacy",
    )

    assert stable_hash
    assert legacy_hash
    assert stable_hash != legacy_hash


def test_launch_plan_runtime_prefers_auto_ring_suite_from_workspace_exports(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    exports_dir = workspace / "exports"
    _write_workspace_anim_latest_ring_exports(exports_dir)
    session_state = {
        "opt_use_staged": True,
        "opt_auto_ring_suite_enabled": True,
        "opt_objectives": "comfort\nroll",
        "ui_opt_minutes": 3.0,
        "ui_seed_candidates": 2,
        "ui_seed_conditions": 2,
        "ui_jobs": 2,
        "warmstart_mode": "archive",
        "surrogate_samples": 256,
        "surrogate_top_k": 8,
        "opt_penalty_key": "penalty_total",
    }

    run_dir = new_optimization_run_dir(
        workspace_dir_for_ui_root(ui_root, env={"PNEUMO_WORKSPACE_DIR": str(workspace)}),
        "staged",
        now_text="20260412_120000",
    )
    plan = build_optimization_launch_plan(
        session_state,
        run_dir=run_dir,
        ui_root=ui_root,
        python_executable="python",
        ui_jobs_default=2,
        env={"PNEUMO_WORKSPACE_DIR": str(workspace)},
    )

    suite_idx = plan.cmd.index("--suite_json") + 1
    suite_path = Path(plan.cmd[suite_idx])
    assert "optimization_auto_ring_suite" in str(suite_path)
    assert suite_path.exists()
    tuner_idx = plan.cmd.index("--stage_tuner_json") + 1
    tuner_path = Path(plan.cmd[tuner_idx])
    assert "optimization_auto_tuner" in str(tuner_path)
    assert tuner_path.exists()
    rows = json.loads(suite_path.read_text(encoding="utf-8"))
    names = {str((row or {}).get("имя") or "").strip() for row in rows if isinstance(row, dict)}
    assert "ring_auto_full" in names
    assert any(name.startswith("ringfrag_") for name in names)
    tuner_plan = json.loads(tuner_path.read_text(encoding="utf-8"))
    assert tuner_plan["suite_family"] == "auto_ring"
    assert tuner_plan["coordinator_handoff"]["recommended_proposer"] == "portfolio"
