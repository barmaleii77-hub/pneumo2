from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"
STAGE_RUNNER_UI = ROOT / "optimization_stage_runner_config_ui.py"
LAUNCH_PLAN_RUNTIME = ROOT / "optimization_launch_plan_runtime.py"
STAGE_RUNTIME_BLOCK = ROOT / "optimization_stage_runtime_block.py"
JOB_START_RUNTIME = ROOT / "optimization_job_start_runtime.py"
JOB_START_UI = ROOT / "optimization_job_start_ui.py"


def test_r31ce_optimization_page_exposes_stage_runner_controls() -> None:
    src = PAGE.read_text(encoding="utf-8")
    stage_src = STAGE_RUNNER_UI.read_text(encoding="utf-8")
    launch_plan_src = LAUNCH_PLAN_RUNTIME.read_text(encoding="utf-8")
    combined = src + "\n" + stage_src + "\n" + launch_plan_src
    assert '"Режим по стадиям (StageRunner) — рекомендуется"' in src
    assert '"StageRunner: warm-start, influence и staged seed/promotion"' in combined
    assert '"opt_stage_runner_v1.py"' in combined
    assert '"stage_policy_mode"' in combined
    assert '"adaptive_influence_eps"' in combined
    assert '"opt_autoupdate_baseline"' in combined
    assert '"ui_seed_candidates"' in combined
    assert '"ui_seed_conditions"' in combined
    assert 'stage_seed_policy_summary_text()' in combined
    assert 'stage_aware_influence_profiles_text(' in combined
    assert 'render_stage_runner_configuration_controls' in src


def test_r31ce_optimization_page_uses_runtime_hardening_helpers() -> None:
    src = PAGE.read_text(encoding="utf-8")
    launch_plan_src = LAUNCH_PLAN_RUNTIME.read_text(encoding="utf-8")
    stage_runtime_src = STAGE_RUNTIME_BLOCK.read_text(encoding="utf-8")
    job_start_src = JOB_START_RUNTIME.read_text(encoding="utf-8")
    job_start_ui_src = JOB_START_UI.read_text(encoding="utf-8")
    combined = src + "\n" + launch_plan_src + "\n" + stage_runtime_src + "\n" + job_start_src + "\n" + job_start_ui_src
    assert 'build_optimization_launch_plan' in src
    assert 'start_optimization_job_with_feedback' in src
    assert 'console_python_executable' in combined
    assert 'build_optimization_run_dir' in combined
    assert 'staged_progress_path' in combined
    assert 'render_stage_policy_runtime_block' in src
    assert 'summarize_staged_progress' in combined
    assert 'summarize_stage_policy_runtime' in combined
    assert 'render_stage_policy_runtime_snapshot' in combined
    assert 'launch_optimization_job_payload' in combined
    assert 'PNEUMO_WORKSPACE_DIR' in combined
    assert 'pipeline_mode' in combined
