from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"


def test_r31ce_optimization_page_exposes_stage_runner_controls() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert '"Режим по стадиям (StageRunner) — рекомендуется"' in src
    assert '"StageRunner: warm-start, influence и staged seed/promotion"' in src
    assert '"opt_stage_runner_v1.py"' in src
    assert '"stage_policy_mode"' in src
    assert '"adaptive_influence_eps"' in src
    assert '"opt_autoupdate_baseline"' in src
    assert '"ui_seed_candidates"' in src
    assert '"ui_seed_conditions"' in src
    assert 'stage_seed_policy_summary_text()' in src
    assert 'stage_aware_influence_profiles_text(' in src


def test_r31ce_optimization_page_uses_runtime_hardening_helpers() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert 'console_python_executable' in src
    assert 'build_optimization_run_dir' in src
    assert 'staged_progress_path' in src
    assert 'summarize_staged_progress' in src
    assert 'summarize_stage_policy_runtime' in src
    assert 'PNEUMO_WORKSPACE_DIR' in src
    assert 'pipeline_mode' in src
