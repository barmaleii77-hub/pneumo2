# -*- coding: utf-8 -*-
"""
pneumo_ui_app.py

Streamlit UI:
- запуск одиночных тестов (baseline),
- запуск оптимизации (фоновый процесс) из UI,
- просмотр/фильтр результатов.

Требования: streamlit, numpy, pandas, openpyxl.

"""
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
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Any, List, Optional

from pneumo_solver_ui.data_contract import build_geometry_meta_from_base, assert_required_geometry_meta, supplement_animator_geometry_meta
from pneumo_solver_ui.solver_points_contract import assert_required_solver_points_contract
from pneumo_solver_ui.visual_contract import build_visual_reload_diagnostics
from pneumo_solver_ui.browser_perf_artifacts import persist_browser_perf_snapshot_event
from pneumo_solver_ui.suite_contract_migration import migrate_legacy_suite_columns

import copy
import gzip
import pickle

from difflib import SequenceMatcher

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

import streamlit.components.v1 as components
from pneumo_solver_ui.streamlit_compat import request_rerun
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


def get_osc_dir() -> Path:
    """Return current osc_dir.

    The UI exposes osc_dir via a text_input (key: osc_dir_path). If user didn't touch it
    (or the expander wasn't opened), we fall back to WORKSPACE_OSC_DIR.
    """
    try:
        p = st.session_state.get("osc_dir_path")
        if isinstance(p, str) and p.strip():
            return Path(p).expanduser()
    except Exception:
        pass
    return WORKSPACE_OSC_DIR
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


def get_ui_nonce() -> str:
    """Короткий nonce на сессию UI.

    Зачем нужен:
    - Компоненты анимации синхронизируются через localStorage.
    - При refresh окна/вкладки localStorage может содержать "старое" состояние play/pause.
    - Если dataset_id совпадает, фронт может на доли секунды подхватить старый playhead.

    Поэтому мы добавляем per-session nonce в dataset_id (не влияет на кэш расчётов),
    чтобы *любая* новая Streamlit-сессия считалась "новым датасетом" для анимации.
    """

    n = st.session_state.get("_ui_nonce")
    if not n:
        n = uuid.uuid4().hex[:8]
        st.session_state["_ui_nonce"] = n
    return str(n)

def _proc_metrics() -> Dict[str, Any]:
    """Снимок метрик процесса (CPU/RAM) — best effort."""

    if not _HAS_PSUTIL or psutil is None:
        return {}

    # На Windows/корп. ПК отдельные вызовы psutil иногда падают
    # (AccessDenied/NotImplementedError). Поэтому собираем "по кускам":
    # что смогли — то записали.
    out: Dict[str, Any] = {}
    try:
        p = psutil.Process(os.getpid())
        out["pid"] = p.pid
    except Exception:
        return {}

    try:
        mem = p.memory_info()
        out["rss_mb"] = round(mem.rss / 1024 / 1024, 1)
        out["vms_mb"] = round(mem.vms / 1024 / 1024, 1)
    except Exception:
        pass

    try:
        out["cpu_num"] = p.cpu_num()
    except Exception:
        pass

    try:
        out["cpu_count"] = psutil.cpu_count(logical=True)
    except Exception:
        pass

    # cpu_percent требует "прогрева"; всё равно полезно видеть хоть что-то.
    try:
        out["cpu_percent"] = p.cpu_percent(interval=None)
    except Exception:
        pass

    return out

# -------------------------------
# Bi-directional SVG component (click on scheme -> Python)
# -------------------------------

_PNEUMO_SVG_FLOW_COMPONENT = None


def get_pneumo_svg_flow_component():
    """Return (and cache) the bi-directional SVG flow component callable.

    The component is served from ./components/pneumo_svg_flow (index.html).
    If the folder is missing for some reason, the app will fall back
    to the static HTML renderer.
    """
    global _PNEUMO_SVG_FLOW_COMPONENT
    if _PNEUMO_SVG_FLOW_COMPONENT is not None:
        return _PNEUMO_SVG_FLOW_COMPONENT
    comp_dir = HERE / "components" / "pneumo_svg_flow"
    if comp_dir.exists():
        try:
            # declare_component expects an absolute path
            _PNEUMO_SVG_FLOW_COMPONENT = components.declare_component(
                "pneumo_svg_flow",
                path=str(comp_dir.resolve()),
            )
        except Exception:
            _PNEUMO_SVG_FLOW_COMPONENT = None
    else:
        _PNEUMO_SVG_FLOW_COMPONENT = None
    return _PNEUMO_SVG_FLOW_COMPONENT


# -------------------------------
# Mechanical animation component (front/side views)
# -------------------------------

_MECH_ANIM_COMPONENT = None


def get_mech_anim_component():
    """Return (and cache) the mechanical animation component callable.

    The component is served from ./components/mech_anim (index.html).
    If the folder is missing for some reason, the app will fall back
    to a static image.
    """
    global _MECH_ANIM_COMPONENT
    if _MECH_ANIM_COMPONENT is not None:
        return _MECH_ANIM_COMPONENT
    comp_dir = HERE / "components" / "mech_anim"
    if comp_dir.exists():
        try:
            _MECH_ANIM_COMPONENT = components.declare_component(
                "mech_anim",
                path=str(comp_dir.resolve()),
            )
        except Exception:
            _MECH_ANIM_COMPONENT = None
    else:
        _MECH_ANIM_COMPONENT = None
    return _MECH_ANIM_COMPONENT





# -------------------------------
# Mechanical car 3D animation component (wireframe, orbit camera)
# -------------------------------

_MECH_CAR3D_COMPONENT = None


def get_mech_car3d_component():
    """Return (and cache) the 3D car animation component callable.

    The component is served from ./components/mech_car3d (index.html).

    Implementation notes:
      - Pure HTML/JS canvas (no external libs) to keep the repo self‑contained.
      - Reads the global playhead state from localStorage (same key as graphs / SVG).
    """
    global _MECH_CAR3D_COMPONENT
    if _MECH_CAR3D_COMPONENT is not None:
        return _MECH_CAR3D_COMPONENT
    comp_dir = HERE / "components" / "mech_car3d"
    if comp_dir.exists():
        try:
            _MECH_CAR3D_COMPONENT = components.declare_component(
                "mech_car3d",
                path=str(comp_dir.resolve()),
            )
        except Exception:
            _MECH_CAR3D_COMPONENT = None
    else:
        _MECH_CAR3D_COMPONENT = None
    return _MECH_CAR3D_COMPONENT

# -------------------------------
# Global playhead controller component (shared timeline)
# -------------------------------

_PLAYHEAD_CTRL_COMPONENT = None


def get_playhead_ctrl_component():
    """Return (and cache) the global playhead controller component callable.

    The component is served from ./components/playhead_ctrl (index.html).
    It writes playhead state into browser localStorage (so other components can follow)
    and sends throttled playhead updates back to Python for syncing graphs.
    """
    global _PLAYHEAD_CTRL_COMPONENT
    if _PLAYHEAD_CTRL_COMPONENT is not None:
        return _PLAYHEAD_CTRL_COMPONENT
    comp_dir = HERE / "components" / "playhead_ctrl"
    if comp_dir.exists():
        try:
            _PLAYHEAD_CTRL_COMPONENT = components.declare_component(
                "playhead_ctrl",
                path=str(comp_dir.resolve()),
            )
        except Exception:
            _PLAYHEAD_CTRL_COMPONENT = None
    else:
        _PLAYHEAD_CTRL_COMPONENT = None
    return _PLAYHEAD_CTRL_COMPONENT



def _apply_pick_list(cur: Any, name: str, mode: str) -> List[str]:
    if cur is None:
        cur_list: List[str] = []
    elif isinstance(cur, list):
        cur_list = list(cur)
    else:
        try:
            cur_list = list(cur)
        except Exception:
            cur_list = []

    if mode == "replace":
        return [name]
    if name not in cur_list:
        cur_list.append(name)
    return cur_list


def consume_svg_pick_event():
    """Consume last pick event from the SVG component and sync other widgets.

    Why this exists:
    - Streamlit forbids mutating st.session_state[widget_key] after that widget
      has been instantiated in the current run.
    - When the component sends a click event, Streamlit re-runs the script and
      the component value is already present in st.session_state. We can read it
      early in the run and update defaults for multiselects used by graphs.

    The component sends events like:
      {kind: 'edge'|'node', name: str, ts: int}

    This function updates:
      - edges: flow_graph_edges, anim_edges_svg
      - nodes: anim_nodes_svg, node_pressure_plot
      - last selected: svg_selected_edge / svg_selected_node
    """
    evt = st.session_state.get("svg_pick_event")
    if not isinstance(evt, dict):
        return

    # de-duplicate by timestamp (each click sends Date.now())
    ts = evt.get("ts")
    last_ts = st.session_state.get("svg_pick_event_last_ts")
    if ts is not None and ts == last_ts:
        return
    st.session_state["svg_pick_event_last_ts"] = ts

    kind = evt.get("kind")
    name = evt.get("name")
    if not isinstance(name, str) or not name.strip():
        return
    name = name.strip()
    if kind not in ("edge", "node", "label", "review_nav", "review_filter", "review_toggle"):
        return

    # review action from SVG overlay (approve/pending/reject) — updates mapping JSON text
    try:
        if kind == "edge":
            ra = evt.get("review_action")
            if isinstance(ra, str):
                ra = ra.strip().lower()
            if ra in ("approved", "pending", "rejected"):
                mapping_text = st.session_state.get("svg_mapping_text", "")
                if isinstance(mapping_text, str) and mapping_text.strip():
                    try:
                        mobj = json.loads(mapping_text)
                    except Exception:
                        mobj = None
                    if isinstance(mobj, dict):
                        mobj.setdefault("version", 2)
                        mobj.setdefault("edges", {})
                        mobj.setdefault("nodes", {})
                        mobj.setdefault("edges_meta", {})
                        if not isinstance(mobj.get("edges_meta"), dict):
                            mobj["edges_meta"] = {}
                        em = mobj["edges_meta"].get(name, {})
                        if not isinstance(em, dict):
                            em = {}
                        em.setdefault("review", {})
                        if not isinstance(em.get("review"), dict):
                            em["review"] = {}
                        em["review"]["status"] = ra
                        em["review"]["by"] = str(evt.get("via", "svg"))
                        em["review"]["ts"] = float(time.time())
                        # preserve existing note, unless provided
                        if isinstance(evt.get("note"), str) and evt.get("note").strip():
                            em["review"]["note"] = evt.get("note").strip()
                        mobj["edges_meta"][name] = em
                        st.session_state["svg_mapping_text"] = json.dumps(mobj, ensure_ascii=False, indent=2)
                        st.session_state["svg_review_last"] = {"edge": name, "status": ra, "ts": float(time.time())}
    except Exception:
        pass


    # -----------------------------------------------------------
    # Review HUD / conveyor events (from SVG component)
    # -----------------------------------------------------------
    if kind == "review_toggle":
        try:
            st.session_state["svg_show_review_overlay"] = bool(evt.get("value"))
        except Exception:
            pass
        return

    if kind == "review_filter":
        try:
            mode = str(evt.get("mode") or "").strip()
        except Exception:
            mode = ""
        if mode == "toggle_pending_only":
            try:
                cur = st.session_state.get("svg_review_statuses", ["approved", "pending", "rejected"])
                cur_set = set([str(x) for x in cur]) if isinstance(cur, (list, tuple)) else set()
                # if already pending-only (pending/unknown), toggle back to full set
                if cur_set and cur_set.issubset({"pending", "unknown"}):
                    st.session_state["svg_review_statuses"] = ["approved", "pending", "rejected"]
                else:
                    st.session_state["svg_review_statuses"] = ["pending", "unknown"]
                st.session_state["svg_show_review_overlay"] = True
            except Exception:
                pass
            return

    if kind == "review_nav":
        try:
            action = str(evt.get("action") or "").strip()
        except Exception:
            action = ""
        if action in ("next_pending", "prev_pending"):
            try:
                mapping_text = st.session_state.get("svg_mapping_text", "")
                mobj = json.loads(mapping_text) if isinstance(mapping_text, str) and mapping_text.strip() else {}
            except Exception:
                mobj = {}
            pending = []
            try:
                edges_geo = mobj.get("edges", {}) if isinstance(mobj, dict) else {}
                emap = mobj.get("edges_meta", {}) if isinstance(mobj, dict) else {}
                if not isinstance(edges_geo, dict):
                    edges_geo = {}
                if not isinstance(emap, dict):
                    emap = {}
                for e_name, segs in edges_geo.items():
                    if not isinstance(segs, list) or not segs:
                        continue
                    status = "unknown"
                    try:
                        meta = emap.get(str(e_name), {})
                        rv = meta.get("review", {}) if isinstance(meta, dict) else {}
                        stt = rv.get("status", "") if isinstance(rv, dict) else ""
                        status = str(stt) if stt else "unknown"
                    except Exception:
                        status = "unknown"
                    if status in ("pending", "unknown", ""):
                        pending.append(str(e_name))
                pending = sorted(set(pending))
            except Exception:
                pending = []
            if pending:
                cur = str(st.session_state.get("svg_selected_edge") or "")
                if cur in pending:
                    i = pending.index(cur)
                else:
                    i = -1
                if action == "next_pending":
                    j = (i + 1) if (i + 1) < len(pending) else 0
                else:
                    j = (i - 1) if i > 0 else (len(pending) - 1)
                st.session_state["svg_selected_edge"] = pending[j]
                st.session_state["svg_selected_node"] = ""
            return

    # Auto-advance in review mode (after Shift/Ctrl/Alt click on overlay line)
    try:
        if kind == "edge":
            ra = evt.get("review_action")
            if isinstance(ra, str):
                ra2 = ra.strip().lower()
            else:
                ra2 = ""
            if ra2 in ("approved", "rejected") and bool(st.session_state.get("svg_review_auto_advance", True)):
                # select next pending/unknown (in mapping.edges)
                try:
                    mapping_text = st.session_state.get("svg_mapping_text", "")
                    mobj = json.loads(mapping_text) if isinstance(mapping_text, str) and mapping_text.strip() else {}
                except Exception:
                    mobj = {}
                pending = []
                try:
                    edges_geo = mobj.get("edges", {}) if isinstance(mobj, dict) else {}
                    emap = mobj.get("edges_meta", {}) if isinstance(mobj, dict) else {}
                    if not isinstance(edges_geo, dict):
                        edges_geo = {}
                    if not isinstance(emap, dict):
                        emap = {}
                    for e_name, segs in edges_geo.items():
                        if not isinstance(segs, list) or not segs:
                            continue
                        status = "unknown"
                        try:
                            meta = emap.get(str(e_name), {})
                            rv = meta.get("review", {}) if isinstance(meta, dict) else {}
                            stt = rv.get("status", "") if isinstance(rv, dict) else ""
                            status = str(stt) if stt else "unknown"
                        except Exception:
                            status = "unknown"
                        if status in ("pending", "unknown", ""):
                            pending.append(str(e_name))
                    pending = sorted(set(pending))
                except Exception:
                    pending = []
                if pending:
                    cur = str(st.session_state.get("svg_selected_edge") or "")
                    if cur in pending:
                        i = pending.index(cur)
                    else:
                        i = -1
                    j = (i + 1) if (i + 1) < len(pending) else 0
                    st.session_state["svg_selected_edge"] = pending[j]
                    st.session_state["svg_selected_node"] = ""
    except Exception:
        pass


    # label pick from SVG (used by connectivity/pathfinder)
    if kind == "label":
        pmode = evt.get("mode")
        if pmode in ("start", "end"):
            st.session_state["svg_route_label_pick_pending"] = evt
            # exit label-pick mode after successful click
            st.session_state["svg_label_pick_mode"] = ""
        return

    mode = st.session_state.get("svg_click_mode", "replace")
    if mode not in ("add", "replace"):
        mode = "add"

    if kind == "edge":
        st.session_state["svg_selected_edge"] = name
        st.session_state["flow_graph_edges"] = _apply_pick_list(st.session_state.get("flow_graph_edges"), name, mode)
        st.session_state["anim_edges_svg"] = _apply_pick_list(st.session_state.get("anim_edges_svg"), name, mode)

    if kind == "node":
        st.session_state["svg_selected_node"] = name
        st.session_state["anim_nodes_svg"] = _apply_pick_list(st.session_state.get("anim_nodes_svg"), name, mode)
        st.session_state["node_pressure_plot"] = _apply_pick_list(st.session_state.get("node_pressure_plot"), name, mode)


def consume_mech_pick_event():
    """Consume last pick event from mechanical animation components (2D/3D) and sync widgets.

    Components write pick events into Streamlit session_state keys:
      - mech2d_pick_event  (2D schematic)
      - mech3d_pick_event  (3D wireframe)
      - (legacy) mech_pick_event

    Event schema (dict), typical:
      {kind: 'corner'|'axle', name: str, ts: int|float, shift: bool, ctrl: bool, meta: bool, alt: bool, source: str}

    We use this to:
      - highlight selected corners in the mech animation (mech_selected_corners)
      - set defaults for mechanical plots (mech_plot_corners)
    """
    # pick newest event by ts (prefer 3D if equal)
    candidates = []
    for k in ("mech3d_pick_event", "mech2d_pick_event", "mech_pick_event"):
        evt_k = st.session_state.get(k)
        if isinstance(evt_k, dict):
            ts_k = evt_k.get("ts")
            try:
                ts_f = float(ts_k) if ts_k is not None else 0.0
            except Exception:
                ts_f = 0.0
            candidates.append((ts_f, 1 if k == "mech3d_pick_event" else 0, evt_k))

    if not candidates:
        return

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    evt = candidates[0][2]

    # de-duplicate by timestamp
    ts = evt.get("ts")
    last_ts = st.session_state.get("mech_pick_event_last_ts")
    if ts is not None and ts == last_ts:
        return
    st.session_state["mech_pick_event_last_ts"] = ts

    name = evt.get("name")
    if not isinstance(name, str) or not name.strip():
        return
    name = name.strip()

    # click mode: reuse SVG click mode to keep UX consistent
    mode = st.session_state.get("svg_click_mode", "replace")
    if mode not in ("add", "replace"):
        mode = "add"

    # map selection -> corners
    name_l = name.lower()
    if name in ("ЛП", "ПП", "ЛЗ", "ПЗ"):
        corners = [name]
    elif name_l in ("перед", "front", "f", "передок"):
        corners = ["ЛП", "ПП"]
    elif name_l in ("зад", "rear", "r", "задок"):
        corners = ["ЛЗ", "ПЗ"]
    else:
        return

    # apply to mech_selected_corners
    cur_sel = st.session_state.get("mech_selected_corners")
    if not isinstance(cur_sel, list):
        cur_sel = []
    if mode == "replace":
        new_sel = list(dict.fromkeys(corners))
    else:
        new_sel = list(cur_sel)
        for c in corners:
            if c not in new_sel:
                new_sel.append(c)

    st.session_state["mech_selected_corners"] = new_sel

    # also set default corners for mech plots
    st.session_state["mech_plot_corners"] = list(new_sel) if new_sel else st.session_state.get("mech_plot_corners", ["ЛП", "ПП", "ЛЗ", "ПЗ"])


def _extract_plotly_selection_points(plot_state: Any) -> List[Dict[str, Any]]:
    """Best-effort extraction of Plotly selection points from st.plotly_chart state.

    Streamlit returns a dictionary-like PlotlyState object when on_select != "ignore".
    The schema includes .selection.points (list of dicts). See Streamlit docs.
    """
    if plot_state is None:
        return []

    # PlotlyState supports both attribute and key access.
    sel = None
    try:
        sel = plot_state.get("selection") if isinstance(plot_state, dict) else getattr(plot_state, "selection", None)
    except Exception:
        sel = None

    if sel is None:
        try:
            sel = plot_state["selection"]
        except Exception:
            sel = None

    if sel is None:
        return []

    try:
        pts = sel.get("points") if isinstance(sel, dict) else getattr(sel, "points", None)
    except Exception:
        pts = None

    if pts is None:
        try:
            pts = sel["points"]
        except Exception:
            pts = None

    if pts is None:
        return []

    # Ensure list[dict]
    out: List[Dict[str, Any]] = []
    if isinstance(pts, list):
        for p in pts:
            if isinstance(p, dict):
                out.append(p)
            else:
                try:
                    out.append(dict(p))
                except Exception:
                    pass
    return out


def _plotly_points_signature(points: List[Dict[str, Any]]) -> str:
    """Small stable signature for deduplicating selection events."""
    sig_items = []
    for p in points:
        cn = p.get("curve_number", p.get("curveNumber"))
        # point_index is preferred; fall back to point_number
        pi = p.get("point_index", p.get("pointIndex", p.get("point_number", p.get("pointNumber"))))
        try:
            cn_i = int(cn) if cn is not None else -1
        except Exception:
            cn_i = -1
        try:
            pi_i = int(pi) if pi is not None else -1
        except Exception:
            pi_i = -1
        sig_items.append((cn_i, pi_i))

    # order-independent
    sig_items = sorted(set(sig_items))
    s = json.dumps(sig_items, ensure_ascii=False)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def consume_plotly_pick_events():
    """Sync Plotly chart selections -> SVG selection (and animation defaults).

    We use Streamlit native `st.plotly_chart(..., on_select="rerun")` to capture clicks.
    The selection state is stored in st.session_state under the chart key.

    This function runs early in the script (before widgets are created), so it can
    safely update multiselect defaults.
    """

    # 1) Flow chart -> pick edge(s)
    flow_key = "plot_flow_edges"
    flow_state = st.session_state.get(flow_key)
    flow_points = _extract_plotly_selection_points(flow_state)
    if flow_points:
        sig = _plotly_points_signature(flow_points)
        last_sig = st.session_state.get(flow_key + "__last_sig")
        if sig != last_sig:
            st.session_state[flow_key + "__last_sig"] = sig

            # also: click on plot -> request playhead jump by x (time)
            try:
                x0 = flow_points[0].get("x")
                if x0 is not None:
                    st.session_state["playhead_request_x"] = float(x0)
            except Exception:
                pass

            trace_names = st.session_state.get(flow_key + "__trace_names")
            if isinstance(trace_names, list) and trace_names:
                picked = []
                for p in flow_points:
                    cn = p.get("curve_number", p.get("curveNumber"))
                    try:
                        ci = int(cn)
                    except Exception:
                        continue
                    if 0 <= ci < len(trace_names):
                        picked.append(str(trace_names[ci]))

                # unique, keep order
                seen = set()
                picked_u = []
                for name in picked:
                    if name not in seen:
                        seen.add(name)
                        picked_u.append(name)

                if picked_u:
                    # Graph click behavior: highlight + ensure it is included in animation list.
                    # We intentionally do NOT "replace" multiselects here to avoid surprising UI resets.
                    for name in picked_u:
                        st.session_state["svg_selected_edge"] = name
                        st.session_state["anim_edges_svg"] = _apply_pick_list(st.session_state.get("anim_edges_svg"), name, "add")

    # 2) Node pressure chart -> pick node(s)
    node_key = "plot_node_pressure"
    node_state = st.session_state.get(node_key)
    node_points = _extract_plotly_selection_points(node_state)
    if node_points:
        sig = _plotly_points_signature(node_points)
        last_sig = st.session_state.get(node_key + "__last_sig")
        if sig != last_sig:
            st.session_state[node_key + "__last_sig"] = sig

            # also: click on plot -> request playhead jump by x (time)
            try:
                x0 = node_points[0].get("x")
                if x0 is not None:
                    st.session_state["playhead_request_x"] = float(x0)
            except Exception:
                pass

            trace_names = st.session_state.get(node_key + "__trace_names")
            if isinstance(trace_names, list) and trace_names:
                picked = []
                for p in node_points:
                    cn = p.get("curve_number", p.get("curveNumber"))
                    try:
                        ci = int(cn)
                    except Exception:
                        continue
                    if 0 <= ci < len(trace_names):
                        picked.append(str(trace_names[ci]))

                seen = set()
                picked_u = []
                for name in picked:
                    if name not in seen:
                        seen.add(name)
                        picked_u.append(name)

                if picked_u:
                    for name in picked_u:
                        st.session_state["svg_selected_node"] = name
                        st.session_state["anim_nodes_svg"] = _apply_pick_list(st.session_state.get("anim_nodes_svg"), name, "add")
                        st.session_state["node_pressure_plot"] = _apply_pick_list(st.session_state.get("node_pressure_plot"), name, "add")


def consume_playhead_event():
    """Consume global playhead updates from the playhead_ctrl component.

    The component sends events like:
      {kind: 'playhead', dataset_id: str, idx: int, t: float, playing: bool, speed: float, loop: bool, ts: int}

    We store the latest state in st.session_state:
      - playhead_idx (int)
      - playhead_t (float)
      - playhead_playing (bool)
      - playhead_speed (float)
      - playhead_loop (bool)
      - playhead_dataset_id (str)
    """
    evt = st.session_state.get("playhead_event")
    if not isinstance(evt, dict):
        return

    if evt.get("kind") == "browser_perf_snapshot":
        ts = evt.get("ts")
        last_perf_ts = st.session_state.get("playhead_browser_perf_last_ts")
        if ts is not None and ts == last_perf_ts:
            return
        st.session_state["playhead_browser_perf_last_ts"] = ts
        try:
            perf_summary = persist_browser_perf_snapshot_event(evt, WORKSPACE_EXPORTS_DIR)
        except Exception:
            perf_summary = None
        if isinstance(perf_summary, dict):
            st.session_state["browser_perf_summary"] = perf_summary
            try:
                log_event(
                    "browser_perf_snapshot_exported",
                    dataset_id=str(perf_summary.get("browser_perf_dataset_id") or evt.get("dataset_id") or ""),
                    component_count=int(perf_summary.get("browser_perf_component_count") or 0),
                    total_wakeups=int(perf_summary.get("browser_perf_total_wakeups") or 0),
                    total_duplicate_guard_hits=int(perf_summary.get("browser_perf_total_duplicate_guard_hits") or 0),
                    trace_exists=bool(perf_summary.get("browser_perf_trace_exists")),
                    level=str(perf_summary.get("browser_perf_level") or ""),
                    proc=_proc_metrics(),
                )
            except Exception:
                pass
        return

    if evt.get("kind") not in (None, "playhead"):
        return

    ts = evt.get("ts")
    last_ts = st.session_state.get("playhead_event_last_ts")
    if ts is not None and ts == last_ts:
        return
    st.session_state["playhead_event_last_ts"] = ts

    # dataset id (to ignore stale storage between runs)
    ds = evt.get("dataset_id")
    if isinstance(ds, str):
        st.session_state["playhead_dataset_id"] = ds

    # idx / t
    try:
        idx = int(evt.get("idx", 0))
    except Exception:
        idx = 0
    if idx < 0:
        idx = 0
    st.session_state["playhead_idx"] = idx

    try:
        t = float(evt.get("t", 0.0))
    except Exception:
        t = 0.0
    st.session_state["playhead_t"] = t

    st.session_state["playhead_playing"] = bool(evt.get("playing", False))

    try:
        sp = float(evt.get("speed", 1.0))
    except Exception:
        sp = 1.0
    if not (sp > 0):
        sp = 1.0
    st.session_state["playhead_speed"] = sp

    st.session_state["playhead_loop"] = bool(evt.get("loop", True))

    picked = evt.get("picked_event")
    if isinstance(picked, dict):
        st.session_state["playhead_picked_event"] = picked

    # Log playhead changes (best effort, throttled by state changes)
    try:
        last = st.session_state.get("_playhead_last_logged")
        if not isinstance(last, dict):
            last = {}

        last_idx = last.get("idx")
        last_play = last.get("playing")
        last_ds = last.get("dataset_id")

        # We log only on meaningful changes to avoid spamming.
        changed = (
            last_idx != idx
            or bool(last_play) != bool(st.session_state.get("playhead_playing"))
            or str(last_ds) != str(ds)
            or isinstance(picked, dict)
        )

        if changed:
            log_event(
                "playhead_update",
                dataset_id=str(ds) if isinstance(ds, str) else None,
                idx=int(idx),
                t=float(t),
                playing=bool(st.session_state.get("playhead_playing")),
                speed=float(st.session_state.get("playhead_speed", 1.0)),
                loop=bool(st.session_state.get("playhead_loop", True)),
                picked_event=bool(isinstance(picked, dict)),
                proc=_proc_metrics(),
            )

        st.session_state["_playhead_last_logged"] = {
            "dataset_id": str(ds) if isinstance(ds, str) else None,
            "idx": int(idx),
            "playing": bool(st.session_state.get("playhead_playing")),
        }
    except Exception:
        pass




def load_py_module(path: Path, module_name: str):
    return load_python_module_from_path(path, module_name)



def call_simulate(
    model_mod,
    params: dict,
    test: dict,
    *,
    dt: Optional[float] = None,
    t_end: Optional[float] = None,
    record_full: bool = False,
    **kwargs,
):
    """Совместимый вызов model.simulate() для разных версий модели.

    Задачи:
    - разные версии модели могут иметь разную сигнатуру simulate()
    - некоторые версии мутируют входные dict => передаём deep-copy
    - dt/t_end иногда не передаются из UI/диагностики => берём из test/params или дефолты
    """

    sim = getattr(model_mod, "simulate", None)
    if sim is None:
        raise AttributeError("model_mod has no simulate()")

    # Нормализация dt/t_end: разрешаем передавать None (тогда берём из test/params или дефолты)
    if dt is None:
        dt = (test or {}).get("dt") or (params or {}).get("dt")
    if t_end is None:
        t_end = (test or {}).get("t_end") or (test or {}).get("t_end_s") or (params or {}).get("t_end")
    try:
        dt = float(dt) if dt is not None else 0.01
    except Exception:
        dt = 0.01
    try:
        t_end = float(t_end) if t_end is not None else 1.0
    except Exception:
        t_end = 1.0

    # Изолируем вызов simulate() от мутаций
    params = copy.deepcopy(params)
    test = copy.deepcopy(test)

    # --- compile time-series inputs (road_csv / axay_csv) for UI detailed simulations ---
    # Важно: baseline использует worker_mod.eval_candidate_once(), который компилирует CSV -> callables.
    # Детальный прогон (call_simulate) должен делать то же самое, иначе сценарий запускается с нулевой дорогой/манёвром.
    ts_compile_ok = 1
    ts_compile_error = ""
    try:
        # импортируем из worker-модуля (единый источник истины)
        from pneumo_solver_ui import opt_worker_v3_margins_energy as _tsw
        if isinstance(test, dict) and (str(test.get('road_csv') or '').strip() or str(test.get('axay_csv') or '').strip()):
            test = _tsw._compile_timeseries_inputs(test)
            # alias for legacy models (если где-то ожидается road_func_dot)
            if callable(test.get('road_dfunc')) and (not callable(test.get('road_func_dot'))):
                test['road_func_dot'] = test.get('road_dfunc')
    except Exception as e:
        ts_compile_ok = 0
        ts_compile_error = (f"{type(e).__name__}: {e}")[:300]
        try:
            log_event('timeseries_compile_error', error=ts_compile_error)
        except Exception:
            pass
        if bool((test or {}).get('timeseries_strict', True)):
            raise RuntimeError('Time-series input compile failed: ' + ts_compile_error) from e



    # Базовые именованные аргументы, которые мы пытаемся передать в simulate()
    base_kwargs = dict(params=params, test=test, dt=float(dt), t_end=float(t_end), record_full=bool(record_full))
    extra_kwargs = dict(kwargs or {})

    try:
        sig = inspect.signature(sim)
        allowed = set(sig.parameters.keys())
        # Если simulate ожидает позиционные (params, test, ...), тоже поддержим.
        # Мы просто фильтруем kwargs до разрешённых имён.
        call_kwargs = {k: v for k, v in {**base_kwargs, **extra_kwargs}.items() if k in allowed}

        dropped = sorted(set({**base_kwargs, **extra_kwargs}.keys()) - set(call_kwargs.keys()))
        if dropped:
            log_event("call_simulate_dropped_kwargs", dropped=dropped)

        return sim(**call_kwargs)
    except TypeError:
        # Иногда signature() не отражает реальность (C-обёртки и т.п.) => пробуем строго совместимый вызов
        return sim(params, test, dt=float(dt), t_end=float(t_end), record_full=bool(record_full))
    except Exception:
        # Последний шанс: строго ожидаем сигнатуру simulate(params, test, dt=..., t_end=..., record_full=...)
        return sim(params, test, dt=float(dt), t_end=float(t_end), record_full=bool(record_full))


def compute_road_profile_from_suite(
    model_mod: Any,
    test_obj: Dict[str, Any],
    time_s: List[float],
    wheelbase_m: float,
    track_m: float,
    corners: List[str],
) -> Optional[Dict[str, List[float]]]:
    """Road profile under each wheel corner from suite definition (input).

    Why: some solver versions don't export road(t) columns into the output log. In that case
    the animation would show moving wheels but a flat/zero road, which is misleading.
    This helper reconstructs the road profile *from the same suite test definition* that
    the solver uses (via model_mod._compile_suite_test_inputs), so we stay truthful.

    Returns dict corner->list[float] or None if not available.
    """
    try:
        if model_mod is None:
            return None
        compile_fn = getattr(model_mod, "_compile_suite_test_inputs", None)
        if not callable(compile_fn):
            return None

        # ABSOLUTE LAW: no duplicated aliases like "база_м"/"колея_м".
        # Canonical model/base keys are "база" and "колея" (meters).
        params = {"база": float(wheelbase_m), "колея": float(track_m)}
        add = compile_fn(test_obj, params)
        road_func = add.get("road_func")
        if not callable(road_func):
            return None

        arr = np.asarray([road_func(float(t)) for t in time_s], dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 4:
            return None

        out: Dict[str, List[float]] = {}
        for i, c in enumerate(corners[:4]):
            out[c] = arr[:, i].astype(float).tolist()
        return out
    except Exception:
        return None


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






def parse_sim_output(out: Any, *, want_full: bool = False) -> Dict[str, Any]:
    """Нормализует вывод model.simulate() в единый dict.

    В проекте одновременно гуляли несколько форматов вывода симулятора.
    Сейчас основной формат (model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py):

    record_full=False:
        (df_main, df_drossel, df_energy, nodes, edges, df_Eedges, df_Egroups, df_atm)

    record_full=True:
        (df_main, df_drossel, df_energy, nodes, edges, df_Eedges, df_Egroups, df_atm,
         df_p, df_mdot, df_open, df_Eedges, df_Egroups, df_atm)

    Эта функция:
    - не падает, если каких-то частей нет;
    - подхватывает повторяющиеся хвостовые df_E*/df_atm (если модель их дублирует);
    - умеет принимать dict-вывод (если в будущем модель сменится).
    """
    res: Dict[str, Any] = {
        "df_main": None,
        "df_drossel": None,
        "df_energy_drossel": None,
        "nodes": None,
        "edges": None,
        "df_Eedges": None,
        "df_Egroups": None,
        "df_atm": None,
        "df_p": None,
        "df_mdot": None,
        "df_open": None,
    }

    if out is None:
        return res

    # Будущий формат (если симулятор начнёт возвращать dict)
    if isinstance(out, dict):
        res.update(out)
        # нормализуем ключи (популярные варианты)
        if res.get("df_main") is None:
            res["df_main"] = out.get("main") or out.get("df")
        return res

    if not isinstance(out, (list, tuple)):
        # неизвестный формат — возвращаем как есть (в лог)
        res["raw"] = out
        return res

    n = len(out)
    try:
        if n > 0: res["df_main"] = out[0]
        if n > 1: res["df_drossel"] = out[1]
        if n > 2: res["df_energy_drossel"] = out[2]
        if n > 3: res["nodes"] = out[3]
        if n > 4: res["edges"] = out[4]
        if n > 5: res["df_Eedges"] = out[5]
        if n > 6: res["df_Egroups"] = out[6]
        if n > 7: res["df_atm"] = out[7]

        # Полный лог (давления/расходы/срабатывания)
        if n >= 11:
            res["df_p"] = out[8]
            res["df_mdot"] = out[9]
            res["df_open"] = out[10]

        # Некоторые версии модели дублируют энергетику/атмосферный баланс в конце — берём хвост, если он есть
        if n >= 12 and isinstance(out[11], pd.DataFrame):
            res["df_Eedges"] = out[11]
        if n >= 13 and isinstance(out[12], pd.DataFrame):
            res["df_Egroups"] = out[12]
        if n >= 14 and isinstance(out[13], pd.DataFrame):
            res["df_atm"] = out[13]

    except Exception as e:
        # Ничего не роняем — но логируем в UI лог.
        try:
            log_event("parse_sim_output_error", err=str(e), n=int(n))
        except Exception:
            pass
        res["raw"] = out

    # want_full=True: просто подсказка вызывающему коду, что он ожидает df_p/df_mdot/df_open.
    # Если модель их не вернула, тут останется None (UI покажет понятное предупреждение).
    return res


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


def is_any_fallback_anim_playing() -> bool:
    """True если где-либо активен Play в fallback‑анимации (2D/3D).

    В fallback‑режиме анимация реализована через st_autorefresh -> частые rerun.
    Если в этот момент пересоздавать тяжёлые Plotly‑графики, пользователю кажется,
    что идёт "бесконечный расчёт".
    """
    try:
        for k, v in st.session_state.items():
            if not isinstance(k, str):
                continue
            if not k.endswith("::play"):
                continue
            if not (k.startswith("mech2d_fb_") or k.startswith("mech3d_fb_")):
                continue
            if bool(v):
                return True
    except Exception:
        # Никогда не падать из-за этого хелпера.
        return False
    return False


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
ANIM_LATEST_NPZ_NAME = "anim_latest.npz"
ANIM_LATEST_PTR_NAME = "anim_latest.json"


def get_anim_latest_paths() -> tuple[Path, Path]:
    """Return (npz_path, pointer_json_path) inside WORKSPACE_EXPORTS_DIR.

    Desktop Animator can run in "follow" mode and watch the pointer JSON.
    This keeps the workflow almost zero-click:
      1) Run a detail simulation in Streamlit
      2) Animator auto-reloads anim_latest
    """
    try:
        exp_dir = Path(WORKSPACE_EXPORTS_DIR)
    except Exception:
        exp_dir = Path(__file__).resolve().parent / "workspace" / "exports"
    exp_dir.mkdir(parents=True, exist_ok=True)
    return exp_dir / ANIM_LATEST_NPZ_NAME, exp_dir / ANIM_LATEST_PTR_NAME


def write_anim_latest_pointer(npz_path: Path, *, meta: dict | None = None, pointer_path: Path | None = None) -> Path:
    """Write anim_latest.json pointer for Desktop Animator.

    Pointer diagnostics must expose not only the NPZ path but also the visual
    dependency token used by web/desktop reload logic.
    """
    import json as _json
    import time as _time
    from datetime import datetime as _datetime, timezone as _timezone

    npz_path = Path(npz_path).expanduser().resolve()
    if pointer_path is None:
        _, pointer_path = get_anim_latest_paths()
    pointer_path = Path(pointer_path)
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    meta_obj = dict(meta or {})
    reload_diag = build_visual_reload_diagnostics(
        npz_path,
        meta=meta_obj,
        context="anim_latest legacy pointer",
        log=_APP_LOGGER.warning,
    )
    rec = {
        "ts": float(_time.time()),
        "updated_utc": _datetime.now(_timezone.utc).isoformat(),
        "npz_path": str(npz_path),
        "meta": meta_obj,
        "visual_cache_token": reload_diag.get("visual_cache_token", ""),
        "visual_reload_inputs": list(reload_diag.get("inputs") or []),
        "visual_cache_dependencies": dict(reload_diag.get("visual_cache_dependencies") or {}),
    }
    pointer_path.write_text(_json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from pneumo_solver_ui.run_artifacts import save_latest_animation_ptr

        save_latest_animation_ptr(npz_path=npz_path, pointer_json=pointer_path, meta=meta_obj)
    except Exception:
        pass
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
            write_anim_latest_pointer(out, meta=meta)
            return out
        except Exception:
            return None


def write_tests_index_csv(osc_dir: Path, tests: List[dict], *, filename: str = "tests_index.csv") -> Path:
    """Генерирует tests_index.csv рядом с NPZ для пайплайнов калибровки.

    Почему это важно:
    - calibration/pipeline_npz_oneclick_v1.py ожидает tests_index.csv с колонкой "имя_теста".
    - Ранее UI экспортировал только Txx_osc.npz, из-за чего autopilot мог искать файлы не там/не так.

    Формат (минимально достаточный):
      - test_num (1..N)
      - имя_теста (строка)
      - npz_file (имя файла)
    """
    osc_dir = Path(osc_dir)
    osc_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, t in enumerate(tests, start=1):
        name = str(t.get("name", f"T{i:02d}"))
        rows.append({
            "test_num": int(i),
            "имя_теста": name,
            "npz_file": f"T{i:02d}_osc.npz",
        })

    df = pd.DataFrame(rows)
    out = osc_dir / filename
    try:
        # utf-8-sig помогает Excel на Windows корректно открыть русские заголовки
        out.write_text(df.to_csv(index=False), encoding="utf-8-sig")
    except Exception:
        df.to_csv(out, index=False)
    return out

def make_ui_diagnostics_zip(
    out_zip_path=None,
    *,
    base_json=None,
    suite_json=None,
    ranges_json=None,
    tag="ui",
    include_logs=True,
    include_results=True,
    include_calibration=True,
    include_workspace=True,
    extra_paths=None,
    meta=None,
):
    """Собрать диагностический ZIP прямо из UI.

    Зачем:
    - когда что-то "плывёт" в окружении пользователя (Windows/прокси/версии Streamlit)
      нужен единый ZIP со всеми логами, конфигами и выходными файлами;
    - чтобы можно было прислать его сюда без отправки всей папки проекта.

    В ZIP кладём:
    - meta.json (версии/платформа/время)
    - base/suite/ranges снапшоты (json)
    - logs/ (ui_*.log, metrics_*.jsonl, combined)
    - results/ (если есть)
    - calibration_runs/ (если есть)
    - workspace/ (osc/, exports/, diagnostics/ ...)
    - любые extra_paths
    """
    import zipfile
    import json as _json

    # default path
    if out_zip_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_zip_path = (WORKSPACE_DIR / "diagnostics" / f"ui_diagnostics_{ts}_{tag}.zip")
    out_zip_path = Path(out_zip_path)
    out_zip_path.parent.mkdir(parents=True, exist_ok=True)

    extra_paths = list(extra_paths or [])

    # default folders that matter for debugging
    default_paths = []
    if include_logs:
        default_paths.append(LOG_DIR)
    if include_results:
        default_paths.append(HERE / "results")
    if include_calibration:
        default_paths.append(HERE / "calibration_runs")
    if include_workspace:
        default_paths.append(WORKSPACE_DIR)
    all_paths = default_paths + extra_paths

    # meta
    meta = dict(meta or {})
    meta.setdefault("app_release", APP_RELEASE)
    meta.setdefault("python", sys.version)
    meta.setdefault("platform", platform.platform())
    meta.setdefault("ts", datetime.now().isoformat(timespec="seconds"))

    # helper
    def _write_json(zf, name, obj):
        try:
            zf.writestr(name, _json.dumps(obj, ensure_ascii=False, indent=2))
        except Exception as e:
            zf.writestr(name + ".error.txt", f"Failed to serialize {name}: {e}")

    def _should_skip(p: Path) -> bool:
        suf = p.suffix.lower()
        if suf in {".pyc", ".pyo"}:
            return True
        # extremely large caches / venv should not be included
        parts = set(p.parts)
        if ".venv" in parts or "__pycache__" in parts:
            return True
        return False

    with zipfile.ZipFile(out_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta.json", _json.dumps(meta, ensure_ascii=False, indent=2))
        if base_json is not None:
            _write_json(zf, "snapshot/base_json.json", base_json)
        if suite_json is not None:
            _write_json(zf, "snapshot/suite_json.json", suite_json)
        if ranges_json is not None:
            _write_json(zf, "snapshot/ranges_json.json", ranges_json)

        for base in all_paths:
            base = Path(base)
            if not base.exists():
                continue
            if base.is_file():
                if _should_skip(base):
                    continue
                arc = str(base.relative_to(HERE)) if str(base).startswith(str(HERE)) else str(base.name)
                zf.write(base, arcname=arc)
                continue
            # directory
            for p in base.rglob("*"):
                if p.is_dir() or _should_skip(p):
                    continue
                arc = str(p.relative_to(HERE)) if str(p).startswith(str(HERE)) else str(Path(base.name) / p.relative_to(base))
                zf.write(p, arcname=arc)

    return out_zip_path
def pareto_front_2d(df: pd.DataFrame, obj1: str, obj2: str) -> pd.Series:
    """Булев маск недоминируемых точек (минимизация obj1 и obj2).

    Быстрый алгоритм для 2D:
      сортируем по obj1 по возрастанию и держим текущий минимум obj2.
    """
    if len(df) == 0:
        return pd.Series([], dtype=bool)
    d = df[[obj1, obj2]].copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) == 0:
        return pd.Series([False] * len(df), index=df.index)
    d = d.sort_values(obj1, ascending=True)
    best2 = float("inf")
    keep_idx = []
    for idx, row in d.iterrows():
        v2 = float(row[obj2])
        if v2 < best2:
            keep_idx.append(idx)
            best2 = v2
    return df.index.isin(keep_idx)


def df_to_excel_bytes(sheets: dict) -> bytes:
    """Собирает Excel из набора {sheet_name: DataFrame} в память."""
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        for name, frame in sheets.items():
            frame.to_excel(w, sheet_name=str(name)[:31], index=False)
    bio.seek(0)
    return bio.read()


def stable_obj_hash(obj: Any) -> str:
    """Стабильный короткий хэш для словарей параметров/тестов.

    Нужен, чтобы:
    - понимать, что baseline был рассчитан именно для текущих параметров,
    - кэшировать «полный лог» (record_full=True) по ключу.
    """
    try:
        s = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        s = str(obj)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]




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


def _baseline_cache_meta_path(cache_dir: Path) -> Path:
    return cache_dir / "meta.json"


def _baseline_cache_table_path(cache_dir: Path) -> Path:
    return cache_dir / "baseline_table.csv"


def _baseline_cache_tests_path(cache_dir: Path) -> Path:
    return cache_dir / "tests_map.json"


def _baseline_cache_base_path(cache_dir: Path) -> Path:
    return cache_dir / "base_override.json"


def _baseline_cache_last_ptr_path() -> Path:
    return WORKSPACE_DIR / "cache" / "baseline" / "_last_baseline.json"


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomic text write: write to *.tmp then replace.

    Streamlit app can be interrupted at any time; atomic writes prevent corrupt caches.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def _atomic_write_csv(path: Path, df: pd.DataFrame) -> None:
    """Atomic CSV write: df -> *.tmp then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)

def save_last_baseline_ptr(cache_dir: Path, meta: Dict[str, Any]) -> None:
    try:
        p = _baseline_cache_last_ptr_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_dir": str(cache_dir),
            "ts": datetime.now().isoformat(timespec="seconds"),
            "meta": meta,
        }
        _atomic_write_text(p, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # не критично
        pass


def load_last_baseline_ptr() -> Optional[Dict[str, Any]]:
    """Load pointer to the most recently saved baseline cache.

    Used to restore UI state after browser refresh without forcing baseline recalculation.
    """
    try:
        p = _baseline_cache_last_ptr_path()
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_baseline_cache(cache_dir: Path) -> Optional[Dict[str, Any]]:
    """Load cached baseline if exists. Returns dict or None."""
    try:
        table_p = _baseline_cache_table_path(cache_dir)
        tests_p = _baseline_cache_tests_path(cache_dir)
        base_p = _baseline_cache_base_path(cache_dir)
        if not (table_p.exists() and tests_p.exists() and base_p.exists()):
            return None
        baseline_df = pd.read_csv(table_p)
        tests_map = json.loads(tests_p.read_text(encoding="utf-8"))
        base_override = json.loads(base_p.read_text(encoding="utf-8"))
        meta_p = _baseline_cache_meta_path(cache_dir)
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
        return {
            "baseline_df": baseline_df,
            "tests_map": tests_map,
            "base_override": base_override,
            "meta": meta,
        }
    except Exception:
        return None


def save_baseline_cache(
    cache_dir: Path,
    baseline_df: pd.DataFrame,
    tests_map: Dict[str, Any],
    base_override: Dict[str, Any],
    meta: Dict[str, Any],
) -> None:
    """Persist baseline artifacts for reuse after refresh (atomically).

    Important:
    - Streamlit reruns/refreshes can interrupt writes.
    - Atomic writes prevent partial/corrupt baseline caches.
    """
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_csv(_baseline_cache_table_path(cache_dir), baseline_df)
        _atomic_write_text(
            _baseline_cache_tests_path(cache_dir),
            json.dumps(tests_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _atomic_write_text(
            _baseline_cache_base_path(cache_dir),
            json.dumps(base_override, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _atomic_write_text(
            _baseline_cache_meta_path(cache_dir),
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_last_baseline_ptr(cache_dir, meta)
    except Exception as e:
        log_event("baseline_cache_save_error", error=str(e), cache_dir=str(cache_dir))



def _float_tag(x: float) -> str:
    """Format float into a filesystem-friendly tag (no '.', no '-', stable)."""
    try:
        s = f"{float(x):.6g}"  # 6 significant digits is enough for dt/t_end in UI
    except Exception:
        s = str(x)
    # Filesystem-safe: '.' -> 'p', '-' -> 'm'
    s = s.replace('-', 'm').replace('.', 'p')
    return s



def make_detail_cache_key(model_hash: str, test_name: str, dt: float, t_end: float, max_points: int, want_full: bool) -> str:
    """Canonical key for detail/full-cache entries (in-memory + disk).

    Important: this key must be used everywhere (single-test run, run-all, exports, animation).
    Otherwise we get cache misses and repeated heavy recomputation on reruns.
    """
    return (
        f"{model_hash}::{test_name}::dt{_float_tag(float(dt))}::t{_float_tag(float(t_end))}"
        f"::mp{int(max_points)}::full{int(bool(want_full))}"
    )

def detail_cache_path(cache_dir: Path, test_name: str, dt: float, t_end: float, max_points: int, want_full: bool) -> Path:
    ddir = cache_dir / "detail"
    t = sanitize_test_name(test_name)
    dt_tag = _float_tag(dt)
    te_tag = _float_tag(t_end)
    return ddir / f"{t}__dt{dt_tag}__t{te_tag}__mp{int(max_points)}__full{int(bool(want_full))}.pkl.gz"
def legacy_detail_cache_path(cache_dir: Path, test_name: str, max_points: int, want_full: bool) -> Path:
    """Legacy cache filename (R32 and earlier) without dt/t_end in the name."""
    ddir = cache_dir / "detail"
    t = sanitize_test_name(test_name)
    return ddir / f"{t}__mp{int(max_points)}__full{int(bool(want_full))}.pkl.gz"

def save_detail_cache(cache_dir: Path, test_name: str, dt: float, t_end: float, max_points: int, want_full: bool, payload: Dict[str, Any]) -> Optional[Path]:
    """Persist detail-run payload (atomically) to disk.

    IMPORTANT: We write to a temp file and then os.replace() it to avoid partial/corrupt caches
    if the app/session is interrupted during write.
    """
    p = detail_cache_path(cache_dir, test_name, dt, t_end, max_points, want_full)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with gzip.open(tmp, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, p)
        return p
    except Exception as e:
        # Cleanup temp/partial files and log the error.
        try:
            if 'tmp' in locals() and Path(tmp).exists():
                Path(tmp).unlink(missing_ok=True)
        except Exception:
            pass
        try:
            # If a partial target exists, keep it as a .bad* artifact for diagnostics.
            if p.exists():
                bad = p.with_suffix(p.suffix + f".bad{int(time.time())}")
                try:
                    os.replace(p, bad)
                except Exception:
                    pass
        except Exception:
            pass
        log_event(
            'detail_cache_save_error',
            test=str(test_name),
            dt=float(dt),
            t_end=float(t_end),
            max_points=int(max_points),
            want_full=bool(want_full),
            error=str(e),
        )
        return None

def load_detail_cache(cache_dir: Path, test_name: str, dt: float, t_end: float, max_points: int, want_full: bool) -> Optional[Dict[str, Any]]:
    """Load detail-run payload from disk.

    - Tries new filename (with dt/t_end) first.
    - Falls back to legacy filename (without dt/t_end) for backwards compatibility.
    - On corruption, quarantines the file and returns None.
    """
    p = detail_cache_path(cache_dir, test_name, dt, t_end, max_points, want_full)
    legacy_p = legacy_detail_cache_path(cache_dir, test_name, max_points, want_full)
    for path in [p, legacy_p]:
        if not path.exists():
            continue
        try:
            with gzip.open(path, 'rb') as f:
                payload = pickle.load(f)
            # If we loaded legacy cache, migrate to new name (best-effort).
            if path == legacy_p and not p.exists():
                try:
                    save_detail_cache(cache_dir, test_name, dt, t_end, max_points, want_full, payload)
                except Exception:
                    pass
            return payload
        except Exception as e:
            log_event(
                'detail_cache_load_error',
                test=str(test_name),
                dt=float(dt),
                t_end=float(t_end),
                max_points=int(max_points),
                want_full=bool(want_full),
                path=str(path),
                error=str(e),
            )
            # Quarantine the bad cache so we do not fail repeatedly.
            try:
                bad = path.with_suffix(path.suffix + f".bad{int(time.time())}")
                os.replace(path, bad)
            except Exception:
                pass
            return None
    return None
def downsample_df(df: pd.DataFrame, max_points: int = 1200) -> pd.DataFrame:
    """Уменьшает число точек для графиков/анимации (чтобы не тормозить UI)."""
    if df is None or len(df) <= max_points:
        return df
    idx = np.linspace(0, len(df) - 1, num=max_points, dtype=int)
    return df.iloc[idx].reset_index(drop=True)


# -------------------------------
# Graph Studio helpers (v7.32)
# -------------------------------

def _infer_unit_and_transform(col: str):
    """Infer a display unit + transform function for a column name.

    This is a best-effort heuristic for быстрый инженерный просмотр графиков.
    Returns: (unit: str, transform: callable|None, yaxis_title: str)
    """
    c = str(col)
    # pressures in Pa -> atm gauge (изб.)
    if c.endswith("_Па") and ("давление" in c or "p_" in c.lower()):
        return ("атм (изб.)", lambda a: (a - P_ATM) / ATM_PA, "атм (изб.)")
    # angles rad -> deg
    if c.endswith("_рад") or c.endswith("_rad"):
        return ("град", lambda a: a * 180.0 / math.pi, "град")
    # lengths
    if "_м_с" in c or c.endswith("_м/с") or c.endswith("_m_s"):
        return ("м/с", None, "м/с")
    if c.endswith("_м") or c.endswith("_m"):
        return ("м", None, "м")
    # forces
    if c.endswith("_Н") or c.endswith("_N"):
        return ("Н", None, "Н")
    # default
    return ("", None, "")


def decimate_minmax(x: np.ndarray, y: np.ndarray, max_points: int = 2000):
    """Min-max decimation to preserve spikes (keeps <= max_points points)."""
    try:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
    except Exception:
        return x, y
    n = int(len(x))
    if n <= 0 or n <= int(max_points):
        return x, y

    # We emit 2 points per bin (min+max), so bins ~ max_points/2
    bins = max(2, int(max_points) // 2)
    step = n / float(bins)
    ox = []
    oy = []
    # always include first
    ox.append(float(x[0])); oy.append(float(y[0]) if np.isfinite(y[0]) else float('nan'))

    for bi in range(bins):
        a = int(bi * step)
        b = int((bi + 1) * step)
        if b <= a:
            continue
        if a < 0: a = 0
        if b > n: b = n
        ys = y[a:b]
        if ys.size <= 0:
            continue
        # handle all-NaN bins
        if not np.isfinite(ys).any():
            continue
        i_min = int(np.nanargmin(ys))
        i_max = int(np.nanargmax(ys))
        j1 = a + min(i_min, i_max)
        j2 = a + max(i_min, i_max)
        # append in time order
        ox.append(float(x[j1])); oy.append(float(y[j1]))
        if j2 != j1:
            ox.append(float(x[j2])); oy.append(float(y[j2]))

    # always include last
    ox.append(float(x[-1])); oy.append(float(y[-1]) if np.isfinite(y[-1]) else float('nan'))

    return np.asarray(ox, dtype=float), np.asarray(oy, dtype=float)


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


# -------------------------------
# Event/alert detection for the global timeline (playhead)
# -------------------------------

def _run_starts(mask: np.ndarray) -> List[int]:
    """Return indices where a boolean mask starts being True (rising edges of a run)."""
    if mask is None:
        return []
    m = np.asarray(mask, dtype=bool)
    if m.size == 0:
        return []
    prev = np.concatenate([[False], m[:-1]])
    starts = np.where(m & (~prev))[0]
    return [int(i) for i in starts.tolist()]


def _shorten_name(name: str, max_len: int = 60) -> str:
    s = str(name)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


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


def render_flow_panel_html(
    time_s: List[float],
    edge_series: List[Dict[str, Any]],
    title: str = "Анимация потоков (MVP)",
    height: int = 520,
):
    """Рендерит HTML (SVG) панель анимации потоков.

    edge_series: список словарей вида:
      {name: str, q: List[float], open: List[int] | None, unit: str}

    Это «инструментальный» MVP: каждая ветка рисуется как отдельная линия,
    по которой бегает маркер (скорость ~ |Q|, направление ~ sign(Q)).

    Почему так:
    - не нужно CAD/SVG‑геометрии схемы,
    - анимация идёт на фронтенде (без постоянных rerun Streamlit).
    """
    payload = {
        "title": title,
        "time": time_s,
        "edges": edge_series,
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { padding: 8px 10px; }
    .hdr { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
    .hdr h3 { margin: 0; font-size: 16px; }
    .btn { padding: 4px 10px; border: 1px solid #bbb; border-radius: 6px; background: #fff; cursor: pointer; }
    .btn:active { transform: translateY(1px); }
    .row { display:flex; align-items:center; gap:10px; margin: 6px 0; }
    .name { width: 380px; font-size: 12px; line-height: 1.1; }
    .val { width: 120px; font-size: 12px; text-align:right; font-variant-numeric: tabular-nums; }
    .svg { flex: 1; height: 18px; }
    .line { stroke: #888; stroke-width: 3; stroke-linecap: round; }
    .line.closed { stroke: #ccc; }
    .dot { fill: #1f77b4; }
    .dot.closed { fill: #bbb; }
    .time { font-variant-numeric: tabular-nums; }
    input[type=range] { width: 320px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hdr">
      <h3 id="title"></h3>
      <button id="play" class="btn">▶︎</button>
      <button id="pause" class="btn">⏸</button>
      <span class="time">t=<span id="t">0.000</span> s</span>
      <input id="slider" type="range" min="0" max="0" value="0" step="1"/>
      <span class="time">idx=<span id="idx">0</span></span>
    </div>
    <div id="rows"></div>
  </div>
  <script>
    const DATA = __JS_DATA__;
    const titleEl = document.getElementById('title');
    const rowsEl = document.getElementById('rows');
    const tEl = document.getElementById('t');
    const idxEl = document.getElementById('idx');
    const slider = document.getElementById('slider');

    titleEl.textContent = DATA.title || 'Flow';

    const T = DATA.time || [];
    const edges = DATA.edges || [];
    const n = T.length;
    slider.max = Math.max(0, n-1);

    // построение строк
    const state = edges.map((e, i) => ({ phase: Math.random(), qmax: 1e-9 }));
    edges.forEach((e, i) => {
      const q = e.q || [];
      let qmax = 1e-9;
      for (let k=0; k<q.length; k++) qmax = Math.max(qmax, Math.abs(q[k]));
      state[i].qmax = qmax;

      const row = document.createElement('div');
      row.className = 'row';

      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = e.name;

      const val = document.createElement('div');
      val.className = 'val';
      val.innerHTML = '<span class="q">0</span> ' + (e.unit || '');

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'svg');
      svg.setAttribute('viewBox', '0 0 500 18');

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', '10');
      line.setAttribute('y1', '9');
      line.setAttribute('x2', '490');
      line.setAttribute('y2', '9');
      line.setAttribute('class', 'line');
      svg.appendChild(line);

      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('r', '5');
      dot.setAttribute('cy', '9');
      dot.setAttribute('cx', '10');
      dot.setAttribute('class', 'dot');
      svg.appendChild(dot);

      row.appendChild(name);
      row.appendChild(svg);
      row.appendChild(val);
      rowsEl.appendChild(row);

      e._dom = {row, line, dot, val};
    });

    function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }

    let idx = 0;
    let playing = false;
    let lastTs = performance.now();
    let lastRenderedIdx = -1;
    let lastRenderedPlaying = null;
    const speedTime = 1.0; // множитель скорости времени (1.0 = real‑time)
    const speedDots = 1.5; // скорость «бегущих точек»

    function renderFrame(dt) {
      idxEl.textContent = String(idx);
      tEl.textContent = (T[idx] ?? 0).toFixed(3);

      // обновление каждой ветки
      edges.forEach((e, i) => {
        const q = e.q || [];
        const open = e.open || null;
        const qv = (q[idx] ?? 0);
        const s = state[i];
        const dir = (qv >= 0) ? 1 : -1;
        const mag = Math.abs(qv);
        const norm = clamp(mag / (s.qmax || 1e-9), 0, 1);

        // фазу маркера крутим только при реальном проигрывании
        if (playing && dt > 0) {
          s.phase = (s.phase + dir * speedDots * norm * dt) % 1;
          if (s.phase < 0) s.phase += 1;
        }
        const x = 10 + s.phase * (490 - 10);
        e._dom.dot.setAttribute('cx', x.toFixed(2));

        const isOpen = open ? !!open[idx] : true;
        e._dom.line.setAttribute('class', 'line' + (isOpen ? '' : ' closed'));
        e._dom.dot.setAttribute('class', 'dot' + (isOpen ? '' : ' closed'));

        // число
        const qEl = e._dom.val.querySelector('.q');
        if (qEl) qEl.textContent = (qv).toFixed(2);
      });

      lastRenderedIdx = idx;
      lastRenderedPlaying = playing;
    }

    function __frameInParentViewport(){
      try {
        const fe = window.frameElement;
        if (!fe || !fe.getBoundingClientRect) return true;
        const r = fe.getBoundingClientRect();
        const w = Number(r.width || Math.max(0, (r.right || 0) - (r.left || 0)) || 0);
        const h = Number(r.height || Math.max(0, (r.bottom || 0) - (r.top || 0)) || 0);
        if (w <= 2 || h <= 2) return false;
        if ((Number(fe.clientWidth || 0) <= 2) || (Number(fe.clientHeight || 0) <= 2)) return false;
        let hiddenByCss = false;
        try {
          const hostView = fe.ownerDocument && fe.ownerDocument.defaultView;
          const cs = (hostView && hostView.getComputedStyle) ? hostView.getComputedStyle(fe) : null;
          hiddenByCss = !!(cs && (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity || '1') === 0));
        } catch(_cssErr) {}
        if (hiddenByCss) return false;
        const hostWin = (window.top && window.top !== window) ? window.top : window;
        const vh = Number(hostWin.innerHeight || window.innerHeight || 0);
        const vw = Number(hostWin.innerWidth || window.innerWidth || 0);
        const margin = 64;
        return (r.bottom >= -margin) && (r.top <= vh + margin) && (r.right >= -margin) && (r.left <= vw + margin);
      } catch(_e) {
        return true;
      }
    }
    function __nextIdleMs(visibleMs, hiddenMs, offscreenMs){
      if (document && document.hidden) return hiddenMs;
      return __frameInParentViewport() ? visibleMs : offscreenMs;
    }
    let __STEP_HANDLE = 0;
    let __STEP_KIND = '';
    function __clearScheduledStep(){
      try {
        if (!__STEP_HANDLE) return;
        if (__STEP_KIND === 'raf' && window.cancelAnimationFrame) window.cancelAnimationFrame(__STEP_HANDLE);
        else clearTimeout(__STEP_HANDLE);
      } catch(_e) {}
      __STEP_HANDLE = 0;
      __STEP_KIND = '';
    }
    function __scheduleStep(kind, delayMs){
      __clearScheduledStep();
      if (kind === 'raf') {
        __STEP_KIND = 'raf';
        __STEP_HANDLE = requestAnimationFrame(step);
      } else {
        __STEP_KIND = 'timeout';
        __STEP_HANDLE = setTimeout(step, Math.max(0, Number(delayMs) || 0));
      }
    }
    function __wakeStep(){
      if (!document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
      else { __STEP_HANDLE = null; }
    }

    function step(ts) {
      const dt = Math.max(0, (ts - lastTs) / 1000.0);
      lastTs = ts;

      if (playing) {
        idx = idx + Math.max(1, Math.floor(speedTime * dt * 60));
        if (idx >= n) idx = 0;
        slider.value = String(idx);
      }

      const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);
      if (shouldRender) renderFrame(dt);

      if (playing && !document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
      else {
        
        __STEP_HANDLE = null;
      }
    }

    slider.addEventListener('input', (ev) => {
      idx = parseInt(slider.value || '0', 10) || 0;
      __wakeStep();
    });
    document.getElementById('play').addEventListener('click', () => { playing = true; __wakeStep(); });
    document.getElementById('pause').addEventListener('click', () => { playing = false; __wakeStep(); });
    window.addEventListener('focus', __wakeStep);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) __wakeStep(); });
window.addEventListener('scroll', () => { try { __wakeStep(); } catch(_e) {} }, {passive:true});
window.addEventListener('resize', () => { try { __wakeStep(); } catch(_e) {} }, {passive:true});

    __wakeStep();
  </script>
</body>
 </html>"""

    # ВАЖНО: намеренно вставляем JSON через replace, чтобы не экранировать все {{ }} в HTML/JS как в f-string.
    html = html.replace("__JS_DATA__", js_data)

    components.html(html, height=height, scrolling=True)



def strip_svg_xml_header(svg_text: str) -> str:
    """Превращает файл SVG в фрагмент, который безопасно вставлять в HTML.

    Многие SVG начинаются с `<?xml ...?>` и комментариев — внутри HTML это может мешать.
    Возвращаем подстроку начиная с первого `<svg`.
    """
    if not svg_text:
        return ""
    p = svg_text.find("<svg")
    if p >= 0:
        return svg_text[p:]
    return svg_text


# -------------------------------
# Автосопоставление имён (ветки/узлы) для mapping JSON
# -------------------------------

_DASH_RE = re.compile(r"[‐‑‒–—−]")
_NONWORD_RE = re.compile(r"[^0-9A-Za-zА-Яа-я]+", re.UNICODE)


def _norm_name(s: Any) -> str:
    """Нормализует имя для устойчивого сопоставления.

    - приводит к нижнему регистру
    - унифицирует разные типы дефисов
    - выкидывает пунктуацию/лишние пробелы
    """
    try:
        s = str(s)
    except Exception:
        return ""
    s = s.strip().lower()
    s = _DASH_RE.sub("-", s)
    s = _NONWORD_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _name_score(a: str, b: str) -> float:
    na = _norm_name(a)
    nb = _norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    r = SequenceMatcher(None, na, nb).ratio()
    ta = set(na.split())
    tb = set(nb.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    return 0.75 * r + 0.25 * jac


def _best_match(target: str, candidates: List[str]) -> Tuple[Any, float]:
    best = None
    best_s = 0.0
    for c in candidates:
        sc = _name_score(target, c)
        if sc > best_s:
            best_s = sc
            best = c
    return best, float(best_s)


def ensure_mapping_for_selection(
    mapping: Dict[str, Any],
    need_edges: List[str],
    need_nodes: List[str],
    min_score: float = 0.70,
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """Подмешивает в mapping недостающие ключи, находя "похожие" по имени.

    Задача: если mapping JSON делался под старую версию модели (или наоборот),
    но имена отличаются только деталями (пробелы/дефисы/порядок слов),
    мы пытаемся автоматически найти соответствия.

    Возвращает:
      - mapping_use (deepcopy исходного mapping с добавленными ключами)
      - report: {edges:[{need,from,score}], nodes:[...]}
    """
    mapping_use = copy.deepcopy(mapping) if isinstance(mapping, dict) else {}
    report: Dict[str, List[Dict[str, Any]]] = {"edges": [], "nodes": []}

    edges_dict = mapping_use.get("edges")
    if not isinstance(edges_dict, dict):
        edges_dict = {}
    nodes_dict = mapping_use.get("nodes")
    if not isinstance(nodes_dict, dict):
        nodes_dict = {}

    edge_keys = list(edges_dict.keys())
    node_keys = list(nodes_dict.keys())

    # edges
    for name in (need_edges or []):
        if not isinstance(name, str) or not name:
            continue
        if edges_dict.get(name):
            continue
        best, score = _best_match(name, edge_keys)
        if best is not None and score >= float(min_score) and edges_dict.get(best):
            edges_dict[name] = edges_dict.get(best)
            report["edges"].append({"need": name, "from": best, "score": score})

    # nodes
    for name in (need_nodes or []):
        if not isinstance(name, str) or not name:
            continue
        val = nodes_dict.get(name)
        if isinstance(val, list) and len(val) >= 2:
            continue
        best, score = _best_match(name, node_keys)
        if best is not None and score >= float(min_score):
            best_val = nodes_dict.get(best)
            if isinstance(best_val, list) and len(best_val) >= 2:
                nodes_dict[name] = best_val
                report["nodes"].append({"need": name, "from": best, "score": score})

    mapping_use["edges"] = edges_dict
    mapping_use["nodes"] = nodes_dict
    return mapping_use, report



def render_svg_edge_mapper_html(
    svg_inline: str,
    edge_names: List[str],
    height: int = 740,
    title: str = "Разметка веток по SVG (клик → точки → сегмент)",
):
    """HTML-инструмент для создания mapping JSON: edge_name -> polyline(points).

    Важно: это односторонний компонент (Streamlit components.html), поэтому:
    - JSON выдаётся в textarea + кнопка Download/Copy.
    - затем пользователь загружает JSON обратно в Streamlit для анимации.

    Mapping формат (version 2):
      {
        "version": 2,
        "viewBox": "0 0 1920 1080",
        "edges": {
          "edgeA": [
             [[x,y],[x,y],...],   # polyline 1
             [[x,y],...],         # polyline 2 ...
          ],
          ...
        },
        "nodes": {
          "Ресивер3": [x,y],
          ...
        }
      }

    Поле nodes можно размечать отдельным инструментом render_svg_node_mapper_html().
    """
    payload = {
        "title": title,
        "svg": svg_inline,
        "edgeNames": edge_names,
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { display:flex; gap:0; height: 100%; min-height: 640px; }
    .left { width: 360px; padding: 10px; border-right: 1px solid #e6e6e6; box-sizing:border-box; overflow:auto; }
    .right { flex: 1; position: relative; overflow:hidden; background: #fafafa; }
    h3 { margin: 0 0 6px 0; font-size: 16px; }
    .muted { color:#666; font-size: 12px; line-height: 1.35; margin-bottom: 8px; }
    label { display:block; font-size:12px; color:#444; margin-top:8px; }
    select, textarea { width:100%; box-sizing:border-box; }
    textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }
    .row { display:flex; gap:8px; margin: 8px 0; flex-wrap: wrap; }
    .btn { padding: 6px 10px; border: 1px solid #bbb; border-radius: 8px; background:#fff; cursor:pointer; font-size: 12px; }
    .btn.primary { border-color:#1f77b4; }
    .btn.danger { border-color:#c62828; }
    .btn:active { transform: translateY(1px); }

    /* SVG */
    #svgHost svg { width: 100%; height: 100%; display:block; background: white; user-select:none; }
    .edgePath { fill:none; stroke: rgba(220,0,0,0.55); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }
    .edgePath.other { stroke: rgba(0,0,0,0.10); stroke-width: 3; }
    .draft { fill:none; stroke: rgba(0,128,255,0.90); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 10 7; }
    .pt { fill: rgba(0,128,255,0.90); }
    .hud { position:absolute; left: 10px; top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.85); border: 1px solid #ddd; border-radius: 8px; font-size: 12px; }
    .hud b { font-variant-numeric: tabular-nums; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="left">
      <h3 id="title"></h3>
      <div class="muted">
        <div><b>Режим “Рисовать”</b>: клик по схеме → добавляется точка.</div>
        <div>Нажмите <b>“Завершить сегмент”</b>, чтобы сохранить polyline для выбранной ветки.</div>
        <div><b>Режим “Пан”</b>: drag мышью. Колёсико — zoom. Кнопка “Сброс вида”.</div>
        <div style="margin-top:6px;">Дальше: скачайте JSON и загрузите его в Streamlit в блоке анимации “По схеме”.</div>
      </div>

      <label>Ветка (edge)</label>
      <select id="edgeSel"></select>

      <div class="row">
        <button id="modeDraw" class="btn primary">✏️ Рисовать</button>
        <button id="modePan" class="btn">✋ Пан</button>
        <button id="resetView" class="btn">↺ Сброс вида</button>
      </div>

      <div class="row">
        <button id="undo" class="btn">↶ Undo</button>
        <button id="finish" class="btn primary">✅ Завершить сегмент</button>
        <button id="clearEdge" class="btn danger">🗑 Очистить ветку</button>
      </div>

      <div class="row">
        <button id="copy" class="btn">📋 Copy JSON</button>
        <button id="download" class="btn">⬇️ Download JSON</button>
      </div>

      <label>Mapping JSON</label>
      <textarea id="json" rows="16" spellcheck="false"></textarea>

      <div class="row">
        <button id="loadJson" class="btn">⭮ Загрузить из поля</button>
      </div>
    </div>

    <div class="right">
      <div id="svgHost">__SVG_INLINE__</div>
      <div class="hud">
        режим: <b id="mode">draw</b> ·
        edge: <b id="edgeName"></b> ·
        pts: <b id="pts">0</b>
      </div>
    </div>
  </div>

<script>
const DATA = __JS_DATA__;
document.getElementById('title').textContent = DATA.title || 'SVG mapping';
const edgeSel = document.getElementById('edgeSel');
const modeEl = document.getElementById('mode');
const edgeNameEl = document.getElementById('edgeName');
const ptsEl = document.getElementById('pts');
const jsonEl = document.getElementById('json');

const EDGE_NAMES = DATA.edgeNames || [];
EDGE_NAMES.forEach(n => {
  const opt = document.createElement('option');
  opt.value = n; opt.textContent = n;
  edgeSel.appendChild(opt);
});

// SVG
const svgHost = document.getElementById('svgHost');
svgHost.innerHTML = DATA.svg || '';
const svg = svgHost.querySelector('svg');
if (!svg) {
  svgHost.innerHTML = '<div style="padding:12px;color:#c00">SVG не найден в HTML.</div>';
}

function parseViewBox(vbStr) {
  // NOTE: двойной backslash нужен, чтобы не ловить Python SyntaxWarning
  // "invalid escape sequence '\\s'" при генерации HTML из строки.
  const a = (vbStr || '').trim().split(/\\s+/).map(parseFloat);
  if (a.length !== 4 || a.some(x => Number.isNaN(x))) return null;
  return {x:a[0], y:a[1], w:a[2], h:a[3]};
}
const vb0 = parseViewBox(svg?.getAttribute('viewBox')) || {x:0, y:0, w:1920, h:1080};
let view = {...vb0};

function setViewBox(v) {
  svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`);
}
function resetView() { view = {...vb0}; setViewBox(view); }

// overlay
const NS = "http://www.w3.org/2000/svg";
const overlay = document.createElementNS(NS, 'g');
overlay.setAttribute('id', 'pneumo_overlay');
svg.appendChild(overlay);

const segLayer = document.createElementNS(NS, 'g');
const draftLayer = document.createElementNS(NS, 'g');
overlay.appendChild(segLayer);
overlay.appendChild(draftLayer);

// mapping state
let mapping = { version: 2, viewBox: svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`, edges: {}, nodes: {} };
EDGE_NAMES.forEach(n => { mapping.edges[n] = []; });

let mode = 'draw'; // draw | pan
let selectedEdge = EDGE_NAMES[0] || '';
edgeNameEl.textContent = selectedEdge;

let curPts = [];
let dragging = false;
let dragStart = null;

function getSvgPoint(clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return {x:0,y:0};
  const sp = pt.matrixTransform(ctm.inverse());
  return {x: sp.x, y: sp.y};
}

function polyToPath(points) {
  if (!points || points.length < 2) return '';
  const p0 = points[0];
  let d = `M ${p0[0]} ${p0[1]}`;
  for (let i=1;i<points.length;i++) {
    const p = points[i];
    d += ` L ${p[0]} ${p[1]}`;
  }
  return d;
}

function rebuildSegments() {
  while (segLayer.firstChild) segLayer.removeChild(segLayer.firstChild);
  for (const [edge, segs] of Object.entries(mapping.edges)) {
    const isSel = (edge === selectedEdge);
    for (const seg of (segs || [])) {
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', polyToPath(seg));
      path.setAttribute('class', 'edgePath' + (isSel ? '' : ' other'));
      segLayer.appendChild(path);
    }
  }
}

function rebuildDraft() {
  while (draftLayer.firstChild) draftLayer.removeChild(draftLayer.firstChild);
  if (curPts.length >= 2) {
    const pts = curPts.map(p => [p.x, p.y]);
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', polyToPath(pts));
    path.setAttribute('class', 'draft');
    draftLayer.appendChild(path);
  }
  for (const p of curPts) {
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', p.x);
    c.setAttribute('cy', p.y);
    c.setAttribute('r', 6);
    c.setAttribute('class', 'pt');
    draftLayer.appendChild(c);
  }
  ptsEl.textContent = String(curPts.length);
}

function syncJson(pretty=true) {
  const s = JSON.stringify(mapping, null, pretty ? 2 : 0);
  jsonEl.value = s;
}

function setMode(m) {
  mode = m;
  modeEl.textContent = mode;
  document.getElementById('modeDraw').classList.toggle('primary', mode === 'draw');
  document.getElementById('modePan').classList.toggle('primary', mode === 'pan');
}

edgeSel.addEventListener('change', () => {
  selectedEdge = edgeSel.value;
  edgeNameEl.textContent = selectedEdge;
  curPts = [];
  rebuildDraft();
  rebuildSegments();
  syncJson(true);
});

document.getElementById('modeDraw').addEventListener('click', () => setMode('draw'));
document.getElementById('modePan').addEventListener('click', () => setMode('pan'));
document.getElementById('resetView').addEventListener('click', () => resetView());

document.getElementById('undo').addEventListener('click', () => {
  curPts.pop();
  rebuildDraft();
});

document.getElementById('finish').addEventListener('click', () => {
  if (curPts.length < 2) return;
  const seg = curPts.map(p => [Number(p.x.toFixed(2)), Number(p.y.toFixed(2))]);
  mapping.edges[selectedEdge] = mapping.edges[selectedEdge] || [];
  mapping.edges[selectedEdge].push(seg);
  curPts = [];
  rebuildDraft();
  rebuildSegments();
  syncJson(true);
});

document.getElementById('clearEdge').addEventListener('click', () => {
  mapping.edges[selectedEdge] = [];
  curPts = [];
  rebuildDraft();
  rebuildSegments();
  syncJson(true);
});

document.getElementById('copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(jsonEl.value || '');
  } catch(e) {}
});

document.getElementById('download').addEventListener('click', () => {
  const blob = new Blob([jsonEl.value || ''], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'pneumo_svg_mapping.json';
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById('loadJson').addEventListener('click', () => {
  try {
    const obj = JSON.parse(jsonEl.value || '{}');
    if (!obj || typeof obj !== 'object') return;
    if (!obj.edges) obj.edges = {};
    if (!obj.nodes) obj.nodes = {};
    // Если в JSON нет некоторых веток — добавляем пустые
    EDGE_NAMES.forEach(n => { if (!obj.edges[n]) obj.edges[n] = []; });
    mapping = obj;
    if (!mapping.viewBox) mapping.viewBox = svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`;
    rebuildSegments();
  } catch(e) {}
});


// zoom (wheel)
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = (e.deltaY < 0) ? 0.9 : 1.1;
  const p = getSvgPoint(e.clientX, e.clientY);
  const nx = p.x - (p.x - view.x) * z;
  const ny = p.y - (p.y - view.y) * z;
  view = { x: nx, y: ny, w: view.w * z, h: view.h * z };
  setViewBox(view);
}, {passive:false});

// pan (drag)
svg.addEventListener('pointerdown', (e) => {
  if (mode !== 'pan') return;
  dragging = true;
  svg.setPointerCapture(e.pointerId);
  dragStart = { p: getSvgPoint(e.clientX, e.clientY), v: {...view} };
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging || mode !== 'pan') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  const dx = p.x - dragStart.p.x;
  const dy = p.y - dragStart.p.y;
  view = { x: dragStart.v.x - dx, y: dragStart.v.y - dy, w: dragStart.v.w, h: dragStart.v.h };
  setViewBox(view);
});
svg.addEventListener('pointerup', (e) => {
  dragging = false;
  dragStart = null;
});

// draw (click)
svg.addEventListener('click', (e) => {
  if (mode !== 'draw') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  curPts.push(p);
  rebuildDraft();
});

setMode('draw');
rebuildDraft();
rebuildSegments();
syncJson(true);

</script>
</body>
</html>"""

    html = html.replace("__SVG_INLINE__", svg_inline)
    html = html.replace("__JS_DATA__", js_data)

    components.html(html, height=height, scrolling=False)


def render_svg_node_mapper_html(
    svg_inline: str,
    node_names: List[str],
    edge_names: List[str] | None = None,
    height: int = 740,
    title: str = "Разметка узлов давления по SVG (клик → позиция)",
):
    """HTML-инструмент для создания mapping JSON: node_name -> (x,y) в координатах SVG.

    Это дополняет mapping веток (edges). Идея такая:
    - Ветки размечаются в render_svg_edge_mapper_html() (polyline сегменты).
    - Узлы давления размечаются здесь: один клик = одна точка (узел).

    Формат (version 2):
      {
        "version": 2,
        "viewBox": "0 0 1920 1080",
        "edges": { ... },
        "nodes": {
           "Ресивер3": [x,y],
           ...
        }
      }

    Компонент односторонний (components.html), поэтому итоговый JSON
    нужно скачать/скопировать и загрузить обратно в блок анимации.
    """
    payload = {
        "title": title,
        "svg": svg_inline,
        "nodeNames": node_names,
        "edgeNames": (edge_names or []),
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { display:flex; gap:0; height: 100%; min-height: 640px; }
    .left { width: 360px; padding: 10px; border-right: 1px solid #e6e6e6; box-sizing:border-box; overflow:auto; }
    .right { flex: 1; position: relative; overflow:hidden; background: #fafafa; }
    h3 { margin: 0 0 6px 0; font-size: 16px; }
    .muted { color:#666; font-size: 12px; line-height: 1.35; margin-bottom: 8px; }
    label { display:block; font-size:12px; color:#444; margin-top:8px; }
    select, textarea { width:100%; box-sizing:border-box; }
    textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }
    .row { display:flex; gap:8px; margin: 8px 0; flex-wrap: wrap; }
    .btn { padding: 6px 10px; border: 1px solid #bbb; border-radius: 8px; background:#fff; cursor:pointer; font-size: 12px; }
    .btn.primary { border-color:#1f77b4; }
    .btn.danger { border-color:#c62828; }
    .btn:active { transform: translateY(1px); }

    #svgHost svg { width: 100%; height: 100%; display:block; background: white; user-select:none; }

    .nodeDot { fill: rgba(0,128,255,0.85); stroke: rgba(255,255,255,0.9); stroke-width: 3; }
    .nodeDot.missing { fill: rgba(200,200,200,0.7); }
    .nodeLabel {
      font-size: 14px;
      fill: rgba(0,0,0,0.85);
      stroke: rgba(255,255,255,0.95);
      stroke-width: 3;
      paint-order: stroke;
      font-variant-numeric: tabular-nums;
    }
    .hud { position:absolute; left: 10px; top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.85); border: 1px solid #ddd; border-radius: 8px; font-size: 12px; }
    .hud b { font-variant-numeric: tabular-nums; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="left">
      <h3 id="title"></h3>
      <div class="muted">
        <div><b>Режим “Поставить”</b>: клик по схеме → координата выбранного узла.</div>
        <div><b>Режим “Пан”</b>: drag мышью. Колёсико — zoom. Кнопка “Сброс вида”.</div>
        <div style="margin-top:6px;">Скачайте JSON и загрузите обратно в Streamlit (в блоке анимации “По схеме”).</div>
      </div>

      <label>Узел (node)</label>
      <select id="nodeSel"></select>

      <div class="row">
        <button id="modePlace" class="btn primary">📍 Поставить</button>
        <button id="modePan" class="btn">✋ Пан</button>
        <button id="resetView" class="btn">↺ Сброс вида</button>
      </div>

      <div class="row">
        <button id="clearNode" class="btn danger">🗑 Очистить узел</button>
      </div>

      <div class="row">
        <button id="copy" class="btn">📋 Copy JSON</button>
        <button id="download" class="btn">⬇️ Download JSON</button>
      </div>

      <label>Mapping JSON</label>
      <textarea id="json" rows="16" spellcheck="false"></textarea>

      <div class="row">
        <button id="loadJson" class="btn">⭮ Загрузить из поля</button>
      </div>
    </div>

    <div class="right">
      <div id="svgHost">__SVG_INLINE__</div>
      <div class="hud">
        режим: <b id="mode">place</b> ·
        node: <b id="nodeName"></b> ·
        xy: <b id="xy">—</b>
      </div>
    </div>
  </div>

<script>
const DATA = __JS_DATA__;
document.getElementById('title').textContent = DATA.title || 'SVG node mapping';
const nodeSel = document.getElementById('nodeSel');
const modeEl = document.getElementById('mode');
const nodeNameEl = document.getElementById('nodeName');
const xyEl = document.getElementById('xy');
const jsonEl = document.getElementById('json');

const NODE_NAMES = DATA.nodeNames || [];
NODE_NAMES.forEach(n => {
  const opt = document.createElement('option');
  opt.value = n; opt.textContent = n;
  nodeSel.appendChild(opt);
});

// SVG
const svgHost = document.getElementById('svgHost');
svgHost.innerHTML = DATA.svg || '';
const svg = svgHost.querySelector('svg');
if (!svg) {
  svgHost.innerHTML = '<div style="padding:12px;color:#c00">SVG не найден в HTML.</div>';
}

function parseViewBox(vbStr) {
  // NOTE: двойной backslash нужен, чтобы не ловить Python SyntaxWarning
  // "invalid escape sequence '\\s'" при генерации HTML из строки.
  const a = (vbStr || '').trim().split(/\\s+/).map(parseFloat);
  if (a.length !== 4 || a.some(x => Number.isNaN(x))) return null;
  return {x:a[0], y:a[1], w:a[2], h:a[3]};
}
const vb0 = parseViewBox(svg?.getAttribute('viewBox')) || {x:0, y:0, w:1920, h:1080};
let view = {...vb0};
function setViewBox(v) { svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`); }
function resetView() { view = {...vb0}; setViewBox(view); }

const NS = 'http://www.w3.org/2000/svg';
const overlay = document.createElementNS(NS, 'g');
overlay.setAttribute('id', 'pneumo_overlay_nodes');
svg.appendChild(overlay);

let mapping = { version: 2, viewBox: svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`, edges: {}, nodes: {} };
const EDGE_NAMES = DATA.edgeNames || [];
EDGE_NAMES.forEach(n => { if (!(n in mapping.edges)) mapping.edges[n] = []; });
// В шаблоне держим все узлы (значение null, пока не задано)
NODE_NAMES.forEach(n => { if (!(n in mapping.nodes)) mapping.nodes[n] = null; });

let mode = 'place'; // place | pan
let selectedNode = NODE_NAMES[0] || '';
nodeNameEl.textContent = selectedNode;

let dragging = false;
let dragStart = null;

function getSvgPoint(clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return {x:0,y:0};
  const sp = pt.matrixTransform(ctm.inverse());
  return {x: sp.x, y: sp.y};
}

function syncJson(pretty=true) {
  const s = JSON.stringify(mapping, null, pretty ? 2 : 0);
  jsonEl.value = s;
}

function rebuild() {
  while (overlay.firstChild) overlay.removeChild(overlay.firstChild);
  for (const [name, xy] of Object.entries(mapping.nodes || {})) {
    if (!xy || !Array.isArray(xy) || xy.length < 2) continue;
    const x = xy[0], y = xy[1];
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', x);
    c.setAttribute('cy', y);
    c.setAttribute('r', 10);
    c.setAttribute('class', 'nodeDot');
    overlay.appendChild(c);

    const t = document.createElementNS(NS, 'text');
    t.setAttribute('x', x + 12);
    t.setAttribute('y', y - 12);
    t.setAttribute('class', 'nodeLabel');
    t.textContent = name;
    overlay.appendChild(t);
  }
  // HUD
  const xy = mapping.nodes?.[selectedNode];
  if (xy && Array.isArray(xy)) xyEl.textContent = `${xy[0].toFixed(1)}, ${xy[1].toFixed(1)}`;
  else xyEl.textContent = '—';
  syncJson(true);
}

function setMode(m) {
  mode = m;
  modeEl.textContent = mode;
  document.getElementById('modePlace').classList.toggle('primary', mode === 'place');
  document.getElementById('modePan').classList.toggle('primary', mode === 'pan');
}

nodeSel.addEventListener('change', () => {
  selectedNode = nodeSel.value;
  nodeNameEl.textContent = selectedNode;
  rebuild();
});

// buttons
document.getElementById('modePlace').addEventListener('click', () => setMode('place'));
document.getElementById('modePan').addEventListener('click', () => setMode('pan'));
document.getElementById('resetView').addEventListener('click', () => resetView());

document.getElementById('clearNode').addEventListener('click', () => {
  mapping.nodes[selectedNode] = null;
  rebuild();
});

document.getElementById('copy').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(jsonEl.value || ''); } catch(e) {}
});

document.getElementById('download').addEventListener('click', () => {
  const blob = new Blob([jsonEl.value || ''], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'pneumo_svg_mapping_nodes.json';
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById('loadJson').addEventListener('click', () => {
  try {
    const obj = JSON.parse(jsonEl.value || '{}');
    if (!obj || typeof obj !== 'object') return;
    if (!obj.nodes) obj.nodes = {};
    if (!obj.edges) obj.edges = {};
    EDGE_NAMES.forEach(n => { if (!obj.edges[n]) obj.edges[n] = []; });
    NODE_NAMES.forEach(n => { if (!(n in obj.nodes)) obj.nodes[n] = null; });
    mapping = obj;
    if (!mapping.viewBox) mapping.viewBox = svg.getAttribute('viewBox') || `${vb0.x} ${vb0.y} ${vb0.w} ${vb0.h}`;
    rebuild();
  } catch(e) {}
});

// zoom
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = (e.deltaY < 0) ? 0.9 : 1.1;
  const p = getSvgPoint(e.clientX, e.clientY);
  const nx = p.x - (p.x - view.x) * z;
  const ny = p.y - (p.y - view.y) * z;
  view = { x: nx, y: ny, w: view.w * z, h: view.h * z };
  setViewBox(view);
}, {passive:false});

// pan
svg.addEventListener('pointerdown', (e) => {
  if (mode !== 'pan') return;
  dragging = true;
  svg.setPointerCapture(e.pointerId);
  dragStart = { p: getSvgPoint(e.clientX, e.clientY), v: {...view} };
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging || mode !== 'pan') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  const dx = p.x - dragStart.p.x;
  const dy = p.y - dragStart.p.y;
  view = { x: dragStart.v.x - dx, y: dragStart.v.y - dy, w: dragStart.v.w, h: dragStart.v.h };
  setViewBox(view);
});
svg.addEventListener('pointerup', (e) => {
  dragging = false;
  dragStart = null;
});

// place
svg.addEventListener('click', (e) => {
  if (mode !== 'place') return;
  const p = getSvgPoint(e.clientX, e.clientY);
  mapping.nodes[selectedNode] = [Number(p.x.toFixed(2)), Number(p.y.toFixed(2))];
  rebuild();
});

setMode('place');
resetView();
rebuild();

</script>
</body>
</html>"""

    html = html.replace("__SVG_INLINE__", svg_inline)
    html = html.replace("__JS_DATA__", js_data)
    components.html(html, height=height, scrolling=False)




def render_svg_flow_animation_html(
    svg_inline: str,
    mapping: Dict[str, Any],
    time_s: List[float],
    edge_series: List[Dict[str, Any]],
    node_series: List[Dict[str, Any]] | None = None,
    title: str = "Анимация по схеме (SVG)",
    height: int = 740,
):
    """Проигрывает потоки по “ручной” геометрии (mapping JSON) поверх SVG схемы.

    edge_series: [{name, q, open, unit}]
    node_series: [{name, p, unit}] (давление узлов, обычно в атм (изб.))
    mapping:
      version 1: {viewBox, edges}
      version 2: {viewBox, edges, nodes}

    Реализация:
    - координаты “точек” берём из mapping,
    - движение маркера по polyline делаем через SVGPathElement.getTotalLength()/getPointAtLength(),
    - пан/зум: управляем viewBox.
    """
    payload = {
        "title": title,
        "svg": svg_inline,
        "mapping": mapping,
        "time": time_s,
        "edges": edge_series,
        "nodes": (node_series or []),
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    html = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    .wrap { display:flex; flex-direction:column; height:100%; min-height: 640px; }
    .hdr { display:flex; align-items:center; gap:10px; padding: 8px 10px; border-bottom: 1px solid #e6e6e6; flex-wrap: wrap; }
    .hdr h3 { margin:0; font-size:16px; }
    .btn { padding: 4px 10px; border: 1px solid #bbb; border-radius: 8px; background:#fff; cursor:pointer; font-size: 12px; }
    .btn.primary { border-color:#1f77b4; }
    input[type=range] { width: 320px; }
    .time { font-variant-numeric: tabular-nums; font-size: 12px; color:#333; }

    .main { flex: 1; display:flex; min-height: 520px; }
    .left { flex: 1; position: relative; overflow:hidden; background:#fafafa; }
    .right { width: 360px; border-left: 1px solid #e6e6e6; padding: 10px; box-sizing:border-box; overflow:auto; }

    #svgHost svg { width:100%; height:100%; display:block; background:white; user-select:none; }

    /* flow paths */
    .edgePath { fill:none; stroke-linecap: round; stroke-linejoin: round; }
    .edgePath.pos { stroke: rgba(0,120,255,0.70); }
    .edgePath.neg { stroke: rgba(255,80,0,0.70); }
    .edgePath.closed { stroke: rgba(180,180,180,0.30); }

    .dot { }
    .dot.pos { fill: rgba(0,120,255,0.95); }
    .dot.neg { fill: rgba(255,80,0,0.95); }
    .dot.closed { fill: rgba(180,180,180,0.65); }

    /* node labels */
    .nodeDot { fill: rgba(0,0,0,0.55); stroke: rgba(255,255,255,0.90); stroke-width: 3; }
    .nodeText {
      font-size: 14px;
      fill: rgba(0,0,0,0.85);
      stroke: rgba(255,255,255,0.95);
      stroke-width: 3;
      paint-order: stroke;
      font-variant-numeric: tabular-nums;
    }

    .h4 { font-size: 12px; color:#222; margin: 10px 0 6px 0; text-transform: uppercase; letter-spacing: .04em; }

    .controls { display:flex; gap:10px; flex-wrap:wrap; padding-bottom: 8px; border-bottom: 1px solid #eee; }
    .controls label { font-size: 12px; color:#333; user-select:none; display:flex; gap:6px; align-items:center; }

    .legend { margin-top: 8px; border: 1px solid #eee; border-radius: 10px; padding: 8px; background: #fff; }
    .legendRow { display:flex; align-items:center; gap:8px; font-size: 12px; color:#333; }
    .swatch { width: 28px; height: 8px; border-radius: 999px; }
    .swatch.pos { background: rgba(0,120,255,0.80); }
    .swatch.neg { background: rgba(255,80,0,0.80); }
    .swatch.closed { background: rgba(180,180,180,0.45); }

    .row { display:flex; justify-content:space-between; gap:10px; border-bottom:1px dashed #eee; padding: 6px 0; }
    .row .name { font-size: 12px; width: 220px; word-break: break-word; }
    .row .val  { font-size: 12px; text-align:right; font-variant-numeric: tabular-nums; color:#333; }

    .hint { font-size: 11px; color:#666; line-height: 1.35; margin-top: 10px; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"hdr\">
      <h3 id=\"title\"></h3>
      <button id=\"play\" class=\"btn primary\">▶︎</button>
      <button id=\"pause\" class=\"btn\">⏸</button>
      <span class=\"time\">t=<span id=\"t\">0.000</span> s</span>
      <input id=\"slider\" type=\"range\" min=\"0\" max=\"0\" value=\"0\" step=\"1\"/>
      <span class=\"time\">idx=<span id=\"idx\">0</span></span>
      <button id=\"resetView\" class=\"btn\">↺ Сброс вида</button>
    </div>

    <div class=\"main\">
      <div class=\"left\">
        <div id=\"svgHost\">__SVG_INLINE__</div>
      </div>
      <div class=\"right\">
        <div class=\"controls\">
          <label><input id=\"togPaths\" type=\"checkbox\" checked/>Пути</label>
          <label><input id=\"togDots\" type=\"checkbox\" checked/>Маркеры</label>
          <label><input id=\"togNodes\" type=\"checkbox\" checked/>Давление</label>
          <label><input id=\"togLegend\" type=\"checkbox\" checked/>Легенда</label>
        </div>

        <div id=\"legend\" class=\"legend\">
          <div class=\"legendRow\"><span class=\"swatch pos\"></span><span>Q ≥ 0 (направление как задано веткой)</span></div>
          <div class=\"legendRow\" style=\"margin-top:6px\"><span class=\"swatch neg\"></span><span>Q &lt; 0 (реверс потока)</span></div>
          <div class=\"legendRow\" style=\"margin-top:6px\"><span class=\"swatch closed\"></span><span>closed (элемент закрыт)</span></div>
        </div>

        <div class=\"h4\">Узлы</div>
        <div id=\"nodesList\"></div>

        <div class=\"h4\">Ветки</div>
        <div id=\"edgesList\"></div>

        <div class=\"hint\">
          Пан: перетащите мышью (всегда). Zoom: колёсико мыши.<br/>
          Толщина/яркость пути ~ |Q|, цвет ~ знак Q.
        </div>
      </div>
    </div>
  </div>

<script>
const DATA = __JS_DATA__;
document.getElementById('title').textContent = DATA.title || 'SVG flow';
const slider = document.getElementById('slider');
const tEl = document.getElementById('t');
const idxEl = document.getElementById('idx');

const edges = DATA.edges || [];
const nodes = DATA.nodes || [];
const mapping = DATA.mapping || {};
const time = DATA.time || [];
const n = time.length;
slider.max = Math.max(0, n-1);

const svgHost = document.getElementById('svgHost');
svgHost.innerHTML = DATA.svg || '';
const svg = svgHost.querySelector('svg');

function parseViewBox(vbStr) {
  // NOTE: двойной backslash нужен, чтобы не ловить Python SyntaxWarning
  // "invalid escape sequence '\\s'" при генерации HTML из строки.
  const a = (vbStr || '').trim().split(/\\s+/).map(parseFloat);
  if (a.length !== 4 || a.some(x => Number.isNaN(x))) return null;
  return {x:a[0], y:a[1], w:a[2], h:a[3]};
}
const vb0 = parseViewBox(mapping.viewBox) || parseViewBox(svg?.getAttribute('viewBox')) || {x:0, y:0, w:1920, h:1080};
let view = {...vb0};
function setViewBox(v) { svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`); }
function resetView() { view = {...vb0}; setViewBox(view); }
resetView();

const NS = "http://www.w3.org/2000/svg";
const overlay = document.createElementNS(NS, 'g');
overlay.setAttribute('id','pneumo_overlay_anim');
svg.appendChild(overlay);

const pathLayer = document.createElementNS(NS, 'g');
const dotLayer  = document.createElementNS(NS, 'g');
const nodeLayer = document.createElementNS(NS, 'g');
overlay.appendChild(pathLayer);
overlay.appendChild(dotLayer);
overlay.appendChild(nodeLayer);

function getSvgPoint(clientX, clientY) {
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return {x:0,y:0};
  const sp = pt.matrixTransform(ctm.inverse());
  return {x: sp.x, y: sp.y};
}

function polyToPath(points) {
  if (!points || points.length < 2) return '';
  const p0 = points[0];
  let d = `M ${p0[0]} ${p0[1]}`;
  for (let i=1;i<points.length;i++) {
    const p = points[i];
    d += ` L ${p[0]} ${p[1]}`;
  }
  return d;
}

function clamp(x,a,b){ return Math.max(a, Math.min(b,x)); }

// --- right panel lists
const edgesListEl = document.getElementById('edgesList');
const nodesListEl = document.getElementById('nodesList');

edges.forEach((e) => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<div class="name">${e.name}</div><div class="val"><span class="q">0</span> ${e.unit||''}</div>`;
  edgesListEl.appendChild(row);
  e._row = row;
});

nodes.forEach((nd) => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<div class="name">${nd.name}</div><div class="val"><span class="p">0</span> ${nd.unit||''}</div>`;
  nodesListEl.appendChild(row);
  nd._row = row;
});

// --- build paths/dots
const segs = []; // {edgeIdx, path, dot, len, phase}
const qMax = edges.map(e => {
  let m = 1e-9;
  (e.q || []).forEach(v => { m = Math.max(m, Math.abs(v)); });
  return m;
});

edges.forEach((e, ei) => {
  const polys = (mapping.edges && mapping.edges[e.name]) ? mapping.edges[e.name] : [];
  if (!polys || polys.length === 0) return;
  polys.forEach((poly) => {
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', polyToPath(poly));
    path.setAttribute('class','edgePath pos');
    path.setAttribute('stroke-width','4');
    pathLayer.appendChild(path);

    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('r','6');
    dot.setAttribute('class','dot pos');
    dotLayer.appendChild(dot);

    const len = path.getTotalLength();
    segs.push({ edgeIdx: ei, path, dot, len, phase: Math.random() });
  });
});

// --- nodes overlay
const nodeObjs = []; // {name, circle, text, pArr, unit}
(nodes || []).forEach((nd) => {
  const xy = (mapping.nodes && mapping.nodes[nd.name]) ? mapping.nodes[nd.name] : null;
  if (!xy || !Array.isArray(xy) || xy.length < 2) return;
  const x = xy[0], y = xy[1];

  const g = document.createElementNS(NS, 'g');
  const c = document.createElementNS(NS, 'circle');
  c.setAttribute('cx', x);
  c.setAttribute('cy', y);
  c.setAttribute('r', 10);
  c.setAttribute('class', 'nodeDot');
  g.appendChild(c);

  const t = document.createElementNS(NS, 'text');
  t.setAttribute('x', x + 12);
  t.setAttribute('y', y - 12);
  t.setAttribute('class', 'nodeText');
  t.textContent = '0.00';
  g.appendChild(t);

  const tt = document.createElementNS(NS, 'title');
  tt.textContent = nd.name;
  g.appendChild(tt);

  nodeLayer.appendChild(g);

  nodeObjs.push({name: nd.name, circle: c, text: t, pArr: nd.p || [], unit: nd.unit || ''});
});

// --- toggles
const togPaths = document.getElementById('togPaths');
const togDots  = document.getElementById('togDots');
const togNodes = document.getElementById('togNodes');
const togLegend = document.getElementById('togLegend');
const legendEl = document.getElementById('legend');

function applyToggles() {
  pathLayer.style.display = togPaths.checked ? 'block' : 'none';
  dotLayer.style.display  = togDots.checked ? 'block' : 'none';
  nodeLayer.style.display = (togNodes.checked && nodeObjs.length>0) ? 'block' : 'none';
  legendEl.style.display  = togLegend.checked ? 'block' : 'none';
  nodesListEl.style.display = (togNodes.checked && nodes.length>0) ? 'block' : 'none';
}
[togPaths, togDots, togNodes, togLegend].forEach(el => el.addEventListener('change', applyToggles));
applyToggles();

// --- interactions: zoom/pan
let idx = 0;
let playing = false;
let lastTs = performance.now();
let dragging = false;
let dragStart = null;

svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = (e.deltaY < 0) ? 0.9 : 1.1;
  const p = getSvgPoint(e.clientX, e.clientY);
  const nx = p.x - (p.x - view.x) * z;
  const ny = p.y - (p.y - view.y) * z;
  view = { x: nx, y: ny, w: view.w * z, h: view.h * z };
  setViewBox(view);
}, {passive:false});

svg.addEventListener('pointerdown', (e) => {
  dragging = true;
  svg.setPointerCapture(e.pointerId);
  dragStart = { p: getSvgPoint(e.clientX, e.clientY), v: {...view} };
});
svg.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  const p = getSvgPoint(e.clientX, e.clientY);
  const dx = p.x - dragStart.p.x;
  const dy = p.y - dragStart.p.y;
  view = { x: dragStart.v.x - dx, y: dragStart.v.y - dy, w: dragStart.v.w, h: dragStart.v.h };
  setViewBox(view);
});
svg.addEventListener('pointerup', (e) => {
  dragging = false;
  dragStart = null;
});

// transport
slider.addEventListener('input', () => { idx = parseInt(slider.value||'0',10) || 0; });
document.getElementById('resetView').addEventListener('click', () => resetView());
document.getElementById('play').addEventListener('click', () => { playing = true; });
document.getElementById('pause').addEventListener('click', () => { playing = false; });

let lastRenderedIdx = -1;
let lastRenderedPlaying = null;

function renderFrame(dt) {
  idxEl.textContent = String(idx);
  tEl.textContent = (time[idx] ?? 0).toFixed(3);

  // edges numeric list
  edges.forEach((e) => {
    const qv = (e.q && e.q[idx] !== undefined) ? e.q[idx] : 0;
    const qEl = e._row?.querySelector('.q');
    if (qEl) qEl.textContent = Number(qv).toFixed(2);
  });

  // nodes numeric list
  nodes.forEach((nd) => {
    const pv = (nd.p && nd.p[idx] !== undefined) ? nd.p[idx] : 0;
    const pEl = nd._row?.querySelector('.p');
    if (pEl) pEl.textContent = Number(pv).toFixed(2);
  });

  // node overlay labels
  nodeObjs.forEach((nd) => {
    const pv = (nd.pArr && nd.pArr[idx] !== undefined) ? nd.pArr[idx] : 0;
    nd.text.textContent = Number(pv).toFixed(2);
  });

  // flow segments
  segs.forEach((s) => {
    const e = edges[s.edgeIdx];
    const qv = (e.q && e.q[idx] !== undefined) ? e.q[idx] : 0;
    const openArr = e.open || null;
    const isOpen = openArr ? !!openArr[idx] : true;

    const dir = (qv >= 0) ? 1 : -1;
    const mag = Math.abs(qv);
    const norm = clamp(mag / (qMax[s.edgeIdx] || 1e-9), 0, 1);

    // marker movement only while playing
    if (playing && dt > 0) {
      const speed = 0.15 + 1.8 * norm;
      s.phase = (s.phase + dir * speed * dt) % 1;
      if (s.phase < 0) s.phase += 1;
    }

    const pt = s.path.getPointAtLength(s.phase * s.len);
    s.dot.setAttribute('cx', pt.x);
    s.dot.setAttribute('cy', pt.y);

    // style
    const w = 2.0 + 6.0 * norm;
    s.path.setAttribute('stroke-width', w.toFixed(2));
    s.path.style.opacity = (0.15 + 0.85 * norm).toFixed(3);

    // direction classes
    if (dir >= 0) {
      s.path.classList.add('pos');
      s.path.classList.remove('neg');
      s.dot.classList.add('pos');
      s.dot.classList.remove('neg');
    } else {
      s.path.classList.add('neg');
      s.path.classList.remove('pos');
      s.dot.classList.add('neg');
      s.dot.classList.remove('pos');
    }

    if (!isOpen) {
      s.path.classList.add('closed');
      s.dot.classList.add('closed');
    } else {
      s.path.classList.remove('closed');
      s.dot.classList.remove('closed');
    }
  });

  lastRenderedIdx = idx;
  lastRenderedPlaying = playing;
}

function __frameInParentViewport(){
  try {
    const fe = window.frameElement;
    if (!fe || !fe.getBoundingClientRect) return true;
    const r = fe.getBoundingClientRect();
    const w = Number(r.width || Math.max(0, (r.right || 0) - (r.left || 0)) || 0);
    const h = Number(r.height || Math.max(0, (r.bottom || 0) - (r.top || 0)) || 0);
    if (w <= 2 || h <= 2) return false;
    if ((Number(fe.clientWidth || 0) <= 2) || (Number(fe.clientHeight || 0) <= 2)) return false;
    let hiddenByCss = false;
    try {
      const hostView = fe.ownerDocument && fe.ownerDocument.defaultView;
      const cs = (hostView && hostView.getComputedStyle) ? hostView.getComputedStyle(fe) : null;
      hiddenByCss = !!(cs && (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity || '1') === 0));
    } catch(_cssErr) {}
    if (hiddenByCss) return false;
    const hostWin = (window.top && window.top !== window) ? window.top : window;
    const vh = Number(hostWin.innerHeight || window.innerHeight || 0);
    const vw = Number(hostWin.innerWidth || window.innerWidth || 0);
    const margin = 64;
    return (r.bottom >= -margin) && (r.top <= vh + margin) && (r.right >= -margin) && (r.left <= vw + margin);
  } catch(_e) {
    return true;
  }
}
function __nextIdleMs(visibleMs, hiddenMs, offscreenMs){
  if (document && document.hidden) return hiddenMs;
  return __frameInParentViewport() ? visibleMs : offscreenMs;
}
let __STEP_HANDLE = 0;
let __STEP_KIND = '';
function __clearScheduledStep(){
  try {
    if (!__STEP_HANDLE) return;
    if (__STEP_KIND === 'raf' && window.cancelAnimationFrame) window.cancelAnimationFrame(__STEP_HANDLE);
    else clearTimeout(__STEP_HANDLE);
  } catch(_e) {}
  __STEP_HANDLE = 0;
  __STEP_KIND = '';
}
function __scheduleStep(kind, delayMs){
  __clearScheduledStep();
  if (kind === 'raf') {
    __STEP_KIND = 'raf';
    __STEP_HANDLE = requestAnimationFrame(step);
  } else {
    __STEP_KIND = 'timeout';
    __STEP_HANDLE = setTimeout(step, Math.max(0, Number(delayMs) || 0));
  }
}
function __wakeStep(){
  if (!document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
  else { __STEP_HANDLE = null; }
}

function step(ts) {
  const dt = Math.max(0, (ts - lastTs) / 1000.0);
  lastTs = ts;

  if (playing && n > 0) {
    idx = idx + Math.max(1, Math.floor(dt * 60));
    if (idx >= n) idx = 0;
    slider.value = String(idx);
  }

  const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);
  if (shouldRender) renderFrame(dt);

  if (playing && !document.hidden && __frameInParentViewport()) __scheduleStep('raf', 0);
  else {
    __STEP_HANDLE = null;
  }
}

window.addEventListener('focus', __wakeStep);
document.addEventListener('visibilitychange', () => { if (!document.hidden) __wakeStep(); });
window.addEventListener('scroll', () => { try { __wakeStep(); } catch(_e) {} }, {passive:true});
window.addEventListener('resize', () => { try { __wakeStep(); } catch(_e) {} }, {passive:true});
__wakeStep();
</script>
</body>
</html>"""

    html = html.replace("__SVG_INLINE__", svg_inline)
    html = html.replace("__JS_DATA__", js_data)

    components.html(html, height=height, scrolling=False)

def start_worker(cmd: list, cwd: Path):
    """Старт фонового неграфического процесса с тихим окном и логами.

    Важно: background workers/staged runners должны идти через ``python.exe``,
    а не через ``pythonw.exe``. Иначе на Windows ошибки и multiprocessing могут
    выглядеть как бесконечное зависание без видимого stderr/stdout.
    """
    creationflags = 0
    startupinfo = None
    run_cmd = list(cmd)
    stdout_f = None
    stderr_f = None
    try:
        if run_cmd:
            run_cmd[0] = console_python_executable(run_cmd[0]) or str(run_cmd[0])
    except Exception:
        pass
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        try:
            script_stem = Path(str(run_cmd[1] if len(run_cmd) > 1 else 'worker')).stem
        except Exception:
            script_stem = 'worker'
        try:
            cwd = Path(cwd)
            cwd.mkdir(parents=True, exist_ok=True)
            stdout_f = (cwd / "_proc.out.log").open('ab')
            stderr_f = (cwd / "_proc.err.log").open('ab')
        except Exception:
            stdout_f = None
            stderr_f = None
    try:
        proc = subprocess.Popen(
            run_cmd,
            cwd=str(cwd),
            creationflags=creationflags,
            startupinfo=startupinfo,
            stdout=stdout_f,
            stderr=stderr_f,
        )
    finally:
        # Дочерний процесс уже унаследовал дескрипторы; родителю нельзя держать
        # их открытыми, иначе Windows diagnostics ловит ResourceWarning на _proc.*.log.
        for _fh in (stdout_f, stderr_f):
            try:
                if _fh is not None:
                    _fh.close()
            except Exception:
                pass
    return proc


def pid_alive(p: subprocess.Popen | None) -> bool:
    return p is not None and (p.poll() is None)


def do_rerun():
    """Best-effort rerun helper for old/new Streamlit builds."""
    request_rerun(st)
    return


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


def pa_abs_to_atm_g(p_abs_pa: float) -> float:
    """Абсолютное давление (Па) -> атм (изб.) относительно P_ATM."""
    return (float(p_abs_pa) - P_ATM) / ATM_PA


def atm_g_to_pa_abs(p_g_atm: float) -> float:
    """атм (изб.) -> абсолютное давление (Па)."""
    return P_ATM + float(p_g_atm) * ATM_PA


def is_pressure_param(name: str) -> bool:
    """Грубая эвристика: параметры, которые храним как абсолютное давление (Па)."""
    return name.startswith("давление_") or name in {"начальное_давление_аккумулятора"}


def is_volume_param(name: str) -> bool:
    return name.startswith("объём_") or name in {"мёртвый_объём_камеры"}


def is_small_volume_param(name: str) -> bool:
    """Объёмы, которые удобнее показывать в миллилитрах (линии, мёртвые объёмы)."""
    return name in {"объём_линии", "мёртвый_объём_камеры"}


# -------------------------------
# Описания/единицы параметров (для UI)
# ВАЖНО: эти функции должны быть определены ДО того, как мы строим таблицу df_opt.
# Иначе Python упадёт с NameError, т.к. модуль выполняется сверху вниз.
# -------------------------------

PARAM_DESC: Dict[str, str] = {
    # давления (в UI — атм избыточного)
    "давление_Pmin_питание_Ресивер2": "Уставка подпитки Ресивера 2 от аккумулятора (ветка Акк → Р2). Нужно, чтобы третья ступень (Ц2/антикрен) не проседала по давлению при резком росте расхода.",
    "давление_Pmin_сброс": "Уставка «мягкого режима»: порог, при котором Ресивер 3 начинает разгружаться/ограничиваться по давлению через путь в атмосферу.",
    "давление_Pmid_сброс": "Уставка «жёсткого режима»: порог, при котором включается дополнительный путь/регулятор, повышающий жёсткость/демпфирование (адаптивность).",
    "давление_Pзаряд_аккумулятора_из_Ресивер3": "Уставка зарядки аккумулятора от Ресивера 3 (ветка Р3 → Акк). Нужна, чтобы во время движения аккумулятор восстанавливал запас и был готов к внезапному манёвру.",
    # дроссели/клапаны (в UI — доля открытия 0..1)
    "открытие_дросселя_Ц2_CAP_в_ROD": "Доля открытия дросселя в диагональной линии Ц2 при направлении потока CAP→ROD (как в схеме).",
    "открытие_дросселя_Ц2_ROD_в_CAP": "Доля открытия дросселя в диагональной линии Ц2 при направлении потока ROD→CAP (как в схеме).",
    "открытие_дросселя_выхлоп_Pmin": "Доля открытия дросселя/ограничителя на выхлопе в «мягком» режиме (рядом с Pmin‑веткой).",
    "открытие_дросселя_выхлоп_Pmid": "Доля открытия дросселя/ограничителя на выхлопе в «жёстком» режиме (рядом с Pmid‑веткой).",
    "открытие_дросселя_выхлоп_Pmax": "Доля открытия дросселя/ограничителя на аварийном выхлопе (рядом с Pmax/предохранителем).",
    # механика
    "пружина_масштаб": "Масштаб нелинейной характеристики пружины (1.0 = базовая табличная кривая).",
    "лимит_пробоя_крен_град": "Эксплуатационный лимит крена (град), по которому считается KPI «запас до пробоя». Это НЕ геометрическое опрокидывание, а требование по устойчивости/комфорту.",
    "лимит_пробоя_тангаж_град": "Эксплуатационный лимит тангажа (град), по которому считается KPI «запас до пробоя».",
}


def param_unit(name: str) -> str:
    """Единицы вывода в UI (строго в тех единицах, в которых показываем мин/макс/база)."""
    if is_pressure_param(name):
        return "атм изб."
    if is_volume_param(name):
        return "мл" if is_small_volume_param(name) else "л"
    if name.endswith("_град"):
        return "град"
    if "открытие" in name:
        return "доля 0..1"
    if name == "пружина_масштаб":
        return "коэф."
    return "—"


def param_desc(name: str) -> str:
    return PARAM_DESC.get(name, "")


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


def _si_to_ui(key: str, x_si: Any, kind: str) -> Any:
    """Преобразование значения из внутреннего СИ -> UI.

    Важно: часть параметров конфигурации хранится как *нечисловые* значения
    (строки/булевы/списки) — например режимы типа "constant".
    Для таких ключей в метаданных используется kind="raw".

    Для kind="raw" делаем безопасный passthrough:
      - если это число — показываем числом,
      - если это строка/булево/список/словарь — возвращаем как есть.

    Это предотвращает падения вида: float('constant').
    """
    if x_si is None:
        return float('nan')

    # kind='raw' — хранить как есть (могут быть строки/булевы/таблицы/режимы).
    if kind == 'raw':
        if isinstance(x_si, (str, bool, list, tuple, dict)):
            return x_si
        # numpy scalar -> python scalar
        try:
            import numpy as _np
            if isinstance(x_si, (_np.bool_,)):
                return bool(x_si)
            if isinstance(x_si, (_np.integer,)):
                return int(x_si)
            if isinstance(x_si, (_np.floating,)):
                return float(x_si)
        except Exception:
            pass
        try:
            return float(x_si)
        except Exception:
            return float('nan')

    if kind == 'pressure_atm_g':
        # x_si: Pa absolute -> atm gauge in UI
        return (float(x_si) - P_ATM) / P_ATM
    if kind == 'pressure_kPa_abs':
        return float(x_si) / 1000.0
    if kind == 'volume_L':
        return float(x_si) * 1000.0
    if kind == 'volume_mL':
        return float(x_si) * 1_000_000.0
    if kind == 'temperature_C':
        return float(x_si) - 273.15
    try:
        return float(x_si)
    except Exception:
        return float('nan')

def _ui_to_si(key: str, x_ui: float, kind: str) -> float:
    if kind == "pressure_atm_g":
        # atm gauge -> Pa absolute
        return P_ATM * (1.0 + float(x_ui))
    if kind == "pressure_kPa_abs":
        return 1000.0 * float(x_ui)
    if kind == "volume_L":
        return float(x_ui) / 1000.0
    if kind == "volume_mL":
        return float(x_ui) / 1_000_000.0
    if kind == "temperature_C":
        return float(x_ui) + 273.15
    return float(x_ui)


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

def _is_numeric_scalar(v: Any) -> bool:
    """Можно ли показывать параметр в числовой таблице."""
    if v is None:
        return False
    # bool является подклассом int -> исключаем, чтобы не превращать флаги в 0/1
    if isinstance(v, bool):
        return False
    try:
        if isinstance(v, (np.integer, np.floating)):
            return True
    except Exception:
        pass
    return isinstance(v, (int, float))

# В таблицу редактирования попадают только числовые скаляры.
scalar_keys = [k for k in all_keys if (k not in structured_keys) and _is_numeric_scalar(base0.get(k, None))]
non_numeric_keys = [k for k in all_keys if (k not in structured_keys) and (not _is_numeric_scalar(base0.get(k, None)))]

rows = []
for k in scalar_keys:
    meta = PARAM_META.get(k, {"группа": "Прочее", "ед": "СИ", "kind": "raw", "описание": ""})
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

def load_suite(path: Path) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            suite = json.load(f)
        if isinstance(suite, list):
            return suite
    except Exception:
        pass
    return []


def load_default_suite_disabled(path: Path) -> List[Dict[str, Any]]:
    rows = load_suite(path)
    out: List[Dict[str, Any]] = []
    for row in rows:
        try:
            rec = dict(row)
        except Exception:
            continue
        rec["включен"] = False
        out.append(rec)
    return out


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
                    m["штраф"] = worker_mod.candidate_penalty(m, targets)
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
                    res_rows.append({"тест": name, "ошибка": str(e), "штраф": 1e9})
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
                            _det_meta["cache_file"] = str(detail_cache_path(_cache_dir, test_pick, float(detail_dt), float(detail_t_end), int(max_points), bool(want_full)))
                            _det_disk["meta"] = _det_meta
                            st.session_state.baseline_full_cache[cache_key] = _det_disk
                            if st.session_state.get("detail_auto_pending") == cache_key:
                                st.session_state["detail_auto_pending"] = None
                            clear_detail_force_fresh(st.session_state, cache_key=str(cache_key))
                            log_event(
                                "detail_loaded_cache",
                                test=str(test_pick),
                                cache_key=str(cache_key),
                                cache_file=str(detail_cache_path(_cache_dir, test_pick, float(detail_dt), float(detail_t_end), int(max_points), bool(want_full))),
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
                                        rows.append({"показатель": label, "значение": float(pa_abs_to_atm_g(df_main[col].iloc[idx0])), "ед": "атм (изб.)"})

                                sel_corners = st.session_state.get("mech_plot_corners")
                                if not isinstance(sel_corners, list) or not sel_corners:
                                    sel_corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]

                                for cc in sel_corners:
                                    col = f"положение_штока_{cc}_м"
                                    if col in df_main.columns:
                                        rows.append({"показатель": f"шток {cc}", "значение": float(df_main[col].iloc[idx0]), "ед": "м"})

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
                                            rows.append({"показатель": f"P узел {n}", "значение": float(pa_abs_to_atm_g(df_p[n].iloc[idxp])), "ед": "атм (изб.)"})

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
                    if SHOW_TOOLS and (not SHOW_RESULTS):
                        _baseline_view_opts = ["Потоки", "Энерго‑аудит"]
                    else:
                        _baseline_view_opts = ["Графики", "Анимация"]

                    view_res = st.radio(
                        "Раздел результатов",
                        options=_baseline_view_opts,
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
                                    title="Давление (атм изб.)",
                                    yaxis_title="атм (изб.)",
                                    transform_y=lambda a: (a - P_ATM) / ATM_PA,
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
                                        title="Давление узлов (df_p, атм изб.)",
                                        yaxis_title="атм (изб.)",
                                        transform_y=lambda a: (a - P_ATM) / ATM_PA,
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
                                                "Давления (Pa → атм изб.)",
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
                                                    "Auto-units (Pa→атм, рад→град)",
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
                                                            # применяем запрос авто‑перехода к неразмеченной ветке (до создания selectbox)
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
                                                                sugg_k = st.slider("Top‑K", 3, 30, 12, step=1, key="route_label_sugg_k")
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
                                                
                                                                # Параметры авто‑подбора меток и записи
                                                                colAA1, colAA2 = st.columns(2)
                                                                with colAA1:
                                                                    auto_strategy = st.selectbox(
                                                                        "Стратегия выбора START/END (из top‑K по score)",
                                                                        options=[
                                                                            "Top2",
                                                                            "Best+Farthest",
                                                                            "FarthestPair",
                                                                        ],
                                                                        index=1,
                                                                        key="route_auto_strategy",
                                                                        help=(
                                                                            "Top2: берём 2 лучших по score. "
                                                                            "Best+Farthest: START=лучший, END=самый дальний из top‑K. "
                                                                            "FarthestPair: выбираем самую далёкую пару из top‑K."
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
                                                                    auto_k = st.slider("Top‑K", 2, 80, int(st.session_state.get("route_label_sugg_k", 12)), step=1, key="route_auto_k")
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
                                                                        "AUTO использует fuzzy‑score по текстовым меткам SVG. "
                                                                        "Лучше работает, если предварительно нажать **«Автофильтр по имени ветки»** в guided‑блоке."
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
                                                
                                                                        # авто‑переход к следующей неразмеченной ветке (через request-key)
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
                                                                    # авто‑переход к следующей неразмеченной ветке (через request-key, чтобы не трогать виджет напрямую)
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
                                                    p_g = (p_src - P_ATM) / ATM_PA
                                                    if t_target is not None and t_src is not None and len(t_src) >= 2 and len(t_target) >= 2:
                                                        if len(t_src) != len(t_target) or (abs(float(t_src[0]) - float(t_target[0])) > 1e-9) or (abs(float(t_src[-1]) - float(t_target[-1])) > 1e-9):
                                                            try:
                                                                p_g = np.interp(t_target, t_src, p_g)
                                                            except Exception:
                                                                p_g = p_g[: len(t_target)]
                                                    else:
                                                        p_g = p_g[: len(time_s)]

                                                    node_series.append({"name": nn, "p": p_g.tolist(), "unit": "атм (изб.)"})

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
            st.write(f"Строк: {len(df_all)}")
            if len(df_all) != len(df_all_raw):
                st.caption(f"Скрыто служебных baseline/service rows: {int(len(df_all_raw) - len(df_all))}")

            st.markdown("### Быстрый TOP по суммарному штрафу")
            if "штраф_физичности_сумма" in df_all.columns:
                df_top = df_all.sort_values(["штраф_физичности_сумма"], ascending=True).head(30)
                safe_dataframe(df_top, height=260)

            st.markdown("### Pareto: выбор осей (без жёстких отсечек по умолчанию)")

            # Рабочая копия
            df_all2 = df_all.copy()

            # (опционально) фильтр по штрафу — НЕ включён по умолчанию
            use_pen_filter = st.checkbox("Фильтровать по штрафу физичности", value=False, key="pareto_pen_filter")
            if use_pen_filter and "штраф_физичности_сумма" in df_all2.columns:
                pen_max_default = float(np.nanmax(df_all2["штраф_физичности_сумма"].astype(float).values))
                pen_max = st.number_input("Макс штраф физичности (<=)", min_value=0.0, value=pen_max_default, step=0.5, key="pareto_pen_max")
                df_all2 = df_all2[df_all2["штраф_физичности_сумма"].astype(float) <= float(pen_max)]

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
