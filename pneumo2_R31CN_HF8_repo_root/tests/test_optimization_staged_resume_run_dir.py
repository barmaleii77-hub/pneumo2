from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_launch_plan_runtime import (
    staged_problem_hash_for_launch,
    staged_resume_run_dir,
)


def _repo_ui_root() -> Path:
    return Path(__file__).resolve().parents[1] / "pneumo_solver_ui"


def test_staged_resume_run_dir_prefers_selected_history_run_when_hash_is_absent(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    selected = workspace / "opt_runs" / "staged" / "p_selected_legacy"
    selected.mkdir(parents=True)
    session_state = {
        "opt_use_staged": True,
        "opt_stage_resume": True,
        "__opt_history_selected_run_dir": str(selected),
        "opt_objectives": "comfort\nenergy",
        "opt_penalty_key": "penalty_total",
    }

    chosen = staged_resume_run_dir(
        session_state,
        workspace_dir=workspace,
        ui_root=ui_root,
    )

    assert chosen == selected


def test_staged_resume_run_dir_reuses_latest_compatible_run(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    session_state = {
        "opt_use_staged": True,
        "opt_stage_resume": True,
        "opt_objectives": "comfort\nenergy",
        "opt_penalty_key": "penalty_total",
    }

    problem_hash = staged_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
    )

    older = workspace / "opt_runs" / "staged" / "p_older"
    older.mkdir(parents=True)
    (older / "problem_hash.txt").write_text(problem_hash, encoding="utf-8")

    latest = workspace / "opt_runs" / "staged" / "p_latest"
    latest.mkdir(parents=True)
    (latest / "problem_hash.txt").write_text(problem_hash, encoding="utf-8")

    chosen = staged_resume_run_dir(
        session_state,
        workspace_dir=workspace,
        ui_root=ui_root,
    )

    assert chosen == latest


def test_staged_resume_run_dir_honors_legacy_problem_hash_mode(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    session_state = {
        "opt_use_staged": True,
        "opt_stage_resume": True,
        "opt_objectives": "comfort\nenergy",
        "opt_penalty_key": "penalty_total",
    }

    legacy_hash = staged_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
        problem_hash_mode="legacy",
    )
    stable_hash = staged_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
        problem_hash_mode="stable",
    )
    assert legacy_hash != stable_hash

    legacy_run = workspace / "opt_runs" / "staged" / "p_legacy_mode_match"
    legacy_run.mkdir(parents=True)
    (legacy_run / "problem_hash.txt").write_text(legacy_hash, encoding="utf-8")

    chosen = staged_resume_run_dir(
        session_state,
        workspace_dir=workspace,
        ui_root=ui_root,
        problem_hash_mode="legacy",
    )

    assert chosen == legacy_run
