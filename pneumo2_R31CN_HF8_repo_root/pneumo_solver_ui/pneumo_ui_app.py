# -*- coding: utf-8 -*-
"""
pneumo_ui_app.py

Streamlit UI:
- Р·Р°РїСѓСЃРє РѕРґРёРЅРѕС‡РЅС‹С… С‚РµСЃС‚РѕРІ (baseline),
- Р·Р°РїСѓСЃРє РѕРїС‚РёРјРёР·Р°С†РёРё (С„РѕРЅРѕРІС‹Р№ РїСЂРѕС†РµСЃСЃ) РёР· UI,
- РїСЂРѕСЃРјРѕС‚СЂ/С„РёР»СЊС‚СЂ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ.

РўСЂРµР±РѕРІР°РЅРёСЏ: streamlit, numpy, pandas, openpyxl.

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
                st.info("РСЃРїРѕР»СЊР·СѓР№С‚Рµ РјРµРЅСЋ РЅР°РІРёРіР°С†РёРё СЃР»РµРІР°.")
        except Exception:
            st.info("РСЃРїРѕР»СЊР·СѓР№С‚Рµ РјРµРЅСЋ РЅР°РІРёРіР°С†РёРё СЃР»РµРІР°.")


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
        st.metric("РђРєС‚РёРІРЅС‹Р№ РїСѓС‚СЊ", "StageRunner" if opt_use_staged else "Distributed")
    with cols[1]:
        st.metric("Р›РёРјРёС‚, РјРёРЅ", f"{minutes:g}")
    if compact:
        st.caption(f"jobs={jobs}; run={run_name}; csv={out_prefix}")
    else:
        with cols[2]:
            st.metric("jobs", str(jobs))
        with cols[3]:
            st.metric("Run", run_name)
        st.caption(f"CSV prefix: {out_prefix}")

    st.caption(f"Seed/promotion policy: {stage_policy_mode}")
    st.caption("Stage-specific seed/promotion profile: " + stage_seed_policy_summary_text())
    st.caption(f"System Influence eps_rel: {influence_eps_rel:g}")
    st.caption("Adaptive epsilon РґР»СЏ System Influence: " + ("on" if adaptive_influence_eps else "off"))

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
        missing_message="РџРѕСЃР»РµРґРЅСЏСЏ РѕРїС‚РёРјРёР·Р°С†РёСЏ РїРѕРєР° РЅРµ Р·Р°РїСѓСЃРєР°Р»Р°СЃСЊ (РёР»Рё СѓРєР°Р·Р°С‚РµР»СЊ РµС‰С‘ РЅРµ Р·Р°РїРёСЃР°РЅ).",
        packaging_heading="Packaging snapshot (last run)",
        packaging_interference_prefix="Р’ РїРѕСЃР»РµРґРЅРµРј run РµСЃС‚СЊ packaging-interference evidence",
    )


from pneumo_solver_ui.ring_visuals import (
    load_ring_spec_from_test_cfg,
    load_ring_spec_from_npz,
    build_ring_visual_payload_from_spec,
    build_nominal_ring_progress_from_spec,
    embed_path_payload_on_ring,
)

# Р РµРґР°РєС‚РѕСЂ СЃС†РµРЅР°СЂРёРµРІ: СЃРµРіРјРµРЅС‚С‹вЂ‘РєРѕР»СЊС†Рѕ (РµРґРёРЅСЃС‚РІРµРЅРЅС‹Р№ РїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ СЂРµРґР°РєС‚РѕСЂ СЃС†РµРЅР°СЂРёРµРІ).
# РЎС‚Р°СЂС‹Р№ СЂРµРґР°РєС‚РѕСЂ СЃС†РµРЅР°СЂРёРµРІ СѓРґР°Р»С‘РЅ РЅР°РјРµСЂРµРЅРЅРѕ; СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ СЃРѕ СЃС‚Р°СЂС‹РјРё СЃС†РµРЅР°СЂРёСЏРјРё РќР• РѕР±РµСЃРїРµС‡РёРІР°РµС‚СЃСЏ.
try:
    from pneumo_solver_ui.ui_scenario_ring import render_ring_scenario_generator
    _HAS_RING_SCENARIO_EDITOR = True
except Exception:
    render_ring_scenario_generator = None  # type: ignore
    _HAS_RING_SCENARIO_EDITOR = False

# РћРїС†РёРѕРЅР°Р»СЊРЅРѕ: РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РіСЂР°С„РёРєРё (Plotly). Р•СЃР»Рё РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅРѕ вЂ” UI РїСЂРѕРґРѕР»Р¶РёС‚ СЂР°Р±РѕС‚Р°С‚СЊ Р±РµР· Plotly.
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

# Optional: РјРµС‚СЂРёРєРё РїСЂРѕС†РµСЃСЃР° (CPU/RAM). Р•СЃР»Рё psutil РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ вЂ” РїСЂРѕСЃС‚Рѕ РѕС‚РєР»СЋС‡Р°РµРј РјРµС‚СЂРёРєРё.
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

# Fallback (Р±РµР· Streamlit Components): matplotlib-РІРёР·СѓР°Р»РёР·Р°С†РёСЏ РјРµС…Р°РЅРёРєРё.
# Р­С‚Рѕ Р»РµС‡РёС‚ С‚РёРїРѕРІС‹Рµ РїСЂРѕР±Р»РµРјС‹ РІСЂРѕРґРµ "Unrecognized component API version" / "apiVersion undefined" РІ РЅРµРєРѕС‚РѕСЂС‹С… РѕРєСЂСѓР¶РµРЅРёСЏС….
#
# Р’Р°Р¶РЅРѕ: fallback-РјРѕРґСѓР»СЊ Р»РµР¶РёС‚ Р’РќРЈРўР Р РїР°РєРµС‚Р° pneumo_solver_ui.
# РџРѕСЌС‚РѕРјСѓ РѕСЃРЅРѕРІРЅРѕР№ РёРјРїРѕСЂС‚ вЂ” package import. Р•СЃР»Рё sys.path СЃР»РѕРјР°РЅ, РїСЂРѕР±СѓРµРј Р·Р°РіСЂСѓР·РёС‚СЊ РїРѕ Р°Р±СЃРѕР»СЋС‚РЅРѕРјСѓ РїСѓС‚Рё С„Р°Р№Р»Р°.
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


# Optional: SVG auto-trace / Р°РЅР°Р»РёР· СЃС…РµРјС‹ РїРѕ РіРµРѕРјРµС‚СЂРёРё Р»РёРЅРёР№
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
    """Р’С‹Р±СЂР°С‚СЊ РєР°РЅРѕРЅРёС‡РµСЃРєРёР№ С„Р°Р№Р» РјРѕРґРµР»Рё РґР»СЏ UI/РѕРїС‚РёРјРёР·Р°С†РёРё.

    Р РµР°Р»СЊРЅС‹Р№ РєР°РЅРѕРЅ СѓР¶Рµ РёРЅРєР°РїСЃСѓР»РёСЂРѕРІР°РЅ РІ optimization_defaults.canonical_model_path():
    СЃРЅР°С‡Р°Р»Р° scheme_fingerprint, Р·Р°С‚РµРј Р°РєС‚СѓР°Р»СЊРЅР°СЏ v9 Camozzi, Р·Р°С‚РµРј worldroad.
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
    """Р”РѕСЃС‚Р°С‚СЊ РїР°СЂР°РјРµС‚СЂ РєР°Рє float РїРѕ *РєР°РЅРѕРЅРёС‡РµСЃРєРѕРјСѓ* РєР»СЋС‡Сѓ.

    ABSOLUTE LAW:
    - РЅРёРєР°РєРёС… Р°Р»РёР°СЃРѕРІ/РґСѓР±Р»РµР№ РєР»СЋС‡РµР№ (РЅР°РїСЂРёРјРµСЂ "Р±Р°Р·Р°" vs "Р±Р°Р·Р°_Рј") РІ СЂР°РЅС‚Р°Р№РјРµ.
    - РµСЃР»Рё РєР°РЅРѕРЅРёС‡РµСЃРєРёР№ РєР»СЋС‡ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, РІРѕР·РІСЂР°С‰Р°РµРј `default`.

    Р’РђР–РќРћ:
    - Р­С‚РѕС‚ helper РЅР°РјРµСЂРµРЅРЅРѕ РќР• РїРѕРґРґРµСЂР¶РёРІР°РµС‚ fallback РЅР° Р°Р»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Рµ РєР»СЋС‡Рё.
      Р›СЋР±С‹Рµ СЃС‚Р°СЂС‹Рµ/Р»РёС€РЅРёРµ РєР»СЋС‡Рё РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РІС‹СЏРІР»РµРЅС‹ РЅР° РіСЂР°РЅРёС†Рµ (Р·Р°РіСЂСѓР·РєР° С„Р°Р№Р»Р°)
      Рё РёСЃРїСЂР°РІР»РµРЅС‹ С‚Р°Рј, Р° РЅРµ СЂР°СЃРїСЂРѕСЃС‚СЂР°РЅСЏС‚СЊСЃСЏ РїРѕ РєРѕРґСѓ.
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

# Р’Р°Р¶РЅРѕ: UI РґРѕР»Р¶РµРЅ СѓРІР°Р¶Р°С‚СЊ РёР·РѕР»СЏС†РёСЋ СЃРµСЃСЃРёРё (PNEUMO_LOG_DIR/PNEUMO_WORKSPACE_DIR),
# РёРЅР°С‡Рµ Р»РѕРіРё СЃРјРµС€РёРІР°СЋС‚СЃСЏ РјРµР¶РґСѓ РїСЂРѕРіРѕРЅР°РјРё Рё Р»РѕРјР°СЋС‚ strict loglint РІ autotest/send-bundle.

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
# Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РєР°С‚Р°Р»РѕРіРё workspace (UI РїРёС€РµС‚ СЃСЋРґР° Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё)
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
    """Р‘РµР·РѕРїР°СЃРЅРѕРµ РёРјСЏ С„Р°Р№Р»Р° РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РІ workspace.

    - РЈР±РёСЂР°РµРј РїСЂРѕР±РµР»С‹/РєРёСЂРёР»Р»РёС†Сѓ/СЃРїРµС†СЃРёРјРІРѕР»С‹ (Windows-friendly)
    - РћСЃС‚Р°РІР»СЏРµРј . _ - РґР»СЏ С‡РёС‚Р°РµРјРѕСЃС‚Рё
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
    """РЎРѕС…СЂР°РЅРёС‚СЊ Р·Р°РіСЂСѓР¶РµРЅРЅС‹Р№ С„Р°Р№Р» (st.file_uploader) РІ workspace Рё РІРµСЂРЅСѓС‚СЊ РїСѓС‚СЊ.

    prefix:
      - 'road'  -> WORKSPACE_ROAD_DIR
      - 'axay'/'maneuver' -> WORKSPACE_MAN_DIR
      - РёРЅР°С‡Рµ  -> WORKSPACE_UPLOADS_DIR
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
        # uploaded_file РјРѕР¶РµС‚ Р±С‹С‚СЊ UploadedFile (getbuffer) РёР»Рё file-like (read)
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
    """Р•РґРёРЅР°СЏ С‚РѕС‡РєР° Р»РѕРіРёСЂРѕРІР°РЅРёСЏ (UI schema, strict JSONL).

    РўСЂРµР±РѕРІР°РЅРёСЏ, РєРѕС‚РѕСЂС‹Рµ СѓРґРѕРІР»РµС‚РІРѕСЂСЏРµРј:
    - strict JSON (Р±РµР· NaN/Inf) РґР»СЏ СѓСЃС‚РѕР№С‡РёРІРѕРіРѕ РїР°СЂСЃРёРЅРіР°;
    - СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ СЃРѕ strict loglint (--schema ui --strict --check_seq);
    - СѓРІР°Р¶РµРЅРёРµ РёР·РѕР»РёСЂРѕРІР°РЅРЅС‹С… РґРёСЂРµРєС‚РѕСЂРёР№ (PNEUMO_LOG_DIR).

    РџРёС€РµРј РІ:
    - ui_*.log (RotatingFileHandler, СЃС‚СЂРѕРєР° JSON)
    - metrics_*.jsonl (СЃС‚СЂРѕРіРёР№ JSONL)
    - metrics_combined.jsonl (СЃС‚СЂРѕРіРёР№ JSONL, РІСЃРµ СЃРµСЃСЃРёРё)

    Best-effort: РЅРёРєРѕРіРґР° РЅРµ РґРѕР»Р¶РµРЅ СЂРѕРЅСЏС‚СЊ UI.
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



# РџСЂРѕР±СЂР°СЃС‹РІР°РµРј callback РґР»СЏ РІРЅСѓС‚СЂРµРЅРЅРёС… РјРѕРґСѓР»РµР№ (fallback-Р°РЅРёРјР°С†РёРё) Р±РµР· РїСЂСЏРјРѕРіРѕ РёРјРїРѕСЂС‚Р° СЌС‚РѕРіРѕ С„Р°Р№Р»Р°.
# Р’ Streamlit-СЃРµСЃСЃРёРё РјРѕР¶РЅРѕ С…СЂР°РЅРёС‚СЊ callable. Р­С‚Рѕ РЅСѓР¶РЅРѕ РґР»СЏ mech_anim_fallback.
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
    """Р—Р°РїСѓСЃРє Desktop Animator РІ follow-СЂРµР¶РёРјРµ (best-effort).

    - РќРµ Р±СЂРѕСЃР°РµС‚ РёСЃРєР»СЋС‡РµРЅРёСЏ РЅР°СЂСѓР¶Сѓ (UI РЅРµ РґРѕР»Р¶РµРЅ РїР°РґР°С‚СЊ).
    - Р’РѕР·РІСЂР°С‰Р°РµС‚ True РµСЃР»Рё РїСЂРѕС†РµСЃСЃ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ.
    - РџРёС€РµС‚ stdout/stderr animator РІ session log dir Рё Р»РѕРіРёСЂСѓРµС‚ РєРѕРґ Р·Р°РІРµСЂС€РµРЅРёСЏ.
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
# Р¦РµР»СЊ: РїРѕСЃР»Рµ refresh (РЅРѕРІР°СЏ session_state) РЅРµ РїРµСЂРµСЃС‡РёС‚С‹РІР°С‚СЊ baseline/РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ,
# Р° РїРѕРґС…РІР°С‚С‹РІР°С‚СЊ СЃ РґРёСЃРєР°. РљСЌС€ С…СЂР°РЅРёС‚СЃСЏ РІ WORKSPACE_DIR/cache/baseline/<key>/...

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
    pressure_unit_label="Р±Р°СЂ (РёР·Р±.)",
    pressure_offset_pa=lambda: P_ATM,
    pressure_divisor_pa=lambda: BAR_PA,
    length_unit_label="РјРј",
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
        st.info("РќРµС‚ РґР°РЅРЅС‹С…/СЃРёРіРЅР°Р»РѕРІ РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ.")
        return
    if not _HAS_PLOTLY:
        st.warning(
            "Plotly РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ вЂ” РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РіСЂР°С„РёРєРё (Graph Studio / Plotly) РѕС‚РєР»СЋС‡РµРЅС‹.\n\nР РµС€РµРЅРёРµ: СѓСЃС‚Р°РЅРѕРІРёС‚Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё С‡РµСЂРµР· Р»Р°СѓРЅС‡РµСЂ (РєРЅРѕРїРєР° В«РЈСЃС‚Р°РЅРѕРІРёС‚СЊ Р·Р°РІРёСЃРёРјРѕСЃС‚РёВ») вЂ” Р±РµР· СЂСѓС‡РЅРѕРіРѕ РІРІРѕРґР° РєРѕРјР°РЅРґ."
        )
        return

    # time axis
    if tcol not in df.columns:
        st.warning(f"РќРµС‚ РєРѕР»РѕРЅРєРё РІСЂРµРјРµРЅРё '{tcol}'")
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
    "Plotly РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ вЂ” РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РіСЂР°С„РёРєРё (Graph Studio / Plotly) РѕС‚РєР»СЋС‡РµРЅС‹.\n\n"
    "Р РµС€РµРЅРёРµ: СѓСЃС‚Р°РЅРѕРІРёС‚Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё С‡РµСЂРµР· Р»Р°СѓРЅС‡РµСЂ (РєРЅРѕРїРєР° В«РЈСЃС‚Р°РЅРѕРІРёС‚СЊ Р·Р°РІРёСЃРёРјРѕСЃС‚РёВ») вЂ” Р±РµР· СЂСѓС‡РЅРѕРіРѕ РІРІРѕРґР° РєРѕРјР°РЅРґ."
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

    if df_main is None or "РІСЂРµРјСЏ_СЃ" not in df_main.columns or len(df_main) == 0:
        return events

    t_arr = df_main["РІСЂРµРјСЏ_СЃ"].to_numpy(dtype=float)
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
    for c in ["Р›Рџ", "РџРџ", "Р›Р—", "РџР—"]:
        col = f"РєРѕР»РµСЃРѕ_РІ_РІРѕР·РґСѓС…Рµ_{c}"
        if col in df_main.columns:
            m = df_main[col].to_numpy()
            # treat any nonzero as True
            starts = _run_starts(m != 0)
            for i0 in starts:
                add_event(i0, "warn", "wheel_lift", c, f"РљРѕР»РµСЃРѕ {c} РІ РІРѕР·РґСѓС…Рµ")

    # --------------------
    
    # --------------------
    # 1b) Sanity check: road differs, but wheels look identical
    # --------------------
    try:
        corners = ["Р›Рџ", "РџРџ", "Р›Р—", "РџР—"]
        road_cols = [f"РґРѕСЂРѕРіР°_{c}_Рј" for c in corners]
        wheel_cols = [f"РїРµСЂРµРјРµС‰РµРЅРёРµ_РєРѕР»РµСЃР°_{c}_Рј" for c in corners]
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
                    "РЎР°РЅРёС‚Рё: РїСЂРѕС„РёР»СЊ РґРѕСЂРѕРіРё СЂР°Р·Р»РёС‡Р°РµС‚СЃСЏ РїРѕ РєРѕР»С‘СЃР°Рј, РЅРѕ С…РѕРґС‹ РєРѕР»С‘СЃ РїРѕС‡С‚Рё РѕРґРёРЅР°РєРѕРІС‹ вЂ” РїСЂРѕРІРµСЂСЊС‚Рµ road_func/РіСЂР°С„РёРєРё/РєР»СЋС‡Рё РєРѕР»РµРё/Р±Р°Р·С‹.",
                )
    except Exception:
        pass

# 2) Stroke limit / bump stop near
    # --------------------
    stroke = float(params_abs.get("С…РѕРґ_С€С‚РѕРєР°", 0.25))
    margin = float(test.get("target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_СѓРїРѕСЂР°_С€С‚РѕРєР°_Рј", 0.005))
    margin = max(0.0, margin)

    for c in ["Р›Рџ", "РџРџ", "Р›Р—", "РџР—"]:
        col = f"РїРѕР»РѕР¶РµРЅРёРµ_С€С‚РѕРєР°_{c}_Рј"
        if col in df_main.columns:
            x = df_main[col].to_numpy(dtype=float)
            m_low = x <= margin
            m_high = x >= (stroke - margin)
            for i0 in _run_starts(m_low):
                add_event(i0, "warn", "stroke_limit", c, f"РЁС‚РѕРє {c}: Р±Р»РёР·РєРѕ Рє СѓРїРѕСЂСѓ (min)")
            for i0 in _run_starts(m_high):
                add_event(i0, "warn", "stroke_limit", c, f"РЁС‚РѕРє {c}: Р±Р»РёР·РєРѕ Рє СѓРїРѕСЂСѓ (max)")

    # --------------------
    # 3) Rod speed limit
    # --------------------
    v_lim = float(test.get("target_Р»РёРјРёС‚_СЃРєРѕСЂРѕСЃС‚Рё_С€С‚РѕРєР°_Рј_СЃ", 2.0))
    if v_lim > 0:
        for c in ["Р›Рџ", "РџРџ", "Р›Р—", "РџР—"]:
            col = f"СЃРєРѕСЂРѕСЃС‚СЊ_С€С‚РѕРєР°_{c}_Рј_СЃ"
            if col in df_main.columns:
                v = df_main[col].to_numpy(dtype=float)
                m_v = np.abs(v) > v_lim
                for i0 in _run_starts(m_v):
                    add_event(i0, "warn", "rod_speed", c, f"РЎРєРѕСЂРѕСЃС‚СЊ С€С‚РѕРєР° {c} > {v_lim:g} Рј/СЃ")

    # --------------------
    # 4) Overpressure / vacuum checks (by node pressures if present)
    # --------------------
    if df_p is not None and "РІСЂРµРјСЏ_СЃ" in df_p.columns and len(df_p) > 1:
        cols = [c for c in df_p.columns if c != "РІСЂРµРјСЏ_СЃ" and c != "РђРўРњ"]
        if cols:
            Pmax_abs = float(params_abs.get("РґР°РІР»РµРЅРёРµ_Pmax_РїСЂРµРґРѕС…СЂР°РЅ", P_ATM + 8e5))
            pmax_thr = Pmax_abs + float(pmax_margin_bar) * BAR_PA

            try:
                # Align df_p -> df_main time vector (nearest) so events don't disappear when tables are downsampled differently.
                t_src = df_p["РІСЂРµРјСЏ_СЃ"].to_numpy(dtype=float)
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
                    add_event(i0, "error", "overpressure", "nodes", "P>РџР Р•Р”РћРҐ (max node)")

            vac_thr = P_ATM + float(vacuum_min_gauge_bar) * BAR_PA
            # do not go below absolute min + small epsilon (avoid false positives)
            p_abs_min = float(params_abs.get("РјРёРЅРёРјР°Р»СЊРЅРѕРµ_Р°Р±СЃРѕР»СЋС‚РЅРѕРµ_РґР°РІР»РµРЅРёРµ_РџР°", 1000.0))
            vac_thr = max(vac_thr, p_abs_min + 1.0)

            if p_min is not None:
                for i0 in _run_starts(p_min < vac_thr):
                    add_event(i0, "warn", "vacuum", "nodes", f"Р’Р°РєСѓСѓРј: min node < {vacuum_min_gauge_bar:g} Р±Р°СЂ(РёР·Р±)")

    # --------------------
    # 5) Valve chatter (rapid toggling) from df_open
    # --------------------
    if df_open is not None and "РІСЂРµРјСЏ_СЃ" in df_open.columns and len(df_open) > 1:
        # Align df_open -> df_main time vector (nearest), so event markers don't randomly disappear.
        try:
            t_src = df_open["РІСЂРµРјСЏ_СЃ"].to_numpy(dtype=float)
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
        edge_cols = [c for c in df_open_aligned.columns if c != "РІСЂРµРјСЏ_СЃ"]
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
                    add_event(togg_list[i], "info", "chatter", nm, f"Р”СЂРµР±РµР·Рі: {nm} ({win_cnt} toggles/{chatter_window_s:.2f}s)")
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
    """Р•РґРёРЅС‹Р№ helper РґР»СЏ РіСЂР°С„РёРєРѕРІ: Plotly (РµСЃР»Рё СѓСЃС‚Р°РЅРѕРІР»РµРЅ) РёР»Рё fallback РЅР° st.line_chart.

    Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ: РµСЃР»Рё Р·Р°РґР°РЅ playhead_x, СЂРёСЃСѓРµРј РІРµСЂС‚РёРєР°Р»СЊРЅСѓСЋ Р»РёРЅРёСЋ Рё РјР°СЂРєРµСЂС‹ Р·РЅР°С‡РµРЅРёР№
    РЅР° РєР°Р¶РґРѕР№ РєСЂРёРІРѕР№ РІ С‚РµРєСѓС‰РёР№ РјРѕРјРµРЅС‚ РІСЂРµРјРµРЅРё (РїРѕ Р±Р»РёР¶Р°Р№С€РµРјСѓ РёРЅРґРµРєСЃСѓ).

    Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃР»РѕРІР°СЂСЊ СЃ РґР°РЅРЅС‹РјРё playhead (idx/x/values) РёР»Рё None.
    """
    if df is None or len(df) == 0:
        st.info("РќРµС‚ РґР°РЅРЅС‹С… РґР»СЏ РіСЂР°С„РёРєР°.")
        return None


    # --- v6_32+R59: prefer *_rel0 displacement columns for plots (if available) ---
    # Р’ РјРѕРґРµР»Рё РґР»СЏ РјРµС‚СЂРёС‡РµСЃРєРёС…/СѓРіР»РѕРІС‹С… РєРѕР»РѕРЅРѕРє СЃРѕР·РґР°СЋС‚СЃСЏ РїР°СЂС‹:
    #   <РёРјСЏ>            (Р°Р±СЃРѕР»СЋС‚ / РёСЃС…РѕРґРЅРѕРµ)
    #   <РёРјСЏ>_rel0       (РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РЅСѓР»РµРІРѕР№ РїРѕР·С‹: СЂРѕРІРЅР°СЏ РґРѕСЂРѕРіР°, СЃС‚Р°С‚РёС‡РµСЃРєР°СЏ РїРѕРґРІРµСЃРєР°)
    #
    # Р§С‚РѕР±С‹ РІ Р»РµРіРµРЅРґР°С…/РІС‹Р±РѕСЂРµ РєРѕР»РѕРЅРѕРє РѕСЃС‚Р°РІР°Р»РёСЃСЊ РёСЃС…РѕРґРЅС‹Рµ РёРјРµРЅР°, РјС‹ РїСЂРё РЅР°Р»РёС‡РёРё *_rel0
    # РїРѕРґРјРµРЅСЏРµРј РґР°РЅРЅС‹Рµ РІ df[<РёРјСЏ>] РЅР° df[<РёРјСЏ>_rel0].
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
            # СЂР°Р±РѕС‚Р°РµРј РЅР° РєРѕРїРёРё, С‡С‚РѕР±С‹ РЅРµ РїРѕСЂС‚РёС‚СЊ РёСЃС…РѕРґРЅС‹Р№ df РІ РєРµС€Рµ/СЃРµСЃСЃРёРё
            df = df.copy()
            for src, dst in rel_map.items():
                df[dst] = df[src]
    y_cols = [c for c in y_cols if c in df.columns]
    if len(y_cols) == 0:
        st.info("РќРµ РІС‹Р±СЂР°РЅРѕ РЅРё РѕРґРЅРѕР№ РєРѕР»РѕРЅРєРё РґР»СЏ РіСЂР°С„РёРєР°.")
        return None

    # ---- performance guard: while fallback animation is playing, avoid heavy Plotly rebuilds ----
    try:
        if st.session_state.get("skip_heavy_on_play", True) and is_any_fallback_anim_playing():
            if not st.session_state.get("_skip_plotly_notice_shown", False):
                st.info("Play (fallback) Р°РєС‚РёРІРµРЅ в†’ Plotly-РіСЂР°С„РёРєРё РІСЂРµРјРµРЅРЅРѕ СЃРєСЂС‹С‚С‹, С‡С‚РѕР±С‹ Р°РЅРёРјР°С†РёСЏ РЅРµ С‚РѕСЂРјРѕР·РёР»Р°. РџРѕСЃС‚Р°РІСЊ РЅР° РїР°СѓР·Сѓ, С‡С‚РѕР±С‹ РІРµСЂРЅСѓС‚СЊ РіСЂР°С„РёРєРё.")
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
safe_set_page_config(page_title="РџРЅРµРІРјРѕРїРѕРґРІРµСЃРєР°: solver+РѕРїС‚РёРјРёР·Р°С†РёСЏ", layout="wide")


# --- UI bootstrap + СЃР°РјРѕРїСЂРѕРІРµСЂРєР°: РїРѕРєР°Р·Р°С‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ СЏРІРЅС‹Р№ СЃС‚Р°С‚СѓСЃ (С‡С‚РѕР±С‹ РЅРµ Р±С‹Р»Рѕ РѕС‰СѓС‰РµРЅРёСЏ "РІРёСЃРёС‚") ---
_startup_first = "_ui_startup_done" not in st.session_state
_startup_status = None
_startup_spinner_cm = None

if _startup_first:
    if hasattr(st, "status"):
        try:
            _startup_status = st.status("РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РёРЅС‚РµСЂС„РµР№СЃР°вЂ¦", expanded=True)
        except Exception:
            _startup_status = None
    if _startup_status is None:
        # Fallback: РѕР±С‹С‡РЅС‹Р№ СЃРїРёРЅРЅРµСЂ (РёСЃС‡РµР·Р°РµС‚ СЃР°Рј)
        _startup_spinner_cm = st.spinner("РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РёРЅС‚РµСЂС„РµР№СЃР°вЂ¦")
        try:
            _startup_spinner_cm.__enter__()
        except Exception:
            _startup_spinner_cm = None

try:
    # 1) UI bootstrap: РїРѕРґСЃРєР°Р·РєРё + Р°РІС‚РѕР·Р°РіСЂСѓР·РєР° СЃРѕС…СЂР°РЅС‘РЅРЅРѕРіРѕ РІРІРѕРґР° + РґРµС„РѕР»С‚С‹ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё + run artifacts
    if _startup_status is not None:
        try:
            _startup_status.write("Р—Р°РіСЂСѓР·РєР° СЃРѕС…СЂР°РЅС‘РЅРЅС‹С… РЅР°СЃС‚СЂРѕРµРє Рё СЃРїСЂР°РІРєРёвЂ¦")
        except Exception:
            pass

    try:
        from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
        _ui_bootstrap(st)
    except Exception:
        # bootstrap РЅРµ РґРѕР»Р¶РµРЅ Р»РѕРјР°С‚СЊ Р·Р°РїСѓСЃРє
        pass

    # 2) РђРІС‚РѕРЅРѕРјРЅР°СЏ СЃР°РјРѕРїСЂРѕРІРµСЂРєР° (QC): РЅР° СЃС‚Р°СЂС‚Рµ РѕРЅР° РјРѕР¶РµС‚ Р·Р°РЅРёРјР°С‚СЊ СЃРµРєСѓРЅРґС‹ вЂ” РїРѕСЌС‚РѕРјСѓ РїРѕРєР°Р·С‹РІР°РµРј СЃС‚Р°С‚СѓСЃ.
    # Streamlit РїРµСЂРµР·Р°РїСѓСЃРєР°РµС‚ СЃРєСЂРёРїС‚ РЅР° РєР°Р¶РґРѕРµ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёРµ вЂ” РґРµСЂР¶РёРј С„Р»Р°Рі РІ session_state.
    try:
        if "_autoselfcheck_v1_done" not in st.session_state:
            if _startup_status is not None:
                try:
                    _startup_status.write("РЎР°РјРѕРїСЂРѕРІРµСЂРєР° (QC): РїСЂРѕРІРµСЂСЏРµРј С†РµР»РѕСЃС‚РЅРѕСЃС‚СЊ РїР°РєРµС‚Р°вЂ¦")
                except Exception:
                    pass

            from pneumo_solver_ui.tools.autoselfcheck import ensure_autoselfcheck_once
            from pneumo_solver_ui.diag.json_safe import json_dumps

            _r = ensure_autoselfcheck_once(strict=None)
            st.session_state["_autoselfcheck_v1_done"] = True
            st.session_state["_autoselfcheck_v1_ok"] = bool(getattr(_r, "ok", False))

            # РћС‚С‡С‘С‚ СЂСЏРґРѕРј СЃ Р»РѕРіР°РјРё (РІС…РѕРґРёС‚ РІ РґРёР°РіРЅРѕСЃС‚РёС‡РµСЃРєРёР№ РїР°РєРµС‚)
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

            # РЎРѕР±С‹С‚РёРµ РІ JSONL Р»РѕРі
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
        # best-effort: РЅРё РїСЂРё РєР°РєРёС… РѕР±СЃС‚РѕСЏС‚РµР»СЊСЃС‚РІР°С… РЅРµ Р»РѕРјР°РµРј UI РёР·-Р·Р° СЃР°РјРѕРїСЂРѕРІРµСЂРєРё
        pass

finally:
    if _startup_spinner_cm is not None:
        try:
            _startup_spinner_cm.__exit__(None, None, None)
        except Exception:
            pass
    if _startup_status is not None:
        try:
            _startup_status.update(label="РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Р·Р°РІРµСЂС€РµРЅР°", state="complete", expanded=False)
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
# Р­С‚Рѕ Р·Р°РєСЂС‹РІР°РµС‚ С‚СЂРµР±РѕРІР°РЅРёРµ: "РќСѓР¶РµРЅ mapping JSON - СЃРґРµР»Р°Р№ СЂР°Р±РѕС‡РёР№ Рё РіСЂСѓР·Рё РїРѕ РґРµС„РѕР»С‚Сѓ".
if "svg_mapping_text" not in st.session_state or not str(st.session_state.get("svg_mapping_text", "")).strip():
    try:
        st.session_state["svg_mapping_text"] = DEFAULT_SVG_MAPPING_PATH.read_text(encoding="utf-8")
        st.session_state["svg_mapping_source"] = str(DEFAULT_SVG_MAPPING_PATH)
        log_event("svg_mapping_loaded_default", path=str(DEFAULT_SVG_MAPPING_PATH))
    except Exception as e:
        # Р•СЃР»Рё С„Р°Р№Р» РЅРµРґРѕСЃС‚СѓРїРµРЅ, РїРѕРґСЃС‚Р°РІР»СЏРµРј РјРёРЅРёРјР°Р»СЊРЅС‹Р№ СЂР°Р±РѕС‡РёР№ С€Р°Р±Р»РѕРЅ.
        st.session_state["svg_mapping_text"] = json.dumps(
            {"version": 2, "viewBox": "0 0 1920 1080", "edges": {}, "nodes": {}},
            ensure_ascii=False,
            indent=2,
        )
        st.session_state["svg_mapping_source"] = "generated_template"
        log_event("svg_mapping_default_failed", error=repr(e))

# -------------------------------
# UI: РєРѕРјРїР°РєС‚РЅС‹Р№ РјР°РєРµС‚ (С‡С‚РѕР±С‹ РєРѕСЂРѕС‚РєРёРµ СЃРµР»РµРєС‚РѕСЂС‹/СЃРїРёСЃРєРё РЅРµ СЂР°СЃС‚СЏРіРёРІР°Р»РёСЃСЊ РЅР° РІРµСЃСЊ СЌРєСЂР°РЅ)
# -------------------------------
with st.sidebar:
    st.markdown("## UI")
    ui_compact = st.checkbox(
        "РЎР¶Р°С‚С‹Р№ РјР°РєРµС‚ (РЅРµ СЂР°СЃС‚СЏРіРёРІР°С‚СЊ СЃРїРёСЃРєРё)",
        value=st.session_state.get("ui_compact", True),
        help="РћРіСЂР°РЅРёС‡РёРІР°РµС‚ РјР°РєСЃРёРјР°Р»СЊРЅСѓСЋ С€РёСЂРёРЅСѓ РєРѕРЅС‚РµРЅС‚Р°. РџРѕР»РµР·РЅРѕ РЅР° С€РёСЂРѕРєРёС… РјРѕРЅРёС‚РѕСЂР°С…: РєРѕСЂРѕС‚РєРёРµ СЃРїРёСЃРєРё/СЃРµР»РµРєС‚РѕСЂС‹ РЅРµ Р±СѓРґСѓС‚ РЅР° РІСЃСЋ С€РёСЂРёРЅСѓ.",
    )
    st.session_state["ui_compact"] = ui_compact


    st.checkbox(
        "РџСЂРё Play (fallback) СЃРєСЂС‹РІР°С‚СЊ Plotly-РіСЂР°С„РёРєРё",
        value=st.session_state.get("skip_heavy_on_play", True),
        key="skip_heavy_on_play",
        help="Fallback-Р°РЅРёРјР°С†РёСЏ РёСЃРїРѕР»СЊР·СѓРµС‚ Р°РІС‚РѕРѕР±РЅРѕРІР»РµРЅРёРµ (РєР°Р¶РґС‹Р№ РєР°РґСЂ = rerun РІСЃРµРіРѕ РїСЂРёР»РѕР¶РµРЅРёСЏ). "
             "Р§С‚РѕР±С‹ Play РЅРµ РїСЂРµРІСЂР°С‰Р°Р»СЃСЏ РІ 'Р±РµСЃРєРѕРЅРµС‡РЅС‹Р№ СЂР°СЃС‡С‘С‚', РјС‹ РјРѕР¶РµРј РІСЂРµРјРµРЅРЅРѕ СЃРєСЂС‹РІР°С‚СЊ С‚СЏР¶С‘Р»С‹Рµ Plotly-РіСЂР°С„РёРєРё. "
             "РџРѕСЃС‚Р°РІСЊ РЅР° РїР°СѓР·Сѓ вЂ” РіСЂР°С„РёРєРё РІРµСЂРЅСѓС‚СЃСЏ.",
    )

    # --- v6_29: rel0 plots toggle ---
    st.session_state.setdefault("use_rel0_for_plots", True)
    st.checkbox(
        "Р“СЂР°С„РёРєРё: РїРѕРєР°Р·С‹РІР°С‚СЊ СЃРјРµС‰РµРЅРёСЏ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РЅСѓР»РµРІРѕР№ РґРѕСЂРѕРіРё (rel0)",
        key="use_rel0_for_plots",
        help=(
            "Р•СЃР»Рё РІ РґР°РЅРЅС‹С… РµСЃС‚СЊ РєРѕР»РѕРЅРєРё *_rel0_m (СЃРјРµС‰РµРЅРёСЏ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РЅСѓР»РµРІРѕР№ РґРѕСЂРѕРіРё), "
            "РіСЂР°С„РёРєРё Р±СѓРґСѓС‚ СЃС‚СЂРѕРёС‚СЊСЃСЏ РїРѕ РЅРёРј, РЅРѕ СЃ РїСЂРёРІС‹С‡РЅС‹РјРё РЅР°Р·РІР°РЅРёСЏРјРё РІ Р»РµРіРµРЅРґРµ. "
            "Р’С‹РєР»СЋС‡Рё, РµСЃР»Рё С…РѕС‡РµС€СЊ РІРёРґРµС‚СЊ Р°Р±СЃРѕР»СЋС‚РЅС‹Рµ РєРѕРѕСЂРґРёРЅР°С‚С‹."
        ),
    )

if st.session_state.get("ui_compact", True):
    st.markdown(
        """<style>
        .block-container { max-width: 1280px; padding-top: 1.0rem; }
        </style>""",
        unsafe_allow_html=True,
    )

# РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ: РєР»РёРє РїРѕ SVG СЃС…РµРјРµ в†’ РІС‹Р±РѕСЂ РІРµС‚РѕРє/СѓР·Р»РѕРІ РІ РіСЂР°С„РёРєР°С…
consume_svg_pick_event()

# РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ: РєР»РёРє РїРѕ РјРµС…Р°РЅРёРєРµ в†’ РІС‹Р±РѕСЂ СѓРіР»РѕРІ РґР»СЏ РіСЂР°С„РёРєРѕРІ/РїРѕРґСЃРІРµС‚РєРё
consume_mech_pick_event()

# РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ: РєР»РёРє/РІС‹РґРµР»РµРЅРёРµ РЅР° РіСЂР°С„РёРєР°С… Plotly в†’ РїРѕРґСЃРІРµС‚РєР°/РІС‹Р±РѕСЂ РЅР° SVG СЃС…РµРјРµ
consume_plotly_pick_events()

# Shared timeline (playhead) updates
consume_playhead_event()

st.title("РџРЅРµРІРјРѕРїРѕРґРІРµСЃРєР°: СЂР°СЃС‡С‘С‚ Рё РѕРїС‚РёРјРёР·Р°С†РёСЏ")

# Truth panel slot (filled later when hashes/results are available)
truth_slot = st.container()

# --- UI_CSS_LABEL_WRAP: Р±Р°Р·РѕРІР°СЏ Р·Р°С‰РёС‚Р° РѕС‚ РЅР°Р»РµР·Р°РЅРёСЏ РїРѕРґРїРёСЃРµР№/Р»РµР№Р±Р»РѕРІ ---
st.markdown(
    """
    <style>
    /* Р Р°Р·СЂРµС€Р°РµРј РїРµСЂРµРЅРѕСЃ СЃС‚СЂРѕРє РІ Р»РµР№Р±Р»Р°С… РІРёРґР¶РµС‚РѕРІ */
    div[data-testid="stWidgetLabel"] > label {
        white-space: normal !important;
        line-height: 1.15;
    }

    /* РџРѕРґСЃРєР°Р·РєРё: РѕРіСЂР°РЅРёС‡РёРј С€РёСЂРёРЅСѓ, С‡С‚РѕР±С‹ РЅРµ СЂР°СЃРїРѕР»Р·Р°Р»РёСЃСЊ */
    div[data-testid="stTooltipContent"] {
        max-width: 520px;
    }

    /* Р§СѓС‚СЊ РјРµРЅСЊС€Рµ РІРµСЂС‚РёРєР°Р»СЊРЅС‹С… Р·Р°Р·РѕСЂРѕРІ РІ СЃР°Р№РґР±Р°СЂРµ */
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.4rem;
    }

    /* РљСѓСЂСЃРѕСЂ: РґРµР»Р°РµРј РєР»РёРєР°Р±РµР»СЊРЅС‹Рµ СЌР»РµРјРµРЅС‚С‹ РѕС‡РµРІРёРґРЅС‹РјРё (РІ С‚.С‡. selectbox, expander) */
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
    st.header("РЎРѕС…СЂР°РЅРµРЅРёРµ РІРІРѕРґР°")
    st.caption(
        "Р—РґРµСЃСЊ РІРєР»СЋС‡Р°РµС‚СЃСЏ Р°РІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёРµ Р·РЅР°С‡РµРЅРёР№, С‡С‚РѕР±С‹ РѕРЅРё РЅРµ РёСЃС‡РµР·Р°Р»Рё РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё СЃС‚СЂР°РЅРёС†С‹ "
        "РёР»Рё РїРѕРІС‚РѕСЂРЅРѕРј Р·Р°РїСѓСЃРєРµ РїСЂРёР»РѕР¶РµРЅРёСЏ."
    )

    # Р’РєР»СЋС‡РµРЅРѕ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ. РњРѕР¶РЅРѕ РѕС‚РєР»СЋС‡РёС‚СЊ, РµСЃР»Рё РЅСѓР¶РµРЅ В«С‡РёСЃС‚С‹Р№В» Р·Р°РїСѓСЃРє.
    st.toggle(
        "РђРІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёРµ (СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ)",
        value=bool(st.session_state.get("ui_autosave_enabled", True)),
        key="ui_autosave_enabled",
        help=(
            "Р•СЃР»Рё РІРєР»СЋС‡РµРЅРѕ, РїСЂРёР»РѕР¶РµРЅРёРµ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃРѕС…СЂР°РЅСЏРµС‚ РІРІРµРґС‘РЅРЅС‹Рµ Р·РЅР°С‡РµРЅРёСЏ (С‚Р°Р±Р»РёС†С‹ РїР°СЂР°РјРµС‚СЂРѕРІ/С‚РµСЃС‚РѕРІ Рё РєР»СЋС‡РµРІС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё) "
            "РІ РЅРµР±РѕР»СЊС€РѕР№ JSON-С„Р°Р№Р» РЅР° РґРёСЃРєРµ."
        ),
    )

    try:
        from pneumo_solver_ui.ui_persistence import pick_state_dir, autosave_path

        _sd = pick_state_dir()
        if _sd is None:
            st.warning("РџР°РїРєР° РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РЅРµ РЅР°Р№РґРµРЅР° РёР»Рё РЅРµРґРѕСЃС‚СѓРїРЅР° РґР»СЏ Р·Р°РїРёСЃРё. РђРІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёРµ РѕС‚РєР»СЋС‡РµРЅРѕ.")
        else:
            _ap = autosave_path(_sd)
            st.caption(f"Р¤Р°Р№Р» Р°РІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёСЏ: `{_ap}`")

            # СЃС‚Р°С‚СѓСЃ Р·Р°РіСЂСѓР·РєРё/СЃРѕС…СЂР°РЅРµРЅРёСЏ
            if st.session_state.get("ui_autosave_loaded"):
                st.success("РќР°СЃС‚СЂРѕР№РєРё Р·Р°РіСЂСѓР¶РµРЅС‹ РёР· Р°РІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёСЏ.")
            if st.session_state.get("ui_autosave_load_error"):
                st.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ Р°РІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёРµ: {st.session_state.get('ui_autosave_load_error')}")

            if st.session_state.get("ui_autosave_last_saved"):
                import datetime as _dt
                _ts = float(st.session_state.get("ui_autosave_last_saved") or 0.0)
                if _ts > 0:
                    st.caption("РџРѕСЃР»РµРґРЅРµРµ Р°РІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёРµ: " + _dt.datetime.fromtimestamp(_ts).strftime("%Y-%m-%d %H:%M:%S"))

            c_save, c_reset = st.columns(2)
            with c_save:
                if st.button("РЎРѕС…СЂР°РЅРёС‚СЊ СЃРµР№С‡Р°СЃ", key="ui_save_now", width="stretch"):
                    try:
                        from pneumo_solver_ui.ui_persistence import build_state_dict, save_autosave
                        ok, info = save_autosave(_sd, build_state_dict(st.session_state))
                        if ok:
                            st.session_state["ui_autosave_last_saved"] = __import__("time").time()
                            st.success("РЎРѕС…СЂР°РЅРµРЅРѕ.")
                        else:
                            st.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ: {info}")
                    except Exception as _e:
                        st.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ: {_e}")
            with c_reset:
                if st.button("РЎР±СЂРѕСЃРёС‚СЊ РІРІРѕРґ", key="ui_reset_input_btn", width="stretch"):
                    st.session_state["ui_reset_input_confirm"] = True

            if st.session_state.get("ui_reset_input_confirm"):
                st.warning("РЎР±СЂРѕСЃ СѓРґР°Р»РёС‚ РІРІРµРґС‘РЅРЅС‹Рµ С‚Р°Р±Р»РёС†С‹ Рё СЃРѕС…СЂР°РЅРµРЅРёРµ. РћС‚РјРµРЅРёС‚СЊ РЅРµР»СЊР·СЏ.")
                c_yes, c_no = st.columns(2)
                with c_yes:
                    if st.button("Р”Р°, СЃР±СЂРѕСЃРёС‚СЊ", key="ui_reset_input_yes", width="stretch"):
                        # РѕС‡РёСЃС‚РєР° РєР»СЋС‡РµРІС‹С… UI-РґР°РЅРЅС‹С…
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
                        # СѓРґР°Р»РёС‚СЊ С„Р°Р№Р» Р°РІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёСЏ
                        try:
                            if _ap.exists():
                                _ap.unlink()
                        except Exception:
                            pass
                        st.session_state["ui_reset_input_confirm"] = False
                        st.success("РЎР±СЂРѕС€РµРЅРѕ. РџРµСЂРµР·Р°РіСЂСѓР·РєР°вЂ¦")
                        st.rerun()
                with c_no:
                    if st.button("РћС‚РјРµРЅР°", key="ui_reset_input_no", width="stretch"):
                        st.session_state["ui_reset_input_confirm"] = False
    except Exception:
        # СЌС‚Р° РїР°РЅРµР»СЊ РЅРµ РґРѕР»Р¶РЅР° Р»РѕРјР°С‚СЊ UI
        pass

    st.header("Р¤Р°Р№Р»С‹ РїСЂРѕРµРєС‚Р°")
    model_path = st.text_input(
        "Р¤Р°Р№Р» РјРѕРґРµР»Рё (py)",
        value=str(_suggest_default_model_path(HERE)),
        key="ui_model_path",
        help="PythonвЂ‘С„Р°Р№Р», РіРґРµ РѕРїРёСЃР°РЅР° РјРѕРґРµР»СЊ РїРѕРґРІРµСЃРєРё/РїРЅРµРІРјРѕСЃРёСЃС‚РµРјС‹. РћР±С‹С‡РЅРѕ РјРµРЅСЏС‚СЊ РЅРµ РЅСѓР¶РЅРѕ.",
    )
    worker_path = st.text_input(
        "Р¤Р°Р№Р» РѕРїС‚РёРјРёР·Р°С‚РѕСЂР° (py)",
        value=str(canonical_worker_path(HERE)),
        key="ui_worker_path",
        help="PythonвЂ‘С„Р°Р№Р», РєРѕС‚РѕСЂС‹Р№ Р·Р°РїСѓСЃРєР°РµС‚ РѕРїС‚РёРјРёР·Р°С†РёСЋ. РћР±С‹С‡РЅРѕ РјРµРЅСЏС‚СЊ РЅРµ РЅСѓР¶РЅРѕ.",
    )

    st.divider()
    st.header("РќР°СЃС‚СЂРѕР№РєРё С‚РµСЃС‚-РЅР°Р±РѕСЂР°")
    st.caption("РЁР°Рі dt, РґР»РёС‚РµР»СЊРЅРѕСЃС‚СЊ t_end Рё РјРѕРјРµРЅС‚ СЃС‚СѓРїРµРЅСЊРєРё t_step Р·Р°РґР°СЋС‚СЃСЏ РІ С‚Р°Р±Р»РёС†Рµ С‚РµСЃС‚-РЅР°Р±РѕСЂР° (РІ РѕСЃРЅРѕРІРЅРѕР№ С‡Р°СЃС‚Рё СЌРєСЂР°РЅР°). Р­С‚Рѕ СЃРґРµР»Р°РЅРѕ СЃРїРµС†РёР°Р»СЊРЅРѕ, С‡С‚РѕР±С‹ РЅРµ Р±С‹Р»Рѕ РґРІРѕР№РЅРѕРіРѕ РІРІРѕРґР° РІСЂРµРјРµРЅРё С‚РµСЃС‚РѕРІ.")

    st.header("РћРїС‚РёРјРёР·Р°С†РёСЏ")
    st.caption(
        "Р—РґРµСЃСЊ Р·Р°РґР°СЋС‚СЃСЏ РїР°СЂР°РјРµС‚СЂС‹ Р·Р°РїСѓСЃРєР° РѕРїС‚РёРјРёР·Р°С‚РѕСЂР° (РІСЂРµРјСЏ, РїР°СЂР°Р»Р»РµР»СЊРЅРѕСЃС‚СЊ, СЃРѕС…СЂР°РЅРµРЅРёРµ РїСЂРѕРіСЂРµСЃСЃР°). "
        "Р”РёР°РїР°Р·РѕРЅС‹ РѕРїС‚РёРјРёР·РёСЂСѓРµРјС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ Р·Р°РґР°СЋС‚СЃСЏ РІ С‚Р°Р±Р»РёС†Рµ В«РСЃС…РѕРґРЅС‹Рµ РґР°РЅРЅС‹РµВ»."
    )

    # --- РњРёРіСЂР°С†РёСЏ РєР»СЋС‡РµР№ (С‡С‚РѕР±С‹ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёСЏС… РЅРµ С‚РµСЂСЏС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ)
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

    # Р“Р»Р°РІРЅР°СЏ Р±РѕР»СЊС€Рµ РЅРµ РґРµСЂР¶РёС‚ РІС‚РѕСЂРѕР№ optimization control plane.
    # Р—РґРµСЃСЊ РѕСЃС‚Р°С‘С‚СЃСЏ С‚РѕР»СЊРєРѕ РёРЅР¶РµРЅРµСЂРЅС‹Р№ gateway + read-only snapshot,
    # Р° Р·Р°РїСѓСЃРє/stop/resume/monitoring Р¶РёРІСѓС‚ РЅР° РѕС‚РґРµР»СЊРЅРѕР№ СЃС‚СЂР°РЅРёС†Рµ.
    auto_refresh = False
    refresh_sec = float(st.session_state.get("ui_refresh_sec", 1.0) or 1.0)

    st.subheader("РћРїС‚РёРјРёР·Р°С†РёСЏ вЂ” РѕС‚РґРµР»СЊРЅР°СЏ СЃС‚СЂР°РЅРёС†Р°")
    st.caption(
        "РќР° РіР»Р°РІРЅРѕР№ РѕСЃС‚Р°СЋС‚СЃСЏ search-space contract Рё РІС…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ: С‚Р°Р±Р»РёС†Р° РїР°СЂР°РјРµС‚СЂРѕРІ, СЂРµР¶РёРјС‹ Рё suite. "
        "Р—Р°РїСѓСЃРє, stop/resume, monitoring Рё РІСЃРµ РЅР°СЃС‚СЂРѕР№РєРё РѕРїС‚РёРјРёР·Р°С†РёРё СЃРѕР±СЂР°РЅС‹ РЅР° РѕС‚РґРµР»СЊРЅРѕР№ СЃС‚СЂР°РЅРёС†Рµ В«РћРїС‚РёРјРёР·Р°С†РёСЏВ»."
    )

    _render_home_opt_config_snapshot(compact=True)
    _render_home_opt_last_pointer_summary(compact=True)

    st.caption(
        "Р“СЂР°РЅРёС†С‹ РїР°СЂР°РјРµС‚СЂРѕРІ Рё test-suite Р·Р°РґР°СЋС‚СЃСЏ РЅР° РіР»Р°РІРЅРѕР№ РІ С‚РµРєСѓС‰РёС… СЂР°Р·РґРµР»Р°С…; Р°Р»РіРѕСЂРёС‚Рј, backend, "
        "РѕСЃС‚Р°РЅРѕРІРєР° Рё РїСЂРѕСЃРјРѕС‚СЂ live-СЃС‚Р°С‚СѓСЃР° вЂ” РЅР° РѕС‚РґРµР»СЊРЅРѕР№ СЃС‚СЂР°РЅРёС†Рµ РѕРїС‚РёРјРёР·Р°С†РёРё."
    )

    _opt_gateway_nav(
        "pneumo_solver_ui/pages/30_Optimization.py",
        "рџЋЇ РћС‚РєСЂС‹С‚СЊ СЃС‚СЂР°РЅРёС†Сѓ РѕРїС‚РёРјРёР·Р°С†РёРё",
        key="home_opt_gateway_sidebar_go_optimization",
        help_text="Р’СЃРµ СЂСѓС‡РєРё Р·Р°РїСѓСЃРєР°, stop/resume, РјРѕРЅРёС‚РѕСЂРёРЅРі Рё С‚РµРєСѓС‰РёР№ Р»РѕРі РѕРїС‚РёРјРёР·Р°С†РёРё.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/20_DistributedOptimization.py",
        "рџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ РѕРїС‚РёРјРёР·Р°С†РёРё / ExperimentDB",
        key="home_opt_gateway_sidebar_go_results",
        help_text="РџСЂРѕСЃРјРѕС‚СЂ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ Рё distributed ExperimentDB.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/31_OptDatabase.py",
        "рџ—„пёЏ Р‘Р°Р·Р° РѕРїС‚РёРјРёР·Р°С†РёР№",
        key="home_opt_gateway_sidebar_go_db",
        help_text="РћС‚РґРµР»СЊРЅР°СЏ СЃС‚СЂР°РЅРёС†Р° Р±Р°Р·С‹ РѕРїС‚РёРјРёР·Р°С†РёР№.",
    )

    # Legacy home control plane retained only as dormant source surface
    # for regression/source guards. Live launch path = dedicated Optimization page.
    if False:
            # --- РћСЃРЅРѕРІРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё (РёСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ РїРѕС‡С‚Рё РІСЃРµРіРґР°)
            minutes = st.number_input(
                "Р›РёРјРёС‚ РІСЂРµРјРµРЅРё (РјРёРЅ)",
                min_value=0.5,
                max_value=10080.0,
                value=float(st.session_state.get("ui_opt_minutes", DIAGNOSTIC_OPT_MINUTES_DEFAULT)),
                step=1.0,
                key="ui_opt_minutes",
                help="РћРіСЂР°РЅРёС‡РµРЅРёРµ РїРѕ РІСЂРµРјРµРЅРё СЂР°Р±РѕС‚С‹ РѕРїС‚РёРјРёР·Р°С‚РѕСЂР°. РџРѕСЃР»Рµ Р»РёРјРёС‚Р° РїСЂРѕС†РµСЃСЃ Р·Р°РІРµСЂС€РёС‚СЃСЏ РєРѕСЂСЂРµРєС‚РЅРѕ Рё СЃРѕС…СЂР°РЅРёС‚ РїСЂРѕРіСЂРµСЃСЃ.",
            )

            # РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ СЃС‚Р°СЂР°РµРјСЃСЏ Р·Р°РґРµР№СЃС‚РІРѕРІР°С‚СЊ РІСЃРµ РґРѕСЃС‚СѓРїРЅС‹Рµ СЏРґСЂР° CPU.
            # max_value РґРµР»Р°РµРј РґРёРЅР°РјРёС‡РµСЃРєРёРј (РЅРѕ СЃ СЂР°Р·СѓРјРЅС‹Рј РѕРіСЂР°РЅРёС‡РµРЅРёРµРј, С‡С‚РѕР±С‹ РЅРµ СѓР»РµС‚РµС‚СЊ РІ СЃРѕС‚РЅРё РїСЂРѕС†РµСЃСЃРѕРІ РЅР° Р±РѕР»СЊС€РёС… СЃРµСЂРІРµСЂР°С…).
            _cpu_n = int(os.cpu_count() or 4)
            # РќР° Windows Сѓ ProcessPoolExecutor РµСЃС‚СЊ Р»РёРјРёС‚ max_workers<=61.
            # РЎРј. РґРѕРєСѓРјРµРЅС‚Р°С†РёСЋ Python: concurrent.futures.ProcessPoolExecutor.
            _platform_cap = 61 if sys.platform.startswith("win") else 128
            _jobs_cap = int(max(1, min(_platform_cap, _cpu_n)))
            _jobs_default = int(diagnostics_jobs_default(_cpu_n, platform_name=sys.platform))

            jobs = st.number_input(
                "РџР°СЂР°Р»Р»РµР»СЊРЅРѕСЃС‚СЊ (jobs)",
                min_value=1,
                max_value=int(_jobs_cap),
                value=int(st.session_state.get("ui_jobs", _jobs_default)),
                step=1,
                key="ui_jobs",
                help="РЎРєРѕР»СЊРєРѕ РїСЂРѕС†РµСЃСЃРѕРІ РїР°СЂР°Р»Р»РµР»СЊРЅРѕ СЃС‡РёС‚Р°С‚СЊ РєР°РЅРґРёРґР°С‚РѕРІ. РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ = РІСЃРµ СЏРґСЂР° CPU. Р‘РѕР»СЊС€Рµ вЂ” Р±С‹СЃС‚СЂРµРµ, РЅРѕ РІС‹С€Рµ РЅР°РіСЂСѓР·РєР° РЅР° CPU/RAM.",
            )

            st.divider()
            st.subheader("Р РµР·СѓР»СЊС‚Р°С‚С‹")

            run_name = st.text_input(
                "РРјСЏ РїСЂРѕРіРѕРЅР°",
                value=str(st.session_state.get("opt_run_name", "main")),
                key="opt_run_name",
                help=(
                    "Р­С‚Рѕ РёРјСЏ РїР°РїРєРё РІ workspace/opt_runs. РСЃРїРѕР»СЊР·СѓР№С‚Рµ СЂР°Р·РЅС‹Рµ РёРјРµРЅР° РґР»СЏ СЂР°Р·РЅС‹С… СЃРµСЂРёР№ СЌРєСЃРїРµСЂРёРјРµРЅС‚РѕРІ "
                    "(РЅР°РїСЂРёРјРµСЂ: 'main', 'winter', 'camozzi_v1')."
                ),
            )

            out_prefix = st.text_input(
                "РРјСЏ CSV (РїСЂРµС„РёРєСЃ)",
                value=str(st.session_state.get("ui_out_prefix", "results_opt")),
                key="ui_out_prefix",
                help="РРјСЏ С„Р°Р№Р»Р° СЂРµР·СѓР»СЊС‚Р°С‚Р° РІРЅСѓС‚СЂРё РїР°РїРєРё РїСЂРѕРіРѕРЅР°. РќР°РїСЂРёРјРµСЂ: results_opt.csv РёР»Рё results_opt_all.csv.",
            )

            st.divider()
            st.subheader("Р РµР¶РёРј Р·Р°РїСѓСЃРєР°")

            opt_use_staged = st.checkbox(
                "Р РµР¶РёРј РїРѕ СЃС‚Р°РґРёСЏРј (StageRunner) вЂ” СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ",
                value=bool(st.session_state.get("opt_use_staged", DIAGNOSTIC_USE_STAGED_OPT)),
                key="opt_use_staged",
                help=(
                    "StageRunner СЃРЅР°С‡Р°Р»Р° РїСЂРѕРіРѕРЅСЏРµС‚ РґРµС€С‘РІС‹Рµ С‚РµСЃС‚С‹ Рё РѕС‚СЃРµРёРІР°РµС‚ РїР»РѕС…РёРµ РєР°РЅРґРёРґР°С‚С‹, "
                    "Р·Р°С‚РµРј РґРѕР±Р°РІР»СЏРµС‚ РґРѕСЂРѕРіРёРµ С‚РµСЃС‚С‹. РћР±С‹С‡РЅРѕ СЌС‚Рѕ Р±С‹СЃС‚СЂРµРµ Рё СѓСЃС‚РѕР№С‡РёРІРµРµ, С‡РµРј В«РІСЃС‘ СЃСЂР°Р·СѓВ». "
                    "РќСѓРјРµСЂР°С†РёСЏ СЃС‚Р°РґРёР№ 0-based: РїРµСЂРІР°СЏ СЃС‚Р°РґРёСЏ = 0."
                ),
            )
            # Р°Р»РёР°СЃ РґР»СЏ СЃС‚Р°СЂС‹С… СЃРѕС…СЂР°РЅРµРЅРёР№/РєРѕРґР° (РЅРµ СѓРґР°Р»СЏРµРј СЂРµР·РєРѕ)
            st.session_state["use_staged_opt"] = bool(opt_use_staged)

            opt_autoupdate_baseline = st.checkbox(
                "РђРІС‚РѕвЂ‘РѕР±РЅРѕРІР»СЏС‚СЊ baseline_best.json",
                value=bool(st.session_state.get("opt_autoupdate_baseline", True)),
                key="opt_autoupdate_baseline",
                help=(
                    "Р•СЃР»Рё РЅР°Р№РґРµРЅ РєР°РЅРґРёРґР°С‚ Р»СѓС‡С€Рµ С‚РµРєСѓС‰РµРіРѕ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°, StageRunner Р·Р°РїРёС€РµС‚ РµРіРѕ РІ "
                    "workspace/baselines/baseline_best.json. Р­С‚РѕС‚ С„Р°Р№Р» РјРѕР¶РЅРѕ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ РєР°Рє РЅРѕРІС‹Р№ СЃС‚Р°СЂС‚."
                ),
            )
            st.session_state["autoupdate_baseline"] = bool(opt_autoupdate_baseline)

            # --- Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё (РїСЂСЏС‡РµРј РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ)
            with st.expander("Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё Р·Р°РїСѓСЃРєР° (СЂРµРґРєРѕ РЅСѓР¶РЅРѕ)", expanded=True):
                seed_candidates = st.number_input(
                    "Seed РєР°РЅРґРёРґР°С‚РѕРІ",
                    min_value=0,
                    max_value=2_147_483_647,
                    value=int(st.session_state.get("ui_seed_candidates", DIAGNOSTIC_SEED_CANDIDATES)),
                    step=1,
                    key="ui_seed_candidates",
                    help="Р’Р»РёСЏРµС‚ С‚РѕР»СЊРєРѕ РЅР° РіРµРЅРµСЂР°С†РёСЋ РЅР°Р±РѕСЂР° РєР°РЅРґРёРґР°С‚РѕРІ (РєРѕРјР±РёРЅР°С†РёР№ РїР°СЂР°РјРµС‚СЂРѕРІ) РІ РѕРїС‚РёРјРёР·Р°С‚РѕСЂРµ.",
                )
                seed_conditions = st.number_input(
                    "Seed СѓСЃР»РѕРІРёР№",
                    min_value=0,
                    max_value=2_147_483_647,
                    value=int(st.session_state.get("ui_seed_conditions", DIAGNOSTIC_SEED_CONDITIONS)),
                    step=1,
                    key="ui_seed_conditions",
                    help="Р’Р»РёСЏРµС‚ РЅР° СЃС‚РѕС…Р°СЃС‚РёС‡РµСЃРєРёРµ СѓСЃР»РѕРІРёСЏ РІ СЃС‚СЂРµСЃСЃвЂ‘С‚РµСЃС‚Р°С… (РµСЃР»Рё РѕРЅРё РІРєР»СЋС‡РµРЅС‹).",
                )
                flush_every = st.number_input(
                    "РЎРѕС…СЂР°РЅСЏС‚СЊ РєР°Р¶РґС‹Рµ N РєР°РЅРґРёРґР°С‚РѕРІ",
                    min_value=1,
                    max_value=200,
                    value=int(st.session_state.get("ui_flush_every", 20)),
                    step=1,
                    key="ui_flush_every",
                    help="РљР°Рє С‡Р°СЃС‚Рѕ СЃР±СЂР°СЃС‹РІР°С‚СЊ СЃС‚СЂРѕРєРё СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РІ CSV РЅР° РґРёСЃРє. РњРµРЅСЊС€Рµ вЂ” РЅР°РґС‘Р¶РЅРµРµ, РЅРѕ Р±РѕР»СЊС€Рµ IO. (РќР° Р·Р°РіСЂСѓР·РєСѓ CPU РЅРµ РІР»РёСЏРµС‚.)",
                )
                progress_every_sec = st.number_input(
                    "РћР±РЅРѕРІР»СЏС‚СЊ progress.json РєР°Р¶РґС‹Рµ О”t (СЃ)",
                    min_value=0.2,
                    max_value=10.0,
                    value=float(st.session_state.get("ui_progress_every_sec", 1.0)),
                    step=0.2,
                    key="ui_progress_every_sec",
                    help="Р§Р°СЃС‚РѕС‚Р° Р·Р°РїРёСЃРё С„Р°Р№Р»Р° РїСЂРѕРіСЂРµСЃСЃР° РёР· С„РѕРЅРѕРІРѕРіРѕ РїСЂРѕС†РµСЃСЃР° РѕРїС‚РёРјРёР·Р°С†РёРё.",
                )

                st.markdown("вЂ”")
                auto_refresh = st.checkbox(
                    "РђРІС‚РѕРѕР±РЅРѕРІР»РµРЅРёРµ РїСЂРѕРіСЂРµСЃСЃР° (UI)",
                    value=bool(st.session_state.get("ui_auto_refresh", True)),
                    key="ui_auto_refresh",
                    help="РџРµСЂРёРѕРґРёС‡РµСЃРєРёР№ auto-rerun СЃС‚СЂР°РЅРёС†С‹, С‡С‚РѕР±С‹ РїСЂРѕРіСЂРµСЃСЃ РѕР±РЅРѕРІР»СЏР»СЃСЏ Р±РµР· РєР»РёРєРѕРІ.",
                )
                refresh_sec = st.number_input(
                    "РРЅС‚РµСЂРІР°Р» Р°РІС‚РѕРѕР±РЅРѕРІР»РµРЅРёСЏ (СЃ)",
                    min_value=0.2,
                    max_value=10.0,
                    value=float(st.session_state.get("ui_refresh_sec", 1.0)),
                    step=0.2,
                    key="ui_refresh_sec",
                    help="РљР°Рє С‡Р°СЃС‚Рѕ UI РїРµСЂРµС‡РёС‚С‹РІР°РµС‚ progress.json Рё РїРµСЂРµСЂРёСЃРѕРІС‹РІР°РµС‚ СЃС‚Р°С‚СѓСЃ.",
                )

            # --- StageRunner advanced (РїРѕРєР°Р·С‹РІР°РµРј С‚РѕР»СЊРєРѕ РµСЃР»Рё РІС‹Р±СЂР°РЅ StageRunner)
            if bool(opt_use_staged):
                with st.expander("StageRunner: СѓСЃРєРѕСЂРµРЅРёРµ РїРѕРёСЃРєР° (РѕР±С‹С‡РЅРѕ РЅРµ С‚СЂРѕРіР°С‚СЊ)", expanded=True):
                    warmstart_mode = st.selectbox(
                        "WarmвЂ‘start СЂРµР¶РёРј",
                        options=["surrogate", "archive", "none"],
                        index=["surrogate", "archive", "none"].index(st.session_state.get("warmstart_mode", DIAGNOSTIC_WARMSTART_MODE)),
                        key="warmstart_mode",
                        help=(
                            "surrogate: РѕР±СѓС‡Р°РµС‚ Р±С‹СЃС‚СЂС‹Р№ surrogate РЅР° РёСЃС‚РѕСЂРёРё Рё РІС‹Р±РёСЂР°РµС‚ СЌР»РёС‚Сѓ РїРѕ РїСЂРµРґСЃРєР°Р·Р°РЅРёСЋ; "
                            "archive: Р±РµСЂС‘С‚ С‚РѕРївЂ‘N РёР· РіР»РѕР±Р°Р»СЊРЅРѕРіРѕ Р°СЂС…РёРІР°; "
                            "none: Р±РµР· warmвЂ‘start."
                        ),
                    )

                    surrogate_samples = st.number_input(
                        "Surrogate samples",
                        min_value=500,
                        max_value=50000,
                        value=int(st.session_state.get("surrogate_samples", DIAGNOSTIC_SURROGATE_SAMPLES)),
                        step=500,
                        key="surrogate_samples",
                        help="РЎРєРѕР»СЊРєРѕ СЃР»СѓС‡Р°Р№РЅС‹С… С‚РѕС‡РµРє СЂР°РЅР¶РёСЂРѕРІР°С‚СЊ РІ surrogate warmвЂ‘start (Р±РѕР»СЊС€Рµ = С‚РѕС‡РЅРµРµ, РЅРѕ РјРµРґР»РµРЅРЅРµРµ).",
                    )

                    surrogate_top_k = st.number_input(
                        "Surrogate topвЂ‘k",
                        min_value=8,
                        max_value=512,
                        value=int(st.session_state.get("surrogate_top_k", DIAGNOSTIC_SURROGATE_TOP_K)),
                        step=8,
                        key="surrogate_top_k",
                        help="Р Р°Р·РјРµСЂ СЌР»РёС‚С‹ РґР»СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё СЂР°СЃРїСЂРµРґРµР»РµРЅРёСЏ РїРѕРёСЃРєР°.",
                    )

                    stop_pen_stage1 = st.number_input(
                        "EarlyвЂ‘stop С€С‚СЂР°С„ (stage1)",
                        min_value=0.0,
                        max_value=1e9,
                        value=float(st.session_state.get("stop_pen_stage1", 25.0)),
                        step=1.0,
                        key="stop_pen_stage1",
                        help="Р•СЃР»Рё РЅР°РєРѕРїР»РµРЅРЅС‹Р№ С€С‚СЂР°С„ > РїРѕСЂРѕРіР° вЂ” РїСЂРµСЂС‹РІР°РµС‚ РѕСЃС‚Р°РІС€РёРµСЃСЏ С‚РµСЃС‚С‹ РґР»СЏ РєР°РЅРґРёРґР°С‚Р° (СѓСЃРєРѕСЂСЏРµС‚ РґР»РёРЅРЅС‹Рµ СЃС‚Р°РґРёРё).",
                    )
                    stop_pen_stage2 = st.number_input(
                        "EarlyвЂ‘stop С€С‚СЂР°С„ (stage2)",
                        min_value=0.0,
                        max_value=1e9,
                        value=float(st.session_state.get("stop_pen_stage2", 15.0)),
                        step=1.0,
                        key="stop_pen_stage2",
                        help="Р‘РѕР»РµРµ СЃС‚СЂРѕРіРёР№ РїРѕСЂРѕРі РґР»СЏ С„РёРЅР°Р»СЊРЅРѕР№ (РґРѕСЂРѕРіРѕР№) СЃС‚Р°РґРёРё.",
                    )

                    sort_tests_by_cost = st.checkbox(
                        "РЎРѕСЂС‚РёСЂРѕРІР°С‚СЊ С‚РµСЃС‚С‹ РїРѕ СЃС‚РѕРёРјРѕСЃС‚Рё (РґРµС€С‘РІС‹Рµ РїРµСЂРІС‹РјРё)",
                        value=bool(st.session_state.get("sort_tests_by_cost", DIAGNOSTIC_SORT_TESTS_BY_COST)),
                        key="sort_tests_by_cost",
                        help="РџРѕРјРѕРіР°РµС‚ earlyвЂ‘stop Р±С‹СЃС‚СЂРµРµ РѕС‚Р±СЂР°СЃС‹РІР°С‚СЊ РїР»РѕС…РёРµ РєР°РЅРґРёРґР°С‚С‹ РЅР° РґР»РёРЅРЅС‹С… РЅР°Р±РѕСЂР°С….",
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
                            "РћС‚РЅРѕСЃРёС‚РµР»СЊРЅС‹Р№ С€Р°Рі РІРѕР·РјСѓС‰РµРЅРёСЏ РґР»СЏ system_influence_report_v1. "
                            "StageRunner С‚РµРїРµСЂСЊ РїРµСЂРµРґР°С‘С‚ СЌС‚Рѕ Р·РЅР°С‡РµРЅРёРµ СЏРІРЅРѕ, РІРјРµСЃС‚Рѕ СЃРєСЂС‹С‚РѕРіРѕ РґРµС„РѕР»С‚Р° РІРЅСѓС‚СЂРё СЃРєСЂРёРїС‚Р°."
                        ),
                    )
                    adaptive_influence_eps = st.checkbox(
                        "Adaptive epsilon РґР»СЏ System Influence",
                        value=bool(st.session_state.get("adaptive_influence_eps", DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS)),
                        key="adaptive_influence_eps",
                        help=(
                            "System Influence РїСЂРѕРіРѕРЅСЏРµС‚ РЅРµР±РѕР»СЊС€РѕР№ РЅР°Р±РѕСЂ eps_rel Рё РІС‹Р±РёСЂР°РµС‚ РЅР°РёР±РѕР»РµРµ СѓСЃС‚РѕР№С‡РёРІС‹Р№ С€Р°Рі "
                            f"РґР»СЏ РєР°Р¶РґРѕРіРѕ РїР°СЂР°РјРµС‚СЂР°. Р‘Р°Р·РѕРІР°СЏ СЃРµС‚РєР°: {influence_eps_grid_text(DIAGNOSTIC_ADAPTIVE_INFLUENCE_EPS_GRID)}. "
                            "Р”Р»СЏ StageRunner РїРѕРІРµСЂС… РЅРµС‘ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃС‚СЂРѕСЏС‚СЃСЏ stage-aware РїСЂРѕС„РёР»Рё: "
                            "stage0 = coarse, stage1 = balanced, stage2 = fine."
                        ),
                    )
                    stage_policy_mode = st.selectbox(
                        "Seed/promotion policy",
                        options=["influence_weighted", "static"],
                        index=["influence_weighted", "static"].index(str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE)) if str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE) in ["influence_weighted", "static"] else 0,
                        key="stage_policy_mode",
                        help=(
                            "influence_weighted вЂ” seed budgeting Рё promotion СѓС‡РёС‚С‹РІР°СЋС‚ stage-specific influence summary: "
                            "stage0 РѕСЃС‚Р°С‘С‚СЃСЏ С€РёСЂРѕРєРёРј, stage1 СѓР¶Рµ С„РѕРєСѓСЃРёСЂСѓРµС‚СЃСЏ, stage2 РїСЂРѕРґРІРёРіР°РµС‚ С‚РѕР»СЊРєРѕ СѓР·РєРѕ СЂРµР»РµРІР°РЅС‚РЅС‹Рµ РїР°СЂР°РјРµС‚СЂС‹.\n"
                            "static вЂ” РёСЃС‚РѕСЂРёС‡РµСЃРєРѕРµ РїРѕРІРµРґРµРЅРёРµ: С‚РѕР»СЊРєРѕ score/ranges Р±РµР· РїСЂРёРѕСЂРёС‚РёР·Р°С†РёРё РїР°СЂР°РјРµС‚СЂРѕРІ РїРѕ СЃС‚Р°РґРёРё."
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
                    # NOTE(Streamlit): РќРµ Р·Р°РїРёСЃС‹РІР°РµРј РѕР±СЂР°С‚РЅРѕ РІ st.session_state РґР»СЏ РєР»СЋС‡Р° РІРёРґР¶РµС‚Р°.
                    # Streamlit СЃР°Рј СѓРїСЂР°РІР»СЏРµС‚ Р·РЅР°С‡РµРЅРёРµРј РїРѕ key=..., Р° СЏРІРЅР°СЏ Р·Р°РїРёСЃСЊ РїРѕСЃР»Рµ СЃРѕР·РґР°РЅРёСЏ
                    # РІРёРґР¶РµС‚Р° РїСЂРёРІРѕРґРёС‚ Рє StreamlitAPIException.

            # Р•СЃР»Рё StageRunner РІС‹РєР»СЋС‡РµРЅ, РЅСѓР¶РЅС‹ Р·РЅР°С‡РµРЅРёСЏ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РґР»СЏ РєРѕРґР° РЅРёР¶Рµ.
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

            st.divider()
            st.subheader("РРЅР¶РµРЅРµСЂРЅС‹Р№ control plane: distributed / BoTorch / coordinator")
            st.caption(
                "Р­С‚Рё РЅР°СЃС‚СЂРѕР№РєРё СЂР°РЅСЊС€Рµ Р¶РёР»Рё РѕС‚РґРµР»СЊРЅРѕ РЅР° СЃС‚СЂР°РЅРёС†Рµ В«РћРїС‚РёРјРёР·Р°С†РёСЏВ» Рё РІ coordinator CLI. "
                "РўРµРїРµСЂСЊ РѕРЅРё СЃРЅРѕРІР° РІРёРґРёРјС‹ РїСЂСЏРјРѕ Р·РґРµСЃСЊ Рё РїРёС€СѓС‚СЃСЏ РІ С‚РѕС‚ Р¶Рµ session_state."
            )

            _botorch_status = botorch_runtime_status()
            if _botorch_status.get("ready"):
                st.success(botorch_status_markdown(_botorch_status))
            else:
                st.warning(
                    botorch_status_markdown(_botorch_status)
                    + ". Р”Р»СЏ СѓСЃС‚Р°РЅРѕРІРєРё Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№ СЃРј. `pneumo_solver_ui/requirements_mobo_botorch.txt`."
                )

            with st.expander("РђР»РіРѕСЂРёС‚Рј / MOBO / РєСЂРёС‚РµСЂРёРё РѕСЃС‚Р°РЅРѕРІР°", expanded=False):
                c_alg1, c_alg2, c_alg3 = st.columns([2, 2, 2])
                with c_alg1:
                    st.selectbox(
                        "РњРµС‚РѕРґ (Р°Р»РіРѕСЂРёС‚Рј) РїСЂРµРґР»РѕР¶РµРЅРёСЏ РєР°РЅРґРёРґР°С‚РѕРІ",
                        options=["auto", "portfolio", "qnehvi", "random"],
                        index=["auto", "portfolio", "qnehvi", "random"].index(
                            str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)
                        )
                        if str(st.session_state.get("opt_proposer", DIST_OPT_PROPOSER_DEFAULT) or DIST_OPT_PROPOSER_DEFAULT)
                        in ["auto", "portfolio", "qnehvi", "random"]
                        else 0,
                        key="opt_proposer",
                        help=(
                            "auto вЂ” РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ Р»СѓС‡С€РµРµ РґРѕСЃС‚СѓРїРЅРѕРµ (qNEHVI РїСЂРё РЅР°Р»РёС‡РёРё BoTorch, РёРЅР°С‡Рµ random). "
                            "portfolio вЂ” СЃРјРµС€РёРІР°С‚СЊ qNEHVI Рё random РґР»СЏ СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚Рё. "
                            "qnehvi вЂ” BoTorch qNEHVI. random вЂ” LHS/СЃР»СѓС‡Р°Р№РЅС‹Р№ РїРѕРёСЃРє."
                        ),
                    )
                with c_alg2:
                    st.number_input(
                        "Р‘СЋРґР¶РµС‚ (РєРѕР»-РІРѕ РѕС†РµРЅРѕРє С†РµР»РµРІРѕР№ С„СѓРЅРєС†РёРё)",
                        min_value=1,
                        max_value=100000,
                        value=int(st.session_state.get("opt_budget", DIST_OPT_BUDGET_DEFAULT) or DIST_OPT_BUDGET_DEFAULT),
                        step=10,
                        key="opt_budget",
                        help="РЎРєРѕР»СЊРєРѕ Р·Р°РїСѓСЃРєРѕРІ/РѕС†РµРЅРѕРє РІС‹РїРѕР»РЅРёС‚СЊ СЃСѓРјРјР°СЂРЅРѕ.",
                    )
                with c_alg3:
                    st.number_input(
                        "РњР°РєСЃ. РїР°СЂР°Р»Р»РµР»СЊРЅС‹С… Р·Р°РґР°С‡",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("opt_max_inflight", DIST_OPT_MAX_INFLIGHT_DEFAULT) or DIST_OPT_MAX_INFLIGHT_DEFAULT),
                        step=1,
                        key="opt_max_inflight",
                        help="0 вЂ” Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё (в‰€ 2Г— РєРѕР»-РІРѕ evaluators/workers).",
                    )

                c_alg4, c_alg5, c_alg6 = st.columns([2, 2, 2])
                with c_alg4:
                    st.number_input(
                        "Seed (distributed / coordinator)",
                        min_value=0,
                        max_value=2**31 - 1,
                        value=int(st.session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT),
                        step=1,
                        key="opt_seed",
                        help="Seed РґР»СЏ coordinator / proposer path. РћС‚Р»РёС‡Р°РµС‚СЃСЏ РѕС‚ seed_candidates/seed_conditions Р»РѕРєР°Р»СЊРЅРѕРіРѕ StageRunner.",
                    )
                with c_alg5:
                    st.text_input(
                        "РљР»СЋС‡ С€С‚СЂР°С„Р°/РѕРіСЂР°РЅРёС‡РµРЅРёР№ (penalty_key)",
                        value=str(st.session_state.get("opt_penalty_key", DIST_OPT_PENALTY_KEY_DEFAULT) or DIST_OPT_PENALTY_KEY_DEFAULT),
                        key="opt_penalty_key",
                        help="РџРѕР»Рµ РІ result row, РєРѕС‚РѕСЂРѕРµ РёРЅС‚РµСЂРїСЂРµС‚РёСЂСѓРµС‚СЃСЏ РєР°Рє С€С‚СЂР°С„/violation.",
                    )
                with c_alg6:
                    st.number_input(
                        "Р”РѕРїСѓСЃРє С€С‚СЂР°С„Р° (penalty_tolerance)",
                        min_value=0.0,
                        max_value=1e9,
                        value=float(st.session_state.get("opt_penalty_tol", DIST_OPT_PENALTY_TOL_DEFAULT) or DIST_OPT_PENALTY_TOL_DEFAULT),
                        step=1e-9,
                        format="%.3e",
                        key="opt_penalty_tol",
                        help="Р•СЃР»Рё penalty <= tol вЂ” СЃС‡РёС‚Р°РµРј СЂРµС€РµРЅРёРµ РґРѕРїСѓСЃС‚РёРјС‹Рј.",
                    )

                c_alg7, c_alg8, c_alg9 = st.columns([2, 2, 2])
                with c_alg7:
                    _hash_modes = ["stable", "legacy"]
                    _hm_val = str(st.session_state.get("settings_opt_problem_hash_mode", DIAGNOSTIC_PROBLEM_HASH_MODE) or DIAGNOSTIC_PROBLEM_HASH_MODE)
                    st.selectbox(
                        "Р РµР¶РёРј РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂР° Р·Р°РґР°С‡Рё (problem_hash)",
                        options=_hash_modes,
                        index=_hash_modes.index(_hm_val) if _hm_val in _hash_modes else 0,
                        key="settings_opt_problem_hash_mode",
                        help=(
                            "stable вЂ” СѓСЃС‚РѕР№С‡РёРІС‹Р№ hash РїРѕ СЃРѕРґРµСЂР¶РёРјРѕРјСѓ Р·Р°РґР°С‡Рё. "
                            "legacy вЂ” СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ СЃРѕ СЃС‚Р°СЂС‹РјРё run_id."
                        ),
                    )
                with c_alg8:
                    st.number_input(
                        "q (СЃРєРѕР»СЊРєРѕ РєР°РЅРґРёРґР°С‚РѕРІ РїСЂРµРґР»Р°РіР°С‚СЊ Р·Р° С€Р°Рі)",
                        min_value=1,
                        max_value=256,
                        value=int(st.session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT),
                        step=1,
                        key="opt_q",
                        help="Р”Р»СЏ qNEHVI/portfolio РјРѕР¶РЅРѕ РїСЂРµРґР»Р°РіР°С‚СЊ РїР°С‡РєСѓ РєР°РЅРґРёРґР°С‚РѕРІ Р·Р° РёС‚РµСЂР°С†РёСЋ.",
                    )
                with c_alg9:
                    _dev_opts = ["auto", "cpu", "cuda"]
                    _dev_val = str(st.session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT) or DIST_OPT_DEVICE_DEFAULT)
                    st.selectbox(
                        "РЈСЃС‚СЂРѕР№СЃС‚РІРѕ РґР»СЏ РјРѕРґРµР»Рё (device)",
                        options=_dev_opts,
                        index=_dev_opts.index(_dev_val) if _dev_val in _dev_opts else 0,
                        key="opt_device",
                        help="auto вЂ” РІС‹Р±СЂР°С‚СЊ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё. cuda вЂ” РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ GPU (РµСЃР»Рё РґРѕСЃС‚СѓРїРЅРѕ Рё СѓСЃС‚Р°РЅРѕРІР»РµРЅС‹ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё).",
                    )

                st.text_area(
                    "Р¦РµР»РµРІС‹Рµ РјРµС‚СЂРёРєРё (objective keys) вЂ” РїРѕ РѕРґРЅРѕР№ РІ СЃС‚СЂРѕРєРµ",
                    value=str(st.session_state.get("opt_objectives", objectives_text(DEFAULT_OPTIMIZATION_OBJECTIVES))),
                    height=92,
                    key="opt_objectives",
                    help=(
                        "РљР»СЋС‡Рё РјРµС‚СЂРёРє, РєРѕС‚РѕСЂС‹Рµ РѕРїС‚РёРјРёР·РёСЂСѓСЋС‚СЃСЏ (multi-objective). Р¤РѕСЂРјР°С‚: РїРѕ РѕРґРЅРѕР№ РІ СЃС‚СЂРѕРєРµ "
                        "РёР»Рё С‡РµСЂРµР· Р·Р°РїСЏС‚СѓСЋ/С‚РѕС‡РєСѓ СЃ Р·Р°РїСЏС‚РѕР№."
                    ),
                )
                st.caption(
                    "qNEHVI gate: proposer РІРєР»СЋС‡Р°РµС‚СЃСЏ РЅРµ СЃСЂР°Р·Сѓ. РЎРЅР°С‡Р°Р»Р° coordinator РїСЂРѕС…РѕРґРёС‚ warmup, Р·Р°С‚РµРј С‚СЂРµР±СѓРµС‚ feasible history: "
                    "done >= n_init Рё feasible >= min_feasible. РРЅР°С‡Рµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ random/LHS path."
                )

            with st.expander("РџР°СЂР°Р»Р»РµР»РёР·Рј Рё РєР»Р°СЃС‚РµСЂ (Dask / Ray)", expanded=False):
                backend = st.selectbox(
                    "Р‘СЌРєРµРЅРґ distributed optimization",
                    options=["Dask", "Ray"],
                    index=0 if str(st.session_state.get("opt_backend", "Dask")) == "Dask" else 1,
                    key="opt_backend",
                    help="Dask СѓРґРѕР±РµРЅ РґР»СЏ Р»РѕРєР°Р»СЊРЅРѕРіРѕ РїР°СЂР°Р»Р»РµР»РёР·РјР° Рё РїСЂРѕСЃС‚С‹С… РєР»Р°СЃС‚РµСЂРѕРІ; Ray вЂ” РґР»СЏ Р°РєС‚РѕСЂРѕРІ Рё proposer pool/GPU СЃС†РµРЅР°СЂРёРµРІ.",
                )

                if backend == "Dask":
                    mode = st.radio(
                        "Р РµР¶РёРј Dask",
                        options=["Р›РѕРєР°Р»СЊРЅС‹Р№ РєР»Р°СЃС‚РµСЂ (СЃРѕР·РґР°С‚СЊ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё)", "РџРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє scheduler"],
                        index=0 if not str(st.session_state.get("dask_mode", "")).startswith("РџРѕРґРєР»СЋС‡") else 1,
                        key="dask_mode",
                    )
                    if mode.startswith("РџРѕРґРєР»СЋС‡"):
                        st.text_input(
                            "РђРґСЂРµСЃ scheduler (РЅР°РїСЂРёРјРµСЂ: tcp://127.0.0.1:8786)",
                            value=str(st.session_state.get("dask_scheduler", "") or ""),
                            key="dask_scheduler",
                        )
                    else:
                        c_d1, c_d2, c_d3, c_d4 = st.columns([1, 1, 1, 1])
                        with c_d1:
                            st.number_input(
                                "Р’РѕСЂРєРµСЂС‹",
                                min_value=0,
                                max_value=256,
                                value=int(st.session_state.get("dask_workers", 0) or 0),
                                step=1,
                                key="dask_workers",
                            )
                        with c_d2:
                            st.number_input(
                                "РџРѕС‚РѕРєРё/РІРѕСЂРєРµСЂ",
                                min_value=1,
                                max_value=128,
                                value=int(st.session_state.get("dask_threads_per_worker", DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT) or DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT),
                                step=1,
                                key="dask_threads_per_worker",
                            )
                        with c_d3:
                            st.text_input(
                                "Р›РёРјРёС‚ РїР°РјСЏС‚Рё/РІРѕСЂРєРµСЂ",
                                value=str(st.session_state.get("dask_memory_limit", "") or ""),
                                key="dask_memory_limit",
                                help="РќР°РїСЂРёРјРµСЂ: 4GB. РџСѓСЃС‚Рѕ вЂ” auto. '0'/'none' вЂ” РѕС‚РєР»СЋС‡РёС‚СЊ limit.",
                            )
                        with c_d4:
                            st.text_input(
                                "Dashboard address",
                                value=str(st.session_state.get("dask_dashboard_address", DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT) or DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT),
                                key="dask_dashboard_address",
                                help="':0' вЂ” РІС‹Р±СЂР°С‚СЊ РїРѕСЂС‚ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё. РџСѓСЃС‚Рѕ/'none' вЂ” РѕС‚РєР»СЋС‡РёС‚СЊ dashboard.",
                            )
                else:
                    mode = st.radio(
                        "Р РµР¶РёРј Ray",
                        options=["Р›РѕРєР°Р»СЊРЅС‹Р№ РєР»Р°СЃС‚РµСЂ (СЃРѕР·РґР°С‚СЊ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё)", "РџРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє РєР»Р°СЃС‚РµСЂСѓ"],
                        index=0 if not str(st.session_state.get("ray_mode", "")).startswith("РџРѕРґРєР»СЋС‡") else 1,
                        key="ray_mode",
                    )
                    if mode.startswith("РџРѕРґРєР»СЋС‡"):
                        st.text_input(
                            "РђРґСЂРµСЃ Ray (РЅР°РїСЂРёРјРµСЂ: 127.0.0.1:6379 РёР»Рё auto)",
                            value=str(st.session_state.get("ray_address", "auto") or "auto"),
                            key="ray_address",
                        )
                    else:
                        c_r1, c_r2, c_r3 = st.columns([1, 1, 1])
                        with c_r1:
                            st.number_input(
                                "РћРіСЂР°РЅРёС‡РёС‚СЊ CPU (0=Р°РІС‚Рѕ)",
                                min_value=0,
                                max_value=4096,
                                value=int(st.session_state.get("ray_local_num_cpus", 0) or 0),
                                step=1,
                                key="ray_local_num_cpus",
                            )
                        with c_r2:
                            st.checkbox(
                                "Р’РєР»СЋС‡РёС‚СЊ dashboard (Р»РѕРєР°Р»СЊРЅРѕ)",
                                value=bool(st.session_state.get("ray_local_dashboard", False)),
                                key="ray_local_dashboard",
                            )
                        with c_r3:
                            st.number_input(
                                "РџРѕСЂС‚ dashboard (0=Р°РІС‚Рѕ)",
                                min_value=0,
                                max_value=65535,
                                value=int(st.session_state.get("ray_local_dashboard_port", 0) or 0),
                                step=1,
                                key="ray_local_dashboard_port",
                            )

            with st.expander("Coordinator advanced / persistence", expanded=False):
                st.markdown(
                    "РќРёР¶Рµ вЂ” **СЂРµР°Р»СЊРЅРѕ РїРѕРґРєР»СЋС‡С‘РЅРЅС‹Рµ** СЂСѓС‡РєРё РєРѕРѕСЂРґРёРЅР°С‚РѕСЂР°. РћРЅРё РёСЃРїРѕР»СЊР·СѓСЋС‚ С‚РѕС‚ Р¶Рµ session_state, С‡С‚Рѕ Рё СЃС‚СЂР°РЅРёС†Р° "
                    "В«РћРїС‚РёРјРёР·Р°С†РёСЏВ», Рё РїРѕРїР°РґР°СЋС‚ РІ `dist_opt_coordinator.py` Р±РµР· С„РµР№РєРѕРІС‹С… CLI-РїРѕР»РµР№."
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
                            "auto вЂ” РІРєР»СЋС‡Р°С‚СЊ runtime_env С‚РѕР»СЊРєРѕ РґР»СЏ РІРЅРµС€РЅРµРіРѕ Ray-РєР»Р°СЃС‚РµСЂР°; "
                            "on вЂ” РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕ СѓРїР°РєРѕРІС‹РІР°С‚СЊ working_dir РІ runtime_env; "
                            "off вЂ” РЅРµ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ runtime_env."
                        ),
                    )
                    st.text_area(
                        "Ray runtime_env JSON merge (optional)",
                        value=migrated_ray_runtime_env_json(st.session_state),
                        height=120,
                        key="ray_runtime_env_json",
                        help="РћРїС†РёРѕРЅР°Р»СЊРЅС‹Р№ JSON-РѕР±СЉРµРєС‚, РєРѕС‚РѕСЂС‹Р№ Р±СѓРґРµС‚ СЃР»РёС‚ СЃ Р±Р°Р·РѕРІС‹Рј runtime_env РєРѕРѕСЂРґРёРЅР°С‚РѕСЂР°.",
                    )
                    st.text_area(
                        "Ray runtime exclude (РїРѕ РѕРґРЅРѕРјСѓ РїР°С‚С‚РµСЂРЅСѓ РІ СЃС‚СЂРѕРєРµ)",
                        value=str(st.session_state.get("ray_runtime_exclude", "") or ""),
                        height=90,
                        key="ray_runtime_exclude",
                        help="РСЃРєР»СЋС‡РµРЅРёСЏ РїСЂРё СѓРїР°РєРѕРІРєРµ РєРѕРґР° РІ Ray runtime_env.",
                    )
                    st.number_input(
                        "Ray evaluators",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("ray_num_evaluators", 0) or 0),
                        step=1,
                        key="ray_num_evaluators",
                        help="0 вЂ” coordinator СЃР°Рј РІС‹Р±РµСЂРµС‚.",
                    )
                    st.number_input(
                        "CPU РЅР° evaluator",
                        min_value=0.25,
                        max_value=512.0,
                        value=float(st.session_state.get("ray_cpus_per_evaluator", 1.0) or 1.0),
                        step=0.25,
                        format="%.2f",
                        key="ray_cpus_per_evaluator",
                    )
                    st.number_input(
                        "Ray proposers",
                        min_value=0,
                        max_value=512,
                        value=int(st.session_state.get("ray_num_proposers", 0) or 0),
                        step=1,
                        key="ray_num_proposers",
                        help="0=auto (РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ РґРѕСЃС‚СѓРїРЅС‹Рµ GPU РµСЃР»Рё qNEHVI).",
                    )
                    st.number_input(
                        "GPU РЅР° proposer",
                        min_value=0.0,
                        max_value=16.0,
                        value=float(st.session_state.get("ray_gpus_per_proposer", 1.0) or 1.0),
                        step=0.25,
                        format="%.2f",
                        key="ray_gpus_per_proposer",
                    )
                with c_adv2:
                    st.number_input(
                        "Р‘СѓС„РµСЂ РєР°РЅРґРёРґР°С‚РѕРІ proposer_buffer",
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
                        help="SQLite/DuckDB/Postgres DSN РёР»Рё РїСѓС‚СЊ Рє Р‘Р” РґР»СЏ coordinator.",
                    )
                    _db_engine_opts = ["sqlite", "duckdb", "postgres"]
                    _db_engine_val = str(st.session_state.get("opt_db_engine", DIST_OPT_DB_ENGINE_DEFAULT) or DIST_OPT_DB_ENGINE_DEFAULT).strip().lower()
                    st.selectbox(
                        "DB engine",
                        options=_db_engine_opts,
                        index=_db_engine_opts.index(_db_engine_val) if _db_engine_val in _db_engine_opts else _db_engine_opts.index(DIST_OPT_DB_ENGINE_DEFAULT),
                        key="opt_db_engine",
                    )
                    st.checkbox(
                        "Resume from existing run",
                        value=bool(st.session_state.get("opt_resume", False)),
                        key="opt_resume",
                    )
                    st.text_input(
                        "Explicit run_id (optional)",
                        value=str(st.session_state.get("opt_dist_run_id", "") or ""),
                        key="opt_dist_run_id",
                    )
                    st.number_input(
                        "stale-ttl-sec",
                        min_value=0,
                        max_value=604800,
                        value=int(st.session_state.get("opt_stale_ttl_sec", DIST_OPT_STALE_TTL_SEC_DEFAULT) or DIST_OPT_STALE_TTL_SEC_DEFAULT),
                        step=60,
                        key="opt_stale_ttl_sec",
                    )
                    st.checkbox(
                        "РџРёСЃР°С‚СЊ hypervolume log",
                        value=bool(st.session_state.get("opt_hv_log", DIST_OPT_HV_LOG_DEFAULT)),
                        key="opt_hv_log",
                        help="Р•СЃР»Рё РІРєР»СЋС‡РµРЅРѕ вЂ” coordinator РїРёС€РµС‚ progress_hv.csv РїРѕ feasible Pareto-front.",
                    )
                    st.number_input(
                        "export-every",
                        min_value=1,
                        max_value=100000,
                        value=int(st.session_state.get("opt_export_every", DIST_OPT_EXPORT_EVERY_DEFAULT) or DIST_OPT_EXPORT_EVERY_DEFAULT),
                        step=1,
                        key="opt_export_every",
                    )

            with st.expander("BoTorch / qNEHVI advanced", expanded=False):
                st.caption(
                    "qNEHVI РІРєР»СЋС‡Р°РµС‚СЃСЏ С‡РµСЃС‚РЅРѕ: coordinator СЃРЅР°С‡Р°Р»Р° РїСЂРѕС…РѕРґРёС‚ warmup, Р·Р°С‚РµРј РїСЂРѕРІРµСЂСЏРµС‚ feasible-point gate. "
                    "Р•СЃР»Рё done < n_init РёР»Рё feasible < min_feasible, proposer РІСЂРµРјРµРЅРЅРѕ РѕС‚РєР°С‚С‹РІР°РµС‚СЃСЏ РІ random/LHS path."
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
                        help="0 вЂ” auto threshold (~2Г—(dim+1), РЅРѕ РЅРµ РјРµРЅСЊС€Рµ 10).",
                    )
                    st.number_input(
                        "min-feasible",
                        min_value=0,
                        max_value=100000,
                        value=int(st.session_state.get("opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT) or DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
                        step=1,
                        key="opt_botorch_min_feasible",
                        help="0 вЂ” gate РѕС‚РєР»СЋС‡С‘РЅ.",
                    )
                    st.number_input(
                        "num_restarts",
                        min_value=1,
                        max_value=4096,
                        value=int(st.session_state.get("opt_botorch_num_restarts", DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT) or DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT),
                        step=1,
                        key="opt_botorch_num_restarts",
                    )
                with c_b2:
                    st.number_input(
                        "raw_samples",
                        min_value=8,
                        max_value=131072,
                        value=int(st.session_state.get("opt_botorch_raw_samples", DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT) or DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT),
                        step=8,
                        key="opt_botorch_raw_samples",
                    )
                    st.number_input(
                        "maxiter",
                        min_value=1,
                        max_value=100000,
                        value=int(st.session_state.get("opt_botorch_maxiter", DIST_OPT_BOTORCH_MAXITER_DEFAULT) or DIST_OPT_BOTORCH_MAXITER_DEFAULT),
                        step=1,
                        key="opt_botorch_maxiter",
                    )
                    st.number_input(
                        "ref_margin",
                        min_value=0.0,
                        max_value=10.0,
                        value=float(st.session_state.get("opt_botorch_ref_margin", DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT) or DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT),
                        step=0.01,
                        format="%.3f",
                        key="opt_botorch_ref_margin",
                    )
                with c_b3:
                    st.checkbox(
                        "Normalize objectives before GP fit",
                        value=bool(st.session_state.get("opt_botorch_normalize_objectives", DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT)),
                        key="opt_botorch_normalize_objectives",
                        help="РћР±С‹С‡РЅРѕ СЌС‚Рѕ СЃС‚РѕРёС‚ РѕСЃС‚Р°РІРёС‚СЊ РІРєР»СЋС‡С‘РЅРЅС‹Рј; РѕС‚РєР»СЋС‡Р°С‚СЊ С‚РѕР»СЊРєРѕ РґР»СЏ РѕСЃРѕР·РЅР°РЅРЅРѕР№ РґРёР°РіРЅРѕСЃС‚РёРєРё qNEHVI path.",
                    )
                    st.info(
                        "Р­С‚Рё СЂСѓС‡РєРё РґРµР№СЃС‚РІСѓСЋС‚ Рё РґР»СЏ Р»РѕРєР°Р»СЊРЅРѕРіРѕ proposer path, Рё РґР»СЏ Ray proposer actors. "
                        "РўРѕ РµСЃС‚СЊ UI Рё coordinator С‚РµРїРµСЂСЊ СЂРµР°Р»СЊРЅРѕ РіРѕРІРѕСЂСЏС‚ РЅР° РѕРґРЅРѕРј РєРѕРЅС‚СЂР°РєС‚Рµ."
                    )

            st.info(
                "Р’ СЌС‚РѕРј control plane Р±РѕР»СЊС€Рµ РЅРµС‚ вЂCLI-onlyвЂ™ Р·Р°РіР»СѓС€РµРє: РїРѕР»СЏ РІС‹С€Рµ РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ wired РІ С‚РµРєСѓС‰РёР№ distributed coordinator path."
            )

# СЃРѕСЃС‚РѕСЏРЅРёСЏ session
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

# baseline (Р±С‹СЃС‚СЂС‹Р№ РїСЂРѕРіРѕРЅ) + РґРµС‚Р°Р»СЊРЅС‹Рµ Р»РѕРіРё РґР»СЏ РіСЂР°С„РёРєРѕРІ/Р°РЅРёРјР°С†РёРё
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

# РђРІС‚РѕРІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ baseline РїРѕСЃР»Рµ refresh РѕРєРЅР° (Р±РµР· РїРµСЂРµСЃС‡С‘С‚Р°).
# Р’Р°Р¶РЅРѕ: СЌС‚Рѕ С‚РѕР»СЊРєРѕ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РґР°РЅРЅС‹С… РґР»СЏ РїСЂРѕСЃРјРѕС‚СЂР°; Р±Р°Р·Р° РїР°СЂР°РјРµС‚СЂРѕРІ РІ UI РЅРµ В«РїРѕРґРєСЂСѓС‡РёРІР°РµС‚СЃСЏВ» Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё.
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


# Р·Р°РіСЂСѓР·РєР° РјРѕРґСѓР»РµР№
try:
    _default_model_path = _suggest_default_model_path(HERE)
    resolved_worker_path, _worker_msgs = resolve_project_py_path(
        worker_path,
        here=HERE,
        kind="РѕРїС‚РёРјРёР·Р°С‚РѕСЂ",
        default_path=canonical_worker_path(HERE),
    )
    resolved_model_path, _model_msgs = resolve_project_py_path(
        model_path,
        here=HERE,
        kind="РјРѕРґРµР»СЊ",
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
    st.error(f"РќРµ РјРѕРіСѓ Р·Р°РіСЂСѓР·РёС‚СЊ РјРѕРґРµР»СЊ/РѕРїС‚РёРјРёР·Р°С‚РѕСЂ: {e}")
    st.stop()

P_ATM = float(getattr(model_mod, "P_ATM", 101325.0))
# Р’РђР–РќРћ: РІРЅСѓС‚СЂРё РјРѕРґРµР»Рё РґР°РІР»РµРЅРёСЏ = РџР° (Р°Р±СЃРѕР»СЋС‚РЅС‹Рµ).
# Р’ UI РїРѕРєР°Р·С‹РІР°РµРј РґР°РІР»РµРЅРёРµ РєР°Рє "Р±Р°СЂ (РёР·Р±.)" (gauge) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ P_ATM.
# (1 bar = 100000 РџР°). 1 atm = 101325 РџР° РѕСЃС‚Р°РІР»СЏРµРј РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃРѕ СЃС‚Р°СЂС‹РјРё РїСЂРѕС„РёР»СЏРјРё/РєСЌС€РµРј.
ATM_PA = 101325.0  # legacy
BAR_PA = 1e5


pa_abs_to_bar_g = _bar_unit_profile.pressure_from_pa
bar_g_to_pa_abs = _bar_unit_profile.pressure_to_pa_abs



# legacy (РѕСЃС‚Р°РІР»РµРЅРѕ РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃРѕ СЃС‚Р°СЂС‹РјРё РїСЂРѕС„РёР»СЏРјРё)
# Р’РђР–РќРћ: РЅРµ РїРµСЂРµРѕРїСЂРµРґРµР»СЏРµРј pa_abs_to_bar_g. Р‘Р°СЂ(g) РґРѕР»Р¶РµРЅ РѕСЃС‚Р°РІР°С‚СЊСЃСЏ Р±Р°СЂ(g).

_atm_pressure_profile = build_gauge_pressure_profile(
    unit_label="Р°С‚Рј (РёР·Р±.)",
    pressure_offset_pa=P_ATM,
    pressure_divisor_pa=ATM_PA,
)
pa_abs_to_atm_g = _atm_pressure_profile.pressure_from_pa
atm_g_to_pa_abs = _atm_pressure_profile.pressure_to_pa_abs
is_length_param = is_length_param_name


# -------------------------------
# РћРїРёСЃР°РЅРёСЏ/РµРґРёРЅРёС†С‹ РїР°СЂР°РјРµС‚СЂРѕРІ (РґР»СЏ UI)
# Р’РђР–РќРћ: СЌС‚Рё С„СѓРЅРєС†РёРё РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РѕРїСЂРµРґРµР»РµРЅС‹ Р”Рћ С‚РѕРіРѕ, РєР°Рє РјС‹ СЃС‚СЂРѕРёРј С‚Р°Р±Р»РёС†Сѓ df_opt.
# РРЅР°С‡Рµ Python СѓРїР°РґС‘С‚ СЃ NameError, С‚.Рє. РјРѕРґСѓР»СЊ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ СЃРІРµСЂС…Сѓ РІРЅРёР·.
# -------------------------------


param_unit = _bar_unit_profile.param_unit


# -------------------------------
# Р‘Р»РѕРє РїР°СЂР°РјРµС‚СЂРѕРІ (Р±Р°Р·Р° + РґРёР°РїР°Р·РѕРЅС‹)
# -------------------------------
base0, ranges0 = worker_mod.make_base_and_ranges(P_ATM)

# Р—Р°РїРѕРјРёРЅР°РµРј РёСЃС…РѕРґРЅС‹Рµ С‚РёРїС‹ С„Р»Р°РіРѕРІ, С‡С‚РѕР±С‹ UI РєРѕСЂСЂРµРєС‚РЅРѕ РїРѕРєР°Р·С‹РІР°Р» С‡РµРєР±РѕРєСЃС‹ РґР°Р¶Рµ РµСЃР»Рё РіРґРµ-С‚Рѕ Р·РЅР°С‡РµРЅРёСЏ СЃС‚Р°Р»Рё 0/1 РёР»Рё numpy.bool_.
try:
    BASE_BOOL_KEYS = {k for k, v in base0.items() if isinstance(v, (bool, np.bool_))}
except Exception:
    BASE_BOOL_KEYS = {k for k, v in base0.items() if isinstance(v, bool)}

with colA:
    st.subheader("РџР°СЂР°РјРµС‚СЂС‹, РєРѕС‚РѕСЂС‹Рµ СѓС‡Р°СЃС‚РІСѓСЋС‚ РІ РѕРїС‚РёРјРёР·Р°С†РёРё")
    st.caption("РЎС‚Р°РІРёС€СЊ РіР°Р»РѕС‡РєСѓ вЂ” РїР°СЂР°РјРµС‚СЂ РѕРїС‚РёРјРёР·РёСЂСѓРµС‚СЃСЏ РІ РґРёР°РїР°Р·РѕРЅРµ. РќРµ СЃС‚Р°РІРёС€СЊ вЂ” С„РёРєСЃРёСЂСѓРµС‚СЃСЏ Р±Р°Р·РѕРІС‹Рј Р·РЅР°С‡РµРЅРёРµРј.")

    # СЂРµРґР°РєС‚РёСЂСѓРµРјР°СЏ С‚Р°Р±Р»РёС†Р° РїР°СЂР°РјРµС‚СЂРѕРІ (РїСЂРѕСЃС‚Р°СЏ)
    
# -------------------------------
# Р•Р”РРќР«Р™ Р’Р’РћР” РџРђР РђРњР•РўР РћР’ (Р·РЅР°С‡РµРЅРёРµ + РґРёР°РїР°Р·РѕРЅ РѕРїС‚РёРјРёР·Р°С†РёРё)
# -------------------------------

st.subheader("РџР°СЂР°РјРµС‚СЂС‹ РјРѕРґРµР»Рё Рё РґРёР°РїР°Р·РѕРЅС‹ РѕРїС‚РёРјРёР·Р°С†РёРё")
st.caption(
    "Р•РґРёРЅР°СЏ С‚Р°Р±Р»РёС†Р°: Сѓ РєР°Р¶РґРѕРіРѕ РїР°СЂР°РјРµС‚СЂР° РµСЃС‚СЊ Р±Р°Р·РѕРІРѕРµ Р·РЅР°С‡РµРЅРёРµ, Рё (РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё) РґРёР°РїР°Р·РѕРЅ РѕРїС‚РёРјРёР·Р°С†РёРё. "
    "Р”СѓР±Р»РёСЂСѓСЋС‰РёР№ РІРІРѕРґ СѓР±СЂР°РЅ: РѕРїС‚РёРјРёР·Р°С‚РѕСЂ РёСЃРїРѕР»СЊР·СѓРµС‚ РўРћР›Р¬РљРћ С‚Рѕ, С‡С‚Рѕ РІ СЌС‚РѕР№ С‚Р°Р±Р»РёС†Рµ."
)

# РњРµС‚Р°РґР°РЅРЅС‹Рµ (С‚РµРєСЃС‚/РµРґРёРЅРёС†С‹) вЂ” Р±РµР· В«Р·Р°С…Р°СЂРґРєРѕР¶РµРЅРЅС‹С…В» С‡РёСЃРµР».
PARAM_META = {
    # Р”Р°РІР»РµРЅРёСЏ (СѓСЃС‚Р°РІРєРё) вЂ” РІ UI: Р±Р°СЂ (РёР·Р±С‹С‚РѕС‡РЅРѕРіРѕ)
    "РґР°РІР»РµРЅРёРµ_Pmin_РїРёС‚Р°РЅРёРµ_Р РµСЃРёРІРµСЂ2": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р±Р°СЂ (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "РЈСЃС‚Р°РІРєР° РїРѕРґРїРёС‚РєРё: Р»РёРЅРёСЏ В«РђРєРєСѓРјСѓР»СЏС‚РѕСЂ в†’ Р РµСЃРёРІРµСЂ 2В». Р­С‚Рѕ РќР• Pmin СЃР±СЂРѕСЃР°/Р°С‚РјРѕСЃС„РµСЂС‹. "
                    "РћРїС‚РёРјРёР·РёСЂСѓР№С‚Рµ РѕС‚РґРµР»СЊРЅРѕ РѕС‚ Pmin."
    },
    "РґР°РІР»РµРЅРёРµ_Pmin_СЃР±СЂРѕСЃ": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р±Р°СЂ (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "Pmin РґР»СЏ СЃР±СЂРѕСЃР° РІ Р°С‚РјРѕСЃС„РµСЂСѓ (РІРµС‚РєР° Р 3в†’Р°С‚Рј). РќРёР¶Рµ СЌС‚РѕРіРѕ РґР°РІР»РµРЅРёСЏ СЃС‚СѓРїРµРЅСЊ РЅРµ РґРѕР»Р¶РЅР° В«СЂР°Р·СЂСЏР¶Р°С‚СЊСЃСЏВ» РІ РЅРѕР»СЊ."
    },
    "РґР°РІР»РµРЅРёРµ_Pmid_СЃР±СЂРѕСЃ": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р±Р°СЂ (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "Pmid (СѓСЃС‚Р°РІРєР° В«СЃРµСЂРµРґРёРЅС‹В»): РІС‹С€Рµ вЂ” РїРѕРґРІРµСЃРєР° Р·Р°РјРµС‚РЅРѕ В«Р¶С‘СЃС‚С‡РµВ». РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ РјРµС‚СЂРёРєРµ В«СЂР°РЅСЊС€Рµ-Р¶С‘СЃС‚РєРѕВ»."
    },
    "РґР°РІР»РµРЅРёРµ_PР·Р°СЂСЏРґ_Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР°_РёР·_Р РµСЃРёРІРµСЂ3": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р±Р°СЂ (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "РЈСЃС‚Р°РІРєР° РїРѕРґРїРёС‚РєРё Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР° РёР· Р РµСЃРёРІРµСЂР° 3 РІРѕ РІСЂРµРјСЏ РґРІРёР¶РµРЅРёСЏ (РІРѕСЃРїРѕР»РЅРµРЅРёРµ Р·Р°РїР°СЃР° РІРѕР·РґСѓС…Р°)."
    },
    "РґР°РІР»РµРЅРёРµ_Pmax_РїСЂРµРґРѕС…СЂР°РЅ": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р±Р°СЂ (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "Pmax вЂ” Р°РІР°СЂРёР№РЅР°СЏ СѓСЃС‚Р°РІРєР° РїСЂРµРґРѕС…СЂР°РЅРёС‚РµР»СЊРЅРѕРіРѕ РєР»Р°РїР°РЅР° (РЅРµ РґРѕР»Р¶РЅР° РїСЂРµРІС‹С€Р°С‚СЊСЃСЏ)."
    },
    "РЅР°С‡Р°Р»СЊРЅРѕРµ_РґР°РІР»РµРЅРёРµ_Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР°": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (РЅР°С‡Р°Р»СЊРЅС‹Рµ)",
        "РµРґ": "Р±Р°СЂ (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "РќР°С‡Р°Р»СЊРЅРѕРµ РґР°РІР»РµРЅРёРµ РІ Р°РєРєСѓРјСѓР»СЏС‚РѕСЂРµ РЅР° СЃС‚Р°СЂС‚Рµ РґРІРёР¶РµРЅРёСЏ. РџРѕ РІР°С€РµРјСѓ РўР— РѕР±С‹С‡РЅРѕ СЂР°РІРЅРѕ Pmin (РёРґРµР°Р»СЊРЅРѕ вЂ” СЃС‚Р°СЂС‚РѕРІР°С‚СЊ РґР°Р¶Рµ СЃ РїСѓСЃС‚С‹Рј)."
    },

    # РћР±СЉС‘РјС‹ вЂ” РІ UI: Р» РёР»Рё РјР»
    "РѕР±СЉС‘Рј_СЂРµСЃРёРІРµСЂР°_1": {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "Р»", "kind": "volume_L", "РѕРїРёСЃР°РЅРёРµ": "РћР±СЉС‘Рј СЂРµСЃРёРІРµСЂР° 1."},
    "РѕР±СЉС‘Рј_СЂРµСЃРёРІРµСЂР°_2": {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "Р»", "kind": "volume_L", "РѕРїРёСЃР°РЅРёРµ": "РћР±СЉС‘Рј СЂРµСЃРёРІРµСЂР° 2."},
    "РѕР±СЉС‘Рј_СЂРµСЃРёРІРµСЂР°_3": {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "Р»", "kind": "volume_L", "РѕРїРёСЃР°РЅРёРµ": "РћР±СЉС‘Рј СЂРµСЃРёРІРµСЂР° 3."},
    "РѕР±СЉС‘Рј_Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР°": {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "Р»", "kind": "volume_L", "РѕРїРёСЃР°РЅРёРµ": "РћР±СЉС‘Рј Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР°."},
    "РѕР±СЉС‘Рј_Р»РёРЅРёРё": {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "РјР»", "kind": "volume_mL", "РѕРїРёСЃР°РЅРёРµ": "Р­РєРІРёРІР°Р»РµРЅС‚РЅС‹Р№ РѕР±СЉС‘Рј РїРЅРµРІРјРѕР»РёРЅРёРё (СЃСѓРјРјР°СЂРЅРѕ), СѓС‡РёС‚С‹РІР°РµС‚ СЃР¶РёРјР°РµРјРѕСЃС‚СЊ РІ С‚СЂСѓР±РєР°С…."},
    "РјС‘СЂС‚РІС‹Р№_РѕР±СЉС‘Рј_РєР°РјРµСЂС‹": {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "РјР»", "kind": "volume_mL", "РѕРїРёСЃР°РЅРёРµ": "РњС‘СЂС‚РІС‹Р№ РѕР±СЉС‘Рј РєР°РјРµСЂС‹/РїРѕР»РѕСЃС‚Рё (РёР· РєР°С‚Р°Р»РѕРіРѕРІ Camozzi)."},


    # Р”СЂРѕСЃСЃРµР»Рё/РїСЂРѕС…РѕРґС‹ вЂ” РґРѕР»СЏ РѕС‚РєСЂС‹С‚РёСЏ 0..1
    "РѕС‚РєСЂС‹С‚РёРµ_РґСЂРѕСЃСЃРµР»СЏ_Р¦2_CAP_РІ_ROD": {
        "РіСЂСѓРїРїР°": "Р”СЂРѕСЃСЃРµР»Рё",
        "РµРґ": "РґРѕР»СЏ 0..1",
        "kind": "fraction01",
        "РѕРїРёСЃР°РЅРёРµ": "РќРѕСЂРјРёСЂРѕРІР°РЅРЅР°СЏ РґРѕР»СЏ РѕС‚РєСЂС‹С‚РёСЏ РґСЂРѕСЃСЃРµР»СЏ (0=РјРёРЅРёРјСѓРј/РїРѕС‡С‚Рё Р·Р°РєСЂС‹С‚, 1=РјР°РєСЃРёРјСѓРј/РїРѕР»РЅРѕСЃС‚СЊСЋ РѕС‚РєСЂС‹С‚). "
                    "Р¤РёР·РёС‡РµСЃРєРё РёРЅС‚РµСЂРїСЂРµС‚РёСЂСѓРµС‚СЃСЏ РєР°Рє РјР°СЃС€С‚Р°Р± РїСЂРѕС…РѕРґРЅРѕРіРѕ СЃРµС‡РµРЅРёСЏ/kv РІС‹Р±СЂР°РЅРЅРѕРіРѕ РґСЂРѕСЃСЃРµР»СЏ Camozzi."
    },
    "РѕС‚РєСЂС‹С‚РёРµ_РґСЂРѕСЃСЃРµР»СЏ_Р¦2_ROD_РІ_CAP": {"РіСЂСѓРїРїР°": "Р”СЂРѕСЃСЃРµР»Рё", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01", "РѕРїРёСЃР°РЅРёРµ": "РўРѕ Р¶Рµ, РѕР±СЂР°С‚РЅРѕРµ РЅР°РїСЂР°РІР»РµРЅРёРµ (С€С‚РѕРєв†’РїРѕСЂС€РµРЅСЊ)."},
    "РѕС‚РєСЂС‹С‚РёРµ_РґСЂРѕСЃСЃРµР»СЏ_Р¦1_CAP_РІ_ROD": {"РіСЂСѓРїРїР°": "Р”СЂРѕСЃСЃРµР»Рё", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01", "РѕРїРёСЃР°РЅРёРµ": "РўРѕ Р¶Рµ РґР»СЏ Р¦1."},
    "РѕС‚РєСЂС‹С‚РёРµ_РґСЂРѕСЃСЃРµР»СЏ_Р¦1_ROD_РІ_CAP": {"РіСЂСѓРїРїР°": "Р”СЂРѕСЃСЃРµР»Рё", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01", "РѕРїРёСЃР°РЅРёРµ": "РўРѕ Р¶Рµ РґР»СЏ Р¦1 (РѕР±СЂР°С‚РЅРѕРµ РЅР°РїСЂР°РІР»РµРЅРёРµ)."},

    # РџСЂСѓР¶РёРЅР°
    "РїСЂСѓР¶РёРЅР°_РјР°СЃС€С‚Р°Р±": {
        "РіСЂСѓРїРїР°": "РџСЂСѓР¶РёРЅР°",
        "РµРґ": "РєРѕСЌС„.",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "РњР°СЃС€С‚Р°Р± РєСЂРёРІРѕР№ В«СЃРёР»Р°-С…РѕРґВ» РїСЂСѓР¶РёРЅС‹ (С‚Р°Р±Р»РёС‡РЅР°СЏ РЅРµР»РёРЅРµР№РЅРѕСЃС‚СЊ РѕСЃС‚Р°С‘С‚СЃСЏ, СѓРјРЅРѕР¶Р°РµРј СЃРёР»Сѓ РЅР° РєРѕСЌС„С„РёС†РёРµРЅС‚)."
    },

    # РњРµС…Р°РЅРёРєР°/РјР°СЃСЃС‹
    "РјР°СЃСЃР°_СЂР°РјС‹": {"РіСЂСѓРїРїР°": "РњРµС…Р°РЅРёРєР°", "РµРґ": "РєРі", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕРґСЂРµСЃСЃРѕСЂРµРЅРЅР°СЏ РјР°СЃСЃР° (СЂР°РјР°/РєСѓР·РѕРІ)."},
    "РјР°СЃСЃР°_РЅРµРїРѕРґСЂРµСЃСЃРѕСЂРµРЅРЅР°СЏ": {"РіСЂСѓРїРїР°": "РњРµС…Р°РЅРёРєР°", "РµРґ": "РєРі", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РќРµРїРѕРґСЂРµСЃСЃРѕСЂРµРЅРЅР°СЏ РјР°СЃСЃР° РЅР° РєРѕР»РµСЃРѕ (СЃС‚СѓРїРёС†Р°/СЂС‹С‡Р°Рі/РєРѕР»РµСЃРѕ)."},
    "РєРѕР»РµСЏ": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РљРѕР»РµСЏ (СЂР°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ С†РµРЅС‚СЂР°РјРё Р»РµРІРѕРіРѕ Рё РїСЂР°РІРѕРіРѕ РєРѕР»С‘СЃ)."},
    "Р±Р°Р·Р°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РљРѕР»С‘СЃРЅР°СЏ Р±Р°Р·Р° (РїРµСЂРµРґ-Р·Р°Рґ)."},
    "С€РёСЂРёРЅР°_СЂР°РјС‹": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РЁРёСЂРёРЅР° СЂР°РјС‹ (РґР»СЏ СЂР°СЃС‡С‘С‚Р° РїР»РµС‡/РєРёРЅРµРјР°С‚РёРєРё РІ СѓРїСЂРѕС‰С‘РЅРЅРѕР№ СЃС…РµРјРµ)."},
    "С…РѕРґ_С€С‚РѕРєР°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РЅС‹Р№ С…РѕРґ С€С‚РѕРєР° С†РёР»РёРЅРґСЂР° (РѕРіСЂР°РЅРёС‡РµРЅРёРµ РїРѕ РїСЂРѕР±РѕСЋ/РІС‹Р»РµС‚Сѓ)."},
    "РєРѕСЌС„_РїРµСЂРµРґР°С‡Рё_СЂС‹С‡Р°Рі": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "РєРѕСЌС„.", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРµСЂРµРґР°С‚РѕС‡РЅРѕРµ РѕС‚РЅРѕС€РµРЅРёРµ СЂС‹С‡Р°РіР° (С…РѕРґ С€С‚РѕРєР° в†” С…РѕРґ РєРѕР»РµСЃР°)."},
    "СЃС‚Р°С‚РёС‡РµСЃРєРёР№_С…РѕРґ_РєРѕР»РµСЃР°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РЎС‚Р°С‚РёС‡РµСЃРєРёР№ С…РѕРґ РєРѕР»РµСЃР°/СЃР¶Р°С‚РёРµ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РЅРµР№С‚СЂР°Р»Рё."},

    # РЁРёРЅР°
    "Р¶С‘СЃС‚РєРѕСЃС‚СЊ_С€РёРЅС‹": {"РіСЂСѓРїРїР°": "РЁРёРЅР°", "РµРґ": "Рќ/Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "Р’РµСЂС‚РёРєР°Р»СЊРЅР°СЏ Р¶С‘СЃС‚РєРѕСЃС‚СЊ С€РёРЅС‹ (Р»РёРЅРµР°СЂРёР·РѕРІР°РЅРЅР°СЏ)."},
    "РґРµРјРїС„РёСЂРѕРІР°РЅРёРµ_С€РёРЅС‹": {"РіСЂСѓРїРїР°": "РЁРёРЅР°", "РµРґ": "РќВ·СЃ/Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "Р’РµСЂС‚РёРєР°Р»СЊРЅРѕРµ РґРµРјРїС„РёСЂРѕРІР°РЅРёРµ С€РёРЅС‹ (Р»РёРЅРµР°СЂРёР·РѕРІР°РЅРЅРѕРµ)."},

    # РРЅРµСЂС†РёРё
    "РјРѕРјРµРЅС‚_РёРЅРµСЂС†РёРё_СЂР°РјС‹_РїРѕ_РєСЂРµРЅСѓ": {"РіСЂСѓРїРїР°": "РРЅРµСЂС†РёСЏ", "РµРґ": "РєРіВ·РјВІ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РњРѕРјРµРЅС‚ РёРЅРµСЂС†РёРё СЂР°РјС‹ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РѕСЃРё РєСЂРµРЅР°."},
    "РјРѕРјРµРЅС‚_РёРЅРµСЂС†РёРё_СЂР°РјС‹_РїРѕ_С‚Р°РЅРіР°Р¶Сѓ": {"РіСЂСѓРїРїР°": "РРЅРµСЂС†РёСЏ", "РµРґ": "РєРіВ·РјВІ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РњРѕРјРµРЅС‚ РёРЅРµСЂС†РёРё СЂР°РјС‹ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РѕСЃРё С‚Р°РЅРіР°Р¶Р°."},
    "РјРѕРјРµРЅС‚_РёРЅРµСЂС†РёРё_СЂР°РјС‹_РїРѕ_СЂС‹СЃРєР°РЅСЊСЋ": {"РіСЂСѓРїРїР°": "РРЅРµСЂС†РёСЏ", "РµРґ": "РєРіВ·РјВІ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РњРѕРјРµРЅС‚ РёРЅРµСЂС†РёРё СЂР°РјС‹ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РѕСЃРё СЂС‹СЃРєР°РЅСЊСЏ."},

    # РћРіСЂР°РЅРёС‡РµРЅРёСЏ/Р·Р°РїР°СЃС‹ (РІ UI)
    "Р»РёРјРёС‚_РїСЂРѕР±РѕСЏ_РєСЂРµРЅ_РіСЂР°Рґ": {"РіСЂСѓРїРїР°": "РћРіСЂР°РЅРёС‡РµРЅРёСЏ", "РµРґ": "РіСЂР°Рґ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РћРіСЂР°РЅРёС‡РµРЅРёРµ РїРѕ РєСЂРµРЅСѓ (Р¶С‘СЃС‚РєРѕРµ/Р°РІР°СЂРёР№РЅРѕРµ)."},
    "Р»РёРјРёС‚_РїСЂРѕР±РѕСЏ_С‚Р°РЅРіР°Р¶_РіСЂР°Рґ": {"РіСЂСѓРїРїР°": "РћРіСЂР°РЅРёС‡РµРЅРёСЏ", "РµРґ": "РіСЂР°Рґ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РћРіСЂР°РЅРёС‡РµРЅРёРµ РїРѕ С‚Р°РЅРіР°Р¶Сѓ (Р¶С‘СЃС‚РєРѕРµ/Р°РІР°СЂРёР№РЅРѕРµ)."},
    "РјРёРЅРёРјР°Р»СЊРЅРѕРµ_Р°Р±СЃРѕР»СЋС‚РЅРѕРµ_РґР°РІР»РµРЅРёРµ_РџР°": {"РіСЂСѓРїРїР°": "РћРіСЂР°РЅРёС‡РµРЅРёСЏ", "РµРґ": "РєРџР° (Р°Р±СЃ.)", "kind": "pressure_kPa_abs", "РѕРїРёСЃР°РЅРёРµ": "РќРёР¶РЅСЏСЏ РіСЂР°РЅРёС†Р° Р°Р±СЃРѕР»СЋС‚РЅРѕРіРѕ РґР°РІР»РµРЅРёСЏ РґР»СЏ С‡РёСЃР»РµРЅРЅРѕР№ СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚Рё. Р’Р°РєСѓСѓРј РґРѕРїСѓСЃРєР°РµРј, РЅРѕ p_abs РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ < 0."},

    # Р“Р°Р·
    "С‚РµРјРїРµСЂР°С‚СѓСЂР°_РіР°Р·Р°_Рљ": {"РіСЂСѓРїРїР°": "Р“Р°Р·", "РµРґ": "В°C", "kind": "temperature_C", "РѕРїРёСЃР°РЅРёРµ": "РўРµРјРїРµСЂР°С‚СѓСЂР° РіР°Р·Р° (РІРЅСѓС‚СЂРё РјРѕРґРµР»Рё С…СЂР°РЅРёС‚СЃСЏ РљРµР»СЊРІРёРЅ)."},
    "РіСЂР°РІРёС‚Р°С†РёСЏ": {"РіСЂСѓРїРїР°": "РЎСЂРµРґР°", "РµРґ": "Рј/СЃВІ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РЈСЃРєРѕСЂРµРЅРёРµ СЃРІРѕР±РѕРґРЅРѕРіРѕ РїР°РґРµРЅРёСЏ."},

    # Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (РґРІРѕР№РЅС‹Рµ РїРѕРїРµСЂРµС‡РЅС‹Рµ СЂС‹С‡Р°РіРё / DW2D)
    "dw_lower_pivot_inboard_РїРµСЂРµРґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "РЎРјРµС‰РµРЅРёРµ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° (РїРµСЂРµРґ) РІРЅСѓС‚СЂСЊ РѕС‚ С†РµРЅС‚СЂР° РєРѕР»РµСЃР° РїРѕ РѕСЃРё Y. РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ РєРёРЅРµРјР°С‚РёРєРµ dw2d_mounts."
    },
    "dw_lower_pivot_inboard_Р·Р°Рґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "РЎРјРµС‰РµРЅРёРµ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° (Р·Р°Рґ) РІРЅСѓС‚СЂСЊ РѕС‚ С†РµРЅС‚СЂР° РєРѕР»РµСЃР° РїРѕ РѕСЃРё Y. РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ РєРёРЅРµРјР°С‚РёРєРµ dw2d_mounts."
    },
    "dw_lower_pivot_z_РїРµСЂРµРґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° (РїРµСЂРµРґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ (z_body РґР»СЏ РґР°РЅРЅРѕР№ С‚РѕС‡РєРё = 0)."
    },
    "dw_lower_pivot_z_Р·Р°Рґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° (Р·Р°Рґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ (z_body РґР»СЏ РґР°РЅРЅРѕР№ С‚РѕС‡РєРё = 0)."
    },
    "dw_lower_arm_len_РїРµСЂРµРґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р”Р»РёРЅР° РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° (РїРµСЂРµРґ): СЂР°СЃСЃС‚РѕСЏРЅРёРµ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РґРѕ С€Р°СЂРЅРёСЂР° Сѓ РїРѕРІРѕСЂРѕС‚РЅРѕРіРѕ РєСѓР»Р°РєР°/СЃС‚СѓРїРёС†С‹ (РІ 2D-РїСЂРёР±Р»РёР¶РµРЅРёРё Y-Z)."
    },
    "dw_lower_arm_len_Р·Р°Рґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р”Р»РёРЅР° РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° (Р·Р°Рґ): СЂР°СЃСЃС‚РѕСЏРЅРёРµ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РґРѕ С€Р°СЂРЅРёСЂР° Сѓ РїРѕРІРѕСЂРѕС‚РЅРѕРіРѕ РєСѓР»Р°РєР°/СЃС‚СѓРїРёС†С‹ (РІ 2D-РїСЂРёР±Р»РёР¶РµРЅРёРё Y-Z)."
    },
    "dw_upper_pivot_inboard_РїРµСЂРµРґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "РЎРјРµС‰РµРЅРёРµ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РІРµСЂС…РЅРµРіРѕ СЂС‹С‡Р°РіР° (РїРµСЂРµРґ) РІРЅСѓС‚СЂСЊ РѕС‚ С†РµРЅС‚СЂР° РєРѕР»РµСЃР° РїРѕ РѕСЃРё Y. РљР°РЅРѕРЅРёС‡РµСЃРєРёР№ source-data РґР»СЏ РІС‚РѕСЂРѕРіРѕ СЂС‹С‡Р°РіР°."
    },
    "dw_upper_pivot_inboard_Р·Р°Рґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "РЎРјРµС‰РµРЅРёРµ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РІРµСЂС…РЅРµРіРѕ СЂС‹С‡Р°РіР° (Р·Р°Рґ) РІРЅСѓС‚СЂСЊ РѕС‚ С†РµРЅС‚СЂР° РєРѕР»РµСЃР° РїРѕ РѕСЃРё Y. РљР°РЅРѕРЅРёС‡РµСЃРєРёР№ source-data РґР»СЏ РІС‚РѕСЂРѕРіРѕ СЂС‹С‡Р°РіР°."
    },
    "dw_upper_pivot_z_РїРµСЂРµРґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РІРµСЂС…РЅРµРіРѕ СЂС‹С‡Р°РіР° (РїРµСЂРµРґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ. РљР°РЅРѕРЅРёС‡РµСЃРєРёР№ source-data РґР»СЏ РІС‚РѕСЂРѕРіРѕ СЂС‹С‡Р°РіР°."
    },
    "dw_upper_pivot_z_Р·Р°Рґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РІРµСЂС…РЅРµРіРѕ СЂС‹С‡Р°РіР° (Р·Р°Рґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ. РљР°РЅРѕРЅРёС‡РµСЃРєРёР№ source-data РґР»СЏ РІС‚РѕСЂРѕРіРѕ СЂС‹С‡Р°РіР°."
    },
    "dw_upper_arm_len_РїРµСЂРµРґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р”Р»РёРЅР° РІРµСЂС…РЅРµРіРѕ СЂС‹С‡Р°РіР° (РїРµСЂРµРґ): СЂР°СЃСЃС‚РѕСЏРЅРёРµ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РґРѕ С€Р°СЂРЅРёСЂР° Сѓ РїРѕРІРѕСЂРѕС‚РЅРѕРіРѕ РєСѓР»Р°РєР°/СЃС‚СѓРїРёС†С‹ (РІ 2D-РїСЂРёР±Р»РёР¶РµРЅРёРё Y-Z)."
    },
    "dw_upper_arm_len_Р·Р°Рґ_Рј": {
        "РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)",
        "РµРґ": "Рј",
        "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р”Р»РёРЅР° РІРµСЂС…РЅРµРіРѕ СЂС‹С‡Р°РіР° (Р·Р°Рґ): СЂР°СЃСЃС‚РѕСЏРЅРёРµ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° РґРѕ С€Р°СЂРЅРёСЂР° Сѓ РїРѕРІРѕСЂРѕС‚РЅРѕРіРѕ РєСѓР»Р°РєР°/СЃС‚СѓРїРёС†С‹ (РІ 2D-РїСЂРёР±Р»РёР¶РµРЅРёРё Y-Z)."
    },

    "РІРµСЂС…_Р¦1_РїРµСЂРµРґ_РјРµР¶РґСѓ_Р›Рџ_РџРџ_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р Р°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ РІРµСЂС…РЅРёРјРё С‚РѕС‡РєР°РјРё РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦1 (РїРµСЂРµРґ), РјРµР¶РґСѓ Р›Рџ Рё РџРџ РїРѕ РѕСЃРё Y."},
    "РІРµСЂС…_Р¦2_РїРµСЂРµРґ_РјРµР¶РґСѓ_Р›Рџ_РџРџ_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р Р°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ РІРµСЂС…РЅРёРјРё С‚РѕС‡РєР°РјРё РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦2 (РїРµСЂРµРґ), РјРµР¶РґСѓ Р›Рџ Рё РџРџ РїРѕ РѕСЃРё Y."},
    "РІРµСЂС…_Р¦1_Р·Р°Рґ_РјРµР¶РґСѓ_Р›Р—_РџР—_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р Р°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ РІРµСЂС…РЅРёРјРё С‚РѕС‡РєР°РјРё РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦1 (Р·Р°Рґ), РјРµР¶РґСѓ Р›Р— Рё РџР— РїРѕ РѕСЃРё Y."},
    "РІРµСЂС…_Р¦2_Р·Р°Рґ_РјРµР¶РґСѓ_Р›Р—_РџР—_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р Р°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ РІРµСЂС…РЅРёРјРё С‚РѕС‡РєР°РјРё РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦2 (Р·Р°Рґ), РјРµР¶РґСѓ Р›Р— Рё РџР— РїРѕ РѕСЃРё Y."},

    "РІРµСЂС…_Р¦1_РїРµСЂРµРґ_z_РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ_СЂР°РјС‹_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРµСЂС…РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦1 (РїРµСЂРµРґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ."},
    "РІРµСЂС…_Р¦2_РїРµСЂРµРґ_z_РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ_СЂР°РјС‹_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРµСЂС…РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦2 (РїРµСЂРµРґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ."},
    "РІРµСЂС…_Р¦1_Р·Р°Рґ_z_РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ_СЂР°РјС‹_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРµСЂС…РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦1 (Р·Р°Рґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ."},
    "РІРµСЂС…_Р¦2_Р·Р°Рґ_z_РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ_СЂР°РјС‹_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw",
        "РѕРїРёСЃР°РЅРёРµ": "Р’С‹СЃРѕС‚Р° (Z) РІРµСЂС…РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ С†РёР»РёРЅРґСЂР° Р¦2 (Р·Р°Рґ) РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂР°РјС‹ РІ СЃС‚Р°С‚РёРєРµ."},

    "РЅРёР·_Р¦1_РїРµСЂРµРґ_РґРѕР»СЏ_СЂС‹С‡Р°РіР°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01",
        "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РѕР¶РµРЅРёРµ РЅРёР¶РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ Р¦1 РЅР° РЅРёР¶РЅРµРј СЂС‹С‡Р°РіРµ (РїРµСЂРµРґ): РґРѕР»СЏ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° (0) РґРѕ С€Р°СЂРЅРёСЂР° СЃС‚СѓРїРёС†С‹ (1)."},
    "РЅРёР·_Р¦2_РїРµСЂРµРґ_РґРѕР»СЏ_СЂС‹С‡Р°РіР°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01",
        "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РѕР¶РµРЅРёРµ РЅРёР¶РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ Р¦2 РЅР° РЅРёР¶РЅРµРј СЂС‹С‡Р°РіРµ (РїРµСЂРµРґ): РґРѕР»СЏ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° (0) РґРѕ С€Р°СЂРЅРёСЂР° СЃС‚СѓРїРёС†С‹ (1)."},
    "РЅРёР·_Р¦1_Р·Р°Рґ_РґРѕР»СЏ_СЂС‹С‡Р°РіР°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01",
        "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РѕР¶РµРЅРёРµ РЅРёР¶РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ Р¦1 РЅР° РЅРёР¶РЅРµРј СЂС‹С‡Р°РіРµ (Р·Р°Рґ): РґРѕР»СЏ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° (0) РґРѕ С€Р°СЂРЅРёСЂР° СЃС‚СѓРїРёС†С‹ (1)."},
    "РЅРёР·_Р¦2_Р·Р°Рґ_РґРѕР»СЏ_СЂС‹С‡Р°РіР°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01",
        "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РѕР¶РµРЅРёРµ РЅРёР¶РЅРµРіРѕ РєСЂРµРїР»РµРЅРёСЏ Р¦2 РЅР° РЅРёР¶РЅРµРј СЂС‹С‡Р°РіРµ (Р·Р°Рґ): РґРѕР»СЏ РѕС‚ РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С€Р°СЂРЅРёСЂР° (0) РґРѕ С€Р°СЂРЅРёСЂР° СЃС‚СѓРїРёС†С‹ (1)."},

    "С…РѕРґ_С€С‚РѕРєР°_Р¦1_РїРµСЂРµРґ_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РЅС‹Р№ С…РѕРґ С€С‚РѕРєР° С†РёР»РёРЅРґСЂР° Р¦1 (РїРµСЂРµРґ)."},
    "С…РѕРґ_С€С‚РѕРєР°_Р¦1_Р·Р°Рґ_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РЅС‹Р№ С…РѕРґ С€С‚РѕРєР° С†РёР»РёРЅРґСЂР° Р¦1 (Р·Р°Рґ)."},
    "С…РѕРґ_С€С‚РѕРєР°_Р¦2_РїРµСЂРµРґ_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РЅС‹Р№ С…РѕРґ С€С‚РѕРєР° С†РёР»РёРЅРґСЂР° Р¦2 (РїРµСЂРµРґ)."},
    "С…РѕРґ_С€С‚РѕРєР°_Р¦2_Р·Р°Рґ_Рј": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕР»РЅС‹Р№ С…РѕРґ С€С‚РѕРєР° С†РёР»РёРЅРґСЂР° Р¦2 (Р·Р°Рґ)."},


}

# --- РќРѕСЂРјР°Р»РёР·Р°С†РёСЏ РјРµС‚Р°РґР°РЅРЅС‹С… (РµРґРёРЅС‹Рµ С‡РµР»РѕРІРµРєРѕвЂ‘РїРѕРЅСЏС‚РЅС‹Рµ РµРґРёРЅРёС†С‹) ---
# Р”Р°РІР»РµРЅРёСЏ: РїРѕРєР°Р·С‹РІР°РµРј РІ Р±Р°СЂ (РёР·Р±.)
for _k, _m in PARAM_META.items():
    if not isinstance(_m, dict):
        continue
    if _m.get("kind") == "pressure_atm_g":
        _m["kind"] = "pressure_bar_g"
        _m["РµРґ"] = "Р±Р°СЂ (РёР·Р±.)"

# Р”Р»РёРЅС‹: РІРЅСѓС‚СЂРµРЅРЅРёРµ РјРµС‚СЂС‹ -> РїРѕРєР°Р·С‹РІР°РµРј РІ РјРј
for _k, _m in PARAM_META.items():
    if not isinstance(_m, dict):
        continue
    if is_length_param(_k) and _m.get("kind", "raw") == "raw" and _m.get("РµРґ") in ("Рј", "m"):
        _m["kind"] = "length_mm"
        _m["РµРґ"] = "РјРј"


def infer_param_meta(k: str) -> Dict[str, str]:
    """Р•РґРёРЅС‹Р№ РёСЃС‚РѕС‡РЅРёРє РјРµС‚Р°РґР°РЅРЅС‹С… РїР°СЂР°РјРµС‚СЂР° РґР»СЏ С‚Р°Р±Р»РёС†С‹ (РіСЂСѓРїРїР°/РµРґРёРЅРёС†С‹/kind/РѕРїРёСЃР°РЅРёРµ).

    Р—Р°РґР°С‡Р°: С‡С‚РѕР±С‹ РІ UI РЅРµ Р±С‹Р»Рѕ В«РєР°С€Р° РёР· РµРґРёРЅРёС†В». Р’РЅСѓС‚СЂРё РјРѕРґРµР»Рё РІСЃС‘ РІ РЎР, РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ вЂ” РїСЂРёРІС‹С‡РЅС‹Рµ.
    """
    if k in PARAM_META:
        return PARAM_META[k]
    fam_meta = family_param_meta(k)
    if fam_meta is not None:
        return fam_meta
    # СЌРІСЂРёСЃС‚РёРєРё РґР»СЏ РїР°СЂР°РјРµС‚СЂРѕРІ, РєРѕС‚РѕСЂС‹С… РЅРµС‚ РІ СЂСѓС‡РЅРѕРј СЃР»РѕРІР°СЂРµ:
    if is_pressure_param(k):
        return {"РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ", "РµРґ": "Р±Р°СЂ (РёР·Р±.)", "kind": "pressure_bar_g", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}
    if is_volume_param(k):
        if is_small_volume_param(k):
            return {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "РјР»", "kind": "volume_mL", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}
        return {"РіСЂСѓРїРїР°": "РћР±СЉС‘РјС‹", "РµРґ": "Р»", "kind": "volume_L", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}
    if is_length_param(k):
        return {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ (РїСЂРѕС‡РµРµ)", "РµРґ": "РјРј", "kind": "length_mm", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}
    if "РѕС‚РєСЂС‹С‚РёРµ" in k:
        return {"РіСЂСѓРїРїР°": "Р”СЂРѕСЃСЃРµР»Рё", "РµРґ": "РґРѕР»СЏ 0..1", "kind": "fraction01", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}
    if k.endswith("_РіСЂР°Рґ"):
        return {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ (СѓРіР»С‹)", "РµРґ": "РіСЂР°Рґ", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}
    # РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ:
    return {"РіСЂСѓРїРїР°": "РџСЂРѕС‡РµРµ", "РµРґ": "РЎР", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": param_desc(k)}


_si_to_ui = _bar_unit_profile.si_to_ui
_ui_to_si = _bar_unit_profile.ui_to_si


# РґРѕРїРѕР»РЅСЏРµРј Р±Р°Р·Сѓ Р·РЅР°С‡РµРЅРёСЏРјРё РґР»СЏ РєР»СЋС‡РµР№, РєРѕС‚РѕСЂС‹Рµ РµСЃС‚СЊ РІ РґРёР°РїР°Р·РѕРЅР°С…, РЅРѕ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ РІ base0
for _k, _rng in ranges0.items():
    if _k not in base0:
        try:
            base0[_k] = 0.5 * (float(_rng[0]) + float(_rng[1]))
        except Exception:
            base0[_k] = float("nan")

all_keys = sorted(set(base0.keys()) | set(ranges0.keys()))

# --- РЎС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅС‹Рµ РїР°СЂР°РјРµС‚СЂС‹ (СЃРїРёСЃРєРё/С‚Р°Р±Р»РёС†С‹) ---
# Р’Р°Р¶РЅРѕ: РЅРµРєРѕС‚РѕСЂС‹Рµ РїР°СЂР°РјРµС‚СЂС‹ (РЅР°РїСЂРёРјРµСЂ РЅРµР»РёРЅРµР№РЅР°СЏ РїСЂСѓР¶РёРЅР°) С…СЂР°РЅСЏС‚СЃСЏ РєР°Рє СЃРїРёСЃРєРё С‡РёСЃРµР».
# РС… РЅРµР»СЊР·СЏ РїРѕРєР°Р·С‹РІР°С‚СЊ РІ РѕР±С‰РµР№ С‚Р°Р±Р»РёС†Рµ СЃРєР°Р»СЏСЂРѕРІ (РёРЅР°С‡Рµ Р±СѓРґРµС‚ TypeError: float(list)).

# 1) РўР°Р±Р»РёС†Р° РЅРµР»РёРЅРµР№РЅРѕР№ РїСЂСѓР¶РёРЅС‹ (С…РѕРґ_РјРј -> СЃРёР»Р°_Рќ)
SPR_X = "РїСЂСѓР¶РёРЅР°_С‚Р°Р±Р»РёС†Р°_С…РѕРґ_РјРј"
SPR_F = "РїСЂСѓР¶РёРЅР°_С‚Р°Р±Р»РёС†Р°_СЃРёР»Р°_Рќ"

if (SPR_X in base0) and (SPR_F in base0):
    try:
        import pandas as _pd
        if "spring_table_df" not in st.session_state:
            st.session_state["spring_table_df"] = _pd.DataFrame({
                "С…РѕРґ_РјРј": list(base0.get(SPR_X, [])),
                "СЃРёР»Р°_Рќ": list(base0.get(SPR_F, [])),
            })

        st.markdown("### РќРµР»РёРЅРµР№РЅР°СЏ РїСЂСѓР¶РёРЅР°: С‚Р°Р±Р»РёС‡РЅР°СЏ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°")
        st.caption("Р РµРґР°РєС‚РёСЂСѓРµС‚СЃСЏ РїСЂСЏРјРѕ Р·РґРµСЃСЊ (Р±РµР· РїСЂР°РІРєРё С„Р°Р№Р»РѕРІ). РўРѕС‡РєРё СЃРѕСЂС‚РёСЂСѓСЋС‚СЃСЏ РїРѕ С…РѕРґСѓ. РњРёРЅРёРјСѓРј 2 С‚РѕС‡РєРё.")
        spring_df = st.data_editor(
            st.session_state["spring_table_df"],
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "С…РѕРґ_РјРј": st.column_config.NumberColumn("РҐРѕРґ (РјРј)", step=None, help="РҐРѕРґ РїРѕРґРІРµСЃРєРё/РїСЂСѓР¶РёРЅС‹ (РјРј). РћС‚СЂРёС†Р°С‚РµР»СЊРЅС‹Р№ = РѕС‚Р±РѕР№, РїРѕР»РѕР¶РёС‚РµР»СЊРЅС‹Р№ = СЃР¶Р°С‚РёРµ."),
                "СЃРёР»Р°_Рќ": st.column_config.NumberColumn("РЎРёР»Р° (Рќ)", step=None, help="РЎРёР»Р° РїСЂСѓР¶РёРЅС‹ (Рќ) РїСЂРё СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РµРј С…РѕРґРµ."),
            },
            key="spring_table_editor",
        )
        st.session_state["spring_table_df"] = spring_df

        # Р’Р°Р»РёРґР°С†РёСЏ + РЅРѕСЂРјР°Р»РёР·Р°С†РёСЏ
        _df = spring_df.copy()
        _df["С…РѕРґ_РјРј"] = _pd.to_numeric(_df["С…РѕРґ_РјРј"], errors="coerce")
        _df["СЃРёР»Р°_Рќ"] = _pd.to_numeric(_df["СЃРёР»Р°_Рќ"], errors="coerce")
        _df = _df.dropna().sort_values("С…РѕРґ_РјРј")
        if len(_df) < 2:
            st.error("РўР°Р±Р»РёС†Р° РїСЂСѓР¶РёРЅС‹ РґРѕР»Р¶РЅР° СЃРѕРґРµСЂР¶Р°С‚СЊ РјРёРЅРёРјСѓРј 2 С‡РёСЃР»РѕРІС‹Рµ С‚РѕС‡РєРё.")
        else:
            base0[SPR_X] = _df["С…РѕРґ_РјРј"].astype(float).tolist()
            base0[SPR_F] = _df["СЃРёР»Р°_Рќ"].astype(float).tolist()
    except Exception as e:
        st.error(f"РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё С‚Р°Р±Р»РёС†С‹ РїСЂСѓР¶РёРЅС‹: {e}")

# РЎРїРёСЃРѕРє РєР»СЋС‡РµР№ СЃРѕ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅС‹РјРё Р·РЅР°С‡РµРЅРёСЏРјРё (list/dict) вЂ” РёС… РёСЃРєР»СЋС‡Р°РµРј РёР· С‚Р°Р±Р»РёС†С‹ СЃРєР°Р»СЏСЂРѕРІ
structured_keys = [k for k in all_keys if isinstance(base0.get(k, None), (list, dict))]

# Р’ С‚Р°Р±Р»РёС†Сѓ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РїРѕРїР°РґР°СЋС‚ С‚РѕР»СЊРєРѕ С‡РёСЃР»РѕРІС‹Рµ СЃРєР°Р»СЏСЂС‹.
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
        "РіСЂСѓРїРїР°": meta.get("РіСЂСѓРїРїР°", "РџСЂРѕС‡РµРµ"),
        "РїР°СЂР°РјРµС‚СЂ": k,
        "РµРґРёРЅРёС†Р°": meta.get("РµРґ", "РЎР"),
        "Р·РЅР°С‡РµРЅРёРµ": val_ui,
        "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ": bool(is_opt),
        "РјРёРЅ": mn_ui,
        "РјР°РєСЃ": mx_ui,
        "РїРѕСЏСЃРЅРµРЅРёРµ": meta.get("РѕРїРёСЃР°РЅРёРµ", ""),
        "_key": k,
        "_kind": kind,
    })

df_params0 = pd.DataFrame(rows)


# Streamlit РёРЅРѕРіРґР° В«Р·Р°Р»РёРїР°РµС‚В» РЅР° СЃС‚Р°СЂРѕРј key РїСЂРё СЃРјРµРЅРµ РЅР°Р±РѕСЂР° РїР°СЂР°РјРµС‚СЂРѕРІ.
# Р”РµР»Р°РµРј СЃРёРіРЅР°С‚СѓСЂСѓ С‚Р°Р±Р»РёС†С‹ Рё РёСЃРїРѕР»СЊР·СѓРµРј РµС‘ РІ key, С‡С‚РѕР±С‹ С‚Р°Р±Р»РёС†Р° РіР°СЂР°РЅС‚РёСЂРѕРІР°РЅРЅРѕ РїРµСЂРµСЃРѕР·РґР°РІР°Р»Р°СЃСЊ РїСЂРё СЃРјРµРЅРµ РЅР°Р±РѕСЂР° СЃС‚СЂРѕРє/СЃС‚РѕР»Р±С†РѕРІ.
_sig_src = df_params0[["РїР°СЂР°РјРµС‚СЂ", "РіСЂСѓРїРїР°", "РµРґРёРЅРёС†Р°", "_kind"]].to_csv(index=False).encode("utf-8")
params_sig = hashlib.sha1(_sig_src).hexdigest()[:10]
def _migrate_df_params_edit(prev_df: Any, new_df: pd.DataFrame) -> pd.DataFrame:
    """РњСЏРіРєР°СЏ РјРёРіСЂР°С†РёСЏ С‚Р°Р±Р»РёС†С‹ РїР°СЂР°РјРµС‚СЂРѕРІ РїСЂРё РёР·РјРµРЅРµРЅРёРё РјРµС‚Р°РґР°РЅРЅС‹С… (РµРґРёРЅРёС†С‹/kind/РіСЂСѓРїРїС‹).

    РўСЂРµР±РѕРІР°РЅРёРµ РїСЂРѕРµРєС‚Р°: РІРІРµРґС‘РЅРЅС‹Рµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј Р·РЅР°С‡РµРЅРёСЏ РќР• РґРѕР»Р¶РЅС‹ РїСЂРѕРїР°РґР°С‚СЊ РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РІРµСЂСЃРёРё.
    Р›РѕРіРёРєР°:
      1) Р±РµСЂС‘Рј СЃС‚Р°СЂРѕРµ UI-Р·РЅР°С‡РµРЅРёРµ + СЃС‚Р°СЂС‹Р№ kind -> РїРµСЂРµРІРѕРґРёРј РІ РЎР,
      2) РїРµСЂРµРІРѕРґРёРј РёР· РЎР РІ РЅРѕРІС‹Р№ UI-kind.
    """
    if not isinstance(prev_df, pd.DataFrame):
        return new_df
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

        # С„Р»Р°Рі РѕРїС‚РёРјРёР·Р°С†РёРё
        try:
            out.at[i, "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"] = bool(prow.get("РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", False))
        except Exception:
            pass

        # Р·РЅР°С‡РµРЅРёРµ
        try:
            v_old = float(prow.get("Р·РЅР°С‡РµРЅРёРµ"))
            v_si = _ui_to_si(str(k), v_old, old_kind)
            out.at[i, "Р·РЅР°С‡РµРЅРёРµ"] = _si_to_ui(str(k), v_si, new_kind)
        except Exception:
            pass

        # РґРёР°РїР°Р·РѕРЅС‹
        for col in ("РјРёРЅ", "РјР°РєСЃ"):
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


# --- РќРѕРІС‹Р№ СЂРµРґР°РєС‚РѕСЂ РїР°СЂР°РјРµС‚СЂРѕРІ: СЃРїРёСЃРѕРє + РєР°СЂС‚РѕС‡РєР° (Р±РµР· РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р°) ---
df_params_edit = st.session_state.get("df_params_edit", df_params0).copy()

# Р¤РёР»СЊС‚СЂС‹
_all_groups = sorted([str(g) for g in df_params_edit["РіСЂСѓРїРїР°"].dropna().unique().tolist() if str(g).strip()])

# Р‘С‹СЃС‚СЂС‹Р№ В«С‡РµР»РѕРІРµС‡РµСЃРєРёР№В» СЂР°Р·СЂРµР· РїРѕ СЂР°Р·РґРµР»Р°Рј (С‡С‚РѕР±С‹ РЅРµ РёСЃРєР°С‚СЊ РіР»Р°Р·Р°РјРё РїРѕ СЃРѕС‚РЅРµ СЃС‚СЂРѕРє).
_SECTION_RULES = {
    "Р’СЃРµ СЂР°Р·РґРµР»С‹": lambda g: True,
    "РџРЅРµРІРјР°С‚РёРєР°": lambda g: any(s in g for s in ["Р”Р°РІР»РµРЅРёРµ", "РћР±СЉС‘Рј", "РћР±СЉРµРј", "Р”СЂРѕСЃСЃРµР»", "Р“Р°Р·", "РЎСЂРµРґР°"]),
    "Р“РµРѕРјРµС‚СЂРёСЏ": lambda g: "Р“РµРѕРјРµС‚СЂРёСЏ" in g,
    "РњР°СЃСЃС‹ Рё РёРЅРµСЂС†РёРё": lambda g: any(s in g for s in ["РњРµС…Р°РЅРёРєР°", "РРЅРµСЂС†РёСЏ"]),
    "РЁРёРЅС‹": lambda g: "РЁРёРЅР°" in g,
    "РџСЂСѓР¶РёРЅР°": lambda g: "РџСЂСѓР¶РёРЅР°" in g,
    "РћРіСЂР°РЅРёС‡РµРЅРёСЏ": lambda g: "РћРіСЂР°РЅРёС‡" in g,
    "РџСЂРѕС‡РµРµ": lambda g: True,  # РІС‹С‡РёСЃР»РёРј РЅРёР¶Рµ
}

# РЎРїРёСЃРѕРє В«РїСЂРѕС‡РµРµВ» = РІСЃС‘, С‡С‚Рѕ РЅРµ РїРѕРїР°Р»Рѕ РІ РѕСЃРЅРѕРІРЅС‹Рµ СЂР°Р·РґРµР»С‹ (РєСЂРѕРјРµ "Р’СЃРµ СЂР°Р·РґРµР»С‹")
_non_misc_rules = {k: v for k, v in _SECTION_RULES.items() if k not in {"Р’СЃРµ СЂР°Р·РґРµР»С‹", "РџСЂРѕС‡РµРµ"}}
_groups_misc = [
    g for g in _all_groups
    if not any(rule(g) for rule in _non_misc_rules.values())
]

_section_opts = list(_SECTION_RULES.keys())
_default_section = st.session_state.get("ui_params_section", "Р’СЃРµ СЂР°Р·РґРµР»С‹")
if _default_section not in _section_opts:
    _default_section = "Р’СЃРµ СЂР°Р·РґРµР»С‹"

ui_params_section = st.selectbox(
    "Р Р°Р·РґРµР» РёСЃС…РѕРґРЅС‹С… РґР°РЅРЅС‹С…",
    options=_section_opts,
    index=_section_opts.index(_default_section),
    key="ui_params_section",
    help="РЎСѓР¶Р°РµС‚ СЃРїРёСЃРѕРє РіСЂСѓРїРї РїР°СЂР°РјРµС‚СЂРѕРІ РґРѕ РІС‹Р±СЂР°РЅРЅРѕРіРѕ СЂР°Р·РґРµР»Р° (РіРµРѕРјРµС‚СЂРёСЏ/РїРЅРµРІРјР°С‚РёРєР°/РјР°СЃСЃС‹ Рё С‚.Рґ.).",
)

if ui_params_section == "РџСЂРѕС‡РµРµ":
    _groups_in_section = _groups_misc
else:
    _rule = _SECTION_RULES.get(ui_params_section, lambda g: True)
    _groups_in_section = [g for g in _all_groups if _rule(g)]

_group_opts = ["Р’СЃРµ РіСЂСѓРїРїС‹"] + list(_groups_in_section)

_default_group = st.session_state.get("ui_params_group", "Р’СЃРµ РіСЂСѓРїРїС‹")
if _default_group not in _group_opts:
    _default_group = "Р’СЃРµ РіСЂСѓРїРїС‹"

ui_params_group = st.selectbox(
    "Р“СЂСѓРїРїР° РїР°СЂР°РјРµС‚СЂРѕРІ",
    options=_group_opts,
    index=_group_opts.index(_default_group),
    key="ui_params_group",
    help="РџР°СЂР°РјРµС‚СЂС‹ СЃРіСЂСѓРїРїРёСЂРѕРІР°РЅС‹ РїРѕ СЃРјС‹СЃР»Сѓ: РіРµРѕРјРµС‚СЂРёСЏ, РїРЅРµРІРјР°С‚РёРєР°, РјР°СЃСЃС‹ Рё С‚.Рґ.",
)

ui_params_search = st.text_input(
    "РџРѕРёСЃРє РїР°СЂР°РјРµС‚СЂР°",
    value=st.session_state.get("ui_params_search", ""),
    key="ui_params_search",
    help="РС‰РµС‚ РїРѕ РєР»СЋС‡Сѓ РїР°СЂР°РјРµС‚СЂР° Рё РїРѕ РїРѕСЏСЃРЅРµРЅРёСЋ.",
).strip()

# РћС‚С„РёР»СЊС‚СЂРѕРІР°РЅРЅС‹Р№ СЃРїРёСЃРѕРє
_df_view = df_params_edit.copy()
if ui_params_section != "Р’СЃРµ СЂР°Р·РґРµР»С‹":
    _df_view = _df_view[_df_view["РіСЂСѓРїРїР°"].isin(_groups_in_section)]
if ui_params_group != "Р’СЃРµ РіСЂСѓРїРїС‹":
    _df_view = _df_view[_df_view["РіСЂСѓРїРїР°"] == ui_params_group]
if ui_params_search:
    _mask = (
        _df_view["РїР°СЂР°РјРµС‚СЂ"].astype(str).str.contains(ui_params_search, case=False, na=False)
        | _df_view["РїРѕСЏСЃРЅРµРЅРёРµ"].astype(str).str.contains(ui_params_search, case=False, na=False)
    )
    _df_view = _df_view[_mask]

_keys_order = _df_view["_key"].tolist()

if not _keys_order:
    st.warning("РџР°СЂР°РјРµС‚СЂРѕРІ РїРѕ С‚РµРєСѓС‰РµРјСѓ С„РёР»СЊС‚СЂСѓ РЅРµС‚.")
else:
    # Р“СЂСѓРїРїРѕРІС‹Рµ РґРµР№СЃС‚РІРёСЏ
    c_act1, c_act2, c_act3 = st.columns([1, 1, 1], gap="small")
    with c_act1:
        if st.button("РћРїС‚. РІСЃРµ", width="stretch", help="РџРѕРјРµС‡Р°РµС‚ РІСЃРµ РїР°СЂР°РјРµС‚СЂС‹ РёР· СЃРїРёСЃРєР° РєР°Рє РѕРїС‚РёРјРёР·РёСЂСѓРµРјС‹Рµ"):
            _mask_all = df_params_edit["_key"].isin(_keys_order)
            df_params_edit.loc[_mask_all, "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"] = True

    with c_act2:
        if st.button("РЎРЅСЏС‚СЊ РѕРїС‚.", width="stretch", help="РЎРЅРёРјР°РµС‚ РѕРїС‚РёРјРёР·Р°С†РёСЋ Сѓ РїР°СЂР°РјРµС‚СЂРѕРІ РёР· СЃРїРёСЃРєР°"):
            _mask_all = df_params_edit["_key"].isin(_keys_order)
            df_params_edit.loc[_mask_all, "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"] = False

    with c_act3:
        if st.button("РђРІС‚РѕРґРёР°РїР°Р·РѕРЅ В±20%", width="stretch", help="Р—Р°РїРѕР»РЅСЏРµС‚ РњРёРЅ/РњР°РєСЃ (РµСЃР»Рё РїСѓСЃС‚Рѕ) Рё РІРєР»СЋС‡Р°РµС‚ РѕРїС‚РёРјРёР·Р°С†РёСЋ"):
            for _k in _keys_order:
                _row = df_params_edit[df_params_edit["_key"] == _k].iloc[0]
                try:
                    _v = float(_row["Р·РЅР°С‡РµРЅРёРµ"])
                except Exception:
                    continue

                _mn = _row.get("РјРёРЅ")
                _mx = _row.get("РјР°РєСЃ")
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

                    df_params_edit.loc[df_params_edit["_key"] == _k, "РјРёРЅ"] = float(min(lo, hi))
                    df_params_edit.loc[df_params_edit["_key"] == _k, "РјР°РєСЃ"] = float(max(lo, hi))

            df_params_edit.loc[df_params_edit["_key"].isin(_keys_order), "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"] = True

    # Р‘С‹СЃС‚СЂРѕРµ РјР°СЃСЃРѕРІРѕРµ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ (Р±РµР· В«РјРёР»Р»РёРѕРЅР°В» РєР°СЂС‚РѕС‡РµРє)
    with st.expander("РњР°СЃСЃРѕРІРѕРµ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ (С‚Р°Р±Р»РёС†Р°)", expanded=True):
        st.caption("Р”Р»СЏ Р±С‹СЃС‚СЂРѕР№ РїСЂР°РІРєРё РЅРµСЃРєРѕР»СЊРєРёС… РїР°СЂР°РјРµС‚СЂРѕРІ. "
                   "Р—РґРµСЃСЊ СЂРµРґР°РєС‚РёСЂСѓСЋС‚СЃСЏ С‚РѕР»СЊРєРѕ Р·РЅР°С‡РµРЅРёСЏ/РґРёР°РїР°Р·РѕРЅС‹; РїРѕСЏСЃРЅРµРЅРёРµ СЃРјРѕС‚СЂРёС‚Рµ РІ РєР°СЂС‚РѕС‡РєРµ СЃРїСЂР°РІР°.")
        try:
            _mass_df = _df_view.set_index("_key")[["РїР°СЂР°РјРµС‚СЂ", "РµРґРёРЅРёС†Р°", "Р·РЅР°С‡РµРЅРёРµ", "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", "РјРёРЅ", "РјР°РєСЃ"]].copy()
            _flt_sig = hashlib.sha1(f"{ui_params_section}|{ui_params_group}|{ui_params_search}".encode("utf-8")).hexdigest()[:6]
            _mass_key = f"{params_table_key}_mass_{_flt_sig}"
            _mass_edited = st.data_editor(
                _mass_df,
                key=_mass_key,
                hide_index=True,
                width="stretch",
                height=280,
                num_rows="fixed",
                disabled=["РїР°СЂР°РјРµС‚СЂ", "РµРґРёРЅРёС†Р°"],
            )

            # РїСЂРёРјРµРЅСЏРµРј РёР·РјРµРЅРµРЅРёСЏ РѕР±СЂР°С‚РЅРѕ РІ РѕР±С‰СѓСЋ С‚Р°Р±Р»РёС†Сѓ
            _idx = df_params_edit.set_index("_key")
            for _col in ["Р·РЅР°С‡РµРЅРёРµ", "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", "РјРёРЅ", "РјР°РєСЃ"]:
                if _col in _mass_edited.columns:
                    _idx.loc[_mass_edited.index, _col] = _mass_edited[_col].values
            df_params_edit = _idx.reset_index()
        except Exception as _e:
            st.warning(f"РњР°СЃСЃРѕРІС‹Р№ СЂРµРґР°РєС‚РѕСЂ РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ: {_e}")


    left, right = st.columns([1.05, 1.0], gap="large")

    with left:
        st.caption("РЎРїРёСЃРѕРє РїР°СЂР°РјРµС‚СЂРѕРІ (Р±РµР· РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р°). Р’С‹Р±РµСЂРё СЃС‚СЂРѕРєСѓ в†’ СЃРїСЂР°РІР° РєР°СЂС‚РѕС‡РєР°.")
        _list_df = _df_view[["РїР°СЂР°РјРµС‚СЂ", "Р·РЅР°С‡РµРЅРёРµ", "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"]].copy()
        _list_df = _list_df.rename(columns={"РїР°СЂР°РјРµС‚СЂ": "РџР°СЂР°РјРµС‚СЂ", "Р·РЅР°С‡РµРЅРёРµ": "Р—РЅР°С‡РµРЅРёРµ", "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ": "РћРїС‚."})

        # Р’С‹Р±РѕСЂ РїР°СЂР°РјРµС‚СЂР° С‡РµСЂРµР· selectbox (СѓСЃС‚СЂР°РЅСЏРµС‚ Р±Р°РіРё selection/rerun Рё В«РґРІРѕР№РЅРѕР№ РєР»РёРєВ»)
        _label_map = dict(zip(_df_view["_key"].astype(str).tolist(), _df_view["РїР°СЂР°РјРµС‚СЂ"].astype(str).tolist()))
        _cur_key = str(st.session_state.get("ui_params_selected_key") or "")
        if _cur_key not in _keys_order:
            _cur_key = _keys_order[0]
            st.session_state["ui_params_selected_key"] = _cur_key

        st.selectbox(
            "Р’С‹Р±СЂР°РЅРЅС‹Р№ РїР°СЂР°РјРµС‚СЂ",
            options=_keys_order,
            index=_keys_order.index(_cur_key) if _cur_key in _keys_order else 0,
            format_func=lambda k: _label_map.get(str(k), str(k)),
            key="ui_params_selected_key",
            help="Р’С‹Р±РѕСЂ РїР°СЂР°РјРµС‚СЂР° РґР»СЏ РєР°СЂС‚РѕС‡РєРё СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ СЃРїСЂР°РІР°.",
        )

        st.dataframe(
            _list_df,
            hide_index=True,
            width="stretch",
            height=420,
        )

    # Р’РђР–РќРћ (Streamlit): РЅРµР»СЊР·СЏ РјРѕРґРёС„РёС†РёСЂРѕРІР°С‚СЊ st.session_state[<widget_key>] РїРѕСЃР»Рµ
    # СЃРѕР·РґР°РЅРёСЏ РІРёРґР¶РµС‚Р° СЃ С‚РµРј Р¶Рµ key РІ СЂР°РјРєР°С… РѕРґРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°.
    # РџРѕСЌС‚РѕРјСѓ Р·РґРµСЃСЊ РјС‹ С‚РѕР»СЊРєРѕ С‡РёС‚Р°РµРј РёС‚РѕРіРѕРІРѕРµ Р·РЅР°С‡РµРЅРёРµ.
    _selected_key = st.session_state.get("ui_params_selected_key")
    if _selected_key not in _keys_order:
        _selected_key = _keys_order[0]

    with right:
        _row = df_params_edit[df_params_edit["_key"] == _selected_key].iloc[0]
        _pkey = str(_row["РїР°СЂР°РјРµС‚СЂ"])
        _unit = str(_row.get("РµРґРёРЅРёС†Р°", "вЂ”"))
        _kind = str(_row.get("_kind", "raw"))

        st.markdown(f"### {_pkey}")
        if str(_row.get("РїРѕСЏСЃРЅРµРЅРёРµ", "")).strip():
            st.info(str(_row.get("РїРѕСЏСЃРЅРµРЅРёРµ", "")))

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

        v0 = _sf(_row.get("Р·РЅР°С‡РµРЅРёРµ"), 0.0)
        opt0 = bool(_row.get("РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", False))
        mn0 = _sf(_row.get("РјРёРЅ"), None)
        mx0 = _sf(_row.get("РјР°РєСЃ"), None)

        nonneg = (_kind in {"pressure_atm_g", "pressure_bar_g", "volume_L", "volume_mL"}) or _pkey.startswith("РјР°СЃСЃР°_")

        with st.form(f"param_card_{_selected_key}"):
            st.caption(f"Р•РґРёРЅРёС†С‹: **{_unit}**")

            # Р”РёР°РїР°Р·РѕРЅ РґР»СЏ СЂСѓС‡РєРё Р·РЅР°С‡РµРЅРёСЏ
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

            val_new = st.slider("Р—РЅР°С‡РµРЅРёРµ", float(lo_b), float(hi_b), float(max(lo_b, min(hi_b, v0))), step=float(step))

            with st.expander("РўРѕС‡РЅРѕ (РІРІРѕРґ)", expanded=True):
                val_new = st.number_input(
                    "Р—РЅР°С‡РµРЅРёРµ (С‚РѕС‡РЅРѕ)",
                    value=float(val_new),
                    step=float(abs(float(val_new)) * 0.01) if float(val_new) != 0 else 0.1,
                    format="%.8g",
                )

            opt_new = st.checkbox(
                "РћРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ",
                value=opt0,
                help="Р•СЃР»Рё РІРєР»СЋС‡РµРЅРѕ вЂ” РїР°СЂР°РјРµС‚СЂ СѓС‡Р°СЃС‚РІСѓРµС‚ РІ РѕРїС‚РёРјРёР·Р°С†РёРё РІРЅСѓС‚СЂРё Р·Р°РґР°РЅРЅРѕРіРѕ РґРёР°РїР°Р·РѕРЅР°.",
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
                    min_new, max_new = st.slider("Р”РёР°РїР°Р·РѕРЅ", 0.0, 1.0, value=(cur_lo, cur_hi), step=0.01)
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
                        "Р”РёР°РїР°Р·РѕРЅ",
                        float(rmin),
                        float(rmax),
                        value=(float(cur_lo), float(cur_hi)),
                        step=float(rstep),
                    )

            submitted = st.form_submit_button("РџСЂРёРјРµРЅРёС‚СЊ РёР·РјРµРЅРµРЅРёСЏ")
            if submitted:
                df_params_edit.loc[df_params_edit["_key"] == _selected_key, "Р·РЅР°С‡РµРЅРёРµ"] = float(val_new)
                df_params_edit.loc[df_params_edit["_key"] == _selected_key, "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"] = bool(opt_new)
                if opt_new:
                    df_params_edit.loc[df_params_edit["_key"] == _selected_key, "РјРёРЅ"] = float(min_new)
                    df_params_edit.loc[df_params_edit["_key"] == _selected_key, "РјР°РєСЃ"] = float(max_new)

                st.session_state["df_params_edit"] = df_params_edit
                st.success("РџР°СЂР°РјРµС‚СЂ РѕР±РЅРѕРІР»С‘РЅ.")

# СЃРѕС…СЂР°РЅРёС‚СЊ РІ session_state (РЅР° СЃР»СѓС‡Р°Р№, РµСЃР»Рё РЅРµ РЅР°Р¶РёРјР°Р»Рё РєРЅРѕРїРєСѓ)
st.session_state["df_params_edit"] = df_params_edit

# СЃС‚СЂРѕРёРј base_override / ranges_override РёР· РµРґРёРЅРѕР№ С‚Р°Р±Р»РёС†С‹
base_override = dict(base0)
ranges_override: Dict[str, Tuple[float, float]] = {}

param_errors = []
for _, r in df_params_edit.iterrows():
    k = str(r["_key"])
    kind = str(r["_kind"])
    try:
        val_ui = float(r["Р·РЅР°С‡РµРЅРёРµ"])
    except Exception:
        param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РїСѓСЃС‚РѕРµ/РЅРµРєРѕСЂСЂРµРєС‚РЅРѕРµ Р±Р°Р·РѕРІРѕРµ Р·РЅР°С‡РµРЅРёРµ.")
        continue

    # С„РёР·РёС‡РµСЃРєРёРµ РїСЂРѕРІРµСЂРєРё (С‚РѕР»СЊРєРѕ РЅРµРІРѕР·РјРѕР¶РЅРѕРµ)
    if kind == "fraction01":
        if not (0.0 <= val_ui <= 1.0):
            param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РґРѕР»СЏ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ 0..1, СЃРµР№С‡Р°СЃ {val_ui}")
    if k.startswith("РјР°СЃСЃР°_") and val_ui < 0:
        param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РјР°СЃСЃР° РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РѕС‚СЂРёС†Р°С‚РµР»СЊРЅРѕР№, СЃРµР№С‡Р°СЃ {val_ui}")
    if ("РѕР±СЉС‘Рј" in k) and (("volume_" in kind) or k.startswith("РѕР±СЉС‘Рј_") or k.startswith("РјС‘СЂС‚РІС‹Р№_РѕР±СЉС‘Рј")):
        if val_ui <= 0:
            param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РѕР±СЉС‘Рј РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ > 0, СЃРµР№С‡Р°СЃ {val_ui}")

    # РєРѕРЅРІРµСЂС‚Р°С†РёСЏ РІ РЎР
    val_si = _ui_to_si(k, val_ui, kind)
    base_override[k] = float(val_si)

    if bool(r["РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"]):
        try:
            mn_ui = float(r["РјРёРЅ"])
            mx_ui = float(r["РјР°РєСЃ"])
        except Exception:
            param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РІРєР»СЋС‡РµРЅР° РѕРїС‚РёРјРёР·Р°С†РёСЏ, РЅРѕ РґРёР°РїР°Р·РѕРЅ (РјРёРЅ/РјР°РєСЃ) РЅРµ Р·Р°РґР°РЅ.")
            continue
        mn_si = _ui_to_si(k, mn_ui, kind)
        mx_si = _ui_to_si(k, mx_ui, kind)
        if not (mn_si < mx_si):
            param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РґРёР°РїР°Р·РѕРЅ РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ (РјРёРЅ >= РјР°РєСЃ).")
            continue
        # С„РёР·РёРєР°
        if kind == "fraction01" and (mn_ui < 0 or mx_ui > 1):
            param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РґРёР°РїР°Р·РѕРЅ РґРѕР»Рё РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ 0..1.")
            continue
        if ("РѕР±СЉС‘Рј" in k) and ((mn_si <= 0) or (mx_si <= 0)):
            param_errors.append(f"РџР°СЂР°РјРµС‚СЂ '{k}': РѕР±СЉС‘РјС‹ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ > 0.")
            continue

        ranges_override[k] = (float(mn_si), float(mx_si))

if param_errors:
    st.error("Р’ С‚Р°Р±Р»РёС†Рµ РїР°СЂР°РјРµС‚СЂРѕРІ РµСЃС‚СЊ РѕС€РёР±РєРё (РёСЃРїСЂР°РІСЊС‚Рµ РїРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј):\n- " + "\n- ".join(param_errors))





# -------------------------------
# Р РµР¶РёРјС‹ Рё С„Р»Р°РіРё (РЅРµС‡РёСЃР»РѕРІС‹Рµ РїР°СЂР°РјРµС‚СЂС‹)
# -------------------------------
st.subheader("Р РµР¶РёРјС‹ Рё С„Р»Р°РіРё")
st.caption(
    "Р­С‚Рё РїР°СЂР°РјРµС‚СЂС‹ РЅРµ СЏРІР»СЏСЋС‚СЃСЏ С‡РёСЃР»Р°РјРё (СЃС‚СЂРѕРєРё/Р±СѓР»РµРІС‹ С„Р»Р°РіРё), РїРѕСЌС‚РѕРјСѓ РѕРЅРё РЅРµ РїРѕРїР°РґР°СЋС‚ РІ С‚Р°Р±Р»РёС†Сѓ С‡РёСЃР»РѕРІС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ РІС‹С€Рµ. "
    "Р—РґРµСЃСЊ РёС… РјРѕР¶РЅРѕ РјРµРЅСЏС‚СЊ Р±РµР· СЂСѓС‡РЅРѕР№ РїСЂР°РІРєРё JSON."
)

# Р¤Р»Р°РіРё (bool)
def _is_bool_like(k, v) -> bool:
    # РќРѕСЂРјР°Р»СЊРЅС‹Р№ СЃР»СѓС‡Р°Р№: РІ JSON true/false -> bool
    if isinstance(v, (bool, np.bool_)):
        return True
    # РРЅРѕРіРґР° С„Р»Р°Рі РјРѕР¶РµС‚ Р±С‹С‚СЊ РїСЂРµРґСЃС‚Р°РІР»РµРЅ РєР°Рє 0/1 (РїРѕСЃР»Рµ РІРЅРµС€РЅРµР№ РєРѕРЅРІРµСЂСЃРёРё/СЌРєСЃРїРѕСЂС‚Р°).
    # Р’Р°Р¶РЅРѕ: РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂСЏРјРѕ РїРѕРїСЂРѕСЃРёР» "РїСЂРѕРІРµСЂСЊ С‡С‚Рѕ РІСЃРµ Р±СѓР»РµРІС‹ РІС‹РЅРµСЃРµРЅС‹" вЂ” РїРѕСЌС‚РѕРјСѓ Р±РµСЂС‘Рј 0/1 РєР°Рє bool Р±РµР· СЌРІСЂРёСЃС‚РёРє.
    if isinstance(v, int) and v in (0, 1):
        return True
    # РРЅРѕРіРґР° Р±С‹РІР°РµС‚ СЃС‚СЂРѕРєРѕР№ "true"/"false"/"0"/"1".
    if isinstance(v, str):
        vv = v.strip().lower()
        if vv in ("true", "false", "0", "1"):
            return True
    return False

bool_keys_ui = sorted(set([k for k, v in base_override.items() if _is_bool_like(k, v)]) | set(BASE_BOOL_KEYS))
if bool_keys_ui:
    with st.expander("Р¤Р»Р°РіРё (bool)", expanded=True):
        def _to_bool(v) -> bool:
            if isinstance(v, (bool, np.bool_)):
                return bool(v)
            if isinstance(v, int):
                return bool(v)
            if isinstance(v, str):
                vv = v.strip().lower()
                if vv in ("true", "1", "yes", "y", "РґР°"):
                    return True
                if vv in ("false", "0", "no", "n", "РЅРµС‚", ""):
                    return False
            return bool(v)

        cols = st.columns(2)
        for i, k in enumerate(bool_keys_ui):
            meta = PARAM_META.get(k, {"РѕРїРёСЃР°РЅРёРµ": ""})
            help_txt = meta.get("РѕРїРёСЃР°РЅРёРµ", "")
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
    st.info("Р’ Р±Р°Р·Рµ РЅРµС‚ Р±СѓР»РµРІС‹С… С„Р»Р°РіРѕРІ (bool).")

# Р РµР¶РёРјС‹ (string)
str_keys_ui = sorted([k for k, v in base_override.items() if isinstance(v, str)])

# Р”Р»СЏ РёР·РІРµСЃС‚РЅС‹С… РєР»СЋС‡РµР№ вЂ” Р·Р°РґР°С‘Рј Р±РµР·РѕРїР°СЃРЅС‹Рµ РІР°СЂРёР°РЅС‚С‹ (РєР°РЅРѕРЅРёС‡РµСЃРєРёРµ РёРјРµРЅР° РєР°Рє РІ РјРѕРґРµР»Рё).
STRING_OPTIONS = {
    "С‚РµСЂРјРѕРґРёРЅР°РјРёРєР°": ["isothermal", "adiabatic", "thermal"],
    "РіР°Р·_РјРѕРґРµР»СЊ_С‚РµРїР»РѕРµРјРєРѕСЃС‚Рё": ["constant", "nist_air"],
    "СЃС‚РµРЅРєР°_С‚РµСЂРјРѕРјРѕРґРµР»СЊ": ["fixed_ambient", "lumped"],
    "СЃС‚РµРЅРєР°_С„РѕСЂРјР°": ["sphere", "cylinder"],
    "СЃС‚РµРЅРєР°_h_РіР°Р·_СЂРµР¶РёРј": ["constant", "flow_dependent"],
    "РјРѕРґРµР»СЊ_РїР°СЃСЃРёРІРЅРѕРіРѕ_СЂР°СЃС…РѕРґР°": ["orifice", "iso6358"],

    # РњРµС…Р°РЅРёРєР°/РєРёРЅРµРјР°С‚РёРєР°
    "РјРµС…Р°РЅРёРєР°_РєРёРЅРµРјР°С‚РёРєР°": ["dw2d", "dw2d_mounts", "mr", "table"],
    "РєРѕР»РµСЃРѕ_РєРѕРѕСЂРґРёРЅР°С‚Р°": ["center", "contact"],
}
STRING_HELP = {
    "С‚РµСЂРјРѕРґРёРЅР°РјРёРєР°": "Р РµР¶РёРј РіР°Р·Р°: isothermal (РёР·РѕС‚РµСЂРјР°), adiabatic (Р°РґРёР°Р±Р°С‚Р°), thermal (С‚РµРїР»РѕРѕР±РјРµРЅ СЃ СѓС‡С‘С‚РѕРј СЃС‚РµРЅРєРё).",
    "РіР°Р·_РјРѕРґРµР»СЊ_С‚РµРїР»РѕРµРјРєРѕСЃС‚Рё": "РўРµРїР»РѕС‘РјРєРѕСЃС‚Рё РІРѕР·РґСѓС…Р°: constant (РїРѕСЃС‚РѕСЏРЅРЅС‹Рµ) РёР»Рё nist_air (T-Р·Р°РІРёСЃРёРјС‹Рµ, РїРѕР»СѓРёРґРµР°Р»СЊРЅС‹Р№ РіР°Р·).",
    "СЃС‚РµРЅРєР°_С‚РµСЂРјРѕРјРѕРґРµР»СЊ": "РњРѕРґРµР»СЊ СЃС‚РµРЅРєРё: fixed_ambient (СЃС‚РµРЅРєР° РІСЃРµРіРґР° = T_РѕРєСЂ, Р±С‹СЃС‚СЂРѕ) РёР»Рё lumped (С‚РµРјРїРµСЂР°С‚СѓСЂР° СЃС‚РµРЅРєРё РєР°Рє СЃРѕСЃС‚РѕСЏРЅРёРµ).",
    "СЃС‚РµРЅРєР°_С„РѕСЂРјР°": "Р“РµРѕРјРµС‚СЂРёСЏ РґР»СЏ auto-РѕС†РµРЅРєРё РїР»РѕС‰Р°РґРё СЃС‚РµРЅРєРё РёР· РѕР±СЉС‘РјР°: sphere (СЃС„РµСЂР°) РёР»Рё cylinder (С†РёР»РёРЅРґСЂ).",
    "СЃС‚РµРЅРєР°_h_РіР°Р·_СЂРµР¶РёРј": "РљРѕСЌС„С„РёС†РёРµРЅС‚ С‚РµРїР»РѕРѕС‚РґР°С‡Рё РіР°Р·в†”СЃС‚РµРЅРєР°: constant РёР»Рё flow_dependent (СѓСЃРёР»РµРЅРёРµ РїСЂРё Р±РѕР»СЊС€РёС… СЂР°СЃС…РѕРґР°С…).",
    "РјРѕРґРµР»СЊ_РїР°СЃСЃРёРІРЅРѕРіРѕ_СЂР°СЃС…РѕРґР°": "РњРѕРґРµР»СЊ РїР°СЃСЃРёРІРЅС‹С… СЃРѕРїСЂРѕС‚РёРІР»РµРЅРёР№/РґСЂРѕСЃСЃРµР»РµР№: orifice (Cd*A) РёР»Рё iso6358 (C,b,m).",
    "РїР°СЃРїРѕСЂС‚_РєРѕРјРїРѕРЅРµРЅС‚РѕРІ_json": "РџСѓС‚СЊ Рє JSON-РїР°СЃРїРѕСЂС‚Сѓ РєРѕРјРїРѕРЅРµРЅС‚РѕРІ (Camozzi Рё РґСЂ.) РґР»СЏ Р°РІС‚РѕРїРѕРґСЃС‚Р°РЅРѕРІРєРё РїР°СЂР°РјРµС‚СЂРѕРІ.",

    # РњРµС…Р°РЅРёРєР°/РєРёРЅРµРјР°С‚РёРєР°
    "РјРµС…Р°РЅРёРєР°_РєРёРЅРµРјР°С‚РёРєР°": "РљРёРЅРµРјР°С‚РёРєР° РїРѕРґРІРµСЃРєРё: mr (РїРѕСЃС‚РѕСЏРЅРЅРѕРµ РїРµСЂРµРґР°С‚РѕС‡РЅРѕРµ), table (С‚Р°Р±Р»РёС†Р° dwв†’drod), dw2d/dw2d_mounts (РіРµРѕРјРµС‚СЂРёСЏ РєСЂРµРїР»РµРЅРёР№ РЅР° РЅРёР¶РЅРµРј СЂС‹С‡Р°РіРµ).",
    "РєРѕР»РµСЃРѕ_РєРѕРѕСЂРґРёРЅР°С‚Р°": "РљР°Рє РёРЅС‚РµСЂРїСЂРµС‚РёСЂСѓРµС‚СЃСЏ zw: center = РєРѕРѕСЂРґРёРЅР°С‚Р° С†РµРЅС‚СЂР° РєРѕР»РµСЃР°; contact = РєРѕРѕСЂРґРёРЅР°С‚Р° РїСЏС‚РЅР° РєРѕРЅС‚Р°РєС‚Р° (С†РµРЅС‚СЂ = zw + R).",
}

if str_keys_ui:
    with st.expander("Р РµР¶РёРјС‹ (string)", expanded=True):
        # Р”РµР»Р°РµРј Р±РѕР»РµРµ РєРѕРјРїР°РєС‚РЅС‹Р№ Рё СѓРґРѕР±РЅС‹Р№ РјР°РєРµС‚: 2 РєРѕР»РѕРЅРєРё РІРјРµСЃС‚Рѕ "РЅР° РІСЃСЋ С€РёСЂРёРЅСѓ"
        cols_modes = st.columns(2, gap="large")

        for i, k in enumerate(str_keys_ui):
            with cols_modes[i % 2]:
                cur = str(base_override.get(k, ""))
                help_txt = STRING_HELP.get(k, "")

                # 1) РР·РІРµСЃС‚РЅС‹Рµ СЂРµР¶РёРјС‹ вЂ” selectbox
                if k in STRING_OPTIONS:
                    opts = list(STRING_OPTIONS[k])
                    if cur not in opts:
                        # РµСЃР»Рё РІ Р±Р°Р·Рµ Р±С‹Р»Рѕ С‡С‚Рѕ-С‚Рѕ РЅРµСЃС‚Р°РЅРґР°СЂС‚РЅРѕРµ вЂ” РїРѕРєР°Р·С‹РІР°РµРј РµРіРѕ РїРµСЂРІС‹Рј, С‡С‚РѕР±С‹ РЅРµ РїРѕС‚РµСЂСЏС‚СЊ
                        opts = [cur] + [o for o in opts if o != cur]
                    base_override[k] = st.selectbox(
                        k,
                        options=opts,
                        index=opts.index(cur) if cur in opts else 0,
                        help=help_txt if help_txt else None,
                        key=f"mode__{k}",
                    )

                    # DW2D geometry is configured on a dedicated page.
                    # (User request: "СЏ РЅРµ РЅР°С€С‘Р» РіРґРµ Р·Р°РґР°С‘С‚СЃСЏ РіРµРѕРјРµС‚СЂРёСЏ")
                    if k == "РјРµС…Р°РЅРёРєР°_РєРёРЅРµРјР°С‚РёРєР°":
                        _kin = str(base_override.get(k, "") or "")
                        if _kin in ("dw2d", "dw2d_mounts"):
                            st.caption(
                                "DW2D: РіРµРѕРјРµС‚СЂРёСЏ РєСЂРµРїР»РµРЅРёР№ Р·Р°РґР°С‘С‚СЃСЏ РЅР° СЃС‚СЂР°РЅРёС†Рµ В«Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)В» "
                                "(РјРµРЅСЋ СЃР»РµРІР° в†’ РџСЂРѕРІРµСЂРєРё Рё РЅР°СЃС‚СЂРѕР№РєР°)."
                            )
                            if hasattr(st, "switch_page"):
                                if st.button(
                                    "РћС‚РєСЂС‹С‚СЊ СЃС‚СЂР°РЅРёС†Сѓ РіРµРѕРјРµС‚СЂРёРё DW2D",
                                    key="go_dw2d_geometry",
                                    help="РџРµСЂРµР№С‚Рё Рє РІРІРѕРґСѓ РіРµРѕРјРµС‚СЂРёРё РЅРёР¶РЅРµРіРѕ СЂС‹С‡Р°РіР° Рё РєСЂРµРїР»РµРЅРёР№ С†РёР»РёРЅРґСЂР°",
                                ):
                                    try:
                                        st.switch_page("pneumo_solver_ui/pages/10_SuspensionGeometry.py")
                                    except Exception:
                                        pass
                            else:
                                st.info("РћС‚РєСЂРѕР№С‚Рµ: РјРµРЅСЋ СЃР»РµРІР° в†’ РџСЂРѕРІРµСЂРєРё Рё РЅР°СЃС‚СЂРѕР№РєР° в†’ Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D).")

                    continue

                # 2) РџР°СЃРїРѕСЂС‚ РєРѕРјРїРѕРЅРµРЅС‚РѕРІ вЂ” selectbox РїРѕ json РІ РїР°РїРєРµ + СЂСѓС‡РЅРѕР№ РІРІРѕРґ
                if k == "РїР°СЃРїРѕСЂС‚_РєРѕРјРїРѕРЅРµРЅС‚РѕРІ_json":
                    # РЎРєР°РЅРёСЂСѓРµРј JSON РІ РїР°РїРєРµ РїСЂРёР»РѕР¶РµРЅРёСЏ (РіРґРµ Р»РµР¶РёС‚ pneumo_ui_app.py)
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
                            "(РёР»Рё РІРІРµРґРёС‚Рµ РІСЂСѓС‡РЅСѓСЋ)",
                            value=str(base_override.get(k, cur)),
                            key=f"mode__{k}__manual",
                            help="Р•СЃР»Рё С…РѕС‚РёС‚Рµ СѓРєР°Р·Р°С‚СЊ РїСѓС‚СЊ/РёРјСЏ С„Р°Р№Р»Р° РІСЂСѓС‡РЅСѓСЋ вЂ” РїСЂРѕСЃС‚Рѕ РІРїРёС€РёС‚Рµ С‚СѓС‚ Рё РѕРЅРѕ Р±СѓРґРµС‚ РёСЃРїРѕР»СЊР·РѕРІР°РЅРѕ.",
                        )
                        # РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РІРІРѕРґРёС‚ РІСЂСѓС‡РЅСѓСЋ вЂ” РїСЂРёРѕСЂРёС‚РµС‚ СЂСѓС‡РЅРѕРіРѕ
                        manual_v = st.session_state.get(f"mode__{k}__manual", "").strip()
                        if manual_v:
                            base_override[k] = manual_v
                    continue

                # 3) РџСЂРѕС‡РёРµ СЃС‚СЂРѕРєРё вЂ” text_input
                base_override[k] = st.text_input(
                    k,
                    value=cur,
                    help=help_txt if help_txt else None,
                    key=f"mode__{k}",
                )
else:
    st.info("Р’ Р±Р°Р·Рµ РЅРµС‚ СЃС‚СЂРѕРєРѕРІС‹С… СЂРµР¶РёРјРѕРІ (string).")

# -------------------------------
# РўРµСЃС‚-РЅР°Р±РѕСЂ Рё РїРѕСЂРѕРіРё (СЂРµРґР°РєС‚РёСЂСѓРµС‚СЃСЏ РёР· UI)
# -------------------------------
st.subheader("РўРµСЃС‚-РЅР°Р±РѕСЂ Рё РїРѕСЂРѕРіРё")
st.caption(
    "Р—РґРµСЃСЊ Р·Р°РґР°СЋС‚СЃСЏ РїР°СЂР°РјРµС‚СЂС‹ С‚РµСЃС‚РѕРІ Рё С†РµР»РµРІС‹Рµ Р·Р°РїР°СЃС‹/РѕРіСЂР°РЅРёС‡РµРЅРёСЏ. "
    "Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ вЂ” С‚РѕР»СЊРєРѕ РІ UI (С„Р°Р№Р»С‹ РІСЂСѓС‡РЅСѓСЋ РїСЂР°РІРёС‚СЊ РЅРµ РЅСѓР¶РЅРѕ)."
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

    ABSOLUTE LAW (СЃРј. 00_READ_FIRST__ABSOLUTE_LAW.md):

    * РќРёРєР°РєРёС… РґСѓР±Р»РµР№/Р°Р»РёР°СЃРѕРІ РєРѕР»РѕРЅРѕРє РІРЅСѓС‚СЂРё suite.
    * Р’РЅСѓС‚СЂРё РїСЂРёР»РѕР¶РµРЅРёСЏ РёСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ **С‚РѕР»СЊРєРѕ РєР°РЅРѕРЅРёС‡РµСЃРєРёРµ** РёРјРµРЅР° РєРѕР»РѕРЅРѕРє.

    Р”РѕРїСѓСЃРєР°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ СЏРІРЅР°СЏ РѕРґРЅРѕСЂР°Р·РѕРІР°СЏ РјРёРіСЂР°С†РёСЏ legacy-РєРѕР»РѕРЅРѕРє РЅР° РІС…РѕРґРµ
    (РїСЂРё Р·Р°РіСЂСѓР·РєРµ/РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРё suite) СЃ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рј warning/logging.
    Р­С‚Рѕ РЅРµ runtime-РјРѕСЃС‚ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё: legacy-РєРѕР»РѕРЅРєРё РЅРµРјРµРґР»РµРЅРЅРѕ СѓРґР°Р»СЏСЋС‚СЃСЏ
    РёР· editor state.
    Р¤СѓРЅРєС†РёСЏ РѕР±СЏР·Р°РЅР° Р±С‹С‚СЊ Р±РµР·РѕРїР°СЃРЅРѕР№: РЅРёРєР°РєРёС… РїР°РґРµРЅРёР№ РёР·-Р·Р° РєСЂРёРІРѕРіРѕ С„Р°Р№Р»Р°.
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
        "РёРјСЏ": "",
        "С‚РёРї": "",
        "РІРєР»СЋС‡РµРЅ": True,
        "РєРѕРјРјРµРЅС‚Р°СЂРёР№": "",

        # Simulation controls
        "dt": 0.005,
        "t_end": 5.0,

        # World-road controls
        "auto_t_end_from_len": True,
        "road_len_m": 3000.0,
        "vx0_Рј_СЃ": 20.0 / 3.6,
        "road_csv": "",
        "axay_csv": "",
        "road_surface": "rough",
        "slope_deg": 0.0,

        # Optional tuning
        "track_m": float('nan'),
        "wheelbase_m": float('nan'),
        "yaw0_СЂР°Рґ": float('nan'),

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
        df["РІРєР»СЋС‡РµРЅ"] = df["РІРєР»СЋС‡РµРЅ"].astype(bool)
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

# Р·Р°РіСЂСѓР·РєР° suite РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ
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

# upload suite РёР· С„Р°Р№Р»Р°
colSU1, colSU2 = st.columns([1.2, 1.0], gap="large")
with colSU1:
    suite_upload = st.file_uploader("Р—Р°РіСЂСѓР·РёС‚СЊ С‚РµСЃС‚-РЅР°Р±РѕСЂ (JSON)", type=["json"], help="РњРѕР¶РЅРѕ Р·Р°РіСЂСѓР·РёС‚СЊ СЂР°РЅРµРµ СЃРѕС…СЂР°РЅС‘РЅРЅС‹Р№ suite.json")
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
                st.success("РўРµСЃС‚-РЅР°Р±РѕСЂ Р·Р°РіСЂСѓР¶РµРЅ.")
                try:
                    from pneumo_solver_ui.ui_persistence import autosave_now
                    autosave_now(st)
                except Exception:
                    pass
            else:
                st.error("suite.json РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃРїРёСЃРєРѕРј РѕР±СЉРµРєС‚РѕРІ (list[dict]).")
        except Exception as e:
            st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ JSON: {e}")

with colSU2:
    df_suite_export = st.session_state["df_suite_edit"].copy()
    # РЈР±РёСЂР°РµРј Р°РЅРіР»РѕСЏР·С‹С‡РЅС‹Рµ РґСѓР±Р»РёРєР°С‚С‹ РєРѕР»РѕРЅРѕРє (РµСЃР»Рё РїСЂРёС€Р»Рё РёР· СЃС‚Р°СЂРѕРіРѕ suite)
    for _c in ["name", "type", "enabled"]:
        if _c in df_suite_export.columns:
            df_suite_export = df_suite_export.drop(columns=[_c])

    # РќРµ СЌРєСЃРїРѕСЂС‚РёСЂСѓРµРј РїСѓСЃС‚С‹Рµ СЃС‚СЂРѕРєРё
    try:
        _name_ok = df_suite_export["РёРјСЏ"].notna() & (df_suite_export["РёРјСЏ"].astype(str).str.strip() != "")
        _type_ok = df_suite_export["С‚РёРї"].notna() & (df_suite_export["С‚РёРї"].astype(str).str.strip() != "")
        df_suite_export = df_suite_export[_name_ok & _type_ok]
    except Exception:
        pass

    suite_bytes = json.dumps(df_suite_export.to_dict(orient="records"), ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("РЎРєР°С‡Р°С‚СЊ С‚РµСЃС‚-РЅР°Р±РѕСЂ (JSON)", data=suite_bytes, file_name="suite.json", mime="application/json")


# --- РќРѕРІС‹Р№ СЂРµРґР°РєС‚РѕСЂ С‚РµСЃС‚-РЅР°Р±РѕСЂР°: СЃРїРёСЃРѕРє + РєР°СЂС‚РѕС‡РєР° (Р±РµР· РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р°) ---
# (С†РµР»СЊ: СѓР±СЂР°С‚СЊ С€РёСЂРѕРєРёРµ С‚Р°Р±Р»РёС†С‹, СЃРґРµР»Р°С‚СЊ СѓРїСЂР°РІР»РµРЅРёРµ С‚РµСЃС‚Р°РјРё В«РїРѕ-С‡РµР»РѕРІРµС‡РµСЃРєРёВ»)
df_suite_edit = st.session_state.get("df_suite_edit", pd.DataFrame([])).copy()
df_suite_edit = ensure_suite_columns(df_suite_edit, context="pneumo_ui_app.session_state_restore")

def _ensure_etalon_long_scenario_present(_df: pd.DataFrame) -> pd.DataFrame:
    """РњСЏРіРєР°СЏ РјРёРіСЂР°С†РёСЏ: РµСЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ Р·Р°РіСЂСѓР·РёР»/РІРѕСЃСЃС‚Р°РЅРѕРІРёР» СЃС‚Р°СЂС‹Р№ suite Р±РµР· СЌС‚Р°Р»РѕРЅРЅРѕРіРѕ РґР»РёРЅРЅРѕРіРѕ СЃС†РµРЅР°СЂРёСЏ,
    РґРѕР±Р°РІР»СЏРµРј РµРіРѕ (РІРєР»СЋС‡С‘РЅРЅС‹Рј РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ), С‡С‚РѕР±С‹ РѕРЅ РЅРµ В«СѓР±РµРіР°Р»В» РёР· РЅР°Р±РѕСЂР°."""
    try:
        if _df is None or _df.empty:
            return _df
        if ("РёРјСЏ" in _df.columns) and (_df["РёРјСЏ"].astype(str) == "РґР»РёРЅРЅС‹Р№_РіРѕСЂРѕРґ_РЅРµСЂРѕРІРЅР°СЏ_РґРѕСЂРѕРіР°_20РєРјС‡").any():
            return _df

        # Р±РµСЂС‘Рј С€Р°Р±Р»РѕРЅ РёР· default_suite.json
        _tmpl = None
        for _r in load_suite(DEFAULT_SUITE_PATH):
            if str(_r.get("РёРјСЏ", "")).strip() == "РґР»РёРЅРЅС‹Р№_РіРѕСЂРѕРґ_РЅРµСЂРѕРІРЅР°СЏ_РґРѕСЂРѕРіР°_20РєРјС‡":
                _tmpl = dict(_r)
                break
        if not _tmpl:
            return _df

        _tmpl["РІРєР»СЋС‡РµРЅ"] = True
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
        "Р’ suite РѕР±РЅР°СЂСѓР¶РµРЅС‹ legacy-РєРѕР»РѕРЅРєРё. Р’С‹РїРѕР»РЅРµРЅР° СЏРІРЅР°СЏ РјРёРіСЂР°С†РёСЏ РІ canonical schema; "
        "РїРµСЂРµСЃРѕС…СЂР°РЅРёС‚Рµ suite.json.\n- " + "\n- ".join(str(x) for x in _suite_contract_issues)
    )

def _new_test_row(preset: str = "worldroad_flat") -> dict:
    """Р“РµРЅРµСЂР°С‚РѕСЂ С€Р°Р±Р»РѕРЅРѕРІ С‚РµСЃС‚РѕРІ.

    Р’Р°Р¶РЅРѕ: РїРѕР»СЏ Р·РґРµСЃСЊ вЂ” СЂСѓСЃСЃРєРѕСЏР·С‹С‡РЅС‹Рµ (РєР°Рє РІ df_suite_edit), РЅРёР¶Рµ РѕРЅРё РјР°РїСЏС‚СЃСЏ РЅР° РєР»СЋС‡Рё worker'Р°.
    """
    base = {
        "id": str(uuid.uuid4()),
        "РІРєР»СЋС‡РµРЅ": True,
        "СЃС‚Р°РґРёСЏ": 0,
        "РёРјСЏ": "РќРѕРІС‹Р№ С‚РµСЃС‚",
        "С‚РёРї": "worldroad",
        "dt": 0.01,
        "t_end": 10.0,
        "road_csv": "",
        "axay_csv": "",
        "road_surface": "flat",
        "road_len_m": 200.0,
        "vx0_Рј_СЃ": 20.0,
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
        "target_РјР°РєСЃ_РґРѕР»СЏ_РѕС‚СЂС‹РІР°": None,
        "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_Pmid_Р±Р°СЂ": None,
        "target_РјРёРЅ_Fmin_Рќ": None,
        "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_РїСЂРѕР±РѕСЏ_РєСЂРµРЅ_РіСЂР°Рґ": None,
        "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_РїСЂРѕР±РѕСЏ_С‚Р°РЅРіР°Р¶_РіСЂР°Рґ": None,
        "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_СѓРїРѕСЂР°_С€С‚РѕРєР°_Рј": None,
        "target_Р»РёРјРёС‚_СЃРєРѕСЂРѕСЃС‚Рё_С€С‚РѕРєР°_Рј_СЃ": None,
        "target_РјР°РєСЃ_РѕС€РёР±РєР°_СЌРЅРµСЂРіРёРё_РіР°Р·Р°_РѕС‚РЅ": None,
        "target_РјР°РєСЃ_СЌРєСЃРµСЂРіРёСЏ_СЂР°Р·СЂСѓС€РµРЅР°_Р”Р¶": None,
        "target_РјР°РєСЃ_СЌРЅС‚СЂРѕРїРёСЏ_РіРµРЅРµСЂР°С†РёСЏ_Р”Р¶_Рљ": None,
        "target_РјР°РєСЃ_СЌРєСЃРµСЂРіРёСЏ_РїР°РґРµРЅРёРµ_РґР°РІР»РµРЅРёСЏ_Р”Р¶": None,
        "target_РјР°РєСЃ_СЌРєСЃРµСЂРіРёСЏ_СЃРјРµС€РµРЅРёРµ_Р”Р¶": None,
        "target_РјР°РєСЃ_СЌРєСЃРµСЂРіРёСЏ_РѕСЃС‚Р°С‚РѕРє_Р±РµР·_С‚РµРїР»Рѕ_Р±РµР·_СЃРјРµС€РµРЅРёСЏ_Р”Р¶": None,
        "target_РјР°РєСЃ_СЌРЅС‚СЂРѕРїРёСЏ_РїР°РґРµРЅРёРµ_РґР°РІР»РµРЅРёСЏ_Р”Р¶_Рљ": None,
        "target_РјР°РєСЃ_СЌРЅС‚СЂРѕРїРёСЏ_СЃРјРµС€РµРЅРёРµ_Р”Р¶_Рљ": None,
        "target_РјР°РєСЃ_СЌРЅС‚СЂРѕРїРёСЏ_РѕСЃС‚Р°С‚РѕРє_Р±РµР·_С‚РµРїР»Рѕ_Р±РµР·_СЃРјРµС€РµРЅРёСЏ_Р”Р¶_Рљ": None,
        "params_override": "",
    }

    if preset == "worldroad_sine_x":
        base.update({
            "РёРјСЏ": "WorldRoad: СЃРёРЅСѓСЃ (РІРґРѕР»СЊ)",
            "С‚РёРї": "worldroad",
            "road_surface": json.dumps({"type": "sine_x", "A": 0.02, "wavelength": 2.0}, ensure_ascii=False),
            "vx0_Рј_СЃ": 20.0,
            "road_len_m": 200.0,
            "auto_t_end_from_len": True,
            "t_end": 10.0,
        })
    elif preset == "worldroad_bump":
        base.update({
            "РёРјСЏ": "WorldRoad: Р±СѓРіРѕСЂ",
            "С‚РёРї": "worldroad",
            "road_surface": json.dumps({"type": "bump", "h": 0.04, "w": 0.6}, ensure_ascii=False),
            "vx0_Рј_СЃ": 15.0,
            "road_len_m": 150.0,
            "auto_t_end_from_len": True,
            "t_end": 10.0,
        })
    elif preset == "inertia_brake":
        base.update({
            "РёРјСЏ": "РРЅРµСЂС†РёСЏ: С‚РѕСЂРјРѕР¶РµРЅРёРµ",
            # Р”Р»СЏ РїСЂРѕРґРѕР»СЊРЅРѕРіРѕ СѓСЃРєРѕСЂРµРЅРёСЏ/С‚РѕСЂРјРѕР¶РµРЅРёСЏ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ С‚РµСЃС‚ "РёРЅРµСЂС†РёСЏ_С‚Р°РЅРіР°Р¶".
            # (РёСЃРїСЂР°РІР»РµРЅРёРµ: СЂР°РЅСЊС€Рµ Р±С‹Р» РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ С‚РёРї "inertia_flat", РёР·-Р·Р° С‡РµРіРѕ С‚РµСЃС‚ РјРѕРі Р»РѕРјР°С‚СЊСЃСЏ)
            "С‚РёРї": "РёРЅРµСЂС†РёСЏ_С‚Р°РЅРіР°Р¶",
            "ax": -3.0,
            "ay": 0.0,
            "road_surface": "flat",
            "t_end": 5.0,
            "auto_t_end_from_len": False,
        })
    else:
        base.update({
            "РёРјСЏ": "WorldRoad: СЂРѕРІРЅР°СЏ",
            "С‚РёРї": "worldroad",
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
            view.loc[:, "СЃС‚Р°РґРёСЏ"] = inferred_stage.loc[view.index].astype(int)
        except Exception:
            try:
                view = view[view["СЃС‚Р°РґРёСЏ"].isin(stages)]
            except Exception:
                pass
    if bool(only_enabled):
        try:
            view = view[view["РІРєР»СЋС‡РµРЅ"].astype(bool)]
        except Exception:
            pass
    q = str(suite_search or "").strip()
    if q:
        try:
            mask = (
                view["РёРјСЏ"].astype(str).str.contains(q, case=False, na=False)
                | view["С‚РёРї"].astype(str).str.contains(q, case=False, na=False)
            )
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
        _ensure_stage_visible_in_filter(row_new.get("СЃС‚Р°РґРёСЏ", 0))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "РўРµСЃС‚-С€Р°Р±Р»РѕРЅ РґРѕР±Р°РІР»РµРЅ РІ РЅР°Р±РѕСЂ.")
    except Exception as exc:
        _suite_set_flash("error", f"РќРµ СѓРґР°Р»РѕСЃСЊ РґРѕР±Р°РІРёС‚СЊ С‚РµСЃС‚-С€Р°Р±Р»РѕРЅ: {exc}")


def _suite_set_enabled_visible_callback(enabled: bool) -> None:
    try:
        row_ids = _suite_current_visible_ids()
        if not row_ids:
            return
        df = ensure_suite_columns(
            pd.DataFrame(st.session_state.get("df_suite_edit", pd.DataFrame([]))).copy(),
            context="pneumo_ui_app.toggle_visible_callback",
        )
        df.loc[df["id"].astype(str).isin(row_ids), "РІРєР»СЋС‡РµРЅ"] = bool(enabled)
        st.session_state["df_suite_edit"] = ensure_suite_columns(df, context="pneumo_ui_app.toggle_visible_callback.final")
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Р’РёРґРёРјС‹Рµ С‚РµСЃС‚С‹ РѕР±РЅРѕРІР»РµРЅС‹.")
    except Exception as exc:
        _suite_set_flash("error", f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РІРёРґРёРјС‹Рµ С‚РµСЃС‚С‹: {exc}")


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
        row["РёРјСЏ"] = f"{row.get('РёРјСЏ', 'РўРµСЃС‚')} (РєРѕРїРёСЏ)"
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df = ensure_suite_columns(df, context="pneumo_ui_app.duplicate_selected_callback.final")
        st.session_state["df_suite_edit"] = df
        _queue_suite_selected_id(str(row["id"]))
        _ensure_stage_visible_in_filter(row.get("СЃС‚Р°РґРёСЏ", 0))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Р’С‹Р±СЂР°РЅРЅС‹Р№ С‚РµСЃС‚ РїСЂРѕРґСѓР±Р»РёСЂРѕРІР°РЅ.")
    except Exception as exc:
        _suite_set_flash("error", f"РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРґСѓР±Р»РёСЂРѕРІР°С‚СЊ С‚РµСЃС‚: {exc}")


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
        _suite_set_flash("success", "Р’С‹Р±СЂР°РЅРЅС‹Р№ С‚РµСЃС‚ СѓРґР°Р»С‘РЅ РёР· РЅР°Р±РѕСЂР°.")
    except Exception as exc:
        _suite_set_flash("error", f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С‚РµСЃС‚: {exc}")


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
        stage_default = max(0, int(rec.get("СЃС‚Р°РґРёСЏ", 0) or 0))
    except Exception:
        stage_default = 0
    ttype_default = str(rec.get("С‚РёРї", "worldroad") or "worldroad")
    if ttype_default not in ALLOWED_TEST_TYPES:
        ttype_default = "worldroad"

    _seed("enabled", bool(rec.get("РІРєР»СЋС‡РµРЅ", True)))
    _seed("name", str(rec.get("РёРјСЏ", "") or ""))
    _seed("stage", int(stage_default))
    _seed("type", ttype_default)
    _seed("dt", float(_as_float(rec.get("dt", 0.01), 0.01)))
    _seed("t_end", float(_as_float(rec.get("t_end", 5.0), 5.0)))
    _seed("road_csv", str(rec.get("road_csv", "") or ""))
    _seed("axay_csv", str(rec.get("axay_csv", "") or ""))
    _seed("road_len_m", float(_as_float(rec.get("road_len_m", 200.0), 200.0)))
    _seed("vx0_mps", float(_as_float(rec.get("vx0_Рј_СЃ", 20.0), 20.0)))
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


st.caption(
    "РўРµСЃС‚-РЅР°Р±РѕСЂ РЅР°СЃС‚СЂР°РёРІР°РµС‚СЃСЏ Р±РµР· С€РёСЂРѕРєРѕР№ С‚Р°Р±Р»РёС†С‹: РІС‹Р±РµСЂРё С‚РµСЃС‚ РІ СЃРїРёСЃРєРµ в†’ СЃРїСЂР°РІР° РєР°СЂС‚РѕС‡РєР°. "
    "Р•СЃС‚СЊ Р±С‹СЃС‚СЂС‹Р№ РіРµРЅРµСЂР°С‚РѕСЂ С€Р°Р±Р»РѕРЅРѕРІ."
)
_suite_maybe_autosave_pending()
_suite_render_flash()
st.session_state.pop("ui_suite_selected_row", None)

# Р‘С‹СЃС‚СЂС‹Р№ РјР°СЃС‚РµСЂ РґРѕР±Р°РІР»РµРЅРёСЏ С‚РµСЃС‚РѕРІ
wiz_l, wiz_r = st.columns([1.2, 1.0], gap="medium")
with wiz_l:
    _preset = st.selectbox(
        "Р”РѕР±Р°РІРёС‚СЊ С‚РµСЃС‚-С€Р°Р±Р»РѕРЅ",
        options=[
            "worldroad_flat",
            "worldroad_sine_x",
            "worldroad_bump",
            "inertia_brake",
        ],
        format_func={
            "worldroad_flat": "WorldRoad: СЂРѕРІРЅР°СЏ РґРѕСЂРѕРіР°",
            "worldroad_sine_x": "WorldRoad: СЃРёРЅСѓСЃ РІРґРѕР»СЊ (A=2 СЃРј, О»=2 Рј)",
            "worldroad_bump": "WorldRoad: Р±СѓРіРѕСЂ (h=4 СЃРј, w=0.6 Рј)",
            "inertia_brake": "РРЅРµСЂС†РёСЏ: С‚РѕСЂРјРѕР¶РµРЅРёРµ ax=-3 Рј/СЃВІ",
        }.get,
        help="РЁР°Р±Р»РѕРЅ РґРѕР±Р°РІРёС‚ РЅРѕРІС‹Р№ С‚РµСЃС‚ СЃ СЂР°Р·СѓРјРЅС‹РјРё РЅР°СЃС‚СЂРѕР№РєР°РјРё. Р—Р°С‚РµРј РјРѕР¶РЅРѕ СѓС‚РѕС‡РЅРёС‚СЊ РІ РєР°СЂС‚РѕС‡РєРµ СЃРїСЂР°РІР°.",
        index=["worldroad_flat", "worldroad_sine_x", "worldroad_bump", "inertia_brake"].index(str(st.session_state.get("ui_suite_preset", DIAGNOSTIC_SUITE_PRESET) or DIAGNOSTIC_SUITE_PRESET)) if str(st.session_state.get("ui_suite_preset", DIAGNOSTIC_SUITE_PRESET) or DIAGNOSTIC_SUITE_PRESET) in ["worldroad_flat", "worldroad_sine_x", "worldroad_bump", "inertia_brake"] else 0,
        key="ui_suite_preset",
    )
with wiz_r:
    st.button(
        "Р”РѕР±Р°РІРёС‚СЊ",
        width="stretch",
        key="ui_suite_add_preset_btn",
        on_click=_suite_add_preset_callback,
        args=(str(_preset),),
    )


# -------------------------------
# РЎС†РµРЅР°СЂРёРё: РЅРѕРІС‹Р№ СЂРµРґР°РєС‚РѕСЂ (СЃРµРіРјРµРЅС‚С‹вЂ‘РєРѕР»СЊС†Рѕ)
st.markdown("### РЎС†РµРЅР°СЂРёР№: СЃРµРіРјРµРЅС‚С‹вЂ‘РєРѕР»СЊС†Рѕ")

if not _HAS_RING_SCENARIO_EDITOR:
    st.error(
        "Р РµРґР°РєС‚РѕСЂ СЃС†РµРЅР°СЂРёРµРІ (СЃРµРіРјРµРЅС‚С‹вЂ‘РєРѕР»СЊС†Рѕ) РЅРµРґРѕСЃС‚СѓРїРµРЅ (РЅРµ СѓРґР°Р»РѕСЃСЊ РёРјРїРѕСЂС‚РёСЂРѕРІР°С‚СЊ pneumo_solver_ui.ui_scenario_ring). "
        "РџРµСЂРµСѓСЃС‚Р°РЅРѕРІРёС‚Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё/РїСЂРѕРІРµСЂСЊС‚Рµ С†РµР»РѕСЃС‚РЅРѕСЃС‚СЊ Р°СЂС…РёРІР°."
    )
else:
    # Р’РђР–РќРћ (ABSOLUTE LAW):
    #  - РќРёРєР°РєРёС… РІС‹РґСѓРјР°РЅРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ Рё РїСЃРµРІРґРѕРЅРёРјРѕРІ.
    #  - РЎС†РµРЅР°СЂРёР№ С…СЂР°РЅРёС‚СЃСЏ РІ scenario_json Рё СЏРІР»СЏРµС‚СЃСЏ РµРґРёРЅСЃС‚РІРµРЅРЅС‹Рј РёСЃС‚РѕС‡РЅРёРєРѕРј РёСЃС‚РёРЅС‹.
    #  - road_csv / axay_csv РіРµРЅРµСЂРёСЂСѓСЋС‚СЃСЏ СЃС‚СЂРѕРіРѕ РєР°Рє РїСЂРѕРёР·РІРѕРґРЅС‹Рµ РѕС‚ scenario_json.
    with st.expander("РћС‚РєСЂС‹С‚СЊ СЂРµРґР°РєС‚РѕСЂ СЃС†РµРЅР°СЂРёРµРІ (СЃРµРіРјРµРЅС‚С‹вЂ‘РєРѕР»СЊС†Рѕ)", expanded=True):
        try:
            try:
                _ring_wheelbase_m = float(base_override.get("Р±Р°Р·Р°", 0.0))
            except Exception:
                _ring_wheelbase_m = 0.0
                logging.warning("[RING] РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ РєР°РЅРѕРЅРёС‡РµСЃРєРёР№ РїР°СЂР°РјРµС‚СЂ 'Р±Р°Р·Р°' РґР»СЏ wheelbase_m.")
                st.warning(
                    "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ РєР°РЅРѕРЅРёС‡РµСЃРєРёР№ РїР°СЂР°РјРµС‚СЂ **'Р±Р°Р·Р°'**. Р“РµРЅРµСЂР°С†РёСЏ ring-СЃС†РµРЅР°СЂРёСЏ РїРѕС‚СЂРµР±СѓРµС‚ РёСЃРїСЂР°РІРёС‚СЊ base.",
                    icon="вљ пёЏ",
                )

            if _ring_wheelbase_m <= 0.0:
                logging.warning("[RING] РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ Р±Р°Р·Р° РґР»СЏ ring-СЃС†РµРЅР°СЂРёСЏ: %s", _ring_wheelbase_m)
                st.warning(
                    "РљРѕР»С‘СЃРЅР°СЏ Р±Р°Р·Р° РґР»СЏ ring-СЃС†РµРЅР°СЂРёСЏ Р±РµСЂС‘С‚СЃСЏ С‚РѕР»СЊРєРѕ РёР· РєР°РЅРѕРЅРёС‡РµСЃРєРѕРіРѕ РїР°СЂР°РјРµС‚СЂР° **'Р±Р°Р·Р°'** Рё СЃРµР№С‡Р°СЃ <= 0. "
                    "РџСЂРѕРІРµСЂСЊС‚Рµ РёСЃС…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ РјРѕРґРµР»Рё.",
                    icon="вљ пёЏ",
                )

            df_suite_edit = render_ring_scenario_generator(
                df_suite_edit,
                work_dir=WORKSPACE_DIR,
                wheelbase_m=float(_ring_wheelbase_m),
                default_dt_s=0.01,
            )
        except Exception as e:
            st.error(f"РћС€РёР±РєР° РІ СЂРµРґР°РєС‚РѕСЂРµ СЃС†РµРЅР°СЂРёРµРІ: {e}")
# Р¤РёР»СЊС‚СЂС‹ СЃРїРёСЃРєР°
def _sync_multiselect_all(key: str, options: list, *, cast=int) -> None:
    """Р”РµР»Р°РµС‚ РјСѓР»СЊС‚РёСЃРµР»РµРєС‚ СѓСЃС‚РѕР№С‡РёРІС‹Рј Рє РёР·РјРµРЅРµРЅРёСЋ options.

    Р•СЃР»Рё СЂР°РЅСЊС€Рµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РґРµСЂР¶Р°Р» РІС‹Р±СЂР°РЅРЅС‹РјРё *РІСЃРµ* РґРѕСЃС‚СѓРїРЅС‹Рµ Р·РЅР°С‡РµРЅРёСЏ,
    С‚Рѕ РїСЂРё РїРѕСЏРІР»РµРЅРёРё РЅРѕРІС‹С… Р·РЅР°С‡РµРЅРёР№ РѕРЅРё Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РґРѕР±Р°РІСЏС‚СЃСЏ РІ РІС‹Р±РѕСЂ.
    Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ С„РёР»СЊС‚СЂРѕРІР°Р» РІСЂСѓС‡РЅСѓСЋ вЂ” РјС‹ СЌС‚Рѕ СѓРІР°Р¶Р°РµРј.
    """
    prev_key = f"{key}__options_prev"
    opts = list(options or [])
    try:
        opts_norm = [cast(x) for x in opts]
    except Exception:
        opts_norm = opts

    prev_opts = st.session_state.get(prev_key)
    cur = st.session_state.get(key)

    if cur is None:
        st.session_state[key] = opts_norm.copy()
    else:
        # РѕСЃС‚Р°РІР»СЏРµРј С‚РѕР»СЊРєРѕ РІР°Р»РёРґРЅС‹Рµ Р·РЅР°С‡РµРЅРёСЏ
        try:
            cur_list = [cast(x) for x in list(cur)]
        except Exception:
            try:
                cur_list = list(cur)
            except Exception:
                cur_list = []
        cur_list = [x for x in cur_list if x in opts_norm]

        # РµСЃР»Рё СЂР°РЅРµРµ Р±С‹Р»Рё РІС‹Р±СЂР°РЅС‹ РІСЃРµ РїСЂРµРґС‹РґСѓС‰РёРµ РѕРїС†РёРё вЂ” РІС‹Р±РёСЂР°РµРј РІСЃРµ РЅРѕРІС‹Рµ
        try:
            if prev_opts is not None:
                prev_norm = [cast(x) for x in list(prev_opts)]
                if set(cur_list) == set(prev_norm):
                    cur_list = opts_norm.copy()
        except Exception:
            pass

        st.session_state[key] = cur_list

    st.session_state[prev_key] = opts_norm.copy()

_stages = sorted({int(infer_suite_stage(_r.to_dict())) for _, _r in df_suite_edit.iterrows()}) if not df_suite_edit.empty else [0]
if not _stages:
    _stages = [0]
for _stage_key in ("ui_suite_stage_filter", "ui_suite_stage_filter__options_prev", "ui_suite_stage_all_prev"):
    try:
        _raw_stage_vals = list(st.session_state.get(_stage_key) or [])
        _norm_stage_vals = sorted({max(0, int(x)) for x in _raw_stage_vals})
        if _norm_stage_vals:
            st.session_state[_stage_key] = _norm_stage_vals
        elif _stage_key == "ui_suite_stage_filter":
            st.session_state[_stage_key] = _stages.copy()
    except Exception:
        pass

# Streamlit Р·Р°РїСЂРµС‰Р°РµС‚ РјРµРЅСЏС‚СЊ Р·РЅР°С‡РµРЅРёРµ widget-key РїРѕСЃР»Рµ СЃРѕР·РґР°РЅРёСЏ СЃР°РјРѕРіРѕ widget.
# РџРѕСЌС‚РѕРјСѓ РєРЅРѕРїРєРё РЅРёР¶Рµ СЃС‚Р°РІСЏС‚ С‚РѕР»СЊРєРѕ pending-flag, Р° С„Р°РєС‚РёС‡РµСЃРєРёР№ reset/extend
# РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ Р·РґРµСЃСЊ, Р”Рћ СЂРµРЅРґРµСЂР° multiselect/checkbox/text_input.
if st.session_state.pop("_ui_suite_filters_reset_pending", False) or st.session_state.pop("_ui_suite_show_all_pending", False):
    st.session_state["ui_suite_stage_filter"] = _stages.copy()
    st.session_state["ui_suite_only_enabled"] = False
    st.session_state["ui_suite_search"] = ""

_pending_stage_extend = st.session_state.pop("_ui_suite_stage_filter_extend_pending", None)
if _pending_stage_extend is not None:
    try:
        _pending_vals = [int(x) for x in list(_pending_stage_extend)]
    except Exception:
        _pending_vals = []
    try:
        _cur_stage_filter = [int(x) for x in list(st.session_state.get("ui_suite_stage_filter") or [])]
    except Exception:
        _cur_stage_filter = []
    _merged_stage_filter = [x for x in _cur_stage_filter if x in _stages]
    for _stg_val in _pending_vals:
        if _stg_val in _stages and _stg_val not in _merged_stage_filter:
            _merged_stage_filter.append(_stg_val)
    st.session_state["ui_suite_stage_filter"] = sorted(set(int(x) for x in (_merged_stage_filter or _stages.copy())))

_sync_multiselect_all("ui_suite_stage_filter", _stages, cast=int)

f1, f2, f3, f4 = st.columns([1.0, 1.0, 1.2, 0.8], gap="small")
with f1:
    stage_filter = st.multiselect(
        "РЎС‚Р°РґРёРё",
        options=_stages,
        default=_stages,
        help="РџРѕРєР°Р·С‹РІР°С‚СЊ С‚РµСЃС‚С‹ РІС‹Р±СЂР°РЅРЅС‹С… СЃС‚Р°РґРёР№.",
        key="ui_suite_stage_filter",
    )
with f2:
    only_enabled = st.checkbox(
        "РўРѕР»СЊРєРѕ РІРєР»СЋС‡С‘РЅРЅС‹Рµ",
        value=False,
        key="ui_suite_only_enabled",
        help="РЎРєСЂС‹РІР°РµС‚ РІС‹РєР»СЋС‡РµРЅРЅС‹Рµ С‚РµСЃС‚С‹.",
    )
with f3:
    suite_search = st.text_input(
        "РџРѕРёСЃРє",
        value=st.session_state.get("ui_suite_search", ""),
        key="ui_suite_search",
        help="РС‰РµС‚ РїРѕ РёРјРµРЅРё С‚РµСЃС‚Р° Рё С‚РёРїСѓ.",
    ).strip()
with f4:
    st.button(
        "РЎР±СЂРѕСЃРёС‚СЊ С„РёР»СЊС‚СЂС‹",
        width="stretch",
        key="ui_suite_reset_filters_btn",
        on_click=_suite_reset_filters_callback,
        args=(list(_stages),),
    )

st.caption("Р›РѕРіРёРєР° staged optimization: S0 вЂ” Р±С‹СЃС‚СЂС‹Р№ relevance-screen; S1 вЂ” РґР»РёРЅРЅС‹Рµ РґРѕСЂРѕР¶РЅС‹Рµ/РјР°РЅС‘РІСЂРµРЅРЅС‹Рµ С‚РµСЃС‚С‹; S2 вЂ” С„РёРЅР°Р»СЊРЅР°СЏ robustness-СЃС‚Р°РґРёСЏ. РќРѕРјРµСЂ РІ РєРѕР»РѕРЅРєРµ В«РЎС‚Р°РґРёСЏВ» РѕР·РЅР°С‡Р°РµС‚ РјРѕРјРµРЅС‚ РїРµСЂРІРѕРіРѕ РІС…РѕРґР° С‚РµСЃС‚Р°: stage 1 РЅРµ РґРѕР»Р¶РµРЅ РјРѕР»С‡Р° РїРµСЂРµРїРёСЃС‹РІР°С‚СЊСЃСЏ РІ 0.")

# РЎРїРёСЃРѕРє С‚РµСЃС‚РѕРІ
_df_view = _suite_filtered_view(df_suite_edit, stage_filter, False, "")
if only_enabled:
    _df_view = _df_view[_df_view["РІРєР»СЋС‡РµРЅ"].astype(bool)]
if suite_search:
    _mask = (
        _df_view["РёРјСЏ"].astype(str).str.contains(suite_search, case=False, na=False)
        | _df_view["С‚РёРї"].astype(str).str.contains(suite_search, case=False, na=False)
    )
    _df_view = _df_view[_mask]

# РџРѕРґСЃРєР°Р·РєР°: СЃРєРѕР»СЊРєРѕ С‚РµСЃС‚РѕРІ СЃРєСЂС‹С‚Рѕ С„РёР»СЊС‚СЂР°РјРё (С‡Р°СЃС‚Р°СЏ РїСЂРёС‡РёРЅР° "РїСЂРѕРїР°Р¶Рё" С‚РµСЃС‚РѕРІ)
try:
    _n_total = int(len(df_suite_edit))
    _n_vis = int(len(_df_view))
    _n_hidden = max(0, _n_total - _n_vis)
except Exception:
    _n_total, _n_vis, _n_hidden = 0, 0, 0

if _n_hidden > 0:
    cols_info = st.columns([1.0, 0.28], gap="small")
    with cols_info[0]:
        st.info(
            f"РџРѕРєР°Р·Р°РЅРѕ **{_n_vis}** РёР· **{_n_total}** С‚РµСЃС‚РѕРІ. РЎРєСЂС‹С‚Рѕ **{_n_hidden}** вЂ” РїСЂРѕРІРµСЂСЊ С„РёР»СЊС‚СЂС‹ СЃС‚Р°РґРёР№/РІРєР»СЋС‡РµРЅРёСЏ/РїРѕРёСЃРє."
        )
    with cols_info[1]:
        st.button(
            "РџРѕРєР°Р·Р°С‚СЊ РІСЃРµ",
            key="ui_suite_show_all_btn",
            width="stretch",
            on_click=_suite_show_all_callback,
            args=(list(_stages),),
        )

# Р’Р°Р¶РЅРѕ: РёСЃРїРѕР»СЊР·СѓРµРј СЃС‚Р°Р±РёР»СЊРЅС‹Р№ ID (Р° РЅРµ РёРЅРґРµРєСЃ DataFrame),
# РёРЅР°С‡Рµ selection РІ st.dataframe С‡Р°СЃС‚Рѕ В«РѕС‚СЃС‚Р°С‘С‚ РЅР° 1 rerunВ» Рё С‚СЂРµР±СѓРµС‚ РґРІРѕР№РЅРѕРіРѕ РєР»РёРєР°.
_row_ids = _df_view["id"].astype(str).tolist() if ("id" in _df_view.columns) else []

# РќРѕСЂРјР°Р»РёР·СѓРµРј РІС‹Р±СЂР°РЅРЅС‹Р№ id Р”Рћ СЂРµРЅРґРµСЂР° selectbox.
# РќРѕСЂРјР°Р»СЊРЅР°СЏ UX-РїРѕР»РёС‚РёРєР°: РµСЃР»Рё СЃРїРёСЃРѕРє С‚РµСЃС‚РѕРІ РЅРµ РїСѓСЃС‚, РІС‹Р±СЂР°РЅРЅС‹Р№ СЃС†РµРЅР°СЂРёР№ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІСЃРµРіРґР°.
# Р”РµС„РѕР»С‚РЅС‹Р№ СЃС‚Р°СЂС‚ Р±РµР· Р°РІС‚РѕР·Р°РїСѓСЃРєР° РѕР±РµСЃРїРµС‡РёРІР°РµС‚СЃСЏ С‚РµРј, С‡С‚Рѕ shipped default-suite РїСЂРёС…РѕРґРёС‚
# СЃ РІС‹РєР»СЋС‡РµРЅРЅС‹РјРё СЃС†РµРЅР°СЂРёСЏРјРё, Р° РЅРµ РїСѓСЃС‚С‹Рј forced-selection.
_row_ids = [_normalize_suite_id_value(x) for x in _row_ids]
_row_ids = [x for x in _row_ids if x]
_pending_sel = _normalize_suite_id_value(st.session_state.pop("_ui_suite_selected_id_pending", ""))
_cur_sel = _normalize_suite_id_value(st.session_state.get("ui_suite_selected_id"))
if _row_ids:
    if _pending_sel and _pending_sel in set(_row_ids):
        _cur_sel = _pending_sel
        st.session_state["ui_suite_selected_id"] = _cur_sel
    elif _cur_sel not in set(_row_ids):
        _cur_sel = str(_row_ids[0])
        st.session_state["ui_suite_selected_id"] = _cur_sel
else:
    st.session_state.pop("ui_suite_selected_id", None)
    _cur_sel = ""

# РљРЅРѕРїРєРё РґРµР№СЃС‚РІРёР№ (РЅР°Рґ СЃРїРёСЃРєРѕРј)
a1, a2, a3, a4 = st.columns([1, 1, 1, 1], gap="small")
with a1:
    st.button(
        "Р’РєР»СЋС‡РёС‚СЊ РІСЃРµ",
        width="stretch",
        key="ui_suite_enable_visible_btn",
        on_click=_suite_set_enabled_visible_callback,
        args=(True,),
        disabled=not bool(_row_ids),
    )
with a2:
    st.button(
        "Р’С‹РєР»СЋС‡РёС‚СЊ РІСЃРµ",
        width="stretch",
        key="ui_suite_disable_visible_btn",
        on_click=_suite_set_enabled_visible_callback,
        args=(False,),
        disabled=not bool(_row_ids),
    )
with a3:
    st.button(
        "Р”СѓР±Р»РёСЂРѕРІР°С‚СЊ РІС‹Р±СЂР°РЅРЅС‹Р№",
        width="stretch",
        key="ui_suite_duplicate_selected_btn",
        on_click=_suite_duplicate_selected_callback,
        disabled=not bool(_cur_sel),
    )
with a4:
    st.button(
        "РЈРґР°Р»РёС‚СЊ РІС‹Р±СЂР°РЅРЅС‹Р№",
        width="stretch",
        key="ui_suite_delete_selected_btn",
        on_click=_suite_delete_selected_callback,
        disabled=not bool(_cur_sel),
    )

left, right = st.columns([1.05, 1.0], gap="large")
with left:
    if _df_view.empty:
        st.info("РЎРїРёСЃРѕРє РїСѓСЃС‚ (РІ С‚РµРєСѓС‰РµРј С„РёР»СЊС‚СЂРµ).")
    else:
        st.caption("РЎРїРёСЃРѕРє С‚РµСЃС‚РѕРІ (Р±РµР· РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р°).")

        def _label_for_id(_id: str) -> str:
            try:
                _r = _df_view[_df_view["id"].astype(str) == str(_id)].iloc[0].to_dict()
                en = "вњ“" if bool(_r.get("РІРєР»СЋС‡РµРЅ", False)) else " "
                stg = int(infer_suite_stage(_r))
                nm = str(_r.get("РёРјСЏ", "")).strip() or "<Р±РµР· РёРјРµРЅРё>"
                tp = str(_r.get("С‚РёРї", "")).strip() or "<Р±РµР· С‚РёРїР°>"
                return f"{en} [S{stg}] {nm} вЂ” {tp}"
            except Exception:
                return str(_id)

        # РІС‹Р±РѕСЂ С‚РµСЃС‚Р°: selectbox РЅР°Рґ С‚Р°Р±Р»РёС†РµР№ (СѓСЃС‚СЂР°РЅСЏРµС‚ Р±Р°РіРё selection/rerun Рё В«РґРІРѕР№РЅРѕР№ РєР»РёРєВ»)
        if _row_ids:
            _suite_select_options = list(_row_ids)
            st.selectbox(
                "Р’С‹Р±СЂР°РЅРЅС‹Р№ С‚РµСЃС‚",
                options=_suite_select_options,
                index=_suite_select_options.index(_cur_sel) if (_cur_sel in _suite_select_options) else 0,
                format_func=lambda _id: _label_for_id(str(_id)),
                key="ui_suite_selected_id",
                help="Р’С‹Р±РѕСЂ С‚РµСЃС‚Р° РґР»СЏ РєР°СЂС‚РѕС‡РєРё СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ СЃРїСЂР°РІР°.",
            )

        _list_df = _df_view[["РІРєР»СЋС‡РµРЅ", "СЃС‚Р°РґРёСЏ", "РёРјСЏ", "С‚РёРї"]].copy()
        _list_df = _list_df.rename(columns={"РІРєР»СЋС‡РµРЅ": "Р’РєР».", "СЃС‚Р°РґРёСЏ": "РЎС‚Р°РґРёСЏ", "РёРјСЏ": "РўРµСЃС‚", "С‚РёРї": "РўРёРї"})
        st.dataframe(
            _list_df,
            hide_index=True,
            width="stretch",
            height=320,
        )

with right:
    if not _row_ids:
        st.info("Р”РѕР±Р°РІСЊ С‚РµСЃС‚-С€Р°Р±Р»РѕРЅ РёР»Рё РѕСЃР»Р°Р±СЊ С„РёР»СЊС‚СЂС‹ вЂ” С‚РѕРіРґР° РїРѕСЏРІРёС‚СЃСЏ РєР°СЂС‚РѕС‡РєР° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ.")
    else:
        sel_id = str(st.session_state.get("ui_suite_selected_id") or "").strip()
        idx = None
        try:
            m = df_suite_edit.index[df_suite_edit["id"].astype(str) == sel_id].tolist()
            if m:
                idx = int(m[0])
        except Exception:
            idx = None
        if idx is None:
            st.error("Р’С‹Р±СЂР°РЅРЅС‹Р№ С‚РµСЃС‚ РЅРµ РЅР°Р№РґРµРЅ РІ РЅР°Р±РѕСЂРµ (РІРѕР·РјРѕР¶РЅРѕ, РёР·РјРµРЅРёР»РёСЃСЊ С„РёР»СЊС‚СЂС‹/РЅР°Р±РѕСЂ).")
            st.stop()
        rec = df_suite_edit.loc[idx].to_dict()
        sid = str(rec.get("id") or sel_id or idx)
        title = str(rec.get("РёРјСЏ", "РўРµСЃС‚"))
        st.markdown(f"### {title}")

        # Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Р№ РїР°СЂСЃРµСЂ С‡РёСЃРµР»
        def _sf(x, default=0.0):
            try:
                if pd.isna(x):
                    return default
            except Exception:
                pass
            try:
                return float(x)
            except Exception:
                return default

        # РљР°СЂС‚РѕС‡РєР° СЂРµРґР°РєС‚РѕСЂР° Р±РµР· st.form: С‡РµСЂРЅРѕРІРёРє Р¶РёРІС‘С‚ РІ session_state Рё РЅРµ С‚РµСЂСЏРµС‚СЃСЏ РїСЂРё РѕР±С‹С‡РЅС‹С… rerun.
        # CSV_UPLOADERS_OUTSIDE_FORM
        uploaded_road_csv = None
        uploaded_axay_csv = None
        with st.expander("CSV РїСЂРѕС„РёР»СЏ РґРѕСЂРѕРіРё / РјР°РЅРµРІСЂР° (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)", expanded=True):
            st.caption("Р•СЃР»Рё РЅСѓР¶РЅРѕ: Р·Р°РіСЂСѓР·РёС‚Рµ CSV, С„Р°Р№Р» Р±СѓРґРµС‚ СЃРѕС…СЂР°РЅС‘РЅ РІ workspace/uploads Рё РїСѓС‚СЊ РїРѕРґСЃС‚Р°РІРёС‚СЃСЏ РІ РїРѕР»СЏ РЅРёР¶Рµ.")
            up_road = st.file_uploader(
                "РџСЂРѕС„РёР»СЊ РґРѕСЂРѕРіРё (CSV)",
                type=["csv"],
                key=f"suite_road_csv_upload_{sid}",
                help="РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ С‚РёРїР°С… road_profile_csv / (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ) РІ РґСЂСѓРіРёС… С‚РµСЃС‚Р°С….",
            )
            if up_road is not None:
                uploaded_road_csv = _save_upload(up_road, prefix="road")
                if uploaded_road_csv:
                    st.success(f"РџСЂРѕС„РёР»СЊ РґРѕСЂРѕРіРё СЃРѕС…СЂР°РЅС‘РЅ: {uploaded_road_csv}")
            up_axay = st.file_uploader(
                "РњР°РЅС‘РІСЂ (CSV ax/ay)",
                type=["csv"],
                key=f"suite_axay_csv_upload_{sid}",
                help="РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ С‚РёРїР°С… maneuver_csv / (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ) РІ РґСЂСѓРіРёС… С‚РµСЃС‚Р°С….",
            )
            if up_axay is not None:
                uploaded_axay_csv = _save_upload(up_axay, prefix="axay")
                if uploaded_axay_csv:
                    st.success(f"РњР°РЅС‘РІСЂ СЃРѕС…СЂР°РЅС‘РЅ: {uploaded_axay_csv}")

        _seed_suite_editor_state(sid, rec)
        st.caption("Р§РµСЂРЅРѕРІРёРє РєР°СЂС‚РѕС‡РєРё Р¶РёРІС‘С‚ РІ UI-state: РѕР±С‹С‡РЅС‹Р№ rerun РЅРµ РґРѕР»Р¶РµРЅ РѕС‚РєР°С‚С‹РІР°С‚СЊ РЅРµСЃРѕС…СЂР°РЅС‘РЅРЅС‹Рµ РїРѕР»СЏ.")

        _enabled_key = _suite_editor_widget_key(sid, "enabled")
        _name_key = _suite_editor_widget_key(sid, "name")
        _stage_key = _suite_editor_widget_key(sid, "stage")
        _type_key = _suite_editor_widget_key(sid, "type")
        _dt_key = _suite_editor_widget_key(sid, "dt")
        _t_end_key = _suite_editor_widget_key(sid, "t_end")
        _road_csv_key = _suite_editor_widget_key(sid, "road_csv")
        _axay_csv_key = _suite_editor_widget_key(sid, "axay_csv")
        _road_len_key = _suite_editor_widget_key(sid, "road_len_m")
        _vx0_key = _suite_editor_widget_key(sid, "vx0_mps")
        _auto_t_end_key = _suite_editor_widget_key(sid, "auto_t_end_from_len")
        _surface_type_key = _suite_editor_widget_key(sid, "road_surface_type")
        _surface_sine_a_key = _suite_editor_widget_key(sid, "road_surface_sine_a")
        _surface_sine_wl_key = _suite_editor_widget_key(sid, "road_surface_sine_wavelength")
        _surface_hw_h_key = _suite_editor_widget_key(sid, "road_surface_hw_h")
        _surface_hw_w_key = _suite_editor_widget_key(sid, "road_surface_hw_w")
        _surface_cos_h_key = _suite_editor_widget_key(sid, "road_surface_cos_h")
        _surface_cos_w_key = _suite_editor_widget_key(sid, "road_surface_cos_w")
        _surface_cos_k_key = _suite_editor_widget_key(sid, "road_surface_cos_k")
        _ax_key = _suite_editor_widget_key(sid, "ax")
        _ay_key = _suite_editor_widget_key(sid, "ay")
        _params_override_key = _suite_editor_widget_key(sid, "params_override")

        if uploaded_road_csv:
            st.session_state[_road_csv_key] = str(uploaded_road_csv)
        if uploaded_axay_csv:
            st.session_state[_axay_csv_key] = str(uploaded_axay_csv)

        enabled = st.checkbox("Р’РєР»СЋС‡С‘РЅ", key=_enabled_key)
        name = st.text_input("РРјСЏ", key=_name_key)

        try:
            _stage_default = max(0, int(st.session_state.get(_stage_key, infer_suite_stage(rec)) or 0))
        except Exception:
            _stage_default = 0
            st.session_state[_stage_key] = 0
        stage = st.number_input(
            "РЎС‚Р°РґРёСЏ",
            value=int(_stage_default),
            min_value=0,
            step=1,
            key=_stage_key,
            help="РњРѕРјРµРЅС‚ РІС…РѕРґР° С‚РµСЃС‚Р° РІ staged optimization. РЎРµРјР°РЅС‚РёРєР° РЅР°РєРѕРїРёС‚РµР»СЊРЅР°СЏ: stage 0 РёРґС‘С‚ С‚РѕР»СЊРєРѕ СЃ S0; stage 1 РІРїРµСЂРІС‹Рµ РІРєР»СЋС‡Р°РµС‚СЃСЏ СЃ S1 Рё Р·Р°С‚РµРј РёРґС‘С‚ Рё РІ S2; stage 2 вЂ” С‚РѕР»СЊРєРѕ РІ С„РёРЅР°Р»СЊРЅРѕР№ СЃС‚Р°РґРёРё. РќСѓРјРµСЂР°С†РёСЏ 0-based: РїРµСЂРІР°СЏ СЃС‚Р°РґРёСЏ = 0.",
        )

        _type_default = str(st.session_state.get(_type_key, rec.get("С‚РёРї", "worldroad")) or "worldroad")
        if _type_default not in ALLOWED_TEST_TYPES:
            _type_default = "worldroad"
            st.session_state[_type_key] = _type_default
        ttype = st.selectbox(
            "РўРёРї",
            options=ALLOWED_TEST_TYPES,
            index=max(0, ALLOWED_TEST_TYPES.index(_type_default)),
            key=_type_key,
        )

        dt = st.number_input("dt, СЃ", min_value=1e-5, step=0.001, format="%.6g", key=_dt_key)
        t_end = st.number_input("t_end, СЃ", min_value=0.01, step=0.1, format="%.6g", key=_t_end_key)

        st.markdown("#### Р”РѕСЂРѕРіР° Рё СЂРµР¶РёРј РґРІРёР¶РµРЅРёСЏ")

        road_csv = str(st.session_state.get(_road_csv_key, "") or "")
        axay_csv = str(st.session_state.get(_axay_csv_key, "") or "")
        road_len_m = float(_sf(st.session_state.get(_road_len_key, rec.get("road_len_m", 200.0)), 200.0))
        vx0_mps = float(_sf(st.session_state.get(_vx0_key, rec.get("vx0_Рј_СЃ", 20.0)), 20.0))
        auto_t_end_from_len = bool(st.session_state.get(_auto_t_end_key, rec.get("auto_t_end_from_len", False)))
        t_end_effective = float(t_end)

        if ttype == "worldroad":
            c1, c2 = st.columns([1, 1], gap="small")
            with c1:
                vx0_mps = st.number_input("РЎРєРѕСЂРѕСЃС‚СЊ (vx0_Рј_СЃ), Рј/СЃ", min_value=0.0, step=0.5, key=_vx0_key)
            with c2:
                road_len_m = st.number_input("Р”Р»РёРЅР° СѓС‡Р°СЃС‚РєР°, Рј", min_value=1.0, step=10.0, key=_road_len_key)

            auto_t_end_from_len = st.checkbox(
                "РђРІС‚Рѕ: t_end = (РґР»РёРЅР° / СЃРєРѕСЂРѕСЃС‚СЊ)",
                key=_auto_t_end_key,
                help="Р•СЃР»Рё РІРєР»СЋС‡РµРЅРѕ, t_end Р±СѓРґРµС‚ РІС‹С‡РёСЃР»СЏС‚СЊСЃСЏ РєР°Рє road_len_m / max(vx0_Рј_СЃ, eps).",
            )

            eps_v = 1e-6
            if auto_t_end_from_len:
                t_end_auto = float(road_len_m) / max(float(vx0_mps), eps_v)
                t_end_effective = float(t_end_auto)
                st.info(
                    f"t_end Р±СѓРґРµС‚ РІС‹С‡РёСЃР»РµРЅ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё: **{t_end_effective:.6g} СЃ** "
                    f"(РІРјРµСЃС‚Рѕ РІРІРµРґС‘РЅРЅРѕРіРѕ {float(t_end):.6g} СЃ)"
                )
            else:
                t_end_effective = float(t_end)
                len_eff = float(vx0_mps) * float(t_end_effective)
                st.caption(
                    f"Р¤Р°РєС‚. РґР»РёРЅР° РїСЂРѕРµР·РґР° = speed * t_end = {len_eff:.6g} Рј. "
                    f"(road_len_m РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ С‚РѕР»СЊРєРѕ РІ Р°РІС‚Рѕ-СЂРµР¶РёРјРµ)"
                )
                try:
                    if float(road_len_m) > 1e-9:
                        rel = abs(len_eff - float(road_len_m)) / max(float(road_len_m), 1e-9)
                        if rel > 0.05:
                            st.warning(
                                f"road_len_m = {float(road_len_m):.6g} Рј **РЅРµ РІР»РёСЏРµС‚**, РїРѕС‚РѕРјСѓ С‡С‚Рѕ Р°РІС‚Рѕ-СЂРµР¶РёРј РІС‹РєР»СЋС‡РµРЅ. "
                                f"РЎРµР№С‡Р°СЃ РїРѕ speed/t_end РїРѕР»СѓС‡Р°РµС‚СЃСЏ {len_eff:.6g} Рј."
                            )
                except Exception:
                    pass

            st.caption("РџСЂРѕС„РёР»СЊ РґРѕСЂРѕРіРё (WorldRoad)")
            surf_map = {
                "flat": "Р РѕРІРЅР°СЏ (flat)",
                "sine_x": "РЎРёРЅСѓСЃ РІРґРѕР»СЊ (sine_x)",
                "sine_y": "РЎРёРЅСѓСЃ РїРѕРїРµСЂС‘Рє (sine_y)",
                "bump": "Р‘СѓРіРѕСЂ (bump)",
                "ridge_x": "РџРѕСЂРѕРі (ridge_x)",
                "ridge_cosine_bump": "РљРѕСЃРёРЅСѓСЃРЅС‹Р№ Р±СѓРіРѕСЂ (ridge_cosine_bump)",
            }
            surf_type_default = str(st.session_state.get(_surface_type_key, "flat") or "flat")
            if surf_type_default not in surf_map:
                surf_type_default = "flat"
                st.session_state[_surface_type_key] = surf_type_default
            surf_type = st.selectbox(
                "РўРёРї РїРѕРІРµСЂС…РЅРѕСЃС‚Рё",
                options=list(surf_map.keys()),
                index=list(surf_map.keys()).index(surf_type_default),
                format_func=lambda _k: surf_map.get(str(_k), str(_k)),
                key=_surface_type_key,
            )

            if surf_type in {"sine_x", "sine_y"}:
                A = st.number_input("РђРјРїР»РёС‚СѓРґР° A (РїРѕР»СѓСЂР°Р·РјР°С…), Рј", min_value=0.0, step=0.005, format="%.6g", key=_surface_sine_a_key)
                st.caption(f"РЎРёРЅСѓСЃ Р·Р°РґР°С‘С‚СЃСЏ РєР°Рє z = AВ·sin(...). Р­С‚Рѕ Р·РЅР°С‡РёС‚: РїСЂРѕС„РёР»СЊ РёРґС‘С‚ РѕС‚ {-float(A):.6g} РґРѕ +{float(A):.6g} Рј, Р° РїРѕР»РЅС‹Р№ СЂР°Р·РјР°С… p-p = 2A = {2.0*float(A):.6g} Рј.")
                wl = st.number_input("Р”Р»РёРЅР° РІРѕР»РЅС‹, Рј", min_value=0.01, step=0.1, format="%.6g", key=_surface_sine_wl_key)
                spec_obj = {"type": surf_type, "A": float(A), "wavelength": float(wl)}
            elif surf_type in {"bump", "ridge_x"}:
                h = st.number_input("Р’С‹СЃРѕС‚Р° h, Рј", min_value=0.0, step=0.005, format="%.6g", key=_surface_hw_h_key)
                w = st.number_input("РЁРёСЂРёРЅР° w, Рј", min_value=0.01, step=0.05, format="%.6g", key=_surface_hw_w_key)
                spec_obj = {"type": surf_type, "h": float(h), "w": float(w)}
            elif surf_type == "ridge_cosine_bump":
                h = st.number_input("Р’С‹СЃРѕС‚Р° h, Рј", min_value=0.0, step=0.005, format="%.6g", key=_surface_cos_h_key)
                w = st.number_input("РЁРёСЂРёРЅР° w, Рј", min_value=0.01, step=0.05, format="%.6g", key=_surface_cos_w_key)
                k = st.number_input("Р¤РѕСЂРјР° k", min_value=0.1, step=0.1, format="%.6g", key=_surface_cos_k_key)
                spec_obj = {"type": surf_type, "h": float(h), "w": float(w), "k": float(k)}
            else:
                spec_obj = {"type": "flat"}

            road_surface = "flat" if spec_obj.get("type") == "flat" else json.dumps(spec_obj, ensure_ascii=False)

        else:
            road_surface = str(rec.get("road_surface", "flat") or "flat")
            auto_t_end_from_len = False
            t_end_effective = float(t_end)
            road_csv = st.text_input("РџСѓС‚СЊ Рє road_csv", key=_road_csv_key)
            axay_csv = st.text_input("РџСѓС‚СЊ Рє axay_csv", key=_axay_csv_key)

        st.markdown("#### РњР°РЅС‘РІСЂ (РµСЃР»Рё РїСЂРёРјРµРЅРёРјРѕ)")
        ax = st.number_input("ax, Рј/СЃВІ", step=0.1, format="%.6g", key=_ax_key)
        ay = st.number_input("ay, Рј/СЃВІ", step=0.1, format="%.6g", key=_ay_key)

        st.markdown("#### Р¦РµР»Рё/РѕРіСЂР°РЅРёС‡РµРЅРёСЏ (penalty targets)")
        st.caption(
            "РЁС‚СЂР°С„ РѕРїС‚РёРјРёР·Р°С†РёРё СѓС‡РёС‚С‹РІР°РµС‚ С‚РѕР»СЊРєРѕ target_*, РІРєР»СЋС‡С‘РЅРЅС‹Рµ РЅРёР¶Рµ. "
            "Р•СЃР»Рё РЅРёС‡РµРіРѕ РЅРµ РІРєР»СЋС‡РµРЅРѕ вЂ” penalty=0, РѕРїС‚РёРјРёР·Р°С†РёСЏ РјРѕР¶РµС‚ СЃС‚Р°С‚СЊ Р±РµСЃСЃРјС‹СЃР»РµРЅРЅРѕР№."
        )

        penalty_targets_cols: Dict[str, Any] = {}
        try:
            from pneumo_solver_ui.opt_worker_v3_margins_energy import PENALTY_TARGET_SPECS
        except Exception:
            PENALTY_TARGET_SPECS = []

        with st.expander("РЎРїРёСЃРѕРє penalty targets (target_*)", expanded=True):
            for _spec in (PENALTY_TARGET_SPECS or []):
                _k = str(_spec.get("key", "") or "").strip()
                if not _k:
                    continue
                _col = f"target_{_k}"
                label = str(_spec.get("label", _k))
                unit = str(_spec.get("unit", "")).strip()
                help_txt = str(_spec.get("help", "") or "")
                _en_key = _suite_editor_widget_key(sid, f"pen_tgt_en_{_k}")
                _val_key = _suite_editor_widget_key(sid, f"pen_tgt_val_{_k}")
                en = st.checkbox(
                    f"{label}{(' [' + unit + ']') if unit else ''}",
                    key=_en_key,
                    help=help_txt or None,
                )
                if en:
                    val = st.number_input(
                        f"Р—РЅР°С‡РµРЅРёРµ: {_col}",
                        step=0.1,
                        format="%.6g",
                        key=_val_key,
                        help=help_txt or None,
                    )
                    penalty_targets_cols[_col] = float(val)
                else:
                    penalty_targets_cols[_col] = None

        DEPRECATED_TARGET_COLS = [
            "target_clearance",
            "target_pmax_atm",
            "target_pmin_atm",
            "target_povershoot_frac",
        ]

        with st.expander("РџРµСЂРµРѕРїСЂРµРґРµР»РµРЅРёСЏ РїР°СЂР°РјРµС‚СЂРѕРІ (СЃС†РµРЅР°СЂРёР№)", expanded=True):
            params_override = st.text_area(
                "JSON (РЅРµРѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)",
                height=120,
                key=_params_override_key,
                help="РњРѕР¶РЅРѕ Р·Р°РґР°С‚СЊ JSON СЃРѕ Р·РЅР°С‡РµРЅРёСЏРјРё РїР°СЂР°РјРµС‚СЂРѕРІ, РєРѕС‚РѕСЂС‹Рµ Р±СѓРґСѓС‚ РїСЂРёРјРµРЅРµРЅС‹ С‚РѕР»СЊРєРѕ РІ СЌС‚РѕРј С‚РµСЃС‚Рµ.",
            )

        submitted = st.button("РџСЂРёРјРµРЅРёС‚СЊ РёР·РјРµРЅРµРЅРёСЏ", key=f"ui_suite_apply_btn_{sid}", width="stretch")

        if submitted:
            df_suite_edit.at[idx, "РІРєР»СЋС‡РµРЅ"] = bool(enabled)
            df_suite_edit.at[idx, "СЃС‚Р°РґРёСЏ"] = int(stage)
            df_suite_edit.at[idx, "РёРјСЏ"] = str(name)
            df_suite_edit.at[idx, "С‚РёРї"] = str(ttype)
            df_suite_edit.at[idx, "dt"] = float(dt)
            df_suite_edit.at[idx, "t_end"] = float(t_end_effective)
            df_suite_edit.at[idx, "auto_t_end_from_len"] = bool(auto_t_end_from_len)
            df_suite_edit.at[idx, "road_csv"] = str(road_csv)
            df_suite_edit.at[idx, "axay_csv"] = str(axay_csv)
            df_suite_edit.at[idx, "road_surface"] = str(road_surface)
            df_suite_edit.at[idx, "road_len_m"] = float(road_len_m)
            df_suite_edit.at[idx, "vx0_Рј_СЃ"] = float(vx0_mps)
            df_suite_edit.at[idx, "ax"] = float(ax)
            df_suite_edit.at[idx, "ay"] = float(ay)

            for _col, _val in (penalty_targets_cols or {}).items():
                df_suite_edit.at[idx, _col] = _val

            for _col in DEPRECATED_TARGET_COLS:
                if _col in df_suite_edit.columns:
                    df_suite_edit.at[idx, _col] = None

            df_suite_edit.at[idx, "params_override"] = str(params_override)
            df_suite_edit = ensure_suite_columns(df_suite_edit, context="pneumo_ui_app.suite_card_apply")
            st.session_state["df_suite_edit"] = df_suite_edit
            _queue_suite_selected_id(sid)
            _ensure_stage_visible_in_filter(stage)
            st.session_state["_ui_suite_autosave_pending"] = True
            _suite_set_flash("success", "РўРµСЃС‚ РѕР±РЅРѕРІР»С‘РЅ.")
            st.rerun()

# (РЅР° РІСЃСЏРєРёР№ СЃР»СѓС‡Р°Р№)
st.session_state["df_suite_edit"] = df_suite_edit


# РІР°Р»РёРґРёСЂСѓРµРј Рё СЃРѕР±РёСЂР°РµРј suite_override (list[dict])
suite_errors = []
SUITE_REQUIRED = ["РёРјСЏ", "С‚РёРї", "dt", "t_end"]

suite_override: List[Dict[str, Any]] = []
for i, row in df_suite_edit.iterrows():
    rec = {k: (None if (isinstance(v, float) and (pd.isna(v))) else v) for k, v in row.to_dict().items()}
    # РїСЂРѕРїСѓСЃРєР°РµРј РїРѕР»РЅРѕСЃС‚СЊСЋ РїСѓСЃС‚С‹Рµ СЃС‚СЂРѕРєРё
    if all((rec.get(k) in [None, "", False] for k in rec.keys())):
        continue

    enabled = bool(rec.get("РІРєР»СЋС‡РµРЅ", True))
    name = str(rec.get("РёРјСЏ", "")).strip()
    typ = str(rec.get("С‚РёРї", "")).strip()

    if enabled:
        if not name:
            suite_errors.append(f"РЎС‚СЂРѕРєР° {i+1}: РїСѓСЃС‚РѕРµ РёРјСЏ С‚РµСЃС‚Р°")
        if typ not in ALLOWED_TEST_TYPES:
            suite_errors.append(f"РўРµСЃС‚ '{name or i+1}': РЅРµРёР·РІРµСЃС‚РЅС‹Р№ С‚РёРї '{typ}'")
        try:
            dt_i = float(rec.get("dt"))
            if dt_i <= 0:
                suite_errors.append(f"РўРµСЃС‚ '{name}': dt РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ > 0")
        except Exception:
            suite_errors.append(f"РўРµСЃС‚ '{name}': dt РЅРµ Р·Р°РґР°РЅ")
        try:
            t_end_i = float(rec.get("t_end"))
            if t_end_i <= 0:
                suite_errors.append(f"РўРµСЃС‚ '{name}': t_end РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ > 0")
        except Exception:
            suite_errors.append(f"РўРµСЃС‚ '{name}': t_end РЅРµ Р·Р°РґР°РЅ")

        # С„РёР·РёРєР°: РґРѕР»СЏ РѕС‚СЂС‹РІР° 0..1
        if rec.get("target_РјР°РєСЃ_РґРѕР»СЏ_РѕС‚СЂС‹РІР°") is not None:
            try:
                frac = float(rec["target_РјР°РєСЃ_РґРѕР»СЏ_РѕС‚СЂС‹РІР°"])
                if not (0.0 <= frac <= 1.0):
                    suite_errors.append(f"РўРµСЃС‚ '{name}': target_РјР°РєСЃ_РґРѕР»СЏ_РѕС‚СЂС‹РІР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ 0..1")
            except Exception:
                suite_errors.append(f"РўРµСЃС‚ '{name}': target_РјР°РєСЃ_РґРѕР»СЏ_РѕС‚СЂС‹РІР° РЅРµРєРѕСЂСЂРµРєС‚РЅР°")

        # JSON sanity: road_surface / params_override (РµСЃР»Рё РїРѕС…РѕР¶Рµ РЅР° JSON вЂ” РїСЂРѕРІРµСЂСЏРµРј)
        for _fld in ("road_surface", "params_override"):
            _v = rec.get(_fld, None)
            if isinstance(_v, str):
                _s = _v.strip()
                if _s and ((_s.startswith('{') and _s.endswith('}')) or (_s.startswith('[') and _s.endswith(']'))):
                    try:
                        json.loads(_s)
                    except Exception as _e_json:
                        suite_errors.append(f"РўРµСЃС‚ '{name}': РїРѕР»Рµ '{_fld}' СЃРѕРґРµСЂР¶РёС‚ РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ JSON: {_e_json}")

        # sidecar sanity: CSV-С„Р°Р№Р»С‹ РґРѕР»Р¶РЅС‹ СЃСѓС‰РµСЃС‚РІРѕРІР°С‚СЊ (С‡С‚РѕР±С‹ РЅРµ Р±С‹Р»Рѕ В«С‚РёС…РёС…В» РЅСѓР»РµР№)
        if typ in ("road_profile_csv", "maneuver_csv", "csv", "worldroad"):
            for _csv_fld in ("road_csv", "axay_csv", "scenario_json"):
                _p = rec.get(_csv_fld, None)
                if not _p:
                    # road_csv РѕР±СЏР·Р°С‚РµР»РµРЅ РґР»СЏ road_profile_csv
                    if (_csv_fld == "road_csv") and (typ in ("road_profile_csv", "worldroad")):
                        suite_errors.append(f"РўРµСЃС‚ '{name}': РЅРµ Р·Р°РґР°РЅ road_csv")
                    continue
                try:
                    _pp = Path(str(_p))
                    if not _pp.is_absolute():
                        _pp = (ROOT_DIR / _pp).resolve()
                    if not _pp.exists():
                        suite_errors.append(f"РўРµСЃС‚ '{name}': С„Р°Р№Р» '{_csv_fld}' РЅРµ РЅР°Р№РґРµРЅ: {str(_p)}")
                except Exception as _e_p:
                    suite_errors.append(f"РўРµСЃС‚ '{name}': РЅРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ '{_csv_fld}': {_e_p}")

    suite_override.append(rec)

# Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ: РёРјРµРЅР° РІРєР»СЋС‡РµРЅРЅС‹С… С‚РµСЃС‚РѕРІ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ СѓРЅРёРєР°Р»СЊРЅС‹
try:
    _name_counts = {}
    for _r in suite_override:
        try:
            if not bool(_r.get('РІРєР»СЋС‡РµРЅ', True)):
                continue
            _nm = str(_r.get('РёРјСЏ', '')).strip()
            if not _nm:
                continue
            _name_counts[_nm] = _name_counts.get(_nm, 0) + 1
        except Exception:
            continue
    _dups = sorted([n for n, c in _name_counts.items() if c > 1])
    if _dups:
        suite_errors.append("Р”СѓР±Р»Рё РёРјС‘РЅ С‚РµСЃС‚РѕРІ (РІРєР»СЋС‡РµРЅРЅС‹С…): " + ", ".join(_dups))
except Exception:
    pass

if suite_errors:
    st.error("Р’ С‚РµСЃС‚-РЅР°Р±РѕСЂРµ РµСЃС‚СЊ РѕС€РёР±РєРё (РёСЃРїСЂР°РІСЊС‚Рµ РїРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј):\n- " + "\n- ".join(suite_errors))


# -------------------------------
# РћРґРёРЅРѕС‡РЅС‹Рµ С‚РµСЃС‚С‹
# -------------------------------
with colB:
    st.subheader("РћРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ С‚РµСЃС‚РѕРІ")
    st.caption("РџСЂРѕРІРµСЂРєР° Р°РґРµРєРІР°С‚РЅРѕСЃС‚Рё РјРѕРґРµР»Рё РЅР° С‚РµРєСѓС‰РёС… РїР°СЂР°РјРµС‚СЂР°С….")

    tests_cfg = {"suite": suite_override}
    tests: List[Tuple[str, Dict[str, Any], float, float, Dict[str, float]]] = []
    if not suite_errors:
        try:
            tests = worker_mod.build_test_suite(tests_cfg)
        except Exception as e:
            st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР±СЂР°С‚СЊ С‚РµСЃС‚вЂ‘РЅР°Р±РѕСЂ: {e}")
            tests = []

    # --- persistent baseline cache (auto-load after refresh / new session) ---
    # РљР»СЋС‡ РєСЌС€Р° Р·Р°РІРёСЃРёС‚ РѕС‚ base_override + suite (СЃ СѓС‡РµС‚РѕРј dt/t_end/targets) + model file.
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
            _stab_on = bool(base_override.get("СЃС‚Р°Р±РёР»РёР·Р°С‚РѕСЂ_РІРєР»", False))
            _baseline_summary = "РћРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ: РЅРµ РІС‹РїРѕР»РЅСЏР»СЃСЏ"
            try:
                _bdf = st.session_state.get("baseline_df")
                if _bdf is not None and hasattr(_bdf, "columns"):
                    if "pass" in _bdf.columns:
                        _n_total = int(len(_bdf))
                        _n_pass = int(_bdf["pass"].astype(int).sum())
                        _baseline_summary = f"РћРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ: {_n_pass}/{_n_total} РїСЂРѕР№РґРµРЅРѕ"
                    else:
                        _baseline_summary = f"РћРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ: {int(len(_bdf))} СЃС‚СЂРѕРє"
            except Exception:
                pass

            with truth_slot:
                c1, c2, c3, c4 = st.columns([1.25, 1.15, 1.05, 1.05])
                with c1:
                    st.markdown(f"**Release:** `{APP_RELEASE}`  \n**Model:** `{getattr(model_path, 'name', str(model_path))}`")
                    st.caption(_baseline_summary)
                with c2:
                    st.markdown(f"**base_hash:** `{_base_hash_preview}`  \n**suite_hash:** `{_suite_hash_preview}`")
                    st.caption(f"cache_dir: `{_cache_dir_preview.name}`")
                with c3:
                    st.markdown("**autoselfcheck:** вњ… OK" if _self_ok else "**autoselfcheck:** вќЊ FAIL")
                    if not _self_ok:
                        st.caption("РћРїС‚РёРјРёР·Р°С†РёСЏ Рё СЌРєСЃРїРѕСЂС‚ Р±СѓРґСѓС‚ Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅС‹ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ.")
                with c4:
                    st.markdown(f"**stabilizer:** {'ON' if _stab_on else 'OFF'}")
        except Exception:
            pass

        if st.session_state.baseline_df is None:
            _cached = load_baseline_cache(_cache_dir_preview)
            if _cached is not None:
                st.session_state.baseline_df = _cached["baseline_df"]
                st.session_state.baseline_tests_map = _cached["tests_map"]
                st.session_state.baseline_param_hash = _base_hash_preview
                # РґРµС‚Р°Р»СЊРЅС‹Рµ РїСЂРѕРіРѕРЅС‹ РЅРµ РіСЂСѓР·РёРј С†РµР»РёРєРѕРј вЂ” Р±СѓРґСѓС‚ РїРѕРґС…РІР°С‡РµРЅС‹ РїРѕ Р·Р°РїСЂРѕСЃСѓ
                log_event("baseline_loaded_cache", cache_dir=str(_cache_dir_preview))
                st.info(f"РћРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ Р·Р°РіСЂСѓР¶РµРЅ РёР· РєСЌС€Р°: {_cache_dir_preview.name}")
    except Exception:
        pass

    test_names = [x[0] for x in tests]
    pick = st.selectbox("РўРµСЃС‚", options=["(РІСЃРµ)"] + test_names, index=0)

    _disable_baseline = bool(suite_errors) or bool(param_errors) or (len(tests) == 0)
    if st.button("Р—Р°РїСѓСЃС‚РёС‚СЊ РѕРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ", disabled=_disable_baseline):
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
        # СЃРѕС…СЂР°РЅСЏРµРј РєР°СЂС‚Сѓ С‚РµСЃС‚РѕРІ (РїРѕРЅР°РґРѕР±РёС‚СЃСЏ РґР»СЏ РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°)
        st.session_state.baseline_tests_map = {
            name: {"test": dict(test), "dt": float(dt_i), "t_end": float(t_end_i), "targets": dict(targets)}
            for (name, test, dt_i, t_end_i, targets) in tests
        }
        st.session_state.baseline_param_hash = stable_obj_hash(base_override)
        st.session_state.baseline_full_cache = {}  # СЃР±СЂРѕСЃ РґРµС‚Р°Р»СЊРЅС‹С… РїСЂРѕРіРѕРЅРѕРІ (РїР°СЂР°РјРµС‚СЂС‹ РјРѕРіР»Рё РёР·РјРµРЅРёС‚СЊСЃСЏ)
        with st.spinner("РЎС‡РёС‚Р°СЋ..."):
            for name, test, dt_i, t_end_i, targets in tests:
                if pick != "(РІСЃРµ)" and name != pick:
                    continue
                try:
                    m = worker_mod.eval_candidate_once(model_mod, base_override, test, dt=dt_i, t_end=t_end_i)
                    m["С‚РµСЃС‚"] = name
                    m["РѕРїРёСЃР°РЅРёРµ"] = test.get("РѕРїРёСЃР°РЅРёРµ", "")
                    pen_targets = float(worker_mod.candidate_penalty(m, targets))
                    try:
                        pen_verif = float(m.get("РІРµСЂРёС„РёРєР°С†РёСЏ_С€С‚СЂР°С„", 0.0))
                    except Exception:
                        pen_verif = 0.0

                    m["С€С‚СЂР°С„_С†РµР»Рё"] = float(pen_targets)
                    m["С€С‚СЂР°С„_РІРµСЂРёС„РёРєР°С†РёСЏ"] = float(pen_verif)
                    m["С€С‚СЂР°С„"] = float(pen_targets + pen_verif)

                    # Р§РёС‚Р°Р±РµР»СЊРЅС‹Рµ С„Р»Р°РіРё РїСЂРѕС…РѕР¶РґРµРЅРёСЏ
                    try:
                        m["pass_РІРµСЂРёС„РёРєР°С†РёСЏ"] = int(int(m.get("РІРµСЂРёС„РёРєР°С†РёСЏ_ok", 1)) == 1)
                    except Exception:
                        m["pass_РІРµСЂРёС„РёРєР°С†РёСЏ"] = 0
                    m["pass_С†РµР»Рё"] = int(float(pen_targets) <= 0.0)
                    m["pass"] = int((m["pass_РІРµСЂРёС„РёРєР°С†РёСЏ"] == 1) and (m["pass_С†РµР»Рё"] == 1))
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
                        "С‚РµСЃС‚": name,
                        "РѕС€РёР±РєР°": str(e),
                        "С€С‚СЂР°С„": 1e9,
                        "С€С‚СЂР°С„_С†РµР»Рё": 1e9,
                        "С€С‚СЂР°С„_РІРµСЂРёС„РёРєР°С†РёСЏ": 0.0,
                        "pass": 0,
                        "pass_РІРµСЂРёС„РёРєР°С†РёСЏ": 0,
                        "pass_С†РµР»Рё": 0,
                    }
                    err_row.update(packaging_error_surface_metrics())
                    res_rows.append(err_row)
        df_res = pd.DataFrame(res_rows)
        st.session_state.baseline_df = df_res
        safe_dataframe(df_res, height=360)
        st.success(f"Р“РѕС‚РѕРІРѕ. РћС€РёР±РѕРє: {err_cnt}")

        log_event(
            "baseline_end",
            errors=int(err_cnt),
            rows=int(len(df_res)),
            elapsed_s=float(time.perf_counter() - t0_baseline),
            proc=_proc_metrics(),
        )

        # РѕС‚РјРµС‚РєР°: baseline РѕР±РЅРѕРІРёР»СЃСЏ (РґР»СЏ Р°РІС‚Рѕ-РґРµС‚Р°Р»СЊРЅРѕРіРѕ С‚СЂРёРіРіРµСЂР°)
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

        # Р±С‹СЃС‚СЂС‹Р№ sanity-check: РІР°РєСѓСѓРј/РґР°РІР»РµРЅРёСЏ
        if "pR3_max_Р±Р°СЂ" in df_res.columns:
            st.write("РњР°РєСЃ РґР°РІР»РµРЅРёРµ Р 3 (Р±Р°СЂ abs):", float(df_res["pR3_max_Р±Р°СЂ"].max()))


# -------------------------------
# РћР±Р·РѕСЂ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° (Р±С‹СЃС‚СЂС‹Рµ РјРµС‚СЂРёРєРё + РіРµР№С‚С‹ С‚СЏР¶С‘Р»С‹С… РІРёР·СѓР°Р»РёР·Р°С†РёР№)
# -------------------------------
if st.session_state.get("baseline_df") is not None:
    _bdf = st.session_state["baseline_df"]
    if isinstance(_bdf, pd.DataFrame) and not _bdf.empty:
        try:
            _n_total = int(len(_bdf))
            _n_pass = int((_bdf.get("pass", False) == True).sum()) if "pass" in _bdf.columns else None  # noqa: E712
            _n_fail = (_n_total - _n_pass) if _n_pass is not None else None

            _best_pen = None
            if "С€С‚СЂР°С„" in _bdf.columns:
                _best_pen = float(pd.to_numeric(_bdf["С€С‚СЂР°С„"], errors="coerce").min())
            elif "penalty" in _bdf.columns:
                _best_pen = float(pd.to_numeric(_bdf["penalty"], errors="coerce").min())

            cM1, cM2, cM3, cM4 = st.columns(4)
            with cM1:
                st.metric("РћРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ: С‚РµСЃС‚РѕРІ", _n_total)
            with cM2:
                st.metric("РџСЂРѕС€Р»Рѕ", _n_pass if _n_pass is not None else "вЂ”")
            with cM3:
                st.metric("РџСЂРѕРІР°Р»", _n_fail if _n_fail is not None else "вЂ”")
            with cM4:
                st.metric("Р›СѓС‡С€РёР№ С€С‚СЂР°С„", f"{_best_pen:.3g}" if _best_pen is not None and np.isfinite(_best_pen) else "вЂ”")

            with st.expander("Р’РёР·СѓР°Р»СЊРЅС‹Р№ РѕР±Р·РѕСЂ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° (РіСЂР°С„РёРєРё/С‚РµРїР»РѕРєР°СЂС‚Р°)", expanded=False):
                st.caption(
                    "РЎРІРѕРґРЅС‹Рµ РіСЂР°С„РёРєРё РІРєР»СЋС‡Р°СЋС‚СЃСЏ С‡РµРєР±РѕРєСЃР°РјРё РЅРёР¶Рµ. "
                    "Р’Р°Р¶РЅРѕ: expander СЃР°Рј РїРѕ СЃРµР±Рµ РЅРµ В«РѕСЃС‚Р°РЅР°РІР»РёРІР°РµС‚В» РєРѕРґ, РїРѕСЌС‚РѕРјСѓ РґР»СЏ СЃРєРѕСЂРѕСЃС‚Рё РёСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ РіРµР№С‚С‹."
                )

                _ov_c1, _ov_c2 = st.columns([1, 1])
                with _ov_c1:
                    _show_overview_plot = st.checkbox(
                        "РџРѕРєР°Р·С‹РІР°С‚СЊ РіСЂР°С„РёРє С…СѓРґС€РёС… С‚РµСЃС‚РѕРІ",
                        value=False,
                        help="РЎС‚СЂРѕРёС‚ PlotlyвЂ‘РіСЂР°С„РёРє РїРѕ С…СѓРґС€РёРј С‚РµСЃС‚Р°Рј (РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚СЏР¶РµР»Рѕ РЅР° Р±РѕР»СЊС€РёС… РЅР°Р±РѕСЂР°С…).",
                        key="gate_baseline_overview_plot",
                    )
                    _show_full_table = st.checkbox(
                        "РџРѕРєР°Р·С‹РІР°С‚СЊ С‚Р°Р±Р»РёС†Сѓ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ (РїРѕР»РЅРѕСЃС‚СЊСЋ)",
                        value=False,
                        help="РџРѕРєР°Р·С‹РІР°РµС‚ РёСЃС…РѕРґРЅСѓСЋ С‚Р°Р±Р»РёС†Сѓ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°. "
                             "РџСЂРё Р±РѕР»СЊС€РёС… С‚Р°Р±Р»РёС†Р°С… РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚СЏР¶РµР»Рѕ.",
                        key="gate_baseline_overview_table_full",
                    )
                with _ov_c2:
                    _show_penalty_heatmap = st.checkbox(
                        "РџРѕРєР°Р·С‹РІР°С‚СЊ С‚РµРїР»РѕРєР°СЂС‚Сѓ С€С‚СЂР°С„РѕРІ",
                        value=False,
                        help="РЎС‚СЂРѕРёС‚ С‚РµРїР»РѕРєР°СЂС‚Сѓ С€С‚СЂР°С„РѕРІ/РєСЂРёС‚РµСЂРёРµРІ (pen_*). Р РµРЅРґРµСЂ Plotly РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚СЏР¶С‘Р»С‹Рј.",
                        key="gate_baseline_overview_heatmap",
                    )
                    _show_penalty_table = st.checkbox(
                        "РџРѕРєР°Р·С‹РІР°С‚СЊ С‚Р°Р±Р»РёС†Сѓ С€С‚СЂР°С„РѕРІ (pen_*)",
                        value=False,
                        help="РџРѕРєР°Р·С‹РІР°РµС‚ С‚Р°Р±Р»РёС†Сѓ pen_* РїРѕ С‚РµСЃС‚Р°Рј (СѓРґРѕР±РЅРѕ РґР»СЏ СЌРєСЃРїРѕСЂС‚Р°/РїСЂРѕРІРµСЂРѕРє).",
                        key="gate_baseline_overview_table_pen",
                    )

                # РҐСѓРґС€РёРµ С‚РµСЃС‚С‹ РїРѕ СЃСѓРјРјР°СЂРЅРѕРјСѓ С€С‚СЂР°С„Сѓ (РґРµС€РµРІРѕ)
                _bdf2 = _bdf.copy()
                if "penalty" not in _bdf2.columns:
                    _bdf2["penalty"] = 0.0
                _bdf2["penalty"] = pd.to_numeric(_bdf2["penalty"], errors="coerce").fillna(0.0)
                _bdf2 = _bdf2.sort_values("penalty", ascending=False)

                _worst = _bdf2.head(10)
                _pairs = [(str(r.get("test_id", "?")), float(r.get("penalty", 0.0))) for _, r in _worst.iterrows()]
                st.write("РҐСѓРґС€РёРµ С‚РµСЃС‚С‹ РїРѕ СЃСѓРјРјР°СЂРЅРѕРјСѓ С€С‚СЂР°С„Сѓ:", ", ".join([f"{tid} ({pen:.3g})" for tid, pen in _pairs]))

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

                # 1) Р“СЂР°С„РёРє С…СѓРґС€РёС… С‚РµСЃС‚РѕРІ
                if _show_overview_plot:
                    if not _HAS_PLOTLY:
                        st.warning("Plotly РЅРµРґРѕСЃС‚СѓРїРµРЅ: РіСЂР°С„РёРє РЅРµ РїРѕСЃС‚СЂРѕРµРЅ.")
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
                                    name="РЁС‚СЂР°С„",
                                )
                            )
                            _fig.update_layout(
                                title="РҐСѓРґС€РёРµ С‚РµСЃС‚С‹ (СЃСѓРјРјР°СЂРЅС‹Р№ С€С‚СЂР°С„)",
                                xaxis_title="РўРµСЃС‚",
                                yaxis_title="РЁС‚СЂР°С„ (Р±РµР·СЂР°Р·Рј.)",
                                height=340,
                                margin=dict(l=20, r=20, t=60, b=40),
                            )
                            return _fig

                        safe_plotly_chart(_render_cached_plotly(_key, _build))

                # 2) РўРµРїР»РѕРєР°СЂС‚Р° С€С‚СЂР°С„РѕРІ pen_*
                if _show_penalty_heatmap:
                    if not _HAS_PLOTLY:
                        st.warning("Plotly РЅРµРґРѕСЃС‚СѓРїРµРЅ: С‚РµРїР»РѕРєР°СЂС‚Р° РЅРµ РїРѕСЃС‚СЂРѕРµРЅР°.")
                    else:
                        _crit_cols = [c for c in _bdf.columns if c.startswith("pen_")]
                        if not _crit_cols:
                            st.info("РќРµС‚ РїРѕР»РµР№ pen_* вЂ” С‚РµРїР»РѕРєР°СЂС‚Р° С€С‚СЂР°С„РѕРІ РЅРµРґРѕСЃС‚СѓРїРЅР°.")
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
                                    labels=dict(x="РўРµСЃС‚", y="РљСЂРёС‚РµСЂРёР№", color="РЁС‚СЂР°С„"),
                                    title="РўРµРїР»РѕРєР°СЂС‚Р° С€С‚СЂР°С„РѕРІ (pen_*)",
                                )
                                _fig.update_layout(height=420, margin=dict(l=20, r=20, t=70, b=40))
                                return _fig

                            safe_plotly_chart(_render_cached_plotly(_key, _build))

                # 3) РўР°Р±Р»РёС†С‹ (РіРµР№С‚С‹)
                if _show_penalty_table:
                    _crit_cols = [c for c in _bdf.columns if c.startswith("pen_")]
                    if _crit_cols:
                        st.caption("РўР°Р±Р»РёС†Р° С€С‚СЂР°С„РѕРІ РїРѕ РєСЂРёС‚РµСЂРёСЏРј (pen_*)")
                        _hm_df = _bdf[_crit_cols + ["test_id"]].set_index("test_id")
                        _hm_df = _hm_df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
                        st.dataframe(_hm_df, width="stretch", height=280)
                    else:
                        st.info("РќРµС‚ РїРѕР»РµР№ pen_* вЂ” С‚Р°Р±Р»РёС†Р° С€С‚СЂР°С„РѕРІ РЅРµРґРѕСЃС‚СѓРїРЅР°.")

                if _show_full_table:
                    st.caption("РўР°Р±Р»РёС†Р° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° (РєР°Рє РµСЃС‚СЊ)")
                    st.dataframe(_bdf, width="stretch", height=360)

        except Exception as _e:
            st.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕСЃС‚СЂРѕРёС‚СЊ РѕР±Р·РѕСЂ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°: {_e}")

# Р”РµС‚Р°Р»СЊРЅС‹Рµ РіСЂР°С„РёРєРё + Р°РЅРёРјР°С†РёСЏ (baseline)
# -------------------------------
st.divider()
st.header("Р“СЂР°С„РёРєРё Рё Р°РЅРёРјР°С†РёСЏ (РѕРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ)")
st.caption(
    "РЎРЅР°С‡Р°Р»Р° Р·Р°РїСѓСЃС‚РёС‚Рµ РѕРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ. Р—Р°С‚РµРј РІС‹Р±РµСЂРёС‚Рµ РѕРґРёРЅ С‚РµСЃС‚ Рё РїРѕР»СѓС‡РёС‚Рµ РїРѕР»РЅС‹Р№ Р»РѕРі (record_full=True): "
    "РіСЂР°С„РёРєРё P/Q/РєСЂРµРЅ/С‚Р°РЅРіР°Р¶/СЃРёР»С‹ Рё MVP-Р°РЅРёРјР°С†РёСЋ РїРѕС‚РѕРєРѕРІ."
)

cur_hash = stable_obj_hash(base_override)
if st.session_state.baseline_df is None:
    st.info("РќРµС‚ С‚Р°Р±Р»РёС†С‹ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°. РќР°Р¶РјРёС‚Рµ В«Р—Р°РїСѓСЃС‚РёС‚СЊ РѕРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅВ» РІС‹С€Рµ.")
elif st.session_state.baseline_param_hash and st.session_state.baseline_param_hash != cur_hash:
    st.warning(
        "РџР°СЂР°РјРµС‚СЂС‹ РёР·РјРµРЅРёР»РёСЃСЊ РїРѕСЃР»Рµ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°. Р§С‚РѕР±С‹ РіСЂР°С„РёРєРё/Р°РЅРёРјР°С†РёСЏ СЃРѕРѕС‚РІРµС‚СЃС‚РІРѕРІР°Р»Рё С‚РµРєСѓС‰РёРј РїР°СЂР°РјРµС‚СЂР°Рј, "
        "РїРµСЂРµР·Р°РїСѓСЃС‚РёС‚Рµ РѕРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ."
    )
else:
    tests_map = st.session_state.baseline_tests_map or {}
    # --- live suite -> tests_map (С‡С‚РѕР±С‹ РёР·РјРµРЅРµРЅРёСЏ С‚РµСЃС‚РѕРІ РїСЂРёРјРµРЅСЏР»РёСЃСЊ СЃСЂР°Р·Сѓ, Р±РµР· РѕР±СЏР·Р°С‚РµР»СЊРЅРѕРіРѕ baseline) ---
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
        st.info("Р’ С‚Р°Р±Р»РёС†Рµ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° РЅРµС‚ РґРѕСЃС‚СѓРїРЅС‹С… С‚РµСЃС‚РѕРІ (РїСЂРѕРІРµСЂСЊС‚Рµ С‚РµСЃС‚вЂ‘РЅР°Р±РѕСЂ).")
    else:
        colG1, colG2 = st.columns([1.35, 0.65], gap="large")
        with colG1:
            test_pick = st.selectbox("РўРµСЃС‚ РґР»СЏ РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°", options=avail, index=0, key="detail_test_pick")

        # Р Р°СЃС€РёСЂРµРЅРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё вЂ” РїСЂСЏС‡РµРј, С‡С‚РѕР±С‹ РіР»Р°РІРЅС‹Р№ СЌРєСЂР°РЅ РЅРµ Р·Р°С…Р»Р°РјР»СЏС‚СЊ
        with colG2:
            with ui_popover("вљ™пёЏ РќР°СЃС‚СЂРѕР№РєРё РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°"):
                max_points = st.slider(
                    "РњР°РєСЃ С‚РѕС‡РµРє (downsample)",
                    min_value=200,
                    max_value=5000,
                    value=int(st.session_state.get("detail_max_points", 1200) or 1200),
                    step=100,
                    key="detail_max_points",
                    help="РњРµРЅСЊС€Рµ вЂ” Р±С‹СЃС‚СЂРµРµ UI/РіСЂР°С„РёРєРё; Р±РѕР»СЊС€Рµ вЂ” С‚РѕС‡РЅРµРµ С„РѕСЂРјР° СЃРёРіРЅР°Р»РѕРІ.",
                )
                want_full = st.checkbox(
                    "record_full (РїРѕС‚РѕРєРё/СЃРѕСЃС‚РѕСЏРЅРёСЏ)",
                    value=bool(st.session_state.get("detail_want_full", True)),
                    key="detail_want_full",
                )
                auto_detail_on_select = st.checkbox(
                    "РђРІС‚Рѕ-СЂР°СЃС‡С‘С‚ РїСЂРё РІС‹Р±РѕСЂРµ С‚РµСЃС‚Р°",
                    value=bool(st.session_state.get("auto_detail_on_select", True)),
                    key="auto_detail_on_select",
                    help="Р•СЃР»Рё РІРєР»СЋС‡РµРЅРѕ Рё РєСЌС€ РїСѓСЃС‚, Р±СѓРґРµС‚ СЃС‡РёС‚Р°С‚СЊСЃСЏ РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ (РјРѕР¶РµС‚ РіСЂСѓР·РёС‚СЊ CPU).",
                )
                st.divider()
                st.caption("Р­РєСЃРїРѕСЂС‚ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)")
                auto_export_npz = st.checkbox(
                    "РђРІС‚Рѕ-СЌРєСЃРїРѕСЂС‚ NPZ (osc_dir)",
                    value=bool(st.session_state.get("auto_export_npz", True)),
                    key="auto_export_npz",
                    help="Р­РєСЃРїРѕСЂС‚РёСЂСѓРµС‚ Txx_osc.npz РІ РїР°РїРєСѓ osc_dir (СЃРј. РљР°Р»РёР±СЂРѕРІРєР°). РќСѓР¶РЅРѕ РґР»СЏ oneclick/autopilot.",
                )

                st.caption('Desktop Animator (follow)')
                st.checkbox(
                    'РђРІС‚Рѕ-СЌРєСЃРїРѕСЂС‚ anim_latest (Desktop Animator)',
                    value=bool(st.session_state.get('auto_export_anim_latest', True)),
                    key='auto_export_anim_latest',
                    help=(
                        'РџРѕСЃР»Рµ РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° СЃРѕС…СЂР°РЅСЏРµС‚ workspace/exports/anim_latest.npz Рё anim_latest.json (pointer). '
                        'Desktop Animator РІ follow-СЂРµР¶РёРјРµ РїРѕРґС…РІР°С‚РёС‚ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё.'
                    ),
                )
                st.checkbox(
                    'РђРІС‚Рѕ-Р·Р°РїСѓСЃРє Desktop Animator РїСЂРё СЌРєСЃРїРѕСЂС‚Рµ',
                    value=bool(st.session_state.get('auto_launch_animator', False)),
                    key='auto_launch_animator',
                    help='Р•СЃР»Рё СЃСЂРµРґР° РїРѕР·РІРѕР»СЏРµС‚ Р·Р°РїСѓСЃРє GUI: РѕС‚РєСЂРѕРµС‚ Desktop Animator (follow) СЃСЂР°Р·Сѓ РїРѕСЃР»Рµ СЌРєСЃРїРѕСЂС‚Р°.',
                )
                st.caption(f'РџР°РїРєР° exports: {WORKSPACE_EXPORTS_DIR}')

        # dt/t_end Р±РµСЂС‘Рј РёР· suite РґР»СЏ РІС‹Р±СЂР°РЅРЅРѕРіРѕ С‚РµСЃС‚Р° вЂ” СЌС‚Рѕ С‡Р°СЃС‚СЊ cache_key Рё РїР°СЂР°РјРµС‚СЂРѕРІ simulate()
        info_pick = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
        detail_dt = float(info_pick.get("dt", 0.01) or 0.01)
        detail_t_end = float(info_pick.get("t_end", 1.0) or 1.0)
        # СЃРѕС…СЂР°РЅСЏРµРј РґР»СЏ РґСЂСѓРіРёС… СЃС‚СЂР°РЅРёС†/РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ
        st.session_state["detail_dt_pick"] = detail_dt
        st.session_state["detail_t_end_pick"] = detail_t_end

        # --- Р”Р•РўРђР›Р¬РќР«Р™ РџР РћР“РћРќ: РёРЅРґРёРєР°С‚РѕСЂ РІС‹РїРѕР»РЅРµРЅРёСЏ Рё Р±Р»РѕРєРёСЂРѕРІРєР° РїРѕРІС‚РѕСЂРЅРѕРіРѕ Р·Р°РїСѓСЃРєР° ---
        # Р’Р°Р¶РЅРѕ: detail_guard вЂ” СЃР»СѓР¶РµР±РЅР°СЏ СЃС‚СЂСѓРєС‚СѓСЂР° UI (РќР• РїР°СЂР°РјРµС‚СЂС‹ РјРѕРґРµР»Рё).
        # РџРѕР»СЏ stage/progress/ts СЏРІР»СЏСЋС‚СЃСЏ РїСЂРѕРёР·РІРѕРґРЅС‹РјРё РѕС‚ СЃРѕСЃС‚РѕСЏРЅРёСЏ РІС‹РїРѕР»РЅРµРЅРёСЏ.
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
            st.info(f"Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ СѓР¶Рµ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ ({_stage}). РџСЂРѕС€Р»Рѕ: {_elapsed:.0f} СЃ")
            try:
                _p = int(_dg_ui.get("progress") or 0)
            except Exception:
                _p = 0
            _p_clamped = min(max(_p, 0), 100)
            st.progress(_p_clamped, text=f"{_stage} вЂ” {_p_clamped}%")
            st.caption("РџРѕРІС‚РѕСЂРЅС‹Р№ Р·Р°РїСѓСЃРє РїРѕРґР°РІР»РµРЅ, РїРѕРєР° С‚РµРєСѓС‰РёР№ РїСЂРѕРіРѕРЅ РЅРµ Р·Р°РІРµСЂС€РёС‚СЃСЏ.")

        run_detail = st.button("Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Рё РїРѕРєР°Р·Р°С‚СЊ", key="run_detail", disabled=_detail_in_progress)

        colDAll1, colDAll2 = st.columns([1.0, 1.0])
        with colDAll1:
            run_detail_all = st.button("Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Р”Р›РЇ Р’РЎР•РҐ С‚РµСЃС‚РѕРІ", key="run_detail_all", disabled=_detail_in_progress)
        with colDAll2:
            export_npz_all = st.button("Р­РєСЃРїРѕСЂС‚ NPZ Р”Р›РЇ Р’РЎР•РҐ (РёР· РєСЌС€Р°)", key="export_npz_all", disabled=_detail_in_progress)

            cache_key = make_detail_cache_key(cur_hash, test_pick, detail_dt, detail_t_end, max_points, want_full)

        # --- РђРІС‚Рѕ-РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: Р·Р°РїСѓСЃРєР°С‚СЊ РўРћР›Р¬РљРћ РїРѕ С‚СЂРёРіРіРµСЂСѓ
        # РўСЂРёРіРіРµСЂС‹:
        #   1) СЃРјРµРЅР° С‚РµСЃС‚Р° (test_pick)
        #   2) Р·Р°РІРµСЂС€РµРЅРёРµ baseline (one-shot С„Р»Р°Рі baseline_just_ran)
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

        # РњР°СЃСЃРѕРІС‹Рµ РґРµР№СЃС‚РІРёСЏ
        # - РїРѕР»РЅС‹Р№ Р»РѕРі РґР»СЏ РІСЃРµС… С‚РµСЃС‚РѕРІ
        # - СЌРєСЃРїРѕСЂС‚ NPZ РґР»СЏ РІСЃРµС… С‚РµСЃС‚РѕРІ
        if run_detail_all:
            if not want_full:
                st.warning("Р”Р»СЏ РјР°СЃСЃРѕРІРѕРіРѕ СЂР°СЃС‡С‘С‚Р° РІРєР»СЋС‡Рё record_full (РїРѕС‚РѕРєРё/СЃРѕСЃС‚РѕСЏРЅРёСЏ) вЂ” РёРЅР°С‡Рµ NPZ Р±СѓРґРµС‚ РЅРµРїРѕР»РЅС‹Р№.")
            else:
                with st.spinner("РЎС‡РёС‚Р°СЋ РїРѕР»РЅС‹Р№ Р»РѕРі РґР»СЏ РІСЃРµС… С‚РµСЃС‚РѕРІвЂ¦ (РјРѕР¶РµС‚ Р±С‹С‚СЊ РґРѕР»РіРѕ)"):
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
                                    st.warning(f"NPZ СЌРєСЃРїРѕСЂС‚ РЅРµ СѓРґР°Р»СЃСЏ РґР»СЏ {tn}: {_e}")
                        except Exception as e:
                            st.error(f"РћС€РёР±РєР° РІ С‚РµСЃС‚Рµ {tn}: {e}")
                        prog.progress(j / n_total)
                    prog.empty()
                log_event("detail_all_done", n_tests=len(avail), want_full=bool(want_full), max_points=int(max_points))

        if export_npz_all:
            if not want_full:
                st.warning("Р­РєСЃРїРѕСЂС‚ NPZ РёРјРµРµС‚ СЃРјС‹СЃР» С‚РѕР»СЊРєРѕ РїСЂРё record_full=True (РёРЅР°С‡Рµ РЅРµС‚ p/q/open).")
            else:
                with st.spinner("Р­РєСЃРїРѕСЂС‚РёСЂСѓСЋ NPZ РґР»СЏ РІСЃРµС… С‚РµСЃС‚РѕРІ, РєРѕС‚РѕСЂС‹Рµ СѓР¶Рµ РїРѕСЃС‡РёС‚Р°РЅС‹вЂ¦"):
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
                            st.warning(f"NPZ СЌРєСЃРїРѕСЂС‚ РЅРµ СѓРґР°Р»СЃСЏ РґР»СЏ {tn}: {e}")
                        prog.progress(j / n_total)
                    prog.empty()
                log_event("export_npz_all_done", n_tests=len(avail), max_points=int(max_points))
        if run_detail and test_pick:
            st.session_state.baseline_full_cache.pop(cache_key, None)

        if test_pick:
            # --- autorun guard: protects from endless rerun-loops (autorefresh / playhead sync / РєРѕРјРїРѕРЅРµРЅС‚С‹) ---
            # Р’Р°Р¶РЅРѕ: auto_detail РјРѕР¶РµС‚ РІС‹Р·С‹РІР°С‚СЊСЃСЏ РјРЅРѕРіРѕ СЂР°Р· РёР·-Р·Р° С‡Р°СЃС‚С‹С… rerun'РѕРІ. Р•СЃР»Рё РєСЌС€ РїРѕ РєР°РєРѕР№-С‚Рѕ РїСЂРёС‡РёРЅРµ
            # РЅРµ СѓРґРµСЂР¶РёРІР°РµС‚СЃСЏ, РїРѕР»СѓС‡РёС‚СЃСЏ Р±РµСЃРєРѕРЅРµС‡РЅС‹Р№ В«РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅВ». Р­С‚РѕС‚ guard РїРѕРґР°РІР»СЏРµС‚ РїРѕРІС‚РѕСЂРЅС‹Рµ Р°РІС‚РѕР·Р°РїСѓСЃРєРё.
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
                    st.info("РџРѕСЃР»Рµ СЃРІРµР¶РµРіРѕ baseline РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅС‹Р№ РїРµСЂРµСЃС‡С‘С‚ РґРµС‚Р°Р»СЊРЅРѕРіРѕ Р»РѕРіР°: СЃС‚Р°СЂС‹Р№ detail cache РґР»СЏ СЌС‚РѕРіРѕ С‚РµСЃС‚Р° РёРіРЅРѕСЂРёСЂСѓРµС‚СЃСЏ.")
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
                        st.info("Р”РµС‚Р°Р»СЊРЅС‹Р№ Р»РѕРі РґР»СЏ С‚РµРєСѓС‰РµРіРѕ С‚РµСЃС‚Р° Р·Р°РіСЂСѓР¶РµРЅ РёР· РєСЌС€Р°. Р”Р»СЏ РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРіРѕ РїРµСЂРµСЃС‡С‘С‚Р° РЅР°Р¶РјРёС‚Рµ 'Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Рё РїРѕРєР°Р·Р°С‚СЊ'.")
            except Exception:
                pass


            auto_pending_key = st.session_state.get("detail_auto_pending")
            auto_trigger = bool(auto_detail_on_select and auto_pending_key == cache_key)

            if cache_key not in st.session_state.baseline_full_cache and (run_detail or auto_trigger):
                if auto_trigger and not run_detail:
                    st.session_state["detail_auto_pending"] = None
                # --- autorun guard: protects from endless rerun-loops (autorefresh / playhead sync / РєРѕРјРїРѕРЅРµРЅС‚С‹) ---
                # Р•СЃР»Рё РїРѕ РєР°РєРѕР№-С‚Рѕ РїСЂРёС‡РёРЅРµ Streamlit РґРµР»Р°РµС‚ С‡Р°СЃС‚С‹Рµ rerun'С‹, auto_detail РјРѕР¶РµС‚ СЃС‚Р°СЂС‚РѕРІР°С‚СЊ СЃРЅРѕРІР° Рё СЃРЅРѕРІР°.
                # РњС‹:
                #  - РЅРµ Р·Р°РїСѓСЃРєР°РµРј РІС‚РѕСЂРѕР№ СЂР°СЃС‡С‘С‚, РµСЃР»Рё С‚Р°РєРѕР№ Р¶Рµ СѓР¶Рµ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ
                #  - РїРѕРґР°РІР»СЏРµРј РїРѕРІС‚РѕСЂРЅС‹Р№ Р°РІС‚РѕР·Р°РїСѓСЃРє С‚РѕРіРѕ Р¶Рµ cache_key РІСЃРєРѕСЂРµ РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ (СЃРёРјРїС‚РѕРј rerun-loop)
                #  - РІСЃРµРіРґР° СЃР±СЂР°СЃС‹РІР°РµРј С„Р»Р°Рі in_progress РІ finally
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
                # Streamlit РІС‹РїРѕР»РЅСЏРµС‚ СЃРєСЂРёРїС‚ РґР»СЏ РѕРґРЅРѕР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРѕР№ СЃРµСЃСЃРёРё РїРѕСЃР»РµРґРѕРІР°С‚РµР»СЊРЅРѕ
                # (Р±РµР· РїР°СЂР°Р»Р»РµР»СЊРЅС‹С… Р·Р°РїСѓСЃРєРѕРІ). РџРѕСЌС‚РѕРјСѓ in_progress=True, РѕР±РЅР°СЂСѓР¶РµРЅРЅС‹Р№ РІ РЅР°С‡Р°Р»Рµ
                # РЅРѕРІРѕРіРѕ Р·Р°РїСѓСЃРєР°, СЃС‡РёС‚Р°РµРј "Р·Р°Р»РёРїС€РёРј" СЃС‚Р°С‚СѓСЃРѕРј РїРѕСЃР»Рµ РїСЂРµСЂС‹РІР°РЅРёСЏ/РєСЂСЌС€Р° Рё
                # СЃР±СЂР°СЃС‹РІР°РµРј, РёРЅР°С‡Рµ РєРЅРѕРїРєР° РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° РјРѕР¶РµС‚ РЅР°РІСЃРµРіРґР° Р±Р»РѕРєРёСЂРѕРІР°С‚СЊСЃСЏ.
                _cur_pid = os.getpid()
                _guard_pid = int(_dg.get("pid") or _cur_pid)
                _start_ts = float(_dg.get("last_start_ts") or 0.0)
                _age = (_now - _start_ts) if (_start_ts > 0.0) else 0.0
                _had_in_progress = bool(_dg.get("in_progress"))
                if _had_in_progress:
                    st.warning("вљ пёЏ РћР±РЅР°СЂСѓР¶РµРЅ Р·Р°РІРёСЃС€РёР№/СѓСЃС‚Р°СЂРµРІС€РёР№ С„Р»Р°Рі 'РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ' вЂ” СЃР±СЂР°СЃС‹РІР°СЋ Р±Р»РѕРєРёСЂРѕРІРєСѓ.")
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

                # Р—Р°С‰РёС‚Р° РѕС‚ РґРІРѕР№РЅРѕРіРѕ РєР»РёРєР°: РІС‚РѕСЂРѕР№ Р·Р°РїСѓСЃРє С‚РѕР№ Р¶Рµ РєРЅРѕРїРєРё СЃСЂР°Р·Сѓ РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ РїСЂРѕРіРѕРЅР°.
                _double_click_suppressed = bool(run_detail) and _same_key and (_now - float(_dg.get("last_end_ts") or 0.0) < 2.0)
                if _double_click_suppressed:
                    st.info("РџРѕРІС‚РѕСЂРЅС‹Р№ Р·Р°РїСѓСЃРє РїРѕРґР°РІР»РµРЅ: РїСЂРµРґС‹РґСѓС‰РёР№ РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ С‚РѕР»СЊРєРѕ С‡С‚Рѕ Р·Р°РІРµСЂС€РёР»СЃСЏ (РІРѕР·РјРѕР¶РЅРѕ РґРІРѕР№РЅРѕР№ РєР»РёРє).")
                    log_event("detail_manual_doubleclick_suppressed", test=test_pick, key=cache_key)

                elif (_dg.get('failed_key') == cache_key) and auto_trigger and (not run_detail):
                    st.warning('РђРІС‚Рѕ-РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ РїРѕРґР°РІР»РµРЅ: РїСЂРµРґС‹РґСѓС‰Р°СЏ РїРѕРїС‹С‚РєР° РґР»СЏ СЌС‚РѕРіРѕ РЅР°Р±РѕСЂР° Р·Р°РІРµСЂС€РёР»Р°СЃСЊ РѕС€РёР±РєРѕР№. РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ **"Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Рё РїРѕРєР°Р·Р°С‚СЊ"** РґР»СЏ РїРѕРІС‚РѕСЂР°.')
                    log_event('detail_autorun_suppressed_after_error', key=cache_key, test=test_pick, err=str(_dg.get('failed_err') or ''))
                elif _same_key_recent and auto_trigger and (not run_detail):
                    # Р­С‚Рѕ РїРѕС‡С‚Рё РІСЃРµРіРґР° РѕР·РЅР°С‡Р°РµС‚ loop РёР· rerun'РѕРІ (РЅР°РїСЂРёРјРµСЂ, fallback Play, server-sync playhead, Р°РІС‚РѕРїРµСЂРµСЂРёСЃРѕРІРєР°).
                    _dg["suppressed"] = int(_dg.get("suppressed") or 0) + 1
                    st.session_state["detail_guard"] = _dg
                    st.warning(
                        "РџРѕРґР°РІР»РµРЅ РїРѕРІС‚РѕСЂРЅС‹Р№ Р°РІС‚РѕР·Р°РїСѓСЃРє РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° РґР»СЏ С‚РµРєСѓС‰РµРіРѕ С‚РµСЃС‚Р°: РѕР±РЅР°СЂСѓР¶РµРЅ rerun-loop. "
                        "РџСЂРѕРІРµСЂСЊ: (1) РѕС‚РєР»СЋС‡РµРЅР° Р»Рё В«РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ playhead СЃ СЃРµСЂРІРµСЂРѕРјВ»; (2) РЅРµ РІРєР»СЋС‡С‘РЅ Р»Рё Play РІ fallback; "
                        "(3) РЅРµС‚ Р»Рё Р°РІС‚РѕРїРµСЂРµСЂРёСЃРѕРІРєРё/РѕР±РЅРѕРІР»РµРЅРёСЏ. Р”Р»СЏ РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРіРѕ РїРµСЂРµСЃС‡С‘С‚Р° РЅР°Р¶РјРё РєРЅРѕРїРєСѓ В«РџРµСЂРµСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРіВ»."
                    )
                    log_event("detail_autorun_suppressed", test=test_pick, suppressed=_dg["suppressed"])

                else:
                    _dg["in_progress"] = True
                    _dg["pid"] = os.getpid()
                    _dg["last_start_ts"] = time.time()
                    _dg["last_key"] = cache_key
                    st.session_state["detail_guard"] = _dg

                    # UI: РїСЂРѕРіСЂРµСЃСЃР±Р°СЂ РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° (С‡С‚РѕР±С‹ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РІРёРґРµР», С‡С‚Рѕ СЂР°Р±РѕС‚Р° РёРґС‘С‚)
                    _dg["stage"] = "prepare"
                    _dg["progress"] = 2  # 0..100
                    st.session_state["detail_guard"] = _dg
                    _detail_pb = st.progress(int(_dg["progress"]))
                    _detail_pb_text = st.empty()
                    _detail_pb_text.caption("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РїРѕРґРіРѕС‚РѕРІРєР°вЂ¦")

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
                            looks_like_test = any(k in info for k in ("С‚РёРї", "type", "road_csv", "axay_csv", "t_end", "dt"))
                            if looks_like_test:
                                test_j = info
                                dt_j = info.get("dt", dt_j)
                                t_end_j = info.get("t_end", t_end_j)
                        if test_j is None:
                            raise RuntimeError(f"РќРµ РЅР°Р№РґРµРЅ С‚РµСЃС‚ '{test_pick}' РІ suite")
                        # fallback: allow dt/t_end embedded in test dict
                        if dt_j is None and isinstance(test_j, dict):
                            dt_j = test_j.get("dt", None)
                        if t_end_j is None and isinstance(test_j, dict):
                            t_end_j = test_j.get("t_end", None)
                        dt_j = float(dt_j) if dt_j is not None else 0.01
                        t_end_j = float(t_end_j) if t_end_j is not None else 1.0
                        log_event("detail_start", test=test_pick, dt=float(dt_j), t_end=float(t_end_j), max_points=int(max_points), want_full=bool(want_full))

                        # UI stage: СЂР°СЃС‡С‘С‚ РјРѕРґРµР»Рё
                        _dg["stage"] = "simulate"
                        _dg["progress"] = 10
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: СЂР°СЃС‡С‘С‚ РјРѕРґРµР»РёвЂ¦")
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

                        # UI stage: РѕР±СЂР°Р±РѕС‚РєР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
                        _dg["stage"] = "parse"
                        _dg["progress"] = 70
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РѕР±СЂР°Р±РѕС‚РєР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІвЂ¦")
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

                        # UI stage: СЃРѕС…СЂР°РЅРµРЅРёРµ/РєСЌС€РёСЂРѕРІР°РЅРёРµ
                        _dg["stage"] = "cache"
                        _dg["progress"] = 90
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: СЃРѕС…СЂР°РЅРµРЅРёРµ РєСЌС€Р°вЂ¦")
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

                        # UI stage: РіРѕС‚РѕРІРѕ
                        _dg["stage"] = "done"
                        _dg["progress"] = 100
                        _dg["progress_last_ts"] = time.time()
                        st.session_state["detail_guard"] = _dg
                        try:
                            _detail_pb.progress(int(_dg["progress"]))
                            _detail_pb_text.caption("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РіРѕС‚РѕРІРѕ.")
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
                                        for _k in ('patm_pa', 'p_atm_pa', 'P_ATM', 'P_ATM_РџР°'):
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
                            st.warning(f'РђРІС‚Рѕ-СЌРєСЃРїРѕСЂС‚ anim_latest РЅРµ СѓРґР°Р»СЃСЏ: {_e_animexp}')
                            log_event('anim_latest_export_error', err=str(_e_animexp), test=str(test_pick))
                        _dg_ok = dict(st.session_state.get("detail_guard") or {})
                        _dg_ok["failed_key"] = None
                        _dg_ok["failed_ts"] = 0.0
                        _dg_ok["failed_err"] = None
                        st.session_state["detail_guard"] = _dg_ok
                    except Exception as e:
                        st.error(f"РћС€РёР±РєР° РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°: {e}")
                        log_event("detail_error", err=str(e), test=test_pick)
                        _dg_fail = dict(st.session_state.get("detail_guard") or {})
                        _dg_fail["failed_key"] = str(cache_key)
                        _dg_fail["failed_ts"] = float(time.time())
                        _dg_fail["failed_err"] = str(e)
                        st.session_state["detail_guard"] = _dg_fail
                        # UI stage: РѕС€РёР±РєР°
                        try:
                            _dg_fail["stage"] = "error"
                            _dg_fail["progress"] = 100
                            _dg_fail["progress_last_ts"] = time.time()
                            st.session_state["detail_guard"] = _dg_fail
                            _detail_pb.progress(100)
                            _detail_pb_text.caption("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РѕС€РёР±РєР°.")
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
                            if s in ('1','true','yes','y','РґР°'):
                                return True
                            if s in ('0','false','no','n','РЅРµС‚',''):
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

                    st.subheader('РЎР°РјРѕРїСЂРѕРІРµСЂРєРё (РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ)')
                    st.caption('РџРѕРґРІРµСЃРєР°: РєРёРЅРµРјР°С‚РёРєР°/РїРµСЂРµРјРµС‰РµРЅРёСЏ + РїСЂРѕРІРµСЂРєР° DW2D РїРѕ С„Р°РєС‚РёС‡РµСЃРєРѕРјСѓ РґРёР°РїР°Р·РѕРЅСѓ С…РѕРґР° РёР· СЃРёРјСѓР»СЏС†РёРё.')

                    cS1, cS2, cS3 = st.columns(3)
                    with cS1:
                        if mech_ok is True:
                            st.success('РљРёРЅРµРјР°С‚РёРєР°/РїРµСЂРµРјРµС‰РµРЅРёСЏ: OK')
                        elif mech_ok is False:
                            st.error('РљРёРЅРµРјР°С‚РёРєР°/РїРµСЂРµРјРµС‰РµРЅРёСЏ: FAIL')
                        else:
                            st.info('РљРёРЅРµРјР°С‚РёРєР°/РїРµСЂРµРјРµС‰РµРЅРёСЏ: вЂ”')

                    with cS2:
                        if isinstance(dw_item, dict):
                            _dw_ok = bool(dw_item.get('ok', True))
                            _dw_sev = str(dw_item.get('severity', 'info') or 'info')
                            _label = 'DW2D РґРёР°РїР°Р·РѕРЅ: OK' if _dw_ok else 'DW2D РґРёР°РїР°Р·РѕРЅ: РџР РћР‘Р›Р•РњРђ'
                            if _dw_ok:
                                st.success(_label)
                            else:
                                if _dw_sev == 'error':
                                    st.error(_label)
                                else:
                                    st.warning(_label)
                        else:
                            st.info('DW2D РґРёР°РїР°Р·РѕРЅ: вЂ”')

                    with cS3:
                        _stab_on = bool(base_override.get('СЃС‚Р°Р±РёР»РёР·Р°С‚РѕСЂ_РІРєР»', False))
                        st.write('РЎС‚Р°Р±РёР»РёР·Р°С‚РѕСЂ:', 'Р’РљР›' if _stab_on else 'РІС‹РєР» (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ)')

                    # РќСѓР»РµРІР°СЏ РїРѕР·Р° (t=0): РґРѕСЂРѕРіР°=0, С€С‚РѕРєРё ~ СЃРµСЂРµРґРёРЅР° С…РѕРґР°
                    if isinstance(pose_item, dict):
                        _pz_ok = bool(pose_item.get('ok', True))
                        _pz_sev = str(pose_item.get('severity', 'info') or 'info')
                        _pz_label = 'РќСѓР»РµРІР°СЏ РїРѕР·Р°: OK' if _pz_ok else 'РќСѓР»РµРІР°СЏ РїРѕР·Р°: РџР РћР‘Р›Р•РњРђ'
                        if _pz_ok:
                            st.success(_pz_label)
                        else:
                            if _pz_sev == 'error':
                                st.error(_pz_label)
                            else:
                                st.warning(_pz_label)
                    else:
                        st.info('РќСѓР»РµРІР°СЏ РїРѕР·Р°: вЂ”')

                    with st.expander('Р”РµС‚Р°Р»Рё СЃР°РјРѕРїСЂРѕРІРµСЂРѕРє', expanded=False):
                        if mech_msg:
                            st.write('РњРµС…Р°РЅРёРєР°:', mech_msg)
                        _mj = _r0.get('mech_selfcheck_json', None)
                        if isinstance(_mj, str) and _mj.strip():
                            try:
                                st.json(json.loads(_mj))
                            except Exception:
                                st.code(_mj)
                        if isinstance(dw_item, dict) and (dw_item.get('message') or dw_item.get('value')):
                            st.markdown('**DW2D dynamic range**')
                            if dw_item.get('message'):
                                st.write(str(dw_item.get('message')))
                            if dw_item.get('value') is not None:
                                st.json(dw_item.get('value'))
                        if isinstance(pose_item, dict) and (pose_item.get('message') or pose_item.get('value')):
                            st.markdown('**РќСѓР»РµРІР°СЏ РїРѕР·Р° (t=0)**')
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
                                            'corner': _c,
                                            'road_m': _d.get('road_m', float('nan')),
                                            'wheel_rel_frame_m': _d.get('wheel_rel_frame_m', float('nan')),
                                            'rod_C1_frac': _d.get('rod_C1_frac', float('nan')),
                                            'rod_C2_frac': _d.get('rod_C2_frac', float('nan')),
                                        })
                                    if _rows:
                                        st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch")
                            except Exception:
                                pass
                            if pose_item.get('value') is not None:
                                st.json(pose_item.get('value'))
                        if isinstance(rep_post, dict):
                            st.markdown('**РџРѕР»РЅС‹Р№ autoself_post_json**')
                            st.json(rep_post)

                    st.caption('Р“РµРѕРјРµС‚СЂРёСЏ DW2D РЅР°СЃС‚СЂР°РёРІР°РµС‚СЃСЏ РЅР° СЃС‚СЂР°РЅРёС†Рµ: В«Р“РµРѕРјРµС‚СЂРёСЏ РїРѕРґРІРµСЃРєРё (DW2D)В» (РІ РјРµРЅСЋ СЃР»РµРІР°).')


                # -----------------------------------
                # Desktop Animator integration (follow-mode)
                # -----------------------------------
                with st.expander('рџ–Ґ Desktop Animator (РІРЅРµС€РЅРµРµ РѕРєРЅРѕ, follow anim_latest)', expanded=False):
                    npz_path, ptr_path = local_anim_latest_export_paths_global(
                        WORKSPACE_EXPORTS_DIR,
                        ensure_exists=False,
                    )
                    st.caption('Animator С‡РёС‚Р°РµС‚ РїРѕСЃР»РµРґРЅСЋСЋ РІС‹РіСЂСѓР·РєСѓ РёР· workspace/exports (anim_latest.*).')
                    st.code(str(ptr_path))
                    cols_da = st.columns([1, 1, 1])
                    with cols_da[0]:
                        if st.button('Р­РєСЃРїРѕСЂС‚РёСЂРѕРІР°С‚СЊ anim_latest СЃРµР№С‡Р°СЃ', key=f'anim_latest_export_now_{cache_key}'):
                            try:
                                if not (_HAS_NPZ_BUNDLE and export_anim_latest_bundle is not None):
                                    raise RuntimeError('npz_bundle РЅРµРґРѕСЃС‚СѓРїРµРЅ (РїСЂРѕРІРµСЂСЊС‚Рµ pneumo_solver_ui/npz_bundle.py)')
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
                                        for _k in ('patm_pa', 'p_atm_pa', 'P_ATM', 'P_ATM_РџР°'):
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
                                st.success(f'OK: {npz_latest.name}')
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
                                st.error(f'Р­РєСЃРїРѕСЂС‚ anim_latest РЅРµ СѓРґР°Р»СЃСЏ: {e}')
                                log_event('anim_latest_export_error_manual', err=str(e), test=str(test_pick))
                    with cols_da[1]:
                        no_gl = st.checkbox('no-gl (compat)', value=False, key=f'anim_latest_no_gl_{cache_key}')
                        if st.button('Р—Р°РїСѓСЃС‚РёС‚СЊ Animator (follow)', key=f'anim_latest_launch_{cache_key}'):
                            ok = launch_desktop_animator_follow(ptr_path, no_gl=bool(no_gl))
                            if ok:
                                st.success('Animator Р·Р°РїСѓС‰РµРЅ (РµСЃР»Рё СЃРёСЃС‚РµРјР° РїРѕР·РІРѕР»СЏРµС‚ GUI).')
                            else:
                                st.warning('РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РїСѓСЃС‚РёС‚СЊ Animator (СЃРј. Р»РѕРіРё).')
                        if st.button('Р—Р°РїСѓСЃС‚РёС‚СЊ Mnemo (follow)', key=f'anim_latest_launch_mnemo_{cache_key}'):
                            ok = launch_desktop_mnemo_follow(ptr_path)
                            if ok:
                                st.success('Desktop Mnemo Р·Р°РїСѓС‰РµРЅ (РµСЃР»Рё СЃРёСЃС‚РµРјР° РїРѕР·РІРѕР»СЏРµС‚ GUI).')
                            else:
                                st.warning('РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РїСѓСЃС‚РёС‚СЊ Desktop Mnemo (СЃРј. Р»РѕРіРё).')
                    with cols_da[2]:
                        st.caption(f'NPZ: {npz_path}')
                        st.caption('РџРѕРґСЃРєР°Р·РєР°: РІРєР»СЋС‡РёС‚Рµ **РђРІС‚Рѕ-СЌРєСЃРїРѕСЂС‚ anim_latest** РІ РЅР°СЃС‚СЂРѕР№РєР°С… РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°. Animator РґР°С‘С‚ 3D/2D РІРёРґС‹, Mnemo РґР°С‘С‚ РѕС‚РґРµР»СЊРЅРѕРµ HMI-РѕРєРЅРѕ СЃ Р°РЅРёРјРёСЂРѕРІР°РЅРЅРѕР№ РјРЅРµРјРѕС…РµРјРѕР№.')

                # -----------------------------------
                # Global timeline (shared playhead)
                # -----------------------------------
                time_s = []
                if df_main is not None and "РІСЂРµРјСЏ_СЃ" in df_main.columns:
                    time_s = df_main["РІСЂРµРјСЏ_СЃ"].astype(float).tolist()
                elif df_mdot is not None and "РІСЂРµРјСЏ_СЃ" in df_mdot.columns:
                    time_s = df_mdot["РІСЂРµРјСЏ_СЃ"].astype(float).tolist()

                # Р’Р°Р¶РЅРѕ: dataset_id РґР»СЏ РєРѕРјРїРѕРЅРµРЅС‚РѕРІ РґРµР»Р°РµРј *СѓРЅРёРєР°Р»СЊРЅС‹Рј РІРЅСѓС‚СЂРё UI-СЃРµСЃСЃРёРё*.
                # Р­С‚Рѕ Р·Р°С‰РёС‰Р°РµС‚ РѕС‚ СЂРµРґРєРѕР№ РіРѕРЅРєРё: РїСЂРё refresh Рё РЅРµРёР·РјРµРЅРёРІС€РµРјСЃСЏ cache_key
                # РІ localStorage РјРѕР¶РµС‚ РѕСЃС‚Р°С‚СЊСЃСЏ playhead СЃ playing=true, Рё 2D/3D
                # РєРѕРјРїРѕРЅРµРЅС‚С‹ СѓСЃРїРµРІР°СЋС‚ РµРіРѕ РїРѕРґС…РІР°С‚РёС‚СЊ, РїРѕРєР° playhead_ctrl РЅРµ РїРµСЂРµР·Р°РїРёСЃР°Р»
                # СЃРѕСЃС‚РѕСЏРЅРёРµ. Р”РѕР±Р°РІР»СЏСЏ nonce, РјС‹ РіР°СЂР°РЅС‚РёСЂСѓРµРј, С‡С‚Рѕ СЃС‚Р°СЂРѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ
                # Р±СѓРґРµС‚ РїСЂРѕРёРіРЅРѕСЂРёСЂРѕРІР°РЅРѕ (dataset_id РЅРµ СЃРѕРІРїР°РґС‘С‚).
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
                        "test": test,
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
                    # Fallback: РїСЂРѕСЃС‚РѕР№ СЃР»Р°Р№РґРµСЂ РїРѕ РёРЅРґРµРєСЃСѓ РІСЂРµРјРµРЅРё (Р±РµР· JS-РєРѕРјРїРѕРЅРµРЅС‚Р°).
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

                # Р’Р°Р¶РЅРѕ: st.tabs РЅРµ "Р»РµРЅРёРІС‹Р№" вЂ” РєРѕРґ РІРЅСѓС‚СЂРё РІСЃРµС… С‚Р°Р±РѕРІ РёСЃРїРѕР»РЅСЏРµС‚СЃСЏ РїСЂРё РєР°Р¶РґРѕРј rerun.
                # РџСЂРё Р°РЅРёРјР°С†РёРё (auto-refresh) СЌС‚Рѕ РІС‹РіР»СЏРґРёС‚ РєР°Рє "Р±РµСЃРєРѕРЅРµС‡РЅС‹Р№ СЂР°СЃС‡С‘С‚".
                # РџРѕСЌС‚РѕРјСѓ РёСЃРїРѕР»СЊР·СѓРµРј СЏРІРЅС‹Р№ СЃРµР»РµРєС‚РѕСЂ Рё СЂРµРЅРґРµСЂРёРј С‚РѕР»СЊРєРѕ РІС‹Р±СЂР°РЅРЅСѓСЋ РІРµС‚РєСѓ.
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
# РћРїС‚РёРјРёР·Р°С†РёСЏ вЂ” РёРЅР¶РµРЅРµСЂРЅС‹Р№ gateway
# -------------------------------
st.divider()
st.header("РћРїС‚РёРјРёР·Р°С†РёСЏ")
st.caption(
    "РџРѕСЃР»РµРґРѕРІР°С‚РµР»СЊРЅС‹Рµ staged / coordinator РїСЂРѕРіРѕРЅС‹ вЂ” РЅРѕСЂРјР°Р»СЊРЅС‹Р№ РёРЅР¶РµРЅРµСЂРЅС‹Р№ СЃС†РµРЅР°СЂРёР№. "
    "Р§С‚РѕР±С‹ РЅРµ СЃРјРµС€РёРІР°С‚СЊ РґРІР° СЂР°РІРЅРѕРїСЂР°РІРЅС‹С… control plane РЅР° РіР»Р°РІРЅРѕР№, Р·Р°РїСѓСЃРє, stop/resume, monitoring Рё РІСЃРµ СЂСѓС‡РєРё РѕРїС‚РёРјРёР·Р°С†РёРё "
    "РІС‹РЅРµСЃРµРЅС‹ РЅР° РѕС‚РґРµР»СЊРЅСѓСЋ СЃС‚СЂР°РЅРёС†Сѓ. РќР° РіР»Р°РІРЅРѕР№ РѕСЃС‚Р°СЋС‚СЃСЏ РІС…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ, search-space contract Рё read-only РѕР±Р·РѕСЂ."
)

colO1, colO2, colO3 = st.columns([1.15, 1.0, 1.05], gap="large")

with colO1:
    st.markdown("**РџРµСЂРµС…РѕРґС‹**")
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/30_Optimization.py",
        "рџЋЇ РћС‚РєСЂС‹С‚СЊ СЃС‚СЂР°РЅРёС†Сѓ РѕРїС‚РёРјРёР·Р°С†РёРё",
        key="home_opt_gateway_main_go_optimization",
        help_text="Р’СЃРµ staged/coordinator РЅР°СЃС‚СЂРѕР№РєРё, Р·Р°РїСѓСЃРє, stop/resume, С‚РµРєСѓС‰РёР№ Р»РѕРі Рё live-monitoring.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/20_DistributedOptimization.py",
        "рџ“Љ Р РµР·СѓР»СЊС‚Р°С‚С‹ РѕРїС‚РёРјРёР·Р°С†РёРё / ExperimentDB",
        key="home_opt_gateway_main_go_results",
        help_text="РџСЂРѕСЃРјРѕС‚СЂ distributed СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ, РїСЂРѕРіСЂРµСЃСЃР° Рё Pareto/DB СЃР»РѕСЏ.",
    )
    _opt_gateway_nav(
        "pneumo_solver_ui/pages/31_OptDatabase.py",
        "рџ—„пёЏ Р‘Р°Р·Р° РѕРїС‚РёРјРёР·Р°С†РёР№",
        key="home_opt_gateway_main_go_db",
        help_text="РћС‚РґРµР»СЊРЅР°СЏ СЃС‚СЂР°РЅРёС†Р° Р±Р°Р·С‹ РїСЂРѕРіРѕРЅРѕРІ РѕРїС‚РёРјРёР·Р°С†РёРё.",
    )
    st.caption(
        "Р’Р°Р¶РЅРѕ: С‚Р°Р±Р»РёС†Р° РїР°СЂР°РјРµС‚СЂРѕРІ, СЂРµР¶РёРјС‹ Рё suite РЅР° РіР»Р°РІРЅРѕР№ РѕСЃС‚Р°СЋС‚СЃСЏ source-of-truth РґР»СЏ search-space contract. "
        "РќРѕ СЃР°Рј optimization launcher РЅР° РіР»Р°РІРЅРѕР№ Р±РѕР»СЊС€Рµ РЅРµ РґСѓР±Р»РёСЂСѓРµС‚СЃСЏ."
    )

with colO2:
    st.markdown("**РўРµРєСѓС‰РёР№ РєРѕРЅС„РёРі (read-only)**")
    _render_home_opt_config_snapshot(compact=False)

with colO3:
    st.markdown("**РџРѕСЃР»РµРґРЅСЏСЏ РѕРїС‚РёРјРёР·Р°С†РёСЏ**")
    _render_home_opt_last_pointer_summary(compact=False)

st.info(
    "Р“Р»Р°РІРЅР°СЏ Р±РѕР»СЊС€Рµ РЅРµ РґРµСЂР¶РёС‚ РІС‚РѕСЂРѕР№ launcher РѕРїС‚РёРјРёР·Р°С†РёРё. Р­С‚Рѕ РЅРµ СЂРµР¶РµС‚ staged/coordinator СЂРµР¶РёРјС‹ Рё РЅРµ РїСЂСЏС‡РµС‚ РЅР°СЃС‚СЂРѕР№РєРё вЂ” "
    "РѕРЅРѕ РїСЂРѕСЃС‚Рѕ СЃРѕР±РёСЂР°РµС‚ Р·Р°РїСѓСЃРє Рё РЅР°Р±Р»СЋРґРµРЅРёРµ РІ РѕРґРЅРѕРј РёРЅР¶РµРЅРµСЂРЅРѕРј РјРµСЃС‚Рµ."
)

# Legacy home optimization block retained only as dormant source surface
# for regression/source guards. Live launch path = dedicated Optimization page.
if False:

    # -------------------------------
    # РћРїС‚РёРјРёР·Р°С†РёСЏ (С„РѕРЅ)
    # -------------------------------
    st.divider()
    st.header("РћРїС‚РёРјРёР·Р°С†РёСЏ (С„РѕРЅ)")

    colO1, colO2, colO3 = st.columns([1.2, 1.0, 1.0], gap="large")

    with colO1:
        st.markdown("**РљРѕРјР°РЅРґС‹**")
        # Gating: if autoselfcheck failed, block optimization by default (override is explicit)
        _self_ok = bool(st.session_state.get("_autoselfcheck_v1_ok", True))
        _allow_unsafe_opt = True
        if not _self_ok:
            st.error("autoselfcheck: FAIL. РћРїС‚РёРјРёР·Р°С†РёСЏ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅР°, С‡С‚РѕР±С‹ РЅРµ РїРѕР»СѓС‡Р°С‚СЊ РјСѓСЃРѕСЂРЅС‹Рµ СЂРµР·СѓР»СЊС‚Р°С‚С‹.")
            _allow_unsafe_opt = st.checkbox(
                "Р Р°Р·СЂРµС€РёС‚СЊ РѕРїС‚РёРјРёР·Р°С†РёСЋ РЅРµСЃРјРѕС‚СЂСЏ РЅР° FAIL",
                value=False,
                key="allow_unsafe_opt",
                help="РРЅРѕРіРґР° РїРѕР»РµР·РЅРѕ РґР»СЏ РѕС‚Р»Р°РґРєРё, РЅРѕ СЂРµР·СѓР»СЊС‚Р°С‚С‹ РјРѕРіСѓС‚ Р±С‹С‚СЊ РЅРµРєРѕСЂСЂРµРєС‚РЅС‹. Р›СѓС‡С€Рµ СЃРЅР°С‡Р°Р»Р° РёСЃРїСЂР°РІРёС‚СЊ РѕС€РёР±РєРё selfcheck.",
            )

        _opt_disabled = (
            pid_alive(st.session_state.opt_proc)
            or bool(param_errors)
            or bool(suite_errors)
            or ((not _self_ok) and (not _allow_unsafe_opt))
        )

        btn_start = st.button("РЎС‚Р°СЂС‚ РѕРїС‚РёРјРёР·Р°С†РёРё", disabled=_opt_disabled)
        colS1, colS2 = st.columns(2)
        with colS1:
            btn_stop_soft = st.button("РЎС‚РѕРї (РјСЏРіРєРѕ)", disabled=not pid_alive(st.session_state.opt_proc), help="РЎРѕР·РґР°С‘С‚ STOP-С„Р°Р№Р». РћРїС‚РёРјРёР·Р°С‚РѕСЂ СЃР°Рј РєРѕСЂСЂРµРєС‚РЅРѕ Р·Р°РІРµСЂС€РёС‚СЃСЏ Рё СЃРѕС…СЂР°РЅРёС‚ CSV/РїСЂРѕРіСЂРµСЃСЃ.")
        with colS2:
            btn_stop_hard = st.button("РЎС‚РѕРї (Р¶С‘СЃС‚РєРѕ)", disabled=not pid_alive(st.session_state.opt_proc), help="РЎРѕР·РґР°С‘С‚ STOP-С„Р°Р№Р» Рё РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕ Р·Р°РІРµСЂС€Р°РµС‚ РїСЂРѕС†РµСЃСЃ. РСЃРїРѕР»СЊР·СѓР№С‚Рµ С‚РѕР»СЊРєРѕ РµСЃР»Рё РјСЏРіРєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР° РЅРµ СЃСЂР°Р±Р°С‚С‹РІР°РµС‚.")

    with colO2:
        st.markdown("**РЎС‚Р°С‚СѓСЃ**")
        if pid_alive(st.session_state.opt_proc):
            st.success(f"РћРїС‚РёРјРёР·Р°С†РёСЏ РёРґС‘С‚ (PID={st.session_state.opt_proc.pid})")
            if st.session_state.opt_stop_requested:
                st.warning("Р—Р°РїСЂРѕС€РµРЅР° РјСЏРіРєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР°вЂ¦ Р¶РґС‘Рј Р·Р°РІРµСЂС€РµРЅРёСЏ РїСЂРѕС†РµСЃСЃР°.")
        else:
            st.info("РћРїС‚РёРјРёР·Р°С†РёСЏ РЅРµ Р·Р°РїСѓС‰РµРЅР°")
            # РµСЃР»Рё РїСЂРѕС†РµСЃСЃ Р·Р°РІРµСЂС€РёР»СЃСЏ (СЃР°Рј РёР»Рё РїРѕСЃР»Рµ РјСЏРіРєРѕРіРѕ STOP) вЂ” С‡РёСЃС‚РёРј СЃРѕСЃС‚РѕСЏРЅРёРµ
            if st.session_state.opt_proc is not None:
                st.session_state.opt_proc = None
            st.session_state.opt_stop_requested = False

        if st.session_state.opt_out_csv:
            st.write("Р¤Р°Р№Р» СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ:", st.session_state.opt_out_csv)
            # РїСЂРѕРіСЂРµСЃСЃ РѕРїС‚РёРјРёР·Р°С†РёРё (С„Р°Р№Р» РїРёС€РµС‚ worker)
            try:
                out_csv_path = Path(st.session_state.opt_out_csv)
                progress_path = st.session_state.opt_progress_path or (str(out_csv_path.with_suffix("")) + "_progress.json")
                if os.path.exists(progress_path):
                    with open(progress_path, "r", encoding="utf-8") as f:
                        prog = json.load(f)
                    try:
                        _mtime = os.path.getmtime(progress_path)
                        _age = time.time() - float(_mtime)
                        st.caption(f"РџСЂРѕРіСЂРµСЃСЃ-С„Р°Р№Р» РѕР±РЅРѕРІР»С‘РЅ {_age:.1f} СЃ РЅР°Р·Р°Рґ: {progress_path}")
                        # Р•СЃР»Рё РїСЂРѕС†РµСЃСЃ Р¶РёРІ, Р° С„Р°Р№Р» РґР°РІРЅРѕ РЅРµ РѕР±РЅРѕРІР»СЏР»СЃСЏ вЂ” РІРµСЂРѕСЏС‚РЅРѕ Р·Р°РІРёСЃ/СѓРїР°Р» РёР»Рё РїРёС€РµС‚ РІ РґСЂСѓРіРѕР№ РєР°С‚Р°Р»РѕРі.
                        if pid_alive(st.session_state.opt_proc) and (_age > max(300.0, 10.0*float(refresh_sec) + 5.0)):
                            st.caption("вљ пёЏ РџСЂРѕРіСЂРµСЃСЃ-С„Р°Р№Р» РґР°РІРЅРѕ РЅРµ РѕР±РЅРѕРІР»СЏР»СЃСЏ. Р•СЃР»Рё СЌС‚Рѕ РЅРµРѕР¶РёРґР°РЅРЅРѕ вЂ” РїСЂРѕРІРµСЂСЊС‚Рµ, С‡С‚Рѕ worker РїРёС€РµС‚ progress.json РІ С‚РѕС‚ Р¶Рµ РєР°С‚Р°Р»РѕРі Рё С‡С‚Рѕ СЂР°СЃС‡С‘С‚ РЅРµ Р·Р°РІРёСЃ.")
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

                        st.write(f"РЎС‚Р°РґРёСЏ: **{stage_name}** (idx={stage_idx}, 0-based; РІСЃРµРіРѕ СЃС‚Р°РґРёР№: {max(1, stage_total)})")
                        st.caption(describe_runtime_stage(stage_name))
                        st.write(f"Готово (суммарно): {total_done}  |  Записано в файл: {total_done_in_file}")
                        st.write(f"РўРµРєСѓС‰Р°СЏ СЃС‚Р°РґРёСЏ: rows РІ CSV = **{stage_rows_current}**  |  РїРѕ progress worker = {worker_done_current}/{worker_written_current}")
                        if stage_rows_done_before > 0:
                            st.caption(f"Р—Р°РІРµСЂС€С‘РЅРЅС‹Рµ РїСЂРµРґС‹РґСѓС‰РёРµ СЃС‚Р°РґРёРё СѓР¶Рµ РґР°Р»Рё СЃС‚СЂРѕРє: {stage_rows_done_before}")
                        if stage_budget_sec is not None and float(stage_budget_sec) > 0:
                            frac_stage = max(0.0, min(1.0, float(stage_elapsed_sec or 0.0) / float(stage_budget_sec)))
                            st.progress(frac_stage, text=f"РџСЂРѕРіСЂРµСЃСЃ С‚РµРєСѓС‰РµР№ СЃС‚Р°РґРёРё РїРѕ РІСЂРµРјРµРЅРё: {frac_stage*100:.1f}% (СЃС‚Р°С‚СѓСЃ: {status_text})")
                        elif time_limit_min > 0:
                            frac_t = max(0.0, min(1.0, elapsed_sec_live / (time_limit_min * 60.0)))
                            st.progress(frac_t, text=f"РџСЂРѕРіСЂРµСЃСЃ РїРѕ РІСЂРµРјРµРЅРё: {frac_t*100:.1f}% (СЃС‚Р°С‚СѓСЃ: {status_text})")
                        if bool(staged_summary.get("worker_progress_stale", False)):
                            st.caption("вљ пёЏ Р’Р»РѕР¶РµРЅРЅС‹Р№ progress.json РѕС‚СЃС‚Р°С‘С‚ РѕС‚ live CSV С‚РµРєСѓС‰РµР№ СЃС‚Р°РґРёРё; UI РїРѕРєР°Р·С‹РІР°РµС‚ РїСЂРѕРёР·РІРѕРґРЅС‹Рµ СЃС‡С‘С‚С‡РёРєРё РїРѕ С„Р°РєС‚РёС‡РµСЃРєРёРј СЃС‚СЂРѕРєР°Рј stage CSV.")
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
                            st.markdown("**Seed/promotion policy (С‚РµРєСѓС‰Р°СЏ СЃС‚Р°РґРёСЏ)**")
                            policy_name = str(live_policy.get("policy_name") or "")
                            effective_mode = str(live_policy.get("effective_mode") or "")
                            requested_mode_live = str(live_policy.get("requested_mode") or "")
                            summary_status_live = str(live_policy.get("summary_status") or "")
                            priority_params_live = list(live_policy.get("priority_params") or [])
                            seed_bucket_counts = dict(live_policy.get("seed_bucket_counts") or {})
                            st.caption(
                                f"policy={policy_name or 'вЂ”'} В· requested={requested_mode_live or 'вЂ”'} В· effective={effective_mode or 'вЂ”'} В· summary={summary_status_live or 'вЂ”'}"
                            )
                            st.write(
                                "Seed budget:",
                                f"explore={int(live_policy.get('explore_budget', 0) or 0)}",
                                f"focus={int(live_policy.get('focus_budget', 0) or 0)}",
                                f"selected={int(live_policy.get('seed_count', 0) or 0)}",
                                f"focus/explore selected={int(seed_bucket_counts.get('focus', 0) or 0)}/{int(seed_bucket_counts.get('explore', 0) or 0)}",
                            )
                            if priority_params_live:
                                st.caption("Priority params for this stage: " + ", ".join(str(x) for x in priority_params_live[:8]))
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
                            st.progress(frac_t, text=f"РџСЂРѕРіСЂРµСЃСЃ РїРѕ РІСЂРµРјРµРЅРё: {frac_t*100:.1f}% (СЃС‚Р°С‚СѓСЃ: {status_text})")
                        st.write(f"Готово кандидатов: **{total_done}**")

                    if ok is not None and err is not None:
                        st.write(f"Р’ РїРѕСЃР»РµРґРЅРµРј Р±Р°С‚С‡Рµ: OK={ok}, ERR={err}")
                    # РґРёР°РіРЅРѕСЃС‚РёРєР°: РїСЂРѕС†РµСЃСЃ СѓРјРµСЂ, РЅРѕ СЃС‚Р°С‚СѓСЃ РµС‰С‘ В«РёРґС‘С‚В»
                    if (not pid_alive(st.session_state.opt_proc)) and status_text in ["Р·Р°РїСѓС‰РµРЅРѕ", "РёРґС‘С‚", "stage_running", "baseline_eval", "seed_eval"]:
                        st.error(
                            "РџРѕС…РѕР¶Рµ, worker/staged-runner Р·Р°РІРµСЂС€РёР»СЃСЏ Р°РІР°СЂРёР№РЅРѕ РёР»Рё Р±С‹Р» РѕСЃС‚Р°РЅРѕРІР»РµРЅ РґРѕ С„РёРЅР°Р»СЊРЅРѕРіРѕ СЃС‚Р°С‚СѓСЃР°, Р° РїСЂРѕРіСЂРµСЃСЃ РЅРµ РґРѕС€С‘Р» РґРѕ 'Р·Р°РІРµСЂС€РµРЅРѕ'. "
                            "РЎРјРѕС‚СЂРёС‚Рµ log/CSV/staged_progress Рё stage_*_progress.json."
                        )
                else:
                    st.caption(f"Р¤Р°Р№Р» РїСЂРѕРіСЂРµСЃСЃР° РµС‰С‘ РЅРµ СЃРѕР·РґР°РЅ. РћР¶РёРґР°РµРјС‹Р№ РїСѓС‚СЊ: {progress_path}")
            except Exception as _e:
                st.caption(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ РїСЂРѕРіСЂРµСЃСЃ: {_e}")

    with colO3:
        st.markdown("**Р›РѕРіРёРєР°**")
        st.write("Р РµР·СѓР»СЊС‚Р°С‚С‹ РїРёС€СѓС‚СЃСЏ РІ CSV РёРЅРєСЂРµРјРµРЅС‚Р°Р»СЊРЅРѕ, РєР°Р¶РґС‹Рµ N РєР°РЅРґРёРґР°С‚РѕРІ.")


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
        # РњСЏРіРєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР°: С‚РѕР»СЊРєРѕ STOP-С„Р°Р№Р». РџСЂРѕС†РµСЃСЃ СЃР°Рј Р·Р°РІРµСЂС€РёС‚СЃСЏ, Р·Р°РїРёС€РµС‚ РїСЂРѕРіСЂРµСЃСЃ Рё РєРѕСЂСЂРµРєС‚РЅРѕ Р·Р°РєСЂРѕРµС‚ С„Р°Р№Р»С‹.
        try:
            (Path(st.session_state.opt_stop_file) if st.session_state.opt_stop_file else (HERE / "STOP_OPTIMIZATION.txt")).write_text("stop", encoding="utf-8")
        except Exception:
            pass
        st.session_state.opt_stop_requested = True
        do_rerun()

    if 'btn_stop_hard' in locals() and btn_stop_hard:
        # Р–С‘СЃС‚РєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР°: STOP-С„Р°Р№Р» + РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ Р·Р°РІРµСЂС€РµРЅРёРµ РїСЂРѕС†РµСЃСЃР° (РµСЃР»Рё РЅСѓР¶РЅРѕ).
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
    # РџСЂРѕСЃРјРѕС‚СЂ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РѕРїС‚РёРјРёР·Р°С†РёРё
    # -------------------------------
    st.subheader("РџСЂРѕСЃРјРѕС‚СЂ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ (CSV)")

    show_csv = st.checkbox("РџРѕРєР°Р·С‹РІР°С‚СЊ/РѕР±РЅРѕРІР»СЏС‚СЊ С‚Р°Р±Р»РёС†Сѓ CSV (РјРѕР¶РµС‚ С‚РѕСЂРјРѕР·РёС‚СЊ РїСЂРё РґРѕР»РіРёС… РїСЂРѕРіРѕРЅР°С…)", value=not pid_alive(st.session_state.opt_proc))

    csv_to_view = st.text_input("РћС‚РєСЂС‹С‚СЊ CSV", value=st.session_state.opt_out_csv or "")
    if show_csv and csv_to_view and os.path.exists(csv_to_view):
        try:
            df_all_raw = pd.read_csv(csv_to_view)
            show_service_rows = st.checkbox(
                "РџРѕРєР°Р·С‹РІР°С‚СЊ baseline/service rows",
                value=bool(st.session_state.get("opt_show_service_rows", False)),
                key="opt_show_service_rows",
                help="РЎР»СѓР¶РµР±РЅС‹Рµ baseline-anchor СЃС‚СЂРѕРєРё РЅРµ СЃС‡РёС‚Р°СЋС‚СЃСЏ СЂРµР°Р»СЊРЅС‹РјРё РєР°РЅРґРёРґР°С‚Р°РјРё Рё РѕР±С‹С‡РЅРѕ СЃРєСЂС‹С‚С‹ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ.",
            )
            try:
                from pneumo_solver_ui.optimization_result_rows import filter_display_df as _filter_opt_display_df
                df_all = _filter_opt_display_df(df_all_raw, include_baseline=bool(show_service_rows))
            except Exception:
                df_all = df_all_raw.copy()
            _opt_packaging_params = load_packaging_params_from_base_json(st.session_state.get("opt_base_json"))
            if len(df_all) > 0:
                df_all = enrich_packaging_surface_df(df_all, params=_opt_packaging_params)
            st.write(f"РЎС‚СЂРѕРє: {len(df_all)}")
            if len(df_all) != len(df_all_raw):
                st.caption(f"РЎРєСЂС‹С‚Рѕ СЃР»СѓР¶РµР±РЅС‹С… baseline/service rows: {int(len(df_all_raw) - len(df_all))}")
            render_packaging_surface_metrics(st, df_all)

            st.markdown("### Р‘С‹СЃС‚СЂС‹Р№ TOP РїРѕ СЃСѓРјРјР°СЂРЅРѕРјСѓ С€С‚СЂР°С„Сѓ")
            if "С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°" in df_all.columns:
                df_top = df_all.sort_values(["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"], ascending=True).head(30)
                top_cols = packaging_surface_result_columns(
                    df_top,
                    leading=["id", "РїРѕРєРѕР»РµРЅРёРµ", "С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"],
                )
                safe_dataframe(df_top[top_cols] if top_cols else df_top, height=260)

            st.markdown("### Pareto: РІС‹Р±РѕСЂ РѕСЃРµР№ (Р±РµР· Р¶С‘СЃС‚РєРёС… РѕС‚СЃРµС‡РµРє РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ)")

            # Р Р°Р±РѕС‡Р°СЏ РєРѕРїРёСЏ
            df_all2 = df_all.copy()

            # Р¤РёР»СЊС‚СЂС‹/СЂР°РЅР¶РёСЂРѕРІР°РЅРёРµ вЂ” РІ popover (С‡С‚РѕР±С‹ РЅРµ Р·Р°С…Р»Р°РјР»СЏС‚СЊ СЌРєСЂР°РЅ)
            with ui_popover("вљ™пёЏ Р¤РёР»СЊС‚СЂС‹ Pareto / СЂР°РЅР¶РёСЂРѕРІР°РЅРёРµ"):
                use_pen_filter = st.checkbox(
                    "Р¤РёР»СЊС‚СЂРѕРІР°С‚СЊ РїРѕ С€С‚СЂР°С„Сѓ С„РёР·РёС‡РЅРѕСЃС‚Рё",
                    value=bool(st.session_state.get("pareto_pen_filter", False)),
                    key="pareto_pen_filter",
                )
                if use_pen_filter and "С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°" in df_all2.columns:
                    try:
                        _pen_vals = df_all2["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].astype(float).values
                        _pen_min = float(np.nanmin(_pen_vals))
                        _pen_max = float(np.nanmax(_pen_vals))
                    except Exception:
                        _pen_min, _pen_max = 0.0, 0.0
                    st.slider(
                        "РњР°РєСЃ С€С‚СЂР°С„ С„РёР·РёС‡РЅРѕСЃС‚Рё (<=)",
                        min_value=float(_pen_min),
                        max_value=float(_pen_max),
                        value=float(st.session_state.get("pareto_pen_max", _pen_max) or _pen_max),
                        step=0.5,
                        key="pareto_pen_max",
                    )
                    try:
                        _pen_max_use = float(st.session_state.get("pareto_pen_max", _pen_max) or _pen_max)
                        df_all2 = df_all2[df_all2["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].astype(float) <= _pen_max_use]
                    except Exception:
                        pass
                df_all2 = apply_packaging_surface_filters(st, df_all2, key_prefix="pareto", compact=True)
                st.divider()
                st.slider(
                    "TOP-N РґР»СЏ РІС‹РІРѕРґР°",
                    min_value=5,
                    max_value=200,
                    value=int(st.session_state.get("pareto_topn", 10) or 10),
                    step=5,
                    key="pareto_topn",
                )

            # Р’С‹Р±РѕСЂ РѕСЃРµР№ Pareto вЂ” РёР· РІСЃРµС… С‡РёСЃР»РµРЅРЅС‹С… СЃС‚РѕР»Р±С†РѕРІ
            num_cols = [c for c in df_all2.columns if pd.api.types.is_numeric_dtype(df_all2[c])]

            if len(num_cols) < 2:
                st.info("РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ С‡РёСЃР»РµРЅРЅС‹С… СЃС‚РѕР»Р±С†РѕРІ РґР»СЏ Pareto.")
            else:
                default1 = "С†РµР»СЊ1_СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ_РёРЅРµСЂС†РёСЏ__СЃ" if "С†РµР»СЊ1_СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ_РёРЅРµСЂС†РёСЏ__СЃ" in num_cols else num_cols[0]
                default2 = "С†РµР»СЊ2_РєРѕРјС„РѕСЂС‚__RMS_СѓСЃРєРѕСЂ_Рј_СЃ2" if "С†РµР»СЊ2_РєРѕРјС„РѕСЂС‚__RMS_СѓСЃРєРѕСЂ_Рј_СЃ2" in num_cols else (num_cols[1] if num_cols[1] != default1 else num_cols[0])

                obj1 = st.selectbox("РћСЃСЊ X (РјРёРЅРёРјРёР·РёСЂРѕРІР°С‚СЊ)", num_cols, index=num_cols.index(default1), key="pareto_obj1")
                obj2 = st.selectbox("РћСЃСЊ Y (РјРёРЅРёРјРёР·РёСЂРѕРІР°С‚СЊ)", num_cols, index=num_cols.index(default2), key="pareto_obj2")

                df_f = df_all2.copy()
                df_f = df_f[df_f[obj1].apply(lambda v: np.isfinite(float(v)) if v is not None else False)]
                df_f = df_f[df_f[obj2].apply(lambda v: np.isfinite(float(v)) if v is not None else False)]

                if len(df_f) == 0:
                    st.info("РќРµС‚ РґР°РЅРЅС‹С… РґР»СЏ Pareto (РІСЃРµ Р·РЅР°С‡РµРЅРёСЏ NaN/inf РёР»Рё РѕС‚С„РёР»СЊС‚СЂРѕРІР°РЅС‹).")
                else:
                    keep = pareto_front_2d(df_f, obj1, obj2)
                    df_p = df_f.loc[keep].copy()
                    st.write(f"Pareto candidates: {len(df_p)} / {len(df_f)}")

                    top_n = int(st.session_state.get("pareto_topn", 10) or 10)

                    # Р‘Р°Р»Р°РЅСЃРЅС‹Р№ СЃРєРѕСЂ: РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Рµ РѕСЃРё + (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ) С€С‚СЂР°С„ С„РёР·РёС‡РЅРѕСЃС‚Рё
                    df_p["_o1n"] = (df_p[obj1] - df_p[obj1].min()) / (df_p[obj1].max() - df_p[obj1].min() + 1e-12)
                    df_p["_o2n"] = (df_p[obj2] - df_p[obj2].min()) / (df_p[obj2].max() - df_p[obj2].min() + 1e-12)

                    if "С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°" in df_p.columns:
                        w_pen = st.slider("Р’РµСЃ С€С‚СЂР°С„Р° РІ Р±Р°Р»Р°РЅСЃРЅРѕРј СЃРєРѕСЂРµ", 0.0, 5.0, 1.0, 0.1, key="pareto_wpen")
                        df_p["_penn"] = (df_p["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"] - df_p["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].min()) / (df_p["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].max() - df_p["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].min() + 1e-12)
                    else:
                        w_pen = 0.0
                        df_p["_penn"] = 0.0

                    df_p["_score_bal"] = df_p["_o1n"] + df_p["_o2n"] + float(w_pen) * df_p["_penn"]

                    df_top = df_p.sort_values("_score_bal").head(int(top_n)).copy()

                    # Р§С‚Рѕ РїРѕРєР°Р·С‹РІР°С‚СЊ РІ С‚Р°Р±Р»РёС†Рµ
                    show_cols = []
                    for c in ["id", "РїРѕРєРѕР»РµРЅРёРµ", "seed_candidates", "seed_conditions"]:
                        if c in df_top.columns:
                            show_cols.append(c)
                    show_cols += [obj1, obj2]
                    if "С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°" in df_top.columns:
                        show_cols.append("С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°")
                    for c in packaging_surface_result_columns(df_top, leading=[]):
                        if c not in show_cols:
                            show_cols.append(c)

                    safe_dataframe(df_top[show_cols])

                    st.markdown("#### 3 С„РёРЅР°Р»Р° (aggressive / balanced / comfort)")
                    aggressive = df_p.sort_values(obj1).head(1).copy()
                    comfort = df_p.sort_values(obj2).head(1).copy()
                    balanced = df_p.sort_values("_score_bal").head(1).copy()

                    aggressive["С„РёРЅР°Р»"] = "aggressive"
                    balanced["С„РёРЅР°Р»"] = "balanced"
                    comfort["С„РёРЅР°Р»"] = "comfort"

                    finals = pd.concat([aggressive, balanced, comfort], ignore_index=True)
                    finals_cols = show_cols + (["С„РёРЅР°Р»"] if "С„РёРЅР°Р»" in finals.columns else [])
                    safe_dataframe(finals[finals_cols])

                    # Р’С‹РіСЂСѓР·РєР°
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                        df_p.drop(columns=[c for c in ["_o1n","_o2n","_penn","_score_bal"] if c in df_p.columns]).to_excel(writer, sheet_name="pareto", index=False)
                        df_top.drop(columns=[c for c in ["_o1n","_o2n","_penn","_score_bal"] if c in df_top.columns]).to_excel(writer, sheet_name="topN", index=False)
                        finals.to_excel(writer, sheet_name="finals", index=False)
                    st.download_button(
                        "РЎРєР°С‡Р°С‚СЊ Pareto/Top/Finals (xlsx)",
                        data=buf.getvalue(),
                        file_name="pareto_top_final.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        except Exception as e:
            st.error(f"РќРµ РјРѕРіСѓ РїСЂРѕС‡РёС‚Р°С‚СЊ CSV: {e}")



    # -------------------------------
    # РљР°Р»РёР±СЂРѕРІРєР° / Autopilot (NPZ/CSV) вЂ” UI
    # -------------------------------
    with st.expander("РљР°Р»РёР±СЂРѕРІРєР° Рё Autopilot (NPZ/CSV) вЂ” СЌРєСЃРїРµСЂРёРјРµРЅС‚", expanded=False):
        st.markdown(
            """
            ...
            """
        )
        # Where calibration/autopilot looks for oscillogram logs.
        # Default: workspace/osc (inside the project), but user may point to any local folder.
        osc_dir_input = st.text_input(
            "РџР°РїРєР° СЃ Р»РѕРіР°РјРё (osc_dir): РіРґРµ Р»РµР¶Р°С‚ NPZ/CSV Рё РєСѓРґР° РёС… СЃРѕС…СЂР°РЅСЏС‚СЊ",
            value=str(st.session_state.get("osc_dir_path", WORKSPACE_OSC_DIR)),
            key="osc_dir_path",
            help=(
                "РљР°Р»РёР±СЂРѕРІРєР° Рё Autopilot С‡РёС‚Р°СЋС‚ Txx_osc.npz РёР· СЌС‚РѕР№ РїР°РїРєРё. "
                "РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ СЌС‚Рѕ pneumo_solver_ui/workspace/osc, РЅРѕ РјРѕР¶РЅРѕ РІС‹Р±СЂР°С‚СЊ Р»СЋР±СѓСЋ Р»РѕРєР°Р»СЊРЅСѓСЋ РґРёСЂРµРєС‚РѕСЂРёСЋ."
            ),
        )
        osc_dir = Path(osc_dir_input).expanduser()
        try:
            osc_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            st.error(f"РќРµ РјРѕРіСѓ СЃРѕР·РґР°С‚СЊ/РѕС‚РєСЂС‹С‚СЊ osc_dir: {osc_dir} ({e})")
        st.code(str(osc_dir), language="text")

        # РџРѕРґСЃРєР°Р·РєР° РїРѕ РѕР¶РёРґР°РµРјС‹Рј РёРјРµРЅР°Рј С„Р°Р№Р»РѕРІ (РµСЃР»Рё РµСЃС‚СЊ baseline-suite)
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

        st.write("Р”РѕР±Р°РІРёС‚СЊ С„Р°Р№Р»С‹ РІ osc_dir (СЃРј. РїСѓС‚СЊ РІС‹С€Рµ):")
        uploads = st.file_uploader(
            "NPZ/CSV (РјРѕР¶РЅРѕ РЅРµСЃРєРѕР»СЊРєРѕ)",
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
                    st.error(f"РќРµ СЃРјРѕРі СЃРѕС…СЂР°РЅРёС‚СЊ {uf.name}: {e}")

        # РЎРїРёСЃРѕРє С„Р°Р№Р»РѕРІ
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
        # Mapping: РїСЂРѕРёР·РІРѕР»СЊРЅС‹Рµ С„Р°Р№Р»С‹ -> РѕР¶РёРґР°РµРјС‹Рµ Txx_osc.npz
        # -------------------------------------------------
        st.markdown("### Mapping С„Р°Р№Р»РѕРІ вћњ Txx_osc.npz (Р±РµР· СЂСѓС‡РЅРѕР№ РїРёСЃР°РЅРёРЅС‹ РІ РєРѕРЅСЃРѕР»Рё)")
        st.caption(
            "Autopilot/РєР°Р»РёР±СЂРѕРІРєР° РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РёС‰СѓС‚ С„Р°Р№Р»С‹ СЃ РёРјРµРЅР°РјРё T01_osc.npz, T02_osc.npz, ... "
            "Р•СЃР»Рё Сѓ С‚РµР±СЏ С„Р°Р№Р»С‹ РЅР°Р·С‹РІР°СЋС‚СЃСЏ РёРЅР°С‡Рµ вЂ” РІС‹Р±РµСЂРё СЃРѕРѕС‚РІРµС‚СЃС‚РІРёРµ Р·РґРµСЃСЊ Рё РЅР°Р¶РјРё В«РџСЂРёРјРµРЅРёС‚СЊ mappingВ»."
        )

        _all_files = sorted([p.name for p in (npz_files + csv_files)])
        if (_tests_map or {}) and _all_files:
            file_opts = ["(РЅРµ РІС‹Р±СЂР°РЅРѕ)"] + _all_files

            # РџРѕРїСЂРѕР±СѓРµРј Р·Р°РіСЂСѓР·РёС‚СЊ СЃРѕС…СЂР°РЅС‘РЅРЅС‹Р№ mapping (РµСЃР»Рё РµСЃС‚СЊ)
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
                # default: РµСЃР»Рё РѕР¶РёРґР°РµРјС‹Р№ СѓР¶Рµ РµСЃС‚СЊ, Р±РµСЂС‘Рј РµРіРѕ; РёРЅР°С‡Рµ РїС‹С‚Р°РµРјСЃСЏ РёР· СЃРѕС…СЂР°РЅС‘РЅРЅРѕРіРѕ mapping
                pick = expected if expected in _all_files else _saved_map.get(str(i), "")
                if pick not in _all_files:
                    pick = ""
                _rows_map.append(
                    {
                        "test_num": i,
                        "test_name": name,
                        "source_file": pick if pick else "(РЅРµ РІС‹Р±СЂР°РЅРѕ)",
                        "expected_npz": expected,
                    }
                )

            df_map = pd.DataFrame(_rows_map)

            try:
                # Streamlit >=1.29: column_config РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ
                edited_map = st.data_editor(
                    df_map,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "source_file": st.column_config.SelectboxColumn(
                            "source_file",
                            help="Р’С‹Р±РµСЂРё С„Р°Р№Р» (NPZ/CSV) РґР»СЏ СЌС‚РѕРіРѕ С‚РµСЃС‚Р°",
                            options=file_opts,
                            required=True,
                        )
                    },
                    key="osc_mapping_editor",
                )
            except Exception:
                # fallback Р±РµР· column_config
                edited_map = safe_dataframe(df_map, hide_index=True)
                edited_map = df_map

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("РџСЂРёРјРµРЅРёС‚СЊ mapping (СЃРѕР·РґР°С‚СЊ/РѕР±РЅРѕРІРёС‚СЊ Txx_osc.npz)", key="apply_tests_file_mapping"):
                    created = 0
                    missing = 0
                    for _, r in edited_map.iterrows():
                        tnum = int(r.get("test_num", 0) or 0)
                        src_name = str(r.get("source_file", "") or "").strip()
                        if not tnum:
                            continue
                        if src_name == "(РЅРµ РІС‹Р±СЂР°РЅРѕ)" or not src_name:
                            missing += 1
                            continue
                        src_path = osc_dir / src_name
                        dst_path = osc_dir / f"T{tnum:02d}_osc.npz"
                        try:
                            if src_path.suffix.lower() == ".csv":
                                # convert to simple NPZ (С‚Р°Р±Р»РёС†Р° -> main_cols/main_values)
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
                                # NPZ -> РїСЂРѕСЃС‚Рѕ РєРѕРїРёСЏ РїРѕРґ РѕР¶РёРґР°РµРјРѕРµ РёРјСЏ
                                dst_path.write_bytes(src_path.read_bytes())
                            created += 1
                        except Exception as e:
                            st.error(f"РќРµ СЃРјРѕРі РїРѕРґРіРѕС‚РѕРІРёС‚СЊ {dst_path.name} РёР· {src_name}: {e}")

                    # СЃРѕС…СЂР°РЅСЏРµРј mapping (test_num -> source_file) С‡С‚РѕР±С‹ РЅРµ РІС‹Р±РёСЂР°С‚СЊ Р·Р°РЅРѕРІРѕ
                    try:
                        out_map = {}
                        for _, r in edited_map.iterrows():
                            tnum = int(r.get("test_num", 0) or 0)
                            src_name = str(r.get("source_file", "") or "").strip()
                            if tnum and src_name and src_name != "(РЅРµ РІС‹Р±СЂР°РЅРѕ)":
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
                    st.success(f"Р“РѕС‚РѕРІРѕ: РїРѕРґРіРѕС‚РѕРІР»РµРЅРѕ {created} С„Р°Р№Р»РѕРІ Txx_osc.npz (РїСЂРѕРїСѓСЃРєРѕРІ: {missing})")
            with col_m2:
                if st.button("РћС‚РєСЂС‹С‚СЊ osc_dir (РїСѓС‚СЊ)", key="show_osc_dir_hint"):
                    st.info(str(osc_dir))
        else:
            st.info("Р”Р»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ mapping РЅСѓР¶РЅС‹: (1) РЅР°Р±РѕСЂ РѕРїРѕСЂРЅС‹С… С‚РµСЃС‚РѕРІ (СЃРїРёСЃРѕРє С‚РµСЃС‚РѕРІ) Рё (2) С…РѕС‚СЏ Р±С‹ РѕРґРёРЅ С„Р°Р№Р» NPZ/CSV РІ РїР°РїРєРµ osc_dir.")

        st.markdown("---")
        st.write("РљРѕРЅРІРµСЂС‚Р°С†РёСЏ CSV вћњ NPZ (РјРёРЅРёРјР°Р»СЊРЅС‹Р№ СЂРµР¶РёРј: CSV=С‚Р°Р±Р»РёС†Р° С‡РёСЃРµР», СЃРѕС…СЂР°РЅСЏРµРј РєР°Рє main_cols/main_values).")
        if csv_files:
            csv_pick = st.selectbox(
                "CSV РґР»СЏ РєРѕРЅРІРµСЂС‚Р°С†РёРё", options=[f.name for f in csv_files], index=0, key="csv_to_npz_pick"
            )
            csv_test_num = st.number_input(
                "Р’ РєР°РєРѕР№ РЅРѕРјРµСЂ С‚РµСЃС‚Р° РїРѕР»РѕР¶РёС‚СЊ (Txx_osc.npz)", min_value=1, max_value=99, value=1, step=1, key="csv_to_npz_num"
            )
            if st.button("РљРѕРЅРІРµСЂС‚РёСЂРѕРІР°С‚СЊ CSV вћњ NPZ", key="csv_to_npz_btn"):
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
                    st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РєРѕРЅРІРµСЂС‚РёСЂРѕРІР°С‚СЊ: {e}")

        st.markdown("---")
        st.write("Р—Р°РїСѓСЃРє РїР°Р№РїР»Р°Р№РЅРѕРІ РєР°Р»РёР±СЂРѕРІРєРё (РѕРЅРё РёСЃРїРѕР»СЊР·СѓСЋС‚ С„Р°Р№Р»С‹ Txx_osc.npz РёР· osc_dir).")

        calib_mode = st.selectbox(
            "Р РµР¶РёРј РєР°Р»РёР±СЂРѕРІРєРё", options=["minimal", "full"], index=["minimal", "full"].index(str(st.session_state.get("calib_mode_pick", DIAGNOSTIC_CALIB_MODE) or DIAGNOSTIC_CALIB_MODE)) if str(st.session_state.get("calib_mode_pick", DIAGNOSTIC_CALIB_MODE) or DIAGNOSTIC_CALIB_MODE) in ["minimal", "full"] else 0, key="calib_mode_pick"
        )

        def _run_pipeline(script_rel: str, out_dir: Path, extra_args: list[str]):
            cmd = [sys.executable, str(HERE / script_rel)] + extra_args
            log_event("pipeline_start", script=script_rel, out_dir=str(out_dir), cmd=" ".join(cmd))
            out_dir.mkdir(parents=True, exist_ok=True)
            # РЎРЅРёРјРѕРє UI-Р»РѕРіРѕРІ СЂСЏРґРѕРј СЃ СЂРµР·СѓР»СЊС‚Р°С‚Р°РјРё РїР°Р№РїР»Р°Р№РЅР° (СѓРґРѕР±РЅРѕ РѕС‚РїСЂР°РІР»СЏС‚СЊ РѕРґРЅРёРј Р°СЂС…РёРІРѕРј)
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

    
        st.markdown("### РђРІС‚РѕРјР°С‚РёР·Р°С†РёСЏ (Р±РµР· РєРѕРЅСЃРѕР»Рё): РїРѕР»РЅС‹Р№ СЂР°СЃС‡С‘С‚ вћњ NPZ вћњ oneclick/autopilot")
        st.caption(
            "Р•СЃР»Рё СЂРµР°Р»СЊРЅС‹С… Р·Р°РјРµСЂРѕРІ РїРѕРєР° РЅРµС‚ вЂ” РјРѕР¶РЅРѕ РіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ В«СЂР°СЃС‡С‘С‚РЅС‹РµВ» NPZ РёР· С‚РµРєСѓС‰РµРіРѕ РѕРїРѕСЂРЅРѕРіРѕ РїСЂРѕРіРѕРЅР° "
            "Рё РіРѕРЅСЏС‚СЊ РїР°Р№РїР»Р°Р№РЅС‹ oneclick/autopilot РєР°Рє СЃР°РјРѕРїСЂРѕРІРµСЂРєСѓ С„РѕСЂРјР°С‚РѕРІ Рё РѕР±РІСЏР·РєРё."
        )

        col_fc1, col_fc2, col_fc3 = st.columns(3)

        def _ensure_full_npz_for_all_tests(_mode_label: str) -> tuple[bool, str]:
            """Р“Р°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ РІ osc_dir РµСЃС‚СЊ Txx_osc.npz РґР»СЏ РІСЃРµС… С‚РµСЃС‚РѕРІ РЅР°Р±РѕСЂР° РѕРїРѕСЂРЅС‹С… С‚РµСЃС‚РѕРІ.

            Р’РѕР·РІСЂР°С‰Р°РµС‚ (ok, message).
            """
            _tests = list((_tests_map or {}).items())
            if not _tests:
                return False, "РќРµС‚ РЅР°Р±РѕСЂР° РѕРїРѕСЂРЅС‹С… С‚РµСЃС‚РѕРІ (СЃРїРёСЃРєР° С‚РµСЃС‚РѕРІ). РЎРЅР°С‡Р°Р»Р° РІС‹РїРѕР»РЅРёС‚Рµ РѕРїРѕСЂРЅС‹Р№ РїСЂРѕРіРѕРЅ."
            if model_mod is None:
                return False, "РњРѕРґРµР»СЊ РЅРµ Р·Р°РіСЂСѓР¶РµРЅР° (model_mod=None)."
            try:
                baseline_full_cache = st.session_state.get("baseline_full_cache") or {}
                st.session_state["baseline_full_cache"] = baseline_full_cache
            except Exception:
                baseline_full_cache = {}

            # Р§С‚РѕР±С‹ UI РЅРµ Р·Р°РІРёСЃР°Р»: РѕРіСЂР°РЅРёС‡РёРј РєРѕР»РёС‡РµСЃС‚РІРѕ С‚РѕС‡РµРє
            _max_points = int(st.session_state.get("detail_max_points", 1200) or 1200)
            want_full = True

            t_start = time.time()
            missing = 0
            ok_cnt = 0

            # Р’Р°Р¶РЅРѕ РґР»СЏ calibration/pipeline_npz_oneclick_v1.py: РЅСѓР¶РµРЅ tests_index.csv СЃ РєРѕР»РѕРЅРєРѕР№ "РёРјСЏ_С‚РµСЃС‚Р°".
            # Р Р°РЅРµРµ СЌС‚Рѕ С‡Р°СЃС‚Рѕ РѕС‚СЃСѓС‚СЃС‚РІРѕРІР°Р»Рѕ => autopilot/oneclick РјРѕРіР»Рё РёСЃРєР°С‚СЊ С„Р°Р№Р»С‹ "РЅРµ С‚Р°Рј".
            try:
                write_tests_index_csv(
                    osc_dir,
                    tests=[{"name": n} for (n, _cfg) in _tests],
                    filename="tests_index.csv",
                )
            except Exception as e:
                log_event("oneclick_tests_index_write_error", err=str(e), osc_dir=str(osc_dir))

            prog = st.progress(0.0, text=f"[{_mode_label}] РџРѕРґРіРѕС‚РѕРІРєР° NPZ: СЂР°СЃС‡С‘С‚/СЌРєСЃРїРѕСЂС‚вЂ¦")
            for i, (name, cfg0) in enumerate(_tests, start=1):
                # cache key СЃРѕРІРјРµСЃС‚РёРј СЃ РѕСЃРЅРѕРІРЅС‹Рј РєСЌС€РµРј РґРµС‚Р°Р»РµР№ (baseline_full_cache)
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

                prog.progress(i / max(1, len(_tests)), text=f"[{_mode_label}] {i}/{len(_tests)}вЂ¦")

            dt_s = time.time() - t_start
            prog.progress(1.0, text=f"[{_mode_label}] Р“РѕС‚РѕРІРѕ Р·Р° {dt_s:.1f} СЃРµРє. OK={ok_cnt}, missing={missing}")

            log_event("oneclick_full_npz_done", ok=int(ok_cnt), missing=int(missing), dt_s=float(dt_s), osc_dir=str(osc_dir))
            if ok_cnt == 0:
                return False, "РќРµ СѓРґР°Р»РѕСЃСЊ СЃС„РѕСЂРјРёСЂРѕРІР°С‚СЊ РЅРё РѕРґРЅРѕРіРѕ NPZ. РџСЂРѕРІРµСЂСЊ Р»РѕРіРё/РјРѕРґРµР»СЊ."
            return True, f"NPZ РїРѕРґРіРѕС‚РѕРІР»РµРЅС‹: OK={ok_cnt}, РїСЂРѕРїСѓСЃРєРѕРІ/РѕС€РёР±РѕРє={missing}, РІСЂРµРјСЏ={dt_s:.1f} СЃРµРє."

        with col_fc1:
            if st.button("1) РџРѕР»РЅС‹Р№ Р»РѕРі + NPZ (РІСЃРµ С‚РµСЃС‚С‹)", key="oneclick_full_logs_npz"):
                ok, msg = _ensure_full_npz_for_all_tests("full_npz")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        with col_fc2:
            if st.button("2) РџРѕР»РЅС‹Р№ Р»РѕРі + NPZ вћњ oneclick", key="oneclick_full_then_oneclick"):
                ok, msg = _ensure_full_npz_for_all_tests("full_then_oneclick")
                if ok:
                    st.success(msg)
                    # Р·Р°РїСѓСЃРєР°РµРј oneclick РїР°Р№РїР»Р°Р№РЅ
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
                    st.write(f"oneclick exit code: {rc}")
                    if rc != 0:
                        st.error("oneclick Р·Р°РІРµСЂС€РёР»СЃСЏ СЃ РѕС€РёР±РєРѕР№ вЂ” СЃРј. stdout/stderr РЅРёР¶Рµ Рё С„Р°Р№Р»С‹ РІ out_dir.")
                        st.code(so[-4000:] if so else "", language="text")
                        st.code(se[-4000:] if se else "", language="text")
                    else:
                        st.success("oneclick РІС‹РїРѕР»РЅРµРЅ. Р РµР·СѓР»СЊС‚Р°С‚С‹ РІ out_dir.")
                        st.code(str(out_dir), language="text")
                else:
                    st.error(msg)

        with col_fc3:
            if st.button("3) РџРѕР»РЅС‹Р№ Р»РѕРі + NPZ вћњ autopilot (minimal)", key="oneclick_full_then_autopilot"):
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
                    st.write(f"autopilot exit code: {rc}")
                    if rc != 0:
                        st.error("autopilot Р·Р°РІРµСЂС€РёР»СЃСЏ СЃ РѕС€РёР±РєРѕР№ вЂ” СЃРј. stdout/stderr РЅРёР¶Рµ Рё С„Р°Р№Р»С‹ РІ out_dir.")
                        st.code(so[-4000:] if so else "", language="text")
                        st.code(se[-4000:] if se else "", language="text")
                    else:
                        st.success("autopilot РІС‹РїРѕР»РЅРµРЅ. Р РµР·СѓР»СЊС‚Р°С‚С‹ РІ out_dir.")
                        st.code(str(out_dir), language="text")
                else:
                    st.error(msg)

        st.markdown("---")
        col_cal1, col_cal2 = st.columns(2)
        with col_cal1:
            if st.button("Р—Р°РїСѓСЃС‚РёС‚СЊ РєР°Р»РёР±СЂРѕРІРєСѓ (oneclick)", key="run_calib_oneclick"):
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
                    st.success(f"Р“РѕС‚РѕРІРѕ: {out_dir}")
                else:
                    st.error(f"РћС€РёР±РєР° (РєРѕРґ {rc}) вЂ” СЃРј. pipeline_stderr.txt")

        with col_cal2:
            if st.button("Р—Р°РїСѓСЃС‚РёС‚СЊ Autopilot (NPZ) v19", key="run_autopilot_v19"):
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
                    st.success(f"Р“РѕС‚РѕРІРѕ: {out_dir}")
                else:
                    st.error(f"РћС€РёР±РєР° (РєРѕРґ {rc}) вЂ” СЃРј. pipeline_stderr.txt")

        last_dir = st.session_state.get("last_calib_out_dir") or st.session_state.get("last_autopilot_out_dir")
        if last_dir:
            st.info(f"РџРѕСЃР»РµРґРЅРёР№ Р·Р°РїСѓСЃРє: {last_dir}")

    # -------------------------------
    # Р”РёР°РіРЅРѕСЃС‚РёРєР° (ZIP РґР»СЏ РѕС‚РїСЂР°РІРєРё)
    # -------------------------------
    with st.expander("Р”РёР°РіРЅРѕСЃС‚РёРєР° вЂ” СЃРѕР±СЂР°С‚СЊ ZIP (РґР»СЏ РѕС‚РїСЂР°РІРєРё)", expanded=False):
        # РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РІ РїСЂРёР»РѕР¶РµРЅРёРё РµСЃС‚СЊ **РѕРґРЅР°** РєРЅРѕРїРєР° РґРёР°РіРЅРѕСЃС‚РёРєРё (РІ Р±РѕРєРѕРІРѕР№ РїР°РЅРµР»Рё):
        # В«РЎРѕС…СЂР°РЅРёС‚СЊ РґРёР°РіРЅРѕСЃС‚РёРєСѓ (ZIP)В». Р­С‚РѕС‚ UI-Р±Р»РѕРє РѕСЃС‚Р°РІР»РµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ Legacy-СЂРµР¶РёРјР°,
        # С‡С‚РѕР±С‹ РЅРµ РїР»РѕРґРёС‚СЊ РґСѓР±Р»РёСЂСѓСЋС‰РёРµ РєРЅРѕРїРєРё.
        show_legacy_tools = bool(
            st.session_state.get("pneumo_show_legacy", False)
            or os.environ.get("PNEUMO_SHOW_LEGACY", "0") == "1"
        )

        if not show_legacy_tools:
            st.info(
                "Р•РґРёРЅР°СЏ РєРЅРѕРїРєР° РґРёР°РіРЅРѕСЃС‚РёРєРё РЅР°С…РѕРґРёС‚СЃСЏ РІ Р±РѕРєРѕРІРѕР№ РїР°РЅРµР»Рё: **РЎРѕС…СЂР°РЅРёС‚СЊ РґРёР°РіРЅРѕСЃС‚РёРєСѓ (ZIP)**. "
                "Р­С‚РѕС‚ UI-Р±Р»РѕРє СЃРєСЂС‹С‚ РІ РѕСЃРЅРѕРІРЅРѕРј СЂРµР¶РёРјРµ, С‡С‚РѕР±С‹ РЅРµ РїР»РѕРґРёС‚СЊ РґСѓР±Р»РёСЂСѓСЋС‰РёРµ РєРЅРѕРїРєРё."
            )
            st.caption(
                "Р•СЃР»Рё РЅСѓР¶РЅРѕ СЃРѕР±СЂР°С‚СЊ UI-РґРёР°РіРЅРѕСЃС‚РёРєСѓ РёРјРµРЅРЅРѕ РѕС‚СЃСЋРґР°: РІРєР»СЋС‡РёС‚Рµ Legacy-СЂРµР¶РёРј "
                "РІ Р±РѕРєРѕРІРѕР№ РїР°РЅРµР»Рё (Р РµР¶РёРј РёРЅС‚РµСЂС„РµР№СЃР° в†’ РџРѕРєР°Р·Р°С‚СЊ СЃС‚СЂР°РЅРёС†С‹ Legacy)."
            )
        else:
            st.markdown(
                """
                Р­С‚Рѕ **Р»РѕРєР°Р»СЊРЅС‹Р№** ZIP, РєРѕС‚РѕСЂС‹Р№ СѓРґРѕР±РЅРѕ РѕС‚РїСЂР°РІР»СЏС‚СЊ РІРјРµСЃС‚Рѕ РІСЃРµР№ РїР°РїРєРё.

                Р’РЅСѓС‚СЂРё: Р»РѕРіРё UI, СЂРµР·СѓР»СЊС‚Р°С‚С‹, **workspace/osc** (NPZ/CSV), **calibration_runs** (oneclick/autopilot) Рё СЃРЅРёРјРѕРє С‚РµРєСѓС‰РёС… JSON (base/suite/ranges).
                """
            )
            diag_tag = st.text_input("РўСЌРі (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)", value="ui", key="ui_diag_tag")
            if st.button("РЎС„РѕСЂРјРёСЂРѕРІР°С‚СЊ ZIP РґРёР°РіРЅРѕСЃС‚РёРєРё", key="ui_diag_make_btn"):
                try:
                    zpath = make_ui_diagnostics_zip(
                        # РЎРЅРёРјРѕРє С‚РµРєСѓС‰РёС… **РїРµСЂРµР·Р°РїРёСЃР°РЅРЅС‹С…** Р·РЅР°С‡РµРЅРёР№ (Р° РЅРµ С‚РѕР»СЊРєРѕ РґРµС„РѕР»С‚РѕРІ)
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
                    st.success(f"Р“РѕС‚РѕРІРѕ: {zpath.name}")
                except Exception as e:
                    st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР±СЂР°С‚СЊ ZIP: {e}")

            zpath = st.session_state.get("ui_diag_zip_path")
            if zpath:
                try:
                    zp = Path(zpath)
                    if zp.exists():
                        st.download_button(
                            "РЎРєР°С‡Р°С‚СЊ ZIP",
                            data=zp.read_bytes(),
                            file_name=zp.name,
                            mime="application/zip",
                            key="ui_diag_download_btn",
                        )
                except Exception as e:
                    st.warning(f"РќРµ СЃРјРѕРі РїРѕРґРіРѕС‚РѕРІРёС‚СЊ download: {e}")

# -------------------------------
# РђРІС‚РѕРѕР±РЅРѕРІР»РµРЅРёРµ РїСЂРѕРіСЂРµСЃСЃР° РІРѕ РІСЂРµРјСЏ РѕРїС‚РёРјРёР·Р°С†РёРё
# -------------------------------
# Streamlit РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РїРµСЂРµСЂРёСЃРѕРІС‹РІР°РµС‚ РїСЂРёР»РѕР¶РµРЅРёРµ РїСЂРё РґРµР№СЃС‚РІРёСЏС… РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
# Р§С‚РѕР±С‹ РїСЂРѕРіСЂРµСЃСЃ С„РѕРЅРѕРІРѕРіРѕ СЂР°СЃС‡С‘С‚Р° РѕР±РЅРѕРІР»СЏР»СЃСЏ "РІР¶РёРІСѓСЋ", РґРµР»Р°РµРј РїРµСЂРёРѕРґРёС‡РµСЃРєРёР№ rerun.
#
# Р Р°РЅСЊС€Рµ СЌС‚Рѕ Р±С‹Р»Рѕ СЃРґРµР»Р°РЅРѕ С‡РµСЂРµР· time.sleep()+st.rerun(), РЅРѕ СЌС‚Рѕ:
#  1) Р±Р»РѕРєРёСЂСѓРµС‚ РїРѕС‚РѕРє РІС‹РїРѕР»РЅРµРЅРёСЏ (UI "Р·Р°РјРёСЂР°РµС‚"),
#  2) Р»РµРіРєРѕ СЃР»РѕРІРёС‚СЊ РѕС€РёР±РєРё Р»РѕРіРёРєРё rerun.
#
# РџРѕСЌС‚РѕРјСѓ РёСЃРїРѕР»СЊР·СѓРµРј С„СЂРѕРЅС‚РµРЅРґ-С‚Р°Р№РјРµСЂ streamlit-autorefresh (РµСЃР»Рё СѓСЃС‚Р°РЅРѕРІР»РµРЅ).
# РћРЅ РїРёРЅРіСѓРµС‚ СЃРµСЂРІРµСЂ Рё РєРѕСЂСЂРµРєС‚РЅРѕ РёРЅРёС†РёРёСЂСѓРµС‚ rerun Р±РµР· Р±РµСЃРєРѕРЅРµС‡РЅС‹С… С†РёРєР»РѕРІ.
if 'auto_refresh' in globals() and auto_refresh and pid_alive(st.session_state.opt_proc):
    try:
        from streamlit_autorefresh import st_autorefresh  # type: ignore

        st_autorefresh(
            interval=int(max(0.2, float(refresh_sec)) * 1000),
            key="progress_autorefresh",
        )
    except Exception:
        # Fallback (Р±РµР· Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№): СЂРµРґРєРёР№ rerun С‡РµСЂРµР· sleep.
        time.sleep(float(refresh_sec))
        do_rerun()


# --- РђРІС‚РѕСЃРѕС…СЂР°РЅРµРЅРёРµ UI (РїРѕСЃР»Рµ С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ РёРЅС‚РµСЂС„РµР№СЃР°) ---
# РќРµ РґРѕР»Р¶РЅРѕ Р»РѕРјР°С‚СЊ СЂР°СЃС‡С‘С‚С‹ РґР°Р¶Рµ РїСЂРё РїСЂРѕР±Р»РµРјР°С… СЃ РїСЂР°РІР°РјРё РЅР° РґРёСЃРє.
try:
    from pneumo_solver_ui.ui_persistence import autosave_if_enabled
    autosave_if_enabled(st)
except Exception:
    pass
