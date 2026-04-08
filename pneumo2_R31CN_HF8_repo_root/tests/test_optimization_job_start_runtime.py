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
