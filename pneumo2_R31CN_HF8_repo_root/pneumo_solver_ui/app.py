# -*- coding: utf-8 -*-
"""
pneumo_ui_app.py

Streamlit UI:
- Р·Р°РїСѓСЃРє РѕРґРёРЅРѕС‡РЅС‹С… С‚РµСЃС‚РѕРІ (baseline),
- Р·Р°РїСѓСЃРє РѕРїС‚РёРјРёР·Р°С†РёРё (С„РѕРЅРѕРІС‹Р№ РїСЂРѕС†РµСЃСЃ) РёР· UI,
- РїСЂРѕСЃРјРѕС‚СЂ/С„РёР»СЊС‚СЂ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ.

РўСЂРµР±РѕРІР°РЅРёСЏ: streamlit, numpy, pandas, openpyxl.

"""
# Compatibility note: this is the legacy single-page package UI.
# The canonical launcher is repo-root app.py; the heavy home page is pneumo_ui_app.py.
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
import uuid
from functools import partial
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Any, List, Optional

from pneumo_solver_ui.data_contract import build_geometry_meta_from_base, assert_required_geometry_meta, supplement_animator_geometry_meta
from pneumo_solver_ui.solver_points_contract import assert_required_solver_points_contract
from pneumo_solver_ui.browser_perf_artifacts import persist_browser_perf_snapshot_event
from pneumo_solver_ui.suite_contract_migration import migrate_legacy_suite_columns

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

# РћРїС†РёРѕРЅР°Р»СЊРЅРѕ: РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РіСЂР°С„РёРєРё (Plotly). Р•СЃР»Рё РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅРѕ вЂ” UI РїСЂРѕРґРѕР»Р¶РёС‚ СЂР°Р±РѕС‚Р°С‚СЊ Р±РµР· Plotly.
try:
    import plotly.graph_objects as go  # type: ignore
    import plotly.express as px  # type: ignore
    _HAS_PLOTLY = True
    from plotly.subplots import make_subplots  # type: ignore
except Exception:
    go = None  # type: ignore
    px = None  # type: ignore
    make_subplots = None  # type: ignore
    _HAS_PLOTLY = False

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
    render_app_results_surface_section,
)
from pneumo_solver_ui.ui_timeline_event_helpers import (
    compute_events_atm_profile as compute_events,
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
    dump_pickle_payload as _dump_detail_cache_payload,
    load_pickle_payload as _load_detail_cache_payload,
    start_background_worker,
)
from pneumo_solver_ui.ui_runtime_helpers import (
    do_rerun,
    get_ui_nonce,
    is_any_fallback_anim_playing,
    pid_alive,
    proc_metrics as _proc_metrics,
)
from pneumo_solver_ui.ui_simulation_helpers import (
    call_simulate,
    compute_road_profile_from_suite,
    parse_sim_output,
)
from pneumo_solver_ui.run_artifacts import (
    apply_anim_latest_to_session as apply_anim_latest_to_session_global,
    local_anim_latest_export_paths as local_anim_latest_export_paths_global,
    write_anim_latest_pointer_json as write_anim_latest_pointer_json_global,
)
from pneumo_solver_ui.tools.send_bundle_contract import ANIM_LOCAL_NPZ, ANIM_LOCAL_POINTER
from pneumo_solver_ui.ui_svg_html_builders import (
    render_svg_flow_animation_html,
)
from pneumo_solver_ui.ui_streamlit_surface_helpers import (
    safe_dataframe as render_safe_dataframe,
    safe_image as render_safe_image,
    safe_plotly_chart as render_safe_plotly_chart,
)
from pneumo_solver_ui.ui_suite_helpers import (
    load_default_suite_disabled,
    load_suite,
    resolve_osc_dir,
)
from pneumo_solver_ui.ui_unit_profile_helpers import (
    build_ui_unit_profile,
)
from pneumo_solver_ui.ui_unit_helpers import (
    gauge_to_pa_abs,
    infer_plot_unit_and_transform,
    pa_abs_to_gauge,
    param_unit_label,
    si_to_ui_value,
    ui_to_si_value,
)
from pneumo_solver_ui.ui_shared_helpers import (
    best_match as _best_match,
    name_score as _name_score,
    norm_name as _norm_name,
    run_starts as _run_starts,
    shorten_name as _shorten_name,
)
from pneumo_solver_ui.module_loading import load_python_module_from_path
from pneumo_solver_ui.project_path_resolution import resolve_project_py_path
from pneumo_solver_ui.detail_autorun_policy import (
    arm_detail_autorun_after_baseline,
    arm_detail_autorun_on_test_change,
    should_bypass_detail_disk_cache,
    clear_detail_force_fresh,
)
from pneumo_solver_ui.optimization_defaults import (
    DIAGNOSTIC_CALIB_MODE,
    canonical_base_json_path,
    canonical_model_path,
    canonical_ranges_json_path,
    canonical_suite_json_path,
    canonical_worker_path,
)
from pneumo_solver_ui.optimization_input_contract import (
    describe_runtime_stage,
    infer_suite_stage,
    normalize_suite_stage_numbers,
    sanitize_optimization_inputs,
)
from pneumo_solver_ui.process_tree import terminate_process_tree
from pneumo_solver_ui.optimization_runtime_paths import (
    build_optimization_run_dir,
    console_python_executable,
    staged_progress_path,
)

# Optional: РјРµС‚СЂРёРєРё РїСЂРѕС†РµСЃСЃР° (CPU/RAM). Р•СЃР»Рё psutil РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ вЂ” РїСЂРѕСЃС‚Рѕ РѕС‚РєР»СЋС‡Р°РµРј РјРµС‚СЂРёРєРё.
try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:
    psutil = None  # type: ignore
    _HAS_PSUTIL = False

# Release tag (used in logs/diagnostics)
from pneumo_solver_ui.release_info import get_release
from pneumo_solver_ui.name_sanitize import sanitize_ascii_id as _sanitize_id, sanitize_test_name
APP_RELEASE = get_release()

# Fallback (Р±РµР· Streamlit Components): matplotlibвЂ‘РІРёР·СѓР°Р»РёР·Р°С†РёСЏ РјРµС…Р°РЅРёРєРё.
# Р­С‚Рѕ Р»РµС‡РёС‚ С‚РёРїРѕРІС‹Рµ РїСЂРѕР±Р»РµРјС‹ РІСЂРѕРґРµ "Unrecognized component API version" РІ РЅРµРєРѕС‚РѕСЂС‹С… РѕРєСЂСѓР¶РµРЅРёСЏС….
try:
    import mech_anim_fallback as mech_fb  # local module
except Exception:
    mech_fb = None

from io import BytesIO

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

MODEL_DEFAULT = str(canonical_model_path(HERE))
WORKER_DEFAULT = str(canonical_worker_path(HERE))
SUITE_DEFAULT = str(canonical_suite_json_path(HERE))
BASE_DEFAULT = str(canonical_base_json_path(HERE))
RANGES_DEFAULT = str(canonical_ranges_json_path(HERE))

# -------------------------------
# Default files shipped with the app
# -------------------------------
DEFAULT_SVG_MAPPING_PATH = HERE / "default_svg_mapping.json"
DEFAULT_SVG_VIEWBOX = "0 0 1920 1080"

# -------------------------------
# Logging / diagnostics
# -------------------------------
LOG_DIR = HERE / "logs"

# Workspace for generated artifacts (NPZ, calibration runs, exports)
WORKSPACE_DIR = HERE / "workspace"
WORKSPACE_OSC_DIR = WORKSPACE_DIR / "osc"
WORKSPACE_EXPORTS_DIR = WORKSPACE_DIR / "exports"

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
    CALIB_RUNS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


get_osc_dir = partial(resolve_osc_dir, WORKSPACE_OSC_DIR)
LOG_DIR = prepare_runtime_log_dir(LOG_DIR)
_APP_LOGGER = configure_runtime_ui_logger("pneumo_ui")


def log_event(event: str, **fields: Any) -> None:
    """Р•РґРёРЅР°СЏ С‚РѕС‡РєР° Р»РѕРіРёСЂРѕРІР°РЅРёСЏ.

    РџРёС€РµРј РІ:
    - ui_*.log (РµСЃР»Рё РґРѕСЃС‚СѓРїРЅРѕ)
    - metrics_*.jsonl (РµСЃР»Рё РґРѕСЃС‚СѓРїРЅРѕ)
    """

    try:
        ensure_runtime_file_logger(
            st.session_state,
            logger=_APP_LOGGER,
            log_dir=LOG_DIR,
        )
        payload = {"event": event, **fields}
        _APP_LOGGER.info(json.dumps(payload, ensure_ascii=False))

        # metrics jsonl вЂ” СѓРґРѕР±РЅРµРµ РїР°СЂСЃРёС‚СЊ
        if LOG_DIR is not None:
            sid = st.session_state.get("_session_id", "")
            rec = {"ts": datetime.now().isoformat(), "session_id": sid, **payload}
            append_ui_log_lines(
                LOG_DIR,
                session_id=str(sid),
                session_metrics_line=json.dumps(rec, ensure_ascii=False),
                combined_text_line=json.dumps({"ts": rec["ts"], "session_id": sid, **payload}, ensure_ascii=False),
            )
    except Exception:
        return



# РџСЂРѕР±СЂР°СЃС‹РІР°РµРј callback РґР»СЏ РІРЅСѓС‚СЂРµРЅРЅРёС… РјРѕРґСѓР»РµР№ (fallback-Р°РЅРёРјР°С†РёРё) Р±РµР· РїСЂСЏРјРѕРіРѕ РёРјРїРѕСЂС‚Р° СЌС‚РѕРіРѕ С„Р°Р№Р»Р°.
# Р’ Streamlit-СЃРµСЃСЃРёРё РјРѕР¶РЅРѕ С…СЂР°РЅРёС‚СЊ callable. Р­С‚Рѕ РЅСѓР¶РЅРѕ РґР»СЏ mech_anim_fallback.
publish_session_callback(st.session_state, "_log_event_cb", log_event)


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




safe_dataframe = partial(render_safe_dataframe, st)
safe_plotly_chart = partial(render_safe_plotly_chart, st)
safe_image = partial(render_safe_image, st)


# --- NPZ / diagnostics helpers ---
try:
    # Preferred unified exporter (copies sidecars for Desktop Animator).
    from .npz_bundle import export_anim_latest_bundle as export_anim_latest_bundle_unified  # type: ignore
except Exception:
    export_anim_latest_bundle_unified = None  # type: ignore

def export_full_log_to_npz(out_path, df_main, df_p=None, df_q=None, df_open=None, meta=None, require_geometry_contract: bool = False, require_solver_points_contract: bool = False):
    """Export a simulation full-log bundle to NPZ (NumPy zipped arrays).

    The NPZ layout is compatible with calibration/npz_autosuggest_mapping_v2.py:
      - main_cols, main_values
      - p_cols, p_values (optional)
      - q_cols, q_values (optional)
      - open_cols, open_values (optional)
      - meta_json (optional)
    """
    import numpy as _np
    import json as _json
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "main_cols": _np.array(list(df_main.columns), dtype=object),
        "main_values": _np.asarray(df_main.to_numpy(), dtype=float),
    }
    if df_p is not None:
        payload["p_cols"] = _np.array(list(df_p.columns), dtype=object)
        payload["p_values"] = _np.asarray(df_p.to_numpy(), dtype=float)
    if df_q is not None:
        payload["q_cols"] = _np.array(list(df_q.columns), dtype=object)
        payload["q_values"] = _np.asarray(df_q.to_numpy(), dtype=float)
    if df_open is not None:
        payload["open_cols"] = _np.array(list(df_open.columns), dtype=object)
        payload["open_values"] = _np.asarray(df_open.to_numpy(), dtype=float)
    # meta: РґРѕР±Р°РІР»СЏРµРј РїРѕР»РµР·РЅС‹Рµ РїРѕР»СЏ РґР»СЏ С‚СЂР°СЃСЃРёСЂСѓРµРјРѕСЃС‚Рё (СЃРІСЏР·СЊ NPZ в†” UI в†” CSV)
    meta = dict(meta or {})
    meta.setdefault("app_release", APP_RELEASE)
    meta.setdefault("exported_at", datetime.now().isoformat(timespec="seconds"))
    if require_solver_points_contract:
        assert_required_solver_points_contract(
            df_main,
            context=f"legacy NPZ export {out_path.name} df_main",
            log=_APP_LOGGER.warning,
        )
    if require_geometry_contract:
        meta = assert_required_geometry_meta(
            meta,
            context=f"legacy NPZ export {out_path.name}",
            log=_APP_LOGGER.warning,
            require_nested=True,
        )
    if meta:
        payload["meta_json"] = _json.dumps(meta, ensure_ascii=False)
    _np.savez_compressed(out_path, **payload)

    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ РІРµРґС‘Рј РёРЅРґРµРєСЃ СЌРєСЃРїРѕСЂС‚РѕРІ, С‡С‚РѕР±С‹ РјРѕР¶РЅРѕ Р±С‹Р»Рѕ:
    # - РїРѕРЅРёРјР°С‚СЊ, РєР°РєРѕР№ С„Р°Р№Р» Рє РєР°РєРѕРјСѓ С‚РµСЃС‚Сѓ/Р±РµР№СЃР»Р°Р№РЅСѓ РѕС‚РЅРѕСЃРёС‚СЃСЏ
    # - Р°РіСЂРµРіРёСЂРѕРІР°С‚СЊ СЂРµР·СѓР»СЊС‚Р°С‚С‹ Р±РµР· "СѓРіР°РґС‹РІР°РЅРёСЏ" РїРѕ РёРјРµРЅРё
    try:
        idx_path = out_path.parent / "osc_index.jsonl"
        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "file": out_path.name,
            "path": str(out_path),
            "meta": meta or {},
        }
        with idx_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # РРЅРґРµРєСЃ РЅРµ РєСЂРёС‚РёС‡РµРЅ вЂ” СЌРєСЃРїРѕСЂС‚ NPZ РґРѕР»Р¶РµРЅ Р·Р°РІРµСЂС€РёС‚СЊСЃСЏ РґР°Р¶Рµ РµСЃР»Рё РёРЅРґРµРєСЃ РЅРµ РїРёС€РµС‚СЃСЏ.
        pass
    return out_path


# --- Desktop Animator helpers ---
ANIM_LATEST_NPZ_NAME = Path(ANIM_LOCAL_NPZ).name
ANIM_LATEST_PTR_NAME = Path(ANIM_LOCAL_POINTER).name


def get_anim_latest_paths() -> tuple[Path, Path]:
    """Return (npz_path, pointer_json_path) inside WORKSPACE_EXPORTS_DIR.

    Desktop Animator can run in "follow" mode and watch the pointer JSON.
    This keeps the workflow almost zero-click:
      1) Run a detail simulation in Streamlit
      2) Animator auto-reloads anim_latest
    """
    try:
        return local_anim_latest_export_paths_global(Path(WORKSPACE_EXPORTS_DIR))
    except Exception:
        exp_dir = Path(__file__).resolve().parent / "workspace" / "exports"
    return local_anim_latest_export_paths_global(exp_dir)


def write_anim_latest_pointer(npz_path: Path, *, meta: dict | None = None, pointer_path: Path | None = None) -> Path:
    """Write anim_latest.json pointer for Desktop Animator.

    Pointer diagnostics must expose not only the NPZ path but also the visual
    dependency token used by web/desktop reload logic.
    """
    if pointer_path is None:
        _, pointer_path = get_anim_latest_paths()
    pointer_path, _payload, _mirrored = write_anim_latest_pointer_json_global(
        npz_path,
        pointer_path=pointer_path,
        meta=dict(meta or {}),
        extra_fields={"ts": float(time.time())},
        context="anim_latest legacy pointer",
        log=_APP_LOGGER.warning,
        mirror_global_pointer=True,
    )
    return pointer_path


def export_anim_latest_bundle(df_main, df_p=None, df_q=None, df_open=None, meta=None):
    """Export to workspace/exports/anim_latest.npz and update pointer JSON.

    IMPORTANT:
      - Prefer unified exporter (pneumo_solver_ui.npz_bundle.export_anim_latest_bundle)
        because it also copies sidecar files (road/axay/scenario) into exports/.
      - New anim_latest bundles MUST satisfy the nested geometry contract:
        meta_json.geometry.wheelbase_m + meta_json.geometry.track_m.
      - New anim_latest bundles MUST contain full canonical solver-point triplets in df_main.
    """
    assert_required_solver_points_contract(
        df_main,
        context="anim_latest export df_main (app.py)",
        log=_APP_LOGGER.warning,
    )
    meta = assert_required_geometry_meta(
        dict(meta or {}),
        context="anim_latest export meta_json (app.py)",
        log=_APP_LOGGER.warning,
        require_nested=True,
    )
    try:
        # unified path (sidecar-safe)
        exp_dir = Path(WORKSPACE_EXPORTS_DIR)
        exp_dir.mkdir(parents=True, exist_ok=True)
        npz_latest, ptr_latest = export_anim_latest_bundle_unified(
            exports_dir=str(exp_dir),
            df_main=df_main,
            df_p=df_p,
            df_q=df_q,
            df_open=df_open,
            meta=meta,
        )
        try:
            apply_anim_latest_to_session_global(
                st.session_state,
                {"npz_path": npz_latest, "pointer_json": ptr_latest, "meta": dict(meta or {})},
            )
        except Exception:
            pass
        return npz_latest
    except ValueError:
        # Contract errors must not be bypassed by a fallback exporter.
        raise
    except Exception:
        # legacy fallback
        try:
            npz_path, _ptr = get_anim_latest_paths()
            out = export_full_log_to_npz(
                npz_path,
                df_main,
                df_p=df_p,
                df_q=df_q,
                df_open=df_open,
                meta=meta,
                require_geometry_contract=True,
                require_solver_points_contract=True,
            )
            ptr_latest = write_anim_latest_pointer(out, meta=meta)
            try:
                apply_anim_latest_to_session_global(
                    st.session_state,
                    {"npz_path": out, "pointer_json": ptr_latest, "meta": dict(meta or {})},
                )
            except Exception:
                pass
            return out
        except Exception:
            return None


make_ui_diagnostics_zip = build_ui_diagnostics_zip_writer(
    here=HERE,
    workspace_dir=WORKSPACE_DIR,
    log_dir=LOG_DIR,
    app_release=APP_RELEASE,
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

_unit_profile = build_ui_unit_profile(
    pressure_unit_label="Р°С‚Рј (РёР·Р±.)",
    pressure_offset_pa=lambda: P_ATM,
    pressure_divisor_pa=lambda: ATM_PA,
    length_unit_label="Рј",
    length_scale=1.0,
    is_pressure_param_fn=is_pressure_param,
    is_volume_param_fn=is_volume_param,
    is_small_volume_param_fn=is_small_volume_param,
    p_atm=lambda: P_ATM,
    bar_pa=100000.0,
)
_infer_unit_and_transform = _unit_profile.infer_unit_and_transform


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
            "Plotly РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ вЂ” РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РіСЂР°С„РёРєРё РѕС‚РєР»СЋС‡РµРЅС‹ (Graph Studio / РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ PlotlyвЂ‘РіСЂР°С„РёРєРё).\n\n"
            "Р РµС€РµРЅРёРµ: РёСЃРїРѕР»СЊР·СѓР№С‚Рµ RUN_ONECLICK_WINDOWS.bat РёР»Рё INSTALL_DEPENDENCIES_WINDOWS.bat (СЃРѕР·РґР°СЃС‚ .venv Рё СѓСЃС‚Р°РЅРѕРІРёС‚ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё).\n"
            "Р›РёР±Рѕ РІС‹РїРѕР»РЅРёС‚Рµ РІ РєРѕРЅСЃРѕР»Рё: python -m pip install -r requirements.txt"
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
    "Plotly РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ вЂ” РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ РіСЂР°С„РёРєРё РѕС‚РєР»СЋС‡РµРЅС‹ (Graph Studio / РёРЅС‚РµСЂР°РєС‚РёРІРЅС‹Рµ Plotly-РіСЂР°С„РёРєРё).\n\n"
    "Р РµС€РµРЅРёРµ: РёСЃРїРѕР»СЊР·СѓР№С‚Рµ RUN_ONECLICK_WINDOWS.bat РёР»Рё INSTALL_DEPENDENCIES_WINDOWS.bat (СЃРѕР·РґР°СЃС‚ .venv Рё СѓСЃС‚Р°РЅРѕРІРёС‚ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё).\n"
    "Р›РёР±Рѕ РІС‹РїРѕР»РЅРёС‚Рµ РІ РєРѕРЅСЃРѕР»Рё: python -m pip install -r requirements.txt"
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
    vacuum_min_gauge_atm: float = -0.2,
    pmax_margin_atm: float = 0.10,
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
    if df_p is not None and "РІСЂРµРјСЏ_СЃ" in df_p.columns and len(df_p) == n:
        cols = [c for c in df_p.columns if c != "РІСЂРµРјСЏ_СЃ" and c != "РђРўРњ"]
        if cols:
            Pmax_abs = float(params_abs.get("РґР°РІР»РµРЅРёРµ_Pmax_РїСЂРµРґРѕС…СЂР°РЅ", P_ATM + 8e5))
            pmax_thr = Pmax_abs + float(pmax_margin_atm) * ATM_PA

            try:
                P_nodes = df_p[cols].to_numpy(dtype=float)
                p_max = np.max(P_nodes, axis=1)
                p_min = np.min(P_nodes, axis=1)
            except Exception:
                p_max = None
                p_min = None

            if p_max is not None:
                for i0 in _run_starts(p_max > pmax_thr):
                    add_event(i0, "error", "overpressure", "nodes", "P>РџР Р•Р”РћРҐ (max node)")

            vac_thr = P_ATM + float(vacuum_min_gauge_atm) * ATM_PA
            # do not go below absolute min + small epsilon (avoid false positives)
            p_abs_min = float(params_abs.get("РјРёРЅРёРјР°Р»СЊРЅРѕРµ_Р°Р±СЃРѕР»СЋС‚РЅРѕРµ_РґР°РІР»РµРЅРёРµ_РџР°", 1000.0))
            vac_thr = max(vac_thr, p_abs_min + 1.0)

            if p_min is not None:
                for i0 in _run_starts(p_min < vac_thr):
                    add_event(i0, "warn", "vacuum", "nodes", f"Р’Р°РєСѓСѓРј: min node < {vacuum_min_gauge_atm:g} Р°С‚Рј(РёР·Р±)")

    # --------------------
    # 5) Valve chatter (rapid toggling) from df_open
    # --------------------
    if df_open is not None and "РІСЂРµРјСЏ_СЃ" in df_open.columns and len(df_open) == n:
        # Analyze only edges that actually toggle, and keep top few.
        edge_cols = [c for c in df_open.columns if c != "РІСЂРµРјСЏ_СЃ"]
        toggle_stats = []
        for col in edge_cols:
            arr = df_open[col].to_numpy()
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


plot_lines = build_line_plot_renderer(
    has_plotly=_HAS_PLOTLY,
    go_module=go,
    safe_plotly_chart_fn=safe_plotly_chart,
    is_any_fallback_anim_playing_fn=is_any_fallback_anim_playing,
    shorten_name_fn=_shorten_name,
)










# Shared worker/process helpers override the legacy inline copy above.
start_worker = build_background_worker_starter(
    console_python_executable_fn=console_python_executable,
)


# -------------------------------
# UI
# -------------------------------
st.set_page_config(page_title="РџРЅРµРІРјРѕРїРѕРґРІРµСЃРєР°: solver+РѕРїС‚РёРјРёР·Р°С†РёСЏ", layout="wide", initial_sidebar_state="collapsed")

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

st.title("РџРЅРµРІРјРѕРїРѕРґРІРµСЃРєР°: РјР°С‚РјРѕРґРµР»СЊ + РѕРїС‚РёРјРёР·Р°С†РёСЏ (solverвЂ‘first)")

# -------------------------------
# UI: РќР°РІРёРіР°С†РёСЏ (progressive disclosure)
# -------------------------------
UI_MODES = ["рџЏ  Р Р°Р±РѕС‡РµРµ РјРµСЃС‚Рѕ", "рџ§° РџРѕР»РЅС‹Р№ РёРЅС‚РµСЂС„РµР№СЃ"]

def _seg_or_radio(label: str, options: List[str], key: str, index: int = 0, horizontal: bool = True) -> str:
    """
    Try to render a compact segmented control (if available in current Streamlit),
    otherwise fallback to a horizontal radio.
    """
    try:
        # Streamlit newer versions may have segmented_control
        return st.segmented_control(label, options=options, default=options[index], key=key)
    except Exception:
        return st.radio(label, options=options, index=index, horizontal=horizontal, key=key)

ui_mode = _seg_or_radio("Р РµР¶РёРј", UI_MODES, key="ui_mode", index=0, horizontal=True)

FULL_SECTIONS = ["РњРѕРґРµР»СЊ", "РџР°СЂР°РјРµС‚СЂС‹", "РўРµСЃС‚С‹", "РџСЂРѕРіРѕРЅ", "Р РµР·СѓР»СЊС‚Р°С‚С‹", "РРЅСЃС‚СЂСѓРјРµРЅС‚С‹"]
if ui_mode == "рџ§° РџРѕР»РЅС‹Р№ РёРЅС‚РµСЂС„РµР№СЃ":
    ui_section = _seg_or_radio("Р Р°Р·РґРµР»", FULL_SECTIONS, key="ui_section", index=0, horizontal=True)
else:
    ui_section = "WORKSPACE"

SHOW_MODEL = (ui_section == "РњРѕРґРµР»СЊ")
SHOW_PARAMS = (ui_section == "РџР°СЂР°РјРµС‚СЂС‹")
SHOW_TESTS = (ui_section == "РўРµСЃС‚С‹")
SHOW_RUN = (ui_section == "РџСЂРѕРіРѕРЅ")
SHOW_RESULTS = (ui_section == "Р РµР·СѓР»СЊС‚Р°С‚С‹")
SHOW_TOOLS = (ui_section == "РРЅСЃС‚СЂСѓРјРµРЅС‚С‹")

# Workspace = Р±С‹СЃС‚СЂС‹Р№ СЃС†РµРЅР°СЂРёР№: РџСЂРѕРіРѕРЅ + Р РµР·СѓР»СЊС‚Р°С‚С‹ (Р±РµР· Р»РёС€РЅРµРіРѕ)
if ui_section == "WORKSPACE":
    SHOW_RUN = True
    SHOW_RESULTS = True
    SHOW_MODEL = False
    SHOW_PARAMS = False
    SHOW_TESTS = False
    SHOW_TOOLS = False

st.caption(
    "РРґРµСЏ РёРЅС‚РµСЂС„РµР№СЃР°: РѕРґРёРЅ СЌРєСЂР°РЅ = РѕРґРЅР° Р·Р°РґР°С‡Р°. "
    "РџРѕР»РЅС‹Р№ РёРЅС‚РµСЂС„РµР№СЃ СЂР°Р·РЅРµСЃС‘РЅ РїРѕ СЃРјС‹СЃР»РѕРІС‹Рј СЂР°Р·РґРµР»Р°Рј, С‡С‚РѕР±С‹ РЅРµ Р±С‹Р»Рѕ 'РїСЂРѕСЃС‚С‹РЅРµР№' Рё РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р°."
)


# -------------------------------
# РџСЂРѕРµРєС‚: РїСѓС‚Рё Рє РјРѕРґРµР»Рё/РѕРїС‚РёРјРёР·Р°С‚РѕСЂСѓ Рё РЅР°СЃС‚СЂРѕР№РєРё (persisted via session_state)
# -------------------------------
DEFAULT_MODEL_PATH = str(HERE / "model_pneumo_v8_energy_audit_vacuum.py")
DEFAULT_WORKER_PATH = str(HERE / "opt_worker_v3_margins_energy.py")

if "model_path" not in st.session_state:
    st.session_state["model_path"] = DEFAULT_MODEL_PATH
if "worker_path" not in st.session_state:
    st.session_state["worker_path"] = DEFAULT_WORKER_PATH

model_path = str(st.session_state.get("model_path", DEFAULT_MODEL_PATH))
worker_path = str(st.session_state.get("worker_path", DEFAULT_WORKER_PATH))

if "out_prefix" not in st.session_state:
    st.session_state["out_prefix"] = "results_opt"
out_prefix = str(st.session_state.get("out_prefix", "results_opt"))

if "opt_settings" not in st.session_state:
    # UI РґР»СЏ СЌС‚РёС… РЅР°СЃС‚СЂРѕРµРє РЅР°С…РѕРґРёС‚СЃСЏ РІ СЂР°Р·РґРµР»Рµ "РџСЂРѕРіРѕРЅ" (С‡С‚РѕР±С‹ РЅРµ Р·Р°С…Р»Р°РјР»СЏС‚СЊ СЃР°Р№РґР±Р°СЂ).
    st.session_state["opt_settings"] = {
        "minutes": 10.0,
        "seed_candidates": 1,
        "seed_conditions": 1,
        "jobs": int(max(1, min(32, (os.cpu_count() or 4)))),
        "flush_every": 20,
        "progress_every_sec": 1.0,
        "auto_refresh": True,
        "refresh_sec": 1.0,
    }

_opt = dict(st.session_state.get("opt_settings") or {})
minutes = float(_opt.get("minutes", 10.0))
seed_candidates = int(_opt.get("seed_candidates", 1))
seed_conditions = int(_opt.get("seed_conditions", 1))
jobs = int(_opt.get("jobs", 1))
flush_every = int(_opt.get("flush_every", 20))
progress_every_sec = float(_opt.get("progress_every_sec", 1.0))
auto_refresh = bool(_opt.get("auto_refresh", True))
refresh_sec = float(_opt.get("refresh_sec", 1.0))


# -------------------------------
# Р Р°Р·РґРµР» "РњРѕРґРµР»СЊ": РІС‹Р±РѕСЂ С„Р°Р№Р»РѕРІ РїСЂРѕРµРєС‚Р° (Р±РµР· Р·Р°С…Р»Р°РјР»РµРЅРёСЏ СЃР°Р№РґР±Р°СЂР°)
# -------------------------------
if SHOW_MODEL:
    st.subheader("РњРѕРґРµР»СЊ: С„Р°Р№Р»С‹ РїСЂРѕРµРєС‚Р°")
    st.caption("Р’С‹Р±РѕСЂ С„Р°Р№Р»РѕРІ РІС‹РЅРµСЃРµРЅ СЃСЋРґР°: С‚Р°Рє СЃР°Р№РґР±Р°СЂ РѕСЃС‚Р°С‘С‚СЃСЏ Р»С‘РіРєРёРј, Р° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ вЂ” РІ РѕРґРЅРѕРј РјРµСЃС‚Рµ.")

    colM1, colM2 = st.columns(2, gap="large")

    with colM1:
        model_files = sorted([p.name for p in HERE.glob("model_*.py")])
        current_model = Path(model_path).name
        opts = model_files.copy()
        if current_model and (current_model not in opts):
            opts = [current_model] + opts
        choice = st.selectbox("Р¤Р°Р№Р» РјРѕРґРµР»Рё (.py)", options=opts + ["(РІСЂСѓС‡РЅСѓСЋ)"], index=(opts.index(current_model) if current_model in opts else 0), key="model_file_choice")
        if choice == "(РІСЂСѓС‡РЅСѓСЋ)":
            manual = st.text_input("РџСѓС‚СЊ Рє РјРѕРґРµР»Рё", value=model_path, key="model_path_manual")
            st.session_state["model_path"] = str(manual)
        else:
            st.session_state["model_path"] = str(HERE / choice)

    with colM2:
        worker_files = sorted([p.name for p in HERE.glob("opt_worker_*.py")])
        current_worker = Path(worker_path).name
        opts = worker_files.copy()
        if current_worker and (current_worker not in opts):
            opts = [current_worker] + opts
        choice = st.selectbox("Р¤Р°Р№Р» РѕРїС‚РёРјРёР·Р°С‚РѕСЂР° (.py)", options=opts + ["(РІСЂСѓС‡РЅСѓСЋ)"], index=(opts.index(current_worker) if current_worker in opts else 0), key="worker_file_choice")
        if choice == "(РІСЂСѓС‡РЅСѓСЋ)":
            manual = st.text_input("РџСѓС‚СЊ Рє РѕРїС‚РёРјРёР·Р°С‚РѕСЂСѓ", value=worker_path, key="worker_path_manual")
            st.session_state["worker_path"] = str(manual)
        else:
            st.session_state["worker_path"] = str(HERE / choice)

    # refresh locals (so downstream code uses updated values in the same run)
    model_path = str(st.session_state.get("model_path", model_path))
    worker_path = str(st.session_state.get("worker_path", worker_path))

    st.info(f"РўРµРєСѓС‰Р°СЏ РјРѕРґРµР»СЊ: {Path(model_path).name} В· РѕРїС‚РёРјРёР·Р°С‚РѕСЂ: {Path(worker_path).name}")



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
    resolved_worker_path, _worker_msgs = resolve_project_py_path(
        worker_path,
        here=HERE,
        kind="РѕРїС‚РёРјРёР·Р°С‚РѕСЂ",
        default_path=DEFAULT_WORKER_PATH,
    )
    resolved_model_path, _model_msgs = resolve_project_py_path(
        model_path,
        here=HERE,
        kind="РјРѕРґРµР»СЊ",
        default_path=DEFAULT_MODEL_PATH,
    )

    for _msg in (_worker_msgs + _model_msgs):
        st.warning(_msg)
        try:
            log_event(
                "project_path_fallback",
                message=str(_msg),
                worker_path=str(worker_path),
                model_path=str(model_path),
                resolved_worker=str(resolved_worker_path),
                resolved_model=str(resolved_model_path),
            )
        except Exception:
            pass

    worker_mod = load_python_module_from_path(Path(resolved_worker_path), "opt_worker_mod")
    model_mod = load_python_module_from_path(Path(resolved_model_path), "pneumo_model_mod")
except Exception as e:
    st.error(f"РќРµ РјРѕРіСѓ Р·Р°РіСЂСѓР·РёС‚СЊ РјРѕРґРµР»СЊ/РѕРїС‚РёРјРёР·Р°С‚РѕСЂ: {e}")
    st.stop()

P_ATM = float(getattr(model_mod, "P_ATM", 101325.0))
# 1 atm (СЃС‚Р°РЅРґР°СЂС‚РЅР°СЏ Р°С‚РјРѕСЃС„РµСЂР°) = 101325 РџР°.
# Р’ UI СЂР°Р±РѕС‚Р°РµРј РІ "Р°С‚Рј (РёР·Р±.)" (gauge), РІРЅСѓС‚СЂРё РјРѕРґРµР»Рё вЂ” РџР° (Р°Р±СЃРѕР»СЋС‚РЅРѕРµ).
ATM_PA = 101325.0


pa_abs_to_atm_g = _unit_profile.pressure_from_pa
atm_g_to_pa_abs = _unit_profile.pressure_to_pa_abs


# -------------------------------
# РћРїРёСЃР°РЅРёСЏ/РµРґРёРЅРёС†С‹ РїР°СЂР°РјРµС‚СЂРѕРІ (РґР»СЏ UI)
# Р’РђР–РќРћ: СЌС‚Рё С„СѓРЅРєС†РёРё РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РѕРїСЂРµРґРµР»РµРЅС‹ Р”Рћ С‚РѕРіРѕ, РєР°Рє РјС‹ СЃС‚СЂРѕРёРј С‚Р°Р±Р»РёС†Сѓ df_opt.
# РРЅР°С‡Рµ Python СѓРїР°РґС‘С‚ СЃ NameError, С‚.Рє. РјРѕРґСѓР»СЊ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ СЃРІРµСЂС…Сѓ РІРЅРёР·.
# -------------------------------


param_unit = _unit_profile.param_unit


# -------------------------------
# Р‘Р»РѕРє РїР°СЂР°РјРµС‚СЂРѕРІ (Р±Р°Р·Р° + РґРёР°РїР°Р·РѕРЅС‹)
# -------------------------------
base0, ranges0 = worker_mod.make_base_and_ranges(P_ATM)

# Р—Р°РїРѕРјРёРЅР°РµРј РёСЃС…РѕРґРЅС‹Рµ С‚РёРїС‹ С„Р»Р°РіРѕРІ, С‡С‚РѕР±С‹ UI РєРѕСЂСЂРµРєС‚РЅРѕ РїРѕРєР°Р·С‹РІР°Р» С‡РµРєР±РѕРєСЃС‹ РґР°Р¶Рµ РµСЃР»Рё РіРґРµ-С‚Рѕ Р·РЅР°С‡РµРЅРёСЏ СЃС‚Р°Р»Рё 0/1 РёР»Рё numpy.bool_.
try:
    BASE_BOOL_KEYS = {k for k, v in base0.items() if isinstance(v, (bool, np.bool_))}
except Exception:
    BASE_BOOL_KEYS = {k for k, v in base0.items() if isinstance(v, bool)}
BASE_STR_KEYS = {k for k, v in base0.items() if isinstance(v, str)}

# -------------------------------
# Р•Р”РРќР«Р™ Р’Р’РћР” РџРђР РђРњР•РўР РћР’ (Р·РЅР°С‡РµРЅРёРµ + РґРёР°РїР°Р·РѕРЅ РѕРїС‚РёРјРёР·Р°С†РёРё)
# -------------------------------

# (UI РїР°СЂР°РјРµС‚СЂРѕРІ РѕС‚РѕР±СЂР°Р¶Р°РµС‚СЃСЏ РЅРёР¶Рµ РІ СЂР°Р·РґРµР»Рµ "РџР°СЂР°РјРµС‚СЂС‹")

# РњРµС‚Р°РґР°РЅРЅС‹Рµ (С‚РµРєСЃС‚/РµРґРёРЅРёС†С‹) вЂ” Р±РµР· В«Р·Р°С…Р°СЂРґРєРѕР¶РµРЅРЅС‹С…В» С‡РёСЃРµР».
PARAM_META = {
    # Р”Р°РІР»РµРЅРёСЏ (СѓСЃС‚Р°РІРєРё) вЂ” РІ UI: Р°С‚Рј (РёР·Р±С‹С‚РѕС‡РЅРѕРіРѕ)
    "РґР°РІР»РµРЅРёРµ_Pmin_РїРёС‚Р°РЅРёРµ_Р РµСЃРёРІРµСЂ2": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р°С‚Рј (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "РЈСЃС‚Р°РІРєР° РїРѕРґРїРёС‚РєРё: Р»РёРЅРёСЏ В«РђРєРєСѓРјСѓР»СЏС‚РѕСЂ в†’ Р РµСЃРёРІРµСЂ 2В». Р­С‚Рѕ РќР• Pmin СЃР±СЂРѕСЃР°/Р°С‚РјРѕСЃС„РµСЂС‹. "
                    "РћРїС‚РёРјРёР·РёСЂСѓР№С‚Рµ РѕС‚РґРµР»СЊРЅРѕ РѕС‚ Pmin."
    },
    "РґР°РІР»РµРЅРёРµ_Pmin_СЃР±СЂРѕСЃ": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р°С‚Рј (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "Pmin РґР»СЏ СЃР±СЂРѕСЃР° РІ Р°С‚РјРѕСЃС„РµСЂСѓ (РІРµС‚РєР° Р 3в†’Р°С‚Рј). РќРёР¶Рµ СЌС‚РѕРіРѕ РґР°РІР»РµРЅРёСЏ СЃС‚СѓРїРµРЅСЊ РЅРµ РґРѕР»Р¶РЅР° В«СЂР°Р·СЂСЏР¶Р°С‚СЊСЃСЏВ» РІ РЅРѕР»СЊ."
    },
    "РґР°РІР»РµРЅРёРµ_Pmid_СЃР±СЂРѕСЃ": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р°С‚Рј (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "Pmid (СѓСЃС‚Р°РІРєР° В«СЃРµСЂРµРґРёРЅС‹В»): РІС‹С€Рµ вЂ” РїРѕРґРІРµСЃРєР° Р·Р°РјРµС‚РЅРѕ В«Р¶С‘СЃС‚С‡РµВ». РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ РјРµС‚СЂРёРєРµ В«СЂР°РЅСЊС€РµвЂ‘Р¶С‘СЃС‚РєРѕВ»."
    },
    "РґР°РІР»РµРЅРёРµ_PР·Р°СЂСЏРґ_Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР°_РёР·_Р РµСЃРёРІРµСЂ3": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р°С‚Рј (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "РЈСЃС‚Р°РІРєР° РїРѕРґРїРёС‚РєРё Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР° РёР· Р РµСЃРёРІРµСЂР° 3 РІРѕ РІСЂРµРјСЏ РґРІРёР¶РµРЅРёСЏ (РІРѕСЃРїРѕР»РЅРµРЅРёРµ Р·Р°РїР°СЃР° РІРѕР·РґСѓС…Р°)."
    },
    "РґР°РІР»РµРЅРёРµ_Pmax_РїСЂРµРґРѕС…СЂР°РЅ": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (СѓСЃС‚Р°РІРєРё)",
        "РµРґ": "Р°С‚Рј (РёР·Р±.)",
        "kind": "pressure_atm_g",
        "РѕРїРёСЃР°РЅРёРµ": "Pmax вЂ” Р°РІР°СЂРёР№РЅР°СЏ СѓСЃС‚Р°РІРєР° РїСЂРµРґРѕС…СЂР°РЅРёС‚РµР»СЊРЅРѕРіРѕ РєР»Р°РїР°РЅР° (РЅРµ РґРѕР»Р¶РЅР° РїСЂРµРІС‹С€Р°С‚СЊСЃСЏ)."
    },
    "РЅР°С‡Р°Р»СЊРЅРѕРµ_РґР°РІР»РµРЅРёРµ_Р°РєРєСѓРјСѓР»СЏС‚РѕСЂР°": {
        "РіСЂСѓРїРїР°": "Р”Р°РІР»РµРЅРёРµ (РЅР°С‡Р°Р»СЊРЅС‹Рµ)",
        "РµРґ": "Р°С‚Рј (РёР·Р±.)",
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
        "РѕРїРёСЃР°РЅРёРµ": "РњР°СЃС€С‚Р°Р± РєСЂРёРІРѕР№ В«СЃРёР»Р°вЂ‘С…РѕРґВ» РїСЂСѓР¶РёРЅС‹ (С‚Р°Р±Р»РёС‡РЅР°СЏ РЅРµР»РёРЅРµР№РЅРѕСЃС‚СЊ РѕСЃС‚Р°С‘С‚СЃСЏ, СѓРјРЅРѕР¶Р°РµРј СЃРёР»Сѓ РЅР° РєРѕСЌС„С„РёС†РёРµРЅС‚)."
    },

    # РњРµС…Р°РЅРёРєР°/РјР°СЃСЃС‹
    "РјР°СЃСЃР°_СЂР°РјС‹": {"РіСЂСѓРїРїР°": "РњРµС…Р°РЅРёРєР°", "РµРґ": "РєРі", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РџРѕРґСЂРµСЃСЃРѕСЂРµРЅРЅР°СЏ РјР°СЃСЃР° (СЂР°РјР°/РєСѓР·РѕРІ)."},
    "РјР°СЃСЃР°_РЅРµРїРѕРґСЂРµСЃСЃРѕСЂРµРЅРЅР°СЏ": {"РіСЂСѓРїРїР°": "РњРµС…Р°РЅРёРєР°", "РµРґ": "РєРі", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РќРµРїРѕРґСЂРµСЃСЃРѕСЂРµРЅРЅР°СЏ РјР°СЃСЃР° РЅР° РєРѕР»РµСЃРѕ (СЃС‚СѓРїРёС†Р°/СЂС‹С‡Р°Рі/РєРѕР»РµСЃРѕ)."},
    "РєРѕР»РµСЏ": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РљРѕР»РµСЏ (СЂР°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ С†РµРЅС‚СЂР°РјРё Р»РµРІРѕРіРѕ Рё РїСЂР°РІРѕРіРѕ РєРѕР»С‘СЃ)."},
    "Р±Р°Р·Р°": {"РіСЂСѓРїРїР°": "Р“РµРѕРјРµС‚СЂРёСЏ", "РµРґ": "Рј", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": "РљРѕР»С‘СЃРЅР°СЏ Р±Р°Р·Р° (РїРµСЂРµРґвЂ‘Р·Р°Рґ)."},
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
}


_si_to_ui = _unit_profile.si_to_ui
_ui_to_si = _unit_profile.ui_to_si


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
    """
    РќРµР»РёРЅРµР№РЅР°СЏ РїСЂСѓР¶РёРЅР° С…СЂР°РЅРёС‚СЃСЏ РєР°Рє 2 РјР°СЃСЃРёРІР° (С…РѕРґ_РјРј, СЃРёР»Р°_Рќ).
    Р’Р°Р¶РЅРѕРµ РїСЂР°РІРёР»Рѕ UI: СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ вЂ” С‚РѕР»СЊРєРѕ РІ СЂР°Р·РґРµР»Рµ "РџР°СЂР°РјРµС‚СЂС‹", С‡С‚РѕР±С‹ РЅРµ Р·Р°С…Р»Р°РјР»СЏС‚СЊ РґСЂСѓРіРёРµ СЌРєСЂР°РЅС‹.
    РџСЂРё СЌС‚РѕРј Р·РЅР°С‡РµРЅРёСЏ РёР· session_state РїСЂРёРјРµРЅСЏСЋС‚СЃСЏ Р’РЎР•Р“Р”Рђ (С‡С‚РѕР±С‹ РїСЂРѕРіРѕРЅ/СЂРµР·СѓР»СЊС‚Р°С‚С‹ РёСЃРїРѕР»СЊР·РѕРІР°Р»Рё Р°РєС‚СѓР°Р»СЊРЅСѓСЋ С‚Р°Р±Р»РёС†Сѓ).
    """
    try:
        import pandas as _pd

        if "spring_table_df" not in st.session_state:
            st.session_state["spring_table_df"] = _pd.DataFrame({
                "С…РѕРґ_РјРј": list(base0.get(SPR_X, [])),
                "СЃРёР»Р°_Рќ": list(base0.get(SPR_F, [])),
            })

        spring_df = st.session_state.get("spring_table_df")

        if SHOW_PARAMS:
            st.markdown("### РќРµР»РёРЅРµР№РЅР°СЏ РїСЂСѓР¶РёРЅР°: С‚Р°Р±Р»РёС‡РЅР°СЏ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°")
            st.caption("Р РµРґР°РєС‚РёСЂСѓР№С‚Рµ С‚РѕС‡РєРё (Р±РµР· РїСЂР°РІРєРё С„Р°Р№Р»РѕРІ). РўРѕС‡РєРё Р±СѓРґСѓС‚ РѕС‚СЃРѕСЂС‚РёСЂРѕРІР°РЅС‹ РїРѕ С…РѕРґСѓ. РњРёРЅРёРјСѓРј 2 С‚РѕС‡РєРё.")
            spring_df = st.data_editor(
                spring_df,
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

        # Р’Р°Р»РёРґР°С†РёСЏ + РЅРѕСЂРјР°Р»РёР·Р°С†РёСЏ (РїСЂРёРјРµРЅСЏРµРј РІСЃРµРіРґР°)
        _df = _pd.DataFrame(spring_df).copy()
        _df["С…РѕРґ_РјРј"] = _pd.to_numeric(_df["С…РѕРґ_РјРј"], errors="coerce")
        _df["СЃРёР»Р°_Рќ"] = _pd.to_numeric(_df["СЃРёР»Р°_Рќ"], errors="coerce")
        _df = _df.dropna().sort_values("С…РѕРґ_РјРј")

        if len(_df) < 2:
            if SHOW_PARAMS or SHOW_RUN:
                st.error("РўР°Р±Р»РёС†Р° РїСЂСѓР¶РёРЅС‹ РґРѕР»Р¶РЅР° СЃРѕРґРµСЂР¶Р°С‚СЊ РјРёРЅРёРјСѓРј 2 С‡РёСЃР»РѕРІС‹Рµ С‚РѕС‡РєРё.")
        else:
            base0[SPR_X] = _df["С…РѕРґ_РјРј"].astype(float).tolist()
            base0[SPR_F] = _df["СЃРёР»Р°_Рќ"].astype(float).tolist()

    except Exception as e:
        if SHOW_PARAMS or SHOW_RUN:
            st.error(f"РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё С‚Р°Р±Р»РёС†С‹ РїСЂСѓР¶РёРЅС‹: {e}")


# РЎРїРёСЃРѕРє РєР»СЋС‡РµР№ СЃРѕ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅС‹РјРё Р·РЅР°С‡РµРЅРёСЏРјРё (list/dict) вЂ” РёС… РёСЃРєР»СЋС‡Р°РµРј РёР· С‚Р°Р±Р»РёС†С‹ СЃРєР°Р»СЏСЂРѕРІ
structured_keys = [k for k in all_keys if isinstance(base0.get(k, None), (list, dict))]

# Р’ С‚Р°Р±Р»РёС†Сѓ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РїРѕРїР°РґР°СЋС‚ С‚РѕР»СЊРєРѕ С‡РёСЃР»РѕРІС‹Рµ СЃРєР°Р»СЏСЂС‹.
scalar_keys = [k for k in all_keys if (k not in structured_keys) and _is_numeric_scalar(base0.get(k, None))]
non_numeric_keys = [k for k in all_keys if (k not in structured_keys) and (not _is_numeric_scalar(base0.get(k, None)))]

rows = []
for k in scalar_keys:
    meta = PARAM_META.get(k) or family_param_meta(k) or {"РіСЂСѓРїРїР°": "РџСЂРѕС‡РµРµ", "РµРґ": "РЎР", "kind": "raw", "РѕРїРёСЃР°РЅРёРµ": ""}
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

if "df_params_edit" not in st.session_state:
    st.session_state["df_params_edit"] = df_params0

# --- UI: РїР°СЂР°РјРµС‚СЂС‹ Р±РµР· РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р° (СЃРїРёСЃРѕРє + РєР°СЂС‚РѕС‡РєР°) ---
def _merge_params_df(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """РЎ remember: СЃРѕС…СЂР°РЅСЏРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРёРµ РїСЂР°РІРєРё Рё РїРѕРґС…РІР°С‚С‹РІР°РµРј РЅРѕРІС‹Рµ РєР»СЋС‡Рё РёР· df_new."""
    try:
        if (df_old is None) or (len(df_old) == 0):
            return df_new.copy()
        if (df_new is None) or (len(df_new) == 0):
            return df_old.copy()
        a = df_old.copy()
        b = df_new.copy()
        if "_key" not in a.columns:
            a["_key"] = a.get("РїР°СЂР°РјРµС‚СЂ", "")
        if "_key" not in b.columns:
            b["_key"] = b.get("РїР°СЂР°РјРµС‚СЂ", "")
        # РёРЅРґРµРєСЃ РїРѕ РєР»СЋС‡Сѓ
        a = a.set_index("_key", drop=False)
        b = b.set_index("_key", drop=False)

        # 1) РѕР±РЅРѕРІР»СЏРµРј РѕРїРёСЃР°РЅРёСЏ/РіСЂСѓРїРїС‹/РµРґРёРЅРёС†С‹ РёР· "СЃРІРµР¶РµРіРѕ"
        for col in ["РіСЂСѓРїРїР°", "РµРґРёРЅРёС†Р°", "РїРѕСЏСЃРЅРµРЅРёРµ", "_kind", "РїР°СЂР°РјРµС‚СЂ"]:
            if col in b.columns:
                a[col] = a[col].where(~a[col].isna(), b[col])
                # РµСЃР»Рё Сѓ РЅР°СЃ СѓСЃС‚Р°СЂРµРІС€РµРµ РѕРїРёСЃР°РЅРёРµ вЂ” РїСЂРµРґРїРѕС‡РёС‚Р°РµРј РЅРѕРІРѕРµ
                a[col] = b[col].combine_first(a[col])

        # 2) РґРѕР±Р°РІР»СЏРµРј РЅРѕРІС‹Рµ РєР»СЋС‡Рё, РєРѕС‚РѕСЂС‹С… РЅРµ Р±С‹Р»Рѕ
        missing = [k for k in b.index if k not in a.index]
        if missing:
            a = pd.concat([a, b.loc[missing].copy()], axis=0)

        # 3) СЃРѕСЂС‚РёСЂРѕРІРєР° РєР°Рє РІ РЅРѕРІРѕРј df (РіСЂСѓРїРїР°/РєР»СЋС‡)
        try:
            a = a.loc[b.index.intersection(a.index).tolist() + [k for k in a.index if k not in b.index]]
        except Exception:
            pass
        return a.reset_index(drop=True)
    except Exception:
        return df_new.copy()

def _render_param_card_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Render one parameter row as a card, return updated values."""
    k = str(row.get("_key") or row.get("РїР°СЂР°РјРµС‚СЂ") or "")
    group = str(row.get("РіСЂСѓРїРїР°") or "РџСЂРѕС‡РµРµ")
    unit = str(row.get("РµРґРёРЅРёС†Р°") or "вЂ”")
    kind = str(row.get("_kind") or "raw")
    desc = str(row.get("РїРѕСЏСЃРЅРµРЅРёРµ") or "")

    # current values (UI units already)
    def _f(x, default=float("nan")):
        try:
            return float(x)
        except Exception:
            return default

    v = _f(row.get("Р·РЅР°С‡РµРЅРёРµ"))
    opt = bool(row.get("РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", False))
    vmin = _f(row.get("РјРёРЅ"))
    vmax = _f(row.get("РјР°РєСЃ"))

    # Card layout
    with st.container():
        topL, topR = st.columns([1.4, 1.0], gap="large")
        with topL:
            st.markdown(f"**{k}**  В·  {group}")
            if desc:
                st.caption(desc)
        with topR:
            opt_new = st.checkbox("РћРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", value=opt, key=f"popt__{k}")
            opt = bool(opt_new)

        # Value editor
        # Rule: try to avoid manual typing where it's safe.
        # We use sliders for common semantics, otherwise number_input.
        val_key = f"pval__{k}"

        # Slider ranges
        use_slider = False
        smin, smax, step = None, None, None

        if kind == "fraction01" or (("РґРѕР»СЏ" in unit) and ("0..1" in unit)):
            use_slider = True
            smin, smax = 0.0, 1.0
            step = 0.01
            if not (0.0 <= v <= 1.0):
                v = max(0.0, min(1.0, v if math.isfinite(v) else 0.0))

        elif kind == "pressure_atm_g" or ("Р°С‚Рј" in unit):
            use_slider = True
            # leaving some room for vacuum (negative gauge)
            base = v if math.isfinite(v) else 0.0
            if opt and math.isfinite(vmin) and math.isfinite(vmax) and (vmin < vmax):
                smin, smax = float(vmin), float(vmax)
            else:
                smin = float(min(base - 2.0, -0.95))
                smax = float(max(base + 2.0, 10.0))
            step = 0.05

        elif ("РѕР±СЉС‘Рј" in k) or (kind.startswith("volume_")) or (unit in ("Р»", "РјР»")):
            use_slider = True
            base = v if math.isfinite(v) else (1.0 if unit == "Р»" else 100.0)
            if opt and math.isfinite(vmin) and math.isfinite(vmax) and (vmin < vmax):
                smin, smax = float(vmin), float(vmax)
            else:
                # heuristic around current
                span = max(abs(base) * 0.5, 1.0 if unit == "Р»" else 50.0)
                smin = max(0.0, base - span)
                smax = max(smin + (1.0 if unit == "Р»" else 10.0), base + span)
            step = 0.1 if unit == "Р»" else 1.0

        elif k.endswith("_РіСЂР°Рґ") or (unit == "РіСЂР°Рґ"):
            use_slider = True
            base = v if math.isfinite(v) else 0.0
            if opt and math.isfinite(vmin) and math.isfinite(vmax) and (vmin < vmax):
                smin, smax = float(vmin), float(vmax)
            else:
                smin, smax = float(min(base - 10.0, -30.0)), float(max(base + 10.0, 30.0))
            step = 0.1

        # Render value
        if use_slider and (smin is not None) and (smax is not None):
            # clamp value into slider range
            vv = v if math.isfinite(v) else (0.0 if smin <= 0.0 <= smax else smin)
            vv = min(max(vv, float(smin)), float(smax))
            v_new = st.slider(
                "Р—РЅР°С‡РµРЅРёРµ",
                min_value=float(smin),
                max_value=float(smax),
                value=float(vv),
                step=float(step) if step else None,
                key=val_key,
            )
        else:
            v_new = st.number_input(
                "Р—РЅР°С‡РµРЅРёРµ",
                value=float(v) if math.isfinite(v) else 0.0,
                step=None,
                key=val_key,
            )

        # Range editor (advanced)
        vmin_new, vmax_new = vmin, vmax
        if opt:
            with st.expander("Р”РёР°РїР°Р·РѕРЅ РѕРїС‚РёРјРёР·Р°С†РёРё", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    vmin_new = st.number_input("РњРёРЅ", value=float(vmin) if math.isfinite(vmin) else float(v_new), step=None, key=f"pmin__{k}")
                with c2:
                    vmax_new = st.number_input("РњР°РєСЃ", value=float(vmax) if math.isfinite(vmax) else float(v_new), step=None, key=f"pmax__{k}")
        return {
            **row,
            "Р·РЅР°С‡РµРЅРёРµ": float(v_new),
            "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ": bool(opt),
            "РјРёРЅ": float(vmin_new) if math.isfinite(float(vmin_new)) else float("nan"),
            "РјР°РєСЃ": float(vmax_new) if math.isfinite(float(vmax_new)) else float("nan"),
        }

# Ensure params table exists and stays in sync with current PARAM_META
if "df_params_edit" not in st.session_state:
    st.session_state["df_params_edit"] = df_params0
else:
    st.session_state["df_params_edit"] = _merge_params_df(st.session_state["df_params_edit"], df_params0)

# Reflect edits only in the Parameters section (progressive disclosure)
if SHOW_PARAMS:
    st.subheader("РџР°СЂР°РјРµС‚СЂС‹ (Р·РЅР°С‡РµРЅРёСЏ + РґРёР°РїР°Р·РѕРЅС‹ РѕРїС‚РёРјРёР·Р°С†РёРё)")
    st.caption(
        "РўСѓС‚ СЂРµРґР°РєС‚РёСЂСѓСЋС‚СЃСЏ С‡РёСЃР»РѕРІС‹Рµ РїР°СЂР°РјРµС‚СЂС‹. РќРµС‚ РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЃРєСЂРѕР»Р»Р°: СЃРїРёСЃРѕРє в†’ РєР°СЂС‚РѕС‡РєР° РїР°СЂР°РјРµС‚СЂР°. "
        "РћРїС‚РёРјРёР·Р°С†РёСЋ РІРєР»СЋС‡Р°Р№С‚Рµ РіР°Р»РѕС‡РєРѕР№ РЅР° РєР°СЂС‚РѕС‡РєРµ, РґРёР°РїР°Р·РѕРЅ РїСЂСЏС‡РµС‚СЃСЏ РІ 'Р”РёР°РїР°Р·РѕРЅ РѕРїС‚РёРјРёР·Р°С†РёРё'."
    )

    df_in = st.session_state["df_params_edit"].copy()
    # Filters
    groups = sorted([g for g in df_in.get("РіСЂСѓРїРїР°", pd.Series(dtype=str)).dropna().unique().tolist() if str(g).strip()])
    colF1, colF2, colF3 = st.columns([1.2, 1.0, 0.9], gap="medium")
    with colF1:
        q = st.text_input("РџРѕРёСЃРє", value=st.session_state.get("param_search", ""), key="param_search", placeholder="РЅР°РїСЂРёРјРµСЂ: РґР°РІР»РµРЅРёРµ, РѕР±СЉС‘Рј, РѕС‚РєСЂС‹С‚РёРµ...")
    with colF2:
        grp = st.selectbox("Р“СЂСѓРїРїР°", options=["(РІСЃРµ)"] + groups, index=0, key="param_group")
    with colF3:
        only_opt = st.checkbox("РўРѕР»СЊРєРѕ РѕРїС‚РёРјРёР·РёСЂСѓРµРјС‹Рµ", value=bool(st.session_state.get("param_only_opt", False)), key="param_only_opt")

    df_view = df_in.copy()
    if grp != "(РІСЃРµ)":
        df_view = df_view[df_view["РіСЂСѓРїРїР°"] == grp]
    if q.strip():
        qq = q.strip().lower()
        df_view = df_view[df_view.apply(lambda r: (qq in str(r.get("_key","")).lower()) or (qq in str(r.get("РїРѕСЏСЃРЅРµРЅРёРµ","")).lower()), axis=1)]
    if only_opt:
        df_view = df_view[df_view["РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ"].astype(bool)]

    # Limit visible cards for performance
    total = int(len(df_view))
    show_n = st.slider("РџРѕРєР°Р·С‹РІР°С‚СЊ РїР°СЂР°РјРµС‚СЂРѕРІ", min_value=8, max_value=40, value=int(min(16, max(8, total))), step=1, key="param_show_n")
    st.caption(f"РџРѕРєР°Р·Р°РЅРѕ: {min(show_n, total)} РёР· {total} (С„РёР»СЊС‚СЂС‹ СЃРІРµСЂС…Сѓ).")
    df_view = df_view.head(show_n)

    # Render cards and write back into df_in
    updated_rows = {}
    for _, r in df_view.iterrows():
        rec = _render_param_card_row(r.to_dict())
        updated_rows[str(rec.get("_key") or rec.get("РїР°СЂР°РјРµС‚СЂ") or "")] = rec

    if updated_rows:
        df_out = df_in.copy().set_index("_key", drop=False)
        for k, rec in updated_rows.items():
            if k in df_out.index:
                for col in ["Р·РЅР°С‡РµРЅРёРµ", "РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ", "РјРёРЅ", "РјР°РєСЃ"]:
                    if col in df_out.columns and col in rec:
                        df_out.loc[k, col] = rec[col]
        df_out = df_out.reset_index(drop=True)
        st.session_state["df_params_edit"] = df_out

df_params_edit = st.session_state["df_params_edit"]

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

if param_errors and (SHOW_PARAMS or SHOW_RUN):
    st.error("Р’ С‚Р°Р±Р»РёС†Рµ РїР°СЂР°РјРµС‚СЂРѕРІ РµСЃС‚СЊ РѕС€РёР±РєРё (РёСЃРїСЂР°РІСЊС‚Рµ РїРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј):\n- " + "\n- ".join(param_errors))





# -------------------------------
# РњРѕРґРµР»СЊ: СЂРµР¶РёРјС‹ Рё С„Р»Р°РіРё (bool + string)
# -------------------------------
# РџСЂРёРЅС†РёРї: UI "РјРѕРґРµР»СЊРЅС‹С…" РЅР°СЃС‚СЂРѕРµРє РїРѕРєР°Р·С‹РІР°РµРј С‚РѕР»СЊРєРѕ РІ СЂР°Р·РґРµР»Рµ "РњРѕРґРµР»СЊ",
# РЅРѕ РІС‹Р±СЂР°РЅРЅС‹Рµ Р·РЅР°С‡РµРЅРёСЏ РїСЂРёРјРµРЅСЏСЋС‚СЃСЏ Р’РЎР•Р“Р”Рђ (С‡С‚РѕР±С‹ РџСЂРѕРіРѕРЅ/Р РµР·СѓР»СЊС‚Р°С‚С‹ СЂР°Р±РѕС‚Р°Р»Рё РѕРґРёРЅР°РєРѕРІРѕ).
bool_keys_ui = [k for k in BASE_BOOL_KEYS if (k in base0)]
str_keys_ui = [k for k in BASE_STR_KEYS if (k in base0)]

if SHOW_MODEL:
    st.divider()
    st.subheader("РњРѕРґРµР»СЊ: СЂРµР¶РёРјС‹ Рё С„Р»Р°РіРё")
    st.caption("Р‘СѓР»РµРІС‹ вЂ” С‡РµРєР±РѕРєСЃС‹. РЎС‚СЂРѕРєРѕРІС‹Рµ вЂ” РІС‹РїР°РґР°СЋС‰РёРµ СЃРїРёСЃРєРё. РџРѕРёСЃРє СЃРІРµСЂС…Сѓ, С‡С‚РѕР±С‹ РЅРµ Р±С‹Р»Рѕ 'РїСЂРѕСЃС‚С‹РЅРµР№'.")

    with st.expander("Р‘СѓР»РµРІС‹ С„Р»Р°РіРё", expanded=False):
        qf = st.text_input("РџРѕРёСЃРє С„Р»Р°РіР°", value=st.session_state.get("flag_search", ""), key="flag_search", placeholder="РЅР°РїСЂРёРјРµСЂ: РІР°РєСѓСѓРј, РјСЏРіРє, РґРµРјРїС„...")
        show_all = st.checkbox("РџРѕРєР°Р·Р°С‚СЊ РІСЃРµ", value=bool(st.session_state.get("flag_show_all", False)), key="flag_show_all")
        keys = bool_keys_ui
        if qf.strip():
            qq = qf.strip().lower()
            keys = [k for k in keys if qq in str(k).lower()]
        if not show_all:
            keys = keys[:40]
        for k in keys:
            # default from current base_override or base0
            v0 = bool(base_override.get(k, base0.get(k, False)))
            st.checkbox(k, value=v0, key=f"flag__{k}")

        if (not show_all) and (len(bool_keys_ui) > 40):
            st.caption("Р§Р°СЃС‚СЊ С„Р»Р°РіРѕРІ СЃРєСЂС‹С‚Р°. Р’РєР»СЋС‡РёС‚Рµ 'РџРѕРєР°Р·Р°С‚СЊ РІСЃРµ' РёР»Рё РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РїРѕРёСЃРє.")

    with st.expander("РЎС‚СЂРѕРєРѕРІС‹Рµ СЂРµР¶РёРјС‹", expanded=False):
        qm = st.text_input("РџРѕРёСЃРє СЂРµР¶РёРјР°", value=st.session_state.get("mode_search", ""), key="mode_search", placeholder="РЅР°РїСЂРёРјРµСЂ: РїР°СЃРїРѕСЂС‚, СЃС‚СЂР°С‚РµРіРёСЏ, СЂРµР¶РёРј...")
        show_all = st.checkbox("РџРѕРєР°Р·Р°С‚СЊ РІСЃРµ СЂРµР¶РёРјС‹", value=bool(st.session_state.get("mode_show_all", False)), key="mode_show_all")

        keys = str_keys_ui
        if qm.strip():
            qq = qm.strip().lower()
            keys = [k for k in keys if qq in str(k).lower()]
        if not show_all:
            keys = keys[:30]

        for k in keys:
            if k == "РїР°СЃРїРѕСЂС‚_РєРѕРјРїРѕРЅРµРЅС‚РѕРІ_json":
                # prefer local json files as presets
                json_files = []
                try:
                    for p in sorted(HERE.glob("*.json")):
                        if p.name.lower() in ("default_suite.json", "svg_mapping.json"):
                            continue
                        json_files.append(p.name)
                except Exception:
                    pass

                current = str(base_override.get(k, base0.get(k, "")) or "")
                options = ["(РєР°Рє РІ Р±Р°Р·Рµ)"] + json_files + ["(РІСЂСѓС‡РЅСѓСЋ)"]
                # index
                idx = 0
                if current in json_files:
                    idx = 1 + json_files.index(current)
                elif current.strip():
                    idx = len(options) - 1

                choice = st.selectbox("РїР°СЃРїРѕСЂС‚_РєРѕРјРїРѕРЅРµРЅС‚РѕРІ_json", options=options, index=idx, key=f"mode__{k}__choice")
                if choice == "(РІСЂСѓС‡РЅСѓСЋ)":
                    st.text_input("РџСѓС‚СЊ/РёРјСЏ JSON", value=current, key=f"mode__{k}__manual")
                elif choice == "(РєР°Рє РІ Р±Р°Р·Рµ)":
                    # clear manual
                    st.session_state.pop(f"mode__{k}__manual", None)
                    st.session_state[f"mode__{k}"] = str(base0.get(k, "")) or ""
                else:
                    st.session_state.pop(f"mode__{k}__manual", None)
                    st.session_state[f"mode__{k}"] = str(choice)
            else:
                # common simple mode
                v0 = str(base_override.get(k, base0.get(k, "")) or "")
                st.text_input(k, value=v0, key=f"mode__{k}")

        if (not show_all) and (len(str_keys_ui) > 30):
            st.caption("Р§Р°СЃС‚СЊ СЂРµР¶РёРјРѕРІ СЃРєСЂС‹С‚Р°. Р’РєР»СЋС‡РёС‚Рµ 'РџРѕРєР°Р·Р°С‚СЊ РІСЃРµ СЂРµР¶РёРјС‹' РёР»Рё РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РїРѕРёСЃРє.")

# Apply overrides from session_state (always)
for k in bool_keys_ui:
    v = st.session_state.get(f"flag__{k}", base0.get(k, False))
    base_override[k] = bool(v)

for k in str_keys_ui:
    if k == "РїР°СЃРїРѕСЂС‚_РєРѕРјРїРѕРЅРµРЅС‚РѕРІ_json":
        v_man = str(st.session_state.get(f"mode__{k}__manual", "") or "").strip()
        if v_man:
            base_override[k] = v_man
        else:
            base_override[k] = str(st.session_state.get(f"mode__{k}", base0.get(k, "")) or "")
    else:
        base_override[k] = str(st.session_state.get(f"mode__{k}", base0.get(k, "")) or "")
# -------------------------------
# РўРµСЃС‚вЂ‘РЅР°Р±РѕСЂ Рё РїРѕСЂРѕРіРё (СЂРµРґР°РєС‚РёСЂСѓРµС‚СЃСЏ РёР· UI)
# -------------------------------
# (UI С‚РµСЃС‚-РЅР°Р±РѕСЂР° РѕС‚РѕР±СЂР°Р¶Р°РµС‚СЃСЏ РЅРёР¶Рµ РІ СЂР°Р·РґРµР»Рµ "РўРµСЃС‚С‹")

ALLOWED_TEST_TYPES = [
    "РёРЅРµСЂС†РёСЏ_РєСЂРµРЅ",
    "РёРЅРµСЂС†РёСЏ_С‚Р°РЅРіР°Р¶",
    "РјРёРєСЂРѕ_СЃРёРЅС„Р°Р·Р°",
    "РјРёРєСЂРѕ_СЂР°Р·РЅРѕС„Р°Р·Р°",
    "РєРѕС‡РєР°_РѕРґРЅРѕ_РєРѕР»РµСЃРѕ",
    "РєРѕС‡РєР°_РґРёР°РіРѕРЅР°Р»СЊ",
    "РєРѕРјР±Рѕ_РєСЂРµРЅ_РїР»СЋСЃ_РјРёРєСЂРѕ",
]

DEFAULT_SUITE_PATH = HERE / "default_suite.json"
SUITE_CONTRACT_WARNINGS_PENDING_KEY = "suite_contract_warnings_pending"


def first_suite_selected_index(df: pd.DataFrame | None) -> int | None:
    try:
        if df is None or len(df) == 0:
            return None
        return int(df.index[0])
    except Exception:
        return None


def _normalize_suite_df_for_editor(df: pd.DataFrame | None, *, context: str) -> pd.DataFrame:
    try:
        df_norm, issues = migrate_legacy_suite_columns(df, context=context)
    except Exception as exc:
        logging.warning("[suite] Failed to normalize suite schema in %s: %s", context, exc)
        log_event("suite_contract_migration_error", context=context, error=str(exc))
        return pd.DataFrame() if df is None else df.copy()

    if issues:
        st.session_state[SUITE_CONTRACT_WARNINGS_PENDING_KEY] = list(issues)
        for msg in issues:
            logging.warning(msg)
            log_event("suite_contract_migration", context=context, message=msg)
    return df_norm


def _show_suite_contract_warnings_once() -> None:
    issues = st.session_state.pop(SUITE_CONTRACT_WARNINGS_PENDING_KEY, [])
    if not issues:
        return
    st.warning(
        "Р’ suite РѕР±РЅР°СЂСѓР¶РµРЅС‹ legacy-РєРѕР»РѕРЅРєРё. Р’С‹РїРѕР»РЅРµРЅР° СЏРІРЅР°СЏ РјРёРіСЂР°С†РёСЏ РІ canonical schema; "
        "РїРµСЂРµСЃРѕС…СЂР°РЅРёС‚Рµ suite.json.\n- " + "\n- ".join(str(x) for x in issues)
    )


# Р·Р°РіСЂСѓР·РєР° suite РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ
if "df_suite_edit" not in st.session_state:
    st.session_state["df_suite_edit"] = _normalize_suite_df_for_editor(
        pd.DataFrame(load_default_suite_disabled(DEFAULT_SUITE_PATH)),
        context="app.default_suite_load",
    )

# upload/СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ suite вЂ” С‚РѕР»СЊРєРѕ РІ СЂР°Р·РґРµР»Рµ "РўРµСЃС‚С‹" (progressive disclosure)
df_suite_edit = st.session_state.get("df_suite_edit")
if df_suite_edit is None:
    df_suite_edit = pd.DataFrame()
    st.session_state["df_suite_edit"] = df_suite_edit
else:
    df_suite_edit = _normalize_suite_df_for_editor(pd.DataFrame(df_suite_edit), context="app.session_state_restore")
    st.session_state["df_suite_edit"] = df_suite_edit

# РќРѕСЂРјР°Р»РёР·Р°С†РёСЏ РєРѕР»РѕРЅРѕРє (РЅР° СЃР»СѓС‡Р°Р№ СЃС‚Р°СЂС‹С…/Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… suite)
EXPECTED_SUITE_COLS = [
    "РёРјСЏ", "РІРєР»СЋС‡РµРЅ", "С‚РёРї", "dt", "t_end",
    "t_step", "settle_band_min_deg", "settle_band_ratio",
    "ax", "ay", "A", "f", "dur", "t0", "idx",
    "vx0_Рј_СЃ", "СѓРіРѕР»_РіСЂР°Рґ", "РґРѕР»СЏ_РїР»Р°РІРЅРѕР№_СЃС‚С‹РєРѕРІРєРё",
    # targets:
    "target_РјР°РєСЃ_РґРѕР»СЏ_РѕС‚СЂС‹РІР°",
    "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_Pmid_Р±Р°СЂ",
    "target_РјРёРЅ_Fmin_Рќ",
    "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_РїСЂРѕР±РѕСЏ_РєСЂРµРЅ_РіСЂР°Рґ",
    "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_РїСЂРѕР±РѕСЏ_С‚Р°РЅРіР°Р¶_РіСЂР°Рґ",
    "target_РјРёРЅ_Р·Р°РїР°СЃ_РґРѕ_СѓРїРѕСЂР°_С€С‚РѕРєР°_Рј",
    "target_Р»РёРјРёС‚_СЃРєРѕСЂРѕСЃС‚Рё_С€С‚РѕРєР°_Рј_СЃ",
]
for _c in EXPECTED_SUITE_COLS:
    if _c not in df_suite_edit.columns:
        df_suite_edit[_c] = np.nan
st.session_state["df_suite_edit"] = df_suite_edit
if SHOW_TESTS or SHOW_RUN:
    _show_suite_contract_warnings_once()

if SHOW_TESTS:
    st.subheader("РўРµСЃС‚вЂ‘РЅР°Р±РѕСЂ (suite)")
    st.caption(
        "РЎР»РµРІР° вЂ” СЃРїРёСЃРѕРє С‚РµСЃС‚РѕРІ (РїРѕРёСЃРє/РІС‹Р±РѕСЂ). РЎРїСЂР°РІР° вЂ” РєР°СЂС‚РѕС‡РєР° РІС‹Р±СЂР°РЅРЅРѕРіРѕ С‚РµСЃС‚Р°. "
        "Р­С‚Рѕ СѓСЃС‚СЂР°РЅСЏРµС‚ РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅС‹Р№ СЃРєСЂРѕР»Р» Рё 'РїСЂРѕСЃС‚С‹РЅРё' С‚Р°Р±Р»РёС†."
    )

    # Import / export / reset
    with st.expander("РРјРїРѕСЂС‚ / СЌРєСЃРїРѕСЂС‚ / СЃР±СЂРѕСЃ", expanded=True):
        colIE1, colIE2, colIE3 = st.columns([1.2, 1.0, 1.0], gap="medium")

        with colIE1:
            suite_upload = st.file_uploader(
                "РРјРїРѕСЂС‚ suite (JSON)",
                type=["json"],
                help="Р—Р°РіСЂСѓР·РёС‚Рµ СЂР°РЅРµРµ СЃРѕС…СЂР°РЅС‘РЅРЅС‹Р№ suite.json (СЃРїРёСЃРѕРє СЃР»РѕРІР°СЂРµР№).",
                key="suite_upload_json",
            )
            if suite_upload is not None:
                try:
                    suite_loaded = json.loads(suite_upload.getvalue().decode("utf-8"))
                    if isinstance(suite_loaded, list):
                        _loaded_df = _normalize_suite_df_for_editor(
                            pd.DataFrame(suite_loaded),
                            context="app.suite_upload",
                        )
                        st.session_state["df_suite_edit"] = _loaded_df
                        st.session_state["suite_sel"] = first_suite_selected_index(_loaded_df)
                        st.success("Suite Р·Р°РіСЂСѓР¶РµРЅ.")
                        st.rerun()
                    else:
                        st.error("JSON РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃРїРёСЃРєРѕРј РѕР±СЉРµРєС‚РѕРІ (list[dict]).")
                except Exception as e:
                    st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ JSON: {e}")

        with colIE2:
            if st.button("РЎР±СЂРѕСЃРёС‚СЊ Рє default_suite.json", key="suite_reset_default"):
                _default_df = _normalize_suite_df_for_editor(
                    pd.DataFrame(load_default_suite_disabled(DEFAULT_SUITE_PATH)),
                    context="app.suite_reset_default",
                )
                st.session_state["df_suite_edit"] = _default_df
                st.session_state["suite_sel"] = first_suite_selected_index(_default_df)
                st.rerun()

        with colIE3:
            # Export
            try:
                df_tmp = st.session_state["df_suite_edit"].copy()
                suite_out = []
                for _, rr in df_tmp.iterrows():
                    rec = {}
                    for k, v in rr.to_dict().items():
                        if isinstance(v, float) and pd.isna(v):
                            continue
                        if v is None:
                            continue
                        rec[k] = v
                    if rec:
                        suite_out.append(rec)
                suite_json = json.dumps(suite_out, ensure_ascii=False, indent=2)
            except Exception:
                suite_json = "[]"
            st.download_button(
                "Р­РєСЃРїРѕСЂС‚ suite.json",
                data=suite_json,
                file_name="suite_export.json",
                mime="application/json",
                key="suite_download_json",
            )

    # Master-detail layout
    df_suite_edit = st.session_state["df_suite_edit"].copy()
    left, right = st.columns([1.0, 1.2], gap="large")

    with left:
        q = st.text_input("РџРѕРёСЃРє С‚РµСЃС‚Р°", value=st.session_state.get("suite_search", ""), key="suite_search", placeholder="РЅР°РїСЂРёРјРµСЂ: РєСЂРµРЅ, РјРёРєСЂРѕ, РєРѕС‡РєР°...")
        # build labels
        labels = []
        idx_map = []
        for i, r in df_suite_edit.iterrows():
            name = str(r.get("РёРјСЏ") or f"test_{i}")
            typ = str(r.get("С‚РёРї") or "")
            enabled = bool(r.get("РІРєР»СЋС‡РµРЅ")) if ("РІРєР»СЋС‡РµРЅ" in r) else True
            lbl = f"{'вњ…' if enabled else 'в›”'} {name}  В·  {typ}"
            if q.strip():
                if q.strip().lower() not in lbl.lower():
                    continue
            labels.append(lbl)
            idx_map.append(i)

        if not labels:
            st.info("РЎРїРёСЃРѕРє С‚РµСЃС‚РѕРІ РїСѓСЃС‚ (РёР»Рё С„РёР»СЊС‚СЂ РЅРёС‡РµРіРѕ РЅРµ РЅР°С€С‘Р»). Р”РѕР±Р°РІСЊС‚Рµ С‚РµСЃС‚.")
            sel_i = None
        else:
            # keep selection stable with a normal always-selected scenario when list is not empty.
            if "suite_sel" not in st.session_state:
                st.session_state["suite_sel"] = idx_map[0]
            if st.session_state["suite_sel"] not in idx_map:
                st.session_state["suite_sel"] = idx_map[0]
            sel_i = st.selectbox(
                "РўРµСЃС‚",
                options=idx_map,
                format_func=lambda i: (labels[idx_map.index(i)] if i in idx_map else str(i)),
                key="suite_sel",
            )

        btnC1, btnC2, btnC3 = st.columns(3, gap="small")
        with btnC1:
            if st.button("вћ• Р”РѕР±Р°РІРёС‚СЊ", key="suite_add"):
                new_row = {c: np.nan for c in EXPECTED_SUITE_COLS}
                new_row["РІРєР»СЋС‡РµРЅ"] = True
                new_row["РёРјСЏ"] = f"new_test_{len(df_suite_edit)+1}"
                new_row["С‚РёРї"] = ALLOWED_TEST_TYPES[0] if ALLOWED_TEST_TYPES else "РёРЅРµСЂС†РёСЏ_РєСЂРµРЅ"
                new_row["dt"] = 0.01
                new_row["t_end"] = 3.0
                df_suite_edit = pd.concat([df_suite_edit, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state["df_suite_edit"] = df_suite_edit
                st.session_state["suite_sel"] = int(len(df_suite_edit)-1)
                st.rerun()
        with btnC2:
            if st.button("рџ“„ Р”СѓР±Р»РёСЂРѕРІР°С‚СЊ", disabled=(sel_i is None), key="suite_dup"):
                if sel_i is not None:
                    row = df_suite_edit.loc[sel_i].to_dict()
                    row["РёРјСЏ"] = str(row.get("РёРјСЏ") or "copy") + "_copy"
                    df_suite_edit = pd.concat([df_suite_edit, pd.DataFrame([row])], ignore_index=True)
                    st.session_state["df_suite_edit"] = df_suite_edit
                    st.session_state["suite_sel"] = int(len(df_suite_edit)-1)
                    st.rerun()
        with btnC3:
            if st.button("рџ—‘пёЏ РЈРґР°Р»РёС‚СЊ", disabled=(sel_i is None), key="suite_del"):
                if sel_i is not None and len(df_suite_edit) > 0:
                    df_suite_edit = df_suite_edit.drop(index=sel_i).reset_index(drop=True)
                    st.session_state["df_suite_edit"] = df_suite_edit
                    st.session_state["suite_sel"] = first_suite_selected_index(df_suite_edit)
                    st.rerun()

        st.caption(f"Р’СЃРµРіРѕ С‚РµСЃС‚РѕРІ: {len(st.session_state['df_suite_edit'])}")

    with right:
        if sel_i is None or len(df_suite_edit) == 0:
            st.info("Р’С‹Р±РµСЂРёС‚Рµ С‚РµСЃС‚ СЃР»РµРІР°.")
        else:
            row = df_suite_edit.loc[sel_i].to_dict()

            def _num(x, default=float("nan")):
                try:
                    return float(x)
                except Exception:
                    return default

            enabled = bool(row.get("РІРєР»СЋС‡РµРЅ", True))
            name = str(row.get("РёРјСЏ") or f"test_{sel_i}")
            typ = str(row.get("С‚РёРї") or (ALLOWED_TEST_TYPES[0] if ALLOWED_TEST_TYPES else ""))

            with st.container():
                st.markdown("**РљР°СЂС‚РѕС‡РєР° С‚РµСЃС‚Р°**")
                cA, cB = st.columns([1.0, 1.0], gap="medium")
                with cA:
                    enabled = st.checkbox("Р’РєР»СЋС‡РµРЅ", value=enabled, key=f"suite_enabled__{sel_i}")
                    name = st.text_input("РРјСЏ", value=name, key=f"suite_name__{sel_i}")
                with cB:
                    typ = st.selectbox("РўРёРї", options=ALLOWED_TEST_TYPES, index=(ALLOWED_TEST_TYPES.index(typ) if typ in ALLOWED_TEST_TYPES else 0), key=f"suite_type__{sel_i}")

                # dt / t_end presets
                dt0 = _num(row.get("dt"), 0.01)
                tend0 = _num(row.get("t_end"), 3.0)
                dt_presets = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1]
                te_presets = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]

                c1, c2 = st.columns(2, gap="medium")
                with c1:
                    dt_choice = st.selectbox("РЁР°Рі dt (СЃ)", options=dt_presets + ["РґСЂСѓРіРѕРµ"], index=(dt_presets.index(dt0) if dt0 in dt_presets else len(dt_presets)), key=f"suite_dt_choice__{sel_i}")
                    if dt_choice == "РґСЂСѓРіРѕРµ":
                        dt = st.number_input("dt (СЃ)", value=float(dt0), step=None, key=f"suite_dt__{sel_i}")
                    else:
                        dt = float(dt_choice)
                with c2:
                    te_choice = st.selectbox("Р”Р»РёС‚РµР»СЊРЅРѕСЃС‚СЊ t_end (СЃ)", options=te_presets + ["РґСЂСѓРіРѕРµ"], index=(te_presets.index(tend0) if tend0 in te_presets else len(te_presets)), key=f"suite_te_choice__{sel_i}")
                    if te_choice == "РґСЂСѓРіРѕРµ":
                        t_end = st.number_input("t_end (СЃ)", value=float(tend0), step=None, key=f"suite_te__{sel_i}")
                    else:
                        t_end = float(te_choice)

                # Common excitation / maneuver params (only if present)
                st.markdown("**Р’РѕР·РјСѓС‰РµРЅРёРµ / РјР°РЅС‘РІСЂ**")
                c3, c4, c5 = st.columns(3, gap="small")
                with c3:
                    ax = _num(row.get("ax"), 0.0)
                    ax = st.slider("ax (Рј/СЃВІ)", min_value=-20.0, max_value=20.0, value=float(max(-20.0, min(20.0, ax))), step=0.1, key=f"suite_ax__{sel_i}")
                with c4:
                    ay = _num(row.get("ay"), 0.0)
                    ay = st.slider("ay (Рј/СЃВІ)", min_value=-20.0, max_value=20.0, value=float(max(-20.0, min(20.0, ay))), step=0.1, key=f"suite_ay__{sel_i}")
                with c5:
                    speed = _num(row.get("vx0_Рј_СЃ"), 0.0)
                    speed = st.slider("СЃРєРѕСЂРѕСЃС‚СЊ (Рј/СЃ)", min_value=0.0, max_value=40.0, value=float(max(0.0, min(40.0, speed))), step=0.5, key=f"suite_speed__{sel_i}")

                c6, c7, c8 = st.columns(3, gap="small")
                with c6:
                    A = _num(row.get("A"), 0.0)
                    A = st.slider("A (Рј)", min_value=0.0, max_value=0.3, value=float(max(0.0, min(0.3, A))), step=0.001, key=f"suite_A__{sel_i}")
                with c7:
                    f = _num(row.get("f"), 0.0)
                    f = st.slider("f (Р“С†)", min_value=0.0, max_value=25.0, value=float(max(0.0, min(25.0, f))), step=0.1, key=f"suite_f__{sel_i}")
                with c8:
                    angle = _num(row.get("СѓРіРѕР»_РіСЂР°Рґ"), 0.0)
                    angle = st.slider("СѓРіРѕР» (РіСЂР°Рґ)", min_value=-45.0, max_value=45.0, value=float(max(-45.0, min(45.0, angle))), step=0.5, key=f"suite_angle__{sel_i}")

                with st.expander("РџРѕСЂРѕРі/СѓСЃС‚Р°РІРєРё (targets) Рё СЂР°СЃС€РёСЂРµРЅРЅС‹Рµ РїР°СЂР°РјРµС‚СЂС‹", expanded=True):
                    # show only non-empty targets
                    for k in EXPECTED_SUITE_COLS:
                        if not k.startswith("target_"):
                            continue
                        v0 = row.get(k, np.nan)
                        if isinstance(v0, float) and pd.isna(v0):
                            v0 = 0.0
                        row[k] = st.number_input(k, value=float(v0) if v0 is not None else 0.0, step=None, key=f"suite_tgt__{k}__{sel_i}")
                    # extra non-target fields we didn't expose above
                    for k in ["t_step", "settle_band_min_deg", "settle_band_ratio", "dur", "t0", "idx", "РґРѕР»СЏ_РїР»Р°РІРЅРѕР№_СЃС‚С‹РєРѕРІРєРё"]:
                        if k not in row:
                            continue
                        v0 = row.get(k, np.nan)
                        if isinstance(v0, float) and pd.isna(v0):
                            v0 = 0.0
                        row[k] = st.number_input(k, value=float(v0) if v0 is not None else 0.0, step=None, key=f"suite_extra__{k}__{sel_i}")

                if st.button("вњ… РџСЂРёРјРµРЅРёС‚СЊ", key=f"suite_apply__{sel_i}"):
                    # write back
                    df2 = st.session_state["df_suite_edit"].copy()
                    df2.loc[sel_i, "РІРєР»СЋС‡РµРЅ"] = bool(enabled)
                    df2.loc[sel_i, "РёРјСЏ"] = str(name)
                    df2.loc[sel_i, "С‚РёРї"] = str(typ)
                    df2.loc[sel_i, "dt"] = float(dt)
                    df2.loc[sel_i, "t_end"] = float(t_end)
                    # common params
                    for k, v in {
                        "ax": ax, "ay": ay, "vx0_Рј_СЃ": speed,
                        "A": A, "f": f, "СѓРіРѕР»_РіСЂР°Рґ": angle,
                    }.items():
                        if k in df2.columns:
                            df2.loc[sel_i, k] = float(v)

                    # advanced stored in row dict from expander keys
                    for k in EXPECTED_SUITE_COLS:
                        if k.startswith("target_") and (k in df2.columns):
                            try:
                                df2.loc[sel_i, k] = float(row.get(k, 0.0))
                            except Exception:
                                pass
                    for k in ["t_step", "settle_band_min_deg", "settle_band_ratio", "dur", "t0", "idx", "РґРѕР»СЏ_РїР»Р°РІРЅРѕР№_СЃС‚С‹РєРѕРІРєРё"]:
                        if k in df2.columns:
                            try:
                                df2.loc[sel_i, k] = float(row.get(k, 0.0))
                            except Exception:
                                pass

                    st.session_state["df_suite_edit"] = df2
                    st.success("РЎРѕС…СЂР°РЅРµРЅРѕ.")
                    st.rerun()

# Always define df_suite_edit for downstream logic
df_suite_edit = st.session_state.get("df_suite_edit", pd.DataFrame())
try:
    _suite_norm, _stage_audit = normalize_suite_stage_numbers((df_suite_edit or pd.DataFrame()).to_dict(orient="records") if hasattr(df_suite_edit, "to_dict") else [])
    if (
        int(_stage_audit.get("stage_bias_applied", 0) or 0) != 0
        or int(_stage_audit.get("clamped_negative_rows", 0) or 0) != 0
        or int(_stage_audit.get("inferred_missing_rows", 0) or 0) != 0
    ):
        df_suite_edit = pd.DataFrame(_suite_norm)
        st.session_state["df_suite_edit"] = df_suite_edit
except Exception:
    pass
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

    suite_override.append(rec)

if suite_errors and (SHOW_TESTS or SHOW_RUN):
    st.error("Р’ С‚РµСЃС‚вЂ‘РЅР°Р±РѕСЂРµ РµСЃС‚СЊ РѕС€РёР±РєРё (РёСЃРїСЂР°РІСЊС‚Рµ РїРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј):\n- " + "\n- ".join(suite_errors))


# -------------------------------
# РћРґРёРЅРѕС‡РЅС‹Рµ С‚РµСЃС‚С‹
# -------------------------------
if SHOW_RUN:
    # РќР°СЃС‚СЂРѕР№РєРё РІС‹РІРѕРґР°/РѕРїС‚РёРјРёР·Р°С†РёРё (РІС‹РЅРµСЃРµРЅС‹ СЃСЋРґР°, С‡С‚РѕР±С‹ РЅРµ РїРµСЂРµРіСЂСѓР¶Р°С‚СЊ СЃР°Р№РґР±Р°СЂ)
    st.subheader("РџСЂРѕРіРѕРЅ: РЅР°СЃС‚СЂРѕР№РєРё")
    cS1, cS2 = st.columns([1.1, 1.0], gap="large")
    with cS1:
        out_prefix = st.text_input("РџСЂРµС„РёРєСЃ СЂРµР·СѓР»СЊС‚Р°С‚Р°", value=str(st.session_state.get("out_prefix", out_prefix)), key="out_prefix")
        auto_refresh = st.checkbox("РђРІС‚РѕвЂ‘РѕР±РЅРѕРІР»РµРЅРёРµ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ", value=bool(st.session_state.get("opt_auto_refresh", auto_refresh)), key="opt_auto_refresh")
    with cS2:
        minutes = st.slider("Р’СЂРµРјСЏ РѕРїС‚РёРјРёР·Р°С†РёРё (РјРёРЅ)", min_value=0.2, max_value=120.0, value=float(st.session_state.get("opt_minutes", minutes)), step=0.2, key="opt_minutes")
        jobs_max = int(max(1, min(32, (os.cpu_count() or 4))))
        jobs = st.slider("РџР°СЂР°Р»Р»РµР»СЊРЅС‹Рµ jobs", min_value=1, max_value=jobs_max, value=int(st.session_state.get("opt_jobs", jobs)), step=1, key="opt_jobs")

    with st.expander("Р Р°СЃС€РёСЂРµРЅРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё РѕРїС‚РёРјРёР·Р°С†РёРё", expanded=True):
        seed_candidates = st.number_input("seed_candidates", min_value=1, max_value=9999, value=int(st.session_state.get("opt_seed_candidates", seed_candidates)), step=1, key="opt_seed_candidates")
        seed_conditions = st.number_input("seed_conditions", min_value=1, max_value=9999, value=int(st.session_state.get("opt_seed_conditions", seed_conditions)), step=1, key="opt_seed_conditions")
        flush_every = st.number_input("flush_every", min_value=1, max_value=9999, value=int(st.session_state.get("opt_flush_every", flush_every)), step=1, key="opt_flush_every")
        progress_every_sec = st.number_input("progress_every_sec", min_value=0.1, max_value=60.0, value=float(st.session_state.get("opt_progress_every_sec", progress_every_sec)), step=0.1, key="opt_progress_every_sec")
        refresh_sec = st.number_input("refresh_sec", min_value=0.2, max_value=10.0, value=float(st.session_state.get("opt_refresh_sec", refresh_sec)), step=0.1, key="opt_refresh_sec")

    # СЃРѕС…СЂР°РЅСЏРµРј РЅР°СЃС‚СЂРѕР№РєРё РѕР±СЂР°С‚РЅРѕ РІ session_state (РµРґРёРЅС‹Р№ РёСЃС‚РѕС‡РЅРёРє РїСЂР°РІРґС‹)
    st.session_state["out_prefix"] = str(out_prefix)
    st.session_state["opt_settings"] = {
        "minutes": float(minutes),
        "seed_candidates": int(seed_candidates),
        "seed_conditions": int(seed_conditions),
        "jobs": int(jobs),
        "flush_every": int(flush_every),
        "progress_every_sec": float(progress_every_sec),
        "auto_refresh": bool(auto_refresh),
        "refresh_sec": float(refresh_sec),
    }

    st.subheader("Р‘С‹СЃС‚СЂС‹Р№ РїСЂРѕРіРѕРЅ С‚РµСЃС‚РѕРІ (baseline)")
    st.caption("РџСЂРѕРІРµСЂРєР° Р°РґРµРєРІР°С‚РЅРѕСЃС‚Рё РјРѕРґРµР»Рё РЅР° С‚РµРєСѓС‰РёС… РїР°СЂР°РјРµС‚СЂР°С….")

    tests_cfg = {"suite": suite_override}
    tests = worker_mod.build_test_suite(tests_cfg)

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

        if st.session_state.baseline_df is None:
            _cached = load_baseline_cache(_cache_dir_preview)
            if _cached is not None:
                st.session_state.baseline_df = _cached["baseline_df"]
                st.session_state.baseline_tests_map = _cached["tests_map"]
                st.session_state.baseline_param_hash = _base_hash_preview
                # РґРµС‚Р°Р»СЊРЅС‹Рµ РїСЂРѕРіРѕРЅС‹ РЅРµ РіСЂСѓР·РёРј С†РµР»РёРєРѕРј вЂ” Р±СѓРґСѓС‚ РїРѕРґС…РІР°С‡РµРЅС‹ РїРѕ Р·Р°РїСЂРѕСЃСѓ
                log_event("baseline_loaded_cache", cache_dir=str(_cache_dir_preview))
                st.info(f"Baseline Р·Р°РіСЂСѓР¶РµРЅ РёР· РєСЌС€Р°: {_cache_dir_preview.name}")
    except Exception:
        pass

    test_names = [x[0] for x in tests]
    pick = st.selectbox("РўРµСЃС‚", options=["(РІСЃРµ)"] + test_names, index=0)

    if st.button("Р—Р°РїСѓСЃС‚РёС‚СЊ baseline"):
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

        # РѕС‚РјРµС‚РєР°: baseline РѕР±РЅРѕРІРёР»СЃСЏ (РґР»СЏ Р°РІС‚РѕвЂ‘РґРµС‚Р°Р»СЊРЅРѕРіРѕ С‚СЂРёРіРіРµСЂР°)
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
if SHOW_RESULTS or SHOW_TOOLS:
    # Р”РµС‚Р°Р»СЊРЅС‹Рµ РіСЂР°С„РёРєРё + Р°РЅРёРјР°С†РёСЏ (baseline)
    # -------------------------------
    st.divider()
    st.header("Baseline: СЂРµР·СѓР»СЊС‚Р°С‚С‹ Рё РґРёР°РіРЅРѕСЃС‚РёРєР°")
    st.caption(
        "РЎРЅР°С‡Р°Р»Р° Р·Р°РїСѓСЃС‚РёС‚Рµ baseline. Р—Р°С‚РµРј РІС‹Р±РµСЂРёС‚Рµ РѕРґРёРЅ С‚РµСЃС‚ Рё РїРѕР»СѓС‡РёС‚Рµ РїРѕР»РЅС‹Р№ Р»РѕРі (record_full=True): "
        "РіСЂР°С„РёРєРё P/Q/РєСЂРµРЅ/С‚Р°РЅРіР°Р¶/СЃРёР»С‹ Рё MVP-Р°РЅРёРјР°С†РёСЋ РїРѕС‚РѕРєРѕРІ."
    )

    cur_hash = stable_obj_hash(base_override)
    if st.session_state.baseline_df is None:
        st.info("РќРµС‚ baseline-С‚Р°Р±Р»РёС†С‹. РќР°Р¶РјРёС‚Рµ вЂР—Р°РїСѓСЃС‚РёС‚СЊ baselineвЂ™ РІС‹С€Рµ.")
    elif st.session_state.baseline_param_hash and st.session_state.baseline_param_hash != cur_hash:
        st.warning(
            "РџР°СЂР°РјРµС‚СЂС‹ РёР·РјРµРЅРёР»РёСЃСЊ РїРѕСЃР»Рµ baseline. Р§С‚РѕР±С‹ РіСЂР°С„РёРєРё/Р°РЅРёРјР°С†РёСЏ СЃРѕРѕС‚РІРµС‚СЃС‚РІРѕРІР°Р»Рё С‚РµРєСѓС‰РёРј РїР°СЂР°РјРµС‚СЂР°Рј, "
            "РїРµСЂРµР·Р°РїСѓСЃС‚РёС‚Рµ baseline."
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
            st.info("Р’ baseline РЅРµС‚ РґРѕСЃС‚СѓРїРЅС‹С… С‚РµСЃС‚РѕРІ (РїСЂРѕРІРµСЂСЊС‚Рµ С‚РµСЃС‚вЂ‘РЅР°Р±РѕСЂ).")
        else:
            colG1, colG2, colG3 = st.columns([1.2, 1.0, 1.0], gap="large")
            with colG1:
                test_pick = st.selectbox("РўРµСЃС‚ РґР»СЏ РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°", options=avail, index=0, key="detail_test_pick")
            with colG2:
                max_points = st.number_input("РњР°РєСЃ С‚РѕС‡РµРє (downsample)", min_value=200, max_value=5000, value=1200, step=100, key="detail_max_points")
            with colG3:
                want_full = st.checkbox("РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ record_full (РїРѕС‚РѕРєРё/СЃРѕСЃС‚РѕСЏРЅРёСЏ)", value=True, key="detail_want_full")
                auto_detail_on_select = st.checkbox(
                    "РђРІС‚РѕвЂ‘СЂР°СЃС‡С‘С‚ РїСЂРё РІС‹Р±РѕСЂРµ С‚РµСЃС‚Р°",
                    value=True,
                    key="auto_detail_on_select",
                    help="Р•СЃР»Рё РІРєР»СЋС‡РµРЅРѕ Рё РєСЌС€ РїСѓСЃС‚, Р±СѓРґРµС‚ СЃС‡РёС‚Р°С‚СЊСЃСЏ РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ (РјРѕР¶РµС‚ РіСЂСѓР·РёС‚СЊ CPU).",
                )
                auto_export_npz = st.checkbox(
                    "РђРІС‚РѕвЂ‘СЌРєСЃРїРѕСЂС‚ NPZ (osc_dir)",
                    value=True,
                    key="auto_export_npz",
                    help="Р­РєСЃРїРѕСЂС‚РёСЂСѓРµС‚ Txx_osc.npz РІ РїР°РїРєСѓ osc_dir (СЃРј. РљР°Р»РёР±СЂРѕРІРєР°). РќСѓР¶РЅРѕ РґР»СЏ oneclick/autopilot.",
                )

                auto_export_anim_latest = st.checkbox(
                    "РђРІС‚РѕвЂ‘СЌРєСЃРїРѕСЂС‚ anim_latest (Desktop Animator)",
                    value=True,
                    key="auto_export_anim_latest",
                    help=(
                        "РџРёС€РµС‚ workspace/exports/anim_latest.npz + anim_latest.json. "
                        "Desktop Animator РІ СЂРµР¶РёРјРµ --follow Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РїРµСЂРµР·Р°РіСЂСѓР·РёС‚ Р°РЅРёРјР°С†РёСЋ."
                    ),
                )

            # Desktop Animator integration (minimal manual steps)
            with st.expander("Desktop Animator (Windows) вЂ” РёРЅС„РѕСЂРјР°С‚РёРІРЅР°СЏ Р°РЅРёРјР°С†РёСЏ", expanded=True):
                # Recompute current detail cache key here (this expander appears before the main cache_key assignment).
                _info_pick = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
                _detail_dt = float(_info_pick.get("dt", 0.01) or 0.01)
                _detail_t_end = float(_info_pick.get("t_end", 1.0) or 1.0)
                _cache_key_now = make_detail_cache_key(cur_hash, test_pick, _detail_dt, _detail_t_end, max_points, want_full)

                _npz_p, _ptr_p = get_anim_latest_paths()
                st.write("Pointer (Animator watches this file):")
                st.code(str(_ptr_p))

                # Show current status
                _st = []
                try:
                    if _npz_p.exists():
                        _st.append(f"NPZ: вњ… {_npz_p.name} ({_npz_p.stat().st_size/1024:.1f} KB)")
                    else:
                        _st.append(f"NPZ: вќЊ {_npz_p.name} (РЅРµС‚)")
                    if _ptr_p.exists():
                        _st.append(f"PTR: вњ… {_ptr_p.name}")
                    else:
                        _st.append(f"PTR: вќЊ {_ptr_p.name} (РЅРµС‚)")
                except Exception:
                    pass
                if _st:
                    st.info("\n".join(_st))

                colA1, colA2, colA3 = st.columns([1.0, 1.0, 1.2], gap="medium")
                with colA1:
                    if st.button("Р—Р°РїСѓСЃС‚РёС‚СЊ Animator (--follow)", key="launch_desktop_animator"):
                        try:
                            cmd = [sys.executable, "-m", "pneumo_solver_ui.desktop_animator.main", "--follow", "--theme", "dark"]
                            # Streamlit runs from project root typically; force cwd near UI package to resolve imports/assets.
                            start_worker(cmd, cwd=HERE)
                            st.success("Desktop Animator Р·Р°РїСѓС‰РµРЅ.")
                        except Exception as e:
                            st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РїСѓСЃС‚РёС‚СЊ Desktop Animator: {e}")
                    if st.button("Р—Р°РїСѓСЃС‚РёС‚СЊ Mnemo (--follow)", key="launch_desktop_mnemo"):
                        try:
                            cmd = [sys.executable, "-m", "pneumo_solver_ui.desktop_mnemo.main", "--follow", "--theme", "dark"]
                            start_worker(cmd, cwd=HERE)
                            st.success("Desktop Mnemo Р·Р°РїСѓС‰РµРЅ.")
                        except Exception as e:
                            st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РїСѓСЃС‚РёС‚СЊ Desktop Mnemo: {e}")
                with colA2:
                    if st.button("РћС‚РєСЂС‹С‚СЊ РїР°РїРєСѓ exports", key="open_exports_dir"):
                        try:
                            if os.name == "nt":
                                os.startfile(str(WORKSPACE_EXPORTS_DIR))  # type: ignore[attr-defined]
                            else:
                                st.warning("РљРЅРѕРїРєР° РѕС‚РєСЂС‹С‚РёСЏ РїР°РїРєРё СЂР°Р±РѕС‚Р°РµС‚ С‚РѕР»СЊРєРѕ РЅР° Windows.")
                        except Exception as e:
                            st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РєСЂС‹С‚СЊ РїР°РїРєСѓ: {e}")
                with colA3:
                    # Manual export button (useful if auto-export disabled)
                    if st.button("Р­РєСЃРїРѕСЂС‚РёСЂРѕРІР°С‚СЊ С‚РµРєСѓС‰РёР№ РґРµС‚Р°Р»СЊРЅС‹Р№ Р»РѕРі РІ anim_latest", key="export_anim_latest_now"):
                        try:
                            det_now = st.session_state.baseline_full_cache.get(_cache_key_now)
                            if not det_now:
                                st.warning("РЎРЅР°С‡Р°Р»Р° РІС‹РїРѕР»РЅРёС‚Рµ РґРµС‚Р°Р»СЊРЅС‹Р№ СЂР°СЃС‡С‘С‚, С‡С‚РѕР±С‹ РїРѕСЏРІРёР»СЃСЏ РєСЌС€.")
                            else:
                                export_anim_latest_bundle(
                                    det_now.get("df_main"),
                                    df_p=det_now.get("df_p"),
                                    df_q=det_now.get("df_mdot"),
                                    df_open=det_now.get("df_open"),
                                    meta=(det_now.get("meta") or {}),
                                )
                                st.success("Р­РєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅРѕ РІ anim_latest.")
                        except Exception as e:
                            st.error(f"Р­РєСЃРїРѕСЂС‚ РЅРµ СѓРґР°Р»СЃСЏ: {e}")

                st.caption(
                    "Р РµРєРѕРјРµРЅРґСѓРµРјС‹Р№ workflow: РѕС‚РєСЂРѕР№С‚Рµ Desktop Animator (follow), Р·Р°С‚РµРј РЅР°Р¶РјРёС‚Рµ 'Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі'. "
                    "Р•СЃР»Рё РІРєР»СЋС‡С‘РЅ Р°РІС‚РѕвЂ‘СЌРєСЃРїРѕСЂС‚ вЂ” Desktop Animator Рё Desktop Mnemo РѕР±РЅРѕРІРёС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё."
                )

            # dt/t_end Р±РµСЂС‘Рј РёР· suite РґР»СЏ РІС‹Р±СЂР°РЅРЅРѕРіРѕ С‚РµСЃС‚Р° вЂ” СЌС‚Рѕ С‡Р°СЃС‚СЊ cache_key Рё РїР°СЂР°РјРµС‚СЂРѕРІ simulate()
            info_pick = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
            detail_dt = float(info_pick.get("dt", 0.01) or 0.01)
            detail_t_end = float(info_pick.get("t_end", 1.0) or 1.0)
            # СЃРѕС…СЂР°РЅСЏРµРј РґР»СЏ РґСЂСѓРіРёС… СЃС‚СЂР°РЅРёС†/РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ
            st.session_state["detail_dt_pick"] = detail_dt
            st.session_state["detail_t_end_pick"] = detail_t_end

            run_detail = st.button("Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Рё РїРѕРєР°Р·Р°С‚СЊ", key="run_detail")

            colDAll1, colDAll2 = st.columns([1.0, 1.0])
            with colDAll1:
                run_detail_all = st.button("Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Р”Р›РЇ Р’РЎР•РҐ С‚РµСЃС‚РѕРІ", key="run_detail_all")
            with colDAll2:
                export_npz_all = st.button("Р­РєСЃРїРѕСЂС‚ NPZ Р”Р›РЇ Р’РЎР•РҐ (РёР· РєСЌС€Р°)", key="export_npz_all")

                cache_key = make_detail_cache_key(cur_hash, test_pick, detail_dt, detail_t_end, max_points, want_full)

            # --- РђРІС‚РѕвЂ‘РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: Р·Р°РїСѓСЃРєР°С‚СЊ РўРћР›Р¬РљРћ РїРѕ С‚СЂРёРіРіРµСЂСѓ
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
                            ck = make_detail_cache_key(
                                cur_hash,
                                tn,
                                float(info_j.get("dt", detail_dt) or detail_dt),
                                float(info_j.get("t_end", detail_t_end) or detail_t_end),
                                max_points,
                                want_full,
                            )
                            if ck in st.session_state.baseline_full_cache:
                                prog.progress(j / n_total)
                                continue
                            test_j = info_j.get("test")
                            dt_j = float(info_j.get("dt", 0.01) or 0.01)
                            t_end_j = float(info_j.get("t_end", 1.0) or 1.0)
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
                            ck = make_detail_cache_key(
                                cur_hash,
                                tn,
                                float(info_j.get("dt", detail_dt) or detail_dt),
                                float(info_j.get("t_end", detail_t_end) or detail_t_end),
                                max_points,
                                want_full,
                            )
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
                # Р’Р°Р¶РЅРѕ: auto_detail РјРѕР¶РµС‚ РІС‹Р·С‹РІР°С‚СЊСЃСЏ РјРЅРѕРіРѕ СЂР°Р· РёР·вЂ‘Р·Р° С‡Р°СЃС‚С‹С… rerun'РѕРІ. Р•СЃР»Рё РєСЌС€ РїРѕ РєР°РєРѕР№вЂ‘С‚Рѕ РїСЂРёС‡РёРЅРµ
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
                    _dg.setdefault("last_key", None)
                    _dg.setdefault("last_end_ts", 0.0)
                    _dg.setdefault("suppressed", 0)
                    _dg.setdefault("failed_key", None)
                    _dg.setdefault("failed_ts", 0.0)
                    _dg.setdefault("failed_err", None)
                    _dg.setdefault("pid", os.getpid())
                    _dg.setdefault("last_start_ts", 0.0)
                    _dg.setdefault("progress", 0.0)  # UI-only (service) progress marker
                    st.session_state["detail_guard"] = _dg

                    _now = float(time.time())
                    _same_key = (_dg.get("last_key") == cache_key)
                    _same_key_recent = _same_key and (_now - float(_dg.get("last_end_ts") or 0.0) < 15.0)
                    _already_running = bool(_dg.get("in_progress")) and _same_key
                    
                    # Stale guard reset: if Streamlit/session restarted or previous run crashed,
                    # do NOT permanently suppress the button.
                    _cur_pid = os.getpid()
                    _guard_pid = int(_dg.get("pid") or _cur_pid)
                    _start_ts = float(_dg.get("last_start_ts") or 0.0)
                    _age = (_now - _start_ts) if (_start_ts > 0.0) else 0.0
                    if bool(_dg.get("in_progress")) and (_guard_pid != _cur_pid or _start_ts <= 0.0 or _age > 1800.0):
                        st.warning("вљ пёЏ РћР±РЅР°СЂСѓР¶РµРЅ Р·Р°РІРёСЃС€РёР№/СѓСЃС‚Р°СЂРµРІС€РёР№ РїСЂРѕРіРѕРЅ вЂ” СЃР±СЂР°СЃС‹РІР°СЋ Р±Р»РѕРєРёСЂРѕРІРєСѓ РїРѕРІС‚РѕСЂРЅРѕРіРѕ Р·Р°РїСѓСЃРєР°.")
                        _dg["in_progress"] = False
                        _dg["pid"] = _cur_pid
                        _dg["last_start_ts"] = _now
                        st.session_state["detail_guard"] = _dg
                        _already_running = False

                    # Manual click must never be blocked by a stuck in_progress flag.
                    # Streamlit is single-threaded per session; if we reached this code path,
                    # we are not "inside" the detailed run right now.
                    if run_detail and _already_running:
                        log_event(
                            "detail_guard_forced_reset",
                            reason="manual_click",
                            key=str(cache_key),
                            test=str(test_pick),
                            guard=_dg,
                        )
                        st.warning(
                            "вљ пёЏ РћР±РЅР°СЂСѓР¶РµРЅ Р·Р°СЃС‚СЂСЏРІС€РёР№ С„Р»Р°Рі 'РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ'. "
                            "РЎР±СЂР°СЃС‹РІР°СЋ С„Р»Р°Рі Рё Р·Р°РїСѓСЃРєР°СЋ Р·Р°РЅРѕРІРѕ."
                        )
                        _dg["in_progress"] = False
                        _dg["pid"] = _cur_pid
                        _dg["last_start_ts"] = _now
                        st.session_state["detail_guard"] = _dg
                        _already_running = False

                    log_event(
                        "auto_detail_trigger",
                        test=test_pick,
                        base_hash=cur_hash,
                        max_points=int(max_points),
                        want_full=bool(want_full),
                        cache_hit=False,
                        already_running=_already_running,
                        same_key_recent=_same_key_recent,
                    )

                    if _already_running:
                        # Show a placeholder progress bar to avoid the "no progress" confusion.
                        _p0 = float(_dg.get("progress") or 0.0)
                        st.progress(min(max(_p0, 0.0), 1.0), text="Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ СѓР¶Рµ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏвЂ¦")
                        st.info("Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ СѓР¶Рµ РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ (РїРѕРІС‚РѕСЂРЅС‹Р№ Р·Р°РїСѓСЃРє РїРѕРґР°РІР»РµРЅ).")
                        log_event("detail_autorun_already_running", test=test_pick)

                    elif (_dg.get('failed_key') == cache_key) and auto_trigger and (not run_detail):
                        st.warning('РђРІС‚РѕвЂ‘РґРµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ РїРѕРґР°РІР»РµРЅ: РїСЂРµРґС‹РґСѓС‰Р°СЏ РїРѕРїС‹С‚РєР° РґР»СЏ СЌС‚РѕРіРѕ РЅР°Р±РѕСЂР° Р·Р°РІРµСЂС€РёР»Р°СЃСЊ РѕС€РёР±РєРѕР№. РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ **"Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРі Рё РїРѕРєР°Р·Р°С‚СЊ"** РґР»СЏ РїРѕРІС‚РѕСЂР°.')
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
                        _dg["progress"] = 0.0
                        st.session_state["detail_guard"] = _dg

                        # Even if the solver itself runs in a single call, we must show that
                        # a long operation started.
                        _pbar = st.progress(0.02, text="Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РїРѕРґРіРѕС‚РѕРІРєР°вЂ¦")
                        _dg["progress"] = 0.02
                        st.session_state["detail_guard"] = _dg

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
                            try:
                                _pbar.progress(0.08, text="Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: Р·Р°РїСѓСЃРє СЃРёРјСѓР»СЏС†РёРёвЂ¦")
                                _dg["progress"] = 0.08
                                st.session_state["detail_guard"] = _dg
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
                            try:
                                _pbar.progress(0.85, text="Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РѕР±СЂР°Р±РѕС‚РєР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІвЂ¦")
                                _dg["progress"] = 0.85
                                st.session_state["detail_guard"] = _dg
                            except Exception:
                                pass
                            t_sec = float(time.perf_counter() - t0_perf)
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
                                    "loaded_from_cache": False,
                                    "geometry": supplement_animator_geometry_meta(build_geometry_meta_from_base(base_override, log=_APP_LOGGER.warning), log=_APP_LOGGER.warning),
                                }
                            }

                            try:
                                _pbar.progress(1.0, text="Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РіРѕС‚РѕРІРѕ")
                                _dg["progress"] = 1.0
                                st.session_state["detail_guard"] = _dg
                            except Exception:
                                pass

                            # --- Desktop Animator: auto-export anim_latest ---
                            if bool(auto_export_anim_latest) and bool(want_full):
                                try:
                                    # Keep meta compact but useful for animator (geometry + provenance).
                                    # Geometry for new bundles goes into canonical nested meta.geometry.
                                    _geom = supplement_animator_geometry_meta(build_geometry_meta_from_base(base_override, log=_APP_LOGGER.warning), log=_APP_LOGGER.warning)
                                    _missing_geom = [k for k in ("wheelbase_m", "track_m") if k not in _geom]
                                    if _missing_geom:
                                        _APP_LOGGER.warning(
                                            "[auto-export] Missing canonical geometry for meta.geometry: %s",
                                            ", ".join(_missing_geom),
                                        )
                                    export_anim_latest_bundle(
                                        df_main,
                                        df_p=df_p,
                                        df_q=df_mdot,
                                        df_open=df_open,
                                        meta={
                                            "source": "ui_anim_latest",
                                            "app_release": APP_RELEASE,
                                            "cache_key": str(cache_key),
                                            "test_name": str(test_pick),
                                            "dt": float(dt_j),
                                            "t_end": float(t_end_j),
                                            "max_points": int(max_points),
                                            "base_hash": str(cur_hash),
                                            "geometry": _geom,
                                        },
                                    )
                                    log_event("anim_latest_export", test=str(test_pick), cache_key=str(cache_key))
                                except Exception as _e:
                                    st.warning(f"РђРІС‚Рѕ-СЌРєСЃРїРѕСЂС‚ anim_latest РЅРµ СѓРґР°Р»СЃСЏ: {_e}")
                                    log_event("anim_latest_export_error", err=str(_e), test=str(test_pick), cache_key=str(cache_key))
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
                            _dg_ok = dict(st.session_state.get("detail_guard") or {})
                            _dg_ok["failed_key"] = None
                            _dg_ok["failed_ts"] = 0.0
                            _dg_ok["failed_err"] = None
                            st.session_state["detail_guard"] = _dg_ok
                        except Exception as e:
                            st.error(f"РћС€РёР±РєР° РґРµС‚Р°Р»СЊРЅРѕРіРѕ РїСЂРѕРіРѕРЅР°: {e}")
                            log_event("detail_error", err=str(e), test=test_pick)
                            try:
                                _pbar.progress(1.0, text="Р”РµС‚Р°Р»СЊРЅС‹Р№ РїСЂРѕРіРѕРЅ: РѕС€РёР±РєР°")
                            except Exception:
                                pass
                            _dg_fail = dict(st.session_state.get("detail_guard") or {})
                            _dg_fail["failed_key"] = str(cache_key)
                            _dg_fail["failed_ts"] = float(time.time())
                            _dg_fail["failed_err"] = str(e)
                            st.session_state["detail_guard"] = _dg_fail
                        finally:
                            if st.session_state.get("detail_auto_pending") == cache_key:
                                st.session_state["detail_auto_pending"] = None
                            clear_detail_force_fresh(st.session_state, cache_key=str(cache_key))
                            _dg2 = dict(st.session_state.get("detail_guard") or {})
                            _dg2["in_progress"] = False
                            _dg2["last_key"] = str(cache_key)
                            _dg2["last_end_ts"] = float(time.time())
                            _dg2.setdefault("progress", float(_dg.get("progress") or 0.0))
                            _dg2.setdefault("suppressed", int(_dg.get("suppressed") or 0))
                            st.session_state["detail_guard"] = _dg2
                if cache_key in st.session_state.baseline_full_cache:
                    det = st.session_state.baseline_full_cache[cache_key]
                    _det_meta_ui = dict(det.get("meta") or {})
                    _det_ts = str(_det_meta_ui.get("ts") or "")
                    _det_src = "РєСЌС€" if ("cache_file" in _det_meta_ui or _det_meta_ui.get("loaded_from_cache")) else "СЃРІРµР¶РёР№ СЂР°СЃС‡С‘С‚"
                    if _det_ts:
                        st.caption(f"Р”РµС‚Р°Р»СЊРЅС‹Р№ Р»РѕРі: {_det_src}; РјРµС‚РєР° РІСЂРµРјРµРЅРё: {_det_ts}.")
                    else:
                        st.caption(f"Р”РµС‚Р°Р»СЊРЅС‹Р№ Р»РѕРі: {_det_src}.")
                    df_main = det.get("df_main")
                    df_p = det.get("df_p")
                    df_mdot = det.get("df_mdot")
                    df_open = det.get("df_open")
                    df_Eedges = det.get("df_Eedges")
                    df_Egroups = det.get("df_Egroups")

                    # -----------------------------------
                    # Global timeline (shared playhead)
                    # -----------------------------------
                    time_s = []
                    if df_main is not None and "РІСЂРµРјСЏ_СЃ" in df_main.columns:
                        time_s = df_main["РІСЂРµРјСЏ_СЃ"].astype(float).tolist()
                    elif df_mdot is not None and "РІСЂРµРјСЏ_СЃ" in df_mdot.columns:
                        time_s = df_mdot["РІСЂРµРјСЏ_СЃ"].astype(float).tolist()

                    # Р’Р°Р¶РЅРѕ: dataset_id РґР»СЏ РєРѕРјРїРѕРЅРµРЅС‚РѕРІ РґРµР»Р°РµРј *СѓРЅРёРєР°Р»СЊРЅС‹Рј РІРЅСѓС‚СЂРё UIвЂ‘СЃРµСЃСЃРёРё*.
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
                            "vacuum_label": "Вакуум мин, атм(изб)",
                            "pmax_label": "Запас к Pmax, атм",
                            "vacuum_state_key": "events_vacuum_min_atm",
                            "pmax_state_key": "events_pmax_margin_atm",
                        },
                        compute_results_events_kwargs={
                            "compute_events_fn": compute_events,
                            "base_override": base_override,
                            "p_atm": P_ATM,
                            "df_main": df_main,
                            "df_p": df_p,
                            "df_open": df_open,
                            "test": test,
                            "vacuum_state_key": "events_vacuum_min_atm",
                            "pmax_state_key": "events_pmax_margin_atm",
                            "vacuum_kwarg_name": "vacuum_min_gauge_atm",
                            "pmax_kwarg_name": "pmax_margin_atm",
                        },
                    )
                    dataset_id_ui = str(_results_runtime["dataset_id_ui"])
                    playhead_x = _results_runtime["playhead_x"]
                    events_list = _results_runtime["events_list"]

                    # Р’Р°Р¶РЅРѕ: st.tabs РЅРµ "Р»РµРЅРёРІС‹Р№" вЂ” РєРѕРґ РІРЅСѓС‚СЂРё РІСЃРµС… С‚Р°Р±РѕРІ РёСЃРїРѕР»РЅСЏРµС‚СЃСЏ РїСЂРё РєР°Р¶РґРѕРј rerun.
                    # РџСЂРё Р°РЅРёРјР°С†РёРё (auto-refresh) СЌС‚Рѕ РІС‹РіР»СЏРґРёС‚ РєР°Рє "Р±РµСЃРєРѕРЅРµС‡РЅС‹Р№ СЂР°СЃС‡С‘С‚".
                    # РџРѕСЌС‚РѕРјСѓ РёСЃРїРѕР»СЊР·СѓРµРј СЏРІРЅС‹Р№ СЃРµР»РµРєС‚РѕСЂ Рё СЂРµРЅРґРµСЂРёРј С‚РѕР»СЊРєРѕ РІС‹Р±СЂР°РЅРЅСѓСЋ РІРµС‚РєСѓ.
                    if SHOW_TOOLS and (not SHOW_RESULTS):
                        _baseline_view_opts = ["РџРѕС‚РѕРєРё", "Р­РЅРµСЂРіРѕвЂ‘Р°СѓРґРёС‚"]
                    else:
                        _baseline_view_opts = ["Р“СЂР°С„РёРєРё", "РђРЅРёРјР°С†РёСЏ"]

                    render_app_results_surface_section(
                        st,
                        session_state=st.session_state,
                        options=_baseline_view_opts,
                        cur_hash=cur_hash,
                        test_pick=test_pick,
                        cache_key=cache_key,
                        dataset_id=dataset_id_ui,
                        time_s=time_s,
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
                        pressure_from_pa_fn=pa_abs_to_atm_g,
                        pressure_divisor=ATM_PA,
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
                        mech_fallback_module=mech_fb,
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
                    )





if SHOW_RUN:
    # -------------------------------
    # РћРїС‚РёРјРёР·Р°С†РёСЏ (С„РѕРЅ)
    # -------------------------------
    st.divider()
    st.header("РћРїС‚РёРјРёР·Р°С†РёСЏ (С„РѕРЅ)")

    colO1, colO2, colO3 = st.columns([1.2, 1.0, 1.0], gap="large")

    with colO1:
        st.markdown("**РљРѕРјР°РЅРґС‹**")
        btn_start = st.button("РЎС‚Р°СЂС‚ РѕРїС‚РёРјРёР·Р°С†РёРё", disabled=pid_alive(st.session_state.opt_proc) or bool(param_errors) or bool(suite_errors))
        colS1, colS2 = st.columns(2)
        with colS1:
            btn_stop_soft = st.button("РЎС‚РѕРї (РјСЏРіРєРѕ)", disabled=not pid_alive(st.session_state.opt_proc), help="РЎРѕР·РґР°С‘С‚ STOPвЂ‘С„Р°Р№Р». РћРїС‚РёРјРёР·Р°С‚РѕСЂ СЃР°Рј РєРѕСЂСЂРµРєС‚РЅРѕ Р·Р°РІРµСЂС€РёС‚СЃСЏ Рё СЃРѕС…СЂР°РЅРёС‚ CSV/РїСЂРѕРіСЂРµСЃСЃ.")
        with colS2:
            btn_stop_hard = st.button("РЎС‚РѕРї (Р¶С‘СЃС‚РєРѕ)", disabled=not pid_alive(st.session_state.opt_proc), help="РЎРѕР·РґР°С‘С‚ STOPвЂ‘С„Р°Р№Р» Рё РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕ Р·Р°РІРµСЂС€Р°РµС‚ РїСЂРѕС†РµСЃСЃ. РСЃРїРѕР»СЊР·СѓР№С‚Рµ С‚РѕР»СЊРєРѕ РµСЃР»Рё РјСЏРіРєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР° РЅРµ СЃСЂР°Р±Р°С‚С‹РІР°РµС‚.")

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
                progress_path = out_csv_path.with_suffix("")
                progress_path = str(progress_path) + "_progress.json"
                if os.path.exists(progress_path):
                    with open(progress_path, "r", encoding="utf-8") as f:
                        prog = json.load(f)
                    try:
                        _mtime = os.path.getmtime(progress_path)
                        _age = time.time() - float(_mtime)
                        st.caption(f"РџСЂРѕРіСЂРµСЃСЃвЂ‘С„Р°Р№Р» РѕР±РЅРѕРІР»С‘РЅ {_age:.1f} СЃ РЅР°Р·Р°Рґ: {progress_path}")
                        # Р•СЃР»Рё РїСЂРѕС†РµСЃСЃ Р¶РёРІ, Р° С„Р°Р№Р» РґР°РІРЅРѕ РЅРµ РѕР±РЅРѕРІР»СЏР»СЃСЏ вЂ” РІРµСЂРѕСЏС‚РЅРѕ Р·Р°РІРёСЃ/СѓРїР°Р» РёР»Рё РїРёС€РµС‚ РІ РґСЂСѓРіРѕР№ РєР°С‚Р°Р»РѕРі.
                        if pid_alive(st.session_state.opt_proc) and (_age > max(300.0, 10.0*float(refresh_sec) + 5.0)):
                            st.caption("вљ пёЏ РџСЂРѕРіСЂРµСЃСЃвЂ‘С„Р°Р№Р» РґР°РІРЅРѕ РЅРµ РѕР±РЅРѕРІР»СЏР»СЃСЏ. Р•СЃР»Рё СЌС‚Рѕ РЅРµРѕР¶РёРґР°РЅРЅРѕ вЂ” РїСЂРѕРІРµСЂСЊС‚Рµ, С‡С‚Рѕ worker РїРёС€РµС‚ progress.json РІ С‚РѕС‚ Р¶Рµ РєР°С‚Р°Р»РѕРі Рё С‡С‚Рѕ СЂР°СЃС‡С‘С‚ РЅРµ Р·Р°РІРёСЃ.")
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
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = str(HERE / f"{out_prefix}_{ts}.csv")
        base_json = str(HERE / f"{out_prefix}_{ts}_base.json")
        ranges_json = str(HERE / f"{out_prefix}_{ts}_ranges.json")
        suite_json = str(HERE / f"{out_prefix}_{ts}_suite.json")

        base_effective, ranges_effective, suite_effective, optimization_input_audit = sanitize_optimization_inputs(
            base_override,
            ranges_override,
            suite_override,
        )
        write_json(base_effective, Path(base_json))
        write_json(ranges_effective, Path(ranges_json))
        write_json(suite_effective, Path(suite_json))
        write_json(optimization_input_audit, Path(os.path.splitext(out_csv)[0] + "_input_audit.json"))

        # РЎРѕР·РґР°С‘Рј С„Р°Р№Р» РїСЂРѕРіСЂРµСЃСЃР° Р·Р°СЂР°РЅРµРµ (С‡С‚РѕР±С‹ UI РЅРµ РїРёСЃР°Р» В«С„Р°Р№Р» РїСЂРѕРіСЂРµСЃСЃР° РЅРµ СЃРѕР·РґР°РЅВ» РёР·вЂ‘Р·Р° РіРѕРЅРєРё РІСЂРµРјРµРЅРё).
        # Worker РїРµСЂРµР·Р°РїРёС€РµС‚ РµРіРѕ СЃРІРѕРёРј РїРµСЂРІС‹Рј update.
        try:
            progress_path = os.path.splitext(out_csv)[0] + "_progress.json"
            write_json({
                "СЃС‚Р°С‚СѓСЃ": "Р·Р°РїСѓС‰РµРЅРѕ",
                "РіРѕС‚РѕРІРѕ_РєР°РЅРґРёРґР°С‚РѕРІ": 0,
                "РїСЂРѕС€Р»Рѕ_СЃРµРє": 0.0,
                "Р»РёРјРёС‚_РјРёРЅСѓС‚": float(minutes),
                "РїРѕСЃР»РµРґРЅРёР№_batch": 0,
                "ok": 0,
                "err": 0,
            }, Path(progress_path))
        except Exception:
            pass

        cmd = [
            sys.executable,
            str(Path(worker_path)),
            "--model", str(Path(model_path)),
            "--out", out_csv,
            "--suite_json", suite_json,
            "--minutes", str(float(minutes)),
            "--seed_candidates", str(int(seed_candidates)), "--seed_conditions", str(int(seed_conditions)),
            "--jobs", str(int(jobs)),
            "--flush_every", str(int(flush_every)),
            "--progress_every_sec", str(float(progress_every_sec)),
            "--base_json", base_json,
            "--ranges_json", ranges_json,
        ]
        # СѓРґР°Р»РёРј СЃС‚РѕРївЂ‘С„Р°Р№Р» (РµСЃР»Рё Р±С‹Р»)
        stop_file = HERE / "STOP_OPTIMIZATION.txt"
        if stop_file.exists():
            try:
                stop_file.unlink()
            except Exception:
                pass

        st.session_state.opt_proc = start_worker(cmd, cwd=HERE)
        st.session_state.opt_out_csv = out_csv
        st.session_state.opt_base_json = base_json
        st.session_state.opt_ranges_json = ranges_json
        do_rerun()

    if 'btn_stop_soft' in locals() and btn_stop_soft:
        # РњСЏРіРєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР°: С‚РѕР»СЊРєРѕ STOPвЂ‘С„Р°Р№Р». РџСЂРѕС†РµСЃСЃ СЃР°Рј Р·Р°РІРµСЂС€РёС‚СЃСЏ, Р·Р°РїРёС€РµС‚ РїСЂРѕРіСЂРµСЃСЃ Рё РєРѕСЂСЂРµРєС‚РЅРѕ Р·Р°РєСЂРѕРµС‚ С„Р°Р№Р»С‹.
        try:
            (HERE / "STOP_OPTIMIZATION.txt").write_text("stop", encoding="utf-8")
        except Exception:
            pass
        st.session_state.opt_stop_requested = True
        do_rerun()

    if 'btn_stop_hard' in locals() and btn_stop_hard:
        # Р–С‘СЃС‚РєР°СЏ РѕСЃС‚Р°РЅРѕРІРєР°: STOPвЂ‘С„Р°Р№Р» + РїСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ Р·Р°РІРµСЂС€РµРЅРёРµ РїСЂРѕС†РµСЃСЃР° (РµСЃР»Рё РЅСѓР¶РЅРѕ).
        try:
            (HERE / "STOP_OPTIMIZATION.txt").write_text("stop", encoding="utf-8")
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


if SHOW_RESULTS:
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

            # (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ) С„РёР»СЊС‚СЂ РїРѕ С€С‚СЂР°С„Сѓ вЂ” РќР• РІРєР»СЋС‡С‘РЅ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ
            use_pen_filter = st.checkbox("Р¤РёР»СЊС‚СЂРѕРІР°С‚СЊ РїРѕ С€С‚СЂР°С„Сѓ С„РёР·РёС‡РЅРѕСЃС‚Рё", value=False, key="pareto_pen_filter")
            if use_pen_filter and "С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°" in df_all2.columns:
                pen_max_default = float(np.nanmax(df_all2["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].astype(float).values))
                pen_max = st.number_input("РњР°РєСЃ С€С‚СЂР°С„ С„РёР·РёС‡РЅРѕСЃС‚Рё (<=)", min_value=0.0, value=pen_max_default, step=0.5, key="pareto_pen_max")
                df_all2 = df_all2[df_all2["С€С‚СЂР°С„_С„РёР·РёС‡РЅРѕСЃС‚Рё_СЃСѓРјРјР°"].astype(float) <= float(pen_max)]
            df_all2 = apply_packaging_surface_filters(st, df_all2, key_prefix="pareto", compact=True)

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

                    top_n = st.number_input("TOPвЂ‘N РґР»СЏ РІС‹РІРѕРґР°", min_value=5, max_value=500, value=10, step=5, key="pareto_topn")

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





if SHOW_RESULTS:
    # -------------------------------
    # Р”РёР°РіСЂР°РјРјС‹: СЃСЂР°РІРЅРµРЅРёРµ РїСЂРѕРіРѕРЅРѕРІ + РІР»РёСЏРЅРёРµ РїР°СЂР°РјРµС‚СЂРѕРІ (Nв†’N)
    # -------------------------------

    st.markdown("---")
    st.subheader("Р”РёР°РіСЂР°РјРјС‹: СЃСЂР°РІРЅРµРЅРёРµ Рё РІР»РёСЏРЅРёРµ РїР°СЂР°РјРµС‚СЂРѕРІ")

    with st.expander("Р’Р»РёСЏРЅРёРµ РїР°СЂР°РјРµС‚СЂРѕРІ (Nв†’N) вЂ” Р°РЅР°Р»РёР· CSV РѕРїС‚РёРјРёР·Р°С†РёРё/СЌРєСЃРїРµСЂРёРјРµРЅС‚РѕРІ", expanded=False):
        st.caption(
            "Coordinated multiple views: Explorer (РІС‹Р±РѕСЂ) в†’ РјР°С‚СЂРёС†С‹/MI в†’ Sankey в†’ PDP/ICE в†’ NГ—N С‡СѓРІСЃС‚РІРёС‚РµР»СЊРЅРѕСЃС‚СЊ в†’ РёРЅС‚РµСЂР°РєС†РёРё (H). "
            "РџРѕРґРґРµСЂР¶РёРІР°РµС‚ reference CSV (A/B/О”), СЃРѕС…СЂР°РЅРµРЅРёРµ СЃРµСЃСЃРёР№ Рё РїРµСЂРµРґР°С‡Сѓ РІС‹Р±СЂР°РЅРЅС‹С… NPZ РІ СЃСЂР°РІРЅРµРЅРёРµ."
        )
        enable_pi = st.checkbox(
            "Р’РєР»СЋС‡РёС‚СЊ Dashboard РІР»РёСЏРЅРёСЏ (РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚СЏР¶С‘Р»С‹Рј РЅР° Р±РѕР»СЊС€РёС… CSV)",
            value=bool(st.session_state.get("pi_enable_dashboard") or False),
            key="pi_enable_dashboard",
            help="Р•СЃР»Рё CSV Р±РѕР»СЊС€РѕР№, РІРєР»СЋС‡Р°Р№С‚Рµ РїРѕСЃР»Рµ РІС‹Р±РѕСЂР° С„Р°Р№Р»Р° Рё С„РёР»СЊС‚СЂРѕРІ."
        )
        if enable_pi:
            try:
                from param_influence_ui import render_param_influence_ui  # type: ignore

                render_param_influence_ui(
                    st=st,
                    default_csv_path=str(csv_to_view or ""),
                    app_dir=HERE,
                    allow_upload=True,
                )
            except Exception as _e:
                st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РєСЂС‹С‚СЊ РјРѕРґСѓР»СЊ РІР»РёСЏРЅРёСЏ РїР°СЂР°РјРµС‚СЂРѕРІ: {_e}")
        else:
            st.info("Р’РєР»СЋС‡РёС‚Рµ С‡РµРєР±РѕРєСЃ РІС‹С€Рµ, С‡С‚РѕР±С‹ РѕС‚СЂРёСЃРѕРІР°С‚СЊ РїРѕР»РЅС‹Р№ Dashboard РІР»РёСЏРЅРёСЏ.")


    with st.expander("РЎСЂР°РІРЅРµРЅРёРµ РїСЂРѕРіРѕРЅРѕРІ (NPZ) вЂ” overlay/smallвЂ‘multiples/О”/РјРµС‚СЂРёРєРё", expanded=False):
        st.caption(
            "РЎСЂР°РІРЅРµРЅРёРµ РЅРµСЃРєРѕР»СЊРєРёС… NPZ (Txx_osc.npz): РЅР°Р»РѕР¶РµРЅРёРµ, smallвЂ‘multiples, СЂР°Р·РЅРѕСЃС‚СЊ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂРµС„РµСЂРµРЅСЃР°, "
            "РјРµС‚СЂРёРєРё (RMS/ptp/mean/min/max), playhead (Р±РµР· Р»РёС€РЅРёС… rerun) Рё СЃРѕС…СЂР°РЅРµРЅРёРµ СЃРµСЃСЃРёР№ СЃСЂР°РІРЅРµРЅРёСЏ."
        )
        st.info(
            "Р•СЃР»Рё Р±СЂР°СѓР·РµСЂ С‚СЏР¶РµР»Рѕ С‚СЏРЅРµС‚ Р±РѕР»СЊС€РёРµ traces вЂ” РёСЃРїРѕР»СЊР·СѓР№С‚Рµ Desktop Compare Viewer: "
            "`INSTALL_DESKTOP_COMPARE_WINDOWS.bat` в†’ `RUN_COMPARE_VIEWER_WINDOWS.bat`."
        )
        enable_cmp = st.checkbox(
            "Р’РєР»СЋС‡РёС‚СЊ Dashboard СЃСЂР°РІРЅРµРЅРёСЏ NPZ",
            value=bool(st.session_state.get("cmp_enable_dashboard") or False),
            key="cmp_enable_dashboard",
            help="Р•СЃР»Рё NPZ РјРЅРѕРіРѕ/С‚СЏР¶С‘Р»С‹Рµ вЂ” РІРєР»СЋС‡Р°Р№С‚Рµ РїРѕСЃР»Рµ РІС‹Р±РѕСЂР° РєР°С‚Р°Р»РѕРіР° Рё РЅСѓР¶РЅС‹С… С„Р°Р№Р»РѕРІ."
        )
        if enable_cmp:
            try:
                from compare_ui import render_compare_ui  # type: ignore

                render_compare_ui(
                    st=st,
                    P_ATM=float(P_ATM),
                    ATM_PA=float(ATM_PA),
                    default_osc_dir=get_osc_dir(),
                    allow_upload=True,
                )
            except Exception as _e:
                st.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РєСЂС‹С‚СЊ РјРѕРґСѓР»СЊ СЃСЂР°РІРЅРµРЅРёСЏ NPZ: {_e}")
        else:
            st.info("Р’РєР»СЋС‡РёС‚Рµ С‡РµРєР±РѕРєСЃ РІС‹С€Рµ, С‡С‚РѕР±С‹ РѕС‚СЂРёСЃРѕРІР°С‚СЊ Dashboard СЃСЂР°РІРЅРµРЅРёСЏ.")


if SHOW_TOOLS:
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
            st.info("Р”Р»СЏ mapping РЅСѓР¶РЅС‹: (1) baseline-suite (СЃРїРёСЃРѕРє С‚РµСЃС‚РѕРІ) Рё (2) С…РѕС‚СЏ Р±С‹ РѕРґРёРЅ С„Р°Р№Р» NPZ/CSV РІ osc_dir.")

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
            "Р•СЃР»Рё СЂРµР°Р»СЊРЅС‹С… Р·Р°РјРµСЂРѕРІ РїРѕРєР° РЅРµС‚ вЂ” РјРѕР¶РЅРѕ РіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ В«СЂР°СЃС‡С‘С‚РЅС‹РµВ» NPZ РёР· С‚РµРєСѓС‰РµРіРѕ baseline "
            "Рё РіРѕРЅСЏС‚СЊ РїР°Р№РїР»Р°Р№РЅС‹ oneclick/autopilot РєР°Рє СЃР°РјРѕРїСЂРѕРІРµСЂРєСѓ С„РѕСЂРјР°С‚РѕРІ Рё РѕР±РІСЏР·РєРё."
        )

        col_fc1, col_fc2, col_fc3 = st.columns(3)

        def _ensure_full_npz_for_all_tests(_mode_label: str) -> tuple[bool, str]:
            """Р“Р°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ РІ osc_dir РµСЃС‚СЊ Txx_osc.npz РґР»СЏ РІСЃРµС… С‚РµСЃС‚РѕРІ baseline-suite.

            Р’РѕР·РІСЂР°С‰Р°РµС‚ (ok, message).
            """
            _tests = list((_tests_map or {}).items())
            if not _tests:
                return False, "РќРµС‚ baseline-suite (СЃРїРёСЃРєР° С‚РµСЃС‚РѕРІ). РЎРЅР°С‡Р°Р»Р° СЂР°СЃСЃС‡РёС‚Р°Р№ baseline."
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

if SHOW_TOOLS:
    # -------------------------------
    # Р”РёР°РіРЅРѕСЃС‚РёРєР° (ZIP РґР»СЏ РѕС‚РїСЂР°РІРєРё)
    # -------------------------------
    with st.expander("Р”РёР°РіРЅРѕСЃС‚РёРєР° вЂ” СЃРѕР±СЂР°С‚СЊ ZIP (РґР»СЏ РѕС‚РїСЂР°РІРєРё)", expanded=False):
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
# РџРѕСЌС‚РѕРјСѓ РёСЃРїРѕР»СЊР·СѓРµРј С„СЂРѕРЅС‚РµРЅРґвЂ‘С‚Р°Р№РјРµСЂ streamlitвЂ‘autorefresh (РµСЃР»Рё СѓСЃС‚Р°РЅРѕРІР»РµРЅ).
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
