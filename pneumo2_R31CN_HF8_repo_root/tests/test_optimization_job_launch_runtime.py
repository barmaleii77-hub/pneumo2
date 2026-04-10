from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_job_launch_runtime import (
    launch_optimization_job_payload,
    optimization_job_log_path,
)


def test_optimization_job_log_path_matches_pipeline_mode() -> None:
    run_dir = Path("C:/tmp/run")
    assert optimization_job_log_path(run_dir, "staged") == run_dir / "stage_runner.log"
    assert optimization_job_log_path(run_dir, "coordinator") == run_dir / "coordinator.log"


def test_launch_optimization_job_payload_creates_log_and_sets_problem_hash_env(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    run_dir = tmp_path / "run"
    app_root.mkdir()
    events: list[tuple[str, object]] = []

    class _DummyProc:
        pid = 123

    def _fake_popen(cmd, *, stdout, stderr, cwd, env):
        events.append(("cmd", list(cmd)))
        events.append(("stderr", stderr))
        events.append(("cwd", cwd))
        events.append(("env", dict(env)))
        events.append(("stdout_closed_during_call", stdout.closed))
        return _DummyProc()

    plan = SimpleNamespace(
        cmd=["python", "worker.py"],
        budget=17,
        label="StageRunner",
        pipeline_mode="staged",
        progress_path=run_dir / "sp.json",
        stop_file=run_dir / "STOP_OPTIMIZATION.txt",
    )

    payload = launch_optimization_job_payload(
        app_root,
        run_dir,
        plan,
        problem_hash_mode="stable",
        base_env={"BASE": "1"},
        popen_factory=_fake_popen,
        now_fn=lambda: 42.5,
    )

    assert payload["proc"].pid == 123
    assert payload["run_dir"] == run_dir
    assert payload["log_path"] == run_dir / "stage_runner.log"
    assert payload["started_ts"] == 42.5
    assert payload["budget"] == 17
    assert payload["backend"] == "StageRunner"
    assert payload["pipeline_mode"] == "staged"
    assert payload["progress_path"] == run_dir / "sp.json"
    assert payload["stop_file"] == run_dir / "STOP_OPTIMIZATION.txt"
    assert payload["log_path"].exists()
    assert ("stderr", subprocess.STDOUT) in events
    assert ("cwd", str(app_root)) in events
    assert ("stdout_closed_during_call", False) in events
    env_event = next(value for key, value in events if key == "env")
    assert env_event["BASE"] == "1"
    assert env_event["PNEUMO_OPT_PROBLEM_HASH_MODE"] == "stable"
    assert (run_dir / "problem_hash_mode.txt").read_text(encoding="utf-8") == "stable"
