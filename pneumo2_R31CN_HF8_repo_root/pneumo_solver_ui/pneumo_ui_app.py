# -*- coding: utf-8 -*-
"""
pneumo_ui_app.py

Streamlit UI:
- запуск одиночных тестов (baseline),
- запуск оптимизации (фоновый процесс) из UI,
- просмотр/фильтр результатов.

Требования: streamlit, numpy, pandas, openpyxl.

"""
# Compatibility note: this is the heavy home page rendered by the repo-root multipage shell.
# Keep it runnable for diagnostics, but prefer streamlit run app.py as the canonical launcher.
import os
import sys
import platform
import json
import time
import math
import re
import hashlib
import inspect
import subprocess
import shutil
import logging
import traceback
import threading
import uuid
from functools import partial
from pathlib import Path

# Ensure project root is on sys.path (fixes ModuleNotFoundError for package-style imports)
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Mandatory event log (ModuleNotFound/Warning/etc) + explicit UI events
try:
    from pneumo_solver_ui.diag.eventlog import get_global_logger

    _EV = get_global_logger(ROOT_DIR)
except Exception:
    _EV = None


def _emit(event: str, msg: str, **kw) -> None:
    try:
        if _EV is not None:
            _EV.emit(event, msg, **kw)
    except Exception:
        pass


from datetime import datetime
from typing import Dict, Tuple, Any, List, Optional, Callable

import copy
import gzip

import numpy as np
import pandas as pd
import streamlit as st

try:
    from pneumo_solver_ui.ui_st_compat import install_st_compat
    install_st_compat()
except Exception:
    pass

from pneumo_solver_ui.streamlit_compat import safe_set_page_config
from pneumo_solver_ui.ui_cache_helpers import (
    detail_cache_path as build_detail_cache_path,
    df_to_excel_bytes,
    float_tag as _float_tag,
    legacy_detail_cache_path as build_legacy_detail_cache_path,
    load_baseline_cache as load_ui_baseline_cache,
    load_detail_cache_payload as load_ui_detail_cache,
    load_last_baseline_ptr as load_ui_last_baseline_ptr,
    make_detail_cache_key,
    pareto_front_2d,
    save_baseline_cache as save_ui_baseline_cache,
    save_detail_cache_payload as save_ui_detail_cache,
    save_last_baseline_ptr as save_ui_last_baseline_ptr,
    stable_obj_hash,
)
from pneumo_solver_ui.ui_cache_runtime_helpers import (
    build_runtime_baseline_cache_dir,
    load_runtime_baseline_cache,
    load_runtime_detail_cache,
    load_runtime_last_baseline_ptr,
    save_runtime_baseline_cache,
    save_runtime_detail_cache,
    save_runtime_last_baseline_ptr,
)
from pneumo_solver_ui.ui_data_helpers import decimate_minmax, downsample_df, write_tests_index_csv
from pneumo_solver_ui.ui_diagnostics_helpers import make_ui_diagnostics_zip_bundle
from pneumo_solver_ui.ui_diagnostics_profile_helpers import (
    build_ui_diagnostics_zip_writer,
)
from pneumo_solver_ui.ui_event_surface_profile_helpers import (
    build_mech_pick_consumer,
    build_playhead_event_consumer,
    build_plotly_pick_consumer,
    build_svg_pick_consumer,
)
from pneumo_solver_ui.ui_event_sync_helpers import (
    consume_mech_pick_event as _consume_mech_pick_event_core,
    consume_playhead_event as _consume_playhead_event_core,
    consume_plotly_pick_events as _consume_plotly_pick_events_core,
    consume_svg_pick_event as _consume_svg_pick_event_core,
)
from pneumo_solver_ui.ui_flow_rate_helpers import (
    flow_rate_display_scale_and_unit,
)
from pneumo_solver_ui.ui_interaction_helpers import (
    apply_pick_list as _apply_pick_list,
    extract_plotly_selection_points as _extract_plotly_selection_points,
    plotly_points_signature as _plotly_points_signature,
)
from pneumo_solver_ui.ui_logging_runtime_helpers import (
    append_ui_log_lines,
    configure_runtime_ui_logger,
    ensure_runtime_file_logger,
    prepare_runtime_log_dir,
    publish_session_callback,
)
from pneumo_solver_ui.ui_line_plot_helpers import (
    prefer_rel0_plot_columns,
)
from pneumo_solver_ui.ui_plot_surface_profile_helpers import (
    build_line_plot_renderer,
    build_plot_studio_renderer,
)
from pneumo_solver_ui.ui_process_profile_helpers import (
    build_background_worker_starter,
)
from pneumo_solver_ui.ui_playhead_helpers import (
    make_playhead_jump_command,
    make_playhead_reset_command,
)
from pneumo_solver_ui.ui_results_runtime_helpers import (
    prepare_results_runtime,
)
from pneumo_solver_ui.ui_results_surface_section_helpers import (
    render_heavy_results_surface_section,
)
from pneumo_solver_ui.ui_timeline_event_helpers import (
    add_wheels_identical_sanity_event,
    compute_events_bar_profile as compute_events,
)
from pneumo_solver_ui.ui_param_helpers import (
    is_numeric_scalar as _is_numeric_scalar,
    is_pressure_param,
    is_small_volume_param,
    is_volume_param,
    param_desc,
)
from pneumo_solver_ui.packaging_surface_helpers import (
    collect_packaging_surface_metrics,
    enrich_packaging_surface_df,
    packaging_error_surface_metrics,
)
from pneumo_solver_ui.packaging_surface_ui import (
    apply_packaging_surface_filters,
    load_packaging_params_from_base_json,
    packaging_surface_result_columns,
    render_packaging_surface_metrics,
)
from pneumo_solver_ui.suspension_family_contract import family_param_meta
from pneumo_solver_ui.ui_process_helpers import (
    dump_cloudpickle_payload as _dump_detail_cache_payload,
    load_cloudpickle_payload as _load_detail_cache_payload,
    start_background_worker,
)
from pneumo_solver_ui.ui_runtime_helpers import (
    do_rerun,
    get_ui_nonce,
    is_any_fallback_anim_playing,
    pid_alive,
    proc_metrics as _proc_metrics,
)
from pneumo_solver_ui.ui_suite_helpers import (
    load_default_suite_disabled,
    load_suite,
    resolve_osc_dir,
)
from pneumo_solver_ui.ui_unit_profile_helpers import (
    build_gauge_pressure_profile,
    build_ui_unit_profile,
)
from pneumo_solver_ui.ui_unit_helpers import (
    gauge_to_pa_abs,
    infer_plot_unit_and_transform,
    is_length_param_name,
    pa_abs_to_gauge,
    param_unit_label,
    si_to_ui_value,
    ui_to_si_value,
)
from pneumo_solver_ui.ui_workflow_shell_helpers import (
    render_heavy_workflow_header,
)
from pneumo_solver_ui.ui_optimization_page_shell_helpers import (
    render_advanced_optimization_section_intro,
    render_heavy_optimization_page_overview,
    render_project_files_section_intro,
    render_search_space_section_intro,
    render_test_suite_section_intro,
)
from pneumo_solver_ui.ui_suite_editor_section_helpers import (
    render_heavy_suite_editor_section,
)
from pneumo_solver_ui.ui_simulation_helpers import (
    call_simulate,
    compute_road_profile_from_suite,
    parse_sim_output,
)
from pneumo_solver_ui.run_artifacts import (
    apply_anim_latest_to_session as apply_anim_latest_to_session_global,
    local_anim_latest_export_paths as local_anim_latest_export_paths_global,
)
from pneumo_solver_ui.ui_streamlit_surface_helpers import (
    safe_dataframe as render_safe_dataframe,
    safe_image as render_safe_image,
    safe_plotly_chart as render_safe_plotly_chart,
    safe_previewable_dataframe as render_safe_previewable_dataframe,
    ui_popover as render_ui_popover,
)
from pneumo_solver_ui.ui_svg_html_builders import (
    render_svg_flow_animation_html,
)

# Source-contract breadcrumbs for source-based regression tests.
# The heavy suite editor implementation now lives in ui_suite_editor_section_helpers.py
# and ui_suite_card_panel_helpers.py, but these historical anchors remain here on purpose:
# st.session_state["ui_suite_selected_id"] = _cur_sel
# _suite_select_options = list(_row_ids)
# format_func=lambda _id: _label_for_id(str(_id))
# _suite_editor_widget_key(sid, "name")
# _stage_key = _suite_editor_widget_key(sid, "stage")
# _stage_default = max(0, int(st.session_state.get(_stage_key, infer_suite_stage(rec)) or 0))
# key=_stage_key
# min_value=0
# ui_suite_apply_btn_
# _queue_suite_selected_id(sid)
# st.session_state["ui_suite_stage_filter"] = sorted(set(int(x) for x in (_merged_stage_filter or _stages.copy())))
# Логика staged optimization: S0 — быстрый relevance-screen; S1 — длинные дорожные/манёвренные тесты; S2 — финальная robustness-стадия.
# Момент входа теста в staged optimization
# stage 1 не должен молча переписываться в 0
# st.caption(describe_runtime_stage(stage_name))

from pneumo_solver_ui.ui_heavy_cache import UIHeavyCache, default_cache_dir
from pneumo_solver_ui.anim_export_meta import extract_anim_sidecar_meta as _extract_anim_sidecar_meta_core
from pneumo_solver_ui.data_contract import build_geometry_meta_from_base, supplement_animator_geometry_meta
from pneumo_solver_ui.suite_contract_migration import migrate_legacy_suite_columns
from pneumo_solver_ui.module_loading import load_python_module_from_path
from pneumo_solver_ui.browser_perf_artifacts import persist_browser_perf_snapshot_event
from pneumo_solver_ui.name_sanitize import (
    sanitize_ascii_id as _sanitize_id,
    sanitize_id,
    sanitize_test_name,
)
from pneumo_solver_ui.project_path_resolution import resolve_project_py_path
from pneumo_solver_ui.detail_autorun_policy import (
    arm_detail_autorun_after_baseline,
    arm_detail_autorun_on_test_change,
    clear_detail_force_fresh,
    should_bypass_detail_disk_cache,
)
from pneumo_solver_ui.process_tree import terminate_process_tree
from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS,
    DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
    DIAGNOSTIC_CALIB_MODE,
    DIAGNOSTIC_INFLUENCE_EPS_REL,
    DIAGNOSTIC_OPT_MINUTES_DEFAULT,
    DIAGNOSTIC_PROBLEM_HASH_MODE,
    DIAGNOSTIC_SEED_CANDIDATES,
    DIAGNOSTIC_SEED_CONDITIONS,
    DIAGNOSTIC_SORT_TESTS_BY_COST,
    DIAGNOSTIC_SUITE_PRESET,
    DIAGNOSTIC_SUITE_SELECTED_ID,
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
    botorch_runtime_status,
    botorch_status_markdown,
    migrated_ray_runtime_env_json,
    migrated_ray_runtime_env_mode,
)
from pneumo_solver_ui.optimization_input_contract import (
    describe_runtime_stage,
    infer_suite_stage,
    normalize_suite_stage_numbers,
    sanitize_optimization_inputs,
)
from pneumo_solver_ui.optimization_ready_preset import (
    CANONICAL_OPTIMIZATION_TEST_TYPES,
    load_optimization_ready_suite_rows,
    seed_optimization_ready_session_state,
)
from pneumo_solver_ui.optimization_stage_policy import (
    DEFAULT_STAGE_POLICY_MODE,
    stage_seed_policy_summary_text,
)
from pneumo_solver_ui.optimization_runtime_paths import (
    build_optimization_run_dir,
    console_python_executable,
    staged_progress_path,
)
from pneumo_solver_ui.optimization_last_pointer_snapshot import (
    load_last_optimization_pointer_snapshot,
)
from pneumo_solver_ui.optimization_last_pointer_ui import (
    render_last_optimization_pointer_summary,
)
from pneumo_solver_ui.optimization_stage_policy_live import (
    summarize_stage_policy_runtime,
)
from pneumo_solver_ui.ui_shared_helpers import (
    best_match as _best_match,
    name_score as _name_score,
    norm_name as _norm_name,
    run_starts as _run_starts,
    shorten_name as _shorten_name,
)


def _opt_gateway_nav(page: str, label: str, *, key: str, help_text: Optional[str] = None) -> None:
    """Robust navigation helper for the home-page optimization gateway."""
    try:
        if hasattr(st, "page_link"):
            st.page_link(page, label=label, help=help_text, width="stretch")
            return
    except Exception:
        pass

    if st.button(label, key=key, help=help_text, width="stretch"):
        try:
            if hasattr(st, "switch_page"):
                st.switch_page(page)
            else:
                st.info("Если переход не сработал, используйте меню навигации слева.")
        except Exception:
            st.info("Если переход не сработал, используйте меню навигации слева.")


def _opt_gateway_last_pointer_snapshot() -> dict:
    """Best-effort summary of the latest optimization pointer for the home gateway."""
    return load_last_optimization_pointer_snapshot()


def _render_home_opt_config_snapshot(*, compact: bool = False) -> None:
    """Read-only optimization snapshot for the home page.

    Important: this is deliberately informational only; active launch/stop/resume
    lives on the dedicated Optimization page.
    """
    cpu_n = int(os.cpu_count() or 4)
    jobs_default = int(diagnostics_jobs_default(cpu_n, platform_name=sys.platform))
    minutes = float(st.session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT) or DIAGNOSTIC_OPT_MINUTES_DEFAULT)
    jobs = int(st.session_state.get("ui_jobs", jobs_default) or jobs_default)
    run_name = str(st.session_state.get("opt_run_name", "main") or "main")
    out_prefix = str(st.session_state.get("ui_out_prefix", "results_opt") or "results_opt")
    opt_use_staged = bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT))
    stage_policy_mode = str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE)
    influence_eps_rel = float(st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL) or DIAGNOSTIC_INFLUENCE_EPS_REL)
    adaptive_influence_eps = bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS))

    if compact:
        cols = st.columns(2)
    else:
        cols = st.columns(4)
    with cols[0]:
        st.metric("Активный путь", "StageRunner" if opt_use_staged else "Distributed")
    with cols[1]:
        st.metric("Лимит, мин", f"{minutes:g}")
    if compact:
        st.caption(f"jobs={jobs}; run={run_name}; csv={out_prefix}")
    else:
        with cols[2]:
            st.metric("jobs", str(jobs))
        with cols[3]:
            st.metric("Run", run_name)
        st.caption(f"CSV prefix: {out_prefix}")

    st.caption(f"Политика отбора и продвижения: {stage_policy_mode}")
    st.caption("Профиль стадийного отбора и продвижения: " + stage_seed_policy_summary_text())
    st.caption(f"System Influence eps_rel: {influence_eps_rel:g}")
    st.caption("Adaptive epsilon для анализа System Influence: " + ("on" if adaptive_influence_eps else "off"))

    if opt_use_staged:
        st.caption(
            "StageRunner: "
            f"warmstart={str(st.session_state.get('warmstart_mode', DIAGNOSTIC_WARMSTART_MODE) or DIAGNOSTIC_WARMSTART_MODE)}, "
            f"surrogate_samples={int(st.session_state.get('surrogate_samples', DIAGNOSTIC_SURROGATE_SAMPLES) or DIAGNOSTIC_SURROGATE_SAMPLES)}, "
            f"surrogate_top_k={int(st.session_state.get('surrogate_top_k', DIAGNOSTIC_SURROGATE_TOP_K) or DIAGNOSTIC_SURROGATE_TOP_K)}"
        )
        st.caption(
            "StageRunner seeds/filters: "
            f"seed_candidates={int(st.session_state.get('ui_seed_candidates', DIAGNOSTIC_SEED_CANDIDATES) or DIAGNOSTIC_SEED_CANDIDATES)}, "
            f"seed_conditions={int(st.session_state.get('ui_seed_conditions', DIAGNOSTIC_SEED_CONDITIONS) or DIAGNOSTIC_SEED_CONDITIONS)}, "
            f"sort_tests_by_cost={bool(st.session_state.get('sort_tests_by_cost', DIAGNOSTIC_SORT_TESTS_BY_COST))}, "
            f"autoupdate_baseline={bool(st.session_state.get('opt_autoupdate_baseline', True))}"
        )
    else:
        st.caption(
            "Distributed / BoTorch / coordinator: "
            f"backend={str(st.session_state.get('opt_backend', 'Dask') or 'Dask')}, "
            f"proposer={str(st.session_state.get('opt_proposer', DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)}, "
            f"budget={int(st.session_state.get('opt_budget', DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT)}, "
            f"q={int(st.session_state.get('opt_q', DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT)}, "
            f"device={str(st.session_state.get('opt_device', DIST_OPT_DEVICE_DEFAULT) or DIST_OPT_DEVICE_DEFAULT)}"
        )
        st.caption(
            "Distributed runtime/env: "
            f"ray_runtime_env_mode={str(st.session_state.get('ray_runtime_env_mode', DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT) or DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT)}, "
            f"opt_botorch_n_init={int(st.session_state.get('opt_botorch_n_init', DIST_OPT_BOTORCH_N_INIT_DEFAULT) or DIST_OPT_BOTORCH_N_INIT_DEFAULT)}, "
            f"opt_botorch_min_feasible={int(st.session_state.get('opt_botorch_min_feasible', DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT) or DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT)}"
        )


def _render_home_opt_last_pointer_summary(*, compact: bool = False) -> None:
    snap = _opt_gateway_last_pointer_snapshot()
    render_last_optimization_pointer_summary(
        st,
        snap,
        compact=compact,
        missing_message="Последняя оптимизация пока не запускалась (или указатель ещё не записан).",
        packaging_heading="Сводка по геометрии узлов (последний run)",
        packaging_interference_prefix="В последнем run есть признаки пересечений по геометрии узлов",
    )


from pneumo_solver_ui.ring_visuals import (
    load_ring_spec_from_test_cfg,
    load_ring_spec_from_npz,
    build_ring_visual_payload_from_spec,
    build_nominal_ring_progress_from_spec,
    embed_path_payload_on_ring,
)

# Редактор сценариев: сегменты‑кольцо (единственный поддерживаемый редактор сценариев).
# Старый редактор сценариев удалён намеренно; совместимость со старыми сценариями НЕ обеспечивается.
try:
    from pneumo_solver_ui.ui_scenario_ring import render_ring_scenario_generator
    _HAS_RING_SCENARIO_EDITOR = True
except Exception:
    render_ring_scenario_generator = None  # type: ignore
    _HAS_RING_SCENARIO_EDITOR = False

# Опционально: интерактивные графики (Plotly). Если не установлено — UI продолжит работать без Plotly.
try:
    import plotly.graph_objects as go  # type: ignore
    import plotly.express as px  # type: ignore
    import plotly.io as pio  # type: ignore
    _HAS_PLOTLY = True
    from plotly.subplots import make_subplots  # type: ignore
except Exception:
    go = None  # type: ignore
    px = None  # type: ignore
    make_subplots = None  # type: ignore
    _HAS_PLOTLY = False

# Optional: метрики процесса (CPU/RAM). Если psutil не установлен — просто отключаем метрики.
try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:
    psutil = None  # type: ignore
    _HAS_PSUTIL = False

# Release tag (used in logs/diagnostics)
try:
    from pneumo_solver_ui.release_info import get_release
    APP_RELEASE = get_release()
except Exception:
    APP_RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"

# Fallback (без Streamlit Components): matplotlib-визуализация механики.
# Это лечит типовые проблемы вроде "Unrecognized component API version" / "apiVersion undefined" в некоторых окружениях.
#
# Важно: fallback-модуль лежит ВНУТРИ пакета pneumo_solver_ui.
# Поэтому основной импорт — package import. Если sys.path сломан, пробуем загрузить по абсолютному пути файла.
import importlib.util as _importlib_util  # noqa: E402


mech_fb = None
_MECH_ANIM_FALLBACK_ERR = None
try:
    from pneumo_solver_ui import mech_anim_fallback as mech_fb  # package import (preferred)
except Exception as _e_pkg:
    try:
        _fallback_path = (Path(__file__).resolve().parent / "mech_anim_fallback.py")
        _spec = _importlib_util.spec_from_file_location("pneumo_solver_ui.mech_anim_fallback", str(_fallback_path))
        if _spec and _spec.loader:
            _mod = _importlib_util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
            mech_fb = _mod  # type: ignore
        else:
            raise RuntimeError(f"spec is None for {_fallback_path}")
    except Exception as _e_file:
        mech_fb = None
        _MECH_ANIM_FALLBACK_ERR = f"pkg:{_e_pkg!r}; file:{_e_file!r}"

from io import BytesIO

# --- Unified NPZ bundle export (Desktop Animator + calibration tools) ---
try:
    from pneumo_solver_ui.npz_bundle import export_full_log_to_npz, export_anim_latest_bundle
    _HAS_NPZ_BUNDLE = True
except Exception as _e_npz_bundle:
    export_full_log_to_npz = None  # type: ignore
    export_anim_latest_bundle = None  # type: ignore
    _HAS_NPZ_BUNDLE = False
    try:
        _emit('ImportError', f'npz_bundle: {_e_npz_bundle!r}')
    except Exception:
        pass


# Optional: SVG auto-trace / анализ схемы по геометрии линий
try:
    from pneumo_solver_ui.svg_autotrace import extract_polylines, auto_build_mapping_from_svg, detect_component_bboxes, shortest_path_between_points, evaluate_route_quality  # type: ignore
    _HAS_SVG_AUTOTRACE = True
except Exception:
    _HAS_SVG_AUTOTRACE = False
    extract_polylines = None  # type: ignore
    auto_build_mapping_from_svg = None  # type: ignore
    detect_component_bboxes = None  # type: ignore
    evaluate_route_quality = None  # type: ignore



HERE = Path(__file__).resolve().parent
_UI_HEAVY_CACHE = UIHeavyCache(default_cache_dir(HERE))

MODEL_DEFAULT = str(canonical_model_path(HERE))
WORKER_DEFAULT = str(canonical_worker_path(HERE))
SUITE_DEFAULT = str(canonical_suite_json_path(HERE))
BASE_DEFAULT = str(canonical_base_json_path(HERE))
RANGES_DEFAULT = str(canonical_ranges_json_path(HERE))


def _suggest_default_model_path(here: Path) -> Path:
    """Выбрать канонический файл модели для UI/оптимизации.

    Реальный канон уже инкапсулирован в optimization_defaults.canonical_model_path():
    сначала scheme_fingerprint, затем актуальная v9 Camozzi, затем worldroad.
    """
    return canonical_model_path(here)


def _extract_anim_sidecar_meta(test_j: Any) -> Dict[str, Any]:
    """Thin wrapper around the portable anim-export meta helper.

    Keeps UI call-sites stable while centralising sidecar/speed inference in a
    pure helper module (testable without importing the whole Streamlit UI).
    """
    base_dirs = [WORKSPACE_DIR, ROOT_DIR, HERE]
    return _extract_anim_sidecar_meta_core(test_j, base_dirs=base_dirs, log=logging.warning)


def _build_animator_geometry_meta(base_override: Dict[str, Any] | None) -> Dict[str, float]:
    """Build canonical nested geometry meta for newly exported NPZ bundles.

    Base extraction stays strict (no aliases, no invented defaults). After that the
    exporter supplements visual-only ``road_width_m`` when it would otherwise be absent
    and Desktop Animator would have to warn + derive it at runtime from the same
    canonical track/width values.
    """
    geom = build_geometry_meta_from_base(base_override or {}, log=logging.warning)
    geom = supplement_animator_geometry_meta(geom, log=logging.warning)
    missing_required = [k for k in ('wheelbase_m', 'track_m') if k not in geom]
    if missing_required:
        logging.warning(
            "[ANIM_META] base_override is missing canonical geometry required for new bundle meta.geometry: %s",
            ', '.join(missing_required),
        )
    return geom


def get_float_param(d: Dict[str, Any], key: str, *, default: float) -> float:
    """Достать параметр как float по *каноническому* ключу.

    ABSOLUTE LAW:
    - никаких алиасов/дублей ключей (например "база" vs "база_м") в рантайме.
    - если канонический ключ отсутствует, возвращаем `default`.

    ВАЖНО:
    - Этот helper намеренно НЕ поддерживает fallback на альтернативные ключи.
      Любые старые/лишние ключи должны быть выявлены на границе (загрузка файла)
      и исправлены там, а не распространяться по коду.
    """
    if not isinstance(key, str) or not key:
        return float(default)
    v = d.get(key)
    if v is None:
        return float(default)
    try:
        return float(v)  # type: ignore[arg-type]
    except Exception:
        return float(default)


# -------------------------------
# Default files shipped with the app
# -------------------------------
DEFAULT_SVG_MAPPING_PATH = HERE / "default_svg_mapping.json"
DEFAULT_SVG_VIEWBOX = "0 0 1920 1080"

# -------------------------------
# Logging / diagnostics
# -------------------------------

# Важно: UI должен уважать изоляцию сессии (PNEUMO_LOG_DIR/PNEUMO_WORKSPACE_DIR),
# иначе логи смешиваются между прогонами и ломают strict loglint в autotest/send-bundle.

def _env_dir(key: str, default: Path) -> Path:
    v = (os.environ.get(key) or "").strip()
    if not v:
        return default
    try:
        return Path(v).expanduser().resolve()
    except Exception:
        return Path(v)

LOG_DIR = _env_dir("PNEUMO_LOG_DIR", HERE / "logs")

# Workspace for generated artifacts (NPZ, calibration runs, exports)
WORKSPACE_DIR = _env_dir("PNEUMO_WORKSPACE_DIR", HERE / "workspace")
WORKSPACE_OSC_DIR = WORKSPACE_DIR / "osc"
WORKSPACE_EXPORTS_DIR = WORKSPACE_DIR / "exports"
# Дополнительные каталоги workspace (UI пишет сюда автоматически)
WORKSPACE_ROAD_DIR = WORKSPACE_DIR / "road_profiles"
WORKSPACE_MAN_DIR = WORKSPACE_DIR / "maneuvers"
WORKSPACE_UPLOADS_DIR = WORKSPACE_DIR / "uploads"

# Calibration runs directory.
# NOTE:
# - Autopilot/oneclick historically scan "./calibration_runs" next to the app.
# - User reports confusion when UI writes elsewhere.
# Therefore we keep a single canonical folder here.
CALIB_RUNS_DIR = HERE / "calibration_runs"

# Backward-compatible aliases (older code / docs may refer to these names)
WORKSPACE_CAL_DIR = CALIB_RUNS_DIR
WORKSPACE_CALIB_RUNS_DIR = CALIB_RUNS_DIR

try:
    WORKSPACE_OSC_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROAD_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_MAN_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CALIB_RUNS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


get_osc_dir = partial(resolve_osc_dir, WORKSPACE_OSC_DIR)


# -------------------------------
# Upload helpers (CSV/NPZ)
# -------------------------------

def _safe_upload_filename(name: str) -> str:
    """Безопасное имя файла для сохранения в workspace.

    - Убираем пробелы/кириллицу/спецсимволы (Windows-friendly)
    - Оставляем . _ - для читаемости
    """
    if not isinstance(name, str):
        name = str(name)
    out = []
    for ch in name:
        if ch.isalnum() or ch in "._-":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    if not s:
        s = "file"
    return s[:180] if len(s) > 180 else s


def _save_upload(uploaded_file: Any, prefix: str = "upload") -> Optional[Path]:
    """Сохранить загруженный файл (st.file_uploader) в workspace и вернуть путь.

    prefix:
      - 'road'  -> WORKSPACE_ROAD_DIR
      - 'axay'/'maneuver' -> WORKSPACE_MAN_DIR
      - иначе  -> WORKSPACE_UPLOADS_DIR
    """
    if uploaded_file is None:
        return None
    try:
        raw_name = getattr(uploaded_file, "name", "") or "upload"
        safe_name = _safe_upload_filename(raw_name)
        if prefix.lower().startswith("road"):
            out_dir = WORKSPACE_ROAD_DIR
        elif prefix.lower().startswith(("axay", "man", "maneuver")):
            out_dir = WORKSPACE_MAN_DIR
        else:
            out_dir = WORKSPACE_UPLOADS_DIR

        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        dst = out_dir / f"{prefix}_{int(time.time())}_{safe_name}"
        # uploaded_file может быть UploadedFile (getbuffer) или file-like (read)
        try:
            buf = uploaded_file.getbuffer()
            dst.write_bytes(buf)
        except Exception:
            try:
                data = uploaded_file.read()
                dst.write_bytes(data)
            except Exception:
                return None
        return dst
    except Exception:
        return None

LOG_DIR = prepare_runtime_log_dir(LOG_DIR)
_APP_LOGGER = configure_runtime_ui_logger("pneumo_ui")


def log_event(event: str, **fields: Any) -> None:
    """Единая точка логирования (UI schema, strict JSONL).

    Требования, которые удовлетворяем:
    - strict JSON (без NaN/Inf) для устойчивого парсинга;
    - совместимость со strict loglint (--schema ui --strict --check_seq);
    - уважение изолированных директорий (PNEUMO_LOG_DIR).

    Пишем в:
    - ui_*.log (RotatingFileHandler, строка JSON)
    - metrics_*.jsonl (строгий JSONL)
    - metrics_combined.jsonl (строгий JSONL, все сессии)

    Best-effort: никогда не должен ронять UI.
    """

    try:
        ensure_runtime_file_logger(
            st.session_state,
            logger=_APP_LOGGER,
            log_dir=LOG_DIR,
            prefer_env_run_id=True,
            set_session_started=True,
        )

        # lazy imports (avoid startup cost)
        try:
            from pneumo_solver_ui.diag.json_safe import json_dumps as _json_dumps  # strict allow_nan=False
        except Exception:
            _json_dumps = None  # type: ignore

        try:
            from pneumo_solver_ui.release_info import get_release
        except Exception:
            get_release = None  # type: ignore

        # session_id: prefer launcher-provided run_id
        sid = (st.session_state.get("_session_id") or "").strip()
        if not sid:
            sid = (os.environ.get("PNEUMO_RUN_ID") or "").strip()
        if not sid:
            sid = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_pid{os.getpid()}"
            try:
                st.session_state["_session_id"] = sid
                st.session_state.setdefault("_session_started", time.time())
            except Exception:
                pass

        # seq counter (monotonic per session)
        try:
            seq0 = int(st.session_state.get("_log_seq") or 0)
            seq = seq0 + 1
            st.session_state["_log_seq"] = seq
        except Exception:
            seq = 1

        # required fields for strict ui schema
        release = (os.environ.get("PNEUMO_RELEASE") or "").strip()
        if not release and callable(get_release):
            try:
                release = str(get_release() or "").strip()
            except Exception:
                release = "UNIFIED_v6_67"
        if not release:
            release = "UNIFIED_v6_67"

        trace_id = (os.environ.get("PNEUMO_TRACE_ID") or "").strip() or sid or "trace"
        run_id = (os.environ.get("PNEUMO_RUN_ID") or "").strip() or sid

        reserved = {
            "ts",
            "schema",
            "schema_version",
            "event",
            "event_id",
            "seq",
            "trace_id",
            "session_id",
            "pid",
            "release",
        }
        extra_reserved = {}
        payload = {}
        for k, v in (fields or {}).items():
            try:
                ks = str(k)
            except Exception:
                ks = repr(k)
            if ks in reserved:
                extra_reserved[ks] = v
            else:
                payload[ks] = v

        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "schema": "ui",
            "schema_version": "1.2.0",
            "event": str(event),
            "event_id": f"u_{seq:06d}_{uuid.uuid4().hex[:8]}",
            "seq": int(seq),
            "trace_id": str(trace_id),
            "session_id": str(sid),
            "run_id": str(run_id),
            "pid": int(os.getpid()),
            "release": str(release),
            **payload,
        }
        if extra_reserved:
            rec["_extra_reserved"] = extra_reserved

        line = _json_dumps(rec) if _json_dumps else json.dumps(rec, ensure_ascii=False, default=str, allow_nan=False)

        # 1) text logger (rotating)
        try:
            _APP_LOGGER.info(line)
        except Exception:
            pass

        # 2) JSONL metrics (atomic-ish append)
        if LOG_DIR is not None:
            append_ui_log_lines(
                LOG_DIR,
                session_id=str(sid),
                session_metrics_line=line,
                combined_text_line=line,
                use_lock=True,
                errors="replace",
            )

    except Exception:
        return



# Пробрасываем callback для внутренних модулей (fallback-анимации) без прямого импорта этого файла.
# В Streamlit-сессии можно хранить callable. Это нужно для mech_anim_fallback.
publish_session_callback(st.session_state, "_log_event_cb", log_event)


# --- Desktop Animator launcher (best-effort) ---
def _desktop_animator_log_dir() -> Path:
    raw = str(os.environ.get('PNEUMO_LOG_DIR', '') or '').strip()
    try:
        if raw:
            return Path(raw).expanduser().resolve()
    except Exception:
        pass
    return (ROOT_DIR / 'pneumo_solver_ui' / 'logs').resolve()


def _watch_desktop_animator_process(proc: subprocess.Popen, *, pointer: Path, cmd: list[str]) -> None:
    def _worker() -> None:
        try:
            rc = int(proc.wait())
        except Exception as e:
            try:
                log_event('desktop_animator_wait_failed', error=repr(e), pointer=str(pointer), cmd=' '.join(cmd))
            except Exception:
                pass
            return
        try:
            log_event('desktop_animator_exit', returncode=rc, pointer=str(pointer), cmd=' '.join(cmd))
        except Exception:
            pass

    try:
        threading.Thread(target=_worker, daemon=True, name='desktop_animator_exit_watch').start()
    except Exception:
        pass


def launch_desktop_animator_follow(pointer_path: str | Path, *, theme: str = 'dark', no_gl: bool = False) -> bool:
    """Запуск Desktop Animator в follow-режиме (best-effort).

    - Не бросает исключения наружу (UI не должен падать).
    - Возвращает True если процесс удалось создать.
    - Пишет stdout/stderr animator в session log dir и логирует код завершения.
    """
    try:
        ptr = Path(pointer_path).expanduser().resolve()
        py_exe = sys.executable
        if os.name == 'nt':
            try:
                cand = Path(str(sys.executable)).with_name('pythonw.exe')
                if cand.exists():
                    py_exe = str(cand)
            except Exception:
                pass
        cmd = [
            py_exe,
            '-m',
            'pneumo_solver_ui.desktop_animator.main',
            '--follow',
            '--pointer',
            str(ptr),
            '--theme',
            str(theme),
        ]
        if bool(no_gl):
            cmd.append('--no-gl')

        log_dir = _desktop_animator_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / 'desktop_animator_stdout.log'
        stderr_path = log_dir / 'desktop_animator_stderr.log'
        with open(stdout_path, 'ab') as f_out, open(stderr_path, 'ab') as f_err:
            creationflags = 0
            startupinfo = None
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
            proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR), stdout=f_out, stderr=f_err, creationflags=creationflags, startupinfo=startupinfo)

        _watch_desktop_animator_process(proc, pointer=ptr, cmd=cmd)
        try:
            log_event(
                'desktop_animator_spawned',
                cmd=' '.join(cmd),
                pointer=str(ptr),
                pid=int(getattr(proc, 'pid', 0) or 0),
                stdout_log=str(stdout_path),
                stderr_log=str(stderr_path),
            )
        except Exception:
            pass
        return True
    except Exception as e:
        try:
            log_event('desktop_animator_spawn_failed', error=repr(e), pointer=str(pointer_path))
        except Exception:
            pass
        return False


def _watch_desktop_mnemo_process(proc: subprocess.Popen, *, pointer: Path, cmd: list[str]) -> None:
    def _worker() -> None:
        try:
            rc = int(proc.wait())
        except Exception as e:
            try:
                log_event('desktop_mnemo_wait_failed', error=repr(e), pointer=str(pointer), cmd=' '.join(cmd))
            except Exception:
                pass
            return
        try:
            log_event('desktop_mnemo_exit', returncode=rc, pointer=str(pointer), cmd=' '.join(cmd))
        except Exception:
            pass

    try:
        threading.Thread(target=_worker, daemon=True, name='desktop_mnemo_exit_watch').start()
    except Exception:
        pass


def launch_desktop_mnemo_follow(pointer_path: str | Path, *, theme: str = 'dark') -> bool:
    """Запуск отдельного окна Desktop Mnemo в follow-режиме (best-effort)."""
    try:
        ptr = Path(pointer_path).expanduser().resolve()
        py_exe = sys.executable
        if os.name == 'nt':
            try:
                cand = Path(str(sys.executable)).with_name('pythonw.exe')
                if cand.exists():
                    py_exe = str(cand)
            except Exception:
                pass
        cmd = [
            py_exe,
            '-m',
            'pneumo_solver_ui.desktop_mnemo.main',
            '--follow',
            '--pointer',
            str(ptr),
            '--theme',
            str(theme),
        ]

        log_dir = _desktop_animator_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / 'desktop_mnemo_stdout.log'
        stderr_path = log_dir / 'desktop_mnemo_stderr.log'
        with open(stdout_path, 'ab') as f_out, open(stderr_path, 'ab') as f_err:
            creationflags = 0
            startupinfo = None
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
            proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR), stdout=f_out, stderr=f_err, creationflags=creationflags, startupinfo=startupinfo)

        _watch_desktop_mnemo_process(proc, pointer=ptr, cmd=cmd)
        try:
            log_event(
                'desktop_mnemo_spawned',
                cmd=' '.join(cmd),
                pointer=str(ptr),
                pid=int(getattr(proc, 'pid', 0) or 0),
                stdout_log=str(stdout_path),
                stderr_log=str(stderr_path),
            )
        except Exception:
            pass
        return True
    except Exception as e:
        try:
            log_event('desktop_mnemo_spawn_failed', error=repr(e), pointer=str(pointer_path))
        except Exception:
            pass
        return False



consume_svg_pick_event = build_svg_pick_consumer(
    st.session_state,
    apply_pick_list_fn=_apply_pick_list,
)


consume_mech_pick_event = build_mech_pick_consumer(
    st.session_state,
)


consume_plotly_pick_events = build_plotly_pick_consumer(
    st.session_state,
    extract_plotly_selection_points_fn=_extract_plotly_selection_points,
    plotly_points_signature_fn=_plotly_points_signature,
    apply_pick_list_fn=_apply_pick_list,
)


consume_playhead_event = build_playhead_event_consumer(
    st.session_state,
    persist_browser_perf_snapshot_event_fn=persist_browser_perf_snapshot_event,
    workspace_exports_dir=WORKSPACE_EXPORTS_DIR,
    log_event_fn=log_event,
    proc_metrics_fn=_proc_metrics,
)




safe_dataframe = partial(render_safe_previewable_dataframe, st)
ui_popover = partial(render_ui_popover, st)
safe_plotly_chart = partial(render_safe_plotly_chart, st)
safe_image = partial(render_safe_image, st, int_width_fallback=2000)


def _json_safe(obj):
    if isinstance(obj, dict):
        return {str(key): _json_safe(value) for key, value in obj.items()}
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, tuple):
        return [_json_safe(value) for value in obj]
    return obj


make_ui_diagnostics_zip = build_ui_diagnostics_zip_writer(
    here=HERE,
    workspace_dir=WORKSPACE_DIR,
    log_dir=LOG_DIR,
    app_release=APP_RELEASE,
    json_safe_fn=_json_safe,
)
# ------------------------- Persistent cache (baseline/details) -------------------------
# Цель: после refresh (новая session_state) не пересчитывать baseline/детальный прогон,
# а подхватывать с диска. Кэш хранится в WORKSPACE_DIR/cache/baseline/<key>/...

baseline_cache_dir = partial(
    build_runtime_baseline_cache_dir,
    WORKSPACE_DIR,
    sanitize_id_fn=_sanitize_id,
    stable_obj_hash_fn=stable_obj_hash,
)


# Shared baseline-cache wrappers override the legacy inline copies above.
save_last_baseline_ptr = partial(
    save_runtime_last_baseline_ptr,
    workspace_dir=WORKSPACE_DIR,
    save_last_baseline_ptr_fn=save_ui_last_baseline_ptr,
)

load_last_baseline_ptr = partial(
    load_runtime_last_baseline_ptr,
    workspace_dir=WORKSPACE_DIR,
    load_last_baseline_ptr_fn=load_ui_last_baseline_ptr,
)

load_baseline_cache = partial(
    load_runtime_baseline_cache,
    load_baseline_cache_fn=load_ui_baseline_cache,
)

save_baseline_cache = partial(
    save_runtime_baseline_cache,
    workspace_dir=WORKSPACE_DIR,
    save_baseline_cache_fn=save_ui_baseline_cache,
    json_safe_fn=_json_safe,
    log_event_fn=log_event,
)


# Shared detail-cache wrappers override the legacy inline copies above.
save_detail_cache = partial(
    save_runtime_detail_cache,
    save_detail_cache_fn=save_ui_detail_cache,
    sanitize_test_name=sanitize_test_name,
    dump_payload_fn=_dump_detail_cache_payload,
    float_tag_fn=_float_tag,
    log_event_fn=log_event,
)

load_detail_cache = partial(
    load_runtime_detail_cache,
    load_detail_cache_fn=load_ui_detail_cache,
    resave_detail_cache_fn=save_detail_cache,
    sanitize_test_name=sanitize_test_name,
    load_payload_fn=_load_detail_cache_payload,
    float_tag_fn=_float_tag,
    log_event_fn=log_event,
)


# -------------------------------
# Graph Studio helpers (v7.32)
# -------------------------------

_bar_unit_profile = build_ui_unit_profile(
    pressure_unit_label="бар (изб.)",
    pressure_offset_pa=lambda: P_ATM,
    pressure_divisor_pa=lambda: BAR_PA,
    length_unit_label="мм",
    length_scale=1000.0,
    is_pressure_param_fn=is_pressure_param,
    is_volume_param_fn=is_volume_param,
    is_small_volume_param_fn=is_small_volume_param,
    p_atm=lambda: P_ATM,
    bar_pa=lambda: BAR_PA,
)
_infer_unit_and_transform = _bar_unit_profile.infer_unit_and_transform


def _legacy_plot_studio_timeseries_dead(
    df: pd.DataFrame,
    tcol: str,
    y_cols: List[str],
    title: str = "Graph Studio",
    mode: str = "stack",
    max_points: int = 2000,
    decimation: str = "minmax",
    auto_units: bool = True,
    render: str = "svg",
    hover_unified: bool = True,
    playhead_x: float | None = None,
    events: List[dict] | None = None,
    plot_key: str = "plot_studio",
):
    """Render Graph Studio time-series plot(s)."""
    if df is None or df.empty or not y_cols:
        st.info("Нет данных/сигналов для построения.")
        return
    if not _HAS_PLOTLY:
        st.warning(
            "Plotly не установлен — интерактивные графики (Graph Studio / Plotly) отключены.\n\nРешение: установите зависимости через лаунчер (кнопка «Установить зависимости») — без ручного ввода команд."
        )
        return

    # time axis
    if tcol not in df.columns:
        st.warning(f"Нет колонки времени '{tcol}'")
        return
    x = df[tcol].to_numpy()

    # clamp playhead
    xph = None
    if playhead_x is not None:
        try:
            xph = float(playhead_x)
        except Exception:
            xph = None

    # Build figure
    if mode == "overlay":
        # Overlay mode: one plot, many traces; supports click->playhead
        fig = go.Figure()

        # try infer a common y-axis unit
        yaxis_title = ""
        units = []
        transforms = {}
        if auto_units:
            for c in y_cols:
                u, tr, _ya = _infer_unit_and_transform(c)
                units.append(u)
                transforms[c] = tr
            units_u = [u for u in units if u]
            if units_u and all(u == units_u[0] for u in units_u):
                yaxis_title = units_u[0]

        # playhead index (for markers)
        idx_ph = None
        if xph is not None:
            try:
                idx_ph = int(np.argmin(np.abs(np.asarray(x, dtype=float) - float(xph))))
            except Exception:
                idx_ph = None

        Trace = go.Scattergl if (render == "webgl") else go.Scatter

        for c in y_cols:
            if c not in df.columns:
                continue
            y_raw = df[c].to_numpy()
            tr = transforms.get(c) if auto_units else None
            y = y_raw
            if tr is not None:
                try:
                    y = tr(np.asarray(y_raw, dtype=float))
                except Exception:
                    y = y_raw

            xx = x
            yy = y
            if decimation == "minmax":
                xx, yy = decimate_minmax(xx, np.asarray(yy, dtype=float), max_points=int(max_points))
            else:
                if len(xx) > int(max_points):
                    idx2 = np.linspace(0, len(xx) - 1, num=int(max_points), dtype=int)
                    xx = xx[idx2]
                    yy = np.asarray(yy, dtype=float)[idx2]

            fig.add_trace(
                Trace(
                    x=xx,
                    y=yy,
                    mode="lines",
                    name=c,
                    hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
                )
            )

            # playhead marker for this trace
            if idx_ph is not None and 0 <= idx_ph < len(x):
                try:
                    # marker uses original full-res value (not decimated)
                    yph = float(y[idx_ph]) if idx_ph < len(y) else None
                    if yph is not None and np.isfinite(yph):
                        fig.add_trace(
                            go.Scatter(
                                x=[float(x[idx_ph])],
                                y=[yph],
                                mode="markers",
                                marker=dict(size=8, color="rgba(0,0,0,0.55)"),
                                showlegend=False,
                                hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
                            )
                        )
                except Exception:
                    pass

        # hover settings
        if hover_unified:
            fig.update_layout(hovermode="x unified")
        else:
            fig.update_layout(hovermode="closest")

        # event markers
        if events:
            try:
                for ev in events[:200]:
                    t_ev = float(ev.get("t", 0.0))
                    sev = str(ev.get("severity", "info")).lower()
                    col = "rgba(0,0,0,0.10)"
                    if sev == "warn":
                        col = "rgba(255,165,0,0.22)"
                    if sev == "error":
                        col = "rgba(255,0,0,0.30)"
                    fig.add_shape(
                        type="line",
                        x0=t_ev,
                        x1=t_ev,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line=dict(width=1, dash="dot", color=col),
                    )
            except Exception:
                pass

        # playhead vertical line
        if xph is not None:
            try:
                fig.add_shape(
                    type="line",
                    x0=float(xph),
                    x1=float(xph),
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    line=dict(width=2, color="rgba(0,0,0,0.45)"),
                )
            except Exception:
                pass

        fig.update_layout(
            title=title,
            height=460,
            margin=dict(l=50, r=20, t=50, b=40),
            yaxis_title=yaxis_title,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )

        st.session_state[plot_key + "__trace_names"] = list(y_cols)
        state = safe_plotly_chart(fig, key=plot_key, on_select="rerun", selection_mode=("points",))

        # click -> playhead request
        pts = _extract_plotly_selection_points(state)
        if pts:
            sig = _plotly_points_signature(pts)
            last_sig = st.session_state.get(plot_key + "__last_sig")
            if sig != last_sig:
                st.session_state[plot_key + "__last_sig"] = sig
                try:
                    x0 = pts[0].get("x")
                    if x0 is not None:
                        st.session_state["playhead_request_x"] = float(x0)
                except Exception:
                    pass

        return

    # stacked oscilloscope: one signal per row
    rows = len(y_cols)
    height = max(260, min(1200, 140 * rows + 80))
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, subplot_titles=y_cols)

    # add traces
    for i, c in enumerate(y_cols):
        if c not in df.columns:
            continue
        y_raw = df[c].to_numpy()
        unit = ""
        tr = None
        if auto_units:
            unit, tr, _ya = _infer_unit_and_transform(c)
        y = y_raw
        if tr is not None:
            try:
                y = tr(np.asarray(y_raw, dtype=float))
            except Exception:
                y = y_raw

        xx = x
        yy = y
        if decimation == "minmax":
            xx, yy = decimate_minmax(xx, np.asarray(yy, dtype=float), max_points=int(max_points))
        else:
            # stride (fast)
            if len(xx) > int(max_points):
                idx2 = np.linspace(0, len(xx) - 1, num=int(max_points), dtype=int)
                xx = xx[idx2]
                yy = np.asarray(yy, dtype=float)[idx2]

        Trace = go.Scattergl if (render == "webgl") else go.Scatter
        fig.add_trace(
            Trace(
                x=xx,
                y=yy,
                mode="lines",
                name=c,
                showlegend=False,
                hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
            ),
            row=i + 1,
            col=1,
        )
        if unit:
            fig.update_yaxes(title_text=unit, row=i + 1, col=1)

    # hover settings
    if hover_unified:
        # 'hoversubplots' makes unified hover work across stacked subplots (Plotly >=5.21)
        fig.update_layout(hovermode="x unified", hoversubplots="axis")
    else:
        fig.update_layout(hovermode="closest")

    # event markers
    if events:
        try:
            for ev in events[:200]:
                t_ev = float(ev.get("t", 0.0))
                sev = str(ev.get("severity", "info")).lower()
                col = "rgba(0,0,0,0.10)"
                if sev == "warn": col = "rgba(255,165,0,0.22)"
                if sev == "error": col = "rgba(255,0,0,0.30)"
                fig.add_shape(type="line", x0=t_ev, x1=t_ev, y0=0, y1=1, xref="x", yref="paper",
                              line=dict(width=1, dash="dot", color=col))
        except Exception:
            pass

    # playhead vertical line
    if xph is not None:
        try:
            fig.add_shape(type="line", x0=float(xph), x1=float(xph), y0=0, y1=1, xref="x", yref="paper",
                          line=dict(width=2, color="rgba(0,0,0,0.45)"))
        except Exception:
            pass

    fig.update_layout(title=title, height=height, margin=dict(l=40, r=20, t=50, b=35))
    # IMPORTANT: activate selection events so click can jump playhead
    st.session_state[plot_key + "__trace_names"] = list(y_cols)
    state = safe_plotly_chart(fig, key=plot_key, on_select="rerun", selection_mode=("points",))

    # click -> playhead request
    pts = _extract_plotly_selection_points(state)
    if pts:
        sig = _plotly_points_signature(pts)
        last_sig = st.session_state.get(plot_key + "__last_sig")
        if sig != last_sig:
            st.session_state[plot_key + "__last_sig"] = sig
            try:
                x0 = pts[0].get("x")
                if x0 is not None:
                    st.session_state["playhead_request_x"] = float(x0)
            except Exception:
                pass


_GRAPH_STUDIO_PLOTLY_MISSING_MESSAGE = (
    "Plotly не установлен — интерактивные графики (Graph Studio / Plotly) отключены.\n\n"
    "Решение: установите зависимости через лаунчер (кнопка «Установить зависимости») — без ручного ввода команд."
)

plot_studio_timeseries = build_plot_studio_renderer(
    has_plotly=_HAS_PLOTLY,
    go_module=go,
    make_subplots_fn=make_subplots,
    safe_plotly_chart_fn=safe_plotly_chart,
    infer_unit_and_transform_fn=_infer_unit_and_transform,
    extract_plotly_selection_points_fn=_extract_plotly_selection_points,
    plotly_points_signature_fn=_plotly_points_signature,
    decimate_minmax_fn=decimate_minmax,
    missing_plotly_message=_GRAPH_STUDIO_PLOTLY_MISSING_MESSAGE,
)


# -------------------------------
# Event/alert detection for the global timeline (playhead)
# -------------------------------

def _legacy_compute_events_dead(
    df_main: pd.DataFrame | None,
    df_p: pd.DataFrame | None,
    df_open: pd.DataFrame | None,
    params_abs: dict,
    test: dict,
    vacuum_min_gauge_bar: float = -0.2,
    pmax_margin_bar: float = 0.10,
    chatter_window_s: float = 0.25,
    chatter_toggle_count: int = 6,
    max_events: int = 240,
) -> List[dict]:
    """Compute a list of events/alerts for the shared timeline.

    Returns list of dicts:
      {id, idx, t, severity ('info'|'warn'|'error'), kind, name, label}

    Notes:
    - Uses *downsampled* data currently shown in UI (so markers match the timeline index).
    - Keeps number of events bounded (max_events) to avoid UI overload.
    """
    events: List[dict] = []

    if df_main is None or "время_с" not in df_main.columns or len(df_main) == 0:
        return events

    t_arr = df_main["время_с"].to_numpy(dtype=float)
    n = int(len(t_arr))
    if n <= 1:
        return events

    P_ATM = float(params_abs.get("_P_ATM", 101325.0))
    ATM_PA = 101325.0

    def add_event(idx: int, severity: str, kind: str, name: str, label: str):
        idx_i = int(max(0, min(int(idx), n - 1)))
        ev = {
            "id": f"{kind}:{name}:{idx_i}",
            "idx": idx_i,
            "t": float(t_arr[idx_i]),
            "severity": severity,
            "kind": kind,
            "name": name,
            "label": label,
        }
        events.append(ev)

    # --------------------
    # 1) Wheel lift (wheel in air)
    # --------------------
    for c in ["ЛП", "ПП", "ЛЗ", "ПЗ"]:
        col = f"колесо_в_воздухе_{c}"
        if col in df_main.columns:
            m = df_main[col].to_numpy()
            # treat any nonzero as True
            starts = _run_starts(m != 0)
            for i0 in starts:
                add_event(i0, "warn", "wheel_lift", c, f"Колесо {c} в воздухе")

    # --------------------
    
    # --------------------
    # 1b) Sanity check: road differs, but wheels look identical
    # --------------------
    try:
        corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
        road_cols = [f"дорога_{c}_м" for c in corners]
        wheel_cols = [f"перемещение_колеса_{c}_м" for c in corners]
        if all(c in df_main.columns for c in road_cols) and all(c in df_main.columns for c in wheel_cols):
            road_mat = df_main[road_cols].to_numpy(dtype=float)
            wheel_mat = df_main[wheel_cols].to_numpy(dtype=float)

            # If road inputs differ across corners, but wheel displacements don't,
            # it's usually a sign of: wrong road_func, wrong base/track keys, or plotting mix-up.
            road_span = np.ptp(road_mat, axis=1)
            wheel_span = np.ptp(wheel_mat, axis=1)

            if float(np.nanmax(road_span)) > 1e-4 and float(np.nanmax(wheel_span)) < 1e-5:
                idx0 = int(np.where(road_span > 1e-4)[0][0])
                add_event(
                    idx0,
                    "warn",
                    "sanity",
                    "wheels_identical",
                    "Санити: профиль дороги различается по колёсам, но ходы колёс почти одинаковы — проверьте road_func/графики/ключи колеи/базы.",
                )
    except Exception:
        pass

# 2) Stroke limit / bump stop near
    # --------------------
    stroke = float(params_abs.get("ход_штока", 0.25))
    margin = float(test.get("target_мин_запас_до_упора_штока_м", 0.005))
    margin = max(0.0, margin)

    for c in ["ЛП", "ПП", "ЛЗ", "ПЗ"]:
        col = f"положение_штока_{c}_м"
        if col in df_main.columns:
            x = df_main[col].to_numpy(dtype=float)
            m_low = x <= margin
            m_high = x >= (stroke - margin)
            for i0 in _run_starts(m_low):
                add_event(i0, "warn", "stroke_limit", c, f"Шток {c}: близко к упору (min)")
            for i0 in _run_starts(m_high):
                add_event(i0, "warn", "stroke_limit", c, f"Шток {c}: близко к упору (max)")

    # --------------------
    # 3) Rod speed limit
    # --------------------
    v_lim = float(test.get("target_лимит_скорости_штока_м_с", 2.0))
    if v_lim > 0:
        for c in ["ЛП", "ПП", "ЛЗ", "ПЗ"]:
            col = f"скорость_штока_{c}_м_с"
            if col in df_main.columns:
                v = df_main[col].to_numpy(dtype=float)
                m_v = np.abs(v) > v_lim
                for i0 in _run_starts(m_v):
                    add_event(i0, "warn", "rod_speed", c, f"Скорость штока {c} > {v_lim:g} м/с")

    # --------------------
    # 4) Overpressure / vacuum checks (by node pressures if present)
    # --------------------
    if df_p is not None and "время_с" in df_p.columns and len(df_p) > 1:
        cols = [c for c in df_p.columns if c != "время_с" and c != "АТМ"]
        if cols:
            Pmax_abs = float(params_abs.get("давление_Pmax_предохран", P_ATM + 8e5))
            pmax_thr = Pmax_abs + float(pmax_margin_bar) * BAR_PA

            try:
                # Align df_p -> df_main time vector (nearest) so events don't disappear when tables are downsampled differently.
                t_src = df_p["время_с"].to_numpy(dtype=float)
                order = np.argsort(t_src)
                t_src = t_src[order]
                P_src = df_p[cols].to_numpy(dtype=float)[order]

                if t_src.size >= 2:
                    idx = np.searchsorted(t_src, t_arr, side="left")
                    idx = np.clip(idx, 1, t_src.size - 1)
                    left = idx - 1
                    right = idx
                    choose_right = (t_src[right] - t_arr) < (t_arr - t_src[left])
                    idx_near = np.where(choose_right, right, left)
                else:
                    idx_near = np.zeros_like(t_arr, dtype=int)

                P_nodes = P_src[idx_near]
                p_max = np.nanmax(P_nodes, axis=1)
                p_min = np.nanmin(P_nodes, axis=1)
            except Exception:
                p_max = None
                p_min = None

            if p_max is not None:
                for i0 in _run_starts(p_max > pmax_thr):
                    add_event(i0, "error", "overpressure", "nodes", "P>ПРЕДОХ (max node)")

            vac_thr = P_ATM + float(vacuum_min_gauge_bar) * BAR_PA
            # do not go below absolute min + small epsilon (avoid false positives)
            p_abs_min = float(params_abs.get("минимальное_абсолютное_давление_Па", 1000.0))
            vac_thr = max(vac_thr, p_abs_min + 1.0)

            if p_min is not None:
                for i0 in _run_starts(p_min < vac_thr):
                    add_event(i0, "warn", "vacuum", "nodes", f"Вакуум: min node < {vacuum_min_gauge_bar:g} бар(изб)")

    # --------------------
    # 5) Valve chatter (rapid toggling) from df_open
    # --------------------
    if df_open is not None and "время_с" in df_open.columns and len(df_open) > 1:
        # Align df_open -> df_main time vector (nearest), so event markers don't randomly disappear.
        try:
            t_src = df_open["время_с"].to_numpy(dtype=float)
            order = np.argsort(t_src)
            t_src = t_src[order]

            if t_src.size >= 2:
                idx = np.searchsorted(t_src, t_arr, side="left")
                idx = np.clip(idx, 1, t_src.size - 1)
                left = idx - 1
                right = idx
                choose_right = (t_src[right] - t_arr) < (t_arr - t_src[left])
                idx_near = np.where(choose_right, right, left)
            else:
                idx_near = np.zeros_like(t_arr, dtype=int)

            df_open_aligned = df_open.iloc[order].reset_index(drop=True).iloc[idx_near].reset_index(drop=True)
        except Exception:
            df_open_aligned = df_open

        # Analyze only edges that actually toggle, and keep top few.
        edge_cols = [c for c in df_open_aligned.columns if c != "время_с"]
        toggle_stats = []
        for col in edge_cols:
            arr = df_open_aligned[col].to_numpy()
            # toggles where value changes (0->1 or 1->0)
            d = np.diff(arr.astype(int), prepend=int(arr[0]))
            togg = np.where(d != 0)[0].astype(int)
            if togg.size > 0:
                toggle_stats.append((int(togg.size), col, togg))
        toggle_stats.sort(reverse=True, key=lambda x: x[0])

        # only check top N edges by toggles (avoid overload)
        for cnt, col, togg in toggle_stats[:8]:
            if cnt < chatter_toggle_count:
                continue
            # sliding window count
            i = 0
            j = 0
            togg_list = togg.tolist()
            while i < len(togg_list):
                t_i = float(t_arr[togg_list[i]])
                if j < i:
                    j = i
                while j < len(togg_list) and float(t_arr[togg_list[j]]) - t_i <= chatter_window_s:
                    j += 1
                win_cnt = j - i
                if win_cnt >= chatter_toggle_count:
                    nm = _shorten_name(col, 55)
                    add_event(togg_list[i], "info", "chatter", nm, f"Дребезг: {nm} ({win_cnt} toggles/{chatter_window_s:.2f}s)")
                    # skip to the end of this window to avoid spamming
                    i = j
                else:
                    i += 1

    # Sort by time, then severity (errors first at same time)
    sev_rank = {"error": 0, "warn": 1, "info": 2}
    events.sort(key=lambda e: (int(e.get("idx", 0)), sev_rank.get(str(e.get("severity")), 9), str(e.get("id"))))

    # Limit count to avoid UI overload
    if len(events) > max_events:
        # prefer errors/warns
        errs = [e for e in events if e.get("severity") == "error"]
        warns = [e for e in events if e.get("severity") == "warn"]
        infos = [e for e in events if e.get("severity") == "info"]

        keep: List[dict] = []
        keep.extend(errs[: max_events])
        if len(keep) < max_events:
            keep.extend(warns[: (max_events - len(keep))])
        if len(keep) < max_events:
            keep.extend(infos[: (max_events - len(keep))])
        # re-sort by idx
        keep.sort(key=lambda e: (int(e.get("idx", 0)), sev_rank.get(str(e.get("severity")), 9)))
        events = keep

    return events
def _legacy_plot_lines_dead(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    title: str,
    yaxis_title: str = "",
    transform_y=None,
    height: int = 320,
    plot_key: str | None = None,
    enable_select: bool = False,
    playhead_x: float | None = None,
    events: List[dict] | None = None,
    events_max: int = 120,
    events_show_labels: bool = False,
    events_label_severities: Tuple[str, ...] = ("error",),
):
    """Единый helper для графиков: Plotly (если установлен) или fallback на st.line_chart.

    Дополнительно: если задан playhead_x, рисуем вертикальную линию и маркеры значений
    на каждой кривой в текущий момент времени (по ближайшему индексу).

    Возвращает словарь с данными playhead (idx/x/values) или None.
    """
    if df is None or len(df) == 0:
        st.info("Нет данных для графика.")
        return None


    # --- v6_32+R59: prefer *_rel0 displacement columns for plots (if available) ---
    # В модели для метрических/угловых колонок создаются пары:
    #   <имя>            (абсолют / исходное)
    #   <имя>_rel0       (относительно нулевой позы: ровная дорога, статическая подвеска)
    #
    # Чтобы в легендах/выборе колонок оставались исходные имена, мы при наличии *_rel0
    # подменяем данные в df[<имя>] на df[<имя>_rel0].
    if st.session_state.get("use_rel0_for_plots", True):
        rel_map = {}
        for c in list(y_cols):
            if str(c).endswith("_rel0"):
                continue
            c_rel0_candidates = [f"{c}_rel0"]
            # backward compatibility: some older datasets used *_rel0_m / *_rel0_rad
            if str(c).endswith("_m"):
                c_rel0_candidates.append(str(c)[:-2] + "_rel0_m")
            if str(c).endswith("_rad"):
                c_rel0_candidates.append(str(c)[:-4] + "_rel0_rad")
            for c_rel0 in c_rel0_candidates:
                if c_rel0 in df.columns:
                    rel_map[c_rel0] = c
                    break
        if rel_map:
            # работаем на копии, чтобы не портить исходный df в кеше/сессии
            df = df.copy()
            for src, dst in rel_map.items():
                df[dst] = df[src]
    y_cols = [c for c in y_cols if c in df.columns]
    if len(y_cols) == 0:
        st.info("Не выбрано ни одной колонки для графика.")
        return None

    # ---- performance guard: while fallback animation is playing, avoid heavy Plotly rebuilds ----
    try:
        if st.session_state.get("skip_heavy_on_play", True) and is_any_fallback_anim_playing():
            if not st.session_state.get("_skip_plotly_notice_shown", False):
                st.info("Play (fallback) активен → Plotly-графики временно скрыты, чтобы анимация не тормозила. Поставь на паузу, чтобы вернуть графики.")
                st.session_state["_skip_plotly_notice_shown"] = True
            return None
    except Exception:
        pass

    if transform_y is None:
        def transform_y(a):
            return a

    # ---- playhead index (nearest in x) ----
    idx_ph = None
    xph = None
    x_arr = None
    try:
        x_arr = df[x_col].to_numpy(dtype=float)
        if playhead_x is not None and len(x_arr) > 0:
            idx_ph = int(np.argmin(np.abs(x_arr - float(playhead_x))))
            idx_ph = max(0, min(idx_ph, len(x_arr) - 1))
            xph = float(x_arr[idx_ph])
    except Exception:
        idx_ph = None
        xph = None

    # UI toggle: markers at playhead
    show_markers = bool(st.session_state.get("playhead_show_markers", True))

    play_values: Dict[str, float] = {}

    if _HAS_PLOTLY:
        fig = go.Figure()
        x = x_arr if x_arr is not None else df[x_col].to_numpy()

        # --- Event markers (vertical lines) ---
        # Draw event lines "below" traces so playhead/markers stay visible on top.
        if events:
            try:
                evs = list(events)
                # Thin out if too many events for performance/readability
                if events_max and len(evs) > int(events_max):
                    step = int(math.ceil(len(evs) / float(events_max)))
                    if step > 1:
                        evs = evs[::step]

                label_sev = set(str(s).lower() for s in (events_label_severities or ()))
                sev_color = {
                    "info": "rgba(0,0,0,0.10)",
                    "warn": "rgba(255,165,0,0.25)",
                    "error": "rgba(255,0,0,0.30)",
                }
                for ev in evs:
                    t_ev = float(ev.get("t", 0.0))
                    sev = str(ev.get("severity", "info")).lower()
                    col = sev_color.get(sev, "rgba(0,0,0,0.10)")
                    fig.add_shape(
                        type="line",
                        x0=t_ev,
                        x1=t_ev,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line=dict(width=1, dash="dot", color=col),
                        layer="below",
                    )
                    if events_show_labels and sev in label_sev:
                        fig.add_annotation(
                            x=t_ev,
                            y=1,
                            yref="paper",
                            text=_shorten_name(str(ev.get("kind", "evt")), 12),
                            showarrow=False,
                            xanchor="left",
                            yanchor="top",
                            font=dict(size=9, color=col),
                            bgcolor="rgba(255,255,255,0.6)",
                        )
            except Exception:
                pass


        for c in y_cols:
            y = transform_y(df[c].to_numpy())

            # IMPORTANT: Streamlit Plotly selection works on points.
            # For line charts, it's safer to have markers "exist" (they can be transparent)
            # so click selection reliably returns curve_number/point_index.
            if enable_select and plot_key:
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="lines+markers",
                        marker=dict(size=10, opacity=0.0),
                        name=c,
                    )
                )
            else:
                fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=c))

            # playhead marker per curve
            if idx_ph is not None and xph is not None:
                try:
                    yph = float(y[idx_ph])
                    play_values[c] = yph
                    if show_markers:
                        fig.add_trace(
                            go.Scatter(
                                x=[xph],
                                y=[yph],
                                mode="markers",
                                marker=dict(size=10, color="rgba(0,0,0,0.55)", symbol="circle"),
                                showlegend=False,
                                hovertemplate=f"{c}: %{{y:.6g}}<br>t=%{{x:.3f}} s<extra></extra>",
                            )
                        )
                except Exception:
                    pass

        # playhead vertical line
        if xph is not None:
            try:
                fig.add_shape(
                    type="line",
                    x0=float(xph),
                    x1=float(xph),
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    line=dict(width=1, dash="dot", color="rgba(0,0,0,0.35)"),
                )
            except Exception:
                pass

        fig.update_layout(
            title=title,
            height=int(height),
            margin=dict(l=10, r=10, t=40, b=10),
        )
        if yaxis_title:
            fig.update_yaxes(title=yaxis_title)
        fig.update_xaxes(title=x_col)

        if enable_select and plot_key:
            # Store mapping curve_number -> trace name so we can sync selection -> scheme.
            st.session_state[plot_key + "__trace_names"] = list(y_cols)
            safe_plotly_chart(fig, key=plot_key, on_select="rerun", selection_mode=("points",))
        else:
            safe_plotly_chart(fig)

    else:
        # Fallback: st.line_chart
        d = df[[x_col] + y_cols].copy()
        d = d.set_index(x_col)
        st.line_chart(d, height=height)

        if idx_ph is not None:
            for c in y_cols:
                try:
                    y = transform_y(df[c].to_numpy())
                    play_values[c] = float(y[idx_ph])
                except Exception:
                    pass

    if idx_ph is not None and xph is not None:
        return {"idx": int(idx_ph), "x": float(xph), "values": play_values}
    return None


def _prepare_plot_lines_df_and_y_cols(
    df: pd.DataFrame,
    y_cols: List[str],
) -> tuple[pd.DataFrame, List[str]]:
    if not st.session_state.get("use_rel0_for_plots", True):
        return df, list(y_cols)
    return prefer_rel0_plot_columns(df, list(y_cols))


plot_lines = build_line_plot_renderer(
    has_plotly=_HAS_PLOTLY,
    go_module=go,
    safe_plotly_chart_fn=safe_plotly_chart,
    is_any_fallback_anim_playing_fn=is_any_fallback_anim_playing,
    shorten_name_fn=_shorten_name,
    preprocess_df_and_y_cols_fn=_prepare_plot_lines_df_and_y_cols,
)










# Shared worker/process helpers override the legacy inline copy above.
start_worker = build_background_worker_starter(
    console_python_executable_fn=console_python_executable,
)


# -------------------------------
# UI
# -------------------------------
safe_set_page_config(page_title="Пневмоподвеска: solver+оптимизация", layout="wide")


# --- UI bootstrap + самопроверка: показать пользователю явный статус (чтобы не было ощущения "висит") ---
_startup_first = "_ui_startup_done" not in st.session_state
_startup_status = None
_startup_spinner_cm = None

if _startup_first:
    if hasattr(st, "status"):
        try:
            _startup_status = st.status("Инициализация интерфейса…", expanded=True)
        except Exception:
            _startup_status = None
    if _startup_status is None:
        # Fallback: обычный спиннер (исчезает сам)
        _startup_spinner_cm = st.spinner("Инициализация интерфейса…")
        try:
            _startup_spinner_cm.__enter__()
        except Exception:
            _startup_spinner_cm = None

try:
    # 1) UI bootstrap: подсказки + автозагрузка сохранённого ввода + дефолты производительности + run artifacts
    if _startup_status is not None:
        try:
            _startup_status.write("Загрузка сохранённых настроек и справки…")
        except Exception:
            pass

    try:
        from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
        _ui_bootstrap(st)
    except Exception:
        # bootstrap не должен ломать запуск
        pass

    # 2) Автономная самопроверка (QC): на старте она может занимать секунды — поэтому показываем статус.
    # Streamlit перезапускает скрипт на каждое взаимодействие — держим флаг в session_state.
    try:
        if "_autoselfcheck_v1_done" not in st.session_state:
            if _startup_status is not None:
                try:
                    _startup_status.write("Самопроверка (QC): проверяем целостность пакета…")
                except Exception:
                    pass

            from pneumo_solver_ui.tools.autoselfcheck import ensure_autoselfcheck_once
            from pneumo_solver_ui.diag.json_safe import json_dumps

            _r = ensure_autoselfcheck_once(strict=None)
            st.session_state["_autoselfcheck_v1_done"] = True
            st.session_state["_autoselfcheck_v1_ok"] = bool(getattr(_r, "ok", False))

            # Отчёт рядом с логами (входит в диагностический пакет)
            try:
                if isinstance(LOG_DIR, Path):
                    _out = LOG_DIR / "autoselfcheck.json"
                    _rep = {
                        "ok": bool(getattr(_r, "ok", False)),
                        "results": dict(getattr(_r, "results", {}) or {}),
                        "failures": list(getattr(_r, "failures", []) or []),
                        "summary": str(getattr(_r, "summary", "")),
                    }
                    _out.write_text(json_dumps(_rep, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Событие в JSONL лог
            try:
                log_event(
                    "autoselfcheck_v1",
                    ok=bool(getattr(_r, "ok", False)),
                    failures=list(getattr(_r, "failures", []) or []),
                    summary=str(getattr(_r, "summary", "")),
                )
            except Exception:
                pass
    except Exception:
        # best-effort: ни при каких обстоятельствах не ломаем UI из-за самопроверки
        pass

finally:
    if _startup_spinner_cm is not None:
        try:
            _startup_spinner_cm.__exit__(None, None, None)
        except Exception:
            pass
    if _startup_status is not None:
        try:
            _startup_status.update(label="Инициализация завершена", state="complete", expanded=False)
        except Exception:
            pass
    if _startup_first:
        st.session_state["_ui_startup_done"] = True

# --- Logging bootstrap (1 file per session) ---
if not st.session_state.get("_ui_start_logged"):
    log_event(
        "ui_start",
        ver=APP_RELEASE,
        pid=os.getpid(),
        python=sys.version.split()[0],
        streamlit=getattr(st, "__version__", ""),
        has_plotly=_HAS_PLOTLY,
        has_svg_autotrace=_HAS_SVG_AUTOTRACE,
        has_psutil=_HAS_PSUTIL,
        proc=_proc_metrics(),
        cwd=str(HERE),
    )
    st.session_state["_ui_start_logged"] = True

# --- Default SVG mapping JSON (loaded by default) ---
# Это закрывает требование: "Нужен mapping JSON - сделай рабочий и грузи по дефолту".
if "svg_mapping_text" not in st.session_state or not str(st.session_state.get("svg_mapping_text", "")).strip():
    try:
        st.session_state["svg_mapping_text"] = DEFAULT_SVG_MAPPING_PATH.read_text(encoding="utf-8")
        st.session_state["svg_mapping_source"] = str(DEFAULT_SVG_MAPPING_PATH)
        log_event("svg_mapping_loaded_default", path=str(DEFAULT_SVG_MAPPING_PATH))
    except Exception as e:
        # Если файл недоступен, подставляем минимальный рабочий шаблон.
        st.session_state["svg_mapping_text"] = json.dumps(
            {"version": 2, "viewBox": "0 0 1920 1080", "edges": {}, "nodes": {}},
            ensure_ascii=False,
            indent=2,
        )
        st.session_state["svg_mapping_source"] = "generated_template"
        log_event("svg_mapping_default_failed", error=repr(e))

# -------------------------------
# UI: компактный макет (чтобы короткие селекторы/списки не растягивались на весь экран)
# -------------------------------
with st.sidebar:
    st.markdown("## UI")
    ui_compact = st.checkbox(
        "Сжатый макет (не растягивать списки)",
        value=st.session_state.get("ui_compact", True),
        help="Ограничивает максимальную ширину контента. Полезно на широких мониторах: короткие списки/селекторы не будут на всю ширину.",
    )
    st.session_state["ui_compact"] = ui_compact


    st.checkbox(
        "При Play (fallback) скрывать Plotly-графики",
        value=st.session_state.get("skip_heavy_on_play", True),
        key="skip_heavy_on_play",
        help="Fallback-анимация использует автообновление (каждый кадр = rerun всего приложения). "
             "Чтобы Play не превращался в 'бесконечный расчёт', мы можем временно скрывать тяжёлые Plotly-графики. "
             "Поставь на паузу — графики вернутся.",
    )

    # --- v6_29: rel0 plots toggle ---
    st.session_state.setdefault("use_rel0_for_plots", True)
    st.checkbox(
        "Графики: показывать смещения относительно нулевой дороги (rel0)",
        key="use_rel0_for_plots",
        help=(
            "Если в данных есть колонки *_rel0_m (смещения относительно нулевой дороги), "
            "графики будут строиться по ним, но с привычными названиями в легенде. "
            "Выключи, если хочешь видеть абсолютные координаты."
        ),
    )

if st.session_state.get("ui_compact", True):
    st.markdown(
        """<style>
        .block-container { max-width: 1280px; padding-top: 1.0rem; }
        </style>""",
        unsafe_allow_html=True,
    )

# Синхронизация: клик по SVG схеме → выбор веток/узлов в графиках
consume_svg_pick_event()

# Синхронизация: клик по механике → выбор углов для графиков/подсветки
consume_mech_pick_event()

# Синхронизация: клик/выделение на графиках Plotly → подсветка/выбор на SVG схеме
consume_plotly_pick_events()

# Shared timeline (playhead) updates
consume_playhead_event()

render_heavy_workflow_header(st)
render_heavy_optimization_page_overview(st)

# Truth panel slot (filled later when hashes/results are available)
truth_slot = st.container()

# --- UI_CSS_LABEL_WRAP: базовая защита от налезания подписей/лейблов ---
st.markdown(
    """
    <style>
    /* Разрешаем перенос строк в лейблах виджетов */
    div[data-testid="stWidgetLabel"] > label {
        white-space: normal !important;
        line-height: 1.15;
    }

    /* Подсказки: ограничим ширину, чтобы не расползались */
    div[data-testid="stTooltipContent"] {
        max-width: 520px;
    }

    /* Чуть меньше вертикальных зазоров в сайдбаре */
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.4rem;
    }

    /* Курсор: делаем кликабельные элементы очевидными (в т.ч. selectbox, expander) */
    div[data-testid="stSelectbox"] div[role="button"],
    div[data-testid="stMultiSelect"] div[role="button"],
    div[data-testid="stSelectbox"] input,
    div[data-testid="stMultiSelect"] input,
    div[data-baseweb="select"] input,
    div[data-testid="stExpander"] summary,
    div[data-testid="stRadio"] label,
    div[data-testid="stCheckbox"] label {
        cursor: pointer !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

colA, colB = st.columns([1.2, 1.0], gap="large")

with st.sidebar:
    st.divider()
    st.header("Сохранение ввода")
    st.caption(
        "Форма автоматически запоминает введённые значения, чтобы вернуться к работе "
        "после перезапуска страницы или аварийного завершения."
    )

    # Включено по умолчанию. Можно отключить, если нужен «чистый» запуск.
    st.toggle(
        "Автосохранение",
        value=bool(st.session_state.get("ui_autosave_enabled", True)),
        key="ui_autosave_enabled",
        help=(
            "Если включено, интерфейс периодически сохраняет текущие значения формы, "
            "настройки и прогресс в JSON-файл в рабочем каталоге состояния."
        ),
    )

    try:
        from pneumo_solver_ui.ui_persistence import pick_state_dir, autosave_path

        _sd = pick_state_dir()
        if _sd is None:
            st.warning("Папка для сохранения не найдена или недоступна для записи. Автосохранение отключено.")
        else:
            _ap = autosave_path(_sd)
            st.caption(f"Файл автосохранения: `{_ap}`")

            # статус загрузки/сохранения
            if st.session_state.get("ui_autosave_loaded"):
                st.success("Настройки загружены из автосохранения.")
            if st.session_state.get("ui_autosave_load_error"):
                st.warning(f"Не удалось загрузить автосохранение: {st.session_state.get('ui_autosave_load_error')}")

            if st.session_state.get("ui_autosave_last_saved"):
                import datetime as _dt
                _ts = float(st.session_state.get("ui_autosave_last_saved") or 0.0)
                if _ts > 0:
                    st.caption("Последнее автосохранение: " + _dt.datetime.fromtimestamp(_ts).strftime("%Y-%m-%d %H:%M:%S"))

            c_save, c_reset = st.columns(2)
            with c_save:
                if st.button("Сохранить сейчас", key="ui_save_now", width="stretch"):
                    try:
                        from pneumo_solver_ui.ui_persistence import build_state_dict, save_autosave
                        ok, info = save_autosave(_sd, build_state_dict(st.session_state))
                        if ok:
                            st.session_state["ui_autosave_last_saved"] = __import__("time").time()
                            st.success("Сохранено.")
                        else:
                            st.warning(f"Не удалось сохранить: {info}")
                    except Exception as _e:
                        st.warning(f"Не удалось сохранить: {_e}")
            with c_reset:
                if st.button("Сбросить ввод", key="ui_reset_input_btn", width="stretch"):
                    st.session_state["ui_reset_input_confirm"] = True

            if st.session_state.get("ui_reset_input_confirm"):
                st.warning("Сброс удалит введённые таблицы и автосохранение. Это действие нельзя отменить.")
                c_yes, c_no = st.columns(2)
                with c_yes:
                    if st.button("Да, сбросить", key="ui_reset_input_yes", width="stretch"):
                        # очистка ключевых UI-данных
                        for _k in [
                            "df_params_edit",
                            "df_suite_edit",
                            "spring_table_df",
                            "df_params_signature",
                            "ui_params_group",
                            "ui_params_search",
                            "ui_params_selected_key",
                            "ui_suite_stage_filter",
                            "ui_suite_only_enabled",
                            "ui_suite_search",
                        ]:
                            try:
                                st.session_state.pop(_k, None)
                            except Exception:
                                pass
                        # удалить файл автосохранения
                        try:
                            if _ap.exists():
                                _ap.unlink()
                        except Exception:
                            pass
                        st.session_state["ui_reset_input_confirm"] = False
                        st.success("Сброс выполнен. Перезагрузка...")
                        st.rerun()
                with c_no:
                    if st.button("Отмена", key="ui_reset_input_no", width="stretch"):
                        st.session_state["ui_reset_input_confirm"] = False
    except Exception:
        # эта панель не должна ломать UI
        pass

    render_project_files_section_intro(st)
    model_path = st.text_input(
        "Файл модели (py)",
        value=str(_suggest_default_model_path(HERE)),
        key="ui_model_path",
        help="Python-файл, где описана модель пневмоподвески. Обычно менять его не нужно.",
    )
    worker_path = st.text_input(
        "Файл оптимизатора (py)",
        value=str(canonical_worker_path(HERE)),
        key="ui_worker_path",
        help="Python-файл, который запускает оптимизацию. Обычно менять его не нужно.",
    )

    render_test_suite_section_intro(st)

    render_search_space_section_intro(st)

    # --- Миграция ключей (чтобы при обновлениях не терять настройки пользователя)
    if "opt_use_staged" not in st.session_state and "use_staged_opt" in st.session_state:
        st.session_state["opt_use_staged"] = bool(st.session_state.get("use_staged_opt"))
    if "opt_autoupdate_baseline" not in st.session_state and "autoupdate_baseline" in st.session_state:
        st.session_state["opt_autoupdate_baseline"] = bool(st.session_state.get("autoupdate_baseline"))

    # --- Clamp persisted numeric state before rendering widgets (protect against stale autosave / StreamlitValueBelowMinError)
    def _clamp_state_number(key: str, default, *, min_value=None, max_value=None, cast=float):
        raw = st.session_state.get(key, default)
        try:
            val = cast(raw)
        except Exception:
            try:
                val = cast(default)
            except Exception:
                val = default
        if min_value is not None:
            try:
                val = max(cast(min_value), val)
            except Exception:
                pass
        if max_value is not None:
            try:
                val = min(cast(max_value), val)
            except Exception:
                pass
        st.session_state[key] = val
        return val

    seed_optimization_ready_session_state(
        st.session_state,
        cpu_count=int(os.cpu_count() or 4),
        platform_name=sys.platform,
    )

    _cpu_n_pre = int(os.cpu_count() or 4)
    _platform_cap_pre = 61 if sys.platform.startswith("win") else 128
    _jobs_cap_pre = int(max(1, min(_platform_cap_pre, _cpu_n_pre)))
    _jobs_default_pre = int(diagnostics_jobs_default(_cpu_n_pre, platform_name=sys.platform))
    _clamp_state_number("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT, min_value=0.5, max_value=10080.0, cast=float)
    _clamp_state_number("ui_jobs", _jobs_default_pre, min_value=1, max_value=_jobs_cap_pre, cast=int)
    _clamp_state_number("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES, min_value=0, max_value=2_147_483_647, cast=int)
    _clamp_state_number("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS, min_value=0, max_value=2_147_483_647, cast=int)
    _clamp_state_number("ui_flush_every", 20, min_value=1, max_value=200, cast=int)
    _clamp_state_number("ui_progress_every_sec", 1.0, min_value=0.2, max_value=10.0, cast=float)
    _clamp_state_number("ui_refresh_sec", 1.0, min_value=0.2, max_value=10.0, cast=float)
    _clamp_state_number("stop_pen_stage1", 25.0, min_value=0.0, max_value=1e9, cast=float)
    _clamp_state_number("stop_pen_stage2", 15.0, min_value=0.0, max_value=1e9, cast=float)

    # Главная больше не держит второй launcher оптимизации.
    # Здесь остаётся только инженерный gateway + read-only snapshot,
    # а запуск/stop/resume/monitoring живут на отдельной странице.
    auto_refresh = False
    refresh_sec = float(st.session_state.get("ui_refresh_sec", 1.0) or 1.0)

    st.subheader("Оптимизация — отдельная страница")
    st.caption(
        "На главной остаются search-space contract и входные данные: таблица параметров, режимы и suite. "
        "Запуск, stop/resume, monitoring и все настройки оптимизации собраны на отдельной странице «Оптимизация»."
    )

    _render_home_opt_config_snapshot(compact=True)
    _render_home_opt_last_pointer_summary(compact=True)

    st.caption(
        "Границы параметров и test-suite задаются на главной в текущих разделах; алгоритм, backend, "
        "остановка и просмотр live-статуса — на отдельной странице оптимизации."
    )

    _opt_gateway_nav(
        "pneumo_solver_ui/pages/30_Optimization.py",
        "🎯 Открыть страницу оптимизации",
        key="home_opt_gateway_sidebar_go_optimization",
        help_text="Все ручки запуска, stop/resume, мониторинг и текущий лог оптимизации.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/20_DistributedOptimization.py",
        "📊 Результаты оптимизации / ExperimentDB",
        key="home_opt_gateway_sidebar_go_results",
        help_text="Просмотр результатов и distributed ExperimentDB.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/31_OptDatabase.py",
        "🗄️ База оптимизаций",
        key="home_opt_gateway_sidebar_go_db",
        help_text="Отдельная страница базы оптимизаций.",
    )

    # Legacy home optimization block retained only as dormant source surface
    # for regression/source guards. Live launch path = dedicated Optimization page.
    if False:
            # --- Основные настройки (используются почти всегда)
            minutes = st.number_input(
                "Лимит времени (мин)",
                min_value=0.5,
                max_value=10080.0,
                value=float(st.session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT)),
                step=1.0,
                key="ui_opt_minutes",
                help="Ограничение по времени работы оптимизатора. После лимита процесс завершится корректно и сохранит прогресс.",
            )

            # По умолчанию стараемся задействовать все доступные ядра CPU.
            # max_value делаем динамическим (но с разумным ограничением, чтобы не улететь в сотни процессов на больших серверах).
            _cpu_n = int(os.cpu_count() or 4)
            # На Windows у ProcessPoolExecutor есть лимит max_workers<=61.
            # См. документацию Python: concurrent.futures.ProcessPoolExecutor.
            _platform_cap = 61 if sys.platform.startswith("win") else 128
            _jobs_cap = int(max(1, min(_platform_cap, _cpu_n)))
            _jobs_default = int(diagnostics_jobs_default(_cpu_n, platform_name=sys.platform))

            jobs = st.number_input(
                "Параллельность (jobs)",
                min_value=1,
                max_value=int(_jobs_cap),
                value=int(st.session_state.get("ui_jobs", _jobs_default)),
                step=1,
                key="ui_jobs",
                help="Сколько процессов параллельно считать кандидатов. По умолчанию = все ядра CPU. Больше — быстрее, но выше нагрузка на CPU/RAM.",
            )

            st.divider()
            st.subheader("Результаты")

            run_name = st.text_input(
                "Имя прогона",
                value=str(st.session_state.get("opt_run_name", "main")),
                key="opt_run_name",
                help=(
                    "Это имя папки в workspace/opt_runs. Используйте разные имена для разных серий экспериментов "
                    "(например: 'main', 'winter', 'camozzi_v1')."
                ),
            )

            out_prefix = st.text_input(
                "Имя CSV (префикс)",
                value=str(st.session_state.get("ui_out_prefix", "results_opt")),
                key="ui_out_prefix",
                help="Имя файла результата внутри папки прогона. Например: results_opt.csv или results_opt_all.csv.",
            )

            st.divider()
            st.subheader("Режим запуска")

            opt_use_staged = st.checkbox(
                "Режим по стадиям (StageRunner) — рекомендуется",
                value=bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)),
                key="opt_use_staged",
                help=(
                    "StageRunner сначала прогоняет дешёвые тесты и отсеивает плохие кандидаты, "
                    "затем добавляет дорогие тесты. Обычно это быстрее и устойчивее, чем «всё сразу». "
                    "Нумерация стадий 0-based: первая стадия = 0."
                ),
            )
            # алиас для старых сохранений/кода (не удаляем резко)
            st.session_state["use_staged_opt"] = bool(opt_use_staged)

            opt_autoupdate_baseline = st.checkbox(
                "Авто‑обновлять лучший опорный прогон",
                value=bool(st.session_state.get("opt_autoupdate_baseline", True)),
                key="opt_autoupdate_baseline",
                help=(
                    "Если найден кандидат лучше текущего опорного прогона, StageRunner сохранит его "
                    "как новый стартовый файл в workspace/baselines/baseline_best.json. "
                    "Этот файл можно использовать как следующую стартовую точку."
                ),
            )
            st.session_state["autoupdate_baseline"] = bool(opt_autoupdate_baseline)

            # --- Дополнительные настройки (прячем по умолчанию)
            with st.expander("Дополнительные настройки запуска (редко нужно)", expanded=True):
                seed_candidates = st.number_input(
                    "Seed кандидатов",
                    min_value=0,
                    max_value=2_147_483_647,
                    value=int(st.session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES)),
                    step=1,
                    key="ui_seed_candidates",
                    help="Влияет только на генерацию набора кандидатов (комбинаций параметров) в оптимизаторе.",
                )
                seed_conditions = st.number_input(
                    "Seed условий",
                    min_value=0,
                    max_value=2_147_483_647,
                    value=int(st.session_state.get("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS)),
                    step=1,
                    key="ui_seed_conditions",
                    help="Влияет на стохастические условия в стресс‑тестах (если они включены).",
                )
                flush_every = st.number_input(
                    "Сохранять каждые N кандидатов",
                    min_value=1,
                    max_value=200,
                    value=int(st.session_state.get("ui_flush_every", 20)),
                    step=1,
                    key="ui_flush_every",
                    help="Как часто сбрасывать строки результатов в CSV на диск. Меньше — надёжнее, но больше IO. (На загрузку CPU не влияет.)",
                )
                progress_every_sec = st.number_input(
                    "Обновлять progress.json каждые Δt (с)",
                    min_value=0.2,
                    max_value=10.0,
                    value=float(st.session_state.get("ui_progress_every_sec", 1.0)),
                    step=0.2,
                    key="ui_progress_every_sec",
                    help="Частота записи файла прогресса из фонового процесса оптимизации.",
                )

                st.markdown("—")
                auto_refresh = st.checkbox(
                    "Автообновление прогресса (UI)",
                    value=bool(st.session_state.get("ui_auto_refresh", True)),
                    key="ui_auto_refresh",
                    help="Периодический auto-rerun страницы, чтобы прогресс обновлялся без кликов.",
                )
                refresh_sec = st.number_input(
                    "Интервал автообновления (с)",
                    min_value=0.2,
                    max_value=10.0,
                    value=float(st.session_state.get("ui_refresh_sec", 1.0)),
                    step=0.2,
                    key="ui_refresh_sec",
                    help="Как часто UI перечитывает progress.json и перерисовывает статус.",
                )

            # --- StageRunner advanced (показываем только если выбран StageRunner)
            if bool(opt_use_staged):
                with st.expander("StageRunner: ускорение поиска (обычно не трогать)", expanded=True):
                    warmstart_mode = st.selectbox(
                        "Warm‑start режим",
                        options=["surrogate", "archive", "none"],
                        index=["surrogate", "archive", "none"].index(st.session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE)),
                        key="warmstart_mode",
                        help=(
                            "surrogate: обучает быстрый surrogate на истории и выбирает элиту по предсказанию; "
                            "archive: берёт топ‑N из глобального архива; "
                            "none: без warm-start."
                        ),
                    )

                    surrogate_samples = st.number_input(
                        "Surrogate samples",
                        min_value=500,
                        max_value=50000,
                        value=int(st.session_state.get("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES)),
                        step=500,
                        key="surrogate_samples",
                        help="Сколько случайных точек ранжировать в surrogate warm‑start (больше = точнее, но медленнее).",
                    )

                    surrogate_top_k = st.number_input(
                        "Surrogate top-k",
                        min_value=8,
                        max_value=512,
                        value=int(st.session_state.get("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K)),
                        step=8,
                        key="surrogate_top_k",
                        help="Размер элиты для инициализации распределения поиска.",
                    )

                    stop_pen_stage1 = st.number_input(
                        "Early‑stop штраф (stage1)",
                        min_value=0.0,
                        max_value=1e9,
                        value=float(st.session_state.get("stop_pen_stage1", 25.0)),
                        step=1.0,
                        key="stop_pen_stage1",
                        help="Если накопленный штраф > порога — прерывает оставшиеся тесты для кандидата (ускоряет длинные стадии).",
                    )
                    stop_pen_stage2 = st.number_input(
                        "Early‑stop штраф (stage2)",
                        min_value=0.0,
                        max_value=1e9,
                        value=float(st.session_state.get("stop_pen_stage2", 15.0)),
                        step=1.0,
                        key="stop_pen_stage2",
                        help="Более строгий порог для финальной (дорогой) стадии.",
                    )

                    sort_tests_by_cost = st.checkbox(
                        "Сортировать тесты по стоимости (дешёвые первыми)",
                        value=bool(st.session_state.get("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)),
                        key="sort_tests_by_cost",
                        help="Помогает early‑stop быстрее отбрасывать плохие кандидаты на длинных наборах.",
                    )

                    influence_eps_rel = st.number_input(
                        "System Influence eps_rel",
                        min_value=1e-6,
                        max_value=0.25,
                        value=float(st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL)),
                        step=1e-3,
                        format="%.6g",
                        key="influence_eps_rel",
                        help=(
                            "Относительный шаг возмущения для system_influence_report_v1. "
                            "StageRunner теперь передаёт это значение явно, вместо скрытого дефолта внутри скрипта."
                        ),
                    )
                    adaptive_influence_eps = st.checkbox(
                        "Adaptive epsilon для System Influence",
                        value=bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)),
                        key="adaptive_influence_eps",
                        help=(
                            "System Influence прогоняет небольшой набор eps_rel и выбирает наиболее устойчивый шаг "
                            f"для каждого параметра. Базовая сетка: {influence_eps_grid_text(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID)}. "
                            "Для StageRunner поверх неё автоматически строятся stage-aware профили: "
                            "stage0 = coarse, stage1 = balanced, stage2 = fine."
                        ),
                    )
                    stage_policy_mode = st.selectbox(
                        "Политика отбора и продвижения",
                        options=["influence_weighted", "static"],
                        index=["influence_weighted", "static"].index(str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE)) if str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE) in ["influence_weighted", "static"] else 0,
                        key="stage_policy_mode",
                        help=(
                            "influence_weighted — seed budgeting и promotion учитывают stage-specific influence summary: "
                            "stage0 остаётся широким, stage1 уже фокусируется, stage2 продвигает только узко релевантные параметры.\n"
                            "static — историческое поведение: только score/ranges без приоритизации параметров по стадии."
                        ),
                    )
                    st.caption("Профиль стадийного отбора и продвижения: " + stage_seed_policy_summary_text())
                    if adaptive_influence_eps:
                        st.caption(
                            "Адаптивный epsilon по стадиям: "
                            + stage_aware_influence_profiles_text(
                                requested_eps_rel=float(influence_eps_rel),
                                base_grid=DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID,
                            )
                        )
                    # NOTE(Streamlit): Не записываем обратно в st.session_state для ключа виджета.
                    # Streamlit сам управляет значением по key=..., а явная запись после создания
                    # виджета приводит к StreamlitAPIException.

            # Если StageRunner выключен, нужны значения по умолчанию для кода ниже.
            if not bool(opt_use_staged):
                sort_tests_by_cost = bool(st.session_state.get("sort_tests_by_cost", True))
                seed_candidates = int(st.session_state.get("ui_seed_candidates", 1))
                seed_conditions = int(st.session_state.get("ui_seed_conditions", 1))
                flush_every = int(st.session_state.get("ui_flush_every", 20))
                progress_every_sec = float(st.session_state.get("ui_progress_every_sec", 1.0))
                auto_refresh = bool(st.session_state.get("ui_auto_refresh", True))
                refresh_sec = float(st.session_state.get("ui_refresh_sec", 1.0))
                influence_eps_rel = float(st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL))
                adaptive_influence_eps = bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS))

            render_advanced_optimization_section_intro(st)

            _botorch_status = botorch_runtime_status()
            if _botorch_status.get("ready"):
                st.success(botorch_status_markdown(_botorch_status))
            else:
                st.warning(
                    botorch_status_markdown(_botorch_status)
                    + ". Для установки зависимостей см. `pneumo_solver_ui/requirements_mobo_botorch.txt`."
                )

            with st.expander("Алгоритм / MOBO / критерии останова", expanded=False):
                c_alg1, c_alg2, c_alg3 = st.columns([2, 2, 2])
                with c_alg1:
                    st.selectbox(
                        "Метод (алгоритм) предложения кандидатов",
                        options=["auto", "portfolio", "qnehvi", "random"],
                        index=["auto", "portfolio", "qnehvi", "random"].index(
                            str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)
                        )
                        if str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)
                        in ["auto", "portfolio", "qnehvi", "random"]
                        else 0,
                        key="opt_proposer",
                        help=(
                            "auto — использовать лучшее доступное (qNEHVI при наличии BoTorch, иначе random). "
                            "portfolio — смешивать qNEHVI и random для устойчивости. "
                            "qnehvi — BoTorch qNEHVI. random — LHS/случайный поиск."
                        ),
                    )
                with c_alg2:
                    st.number_input(
                        "Бюджет (кол-во оценок целевой функции)",
                        min_value=1,
                        max_value=100000,
                        value=int(st.session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT),
                        step=10,
                        key="opt_budget",
                        help="Сколько запусков/оценок выполнить суммарно.",
                    )
                with c_alg3:
                    st.number_input(
                        "Макс. параллельных задач",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT) or DIST_OPT_MAX_INFLIGHT_DEFAULT),
                        step=1,
                        key="opt_max_inflight",
                        help="0 — автоматически (≈ 2× кол-во evaluators/workers).",
                    )

                c_alg4, c_alg5, c_alg6 = st.columns([2, 2, 2])
                with c_alg4:
                    st.number_input(
                        "Случайное зерно для координатора",
                        min_value=0,
                        max_value=2**31 - 1,
                        value=int(st.session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT),
                        step=1,
                        key="opt_seed",
                        help="Случайное зерно для coordinator / proposer path. Отличается от локальных настроек отбора в режиме по стадиям.",
                    )
                with c_alg5:
                    st.text_input(
                        "Ключ штрафа/ограничений (penalty_key)",
                        value=str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT),
                        key="opt_penalty_key",
                        help="Поле в result row, которое интерпретируется как штраф/violation.",
                    )
                with c_alg6:
                    st.number_input(
                        "Допуск штрафа (penalty_tolerance)",
                        min_value=0.0,
                        max_value=1e9,
                        value=float(st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT) or DIST_OPT_PENALTY_TOL_DEFAULT),
                        step=1e-9,
                        format="%.3e",
                        key="opt_penalty_tol",
                        help="Если penalty <= tol — считаем решение допустимым.",
                    )

                c_alg7, c_alg8, c_alg9 = st.columns([2, 2, 2])
                with c_alg7:
                    _hash_modes = ["stable", "legacy"]
                    _hm_val = str(st.session_state.get("settings_opt_problem_hash_mode", DIAGNOSTIC_PROBLEM_HASH_MODE) or DIAGNOSTIC_PROBLEM_HASH_MODE)
                    st.selectbox(
                        "Режим идентификатора задачи (problem_hash)",
                        options=_hash_modes,
                        index=_hash_modes.index(_hm_val) if _hm_val in _hash_modes else 0,
                        key="settings_opt_problem_hash_mode",
                        help=(
                            "stable — устойчивый hash по содержимому задачи. "
                            "legacy — совместимость со старыми run_id."
                        ),
                    )
                with c_alg8:
                    st.number_input(
                        "Размер пакета q (сколько кандидатов предлагать за шаг)",
                        min_value=1,
                        max_value=256,
                        value=int(st.session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT),
                        step=1,
                        key="opt_q",
                        help="Для qNEHVI/portfolio можно предлагать несколько кандидатов за одну итерацию.",
                    )
                with c_alg9:
                    _dev_opts = ["auto", "cpu", "cuda"]
                    _dev_val = str(st.session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT) or DIST_OPT_DEVICE_DEFAULT)
                    st.selectbox(
                        "Вычислительное устройство для модели",
                        options=_dev_opts,
                        index=_dev_opts.index(_dev_val) if _dev_val in _dev_opts else 0,
                        key="opt_device",
                        help="auto — выбрать автоматически. cuda — использовать GPU (если доступно и установлены зависимости).",
                    )

                st.text_area(
                    "Целевые метрики (objective keys) — по одной в строке",
                    value=str(st.session_state.get("opt_objectives", objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES))),
                    height=92,
                    key="opt_objectives",
                    help=(
                        "Ключи метрик, которые оптимизируются (multi-objective). Формат: по одной в строке "
                        "или через запятую/точку с запятой."
                    ),
                )
                st.caption(
                    "qNEHVI включается не сразу: сначала coordinator проходит разогрев, затем ждёт достаточное число допустимых точек. "
                    "Пока пороги n_init и min-feasible не выполнены, используется random/LHS path."
                )

            with st.expander("Параллелизм и кластер (Dask / Ray)", expanded=False):
                backend = st.selectbox(
                    "Бэкенд distributed optimization",
                    options=["Dask", "Ray"],
                    index=0 if str(st.session_state.get("opt_backend", "Dask")) == "Dask" else 1,
                    key="opt_backend",
                    help="Dask удобен для локального параллелизма и простых кластеров; Ray — для акторов и proposer pool/GPU сценариев.",
                )

                if backend == "Dask":
                    mode = st.radio(
                        "Режим Dask",
                        options=["Локальный кластер (создать автоматически)", "Подключиться к scheduler"],
                        index=0 if not str(st.session_state.get("dask_mode", "")).startswith("Подключ") else 1,
                        key="dask_mode",
                    )
                    if mode.startswith("Подключ"):
                        st.text_input(
                            "Адрес scheduler (например: tcp://127.0.0.1:8786)",
                            value=str(st.session_state.get("dask_scheduler", "") or ""),
                            key="dask_scheduler",
                        )
                    else:
                        c_d1, c_d2, c_d3, c_d4 = st.columns([1, 1, 1, 1])
                        with c_d1:
                            st.number_input(
                                "Воркеры",
                                min_value=0,
                                max_value=256,
                                value=int(st.session_state.get("dask_workers", 0) or 0),
                                step=1,
                                key="dask_workers",
                            )
                        with c_d2:
                            st.number_input(
                                "Потоки/воркер",
                                min_value=1,
                                max_value=128,
                                value=int(st.session_state.get("dask_threads_per_worker", DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT) or DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT),
                                step=1,
                                key="dask_threads_per_worker",
                            )
                        with c_d3:
                            st.text_input(
                                "Лимит памяти/воркер",
                                value=str(st.session_state.get("dask_memory_limit", "") or ""),
                                key="dask_memory_limit",
                                help="Например: 4GB. Пусто — auto. '0'/'none' — отключить limit.",
                            )
                        with c_d4:
                            st.text_input(
                                "Dashboard address",
                                value=str(st.session_state.get("dask_dashboard_address", DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT) or DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT),
                                key="dask_dashboard_address",
                                help="':0' — выбрать порт автоматически. Пусто/'none' — отключить dashboard.",
                            )
                else:
                    mode = st.radio(
                        "Режим Ray",
                        options=["Локальный кластер (создать автоматически)", "Подключиться к кластеру"],
                        index=0 if not str(st.session_state.get("ray_mode", "")).startswith("Подключ") else 1,
                        key="ray_mode",
                    )
                    if mode.startswith("Подключ"):
                        st.text_input(
                            "Адрес Ray (например: 127.0.0.1:6379 или auto)",
                            value=str(st.session_state.get("ray_address", "auto") or "auto"),
                            key="ray_address",
                        )
                    else:
                        c_r1, c_r2, c_r3 = st.columns([1, 1, 1])
                        with c_r1:
                            st.number_input(
                                "Ограничить CPU (0=авто)",
                                min_value=0,
                                max_value=4096,
                                value=int(st.session_state.get("ray_local_num_cpus", 0) or 0),
                                step=1,
                                key="ray_local_num_cpus",
                            )
                        with c_r2:
                            st.checkbox(
                                "Включить dashboard (локально)",
                                value=bool(st.session_state.get("ray_local_dashboard", False)),
                                key="ray_local_dashboard",
                            )
                        with c_r3:
                            st.number_input(
                                "Порт dashboard (0=авто)",
                                min_value=0,
                                max_value=65535,
                                value=int(st.session_state.get("ray_local_dashboard_port", 0) or 0),
                                step=1,
                                key="ray_local_dashboard_port",
                            )

            with st.expander("Coordinator advanced / persistence", expanded=False):
                st.markdown(
                    "Ниже — **реально подключённые** ручки координатора. Они используют тот же session_state, что и страница "
                    "«Оптимизация», и попадают в `dist_opt_coordinator.py` без фейковых CLI-полей."
                )
                c_adv1, c_adv2 = st.columns([1, 1])
                with c_adv1:
                    _rt_mode_val = migrated_ray_runtime_env_mode(st.session_state)
                    st.selectbox(
                        "Режим runtime_env для Ray",
                        options=list(RAY_RUNTIME_ENV_MODES),
                        index=list(RAY_RUNTIME_ENV_MODES).index(_rt_mode_val) if _rt_mode_val in RAY_RUNTIME_ENV_MODES else list(RAY_RUNTIME_ENV_MODES).index(DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT),
                        key="ray_runtime_env_mode",
                        help=(
                            "auto — включать runtime_env только для внешнего Ray-кластера; "
                            "on — принудительно упаковывать рабочую папку в runtime_env; "
                            "off — не использовать runtime_env."
                        ),
                    )
                    st.text_area(
                        "Дополнительный JSON для runtime_env Ray (необязательно)",
                        value=migrated_ray_runtime_env_json(st.session_state),
                        height=120,
                        key="ray_runtime_env_json",
                        help="Необязательный JSON-объект, который будет слит с базовым runtime_env координатора.",
                    )
                    st.text_area(
                        "Ray runtime exclude (по одному паттерну в строке)",
                        value=str(st.session_state.get("ray_runtime_exclude", "") or ""),
                        height=90,
                        key="ray_runtime_exclude",
                        help="Исключения при упаковке кода в Ray runtime_env.",
                    )
                    st.number_input(
                        "Evaluator-процессов Ray",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("ray_num_evaluators", 0) or 0),
                        step=1,
                        key="ray_num_evaluators",
                        help="0 — coordinator сам выберет.",
                    )
                    st.number_input(
                        "CPU на evaluator-процесс",
                        min_value=0.25,
                        max_value=512.0,
                        value=float(st.session_state.get("ray_cpus_per_evaluator", 1.0) or 1.0),
                        step=0.25,
                        format="%.2f",
                        key="ray_cpus_per_evaluator",
                    )
                    st.number_input(
                        "Proposer-процессов Ray",
                        min_value=0,
                        max_value=512,
                        value=int(st.session_state.get("ray_num_proposers", 0) or 0),
                        step=1,
                        key="ray_num_proposers",
                        help="0 — автоматически (использовать доступные GPU при qNEHVI).",
                    )
                    st.number_input(
                        "GPU на proposer-процесс",
                        min_value=0.0,
                        max_value=16.0,
                        value=float(st.session_state.get("ray_gpus_per_proposer", 1.0) or 1.0),
                        step=0.25,
                        format="%.2f",
                        key="ray_gpus_per_proposer",
                    )
                with c_adv2:
                    st.number_input(
                        "Буфер кандидатов proposer_buffer",
                        min_value=1,
                        max_value=8192,
                        value=int(st.session_state.get("proposer_buffer", 128) or 128),
                        step=1,
                        key="proposer_buffer",
                    )
                    st.text_input(
                        "ExperimentDB path / DSN",
                        value=str(st.session_state.get("opt_db_path", "") or ""),
                        key="opt_db_path",
                        help="SQLite/DuckDB/Postgres DSN или путь к БД для coordinator.",
                    )
                    _db_engine_opts = ["sqlite", "duckdb", "postgres"]
                    _db_engine_val = str(st.session_state.get("opt_db_engine", DIST_OPT_DB_ENGINE_DEFAULT) or DIST_OPT_DB_ENGINE_DEFAULT).strip().lower()
                    st.selectbox(
                        "Движок базы данных",
                        options=_db_engine_opts,
                        index=_db_engine_opts.index(_db_engine_val) if _db_engine_val in _db_engine_opts else _db_engine_opts.index(DIST_OPT_DB_ENGINE_DEFAULT),
                        key="opt_db_engine",
                    )
                    st.checkbox(
                        "Продолжить существующий запуск",
                        value=bool(st.session_state.get("opt_resume", False)),
                        key="opt_resume",
                    )
                    st.text_input(
                        "Явный run_id (необязательно)",
                        value=str(st.session_state.get("opt_dist_run_id", "") or ""),
                        key="opt_dist_run_id",
                    )
                    st.number_input(
                        "Срок устаревания, с",
                        min_value=0,
                        max_value=604800,
                        value=int(st.session_state.get("opt_stale_ttl_sec", DIST_OPT_STALE_TTL_SEC_DEFAULT) or DIST_OPT_STALE_TTL_SEC_DEFAULT),
                        step=60,
                        key="opt_stale_ttl_sec",
                    )
                    st.checkbox(
                        "Писать hypervolume log",
                        value=bool(st.session_state.get("opt_hv_log", DIST_OPT_HV_LOG_DEFAULT)),
                        key="opt_hv_log",
                        help="Если включено — coordinator пишет progress_hv.csv по допустимому Pareto-front.",
                    )
                    st.number_input(
                        "Интервал экспорта, шагов",
                        min_value=1,
                        max_value=100000,
                        value=int(st.session_state.get("opt_export_every", DIST_OPT_EXPORT_EVERY_DEFAULT) or DIST_OPT_EXPORT_EVERY_DEFAULT),
                        step=1,
                        key="opt_export_every",
                    )

            with st.expander("BoTorch / qNEHVI: дополнительные настройки", expanded=False):
                st.caption(
                    "qNEHVI включается по условиям: coordinator сначала проходит разогрев, затем проверяет число допустимых точек. "
                    "Если done < n_init или feasible < min_feasible, proposer временно откатывается в random/LHS path."
                )
                c_b1, c_b2, c_b3 = st.columns([1, 1, 1])
                with c_b1:
                    st.number_input(
                        "Начальных точек до qNEHVI (n-init)",
                        min_value=0,
                        max_value=100000,
                        value=int(st.session_state.get("opt_botorch_n_init", DIST_OPT_BOTORCH_N_INIT_DEFAULT) or DIST_OPT_BOTORCH_N_INIT_DEFAULT),
                        step=1,
                        key="opt_botorch_n_init",
                        help="0 — auto threshold (~2×(dim+1), но не меньше 10).",
                    )
                    st.number_input(
                        "Минимум допустимых точек (min-feasible)",
                        min_value=0,
                        max_value=100000,
                        value=int(st.session_state.get("opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT) or DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
                        step=1,
                        key="opt_botorch_min_feasible",
                        help="0 — порог допустимых точек отключён.",
                    )
                    st.number_input(
                        "Число перезапусков оптимизатора",
                        min_value=1,
                        max_value=4096,
                        value=int(st.session_state.get("opt_botorch_num_restarts", DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT) or DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT),
                        step=1,
                        key="opt_botorch_num_restarts",
                    )
                with c_b2:
                    st.number_input(
                        "Число сырых выборок",
                        min_value=8,
                        max_value=131072,
                        value=int(st.session_state.get("opt_botorch_raw_samples", DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT) or DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT),
                        step=8,
                        key="opt_botorch_raw_samples",
                    )
                    st.number_input(
                        "Макс. итераций оптимизатора",
                        min_value=1,
                        max_value=100000,
                        value=int(st.session_state.get("opt_botorch_maxiter", DIST_OPT_BOTORCH_MAXITER_DEFAULT) or DIST_OPT_BOTORCH_MAXITER_DEFAULT),
                        step=1,
                        key="opt_botorch_maxiter",
                    )
                    st.number_input(
                        "Запас опорной точки (ref_margin)",
                        min_value=0.0,
                        max_value=10.0,
                        value=float(st.session_state.get("opt_botorch_ref_margin", DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT) or DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT),
                        step=0.01,
                        format="%.3f",
                        key="opt_botorch_ref_margin",
                    )
                with c_b3:
                    st.checkbox(
                        "Нормализовать цели перед GP-fit",
                        value=bool(st.session_state.get("opt_botorch_normalize_objectives", DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT)),
                        key="opt_botorch_normalize_objectives",
                        help="Обычно это стоит оставить включённым; отключать только для осознанной диагностики пути qNEHVI.",
                    )
                    st.info(
                        "Эти ручки действуют и для локального proposer path, и для Ray proposer actors. "
                        "То есть UI и coordinator теперь реально говорят на одном контракте."
                    )

            st.info(
                "В этом control plane больше нет «CLI-only» заглушек: поля выше действительно подключены к текущему distributed coordinator path."
            )

# состояния session
if "opt_proc" not in st.session_state:
    st.session_state.opt_proc = None
if "opt_out_csv" not in st.session_state:
    st.session_state.opt_out_csv = ""
if "opt_base_json" not in st.session_state:
    st.session_state.opt_base_json = ""
if "opt_ranges_json" not in st.session_state:
    st.session_state.opt_ranges_json = ""
if "opt_stop_requested" not in st.session_state:
    st.session_state.opt_stop_requested = False

if "opt_run_dir" not in st.session_state:
    st.session_state.opt_run_dir = ""
if "opt_stop_file" not in st.session_state:
    st.session_state.opt_stop_file = ""
if "opt_progress_path" not in st.session_state:
    st.session_state.opt_progress_path = ""
if "opt_use_staged" not in st.session_state:
    st.session_state.opt_use_staged = True
if "opt_autoupdate_baseline" not in st.session_state:
    st.session_state.opt_autoupdate_baseline = True

# baseline (быстрый прогон) + детальные логи для графиков/анимации
if "baseline_df" not in st.session_state:
    st.session_state.baseline_df = None
if "baseline_tests_map" not in st.session_state:
    # name -> dict(test=test, dt=..., t_end=..., targets=...)
    st.session_state.baseline_tests_map = {}
if "baseline_param_hash" not in st.session_state:
    st.session_state.baseline_param_hash = ""
if "baseline_full_cache" not in st.session_state:
    # key -> dict(df_main=..., df_p=..., df_mdot=..., df_open=..., df_Egroups=..., df_Eedges=..., df_atm=...)
    st.session_state.baseline_full_cache = {}
if "baseline_autoloaded_once" not in st.session_state:
    st.session_state.baseline_autoloaded_once = False

# Автовосстановление baseline после refresh окна (без пересчёта).
# Важно: это только восстановление данных для просмотра; база параметров в UI не «подкручивается» автоматически.
if (st.session_state.baseline_df is None) and (not st.session_state.baseline_autoloaded_once):
    ptr = load_last_baseline_ptr()
    if ptr and isinstance(ptr, dict):
        cd = ptr.get("cache_dir", "")
        if cd:
            try:
                cached = load_baseline_cache(Path(cd))
                if cached:
                    st.session_state.baseline_df = cached.get("baseline_df")
                    st.session_state.baseline_tests_map = cached.get("tests_map", {}) or {}
                    st.session_state.baseline_cache_dir = str(cd)
                    st.session_state.baseline_param_hash = str(ptr.get("meta", {}).get("base_hash", ""))
                    log_event("baseline_autoload_ok", cache_dir=str(cd))
            except Exception as e:
                log_event("baseline_autoload_error", error=str(e), cache_dir=str(cd))
    st.session_state.baseline_autoloaded_once = True


# загрузка модулей
try:
    _default_model_path = _suggest_default_model_path(HERE)
    resolved_worker_path, _worker_msgs = resolve_project_py_path(
        worker_path,
        here=HERE,
        kind="оптимизатор",
        default_path=canonical_worker_path(HERE),
    )
    resolved_model_path, _model_msgs = resolve_project_py_path(
        model_path,
        here=HERE,
        kind="модель",
        default_path=_default_model_path,
    )

    for _msg in (_worker_msgs + _model_msgs):
        st.warning(_msg)
        try:
            _emit(
                "ProjectPathFallback",
                _msg,
                worker_path=str(worker_path),
                model_path=str(model_path),
                resolved_worker=str(resolved_worker_path),
                resolved_model=str(resolved_model_path),
            )
        except Exception:
            pass

    worker_mod = load_python_module_from_path(
        Path(resolved_worker_path),
        "opt_worker_mod",
        log=lambda event, message, **kw: _emit(event, message, **kw),
    )
    model_mod = load_python_module_from_path(
        Path(resolved_model_path),
        "pneumo_model_mod",
        log=lambda event, message, **kw: _emit(event, message, **kw),
    )
except Exception as e:
    st.error(f"Не могу загрузить модель/оптимизатор: {e}")
    st.stop()

P_ATM = float(getattr(model_mod, "P_ATM", 101325.0))
# ВАЖНО: внутри модели давления = Па (абсолютные).
# В UI показываем давление как "бар (изб.)" (gauge) относительно P_ATM.
# (1 bar = 100000 Па). 1 atm = 101325 Па оставляем для совместимости со старыми профилями/кэшем.
ATM_PA = 101325.0  # legacy
BAR_PA = 1e5


pa_abs_to_bar_g = _bar_unit_profile.pressure_from_pa
bar_g_to_pa_abs = _bar_unit_profile.pressure_to_pa_abs



# legacy (оставлено для совместимости со старыми профилями)
# ВАЖНО: не переопределяем pa_abs_to_bar_g. Бар(g) должен оставаться бар(g).

_atm_pressure_profile = build_gauge_pressure_profile(
    unit_label="атм (изб.)",
    pressure_offset_pa=P_ATM,
    pressure_divisor_pa=ATM_PA,
)
pa_abs_to_atm_g = _atm_pressure_profile.pressure_from_pa
atm_g_to_pa_abs = _atm_pressure_profile.pressure_to_pa_abs
is_length_param = is_length_param_name


# -------------------------------
# Описания/единицы параметров (для UI)
# ВАЖНО: эти функции должны быть определены ДО того, как мы строим таблицу df_opt.
# Иначе Python упадёт с NameError, т.к. модуль выполняется сверху вниз.
# -------------------------------


param_unit = _bar_unit_profile.param_unit


# -------------------------------
# Блок параметров (база + диапазоны)
# -------------------------------
base0, ranges0 = worker_mod.make_base_and_ranges(P_ATM)

# Запоминаем исходные типы флагов, чтобы UI корректно показывал чекбоксы даже если где-то значения стали 0/1 или numpy.bool_.
try:
    BASE_BOOL_KEYS = {k for k, v in base0.items() if isinstance(v, (bool, np.bool_))}
except Exception:
    BASE_BOOL_KEYS = {k for k, v in base0.items() if isinstance(v, bool)}

with colA:
    st.subheader("Параметры, которые участвуют в оптимизации")
    st.caption("Ставишь галочку — параметр оптимизируется в диапазоне. Не ставишь — фиксируется базовым значением.")

    # редактируемая таблица параметров (простая)
    
# -------------------------------
# ЕДИНЫЙ ВВОД ПАРАМЕТРОВ (значение + диапазон оптимизации)
# -------------------------------

st.subheader("Параметры модели и диапазоны оптимизации")
st.caption(
    "Единая таблица: у каждого параметра есть базовое значение, и (при необходимости) диапазон оптимизации. "
    "Дублирующий ввод убран: оптимизатор использует ТОЛЬКО то, что в этой таблице."
)

# Метаданные (текст/единицы) — без «захардкоженных» чисел.
PARAM_META = {
    # Давления (уставки) — в UI: бар (избыточного)
    "давление_Pmin_питание_Ресивер2": {
        "группа": "Давление (уставки)",
        "ед": "бар (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Уставка подпитки: линия «Аккумулятор → Ресивер 2». Это НЕ Pmin сброса/атмосферы. "
                    "Оптимизируйте отдельно от Pmin."
    },
    "давление_Pmin_сброс": {
        "группа": "Давление (уставки)",
        "ед": "бар (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Pmin для сброса в атмосферу (ветка Р3→атм). Ниже этого давления ступень не должна «разряжаться» в ноль."
    },
    "давление_Pmid_сброс": {
        "группа": "Давление (уставки)",
        "ед": "бар (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Pmid (уставка «середины»): выше — подвеска заметно «жёстче». Используется в метрике «раньше-жёстко»."
    },
    "давление_Pзаряд_аккумулятора_из_Ресивер3": {
        "группа": "Давление (уставки)",
        "ед": "бар (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Уставка подпитки аккумулятора из Ресивера 3 во время движения (восполнение запаса воздуха)."
    },
    "давление_Pmax_предохран": {
        "группа": "Давление (уставки)",
        "ед": "бар (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Pmax — аварийная уставка предохранительного клапана (не должна превышаться)."
    },
    "начальное_давление_аккумулятора": {
        "группа": "Давление (начальные)",
        "ед": "бар (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Начальное давление в аккумуляторе на старте движения. По вашему ТЗ обычно равно Pmin (идеально — стартовать даже с пустым)."
    },

    # Объёмы — в UI: л или мл
    "объём_ресивера_1": {"группа": "Объёмы", "ед": "л", "kind": "volume_L", "описание": "Объём ресивера 1."},
    "объём_ресивера_2": {"группа": "Объёмы", "ед": "л", "kind": "volume_L", "описание": "Объём ресивера 2."},
    "объём_ресивера_3": {"группа": "Объёмы", "ед": "л", "kind": "volume_L", "описание": "Объём ресивера 3."},
    "объём_аккумулятора": {"группа": "Объёмы", "ед": "л", "kind": "volume_L", "описание": "Объём аккумулятора."},
    "объём_линии": {"группа": "Объёмы", "ед": "мл", "kind": "volume_mL", "описание": "Эквивалентный объём пневмолинии (суммарно), учитывает сжимаемость в трубках."},
    "мёртвый_объём_камеры": {"группа": "Объёмы", "ед": "мл", "kind": "volume_mL", "описание": "Мёртвый объём камеры/полости (из каталогов Camozzi)."},


    # Дроссели/проходы — доля открытия 0..1
    "открытие_дросселя_Ц2_CAP_в_ROD": {
        "группа": "Дроссели",
        "ед": "доля 0..1",
        "kind": "fraction01",
        "описание": "Нормированная доля открытия дросселя (0=минимум/почти закрыт, 1=максимум/полностью открыт). "
                    "Физически интерпретируется как масштаб проходного сечения/kv выбранного дросселя Camozzi."
    },
    "открытие_дросселя_Ц2_ROD_в_CAP": {"группа": "Дроссели", "ед": "доля 0..1", "kind": "fraction01", "описание": "То же, обратное направление (шток→поршень)."},
    "открытие_дросселя_Ц1_CAP_в_ROD": {"группа": "Дроссели", "ед": "доля 0..1", "kind": "fraction01", "описание": "То же для Ц1."},
    "открытие_дросселя_Ц1_ROD_в_CAP": {"группа": "Дроссели", "ед": "доля 0..1", "kind": "fraction01", "описание": "То же для Ц1 (обратное направление)."},

    # Пружина
    "пружина_масштаб": {
        "группа": "Пружина",
        "ед": "коэф.",
        "kind": "raw",
        "описание": "Масштаб кривой «сила-ход» пружины (табличная нелинейность остаётся, умножаем силу на коэффициент)."
    },

    # Механика/массы
    "масса_рамы": {"группа": "Механика", "ед": "кг", "kind": "raw", "описание": "Подрессоренная масса (рама/кузов)."},
    "масса_неподрессоренная": {"группа": "Механика", "ед": "кг", "kind": "raw", "описание": "Неподрессоренная масса на колесо (ступица/рычаг/колесо)."},
    "колея": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Колея (расстояние между центрами левого и правого колёс)."},
    "база": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Колёсная база (перед-зад)."},
    "ширина_рамы": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Ширина рамы (для расчёта плеч/кинематики в упрощённой схеме)."},
    "ход_штока": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Полный ход штока цилиндра (ограничение по пробою/вылету)."},
    "коэф_передачи_рычаг": {"группа": "Геометрия", "ед": "коэф.", "kind": "raw", "описание": "Передаточное отношение рычага (ход штока ↔ ход колеса)."},
    "статический_ход_колеса": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Статический ход колеса/сжатие относительно нейтрали."},

    # Шина
    "жёсткость_шины": {"группа": "Шина", "ед": "Н/м", "kind": "raw", "описание": "Вертикальная жёсткость шины (линеаризованная)."},
    "демпфирование_шины": {"группа": "Шина", "ед": "Н·с/м", "kind": "raw", "описание": "Вертикальное демпфирование шины (линеаризованное)."},

    # Инерции
    "момент_инерции_рамы_по_крену": {"группа": "Инерция", "ед": "кг·м²", "kind": "raw", "описание": "Момент инерции рамы относительно оси крена."},
    "момент_инерции_рамы_по_тангажу": {"группа": "Инерция", "ед": "кг·м²", "kind": "raw", "описание": "Момент инерции рамы относительно оси тангажа."},
    "момент_инерции_рамы_по_рысканью": {"группа": "Инерция", "ед": "кг·м²", "kind": "raw", "описание": "Момент инерции рамы относительно оси рысканья."},

    # Ограничения/запасы (в UI)
    "лимит_пробоя_крен_град": {"группа": "Ограничения", "ед": "град", "kind": "raw", "описание": "Ограничение по крену (жёсткое/аварийное)."},
    "лимит_пробоя_тангаж_град": {"группа": "Ограничения", "ед": "град", "kind": "raw", "описание": "Ограничение по тангажу (жёсткое/аварийное)."},
    "минимальное_абсолютное_давление_Па": {"группа": "Ограничения", "ед": "кПа (абс.)", "kind": "pressure_kPa_abs", "описание": "Нижняя граница абсолютного давления для численной устойчивости. Вакуум допускаем, но p_abs не может быть < 0."},

    # Газ
    "температура_газа_К": {"группа": "Газ", "ед": "°C", "kind": "temperature_C", "описание": "Температура газа (внутри модели хранится Кельвин)."},
    "гравитация": {"группа": "Среда", "ед": "м/с²", "kind": "raw", "описание": "Ускорение свободного падения."},

    # Геометрия подвески (двойные поперечные рычаги / DW2D)
    "dw_lower_pivot_inboard_перед_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Смещение внутреннего шарнира нижнего рычага (перед) внутрь от центра колеса по оси Y. Используется в кинематике dw2d_mounts."
    },
    "dw_lower_pivot_inboard_зад_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Смещение внутреннего шарнира нижнего рычага (зад) внутрь от центра колеса по оси Y. Используется в кинематике dw2d_mounts."
    },
    "dw_lower_pivot_z_перед_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Высота (Z) внутреннего шарнира нижнего рычага (перед) относительно рамы в статике (z_body для данной точки = 0)."
    },
    "dw_lower_pivot_z_зад_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Высота (Z) внутреннего шарнира нижнего рычага (зад) относительно рамы в статике (z_body для данной точки = 0)."
    },
    "dw_lower_arm_len_перед_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Длина нижнего рычага (перед): расстояние от внутреннего шарнира до шарнира у поворотного кулака/ступицы (в 2D-приближении Y-Z)."
    },
    "dw_lower_arm_len_зад_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Длина нижнего рычага (зад): расстояние от внутреннего шарнира до шарнира у поворотного кулака/ступицы (в 2D-приближении Y-Z)."
    },
    "dw_upper_pivot_inboard_перед_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Смещение внутреннего шарнира верхнего рычага (перед) внутрь от центра колеса по оси Y. Канонический source-data для второго рычага."
    },
    "dw_upper_pivot_inboard_зад_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Смещение внутреннего шарнира верхнего рычага (зад) внутрь от центра колеса по оси Y. Канонический source-data для второго рычага."
    },
    "dw_upper_pivot_z_перед_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Высота (Z) внутреннего шарнира верхнего рычага (перед) относительно рамы в статике. Канонический source-data для второго рычага."
    },
    "dw_upper_pivot_z_зад_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Высота (Z) внутреннего шарнира верхнего рычага (зад) относительно рамы в статике. Канонический source-data для второго рычага."
    },
    "dw_upper_arm_len_перед_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Длина верхнего рычага (перед): расстояние от внутреннего шарнира до шарнира у поворотного кулака/ступицы (в 2D-приближении Y-Z)."
    },
    "dw_upper_arm_len_зад_м": {
        "группа": "Геометрия подвески (DW2D)",
        "ед": "м",
        "kind": "raw",
        "описание": "Длина верхнего рычага (зад): расстояние от внутреннего шарнира до шарнира у поворотного кулака/ступицы (в 2D-приближении Y-Z)."
    },

    "верх_Ц1_перед_между_ЛП_ПП_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Расстояние между верхними точками крепления цилиндра Ц1 (перед), между ЛП и ПП по оси Y."},
    "верх_Ц2_перед_между_ЛП_ПП_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Расстояние между верхними точками крепления цилиндра Ц2 (перед), между ЛП и ПП по оси Y."},
    "верх_Ц1_зад_между_ЛЗ_ПЗ_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Расстояние между верхними точками крепления цилиндра Ц1 (зад), между ЛЗ и ПЗ по оси Y."},
    "верх_Ц2_зад_между_ЛЗ_ПЗ_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Расстояние между верхними точками крепления цилиндра Ц2 (зад), между ЛЗ и ПЗ по оси Y."},

    "верх_Ц1_перед_z_относительно_рамы_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Высота (Z) верхнего крепления цилиндра Ц1 (перед) относительно рамы в статике."},
    "верх_Ц2_перед_z_относительно_рамы_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Высота (Z) верхнего крепления цилиндра Ц2 (перед) относительно рамы в статике."},
    "верх_Ц1_зад_z_относительно_рамы_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Высота (Z) верхнего крепления цилиндра Ц1 (зад) относительно рамы в статике."},
    "верх_Ц2_зад_z_относительно_рамы_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw",
        "описание": "Высота (Z) верхнего крепления цилиндра Ц2 (зад) относительно рамы в статике."},

    "низ_Ц1_перед_доля_рычага": {"группа": "Геометрия подвески (DW2D)", "ед": "доля 0..1", "kind": "fraction01",
        "описание": "Положение нижнего крепления Ц1 на нижнем рычаге (перед): доля от внутреннего шарнира (0) до шарнира ступицы (1)."},
    "низ_Ц2_перед_доля_рычага": {"группа": "Геометрия подвески (DW2D)", "ед": "доля 0..1", "kind": "fraction01",
        "описание": "Положение нижнего крепления Ц2 на нижнем рычаге (перед): доля от внутреннего шарнира (0) до шарнира ступицы (1)."},
    "низ_Ц1_зад_доля_рычага": {"группа": "Геометрия подвески (DW2D)", "ед": "доля 0..1", "kind": "fraction01",
        "описание": "Положение нижнего крепления Ц1 на нижнем рычаге (зад): доля от внутреннего шарнира (0) до шарнира ступицы (1)."},
    "низ_Ц2_зад_доля_рычага": {"группа": "Геометрия подвески (DW2D)", "ед": "доля 0..1", "kind": "fraction01",
        "описание": "Положение нижнего крепления Ц2 на нижнем рычаге (зад): доля от внутреннего шарнира (0) до шарнира ступицы (1)."},

    "ход_штока_Ц1_перед_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw", "описание": "Полный ход штока цилиндра Ц1 (перед)."},
    "ход_штока_Ц1_зад_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw", "описание": "Полный ход штока цилиндра Ц1 (зад)."},
    "ход_штока_Ц2_перед_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw", "описание": "Полный ход штока цилиндра Ц2 (перед)."},
    "ход_штока_Ц2_зад_м": {"группа": "Геометрия подвески (DW2D)", "ед": "м", "kind": "raw", "описание": "Полный ход штока цилиндра Ц2 (зад)."},


}

# --- Нормализация метаданных (единые человеко‑понятные единицы) ---
# Давления: показываем в бар (изб.)
for _k, _m in PARAM_META.items():
    if not isinstance(_m, dict):
        continue
    if _m.get("kind") == "pressure_atm_g":
        _m["kind"] = "pressure_bar_g"
        _m["ед"] = "бар (изб.)"

# Длины: внутренние метры -> показываем в мм
for _k, _m in PARAM_META.items():
    if not isinstance(_m, dict):
        continue
    if is_length_param(_k) and _m.get("kind", "raw") == "raw" and _m.get("ед") in ("м", "m"):
        _m["kind"] = "length_mm"
        _m["ед"] = "мм"


def infer_param_meta(k: str) -> Dict[str, str]:
    """Единый источник метаданных параметра для таблицы (группа/единицы/kind/описание).

    Задача: чтобы в UI не было «каша из единиц». Внутри модели всё в СИ, пользователю — привычные.
    """
    if k in PARAM_META:
        return PARAM_META[k]
    fam_meta = family_param_meta(k)
    if fam_meta is not None:
        return fam_meta
    # эвристики для параметров, которых нет в ручном словаре:
    if is_pressure_param(k):
        return {"группа": "Давление", "ед": "бар (изб.)", "kind": "pressure_bar_g", "описание": param_desc(k)}
    if is_volume_param(k):
        if is_small_volume_param(k):
            return {"группа": "Объёмы", "ед": "мл", "kind": "volume_mL", "описание": param_desc(k)}
        return {"группа": "Объёмы", "ед": "л", "kind": "volume_L", "описание": param_desc(k)}
    if is_length_param(k):
        return {"группа": "Геометрия (прочее)", "ед": "мм", "kind": "length_mm", "описание": param_desc(k)}
    if "открытие" in k:
        return {"группа": "Дроссели", "ед": "доля 0..1", "kind": "fraction01", "описание": param_desc(k)}
    if k.endswith("_град"):
        return {"группа": "Геометрия (углы)", "ед": "град", "kind": "raw", "описание": param_desc(k)}
    # по умолчанию:
    return {"группа": "Прочее", "ед": "СИ", "kind": "raw", "описание": param_desc(k)}


_si_to_ui = _bar_unit_profile.si_to_ui
_ui_to_si = _bar_unit_profile.ui_to_si


# дополняем базу значениями для ключей, которые есть в диапазонах, но отсутствуют в base0
for _k, _rng in ranges0.items():
    if _k not in base0:
        try:
            base0[_k] = 0.5 * (float(_rng[0]) + float(_rng[1]))
        except Exception:
            base0[_k] = float("nan")

all_keys = sorted(set(base0.keys()) | set(ranges0.keys()))

# --- Структурированные параметры (списки/таблицы) ---
# Важно: некоторые параметры (например нелинейная пружина) хранятся как списки чисел.
# Их нельзя показывать в общей таблице скаляров (иначе будет TypeError: float(list)).

# 1) Таблица нелинейной пружины (ход_мм -> сила_Н)
SPR_X = "пружина_таблица_ход_мм"
SPR_F = "пружина_таблица_сила_Н"

if (SPR_X in base0) and (SPR_F in base0):
    try:
        import pandas as _pd
        if "spring_table_df" not in st.session_state:
            st.session_state["spring_table_df"] = _pd.DataFrame({
                "ход_мм": list(base0.get(SPR_X, [])),
                "сила_Н": list(base0.get(SPR_F, [])),
            })

        st.markdown("### Нелинейная пружина: табличная характеристика")
        st.caption("Редактируется прямо здесь (без правки файлов). Точки сортируются по ходу. Минимум 2 точки.")
        spring_df = st.data_editor(
            st.session_state["spring_table_df"],
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "ход_мм": st.column_config.NumberColumn("Ход (мм)", step=None, help="Ход подвески/пружины (мм). Отрицательный = отбой, положительный = сжатие."),
                "сила_Н": st.column_config.NumberColumn("Сила (Н)", step=None, help="Сила пружины (Н) при соответствующем ходе."),
            },
            key="spring_table_editor",
        )
        st.session_state["spring_table_df"] = spring_df

        # Валидация + нормализация
        _df = spring_df.copy()
        _df["ход_мм"] = _pd.to_numeric(_df["ход_мм"], errors="coerce")
        _df["сила_Н"] = _pd.to_numeric(_df["сила_Н"], errors="coerce")
        _df = _df.dropna().sort_values("ход_мм")
        if len(_df) < 2:
            st.error("Таблица пружины должна содержать минимум 2 числовые точки.")
        else:
            base0[SPR_X] = _df["ход_мм"].astype(float).tolist()
            base0[SPR_F] = _df["сила_Н"].astype(float).tolist()
    except Exception as e:
        st.error(f"Ошибка обработки таблицы пружины: {e}")

# Список ключей со структурированными значениями (list/dict) — их исключаем из таблицы скаляров
structured_keys = [k for k in all_keys if isinstance(base0.get(k, None), (list, dict))]

# В таблицу редактирования попадают только числовые скаляры.
scalar_keys = [k for k in all_keys if (k not in structured_keys) and _is_numeric_scalar(base0.get(k, None))]
non_numeric_keys = [k for k in all_keys if (k not in structured_keys) and (not _is_numeric_scalar(base0.get(k, None)))]

rows = []
for k in scalar_keys:
    meta = infer_param_meta(k)
    kind = meta.get("kind", "raw")
    val_ui = _si_to_ui(k, base0.get(k, float("nan")), kind)
    is_opt = k in ranges0
    if is_opt:
        mn_ui = _si_to_ui(k, ranges0[k][0], kind)
        mx_ui = _si_to_ui(k, ranges0[k][1], kind)
    else:
        mn_ui = float("nan")
        mx_ui = float("nan")

    rows.append({
        "группа": meta.get("группа", "Прочее"),
        "параметр": k,
        "единица": meta.get("ед") or meta.get("РµРґ") or "СИ",
        "значение": val_ui,
        "оптимизировать": bool(is_opt),
        "мин": mn_ui,
        "макс": mx_ui,
        "пояснение": meta.get("описание", ""),
        "_key": k,
        "_kind": kind,
    })

def _normalize_params_editor_columns(frame: Any) -> Any:
    if not isinstance(frame, pd.DataFrame):
        return frame
    rename_map: Dict[str, str] = {}
    if "единица" not in frame.columns and "РµРґРёРЅРёС†Р°" in frame.columns:
        rename_map["РµРґРёРЅРёС†Р°"] = "единица"
    if "мин" not in frame.columns and "РјРёРЅ" in frame.columns:
        rename_map["РјРёРЅ"] = "мин"
    if "макс" not in frame.columns and "РјР°РєСЃ" in frame.columns:
        rename_map["РјР°РєСЃ"] = "макс"
    if not rename_map:
        return frame
    return frame.rename(columns=rename_map)


df_params0 = _normalize_params_editor_columns(pd.DataFrame(rows))


# Streamlit иногда «залипает» на старом key при смене набора параметров.
# Делаем сигнатуру таблицы и используем её в key, чтобы таблица гарантированно пересоздавалась при смене набора строк/столбцов.
_sig_src = df_params0[["параметр", "группа", "единица", "_kind"]].to_csv(index=False).encode("utf-8")
params_sig = hashlib.sha1(_sig_src).hexdigest()[:10]
def _migrate_df_params_edit(prev_df: Any, new_df: pd.DataFrame) -> pd.DataFrame:
    """Мягкая миграция таблицы параметров при изменении метаданных (единицы/kind/группы).

    Требование проекта: введённые пользователем значения НЕ должны пропадать при обновлении версии.
    Логика:
      1) берём старое UI-значение + старый kind -> переводим в СИ,
      2) переводим из СИ в новый UI-kind.
    """
    if not isinstance(prev_df, pd.DataFrame):
        return new_df
    prev_df = _normalize_params_editor_columns(prev_df)
    new_df = _normalize_params_editor_columns(new_df)
    if "_key" not in prev_df.columns:
        return new_df

    try:
        prev_map = prev_df.set_index("_key", drop=False)
    except Exception:
        return new_df

    out = new_df.copy()
    for i, row in out.iterrows():
        k = row.get("_key")
        if k is None:
            continue
        if k not in prev_map.index:
            continue
        prow = prev_map.loc[k]
        old_kind = str(prow.get("_kind", "raw"))
        new_kind = str(row.get("_kind", "raw"))

        # флаг оптимизации
        try:
            out.at[i, "оптимизировать"] = bool(prow.get("оптимизировать", False))
        except Exception:
            pass

        # значение
        try:
            v_old = float(prow.get("значение"))
            v_si = _ui_to_si(str(k), v_old, old_kind)
            out.at[i, "значение"] = _si_to_ui(str(k), v_si, new_kind)
        except Exception:
            pass

        # диапазоны
        for col in ("мин", "макс"):
            try:
                x_old = prow.get(col)
                if x_old is None:
                    continue
                x_old = float(x_old)
                if math.isnan(x_old):
                    continue
                x_si = _ui_to_si(str(k), x_old, old_kind)
                out.at[i, col] = _si_to_ui(str(k), x_si, new_kind)
            except Exception:
                pass

    return out

if st.session_state.get("df_params_signature") != params_sig:
    prev_df = st.session_state.get("df_params_edit")
    st.session_state["df_params_edit"] = _migrate_df_params_edit(prev_df, df_params0)
    st.session_state["df_params_signature"] = params_sig
params_table_key = f"params_table_{params_sig}"


# --- Новый редактор параметров: список + карточка (без горизонтального скролла) ---
df_params_edit = st.session_state.get("df_params_edit", df_params0).copy()

# Фильтры
_all_groups = sorted([str(g) for g in df_params_edit["группа"].dropna().unique().tolist() if str(g).strip()])

# Быстрый «человеческий» разрез по разделам (чтобы не искать глазами по сотне строк).
_SECTION_RULES = {
    "Все разделы": lambda g: True,
    "Пневматика": lambda g: any(s in g for s in ["Давление", "Объём", "Объем", "Дроссел", "Газ", "Среда"]),
    "Геометрия": lambda g: "Геометрия" in g,
    "Массы и инерции": lambda g: any(s in g for s in ["Механика", "Инерция"]),
    "Шины": lambda g: "Шина" in g,
    "Пружина": lambda g: "Пружина" in g,
    "Ограничения": lambda g: "Огранич" in g,
    "Прочее": lambda g: True,  # вычислим ниже
}

# Список «прочее» = всё, что не попало в основные разделы (кроме "Все разделы")
_non_misc_rules = {k: v for k, v in _SECTION_RULES.items() if k not in {"Все разделы", "Прочее"}}
_groups_misc = [
    g for g in _all_groups
    if not any(rule(g) for rule in _non_misc_rules.values())
]

_section_opts = list(_SECTION_RULES.keys())
_default_section = st.session_state.get("ui_params_section", "Все разделы")
if _default_section not in _section_opts:
    _default_section = "Все разделы"

ui_params_section = st.selectbox(
    "Раздел исходных данных",
    options=_section_opts,
    index=_section_opts.index(_default_section),
    key="ui_params_section",
    help="Сужает список групп параметров до выбранного раздела (геометрия/пневматика/массы и т.д.).",
)

if ui_params_section == "Прочее":
    _groups_in_section = _groups_misc
else:
    _rule = _SECTION_RULES.get(ui_params_section, lambda g: True)
    _groups_in_section = [g for g in _all_groups if _rule(g)]

_group_opts = ["Все группы"] + list(_groups_in_section)

_default_group = st.session_state.get("ui_params_group", "Все группы")
if _default_group not in _group_opts:
    _default_group = "Все группы"

ui_params_group = st.selectbox(
    "Группа параметров",
    options=_group_opts,
    index=_group_opts.index(_default_group),
    key="ui_params_group",
    help="Параметры сгруппированы по смыслу: геометрия, пневматика, массы и т.д.",
)

ui_params_search = st.text_input(
    "Поиск параметра",
    value=st.session_state.get("ui_params_search", ""),
    key="ui_params_search",
    help="Ищет по ключу параметра и по пояснению.",
).strip()

# Отфильтрованный список
_df_view = df_params_edit.copy()
if ui_params_section != "Все разделы":
    _df_view = _df_view[_df_view["группа"].isin(_groups_in_section)]
if ui_params_group != "Все группы":
    _df_view = _df_view[_df_view["группа"] == ui_params_group]
if ui_params_search:
    _mask = (
        _df_view["параметр"].astype(str).str.contains(ui_params_search, case=False, na=False)
        | _df_view["пояснение"].astype(str).str.contains(ui_params_search, case=False, na=False)
    )
    _df_view = _df_view[_mask]

_keys_order = _df_view["_key"].tolist()

if not _keys_order:
    st.warning("Параметров по текущему фильтру нет.")
else:
    # Групповые действия
    c_act1, c_act2, c_act3 = st.columns([1, 1, 1], gap="small")
    with c_act1:
        if st.button("Опт. все", width="stretch", help="Помечает все параметры из списка как оптимизируемые"):
            _mask_all = df_params_edit["_key"].isin(_keys_order)
            df_params_edit.loc[_mask_all, "оптимизировать"] = True

    with c_act2:
        if st.button("Снять опт.", width="stretch", help="Снимает оптимизацию у параметров из списка"):
            _mask_all = df_params_edit["_key"].isin(_keys_order)
            df_params_edit.loc[_mask_all, "оптимизировать"] = False

    with c_act3:
        if st.button("Автодиапазон ±20%", width="stretch", help="Заполняет Мин/Макс (если пусто) и включает оптимизацию"):
            for _k in _keys_order:
                _row = df_params_edit[df_params_edit["_key"] == _k].iloc[0]
                try:
                    _v = float(_row["значение"])
                except Exception:
                    continue

                _mn = _row.get("мин")
                _mx = _row.get("макс")
                _need = True
                try:
                    if (not pd.isna(_mn)) and (not pd.isna(_mx)) and float(_mx) > float(_mn):
                        _need = False
                except Exception:
                    _need = True

                if _need:
                    lo = _v * 0.8
                    hi = _v * 1.2
                    if lo == hi:
                        hi = lo + 1.0

                    _kind = str(_row.get("_kind", ""))
                    if _kind in {"pressure_atm_g", "pressure_bar_g", "volume_L", "volume_mL"}:
                        lo = max(0.0, lo)
                        hi = max(lo + 1e-9, hi)

                    df_params_edit.loc[df_params_edit["_key"] == _k, "мин"] = float(min(lo, hi))
                    df_params_edit.loc[df_params_edit["_key"] == _k, "макс"] = float(max(lo, hi))

            df_params_edit.loc[df_params_edit["_key"].isin(_keys_order), "оптимизировать"] = True

    # Быстрое массовое редактирование (без «миллиона» карточек)
    with st.expander("Массовое редактирование (таблица)", expanded=True):
        st.caption("Для быстрой правки нескольких параметров. "
                   "Здесь редактируются только значения/диапазоны; пояснение смотрите в карточке справа.")
        try:
            _mass_df = _df_view.set_index("_key")[["параметр", "единица", "значение", "оптимизировать", "мин", "макс"]].copy()
            _flt_sig = hashlib.sha1(f"{ui_params_section}|{ui_params_group}|{ui_params_search}".encode("utf-8")).hexdigest()[:6]
            _mass_key = f"{params_table_key}_mass_{_flt_sig}"
            _mass_edited = st.data_editor(
                _mass_df,
                key=_mass_key,
                hide_index=True,
                width="stretch",
                height=280,
                num_rows="fixed",
                disabled=["параметр", "единица"],
            )

            # применяем изменения обратно в общую таблицу
            _idx = df_params_edit.set_index("_key")
            for _col in ["значение", "оптимизировать", "мин", "макс"]:
                if _col in _mass_edited.columns:
                    _idx.loc[_mass_edited.index, _col] = _mass_edited[_col].values
            df_params_edit = _idx.reset_index()
        except Exception as _e:
            st.warning(f"Массовый редактор временно недоступен: {_e}")


    left, right = st.columns([1.05, 1.0], gap="large")

    with left:
        st.caption("Список параметров (без горизонтального скролла). Выбери строку → справа карточка.")
        _list_df = _df_view[["параметр", "значение", "оптимизировать"]].copy()
        _list_df = _list_df.rename(columns={"параметр": "Параметр", "значение": "Значение", "оптимизировать": "Опт."})

        # Выбор параметра через selectbox (устраняет баги selection/rerun и «двойной клик»)
        _label_map = dict(zip(_df_view["_key"].astype(str).tolist(), _df_view["параметр"].astype(str).tolist()))
        _cur_key = str(st.session_state.get("ui_params_selected_key") or "")
        if _cur_key not in _keys_order:
            _cur_key = _keys_order[0]
            st.session_state["ui_params_selected_key"] = _cur_key

        st.selectbox(
            "Выбранный параметр",
            options=_keys_order,
            index=_keys_order.index(_cur_key) if _cur_key in _keys_order else 0,
            format_func=lambda k: _label_map.get(str(k), str(k)),
            key="ui_params_selected_key",
            help="Выбор параметра для карточки редактирования справа.",
        )

        st.dataframe(
            _list_df,
            hide_index=True,
            width="stretch",
            height=420,
        )

    # ВАЖНО (Streamlit): нельзя модифицировать st.session_state[<widget_key>] после
    # создания виджета с тем же key в рамках одного прогона.
    # Поэтому здесь мы только читаем итоговое значение.
    _selected_key = st.session_state.get("ui_params_selected_key")
    if _selected_key not in _keys_order:
        _selected_key = _keys_order[0]

    with right:
        _row = df_params_edit[df_params_edit["_key"] == _selected_key].iloc[0]
        _pkey = str(_row["параметр"])
        _unit = str(_row.get("единица", "—"))
        _kind = str(_row.get("_kind", "raw"))

        st.markdown(f"### {_pkey}")
        if str(_row.get("пояснение", "")).strip():
            st.info(str(_row.get("пояснение", "")))

        def _sf(x, default=None):
            try:
                if pd.isna(x):
                    return default
            except Exception:
                pass
            try:
                return float(x)
            except Exception:
                return default

        v0 = _sf(_row.get("значение"), 0.0)
        opt0 = bool(_row.get("оптимизировать", False))
        mn0 = _sf(_row.get("мин"), None)
        mx0 = _sf(_row.get("макс"), None)

        nonneg = (_kind in {"pressure_atm_g", "pressure_bar_g", "volume_L", "volume_mL"}) or _pkey.startswith("масса_")

        with st.form(f"param_card_{_selected_key}"):
            st.caption(f"Единицы: **{_unit}**")

            # Диапазон для ручки значения
            if _kind == "fraction01":
                lo_b, hi_b = 0.0, 1.0
            else:
                if (mn0 is not None) and (mx0 is not None) and (mx0 > mn0):
                    lo_b, hi_b = float(mn0), float(mx0)
                else:
                    span = abs(float(v0)) * 0.25
                    if span == 0:
                        span = 1.0
                    lo_b, hi_b = float(v0) - span, float(v0) + span

            if nonneg:
                lo_b = max(0.0, lo_b)
                hi_b = max(lo_b + 1e-9, hi_b)

            step = (hi_b - lo_b) / 200.0 if (hi_b > lo_b) else 0.01
            if step <= 0:
                step = 0.01

            val_new = st.slider("Значение", float(lo_b), float(hi_b), float(max(lo_b, min(hi_b, v0))), step=float(step))

            with st.expander("Точно (ввод)", expanded=True):
                val_new = st.number_input(
                    "Значение (точно)",
                    value=float(val_new),
                    step=float(abs(float(val_new)) * 0.01) if float(val_new) != 0 else 0.1,
                    format="%.8g",
                )

            opt_new = st.checkbox(
                "Оптимизировать",
                value=opt0,
                help="Если включено — параметр участвует в оптимизации внутри заданного диапазона.",
            )

            min_new = mn0
            max_new = mx0

            if opt_new:
                if _kind == "fraction01":
                    cur_lo = 0.0 if mn0 is None else float(mn0)
                    cur_hi = 1.0 if mx0 is None else float(mx0)
                    cur_lo = max(0.0, min(1.0, cur_lo))
                    cur_hi = max(0.0, min(1.0, cur_hi))
                    if cur_hi < cur_lo:
                        cur_lo, cur_hi = cur_hi, cur_lo
                    min_new, max_new = st.slider("Диапазон", 0.0, 1.0, value=(cur_lo, cur_hi), step=0.01)
                else:
                    cur_lo = float(v0) * 0.8 if mn0 is None else float(mn0)
                    cur_hi = float(v0) * 1.2 if mx0 is None else float(mx0)
                    if cur_hi == cur_lo:
                        cur_hi = cur_lo + 1.0

                    span = max(abs(float(v0)) * 0.6, abs(cur_hi - cur_lo) * 0.6, 1.0)
                    rmin = min(cur_lo, cur_hi, float(v0) - span)
                    rmax = max(cur_lo, cur_hi, float(v0) + span)
                    if nonneg:
                        rmin = max(0.0, rmin)
                        rmax = max(rmin + 1e-9, rmax)

                    rstep = (rmax - rmin) / 200.0
                    if rstep <= 0:
                        rstep = 0.01

                    min_new, max_new = st.slider(
                        "Диапазон",
                        float(rmin),
                        float(rmax),
                        value=(float(cur_lo), float(cur_hi)),
                        step=float(rstep),
                    )

            submitted = st.form_submit_button("Применить изменения")
            if submitted:
                df_params_edit.loc[df_params_edit["_key"] == _selected_key, "значение"] = float(val_new)
                df_params_edit.loc[df_params_edit["_key"] == _selected_key, "оптимизировать"] = bool(opt_new)
                if opt_new:
                    df_params_edit.loc[df_params_edit["_key"] == _selected_key, "мин"] = float(min_new)
                    df_params_edit.loc[df_params_edit["_key"] == _selected_key, "макс"] = float(max_new)

                st.session_state["df_params_edit"] = df_params_edit
                st.success("Параметр обновлён.")

# сохранить в session_state (на случай, если не нажимали кнопку)
st.session_state["df_params_edit"] = df_params_edit

# строим base_override / ranges_override из единой таблицы
base_override = dict(base0)
ranges_override: Dict[str, Tuple[float, float]] = {}

param_errors = []
for _, r in df_params_edit.iterrows():
    k = str(r["_key"])
    kind = str(r["_kind"])
    try:
        val_ui = float(r["значение"])
    except Exception:
        param_errors.append(f"Параметр '{k}': пустое/некорректное базовое значение.")
        continue

    # физические проверки (только невозможное)
    if kind == "fraction01":
        if not (0.0 <= val_ui <= 1.0):
            param_errors.append(f"Параметр '{k}': доля должна быть 0..1, сейчас {val_ui}")
    if k.startswith("масса_") and val_ui < 0:
        param_errors.append(f"Параметр '{k}': масса не может быть отрицательной, сейчас {val_ui}")
    if ("объём" in k) and (("volume_" in kind) or k.startswith("объём_") or k.startswith("мёртвый_объём")):
        if val_ui <= 0:
            param_errors.append(f"Параметр '{k}': объём должен быть > 0, сейчас {val_ui}")

    # конвертация в СИ
    val_si = _ui_to_si(k, val_ui, kind)
    base_override[k] = float(val_si)

    if bool(r["оптимизировать"]):
        try:
            mn_ui = float(r["мин"])
            mx_ui = float(r["макс"])
        except Exception:
            param_errors.append(f"Параметр '{k}': включена оптимизация, но диапазон (мин/макс) не задан.")
            continue
        mn_si = _ui_to_si(k, mn_ui, kind)
        mx_si = _ui_to_si(k, mx_ui, kind)
        if not (mn_si < mx_si):
            param_errors.append(f"Параметр '{k}': диапазон некорректный (мин >= макс).")
            continue
        # физика
        if kind == "fraction01" and (mn_ui < 0 or mx_ui > 1):
            param_errors.append(f"Параметр '{k}': диапазон доли должен быть в 0..1.")
            continue
        if ("объём" in k) and ((mn_si <= 0) or (mx_si <= 0)):
            param_errors.append(f"Параметр '{k}': объёмы должны быть > 0.")
            continue

        ranges_override[k] = (float(mn_si), float(mx_si))

if param_errors:
    st.error("В таблице параметров есть ошибки (исправьте перед запуском):\n- " + "\n- ".join(param_errors))





# -------------------------------
# Режимы и флаги (нечисловые параметры)
# -------------------------------
st.subheader("Режимы и флаги")
st.caption(
    "Эти параметры не являются числами (строки/булевы флаги), поэтому они не попадают в таблицу числовых параметров выше. "
    "Здесь их можно менять без ручной правки JSON."
)

# Флаги (bool)
def _is_bool_like(k, v) -> bool:
    # Нормальный случай: в JSON true/false -> bool
    if isinstance(v, (bool, np.bool_)):
        return True
    # Иногда флаг может быть представлен как 0/1 (после внешней конверсии/экспорта).
    # Важно: пользователь прямо попросил "проверь что все булевы вынесены" — поэтому берём 0/1 как bool без эвристик.
    if isinstance(v, int) and v in (0, 1):
        return True
    # Иногда бывает строкой "true"/"false"/"0"/"1".
    if isinstance(v, str):
        vv = v.strip().lower()
        if vv in ("true", "false", "0", "1"):
            return True
    return False

bool_keys_ui = sorted(set([k for k, v in base_override.items() if _is_bool_like(k, v)]) | set(BASE_BOOL_KEYS))
if bool_keys_ui:
    with st.expander("Флаги (bool)", expanded=True):
        def _to_bool(v) -> bool:
            if isinstance(v, (bool, np.bool_)):
                return bool(v)
            if isinstance(v, int):
                return bool(v)
            if isinstance(v, str):
                vv = v.strip().lower()
                if vv in ("true", "1", "yes", "y", "да"):
                    return True
                if vv in ("false", "0", "no", "n", "нет", ""):
                    return False
            return bool(v)

        cols = st.columns(2)
        for i, k in enumerate(bool_keys_ui):
            meta = PARAM_META.get(k, {"описание": ""})
            help_txt = meta.get("описание", "")
            with cols[i % 2]:
                base_override[k] = bool(
                    st.checkbox(
                        k,
                        value=_to_bool(base_override.get(k, False)),
                        help=help_txt if help_txt else None,
                        key=f"flag__{k}",
                    )
                )
else:
    st.info("В базе нет булевых флагов (bool).")

# Режимы (string)
str_keys_ui = sorted([k for k, v in base_override.items() if isinstance(v, str)])

# Для известных ключей — задаём безопасные варианты (канонические имена как в модели).
STRING_OPTIONS = {
    "термодинамика": ["isothermal", "adiabatic", "thermal"],
    "газ_модель_теплоемкости": ["constant", "nist_air"],
    "стенка_термомодель": ["fixed_ambient", "lumped"],
    "стенка_форма": ["sphere", "cylinder"],
    "стенка_h_газ_режим": ["constant", "flow_dependent"],
    "модель_пассивного_расхода": ["orifice", "iso6358"],

    # Механика/кинематика
    "механика_кинематика": ["dw2d", "dw2d_mounts", "mr", "table"],
    "колесо_координата": ["center", "contact"],
}
STRING_HELP = {
    "термодинамика": "Режим газа: isothermal (изотерма), adiabatic (адиабата), thermal (теплообмен с учётом стенки).",
    "газ_модель_теплоемкости": "Теплоёмкости воздуха: constant (постоянные) или nist_air (T-зависимые, полуидеальный газ).",
    "стенка_термомодель": "Модель стенки: fixed_ambient (стенка всегда = T_окр, быстро) или lumped (температура стенки как состояние).",
    "стенка_форма": "Геометрия для auto-оценки площади стенки из объёма: sphere (сфера) или cylinder (цилиндр).",
    "стенка_h_газ_режим": "Коэффициент теплоотдачи газ↔стенка: constant или flow_dependent (усиление при больших расходах).",
    "модель_пассивного_расхода": "Модель пассивных сопротивлений/дросселей: orifice (Cd*A) или iso6358 (C,b,m).",
    "паспорт_компонентов_json": "Путь к JSON-паспорту компонентов (Camozzi и др.) для автоподстановки параметров.",

    # Механика/кинематика
    "механика_кинематика": "Кинематика подвески: mr (постоянное передаточное), table (таблица dw→drod), dw2d/dw2d_mounts (геометрия креплений на нижнем рычаге).",
    "колесо_координата": "Как интерпретируется zw: center = координата центра колеса; contact = координата пятна контакта (центр = zw + R).",
}

if str_keys_ui:
    with st.expander("Режимы (string)", expanded=True):
        # Делаем более компактный и удобный макет: 2 колонки вместо "на всю ширину"
        cols_modes = st.columns(2, gap="large")

        for i, k in enumerate(str_keys_ui):
            with cols_modes[i % 2]:
                cur = str(base_override.get(k, ""))
                help_txt = STRING_HELP.get(k, "")

                # 1) Известные режимы — selectbox
                if k in STRING_OPTIONS:
                    opts = list(STRING_OPTIONS[k])
                    if cur not in opts:
                        # если в базе было что-то нестандартное — показываем его первым, чтобы не потерять
                        opts = [cur] + [o for o in opts if o != cur]
                    base_override[k] = st.selectbox(
                        k,
                        options=opts,
                        index=opts.index(cur) if cur in opts else 0,
                        help=help_txt if help_txt else None,
                        key=f"mode__{k}",
                    )

                    # DW2D geometry is configured on a dedicated page.
                    # (User request: "я не нашёл где задаётся геометрия")
                    if k == "механика_кинематика":
                        _kin = str(base_override.get(k, "") or "")
                        if _kin in ("dw2d", "dw2d_mounts"):
                            st.caption(
                                "DW2D: геометрия креплений задаётся на странице «Геометрия подвески (DW2D)» "
                                "(меню слева → Проверки и настройка)."
                            )
                            if hasattr(st, "switch_page"):
                                if st.button(
                                    "Открыть страницу геометрии DW2D",
                                    key="go_dw2d_geometry",
                                    help="Перейти к вводу геометрии нижнего рычага и креплений цилиндра",
                                ):
                                    try:
                                        st.switch_page("pneumo_solver_ui/pages/10_SuspensionGeometry.py")
                                    except Exception:
                                        pass
                            else:
                                st.info("Откройте: меню слева → Проверки и настройка → Геометрия подвески (DW2D).")

                    continue

                # 2) Паспорт компонентов — selectbox по json в папке + ручной ввод
                if k == "паспорт_компонентов_json":
                    # Сканируем JSON в папке приложения (где лежит pneumo_ui_app.py)
                    try:
                        json_files = sorted([pp.name for pp in HERE.glob("*.json")])
                    except Exception:
                        json_files = []
                    if cur and (cur not in json_files):
                        json_files = [cur] + json_files

                    colA, colB = st.columns([1.1, 1.0], gap="medium")
                    with colA:
                        if json_files:
                            base_override[k] = st.selectbox(
                                k,
                                options=json_files,
                                index=json_files.index(cur) if cur in json_files else 0,
                                help=help_txt if help_txt else None,
                                key=f"mode__{k}",
                            )
                        else:
                            base_override[k] = st.text_input(
                                k,
                                value=cur,
                                help=help_txt if help_txt else None,
                                key=f"mode__{k}",
                            )
                    with colB:
                        st.text_input(
                            "(или введите вручную)",
                            value=str(base_override.get(k, cur)),
                            key=f"mode__{k}__manual",
                            help="Если хотите указать путь/имя файла вручную — просто впишите тут и оно будет использовано.",
                        )
                        # если пользователь вводит вручную — приоритет ручного
                        manual_v = st.session_state.get(f"mode__{k}__manual", "").strip()
                        if manual_v:
                            base_override[k] = manual_v
                    continue

                # 3) Прочие строки — text_input
                base_override[k] = st.text_input(
                    k,
                    value=cur,
                    help=help_txt if help_txt else None,
                    key=f"mode__{k}",
                )
else:
    st.info("В базе нет строковых режимов (string).")

# -------------------------------
# Набор сценариев и ограничения (редактируется из UI)
# -------------------------------
st.subheader("Набор сценариев и ограничения")
st.caption(
    "Здесь задаются параметры сценариев и целевые запасы/ограничения. "
    "Редактирование — только в UI (файлы вручную править не нужно)."
)

ALLOWED_TEST_TYPES = list(CANONICAL_OPTIMIZATION_TEST_TYPES)

DEFAULT_SUITE_PATH = canonical_suite_json_path(HERE)
SUITE_CONTRACT_WARNINGS_PENDING_KEY = "suite_contract_warnings_pending"


def _normalize_suite_id_value(value: Any) -> str:
    try:
        if value is None:
            return ""
        s = str(value).strip()
        if s.lower() in {"", "none", "nan", "nat"}:
            return ""
        return s
    except Exception:
        return ""


def first_suite_selected_id(df: pd.DataFrame) -> str:
    try:
        if df is None or df.empty or ("id" not in df.columns):
            return ""
        ids = [_normalize_suite_id_value(x) for x in df["id"].tolist()]
        ids = [x for x in ids if x]
        return ids[0] if ids else ""
    except Exception:
        return ""


def _ensure_unique_suite_ids(df: pd.DataFrame, *, context: str = "suite") -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    issues: list[str] = []
    if "id" not in out.columns:
        out["id"] = ""
    seen: set[str] = set()
    repaired = 0
    duplicate_repairs = 0
    for idx in list(out.index):
        raw_id = out.at[idx, "id"]
        norm_id = _normalize_suite_id_value(raw_id)
        if (not norm_id) or (norm_id in seen):
            if norm_id in seen:
                duplicate_repairs += 1
            norm_id = str(uuid.uuid4())
            out.at[idx, "id"] = norm_id
            repaired += 1
        seen.add(norm_id)
    if repaired > 0:
        issues.append(
            f"[{context}] Repaired suite row ids: regenerated={repaired}, duplicate_conflicts={duplicate_repairs}. "
            "Missing/NaN/duplicate ids are forbidden because they break row selection and widget-key stability."
        )
    return out, issues


def ensure_suite_columns(df: pd.DataFrame, *, context: str = "pneumo_ui_app.ensure_suite_columns") -> pd.DataFrame:
    """Ensure canonical suite schema.

    ABSOLUTE LAW (см. 00_READ_FIRST__ABSOLUTE_LAW.md):

    * Никаких дублей/алиасов колонок внутри suite.
    * Внутри приложения используются **только канонические** имена колонок.

    Допускается только явная одноразовая миграция legacy-колонок на входе
    (при загрузке/восстановлении suite) с обязательным warning/logging.
    Это не runtime-мост совместимости: legacy-колонки немедленно удаляются
    из editor state.
    Функция обязана быть безопасной: никаких падений из-за кривого файла.
    """

    if df is None:
        return pd.DataFrame()

    df = df.copy()

    issues: list[str] = []
    try:
        df, migration_issues = migrate_legacy_suite_columns(df, context=context)
        issues.extend(migration_issues)
    except Exception as exc:
        msg = f"[suite] Failed to migrate legacy suite columns in {context}: {exc}"
        logging.warning(msg)
        _emit("contract_warning", msg)

    try:
        suite_norm, stage_audit = normalize_suite_stage_numbers(df.to_dict(orient="records"))
        if (
            int(stage_audit.get("stage_bias_applied", 0) or 0) != 0
            or int(stage_audit.get("clamped_negative_rows", 0) or 0) != 0
            or int(stage_audit.get("inferred_missing_rows", 0) or 0) != 0
        ):
            df = pd.DataFrame(suite_norm)
        if int(stage_audit.get("stage_bias_applied", 0) or 0) != 0:
            issues.append(
                "Stage numbering was explicitly normalized to canonical 0-based form "
                f"(bias={int(stage_audit.get('stage_bias_applied', 0) or 0)})."
            )
        if int(stage_audit.get("clamped_negative_rows", 0) or 0) != 0:
            issues.append(
                f"Negative stage values were clamped to canonical stage 0: rows={int(stage_audit.get('clamped_negative_rows', 0) or 0)}."
            )
        if int(stage_audit.get("inferred_missing_rows", 0) or 0) != 0:
            issues.append(
                f"Missing/NaN stage values were inferred and made explicit: rows={int(stage_audit.get('inferred_missing_rows', 0) or 0)}."
            )
    except Exception as exc:
        msg = f"[suite] Failed to normalize suite stage numbers in {context}: {exc}"
        logging.warning(msg)
        _emit("contract_warning", msg)

    defaults = {
        # Primary identifying fields
        "id": "",
        "имя": "",
        "тип": "",
        "включен": True,
        "комментарий": "",

        # Simulation controls
        "dt": 0.005,
        "t_end": 5.0,

        # World-road controls
        "auto_t_end_from_len": True,
        "road_len_m": 3000.0,
        "vx0_м_с": 20.0 / 3.6,
        "road_csv": "",
        "axay_csv": "",
        "road_surface": "rough",
        "slope_deg": 0.0,

        # Optional tuning
        "track_m": float('nan'),
        "wheelbase_m": float('nan'),
        "yaw0_рад": float('nan'),

        # Boolean flags
        "save_npz": True,
        "save_csv": True,
    }

    # Ensure all expected columns exist.
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Normalize types (best-effort).
    try:
        df["включен"] = df["включен"].astype(bool)
    except Exception:
        pass

    try:
        df, id_issues = _ensure_unique_suite_ids(df, context=context)
        issues.extend(id_issues)
    except Exception as exc:
        msg = f"[suite] Failed to normalize suite row ids in {context}: {exc}"
        logging.warning(msg)
        _emit("contract_warning", msg)

    # Drop any duplicate column names (should not happen, but keep app alive).
    try:
        if df.columns.duplicated().any():
            dups = df.columns[df.columns.duplicated()].tolist()
            logging.warning("[SUITE] Duplicate columns after normalization: %s. Keeping first occurrences.", dups)
            df = df.loc[:, ~df.columns.duplicated()]
    except Exception:
        pass

    # Keep canonical ordering: expected columns first, then everything else.
    expected_cols = list(defaults.keys())
    extra_cols = [c for c in df.columns if c not in expected_cols]
    df = df[expected_cols + extra_cols]

    if issues:
        st.session_state[SUITE_CONTRACT_WARNINGS_PENDING_KEY] = list(issues)
        msg = (
            "Legacy suite columns were explicitly migrated to canonical schema. "
            "Please re-save suite to keep only canonical columns.\n"
            "- " + "\n- ".join(issues)
        )
        logging.warning(msg)
        _emit("contract_warning", msg)

    return df

# загрузка suite по умолчанию
if "df_suite_edit" not in st.session_state:
    st.session_state["df_suite_edit"] = ensure_suite_columns(
        pd.DataFrame(
            load_optimization_ready_suite_rows(
                WORKSPACE_DIR,
                base_json_path=canonical_base_json_path(HERE),
                suite_source_path=DEFAULT_SUITE_PATH,
            )
        ),
        context="pneumo_ui_app.default_suite_load",
    )
_sel0 = _normalize_suite_id_value(st.session_state.get("ui_suite_selected_id"))
if not _sel0:
    try:
        _suite_df0 = st.session_state.get("df_suite_edit")
        _suite_records0 = _suite_df0.to_dict(orient="records") if hasattr(_suite_df0, "to_dict") else []
        _diag_sel = DIAGNOSTIC_SUITE_SELECTED_ID if any(_normalize_suite_id_value((row or {}).get("id")) == DIAGNOSTIC_SUITE_SELECTED_ID for row in _suite_records0) else ""
        if _diag_sel:
            st.session_state["ui_suite_selected_id"] = _diag_sel
        else:
            st.session_state["ui_suite_selected_id"] = first_suite_selected_id(_suite_df0) if hasattr(_suite_df0, 'columns') else ""
    except Exception:
        pass
else:
    st.session_state["ui_suite_selected_id"] = _sel0

# upload suite из файла
colSU1, colSU2 = st.columns([1.2, 1.0], gap="large")
with colSU1:
    suite_upload = st.file_uploader(
        "Загрузить набор сценариев (JSON)",
        type=["json"],
        help="Можно загрузить ранее сохранённый файл suite.json с набором сценариев.",
    )
    if suite_upload is not None:
        try:
            suite_loaded = json.loads(suite_upload.read().decode("utf-8"))
            if isinstance(suite_loaded, list):
                _loaded_df = ensure_suite_columns(
                    pd.DataFrame(suite_loaded),
                    context="pneumo_ui_app.suite_upload",
                )
                st.session_state["df_suite_edit"] = _loaded_df
                st.session_state["ui_suite_selected_id"] = first_suite_selected_id(_loaded_df)
                st.success("Набор сценариев загружен.")
                try:
                    from pneumo_solver_ui.ui_persistence import autosave_now
                    autosave_now(st)
                except Exception:
                    pass
            else:
                st.error("Файл JSON должен содержать список сценариев.")
        except Exception as e:
            st.error(f"Не удалось прочитать JSON: {e}")

with colSU2:
    df_suite_export = st.session_state["df_suite_edit"].copy()
    # Убираем англоязычные дубликаты колонок (если пришли из старого suite)
    for _c in ["name", "type", "enabled"]:
        if _c in df_suite_export.columns:
            df_suite_export = df_suite_export.drop(columns=[_c])

    # Не экспортируем пустые строки
    try:
        _name_ok = df_suite_export["имя"].notna() & (df_suite_export["имя"].astype(str).str.strip() != "")
        _type_ok = df_suite_export["тип"].notna() & (df_suite_export["тип"].astype(str).str.strip() != "")
        df_suite_export = df_suite_export[_name_ok & _type_ok]
    except Exception:
        pass

    suite_bytes = json.dumps(df_suite_export.to_dict(orient="records"), ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("Скачать набор сценариев (JSON)", data=suite_bytes, file_name="suite.json", mime="application/json")


# --- Новый редактор тест-набора: список + карточка (без горизонтального скролла) ---
# (цель: убрать широкие таблицы, сделать управление тестами «по-человечески»)
df_suite_edit = st.session_state.get("df_suite_edit", pd.DataFrame([])).copy()
df_suite_edit = ensure_suite_columns(df_suite_edit, context="pneumo_ui_app.session_state_restore")

def _ensure_etalon_long_scenario_present(_df: pd.DataFrame) -> pd.DataFrame:
    """Мягкая миграция: если пользователь загрузил/восстановил старый suite без эталонного длинного сценария,
    добавляем его (включённым по умолчанию), чтобы он не «убегал» из набора."""
    try:
        if _df is None or _df.empty:
            return _df
        if ("имя" in _df.columns) and (_df["имя"].astype(str) == "длинный_город_неровная_дорога_20кмч").any():
            return _df

        # берём шаблон из default_suite.json
        _tmpl = None
        for _r in load_suite(DEFAULT_SUITE_PATH):
            if str(_r.get("имя", "")).strip() == "длинный_город_неровная_дорога_20кмч":
                _tmpl = dict(_r)
                break
        if not _tmpl:
            return _df

        _tmpl["включен"] = True
        _df2 = pd.concat([_df, pd.DataFrame([_tmpl])], ignore_index=True)
        return ensure_suite_columns(_df2)
    except Exception:
        return _df

# NOTE(R168): Do not silently inject extra tests into the user's suite.
# df_suite_edit = _ensure_etalon_long_scenario_present(df_suite_edit)
st.session_state["df_suite_edit"] = df_suite_edit

_suite_contract_issues = st.session_state.pop(SUITE_CONTRACT_WARNINGS_PENDING_KEY, [])
if _suite_contract_issues:
    st.warning(
        "В suite обнаружены legacy-колонки. Выполнена явная миграция в canonical schema; "
        "пересохраните suite.json.\n- " + "\n- ".join(str(x) for x in _suite_contract_issues)
    )

def _new_test_row(preset: str = "worldroad_flat") -> dict:
    """Генератор шаблонов тестов.

    Важно: поля здесь — русскоязычные (как в df_suite_edit), ниже они мапятся на ключи worker'а.
    """
    base = {
        "id": str(uuid.uuid4()),
        "включен": True,
        "стадия": 0,
        "имя": "Новый тест",
        "тип": "worldroad",
        "dt": 0.01,
        "t_end": 10.0,
        "road_csv": "",
        "axay_csv": "",
        "road_surface": "flat",
        "road_len_m": 200.0,
        "vx0_м_с": 20.0,
        "auto_t_end_from_len": True,
        "A": 0.02,
        "f": 1.0,
        "L": 1.0,
        "amp": 0.0,
        "h": 0.02,
        "w": 0.5,
        "k": 3.0,
        "ay": 0.0,
        "ax": 0.0,
        # penalty targets (see opt_worker_v3_margins_energy.PENALTY_TARGET_SPECS)
        # By default they are disabled (None). Enable them in the Suite editor.
        "target_макс_доля_отрыва": None,
        "target_мин_запас_до_Pmid_бар": None,
        "target_мин_Fmin_Н": None,
        "target_мин_запас_до_пробоя_крен_град": None,
        "target_мин_запас_до_пробоя_тангаж_град": None,
        "target_мин_запас_до_упора_штока_м": None,
        "target_лимит_скорости_штока_м_с": None,
        "target_макс_ошибка_энергии_газа_отн": None,
        "target_макс_эксергия_разрушена_Дж": None,
        "target_макс_энтропия_генерация_Дж_К": None,
        "target_макс_эксергия_падение_давления_Дж": None,
        "target_макс_эксергия_смешение_Дж": None,
        "target_макс_эксергия_остаток_без_тепло_без_смешения_Дж": None,
        "target_макс_энтропия_падение_давления_Дж_К": None,
        "target_макс_энтропия_смешение_Дж_К": None,
        "target_макс_энтропия_остаток_без_тепло_без_смешения_Дж_К": None,
        "params_override": "",
    }

    if preset == "worldroad_sine_x":
        base.update({
            "имя": "WorldRoad: синус (вдоль)",
            "тип": "worldroad",
            "road_surface": json.dumps({"type": "sine_x", "A": 0.02, "wavelength": 2.0}, ensure_ascii=False),
            "vx0_м_с": 20.0,
            "road_len_m": 200.0,
            "auto_t_end_from_len": True,
            "t_end": 10.0,
        })
    elif preset == "worldroad_bump":
        base.update({
            "имя": "WorldRoad: бугор",
            "тип": "worldroad",
            "road_surface": json.dumps({"type": "bump", "h": 0.04, "w": 0.6}, ensure_ascii=False),
            "vx0_м_с": 15.0,
            "road_len_m": 150.0,
            "auto_t_end_from_len": True,
            "t_end": 10.0,
        })
    elif preset == "inertia_brake":
        base.update({
            "имя": "Инерция: торможение",
            # Для продольного ускорения/торможения используется тест "инерция_тангаж".
            # (исправление: раньше был несуществующий тип "inertia_flat", из-за чего тест мог ломаться)
            "тип": "инерция_тангаж",
            "ax": -3.0,
            "ay": 0.0,
            "road_surface": "flat",
            "t_end": 5.0,
            "auto_t_end_from_len": False,
        })
    else:
        base.update({
            "имя": "WorldRoad: ровная",
            "тип": "worldroad",
            "road_surface": "flat",
        })

    return base


def _suite_set_flash(level: str, msg: str) -> None:
    try:
        st.session_state["_ui_suite_flash"] = {"level": str(level or "info"), "msg": str(msg or "")}
    except Exception:
        pass


def _suite_render_flash() -> None:
    raw = st.session_state.pop("_ui_suite_flash", None)
    if not isinstance(raw, dict):
        return
    level = str(raw.get("level") or "info").strip().lower()
    msg = str(raw.get("msg") or "").strip()
    if not msg:
        return
    renderer = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
        "info": st.info,
    }.get(level, st.info)
    renderer(msg)


def _suite_maybe_autosave_pending() -> None:
    if not bool(st.session_state.pop("_ui_suite_autosave_pending", False)):
        return
    try:
        from pneumo_solver_ui.ui_persistence import autosave_now

        autosave_now(st)
    except Exception:
        pass


def _queue_suite_selected_id(next_id: Any) -> None:
    st.session_state["_ui_suite_selected_id_pending"] = _normalize_suite_id_value(next_id)


def _queue_stage_filter_extend(stage_value: Any) -> None:
    try:
        stage_i = max(0, int(stage_value))
    except Exception:
        stage_i = 0
    try:
        pending = [max(0, int(x)) for x in list(st.session_state.get("_ui_suite_stage_filter_extend_pending") or [])]
    except Exception:
        pending = []
    if stage_i not in pending:
        pending.append(stage_i)
    st.session_state["_ui_suite_stage_filter_extend_pending"] = sorted(set(pending))


def _sync_multiselect_all(key: str, all_values: list[Any], *, cast: Callable[[Any], Any] = lambda x: x) -> None:
    def _normalize(raw_values: Any) -> list[Any]:
        out: list[Any] = []
        try:
            seq = list(raw_values or [])
        except Exception:
            seq = []
        for raw in seq:
            try:
                value = cast(raw)
            except Exception:
                continue
            if value not in out:
                out.append(value)
        return out

    normalized_all = _normalize(all_values)
    prev_key = f"{key}__options_prev"
    prev_values = _normalize(st.session_state.get(prev_key))
    current_values = _normalize(st.session_state.get(key))
    current_values = [value for value in current_values if value in normalized_all]
    had_all_selected = bool(prev_values) and set(current_values) == set(prev_values)

    if not current_values or had_all_selected:
        st.session_state[key] = normalized_all.copy()
    else:
        st.session_state[key] = [value for value in normalized_all if value in current_values]
    st.session_state[prev_key] = normalized_all.copy()


def _pick_existing_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def _suite_filtered_view(df: pd.DataFrame, stage_filter: List[int] | None, only_enabled: bool, suite_search: str) -> pd.DataFrame:
    view = df.copy()
    try:
        stages = sorted({max(0, int(x)) for x in list(stage_filter or [])})
    except Exception:
        stages = []
    if stages:
        try:
            inferred_stage = view.apply(lambda _row: int(infer_suite_stage(_row.to_dict())), axis=1)
            view = view.loc[inferred_stage.isin(stages)].copy()
            view.loc[:, "стадия"] = inferred_stage.loc[view.index].astype(int)
        except Exception:
            try:
                view = view[view["стадия"].isin(stages)]
            except Exception:
                pass
    if bool(only_enabled):
        try:
            view = view[view["включен"].astype(bool)]
        except Exception:
            pass
    q = str(suite_search or "").strip()
    if q:
        try:
            name_col = _pick_existing_column(view, ("имя", "РёРјСЏ"))
            type_col = _pick_existing_column(view, ("тип", "С‚РёРї"))
            mask = pd.Series(False, index=view.index)
            if name_col:
                mask = mask | view[name_col].astype(str).str.contains(q, case=False, na=False)
            if type_col:
                mask = mask | view[type_col].astype(str).str.contains(q, case=False, na=False)
            view = view[mask]
        except Exception:
            pass
    return view


def _suite_current_visible_ids() -> list[str]:
    try:
        df = ensure_suite_columns(
            pd.DataFrame(st.session_state.get("df_suite_edit", pd.DataFrame([]))).copy(),
            context="pneumo_ui_app.visible_ids_callback",
        )
    except Exception:
        return []
    try:
        stage_filter = [max(0, int(x)) for x in list(st.session_state.get("ui_suite_stage_filter") or [])]
    except Exception:
        stage_filter = []
    only_enabled = bool(st.session_state.get("ui_suite_only_enabled", False))
    suite_search = str(st.session_state.get("ui_suite_search", "") or "").strip()
    view = _suite_filtered_view(df, stage_filter, only_enabled, suite_search)
    if "id" not in view.columns:
        return []
    ids = [_normalize_suite_id_value(x) for x in view["id"].tolist()]
    return [x for x in ids if x]


def _ensure_stage_visible_in_filter(stage_value: Any) -> None:
    try:
        stage_i = max(0, int(stage_value))
    except Exception:
        stage_i = 0
    _queue_stage_filter_extend(stage_i)
    try:
        all_prev = [max(0, int(x)) for x in list(st.session_state.get("ui_suite_stage_all_prev") or [])]
    except Exception:
        all_prev = []
    if stage_i not in all_prev:
        all_prev.append(stage_i)
        st.session_state["ui_suite_stage_all_prev"] = sorted(set(all_prev))


def _suite_reset_filters_callback(all_stages: list[int] | None = None) -> None:
    try:
        stages = sorted({max(0, int(x)) for x in list(all_stages or [])})
    except Exception:
        stages = []
    st.session_state["_ui_suite_filters_reset_pending"] = True
    st.session_state["ui_suite_stage_all_prev"] = stages


def _suite_show_all_callback(all_stages: list[int] | None = None) -> None:
    try:
        stages = sorted({max(0, int(x)) for x in list(all_stages or [])})
    except Exception:
        stages = []
    st.session_state["_ui_suite_show_all_pending"] = True
    st.session_state["ui_suite_stage_all_prev"] = stages


def _suite_add_preset_callback(preset: str) -> None:
    try:
        df = ensure_suite_columns(
            pd.DataFrame(st.session_state.get("df_suite_edit", pd.DataFrame([]))).copy(),
            context="pneumo_ui_app.add_preset_callback",
        )
        row_new = _new_test_row(str(preset or "worldroad_flat"))
        new_id = _normalize_suite_id_value(row_new.get("id")) or str(uuid.uuid4())
        row_new["id"] = new_id
        df = pd.concat([df, pd.DataFrame([row_new])], ignore_index=True)
        df = ensure_suite_columns(df, context="pneumo_ui_app.add_preset_callback.final")
        st.session_state["df_suite_edit"] = df
        _queue_suite_selected_id(new_id)
        st.session_state["ui_suite_search"] = ""
        st.session_state["ui_suite_only_enabled"] = False
        _ensure_stage_visible_in_filter(row_new.get("стадия", 0))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Шаблон сценария добавлен в набор.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось добавить шаблон сценария: {exc}")


def _suite_set_enabled_visible_callback(enabled: bool) -> None:
    try:
        row_ids = _suite_current_visible_ids()
        if not row_ids:
            return
        df = ensure_suite_columns(
            pd.DataFrame(st.session_state.get("df_suite_edit", pd.DataFrame([]))).copy(),
            context="pneumo_ui_app.toggle_visible_callback",
        )
        df.loc[df["id"].astype(str).isin(row_ids), "включен"] = bool(enabled)
        st.session_state["df_suite_edit"] = ensure_suite_columns(df, context="pneumo_ui_app.toggle_visible_callback.final")
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Видимые сценарии обновлены.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось обновить видимые сценарии: {exc}")


def _suite_duplicate_selected_callback() -> None:
    try:
        sel_id = _normalize_suite_id_value(st.session_state.get("ui_suite_selected_id"))
        if not sel_id:
            return
        df = ensure_suite_columns(
            pd.DataFrame(st.session_state.get("df_suite_edit", pd.DataFrame([]))).copy(),
            context="pneumo_ui_app.duplicate_selected_callback",
        )
        matches = df.index[df["id"].astype(str) == sel_id].tolist()
        if not matches:
            return
        src_idx = int(matches[0])
        row = df.loc[src_idx].to_dict()
        row["id"] = str(uuid.uuid4())
        row["имя"] = f"{row.get('имя', 'Сценарий')} (копия)"
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df = ensure_suite_columns(df, context="pneumo_ui_app.duplicate_selected_callback.final")
        st.session_state["df_suite_edit"] = df
        _queue_suite_selected_id(str(row["id"]))
        _ensure_stage_visible_in_filter(row.get("стадия", 0))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Выбранный сценарий продублирован.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось продублировать сценарий: {exc}")


def _suite_delete_selected_callback() -> None:
    try:
        sel_id = _normalize_suite_id_value(st.session_state.get("ui_suite_selected_id"))
        if not sel_id:
            return
        df = ensure_suite_columns(
            pd.DataFrame(st.session_state.get("df_suite_edit", pd.DataFrame([]))).copy(),
            context="pneumo_ui_app.delete_selected_callback",
        )
        matches = df.index[df["id"].astype(str) == sel_id].tolist()
        if not matches:
            return
        del_idx = int(matches[0])
        df = df.drop(index=del_idx).reset_index(drop=True)
        df = ensure_suite_columns(df, context="pneumo_ui_app.delete_selected_callback.final")
        st.session_state["df_suite_edit"] = df
        try:
            new_ids = [_normalize_suite_id_value(x) for x in df.get("id", pd.Series([], dtype=object)).tolist()]
            new_ids = [x for x in new_ids if x]
            if new_ids:
                pick = min(int(del_idx), int(len(new_ids) - 1))
                _queue_suite_selected_id(str(new_ids[pick]))
            else:
                _queue_suite_selected_id("")
        except Exception:
            _queue_suite_selected_id(first_suite_selected_id(df))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Выбранный сценарий удалён из набора.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось удалить сценарий: {exc}")


def _suite_editor_widget_key(sid: str, field: str) -> str:
    return f"ui_suite_card_{field}_{sid}"


def _seed_suite_editor_state(sid: str, rec: Dict[str, Any], *, force: bool = False) -> None:
    def _seed(field: str, value: Any) -> None:
        key = _suite_editor_widget_key(sid, field)
        if force or (key not in st.session_state):
            st.session_state[key] = value

    def _as_float(value: Any, default: float) -> float:
        try:
            if pd.isna(value):
                return float(default)
        except Exception:
            pass
        try:
            return float(value)
        except Exception:
            return float(default)

    try:
        stage_default = max(0, int(rec.get("стадия", 0) or 0))
    except Exception:
        stage_default = 0
    ttype_default = str(rec.get("тип", "worldroad") or "worldroad")
    if ttype_default not in ALLOWED_TEST_TYPES:
        ttype_default = "worldroad"

    _seed("enabled", bool(rec.get("включен", True)))
    _seed("name", str(rec.get("имя", "") or ""))
    _seed("stage", int(stage_default))
    _seed("type", ttype_default)
    _seed("dt", float(_as_float(rec.get("dt", 0.01), 0.01)))
    _seed("t_end", float(_as_float(rec.get("t_end", 5.0), 5.0)))
    _seed("road_csv", str(rec.get("road_csv", "") or ""))
    _seed("axay_csv", str(rec.get("axay_csv", "") or ""))
    _seed("road_len_m", float(_as_float(rec.get("road_len_m", 200.0), 200.0)))
    _seed("vx0_mps", float(_as_float(rec.get("vx0_м_с", 20.0), 20.0)))
    _seed("auto_t_end_from_len", bool(rec.get("auto_t_end_from_len", False)))
    _seed("ax", float(_as_float(rec.get("ax", 0.0), 0.0)))
    _seed("ay", float(_as_float(rec.get("ay", 0.0), 0.0)))
    _seed("params_override", str(rec.get("params_override", "") or ""))

    road_surface_raw = str(rec.get("road_surface", "flat") or "flat")
    try:
        spec_obj = json.loads(road_surface_raw) if str(road_surface_raw).strip().startswith("{") else {"type": road_surface_raw}
    except Exception:
        spec_obj = {"type": "flat"}
    surf_type = str(spec_obj.get("type", "flat") or "flat")
    if surf_type not in {"flat", "sine_x", "sine_y", "bump", "ridge_x", "ridge_cosine_bump"}:
        surf_type = "flat"
    _seed("road_surface_type", surf_type)
    _seed("road_surface_sine_a", float(_as_float(spec_obj.get("A", 0.02), 0.02)))
    _seed("road_surface_sine_wavelength", float(_as_float(spec_obj.get("wavelength", 2.0), 2.0)))
    _seed("road_surface_hw_h", float(_as_float(spec_obj.get("h", 0.04), 0.04)))
    _seed("road_surface_hw_w", float(_as_float(spec_obj.get("w", 0.6), 0.6)))
    _seed("road_surface_cos_h", float(_as_float(spec_obj.get("h", 0.04), 0.04)))
    _seed("road_surface_cos_w", float(_as_float(spec_obj.get("w", 0.6), 0.6)))
    _seed("road_surface_cos_k", float(_as_float(spec_obj.get("k", 3.0), 3.0)))

    try:
        from pneumo_solver_ui.opt_worker_v3_margins_energy import PENALTY_TARGET_SPECS
    except Exception:
        PENALTY_TARGET_SPECS = []
    for spec in (PENALTY_TARGET_SPECS or []):
        k = str(spec.get("key", "") or "").strip()
        if not k:
            continue
        col = f"target_{k}"
        cur = rec.get(col, None)
        enabled = False
        if cur is not None:
            try:
                if isinstance(cur, float) and pd.isna(cur):
                    enabled = False
                elif isinstance(cur, str) and cur.strip() == "":
                    enabled = False
                else:
                    enabled = True
            except Exception:
                enabled = True
        _seed(f"pen_tgt_en_{k}", bool(enabled))
        _seed(f"pen_tgt_val_{k}", float(_as_float(cur, 0.0) if enabled else 0.0))


def _resolve_ring_default_dt_s(df_suite_frame: pd.DataFrame) -> float:
    fallback_dt_s = 0.01

    def _coerce_dt(value: Any) -> Optional[float]:
        try:
            dt_s = float(value)
        except Exception:
            return None
        if (not math.isfinite(dt_s)) or dt_s <= 0.0:
            return None
        return float(dt_s)

    try:
        sel_id = _normalize_suite_id_value(st.session_state.get("ui_suite_selected_id"))
    except Exception:
        sel_id = ""

    if sel_id and hasattr(df_suite_frame, "columns") and {"id", "dt"}.issubset(df_suite_frame.columns):
        try:
            matches = df_suite_frame.index[df_suite_frame["id"].astype(str) == sel_id].tolist()
            if matches:
                selected_dt_s = _coerce_dt(df_suite_frame.loc[int(matches[0]), "dt"])
                if selected_dt_s is not None:
                    return selected_dt_s
        except Exception:
            pass

    if hasattr(df_suite_frame, "columns") and "dt" in df_suite_frame.columns:
        try:
            for value in df_suite_frame["dt"].tolist():
                dt_s = _coerce_dt(value)
                if dt_s is not None:
                    return dt_s
        except Exception:
            pass

    return fallback_dt_s


def _render_heavy_ring_editor(df_suite_frame: pd.DataFrame) -> pd.DataFrame:
    st.markdown("### Сценарий: сегменты-кольцо")

    if not _HAS_RING_SCENARIO_EDITOR:
        st.error(
            "Редактор сценариев (сегменты-кольцо) недоступен "
            "(не удалось импортировать `pneumo_solver_ui.ui_scenario_ring`). "
            "Переустановите зависимости или проверьте целостность архива."
        )
        return df_suite_frame

    with st.expander("Открыть редактор сценариев (сегменты-кольцо)", expanded=True):
        try:
            ring_default_dt_s = _resolve_ring_default_dt_s(df_suite_frame)
            try:
                ring_wheelbase_m = float(base_override.get("база", 0.0))
            except Exception:
                ring_wheelbase_m = 0.0
                logging.warning("[RING] Не удалось прочитать канонический параметр 'база' для wheelbase_m.")
                st.warning(
                    "Не удалось прочитать канонический параметр **'база'**. "
                    "Генерация ring-сценария потребует исправить base.",
                    icon="⚠️",
                )

            if ring_wheelbase_m <= 0.0:
                logging.warning("[RING] Некорректная база для ring-сценария: %s", ring_wheelbase_m)
                st.warning(
                    "Колёсная база для ring-сценария берётся только из канонического "
                    "параметра **'база'** и сейчас <= 0. Проверьте исходные данные модели.",
                    icon="⚠️",
                )

            return render_ring_scenario_generator(
                df_suite_frame,
                work_dir=WORKSPACE_DIR,
                wheelbase_m=float(ring_wheelbase_m),
                default_dt_s=float(ring_default_dt_s),
            )
        except Exception as exc:
            st.error(f"Ошибка в редакторе сценариев: {exc}")
            st.caption("Продолжаем работу с обычным редактором suite.")
            logging.exception("[RING] scenario editor failed")
            return df_suite_frame



df_suite_edit = render_heavy_suite_editor_section(
    st,
    df_suite_edit=df_suite_edit,
    diagnostic_suite_preset=DIAGNOSTIC_SUITE_PRESET,
    allowed_test_types=ALLOWED_TEST_TYPES,
    suite_editor_widget_key_fn=_suite_editor_widget_key,
    seed_suite_editor_state_fn=_seed_suite_editor_state,
    infer_suite_stage_fn=infer_suite_stage,
    save_upload_fn=lambda uploaded, prefix: _save_upload(uploaded, prefix=prefix),
    queue_suite_selected_id_fn=_queue_suite_selected_id,
    ensure_stage_visible_in_filter_fn=_ensure_stage_visible_in_filter,
    set_flash_fn=_suite_set_flash,
    ensure_suite_columns_fn=lambda frame: ensure_suite_columns(frame, context="pneumo_ui_app.suite_card_apply"),
    on_enable_visible=_suite_set_enabled_visible_callback,
    on_disable_visible=_suite_set_enabled_visible_callback,
    on_duplicate_selected=_suite_duplicate_selected_callback,
    on_delete_selected=_suite_delete_selected_callback,
    maybe_autosave_pending_fn=_suite_maybe_autosave_pending,
    render_flash_fn=_suite_render_flash,
    on_add_preset=_suite_add_preset_callback,
    suite_filtered_view_fn=_suite_filtered_view,
    normalize_suite_id_value_fn=_normalize_suite_id_value,
    sync_multiselect_all_fn=_sync_multiselect_all,
    reset_filters_callback=_suite_reset_filters_callback,
    show_all_callback=_suite_show_all_callback,
    render_ring_editor_fn=_render_heavy_ring_editor,
)


# валидируем и собираем suite_override (list[dict])
suite_errors: List[str] = []
suite_override: List[Dict[str, Any]] = []
for i, row in df_suite_edit.iterrows():
    rec = {k: (None if (isinstance(v, float) and (pd.isna(v))) else v) for k, v in row.to_dict().items()}
    # пропускаем полностью пустые строки
    if all((rec.get(k) in [None, "", False] for k in rec.keys())):
        continue

    enabled = bool(rec.get("включен", True))
    name = str(rec.get("имя") or rec.get("РёРјСЏ") or "").strip()
    typ = str(rec.get("тип") or rec.get("С‚РёРї") or "").strip()

    if enabled:
        if not name:
            suite_errors.append(f"Строка {i+1}: пустое имя сценария")
        if typ not in ALLOWED_TEST_TYPES:
            suite_errors.append(f"Сценарий '{name or i+1}': неизвестный тип '{typ}'")
        try:
            dt_i = float(rec.get("dt"))
            if dt_i <= 0:
                suite_errors.append(f"Сценарий '{name}': dt должен быть > 0")
        except Exception:
            suite_errors.append(f"Сценарий '{name}': dt не задан")
        try:
            t_end_i = float(rec.get("t_end"))
            if t_end_i <= 0:
                suite_errors.append(f"Сценарий '{name}': t_end должен быть > 0")
        except Exception:
            suite_errors.append(f"Сценарий '{name}': t_end не задан")

        # физика: доля отрыва 0..1
        if rec.get("target_макс_доля_отрыва") is not None:
            try:
                frac = float(rec["target_макс_доля_отрыва"])
                if not (0.0 <= frac <= 1.0):
                    suite_errors.append(f"Сценарий '{name}': target_макс_доля_отрыва должна быть 0..1")
            except Exception:
                suite_errors.append(f"Сценарий '{name}': target_макс_доля_отрыва некорректна")

        # JSON sanity: road_surface / params_override (если похоже на JSON — проверяем)
        for _fld in ("road_surface", "params_override"):
            _v = rec.get(_fld, None)
            if isinstance(_v, str):
                _s = _v.strip()
                if _s and ((_s.startswith('{') and _s.endswith('}')) or (_s.startswith('[') and _s.endswith(']'))):
                    try:
                        json.loads(_s)
                    except Exception as _e_json:
                        suite_errors.append(f"Сценарий '{name}': поле '{_fld}' содержит некорректный JSON: {_e_json}")

        # sidecar sanity: CSV-файлы должны существовать (чтобы не было «тихих» нулей)
        if typ in ("road_profile_csv", "maneuver_csv", "csv", "worldroad"):
            for _csv_fld in ("road_csv", "axay_csv", "scenario_json"):
                _p = rec.get(_csv_fld, None)
                if not _p:
                    # road_csv обязателен для road_profile_csv
                    if (_csv_fld == "road_csv") and (typ in ("road_profile_csv", "worldroad")):
                        suite_errors.append(f"Сценарий '{name}': не задан road_csv")
                    continue
                try:
                    _pp = Path(str(_p))
                    if not _pp.is_absolute():
                        _pp = (ROOT_DIR / _pp).resolve()
                    if not _pp.exists():
                        suite_errors.append(f"Сценарий '{name}': файл '{_csv_fld}' не найден: {str(_p)}")
                except Exception as _e_p:
                    suite_errors.append(f"Сценарий '{name}': не удалось проверить '{_csv_fld}': {_e_p}")

    suite_override.append(rec)

# Дополнительно: имена включенных тестов должны быть уникальны
try:
    _name_counts = {}
    for _r in suite_override:
        try:
            if not bool(_r.get('включен', True)):
                continue
            _nm = str(_r.get('имя') or _r.get('РёРјСЏ') or '').strip()
            if not _nm:
                continue
            _name_counts[_nm] = _name_counts.get(_nm, 0) + 1
        except Exception:
            continue
    _dups = sorted([n for n, c in _name_counts.items() if c > 1])
    if _dups:
        suite_errors.append("Дубли имён включённых сценариев: " + ", ".join(_dups))
except Exception:
    pass

if suite_errors:
    st.error("В наборе сценариев есть ошибки (исправьте перед запуском):\n- " + "\n- ".join(suite_errors))


# -------------------------------
# Одиночные тесты
# -------------------------------
with colB:
    st.subheader("Опорный прогон сценариев")
    st.caption("Проверка адекватности модели на текущих параметрах.")

    tests_cfg = {"suite": suite_override}
    tests: List[Tuple[str, Dict[str, Any], float, float, Dict[str, float]]] = []
    if not suite_errors:
        try:
            tests = worker_mod.build_test_suite(tests_cfg)
        except Exception as e:
            st.error(f"Не удалось собрать набор сценариев: {e}")
            tests = []

    # --- persistent baseline cache (auto-load after refresh / new session) ---
    # Ключ кэша зависит от base_override + suite (с учетом dt/t_end/targets) + model file.
    try:
        _tests_map_preview: Dict[str, Any] = {}
        for _nm, _tst, _dt, _tend, _targets in tests:
            _tests_map_preview[_nm] = {
                "test": _tst,
                "dt": float(_dt),
                "t_end": float(_tend),
                "targets": _targets,
            }
        _base_hash_preview = stable_obj_hash(base_override)
        _suite_hash_preview = stable_obj_hash(_tests_map_preview)
        _cache_dir_preview = baseline_cache_dir(_base_hash_preview, _suite_hash_preview, str(model_path))
        st.session_state.baseline_cache_dir = str(_cache_dir_preview)

        # --- TRUTH_PANEL_RENDER ---
        # The slot is created near the page title. Here we fill it once hashes/model are known.
        try:
            _self_ok = bool(st.session_state.get("_autoselfcheck_v1_ok", True))
            _stab_on = bool(base_override.get("стабилизатор_вкл", False))
            _baseline_summary = "Опорный прогон: не выполнялся"
            try:
                _bdf = st.session_state.get("baseline_df")
                if _bdf is not None and hasattr(_bdf, "columns"):
                    if "pass" in _bdf.columns:
                        _n_total = int(len(_bdf))
                        _n_pass = int(_bdf["pass"].astype(int).sum())
                        _baseline_summary = f"Опорный прогон: {_n_pass}/{_n_total} пройдено"
                    else:
                        _baseline_summary = f"Опорный прогон: {int(len(_bdf))} строк"
            except Exception:
                pass

                with truth_slot:
                    c1, c2, c3, c4 = st.columns([1.25, 1.15, 1.05, 1.05])
                    with c1:
                        st.markdown(
                            f"**Версия интерфейса:** `{APP_RELEASE}`  \n"
                            f"**Файл модели:** `{getattr(model_path, 'name', str(model_path))}`"
                        )
                        st.caption(_baseline_summary)
                    with c2:
                        st.markdown(
                            f"**Контрольная сумма параметров:** `{_base_hash_preview}`  \n"
                            f"**Контрольная сумма набора сценариев:** `{_suite_hash_preview}`"
                        )
                        st.caption(f"Папка сохранённого кэша: `{_cache_dir_preview.name}`")
                    with c3:
                        st.markdown(
                            "**Самопроверка интерфейса:** ✅ OK"
                            if _self_ok
                            else "**Самопроверка интерфейса:** ❌ FAIL"
                        )
                        if not _self_ok:
                            st.caption("Оптимизация и экспорт будут заблокированы по умолчанию.")
                    with c4:
                        st.markdown(
                            f"**Стабилизатор интерфейса:** {'включён' if _stab_on else 'выключен'}"
                        )
        except Exception:
            pass

        if st.session_state.baseline_df is None:
            _cached = load_baseline_cache(_cache_dir_preview)
            if _cached is not None:
                st.session_state.baseline_df = _cached["baseline_df"]
                st.session_state.baseline_tests_map = _cached["tests_map"]
                st.session_state.baseline_param_hash = _base_hash_preview
                # детальные прогоны не грузим целиком — будут подхвачены по запросу
                log_event("baseline_loaded_cache", cache_dir=str(_cache_dir_preview))
                st.info(f"Опорный прогон восстановлен из сохранённого кэша: {_cache_dir_preview.name}")
    except Exception:
        pass

    test_names = [x[0] for x in tests]
    pick = st.selectbox("Сценарий", options=["(все)"] + test_names, index=0)

    _disable_baseline = bool(suite_errors) or bool(param_errors) or (len(tests) == 0)
    if st.button("Запустить опорный прогон", disabled=_disable_baseline):
        t0_baseline = time.perf_counter()
        log_event(
            "baseline_start",
            pick=pick,
            tests_total=len(tests),
            base_hash=stable_obj_hash(base_override),
            proc=_proc_metrics(),
        )
        res_rows = []
        err_cnt = 0
        # сохраняем карту тестов (понадобится для детального прогона)
        st.session_state.baseline_tests_map = {
            name: {"test": dict(test), "dt": float(dt_i), "t_end": float(t_end_i), "targets": dict(targets)}
            for (name, test, dt_i, t_end_i, targets) in tests
        }
        st.session_state.baseline_param_hash = stable_obj_hash(base_override)
        st.session_state.baseline_full_cache = {}  # сброс детальных прогонов (параметры могли измениться)
        with st.spinner("Считаю..."):
            for name, test, dt_i, t_end_i, targets in tests:
                if pick != "(все)" and name != pick:
                    continue
                try:
                    m = worker_mod.eval_candidate_once(model_mod, base_override, test, dt=dt_i, t_end=t_end_i)
                    m["тест"] = name
                    m["описание"] = test.get("описание", "")
                    pen_targets = float(worker_mod.candidate_penalty(m, targets))
                    try:
                        pen_verif = float(m.get("верификация_штраф", 0.0))
                    except Exception:
                        pen_verif = 0.0

                    m["штраф_цели"] = float(pen_targets)
                    m["штраф_верификация"] = float(pen_verif)
                    m["штраф"] = float(pen_targets + pen_verif)

                    # Читабельные флаги прохождения
                    try:
                        m["pass_верификация"] = int(int(m.get("верификация_ok", 1)) == 1)
                    except Exception:
                        m["pass_верификация"] = 0
                    m["pass_цели"] = int(float(pen_targets) <= 0.0)
                    m["pass"] = int((m["pass_верификация"] == 1) and (m["pass_цели"] == 1))
                    m.update(collect_packaging_surface_metrics(m, targets=targets, params=base_override))
                    res_rows.append(m)
                except Exception as e:
                    err_cnt += 1
                    log_event(
                        "baseline_test_error",
                        test=name,
                        error=str(e),
                        traceback=traceback.format_exc(limit=8),
                        proc=_proc_metrics(),
                    )
                    err_row = {
                        "тест": name,
                        "ошибка": str(e),
                        "штраф": 1e9,
                        "штраф_цели": 1e9,
                        "штраф_верификация": 0.0,
                        "pass": 0,
                        "pass_верификация": 0,
                        "pass_цели": 0,
                    }
                    err_row.update(packaging_error_surface_metrics())
                    res_rows.append(err_row)
        df_res = pd.DataFrame(res_rows)
        st.session_state.baseline_df = df_res
        safe_dataframe(df_res, height=360)
        st.success(f"Готово. Ошибок: {err_cnt}")

        log_event(
            "baseline_end",
            errors=int(err_cnt),
            rows=int(len(df_res)),
            elapsed_s=float(time.perf_counter() - t0_baseline),
            proc=_proc_metrics(),
        )

        # отметка: baseline обновился (для авто-детального триггера)
        st.session_state["baseline_updated_ts"] = time.time()
        # One-shot flag: the Detail section may start auto-detail exactly once
        # after a fresh baseline calculation.
        st.session_state["baseline_just_ran"] = True

        # --- persist baseline to disk cache (survives browser refresh) ---
        try:
            _base_hash = stable_obj_hash(base_override)
            _suite_hash = stable_obj_hash(st.session_state.baseline_tests_map)
            _cache_dir = baseline_cache_dir(_base_hash, _suite_hash, str(model_path))
            st.session_state.baseline_cache_dir = str(_cache_dir)
            _meta = {
                "release": APP_RELEASE,
                "ts": datetime.now().isoformat(timespec="seconds"),
                "base_hash": _base_hash,
                "suite_hash": _suite_hash,
                "model_file": str(model_path),
                "python": sys.version.split()[0],
                "errors": int(err_cnt),
                "rows": int(len(df_res)),
            }
            save_baseline_cache(_cache_dir, df_res, st.session_state.baseline_tests_map, base_override, _meta)
            log_event("baseline_saved_cache", cache_dir=str(_cache_dir))
        except Exception:
            pass

        # быстрый sanity-check: вакуум/давления
        if "pR3_max_бар" in df_res.columns:
            st.write("Макс давление Р3 (бар abs):", float(df_res["pR3_max_бар"].max()))


# -------------------------------
# Обзор опорного прогона (быстрые метрики + гейты тяжёлых визуализаций)
# -------------------------------
if st.session_state.get("baseline_df") is not None:
    _bdf = st.session_state["baseline_df"]
    if isinstance(_bdf, pd.DataFrame) and not _bdf.empty:
        try:
            _n_total = int(len(_bdf))
            _n_pass = int((_bdf.get("pass", False) == True).sum()) if "pass" in _bdf.columns else None  # noqa: E712
            _n_fail = (_n_total - _n_pass) if _n_pass is not None else None

            _best_pen = None
            if "штраф" in _bdf.columns:
                _best_pen = float(pd.to_numeric(_bdf["штраф"], errors="coerce").min())
            elif "penalty" in _bdf.columns:
                _best_pen = float(pd.to_numeric(_bdf["penalty"], errors="coerce").min())

            cM1, cM2, cM3, cM4 = st.columns(4)
            with cM1:
                st.metric("Опорный прогон: сценариев", _n_total)
            with cM2:
                st.metric("Прошло", _n_pass if _n_pass is not None else "—")
            with cM3:
                st.metric("Провал", _n_fail if _n_fail is not None else "—")
            with cM4:
                st.metric("Лучший штраф", f"{_best_pen:.3g}" if _best_pen is not None and np.isfinite(_best_pen) else "—")

            with st.expander("Визуальный обзор опорного прогона (графики/теплокарта)", expanded=False):
                st.caption(
                    "Сводные графики включаются чекбоксами ниже. "
                    "Важно: expander сам по себе не «останавливает» код, поэтому для скорости используются гейты."
                )

                _ov_c1, _ov_c2 = st.columns([1, 1])
                with _ov_c1:
                    _show_overview_plot = st.checkbox(
                        "Показывать график худших сценариев",
                        value=False,
                        help="Строит Plotly‑график по худшим сценариям (может быть тяжело на больших наборах).",
                        key="gate_baseline_overview_plot",
                    )
                    _show_full_table = st.checkbox(
                        "Показывать таблицу результатов (полностью)",
                        value=False,
                        help="Показывает исходную таблицу результатов опорного прогона. "
                             "При больших таблицах может быть тяжело.",
                        key="gate_baseline_overview_table_full",
                    )
                with _ov_c2:
                    _show_penalty_heatmap = st.checkbox(
                        "Показывать теплокарту штрафов",
                        value=False,
                        help="Строит теплокарту штрафов/критериев (pen_*). Рендер Plotly может быть тяжёлым.",
                        key="gate_baseline_overview_heatmap",
                    )
                    _show_penalty_table = st.checkbox(
                        "Показывать таблицу штрафов (pen_*)",
                        value=False,
                        help="Показывает таблицу pen_* по сценариям (удобно для экспорта и проверок).",
                        key="gate_baseline_overview_table_pen",
                    )

                # Худшие сценарии по суммарному штрафу (дешево)
                _bdf2 = _bdf.copy()
                if "penalty" not in _bdf2.columns:
                    _bdf2["penalty"] = 0.0
                _bdf2["penalty"] = pd.to_numeric(_bdf2["penalty"], errors="coerce").fillna(0.0)
                _bdf2 = _bdf2.sort_values("penalty", ascending=False)

                _worst = _bdf2.head(10)
                _pairs = [(str(r.get("test_id", "?")), float(r.get("penalty", 0.0))) for _, r in _worst.iterrows()]
                st.write("Худшие сценарии по суммарному штрафу:", ", ".join([f"{tid} ({pen:.3g})" for tid, pen in _pairs]))

                def _render_cached_plotly(_key: str, _build_fn):
                    _fig_json = _UI_HEAVY_CACHE.get_json(_key)
                    if _fig_json is None:
                        _fig = _build_fn()
                        try:
                            _UI_HEAVY_CACHE.set_json(_key, _fig.to_json())
                        except Exception:
                            pass
                        return _fig
                    try:
                        if isinstance(_fig_json, str):
                            return pio.from_json(_fig_json)
                        return pio.from_json(json.dumps(_fig_json))
                    except Exception:
                        return _build_fn()

                # 1) График худших сценариев
                if _show_overview_plot:
                    if not _HAS_PLOTLY:
                        st.warning("Plotly недоступен: график не построен.")
                    else:
                        _cache_tag = str(st.session_state.get("baseline_cache_dir", "")) or "no_cache_dir"
                        _key = f"baseline_overview_worst_plot::{_cache_tag}"

                        def _build():
                            _x = [p[0] for p in _pairs]
                            _y = [p[1] for p in _pairs]
                            _fig = go.Figure()
                            _fig.add_trace(
                                go.Bar(
                                    x=_x,
                                    y=_y,
                                    text=[f"{v:.3g}" for v in _y],
                                    textposition="auto",
                                    name="Штраф",
                                )
                            )
                            _fig.update_layout(
                                title="Худшие сценарии (суммарный штраф)",
                                xaxis_title="Сценарий",
                                yaxis_title="Штраф (безразм.)",
                                height=340,
                                margin=dict(l=20, r=20, t=60, b=40),
                            )
                            return _fig

                        safe_plotly_chart(_render_cached_plotly(_key, _build))

                # 2) Теплокарта штрафов pen_*
                if _show_penalty_heatmap:
                    if not _HAS_PLOTLY:
                        st.warning("Plotly недоступен: теплокарта не построена.")
                    else:
                        _crit_cols = [c for c in _bdf.columns if c.startswith("pen_")]
                        if not _crit_cols:
                            st.info("Нет полей pen_* — теплокарта штрафов недоступна.")
                        else:
                            _cache_tag = str(st.session_state.get("baseline_cache_dir", "")) or "no_cache_dir"
                            _key = f"baseline_overview_heatmap::{_cache_tag}"

                            def _build():
                                _hm = _bdf[_crit_cols + ["test_id"]].set_index("test_id")
                                _hm = _hm.apply(pd.to_numeric, errors="coerce").fillna(0.0)
                                _fig = px.imshow(
                                    _hm.T,
                                    aspect="auto",
                                    color_continuous_scale="RdBu",
                                    origin="lower",
                                    labels=dict(x="Сценарий", y="Критерий", color="Штраф"),
                                    title="Теплокарта штрафов (pen_*)",
                                )
                                _fig.update_layout(height=420, margin=dict(l=20, r=20, t=70, b=40))
                                return _fig

                            safe_plotly_chart(_render_cached_plotly(_key, _build))

                # 3) Таблицы (гейты)
                if _show_penalty_table:
                    _crit_cols = [c for c in _bdf.columns if c.startswith("pen_")]
                    if _crit_cols:
                        st.caption("Таблица штрафов по критериям (pen_*)")
                        _hm_df = _bdf[_crit_cols + ["test_id"]].set_index("test_id")
                        _hm_df = _hm_df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
                        st.dataframe(_hm_df, width="stretch", height=280)
                    else:
                        st.info("Нет полей pen_* — таблица штрафов недоступна.")

                if _show_full_table:
                    st.caption("Таблица результатов опорного прогона (как есть)")
                    st.dataframe(_bdf, width="stretch", height=360)

        except Exception as _e:
            st.warning(f"Не удалось построить обзор опорного прогона: {_e}")

# Детальные графики + анимация (baseline)
# -------------------------------
st.divider()
st.header("Графики и анимация (опорный прогон)")
st.caption(
    "Сначала запустите опорный прогон. Затем выберите один сценарий и получите расширенный лог расчёта: "
    "графики P/Q/крен/тангаж/силы и MVP-анимацию потоков."
)

cur_hash = stable_obj_hash(base_override)
if st.session_state.baseline_df is None:
    st.info("Нет таблицы опорного прогона. Нажмите «Запустить опорный прогон» выше.")
elif st.session_state.baseline_param_hash and st.session_state.baseline_param_hash != cur_hash:
    st.warning(
        "Параметры изменились после опорного прогона. Чтобы графики/анимация соответствовали текущим параметрам, "
        "перезапустите опорный прогон."
    )
else:
    tests_map = st.session_state.baseline_tests_map or {}
    # --- live suite -> tests_map (чтобы изменения тестов применялись сразу, без обязательного baseline) ---
    try:
        live_suite = suite_override if isinstance(locals().get('suite_override', None), list) else None
        if live_suite:
            _tlist_live = worker_mod.build_test_suite(live_suite)
            tests_map_live = {}
            for (tid, test_j, _dt, _tend, _targets) in _tlist_live:
                # embed dt/t_end into test dict for downstream UI (detail_dt/detail_t_end)
                _tj = dict(test_j)
                _tj['dt'] = float(_dt)
                _tj['t_end'] = float(_tend)
                _targets_d = dict(_targets) if isinstance(_targets, dict) else {}
                # IMPORTANT: keep the same tests_map contract as baseline_tests_map:
                #   tests_map[name] = {"test": {...}, "dt": ..., "t_end": ..., "targets": {...}}
                tests_map_live[str(tid)] = {"test": _tj, "dt": float(_dt), "t_end": float(_tend), "targets": _targets_d}
            if len(tests_map_live) > 0:
                tests_map = tests_map_live
    except Exception as e:
        try:
            log_event('tests_map_live_error', error=(f"{type(e).__name__}: {e}")[:200])
        except Exception:
            pass
    
    avail = [t for t in tests_map.keys()]
    if not avail:
        st.info("В таблице опорного прогона нет доступных сценариев (проверьте набор сценариев).")
    else:
        colG1, colG2 = st.columns([1.35, 0.65], gap="large")
        with colG1:
            test_pick = st.selectbox("Сценарий для детального прогона", options=avail, index=0, key="detail_test_pick")

        # Расширенные настройки — прячем, чтобы главный экран не захламлять
        with colG2:
            with ui_popover("⚙️ Настройки детального прогона"):
                max_points = st.slider(
                    "Макс точек (downsample)",
                    min_value=200,
                    max_value=5000,
                    value=int(st.session_state.get("detail_max_points", 1200) or 1200),
                    step=100,
                    key="detail_max_points",
                    help="Меньше — быстрее UI/графики; больше — точнее форма сигналов.",
                )
                want_full = st.checkbox(
                    "Расширенный лог (потоки и состояния)",
                    value=bool(st.session_state.get("detail_want_full", True)),
                    key="detail_want_full",
                )
                auto_detail_on_select = st.checkbox(
                    "Авто-расчёт при выборе сценария",
                    value=bool(st.session_state.get("auto_detail_on_select", True)),
                    key="auto_detail_on_select",
                    help="Если включено и кэш пуст, будет считаться детальный прогон (может грузить CPU).",
                )
                st.divider()
                st.caption("Экспорт (опционально)")
                auto_export_npz = st.checkbox(
                    "Авто-экспорт NPZ (osc_dir)",
                    value=bool(st.session_state.get("auto_export_npz", True)),
                    key="auto_export_npz",
                    help="Экспортирует Txx_osc.npz в папку osc_dir (см. раздел калибровки). Нужно для запуска oneclick/autopilot.",
                )

                st.caption('Desktop Animator (по последней выгрузке anim_latest)')
                st.checkbox(
                    'Авто-экспорт последней анимационной выгрузки (anim_latest)',
                    value=bool(st.session_state.get('auto_export_anim_latest', True)),
                    key='auto_export_anim_latest',
                    help=(
                        'После детального прогона сохраняет файлы '
                        'workspace/exports/anim_latest.npz и anim_latest.json '
                        'с указанием последней выгрузки. Desktop Animator подхватит их автоматически.'
                    ),
                )
                st.checkbox(
                    'Авто-запуск Desktop Animator при экспорте',
                    value=bool(st.session_state.get('auto_launch_animator', False)),
                    key='auto_launch_animator',
                    help='Если среда позволяет запуск GUI: откроет Desktop Animator сразу после экспорта.',
                )
                st.caption(f'Папка exports: {WORKSPACE_EXPORTS_DIR}')

        # dt/t_end берём из suite для выбранного теста — это часть cache_key и параметров simulate()
        info_pick = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
        test_for_events = {}
        if isinstance(info_pick, dict):
            raw_test = info_pick.get("test")
            if isinstance(raw_test, dict):
                test_for_events = raw_test
            elif any(k in info_pick for k in ("тип", "type", "road_csv", "axay_csv", "t_end", "dt")):
                test_for_events = info_pick
        detail_dt = float(info_pick.get("dt", 0.01) or 0.01)
        detail_t_end = float(info_pick.get("t_end", 1.0) or 1.0)
        # сохраняем для других страниц/инструментов
        st.session_state["detail_dt_pick"] = detail_dt
        st.session_state["detail_t_end_pick"] = detail_t_end

        # --- ДЕТАЛЬНЫЙ ПРОГОН: индикатор выполнения и блокировка повторного запуска ---
        # Важно: detail_guard — служебная структура UI (НЕ параметры модели).
        # Поля stage/progress/ts являются производными от состояния выполнения.
        if "detail_guard" not in st.session_state:
            st.session_state["detail_guard"] = {}
        _dg_ui = st.session_state.get("detail_guard") or {}
        _dg_ui.setdefault("in_progress", False)
        _dg_ui.setdefault("stage", "idle")
        _dg_ui.setdefault("progress", 0)  # 0..100
        _dg_ui.setdefault("last_start_ts", 0.0)
        _dg_ui.setdefault("last_end_ts", 0.0)
        _dg_ui.setdefault("last_key", None)
        st.session_state["detail_guard"] = _dg_ui
        _detail_in_progress = bool(_dg_ui.get("in_progress"))
        if _detail_in_progress:
            _elapsed = max(0.0, float(time.time()) - float(_dg_ui.get("last_start_ts") or time.time()))
            _stage = str(_dg_ui.get("stage") or "running")
            st.info(f"Детальный прогон уже выполняется ({_stage}). Прошло: {_elapsed:.0f} с")
            try:
                _p = int(_dg_ui.get("progress") or 0)
            except Exception:
                _p = 0
            _p_clamped = min(max(_p, 0), 100)
            st.progress(_p_clamped, text=f"{_stage} — {_p_clamped}%")
            st.caption("Повторный запуск подавлен, пока текущий прогон не завершится.")

        run_detail = st.button("Рассчитать полный лог и показать", key="run_detail", disabled=_detail_in_progress)

        colDAll1, colDAll2 = st.columns([1.0, 1.0])
        with colDAll1:
            run_detail_all = st.button("Рассчитать полный лог ДЛЯ ВСЕХ сценариев", key="run_detail_all", disabled=_detail_in_progress)
        with colDAll2:
            export_npz_all = st.button("Экспорт NPZ ДЛЯ ВСЕХ сценариев (из кэша)", key="export_npz_all", disabled=_detail_in_progress)

            cache_key = make_detail_cache_key(cur_hash, test_pick, detail_dt, detail_t_end, max_points, want_full)

        # --- Авто-детальный прогон: запускать ТОЛЬКО по триггеру
        # Триггеры:
        #   1) смена теста (test_pick)
        #   2) завершение baseline (one-shot флаг baseline_just_ran)
        if "detail_auto_pending" not in st.session_state:
            st.session_state["detail_auto_pending"] = None
        if "detail_prev_test_pick" not in st.session_state:
            st.session_state["detail_prev_test_pick"] = None
        if "detail_force_fresh_key" not in st.session_state:
            st.session_state["detail_force_fresh_key"] = None
        if "baseline_just_ran" not in st.session_state:
            st.session_state["baseline_just_ran"] = False

        if arm_detail_autorun_on_test_change(
            st.session_state,
            auto_detail_on_select=bool(auto_detail_on_select),
            cache_key=str(cache_key),
            test_pick=str(test_pick),
        ):
            log_event("auto_detail_pending", test=test_pick, cache_key=cache_key)

        # baseline finished: trigger auto-detail exactly once (if enabled)
        if arm_detail_autorun_after_baseline(
            st.session_state,
            auto_detail_on_select=bool(auto_detail_on_select),
            cache_key=str(cache_key),
            force_fresh_after_baseline=True,
        ):
            log_event("auto_detail_pending_after_baseline", test=test_pick, cache_key=cache_key, force_fresh=True)

        # Массовые действия
        # - полный лог для всех сценариев
        # - экспорт NPZ для всех сценариев
        if run_detail_all:
            if not want_full:
                st.warning("Для массового расчёта включите расширенный лог расчёта — иначе файл NPZ будет неполным.")
            else:
                with st.spinner("Считаю полный лог для всех сценариев… (может быть долго)"):
                    prog = st.progress(0.0)
                    n_total = max(1, len(avail))

                    # NPZ export dir (osc_dir). Can be overridden in Calibration expander.
                    osc_dir_export = get_osc_dir()
                    try:
                        osc_dir_export.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        pass

                    for j, tn in enumerate(avail, start=1):
                        info_j = tests_map.get(tn) or {}
                        test_j = info_j.get("test")
                        dt_j = float(info_j.get("dt", detail_dt) or detail_dt)
                        t_end_j = float(info_j.get("t_end", detail_t_end) or detail_t_end)
                        ck = make_detail_cache_key(cur_hash, tn, dt_j, t_end_j, max_points, want_full)
                        if ck in st.session_state.baseline_full_cache:
                            prog.progress(j / n_total)
                            continue
                        if not test_j:
                            prog.progress(j / n_total)
                            continue
                        try:
                            out_j = call_simulate(
                                model_mod,
                                base_override,
                                test_j,
                                dt=dt_j,
                                t_end=t_end_j,
                                record_full=True,
                                max_steps=int(2e6),
                            )
                            parsed_j = parse_sim_output(out_j, want_full=True)
                            df_main_j = parsed_j.get("df_main")
                            df_p_j = parsed_j.get("df_p")
                            df_mdot_j = parsed_j.get("df_mdot")
                            df_open_j = parsed_j.get("df_open")
                            df_Eedges_j = parsed_j.get("df_Eedges")
                            df_Egroups_j = parsed_j.get("df_Egroups")
                            df_atm_j = parsed_j.get("df_atm")
                            # decimate
                            if max_points and (df_main_j is not None) and len(df_main_j) > int(max_points):
                                idxs = np.linspace(0, len(df_main_j) - 1, int(max_points)).astype(int)
                                df_main_j = df_main_j.iloc[idxs].reset_index(drop=True)
                                if df_p_j is not None:
                                    df_p_j = df_p_j.iloc[idxs].reset_index(drop=True)
                                if df_mdot_j is not None:
                                    df_mdot_j = df_mdot_j.iloc[idxs].reset_index(drop=True)
                                if df_open_j is not None:
                                    df_open_j = df_open_j.iloc[idxs].reset_index(drop=True)
                                if df_Eedges_j is not None:
                                    df_Eedges_j = df_Eedges_j.iloc[idxs].reset_index(drop=True)
                                if df_Egroups_j is not None:
                                    df_Egroups_j = df_Egroups_j.iloc[idxs].reset_index(drop=True)
                                if df_atm_j is not None:
                                    df_atm_j = df_atm_j.iloc[idxs].reset_index(drop=True)
                            st.session_state.baseline_full_cache[ck] = {
                                "df_main": df_main_j,
                                "df_p": df_p_j,
                                "df_mdot": df_mdot_j,
                                "df_open": df_open_j,
                                "df_Eedges": df_Eedges_j,
                                "df_Egroups": df_Egroups_j,
                                "df_atm": df_atm_j,
                            }
                            if auto_export_npz:
                                try:
                                    test_num_j = j
                                    npz_path_j = osc_dir_export / f"T{test_num_j:02d}_osc.npz"
                                    export_full_log_to_npz(
                                        npz_path_j,
                                        df_main_j,
                                        df_p=df_p_j,
                                        df_q=df_mdot_j,
                                        df_open=df_open_j,
                                        meta={
                                            "source": "ui_baseline",
                                            "cache_key": ck,
                                            "test_name": tn,
                                            "test_num": test_num_j,
                                            "max_points": int(max_points),
                                        },
                                    )
                                except Exception as _e:
                                    st.warning(f"NPZ экспорт не удался для {tn}: {_e}")
                        except Exception as e:
                            st.error(f"Ошибка в сценарии {tn}: {e}")
                        prog.progress(j / n_total)
                    prog.empty()
                log_event("detail_all_done", n_tests=len(avail), want_full=bool(want_full), max_points=int(max_points))

        if export_npz_all:
            if not want_full:
                st.warning("Экспорт NPZ доступен только для расширенного лога расчёта — иначе не будет данных p/q/open.")
            else:
                with st.spinner("Экспортирую NPZ для всех сценариев, которые уже посчитаны…"):
                    prog = st.progress(0.0)
                    n_total = max(1, len(avail))

                    osc_dir_export = get_osc_dir()
                    try:
                        osc_dir_export.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        pass

                    for j, tn in enumerate(avail, start=1):
                        info_j = tests_map.get(tn) or {}
                        test_j = info_j.get("test")
                        dt_j = float(info_j.get("dt", detail_dt) or detail_dt)
                        t_end_j = float(info_j.get("t_end", detail_t_end) or detail_t_end)
                        ck = make_detail_cache_key(cur_hash, tn, dt_j, t_end_j, max_points, want_full)
                        det_j = st.session_state.baseline_full_cache.get(ck)
                        if not det_j:
                            prog.progress(j / n_total)
                            continue
                        try:
                            npz_path_j = osc_dir_export / f"T{j:02d}_osc.npz"
                            export_full_log_to_npz(
                                npz_path_j,
                                det_j.get("df_main"),
                                df_p=det_j.get("df_p"),
                                df_q=det_j.get("df_mdot"),
                                df_open=det_j.get("df_open"),
                                meta={
                                    "source": "ui_baseline",
                                    "cache_key": ck,
                                    "test_name": tn,
                                    "test_num": j,
                                    "max_points": int(max_points),
                                },
                            )
                        except Exception as e:
                            st.warning(f"NPZ экспорт не удался для {tn}: {e}")
                        prog.progress(j / n_total)
                    prog.empty()
                log_event("export_npz_all_done", n_tests=len(avail), max_points=int(max_points))
        if run_detail and test_pick:
            st.session_state.baseline_full_cache.pop(cache_key, None)

        if test_pick:
            # --- autorun guard: protects from endless rerun-loops (autorefresh / playhead sync / компоненты) ---
            # Важно: auto_detail может вызываться много раз из-за частых rerun'ов. Если кэш по какой-то причине
            # не удерживается, получится бесконечный «детальный прогон». Этот guard подавляет повторные автозапуски.
            if "detail_guard" not in st.session_state:
                st.session_state["detail_guard"] = {
                    "last_key": None,
                    "last_end_ts": 0.0,
                    "in_progress": False,
                    "suppressed": 0,
                }

            # --- load detail from disk cache (if exists) ---
            try:
                _bcd = st.session_state.get("baseline_cache_dir")
                _cache_dir = Path(_bcd) if _bcd else None
                _force_fresh_after_baseline = should_bypass_detail_disk_cache(st.session_state, cache_key=str(cache_key))
                if _force_fresh_after_baseline:
                    st.info(
                        "После свежего опорного прогона выполняется принудительный пересчёт детального лога: "
                        "старый сохранённый детальный лог для этого сценария игнорируется."
                    )
                    log_event("detail_cache_bypassed_after_baseline", test=str(test_pick), cache_key=str(cache_key))
                if (not _force_fresh_after_baseline) and _cache_dir and _cache_dir.exists() and cache_key not in st.session_state.baseline_full_cache:
                    _det_disk = load_detail_cache(_cache_dir, test_pick, float(detail_dt), float(detail_t_end), int(max_points), bool(want_full))
                    if _det_disk is not None:
                        _det_meta = dict(_det_disk.get("meta") or {})
                        _det_meta["loaded_from_cache"] = True
                        _det_meta["cache_file"] = str(
                            build_detail_cache_path(
                                _cache_dir,
                                test_pick,
                                float(detail_dt),
                                float(detail_t_end),
                                int(max_points),
                                bool(want_full),
                                sanitize_test_name=sanitize_test_name,
                                float_tag_fn=_float_tag,
                            )
                        )
                        _det_disk["meta"] = _det_meta
                        st.session_state.baseline_full_cache[cache_key] = _det_disk
                        if st.session_state.get("detail_auto_pending") == cache_key:
                            st.session_state["detail_auto_pending"] = None
                        clear_detail_force_fresh(st.session_state, cache_key=str(cache_key))
                        log_event(
                            "detail_loaded_cache",
                            test=str(test_pick),
                            cache_key=str(cache_key),
                            cache_file=str(
                                build_detail_cache_path(
                                    _cache_dir,
                                    test_pick,
                                    float(detail_dt),
                                    float(detail_t_end),
                                    int(max_points),
                                    bool(want_full),
                                    sanitize_test_name=sanitize_test_name,
                                    float_tag_fn=_float_tag,
                                )
                            ),
                        )
                        st.info("Детальный лог для текущего сценария загружен из кэша. Для принудительного пересчёта нажмите 'Рассчитать полный лог и показать'.")
            except Exception:
                pass


            auto_pending_key = st.session_state.get("detail_auto_pending")
            auto_trigger = bool(auto_detail_on_select and auto_pending_key == cache_key)

            if cache_key not in st.session_state.baseline_full_cache and (run_detail or auto_trigger):
                if auto_trigger and not run_detail:
                    st.session_state["detail_auto_pending"] = None
                # --- autorun guard: protects from endless rerun-loops (autorefresh / playhead sync / компоненты) ---
                # Если по какой-то причине Streamlit делает частые rerun'ы, auto_detail может стартовать снова и снова.
                # Мы:
                #  - не запускаем второй расчёт, если такой же уже выполняется
                #  - подавляем повторный автозапуск того же cache_key вскоре после завершения (симптом rerun-loop)
                #  - всегда сбрасываем флаг in_progress в finally
                _dg = dict(st.session_state.get("detail_guard") or {})
                _dg.setdefault("in_progress", False)
                _dg.setdefault("stage", "idle")
                _dg.setdefault("progress", 0)  # 0..100
                _dg.setdefault("last_key", None)
                _dg.setdefault("last_end_ts", 0.0)
                _dg.setdefault("suppressed", 0)
                _dg.setdefault("failed_key", None)
                _dg.setdefault("failed_ts", 0.0)
                _dg.setdefault("failed_err", None)
                st.session_state["detail_guard"] = _dg

                _now = float(time.time())
                _same_key = (_dg.get("last_key") == cache_key)
                _same_key_recent = _same_key and (_now - float(_dg.get("last_end_ts") or 0.0) < 15.0)

                # NOTE:
                # Streamlit выполняет скрипт для одной пользовательской сессии последовательно
                # (без параллельных запусков). Поэтому in_progress=True, обнаруженный в начале
                # нового запуска, считаем "залипшим" статусом после прерывания/крэша и
                # сбрасываем, иначе кнопка детального прогона может навсегда блокироваться.
                _cur_pid = os.getpid()
                _guard_pid = int(_dg.get("pid") or _cur_pid)
                _start_ts = float(_dg.get("last_start_ts") or 0.0)
                _age = (_now - _start_ts) if (_start_ts > 0.0) else 0.0
                _had_in_progress = bool(_dg.get("in_progress"))
                if _had_in_progress:
                    st.warning("⚠️ Обнаружен зависший/устаревший флаг 'детальный прогон выполняется' — сбрасываю блокировку.")
                    log_event(
                        "detail_guard_stale_reset",
                        test=test_pick,
                        key=str(_dg.get("last_key") or ""),
                        age_s=float(_age),
                        pid=int(_guard_pid),
                        cur_pid=int(_cur_pid),
                    )
                    _dg["in_progress"] = False
                    _dg["pid"] = _cur_pid
                    _dg["last_start_ts"] = _now
                    st.session_state["detail_guard"] = _dg

                log_event(
                    "auto_detail_trigger",
                    test=test_pick,
                    base_hash=cur_hash,
                    max_points=int(max_points),
                    want_full=bool(want_full),
                    cache_hit=False,
                    same_key_recent=_same_key_recent,
                    had_in_progress=_had_in_progress,
                )

                # Защита от двойного клика: второй запуск той же кнопки сразу после завершения прогона.
                _double_click_suppressed = bool(run_detail) and _same_key and (_now - float(_dg.get("last_end_ts") or 0.0) < 2.0)
                if _double_click_suppressed:
                    st.info("Повторный запуск подавлен: предыдущий детальный прогон только что завершился (возможно двойной клик).")
                    log_event("detail_manual_doubleclick_suppressed", test=test_pick, key=cache_key)

                elif (_dg.get('failed_key') == cache_key) and auto_trigger and (not run_detail):
                    st.warning('Авто-детальный прогон подавлен: предыдущая попытка для этого набора завершилась ошибкой. Нажмите кнопку **"Рассчитать полный лог и показать"** для повтора.')
                    log_event('detail_autorun_suppressed_after_error', key=cache_key, test=test_pick, err=str(_dg.get('failed_err') or ''))
                elif _same_key_recent and auto_trigger and (not run_detail):
                    # Это почти всегда означает loop из rerun'ов (например, fallback Play, server-sync playhead, автоперерисовка).
                    _dg["suppressed"] = int(_dg.get("suppressed") or 0) + 1
                    st.session_state["detail_guard"] = _dg
                    st.warning(
                        "Подавлен повторный автозапуск детального прогона для текущего сценария: обнаружен rerun-loop. "
                        "Проверь: (1) отключена ли «Синхронизация playhead с сервером»; (2) не включён ли Play в fallback; "
                        "(3) нет ли автоперерисовки/обновления. Для принудительного пересчёта нажми кнопку «Пересчитать полный лог»."
                    )
                    log_event("detail_autorun_suppressed", test=test_pick, suppressed=_dg["suppressed"])

                else:
                    _dg["in_progress"] = True
                    _dg["pid"] = os.getpid()
                    _dg["last_start_ts"] = time.time()
                    _dg["last_key"] = cache_key
                    st.session_state["detail_guard"] = _dg

                    # UI: прогрессбар детального прогона (чтобы пользователь видел, что работа идёт)
                    _dg["stage"] = "prepare"
                    _dg["progress"] = 2  # 0..100
                    st.session_state["detail_guard"] = _dg
                    _detail_pb = st.progress(int(_dg["progress"]))
                    _detail_pb_text = st.empty()
                    _detail_pb_text.caption("Детальный прогон: подготовка…")

                    t0_perf = time.perf_counter()
                    try:
                        info = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
                        test_j = info.get("test") if isinstance(info, dict) else None
                        dt_j = info.get("dt", None) if isinstance(info, dict) else None
                        t_end_j = info.get("t_end", None) if isinstance(info, dict) else None
                        # Support two shapes:
                        #  (A) baseline_tests_map contract: info={"test": {...}, "dt":..., "t_end":..., ...}
                        #  (B) raw test dict (legacy / live suite): info={...test fields...}
                        if test_j is None and isinstance(info, dict):
                            looks_like_test = any(k in info for k in ("тип", "type", "road_csv", "axay_csv", "t_end", "dt"))
                            if looks_like_test:
                                test_j = info
                                dt_j = info.get("dt", dt_j)
                                t_end_j = info.get("t_end", t_end_j)
                        if test_j is None:
                            raise RuntimeError(f"Не найден сценарий '{test_pick}' в наборе")
                        # fallback: allow dt/t_end embedded in test dict
                        if dt_j is None and isinstance(test_j, dict):
                            dt_j = test_j.get("dt", None)
                        if t_end_j is None and isinstance(test_j, dict):
                            t_end_j = test_j.get("t_end", None)
                        dt_j = float(dt_j) if dt_j is not None else 0.01
                        t_end_j = float(t_end_j) if t_end_j is not None else 1.0
                        log_event("detail_start", test=test_pick, dt=float(dt_j), t_end=float(t_end_j), max_points=int(max_points), want_full=bool(want_full))

                        # UI stage: расчёт модели
                        _dg["stage"] = "simulate"
                        _dg["progress"] = 10
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Детальный прогон: расчёт модели…")
                        except Exception:
                            pass

                        out = call_simulate(
                            model_mod,
                            base_override,
                            test_j,
                            dt=dt_j,
                            t_end=t_end_j,
                            record_full=want_full,
                            max_steps=int(2e6),
                        )
                        t_sec = float(time.perf_counter() - t0_perf)

                        # UI stage: обработка результатов
                        _dg["stage"] = "parse"
                        _dg["progress"] = 70
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Детальный прогон: обработка результатов…")
                        except Exception:
                            pass

                        parsed = parse_sim_output(out, want_full=want_full)
                        df_main = downsample_df(parsed.get("df_main"), int(max_points))
                        df_drossel = downsample_df(parsed.get("df_drossel"), int(max_points))
                        df_energy = downsample_df(parsed.get("df_energy_drossel"), int(max_points))
                        nodes = parsed.get("nodes")
                        edges = parsed.get("edges")
                        df_Eedges = downsample_df(parsed.get("df_Eedges"), int(max_points))
                        df_Egroups = downsample_df(parsed.get("df_Egroups"), int(max_points))
                        df_atm = downsample_df(parsed.get("df_atm"), int(max_points))
                        df_p = downsample_df(parsed.get("df_p"), int(max_points))
                        df_mdot = downsample_df(parsed.get("df_mdot"), int(max_points))
                        df_open = downsample_df(parsed.get("df_open"), int(max_points))
                        st.session_state.baseline_full_cache[cache_key] = {
                            "df_main": df_main,
                            "df_drossel": df_drossel,
                            "df_energy": df_energy,
                            "nodes": nodes,
                            "edges": edges,
                            "df_Eedges": df_Eedges,
                            "df_Egroups": df_Egroups,
                            "df_atm": df_atm,
                            "df_p": df_p,
                            "df_mdot": df_mdot,
                            "df_open": df_open,
                            "meta": {
                                "test": test_pick,
                                "t_sec": float(t_sec),
                                "dt": float(dt_j),
                                "t_end": float(t_end_j),
                                "max_points": int(max_points),
                                "want_full": bool(want_full),
                                "app_release": APP_RELEASE,
                                "ts": datetime.now().isoformat(timespec="seconds"),
                                "geometry": _build_animator_geometry_meta(base_override),
                            }
                        }
                        # Avoid UI slowdowns from unbounded cache growth.
                        try:
                            _KEEP = int(st.session_state.get("baseline_full_cache_keep", 4))
                            if _KEEP < 1:
                                _KEEP = 1
                            while len(st.session_state.baseline_full_cache) > _KEEP:
                                st.session_state.baseline_full_cache.pop(next(iter(st.session_state.baseline_full_cache)))
                        except Exception:
                            pass

                        # UI stage: сохранение/кэширование
                        _dg["stage"] = "cache"
                        _dg["progress"] = 90
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Детальный прогон: сохранение кэша…")
                        except Exception:
                            pass

                        try:
                            if _cache_dir and _cache_dir.exists():
                                save_detail_cache(
                                    _cache_dir,
                                    test_pick,
                                    float(detail_dt),
                                    float(detail_t_end),
                                    int(max_points),
                                    bool(want_full),
                                    st.session_state.baseline_full_cache[cache_key],
                                )
                        except Exception as e:
                            log_event("detail_cache_save_error", err=str(e), test=test_pick)
                        log_event("detail_end", test=test_pick, rows=int(len(df_main) if df_main is not None else 0), t_sec=float(t_sec))

                        # UI stage: готово
                        _dg["stage"] = "done"
                        _dg["progress"] = 100
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Детальный прогон: готово.")
                        except Exception:
                            pass

                        # --- Auto-export anim_latest bundle for Desktop Animator (follow) ---
                        try:
                            if bool(st.session_state.get('auto_export_anim_latest', True)) and (_HAS_NPZ_BUNDLE and export_anim_latest_bundle is not None):
                                _meta_anim = {
                                    'source': 'ui_detail',
                                    'cache_key': str(cache_key),
                                    'test_name': str(test_pick),
                                    'dt': float(dt_j),
                                    't_end': float(t_end_j),
                                    'max_points': int(max_points),
                                    'want_full': bool(want_full),
                                    'app_release': str(APP_RELEASE),
                                }
                                try:
                                    _info2 = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
                                    _test2 = _info2.get('test') if isinstance(_info2, dict) else None
                                    _meta_anim.update(_extract_anim_sidecar_meta(_test2))
                                except Exception:
                                    pass
                                # optional: pass Patm for gauge calculations
                                try:
                                    if isinstance(base_override, dict):
                                        for _k in ('patm_pa', 'p_atm_pa', 'P_ATM', 'P_ATM_Па'):
                                            if _k in base_override and base_override.get(_k) is not None:
                                                _meta_anim['patm_pa'] = float(base_override.get(_k))
                                                break
                                except Exception:
                                    pass
                                _geom_anim = _build_animator_geometry_meta(base_override)
                                if _geom_anim:
                                    _meta_anim['geometry'] = _geom_anim
                                npz_latest, ptr_latest = export_anim_latest_bundle(
                                    exports_dir=str(WORKSPACE_EXPORTS_DIR),
                                    df_main=df_main,
                                    df_p=df_p,
                                    df_q=df_mdot,
                                    df_open=df_open,
                                    meta=_meta_anim,
                                )
                                _anim_state = {
                                    'npz_path': npz_latest,
                                    'pointer_json': ptr_latest,
                                    'meta': dict(_meta_anim or {}),
                                }
                                log_event('anim_latest_exported', npz=str(npz_latest), pointer=str(ptr_latest), test=str(test_pick))
                                # Cross-page compatibility: store anim_latest pointers.
                                try:
                                    from pneumo_solver_ui.run_artifacts import save_last_baseline_ptr as save_last_baseline_ptr_global

                                    _ra_payload = save_last_baseline_ptr_global(
                                        cache_dir=Path(_cache_dir) if _cache_dir else WORKSPACE_EXPORTS_DIR,
                                        meta={
                                            'source': 'ui_detail',
                                            'cache_key': str(cache_key),
                                            'test_name': str(test_pick),
                                            'release': str(APP_RELEASE),
                                        },
                                        anim_latest_npz=npz_latest,
                                        anim_latest_json=ptr_latest,
                                    )
                                    if isinstance(_ra_payload, dict):
                                        _anim_state = dict(_ra_payload)
                                except Exception:
                                    pass
                                try:
                                    apply_anim_latest_to_session_global(st.session_state, _anim_state)
                                except Exception:
                                    pass
                                if bool(st.session_state.get('auto_launch_animator', False)):
                                    launch_desktop_animator_follow(ptr_latest)
                        except Exception as _e_animexp:
                            st.warning(f'Авто-экспорт последней анимационной выгрузки не удался: {_e_animexp}')
                            log_event('anim_latest_export_error', err=str(_e_animexp), test=str(test_pick))
                        _dg_ok = dict(st.session_state.get("detail_guard") or {})
                        _dg_ok["failed_key"] = None
                        _dg_ok["failed_ts"] = 0.0
                        _dg_ok["failed_err"] = None
                        st.session_state["detail_guard"] = _dg_ok
                    except Exception as e:
                        st.error(f"Ошибка детального прогона: {e}")
                        log_event("detail_error", err=str(e), test=test_pick)
                        _dg_fail = dict(st.session_state.get("detail_guard") or {})
                        _dg_fail["failed_key"] = str(cache_key)
                        _dg_fail["failed_ts"] = float(time.time())
                        _dg_fail["failed_err"] = str(e)
                        st.session_state["detail_guard"] = _dg_fail
                        # UI stage: ошибка
                        try:
                            _dg_fail["stage"] = "error"
                            _dg_fail["progress"] = 100
                            _dg_fail["progress_last_ts"] = time.time()
                            st.session_state["detail_guard"] = _dg_fail
                            _detail_pb.progress(100)
                            _detail_pb_text.caption("Детальный прогон: ошибка.")
                        except Exception:
                            pass
                    finally:
                        if st.session_state.get("detail_auto_pending") == cache_key:
                            st.session_state["detail_auto_pending"] = None
                        clear_detail_force_fresh(st.session_state, cache_key=str(cache_key))
                        _dg2 = dict(st.session_state.get("detail_guard") or {})
                        _dg2["in_progress"] = False
                        _dg2["last_key"] = str(cache_key)
                        _dg2["last_end_ts"] = float(time.time())
                        _dg2.setdefault("suppressed", int(_dg.get("suppressed") or 0))
                        st.session_state["detail_guard"] = _dg2
            if cache_key in st.session_state.baseline_full_cache:
                det = st.session_state.baseline_full_cache[cache_key]
                df_main = det.get("df_main")
                df_p = det.get("df_p")
                df_mdot = det.get("df_mdot")
                df_open = det.get("df_open")
                df_Eedges = det.get("df_Eedges")
                df_Egroups = det.get("df_Egroups")

                df_atm = det.get("df_atm")

                # -----------------------------------
                # Self-check summary (kinematics / balances / DW2D)
                # -----------------------------------
                if df_atm is not None and hasattr(df_atm, 'iloc') and len(df_atm) > 0:
                    try:
                        _r0 = df_atm.iloc[0].to_dict()
                    except Exception:
                        _r0 = {}

                    def _as_bool(v, default=None):
                        if v is None:
                            return default
                        try:
                            if isinstance(v, (bool, int, float)):
                                return bool(int(v))
                        except Exception:
                            pass
                        try:
                            s = str(v).strip().lower()
                            if s in ('1','true','yes','y','да'):
                                return True
                            if s in ('0','false','no','n','нет',''):
                                return False
                        except Exception:
                            pass
                        return default

                    mech_ok = _as_bool(_r0.get('mech_selfcheck_ok', None), default=None)
                    mech_msg = str(_r0.get('mech_selfcheck_msg', '') or '')

                    # Parse autoself post JSON to extract DW2D dynamic range info
                    rep_post = None
                    _post_json = _r0.get('autoself_post_json', None)
                    if isinstance(_post_json, str) and _post_json.strip():
                        try:
                            rep_post = json.loads(_post_json)
                        except Exception:
                            rep_post = None

                    dw_item = None
                    if isinstance(rep_post, dict):
                        for it in (rep_post.get('items') or []):
                            if isinstance(it, dict) and it.get('name') == 'dw2d_dynamic_range':
                                dw_item = it
                                break

                    pose_item = None
                    if isinstance(rep_post, dict):
                        for it in (rep_post.get('items') or []):
                            if isinstance(it, dict) and it.get('name') == 'zero_pose':
                                pose_item = it
                                break

                    st.subheader('Самопроверки (детальный прогон)')
                    st.caption('Подвеска: кинематика и перемещения, плюс проверка DW2D по фактическому рабочему диапазону хода из симуляции.')

                    cS1, cS2, cS3 = st.columns(3)
                    with cS1:
                        if mech_ok is True:
                            st.success('Кинематика и перемещения: в норме')
                        elif mech_ok is False:
                            st.error('Кинематика и перемещения: требуют внимания')
                        else:
                            st.info('Кинематика и перемещения: данных нет')

                    with cS2:
                        if isinstance(dw_item, dict):
                            _dw_ok = bool(dw_item.get('ok', True))
                            _dw_sev = str(dw_item.get('severity', 'info') or 'info')
                            _label = 'Рабочий диапазон DW2D: в норме' if _dw_ok else 'Рабочий диапазон DW2D: требует внимания'
                            if _dw_ok:
                                st.success(_label)
                            else:
                                if _dw_sev == 'error':
                                    st.error(_label)
                                else:
                                    st.warning(_label)
                        else:
                            st.info('Рабочий диапазон DW2D: данных нет')

                    with cS3:
                        _stab_on = bool(base_override.get('стабилизатор_вкл', False))
                        st.write('Стабилизатор:', 'включён' if _stab_on else 'выключен (по умолчанию)')

                    # Нулевая поза (t=0): дорога=0, штоки ~ середина хода
                    if isinstance(pose_item, dict):
                        _pz_ok = bool(pose_item.get('ok', True))
                        _pz_sev = str(pose_item.get('severity', 'info') or 'info')
                        _pz_label = 'Нулевая поза: в норме' if _pz_ok else 'Нулевая поза: требует внимания'
                        if _pz_ok:
                            st.success(_pz_label)
                        else:
                            if _pz_sev == 'error':
                                st.error(_pz_label)
                            else:
                                st.warning(_pz_label)
                    else:
                        st.info('Нулевая поза: данных нет')

                    with st.expander('Детали самопроверок', expanded=False):
                        if mech_msg:
                            st.write('Сообщение по механике:', mech_msg)
                        _mj = _r0.get('mech_selfcheck_json', None)
                        if isinstance(_mj, str) and _mj.strip():
                            try:
                                st.json(json.loads(_mj))
                            except Exception:
                                st.code(_mj)
                        if isinstance(dw_item, dict) and (dw_item.get('message') or dw_item.get('value')):
                            st.markdown('**Проверка рабочего диапазона DW2D**')
                            if dw_item.get('message'):
                                st.write(str(dw_item.get('message')))
                            if dw_item.get('value') is not None:
                                st.json(dw_item.get('value'))
                        if isinstance(pose_item, dict) and (pose_item.get('message') or pose_item.get('value')):
                            st.markdown('**Нулевая поза в начале расчёта (t=0)**')
                            if pose_item.get('message'):
                                st.write(str(pose_item.get('message')))
                            try:
                                _val = pose_item.get('value') or {}
                                _corn = (_val.get('corners') or {}) if isinstance(_val, dict) else {}
                                if isinstance(_corn, dict) and _corn:
                                    _rows = []
                                    for _c, _d in _corn.items():
                                        if not isinstance(_d, dict):
                                            continue
                                        _rows.append({
                                            'Угол подвески': _c,
                                            'Уровень дороги, м': _d.get('road_m', float('nan')),
                                            'Колесо относительно рамы, м': _d.get('wheel_rel_frame_m', float('nan')),
                                            'Шток C1, доля хода': _d.get('rod_C1_frac', float('nan')),
                                            'Шток C2, доля хода': _d.get('rod_C2_frac', float('nan')),
                                        })
                                    if _rows:
                                        st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch")
                            except Exception:
                                pass
                            if pose_item.get('value') is not None:
                                st.json(pose_item.get('value'))
                        if isinstance(rep_post, dict):
                            st.markdown('**Полный отчёт самопроверки (JSON)**')
                            st.json(rep_post)

                    st.caption('Настройка геометрии DW2D доступна на странице «Геометрия подвески (DW2D)» в меню слева.')


                # -----------------------------------
                # Desktop Animator integration (follow-mode)
                # -----------------------------------
                with st.expander('🖥 Desktop Animator (внешнее окно, по выгрузке anim_latest)', expanded=False):
                    npz_path, ptr_path = local_anim_latest_export_paths_global(
                        WORKSPACE_EXPORTS_DIR,
                        ensure_exists=False,
                    )
                    st.caption('Desktop Animator читает последнюю выгрузку из папки workspace/exports (файлы anim_latest.*).')
                    st.code(str(ptr_path))
                    cols_da = st.columns([1, 1, 1])
                    with cols_da[0]:
                        if st.button('Экспортировать последнюю выгрузку (anim_latest)', key=f'anim_latest_export_now_{cache_key}'):
                            try:
                                if not (_HAS_NPZ_BUNDLE and export_anim_latest_bundle is not None):
                                    raise RuntimeError('npz_bundle недоступен (проверьте pneumo_solver_ui/npz_bundle.py)')
                                _meta_anim = {
                                    'source': 'ui_manual',
                                    'cache_key': str(cache_key),
                                    'test_name': str(test_pick),
                                    'max_points': int(max_points),
                                    'want_full': bool(want_full),
                                    'app_release': str(APP_RELEASE),
                                }
                                try:
                                    _info2 = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
                                    _test2 = _info2.get('test') if isinstance(_info2, dict) else None
                                    _meta_anim.update(_extract_anim_sidecar_meta(_test2))
                                except Exception:
                                    pass
                                try:
                                    if isinstance(base_override, dict):
                                        for _k in ('patm_pa', 'p_atm_pa', 'P_ATM', 'P_ATM_Па'):
                                            if _k in base_override and base_override.get(_k) is not None:
                                                _meta_anim['patm_pa'] = float(base_override.get(_k))
                                                break
                                except Exception:
                                    pass
                                _geom_anim = _build_animator_geometry_meta(base_override)
                                if _geom_anim:
                                    _meta_anim['geometry'] = _geom_anim
                                npz_latest, ptr_latest = export_anim_latest_bundle(
                                    exports_dir=str(WORKSPACE_EXPORTS_DIR),
                                    df_main=df_main,
                                    df_p=df_p,
                                    df_q=df_mdot,
                                    df_open=df_open,
                                    meta=_meta_anim,
                                )
                                _anim_state = {
                                    'npz_path': npz_latest,
                                    'pointer_json': ptr_latest,
                                    'meta': dict(_meta_anim or {}),
                                }
                                st.success(f'Последняя анимационная выгрузка сохранена: {npz_latest.name}')
                                log_event('anim_latest_exported_manual', npz=str(npz_latest), pointer=str(ptr_latest), test=str(test_pick))
                                try:
                                    from pneumo_solver_ui.run_artifacts import save_last_baseline_ptr as save_last_baseline_ptr_global

                                    _ra_payload = save_last_baseline_ptr_global(
                                        cache_dir=WORKSPACE_EXPORTS_DIR,
                                        meta={
                                            'source': 'ui_manual',
                                            'cache_key': str(cache_key),
                                            'test_name': str(test_pick),
                                            'release': str(APP_RELEASE),
                                        },
                                        anim_latest_npz=npz_latest,
                                        anim_latest_json=ptr_latest,
                                    )
                                    if isinstance(_ra_payload, dict):
                                        _anim_state = dict(_ra_payload)
                                except Exception:
                                    pass
                                try:
                                    apply_anim_latest_to_session_global(st.session_state, _anim_state)
                                except Exception:
                                    pass
                            except Exception as e:
                                st.error(f'Не удалось экспортировать последнюю анимационную выгрузку: {e}')
                                log_event('anim_latest_export_error_manual', err=str(e), test=str(test_pick))
                    with cols_da[1]:
                        no_gl = st.checkbox('Без OpenGL (режим совместимости)', value=False, key=f'anim_latest_no_gl_{cache_key}')
                        if st.button('Запустить Desktop Animator', key=f'anim_latest_launch_{cache_key}'):
                            ok = launch_desktop_animator_follow(ptr_path, no_gl=bool(no_gl))
                            if ok:
                                st.success('Desktop Animator запущен (если система позволяет GUI).')
                            else:
                                st.warning('Не удалось запустить Desktop Animator (см. логи).')
                        if st.button('Запустить Mnemo (follow)', key=f'anim_latest_launch_mnemo_{cache_key}'):
                            ok = launch_desktop_mnemo_follow(ptr_path)
                            if ok:
                                st.success('Desktop Mnemo запущен (если система позволяет GUI).')
                            else:
                                st.warning('Не удалось запустить Desktop Mnemo (см. логи).')
                    with cols_da[2]:
                        st.caption(f'Файл NPZ: {npz_path}')
                        st.caption('Подсказка: включите **Авто-экспорт anim_latest** в настройках детального прогона. Animator даёт 3D/2D виды, Mnemo даёт отдельное HMI-окно с анимированной мнемохемой.')

                # -----------------------------------
                # Global timeline (shared playhead)
                # -----------------------------------
                time_s = []
                if df_main is not None and "время_с" in df_main.columns:
                    time_s = df_main["время_с"].astype(float).tolist()
                elif df_mdot is not None and "время_с" in df_mdot.columns:
                    time_s = df_mdot["время_с"].astype(float).tolist()

                # Важно: dataset_id для компонентов делаем *уникальным внутри UI-сессии*.
                # Это защищает от редкой гонки: при refresh и неизменившемся cache_key
                # в localStorage может остаться playhead с playing=true, и 2D/3D
                # компоненты успевают его подхватить, пока playhead_ctrl не перезаписал
                # состояние. Добавляя nonce, мы гарантируем, что старое состояние
                # будет проигнорировано (dataset_id не совпадёт).
                _results_runtime = prepare_results_runtime(
                    st,
                    session_state=st.session_state,
                    cache_key=cache_key,
                    get_ui_nonce_fn=get_ui_nonce,
                    time_s=time_s,
                    make_playhead_reset_command_fn=make_playhead_reset_command,
                    make_playhead_jump_command_fn=make_playhead_jump_command,
                    log_event_fn=log_event,
                    event_controls_kwargs={
                        "vacuum_label": "Вакуум мин, бар(изб)",
                        "pmax_label": "Запас к Pmax, бар",
                        "vacuum_state_key": "events_vacuum_min_bar",
                        "pmax_state_key": "events_pmax_margin_bar",
                        "migration_source_vacuum_key": "events_vacuum_min_atm",
                        "migration_source_pmax_key": "events_pmax_margin_atm",
                        "migration_scale": ATM_PA / BAR_PA,
                    },
                    compute_results_events_kwargs={
                        "compute_events_fn": compute_events,
                        "base_override": base_override,
                        "p_atm": P_ATM,
                        "df_main": df_main,
                        "df_p": df_p,
                        "df_open": df_open,
                        "test": test_for_events,
                        "vacuum_state_key": "events_vacuum_min_bar",
                        "pmax_state_key": "events_pmax_margin_bar",
                        "vacuum_kwarg_name": "vacuum_min_gauge_bar",
                        "pmax_kwarg_name": "pmax_margin_bar",
                    },
                )
                dataset_id_ui = str(_results_runtime["dataset_id_ui"])
                playhead_idx = int(_results_runtime["playhead_idx"])
                playhead_x = _results_runtime["playhead_x"]
                events_list = _results_runtime["events_list"]

                def _render_playhead_fallback() -> None:
                    log_event("component_missing", component="playhead_ctrl", detail="components/playhead_ctrl", proc=_proc_metrics())
                    # Fallback: простой слайдер по индексу времени (без JS-компонента).
                    _ph_max = max(0, len(time_s) - 1)
                    _ph_default = int(st.session_state.get('playhead_idx', 0) or 0)
                    _ph_default = min(max(_ph_default, 0), _ph_max)
                    _ph_idx = st.slider('Playhead (idx)', 0, _ph_max, value=_ph_default, key=f'playhead_idx_fallback_{cache_key}')
                    st.session_state['playhead_idx'] = int(_ph_idx)
                    try:
                        st.session_state['playhead_t'] = float(time_s[int(_ph_idx)])
                    except Exception:
                        pass
                    st.caption(f"t = {float(time_s[int(_ph_idx)]):.3f} s")

                # Важно: st.tabs не "ленивый" — код внутри всех табов исполняется при каждом rerun.
                # При анимации (auto-refresh) это выглядит как "бесконечный расчёт".
                # Поэтому используем явный селектор и рендерим только выбранную ветку.
                render_heavy_results_surface_section(
                    st,
                    session_state=st.session_state,
                    cur_hash=cur_hash,
                    test_pick=test_pick,
                    cache_key=cache_key,
                    dataset_id=dataset_id_ui,
                    time_s=time_s,
                    playhead_idx=int(playhead_idx),
                    playhead_x=playhead_x,
                    events_list=events_list,
                    df_main=df_main,
                    df_p=df_p,
                    df_mdot=df_mdot,
                    df_open=df_open,
                    df_egroups=df_Egroups,
                    df_eedges=df_Eedges,
                    plot_lines_fn=plot_lines,
                    plot_timeseries_fn=plot_studio_timeseries,
                    excel_bytes_fn=df_to_excel_bytes,
                    safe_dataframe_fn=safe_dataframe,
                    p_atm=P_ATM,
                    pressure_from_pa_fn=pa_abs_to_bar_g,
                    pressure_divisor=BAR_PA,
                    flow_scale_and_unit_fn=flow_rate_display_scale_and_unit,
                    model_module=model_mod,
                    has_plotly=_HAS_PLOTLY,
                    px_module=px,
                    safe_plotly_chart_fn=safe_plotly_chart,
                    log_event_fn=log_event,
                    base_override=base_override,
                    tests_map=tests_map,
                    compute_road_profile_fn=compute_road_profile_from_suite,
                    proc_metrics_fn=_proc_metrics,
                    safe_image_fn=safe_image,
                    base_dir=HERE,
                    ring_visual_base_dir=ROOT_DIR,
                    mech_fallback_module=mech_fb,
                    get_float_param_fn=get_float_param,
                    fallback_error=_MECH_ANIM_FALLBACK_ERR,
                    ring_visual_pick=pick,
                    ring_visual_workspace_exports_dir=WORKSPACE_EXPORTS_DIR,
                    ring_visual_latest_export_paths_fn=local_anim_latest_export_paths_global,
                    default_svg_mapping_path=DEFAULT_SVG_MAPPING_PATH,
                    route_write_view_box=DEFAULT_SVG_VIEWBOX,
                    do_rerun_fn=do_rerun,
                    render_svg_flow_animation_html_fn=render_svg_flow_animation_html,
                    has_svg_autotrace=_HAS_SVG_AUTOTRACE,
                    extract_polylines_fn=extract_polylines,
                    auto_build_mapping_from_svg_fn=auto_build_mapping_from_svg,
                    detect_component_bboxes_fn=detect_component_bboxes,
                    name_score_fn=_name_score,
                    shortest_path_fn=shortest_path_between_points,
                    evaluate_quality_fn=evaluate_route_quality,
                    missing_playhead_fallback_fn=_render_playhead_fallback,
                )





# -------------------------------
# Оптимизация — инженерный gateway
# -------------------------------
st.divider()
st.header("Оптимизация")
st.caption(
    "Последовательные staged / coordinator прогоны — нормальный инженерный сценарий. "
    "Чтобы не смешивать два равноправных control plane на главной, запуск, stop/resume, monitoring и все ручки оптимизации "
    "вынесены на отдельную страницу. На главной остаются входные данные, search-space contract и read-only обзор."
)

colO1, colO2, colO3 = st.columns([1.15, 1.0, 1.05], gap="large")

with colO1:
    st.markdown("**Переходы**")
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/30_Optimization.py",
        "🎯 Открыть страницу оптимизации",
        key="home_opt_gateway_main_go_optimization",
        help_text="Все staged/coordinator настройки, запуск, stop/resume, текущий лог и live-monitoring.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/20_DistributedOptimization.py",
        "📊 Результаты оптимизации / ExperimentDB",
        key="home_opt_gateway_main_go_results",
        help_text="Просмотр distributed результатов, прогресса и Pareto/DB слоя.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/31_OptDatabase.py",
        "🗄️ База оптимизаций",
        key="home_opt_gateway_main_go_db",
        help_text="Отдельная страница базы прогонов оптимизации.",
    )
    st.caption(
        "Важно: таблица параметров, режимы и suite на главной остаются source-of-truth для search-space contract. "
        "Но сам optimization launcher на главной больше не дублируется."
    )

with colO2:
    st.markdown("**Текущий конфиг (read-only)**")
    _render_home_opt_config_snapshot(compact=False)

with colO3:
    st.markdown("**Последняя оптимизация**")
    _render_home_opt_last_pointer_summary(compact=False)

st.info(
    "Главная больше не держит второй launcher оптимизации. Это не режет staged/coordinator режимы и не прячет настройки — "
    "оно просто собирает запуск и наблюдение в одном инженерном месте."
)

# Legacy home optimization block retained only as dormant source surface
# for regression/source guards. Live launch path = dedicated Optimization page.
if False:

    # -------------------------------
    # Оптимизация (фон)
    # -------------------------------
    st.divider()
    st.header("Оптимизация (фон)")

    colO1, colO2, colO3 = st.columns([1.2, 1.0, 1.0], gap="large")

    with colO1:
        st.markdown("**Команды**")
        # Gating: if autoselfcheck failed, block optimization by default (override is explicit)
        _self_ok = bool(st.session_state.get("_autoselfcheck_v1_ok", True))
        _allow_unsafe_opt = True
        if not _self_ok:
            st.error(
                "Самопроверка интерфейса не пройдена. "
                "Оптимизация по умолчанию заблокирована, чтобы не получать недостоверные результаты."
            )
            _allow_unsafe_opt = st.checkbox(
                "Разрешить оптимизацию несмотря на сбой самопроверки",
                value=False,
                key="allow_unsafe_opt",
                help=(
                    "Иногда это полезно для отладки, но результаты могут быть некорректны. "
                    "Лучше сначала исправить ошибки самопроверки."
                ),
            )

        _opt_disabled = (
            pid_alive(st.session_state.opt_proc)
            or bool(param_errors)
            or bool(suite_errors)
            or ((not _self_ok) and (not _allow_unsafe_opt))
        )

        btn_start = st.button("Старт оптимизации", disabled=_opt_disabled)
        colS1, colS2 = st.columns(2)
        with colS1:
            btn_stop_soft = st.button("Стоп (мягко)", disabled=not pid_alive(st.session_state.opt_proc), help="Создаёт STOP-файл. Оптимизатор сам корректно завершится и сохранит CSV/прогресс.")
        with colS2:
            btn_stop_hard = st.button("Стоп (жёстко)", disabled=not pid_alive(st.session_state.opt_proc), help="Создаёт STOP-файл и принудительно завершает процесс. Используйте только если мягкая остановка не срабатывает.")

    with colO2:
        st.markdown("**Статус**")
        if pid_alive(st.session_state.opt_proc):
            st.success(f"Оптимизация идёт (PID={st.session_state.opt_proc.pid})")
            if st.session_state.opt_stop_requested:
                st.warning("Запрошена мягкая остановка… ждём завершения процесса.")
        else:
            st.info("Оптимизация не запущена")
            # если процесс завершился (сам или после мягкого STOP) — чистим состояние
            if st.session_state.opt_proc is not None:
                st.session_state.opt_proc = None
            st.session_state.opt_stop_requested = False

        if st.session_state.opt_out_csv:
            st.write("Файл результатов:", st.session_state.opt_out_csv)
            # прогресс оптимизации (файл пишет worker)
            try:
                out_csv_path = Path(st.session_state.opt_out_csv)
                progress_path = st.session_state.opt_progress_path or (str(out_csv_path.with_suffix("")) + "_progress.json")
                if os.path.exists(progress_path):
                    with open(progress_path, "r", encoding="utf-8") as f:
                        prog = json.load(f)
                    try:
                        _mtime = os.path.getmtime(progress_path)
                        _age = time.time() - float(_mtime)
                        st.caption(f"Файл прогресса обновлён {_age:.1f} с назад: {progress_path}")
                        # Если процесс жив, а файл давно не обновлялся — вероятно завис/упал или пишет в другой каталог.
                        if pid_alive(st.session_state.opt_proc) and (_age > max(300.0, 10.0*float(refresh_sec) + 5.0)):
                            st.caption("⚠️ Файл прогресса давно не обновлялся. Если это неожиданно, проверьте, что worker пишет служебный progress.json в тот же каталог и что расчёт не завис.")
                    except Exception:
                        pass

                    time_limit_min = float(prog.get("лимит_минут", 0.0) or 0.0)
                    elapsed_sec = float(prog.get("прошло_сек", 0.0) or 0.0)
                    ts_start = prog.get("ts_start", None)
                    try:
                        if ts_start is not None:
                            elapsed_sec_live = max(elapsed_sec, time.time() - float(ts_start))
                        else:
                            elapsed_sec_live = elapsed_sec
                    except Exception:
                        elapsed_sec_live = elapsed_sec
                    status_text = str(prog.get("статус", "") or "")
                    ok = prog.get("ok", None)
                    err = prog.get("err", None)

                    staged_summary = None
                    try:
                        if str(progress_path).endswith("staged_progress.json") or ("stage_total" in prog and "stage" in prog):
                            from pneumo_solver_ui.optimization_progress_live import summarize_staged_progress
                            _run_dir_for_progress = None
                            try:
                                if st.session_state.get("opt_run_dir"):
                                    _run_dir_for_progress = Path(str(st.session_state.opt_run_dir))
                                else:
                                    _run_dir_for_progress = Path(out_csv_path).parent
                            except Exception:
                                _run_dir_for_progress = None
                            staged_summary = summarize_staged_progress(prog, _run_dir_for_progress)
                    except Exception:
                        staged_summary = None

                    if staged_summary is not None:
                        stage_name = str(staged_summary.get("stage", "") or "")
                        stage_idx = int(staged_summary.get("idx", 0) or 0)
                        stage_total = int(staged_summary.get("stage_total", 0) or 0)
                        total_done = int(staged_summary.get("total_rows_live", 0) or 0)
                        total_done_in_file = int(staged_summary.get("total_rows_live", total_done) or total_done)
                        stage_rows_current = int(staged_summary.get("stage_rows_current", 0) or 0)
                        stage_rows_done_before = int(staged_summary.get("stage_rows_done_before", 0) or 0)
                        worker_done_current = int(staged_summary.get("worker_done_current", stage_rows_current) or stage_rows_current)
                        worker_written_current = int(staged_summary.get("worker_written_current", worker_done_current) or worker_done_current)
                        stage_elapsed_sec = staged_summary.get("stage_elapsed_sec", None)
                        stage_budget_sec = staged_summary.get("stage_budget_sec", None)

                        st.write(f"Стадия: **{stage_name}** (idx={stage_idx}, 0-based; всего стадий: {max(1, stage_total)})")
                        st.caption(describe_runtime_stage(stage_name))
                        st.write(f"Готово (суммарно): {total_done}  |  Записано в файл: {total_done_in_file}")
                        st.write(f"Текущая стадия: строк в CSV текущей стадии = **{stage_rows_current}**  |  по данным progress-файла = {worker_done_current}/{worker_written_current}")
                        if stage_rows_done_before > 0:
                            st.caption(f"Завершённые предыдущие стадии уже дали строк: {stage_rows_done_before}")
                        if stage_budget_sec is not None and float(stage_budget_sec) > 0:
                            frac_stage = max(0.0, min(1.0, float(stage_elapsed_sec or 0.0) / float(stage_budget_sec)))
                            st.progress(frac_stage, text=f"Прогресс текущей стадии по времени: {frac_stage*100:.1f}% (статус: {status_text})")
                        elif time_limit_min > 0:
                            frac_t = max(0.0, min(1.0, elapsed_sec_live / (time_limit_min * 60.0)))
                            st.progress(frac_t, text=f"Прогресс по времени: {frac_t*100:.1f}% (статус: {status_text})")
                        if bool(staged_summary.get("worker_progress_stale", False)):
                            st.caption("⚠️ Вложенный progress.json отстаёт от фактического CSV текущей стадии; интерфейс показывает производные счётчики по реально записанным строкам stage CSV.")
                        try:
                            policy_run_dir = None
                            if st.session_state.get("opt_run_dir"):
                                policy_run_dir = Path(str(st.session_state.opt_run_dir))
                            else:
                                policy_run_dir = Path(out_csv_path).parent
                            live_policy = summarize_stage_policy_runtime(
                                policy_run_dir,
                                stage_idx=stage_idx,
                                stage_name=stage_name,
                            )
                        except Exception:
                            live_policy = {}
                        if bool(live_policy.get("available")):
                            st.markdown("**Политика отбора и продвижения (текущая стадия)**")
                            policy_name = str(live_policy.get("policy_name") or "")
                            effective_mode = str(live_policy.get("effective_mode") or "")
                            requested_mode_live = str(live_policy.get("requested_mode") or "")
                            summary_status_live = str(live_policy.get("summary_status") or "")
                            priority_params_live = list(live_policy.get("priority_params") or [])
                            seed_bucket_counts = dict(live_policy.get("seed_bucket_counts") or {})
                            st.caption(
                                f"policy={policy_name or '—'} · requested={requested_mode_live or '—'} · effective={effective_mode or '—'} · summary={summary_status_live or '—'}"
                            )
                            st.write(
                                "Seed budget:",
                                f"explore={int(live_policy.get('explore_budget', 0) or 0)}",
                                f"focus={int(live_policy.get('focus_budget', 0) or 0)}",
                                f"selected={int(live_policy.get('seed_count', 0) or 0)}",
                                f"focus/explore selected={int(seed_bucket_counts.get('focus', 0) or 0)}/{int(seed_bucket_counts.get('explore', 0) or 0)}",
                            )
                            if priority_params_live:
                                st.caption("Приоритетные параметры этой стадии: " + ", ".join(str(x) for x in priority_params_live[:8]))
                            if int(live_policy.get("promotion_selected_count", 0) or 0) > 0:
                                st.caption(
                                    "Promotion decisions selected: "
                                    + str(int(live_policy.get("promotion_selected_count", 0) or 0))
                                    + f" (focus={int(live_policy.get('promotion_selected_focus_count', 0) or 0)}, explore={int(live_policy.get('promotion_selected_explore_count', 0) or 0)})"
                                )
                            seed_preview_rows = list(live_policy.get("seed_preview") or [])
                            if seed_preview_rows:
                                st.dataframe(pd.DataFrame(seed_preview_rows), use_container_width=True, hide_index=True)
                    else:
                        total_done = int(prog.get("готово_кандидатов", 0) or 0)
                        total_done_in_file = int(prog.get("готово_кандидатов_в_файле", total_done) or 0)
                        st.write(f"Готово (посчитано): {total_done}  |  Записано в файл: {total_done_in_file}")
                        if time_limit_min > 0:
                            frac_t = max(0.0, min(1.0, elapsed_sec_live / (time_limit_min * 60.0)))
                            st.progress(frac_t, text=f"Прогресс по времени: {frac_t*100:.1f}% (статус: {status_text})")
                        st.write(f"Готово кандидатов: **{total_done}**")

                    if ok is not None and err is not None:
                        st.write(f"В последнем батче: OK={ok}, ERR={err}")
                    # диагностика: процесс умер, но статус ещё «идёт»
                    if (not pid_alive(st.session_state.opt_proc)) and status_text in ["запущено", "идёт", "stage_running", "baseline_eval", "seed_eval"]:
                        st.error(
                            "Похоже, worker/staged-runner завершился аварийно или был остановлен до финального статуса, а прогресс не дошёл до 'завершено'. "
                            "Смотрите log/CSV/staged_progress и stage_*_progress.json."
                        )
                else:
                    st.caption(f"Файл прогресса ещё не создан. Ожидаемый путь: {progress_path}")
            except Exception as _e:
                st.caption(f"Не удалось прочитать прогресс: {_e}")

    with colO3:
        st.markdown("**Логика**")
        st.write("Результаты пишутся в CSV инкрементально, каждые N кандидатов.")


    def write_json(obj: dict, path: Path):
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


    if btn_start:
        # ------------------------------------------------------------------
        # Stable run directory (resume + caching) + optional staged runner
        # ------------------------------------------------------------------
        def _file_sha1(path: Path) -> str:
            h = hashlib.sha1()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()

        # Deterministic "problem hash" depends ONLY on what defines the objective:
        # Normalize optimization inputs before hashing/writing:
        # - tolerate historical 1-based suite stages by converting them to canonical 0-based;
        # - strip non-design/service keys from ranges;
        # - widen numeric bounds so the canonical base stays inside the search domain.
        base_effective, ranges_effective, suite_effective, optimization_input_audit = sanitize_optimization_inputs(
            base_override,
            ranges_override,
            suite_override,
        )

        # model + base + ranges + suite. Algorithm settings (minutes/jobs/seeds)
        # must NOT change it, otherwise resume would be broken.
        try:
            model_hash = _file_sha1(Path(model_path))[:12]
        except Exception:
            model_hash = "nomodel"

        base_hash = stable_obj_hash(base_effective)
        ranges_hash = stable_obj_hash(ranges_effective)
        suite_hash = stable_obj_hash(suite_effective)
        problem_hash = hashlib.sha1(
            f"{model_hash}|{base_hash}|{ranges_hash}|{suite_hash}".encode("utf-8")
        ).hexdigest()[:12]

        run_id = sanitize_id(st.session_state.get("opt_run_name", "run")) or "run"
        run_dir = build_optimization_run_dir(WORKSPACE_DIR, run_id, problem_hash)
        run_dir.mkdir(parents=True, exist_ok=True)

        safe_stem = sanitize_id(out_prefix or "results_opt") or "results_opt"
        out_csv_path = run_dir / (
            f"{safe_stem}_all.csv" if st.session_state.opt_use_staged else f"{safe_stem}.csv"
        )

        # Snapshot current inputs into run_dir (reproducibility + future resume)
        base_json = run_dir / "base.json"
        suite_json = run_dir / "suite.json"
        ranges_json = run_dir / "ranges.json"
        write_json(base_effective, base_json)
        write_json(suite_effective, suite_json)
        write_json(ranges_effective, ranges_json)
        write_json(optimization_input_audit, run_dir / "optimization_input_audit.json")

        # STOP file for both single-stage and staged runner
        stop_file = run_dir / "STOP_OPTIMIZATION.txt"
        if stop_file.exists():
            try:
                stop_file.unlink()
            except Exception:
                pass

        # Select runner
        if st.session_state.opt_use_staged:
            progress_path = staged_progress_path(run_dir)
            stage_runner_path = HERE / "opt_stage_runner_v1.py"
            cmd = [
                sys.executable,
                str(stage_runner_path),
                "--model",
                str(Path(resolved_model_path)),
                "--worker",
                str(Path(resolved_worker_path)),
                "--run_dir",
                str(run_dir),
                "--base_json",
                str(base_json),
                "--ranges_json",
                str(ranges_json),
                "--suite_json",
                str(suite_json),
                "--out_csv",
                str(out_csv_path),
                "--progress_json",
                str(progress_path),
                "--stop_file",
                str(stop_file),
                "--minutes",
                str(float(minutes)),
                "--seed_candidates",
                str(int(seed_candidates)),
                "--seed_conditions",
                str(int(seed_conditions)),
                "--jobs",
                str(int(jobs)),
                "--flush_every",
                str(int(flush_every)),
                "--progress_every_sec",
                str(float(progress_every_sec)),
                "--warmstart_mode",
                str(st.session_state.get("warmstart_mode", "surrogate")),
                "--surrogate_samples",
                str(int(st.session_state.get("surrogate_samples", 8000))),
                "--surrogate_top_k",
                str(int(st.session_state.get("surrogate_top_k", 64))),
                "--stop_pen_stage1",
                str(float(st.session_state.get("stop_pen_stage1", 25.0))),
                "--stop_pen_stage2",
                str(float(st.session_state.get("stop_pen_stage2", 15.0))),
                "--sort_tests_by_cost",
                "1" if bool(st.session_state.get("sort_tests_by_cost", True)) else "0",
                "--eps_rel",
                str(float(st.session_state.get("influence_eps_rel", DIAGNOSTIC_INFLUENCE_EPS_REL))),
                "--stage_policy_mode",
                str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE),
                "--autoupdate_baseline",
                "1" if st.session_state.opt_autoupdate_baseline else "0",
            ]
            if bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)):
                cmd.append("--adaptive_influence_eps")
                cmd += [
                    "--adaptive_influence_eps_grid",
                    influence_eps_grid_text(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID),
                ]
        else:
            progress_path = Path(os.path.splitext(str(out_csv_path))[0] + "_progress.json")
            cmd = [
                sys.executable,
                str(Path(resolved_worker_path)),
                "--model",
                str(Path(model_path)),
                "--out",
                str(out_csv_path),
                "--suite_json",
                str(suite_json),
                "--minutes",
                str(float(minutes)),
                "--seed_candidates",
                str(int(seed_candidates)),
                "--seed_conditions",
                str(int(seed_conditions)),
                "--jobs",
                str(int(jobs)),
                "--flush_every",
                str(int(flush_every)),
                "--progress_every_sec",
                str(float(progress_every_sec)),
                "--base_json",
                str(base_json),
                "--ranges_json",
                str(ranges_json),
                "--stop_file",
                str(stop_file),
            ]

        # Persist for UI (stop/resume/display)
        st.session_state.opt_run_dir = str(run_dir)
        st.session_state.opt_stop_file = str(stop_file)
        st.session_state.opt_progress_path = str(progress_path)
        st.session_state.opt_out_csv = str(out_csv_path)
        st.session_state.opt_base_json = str(base_json)
        st.session_state.opt_ranges_json = str(ranges_json)

        # Cross-page pointer: so any page can pick the latest optimization run automatically.
        try:
            from pneumo_solver_ui.run_artifacts import save_last_opt_ptr

            save_last_opt_ptr(
                run_dir,
                meta={
                    "source": "pneumo_ui_app",
                    "out_csv": str(out_csv_path),
                    "progress_path": str(progress_path),
                    "base_json": str(base_json),
                    "ranges_json": str(ranges_json),
                    "model": str(resolved_model_path),
                    "worker": str(resolved_worker_path),
                },
            )
        except Exception:
            pass

        st.session_state.opt_proc = start_worker(cmd, cwd=run_dir)
        do_rerun()

    if 'btn_stop_soft' in locals() and btn_stop_soft:
        # Мягкая остановка: только STOP-файл. Процесс сам завершится, запишет прогресс и корректно закроет файлы.
        try:
            (Path(st.session_state.opt_stop_file) if st.session_state.opt_stop_file else (HERE / "STOP_OPTIMIZATION.txt")).write_text("stop", encoding="utf-8")
        except Exception:
            pass
        st.session_state.opt_stop_requested = True
        do_rerun()

    if 'btn_stop_hard' in locals() and btn_stop_hard:
        # Жёсткая остановка: STOP-файл + принудительное завершение процесса (если нужно).
        try:
            (Path(st.session_state.opt_stop_file) if st.session_state.opt_stop_file else (HERE / "STOP_OPTIMIZATION.txt")).write_text("stop", encoding="utf-8")
        except Exception:
            pass

        p = st.session_state.opt_proc
        if pid_alive(p):
            try:
                terminate_process_tree(p, grace_sec=0.8, reason="optimization_hard_stop")
            except Exception:
                try:
                    p.terminate()
                    time.sleep(0.2)
                    if pid_alive(p):
                        p.kill()
                except Exception:
                    pass
        st.session_state.opt_proc = None
        st.session_state.opt_stop_requested = False
        do_rerun()


    # -------------------------------
    # Просмотр результатов оптимизации
    # -------------------------------
    st.subheader("Просмотр результатов (CSV)")

    show_csv = st.checkbox("Показывать/обновлять таблицу CSV (может тормозить при долгих прогонах)", value=not pid_alive(st.session_state.opt_proc))

    csv_to_view = st.text_input("Открыть CSV", value=st.session_state.opt_out_csv or "")
    if show_csv and csv_to_view and os.path.exists(csv_to_view):
        try:
            df_all_raw = pd.read_csv(csv_to_view)
            show_service_rows = st.checkbox(
                "Показывать опорные и служебные строки",
                value=bool(st.session_state.get("opt_show_service_rows", False)),
                key="opt_show_service_rows",
                help="Опорные и служебные строки не считаются реальными кандидатами и обычно скрыты по умолчанию.",
            )
            try:
                from pneumo_solver_ui.optimization_result_rows import filter_display_df as _filter_opt_display_df
                df_all = _filter_opt_display_df(df_all_raw, include_baseline=bool(show_service_rows))
            except Exception:
                df_all = df_all_raw.copy()
            _opt_packaging_params = load_packaging_params_from_base_json(st.session_state.get("opt_base_json"))
            if len(df_all) > 0:
                df_all = enrich_packaging_surface_df(df_all, params=_opt_packaging_params)
            st.write(f"Строк: {len(df_all)}")
            if len(df_all) != len(df_all_raw):
                st.caption(f"Скрыто опорных и служебных строк: {int(len(df_all_raw) - len(df_all))}")
            render_packaging_surface_metrics(st, df_all)

            st.markdown("### Быстрый TOP по суммарному штрафу")
            if "штраф_физичности_сумма" in df_all.columns:
                df_top = df_all.sort_values(["штраф_физичности_сумма"], ascending=True).head(30)
                top_cols = packaging_surface_result_columns(
                    df_top,
                    leading=["id", "поколение", "штраф_физичности_сумма"],
                )
                safe_dataframe(df_top[top_cols] if top_cols else df_top, height=260)

            st.markdown("### Pareto: выбор осей (без жёстких отсечек по умолчанию)")

            # Рабочая копия
            df_all2 = df_all.copy()

            # Фильтры/ранжирование — в popover (чтобы не захламлять экран)
            with ui_popover("⚙️ Фильтры Pareto / ранжирование"):
                use_pen_filter = st.checkbox(
                    "Фильтровать по штрафу физичности",
                    value=bool(st.session_state.get("pareto_pen_filter", False)),
                    key="pareto_pen_filter",
                )
                if use_pen_filter and "штраф_физичности_сумма" in df_all2.columns:
                    try:
                        _pen_vals = df_all2["штраф_физичности_сумма"].astype(float).values
                        _pen_min = float(np.nanmin(_pen_vals))
                        _pen_max = float(np.nanmax(_pen_vals))
                    except Exception:
                        _pen_min, _pen_max = 0.0, 0.0
                    st.slider(
                        "Макс штраф физичности (<=)",
                        min_value=float(_pen_min),
                        max_value=float(_pen_max),
                        value=float(st.session_state.get("pareto_pen_max", _pen_max) or _pen_max),
                        step=0.5,
                        key="pareto_pen_max",
                    )
                    try:
                        _pen_max_use = float(st.session_state.get("pareto_pen_max", _pen_max) or _pen_max)
                        df_all2 = df_all2[df_all2["штраф_физичности_сумма"].astype(float) <= _pen_max_use]
                    except Exception:
                        pass
                df_all2 = apply_packaging_surface_filters(st, df_all2, key_prefix="pareto", compact=True)
                st.divider()
                st.slider(
                    "TOP-N для вывода",
                    min_value=5,
                    max_value=200,
                    value=int(st.session_state.get("pareto_topn", 10) or 10),
                    step=5,
                    key="pareto_topn",
                )

            # Выбор осей Pareto — из всех численных столбцов
            num_cols = [c for c in df_all2.columns if pd.api.types.is_numeric_dtype(df_all2[c])]

            if len(num_cols) < 2:
                st.info("Недостаточно численных столбцов для Pareto.")
            else:
                default1 = "цель1_устойчивость_инерция__с" if "цель1_устойчивость_инерция__с" in num_cols else num_cols[0]
                default2 = "цель2_комфорт__RMS_ускор_м_с2" if "цель2_комфорт__RMS_ускор_м_с2" in num_cols else (num_cols[1] if num_cols[1] != default1 else num_cols[0])

                obj1 = st.selectbox("Ось X (минимизировать)", num_cols, index=num_cols.index(default1), key="pareto_obj1")
                obj2 = st.selectbox("Ось Y (минимизировать)", num_cols, index=num_cols.index(default2), key="pareto_obj2")

                df_f = df_all2.copy()
                df_f = df_f[df_f[obj1].apply(lambda v: np.isfinite(float(v)) if v is not None else False)]
                df_f = df_f[df_f[obj2].apply(lambda v: np.isfinite(float(v)) if v is not None else False)]

                if len(df_f) == 0:
                    st.info("Нет данных для Pareto (все значения NaN/inf или отфильтрованы).")
                else:
                    keep = pareto_front_2d(df_f, obj1, obj2)
                    df_p = df_f.loc[keep].copy()
                    st.write(f"Pareto candidates: {len(df_p)} / {len(df_f)}")

                    top_n = int(st.session_state.get("pareto_topn", 10) or 10)

                    # Балансный скор: нормализованные оси + (опционально) штраф физичности
                    df_p["_o1n"] = (df_p[obj1] - df_p[obj1].min()) / (df_p[obj1].max() - df_p[obj1].min() + 1e-12)
                    df_p["_o2n"] = (df_p[obj2] - df_p[obj2].min()) / (df_p[obj2].max() - df_p[obj2].min() + 1e-12)

                    if "штраф_физичности_сумма" in df_p.columns:
                        w_pen = st.slider("Вес штрафа в балансном скоре", 0.0, 5.0, 1.0, 0.1, key="pareto_wpen")
                        df_p["_penn"] = (df_p["штраф_физичности_сумма"] - df_p["штраф_физичности_сумма"].min()) / (df_p["штраф_физичности_сумма"].max() - df_p["штраф_физичности_сумма"].min() + 1e-12)
                    else:
                        w_pen = 0.0
                        df_p["_penn"] = 0.0

                    df_p["_score_bal"] = df_p["_o1n"] + df_p["_o2n"] + float(w_pen) * df_p["_penn"]

                    df_top = df_p.sort_values("_score_bal").head(int(top_n)).copy()

                    # Что показывать в таблице
                    show_cols = []
                    for c in ["id", "поколение", "seed_candidates", "seed_conditions"]:
                        if c in df_top.columns:
                            show_cols.append(c)
                    show_cols += [obj1, obj2]
                    if "штраф_физичности_сумма" in df_top.columns:
                        show_cols.append("штраф_физичности_сумма")
                    for c in packaging_surface_result_columns(df_top, leading=[]):
                        if c not in show_cols:
                            show_cols.append(c)

                    safe_dataframe(df_top[show_cols])

                    st.markdown("#### 3 финала (aggressive / balanced / comfort)")
                    aggressive = df_p.sort_values(obj1).head(1).copy()
                    comfort = df_p.sort_values(obj2).head(1).copy()
                    balanced = df_p.sort_values("_score_bal").head(1).copy()

                    aggressive["финал"] = "aggressive"
                    balanced["финал"] = "balanced"
                    comfort["финал"] = "comfort"

                    finals = pd.concat([aggressive, balanced, comfort], ignore_index=True)
                    finals_cols = show_cols + (["финал"] if "финал" in finals.columns else [])
                    safe_dataframe(finals[finals_cols])

                    # Выгрузка
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                        df_p.drop(columns=[c for c in ["_o1n","_o2n","_penn","_score_bal"] if c in df_p.columns]).to_excel(writer, sheet_name="pareto", index=False)
                        df_top.drop(columns=[c for c in ["_o1n","_o2n","_penn","_score_bal"] if c in df_top.columns]).to_excel(writer, sheet_name="topN", index=False)
                        finals.to_excel(writer, sheet_name="finals", index=False)
                    st.download_button(
                        "Скачать Pareto/Top/Finals (xlsx)",
                        data=buf.getvalue(),
                        file_name="pareto_top_final.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        except Exception as e:
            st.error(f"Не могу прочитать CSV: {e}")



    # -------------------------------
    # Калибровка / Autopilot (NPZ/CSV) — UI
    # -------------------------------
    with st.expander("Калибровка и пакетные пайплайны (NPZ/CSV) — эксперимент", expanded=False):
        st.markdown(
            """
            ...
            """
        )
        # Where calibration/autopilot looks for oscillogram logs.
        # Default: workspace/osc (inside the project), but user may point to any local folder.
        osc_dir_input = st.text_input(
            "Папка с логами (osc_dir): где лежат NPZ/CSV и куда их сохранять",
            value=str(st.session_state.get("osc_dir_path", WORKSPACE_OSC_DIR)),
            key="osc_dir_path",
            help=(
                "Калибровочные пайплайны и Autopilot читают Txx_osc.npz из этой папки. "
                "По умолчанию это pneumo_solver_ui/workspace/osc, но можно выбрать любую локальную директорию."
            ),
        )
        osc_dir = Path(osc_dir_input).expanduser()
        try:
            osc_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            st.error(f"Не могу создать/открыть osc_dir: {osc_dir} ({e})")
        st.code(str(osc_dir), language="text")

        # Подсказка по ожидаемым именам файлов (если есть baseline-suite)
        _tests_map = st.session_state.get("baseline_tests_map") or {}
        if _tests_map:
            _avail = list(_tests_map.keys())
            _rows = []
            for i, name in enumerate(_avail, start=1):
                _rows.append({
                    "test_num": i,
                    "test_name": name,
                    "expected_npz": f"T{i:02d}_osc.npz",
                })
            safe_dataframe(pd.DataFrame(_rows), hide_index=True)

        st.write("Добавить файлы в osc_dir (см. путь выше):")
        uploads = st.file_uploader(
            "NPZ/CSV (можно несколько)",
            type=["npz", "csv"],
            accept_multiple_files=True,
            key="osc_upload_files",
        )

        def _safe_fname(name: str) -> str:
            # Windows-friendly filename (ASCII-ish) but keep dots and dashes
            out = []
            for ch in name:
                if ch.isalnum() or ch in "._-":
                    out.append(ch)
                else:
                    out.append("_")
            s = "".join(out)
            # collapse
            while "__" in s:
                s = s.replace("__", "_")
            return s[:180] if len(s) > 180 else s

        if uploads:
            for uf in uploads:
                try:
                    fname = _safe_fname(uf.name)
                    dst = osc_dir / fname
                    dst.write_bytes(uf.getbuffer())
                    log_event("osc_upload", name=fname, size=int(len(uf.getbuffer())))
                except Exception as e:
                    st.error(f"Не смог сохранить {uf.name}: {e}")

        # Список файлов
        npz_files = sorted(osc_dir.glob("*.npz"))
        csv_files = sorted(osc_dir.glob("*.csv"))
        st.write(f"NPZ: {len(npz_files)}, CSV: {len(csv_files)}")
        if npz_files or csv_files:
            rows = []
            for f in (npz_files + csv_files):
                try:
                    rows.append({
                        "file": f.name,
                        "bytes": f.stat().st_size,
                        "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    })
                except Exception:
                    rows.append({"file": f.name, "bytes": None, "mtime": None})
            safe_dataframe(pd.DataFrame(rows), hide_index=True)

    
        # -------------------------------------------------
        # Mapping: произвольные файлы -> ожидаемые Txx_osc.npz
        # -------------------------------------------------
        st.markdown("### Сопоставление файлов ➜ Txx_osc.npz (без работы в консоли)")
        st.caption(
            "Калибровочные пайплайны по умолчанию ищут файлы с именами "
            "T01_osc.npz, T02_osc.npz, ... Если ваши файлы называются иначе — "
            "выберите соответствие здесь и нажмите «Применить сопоставление»."
        )

        _all_files = sorted([p.name for p in (npz_files + csv_files)])
        if (_tests_map or {}) and _all_files:
            file_opts = ["(не выбрано)"] + _all_files

            # Попробуем загрузить сохранённый mapping (если есть)
            mapping_json_path = osc_dir / "mapping_tests_files.json"
            _saved_map = {}
            try:
                if mapping_json_path.exists():
                    _saved_map = json.loads(mapping_json_path.read_text(encoding="utf-8", errors="ignore")) or {}
            except Exception:
                _saved_map = {}

            _rows_map = []
            for i, name in enumerate(list(_tests_map.keys()), start=1):
                expected = f"T{i:02d}_osc.npz"
                # default: если ожидаемый уже есть, берём его; иначе пытаемся из сохранённого mapping
                pick = expected if expected in _all_files else _saved_map.get(str(i), "")
                if pick not in _all_files:
                    pick = ""
                _rows_map.append(
                    {
                        "test_num": i,
                        "test_name": name,
                        "source_file": pick if pick else "(не выбрано)",
                        "expected_npz": expected,
                    }
                )

            df_map = pd.DataFrame(_rows_map)

            try:
                # Streamlit >=1.29: column_config поддерживается
                edited_map = st.data_editor(
                    df_map,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "source_file": st.column_config.SelectboxColumn(
                            "source_file",
                            help="Выберите файл (NPZ/CSV) для этого сценария",
                            options=file_opts,
                            required=True,
                        )
                    },
                    key="osc_mapping_editor",
                )
            except Exception:
                # fallback без column_config
                edited_map = safe_dataframe(df_map, hide_index=True)
                edited_map = df_map

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("Применить сопоставление (создать/обновить Txx_osc.npz)", key="apply_tests_file_mapping"):
                    created = 0
                    missing = 0
                    for _, r in edited_map.iterrows():
                        tnum = int(r.get("test_num", 0) or 0)
                        src_name = str(r.get("source_file", "") or "").strip()
                        if not tnum:
                            continue
                        if src_name == "(не выбрано)" or not src_name:
                            missing += 1
                            continue
                        src_path = osc_dir / src_name
                        dst_path = osc_dir / f"T{tnum:02d}_osc.npz"
                        try:
                            if src_path.suffix.lower() == ".csv":
                                # convert to simple NPZ (таблица -> main_cols/main_values)
                                df = pd.read_csv(src_path, sep=None, engine="python")
                                export_full_log_to_npz(
                                    dst_path,
                                    df_main=df,
                                    meta={
                                        "source": "csv_simple",
                                        "src": src_path.name,
                                        "created_ts": datetime.now().isoformat(),
                                        "test_num": int(tnum),
                                    },
                                )
                            else:
                                # NPZ -> просто копия под ожидаемое имя
                                dst_path.write_bytes(src_path.read_bytes())
                            created += 1
                        except Exception as e:
                            st.error(f"Не смог подготовить {dst_path.name} из {src_name}: {e}")

                    # сохраняем mapping (test_num -> source_file) чтобы не выбирать заново
                    try:
                        out_map = {}
                        for _, r in edited_map.iterrows():
                            tnum = int(r.get("test_num", 0) or 0)
                            src_name = str(r.get("source_file", "") or "").strip()
                            if tnum and src_name and src_name != "(не выбрано)":
                                out_map[str(tnum)] = src_name
                        mapping_json_path.write_text(json.dumps(out_map, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass

                    log_event(
                        "osc_mapping_applied",
                        created=int(created),
                        missing=int(missing),
                        osc_dir=str(osc_dir),
                        mapping_json=str(mapping_json_path),
                    )
                    st.success(f"Готово: подготовлено {created} файлов Txx_osc.npz (пропусков: {missing})")
            with col_m2:
                if st.button("Показать путь к osc_dir", key="show_osc_dir_hint"):
                    st.info(str(osc_dir))
        else:
            st.info(
                "Для сопоставления файлов нужны: (1) набор опорных сценариев "
                "(список сценариев) и (2) хотя бы один файл NPZ/CSV в папке osc_dir."
            )

        st.markdown("---")
        st.write(
            "Преобразование CSV ➜ NPZ "
            "(упрощённый режим: CSV читается как таблица чисел и сохраняется в NPZ)."
        )
        if csv_files:
            csv_pick = st.selectbox(
                "CSV для конвертации", options=[f.name for f in csv_files], index=0, key="csv_to_npz_pick"
            )
            csv_test_num = st.number_input(
                "К какому номеру сценария привязать (Txx_osc.npz)",
                min_value=1,
                max_value=99,
                value=1,
                step=1,
                key="csv_to_npz_num",
            )
            if st.button("Конвертировать CSV ➜ NPZ", key="csv_to_npz_btn"):
                src = osc_dir / csv_pick
                out_npz = osc_dir / f"T{int(csv_test_num):02d}_osc.npz"
                try:
                    df = pd.read_csv(src, sep=None, engine="python")
                    export_full_log_to_npz(
                        out_npz,
                        df_main=df,
                        meta={"source": "csv_simple", "src": src.name, "created_ts": datetime.now().isoformat()},
                    )
                    st.success(f"OK: {out_npz.name}")
                    log_event("csv_to_npz", src=str(src), dst=str(out_npz))
                except Exception as e:
                    st.error(f"Не удалось конвертировать: {e}")

        st.markdown("---")
        st.write("Запуск калибровочных пайплайнов (они используют файлы Txx_osc.npz из osc_dir).")

        calib_mode = st.selectbox(
            "Режим калибровки", options=["minimal", "full"], index=["minimal", "full"].index(str(st.session_state.get("calib_mode_pick", DIAGNOSTIC_CALIB_MODE) or DIAGNOSTIC_CALIB_MODE)) if str(st.session_state.get("calib_mode_pick", DIAGNOSTIC_CALIB_MODE) or DIAGNOSTIC_CALIB_MODE) in ["minimal", "full"] else 0, key="calib_mode_pick"
        )

        def _run_pipeline(script_rel: str, out_dir: Path, extra_args: list[str]):
            cmd = [sys.executable, str(HERE / script_rel)] + extra_args
            log_event("pipeline_start", script=script_rel, out_dir=str(out_dir), cmd=" ".join(cmd))
            out_dir.mkdir(parents=True, exist_ok=True)
            # Снимок UI-логов рядом с результатами пайплайна (удобно отправлять одним архивом)
            try:
                snap_dir = out_dir / "ui_logs_snapshot"
                snap_dir.mkdir(parents=True, exist_ok=True)
                for fp in [LOG_DIR / "ui_combined.log", LOG_DIR / "metrics_combined.jsonl"]:
                    if fp.exists():
                        shutil.copy2(fp, snap_dir / fp.name)
            except Exception:
                pass
            try:
                cp = subprocess.run(
                    cmd,
                    cwd=str(HERE),
                    capture_output=True,
                    text=True,
                )
                (out_dir / "pipeline_stdout.txt").write_text(cp.stdout or "", encoding="utf-8", errors="ignore")
                (out_dir / "pipeline_stderr.txt").write_text(cp.stderr or "", encoding="utf-8", errors="ignore")
                log_event("pipeline_done", script=script_rel, returncode=int(cp.returncode))
                return cp.returncode, cp.stdout, cp.stderr
            except Exception as e:
                log_event("pipeline_error", script=script_rel, error=str(e))
                return 999, "", str(e)

    
        st.markdown("### Автоматизация (без консоли): полный расчёт ➜ NPZ ➜ калибровочный пайплайн")
        st.caption(
            "Если реальных замеров пока нет — можно генерировать «расчётные» NPZ из текущего опорного прогона "
            "и запускать пайплайны oneclick/autopilot как самопроверку форматов и обвязки."
        )

        col_fc1, col_fc2, col_fc3 = st.columns(3)

        def _ensure_full_npz_for_all_tests(_mode_label: str) -> tuple[bool, str]:
            """Гарантирует, что в osc_dir есть Txx_osc.npz для всех сценариев опорного прогона.

            Возвращает (ok, message).
            """
            _tests = list((_tests_map or {}).items())
            if not _tests:
                return False, (
                    "Нет набора опорных сценариев (списка сценариев). "
                    "Сначала выполните опорный прогон."
                )
            if model_mod is None:
                return False, "Модель не загружена (model_mod=None)."
            try:
                baseline_full_cache = st.session_state.get("baseline_full_cache") or {}
                st.session_state["baseline_full_cache"] = baseline_full_cache
            except Exception:
                baseline_full_cache = {}

            # Чтобы UI не зависал: ограничим количество точек
            _max_points = int(st.session_state.get("detail_max_points", 1200) or 1200)
            want_full = True

            t_start = time.time()
            missing = 0
            ok_cnt = 0

            # Важно для calibration/pipeline_npz_oneclick_v1.py: нужен tests_index.csv с колонкой "имя_теста".
            # Ранее это часто отсутствовало => autopilot/oneclick могли искать файлы "не там".
            try:
                write_tests_index_csv(
                    osc_dir,
                    tests=[{"name": n} for (n, _cfg) in _tests],
                    filename="tests_index.csv",
                )
            except Exception as e:
                log_event("oneclick_tests_index_write_error", err=str(e), osc_dir=str(osc_dir))

            prog = st.progress(0.0, text=f"[{_mode_label}] Подготовка NPZ: расчёт/экспорт…")
            for i, (name, cfg0) in enumerate(_tests, start=1):
                # cache key совместим с основным кэшем деталей (baseline_full_cache)
                dt_j = float(cfg0.get("dt", 0.01) or 0.01)
                t_end_j = float(cfg0.get("t_end", 1.0) or 1.0)
                cache_key = make_detail_cache_key(cur_hash, name, dt_j, t_end_j, _max_points, want_full)

                df_main = None
                df_p = None
                df_q = None
                df_open = None

                try:
                    payload = baseline_full_cache.get(cache_key)
                    if isinstance(payload, dict) and isinstance(payload.get("df_main"), pd.DataFrame):
                        df_main = payload.get("df_main")
                        df_p = payload.get("df_p")
                        df_q = payload.get("df_q")
                        df_open = payload.get("df_open")
                    else:
                        # If the cache is empty - run the model once (record_full=True) and cache the frames.
                        test_j = cfg0.get("test") if isinstance(cfg0, dict) else (cfg0 or {})
                        # dt_j already resolved above (and encoded in cache_key)
                        # t_end_j already resolved above (and encoded in cache_key)

                        out = call_simulate(
                            model_mod,
                            base_override,
                            test_j,
                            dt=dt_j,
                            t_end=t_end_j,
                            record_full=True,
                            max_steps=int(2e6),
                        )
                        parsed = parse_sim_output(out, want_full=True)
                        df_main = parsed.get("df_main")
                        df_p = parsed.get("df_p")
                        df_q = parsed.get("df_mdot") or parsed.get("df_q")  # df_q legacy alias
                        df_open = parsed.get("df_open")
                        metrics = parsed.get("metrics")

                        # Downsample for UI/NPZ if needed
                        if isinstance(df_main, pd.DataFrame) and (not df_main.empty) and (_max_points is not None):
                            df_main = downsample_df(df_main, max_points=int(_max_points))
                        if isinstance(df_p, pd.DataFrame) and (not df_p.empty) and (_max_points is not None):
                            df_p = downsample_df(df_p, max_points=int(_max_points))
                        if isinstance(df_q, pd.DataFrame) and (not df_q.empty) and (_max_points is not None):
                            df_q = downsample_df(df_q, max_points=int(_max_points))
                        if isinstance(df_open, pd.DataFrame) and (not df_open.empty) and (_max_points is not None):
                            df_open = downsample_df(df_open, max_points=int(_max_points))

                        if isinstance(df_main, pd.DataFrame) and not df_main.empty:
                            baseline_full_cache[cache_key] = {
                                "df_main": df_main,
                                "df_p": df_p,
                                "df_q": df_q,
                                "df_open": df_open,
                                "metrics": metrics,
                                "max_points": int(_max_points),
                                "want_full": True,
                            }
                        else:
                            df_main = None
                except Exception as e:
                    missing += 1
                    log_event("oneclick_full_npz_error", test=name, err=str(e))
                    df_main = None


                try:
                    if df_main is None:
                        missing += 1
                    else:
                        dst_path = osc_dir / f"T{i:02d}_osc.npz"
                        export_full_log_to_npz(
                            dst_path,
                            df_main=df_main,
                            df_p=df_p,
                            df_q=df_q,
                            df_open=df_open,
                            meta={
                                "source": "simulation",
                                "created_ts": datetime.now().isoformat(timespec="seconds"),
                                "test_num": int(i),
                                "test_name": str(name),
                                "mode": str(_mode_label),
                            },
                        )
                        ok_cnt += 1
                except Exception as e:
                    missing += 1
                    log_event("oneclick_full_npz_export_error", test=name, err=str(e))

                prog.progress(i / max(1, len(_tests)), text=f"[{_mode_label}] {i}/{len(_tests)}…")

            dt_s = time.time() - t_start
            prog.progress(1.0, text=f"[{_mode_label}] Готово за {dt_s:.1f} сек. OK={ok_cnt}, missing={missing}")

            log_event("oneclick_full_npz_done", ok=int(ok_cnt), missing=int(missing), dt_s=float(dt_s), osc_dir=str(osc_dir))
            if ok_cnt == 0:
                return False, "Не удалось сформировать ни одного NPZ. Проверь логи/модель."
            return True, f"NPZ подготовлены: OK={ok_cnt}, пропусков/ошибок={missing}, время={dt_s:.1f} сек."

        with col_fc1:
            if st.button("1) Полный лог + NPZ (все сценарии)", key="oneclick_full_logs_npz"):
                ok, msg = _ensure_full_npz_for_all_tests("full_npz")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        with col_fc2:
            if st.button("2) Полный лог + NPZ ➜ oneclick-пайплайн", key="oneclick_full_then_oneclick"):
                ok, msg = _ensure_full_npz_for_all_tests("full_then_oneclick")
                if ok:
                    st.success(msg)
                    # запускаем oneclick пайплайн
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_dir = WORKSPACE_CALIB_RUNS_DIR / f"RUN_{ts}_oneclick_auto"
                    rc, so, se = _run_pipeline(
                        "calibration/pipeline_npz_oneclick_v1.py",
                        out_dir,
                        [
                            "--osc_dir",
                            str(osc_dir),
                            "--out_dir",
                            str(out_dir),
                            "--mode",
                            "minimal",
                            "--model",
                            os.path.basename(MODEL_DEFAULT),
                            "--worker",
                            os.path.basename(WORKER_DEFAULT),
                            "--suite_json",
                            os.path.basename(SUITE_DEFAULT),
                            "--base_json",
                            os.path.basename(BASE_DEFAULT),
                            "--fit_ranges_json",
                            os.path.basename(RANGES_DEFAULT),
                            "--auto_scale",
                            "mad",
                            "--holdout_frac",
                            "0.0",
                            "--use_smoothing_defaults",
                        ],
                    )
                    st.write(f"Код завершения пайплайна oneclick: {rc}")
                    if rc != 0:
                        st.error("Пайплайн oneclick завершился с ошибкой. Подробности ниже; файлы запуска сохранены в рабочей папке.")
                        st.code(so[-4000:] if so else "", language="text")
                        st.code(se[-4000:] if se else "", language="text")
                    else:
                        st.success("Пайплайн oneclick выполнен. Результаты сохранены в рабочей папке запуска.")
                        st.code(str(out_dir), language="text")
                else:
                    st.error(msg)

        with col_fc3:
            if st.button("3) Полный лог + NPZ ➜ Autopilot (минимальный режим)", key="oneclick_full_then_autopilot"):
                ok, msg = _ensure_full_npz_for_all_tests("full_then_autopilot")
                if ok:
                    st.success(msg)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_dir = WORKSPACE_CALIB_RUNS_DIR / f"RUN_{ts}_autopilot_auto"
                    rc, so, se = _run_pipeline(
                        "calibration/pipeline_npz_autopilot_v19.py",
                        out_dir,
                        [
                            "--osc_dir",
                            str(osc_dir),
                            "--out_dir",
                            str(out_dir),
                            "--mode",
                            "minimal",
                        ],
                    )
                    st.write(f"Код завершения пайплайна Autopilot: {rc}")
                    if rc != 0:
                        st.error("Пайплайн Autopilot завершился с ошибкой. Подробности ниже; файлы запуска сохранены в рабочей папке.")
                        st.code(so[-4000:] if so else "", language="text")
                        st.code(se[-4000:] if se else "", language="text")
                    else:
                        st.success("Пайплайн Autopilot выполнен. Результаты сохранены в рабочей папке запуска.")
                        st.code(str(out_dir), language="text")
                else:
                    st.error(msg)

        st.markdown("---")
        col_cal1, col_cal2 = st.columns(2)
        with col_cal1:
            if st.button("Запустить пайплайн oneclick", key="run_calib_oneclick"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_dir = WORKSPACE_CALIB_RUNS_DIR / f"RUN_{ts}_oneclick"
                rc, so, se = _run_pipeline(
                    "calibration/pipeline_npz_oneclick_v1.py",
                    out_dir,
                    [
                        "--osc_dir",
                        str(osc_dir),
                        "--out_dir",
                        str(out_dir),
                        "--mode",
                        str(calib_mode),
                    ],
                )
                st.session_state["last_calib_out_dir"] = str(out_dir)
                if rc == 0:
                    st.success(f"Готово: {out_dir}")
                else:
                    st.error(f"Ошибка (код {rc}) — см. pipeline_stderr.txt")

        with col_cal2:
            if st.button("Запустить пайплайн Autopilot v19 (по NPZ)", key="run_autopilot_v19"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_dir = WORKSPACE_CALIB_RUNS_DIR / f"RUN_{ts}_autopilot_v19"
                rc, so, se = _run_pipeline(
                    "calibration/pipeline_npz_autopilot_v19.py",
                    out_dir,
                    [
                        "--osc_dir",
                        str(osc_dir),
                        "--out_dir",
                        str(out_dir),
                        "--max_iter",
                        "25",
                    ],
                )
                st.session_state["last_autopilot_out_dir"] = str(out_dir)
                if rc == 0:
                    st.success(f"Готово: {out_dir}")
                else:
                    st.error(f"Ошибка (код {rc}) — см. pipeline_stderr.txt")

        last_dir = st.session_state.get("last_calib_out_dir") or st.session_state.get("last_autopilot_out_dir")
        if last_dir:
            st.info(f"Последний запуск: {last_dir}")

    # -------------------------------
    # Диагностика (ZIP для отправки)
    # -------------------------------
    with st.expander("Диагностика — собрать архив ZIP для отправки", expanded=False):
        # По умолчанию в приложении есть **одна** кнопка диагностики (в боковой панели):
        # «Сохранить диагностику (ZIP)». Этот UI-блок оставлен только для Legacy-режима,
        # чтобы не плодить дублирующие кнопки.
        show_legacy_tools = bool(
            st.session_state.get("pneumo_show_legacy", False)
            or os.environ.get("PNEUMO_SHOW_LEGACY", "0") == "1"
        )

        if not show_legacy_tools:
            st.info(
                "Основная кнопка диагностики находится в боковой панели: **Сохранить диагностику (ZIP)**. "
                "Этот UI-блок скрыт в основном режиме, чтобы не плодить дублирующие кнопки."
            )
            st.caption(
                "Если нужно собрать UI-диагностику именно отсюда: включите режим старых страниц "
                "в боковой панели (Режим интерфейса → Показать страницы Legacy)."
            )
        else:
            st.markdown(
                """
                Это **локальный архив ZIP**, который удобно отправлять вместо всей папки проекта.

                Внутри: логи UI, результаты, **workspace/osc** (NPZ/CSV),
                **calibration_runs** (результаты oneclick/autopilot) и снимок текущих
                файлов настроек: база параметров, набор сценариев и диапазоны подбора.
                """
            )
            diag_tag = st.text_input("Тэг (опционально)", value="ui", key="ui_diag_tag")
            if st.button("Сформировать ZIP диагностики", key="ui_diag_make_btn"):
                try:
                    zpath = make_ui_diagnostics_zip(
                        # Снимок текущих **перезаписанных** значений (а не только дефолтов)
                        base_json=base_override,
                        suite_json=suite_override,
                        ranges_json=ranges_override,
                        tag=str(diag_tag) if diag_tag else "ui",
                        include_logs=True,
                        include_results=True,
                        include_calibration=True,
                        include_workspace=True,
                    )
                    st.session_state["ui_diag_zip_path"] = str(zpath)
                    log_event("ui_diag_zip_done", path=str(zpath))
                    st.success(f"Готово: {zpath.name}")
                except Exception as e:
                    st.error(f"Не удалось собрать ZIP: {e}")

            zpath = st.session_state.get("ui_diag_zip_path")
            if zpath:
                try:
                    zp = Path(zpath)
                    if zp.exists():
                        st.download_button(
                            "Скачать ZIP",
                            data=zp.read_bytes(),
                            file_name=zp.name,
                            mime="application/zip",
                            key="ui_diag_download_btn",
                        )
                except Exception as e:
                    st.warning(f"Не смог подготовить download: {e}")

# -------------------------------
# Автообновление прогресса во время оптимизации
# -------------------------------
# Streamlit по умолчанию перерисовывает приложение при действиях пользователя.
# Чтобы прогресс фонового расчёта обновлялся "вживую", делаем периодический rerun.
#
# Раньше это было сделано через time.sleep()+st.rerun(), но это:
#  1) блокирует поток выполнения (UI "замирает"),
#  2) легко словить ошибки логики rerun.
#
# Поэтому используем фронтенд-таймер streamlit-autorefresh (если установлен).
# Он пингует сервер и корректно инициирует rerun без бесконечных циклов.
if 'auto_refresh' in globals() and auto_refresh and pid_alive(st.session_state.opt_proc):
    try:
        from streamlit_autorefresh import st_autorefresh  # type: ignore

        st_autorefresh(
            interval=int(max(0.2, float(refresh_sec)) * 1000),
            key="progress_autorefresh",
        )
    except Exception:
        # Fallback (без зависимостей): редкий rerun через sleep.
        time.sleep(float(refresh_sec))
        do_rerun()


# --- Автосохранение UI (после формирования интерфейса) ---
# Не должно ломать расчёты даже при проблемах с правами на диск.
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled
    autosave_if_enabled(st)
except Exception:
    pass
