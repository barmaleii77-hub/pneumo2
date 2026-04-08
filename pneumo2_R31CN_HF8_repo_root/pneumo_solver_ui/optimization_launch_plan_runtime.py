from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from pneumo_solver_ui.optimization_defaults import (
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS,
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    DIAGNOSTIC_OPT_MINUTES_DEFAULT,
    DIAGNOSTIC_SEED_CANDIDATES,
    DIAGNOSTIC_SEED_CONDITIONS,
    DIAGNOSTIC_SORT_TESTS_BY_COST,
    DIAGNOSTIC_SURROGATE_SAMPLES,
    DIAGNOSTIC_SURROGATE_TOP_K,
    DIAGNOSTIC_USE_STAGED_OPT,
    DIAGNOSTIC_WARMSTART_MODE,
    DIST_OPT_BUDGET_DEFAULT,
    DIST_OPT_DEVICE_DEFAULT,
    DIST_OPT_MAX_INFLIGHT_DEFAULT,
    DIST_OPT_PENALTY_KEY_DEFAULT,
    DIST_OPT_PENALTY_TOL_DEFAULT,
    DIST_OPT_PROPOSER_DEFAULT,
    DIST_OPT_Q_DEFAULT,
    DIST_OPT_SEED_DEFAULT,
    canonical_base_json_path,
    canonical_model_path,
    canonical_ranges_json_path,
    canonical_suite_json_path,
    canonical_worker_path,
    influence_eps_grid_text,
)
from pneumo_solver_ui.optimization_distributed_wiring import (
    append_coordinator_runtime_args,
)
from pneumo_solver_ui.optimization_ready_preset import (
    materialize_optimization_ready_suite_json,
)
from pneumo_solver_ui.optimization_runtime_paths import (
    build_optimization_run_dir,
    console_python_executable,
    staged_progress_path,
)
from pneumo_solver_ui.optimization_stage_policy import (
    DEFAULT_STAGE_POLICY_MODE,
)


@dataclass
class LaunchPlan:
    label: str
    cmd: list[str]
    pipeline_mode: str
    progress_path: Optional[Path]
    budget: int
    stop_file: Optional[Path] = None


def ui_root_from_page_path(page_path: Path) -> Path:
    return Path(page_path).resolve().parents[1]


def app_root_from_ui_root(ui_root: Path) -> Path:
    return Path(ui_root).resolve().parent


def tools_root_from_ui_root(ui_root: Path) -> Path:
    return Path(ui_root) / "tools"


def env_dir(key: str, default: Path, *, env: Mapping[str, str] | None = None) -> Path:
    source = env or os.environ
    raw = str(source.get(key, "") or "").strip()
    if not raw:
        return default
    try:
        return Path(raw).expanduser().resolve()
    except Exception:
        return Path(raw)


def workspace_dir_for_ui_root(ui_root: Path, *, env: Mapping[str, str] | None = None) -> Path:
    workspace = env_dir("PNEUMO_WORKSPACE_DIR", Path(ui_root) / "workspace", env=env)
    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return workspace


def default_model_path(ui_root: Path) -> Path:
    return canonical_model_path(Path(ui_root))


def default_worker_path(ui_root: Path) -> Path:
    return canonical_worker_path(Path(ui_root))


def default_base_json_path(ui_root: Path) -> Path:
    return canonical_base_json_path(Path(ui_root))


def default_ranges_json_path(ui_root: Path) -> Path:
    return canonical_ranges_json_path(Path(ui_root))


def default_suite_json_path(ui_root: Path, workspace_dir: Path) -> Path:
    return materialize_optimization_ready_suite_json(
        workspace_dir,
        base_json_path=default_base_json_path(ui_root),
        suite_source_path=canonical_suite_json_path(Path(ui_root)),
    )


def timestamp_stamp(now_text: str | None = None) -> str:
    return str(now_text or time.strftime("%Y%m%d_%H%M%S"))


def new_optimization_run_dir(
    workspace_dir: Path,
    pipeline_mode: str,
    *,
    now_text: str | None = None,
) -> Path:
    mode = str(pipeline_mode or "coordinator").strip().lower() or "coordinator"
    run_id = "staged" if mode == "staged" else "coord"
    problem_hash = f"{mode}_{timestamp_stamp(now_text)}"
    run_dir = build_optimization_run_dir(workspace_dir, run_id, problem_hash)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_optimization_launch_plan(
    session_state: Mapping[str, Any],
    *,
    run_dir: Path,
    ui_root: Path,
    python_executable: str,
    ui_jobs_default: int,
    env: Mapping[str, str] | None = None,
) -> LaunchPlan:
    python_exec = console_python_executable(python_executable)
    ui_root = Path(ui_root)
    tools_root = tools_root_from_ui_root(ui_root)
    workspace_dir = workspace_dir_for_ui_root(ui_root, env=env)
    use_staged = bool(session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT))

    obj_raw = str(session_state.get("opt_objectives", "") or "").strip()
    obj_keys = [item.strip() for item in re.split(r"[\n,;]+", obj_raw) if item.strip()]

    if use_staged:
        progress_path = staged_progress_path(run_dir)
        stop_file = run_dir / "STOP_OPTIMIZATION.txt"
        if stop_file.exists():
            try:
                stop_file.unlink()
            except Exception:
                pass
        out_csv = run_dir / "results_all.csv"
        cmd = [
            python_exec,
            str((ui_root / "opt_stage_runner_v1.py").resolve()),
            "--model",
            str(default_model_path(ui_root)),
            "--worker",
            str(default_worker_path(ui_root)),
            "--run_dir",
            str(run_dir),
            "--base_json",
            str(default_base_json_path(ui_root)),
            "--ranges_json",
            str(default_ranges_json_path(ui_root)),
            "--suite_json",
            str(default_suite_json_path(ui_root, workspace_dir)),
            "--out_csv",
            str(out_csv),
            "--progress_json",
            str(progress_path),
            "--stop_file",
            str(stop_file),
            "--minutes",
            str(float(session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT) or DIAGNOSTIC_OPT_MINUTES_DEFAULT)),
            "--seed_candidates",
            str(int(session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES) or DIAGNOSTIC_SEED_CANDIDATES)),
            "--seed_conditions",
            str(int(session_state.get("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS) or DIAGNOSTIC_SEED_CONDITIONS)),
            "--jobs",
            str(int(session_state.get("ui_jobs", ui_jobs_default) or ui_jobs_default)),
            "--flush_every",
            str(int(session_state.get("ui_flush_every", 20) or 20)),
            "--progress_every_sec",
            str(float(session_state.get("ui_progress_every_sec", 1.0) or 1.0)),
            "--warmstart_mode",
            str(session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE) or DIAGNOSTIC_WARMSTART_MODE),
            "--surrogate_samples",
            str(int(session_state.get("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES) or DIAGNOSTIC_SURROGATE_SAMPLES)),
            "--surrogate_top_k",
            str(int(session_state.get("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K) or DIAGNOSTIC_SURROGATE_TOP_K)),
            "--stop_pen_stage1",
            str(float(session_state.get("stop_pen_stage1", 25.0) or 25.0)),
            "--stop_pen_stage2",
            str(float(session_state.get("stop_pen_stage2", 15.0) or 15.0)),
            "--sort_tests_by_cost",
            "1" if bool(session_state.get("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)) else "0",
            "--eps_rel",
            str(float(session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL) or DIAGNOSTIC_INFLUENCE_EPS_REL)),
            "--stage_policy_mode",
            str(session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE),
            "--autoupdate_baseline",
            "1" if bool(session_state.get("opt_autoupdate_baseline", True)) else "0",
            "--penalty-key",
            str(session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT),
        ]
        for key in obj_keys:
            cmd += ["--objective", key]
        if bool(session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)):
            cmd.append("--adaptive_influence_eps")
            cmd += [
                "--adaptive_influence_eps_grid",
                influence_eps_grid_text(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID),
            ]
        return LaunchPlan(
            label="StageRunner",
            cmd=cmd,
            pipeline_mode="staged",
            progress_path=progress_path,
            budget=0,
            stop_file=stop_file,
        )

    backend_ui = str(session_state.get("opt_backend", "Dask"))
    backend_cli = "dask" if backend_ui == "Dask" else "ray"
    cmd = [
        python_exec,
        str((tools_root / "dist_opt_coordinator.py").resolve()),
        "--backend",
        backend_cli,
        "--run-dir",
        str(run_dir),
        "--model",
        str(default_model_path(ui_root)),
        "--worker",
        str(default_worker_path(ui_root)),
        "--base-json",
        str(default_base_json_path(ui_root)),
        "--ranges-json",
        str(default_ranges_json_path(ui_root)),
        "--suite-json",
        str(default_suite_json_path(ui_root, workspace_dir)),
        "--budget",
        str(int(session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT)),
        "--seed",
        str(int(session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT)),
        "--max-inflight",
        str(int(session_state.get("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT) or DIST_OPT_MAX_INFLIGHT_DEFAULT)),
        "--proposer",
        str(session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT)),
        "--q",
        str(int(session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT)),
        "--device",
        str(session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT)),
        "--penalty-key",
        str(session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT)),
        "--penalty-tol",
        str(session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT)),
    ]
    for key in obj_keys:
        cmd += ["--objective", key]
    cmd = append_coordinator_runtime_args(cmd, session_state, backend_cli=backend_cli)
    return LaunchPlan(
        label=backend_ui,
        cmd=cmd,
        pipeline_mode="coordinator",
        progress_path=None,
        budget=int(session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT),
    )


__all__ = [
    "LaunchPlan",
    "app_root_from_ui_root",
    "build_optimization_launch_plan",
    "default_base_json_path",
    "default_model_path",
    "default_ranges_json_path",
    "default_suite_json_path",
    "default_worker_path",
    "env_dir",
    "new_optimization_run_dir",
    "timestamp_stamp",
    "tools_root_from_ui_root",
    "ui_root_from_page_path",
    "workspace_dir_for_ui_root",
]
