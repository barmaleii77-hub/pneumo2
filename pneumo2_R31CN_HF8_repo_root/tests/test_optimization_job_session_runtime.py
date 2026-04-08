from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_job_session_runtime import (
    DistOptJob,
    clear_job_from_session,
    load_job_from_session,
    parse_done_from_log,
    save_job_to_session,
    soft_stop_requested,
    tail_file_text,
    write_soft_stop_file,
)


def test_optimization_job_session_roundtrip() -> None:
    session_state: dict[str, object] = {}
    job = DistOptJob(
        proc=SimpleNamespace(pid=123),
        run_dir=Path("C:/tmp/run"),
        log_path=Path("C:/tmp/run/stage_runner.log"),
        started_ts=42.5,
        budget=17,
        backend="StageRunner",
        pipeline_mode="staged",
        progress_path=Path("C:/tmp/run/sp.json"),
        stop_file=Path("C:/tmp/run/STOP_OPTIMIZATION.txt"),
    )

    save_job_to_session(session_state, job)
    restored = load_job_from_session(session_state)

    assert restored is not None
    assert restored.run_dir == job.run_dir
    assert restored.log_path == job.log_path
    assert restored.budget == 17
    clear_job_from_session(session_state)
    assert load_job_from_session(session_state) is None


def test_optimization_job_runtime_helpers_handle_log_and_stop_file(tmp_path: Path) -> None:
    log_path = tmp_path / "coordinator.log"
    log_path.write_text("warmup done=1\nstep done=7/20\n", encoding="utf-8")

    stop_path = tmp_path / "STOP_OPTIMIZATION.txt"
    assert "step done=7/20" in tail_file_text(log_path)
    assert parse_done_from_log("done=1\ndone=9/12") == 9
    assert write_soft_stop_file(stop_path) is True

    job = DistOptJob(
        proc=SimpleNamespace(pid=1),
        run_dir=tmp_path,
        log_path=log_path,
        started_ts=1.0,
        budget=20,
        backend="ray",
        pipeline_mode="coordinator",
        stop_file=stop_path,
    )
    assert soft_stop_requested(job) is True
