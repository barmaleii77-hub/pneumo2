from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_job_start_runtime import (
    start_optimization_job,
)


def test_job_start_runtime_builds_plan_launches_payload_and_saves_job() -> None:
    session_state = {
        "opt_use_staged": True,
        "settings_opt_problem_hash_mode": "stable",
    }
    events: list[tuple[str, object]] = []

    job = start_optimization_job(
        session_state,
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        ui_jobs_default=7,
        python_executable="python",
        problem_hash_mode="stable",
        workspace_dir_fn=lambda ui_root: events.append(("workspace", ui_root)) or Path("C:/workspace"),
        app_root_fn=lambda ui_root: events.append(("app_root", ui_root)) or Path("C:/repo"),
        new_run_dir_fn=lambda workspace, mode: events.append(("run_dir", workspace, mode)) or Path("C:/workspace/run-1"),
        build_plan_fn=lambda state, **kwargs: events.append(("plan", kwargs["run_dir"], kwargs["ui_root"], kwargs["python_executable"], kwargs["ui_jobs_default"])) or type(
            "Plan",
            (),
            {
                "cmd": ["python", "worker.py"],
                "budget": 17,
                "label": "StageRunner",
                "pipeline_mode": "staged",
                "progress_path": Path("C:/workspace/run-1/sp.json"),
                "stop_file": Path("C:/workspace/run-1/STOP_OPTIMIZATION.txt"),
            },
        )(),
        launch_payload_fn=lambda app_root, run_dir, plan, **kwargs: events.append(("launch", app_root, run_dir, plan.pipeline_mode, kwargs["problem_hash_mode"])) or {
            "proc": type("Proc", (), {"pid": 321})(),
            "run_dir": run_dir,
            "log_path": Path("C:/workspace/run-1/stage_runner.log"),
            "started_ts": 1.0,
            "budget": plan.budget,
            "backend": plan.label,
            "pipeline_mode": plan.pipeline_mode,
            "progress_path": plan.progress_path,
            "stop_file": plan.stop_file,
        },
        save_job_fn=lambda state, job_obj: events.append(("save", job_obj.run_dir, job_obj.pipeline_mode)),
    )

    assert job.run_dir == Path("C:/workspace/run-1")
    assert job.pipeline_mode == "staged"
    assert events == [
        ("workspace", Path("C:/repo/pneumo_solver_ui")),
        ("run_dir", Path("C:/workspace"), "staged"),
        ("plan", Path("C:/workspace/run-1"), Path("C:/repo/pneumo_solver_ui"), "python", 7),
        ("app_root", Path("C:/repo/pneumo_solver_ui")),
        ("launch", Path("C:/repo"), Path("C:/workspace/run-1"), "staged", "stable"),
        ("save", Path("C:/workspace/run-1"), "staged"),
    ]


def test_job_start_runtime_uses_resume_run_dir_for_coordinator_resume() -> None:
    session_state = {
        "opt_use_staged": False,
        "opt_resume": True,
        "opt_dist_run_id": "run_existing_42",
    }
    events: list[tuple[str, object]] = []

    job = start_optimization_job(
        session_state,
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        ui_jobs_default=7,
        python_executable="python",
        problem_hash_mode="stable",
        workspace_dir_fn=lambda ui_root: events.append(("workspace", ui_root)) or Path("C:/workspace"),
        app_root_fn=lambda ui_root: events.append(("app_root", ui_root)) or Path("C:/repo"),
        new_run_dir_fn=lambda workspace, mode: events.append(("new_run_dir", workspace, mode)) or Path("C:/workspace/new-run"),
        resume_run_dir_fn=lambda state, **kwargs: events.append(("resume_run_dir", kwargs["workspace_dir"], kwargs["ui_root"], state.get("opt_dist_run_id"), kwargs["problem_hash_mode"])) or Path("C:/workspace/opt_runs/coord/p_resume"),
        build_plan_fn=lambda state, **kwargs: events.append(("plan", kwargs["run_dir"], kwargs["ui_root"], kwargs["python_executable"], kwargs["ui_jobs_default"])) or type(
            "Plan",
            (),
            {
                "cmd": ["python", "worker.py"],
                "budget": 17,
                "label": "Ray",
                "pipeline_mode": "coordinator",
                "progress_path": None,
                "stop_file": None,
            },
        )(),
        launch_payload_fn=lambda app_root, run_dir, plan, **kwargs: events.append(("launch", app_root, run_dir, plan.pipeline_mode, kwargs["problem_hash_mode"])) or {
            "proc": type("Proc", (), {"pid": 654})(),
            "run_dir": run_dir,
            "log_path": Path("C:/workspace/opt_runs/coord/p_resume/coordinator.log"),
            "started_ts": 1.0,
            "budget": plan.budget,
            "backend": plan.label,
            "pipeline_mode": plan.pipeline_mode,
            "progress_path": plan.progress_path,
            "stop_file": plan.stop_file,
        },
        save_job_fn=lambda state, job_obj: events.append(("save", job_obj.run_dir, job_obj.pipeline_mode)),
    )

    assert job.run_dir == Path("C:/workspace/opt_runs/coord/p_resume")
    assert events == [
        ("workspace", Path("C:/repo/pneumo_solver_ui")),
        ("resume_run_dir", Path("C:/workspace"), Path("C:/repo/pneumo_solver_ui"), "run_existing_42", "stable"),
        ("plan", Path("C:/workspace/opt_runs/coord/p_resume"), Path("C:/repo/pneumo_solver_ui"), "python", 7),
        ("app_root", Path("C:/repo/pneumo_solver_ui")),
        ("launch", Path("C:/repo"), Path("C:/workspace/opt_runs/coord/p_resume"), "coordinator", "stable"),
        ("save", Path("C:/workspace/opt_runs/coord/p_resume"), "coordinator"),
    ]


def test_job_start_runtime_uses_staged_resume_run_dir_when_requested() -> None:
    session_state = {
        "opt_use_staged": True,
        "opt_stage_resume": True,
    }
    events: list[tuple[str, object]] = []

    job = start_optimization_job(
        session_state,
        ui_root=Path("C:/repo/pneumo_solver_ui"),
        ui_jobs_default=7,
        python_executable="python",
        problem_hash_mode="stable",
        workspace_dir_fn=lambda ui_root: events.append(("workspace", ui_root)) or Path("C:/workspace"),
        app_root_fn=lambda ui_root: events.append(("app_root", ui_root)) or Path("C:/repo"),
        new_run_dir_fn=lambda workspace, mode: events.append(("new_run_dir", workspace, mode)) or Path("C:/workspace/new-run"),
        staged_resume_run_dir_fn=lambda state, **kwargs: events.append(("staged_resume_run_dir", kwargs["workspace_dir"], kwargs["ui_root"], state.get("opt_stage_resume"), kwargs["problem_hash_mode"])) or Path("C:/workspace/opt_runs/staged/p_stage_resume"),
        build_plan_fn=lambda state, **kwargs: events.append(("plan", kwargs["run_dir"], kwargs["ui_root"], kwargs["python_executable"], kwargs["ui_jobs_default"])) or type(
            "Plan",
            (),
            {
                "cmd": ["python", "worker.py"],
                "budget": 17,
                "label": "StageRunner",
                "pipeline_mode": "staged",
                "progress_path": Path("C:/workspace/opt_runs/staged/p_stage_resume/sp.json"),
                "stop_file": Path("C:/workspace/opt_runs/staged/p_stage_resume/STOP_OPTIMIZATION.txt"),
            },
        )(),
        launch_payload_fn=lambda app_root, run_dir, plan, **kwargs: events.append(("launch", app_root, run_dir, plan.pipeline_mode, kwargs["problem_hash_mode"])) or {
            "proc": type("Proc", (), {"pid": 987})(),
            "run_dir": run_dir,
            "log_path": Path("C:/workspace/opt_runs/staged/p_stage_resume/stage_runner.log"),
            "started_ts": 1.0,
            "budget": plan.budget,
            "backend": plan.label,
            "pipeline_mode": plan.pipeline_mode,
            "progress_path": plan.progress_path,
            "stop_file": plan.stop_file,
        },
        save_job_fn=lambda state, job_obj: events.append(("save", job_obj.run_dir, job_obj.pipeline_mode)),
    )

    assert job.run_dir == Path("C:/workspace/opt_runs/staged/p_stage_resume")
    assert events == [
        ("workspace", Path("C:/repo/pneumo_solver_ui")),
        ("staged_resume_run_dir", Path("C:/workspace"), Path("C:/repo/pneumo_solver_ui"), True, "stable"),
        ("plan", Path("C:/workspace/opt_runs/staged/p_stage_resume"), Path("C:/repo/pneumo_solver_ui"), "python", 7),
        ("app_root", Path("C:/repo/pneumo_solver_ui")),
        ("launch", Path("C:/repo"), Path("C:/workspace/opt_runs/staged/p_stage_resume"), "staged", "stable"),
        ("save", Path("C:/workspace/opt_runs/staged/p_stage_resume"), "staged"),
    ]
