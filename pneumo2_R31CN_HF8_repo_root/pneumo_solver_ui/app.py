# -*- coding: utf-8 -*-
"""
pneumo_ui_app.py

Streamlit UI:
- запуск одиночных тестов (baseline),
- запуск оптимизации (фоновый процесс) из UI,
- просмотр/фильтр результатов.

Требования: streamlit, numpy, pandas, openpyxl.

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
import importlib.util
import logging
from logging.handlers import RotatingFileHandler
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

# Опционально: интерактивные графики (Plotly). Если не установлено — UI продолжит работать без Plotly.
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
from pneumo_solver_ui.ui_data_helpers import decimate_minmax, downsample_df, write_tests_index_csv
from pneumo_solver_ui.ui_diagnostics_helpers import make_ui_diagnostics_zip_bundle
from pneumo_solver_ui.ui_animation_mode_helpers import (
    ANIMATION_VIEW_MECHANICS,
    render_animation_view_selector,
    render_non_mechanical_animation_subsection,
)
from pneumo_solver_ui.ui_event_sync_helpers import (
    consume_mech_pick_event as _consume_mech_pick_event_core,
    consume_playhead_event as _consume_playhead_event_core,
    consume_plotly_pick_events as _consume_plotly_pick_events_core,
    consume_svg_pick_event as _consume_svg_pick_event_core,
)
from pneumo_solver_ui.ui_event_overlay_helpers import (
    prepare_events_for_graph_overlays,
)
from pneumo_solver_ui.ui_flow_rate_helpers import (
    flow_rate_display_scale_and_unit,
)
from pneumo_solver_ui.ui_flow_graph_helpers import (
    render_flow_edge_graphs_section,
)
from pneumo_solver_ui.ui_flow_animation_helpers import (
    render_flow_animation_panel,
)
from pneumo_solver_ui.ui_graph_studio_helpers import (
    render_graph_studio_section,
)
from pneumo_solver_ui.ui_svg_scheme_section_helpers import (
    render_svg_scheme_section,
)
from pneumo_solver_ui.ui_interaction_helpers import (
    apply_pick_list as _apply_pick_list,
    extract_plotly_selection_points as _extract_plotly_selection_points,
    plotly_points_signature as _plotly_points_signature,
)
from pneumo_solver_ui.ui_line_plot_helpers import (
    plot_lines as plot_lines_core,
)
from pneumo_solver_ui.ui_mech_graph_helpers import (
    render_mech_overview_graphs,
)
from pneumo_solver_ui.ui_mech_animation_helpers import (
    render_mechanical_animation_intro,
    render_mechanical_scheme_asset_expander,
)
from pneumo_solver_ui.ui_node_pressure_helpers import (
    render_node_pressure_expander,
)
from pneumo_solver_ui.ui_playhead_helpers import (
    make_playhead_jump_command,
    make_playhead_reset_command,
    render_results_view_selector,
)
from pneumo_solver_ui.ui_playhead_section_helpers import (
    render_playhead_results_section,
)
from pneumo_solver_ui.ui_timeline_event_helpers import (
    compute_events as compute_events_core,
)
from pneumo_solver_ui.ui_flow_panel_helpers import render_flow_panel_html
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
from pneumo_solver_ui.ui_plot_studio_helpers import (
    plot_studio_timeseries as plot_studio_timeseries_core,
)
from pneumo_solver_ui.ui_quick_graph_helpers import (
    render_main_overview_graphs,
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

# Optional: метрики процесса (CPU/RAM). Если psutil не установлен — просто отключаем метрики.
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

# Fallback (без Streamlit Components): matplotlib‑визуализация механики.
# Это лечит типовые проблемы вроде "Unrecognized component API version" в некоторых окружениях.
try:
    import mech_anim_fallback as mech_fb  # local module
except Exception:
    mech_fb = None

from io import BytesIO

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

MODEL_DEFAULT = str(canonical_model_path(HERE))
WORKER_DEFAULT = str(canonical_worker_path(HERE))
SUITE_DEFAULT = str(canonical_suite_json_path(HERE))
BASE_DEFAULT = str(canonical_base_json_path(HERE))
RANGES_DEFAULT = str(canonical_ranges_json_path(HERE))

# -------------------------------
# Default files shipped with the app
# -------------------------------
DEFAULT_SVG_MAPPING_PATH = HERE / "default_svg_mapping.json"

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
            sid = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_pid{os.getpid()}"
            st.session_state["_session_id"] = sid
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
    """Единая точка логирования.

    Пишем в:
    - ui_*.log (если доступно)
    - metrics_*.jsonl (если доступно)
    """

    try:
        _init_file_logger_once()
        payload = {"event": event, **fields}
        _APP_LOGGER.info(json.dumps(payload, ensure_ascii=False))

        # metrics jsonl — удобнее парсить
        if LOG_DIR is not None:
            sid = st.session_state.get("_session_id", "")
            mp = LOG_DIR / f"metrics_{sid}.jsonl"
            rec = {"ts": datetime.now().isoformat(), "session_id": sid, **payload}
            with open(mp, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

            # Optional: a single combined log file for all sessions.
            # This addresses the typical question "почему каждый запуск пишет в новый файл".
            try:
                with open(LOG_DIR / "ui_combined.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": rec["ts"], "session_id": sid, **payload}, ensure_ascii=False) + "\n")
            except Exception:
                pass
            try:
                with open(LOG_DIR / "metrics_combined.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
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
    return load_python_module_from_path(path, module_name)



def safe_dataframe(df: pd.DataFrame, height: int = 240, hide_index: bool = False):
    """Compatibility wrapper for Streamlit dataframe rendering.

    Streamlit recently started deprecating `use_container_width` in favor of `width="stretch"`.
    Some versions also differ on whether `hide_index` is supported.

    We try the most future-proof signature first to avoid console warnings, then fall back.
    """
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







def safe_plotly_chart(fig, *, key=None, on_select=None, selection_mode=None):
    """Безопасная обёртка над st.plotly_chart для разных версий Streamlit.

    В новых версиях Streamlit параметр on_select НЕ принимает None (только "ignore"/"rerun"/callable).
    Поэтому передаём on_select только если он задан явно.
    """
    # New API (2025+): width="stretch" вместо use_container_width
    kwargs_new = {"width": "stretch", "key": key}
    if on_select is not None:
        kwargs_new["on_select"] = on_select
    if selection_mode is not None:
        kwargs_new["selection_mode"] = selection_mode
    try:
        return st.plotly_chart(fig, **kwargs_new)
    except TypeError:
        # Older API fallback
        kwargs_old = {"use_container_width": True, "key": key}
        if on_select is not None:
            kwargs_old["on_select"] = on_select
        if selection_mode is not None:
            kwargs_old["selection_mode"] = selection_mode
        try:
            return st.plotly_chart(fig, **kwargs_old)
        except TypeError:
            return st.plotly_chart(fig, use_container_width=True, key=key)


def safe_image(img, *, caption=None):
    """Безопасный st.image: width='stretch' (новый API) -> fallback на use_container_width."""
    try:
        return st.image(img, caption=caption, width='stretch')
    except TypeError:
        return st.image(img, caption=caption, use_container_width=True)


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
    # meta: добавляем полезные поля для трассируемости (связь NPZ ↔ UI ↔ CSV)
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

    # Дополнительно ведём индекс экспортов, чтобы можно было:
    # - понимать, какой файл к какому тесту/бейслайну относится
    # - агрегировать результаты без "угадывания" по имени
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
        # Индекс не критичен — экспорт NPZ должен завершиться даже если индекс не пишется.
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


make_ui_diagnostics_zip = partial(
    make_ui_diagnostics_zip_bundle,
    here=HERE,
    workspace_dir=WORKSPACE_DIR,
    log_dir=LOG_DIR,
    app_release=APP_RELEASE,
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
    pressure_unit_label="атм (изб.)",
    pressure_offset_pa=lambda: P_ATM,
    pressure_divisor_pa=lambda: ATM_PA,
    length_unit_label="м",
    length_scale=1.0,
)


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
            "Plotly не установлен — интерактивные графики отключены (Graph Studio / интерактивные Plotly‑графики).\n\n"
            "Решение: используйте RUN_ONECLICK_WINDOWS.bat или INSTALL_DEPENDENCIES_WINDOWS.bat (создаст .venv и установит зависимости).\n"
            "Либо выполните в консоли: python -m pip install -r requirements.txt"
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
    "Plotly не установлен — интерактивные графики отключены (Graph Studio / интерактивные Plotly-графики).\n\n"
    "Решение: используйте RUN_ONECLICK_WINDOWS.bat или INSTALL_DEPENDENCIES_WINDOWS.bat (создаст .venv и установит зависимости).\n"
    "Либо выполните в консоли: python -m pip install -r requirements.txt"
)

plot_studio_timeseries = partial(
    plot_studio_timeseries_core,
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
    if df_p is not None and "время_с" in df_p.columns and len(df_p) == n:
        cols = [c for c in df_p.columns if c != "время_с" and c != "АТМ"]
        if cols:
            Pmax_abs = float(params_abs.get("давление_Pmax_предохран", P_ATM + 8e5))
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
                    add_event(i0, "error", "overpressure", "nodes", "P>ПРЕДОХ (max node)")

            vac_thr = P_ATM + float(vacuum_min_gauge_atm) * ATM_PA
            # do not go below absolute min + small epsilon (avoid false positives)
            p_abs_min = float(params_abs.get("минимальное_абсолютное_давление_Па", 1000.0))
            vac_thr = max(vac_thr, p_abs_min + 1.0)

            if p_min is not None:
                for i0 in _run_starts(p_min < vac_thr):
                    add_event(i0, "warn", "vacuum", "nodes", f"Вакуум: min node < {vacuum_min_gauge_atm:g} атм(изб)")

    # --------------------
    # 5) Valve chatter (rapid toggling) from df_open
    # --------------------
    if df_open is not None and "время_с" in df_open.columns and len(df_open) == n:
        # Analyze only edges that actually toggle, and keep top few.
        edge_cols = [c for c in df_open.columns if c != "время_с"]
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


def compute_events(
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
    return compute_events_core(
        df_main=df_main,
        df_p=df_p,
        df_open=df_open,
        params_abs=params_abs,
        test=test,
        vacuum_min_gauge=vacuum_min_gauge_atm,
        pmax_margin_gauge=pmax_margin_atm,
        chatter_window_s=chatter_window_s,
        chatter_toggle_count=chatter_toggle_count,
        max_events=max_events,
        gauge_pressure_scale_pa=101325.0,
        vacuum_unit_label="атм(изб)",
        run_starts_fn=_run_starts,
        shorten_name_fn=_shorten_name,
    )


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


plot_lines = partial(
    plot_lines_core,
    has_plotly=_HAS_PLOTLY,
    go_module=go,
    safe_plotly_chart_fn=safe_plotly_chart,
    is_any_fallback_anim_playing_fn=is_any_fallback_anim_playing,
    shorten_name_fn=_shorten_name,
)










# Shared worker/process helpers override the legacy inline copy above.
start_worker = partial(
    start_background_worker,
    console_python_executable_fn=console_python_executable,
)


# -------------------------------
# UI
# -------------------------------
st.set_page_config(page_title="Пневмоподвеска: solver+оптимизация", layout="wide", initial_sidebar_state="collapsed")

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

st.title("Пневмоподвеска: матмодель + оптимизация (solver‑first)")

# -------------------------------
# UI: Навигация (progressive disclosure)
# -------------------------------
UI_MODES = ["🏠 Рабочее место", "🧰 Полный интерфейс"]

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

ui_mode = _seg_or_radio("Режим", UI_MODES, key="ui_mode", index=0, horizontal=True)

FULL_SECTIONS = ["Модель", "Параметры", "Тесты", "Прогон", "Результаты", "Инструменты"]
if ui_mode == "🧰 Полный интерфейс":
    ui_section = _seg_or_radio("Раздел", FULL_SECTIONS, key="ui_section", index=0, horizontal=True)
else:
    ui_section = "WORKSPACE"

SHOW_MODEL = (ui_section == "Модель")
SHOW_PARAMS = (ui_section == "Параметры")
SHOW_TESTS = (ui_section == "Тесты")
SHOW_RUN = (ui_section == "Прогон")
SHOW_RESULTS = (ui_section == "Результаты")
SHOW_TOOLS = (ui_section == "Инструменты")

# Workspace = быстрый сценарий: Прогон + Результаты (без лишнего)
if ui_section == "WORKSPACE":
    SHOW_RUN = True
    SHOW_RESULTS = True
    SHOW_MODEL = False
    SHOW_PARAMS = False
    SHOW_TESTS = False
    SHOW_TOOLS = False

st.caption(
    "Идея интерфейса: один экран = одна задача. "
    "Полный интерфейс разнесён по смысловым разделам, чтобы не было 'простыней' и горизонтального скролла."
)


# -------------------------------
# Проект: пути к модели/оптимизатору и настройки (persisted via session_state)
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
    # UI для этих настроек находится в разделе "Прогон" (чтобы не захламлять сайдбар).
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
# Раздел "Модель": выбор файлов проекта (без захламления сайдбара)
# -------------------------------
if SHOW_MODEL:
    st.subheader("Модель: файлы проекта")
    st.caption("Выбор файлов вынесен сюда: так сайдбар остаётся лёгким, а редактирование — в одном месте.")

    colM1, colM2 = st.columns(2, gap="large")

    with colM1:
        model_files = sorted([p.name for p in HERE.glob("model_*.py")])
        current_model = Path(model_path).name
        opts = model_files.copy()
        if current_model and (current_model not in opts):
            opts = [current_model] + opts
        choice = st.selectbox("Файл модели (.py)", options=opts + ["(вручную)"], index=(opts.index(current_model) if current_model in opts else 0), key="model_file_choice")
        if choice == "(вручную)":
            manual = st.text_input("Путь к модели", value=model_path, key="model_path_manual")
            st.session_state["model_path"] = str(manual)
        else:
            st.session_state["model_path"] = str(HERE / choice)

    with colM2:
        worker_files = sorted([p.name for p in HERE.glob("opt_worker_*.py")])
        current_worker = Path(worker_path).name
        opts = worker_files.copy()
        if current_worker and (current_worker not in opts):
            opts = [current_worker] + opts
        choice = st.selectbox("Файл оптимизатора (.py)", options=opts + ["(вручную)"], index=(opts.index(current_worker) if current_worker in opts else 0), key="worker_file_choice")
        if choice == "(вручную)":
            manual = st.text_input("Путь к оптимизатору", value=worker_path, key="worker_path_manual")
            st.session_state["worker_path"] = str(manual)
        else:
            st.session_state["worker_path"] = str(HERE / choice)

    # refresh locals (so downstream code uses updated values in the same run)
    model_path = str(st.session_state.get("model_path", model_path))
    worker_path = str(st.session_state.get("worker_path", worker_path))

    st.info(f"Текущая модель: {Path(model_path).name} · оптимизатор: {Path(worker_path).name}")



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
    resolved_worker_path, _worker_msgs = resolve_project_py_path(
        worker_path,
        here=HERE,
        kind="оптимизатор",
        default_path=DEFAULT_WORKER_PATH,
    )
    resolved_model_path, _model_msgs = resolve_project_py_path(
        model_path,
        here=HERE,
        kind="модель",
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

    worker_mod = load_py_module(Path(resolved_worker_path), "opt_worker_mod")
    model_mod = load_py_module(Path(resolved_model_path), "pneumo_model_mod")
except Exception as e:
    st.error(f"Не могу загрузить модель/оптимизатор: {e}")
    st.stop()

P_ATM = float(getattr(model_mod, "P_ATM", 101325.0))
# 1 atm (стандартная атмосфера) = 101325 Па.
# В UI работаем в "атм (изб.)" (gauge), внутри модели — Па (абсолютное).
ATM_PA = 101325.0


pa_abs_to_atm_g = partial(pa_abs_to_gauge, pressure_offset_pa=P_ATM, pressure_divisor_pa=ATM_PA)
atm_g_to_pa_abs = partial(gauge_to_pa_abs, pressure_offset_pa=P_ATM, pressure_divisor_pa=ATM_PA)


# -------------------------------
# Описания/единицы параметров (для UI)
# ВАЖНО: эти функции должны быть определены ДО того, как мы строим таблицу df_opt.
# Иначе Python упадёт с NameError, т.к. модуль выполняется сверху вниз.
# -------------------------------


param_unit = partial(
    param_unit_label,
    pressure_unit_label="атм изб.",
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
BASE_STR_KEYS = {k for k, v in base0.items() if isinstance(v, str)}

# -------------------------------
# ЕДИНЫЙ ВВОД ПАРАМЕТРОВ (значение + диапазон оптимизации)
# -------------------------------

# (UI параметров отображается ниже в разделе "Параметры")

# Метаданные (текст/единицы) — без «захардкоженных» чисел.
PARAM_META = {
    # Давления (уставки) — в UI: атм (избыточного)
    "давление_Pmin_питание_Ресивер2": {
        "группа": "Давление (уставки)",
        "ед": "атм (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Уставка подпитки: линия «Аккумулятор → Ресивер 2». Это НЕ Pmin сброса/атмосферы. "
                    "Оптимизируйте отдельно от Pmin."
    },
    "давление_Pmin_сброс": {
        "группа": "Давление (уставки)",
        "ед": "атм (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Pmin для сброса в атмосферу (ветка Р3→атм). Ниже этого давления ступень не должна «разряжаться» в ноль."
    },
    "давление_Pmid_сброс": {
        "группа": "Давление (уставки)",
        "ед": "атм (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Pmid (уставка «середины»): выше — подвеска заметно «жёстче». Используется в метрике «раньше‑жёстко»."
    },
    "давление_Pзаряд_аккумулятора_из_Ресивер3": {
        "группа": "Давление (уставки)",
        "ед": "атм (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Уставка подпитки аккумулятора из Ресивера 3 во время движения (восполнение запаса воздуха)."
    },
    "давление_Pmax_предохран": {
        "группа": "Давление (уставки)",
        "ед": "атм (изб.)",
        "kind": "pressure_atm_g",
        "описание": "Pmax — аварийная уставка предохранительного клапана (не должна превышаться)."
    },
    "начальное_давление_аккумулятора": {
        "группа": "Давление (начальные)",
        "ед": "атм (изб.)",
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
        "описание": "Масштаб кривой «сила‑ход» пружины (табличная нелинейность остаётся, умножаем силу на коэффициент)."
    },

    # Механика/массы
    "масса_рамы": {"группа": "Механика", "ед": "кг", "kind": "raw", "описание": "Подрессоренная масса (рама/кузов)."},
    "масса_неподрессоренная": {"группа": "Механика", "ед": "кг", "kind": "raw", "описание": "Неподрессоренная масса на колесо (ступица/рычаг/колесо)."},
    "колея": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Колея (расстояние между центрами левого и правого колёс)."},
    "база": {"группа": "Геометрия", "ед": "м", "kind": "raw", "описание": "Колёсная база (перед‑зад)."},
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
}


_si_to_ui = partial(si_to_ui_value, p_atm=P_ATM, bar_pa=100000.0)
_ui_to_si = partial(ui_to_si_value, p_atm=P_ATM, bar_pa=100000.0)


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
    """
    Нелинейная пружина хранится как 2 массива (ход_мм, сила_Н).
    Важное правило UI: редактирование — только в разделе "Параметры", чтобы не захламлять другие экраны.
    При этом значения из session_state применяются ВСЕГДА (чтобы прогон/результаты использовали актуальную таблицу).
    """
    try:
        import pandas as _pd

        if "spring_table_df" not in st.session_state:
            st.session_state["spring_table_df"] = _pd.DataFrame({
                "ход_мм": list(base0.get(SPR_X, [])),
                "сила_Н": list(base0.get(SPR_F, [])),
            })

        spring_df = st.session_state.get("spring_table_df")

        if SHOW_PARAMS:
            st.markdown("### Нелинейная пружина: табличная характеристика")
            st.caption("Редактируйте точки (без правки файлов). Точки будут отсортированы по ходу. Минимум 2 точки.")
            spring_df = st.data_editor(
                spring_df,
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

        # Валидация + нормализация (применяем всегда)
        _df = _pd.DataFrame(spring_df).copy()
        _df["ход_мм"] = _pd.to_numeric(_df["ход_мм"], errors="coerce")
        _df["сила_Н"] = _pd.to_numeric(_df["сила_Н"], errors="coerce")
        _df = _df.dropna().sort_values("ход_мм")

        if len(_df) < 2:
            if SHOW_PARAMS or SHOW_RUN:
                st.error("Таблица пружины должна содержать минимум 2 числовые точки.")
        else:
            base0[SPR_X] = _df["ход_мм"].astype(float).tolist()
            base0[SPR_F] = _df["сила_Н"].astype(float).tolist()

    except Exception as e:
        if SHOW_PARAMS or SHOW_RUN:
            st.error(f"Ошибка обработки таблицы пружины: {e}")


# Список ключей со структурированными значениями (list/dict) — их исключаем из таблицы скаляров
structured_keys = [k for k in all_keys if isinstance(base0.get(k, None), (list, dict))]

# В таблицу редактирования попадают только числовые скаляры.
scalar_keys = [k for k in all_keys if (k not in structured_keys) and _is_numeric_scalar(base0.get(k, None))]
non_numeric_keys = [k for k in all_keys if (k not in structured_keys) and (not _is_numeric_scalar(base0.get(k, None)))]

rows = []
for k in scalar_keys:
    meta = PARAM_META.get(k) or family_param_meta(k) or {"группа": "Прочее", "ед": "СИ", "kind": "raw", "описание": ""}
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

if "df_params_edit" not in st.session_state:
    st.session_state["df_params_edit"] = df_params0

# --- UI: параметры без горизонтального скролла (список + карточка) ---
def _merge_params_df(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """С remember: сохраняем пользовательские правки и подхватываем новые ключи из df_new."""
    try:
        if (df_old is None) or (len(df_old) == 0):
            return df_new.copy()
        if (df_new is None) or (len(df_new) == 0):
            return df_old.copy()
        a = df_old.copy()
        b = df_new.copy()
        if "_key" not in a.columns:
            a["_key"] = a.get("параметр", "")
        if "_key" not in b.columns:
            b["_key"] = b.get("параметр", "")
        # индекс по ключу
        a = a.set_index("_key", drop=False)
        b = b.set_index("_key", drop=False)

        # 1) обновляем описания/группы/единицы из "свежего"
        for col in ["группа", "единица", "пояснение", "_kind", "параметр"]:
            if col in b.columns:
                a[col] = a[col].where(~a[col].isna(), b[col])
                # если у нас устаревшее описание — предпочитаем новое
                a[col] = b[col].combine_first(a[col])

        # 2) добавляем новые ключи, которых не было
        missing = [k for k in b.index if k not in a.index]
        if missing:
            a = pd.concat([a, b.loc[missing].copy()], axis=0)

        # 3) сортировка как в новом df (группа/ключ)
        try:
            a = a.loc[b.index.intersection(a.index).tolist() + [k for k in a.index if k not in b.index]]
        except Exception:
            pass
        return a.reset_index(drop=True)
    except Exception:
        return df_new.copy()

def _render_param_card_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Render one parameter row as a card, return updated values."""
    k = str(row.get("_key") or row.get("параметр") or "")
    group = str(row.get("группа") or "Прочее")
    unit = str(row.get("единица") or "—")
    kind = str(row.get("_kind") or "raw")
    desc = str(row.get("пояснение") or "")

    # current values (UI units already)
    def _f(x, default=float("nan")):
        try:
            return float(x)
        except Exception:
            return default

    v = _f(row.get("значение"))
    opt = bool(row.get("оптимизировать", False))
    vmin = _f(row.get("мин"))
    vmax = _f(row.get("макс"))

    # Card layout
    with st.container():
        topL, topR = st.columns([1.4, 1.0], gap="large")
        with topL:
            st.markdown(f"**{k}**  ·  {group}")
            if desc:
                st.caption(desc)
        with topR:
            opt_new = st.checkbox("Оптимизировать", value=opt, key=f"popt__{k}")
            opt = bool(opt_new)

        # Value editor
        # Rule: try to avoid manual typing where it's safe.
        # We use sliders for common semantics, otherwise number_input.
        val_key = f"pval__{k}"

        # Slider ranges
        use_slider = False
        smin, smax, step = None, None, None

        if kind == "fraction01" or (("доля" in unit) and ("0..1" in unit)):
            use_slider = True
            smin, smax = 0.0, 1.0
            step = 0.01
            if not (0.0 <= v <= 1.0):
                v = max(0.0, min(1.0, v if math.isfinite(v) else 0.0))

        elif kind == "pressure_atm_g" or ("атм" in unit):
            use_slider = True
            # leaving some room for vacuum (negative gauge)
            base = v if math.isfinite(v) else 0.0
            if opt and math.isfinite(vmin) and math.isfinite(vmax) and (vmin < vmax):
                smin, smax = float(vmin), float(vmax)
            else:
                smin = float(min(base - 2.0, -0.95))
                smax = float(max(base + 2.0, 10.0))
            step = 0.05

        elif ("объём" in k) or (kind.startswith("volume_")) or (unit in ("л", "мл")):
            use_slider = True
            base = v if math.isfinite(v) else (1.0 if unit == "л" else 100.0)
            if opt and math.isfinite(vmin) and math.isfinite(vmax) and (vmin < vmax):
                smin, smax = float(vmin), float(vmax)
            else:
                # heuristic around current
                span = max(abs(base) * 0.5, 1.0 if unit == "л" else 50.0)
                smin = max(0.0, base - span)
                smax = max(smin + (1.0 if unit == "л" else 10.0), base + span)
            step = 0.1 if unit == "л" else 1.0

        elif k.endswith("_град") or (unit == "град"):
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
                "Значение",
                min_value=float(smin),
                max_value=float(smax),
                value=float(vv),
                step=float(step) if step else None,
                key=val_key,
            )
        else:
            v_new = st.number_input(
                "Значение",
                value=float(v) if math.isfinite(v) else 0.0,
                step=None,
                key=val_key,
            )

        # Range editor (advanced)
        vmin_new, vmax_new = vmin, vmax
        if opt:
            with st.expander("Диапазон оптимизации", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    vmin_new = st.number_input("Мин", value=float(vmin) if math.isfinite(vmin) else float(v_new), step=None, key=f"pmin__{k}")
                with c2:
                    vmax_new = st.number_input("Макс", value=float(vmax) if math.isfinite(vmax) else float(v_new), step=None, key=f"pmax__{k}")
        return {
            **row,
            "значение": float(v_new),
            "оптимизировать": bool(opt),
            "мин": float(vmin_new) if math.isfinite(float(vmin_new)) else float("nan"),
            "макс": float(vmax_new) if math.isfinite(float(vmax_new)) else float("nan"),
        }

# Ensure params table exists and stays in sync with current PARAM_META
if "df_params_edit" not in st.session_state:
    st.session_state["df_params_edit"] = df_params0
else:
    st.session_state["df_params_edit"] = _merge_params_df(st.session_state["df_params_edit"], df_params0)

# Reflect edits only in the Parameters section (progressive disclosure)
if SHOW_PARAMS:
    st.subheader("Параметры (значения + диапазоны оптимизации)")
    st.caption(
        "Тут редактируются числовые параметры. Нет горизонтального скролла: список → карточка параметра. "
        "Оптимизацию включайте галочкой на карточке, диапазон прячется в 'Диапазон оптимизации'."
    )

    df_in = st.session_state["df_params_edit"].copy()
    # Filters
    groups = sorted([g for g in df_in.get("группа", pd.Series(dtype=str)).dropna().unique().tolist() if str(g).strip()])
    colF1, colF2, colF3 = st.columns([1.2, 1.0, 0.9], gap="medium")
    with colF1:
        q = st.text_input("Поиск", value=st.session_state.get("param_search", ""), key="param_search", placeholder="например: давление, объём, открытие...")
    with colF2:
        grp = st.selectbox("Группа", options=["(все)"] + groups, index=0, key="param_group")
    with colF3:
        only_opt = st.checkbox("Только оптимизируемые", value=bool(st.session_state.get("param_only_opt", False)), key="param_only_opt")

    df_view = df_in.copy()
    if grp != "(все)":
        df_view = df_view[df_view["группа"] == grp]
    if q.strip():
        qq = q.strip().lower()
        df_view = df_view[df_view.apply(lambda r: (qq in str(r.get("_key","")).lower()) or (qq in str(r.get("пояснение","")).lower()), axis=1)]
    if only_opt:
        df_view = df_view[df_view["оптимизировать"].astype(bool)]

    # Limit visible cards for performance
    total = int(len(df_view))
    show_n = st.slider("Показывать параметров", min_value=8, max_value=40, value=int(min(16, max(8, total))), step=1, key="param_show_n")
    st.caption(f"Показано: {min(show_n, total)} из {total} (фильтры сверху).")
    df_view = df_view.head(show_n)

    # Render cards and write back into df_in
    updated_rows = {}
    for _, r in df_view.iterrows():
        rec = _render_param_card_row(r.to_dict())
        updated_rows[str(rec.get("_key") or rec.get("параметр") or "")] = rec

    if updated_rows:
        df_out = df_in.copy().set_index("_key", drop=False)
        for k, rec in updated_rows.items():
            if k in df_out.index:
                for col in ["значение", "оптимизировать", "мин", "макс"]:
                    if col in df_out.columns and col in rec:
                        df_out.loc[k, col] = rec[col]
        df_out = df_out.reset_index(drop=True)
        st.session_state["df_params_edit"] = df_out

df_params_edit = st.session_state["df_params_edit"]

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

if param_errors and (SHOW_PARAMS or SHOW_RUN):
    st.error("В таблице параметров есть ошибки (исправьте перед запуском):\n- " + "\n- ".join(param_errors))





# -------------------------------
# Модель: режимы и флаги (bool + string)
# -------------------------------
# Принцип: UI "модельных" настроек показываем только в разделе "Модель",
# но выбранные значения применяются ВСЕГДА (чтобы Прогон/Результаты работали одинаково).
bool_keys_ui = [k for k in BASE_BOOL_KEYS if (k in base0)]
str_keys_ui = [k for k in BASE_STR_KEYS if (k in base0)]

if SHOW_MODEL:
    st.divider()
    st.subheader("Модель: режимы и флаги")
    st.caption("Булевы — чекбоксы. Строковые — выпадающие списки. Поиск сверху, чтобы не было 'простыней'.")

    with st.expander("Булевы флаги", expanded=False):
        qf = st.text_input("Поиск флага", value=st.session_state.get("flag_search", ""), key="flag_search", placeholder="например: вакуум, мягк, демпф...")
        show_all = st.checkbox("Показать все", value=bool(st.session_state.get("flag_show_all", False)), key="flag_show_all")
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
            st.caption("Часть флагов скрыта. Включите 'Показать все' или используйте поиск.")

    with st.expander("Строковые режимы", expanded=False):
        qm = st.text_input("Поиск режима", value=st.session_state.get("mode_search", ""), key="mode_search", placeholder="например: паспорт, стратегия, режим...")
        show_all = st.checkbox("Показать все режимы", value=bool(st.session_state.get("mode_show_all", False)), key="mode_show_all")

        keys = str_keys_ui
        if qm.strip():
            qq = qm.strip().lower()
            keys = [k for k in keys if qq in str(k).lower()]
        if not show_all:
            keys = keys[:30]

        for k in keys:
            if k == "паспорт_компонентов_json":
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
                options = ["(как в базе)"] + json_files + ["(вручную)"]
                # index
                idx = 0
                if current in json_files:
                    idx = 1 + json_files.index(current)
                elif current.strip():
                    idx = len(options) - 1

                choice = st.selectbox("паспорт_компонентов_json", options=options, index=idx, key=f"mode__{k}__choice")
                if choice == "(вручную)":
                    st.text_input("Путь/имя JSON", value=current, key=f"mode__{k}__manual")
                elif choice == "(как в базе)":
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
            st.caption("Часть режимов скрыта. Включите 'Показать все режимы' или используйте поиск.")

# Apply overrides from session_state (always)
for k in bool_keys_ui:
    v = st.session_state.get(f"flag__{k}", base0.get(k, False))
    base_override[k] = bool(v)

for k in str_keys_ui:
    if k == "паспорт_компонентов_json":
        v_man = str(st.session_state.get(f"mode__{k}__manual", "") or "").strip()
        if v_man:
            base_override[k] = v_man
        else:
            base_override[k] = str(st.session_state.get(f"mode__{k}", base0.get(k, "")) or "")
    else:
        base_override[k] = str(st.session_state.get(f"mode__{k}", base0.get(k, "")) or "")
# -------------------------------
# Тест‑набор и пороги (редактируется из UI)
# -------------------------------
# (UI тест-набора отображается ниже в разделе "Тесты")

ALLOWED_TEST_TYPES = [
    "инерция_крен",
    "инерция_тангаж",
    "микро_синфаза",
    "микро_разнофаза",
    "кочка_одно_колесо",
    "кочка_диагональ",
    "комбо_крен_плюс_микро",
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
        "В suite обнаружены legacy-колонки. Выполнена явная миграция в canonical schema; "
        "пересохраните suite.json.\n- " + "\n- ".join(str(x) for x in issues)
    )


# загрузка suite по умолчанию
if "df_suite_edit" not in st.session_state:
    st.session_state["df_suite_edit"] = _normalize_suite_df_for_editor(
        pd.DataFrame(load_default_suite_disabled(DEFAULT_SUITE_PATH)),
        context="app.default_suite_load",
    )

# upload/редактирование suite — только в разделе "Тесты" (progressive disclosure)
df_suite_edit = st.session_state.get("df_suite_edit")
if df_suite_edit is None:
    df_suite_edit = pd.DataFrame()
    st.session_state["df_suite_edit"] = df_suite_edit
else:
    df_suite_edit = _normalize_suite_df_for_editor(pd.DataFrame(df_suite_edit), context="app.session_state_restore")
    st.session_state["df_suite_edit"] = df_suite_edit

# Нормализация колонок (на случай старых/загруженных suite)
EXPECTED_SUITE_COLS = [
    "имя", "включен", "тип", "dt", "t_end",
    "t_step", "settle_band_min_deg", "settle_band_ratio",
    "ax", "ay", "A", "f", "dur", "t0", "idx",
    "vx0_м_с", "угол_град", "доля_плавной_стыковки",
    # targets:
    "target_макс_доля_отрыва",
    "target_мин_запас_до_Pmid_бар",
    "target_мин_Fmin_Н",
    "target_мин_запас_до_пробоя_крен_град",
    "target_мин_запас_до_пробоя_тангаж_град",
    "target_мин_запас_до_упора_штока_м",
    "target_лимит_скорости_штока_м_с",
]
for _c in EXPECTED_SUITE_COLS:
    if _c not in df_suite_edit.columns:
        df_suite_edit[_c] = np.nan
st.session_state["df_suite_edit"] = df_suite_edit
if SHOW_TESTS or SHOW_RUN:
    _show_suite_contract_warnings_once()

if SHOW_TESTS:
    st.subheader("Тест‑набор (suite)")
    st.caption(
        "Слева — список тестов (поиск/выбор). Справа — карточка выбранного теста. "
        "Это устраняет горизонтальный скролл и 'простыни' таблиц."
    )

    # Import / export / reset
    with st.expander("Импорт / экспорт / сброс", expanded=True):
        colIE1, colIE2, colIE3 = st.columns([1.2, 1.0, 1.0], gap="medium")

        with colIE1:
            suite_upload = st.file_uploader(
                "Импорт suite (JSON)",
                type=["json"],
                help="Загрузите ранее сохранённый suite.json (список словарей).",
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
                        st.success("Suite загружен.")
                        st.rerun()
                    else:
                        st.error("JSON должен быть списком объектов (list[dict]).")
                except Exception as e:
                    st.error(f"Не удалось прочитать JSON: {e}")

        with colIE2:
            if st.button("Сбросить к default_suite.json", key="suite_reset_default"):
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
                "Экспорт suite.json",
                data=suite_json,
                file_name="suite_export.json",
                mime="application/json",
                key="suite_download_json",
            )

    # Master-detail layout
    df_suite_edit = st.session_state["df_suite_edit"].copy()
    left, right = st.columns([1.0, 1.2], gap="large")

    with left:
        q = st.text_input("Поиск теста", value=st.session_state.get("suite_search", ""), key="suite_search", placeholder="например: крен, микро, кочка...")
        # build labels
        labels = []
        idx_map = []
        for i, r in df_suite_edit.iterrows():
            name = str(r.get("имя") or f"test_{i}")
            typ = str(r.get("тип") or "")
            enabled = bool(r.get("включен")) if ("включен" in r) else True
            lbl = f"{'✅' if enabled else '⛔'} {name}  ·  {typ}"
            if q.strip():
                if q.strip().lower() not in lbl.lower():
                    continue
            labels.append(lbl)
            idx_map.append(i)

        if not labels:
            st.info("Список тестов пуст (или фильтр ничего не нашёл). Добавьте тест.")
            sel_i = None
        else:
            # keep selection stable with a normal always-selected scenario when list is not empty.
            if "suite_sel" not in st.session_state:
                st.session_state["suite_sel"] = idx_map[0]
            if st.session_state["suite_sel"] not in idx_map:
                st.session_state["suite_sel"] = idx_map[0]
            sel_i = st.selectbox(
                "Тест",
                options=idx_map,
                format_func=lambda i: (labels[idx_map.index(i)] if i in idx_map else str(i)),
                key="suite_sel",
            )

        btnC1, btnC2, btnC3 = st.columns(3, gap="small")
        with btnC1:
            if st.button("➕ Добавить", key="suite_add"):
                new_row = {c: np.nan for c in EXPECTED_SUITE_COLS}
                new_row["включен"] = True
                new_row["имя"] = f"new_test_{len(df_suite_edit)+1}"
                new_row["тип"] = ALLOWED_TEST_TYPES[0] if ALLOWED_TEST_TYPES else "инерция_крен"
                new_row["dt"] = 0.01
                new_row["t_end"] = 3.0
                df_suite_edit = pd.concat([df_suite_edit, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state["df_suite_edit"] = df_suite_edit
                st.session_state["suite_sel"] = int(len(df_suite_edit)-1)
                st.rerun()
        with btnC2:
            if st.button("📄 Дублировать", disabled=(sel_i is None), key="suite_dup"):
                if sel_i is not None:
                    row = df_suite_edit.loc[sel_i].to_dict()
                    row["имя"] = str(row.get("имя") or "copy") + "_copy"
                    df_suite_edit = pd.concat([df_suite_edit, pd.DataFrame([row])], ignore_index=True)
                    st.session_state["df_suite_edit"] = df_suite_edit
                    st.session_state["suite_sel"] = int(len(df_suite_edit)-1)
                    st.rerun()
        with btnC3:
            if st.button("🗑️ Удалить", disabled=(sel_i is None), key="suite_del"):
                if sel_i is not None and len(df_suite_edit) > 0:
                    df_suite_edit = df_suite_edit.drop(index=sel_i).reset_index(drop=True)
                    st.session_state["df_suite_edit"] = df_suite_edit
                    st.session_state["suite_sel"] = first_suite_selected_index(df_suite_edit)
                    st.rerun()

        st.caption(f"Всего тестов: {len(st.session_state['df_suite_edit'])}")

    with right:
        if sel_i is None or len(df_suite_edit) == 0:
            st.info("Выберите тест слева.")
        else:
            row = df_suite_edit.loc[sel_i].to_dict()

            def _num(x, default=float("nan")):
                try:
                    return float(x)
                except Exception:
                    return default

            enabled = bool(row.get("включен", True))
            name = str(row.get("имя") or f"test_{sel_i}")
            typ = str(row.get("тип") or (ALLOWED_TEST_TYPES[0] if ALLOWED_TEST_TYPES else ""))

            with st.container():
                st.markdown("**Карточка теста**")
                cA, cB = st.columns([1.0, 1.0], gap="medium")
                with cA:
                    enabled = st.checkbox("Включен", value=enabled, key=f"suite_enabled__{sel_i}")
                    name = st.text_input("Имя", value=name, key=f"suite_name__{sel_i}")
                with cB:
                    typ = st.selectbox("Тип", options=ALLOWED_TEST_TYPES, index=(ALLOWED_TEST_TYPES.index(typ) if typ in ALLOWED_TEST_TYPES else 0), key=f"suite_type__{sel_i}")

                # dt / t_end presets
                dt0 = _num(row.get("dt"), 0.01)
                tend0 = _num(row.get("t_end"), 3.0)
                dt_presets = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1]
                te_presets = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]

                c1, c2 = st.columns(2, gap="medium")
                with c1:
                    dt_choice = st.selectbox("Шаг dt (с)", options=dt_presets + ["другое"], index=(dt_presets.index(dt0) if dt0 in dt_presets else len(dt_presets)), key=f"suite_dt_choice__{sel_i}")
                    if dt_choice == "другое":
                        dt = st.number_input("dt (с)", value=float(dt0), step=None, key=f"suite_dt__{sel_i}")
                    else:
                        dt = float(dt_choice)
                with c2:
                    te_choice = st.selectbox("Длительность t_end (с)", options=te_presets + ["другое"], index=(te_presets.index(tend0) if tend0 in te_presets else len(te_presets)), key=f"suite_te_choice__{sel_i}")
                    if te_choice == "другое":
                        t_end = st.number_input("t_end (с)", value=float(tend0), step=None, key=f"suite_te__{sel_i}")
                    else:
                        t_end = float(te_choice)

                # Common excitation / maneuver params (only if present)
                st.markdown("**Возмущение / манёвр**")
                c3, c4, c5 = st.columns(3, gap="small")
                with c3:
                    ax = _num(row.get("ax"), 0.0)
                    ax = st.slider("ax (м/с²)", min_value=-20.0, max_value=20.0, value=float(max(-20.0, min(20.0, ax))), step=0.1, key=f"suite_ax__{sel_i}")
                with c4:
                    ay = _num(row.get("ay"), 0.0)
                    ay = st.slider("ay (м/с²)", min_value=-20.0, max_value=20.0, value=float(max(-20.0, min(20.0, ay))), step=0.1, key=f"suite_ay__{sel_i}")
                with c5:
                    speed = _num(row.get("vx0_м_с"), 0.0)
                    speed = st.slider("скорость (м/с)", min_value=0.0, max_value=40.0, value=float(max(0.0, min(40.0, speed))), step=0.5, key=f"suite_speed__{sel_i}")

                c6, c7, c8 = st.columns(3, gap="small")
                with c6:
                    A = _num(row.get("A"), 0.0)
                    A = st.slider("A (м)", min_value=0.0, max_value=0.3, value=float(max(0.0, min(0.3, A))), step=0.001, key=f"suite_A__{sel_i}")
                with c7:
                    f = _num(row.get("f"), 0.0)
                    f = st.slider("f (Гц)", min_value=0.0, max_value=25.0, value=float(max(0.0, min(25.0, f))), step=0.1, key=f"suite_f__{sel_i}")
                with c8:
                    angle = _num(row.get("угол_град"), 0.0)
                    angle = st.slider("угол (град)", min_value=-45.0, max_value=45.0, value=float(max(-45.0, min(45.0, angle))), step=0.5, key=f"suite_angle__{sel_i}")

                with st.expander("Порог/уставки (targets) и расширенные параметры", expanded=True):
                    # show only non-empty targets
                    for k in EXPECTED_SUITE_COLS:
                        if not k.startswith("target_"):
                            continue
                        v0 = row.get(k, np.nan)
                        if isinstance(v0, float) and pd.isna(v0):
                            v0 = 0.0
                        row[k] = st.number_input(k, value=float(v0) if v0 is not None else 0.0, step=None, key=f"suite_tgt__{k}__{sel_i}")
                    # extra non-target fields we didn't expose above
                    for k in ["t_step", "settle_band_min_deg", "settle_band_ratio", "dur", "t0", "idx", "доля_плавной_стыковки"]:
                        if k not in row:
                            continue
                        v0 = row.get(k, np.nan)
                        if isinstance(v0, float) and pd.isna(v0):
                            v0 = 0.0
                        row[k] = st.number_input(k, value=float(v0) if v0 is not None else 0.0, step=None, key=f"suite_extra__{k}__{sel_i}")

                if st.button("✅ Применить", key=f"suite_apply__{sel_i}"):
                    # write back
                    df2 = st.session_state["df_suite_edit"].copy()
                    df2.loc[sel_i, "включен"] = bool(enabled)
                    df2.loc[sel_i, "имя"] = str(name)
                    df2.loc[sel_i, "тип"] = str(typ)
                    df2.loc[sel_i, "dt"] = float(dt)
                    df2.loc[sel_i, "t_end"] = float(t_end)
                    # common params
                    for k, v in {
                        "ax": ax, "ay": ay, "vx0_м_с": speed,
                        "A": A, "f": f, "угол_град": angle,
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
                    for k in ["t_step", "settle_band_min_deg", "settle_band_ratio", "dur", "t0", "idx", "доля_плавной_стыковки"]:
                        if k in df2.columns:
                            try:
                                df2.loc[sel_i, k] = float(row.get(k, 0.0))
                            except Exception:
                                pass

                    st.session_state["df_suite_edit"] = df2
                    st.success("Сохранено.")
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

    suite_override.append(rec)

if suite_errors and (SHOW_TESTS or SHOW_RUN):
    st.error("В тест‑наборе есть ошибки (исправьте перед запуском):\n- " + "\n- ".join(suite_errors))


# -------------------------------
# Одиночные тесты
# -------------------------------
if SHOW_RUN:
    # Настройки вывода/оптимизации (вынесены сюда, чтобы не перегружать сайдбар)
    st.subheader("Прогон: настройки")
    cS1, cS2 = st.columns([1.1, 1.0], gap="large")
    with cS1:
        out_prefix = st.text_input("Префикс результата", value=str(st.session_state.get("out_prefix", out_prefix)), key="out_prefix")
        auto_refresh = st.checkbox("Авто‑обновление результатов", value=bool(st.session_state.get("opt_auto_refresh", auto_refresh)), key="opt_auto_refresh")
    with cS2:
        minutes = st.slider("Время оптимизации (мин)", min_value=0.2, max_value=120.0, value=float(st.session_state.get("opt_minutes", minutes)), step=0.2, key="opt_minutes")
        jobs_max = int(max(1, min(32, (os.cpu_count() or 4))))
        jobs = st.slider("Параллельные jobs", min_value=1, max_value=jobs_max, value=int(st.session_state.get("opt_jobs", jobs)), step=1, key="opt_jobs")

    with st.expander("Расширенные настройки оптимизации", expanded=True):
        seed_candidates = st.number_input("seed_candidates", min_value=1, max_value=9999, value=int(st.session_state.get("opt_seed_candidates", seed_candidates)), step=1, key="opt_seed_candidates")
        seed_conditions = st.number_input("seed_conditions", min_value=1, max_value=9999, value=int(st.session_state.get("opt_seed_conditions", seed_conditions)), step=1, key="opt_seed_conditions")
        flush_every = st.number_input("flush_every", min_value=1, max_value=9999, value=int(st.session_state.get("opt_flush_every", flush_every)), step=1, key="opt_flush_every")
        progress_every_sec = st.number_input("progress_every_sec", min_value=0.1, max_value=60.0, value=float(st.session_state.get("opt_progress_every_sec", progress_every_sec)), step=0.1, key="opt_progress_every_sec")
        refresh_sec = st.number_input("refresh_sec", min_value=0.2, max_value=10.0, value=float(st.session_state.get("opt_refresh_sec", refresh_sec)), step=0.1, key="opt_refresh_sec")

    # сохраняем настройки обратно в session_state (единый источник правды)
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

    st.subheader("Быстрый прогон тестов (baseline)")
    st.caption("Проверка адекватности модели на текущих параметрах.")

    tests_cfg = {"suite": suite_override}
    tests = worker_mod.build_test_suite(tests_cfg)

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

        if st.session_state.baseline_df is None:
            _cached = load_baseline_cache(_cache_dir_preview)
            if _cached is not None:
                st.session_state.baseline_df = _cached["baseline_df"]
                st.session_state.baseline_tests_map = _cached["tests_map"]
                st.session_state.baseline_param_hash = _base_hash_preview
                # детальные прогоны не грузим целиком — будут подхвачены по запросу
                log_event("baseline_loaded_cache", cache_dir=str(_cache_dir_preview))
                st.info(f"Baseline загружен из кэша: {_cache_dir_preview.name}")
    except Exception:
        pass

    test_names = [x[0] for x in tests]
    pick = st.selectbox("Тест", options=["(все)"] + test_names, index=0)

    if st.button("Запустить baseline"):
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

        # отметка: baseline обновился (для авто‑детального триггера)
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
if SHOW_RESULTS or SHOW_TOOLS:
    # Детальные графики + анимация (baseline)
    # -------------------------------
    st.divider()
    st.header("Baseline: результаты и диагностика")
    st.caption(
        "Сначала запустите baseline. Затем выберите один тест и получите полный лог (record_full=True): "
        "графики P/Q/крен/тангаж/силы и MVP-анимацию потоков."
    )

    cur_hash = stable_obj_hash(base_override)
    if st.session_state.baseline_df is None:
        st.info("Нет baseline-таблицы. Нажмите ‘Запустить baseline’ выше.")
    elif st.session_state.baseline_param_hash and st.session_state.baseline_param_hash != cur_hash:
        st.warning(
            "Параметры изменились после baseline. Чтобы графики/анимация соответствовали текущим параметрам, "
            "перезапустите baseline."
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
            st.info("В baseline нет доступных тестов (проверьте тест‑набор).")
        else:
            colG1, colG2, colG3 = st.columns([1.2, 1.0, 1.0], gap="large")
            with colG1:
                test_pick = st.selectbox("Тест для детального прогона", options=avail, index=0, key="detail_test_pick")
            with colG2:
                max_points = st.number_input("Макс точек (downsample)", min_value=200, max_value=5000, value=1200, step=100, key="detail_max_points")
            with colG3:
                want_full = st.checkbox("Использовать record_full (потоки/состояния)", value=True, key="detail_want_full")
                auto_detail_on_select = st.checkbox(
                    "Авто‑расчёт при выборе теста",
                    value=True,
                    key="auto_detail_on_select",
                    help="Если включено и кэш пуст, будет считаться детальный прогон (может грузить CPU).",
                )
                auto_export_npz = st.checkbox(
                    "Авто‑экспорт NPZ (osc_dir)",
                    value=True,
                    key="auto_export_npz",
                    help="Экспортирует Txx_osc.npz в папку osc_dir (см. Калибровка). Нужно для oneclick/autopilot.",
                )

                auto_export_anim_latest = st.checkbox(
                    "Авто‑экспорт anim_latest (Desktop Animator)",
                    value=True,
                    key="auto_export_anim_latest",
                    help=(
                        "Пишет workspace/exports/anim_latest.npz + anim_latest.json. "
                        "Desktop Animator в режиме --follow автоматически перезагрузит анимацию."
                    ),
                )

            # Desktop Animator integration (minimal manual steps)
            with st.expander("Desktop Animator (Windows) — информативная анимация", expanded=True):
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
                        _st.append(f"NPZ: ✅ {_npz_p.name} ({_npz_p.stat().st_size/1024:.1f} KB)")
                    else:
                        _st.append(f"NPZ: ❌ {_npz_p.name} (нет)")
                    if _ptr_p.exists():
                        _st.append(f"PTR: ✅ {_ptr_p.name}")
                    else:
                        _st.append(f"PTR: ❌ {_ptr_p.name} (нет)")
                except Exception:
                    pass
                if _st:
                    st.info("\n".join(_st))

                colA1, colA2, colA3 = st.columns([1.0, 1.0, 1.2], gap="medium")
                with colA1:
                    if st.button("Запустить Animator (--follow)", key="launch_desktop_animator"):
                        try:
                            cmd = [sys.executable, "-m", "pneumo_solver_ui.desktop_animator.main", "--follow", "--theme", "dark"]
                            # Streamlit runs from project root typically; force cwd near UI package to resolve imports/assets.
                            start_worker(cmd, cwd=HERE)
                            st.success("Desktop Animator запущен.")
                        except Exception as e:
                            st.error(f"Не удалось запустить Desktop Animator: {e}")
                with colA2:
                    if st.button("Открыть папку exports", key="open_exports_dir"):
                        try:
                            if os.name == "nt":
                                os.startfile(str(WORKSPACE_EXPORTS_DIR))  # type: ignore[attr-defined]
                            else:
                                st.warning("Кнопка открытия папки работает только на Windows.")
                        except Exception as e:
                            st.error(f"Не удалось открыть папку: {e}")
                with colA3:
                    # Manual export button (useful if auto-export disabled)
                    if st.button("Экспортировать текущий детальный лог в anim_latest", key="export_anim_latest_now"):
                        try:
                            det_now = st.session_state.baseline_full_cache.get(_cache_key_now)
                            if not det_now:
                                st.warning("Сначала выполните детальный расчёт, чтобы появился кэш.")
                            else:
                                export_anim_latest_bundle(
                                    det_now.get("df_main"),
                                    df_p=det_now.get("df_p"),
                                    df_q=det_now.get("df_mdot"),
                                    df_open=det_now.get("df_open"),
                                    meta=(det_now.get("meta") or {}),
                                )
                                st.success("Экспортировано в anim_latest.")
                        except Exception as e:
                            st.error(f"Экспорт не удался: {e}")

                st.caption(
                    "Рекомендуемый workflow: откройте Desktop Animator (follow), затем нажмите 'Рассчитать полный лог'. "
                    "Если включён авто‑экспорт — Desktop Animator обновится автоматически."
                )

            # dt/t_end берём из suite для выбранного теста — это часть cache_key и параметров simulate()
            info_pick = tests_map.get(test_pick, {}) if isinstance(tests_map, dict) else {}
            detail_dt = float(info_pick.get("dt", 0.01) or 0.01)
            detail_t_end = float(info_pick.get("t_end", 1.0) or 1.0)
            # сохраняем для других страниц/инструментов
            st.session_state["detail_dt_pick"] = detail_dt
            st.session_state["detail_t_end_pick"] = detail_t_end

            run_detail = st.button("Рассчитать полный лог и показать", key="run_detail")

            colDAll1, colDAll2 = st.columns([1.0, 1.0])
            with colDAll1:
                run_detail_all = st.button("Рассчитать полный лог ДЛЯ ВСЕХ тестов", key="run_detail_all")
            with colDAll2:
                export_npz_all = st.button("Экспорт NPZ ДЛЯ ВСЕХ (из кэша)", key="export_npz_all")

                cache_key = make_detail_cache_key(cur_hash, test_pick, detail_dt, detail_t_end, max_points, want_full)

            # --- Авто‑детальный прогон: запускать ТОЛЬКО по триггеру
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
                            ck = make_detail_cache_key(cur_hash, tn, float(tobj.get("dt", detail_dt)), float(tobj.get("t_end", detail_t_end)), max_points, want_full)
                            if ck in st.session_state.baseline_full_cache:
                                prog.progress(j / n_total)
                                continue
                            info_j = tests_map.get(tn) or {}
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
                            ck = make_detail_cache_key(cur_hash, tn, float(tobj.get("dt", detail_dt)), float(tobj.get("t_end", detail_t_end)), max_points, want_full)
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
                # Важно: auto_detail может вызываться много раз из‑за частых rerun'ов. Если кэш по какой‑то причине
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
                        st.warning("⚠️ Обнаружен зависший/устаревший прогон — сбрасываю блокировку повторного запуска.")
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
                            "⚠️ Обнаружен застрявший флаг 'детальный прогон выполняется'. "
                            "Сбрасываю флаг и запускаю заново."
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
                        st.progress(min(max(_p0, 0.0), 1.0), text="Детальный прогон уже выполняется…")
                        st.info("Детальный прогон уже выполняется (повторный запуск подавлен).")
                        log_event("detail_autorun_already_running", test=test_pick)

                    elif (_dg.get('failed_key') == cache_key) and auto_trigger and (not run_detail):
                        st.warning('Авто‑детальный прогон подавлен: предыдущая попытка для этого набора завершилась ошибкой. Нажмите кнопку **"Рассчитать полный лог и показать"** для повтора.')
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
                        _dg["progress"] = 0.0
                        st.session_state["detail_guard"] = _dg

                        # Even if the solver itself runs in a single call, we must show that
                        # a long operation started.
                        _pbar = st.progress(0.02, text="Детальный прогон: подготовка…")
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
                            try:
                                _pbar.progress(0.08, text="Детальный прогон: запуск симуляции…")
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
                                _pbar.progress(0.85, text="Детальный прогон: обработка результатов…")
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
                                _pbar.progress(1.0, text="Детальный прогон: готово")
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
                                    st.warning(f"Авто-экспорт anim_latest не удался: {_e}")
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
                            st.error(f"Ошибка детального прогона: {e}")
                            log_event("detail_error", err=str(e), test=test_pick)
                            try:
                                _pbar.progress(1.0, text="Детальный прогон: ошибка")
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
                    _det_src = "кэш" if ("cache_file" in _det_meta_ui or _det_meta_ui.get("loaded_from_cache")) else "свежий расчёт"
                    if _det_ts:
                        st.caption(f"Детальный лог: {_det_src}; метка времени: {_det_ts}.")
                    else:
                        st.caption(f"Детальный лог: {_det_src}.")
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
                    if df_main is not None and "время_с" in df_main.columns:
                        time_s = df_main["время_с"].astype(float).tolist()
                    elif df_mdot is not None and "время_с" in df_mdot.columns:
                        time_s = df_mdot["время_с"].astype(float).tolist()

                    # Важно: dataset_id для компонентов делаем *уникальным внутри UI‑сессии*.
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
                        st.session_state["playhead_cmd"] = make_playhead_reset_command()
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
                            st.session_state["playhead_cmd"] = make_playhead_jump_command(j)
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

                    # --- События/алёрты (метки на таймлайне) ---
                    cols_evt = st.columns([1, 1, 1, 1])
                    with cols_evt[0]:
                        st.checkbox("События/алёрты", value=True, key="events_show")
                    with cols_evt[1]:
                        st.slider("Вакуум мин, атм(изб)", -1.0, 0.0, -0.2, 0.05, key="events_vacuum_min_atm")
                    with cols_evt[2]:
                        st.slider("Запас к Pmax, атм", 0.0, 1.0, 0.10, 0.05, key="events_pmax_margin_atm")
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
                                vacuum_min_gauge_atm=float(st.session_state.get("events_vacuum_min_atm", -0.2)),
                                pmax_margin_atm=float(st.session_state.get("events_pmax_margin_atm", 0.10)),
                                chatter_window_s=0.25,
                                chatter_toggle_count=int(st.session_state.get("events_chatter_toggles", 6)),
                                max_events=240,
                            )
                        except Exception:
                            events_list = []

                    events_for_graphs, events_graph_labels, events_graph_max = prepare_events_for_graph_overlays(
                        events_list,
                        st.session_state,
                    )

                    render_playhead_results_section(
                        get_playhead_ctrl_component(),
                        dataset_id=dataset_id_ui,
                        time_s=time_s,
                        session_state=st.session_state,
                        events_list=events_list,
                        safe_dataframe_fn=safe_dataframe,
                        df_main=df_main,
                        df_p=df_p,
                        df_mdot=df_mdot,
                        playhead_x=playhead_x,
                        pressure_from_pa_fn=pa_abs_to_atm_g,
                        pressure_unit="атм (изб.)",
                        stroke_scale=1.0,
                        stroke_unit="м",
                        flow_scale_and_unit_fn=flow_rate_display_scale_and_unit,
                        p_atm=P_ATM,
                        model_module=model_mod,
                        info_fn=st.info,
                        caption_fn=st.caption,
                        expander_fn=st.expander,
                        columns_fn=st.columns,
                        checkbox_fn=st.checkbox,
                    )
                    # Важно: st.tabs не "ленивый" — код внутри всех табов исполняется при каждом rerun.
                    # При анимации (auto-refresh) это выглядит как "бесконечный расчёт".
                    # Поэтому используем явный селектор и рендерим только выбранную ветку.
                    if SHOW_TOOLS and (not SHOW_RESULTS):
                        _baseline_view_opts = ["Потоки", "Энерго‑аудит"]
                    else:
                        _baseline_view_opts = ["Графики", "Анимация"]

                    view_res = render_results_view_selector(
                        options=_baseline_view_opts,
                        session_state=st.session_state,
                        cur_hash=cur_hash,
                        test_pick=test_pick,
                        log_event_fn=log_event,
                        radio_fn=st.radio,
                    )


                    if view_res == "Графики":
                        st.subheader("Графики по времени")
                        tcol = "время_с"

                        render_main_overview_graphs(
                            plot_lines_fn=plot_lines,
                            df_main=df_main,
                            tcol=tcol,
                            playhead_x=playhead_x,
                            events=events_for_graphs,
                            events_max=events_graph_max,
                            events_show_labels=events_graph_labels,
                            pressure_title="Давление (атм изб.)",
                            pressure_yaxis_title="атм (изб.)",
                            pressure_transform_fn=lambda a: (a - P_ATM) / ATM_PA,
                        )

                        render_mech_overview_graphs(
                            plot_lines_fn=plot_lines,
                            df_main=df_main,
                            tcol=tcol,
                            playhead_x=playhead_x,
                            events=events_for_graphs,
                            events_max=events_graph_max,
                            events_show_labels=events_graph_labels,
                            session_state=st.session_state,
                            markdown_fn=st.markdown,
                            columns_fn=st.columns,
                            multiselect_fn=st.multiselect,
                            caption_fn=st.caption,
                        )

                        render_node_pressure_expander(
                            df_p=df_p,
                            plot_lines_fn=plot_lines,
                            session_state=st.session_state,
                            playhead_x=playhead_x,
                            events=events_for_graphs,
                            events_max=events_graph_max,
                            events_show_labels=events_graph_labels,
                            title="Давление узлов (df_p, атм изб.)",
                            yaxis_title="атм (изб.)",
                            transform_y_fn=lambda a: (a - P_ATM) / ATM_PA,
                            has_plotly=_HAS_PLOTLY,
                            expander_fn=st.expander,
                            multiselect_fn=st.multiselect,
                            info_fn=st.info,
                            caption_fn=st.caption,
                        )

                        with st.container():
                            render_graph_studio_section(
                                st,
                                df_main=df_main,
                                df_p=df_p,
                                df_mdot=df_mdot,
                                df_open=df_open,
                                cache_key=cache_key,
                                pressure_preset_label="Давления (Pa → атм изб.)",
                                auto_units_label="Auto-units (Pa\u2192\u0430\u0442\u043c, \u0440\u0430\u0434\u2192\u0433\u0440\u0430\u0434)",
                                drop_all_nan=False,
                                session_state=st.session_state,
                                playhead_x=playhead_x,
                                events_for_graphs=events_for_graphs,
                                plot_timeseries_fn=plot_studio_timeseries,
                                excel_bytes_fn=df_to_excel_bytes,
                                safe_dataframe_fn=safe_dataframe,
                            )


                    elif view_res == "Потоки":
                        render_flow_edge_graphs_section(
                            st,
                            df_mdot=df_mdot,
                            df_open=df_open,
                            playhead_x=playhead_x,
                            events_for_graphs=events_for_graphs,
                            events_graph_max=events_graph_max,
                            events_graph_labels=events_graph_labels,
                            p_atm=P_ATM,
                            model_module=model_mod,
                            plot_lines_fn=plot_lines,
                            flow_scale_and_unit_fn=flow_rate_display_scale_and_unit,
                            has_plotly=_HAS_PLOTLY,
                        )

                    elif view_res == "Энерго‑аудит":
                        st.subheader("Энерго‑аудит")
                        if df_Egroups is not None and len(df_Egroups):
                            safe_dataframe(df_Egroups.sort_values("энергия_Дж", ascending=False), height=220)
                            if _HAS_PLOTLY and px is not None:
                                try:
                                    fig = px.bar(df_Egroups.sort_values("энергия_Дж", ascending=False), x="группа", y="энергия_Дж", title="Энергия по группам")
                                    safe_plotly_chart(fig)
                                except Exception:
                                    pass
                        if df_Eedges is not None and len(df_Eedges):
                            st.markdown("**TOP‑20 элементов по энергии**")
                            safe_dataframe(df_Eedges.sort_values("энергия_Дж", ascending=False).head(20), height=320)


                    elif view_res == "Анимация":
                        anim_view = render_animation_view_selector(
                            st,
                            cur_hash=cur_hash,
                            test_pick=test_pick,
                        )

                        def _render_flow_tool_animation() -> None:
                            render_flow_animation_panel(
                                st,
                                df_mdot=df_mdot,
                                df_open=df_open,
                                p_atm=P_ATM,
                                model_module=model_mod,
                                flow_scale_and_unit_fn=flow_rate_display_scale_and_unit,
                                render_flow_panel_html_fn=render_flow_panel_html,
                            )

                        def _render_svg_scheme_animation() -> None:
                            render_svg_scheme_section(
                                st,
                                st.session_state,
                                df_mdot=df_mdot,
                                df_open=df_open,
                                df_p=df_p,
                                base_dir=HERE,
                                default_svg_mapping_path=DEFAULT_SVG_MAPPING_PATH,
                                route_write_view_box=view_box,
                                do_rerun_fn=do_rerun,
                                log_event_fn=log_event,
                                p_atm=P_ATM,
                                model_module=model_mod,
                                pressure_divisor=ATM_PA,
                                pressure_unit="атм (изб.)",
                                dataset_id=dataset_id_ui,
                                safe_dataframe_fn=safe_dataframe,
                                flow_scale_and_unit_fn=flow_rate_display_scale_and_unit,
                                get_component_fn=get_pneumo_svg_flow_component,
                                render_svg_flow_animation_html_fn=render_svg_flow_animation_html,
                                has_svg_autotrace=_HAS_SVG_AUTOTRACE,
                                extract_polylines_fn=extract_polylines,
                                auto_build_mapping_from_svg_fn=auto_build_mapping_from_svg,
                                detect_component_bboxes_fn=detect_component_bboxes,
                                name_score_fn=_name_score,
                                shortest_path_fn=shortest_path_between_points,
                                evaluate_quality_fn=evaluate_route_quality,
                            )

                        # -----------------------------------
                        # (1) Механическая анимация (упрощённая)
                        # -----------------------------------
                        if anim_view == ANIMATION_VIEW_MECHANICS:
                            if render_mechanical_animation_intro(st, df_main=df_main):
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
                                    wheelbase = float(base_override.get("база", 2.3))
                                    track = float(base_override.get("колея", 1.2))
                                except Exception:
                                    wheelbase = 2.3
                                    track = 1.2

                                z = df_main.get("перемещение_рамы_z_м", pd.Series(np.zeros(len(time_s)))).astype(float).to_numpy()
                                phi = df_main.get("крен_phi_рад", pd.Series(np.zeros(len(time_s)))).astype(float).to_numpy()
                                theta = df_main.get("тангаж_theta_рад", pd.Series(np.zeros(len(time_s)))).astype(float).to_numpy()

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
                                    col_w = f"перемещение_колеса_{c}_м"
                                    col_r = f"дорога_{c}_м"
                                    col_s = f"положение_штока_{c}_м"
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
                                _has_road_input = bool(str(_test_cfg.get('road_csv') or '').strip()) or callable(_test_cfg.get('road_func'))
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
                                        index=1,
                                        key=f"anim_backend_{cache_key}",
                                        help="Если видишь ошибки Streamlit Component (например apiVersion undefined) — используй встроенный режим.",
                                    )

                                # Unified boolean used дальше по коду (и чтобы не ловить NameError в ветках)
                                use_component_anim = bool(str(anim_backend).startswith("Компонент"))
                                with col_animB:
                                    st.caption(
                                        "По умолчанию включён компонентный режим (SVG/Canvas): Play/Pause выполняются в браузере и не дёргают сервер на каждый кадр. "
                                        "Если компоненты Streamlit не загружаются/видишь ошибки вида `apiVersion undefined` — переключись на встроенный режим (matplotlib)."
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
                                    else:
                                        if use_component_anim:
                                            st.warning("Компонент mech_anim не найден/не загружается (components/mech_anim). Покажу fallback (matplotlib).")
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
                                        "3D‑wireframe «машинка»: рама (параллелепипед), 4 колеса (цилиндры) и профили дороги под каждым колесом. "
                                        "Крутите сцену мышью, колёсики реально вращаются по пройденному пути."
                                    )

                                    # --- Path / maneuver (pure kinematics, does NOT affect the solver) ---
                                    colA, colB, colC = st.columns(3)
                                    with colA:
                                            demo_paths = st.checkbox(
                                                "3D: доп. траектории (НЕ физика, только визуализация)",
                                                value=False,
                                                key=f"mech3d_demo_paths_{cache_key}",
                                            )
                                            if not demo_paths:
                                                path_mode = "Статика (без движения)"
                                                st.caption("По умолчанию X/Z‑движение отключено. В 3D рисуются только величины из результатов расчёта (крен/тангаж/ходы/дорога).")
                                                # дефолты (в статике почти не используются, но нужны как переменные ниже)
                                                v0 = 12.0
                                                lateral_scale = 1.0
                                                steer_gain = 1.0
                                                steer_max_deg = 35.0
                                            else:
                                                path_mode = st.selectbox(
                                                    "Траектория (для 3D)",
                                                    ["Статика (без движения)", "По ax/ay из модели", "Прямая", "Слалом", "Поворот (радиус)"],
                                                    index=0,
                                                    key=f"mech3d_path_mode_{cache_key}",
                                                )
                                                st.info("3D: траектория X/Z сейчас кинематическая (только визуализация) и НЕ влияет на расчёт. Крен/тангаж/высоты берутся из результатов симуляции. Реальная продольная/поперечная динамика (передача момента/торможение, скорость по дороге и т.д.) — TODO.")
                                                v0 = st.number_input(
                                                    "v0, м/с",
                                                    min_value=0.0,
                                                    max_value=60.0,
                                                    value=12.0,
                                                    step=0.5,
                                                    key=f"mech3d_v0_{cache_key}",
                                                )
                                                lateral_scale = st.number_input(
                                                    "масштаб бокового смещения",
                                                    min_value=0.0,
                                                    max_value=20.0,
                                                    value=1.0,
                                                    step=0.1,
                                                    key=f"mech3d_lat_scale_{cache_key}",
                                                )
                                                steer_gain = st.number_input(
                                                    "усиление руления (по φ)",
                                                    min_value=0.0,
                                                    max_value=10.0,
                                                    value=1.0,
                                                    step=0.1,
                                                    key=f"mech3d_steer_gain_{cache_key}",
                                                )
                                                steer_max_deg = st.slider(
                                                    "ограничение руления, град",
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
                                                yaw_smooth = 0.15
                                                turn_radius = 35.0
                                                turn_dir = "влево"

                                    with colC:
                                        # --- Geometry / viz ---
                                        base_m = float(base_override.get("база", 2.8))
                                        track_m = float(base_override.get("колея", 1.6))
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
                                        camera_follow = st.checkbox("Камера следует за машиной (центр кадра)", value=True, key=f"mech3d_cam_follow_{cache_key}")
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
                                            "Hover‑подсказки (колесо/ось): wheel/road/gap",
                                            value=True,
                                            key=f"mech3d_hover_tooltip_{cache_key}",
                                        )
                                        show_minimap = st.checkbox(
                                            "Мини‑карта (вид сверху) поверх сцены",
                                            value=False,
                                            key=f"mech3d_show_minimap_{cache_key}",
                                        )
                                        minimap_size = st.slider(
                                            "Размер мини‑карты (px)",
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
                                            value=6,
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
                                    if path_mode == "Поворот (радиус)":
                                        # yaw already set by the turn generator
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

                                    mech3d_comp = get_mech_car3d_component() if use_component_anim else None
                                    if mech3d_comp is None:
                                        if use_component_anim:
                                            st.warning("Компонент mech_car3d не найден/не загружается (components/mech_car3d). Покажу fallback (matplotlib).")
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
                                        }

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
                                render_mechanical_scheme_asset_expander(
                                    st,
                                    base_dir=HERE,
                                    safe_image_fn=safe_image,
                                )

                        else:
                            render_non_mechanical_animation_subsection(
                                anim_view,
                                render_flow_tool_fn=_render_flow_tool_animation,
                                render_svg_scheme_fn=_render_svg_scheme_animation,
                            )



if SHOW_RUN:
    # -------------------------------
    # Оптимизация (фон)
    # -------------------------------
    st.divider()
    st.header("Оптимизация (фон)")

    colO1, colO2, colO3 = st.columns([1.2, 1.0, 1.0], gap="large")

    with colO1:
        st.markdown("**Команды**")
        btn_start = st.button("Старт оптимизации", disabled=pid_alive(st.session_state.opt_proc) or bool(param_errors) or bool(suite_errors))
        colS1, colS2 = st.columns(2)
        with colS1:
            btn_stop_soft = st.button("Стоп (мягко)", disabled=not pid_alive(st.session_state.opt_proc), help="Создаёт STOP‑файл. Оптимизатор сам корректно завершится и сохранит CSV/прогресс.")
        with colS2:
            btn_stop_hard = st.button("Стоп (жёстко)", disabled=not pid_alive(st.session_state.opt_proc), help="Создаёт STOP‑файл и принудительно завершает процесс. Используйте только если мягкая остановка не срабатывает.")

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
                progress_path = out_csv_path.with_suffix("")
                progress_path = str(progress_path) + "_progress.json"
                if os.path.exists(progress_path):
                    with open(progress_path, "r", encoding="utf-8") as f:
                        prog = json.load(f)
                    try:
                        _mtime = os.path.getmtime(progress_path)
                        _age = time.time() - float(_mtime)
                        st.caption(f"Прогресс‑файл обновлён {_age:.1f} с назад: {progress_path}")
                        # Если процесс жив, а файл давно не обновлялся — вероятно завис/упал или пишет в другой каталог.
                        if pid_alive(st.session_state.opt_proc) and (_age > max(300.0, 10.0*float(refresh_sec) + 5.0)):
                            st.caption("⚠️ Прогресс‑файл давно не обновлялся. Если это неожиданно — проверьте, что worker пишет progress.json в тот же каталог и что расчёт не завис.")
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

        # Создаём файл прогресса заранее (чтобы UI не писал «файл прогресса не создан» из‑за гонки времени).
        # Worker перезапишет его своим первым update.
        try:
            progress_path = os.path.splitext(out_csv)[0] + "_progress.json"
            write_json({
                "статус": "запущено",
                "готово_кандидатов": 0,
                "прошло_сек": 0.0,
                "лимит_минут": float(minutes),
                "последний_batch": 0,
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
        # удалим стоп‑файл (если был)
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
        # Мягкая остановка: только STOP‑файл. Процесс сам завершится, запишет прогресс и корректно закроет файлы.
        try:
            (HERE / "STOP_OPTIMIZATION.txt").write_text("stop", encoding="utf-8")
        except Exception:
            pass
        st.session_state.opt_stop_requested = True
        do_rerun()

    if 'btn_stop_hard' in locals() and btn_stop_hard:
        # Жёсткая остановка: STOP‑файл + принудительное завершение процесса (если нужно).
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

            # (опционально) фильтр по штрафу — НЕ включён по умолчанию
            use_pen_filter = st.checkbox("Фильтровать по штрафу физичности", value=False, key="pareto_pen_filter")
            if use_pen_filter and "штраф_физичности_сумма" in df_all2.columns:
                pen_max_default = float(np.nanmax(df_all2["штраф_физичности_сумма"].astype(float).values))
                pen_max = st.number_input("Макс штраф физичности (<=)", min_value=0.0, value=pen_max_default, step=0.5, key="pareto_pen_max")
                df_all2 = df_all2[df_all2["штраф_физичности_сумма"].astype(float) <= float(pen_max)]
            df_all2 = apply_packaging_surface_filters(st, df_all2, key_prefix="pareto", compact=True)

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

                    top_n = st.number_input("TOP‑N для вывода", min_value=5, max_value=500, value=10, step=5, key="pareto_topn")

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





if SHOW_RESULTS:
    # -------------------------------
    # Диаграммы: сравнение прогонов + влияние параметров (N→N)
    # -------------------------------

    st.markdown("---")
    st.subheader("Диаграммы: сравнение и влияние параметров")

    with st.expander("Влияние параметров (N→N) — анализ CSV оптимизации/экспериментов", expanded=False):
        st.caption(
            "Coordinated multiple views: Explorer (выбор) → матрицы/MI → Sankey → PDP/ICE → N×N чувствительность → интеракции (H). "
            "Поддерживает reference CSV (A/B/Δ), сохранение сессий и передачу выбранных NPZ в сравнение."
        )
        enable_pi = st.checkbox(
            "Включить Dashboard влияния (может быть тяжёлым на больших CSV)",
            value=bool(st.session_state.get("pi_enable_dashboard") or False),
            key="pi_enable_dashboard",
            help="Если CSV большой, включайте после выбора файла и фильтров."
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
                st.error(f"Не удалось открыть модуль влияния параметров: {_e}")
        else:
            st.info("Включите чекбокс выше, чтобы отрисовать полный Dashboard влияния.")


    with st.expander("Сравнение прогонов (NPZ) — overlay/small‑multiples/Δ/метрики", expanded=False):
        st.caption(
            "Сравнение нескольких NPZ (Txx_osc.npz): наложение, small‑multiples, разность относительно референса, "
            "метрики (RMS/ptp/mean/min/max), playhead (без лишних rerun) и сохранение сессий сравнения."
        )
        st.info(
            "Если браузер тяжело тянет большие traces — используйте Desktop Compare Viewer: "
            "`INSTALL_DESKTOP_COMPARE_WINDOWS.bat` → `RUN_COMPARE_VIEWER_WINDOWS.bat`."
        )
        enable_cmp = st.checkbox(
            "Включить Dashboard сравнения NPZ",
            value=bool(st.session_state.get("cmp_enable_dashboard") or False),
            key="cmp_enable_dashboard",
            help="Если NPZ много/тяжёлые — включайте после выбора каталога и нужных файлов."
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
                st.error(f"Не удалось открыть модуль сравнения NPZ: {_e}")
        else:
            st.info("Включите чекбокс выше, чтобы отрисовать Dashboard сравнения.")


if SHOW_TOOLS:
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
            st.info("Для mapping нужны: (1) baseline-suite (список тестов) и (2) хотя бы один файл NPZ/CSV в osc_dir.")

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
            "Если реальных замеров пока нет — можно генерировать «расчётные» NPZ из текущего baseline "
            "и гонять пайплайны oneclick/autopilot как самопроверку форматов и обвязки."
        )

        col_fc1, col_fc2, col_fc3 = st.columns(3)

        def _ensure_full_npz_for_all_tests(_mode_label: str) -> tuple[bool, str]:
            """Гарантирует, что в osc_dir есть Txx_osc.npz для всех тестов baseline-suite.

            Возвращает (ok, message).
            """
            _tests = list((_tests_map or {}).items())
            if not _tests:
                return False, "Нет baseline-suite (списка тестов). Сначала рассчитай baseline."
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

if SHOW_TOOLS:
    # -------------------------------
    # Диагностика (ZIP для отправки)
    # -------------------------------
    with st.expander("Диагностика — собрать ZIP (для отправки)", expanded=False):
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
# Поэтому используем фронтенд‑таймер streamlit‑autorefresh (если установлен).
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
