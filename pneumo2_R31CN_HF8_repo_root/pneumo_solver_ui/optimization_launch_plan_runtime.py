from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from pneumo_dist.trial_hash import hash_file, hash_problem, make_problem_spec, stable_hash_problem
from pneumo_solver_ui.optimization_defaults import (
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS,
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    DIAGNOSTIC_OPT_MINUTES_DEFAULT,
    DIAGNOSTIC_PROBLEM_HASH_MODE,
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
from pneumo_solver_ui.optimization_input_contract import (
    sanitize_optimization_inputs,
)
from pneumo_solver_ui.optimization_auto_ring_suite import (
    materialize_optimization_auto_ring_suite_json,
)
from pneumo_solver_ui.optimization_auto_tuner_plan import (
    is_auto_ring_suite_json,
    materialize_optimization_auto_tuner_plan_json,
)
from pneumo_solver_ui.optimization_objective_contract import (
    normalize_objective_keys,
    normalize_penalty_key,
    normalize_penalty_tol,
)
from pneumo_solver_ui.optimization_problem_hash_mode import (
    normalize_problem_hash_mode,
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
    launch_run_dir: Optional[Path] = None


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


def _read_json_mapping(path: Path) -> Mapping[str, Any] | None:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, Mapping) else None


def _looks_like_ring_scenario_json(path: Path) -> bool:
    payload = _read_json_mapping(path)
    if not isinstance(payload, Mapping):
        return False
    if list(payload.get("segments") or []):
        return True
    schema_version = str(payload.get("schema_version") or "").strip().lower()
    if schema_version.startswith("ring_") or schema_version.startswith("ring"):
        return True
    meta = payload.get("_generated_meta")
    return isinstance(meta, Mapping) and ("lap_time_s" in meta or "ring_length_m" in meta)


def _existing_path(raw: Any) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        path = Path(text).expanduser().resolve()
    except Exception:
        return None
    return path if path.exists() else None


def _session_auto_ring_sidecars(
    session_state: Mapping[str, Any] | None,
    workspace_dir: Path,
) -> dict[str, Path] | None:
    if session_state is None:
        return None
    if not bool(session_state.get("opt_auto_ring_suite_enabled", True)):
        return None

    explicit_key_sets = [
        ("opt_auto_ring_road_csv", "opt_auto_ring_axay_csv", "opt_auto_ring_scenario_json"),
        ("auto_ring_road_csv", "auto_ring_axay_csv", "auto_ring_scenario_json"),
    ]
    for road_key, axay_key, scenario_key in explicit_key_sets:
        road = _existing_path(session_state.get(road_key))
        axay = _existing_path(session_state.get(axay_key))
        scenario = _existing_path(session_state.get(scenario_key))
        if road and axay and scenario and _looks_like_ring_scenario_json(scenario):
            return {"road_csv": road, "axay_csv": axay, "scenario_json": scenario}

    exports_dir = Path(workspace_dir) / "exports"
    road = exports_dir / "anim_latest_road_csv.csv"
    axay = exports_dir / "anim_latest_axay_csv.csv"
    scenario = exports_dir / "anim_latest_scenario_json.json"
    if road.exists() and axay.exists() and scenario.exists() and _looks_like_ring_scenario_json(scenario):
        return {"road_csv": road.resolve(), "axay_csv": axay.resolve(), "scenario_json": scenario.resolve()}
    return None


def default_suite_json_path(
    ui_root: Path,
    workspace_dir: Path,
    *,
    session_state: Mapping[str, Any] | None = None,
) -> Path:
    auto_ring = _session_auto_ring_sidecars(session_state, Path(workspace_dir))
    if auto_ring is not None:
        return materialize_optimization_auto_ring_suite_json(
            workspace_dir,
            suite_source_path=canonical_suite_json_path(Path(ui_root)),
            road_csv=auto_ring["road_csv"],
            axay_csv=auto_ring["axay_csv"],
            scenario_json=auto_ring["scenario_json"],
        )
    return materialize_optimization_ready_suite_json(
        workspace_dir,
        base_json_path=default_base_json_path(ui_root),
        suite_source_path=canonical_suite_json_path(Path(ui_root)),
    )


def default_stage_tuner_json_path(
    ui_root: Path,
    workspace_dir: Path,
    *,
    session_state: Mapping[str, Any] | None = None,
    suite_json_path: Path | None = None,
    jobs_hint: int = 8,
) -> Path | None:
    if session_state is None:
        return None
    if not bool(session_state.get("opt_auto_stage_tuner_enabled", True)):
        return None

    explicit = _existing_path(
        session_state.get("opt_stage_tuner_json")
        or session_state.get("stage_tuner_json")
    )
    if explicit is not None:
        return explicit

    suite_path = Path(suite_json_path or default_suite_json_path(ui_root, workspace_dir, session_state=session_state)).resolve()
    if not is_auto_ring_suite_json(suite_path):
        return None

    return materialize_optimization_auto_tuner_plan_json(
        workspace_dir,
        suite_json_path=suite_path,
        minutes_total=float(
            session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT)
            or DIAGNOSTIC_OPT_MINUTES_DEFAULT
        ),
        jobs_hint=int(session_state.get("ui_jobs", jobs_hint) or jobs_hint),
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


def _current_objective_keys(session_state: Mapping[str, Any]) -> tuple[str, ...]:
    return normalize_objective_keys(session_state.get("opt_objectives"))


def problem_hash_mode_for_launch(
    session_state: Mapping[str, Any],
    *,
    problem_hash_mode: str | None = None,
) -> str:
    raw = (
        problem_hash_mode
        if problem_hash_mode is not None
        else session_state.get("settings_opt_problem_hash_mode", DIAGNOSTIC_PROBLEM_HASH_MODE)
    )
    return normalize_problem_hash_mode(raw, default=DIAGNOSTIC_PROBLEM_HASH_MODE)


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _optimization_signature_payload(
    *,
    model_path: Path,
    worker_path: Path,
    base_payload: Mapping[str, Any],
    ranges_payload: Mapping[str, Any],
    suite_payload: Any,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "model_sha256": str(hash_file(model_path)),
        "worker_sha256": str(hash_file(worker_path)),
        "base_signature": dict(base_payload),
        "ranges_signature": dict(ranges_payload),
        "suite_signature": suite_payload,
        "extra": dict(extra),
    }


def _stage_signature_payload_for_launch(
    session_state: Mapping[str, Any],
    *,
    ui_root: Path,
    workspace_dir: Path,
) -> dict[str, Any]:
    ui_root = Path(ui_root)
    base_raw = _read_json_dict(default_base_json_path(ui_root))
    ranges_raw = _read_json_dict(default_ranges_json_path(ui_root))
    suite_path = default_suite_json_path(ui_root, workspace_dir, session_state=session_state)
    try:
        suite_raw = json.loads(suite_path.read_text(encoding="utf-8"))
    except Exception:
        suite_raw = []
    base_clean, ranges_clean, suite_clean, _audit = sanitize_optimization_inputs(base_raw, ranges_raw, suite_raw)
    return _optimization_signature_payload(
        model_path=default_model_path(ui_root),
        worker_path=default_worker_path(ui_root),
        base_payload=base_clean,
        ranges_payload=ranges_clean,
        suite_payload=suite_clean,
        extra={
            "objective_keys": list(_current_objective_keys(session_state)),
            "penalty_key": normalize_penalty_key(session_state.get("opt_penalty_key")),
        },
    )


def coordinator_problem_hash_for_launch(
    session_state: Mapping[str, Any],
    *,
    ui_root: Path,
    workspace_dir: Path,
    problem_hash_mode: str | None = None,
) -> str:
    ui_root = Path(ui_root)
    hash_mode = problem_hash_mode_for_launch(
        session_state,
        problem_hash_mode=problem_hash_mode,
    )
    suite_path = default_suite_json_path(ui_root, workspace_dir, session_state=session_state)
    problem_spec = make_problem_spec(
        model_path=str(default_model_path(ui_root)),
        worker_path=str(default_worker_path(ui_root)),
        base_json=str(default_base_json_path(ui_root)),
        ranges_json=str(default_ranges_json_path(ui_root)),
        suite_json=str(suite_path),
        cfg={
            "objective_keys": list(_current_objective_keys(session_state)),
            "penalty_key": normalize_penalty_key(session_state.get("opt_penalty_key")),
            "penalty_tol": normalize_penalty_tol(session_state.get("opt_penalty_tol")),
        },
        include_file_hashes=True,
    )
    if hash_mode == "legacy":
        return str(hash_problem(problem_spec))
    base_raw = _read_json_dict(default_base_json_path(ui_root))
    ranges_raw = _read_json_dict(default_ranges_json_path(ui_root))
    try:
        suite_raw = json.loads(suite_path.read_text(encoding="utf-8"))
    except Exception:
        suite_raw = []
    return str(
        stable_hash_problem(
            base=base_raw,
            ranges=ranges_raw,
            suite=suite_raw,
            model_sha256=str(problem_spec.model_sha256 or ""),
            worker_sha256=str(problem_spec.worker_sha256 or ""),
            extra={
                "objective_keys": list(_current_objective_keys(session_state)),
                "penalty_key": normalize_penalty_key(session_state.get("opt_penalty_key")),
                "penalty_tol": normalize_penalty_tol(session_state.get("opt_penalty_tol")),
            },
            mode="stable",
        )
    )


def staged_problem_hash_for_launch(
    session_state: Mapping[str, Any],
    *,
    ui_root: Path,
    workspace_dir: Path,
    problem_hash_mode: str | None = None,
) -> str:
    hash_mode = problem_hash_mode_for_launch(
        session_state,
        problem_hash_mode=problem_hash_mode,
    )
    payload = _stage_signature_payload_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace_dir,
    )
    return str(
        stable_hash_problem(
            base=payload["base_signature"],
            ranges=payload["ranges_signature"],
            suite=payload["suite_signature"],
            model_sha256=payload["model_sha256"],
            worker_sha256=payload["worker_sha256"],
            extra=payload["extra"],
            mode=hash_mode,
        )
    )


def current_problem_hash_for_launch(
    session_state: Mapping[str, Any],
    *,
    ui_root: Path,
    workspace_dir: Path,
    problem_hash_mode: str | None = None,
) -> str:
    if bool(session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)):
        return staged_problem_hash_for_launch(
            session_state,
            ui_root=ui_root,
            workspace_dir=workspace_dir,
            problem_hash_mode=problem_hash_mode,
        )
    return coordinator_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace_dir,
        problem_hash_mode=problem_hash_mode,
    )


def _iter_existing_run_dirs(workspace_dir: Path, pipeline_mode: str):
    mode = str(pipeline_mode or "").strip().lower()
    run_id = "staged" if mode == "staged" else "coord"
    root = Path(workspace_dir) / "opt_runs" / run_id
    if not root.exists():
        return []
    try:
        dirs = [p for p in root.iterdir() if p.is_dir()]
    except Exception:
        return []
    dirs.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    return dirs


def _stored_problem_hash(run_dir: Path) -> str:
    try:
        return (Path(run_dir) / "problem_hash.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _raise_resume_problem_hash_mismatch(
    *,
    run_dir: Path,
    stored_problem_hash: str,
    expected_problem_hash: str,
    pipeline_mode: str,
) -> None:
    raise RuntimeError(
        "Resume problem_hash mismatch: "
        f"pipeline={pipeline_mode}, run_dir={Path(run_dir)}, "
        f"stored={stored_problem_hash}, expected={expected_problem_hash}. "
        "Objective stack, hard gate, suite or baseline scope changed; choose a compatible run or start a new run."
    )


def _selected_history_run_dir(session_state: Mapping[str, Any], *, pipeline_mode: str) -> Path | None:
    raw = str(session_state.get("__opt_history_selected_run_dir", "") or "").strip()
    if not raw:
        return None
    run_dir = Path(raw)
    if not run_dir.exists() or not run_dir.is_dir():
        return None
    expected_parent = "staged" if str(pipeline_mode).strip().lower() == "staged" else "coord"
    if run_dir.parent.name.lower() != expected_parent:
        return None
    return run_dir


def coordinator_resume_run_dir(
    session_state: Mapping[str, Any],
    *,
    workspace_dir: Path,
    ui_root: Path,
    problem_hash_mode: str | None = None,
) -> Path:
    workspace_dir = Path(workspace_dir)
    ui_root = Path(ui_root)
    explicit_run_id = str(session_state.get("opt_dist_run_id", "") or "").strip()
    problem_hash = coordinator_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace_dir,
        problem_hash_mode=problem_hash_mode,
    )
    candidates = _iter_existing_run_dirs(workspace_dir, "coordinator")

    if explicit_run_id:
        for run_dir in candidates:
            try:
                candidate_run_id = (run_dir / "run_id.txt").read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if candidate_run_id == explicit_run_id:
                stored = _stored_problem_hash(run_dir)
                if stored and stored != problem_hash:
                    _raise_resume_problem_hash_mismatch(
                        run_dir=run_dir,
                        stored_problem_hash=stored,
                        expected_problem_hash=problem_hash,
                        pipeline_mode="coordinator",
                    )
                return run_dir

    for run_dir in candidates:
        try:
            if (run_dir / "problem_hash.txt").read_text(encoding="utf-8").strip() == problem_hash:
                return run_dir
        except Exception:
            continue

    run_dir = build_optimization_run_dir(workspace_dir, "coord", problem_hash)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def staged_resume_run_dir(
    session_state: Mapping[str, Any],
    *,
    workspace_dir: Path,
    ui_root: Path,
    problem_hash_mode: str | None = None,
) -> Path:
    workspace_dir = Path(workspace_dir)
    ui_root = Path(ui_root)
    problem_hash = staged_problem_hash_for_launch(
        session_state,
        ui_root=ui_root,
        workspace_dir=workspace_dir,
        problem_hash_mode=problem_hash_mode,
    )

    selected_run = _selected_history_run_dir(session_state, pipeline_mode="staged")
    if selected_run is not None:
        stored = _stored_problem_hash(selected_run)
        if stored and stored != problem_hash:
            _raise_resume_problem_hash_mismatch(
                run_dir=selected_run,
                stored_problem_hash=stored,
                expected_problem_hash=problem_hash,
                pipeline_mode="staged",
            )
        if not stored or stored == problem_hash:
            return selected_run

    for run_dir in _iter_existing_run_dirs(workspace_dir, "staged"):
        stored = _stored_problem_hash(run_dir)
        if stored and stored == problem_hash:
            return run_dir

    run_dir = build_optimization_run_dir(workspace_dir, "staged", problem_hash)
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
    suite_path = default_suite_json_path(ui_root, workspace_dir, session_state=session_state)
    stage_tuner_path = default_stage_tuner_json_path(
        ui_root,
        workspace_dir,
        session_state=session_state,
        suite_json_path=suite_path,
        jobs_hint=int(session_state.get("ui_jobs", ui_jobs_default) or ui_jobs_default),
    ) if use_staged else None

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
            str(suite_path),
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
        if stage_tuner_path is not None:
            cmd += ["--stage_tuner_json", str(stage_tuner_path)]
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
        str(suite_path),
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
    "coordinator_problem_hash_for_launch",
    "coordinator_resume_run_dir",
    "current_problem_hash_for_launch",
    "default_base_json_path",
    "default_model_path",
    "default_ranges_json_path",
    "default_suite_json_path",
    "default_stage_tuner_json_path",
    "default_worker_path",
    "env_dir",
    "new_optimization_run_dir",
    "problem_hash_mode_for_launch",
    "staged_problem_hash_for_launch",
    "staged_resume_run_dir",
    "timestamp_stamp",
    "tools_root_from_ui_root",
    "ui_root_from_page_path",
    "workspace_dir_for_ui_root",
]
