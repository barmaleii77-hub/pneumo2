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
import importlib.util
import logging
from logging.handlers import RotatingFileHandler
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

from contextlib import contextmanager

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
from pneumo_solver_ui.ui_data_helpers import decimate_minmax, downsample_df, write_tests_index_csv
from pneumo_solver_ui.ui_diagnostics_helpers import make_ui_diagnostics_zip_bundle
from pneumo_solver_ui.ui_event_sync_helpers import (
    consume_mech_pick_event as _consume_mech_pick_event_core,
    consume_playhead_event as _consume_playhead_event_core,
    consume_plotly_pick_events as _consume_plotly_pick_events_core,
    consume_svg_pick_event as _consume_svg_pick_event_core,
)
from pneumo_solver_ui.ui_flow_panel_helpers import render_flow_panel_html
from pneumo_solver_ui.ui_interaction_helpers import (
    apply_pick_list as _apply_pick_list,
    ensure_mapping_for_selection,
    extract_plotly_selection_points as _extract_plotly_selection_points,
    plotly_points_signature as _plotly_points_signature,
    strip_svg_xml_header,
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
from pneumo_solver_ui.ui_components import (
    get_mech_anim_component,
    get_mech_car3d_component,
    get_playhead_ctrl_component,
    get_pneumo_svg_flow_component,
    last_error as component_last_error,
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
from pneumo_solver_ui.ui_svg_html_builders import (
    render_svg_edge_mapper_html,
    render_svg_flow_animation_html,
    render_svg_node_mapper_html,
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
                st.info("Используйте меню навигации слева.")
        except Exception:
            st.info("Используйте меню навигации слева.")


def _opt_gateway_last_pointer_snapshot() -> dict:
    """Best-effort summary of the latest optimization pointer for the home gateway."""
    try:
        from pneumo_solver_ui import run_artifacts as _run_artifacts

        raw = dict(_run_artifacts.load_last_opt_ptr() or {})
    except Exception:
        raw = {}

    meta = dict(raw.get("meta") or {})
    run_dir = None
    raw_run_dir = raw.get("run_dir")
    if isinstance(raw_run_dir, str) and raw_run_dir.strip():
        try:
            run_dir = Path(raw_run_dir).expanduser()
        except Exception:
            run_dir = None

    mode_label = "—"
    if run_dir is not None:
        try:
            parts_lower = {str(p).lower() for p in run_dir.parts}
        except Exception:
            parts_lower = set()
        if (run_dir / "sp.json").exists() or "staged" in parts_lower:
            mode_label = "StageRunner"
        else:
            backend = str(meta.get("backend") or "").strip()
            mode_label = f"Distributed coordinator ({backend})" if backend else "Distributed coordinator"

    live_policy = {}
    if run_dir is not None and run_dir.exists():
        try:
            stage_dirs = sorted(
                [p for p in run_dir.iterdir() if p.is_dir() and re.fullmatch(r"s\d+", p.name)],
                key=lambda p: int(p.name[1:] or 0),
            )
        except Exception:
            stage_dirs = []
        if stage_dirs:
            last_stage = stage_dirs[-1]
            try:
                stage_idx = int(last_stage.name[1:] or 0)
            except Exception:
                stage_idx = 0
            stage_name = {0: "stage0_relevance", 1: "stage1_long", 2: "stage2_final"}.get(stage_idx, f"stage{stage_idx}")
            try:
                live_policy = summarize_stage_policy_runtime(run_dir, stage_idx=stage_idx, stage_name=stage_name) or {}
            except Exception:
                live_policy = {}

    sp_payload = {}
    if run_dir is not None and (run_dir / "sp.json").exists():
        try:
            sp_payload = json.loads((run_dir / "sp.json").read_text(encoding="utf-8"))
        except Exception:
            sp_payload = {}

    return {
        "raw": raw,
        "meta": meta,
        "run_dir": run_dir,
        "mode_label": mode_label,
        "live_policy": live_policy,
        "sp_payload": sp_payload,
    }


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

    st.caption(f"Seed/promotion policy: {stage_policy_mode}")
    st.caption("Stage-specific seed/promotion profile: " + stage_seed_policy_summary_text())
    st.caption(f"System Influence eps_rel: {influence_eps_rel:g}")
    st.caption("Adaptive epsilon для System Influence: " + ("on" if adaptive_influence_eps else "off"))

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
    raw = snap.get("raw") or {}
    if not raw:
        st.info("Последняя оптимизация пока не запускалась (или указатель ещё не записан).")
        st.markdown("**Seed/promotion policy (текущая стадия)**")
        st.caption("Будет видно после staged run, когда появятся stage artifacts и live policy summary.")
        return

    meta = snap.get("meta") or {}
    run_dir = snap.get("run_dir")
    mode_label = str(snap.get("mode_label") or "—")
    if compact:
        st.write(f"**Путь:** `{run_dir}`")
        st.caption(f"Режим: {mode_label}")
        st.caption(f"Время: {meta.get('ts', raw.get('updated_at', '—'))}")
    else:
        cols = st.columns(3)
        with cols[0]:
            st.metric("Последний режим", mode_label)
        with cols[1]:
            st.metric("Backend", str(meta.get("backend") or "—"))
        with cols[2]:
            st.metric("Время", str(meta.get("ts") or raw.get("updated_at") or "—"))
        st.caption(f"Папка: `{run_dir}`")

    sp_payload = snap.get("sp_payload") or {}
    if sp_payload:
        st.caption(
            "StageRunner pointer: "
            f"status={sp_payload.get('status') or '—'}, ts={sp_payload.get('ts') or '—'}"
        )

    live_policy = snap.get("live_policy") or {}
    st.markdown("**Seed/promotion policy (текущая стадия)**")
    if live_policy.get("available"):
        st.caption(
            f"requested={live_policy.get('requested_mode') or '—'} → effective={live_policy.get('effective_mode') or '—'}; "
            f"policy={live_policy.get('policy_name') or '—'}"
        )
        if str(live_policy.get("summary_line") or "").strip():
            st.caption(str(live_policy.get("summary_line") or ""))
    else:
        st.caption("Будет видно после staged run, когда появятся stage artifacts и live policy summary.")


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

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # не падаем, если нет прав на запись — просто отключим файловое логирование
    LOG_DIR = None  # type: ignore

_APP_LOGGER = logging.getLogger("pneumo_ui")
_APP_LOGGER.setLevel(logging.INFO)
_APP_LOGGER.propagate = False


def _init_file_logger_once() -> None:
    """Инициализировать логгер один раз на сессию Streamlit.

    В Streamlit скрипт перезапускается на каждое изменение виджетов.
    Нельзя добавлять хендлер каждый раз, иначе будут дубликаты строк.
    """

    # Папка логов может быть недоступна (например, read-only).
    if LOG_DIR is None:
        return

    # log_path храним в session_state, чтобы был один файл на сессию
    if "_log_path" not in st.session_state:
        sid = st.session_state.get("_session_id")
        if not sid:
            # Prefer launcher-provided run_id (stable folder name), fallback to timestamp+pid
            sid = (os.environ.get("PNEUMO_RUN_ID") or "").strip()
            if not sid:
                sid = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_pid{os.getpid()}"
            st.session_state["_session_id"] = sid
            st.session_state.setdefault("_session_started", time.time())
        st.session_state["_log_path"] = str((LOG_DIR / f"ui_{sid}.log").resolve())

    log_path = st.session_state.get("_log_path")
    if not log_path:
        return

    # Проверяем: уже есть хендлер на этот файл?
    for h in list(_APP_LOGGER.handlers):
        if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == log_path:
            return

    try:
        h = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        h.setFormatter(fmt)
        _APP_LOGGER.addHandler(h)
    except Exception:
        # не фейлим UI из-за логирования
        return


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
        _init_file_logger_once()

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
            mp = LOG_DIR / f"metrics_{sid}.jsonl"
            # combined metrics jsonl
            mcp = LOG_DIR / "metrics_combined.jsonl"
            # optional combined text
            ucp = LOG_DIR / "ui_combined.log"

            global _UI_LOG_WRITE_LOCK
            try:
                _ = _UI_LOG_WRITE_LOCK
            except NameError:
                _UI_LOG_WRITE_LOCK = None  # type: ignore

            if _UI_LOG_WRITE_LOCK is None:
                try:
                    import threading

                    _UI_LOG_WRITE_LOCK = threading.Lock()  # type: ignore
                except Exception:
                    _UI_LOG_WRITE_LOCK = False  # type: ignore

            try:
                if _UI_LOG_WRITE_LOCK:
                    with _UI_LOG_WRITE_LOCK:  # type: ignore
                        with open(mp, "a", encoding="utf-8", errors="replace") as f:
                            f.write(line + "\n")
                        with open(mcp, "a", encoding="utf-8", errors="replace") as f:
                            f.write(line + "\n")
                        # ui_combined.log: for humans (not jsonl)
                        try:
                            with open(ucp, "a", encoding="utf-8", errors="replace") as f:
                                f.write(line + "\n")
                        except Exception:
                            pass
                else:
                    # no lock available
                    with open(mp, "a", encoding="utf-8", errors="replace") as f:
                        f.write(line + "\n")
                    with open(mcp, "a", encoding="utf-8", errors="replace") as f:
                        f.write(line + "\n")
                    try:
                        with open(ucp, "a", encoding="utf-8", errors="replace") as f:
                            f.write(line + "\n")
                    except Exception:
                        pass
            except Exception:
                pass

    except Exception:
        return



# Пробрасываем callback для внутренних модулей (fallback-анимации) без прямого импорта этого файла.
try:
    # В Streamlit-сессии можно хранить callable. Это нужно для mech_anim_fallback.
    st.session_state["_log_event_cb"] = log_event
except Exception:
    pass


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



consume_svg_pick_event = partial(
    _consume_svg_pick_event_core,
    st.session_state,
    apply_pick_list_fn=_apply_pick_list,
)


consume_mech_pick_event = partial(
    _consume_mech_pick_event_core,
    st.session_state,
)


consume_plotly_pick_events = partial(
    _consume_plotly_pick_events_core,
    st.session_state,
    extract_plotly_selection_points_fn=_extract_plotly_selection_points,
    plotly_points_signature_fn=_plotly_points_signature,
    apply_pick_list_fn=_apply_pick_list,
)


consume_playhead_event = partial(
    _consume_playhead_event_core,
    st.session_state,
    persist_browser_perf_snapshot_event_fn=persist_browser_perf_snapshot_event,
    workspace_exports_dir=WORKSPACE_EXPORTS_DIR,
    log_event_fn=log_event,
    proc_metrics_fn=_proc_metrics,
)




def load_py_module(path: Path, module_name: str):
    """Load a module from a file path with canonical package context.

    Important for project files that use relative imports (``from .x import ...``)
    and for sibling imports such as ``import road_surface``.
    """
    return load_python_module_from_path(
        path,
        module_name,
        log=lambda event, message, **kw: _emit(event, message, **kw),
    )



def safe_dataframe(df: pd.DataFrame, height: int = 240, hide_index: bool = False, *, max_cols: int = 10, key: str = ""):
    """Render a dataframe without forcing users into horizontal scrolling.

    Why:
    - Wide tables are hard to read and require horizontal scroll (bad UX).
    - For wide outputs we show a compact preview (first columns) + a row "card" with full details.

    Notes:
    - This is a UI helper. Return value is not relied upon in the app.
    - `max_cols` is the number of columns shown in the preview table.
    """
    try:
        if df is None:
            st.info("Нет данных.")
            return None

        # Defensive conversion: in case df is not a DataFrame
        if not isinstance(df, pd.DataFrame):
            try:
                df = pd.DataFrame(df)
            except Exception:
                st.write(df)
                return None

        ncols = int(df.shape[1]) if hasattr(df, "shape") else 0
        nrows = int(df.shape[0]) if hasattr(df, "shape") else 0

        if ncols > int(max_cols):
            # Stable-ish widget key to avoid collisions across multiple calls
            if not key:
                h = hashlib.md5((str(list(df.columns)) + f"::{nrows}x{ncols}").encode("utf-8")).hexdigest()[:10]
                key = f"wide_df_{h}"

            cols_preview = list(df.columns)[: int(max_cols)]
            st.caption(f"Таблица широкая: {ncols} колонок. Показаны первые {len(cols_preview)}. Полные данные — в карточке строки ниже.")

            # Preview table (no horizontal scroll)
            try:
                st.dataframe(df[cols_preview], width="stretch", height=height, hide_index=hide_index)
            except TypeError:
                try:
                    st.dataframe(df[cols_preview], width="stretch", height=height)
                except Exception:
                    st.write(df[cols_preview])

            # Row details (master-detail)
            with st.expander("Детали выбранной строки", expanded=False):
                if nrows <= 0:
                    st.info("Пустая таблица.")
                else:
                    # Prefer slider (no typing) for typical table sizes; fallback to number input for huge tables
                    if nrows <= 2000:
                        sel = st.slider("Выбор строки", 0, max(0, nrows - 1), 0, step=1, key=f"{key}__row")
                    else:
                        sel = st.number_input("Номер строки", min_value=0, max_value=max(0, nrows - 1), value=0, step=1, key=f"{key}__row")
                    try:
                        i = int(sel)
                    except Exception:
                        i = 0

                    # Optional label for the selected row (helps orientation)
                    _label_cols = [c for c in ["id", "name", "имя", "параметр", "тест", "test", "финал", "поколение"] if c in df.columns]
                    if _label_cols:
                        try:
                            st.caption(f"Строка {i}: {_label_cols[0]} = {df.iloc[i][_label_cols[0]]}")
                        except Exception:
                            pass

                    try:
                        rec = df.iloc[i].to_dict()
                        st.json(rec)
                    except Exception:
                        st.write(df.iloc[i])

            return None

        # Normal case: not wide
        try:
            # Newer Streamlit (preferred)
            return st.dataframe(df, width="stretch", height=height, hide_index=hide_index)
        except TypeError:
            try:
                # Some versions don't have hide_index
                return st.dataframe(df, width="stretch", height=height)
            except TypeError:
                try:
                    # Older Streamlit
                    return st.dataframe(df, width="stretch", height=height, hide_index=hide_index)
                except TypeError:
                    return st.dataframe(df, width="stretch", height=height)
    except Exception:
        # Last resort: plain output
        st.write(df)
        return None



@contextmanager
def ui_popover(label: str, expanded: bool = False):
    """Popover if available, otherwise an expander.

    Удобно прятать редкие/расширенные настройки, чтобы основной UI был спокойнее.
    """
    pop = getattr(st, "popover", None)
    if callable(pop):
        with st.popover(label):
            yield
    else:
        with st.expander(label, expanded=expanded):
            yield



def safe_plotly_chart(fig, *, key=None, on_select=None, selection_mode=None):
    """Безопасная обёртка над st.plotly_chart для разных версий Streamlit.

    Цели:
    - НЕ использовать `use_container_width` в нормальном режиме (Streamlit его депрецирует).
    - Поддержать разные сигнатуры (on_select/selection_mode могли меняться).
    - При несовместимости аргументов пробуем более "простые" варианты вызова.
    """
    # 1) Самый новый API: width="stretch" (см. Streamlit docs).
    kwargs = {"width": "stretch", "key": key}

    # В некоторых версиях `on_select` НЕ принимает None.
    if on_select is not None:
        kwargs["on_select"] = on_select
    if selection_mode is not None:
        kwargs["selection_mode"] = selection_mode

    try:
        return st.plotly_chart(fig, **kwargs)
    except TypeError:
        # 2) Убираем "плавающие" args, оставляем только безопасное.
        try:
            return st.plotly_chart(fig, width="stretch", key=key)
        except TypeError:
            # 3) Совсем старый API: без width -> fallback на use_container_width.
            # В новых версиях это даст warning, но сюда мы попадаем только если width не поддержан.
            return st.plotly_chart(fig, use_container_width=True, key=key)


def safe_image(img, *, caption=None):
    """Безопасный st.image без депрецированного use_container_width.

    1) Пробуем новый API: width="stretch"
    2) Если конкретная версия Streamlit не принимает строковый width -> пробуем большой int
    3) Если совсем старый Streamlit -> fallback на use_container_width (там обычно ещё нет предупреждения)
    """
    try:
        return st.image(img, caption=caption, width="stretch")
    except Exception:
        try:
            return st.image(img, caption=caption, width=2000)
        except TypeError:
            return st.image(img, caption=caption, use_container_width=True)


make_ui_diagnostics_zip = partial(
    make_ui_diagnostics_zip_bundle,
    here=HERE,
    workspace_dir=WORKSPACE_DIR,
    log_dir=LOG_DIR,
    app_release=APP_RELEASE,
    json_safe_fn=_json_safe,
)
# ------------------------- Persistent cache (baseline/details) -------------------------
# Цель: после refresh (новая session_state) не пересчитывать baseline/детальный прогон,
# а подхватывать с диска. Кэш хранится в WORKSPACE_DIR/cache/baseline/<key>/...

def baseline_cache_dir(base_hash: str, suite_hash: str, model_file: str) -> Path:
    """Deterministic cache dir for the given (model, base, suite)."""
    try:
        mf = Path(model_file)
        model_tag = _sanitize_id(mf.stem, max_len=32)
        # Important: do NOT rely on the absolute path. Users keep unpacking new
        # releases into new folders, which would invalidate cache and force
        # baseline recalculation after every update.
        if mf.is_file():
            h = hashlib.sha1()
            with mf.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            model_hash = h.hexdigest()[:12]
        else:
            model_hash = stable_obj_hash(str(mf.resolve()))
    except Exception:
        model_tag = "model"
        model_hash = stable_obj_hash(str(model_file))
    key = f"{base_hash}_{suite_hash}_{model_tag}_{model_hash}"
    return WORKSPACE_DIR / "cache" / "baseline" / key


# Shared baseline-cache wrappers override the legacy inline copies above.
def save_last_baseline_ptr(cache_dir: Path, meta: Dict[str, Any]) -> None:
    return save_ui_last_baseline_ptr(cache_dir, meta, workspace_dir=WORKSPACE_DIR)


def load_last_baseline_ptr() -> Optional[Dict[str, Any]]:
    return load_ui_last_baseline_ptr(workspace_dir=WORKSPACE_DIR)


def load_baseline_cache(cache_dir: Path) -> Optional[Dict[str, Any]]:
    return load_ui_baseline_cache(cache_dir)


def save_baseline_cache(
    cache_dir: Path,
    baseline_df: pd.DataFrame,
    tests_map: Dict[str, Any],
    base_override: Dict[str, Any],
    meta: Dict[str, Any],
) -> None:
    return save_ui_baseline_cache(
        cache_dir,
        baseline_df,
        tests_map,
        base_override,
        meta,
        workspace_dir=WORKSPACE_DIR,
        json_safe_fn=_json_safe,
        log_event_fn=log_event,
    )


# Shared detail-cache wrappers override the legacy inline copies above.
def save_detail_cache(cache_dir: Path, test_name: str, dt: float, t_end: float, max_points: int, want_full: bool, payload: Dict[str, Any]) -> Optional[Path]:
    return save_ui_detail_cache(
        cache_dir,
        test_name,
        dt,
        t_end,
        max_points,
        want_full,
        payload,
        sanitize_test_name=sanitize_test_name,
        dump_payload_fn=_dump_detail_cache_payload,
        float_tag_fn=_float_tag,
        log_event_fn=log_event,
    )


def load_detail_cache(cache_dir: Path, test_name: str, dt: float, t_end: float, max_points: int, want_full: bool) -> Optional[Dict[str, Any]]:
    def _resave_detail_payload(loaded_payload: Dict[str, Any]) -> Optional[Path]:
        return save_detail_cache(cache_dir, test_name, dt, t_end, max_points, want_full, loaded_payload)

    return load_ui_detail_cache(
        cache_dir,
        test_name,
        dt,
        t_end,
        max_points,
        want_full,
        sanitize_test_name=sanitize_test_name,
        load_payload_fn=_load_detail_cache_payload,
        resave_payload_fn=_resave_detail_payload,
        float_tag_fn=_float_tag,
        log_event_fn=log_event,
    )


# -------------------------------
# Graph Studio helpers (v7.32)
# -------------------------------

_infer_unit_and_transform = partial(
    infer_plot_unit_and_transform,
    pressure_unit_label="бар (изб.)",
    pressure_offset_pa=lambda: P_ATM,
    pressure_divisor_pa=lambda: BAR_PA,
    length_unit_label="мм",
    length_scale=1000.0,
)


def plot_studio_timeseries(
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


# -------------------------------
# Event/alert detection for the global timeline (playhead)
# -------------------------------

def compute_events(
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


def plot_lines(
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










# Shared worker/process helpers override the legacy inline copy above.
start_worker = partial(
    start_background_worker,
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

st.title("Пневмоподвеска: расчёт и оптимизация")

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
        "Здесь включается автосохранение значений, чтобы они не исчезали при обновлении страницы "
        "или повторном запуске приложения."
    )

    # Включено по умолчанию. Можно отключить, если нужен «чистый» запуск.
    st.toggle(
        "Автосохранение (рекомендуется)",
        value=bool(st.session_state.get("ui_autosave_enabled", True)),
        key="ui_autosave_enabled",
        help=(
            "Если включено, приложение автоматически сохраняет введённые значения (таблицы параметров/тестов и ключевые настройки) "
            "в небольшой JSON-файл на диске."
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
                st.warning("Сброс удалит введённые таблицы и сохранение. Отменить нельзя.")
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
                        st.success("Сброшено. Перезагрузка…")
                        st.rerun()
                with c_no:
                    if st.button("Отмена", key="ui_reset_input_no", width="stretch"):
                        st.session_state["ui_reset_input_confirm"] = False
    except Exception:
        # эта панель не должна ломать UI
        pass

    st.header("Файлы проекта")
    model_path = st.text_input(
        "Файл модели (py)",
        value=str(_suggest_default_model_path(HERE)),
        key="ui_model_path",
        help="Python‑файл, где описана модель подвески/пневмосистемы. Обычно менять не нужно.",
    )
    worker_path = st.text_input(
        "Файл оптимизатора (py)",
        value=str(canonical_worker_path(HERE)),
        key="ui_worker_path",
        help="Python‑файл, который запускает оптимизацию. Обычно менять не нужно.",
    )

    st.divider()
    st.header("Настройки тест-набора")
    st.caption("Шаг dt, длительность t_end и момент ступеньки t_step задаются в таблице тест-набора (в основной части экрана). Это сделано специально, чтобы не было двойного ввода времени тестов.")

    st.header("Оптимизация")
    st.caption(
        "Здесь задаются параметры запуска оптимизатора (время, параллельность, сохранение прогресса). "
        "Диапазоны оптимизируемых параметров задаются в таблице «Исходные данные»."
    )

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

    # Главная больше не держит второй optimization control plane.
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

    # Legacy home control plane retained only as dormant source surface
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
                "Авто‑обновлять baseline_best.json",
                value=bool(st.session_state.get("opt_autoupdate_baseline", True)),
                key="opt_autoupdate_baseline",
                help=(
                    "Если найден кандидат лучше текущего опорного прогона, StageRunner запишет его в "
                    "workspace/baselines/baseline_best.json. Этот файл можно использовать как новый старт."
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
                            "none: без warm‑start."
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
                        "Surrogate top‑k",
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
                        "Seed/promotion policy",
                        options=["influence_weighted", "static"],
                        index=["influence_weighted", "static"].index(str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE)) if str(st.session_state.get("stage_policy_mode", DEFAULT_STAGE_POLICY_MODE) or DEFAULT_STAGE_POLICY_MODE) in ["influence_weighted", "static"] else 0,
                        key="stage_policy_mode",
                        help=(
                            "influence_weighted — seed budgeting и promotion учитывают stage-specific influence summary: "
                            "stage0 остаётся широким, stage1 уже фокусируется, stage2 продвигает только узко релевантные параметры.\n"
                            "static — историческое поведение: только score/ranges без приоритизации параметров по стадии."
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

            st.divider()
            st.subheader("Инженерный control plane: distributed / BoTorch / coordinator")
            st.caption(
                "Эти настройки раньше жили отдельно на странице «Оптимизация» и в coordinator CLI. "
                "Теперь они снова видимы прямо здесь и пишутся в тот же session_state."
            )

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
                        "Seed (distributed / coordinator)",
                        min_value=0,
                        max_value=2**31 - 1,
                        value=int(st.session_state.get("opt_seed", DIST_OPT_SEED_DEFAULT) or DIST_OPT_SEED_DEFAULT),
                        step=1,
                        key="opt_seed",
                        help="Seed для coordinator / proposer path. Отличается от seed_candidates/seed_conditions локального StageRunner.",
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
                        "q (сколько кандидатов предлагать за шаг)",
                        min_value=1,
                        max_value=256,
                        value=int(st.session_state.get("opt_q", DIST_OPT_Q_DEFAULT) or DIST_OPT_Q_DEFAULT),
                        step=1,
                        key="opt_q",
                        help="Для qNEHVI/portfolio можно предлагать пачку кандидатов за итерацию.",
                    )
                with c_alg9:
                    _dev_opts = ["auto", "cpu", "cuda"]
                    _dev_val = str(st.session_state.get("opt_device", DIST_OPT_DEVICE_DEFAULT) or DIST_OPT_DEVICE_DEFAULT)
                    st.selectbox(
                        "Устройство для модели (device)",
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
                    "qNEHVI gate: proposer включается не сразу. Сначала coordinator проходит warmup, затем требует feasible history: "
                    "done >= n_init и feasible >= min_feasible. Иначе используется random/LHS path."
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
                        help="Опциональный JSON-объект, который будет слит с базовым runtime_env координатора.",
                    )
                    st.text_area(
                        "Ray runtime exclude (по одному паттерну в строке)",
                        value=str(st.session_state.get("ray_runtime_exclude", "") or ""),
                        height=90,
                        key="ray_runtime_exclude",
                        help="Исключения при упаковке кода в Ray runtime_env.",
                    )
                    st.number_input(
                        "Ray evaluators",
                        min_value=0,
                        max_value=4096,
                        value=int(st.session_state.get("ray_num_evaluators", 0) or 0),
                        step=1,
                        key="ray_num_evaluators",
                        help="0 — coordinator сам выберет.",
                    )
                    st.number_input(
                        "CPU на evaluator",
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
                        help="0=auto (использовать доступные GPU если qNEHVI).",
                    )
                    st.number_input(
                        "GPU на proposer",
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
                        "Писать hypervolume log",
                        value=bool(st.session_state.get("opt_hv_log", DIST_OPT_HV_LOG_DEFAULT)),
                        key="opt_hv_log",
                        help="Если включено — coordinator пишет progress_hv.csv по feasible Pareto-front.",
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
                        help="0 — auto threshold (~2×(dim+1), но не меньше 10).",
                    )
                    st.number_input(
                        "min-feasible",
                        min_value=0,
                        max_value=100000,
                        value=int(st.session_state.get("opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT) or DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT),
                        step=1,
                        key="opt_botorch_min_feasible",
                        help="0 — gate отключён.",
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
                        help="Обычно это стоит оставить включённым; отключать только для осознанной диагностики qNEHVI path.",
                    )
                    st.info(
                        "Эти ручки действуют и для локального proposer path, и для Ray proposer actors. "
                        "То есть UI и coordinator теперь реально говорят на одном контракте."
                    )

            st.info(
                "В этом control plane больше нет ‘CLI-only’ заглушек: поля выше действительно wired в текущий distributed coordinator path."
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

    worker_mod = load_py_module(Path(resolved_worker_path), "opt_worker_mod")
    model_mod = load_py_module(Path(resolved_model_path), "pneumo_model_mod")
except Exception as e:
    st.error(f"Не могу загрузить модель/оптимизатор: {e}")
    st.stop()

P_ATM = float(getattr(model_mod, "P_ATM", 101325.0))
# ВАЖНО: внутри модели давления = Па (абсолютные).
# В UI показываем давление как "бар (изб.)" (gauge) относительно P_ATM.
# (1 bar = 100000 Па). 1 atm = 101325 Па оставляем для совместимости со старыми профилями/кэшем.
ATM_PA = 101325.0  # legacy
BAR_PA = 1e5


pa_abs_to_bar_g = partial(pa_abs_to_gauge, pressure_offset_pa=P_ATM, pressure_divisor_pa=BAR_PA)
bar_g_to_pa_abs = partial(gauge_to_pa_abs, pressure_offset_pa=P_ATM, pressure_divisor_pa=BAR_PA)



# legacy (оставлено для совместимости со старыми профилями)
# ВАЖНО: не переопределяем pa_abs_to_bar_g. Бар(g) должен оставаться бар(g).

pa_abs_to_atm_g = partial(pa_abs_to_gauge, pressure_offset_pa=P_ATM, pressure_divisor_pa=ATM_PA)
atm_g_to_pa_abs = partial(gauge_to_pa_abs, pressure_offset_pa=P_ATM, pressure_divisor_pa=ATM_PA)
is_length_param = is_length_param_name


# -------------------------------
# Описания/единицы параметров (для UI)
# ВАЖНО: эти функции должны быть определены ДО того, как мы строим таблицу df_opt.
# Иначе Python упадёт с NameError, т.к. модуль выполняется сверху вниз.
# -------------------------------


param_unit = partial(
    param_unit_label,
    pressure_unit_label="бар (изб.)",
    is_pressure_param_fn=is_pressure_param,
    is_volume_param_fn=is_volume_param,
    is_small_volume_param_fn=is_small_volume_param,
)


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


_si_to_ui = partial(si_to_ui_value, p_atm=P_ATM, bar_pa=BAR_PA)
_ui_to_si = partial(ui_to_si_value, p_atm=P_ATM, bar_pa=BAR_PA)


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
        "единица": meta.get("ед", "СИ"),
        "значение": val_ui,
        "оптимизировать": bool(is_opt),
        "мин": mn_ui,
        "макс": mx_ui,
        "пояснение": meta.get("описание", ""),
        "_key": k,
        "_kind": kind,
    })

df_params0 = pd.DataFrame(rows)


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
# Тест-набор и пороги (редактируется из UI)
# -------------------------------
st.subheader("Тест-набор и пороги")
st.caption(
    "Здесь задаются параметры тестов и целевые запасы/ограничения. "
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
    suite_upload = st.file_uploader("Загрузить тест-набор (JSON)", type=["json"], help="Можно загрузить ранее сохранённый suite.json")
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
                st.success("Тест-набор загружен.")
                try:
                    from pneumo_solver_ui.ui_persistence import autosave_now
                    autosave_now(st)
                except Exception:
                    pass
            else:
                st.error("suite.json должен быть списком объектов (list[dict]).")
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
    st.download_button("Скачать тест-набор (JSON)", data=suite_bytes, file_name="suite.json", mime="application/json")


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
            mask = (
                view["имя"].astype(str).str.contains(q, case=False, na=False)
                | view["тип"].astype(str).str.contains(q, case=False, na=False)
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
        _ensure_stage_visible_in_filter(row_new.get("стадия", 0))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Тест-шаблон добавлен в набор.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось добавить тест-шаблон: {exc}")


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
        _suite_set_flash("success", "Видимые тесты обновлены.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось обновить видимые тесты: {exc}")


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
        row["имя"] = f"{row.get('имя', 'Тест')} (копия)"
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df = ensure_suite_columns(df, context="pneumo_ui_app.duplicate_selected_callback.final")
        st.session_state["df_suite_edit"] = df
        _queue_suite_selected_id(str(row["id"]))
        _ensure_stage_visible_in_filter(row.get("стадия", 0))
        st.session_state["_ui_suite_autosave_pending"] = True
        _suite_set_flash("success", "Выбранный тест продублирован.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось продублировать тест: {exc}")


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
        _suite_set_flash("success", "Выбранный тест удалён из набора.")
    except Exception as exc:
        _suite_set_flash("error", f"Не удалось удалить тест: {exc}")


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


st.caption(
    "Тест-набор настраивается без широкой таблицы: выбери тест в списке → справа карточка. "
    "Есть быстрый генератор шаблонов."
)
_suite_maybe_autosave_pending()
_suite_render_flash()
st.session_state.pop("ui_suite_selected_row", None)

# Быстрый мастер добавления тестов
wiz_l, wiz_r = st.columns([1.2, 1.0], gap="medium")
with wiz_l:
    _preset = st.selectbox(
        "Добавить тест-шаблон",
        options=[
            "worldroad_flat",
            "worldroad_sine_x",
            "worldroad_bump",
            "inertia_brake",
        ],
        format_func={
            "worldroad_flat": "WorldRoad: ровная дорога",
            "worldroad_sine_x": "WorldRoad: синус вдоль (A=2 см, λ=2 м)",
            "worldroad_bump": "WorldRoad: бугор (h=4 см, w=0.6 м)",
            "inertia_brake": "Инерция: торможение ax=-3 м/с²",
        }.get,
        help="Шаблон добавит новый тест с разумными настройками. Затем можно уточнить в карточке справа.",
        index=["worldroad_flat", "worldroad_sine_x", "worldroad_bump", "inertia_brake"].index(str(st.session_state.get("ui_suite_preset", DIAGNOSTIC_SUITE_PRESET) or DIAGNOSTIC_SUITE_PRESET)) if str(st.session_state.get("ui_suite_preset", DIAGNOSTIC_SUITE_PRESET) or DIAGNOSTIC_SUITE_PRESET) in ["worldroad_flat", "worldroad_sine_x", "worldroad_bump", "inertia_brake"] else 0,
        key="ui_suite_preset",
    )
with wiz_r:
    st.button(
        "Добавить",
        width="stretch",
        key="ui_suite_add_preset_btn",
        on_click=_suite_add_preset_callback,
        args=(str(_preset),),
    )


# -------------------------------
# Сценарии: новый редактор (сегменты‑кольцо)
st.markdown("### Сценарий: сегменты‑кольцо")

if not _HAS_RING_SCENARIO_EDITOR:
    st.error(
        "Редактор сценариев (сегменты‑кольцо) недоступен (не удалось импортировать pneumo_solver_ui.ui_scenario_ring). "
        "Переустановите зависимости/проверьте целостность архива."
    )
else:
    # ВАЖНО (ABSOLUTE LAW):
    #  - Никаких выдуманных параметров и псевдонимов.
    #  - Сценарий хранится в scenario_json и является единственным источником истины.
    #  - road_csv / axay_csv генерируются строго как производные от scenario_json.
    with st.expander("Открыть редактор сценариев (сегменты‑кольцо)", expanded=True):
        try:
            try:
                _ring_wheelbase_m = float(base_override.get("база", 0.0))
            except Exception:
                _ring_wheelbase_m = 0.0
                logging.warning("[RING] Не удалось прочитать канонический параметр 'база' для wheelbase_m.")
                st.warning(
                    "Не удалось прочитать канонический параметр **'база'**. Генерация ring-сценария потребует исправить base.",
                    icon="⚠️",
                )

            if _ring_wheelbase_m <= 0.0:
                logging.warning("[RING] Некорректная база для ring-сценария: %s", _ring_wheelbase_m)
                st.warning(
                    "Колёсная база для ring-сценария берётся только из канонического параметра **'база'** и сейчас <= 0. "
                    "Проверьте исходные данные модели.",
                    icon="⚠️",
                )

            df_suite_edit = render_ring_scenario_generator(
                df_suite_edit,
                work_dir=WORKSPACE_DIR,
                wheelbase_m=float(_ring_wheelbase_m),
                default_dt_s=0.01,
            )
        except Exception as e:
            st.error(f"Ошибка в редакторе сценариев: {e}")
# Фильтры списка
def _sync_multiselect_all(key: str, options: list, *, cast=int) -> None:
    """Делает мультиселект устойчивым к изменению options.

    Если раньше пользователь держал выбранными *все* доступные значения,
    то при появлении новых значений они автоматически добавятся в выбор.
    Если пользователь фильтровал вручную — мы это уважаем.
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
        # оставляем только валидные значения
        try:
            cur_list = [cast(x) for x in list(cur)]
        except Exception:
            try:
                cur_list = list(cur)
            except Exception:
                cur_list = []
        cur_list = [x for x in cur_list if x in opts_norm]

        # если ранее были выбраны все предыдущие опции — выбираем все новые
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

# Streamlit запрещает менять значение widget-key после создания самого widget.
# Поэтому кнопки ниже ставят только pending-flag, а фактический reset/extend
# выполняется здесь, ДО рендера multiselect/checkbox/text_input.
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
        "Стадии",
        options=_stages,
        default=_stages,
        help="Показывать тесты выбранных стадий.",
        key="ui_suite_stage_filter",
    )
with f2:
    only_enabled = st.checkbox(
        "Только включённые",
        value=False,
        key="ui_suite_only_enabled",
        help="Скрывает выключенные тесты.",
    )
with f3:
    suite_search = st.text_input(
        "Поиск",
        value=st.session_state.get("ui_suite_search", ""),
        key="ui_suite_search",
        help="Ищет по имени теста и типу.",
    ).strip()
with f4:
    st.button(
        "Сбросить фильтры",
        width="stretch",
        key="ui_suite_reset_filters_btn",
        on_click=_suite_reset_filters_callback,
        args=(list(_stages),),
    )

st.caption("Логика staged optimization: S0 — быстрый relevance-screen; S1 — длинные дорожные/манёвренные тесты; S2 — финальная robustness-стадия. Номер в колонке «Стадия» означает момент первого входа теста: stage 1 не должен молча переписываться в 0.")

# Список тестов
_df_view = _suite_filtered_view(df_suite_edit, stage_filter, False, "")
if only_enabled:
    _df_view = _df_view[_df_view["включен"].astype(bool)]
if suite_search:
    _mask = (
        _df_view["имя"].astype(str).str.contains(suite_search, case=False, na=False)
        | _df_view["тип"].astype(str).str.contains(suite_search, case=False, na=False)
    )
    _df_view = _df_view[_mask]

# Подсказка: сколько тестов скрыто фильтрами (частая причина "пропажи" тестов)
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
            f"Показано **{_n_vis}** из **{_n_total}** тестов. Скрыто **{_n_hidden}** — проверь фильтры стадий/включения/поиск."
        )
    with cols_info[1]:
        st.button(
            "Показать все",
            key="ui_suite_show_all_btn",
            width="stretch",
            on_click=_suite_show_all_callback,
            args=(list(_stages),),
        )

# Важно: используем стабильный ID (а не индекс DataFrame),
# иначе selection в st.dataframe часто «отстаёт на 1 rerun» и требует двойного клика.
_row_ids = _df_view["id"].astype(str).tolist() if ("id" in _df_view.columns) else []

# Нормализуем выбранный id ДО рендера selectbox.
# Нормальная UX-политика: если список тестов не пуст, выбранный сценарий должен быть всегда.
# Дефолтный старт без автозапуска обеспечивается тем, что shipped default-suite приходит
# с выключенными сценариями, а не пустым forced-selection.
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

# Кнопки действий (над списком)
a1, a2, a3, a4 = st.columns([1, 1, 1, 1], gap="small")
with a1:
    st.button(
        "Включить все",
        width="stretch",
        key="ui_suite_enable_visible_btn",
        on_click=_suite_set_enabled_visible_callback,
        args=(True,),
        disabled=not bool(_row_ids),
    )
with a2:
    st.button(
        "Выключить все",
        width="stretch",
        key="ui_suite_disable_visible_btn",
        on_click=_suite_set_enabled_visible_callback,
        args=(False,),
        disabled=not bool(_row_ids),
    )
with a3:
    st.button(
        "Дублировать выбранный",
        width="stretch",
        key="ui_suite_duplicate_selected_btn",
        on_click=_suite_duplicate_selected_callback,
        disabled=not bool(_cur_sel),
    )
with a4:
    st.button(
        "Удалить выбранный",
        width="stretch",
        key="ui_suite_delete_selected_btn",
        on_click=_suite_delete_selected_callback,
        disabled=not bool(_cur_sel),
    )

left, right = st.columns([1.05, 1.0], gap="large")
with left:
    if _df_view.empty:
        st.info("Список пуст (в текущем фильтре).")
    else:
        st.caption("Список тестов (без горизонтального скролла).")

        def _label_for_id(_id: str) -> str:
            try:
                _r = _df_view[_df_view["id"].astype(str) == str(_id)].iloc[0].to_dict()
                en = "✓" if bool(_r.get("включен", False)) else " "
                stg = int(infer_suite_stage(_r))
                nm = str(_r.get("имя", "")).strip() or "<без имени>"
                tp = str(_r.get("тип", "")).strip() or "<без типа>"
                return f"{en} [S{stg}] {nm} — {tp}"
            except Exception:
                return str(_id)

        # выбор теста: selectbox над таблицей (устраняет баги selection/rerun и «двойной клик»)
        if _row_ids:
            _suite_select_options = list(_row_ids)
            st.selectbox(
                "Выбранный тест",
                options=_suite_select_options,
                index=_suite_select_options.index(_cur_sel) if (_cur_sel in _suite_select_options) else 0,
                format_func=lambda _id: _label_for_id(str(_id)),
                key="ui_suite_selected_id",
                help="Выбор теста для карточки редактирования справа.",
            )

        _list_df = _df_view[["включен", "стадия", "имя", "тип"]].copy()
        _list_df = _list_df.rename(columns={"включен": "Вкл.", "стадия": "Стадия", "имя": "Тест", "тип": "Тип"})
        st.dataframe(
            _list_df,
            hide_index=True,
            width="stretch",
            height=320,
        )

with right:
    if not _row_ids:
        st.info("Добавь тест-шаблон или ослабь фильтры — тогда появится карточка редактирования.")
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
            st.error("Выбранный тест не найден в наборе (возможно, изменились фильтры/набор).")
            st.stop()
        rec = df_suite_edit.loc[idx].to_dict()
        sid = str(rec.get("id") or sel_id or idx)
        title = str(rec.get("имя", "Тест"))
        st.markdown(f"### {title}")

        # Вспомогательный парсер чисел
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

        # Карточка редактора без st.form: черновик живёт в session_state и не теряется при обычных rerun.
        # CSV_UPLOADERS_OUTSIDE_FORM
        uploaded_road_csv = None
        uploaded_axay_csv = None
        with st.expander("CSV профиля дороги / маневра (опционально)", expanded=True):
            st.caption("Если нужно: загрузите CSV, файл будет сохранён в workspace/uploads и путь подставится в поля ниже.")
            up_road = st.file_uploader(
                "Профиль дороги (CSV)",
                type=["csv"],
                key=f"suite_road_csv_upload_{sid}",
                help="Используется в типах road_profile_csv / (опционально) в других тестах.",
            )
            if up_road is not None:
                uploaded_road_csv = _save_upload(up_road, prefix="road")
                if uploaded_road_csv:
                    st.success(f"Профиль дороги сохранён: {uploaded_road_csv}")
            up_axay = st.file_uploader(
                "Манёвр (CSV ax/ay)",
                type=["csv"],
                key=f"suite_axay_csv_upload_{sid}",
                help="Используется в типах maneuver_csv / (опционально) в других тестах.",
            )
            if up_axay is not None:
                uploaded_axay_csv = _save_upload(up_axay, prefix="axay")
                if uploaded_axay_csv:
                    st.success(f"Манёвр сохранён: {uploaded_axay_csv}")

        _seed_suite_editor_state(sid, rec)
        st.caption("Черновик карточки живёт в UI-state: обычный rerun не должен откатывать несохранённые поля.")

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

        enabled = st.checkbox("Включён", key=_enabled_key)
        name = st.text_input("Имя", key=_name_key)

        try:
            _stage_default = max(0, int(st.session_state.get(_stage_key, infer_suite_stage(rec)) or 0))
        except Exception:
            _stage_default = 0
            st.session_state[_stage_key] = 0
        stage = st.number_input(
            "Стадия",
            value=int(_stage_default),
            min_value=0,
            step=1,
            key=_stage_key,
            help="Момент входа теста в staged optimization. Семантика накопительная: stage 0 идёт только с S0; stage 1 впервые включается с S1 и затем идёт и в S2; stage 2 — только в финальной стадии. Нумерация 0-based: первая стадия = 0.",
        )

        _type_default = str(st.session_state.get(_type_key, rec.get("тип", "worldroad")) or "worldroad")
        if _type_default not in ALLOWED_TEST_TYPES:
            _type_default = "worldroad"
            st.session_state[_type_key] = _type_default
        ttype = st.selectbox(
            "Тип",
            options=ALLOWED_TEST_TYPES,
            index=max(0, ALLOWED_TEST_TYPES.index(_type_default)),
            key=_type_key,
        )

        dt = st.number_input("dt, с", min_value=1e-5, step=0.001, format="%.6g", key=_dt_key)
        t_end = st.number_input("t_end, с", min_value=0.01, step=0.1, format="%.6g", key=_t_end_key)

        st.markdown("#### Дорога и режим движения")

        road_csv = str(st.session_state.get(_road_csv_key, "") or "")
        axay_csv = str(st.session_state.get(_axay_csv_key, "") or "")
        road_len_m = float(_sf(st.session_state.get(_road_len_key, rec.get("road_len_m", 200.0)), 200.0))
        vx0_mps = float(_sf(st.session_state.get(_vx0_key, rec.get("vx0_м_с", 20.0)), 20.0))
        auto_t_end_from_len = bool(st.session_state.get(_auto_t_end_key, rec.get("auto_t_end_from_len", False)))
        t_end_effective = float(t_end)

        if ttype == "worldroad":
            c1, c2 = st.columns([1, 1], gap="small")
            with c1:
                vx0_mps = st.number_input("Скорость (vx0_м_с), м/с", min_value=0.0, step=0.5, key=_vx0_key)
            with c2:
                road_len_m = st.number_input("Длина участка, м", min_value=1.0, step=10.0, key=_road_len_key)

            auto_t_end_from_len = st.checkbox(
                "Авто: t_end = (длина / скорость)",
                key=_auto_t_end_key,
                help="Если включено, t_end будет вычисляться как road_len_m / max(vx0_м_с, eps).",
            )

            eps_v = 1e-6
            if auto_t_end_from_len:
                t_end_auto = float(road_len_m) / max(float(vx0_mps), eps_v)
                t_end_effective = float(t_end_auto)
                st.info(
                    f"t_end будет вычислен автоматически: **{t_end_effective:.6g} с** "
                    f"(вместо введённого {float(t_end):.6g} с)"
                )
            else:
                t_end_effective = float(t_end)
                len_eff = float(vx0_mps) * float(t_end_effective)
                st.caption(
                    f"Факт. длина проезда = speed * t_end = {len_eff:.6g} м. "
                    f"(road_len_m используется только в авто-режиме)"
                )
                try:
                    if float(road_len_m) > 1e-9:
                        rel = abs(len_eff - float(road_len_m)) / max(float(road_len_m), 1e-9)
                        if rel > 0.05:
                            st.warning(
                                f"road_len_m = {float(road_len_m):.6g} м **не влияет**, потому что авто-режим выключен. "
                                f"Сейчас по speed/t_end получается {len_eff:.6g} м."
                            )
                except Exception:
                    pass

            st.caption("Профиль дороги (WorldRoad)")
            surf_map = {
                "flat": "Ровная (flat)",
                "sine_x": "Синус вдоль (sine_x)",
                "sine_y": "Синус поперёк (sine_y)",
                "bump": "Бугор (bump)",
                "ridge_x": "Порог (ridge_x)",
                "ridge_cosine_bump": "Косинусный бугор (ridge_cosine_bump)",
            }
            surf_type_default = str(st.session_state.get(_surface_type_key, "flat") or "flat")
            if surf_type_default not in surf_map:
                surf_type_default = "flat"
                st.session_state[_surface_type_key] = surf_type_default
            surf_type = st.selectbox(
                "Тип поверхности",
                options=list(surf_map.keys()),
                index=list(surf_map.keys()).index(surf_type_default),
                format_func=lambda _k: surf_map.get(str(_k), str(_k)),
                key=_surface_type_key,
            )

            if surf_type in {"sine_x", "sine_y"}:
                A = st.number_input("Амплитуда A (полуразмах), м", min_value=0.0, step=0.005, format="%.6g", key=_surface_sine_a_key)
                st.caption(f"Синус задаётся как z = A·sin(...). Это значит: профиль идёт от {-float(A):.6g} до +{float(A):.6g} м, а полный размах p-p = 2A = {2.0*float(A):.6g} м.")
                wl = st.number_input("Длина волны, м", min_value=0.01, step=0.1, format="%.6g", key=_surface_sine_wl_key)
                spec_obj = {"type": surf_type, "A": float(A), "wavelength": float(wl)}
            elif surf_type in {"bump", "ridge_x"}:
                h = st.number_input("Высота h, м", min_value=0.0, step=0.005, format="%.6g", key=_surface_hw_h_key)
                w = st.number_input("Ширина w, м", min_value=0.01, step=0.05, format="%.6g", key=_surface_hw_w_key)
                spec_obj = {"type": surf_type, "h": float(h), "w": float(w)}
            elif surf_type == "ridge_cosine_bump":
                h = st.number_input("Высота h, м", min_value=0.0, step=0.005, format="%.6g", key=_surface_cos_h_key)
                w = st.number_input("Ширина w, м", min_value=0.01, step=0.05, format="%.6g", key=_surface_cos_w_key)
                k = st.number_input("Форма k", min_value=0.1, step=0.1, format="%.6g", key=_surface_cos_k_key)
                spec_obj = {"type": surf_type, "h": float(h), "w": float(w), "k": float(k)}
            else:
                spec_obj = {"type": "flat"}

            road_surface = "flat" if spec_obj.get("type") == "flat" else json.dumps(spec_obj, ensure_ascii=False)

        else:
            road_surface = str(rec.get("road_surface", "flat") or "flat")
            auto_t_end_from_len = False
            t_end_effective = float(t_end)
            road_csv = st.text_input("Путь к road_csv", key=_road_csv_key)
            axay_csv = st.text_input("Путь к axay_csv", key=_axay_csv_key)

        st.markdown("#### Манёвр (если применимо)")
        ax = st.number_input("ax, м/с²", step=0.1, format="%.6g", key=_ax_key)
        ay = st.number_input("ay, м/с²", step=0.1, format="%.6g", key=_ay_key)

        st.markdown("#### Цели/ограничения (penalty targets)")
        st.caption(
            "Штраф оптимизации учитывает только target_*, включённые ниже. "
            "Если ничего не включено — penalty=0, оптимизация может стать бессмысленной."
        )

        penalty_targets_cols: Dict[str, Any] = {}
        try:
            from pneumo_solver_ui.opt_worker_v3_margins_energy import PENALTY_TARGET_SPECS
        except Exception:
            PENALTY_TARGET_SPECS = []

        with st.expander("Список penalty targets (target_*)", expanded=True):
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
                        f"Значение: {_col}",
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

        with st.expander("Переопределения параметров (сценарий)", expanded=True):
            params_override = st.text_area(
                "JSON (необязательно)",
                height=120,
                key=_params_override_key,
                help="Можно задать JSON со значениями параметров, которые будут применены только в этом тесте.",
            )

        submitted = st.button("Применить изменения", key=f"ui_suite_apply_btn_{sid}", width="stretch")

        if submitted:
            df_suite_edit.at[idx, "включен"] = bool(enabled)
            df_suite_edit.at[idx, "стадия"] = int(stage)
            df_suite_edit.at[idx, "имя"] = str(name)
            df_suite_edit.at[idx, "тип"] = str(ttype)
            df_suite_edit.at[idx, "dt"] = float(dt)
            df_suite_edit.at[idx, "t_end"] = float(t_end_effective)
            df_suite_edit.at[idx, "auto_t_end_from_len"] = bool(auto_t_end_from_len)
            df_suite_edit.at[idx, "road_csv"] = str(road_csv)
            df_suite_edit.at[idx, "axay_csv"] = str(axay_csv)
            df_suite_edit.at[idx, "road_surface"] = str(road_surface)
            df_suite_edit.at[idx, "road_len_m"] = float(road_len_m)
            df_suite_edit.at[idx, "vx0_м_с"] = float(vx0_mps)
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
            _suite_set_flash("success", "Тест обновлён.")
            st.rerun()

# (на всякий случай)
st.session_state["df_suite_edit"] = df_suite_edit


# валидируем и собираем suite_override (list[dict])
suite_errors = []
SUITE_REQUIRED = ["имя", "тип", "dt", "t_end"]

suite_override: List[Dict[str, Any]] = []
for i, row in df_suite_edit.iterrows():
    rec = {k: (None if (isinstance(v, float) and (pd.isna(v))) else v) for k, v in row.to_dict().items()}
    # пропускаем полностью пустые строки
    if all((rec.get(k) in [None, "", False] for k in rec.keys())):
        continue

    enabled = bool(rec.get("включен", True))
    name = str(rec.get("имя", "")).strip()
    typ = str(rec.get("тип", "")).strip()

    if enabled:
        if not name:
            suite_errors.append(f"Строка {i+1}: пустое имя теста")
        if typ not in ALLOWED_TEST_TYPES:
            suite_errors.append(f"Тест '{name or i+1}': неизвестный тип '{typ}'")
        try:
            dt_i = float(rec.get("dt"))
            if dt_i <= 0:
                suite_errors.append(f"Тест '{name}': dt должен быть > 0")
        except Exception:
            suite_errors.append(f"Тест '{name}': dt не задан")
        try:
            t_end_i = float(rec.get("t_end"))
            if t_end_i <= 0:
                suite_errors.append(f"Тест '{name}': t_end должен быть > 0")
        except Exception:
            suite_errors.append(f"Тест '{name}': t_end не задан")

        # физика: доля отрыва 0..1
        if rec.get("target_макс_доля_отрыва") is not None:
            try:
                frac = float(rec["target_макс_доля_отрыва"])
                if not (0.0 <= frac <= 1.0):
                    suite_errors.append(f"Тест '{name}': target_макс_доля_отрыва должна быть 0..1")
            except Exception:
                suite_errors.append(f"Тест '{name}': target_макс_доля_отрыва некорректна")

        # JSON sanity: road_surface / params_override (если похоже на JSON — проверяем)
        for _fld in ("road_surface", "params_override"):
            _v = rec.get(_fld, None)
            if isinstance(_v, str):
                _s = _v.strip()
                if _s and ((_s.startswith('{') and _s.endswith('}')) or (_s.startswith('[') and _s.endswith(']'))):
                    try:
                        json.loads(_s)
                    except Exception as _e_json:
                        suite_errors.append(f"Тест '{name}': поле '{_fld}' содержит некорректный JSON: {_e_json}")

        # sidecar sanity: CSV-файлы должны существовать (чтобы не было «тихих» нулей)
        if typ in ("road_profile_csv", "maneuver_csv", "csv", "worldroad"):
            for _csv_fld in ("road_csv", "axay_csv", "scenario_json"):
                _p = rec.get(_csv_fld, None)
                if not _p:
                    # road_csv обязателен для road_profile_csv
                    if (_csv_fld == "road_csv") and (typ in ("road_profile_csv", "worldroad")):
                        suite_errors.append(f"Тест '{name}': не задан road_csv")
                    continue
                try:
                    _pp = Path(str(_p))
                    if not _pp.is_absolute():
                        _pp = (ROOT_DIR / _pp).resolve()
                    if not _pp.exists():
                        suite_errors.append(f"Тест '{name}': файл '{_csv_fld}' не найден: {str(_p)}")
                except Exception as _e_p:
                    suite_errors.append(f"Тест '{name}': не удалось проверить '{_csv_fld}': {_e_p}")

    suite_override.append(rec)

# Дополнительно: имена включенных тестов должны быть уникальны
try:
    _name_counts = {}
    for _r in suite_override:
        try:
            if not bool(_r.get('включен', True)):
                continue
            _nm = str(_r.get('имя', '')).strip()
            if not _nm:
                continue
            _name_counts[_nm] = _name_counts.get(_nm, 0) + 1
        except Exception:
            continue
    _dups = sorted([n for n, c in _name_counts.items() if c > 1])
    if _dups:
        suite_errors.append("Дубли имён тестов (включенных): " + ", ".join(_dups))
except Exception:
    pass

if suite_errors:
    st.error("В тест-наборе есть ошибки (исправьте перед запуском):\n- " + "\n- ".join(suite_errors))


# -------------------------------
# Одиночные тесты
# -------------------------------
with colB:
    st.subheader("Опорный прогон тестов")
    st.caption("Проверка адекватности модели на текущих параметрах.")

    tests_cfg = {"suite": suite_override}
    tests: List[Tuple[str, Dict[str, Any], float, float, Dict[str, float]]] = []
    if not suite_errors:
        try:
            tests = worker_mod.build_test_suite(tests_cfg)
        except Exception as e:
            st.error(f"Не удалось собрать тест‑набор: {e}")
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
                    st.markdown(f"**Release:** `{APP_RELEASE}`  \n**Model:** `{getattr(model_path, 'name', str(model_path))}`")
                    st.caption(_baseline_summary)
                with c2:
                    st.markdown(f"**base_hash:** `{_base_hash_preview}`  \n**suite_hash:** `{_suite_hash_preview}`")
                    st.caption(f"cache_dir: `{_cache_dir_preview.name}`")
                with c3:
                    st.markdown("**autoselfcheck:** ✅ OK" if _self_ok else "**autoselfcheck:** ❌ FAIL")
                    if not _self_ok:
                        st.caption("Оптимизация и экспорт будут заблокированы по умолчанию.")
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
                # детальные прогоны не грузим целиком — будут подхвачены по запросу
                log_event("baseline_loaded_cache", cache_dir=str(_cache_dir_preview))
                st.info(f"Опорный прогон загружен из кэша: {_cache_dir_preview.name}")
    except Exception:
        pass

    test_names = [x[0] for x in tests]
    pick = st.selectbox("Тест", options=["(все)"] + test_names, index=0)

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
                st.metric("Опорный прогон: тестов", _n_total)
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
                        "Показывать график худших тестов",
                        value=False,
                        help="Строит Plotly‑график по худшим тестам (может быть тяжело на больших наборах).",
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
                        help="Показывает таблицу pen_* по тестам (удобно для экспорта/проверок).",
                        key="gate_baseline_overview_table_pen",
                    )

                # Худшие тесты по суммарному штрафу (дешево)
                _bdf2 = _bdf.copy()
                if "penalty" not in _bdf2.columns:
                    _bdf2["penalty"] = 0.0
                _bdf2["penalty"] = pd.to_numeric(_bdf2["penalty"], errors="coerce").fillna(0.0)
                _bdf2 = _bdf2.sort_values("penalty", ascending=False)

                _worst = _bdf2.head(10)
                _pairs = [(str(r.get("test_id", "?")), float(r.get("penalty", 0.0))) for _, r in _worst.iterrows()]
                st.write("Худшие тесты по суммарному штрафу:", ", ".join([f"{tid} ({pen:.3g})" for tid, pen in _pairs]))

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

                # 1) График худших тестов
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
                                title="Худшие тесты (суммарный штраф)",
                                xaxis_title="Тест",
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
                                    labels=dict(x="Тест", y="Критерий", color="Штраф"),
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
    "Сначала запустите опорный прогон. Затем выберите один тест и получите полный лог (record_full=True): "
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
        st.info("В таблице опорного прогона нет доступных тестов (проверьте тест‑набор).")
    else:
        colG1, colG2 = st.columns([1.35, 0.65], gap="large")
        with colG1:
            test_pick = st.selectbox("Тест для детального прогона", options=avail, index=0, key="detail_test_pick")

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
                    "record_full (потоки/состояния)",
                    value=bool(st.session_state.get("detail_want_full", True)),
                    key="detail_want_full",
                )
                auto_detail_on_select = st.checkbox(
                    "Авто-расчёт при выборе теста",
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
                    help="Экспортирует Txx_osc.npz в папку osc_dir (см. Калибровка). Нужно для oneclick/autopilot.",
                )

                st.caption('Desktop Animator (follow)')
                st.checkbox(
                    'Авто-экспорт anim_latest (Desktop Animator)',
                    value=bool(st.session_state.get('auto_export_anim_latest', True)),
                    key='auto_export_anim_latest',
                    help=(
                        'После детального прогона сохраняет workspace/exports/anim_latest.npz и anim_latest.json (pointer). '
                        'Desktop Animator в follow-режиме подхватит автоматически.'
                    ),
                )
                st.checkbox(
                    'Авто-запуск Desktop Animator при экспорте',
                    value=bool(st.session_state.get('auto_launch_animator', False)),
                    key='auto_launch_animator',
                    help='Если среда позволяет запуск GUI: откроет Desktop Animator (follow) сразу после экспорта.',
                )
                st.caption(f'Папка exports: {WORKSPACE_EXPORTS_DIR}')

        # dt/t_end берём из suite для выбранного теста — это часть cache_key и параметров simulate()
        info_pick = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
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
            run_detail_all = st.button("Рассчитать полный лог ДЛЯ ВСЕХ тестов", key="run_detail_all", disabled=_detail_in_progress)
        with colDAll2:
            export_npz_all = st.button("Экспорт NPZ ДЛЯ ВСЕХ (из кэша)", key="export_npz_all", disabled=_detail_in_progress)

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
        # - полный лог для всех тестов
        # - экспорт NPZ для всех тестов
        if run_detail_all:
            if not want_full:
                st.warning("Для массового расчёта включи record_full (потоки/состояния) — иначе NPZ будет неполный.")
            else:
                with st.spinner("Считаю полный лог для всех тестов… (может быть долго)"):
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
                            st.error(f"Ошибка в тесте {tn}: {e}")
                        prog.progress(j / n_total)
                    prog.empty()
                log_event("detail_all_done", n_tests=len(avail), want_full=bool(want_full), max_points=int(max_points))

        if export_npz_all:
            if not want_full:
                st.warning("Экспорт NPZ имеет смысл только при record_full=True (иначе нет p/q/open).")
            else:
                with st.spinner("Экспортирую NPZ для всех тестов, которые уже посчитаны…"):
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
                    st.info("После свежего baseline выполняется принудительный пересчёт детального лога: старый detail cache для этого теста игнорируется.")
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
                        st.info("Детальный лог для текущего теста загружен из кэша. Для принудительного пересчёта нажмите 'Рассчитать полный лог и показать'.")
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
                        "Подавлен повторный автозапуск детального прогона для текущего теста: обнаружен rerun-loop. "
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
                            raise RuntimeError(f"Не найден тест '{test_pick}' в suite")
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
                            st.warning(f'Авто-экспорт anim_latest не удался: {_e_animexp}')
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
                    st.caption('Подвеска: кинематика/перемещения + проверка DW2D по фактическому диапазону хода из симуляции.')

                    cS1, cS2, cS3 = st.columns(3)
                    with cS1:
                        if mech_ok is True:
                            st.success('Кинематика/перемещения: OK')
                        elif mech_ok is False:
                            st.error('Кинематика/перемещения: FAIL')
                        else:
                            st.info('Кинематика/перемещения: —')

                    with cS2:
                        if isinstance(dw_item, dict):
                            _dw_ok = bool(dw_item.get('ok', True))
                            _dw_sev = str(dw_item.get('severity', 'info') or 'info')
                            _label = 'DW2D диапазон: OK' if _dw_ok else 'DW2D диапазон: ПРОБЛЕМА'
                            if _dw_ok:
                                st.success(_label)
                            else:
                                if _dw_sev == 'error':
                                    st.error(_label)
                                else:
                                    st.warning(_label)
                        else:
                            st.info('DW2D диапазон: —')

                    with cS3:
                        _stab_on = bool(base_override.get('стабилизатор_вкл', False))
                        st.write('Стабилизатор:', 'ВКЛ' if _stab_on else 'выкл (по умолчанию)')

                    # Нулевая поза (t=0): дорога=0, штоки ~ середина хода
                    if isinstance(pose_item, dict):
                        _pz_ok = bool(pose_item.get('ok', True))
                        _pz_sev = str(pose_item.get('severity', 'info') or 'info')
                        _pz_label = 'Нулевая поза: OK' if _pz_ok else 'Нулевая поза: ПРОБЛЕМА'
                        if _pz_ok:
                            st.success(_pz_label)
                        else:
                            if _pz_sev == 'error':
                                st.error(_pz_label)
                            else:
                                st.warning(_pz_label)
                    else:
                        st.info('Нулевая поза: —')

                    with st.expander('Детали самопроверок', expanded=False):
                        if mech_msg:
                            st.write('Механика:', mech_msg)
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
                            st.markdown('**Нулевая поза (t=0)**')
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
                            st.markdown('**Полный autoself_post_json**')
                            st.json(rep_post)

                    st.caption('Геометрия DW2D настраивается на странице: «Геометрия подвески (DW2D)» (в меню слева).')


                # -----------------------------------
                # Desktop Animator integration (follow-mode)
                # -----------------------------------
                with st.expander('🖥 Desktop Animator (внешнее окно, follow anim_latest)', expanded=False):
                    npz_path, ptr_path = local_anim_latest_export_paths_global(
                        WORKSPACE_EXPORTS_DIR,
                        ensure_exists=False,
                    )
                    st.caption('Animator читает последнюю выгрузку из workspace/exports (anim_latest.*).')
                    st.code(str(ptr_path))
                    cols_da = st.columns([1, 1, 1])
                    with cols_da[0]:
                        if st.button('Экспортировать anim_latest сейчас', key=f'anim_latest_export_now_{cache_key}'):
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
                                st.error(f'Экспорт anim_latest не удался: {e}')
                                log_event('anim_latest_export_error_manual', err=str(e), test=str(test_pick))
                    with cols_da[1]:
                        no_gl = st.checkbox('no-gl (compat)', value=False, key=f'anim_latest_no_gl_{cache_key}')
                        if st.button('Запустить Animator (follow)', key=f'anim_latest_launch_{cache_key}'):
                            ok = launch_desktop_animator_follow(ptr_path, no_gl=bool(no_gl))
                            if ok:
                                st.success('Animator запущен (если система позволяет GUI).')
                            else:
                                st.warning('Не удалось запустить Animator (см. логи).')
                    with cols_da[2]:
                        st.caption(f'NPZ: {npz_path}')
                        st.caption('Подсказка: включите **Авто-экспорт anim_latest** в настройках детального прогона.')

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
                dataset_id_ui = f"{cache_key}__{get_ui_nonce()}"

                # reset playhead when dataset changes
                if st.session_state.get("playhead_active_dataset") != cache_key:
                    st.session_state["playhead_active_dataset"] = cache_key
                    st.session_state["playhead_idx"] = 0
                    if time_s:
                        st.session_state["playhead_t"] = float(time_s[0])
                    st.session_state["playhead_cmd"] = {"ts": int(time.time() * 1000), "set_idx": 0, "set_playing": False, "set_loop": False, "set_speed": 0.25}
                    log_event("playhead_reset", dataset_id=str(dataset_id_ui))

                # jump from plot clicks (x=time)
                req_x = st.session_state.pop("playhead_request_x", None)
                if req_x is not None and time_s:
                    try:
                        req_x_f = float(req_x)
                        arr = np.asarray(time_s, dtype=float)
                        j = int(np.argmin(np.abs(arr - req_x_f)))
                        st.session_state["playhead_idx"] = j
                        st.session_state["playhead_t"] = float(time_s[j])
                        st.session_state["playhead_cmd"] = {"ts": int(time.time() * 1000), "set_idx": j, "set_playing": False}
                    except Exception:
                        pass

                # clamp playhead to data
                playhead_x = None
                if time_s:
                    try:
                        ph_idx = int(st.session_state.get("playhead_idx", 0))
                    except Exception:
                        ph_idx = 0
                    ph_idx = max(0, min(ph_idx, len(time_s) - 1))
                    st.session_state["playhead_idx"] = ph_idx
                    playhead_x = float(time_s[ph_idx])
                    st.session_state["playhead_t"] = playhead_x
                st.markdown("### ⏱ Общий таймлайн")

                # local alias (avoid NameError even if JS components are disabled)
                try:
                    playhead_idx = int(st.session_state.get('playhead_idx', 0) or 0)
                except Exception:
                    playhead_idx = 0

                # --- События/алёрты (метки на таймлайне) ---
                cols_evt = st.columns([1, 1, 1, 1])
                # миграция: старые ключи (атм) -> новые (бар)
                if "events_vacuum_min_bar" not in st.session_state and "events_vacuum_min_atm" in st.session_state:
                    try:
                        st.session_state["events_vacuum_min_bar"] = float(st.session_state["events_vacuum_min_atm"]) * (ATM_PA / BAR_PA)
                    except Exception:
                        pass
                if "events_pmax_margin_bar" not in st.session_state and "events_pmax_margin_atm" in st.session_state:
                    try:
                        st.session_state["events_pmax_margin_bar"] = float(st.session_state["events_pmax_margin_atm"]) * (ATM_PA / BAR_PA)
                    except Exception:
                        pass
                with cols_evt[0]:
                    st.checkbox("События/алёрты", value=True, key="events_show")
                with cols_evt[1]:
                    st.slider("Вакуум мин, бар(изб)", -1.0, 0.0, -0.2, 0.05, key="events_vacuum_min_bar")
                with cols_evt[2]:
                    st.slider("Запас к Pmax, бар", 0.0, 1.0, 0.10, 0.05, key="events_pmax_margin_bar")
                with cols_evt[3]:
                    st.slider("Дребезг: toggles/окно", 3, 20, 6, 1, key="events_chatter_toggles")

                # --- События на графиках (вертикальные линии) ---
                cols_evt2 = st.columns([1, 2, 1, 1])
                with cols_evt2[0]:
                    st.checkbox("Метки событий на графиках", value=True, key="events_on_graphs")
                with cols_evt2[1]:
                    st.multiselect(
                        "Уровни на графиках",
                        options=["error", "warn", "info"],
                        default=["error", "warn"],
                        key="events_graph_sev",
                    )
                with cols_evt2[2]:
                    st.checkbox("Подписи error", value=False, key="events_graph_labels")
                with cols_evt2[3]:
                    st.slider("Макс. событий на графиках", 0, 300, 120, 10, key="events_graph_max")

                events_list = []
                if st.session_state.get("events_show", True):
                    try:
                        params_for_events = dict(base_override)
                        params_for_events["_P_ATM"] = float(P_ATM)
                        events_list = compute_events(
                            df_main=df_main,
                            df_p=df_p,
                            df_open=df_open,
                            params_abs=params_for_events,
                            test=test,
                            vacuum_min_gauge_bar=float(st.session_state.get("events_vacuum_min_bar", -0.2)),
                            pmax_margin_bar=float(st.session_state.get("events_pmax_margin_bar", 0.10)),
                            chatter_window_s=0.25,
                            chatter_toggle_count=int(st.session_state.get("events_chatter_toggles", 6)),
                            max_events=240,
                        )
                    except Exception:
                        events_list = []

                # Prepare event list for graph overlays (filtered by severity and max)
                events_for_graphs: List[dict] = []
                events_graph_labels = bool(st.session_state.get("events_graph_labels", False))
                try:
                    events_graph_max = int(st.session_state.get("events_graph_max", 120))
                except Exception:
                    events_graph_max = 120

                if events_list and st.session_state.get("events_on_graphs", True) and events_graph_max > 0:
                    sev_allow = set(
                        str(s).lower()
                        for s in (st.session_state.get("events_graph_sev", ["error", "warn"]) or [])
                    )
                    events_for_graphs = [
                        ev for ev in events_list
                        if str(ev.get("severity", "")).lower() in sev_allow
                    ]
                    events_for_graphs.sort(key=lambda e: int(e.get("idx", 0)))
                    # Let plot_lines thin out further, but also cap here (helps memory)
                    if len(events_for_graphs) > max(10, events_graph_max * 4):
                        step = int(math.ceil(len(events_for_graphs) / float(events_graph_max * 4)))
                        if step > 1:
                            events_for_graphs = events_for_graphs[::step]

                # --- Playhead server sync (important for perceived responsiveness) ---
                # By default we do NOT send periodic updates to Python while playing.
                # This avoids the "infinite recalculation" feel (Streamlit reruns).
                # You can still scrub/jump time and get a sync snapshot (forced event).
                cols_phsync = st.columns([1.35, 0.95, 0.95, 0.95], gap="medium")
                with cols_phsync[0]:
                    ph_server_sync = st.checkbox(
                        "Синхронизация графиков во время Play (СЕРВЕР, тяжело)",
                        value=False,
                        key="playhead_server_sync",
                    )
                with cols_phsync[1]:
                    if ph_server_sync:
                        ph_send_hz = st.slider(
                            "Hz (сервер)",
                            1,
                            10,
                            2,
                            1,
                            key="playhead_send_hz",
                            help=(
                                "Каждые N раз/сек будет происходить полный rerun Streamlit-скрипта, "
                                "чтобы двигались маркеры на графиках. Это может подвисать при N>2."
                            ),
                        )
                    else:
                        ph_send_hz = 0
                with cols_phsync[2]:
                    ph_storage_hz = st.slider(
                        "FPS (браузер)",
                        5,
                        60,
                        30,
                        1,
                        key="playhead_storage_hz",
                        help=(
                            "Ограничивает частоту обновления общего playhead через localStorage. "
                            "Влияет на плавность 2D/3D анимации, но не вызывает rerun на сервере."
                        ),
                    )
                with cols_phsync[3]:
                    st.caption(
                        "Рекомендация: **Hz(сервер)=0** для плавной анимации. "
                        "Если нужны маркеры на графиках — 1–2 Hz."
                    )

                if ph_server_sync and int(ph_send_hz) >= 4:
                    st.warning(
                        "Hz(сервер) ≥ 4 часто приводит к зависанию: Streamlit не успевает перерабатывать rerun. "
                        "Для плавности увеличивайте FPS(браузер), а не Hz(сервер)."
                    )

                ph_comp = get_playhead_ctrl_component()

                if ph_comp is not None and time_s:
                    ph_comp(
                        title='Playhead',
                        time=time_s,
                        dataset_id=str(dataset_id_ui),
                        storage_key='pneumo_play_state',
                        send_hz=int(ph_send_hz),
                        storage_hz=int(ph_storage_hz),
                        height=88,
                        cmd=st.session_state.get('playhead_cmd'),
                        events=[{'t': float(ev.get('t', ev.get('t_s', 0.0))), 'label': str(ev.get('label', ''))} for ev in (events_list or [])],
                        events_max=40,
                        hint='Воспроизведение и точный переход по времени. Loop по умолчанию выключен (можно включить в контроле).',
                        restore_state=False,
                        key='playhead_event',
                        default=None,
                    )
                elif not time_s:
                    st.info("Нет временного массива для таймлайна.")
                else:
                    st.info("Компонент playhead_ctrl не найден (components/playhead_ctrl).")
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

                picked_ev = st.session_state.get("playhead_picked_event")
                if isinstance(picked_ev, dict):
                    st.caption(f"Последний клик по событию: {picked_ev.get('label','')}" )


                if st.session_state.get("events_show", True) and events_list:
                    with st.expander("События/алёрты", expanded=False):
                        st.caption(f"Найдено событий: {len(events_list)}")
                        df_events_view = pd.DataFrame([
                            {
                                "t, s": float(e.get("t", 0.0)),
                                "severity": e.get("severity"),
                                "kind": e.get("kind"),
                                "name": e.get("name"),
                                "label": e.get("label"),
                                "idx": int(e.get("idx", 0)),
                            }
                            for e in events_list
                        ])
                        safe_dataframe(df_events_view, height=240)

                        opt = list(range(len(events_list)))

                        def _fmt(i: int):
                            e = events_list[i]
                            return f't={float(e.get("t",0.0)):.3f}s | {e.get("severity","")} | {e.get("label","")}'

                        sel_i = st.selectbox("Перейти к событию", options=opt, format_func=_fmt, key="events_jump_sel")
                        if st.button("Перейти (jump playhead)", key="events_jump_btn"):
                            try:
                                e = events_list[int(sel_i)]
                                j = int(e.get("idx", 0))
                                st.session_state["playhead_cmd"] = {"ts": int(time.time()*1000), "set_idx": j, "set_playing": False}
                                st.session_state["playhead_idx"] = j
                                st.session_state["playhead_t"] = float(e.get("t", 0.0))
                            except Exception:
                                pass


                # Настройки синхронизации playhead → графики
                cols_ph = st.columns(2)
                with cols_ph[0]:
                    st.checkbox("Маркеры на графиках (playhead)", value=True, key="playhead_show_markers")
                with cols_ph[1]:
                    st.checkbox("Таблица значений (playhead)", value=True, key="playhead_show_values")

                if st.session_state.get("playhead_show_values", True) and playhead_x is not None:
                    with st.expander("Текущие значения (playhead)", expanded=False):
                        st.caption(f"t = {float(playhead_x):.3f} s")
                        rows = []

                        # --- df_main (углы/давления/штоки) ---
                        if df_main is not None and "время_с" in df_main.columns and len(df_main) > 0:
                            try:
                                arr = df_main["время_с"].to_numpy(dtype=float)
                                idx0 = int(np.argmin(np.abs(arr - float(playhead_x))))
                            except Exception:
                                idx0 = 0
                            idx0 = max(0, min(idx0, len(df_main) - 1))

                            if "крен_phi_рад" in df_main.columns:
                                rows.append({"показатель": "крен φ", "значение": float(df_main["крен_phi_рад"].iloc[idx0] * 180.0 / math.pi), "ед": "град"})
                            if "тангаж_theta_рад" in df_main.columns:
                                rows.append({"показатель": "тангаж θ", "значение": float(df_main["тангаж_theta_рад"].iloc[idx0] * 180.0 / math.pi), "ед": "град"})

                            for col, label in [
                                ("давление_ресивер1_Па", "P ресивер1"),
                                ("давление_ресивер2_Па", "P ресивер2"),
                                ("давление_ресивер3_Па", "P ресивер3"),
                                ("давление_аккумулятор_Па", "P аккумулятор"),
                            ]:
                                if col in df_main.columns:
                                    rows.append({"показатель": label, "значение": float(pa_abs_to_bar_g(df_main[col].iloc[idx0])), "ед": "бар (изб.)"})

                            sel_corners = st.session_state.get("mech_plot_corners")
                            if not isinstance(sel_corners, list) or not sel_corners:
                                sel_corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]

                            for cc in sel_corners:
                                col = f"положение_штока_{cc}_м"
                                if col in df_main.columns:
                                    rows.append({"показатель": f"шток {cc}", "значение": float(df_main[col].iloc[idx0]) * 1000.0, "ед": "мм"})

                        # --- df_p (узлы давления) ---
                        if df_p is not None and "время_с" in df_p.columns and len(df_p) > 0:
                            nodes = st.session_state.get("node_pressure_plot")
                            if not isinstance(nodes, list) or not nodes:
                                nodes = st.session_state.get("anim_nodes_svg")
                            if not isinstance(nodes, list):
                                nodes = []
                            if not nodes:
                                nodes = [n for n in ["Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор"] if n in df_p.columns]

                            if nodes:
                                try:
                                    arr = df_p["время_с"].to_numpy(dtype=float)
                                    idxp = int(np.argmin(np.abs(arr - float(playhead_x))))
                                except Exception:
                                    idxp = 0
                                idxp = max(0, min(idxp, len(df_p) - 1))

                                for n in nodes[:8]:
                                    if n in df_p.columns:
                                        rows.append({"показатель": f"P узел {n}", "значение": float(pa_abs_to_bar_g(df_p[n].iloc[idxp])), "ед": "бар (изб.)"})

                        # --- df_mdot (потоки по веткам) ---
                        if df_mdot is not None and "время_с" in df_mdot.columns and len(df_mdot) > 0:
                            edges = st.session_state.get("flow_graph_edges")
                            if not isinstance(edges, list) or not edges:
                                edges = st.session_state.get("anim_edges_svg")
                            if not isinstance(edges, list):
                                edges = []
                            if not edges:
                                edges = [c for c in df_mdot.columns if c != "время_с"][:4]

                            if edges:
                                # unit conversion (same as tabB)
                                try:
                                    rho_N = float(P_ATM) / (float(getattr(model_mod, 'R_AIR', 287.0)) * float(getattr(model_mod, 'T_AIR', 293.15)))
                                    scale = 1000.0 * 60.0 / rho_N
                                    unit = "Нл/мин"
                                except Exception:
                                    scale = 1.0
                                    unit = "кг/с"

                                try:
                                    arr = df_mdot["время_с"].to_numpy(dtype=float)
                                    idxm = int(np.argmin(np.abs(arr - float(playhead_x))))
                                except Exception:
                                    idxm = 0
                                idxm = max(0, min(idxm, len(df_mdot) - 1))

                                for e in edges[:8]:
                                    if e in df_mdot.columns:
                                        rows.append({"показатель": f"Q {e}", "значение": float(df_mdot[e].iloc[idxm]) * float(scale), "ед": unit})

                        if rows:
                            dfv = pd.DataFrame(rows)
                            safe_dataframe(dfv, height=min(360, 34 * (len(dfv) + 1) + 40))
                        else:
                            st.info("Нет данных для отображения на playhead.")
                # Важно: st.tabs не "ленивый" — код внутри всех табов исполняется при каждом rerun.
                # При анимации (auto-refresh) это выглядит как "бесконечный расчёт".
                # Поэтому используем явный селектор и рендерим только выбранную ветку.
                view_res = st.radio(
                    "Раздел результатов",
                    options=["Графики", "Потоки", "Энерго-аудит", "Анимация"],
                    horizontal=True,
                    key="baseline_view_res",
                )
                # Auto-pause playhead on view switches to avoid accidental background load
                _prev_view_key = f'__prev_view_res__{cur_hash}::{test_pick}'
                _prev_view = st.session_state.get(_prev_view_key)
                if _prev_view != view_res:
                    st.session_state[_prev_view_key] = view_res
                    log_event("view_switch", view=view_res, test=test_pick)
                    # Pause any running frontend playhead when switching views (esp. entering Animation)
                    st.session_state['playhead_cmd'] = {
                        'ts': int(time.time() * 1000),
                        'set_playing': False,
                    }


                if view_res == "Графики":
                    st.subheader("Графики по времени")
                    tcol = "время_с"

                    # крен/тангаж (град)
                    if df_main is not None:
                        plot_lines(
                            df_main,
                            tcol,
                            ["крен_phi_рад", "тангаж_theta_рад"],
                            title="Крен/тангаж",
                            yaxis_title="град",
                            transform_y=lambda a: a * 180.0 / math.pi,
                            playhead_x=playhead_x,
                            events=events_for_graphs,
                            events_max=events_graph_max,
                            events_show_labels=events_graph_labels,

                        )

                        # давления (быстро): из df_main
                        press_cols = [c for c in [
                            "давление_ресивер1_Па",
                            "давление_ресивер2_Па",
                            "давление_ресивер3_Па",
                            "давление_аккумулятор_Па",
                        ] if c in df_main.columns]
                        if press_cols:
                            plot_lines(
                                df_main,
                                tcol,
                                press_cols,
                                title="Давление (бар изб.)",
                                yaxis_title="бар (изб.)",
                                transform_y=lambda a: (a - P_ATM) / BAR_PA,
                                playhead_x=playhead_x,
                                events=events_for_graphs,
                                events_max=events_graph_max,
                                events_show_labels=events_graph_labels,

                            )

                        # выбор углов для механических графиков (синхр. с мех-анимацией)
                        corners_mech = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
                        default_corners_mech = st.session_state.get("mech_plot_corners")
                        if not default_corners_mech:
                            default_corners_mech = corners_mech
                        st.markdown("**Углы (механика) — синхронизация с анимацией**")
                        col_pick, col_hint = st.columns([1, 4], gap="small")
                        with col_pick:
                            pick_corners_mech = st.multiselect(
                                "Углы",
                                options=corners_mech,
                                default=default_corners_mech,
                                key="mech_plot_corners",
                                label_visibility="collapsed",
                            )
                        with col_hint:
                            st.caption("Клик по колесу/оси в вкладке «Анимация → Механика» обновляет этот выбор.")
                        if not pick_corners_mech:
                            pick_corners_mech = corners_mech

                        # силы шин
                        f_cols = []
                        for cc in pick_corners_mech:
                            col = f"нормальная_сила_шины_{cc}_Н"
                            if col in df_main.columns:
                                f_cols.append(col)
                        if not f_cols:
                            f_cols = [c for c in df_main.columns if c.startswith("нормальная_сила_шины_")]
                        if f_cols:
                            plot_lines(df_main, tcol, f_cols, title="Нормальные силы шин", yaxis_title="Н", playhead_x=playhead_x, events=events_for_graphs, events_max=events_graph_max, events_show_labels=events_graph_labels)

                        # положение штоков
                        s_cols = []
                        for cc in pick_corners_mech:
                            col = f"положение_штока_{cc}_м"
                            if col in df_main.columns:
                                s_cols.append(col)
                        if s_cols:
                            plot_lines(df_main, tcol, s_cols, title="Положение штоков", yaxis_title="м", playhead_x=playhead_x, events=events_for_graphs, events_max=events_graph_max, events_show_labels=events_graph_labels)

                        # скорости штоков
                        v_cols = []
                        for cc in pick_corners_mech:
                            col = f"скорость_штока_{cc}_м_с"
                            if col in df_main.columns:
                                v_cols.append(col)
                        if not v_cols:
                            v_cols = [c for c in df_main.columns if c.startswith("скорость_штока_")]
                        if v_cols:
                            plot_lines(df_main, tcol, v_cols, title="Скорость штоков", yaxis_title="м/с", playhead_x=playhead_x, events=events_for_graphs, events_max=events_graph_max, events_show_labels=events_graph_labels)

                    # Дополнительно: давления узлов из df_p (record_full=True)
                    if df_p is not None:
                        with st.expander("Давление узлов (df_p)", expanded=False):
                            node_cols_p = [c for c in df_p.columns if c != "время_с"]
                            if not node_cols_p:
                                st.info("В df_p нет колонок узлов давления.")
                            else:
                                # если пользователь кликал по узлам на схеме — используем это как дефолт
                                default_nodes_plot = st.session_state.get("node_pressure_plot")
                                if not default_nodes_plot:
                                    default_nodes_plot = st.session_state.get("anim_nodes_svg")
                                if not default_nodes_plot:
                                    default_nodes_plot = [n for n in ["Ресивер1","Ресивер2","Ресивер3","Аккумулятор"] if n in node_cols_p]
                                if not default_nodes_plot:
                                    default_nodes_plot = node_cols_p[: min(6, len(node_cols_p))]

                                pick_nodes_plot = st.multiselect("Узлы (df_p)", options=node_cols_p, default=default_nodes_plot, key="node_pressure_plot")
                                plot_lines(
                                    df_p,
                                    "время_с",
                                    pick_nodes_plot,
                                    title="Давление узлов (df_p, бар изб.)",
                                    yaxis_title="бар (изб.)",
                                    transform_y=lambda a: (a - P_ATM) / BAR_PA,
                                    height=320,
                                    plot_key="plot_node_pressure",
                                    enable_select=True,
                                    playhead_x=playhead_x,
                                    events=events_for_graphs,
                                    events_max=events_graph_max,
                                    events_show_labels=events_graph_labels,

                                )
                                if _HAS_PLOTLY:
                                    st.caption("Клик по графику выбирает узел и подсвечивает его на SVG схеме (вкладка ‘Анимация’).")


                        # -----------------------------------
                        # Graph Studio (произвольные сигналы) — v7.32
                        # -----------------------------------
                        st.divider()
                        st.subheader("Конструктор графиков (Graph Studio)")
                        st.caption("Выбирайте любые сигналы из df_main/df_p/df_mdot/df_open, стройте осциллограф (stack) или overlay, кликом прыгайте по времени.")

                        with st.expander("Graph Studio: сигналы → график → экспорт", expanded=True):
                            # доступные источники
                            sources = {
                                "df_main": df_main,
                                "df_p (давления узлов)": df_p,
                                "df_mdot (потоки)": df_mdot,
                                "df_open (состояния клапанов)": df_open,
                            }
                            avail_sources = {k: v for k, v in sources.items() if v is not None and hasattr(v, "columns") and len(v)}
                            if not avail_sources:
                                st.info("Нет источников данных для Graph Studio (нужно record_full=True или df_main).")
                            else:
                                src_name = st.selectbox(
                                    "Источник данных",
                                    options=list(avail_sources.keys()),
                                    index=0,
                                    key=f"gs_src_{cache_key}",
                                )
                                df_src = avail_sources.get(src_name)

                                # определяем колонку времени
                                tcol_gs = "время_с" if (df_src is not None and "время_с" in df_src.columns) else None
                                if tcol_gs is None and df_src is not None and len(df_src.columns):
                                    tcol_gs = str(df_src.columns[0])

                                if df_src is None or tcol_gs is None or tcol_gs not in df_src.columns:
                                    st.warning("Не удалось определить колонку времени.")
                                else:
                                    all_cols = [c for c in df_src.columns if c != tcol_gs]
                                    # Скрываем каналы, полностью состоящие из NaN/None (обычно служебные или не рассчитанные)
                                    try:
                                        all_cols = [c for c in all_cols if df_src[c].notna().any()]
                                    except Exception:
                                        pass

                                    q = st.text_input(
                                        "Фильтр сигналов (подстрока или regex)",
                                        value="",
                                        key=f"gs_filter_{cache_key}",
                                    )
                                    if q:
                                        try:
                                            rx = re.compile(q, flags=re.IGNORECASE)
                                            cols_f = [c for c in all_cols if rx.search(str(c))]
                                        except Exception:
                                            ql = q.lower()
                                            cols_f = [c for c in all_cols if ql in str(c).lower()]
                                    else:
                                        cols_f = list(all_cols)

                                    # presets
                                    preset = st.selectbox(
                                        "Пресет",
                                        options=[
                                            "(нет)",
                                            "Механика: штоки (положение/скорость)",
                                            "Механика: колёса (z + дорога)",
                                            "Давления (Pa → бар изб.)",
                                            "Крен/тангаж (рад → град)",
                                        ],
                                        index=0,
                                        key=f"gs_preset_{cache_key}",
                                    )

                                    # current selection (dataset-specific)
                                    # IMPORTANT (Streamlit): чтобы не получать предупреждение
                                    # "... created with a default value but also had its value set via the Session State API",
                                    # мы инициализируем st.session_state[gs_key] ДО создания виджета и НЕ передаём default=...
                                    gs_key = f"gs_cols_{cache_key}::{src_name}"

                                    def _sanitize_cols(sel: list) -> list:
                                        return [c for c in sel if c in cols_f]

                                    if (gs_key not in st.session_state) or (not isinstance(st.session_state.get(gs_key), list)):
                                        st.session_state[gs_key] = cols_f[: min(8, len(cols_f))]
                                    else:
                                        st.session_state[gs_key] = _sanitize_cols(st.session_state.get(gs_key, []))

                                    # Apply preset button
                                    if st.button("Применить пресет", key=f"gs_apply_{cache_key}"):
                                        if preset.startswith("Механика: штоки"):
                                            pick = [c for c in all_cols if str(c).startswith("положение_штока_") or str(c).startswith("скорость_штока_")]
                                        elif preset.startswith("Механика: колёса"):
                                            pick = [c for c in all_cols if ("перемещение_колеса_" in str(c)) or str(c).startswith("дорога_")]
                                        elif preset.startswith("Давления"):
                                            pick = [c for c in all_cols if str(c).endswith("_Па") and ("давление" in str(c))]
                                        elif preset.startswith("Крен/тангаж"):
                                            pick = [c for c in all_cols if str(c) in ("крен_phi_рад", "тангаж_theta_рад")]
                                        else:
                                            pick = st.session_state.get(gs_key, [])
                                        if pick:
                                            st.session_state[gs_key] = _sanitize_cols(pick)

                                    pick_cols = st.multiselect(
                                        "Сигналы",
                                        options=cols_f,
                                        key=gs_key,
                                    )
                                    if not pick_cols:
                                        st.info("Выберите хотя бы один сигнал.")
                                    else:
                                        colS1, colS2, colS3, colS4 = st.columns([1.0, 0.9, 0.8, 0.8], gap="medium")
                                        with colS1:
                                            gs_mode = st.radio(
                                                "Режим",
                                                options=["stack", "overlay"],
                                                index=0,
                                                format_func=lambda v: "Осциллограф (stack)" if v == "stack" else "Overlay (одна ось)",
                                                key=f"gs_mode_{cache_key}",
                                            )
                                        with colS2:
                                            gs_maxp = st.number_input(
                                                "Макс точек",
                                                min_value=400,
                                                max_value=20000,
                                                value=2200,
                                                step=200,
                                                key=f"gs_maxp_{cache_key}",
                                            )
                                        with colS3:
                                            gs_dec = st.selectbox(
                                                "Decimation",
                                                options=["minmax", "stride"],
                                                index=0,
                                                key=f"gs_dec_{cache_key}",
                                            )
                                        with colS4:
                                            gs_render = st.selectbox(
                                                "Renderer",
                                                options=["svg", "webgl"],
                                                index=0,
                                                key=f"gs_render_{cache_key}",
                                            )

                                        colS5, colS6, colS7 = st.columns([1.0, 1.0, 1.0], gap="medium")
                                        with colS5:
                                            gs_auto_units = st.checkbox(
                                                "Auto-units (Pa→бар, рад→град)",
                                                value=True,
                                                key=f"gs_auto_units_{cache_key}",
                                            )
                                        with colS6:
                                            gs_hover = st.checkbox(
                                                "Hover: x unified (по всем подграфикам)",
                                                value=True,
                                                key=f"gs_hover_{cache_key}",
                                            )
                                        with colS7:
                                            gs_show_events = st.checkbox(
                                                "Показывать события (timeline)",
                                                value=True,
                                                key=f"gs_events_{cache_key}",
                                            )

                                        # Plot
                                        plot_studio_timeseries(
                                            df=df_src,
                                            tcol=tcol_gs,
                                            y_cols=pick_cols[:32],  # guard
                                            title=f"Graph Studio: {src_name}",
                                            mode=gs_mode,
                                            max_points=int(gs_maxp),
                                            decimation=gs_dec,
                                            auto_units=bool(gs_auto_units),
                                            render=gs_render,
                                            hover_unified=bool(gs_hover),
                                            playhead_x=playhead_x,
                                            events=(events_for_graphs if (gs_show_events and events_for_graphs) else None),
                                            plot_key=f"plot_graph_studio_{cache_key}",
                                        )

                                        # Export
                                        st.markdown("**Экспорт выбранных сигналов**")
                                        try:
                                            df_exp = df_src[[tcol_gs] + [c for c in pick_cols if c in df_src.columns]].copy()
                                            csv_bytes = df_exp.to_csv(index=False).encode("utf-8")
                                            st.download_button(
                                                "Скачать CSV",
                                                data=csv_bytes,
                                                file_name="graph_studio_signals.csv",
                                                mime="text/csv",
                                                key=f"gs_csv_{cache_key}",
                                            )
                                            xlsx_bytes = df_to_excel_bytes({"signals": df_exp})
                                            st.download_button(
                                                "Скачать Excel",
                                                data=xlsx_bytes,
                                                file_name="graph_studio_signals.xlsx",
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                key=f"gs_xlsx_{cache_key}",
                                            )
                                        except Exception:
                                            st.info("Экспорт недоступен для выбранного источника.")

                                        # Quick stats on time window
                                        try:
                                            tarr = np.asarray(df_src[tcol_gs].to_numpy(), dtype=float)
                                            t0 = float(np.min(tarr))
                                            t1 = float(np.max(tarr))
                                            tw = st.slider(
                                                "Окно времени для статистики (min/max/mean)",
                                                min_value=float(t0),
                                                max_value=float(t1),
                                                value=(float(t0), float(t1)),
                                                step=float(max(1e-3, (t1 - t0) / 200.0)),
                                                key=f"gs_tw_{cache_key}",
                                            )
                                            msk = (tarr >= float(tw[0])) & (tarr <= float(tw[1]))
                                            rows = []
                                            for c in pick_cols[:64]:
                                                if c not in df_src.columns:
                                                    continue
                                                yv = np.asarray(df_src[c].to_numpy(), dtype=float)
                                                yv = yv[msk]
                                                if yv.size <= 0:
                                                    continue
                                                rows.append({
                                                    "сигнал": c,
                                                    "min": float(np.nanmin(yv)),
                                                    "max": float(np.nanmax(yv)),
                                                    "mean": float(np.nanmean(yv)),
                                                })
                                            if rows:
                                                safe_dataframe(pd.DataFrame(rows), height=min(420, 34 * (len(rows) + 1) + 40))
                                        except Exception:
                                            pass


                elif view_res == "Потоки":
                    st.subheader("Потоки по веткам")
                    if df_mdot is None:
                        st.info("Потоки доступны только при record_full=True.")
                    else:
                        edge_cols = [c for c in df_mdot.columns if c != "время_с"]
                        default_edges = edge_cols[: min(6, len(edge_cols))]
                        pick_edges = st.multiselect("Ветки/элементы", options=edge_cols, default=default_edges, key="flow_graph_edges")

                        # перевод в Нл/мин (если есть константы)
                        try:
                            rho_N = float(P_ATM) / (float(getattr(model_mod, 'R_AIR', 287.0)) * float(getattr(model_mod, 'T_AIR', 293.15)))
                            scale = 1000.0 * 60.0 / rho_N
                            unit = "Нл/мин"
                        except Exception:
                            scale = 1.0
                            unit = "кг/с"

                        plot_lines(
                            df_mdot,
                            "время_с",
                            pick_edges,
                            title=f"Расход по веткам ({unit})",
                            yaxis_title=unit,
                            transform_y=lambda a: a * scale,
                            height=360,
                            plot_key="plot_flow_edges",
                            enable_select=True,
                            playhead_x=playhead_x,
                            events=events_for_graphs,
                            events_max=events_graph_max,
                            events_show_labels=events_graph_labels,

                        )
                        if _HAS_PLOTLY:
                            st.caption("Клик по графику выбирает ветку и подсвечивает её на SVG схеме (вкладка ‘Анимация’).")

                        if df_open is not None:
                            # открыто/закрыто (0/1)
                            open_cols = [c for c in pick_edges if c in df_open.columns]
                            if open_cols:
                                plot_lines(
                                    df_open,
                                    "время_с",
                                    open_cols,
                                    title="Состояния элементов (open=1)",
                                    yaxis_title="0/1",
                                    transform_y=lambda a: a,
                                    height=220,
                                    playhead_x=playhead_x,
                                    events=events_for_graphs,
                                    events_max=events_graph_max,
                                    events_show_labels=events_graph_labels,

                                )

                elif view_res == "Энерго-аудит":
                    st.subheader("Энерго-аудит")
                    if df_Egroups is not None and len(df_Egroups):
                        safe_dataframe(df_Egroups.sort_values("энергия_Дж", ascending=False), height=220)
                        if _HAS_PLOTLY and px is not None:
                            try:
                                fig = px.bar(df_Egroups.sort_values("энергия_Дж", ascending=False), x="группа", y="энергия_Дж", title="Энергия по группам")
                                safe_plotly_chart(fig)
                            except Exception:
                                pass
                    if df_Eedges is not None and len(df_Eedges):
                        st.markdown("**TOP-20 элементов по энергии**")
                        safe_dataframe(df_Eedges.sort_values("энергия_Дж", ascending=False).head(20), height=320)


                elif view_res == "Анимация":
                    st.subheader("Анимация")

                    # st.tabs не ленивый — для анимации нужно, чтобы исполнялся только выбранный раздел.
                    anim_view = st.radio(
                        "Подраздел",
                        options=["Механика", "Потоки (инструмент)", "Пневмосхема (SVG)"],
                        horizontal=True,
                        key=f"anim_view_{cur_hash}::{test_pick}",
                    )

                    # -----------------------------------
                    # (1) Механическая анимация (упрощённая)
                    # -----------------------------------
                    if anim_view == "Механика":
                        st.caption(
                            "Упрощённая анимация механики: фронтальный вид (крен) и боковой вид (тангаж). "
                            "Показывает движение рамы/колёс и ход штока по данным df_main."
                        )

                        st.radio(
                            "Клик по механике",
                            options=["replace", "add"],
                            format_func=lambda v: "Заменять выбор" if v == "replace" else "Добавлять к выбору",
                            horizontal=True,
                            index=0,
                            key="mech_click_mode",
                        )

                        if df_main is None or "время_с" not in df_main.columns:
                            st.warning("Нет df_main для анимации механики.")
                        else:
                            colM1, colM2, colM3 = st.columns(3)
                            with colM1:
                                px_per_m = st.slider("Масштаб (px/м)", 500, 4000, 2000, step=100, key="mech_px_per_m")
                            with colM2:
                                body_offset_px = st.slider("Отступ рамы над колёсами (px)", 40, 220, 110, step=5, key="mech_body_offset_px")
                            with colM3:
                                fps = st.slider("Скорость (FPS)", 10, 60, 30, step=5, key="mech_fps")

                            frame_dt_s = 1.0 / max(1.0, float(fps))

                            time_s = df_main["время_с"].astype(float).tolist()
                            corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]

                            # Геометрия для расчёта высоты углов рамы (как в модели)
                            try:
                                wheelbase = get_float_param(base_override, "база", default=1.5)
                                track = get_float_param(base_override, "колея", default=1.0)
                            except Exception:
                                wheelbase = 2.3
                                track = 1.2

                            # Нулевая поза для анимации: по умолчанию используем *_rel0, если они есть.
                            # Это синхронизировано с настройкой графиков (use_rel0_for_plots).
                            use_rel0_anim = bool(st.session_state.get("use_rel0_for_plots", True))

                            def _pick_col(_base: str) -> str:
                                """Выбрать колонку для визуализации (rel0, если доступно и включено)."""
                                if use_rel0_anim and (f"{_base}_rel0" in df_main.columns):
                                    return f"{_base}_rel0"
                                return _base

                            col_z = _pick_col("перемещение_рамы_z_м")
                            col_phi = _pick_col("крен_phi_рад")
                            col_theta = _pick_col("тангаж_theta_рад")

                            z = df_main.get(col_z, pd.Series(np.zeros(len(time_s)))).astype(float).to_numpy()
                            phi = df_main.get(col_phi, pd.Series(np.zeros(len(time_s)))).astype(float).to_numpy()
                            theta = df_main.get(col_theta, pd.Series(np.zeros(len(time_s)))).astype(float).to_numpy()

                            x_pos = np.array([wheelbase/2, wheelbase/2, -wheelbase/2, -wheelbase/2], dtype=float)
                            y_pos = np.array([track/2, -track/2, track/2, -track/2], dtype=float)

                            z_body = (
                                z[:, None]
                                + np.sin(phi)[:, None] * y_pos[None, :] * np.cos(theta)[:, None]
                                - np.sin(theta)[:, None] * x_pos[None, :]
                            )
                            body = {corners[i]: z_body[:, i].tolist() for i in range(4)}
                            body3d = {"z": z.astype(float).tolist()}  # for mech_car3d component (expects body.z)


                            wheel: Dict[str, List[float]] = {}
                            road: Dict[str, List[float]] = {}
                            stroke: Dict[str, List[float]] = {}
                            for c in corners:
                                col_w0 = f"перемещение_колеса_{c}_м"
                                col_r0 = f"дорога_{c}_м"
                                col_s = f"положение_штока_{c}_м"  # Шток показываем в абсолюте (0..L), чтобы видно было запас до упоров.
                                col_w = _pick_col(col_w0)
                                col_r = _pick_col(col_r0)
                                wheel[c] = df_main[col_w].astype(float).tolist() if col_w in df_main.columns else [0.0] * len(time_s)
                                road[c] = df_main[col_r].astype(float).tolist() if col_r in df_main.columns else [0.0] * len(time_s)
                                stroke[c] = df_main[col_s].astype(float).tolist() if col_s in df_main.columns else [0.0] * len(time_s)
                            # Если солвер не экспортировал профиль дороги в лог — восстанавливаем его из входного теста (road_func).
                            # Это НЕ "подрисовка физики": мы визуализируем вход (дорожный профиль), а динамику (крен/тангаж/ходы) берём только из расчёта.
                            #
                            # Важно: из-за контрактов/нормализации колонок иногда в df_main появляются колонки дороги,
                            # но заполненные нулями (как будто дорога плоская) — тогда тоже делаем восстановление.
                            needs_road_restore = False
                            try:
                                _test_cfg = tests_map.get(test_pick, {}) or {}
                                _has_road_input = bool(str(_test_cfg.get('road_csv') or _test_cfg.get('road_csv') or '').strip()) or callable(_test_cfg.get('road_func'))
                                if any((f"дорога_{c}_м" not in df_main.columns) for c in corners):
                                    needs_road_restore = True
                                elif _has_road_input:
                                    # Колонки есть, но они могут быть "пустыми" (все ~0).
                                    mx_road = 0.0
                                    for _c in corners:
                                        col = f"дорога_{_c}_м"
                                        if col not in df_main.columns:
                                            continue
                                        try:
                                            arr = pd.to_numeric(df_main[col], errors='coerce').fillna(0.0).to_numpy(dtype=float)
                                            mx_road = max(mx_road, float(np.max(np.abs(arr))))
                                        except Exception:
                                            pass
                                    if mx_road < 1e-9:
                                        needs_road_restore = True
                            except Exception:
                                pass

                            if needs_road_restore:

                                road_from_suite = compute_road_profile_from_suite(
                                    model_mod,
                                    tests_map.get(test_pick, {}),
                                    time_s,
                                    wheelbase,
                                    track,
                                    corners,
                                )
                                if road_from_suite is not None:
                                    road = road_from_suite
                                    # Нулевая поза: если используем rel0 — сдвигаем восстановленный профиль так, чтобы в t=0 дорога была 0.
                                    if use_rel0_anim:
                                        try:
                                            for _c in corners:
                                                _arr = road.get(_c, None)
                                                if _arr is None or len(_arr) == 0:
                                                    continue
                                                _z0 = float(_arr[0])
                                                road[_c] = [float(_v) - _z0 for _v in _arr]
                                        except Exception:
                                            pass
                                    st.caption("ℹ️ Профиль дороги восстановлен из входного профиля теста (road_func), т.к. в логе нет колонок дороги или они заполнены нулями.")
                                    log_event("anim_road_from_suite", test=test_pick)


                            try:
                                L_stroke_m = float(base_override.get("ход_штока", 0.25))
                            except Exception:
                                L_stroke_m = 0.25

                            # --- Движок анимации (по умолчанию: компонент; fallback доступен) ---
                            col_animA, col_animB = st.columns([1, 2])
                            with col_animA:
                                anim_backend = st.selectbox(
                                    "Движок анимации",
                                    ["Встроенный (matplotlib, совместимость)", "Компонент (SVG/Canvas, быстро)"],
                                    index=0,
                                    key=f"anim_backend_{cache_key}",
                                    help="Если видишь ошибки Streamlit Component (например apiVersion undefined) — используй встроенный режим.",
                                )

                            # Unified boolean used дальше по коду (и чтобы не ловить NameError в ветках)
                            use_component_anim = bool(str(anim_backend).startswith("Компонент"))
                            with col_animB:
                                st.caption(
                                    "По умолчанию включён встроенный режим (matplotlib): он самый надёжный и не зависит от Streamlit Components. "
                                    "Компонентный режим (SVG/Canvas) — экспериментальный: если он у тебя падает/не грузится — оставь встроенный."
                                )
                            # Log which backend the user chose (helps debug "Play causes infinite compute" etc.)
                            try:
                                _cur_backend = "component" if use_component_anim else "fallback"
                                _last_backend = st.session_state.get(f"_anim_backend_last::{cache_key}")
                                if _last_backend != _cur_backend:
                                    st.session_state[f"_anim_backend_last::{cache_key}"] = _cur_backend
                                    log_event(
                                        "anim_backend_selected",
                                        backend=_cur_backend,
                                        dataset_id=str(dataset_id_ui),
                                        proc=_proc_metrics(),
                                    )
                            except Exception:
                                pass

                            if use_component_anim:
                                st.caption("Управление Play/Pause/скоростью — в блоке **Таймлайн (общий playhead)** выше. Во время Play сервер не дёргается; синхронизация графиков выполняется при паузе/скраббинге.")

                            mech_view = st.radio(
                                "Визуализация",
                                options=["2D (схема)", "3D (машинка)"],
                                horizontal=True,
                                key=f"mech_view_{cache_key}",
                            )

                            if mech_view == "2D (схема)":
                                mech_comp = get_mech_anim_component() if use_component_anim else None
                                if mech_comp is not None:
                                    try:
                                        mech_comp(
                                            title="Механика (2D схема: крен/тангаж)",
                                            time=time_s,
                                            body=body,
                                            wheel=wheel,
                                            road=road,
                                            stroke=stroke,
                                            phi=phi.tolist(),
                                            theta=theta.tolist(),
                                            selected=st.session_state.get("mech_selected_corners", []),
                                            meta={
                                                "px_per_m": float(px_per_m),
                                                "body_offset_px": float(body_offset_px),
                                                "L_stroke_m": float(L_stroke_m),
                                                "frame_dt_s": float(frame_dt_s),
                                            },
                                            sync_playhead=True,
                                            playhead_storage_key="pneumo_play_state",
                                            dataset_id=dataset_id_ui,
                                            cmd=st.session_state.get(f"mech3d_cmd_{cache_key}"),
                                            height=620,
                                            key="mech2d_pick_event",
                                            default=None,
                                        )
                                    except Exception as _e_mech:
                                        st.warning("Компонент mech_anim упал во время выполнения. Показываю fallback (matplotlib).")
                                        log_event("component_runtime_error", component="mech_anim", error=repr(_e_mech), traceback=traceback.format_exc(), proc=_proc_metrics())
                                        if mech_fb is not None:
                                            mech_fb.render_mech2d_fallback(
                                                time=time_s,
                                                body=body,
                                                wheel=wheel,
                                                road=road,
                                                stroke=stroke,
                                                wheelbase_m=float(wheelbase),
                                                track_m=float(track),
                                                L_stroke_m=float(L_stroke_m),
                                                dataset_id=str(dataset_id_ui),
                                                idx=int(playhead_idx),
                                                show_controls=False,
                                                log_cb=log_event,
                                            )
                                        else:
                                            st.warning("Модуль mech_anim_fallback.py недоступен — показываю статическую схему.")
                                            log_event("fallback_missing", component="mech_anim_fallback", detail=str(_MECH_ANIM_FALLBACK_ERR) if _MECH_ANIM_FALLBACK_ERR else None, proc=_proc_metrics())
                                            if _MECH_ANIM_FALLBACK_ERR:
                                                with st.expander("Диагностика mech_anim_fallback"):
                                                    st.code(str(_MECH_ANIM_FALLBACK_ERR))
                                            png = HERE / "assets" / "mech_scheme.png"
                                            if png.exists():
                                                safe_image(str(png), caption="Механическая схема (статично)")
                                else:
                                    if use_component_anim:
                                        st.warning("Компонент mech_anim не найден/не загружается (components/mech_anim). Покажу fallback (matplotlib).")
                                        _mech_anim_component_err = component_last_error("mech_anim")
                                        log_event("component_missing", component="mech_anim", detail=str(_mech_anim_component_err) if _mech_anim_component_err else None, proc=_proc_metrics())
                                    _mech_anim_component_err = component_last_error("mech_anim")
                                    if _mech_anim_component_err:
                                        with st.expander("Диагностика mech_anim"):
                                            st.code(str(_mech_anim_component_err))
                                    else:
                                        st.info("Компонентный режим отключён — показываю встроенную 2D визуализацию (matplotlib).")
                                    
                                    if mech_fb is not None:
                                        mech_fb.render_mech2d_fallback(
                                            time=time_s,
                                            body=body,
                                            wheel=wheel,
                                            road=road,
                                            stroke=stroke,
                                            wheelbase_m=float(wheelbase),
                                            track_m=float(track),
                                            L_stroke_m=float(L_stroke_m),
                                            dataset_id=str(dataset_id_ui),
                                            idx=int(playhead_idx),
                                            show_controls=False,
                                            # Передаём реальный callback логирования, чтобы события Play/Seek попадали в logs/ui_*.log
                                            log_cb=log_event,
                                        )
                                    else:
                                        st.warning("Модуль mech_anim_fallback.py недоступен — показываю статическую схему.")
                                        png = HERE / "assets" / "mech_scheme.png"
                                        if png.exists():
                                            safe_image(str(png), caption="Механическая схема (статично)")
                            elif mech_view == "3D (машинка)":
                                st.caption(
                                    "3D-wireframe «машинка»: рама (параллелепипед), 4 колеса (цилиндры) и профили дороги под каждым колесом. "
                                    "Крутите сцену мышью, колёсики реально вращаются по пройденному пути."
                                )

                                # --- Path / maneuver (pure kinematics, does NOT affect the solver) ---
                                colA, colB, colC = st.columns(3)
                                with colA:
                                        demo_paths = st.checkbox(
                                            "3D: выбор траектории (vx/yaw = из расчёта, остальное — демо)",
                                            value=False,
                                            key=f"mech3d_demo_paths_{cache_key}",
                                        )
                                        if not demo_paths:
                                            # Авто-режим: если в расчёте есть world сигналы (vx/yaw) — используем их как траекторию.
                                            has_world_path = ('скорость_vx_м_с' in df_main.columns) and ('yaw_рад' in df_main.columns)
                                            if bool(has_world_path):
                                                path_mode = 'По vx/yaw из модели'
                                                st.caption('3D: траектория берётся из расчёта (vx + yaw) → скорость соответствует расчётной, повороты видны по yaw.')
                                                # дефолты (нужны как переменные ниже)
                                                try:
                                                    v0 = float(np.nanmean(df_main['скорость_vx_м_с'].to_numpy(dtype=float)))
                                                except Exception:
                                                    v0 = 12.0
                                                lateral_scale = 1.0
                                                steer_gain = 1.0
                                                steer_max_deg = 35.0
                                            else:
                                                path_mode = 'Статика (без движения)'
                                                st.caption('3D: world- траектория недоступна (нет колонок скорость_vx_м_с / yaw_рад). По умолчанию X/Z-движение выключено — показываем только крен/тангаж/ходы/дорогу.')
                                                v0 = 12.0
                                                lateral_scale = 1.0
                                                steer_gain = 1.0
                                                steer_max_deg = 35.0
                                        else:
                                            path_mode = st.selectbox(
                                                'Траектория (для 3D)',
                                                ['По vx/yaw из модели', 'Статика (без движения)', 'По ax/ay из модели', 'Прямая', 'Слалом', 'Поворот (радиус)'],
                                                index=0,
                                                key=f"mech3d_path_mode_{cache_key}",
                                            )
                                            st.info('3D: режим **По vx/yaw из модели** использует реальную траекторию из расчёта. Остальные режимы — кинематика/демо (НЕ влияет на расчёт).')
                                            v0 = st.number_input(
                                                'v0, м/с',
                                                min_value=0.0,
                                                max_value=60.0,
                                                value=12.0,
                                                step=0.5,
                                                key=f"mech3d_v0_{cache_key}",
                                            )
                                            lateral_scale = st.number_input(
                                                'масштаб бокового смещения',
                                                min_value=0.0,
                                                max_value=20.0,
                                                value=1.0,
                                                step=0.1,
                                                key=f"mech3d_lat_scale_{cache_key}",
                                            )
                                            steer_gain = st.number_input(
                                                'усиление руления (по φ)',
                                                min_value=0.0,
                                                max_value=10.0,
                                                value=1.0,
                                                step=0.1,
                                                key=f"mech3d_steer_gain_{cache_key}",
                                            )
                                            steer_max_deg = st.slider(
                                                'ограничение руления, град',
                                                min_value=0,
                                                max_value=60,
                                                value=35,
                                                step=1,
                                                key=f"mech3d_steer_max_deg_{cache_key}",
                                            )
                                with colB:
                                        if demo_paths:
                                            slalom_amp = st.number_input(
                                                "Слалом: амплитуда (м)",
                                                min_value=0.0,
                                                value=1.5,
                                                step=0.1,
                                                key=f"mech3d_slalom_amp_{cache_key}",
                                            )
                                            slalom_period = st.number_input(
                                                "Слалом: период (с)",
                                                min_value=0.2,
                                                value=4.0,
                                                step=0.2,
                                                key=f"mech3d_slalom_period_{cache_key}",
                                            )
                                            yaw_smooth = st.number_input(
                                                "Сглаживание yaw (0..1)",
                                                min_value=0.0,
                                                max_value=1.0,
                                                value=0.15,
                                                step=0.05,
                                                key=f"mech3d_yaw_smooth_{cache_key}",
                                            )
                                            st.markdown("**Поворот/радиус (для манёвра)**")
                                            turn_radius = st.number_input(
                                                "Поворот: радиус R (м)",
                                                min_value=1.0,
                                                value=35.0,
                                                step=1.0,
                                                key=f"mech3d_turn_R_{cache_key}",
                                            )
                                            turn_dir = st.selectbox(
                                                "Поворот: направление",
                                                options=["влево", "вправо"],
                                                index=0,
                                                key=f"mech3d_turn_dir_{cache_key}",
                                            )
                                        else:
                                            # дефолты (не используются, когда demo_paths=False)
                                            slalom_amp = 1.5
                                            slalom_period = 4.0
                                            # В физичном режиме (vx/yaw из модели) yaw трогать не надо → smoothing=0.
                                            yaw_smooth = 0.0 if str(path_mode) == 'По vx/yaw из модели' else 0.15
                                            turn_radius = 35.0
                                            turn_dir = "влево"

                                with colC:
                                    # --- Geometry / viz ---
                                    base_m = get_float_param(base_override, "база", default=1.5)
                                    track_m = get_float_param(base_override, "колея", default=1.0)
                                    wheel_r = st.number_input(
                                        "Радиус колеса (м)",
                                        min_value=0.05,
                                        value=0.32,
                                        step=0.01,
                                        key=f"mech3d_wheel_r_{cache_key}",
                                    )
                                    wheel_w = st.number_input(
                                        "Ширина колеса (м)",
                                        min_value=0.02,
                                        value=0.22,
                                        step=0.01,
                                        key=f"mech3d_wheel_w_{cache_key}",
                                    )
                                    body_y_off = st.number_input(
                                        "Поднять раму (м)",
                                        min_value=-5.0,
                                        value=0.60,
                                        step=0.05,
                                        key=f"mech3d_body_yoff_{cache_key}",
                                    )
                                    road_win = st.slider(
                                        "Окно дороги (точек)",
                                        min_value=60,
                                        max_value=600,
                                        value=220,
                                        step=10,
                                        key=f"mech3d_road_win_{cache_key}",
                                    )
                                    st.markdown("**Калибровка высот (3D)**")
                                    invert_y = st.checkbox("Инвертировать вертикаль (Y)", value=False, key=f"mech3d_invert_y_{cache_key}")
                                    y_sign = -1.0 if invert_y else 1.0
                                    wheel_center_offset = st.number_input("Сдвиг центра колеса по Y (м)", min_value=-5.0, value=0.0, step=0.05, key=f"mech3d_wheel_center_off_{cache_key}")
                                    road_y_offset = st.number_input("Сдвиг дороги по Y (м)", min_value=-5.0, value=0.0, step=0.05, key=f"mech3d_road_y_off_{cache_key}")
                                    road_subtract_radius = st.checkbox("Дорога в df = уровень центра колеса (рисовать поверхность = road - R)", value=False, key=f"mech3d_road_subr_{cache_key}")
                                    camera_follow = st.checkbox("Камера следует за машиной (центр кадра)", value=False, key=f"mech3d_cam_follow_{cache_key}")
                                    camera_follow_heading = st.checkbox("Камера поворачивается по yaw (удобно для поворотов/слалома)", value=False, key=f"mech3d_cam_follow_heading_{cache_key}")
                                    camera_follow_selected = st.checkbox(
                                        "Камера следует за выбранным колесом/осью (если выбрано)",
                                        value=False,
                                        key=f"mech3d_cam_follow_selected_{cache_key}",
                                    )
                                    follow_smooth = st.slider(
                                        "Сглаживание target (камера/следование)",
                                        min_value=0.0,
                                        max_value=1.0,
                                        value=0.25,
                                        step=0.05,
                                        key=f"mech3d_follow_smooth_{cache_key}",
                                    )
                                    hover_tooltip = st.checkbox(
                                        "Hover-подсказки (колесо/ось): wheel/road/gap",
                                        value=True,
                                        key=f"mech3d_hover_tooltip_{cache_key}",
                                    )
                                    show_minimap = st.checkbox(
                                        "Мини-карта (вид сверху) поверх сцены",
                                        value=False,
                                        key=f"mech3d_show_minimap_{cache_key}",
                                    )
                                    minimap_size = st.slider(
                                        "Размер мини-карты (px)",
                                        min_value=80,
                                        max_value=320,
                                        value=160,
                                        step=10,
                                        key=f"mech3d_minimap_size_{cache_key}",
                                    )

                                    st.markdown("**Отрисовка дороги/подвески (3D)**")
                                    road_mode_ui = st.selectbox(
                                        "Режим дороги (как рисовать профиль под колёсами)",
                                        options=["track (след по траектории)", "local (под машиной)"],
                                        index=0,
                                        key=f"mech3d_road_mode_{cache_key}",
                                    )
                                    road_mode = "track" if str(road_mode_ui).startswith("track") else "local"
                                    spin_per_wheel = st.checkbox(
                                        "Крутить колёса по пути каждого колеса (в повороте внутр/наруж отличаются)",
                                        value=True,
                                        key=f"mech3d_spin_per_wheel_{cache_key}",
                                    )
                                    show_suspension = st.checkbox(
                                        "Показывать стойки/подвеску (линии от рамы к колёсам)",
                                        value=True,
                                        key=f"mech3d_show_susp_{cache_key}",
                                    )
                                    show_contact = st.checkbox(
                                        "Показывать контакт колеса с дорогой (gap/penetration)",
                                        value=True,
                                        key=f"mech3d_show_contact_{cache_key}",
                                    )
                                    show_gap_heat = st.checkbox(
                                        "Цвет по gap (контакт/зазор) — окрашивать колёса/контакт",
                                        value=True,
                                        key=f"mech3d_show_gap_heat_{cache_key}",
                                    )
                                    gap_scale_m = st.slider(
                                        "Шкала gap (м) для цвета",
                                        min_value=0.005,
                                        max_value=0.200,
                                        value=0.050,
                                        step=0.005,
                                        key=f"mech3d_gap_scale_{cache_key}",
                                    )
                                    show_gap_hud = st.checkbox(
                                        "Показывать gap/min-gap в HUD",
                                        value=True,
                                        key=f"mech3d_show_gap_hud_{cache_key}",
                                    )
                                    min_gap_window = st.slider(
                                        "Окно min-gap (точек назад, 0=выкл)",
                                        min_value=0,
                                        max_value=2000,
                                        value=300,
                                        step=50,
                                        key=f"mech3d_min_gap_window_{cache_key}",
                                    )
                                    min_gap_step = st.slider(
                                        "Шаг анализа min-gap (прореживание)",
                                        min_value=1,
                                        max_value=20,
                                        value=3,
                                        step=1,
                                        key=f"mech3d_min_gap_step_{cache_key}",
                                    )
                                    hover_contact_marker = st.checkbox(
                                        "Маркер контакта при hover (крупнее, цвет по gap)",
                                        value=True,
                                        key=f"mech3d_hover_contact_{cache_key}",
                                    )
                                    st.markdown("**Камера/виды (3D)**")
                                    multi_view = st.checkbox(
                                        "Мультивид: 4 проекции (ISO/TOP/FRONT/SIDE)",
                                        value=False,
                                        key=f"mech3d_multi_view_{cache_key}",
                                    )
                                    allow_pan = st.checkbox(
                                        "Разрешить панорамирование (RMB/Shift+Drag)",
                                        value=True,
                                        key=f"mech3d_allow_pan_{cache_key}",
                                    )
                                    debug_overlay = st.checkbox(
                                        "DEBUG overlay (служебный текст на канве)",
                                        value=False,
                                        key=f"mech3d_debug_overlay_{cache_key}",
                                        help="Если 3D кажется пустым/«за пределами канвы»: включи overlay — он покажет dataset/idx/t и подтвердит, что сцена реально рисуется.",
                                    )
                                    if st.button(
                                        "Сбросить вид 3D (Reset view)",
                                        key=f"mech3d_reset_view_{cache_key}",
                                        help="Сбрасывает камеру/панорамирование (так же работает dblclick по 3D). Полезно, если сцену «увели» за экран.",
                                    ):
                                        st.session_state[f"mech3d_cmd_{cache_key}"] = {"reset_view": True, "ts": time.time()}

                                    st.markdown("**Дорога/траектория (3D)**")
                                    show_road_mesh = st.checkbox(
                                        "Показывать «сетку/перемычки» дороги (между левым и правым колесом)",
                                        value=True,
                                        key=f"mech3d_show_road_mesh_{cache_key}",
                                    )
                                    road_mesh_step = st.slider(
                                        "Шаг сетки дороги (точек)",
                                        min_value=1,
                                        max_value=30,
                                        value=2,
                                        step=1,
                                        key=f"mech3d_road_mesh_step_{cache_key}",
                                    )
                                    show_trail = st.checkbox(
                                        "Показывать траекторию (след кузова и колёс)",
                                        value=True,
                                        key=f"mech3d_show_trail_{cache_key}",
                                    )
                                    trail_len = st.slider(
                                        "Длина следа (точек назад)",
                                        min_value=20,
                                        max_value=2000,
                                        value=500,
                                        step=20,
                                        key=f"mech3d_trail_len_{cache_key}",
                                    )
                                    trail_step = st.slider(
                                        "Шаг следа (прореживание)",
                                        min_value=1,
                                        max_value=20,
                                        value=3,
                                        step=1,
                                        key=f"mech3d_trail_step_{cache_key}",
                                    )



                                # --- build path arrays ---
                                t_np = np.asarray(time_s, dtype=float)
                                n = len(t_np)
                                if n >= 2:
                                    dt = np.diff(t_np, prepend=t_np[0])
                                    dt[0] = dt[1]
                                else:
                                    dt = np.ones_like(t_np)

                                # outputs
                                x = np.zeros(n, dtype=float)
                                z = np.zeros(n, dtype=float)
                                vx = np.zeros(n, dtype=float)
                                vz = np.zeros(n, dtype=float)

                                if path_mode == "Статика (без движения)":
                                    vx[:] = 0.0
                                    vz[:] = 0.0
                                    x[:] = 0.0
                                    z[:] = 0.0
                                elif path_mode == "По vx/yaw из модели":
                                    # Физически осмысленная траектория: берём vx и yaw из лога модели и интегрируем положение.
                                    speed_col = "скорость_vx_м_с"
                                    yaw_col = "yaw_рад"
                                    v_body = df_main[speed_col].to_numpy(dtype=float) if speed_col in df_main.columns else np.full(n, float(v0), dtype=float)
                                    yaw = df_main[yaw_col].to_numpy(dtype=float) if yaw_col in df_main.columns else np.zeros(n, dtype=float)
                                    vx = v_body * np.cos(yaw)
                                    vz = v_body * np.sin(yaw)
                                    x = np.cumsum(vx * dt)
                                    z = np.cumsum(vz * dt)
                                    x = x - x[0]
                                    z = z - z[0]
                                elif path_mode == "Прямая":
                                    vx[:] = float(v0)
                                    vz[:] = 0.0
                                    x = np.cumsum(vx * dt)
                                    x = x - x[0]
                                    z[:] = 0.0
                                elif path_mode == "Слалом":
                                    vx[:] = float(v0)
                                    z = float(slalom_amp) * np.sin(2.0 * np.pi * t_np / float(slalom_period))
                                    # dz/dt for heading
                                    vz = float(slalom_amp) * (2.0 * np.pi / float(slalom_period)) * np.cos(2.0 * np.pi * t_np / float(slalom_period))
                                    x = np.cumsum(vx * dt)
                                    x = x - x[0]
                                elif path_mode == "Поворот (радиус)":
                                    R = float(st.session_state.get(f"mech3d_turn_R_{cache_key}", 35.0))
                                    dir_left = str(st.session_state.get(f"mech3d_turn_dir_{cache_key}", "влево")).startswith("влево")
                                    sign = 1.0 if dir_left else -1.0
                                    vx[:] = float(v0)
                                    # yaw = omega * t, omega = v / R
                                    omega = (float(v0) / max(1e-6, R)) * sign
                                    yaw = omega * (t_np - t_np[0])
                                    # circle arc: x=R*sin(yaw), z=sign*R*(1-cos(yaw))
                                    x = R * np.sin(yaw)
                                    z = sign * R * (1.0 - np.cos(yaw))
                                    # approximate v components
                                    vx = float(v0) * np.cos(yaw)
                                    vz = float(v0) * np.sin(yaw) * sign

                                else:
                                    # By ax/ay from df_main (if present). This is a visualization-only integration.
                                    ax_col = "ускорение_продольное_ax_м_с2"
                                    ay_col = "ускорение_поперечное_ay_м_с2"
                                    ax = df_main[ax_col].to_numpy(dtype=float) if ax_col in df_main.columns else np.zeros(n, dtype=float)
                                    ay = df_main[ay_col].to_numpy(dtype=float) if ay_col in df_main.columns else np.zeros(n, dtype=float)
                                    vx[0] = float(v0)
                                    vz[0] = 0.0
                                    for i in range(1, n):
                                        vx[i] = vx[i - 1] + ax[i] * dt[i]
                                        vz[i] = vz[i - 1] + ay[i] * dt[i]
                                        x[i] = x[i - 1] + vx[i] * dt[i]
                                        z[i] = z[i - 1] + vz[i] * dt[i]

                                # apply scale (helps avoid huge drift when integrating ay)
                                z = z * float(lateral_scale)

                                # yaw from velocity direction (robust for slalom + ax/ay)
                                if path_mode in ("Поворот (радиус)", "По vx/yaw из модели"):
                                    # yaw already set by the turn generator / model output
                                    pass
                                else:
                                    yaw = np.arctan2(vz * float(lateral_scale), np.maximum(vx, 1e-6))

                                # smooth yaw a bit to make camera nicer
                                if n >= 3 and float(yaw_smooth) > 0.0:
                                    a = float(yaw_smooth)
                                    for i in range(1, n):
                                        yaw[i] = (1 - a) * yaw[i - 1] + a * yaw[i]

                                # traveled distance for wheel spin
                                vabs = np.sqrt(vx * vx + (vz * float(lateral_scale)) * (vz * float(lateral_scale)))
                                s = np.cumsum(vabs * dt)
                                s = s - s[0]

                                # Steering angle (kinematic bicycle): r = yaw_rate = v/L * tan(delta) => delta = atan(L*r/v)
                                if n >= 3:
                                    yaw_u = np.unwrap(yaw)
                                    yaw_rate = np.gradient(yaw_u, t_np)
                                else:
                                    yaw_rate = np.zeros(n, dtype=float)
                                steer = np.arctan2(float(base_m) * yaw_rate, np.maximum(vabs, 0.1))
                                steer = steer * float(steer_gain)
                                steer_max = np.deg2rad(float(steer_max_deg))
                                steer = np.clip(steer, -steer_max, steer_max)

                                path_payload = {
                                    "x": x.tolist(),
                                    "z": z.tolist(),
                                    "yaw": yaw.tolist(),
                                    "s": s.tolist(),
                                    "v": vabs.tolist(),
                                    "steer": steer.tolist(),
                                }

                                ring_visual = None
                                try:
                                    _ring_spec = load_ring_spec_from_test_cfg(
                                        tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {},
                                        base_dir=ROOT_DIR,
                                    )
                                    if not (isinstance(_ring_spec, dict) and isinstance(_ring_spec.get("segments"), list)):
                                        _npz_candidates = []
                                        try:
                                            _pick_path = Path(str(pick))
                                            if _pick_path.suffix.lower() == '.npz':
                                                _npz_candidates.append(_pick_path)
                                        except Exception:
                                            pass
                                        try:
                                            _npz_ss = str(st.session_state.get('anim_latest_npz') or '').strip()
                                            if _npz_ss:
                                                _npz_candidates.append(Path(_npz_ss))
                                        except Exception:
                                            pass
                                        _anim_latest_npz_path, _ = local_anim_latest_export_paths_global(
                                            WORKSPACE_EXPORTS_DIR,
                                            ensure_exists=False,
                                        )
                                        _npz_candidates.append(_anim_latest_npz_path)
                                        for _npz_cand in _npz_candidates:
                                            try:
                                                _npz_cand = Path(_npz_cand)
                                                if _npz_cand.exists():
                                                    _ring_spec = load_ring_spec_from_npz(_npz_cand)
                                                    if isinstance(_ring_spec, dict) and isinstance(_ring_spec.get("segments"), list):
                                                        try:
                                                            log_event('ring_visual_loaded_from_npz_sidecar', npz=str(_npz_cand), test=str(test_pick))
                                                        except Exception:
                                                            pass
                                                        break
                                            except Exception:
                                                continue
                                    if isinstance(_ring_spec, dict) and isinstance(_ring_spec.get("segments"), list):
                                        ring_visual = build_ring_visual_payload_from_spec(
                                            _ring_spec,
                                            track_m=float(track_m),
                                            wheel_width_m=float(wheel_w),
                                            seed=int(_ring_spec.get("seed", 0) or 0),
                                        )
                                        if ring_visual:
                                            _nominal_prog = build_nominal_ring_progress_from_spec(_ring_spec, time_s)
                                            if _nominal_prog.get("distance_m"):
                                                path_payload["s"] = list(_nominal_prog.get("distance_m") or [])
                                                path_payload["v"] = list(_nominal_prog.get("v_mps") or path_payload.get("v") or [])
                                            path_payload = embed_path_payload_on_ring(
                                                path_payload,
                                                ring_visual,
                                                wheelbase_m=float(base_m),
                                            )
                                except Exception as _e_ring_visual:
                                    ring_visual = None
                                    log_event('ring_visual_payload_error', err=str(_e_ring_visual), test=str(test_pick))

                                mech3d_comp = get_mech_car3d_component() if use_component_anim else None
                                if mech3d_comp is None:
                                    if use_component_anim:
                                        st.warning("Компонент mech_car3d не найден/не загружается (components/mech_car3d). Покажу fallback (matplotlib).")
                                        _mech_car3d_component_err = component_last_error("mech_car3d")
                                        log_event("component_missing", component="mech_car3d", detail=str(_mech_car3d_component_err) if _mech_car3d_component_err else None, proc=_proc_metrics())
                                    else:
                                        st.info("Компонентный режим отключён — показываю встроенную 3D визуализацию (matplotlib).")
                                    
                                    if mech_fb is not None:
                                        mech_fb.render_mech3d_fallback(
                                            time=time_s,
                                            body=body3d,
                                            wheel=wheel,
                                            road=road,
                                            phi=phi.tolist(),
                                            theta=theta.tolist(),
                                            path=path_payload,
                                            wheelbase_m=float(base_m),
                                            track_m=float(track_m),
                                            dataset_id=str(dataset_id_ui),
                                            # Передаём callback логирования, чтобы видеть в логах причины "кажется бесконечным" (частота rerun, idx, t)
                                            log_cb=log_event,
                                        )
                                    else:
                                        st.error("Модуль mech_anim_fallback.py недоступен — 3D fallback не может быть показан.")

                                else:
                                    # reasonable body dims from geometry
                                    body_L = float(st.session_state.get(f"mech3d_body_L_{cache_key}", base_m * 0.85))
                                    body_W = float(st.session_state.get(f"mech3d_body_W_{cache_key}", track_m * 0.55))
                                    body_H = float(st.session_state.get(f"mech3d_body_H_{cache_key}", 0.35))
                                    c1, c2, c3 = st.columns(3)
                                    with c1:
                                        body_L = st.number_input("Длина рамы (м)", min_value=0.2, value=body_L, step=0.05, key=f"mech3d_body_L_{cache_key}")
                                    with c2:
                                        body_W = st.number_input("Ширина рамы (м)", min_value=0.2, value=body_W, step=0.05, key=f"mech3d_body_W_{cache_key}")
                                    with c3:
                                        body_H = st.number_input("Высота рамы (м)", min_value=0.05, value=body_H, step=0.02, key=f"mech3d_body_H_{cache_key}")

                                    geo_payload = {
                                        "base_m": float(base_m),
                                        "track_m": float(track_m),
                                        "wheel_radius_m": float(wheel_r),
                                        "wheel_width_m": float(wheel_w),
                                        "wheel_center_offset_m": float(wheel_center_offset),
                                        "road_y_offset_m": float(road_y_offset),
                                        "road_subtract_radius": bool(road_subtract_radius),
                                        "road_mode": str(road_mode),
                                        "spin_per_wheel": bool(spin_per_wheel),
                                        "show_suspension": bool(show_suspension),
                                                                                "show_contact": bool(show_contact),
                                        "multi_view": bool(multi_view),
                                        "allow_pan": bool(allow_pan),
                                        "show_road_mesh": bool(show_road_mesh),
                                        "road_mesh_step": int(road_mesh_step),
                                        "show_trail": bool(show_trail),
                                        "trail_len": int(trail_len),
                                        "trail_step": int(trail_step),
                                        "y_sign": float(y_sign),
                                        "camera_follow": bool(camera_follow),
                                        "camera_follow_heading": bool(camera_follow_heading),
                                        "camera_follow_selected": bool(camera_follow_selected),
                                        "hover_tooltip": bool(hover_tooltip),
                                        "debug_overlay": bool(debug_overlay),
                                        "follow_smooth": float(follow_smooth),
                                        "show_gap_heat": bool(show_gap_heat),
                                        "gap_scale_m": float(gap_scale_m),
                                        "show_gap_hud": bool(show_gap_hud),
                                        "min_gap_window": int(min_gap_window),
                                        "min_gap_step": int(min_gap_step),
                                        "hover_contact_marker": bool(hover_contact_marker),
                                        "show_minimap": bool(show_minimap),
                                        "minimap_size": int(minimap_size),
                                        "body_y_offset_m": float(body_y_off),
                                        "body_L_m": float(body_L),
                                        "body_W_m": float(body_W),
                                        "body_H_m": float(body_H),
                                        "road_window_points": int(road_win),
                                        "path_window_points": 160,
                                        "roll_sign": 1.0,
                                        "pitch_sign": 1.0,
                                        "spin_sign": 1.0,
                                        "wheel_x_off_m": {"ЛП": base_m * 0.5, "ПП": base_m * 0.5, "ЛЗ": -base_m * 0.5, "ПЗ": -base_m * 0.5},
                                        "wheel_z_off_m": {"ЛП": -track_m * 0.5, "ПП": track_m * 0.5, "ЛЗ": -track_m * 0.5, "ПЗ": track_m * 0.5},
                                        "ring_visual": ring_visual,
                                    }
                                    if ring_visual:
                                        st.info(
                                            f"3D кольцо: замкнутый ring-view, сегменты подсвечены по краям, heatmap = кривизна. "
                                            f"Длина кольца ≈ {float(ring_visual.get('ring_length_m', 0.0)):.2f} м, post-seam ≈ {1000.0 * float((ring_visual.get('meta', {}) or {}).get('seam_max_jump_m', 0.0) or 0.0):.1f} мм."
                                        )

                                    try:
                                        mech3d_comp(
                                            title="Механика 3D (машинка wireframe)",
                                            time=time_s,
                                            body=body3d,
                                            wheel=wheel,
                                            road=road,
                                            phi=phi.tolist(),
                                            theta=theta.tolist(),
                                            selected=st.session_state.get("mech_selected_corners", []),
                                            path=path_payload,
                                            geo=geo_payload,
                                            dataset_id=dataset_id_ui,
                                            playhead_storage_key="pneumo_play_state",
                                            height=680,
                                            key="mech3d_pick_event",
                                            default=None,
                                        )
                                    except Exception as _e_mech3d:
                                        st.warning("Компонент мех. 3D (mech_car3d) упал во время выполнения. Показываю статическую схему.")
                                        log_event("component_runtime_error", component="mech_car3d", error=repr(_e_mech3d), traceback=traceback.format_exc(), proc=_proc_metrics())
                                        png = HERE / "assets" / "mech_scheme.png"
                                        if png.exists():
                                            safe_image(str(png), caption="Механическая схема (статично)")
                            with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):
                                png = HERE / "assets" / "mech_scheme.png"
                                if png.exists():
                                    safe_image(str(png))
                                svg_path = HERE / "assets" / "mech_scheme.svg"
                                if svg_path.exists():
                                    st.download_button(
                                        "Скачать mech_scheme.svg",
                                        data=svg_path.read_bytes(),
                                        file_name="mech_scheme.svg",
                                        mime="image/svg+xml",
                                    )

                    # -----------------------------------
                    # (2) Потоки: инструментальная анимация
                    # -----------------------------------
                    elif anim_view == "Потоки (инструмент)":
                        if df_mdot is None:
                            st.info("Анимация потоков доступна только при record_full=True (df_mdot).")
                        else:
                            st.caption("MVP: каждая выбранная ветка рисуется отдельной линией, по ней бегает маркер.")
                            edge_cols = [c for c in df_mdot.columns if c != "время_с"]
                            # по умолчанию берём несколько «похожих на магистраль»
                            defaults = [c for c in edge_cols if ("Ресивер3" in c or "выхлоп" in c or "предохран" in c)][:8]
                            if not defaults:
                                defaults = edge_cols[: min(8, len(edge_cols))]
                            pick_edges = st.multiselect("Ветки для анимации", options=edge_cols, default=defaults, key="anim_edges")
                            if len(pick_edges) == 0:
                                st.info("Выберите хотя бы одну ветку.")
                            else:
                                # конверсия в Нл/мин
                                try:
                                    rho_N = float(P_ATM) / (float(getattr(model_mod, "R_AIR", 287.0)) * float(getattr(model_mod, "T_AIR", 293.15)))
                                    scale = 1000.0 * 60.0 / rho_N
                                    unit = "Нл/мин"
                                except Exception:
                                    scale = 1.0
                                    unit = "кг/с"

                                time_s = df_mdot["время_с"].astype(float).tolist()
                                edge_series = []
                                for c in pick_edges:
                                    q = (df_mdot[c].astype(float).to_numpy() * scale).tolist()
                                    if df_open is not None and c in df_open.columns:
                                        op = df_open[c].astype(int).tolist()
                                    else:
                                        op = None
                                    edge_series.append({"name": c, "q": q, "open": op, "unit": unit})

                                render_flow_panel_html(time_s=time_s, edge_series=edge_series, height=560)

                    # -----------------------------------
                    # (3) Потоки: анимация по SVG схеме + автосопоставление имён
                    # -----------------------------------
                    elif anim_view == "Пневмосхема (SVG)":
                        if df_mdot is None:
                            st.info("Анимация по схеме (SVG) доступна только при record_full=True (df_mdot + mapping).")
                        else:
                            st.caption(
                                "Анимация поверх SVG схемы работает по mapping JSON: "
                                "ветка → polyline(points), узел → [x,y] в координатах SVG."
                            )

                            st.radio(
                                "Клик по схеме",
                                options=["add", "replace"],
                                format_func=lambda v: "Добавлять к выбору" if v == "add" else "Заменять выбор",
                                horizontal=True,
                                key="svg_click_mode",
                            )

                            edge_cols = [c for c in df_mdot.columns if c != "время_с"]

                            # Узлы давления (подписи на схеме) берём из df_p при record_full=True
                            if df_p is not None:
                                node_cols = [c for c in df_p.columns if c != "время_с"]
                            else:
                                node_cols = []

                            if node_cols:
                                default_nodes = [n for n in [
                                    "Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор",
                                    "узел_после_рег_Pmin_питание_Р2", "узел_после_предохран_Pmax",
                                    "узел_после_рег_Pmid", "узел_после_рег_Pmin_сброс", "узел_после_рег_заряд_аккумулятора",
                                    "Магистраль_ЛП2_ПЗ2", "Магистраль_ПП2_ЛЗ2",
                                ] if n in node_cols]
                                if not default_nodes:
                                    default_nodes = node_cols[: min(8, len(node_cols))]

                                pick_nodes_svg = st.multiselect(
                                    "Узлы давления для отображения на схеме",
                                    options=node_cols,
                                    default=default_nodes,
                                    key="anim_nodes_svg",
                                )
                            else:
                                pick_nodes_svg = []
                                st.info("Подписи давления на схеме доступны только при record_full=True (df_p).")

                            # --- SVG источник (по умолчанию: assets/pneumo_scheme.svg)
                            default_svg_path = HERE / "assets" / "pneumo_scheme.svg"
                            default_svg_text = ""
                            if default_svg_path.exists():
                                try:
                                    default_svg_text = default_svg_path.read_text(encoding="utf-8")
                                except Exception:
                                    default_svg_text = default_svg_path.read_text(errors="ignore")

                            svg_upl = st.file_uploader(
                                "SVG файл схемы (опционально, если хотите заменить)",
                                type=["svg"],
                                key="svg_scheme_upl",
                            )
                            if svg_upl is not None:
                                try:
                                    svg_text = svg_upl.getvalue().decode("utf-8")
                                except Exception:
                                    svg_text = svg_upl.getvalue().decode("utf-8", errors="ignore")
                            else:
                                svg_text = default_svg_text

                            if not svg_text:
                                st.warning("SVG не найден. Положите файл в assets/pneumo_scheme.svg или загрузите через uploader.")
                            else:
                                svg_inline = strip_svg_xml_header(svg_text)

                                # viewBox для шаблона mapping
                                vb = "0 0 1920 1080"
                                m = re.search(r'viewBox\s*=\s*"([^"]+)"', svg_inline)
                                if m:
                                    vb = m.group(1)

                                template_mapping = {
                                    "version": 2,
                                    "viewBox": vb,
                                    "edges": {c: [] for c in edge_cols},
                                    "nodes": {n: None for n in pick_nodes_svg},
                                }
                                st.download_button(
                                    "Скачать шаблон mapping JSON",
                                    data=json.dumps(template_mapping, ensure_ascii=False, indent=2).encode("utf-8"),
                                    file_name="pneumo_svg_mapping_template.json",
                                    mime="application/json",
                                )

                                with st.expander("Авторазметка из SVG (beta)", expanded=False):
                                    if not _HAS_SVG_AUTOTRACE:
                                        st.error("pneumo_solver_ui.svg_autotrace не импортируется. Проверьте целостность пакета pneumo_solver_ui.")
                                    else:
                                        st.info(
                                            "Авторазметка пытается построить черновой mapping JSON по геометрии линий (<line>) "
                                            "и текстовым меткам (<text>, transform=matrix...). "
                                            "Это помогает быстро получить стартовый mapping без ручного клика по каждой ветке."
                                        )

                                        colAT1, colAT2, colAT3 = st.columns(3)
                                        with colAT1:
                                            tol_merge = st.slider(
                                                "Tol склейки концов (px)",
                                                0.5, 8.0, 2.1, step=0.1,
                                                key="svg_autotrace_tol_merge",
                                            )
                                        with colAT2:
                                            max_label_dist = st.slider(
                                                "Макс. расстояние метка → трубка (px)",
                                                10.0, 300.0, 80.0, step=5.0,
                                                key="svg_autotrace_max_label_dist",
                                            )
                                        with colAT3:
                                            min_name_score = st.slider(
                                                "Порог сходства имён (fuzzy)",
                                                0.50, 0.95, 0.75, step=0.05,
                                                key="svg_autotrace_min_name_score",
                                            )

                                        colAT4, colAT5, colAT6 = st.columns(3)
                                        with colAT4:
                                            simplify_eps = st.slider(
                                                "Упростить полилинии (epsilon, px)",
                                                0.0, 5.0, 0.0, step=0.2,
                                                key="svg_autotrace_simplify_eps",
                                            )
                                        with colAT5:
                                            snap_nodes = st.checkbox(
                                                "Snap узлы к графу",
                                                value=True,
                                                key="svg_autotrace_snap_nodes",
                                            )
                                        with colAT6:
                                            prefer_junc = st.checkbox(
                                                "Prefer junction (deg≠2)",
                                                value=True,
                                                key="svg_autotrace_prefer_junction",
                                            )
                                        node_snap_max_dist = st.slider(
                                            "Макс. dist метка→junction для snap (px)",
                                            5.0, 160.0, 40.0, step=5.0,
                                            key="svg_autotrace_snap_dist",
                                        )

# Выбираем ветки/узлы, для которых строим mapping
                                        default_auto_edges = edge_cols[: min(16, len(edge_cols))]
                                        auto_edges = st.multiselect(
                                            "Ветки, для которых построить mapping.edges",
                                            options=edge_cols,
                                            default=default_auto_edges,
                                            key="svg_autotrace_edges",
                                        )
                                        auto_nodes = st.multiselect(
                                            "Узлы, для которых построить mapping.nodes (координаты подписей давления)",
                                            options=(pick_nodes_svg if pick_nodes_svg else node_cols),
                                            default=(pick_nodes_svg if pick_nodes_svg else []),
                                            key="svg_autotrace_nodes",
                                        )

                                        colB1, colB2, colB3 = st.columns(3)
                                        with colB1:
                                            do_analyze = st.button("Проанализировать SVG", key="btn_svg_autotrace_analyze")
                                        with colB2:
                                            do_build = st.button("Сгенерировать mapping (auto)", key="btn_svg_autotrace_build")
                                        with colB3:
                                            do_clear = st.button("Очистить результаты", key="btn_svg_autotrace_clear")

                                        if do_clear:
                                            for k in ["svg_autotrace_analysis", "svg_autotrace_report", "svg_autotrace_components"]:
                                                st.session_state.pop(k, None)
                                            st.success("Очищено.")

                                        if do_analyze:
                                            try:
                                                analysis = extract_polylines(svg_inline, tol_merge=float(tol_merge))  # type: ignore
                                                st.session_state["svg_autotrace_analysis"] = analysis
                                                st.success(
                                                    f"SVG разобран: polylines={len(analysis.get('polylines', []))}, "
                                                    f"nodes={len(analysis.get('nodes', []))}, edges={len(analysis.get('edges', []))}"
                                                )
                                            except Exception as e:
                                                st.error(f"Ошибка анализа SVG: {e}")

                                        if do_build:
                                            try:
                                                mapping_auto, report_auto = auto_build_mapping_from_svg(  # type: ignore
                                                    svg_text=svg_inline,
                                                    edge_names=list(auto_edges),
                                                    node_names=list(auto_nodes),
                                                    tol_merge=float(tol_merge),
                                                    max_label_dist=float(max_label_dist),
                                                    min_name_score=float(min_name_score),
                                                    simplify_epsilon=float(simplify_eps),
                                                    snap_nodes_to_graph=bool(snap_nodes),
                                                    prefer_junctions=bool(prefer_junc),
                                                    node_snap_max_dist=float(node_snap_max_dist),
                                                )
                                                st.session_state["svg_mapping_text"] = json.dumps(mapping_auto, ensure_ascii=False, indent=2)
                                                st.session_state["svg_autotrace_report"] = report_auto
                                                st.success(
                                                    f"mapping обновлён (edges={len(mapping_auto.get('edges', {}))}, "
                                                    f"nodes={len(mapping_auto.get('nodes', {}))}). "
                                                    "Прокрутите ниже — mapping уже подставлен в текстовое поле."
                                                )
                                            except Exception as e:
                                                st.error(f"Ошибка авторазметки: {e}")

                                        analysis = st.session_state.get("svg_autotrace_analysis")
                                        report_auto = st.session_state.get("svg_autotrace_report")

                                        if analysis:
                                            with st.expander("Результаты анализа SVG", expanded=False):
                                                try:
                                                    deg_counts = analysis.get("degree_counts", {})
                                                    st.write(
                                                        {
                                                            "viewBox": analysis.get("viewBox"),
                                                            "nodes": len(analysis.get("nodes", [])),
                                                            "edges": len(analysis.get("edges", [])),
                                                            "polylines": len(analysis.get("polylines", [])),
                                                            "degree_counts": deg_counts,
                                                            "junction_nodes": len(analysis.get("junction_nodes", [])),
                                                            "poly_endpoints": len(analysis.get("poly_endpoints", [])),
                                                        }
                                                    )
                                                    df_txt = pd.DataFrame(analysis.get("texts", []))
                                                    if len(df_txt):
                                                        # небольшая фильтрация “шумных” P/Q
                                                        df_show = df_txt.copy()
                                                        df_show["len"] = df_show["text"].astype(str).str.len()
                                                        df_show = df_show.sort_values(["len", "text"]).head(200)
                                                        safe_dataframe(df_show[["text", "x", "y", "klass"]], height=280)
                                                    st.download_button(
                                                        "Скачать анализ SVG (json)",
                                                        data=json.dumps(analysis, ensure_ascii=False, indent=2).encode("utf-8"),
                                                        file_name="svg_analysis.json",
                                                        mime="application/json",
                                                    )
                                                except Exception as e:
                                                    st.error(f"Не удалось показать анализ: {e}")

                                        if report_auto:
                                            with st.expander("Отчёт авторазметки (mapping)", expanded=False):
                                                try:
                                                    st.write(report_auto.get("summary", {}))
                                                    df_edges = pd.DataFrame(report_auto.get("edges", []))
                                                    if len(df_edges):
                                                        safe_dataframe(df_edges.sort_values(["score", "dist"], ascending=[False, True]), height=260)
                                                    df_nodes = pd.DataFrame(report_auto.get("nodes", []))
                                                    if len(df_nodes):
                                                        try:
                                                            df_nodes_show = df_nodes.sort_values(
                                                                ["score", "dist_label_poly"], ascending=[False, True]
                                                            )
                                                        except Exception:
                                                            df_nodes_show = df_nodes
                                                        safe_dataframe(df_nodes_show, height=240)
                                                    if report_auto.get("unmatched_nodes"):
                                                        st.warning(f"Не сопоставлены {len(report_auto['unmatched_nodes'])} узлов.")
                                                    if report_auto.get("unmatched_edges"):
                                                        st.warning(f"Не сопоставлены {len(report_auto['unmatched_edges'])} веток.")
                                                    st.download_button(
                                                        "Скачать отчёт авторазметки (json)",
                                                        data=json.dumps(report_auto, ensure_ascii=False, indent=2).encode("utf-8"),
                                                        file_name="svg_autotrace_report.json",
                                                        mime="application/json",
                                                    )
                                                except Exception as e:
                                                    st.error(f"Не удалось показать отчёт: {e}")

                                        with st.expander("Компоненты (bbox по текстовым меткам)", expanded=False):
                                            st.caption("Грубая оценка bbox компонентов вокруг меток типа 'Ресивер', 'Аккумулятор', 'Рег.'.")
                                            comp_r = st.slider("Радиус поиска линий вокруг метки (px)", 40, 260, 120, step=10, key="svg_comp_radius")
                                            if st.button("Найти компоненты", key="btn_svg_find_components"):
                                                try:
                                                    comps = detect_component_bboxes(svg_inline, radius=float(comp_r))  # type: ignore
                                                    st.session_state["svg_autotrace_components"] = comps
                                                    st.success(f"Найдено компонентов: {len(comps)}")
                                                except Exception as e:
                                                    st.error(f"Ошибка поиска компонентов: {e}")

                                            comps = st.session_state.get("svg_autotrace_components", [])
                                            if comps:
                                                dfc = pd.DataFrame(comps)
                                                safe_dataframe(dfc, height=260)
                                                st.download_button(
                                                    "Скачать компоненты (json)",
                                                    data=json.dumps(comps, ensure_ascii=False, indent=2).encode("utf-8"),
                                                    file_name="svg_components.json",
                                                    mime="application/json",
                                                )


                                with st.expander("Путь по схеме (connectivity beta)", expanded=False):
                                    st.info(
                                        "Инструмент ниже ищет кратчайший путь по *геометрическому графу* труб (line->nodes/edges), "
                                        "между двумя текстовыми метками SVG. "
                                        "Результат подсвечивается на схеме как маршрут (overlay)."
                                    )

                                    analysis = st.session_state.get("svg_autotrace_analysis")
                                    if not analysis:
                                        st.warning("Сначала нажмите **Проанализировать SVG** в блоке выше.")
                                    else:
                                        texts = analysis.get("texts", [])
                                        if not isinstance(texts, list) or len(texts) == 0:
                                            st.warning("В SVG не найдены текстовые метки (<text>).")
                                        else:
                                            # --- фильтрация “шумных” меток (P/Q и т.п.)
                                            def _is_noise_label(s: str) -> bool:
                                                s = (s or "").strip()
                                                if not s:
                                                    return True
                                                s_up = s.upper()
                                                if s_up in {"P", "Q", "PQ", "PQPQ"}:
                                                    return True
                                                if len(s) == 1:
                                                    return True
                                                return False

                                            flt = st.text_input(
                                                "Фильтр меток (подстрока, регистр не важен)",
                                                value=st.session_state.get("svg_route_filter", ""),
                                                key="svg_route_filter",
                                            )

                                            items = []
                                            for ti, t in enumerate(texts):
                                                try:
                                                    label = str(t.get("text", "")).strip()
                                                    if _is_noise_label(label):
                                                        continue
                                                    if flt and (flt.lower() not in label.lower()):
                                                        continue
                                                    x = float(t.get("x", 0.0))
                                                    y = float(t.get("y", 0.0))
                                                    items.append((ti, label, x, y))
                                                except Exception:
                                                    continue

                                            if len(items) == 0:
                                                st.warning("Нет подходящих меток (после фильтрации). Попробуйте очистить фильтр.")
                                            else:
                                                # ограничим список, чтобы UI не тормозил
                                                items = items[:600]

                                                def _fmt_item(it):
                                                    ti, label, x, y = it
                                                    return f"#{ti:03d} | {label} | ({x:.0f},{y:.0f})"

                                                opts = [_fmt_item(it) for it in items]
                                                opt_to_idx = {o: int(o.split('|')[0].strip().lstrip('#')) for o in opts}


                                                # --- Ассистент разметки веток (guided): выбор целевой ветки + подсказки меток
                                                edge_target = st.session_state.get("svg_route_assign_edge", edge_cols[0] if edge_cols else "")
                                                with st.expander("Ассистент разметки веток (guided)", expanded=False):
                                                    if not edge_cols:
                                                        st.info("Нет df_mdot веток (edge_cols пуст). Запустите детальный прогон с **record_full=True**.")
                                                    else:
                                                        # применяем запрос авто-перехода к неразмеченной ветке (до создания selectbox)
                                                        _adv = st.session_state.pop("route_advance_to_unmapped", None)
                                                        if isinstance(_adv, str) and _adv in edge_cols:
                                                            st.session_state["svg_route_assign_edge"] = _adv

                                                        # текущее покрытие mapping.edges
                                                        _map_txt = st.session_state.get("svg_mapping_text", "{}") or "{}"
                                                        mapping_current = {}
                                                        try:
                                                            mapping_current = json.loads(_map_txt)
                                                            if not isinstance(mapping_current, dict):
                                                                mapping_current = {}
                                                        except Exception:
                                                            mapping_current = {}
                                                        _edges_map = mapping_current.get("edges") if isinstance(mapping_current, dict) else {}
                                                        if not isinstance(_edges_map, dict):
                                                            _edges_map = {}
                                                        mapped_set = set(_edges_map.keys())
                                                        unmapped = [e for e in edge_cols if e not in mapped_set]
                                                        st.caption(f"Покрытие mapping.edges: {len(mapped_set)}/{len(edge_cols)} веток. Неразмечено: {len(unmapped)}.")

                                                        colW1, colW2, colW3, colW4 = st.columns([1, 1, 1, 2])
                                                        with colW1:
                                                            if st.button("Следующая неразмеченная", key="btn_route_next_unmapped"):
                                                                if unmapped:
                                                                    st.session_state["svg_route_assign_edge"] = unmapped[0]
                                                        with colW2:
                                                            st.checkbox("Автопереход после записи", value=True, key="route_auto_next")
                                                        with colW3:
                                                            st.checkbox("Показать таблицу покрытия", value=False, key="route_show_cov")
                                                        with colW4:
                                                            if st.button("Автофильтр по имени ветки", key="btn_route_autofilter_edge"):
                                                                try:
                                                                    tgt0 = str(st.session_state.get("svg_route_assign_edge", "") or "")
                                                                    # ищем сигнатуры типа ЛП1/ПЗ2
                                                                    ms = re.findall(r"(ЛП|ЛЗ|ПП|ПЗ)\s*([0-9]+)", tgt0.upper())
                                                                    if ms:
                                                                        st.session_state["svg_route_filter"] = f"{ms[0][0]}{ms[0][1]}"
                                                                    else:
                                                                        tt = tgt0.strip().split()
                                                                        if tt:
                                                                            st.session_state["svg_route_filter"] = tt[0][:24]
                                                                except Exception:
                                                                    pass

                                                        st.checkbox("Очистить маршрут после записи", value=False, key="route_clear_after_assign")

                                                        if st.session_state.get("route_show_cov"):
                                                            try:
                                                                df_cov = pd.DataFrame([
                                                                    {
                                                                        "edge": e,
                                                                        "mapped": (e in mapped_set),
                                                                        "segments": len(_edges_map.get(e, [])) if isinstance(_edges_map.get(e, []), list) else 0,
                                                                    }
                                                                    for e in edge_cols
                                                                ])
                                                                safe_dataframe(df_cov.sort_values(["mapped", "edge"]), height=220)
                                                            except Exception as e:
                                                                st.warning(f"Не удалось построить таблицу покрытия: {e}")

                                                        edge_target = st.selectbox(
                                                            "Целевая ветка модели (df_mdot) для разметки",
                                                            options=edge_cols,
                                                            key="svg_route_assign_edge",
                                                        )

                                                        st.markdown("**Подсказки START/END меток по имени ветки (fuzzy):**")
                                                        colS1, colS2, colS3 = st.columns([1, 1, 2])
                                                        with colS1:
                                                            sugg_thr = st.slider("Порог", 0.0, 1.0, 0.55, step=0.01, key="route_label_sugg_thr")
                                                        with colS2:
                                                            sugg_k = st.slider("Top-K", 3, 30, 12, step=1, key="route_label_sugg_k")
                                                        with colS3:
                                                            if st.button("↔ Поменять START/END", key="btn_swap_route_labels"):
                                                                s0 = st.session_state.get("svg_route_start_opt")
                                                                e0 = st.session_state.get("svg_route_end_opt")
                                                                if s0 is not None and e0 is not None:
                                                                    st.session_state["svg_route_start_opt"] = e0
                                                                    st.session_state["svg_route_end_opt"] = s0

                                                        def _latinize_sig(s: str) -> str:
                                                            if not isinstance(s, str):
                                                                s = str(s)
                                                            table = str.maketrans({
                                                                "Л": "L", "П": "P", "З": "Z",
                                                                "л": "l", "п": "p", "з": "z",
                                                                "Р": "R", "р": "r",
                                                                "В": "B", "в": "b",
                                                                "А": "A", "а": "a",
                                                                "Е": "E", "е": "e",
                                                                "К": "K", "к": "k",
                                                                "М": "M", "м": "m",
                                                                "Н": "H", "н": "h",
                                                                "О": "O", "о": "o",
                                                                "С": "C", "с": "c",
                                                                "Т": "T", "т": "t",
                                                                "У": "Y", "у": "y",
                                                                "Х": "X", "х": "x",
                                                            })
                                                            return s.translate(table)

                                                        def _score_edge_label(edge_name: str, label: str) -> float:
                                                            try:
                                                                s1 = _name_score(edge_name, label)
                                                                s2 = _name_score(_latinize_sig(edge_name), _latinize_sig(label))
                                                                return float(max(s1, s2))
                                                            except Exception:
                                                                return 0.0

                                                        try:
                                                            tgt = str(edge_target or "")
                                                            cand = []
                                                            for it in items:
                                                                ti, lab, x, y = it
                                                                sc = _score_edge_label(tgt, str(lab))
                                                                if sc >= float(sugg_thr):
                                                                    cand.append((sc, it))
                                                            cand.sort(key=lambda x: x[0], reverse=True)
                                                            cand = cand[: int(sugg_k)]
                                                            if not cand:
                                                                st.caption("Подсказки не найдены (попробуйте снизить порог или используйте фильтр/клик по схеме).")
                                                            else:
                                                                for j, (sc, it) in enumerate(cand):
                                                                    ti, lab, x, y = it
                                                                    c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
                                                                    c1.write(_fmt_item(it))
                                                                    c2.metric("score", f"{sc:.2f}")
                                                                    if c3.button("START", key=f"btn_sugg_start_{ti}_{j}"):
                                                                        st.session_state["svg_route_start_opt"] = _fmt_item(it)
                                                                    if c4.button("END", key=f"btn_sugg_end_{ti}_{j}"):
                                                                        st.session_state["svg_route_end_opt"] = _fmt_item(it)
                                                        except Exception as e:
                                                            st.warning(f"Не удалось построить подсказки: {e}")



                                                # --- AUTO pipeline: propose → find route → write mapping.edges → next (beta)
                                                with st.expander("AUTO: propose → route → mapping (beta)", expanded=False):
                                                    if not edge_cols:
                                                        st.info("Нет df_mdot веток (edge_cols пуст). Запустите детальный прогон с **record_full=True**.")
                                                    else:
                                                        edge_auto = str(st.session_state.get("svg_route_assign_edge", "") or "")
                                                        if not edge_auto:
                                                            st.warning("Сначала выберите целевую ветку в ассистенте выше (guided).")
                                                        else:
                                                            st.caption(f"Текущая целевая ветка: **{edge_auto}**")
                                                
                                                            # Параметры авто-подбора меток и записи
                                                            colAA1, colAA2 = st.columns(2)
                                                            with colAA1:
                                                                auto_strategy = st.selectbox(
                                                                    "Стратегия выбора START/END (из top-K по score)",
                                                                    options=[
                                                                        "Top2",
                                                                        "Best+Farthest",
                                                                        "FarthestPair",
                                                                    ],
                                                                    index=1,
                                                                    key="route_auto_strategy",
                                                                    help=(
                                                                        "Top2: берём 2 лучших по score. "
                                                                        "Best+Farthest: START=лучший, END=самый дальний из top-K. "
                                                                        "FarthestPair: выбираем самую далёкую пару из top-K."
                                                                    ),
                                                                )
                                                            with colAA2:
                                                                auto_write_mode = st.radio(
                                                                    "Режим записи (AUTO)",
                                                                    options=["Заменить", "Добавить сегмент"],
                                                                    horizontal=True,
                                                                    key="route_auto_write_mode",
                                                                )
                                                
                                                            colAB1, colAB2, colAB3, colAB4 = st.columns([1, 1, 1, 1])
                                                            with colAB1:
                                                                auto_thr = st.slider("Мин. score", 0.0, 1.0, float(st.session_state.get("route_label_sugg_thr", 0.55)), step=0.01, key="route_auto_thr")
                                                            with colAB2:
                                                                auto_k = st.slider("Top-K", 2, 80, int(st.session_state.get("route_label_sugg_k", 12)), step=1, key="route_auto_k")
                                                            with colAB3:
                                                                auto_simplify = st.slider("Simplify (RDP, px)", 0.0, 10.0, float(st.session_state.get("svg_route_simplify_eps", 1.0)), step=0.1, key="route_auto_simplify")
                                                            with colAB4:
                                                                auto_max_len = st.number_input("MaxLen (px, 0=∞)", min_value=0.0, max_value=30000.0, value=float(st.session_state.get("route_auto_max_len", 0.0)), step=50.0, key="route_auto_max_len")
                                                
                                                            colAC1, colAC2, colAC3 = st.columns([1.2, 1.2, 2.0])
                                                            with colAC1:
                                                                btn_auto_one = st.button("AUTO: текущая", key="btn_route_auto_one")
                                                            with colAC2:
                                                                batch_n = st.number_input("Batch N (неразм.)", min_value=1, max_value=50, value=10, step=1, key="route_auto_batch_n")
                                                                btn_auto_batch = st.button("AUTO: batch", key="btn_route_auto_batch")
                                                            with colAC3:
                                                                st.caption(
                                                                    "AUTO использует fuzzy-score по текстовым меткам SVG. "
                                                                    "Лучше работает, если предварительно нажать **«Автофильтр по имени ветки»** в guided-блоке."
                                                                )
                                                
                                                            # Локальные утилиты
                                                            def _latinize_sig_auto(s: str) -> str:
                                                                table = str.maketrans({
                                                                    "Л": "L", "П": "P", "З": "Z",
                                                                    "л": "l", "п": "p", "з": "z",
                                                                    "Р": "R", "р": "r",
                                                                    "В": "B", "в": "b",
                                                                    "А": "A", "а": "a",
                                                                    "Е": "E", "е": "e",
                                                                    "К": "K", "к": "k",
                                                                    "М": "M", "м": "m",
                                                                    "Н": "H", "н": "h",
                                                                    "О": "O", "о": "o",
                                                                    "С": "C", "с": "c",
                                                                    "Т": "T", "т": "t",
                                                                    "У": "Y", "у": "y",
                                                                    "Х": "X", "х": "x",
                                                                })
                                                                try:
                                                                    return str(s).translate(table)
                                                                except Exception:
                                                                    return str(s)
                                                
                                                            def _score_edge_label_auto(edge_name: str, label: str) -> float:
                                                                try:
                                                                    s1 = _name_score(edge_name, label)
                                                                    s2 = _name_score(_latinize_sig_auto(edge_name), _latinize_sig_auto(label))
                                                                    return float(max(s1, s2))
                                                                except Exception:
                                                                    return 0.0
                                                
                                                            def _choose_pair(cands, strategy: str):
                                                                if not cands or len(cands) < 2:
                                                                    return None
                                                                if strategy == "Top2":
                                                                    return cands[0], cands[1]
                                                                # best+farthest
                                                                if strategy == "Best+Farthest":
                                                                    best = cands[0]
                                                                    bx = float(best[1][2]); by = float(best[1][3])
                                                                    best_i = 1
                                                                    best_d = -1.0
                                                                    for i in range(1, len(cands)):
                                                                        it = cands[i]
                                                                        x = float(it[1][2]); y = float(it[1][3])
                                                                        d = (x - bx) ** 2 + (y - by) ** 2
                                                                        if d > best_d:
                                                                            best_d = d
                                                                            best_i = i
                                                                    return best, cands[best_i]
                                                                # farthest pair among topK
                                                                best_pair = (cands[0], cands[1])
                                                                best_d = -1.0
                                                                best_s = -1.0
                                                                for i in range(len(cands)):
                                                                    for j in range(i + 1, len(cands)):
                                                                        xi = float(cands[i][1][2]); yi = float(cands[i][1][3])
                                                                        xj = float(cands[j][1][2]); yj = float(cands[j][1][3])
                                                                        d = (xi - xj) ** 2 + (yi - yj) ** 2
                                                                        s = float(cands[i][0]) + float(cands[j][0])
                                                                        if d > best_d or (abs(d - best_d) < 1e-9 and s > best_s):
                                                                            best_d = d
                                                                            best_s = s
                                                                            best_pair = (cands[i], cands[j])
                                                                return best_pair
                                                
                                                            def _load_mapping_or_empty() -> Dict[str, Any]:
                                                                mtxt = str(st.session_state.get("svg_mapping_text", "") or "").strip()
                                                                if mtxt:
                                                                    try:
                                                                        m = json.loads(mtxt)
                                                                        if isinstance(m, dict):
                                                                            return m
                                                                    except Exception:
                                                                        pass
                                                                return {"version": 2, "viewBox": analysis.get("viewBox"), "edges": {}, "nodes": {}}
                                                
                                                            def _write_edge_route(mapping2: Dict[str, Any], edge_name: str, poly_xy: List[List[float]], mode: str, meta: Dict[str, Any]):
                                                                mapping2.setdefault("version", 2)
                                                                mapping2.setdefault("viewBox", analysis.get("viewBox"))
                                                                mapping2.setdefault("edges", {})
                                                                mapping2.setdefault("nodes", {})
                                                                if not isinstance(mapping2.get("edges"), dict):
                                                                    mapping2["edges"] = {}
                                                                if mode == "Добавить сегмент":
                                                                    segs = mapping2["edges"].get(edge_name, [])
                                                                    if not isinstance(segs, list):
                                                                        segs = []
                                                                    segs.append(poly_xy)
                                                                    mapping2["edges"][edge_name] = segs
                                                                else:
                                                                    mapping2["edges"][edge_name] = [poly_xy]
                                                
                                                                mapping2.setdefault("edges_meta", {})
                                                                if not isinstance(mapping2.get("edges_meta"), dict):
                                                                    mapping2["edges_meta"] = {}
                                                                try:
                                                                    existing = mapping2["edges_meta"].get(edge_name, {})
                                                                except Exception:
                                                                    existing = {}
                                                                if isinstance(existing, dict) and isinstance(meta, dict):
                                                                    merged = dict(existing)
                                                                    for k, v in meta.items():
                                                                        if isinstance(v, dict) and isinstance(merged.get(k), dict):
                                                                            tmpv = dict(merged.get(k, {}))
                                                                            tmpv.update(v)
                                                                            merged[k] = tmpv
                                                                        else:
                                                                            merged[k] = v
                                                                    mapping2["edges_meta"][edge_name] = merged
                                                                else:
                                                                    mapping2["edges_meta"][edge_name] = meta
                                                
                                                            # --- AUTO для одной ветки (используем items после фильтрации, чтобы значения гарантированно были в opts)
                                                            if btn_auto_one:
                                                                try:
                                                                    cands = []
                                                                    for it in items:
                                                                        ti, lab, x, y = it
                                                                        sc = _score_edge_label_auto(edge_auto, str(lab))
                                                                        if sc >= float(auto_thr):
                                                                            cands.append((float(sc), it))
                                                                    cands.sort(key=lambda x: x[0], reverse=True)
                                                                    cands = cands[: int(auto_k)]
                                                                    if len(cands) < 2:
                                                                        raise ValueError("Недостаточно кандидатов меток для AUTO. Попробуйте снизить порог или очистить фильтр.")
                                                
                                                                    pair = _choose_pair(cands, str(auto_strategy))
                                                                    if not pair:
                                                                        raise ValueError("Не удалось выбрать пару меток.")
                                                
                                                                    (sc_s, it_s), (sc_e, it_e) = pair
                                                                    st.session_state["svg_route_start_opt"] = _fmt_item(it_s)
                                                                    st.session_state["svg_route_end_opt"] = _fmt_item(it_e)
                                                                    st.session_state["svg_route_label_picks"] = {
                                                                        "start": {"ti": int(it_s[0]), "name": str(it_s[1]), "x": float(it_s[2]), "y": float(it_s[3])},
                                                                        "end": {"ti": int(it_e[0]), "name": str(it_e[1]), "x": float(it_e[2]), "y": float(it_e[3])},
                                                                    }
                                                
                                                                    p1 = (float(it_s[2]), float(it_s[3]))
                                                                    p2 = (float(it_e[2]), float(it_e[3]))
                                                                    route = shortest_path_between_points(
                                                                        nodes_coords=analysis.get("nodes", []),
                                                                        edges_ab=analysis.get("edges", []),
                                                                        p_start=p1,
                                                                        p_end=p2,
                                                                        snap_eps_px=0.25,
                                                                        simplify_epsilon=float(auto_simplify),
                                                                    )
                                                                    poly = route.get("path_xy", [])
                                                                    if not (isinstance(poly, list) and len(poly) >= 2):
                                                                        raise ValueError("AUTO: маршрут пустой или слишком короткий.")
                                                
                                                                    if float(auto_max_len) > 0 and float(route.get("length", 0.0) or 0.0) > float(auto_max_len):
                                                                        raise ValueError("AUTO: маршрут слишком длинный. Проверьте метки/фильтр.")
                                                
                                                                    mapping2 = _load_mapping_or_empty()
                                                                    meta = {
                                                                        "auto": True,
                                                                        "strategy": str(auto_strategy),
                                                                        "start": {"label": str(it_s[1]), "ti": int(it_s[0]), "score": float(sc_s), "x": float(it_s[2]), "y": float(it_s[3])},
                                                                        "end": {"label": str(it_e[1]), "ti": int(it_e[0]), "score": float(sc_e), "x": float(it_e[2]), "y": float(it_e[3])},
                                                                        "route": {"length_px": float(route.get("length", 0.0) or 0.0), "points": int(len(poly))},
                                                                        "ts": float(time.time()),
                                                                    }
                                                                    # --- quality + review status for AUTO (v7.21)
                                                                    try:
                                                                        q = evaluate_route_quality(
                                                                            poly,
                                                                            attach_start=route.get("attach_start") if isinstance(route, dict) else None,
                                                                            attach_end=route.get("attach_end") if isinstance(route, dict) else None,
                                                                            min_turn_deg=float(st.session_state.get("route_q_min_turn_deg", 45.0)),
                                                                            max_detour=float(st.session_state.get("route_q_max_detour", 8.0)),
                                                                            max_attach_dist=float(st.session_state.get("route_q_max_attach_dist", 35.0)),
                                                                        )
                                                                    except Exception:
                                                                        q = None
                                                                    try:
                                                                        meta["quality"] = q
                                                                    except Exception:
                                                                        pass
                                                                    try:
                                                                        if isinstance(q, dict) and str(q.get("grade", "")).upper() == "PASS":
                                                                            status_r = "approved"
                                                                        else:
                                                                            status_r = "pending"
                                                                    except Exception:
                                                                        status_r = "pending"
                                                                    meta["review"] = {"status": status_r, "by": "auto", "ts": float(time.time())}

                                                                    _write_edge_route(mapping2, edge_auto, poly, str(auto_write_mode), meta)
                                                                    mapping2.setdefault("meta", {})
                                                                    if isinstance(mapping2.get("meta"), dict):
                                                                        mapping2["meta"]["last_auto_route_assign"] = {"edge": edge_auto, "ts": float(time.time())}
                                                
                                                                    st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                                    st.session_state["svg_route_paths"] = [poly]
                                                                    st.session_state["svg_route_report"] = route
                                                
                                                                    st.success(
                                                                        f"AUTO OK: {edge_auto} ← '{it_s[1]}' → '{it_e[1]}' | "
                                                                        f"len≈{float(route.get('length', 0.0) or 0.0):.0f}px, pts={len(poly)}."
                                                                    )
                                                
                                                                    # авто-переход к следующей неразмеченной ветке (через request-key)
                                                                    if st.session_state.get("route_auto_next", True):
                                                                        try:
                                                                            _edges_map2 = mapping2.get("edges") if isinstance(mapping2, dict) else {}
                                                                            if not isinstance(_edges_map2, dict):
                                                                                _edges_map2 = {}
                                                                            _mapped2 = set(_edges_map2.keys())
                                                                            _unmapped2 = [e for e in edge_cols if e not in _mapped2]
                                                                            if _unmapped2:
                                                                                st.session_state["route_advance_to_unmapped"] = _unmapped2[0]
                                                                        except Exception:
                                                                            pass
                                                
                                                                    if st.session_state.get("route_clear_after_assign", False):
                                                                        try:
                                                                            st.session_state.pop("svg_route_paths", None)
                                                                            st.session_state.pop("svg_route_report", None)
                                                                        except Exception:
                                                                            pass
                                                                except Exception as e:
                                                                    st.error(f"AUTO: не удалось: {e}")
                                                
                                                            # --- AUTO batch: пройтись по N неразмеченным веткам (используем все тексты, игнорируя фильтр)
                                                            if btn_auto_batch:
                                                                try:
                                                                    mapping2 = _load_mapping_or_empty()
                                                                    _edges_map2 = mapping2.get("edges") if isinstance(mapping2, dict) else {}
                                                                    if not isinstance(_edges_map2, dict):
                                                                        _edges_map2 = {}
                                                                    _mapped2 = set(_edges_map2.keys())
                                                                    todo = [e for e in edge_cols if e not in _mapped2][: int(batch_n)]
                                                                    if not todo:
                                                                        st.info("AUTO batch: нет неразмеченных веток (или N=0).")
                                                                    else:
                                                                        items_all = []
                                                                        for ti, t in enumerate(texts):
                                                                            try:
                                                                                lab = str(t.get("text", "")).strip()
                                                                                if _is_noise_label(lab):
                                                                                    continue
                                                                                x = float(t.get("x", 0.0)); y = float(t.get("y", 0.0))
                                                                                items_all.append((int(ti), lab, x, y))
                                                                            except Exception:
                                                                                continue
                                                
                                                                        prog = st.progress(0.0)
                                                                        out_rows = []
                                                                        ok_cnt = 0
                                                                        for k_i, e_name in enumerate(todo):
                                                                            status = "fail"
                                                                            err = ""
                                                                            chosen = None
                                                                            try:
                                                                                cands = []
                                                                                for it in items_all:
                                                                                    ti, lab, x, y = it
                                                                                    sc = _score_edge_label_auto(str(e_name), str(lab))
                                                                                    if sc >= float(auto_thr):
                                                                                        cands.append((float(sc), it))
                                                                                cands.sort(key=lambda x: x[0], reverse=True)
                                                                                cands = cands[: int(auto_k)]
                                                                                if len(cands) < 2:
                                                                                    raise ValueError("not enough label candidates")
                                                                                pair = _choose_pair(cands, str(auto_strategy))
                                                                                if not pair:
                                                                                    raise ValueError("pair selection failed")
                                                                                (sc_s, it_s), (sc_e, it_e) = pair
                                                                                p1 = (float(it_s[2]), float(it_s[3]))
                                                                                p2 = (float(it_e[2]), float(it_e[3]))
                                                                                route = shortest_path_between_points(
                                                                                    nodes_coords=analysis.get("nodes", []),
                                                                                    edges_ab=analysis.get("edges", []),
                                                                                    p_start=p1,
                                                                                    p_end=p2,
                                                                                    snap_eps_px=0.25,
                                                                                    simplify_epsilon=float(auto_simplify),
                                                                                )
                                                                                poly = route.get("path_xy", [])
                                                                                if not (isinstance(poly, list) and len(poly) >= 2):
                                                                                    raise ValueError("empty route")
                                                                                if float(auto_max_len) > 0 and float(route.get("length", 0.0) or 0.0) > float(auto_max_len):
                                                                                    raise ValueError("route too long")
                                                
                                                                                meta = {
                                                                                    "auto_batch": True,
                                                                                    "strategy": str(auto_strategy),
                                                                                    "start": {"label": str(it_s[1]), "ti": int(it_s[0]), "score": float(sc_s), "x": float(it_s[2]), "y": float(it_s[3])},
                                                                                    "end": {"label": str(it_e[1]), "ti": int(it_e[0]), "score": float(sc_e), "x": float(it_e[2]), "y": float(it_e[3])},
                                                                                    "route": {"length_px": float(route.get("length", 0.0) or 0.0), "points": int(len(poly))},
                                                                                    "ts": float(time.time()),
                                                                                }
                                                                                # --- quality + review status for AUTO batch (v7.21)
                                                                                try:
                                                                                    q = evaluate_route_quality(
                                                                                        poly,
                                                                                        attach_start=route.get("attach_start") if isinstance(route, dict) else None,
                                                                                        attach_end=route.get("attach_end") if isinstance(route, dict) else None,
                                                                                        min_turn_deg=float(st.session_state.get("route_q_min_turn_deg", 45.0)),
                                                                                        max_detour=float(st.session_state.get("route_q_max_detour", 8.0)),
                                                                                        max_attach_dist=float(st.session_state.get("route_q_max_attach_dist", 35.0)),
                                                                                    )
                                                                                except Exception:
                                                                                    q = None
                                                                                try:
                                                                                    meta["quality"] = q
                                                                                except Exception:
                                                                                    pass
                                                                                try:
                                                                                    if isinstance(q, dict) and str(q.get("grade", "")).upper() == "PASS":
                                                                                        status_r = "approved"
                                                                                    else:
                                                                                        status_r = "pending"
                                                                                except Exception:
                                                                                    status_r = "pending"
                                                                                meta["review"] = {"status": status_r, "by": "auto_batch", "ts": float(time.time())}

                                                                                _write_edge_route(mapping2, str(e_name), poly, str(auto_write_mode), meta)
                                                                                status = "ok"
                                                                                ok_cnt += 1
                                                                                chosen = (it_s, it_e, float(sc_s), float(sc_e), float(route.get("length", 0.0) or 0.0), int(len(poly)))
                                                                            except Exception as ex:
                                                                                err = str(ex)
                                                
                                                                            if chosen:
                                                                                it_s, it_e, sc_s, sc_e, lpx, pts = chosen
                                                                                # quality summary (if any)
                                                                                try:
                                                                                    q_grade = str(q.get("grade", "")) if isinstance(q, dict) else ""
                                                                                    q_review = str(status_r) if isinstance(status_r, str) else ""
                                                                                    q_detour = q.get("detour_ratio") if isinstance(q, dict) else None
                                                                                except Exception:
                                                                                    q_grade = ""
                                                                                    q_review = ""
                                                                                    q_detour = None

                                                                                out_rows.append({
                                                                                    "edge": str(e_name),
                                                                                    "status": status,
                                                                                    "review_status": q_review,
                                                                                    "grade": q_grade,
                                                                                    "detour": q_detour,
                                                                                    "start": str(it_s[1]),
                                                                                    "end": str(it_e[1]),
                                                                                    "score_start": float(sc_s),
                                                                                    "score_end": float(sc_e),
                                                                                    "len_px": float(lpx),
                                                                                    "points": int(pts),
                                                                                    "error": err,
                                                                                })
                                                                            else:
                                                                                out_rows.append({"edge": str(e_name), "status": status, "review_status": "", "grade": "", "detour": None, "start": "", "end": "", "score_start": 0.0, "score_end": 0.0, "len_px": 0.0, "points": 0, "error": err})
                                                
                                                                            prog.progress((k_i + 1) / max(1, len(todo)))
                                                
                                                                        mapping2.setdefault("meta", {})
                                                                        if isinstance(mapping2.get("meta"), dict):
                                                                            mapping2["meta"]["auto_batch_last"] = {"ok": int(ok_cnt), "total": int(len(todo)), "ts": float(time.time())}
                                                
                                                                        st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                
                                                                        st.success(f"AUTO batch завершён: OK {ok_cnt}/{len(todo)}")
                                                                        try:
                                                                            df_auto = pd.DataFrame(out_rows)
                                                                            safe_dataframe(df_auto, height=260)
                                                                            st.download_button(
                                                                                "Скачать отчёт AUTO batch (csv)",
                                                                                data=df_auto.to_csv(index=False).encode("utf-8"),
                                                                                file_name="svg_auto_batch_report.csv",
                                                                                mime="text/csv",
                                                                            )
                                                                        except Exception:
                                                                            pass
                                                                except Exception as e:
                                                                    st.error(f"AUTO batch: не удалось: {e}")

                                                # --- Быстрый выбор старт/финиш меток кликом на SVG (без длинных списков)
                                                colP1, colP2 = st.columns(2)
                                                with colP1:
                                                    if st.button("Выбрать START кликом на схеме", key="btn_svg_pick_start_label"):
                                                        st.session_state["svg_label_pick_mode"] = "start"
                                                with colP2:
                                                    if st.button("Выбрать END кликом на схеме", key="btn_svg_pick_end_label"):
                                                        st.session_state["svg_label_pick_mode"] = "end"

                                                st.caption("Горячие клавиши: **Shift+клик** = START, **Ctrl/Cmd+клик** = END. Можно кликать рядом с подписью (поиск ближайшей метки).")
                                                st.slider("Радиус поиска ближайшей метки (px)", min_value=6, max_value=60, value=18, key="svg_label_pick_radius")


                                                pm = st.session_state.get("svg_label_pick_mode", "")
                                                if pm in ("start", "end"):
                                                    st.warning(f"Режим выбора метки: **{pm.upper()}**. Кликните по текстовой подписи на схеме (SVG справа).")

                                                # если компонент прислал клик по метке — применим как выбор start/end
                                                pending = st.session_state.get("svg_route_label_pick_pending")
                                                if isinstance(pending, dict):
                                                    try:
                                                        pmode = str(pending.get("mode", "")).strip().lower()
                                                        ti_p = pending.get("ti")
                                                        lx = float(pending.get("x", 0.0))
                                                        ly = float(pending.get("y", 0.0))
                                                        lname = str(pending.get("name", "")).strip()

                                                        # найдём соответствующий item (предпочитаем совпадение по ti)
                                                        picked = None
                                                        if isinstance(ti_p, int):
                                                            for it in items:
                                                                if int(it[0]) == int(ti_p):
                                                                    picked = it
                                                                    break
                                                        if picked is None and isinstance(lx, float) and isinstance(ly, float):
                                                            # fallback: ближайшая метка по координатам (и по имени, если есть)
                                                            best_d = 1e18
                                                            for it in items:
                                                                ti, lab, x, y = it
                                                                if lname and str(lab).strip().lower() != lname.lower():
                                                                    continue
                                                                d = (float(x) - lx) ** 2 + (float(y) - ly) ** 2
                                                                if d < best_d:
                                                                    best_d = d
                                                                    picked = it
                                                        if picked is not None:
                                                            picked_opt = _fmt_item(picked)
                                                            if picked_opt not in opts:
                                                                opts.append(picked_opt)
                                                                opt_to_idx[picked_opt] = int(picked[0])

                                                            if pmode == "start":
                                                                st.session_state["svg_route_start_opt"] = picked_opt
                                                            elif pmode == "end":
                                                                st.session_state["svg_route_end_opt"] = picked_opt

                                                            # сохраним для подсветки на SVG
                                                            picks = st.session_state.get("svg_route_label_picks")
                                                            picks = dict(picks) if isinstance(picks, dict) else {}
                                                            picks[pmode] = {"ti": int(picked[0]), "name": str(picked[1]), "x": float(picked[2]), "y": float(picked[3])}
                                                            st.session_state["svg_route_label_picks"] = picks
                                                    except Exception:
                                                        pass
                                                    # сбросим pending
                                                    try:
                                                        st.session_state.pop("svg_route_label_pick_pending", None)
                                                    except Exception:
                                                        pass

                                                colR1, colR2 = st.columns(2)
                                                with colR1:
                                                    start_opt = st.selectbox("Стартовая метка", opts, key="svg_route_start_opt")
                                                with colR2:
                                                    end_default = min(1, len(opts) - 1)
                                                    end_opt = st.selectbox("Конечная метка", opts, index=end_default, key="svg_route_end_opt")


                                                # --- Подсветка выбранных меток на SVG (START/END)
                                                try:
                                                    picks = {}
                                                    ti_s = opt_to_idx.get(start_opt)
                                                    ti_e = opt_to_idx.get(end_opt)
                                                    if isinstance(ti_s, int):
                                                        for it in items:
                                                            if int(it[0]) == int(ti_s):
                                                                picks["start"] = {"ti": int(it[0]), "name": str(it[1]), "x": float(it[2]), "y": float(it[3])}
                                                                break
                                                    if isinstance(ti_e, int):
                                                        for it in items:
                                                            if int(it[0]) == int(ti_e):
                                                                picks["end"] = {"ti": int(it[0]), "name": str(it[1]), "x": float(it[2]), "y": float(it[3])}
                                                                break
                                                    st.session_state["svg_route_label_picks"] = picks
                                                except Exception:
                                                    st.session_state["svg_route_label_picks"] = {}

                                                colB1, colB2, colB3 = st.columns(3)
                                                with colB1:
                                                    btn_find = st.button("Найти путь", key="btn_svg_route_find")
                                                with colB2:
                                                    btn_clear = st.button("Очистить путь", key="btn_svg_route_clear")
                                                with colB3:
                                                    simplify_eps = st.slider(
                                                        "Упростить маршрут (RDP epsilon, px)",
                                                        0.0, 10.0, 1.0,
                                                        step=0.1,
                                                        key="svg_route_simplify_eps",
                                                    )

                                                if btn_clear:
                                                    st.session_state.pop("svg_route_paths", None)
                                                    st.session_state.pop("svg_route_report", None)
                                                    st.success("Маршрут очищен.")

                                                if btn_find:
                                                    try:
                                                        si = opt_to_idx.get(start_opt, None)
                                                        ei = opt_to_idx.get(end_opt, None)
                                                        if si is None or ei is None:
                                                            raise ValueError("Не удалось распарсить индексы меток.")
                                                        p1 = (float(texts[si].get("x", 0.0)), float(texts[si].get("y", 0.0)))
                                                        p2 = (float(texts[ei].get("x", 0.0)), float(texts[ei].get("y", 0.0)))

                                                        route = shortest_path_between_points(
                                                            nodes_coords=analysis.get("nodes", []),
                                                            edges_ab=analysis.get("edges", []),
                                                            p_start=p1,
                                                            p_end=p2,
                                                            snap_eps_px=0.25,
                                                            simplify_epsilon=float(simplify_eps),
                                                        )
                                                        st.session_state["svg_route_paths"] = [route.get("path_xy", [])]
                                                        st.session_state["svg_route_report"] = route

                                                        st.success(
                                                            f"Путь найден: длина≈{route.get('length', 0.0):.1f}px, "
                                                            f"точек={len(route.get('path_xy', []))}."
                                                        )
                                                    except Exception as e:
                                                        st.session_state["svg_route_paths"] = []
                                                        st.session_state["svg_route_report"] = {"ok": False, "error": str(e)}
                                                        st.error(f"Не удалось найти путь: {e}")

                                                rep = st.session_state.get("svg_route_report")
                                                if isinstance(rep, dict) and rep:
                                                    with st.expander("Маршрут: детали", expanded=False):
                                                        st.write(
                                                            {
                                                                "ok": rep.get("ok"),
                                                                "length_px": rep.get("length"),
                                                                "node_count": rep.get("node_count"),
                                                                "attach_start": rep.get("attach_start"),
                                                                "attach_end": rep.get("attach_end"),
                                                                "params": rep.get("params"),
                                                            }
                                                        )
                                                        st.download_button(
                                                            "Скачать маршрут (json)",
                                                            data=json.dumps(rep, ensure_ascii=False, indent=2).encode("utf-8"),
                                                            file_name="svg_route.json",
                                                            mime="application/json",
                                                        )
                                                    # --- Route quality (beta)
                                                    try:
                                                        q_params = {
                                                            "min_turn_deg": float(st.session_state.get("route_q_min_turn_deg", 45.0)),
                                                            "max_detour": float(st.session_state.get("route_q_max_detour", 8.0)),
                                                            "max_attach_dist": float(st.session_state.get("route_q_max_attach_dist", 35.0)),
                                                        }
                                                    except Exception:
                                                        q_params = {"min_turn_deg": 45.0, "max_detour": 8.0, "max_attach_dist": 35.0}

                                                    with st.expander("Проверка качества маршрута (beta)", expanded=False):
                                                        colQ1, colQ2, colQ3 = st.columns(3)
                                                        with colQ1:
                                                            st.slider("Порог поворота (deg)", 20.0, 120.0, float(q_params["min_turn_deg"]), step=5.0, key="route_q_min_turn_deg")
                                                        with colQ2:
                                                            st.slider("Max detour", 2.0, 20.0, float(q_params["max_detour"]), step=0.5, key="route_q_max_detour")
                                                        with colQ3:
                                                            st.slider("Max dist метка→трубка (px)", 5.0, 120.0, float(q_params["max_attach_dist"]), step=5.0, key="route_q_max_attach_dist")

                                                        try:
                                                            q = evaluate_route_quality(
                                                                rep.get("path_xy", []) if isinstance(rep, dict) else [],
                                                                attach_start=rep.get("attach_start") if isinstance(rep, dict) else None,
                                                                attach_end=rep.get("attach_end") if isinstance(rep, dict) else None,
                                                                min_turn_deg=float(st.session_state.get("route_q_min_turn_deg", 45.0)),
                                                                max_detour=float(st.session_state.get("route_q_max_detour", 8.0)),
                                                                max_attach_dist=float(st.session_state.get("route_q_max_attach_dist", 35.0)),
                                                            )
                                                            st.session_state["svg_route_quality"] = q
                                                        except Exception as e:
                                                            q = {"grade": "FAIL", "reasons": [f"Не удалось оценить: {e}"]}

                                                        grade = str(q.get("grade", ""))
                                                        if grade == "PASS":
                                                            st.success("PASS: маршрут выглядит адекватно.")
                                                        elif grade == "FAIL":
                                                            st.error("FAIL: маршрут подозрительный (см. причины ниже).")
                                                        else:
                                                            st.warning("WARN: маршрут требует проверки.")

                                                        st.write(
                                                            {
                                                                "grade": q.get("grade"),
                                                                "length_px": q.get("length_px"),
                                                                "detour_ratio": q.get("detour_ratio"),
                                                                "points": q.get("points"),
                                                                "turns": q.get("turns"),
                                                                "self_intersections": q.get("self_intersections"),
                                                                "attach_start_dist": q.get("attach_start_dist"),
                                                                "attach_end_dist": q.get("attach_end_dist"),
                                                            }
                                                        )
                                                        if q.get("reasons"):
                                                            st.markdown("**Причины / предупреждения:**")
                                                            for r in q.get("reasons", []):
                                                                st.write(f"- {r}")
                                                        st.download_button(
                                                            "Скачать quality report (json)",
                                                            data=json.dumps(q, ensure_ascii=False, indent=2).encode("utf-8"),
                                                            file_name="svg_route_quality.json",
                                                            mime="application/json",
                                                        )

                                                    st.markdown("#### Привязать найденный путь к ветке модели (mapping.edges)")
                                                    route_paths = st.session_state.get("svg_route_paths", [])
                                                    if not (isinstance(route_paths, list) and route_paths and isinstance(route_paths[0], list) and len(route_paths[0]) >= 2):
                                                        st.info("Сначала нажмите **«Найти путь»** — затем можно записать маршрут в mapping.edges.")
                                                    else:
                                                        
                                                        # --- Целевая ветка выбирается в ассистенте выше (svg_route_assign_edge)
                                                        edge_target = str(st.session_state.get("svg_route_assign_edge", "") or "")
                                                        if not edge_target:
                                                            st.warning("Выберите целевую ветку в ассистенте выше (в этом же блоке).")
                                                        else:
                                                            st.caption(f"Целевая ветка: **{edge_target}**")

                                                        mode = st.radio(
                                                            "Режим записи",
                                                            options=["Заменить", "Добавить сегмент"],
                                                            horizontal=True,
                                                            key="svg_route_assign_mode",
                                                        )
                                                        colM1, colM2, colM3 = st.columns([1, 1, 2])
                                                        with colM1:
                                                            btn_assign = st.button("Записать маршрут", key="btn_svg_route_assign")
                                                        with colM2:
                                                            btn_clear_edge = st.button("Очистить ветку", key="btn_svg_route_clear_edge")
                                                        with colM3:
                                                            st.caption("Запись обновит текст в блоке **Анимация по схеме (mapping JSON)** ниже. Рекомендуется потом скачать mapping JSON файлом.")

                                                        if btn_assign or btn_clear_edge:
                                                            try:
                                                                mtxt = str(st.session_state.get("svg_mapping_text", "") or "").strip()
                                                                if mtxt:
                                                                    mapping2 = json.loads(mtxt)
                                                                    if not isinstance(mapping2, dict):
                                                                        raise ValueError("mapping JSON должен быть объектом (dict).")
                                                                else:
                                                                    mapping2 = {"version": 2, "viewBox": analysis.get("viewBox"), "edges": {}, "nodes": {}}

                                                                mapping2.setdefault("version", 2)
                                                                mapping2.setdefault("viewBox", analysis.get("viewBox"))
                                                                mapping2.setdefault("edges", {})
                                                                mapping2.setdefault("nodes", {})
                                                                if not isinstance(mapping2.get("edges"), dict):
                                                                    mapping2["edges"] = {}

                                                                if btn_clear_edge:
                                                                    mapping2["edges"].pop(edge_target, None)
                                                                    st.success(f"Очищено: mapping.edges['{edge_target}']")

                                                                if btn_assign:
                                                                    poly = route_paths[0]
                                                                    if mode == "Добавить сегмент":
                                                                        segs = mapping2["edges"].get(edge_target, [])
                                                                        if not isinstance(segs, list):
                                                                            segs = []
                                                                        segs.append(poly)
                                                                        mapping2["edges"][edge_target] = segs
                                                                    else:
                                                                        mapping2["edges"][edge_target] = [poly]

                                                                    mapping2.setdefault("meta", {})
                                                                    mapping2["meta"]["last_route_assign"] = {
                                                                        "edge": edge_target,
                                                                        "mode": mode,
                                                                        "route_length_px": float(rep.get("length", 0.0) or 0.0),
                                                                        "points": int(len(poly)),
                                                                        "ts": float(time.time()),
                                                                    }
                                                                    # --- route quality + review meta (v7.21)
                                                                    try:
                                                                        q_params = {
                                                                            "min_turn_deg": float(st.session_state.get("route_q_min_turn_deg", 45.0)),
                                                                            "max_detour": float(st.session_state.get("route_q_max_detour", 8.0)),
                                                                            "max_attach_dist": float(st.session_state.get("route_q_max_attach_dist", 35.0)),
                                                                        }
                                                                    except Exception:
                                                                        q_params = {"min_turn_deg": 45.0, "max_detour": 8.0, "max_attach_dist": 35.0}

                                                                    try:
                                                                        q = evaluate_route_quality(
                                                                            poly,
                                                                            attach_start=rep.get("attach_start") if isinstance(rep, dict) else None,
                                                                            attach_end=rep.get("attach_end") if isinstance(rep, dict) else None,
                                                                            min_turn_deg=float(q_params.get("min_turn_deg", 45.0)),
                                                                            max_detour=float(q_params.get("max_detour", 8.0)),
                                                                            max_attach_dist=float(q_params.get("max_attach_dist", 35.0)),
                                                                        )
                                                                        st.session_state["svg_route_quality"] = q
                                                                    except Exception:
                                                                        q = None

                                                                    try:
                                                                        mapping2.setdefault("edges_meta", {})
                                                                        if not isinstance(mapping2.get("edges_meta"), dict):
                                                                            mapping2["edges_meta"] = {}
                                                                        edge_meta_new = {
                                                                            "manual": True,
                                                                            "quality": q,
                                                                            "review": {"status": "approved", "by": "manual", "ts": float(time.time())},
                                                                            "route": {
                                                                                "length_px": float(rep.get("length", 0.0) or 0.0) if isinstance(rep, dict) else float(rep.get("length", 0.0) or 0.0) if isinstance(rep, dict) else 0.0,
                                                                                "points": int(len(poly)),
                                                                            },
                                                                            "start_end": st.session_state.get("svg_route_label_picks", {}),
                                                                        }
                                                                        existing = mapping2["edges_meta"].get(edge_target, {})
                                                                        if isinstance(existing, dict) and isinstance(edge_meta_new, dict):
                                                                            merged = dict(existing)
                                                                            for k, v in edge_meta_new.items():
                                                                                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                                                                                    tmpv = dict(merged.get(k, {}))
                                                                                    tmpv.update(v)
                                                                                    merged[k] = tmpv
                                                                                else:
                                                                                    merged[k] = v
                                                                            mapping2["edges_meta"][edge_target] = merged
                                                                        else:
                                                                            mapping2["edges_meta"][edge_target] = edge_meta_new
                                                                    except Exception:
                                                                        pass
                                                                    st.success(f"Маршрут записан в mapping.edges['{edge_target}'] ({mode}).")

                                                                st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                                # авто-переход к следующей неразмеченной ветке (через request-key, чтобы не трогать виджет напрямую)
                                                                if st.session_state.get("route_auto_next", True):
                                                                    try:
                                                                        _edges_map2 = mapping2.get("edges") if isinstance(mapping2, dict) else {}
                                                                        if not isinstance(_edges_map2, dict):
                                                                            _edges_map2 = {}
                                                                        _mapped2 = set(_edges_map2.keys())
                                                                        _unmapped2 = [e for e in edge_cols if e not in _mapped2]
                                                                        if _unmapped2:
                                                                            st.session_state["route_advance_to_unmapped"] = _unmapped2[0]
                                                                    except Exception:
                                                                        pass

                                                                # опционально: очистить маршрут после записи (чтобы не мешал следующей ветке)
                                                                if btn_assign and st.session_state.get("route_clear_after_assign", False):
                                                                    try:
                                                                        st.session_state.pop("svg_route_paths", None)
                                                                        st.session_state.pop("svg_route_report", None)
                                                                    except Exception:
                                                                        pass

                                                            except Exception as e:
                                                                st.error(f"Не удалось обновить mapping JSON: {e}")


                                with st.expander("Разметка веток (edges)", expanded=False):
                                    st.info(
                                        "Инструмент ниже создаёт mapping.edges локально в браузере. "
                                        "Нажмите Download/Copy и потом загрузите JSON обратно в блоке анимации. "
                                        "Если в JSON уже есть mapping.nodes — они сохранятся."
                                    )
                                    render_svg_edge_mapper_html(svg_inline=svg_inline, edge_names=edge_cols, height=760)

                                with st.expander("Разметка узлов давления (nodes)", expanded=False):
                                    st.info(
                                        "Инструмент ниже размечает mapping.nodes (координаты узлов давления). "
                                        "Можно вставить сюда JSON после разметки веток и дополнить узлами."
                                    )
                                    node_names_for_mapper = pick_nodes_svg if pick_nodes_svg else (node_cols[: min(20, len(node_cols))] if node_cols else [])
                                    render_svg_node_mapper_html(svg_inline=svg_inline, node_names=node_names_for_mapper, edge_names=edge_cols, height=760)

                                # --- загрузка mapping JSON
                                st.markdown("### Анимация по схеме (по mapping JSON)")

                                # Показываем, откуда взят mapping сейчас
                                cur_map_src = st.session_state.get("svg_mapping_source", "(не задан)")
                                st.caption(f"Источник mapping: {cur_map_src}")

                                colMAP1, colMAP2 = st.columns([1.0, 1.0], gap="medium")
                                with colMAP1:
                                    if st.button("Сбросить mapping к default", key="svg_mapping_reset_default", help="Загрузить default_svg_mapping.json из пакета приложения."):
                                        try:
                                            st.session_state["svg_mapping_text"] = DEFAULT_SVG_MAPPING_PATH.read_text(encoding="utf-8")
                                            st.session_state["svg_mapping_source"] = str(DEFAULT_SVG_MAPPING_PATH)
                                            log_event("svg_mapping_reset_default", path=str(DEFAULT_SVG_MAPPING_PATH))
                                            do_rerun()
                                        except Exception as e:
                                            st.error(f"Не удалось загрузить default mapping: {e}")
                                            log_event("svg_mapping_reset_default_failed", error=repr(e))
                                with colMAP2:
                                    # Удобный быстрый экспорт текущего mapping из textarea
                                    try:
                                        _cur_bytes = (st.session_state.get("svg_mapping_text", "") or "").encode("utf-8")
                                        st.download_button(
                                            "Скачать текущий mapping.json",
                                            data=_cur_bytes,
                                            file_name="mapping.json",
                                            mime="application/json",
                                            help="Скачивает содержимое mapping из текстового поля (как сейчас в UI).",
                                        )
                                    except Exception:
                                        pass

                                map_upl = st.file_uploader("Загрузить mapping JSON", type=["json"], key="svg_mapping_upl")

                                map_text = st.text_area(
                                    "…или вставьте mapping JSON сюда (если вы нажали Copy в разметчике)",
                                    value=st.session_state.get("svg_mapping_text", ""),
                                    height=160,
                                )
                                mapping = None
                                if map_upl is not None:
                                    try:
                                        mapping = json.loads(map_upl.getvalue().decode("utf-8"))
                                        st.session_state["svg_mapping_text"] = json.dumps(mapping, ensure_ascii=False, indent=2)
                                        st.session_state["svg_mapping_source"] = f"uploaded:{getattr(map_upl, 'name', '')}".strip(":")
                                        log_event("svg_mapping_uploaded", name=getattr(map_upl, "name", ""), bytes=len(map_upl.getvalue()))
                                    except Exception as e:
                                        st.error(f"Не удалось прочитать mapping JSON: {e}")
                                        log_event("svg_mapping_upload_failed", error=repr(e))
                                elif map_text.strip():
                                    try:
                                        mapping = json.loads(map_text)
                                        # Если пользователь правит руками (textarea), считаем это источником
                                        if st.session_state.get("svg_mapping_source", "").startswith("uploaded") is False:
                                            st.session_state["svg_mapping_source"] = "textarea"
                                    except Exception as e:
                                        st.error(f"JSON не парсится: {e}")
                                        log_event("svg_mapping_text_parse_failed", error=repr(e))

                                if not mapping:
                                    st.warning("Нужен mapping JSON. Создайте его в разметчиках выше или загрузите файл.")
                                else:
                                    # --- Review / Quality: mapping.edges_meta (approve/reject) (v7.21)
                                    with st.expander("Review / Quality: mapping.edges_meta (approve/reject)", expanded=False):
                                        mapping2 = copy.deepcopy(mapping) if isinstance(mapping, dict) else {}
                                        if not isinstance(mapping2, dict):
                                            mapping2 = {}
                                        mapping2.setdefault("version", 2)
                                        mapping2.setdefault("edges", {})
                                        mapping2.setdefault("nodes", {})
                                        mapping2.setdefault("edges_meta", {})
                                        if not isinstance(mapping2.get("edges"), dict):
                                            mapping2["edges"] = {}
                                        if not isinstance(mapping2.get("edges_meta"), dict):
                                            mapping2["edges_meta"] = {}

                                        edges_meta = mapping2.get("edges_meta", {})
                                        edges_geo = mapping2.get("edges", {})

                                        def _first_poly(edge_name: str):
                                            try:
                                                segs = edges_geo.get(edge_name, None)
                                                if isinstance(segs, list) and segs:
                                                    poly0 = segs[0]
                                                    if isinstance(poly0, list) and len(poly0) >= 2:
                                                        return poly0
                                            except Exception:
                                                pass
                                            return None

                                        colRQ1, colRQ2, colRQ3 = st.columns([1.2, 1.2, 2.0])
                                        with colRQ1:
                                            btn_recompute_q = st.button("Recompute quality (all)", key="btn_map_recompute_quality")
                                        with colRQ2:
                                            btn_approve_pass = st.button("Approve all PASS", key="btn_map_approve_pass")
                                        with colRQ3:
                                            st.caption("Quality хранится в edges_meta[edge].quality; статусы — в edges_meta[edge].review.status.")

                                        if btn_recompute_q:
                                            try:
                                                for e_name, segs in list(edges_geo.items()):
                                                    poly = _first_poly(str(e_name))
                                                    if not poly:
                                                        continue
                                                    q = evaluate_route_quality(
                                                        poly,
                                                        attach_start=None,
                                                        attach_end=None,
                                                        min_turn_deg=float(st.session_state.get("route_q_min_turn_deg", 45.0)),
                                                        max_detour=float(st.session_state.get("route_q_max_detour", 8.0)),
                                                        max_attach_dist=float(st.session_state.get("route_q_max_attach_dist", 35.0)),
                                                    )
                                                    em = edges_meta.get(str(e_name), {})
                                                    if not isinstance(em, dict):
                                                        em = {}
                                                    em["quality"] = q
                                                    em.setdefault("review", {})
                                                    if isinstance(em.get("review"), dict):
                                                        em["review"].setdefault("status", "pending")
                                                        em["review"].setdefault("by", "quality_recompute")
                                                        em["review"]["ts"] = float(time.time())
                                                    edges_meta[str(e_name)] = em
                                                mapping2["edges_meta"] = edges_meta
                                                st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                st.success("Quality пересчитан и сохранён в mapping JSON (text area ниже обновится после rerun).")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Не удалось пересчитать quality: {e}")

                                        if btn_approve_pass:
                                            try:
                                                n_ok = 0
                                                for e_name, em in list(edges_meta.items()):
                                                    if not isinstance(em, dict):
                                                        continue
                                                    q = em.get("quality")
                                                    if isinstance(q, dict) and str(q.get("grade", "")).upper() == "PASS":
                                                        em.setdefault("review", {})
                                                        if isinstance(em.get("review"), dict):
                                                            em["review"]["status"] = "approved"
                                                            em["review"]["by"] = "approve_pass"
                                                            em["review"]["ts"] = float(time.time())
                                                            n_ok += 1
                                                        edges_meta[str(e_name)] = em
                                                mapping2["edges_meta"] = edges_meta
                                                st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                st.success(f"Approved PASS: {n_ok}")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Approve PASS: ошибка: {e}")

                                        # table
                                        rows = []
                                        try:
                                            # show only edges from model if present, else from mapping
                                            edges_list = edge_cols if edge_cols else list(edges_geo.keys())
                                        except Exception:
                                            edges_list = list(edges_geo.keys())

                                        for e in edges_list:
                                            e = str(e)
                                            poly = _first_poly(e)
                                            em = edges_meta.get(e, {})
                                            if not isinstance(em, dict):
                                                em = {}
                                            rv = em.get("review", {})
                                            if not isinstance(rv, dict):
                                                rv = {}
                                            stt = str(rv.get("status", "")) if rv else ""
                                            q = em.get("quality", {})
                                            if not isinstance(q, dict):
                                                q = {}
                                            rows.append({
                                                "edge": e,
                                                "has_geom": bool(poly),
                                                "status": stt,
                                                "grade": q.get("grade", ""),
                                                "len_px": q.get("length_px", None),
                                                "detour": q.get("detour_ratio", None),
                                                "points": q.get("points", None),
                                            })

                                        df_rev = pd.DataFrame(rows)
                                        if len(df_rev) == 0:
                                            st.info("Нет данных для review.")
                                        else:
                                            colF1, colF2 = st.columns([1.2, 2.0])
                                            with colF1:
                                                status_filter = st.multiselect(
                                                    "Фильтр по status",
                                                    options=sorted([s for s in df_rev["status"].unique().tolist() if s != ""]),
                                                    default=[],
                                                    key="map_review_status_filter",
                                                )
                                            with colF2:
                                                grade_filter = st.multiselect(
                                                    "Фильтр по grade",
                                                    options=sorted([s for s in df_rev["grade"].unique().tolist() if s != ""]),
                                                    default=[],
                                                    key="map_review_grade_filter",
                                                )

                                            df_show = df_rev.copy()
                                            if status_filter:
                                                df_show = df_show[df_show["status"].isin(status_filter)]
                                            if grade_filter:
                                                df_show = df_show[df_show["grade"].isin(grade_filter)]

                                            safe_dataframe(df_show.sort_values(["has_geom", "status", "grade", "edge"], ascending=[False, True, True, True]), height=280)
                                            st.download_button(
                                                "Скачать review table (csv)",
                                                data=df_show.to_csv(index=False).encode("utf-8"),
                                                file_name="mapping_review_table.csv",
                                                mime="text/csv",
                                            )

                                        st.markdown("#### Изменить статус / заметку для одной ветки")
                                        edge_sel = ""
                                        if rows:
                                            edge_sel = st.selectbox(
                                                "Edge",
                                                options=[r["edge"] for r in rows],
                                                index=0,
                                                key="map_review_edge_select",
                                            )
                                        else:
                                            st.info("Нет веток для выбора (rows пуст).")

                                        if edge_sel:
                                            em = edges_meta.get(str(edge_sel), {})
                                            if not isinstance(em, dict):
                                                em = {}
                                            rv = em.get("review", {})
                                            if not isinstance(rv, dict):
                                                rv = {}
                                            cur_status = str(rv.get("status", "pending") or "pending")
                                            note = str(rv.get("note", "") or "")
                                            colE1, colE2 = st.columns([1.0, 2.0])
                                            with colE1:
                                                new_status = st.radio(
                                                    "status",
                                                    options=["approved", "pending", "rejected"],
                                                    index=["approved", "pending", "rejected"].index(cur_status) if cur_status in ["approved", "pending", "rejected"] else 1,
                                                    horizontal=True,
                                                    key="map_review_status_set",
                                                )
                                            with colE2:
                                                new_note = st.text_input("note", value=note, key="map_review_note_set")

                                            colA1, colA2, colA3 = st.columns([1.2, 1.2, 2.0])
                                            with colA1:
                                                btn_save_status = st.button("Save review", key="btn_map_review_save")
                                            with colA2:
                                                btn_clear_geom = st.button("Clear geometry", key="btn_map_review_clear_geom")
                                            with colA3:
                                                st.caption("Clear geometry удаляет mapping.edges[edge], но оставляет edges_meta (для истории).")

                                            if btn_save_status:
                                                try:
                                                    em.setdefault("review", {})
                                                    if not isinstance(em.get("review"), dict):
                                                        em["review"] = {}
                                                    em["review"]["status"] = str(new_status)
                                                    em["review"]["note"] = str(new_note)
                                                    em["review"]["by"] = "user"
                                                    em["review"]["ts"] = float(time.time())
                                                    edges_meta[str(edge_sel)] = em
                                                    mapping2["edges_meta"] = edges_meta
                                                    st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                    st.success("Review сохранён.")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Save review: ошибка: {e}")

                                            if btn_clear_geom:
                                                try:
                                                    if isinstance(mapping2.get("edges"), dict):
                                                        mapping2["edges"].pop(str(edge_sel), None)
                                                    em.setdefault("review", {})
                                                    if not isinstance(em.get("review"), dict):
                                                        em["review"] = {}
                                                    em["review"]["status"] = "rejected"
                                                    em["review"]["by"] = "clear_geom"
                                                    em["review"]["ts"] = float(time.time())
                                                    edges_meta[str(edge_sel)] = em
                                                    mapping2["edges_meta"] = edges_meta
                                                    st.session_state["svg_mapping_text"] = json.dumps(mapping2, ensure_ascii=False, indent=2)
                                                    st.success("Геометрия удалена (и помечено rejected).")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Clear geometry: ошибка: {e}")

                                    # Optional: filter by review status (approved only)
                                    approved_only = st.checkbox(
                                        "Только APPROVED (review.status=approved)",
                                        value=False,
                                        key="svg_only_approved_edges",
                                    )
                                    edge_options_anim = edge_cols
                                    try:
                                        if approved_only and isinstance(mapping, dict):
                                            emap = mapping.get("edges_meta", {})
                                            if isinstance(emap, dict):
                                                edge_options_anim = []
                                                for e in edge_cols:
                                                    meta_e = emap.get(str(e), {})
                                                    if not isinstance(meta_e, dict):
                                                        continue
                                                    rv = meta_e.get("review", {})
                                                    if not isinstance(rv, dict):
                                                        continue
                                                    if str(rv.get("status", "")) == "approved":
                                                        edge_options_anim.append(str(e))
                                                if not edge_options_anim:
                                                    edge_options_anim = edge_cols
                                    except Exception:
                                        edge_options_anim = edge_cols

                                    defaults_svg = [c for c in edge_options_anim if ("Ресивер3" in c or "выхлоп" in c or "предохран" in c)][:6]
                                    if not defaults_svg:
                                        defaults_svg = edge_options_anim[: min(6, len(edge_options_anim))]
                                    pick_edges_svg = st.multiselect(
                                        "Ветки для анимации на схеме",
                                        options=edge_options_anim,
                                        default=defaults_svg,
                                        key="anim_edges_svg",
                                    )

                                    auto_match = st.checkbox(
                                        "Автосопоставление имён (fuzzy) — если mapping делался под другую версию модели",
                                        value=True,
                                        key="svg_auto_match_names",
                                    )
                                    min_score = st.slider(
                                        "Порог совпадения имён",
                                        min_value=0.50,
                                        max_value=0.95,
                                        value=0.70,
                                        step=0.01,
                                        key="svg_auto_match_threshold",
                                    )

                                    if len(pick_edges_svg) == 0:
                                        st.info("Выберите хотя бы одну ветку.")
                                    else:
                                        mapping_use = mapping
                                        report = {"edges": [], "nodes": []}
                                        if auto_match:
                                            mapping_use, report = ensure_mapping_for_selection(
                                                mapping=mapping,
                                                need_edges=pick_edges_svg,
                                                need_nodes=pick_nodes_svg,
                                                min_score=float(min_score),
                                            )

                                            if report.get("edges") or report.get("nodes"):
                                                with st.expander("Отчёт автосопоставления", expanded=False):
                                                    if report.get("edges"):
                                                        st.markdown("**Ветки (edges)**")
                                                        safe_dataframe(
                                                            pd.DataFrame(report["edges"]).sort_values("score", ascending=False),
                                                            height=220,
                                                        )
                                                    if report.get("nodes"):
                                                        st.markdown("**Узлы (nodes)**")
                                                        safe_dataframe(
                                                            pd.DataFrame(report["nodes"]).sort_values("score", ascending=False),
                                                            height=220,
                                                        )

                                        # конверсия в Нл/мин
                                        try:
                                            rho_N = float(P_ATM) / (float(getattr(model_mod, "R_AIR", 287.0)) * float(getattr(model_mod, "T_AIR", 293.15)))
                                            scale = 1000.0 * 60.0 / rho_N
                                            unit = "Нл/мин"
                                        except Exception:
                                            scale = 1.0
                                            unit = "кг/с"

                                        time_s = df_mdot["время_с"].astype(float).tolist()
                                        edge_series = []
                                        missing = []
                                        for c in pick_edges_svg:
                                            q = (df_mdot[c].astype(float).to_numpy() * scale).tolist()
                                            if df_open is not None and c in df_open.columns:
                                                op = df_open[c].astype(int).tolist()
                                            else:
                                                op = None
                                            edge_series.append({"name": c, "q": q, "open": op, "unit": unit})

                                            try:
                                                if not mapping_use.get("edges", {}).get(c):
                                                    missing.append(c)
                                            except Exception:
                                                pass
                                        if missing:
                                            st.warning("Для некоторых веток нет геометрии в mapping.edges: " + ", ".join(missing[:20]))

                                        # --- Узлы давления (если выбраны) + проверка координат
                                        node_series = []
                                        missing_nodes = []
                                        if df_p is not None and pick_nodes_svg:
                                            try:
                                                t_target = np.array(time_s, dtype=float)
                                                t_src = df_p["время_с"].astype(float).to_numpy()
                                            except Exception:
                                                t_target = None
                                                t_src = None

                                            for nn in pick_nodes_svg:
                                                if nn not in df_p.columns:
                                                    continue
                                                p_src = df_p[nn].astype(float).to_numpy()
                                                p_g = (p_src - P_ATM) / BAR_PA
                                                if t_target is not None and t_src is not None and len(t_src) >= 2 and len(t_target) >= 2:
                                                    if len(t_src) != len(t_target) or (abs(float(t_src[0]) - float(t_target[0])) > 1e-9) or (abs(float(t_src[-1]) - float(t_target[-1])) > 1e-9):
                                                        try:
                                                            p_g = np.interp(t_target, t_src, p_g)
                                                        except Exception:
                                                            p_g = p_g[: len(t_target)]
                                                else:
                                                    p_g = p_g[: len(time_s)]

                                                node_series.append({"name": nn, "p": p_g.tolist(), "unit": "бар (изб.)"})

                                                try:
                                                    xy = mapping_use.get("nodes", {}).get(nn)
                                                    if not (isinstance(xy, list) and len(xy) >= 2):
                                                        missing_nodes.append(nn)
                                                except Exception:
                                                    pass

                                        if missing_nodes:
                                            st.warning("Для некоторых узлов нет координат в mapping.nodes: " + ", ".join(missing_nodes[:20]))


                                        # Review overlay controls (v7.22)
                                        colOV1, colOV2, colOV3 = st.columns([1.2, 1.2, 2.2])
                                        with colOV1:
                                            st.checkbox(
                                                "Показать review overlay",
                                                value=True,
                                                key="svg_show_review_overlay",
                                                help="Раскраска mapping.edges по edges_meta.review.status поверх SVG.",
                                            )
                                        with colOV2:
                                            st.checkbox(
                                                "Review hotkeys",
                                                value=False,
                                                key="svg_review_pick_mode",
                                                help="Включает горячие клики по линиям overlay: Shift=approved, Ctrl/Cmd=rejected, Alt=pending.",
                                            )
                                        with colOV3:
                                            st.multiselect(
                                                "Показывать статусы",
                                                options=["approved", "pending", "rejected", "unknown"],
                                                default=["approved", "pending", "rejected"],
                                                key="svg_review_statuses",
                                            )

                                        with colOV3:
                                            st.checkbox(
                                                "HUD на схеме",
                                                value=True,
                                                key="svg_review_hud",
                                                help="Показывает небольшую панель статистики review прямо поверх SVG (с кнопками Next/Prev pending).",
                                            )

                                        with st.expander("Review conveyor (pending-first)", expanded=False):
                                            mapping_text = st.session_state.get("svg_mapping_text", "")
                                            mobj = None
                                            try:
                                                if isinstance(mapping_text, str) and mapping_text.strip():
                                                    mobj = json.loads(mapping_text)
                                            except Exception:
                                                mobj = None

                                            # counts
                                            cnt = {"approved":0, "pending":0, "rejected":0, "unknown":0, "total":0}
                                            pending_list = []
                                            try:
                                                if isinstance(mobj, dict):
                                                    edges_geo = mobj.get("edges", {})
                                                    emap = mobj.get("edges_meta", {})
                                                    if not isinstance(edges_geo, dict):
                                                        edges_geo = {}
                                                    if not isinstance(emap, dict):
                                                        emap = {}
                                                    for e_name, segs in edges_geo.items():
                                                        if not isinstance(segs, list) or not segs:
                                                            continue
                                                        stt = "unknown"
                                                        try:
                                                            meta = emap.get(str(e_name), {})
                                                            rv = meta.get("review", {}) if isinstance(meta, dict) else {}
                                                            stt2 = rv.get("status", "") if isinstance(rv, dict) else ""
                                                            stt = str(stt2) if stt2 else "unknown"
                                                        except Exception:
                                                            stt = "unknown"
                                                        cnt["total"] += 1
                                                        if stt in cnt:
                                                            cnt[stt] += 1
                                                        else:
                                                            cnt["unknown"] += 1
                                                        if stt in ("pending", "unknown", ""):
                                                            pending_list.append(str(e_name))
                                            except Exception:
                                                pass
                                            pending_list = sorted(set(pending_list))

                                            c1, c2, c3, c4, c5 = st.columns(5)
                                            c1.metric("approved", cnt["approved"])
                                            c2.metric("pending", cnt["pending"])
                                            c3.metric("rejected", cnt["rejected"])
                                            c4.metric("unknown", cnt["unknown"])
                                            c5.metric("total", cnt["total"])

                                            st.checkbox(
                                                "Auto-advance после approve/reject",
                                                value=True,
                                                key="svg_review_auto_advance",
                                                help="После Shift/Ctrl-клика по линии overlay автоматически выбирается следующая pending/unknown ветка.",
                                            )

                                            colN1, colN2, colN3 = st.columns([1.2, 1.2, 2.4])
                                            with colN1:
                                                if st.button("◀ Prev pending", key="btn_prev_pending"):
                                                    if pending_list:
                                                        cur = str(st.session_state.get("svg_selected_edge") or "")
                                                        i = pending_list.index(cur) if cur in pending_list else 0
                                                        j = (i - 1) if i > 0 else (len(pending_list)-1)
                                                        st.session_state["svg_selected_edge"] = pending_list[j]
                                                        st.session_state["svg_selected_node"] = ""
                                                        st.rerun()
                                            with colN2:
                                                if st.button("Next pending ▶", key="btn_next_pending"):
                                                    if pending_list:
                                                        cur = str(st.session_state.get("svg_selected_edge") or "")
                                                        i = pending_list.index(cur) if cur in pending_list else -1
                                                        j = (i + 1) if (i + 1) < len(pending_list) else 0
                                                        st.session_state["svg_selected_edge"] = pending_list[j]
                                                        st.session_state["svg_selected_node"] = ""
                                                        st.rerun()
                                            with colN3:
                                                if pending_list:
                                                    st.caption(f"pending/unknown: {len(pending_list)} | текущая: {st.session_state.get('svg_selected_edge')}")
                                                else:
                                                    st.caption("pending/unknown: 0")


                                        last_rv = st.session_state.get("svg_review_last")
                                        if isinstance(last_rv, dict) and last_rv.get("edge"):
                                            st.caption(f"Последнее review: {last_rv.get('edge')} → {last_rv.get('status')}")

                                        comp = get_pneumo_svg_flow_component()
                                        selected = {
                                            "edge": st.session_state.get("svg_selected_edge"),
                                            "node": st.session_state.get("svg_selected_node"),
                                        }
                                        if comp is not None:
                                            _evt = comp(
                                                title="Анимация по схеме (SVG)",
                                                svg=svg_inline,
                                                mapping=mapping_use,
                                                show_review_overlay=bool(st.session_state.get('svg_show_review_overlay', True)),
                                                review_pick_mode=bool(st.session_state.get('svg_review_pick_mode', False)),
                                                review_statuses=st.session_state.get('svg_review_statuses', ['approved','pending','rejected']),
                                                review_hud=bool(st.session_state.get('svg_review_hud', True)),
                                                route_paths=st.session_state.get("svg_route_paths", []),
                                                label_pick_mode=st.session_state.get("svg_label_pick_mode", ""),
                                                label_picks=st.session_state.get("svg_route_label_picks", {}),
                                                label_pick_radius=st.session_state.get("svg_label_pick_radius", 18),
                                                time=time_s,
                                                edges=edge_series,
                                                nodes=node_series,
                                                selected=selected,
                                                sync_playhead=True,
                                                playhead_storage_key="pneumo_play_state",
                                                dataset_id=dataset_id_ui,
                                                height=760,
                                                key="svg_pick_event",
                                                default=None,
                                            )
                                            st.caption("Клик по ветке/узлу на схеме добавляет/заменяет выбор в графиках (см. переключатель выше).")
                                        else:
                                            render_svg_flow_animation_html(
                                                svg_inline=svg_inline,
                                                mapping=mapping_use,
                                                time_s=time_s,
                                                edge_series=edge_series,
                                                node_series=node_series,
                                                height=760,
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
            st.error("autoselfcheck: FAIL. Оптимизация по умолчанию заблокирована, чтобы не получать мусорные результаты.")
            _allow_unsafe_opt = st.checkbox(
                "Разрешить оптимизацию несмотря на FAIL",
                value=False,
                key="allow_unsafe_opt",
                help="Иногда полезно для отладки, но результаты могут быть некорректны. Лучше сначала исправить ошибки selfcheck.",
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
                        st.caption(f"Прогресс-файл обновлён {_age:.1f} с назад: {progress_path}")
                        # Если процесс жив, а файл давно не обновлялся — вероятно завис/упал или пишет в другой каталог.
                        if pid_alive(st.session_state.opt_proc) and (_age > max(300.0, 10.0*float(refresh_sec) + 5.0)):
                            st.caption("⚠️ Прогресс-файл давно не обновлялся. Если это неожиданно — проверьте, что worker пишет progress.json в тот же каталог и что расчёт не завис.")
                    except Exception:
                        pass

                    лимит_мин = float(prog.get("лимит_минут", 0.0) or 0.0)
                    прошло_сек = float(prog.get("прошло_сек", 0.0) or 0.0)
                    ts_start = prog.get("ts_start", None)
                    try:
                        if ts_start is not None:
                            прошло_сек_live = max(прошло_сек, time.time() - float(ts_start))
                        else:
                            прошло_сек_live = прошло_сек
                    except Exception:
                        прошло_сек_live = прошло_сек
                    статус = str(prog.get("статус", "") or "")
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
                        готово = int(staged_summary.get("total_rows_live", 0) or 0)
                        готово_в_файле = int(staged_summary.get("total_rows_live", готово) or готово)
                        stage_rows_current = int(staged_summary.get("stage_rows_current", 0) or 0)
                        stage_rows_done_before = int(staged_summary.get("stage_rows_done_before", 0) or 0)
                        worker_done_current = int(staged_summary.get("worker_done_current", stage_rows_current) or stage_rows_current)
                        worker_written_current = int(staged_summary.get("worker_written_current", worker_done_current) or worker_done_current)
                        stage_elapsed_sec = staged_summary.get("stage_elapsed_sec", None)
                        stage_budget_sec = staged_summary.get("stage_budget_sec", None)

                        st.write(f"Стадия: **{stage_name}** (idx={stage_idx}, 0-based; всего стадий: {max(1, stage_total)})")
                        st.caption(describe_runtime_stage(stage_name))
                        st.write(f"Готово (суммарно): {готово}  |  Записано в файл: {готово_в_файле}")
                        st.write(f"Текущая стадия: rows в CSV = **{stage_rows_current}**  |  по progress worker = {worker_done_current}/{worker_written_current}")
                        if stage_rows_done_before > 0:
                            st.caption(f"Завершённые предыдущие стадии уже дали строк: {stage_rows_done_before}")
                        if stage_budget_sec is not None and float(stage_budget_sec) > 0:
                            frac_stage = max(0.0, min(1.0, float(stage_elapsed_sec or 0.0) / float(stage_budget_sec)))
                            st.progress(frac_stage, text=f"Прогресс текущей стадии по времени: {frac_stage*100:.1f}% (статус: {статус})")
                        elif лимит_мин > 0:
                            frac_t = max(0.0, min(1.0, прошло_сек_live / (лимит_мин * 60.0)))
                            st.progress(frac_t, text=f"Прогресс по времени: {frac_t*100:.1f}% (статус: {статус})")
                        if bool(staged_summary.get("worker_progress_stale", False)):
                            st.caption("⚠️ Вложенный progress.json отстаёт от live CSV текущей стадии; UI показывает производные счётчики по фактическим строкам stage CSV.")
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
                            st.markdown("**Seed/promotion policy (текущая стадия)**")
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
                        готово = int(prog.get("готово_кандидатов", 0) or 0)
                        готово_в_файле = int(prog.get("готово_кандидатов_в_файле", готово) or 0)
                        st.write(f"Готово (посчитано): {готово}  |  Записано в файл: {готово_в_файле}")
                        if лимит_мин > 0:
                            frac_t = max(0.0, min(1.0, прошло_сек_live / (лимит_мин * 60.0)))
                            st.progress(frac_t, text=f"Прогресс по времени: {frac_t*100:.1f}% (статус: {статус})")
                        st.write(f"Готово кандидатов: **{готово}**")

                    if ok is not None and err is not None:
                        st.write(f"В последнем батче: OK={ok}, ERR={err}")
                    # диагностика: процесс умер, но статус ещё «идёт»
                    if (not pid_alive(st.session_state.opt_proc)) and статус in ["запущено", "идёт", "stage_running", "baseline_eval", "seed_eval"]:
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
                "Показывать baseline/service rows",
                value=bool(st.session_state.get("opt_show_service_rows", False)),
                key="opt_show_service_rows",
                help="Служебные baseline-anchor строки не считаются реальными кандидатами и обычно скрыты по умолчанию.",
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
                st.caption(f"Скрыто служебных baseline/service rows: {int(len(df_all_raw) - len(df_all))}")
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
    with st.expander("Калибровка и Autopilot (NPZ/CSV) — эксперимент", expanded=False):
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
                "Калибровка и Autopilot читают Txx_osc.npz из этой папки. "
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
        st.markdown("### Mapping файлов ➜ Txx_osc.npz (без ручной писанины в консоли)")
        st.caption(
            "Autopilot/калибровка по умолчанию ищут файлы с именами T01_osc.npz, T02_osc.npz, ... "
            "Если у тебя файлы называются иначе — выбери соответствие здесь и нажми «Применить mapping»."
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
                            help="Выбери файл (NPZ/CSV) для этого теста",
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
                if st.button("Применить mapping (создать/обновить Txx_osc.npz)", key="apply_tests_file_mapping"):
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
                if st.button("Открыть osc_dir (путь)", key="show_osc_dir_hint"):
                    st.info(str(osc_dir))
        else:
            st.info("Для построения mapping нужны: (1) набор опорных тестов (список тестов) и (2) хотя бы один файл NPZ/CSV в папке osc_dir.")

        st.markdown("---")
        st.write("Конвертация CSV ➜ NPZ (минимальный режим: CSV=таблица чисел, сохраняем как main_cols/main_values).")
        if csv_files:
            csv_pick = st.selectbox(
                "CSV для конвертации", options=[f.name for f in csv_files], index=0, key="csv_to_npz_pick"
            )
            csv_test_num = st.number_input(
                "В какой номер теста положить (Txx_osc.npz)", min_value=1, max_value=99, value=1, step=1, key="csv_to_npz_num"
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
        st.write("Запуск пайплайнов калибровки (они используют файлы Txx_osc.npz из osc_dir).")

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

    
        st.markdown("### Автоматизация (без консоли): полный расчёт ➜ NPZ ➜ oneclick/autopilot")
        st.caption(
            "Если реальных замеров пока нет — можно генерировать «расчётные» NPZ из текущего опорного прогона "
            "и гонять пайплайны oneclick/autopilot как самопроверку форматов и обвязки."
        )

        col_fc1, col_fc2, col_fc3 = st.columns(3)

        def _ensure_full_npz_for_all_tests(_mode_label: str) -> tuple[bool, str]:
            """Гарантирует, что в osc_dir есть Txx_osc.npz для всех тестов набора опорных тестов.

            Возвращает (ok, message).
            """
            _tests = list((_tests_map or {}).items())
            if not _tests:
                return False, "Нет набора опорных тестов (списка тестов). Сначала выполните опорный прогон."
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
            if st.button("1) Полный лог + NPZ (все тесты)", key="oneclick_full_logs_npz"):
                ok, msg = _ensure_full_npz_for_all_tests("full_npz")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        with col_fc2:
            if st.button("2) Полный лог + NPZ ➜ oneclick", key="oneclick_full_then_oneclick"):
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
                    st.write(f"oneclick exit code: {rc}")
                    if rc != 0:
                        st.error("oneclick завершился с ошибкой — см. stdout/stderr ниже и файлы в out_dir.")
                        st.code(so[-4000:] if so else "", language="text")
                        st.code(se[-4000:] if se else "", language="text")
                    else:
                        st.success("oneclick выполнен. Результаты в out_dir.")
                        st.code(str(out_dir), language="text")
                else:
                    st.error(msg)

        with col_fc3:
            if st.button("3) Полный лог + NPZ ➜ autopilot (minimal)", key="oneclick_full_then_autopilot"):
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
                        st.error("autopilot завершился с ошибкой — см. stdout/stderr ниже и файлы в out_dir.")
                        st.code(so[-4000:] if so else "", language="text")
                        st.code(se[-4000:] if se else "", language="text")
                    else:
                        st.success("autopilot выполнен. Результаты в out_dir.")
                        st.code(str(out_dir), language="text")
                else:
                    st.error(msg)

        st.markdown("---")
        col_cal1, col_cal2 = st.columns(2)
        with col_cal1:
            if st.button("Запустить калибровку (oneclick)", key="run_calib_oneclick"):
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
            if st.button("Запустить Autopilot (NPZ) v19", key="run_autopilot_v19"):
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
    with st.expander("Диагностика — собрать ZIP (для отправки)", expanded=False):
        # По умолчанию в приложении есть **одна** кнопка диагностики (в боковой панели):
        # «Сохранить диагностику (ZIP)». Этот UI-блок оставлен только для Legacy-режима,
        # чтобы не плодить дублирующие кнопки.
        show_legacy_tools = bool(
            st.session_state.get("pneumo_show_legacy", False)
            or os.environ.get("PNEUMO_SHOW_LEGACY", "0") == "1"
        )

        if not show_legacy_tools:
            st.info(
                "Единая кнопка диагностики находится в боковой панели: **Сохранить диагностику (ZIP)**. "
                "Этот UI-блок скрыт в основном режиме, чтобы не плодить дублирующие кнопки."
            )
            st.caption(
                "Если нужно собрать UI-диагностику именно отсюда: включите Legacy-режим "
                "в боковой панели (Режим интерфейса → Показать страницы Legacy)."
            )
        else:
            st.markdown(
                """
                Это **локальный** ZIP, который удобно отправлять вместо всей папки.

                Внутри: логи UI, результаты, **workspace/osc** (NPZ/CSV), **calibration_runs** (oneclick/autopilot) и снимок текущих JSON (base/suite/ranges).
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
