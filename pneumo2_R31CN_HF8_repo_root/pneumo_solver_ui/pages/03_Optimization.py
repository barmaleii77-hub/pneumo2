"""Оптимизация (инженерный раздел).

Цели раздела:
- все настройки оптимизации доступны всегда (без "экспертных режимов"), но разложены по смысловым блокам;
- поддержка двух бэкендов распределённых вычислений: Dask и Ray;
- UI умеет *сам* запускать локальный кластер (без ручных команд) и запускать оптимизацию через координатор;
- результаты "последней оптимизации" автоматически подхватываются всеми страницами через run_artifacts.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from pneumo_solver_ui.streamlit_compat import request_rerun
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui import run_artifacts
from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
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
    canonical_base_json_path,
    canonical_model_path,
    canonical_ranges_json_path,
    canonical_suite_json_path,
    canonical_worker_path,
    diagnostics_jobs_default,
    influence_eps_grid_text,
    objectives_text,
    stage_aware_influence_profiles_text,
)
from pneumo_solver_ui.optimization_distributed_wiring import (
    RAY_RUNTIME_ENV_MODES,
    append_coordinator_runtime_args,
    botorch_runtime_status,
    botorch_status_markdown,
    migrated_ray_runtime_env_json,
    migrated_ray_runtime_env_mode,
)
from pneumo_solver_ui.optimization_progress_live import summarize_staged_progress
from pneumo_solver_ui.optimization_runtime_paths import (
    build_optimization_run_dir,
    console_python_executable,
    staged_progress_path,
)
from pneumo_solver_ui.optimization_run_history import (
    discover_workspace_optimization_runs,
    format_run_choice,
    summarize_optimization_run,
)
from pneumo_solver_ui.optimization_stage_policy import (
    DEFAULT_STAGE_POLICY_MODE,
    stage_seed_policy_summary_text,
)
from pneumo_solver_ui.optimization_stage_policy_live import summarize_stage_policy_runtime
from pneumo_solver_ui.process_tree import terminate_process_tree
from pneumo_solver_ui.optimization_ready_preset import (
    materialize_optimization_ready_suite_json,
    seed_optimization_ready_session_state,
)


bootstrap(st)
seed_optimization_ready_session_state(st.session_state, cpu_count=int(os.cpu_count() or 4), platform_name=sys.platform)

_UI_JOBS_DEFAULT = int(diagnostics_jobs_default(os.cpu_count(), platform_name=sys.platform))

st.set_page_config(page_title="Пневмо‑UI | Оптимизация", layout="wide")


# ---------------------------
# Helpers
# ---------------------------


@dataclass
class DistOptJob:
    proc: subprocess.Popen
    run_dir: Path
    log_path: Path
    started_ts: float
    budget: int
    backend: str
    pipeline_mode: str
    progress_path: Optional[Path] = None
    stop_file: Optional[Path] = None


@dataclass
class LaunchPlan:
    label: str
    cmd: list[str]
    pipeline_mode: str
    progress_path: Optional[Path]
    budget: int
    stop_file: Optional[Path] = None


def _app_root() -> Path:
    # .../PneumoApp_v6_80/pneumo_solver_ui/pages/03_Optimization.py -> .../PneumoApp_v6_80
    return Path(__file__).resolve().parents[2]


def _ui_root() -> Path:
    # .../PneumoApp_v6_80/pneumo_solver_ui
    return Path(__file__).resolve().parents[1]


def _tools_root() -> Path:
    return _ui_root() / "tools"


def _env_dir(key: str, default: Path) -> Path:
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        return Path(raw).expanduser().resolve()
    except Exception:
        return Path(raw)


def _workspace_dir() -> Path:
    ws = _env_dir("PNEUMO_WORKSPACE_DIR", _ui_root() / "workspace")
    try:
        ws.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return ws


def _default_model_path() -> Path:
    return canonical_model_path(_ui_root())


def _default_worker_path() -> Path:
    return canonical_worker_path(_ui_root())


def _default_base_json_path() -> Path:
    return canonical_base_json_path(_ui_root())


def _default_ranges_json_path() -> Path:
    return canonical_ranges_json_path(_ui_root())


def _default_suite_json_path() -> Path:
    return materialize_optimization_ready_suite_json(
        _workspace_dir(),
        base_json_path=_default_base_json_path(),
        suite_source_path=canonical_suite_json_path(_ui_root()),
    )


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _new_run_dir(pipeline_mode: str) -> Path:
    mode = str(pipeline_mode or "coordinator").strip().lower() or "coordinator"
    run_id = "staged" if mode == "staged" else "coord"
    problem_hash = f"{mode}_{_stamp()}"
    run_dir = build_optimization_run_dir(_workspace_dir(), run_id, problem_hash)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _tail_file_text(path: Path, max_bytes: int = 24_000) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[не удалось прочитать лог: {e}]"


_PROGRESS_RE = re.compile(r"\bdone=(\d+)(?:/(\d+))?")


def _parse_done_from_log(text: str) -> Optional[int]:
    # Берём ПОСЛЕДНЕЕ совпадение
    matches = list(_PROGRESS_RE.finditer(text))
    if not matches:
        return None
    try:
        return int(matches[-1].group(1))
    except Exception:
        return None


def _job_from_state() -> Optional[DistOptJob]:
    raw = st.session_state.get("__dist_opt_job")
    if not raw:
        return None
    try:
        return DistOptJob(**raw)
    except Exception:
        return None


def _save_job(job: DistOptJob) -> None:
    st.session_state["__dist_opt_job"] = {
        "proc": job.proc,
        "run_dir": job.run_dir,
        "log_path": job.log_path,
        "started_ts": job.started_ts,
        "budget": int(job.budget),
        "backend": str(job.backend),
        "pipeline_mode": str(job.pipeline_mode),
        "progress_path": job.progress_path,
        "stop_file": job.stop_file,
    }


def _clear_job() -> None:
    st.session_state.pop("__dist_opt_job", None)


def _write_soft_stop_file(stop_file: Optional[Path]) -> bool:
    if stop_file is None:
        return False
    try:
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("stop", encoding="utf-8")
        return True
    except Exception:
        return False


def _soft_stop_requested(job: DistOptJob) -> bool:
    try:
        return bool(job.stop_file and Path(job.stop_file).exists())
    except Exception:
        return False


def _terminate_process(proc: subprocess.Popen) -> None:
    try:
        terminate_process_tree(proc, grace_sec=0.8, reason="optimization_hard_stop")
        return
    except Exception:
        pass
    try:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass


def _build_cmd(run_dir: Path) -> LaunchPlan:
    """Build launch command based on *current* UI state.

    The page now exposes both execution pipelines:
    - StageRunner (staged seed/promotion policy, warm-start, influence-aware);
    - Distributed coordinator (Dask/Ray/BoTorch path).
    """

    python_exec = console_python_executable(sys.executable)
    tools = _tools_root()
    use_staged = bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT))

    # Objectives: newline/comma separated in UI. StageRunner and coordinator must
    # share the same explicit contract, otherwise UI alignment would stay purely cosmetic.
    obj_raw = str(st.session_state.get("opt_objectives", "") or "").strip()
    obj_keys = [
        s.strip()
        for s in re.split(r"[\n,;]+", obj_raw)
        if s.strip()
    ]

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
            str((_ui_root() / "opt_stage_runner_v1.py").resolve()),
            "--model",
            str(_default_model_path()),
            "--worker",
            str(_default_worker_path()),
            "--run_dir",
            str(run_dir),
            "--base_json",
            str(_default_base_json_path()),
            "--ranges_json",
            str(_default_ranges_json_path()),
            "--suite_json",
            str(_default_suite_json_path()),
            "--out_csv",
            str(out_csv),
            "--progress_json",
            str(progress_path),
            "--stop_file",
            str(stop_file),
            "--minutes",
            str(float(st.session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT) or DIAGNOSTIC_OPT_MINUTES_DEFAULT)),
            "--seed_candidates",
            str(int(st.session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES) or DIAGNOSTIC_SEED_CANDIDATES)),
            "--seed_conditions",
            str(int(st.session_state.get("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS) or DIAGNOSTIC_SEED_CONDITIONS)),
            "--jobs",
            str(int(st.session_state.get("ui_jobs", _UI_JOBS_DEFAULT) or _UI_JOBS_DEFAULT)),
            "--flush_every",
            str(int(st.session_state.get("ui_flush_every", 20) or 20)),
            "--progress_every_sec",
            str(float(st.session_state.get("ui_progress_every_sec", 1.0) or 1.0)),
            "--warmstart_mode",
            str(st.session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE) or DIAGNOSTIC_WARMSTART_MODE),
            "--surrogate_samples",
            str(int(st.session_state.get("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES) or DIAGNOSTIC_SURROGATE_SAMPLES)),
            "--surrogate_top_k",
            str(int(st.session_state.get("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K) or DIAGNOSTIC_SURROGATE_TOP_K)),
            "--stop_pen_stage1",
            str(float(st.session_state.get("stop_pen_stage1", 25.0) or 25.0)),
            "--stop_pen_stage2",
            str(float(st.session_state.get("stop_pen_stage2", 15.0) or 15.0)),
            "--sort_tests_by_cost",
            "1" if bool(st.session_state.get("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)) else "0",
            "--eps_rel",
            str(float(st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL) or DIAGNOSTIC_INFLUENCE_EPS_REL)),
            "--stage_policy_mode",
            str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE),
            "--autoupdate_baseline",
            "1" if bool(st.session_state.get("opt_autoupdate_baseline", True)) else "0",
            "--penalty-key",
            str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT),
        ]
        for k in obj_keys:
            cmd += ["--objective", k]
        if bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)):
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

    backend_ui = str(st.session_state.get("opt_backend", "Dask"))
    backend_cli = "dask" if backend_ui == "Dask" else "ray"

    cmd = [
        python_exec,
        str((tools / "dist_opt_coordinator.py").resolve()),
        "--backend",
        backend_cli,
        "--run-dir",
        str(run_dir),
        "--model",
        str(_default_model_path()),
        "--worker",
        str(_default_worker_path()),
        "--base-json",
        str(_default_base_json_path()),
        "--ranges-json",
        str(_default_ranges_json_path()),
        "--suite-json",
        str(_default_suite_json_path()),
        "--budget",
        str(int(st.session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT)),
        "--seed",
        str(int(st.session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT)),
        "--max-inflight",
        str(int(st.session_state.get("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT) or DIST_OPT_MAX_INFLIGHT_DEFAULT)),
        "--proposer",
        str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT)),
        "--q",
        str(int(st.session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT)),
        "--device",
        str(st.session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT)),
        "--penalty-key",
        str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT)),
        "--penalty-tol",
        str(st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT)),
    ]

    for k in obj_keys:
        cmd += ["--objective", k]

    cmd = append_coordinator_runtime_args(cmd, st.session_state, backend_cli=backend_cli)
    return LaunchPlan(
        label=backend_ui,
        cmd=cmd,
        pipeline_mode="coordinator",
        progress_path=None,
        budget=int(st.session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT),
    )


def _render_last_opt_summary() -> None:
    ptr = st.session_state.get("last_opt_ptr")
    meta = st.session_state.get("last_opt_meta") or {}

    if not ptr:
        st.info("Последняя оптимизация пока не запускалась (или артефакты не найдены).")
        return

    st.success("Найдены результаты последней оптимизации.")
    cols = st.columns([3, 2, 2])
    with cols[0]:
        st.write(f"**Папка:** `{ptr}`")
    with cols[1]:
        st.write(f"**Бэкенд:** {meta.get('backend', '—')}")
    with cols[2]:
        st.write(f"**Время:** {meta.get('ts', '—')}")

    last_obj = [str(x).strip() for x in (meta.get('objective_keys') or []) if str(x).strip()] if isinstance(meta.get('objective_keys'), (list, tuple)) else []
    last_penalty_key = str(meta.get('penalty_key') or '').strip()
    last_penalty_tol = meta.get('penalty_tol')
    if last_obj:
        st.write("**Objective stack:** " + ", ".join(last_obj))
    if last_penalty_key:
        hard_gate = f"`{last_penalty_key}`"
        try:
            if last_penalty_tol is not None:
                hard_gate += f" (tol={float(last_penalty_tol):g})"
        except Exception:
            pass
        st.write(f"**Hard gate:** {hard_gate}")

    btn_cols = st.columns([1, 1, 2])
    with btn_cols[0]:
        if st.button("Открыть результаты", help="Перейти на страницу просмотра результатов оптимизации"):
            try:
                st.switch_page("pages/20_DistributedOptimization.py")
            except Exception:
                st.info("Откройте страницу 'Результаты оптимизации' в меню слева.")
    with btn_cols[1]:
        if st.button("Открыть папку", help="Показать путь к папке в виде текста"):
            st.code(str(ptr))


def _current_objective_keys() -> list[str]:
    raw = str(
        st.session_state.get(
            "opt_objectives",
            objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES),
        )
        or ""
    ).strip()
    keys = [s.strip() for s in re.split(r"[\n,;]+", raw) if s.strip()]
    return keys or [str(x) for x in DEFAULT_OPTIMIZATION_OBJECTIVES]


def _render_physical_workflow_block() -> None:
    current_obj = _current_objective_keys()
    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.metric("Physics-first path", "StageRunner")
    with cols[1]:
        st.metric("Trade-study path", "Distributed")
    with cols[2]:
        st.metric("Hard gate", str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT))

    st.caption(
        "Отдельной powertrain / engine-map модели в live optimization contract сейчас нет. "
        "Честный физический scope текущего оптимизатора — сигналы подвески, дороги и реакции кузова."
    )
    st.caption(
        "StageRunner — physics-first путь: дешёвые стадии и ранний отсев. Быстрый stop/fail на stage0/stage1 — это штатно, "
        "если кандидат сразу выбивается по физике или penalty gate."
    )
    st.caption(
        "Distributed coordinator — длинный trade study после того, как search-space и suite уже стабилизированы. "
        "Он нужен не вместо physical gate, а после него."
    )
    st.caption(
        "Канонический minimize-safe стек целей для coordinator и StageRunner promotion/baseline: " + ", ".join(str(x) for x in DEFAULT_OPTIMIZATION_OBJECTIVES)
    )
    st.caption(
        "Текущий objective stack: " + ", ".join(current_obj)
    )
    st.caption(
        "Если нужна другая постановка — правьте objective keys ниже вручную. И coordinator, и StageRunner будут читать один и тот же stack; блок ничего не скрывает и не режет настройки."
    )
    if st.button(
        "Вернуть канонический objective stack (comfort / roll / energy)",
        key="opt_restore_default_objectives",
        help="Подставляет текущий канонический стек целей в editable objective textarea ниже.",
    ):
        st.session_state["opt_objectives"] = objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES)
        st.success("Канонический objective stack подставлен в editable поле ниже.")
        request_rerun(st)


def _render_workspace_run_history(active_job: Optional[DistOptJob]) -> None:
    active_run_dir = active_job.run_dir if active_job is not None else None
    summaries = discover_workspace_optimization_runs(_workspace_dir(), active_run_dir=active_run_dir)
    if not summaries:
        st.info("В текущем workspace ещё нет запусков оптимизации на диске.")
        return

    st.caption(
        "Если вы запускаете оптимизации последовательно (например, сначала StageRunner, потом coordinator), "
        "это нормальный инженерный сценарий. staged и coordinator run dirs показаны одновременно, чтобы второй запуск не затирал понимание первого."
    )

    option_map = {str(item.run_dir): item for item in summaries}
    option_keys = list(option_map.keys())
    preferred = str(st.session_state.get("__opt_history_selected_run_dir") or option_keys[0])
    if preferred not in option_map:
        preferred = option_keys[0]
    selected_run_dir = st.selectbox(
        "Выберите run для разбора",
        options=option_keys,
        index=option_keys.index(preferred),
        key="__opt_history_selected_run_dir",
        format_func=lambda key: format_run_choice(option_map[key]),
        help=(
            "Здесь сохраняется последовательность запусков по папкам run_dir. Это нужно, когда сначала был StageRunner, "
            "а потом coordinator (или наоборот)."
        ),
    )
    summary = option_map[selected_run_dir]

    cols = st.columns([1.2, 1.0, 1.0, 1.0])
    with cols[0]:
        st.metric("Статус", summary.status_label)
    with cols[1]:
        if summary.pipeline_mode == "staged":
            st.metric("Rows", int(summary.row_count))
        else:
            st.metric("DONE", int(summary.done_count))
    with cols[2]:
        if summary.pipeline_mode == "staged":
            st.metric("Pipeline", summary.backend)
        else:
            st.metric("ERROR", int(summary.error_count))
    with cols[3]:
        if summary.pipeline_mode == "coordinator":
            st.metric("RUNNING", int(summary.running_count))
        else:
            st.metric("Run dir", summary.run_dir.name)

    st.write(f"**Pipeline:** {summary.backend}")
    st.write(f"**run_dir:** `{summary.run_dir}`")
    if summary.result_path is not None:
        st.write(f"**Артефакт результатов:** `{summary.result_path}`")
    if summary.started_at:
        st.write(f"**Started hint:** `{summary.started_at}`")
    if summary.note:
        st.caption(summary.note)
    if summary.last_error:
        st.warning("Последняя ошибка из артефактов: " + summary.last_error)

    if summary.objective_keys:
        st.write("**Objective stack:** " + ", ".join(str(x) for x in summary.objective_keys))
    if summary.penalty_key:
        hard_gate = f"`{summary.penalty_key}`"
        if summary.penalty_tol is not None:
            hard_gate += f" (tol={float(summary.penalty_tol):g})"
        st.write(f"**Hard gate:** {hard_gate}")
    if summary.objective_contract_path is not None:
        st.caption(f"Objective contract artifact: {summary.objective_contract_path}")

    current_obj = tuple(_current_objective_keys())
    current_penalty_key = str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT).strip()
    current_penalty_tol = st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT)
    contract_diff_bits = []
    if summary.objective_keys and tuple(summary.objective_keys) != current_obj:
        contract_diff_bits.append("objective stack")
    if summary.penalty_key and summary.penalty_key != current_penalty_key:
        contract_diff_bits.append("penalty key")
    try:
        if summary.penalty_tol is not None and float(summary.penalty_tol) != float(current_penalty_tol):
            contract_diff_bits.append("penalty tol")
    except Exception:
        pass
    if contract_diff_bits:
        st.info(
            "Выбранный run собран на другом objective-contract, чем текущие поля UI ("
            + ", ".join(contract_diff_bits)
            + "). Это нормально для честного сравнения исторических запусков; в HF8 coordinator resume/cache уже различает такие контракты по problem_hash."
        )

    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button(
            "Сделать текущей «последней оптимизацией»",
            key=f"opt_make_latest::{summary.run_dir}",
            help="Перепривязать глобальный latest_optimization pointer к выбранному run_dir.",
        ):
            meta = {
                "backend": summary.backend,
                "pipeline_mode": summary.pipeline_mode,
                "status": summary.status,
                "rows": int(summary.row_count),
                "done_count": int(summary.done_count),
                "running_count": int(summary.running_count),
                "error_count": int(summary.error_count),
                "objective_keys": list(summary.objective_keys),
                "penalty_key": summary.penalty_key,
                "penalty_tol": summary.penalty_tol,
                "selected_from": "optimization_history",
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            try:
                run_artifacts.save_last_opt_ptr(summary.run_dir, meta)
                run_artifacts.autoload_to_session(st.session_state)
                st.success("latest_optimization pointer перепривязан к выбранному run_dir.")
                request_rerun(st)
            except Exception as e:
                st.error(f"Не удалось перепривязать latest_optimization: {e}")
    with b2:
        if st.button(
            "Открыть результаты выбранного run",
            key=f"opt_open_results::{summary.run_dir}",
            help="Сначала перепривязать latest_optimization, затем открыть страницу результатов.",
        ):
            meta = {
                "backend": summary.backend,
                "pipeline_mode": summary.pipeline_mode,
                "status": summary.status,
                "objective_keys": list(summary.objective_keys),
                "penalty_key": summary.penalty_key,
                "penalty_tol": summary.penalty_tol,
                "selected_from": "optimization_history",
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            try:
                run_artifacts.save_last_opt_ptr(summary.run_dir, meta)
                run_artifacts.autoload_to_session(st.session_state)
                st.switch_page("pages/20_DistributedOptimization.py")
            except Exception:
                st.info("Откройте страницу 'Результаты оптимизации' в меню слева — pointer уже обновлён.")
    with b3:
        if summary.log_path is not None:
            st.caption(f"Лог: {summary.log_path}")

    if summary.log_path is not None:
        log_text = _tail_file_text(summary.log_path)
        if log_text:
            st.code(log_text[-8000:] if len(log_text) > 8000 else log_text)
        else:
            st.caption("Лог-файл существует, но сейчас пуст. Для staged run это не обязательно означает провал: ориентируйтесь на sp.json / CSV / trial export.")


def _load_json(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        return dict(obj) if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _render_stage_policy_runtime_block(job: DistOptJob) -> None:
    payload = _load_json(job.progress_path)
    if not payload:
        st.caption("StageRunner progress.json ещё не записан — это нормально в первые секунды запуска.")
        return

    stage_name = str(payload.get("stage") or "")
    stage_idx = int(payload.get("idx", 0) or 0)
    staged = summarize_staged_progress(payload, job.run_dir)

    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.metric("Стадия", stage_name or f"stage{stage_idx}")
    with cols[1]:
        st.metric("Stage rows", int(staged.get("stage_rows_current", 0) or 0))
    with cols[2]:
        st.metric("Всего live rows", int(staged.get("total_rows_live", 0) or 0))
    with cols[3]:
        elapsed = staged.get("stage_elapsed_sec")
        st.metric("Время стадии, с", f"{float(elapsed):.1f}" if elapsed is not None else "—")

    policy = summarize_stage_policy_runtime(job.run_dir, stage_idx=stage_idx, stage_name=stage_name)
    if not policy.get("available"):
        return

    st.markdown("**Seed/promotion policy (текущая стадия)**")
    st.caption(
        f"requested={policy.get('requested_mode') or '—'} → effective={policy.get('effective_mode') or '—'}; "
        f"policy={policy.get('policy_name') or '—'}"
    )
    st.caption(str(policy.get("summary_line") or ""))

    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.metric("Target seeds", int(policy.get("target_seed_count", 0) or 0))
    with cols[1]:
        st.metric("Selected", int((policy.get("selected_counts") or {}).get("total", 0) or 0))
    with cols[2]:
        st.metric("Focus budget", int(policy.get("focus_budget", 0) or 0))
    with cols[3]:
        st.metric("Explore budget", int(policy.get("explore_budget", 0) or 0))

    if policy.get("priority_params"):
        st.caption("Priority params: " + ", ".join(str(x) for x in (policy.get("priority_params") or [])[:8]))
    if policy.get("underfilled"):
        st.warning(
            "Seed budget underfilled: "
            + str(policy.get("underfill_message") or policy.get("underfill_reason") or "see audit")
        )
    gate_preview = str(policy.get("gate_reason_preview") or "").strip()
    if gate_preview:
        st.caption("Main gate reasons: " + gate_preview)


# ---------------------------
# UI
# ---------------------------

st.title("Оптимизация")
st.caption(
    "Инженерный раздел: алгоритм, критерии останова, параллелизм/распределёнка и единая "
    "система подхвата результатов (последняя оптимизация). Главная страница держит search-space contract "
    "(параметры/режимы/suite), а запуск/stop/resume/monitoring оптимизации живут здесь."
)

_nav1, _nav2, _nav3 = st.columns(3)
with _nav1:
    if st.button("🏠 Главная: входные данные и suite", width="stretch", key="opt_page_go_home"):
        try:
            st.switch_page("pneumo_solver_ui/pneumo_ui_app.py")
        except Exception:
            st.info("Откройте главную страницу через меню слева.")
with _nav2:
    if st.button("📊 Результаты оптимизации", width="stretch", key="opt_page_go_results"):
        try:
            st.switch_page("pneumo_solver_ui/pages/20_DistributedOptimization.py")
        except Exception:
            st.info("Откройте страницу результатов оптимизации через меню слева.")
with _nav3:
    if st.button("🗄️ База оптимизаций", width="stretch", key="opt_page_go_db"):
        try:
            st.switch_page("pneumo_solver_ui/pages/31_OptDatabase.py")
        except Exception:
            st.info("Откройте страницу базы оптимизаций через меню слева.")

with st.expander("Последняя оптимизация", expanded=True):
    _render_last_opt_summary()

with st.expander("Физический смысл путей запуска", expanded=True):
    _render_physical_workflow_block()

with st.expander("Последовательные запуски в текущем workspace", expanded=True):
    _render_workspace_run_history(_job_from_state())


_MODE_STAGE = "Режим по стадиям (StageRunner) — рекомендуется"
_MODE_COORD = "Distributed coordinator (Dask / Ray / BoTorch)"

with st.expander("Режим запуска и стадийность", expanded=True):
    _launch_mode_options = [_MODE_STAGE, _MODE_COORD]
    _launch_mode_default = _MODE_STAGE if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)) else _MODE_COORD
    _launch_mode_index = _launch_mode_options.index(_launch_mode_default)
    launch_mode = st.radio(
        "Активный путь запуска",
        options=_launch_mode_options,
        index=_launch_mode_index,
        horizontal=False,
        help=(
            "Сейчас работает только один путь запуска. Выберите режим здесь, настройте только его блоки ниже "
            "и нажмите одну кнопку в секции «Запуск оптимизации»."
        ),
    )
    opt_use_staged = launch_mode == _MODE_STAGE
    st.session_state["opt_use_staged"] = bool(opt_use_staged)
    st.session_state["use_staged_opt"] = bool(opt_use_staged)
    st.info("Сейчас активен только один путь запуска. Нажимать нужно одну кнопку в блоке «Запуск оптимизации» ниже.")
    if opt_use_staged:
        st.success(
            "Активен StageRunner: это рекомендованный physics-first путь. Ниже показываются только staged-настройки и одна кнопка «Запустить StageRunner». Быстрый stop/fail на ранних стадиях — штатный признак того, что physical gate сработал рано."
        )
    else:
        st.info(
            "Активен distributed coordinator path. Ниже показываются только настройки Dask/Ray/BoTorch и одна кнопка «Запустить distributed coordinator». Это длинный trade-study путь после того, как search-space и suite уже приведены в порядок."
        )


if not opt_use_staged:
    # 1) Алгоритм / критерии
    with st.expander("Алгоритм и критерии останова", expanded=True):
        st.markdown(
            "Здесь задаются **инженерные параметры оптимизации**: выбор метода порождения кандидатов, "
            "бюджет, seed, лимит параллельных вычислений и критерии по штрафам/ограничениям."
        )
        if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)):
            st.caption(
                "Этот блок нужен для distributed coordinator path. В staged режиме он не пропадает, "
                "но применяется только когда вы выключаете StageRunner."
            )

        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            proposer = st.selectbox(
                "Метод (алгоритм) предложения кандидатов",
                options=["auto", "portfolio", "qnehvi", "random"],
                index=["auto", "portfolio", "qnehvi", "random"].index(str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)) if str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT) in ["auto", "portfolio", "qnehvi", "random"] else 0,
                key="opt_proposer",
                help=(
                    "auto — использовать лучшее доступное (qNEHVI при наличии BoTorch, иначе random).\n"
                    "portfolio — смешивать qNEHVI и random для устойчивости.\n"
                    "qnehvi — BoTorch qNEHVI (требует установленных зависимостей).\n"
                    "random — LHS/случайный поиск."
                ),
            )

        with c2:
            budget = st.number_input(
                "Бюджет (кол-во оценок целевой функции)",
                min_value=1,
                max_value=100000,
                value=int(st.session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT),
                step=10,
                key="opt_budget",
                help="Сколько запусков/оценок выполнить суммарно. Это главный 'стоп' критерий.",
            )

        with c3:
            max_inflight = st.number_input(
                "Макс. параллельных задач",
                min_value=0,
                max_value=4096,
                value=int(st.session_state.get("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT) or DIST_OPT_MAX_INFLIGHT_DEFAULT),
                step=1,
                key="opt_max_inflight",
                help=(
                    "Ограничивает, сколько оценок одновременно может быть 'в полёте'.\n"
                    "0 — автоматически (≈ 2×кол-во воркеров)."
                ),
            )

        c4, c5, c6 = st.columns([2, 2, 2])
        with c4:
            seed = st.number_input(
                "Seed (для воспроизводимости)",
                min_value=0,
                max_value=2**31 - 1,
                value=int(st.session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT),
                step=1,
                key="opt_seed",
                help="Фиксирует генератор случайных чисел. Одинаковый seed → более повторяемые эксперименты.",
            )

        with c5:
            penalty_key = st.text_input(
                "Ключ штрафа/ограничений (penalty_key)",
                value=str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT),
                key="opt_penalty_key",
                help=(
                    "Имя поля в результатах расчёта, которое интерпретируется как штраф (constraint violation). "
                    "0 — полностью допустимо; >0 — нарушение."
                ),
            )

        with c6:
            penalty_tol = st.number_input(
                "Допуск штрафа (penalty_tolerance)",
                min_value=0.0,
                max_value=1e9,
                value=float(st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT) or DIST_OPT_PENALTY_TOL_DEFAULT),
                step=1e-9,
                format="%.3e",
                key="opt_penalty_tol",
                help="Если penalty <= tol — считаем решение допустимым.",
            )

        # Problem hash mode (stable vs legacy)
        _hash_modes = ['stable', 'legacy']
        _hm_val = str(st.session_state.get('settings_opt_problem_hash_mode', DIAGNOSTIC_PROBLEM_HASH_MODE) or DIAGNOSTIC_PROBLEM_HASH_MODE)
        _hm_idx = _hash_modes.index(_hm_val) if _hm_val in _hash_modes else 0
        st.selectbox(
            'Режим идентификатора задачи (problem_hash)',
            options=_hash_modes,
            index=_hm_idx,
            key='settings_opt_problem_hash_mode',
            help=(
                'stable (рекомендуется) — устойчивый hash по содержимому (фикс. часть base + набор optim keys + suite + sha кода).\n'
                'legacy — совместимость со старыми run_id; может зависеть от путей/настроек.'
            ),
        )

        st.divider()

        c7, c8, c9 = st.columns([2, 2, 2])
        with c7:
            st.number_input(
                "q (сколько кандидатов предлагать за шаг)",
                min_value=1,
                max_value=256,
                value=int(st.session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT),
                step=1,
                key="opt_q",
                help="Для qNEHVI/portfolio можно предлагать пачку кандидатов за итерацию.",
            )
        with c8:
            _dev_opts = ["auto", "cpu", "cuda"]
            _dev_val = str(st.session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT) or DIST_OPT_DEVICE_DEFAULT)
            _dev_idx = _dev_opts.index(_dev_val) if _dev_val in _dev_opts else 0
            st.selectbox(
                "Устройство для модели (device)",
                options=_dev_opts,
                index=_dev_idx,
                key="opt_device",
                help="auto — выбрать автоматически. cuda — использовать GPU (если доступно и установлены зависимости).",
            )
        with c9:
            st.text_area(
                "Целевые метрики (objective keys) — по одной в строке",
                value=str(
                    st.session_state.get(
                        "opt_objectives",
                        objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES),
                    )
                ),
                height=92,
                key="opt_objectives",
                help=(
                    "Ключи метрик, которые оптимизируются (multi-objective).\n"
                    "Формат: по одной в строке (или можно разделять запятыми)."
                ),
            )


    # 2) Параллелизм/распределёнка
    with st.expander("Параллелизм и кластер (Dask / Ray)", expanded=True):
        st.markdown(
            "Здесь выбирается **бэкенд распределённых вычислений** и настройки локального/удалённого кластера.\n\n"
            "Ключевой принцип: **UI умеет создавать локальный кластер автоматически** — без ручных команд, "
            "достаточно выбрать *Локальный* режим и нажать *Запустить оптимизацию*."
        )

        backend = st.selectbox(
            "Бэкенд распределённых вычислений",
            options=["Dask", "Ray"],
            index=0 if str(st.session_state.get("opt_backend", "Dask")) == "Dask" else 1,
            key="opt_backend",
            help="Dask удобен для локального параллелизма и простых кластеров; Ray — для акторов и более сложных сценариев.",
        )

        if backend == "Dask":
            mode = st.radio(
                "Режим Dask",
                options=["Локальный кластер (создать автоматически)", "Подключиться к scheduler"],
                index=0 if not str(st.session_state.get("dask_mode", "")).startswith("Подключ") else 1,
                key="dask_mode",
                help=(
                    "Локальный кластер создаётся координатором автоматически через LocalCluster.\n"
                    "Если есть внешний scheduler — укажите адрес и подключитесь к нему."
                ),
            )

            if mode.startswith("Подключ"):
                st.text_input(
                    "Адрес scheduler (например: tcp://127.0.0.1:8786)",
                    value=str(st.session_state.get("dask_scheduler", "") or ""),
                    key="dask_scheduler",
                    help="Адрес планировщика Dask. Если пусто — будет создан локальный кластер.",
                )
            else:
                c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                with c1:
                    st.number_input(
                        "Воркеры",
                        min_value=0,
                        max_value=256,
                        value=int(st.session_state.get("dask_workers", 0) or 0),
                        step=1,
                        key="dask_workers",
                        help="0 — автоматически (Dask выберет разумное значение).",
                    )
                with c2:
                    st.number_input(
                        "Потоки/воркер",
                        min_value=1,
                        max_value=128,
                        value=int(st.session_state.get("dask_threads_per_worker", DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT) or DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT),
                        step=1,
                        key="dask_threads_per_worker",
                        help="Количество потоков на каждый процесс-воркер.",
                    )
                with c3:
                    st.text_input(
                        "Лимит памяти/воркер",
                        value=str(st.session_state.get("dask_memory_limit", "") or ""),
                        key="dask_memory_limit",
                        help="Например: 4GB. Пусто — по умолчанию (auto). '0'/'none' — без лимита.",
                    )
                with c4:
                    st.text_input(
                        "Dashboard address",
                        value=str(st.session_state.get("dask_dashboard_address", DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT) or DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT),
                        key="dask_dashboard_address",
                        help="':0' — выбрать порт автоматически. Пусто — отключить dashboard.",
                    )

            st.caption(
                "Подсказка: LocalCluster поддерживает параметры n_workers / threads_per_worker / memory_limit / dashboard_address "
                "(dashboard_address=None отключает dashboard)."
            )

        else:
            mode = st.radio(
                "Режим Ray",
                options=["Локальный кластер (создать автоматически)", "Подключиться к кластеру"],
                index=0 if not str(st.session_state.get("ray_mode", "")).startswith("Подключ") else 1,
                key="ray_mode",
                help=(
                    "Локальный кластер создаётся автоматически через ray.init() в процессе координатора.\n"
                    "Если есть внешний кластер Ray — укажите адрес подключения."
                ),
            )

            if mode.startswith("Подключ"):
                st.text_input(
                    "Адрес Ray (например: 127.0.0.1:6379 или 'auto')",
                    value=str(st.session_state.get("ray_address", "auto") or "auto"),
                    key="ray_address",
                    help="Адрес кластера Ray. 'auto' — подключиться к запущенному, если возможно.",
                )
            else:
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    st.number_input(
                        "Ограничить CPU (0=авто)",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("ray_local_num_cpus", 0) or 0),
                        step=1,
                        key="ray_local_num_cpus",
                        help="Если задать >0 — Ray в локальном режиме будет считать, что доступно столько CPU.",
                    )
                with c2:
                    st.checkbox(
                        "Включить dashboard (локально)",
                        value=bool(st.session_state.get("ray_local_dashboard", False)),
                        key="ray_local_dashboard",
                        help="Попытка включить dashboard Ray в локальном режиме.",
                    )
                with c3:
                    st.number_input(
                        "Порт dashboard (0=авто)",
                        min_value=0,
                        max_value=65535,
                        value=int(st.session_state.get("ray_local_dashboard_port", 0) or 0),
                        step=1,
                        key="ray_local_dashboard_port",
                        help="Если 0 — Ray выберет порт автоматически.",
                    )


    # 2b) Coordinator advanced / persistence
    with st.expander("Coordinator advanced / persistence", expanded=False):
        st.markdown(
            "Ниже — **реально подключённые** ручки координатора. Они используют тот же session_state, что и основной UI, "
            "и попадают в `dist_opt_coordinator.py` без фейковых CLI-полей."
        )

        c_adv1, c_adv2 = st.columns([1, 1])
        with c_adv1:
            _rt_mode_val = migrated_ray_runtime_env_mode(st.session_state)
            st.selectbox(
                "Ray runtime_env mode",
                options=list(RAY_RUNTIME_ENV_MODES),
                index=list(RAY_RUNTIME_ENV_MODES).index(_rt_mode_val) if _rt_mode_val in RAY_RUNTIME_ENV_MODES else list(RAY_RUNTIME_ENV_MODES).index(DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT),
                key="ray_runtime_env_mode",
                help=(
                    "auto — включать runtime_env только для внешнего Ray-кластера; "
                    "on — принудительно упаковывать working_dir в runtime_env; "
                    "off — не использовать runtime_env."
                ),
            )
            st.text_area(
                "Ray runtime_env JSON merge (optional)",
                value=migrated_ray_runtime_env_json(st.session_state),
                height=120,
                key="ray_runtime_env_json",
                help=(
                    "Опциональный JSON-объект, который будет слит с базовым runtime_env координатора. "
                    "Полезно для env_vars / pip / excludes на кластере."
                ),
            )
            st.text_area(
                "Ray runtime exclude (по одному паттерну в строке)",
                value=str(st.session_state.get("ray_runtime_exclude", "") or ""),
                height=90,
                key="ray_runtime_exclude",
                help="Исключения при упаковке working_dir в Ray runtime_env.",
            )
            st.number_input(
                "Ray evaluators",
                min_value=0,
                max_value=4096,
                value=int(st.session_state.get("ray_num_evaluators", 0) or 0),
                step=1,
                key="ray_num_evaluators",
                help="0 — координатор сам выберет количество evaluator actors.",
            )
            st.number_input(
                "CPU на evaluator",
                min_value=0.25,
                max_value=512.0,
                value=float(st.session_state.get("ray_cpus_per_evaluator", 1.0) or 1.0),
                step=0.25,
                format="%.2f",
                key="ray_cpus_per_evaluator",
                help="Сколько CPU резервировать на один evaluator actor Ray.",
            )
            st.number_input(
                "Ray proposers",
                min_value=0,
                max_value=512,
                value=int(st.session_state.get("ray_num_proposers", 0) or 0),
                step=1,
                key="ray_num_proposers",
                help="0 — auto (попробовать использовать доступные GPU для proposer actors).",
            )
            st.number_input(
                "GPU на proposer",
                min_value=0.0,
                max_value=16.0,
                value=float(st.session_state.get("ray_gpus_per_proposer", 1.0) or 1.0),
                step=0.25,
                format="%.2f",
                key="ray_gpus_per_proposer",
                help="Сколько GPU резервировать на один proposer actor Ray.",
            )

        with c_adv2:
            st.number_input(
                "Буфер кандидатов proposer_buffer",
                min_value=1,
                max_value=8192,
                value=int(st.session_state.get("proposer_buffer", 128) or 128),
                step=1,
                key="proposer_buffer",
                help="Сколько готовых кандидатов держать в буфере координатора.",
            )
            st.text_input(
                "ExperimentDB path / DSN",
                value=str(st.session_state.get("opt_db_path", "") or ""),
                key="opt_db_path",
                help="Путь к sqlite/duckdb файлу или Postgres DSN для ExperimentDB.",
            )
            _db_engine_opts = ["sqlite", "duckdb", "postgres"]
            _db_engine_val = str(st.session_state.get("opt_db_engine", DIST_OPT_DB_ENGINE_DEFAULT) or DIST_OPT_DB_ENGINE_DEFAULT).strip().lower()
            st.selectbox(
                "DB engine",
                options=_db_engine_opts,
                index=_db_engine_opts.index(_db_engine_val) if _db_engine_val in _db_engine_opts else _db_engine_opts.index(DIST_OPT_DB_ENGINE_DEFAULT),
                key="opt_db_engine",
                help="Координатор умеет работать с sqlite, duckdb и postgres backends.",
            )
            st.checkbox(
                "Resume from existing run",
                value=bool(st.session_state.get("opt_resume", False)),
                key="opt_resume",
                help="Повторно открыть последний/указанный run_id для той же задачи и доработать его.",
            )
            st.text_input(
                "Explicit run_id (optional)",
                value=str(st.session_state.get("opt_dist_run_id", "") or ""),
                key="opt_dist_run_id",
                help="Если заполнено вместе с Resume — координатор будет пытаться продолжить именно этот run_id.",
            )
            st.number_input(
                "stale-ttl-sec",
                min_value=0,
                max_value=604800,
                value=int(st.session_state.get("opt_stale_ttl_sec", DIST_OPT_STALE_TTL_SEC_DEFAULT) or DIST_OPT_STALE_TTL_SEC_DEFAULT),
                step=60,
                key="opt_stale_ttl_sec",
                help="Через сколько секунд RUNNING trial можно считать stale и requeue при resume.",
            )
            st.checkbox(
                "Писать hypervolume log",
                value=bool(st.session_state.get("opt_hv_log", DIST_OPT_HV_LOG_DEFAULT)),
                key="opt_hv_log",
                help="Если включено — координатор пишет progress_hv.csv по feasible Pareto-front.",
            )
            st.number_input(
                "export-every",
                min_value=1,
                max_value=100000,
                value=int(st.session_state.get("opt_export_every", DIST_OPT_EXPORT_EVERY_DEFAULT) or DIST_OPT_EXPORT_EVERY_DEFAULT),
                step=1,
                key="opt_export_every",
                help="Как часто (по DONE trials) обновлять CSV export из ExperimentDB.",
            )


    # 2c) BoTorch / qNEHVI advanced
    with st.expander("BoTorch / qNEHVI advanced", expanded=False):
        if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)):
            st.caption(
                "Этот блок относится к distributed coordinator. В StageRunner он не исчезает, но применяется только "
                "к запуску через Dask/Ray/BoTorch path."
            )
        _botorch_status = botorch_runtime_status()
        if _botorch_status.get("ready"):
            st.success(botorch_status_markdown(_botorch_status))
        else:
            st.warning(
                botorch_status_markdown(_botorch_status)
                + ". Для установки зависимостей см. `pneumo_solver_ui/requirements_mobo_botorch.txt`."
            )
        st.caption(
            "qNEHVI включается честно: coordinator сначала проходит warmup, затем проверяет feasible-point gate. "
            "Если done < n_init или feasible < min_feasible, proposer временно откатывается в random/LHS path."
        )

        c_b1, c_b2, c_b3 = st.columns([1, 1, 1])
        with c_b1:
            st.number_input(
                "n-init (warmup before qNEHVI)",
                min_value=0,
                max_value=100000,
                value=int(st.session_state.get("opt_botorch_n_init", DIST_OPT_BOTORCH_N_INIT_DEFAULT) or DIST_OPT_BOTORCH_N_INIT_DEFAULT),
                step=1,
                key="opt_botorch_n_init",
                help="0 — auto threshold (~2×(dim+1), но не меньше 10). До этого qNEHVI не включается.",
            )
            st.number_input(
                "min-feasible",
                min_value=0,
                max_value=100000,
                value=int(st.session_state.get("opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT) or DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
                step=1,
                key="opt_botorch_min_feasible",
                help="Сколько feasible DONE trials нужно накопить перед включением qNEHVI. 0 — gate отключён.",
            )
            st.number_input(
                "num_restarts",
                min_value=1,
                max_value=4096,
                value=int(st.session_state.get("opt_botorch_num_restarts", DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT) or DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT),
                step=1,
                key="opt_botorch_num_restarts",
                help="Число restarts для оптимизации acquisition-функции qNEHVI.",
            )

        with c_b2:
            st.number_input(
                "raw_samples",
                min_value=8,
                max_value=131072,
                value=int(st.session_state.get("opt_botorch_raw_samples", DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT) or DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT),
                step=8,
                key="opt_botorch_raw_samples",
                help="Размер набора raw samples для оптимизации acquisition-функции qNEHVI.",
            )
            st.number_input(
                "maxiter",
                min_value=1,
                max_value=100000,
                value=int(st.session_state.get("opt_botorch_maxiter", DIST_OPT_BOTORCH_MAXITER_DEFAULT) or DIST_OPT_BOTORCH_MAXITER_DEFAULT),
                step=1,
                key="opt_botorch_maxiter",
                help="Максимум итераций внутреннего оптимизатора acquisition-функции.",
            )
            st.number_input(
                "ref_margin",
                min_value=0.0,
                max_value=10.0,
                value=float(st.session_state.get("opt_botorch_ref_margin", DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT) or DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT),
                step=0.01,
                format="%.3f",
                key="opt_botorch_ref_margin",
                help="Запас для reference point при построении qNEHVI / hypervolume geometry.",
            )

        with c_b3:
            st.checkbox(
                "Normalize objectives before GP fit",
                value=bool(st.session_state.get("opt_botorch_normalize_objectives", DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT)),
                key="opt_botorch_normalize_objectives",
                help="Обычно это стоит оставить включённым; отключать только для осознанной диагностики qNEHVI path.",
            )
            st.info(
                "Эти ручки действуют и для локального proposer path, и для Ray proposer actors. "
                "То есть UI и coordinator теперь реально говорят на одном контракте."
            )


if opt_use_staged:
    with st.expander("StageRunner: warm-start, influence и staged seed/promotion", expanded=True):
        st.markdown(
            "Этот блок управляет **стадийным pipeline**: длительность запуска, seeds, warm-start, early-stop и "
            "influence-aware seed/promotion policy. Именно эти ручки определяют поведение `opt_stage_runner_v1.py`."
        )

        c_s0, c_s1, c_s2 = st.columns([1, 1, 1])
        with c_s0:
            st.number_input(
                "Минуты на staged run",
                min_value=0.1,
                max_value=1440.0,
                value=float(st.session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT) or DIAGNOSTIC_OPT_MINUTES_DEFAULT),
                step=1.0,
                key="ui_opt_minutes",
                help="Общий wall-clock budget для StageRunner. Внутри него он сам распределяет время между стадиями.",
            )
        with c_s1:
            st.number_input(
                "Jobs (локальный parallel worker pool)",
                min_value=1,
                max_value=512,
                value=int(st.session_state.get("ui_jobs", _UI_JOBS_DEFAULT) or _UI_JOBS_DEFAULT),
                step=1,
                key="ui_jobs",
                help="Число локальных worker jobs для opt_worker_v3_margins_energy.py внутри StageRunner.",
            )
        with c_s2:
            st.checkbox(
                "Авто-обновлять baseline_best.json",
                value=bool(st.session_state.get("opt_autoupdate_baseline", True)),
                key="opt_autoupdate_baseline",
                help="Если найден кандидат лучше текущего baseline — StageRunner запишет его в workspace/baselines/baseline_best.json.",
            )

        c_s3, c_s4, c_s5, c_s6 = st.columns([1, 1, 1, 1])
        with c_s3:
            st.number_input(
                "Seed кандидатов",
                min_value=0,
                max_value=2_147_483_647,
                value=int(st.session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES) or DIAGNOSTIC_SEED_CANDIDATES),
                step=1,
                key="ui_seed_candidates",
                help="Влияет только на генерацию набора кандидатов в staged optimizer.",
            )
        with c_s4:
            st.number_input(
                "Seed условий",
                min_value=0,
                max_value=2_147_483_647,
                value=int(st.session_state.get("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS) or DIAGNOSTIC_SEED_CONDITIONS),
                step=1,
                key="ui_seed_conditions",
                help="Влияет на стохастические условия в staged tests (если они включены).",
            )
        with c_s5:
            st.number_input(
                "flush_every",
                min_value=1,
                max_value=200,
                value=int(st.session_state.get("ui_flush_every", 20) or 20),
                step=1,
                key="ui_flush_every",
                help="Как часто StageRunner сбрасывает строки результатов в CSV на диск.",
            )
        with c_s6:
            st.number_input(
                "progress_every_sec",
                min_value=0.2,
                max_value=10.0,
                value=float(st.session_state.get("ui_progress_every_sec", 1.0) or 1.0),
                step=0.2,
                key="ui_progress_every_sec",
                help="Как часто StageRunner пишет progress.json.",
            )

        c_s7, c_s8, c_s9 = st.columns([1, 1, 1])
        with c_s7:
            st.selectbox(
                "Warm-start режим",
                options=["surrogate", "archive", "none"],
                index=["surrogate", "archive", "none"].index(str(st.session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE) or DIAGNOSTIC_WARMSTART_MODE)) if str(st.session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE) or DIAGNOSTIC_WARMSTART_MODE) in ["surrogate", "archive", "none"] else 0,
                key="warmstart_mode",
                help="surrogate: прогреть распределение по surrogate; archive: стартовать из истории; none: без warm-start.",
            )
        with c_s8:
            st.number_input(
                "Surrogate samples",
                min_value=500,
                max_value=50000,
                value=int(st.session_state.get("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES) or DIAGNOSTIC_SURROGATE_SAMPLES),
                step=500,
                key="surrogate_samples",
                help="Сколько случайных точек ранжировать в surrogate warm-start.",
            )
        with c_s9:
            st.number_input(
                "Surrogate top-k",
                min_value=8,
                max_value=512,
                value=int(st.session_state.get("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K) or DIAGNOSTIC_SURROGATE_TOP_K),
                step=8,
                key="surrogate_top_k",
                help="Размер элиты для инициализации распределения staged search.",
            )

        c_s10, c_s11, c_s12 = st.columns([1, 1, 1])
        with c_s10:
            st.number_input(
                "Early-stop штраф (stage1)",
                min_value=0.0,
                max_value=1e9,
                value=float(st.session_state.get("stop_pen_stage1", 25.0) or 25.0),
                step=1.0,
                key="stop_pen_stage1",
                help="Если накопленный штраф > порога — StageRunner прерывает оставшиеся тесты для кандидата на длинной стадии.",
            )
        with c_s11:
            st.number_input(
                "Early-stop штраф (stage2)",
                min_value=0.0,
                max_value=1e9,
                value=float(st.session_state.get("stop_pen_stage2", 15.0) or 15.0),
                step=1.0,
                key="stop_pen_stage2",
                help="Более строгий порог для финальной стадии.",
            )
        with c_s12:
            st.checkbox(
                "Сортировать тесты по стоимости",
                value=bool(st.session_state.get("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)),
                key="sort_tests_by_cost",
                help="Дешёвые тесты идут первыми, чтобы early-stop быстрее отбрасывал плохих кандидатов.",
            )

        c_s13, c_s14, c_s15 = st.columns([1, 1, 1])
        with c_s13:
            influence_eps_rel = st.number_input(
                "System Influence eps_rel",
                min_value=1e-6,
                max_value=0.25,
                value=float(st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL) or DIAGNOSTIC_INFLUENCE_EPS_REL),
                step=1e-3,
                format="%.6g",
                key="influence_eps_rel",
                help="Явный относительный шаг возмущения для system_influence_report_v1 в StageRunner.",
            )
        with c_s14:
            adaptive_influence_eps = st.checkbox(
                "Adaptive epsilon для System Influence",
                value=bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)),
                key="adaptive_influence_eps",
                help=(
                    "System Influence прогоняет сетку eps_rel и выбирает более устойчивый шаг. "
                    f"Базовая сетка: {influence_eps_grid_text(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID)}."
                ),
            )
        with c_s15:
            st.selectbox(
                "Seed/promotion policy",
                options=["influence_weighted", "static"],
                index=["influence_weighted", "static"].index(str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE)) if str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE) in ["influence_weighted", "static"] else 0,
                key="stage_policy_mode",
                help=(
                    "influence_weighted — позже стадии сильнее фокусируются на stage-relevant параметрах; "
                    "static — историческое поведение без influence-aware promotion."
                ),
            )

        st.caption("Stage-specific seed/promotion profile: " + stage_seed_policy_summary_text())
        if adaptive_influence_eps:
            st.caption(
                "Stage-aware adaptive epsilon: "
                + stage_aware_influence_profiles_text(
                    requested_eps_rel=float(influence_eps_rel),
                    base_grid=DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
                )
            )


# 3) Запуск
with st.expander("Запуск оптимизации", expanded=True):
    if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)):
        st.markdown(
            "Будет запущен **opt_stage_runner_v1.py**. Он ведёт staged run, пишет `sp.json`, stage CSV и "
            "live seed/promotion artifacts. Во время выполнения UI показывает хвост лога, live stage rows и текущую stage policy."
        )
    else:
        st.markdown(
            "Будет запущен **tools/dist_opt_coordinator.py**. Это distributed coordinator path для Dask/Ray/BoTorch. "
            "Во время выполнения UI показывает хвост лога и done-progress."
        )

    job = _job_from_state()

    # If there's a job, show status & controls
    if job is not None:
        rc = job.proc.poll()
        if rc is None:
            st.info(
                f"Оптимизация выполняется… (PID={job.proc.pid}, pipeline={job.pipeline_mode}, backend={job.backend}, run_dir={job.run_dir.name})"
            )
            if _soft_stop_requested(job):
                st.warning(
                    "Запрошена мягкая остановка через STOP_OPTIMIZATION.txt. "
                    "StageRunner должен корректно завершить текущий шаг и сохранить CSV/progress."
                )

            log_text = _tail_file_text(job.log_path)
            if job.pipeline_mode == "staged":
                _render_stage_policy_runtime_block(job)
            else:
                done = _parse_done_from_log(log_text)
                if done is not None and job.budget > 0:
                    st.progress(min(1.0, max(0.0, done / float(job.budget))))
                    st.caption(f"Выполнено: {done} из {job.budget}")

            st.code(log_text[-8000:] if len(log_text) > 8000 else log_text)

            if job.stop_file is not None:
                c_stop_soft, c_stop_hard, c_refresh, c_space = st.columns([1, 1, 1, 3])
                with c_stop_soft:
                    if st.button(
                        "Стоп (мягко)",
                        type="secondary",
                        help="Создаёт STOP-файл. StageRunner сам корректно завершится и сохранит CSV/прогресс.",
                    ):
                        if _write_soft_stop_file(job.stop_file):
                            st.warning("Запрошена мягкая остановка. Лог обновится через пару секунд.")
                            request_rerun(st)
                        else:
                            st.error("Не удалось записать STOP-файл.")
                with c_stop_hard:
                    if st.button(
                        "Стоп (жёстко)",
                        type="secondary",
                        help="Создаёт STOP-файл и принудительно завершает процесс. Используйте только если мягкая остановка не срабатывает.",
                    ):
                        if not _write_soft_stop_file(job.stop_file):
                            st.warning("STOP-файл записать не удалось; продолжаю жёсткую остановку процесса.")
                        _terminate_process(job.proc)
                        st.warning("Отправлен жёсткий сигнал остановки. Лог обновится через пару секунд.")
                        request_rerun(st)
                with c_refresh:
                    if st.button("Обновить", help="Перечитать лог"):
                        request_rerun(st)
            else:
                c_stop, c_refresh, c_space = st.columns([1, 1, 3])
                with c_stop:
                    if st.button("Остановить (жёстко)", type="secondary", help="Попытаться остановить текущую оптимизацию"):
                        try:
                            _terminate_process(job.proc)
                            st.warning("Отправлен сигнал остановки. Лог обновится через пару секунд.")
                            request_rerun(st)
                        except Exception as e:
                            st.error(f"Не удалось остановить: {e}")
                with c_refresh:
                    if st.button("Обновить", help="Перечитать лог"):
                        request_rerun(st)

            auto_refresh = st.checkbox(
                "Авто‑обновлять страницу (каждые ~2 секунды)",
                value=bool(st.session_state.get("__opt_autorefresh_enabled", True)),
                key="__opt_autorefresh_enabled",
                help="Если включено — UI будет сам обновляться, пока оптимизация активна.",
            )
            if auto_refresh:
                # Простая и надёжная реализация без внешних зависимостей.
                time.sleep(2.0)
                request_rerun(st)

        else:
            if rc == 0 and _soft_stop_requested(job):
                st.warning(f"Оптимизация остановлена по STOP-файлу (код={rc}).")
            elif rc == 0:
                st.success(f"Оптимизация завершена успешно (код={rc}).")
            else:
                st.error(f"Оптимизация завершилась с ошибкой (код={rc}).")

            # Save pointer to last optimization only when the run produced honest usable artifacts.
            meta = {
                "backend": job.backend,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "run_dir": str(job.run_dir),
            }
            summary = summarize_optimization_run(job.run_dir)
            if summary is not None:
                meta.update({
                    "pipeline_mode": summary.pipeline_mode,
                    "status": summary.status,
                    "rows": int(summary.row_count),
                    "done_count": int(summary.done_count),
                    "running_count": int(summary.running_count),
                    "error_count": int(summary.error_count),
                    "objective_keys": list(summary.objective_keys),
                    "penalty_key": summary.penalty_key,
                    "penalty_tol": summary.penalty_tol,
                })
            try:
                if summary is not None and summary.status in {"done", "partial"}:
                    run_artifacts.save_last_opt_ptr(job.run_dir, meta)
                    # Обновляем session_state сразу, без перезапуска приложения.
                    run_artifacts.autoload_to_session(st.session_state)
                elif summary is not None and summary.status == "error":
                    st.warning("Этот run завершился без usable optimization artifacts — latest_optimization pointer автоматически не переключаю.")
            except Exception as e:
                st.warning(f"Не удалось сохранить указатель на последнюю оптимизацию: {e}")

            if st.button("Очистить статус запуска", help="Скрыть завершённую задачу и вернуться к настройкам"):
                _clear_job()
                request_rerun(st)

    # Start new job if not running
    if job is None or (job.proc.poll() is not None):
        st.subheader("Новый запуск")
        launch_button_label = "Запустить StageRunner" if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)) else "Запустить distributed coordinator"
        st.markdown(
            "**Что нажимать:** выберите режим выше, настройте только видимые для него блоки и затем нажмите "
            f"**{launch_button_label}**. Другой путь запуска сейчас не активен."
        )
        st.caption(
            "Нормальный инженерный сценарий: сначала StageRunner как быстрый physical gate, затем distributed coordinator как длинный trade study. "
            "Эти run dirs не считаются параллельными и сохраняются отдельно в журнале последовательных запусков выше."
        )

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button(launch_button_label, type="primary"):
                app_root = _app_root()
                run_dir = _new_run_dir("staged" if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)) else "coordinator")
                plan = _build_cmd(run_dir)
                log_path = run_dir / ("stage_runner.log" if plan.pipeline_mode == "staged" else "coordinator.log")

                # Launch
                # Ensure deterministic problem_hash behavior
                env = os.environ.copy()
                env['PNEUMO_OPT_PROBLEM_HASH_MODE'] = str(st.session_state.get('settings_opt_problem_hash_mode', 'stable') or 'stable')
                try:
                    with log_path.open("wb") as lf:
                        proc = subprocess.Popen(
                            plan.cmd,
                            stdout=lf,
                            stderr=subprocess.STDOUT,
                            cwd=str(app_root),
                            env=env,
                        )
                    new_job = DistOptJob(
                        proc=proc,
                        run_dir=run_dir,
                        log_path=log_path,
                        started_ts=time.time(),
                        budget=int(plan.budget),
                        backend=plan.label,
                        pipeline_mode=plan.pipeline_mode,
                        progress_path=plan.progress_path,
                        stop_file=plan.stop_file,
                    )
                    _save_job(new_job)
                    st.success("Запуск создан. Лог и прогресс появятся через пару секунд.")
                    request_rerun(st)
                except Exception as e:
                    st.error(f"Не удалось запустить оптимизацию: {e}")

        with c2:
            cmd_preview = _build_cmd(Path("<RUN_DIR>")).cmd
            st.download_button(
                "Скачать шаблон команды",
                data=(" ".join(cmd_preview) + "\n"),
                file_name="dist_opt_command.txt",
                help="На случай, если нужно повторить запуск из консоли.",
            )

        with c3:
            if bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)):
                st.caption(
                    "Техническая заметка: StageRunner запускается через console `python.exe`, пишет короткие runtime paths в workspace/opt_runs "
                    "и сохраняет `sp.json` + stage artifacts для live UI."
                )
            else:
                st.caption(
                    "Техническая заметка: coordinator создаёт локальный кластер автоматически (если выбран локальный режим) — "
                    "Dask через LocalCluster, Ray через ray.init()."
                )


st.divider()

with st.expander("Справка: что именно запускается", expanded=False):
    st.markdown(
        "Страница умеет запускать **оба** пути оптимизации:\n\n"
        "- **`pneumo_solver_ui/opt_stage_runner_v1.py`** — staged pipeline: warm-start, stage-aware seed/promotion policy, "
        "adaptive influence epsilon, `sp.json` и stage artifacts на диске;\n"
        "- **`pneumo_solver_ui/tools/dist_opt_coordinator.py`** — distributed Dask/Ray/BoTorch coordinator path с ExperimentDB, resume и qNEHVI.\n\n"
        "Оба запуска идут через console Python и короткие runtime paths в `workspace/opt_runs`, чтобы не возвращать старые Windows path/runtime регрессии. "
        "После завершения UI сохраняет указатель на папку как *последнюю оптимизацию* (run_artifacts), чтобы результаты автоматически подхватывались везде."
    )


# best‑effort autosave (важно: без него UI‑настройки оптимизации могут теряться при перезагрузке)
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled

    autosave_if_enabled(st)
except Exception:
    pass
