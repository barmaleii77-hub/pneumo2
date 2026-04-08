from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"
LAUNCH_SESSION_UI = ROOT / "optimization_launch_session_ui.py"
JOB_RUNTIME = ROOT / "optimization_job_session_runtime.py"
LAUNCH_PLAN_RUNTIME = ROOT / "optimization_launch_plan_runtime.py"
JOB_START_RUNTIME = ROOT / "optimization_job_start_runtime.py"
JOB_START_UI = ROOT / "optimization_job_start_ui.py"


def test_r31cf_optimization_page_preserves_soft_stop_contract() -> None:
    src = PAGE.read_text(encoding="utf-8")
    launch_src = LAUNCH_SESSION_UI.read_text(encoding="utf-8")
    job_runtime_src = JOB_RUNTIME.read_text(encoding="utf-8")
    launch_plan_src = LAUNCH_PLAN_RUNTIME.read_text(encoding="utf-8")
    job_start_src = JOB_START_RUNTIME.read_text(encoding="utf-8")
    job_start_ui_src = JOB_START_UI.read_text(encoding="utf-8")
    combined = src + "\n" + launch_src + "\n" + job_runtime_src + "\n" + launch_plan_src + "\n" + job_start_src + "\n" + job_start_ui_src
    assert 'stop_file: Optional[Path] = None' in job_runtime_src
    assert 'def write_soft_stop_file(' in job_runtime_src
    assert 'def soft_stop_requested(' in job_runtime_src
    assert 'def terminate_optimization_process(' in job_runtime_src
    assert 'render_optimization_launch_session_block' in src
    assert 'render_live_optimization_job_panel' in combined
    assert 'start_optimization_job_with_feedback' in src
    assert 'launch_optimization_job_payload' in combined
    assert 'STOP_OPTIMIZATION.txt' in combined
    assert '"Стоп (мягко)"' in combined
    assert '"Стоп (жёстко)"' in combined
    assert '.write_text("stop", encoding="utf-8")' in job_runtime_src


def test_r31cf_optimization_page_marks_stop_requested_runs_honestly() -> None:
    src = PAGE.read_text(encoding="utf-8")
    launch_src = LAUNCH_SESSION_UI.read_text(encoding="utf-8")
    job_runtime_src = JOB_RUNTIME.read_text(encoding="utf-8")
    launch_plan_src = LAUNCH_PLAN_RUNTIME.read_text(encoding="utf-8")
    job_start_src = JOB_START_RUNTIME.read_text(encoding="utf-8")
    job_start_ui_src = JOB_START_UI.read_text(encoding="utf-8")
    combined = src + "\n" + launch_src + "\n" + job_runtime_src + "\n" + launch_plan_src + "\n" + job_start_src + "\n" + job_start_ui_src
    assert 'soft_stop_requested_fn=soft_stop_requested' in src
    assert 'write_soft_stop_file_fn=write_soft_stop_file' in src
    assert 'terminate_process_fn=terminate_optimization_process' in src
    assert 'render_finished_optimization_job_panel' in combined
    assert '"Запрошена мягкая остановка через STOP_OPTIMIZATION.txt.' in combined
