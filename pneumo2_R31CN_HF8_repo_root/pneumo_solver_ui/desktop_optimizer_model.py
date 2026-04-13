from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from pneumo_solver_ui.optimization_baseline_source import resolve_workspace_baseline_source
from pneumo_solver_ui.optimization_defaults import (
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    DIAGNOSTIC_OPT_MINUTES_DEFAULT,
    DIAGNOSTIC_SEED_CANDIDATES,
    DIAGNOSTIC_SEED_CONDITIONS,
    DIAGNOSTIC_SORT_TESTS_BY_COST,
    DIAGNOSTIC_SURROGATE_SAMPLES,
    DIAGNOSTIC_SURROGATE_TOP_K,
    DIAGNOSTIC_WARMSTART_MODE,
    DIST_OPT_BOTORCH_MAXITER_DEFAULT,
    DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT,
    DIST_OPT_BOTORCH_N_INIT_DEFAULT,
    DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT,
    DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT,
    DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT,
    DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT,
    DIST_OPT_BUDGET_DEFAULT,
    DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT,
    DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT,
    DIST_OPT_DB_ENGINE_DEFAULT,
    DIST_OPT_DEVICE_DEFAULT,
    DIST_OPT_EXPORT_EVERY_DEFAULT,
    DIST_OPT_HV_LOG_DEFAULT,
    DIST_OPT_MAX_INFLIGHT_DEFAULT,
    DIST_OPT_PENALTY_KEY_DEFAULT,
    DIST_OPT_PENALTY_TOL_DEFAULT,
    DIST_OPT_PROPOSER_DEFAULT,
    DIST_OPT_Q_DEFAULT,
    DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT,
    DIST_OPT_SEED_DEFAULT,
    DIST_OPT_STALE_TTL_SEC_DEFAULT,
)
from pneumo_solver_ui.optimization_input_contract import (
    describe_runtime_stage,
    sanitize_optimization_inputs,
    summarize_enabled_stage_distribution,
)
from pneumo_solver_ui.optimization_launch_plan_runtime import (
    current_problem_hash_for_launch,
    default_base_json_path,
    default_model_path,
    default_ranges_json_path,
    default_stage_tuner_json_path,
    default_suite_json_path,
    default_worker_path,
    problem_hash_mode_for_launch,
    workspace_dir_for_ui_root,
)
from pneumo_solver_ui.optimization_objective_contract import (
    normalize_objective_keys,
    normalize_penalty_key,
    normalize_penalty_tol,
)
from pneumo_solver_ui.optimization_ready_preset import seed_optimization_ready_session_state
from pneumo_solver_ui.optimization_stage_policy import (
    DEFAULT_STAGE_POLICY_MODE,
    build_stage_seed_budget_plan,
    stage_policy_spec,
)
from pneumo_solver_ui.optimization_workspace_history_ui import HANDOFF_SORT_OPTIONS


STAGE_NAMES: tuple[str, ...] = (
    "stage0_relevance",
    "stage1_long",
    "stage2_final",
)

DASK_LOCAL_MODE = "Локальный кластер (создать автоматически)"
RAY_LOCAL_MODE = "Локальный кластер (создать автоматически)"

DESKTOP_OPTIMIZER_PROFILE_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "stage_triage",
        "StageRunner / Triage",
        "Быстрый staged triage для первичного физического фильтра и baseline sanity-check.",
    ),
    (
        "stage_validation",
        "StageRunner / Validation",
        "Более длинный staged path для проверки suite и stage policy перед handoff.",
    ),
    (
        "coord_dask_explore",
        "Coordinator / Dask Explore",
        "Локальный distributed перебор через Dask, когда search-space уже стабилизирован.",
    ),
    (
        "coord_ray_handoff",
        "Coordinator / Ray Handoff",
        "Ray-oriented профиль для continuation после staged handoff и short full-ring exploration.",
    ),
)

FINISHED_JOB_SORT_OPTIONS: tuple[str, ...] = (
    "Truth-ready first",
    "Verification first",
    "Recent first",
    "Least interference",
    "Most packaging rows",
)

PACKAGING_SORT_OPTIONS: tuple[str, ...] = (
    "Truth-ready first",
    "Zero interference first",
    "Verification first",
    "Most packaging rows",
    "Recent first",
)


@dataclass(frozen=True)
class DesktopOptimizerContractSnapshot:
    workspace_dir: Path
    model_path: Path
    worker_path: Path
    base_json_path: Path
    ranges_json_path: Path
    suite_json_path: Path
    stage_tuner_json_path: Path | None
    objective_keys: tuple[str, ...]
    penalty_key: str
    penalty_tol: float
    problem_hash_mode: str
    problem_hash: str
    baseline_source_kind: str
    baseline_source_label: str
    baseline_path: str
    base_param_count: int
    search_param_count: int
    suite_row_count: int
    enabled_suite_total: int
    enabled_stage_counts: dict[str, int]
    removed_runtime_knob_count: int
    widened_range_count: int
    sample_search_params: tuple[str, ...]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _json_dict(path: Path) -> dict[str, Any]:
    obj = _read_json(path)
    return dict(obj) if isinstance(obj, dict) else {}


def _json_list(path: Path) -> list[dict[str, Any]]:
    obj = _read_json(path)
    if not isinstance(obj, list):
        return []
    return [dict(item) for item in obj if isinstance(item, dict)]


def build_optimizer_session_defaults(
    *,
    cpu_count: int | None = None,
    platform_name: str | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    seed_optimization_ready_session_state(
        state,
        cpu_count=cpu_count,
        platform_name=platform_name,
    )
    state.setdefault("opt_stage_resume", False)
    state.setdefault("opt_resume", False)
    state.setdefault("opt_backend", "Dask")
    state.setdefault("opt_budget", DIST_OPT_BUDGET_DEFAULT)
    state.setdefault("opt_seed", DIST_OPT_SEED_DEFAULT)
    state.setdefault("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT)
    state.setdefault("opt_proposer", DIST_OPT_PROPOSER_DEFAULT)
    state.setdefault("opt_q", DIST_OPT_Q_DEFAULT)
    state.setdefault("opt_device", DIST_OPT_DEVICE_DEFAULT)
    state.setdefault("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT)
    state.setdefault("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT)
    state.setdefault("opt_db_engine", DIST_OPT_DB_ENGINE_DEFAULT)
    state.setdefault("opt_db_path", "")
    state.setdefault("opt_stale_ttl_sec", DIST_OPT_STALE_TTL_SEC_DEFAULT)
    state.setdefault("opt_hv_log", DIST_OPT_HV_LOG_DEFAULT)
    state.setdefault("opt_export_every", DIST_OPT_EXPORT_EVERY_DEFAULT)
    state.setdefault("opt_dist_run_id", "")
    state.setdefault("ui_flush_every", 20)
    state.setdefault("ui_progress_every_sec", 1.0)
    state.setdefault("stop_pen_stage1", 25.0)
    state.setdefault("stop_pen_stage2", 15.0)
    state.setdefault("adaptive_influence_eps", False)
    state.setdefault("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)
    state.setdefault("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE)
    state.setdefault("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES)
    state.setdefault("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K)
    state.setdefault("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT)
    state.setdefault("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES)
    state.setdefault("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS)
    state.setdefault("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL)
    state.setdefault("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE)
    state.setdefault("dask_mode", DASK_LOCAL_MODE)
    state.setdefault("dask_workers", max(1, int(os.cpu_count() or 4)))
    state.setdefault("dask_threads_per_worker", DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT)
    state.setdefault("dask_memory_limit", "")
    state.setdefault("dask_dashboard_address", DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT)
    state.setdefault("ray_mode", RAY_LOCAL_MODE)
    state.setdefault("ray_address", "auto")
    state.setdefault("ray_local_num_cpus", max(1, int(os.cpu_count() or 4)))
    state.setdefault("ray_local_dashboard_port", 0)
    state.setdefault("ray_local_dashboard", False)
    state.setdefault("ray_runtime_env_mode", DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT)
    state.setdefault("ray_runtime_env_json", "")
    state.setdefault("ray_runtime_exclude", "")
    state.setdefault("ray_num_evaluators", max(1, int(os.cpu_count() or 4)))
    state.setdefault("ray_cpus_per_evaluator", 1.0)
    state.setdefault("ray_num_proposers", 1)
    state.setdefault("ray_gpus_per_proposer", 0.0)
    state.setdefault("proposer_buffer", 128)
    state.setdefault("opt_botorch_n_init", DIST_OPT_BOTORCH_N_INIT_DEFAULT)
    state.setdefault("opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT)
    state.setdefault("opt_botorch_num_restarts", DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT)
    state.setdefault("opt_botorch_raw_samples", DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT)
    state.setdefault("opt_botorch_maxiter", DIST_OPT_BOTORCH_MAXITER_DEFAULT)
    state.setdefault("opt_botorch_ref_margin", DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT)
    state.setdefault(
        "opt_botorch_normalize_objectives",
        DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT,
    )
    state.setdefault("opt_auto_ring_suite_enabled", True)
    state.setdefault("opt_auto_stage_tuner_enabled", True)
    state.setdefault("opt_stage_tuner_json", "")
    state.setdefault("opt_launch_profile", "stage_triage")
    state.setdefault("opt_handoff_sort_mode", HANDOFF_SORT_OPTIONS[0])
    state.setdefault("opt_handoff_full_ring_only", False)
    state.setdefault("opt_handoff_done_only", False)
    state.setdefault("opt_handoff_min_seeds", 0)
    state.setdefault("opt_finished_sort_mode", FINISHED_JOB_SORT_OPTIONS[0])
    state.setdefault("opt_finished_done_only", False)
    state.setdefault("opt_finished_truth_ready_only", False)
    state.setdefault("opt_finished_verification_only", False)
    state.setdefault("opt_packaging_sort_mode", PACKAGING_SORT_OPTIONS[0])
    state.setdefault("opt_packaging_done_only", False)
    state.setdefault("opt_packaging_truth_ready_only", False)
    state.setdefault("opt_packaging_verification_only", False)
    state.setdefault("opt_packaging_zero_interference_only", False)
    return state


def launch_profile_label(profile_key: str) -> str:
    key = str(profile_key or "").strip()
    return launch_profile_label_map().get(key, key or "StageRunner / Triage")


def launch_profile_description(profile_key: str) -> str:
    key = str(profile_key or "").strip()
    return launch_profile_description_map().get(key, "")


def launch_profile_label_map() -> dict[str, str]:
    return {key: label for key, label, _desc in DESKTOP_OPTIMIZER_PROFILE_OPTIONS}


def launch_profile_description_map() -> dict[str, str]:
    return {key: desc for key, _label, desc in DESKTOP_OPTIMIZER_PROFILE_OPTIONS}


def launch_profile_labels() -> tuple[str, ...]:
    return tuple(label for _key, label, _desc in DESKTOP_OPTIMIZER_PROFILE_OPTIONS)


def launch_profile_key_for_label(label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return "stage_triage"
    for option_key, option_label, _desc in DESKTOP_OPTIMIZER_PROFILE_OPTIONS:
        if option_label == text:
            return option_key
    for option_key, _option_label, _desc in DESKTOP_OPTIMIZER_PROFILE_OPTIONS:
        if option_key == text:
            return option_key
    return "stage_triage"


def apply_launch_profile(
    snapshot: Mapping[str, Any],
    profile_key: str,
    *,
    cpu_count: int | None = None,
) -> tuple[dict[str, Any], list[str]]:
    current = dict(snapshot or {})
    updated = dict(current)
    changed_keys: list[str] = []

    worker_hint = max(1, int(cpu_count or os.cpu_count() or 4))
    dask_workers = max(1, min(worker_hint, 16))
    ray_evaluators = max(1, min(worker_hint, 16))

    def _set_value(key: str, value: Any) -> None:
        if updated.get(key) != value:
            updated[key] = value
            changed_keys.append(key)

    profile = str(profile_key or "stage_triage").strip() or "stage_triage"
    _set_value("opt_launch_profile", profile)

    if profile == "stage_validation":
        _set_value("opt_use_staged", True)
        _set_value("use_staged_opt", True)
        _set_value("ui_opt_minutes", 30.0)
        _set_value("ui_jobs", worker_hint)
        _set_value("ui_seed_candidates", 2)
        _set_value("ui_seed_conditions", 2)
        _set_value("adaptive_influence_eps", True)
        _set_value("warmstart_mode", "surrogate")
        _set_value("surrogate_samples", 12000)
        _set_value("surrogate_top_k", 96)
        _set_value("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE)
        _set_value("stop_pen_stage1", 35.0)
        _set_value("stop_pen_stage2", 20.0)
        _set_value("opt_autoupdate_baseline", True)
        _set_value("sort_tests_by_cost", True)
        _set_value("opt_stage_resume", False)
        _set_value("opt_resume", False)
        return updated, changed_keys

    if profile == "coord_dask_explore":
        _set_value("opt_use_staged", False)
        _set_value("use_staged_opt", False)
        _set_value("opt_backend", "Dask")
        _set_value("opt_budget", 300)
        _set_value("opt_seed", DIST_OPT_SEED_DEFAULT)
        _set_value("opt_max_inflight", 0)
        _set_value("opt_proposer", DIST_OPT_PROPOSER_DEFAULT)
        _set_value("opt_q", 1)
        _set_value("opt_device", DIST_OPT_DEVICE_DEFAULT)
        _set_value("dask_mode", DASK_LOCAL_MODE)
        _set_value("dask_workers", dask_workers)
        _set_value("dask_threads_per_worker", 1)
        _set_value("dask_dashboard_address", DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT)
        _set_value("opt_export_every", 50)
        _set_value("opt_hv_log", True)
        _set_value("opt_resume", False)
        _set_value("opt_stage_resume", False)
        return updated, changed_keys

    if profile == "coord_ray_handoff":
        _set_value("opt_use_staged", False)
        _set_value("use_staged_opt", False)
        _set_value("opt_backend", "Ray")
        _set_value("opt_budget", 120)
        _set_value("opt_seed", DIST_OPT_SEED_DEFAULT)
        _set_value("opt_max_inflight", 0)
        _set_value("opt_proposer", DIST_OPT_PROPOSER_DEFAULT)
        _set_value("opt_q", 2)
        _set_value("opt_device", DIST_OPT_DEVICE_DEFAULT)
        _set_value("ray_mode", RAY_LOCAL_MODE)
        _set_value("ray_address", "auto")
        _set_value("ray_num_evaluators", ray_evaluators)
        _set_value("ray_cpus_per_evaluator", 1.0)
        _set_value("ray_num_proposers", 1)
        _set_value("ray_gpus_per_proposer", 0.0)
        _set_value("proposer_buffer", 256)
        _set_value("opt_export_every", 20)
        _set_value("opt_hv_log", True)
        _set_value("opt_botorch_n_init", 16)
        _set_value("opt_botorch_min_feasible", 4)
        _set_value("opt_resume", False)
        _set_value("opt_stage_resume", False)
        return updated, changed_keys

    _set_value("opt_use_staged", True)
    _set_value("use_staged_opt", True)
    _set_value("ui_opt_minutes", 10.0)
    _set_value("ui_jobs", worker_hint)
    _set_value("ui_seed_candidates", 1)
    _set_value("ui_seed_conditions", 1)
    _set_value("adaptive_influence_eps", False)
    _set_value("warmstart_mode", "surrogate")
    _set_value("surrogate_samples", 4000)
    _set_value("surrogate_top_k", 32)
    _set_value("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE)
    _set_value("stop_pen_stage1", 25.0)
    _set_value("stop_pen_stage2", 15.0)
    _set_value("opt_autoupdate_baseline", True)
    _set_value("sort_tests_by_cost", True)
    _set_value("opt_stage_resume", False)
    _set_value("opt_resume", False)
    return updated, changed_keys


def build_contract_snapshot(
    session_state: Mapping[str, Any],
    *,
    ui_root: Path,
) -> DesktopOptimizerContractSnapshot:
    ui_root = Path(ui_root).resolve()
    workspace_dir = workspace_dir_for_ui_root(ui_root)
    base_json_path = default_base_json_path(ui_root)
    ranges_json_path = default_ranges_json_path(ui_root)
    suite_json_path = default_suite_json_path(
        ui_root,
        workspace_dir,
        session_state=session_state,
    )
    stage_tuner_json_path = default_stage_tuner_json_path(
        ui_root,
        workspace_dir,
        session_state=session_state,
        suite_json_path=suite_json_path,
        jobs_hint=int(session_state.get("ui_jobs", 4) or 4),
    )
    base_payload = _json_dict(base_json_path)
    ranges_payload = _json_dict(ranges_json_path)
    suite_payload = _json_list(suite_json_path)
    base_clean, ranges_clean, suite_clean, audit = sanitize_optimization_inputs(
        base_payload,
        ranges_payload,
        suite_payload,
    )
    stage_distribution = summarize_enabled_stage_distribution(suite_clean)
    problem_hash_mode = problem_hash_mode_for_launch(session_state)
    try:
        problem_hash = current_problem_hash_for_launch(
            session_state,
            ui_root=ui_root,
            workspace_dir=workspace_dir,
            problem_hash_mode=problem_hash_mode,
        )
    except Exception:
        problem_hash = ""
    baseline_source = resolve_workspace_baseline_source(
        problem_hash,
        workspace_dir=workspace_dir,
    )
    sample_search_params = tuple(sorted(str(key) for key in ranges_clean.keys())[:8])
    return DesktopOptimizerContractSnapshot(
        workspace_dir=workspace_dir,
        model_path=default_model_path(ui_root),
        worker_path=default_worker_path(ui_root),
        base_json_path=base_json_path,
        ranges_json_path=ranges_json_path,
        suite_json_path=suite_json_path,
        stage_tuner_json_path=Path(stage_tuner_json_path).resolve()
        if stage_tuner_json_path is not None
        else None,
        objective_keys=normalize_objective_keys(session_state.get("opt_objectives")),
        penalty_key=normalize_penalty_key(session_state.get("opt_penalty_key")),
        penalty_tol=normalize_penalty_tol(session_state.get("opt_penalty_tol")),
        problem_hash_mode=problem_hash_mode,
        problem_hash=str(problem_hash or ""),
        baseline_source_kind=str(baseline_source.get("source_kind") or ""),
        baseline_source_label=str(baseline_source.get("source_label") or ""),
        baseline_path=str(baseline_source.get("baseline_path") or ""),
        base_param_count=len(base_clean),
        search_param_count=len(ranges_clean),
        suite_row_count=len(suite_clean),
        enabled_suite_total=int(stage_distribution.get("enabled_total", 0) or 0),
        enabled_stage_counts=dict(stage_distribution.get("enabled_stage_counts") or {}),
        removed_runtime_knob_count=len(
            dict((audit.get("ranges") or {}).get("removed_non_design_keys") or {})
        ),
        widened_range_count=len(
            dict((audit.get("ranges") or {}).get("widened_to_include_base") or {})
        ),
        sample_search_params=sample_search_params,
    )


def build_stage_policy_blueprint_rows(
    session_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    requested_mode = str(
        session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE)
        or DEFAULT_STAGE_POLICY_MODE
    )
    total_seed_cap = int(
        session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES)
        or DIAGNOSTIC_SEED_CANDIDATES
    )
    rows: list[dict[str, Any]] = []
    for stage_name in STAGE_NAMES:
        spec = stage_policy_spec(stage_name)
        plan = build_stage_seed_budget_plan(
            stage_name,
            total_seed_cap=total_seed_cap,
            requested_mode=requested_mode,
            stage_influence_summary={},
        )
        rows.append(
            {
                "stage_name": stage_name,
                "role": describe_runtime_stage(stage_name),
                "policy_name": str(spec.get("policy_name") or ""),
                "top_k": int(spec.get("top_k", 0) or 0),
                "explore_frac": float(spec.get("explore_frac", 0.0) or 0.0),
                "alpha": float(spec.get("alpha", 0.0) or 0.0),
                "requested_mode": requested_mode,
                "effective_mode": str(plan.get("effective_mode") or requested_mode),
                "explore_budget": int(plan.get("explore_budget", 0) or 0),
                "focus_budget": int(plan.get("focus_budget", 0) or 0),
                "fallback_reason": str(plan.get("fallback_reason") or ""),
            }
        )
    return rows


__all__ = [
    "DASK_LOCAL_MODE",
    "DESKTOP_OPTIMIZER_PROFILE_OPTIONS",
    "FINISHED_JOB_SORT_OPTIONS",
    "PACKAGING_SORT_OPTIONS",
    "DesktopOptimizerContractSnapshot",
    "RAY_LOCAL_MODE",
    "STAGE_NAMES",
    "apply_launch_profile",
    "build_contract_snapshot",
    "build_optimizer_session_defaults",
    "build_stage_policy_blueprint_rows",
    "launch_profile_description",
    "launch_profile_description_map",
    "launch_profile_key_for_label",
    "launch_profile_label",
    "launch_profile_label_map",
    "launch_profile_labels",
]
