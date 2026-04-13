"""Оптимизация (инженерный раздел).

Цели раздела:
- все настройки оптимизации доступны всегда (без "экспертных режимов"), но разложены по смысловым блокам;
- поддержка двух бэкендов распределённых вычислений: Dask и Ray;
- UI умеет *сам* запускать локальный кластер (без ручных команд) и запускать оптимизацию через координатор;
- результаты "последней оптимизации" автоматически подхватываются всеми страницами через run_artifacts.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import streamlit as st

from pneumo_solver_ui.streamlit_compat import request_rerun
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIAGNOSTIC_USE_STAGED_OPT,
    DIST_OPT_PENALTY_KEY_DEFAULT,
    DIST_OPT_PENALTY_TOL_DEFAULT,
    diagnostics_jobs_default,
    objectives_text,
)
from pneumo_solver_ui.optimization_job_session_runtime import (
    clear_job_from_session,
    load_job_from_session,
    parse_done_from_log,
    soft_stop_requested,
    tail_file_text,
    terminate_optimization_process,
    write_soft_stop_file,
)
from pneumo_solver_ui.optimization_launch_plan_runtime import (
    build_optimization_launch_plan,
    current_problem_hash_for_launch,
    problem_hash_mode_for_launch,
    ui_root_from_page_path,
    workspace_dir_for_ui_root,
)
from pneumo_solver_ui.optimization_coordinator_algorithm_ui import (
    render_coordinator_algorithm_controls,
)
from pneumo_solver_ui.optimization_coordinator_cluster_ui import (
    render_coordinator_cluster_controls,
)
from pneumo_solver_ui.optimization_coordinator_persistence_ui import (
    render_coordinator_persistence_controls,
)
from pneumo_solver_ui.optimization_botorch_advanced_ui import (
    render_botorch_advanced_controls,
)
from pneumo_solver_ui.optimization_stage_runner_config_ui import (
    render_stage_runner_configuration_controls,
)
from pneumo_solver_ui.optimization_job_start_ui import (
    start_coordinator_handoff_job_with_feedback,
    start_optimization_job_with_feedback,
)
from pneumo_solver_ui.optimization_active_runtime_summary import (
    build_active_runtime_summary,
)
from pneumo_solver_ui.optimization_page_readonly_ui import (
    render_last_optimization_overview_block,
    render_physical_workflow_block,
)
from pneumo_solver_ui.optimization_workspace_history_ui import (
    render_workspace_run_history_block,
)
from pneumo_solver_ui.optimization_launch_mode_ui import (
    render_optimization_launch_mode_block,
)
from pneumo_solver_ui.optimization_launch_session_ui import (
    render_optimization_launch_session_block,
)
from pneumo_solver_ui.optimization_page_shell_ui import (
    render_optimization_help_expander,
    render_optimization_navigation_row,
    render_optimization_page_header,
    render_optimization_readonly_expanders,
)
from pneumo_solver_ui.optimization_last_pointer_snapshot import (
    load_last_optimization_pointer_snapshot,
)
from pneumo_solver_ui.optimization_stage_runtime_block import (
    render_stage_policy_runtime_block,
)
from pneumo_solver_ui.optimization_ready_preset import (
    seed_optimization_ready_session_state,
)


bootstrap(st)
seed_optimization_ready_session_state(st.session_state, cpu_count=int(os.cpu_count() or 4), platform_name=sys.platform)

_UI_JOBS_DEFAULT = int(diagnostics_jobs_default(os.cpu_count(), platform_name=sys.platform))

st.set_page_config(page_title="Пневмо‑UI | Оптимизация", layout="wide")

_UI_ROOT = ui_root_from_page_path(Path(__file__))
_WORKSPACE_DIR = workspace_dir_for_ui_root(_UI_ROOT)
_CURRENT_PROBLEM_HASH_MODE = problem_hash_mode_for_launch(st.session_state)
try:
    _CURRENT_PROBLEM_HASH = current_problem_hash_for_launch(
        st.session_state,
        ui_root=_UI_ROOT,
        workspace_dir=_WORKSPACE_DIR,
        problem_hash_mode=_CURRENT_PROBLEM_HASH_MODE,
    )
except Exception:
    _CURRENT_PROBLEM_HASH = ""
_ACTIVE_JOB = load_job_from_session(st.session_state)
_ACTIVE_LAUNCH_CONTEXT = dict(st.session_state.get("__opt_active_launch_context") or {})
_ACTIVE_RUNTIME_SUMMARY = build_active_runtime_summary(
    _ACTIVE_JOB,
    tail_file_text_fn=tail_file_text,
    parse_done_from_log_fn=parse_done_from_log,
    active_launch_context=_ACTIVE_LAUNCH_CONTEXT,
)

# ---------------------------
# UI
# ---------------------------

render_optimization_page_header(
    st,
    title="Оптимизация",
    caption=(
    "Инженерный раздел: алгоритм, критерии останова, параллелизм/распределёнка и единая "
    "система подхвата результатов (последняя оптимизация). Главная страница держит search-space contract "
    "(параметры/режимы/suite), а запуск/stop/resume/monitoring оптимизации живут здесь."
    ),
)

render_optimization_navigation_row(
    st,
    home_label="🏠 Главная: входные данные и suite",
    home_key="opt_page_go_home",
    home_action=lambda: st.switch_page("pneumo_solver_ui/pneumo_ui_app.py"),
    home_fallback="Откройте главную страницу через меню слева.",
    results_label="📊 Результаты оптимизации",
    results_key="opt_page_go_results",
    results_action=lambda: st.switch_page("pneumo_solver_ui/pages/20_DistributedOptimization.py"),
    results_fallback="Откройте страницу результатов оптимизации через меню слева.",
    db_label="🗄️ База оптимизаций",
    db_key="opt_page_go_db",
    db_action=lambda: st.switch_page("pneumo_solver_ui/pages/31_OptDatabase.py"),
    db_fallback="Откройте страницу базы оптимизаций через меню слева.",
)

render_optimization_readonly_expanders(
    st,
    last_label="Последняя оптимизация",
    render_last=lambda: render_last_optimization_overview_block(
        st,
        snapshot=load_last_optimization_pointer_snapshot(),
        results_page="pages/20_DistributedOptimization.py",
        current_problem_hash=_CURRENT_PROBLEM_HASH,
        current_problem_hash_mode=_CURRENT_PROBLEM_HASH_MODE,
        active_run_dir=getattr(_ACTIVE_JOB, "run_dir", None),
        active_launch_context=_ACTIVE_LAUNCH_CONTEXT,
        active_runtime_summary=_ACTIVE_RUNTIME_SUMMARY,
    ),
    physical_label="Физический смысл путей запуска",
    render_physical=lambda: render_physical_workflow_block(
        st,
        session_state=st.session_state,
        default_objectives=DEFAULT_OPTIMIZATION_OBJECTIVES,
        penalty_key_default=DIST_OPT_PENALTY_KEY_DEFAULT,
        objectives_text_fn=objectives_text,
        rerun_fn=request_rerun,
    ),
    history_label="Последовательные запуски в текущем workspace",
    render_history=lambda: render_workspace_run_history_block(
        st,
        workspace_dir=_WORKSPACE_DIR,
        active_job=_ACTIVE_JOB,
        session_state=st.session_state,
        current_problem_hash=_CURRENT_PROBLEM_HASH,
        default_objectives=DEFAULT_OPTIMIZATION_OBJECTIVES,
        objectives_text_fn=objectives_text,
        penalty_key_default=DIST_OPT_PENALTY_KEY_DEFAULT,
        current_penalty_tol=st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT),
        load_log_text=tail_file_text,
        rerun_fn=request_rerun,
        active_runtime_summary=_ACTIVE_RUNTIME_SUMMARY,
        start_handoff_fn=lambda source_run_dir: start_coordinator_handoff_job_with_feedback(
            st,
            session_state=st.session_state,
            source_run_dir=Path(source_run_dir),
            ui_root=_UI_ROOT,
            python_executable=sys.executable,
            problem_hash_mode=str(
                st.session_state.get("settings_opt_problem_hash_mode", "stable") or "stable"
            ),
            rerun_fn=request_rerun,
        ),
        current_problem_hash_mode=_CURRENT_PROBLEM_HASH_MODE,
    ),
)


_MODE_STAGE = "Режим по стадиям (StageRunner) — рекомендуется"
_MODE_COORD = "Distributed coordinator (Dask / Ray / BoTorch)"

opt_use_staged = render_optimization_launch_mode_block(
    st,
    expander_label="Режим запуска и стадийность",
    mode_stage_label=_MODE_STAGE,
    mode_coord_label=_MODE_COORD,
    current_use_staged=bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)),
    radio_label="Активный путь запуска",
    radio_help=(
        "Сейчас работает только один путь запуска. Выберите режим здесь, настройте только его блоки ниже "
        "и нажмите одну кнопку в секции «Запуск оптимизации»."
    ),
    single_path_message="Сейчас активен только один путь запуска. Нажимать нужно одну кнопку в блоке «Запуск оптимизации» ниже.",
    staged_message=(
        "Активен StageRunner: это рекомендованный быстрый путь по физике. Ниже показываются только "
        "staged-настройки и одна кнопка «Запустить StageRunner». Быстрый stop/fail на ранних стадиях — "
        "штатный признак того, что физический фильтр сработал рано."
    ),
    coordinator_message=(
        "Активен distributed coordinator. Ниже показываются только настройки Dask/Ray/BoTorch и одна "
        "кнопка «Запустить distributed coordinator». Это длинный путь перебора вариантов после того, как search-space "
        "и suite уже приведены в порядок."
    ),
)
st.session_state["opt_use_staged"] = bool(opt_use_staged)
st.session_state["use_staged_opt"] = bool(opt_use_staged)


if not opt_use_staged:
    # 1) Алгоритм / критерии
    render_coordinator_algorithm_controls(
        st,
        show_staged_caption=bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)),
    )

    # 2) Параллелизм/распределёнка
    render_coordinator_cluster_controls(st)


    # 2b) Coordinator advanced / persistence
    render_coordinator_persistence_controls(st)


    # 2c) BoTorch / qNEHVI advanced
    render_botorch_advanced_controls(
        st,
        show_staged_caption=bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)),
    )


if opt_use_staged:
    render_stage_runner_configuration_controls(st, ui_jobs_default=_UI_JOBS_DEFAULT)


render_optimization_launch_session_block(
    st,
    job=_ACTIVE_JOB,
    is_staged=bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)),
    current_problem_hash=_CURRENT_PROBLEM_HASH,
    current_problem_hash_mode=_CURRENT_PROBLEM_HASH_MODE,
    active_runtime_summary=_ACTIVE_RUNTIME_SUMMARY,
    tail_file_text_fn=tail_file_text,
    soft_stop_requested_fn=soft_stop_requested,
    parse_done_from_log_fn=parse_done_from_log,
    render_stage_runtime_fn=lambda job: render_stage_policy_runtime_block(st, job),
    write_soft_stop_file_fn=write_soft_stop_file,
    terminate_process_fn=terminate_optimization_process,
    rerun_fn=request_rerun,
    sleep_fn=time.sleep,
    clear_job_fn=lambda: clear_job_from_session(st.session_state),
    launch_job_fn=lambda: start_optimization_job_with_feedback(
        st,
        session_state=st.session_state,
        ui_root=_UI_ROOT,
        ui_jobs_default=_UI_JOBS_DEFAULT,
        python_executable=sys.executable,
        problem_hash_mode=str(
            st.session_state.get("settings_opt_problem_hash_mode", "stable") or "stable"
        ),
        rerun_fn=request_rerun,
    ),
    start_handoff_job_fn=lambda source_run_dir: start_coordinator_handoff_job_with_feedback(
        st,
        session_state=st.session_state,
        source_run_dir=Path(source_run_dir),
        ui_root=_UI_ROOT,
        python_executable=sys.executable,
        problem_hash_mode=str(
            st.session_state.get("settings_opt_problem_hash_mode", "stable") or "stable"
        ),
        rerun_fn=request_rerun,
    ),
    build_cmd_preview_text_fn=lambda: " ".join(
        build_optimization_launch_plan(
            st.session_state,
            run_dir=Path("<RUN_DIR>"),
            ui_root=_UI_ROOT,
            python_executable=sys.executable,
            ui_jobs_default=_UI_JOBS_DEFAULT,
        ).cmd
    ) + "\n",
)


st.divider()

render_optimization_help_expander(
    st,
    label="Справка: что именно запускается",
    markdown_text=(
        "Страница умеет запускать **оба** пути оптимизации:\n\n"
        "- **`pneumo_solver_ui/opt_stage_runner_v1.py`** — staged pipeline: warm-start, stage-aware seed/promotion policy, "
        "adaptive influence epsilon, `sp.json` и stage artifacts на диске;\n"
        "- **`pneumo_solver_ui/tools/dist_opt_coordinator.py`** — distributed Dask/Ray/BoTorch coordinator path с ExperimentDB, resume и qNEHVI.\n\n"
        "Оба запуска идут через console Python и короткие runtime paths в `workspace/opt_runs`, чтобы не возвращать старые Windows path/runtime регрессии. "
        "После завершения UI сохраняет указатель на папку как *последнюю оптимизацию* (run_artifacts), чтобы результаты автоматически подхватывались везде."
    ),
    expanded=False,
)


# best‑effort autosave (важно: без него UI‑настройки оптимизации могут теряться при перезагрузке)
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled

    autosave_if_enabled(st)
except Exception:
    pass
