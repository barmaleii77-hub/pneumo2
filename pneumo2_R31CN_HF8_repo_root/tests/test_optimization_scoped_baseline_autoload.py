from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_baseline_source import (
    resolve_workspace_baseline_source,
)
from pneumo_solver_ui.opt_stage_runner_v1 import build_stage_worker_env
from pneumo_solver_ui.opt_worker_v3_margins_energy import (
    make_base_and_ranges,
    resolve_workspace_baseline_override_path,
)
from pneumo_solver_ui.tools.dist_opt_coordinator import apply_problem_hash_env


def test_resolve_workspace_baseline_override_path_prefers_problem_scoped_baseline(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "baseline_best.json").write_text('{"scope_probe": "global"}', encoding="utf-8")
    scoped = baseline_dir / "by_problem" / "p_ph_scope_789" / "baseline_best.json"
    scoped.parent.mkdir(parents=True)
    scoped.write_text('{"scope_probe": "scoped"}', encoding="utf-8")

    selected = resolve_workspace_baseline_override_path(
        env={"PNEUMO_OPT_PROBLEM_HASH": "ph_scope_789"},
        baseline_dir=baseline_dir,
    )

    assert selected == scoped


def test_make_base_and_ranges_merges_scoped_baseline_before_global_fallback(tmp_path: Path, monkeypatch) -> None:
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "baseline_best.json").write_text('{"scope_probe": "global"}', encoding="utf-8")
    scoped = baseline_dir / "by_problem" / "p_ph_scope_789" / "baseline_best.json"
    scoped.parent.mkdir(parents=True)
    scoped.write_text('{"scope_probe": "scoped"}', encoding="utf-8")

    monkeypatch.setattr(
        "pneumo_solver_ui.opt_worker_v3_margins_energy._workspace_baseline_dir",
        lambda: baseline_dir,
    )
    monkeypatch.setenv("PNEUMO_OPT_PROBLEM_HASH", "ph_scope_789")

    base, _ranges = make_base_and_ranges(101325.0)

    assert base["scope_probe"] == "scoped"


def test_build_stage_worker_env_sets_problem_hash_and_workspace_cache(tmp_path: Path) -> None:
    env = build_stage_worker_env(
        tmp_path,
        "ph_stage_resume_scope",
        base_env={"BASE": "1"},
    )

    assert env["BASE"] == "1"
    assert env["PNEUMO_OPT_PROBLEM_HASH"] == "ph_stage_resume_scope"
    assert env["PNEUMO_WORKSPACE_DIR"] == str(tmp_path)
    assert env["PNEUMO_GUIDED_MODE"] == "auto"
    assert env["WORLDROAD_CACHE_DIR"] == str(tmp_path / "cache" / "worldroad")


def test_apply_problem_hash_env_sets_and_clears_mapping() -> None:
    env = {"BASE": "1", "PNEUMO_OPT_PROBLEM_HASH": "old_hash"}

    apply_problem_hash_env("ph_dist_scope", env)
    assert env["BASE"] == "1"
    assert env["PNEUMO_OPT_PROBLEM_HASH"] == "ph_dist_scope"

    apply_problem_hash_env("", env)
    assert "PNEUMO_OPT_PROBLEM_HASH" not in env


def test_resolve_workspace_baseline_source_respects_workspace_env_override(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace_custom"
    baseline_dir = workspace / "baselines"
    scoped = baseline_dir / "by_problem" / "p_ph_env_scope" / "baseline_best.json"
    scoped.parent.mkdir(parents=True, exist_ok=True)
    scoped.write_text('{"scope_probe": "env_scoped"}', encoding="utf-8")

    payload = resolve_workspace_baseline_source(
        env={
            "PNEUMO_WORKSPACE_DIR": str(workspace),
            "PNEUMO_OPT_PROBLEM_HASH": "ph_env_scope",
        }
    )

    assert payload["source_kind"] == "scoped"
    assert payload["source_label"] == "scoped baseline"
    assert payload["baseline_path"] == str(scoped)
