from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_launch_plan_runtime import (
    coordinator_problem_hash_for_launch,
    coordinator_resume_run_dir,
)


def _repo_ui_root() -> Path:
    return Path(__file__).resolve().parents[1] / "pneumo_solver_ui"


def test_resume_run_dir_reuses_existing_problem_hash_folder(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    session_state = {
        "opt_use_staged": False,
        "opt_resume": True,
        "opt_objectives": "comfort\nenergy",
        "opt_penalty_key": "penalty_total",
        "opt_penalty_tol": 0.0,
    }

    problem_hash = coordinator_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
    )
    existing = workspace / "opt_runs" / "coord" / "p_legacy_1234"
    existing.mkdir(parents=True)
    (existing / "problem_hash.txt").write_text(problem_hash, encoding="utf-8")
    (existing / "run_id.txt").write_text("run_existing_hash", encoding="utf-8")

    chosen = coordinator_resume_run_dir(
        session_state,
        workspace_dir=workspace,
        ui_root=ui_root,
    )

    assert chosen == existing


def test_resume_run_dir_prefers_explicit_run_id_over_problem_hash(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    session_state = {
        "opt_use_staged": False,
        "opt_resume": True,
        "opt_dist_run_id": "run_target",
        "opt_objectives": "comfort\nenergy",
        "opt_penalty_key": "penalty_total",
        "opt_penalty_tol": 0.0,
    }

    problem_hash = coordinator_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
    )

    hash_match = workspace / "opt_runs" / "coord" / "p_hash_match"
    hash_match.mkdir(parents=True)
    (hash_match / "problem_hash.txt").write_text(problem_hash, encoding="utf-8")
    (hash_match / "run_id.txt").write_text("run_other", encoding="utf-8")

    explicit = workspace / "opt_runs" / "coord" / "p_explicit"
    explicit.mkdir(parents=True)
    (explicit / "problem_hash.txt").write_text("different_problem", encoding="utf-8")
    (explicit / "run_id.txt").write_text("run_target", encoding="utf-8")

    chosen = coordinator_resume_run_dir(
        session_state,
        workspace_dir=workspace,
        ui_root=ui_root,
    )

    assert chosen == explicit


def test_resume_run_dir_honors_legacy_problem_hash_mode(tmp_path: Path) -> None:
    ui_root = _repo_ui_root()
    workspace = tmp_path / "workspace"
    session_state = {
        "opt_use_staged": False,
        "opt_resume": True,
        "opt_objectives": "comfort\nenergy",
        "opt_penalty_key": "penalty_total",
        "opt_penalty_tol": 0.0,
    }

    legacy_hash = coordinator_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
        problem_hash_mode="legacy",
    )
    stable_hash = coordinator_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace,
        problem_hash_mode="stable",
    )
    assert legacy_hash != stable_hash

    legacy_run = workspace / "opt_runs" / "coord" / "p_legacy_mode_match"
    legacy_run.mkdir(parents=True)
    (legacy_run / "problem_hash.txt").write_text(legacy_hash, encoding="utf-8")

    chosen = coordinator_resume_run_dir(
        session_state,
        workspace_dir=workspace,
        ui_root=ui_root,
        problem_hash_mode="legacy",
    )

    assert chosen == legacy_run
