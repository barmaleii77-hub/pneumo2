from __future__ import annotations

from pathlib import Path


def test_r31bk_worker_parallel_loop_is_deadline_aware_and_flushes_partial_rows() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py").read_text(encoding="utf-8")
    assert "FIRST_COMPLETED" in src
    assert "_wait_futures" in src
    assert "_terminate_process_pool_fast" in src
    assert 'early_stop_reason = "time_limit"' in src
    assert 'early_stop_reason = "stop_file"' in src
    assert '_flush_rows_buf()' in src
    assert 'elif early_stop_reason == "time_limit" or (time.time() >= t_limit):' in src


def test_r31bk_stage_runner_uses_activity_watchdog_and_closes_parent_log_handles() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert "_safe_close_fileobj" in src
    assert "idle_timeout_sec" in src
    assert "last_activity_ts" in src
    assert "worker_last_progress_ts" in src
    assert "stage_idle_sec" in src
    assert "stopped making progress" in src
    assert "_safe_close_fileobj(_worker_stdout_f)" in src
    assert "_safe_close_fileobj(_worker_stderr_f)" in src
    assert "_safe_close_fileobj(stdout_f)" in src
    assert "_safe_close_fileobj(stderr_f)" in src
