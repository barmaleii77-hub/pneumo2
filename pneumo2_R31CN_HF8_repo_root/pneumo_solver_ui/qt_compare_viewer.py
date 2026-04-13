# -*- coding: utf-8 -*-
"""qt_compare_viewer.py

Desktop (Windows) viewer для сравнения нескольких прогонов по NPZ.

Зачем нужен, если уже есть Streamlit:
  - когда хочется «как в осциллографе»: быстрый скролл/зум, shared crosshair,
    dock‑панели, горячие клавиши.
  - когда браузер/Streamlit тяжеловато тянет большие traces.

Запуск:
  - рекомендовано: из Streamlit страницы **Compare Viewer (Qt)** (кнопка «Открыть окно»).
  - standalone (если зависимости уже установлены):
      python pneumo_solver_ui/qt_compare_viewer.py

Формат данных:
  - *.npz (Txx_osc.npz), как пишет UI.

Ограничения (осознанно):
  - это lightweight‑viewer (не пытается повторять весь UI).
  - акцент на сравнение time‑series.
"""

from __future__ import annotations

import argparse
import ast
import html
import os
import re
import sys
import warnings


# --- robust import paths (works even if ZIP extracted into nested folder) ---
def _ensure_import_paths() -> None:
    try:
        from pathlib import Path
        this = Path(__file__).resolve()
        ui_dir = this.parent
        repo_root = ui_dir.parent
        if str(ui_dir) not in sys.path:
            sys.path.insert(0, str(ui_dir))
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
    except Exception:
        pass

_ensure_import_paths()
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import json

import numpy as np
import pandas as pd

# Plotly (for Multivariate Explorer inside Qt via QtWebEngine)
try:
    import plotly.express as px  # type: ignore
    import plotly.graph_objects as go  # type: ignore
except Exception:
    px = None  # type: ignore
    go = None  # type: ignore

# Plotly-in-Qt bridge (optional: requires QtWebEngine / PySide6-Addons)
try:
    try:
        from qt_plotly_view import PlotlyWebView, PlotlyHtmlSpec, HAVE_QTWEBENGINE  # type: ignore
    except Exception:
        from pneumo_solver_ui.qt_plotly_view import PlotlyWebView, PlotlyHtmlSpec, HAVE_QTWEBENGINE  # type: ignore
except Exception:
    PlotlyWebView = None  # type: ignore
    PlotlyHtmlSpec = None  # type: ignore
    HAVE_QTWEBENGINE = False

# Reuse NPZ loader from compare_ui (it is safe even if Plotly is not installed).
try:
    try:
        from compare_ui import load_npz_bundle, detect_time_col, extract_time_vector, _infer_unit_and_transform  # type: ignore
    except Exception:
        from pneumo_solver_ui.compare_ui import (  # type: ignore
            load_npz_bundle,
            detect_time_col,
            extract_time_vector,
            _infer_unit_and_transform,
        )
except Exception as e:
    raise SystemExit(f"Cannot import compare_ui helpers: {e}")


try:
    try:
        from npz_anim_diagnostics import format_anim_diagnostics_lines  # type: ignore
    except Exception:
        from pneumo_solver_ui.npz_anim_diagnostics import format_anim_diagnostics_lines  # type: ignore
except Exception:
    def format_anim_diagnostics_lines(diag, *, label=""):
        return []


try:
    try:
        from desktop_animator.pointer_paths import iter_session_workspaces, workspace_autoload_pointer_candidates  # type: ignore
    except Exception:
        from pneumo_solver_ui.desktop_animator.pointer_paths import (  # type: ignore
            iter_session_workspaces,
            workspace_autoload_pointer_candidates,
        )
except Exception:
    def iter_session_workspaces(project_root, limit=None):
        return []

    def workspace_autoload_pointer_candidates(workspace_dir):
        return []


try:
    try:
        from geometry_acceptance_contract import build_geometry_acceptance_rows, format_geometry_acceptance_summary_lines  # type: ignore
    except Exception:
        from pneumo_solver_ui.geometry_acceptance_contract import build_geometry_acceptance_rows, format_geometry_acceptance_summary_lines  # type: ignore
except Exception:
    def build_geometry_acceptance_rows(summary):  # type: ignore
        return []

    def format_geometry_acceptance_summary_lines(summary, *, label=""):
        return []


# Diagrammy: shared trust banner + Δ(t) cube (used by both Web and Qt)
try:
    try:
        from compare_trust import inspect_runs as trust_inspect_runs, format_banner_text  # type: ignore
        from compare_deltat_heatmap import build_deltat_cube  # type: ignore
        from compare_influence_time import build_influence_t_cube  # type: ignore
    except Exception:
        from pneumo_solver_ui.compare_trust import inspect_runs as trust_inspect_runs, format_banner_text  # type: ignore
        from pneumo_solver_ui.compare_deltat_heatmap import build_deltat_cube  # type: ignore
        from pneumo_solver_ui.compare_influence_time import build_influence_t_cube  # type: ignore
except Exception:
    trust_inspect_runs = None  # type: ignore
    format_banner_text = None  # type: ignore
    build_deltat_cube = None  # type: ignore
    build_influence_t_cube = None  # type: ignore

# Diagrammy: QA suspicious signals helpers
try:
    try:
        from diag.qa_suspicious_signals import (
            scan_run_tables as qa_scan_run_tables,  # type: ignore
            issues_to_frame as qa_issues_to_frame,  # type: ignore
            severity_matrix as qa_severity_matrix,  # type: ignore
            summarize as qa_summarize,  # type: ignore
        )
    except Exception:
        from pneumo_solver_ui.diag.qa_suspicious_signals import (
            scan_run_tables as qa_scan_run_tables,  # type: ignore
            issues_to_frame as qa_issues_to_frame,  # type: ignore
            severity_matrix as qa_severity_matrix,  # type: ignore
            summarize as qa_summarize,  # type: ignore
        )
except Exception:
    qa_scan_run_tables = None  # type: ignore
    qa_issues_to_frame = None  # type: ignore
    qa_severity_matrix = None  # type: ignore
    qa_summarize = None  # type: ignore

# Diagrammy: discrete event markers ("галька")
try:
    try:
        from diag.event_markers import (
            scan_run_tables as ev_scan_run_tables,  # type: ignore
            events_to_frame as ev_events_to_frame,  # type: ignore
            summarize as ev_summarize,  # type: ignore
            pick_top_signals as ev_pick_top_signals,  # type: ignore
        )
    except Exception:
        from pneumo_solver_ui.diag.event_markers import (
            scan_run_tables as ev_scan_run_tables,  # type: ignore
            events_to_frame as ev_events_to_frame,  # type: ignore
            summarize as ev_summarize,  # type: ignore
            pick_top_signals as ev_pick_top_signals,  # type: ignore
        )
except Exception:
    ev_scan_run_tables = None  # type: ignore
    ev_events_to_frame = None  # type: ignore
    ev_summarize = None  # type: ignore
    ev_pick_top_signals = None  # type: ignore

# Diagrammy: influence helpers (meta → signals)
try:
    try:
        from compare_influence import (
            flatten_meta_numeric as infl_flatten_meta_numeric,  # type: ignore
            corr_matrix as infl_corr_matrix,  # type: ignore
            prefilter_features_by_variance as infl_prefilter_features_by_variance,  # type: ignore
            rank_features_by_max_abs_corr as infl_rank_features_by_max_abs_corr,  # type: ignore
        )
    except Exception:
        from pneumo_solver_ui.compare_influence import (
            flatten_meta_numeric as infl_flatten_meta_numeric,  # type: ignore
            corr_matrix as infl_corr_matrix,  # type: ignore
            prefilter_features_by_variance as infl_prefilter_features_by_variance,  # type: ignore
            rank_features_by_max_abs_corr as infl_rank_features_by_max_abs_corr,  # type: ignore
        )
except Exception:
    infl_flatten_meta_numeric = None  # type: ignore
    infl_corr_matrix = None  # type: ignore
    infl_prefilter_features_by_variance = None  # type: ignore
    infl_rank_features_by_max_abs_corr = None  # type: ignore



def _soft_import_qt():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
        return QtCore, QtGui, QtWidgets
    except Exception as e:
        raise SystemExit(
            "PySide6 не установлен. Установите зависимости через лаунчер (кнопка «Установить зависимости») или через UI (страница «Setup/Диагностика»).\n\n"
            f"Import error: {e}"
        )


def _soft_import_pg():
    try:
        import pyqtgraph as pg  # type: ignore
        return pg
    except Exception as e:
        raise SystemExit(
            "pyqtgraph не установлен. Установите зависимости через лаунчер (кнопка «Установить зависимости») или через UI (страница «Setup/Диагностика»).\n\n"
            f"Import error: {e}"
        )


QtCore, QtGui, QtWidgets = _soft_import_qt()
pg = _soft_import_pg()


def _parse_qsettings_str_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [str(x) for x in v if x is not None]
    s = str(v).strip()
    if not s:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            obj = parser(s)
        except Exception:
            continue
        if obj is None:
            return []
        if isinstance(obj, (list, tuple, set)):
            return [str(x) for x in obj if x is not None]
        if isinstance(obj, str):
            return [obj]
    return [s]


def _absolute_fs_path(path) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except Exception:
        try:
            return Path(path).expanduser().absolute()
        except Exception:
            return Path(str(path))


def _normalized_fs_path_key(path) -> str:
    p = _absolute_fs_path(path)
    try:
        return os.path.normcase(os.path.normpath(str(p)))
    except Exception:
        return str(p)

pg.setConfigOptions(antialias=False)


@dataclass
class Run:
    label: str
    path: Path
    tables: Dict[str, pd.DataFrame]
    meta: Dict
    visual_contract: Dict
    anim_diagnostics: Dict
    geometry_acceptance: Dict
    events: Optional[pd.DataFrame] = None


class VerticalLinesOverlay(pg.PlotDataItem):
    """Efficient multi-vertical-lines overlay for pyqtgraph.

    Использует connect='pairs': каждая пара точек — отдельный сегмент.
    По сигналу изменения диапазона Y автоматически подстраивает длину линий.
    """

    def __init__(self, plot_item: 'pg.PlotItem', xs: Optional[Sequence[float]] = None, pen=None):
        self._plot_item = plot_item
        self._xs = np.asarray(xs or [], dtype=float)
        if pen is None:
            pen = pg.mkPen((255, 140, 0, 90), width=1, style=QtCore.Qt.DashLine)
        super().__init__([], [], pen=pen, connect='pairs')
        try:
            self.setZValue(5)  # above curves a bit, below playhead
        except Exception:
            pass
        try:
            vb = self._plot_item.getViewBox()
            vb.sigRangeChanged.connect(self._on_range_changed)
        except Exception:
            vb = None
        self._on_range_changed()

    def set_xs(self, xs: Sequence[float]):
        self._xs = np.asarray(list(xs or []), dtype=float)
        self._on_range_changed()

    def _on_range_changed(self, *args, **kwargs):
        try:
            if self._xs.size == 0:
                self.setData([], [])
                return
            vb = self._plot_item.getViewBox()
            (y0, y1) = vb.viewRange()[1]
            xs = np.repeat(self._xs, 2)
            ys = np.tile([y0, y1], int(self._xs.size))
            self.setData(xs, ys)
        except Exception:
            # best-effort: do not crash UI
            try:
                self.setData([], [])
            except Exception:
                pass


def _default_label(path: Path, meta: Dict) -> str:
    tn = meta.get("test_name") or meta.get("имя_теста")
    mode = meta.get("mode")
    if tn and mode:
        return f"{tn} · {mode}"
    if tn:
        return str(tn)
    return path.stem


def _trim_label(s: str, n: int = 26) -> str:
    """Short label for axes/legends (prevents overlaps).

    Правило UI проекта: подписи не должны накладываться.
    Для Plotly (SPLOM/Parallel/3D) проще всего держать оси короткими,
    а полный текст показывать в tooltip/таблице соответствий.
    """

    s = str(s or "")
    s2 = s.replace("\t", " ").replace("_", " ").strip()
    if len(s2) <= int(n):
        return s2
    return s2[: max(0, int(n) - 1)].rstrip() + "…"


def _shorten_unique(names: Sequence[str], *, max_len: int = 26) -> Dict[str, str]:
    """Map full_name -> unique short label (<= max_len)."""

    used = set()
    out: Dict[str, str] = {}
    for full in list(names or []):
        base = _trim_label(str(full), n=max_len)
        short = base
        k = 2
        while short in used:
            # keep unique with small suffix
            suffix = f"#{k}"
            short = _trim_label(base, n=max(8, max_len - len(suffix) - 1)) + " " + suffix
            k += 1
            if k > 99:
                break
        used.add(short)
        out[str(full)] = short
    return out


def _sample_nearest(x: np.ndarray, y: np.ndarray, t: float) -> float:
    """Nearest neighbor sampling (stable for discrete 0/1 signals)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0 or y.size == 0 or (not np.isfinite(float(t))):
        return float("nan")
    try:
        if np.any(np.diff(x) <= 0):
            idx = np.argsort(x)
            x = x[idx]
            y = y[idx]
    except Exception:
        pass
    j = int(np.searchsorted(x, float(t)))
    j = max(1, min(j, int(x.size) - 1))
    j0, j1 = j - 1, j
    return float(y[j0] if abs(x[j0] - t) <= abs(x[j1] - t) else y[j1])


def _knn_density(points01: np.ndarray, k: int = 5) -> np.ndarray:
    """Cheap O(N^2) kNN density proxy (for interactive thinning).

    points01: Nx3 already normalized to [0..1].
    Returns higher values for denser regions.
    """

    pts = np.asarray(points01, dtype=float)
    n = int(pts.shape[0])
    if n <= 2:
        return np.ones(n, dtype=float)
    d2 = np.sum((pts[:, None, :] - pts[None, :, :]) ** 2, axis=2)
    kk = max(1, min(int(k) + 1, n - 1))
    dk2 = np.partition(d2, kk, axis=1)[:, kk]
    dk = np.sqrt(np.maximum(dk2, 1e-12))
    return 1.0 / (dk + 1e-9)


class CompareViewer(QtWidgets.QMainWindow):
    def __init__(self, paths: List[Path]):
        super().__init__()
        self.setObjectName("compareViewerWindow")
        self._window_title_base = "Pneumo: NPZ Compare Viewer (DiagrammyV680R05)"
        self.setWindowTitle(self._window_title_base)
        self.setMinimumSize(1220, 820)
        try:
            self.setDockOptions(
                QtWidgets.QMainWindow.AllowTabbedDocks
                | QtWidgets.QMainWindow.AllowNestedDocks
                | QtWidgets.QMainWindow.AnimatedDocks
            )
            self.setTabPosition(QtCore.Qt.AllDockWidgetAreas, QtWidgets.QTabWidget.North)
        except Exception:
            pass

        # Display/units defaults (ANR):
        # - 1 bar = 100000 Pa (BAR_PA)
        # - P_ATM is used for gauge pressure (Pa - P_ATM)
        self.P_ATM = 100000.0  # Pa
        self.BAR_PA = 100000.0  # Pa per bar
        self.ATM_PA = self.BAR_PA  # backward-compat alias

        # Compare/plot options
        self.dist_unit = "mm"
        self.angle_unit = "deg"
        self.flow_unit = "raw"
        self.p_atm = float(self.P_ATM)
        self.zero_baseline = True
        self.baseline_mode = "t0"
        self.baseline_window_s = 0.0
        self.baseline_first_n = 0
        self.lock_y = True
        self.lock_y_by_unit = False
        self.robust_y = True
        self.sym_y = True
        self.heat_enabled = True
        self.heat_metric = "signed Δ"
        self.heat_max_sigs = 12
        self.heat_max_time_points = 2500

        self.runs: List[Run] = []
        self.table_names: List[str] = []
        self.current_table: str = "main"
        self.table_selected: str = "main"
        self.reference_run_selected: str = ""
        self.reference_run_selected_path: str = ""
        self.runs_selected_paths: List[str] = []
        self._runs_selection_explicit: bool = False
        self.available_signals: List[str] = []
        self.signals_selected: List[str] = []
        self._signals_selection_explicit: bool = False
        self.dist_signal_selected: str = ""
        self.navigator_signal_selected: str = ""
        self.events_selected: List[str] = []
        self._events_selection_explicit: bool = False
        self._last_load_errors: List[str] = []

        # plots
        self.glw = pg.GraphicsLayoutWidget()
        self.setCentralWidget(self.glw)
        self.plots: List[pg.PlotItem] = []
        self.vlines: List[pg.InfiniteLine] = []
        self.plot_signals: List[str] = []
        self._navigator_plot: Optional[pg.PlotItem] = None
        self._navigator_region: Optional[pg.LinearRegionItem] = None
        self.navigator_region_selected: Optional[Tuple[float, float]] = None
        self._syncing_region: bool = False
        self._region = None
        self._updating_region = False

        # playhead / animation
        self._t_ref = np.asarray([], dtype=float)
        self.playhead_time_selected: Optional[float] = None
        self.playhead_index_selected: Optional[int] = None
        self._time_slider_updating = False
        self._is_playing = False
        self._play_timer = QtCore.QTimer(self)
        self._play_timer.timeout.connect(self._on_play_tick)
        self._runs_selection_connected = False

        # Multivariate explorer state (Plotly in Qt)
        self._mv_df_full: Optional[pd.DataFrame] = None
        self._mv_df_plot: Optional[pd.DataFrame] = None
        self._mv_map_full_to_short: Dict[str, str] = {}
        self._mv_map_short_to_full: Dict[str, str] = {}
        self._mv_last_key: str = ""
        self._mv_checked_dims_selected: Optional[List[str]] = None
        self._mv_color_selected: str = ""
        self._mv_color3d_selected: str = ""
        self._mv_x_selected: str = ""
        self._mv_y_selected: str = ""
        self._mv_z_selected: str = ""
        self._mv_peb_sig_selected: str = ""
        self._mv_updating: bool = False
        self._mv_restoring_settings: bool = False
        self._workspace_focus_mode: str = "all"
        self._workspace_focus_dock_attr: str = ""
        self._workspace_app_focus_connected: bool = False
        self._workspace_analysis_mode: str = "all_to_all"
        self._insight_heat: Dict[str, object] = {}
        self._insight_peak_heat: Dict[str, object] = {}
        self._insight_infl: Dict[str, object] = {}
        self._insight_qa: Dict[str, object] = {}
        self._insight_events: Dict[str, object] = {}
        self._events_timeline_cache: Optional[Dict[str, object]] = None
        self._events_runs_cache: Optional[Dict[str, object]] = None
        self._peak_cache: Optional[Dict[str, object]] = None
        self._open_timeline_cache: Optional[Dict[str, object]] = None
        self._static_stroke_cache: Optional[Dict[str, object]] = None
        self._geometry_acceptance_cache: Optional[Dict[str, object]] = None
        self._dist_cache: Optional[Dict[str, object]] = None
        self._mv_timer = QtCore.QTimer(self)
        self._mv_timer.setSingleShot(True)
        self._mv_timer.timeout.connect(self._update_multivar_views)
        self._dist_timer = QtCore.QTimer(self)
        self._dist_timer.setSingleShot(True)
        self._dist_timer.timeout.connect(self._rebuild_run_metrics)
        self._peak_timer = QtCore.QTimer(self)
        self._peak_timer.setSingleShot(True)
        self._peak_timer.timeout.connect(self._rebuild_peak_heatmap)
        self._open_timeline_timer = QtCore.QTimer(self)
        self._open_timeline_timer.setSingleShot(True)
        self._open_timeline_timer.timeout.connect(self._rebuild_open_timeline_view)
        self._static_timer = QtCore.QTimer(self)
        self._static_timer.setSingleShot(True)
        self._static_timer.timeout.connect(self._rebuild_static_stroke_view)
        self._geometry_timer = QtCore.QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self._rebuild_geometry_acceptance_view)

        self._build_dock()
        self._build_menu()
        self._build_status_bar()
        self._apply_workspace_theme()

        # Persistent UI state (desktop): keep user selections across restarts
        self._settings = QtCore.QSettings('UnifiedPneumoApp', 'DiagrammyCompareViewer')
        self._restore_after_load = {}
        self._load_settings()
        self._build_heatmap_dock()
        self._build_peak_heatmap_dock()
        self._build_open_timeline_dock()
        self._build_influence_dock()
        self._build_run_metrics_dock()
        self._build_static_stroke_dock()
        self._build_infl_heatmap_dock()
        self._build_multivar_dock()
        self._build_qa_dock()
        self._build_events_dock()
        self._build_geometry_acceptance_dock()
        self._build_view_menu()
        self._apply_default_workspace_layout()

        # debounce timer for Influence(t) recompute
        self._infl_timer = QtCore.QTimer(self)
        self._infl_timer.setSingleShot(True)
        self._infl_timer.timeout.connect(self._rebuild_influence)

        self._inflheat_timer = QtCore.QTimer(self)
        self._inflheat_timer.setSingleShot(True)
        self._inflheat_timer.timeout.connect(self._rebuild_infl_heatmap)

        self._inflheat = None
        self._inflheat_sig_labels = []
        self._inflheat_feat_labels = []

        self._load_paths(paths)
        self._clear_pending_dataset_restore_if_mismatch([getattr(r, 'path', Path('')) for r in getattr(self, 'runs', [])])
        self._apply_restore_after_load()
        self._update_workspace_status()

        # crosshair
        self.proxy = pg.SignalProxy(self.glw.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)
        try:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.focusChanged.connect(self._on_app_focus_changed)
                self._workspace_app_focus_connected = True
        except Exception:
            self._workspace_app_focus_connected = False

    # ---------------- UI ----------------
    def _build_dock(self):
        dock = QtWidgets.QDockWidget("Controls", self)
        dock.setObjectName("dock_controls")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # trust banner (yellow/red)
        self.lbl_trust = QtWidgets.QLabel("")
        self.lbl_trust.setWordWrap(True)
        self.lbl_trust.setVisible(False)
        self.lbl_trust.setToolTip("Почему данным нельзя доверять (dt/NaN/не‑монотонность)")
        self.lbl_trust.setStyleSheet("QLabel{padding:6px;border-radius:6px;}")
        lay.addWidget(self.lbl_trust)

        gb_assistant = QtWidgets.QGroupBox("Workspace assistant")
        ga = QtWidgets.QVBoxLayout(gb_assistant)
        ga.setContentsMargins(8, 8, 8, 8)
        ga.setSpacing(6)

        self.lbl_workspace_assistant_title = QtWidgets.QLabel("Load compare bundle")
        self.lbl_workspace_assistant_title.setObjectName("workspaceAssistantTitle")
        self.lbl_workspace_assistant_title.setWordWrap(True)
        ga.addWidget(self.lbl_workspace_assistant_title)

        self.lbl_workspace_assistant = QtWidgets.QLabel(
            "Open 2+ NPZ runs. Then pick a shared table and a few signals to unlock Heatmaps, QA and Multivariate views."
        )
        self.lbl_workspace_assistant.setObjectName("workspaceAssistantBody")
        self.lbl_workspace_assistant.setWordWrap(True)
        ga.addWidget(self.lbl_workspace_assistant)

        row_focus = QtWidgets.QHBoxLayout()
        row_focus.setSpacing(6)
        self._workspace_focus_buttons = QtWidgets.QButtonGroup(self)
        self._workspace_focus_buttons.setExclusive(True)

        self.btn_workspace_focus_all = QtWidgets.QPushButton("Overview")
        self.btn_workspace_focus_all.setObjectName("workspaceFocusAllButton")
        self.btn_workspace_focus_all.setToolTip("Show the full workspace with all docks.")
        self.btn_workspace_focus_all.setCheckable(True)
        self.btn_workspace_focus_all.setChecked(True)
        self.btn_workspace_focus_all.clicked.connect(lambda _=False: self._activate_workspace_focus_mode("all"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_all)
        row_focus.addWidget(self.btn_workspace_focus_all)

        self.btn_workspace_focus_heatmaps = QtWidgets.QPushButton("Heatmaps")
        self.btn_workspace_focus_heatmaps.setObjectName("workspaceFocusHeatmapsButton")
        self.btn_workspace_focus_heatmaps.setToolTip("Focus Delta and Influence heatmaps.")
        self.btn_workspace_focus_heatmaps.setCheckable(True)
        self.btn_workspace_focus_heatmaps.clicked.connect(lambda _=False: self._activate_workspace_focus_mode("heatmaps"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_heatmaps)
        row_focus.addWidget(self.btn_workspace_focus_heatmaps)

        self.btn_workspace_focus_multivar = QtWidgets.QPushButton("Multivar")
        self.btn_workspace_focus_multivar.setObjectName("workspaceFocusMultivarButton")
        self.btn_workspace_focus_multivar.setToolTip("Focus SPLOM, Parallel and 3D melting-cloud / pebbles views.")
        self.btn_workspace_focus_multivar.setCheckable(True)
        self.btn_workspace_focus_multivar.clicked.connect(lambda _=False: self._activate_workspace_focus_mode("multivariate"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_multivar)
        row_focus.addWidget(self.btn_workspace_focus_multivar)

        self.btn_workspace_focus_qa = QtWidgets.QPushButton("QA / Events")
        self.btn_workspace_focus_qa.setObjectName("workspaceFocusQaButton")
        self.btn_workspace_focus_qa.setToolTip("Focus QA and event drill-down tools.")
        self.btn_workspace_focus_qa.setCheckable(True)
        self.btn_workspace_focus_qa.clicked.connect(lambda _=False: self._activate_workspace_focus_mode("qa"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_qa)
        row_focus.addWidget(self.btn_workspace_focus_qa)

        ga.addLayout(row_focus)

        self.btn_workspace_follow_hint = QtWidgets.QPushButton("Follow weakest link")
        self.btn_workspace_follow_hint.setObjectName("workspaceFollowHintButton")
        self.btn_workspace_follow_hint.setToolTip("Jump to the dock preset that best repairs the current weakest link.")
        self.btn_workspace_follow_hint.clicked.connect(self._follow_workspace_heuristic_focus)
        ga.addWidget(self.btn_workspace_follow_hint)

        row_analysis = QtWidgets.QHBoxLayout()
        row_analysis.setSpacing(6)
        self._workspace_analysis_buttons = QtWidgets.QButtonGroup(self)
        self._workspace_analysis_buttons.setExclusive(True)

        self.btn_workspace_analysis_one_to_all = QtWidgets.QPushButton("1 -> all")
        self.btn_workspace_analysis_one_to_all.setObjectName("workspaceAnalysisOneToAllButton")
        self.btn_workspace_analysis_one_to_all.setToolTip("Trace one driver or hotspot across many responses.")
        self.btn_workspace_analysis_one_to_all.setCheckable(True)
        self.btn_workspace_analysis_one_to_all.clicked.connect(
            lambda _=False: self._set_workspace_analysis_mode("one_to_all")
        )
        self._workspace_analysis_buttons.addButton(self.btn_workspace_analysis_one_to_all)
        row_analysis.addWidget(self.btn_workspace_analysis_one_to_all)

        self.btn_workspace_analysis_all_to_one = QtWidgets.QPushButton("all -> 1")
        self.btn_workspace_analysis_all_to_one.setObjectName("workspaceAnalysisAllToOneButton")
        self.btn_workspace_analysis_all_to_one.setToolTip("Explain one target waveform through many candidate drivers.")
        self.btn_workspace_analysis_all_to_one.setCheckable(True)
        self.btn_workspace_analysis_all_to_one.clicked.connect(
            lambda _=False: self._set_workspace_analysis_mode("all_to_one")
        )
        self._workspace_analysis_buttons.addButton(self.btn_workspace_analysis_all_to_one)
        row_analysis.addWidget(self.btn_workspace_analysis_all_to_one)

        self.btn_workspace_analysis_all_to_all = QtWidgets.QPushButton("all -> all")
        self.btn_workspace_analysis_all_to_all.setObjectName("workspaceAnalysisAllToAllButton")
        self.btn_workspace_analysis_all_to_all.setToolTip(
            "Scout clusters, melting clouds and pebbles across the full multivariate field."
        )
        self.btn_workspace_analysis_all_to_all.setCheckable(True)
        self.btn_workspace_analysis_all_to_all.setChecked(True)
        self.btn_workspace_analysis_all_to_all.clicked.connect(
            lambda _=False: self._set_workspace_analysis_mode("all_to_all")
        )
        self._workspace_analysis_buttons.addButton(self.btn_workspace_analysis_all_to_all)
        row_analysis.addWidget(self.btn_workspace_analysis_all_to_all)

        ga.addLayout(row_analysis)
        lay.addWidget(gb_assistant)

        gb_insights = QtWidgets.QGroupBox("Heuristic insights")
        gi = QtWidgets.QVBoxLayout(gb_insights)
        gi.setContentsMargins(8, 8, 8, 8)
        gi.setSpacing(6)

        self.txt_workspace_insights = QtWidgets.QTextBrowser()
        self.txt_workspace_insights.setObjectName("workspaceInsightsBrowser")
        self.txt_workspace_insights.setReadOnly(True)
        self.txt_workspace_insights.setOpenExternalLinks(False)
        self.txt_workspace_insights.setOpenLinks(False)
        self.txt_workspace_insights.setUndoRedoEnabled(False)
        self.txt_workspace_insights.setMinimumHeight(210)
        self.txt_workspace_insights.setMaximumHeight(280)
        self.txt_workspace_insights.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        gi.addWidget(self.txt_workspace_insights)
        lay.addWidget(gb_insights)

        gb_diag = QtWidgets.QGroupBox("Selected run diagnostics")
        gd = QtWidgets.QVBoxLayout(gb_diag)
        gd.setContentsMargins(6, 6, 6, 6)
        self.txt_anim_diag = QtWidgets.QPlainTextEdit()
        self.txt_anim_diag.setReadOnly(True)
        self.txt_anim_diag.setPlaceholderText("Выберите прогон, чтобы увидеть current/pointer visual tokens и sync-статус.")
        self.txt_anim_diag.setMinimumHeight(160)
        gd.addWidget(self.txt_anim_diag)
        lay.addWidget(gb_diag)

        # runs
        lay.addWidget(QtWidgets.QLabel("Runs"))
        self.list_runs = QtWidgets.QListWidget()
        self.list_runs.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.list_runs, stretch=1)

        # table
        self.combo_table = QtWidgets.QComboBox()
        self.combo_table.currentIndexChanged.connect(self._on_table_changed)
        lay.addWidget(QtWidgets.QLabel("Table"))
        lay.addWidget(self.combo_table)

        # signal filter
        lay.addWidget(QtWidgets.QLabel("Signal filter (substring or regex)"))
        self.edit_filter = QtWidgets.QLineEdit()
        self.edit_filter.setPlaceholderText("e.g. давление|штока")
        self.edit_filter.textChanged.connect(self._on_signal_filter_changed)
        lay.addWidget(self.edit_filter)

        # signals
        lay.addWidget(QtWidgets.QLabel("Signals (select multiple)"))
        self.list_signals = QtWidgets.QListWidget()
        self.list_signals.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.list_signals, stretch=2)
        self.list_signals.itemSelectionChanged.connect(self._on_signal_selection_changed)

        # navigator (overview+detail)
        lay.addWidget(QtWidgets.QLabel("Navigator (overview+detail)"))
        self.chk_nav = QtWidgets.QCheckBox("Enable navigator")
        self.chk_nav.setChecked(True)
        self.chk_nav.stateChanged.connect(self._rebuild_plots)
        lay.addWidget(self.chk_nav)

        self.combo_nav_signal = QtWidgets.QComboBox()
        self.combo_nav_signal.currentIndexChanged.connect(self._on_navigator_signal_changed)
        lay.addWidget(QtWidgets.QLabel("Navigator signal"))
        lay.addWidget(self.combo_nav_signal)

        # options
        opt_row = QtWidgets.QHBoxLayout()
        self.spin_rows = QtWidgets.QSpinBox()
        self.spin_rows.setRange(1, 24)
        self.spin_rows.setValue(6)
        self.spin_rows.valueChanged.connect(self._rebuild_plots)
        opt_row.addWidget(QtWidgets.QLabel("Max rows"))
        opt_row.addWidget(self.spin_rows)
        lay.addLayout(opt_row)

        self.chk_delta = QtWidgets.QCheckBox("Delta to reference run")
        self.chk_delta.stateChanged.connect(self._rebuild_plots)
        lay.addWidget(self.chk_delta)

        ref_row = QtWidgets.QHBoxLayout()
        ref_row.addWidget(QtWidgets.QLabel("Reference run"))
        self.combo_ref = QtWidgets.QComboBox()
        self.combo_ref.setEnabled(False)
        self.combo_ref.setToolTip("Эталон для Δ-режима, Influence(t), heatmap, multivar и baseline событий.")
        self.combo_ref.currentIndexChanged.connect(self._on_reference_run_changed)
        ref_row.addWidget(self.combo_ref, stretch=1)
        lay.addLayout(ref_row)

        # display options (baseline, units, scale locking)
        gb = QtWidgets.QGroupBox("Display / Scales")
        g = QtWidgets.QGridLayout(gb)
        g.setContentsMargins(8, 8, 8, 8)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(4)

        g.addWidget(QtWidgets.QLabel("Distance"), 0, 0)
        self.combo_dist_unit = QtWidgets.QComboBox()
        self.combo_dist_unit.addItems(["mm", "m"])
        self.combo_dist_unit.setCurrentText(str(getattr(self, 'dist_unit', 'mm')))
        self.combo_dist_unit.currentIndexChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.combo_dist_unit, 0, 1)

        g.addWidget(QtWidgets.QLabel("Angle"), 0, 2)
        self.combo_angle_unit = QtWidgets.QComboBox()
        self.combo_angle_unit.addItems(["deg", "rad"])
        self.combo_angle_unit.setCurrentText(str(getattr(self, 'angle_unit', 'deg')))
        self.combo_angle_unit.currentIndexChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.combo_angle_unit, 0, 3)

        self.chk_zero_baseline = QtWidgets.QCheckBox("Zero baseline (disp/angle)")
        self.chk_zero_baseline.setChecked(bool(getattr(self, 'zero_baseline', True)))
        self.chk_zero_baseline.stateChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.chk_zero_baseline, 1, 0, 1, 2)

        g.addWidget(QtWidgets.QLabel("Baseline window, s"), 1, 2)
        self.spin_baseline_s = QtWidgets.QDoubleSpinBox()
        self.spin_baseline_s.setRange(0.0, 5.0)
        self.spin_baseline_s.setSingleStep(0.05)
        self.spin_baseline_s.setDecimals(3)
        self.spin_baseline_s.setValue(float(getattr(self, 'baseline_window_s', 0.0) or 0.0))
        self.spin_baseline_s.valueChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.spin_baseline_s, 1, 3)

        self.chk_lock_y = QtWidgets.QCheckBox("Lock Y (per-signal)")
        self.chk_lock_y.setChecked(bool(getattr(self, 'lock_y', True)))
        self.chk_lock_y.stateChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.chk_lock_y, 2, 0, 1, 2)

        self.chk_lock_y_unit = QtWidgets.QCheckBox("Lock Y by unit")
        self.chk_lock_y_unit.setChecked(bool(getattr(self, 'lock_y_by_unit', False)))
        self.chk_lock_y_unit.stateChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.chk_lock_y_unit, 2, 2, 1, 2)

        self.chk_sym_y = QtWidgets.QCheckBox("Symmetric Y around 0")
        self.chk_sym_y.setChecked(bool(getattr(self, 'sym_y', True)))
        self.chk_sym_y.stateChanged.connect(self._on_display_opts_changed)
        g.addWidget(self.chk_sym_y, 3, 0, 1, 2)

        lay.addWidget(gb)

        # discrete events ("галька")
        gb_ev = QtWidgets.QGroupBox("Events (discrete)")
        ge = QtWidgets.QGridLayout(gb_ev)
        ge.setContentsMargins(8, 8, 8, 8)
        ge.setHorizontalSpacing(8)
        ge.setVerticalSpacing(4)

        self.chk_events = QtWidgets.QCheckBox("Show event markers")
        self.chk_events.setChecked(bool(getattr(self, 'events_enabled', False)))
        self.chk_events.setToolTip(
            "Показывает моменты переключения дискретных сигналов (0/1/2...) как вертикальные линии.\n"
            "Полезно для порогов: клапан открылся, отрыв колеса, пробой и т.п."
        )
        self.chk_events.stateChanged.connect(self._rebuild_plots)
        ge.addWidget(self.chk_events, 0, 0, 1, 2)

        ge.addWidget(QtWidgets.QLabel("Max markers"), 1, 0)
        self.spin_events_max = QtWidgets.QSpinBox()
        self.spin_events_max.setRange(0, 300)
        self.spin_events_max.setSingleStep(10)
        self.spin_events_max.setValue(int(getattr(self, 'events_max', 60) or 60))
        self.spin_events_max.setToolTip("Ограничение на число вертикальных маркеров, чтобы графики не превращались в шум.")
        self.spin_events_max.valueChanged.connect(self._rebuild_plots)
        ge.addWidget(self.spin_events_max, 1, 1)

        ge.addWidget(QtWidgets.QLabel("Event signals (auto)"), 2, 0, 1, 2)
        self.list_events = QtWidgets.QListWidget()
        self.list_events.setToolTip(
            "Список формируется автоматически по дискретным сигналам.\n"
            "Отметьте события, которые хотите видеть на графиках."
        )
        self.list_events.setMinimumHeight(110)
        self.list_events.itemChanged.connect(self._on_event_selection_changed)
        ge.addWidget(self.list_events, 3, 0, 1, 2)

        lay.addWidget(gb_ev)

        self.lbl_readout = QtWidgets.QLabel("x: –")
        self.lbl_readout.setWordWrap(True)
        lay.addWidget(self.lbl_readout)

        # Time slider / playhead (optional animation)
        lay.addWidget(QtWidgets.QLabel("Playhead (time scrub)"))
        row_ph = QtWidgets.QHBoxLayout()
        self.btn_play = QtWidgets.QPushButton("▶")
        self.btn_play.setCheckable(True)
        self.btn_play.setEnabled(False)
        self.btn_play.toggled.connect(self._toggle_play)
        row_ph.addWidget(self.btn_play)

        self.spin_fps = QtWidgets.QSpinBox()
        self.spin_fps.setRange(1, 60)
        self.spin_fps.setValue(24)
        self.spin_fps.setEnabled(False)
        self.spin_fps.setToolTip("Play FPS")
        self.spin_fps.valueChanged.connect(self._on_fps_changed)
        row_ph.addWidget(QtWidgets.QLabel("FPS"))
        row_ph.addWidget(self.spin_fps)

        self.slider_time = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_time.setRange(0, 0)
        self.slider_time.setValue(0)
        self.slider_time.setEnabled(False)
        self.slider_time.valueChanged.connect(self._on_time_slider)
        row_ph.addWidget(self.slider_time, stretch=1)
        lay.addLayout(row_ph)

        lay.addStretch(0)
        dock.setWidget(w)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        self.dock_controls = dock


    # -------------------------
    # Persistent UI state (QSettings)
    # -------------------------

    def closeEvent(self, event):  # noqa: N802
        try:
            if bool(getattr(self, '_workspace_app_focus_connected', False)):
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    app.focusChanged.disconnect(self._on_app_focus_changed)
        except Exception:
            pass
        finally:
            self._workspace_app_focus_connected = False
        try:
            self._save_settings()
        except Exception:
            pass
        return super().closeEvent(event)

    def _qs_bool(self, v, default=False) -> bool:
        if v is None:
            return bool(default)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(int(v))
        s = str(v).strip().lower()
        if s in ('1','true','yes','y','on'):
            return True
        if s in ('0','false','no','n','off',''):
            return False
        return bool(default)

    def _qs_int(self, v, default=0) -> int:
        try:
            return int(v)
        except Exception:
            try:
                s = str(v).strip().replace(',', '.')
                if not s:
                    raise ValueError("empty")
                return int(round(float(s)))
            except Exception:
                return int(default)

    def _qs_float(self, v, default=0.0) -> float:
        try:
            return float(v)
        except Exception:
            try:
                s = str(v).strip().replace(',', '.')
                if not s:
                    raise ValueError("empty")
                return float(s)
            except Exception:
                return float(default)

    def _qs_str_list(self, v) -> List[str]:
        return _parse_qsettings_str_list(v)

    def _qs_float_pair(self, v) -> Optional[Tuple[float, float]]:
        vals = self._qs_str_list(v)
        if len(vals) < 2:
            return None
        try:
            a = float(vals[0])
            b = float(vals[1])
        except Exception:
            return None
        if not (np.isfinite(a) and np.isfinite(b)):
            return None
        return float(a), float(b)

    def _load_settings(self) -> None:
        s = getattr(self, '_settings', None)
        if s is None:
            return
        self._restore_after_load = {}

        try:
            geo = s.value('geometry')
            if geo is not None:
                self.restoreGeometry(geo)
        except Exception:
            pass
        try:
            stt = s.value('window_state')
            if stt is not None:
                self._restore_after_load['window_state'] = stt
        except Exception:
            pass

        try:
            self.combo_dist_unit.setCurrentText(str(s.value('dist_unit', self.dist_unit)))
            self.combo_angle_unit.setCurrentText(str(s.value('angle_unit', self.angle_unit)))
        except Exception:
            pass
        try:
            self.flow_unit = str(s.value('flow_unit', self.flow_unit) or self.flow_unit)
        except Exception:
            pass

        try:
            self.chk_nav.setChecked(self._qs_bool(s.value('nav_enabled', self.chk_nav.isChecked()), self.chk_nav.isChecked()))
            self.chk_delta.setChecked(self._qs_bool(s.value('mode_delta', self.chk_delta.isChecked()), self.chk_delta.isChecked()))
            self._workspace_analysis_mode = str(
                s.value('workspace_analysis_mode', getattr(self, '_workspace_analysis_mode', 'all_to_all'))
                or getattr(self, '_workspace_analysis_mode', 'all_to_all')
            )
            raw_focus_mode = s.value('workspace_focus_mode')
            if raw_focus_mode is not None:
                self._restore_after_load['workspace_focus_mode'] = str(raw_focus_mode or 'all')
            raw_focus_dock = s.value('workspace_focus_dock')
            if raw_focus_dock is not None:
                self._restore_after_load['workspace_focus_dock'] = str(raw_focus_dock or '')
            if hasattr(self, 'spin_rows'):
                self.spin_rows.setValue(self._qs_int(s.value('plot_rows', self.spin_rows.value()), self.spin_rows.value()))
            if hasattr(self, 'spin_fps'):
                self.spin_fps.setValue(self._qs_int(s.value('play_fps', self.spin_fps.value()), self.spin_fps.value()))
            self.chk_zero_baseline.setChecked(
                self._qs_bool(s.value('zero_baseline', self.chk_zero_baseline.isChecked()), self.chk_zero_baseline.isChecked())
            )
            self.chk_lock_y.setChecked(self._qs_bool(s.value('lock_y_signal', self.chk_lock_y.isChecked()), self.chk_lock_y.isChecked()))
            self.chk_lock_y_unit.setChecked(
                self._qs_bool(s.value('lock_y_unit', self.chk_lock_y_unit.isChecked()), self.chk_lock_y_unit.isChecked())
            )
            self.robust_y = self._qs_bool(s.value('robust_y', self.robust_y), self.robust_y)
            self.chk_sym_y.setChecked(self._qs_bool(s.value('sym_y', self.sym_y), self.sym_y))
        except Exception:
            pass

        # Discrete events
        try:
            if hasattr(self, 'chk_events'):
                self.chk_events.setChecked(self._qs_bool(s.value('events_enabled', False), False))
            if hasattr(self, 'spin_events_max'):
                self.spin_events_max.setValue(self._qs_int(s.value('events_max', 60), 60))
        except Exception:
            pass

        try:
            self.baseline_mode = str(s.value('baseline_mode', self.baseline_mode) or self.baseline_mode)
            self.spin_baseline_s.setValue(
                self._qs_float(s.value('baseline_window_s', self.baseline_window_s), self.baseline_window_s)
            )
            self.baseline_first_n = self._qs_int(s.value('baseline_first_n', self.baseline_first_n), self.baseline_first_n)
        except Exception:
            pass

        try:
            self.heat_enabled = self._qs_bool(s.value('heat_enabled', self.heat_enabled), self.heat_enabled)
            if hasattr(self, 'chk_heatmap'):
                self.chk_heatmap.setChecked(bool(self.heat_enabled))
            self.heat_metric = str(s.value('heat_metric', self.heat_metric) or self.heat_metric)
            self.heat_max_sigs = self._qs_int(s.value('heat_max_sigs', self.heat_max_sigs), self.heat_max_sigs)
            self.heat_max_time_points = self._qs_int(
                s.value('heat_max_time_points', self.heat_max_time_points),
                self.heat_max_time_points,
            )
        except Exception:
            pass
        try:
            self._restore_after_load['table'] = str(s.value('table', ''))
        except Exception:
            pass
        try:
            raw = s.value('signal_filter')
            if raw is not None:
                self._restore_after_load['signal_filter'] = str(raw or '')
        except Exception:
            pass
        try:
            raw = s.value('dist_signal')
            if raw is not None:
                self._restore_after_load['dist_signal'] = str(raw or '')
        except Exception:
            pass
        try:
            raw = s.value('nav_signal')
            if raw is not None:
                self._restore_after_load['nav_signal'] = str(raw or '')
        except Exception:
            pass
        try:
            raw = s.value('nav_region')
            if raw is not None:
                self._restore_after_load['nav_region'] = raw
        except Exception:
            pass
        try:
            raw = s.value('play_time')
            if raw is not None:
                self._restore_after_load['play_time'] = raw
        except Exception:
            pass
        try:
            raw = s.value('play_index')
            if raw is not None:
                self._restore_after_load['play_index'] = raw
        except Exception:
            pass
        for k in ('signals','runs','runs_paths'):
            try:
                raw = s.value(k)
                if raw is None:
                    continue
                self._restore_after_load[k] = self._qs_str_list(raw)
            except Exception:
                pass
        try:
            raw = s.value('last_files')
            if raw is not None:
                self._restore_after_load['dataset_paths'] = self._qs_str_list(raw)
        except Exception:
            pass
        try:
            raw = s.value('runs_selection_explicit')
            if raw is not None:
                self._restore_after_load['runs_selection_explicit'] = self._qs_bool(raw, False)
        except Exception:
            pass
        try:
            raw = s.value('signals_selection_explicit')
            if raw is not None:
                self._restore_after_load['signals_selection_explicit'] = self._qs_bool(raw, False)
        except Exception:
            pass
        try:
            self._restore_after_load['reference_run'] = str(s.value('reference_run', '') or '')
        except Exception:
            pass
        try:
            self._restore_after_load['reference_run_path'] = str(s.value('reference_run_path', '') or '')
        except Exception:
            pass

        # events selection restore (items created after load)
        try:
            raw = s.value('events_selected')
            if raw is None:
                pass
            else:
                self._restore_after_load['events_selected'] = self._qs_str_list(raw)
        except Exception:
            pass
        try:
            raw = s.value('events_selection_explicit')
            if raw is not None:
                self._restore_after_load['events_selection_explicit'] = self._qs_bool(raw, False)
        except Exception:
            pass

        # Influence(t) heatmap restore (widgets created later)
        try:
            self._restore_after_load['inflheat_enabled'] = self._qs_bool(s.value('inflheat_enabled', False), False)
            self._restore_after_load['inflheat_maxfeat'] = self._qs_int(s.value('inflheat_maxfeat', 24), 24)
            self._restore_after_load['inflheat_maxsigs'] = self._qs_int(s.value('inflheat_maxsigs', 12), 12)
            self._restore_after_load['inflheat_frames'] = self._qs_int(s.value('inflheat_frames', 120), 120)
            self._restore_after_load['inflheat_tpts'] = self._qs_int(s.value('inflheat_tpts', 2500), 2500)
        except Exception:
            pass

        # QA restore (widgets created later)
        try:
            self._restore_after_load['qa_enabled'] = self._qs_bool(s.value('qa_enabled', True), True)
            self._restore_after_load['qa_sens'] = str(s.value('qa_sens', 'normal') or 'normal')
            self._restore_after_load['qa_all'] = self._qs_bool(s.value('qa_all', False), False)
        except Exception:
            pass

    def _apply_restore_after_load(self) -> None:
        stt = dict(getattr(self, '_restore_after_load', {}) or {})
        self._restore_after_load = {}
        if not stt:
            return
        valid_focus_modes = {"all", "heatmaps", "multivariate", "qa"}
        saved_focus_mode = str(stt.get('workspace_focus_mode') or '').strip()
        if saved_focus_mode not in valid_focus_modes:
            saved_focus_mode = ""
        saved_focus_dock = str(stt.get('workspace_focus_dock') or '').strip()
        if saved_focus_dock and not isinstance(self._workspace_dock_by_attr(saved_focus_dock), QtWidgets.QDockWidget):
            saved_focus_dock = ""
        had_window_state = stt.get('window_state') is not None
        try:
            win_state = stt.get('window_state')
            if win_state is not None:
                self.restoreState(win_state)
        except Exception:
            pass
        if saved_focus_mode:
            self._workspace_focus_mode = saved_focus_mode
        if saved_focus_dock:
            self._workspace_focus_dock_attr = saved_focus_dock
        # Influence(t) heatmap dock
        try:
            if hasattr(self, 'chk_inflheat'):
                self.chk_inflheat.blockSignals(True)
                self.chk_inflheat.setChecked(
                    self._qs_bool(stt.get('inflheat_enabled', self.chk_inflheat.isChecked()), self.chk_inflheat.isChecked())
                )
                self.chk_inflheat.blockSignals(False)
            if hasattr(self, 'spin_inflheat_feat'):
                self.spin_inflheat_feat.setValue(
                    self._qs_int(stt.get('inflheat_maxfeat', self.spin_inflheat_feat.value()), self.spin_inflheat_feat.value())
                )
            if hasattr(self, 'spin_inflheat_sigs'):
                self.spin_inflheat_sigs.setValue(
                    self._qs_int(stt.get('inflheat_maxsigs', self.spin_inflheat_sigs.value()), self.spin_inflheat_sigs.value())
                )
            if hasattr(self, 'spin_inflheat_frames'):
                self.spin_inflheat_frames.setValue(
                    self._qs_int(stt.get('inflheat_frames', self.spin_inflheat_frames.value()), self.spin_inflheat_frames.value())
                )
            if hasattr(self, 'spin_inflheat_tpts'):
                self.spin_inflheat_tpts.setValue(
                    self._qs_int(stt.get('inflheat_tpts', self.spin_inflheat_tpts.value()), self.spin_inflheat_tpts.value())
                )
        except Exception:
            try:
                if hasattr(self, 'chk_inflheat'):
                    self.chk_inflheat.blockSignals(False)
            except Exception:
                pass

        if not getattr(self, 'runs', None):
            try:
                if saved_focus_mode and not had_window_state:
                    self._focus_workspace_preset(saved_focus_mode)
                    self._restore_workspace_focus_dock(saved_focus_mode=saved_focus_mode, dock_attr=saved_focus_dock)
                elif saved_focus_mode:
                    self._update_workspace_status()
            except Exception:
                pass
            keep_keys = (
                'dataset_paths',
                'runs',
                'runs_paths',
                'runs_selection_explicit',
                'reference_run',
                'reference_run_path',
                'table',
                'signal_filter',
                'dist_signal',
                'nav_signal',
                'nav_region',
                'play_time',
                'play_index',
                'signals',
                'signals_selection_explicit',
                'events_selected',
                'events_selection_explicit',
            )
            self._restore_after_load = {k: stt[k] for k in keep_keys if k in stt}
            return

        have_runs_restore = ('runs' in stt) or ('runs_paths' in stt)
        want_runs = stt.get('runs') if ('runs' in stt) else None
        want_run_paths = stt.get('runs_paths') if ('runs_paths' in stt) else None
        legacy_runs_restore = 'runs_selection_explicit' not in stt
        runs_explicit = self._qs_bool(stt.get('runs_selection_explicit', False), False)
        run_restore_target_count = 0
        run_restore_complete = True
        restored_run_matches = 0
        want_run_set = set(str(x) for x in (want_runs or []))
        want_run_path_set = set()
        for x in (want_run_paths or []):
            try:
                want_run_path_set.add(self._normalized_run_path(Path(str(x))))
            except Exception:
                pass
        if legacy_runs_restore:
            try:
                dataset_path_set = {
                    self._normalized_run_path(Path(str(x)))
                    for x in (stt.get('dataset_paths') or [])
                    if str(x).strip()
                }
            except Exception:
                dataset_path_set = set()
            try:
                current_all_run_paths = {
                    self._normalized_run_path(getattr(run, "path", Path("")))
                    for run in getattr(self, 'runs', [])
                }
            except Exception:
                current_all_run_paths = set()
            if want_run_path_set:
                baseline_paths = dataset_path_set or current_all_run_paths
                runs_explicit = bool(baseline_paths) and (want_run_path_set != baseline_paths)
            elif want_run_set:
                current_all_labels = {str(getattr(run, "label", "") or "") for run in getattr(self, 'runs', [])}
                runs_explicit = bool(current_all_labels) and (want_run_set != current_all_labels)
            else:
                runs_explicit = False
        try:
            if have_runs_restore:
                self.list_runs.blockSignals(True)
                for i in range(self.list_runs.count()):
                    it = self.list_runs.item(i)
                    if it is not None:
                        it.setSelected(False)
                if want_run_path_set:
                    run_restore_target_count = len(want_run_path_set)
                    for i in range(self.list_runs.count()):
                        it = self.list_runs.item(i)
                        if it is None:
                            continue
                        key = it.data(QtCore.Qt.UserRole)
                        key = str(key).strip() if key is not None else ""
                        if not key and 0 <= i < len(self.runs):
                            key = self._normalized_run_path(getattr(self.runs[i], "path", Path("")))
                        if key in want_run_path_set:
                            it.setSelected(True)
                            restored_run_matches += 1
                elif want_run_set:
                    run_restore_target_count = len(want_run_set)
                    for i in range(self.list_runs.count()):
                        it = self.list_runs.item(i)
                        if it is not None and it.text() in want_run_set:
                            it.setSelected(True)
                            restored_run_matches += 1
                if run_restore_target_count > 0 and restored_run_matches < run_restore_target_count:
                    run_restore_complete = False
                self.list_runs.blockSignals(False)
        except Exception:
            try:
                self.list_runs.blockSignals(False)
            except Exception:
                pass

        try:
            if have_runs_restore and (want_run_set or want_run_path_set):
                if restored_run_matches <= 0 and not runs_explicit:
                    self.list_runs.blockSignals(True)
                    for i in range(self.list_runs.count()):
                        it = self.list_runs.item(i)
                        if it is not None:
                            it.setSelected(True)
                    self.list_runs.blockSignals(False)
            elif have_runs_restore and (not runs_explicit) and (not self.list_runs.selectedIndexes()):
                self.list_runs.blockSignals(True)
                for i in range(self.list_runs.count()):
                    it = self.list_runs.item(i)
                    if it is not None:
                        it.setSelected(True)
                self.list_runs.blockSignals(False)
            elif (not have_runs_restore) and hasattr(self, 'list_runs') and not self.list_runs.selectedIndexes():
                self.list_runs.blockSignals(True)
                for i in range(self.list_runs.count()):
                    it = self.list_runs.item(i)
                    if it is not None:
                        it.setSelected(True)
                self.list_runs.blockSignals(False)
        except Exception:
            try:
                self.list_runs.blockSignals(False)
            except Exception:
                pass

        try:
            selected_run_keys = [
                self._normalized_run_path(getattr(run, 'path', Path('')))
                for run in self._selected_runs()
            ]
        except Exception:
            selected_run_keys = []
        self._runs_selection_explicit = bool(runs_explicit)
        if selected_run_keys:
            self.runs_selected_paths = list(selected_run_keys)
        elif have_runs_restore and runs_explicit:
            self.runs_selected_paths = list(want_run_path_set)
        elif not self._runs_selection_explicit:
            self.runs_selected_paths = []

        if not run_restore_complete:
            for k in (
                'reference_run',
                'reference_run_path',
                'table',
                'signals',
                'signals_selection_explicit',
                'dist_signal',
                'events_selected',
                'events_selection_explicit',
            ):
                stt.pop(k, None)

        try:
            preferred_ref_label = str(stt.get('reference_run') or '')
            preferred_ref_path = str(stt.get('reference_run_path') or '').strip()
            if preferred_ref_label:
                self.reference_run_selected = str(preferred_ref_label)
            if preferred_ref_path:
                self.reference_run_selected_path = self._normalized_run_path(Path(preferred_ref_path))
            if preferred_ref_path:
                pref_key = self._normalized_run_path(Path(preferred_ref_path))
                for run in self._selected_runs():
                    if self._normalized_run_path(getattr(run, 'path', Path(''))) == pref_key:
                        preferred_ref_label = str(run.label)
                        break
            self._refresh_reference_runs(preferred_ref_label)
        except Exception:
            pass

        try:
            self._refresh_table_list()
        except Exception:
            pass

        try:
            want_table = stt.get('table')
            if want_table:
                self.table_selected = str(want_table)
            if want_table and hasattr(self, 'combo_table'):
                self.combo_table.blockSignals(True)
                idx = self.combo_table.findText(str(want_table))
                if idx >= 0:
                    self.combo_table.setCurrentIndex(idx)
                    self.current_table = self.combo_table.currentText() or self.current_table
                    if self.current_table:
                        self.table_selected = str(self.current_table)
                self.combo_table.blockSignals(False)
        except Exception:
            try:
                if hasattr(self, 'combo_table'):
                    self.combo_table.blockSignals(False)
            except Exception:
                pass

        try:
            want_filter = str(stt.get('signal_filter') or '')
            if hasattr(self, 'edit_filter'):
                self.edit_filter.blockSignals(True)
                self.edit_filter.setText(want_filter)
                self.edit_filter.blockSignals(False)
        except Exception:
            try:
                if hasattr(self, 'edit_filter'):
                    self.edit_filter.blockSignals(False)
            except Exception:
                pass

        try:
            want_dist_signal = str(stt.get('dist_signal') or '').strip()
            if want_dist_signal:
                self.dist_signal_selected = want_dist_signal
        except Exception:
            pass
        try:
            want_nav_signal = str(stt.get('nav_signal') or '').strip()
            if want_nav_signal:
                self.navigator_signal_selected = want_nav_signal
        except Exception:
            pass
        try:
            nav_region = self._qs_float_pair(stt.get('nav_region'))
            if nav_region is not None:
                self.navigator_region_selected = nav_region
        except Exception:
            pass
        try:
            raw_play_time = stt.get('play_time')
            if raw_play_time is not None:
                play_time = self._qs_float(raw_play_time, 0.0)
                if np.isfinite(play_time):
                    self.playhead_time_selected = float(play_time)
        except Exception:
            pass
        try:
            raw_play_index = stt.get('play_index')
            if raw_play_index is not None:
                self.playhead_index_selected = int(self._qs_int(raw_play_index, 0))
        except Exception:
            pass

        try:
            self._refresh_signal_list()
        except Exception:
            pass

        have_sigs_restore = 'signals' in stt
        want_sigs = stt.get('signals') if have_sigs_restore else None
        legacy_sigs_restore = 'signals_selection_explicit' not in stt
        sigs_explicit = self._qs_bool(stt.get('signals_selection_explicit', False), False)
        sig_restore_complete = True
        try:
            restored_sig_matches = 0
            if have_sigs_restore:
                restored_sig_set = set()
                default_sig_set = set(self._default_signal_names())
                self.list_signals.blockSignals(True)
                for i in range(self.list_signals.count()):
                    self.list_signals.item(i).setSelected(False)
                want_sig_set = set(str(x) for x in (want_sigs or []))
                if want_sig_set:
                    for i in range(self.list_signals.count()):
                        it = self.list_signals.item(i)
                        if it.text() in want_sig_set:
                            it.setSelected(True)
                            restored_sig_matches += 1
                            restored_sig_set.add(str(it.text()))
                    sig_restore_complete = restored_sig_matches >= len(want_sig_set)
                if legacy_sigs_restore:
                    if not sig_restore_complete:
                        sigs_explicit = False
                    else:
                        sigs_explicit = bool(restored_sig_set) and (restored_sig_set != default_sig_set)
                self._signals_selection_explicit = bool(sigs_explicit)
                self.list_signals.blockSignals(False)
                if want_sigs and (restored_sig_matches <= 0 or (legacy_sigs_restore and not sig_restore_complete)) and not sigs_explicit:
                    self._select_default_signals()
                elif (not want_sigs) and (not sigs_explicit):
                    self._select_default_signals()
            elif hasattr(self, 'list_signals') and not self.list_signals.selectedIndexes():
                self._select_default_signals()
        except Exception:
            try:
                self.list_signals.blockSignals(False)
            except Exception:
                pass
        try:
            self.signals_selected = list(self._selected_signals())
            if have_sigs_restore and sigs_explicit and want_sigs and not getattr(self, 'available_signals', []):
                self.signals_selected = [str(x) for x in want_sigs]
        except Exception:
            if have_sigs_restore and sigs_explicit and want_sigs and not getattr(self, 'available_signals', []):
                self.signals_selected = [str(x) for x in want_sigs]
            elif not bool(getattr(self, '_signals_selection_explicit', False)):
                self.signals_selected = []
        try:
            self._refresh_event_list()
            self._refresh_events_table()
        except Exception:
            pass

        # Events selection (items exist after run/table restore)
        try:
            if ('events_selected' in stt) and hasattr(self, 'list_events'):
                want_ev = stt.get('events_selected') or []
                legacy_ev_restore = 'events_selection_explicit' not in stt
                ev_explicit = self._qs_bool(stt.get('events_selection_explicit', False), False)
                if want_ev or ev_explicit:
                    want_set = set([str(x) for x in want_ev])
                    default_ev_names = []
                    for i in range(self.list_events.count()):
                        it = self.list_events.item(i)
                        if it is None:
                            continue
                        sig = it.data(QtCore.Qt.UserRole)
                        sig = str(sig) if sig is not None else str(it.text()).strip()
                        if "  [" in sig:
                            sig = sig.split("  [", 1)[0]
                        default_ev_names.append(sig)
                    default_ev_set = set(self._default_event_names(default_ev_names))
                    restored_ev_matches = 0
                    restored_ev_set = set()
                    ev_restore_complete = True
                    self.list_events.blockSignals(True)
                    for i in range(self.list_events.count()):
                        it = self.list_events.item(i)
                        if it is None:
                            continue
                        sig = it.data(QtCore.Qt.UserRole)
                        sig = str(sig) if sig is not None else str(it.text()).strip()
                        if "  [" in sig:
                            sig = sig.split("  [", 1)[0]
                        matched = sig in want_set
                        it.setCheckState(QtCore.Qt.Checked if matched else QtCore.Qt.Unchecked)
                        if matched:
                            restored_ev_matches += 1
                            restored_ev_set.add(sig)
                    self.list_events.blockSignals(False)
                    if want_ev:
                        ev_restore_complete = restored_ev_matches >= len(want_set)
                    if legacy_ev_restore:
                        if not ev_restore_complete:
                            ev_explicit = False
                        else:
                            ev_explicit = bool(restored_ev_set) and (restored_ev_set != default_ev_set)
                    self.events_selected = self._get_selected_event_signals()
                    if want_ev and ev_explicit and self.list_events.count() <= 0:
                        self.events_selected = [str(x) for x in want_ev]
                    self._events_selection_explicit = bool(ev_explicit)
                    if want_ev and (restored_ev_matches <= 0 or (legacy_ev_restore and not ev_restore_complete)) and not ev_explicit:
                        self.list_events.blockSignals(True)
                        for i in range(self.list_events.count()):
                            it = self.list_events.item(i)
                            if it is not None:
                                it.setCheckState(QtCore.Qt.Unchecked)
                        self.list_events.blockSignals(False)
                        self.events_selected = []
                        self._events_selection_explicit = False
                        self._refresh_event_list()
                    self._refresh_events_table()
                else:
                    self.events_selected = self._get_selected_event_signals()
                    self._events_selection_explicit = False
        except Exception:
            try:
                if hasattr(self, 'list_events'):
                    self.list_events.blockSignals(False)
            except Exception:
                pass
        try:
            if not bool(getattr(self, '_events_selection_explicit', False)) and (not getattr(self, 'events_selected', None)):
                self.events_selected = self._get_selected_event_signals()
        except Exception:
            pass

        try:
            self._refresh_anim_diag_panel()
        except Exception:
            pass

        try:
            if hasattr(self, 'chk_inflheat') and bool(self.chk_inflheat.isChecked()):
                self._schedule_inflheat_rebuild(delay_ms=10)
        except Exception:
            pass

        try:
            self._rebuild_plots()
        except Exception:
            pass
        try:
            if ('play_time' in stt) or ('play_index' in stt):
                self._ensure_playhead_visible_in_view()
        except Exception:
            pass
        try:
            if saved_focus_mode and not had_window_state:
                self._focus_workspace_preset(saved_focus_mode)
                self._restore_workspace_focus_dock(saved_focus_mode=saved_focus_mode, dock_attr=saved_focus_dock)
            elif saved_focus_mode:
                self._update_workspace_status()
        except Exception:
            pass

    def _save_settings(self) -> None:
        s = getattr(self, '_settings', None)
        if s is None:
            return
        have_runs = bool(getattr(self, 'runs', []))

        try:
            s.setValue('geometry', self.saveGeometry())
            s.setValue('window_state', self.saveState())
        except Exception:
            pass

        try:
            s.setValue('dist_unit', self.combo_dist_unit.currentText())
            s.setValue('angle_unit', self.combo_angle_unit.currentText())
            s.setValue('flow_unit', str(getattr(self, 'flow_unit', 'raw') or 'raw'))
        except Exception:
            pass

        try:
            s.setValue('nav_enabled', int(self.chk_nav.isChecked()))
            s.setValue('mode_delta', int(self.chk_delta.isChecked()))
            s.setValue('workspace_analysis_mode', str(getattr(self, '_workspace_analysis_mode', 'all_to_all') or 'all_to_all'))
            s.setValue('workspace_focus_mode', str(getattr(self, '_workspace_focus_mode', 'all') or 'all'))
            s.setValue('workspace_focus_dock', str(getattr(self, '_workspace_focus_dock_attr', '') or ''))
            s.setValue('plot_rows', int(self.spin_rows.value()))
            s.setValue('play_fps', int(self.spin_fps.value()))
            if hasattr(self, 'combo_dist_mode'):
                s.setValue('dist_mode', self._run_metrics_mode_key())
            if hasattr(self, 'chk_dist_use_view'):
                s.setValue('dist_use_view', int(self.chk_dist_use_view.isChecked()))
            s.setValue('zero_baseline', int(self.chk_zero_baseline.isChecked()))
            s.setValue('lock_y_signal', int(self.chk_lock_y.isChecked()))
            s.setValue('lock_y_unit', int(self.chk_lock_y_unit.isChecked()))
            s.setValue('robust_y', int(bool(getattr(self, 'robust_y', True))))
            s.setValue('sym_y', int(self.chk_sym_y.isChecked()))
        except Exception:
            pass

        try:
            s.setValue('baseline_mode', str(getattr(self, 'baseline_mode', 't0') or 't0'))
            s.setValue(
                'baseline_window_s',
                float(self.spin_baseline_s.value()) if hasattr(self, 'spin_baseline_s') else float(self.baseline_window_s),
            )
            s.setValue('baseline_first_n', int(getattr(self, 'baseline_first_n', 0) or 0))
        except Exception:
            pass

        try:
            s.setValue('heat_enabled', int(bool(self.chk_heatmap.isChecked())))
            s.setValue('heat_metric', self.combo_heat_metric.currentText())
            s.setValue('heat_max_sigs', int(self.spin_heat_sigs.value()))
            s.setValue('heat_max_time_points', int(self.spin_heat_tpts.value()))
        except Exception:
            pass

        # Influence(t) heatmap dock
        try:
            if hasattr(self, 'chk_inflheat'):
                s.setValue('inflheat_enabled', int(self.chk_inflheat.isChecked()))
            if hasattr(self, 'spin_inflheat_feat'):
                s.setValue('inflheat_maxfeat', int(self.spin_inflheat_feat.value()))
            if hasattr(self, 'spin_inflheat_sigs'):
                s.setValue('inflheat_maxsigs', int(self.spin_inflheat_sigs.value()))
            if hasattr(self, 'spin_inflheat_frames'):
                s.setValue('inflheat_frames', int(self.spin_inflheat_frames.value()))
            if hasattr(self, 'spin_inflheat_tpts'):
                s.setValue('inflheat_tpts', int(self.spin_inflheat_tpts.value()))
        except Exception:
            pass

        if have_runs:
            try:
                table_value = str(getattr(self, 'table_selected', '') or self.combo_table.currentText() or self.current_table or '')
                s.setValue('table', table_value)
            except Exception:
                pass

            try:
                if hasattr(self, 'edit_filter'):
                    s.setValue('signal_filter', str(self.edit_filter.text() or ''))
            except Exception:
                pass
            try:
                dist_signal_value = str(
                    getattr(self, 'dist_signal_selected', '') or
                    (self.combo_dist_signal.currentText() if hasattr(self, 'combo_dist_signal') else '') or ''
                ).strip()
                s.setValue('dist_signal', dist_signal_value)
            except Exception:
                pass
            try:
                nav_signal_value = str(
                    getattr(self, 'navigator_signal_selected', '') or self.combo_nav_signal.currentText() or ''
                ).strip()
                s.setValue('nav_signal', nav_signal_value)
            except Exception:
                pass
            try:
                nav_region_value = getattr(self, 'navigator_region_selected', None)
                reg = getattr(self, '_region', None)
                if reg is not None:
                    rr = reg.getRegion()
                    if isinstance(rr, (list, tuple)) and len(rr) >= 2:
                        nav_region_value = (float(rr[0]), float(rr[1]))
                elif getattr(self, 'plots', None):
                    try:
                        xr = self.plots[0].getViewBox().viewRange()[0]
                        if isinstance(xr, (list, tuple)) and len(xr) >= 2:
                            nav_region_value = (float(xr[0]), float(xr[1]))
                    except Exception:
                        pass
                if nav_region_value is not None:
                    r0, r1 = float(nav_region_value[0]), float(nav_region_value[1])
                    if np.isfinite(r0) and np.isfinite(r1):
                        self.navigator_region_selected = (r0, r1)
                        s.setValue('nav_region', json.dumps([r0, r1]))
            except Exception:
                pass
            try:
                play_time_value = getattr(self, 'playhead_time_selected', None)
                play_index_value = getattr(self, 'playhead_index_selected', None)
                t_ref = getattr(self, '_t_ref', None)
                if t_ref is not None and len(t_ref):
                    idx = int(self.slider_time.value()) if hasattr(self, 'slider_time') else 0
                    idx = max(0, min(idx, int(len(t_ref) - 1)))
                    play_index_value = idx
                    play_time_value = float(np.asarray(t_ref, dtype=float)[idx])
                if play_time_value is not None and np.isfinite(float(play_time_value)):
                    s.setValue('play_time', float(play_time_value))
                if play_index_value is not None:
                    s.setValue('play_index', int(play_index_value))
            except Exception:
                pass

            try:
                if bool(getattr(self, '_signals_selection_explicit', False)):
                    sigs = [str(x) for x in (getattr(self, 'signals_selected', []) or [])]
                else:
                    sigs = [it.text() for it in self.list_signals.selectedItems()]
                if not sigs:
                    sigs = [str(x) for x in (getattr(self, 'signals_selected', []) or [])]
                s.setValue('signals', json.dumps(sigs))
                s.setValue('signals_selection_explicit', int(bool(getattr(self, '_signals_selection_explicit', False))))
            except Exception:
                pass

            try:
                selected_runs = list(self._selected_runs())
                run_labels = [str(getattr(r, 'label', '') or '') for r in selected_runs]
                run_paths = [str(self._absolute_run_path(r.path)) for r in selected_runs]
                if not run_paths and not bool(getattr(self, '_runs_selection_explicit', False)):
                    remembered_keys = {
                        str(x) for x in (getattr(self, 'runs_selected_paths', []) or []) if str(x).strip()
                    }
                    if remembered_keys:
                        for run in getattr(self, 'runs', []):
                            try:
                                key = self._normalized_run_path(getattr(run, 'path', Path('')))
                            except Exception:
                                continue
                            if key in remembered_keys:
                                run_labels.append(str(getattr(run, 'label', '') or ''))
                                run_paths.append(str(self._absolute_run_path(getattr(run, 'path', Path('')))))
                s.setValue('runs', json.dumps(run_labels))
                s.setValue('runs_paths', json.dumps(run_paths))
                s.setValue('runs_selection_explicit', int(bool(getattr(self, '_runs_selection_explicit', False))))
            except Exception:
                pass

            try:
                ref_label = str(getattr(self, 'reference_run_selected', '') or self._reference_run_label() or '')
                s.setValue('reference_run', ref_label)
                ref_path = ''
                remembered_ref_path = str(getattr(self, 'reference_run_selected_path', '') or '')
                if remembered_ref_path:
                    ref_path = remembered_ref_path
                else:
                    ref_run = self._reference_run()
                    if ref_run is not None:
                        ref_path = str(self._absolute_run_path(ref_run.path))
                s.setValue('reference_run_path', ref_path)
            except Exception:
                pass

            try:
                files = [str(self._absolute_run_path(r.path)) for r in getattr(self, 'runs', [])]
                s.setValue('last_files', json.dumps(files))
            except Exception:
                pass

        # Influence(t) dock
        try:
            chk = getattr(self, "chk_infl_enable", None)
            spn = getattr(self, "spin_infl_maxfeat", None)
            trn = getattr(self, "chk_infl_trend", None)
            if chk is not None:
                s.setValue("infl_enabled", int(chk.isChecked()))
            if spn is not None:
                s.setValue("infl_maxfeat", int(spn.value()))
            if trn is not None:
                s.setValue("infl_trend", int(trn.isChecked()))
        except Exception:
            pass

        # QA dock
        try:
            chkq = getattr(self, "chk_qa_enable", None)
            cmbq = getattr(self, "combo_qa_sens", None)
            allq = getattr(self, "chk_qa_all", None)
            if chkq is not None:
                s.setValue("qa_enabled", int(chkq.isChecked()))
            if cmbq is not None:
                s.setValue("qa_sens", str(self._qa_sensitivity_code()))
            if allq is not None:
                s.setValue("qa_all", int(allq.isChecked()))
        except Exception:
            pass

        # Events dock
        try:
            chk = getattr(self, 'chk_events', None)
            spn = getattr(self, 'spin_events_max', None)
            if chk is not None:
                s.setValue('events_enabled', int(chk.isChecked()))
            if spn is not None:
                s.setValue('events_max', int(spn.value()))
        except Exception:
            pass
        if have_runs:
            try:
                if bool(getattr(self, '_events_selection_explicit', False)):
                    ev_sigs = [str(x) for x in (getattr(self, 'events_selected', []) or [])]
                else:
                    ev_sigs = self._get_selected_event_signals()
                if not ev_sigs:
                    ev_sigs = [str(x) for x in (getattr(self, 'events_selected', []) or [])]
                s.setValue('events_selected', json.dumps(ev_sigs))
                s.setValue('events_selection_explicit', int(bool(getattr(self, '_events_selection_explicit', False))))
            except Exception:
                pass


    def _build_menu(self):
        m = self.menuBar()
        file_menu = m.addMenu("File")

        act_open = QtGui.QAction("Open NPZ...", self)
        act_open.setShortcut(QtGui.QKeySequence.Open)
        act_open.triggered.connect(self._open_dialog)
        file_menu.addAction(act_open)

        act_export = QtGui.QAction("Export PNG...", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._export_png)
        file_menu.addAction(act_export)

        act_export_snapshots = QtGui.QAction("Export Snapshot Set...", self)
        act_export_snapshots.setShortcut("Ctrl+Shift+E")
        act_export_snapshots.triggered.connect(self._export_snapshot_set_dialog)
        file_menu.addAction(act_export_snapshots)

        act_quit = QtGui.QAction("Quit", self)
        act_quit.setShortcut(QtGui.QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

    def _build_status_bar(self) -> None:
        sb = QtWidgets.QStatusBar(self)
        sb.setObjectName("workspaceStatusBar")
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)

        self.lbl_status_selection = QtWidgets.QLabel("Runs 0 | Table — | Signals 0")
        self.lbl_status_selection.setObjectName("statusChipSelection")
        sb.addPermanentWidget(self.lbl_status_selection)

        self.lbl_status_quality = QtWidgets.QLabel("Events 0 | QA —")
        self.lbl_status_quality.setObjectName("statusChipQuality")
        sb.addPermanentWidget(self.lbl_status_quality)

        self.lbl_status_layout = QtWidgets.QLabel("Focus Overview | Docks 0/0 | Ref —")
        self.lbl_status_layout.setObjectName("statusChipLayout")
        sb.addPermanentWidget(self.lbl_status_layout)

    def _apply_workspace_theme(self) -> None:
        try:
            self.glw.setBackground("#f2eadf")
        except Exception:
            pass
        try:
            self.setStyleSheet(
                """
                QMainWindow#compareViewerWindow {
                    background: #efe6d7;
                }
                QDockWidget {
                    color: #2f322b;
                    font-weight: 600;
                }
                QDockWidget::title {
                    background: #d9ccb4;
                    color: #2f322b;
                    padding: 7px 10px;
                    border-bottom: 1px solid #b9aa90;
                }
                QGroupBox {
                    background: #fbf7ef;
                    border: 1px solid #d6c8af;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 6px;
                    color: #2f322b;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #695f4b;
                }
                QListWidget, QTreeWidget, QPlainTextEdit, QTableWidget,
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background: #fffdf8;
                    border: 1px solid #d6c8af;
                    border-radius: 6px;
                    color: #1f251f;
                    selection-background-color: #0f7b64;
                    selection-color: #f6fbf8;
                }
                QHeaderView::section {
                    background: #e6dcc8;
                    color: #3e3a32;
                    border: 0;
                    border-right: 1px solid #d0c1a7;
                    border-bottom: 1px solid #d0c1a7;
                    padding: 5px 6px;
                }
                QPushButton {
                    background: #f7efe2;
                    color: #2b3028;
                    border: 1px solid #ccbba0;
                    border-radius: 6px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background: #f2e6d4;
                }
                QPushButton:checked {
                    background: #0f7b64;
                    color: #f6fbf8;
                    border-color: #0f7b64;
                }
                QTabWidget::pane {
                    border: 1px solid #d6c8af;
                    background: #fbf7ef;
                }
                QTabBar::tab {
                    background: #e8decc;
                    color: #4b463d;
                    border: 1px solid #d0c1a7;
                    padding: 6px 12px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background: #fffaf1;
                    color: #1f251f;
                }
                QStatusBar#workspaceStatusBar {
                    background: #ded1b9;
                    border-top: 1px solid #c7b89d;
                }
                QLabel#statusChipSelection,
                QLabel#statusChipQuality,
                QLabel#statusChipLayout {
                    border-radius: 10px;
                    padding: 4px 10px;
                    margin: 3px 4px;
                    font-weight: 600;
                }
                QLabel#statusChipSelection {
                    background: #faf4e8;
                    border: 1px solid #cfbea1;
                    color: #3c3a33;
                }
                QLabel#statusChipQuality {
                    background: #eef7f2;
                    border: 1px solid #98c7b2;
                    color: #245746;
                }
                QLabel#statusChipLayout {
                    background: #f4efe6;
                    border: 1px solid #cbbda4;
                    color: #4d5046;
                }
                QLabel#workspaceAssistantTitle {
                    color: #324136;
                    font-size: 13px;
                    font-weight: 700;
                }
                QLabel#workspaceAssistantBody {
                    background: #f8f1e5;
                    border: 1px solid #d6c8af;
                    border-radius: 8px;
                    color: #384136;
                    padding: 8px 10px;
                }
                QTextBrowser#workspaceInsightsBrowser {
                    background: #fcf8f1;
                    border: 1px solid #d6c8af;
                    border-radius: 8px;
                    padding: 4px;
                    color: #2f322b;
                }
                """
            )
        except Exception:
            pass

    def _set_status_chip_tone(self, label: Optional[QtWidgets.QLabel], tone: str) -> None:
        if label is None:
            return
        tone_map = {
            "ok": ("#e7f5ee", "#8cc3ae", "#245746"),
            "warn": ("#fff0d8", "#d9b36a", "#6a4b00"),
            "alert": ("#fde2de", "#d48f81", "#7c2415"),
            "neutral": ("#faf4e8", "#cfbea1", "#3c3a33"),
            "accent": ("#e6f2ef", "#93bbae", "#2d5b4f"),
        }
        bg, border, fg = tone_map.get(str(tone), tone_map["neutral"])
        try:
            label.setStyleSheet(
                f"background:{bg}; border:1px solid {border}; color:{fg};"
                "border-radius:10px; padding:4px 10px; margin:3px 4px; font-weight:600;"
            )
        except Exception:
            pass

    def _set_workspace_assistant_tone(self, tone: str) -> None:
        label = getattr(self, "lbl_workspace_assistant", None)
        title = getattr(self, "lbl_workspace_assistant_title", None)
        if label is None:
            return
        tone_map = {
            "ok": ("#e7f5ee", "#8cc3ae", "#245746"),
            "warn": ("#fff0d8", "#d9b36a", "#6a4b00"),
            "alert": ("#fde2de", "#d48f81", "#7c2415"),
            "neutral": ("#f8f1e5", "#d6c8af", "#384136"),
            "accent": ("#e6f2ef", "#93bbae", "#2d5b4f"),
        }
        bg, border, fg = tone_map.get(str(tone), tone_map["neutral"])
        try:
            label.setStyleSheet(
                f"background:{bg}; border:1px solid {border}; color:{fg};"
                "border-radius:8px; padding:8px 10px;"
            )
        except Exception:
            pass
        if title is not None:
            try:
                title.setStyleSheet(f"color:{fg}; font-size:13px; font-weight:700;")
            except Exception:
                pass

    def _sync_workspace_focus_buttons(self) -> None:
        mapping = {
            "all": getattr(self, "btn_workspace_focus_all", None),
            "heatmaps": getattr(self, "btn_workspace_focus_heatmaps", None),
            "multivariate": getattr(self, "btn_workspace_focus_multivar", None),
            "qa": getattr(self, "btn_workspace_focus_qa", None),
        }
        mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        for key, button in mapping.items():
            if button is None:
                continue
            prev = False
            try:
                prev = button.blockSignals(True)
                button.setChecked(key == mode)
            except Exception:
                pass
            finally:
                try:
                    button.blockSignals(prev)
                except Exception:
                    pass

    def _workspace_focus_mode_display_text(
        self,
        *,
        focus_mode: str,
        follow_target: Optional[Dict[str, object]] = None,
        for_action: bool = False,
    ) -> str:
        mode = str(focus_mode or "all")
        base_labels = {
            "all": "Show All Docks" if for_action else "Overview",
            "heatmaps": "Focus Heatmaps" if for_action else "Heatmaps",
            "multivariate": "Focus Multivariate" if for_action else "Multivar",
            "qa": "Focus QA / Events" if for_action else "QA / Events",
        }
        label = base_labels.get(mode, base_labels["all"])
        target = dict(follow_target or {})
        target_focus = str(target.get("focus") or "").strip()
        target_dock = str(target.get("dock_label") or "").strip()
        if target_dock == "Influence(t) Heatmap":
            target_short = "Influence(t)"
        else:
            target_short = target_dock
        current_short = self._workspace_current_dock_label(short=True)
        if mode == "all" and target_short:
            if current_short and current_short != target_short:
                return f"{label} ({current_short}) -> Next {target_short}"
            return f"{label} -> Next {target_short}"
        if mode == "all" and current_short:
            return f"{label} ({current_short})"
        if mode != target_focus or not target_dock:
            return label
        if mode == "heatmaps":
            return f"{label} -> {target_short}"
        if mode == "qa":
            return f"{label} -> {target_dock}"
        return label

    def _update_workspace_focus_labels(
        self,
        *,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
    ) -> None:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        trust_flag = bool(
            trust_visible if trust_visible is not None else (
                getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible()
            )
        )
        qa_count = int(
            qa_issues if qa_issues is not None else int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        )
        events = dict(getattr(self, "_insight_events", {}) or {})
        events_rows = int(events.get("rows", 0) or 0)
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=self._workspace_influence_lens_summary(),
            events=events,
            trust_visible=trust_flag,
            qa_issues=qa_count,
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=mode,
            trust_visible=trust_flag,
            qa_issues=qa_count,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )

        button_mapping = {
            "all": getattr(self, "btn_workspace_focus_all", None),
            "heatmaps": getattr(self, "btn_workspace_focus_heatmaps", None),
            "multivariate": getattr(self, "btn_workspace_focus_multivar", None),
            "qa": getattr(self, "btn_workspace_focus_qa", None),
        }
        action_mapping = {
            "all": getattr(self, "act_view_show_all_docks", None),
            "heatmaps": getattr(self, "act_view_focus_heatmaps", None),
            "multivariate": getattr(self, "act_view_focus_multivar", None),
            "qa": getattr(self, "act_view_focus_qa", None),
        }
        for key, button in button_mapping.items():
            if button is None:
                continue
            try:
                button.setText(self._workspace_focus_mode_display_text(focus_mode=key, follow_target=follow_target, for_action=False))
            except Exception:
                pass
        for key, action in action_mapping.items():
            if action is None:
                continue
            try:
                action.setText(self._workspace_focus_mode_display_text(focus_mode=key, follow_target=follow_target, for_action=True))
            except Exception:
                pass

    def _update_workspace_focus_button_hints(
        self,
        *,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
    ) -> None:
        mapping = {
            "all": (
                getattr(self, "btn_workspace_focus_all", None),
                "Show the full workspace with all docks."
            ),
            "heatmaps": (
                getattr(self, "btn_workspace_focus_heatmaps", None),
                "Focus Delta and Influence heatmaps."
            ),
            "multivariate": (
                getattr(self, "btn_workspace_focus_multivar", None),
                "Focus SPLOM, Parallel and 3D melting-cloud / pebbles views."
            ),
            "qa": (
                getattr(self, "btn_workspace_focus_qa", None),
                "Focus QA and event drill-down tools."
            ),
        }
        for key, spec in mapping.items():
            button, base = spec
            if button is None:
                continue
            hint = self._workspace_focus_mode_hint_text(
                focus_mode=key,
                base=base,
                analysis_mode=analysis_mode,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
            )
            try:
                button.setToolTip(hint)
            except Exception:
                pass

    def _update_workspace_focus_action_hints(
        self,
        *,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
    ) -> None:
        mapping = {
            "all": (
                getattr(self, "act_view_show_all_docks", None),
                "Show the full workspace with all docks."
            ),
            "heatmaps": (
                getattr(self, "act_view_focus_heatmaps", None),
                "Focus Delta and Influence heatmaps."
            ),
            "multivariate": (
                getattr(self, "act_view_focus_multivar", None),
                "Focus SPLOM, Parallel and 3D melting-cloud / pebbles views."
            ),
            "qa": (
                getattr(self, "act_view_focus_qa", None),
                "Focus QA and event drill-down tools."
            ),
        }
        for key, spec in mapping.items():
            action, base = spec
            if action is None:
                continue
            hint = self._workspace_focus_mode_hint_text(
                focus_mode=key,
                base=base,
                analysis_mode=analysis_mode,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
            )
            try:
                action.setToolTip(hint)
                action.setStatusTip(hint)
            except Exception:
                pass

    def _workspace_analysis_label(self) -> str:
        mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        labels = {
            "one_to_all": "1->all",
            "all_to_one": "all->1",
            "all_to_all": "all->all",
        }
        return labels.get(mode, labels["all_to_all"])

    def _sync_workspace_analysis_buttons(self) -> None:
        mapping = {
            "one_to_all": getattr(self, "btn_workspace_analysis_one_to_all", None),
            "all_to_one": getattr(self, "btn_workspace_analysis_all_to_one", None),
            "all_to_all": getattr(self, "btn_workspace_analysis_all_to_all", None),
        }
        mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if mode not in mapping:
            mode = "all_to_all"
        for key, button in mapping.items():
            if button is None:
                continue
            prev = False
            try:
                prev = button.blockSignals(True)
                button.setChecked(key == mode)
            except Exception:
                pass
            finally:
                try:
                    button.blockSignals(prev)
                except Exception:
                    pass

    def _workspace_follow_target_label(
        self,
        follow_target: Optional[Dict[str, object]] = None,
        *,
        separator: str = " -> ",
        fallback: str = "Overview",
    ) -> str:
        target = dict(follow_target or {})
        focus_label = str(target.get("focus_label") or "").strip()
        dock_label = str(target.get("dock_label") or "").strip()
        if focus_label and dock_label:
            return f"{focus_label}{separator}{dock_label}"
        if dock_label:
            return dock_label
        if focus_label:
            return focus_label
        return fallback

    def _workspace_current_focus_target(self) -> Dict[str, str]:
        mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        attr = str(getattr(self, "_workspace_focus_dock_attr", "") or "").strip()
        if mode == "all" or not attr:
            return {}
        if attr == "dock_controls":
            return {}
        if attr not in self._workspace_allowed_dock_attrs(mode):
            return {}
        dock = self._workspace_dock_by_attr(attr)
        if dock is None:
            return {}
        focus_label_map = {
            "heatmaps": "Heatmaps",
            "multivariate": "Multivar",
            "qa": "QA / Events",
        }
        dock_label_map = {
            "dock_controls": "Controls",
            "dock_heatmap": "Δ(t)",
            "dock_peak_heatmap": "Peak |Δ|",
            "dock_open_timeline": "Valves (open)",
            "dock_influence": "Influence(t)",
            "dock_run_metrics": "Run metrics",
            "dock_static_stroke": "Static (t0)",
            "dock_inflheat": "Influence(t) Heatmap",
            "dock_multivar": "Multivariate",
            "dock_qa": "QA",
            "dock_events": "Events",
            "dock_geometry_acceptance": "Geometry acceptance",
        }
        if attr == "dock_events":
            return {
                "focus": mode,
                "focus_label": str(focus_label_map.get(mode, mode) or mode),
                "dock_attr": attr,
                "dock_label": self._events_dock_route_label(self._events_dock_current_subtarget()),
            }
        return {
            "focus": mode,
            "focus_label": str(focus_label_map.get(mode, mode) or mode),
            "dock_attr": attr,
            "dock_label": str(dock_label_map.get(attr, dock.windowTitle() or attr) or attr),
        }

    def _workspace_current_dock_label(self, *, short: bool = False) -> str:
        attr = str(getattr(self, "_workspace_focus_dock_attr", "") or "").strip()
        if not attr or attr == "dock_controls":
            return ""
        label_map = {
            "dock_heatmap": "Δ(t)",
            "dock_peak_heatmap": "Peak |Δ|",
            "dock_open_timeline": "Valves (open)",
            "dock_influence": "Influence(t)",
            "dock_run_metrics": "Run metrics",
            "dock_static_stroke": "Static (t0)",
            "dock_inflheat": "Influence(t) Heatmap",
            "dock_multivar": "Multivariate",
            "dock_qa": "QA",
            "dock_events": "Events",
            "dock_geometry_acceptance": "Geometry acceptance",
        }
        if attr == "dock_events":
            return self._events_dock_route_label(self._events_dock_current_subtarget(), short=short)
        label = str(label_map.get(attr, "") or "")
        if short and label == "Influence(t) Heatmap":
            return "Influence(t)"
        return label

    def _workspace_route_label(
        self,
        follow_target: Optional[Dict[str, object]] = None,
        *,
        separator: str = ": ",
        fallback: str = "Overview",
        include_current: bool = True,
    ) -> str:
        target = dict(follow_target or {})
        target_label = self._workspace_follow_target_label(target, separator=separator, fallback=fallback)
        target_dock = str(target.get("dock_label") or "").strip()
        current_dock = self._workspace_current_dock_label()
        if include_current and current_dock and current_dock != target_dock:
            return f"{current_dock} -> {target_label}"
        return target_label

    def _workspace_focus_mode_hint_text(
        self,
        *,
        focus_mode: str,
        base: str,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
        events_insight: Optional[Dict[str, object]] = None,
        infl_lens: Optional[Dict[str, object]] = None,
        mv_lens: Optional[Dict[str, object]] = None,
    ) -> str:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        trust_flag = bool(
            trust_visible if trust_visible is not None else (
                getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible()
            )
        )
        qa_count = int(
            qa_issues if qa_issues is not None else int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        )
        events = dict(events_insight if events_insight is not None else (getattr(self, "_insight_events", {}) or {}))
        infl_summary = dict(infl_lens if infl_lens is not None else self._workspace_influence_lens_summary())
        mv_summary = dict(mv_lens if mv_lens is not None else self._workspace_multivar_lens_summary())
        events_rows = int(events.get("rows", 0) or 0)
        current_anchor = self._workspace_analysis_anchor_label(
            analysis_mode=mode,
            infl_lens=infl_summary,
            mv_lens=mv_summary,
        )
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=infl_summary,
            events=events,
            trust_visible=trust_flag,
            qa_issues=qa_count,
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=mode,
            trust_visible=trust_flag,
            qa_issues=qa_count,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        target_focus = str(follow_target.get("focus") or "").strip()
        target_dock = str(follow_target.get("dock_label") or "").strip()
        target_label = self._workspace_follow_target_label(follow_target)
        reason = self._workspace_contextual_focus_reason(
            analysis_mode=mode,
            trust_visible=trust_flag,
            qa_issues=qa_count,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )

        hint = base
        if focus_mode == "all":
            hint = f"{hint} Current anchor: {current_anchor}."
            current_dock = self._workspace_current_dock_label()
            if current_dock:
                hint = f"{hint} Current overview dock: {current_dock}."
            if target_label:
                hint = f"{hint} Exact target right now: {target_label}."
            if target_label and target_focus:
                hint = f"{hint} Use this when you want context before jumping to {target_label}. If you are already in Overview, clicking it again follows that target."
            return hint

        if focus_mode == "heatmaps" and mode in {"one_to_all", "all_to_one"}:
            hint = f"{hint} Current anchor: {current_anchor}."
        elif focus_mode == "multivariate" and mode == "all_to_all":
            hint = f"{hint} Current anchor: {current_anchor}."
        elif focus_mode == "qa" and (trust_flag or qa_count > 0 or target_focus == "qa"):
            hint = f"{hint} Current anchor: {current_anchor}."

        if focus_mode == target_focus and target_dock:
            hint = f"{hint} Best dock inside this focus: {target_dock}."
            hint = f"{hint} Recommended right now because {reason}."
        elif focus_mode == "qa" and (trust_flag or qa_count > 0):
            hint = f"{hint} Recommended when trust warnings or QA issues need confirmation."
        return hint

    def _workspace_analysis_mode_hint_text(
        self,
        *,
        analysis_mode: str,
        base: str,
        infl_lens: Optional[Dict[str, object]] = None,
        mv_lens: Optional[Dict[str, object]] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
        events_insight: Optional[Dict[str, object]] = None,
    ) -> str:
        infl_summary = dict(infl_lens if infl_lens is not None else self._workspace_influence_lens_summary())
        mv_summary = dict(mv_lens if mv_lens is not None else self._workspace_multivar_lens_summary())
        events = dict(events_insight if events_insight is not None else (getattr(self, "_insight_events", {}) or {}))
        trust_flag = bool(
            trust_visible if trust_visible is not None else (
                getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible()
            )
        )
        qa_count = int(
            qa_issues if qa_issues is not None else int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        )
        events_rows = int(events.get("rows", 0) or 0)
        anchor = self._workspace_analysis_anchor_label(
            analysis_mode=analysis_mode,
            infl_lens=infl_summary,
            mv_lens=mv_summary,
        )
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=analysis_mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=infl_summary,
            events=events,
            trust_visible=trust_flag,
            qa_issues=qa_count,
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=analysis_mode,
            trust_visible=trust_flag,
            qa_issues=qa_count,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        reason = self._workspace_contextual_focus_reason(
            analysis_mode=analysis_mode,
            trust_visible=trust_flag,
            qa_issues=qa_count,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        target_label = self._workspace_follow_target_label(follow_target)
        return f"{base} Anchor: {anchor}. Recommended target: {target_label} because {reason}."

    def _update_workspace_analysis_button_hints(self, *, current_mode: Optional[str] = None) -> None:
        mode = str(current_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        events_insight = dict(getattr(self, "_insight_events", {}) or {})
        hints = {
            "one_to_all": (
                getattr(self, "btn_workspace_analysis_one_to_all", None),
                "One driver to many responses.",
            ),
            "all_to_one": (
                getattr(self, "btn_workspace_analysis_all_to_one", None),
                "Many drivers to one target response.",
            ),
            "all_to_all": (
                getattr(self, "btn_workspace_analysis_all_to_all", None),
                "Cross-coupled field scouting with clouds and pebbles.",
            ),
        }
        for key, spec in hints.items():
            button, base = spec
            if button is None:
                continue
            hint = self._workspace_analysis_mode_hint_text(
                analysis_mode=key,
                base=base,
                infl_lens=infl_lens,
                mv_lens=mv_lens,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
                events_insight=events_insight,
            )
            if key == mode:
                hint = f"{hint} Current lens."
            try:
                button.setToolTip(hint)
            except Exception:
                pass

    def _sync_workspace_analysis_actions(self, *, current_mode: Optional[str] = None) -> None:
        mode = str(current_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        mapping = {
            "one_to_all": getattr(self, "act_view_analysis_one_to_all", None),
            "all_to_one": getattr(self, "act_view_analysis_all_to_one", None),
            "all_to_all": getattr(self, "act_view_analysis_all_to_all", None),
        }
        if mode not in mapping:
            mode = "all_to_all"
        for key, action in mapping.items():
            if action is None:
                continue
            prev = False
            try:
                prev = action.blockSignals(True)
                action.setChecked(key == mode)
            except Exception:
                pass
            finally:
                try:
                    action.blockSignals(prev)
                except Exception:
                    pass

    def _update_workspace_analysis_action_hints(self, *, current_mode: Optional[str] = None) -> None:
        mode = str(current_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        events_insight = dict(getattr(self, "_insight_events", {}) or {})
        action_specs = {
            "one_to_all": (
                getattr(self, "act_view_analysis_one_to_all", None),
                "One driver to many responses.",
            ),
            "all_to_one": (
                getattr(self, "act_view_analysis_all_to_one", None),
                "Many drivers to one target response.",
            ),
            "all_to_all": (
                getattr(self, "act_view_analysis_all_to_all", None),
                "Cross-coupled field scouting with clouds and pebbles.",
            ),
        }
        for key, spec in action_specs.items():
            action, base = spec
            if action is None:
                continue
            hint = self._workspace_analysis_mode_hint_text(
                analysis_mode=key,
                base=base,
                infl_lens=infl_lens,
                mv_lens=mv_lens,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
                events_insight=events_insight,
            )
            if key == mode:
                hint = f"{hint} Current lens."
            try:
                action.setToolTip(hint)
                action.setStatusTip(hint)
            except Exception:
                pass

    def _workspace_recommended_focus_for_analysis(self, mode: str) -> str:
        mode = str(mode or "all_to_all")
        mapping = {
            "one_to_all": "heatmaps",
            "all_to_one": "heatmaps",
            "all_to_all": "multivariate",
        }
        return mapping.get(mode, "all")

    def _workspace_contextual_focus_recommendation(
        self,
        *,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
        events_rows: Optional[int] = None,
        events_insight: Optional[Dict[str, object]] = None,
        causal_story: Optional[Dict[str, object]] = None,
    ) -> str:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        base = self._workspace_recommended_focus_for_analysis(mode)
        trust_flag = bool(
            trust_visible if trust_visible is not None else (
                getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible()
            )
        )
        qa_count = int(
            qa_issues if qa_issues is not None else int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        )
        events = dict(events_insight if events_insight is not None else (getattr(self, "_insight_events", {}) or {}))
        rows = int(events_rows if events_rows is not None else int(events.get("rows", 0) or 0))
        source_rows = int(events.get("source_rows", rows) or rows)
        no_signals_selected = bool(events.get("no_signals_selected", False))
        if trust_flag or qa_count > 0:
            return "qa"
        if no_signals_selected and source_rows > 0 and mode in {"one_to_all", "all_to_one"}:
            return "qa"
        story = dict(
            causal_story
            if causal_story is not None
            else self._workspace_causal_story_summary(
                analysis_mode=mode,
                heat=dict(getattr(self, "_insight_heat", {}) or {}),
                infl=dict(getattr(self, "_insight_infl", {}) or {}),
                infl_lens=self._workspace_influence_lens_summary(),
                events=events,
                trust_visible=trust_flag,
                qa_issues=qa_count,
            )
        )
        story_conf = str(story.get("confidence") or "").strip()
        repair_lane = str(story.get("repair_lane") or "").strip()
        if repair_lane in {"heatmaps", "qa", "multivariate"}:
            return repair_lane
        if story_conf == "partial":
            if mode in {"one_to_all", "all_to_one"}:
                return "qa" if (rows > 0 or source_rows > 0) else "heatmaps"
            if mode == "all_to_all":
                return "heatmaps"
        if story_conf == "tentative":
            if mode in {"one_to_all", "all_to_one"}:
                return "heatmaps"
        return base

    def _workspace_contextual_focus_reason(
        self,
        *,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
        events_rows: Optional[int] = None,
        events_insight: Optional[Dict[str, object]] = None,
        causal_story: Optional[Dict[str, object]] = None,
    ) -> str:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        trust_flag = bool(
            trust_visible if trust_visible is not None else (
                getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible()
            )
        )
        qa_count = int(
            qa_issues if qa_issues is not None else int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        )
        events = dict(events_insight if events_insight is not None else (getattr(self, "_insight_events", {}) or {}))
        rows = int(events_rows if events_rows is not None else int(events.get("rows", 0) or 0))
        source_rows = int(events.get("source_rows", rows) or rows)
        no_signals_selected = bool(events.get("no_signals_selected", False))
        story = dict(
            causal_story
            if causal_story is not None
            else self._workspace_causal_story_summary(
                analysis_mode=mode,
                heat=dict(getattr(self, "_insight_heat", {}) or {}),
                infl=dict(getattr(self, "_insight_infl", {}) or {}),
                infl_lens=self._workspace_influence_lens_summary(),
                events=events,
                trust_visible=trust_flag,
                qa_issues=qa_count,
            )
        )
        follow_target = dict(
            self._workspace_follow_target_summary(
                analysis_mode=mode,
                trust_visible=trust_flag,
                qa_issues=qa_count,
                events_rows=rows,
                events_insight=events,
                causal_story=story,
            )
            or {}
        )
        target_dock = str(follow_target.get("dock_label") or "").strip()
        target_label = self._workspace_route_label(follow_target, separator=": ", fallback="the suggested dock")
        current_dock = self._workspace_current_dock_label()
        if current_dock and target_dock and current_dock != target_dock:
            target_ref = f"the route {target_label}"
        else:
            target_ref = target_label or "the suggested dock"
        if trust_flag:
            return f"trust banner is active, so {target_ref} should check the evidence before pattern hunting"
        if qa_count > 0:
            return f"QA found {qa_count} issue(s), so {target_ref} should validate suspicious regions first"
        if no_signals_selected and source_rows > 0 and mode in {"one_to_all", "all_to_one"}:
            return f"event channels are muted, so {target_ref} should restore causal timing support"
        story_conf = str(story.get("confidence") or "").strip()
        repair_lane = str(story.get("repair_lane") or "").strip()
        repair_hint = str(story.get("repair_hint") or "").strip()
        if repair_lane == "qa":
            return (
                f"the weakest link is event / evidence support, so {target_ref} should repair it"
                f"{': ' + repair_hint if repair_hint else ''}"
            )
        if repair_lane == "heatmaps":
            return (
                f"the weakest link is time-local alignment, so {target_ref} should repair it"
                f"{': ' + repair_hint if repair_hint else ''}"
            )
        if repair_lane == "multivariate":
            return (
                f"the weakest link is field structure, so {target_ref} should repair it"
                f"{': ' + repair_hint if repair_hint else ''}"
            )
        if story_conf == "partial":
            if mode in {"one_to_all", "all_to_one"}:
                return f"the causal story is only partially aligned, so {target_ref} should repair the missing link"
            if mode == "all_to_all":
                return f"the corridor is only partially aligned, so {target_ref} should localize the missing link in time"
        if story_conf == "tentative":
            if mode in {"one_to_all", "all_to_one"}:
                return f"the causal story is still tentative, so {target_ref} should stabilize the time-local explanation"
            if mode == "all_to_all":
                return f"the field story is still tentative, so {target_ref} should strengthen the structure before drill-down"
        if mode == "one_to_all":
            return f"{target_ref} is the fastest way to trace one driver fanning out across many responses"
        if mode == "all_to_one":
            return f"{target_ref} keeps one target waveform aligned with many competing drivers"
        if mode == "all_to_all":
            return f"{target_ref} is best for melting-cloud and pebbles-on-sand structure scouting"
        return "full workspace gives the broadest context"

    def _workspace_should_follow_analysis_focus(self, previous_analysis_mode: str, current_focus_mode: str) -> bool:
        current_focus = str(current_focus_mode or "all")
        if current_focus == "all":
            return True
        prev_recommended = self._workspace_contextual_focus_recommendation(analysis_mode=previous_analysis_mode)
        return current_focus == prev_recommended

    def _workspace_live_follow_target(self, *, analysis_mode: Optional[str] = None) -> Dict[str, object]:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        events_rows = 0
        try:
            if getattr(self, "tbl_events", None) is not None:
                events_rows = int(self.tbl_events.rowCount())
        except Exception:
            events_rows = 0
        qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        events = dict(getattr(self, "_insight_events", {}) or {})
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=self._workspace_influence_lens_summary(),
            events=events,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        return dict(
            self._workspace_follow_target_summary(
                analysis_mode=mode,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
                events_rows=events_rows,
                events_insight=events,
                causal_story=causal_story,
            )
            or {}
        )

    def _apply_workspace_follow_target(self, follow_target: Optional[Dict[str, object]] = None) -> None:
        target = dict(follow_target or {})
        focus = str(target.get("focus") or "all")
        self._focus_workspace_preset(focus)
        dock = getattr(self, str(target.get("dock_attr") or ""), None)
        if isinstance(dock, QtWidgets.QDockWidget):
            self._raise_dock(dock)
            if dock is getattr(self, "dock_events", None):
                try:
                    self._set_events_dock_tab(str(target.get("dock_subtarget") or ""))
                except Exception:
                    pass
        self._update_workspace_status()

    def _activate_workspace_focus_mode(self, mode: str) -> None:
        focus = str(mode or "all")
        follow_target = self._workspace_live_follow_target()
        if focus == "all":
            if str(getattr(self, "_workspace_focus_mode", "all") or "all") == "all" and str(follow_target.get("focus") or "").strip():
                self._apply_workspace_follow_target(follow_target)
                return
            self._focus_workspace_preset("all")
            return
        if str(follow_target.get("focus") or "").strip() == focus:
            self._apply_workspace_follow_target(follow_target)
            return
        self._focus_workspace_preset(focus)

    def _set_workspace_analysis_mode(self, mode: str) -> None:
        valid = {"one_to_all", "all_to_one", "all_to_all"}
        previous_analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        current_focus_mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        self._workspace_analysis_mode = str(mode or "all_to_all")
        if self._workspace_analysis_mode not in valid:
            self._workspace_analysis_mode = "all_to_all"
        if self._workspace_should_follow_analysis_focus(previous_analysis_mode, current_focus_mode):
            qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
            trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
            events = dict(getattr(self, "_insight_events", {}) or {})
            events_rows = int(events.get("rows", 0) or 0)
            causal_story = self._workspace_causal_story_summary(
                analysis_mode=self._workspace_analysis_mode,
                heat=dict(getattr(self, "_insight_heat", {}) or {}),
                infl=dict(getattr(self, "_insight_infl", {}) or {}),
                infl_lens=self._workspace_influence_lens_summary(),
                events=events,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
            )
            follow_target = self._workspace_follow_target_summary(
                analysis_mode=self._workspace_analysis_mode,
                trust_visible=trust_visible,
                qa_issues=qa_issues,
                events_rows=events_rows,
                events_insight=events,
                causal_story=causal_story,
            )
            if str(follow_target.get("focus") or ""):
                self._apply_workspace_follow_target(follow_target)
                return
        self._update_workspace_status()

    def _update_workspace_assistant(self) -> None:
        title_label = getattr(self, "lbl_workspace_assistant_title", None)
        body_label = getattr(self, "lbl_workspace_assistant", None)
        if title_label is None or body_label is None:
            return

        runs = list(self._selected_runs()) if hasattr(self, "list_runs") else []
        sigs = list(self._selected_signals()) if hasattr(self, "list_signals") else []
        table = str(getattr(self, "current_table", "") or "-")
        ref = str(self._reference_run_label(runs) or "auto")
        mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())

        events_rows = 0
        try:
            if getattr(self, "tbl_events", None) is not None:
                events_rows = int(self.tbl_events.rowCount())
        except Exception:
            events_rows = 0
        events = dict(getattr(self, "_insight_events", {}) or {})

        qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        try:
            qa_text = str(
                getattr(self, "lbl_qa_summary", None).text()
                if getattr(self, "lbl_qa_summary", None) is not None
                else ""
            )
            if "issues=" in qa_text:
                qa_issues = int(str(qa_text).split("issues=", 1)[1].split()[0].split("(", 1)[0].rstrip(",)"))
        except Exception:
            qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)

        event_focus = ""
        event_name = str(events.get("top_signal") or events.get("sample_signal") or "")
        if event_name:
            try:
                event_time = float(events.get("sample_time_s", 0.0) or 0.0)
                if np.isfinite(event_time):
                    event_focus = f"{event_name} @ {event_time:.3f}s"
                else:
                    event_focus = event_name
            except Exception:
                event_focus = event_name

        notes: List[str] = []
        if trust_visible:
            notes.append("trust banner active")
        if qa_issues > 0:
            notes.append(f"QA issues: {qa_issues}")
        if bool(events.get("no_signals_selected", False)):
            notes.append("events muted")
        elif event_name:
            notes.append(f"event anchor: {event_name}")
        elif events_rows > 0:
            notes.append(f"event rows: {events_rows}")

        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        dist_lens = self._workspace_run_metrics_lens_summary()
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=analysis_mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=infl_lens,
            events=events,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        peak_bridge = self._workspace_peak_heat_bridge_summary(
            analysis_mode=analysis_mode,
            sigs=sigs,
            infl_lens=infl_lens,
            causal_story=causal_story,
        )
        dist_bridge = self._workspace_run_metrics_bridge_summary(
            analysis_mode=analysis_mode,
            sigs=sigs,
            infl_lens=infl_lens,
            dist_lens=dist_lens,
            causal_story=causal_story,
        )
        recommended_focus = self._workspace_contextual_focus_recommendation(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        focus_labels = {
            "all": "all",
            "heatmaps": "heatmaps",
            "multivariate": "multivar",
            "qa": "qa/events",
        }
        recommended_focus_label = focus_labels.get(str(recommended_focus), str(recommended_focus or "all"))
        focus_reason = self._workspace_contextual_focus_reason(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        story_label = self._workspace_causal_story_label(causal_story)
        story_confidence = str(causal_story.get("confidence") or "").strip()
        story_confidence_title = story_confidence.title() if story_confidence else ""
        repair_summary = self._workspace_repair_lane_summary(
            causal_story=causal_story,
            analysis_mode=analysis_mode,
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        current_dock_label = str(self._workspace_current_dock_label() or "").strip()
        target_focus_label = str(follow_target.get('focus_label') or recommended_focus_label or "").strip()
        target_dock_label = str(follow_target.get('dock_label') or 'dock').strip()
        follow_route_label = f"{target_focus_label}: {target_dock_label}" if target_focus_label else target_dock_label
        if current_dock_label and current_dock_label != target_dock_label:
            follow_route_label = f"from {current_dock_label} -> {follow_route_label}"
        follow_button = getattr(self, "btn_workspace_follow_hint", None)
        if isinstance(follow_button, QtWidgets.QPushButton):
            follow_headline = str(repair_summary.get("headline") or "Weakest link")
            follow_detail = str(repair_summary.get("detail") or focus_reason)
            try:
                follow_button.setText(f"Follow weakest link -> {follow_route_label}")
                follow_button.setEnabled(bool(runs))
                extra = f" Current dock: {current_dock_label}." if current_dock_label else ""
                follow_button.setToolTip(f"{follow_headline}. {follow_detail}{extra}")
            except Exception:
                pass
        follow_action = getattr(self, "act_view_focus_hint", None)
        if isinstance(follow_action, QtGui.QAction):
            try:
                follow_action.setText(f"Follow Weakest Link ({follow_route_label})")
                extra = f" Current dock: {current_dock_label}." if current_dock_label else ""
                follow_action.setStatusTip(f"{str(repair_summary.get('headline') or 'Weakest link')}. {str(repair_summary.get('detail') or focus_reason)}{extra}")
                follow_action.setToolTip(f"{str(repair_summary.get('headline') or 'Weakest link')}. {str(repair_summary.get('detail') or focus_reason)}{extra}")
                follow_action.setEnabled(bool(runs))
            except Exception:
                pass
        follow_target_label = self._workspace_follow_target_label(
            follow_target,
            separator=": ",
            fallback=str(recommended_focus_label or "Overview"),
        )
        follow_route_label = self._workspace_route_label(
            follow_target,
            separator=": ",
            fallback=str(recommended_focus_label or "Overview"),
        )

        title = "Compare overview"
        body = (
            f"Reference run: {ref}. Heatmaps explain time-local differences, "
            "QA/Events validate anomalies and Multivariate gets stronger as you add more runs and signals."
        )
        tone = "accent"

        if not runs:
            title = "Load compare bundle"
            body = (
                "Open 2+ NPZ runs. Then pick a shared table and a few signals to unlock "
                "Heatmaps, QA and Multivariate views."
            )
            tone = "neutral"
        elif len(runs) < 2:
            title = "Add one more run"
            body = (
                f"Only {len(runs)} run is selected. Add a peer run to make Delta, Influence and "
                "cross-run QA comparisons informative."
            )
            tone = "neutral"
        elif not sigs:
            title = "Select signals"
            body = (
                f"Table {table} is ready. Pick 2-6 signals on the left. Heatmaps work well for quick contrasts, "
                "while Multivariate becomes most useful with 3+ signals."
            )
            tone = "accent"
        elif analysis_mode == "one_to_all":
            top_feat = str((getattr(self, "_insight_infl", {}) or {}).get("feature") or "")
            top_sig = str((getattr(self, "_insight_infl", {}) or {}).get("signal") or "")
            title = "1 -> all driver sweep"
            if len(runs) < 3:
                body = (
                    "For one-driver-to-many-response analysis, keep 3+ runs selected so Influence(t) can rank "
                    "one meta parameter against many signals."
                )
                tone = "neutral"
            elif len(sigs) < 2:
                body = (
                    f"Reference run: {ref}. Add more signals in table {table} so one parameter can fan out across "
                    "multiple responses in Delta / Influence heatmaps."
                )
                tone = "accent"
            elif infl_lens.get("fanout_feature"):
                examples = ", ".join(
                    f"{sig} {corr:+.2f}" for sig, corr in (infl_lens.get("fanout_examples", []) or [])[:3]
                )
                body = (
                    f"Primary fan-out candidate is {infl_lens.get('fanout_feature')}: it already reaches "
                    f"{int(infl_lens.get('fanout_count', 0) or 0)}/{int(infl_lens.get('signal_count', 0) or 0)} signals "
                    f"at t={float(infl_lens.get('time_s', 0.0) or 0.0):.3f}s."
                )
                if examples:
                    body = f"{body} Start with {examples}, then validate the hotspot in QA / Events."
                tone = "ok" if not trust_visible and qa_issues == 0 else "warn"
            elif top_feat and top_sig:
                body = (
                    f"Current strongest candidate is {top_feat} -> {top_sig}. Stay in Heatmaps / Influence to see "
                    "how one meta driver spreads across many signals and time zones."
                )
                tone = "ok" if not trust_visible and qa_issues == 0 else "warn"
            else:
                body = (
                    f"Use Influence(t) and Influence(t) Heatmap to broadcast one parameter across {len(sigs)} signals. "
                    "Then confirm hot spots with QA / Events."
                )
                tone = "accent"
        elif analysis_mode == "all_to_one":
            target_sig = str(sigs[0] if sigs else "")
            title = "all -> 1 target explanation"
            if len(runs) < 3:
                body = (
                    "Explaining one target signal from many drivers works best with 3+ runs. Add more runs, then keep "
                    "the target waveform stable while moving the playhead."
                )
                tone = "neutral"
            elif len(sigs) > 2:
                body = (
                    f"{len(sigs)} signals are selected. Narrow to 1-2 target signals so Heatmaps and Influence rank "
                    "many meta drivers against one response, not a mixed bundle."
                )
                tone = "accent"
            elif infl_lens.get("target_signal") and infl_lens.get("target_examples"):
                examples = ", ".join(
                    f"{feat} {corr:+.2f}" for feat, corr in (infl_lens.get("target_examples", []) or [])[:3]
                )
                body = (
                    f"Treat {infl_lens.get('target_signal')} as the outcome. Right now the clearest drivers are "
                    f"{examples} at t={float(infl_lens.get('time_s', 0.0) or 0.0):.3f}s."
                )
                if events_rows > 0:
                    body = f"{body} Use Events to see whether local triggers reinforce that explanation."
                tone = "ok" if len(sigs) == 1 and not trust_visible and qa_issues == 0 else "accent"
            else:
                body = (
                    f"Treat {target_sig or 'the current waveform'} as the outcome. Use Delta, Influence and Events to "
                    "explain one response from many parameters and local event triggers."
                )
                tone = "ok" if len(sigs) == 1 and not trust_visible else "accent"
        elif analysis_mode == "all_to_all":
            title = "all -> all structure scouting"
            if mv_lens and int(mv_lens.get("checked_dim_count", 0) or 0) < 3:
                body = (
                    f"Cloud is under-described: only {int(mv_lens.get('checked_dim_count', 0) or 0)} checked dimensions are active. "
                    "Check at least 3-4 fields in Multivariate so SPLOM, Parallel and 3D can separate regimes instead of flattening them."
                )
                tone = "accent"
            elif mv_lens and int(mv_lens.get("keep_pct", 100) or 100) <= 15 and int(mv_lens.get("runs", 0) or 0) >= 4:
                body = (
                    f"Melting cloud is very thin at {int(mv_lens.get('keep_pct', 100) or 100)}%. "
                    f"If you are scouting rare outliers keep sparse-first; if you want regime cores, raise keep% or switch to {('dense-first' if str(mv_lens.get('keep_mode') or '') == 'sparse-first' else 'sparse-first')}."
                )
                tone = "warn"
            elif mv_lens and bool(mv_lens.get("pebbles", False)) and not str(mv_lens.get("peb_signal", "") or "").strip():
                body = (
                    "Cloud geometry is ready, but pebbles have no discrete signal yet. Pick an event signal in Multivariate so the sand/grain overlay can show where structure changes are event-driven."
                )
                tone = "accent"
            elif len(runs) >= 3 and len(sigs) >= 3:
                body = (
                    f"{len(runs)} runs and {len(sigs)} signals are ready for SPLOM, Parallel and 3D melting cloud. "
                    "Use pebbles-on-sand overlays to see where event structure separates clusters."
                )
                if mv_lens:
                    body = (
                        f"{body} Current 3D lens is {mv_lens.get('x') or '—'}/{mv_lens.get('y') or '—'}/{mv_lens.get('z') or '—'} "
                        f"with keep={int(mv_lens.get('keep_pct', 100) or 100)}% in {mv_lens.get('keep_mode') or 'sparse-first'} mode."
                    )
                tone = "ok" if not trust_visible and qa_issues == 0 else "warn"
            else:
                body = (
                    f"Build density for all-to-all analysis: keep 3+ runs and 3+ signals in table {table}. "
                    "That is where clouds, sparse outliers and pebbles become visually useful."
                )
                tone = "accent"
        elif mode == "heatmaps":
            title = "Heatmap comparison"
            body = (
                f"Use Delta and Influence heatmaps to localize where {len(runs)} runs diverge across "
                f"{len(sigs)} selected signals in table {table}. Review QA or Events when a hotspot needs explanation."
            )
            tone = "accent"
        elif mode == "multivariate":
            title = "Multivariate scouting"
            if mv_lens:
                body = (
                    f"Checked fields: {int(mv_lens.get('checked_dim_count', 0) or 0)} out of {int(mv_lens.get('field_count', 0) or 0)}. "
                    f"3D = {mv_lens.get('x') or '—'}/{mv_lens.get('y') or '—'}/{mv_lens.get('z') or '—'}, "
                    f"keep={int(mv_lens.get('keep_pct', 100) or 100)}% ({mv_lens.get('keep_mode') or 'sparse-first'}). "
                    "Use brushing to pull clusters or sparse outliers back into the main compare plots."
                )
                if bool(mv_lens.get("pebbles", False)) and str(mv_lens.get("peb_signal", "") or "").strip():
                    body = f"{body} Pebbles are anchored to {mv_lens.get('peb_signal')}."
                tone = "ok" if (not trust_visible and qa_issues == 0 and int(mv_lens.get('checked_dim_count', 0) or 0) >= 3) else "warn"
            else:
                body = (
                    f"{len(runs)} runs and {len(sigs)} signals are ready for SPLOM, Parallel and 3D cloud analysis. "
                    "Use brushing to pull outliers back into the main compare plots."
                )
                tone = "ok" if (not trust_visible and qa_issues == 0) else "warn"
        elif mode == "qa":
            title = "QA drill-down"
            if qa_issues > 0:
                body = (
                    f"QA found {qa_issues} issue(s). Double-click a QA or Events row to move the playhead, "
                    "keep the reference run stable and verify the local waveform."
                )
                tone = "warn" if not trust_visible and qa_issues < 10 else "alert"
            else:
                body = (
                    f"QA and Events are ready for drill-down on {len(runs)} runs. Use this layout to validate "
                    "suspicious regions before trusting the prettier charts."
                )
                tone = "accent"
        elif trust_visible:
            title = "Trust attention"
            body = (
                "The trust banner reports data-quality caveats. Review QA and Events first, then return "
                "to Heatmaps or Multivariate once the suspect runs are understood."
            )
            tone = "alert" if qa_issues > 0 else "warn"
        elif qa_issues > 0:
            title = "QA findings detected"
            body = (
                f"QA found {qa_issues} issue(s). Start with QA / Events, then use Heatmaps to see whether "
                "the problem is local or systemic across runs."
            )
            tone = "warn" if qa_issues < 10 else "alert"
        elif len(runs) >= 3 and len(sigs) >= 3:
            title = "Ready for multivariate"
            body = (
                f"{len(runs)} runs and {len(sigs)} signals are selected in table {table}. "
                "Multivariate view should now separate clusters, sparse clouds and outliers clearly."
            )
            tone = "ok"

        if (not runs) or len(runs) < 2 or (not sigs):
            if analysis_mode == "one_to_all":
                body = (
                    f"{body} Setup for 1 -> all: aim for 3+ runs, keep one candidate driver in mind and select 2+ signals "
                    "so Influence(t) can show how one parameter fans out into many responses."
                )
            elif analysis_mode == "all_to_one":
                body = (
                    f"{body} Setup for all -> 1: aim for 3+ runs and narrow the target to 1-2 signals, then explain one waveform "
                    "through many drivers and local event markers."
                )
            else:
                body = (
                    f"{body} Setup for all -> all: aim for 3+ runs and 3+ signals so melting clouds, sparse outliers and "
                    "pebbles-on-sand overlays become visually informative."
                )
            if follow_route_label:
                body = f"{body} First working route after setup: {follow_route_label}."

        if runs:
            if bool(events.get("no_signals_selected", False)):
                body = f"{body} Events are currently muted: pick one or more event channels to add local trigger evidence."
            elif event_focus:
                if analysis_mode == "one_to_all":
                    body = f"{body} Event anchor: {event_focus}. Check whether the current fan-out starts near that trigger."
                elif analysis_mode == "all_to_one":
                    body = f"{body} Event anchor: {event_focus}. Use it to test whether the target change is trigger-driven or only parameter-driven."
                else:
                    body = f"{body} Event anchor: {event_focus}. Compare it against cloud clusters and pebbles to see whether structure is event-driven."
            if story_label:
                title = f"Causal read ({story_confidence_title or 'Story'}): {story_label}" if story_confidence_title else f"Causal read: {story_label}"
                body = f"{body} Current causal story: {story_label}."
                if story_confidence:
                    body = f"{body} Story confidence: {story_confidence}."
                if str(causal_story.get('confidence_detail') or '').strip():
                    body = f"{body} {str(causal_story.get('confidence_detail') or '').strip()}"
                if str(causal_story.get('repair_hint') or '').strip():
                    body = f"{body} Main gap: {str(causal_story.get('repair_hint') or '').strip()}"
                if str(repair_summary.get("headline") or "").strip():
                    body = f"{body} {str(repair_summary.get('headline') or '').strip()}."
            if peak_bridge:
                body = (
                    f"{body} Peak bridge: {str(peak_bridge.get('headline') or '').strip()}. "
                    f"{str(peak_bridge.get('detail') or '').strip()}"
                )
            if dist_bridge:
                body = (
                    f"{body} Run-metrics bridge: {str(dist_bridge.get('headline') or '').strip()}. "
                    f"{str(dist_bridge.get('detail') or '').strip()}"
                )
            body = f"{body} Recommended route: {follow_route_label} because {focus_reason}."

        if notes:
            body = f"{body} Status: {', '.join(notes)}."
        if ref and ref != "auto":
            body = f"{body} Ref: {ref}."

        try:
            title_label.setText(title)
            body_label.setText(body)
        except Exception:
            pass
        self._set_workspace_assistant_tone(tone)

    def _insight_html_escape(self, value: object) -> str:
        try:
            return html.escape(str(value))
        except Exception:
            return ""

    def _workspace_insight_card_html(self, title: str, headline: str, detail: str, *, tone: str = "neutral") -> str:
        tone_map = {
            "ok": ("#edf8f2", "#94c8af", "#245746", "#174034"),
            "warn": ("#fff3de", "#dfbb74", "#7a5608", "#5e4104"),
            "alert": ("#fde7e3", "#d69c92", "#8c2f20", "#6a2217"),
            "accent": ("#e9f4f0", "#9bbeb1", "#2f5e53", "#22473f"),
            "neutral": ("#f8f1e5", "#d6c8af", "#6b624f", "#403a30"),
        }
        bg, border, accent, text = tone_map.get(str(tone), tone_map["neutral"])
        title_html = self._insight_html_escape(title)
        headline_html = self._insight_html_escape(headline)
        detail_html = self._insight_html_escape(detail).replace("\n", "<br/>")
        return (
            f"<div style='margin:0 0 8px 0; padding:10px 12px; "
            f"background:{bg}; border:1px solid {border}; border-left:4px solid {accent}; border-radius:10px;'>"
            f"<div style='font-size:10px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:{accent};'>{title_html}</div>"
            f"<div style='margin-top:3px; font-size:14px; font-weight:700; color:{text};'>{headline_html}</div>"
            f"<div style='margin-top:4px; font-size:11px; line-height:1.45; color:{text};'>{detail_html}</div>"
            f"</div>"
        )

    def _workspace_analysis_target_signal(self, valid_sigs: Optional[List[str]] = None) -> str:
        valid = [str(x) for x in (valid_sigs or []) if str(x).strip()]
        valid_set = set(valid)
        picked: List[str] = []
        try:
            picked = [str(x) for x in self._selected_signals()]
        except Exception:
            picked = []
        candidates: List[str] = []
        if len(picked) == 1:
            candidates.extend(picked)
        for cand in (
            getattr(self, "_infl_focus_sig", ""),
            getattr(self, "navigator_signal_selected", ""),
            str(self.combo_nav_signal.currentText() or "") if hasattr(self, "combo_nav_signal") else "",
            picked[0] if picked else "",
            valid[0] if valid else "",
        ):
            cand = str(cand or "").strip()
            if cand:
                candidates.append(cand)
        for cand in candidates:
            if cand and ((not valid_set) or (cand in valid_set)):
                return cand
        return valid[0] if valid else ""

    def _workspace_analysis_anchor_label(
        self,
        *,
        analysis_mode: Optional[str] = None,
        infl_lens: Optional[Dict[str, object]] = None,
        mv_lens: Optional[Dict[str, object]] = None,
    ) -> str:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        infl_lens = dict(infl_lens or self._workspace_influence_lens_summary() or {})
        mv_lens = dict(mv_lens or self._workspace_multivar_lens_summary() or {})

        if mode == "one_to_all":
            feat = str(infl_lens.get("fanout_feature") or "").strip()
            return f"Driver {feat}" if feat else "Driver —"

        if mode == "all_to_one":
            target = str(infl_lens.get("target_signal") or self._workspace_analysis_target_signal() or "").strip()
            return f"Target {target}" if target else "Target —"

        if mode == "all_to_all":
            dims = [str(x) for x in (mv_lens.get("checked_dims") or []) if str(x).strip()]
            if len(dims) >= 3:
                return f"Cloud {'/'.join(dims[:3])}"
            feat = str(infl_lens.get("top_pair_feature") or "").strip()
            sig = str(infl_lens.get("top_pair_signal") or "").strip()
            if feat and sig:
                return f"Corr {feat}->{sig}"
            return "Cloud —"

        return "Anchor —"

    def _workspace_influence_lens_summary(self) -> Dict[str, object]:
        cache = getattr(self, "_infl_cache", None)
        if not isinstance(cache, dict):
            return {}
        feat_sel = [str(x) for x in (cache.get("feat_sel") or []) if str(x).strip()]
        sigs = [str(x) for x in (cache.get("sigs") or []) if str(x).strip()]
        C = np.asarray(cache.get("C_sel", np.asarray([])), dtype=float)
        if C.ndim != 2 or C.size == 0 or not feat_sel or not sigs:
            return {}
        n_feat = min(len(feat_sel), int(C.shape[0]))
        n_sig = min(len(sigs), int(C.shape[1]))
        if n_feat <= 0 or n_sig <= 0:
            return {}
        feat_sel = feat_sel[:n_feat]
        sigs = sigs[:n_sig]
        C = C[:n_feat, :n_sig]
        finite = np.isfinite(C)
        if not finite.any():
            return {}

        strong_thr = 0.45
        A = np.abs(C)
        A_nan = np.where(finite, A, np.nan)
        strong_mask = finite & (A >= strong_thr)

        row_counts = np.asarray([int(strong_mask[i].sum()) for i in range(n_feat)], dtype=int)
        row_mean = np.asarray(
            [
                float(np.nanmean(A_nan[i])) if np.isfinite(A_nan[i]).any() else float("nan")
                for i in range(n_feat)
            ],
            dtype=float,
        )
        row_max = np.asarray(
            [
                float(np.nanmax(A_nan[i])) if np.isfinite(A_nan[i]).any() else float("nan")
                for i in range(n_feat)
            ],
            dtype=float,
        )
        col_mean = np.asarray(
            [
                float(np.nanmean(A_nan[:, j])) if np.isfinite(A_nan[:, j]).any() else float("nan")
                for j in range(n_sig)
            ],
            dtype=float,
        )

        fanout_idx = max(
            range(n_feat),
            key=lambda i: (
                int(row_counts[i]),
                float(np.nan_to_num(row_mean[i], nan=-1.0)),
                float(np.nan_to_num(row_max[i], nan=-1.0)),
            ),
        )
        fanout_order = np.argsort(np.nan_to_num(A_nan[fanout_idx], nan=-1.0))[::-1]
        fanout_examples: List[Tuple[str, float]] = []
        for j in fanout_order[:3]:
            if not finite[fanout_idx, j]:
                continue
            fanout_examples.append((str(sigs[int(j)]), float(C[fanout_idx, int(j)])))

        target_sig = self._workspace_analysis_target_signal(sigs)
        if target_sig in sigs:
            target_idx = sigs.index(target_sig)
        else:
            target_idx = int(np.argmax(np.nan_to_num(col_mean, nan=-1.0))) if len(col_mean) else -1
            target_sig = str(sigs[target_idx]) if 0 <= target_idx < len(sigs) else ""
        target_examples: List[Tuple[str, float]] = []
        if 0 <= target_idx < n_sig:
            target_order = np.argsort(np.nan_to_num(A_nan[:, target_idx], nan=-1.0))[::-1]
            for i in target_order[:3]:
                if not finite[int(i), target_idx]:
                    continue
                target_examples.append((str(feat_sel[int(i)]), float(C[int(i), target_idx])))

        A_rank = np.nan_to_num(A_nan, nan=-1.0)
        k_top = int(np.argmax(A_rank))
        i_top, j_top = int(k_top // n_sig), int(k_top % n_sig)
        strong_links = int(strong_mask.sum())
        total_links = int(finite.sum())
        density = (float(strong_links) / float(total_links)) if total_links else 0.0

        return {
            "time_s": float(cache.get("t", 0.0) or 0.0),
            "runs": int(len(cache.get("runs") or [])),
            "signal_count": int(n_sig),
            "feature_count": int(n_feat),
            "strong_threshold": float(strong_thr),
            "strong_links": strong_links,
            "total_links": total_links,
            "density": float(density),
            "fanout_feature": str(feat_sel[fanout_idx]),
            "fanout_count": int(row_counts[fanout_idx]),
            "fanout_examples": fanout_examples,
            "target_signal": str(target_sig),
            "target_examples": target_examples,
            "top_pair_feature": str(feat_sel[i_top]) if 0 <= i_top < len(feat_sel) else "",
            "top_pair_signal": str(sigs[j_top]) if 0 <= j_top < len(sigs) else "",
            "top_pair_corr": float(C[i_top, j_top]) if C.size else float("nan"),
            "delta": bool(cache.get("use_delta", False)),
            "ref_label": str(cache.get("ref_label") or ""),
        }

    def _workspace_multivar_lens_summary(self) -> Dict[str, object]:
        dfp = getattr(self, "_mv_df_plot", None)
        if not isinstance(dfp, pd.DataFrame) or dfp.empty:
            return {}

        cols = [str(c) for c in dfp.columns if str(c) != "run"]
        if not cols:
            return {}

        checked_now: List[str] = []
        try:
            checked_now = [str(x) for x in self._mv_checked_dims() if str(x).strip()]
        except Exception:
            checked_now = []
        remembered_checked = [str(x) for x in (getattr(self, "_mv_checked_dims_selected", None) or []) if str(x).strip()]
        checked = [c for c in (checked_now or remembered_checked) if c in cols]
        if not checked:
            checked = cols[: min(6, len(cols))]

        keep_pct = 100
        try:
            keep_pct = int(self.slider_mv_keep.value())
        except Exception:
            keep_pct = 100
        keep_pct = max(1, min(100, keep_pct))

        keep_mode = str(self.combo_mv_keepmode.currentText() or "sparse-first") if hasattr(self, "combo_mv_keepmode") else "sparse-first"
        metric = str(self.combo_mv_metric.currentText() or "RMS") if hasattr(self, "combo_mv_metric") else "RMS"
        use_view = bool(self.chk_mv_use_view.isChecked()) if hasattr(self, "chk_mv_use_view") else False
        pebbles = bool(self.chk_mv_pebbles.isChecked()) if hasattr(self, "chk_mv_pebbles") else False
        peb_signal = str(
            getattr(self, "_mv_peb_sig_selected", "")
            or (self.combo_mv_peb_sig.currentText() if hasattr(self, "combo_mv_peb_sig") else "")
            or ""
        ).strip()
        peb_mode = str(self.combo_mv_peb_mode.currentText() or "occurred") if hasattr(self, "combo_mv_peb_mode") else "occurred"

        max_pts = int(len(dfp))
        try:
            max_pts = max(1, int(self.spin_mv_maxpts.value()))
        except Exception:
            max_pts = int(len(dfp))
        approx_after_keep = max(1, int(round(float(len(dfp)) * keep_pct / 100.0))) if len(dfp) else 0
        approx_cloud = min(int(len(dfp)), int(max_pts), int(approx_after_keep)) if len(dfp) else 0

        xcol = str(self.combo_mv_x.currentText() or "") if hasattr(self, "combo_mv_x") else ""
        ycol = str(self.combo_mv_y.currentText() or "") if hasattr(self, "combo_mv_y") else ""
        zcol = str(self.combo_mv_z.currentText() or "") if hasattr(self, "combo_mv_z") else ""
        c3 = str(self.combo_mv_color3d.currentText() or "") if hasattr(self, "combo_mv_color3d") else ""

        return {
            "runs": int(len(dfp)),
            "field_count": int(len(cols)),
            "checked_dims": checked,
            "checked_dim_count": int(len(checked)),
            "keep_pct": int(keep_pct),
            "keep_mode": keep_mode,
            "metric": metric,
            "use_view": bool(use_view),
            "pebbles": bool(pebbles),
            "peb_signal": peb_signal,
            "peb_mode": peb_mode,
            "max_pts": int(max_pts),
            "approx_cloud_points": int(approx_cloud),
            "x": xcol,
            "y": ycol,
            "z": zcol,
            "color3d": c3,
        }

    def _workspace_run_metrics_lens_summary(self) -> Dict[str, object]:
        cache = getattr(self, "_dist_cache", None)
        if not isinstance(cache, dict):
            return {}
        rows_raw = list(cache.get("rows") or [])
        parsed: List[Dict[str, object]] = []
        for rec in rows_raw:
            if not isinstance(rec, dict):
                continue
            run_label = str(rec.get("run") or "").strip()
            if not run_label:
                continue
            try:
                value = float(rec.get("value", np.nan))
            except Exception:
                value = float("nan")
            if not np.isfinite(value):
                continue
            parsed.append(
                {
                    "run": run_label,
                    "value": float(value),
                    "is_ref": bool(rec.get("is_ref", False)),
                }
            )
        if not parsed:
            return {}

        values = np.asarray([float(rec["value"]) for rec in parsed], dtype=float)
        if values.size <= 0 or not np.isfinite(values).any():
            return {}

        mean_value = float(np.nanmean(values))
        median_value = float(np.nanmedian(values))
        std_value = float(np.nanstd(values))
        min_value = float(np.nanmin(values))
        max_value = float(np.nanmax(values))
        spread_value = float(max_value - min_value)
        abs_scale = max(
            abs(median_value),
            abs(mean_value),
            float(np.nanmedian(np.abs(values))) if values.size else 0.0,
            1.0,
        )
        robust_scale = float(np.nanmedian(np.abs(values - median_value)) * 1.4826) if values.size else 0.0
        outlier_rec = max(parsed, key=lambda rec: abs(float(rec["value"]) - median_value))
        top_rec = max(parsed, key=lambda rec: float(rec["value"]))
        bottom_rec = min(parsed, key=lambda rec: float(rec["value"]))
        ref_rec = next((dict(rec) for rec in parsed if bool(rec.get("is_ref", False))), None)
        outlier_gap = abs(float(outlier_rec["value"]) - median_value)
        mixed_sign = bool(min_value < 0.0 < max_value)
        outlier_driven = bool(
            len(parsed) >= 3 and outlier_gap >= max(std_value * 1.25, robust_scale * 1.5, max(abs_scale, 1.0) * 0.35)
        )
        wide_spread = bool(
            len(parsed) >= 3 and spread_value >= max(std_value * 1.6, max(abs_scale, 1.0) * 0.75)
        )
        metric_key = str(cache.get("metric_key") or "").strip()
        return {
            "signal": str(cache.get("signal") or "").strip(),
            "metric_key": metric_key,
            "metric_label": str(cache.get("metric_label") or "").strip(),
            "time_desc": str(cache.get("time_desc") or "").strip(),
            "table_name": str(cache.get("table_name") or "").strip(),
            "ref_label": str(cache.get("ref_label") or (ref_rec or {}).get("run") or "").strip(),
            "unit": str(cache.get("unit") or "").strip(),
            "runs": int(len(parsed)),
            "mean": float(mean_value),
            "median": float(median_value),
            "std": float(std_value),
            "min": float(min_value),
            "max": float(max_value),
            "spread": float(spread_value),
            "mixed_sign": bool(mixed_sign),
            "outlier_driven": bool(outlier_driven),
            "wide_spread": bool(wide_spread),
            "bridge_ready": bool(len(parsed) >= 3 and (mixed_sign or outlier_driven or wide_spread)),
            "top_run": str(top_rec.get("run") or ""),
            "top_value": float(top_rec.get("value", np.nan)),
            "bottom_run": str(bottom_rec.get("run") or ""),
            "bottom_value": float(bottom_rec.get("value", np.nan)),
            "outlier_run": str(outlier_rec.get("run") or ""),
            "outlier_value": float(outlier_rec.get("value", np.nan)),
            "outlier_gap": float(outlier_gap),
            "ref_run": str((ref_rec or {}).get("run") or ""),
            "ref_value": float((ref_rec or {}).get("value", np.nan)) if ref_rec is not None else float("nan"),
        }

    def _workspace_peak_heat_lens_summary(self) -> Dict[str, object]:
        cache = getattr(self, "_peak_cache", None)
        if not isinstance(cache, dict):
            return {}
        run_labels = [str(x) for x in (cache.get("runs") or []) if str(x).strip()]
        sig_labels = [str(x) for x in (cache.get("signals") or []) if str(x).strip()]
        values = np.asarray(cache.get("values", np.asarray([])), dtype=float)
        times = np.asarray(cache.get("times", np.asarray([])), dtype=float)
        if values.ndim != 2 or values.shape[0] != len(sig_labels) or values.shape[1] != len(run_labels):
            return {}
        if len(run_labels) < 2 or len(sig_labels) < 1:
            return {}
        nonref = np.asarray(values[:, 1:], dtype=float) if values.shape[1] > 1 else np.asarray([], dtype=float)
        if nonref.size <= 0 or not np.isfinite(nonref).any():
            return {}
        hotspot = dict(getattr(self, "_insight_peak_heat", {}) or {})
        abs_nonref = np.where(np.isfinite(nonref), nonref, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            row_max = np.nanmax(abs_nonref, axis=1) if abs_nonref.ndim == 2 else np.asarray([], dtype=float)
            col_max = np.nanmax(abs_nonref, axis=0) if abs_nonref.ndim == 2 else np.asarray([], dtype=float)
        hotspot_peak = float(hotspot.get("peak", np.nan))
        if not np.isfinite(hotspot_peak) or hotspot_peak <= 0.0:
            hotspot_peak = float(np.nanmax(abs_nonref))
        dominant_signal = ""
        dominant_run = ""
        if row_max.size:
            try:
                dominant_signal = str(sig_labels[int(np.nanargmax(row_max))])
            except Exception:
                dominant_signal = ""
        if col_max.size:
            try:
                dominant_run = str(run_labels[int(np.nanargmax(col_max)) + 1])
            except Exception:
                dominant_run = ""
        signal_competition = 0
        run_competition = 0
        threshold = float(hotspot_peak * 0.7) if np.isfinite(hotspot_peak) and hotspot_peak > 0.0 else float("nan")
        if np.isfinite(threshold):
            try:
                signal_competition = int(np.sum(np.isfinite(row_max) & (row_max >= threshold)))
            except Exception:
                signal_competition = 0
            try:
                run_competition = int(np.sum(np.isfinite(col_max) & (col_max >= threshold)))
            except Exception:
                run_competition = 0
        hotspot_signal = str(hotspot.get("signal") or dominant_signal or "").strip()
        hotspot_run = str(hotspot.get("run") or dominant_run or "").strip()
        hotspot_time = float(hotspot.get("time_s", np.nan))
        if (not np.isfinite(hotspot_time)) and hotspot_signal and hotspot_run:
            try:
                row = sig_labels.index(hotspot_signal)
                col = run_labels.index(hotspot_run)
                hotspot_time = float(times[row, col])
            except Exception:
                hotspot_time = float("nan")
        return {
            "signal_count": int(len(sig_labels)),
            "run_count": int(len(run_labels)),
            "ref_label": str(cache.get("ref_label") or (run_labels[0] if run_labels else "")).strip(),
            "table_name": str(cache.get("table_name") or "").strip(),
            "hotspot_signal": hotspot_signal,
            "hotspot_run": hotspot_run,
            "hotspot_time": float(hotspot_time) if np.isfinite(hotspot_time) else float("nan"),
            "hotspot_peak": float(hotspot_peak) if np.isfinite(hotspot_peak) else float("nan"),
            "hotspot_unit": str(hotspot.get("unit") or "").strip(),
            "dominant_signal": dominant_signal,
            "dominant_run": dominant_run,
            "signal_competition": int(signal_competition),
            "run_competition": int(run_competition),
            "bridge_ready": bool(len(sig_labels) >= 2 and len(run_labels) >= 3),
        }

    def _workspace_peak_heat_bridge_summary(
        self,
        *,
        analysis_mode: Optional[str] = None,
        sigs: Optional[List[str]] = None,
        infl_lens: Optional[Dict[str, object]] = None,
        peak_lens: Optional[Dict[str, object]] = None,
        causal_story: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if mode not in {"one_to_all", "all_to_one"}:
            return {}
        peak = dict(peak_lens if peak_lens is not None else self._workspace_peak_heat_lens_summary())
        if not peak or not bool(peak.get("bridge_ready", False)):
            return {}
        if sigs is None:
            try:
                sig_list = [str(x) for x in self._selected_signals() if str(x).strip()]
            except Exception:
                sig_list = []
        else:
            sig_list = [str(x) for x in (sigs or []) if str(x).strip()]
        if len(sig_list) < 2:
            return {}
        infl = dict(infl_lens if infl_lens is not None else self._workspace_influence_lens_summary())
        story = dict(causal_story or {})
        story_conf = str(story.get("confidence") or "").strip()
        repair_lane = str(story.get("repair_lane") or "").strip()
        repair_surface = str(story.get("repair_surface") or "").strip()
        if story_conf == "aligned":
            return {}
        if repair_lane == "qa":
            return {}
        hotspot_signal = str(peak.get("hotspot_signal") or "").strip()
        hotspot_run = str(peak.get("hotspot_run") or "").strip()
        hotspot_peak = float(peak.get("hotspot_peak", np.nan))
        hotspot_time = float(peak.get("hotspot_time", np.nan))
        signal_competition = int(peak.get("signal_competition", 0) or 0)
        run_competition = int(peak.get("run_competition", 0) or 0)
        target_signal = str(
            infl.get("target_signal")
            or self._workspace_analysis_target_signal(sig_list)
            or ""
        ).strip()
        headline = ""
        detail = ""
        tone = "accent"
        if mode == "one_to_all":
            if str(infl.get("fanout_feature") or "").strip() and signal_competition < 2 and story_conf == "partial" and repair_surface in {"delta", "influence_heatmap"}:
                return {}
            headline = "Coarse-gate the fan-out first"
            detail = (
                f"Peak |Δ| is dominated by {hotspot_signal or 'one response'} in {hotspot_run or 'one run'}"
                f"{f' @ {hotspot_time:.3f}s' if np.isfinite(hotspot_time) else ''}"
                f"{f' (|Δ|={hotspot_peak:.6g})' if np.isfinite(hotspot_peak) else ''}. "
                "Use the aggregate surface to decide which response lane deserves the next time-local heatmap pass."
            )
            if signal_competition >= 2:
                detail = f"{detail} Around {signal_competition} responses stay within the same peak band, so the fan-out is still crowded."
                tone = "warn"
        else:
            if not target_signal or (hotspot_signal and hotspot_signal == target_signal):
                return {}
            headline = "Check whether another response steals the global peak"
            detail = (
                f"The target is {target_signal}, but Peak |Δ| is currently led by {hotspot_signal or 'another response'}"
                f"{f' in {hotspot_run}' if hotspot_run else ''}"
                f"{f' @ {hotspot_time:.3f}s' if np.isfinite(hotspot_time) else ''}. "
                "Use the aggregate surface to see whether the target is truly primary or just one member of a broader split."
            )
            if run_competition >= 2:
                detail = f"{detail} The peak also spans multiple runs, so this is not just a single-run outlier."
            tone = "warn"
        return {
            "focus": "heatmaps",
            "focus_label": "Heatmaps",
            "dock_attr": "dock_peak_heatmap",
            "dock_label": "Peak |Δ|",
            "headline": headline,
            "detail": detail,
            "tone": tone,
            "signal": hotspot_signal,
            "run": hotspot_run,
        }

    def _workspace_run_metrics_bridge_summary(
        self,
        *,
        analysis_mode: Optional[str] = None,
        sigs: Optional[List[str]] = None,
        infl_lens: Optional[Dict[str, object]] = None,
        dist_lens: Optional[Dict[str, object]] = None,
        causal_story: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if mode not in {"one_to_all", "all_to_one"}:
            return {}
        dist = dict(dist_lens if dist_lens is not None else self._workspace_run_metrics_lens_summary())
        if not dist or int(dist.get("runs", 0) or 0) < 3:
            return {}

        if sigs is None:
            try:
                sig_list = [str(x) for x in self._selected_signals() if str(x).strip()]
            except Exception:
                sig_list = []
        else:
            sig_list = [str(x) for x in (sigs or []) if str(x).strip()]
        infl = dict(infl_lens if infl_lens is not None else self._workspace_influence_lens_summary())
        story = dict(causal_story or {})
        story_conf = str(story.get("confidence") or "").strip()
        repair_lane = str(story.get("repair_lane") or "").strip()
        repair_surface = str(story.get("repair_surface") or "").strip()
        if story_conf in {"aligned", "validate first"}:
            return {}
        if repair_lane in {"qa", "multivariate"}:
            return {}
        if story_conf == "partial" and repair_surface in {"delta", "influence_heatmap"}:
            return {}

        signal_name = str(dist.get("signal") or (sig_list[0] if sig_list else "")).strip()
        metric_label = str(dist.get("metric_label") or "run metric").strip()
        time_desc = str(dist.get("time_desc") or "").strip()
        outlier_run = str(dist.get("outlier_run") or "").strip()
        top_run = str(dist.get("top_run") or "").strip()
        outlier_value = float(dist.get("outlier_value", np.nan))
        median_value = float(dist.get("median", np.nan))
        ref_label = str(dist.get("ref_label") or dist.get("ref_run") or "").strip()
        mixed_sign = bool(dist.get("mixed_sign", False))
        outlier_driven = bool(dist.get("outlier_driven", False))
        wide_spread = bool(dist.get("wide_spread", False))
        metric_key = str(dist.get("metric_key") or "").strip()

        headline = ""
        detail = ""
        tone = "accent"

        if mode == "all_to_one":
            if len(sig_list) > 2:
                return {}
            if outlier_driven:
                headline = "Check whether the target is outlier-driven"
                detail = (
                    f"{outlier_run or top_run or 'One run'} is pulling {signal_name or 'the target'} "
                    f"to {outlier_value:.6g} while the median stays near {median_value:.6g} in {metric_label}. "
                    f"Use this ranking before trusting a single lead driver."
                )
                tone = "warn"
            elif mixed_sign and "delta" in metric_key:
                headline = "Check whether the target splits around the reference"
                detail = (
                    f"{signal_name or 'The target'} crosses both sides of the reference"
                    f"{f' {ref_label}' if ref_label else ''} in {metric_label}. "
                    "Use the scalar ranking to see whether this is a clean cohort split or just a noisy frame."
                )
            elif wide_spread or not list(infl.get("target_examples") or []):
                headline = "Quantify target spread first"
                detail = (
                    f"Use {metric_label} for {signal_name or 'the target'} to see whether the response is broad, skewed or ref-biased"
                    f"{f' ({time_desc})' if time_desc else ''} before ranking many drivers."
                )
            else:
                return {}
        else:
            if len(sig_list) > 2 and list(infl.get("fanout_examples") or []) and not (outlier_driven or wide_spread):
                return {}
            if outlier_driven:
                headline = "Check whether one response is run-dominated"
                detail = (
                    f"{signal_name or 'This response'} is being amplified mainly by {outlier_run or top_run or 'one run'} "
                    f"({outlier_value:.6g} in {metric_label}). Use Run metrics to see whether the fan-out is broad enough"
                    " across runs to justify a one-driver sweep."
                )
                tone = "warn"
            elif wide_spread or not str(infl.get("fanout_feature") or "").strip():
                headline = "Quantify response spread first"
                detail = (
                    f"Use {metric_label} for {signal_name or 'the current response'} to check whether the run spread is broad, split or reference-biased"
                    f"{f' ({time_desc})' if time_desc else ''} before sweeping one driver across many outputs."
                )
            else:
                return {}

        return {
            "focus": "heatmaps",
            "focus_label": "Heatmaps",
            "dock_attr": "dock_run_metrics",
            "dock_label": "Run metrics",
            "signal": signal_name,
            "metric_label": metric_label,
            "headline": headline,
            "detail": detail,
            "tone": tone,
        }

    def _workspace_next_move_summary(
        self,
        *,
        analysis_mode: str,
        runs: List[object],
        sigs: List[str],
        table: str,
        events_rows: int,
        trust_visible: bool,
        qa_issues: int,
        infl_lens: Dict[str, object],
        mv_lens: Dict[str, object],
        causal_story: Optional[Dict[str, object]] = None,
    ) -> Dict[str, str]:
        if trust_visible or qa_issues > 0:
            detail = (
                f"Pause exploration and validate the suspect zone in QA / Events first. "
                f"Then return to {self._workspace_analysis_label()} only after the anomaly is understood."
            )
            if qa_issues > 0:
                detail = f"{detail} Current QA issues: {qa_issues}."
            return {"headline": "Validate anomalies first", "detail": detail, "tone": "warn" if qa_issues < 10 else "alert"}

        story = dict(causal_story or {})
        story_conf = str(story.get("confidence") or "").strip()
        story_label = str(story.get("headline") or "").strip()
        repair_lane = str(story.get("repair_lane") or "").strip()
        repair_surface = str(story.get("repair_surface") or "").strip()
        repair_hint = str(story.get("repair_hint") or "").strip()
        surface_label = {
            "delta": "Δ(t)",
            "influence_heatmap": "Influence(t) Heatmap",
            "events": "Events",
            "qa": "QA",
            "multivariate": "Multivariate",
        }.get(repair_surface, "")
        current_dock_label = str(self._workspace_current_dock_label() or "").strip()

        def _route_surface_detail(detail: str, target_label: str) -> str:
            target = str(target_label or "").strip()
            if not target:
                return detail
            route = f"Open {target}"
            if current_dock_label and current_dock_label != target:
                route = f"From {current_dock_label}, open {target}"
            clean_detail = str(detail or "").strip()
            if not clean_detail:
                return route
            return f"{route} and {clean_detail[0].lower()}{clean_detail[1:]}"

        peak_bridge = self._workspace_peak_heat_bridge_summary(
            analysis_mode=analysis_mode,
            sigs=sigs,
            infl_lens=infl_lens,
            causal_story=story,
        )
        if peak_bridge:
            detail = _route_surface_detail(
                str(peak_bridge.get("detail") or "").strip(),
                str(peak_bridge.get("dock_label") or "Peak |Δ|"),
            )
            return {
                "headline": str(peak_bridge.get("headline") or "Coarse-gate the response field first"),
                "detail": detail,
                "tone": str(peak_bridge.get("tone") or "accent"),
            }

        dist_bridge = self._workspace_run_metrics_bridge_summary(
            analysis_mode=analysis_mode,
            sigs=sigs,
            infl_lens=infl_lens,
            causal_story=story,
        )
        if dist_bridge:
            detail = _route_surface_detail(
                str(dist_bridge.get("detail") or "").strip(),
                str(dist_bridge.get("dock_label") or "Run metrics"),
            )
            return {
                "headline": str(dist_bridge.get("headline") or "Quantify run spread first"),
                "detail": detail,
                "tone": str(dist_bridge.get("tone") or "accent"),
            }

        if story_conf == "aligned":
            if analysis_mode == "one_to_all":
                detail = f"The current chain {story_label or 'driver -> responses'} is aligned. Sweep nearby times and confirm that the same fan-out survives outside the hotspot window."
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Stress-test the aligned fan-out",
                    "detail": detail,
                    "tone": "ok",
                }
            if analysis_mode == "all_to_one":
                detail = f"The chain {story_label or 'driver -> target'} is aligned. Keep the target fixed and check whether it survives adjacent frames and event windows."
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Stress-test the aligned target chain",
                    "detail": detail,
                    "tone": "ok",
                }
            if analysis_mode == "all_to_all":
                detail = f"The field chain {story_label or 'corridor'} is aligned. Now test whether it stays dominant inside each visual cluster instead of only globally."
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Stress-test the aligned corridor",
                    "detail": detail,
                    "tone": "ok",
                }
        if story_conf == "partial":
            if repair_lane == "qa":
                detail = (
                    f"The chain {story_label or 'story'} is only partially aligned because its evidence link is weak. "
                    f"{repair_hint or 'Use QA / Events to restore the missing local trigger support.'}"
                )
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Repair the event anchor",
                    "detail": detail,
                    "tone": "warn",
                }
            if repair_lane == "heatmaps":
                detail = (
                    f"The chain {story_label or 'story'} is only partially aligned in time. "
                    f"{repair_hint or 'Use Heatmaps to lock the hotspot onto the active response or target.'}"
                )
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Repair the time-local link",
                    "detail": detail,
                    "tone": "warn",
                }
            if repair_lane == "multivariate":
                detail = (
                    f"The field story {story_label or 'corridor'} is only partially aligned structurally. "
                    f"{repair_hint or 'Use Multivariate to test whether the corridor survives inside the cloud clusters.'}"
                )
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Repair the field structure",
                    "detail": detail,
                    "tone": "warn",
                }
            if analysis_mode in {"one_to_all", "all_to_one"}:
                return {
                    "headline": "Repair the missing link",
                    "detail": f"The current chain {story_label or 'story'} is only partially aligned. Use QA / Events to find which timing or waveform segment is breaking the explanation.",
                    "tone": "warn",
                }
            if analysis_mode == "all_to_all":
                return {
                    "headline": "Localize the weak corridor link",
                    "detail": f"The field story {story_label or 'corridor'} is only partially aligned. Jump to Heatmaps and locate where the corridor and hotspot stop agreeing.",
                    "tone": "warn",
                }
        if story_conf == "tentative":
            if repair_lane == "qa":
                detail = (
                    f"The current chain {story_label or 'story'} is still tentative because its trigger evidence is thin. "
                    f"{repair_hint or 'Use QA / Events to anchor the candidate chain before drilling deeper.'}"
                )
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Rebuild evidence support",
                    "detail": detail,
                    "tone": "accent",
                }
            if repair_lane == "heatmaps":
                detail = (
                    f"The current chain {story_label or 'story'} is still tentative in time. "
                    f"{repair_hint or 'Use Heatmaps to find a stable hotspot before trusting the driver ranking.'}"
                )
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Stabilize the time gate",
                    "detail": detail,
                    "tone": "accent",
                }
            if repair_lane == "multivariate":
                detail = (
                    f"The current field story {story_label or 'corridor'} is still tentative structurally. "
                    f"{repair_hint or 'Use Multivariate to build a stronger cloud separation before trusting the corridor.'}"
                )
                if surface_label:
                    detail = _route_surface_detail(detail, surface_label)
                return {
                    "headline": "Strengthen the field structure",
                    "detail": detail,
                    "tone": "accent",
                }
            if analysis_mode in {"one_to_all", "all_to_one"}:
                return {
                    "headline": "Strengthen the causal chain",
                    "detail": "The current influence story is still tentative. Hold the selection stable and move through Heatmaps until hotspot, driver and event timing begin to lock together.",
                    "tone": "accent",
                }
            if analysis_mode == "all_to_all":
                return {
                    "headline": "Strengthen the field story",
                    "detail": "The current corridor is still tentative. Build more structure in Multivariate, then return to time-local heatmaps for confirmation.",
                    "tone": "accent",
                }

        if analysis_mode == "one_to_all":
            if infl_lens.get("fanout_feature"):
                examples = [str(sig) for sig, _corr in (infl_lens.get("fanout_examples", []) or [])[:2] if str(sig)]
                example_txt = f" Start with {', '.join(examples)}." if examples else ""
                return {
                    "headline": "Pin one driver, sweep many responses",
                    "detail": (
                        f"Hold {infl_lens.get('fanout_feature')} as the candidate driver at "
                        f"t={float(infl_lens.get('time_s', 0.0) or 0.0):.3f}s and compare how it fans out across the selected signals.{example_txt}"
                    ),
                    "tone": "ok",
                }
            return {
                "headline": "Build a driver sweep",
                "detail": (
                    f"Keep 3+ runs and at least 2 signals in table {table}, then move the playhead until one meta feature starts dominating Influence(t)."
                ),
                "tone": "accent",
            }

        if analysis_mode == "all_to_one":
            target_signal = str(infl_lens.get("target_signal") or (sigs[0] if sigs else "the target waveform"))
            if len(sigs) > 2:
                return {
                    "headline": "Narrow the target bundle",
                    "detail": f"Reduce the selection to 1-2 signals so {target_signal} can be explained cleanly by many drivers instead of a mixed target bundle.",
                    "tone": "accent",
                }
            if infl_lens.get("target_examples"):
                first_feat, first_corr = (infl_lens.get("target_examples") or [("", 0.0)])[0]
                return {
                    "headline": "Test the lead explanation",
                    "detail": (
                        f"Keep {target_signal} as the outcome and verify whether {first_feat} ({float(first_corr):+.2f}) still leads after you cross-check Events and Delta around the current playhead."
                    ),
                    "tone": "ok",
                }
            return {
                "headline": "Stabilize one target",
                "detail": f"Keep one target signal visible, move the playhead to a sharp local change, then let Influence(t) rank many drivers against {target_signal}.",
                "tone": "accent",
            }

        if analysis_mode == "all_to_all":
            if not mv_lens:
                return {
                    "headline": "Build the multivariate field",
                    "detail": "Select 3+ runs and 3+ signals so the window can derive enough fields for SPLOM, Parallel and 3D cloud scouting.",
                    "tone": "neutral",
                }
            checked_dim_count = int(mv_lens.get("checked_dim_count", 0) or 0)
            if checked_dim_count < 3:
                return {
                    "headline": "Add dimensions before scouting",
                    "detail": f"Check 1-2 more dimensions in Multivariate. With only {checked_dim_count} active fields the cloud will flatten instead of separating regimes.",
                    "tone": "accent",
                }
            keep_pct = int(mv_lens.get("keep_pct", 100) or 100)
            keep_mode = str(mv_lens.get("keep_mode") or "sparse-first")
            if keep_pct <= 15 and int(mv_lens.get("runs", 0) or 0) >= 4:
                return {
                    "headline": "Decide between outliers and cores",
                    "detail": (
                        f"Keep is only {keep_pct}%. Stay in {keep_mode} if you are hunting rare outliers; otherwise raise keep% or switch mode to expose regime cores before clustering by eye."
                    ),
                    "tone": "warn",
                }
            pebbles = bool(mv_lens.get("pebbles", False))
            peb_signal = str(mv_lens.get("peb_signal", "") or "")
            if pebbles and not peb_signal:
                return {
                    "headline": "Anchor the sand with events",
                    "detail": "Pebbles are enabled but not tied to a discrete event. Pick an event signal so cluster boundaries can be checked against real trigger structure.",
                    "tone": "accent",
                }
            if (not pebbles) and events_rows > 0:
                return {
                    "headline": "Turn events into pebbles",
                    "detail": "Event rows are available. Enable pebbles and bind them to a discrete signal to see whether cloud separation is structural or event-driven.",
                    "tone": "accent",
                }
            if infl_lens.get("top_pair_feature") and infl_lens.get("top_pair_signal"):
                return {
                    "headline": "Cross-check the dominant corridor",
                    "detail": (
                        f"Use the cloud to separate regimes, then verify whether {infl_lens.get('top_pair_feature')} -> {infl_lens.get('top_pair_signal')} remains dominant inside each visual cluster."
                    ),
                    "tone": "ok",
                }
            return {
                "headline": "Scout clusters, then localize time",
                "detail": "Use SPLOM / 3D to split the field into regimes, then jump back to Heatmaps to see where each visual cluster separates in time.",
                "tone": "ok",
            }

        return {
            "headline": "Move from overview to evidence",
            "detail": "Use the current lens to find a promising hotspot or cluster, then validate it with Heatmaps, QA and Events before trusting the pattern.",
            "tone": "accent",
        }

    def _workspace_causal_story_summary(
        self,
        *,
        analysis_mode: str,
        heat: Dict[str, object],
        infl: Dict[str, object],
        infl_lens: Dict[str, object],
        events: Dict[str, object],
        trust_visible: bool,
        qa_issues: int,
    ) -> Dict[str, str]:
        def _time_close(a: float, b: float, tol_s: float = 0.35) -> bool:
            try:
                return bool(np.isfinite(a) and np.isfinite(b) and abs(float(a) - float(b)) <= float(tol_s))
            except Exception:
                return False

        if trust_visible or qa_issues > 0:
            return {
                "headline": "Candidate chain needs validation",
                "detail": (
                    "QA / trust warnings are active, so treat any influence chain as provisional until the suspect zone is checked."
                ),
                "tone": "warn" if qa_issues < 10 else "alert",
                "confidence": "validate first",
                "confidence_detail": "The data-quality layer is warning before the influence story is fully trusted.",
                "repair_hint": "Resolve the trust / QA warnings first, then rebuild the causal story on the cleaned evidence.",
                "repair_lane": "qa",
                "repair_surface": "qa",
            }

        heat_sig = str(heat.get("signal") or "").strip()
        heat_run = str(heat.get("run") or "").strip()
        heat_time = float(heat.get("time_s", np.nan))
        heat_peak = float(heat.get("peak", np.nan))
        event_sig = str(events.get("top_signal") or events.get("sample_signal") or "").strip()
        event_time = float(events.get("sample_time_s", np.nan))
        infl_time = float(infl_lens.get("time_s", infl.get("time_s", np.nan)))
        infl_time_txt = f" @ {infl_time:.3f}s" if np.isfinite(infl_time) else ""

        if analysis_mode == "one_to_all":
            driver = str(infl_lens.get("fanout_feature") or infl.get("feature") or "").strip()
            fanout_examples = [str(sig) for sig, _corr in (infl_lens.get("fanout_examples", []) or []) if str(sig).strip()]
            response = heat_sig or (fanout_examples[0] if fanout_examples else "")
            if driver and response:
                chain = f"{driver} -> {response}"
                if event_sig:
                    chain = f"{event_sig} -> {chain}"
                align_score = 0
                response_in_fanout = bool(response and response in fanout_examples)
                fanout_multi = bool(int(infl_lens.get("fanout_count", 0) or 0) >= 2)
                event_aligned = bool(
                    event_sig
                    and np.isfinite(event_time)
                    and (_time_close(event_time, heat_time) or _time_close(event_time, infl_time))
                )
                detail = (
                    f"Best current story: {driver} is the fan-out candidate, while the strongest visible response is "
                    f"{response}{f' in {heat_run}' if heat_run else ''}"
                )
                if np.isfinite(heat_time):
                    detail = f"{detail} @ {heat_time:.3f}s"
                if np.isfinite(heat_peak):
                    detail = f"{detail} with peak {heat_peak:.3g}"
                detail = f"{detail}."
                if response_in_fanout:
                    align_score += 1
                    detail = f"{detail} The hotspot signal is already inside the top fan-out responses."
                if fanout_multi:
                    align_score += 1
                if event_sig:
                    if np.isfinite(event_time) and np.isfinite(heat_time):
                        detail = f"{detail} Event anchor {event_sig} sits at {event_time:.3f}s, so check whether it gates that spread."
                        if event_aligned:
                            align_score += 1
                    else:
                        detail = f"{detail} Event anchor {event_sig} can be used as the gate for this spread."
                confidence = "aligned" if align_score >= 3 else ("partial" if align_score >= 2 else "tentative")
                confidence_detail = {
                    "aligned": "Driver ranking, hotspot response and event timing all point in the same direction.",
                    "partial": "Two parts of the chain agree, but one link still needs a closer check.",
                    "tentative": "The chain is plausible, but it is still resting on incomplete agreement.",
                }[confidence]
                if confidence == "aligned":
                    repair_hint = "Sweep a few nearby frames and confirm that the same response set stays inside the fan-out."
                    repair_lane = "heatmaps"
                    repair_surface = "influence_heatmap"
                elif confidence == "partial":
                    if not response_in_fanout:
                        repair_hint = "The hotspot response is outside the top fan-out set, so re-check the local frame or response selection."
                        repair_lane = "heatmaps"
                        repair_surface = "delta"
                    elif event_sig and not event_aligned:
                        repair_hint = "The fan-out is visible, but event timing is not yet locking the spread; inspect nearby Events and Delta frames."
                        repair_lane = "qa"
                        repair_surface = "events"
                    else:
                        repair_hint = "One link in the spread is still weak, so keep the driver fixed and verify the local gate."
                        repair_lane = "heatmaps"
                        repair_surface = "delta"
                else:
                    repair_hint = "Hold one driver steady and step through time until the hotspot response and event gate begin to agree."
                    repair_lane = "heatmaps"
                    repair_surface = "delta"
                return {
                    "headline": chain,
                    "detail": detail,
                    "tone": "ok" if confidence == "aligned" else "accent",
                    "confidence": confidence,
                    "confidence_detail": confidence_detail,
                    "repair_hint": repair_hint,
                    "repair_lane": repair_lane,
                    "repair_surface": repair_surface,
                }

        if analysis_mode == "all_to_one":
            target = str(infl_lens.get("target_signal") or infl.get("signal") or heat_sig or "").strip()
            lead_examples = infl_lens.get("target_examples", []) or []
            lead_driver = str(lead_examples[0][0] if lead_examples else (infl.get("feature") or "")).strip()
            if target and lead_driver:
                chain = f"{lead_driver} -> {target}"
                if event_sig:
                    chain = f"{event_sig} -> {chain}"
                align_score = 1 if lead_examples else 0
                target_match = bool(heat_sig and heat_sig == target)
                event_aligned = bool(
                    event_sig
                    and np.isfinite(event_time)
                    and (_time_close(event_time, heat_time) or _time_close(event_time, infl_time))
                )
                detail = f"Best current explanation is {lead_driver} driving {target}{infl_time_txt}."
                if heat_sig:
                    if target_match:
                        align_score += 1
                        detail = f"{detail} The heat hotspot is already on the target waveform"
                    else:
                        detail = f"{detail} The current heat hotspot is on {heat_sig}, so compare it against the target"
                    if heat_run:
                        detail = f"{detail} in {heat_run}"
                    if np.isfinite(heat_time):
                        detail = f"{detail} @ {heat_time:.3f}s"
                    detail = f"{detail}."
                if event_sig:
                    if np.isfinite(event_time):
                        detail = f"{detail} Event anchor {event_sig} @ {event_time:.3f}s is the local trigger check."
                        if event_aligned:
                            align_score += 1
                    else:
                        detail = f"{detail} Event anchor {event_sig} is the local trigger check."
                confidence = "aligned" if align_score >= 3 else ("partial" if align_score >= 2 else "tentative")
                confidence_detail = {
                    "aligned": "Driver ranking, target hotspot and local trigger all reinforce the same target explanation.",
                    "partial": "The target explanation is promising, but one part of the chain is still weakly aligned.",
                    "tentative": "The target explanation exists, but the supporting pieces have not fully locked together yet.",
                }[confidence]
                if confidence == "aligned":
                    repair_hint = "Move a few frames around the target and confirm that the same lead driver keeps winning."
                    repair_lane = "heatmaps"
                    repair_surface = "influence_heatmap"
                elif confidence == "partial":
                    if not target_match and heat_sig:
                        repair_hint = "The heat hotspot is still off-target, so move Delta onto the target waveform before trusting the chain."
                        repair_lane = "heatmaps"
                        repair_surface = "delta"
                    elif event_sig and not event_aligned:
                        repair_hint = "Driver and target agree, but event timing is still drifting; inspect Events around the current frame."
                        repair_lane = "qa"
                        repair_surface = "events"
                    else:
                        repair_hint = "The target chain is close, but one local confirmation is still missing."
                        repair_lane = "heatmaps"
                        repair_surface = "delta"
                else:
                    repair_hint = "Narrow the target, hold the playhead steady and wait until hotspot, driver and event timing start to lock together."
                    repair_lane = "heatmaps"
                    repair_surface = "delta"
                return {
                    "headline": chain,
                    "detail": detail,
                    "tone": "ok" if confidence == "aligned" else "accent",
                    "confidence": confidence,
                    "confidence_detail": confidence_detail,
                    "repair_hint": repair_hint,
                    "repair_lane": repair_lane,
                    "repair_surface": repair_surface,
                }

        corridor_feat = str(infl_lens.get("top_pair_feature") or infl.get("feature") or "").strip()
        corridor_sig = str(infl_lens.get("top_pair_signal") or infl.get("signal") or heat_sig or "").strip()
        if corridor_feat and corridor_sig:
            chain = f"{corridor_feat} -> {corridor_sig}"
            if event_sig:
                chain = f"{event_sig} -> {chain}"
            align_score = 1
            corridor_matches_hotspot = bool(heat_sig and heat_sig == corridor_sig)
            event_aligned = bool(
                event_sig
                and np.isfinite(event_time)
                and (_time_close(event_time, heat_time) or _time_close(event_time, infl_time))
            )
            detail = f"Field story: dominant corridor is {corridor_feat} -> {corridor_sig}{infl_time_txt}."
            if heat_sig:
                detail = f"{detail} Current hotspot is {heat_sig}{f' in {heat_run}' if heat_run else ''}"
                if np.isfinite(heat_time):
                    detail = f"{detail} @ {heat_time:.3f}s"
                detail = f"{detail}, so use it as the time gate for this corridor."
                if corridor_matches_hotspot:
                    align_score += 1
            if event_sig:
                peb_signal = str(events.get("top_signal") or events.get("sample_signal") or "")
                detail = f"{detail} Event anchor {peb_signal} can act as the pebble check for whether the corridor is trigger-driven."
                if event_aligned:
                    align_score += 1
            confidence = "aligned" if align_score >= 3 else ("partial" if align_score >= 2 else "tentative")
            confidence_detail = {
                "aligned": "Corridor, hotspot gate and event anchor are mutually consistent.",
                "partial": "The field story has two supporting anchors, but one layer is still weaker than the others.",
                "tentative": "The corridor exists, but the time/event anchoring is still thin.",
            }[confidence]
            if confidence == "aligned":
                repair_hint = "Probe each cloud cluster and confirm that the same corridor survives inside the local structure."
                repair_lane = "multivariate"
                repair_surface = "multivariate"
            elif confidence == "partial":
                if not corridor_matches_hotspot and heat_sig:
                    repair_hint = "The dominant corridor and Delta hotspot disagree on the active response, so localize the split in Heatmaps."
                    repair_lane = "heatmaps"
                    repair_surface = "delta"
                elif event_sig and not event_aligned:
                    repair_hint = "The corridor is visible, but event timing is not anchoring it yet; compare against pebbles or nearby Events."
                    repair_lane = "multivariate"
                    repair_surface = "multivariate"
                else:
                    repair_hint = "One field anchor is still weaker than the others, so keep cross-checking time-local heatmaps against the cloud."
                    repair_lane = "heatmaps"
                    repair_surface = "delta"
            else:
                repair_hint = "Add stronger time or event anchoring before trusting the cloud corridor as a real field pattern."
                repair_lane = "multivariate"
                repair_surface = "multivariate"
            return {
                "headline": chain,
                "detail": detail,
                "tone": "ok" if confidence == "aligned" else "accent",
                "confidence": confidence,
                "confidence_detail": confidence_detail,
                "repair_hint": repair_hint,
                "repair_lane": repair_lane,
                "repair_surface": repair_surface,
            }

        return {
            "headline": "Causal story is still thin",
            "detail": "Keep Heatmaps, Influence and Events stable for a moment so the window can propose a stronger influence chain.",
            "tone": "neutral",
            "confidence": "tentative",
            "confidence_detail": "There is not enough agreement yet between the available evidence layers.",
            "repair_hint": "Stabilize one frame and one target or corridor before asking the window for a stronger causal story.",
            "repair_lane": "multivariate" if analysis_mode == "all_to_all" else "heatmaps",
            "repair_surface": "multivariate" if analysis_mode == "all_to_all" else "delta",
        }

    def _workspace_causal_story_label(self, causal_story: Optional[Dict[str, object]] = None) -> str:
        story = dict(causal_story or {})
        headline = str(story.get("headline") or "").strip()
        if not headline or headline in {"Causal story is still thin", "Candidate chain needs validation"}:
            return ""
        if len(headline) > 44:
            headline = f"{headline[:41]}..."
        return headline

    def _workspace_repair_lane_summary(
        self,
        *,
        causal_story: Optional[Dict[str, object]] = None,
        analysis_mode: Optional[str] = None,
    ) -> Dict[str, str]:
        story = dict(causal_story or {})
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        lane = str(story.get("repair_lane") or "").strip()
        confidence = str(story.get("confidence") or "").strip()
        hint = str(story.get("repair_hint") or "").strip()
        if lane not in {"heatmaps", "qa", "multivariate"}:
            lane = "multivariate" if mode == "all_to_all" else "heatmaps"

        lane_titles = {
            "heatmaps": "time-local alignment",
            "qa": "event / evidence support",
            "multivariate": "field structure",
        }
        lane_status = {
            "heatmaps": "time gate",
            "qa": "event evidence",
            "multivariate": "field structure",
        }
        lane_title = lane_titles.get(lane, lane)
        status_label = lane_status.get(lane, lane)

        if confidence == "validate first":
            return {
                "headline": "Weakest link: trust / QA",
                "detail": hint or "Resolve trust or QA warnings before relying on the causal story.",
                "tone": "alert",
                "status_label": "trust / QA",
            }
        if confidence == "aligned":
            return {
                "headline": f"Validation lane: {lane_title}",
                "detail": hint or "The chain is aligned; use this lane to stress-test it rather than to repair it.",
                "tone": "ok",
                "status_label": status_label,
            }
        return {
            "headline": f"Weakest link: {lane_title}",
            "detail": hint or f"Use {lane_title} as the primary repair lane for the current causal story.",
            "tone": "warn" if confidence == "partial" else "accent",
            "status_label": status_label,
        }

    def _workspace_follow_target_summary(
        self,
        *,
        analysis_mode: Optional[str] = None,
        trust_visible: Optional[bool] = None,
        qa_issues: Optional[int] = None,
        events_rows: Optional[int] = None,
        events_insight: Optional[Dict[str, object]] = None,
        causal_story: Optional[Dict[str, object]] = None,
    ) -> Dict[str, str]:
        mode = str(analysis_mode or getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        trust_flag = bool(
            trust_visible if trust_visible is not None else (
                getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible()
            )
        )
        qa_count = int(
            qa_issues if qa_issues is not None else int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        )
        events = dict(events_insight if events_insight is not None else (getattr(self, "_insight_events", {}) or {}))
        rows = int(events_rows if events_rows is not None else int(events.get("rows", 0) or 0))
        story = dict(causal_story or {})
        focus = str(
            self._workspace_contextual_focus_recommendation(
                analysis_mode=mode,
                trust_visible=trust_flag,
                qa_issues=qa_count,
                events_rows=rows,
                events_insight=events,
                causal_story=story,
            ) or "all"
        )
        focus_label_map = {
            "all": "Overview",
            "heatmaps": "Heatmaps",
            "multivariate": "Multivar",
            "qa": "QA / Events",
        }
        focus_label = focus_label_map.get(focus, focus)
        repair_lane = str(story.get("repair_lane") or "").strip()
        repair_surface = str(story.get("repair_surface") or "").strip()
        dock_attr = "dock_controls"
        dock_label = "Controls"
        dock_subtarget = ""
        if focus == "heatmaps":
            dock_attr = "dock_heatmap"
            dock_label = "Δ(t)"
            if repair_surface == "influence_heatmap":
                dock_attr = "dock_inflheat"
                dock_label = "Influence(t) Heatmap"
        elif focus == "multivariate":
            dock_attr = "dock_multivar"
            dock_label = "Multivariate"
        elif focus == "qa":
            dock_attr = "dock_qa"
            dock_label = "QA"
            if trust_flag or qa_count > 0:
                dock_attr = "dock_qa"
                dock_label = "QA"
            elif repair_surface == "events":
                dock_attr = "dock_events"
                if len(list(self._selected_runs())) > 1 and int(rows or 0) > 0:
                    dock_label = self._events_dock_route_label("Runs raster")
                    dock_subtarget = "Runs raster"
                else:
                    dock_label = "Events"
            elif repair_lane == "qa" and int(rows or 0) > 0:
                dock_attr = "dock_events"
                if len(list(self._selected_runs())) > 1:
                    dock_label = self._events_dock_route_label("Runs raster")
                    dock_subtarget = "Runs raster"
                else:
                    dock_label = "Events"
        if focus == "heatmaps":
            peak_bridge = self._workspace_peak_heat_bridge_summary(
                analysis_mode=mode,
                sigs=[str(x) for x in self._selected_signals() if str(x).strip()],
                infl_lens=self._workspace_influence_lens_summary(),
                causal_story=story,
            )
            if peak_bridge:
                dock_attr = str(peak_bridge.get("dock_attr") or dock_attr)
                dock_label = str(peak_bridge.get("dock_label") or dock_label)
            if not peak_bridge:
                dist_bridge = self._workspace_run_metrics_bridge_summary(
                    analysis_mode=mode,
                    infl_lens=self._workspace_influence_lens_summary(),
                    causal_story=story,
                )
                if dist_bridge:
                    dock_attr = str(dist_bridge.get("dock_attr") or dock_attr)
                    dock_label = str(dist_bridge.get("dock_label") or dock_label)
        return {
            "focus": focus,
            "focus_label": focus_label,
            "dock_attr": dock_attr,
            "dock_label": dock_label,
            "dock_subtarget": dock_subtarget,
        }

    def _update_workspace_insights(self) -> None:
        browser = getattr(self, "txt_workspace_insights", None)
        if browser is None:
            return

        runs = list(self._selected_runs()) if hasattr(self, "list_runs") else []
        sigs = list(self._selected_signals()) if hasattr(self, "list_signals") else []
        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        table = str(getattr(self, "current_table", "") or "-")

        events_rows = 0
        try:
            if getattr(self, "tbl_events", None) is not None:
                events_rows = int(self.tbl_events.rowCount())
        except Exception:
            events_rows = 0

        heat = dict(getattr(self, "_insight_heat", {}) or {})
        peak_heat = dict(getattr(self, "_insight_peak_heat", {}) or {})
        infl = dict(getattr(self, "_insight_infl", {}) or {})
        qa = dict(getattr(self, "_insight_qa", {}) or {})
        events = dict(getattr(self, "_insight_events", {}) or {})
        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        dist_lens = self._workspace_run_metrics_lens_summary()
        peak_lens = self._workspace_peak_heat_lens_summary()

        qa_issues = int(qa.get("issues", 0) or 0)
        qa_err = int(qa.get("err", 0) or 0)
        qa_warn = int(qa.get("warn", 0) or 0)
        qa_focus = ""
        if qa.get("top_signal") and qa.get("top_run"):
            try:
                qa_focus = (
                    f"Top suspect: {qa.get('top_signal')} in {qa.get('top_run')} "
                    f"@ {float(qa.get('top_time_s', 0.0) or 0.0):.3f}s."
                )
            except Exception:
                qa_focus = f"Top suspect: {qa.get('top_signal')} in {qa.get('top_run')}."

        events_focus = ""
        if events.get("top_signal") or events.get("sample_signal"):
            try:
                events_name = str(events.get("top_signal") or events.get("sample_signal") or "")
                events_time = float(events.get("sample_time_s", 0.0) or 0.0)
                if events_name and np.isfinite(events_time):
                    events_focus = f"{events_name} @ {events_time:.3f}s"
                else:
                    events_focus = events_name
            except Exception:
                events_focus = str(events.get("top_signal") or events.get("sample_signal") or "")

        causal_story = self._workspace_causal_story_summary(
            analysis_mode=analysis_mode,
            heat=heat,
            infl=infl,
            infl_lens=infl_lens,
            events=events,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        dist_bridge = self._workspace_run_metrics_bridge_summary(
            analysis_mode=analysis_mode,
            sigs=sigs,
            infl_lens=infl_lens,
            dist_lens=dist_lens,
            causal_story=causal_story,
        )
        peak_bridge = self._workspace_peak_heat_bridge_summary(
            analysis_mode=analysis_mode,
            sigs=sigs,
            infl_lens=infl_lens,
            peak_lens=peak_lens,
            causal_story=causal_story,
        )
        next_move = self._workspace_next_move_summary(
            analysis_mode=analysis_mode,
            runs=runs,
            sigs=sigs,
            table=table,
            events_rows=events_rows,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            infl_lens=infl_lens,
            mv_lens=mv_lens,
            causal_story=causal_story,
        )
        recommended_focus = self._workspace_contextual_focus_recommendation(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        focus_labels = {
            "all": "all",
            "heatmaps": "heatmaps",
            "multivariate": "multivar",
            "qa": "qa/events",
        }
        recommended_focus_label = focus_labels.get(str(recommended_focus), str(recommended_focus or "all"))
        focus_reason = self._workspace_contextual_focus_reason(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        story_confidence = str(causal_story.get("confidence") or "").strip()
        story_confidence_title = story_confidence.title() if story_confidence else ""
        repair_summary = self._workspace_repair_lane_summary(
            causal_story=causal_story,
            analysis_mode=analysis_mode,
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events,
            causal_story=causal_story,
        )
        follow_target_label = self._workspace_follow_target_label(follow_target, separator=": ", fallback="Overview")
        follow_route_label = self._workspace_route_label(follow_target, separator=": ", fallback="Overview")

        cards: List[str] = []

        lens_headline = "all -> all structure"
        lens_detail = (
            "Use multivariate clouds, melting density and pebbles to scout clusters, sparse outliers and cross-coupled regimes."
        )
        lens_tone = "accent"
        if analysis_mode == "one_to_all":
            lens_headline = "1 -> all driver sweep"
            lens_detail = (
                "Hold one candidate driver or hotspot fixed, then inspect how it fans out across many signals via Influence(t) and heatmaps."
            )
            lens_tone = "ok" if len(runs) >= 3 and len(sigs) >= 2 else "neutral"
        elif analysis_mode == "all_to_one":
            target_sig = str(sigs[0] if sigs else "")
            lens_headline = "all -> 1 target explanation"
            lens_detail = (
                f"Treat {target_sig or 'the current waveform'} as the outcome and rank many drivers against one response with local event support."
            )
            lens_tone = "ok" if len(runs) >= 3 and len(sigs) <= 2 and len(sigs) >= 1 else "neutral"
        elif len(runs) >= 3 and len(sigs) >= 3:
            lens_tone = "ok"
        cards.append(
            self._workspace_insight_card_html(
                "Analysis lens",
                lens_headline,
                lens_detail,
                tone=lens_tone,
            )
        )
        cards.append(
            self._workspace_insight_card_html(
                "Recommended focus",
                follow_route_label,
                f"Take this route now. Why now: {focus_reason}.",
                tone="warn" if recommended_focus == "qa" else ("ok" if recommended_focus == "multivariate" else "accent"),
            )
        )
        cards.append(
            self._workspace_insight_card_html(
                "Causal story",
                (
                    f"{story_confidence_title} | {str(causal_story.get('headline') or 'Causal story')}"
                    if story_confidence_title
                    else str(causal_story.get("headline") or "Causal story")
                ),
                (
                    f"Confidence: {story_confidence}. {str(causal_story.get('confidence_detail') or '').strip()} "
                    f"{str(causal_story.get('detail') or '').strip()} "
                    f"{('Repair hint: ' + str(causal_story.get('repair_hint') or '').strip()) if str(causal_story.get('repair_hint') or '').strip() else ''}"
                ).strip(),
                tone=str(causal_story.get("tone") or "neutral"),
            )
        )
        cards.append(
            self._workspace_insight_card_html(
                "Weakest link",
                str(repair_summary.get("headline") or "Weakest link"),
                str(repair_summary.get("detail") or ""),
                tone=str(repair_summary.get("tone") or "accent"),
            )
        )

        if analysis_mode == "one_to_all" and infl_lens.get("fanout_feature"):
            examples = ", ".join(
                f"{sig} {corr:+.2f}" for sig, corr in infl_lens.get("fanout_examples", [])[:3]
            )
            detail = (
                f"{infl_lens.get('fanout_feature')} reaches {int(infl_lens.get('fanout_count', 0) or 0)}/"
                f"{int(infl_lens.get('signal_count', 0) or 0)} signals at |corr|≥"
                f"{float(infl_lens.get('strong_threshold', 0.45) or 0.45):.2f}. "
                f"t={float(infl_lens.get('time_s', 0.0) or 0.0):.3f}s."
            )
            if examples:
                detail = f"{detail} Strongest fan-out: {examples}."
            cards.append(
                self._workspace_insight_card_html(
                    "Driver fan-out",
                    f"{infl_lens.get('fanout_feature')} -> {int(infl_lens.get('fanout_count', 0) or 0)} signals",
                    detail,
                    tone="ok" if int(infl_lens.get("fanout_count", 0) or 0) >= 2 else "accent",
                )
            )
        elif analysis_mode == "all_to_one" and infl_lens.get("target_signal"):
            examples = ", ".join(
                f"{feat} {corr:+.2f}" for feat, corr in infl_lens.get("target_examples", [])[:3]
            )
            detail = (
                f"Target signal {infl_lens.get('target_signal')} is ranked against "
                f"{int(infl_lens.get('feature_count', 0) or 0)} meta drivers at "
                f"t={float(infl_lens.get('time_s', 0.0) or 0.0):.3f}s."
            )
            if examples:
                detail = f"{detail} Top drivers: {examples}."
            cards.append(
                self._workspace_insight_card_html(
                    "Target drivers",
                    str(infl_lens.get("target_signal") or "Target signal"),
                    detail,
                    tone="ok" if len(infl_lens.get("target_examples", []) or []) >= 2 else "accent",
                )
            )
        elif analysis_mode == "all_to_all" and infl_lens.get("top_pair_feature"):
            detail = (
                f"Strong links: {int(infl_lens.get('strong_links', 0) or 0)}/"
                f"{int(infl_lens.get('total_links', 0) or 0)} "
                f"({100.0 * float(infl_lens.get('density', 0.0) or 0.0):.0f}% dense) at "
                f"t={float(infl_lens.get('time_s', 0.0) or 0.0):.3f}s. "
                f"Dominant corridor: {infl_lens.get('top_pair_feature')} -> {infl_lens.get('top_pair_signal')} "
                f"({float(infl_lens.get('top_pair_corr', 0.0) or 0.0):+.2f})."
            )
            cards.append(
                self._workspace_insight_card_html(
                    "Coupling field",
                    f"{int(infl_lens.get('strong_links', 0) or 0)} strong links in play",
                    detail,
                    tone="ok" if float(infl_lens.get("density", 0.0) or 0.0) >= 0.25 else "accent",
                )
            )

        if analysis_mode == "all_to_all":
            if mv_lens:
                keep_mode = str(mv_lens.get("keep_mode") or "sparse-first")
                keep_focus = (
                    "preserving sparse contours and outliers"
                    if keep_mode == "sparse-first"
                    else "preserving dense regime cores"
                )
                peb_signal = str(mv_lens.get("peb_signal") or "")
                pebbles = bool(mv_lens.get("pebbles", False))
                if pebbles and peb_signal:
                    pebbles_text = f"Pebbles pin event structure from {peb_signal} ({mv_lens.get('peb_mode', 'occurred')})."
                elif pebbles:
                    pebbles_text = "Pebbles are on, but pick a discrete signal so event grains can separate clusters."
                else:
                    pebbles_text = "Pebbles are off, so the view is showing only cloud geometry."
                dims_preview = ", ".join([str(x) for x in mv_lens.get("checked_dims", [])[:4]])
                if int(mv_lens.get("runs", 0) or 0) < 3:
                    mv_headline = "Need more runs for cloud scouting"
                    mv_tone = "neutral"
                elif int(mv_lens.get("checked_dim_count", 0) or 0) < 3:
                    mv_headline = "Need 3 checked dimensions"
                    mv_tone = "accent"
                elif int(mv_lens.get("keep_pct", 100) or 100) <= 15 and int(mv_lens.get("runs", 0) or 0) >= 4:
                    mv_headline = "Cloud is very thin"
                    mv_tone = "warn"
                else:
                    mv_headline = "Melting cloud ready"
                    mv_tone = "ok"
                mv_detail = (
                    f"Fields={int(mv_lens.get('field_count', 0) or 0)}, checked={int(mv_lens.get('checked_dim_count', 0) or 0)}"
                    f" ({dims_preview or 'auto'}). Keep={int(mv_lens.get('keep_pct', 100) or 100)}% -> ~"
                    f"{int(mv_lens.get('approx_cloud_points', 0) or 0)}/{int(mv_lens.get('runs', 0) or 0)} points, "
                    f"{keep_mode} means {keep_focus}. 3D={mv_lens.get('x') or '—'}/{mv_lens.get('y') or '—'}/{mv_lens.get('z') or '—'}; "
                    f"color={mv_lens.get('color3d') or '—'}; metric={mv_lens.get('metric') or 'RMS'}. "
                    f"{'Current view only.' if mv_lens.get('use_view') else 'Whole-run metrics.'} {pebbles_text}"
                )
                cards.append(
                    self._workspace_insight_card_html(
                        "Cloud / pebbles",
                        mv_headline,
                        mv_detail,
                        tone=mv_tone,
                    )
                )
            else:
                cards.append(
                    self._workspace_insight_card_html(
                        "Cloud / pebbles",
                        "Build multivariate field",
                        "Select 2+ runs and 1+ signals so the window can derive run-level fields for SPLOM, 3D melting cloud and pebbles-on-sand overlays.",
                        tone="neutral",
                )
            )

        if analysis_mode in {"one_to_all", "all_to_one"} and dist_lens:
            dist_headline = str(dist_bridge.get("headline") or "Run spread ready").strip()
            dist_tone = str(dist_bridge.get("tone") or ("ok" if not dist_lens.get("bridge_ready", False) else "accent")).strip()
            dist_signal = str(dist_lens.get("signal") or "signal").strip()
            dist_metric = str(dist_lens.get("metric_label") or "run metric").strip()
            dist_time = str(dist_lens.get("time_desc") or "").strip()
            dist_detail = (
                f"{dist_signal} via {dist_metric}: top={str(dist_lens.get('top_run') or '—')} "
                f"({float(dist_lens.get('top_value', 0.0) or 0.0):.6g}), median={float(dist_lens.get('median', 0.0) or 0.0):.6g}, "
                f"ref={str(dist_lens.get('ref_label') or dist_lens.get('ref_run') or '—')} "
                f"({float(dist_lens.get('ref_value', 0.0) or 0.0):.6g})."
            )
            if dist_time:
                dist_detail = f"{dist_detail} Window: {dist_time}."
            if dist_bridge:
                dist_detail = f"{dist_detail} {str(dist_bridge.get('detail') or '').strip()}"
            elif bool(dist_lens.get("mixed_sign", False)) and "delta" in str(dist_lens.get("metric_key") or ""):
                dist_detail = f"{dist_detail} Values cross both sides of the reference, so the run spread is currently split."
            elif bool(dist_lens.get("outlier_driven", False)):
                dist_detail = (
                    f"{dist_detail} {str(dist_lens.get('outlier_run') or 'One run')} is currently pulling the scalar ranking away from the median."
                )
            cards.append(
                self._workspace_insight_card_html(
                    "Run spread",
                    dist_headline,
                    dist_detail,
                    tone=dist_tone,
                )
            )

        if analysis_mode in {"one_to_all", "all_to_one"} and peak_lens:
            peak_headline = str(peak_bridge.get("headline") or "Peak |Δ| field ready").strip()
            peak_tone = str(peak_bridge.get("tone") or ("ok" if not peak_lens.get("bridge_ready", False) else "accent")).strip()
            peak_signal = str(peak_lens.get("hotspot_signal") or peak_lens.get("dominant_signal") or "signal").strip()
            peak_run = str(peak_lens.get("hotspot_run") or peak_lens.get("dominant_run") or "run").strip()
            peak_value = float(peak_lens.get("hotspot_peak", 0.0) or 0.0)
            peak_time = float(peak_lens.get("hotspot_time", float("nan")) or float("nan"))
            peak_unit = str(peak_lens.get("hotspot_unit") or "").strip()
            peak_unit_txt = f" [{peak_unit}]" if peak_unit else ""
            peak_detail = (
                f"Hotspot {peak_signal} in {peak_run}"
                f"{f' @ {peak_time:.3f}s' if np.isfinite(peak_time) else ''}"
                f" = {peak_value:.6g}{peak_unit_txt}. "
                f"Signal competition={int(peak_lens.get('signal_competition', 0) or 0)}, "
                f"run competition={int(peak_lens.get('run_competition', 0) or 0)}."
            )
            if peak_bridge:
                peak_detail = f"{peak_detail} {str(peak_bridge.get('detail') or '').strip()}"
            cards.append(
                self._workspace_insight_card_html(
                    "Peak |Δ| field",
                    peak_headline,
                    peak_detail,
                    tone=peak_tone,
                )
            )

        if heat.get("signal"):
            cards.append(
                self._workspace_insight_card_html(
                    "Delta hotspot",
                    f"{heat.get('signal')} @ {float(heat.get('time_s', 0.0) or 0.0):.3f}s",
                    f"Run {heat.get('run')} shows the strongest divergence. "
                    f"Peak {float(heat.get('peak', 0.0) or 0.0):.3g} in {heat.get('metric', 'heatmap')} mode.",
                    tone="accent",
                )
            )
        elif len(runs) >= 2 and len(sigs) >= 1:
            cards.append(
                self._workspace_insight_card_html(
                    "Delta hotspot",
                    "Waiting for heatmap refresh",
                    "Heatmaps are enabled, but no stable hotspot summary is cached yet. "
                    "Keep 2+ runs and 1+ signals selected.",
                    tone="neutral",
                )
            )
        else:
            cards.append(
                self._workspace_insight_card_html(
                    "Delta hotspot",
                    "Need comparison context",
                    "Select at least 2 runs and a signal to surface the strongest time-local delta zone.",
                    tone="neutral",
                )
            )

        if infl.get("feature") and infl.get("signal"):
            corr = float(infl.get("corr", 0.0) or 0.0)
            cards.append(
                self._workspace_insight_card_html(
                    "Top meta driver",
                    f"{infl.get('feature')} -> {infl.get('signal')}",
                    f"corr={corr:+.2f} at t={float(infl.get('time_s', 0.0) or 0.0):.3f}s. "
                    f"Runs={int(infl.get('runs', 0) or 0)}, meta shown={int(infl.get('meta_count', 0) or 0)}.",
                    tone="ok" if abs(corr) >= 0.7 else "accent",
                )
            )
        elif len(runs) >= 3 and len(sigs) >= 1:
            cards.append(
                self._workspace_insight_card_html(
                    "Top meta driver",
                    "Need influence refresh",
                    "Influence(t) becomes meaningful with 3+ runs. Move the playhead or keep the current selection stable to rank meta drivers.",
                    tone="neutral",
                )
            )
        else:
            cards.append(
                self._workspace_insight_card_html(
                    "Top meta driver",
                    "Need 3+ runs",
                    "Meta-to-signal heuristics rank which numeric meta parameters explain the current signal shape best.",
                    tone="neutral",
                )
            )

        if bool(events.get("no_signals_selected", False)):
            cards.append(
                self._workspace_insight_card_html(
                    "Event context",
                    "Event filter is muted",
                    "No event signals are selected right now. Pick one or more event channels so local triggers can support the current explanation.",
                    tone="accent",
                )
            )
        elif events_rows > 0:
            event_headline = "Visible event context"
            event_detail = (
                f"Baseline={events.get('baseline') or '—'}, visible rows={int(events.get('rows', events_rows) or events_rows)}"
                f"/{int(events.get('source_rows', events_rows) or events_rows)}."
            )
            if events_focus:
                event_detail = f"{event_detail} First visible anchor: {events_focus}."
            if events.get("top_signal"):
                event_detail = (
                    f"{event_detail} Dominant visible event is {events.get('top_signal')} "
                    f"({int(events.get('top_count', 0) or 0)} row(s))."
                )
            if analysis_mode == "one_to_all":
                event_headline = f"Trigger gate: {events.get('top_signal') or events.get('sample_signal') or 'events'}"
                event_detail = f"{event_detail} Use this trigger gate to test whether one driver fans out into several responses."
            elif analysis_mode == "all_to_one":
                event_headline = f"Target-side trigger: {events.get('top_signal') or events.get('sample_signal') or 'events'}"
                event_detail = f"{event_detail} Use this local event context to confirm or reject the current target-driver explanation."
            elif analysis_mode == "all_to_all":
                event_headline = f"Pebble anchor: {events.get('top_signal') or events.get('sample_signal') or 'events'}"
                event_detail = f"{event_detail} Compare these grains with cloud clusters to see whether separation is event-driven."
            cards.append(
                self._workspace_insight_card_html(
                    "Event context",
                    event_headline,
                    event_detail,
                    tone="ok" if events_focus else "accent",
                )
            )
        elif int(events.get("source_rows", 0) or 0) > 0:
            cards.append(
                self._workspace_insight_card_html(
                    "Event context",
                    "No visible events after filtering",
                    "The baseline run has event rows, but none are currently visible. Revisit the event filter or the current reference run.",
                    tone="accent",
                )
            )

        if not runs:
            quality_headline = "Load a compare set"
            quality_detail = "Open 2+ NPZ runs to unlock heatmaps, QA and multivariate clustering."
            quality_tone = "neutral"
        elif trust_visible:
            quality_headline = "Trust attention required"
            quality_detail = (
                f"Trust banner is active. QA issues={qa_issues} (err={qa_err}, warn={qa_warn}), events rows={events_rows}. "
                f"Next: {follow_route_label}."
            )
            if qa_focus:
                quality_detail = f"{quality_detail} {qa_focus}"
            if events_focus:
                quality_detail = f"{quality_detail} Event anchor: {events_focus}."
            quality_tone = "alert" if qa_err > 0 else "warn"
        elif qa_issues > 0:
            quality_headline = f"QA flagged {qa_issues} issue(s)"
            quality_detail = (
                f"err={qa_err}, warn={qa_warn}, events rows={events_rows}. "
                f"Next: inspect {follow_route_label}, then return to Heatmaps for root-cause localization."
            )
            if qa_focus:
                quality_detail = f"{quality_detail} {qa_focus}"
            if events_focus:
                quality_detail = f"{quality_detail} Event anchor: {events_focus}."
            quality_tone = "warn" if qa_err == 0 else "alert"
        elif analysis_mode == "all_to_all" and len(runs) >= 3 and len(sigs) >= 3:
            quality_headline = "Ready for all-to-all scouting"
            quality_detail = (
                f"Table {table}, runs={len(runs)}, signals={len(sigs)}, events rows={events_rows}. "
                f"Next: {follow_route_label} for clusters and sparse outliers, then Heatmaps for time localization."
            )
            quality_tone = "ok"
        elif analysis_mode == "all_to_one" and len(runs) >= 3 and 1 <= len(sigs) <= 2:
            quality_headline = "Ready for target explanation"
            quality_detail = (
                f"Table {table}, runs={len(runs)}, target signals={len(sigs)}, events rows={events_rows}. "
                f"Next: {follow_route_label} to rank many drivers against the current target, then cross-check Delta / Events around the active frame."
            )
            quality_tone = "ok"
        elif analysis_mode == "one_to_all" and len(runs) >= 3 and len(sigs) >= 2:
            quality_headline = "Ready for driver sweep"
            quality_detail = (
                f"Table {table}, runs={len(runs)}, response signals={len(sigs)}, events rows={events_rows}. "
                f"Next: {follow_route_label} to trace one candidate driver across many responses, then use QA / Events for local trigger checks."
            )
            quality_tone = "ok"
        else:
            quality_headline = "Build comparison density"
            if analysis_mode == "all_to_one":
                quality_detail = (
                    f"Table {table}, runs={len(runs)}, signals={len(sigs)}, events rows={events_rows}. "
                    "Keep 3+ runs and narrow the target to 1-2 signals so one waveform can be explained cleanly."
                )
            elif analysis_mode == "one_to_all":
                quality_detail = (
                    f"Table {table}, runs={len(runs)}, signals={len(sigs)}, events rows={events_rows}. "
                    "Keep 3+ runs and at least 2 response signals so one driver can fan out across visible responses."
                )
            else:
                quality_detail = (
                    f"Table {table}, runs={len(runs)}, signals={len(sigs)}, events rows={events_rows}. "
                    "Add a few more signals to strengthen multivariate separation."
                )
            quality_tone = "accent"

        cards.append(
            self._workspace_insight_card_html(
                "Quality / next step",
                quality_headline,
                quality_detail,
                tone=quality_tone,
            )
        )
        cards.append(
            self._workspace_insight_card_html(
                "Heuristic next move",
                str(next_move.get("headline") or "Next move"),
                str(next_move.get("detail") or ""),
                tone=str(next_move.get("tone") or "accent"),
            )
        )

        html_doc = (
            "<html><body style='margin:0; padding:0; font-family:Segoe UI, Arial, sans-serif;'>"
            + "".join(cards)
            + "</body></html>"
        )
        try:
            browser.setHtml(html_doc)
        except Exception:
            try:
                browser.setPlainText("\n\n".join([html.unescape(card) for card in cards]))
            except Exception:
                pass

    def _workspace_focus_label(self, *, follow_target: Optional[Dict[str, object]] = None) -> str:
        mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        current_target = self._workspace_current_focus_target()
        return self._workspace_focus_mode_display_text(
            focus_mode=mode,
            follow_target=(current_target or follow_target),
            for_action=False,
        )

    def _set_workspace_dock_title(self, attr: str, title: str) -> None:
        dock = getattr(self, attr, None)
        if not isinstance(dock, QtWidgets.QDockWidget):
            return
        try:
            dock.setWindowTitle(str(title))
        except Exception:
            pass

    def _update_workspace_window_title(
        self,
        *,
        analysis_mode: str,
        follow_target: Optional[Dict[str, object]] = None,
        anchor_label: str,
        ref: str,
        runs_count: int,
        sig_count: int,
        table: str,
    ) -> None:
        base = str(getattr(self, "_window_title_base", "") or "Pneumo: NPZ Compare Viewer")
        parts: List[str] = []
        focus_mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        focus_label = str(self._workspace_focus_label(follow_target=follow_target) or "").strip()
        if focus_label:
            parts.append(f"Focus {focus_label}")
        if focus_mode == "all":
            next_label = self._workspace_follow_target_label(follow_target, separator=": ", fallback="")
            if next_label:
                parts.append(f"Next {next_label}")
        lens_label = self._workspace_analysis_label()
        if lens_label:
            parts.append(f"Lens {lens_label}")
        anchor = str(anchor_label or "").strip()
        if anchor and ("—" not in anchor):
            if len(anchor) > 42:
                anchor = f"{anchor[:39]}..."
            parts.append(anchor)
        if ref and ref != "—":
            parts.append(f"Ref {ref}")
        if table and table != "—":
            parts.append(f"Table {table}")
        if runs_count or sig_count:
            parts.append(f"{int(runs_count)} run(s) / {int(sig_count)} signal(s)")
        title = base if not parts else f"{base} | {' | '.join(parts)}"
        try:
            self.setWindowTitle(title)
        except Exception:
            pass

    def _workspace_export_slugify(self, value: str, *, fallback: str = "") -> str:
        txt = str(value or "").strip().lower()
        if not txt:
            return fallback
        txt = txt.replace("->", "_to_").replace("→", "_to_").replace("Δ", "delta").replace("δ", "delta")
        txt = re.sub(r"[^a-z0-9]+", "_", txt)
        txt = txt.strip("_")
        return txt or fallback

    def _workspace_export_context_slug(self) -> str:
        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        focus_mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        runs = list(self._selected_runs()) if hasattr(self, "list_runs") else []
        ref = str(self._reference_run_label(runs) or "").strip()
        table = str(getattr(self, "current_table", "") or "").strip()
        follow_target = self._workspace_live_follow_target(analysis_mode=analysis_mode)
        current_target = self._workspace_current_focus_target()
        focus_label = self._workspace_focus_label(follow_target=follow_target)
        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        anchor = self._workspace_analysis_anchor_label(
            analysis_mode=analysis_mode,
            infl_lens=infl_lens,
            mv_lens=mv_lens,
        )

        parts: List[str] = []
        if focus_mode == "all":
            current_label = self._workspace_current_dock_label()
            current_slug = self._workspace_export_slugify(current_label)
            if current_slug:
                parts.append(f"current_{current_slug[:24]}")
            next_label = self._workspace_follow_target_label(follow_target, separator=" ", fallback="")
            next_slug = self._workspace_export_slugify(next_label)
            if next_slug:
                parts.append(f"next_{next_slug[:32]}")
        else:
            focus_slug = self._workspace_export_slugify(
                self._workspace_follow_target_label(current_target or follow_target, separator=" ", fallback=focus_label)
            )
            if focus_slug and focus_slug not in {"overview", "show_all_docks"}:
                parts.append(f"focus_{focus_slug[:32]}")
        lens_slug = self._workspace_export_slugify(analysis_mode, fallback="all_to_all")
        if lens_slug:
            parts.append(f"lens_{lens_slug}")
        anchor_slug = self._workspace_export_slugify(anchor)
        if anchor_slug and ("cloud" not in anchor_slug or len(anchor_slug) > 5):
            parts.append(anchor_slug[:36].rstrip("_"))
        ref_slug = self._workspace_export_slugify(ref)
        if ref_slug:
            parts.append(f"ref_{ref_slug[:20]}")
        table_slug = self._workspace_export_slugify(table)
        if table_slug:
            parts.append(f"table_{table_slug[:20]}")
        slug = "__".join([p for p in parts if p]).strip("_")
        if len(slug) > 96:
            slug = slug[:96].rstrip("_")
        return slug

    def _workspace_export_filename(self, stem: str, *, suffix: str = ".png") -> str:
        base = self._workspace_export_slugify(stem, fallback="compare")
        ctx = self._workspace_export_context_slug()
        if ctx:
            return f"{base}__{ctx}{suffix}"
        return f"{base}{suffix}"

    def _update_workspace_dock_titles(
        self,
        *,
        analysis_mode: str,
        anchor_label: str,
        qa_issues: int,
        events_rows: int,
    ) -> None:
        mode = str(analysis_mode or "all_to_all")
        anchor = str(anchor_label or "").strip()
        anchor_ready = "—" not in anchor if anchor else False
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        events = dict(getattr(self, "_insight_events", {}) or {})
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=infl_lens,
            events=events,
            trust_visible=trust_visible,
            qa_issues=int(qa_issues or 0),
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=mode,
            trust_visible=trust_visible,
            qa_issues=int(qa_issues or 0),
            events_rows=int(events_rows or 0),
            events_insight=events,
            causal_story=causal_story,
        )
        repair_lane = str(causal_story.get("repair_lane") or "").strip()
        repair_badge = ""
        if repair_lane in {"heatmaps", "qa", "multivariate"}:
            repair_badge = " | Validation lane" if str(causal_story.get("confidence") or "").strip() == "aligned" else " | Repair lane"
        target_attr = str(follow_target.get("dock_attr") or "").strip()
        target_badge = ""
        if target_attr:
            target_badge = (
                f" | Validate {str(follow_target.get('dock_label') or 'target')}"
                if str(causal_story.get("confidence") or "").strip() == "aligned"
                else f" | Follow {str(follow_target.get('dock_label') or 'target')}"
            )

        self._set_workspace_dock_title("dock_controls", "Controls")

        heat_suffix = ""
        if mode in {"one_to_all", "all_to_one"} and anchor_ready:
            heat_suffix = f" | {anchor}"
        heat_lane_suffix = repair_badge if repair_lane == "heatmaps" else ""
        heat_follow_suffix = target_badge if target_attr == "dock_heatmap" else ""
        peak_follow_suffix = target_badge if target_attr == "dock_peak_heatmap" else ""
        open_follow_suffix = target_badge if target_attr == "dock_open_timeline" else ""
        infl_follow_suffix = target_badge if target_attr == "dock_influence" else ""
        dist_follow_suffix = target_badge if target_attr == "dock_run_metrics" else ""
        static_follow_suffix = target_badge if target_attr == "dock_static_stroke" else ""
        inflheat_follow_suffix = target_badge if target_attr == "dock_inflheat" else ""
        self._set_workspace_dock_title("dock_heatmap", f"Δ(t) Heatmap{heat_suffix}{heat_lane_suffix}{heat_follow_suffix}")
        self._set_workspace_dock_title("dock_open_timeline", f"Valves (open) timeline{heat_suffix}{heat_lane_suffix}{open_follow_suffix}")
        self._set_workspace_dock_title("dock_influence", f"Influence(t): meta → signals{heat_suffix}{heat_lane_suffix}{infl_follow_suffix}")
        self._set_workspace_dock_title("dock_peak_heatmap", f"Peak |Δ| heatmap{heat_suffix}{heat_lane_suffix}{peak_follow_suffix}")
        self._set_workspace_dock_title("dock_run_metrics", f"Run metrics / distributions{heat_suffix}{heat_lane_suffix}{dist_follow_suffix}")
        self._set_workspace_dock_title("dock_static_stroke", f"Static (t0) / stroke check{heat_suffix}{heat_lane_suffix}{static_follow_suffix}")
        self._set_workspace_dock_title("dock_inflheat", f"Influence(t) Heatmap{heat_suffix}{heat_lane_suffix}{inflheat_follow_suffix}")

        multivar_title = "Multivariate: SPLOM / Parallel / 3D"
        if mode == "all_to_all" and anchor_ready:
            multivar_title = f"{multivar_title} | {anchor}"
        if repair_lane == "multivariate":
            multivar_title = f"{multivar_title}{repair_badge}"
        if target_attr == "dock_multivar":
            multivar_title = f"{multivar_title}{target_badge}"
        self._set_workspace_dock_title("dock_multivar", multivar_title)

        qa_title = "QA: suspicious signals"
        if int(qa_issues or 0) > 0:
            qa_title = f"{qa_title} | {int(qa_issues)} issue(s)"
        if repair_lane == "qa":
            qa_title = f"{qa_title}{repair_badge}"
        if target_attr == "dock_qa":
            qa_title = f"{qa_title}{target_badge}"
        self._set_workspace_dock_title("dock_qa", qa_title)

        events_title = "Events"
        if int(events_rows or 0) > 0:
            events_title = f"{events_title} | {int(events_rows)} row(s)"
        if repair_lane == "qa":
            events_title = f"{events_title}{repair_badge}"
        if target_attr == "dock_events":
            events_title = f"{events_title}{target_badge}"
        self._set_workspace_dock_title("dock_events", events_title)

        ga_title = "Geometry acceptance"
        ga_cache = dict(getattr(self, "_geometry_acceptance_cache", {}) or {})
        gate_counts = dict(ga_cache.get("gate_counts") or {})
        fail_n = int(gate_counts.get("FAIL", 0) or 0)
        warn_n = int(gate_counts.get("WARN", 0) or 0)
        if fail_n > 0:
            ga_title = f"{ga_title} | FAIL {fail_n}"
        elif warn_n > 0:
            ga_title = f"{ga_title} | WARN {warn_n}"
        if repair_lane == "qa":
            ga_title = f"{ga_title}{repair_badge}"
        if target_attr == "dock_geometry_acceptance":
            ga_title = f"{ga_title}{target_badge}"
        self._set_workspace_dock_title("dock_geometry_acceptance", ga_title)

    def _update_workspace_status(self) -> None:
        runs = list(self._selected_runs()) if hasattr(self, "list_runs") else []
        sigs = list(self._selected_signals()) if hasattr(self, "list_signals") else []
        table = str(getattr(self, "current_table", "") or "—")
        ref = str(self._reference_run_label(runs) or "—")
        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        total_docks = len(self._iter_workspace_docks())
        visible_docks = 0
        for dock in self._iter_workspace_docks():
            try:
                if not dock.isHidden():
                    visible_docks += 1
            except Exception:
                pass
        events_rows = 0
        try:
            if getattr(self, "tbl_events", None) is not None:
                events_rows = int(self.tbl_events.rowCount())
        except Exception:
            events_rows = 0
        events_insight = dict(getattr(self, "_insight_events", {}) or {})

        qa_text = str(getattr(self, "lbl_qa_summary", None).text() if getattr(self, "lbl_qa_summary", None) is not None else "QA —")
        qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        try:
            if "issues=" in qa_text:
                qa_issues = int(str(qa_text).split("issues=", 1)[1].split()[0].split("(", 1)[0].rstrip(",)"))
        except Exception:
            qa_issues = int((getattr(self, "_insight_qa", {}) or {}).get("issues", 0) or 0)
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        infl_lens = self._workspace_influence_lens_summary()
        mv_lens = self._workspace_multivar_lens_summary()
        anchor_label = self._workspace_analysis_anchor_label(
            analysis_mode=analysis_mode,
            infl_lens=infl_lens,
            mv_lens=mv_lens,
        )
        causal_story = self._workspace_causal_story_summary(
            analysis_mode=analysis_mode,
            heat=dict(getattr(self, "_insight_heat", {}) or {}),
            infl=dict(getattr(self, "_insight_infl", {}) or {}),
            infl_lens=infl_lens,
            events=events_insight,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        recommended_focus = self._workspace_contextual_focus_recommendation(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events_insight,
            causal_story=causal_story,
        )
        story_label = self._workspace_causal_story_label(causal_story)
        story_confidence = str(causal_story.get("confidence") or "").strip()
        repair_summary = self._workspace_repair_lane_summary(
            causal_story=causal_story,
            analysis_mode=analysis_mode,
        )
        follow_target = self._workspace_follow_target_summary(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
            events_rows=events_rows,
            events_insight=events_insight,
            causal_story=causal_story,
        )
        focus_labels = {
            "all": "all",
            "heatmaps": "heatmaps",
            "multivariate": "multivar",
            "qa": "qa/events",
        }
        recommended_focus_label = focus_labels.get(str(recommended_focus), str(recommended_focus or "all"))

        selection_text = f"Runs {len(runs)} | Table {table} | Signals {len(sigs)}"
        weakest_status = str(repair_summary.get("status_label") or "").strip()
        next_target_status = (
            f"{str(follow_target.get('focus_label') or recommended_focus_label)}: "
            f"{str(follow_target.get('dock_label') or 'dock')}"
        )
        quality_text = (
            f"Events {events_rows} | {'Trust attention' if trust_visible else 'Trust ok'} | "
            f"QA {qa_issues} | Next {next_target_status}"
        )
        if weakest_status:
            quality_text = f"{quality_text} | Weakest {weakest_status}"
        layout_text = (
            f"Focus {self._workspace_focus_label(follow_target=follow_target)} | Lens {self._workspace_analysis_label()} | "
            f"{anchor_label} | Docks {visible_docks}/{total_docks} | Ref {ref}"
        )
        if story_label:
            if story_confidence:
                layout_text = f"{layout_text} | Story {story_confidence}: {story_label}"
            else:
                layout_text = f"{layout_text} | Story {story_label}"

        try:
            self.lbl_status_selection.setText(selection_text)
            self.lbl_status_quality.setText(quality_text)
            self.lbl_status_layout.setText(layout_text)
        except Exception:
            pass

        self._set_status_chip_tone(self.lbl_status_selection, "accent" if runs else "neutral")
        if trust_visible or qa_issues > 0:
            self._set_status_chip_tone(self.lbl_status_quality, "warn" if qa_issues < 10 else "alert")
        else:
            self._set_status_chip_tone(self.lbl_status_quality, "ok" if runs else "neutral")
        anchor_ready = "—" not in str(anchor_label or "")
        self._set_status_chip_tone(
            self.lbl_status_layout,
            "ok" if (visible_docks and anchor_ready) else ("accent" if visible_docks else "neutral"),
        )
        self._update_workspace_window_title(
            analysis_mode=analysis_mode,
            follow_target=follow_target,
            anchor_label=anchor_label,
            ref=ref,
            runs_count=len(runs),
            sig_count=len(sigs),
            table=table,
        )
        self._update_workspace_dock_titles(
            analysis_mode=analysis_mode,
            anchor_label=anchor_label,
            qa_issues=qa_issues,
            events_rows=events_rows,
        )
        self._sync_workspace_focus_buttons()
        self._sync_workspace_analysis_buttons()
        self._sync_workspace_analysis_actions(current_mode=analysis_mode)
        self._update_workspace_focus_labels(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        self._update_workspace_focus_button_hints(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        self._update_workspace_focus_action_hints(
            analysis_mode=analysis_mode,
            trust_visible=trust_visible,
            qa_issues=qa_issues,
        )
        self._update_workspace_analysis_button_hints(current_mode=analysis_mode)
        self._update_workspace_analysis_action_hints(current_mode=analysis_mode)
        self._update_workspace_assistant()
        self._update_workspace_insights()

    def _iter_workspace_docks(self) -> List[QtWidgets.QDockWidget]:
        docks: List[QtWidgets.QDockWidget] = []
        for attr in (
            "dock_controls",
            "dock_heatmap",
            "dock_peak_heatmap",
            "dock_open_timeline",
            "dock_influence",
            "dock_run_metrics",
            "dock_static_stroke",
            "dock_inflheat",
            "dock_multivar",
            "dock_qa",
            "dock_events",
            "dock_geometry_acceptance",
        ):
            dock = getattr(self, attr, None)
            if isinstance(dock, QtWidgets.QDockWidget):
                docks.append(dock)
        return docks

    def _workspace_dock_by_attr(self, attr: str) -> Optional[QtWidgets.QDockWidget]:
        key = str(attr or "").strip()
        if key not in {
            "dock_controls",
            "dock_heatmap",
            "dock_peak_heatmap",
            "dock_open_timeline",
            "dock_influence",
            "dock_run_metrics",
            "dock_static_stroke",
            "dock_inflheat",
            "dock_multivar",
            "dock_qa",
            "dock_events",
            "dock_geometry_acceptance",
        }:
            return None
        dock = getattr(self, key, None)
        return dock if isinstance(dock, QtWidgets.QDockWidget) else None

    def _workspace_dock_attr_for(self, dock: Optional[QtWidgets.QDockWidget]) -> str:
        if dock is None:
            return ""
        for attr in (
            "dock_controls",
            "dock_heatmap",
            "dock_peak_heatmap",
            "dock_open_timeline",
            "dock_influence",
            "dock_run_metrics",
            "dock_static_stroke",
            "dock_inflheat",
            "dock_multivar",
            "dock_qa",
            "dock_events",
            "dock_geometry_acceptance",
        ):
            if getattr(self, attr, None) is dock:
                return attr
        return ""

    def _workspace_dock_for_widget(self, widget: Optional[QtWidgets.QWidget]) -> Optional[QtWidgets.QDockWidget]:
        cur = widget
        while cur is not None:
            if isinstance(cur, QtWidgets.QDockWidget):
                return cur
            try:
                cur = cur.parentWidget()
            except Exception:
                return None
        return None

    def _workspace_allowed_dock_attrs(self, focus_mode: str) -> Set[str]:
        mode = str(focus_mode or "all")
        allowed = {"dock_controls"}
        if mode == "heatmaps":
            allowed.update({"dock_heatmap", "dock_peak_heatmap", "dock_open_timeline", "dock_influence", "dock_run_metrics", "dock_static_stroke", "dock_inflheat"})
        elif mode == "multivariate":
            allowed.add("dock_multivar")
        elif mode == "qa":
            allowed.update({"dock_qa", "dock_events", "dock_geometry_acceptance"})
        else:
            allowed.update(
                {
                    "dock_heatmap",
                    "dock_peak_heatmap",
                    "dock_open_timeline",
                    "dock_influence",
                    "dock_run_metrics",
                    "dock_static_stroke",
                    "dock_inflheat",
                    "dock_multivar",
                    "dock_qa",
                    "dock_events",
                    "dock_geometry_acceptance",
                }
            )
        return allowed

    def _restore_workspace_focus_dock(self, *, saved_focus_mode: str, dock_attr: str) -> bool:
        attr = str(dock_attr or "").strip()
        if not attr:
            return False
        if attr not in self._workspace_allowed_dock_attrs(saved_focus_mode):
            return False
        dock = self._workspace_dock_by_attr(attr)
        if dock is None:
            return False
        self._raise_dock(dock)
        return True

    def _remember_workspace_focus_widget(self, widget: Optional[QtWidgets.QWidget]) -> bool:
        dock = self._workspace_dock_for_widget(widget)
        attr = self._workspace_dock_attr_for(dock)
        if not attr or attr == "dock_controls":
            return False
        mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        if mode != "all" and attr not in self._workspace_allowed_dock_attrs(mode):
            return False
        if str(getattr(self, "_workspace_focus_dock_attr", "") or "") == attr:
            return False
        self._workspace_focus_dock_attr = attr
        try:
            self._update_workspace_status()
        except Exception:
            pass
        return True

    def _on_app_focus_changed(self, _old: Optional[QtWidgets.QWidget], new: Optional[QtWidgets.QWidget]) -> None:
        try:
            self._remember_workspace_focus_widget(new)
        except Exception:
            pass

    def _show_dock(self, dock: Optional[QtWidgets.QDockWidget]) -> None:
        if dock is None:
            return
        try:
            dock.setFloating(False)
        except Exception:
            pass
        try:
            dock.show()
        except Exception:
            pass

    def _raise_dock(self, dock: Optional[QtWidgets.QDockWidget]) -> None:
        if dock is None:
            return
        try:
            attr = self._workspace_dock_attr_for(dock)
            if attr:
                self._workspace_focus_dock_attr = attr
        except Exception:
            pass
        try:
            dock.raise_()
        except Exception:
            pass

    def _apply_default_workspace_layout(self) -> None:
        self._workspace_focus_mode = "all"
        controls = getattr(self, "dock_controls", None)
        heatmap = getattr(self, "dock_heatmap", None)
        peak_heatmap = getattr(self, "dock_peak_heatmap", None)
        open_timeline = getattr(self, "dock_open_timeline", None)
        influence = getattr(self, "dock_influence", None)
        run_metrics = getattr(self, "dock_run_metrics", None)
        static_stroke = getattr(self, "dock_static_stroke", None)
        inflheat = getattr(self, "dock_inflheat", None)
        multivar = getattr(self, "dock_multivar", None)
        qa = getattr(self, "dock_qa", None)
        events = getattr(self, "dock_events", None)
        geometry_acceptance = getattr(self, "dock_geometry_acceptance", None)

        for dock in self._iter_workspace_docks():
            self._show_dock(dock)
            try:
                self.removeDockWidget(dock)
            except Exception:
                pass

        if controls is not None:
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, controls)

        analysis_anchor = heatmap or peak_heatmap or open_timeline or influence or run_metrics or static_stroke or inflheat or multivar
        if analysis_anchor is not None:
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea, analysis_anchor)

        if qa is not None:
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea, qa)
            if analysis_anchor is not None:
                try:
                    self.splitDockWidget(analysis_anchor, qa, QtCore.Qt.Vertical)
                except Exception:
                    pass

        if events is not None:
            if qa is not None:
                try:
                    self.tabifyDockWidget(qa, events)
                except Exception:
                    pass
            else:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, events)

        if geometry_acceptance is not None:
            if qa is not None:
                try:
                    self.tabifyDockWidget(qa, geometry_acceptance)
                except Exception:
                    pass
            elif events is not None:
                try:
                    self.tabifyDockWidget(events, geometry_acceptance)
                except Exception:
                    pass
            else:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, geometry_acceptance)

        for dock in (heatmap, peak_heatmap, open_timeline, influence, run_metrics, static_stroke, inflheat, multivar):
            if dock is None or dock is analysis_anchor:
                continue
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
            if analysis_anchor is not None:
                try:
                    self.tabifyDockWidget(analysis_anchor, dock)
                except Exception:
                    pass

        for dock in self._iter_workspace_docks():
            self._show_dock(dock)

        try:
            if controls is not None and analysis_anchor is not None:
                self.resizeDocks([controls, analysis_anchor], [340, 980], QtCore.Qt.Horizontal)
        except Exception:
            pass
        try:
            if analysis_anchor is not None and qa is not None:
                self.resizeDocks([analysis_anchor, qa], [620, 280], QtCore.Qt.Vertical)
        except Exception:
            pass

        self._raise_dock(heatmap or analysis_anchor)
        self._raise_dock(qa)
        self._update_workspace_status()

    def _focus_workspace_preset(self, mode: str) -> None:
        self._apply_default_workspace_layout()
        self._workspace_focus_mode = str(mode or "all")

        controls = getattr(self, "dock_controls", None)
        heatmap = getattr(self, "dock_heatmap", None)
        peak_heatmap = getattr(self, "dock_peak_heatmap", None)
        open_timeline = getattr(self, "dock_open_timeline", None)
        influence = getattr(self, "dock_influence", None)
        run_metrics = getattr(self, "dock_run_metrics", None)
        static_stroke = getattr(self, "dock_static_stroke", None)
        inflheat = getattr(self, "dock_inflheat", None)
        multivar = getattr(self, "dock_multivar", None)
        qa = getattr(self, "dock_qa", None)
        events = getattr(self, "dock_events", None)
        geometry_acceptance = getattr(self, "dock_geometry_acceptance", None)

        show_attrs = {"dock_controls"}
        active_dock = controls
        if mode == "heatmaps":
            show_attrs.update({"dock_heatmap", "dock_peak_heatmap", "dock_open_timeline", "dock_influence", "dock_run_metrics", "dock_static_stroke", "dock_inflheat"})
            active_dock = heatmap or peak_heatmap or open_timeline or influence or run_metrics or static_stroke or inflheat or controls
        elif mode == "multivariate":
            show_attrs.add("dock_multivar")
            active_dock = multivar or controls
        elif mode == "qa":
            show_attrs.update({"dock_qa", "dock_events", "dock_geometry_acceptance"})
            active_dock = qa or events or geometry_acceptance or controls
        else:
            show_attrs.update(
                {
                    "dock_heatmap",
                    "dock_peak_heatmap",
                    "dock_open_timeline",
                    "dock_influence",
                    "dock_run_metrics",
                    "dock_static_stroke",
                    "dock_inflheat",
                    "dock_multivar",
                    "dock_qa",
                    "dock_events",
                    "dock_geometry_acceptance",
                }
            )
            active_dock = heatmap or multivar or qa or controls

        for attr in (
            "dock_controls",
            "dock_heatmap",
            "dock_peak_heatmap",
            "dock_open_timeline",
            "dock_influence",
            "dock_run_metrics",
            "dock_static_stroke",
            "dock_inflheat",
            "dock_multivar",
            "dock_qa",
            "dock_events",
            "dock_geometry_acceptance",
        ):
            dock = getattr(self, attr, None)
            if not isinstance(dock, QtWidgets.QDockWidget):
                continue
            try:
                if attr in show_attrs:
                    self._show_dock(dock)
                else:
                    dock.hide()
            except Exception:
                pass

        self._raise_dock(active_dock)
        self._update_workspace_status()

    def _follow_workspace_heuristic_focus(self) -> None:
        self._apply_workspace_follow_target(self._workspace_live_follow_target())

    def _build_view_menu(self) -> None:
        m = self.menuBar()
        view_menu = m.addMenu("View")
        self.menu_view = view_menu

        layout_menu = view_menu.addMenu("Layout")
        self.menu_view_layout = layout_menu

        self.act_view_reset_workspace = QtGui.QAction("Reset Workspace", self)
        self.act_view_reset_workspace.setObjectName("act_view_reset_workspace")
        self.act_view_reset_workspace.setShortcut("Ctrl+Shift+0")
        self.act_view_reset_workspace.triggered.connect(self._apply_default_workspace_layout)
        layout_menu.addAction(self.act_view_reset_workspace)

        self.act_view_show_all_docks = QtGui.QAction("Show All Docks", self)
        self.act_view_show_all_docks.setObjectName("act_view_show_all_docks")
        self.act_view_show_all_docks.triggered.connect(lambda: self._activate_workspace_focus_mode("all"))
        layout_menu.addAction(self.act_view_show_all_docks)

        layout_menu.addSeparator()

        self.act_view_focus_heatmaps = QtGui.QAction("Focus Heatmaps", self)
        self.act_view_focus_heatmaps.setObjectName("act_view_focus_heatmaps")
        self.act_view_focus_heatmaps.setShortcut("Ctrl+Shift+1")
        self.act_view_focus_heatmaps.triggered.connect(lambda: self._activate_workspace_focus_mode("heatmaps"))
        layout_menu.addAction(self.act_view_focus_heatmaps)

        self.act_view_focus_multivar = QtGui.QAction("Focus Multivariate", self)
        self.act_view_focus_multivar.setObjectName("act_view_focus_multivar")
        self.act_view_focus_multivar.setShortcut("Ctrl+Shift+2")
        self.act_view_focus_multivar.triggered.connect(lambda: self._activate_workspace_focus_mode("multivariate"))
        layout_menu.addAction(self.act_view_focus_multivar)

        self.act_view_focus_qa = QtGui.QAction("Focus QA / Events", self)
        self.act_view_focus_qa.setObjectName("act_view_focus_qa")
        self.act_view_focus_qa.setShortcut("Ctrl+Shift+3")
        self.act_view_focus_qa.triggered.connect(lambda: self._activate_workspace_focus_mode("qa"))
        layout_menu.addAction(self.act_view_focus_qa)

        self.act_view_focus_hint = QtGui.QAction("Follow Weakest Link", self)
        self.act_view_focus_hint.setObjectName("act_view_focus_hint")
        self.act_view_focus_hint.setShortcut("Ctrl+Shift+4")
        self.act_view_focus_hint.triggered.connect(self._follow_workspace_heuristic_focus)
        layout_menu.addAction(self.act_view_focus_hint)

        analysis_menu = view_menu.addMenu("Analysis Lens")
        self.menu_view_analysis = analysis_menu
        self._workspace_analysis_action_group = QtGui.QActionGroup(self)
        self._workspace_analysis_action_group.setExclusive(True)

        self.act_view_analysis_one_to_all = QtGui.QAction("1 -> all", self)
        self.act_view_analysis_one_to_all.setObjectName("act_view_analysis_one_to_all")
        self.act_view_analysis_one_to_all.setCheckable(True)
        self.act_view_analysis_one_to_all.setShortcut("Ctrl+Alt+1")
        self.act_view_analysis_one_to_all.triggered.connect(lambda: self._set_workspace_analysis_mode("one_to_all"))
        self._workspace_analysis_action_group.addAction(self.act_view_analysis_one_to_all)
        analysis_menu.addAction(self.act_view_analysis_one_to_all)

        self.act_view_analysis_all_to_one = QtGui.QAction("all -> 1", self)
        self.act_view_analysis_all_to_one.setObjectName("act_view_analysis_all_to_one")
        self.act_view_analysis_all_to_one.setCheckable(True)
        self.act_view_analysis_all_to_one.setShortcut("Ctrl+Alt+2")
        self.act_view_analysis_all_to_one.triggered.connect(lambda: self._set_workspace_analysis_mode("all_to_one"))
        self._workspace_analysis_action_group.addAction(self.act_view_analysis_all_to_one)
        analysis_menu.addAction(self.act_view_analysis_all_to_one)

        self.act_view_analysis_all_to_all = QtGui.QAction("all -> all", self)
        self.act_view_analysis_all_to_all.setObjectName("act_view_analysis_all_to_all")
        self.act_view_analysis_all_to_all.setCheckable(True)
        self.act_view_analysis_all_to_all.setShortcut("Ctrl+Alt+3")
        self.act_view_analysis_all_to_all.triggered.connect(lambda: self._set_workspace_analysis_mode("all_to_all"))
        self._workspace_analysis_action_group.addAction(self.act_view_analysis_all_to_all)
        analysis_menu.addAction(self.act_view_analysis_all_to_all)

        docks_menu = view_menu.addMenu("Docks")
        self.menu_view_docks = docks_menu
        dock_specs = (
            ("Controls", getattr(self, "dock_controls", None)),
            ("Δ(t) Heatmap", getattr(self, "dock_heatmap", None)),
            ("Peak |Δ| Heatmap", getattr(self, "dock_peak_heatmap", None)),
            ("Valves (open) timeline", getattr(self, "dock_open_timeline", None)),
            ("Influence(t)", getattr(self, "dock_influence", None)),
            ("Run metrics", getattr(self, "dock_run_metrics", None)),
            ("Static (t0) / stroke check", getattr(self, "dock_static_stroke", None)),
            ("Influence(t) Heatmap", getattr(self, "dock_inflheat", None)),
            ("Multivariate", getattr(self, "dock_multivar", None)),
            ("QA", getattr(self, "dock_qa", None)),
            ("Events", getattr(self, "dock_events", None)),
            ("Geometry acceptance", getattr(self, "dock_geometry_acceptance", None)),
        )
        for text, dock in dock_specs:
            if not isinstance(dock, QtWidgets.QDockWidget):
                continue
            act = dock.toggleViewAction()
            act.setText(text)
            docks_menu.addAction(act)

        self._sync_workspace_analysis_actions()
        self._update_workspace_analysis_action_hints()



    # ---------------- trust banner (yellow/red) ----------------
    def _update_trust_banner(self, runs: List['Run'], sigs: List[str]):
        if not hasattr(self, 'lbl_trust') or self.lbl_trust is None:
            return
        if trust_inspect_runs is None or format_banner_text is None:
            # trust module not available
            self.lbl_trust.setVisible(False)
            return
        try:
            run_tuples = [(r.label, {'tables': r.tables, 'meta': r.meta}) for r in (runs or [])]
            issues = trust_inspect_runs(run_tuples, table=str(self.current_table), signals=list(sigs) if sigs else None)
        except Exception:
            self.lbl_trust.setVisible(False)
            return

        if not issues:
            self.lbl_trust.setVisible(False)
            return

        try:
            worst = 'warn'
            for it in issues:
                if getattr(it, 'level', '') == 'error':
                    worst = 'error'
                    break
            txt = format_banner_text(issues, max_lines=6)

            if worst == 'error':
                self.lbl_trust.setStyleSheet(
                    'QLabel{background:#ffd6d6;border:1px solid #cc0000;color:#330000;padding:6px;border-radius:6px;}'
                )
            else:
                self.lbl_trust.setStyleSheet(
                    'QLabel{background:#fff1c2;border:1px solid #cc8a00;color:#332200;padding:6px;border-radius:6px;}'
                )
            self.lbl_trust.setText(txt)
            self.lbl_trust.setVisible(True)
        except Exception:
            self.lbl_trust.setVisible(False)
            return


    # ---------------- Δ(t) Heatmap (3D cube → ImageView) ----------------
    def _heatmap_default_note(self) -> str:
        return (
            "Rows = Signals (в порядке выбора), Cols = Runs (в порядке выбора).\n"
            "Наведи мышь на ячейку: покажу полные подписи."
        )

    def _heatmap_status_text(
        self,
        *,
        metric: str,
        mode: str,
        ref_label: str,
        runs_count: int,
        sigs_count: int,
        hotspot_signal: str,
        hotspot_run: str,
        hotspot_time: float,
        hotspot_peak: float,
    ) -> str:
        mode_txt = f"Δ vs {ref_label}" if str(mode) == "delta" else "value"
        line1 = (
            f"Rows=Signals | Cols=Runs | metric={metric} | mode={mode_txt} | "
            f"runs={int(runs_count)} | signals={int(sigs_count)}"
        )
        if hotspot_signal and hotspot_run and np.isfinite(float(hotspot_time)) and np.isfinite(float(hotspot_peak)):
            line2 = (
                f"Hotspot: {hotspot_signal} in {hotspot_run} @ {float(hotspot_time):.4f}s "
                f"(peak {float(hotspot_peak):.3g})"
            )
        else:
            line2 = "Hotspot: move through time to find the strongest local divergence."

        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if analysis_mode == "one_to_all":
            hint = "Use the hotspot as a gate, then check Influence(t) to see whether one driver fans out across nearby signals."
        elif analysis_mode == "all_to_one":
            target_sig = self._workspace_analysis_target_signal([str(hotspot_signal)]) if str(hotspot_signal or "").strip() else ""
            hint = (
                f"Treat {target_sig or hotspot_signal or 'the hotspot signal'} as the target and test which drivers still explain it around this time."
            )
        else:
            hint = "Use the hotspot as a time-local gate, then compare it against cloud clusters and the dominant influence corridor."
        line3 = f"Heuristic: {hint}"
        return "\n".join([line1, line2, line3])

    def _build_heatmap_dock(self):
        dock = QtWidgets.QDockWidget("Δ(t) Heatmap", self)
        dock.setObjectName("dock_deltat_heatmap")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea
        )

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.chk_heatmap = QtWidgets.QCheckBox("Enable Δ(t) heatmap (3D cube → ImageView)")
        self.chk_heatmap.setChecked(bool(getattr(self, "heat_enabled", True)))
        self.chk_heatmap.setToolTip(
            "Показывает матрицу (signals × runs) во времени.\n"
            "Строки = выбранные Signals, столбцы = выбранные Runs."
        )
        self.chk_heatmap.stateChanged.connect(self._rebuild_heatmap)
        lay.addWidget(self.chk_heatmap)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Metric"))
        self.combo_heat_metric = QtWidgets.QComboBox()
        self.combo_heat_metric.addItems(["signed Δ", "|Δ|", "|Δ| / amp(ref)"])
        self.combo_heat_metric.setCurrentText(str(getattr(self, "heat_metric", "signed Δ")))
        self.combo_heat_metric.setToolTip(
            "signed Δ: со знаком (полезно для направления)\n"
            "|Δ|: модуль (быстро видны зоны различий)\n"
            "|Δ| / amp(ref): относительный модуль (нормировка по reference)"
        )
        self.combo_heat_metric.currentIndexChanged.connect(self._rebuild_heatmap)
        row.addWidget(self.combo_heat_metric, stretch=1)
        lay.addLayout(row)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("Max signals"))
        self.spin_heat_sigs = QtWidgets.QSpinBox()
        self.spin_heat_sigs.setRange(2, 30)
        self.spin_heat_sigs.setSingleStep(1)
        self.spin_heat_sigs.setValue(int(getattr(self, "heat_max_sigs", 12) or 12))
        self.spin_heat_sigs.setToolTip("Ограничение читаемости/производительности")
        self.spin_heat_sigs.valueChanged.connect(self._rebuild_heatmap)
        row2.addWidget(self.spin_heat_sigs)

        row2.addWidget(QtWidgets.QLabel("LOD time pts"))
        self.spin_heat_tpts = QtWidgets.QSpinBox()
        self.spin_heat_tpts.setRange(200, 12000)
        self.spin_heat_tpts.setSingleStep(200)
        self.spin_heat_tpts.setValue(int(getattr(self, "heat_max_time_points", 2500) or 2500))
        self.spin_heat_tpts.setToolTip("LOD по времени: ограничивает размер куба")
        self.spin_heat_tpts.valueChanged.connect(self._rebuild_heatmap)
        row2.addWidget(self.spin_heat_tpts)
        lay.addLayout(row2)

        self.lbl_heat_note = QtWidgets.QLabel(self._heatmap_default_note())
        self.lbl_heat_note.setWordWrap(True)
        lay.addWidget(self.lbl_heat_note)

        self.imv_heat = None
        self._heat_proxy = None
        self.lbl_heat_readout = QtWidgets.QLabel("")
        self.lbl_heat_readout.setWordWrap(True)

        if pg is None or build_deltat_cube is None:
            lay.addWidget(QtWidgets.QLabel("Heatmap unavailable: pyqtgraph / build_deltat_cube not found"))
        else:
            try:
                # PlotItem -> axes; ImageView handles 3D cube with internal timeline
                self.imv_heat = pg.ImageView(view=pg.PlotItem())
                try:
                    self.imv_heat.ui.roiBtn.hide()
                    self.imv_heat.ui.menuBtn.hide()
                except Exception:
                    pass
                try:
                    self.imv_heat.setEnabled(False)
                except Exception:
                    pass
                lay.addWidget(self.imv_heat, stretch=1)
                lay.addWidget(self.lbl_heat_readout)
                try:
                    self._heat_proxy = pg.SignalProxy(
                        self.imv_heat.getView().scene().sigMouseMoved,
                        rateLimit=60,
                        slot=self._on_heatmap_mouse_moved,
                    )
                except Exception:
                    self._heat_proxy = None

                try:
                    self.imv_heat.getView().scene().sigMouseClicked.connect(self._on_heatmap_mouse_clicked)
                except Exception:
                    pass
            except Exception as e:
                self.imv_heat = None
                lay.addWidget(QtWidgets.QLabel(f"Heatmap init failed: {e}"))

        dock.setWidget(w)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.dock_heatmap = dock

        # state
        self._heat_t = np.zeros(0, dtype=float)
        self._heat_run_labels = []
        self._heat_sig_labels = []
        self._heat_enabled = True

    def _rebuild_heatmap(self):
        # Recompute Δ(t) cube and push it into ImageView.
        if not hasattr(self, "chk_heatmap"):
            return
        self.heat_enabled = bool(self.chk_heatmap.isChecked())
        if not self.chk_heatmap.isChecked():
            self._clear_heatmap_view()
            return

        if self.imv_heat is None or build_deltat_cube is None:
            return

        runs = self._ordered_runs_for_reference(self._selected_runs())
        sigs = self._selected_signals()
        if not runs or not sigs:
            self._clear_heatmap_view("Выберите хотя бы один прогон и один сигнал.")
            return
        self._heat_enabled = True
        ref = runs[0]

        max_sigs = int(self.spin_heat_sigs.value()) if hasattr(self, "spin_heat_sigs") else 12
        sigs_use = list(sigs)[:max_sigs]

        # Build minimal bundle-like dicts
        run_tuples = [(r.label, {"tables": r.tables, "meta": r.meta}) for r in runs]

        # Mode: if UI is in delta mode -> Δ; else show absolute values.
        mode = "delta" if bool(self.chk_delta.isChecked()) else "value"

        try:
            cube_obj = build_deltat_cube(
                run_tuples,
                table=str(self.current_table),
                sigs=sigs_use,
                ref_label=str(ref.label),
                mode=mode,
                dist_unit=str(self.dist_unit),
                angle_unit=str(self.angle_unit),
                P_ATM=float(getattr(self, "p_atm", getattr(self, "P_ATM", 100000.0))),
                BAR_PA=float(getattr(self, "BAR_PA", 100000.0)),
                baseline_mode=str(self.baseline_mode),
                baseline_window_s=float(self.baseline_window_s),
                baseline_first_n=int(getattr(self, "baseline_first_n", 0) or 0),
                zero_positions=bool(self.zero_baseline),
                flow_unit=str(getattr(self, "flow_unit", "raw") or "raw"),
                time_window=None,
                max_time_points=int(self.spin_heat_tpts.value()) if hasattr(self, "spin_heat_tpts") else 2500,
            )
        except Exception:
            self._clear_heatmap_view("Δ(t) heatmap: не удалось пересчитать текущий выбор.")
            return

        if cube_obj is None or np.asarray(getattr(cube_obj, "t", np.asarray([])), dtype=float).size < 1:
            self._clear_heatmap_view("Δ(t) heatmap: нет данных для отображения.")
            return

        tH = np.asarray(cube_obj.t, dtype=float)
        Z = np.asarray(cube_obj.cube, dtype=float)  # (T, n_sig, n_run)
        if Z.size == 0:
            self._clear_heatmap_view("Δ(t) heatmap: нет данных для отображения.")
            return
        if not np.isfinite(Z).any():
            self._clear_heatmap_view("Δ(t) heatmap: текущий выбор даёт только NaN/пустые значения.")
            return

        metric = str(self.combo_heat_metric.currentText() if hasattr(self, "combo_heat_metric") else "signed Δ")

        if metric.startswith("|Δ| /") and mode == "delta":
            # relative scaling by reference amplitude
            try:
                ref_only = build_deltat_cube(
                    [(ref.label, {"tables": ref.tables, "meta": ref.meta})],
                    table=str(self.current_table),
                    sigs=sigs_use,
                    ref_label=str(ref.label),
                    mode="value",
                    dist_unit=str(self.dist_unit),
                    angle_unit=str(self.angle_unit),
                    P_ATM=float(getattr(self, "p_atm", getattr(self, "P_ATM", 100000.0))),
                    BAR_PA=float(getattr(self, "BAR_PA", 100000.0)),
                    baseline_mode=str(self.baseline_mode),
                    baseline_window_s=float(self.baseline_window_s),
                    baseline_first_n=int(getattr(self, "baseline_first_n", 0) or 0),
                    zero_positions=bool(self.zero_baseline),
                    flow_unit=str(getattr(self, "flow_unit", "raw") or "raw"),
                    time_window=None,
                    max_time_points=int(self.spin_heat_tpts.value()) if hasattr(self, "spin_heat_tpts") else 2500,
                )
                amp = np.nanmax(np.abs(np.asarray(ref_only.cube, dtype=float)[:, :, 0]), axis=0)
                amp = np.where(np.isfinite(amp) & (amp > 0), amp, 1.0)
                Z = np.abs(Z) / amp.reshape(1, -1, 1)
            except Exception:
                Z = np.abs(Z)
        elif metric.startswith("|Δ|"):
            Z = np.abs(Z)

        # robust levels for consistent perception
        z_vals = np.abs(Z[np.isfinite(Z)]) if np.isfinite(Z).any() else np.asarray([0.0])
        if z_vals.size:
            zmax = float(np.nanpercentile(z_vals, 98))
            if not np.isfinite(zmax) or zmax <= 0:
                zmax = float(np.nanmax(z_vals)) if z_vals.size else 1.0
        else:
            zmax = 1.0

        signed = metric.startswith("signed") and mode == "delta"
        levels = (-zmax, zmax) if signed else (0.0, zmax)

        # ImageView expects (t, x, y) with default axes; we want x=runs, y=signals
        img = np.transpose(Z, (0, 2, 1))  # (T, n_run, n_sig)

        self._heat_t = tH
        self._heat_run_labels = list(cube_obj.run_labels)
        self._heat_sig_labels = list(cube_obj.sigs)
        try:
            absZ = np.abs(np.asarray(Z, dtype=float))
            absZ = np.nan_to_num(absZ, nan=-1.0, posinf=-1.0, neginf=-1.0)
            flat_idx = int(np.argmax(absZ))
            it_hot, isig_hot, irun_hot = np.unravel_index(flat_idx, absZ.shape)
            self._insight_heat = {
                "signal": self._heat_sig_labels[isig_hot] if 0 <= isig_hot < len(self._heat_sig_labels) else "",
                "run": self._heat_run_labels[irun_hot] if 0 <= irun_hot < len(self._heat_run_labels) else "",
                "time_s": float(tH[it_hot]) if 0 <= it_hot < len(tH) else float("nan"),
                "peak": float(absZ[it_hot, isig_hot, irun_hot]) if absZ.size else float("nan"),
                "metric": metric,
                "mode": mode,
            }
        except Exception:
            self._insight_heat = {}

        try:
            self.imv_heat.setImage(img, xvals=tH, autoLevels=False)
        except TypeError:
            self.imv_heat.setImage(img, xvals=tH)
        try:
            self.imv_heat.setEnabled(True)
        except Exception:
            pass

        try:
            self.imv_heat.setLevels(levels)
        except Exception:
            pass
        try:
            heat_info = dict(getattr(self, "_insight_heat", {}) or {})
            self.lbl_heat_note.setText(
                self._heatmap_status_text(
                    metric=metric,
                    mode=mode,
                    ref_label=str(ref.label),
                    runs_count=len(runs),
                    sigs_count=len(sigs_use),
                    hotspot_signal=str(heat_info.get("signal") or ""),
                    hotspot_run=str(heat_info.get("run") or ""),
                    hotspot_time=float(heat_info.get("time_s", float("nan")) or float("nan")),
                    hotspot_peak=float(heat_info.get("peak", float("nan")) or float("nan")),
                )
            )
        except Exception:
            pass
        try:
            self.lbl_heat_readout.setText("")
        except Exception:
            pass

        # sync to current playhead time
        try:
            if hasattr(self, "_t_ref") and self._t_ref.size and hasattr(self, "slider_time"):
                idx = int(self.slider_time.value())
                idx = max(0, min(idx, int(self._t_ref.size - 1)))
                self._sync_heatmap_to_time(float(self._t_ref[idx]))
        except Exception:
            pass
        self._update_workspace_status()

    def _clear_heatmap_view(self, note: str = "") -> None:
        self._heat_t = np.zeros(0, dtype=float)
        self._heat_run_labels = []
        self._heat_sig_labels = []
        self._heat_enabled = False
        self._insight_heat = {}
        try:
            if self.imv_heat is not None:
                blank = np.zeros((1, 1, 1), dtype=float)
                try:
                    self.imv_heat.setImage(blank, xvals=np.asarray([0.0], dtype=float), autoLevels=False)
                except TypeError:
                    self.imv_heat.setImage(blank, xvals=np.asarray([0.0], dtype=float))
                try:
                    self.imv_heat.setEnabled(False)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.lbl_heat_note.setText(str(note or self._heatmap_default_note()))
        except Exception:
            pass
        try:
            self.lbl_heat_readout.setText(str(note or ""))
        except Exception:
            pass
        self._update_workspace_status()

    def _sync_heatmap_to_time(self, t: float):
        if self.imv_heat is None:
            return
        if self._heat_t is None or np.asarray(self._heat_t).size == 0:
            return
        try:
            idx = int(np.argmin(np.abs(np.asarray(self._heat_t, dtype=float) - float(t))))
            idx = max(0, min(idx, int(len(self._heat_t) - 1)))
            if hasattr(self.imv_heat, "setCurrentIndex"):
                self.imv_heat.setCurrentIndex(idx)
        except Exception:
            return

    def _on_heatmap_mouse_moved(self, evt):
        if self.imv_heat is None:
            return
        try:
            pos = evt[0] if isinstance(evt, (tuple, list)) else evt
            vb = self.imv_heat.getView()
            p = vb.mapSceneToView(pos)
            x = float(p.x())
            y = float(p.y())
            ix = int(np.clip(round(x), 0, max(0, len(self._heat_run_labels) - 1)))
            iy = int(np.clip(round(y), 0, max(0, len(self._heat_sig_labels) - 1)))
            run_lab = self._heat_run_labels[ix] if self._heat_run_labels else str(ix)
            sig_lab = self._heat_sig_labels[iy] if self._heat_sig_labels else str(iy)

            tidx = None
            try:
                tidx = int(self.imv_heat.currentIndex)
            except Exception:
                tidx = None

            t_txt = ""
            if tidx is not None and np.asarray(self._heat_t).size:
                tidx = max(0, min(tidx, int(len(self._heat_t) - 1)))
                t_txt = f"t={float(self._heat_t[tidx]):.4f}s"

            self.lbl_heat_readout.setText(f"{t_txt}   run[{ix}]={run_lab}   sig[{iy}]={sig_lab}")
        except Exception:
            return

    # ---------------- data ----------------
    def _on_heatmap_mouse_clicked(self, event):
        # Click on heatmap cell -> focus signal/run (non-destructive)
        if self.imv_heat is None or not self._heat_run_labels or not self._heat_sig_labels:
            return
        try:
            pos = event.scenePos() if hasattr(event, 'scenePos') else None
            if pos is None:
                return
            vb = self.imv_heat.getView()
            p = vb.mapSceneToView(pos)
            x, y = float(p.x()), float(p.y())
            ix, iy = int(round(x)), int(round(y))
            if iy < 0 or iy >= len(self._heat_sig_labels):
                return
            if ix < 0 or ix >= len(self._heat_run_labels):
                return
            sig_lab = self._heat_sig_labels[iy]
            run_lab = self._heat_run_labels[ix]
            target_run_row = -1
            if hasattr(self, 'list_runs'):
                for i in range(self.list_runs.count()):
                    it = self.list_runs.item(i)
                    if it is not None and str(it.text()) == str(run_lab):
                        target_run_row = i
                        break
            if (not self._signal_exists_in_current_context(str(sig_lab))) or target_run_row < 0:
                return
            # Add signal to selection and move current focus without altering multi-select state.
            if not self._select_signal_by_name(str(sig_lab), exclusive=False):
                return
            run_added = False
            if hasattr(self, 'list_runs'):
                try:
                    self.list_runs.blockSignals(True)
                    it = self.list_runs.item(target_run_row)
                    if it is not None:
                        if not it.isSelected():
                            it.setSelected(True)
                            run_added = True
                        self._set_current_list_row(self.list_runs, target_run_row)
                    self._runs_selection_explicit = True
                    self.runs_selected_paths = [
                        self._normalized_run_path(getattr(run, 'path', Path('')))
                        for run in self._selected_runs()
                    ]
                finally:
                    self.list_runs.blockSignals(False)
            if run_added:
                self._on_run_selection_changed()
            else:
                self._rebuild_plots()
        except Exception:
            return

    def _peak_heat_default_note(self) -> str:
        return (
            "Peak |Δ| heatmap: rows = Signals, cols = Runs. "
            "Each cell stores the strongest absolute deviation from the reference run over time. "
            "Click a cell to focus run/signal and jump to the peak time."
        )

    def _peak_heat_color(self, value: float, vmax: float, *, is_ref: bool = False) -> QtGui.QColor:
        if is_ref:
            return QtGui.QColor(255, 240, 214)
        if not np.isfinite(value):
            return QtGui.QColor(245, 245, 245)
        scale = float(vmax) if np.isfinite(vmax) and float(vmax) > 0.0 else 1.0
        alpha = float(np.clip(abs(float(value)) / scale, 0.0, 1.0))
        warm = int(170 * alpha)
        return QtGui.QColor(255, 252 - warm, 236 - int(80 * alpha))

    def _peak_heat_status_text(
        self,
        *,
        ref_label: str,
        table_name: str,
        runs_count: int,
        sigs_count: int,
        hotspot_signal: str,
        hotspot_run: str,
        hotspot_time: float,
        hotspot_value: float,
        hotspot_unit: str,
    ) -> Tuple[str, str]:
        unit_txt = f" [{hotspot_unit}]" if str(hotspot_unit or "").strip() else ""
        line1 = (
            f"Peak |Δ| vs ref={ref_label or '—'} | table={table_name or '—'} | "
            f"runs={int(runs_count)} | signals={int(sigs_count)}"
        )
        if hotspot_signal and hotspot_run and np.isfinite(float(hotspot_value)):
            line2 = (
                f"Hotspot: {hotspot_signal} in {hotspot_run} @ {float(hotspot_time):.3f}s = "
                f"{float(hotspot_value):.6g}{unit_txt}"
            )
        else:
            line2 = "No finite peak cells in the current compare context."
        mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if mode == "one_to_all":
            hint = "Use this surface to spot which response lights up hardest before opening Δ(t) or Influence(t)."
        elif mode == "all_to_one":
            hint = "Use this surface to check whether the target split is broad or concentrated in a few extreme runs."
        else:
            hint = "Use this surface as a coarse gate before time-local Δ(t) slices and all-to-all cloud structure."
        return line1, f"{line2}\nHeuristic: {hint}"

    def _build_peak_heatmap_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Peak |Δ| heatmap", self)
        dock.setObjectName("dock_peak_heatmap")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea
        )

        root = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.lbl_peak_heat_note = QtWidgets.QLabel(self._peak_heat_default_note())
        self.lbl_peak_heat_note.setWordWrap(True)
        lay.addWidget(self.lbl_peak_heat_note)

        self.lbl_peak_heat_stats = QtWidgets.QLabel("")
        self.lbl_peak_heat_stats.setWordWrap(True)
        self.lbl_peak_heat_stats.setStyleSheet("color:#666;")
        lay.addWidget(self.lbl_peak_heat_stats)

        self.tbl_peak_heat = QtWidgets.QTableWidget()
        self.tbl_peak_heat.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tbl_peak_heat.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_peak_heat.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_peak_heat.setAlternatingRowColors(True)
        self.tbl_peak_heat.setEnabled(False)
        try:
            self.tbl_peak_heat.cellClicked.connect(self._on_peak_heat_cell_clicked)
        except Exception:
            pass
        lay.addWidget(self.tbl_peak_heat, 1)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        try:
            if hasattr(self, "dock_heatmap") and self.dock_heatmap is not None:
                self.tabifyDockWidget(self.dock_heatmap, dock)
        except Exception:
            pass
        self.dock_peak_heatmap = dock
        self._clear_peak_heatmap_view()

    def _clear_peak_heatmap_view(self, note: str = "") -> None:
        self._peak_cache = None
        self._insight_peak_heat = {}
        try:
            if getattr(self, "tbl_peak_heat", None) is not None:
                self.tbl_peak_heat.clear()
                self.tbl_peak_heat.setRowCount(0)
                self.tbl_peak_heat.setColumnCount(0)
                self.tbl_peak_heat.setEnabled(False)
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_peak_heat_note"):
                self.lbl_peak_heat_note.setText(str(note or self._peak_heat_default_note()))
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_peak_heat_stats"):
                self.lbl_peak_heat_stats.setText("")
        except Exception:
            pass
        self._update_workspace_status()

    def _schedule_peak_heatmap_rebuild(self, *_args, delay_ms: int = 120) -> None:
        timer = getattr(self, "_peak_timer", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        try:
            timer.start(int(delay_ms))
        except Exception:
            pass

    def _rebuild_peak_heatmap(self) -> None:
        tbl = getattr(self, "tbl_peak_heat", None)
        if tbl is None:
            return
        runs = self._ordered_runs_for_reference(self._selected_runs())
        if len(runs) < 2:
            self._clear_peak_heatmap_view("Peak |Δ| heatmap: выберите минимум два прогона.")
            return
        sigs = list(self._selected_signals())
        if not sigs:
            self._clear_peak_heatmap_view("Peak |Δ| heatmap: выберите хотя бы один сигнал.")
            return
        table_name = str(getattr(self, "current_table", "") or "").strip()
        if not table_name:
            self._clear_peak_heatmap_view("Peak |Δ| heatmap: выберите общую таблицу.")
            return

        ref_run = runs[0]
        run_labels = [str(getattr(run, "label", "") or "") for run in runs]
        sig_labels = [str(sig) for sig in sigs]
        values = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        peak_times = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        signed_peaks = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        unit_map: Dict[str, str] = {}

        for i_sig, sig in enumerate(sig_labels):
            x_ref, y_ref, unit = self._get_xy(ref_run, sig)
            unit_map[str(sig)] = str(unit or "")
            if x_ref.size == 0 or y_ref.size == 0:
                continue
            x_ref = np.asarray(x_ref, dtype=float)
            y_ref = np.asarray(y_ref, dtype=float)
            ref_mask = np.isfinite(x_ref) & np.isfinite(y_ref)
            if not np.any(ref_mask):
                continue
            x_use = x_ref[ref_mask]
            y_ref_use = y_ref[ref_mask]
            if x_use.size <= 0:
                continue
            values[i_sig, 0] = 0.0
            signed_peaks[i_sig, 0] = 0.0
            peak_times[i_sig, 0] = float(x_use[0])
            for j_run, run in enumerate(runs[1:], start=1):
                x, y, _u = self._get_xy(run, sig)
                if x.size == 0 or y.size == 0:
                    continue
                try:
                    y_interp = np.interp(x_use, np.asarray(x, dtype=float), np.asarray(y, dtype=float), left=np.nan, right=np.nan)
                except Exception:
                    continue
                delta = np.asarray(y_interp, dtype=float) - y_ref_use
                mask = np.isfinite(delta)
                if not np.any(mask):
                    continue
                idxs = np.flatnonzero(mask)
                abs_delta = np.abs(delta[idxs])
                if abs_delta.size <= 0:
                    continue
                best_rel = int(np.argmax(abs_delta))
                best_idx = int(idxs[best_rel])
                values[i_sig, j_run] = float(abs_delta[best_rel])
                signed_peaks[i_sig, j_run] = float(delta[best_idx])
                peak_times[i_sig, j_run] = float(x_use[best_idx])

        finite_vals = values[np.isfinite(values)]
        non_ref_vals = values[:, 1:] if values.shape[1] > 1 else np.asarray([], dtype=float)
        finite_non_ref = non_ref_vals[np.isfinite(non_ref_vals)]
        if finite_non_ref.size <= 0:
            self._clear_peak_heatmap_view("Peak |Δ| heatmap: нет конечных отклонений относительно reference.")
            return

        vmax = float(np.nanpercentile(finite_non_ref, 98))
        if not np.isfinite(vmax) or vmax <= 0.0:
            vmax = float(np.nanmax(finite_non_ref)) if finite_non_ref.size else 1.0
        if not np.isfinite(vmax) or vmax <= 0.0:
            vmax = 1.0

        try:
            tbl.setSortingEnabled(False)
            tbl.clear()
            tbl.setRowCount(len(sig_labels))
            tbl.setColumnCount(len(run_labels))
            tbl.setHorizontalHeaderLabels([_trim_label(label, 18) for label in run_labels])
            tbl.setVerticalHeaderLabels([_trim_label(label, 24) for label in sig_labels])
            for col, run_label in enumerate(run_labels):
                item = tbl.horizontalHeaderItem(col)
                if item is not None:
                    item.setToolTip(str(run_label))
            for row, sig in enumerate(sig_labels):
                item = tbl.verticalHeaderItem(row)
                if item is not None:
                    item.setToolTip(str(sig))
            for row, sig in enumerate(sig_labels):
                unit = str(unit_map.get(sig, "") or "")
                unit_txt = f" [{unit}]" if unit else ""
                for col, run_label in enumerate(run_labels):
                    value = float(values[row, col])
                    time_s = float(peak_times[row, col])
                    signed_delta = float(signed_peaks[row, col])
                    text = "" if not np.isfinite(value) else f"{value:.4g}"
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setBackground(self._peak_heat_color(value, vmax, is_ref=(col == 0)))
                    if np.isfinite(value):
                        tooltip = (
                            f"sig: {sig}\n"
                            f"run: {run_label}\n"
                            f"ref: {ref_run.label}\n"
                            f"peak |Δ|: {value:.6g}{unit_txt}\n"
                            f"signed Δ @ peak: {signed_delta:.6g}{unit_txt}\n"
                            f"t_peak: {time_s:.6f} s\n"
                            f"table: {table_name}"
                        )
                    else:
                        tooltip = (
                            f"sig: {sig}\nrun: {run_label}\nref: {ref_run.label}\n"
                            f"No finite peak |Δ| in table {table_name}."
                        )
                    item.setToolTip(tooltip)
                    item.setData(
                        QtCore.Qt.UserRole,
                        {
                            "run": run_label,
                            "signal": sig,
                            "time_s": time_s,
                            "peak": value,
                            "signed_delta": signed_delta,
                            "unit": unit,
                            "is_ref": bool(col == 0),
                        },
                    )
                    tbl.setItem(row, col, item)
            try:
                hdr = tbl.horizontalHeader()
                hdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
                tbl.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            except Exception:
                pass
            tbl.setEnabled(True)
        except Exception:
            self._clear_peak_heatmap_view("Peak |Δ| heatmap: не удалось собрать таблицу.")
            return

        hotspot_vals = np.asarray(values[:, 1:], dtype=float)
        hotspot_times = np.asarray(peak_times[:, 1:], dtype=float)
        hotspot_signed = np.asarray(signed_peaks[:, 1:], dtype=float)
        hotspot_vals = np.where(np.isfinite(hotspot_vals), hotspot_vals, np.nan)
        flat_idx = int(np.nanargmax(hotspot_vals))
        hot_row, hot_col_rel = np.unravel_index(flat_idx, hotspot_vals.shape)
        hot_col = int(hot_col_rel + 1)
        hotspot_signal = sig_labels[hot_row] if 0 <= hot_row < len(sig_labels) else ""
        hotspot_run = run_labels[hot_col] if 0 <= hot_col < len(run_labels) else ""
        hotspot_time = float(hotspot_times[hot_row, hot_col_rel]) if hotspot_times.size else float("nan")
        hotspot_peak = float(hotspot_vals[hot_row, hot_col_rel]) if hotspot_vals.size else float("nan")
        hotspot_signed = float(hotspot_signed[hot_row, hot_col_rel]) if hotspot_signed.size else float("nan")
        hotspot_unit = str(unit_map.get(hotspot_signal, "") or "")

        self._peak_cache = {
            "ref_label": str(ref_run.label),
            "table_name": table_name,
            "runs": list(run_labels),
            "signals": list(sig_labels),
            "values": values,
            "times": peak_times,
            "signed": signed_peaks,
            "units": dict(unit_map),
        }
        self._insight_peak_heat = {
            "signal": hotspot_signal,
            "run": hotspot_run,
            "time_s": hotspot_time,
            "peak": hotspot_peak,
            "signed_delta": hotspot_signed,
            "unit": hotspot_unit,
            "ref_label": str(ref_run.label),
            "table_name": table_name,
        }

        line1, line2 = self._peak_heat_status_text(
            ref_label=str(ref_run.label),
            table_name=table_name,
            runs_count=len(run_labels),
            sigs_count=len(sig_labels),
            hotspot_signal=hotspot_signal,
            hotspot_run=hotspot_run,
            hotspot_time=hotspot_time,
            hotspot_value=hotspot_peak,
            hotspot_unit=hotspot_unit,
        )
        try:
            self.lbl_peak_heat_note.setText(line1)
        except Exception:
            pass
        try:
            self.lbl_peak_heat_stats.setText(line2)
        except Exception:
            pass
        self._update_workspace_status()

    def _on_peak_heat_cell_clicked(self, row: int, col: int) -> None:
        tbl = getattr(self, "tbl_peak_heat", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), int(col))
        except Exception:
            item = None
        if item is None:
            return
        try:
            payload = item.data(QtCore.Qt.UserRole) or {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return
        run_label = str(payload.get("run") or "").strip()
        sig = str(payload.get("signal") or "").strip()
        if not run_label or not sig:
            return
        target_run_row = -1
        if hasattr(self, "list_runs"):
            for i in range(self.list_runs.count()):
                it = self.list_runs.item(i)
                if it is not None and str(it.text()) == run_label:
                    target_run_row = i
                    break
        if (not self._signal_exists_in_current_context(sig)) or target_run_row < 0:
            return
        if not self._select_signal_by_name(sig, exclusive=False):
            return
        run_added = False
        if hasattr(self, "list_runs"):
            try:
                self.list_runs.blockSignals(True)
                it = self.list_runs.item(target_run_row)
                if it is not None:
                    if not it.isSelected():
                        it.setSelected(True)
                        run_added = True
                    self._set_current_list_row(self.list_runs, target_run_row)
                self._runs_selection_explicit = True
                self.runs_selected_paths = [
                    self._normalized_run_path(getattr(run, "path", Path("")))
                    for run in self._selected_runs()
                ]
            finally:
                try:
                    self.list_runs.blockSignals(False)
                except Exception:
                    pass
        if run_added:
            self._on_run_selection_changed()
        else:
            self._rebuild_plots()
        try:
            t_peak = float(payload.get("time_s", np.nan))
            if np.isfinite(t_peak):
                self._set_playhead_time(t_peak)
        except Exception:
            pass

    def _open_timeline_default_note(self) -> str:
        return (
            "Valves (open): quick discrete timeline for the current reference run. "
            "Rows come from the `open` table; click to move the playhead."
        )

    def _open_timeline_status_text(
        self,
        *,
        ref_label: str,
        valves_count: int,
        changed_count: int,
        t_min: float,
        t_max: float,
        truncated: bool,
    ) -> Tuple[str, str]:
        line1 = (
            f"Valves (open) timeline | ref={ref_label or '—'} | valves={int(valves_count)}"
            f" | changed={int(changed_count)}"
        )
        if np.isfinite(float(t_min)) and np.isfinite(float(t_max)):
            line1 = f"{line1} | t=[{float(t_min):.3f}, {float(t_max):.3f}] s"
        line2 = "Click a stripe to move the playhead."
        if truncated:
            line2 = f"{line2} The list is truncated to the current max-valves limit."
        return line1, line2

    def _open_timeline_mismatch_color(self, mismatch_ratio: float, *, is_ref: bool = False) -> QtGui.QColor:
        if is_ref:
            return QtGui.QColor(232, 236, 245)
        try:
            v = float(mismatch_ratio)
        except Exception:
            return QtGui.QColor(242, 242, 242)
        if not np.isfinite(v):
            return QtGui.QColor(242, 242, 242)
        a = max(0.0, min(1.0, v))
        red = int(230 + 25 * a)
        green = int(245 - 105 * a)
        blue = int(220 - 60 * a)
        return QtGui.QColor(red, green, blue)

    def _build_open_timeline_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Valves (open) timeline", self)
        dock.setObjectName("dock_open_timeline")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)

        root = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel("Max valves:"))
        self.spin_open_timeline_valves = QtWidgets.QSpinBox()
        self.spin_open_timeline_valves.setRange(1, 80)
        self.spin_open_timeline_valves.setSingleStep(1)
        self.spin_open_timeline_valves.setValue(40)
        self.spin_open_timeline_valves.setToolTip(
            "Upper bound for rows in the open timeline. Changed valves are prioritized first."
        )
        self.spin_open_timeline_valves.valueChanged.connect(
            lambda _=None: self._schedule_open_timeline_rebuild(delay_ms=40)
        )
        row.addWidget(self.spin_open_timeline_valves, 0)
        row.addStretch(1)
        lay.addLayout(row)

        self.lbl_open_timeline_note = QtWidgets.QLabel(self._open_timeline_default_note())
        self.lbl_open_timeline_note.setWordWrap(True)
        lay.addWidget(self.lbl_open_timeline_note)

        self.lbl_open_timeline_stats = QtWidgets.QLabel("")
        self.lbl_open_timeline_stats.setWordWrap(True)
        self.lbl_open_timeline_stats.setStyleSheet("color:#666;")
        lay.addWidget(self.lbl_open_timeline_stats)

        tabs = QtWidgets.QTabWidget()

        self.plot_open_timeline = None
        self.img_open_timeline = None
        self.line_open_timeline = None
        self._open_timeline_proxy = None
        self.lbl_open_timeline_readout = QtWidgets.QLabel("")
        self.lbl_open_timeline_readout.setWordWrap(True)
        tab_timeline = QtWidgets.QWidget()
        tl_lay = QtWidgets.QVBoxLayout(tab_timeline)
        tl_lay.setContentsMargins(6, 6, 6, 6)
        tl_lay.setSpacing(6)

        if pg is None:
            tl_lay.addWidget(QtWidgets.QLabel("Valves timeline unavailable: pyqtgraph not found"))
        else:
            try:
                self.plot_open_timeline = pg.PlotWidget()
                self.plot_open_timeline.setMinimumHeight(260)
                self.plot_open_timeline.setBackground(None)
                self.plot_open_timeline.showGrid(x=True, y=False, alpha=0.20)
                self.plot_open_timeline.setMouseEnabled(x=True, y=False)
                self.plot_open_timeline.invertY(True)
                try:
                    self.plot_open_timeline.setLabel("bottom", "t, s")
                except Exception:
                    pass
                self.plot_open_timeline.setEnabled(False)
                self.img_open_timeline = pg.ImageItem(axisOrder='row-major')
                self.plot_open_timeline.addItem(self.img_open_timeline)
                self.line_open_timeline = pg.InfiniteLine(
                    angle=90, movable=False, pen=pg.mkPen((255, 140, 0, 190), width=2)
                )
                self.plot_open_timeline.addItem(self.line_open_timeline)
                try:
                    self.line_open_timeline.hide()
                except Exception:
                    pass
                tl_lay.addWidget(self.plot_open_timeline, 1)
                tl_lay.addWidget(self.lbl_open_timeline_readout)
                try:
                    self._open_timeline_proxy = pg.SignalProxy(
                        self.plot_open_timeline.scene().sigMouseMoved,
                        rateLimit=60,
                        slot=self._on_open_timeline_mouse_moved,
                    )
                except Exception:
                    self._open_timeline_proxy = None
                try:
                    self.plot_open_timeline.scene().sigMouseClicked.connect(self._on_open_timeline_mouse_clicked)
                except Exception:
                    pass
            except Exception as e:
                self.plot_open_timeline = None
                tl_lay.addWidget(QtWidgets.QLabel(f"Valves timeline init failed: {e}"))

        tabs.addTab(tab_timeline, "Reference timeline")

        tab_mismatch = QtWidgets.QWidget()
        mm_lay = QtWidgets.QVBoxLayout(tab_mismatch)
        mm_lay.setContentsMargins(6, 6, 6, 6)
        mm_lay.setSpacing(6)
        self.lbl_open_timeline_mismatch = QtWidgets.QLabel(
            "Mismatch vs ref: rows are common valves, columns are selected runs."
        )
        self.lbl_open_timeline_mismatch.setWordWrap(True)
        self.lbl_open_timeline_mismatch.setStyleSheet("color:#666;")
        mm_lay.addWidget(self.lbl_open_timeline_mismatch)
        self.tbl_open_timeline_mismatch = QtWidgets.QTableWidget()
        self.tbl_open_timeline_mismatch.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tbl_open_timeline_mismatch.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_open_timeline_mismatch.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_open_timeline_mismatch.setAlternatingRowColors(True)
        self.tbl_open_timeline_mismatch.setEnabled(False)
        try:
            self.tbl_open_timeline_mismatch.cellClicked.connect(self._on_open_timeline_mismatch_clicked)
            self.tbl_open_timeline_mismatch.cellDoubleClicked.connect(self._on_open_timeline_mismatch_clicked)
        except Exception:
            pass
        mm_lay.addWidget(self.tbl_open_timeline_mismatch, 1)
        tabs.addTab(tab_mismatch, "Mismatch vs ref")

        lay.addWidget(tabs, 1)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        try:
            if hasattr(self, "dock_heatmap") and self.dock_heatmap is not None:
                self.tabifyDockWidget(self.dock_heatmap, dock)
        except Exception:
            pass
        self.dock_open_timeline = dock
        self._clear_open_timeline_view()

    def _clear_open_timeline_view(self, note: str = "") -> None:
        self._open_timeline_cache = None
        try:
            if getattr(self, "img_open_timeline", None) is not None:
                self.img_open_timeline.setImage(np.zeros((1, 1), dtype=float))
        except Exception:
            pass
        try:
            if getattr(self, "plot_open_timeline", None) is not None:
                self.plot_open_timeline.setEnabled(False)
                self.plot_open_timeline.getAxis("left").setTicks([[]])
        except Exception:
            pass
        try:
            if getattr(self, "line_open_timeline", None) is not None:
                self.line_open_timeline.hide()
        except Exception:
            pass
        try:
            if getattr(self, "tbl_open_timeline_mismatch", None) is not None:
                self.tbl_open_timeline_mismatch.clear()
                self.tbl_open_timeline_mismatch.setRowCount(0)
                self.tbl_open_timeline_mismatch.setColumnCount(0)
                self.tbl_open_timeline_mismatch.setEnabled(False)
        except Exception:
            pass
        try:
            self.lbl_open_timeline_note.setText(str(note or self._open_timeline_default_note()))
        except Exception:
            pass
        try:
            self.lbl_open_timeline_stats.setText("")
        except Exception:
            pass
        try:
            self.lbl_open_timeline_readout.setText("")
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_open_timeline_mismatch"):
                self.lbl_open_timeline_mismatch.setText(
                    "Mismatch vs ref: rows are common valves, columns are selected runs."
                )
        except Exception:
            pass
        self._update_workspace_status()

    def _schedule_open_timeline_rebuild(self, *_args, delay_ms: int = 120) -> None:
        timer = getattr(self, "_open_timeline_timer", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        try:
            timer.start(int(delay_ms))
        except Exception:
            pass

    def _rebuild_open_timeline_view(self) -> None:
        plot = getattr(self, "plot_open_timeline", None)
        img = getattr(self, "img_open_timeline", None)
        if plot is None or img is None:
            return
        runs = self._ordered_runs_for_reference(self._selected_runs())
        if not runs:
            self._clear_open_timeline_view("Valves (open): выберите хотя бы один run.")
            return
        ref = self._reference_run(runs)
        if ref is None:
            self._clear_open_timeline_view("Valves (open): reference run is unavailable.")
            return
        try:
            df_open = getattr(ref, "tables", {}).get("open")
        except Exception:
            df_open = None
        if not isinstance(df_open, pd.DataFrame) or df_open.empty:
            self._clear_open_timeline_view(
                f"Valves (open): run {getattr(ref, 'label', '—')} has no non-empty `open` table."
            )
            return

        try:
            tcol = detect_time_col(df_open) or df_open.columns[0]
        except Exception:
            tcol = df_open.columns[0]
        try:
            tt = np.asarray(extract_time_vector(df_open, tcol), dtype=float)
        except Exception:
            tt = np.asarray([], dtype=float)
        if tt.size <= 0:
            tt = np.arange(len(df_open), dtype=float)
        valve_cols = [str(c) for c in df_open.columns if str(c) != str(tcol)]
        if not valve_cols:
            self._clear_open_timeline_view("Valves (open): open table exists, but no valve columns were found.")
            return

        max_valves = int(self.spin_open_timeline_valves.value()) if hasattr(self, "spin_open_timeline_valves") else 40
        rows_meta: List[Tuple[int, int, str, np.ndarray]] = []
        for col in valve_cols:
            try:
                arr_raw = np.asarray(df_open[col].values, dtype=float)
            except Exception:
                continue
            n = min(int(tt.size), int(arr_raw.size))
            if n <= 0:
                continue
            arr_raw = np.asarray(arr_raw[:n], dtype=float)
            mask = np.isfinite(arr_raw)
            if not np.any(mask):
                continue
            arr01 = np.zeros(n, dtype=float)
            arr01[mask] = (arr_raw[mask] > 0.5).astype(float)
            changed = int(np.nanmax(arr01[mask]) - np.nanmin(arr01[mask]) > 0.0)
            active = int(np.nanmax(arr01[mask]) > 0.5)
            rows_meta.append((changed, active, str(col), arr01))
        if not rows_meta:
            self._clear_open_timeline_view("Valves (open): no finite valve state columns were found.")
            return

        rows_meta.sort(key=lambda item: (-int(item[0]), -int(item[1]), str(item[2]).lower()))
        truncated = len(rows_meta) > max_valves
        rows_use = rows_meta[:max_valves]
        labels = [str(item[2]) for item in rows_use]
        Z = np.vstack([np.asarray(item[3], dtype=float) for item in rows_use])
        tt_use = np.asarray(tt[: Z.shape[1]], dtype=float)
        changed_count = int(sum(int(item[0]) for item in rows_use))
        if tt_use.size <= 0 or Z.size <= 0:
            self._clear_open_timeline_view("Valves (open): no aligned timeline points were found.")
            return

        try:
            img.setImage(Z, autoLevels=False)
            x0 = float(tt_use[0])
            x1 = float(tt_use[-1]) if tt_use.size > 1 else float(tt_use[0] + 1e-6)
            img.setRect(QtCore.QRectF(float(x0), -0.5, max(1e-6, float(x1 - x0)), float(len(labels))))
            img.setLevels((0.0, 1.0))
            img.setLookupTable(
                np.asarray(
                    [
                        [242, 242, 242, 255],
                        [210, 232, 214, 255],
                        [68, 150, 92, 255],
                    ],
                    dtype=np.ubyte,
                )
            )
            tick_step = max(1, int(np.ceil(len(labels) / 16.0)))
            ticks = [(float(i), _trim_label(labels[i], 28)) for i in range(0, len(labels), tick_step)]
            plot.getAxis("left").setTicks([ticks])
            plot.setEnabled(True)
            plot.setYRange(-0.5, float(len(labels) - 0.5), padding=0.02)
            plot.setXRange(float(tt_use[0]), float(tt_use[-1]), padding=0.01)
        except Exception:
            self._clear_open_timeline_view("Valves (open): failed to build the timeline heatmap.")
            return

        mismatch_rows_count = 0
        mismatch_cols_count = 0
        mismatch_common = 0
        mismatch_tbl = getattr(self, "tbl_open_timeline_mismatch", None)
        if mismatch_tbl is not None:
            try:
                ref_series_by_valve = {str(item[2]): np.asarray(item[3], dtype=float) for item in rows_meta}
                common_valves = set(labels)
                run_open_cache: Dict[str, Tuple[np.ndarray, Dict[str, np.ndarray]]] = {}
                for run in runs:
                    try:
                        df_run_open = getattr(run, "tables", {}).get("open")
                    except Exception:
                        df_run_open = None
                    if not isinstance(df_run_open, pd.DataFrame) or df_run_open.empty:
                        common_valves = set()
                        break
                    try:
                        tcol_run = detect_time_col(df_run_open) or df_run_open.columns[0]
                    except Exception:
                        tcol_run = df_run_open.columns[0]
                    try:
                        tt_run = np.asarray(extract_time_vector(df_run_open, tcol_run), dtype=float)
                    except Exception:
                        tt_run = np.asarray([], dtype=float)
                    if tt_run.size <= 0:
                        tt_run = np.arange(len(df_run_open), dtype=float)
                    cols_map: Dict[str, np.ndarray] = {}
                    for col in df_run_open.columns:
                        if str(col) == str(tcol_run):
                            continue
                        try:
                            arr_raw = np.asarray(df_run_open[col].values, dtype=float)
                        except Exception:
                            continue
                        n = min(int(tt_run.size), int(arr_raw.size))
                        if n <= 0:
                            continue
                        arr_raw = np.asarray(arr_raw[:n], dtype=float)
                        mask = np.isfinite(arr_raw)
                        if not np.any(mask):
                            continue
                        arr01 = np.zeros(n, dtype=float)
                        arr01[mask] = (arr_raw[mask] > 0.5).astype(float)
                        cols_map[str(col)] = arr01
                    common_valves &= set(cols_map.keys())
                    run_open_cache[str(getattr(run, "label", "") or "")] = (np.asarray(tt_run, dtype=float), cols_map)

                mismatch_labels = [lab for lab in labels if lab in common_valves]
                mismatch_common = int(len(mismatch_labels))
                mismatch_tbl.clear()
                if mismatch_labels and len(runs) >= 2:
                    run_labels = [str(getattr(run, "label", "") or "") for run in runs]
                    mismatch_tbl.setRowCount(len(mismatch_labels))
                    mismatch_tbl.setColumnCount(len(run_labels))
                    mismatch_tbl.setHorizontalHeaderLabels([_trim_label(lbl, 18) for lbl in run_labels])
                    mismatch_tbl.setVerticalHeaderLabels([_trim_label(lbl, 28) for lbl in mismatch_labels])
                    for c, run_label in enumerate(run_labels):
                        hitem = mismatch_tbl.horizontalHeaderItem(c)
                        if hitem is not None:
                            hitem.setToolTip(run_label)
                    for r, valve in enumerate(mismatch_labels):
                        vitem = mismatch_tbl.verticalHeaderItem(r)
                        if vitem is not None:
                            vitem.setToolTip(valve)
                        ref_arr = np.asarray(ref_series_by_valve.get(valve, np.asarray([], dtype=float)), dtype=float)
                        ref_t = np.asarray(tt_use[: ref_arr.size], dtype=float)
                        for c, run_label in enumerate(run_labels):
                            is_ref = (c == 0)
                            mismatch = float("nan")
                            duty_ref = float("nan")
                            duty_run = float("nan")
                            first_time = float("nan")
                            if is_ref:
                                mismatch = 0.0
                                if ref_arr.size > 0:
                                    duty_ref = float(np.mean(ref_arr > 0.5))
                                    duty_run = duty_ref
                            else:
                                run_tt, run_cols = run_open_cache.get(run_label, (np.asarray([], dtype=float), {}))
                                run_arr = np.asarray(run_cols.get(valve, np.asarray([], dtype=float)), dtype=float)
                                run_tt = np.asarray(run_tt[: run_arr.size], dtype=float)
                                if ref_arr.size > 0 and run_arr.size > 0 and run_tt.size > 0 and ref_t.size > 0:
                                    order = np.argsort(run_tt)
                                    x_src = np.asarray(run_tt[order], dtype=float)
                                    y_src = np.asarray(run_arr[order], dtype=float)
                                    idx = np.searchsorted(x_src, ref_t)
                                    idx = np.clip(idx, 1, max(1, len(x_src) - 1))
                                    left = idx - 1
                                    choose = np.where(np.abs(x_src[left] - ref_t) <= np.abs(x_src[idx] - ref_t), left, idx)
                                    sampled = np.asarray(y_src[choose], dtype=float)
                                    mask = np.isfinite(ref_arr) & np.isfinite(sampled)
                                    if np.any(mask):
                                        ref_masked = np.asarray(ref_arr[mask], dtype=float)
                                        sampled = np.asarray(sampled[mask], dtype=float)
                                        diff = ref_masked != sampled
                                        mismatch = float(np.mean(diff)) if diff.size else float("nan")
                                        duty_ref = float(np.mean(ref_masked > 0.5))
                                        duty_run = float(np.mean(sampled > 0.5))
                                        diff_idx = np.flatnonzero(diff)
                                        if diff_idx.size > 0:
                                            first_time = float(np.asarray(ref_t[mask], dtype=float)[int(diff_idx[0])])
                            text = "" if not np.isfinite(mismatch) else f"{100.0 * mismatch:.0f}%"
                            item = QtWidgets.QTableWidgetItem(text)
                            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                            item.setTextAlignment(QtCore.Qt.AlignCenter)
                            item.setBackground(self._open_timeline_mismatch_color(mismatch, is_ref=is_ref))
                            tooltip = (
                                f"valve: {valve}\nrun: {run_label}\nref: {getattr(ref, 'label', '')}\n"
                                f"mismatch: {'' if not np.isfinite(mismatch) else f'{100.0 * mismatch:.2f}%'}\n"
                                f"ref duty: {'' if not np.isfinite(duty_ref) else f'{100.0 * duty_ref:.1f}%'}\n"
                                f"run duty: {'' if not np.isfinite(duty_run) else f'{100.0 * duty_run:.1f}%'}"
                            )
                            if np.isfinite(first_time):
                                tooltip = f"{tooltip}\nfirst mismatch: {first_time:.6f} s"
                            item.setToolTip(tooltip)
                            item.setData(
                                QtCore.Qt.UserRole,
                                {
                                    "run": run_label,
                                    "signal": valve,
                                    "time_s": first_time,
                                    "mismatch": mismatch,
                                    "is_ref": bool(is_ref),
                                },
                            )
                            if np.isfinite(mismatch) and mismatch > 0.0:
                                font = item.font()
                                font.setBold(True)
                                item.setFont(font)
                            mismatch_tbl.setItem(r, c, item)
                    try:
                        hdr = mismatch_tbl.horizontalHeader()
                        for c in range(len(run_labels)):
                            hdr.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
                        mismatch_tbl.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
                    except Exception:
                        pass
                    mismatch_tbl.setEnabled(True)
                    mismatch_rows_count = int(len(mismatch_labels))
                    mismatch_cols_count = int(len(run_labels))
                    try:
                        self.lbl_open_timeline_mismatch.setText(
                            f"Mismatch vs ref: {len(mismatch_labels)} common valve(s) across {len(run_labels)} run(s). "
                            "Click a cell to focus run / valve and jump to the first mismatch."
                        )
                    except Exception:
                        pass
                else:
                    mismatch_tbl.setRowCount(0)
                    mismatch_tbl.setColumnCount(0)
                    mismatch_tbl.setEnabled(False)
                    try:
                        self.lbl_open_timeline_mismatch.setText(
                            "Mismatch vs ref: need at least 2 runs with common `open` valve columns."
                        )
                    except Exception:
                        pass
            except Exception:
                try:
                    mismatch_tbl.clear()
                    mismatch_tbl.setRowCount(0)
                    mismatch_tbl.setColumnCount(0)
                    mismatch_tbl.setEnabled(False)
                except Exception:
                    pass
                try:
                    self.lbl_open_timeline_mismatch.setText(
                        "Mismatch vs ref is temporarily unavailable; the reference timeline above remains valid."
                    )
                except Exception:
                    pass

        self._open_timeline_cache = {
            "run": str(getattr(ref, "label", "") or ""),
            "time": tt_use,
            "valves": list(labels),
            "data": Z,
            "changed_count": changed_count,
            "truncated": bool(truncated),
            "mismatch_rows": mismatch_rows_count,
            "mismatch_cols": mismatch_cols_count,
            "common_valves": mismatch_common,
        }
        line1, line2 = self._open_timeline_status_text(
            ref_label=str(getattr(ref, "label", "") or ""),
            valves_count=len(labels),
            changed_count=changed_count,
            t_min=float(tt_use[0]),
            t_max=float(tt_use[-1]),
            truncated=bool(truncated),
        )
        try:
            self.lbl_open_timeline_note.setText(line1)
            self.lbl_open_timeline_readout.setText("")
            self.lbl_open_timeline_stats.setText(line2)
        except Exception:
            pass
        try:
            if getattr(self, "line_open_timeline", None) is not None:
                self.line_open_timeline.show()
        except Exception:
            pass
        try:
            if hasattr(self, "_t_ref") and np.asarray(getattr(self, "_t_ref", np.asarray([])), dtype=float).size > 0:
                idx = int(self.slider_time.value()) if hasattr(self, "slider_time") else 0
                idx = max(0, min(idx, int(len(self._t_ref) - 1)))
                self._sync_open_timeline_to_time(float(self._t_ref[idx]))
        except Exception:
            pass
        self._update_workspace_status()

    def _sync_open_timeline_to_time(self, t: float) -> None:
        cache = dict(getattr(self, "_open_timeline_cache", {}) or {})
        tt = np.asarray(cache.get("time", np.asarray([])), dtype=float)
        Z = np.asarray(cache.get("data", np.asarray([[]], dtype=float)), dtype=float)
        labels = list(cache.get("valves") or [])
        if tt.size <= 0 or Z.size <= 0 or not labels:
            return
        try:
            idx = int(np.argmin(np.abs(tt - float(t))))
        except Exception:
            return
        idx = max(0, min(idx, int(tt.size - 1)))
        x = float(tt[idx])
        active_now = int(np.sum(np.asarray(Z[:, idx], dtype=float) > 0.5))
        try:
            if getattr(self, "line_open_timeline", None) is not None:
                self.line_open_timeline.setPos(x)
        except Exception:
            pass
        try:
            self.lbl_open_timeline_stats.setText(
                f"ref={str(cache.get('run') or '—')} | t={x:.3f}s | active now={active_now}/{len(labels)}"
            )
        except Exception:
            pass

    def _open_timeline_sample(self, scene_pos) -> Dict[str, object]:
        cache = dict(getattr(self, "_open_timeline_cache", {}) or {})
        plot = getattr(self, "plot_open_timeline", None)
        if plot is None or not cache:
            return {}
        tt = np.asarray(cache.get("time", np.asarray([])), dtype=float)
        Z = np.asarray(cache.get("data", np.asarray([[]], dtype=float)), dtype=float)
        labels = list(cache.get("valves") or [])
        if tt.size <= 0 or Z.size <= 0 or not labels:
            return {}
        try:
            mp = plot.getViewBox().mapSceneToView(scene_pos)
            x = float(mp.x())
            y = float(mp.y())
        except Exception:
            return {}
        if not np.isfinite(x) or not np.isfinite(y):
            return {}
        row = int(np.round(y))
        if row < 0 or row >= len(labels):
            return {}
        idx = int(np.argmin(np.abs(tt - x)))
        idx = max(0, min(idx, int(tt.size - 1)))
        state = float(Z[row, idx]) if 0 <= row < Z.shape[0] and 0 <= idx < Z.shape[1] else float("nan")
        return {
            "row": row,
            "idx": idx,
            "time_s": float(tt[idx]),
            "valve": str(labels[row]),
            "state": state,
            "run": str(cache.get("run") or ""),
        }

    def _on_open_timeline_mouse_moved(self, evt) -> None:
        pos = evt[0] if isinstance(evt, tuple) else evt
        sample = self._open_timeline_sample(pos)
        if not sample:
            return
        state_txt = "open" if float(sample.get("state", 0.0) or 0.0) > 0.5 else "closed"
        try:
            self.lbl_open_timeline_readout.setText(
                f"run={sample.get('run') or '—'} | valve={sample.get('valve') or '—'} | "
                f"t={float(sample.get('time_s', float('nan'))):.3f}s | state={state_txt}"
            )
        except Exception:
            pass

    def _on_open_timeline_mouse_clicked(self, event) -> None:
        try:
            if event.button() != QtCore.Qt.LeftButton:
                return
        except Exception:
            return
        sample = self._open_timeline_sample(event.scenePos())
        if not sample:
            return
        try:
            self._set_playhead_time(float(sample.get("time_s", float("nan"))))
        except Exception:
            pass

    def _on_open_timeline_mismatch_clicked(self, row: int, col: int) -> None:
        tbl = getattr(self, "tbl_open_timeline_mismatch", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), int(col))
        except Exception:
            item = None
        if item is None:
            return
        try:
            payload = dict(item.data(QtCore.Qt.UserRole) or {})
        except Exception:
            payload = {}
        run_label = str(payload.get("run") or "").strip()
        sig = str(payload.get("signal") or "").strip()
        t0 = float(payload.get("time_s", np.nan))
        focused = False
        if run_label and sig:
            try:
                focused = bool(self._focus_run_signal(run_label, sig))
            except Exception:
                focused = False
        if (not focused) and run_label:
            try:
                focused = bool(self._focus_run_label_preserving_context(run_label))
            except Exception:
                focused = False
        if focused and np.isfinite(t0):
            try:
                self._set_playhead_time(t0)
            except Exception:
                pass




    # ---------------- Influence(t) Heatmap (time-player): meta → signals over time ----------------

    def _build_infl_heatmap_dock(self):
        dock = QtWidgets.QDockWidget("Influence(t) Heatmap", self)
        dock.setObjectName("dock_influence_heatmap")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea
        )

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.chk_inflheat = QtWidgets.QCheckBox("Enable Influence(t) heatmap (corr cube → ImageView)")
        # По умолчанию выключено: куб корреляций может быть тяжёлым на больших датасетах.
        self.chk_inflheat.setChecked(False)
        self.chk_inflheat.setToolTip(
            "Показывает корреляцию meta → signal как матрицу (signals × meta) во времени.\n"
            "Это качественный инструмент: при малом числе прогонов корреляции могут быть шумными."
        )
        self.chk_inflheat.stateChanged.connect(self._schedule_inflheat_rebuild)
        lay.addWidget(self.chk_inflheat)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Max meta"))
        self.spin_inflheat_feat = QtWidgets.QSpinBox()
        self.spin_inflheat_feat.setRange(4, 80)
        self.spin_inflheat_feat.setSingleStep(1)
        self.spin_inflheat_feat.setValue(24)
        self.spin_inflheat_feat.setToolTip("Ограничение читаемости/производительности")
        self.spin_inflheat_feat.valueChanged.connect(self._schedule_inflheat_rebuild)
        row.addWidget(self.spin_inflheat_feat)

        row.addWidget(QtWidgets.QLabel("Max signals"))
        self.spin_inflheat_sigs = QtWidgets.QSpinBox()
        self.spin_inflheat_sigs.setRange(2, 30)
        self.spin_inflheat_sigs.setSingleStep(1)
        self.spin_inflheat_sigs.setValue(12)
        self.spin_inflheat_sigs.setToolTip("Ограничение читаемости/производительности")
        self.spin_inflheat_sigs.valueChanged.connect(self._schedule_inflheat_rebuild)
        row.addWidget(self.spin_inflheat_sigs)
        lay.addLayout(row)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("Frames"))
        self.spin_inflheat_frames = QtWidgets.QSpinBox()
        self.spin_inflheat_frames.setRange(20, 300)
        self.spin_inflheat_frames.setSingleStep(10)
        self.spin_inflheat_frames.setValue(120)
        self.spin_inflheat_frames.setToolTip("Сколько кадров оставить для плеера")
        self.spin_inflheat_frames.valueChanged.connect(self._schedule_inflheat_rebuild)
        row2.addWidget(self.spin_inflheat_frames)

        row2.addWidget(QtWidgets.QLabel("LOD time pts"))
        self.spin_inflheat_tpts = QtWidgets.QSpinBox()
        self.spin_inflheat_tpts.setRange(200, 12000)
        self.spin_inflheat_tpts.setSingleStep(200)
        self.spin_inflheat_tpts.setValue(2500)
        self.spin_inflheat_tpts.setToolTip("LOD по времени: ограничивает объём ресэмплинга")
        self.spin_inflheat_tpts.valueChanged.connect(self._schedule_inflheat_rebuild)
        row2.addWidget(self.spin_inflheat_tpts)
        lay.addLayout(row2)

        self.lbl_inflheat_note = QtWidgets.QLabel(self._inflheat_default_note())
        self.lbl_inflheat_note.setWordWrap(True)
        lay.addWidget(self.lbl_inflheat_note)

        self.imv_inflheat = None
        self._inflheat_proxy = None
        self.lbl_inflheat_readout = QtWidgets.QLabel("")
        self.lbl_inflheat_readout.setWordWrap(True)
        self.plot_inflheat_pair = None
        self._inflheat_pair_click_connected = False

        if pg is None or build_influence_t_cube is None:
            lay.addWidget(QtWidgets.QLabel("Influence(t) heatmap unavailable: pyqtgraph / build_influence_t_cube not found"))
        else:
            try:
                self.imv_inflheat = pg.ImageView(view=pg.PlotItem())
                try:
                    self.imv_inflheat.ui.roiBtn.hide()
                    self.imv_inflheat.ui.menuBtn.hide()
                except Exception:
                    pass
                try:
                    self.imv_inflheat.setEnabled(False)
                except Exception:
                    pass
                lay.addWidget(self.imv_inflheat, stretch=1)
                lay.addWidget(self.lbl_inflheat_readout)

                try:
                    self._inflheat_proxy = pg.SignalProxy(
                        self.imv_inflheat.getView().scene().sigMouseMoved,
                        rateLimit=60,
                        slot=self._on_inflheat_mouse_moved,
                    )
                except Exception:
                    self._inflheat_proxy = None
                try:
                    self.imv_inflheat.getView().scene().sigMouseClicked.connect(self._on_inflheat_mouse_clicked)
                except Exception:
                    pass

                self.plot_inflheat_pair = pg.PlotWidget()
                self.plot_inflheat_pair.setMinimumHeight(180)
                self.plot_inflheat_pair.setBackground(None)
                self.plot_inflheat_pair.showGrid(x=True, y=True, alpha=0.25)
                self.plot_inflheat_pair.setLabel("bottom", "t, s")
                self.plot_inflheat_pair.setLabel("left", "corr")
                self.plot_inflheat_pair.setEnabled(False)
                self.plot_inflheat_pair.setToolTip(
                    "corr(t) for the current meta -> signal pair. "
                    "Click inside the plot to move the playhead."
                )
                try:
                    self.plot_inflheat_pair.scene().sigMouseClicked.connect(self._on_inflheat_pair_mouse_clicked)
                    self._inflheat_pair_click_connected = True
                except Exception:
                    self._inflheat_pair_click_connected = False
                lay.addWidget(self.plot_inflheat_pair)
            except Exception as e:
                self.imv_inflheat = None
                lay.addWidget(QtWidgets.QLabel(f"Influence(t) heatmap init failed: {e}"))

        dock.setWidget(w)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.dock_inflheat = dock

        # tabify with other analysis docks (keeps UI compact)
        try:
            if hasattr(self, "dock_influence"):
                self.tabifyDockWidget(self.dock_influence, dock)
        except Exception:
            pass

    def _schedule_inflheat_rebuild(self, *_args, delay_ms: int = 250):
        if not hasattr(self, "_inflheat_timer"):
            return
        try:
            self._inflheat_timer.stop()
        except Exception:
            pass
        try:
            self._inflheat_timer.start(int(delay_ms))
        except Exception:
            pass

    def _inflheat_default_note(self) -> str:
        return (
            "Axes: X = Signals, Y = Meta features.\n"
            "Наведи мышь на ячейку: покажу полные подписи.\n"
            "Совет: включите Δ-mode, чтобы видеть влияние на Δ(signal) относительно reference run.\n"
            "Текущая focused pair получает corr(t) trace ниже."
        )

    def _clear_inflheat_pair_trace(self, title: str = "") -> None:
        plot = getattr(self, "plot_inflheat_pair", None)
        if plot is None:
            return
        try:
            plot.clear()
            plot.setEnabled(False)
            plot.setLabel("bottom", "t, s")
            plot.setLabel("left", "corr")
            plot.setTitle(str(title or "corr(t): focus a meta -> signal pair"))
        except Exception:
            pass

    def _resolve_inflheat_focus_pair(self) -> Optional[Tuple[str, str, int, int]]:
        sigs = list(getattr(self, "_inflheat_sig_labels", []) or [])
        feats = list(getattr(self, "_inflheat_feat_labels", []) or [])
        cube_obj = getattr(self, "_inflheat", None)
        if cube_obj is None or not sigs or not feats:
            return None

        def _try_pair(feat_name: str, sig_name: str) -> Optional[Tuple[str, str, int, int]]:
            feat_name = str(feat_name or "").strip()
            sig_name = str(sig_name or "").strip()
            if feat_name in feats and sig_name in sigs:
                return feat_name, sig_name, feats.index(feat_name), sigs.index(sig_name)
            return None

        pair = _try_pair(
            str(getattr(self, "_infl_focus_feat", "") or ""),
            str(getattr(self, "_infl_focus_sig", "") or ""),
        )
        if pair is None:
            insight = dict(getattr(self, "_insight_infl", {}) or {})
            pair = _try_pair(
                str(insight.get("feature") or ""),
                str(insight.get("signal") or ""),
            )
        if pair is not None:
            feat_name, sig_name, _fi, _si = pair
            self._infl_focus_feat = feat_name
            self._infl_focus_sig = sig_name
            return pair

        try:
            tH = np.asarray(getattr(self, "_inflheat_t", np.asarray([])), dtype=float)
            cube = np.asarray(getattr(cube_obj, "cube", np.asarray([])), dtype=float)
            if cube.ndim != 3 or cube.size == 0 or tH.size <= 0:
                return None
            idx = 0
            if hasattr(self, "slider_time") and getattr(self, "_t_ref", np.asarray([])).size:
                try:
                    idx = int(max(0, min(int(self.slider_time.value()), int(len(self._t_ref) - 1))))
                    t_now = float(self._t_ref[idx])
                    idx = int(np.argmin(np.abs(tH - t_now)))
                except Exception:
                    idx = 0
            idx = max(0, min(int(idx), int(cube.shape[0] - 1)))
            frame = np.asarray(cube[idx], dtype=float)
            if frame.ndim != 2 or frame.size == 0 or not np.isfinite(frame).any():
                return None
            A = np.abs(frame)
            A = np.nan_to_num(A, nan=-1.0, posinf=-1.0, neginf=-1.0)
            k = int(np.argmax(A))
            fi = int(k // len(sigs))
            si = int(k % len(sigs))
            if not (0 <= fi < len(feats) and 0 <= si < len(sigs)):
                return None
            feat_name = str(feats[fi])
            sig_name = str(sigs[si])
            self._infl_focus_feat = feat_name
            self._infl_focus_sig = sig_name
            return feat_name, sig_name, fi, si
        except Exception:
            return None

    def _update_inflheat_pair_trace(self) -> None:
        plot = getattr(self, "plot_inflheat_pair", None)
        if plot is None:
            return
        pair = self._resolve_inflheat_focus_pair()
        cube_obj = getattr(self, "_inflheat", None)
        tH = np.asarray(getattr(self, "_inflheat_t", np.asarray([])), dtype=float)
        cube = np.asarray(getattr(cube_obj, "cube", np.asarray([])), dtype=float) if cube_obj is not None else np.asarray([])
        if pair is None or cube.ndim != 3 or cube.size == 0 or tH.size == 0:
            self._clear_inflheat_pair_trace("corr(t): build Influence(t) Heatmap to inspect one pair over time")
            return

        feat_name, sig_name, fi, si = pair
        try:
            c_t = np.asarray(cube[:, fi, si], dtype=float)
        except Exception:
            c_t = np.asarray([], dtype=float)
        finite = np.isfinite(tH) & np.isfinite(c_t)
        if c_t.size == 0 or not finite.any():
            self._clear_inflheat_pair_trace(f"corr(t): {feat_name} -> {sig_name} has no finite frames")
            return

        try:
            plot.clear()
            plot.setEnabled(True)
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setLabel("bottom", "t, s")
            plot.setLabel("left", "corr")
            plot.plot(
                tH[finite],
                c_t[finite],
                pen=pg.mkPen((60, 110, 190, 220), width=2),
                antialias=True,
            )
            plot.addItem(pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((120, 120, 120, 160), width=1, style=QtCore.Qt.DotLine)))

            idx_now = 0
            if hasattr(self, "slider_time") and getattr(self, "_t_ref", np.asarray([])).size:
                try:
                    idx_now = int(max(0, min(int(self.slider_time.value()), int(len(self._t_ref) - 1))))
                    t_now = float(self._t_ref[idx_now])
                except Exception:
                    t_now = float(tH[0])
            else:
                t_now = float(tH[0])
            try:
                idx_now = int(np.argmin(np.abs(tH - float(t_now))))
            except Exception:
                idx_now = 0
            idx_now = max(0, min(int(idx_now), int(len(tH) - 1)))
            t_now = float(tH[idx_now])
            c_now = float(c_t[idx_now]) if idx_now < len(c_t) else float("nan")
            plot.addItem(pg.InfiniteLine(pos=t_now, angle=90, pen=pg.mkPen((230, 120, 40, 220), width=2)))
            plot.setYRange(-1.05, 1.05, padding=0.0)
            current_txt = f" | current={c_now:+.3f} @ {t_now:.3f}s" if np.isfinite(c_now) else ""
            plot.setTitle(f"corr(t): {feat_name} -> {sig_name}{current_txt} | click to move playhead")
        except Exception:
            self._clear_inflheat_pair_trace(f"corr(t): failed for {feat_name} -> {sig_name}")

    def _update_inflheat_note_for_index(self, idx: int) -> None:
        cube_obj = getattr(self, "_inflheat", None)
        if cube_obj is None:
            try:
                self.lbl_inflheat_note.setText(self._inflheat_default_note())
            except Exception:
                pass
            return

        try:
            tH = np.asarray(getattr(self, "_inflheat_t", np.asarray([])), dtype=float)
            C = np.asarray(getattr(cube_obj, "cube", np.asarray([])), dtype=float)
            sigs = list(getattr(self, "_inflheat_sig_labels", []) or [])
            feats = list(getattr(self, "_inflheat_feat_labels", []) or [])
            if C.ndim != 3 or C.size == 0 or not sigs or not feats or tH.size == 0:
                self.lbl_inflheat_note.setText(self._inflheat_default_note())
                return
            idx = max(0, min(int(idx), int(len(tH) - 1), int(C.shape[0] - 1)))
            frame = np.asarray(C[idx], dtype=float)  # (n_feat, n_sig)
            if frame.ndim != 2 or frame.size == 0 or not np.isfinite(frame).any():
                self.lbl_inflheat_note.setText(self._inflheat_default_note())
                return
        except Exception:
            try:
                self.lbl_inflheat_note.setText(self._inflheat_default_note())
            except Exception:
                pass
            return

        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        mode = str(getattr(self, "_inflheat_mode", "value") or "value")
        ref_label = str(getattr(self, "_inflheat_ref_label", "") or "")
        runs_count = int(getattr(self, "_inflheat_runs_count", 0) or 0)
        t0 = float(tH[idx])
        abs_frame = np.abs(frame)
        finite = np.isfinite(frame)
        abs_rank = np.nan_to_num(abs_frame, nan=-1.0, posinf=-1.0, neginf=-1.0)
        strong_thr = 0.45
        strong_mask = finite & (abs_frame >= strong_thr)

        line1 = (
            f"X=Signals | Y=Meta | t={t0:.4f}s | runs={runs_count} | sigs={len(sigs)} | meta={len(feats)} | "
            f"mode={'Δ vs ' + ref_label if mode == 'delta' and ref_label else mode}"
        )

        if analysis_mode == "one_to_all":
            row_counts = np.asarray([int(strong_mask[i].sum()) for i in range(frame.shape[0])], dtype=int)
            row_mean = np.asarray(
                [
                    float(np.nanmean(np.where(finite[i], abs_frame[i], np.nan))) if np.isfinite(np.where(finite[i], abs_frame[i], np.nan)).any() else float("nan")
                    for i in range(frame.shape[0])
                ],
                dtype=float,
            )
            fan_idx = max(
                range(frame.shape[0]),
                key=lambda i: (
                    int(row_counts[i]),
                    float(np.nan_to_num(row_mean[i], nan=-1.0)),
                ),
            )
            fan_order = np.argsort(np.nan_to_num(np.where(finite[fan_idx], abs_frame[fan_idx], np.nan), nan=-1.0))[::-1]
            examples = []
            for j in fan_order[:3]:
                if finite[fan_idx, int(j)]:
                    examples.append(f"{sigs[int(j)]} {float(frame[fan_idx, int(j)]):+.2f}")
            line2 = (
                f"Frame fan-out: {feats[fan_idx]} -> {int(row_counts[fan_idx])}/{len(sigs)} signals at |corr|≥{strong_thr:.2f}"
                + (f" | top: {', '.join(examples)}" if examples else "")
            )
            line3 = "Heuristic: sweep nearby frames to see whether one driver stays broad or collapses to a local hotspot."
        elif analysis_mode == "all_to_one":
            target_sig = self._workspace_analysis_target_signal(sigs)
            target_idx = sigs.index(target_sig) if target_sig in sigs else int(np.argmax(np.nan_to_num(np.nanmean(np.where(finite, abs_frame, np.nan), axis=0), nan=-1.0)))
            col = frame[:, target_idx]
            col_rank = np.nan_to_num(np.abs(col), nan=-1.0, posinf=-1.0, neginf=-1.0)
            feat_idx = int(np.argmax(col_rank))
            line2 = f"Target: {sigs[target_idx]} | lead driver at this frame: {feats[feat_idx]} ({float(frame[feat_idx, target_idx]):+.2f})"
            line3 = "Heuristic: keep the target fixed and watch whether the driver ranking swaps as time moves."
        else:
            k_top = int(np.argmax(abs_rank))
            i_top, j_top = int(k_top // frame.shape[1]), int(k_top % frame.shape[1])
            strong_links = int(strong_mask.sum())
            total_links = int(finite.sum())
            density = (100.0 * float(strong_links) / float(total_links)) if total_links else 0.0
            line2 = (
                f"Frame corridor: {feats[i_top]} -> {sigs[j_top]} ({float(frame[i_top, j_top]):+.2f}) | "
                f"strong links {strong_links}/{total_links} ({density:.0f}% dense)"
            )
            line3 = "Heuristic: use this frame as a gate, then compare it against cloud clusters and the dominant scatter corridor."

        try:
            self.lbl_inflheat_note.setText("\n".join([line1, line2, line3]))
        except Exception:
            pass

    def _rebuild_infl_heatmap(self):
        if not hasattr(self, "chk_inflheat"):
            return
        if not self.chk_inflheat.isChecked():
            self._clear_inflheat_view()
            return
        if self.imv_inflheat is None or build_influence_t_cube is None:
            return

        runs = self._ordered_runs_for_reference(self._selected_runs())
        sigs = self._selected_signals()
        if not runs or not sigs:
            self._clear_inflheat_view("Выберите хотя бы один прогон и один сигнал.")
            return
        ref = runs[0]

        if len(runs) < 3:
            # correlation is meaningless with < 3 points
            self._clear_inflheat_view("Need at least 3 runs to compute correlations")
            return

        max_sigs = int(self.spin_inflheat_sigs.value()) if hasattr(self, "spin_inflheat_sigs") else 12
        sigs_use = list(sigs)[:max_sigs]

        # ---- meta matrix X ----
        try:
            flat = [infl_flatten_meta_numeric(r.meta) for r in runs]
        except Exception:
            flat = [{} for _ in runs]

        feat_all = sorted({k for d in flat for k in d.keys()})
        if not feat_all:
            self._clear_inflheat_view("В meta_json нет численных параметров.")
            return

        X_all = np.full((len(runs), len(feat_all)), np.nan, dtype=float)
        for i, d in enumerate(flat):
            for j, k in enumerate(feat_all):
                v = d.get(k, None)
                if v is None:
                    continue
                try:
                    X_all[i, j] = float(v)
                except Exception:
                    continue

        # prefilter by variance + finite count
        keep = []
        for j, k in enumerate(feat_all):
            col = X_all[:, j]
            if int(np.isfinite(col).sum()) < 3:
                continue
            if float(np.nanstd(col)) <= 1e-12:
                continue
            keep.append(j)

        if not keep:
            self._clear_inflheat_view("Недостаточно вариативных meta параметров для корреляции.")
            return

        feat_use = [feat_all[j] for j in keep]
        X_use = X_all[:, keep]

        max_feat = int(self.spin_inflheat_feat.value()) if hasattr(self, "spin_inflheat_feat") else 24
        if X_use.shape[1] > max_feat:
            feat_use = feat_use[:max_feat]
            X_use = X_use[:, :max_feat]

        # Build minimal bundle-like dicts
        run_tuples = [(r.label, {"tables": r.tables, "meta": r.meta}) for r in runs]

        mode = "delta" if bool(self.chk_delta.isChecked()) else "value"

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                cube_obj = build_influence_t_cube(
                    run_tuples,
                    X=X_use,
                    feat_names=feat_use,
                    table=str(self.current_table),
                    sigs=sigs_use,
                    ref_label=str(ref.label),
                    mode=mode,
                    dist_unit=str(self.dist_unit),
                    angle_unit=str(self.angle_unit),
                    p_atm=float(getattr(self, "p_atm", getattr(self, "P_ATM", 100000.0))),
                    baseline_mode=str(self.baseline_mode),
                    baseline_window_s=float(self.baseline_window_s),
                    baseline_first_n=int(getattr(self, "baseline_first_n", 0) or 0),
                    zero_positions=bool(self.zero_baseline),
                    flow_unit=str(getattr(self, "flow_unit", "raw") or "raw"),
                    time_window=None,
                    max_time_points=int(self.spin_inflheat_tpts.value()) if hasattr(self, "spin_inflheat_tpts") else 2500,
                    max_frames=int(self.spin_inflheat_frames.value()) if hasattr(self, "spin_inflheat_frames") else 120,
                )
        except Exception:
            self._clear_inflheat_view("Influence(t) heatmap: не удалось пересчитать текущий выбор.")
            return

        if cube_obj is None or np.asarray(cube_obj.t).size < 2 or np.asarray(cube_obj.cube).size == 0:
            self._clear_inflheat_view("Influence(t) heatmap: нет данных для отображения.")
            return

        tH = np.asarray(cube_obj.t, dtype=float)
        C = np.asarray(cube_obj.cube, dtype=float)  # (T, n_feat, n_sig)
        if not np.isfinite(C).any():
            self._clear_inflheat_view("Influence(t) heatmap: текущий выбор даёт только NaN/пустые значения.")
            return

        # ImageView expects (t, x, y). We want x=sigs, y=features.
        img = np.transpose(C, (0, 2, 1))  # (T, n_sig, n_feat)

        self._inflheat = cube_obj
        self._inflheat_t = tH
        self._inflheat_sig_labels = list(cube_obj.sigs)
        self._inflheat_feat_labels = list(cube_obj.feat_names)
        self._inflheat_mode = str(mode)
        self._inflheat_ref_label = str(ref.label)
        self._inflheat_runs_count = int(len(runs))

        try:
            self.imv_inflheat.setImage(img, xvals=tH, autoLevels=False)
        except TypeError:
            self.imv_inflheat.setImage(img, xvals=tH)
        try:
            self.imv_inflheat.setEnabled(True)
        except Exception:
            pass

        try:
            self.imv_inflheat.setLevels((-1.0, 1.0))
        except Exception:
            pass
        try:
            self._update_inflheat_note_for_index(0)
        except Exception:
            pass
        try:
            self.lbl_inflheat_readout.setText("")
        except Exception:
            pass

        # Sync to current playhead
        try:
            if hasattr(self, "_t_ref") and self._t_ref is not None and np.asarray(self._t_ref).size:
                idx = int(self.slider_time.value()) if hasattr(self, "slider_time") else 0
                idx = max(0, min(idx, int(len(self._t_ref) - 1)))
                self._sync_inflheat_to_time(float(self._t_ref[idx]))
            else:
                self._update_inflheat_pair_trace()
        except Exception:
            pass

    def _clear_inflheat_view(self, note: str = "") -> None:
        self._inflheat = None
        self._inflheat_t = np.zeros(0, dtype=float)
        self._inflheat_sig_labels = []
        self._inflheat_feat_labels = []
        self._inflheat_mode = ""
        self._inflheat_ref_label = ""
        self._inflheat_runs_count = 0
        try:
            if self.imv_inflheat is not None:
                blank = np.zeros((1, 1, 1), dtype=float)
                try:
                    self.imv_inflheat.setImage(blank, xvals=np.asarray([0.0], dtype=float), autoLevels=False)
                except TypeError:
                    self.imv_inflheat.setImage(blank, xvals=np.asarray([0.0], dtype=float))
                try:
                    self.imv_inflheat.setEnabled(False)
                except Exception:
                    pass
        except Exception:
            pass
        self._clear_inflheat_pair_trace(note or "")
        try:
            self.lbl_inflheat_note.setText(str(note or self._inflheat_default_note()))
        except Exception:
            pass
        try:
            self.lbl_inflheat_readout.setText(str(note or ""))
        except Exception:
            pass

    def _sync_inflheat_to_time(self, t: float):
        if self.imv_inflheat is None:
            return
        if self._inflheat_t is None or np.asarray(self._inflheat_t).size == 0:
            return
        try:
            idx = int(np.argmin(np.abs(np.asarray(self._inflheat_t, dtype=float) - float(t))))
            idx = max(0, min(idx, int(len(self._inflheat_t) - 1)))
            if hasattr(self.imv_inflheat, "setCurrentIndex"):
                self.imv_inflheat.setCurrentIndex(idx)
            self._update_inflheat_note_for_index(idx)
            self._update_inflheat_pair_trace()
        except Exception:
            return

    def _on_inflheat_mouse_moved(self, evt):
        if self.imv_inflheat is None:
            return
        try:
            pos = evt[0] if isinstance(evt, (tuple, list)) else evt
            plot_item = self.imv_inflheat.getView()
            vb = plot_item.vb if hasattr(plot_item, "vb") else plot_item
            p = vb.mapSceneToView(pos)
            x = float(p.x())
            y = float(p.y())

            ix = int(np.clip(round(x), 0, max(0, len(self._inflheat_sig_labels) - 1)))
            iy = int(np.clip(round(y), 0, max(0, len(self._inflheat_feat_labels) - 1)))

            sig_lab = self._inflheat_sig_labels[ix] if self._inflheat_sig_labels else str(ix)
            feat_lab = self._inflheat_feat_labels[iy] if self._inflheat_feat_labels else str(iy)

            tidx = None
            try:
                tidx = int(self.imv_inflheat.currentIndex)
            except Exception:
                tidx = None

            t_txt = ""
            if tidx is not None and np.asarray(self._inflheat_t).size:
                tidx = max(0, min(tidx, int(len(self._inflheat_t) - 1)))
                t_txt = f"t={float(self._inflheat_t[tidx]):.4f}s"

            self.lbl_inflheat_readout.setText(
                f"{t_txt}   sig[{ix}]={sig_lab}   meta[{iy}]={feat_lab}"
            )
        except Exception:
            return

    def _on_inflheat_mouse_clicked(self, event):
        if self.imv_inflheat is None or not self._inflheat_sig_labels or not self._inflheat_feat_labels:
            return
        try:
            pos = event.scenePos() if hasattr(event, "scenePos") else None
            if pos is None:
                return
            plot_item = self.imv_inflheat.getView()
            vb = plot_item.vb if hasattr(plot_item, "vb") else plot_item
            try:
                if not vb.sceneBoundingRect().contains(pos):
                    return
            except Exception:
                pass
            p = vb.mapSceneToView(pos)
            ix = int(round(float(p.x())))
            iy = int(round(float(p.y())))
            if iy < 0 or iy >= len(self._inflheat_feat_labels):
                return
            if ix < 0 or ix >= len(self._inflheat_sig_labels):
                return
            feat_name = str(self._inflheat_feat_labels[iy])
            sig_name = str(self._inflheat_sig_labels[ix])
            self._infl_focus_feat = feat_name
            self._infl_focus_sig = sig_name
            try:
                cache = dict(getattr(self, "_infl_cache", {}) or {})
                feat_sel = [str(x) for x in (cache.get("feat_sel") or []) if str(x).strip()]
                sigs = [str(x) for x in (cache.get("sigs") or []) if str(x).strip()]
                if feat_name in feat_sel and sig_name in sigs and getattr(self, "tbl_infl", None) is not None:
                    self.tbl_infl.setCurrentCell(feat_sel.index(feat_name), sigs.index(sig_name))
            except Exception:
                pass
            try:
                self._update_influence_scatter_from_cache()
            except Exception:
                pass
            self._update_inflheat_pair_trace()
        except Exception:
            return

    def _on_inflheat_pair_mouse_clicked(self, event):
        plot = getattr(self, "plot_inflheat_pair", None)
        if plot is None or self._inflheat_t is None or np.asarray(self._inflheat_t).size == 0:
            return
        try:
            pos = event.scenePos() if hasattr(event, "scenePos") else None
            if pos is None:
                return
            vb = plot.plotItem.vb
            try:
                if not vb.sceneBoundingRect().contains(pos):
                    return
            except Exception:
                pass
            p = vb.mapSceneToView(pos)
            self._set_playhead_time(float(p.x()))
        except Exception:
            return

# ---------------- Influence(t): meta → signals at playhead ----------------

    def _build_influence_dock(self) -> None:
        """Dock: Influence(t) = correlation(meta, signal(t_playhead)).

        Зачем:
        - Быстро увидеть, какие входные параметры (meta) связаны с выходными сигналами
          *в текущий момент времени*.
        - Клик по ячейке → scatter (meta vs signal@t) ниже.

        Примечание по UX:
        - Это НЕ “экспертный режим”: включение/выключение одним чекбоксом,
          дефолтные значения безопасные, интерфейс простой.
        """
        self._infl_cache = None  # type: ignore
        self._infl_focus_feat = None
        self._infl_focus_sig = None

        dock = QtWidgets.QDockWidget("Influence(t): meta → signals", self)
        dock.setObjectName("DockInfluenceT")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)

        root = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(root)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)

        self.chk_infl_enable = QtWidgets.QCheckBox("Влияние в точке времени (t): показывать")
        self.chk_infl_enable.setToolTip(
            "Показывает тепловую карту корреляций: meta → значение сигнала в текущий момент времени.\n"
            "Клик по ячейке — подробности (scatter) ниже."
        )
        self.chk_infl_enable.setChecked(True)
        self.chk_infl_enable.stateChanged.connect(lambda _=None: self._schedule_influence_rebuild())

        row.addWidget(self.chk_infl_enable, 1)

        row.addWidget(QtWidgets.QLabel("Meta (top):"))

        self.spin_infl_maxfeat = QtWidgets.QSpinBox()
        self.spin_infl_maxfeat.setRange(5, 120)
        self.spin_infl_maxfeat.setValue(30)
        self.spin_infl_maxfeat.setToolTip("Сколько параметров meta показывать (по силе связи/влияния).")
        self.spin_infl_maxfeat.valueChanged.connect(lambda _=None: self._schedule_influence_rebuild())
        row.addWidget(self.spin_infl_maxfeat, 0)

        self.chk_infl_trend = QtWidgets.QCheckBox("Тренд")
        self.chk_infl_trend.setChecked(True)
        self.chk_infl_trend.setToolTip("Показывает линию тренда (линейная аппроксимация) на scatter.")
        self.chk_infl_trend.stateChanged.connect(lambda _=None: self._update_influence_scatter_from_cache())
        row.addWidget(self.chk_infl_trend, 0)

        v.addLayout(row)

        self.lbl_infl_note = QtWidgets.QLabel("")
        self.lbl_infl_note.setWordWrap(True)
        self.lbl_infl_note.setStyleSheet("color: #666;")
        v.addWidget(self.lbl_infl_note)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        self.tbl_infl = QtWidgets.QTableWidget()
        self.tbl_infl.setSortingEnabled(False)
        self.tbl_infl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_infl.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_infl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tbl_infl.cellClicked.connect(self._on_infl_cell_clicked)
        self.tbl_infl.setToolTip("Корреляция (Pearson): -1 … +1. Клик по ячейке → scatter ниже.")
        splitter.addWidget(self.tbl_infl)

        self.plot_infl = pg.PlotWidget()
        self.plot_infl.showGrid(x=True, y=True, alpha=0.25)
        self.plot_infl.setLabel('bottom', 'meta value')
        self.plot_infl.setLabel('left', 'signal value')
        self.plot_infl.setEnabled(False)
        self.plot_infl.setToolTip("Клик по точке → сфокусировать соответствующий run в текущей паре meta → signal.")
        splitter.addWidget(self.plot_infl)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        v.addWidget(splitter, 1)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

        # табом рядом с Δ(t) heatmap — это обычно “семейство” мультипараметрических видов
        try:
            if hasattr(self, "dock_heatmap") and self.dock_heatmap is not None:
                self.tabifyDockWidget(self.dock_heatmap, dock)
        except Exception:
            pass

        # Restore basic settings (без жёсткой зависимости от порядка init)
        try:
            s = self._settings
            self.chk_infl_enable.setChecked(
                self._qs_bool(
                    s.value("infl_enabled", self.chk_infl_enable.isChecked()),
                    self.chk_infl_enable.isChecked(),
                )
            )
            self.spin_infl_maxfeat.setValue(
                self._qs_int(s.value("infl_maxfeat", self.spin_infl_maxfeat.value()), self.spin_infl_maxfeat.value())
            )
            self.chk_infl_trend.setChecked(
                self._qs_bool(
                    s.value("infl_trend", self.chk_infl_trend.isChecked()),
                    self.chk_infl_trend.isChecked(),
                )
            )
        except Exception:
            pass

        self.dock_influence = dock


    # ---------------- Run-level metrics / distributions ----------------

    def _build_run_metrics_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Run metrics / distributions", self)
        dock.setObjectName("dock_run_metrics")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)

        root = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(root)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel("Signal:"))
        self.combo_dist_signal = QtWidgets.QComboBox()
        self.combo_dist_signal.setToolTip(
            "Один сигнал на все выбранные runs. Метрика превращает его в одно число на run, "
            "чтобы быстро увидеть ranking и распределение."
        )
        self.combo_dist_signal.currentIndexChanged.connect(self._on_run_metrics_signal_changed)
        row.addWidget(self.combo_dist_signal, 1)

        row.addWidget(QtWidgets.QLabel("Metric:"))
        self.combo_dist_mode = QtWidgets.QComboBox()
        self.combo_dist_mode.addItem("Значение @ playhead", "value_at_playhead")
        self.combo_dist_mode.addItem("Δ @ playhead (vs reference)", "delta_at_playhead")
        self.combo_dist_mode.addItem("RMS по окну", "rms_window")
        self.combo_dist_mode.addItem("RMS(Δ) по окну (vs reference)", "rms_delta_window")
        self.combo_dist_mode.addItem("max|Δ| по окну (vs reference)", "maxabs_delta_window")
        self.combo_dist_mode.setToolTip(
            "Как свернуть выбранный сигнал в одно число на каждый run: значение в playhead "
            "или оконная метрика по текущему виду."
        )
        self.combo_dist_mode.currentIndexChanged.connect(self._on_run_metrics_mode_changed)
        row.addWidget(self.combo_dist_mode, 1)

        self.chk_dist_use_view = QtWidgets.QCheckBox("По видимому окну")
        self.chk_dist_use_view.setChecked(True)
        self.chk_dist_use_view.setToolTip(
            "Для оконных метрик использовать текущий видимый X-интервал первого графика. "
            "Если окно недоступно, будет использован весь сигнал."
        )
        self.chk_dist_use_view.stateChanged.connect(lambda _=None: self._schedule_run_metrics_rebuild(delay_ms=80))
        row.addWidget(self.chk_dist_use_view, 0)
        v.addLayout(row)

        self.lbl_dist_note = QtWidgets.QLabel("Run metrics: choose a signal to rank runs.")
        self.lbl_dist_note.setWordWrap(True)
        v.addWidget(self.lbl_dist_note)

        self.lbl_dist_stats = QtWidgets.QLabel("")
        self.lbl_dist_stats.setWordWrap(True)
        self.lbl_dist_stats.setStyleSheet("color:#666;")
        v.addWidget(self.lbl_dist_stats)

        tabs = QtWidgets.QTabWidget()

        tab_rank = QtWidgets.QWidget()
        rank_lay = QtWidgets.QVBoxLayout(tab_rank)
        rank_lay.setContentsMargins(6, 6, 6, 6)
        rank_lay.setSpacing(6)

        self.plot_dist_bar = pg.PlotWidget()
        self.plot_dist_bar.setMinimumHeight(220)
        self.plot_dist_bar.setBackground(None)
        self.plot_dist_bar.showGrid(x=False, y=True, alpha=0.25)
        self.plot_dist_bar.setMouseEnabled(x=False, y=False)
        self.plot_dist_bar.setEnabled(False)
        rank_lay.addWidget(self.plot_dist_bar, 1)

        self.tbl_dist = QtWidgets.QTableWidget()
        self.tbl_dist.setColumnCount(4)
        self.tbl_dist.setHorizontalHeaderLabels(["#", "run", "value", "ref"])
        self.tbl_dist.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_dist.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_dist.setAlternatingRowColors(True)
        self.tbl_dist.setMinimumHeight(170)
        try:
            hdr = self.tbl_dist.horizontalHeader()
            hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        except Exception:
            pass
        try:
            self.tbl_dist.cellDoubleClicked.connect(self._on_run_metrics_table_double_clicked)
        except Exception:
            pass
        rank_lay.addWidget(self.tbl_dist, 0)
        tabs.addTab(tab_rank, "Ranking")

        tab_hist = QtWidgets.QWidget()
        hist_lay = QtWidgets.QVBoxLayout(tab_hist)
        hist_lay.setContentsMargins(6, 6, 6, 6)
        hist_lay.setSpacing(6)
        self.plot_dist_hist = pg.PlotWidget()
        self.plot_dist_hist.setMinimumHeight(280)
        self.plot_dist_hist.setBackground(None)
        self.plot_dist_hist.showGrid(x=True, y=True, alpha=0.25)
        self.plot_dist_hist.setMouseEnabled(x=False, y=False)
        self.plot_dist_hist.setEnabled(False)
        hist_lay.addWidget(self.plot_dist_hist, 1)
        tabs.addTab(tab_hist, "Distribution")

        tab_kde = QtWidgets.QWidget()
        kde_lay = QtWidgets.QVBoxLayout(tab_kde)
        kde_lay.setContentsMargins(6, 6, 6, 6)
        kde_lay.setSpacing(6)
        self.plot_dist_kde = pg.PlotWidget()
        self.plot_dist_kde.setMinimumHeight(280)
        self.plot_dist_kde.setBackground(None)
        self.plot_dist_kde.showGrid(x=True, y=True, alpha=0.25)
        self.plot_dist_kde.setMouseEnabled(x=False, y=False)
        self.plot_dist_kde.setEnabled(False)
        kde_lay.addWidget(self.plot_dist_kde, 1)
        tabs.addTab(tab_kde, "Density / KDE")

        tab_box = QtWidgets.QWidget()
        box_lay = QtWidgets.QVBoxLayout(tab_box)
        box_lay.setContentsMargins(6, 6, 6, 6)
        box_lay.setSpacing(6)
        self.plot_dist_box = pg.PlotWidget()
        self.plot_dist_box.setMinimumHeight(280)
        self.plot_dist_box.setBackground(None)
        self.plot_dist_box.showGrid(x=False, y=True, alpha=0.25)
        self.plot_dist_box.setMouseEnabled(x=False, y=False)
        self.plot_dist_box.setEnabled(False)
        try:
            self.plot_dist_box.getAxis("bottom").setTicks([[]])
        except Exception:
            pass
        box_lay.addWidget(self.plot_dist_box, 1)
        tabs.addTab(tab_box, "Box / strip")

        v.addWidget(tabs, 1)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        try:
            if hasattr(self, "dock_influence") and self.dock_influence is not None:
                self.tabifyDockWidget(self.dock_influence, dock)
        except Exception:
            pass
        self.dock_run_metrics = dock

        try:
            self.plot_dist_bar.scene().sigMouseClicked.connect(self._on_run_metrics_bar_clicked)
        except Exception:
            pass

        try:
            s = self._settings
            want_mode = str(s.value("dist_mode", "value_at_playhead") or "value_at_playhead")
            idx_mode = self.combo_dist_mode.findData(want_mode)
            if idx_mode >= 0:
                self.combo_dist_mode.setCurrentIndex(idx_mode)
            self.chk_dist_use_view.setChecked(
                self._qs_bool(s.value("dist_use_view", self.chk_dist_use_view.isChecked()), self.chk_dist_use_view.isChecked())
            )
        except Exception:
            pass

        self._refresh_run_metrics_signal_combo()
        self._clear_run_metrics_view("Выберите runs и signal context для per-run compare.")

    def _run_metrics_mode_key(self) -> str:
        combo = getattr(self, "combo_dist_mode", None)
        if combo is None:
            return "value_at_playhead"
        try:
            data = combo.currentData()
            if data is not None and str(data).strip():
                return str(data).strip()
        except Exception:
            pass
        return "value_at_playhead"

    def _run_metrics_signal_options(self) -> List[str]:
        try:
            return self._current_context_signal_names(apply_filter=False)
        except Exception:
            return []

    def _refresh_run_metrics_signal_combo(self) -> None:
        combo = getattr(self, "combo_dist_signal", None)
        if combo is None:
            return
        options = self._run_metrics_signal_options()
        try:
            current = str(combo.currentText() or "").strip()
        except Exception:
            current = ""
        remembered = str(getattr(self, "dist_signal_selected", "") or "").strip()
        selected = []
        try:
            selected = [str(x) for x in (self._selected_signals() or []) if str(x).strip()]
        except Exception:
            selected = []
        target = ""
        for candidate in [remembered, current] + list(selected) + list(options[:1]):
            cand = str(candidate or "").strip()
            if cand and cand in options:
                target = cand
                break
        try:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(options)
            if target:
                combo.setCurrentText(target)
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass
        try:
            combo.setEnabled(bool(options))
        except Exception:
            pass
        try:
            current_sig = str(combo.currentText() or "").strip()
            if current_sig and ((not remembered) or (remembered in options) or current_sig == remembered):
                self.dist_signal_selected = current_sig
        except Exception:
            pass

    def _current_metrics_time_window(self) -> Tuple[Optional[float], Optional[float], str]:
        use_view = bool(getattr(self, "chk_dist_use_view", None) and self.chk_dist_use_view.isChecked())
        if not use_view:
            return None, None, "whole-run"
        if not getattr(self, "plots", None):
            return None, None, "whole-run (view unavailable)"
        try:
            xr = self.plots[0].getViewBox().viewRange()[0]
            if not isinstance(xr, (list, tuple)) or len(xr) < 2:
                return None, None, "whole-run (view unavailable)"
            t0 = float(xr[0])
            t1 = float(xr[1])
            if not (np.isfinite(t0) and np.isfinite(t1)):
                return None, None, "whole-run (view unavailable)"
            lo = min(t0, t1)
            hi = max(t0, t1)
            if hi <= lo:
                return None, None, "whole-run (view unavailable)"
            return lo, hi, f"view {lo:.3f}..{hi:.3f}s"
        except Exception:
            return None, None, "whole-run (view unavailable)"

    def _run_metrics_status_text(
        self,
        *,
        signal_name: str,
        metric_label: str,
        table_name: str,
        ref_label: str,
        rows_count: int,
        unit: str,
        top_run: str,
        top_value: float,
        mean_value: float,
        median_value: float,
        std_value: float,
        time_desc: str,
    ) -> Tuple[str, str]:
        unit_txt = f" [{unit}]" if str(unit or "").strip() else ""
        line1 = (
            f"Signal={signal_name or '—'} | metric={metric_label}{unit_txt} | "
            f"table={table_name or '—'} | ref={ref_label or '—'} | runs={int(rows_count)}"
        )
        if top_run and np.isfinite(float(top_value)):
            line2 = (
                f"Top run: {top_run} = {float(top_value):.6g}{unit_txt} | "
                f"{time_desc} | mean={float(mean_value):.6g} | median={float(median_value):.6g} | std={float(std_value):.6g}"
            )
        else:
            line2 = f"{time_desc} | no finite values"

        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if analysis_mode == "one_to_all":
            hint = "Use this ranking to see which runs amplify the chosen response most before sweeping one driver across many outputs."
        elif analysis_mode == "all_to_one":
            hint = "Use this spread check to see whether the target response is stable, split or outlier-driven before trusting one lead driver."
        else:
            hint = "Use this scalar slice as a fast bridge between waveform detail and all-to-all cloud structure."
        return line1, f"{line2}\nHeuristic: {hint}"

    def _clear_run_metrics_view(self, note: str = "") -> None:
        self._dist_cache = None
        try:
            if getattr(self, "plot_dist_bar", None) is not None:
                self.plot_dist_bar.clear()
                self.plot_dist_bar.setEnabled(False)
        except Exception:
            pass
        try:
            if getattr(self, "plot_dist_hist", None) is not None:
                self.plot_dist_hist.clear()
                self.plot_dist_hist.setEnabled(False)
        except Exception:
            pass
        try:
            if getattr(self, "plot_dist_kde", None) is not None:
                self.plot_dist_kde.clear()
                self.plot_dist_kde.setEnabled(False)
        except Exception:
            pass
        try:
            self._dist_box_scatter = None
            if getattr(self, "plot_dist_box", None) is not None:
                self.plot_dist_box.clear()
                self.plot_dist_box.setEnabled(False)
        except Exception:
            pass
        try:
            if getattr(self, "tbl_dist", None) is not None:
                self.tbl_dist.setRowCount(0)
                self.tbl_dist.setEnabled(False)
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_dist_note"):
                self.lbl_dist_note.setText(str(note or "Run metrics: —"))
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_dist_stats"):
                self.lbl_dist_stats.setText("")
        except Exception:
            pass
        self._update_workspace_status()

    def _schedule_run_metrics_rebuild(self, *_args, delay_ms: int = 160) -> None:
        timer = getattr(self, "_dist_timer", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        try:
            timer.start(int(delay_ms))
        except Exception:
            pass

    def _on_run_metrics_signal_changed(self, _index: int) -> None:
        try:
            self.dist_signal_selected = str(self.combo_dist_signal.currentText() or "").strip()
        except Exception:
            self.dist_signal_selected = ""
        self._schedule_run_metrics_rebuild(delay_ms=40)

    def _on_run_metrics_mode_changed(self, _index: int) -> None:
        try:
            s = getattr(self, "_settings", None)
            if s is not None:
                s.setValue("dist_mode", self._run_metrics_mode_key())
        except Exception:
            pass
        self._schedule_run_metrics_rebuild(delay_ms=40)

    def _on_run_metrics_table_double_clicked(self, row: int, _col: int) -> None:
        try:
            item = self.tbl_dist.item(int(row), 1)
            if item is None:
                return
            run_label = str(item.data(QtCore.Qt.UserRole) or item.text() or "").strip()
        except Exception:
            return
        sig = str(getattr(self, "dist_signal_selected", "") or "").strip()
        if run_label and sig:
            self._focus_run_signal(run_label, sig)

    def _on_run_metrics_bar_clicked(self, event) -> None:
        cache = dict(getattr(self, "_dist_cache", {}) or {})
        if not cache:
            return
        try:
            pos = event.scenePos() if hasattr(event, "scenePos") else None
            if pos is None:
                return
            vb = self.plot_dist_bar.getViewBox()
            p = vb.mapSceneToView(pos)
            idx = int(round(float(p.x())))
        except Exception:
            return
        rows = list(cache.get("rows", []) or [])
        if idx < 0 or idx >= len(rows):
            return
        row = dict(rows[idx] or {})
        run_label = str(row.get("run") or "").strip()
        sig = str(cache.get("signal") or "").strip()
        if not run_label or not sig:
            return
        try:
            self.tbl_dist.selectRow(idx)
        except Exception:
            pass
        self._focus_run_signal(run_label, sig)

    def _on_run_metrics_box_clicked(self, _item, points, *_args) -> None:
        if points is None:
            return
        try:
            if len(points) <= 0:
                return
        except Exception:
            return
        try:
            point = points[0]
            data = point.data()
            if isinstance(data, np.ndarray):
                data = data.tolist()
            if isinstance(data, (list, tuple)):
                data = data[0] if data else ""
            run_label = str(data or "").strip()
        except Exception:
            return
        cache = dict(getattr(self, "_dist_cache", {}) or {})
        sig = str(cache.get("signal") or "").strip()
        if not run_label or not sig:
            return
        try:
            rows = list(cache.get("rows", []) or [])
            for idx, row in enumerate(rows):
                if str((row or {}).get("run") or "").strip() == run_label:
                    self.tbl_dist.selectRow(int(idx))
                    break
        except Exception:
            pass
        self._focus_run_signal(run_label, sig)

    def _run_metrics_density_curve(
        self,
        values: np.ndarray,
        *,
        points: int = 160,
    ) -> Tuple[np.ndarray, np.ndarray]:
        vals = np.asarray(values, dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size <= 0:
            return np.zeros(0, dtype=float), np.zeros(0, dtype=float)
        if vals.size == 1:
            center = float(vals[0])
            span = max(1.0, abs(center) * 0.2, 1e-6)
            xs = np.linspace(center - span, center + span, max(32, int(points)))
            sigma = max(span / 5.0, 1e-6)
            z = (xs - center) / sigma
            ys = np.exp(-0.5 * z * z) / (sigma * np.sqrt(2.0 * np.pi))
            return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

        vmin = float(np.nanmin(vals))
        vmax = float(np.nanmax(vals))
        spread = float(vmax - vmin)
        std = float(np.nanstd(vals))
        if not np.isfinite(std):
            std = 0.0
        if spread <= 1e-12:
            center = float(np.nanmean(vals))
            span = max(1.0, abs(center) * 0.2, 1e-6)
            xs = np.linspace(center - span, center + span, max(32, int(points)))
            sigma = max(span / 5.0, 1e-6)
            z = (xs - center) / sigma
            ys = np.exp(-0.5 * z * z) / (sigma * np.sqrt(2.0 * np.pi))
            return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

        sigma = max(std, spread / 6.0, 1e-6)
        n = float(len(vals))
        bw = 1.06 * sigma * (n ** (-1.0 / 5.0))
        if not np.isfinite(bw) or bw <= 0.0:
            bw = max(spread / 12.0, sigma * 0.25, 1e-3)
        lo = vmin - 3.0 * bw
        hi = vmax + 3.0 * bw
        xs = np.linspace(lo, hi, max(48, int(points)))
        diffs = (xs[:, None] - vals[None, :]) / bw
        kern = np.exp(-0.5 * diffs * diffs)
        ys = np.sum(kern, axis=1) / (n * bw * np.sqrt(2.0 * np.pi))
        return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

    def _rebuild_run_metrics(self) -> None:
        combo_sig = getattr(self, "combo_dist_signal", None)
        combo_mode = getattr(self, "combo_dist_mode", None)
        if combo_sig is None or combo_mode is None:
            return
        runs = list(self._selected_runs())
        if not runs:
            self._clear_run_metrics_view("Выберите хотя бы один прогон (Runs).")
            return
        if combo_sig.count() <= 0:
            self._refresh_run_metrics_signal_combo()
        sig = str(combo_sig.currentText() or getattr(self, "dist_signal_selected", "") or "").strip()
        if not sig:
            self._clear_run_metrics_view("Выберите signal context для per-run compare.")
            return

        ref_run = self._reference_run(runs) or runs[0]
        mode_key = self._run_metrics_mode_key()
        metric_label = str(combo_mode.currentText() or "").strip() or "Run metric"

        x_ref, y_ref, unit = self._get_xy(ref_run, sig)
        if x_ref.size == 0 or y_ref.size == 0:
            self._clear_run_metrics_view(f"{sig}: нет данных в текущей таблице для reference run.")
            return

        t_play = float("nan")
        try:
            remembered_t = getattr(self, "playhead_time_selected", None)
            if remembered_t is not None and np.isfinite(float(remembered_t)):
                t_play = float(remembered_t)
        except Exception:
            t_play = float("nan")
        if not np.isfinite(t_play):
            try:
                if getattr(self, "_t_ref", np.asarray([])).size:
                    idx = int(max(0, min(self.slider_time.value(), int(len(self._t_ref) - 1))))
                    t_play = float(self._t_ref[idx])
            except Exception:
                t_play = float("nan")
        if not np.isfinite(t_play) and x_ref.size:
            try:
                t_play = float(x_ref[0])
            except Exception:
                t_play = float("nan")

        t0, t1, window_desc = self._current_metrics_time_window()
        is_playhead_mode = mode_key in {"value_at_playhead", "delta_at_playhead"}
        time_desc = f"playhead {t_play:.3f}s" if is_playhead_mode and np.isfinite(t_play) else window_desc

        values: List[Dict[str, object]] = []
        ref_interp = float(np.interp(float(t_play), x_ref, y_ref, left=np.nan, right=np.nan)) if np.isfinite(t_play) else float("nan")
        lo = min(float(t0), float(t1)) if (t0 is not None and t1 is not None and np.isfinite(t0) and np.isfinite(t1)) else None
        hi = max(float(t0), float(t1)) if (t0 is not None and t1 is not None and np.isfinite(t0) and np.isfinite(t1)) else None

        ref_x_use = np.asarray(x_ref, dtype=float)
        ref_y_use = np.asarray(y_ref, dtype=float)
        if lo is not None and hi is not None and ref_x_use.size:
            mask_ref = (ref_x_use >= lo) & (ref_x_use <= hi)
            if bool(np.any(mask_ref)):
                ref_x_use = ref_x_use[mask_ref]
                ref_y_use = ref_y_use[mask_ref]

        for run in runs:
            x, y, _u = self._get_xy(run, sig)
            if x.size == 0 or y.size == 0:
                values.append({"run": str(run.label), "value": float("nan"), "is_ref": bool(run is ref_run)})
                continue
            v = float("nan")
            if mode_key == "value_at_playhead":
                if np.isfinite(t_play):
                    try:
                        v = float(np.interp(float(t_play), x, y, left=np.nan, right=np.nan))
                    except Exception:
                        v = float("nan")
            elif mode_key == "delta_at_playhead":
                if np.isfinite(t_play):
                    try:
                        y0 = float(np.interp(float(t_play), x, y, left=np.nan, right=np.nan))
                    except Exception:
                        y0 = float("nan")
                    v = float(y0 - ref_interp) if np.isfinite(y0) and np.isfinite(ref_interp) else float("nan")
            elif mode_key == "rms_window":
                y_use = np.asarray(y, dtype=float)
                if lo is not None and hi is not None and x.size:
                    mask = (x >= lo) & (x <= hi)
                    if bool(np.any(mask)):
                        y_use = y_use[mask]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    v = float(np.sqrt(np.nanmean(y_use * y_use))) if y_use.size else float("nan")
            elif mode_key in {"rms_delta_window", "maxabs_delta_window"}:
                if ref_x_use.size and ref_y_use.size:
                    try:
                        y_itp = np.interp(ref_x_use, x, y, left=np.nan, right=np.nan)
                    except Exception:
                        y_itp = np.asarray([], dtype=float)
                    if y_itp.size:
                        d = np.asarray(y_itp, dtype=float) - np.asarray(ref_y_use, dtype=float)
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", RuntimeWarning)
                            if mode_key == "rms_delta_window":
                                v = float(np.sqrt(np.nanmean(d * d))) if d.size else float("nan")
                            else:
                                v = float(np.nanmax(np.abs(d))) if d.size else float("nan")
            values.append({"run": str(run.label), "value": float(v), "is_ref": bool(run is ref_run)})

        df = pd.DataFrame(values)
        if df.empty or "value" not in df.columns:
            self._clear_run_metrics_view("Недостаточно данных для per-run distributions.")
            return
        try:
            df = df[np.isfinite(df["value"].values)].copy()
        except Exception:
            df = pd.DataFrame(columns=["run", "value", "is_ref"])
        if df.empty:
            self._clear_run_metrics_view("Недостаточно конечных значений для выбранной метрики.")
            return

        df.sort_values("value", ascending=False, inplace=True, kind="mergesort")
        df.reset_index(drop=True, inplace=True)
        df["rank"] = np.arange(1, len(df) + 1, dtype=int)

        vals = np.asarray(df["value"].values, dtype=float)
        mean_value = float(np.nanmean(vals)) if vals.size else float("nan")
        median_value = float(np.nanmedian(vals)) if vals.size else float("nan")
        std_value = float(np.nanstd(vals)) if vals.size else float("nan")
        top_run = str(df.iloc[0]["run"]) if len(df) else ""
        top_value = float(df.iloc[0]["value"]) if len(df) else float("nan")

        line1, line2 = self._run_metrics_status_text(
            signal_name=sig,
            metric_label=metric_label,
            table_name=str(getattr(self, "current_table", "") or ""),
            ref_label=str(getattr(ref_run, "label", "") or ""),
            rows_count=len(df),
            unit=str(unit or ""),
            top_run=top_run,
            top_value=top_value,
            mean_value=mean_value,
            median_value=median_value,
            std_value=std_value,
            time_desc=time_desc,
        )
        try:
            self.lbl_dist_note.setText(line1)
        except Exception:
            pass
        try:
            self.lbl_dist_stats.setText(line2)
        except Exception:
            pass

        try:
            self.tbl_dist.setSortingEnabled(False)
            self.tbl_dist.clearContents()
            self.tbl_dist.setRowCount(int(len(df)))
            self.tbl_dist.setEnabled(True)
            for i, rec in enumerate(df.itertuples(index=False)):
                rank_item = QtWidgets.QTableWidgetItem(str(int(rec.rank)))
                run_item = QtWidgets.QTableWidgetItem(_trim_label(str(rec.run), 26))
                run_item.setToolTip(str(rec.run))
                run_item.setData(QtCore.Qt.UserRole, str(rec.run))
                val_item = QtWidgets.QTableWidgetItem(f"{float(rec.value):.6g}")
                ref_item = QtWidgets.QTableWidgetItem("ref" if bool(rec.is_ref) else "")
                for item in (rank_item, run_item, val_item, ref_item):
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                if bool(rec.is_ref):
                    for item in (rank_item, run_item, val_item, ref_item):
                        item.setBackground(QtGui.QColor(255, 240, 214))
                self.tbl_dist.setItem(i, 0, rank_item)
                self.tbl_dist.setItem(i, 1, run_item)
                self.tbl_dist.setItem(i, 2, val_item)
                self.tbl_dist.setItem(i, 3, ref_item)
            self.tbl_dist.setSortingEnabled(False)
        except Exception:
            pass

        try:
            self.plot_dist_bar.clear()
            self.plot_dist_bar.setEnabled(True)
            xs = np.arange(len(df), dtype=float)
            ys = np.asarray(df["value"].values, dtype=float)
            ref_mask = np.asarray(df["is_ref"].values, dtype=bool)
            if np.any(~ref_mask):
                bar = pg.BarGraphItem(
                    x=xs[~ref_mask],
                    height=ys[~ref_mask],
                    width=0.75,
                    brush=pg.mkBrush(90, 150, 230, 180),
                    pen=pg.mkPen(50, 90, 150, 220),
                )
                self.plot_dist_bar.addItem(bar)
            if np.any(ref_mask):
                bar_ref = pg.BarGraphItem(
                    x=xs[ref_mask],
                    height=ys[ref_mask],
                    width=0.75,
                    brush=pg.mkBrush(235, 165, 40, 210),
                    pen=pg.mkPen(150, 90, 20, 220),
                )
                self.plot_dist_bar.addItem(bar_ref)
            self.plot_dist_bar.addItem(pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((0, 0, 0, 70), width=1)))
            ticks: List[Tuple[float, str]] = []
            step = max(1, int(np.ceil(len(df) / 12.0)))
            for i, rec in enumerate(df.itertuples(index=False)):
                if (i % step) == 0 or i == int(len(df) - 1):
                    ticks.append((float(i), _trim_label(str(rec.run), 14)))
            try:
                self.plot_dist_bar.getAxis("bottom").setTicks([ticks])
            except Exception:
                pass
            self.plot_dist_bar.setXRange(-0.8, max(0.8, float(len(df) - 0.2)), padding=0)
            self.plot_dist_bar.setLabel("left", f"{metric_label}{' [' + str(unit) + ']' if str(unit or '').strip() else ''}")
            self.plot_dist_bar.setLabel("bottom", "runs (ranked)")
        except Exception:
            pass

        try:
            self.plot_dist_hist.clear()
            self.plot_dist_hist.setEnabled(True)
            if vals.size <= 1 or float(np.nanmin(vals)) == float(np.nanmax(vals)):
                center = float(vals[0])
                width = max(1e-6, abs(center) * 0.1, 1.0)
                centers = np.asarray([center], dtype=float)
                counts = np.asarray([1.0], dtype=float)
            else:
                nbins = min(40, max(8, int(np.sqrt(len(vals)) * 2)))
                counts, edges = np.histogram(vals, bins=nbins)
                centers = 0.5 * (edges[:-1] + edges[1:])
                width = float(edges[1] - edges[0]) * 0.92 if len(edges) >= 2 else 1.0
            hist_bar = pg.BarGraphItem(
                x=np.asarray(centers, dtype=float),
                height=np.asarray(counts, dtype=float),
                width=float(width),
                brush=pg.mkBrush(120, 120, 120, 170),
                pen=pg.mkPen(90, 90, 90, 220),
            )
            self.plot_dist_hist.addItem(hist_bar)
            if np.isfinite(mean_value):
                ln_mean = pg.InfiniteLine(pos=float(mean_value), angle=90, pen=pg.mkPen((50, 120, 210, 210), width=2))
                ln_mean.setToolTip("mean")
                self.plot_dist_hist.addItem(ln_mean)
            if np.isfinite(median_value):
                ln_med = pg.InfiniteLine(pos=float(median_value), angle=90, pen=pg.mkPen((220, 140, 30, 210), width=2, style=QtCore.Qt.DashLine))
                ln_med.setToolTip("median")
                self.plot_dist_hist.addItem(ln_med)
            ref_vals = df[df["is_ref"]]["value"].values
            if len(ref_vals):
                ref_v = float(ref_vals[0])
                if np.isfinite(ref_v):
                    ln_ref = pg.InfiniteLine(pos=ref_v, angle=90, pen=pg.mkPen((170, 40, 40, 210), width=1))
                    ln_ref.setToolTip("reference")
                    self.plot_dist_hist.addItem(ln_ref)
            self.plot_dist_hist.setLabel("bottom", f"{metric_label}{' [' + str(unit) + ']' if str(unit or '').strip() else ''}")
            self.plot_dist_hist.setLabel("left", "count")
        except Exception:
            pass

        try:
            self.plot_dist_kde.clear()
            self.plot_dist_kde.setEnabled(True)
            xs_kde, ys_kde = self._run_metrics_density_curve(vals)
            if xs_kde.size and ys_kde.size and np.isfinite(ys_kde).any():
                curve = pg.PlotDataItem(
                    xs_kde,
                    ys_kde,
                    pen=pg.mkPen(70, 110, 190, 230, width=2),
                    antialias=True,
                )
                self.plot_dist_kde.addItem(curve)
                fill = pg.FillBetweenItem(
                    curve,
                    pg.PlotDataItem(xs_kde, np.zeros_like(xs_kde), pen=pg.mkPen(None)),
                    brush=pg.mkBrush(120, 170, 230, 70),
                )
                self.plot_dist_kde.addItem(fill)
            if np.isfinite(mean_value):
                ln_mean_kde = pg.InfiniteLine(pos=float(mean_value), angle=90, pen=pg.mkPen((50, 120, 210, 210), width=2))
                ln_mean_kde.setToolTip("mean")
                self.plot_dist_kde.addItem(ln_mean_kde)
            if np.isfinite(median_value):
                ln_med_kde = pg.InfiniteLine(pos=float(median_value), angle=90, pen=pg.mkPen((220, 140, 30, 210), width=2, style=QtCore.Qt.DashLine))
                ln_med_kde.setToolTip("median")
                self.plot_dist_kde.addItem(ln_med_kde)
            ref_vals = df[df["is_ref"]]["value"].values
            if len(ref_vals):
                ref_v = float(ref_vals[0])
                if np.isfinite(ref_v):
                    ln_ref_kde = pg.InfiniteLine(pos=ref_v, angle=90, pen=pg.mkPen((170, 40, 40, 210), width=1))
                    ln_ref_kde.setToolTip("reference")
                    self.plot_dist_kde.addItem(ln_ref_kde)
            self.plot_dist_kde.setLabel("bottom", f"{metric_label}{' [' + str(unit) + ']' if str(unit or '').strip() else ''}")
            self.plot_dist_kde.setLabel("left", "density")
        except Exception:
            pass

        try:
            self._dist_box_scatter = None
            self.plot_dist_box.clear()
            self.plot_dist_box.setEnabled(True)
            self.plot_dist_box.setLabel("left", f"{metric_label}{' [' + str(unit) + ']' if str(unit or '').strip() else ''}")
            self.plot_dist_box.setLabel("bottom", "")
            self.plot_dist_box.setXRange(-0.7, 0.7, padding=0)
            try:
                self.plot_dist_box.getAxis("bottom").setTicks([[]])
            except Exception:
                pass

            q1 = float(np.nanpercentile(vals, 25))
            q2 = float(np.nanpercentile(vals, 50))
            q3 = float(np.nanpercentile(vals, 75))
            iqr = float(q3 - q1)
            low_bound = float(q1 - 1.5 * iqr)
            high_bound = float(q3 + 1.5 * iqr)
            inlier_vals = vals[np.isfinite(vals) & (vals >= low_bound) & (vals <= high_bound)]
            whisk_lo = float(np.nanmin(inlier_vals)) if inlier_vals.size else float(np.nanmin(vals))
            whisk_hi = float(np.nanmax(inlier_vals)) if inlier_vals.size else float(np.nanmax(vals))

            box_item = pg.BarGraphItem(
                x=np.asarray([0.0], dtype=float),
                y0=np.asarray([q1], dtype=float),
                height=np.asarray([max(1e-12, q3 - q1)], dtype=float),
                width=0.34,
                brush=pg.mkBrush(150, 150, 150, 80),
                pen=pg.mkPen(100, 100, 100, 220),
            )
            self.plot_dist_box.addItem(box_item)
            for x0, x1, y0, y1, pen in [
                (0.0, 0.0, whisk_lo, q1, pg.mkPen(90, 90, 90, 220, width=1)),
                (0.0, 0.0, q3, whisk_hi, pg.mkPen(90, 90, 90, 220, width=1)),
                (-0.18, 0.18, q2, q2, pg.mkPen(220, 140, 30, 230, width=2)),
                (-0.11, 0.11, whisk_lo, whisk_lo, pg.mkPen(90, 90, 90, 220, width=1)),
                (-0.11, 0.11, whisk_hi, whisk_hi, pg.mkPen(90, 90, 90, 220, width=1)),
            ]:
                self.plot_dist_box.addItem(pg.PlotDataItem([x0, x1], [y0, y1], pen=pen))

            ref_vals = df[df["is_ref"]]["value"].values
            if len(ref_vals):
                ref_v = float(ref_vals[0])
                if np.isfinite(ref_v):
                    ln_ref_box = pg.InfiniteLine(pos=ref_v, angle=0, pen=pg.mkPen((170, 40, 40, 210), width=1, style=QtCore.Qt.DashLine))
                    ln_ref_box.setToolTip("reference")
                    self.plot_dist_box.addItem(ln_ref_box)

            count_vals = int(len(vals))
            if count_vals <= 1:
                jit = np.asarray([0.0], dtype=float)
            else:
                order = np.arange(count_vals, dtype=float)
                span = min(0.24, 0.04 * max(1.0, np.ceil(np.sqrt(count_vals))))
                centered = order - float((count_vals - 1) / 2.0)
                scale = max(1.0, float(np.max(np.abs(centered))))
                jit = (centered / scale) * span

            spots = []
            for j, rec in enumerate(df.itertuples(index=False)):
                is_ref = bool(rec.is_ref)
                spots.append(
                    {
                        "pos": (float(jit[j]), float(rec.value)),
                        "data": str(rec.run),
                        "size": 12 if is_ref else 10,
                        "brush": pg.mkBrush(235, 165, 40, 220) if is_ref else pg.mkBrush(90, 150, 230, 185),
                        "pen": pg.mkPen(150, 90, 20, 220) if is_ref else pg.mkPen(50, 90, 150, 210),
                        "symbol": "o",
                    }
                )
            scatter = pg.ScatterPlotItem(pxMode=True)
            scatter.addPoints(spots)
            try:
                scatter.sigClicked.connect(self._on_run_metrics_box_clicked)
            except Exception:
                pass
            self.plot_dist_box.addItem(scatter)
            self._dist_box_scatter = scatter
        except Exception:
            pass

        self._dist_cache = {
            "signal": sig,
            "metric_key": mode_key,
            "metric_label": metric_label,
            "time_desc": time_desc,
            "table_name": str(getattr(self, "current_table", "") or ""),
            "ref_label": str(getattr(ref_run, "label", "") or ""),
            "unit": str(unit or ""),
            "rows": df[["run", "value", "is_ref"]].to_dict("records"),
        }
        self._update_workspace_status()


    # ---------------- Static (t0) / stroke check ----------------

    def _stroke_signal_names(self, columns: Sequence[object]) -> List[str]:
        out: List[str] = []
        seen: Set[str] = set()
        for col in columns or []:
            name = str(col or "").strip()
            if not name:
                continue
            low = name.lower()
            if ("шток" not in low) and ("stroke" not in low):
                continue
            if name in seen:
                continue
            out.append(name)
            seen.add(name)
        return out

    def _run_stroke_length_m(self, run: Run) -> Optional[float]:
        meta = getattr(run, "meta", None)
        if not isinstance(meta, dict):
            meta = {}
        for key in ("L_stroke_m", "ход_штока_м"):
            try:
                value = meta.get(key)
                if value is None:
                    continue
                value_f = float(value)
                if np.isfinite(value_f) and value_f > 0.0:
                    return float(value_f)
            except Exception:
                pass
        try:
            flat = infl_flatten_meta_numeric(meta) if callable(infl_flatten_meta_numeric) else {}
        except Exception:
            flat = {}
        if isinstance(flat, dict):
            for key, value in flat.items():
                low = str(key or "").strip().lower()
                if not low:
                    continue
                if not (low.endswith("l_stroke_m") or low.endswith("ход_штока_м")):
                    continue
                try:
                    value_f = float(value)
                except Exception:
                    continue
                if np.isfinite(value_f) and value_f > 0.0:
                    return float(value_f)
        return None

    def _static_stroke_signal_table_map(self, run: Run) -> Dict[str, str]:
        table_map: Dict[str, str] = {}
        candidates: List[str] = []
        for candidate in [str(getattr(self, "current_table", "") or "").strip(), "main", "full"]:
            if candidate and candidate in getattr(run, "tables", {}) and candidate not in candidates:
                candidates.append(candidate)
        for candidate in sorted([str(x) for x in getattr(run, "tables", {}).keys() if str(x).strip()]):
            if candidate not in candidates:
                candidates.append(candidate)
        for table_name in candidates:
            df = run.tables.get(table_name)
            if df is None or df.empty:
                continue
            for sig in self._stroke_signal_names(list(df.columns)):
                table_map.setdefault(sig, str(table_name))
        return table_map

    def _static_stroke_default_note(self) -> str:
        return (
            "Static (t0) / stroke check: look for rods sitting far from ~50% stroke at startup. "
            "Cells show stroke % when L_stroke_m is available, otherwise raw transformed t0."
        )

    def _static_stroke_color(
        self,
        dev_from_50_pct: float,
        max_abs_dev_pct: float,
        *,
        is_ref: bool = False,
        has_pct: bool = True,
    ) -> QtGui.QColor:
        try:
            if is_ref:
                return QtGui.QColor(255, 240, 214)
            if not has_pct or not np.isfinite(float(dev_from_50_pct)):
                return QtGui.QColor(244, 244, 244)
            vmax = float(max(max_abs_dev_pct, 5.0))
            a = min(1.0, abs(float(dev_from_50_pct)) / vmax)
            k = int(130 * a)
            if float(dev_from_50_pct) >= 0.0:
                return QtGui.QColor(255, 255 - k, 255 - k)
            return QtGui.QColor(255 - k, 255 - k, 255)
        except Exception:
            return QtGui.QColor(244, 244, 244)

    def _static_stroke_status_text(
        self,
        *,
        ref_label: str,
        runs_count: int,
        signals_count: int,
        worst_run: str,
        worst_signal: str,
        worst_pct: float,
        worst_dev_pct: float,
        have_pct: bool,
        missing_pct_count: int,
    ) -> Tuple[str, str]:
        line1 = (
            f"Static (t0) / stroke check | ref={ref_label or '—'} | runs={int(runs_count)} | "
            f"stroke signals={int(signals_count)} | goal≈50% stroke"
        )
        if have_pct and worst_run and worst_signal and np.isfinite(float(worst_pct)):
            line2 = (
                f"Worst startup offset: {worst_signal} in {worst_run} = {float(worst_pct):.1f}% "
                f"({float(worst_dev_pct):+.1f} pp from 50%). Click a cell to inspect the waveform."
            )
        else:
            line2 = "L_stroke_m metadata is missing, so cells show raw transformed t0 values only."
        if int(missing_pct_count) > 0 and have_pct:
            line2 = f"{line2} {int(missing_pct_count)} cell(s) still have no stroke %."
        return line1, line2

    def _build_static_stroke_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Static (t0) / stroke check", self)
        dock.setObjectName("dock_static_stroke")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea
        )

        root = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.lbl_static_stroke_note = QtWidgets.QLabel(self._static_stroke_default_note())
        self.lbl_static_stroke_note.setWordWrap(True)
        lay.addWidget(self.lbl_static_stroke_note)

        self.lbl_static_stroke_stats = QtWidgets.QLabel("")
        self.lbl_static_stroke_stats.setWordWrap(True)
        self.lbl_static_stroke_stats.setStyleSheet("color:#666;")
        lay.addWidget(self.lbl_static_stroke_stats)

        self.tbl_static_stroke = QtWidgets.QTableWidget()
        self.tbl_static_stroke.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tbl_static_stroke.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_static_stroke.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_static_stroke.setAlternatingRowColors(True)
        self.tbl_static_stroke.setEnabled(False)
        try:
            self.tbl_static_stroke.cellClicked.connect(self._on_static_stroke_cell_clicked)
        except Exception:
            pass
        lay.addWidget(self.tbl_static_stroke, 1)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        try:
            anchor = getattr(self, "dock_run_metrics", None) or getattr(self, "dock_heatmap", None)
            if anchor is not None:
                self.tabifyDockWidget(anchor, dock)
        except Exception:
            pass
        self.dock_static_stroke = dock
        self._clear_static_stroke_view()

    def _clear_static_stroke_view(self, note: str = "") -> None:
        self._static_stroke_cache = None
        try:
            if getattr(self, "tbl_static_stroke", None) is not None:
                self.tbl_static_stroke.clear()
                self.tbl_static_stroke.setRowCount(0)
                self.tbl_static_stroke.setColumnCount(0)
                self.tbl_static_stroke.setEnabled(False)
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_static_stroke_note"):
                self.lbl_static_stroke_note.setText(str(note or self._static_stroke_default_note()))
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_static_stroke_stats"):
                self.lbl_static_stroke_stats.setText("")
        except Exception:
            pass
        self._update_workspace_status()

    def _schedule_static_stroke_rebuild(self, *_args, delay_ms: int = 120) -> None:
        timer = getattr(self, "_static_timer", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        try:
            timer.start(int(delay_ms))
        except Exception:
            pass

    def _rebuild_static_stroke_view(self) -> None:
        tbl = getattr(self, "tbl_static_stroke", None)
        if tbl is None:
            return
        runs = self._ordered_runs_for_reference(self._selected_runs())
        if not runs:
            self._clear_static_stroke_view("Static (t0) / stroke check: выберите хотя бы один run.")
            return

        run_labels = [str(getattr(run, "label", "") or "") for run in runs]
        run_tables = [self._static_stroke_signal_table_map(run) for run in runs]
        sig_labels = sorted({sig for mapping in run_tables for sig in mapping.keys()})
        if not sig_labels:
            self._clear_static_stroke_view(
                "Static (t0) / stroke check: не найдено сигналов штока в current/main/full таблицах."
            )
            return

        raw_t0 = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        time_s = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        stroke_pct = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        dev_pct = np.full((len(sig_labels), len(run_labels)), np.nan, dtype=float)
        unit_map: Dict[str, str] = {}
        payload_map: Dict[Tuple[int, int], Dict[str, object]] = {}

        for j_run, run in enumerate(runs):
            stroke_len_m = self._run_stroke_length_m(run)
            for i_sig, sig in enumerate(sig_labels):
                table_name = str(run_tables[j_run].get(sig, "") or "").strip()
                if not table_name:
                    continue
                x, y, unit = self._get_xy_from_table(
                    run,
                    sig,
                    table_name=table_name,
                    apply_zero_baseline=False,
                )
                if x.size == 0 or y.size == 0:
                    continue
                x = np.asarray(x, dtype=float)
                y = np.asarray(y, dtype=float)
                mask = np.isfinite(x) & np.isfinite(y)
                if not np.any(mask):
                    continue
                idx0 = int(np.flatnonzero(mask)[0])
                t0 = float(x[idx0])
                v0 = float(y[idx0])
                raw_t0[i_sig, j_run] = v0
                time_s[i_sig, j_run] = t0
                unit_map.setdefault(sig, str(unit or ""))
                if stroke_len_m is not None and stroke_len_m > 1e-9 and str(unit or "").lower() in {"mm", "m"}:
                    denom = float(stroke_len_m) * (1000.0 if str(unit).lower() == "mm" else 1.0)
                    if np.isfinite(denom) and denom > 0.0:
                        pct = float(v0 / denom * 100.0)
                        stroke_pct[i_sig, j_run] = pct
                        dev_pct[i_sig, j_run] = float(pct - 50.0)
                payload_map[(i_sig, j_run)] = {
                    "run": str(getattr(run, "label", "") or ""),
                    "signal": str(sig),
                    "time_s": float(t0),
                    "raw_t0": float(v0),
                    "unit": str(unit or ""),
                    "table": str(table_name),
                    "stroke_length_m": None if stroke_len_m is None else float(stroke_len_m),
                    "stroke_pct": float(stroke_pct[i_sig, j_run]) if np.isfinite(stroke_pct[i_sig, j_run]) else float("nan"),
                    "dev_from_50_pct": float(dev_pct[i_sig, j_run]) if np.isfinite(dev_pct[i_sig, j_run]) else float("nan"),
                    "is_ref": bool(j_run == 0),
                }

        finite_pct = stroke_pct[np.isfinite(stroke_pct)]
        finite_dev = dev_pct[np.isfinite(dev_pct)]
        have_pct = finite_pct.size > 0
        max_abs_dev = float(np.nanmax(np.abs(finite_dev))) if finite_dev.size else 5.0
        missing_pct_count = int(np.count_nonzero(np.isfinite(raw_t0) & ~np.isfinite(stroke_pct)))

        try:
            tbl.setSortingEnabled(False)
            tbl.clear()
            tbl.setRowCount(len(sig_labels))
            tbl.setColumnCount(len(run_labels))
            tbl.setHorizontalHeaderLabels([_trim_label(label, 18) for label in run_labels])
            tbl.setVerticalHeaderLabels([_trim_label(label, 28) for label in sig_labels])
            for col, run_label in enumerate(run_labels):
                item = tbl.horizontalHeaderItem(col)
                if item is not None:
                    item.setToolTip(str(run_label))
            for row, sig in enumerate(sig_labels):
                item = tbl.verticalHeaderItem(row)
                if item is not None:
                    item.setToolTip(str(sig))
            for row, sig in enumerate(sig_labels):
                for col, run_label in enumerate(run_labels):
                    payload = dict(payload_map.get((row, col), {}) or {})
                    pct = float(payload.get("stroke_pct", np.nan))
                    raw = float(payload.get("raw_t0", np.nan))
                    dev = float(payload.get("dev_from_50_pct", np.nan))
                    unit = str(payload.get("unit") or "")
                    unit_txt = f" [{unit}]" if unit else ""
                    if np.isfinite(pct):
                        text = f"{pct:.1f}%"
                    elif np.isfinite(raw):
                        text = f"{raw:.4g}"
                    else:
                        text = ""
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setBackground(
                        self._static_stroke_color(
                            dev,
                            max_abs_dev,
                            is_ref=bool(payload.get("is_ref", False)),
                            has_pct=bool(np.isfinite(pct)),
                        )
                    )
                    if payload:
                        tooltip = [
                            f"sig: {sig}",
                            f"run: {run_label}",
                            f"table: {str(payload.get('table') or '—')}",
                            f"t0: {float(payload.get('time_s', np.nan)):.6f} s" if np.isfinite(float(payload.get("time_s", np.nan))) else "t0: —",
                            f"value @ t0: {raw:.6g}{unit_txt}" if np.isfinite(raw) else "value @ t0: —",
                        ]
                        stroke_len_m = payload.get("stroke_length_m")
                        if stroke_len_m is not None and np.isfinite(float(stroke_len_m)):
                            tooltip.append(f"L_stroke: {float(stroke_len_m):.6g} m")
                        if np.isfinite(pct):
                            tooltip.append(f"stroke %: {pct:.3f}%")
                        if np.isfinite(dev):
                            tooltip.append(f"dev from 50%: {dev:+.3f} pp")
                        item.setToolTip("\n".join(tooltip))
                    else:
                        item.setToolTip(f"sig: {sig}\nrun: {run_label}\nNo static stroke value available.")
                    item.setData(QtCore.Qt.UserRole, payload)
                    tbl.setItem(row, col, item)
            try:
                hdr = tbl.horizontalHeader()
                hdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
                tbl.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            except Exception:
                pass
            tbl.setEnabled(True)
        except Exception:
            self._clear_static_stroke_view("Static (t0) / stroke check: не удалось собрать таблицу.")
            return

        worst_run = ""
        worst_signal = ""
        worst_pct = float("nan")
        worst_dev = float("nan")
        if finite_dev.size > 0:
            idx_flat = int(np.nanargmax(np.abs(dev_pct)))
            row_w, col_w = np.unravel_index(idx_flat, dev_pct.shape)
            worst_signal = str(sig_labels[int(row_w)] or "")
            worst_run = str(run_labels[int(col_w)] or "")
            worst_pct = float(stroke_pct[int(row_w), int(col_w)])
            worst_dev = float(dev_pct[int(row_w), int(col_w)])

        line1, line2 = self._static_stroke_status_text(
            ref_label=str(run_labels[0] if run_labels else ""),
            runs_count=len(run_labels),
            signals_count=len(sig_labels),
            worst_run=worst_run,
            worst_signal=worst_signal,
            worst_pct=worst_pct,
            worst_dev_pct=worst_dev,
            have_pct=bool(have_pct),
            missing_pct_count=missing_pct_count,
        )
        try:
            self.lbl_static_stroke_note.setText(line1)
        except Exception:
            pass
        try:
            self.lbl_static_stroke_stats.setText(line2)
        except Exception:
            pass

        self._static_stroke_cache = {
            "runs": list(run_labels),
            "signals": list(sig_labels),
            "raw_t0": raw_t0,
            "time_s": time_s,
            "stroke_pct": stroke_pct,
            "dev_pct": dev_pct,
        }
        self._update_workspace_status()

    def _on_static_stroke_cell_clicked(self, row: int, col: int) -> None:
        tbl = getattr(self, "tbl_static_stroke", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), int(col))
        except Exception:
            item = None
        if item is None:
            return
        try:
            payload = dict(item.data(QtCore.Qt.UserRole) or {})
        except Exception:
            payload = {}
        run_label = str(payload.get("run") or "").strip()
        sig = str(payload.get("signal") or "").strip()
        if not run_label or not sig:
            return
        if not self._focus_run_signal(run_label, sig):
            return
        try:
            t0 = float(payload.get("time_s", np.nan))
            if np.isfinite(t0):
                self._set_playhead_time(t0)
        except Exception:
            pass


    # ---------------- Geometry acceptance (frame / wheel / road) ----------------

    def _geometry_gate_color(self, gate: str) -> QtGui.QColor:
        gate_txt = str(gate or "MISSING").strip().upper()
        if gate_txt == "FAIL":
            return QtGui.QColor(255, 219, 219)
        if gate_txt == "WARN":
            return QtGui.QColor(255, 243, 208)
        if gate_txt == "PASS":
            return QtGui.QColor(220, 247, 220)
        return QtGui.QColor(242, 242, 242)

    def _focus_run_label_preserving_context(self, run_label: str) -> bool:
        label_txt = str(run_label or "").strip()
        if not label_txt or not hasattr(self, "list_runs"):
            return False
        target_row = -1
        for i in range(self.list_runs.count()):
            it = self.list_runs.item(i)
            if it is not None and str(it.text()) == label_txt:
                target_row = i
                break
        if target_row < 0:
            return False
        run_added = False
        try:
            self.list_runs.blockSignals(True)
            it = self.list_runs.item(target_row)
            if it is not None:
                if not it.isSelected():
                    it.setSelected(True)
                    run_added = True
                self._set_current_list_row(self.list_runs, target_row)
            self._runs_selection_explicit = True
            self.runs_selected_paths = [
                self._normalized_run_path(getattr(run, "path", Path("")))
                for run in self._selected_runs()
            ]
        finally:
            try:
                self.list_runs.blockSignals(False)
            except Exception:
                pass
        if run_added:
            self._on_run_selection_changed()
        else:
            self._update_workspace_status()
        return True

    def _geometry_acceptance_status_text(
        self,
        *,
        runs_count: int,
        gate_counts: Dict[str, int],
        worst_run: str,
        worst_gate: str,
        worst_reason: str,
    ) -> Tuple[str, str]:
        parts = []
        for gate in ("FAIL", "WARN", "PASS", "MISSING"):
            n = int(gate_counts.get(gate, 0) or 0)
            if n > 0:
                parts.append(f"{gate}={n}")
        counts_txt = " | ".join(parts) if parts else "no gates"
        line1 = f"Geometry acceptance | runs={int(runs_count)} | {counts_txt}"
        if worst_run and worst_gate:
            line2 = f"Worst run: {worst_run} [{worst_gate}]"
            if str(worst_reason or "").strip():
                line2 = f"{line2} | {str(worst_reason).strip()}"
        else:
            line2 = "No geometry acceptance payloads are available for the current selection."
        return line1, line2

    def _build_geometry_acceptance_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Geometry acceptance", self)
        dock.setObjectName("dock_geometry_acceptance")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea
        )

        root = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.lbl_geometry_note = QtWidgets.QLabel(
            "Geometry acceptance checks the frame / wheel / road solver-point contract across selected runs."
        )
        self.lbl_geometry_note.setWordWrap(True)
        lay.addWidget(self.lbl_geometry_note)

        self.lbl_geometry_stats = QtWidgets.QLabel("")
        self.lbl_geometry_stats.setWordWrap(True)
        self.lbl_geometry_stats.setStyleSheet("color:#666;")
        lay.addWidget(self.lbl_geometry_stats)

        tabs = QtWidgets.QTabWidget()

        tab_matrix = QtWidgets.QWidget()
        mv = QtWidgets.QVBoxLayout(tab_matrix)
        mv.setContentsMargins(6, 6, 6, 6)
        mv.setSpacing(6)
        self.lbl_geometry_matrix = QtWidgets.QLabel(
            "Gate matrix: rows are corners, columns are runs. Click a cell to focus the corresponding run."
        )
        self.lbl_geometry_matrix.setWordWrap(True)
        self.lbl_geometry_matrix.setStyleSheet("color:#666;")
        mv.addWidget(self.lbl_geometry_matrix)
        self.tbl_geometry_gate_matrix = QtWidgets.QTableWidget()
        self.tbl_geometry_gate_matrix.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tbl_geometry_gate_matrix.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_geometry_gate_matrix.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_geometry_gate_matrix.setAlternatingRowColors(False)
        self.tbl_geometry_gate_matrix.setEnabled(False)
        try:
            self.tbl_geometry_gate_matrix.cellClicked.connect(self._on_geometry_acceptance_matrix_clicked)
            self.tbl_geometry_gate_matrix.cellDoubleClicked.connect(self._on_geometry_acceptance_matrix_clicked)
        except Exception:
            pass
        mv.addWidget(self.tbl_geometry_gate_matrix, 1)
        tabs.addTab(tab_matrix, "Gate matrix")

        tab_summary = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(tab_summary)
        sv.setContentsMargins(6, 6, 6, 6)
        sv.setSpacing(6)
        self.tbl_geometry_summary = QtWidgets.QTableWidget()
        self.tbl_geometry_summary.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_geometry_summary.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_geometry_summary.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_geometry_summary.setAlternatingRowColors(True)
        self.tbl_geometry_summary.setEnabled(False)
        try:
            self.tbl_geometry_summary.cellDoubleClicked.connect(self._on_geometry_acceptance_summary_clicked)
        except Exception:
            pass
        sv.addWidget(self.tbl_geometry_summary, 1)
        tabs.addTab(tab_summary, "Runs")

        tab_corner = QtWidgets.QWidget()
        cv = QtWidgets.QVBoxLayout(tab_corner)
        cv.setContentsMargins(6, 6, 6, 6)
        cv.setSpacing(6)
        self.tbl_geometry_corners = QtWidgets.QTableWidget()
        self.tbl_geometry_corners.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_geometry_corners.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_geometry_corners.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_geometry_corners.setAlternatingRowColors(True)
        self.tbl_geometry_corners.setEnabled(False)
        try:
            self.tbl_geometry_corners.cellDoubleClicked.connect(self._on_geometry_acceptance_corner_clicked)
        except Exception:
            pass
        cv.addWidget(self.tbl_geometry_corners, 1)
        tabs.addTab(tab_corner, "Per-corner")

        tab_detail = QtWidgets.QWidget()
        dv = QtWidgets.QVBoxLayout(tab_detail)
        dv.setContentsMargins(6, 6, 6, 6)
        dv.setSpacing(6)
        self.txt_geometry_details = QtWidgets.QPlainTextEdit()
        self.txt_geometry_details.setReadOnly(True)
        self.txt_geometry_details.setPlaceholderText("Detailed geometry acceptance summary will appear here.")
        dv.addWidget(self.txt_geometry_details, 1)
        tabs.addTab(tab_detail, "Details")

        lay.addWidget(tabs, 1)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        try:
            qa = getattr(self, "dock_qa", None)
            events = getattr(self, "dock_events", None)
            if qa is not None:
                self.tabifyDockWidget(qa, dock)
            elif events is not None:
                self.tabifyDockWidget(events, dock)
        except Exception:
            pass
        self.dock_geometry_acceptance = dock
        self._clear_geometry_acceptance_view()

    def _clear_geometry_acceptance_view(self, note: str = "") -> None:
        self._geometry_acceptance_cache = None
        for attr in ("tbl_geometry_gate_matrix", "tbl_geometry_summary", "tbl_geometry_corners"):
            tbl = getattr(self, attr, None)
            if tbl is None:
                continue
            try:
                tbl.clear()
                tbl.setRowCount(0)
                tbl.setColumnCount(0)
                tbl.setEnabled(False)
            except Exception:
                pass
        try:
            if getattr(self, "txt_geometry_details", None) is not None:
                self.txt_geometry_details.setPlainText("")
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_geometry_note"):
                self.lbl_geometry_note.setText(
                    str(note or "Geometry acceptance: select runs to inspect frame / wheel / road contract health.")
                )
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_geometry_stats"):
                self.lbl_geometry_stats.setText("")
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_geometry_matrix"):
                self.lbl_geometry_matrix.setText(
                    "Gate matrix: rows are corners, columns are runs. Click a cell to focus the corresponding run."
                )
        except Exception:
            pass
        self._update_workspace_status()

    def _schedule_geometry_acceptance_rebuild(self, *_args, delay_ms: int = 120) -> None:
        timer = getattr(self, "_geometry_timer", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        try:
            timer.start(int(delay_ms))
        except Exception:
            pass

    def _rebuild_geometry_acceptance_view(self) -> None:
        tbl_matrix = getattr(self, "tbl_geometry_gate_matrix", None)
        tbl_summary = getattr(self, "tbl_geometry_summary", None)
        tbl_corners = getattr(self, "tbl_geometry_corners", None)
        txt_details = getattr(self, "txt_geometry_details", None)
        if tbl_matrix is None or tbl_summary is None or tbl_corners is None or txt_details is None:
            return

        runs = list(self._selected_runs())
        if not runs:
            self._clear_geometry_acceptance_view("Geometry acceptance: выберите хотя бы один run.")
            return

        gate_rank = {"FAIL": 3, "WARN": 2, "PASS": 1, "MISSING": 0}
        summary_rows: List[Dict[str, object]] = []
        corner_rows: List[Dict[str, object]] = []
        detail_lines: List[str] = []
        gate_counts = {"FAIL": 0, "WARN": 0, "PASS": 0, "MISSING": 0}
        worst_run = ""
        worst_gate = ""
        worst_reason = ""
        worst_rank = -1

        for run in runs:
            run_label = str(getattr(run, "label", "") or "").strip()
            acc = dict(getattr(run, "geometry_acceptance", {}) or {})
            gate = str(acc.get("release_gate") or ("MISSING" if not acc else "PASS")).strip().upper()
            if gate not in gate_counts:
                gate = "MISSING"
            reason = str(acc.get("release_gate_reason") or ("geometry acceptance data missing" if not acc else "")).strip()
            fr_min = acc.get("frame_road_min_m")
            wr_min = acc.get("wheel_road_min_m")
            worst_corner = str(acc.get("worst_corner") or "").strip()
            worst_metric = str(acc.get("worst_metric") or "").strip()
            worst_value_m = acc.get("worst_value_m")
            try:
                worst_value_mm = float(worst_value_m) * 1000.0 if worst_value_m is not None else None
            except Exception:
                worst_value_mm = None
            summary_rows.append(
                {
                    "run": run_label,
                    "gate": gate,
                    "reason": reason,
                    "frame_road_min_m": fr_min,
                    "wheel_road_min_m": wr_min,
                    "worst_corner": worst_corner,
                    "worst_metric": worst_metric,
                    "worst_value_mm": worst_value_mm,
                }
            )
            gate_counts[gate] = int(gate_counts.get(gate, 0) or 0) + 1
            rank = int(gate_rank.get(gate, 0))
            if rank > worst_rank:
                worst_rank = rank
                worst_run = run_label
                worst_gate = gate
                worst_reason = reason
            try:
                detail_lines.extend(format_geometry_acceptance_summary_lines(acc, label=run_label))
            except Exception:
                pass
            try:
                rows = build_geometry_acceptance_rows(acc) if acc else []
            except Exception:
                rows = []
            for row in rows:
                row_out = dict(row or {})
                row_out["run"] = run_label
                corner_rows.append(row_out)

        if not summary_rows:
            self._clear_geometry_acceptance_view("Geometry acceptance: нет данных для текущего выбора.")
            return

        line1, line2 = self._geometry_acceptance_status_text(
            runs_count=len(summary_rows),
            gate_counts=gate_counts,
            worst_run=worst_run,
            worst_gate=worst_gate,
            worst_reason=worst_reason,
        )
        try:
            self.lbl_geometry_note.setText(line1)
            self.lbl_geometry_stats.setText(line2)
        except Exception:
            pass

        matrix_ok = False
        matrix_rows_count = 0
        matrix_cols_count = 0
        try:
            run_labels = [str(row.get("run") or "").strip() for row in summary_rows]
            corners_order: List[str] = []
            matrix_by_corner: Dict[str, Dict[str, Dict[str, object]]] = {}
            for row in corner_rows:
                corner = str(row.get("угол") or row.get("corner") or "").strip()
                run_label = str(row.get("run") or "").strip()
                if not corner or not run_label:
                    continue
                if corner not in corners_order:
                    corners_order.append(corner)
                matrix_by_corner.setdefault(corner, {})[run_label] = dict(row or {})

            tbl_matrix.clear()
            tbl_matrix.setRowCount(len(corners_order))
            tbl_matrix.setColumnCount(len(run_labels))
            tbl_matrix.setVerticalHeaderLabels(corners_order)
            tbl_matrix.setHorizontalHeaderLabels(run_labels)

            gate_short = {"FAIL": "F", "WARN": "W", "PASS": "P", "MISSING": "M"}
            for i, corner in enumerate(corners_order):
                by_run = dict(matrix_by_corner.get(corner) or {})
                for j, run_label in enumerate(run_labels):
                    row = dict(by_run.get(run_label) or {})
                    gate = str(row.get("gate") or "MISSING").upper()
                    text = gate_short.get(gate, "M")
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setBackground(self._geometry_gate_color(gate))
                    item.setTextAlignment(int(QtCore.Qt.AlignCenter))
                    item.setData(
                        QtCore.Qt.UserRole,
                        {
                            "run": run_label,
                            "corner": corner,
                            "gate": gate,
                            "reason": str(row.get("reason") or "").strip(),
                        },
                    )
                    tooltip_lines = [f"run: {run_label}", f"corner: {corner}", f"gate: {gate}"]
                    reason = str(row.get("reason") or "").strip()
                    if reason:
                        tooltip_lines.append(reason)
                    for src_key, title in (
                        ("рама‑дорога min, м", "frame-road min"),
                        ("колесо‑дорога min, м", "wheel-road min"),
                        ("Σ err, мм", "sum err"),
                        ("XY wheel-road err, мм", "XY wheel-road"),
                        ("WF err, мм", "WF"),
                        ("WR err, мм", "WR"),
                        ("FR err, мм", "FR"),
                    ):
                        value = row.get(src_key)
                        try:
                            num = float(value)
                        except Exception:
                            continue
                        if np.isfinite(num):
                            tooltip_lines.append(f"{title}: {num:.6g}")
                    missing = str(row.get("missing") or "").strip()
                    if missing:
                        tooltip_lines.append(f"missing: {missing}")
                    item.setToolTip("\n".join(tooltip_lines))
                    if gate in {"FAIL", "WARN"}:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    tbl_matrix.setItem(i, j, item)
            try:
                hdr = tbl_matrix.horizontalHeader()
                for col in range(len(run_labels)):
                    hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
                v_hdr = tbl_matrix.verticalHeader()
                v_hdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            except Exception:
                pass
            matrix_ok = bool(corners_order and run_labels)
            matrix_rows_count = int(len(corners_order))
            matrix_cols_count = int(len(run_labels))
            tbl_matrix.setEnabled(matrix_ok)
            try:
                if hasattr(self, "lbl_geometry_matrix"):
                    self.lbl_geometry_matrix.setText(
                        "Gate matrix: F fail, W warn, P pass, M missing. Click a cell to focus the run."
                    )
            except Exception:
                pass
        except Exception:
            try:
                tbl_matrix.clear()
                tbl_matrix.setRowCount(0)
                tbl_matrix.setColumnCount(0)
                tbl_matrix.setEnabled(False)
            except Exception:
                pass
            try:
                if hasattr(self, "lbl_geometry_matrix"):
                    self.lbl_geometry_matrix.setText(
                        "Gate matrix is temporarily unavailable; summary tables below remain valid."
                    )
            except Exception:
                pass

        try:
            cols = [
                ("run", "run"),
                ("gate", "gate"),
                ("reason", "reason"),
                ("frame_road_min_m", "frame-road min, m"),
                ("wheel_road_min_m", "wheel-road min, m"),
                ("worst_corner", "worst corner"),
                ("worst_metric", "worst metric"),
                ("worst_value_mm", "worst value, mm"),
            ]
            tbl_summary.clear()
            tbl_summary.setRowCount(len(summary_rows))
            tbl_summary.setColumnCount(len(cols))
            tbl_summary.setHorizontalHeaderLabels([c[1] for c in cols])
            for i, row in enumerate(summary_rows):
                gate = str(row.get("gate") or "MISSING").upper()
                bg = self._geometry_gate_color(gate)
                for j, (key, _title) in enumerate(cols):
                    value = row.get(key)
                    if isinstance(value, float):
                        text = "" if not np.isfinite(value) else f"{value:.6g}"
                    elif value is None:
                        text = ""
                    else:
                        text = str(value)
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setBackground(bg)
                    if key == "run":
                        item.setData(QtCore.Qt.UserRole, str(row.get("run") or ""))
                    tbl_summary.setItem(i, j, item)
            try:
                hdr = tbl_summary.horizontalHeader()
                hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
                for col in range(3, len(cols)):
                    hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
            except Exception:
                pass
            tbl_summary.setEnabled(True)
        except Exception:
            self._clear_geometry_acceptance_view("Geometry acceptance: не удалось собрать summary table.")
            return

        try:
            corner_cols = [
                ("run", "run"),
                ("угол", "corner"),
                ("gate", "gate"),
                ("reason", "reason"),
                ("рама‑дорога min, м", "frame-road min, m"),
                ("колесо‑дорога min, м", "wheel-road min, m"),
                ("Σ err, мм", "Σ err, mm"),
                ("XY wheel-road err, мм", "XY wheel-road, mm"),
                ("WF err, мм", "WF err, mm"),
                ("WR err, мм", "WR err, mm"),
                ("FR err, мм", "FR err, mm"),
                ("missing", "missing"),
            ]
            tbl_corners.clear()
            tbl_corners.setRowCount(len(corner_rows))
            tbl_corners.setColumnCount(len(corner_cols))
            tbl_corners.setHorizontalHeaderLabels([c[1] for c in corner_cols])
            for i, row in enumerate(corner_rows):
                gate = str(row.get("gate") or "MISSING").upper()
                bg = self._geometry_gate_color(gate)
                for j, (key, _title) in enumerate(corner_cols):
                    value = row.get(key)
                    if isinstance(value, float):
                        text = "" if not np.isfinite(value) else f"{value:.6g}"
                    elif value is None:
                        text = ""
                    else:
                        text = str(value)
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setBackground(bg)
                    if key == "run":
                        item.setData(QtCore.Qt.UserRole, str(row.get("run") or ""))
                    tbl_corners.setItem(i, j, item)
            try:
                hdr = tbl_corners.horizontalHeader()
                hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
                for col in range(4, len(corner_cols)):
                    hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
            except Exception:
                pass
            tbl_corners.setEnabled(bool(corner_rows))
        except Exception:
            self._clear_geometry_acceptance_view("Geometry acceptance: не удалось собрать per-corner table.")
            return

        try:
            txt_details.setPlainText("\n".join(detail_lines[:96]))
        except Exception:
            pass

        self._geometry_acceptance_cache = {
            "matrix_rows": matrix_rows_count,
            "matrix_cols": matrix_cols_count,
            "matrix_enabled": bool(matrix_ok),
            "summary_rows": summary_rows,
            "corner_rows": corner_rows,
            "gate_counts": gate_counts,
            "worst_run": worst_run,
            "worst_gate": worst_gate,
            "worst_reason": worst_reason,
        }
        self._update_workspace_status()

    def _on_geometry_acceptance_summary_clicked(self, row: int, _col: int) -> None:
        tbl = getattr(self, "tbl_geometry_summary", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), 0)
        except Exception:
            item = None
        if item is None:
            return
        run_label = str(item.data(QtCore.Qt.UserRole) or item.text() or "").strip()
        if run_label:
            self._focus_run_label_preserving_context(run_label)

    def _on_geometry_acceptance_corner_clicked(self, row: int, _col: int) -> None:
        tbl = getattr(self, "tbl_geometry_corners", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), 0)
        except Exception:
            item = None
        if item is None:
            return
        run_label = str(item.data(QtCore.Qt.UserRole) or item.text() or "").strip()
        if run_label:
            self._focus_run_label_preserving_context(run_label)

    def _on_geometry_acceptance_matrix_clicked(self, row: int, col: int) -> None:
        tbl = getattr(self, "tbl_geometry_gate_matrix", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), int(col))
        except Exception:
            item = None
        if item is None:
            return
        try:
            payload = dict(item.data(QtCore.Qt.UserRole) or {})
        except Exception:
            payload = {}
        run_label = str(payload.get("run") or "").strip()
        if run_label:
            self._focus_run_label_preserving_context(run_label)


    # ---------------- Multivariate Explorer (SPLOM / Parallel / 3D) ----------------

    def _build_multivar_dock(self) -> None:
        """Plotly-based multivariate explorer.

        Цель:
        - быстрый качественный анализ взаимовлияний: N параметров → N метрик,
          где метрики получаются из выбранных сигналов (RMS/Max|Δ|/...)
        - linked‑brushing: выделение точек в SPLOM/3D → выделение прогонов в списке

        Принцип UI:
        - без «экспертности»: простые дефолты, минимум шагов,
          безопасные ограничения (max dims / max points).
        """

        dock = QtWidgets.QDockWidget("Multivariate: SPLOM / Parallel / 3D", self)
        dock.setObjectName("DockMultivar")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)

        root = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(root)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self.lbl_mv_banner = QtWidgets.QLabel(
            "Мультипараметрический анализ прогонов. "
            "Выберите прогоны и сигналы слева → здесь появятся SPLOM/Parallel/3D.\n"
            "Подписи осей автоматически сокращаются (чтобы ничего не налезало). "
            "Полные имена — в подсказках и в таблице соответствий."
        )
        self.lbl_mv_banner.setWordWrap(True)
        self.lbl_mv_banner.setStyleSheet("color:#444")
        v.addWidget(self.lbl_mv_banner)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        self.chk_mv_auto = QtWidgets.QCheckBox("Авто‑обновление")
        self.chk_mv_auto.setChecked(True)
        self.chk_mv_auto.setToolTip("Если включено — графики обновляются при изменении выбора прогонов/сигналов (с задержкой).")
        self.chk_mv_auto.stateChanged.connect(lambda _=None: self._schedule_multivar_update(force=True))
        row.addWidget(self.chk_mv_auto)

        self.btn_mv_update = QtWidgets.QPushButton("Обновить сейчас")
        self.btn_mv_update.setToolTip("Пересчитать метрики и обновить все графики в этом доке.")
        self.btn_mv_update.clicked.connect(self._update_multivar_views)
        row.addWidget(self.btn_mv_update)

        row.addWidget(QtWidgets.QLabel("Метрика:"))
        self.combo_mv_metric = QtWidgets.QComboBox()
        self.combo_mv_metric.addItems(["RMS", "Max|Δ|", "Max", "Mean"])
        self.combo_mv_metric.setToolTip(
            "Как сворачивать выбранные сигналы в скалярные метрики для каждого прогона.\n"
            "RMS — хорош для оценки 'энергии' сигнала; Max|Δ| — для пиков/пробоев."
        )
        self.combo_mv_metric.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update(force=True))
        row.addWidget(self.combo_mv_metric)

        self.chk_mv_use_view = QtWidgets.QCheckBox("По видимому интервалу времени")
        self.chk_mv_use_view.setChecked(False)
        self.chk_mv_use_view.setToolTip(
            "Если включено — метрики считаются только в текущем видимом диапазоне времени (zoom) первого графика.\n"
            "Иначе — по всему сигналу."
        )
        self.chk_mv_use_view.stateChanged.connect(lambda _=None: self._schedule_multivar_update(force=True))
        row.addWidget(self.chk_mv_use_view)

        row.addWidget(QtWidgets.QLabel("Сигналов:"))
        self.spin_mv_max_sigs = QtWidgets.QSpinBox()
        self.spin_mv_max_sigs.setRange(1, 32)
        self.spin_mv_max_sigs.setValue(8)
        self.spin_mv_max_sigs.setToolTip("Сколько выбранных сигналов использовать для метрик (лишнее ограничиваем для скорости/понятности).")
        self.spin_mv_max_sigs.valueChanged.connect(lambda _=None: self._schedule_multivar_update(force=True))
        row.addWidget(self.spin_mv_max_sigs)

        row.addStretch(1)
        v.addLayout(row)

        self.lbl_mv_status = QtWidgets.QLabel("")
        self.lbl_mv_status.setWordWrap(True)
        self.lbl_mv_status.setStyleSheet("color:#666")
        v.addWidget(self.lbl_mv_status)

        # Main split: left = columns & mapping, right = tabs
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)

        self.tree_mv_cols = QtWidgets.QTreeWidget()
        self.tree_mv_cols.setHeaderLabels(["Поля (коротко)"])
        self.tree_mv_cols.setToolTip("Отметьте поля, которые хотите видеть в SPLOM/Parallel.\n3D использует отдельные оси.")
        self.tree_mv_cols.header().setStretchLastSection(True)
        self.tree_mv_cols.itemChanged.connect(self._on_mv_dims_changed)
        lv.addWidget(self.tree_mv_cols, 2)

        self.txt_mv_map = QtWidgets.QPlainTextEdit()
        self.txt_mv_map.setReadOnly(True)
        self.txt_mv_map.setPlaceholderText("Таблица соответствия коротких имён (ось) → полных имён появится после расчёта.")
        self.txt_mv_map.setToolTip("Полные названия полей (чтобы не гадать, что скрыто за сокращением).")
        self.txt_mv_map.setMaximumBlockCount(4000)
        lv.addWidget(self.txt_mv_map, 1)

        split.addWidget(left)

        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)

        self.tabs_mv = QtWidgets.QTabWidget()

        # --- SPLOM tab ---
        tab_splom = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(tab_splom)
        sv.setContentsMargins(6, 6, 6, 6)
        sv.setSpacing(6)

        row_s = QtWidgets.QHBoxLayout()
        row_s.addWidget(QtWidgets.QLabel("SPLOM dims:"))
        self.spin_mv_splom_dims = QtWidgets.QSpinBox()
        self.spin_mv_splom_dims.setRange(2, 12)
        self.spin_mv_splom_dims.setValue(6)
        self.spin_mv_splom_dims.setToolTip("Сколько измерений брать в SPLOM (слишком много → превращается в кашу).")
        self.spin_mv_splom_dims.valueChanged.connect(lambda _=None: self._schedule_multivar_update())
        row_s.addWidget(self.spin_mv_splom_dims)

        row_s.addWidget(QtWidgets.QLabel("Color:"))
        self.combo_mv_color = QtWidgets.QComboBox()
        self.combo_mv_color.setToolTip("Чем раскрашивать точки (метрика/параметр).")
        self.combo_mv_color.currentIndexChanged.connect(self._on_mv_projection_combo_changed)
        row_s.addWidget(self.combo_mv_color, 1)
        row_s.addStretch(1)
        sv.addLayout(row_s)

        if PlotlyWebView is not None:
            self.mv_view_splom = PlotlyWebView()
            self.mv_view_splom.runsSelected.connect(self._on_mv_runs_selected)
            sv.addWidget(self.mv_view_splom, 1)
        else:
            self.mv_view_splom = None
            sv.addWidget(QtWidgets.QLabel("Plotly‑view недоступен."))

        self.tabs_mv.addTab(tab_splom, "SPLOM")

        # --- Parallel tab ---
        tab_par = QtWidgets.QWidget()
        pv = QtWidgets.QVBoxLayout(tab_par)
        pv.setContentsMargins(6, 6, 6, 6)
        pv.setSpacing(6)
        row_p = QtWidgets.QHBoxLayout()
        row_p.addWidget(QtWidgets.QLabel("Parallel dims:"))
        self.spin_mv_par_dims = QtWidgets.QSpinBox()
        self.spin_mv_par_dims.setRange(2, 32)
        self.spin_mv_par_dims.setValue(12)
        self.spin_mv_par_dims.setToolTip("Сколько измерений показывать в parallel coordinates.")
        self.spin_mv_par_dims.valueChanged.connect(lambda _=None: self._schedule_multivar_update())
        row_p.addWidget(self.spin_mv_par_dims)
        row_p.addStretch(1)
        pv.addLayout(row_p)

        if PlotlyWebView is not None:
            self.mv_view_par = PlotlyWebView()
            # NOTE: parcoords selection events are limited; keep view only.
            pv.addWidget(self.mv_view_par, 1)
        else:
            self.mv_view_par = None
            pv.addWidget(QtWidgets.QLabel("Plotly‑view недоступен."))

        self.tabs_mv.addTab(tab_par, "Parallel")

        # --- 3D tab ---
        tab_3d = QtWidgets.QWidget()
        tv = QtWidgets.QVBoxLayout(tab_3d)
        tv.setContentsMargins(6, 6, 6, 6)
        tv.setSpacing(6)

        row3 = QtWidgets.QHBoxLayout()
        row3.setSpacing(8)
        row3.addWidget(QtWidgets.QLabel("X:"))
        self.combo_mv_x = QtWidgets.QComboBox(); self.combo_mv_x.currentIndexChanged.connect(self._on_mv_projection_combo_changed)
        row3.addWidget(self.combo_mv_x, 1)
        row3.addWidget(QtWidgets.QLabel("Y:"))
        self.combo_mv_y = QtWidgets.QComboBox(); self.combo_mv_y.currentIndexChanged.connect(self._on_mv_projection_combo_changed)
        row3.addWidget(self.combo_mv_y, 1)
        row3.addWidget(QtWidgets.QLabel("Z:"))
        self.combo_mv_z = QtWidgets.QComboBox(); self.combo_mv_z.currentIndexChanged.connect(self._on_mv_projection_combo_changed)
        row3.addWidget(self.combo_mv_z, 1)
        tv.addLayout(row3)

        row3b = QtWidgets.QHBoxLayout()
        row3b.setSpacing(8)
        row3b.addWidget(QtWidgets.QLabel("3D color:"))
        self.combo_mv_color3d = QtWidgets.QComboBox(); self.combo_mv_color3d.currentIndexChanged.connect(self._on_mv_projection_combo_changed)
        row3b.addWidget(self.combo_mv_color3d, 1)

        row3b.addWidget(QtWidgets.QLabel("Max pts:"))
        self.spin_mv_maxpts = QtWidgets.QSpinBox()
        self.spin_mv_maxpts.setRange(200, 10000)
        self.spin_mv_maxpts.setValue(2500)
        self.spin_mv_maxpts.setToolTip("Сколько точек максимум показывать в 3D (для скорости).")
        self.spin_mv_maxpts.valueChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3b.addWidget(self.spin_mv_maxpts)

        row3b.addWidget(QtWidgets.QLabel("Keep:"))
        self.slider_mv_keep = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_mv_keep.setRange(1, 100)
        self.slider_mv_keep.setValue(100)
        self.slider_mv_keep.setToolTip("Порог прореживания по плотности: 100% — всё, меньше — облако 'тает'.")
        self.slider_mv_keep.valueChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3b.addWidget(self.slider_mv_keep, 2)

        self.combo_mv_keepmode = QtWidgets.QComboBox()
        self.combo_mv_keepmode.addItems(["sparse-first", "dense-first"])
        self.combo_mv_keepmode.setToolTip("Как 'таять': sparse-first — оставляет редкие точки/контуры, dense-first — оставляет ядро плотности.")
        self.combo_mv_keepmode.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3b.addWidget(self.combo_mv_keepmode)

        tv.addLayout(row3b)

        row3c = QtWidgets.QHBoxLayout()
        row3c.setSpacing(8)
        self.chk_mv_pebbles = QtWidgets.QCheckBox("Галька (дискретные события)")
        self.chk_mv_pebbles.setChecked(True)
        self.chk_mv_pebbles.setToolTip("Крупные контрастные точки: прогоны, где случилось выбранное событие/сработка.")
        self.chk_mv_pebbles.stateChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3c.addWidget(self.chk_mv_pebbles)
        row3c.addWidget(QtWidgets.QLabel("Signal:"))
        self.combo_mv_peb_sig = QtWidgets.QComboBox(); self.combo_mv_peb_sig.currentIndexChanged.connect(self._on_mv_peb_sig_changed)
        row3c.addWidget(self.combo_mv_peb_sig, 1)
        self.combo_mv_peb_mode = QtWidgets.QComboBox(); self.combo_mv_peb_mode.addItems(["occurred", "active@t"])
        self.combo_mv_peb_mode.setToolTip("occurred — событие случалось; active@t — активность в текущий момент времени (ползунок).")
        self.combo_mv_peb_mode.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3c.addWidget(self.combo_mv_peb_mode)
        row3c.addStretch(1)
        tv.addLayout(row3c)

        if PlotlyWebView is not None:
            self.mv_view_3d = PlotlyWebView()
            self.mv_view_3d.runsSelected.connect(self._on_mv_runs_selected)
            tv.addWidget(self.mv_view_3d, 1)
        else:
            self.mv_view_3d = None
            tv.addWidget(QtWidgets.QLabel("Plotly‑view недоступен."))

        self.tabs_mv.addTab(tab_3d, "3D")

        rv.addWidget(self.tabs_mv, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)

        v.addWidget(split, 1)

        # hint about dependencies
        if (px is None) or (go is None) or (not HAVE_QTWEBENGINE):
            warn = QtWidgets.QLabel(
                "⚠ Multivariate требует Plotly + QtWebEngine (PySide6-Addons). "
                "Если вкладки пустые — установите зависимости и перезапустите."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color:#6a4b00;background:#fff7d6;border:1px solid #e6d18b;border-radius:6px;padding:6px;")
            v.addWidget(warn)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

        # tabify with influence family
        try:
            if hasattr(self, "dock_influence") and self.dock_influence is not None:
                self.tabifyDockWidget(self.dock_influence, dock)
        except Exception:
            pass

        self.dock_multivar = dock

        # Restore persisted settings
        try:
            self._mv_restoring_settings = True
            s = self._settings
            self.chk_mv_auto.setChecked(
                self._qs_bool(
                    s.value("mv_auto", self.chk_mv_auto.isChecked()),
                    self.chk_mv_auto.isChecked(),
                )
            )
            self.combo_mv_metric.setCurrentText(str(s.value("mv_metric", "RMS")))
            self.chk_mv_use_view.setChecked(
                self._qs_bool(
                    s.value("mv_use_view", self.chk_mv_use_view.isChecked()),
                    self.chk_mv_use_view.isChecked(),
                )
            )
            self.spin_mv_max_sigs.setValue(
                self._qs_int(s.value("mv_max_sigs", self.spin_mv_max_sigs.value()), self.spin_mv_max_sigs.value())
            )
            self.spin_mv_splom_dims.setValue(
                self._qs_int(s.value("mv_splom_dims", self.spin_mv_splom_dims.value()), self.spin_mv_splom_dims.value())
            )
            self.spin_mv_par_dims.setValue(
                self._qs_int(s.value("mv_par_dims", self.spin_mv_par_dims.value()), self.spin_mv_par_dims.value())
            )
            self.spin_mv_maxpts.setValue(
                self._qs_int(s.value("mv_maxpts", self.spin_mv_maxpts.value()), self.spin_mv_maxpts.value())
            )
            self.slider_mv_keep.setValue(
                self._qs_int(s.value("mv_keep", self.slider_mv_keep.value()), self.slider_mv_keep.value())
            )
            self.combo_mv_keepmode.setCurrentText(str(s.value("mv_keepmode", "sparse-first")))
            self._mv_color_selected = str(s.value("mv_color", "") or "")
            self._mv_color3d_selected = str(s.value("mv_color3d", "") or "")
            self._mv_x_selected = str(s.value("mv_x", "") or "")
            self._mv_y_selected = str(s.value("mv_y", "") or "")
            self._mv_z_selected = str(s.value("mv_z", "") or "")
            self.chk_mv_pebbles.setChecked(
                self._qs_bool(
                    s.value("mv_pebbles", self.chk_mv_pebbles.isChecked()),
                    self.chk_mv_pebbles.isChecked(),
                )
            )
            self._mv_peb_sig_selected = str(s.value("mv_peb_sig", "") or "")
            self.combo_mv_peb_mode.setCurrentText(str(s.value("mv_peb_mode", "occurred")))
            if s.contains("mv_checked_dims"):
                self._mv_checked_dims_selected = self._qs_str_list(s.value("mv_checked_dims"))
        except Exception:
            pass
        finally:
            self._mv_restoring_settings = False

        # First paint (debounced)
        self._schedule_multivar_update(force=False)


    def _schedule_multivar_update(self, *, force: bool = False) -> None:
        """Debounced update for multivariate dock."""
        try:
            if not hasattr(self, "dock_multivar") or self.dock_multivar is None:
                return
            if getattr(self, "_mv_restoring_settings", False):
                return
            self._remember_multivar_projection_state()
            # persist
            try:
                s = self._settings
                s.setValue("mv_auto", bool(self.chk_mv_auto.isChecked()))
                s.setValue("mv_metric", str(self.combo_mv_metric.currentText()))
                s.setValue("mv_use_view", bool(self.chk_mv_use_view.isChecked()))
                s.setValue("mv_max_sigs", int(self.spin_mv_max_sigs.value()))
                s.setValue("mv_splom_dims", int(self.spin_mv_splom_dims.value()))
                s.setValue("mv_par_dims", int(self.spin_mv_par_dims.value()))
                s.setValue("mv_maxpts", int(self.spin_mv_maxpts.value()))
                s.setValue("mv_keep", int(self.slider_mv_keep.value()))
                s.setValue("mv_keepmode", str(self.combo_mv_keepmode.currentText()))
                s.setValue("mv_color", str(getattr(self, "_mv_color_selected", "") or self.combo_mv_color.currentText() or ""))
                s.setValue("mv_color3d", str(getattr(self, "_mv_color3d_selected", "") or self.combo_mv_color3d.currentText() or ""))
                s.setValue("mv_x", str(getattr(self, "_mv_x_selected", "") or self.combo_mv_x.currentText() or ""))
                s.setValue("mv_y", str(getattr(self, "_mv_y_selected", "") or self.combo_mv_y.currentText() or ""))
                s.setValue("mv_z", str(getattr(self, "_mv_z_selected", "") or self.combo_mv_z.currentText() or ""))
                s.setValue("mv_pebbles", bool(self.chk_mv_pebbles.isChecked()))
                s.setValue("mv_peb_sig", str(getattr(self, "_mv_peb_sig_selected", "") or self.combo_mv_peb_sig.currentText() or ""))
                s.setValue("mv_peb_mode", str(self.combo_mv_peb_mode.currentText()))
                mv_checked_dims = getattr(self, "_mv_checked_dims_selected", None)
                if mv_checked_dims is None:
                    mv_checked_dims = self._mv_checked_dims()
                s.setValue("mv_checked_dims", json.dumps([str(x) for x in (mv_checked_dims or []) if str(x).strip()]))
            except Exception:
                pass

            if (not force) and (hasattr(self, "chk_mv_auto")) and (not self.chk_mv_auto.isChecked()):
                return
            self._mv_timer.start(260 if not force else 10)
        except Exception:
            return


    def _on_mv_runs_selected(self, run_labels: List[str]) -> None:
        """Linked brushing: selection from Plotly → select runs in the main list."""
        if not run_labels:
            return
        want = set(str(x) for x in run_labels)
        target_rows: List[int] = []
        try:
            for i in range(self.list_runs.count()):
                it = self.list_runs.item(i)
                if it is not None and it.text() in want:
                    target_rows.append(i)
        except Exception:
            target_rows = []
        if not target_rows:
            return
        try:
            self.list_runs.blockSignals(True)
            for i in range(self.list_runs.count()):
                it = self.list_runs.item(i)
                if it is None:
                    continue
                it.setSelected(i in target_rows)
            self._set_current_list_row(self.list_runs, int(target_rows[0]))
        finally:
            self.list_runs.blockSignals(False)
        # rebuild plots after selection change
        try:
            self._on_run_selection_changed()
        except Exception:
            pass

    def _on_mv_peb_sig_changed(self, _index: int) -> None:
        try:
            self._mv_peb_sig_selected = str(self.combo_mv_peb_sig.currentText() or "")
        except Exception:
            self._mv_peb_sig_selected = ""
        self._schedule_multivar_update()

    def _on_mv_projection_combo_changed(self, _index: int) -> None:
        sender = self.sender()
        attr_name = None
        for candidate_attr, combo_name in (
            ("_mv_color_selected", "combo_mv_color"),
            ("_mv_color3d_selected", "combo_mv_color3d"),
            ("_mv_x_selected", "combo_mv_x"),
            ("_mv_y_selected", "combo_mv_y"),
            ("_mv_z_selected", "combo_mv_z"),
        ):
            if sender is getattr(self, combo_name, None):
                attr_name = candidate_attr
                break
        if attr_name:
            try:
                setattr(self, attr_name, str(sender.currentText() or "").strip())
            except Exception:
                pass
        self._schedule_multivar_update()

    def _remember_multivar_projection_state(self) -> None:
        for attr_name, combo_name in (
            ("_mv_color_selected", "combo_mv_color"),
            ("_mv_color3d_selected", "combo_mv_color3d"),
            ("_mv_x_selected", "combo_mv_x"),
            ("_mv_y_selected", "combo_mv_y"),
            ("_mv_z_selected", "combo_mv_z"),
        ):
            combo = getattr(self, combo_name, None)
            if combo is None:
                continue
            try:
                if int(combo.count()) <= 0:
                    continue
                val = str(combo.currentText() or "").strip()
                if not val:
                    continue
                remembered = str(getattr(self, attr_name, "") or "").strip()
                remembered_available = bool(remembered) and (combo.findText(remembered) >= 0)
                if (not remembered) or remembered_available or (val == remembered):
                    setattr(self, attr_name, val)
            except Exception:
                pass

    def _invalidate_multivar_cache(self) -> None:
        self._mv_df_full = None
        self._mv_df_plot = None
        self._mv_map_full_to_short = {}
        self._mv_map_short_to_full = {}
        self._mv_last_key = ""

    def _set_multivar_placeholder(self, view, title: str, note: str) -> None:
        if view is None or PlotlyHtmlSpec is None:
            return
        text = str(note or "").strip() or "Нет данных для отображения."
        fig_json = {
            "data": [],
            "layout": {
                "height": 650,
                "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "showarrow": False,
                        "text": text,
                        "font": {"size": 15, "color": "#666666"},
                        "align": "center",
                    }
                ],
            },
        }
        try:
            view.set_figure(PlotlyHtmlSpec(fig_json=fig_json, title=str(title), allow_select=False))
        except Exception:
            pass

    def _clear_multivar_view(self, note: str = "") -> None:
        self._invalidate_multivar_cache()
        try:
            self.tree_mv_cols.blockSignals(True)
            self.tree_mv_cols.clear()
        except Exception:
            pass
        finally:
            try:
                self.tree_mv_cols.blockSignals(False)
            except Exception:
                pass
        try:
            self.tree_mv_cols.setEnabled(False)
        except Exception:
            pass
        try:
            self.txt_mv_map.setPlainText("")
            self.txt_mv_map.setEnabled(False)
        except Exception:
            pass
        for name in ("combo_mv_color", "combo_mv_color3d", "combo_mv_x", "combo_mv_y", "combo_mv_z", "combo_mv_peb_sig"):
            combo = getattr(self, name, None)
            if combo is None:
                continue
            try:
                combo.blockSignals(True)
                combo.clear()
                if name == "combo_mv_peb_sig":
                    combo.addItem("")
            except Exception:
                pass
            finally:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass
            try:
                combo.setEnabled(False)
            except Exception:
                pass
        self._set_multivar_placeholder(getattr(self, "mv_view_splom", None), "SPLOM", note)
        self._set_multivar_placeholder(getattr(self, "mv_view_par", None), "Parallel", note)
        self._set_multivar_placeholder(getattr(self, "mv_view_3d", None), "3D", note)
        try:
            self.lbl_mv_status.setText(note)
        except Exception:
            pass

    def _multivar_status_text(
        self,
        *,
        runs_count: int,
        sigs_count: int,
        field_count: int,
        metric: str,
        delta_mode: bool,
        dims: List[str],
        xcol: str,
        ycol: str,
        zcol: str,
        keep_pct: int,
        keep_mode: str,
        pebbles: bool,
        peb_signal: str,
        peb_mode: str,
        use_view: bool,
    ) -> str:
        dims_preview = ", ".join([str(x) for x in dims[:4]])
        line1 = (
            f"Runs: {int(runs_count)} | Signals: {int(sigs_count)} | Fields: {int(field_count)} | "
            f"Metric: {metric} | Δ-mode: {bool(delta_mode)}"
        )
        line2 = (
            f"Dims: {dims_preview or 'auto'} | 3D: {xcol or '—'}/{ycol or '—'}/{zcol or '—'} | "
            f"Keep {int(keep_pct)}% ({keep_mode}) | "
            f"{'View-window metrics' if use_view else 'Whole-run metrics'}"
        )
        if pebbles:
            peb_txt = f"Pebbles: {peb_signal} ({peb_mode})" if str(peb_signal or '').strip() else "Pebbles: choose event signal"
        else:
            peb_txt = "Pebbles: off"
        if len(dims) < 3:
            hint = "add 1-2 dims before scouting regimes"
        elif int(keep_pct) <= 15 and int(runs_count) >= 4:
            hint = "very thin cloud: good for outliers, weak for regime cores"
        elif pebbles and (not str(peb_signal or '').strip()):
            hint = "pick a pebble signal to test event-driven separation"
        elif pebbles and str(peb_signal or '').strip():
            hint = "compare cloud geometry with pebble-triggered grains"
        else:
            hint = "brush clusters back into compare plots"
        line3 = f"{peb_txt} | Heuristic: {hint}"
        return "\n".join([line1, line2, line3])


    def _update_multivar_views(self) -> None:
        """Compute multivariate table and render SPLOM/Parallel/3D."""

        if self._mv_updating:
            return
        self._mv_updating = True
        try:
            if (px is None) or (go is None) or (PlotlyWebView is None) or (PlotlyHtmlSpec is None) or (not HAVE_QTWEBENGINE):
                self._clear_multivar_view("Multivariate недоступен: нужны Plotly + QtWebEngine (PySide6-Addons).")
                return

            runs = self._selected_runs()
            if not runs:
                self._clear_multivar_view("Выберите хотя бы один прогон (Runs).")
                return
            if len(runs) < 2:
                self._clear_multivar_view("Выберите минимум 2 прогона для мультипараметрического анализа.")
                return

            # chosen signals for metrics (independent from 'rows' plot grid)
            sig_idxs = [i.row() for i in self.list_signals.selectedIndexes()]
            sigs = [self.available_signals[i] for i in sig_idxs if 0 <= i < len(self.available_signals)]
            sigs = sigs[: int(self.spin_mv_max_sigs.value())]
            if not sigs:
                self._clear_multivar_view("Выберите хотя бы один сигнал (слева), чтобы построить метрики.")
                return

            metric = str(self.combo_mv_metric.currentText() or "RMS")
            use_view = bool(self.chk_mv_use_view.isChecked())
            t0, t1 = None, None
            if use_view and self.plots:
                try:
                    xr = self.plots[0].viewRange()[0]
                    t0, t1 = float(xr[0]), float(xr[1])
                except Exception:
                    t0, t1 = None, None

            # cache key
            key = {
                "runs": [r.label for r in runs],
                "sigs": list(sigs),
                "table": str(self.current_table),
                "metric": metric,
                "delta": bool(getattr(self, "chk_delta", None) and self.chk_delta.isChecked()),
                "ref": self._reference_run_label(runs),
                "use_view": use_view,
                "t0": None if t0 is None else round(t0, 6),
                "t1": None if t1 is None else round(t1, 6),
            }
            key_s = json.dumps(key, sort_keys=True, ensure_ascii=False)
            if key_s != self._mv_last_key:
                df_full, df_plot, map_full_to_short = self._mv_build_dataframe(runs, sigs, metric=metric, t0=t0, t1=t1)
                self._mv_df_full = df_full
                self._mv_df_plot = df_plot
                self._mv_map_full_to_short = dict(map_full_to_short)
                self._mv_map_short_to_full = {v: k for k, v in map_full_to_short.items()}
                self._mv_last_key = key_s
                self._mv_refresh_columns_ui()

            if self._mv_df_plot is None or self._mv_df_plot.empty:
                self._clear_multivar_view("Недостаточно данных для multivariate (пустая таблица после фильтров).")
                return

            dfp = self._mv_df_plot

            # selected dims from tree (checked)
            dims = self._mv_checked_dims()
            if len(dims) < 2:
                # fallback to first metrics/meta
                dims = [c for c in dfp.columns if c != "run"][:6]

            # --- SPLOM ---
            dims_splom = dims[: int(self.spin_mv_splom_dims.value())]
            color = str(self.combo_mv_color.currentText() or "")
            color = color if color in dfp.columns else ""

            fig1 = px.scatter_matrix(
                dfp,
                dimensions=dims_splom,
                color=color if color else None,
                hover_name="run",
                custom_data=["run"],
                height=650,
            )
            try:
                fig1.update_traces(diagonal_visible=False, marker=dict(opacity=0.65))
                fig1.update_layout(margin=dict(l=40, r=20, t=40, b=40))
            except Exception:
                pass

            self.mv_view_splom.set_figure(PlotlyHtmlSpec(fig_json=json.loads(fig1.to_json()), title="SPLOM", allow_select=True))

            # --- Parallel ---
            dims_par = dims[: int(self.spin_mv_par_dims.value())]
            fig2 = px.parallel_coordinates(
                dfp,
                dimensions=dims_par,
                color=color if (color and color in dfp.columns and pd.api.types.is_numeric_dtype(dfp[color])) else None,
                height=650,
            )
            try:
                fig2.update_layout(margin=dict(l=30, r=30, t=30, b=30))
            except Exception:
                pass
            self.mv_view_par.set_figure(PlotlyHtmlSpec(fig_json=json.loads(fig2.to_json()), title="Parallel", allow_select=False))

            # --- 3D ---
            xcol = str(self.combo_mv_x.currentText() or "")
            ycol = str(self.combo_mv_y.currentText() or "")
            zcol = str(self.combo_mv_z.currentText() or "")
            c3 = str(self.combo_mv_color3d.currentText() or "")
            if xcol not in dfp.columns: xcol = dims[0]
            if ycol not in dfp.columns: ycol = dims[1] if len(dims) > 1 else dims[0]
            if zcol not in dfp.columns: zcol = dims[2] if len(dims) > 2 else dims[0]
            if c3 not in dfp.columns: c3 = color if color in dfp.columns else ""

            max_pts = int(self.spin_mv_maxpts.value())
            keep_frac = float(self.slider_mv_keep.value()) / 100.0
            keep_mode = str(self.combo_mv_keepmode.currentText() or "sparse-first")
            use_peb = bool(self.chk_mv_pebbles.isChecked())
            peb_sig = str(self.combo_mv_peb_sig.currentText() or "")
            peb_mode = str(self.combo_mv_peb_mode.currentText() or "occurred")
            # current time in seconds (not slider index)
            t_cur = float("nan")
            try:
                if hasattr(self, "slider_time") and hasattr(self, "_t_ref") and (self._t_ref is not None):
                    idx = int(self.slider_time.value())
                    if 0 <= idx < len(self._t_ref):
                        t_cur = float(self._t_ref[idx])
            except Exception:
                t_cur = float("nan")

            fig3 = self._mv_build_cloud3d(
                dfp,
                runs=runs,
                xcol=xcol,
                ycol=ycol,
                zcol=zcol,
                color_col=c3,
                max_pts=max_pts,
                keep_frac=keep_frac,
                keep_mode=keep_mode,
                pebbles=use_peb,
                peb_signal=peb_sig,
                peb_mode=peb_mode,
                t_cur=t_cur,
            )
            self.mv_view_3d.set_figure(PlotlyHtmlSpec(fig_json=json.loads(fig3.to_json()), title="3D", allow_select=True))

            # status
            self.lbl_mv_status.setText(
                self._multivar_status_text(
                    runs_count=len(runs),
                    sigs_count=len(sigs),
                    field_count=max(0, len(dfp.columns) - 1),
                    metric=metric,
                    delta_mode=bool(getattr(self, 'chk_delta', None) and self.chk_delta.isChecked()),
                    dims=list(dims),
                    xcol=xcol,
                    ycol=ycol,
                    zcol=zcol,
                    keep_pct=int(round(keep_frac * 100.0)),
                    keep_mode=keep_mode,
                    pebbles=use_peb,
                    peb_signal=peb_sig,
                    peb_mode=peb_mode,
                    use_view=use_view,
                )
            )

        finally:
            self._mv_updating = False
            self._update_workspace_status()


    def _mv_checked_dims(self) -> List[str]:
        """Return checked leaf items (short names) from the tree."""
        out: List[str] = []
        try:
            root = self.tree_mv_cols.invisibleRootItem()
            for i in range(root.childCount()):
                cat = root.child(i)
                for j in range(cat.childCount()):
                    it = cat.child(j)
                    if it.checkState(0) == QtCore.Qt.Checked:
                        out.append(str(it.text(0)))
        except Exception:
            return []
        return out


    def _on_mv_dims_changed(self, _item=None, _column=None) -> None:
        try:
            self._mv_checked_dims_selected = list(self._mv_checked_dims())
        except Exception:
            self._mv_checked_dims_selected = []
        self._schedule_multivar_update()


    def _mv_refresh_columns_ui(self) -> None:
        """Populate tree + combos using current df_plot."""
        dfp = self._mv_df_plot
        if dfp is None or dfp.empty:
            return

        # preserve checked dims
        remembered_checked = getattr(self, "_mv_checked_dims_selected", None)
        if remembered_checked is None:
            prev_checked = set(self._mv_checked_dims())
        else:
            prev_checked = {str(x) for x in remembered_checked if str(x).strip()}

        self.tree_mv_cols.blockSignals(True)
        try:
            self.tree_mv_cols.clear()
            root = self.tree_mv_cols.invisibleRootItem()

            meta_cat = QtWidgets.QTreeWidgetItem(["Meta parameters"])
            meta_cat.setFlags(meta_cat.flags() & ~QtCore.Qt.ItemIsSelectable)
            root.addChild(meta_cat)

            met_cat = QtWidgets.QTreeWidgetItem(["Metrics"])
            met_cat.setFlags(met_cat.flags() & ~QtCore.Qt.ItemIsSelectable)
            root.addChild(met_cat)

            cols = [c for c in dfp.columns if c != "run"]
            # heuristic split
            for c in cols:
                parent = met_cat if c.startswith("RMS") or c.startswith("Max") or c.startswith("Mean") else meta_cat
                it = QtWidgets.QTreeWidgetItem([str(c)])
                it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
                it.setCheckState(0, QtCore.Qt.Checked if (c in prev_checked) else QtCore.Qt.Unchecked)
                full = self._mv_map_short_to_full.get(str(c), str(c))
                it.setToolTip(0, full)
                parent.addChild(it)

            self.tree_mv_cols.expandAll()
        finally:
            self.tree_mv_cols.blockSignals(False)
        try:
            self.tree_mv_cols.setEnabled(bool(self.tree_mv_cols.topLevelItemCount()))
        except Exception:
            pass

        # mapping text
        try:
            lines = []
            for full, short in sorted(self._mv_map_full_to_short.items(), key=lambda kv: kv[1].lower()):
                lines.append(f"{short} = {full}")
            self.txt_mv_map.setPlainText("\n".join(lines))
            self.txt_mv_map.setEnabled(bool(lines))
        except Exception:
            pass

        # combos for color/axes
        try:
            cols_all = [c for c in dfp.columns if c != "run"]
            # keep previous current
            def _refill(combo: QtWidgets.QComboBox, items: List[str], prefer: str = ""):
                cur = str(combo.currentText() or prefer)
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(items)
                if cur in items:
                    combo.setCurrentText(cur)
                elif prefer in items:
                    combo.setCurrentText(prefer)
                combo.blockSignals(False)

            default_color = "RMS_mean" if "RMS_mean" in cols_all else (cols_all[0] if cols_all else "")
            prefer_color = str(getattr(self, "_mv_color_selected", "") or default_color)
            prefer_color3d = str(getattr(self, "_mv_color3d_selected", "") or default_color)
            prefer_x = str(getattr(self, "_mv_x_selected", "") or (cols_all[0] if cols_all else ""))
            prefer_y = str(getattr(self, "_mv_y_selected", "") or (cols_all[1] if len(cols_all) > 1 else (cols_all[0] if cols_all else "")))
            prefer_z = str(getattr(self, "_mv_z_selected", "") or (cols_all[2] if len(cols_all) > 2 else (cols_all[0] if cols_all else "")))
            _refill(self.combo_mv_color, cols_all, prefer=prefer_color)
            _refill(self.combo_mv_color3d, cols_all, prefer=prefer_color3d)
            _refill(self.combo_mv_x, cols_all, prefer=prefer_x)
            _refill(self.combo_mv_y, cols_all, prefer=prefer_y)
            _refill(self.combo_mv_z, cols_all, prefer=prefer_z)
            self._remember_multivar_projection_state()
            for combo in (self.combo_mv_color, self.combo_mv_color3d, self.combo_mv_x, self.combo_mv_y, self.combo_mv_z):
                combo.setEnabled(bool(combo.count()))
        except Exception:
            pass

        # pebbles signals options (from events / discrete detection)
        try:
            disc = self._mv_discrete_signal_options()
            remembered_peb = str(getattr(self, "_mv_peb_sig_selected", "") or "").strip()
            remembered_available = bool(remembered_peb) and (remembered_peb in disc)
            cur = str(
                remembered_peb
                if remembered_available
                else (self.combo_mv_peb_sig.currentText() or remembered_peb or "")
            ).strip()
            self.combo_mv_peb_sig.blockSignals(True)
            self.combo_mv_peb_sig.clear()
            self.combo_mv_peb_sig.addItems([""] + disc)
            if cur in disc:
                self.combo_mv_peb_sig.setCurrentText(cur)
            elif disc:
                self.combo_mv_peb_sig.setCurrentText(disc[0])
            self.combo_mv_peb_sig.blockSignals(False)
            self.combo_mv_peb_sig.setEnabled(bool(disc))
            current_peb = str(self.combo_mv_peb_sig.currentText() or "").strip()
            if current_peb and (not remembered_peb or remembered_available or current_peb == remembered_peb):
                self._mv_peb_sig_selected = current_peb
        except Exception:
            pass


    def _mv_discrete_signal_options(self) -> List[str]:
        """Candidate discrete signals for 'pebbles'."""
        opts: List[str] = []
        runs = self._selected_runs()
        if not runs:
            return opts
        try:
            # prefer event markers if available
            sigs = set()
            for r in runs:
                df = getattr(r, "events", None)
                if isinstance(df, pd.DataFrame) and (not df.empty) and ("signal" in df.columns):
                    sigs.update(str(s) for s in df["signal"].astype(str).tolist())
            if sigs:
                opts.extend(sorted([s for s in sigs if s]))
        except Exception:
            pass

        # also attempt detect from reference table
        try:
            ref = self._reference_run(self._selected_runs())
            df = ref.tables.get(self.current_table) if ref is not None else None
            if df is not None and (not df.empty) and ev_scan_run_tables is not None and ev_pick_top_signals is not None:
                evs = ev_scan_run_tables({"tbl": df}, rising_only=True)
                top = ev_pick_top_signals(evs, k=12) or []
                for s in top:
                    if s and (s not in opts):
                        opts.append(str(s))
        except Exception:
            pass

        return opts[:50]


    def _mv_build_dataframe(
        self,
        runs: List[Run],
        sigs: List[str],
        *,
        metric: str = "RMS",
        t0: Optional[float] = None,
        t1: Optional[float] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
        """Build run-level numeric table: meta + scalar metrics (Plotly-friendly)."""

        # --- meta numeric flatten ---
        flats = [infl_flatten_meta_numeric(r.meta) for r in runs]
        feat_names: List[str] = sorted(set().union(*[set(f.keys()) for f in flats]))
        # cap to avoid pathological meta explosions
        feat_names = feat_names[:800]
        X = np.asarray([[float(fl.get(k, np.nan)) for k in feat_names] for fl in flats], dtype=float)

        # prefilter by variance (keeps informative)
        try:
            keep_names = infl_prefilter_features_by_variance(X, feat_names, keep=120)
        except Exception:
            keep_names = feat_names[:120]

        keep_idx = [feat_names.index(k) for k in keep_names if k in feat_names]
        Xk = X[:, keep_idx] if keep_idx else np.zeros((len(runs), 0))

        df_parts: List[pd.DataFrame] = [pd.DataFrame({"run": [r.label for r in runs]})]
        if keep_names:
            meta_cols = {
                nm: (Xk[:, j] if Xk.shape[1] > j else np.full(len(runs), np.nan, dtype=float))
                for j, nm in enumerate(keep_names)
            }
            if meta_cols:
                df_parts.append(pd.DataFrame(meta_cols, index=np.arange(len(runs))))

        # --- scalar metrics from signals ---
        ref = self._reference_run(runs) or runs[0]
        delta_mode = bool(getattr(self, "chk_delta", None) and self.chk_delta.isChecked())

        metric_vals = []
        metric_cols = []

        for sig in sigs:
            x_ref, y_ref, _u = self._get_xy(ref, sig)
            if x_ref.size == 0 or y_ref.size == 0:
                continue
            # time window
            if (t0 is not None) and (t1 is not None) and np.isfinite(t0) and np.isfinite(t1):
                lo, hi = (min(t0, t1), max(t0, t1))
                m = (x_ref >= lo) & (x_ref <= hi)
                if np.any(m):
                    x_use = x_ref[m]
                    yref_use = y_ref[m]
                else:
                    x_use = x_ref
                    yref_use = y_ref
            else:
                x_use = x_ref
                yref_use = y_ref

            col = f"{metric}({self.current_table}.{sig})"
            metric_cols.append(col)
            vals = []
            for r in runs:
                x, y, _u2 = self._get_xy(r, sig)
                if x.size == 0 or y.size == 0:
                    vals.append(float("nan"))
                    continue
                try:
                    y_i = np.interp(x_use, x, y, left=np.nan, right=np.nan)
                except Exception:
                    vals.append(float("nan"))
                    continue
                if delta_mode:
                    y_i = y_i - yref_use

                if metric == "RMS":
                    v = float(np.sqrt(np.nanmean(y_i ** 2)))
                elif metric == "Max|Δ|":
                    v = float(np.nanmax(np.abs(y_i)))
                elif metric == "Max":
                    v = float(np.nanmax(y_i))
                elif metric == "Mean":
                    v = float(np.nanmean(y_i))
                else:
                    v = float(np.sqrt(np.nanmean(y_i ** 2)))
                vals.append(v)
            metric_vals.append(vals)

        metric_frame = pd.DataFrame(
            {
                col: np.asarray(vals, dtype=float)
                for col, vals in zip(metric_cols, metric_vals)
            },
            index=np.arange(len(runs)),
        )
        if not metric_frame.empty:
            df_parts.append(metric_frame)

        df = pd.concat(df_parts, axis=1)

        # aggregate helper metric
        if metric_cols:
            try:
                df[f"{metric}_mean"] = df[metric_cols].mean(axis=1, skipna=True)
            except Exception:
                pass
        try:
            df = df.copy()
        except Exception:
            pass

        # --- make Plotly-friendly short labels ---
        full_cols = [c for c in df.columns if c != "run"]
        map_full_to_short = _shorten_unique(full_cols, max_len=26)
        df_plot = df.rename(columns=map_full_to_short)

        # Ensure numeric dtype where possible
        for c in df_plot.columns:
            if c == "run":
                continue
            try:
                df_plot[c] = pd.to_numeric(df_plot[c], errors="coerce")
            except Exception:
                pass

        return df, df_plot, map_full_to_short


    def _mv_build_cloud3d(
        self,
        dfp: pd.DataFrame,
        *,
        runs: List[Run],
        xcol: str,
        ycol: str,
        zcol: str,
        color_col: str,
        max_pts: int,
        keep_frac: float,
        keep_mode: str,
        pebbles: bool,
        peb_signal: str,
        peb_mode: str,
        t_cur: float,
    ):
        """Build 3D cloud with optional density thinning + 'pebbles' overlay."""

        if go is None:
            return None

        df = dfp.copy()
        # drop NaNs for required axes
        df = df[np.isfinite(df[xcol]) & np.isfinite(df[ycol]) & np.isfinite(df[zcol])]
        if df.empty:
            return go.Figure()

        # limit points first (random)
        if len(df) > int(max_pts):
            df = df.sample(n=int(max_pts), random_state=0)

        # density thinning
        if keep_frac < 0.999 and len(df) >= 30:
            cols_xyz = [xcol, ycol, zcol]
            pts = df[cols_xyz].to_numpy(dtype=float)
            pmin = np.nanmin(pts, axis=0)
            pmax = np.nanmax(pts, axis=0)
            span = np.where((pmax - pmin) <= 1e-12, 1.0, (pmax - pmin))
            pts01 = (pts - pmin) / span
            dens = _knn_density(pts01, k=5)
            order = np.argsort(dens)  # low density first
            keep_n = max(10, int(round(len(df) * float(keep_frac))))
            if str(keep_mode) == "dense-first":
                order = order[::-1]
            keep_idx = order[:keep_n]
            df = df.iloc[keep_idx]

        # base scatter
        cval = df[color_col] if (color_col and (color_col in df.columns)) else None
        fig = go.Figure()
        fig.add_trace(
            go.Scatter3d(
                x=df[xcol],
                y=df[ycol],
                z=df[zcol],
                mode="markers",
                marker=dict(
                    size=4,
                    opacity=0.7,
                    color=cval,
                    colorscale="Viridis",
                    showscale=True if (cval is not None) else False,
                    colorbar=dict(title=str(color_col) if color_col else ""),
                ),
                text=df["run"],
                customdata=df[["run"]].values,
                name="cloud",
                hovertemplate="run=%{text}<br>x=%{x:.4g}<br>y=%{y:.4g}<br>z=%{z:.4g}<extra></extra>",
            )
        )

        # pebbles overlay
        if pebbles and peb_signal:
            try:
                mask = self._mv_pebble_mask(runs, peb_signal, mode=peb_mode, t_cur=t_cur)
                if mask is not None:
                    dfp2 = dfp.copy()
                    dfp2 = dfp2[np.isfinite(dfp2[xcol]) & np.isfinite(dfp2[ycol]) & np.isfinite(dfp2[zcol])]
                    if len(mask) == len(runs):
                        want = set(r.label for r, m in zip(runs, mask) if bool(m))
                        dfp2 = dfp2[dfp2["run"].isin(want)]
                        if not dfp2.empty:
                            fig.add_trace(
                                go.Scatter3d(
                                    x=dfp2[xcol],
                                    y=dfp2[ycol],
                                    z=dfp2[zcol],
                                    mode="markers",
                                    marker=dict(size=9, opacity=0.95, color="red"),
                                    text=dfp2["run"],
                                    customdata=dfp2[["run"]].values,
                                    name=f"pebbles:{peb_signal}",
                                )
                            )
            except Exception:
                pass

        fig.update_layout(
            margin=dict(l=0, r=0, t=20, b=0),
            scene=dict(
                xaxis_title=str(xcol),
                yaxis_title=str(ycol),
                zaxis_title=str(zcol),
            ),
            showlegend=True,
        )
        return fig


    def _mv_pebble_mask(self, runs: List[Run], sig: str, *, mode: str = "occurred", t_cur: float = float("nan")):
        """Return boolean mask (len=runs) for pebbles overlay."""

        out = [False] * len(runs)
        if not sig:
            return out

        if str(mode) == "occurred":
            # fallback: scan tables
            try:
                for i, r in enumerate(runs):
                    df = getattr(r, "events", None)
                    if isinstance(df, pd.DataFrame) and (not df.empty) and ("signal" in df.columns):
                        out[i] = bool((df["signal"].astype(str) == str(sig)).any())
                    else:
                        # last resort: look at the raw column changes
                        tbl = r.tables.get(self.current_table)
                        if tbl is None or tbl.empty or sig not in tbl.columns:
                            continue
                        y = pd.to_numeric(tbl[sig], errors="coerce").to_numpy(dtype=float)
                        out[i] = bool(np.nanmax(y) != np.nanmin(y))
            except Exception:
                pass
            return out

        # active@t
        try:
            for i, r in enumerate(runs):
                x, y, _u = self._get_xy(r, sig)
                if x.size == 0 or y.size == 0:
                    continue
                y0 = float(y[0])
                v = _sample_nearest(x, y, t_cur)
                if np.isfinite(v) and np.isfinite(y0):
                    out[i] = bool(v != y0)
            return out
        except Exception:
            return out


    def _build_qa_dock(self) -> None:
        """QA dock: suspicious signals (run × signal) + issues table.

        Цель — быстрый качественный контроль, чтобы графики не вводили в заблуждение.
        Это не физическая валидация модели.
        """

        dock = QtWidgets.QDockWidget("QA: suspicious signals", self)
        dock.setObjectName("dock_qa_suspicious_signals")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        root = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # Controls row
        row = QtWidgets.QHBoxLayout()
        self.chk_qa_enable = QtWidgets.QCheckBox("QA включено")
        self.chk_qa_enable.setChecked(True)
        self.chk_qa_enable.setToolTip(
            "Лёгкая QA‑проверка результатов: NaN/Inf, пики/скачки, выбросы, дрейф.\n"
            "Не заменяет физическую валидацию — только помогает не верить красивым графикам вслепую."
        )

        row.addWidget(self.chk_qa_enable)

        row.addWidget(QtWidgets.QLabel("Чувствительность:"))
        self.combo_qa_sens = QtWidgets.QComboBox()
        self.combo_qa_sens.addItem("Низкая (меньше ложных)", "low")
        self.combo_qa_sens.addItem("Нормальная", "normal")
        self.combo_qa_sens.addItem("Высокая (больше находок)", "high")
        self.combo_qa_sens.setCurrentIndex(1)
        self.combo_qa_sens.setToolTip("Чем выше — тем больше находок, но риск ложных срабатываний выше.")
        row.addWidget(self.combo_qa_sens)

        self.chk_qa_all = QtWidgets.QCheckBox("Сканировать все сигналы")
        self.chk_qa_all.setChecked(False)
        self.chk_qa_all.setToolTip("По умолчанию сканируются выбранные сигналы (быстрее).")
        row.addWidget(self.chk_qa_all)

        row.addStretch(1)
        self.btn_qa_rescan = QtWidgets.QPushButton("Rescan")
        self.btn_qa_rescan.setToolTip("Пересканировать выбранные runs прямо сейчас.")
        row.addWidget(self.btn_qa_rescan)

        lay.addLayout(row)

        self.lbl_qa_summary = QtWidgets.QLabel("QA: —")
        self.lbl_qa_summary.setWordWrap(True)
        lay.addWidget(self.lbl_qa_summary)

        self.lbl_qa_readout = QtWidgets.QLabel("")
        self.lbl_qa_readout.setWordWrap(True)
        lay.addWidget(self.lbl_qa_readout)

        # Heatmap (signals × runs)
        self.qa_plot = pg.PlotWidget()
        self.qa_plot.setMinimumHeight(220)
        self.qa_plot.setBackground(None)
        self.qa_plot.setMouseEnabled(x=False, y=False)
        self.qa_plot.showGrid(x=False, y=False)
        self.qa_plot.invertY(True)
        self.qa_plot.setEnabled(False)

        self.qa_img = pg.ImageItem(axisOrder='row-major')
        self.qa_plot.addItem(self.qa_img)
        lay.addWidget(self.qa_plot, 1)

        filters_row = QtWidgets.QHBoxLayout()
        filters_row.setSpacing(8)
        filters_row.addWidget(QtWidgets.QLabel("Фильтр таблицы: severity ≥"))
        self.combo_qa_min_sev = QtWidgets.QComboBox()
        self.combo_qa_min_sev.addItem("1 (любая проблема)", 1)
        self.combo_qa_min_sev.addItem("2 (warn+)", 2)
        self.combo_qa_min_sev.addItem("3 (error only)", 3)
        self.combo_qa_min_sev.setCurrentIndex(0)
        self.combo_qa_min_sev.setToolTip("Фильтрует нижнюю таблицу issues. Heatmap сверху остаётся полной картой QA-проблем.")
        filters_row.addWidget(self.combo_qa_min_sev)
        filters_row.addWidget(QtWidgets.QLabel("Codes:"))
        self.btn_qa_codes_all = QtWidgets.QPushButton("All")
        self.btn_qa_codes_all.setToolTip("Включить все коды проблем в таблице ниже.")
        filters_row.addWidget(self.btn_qa_codes_all)
        self.btn_qa_codes_none = QtWidgets.QPushButton("None")
        self.btn_qa_codes_none.setToolTip("Временно скрыть все коды проблем в таблице ниже.")
        filters_row.addWidget(self.btn_qa_codes_none)
        filters_row.addStretch(1)
        lay.addLayout(filters_row)

        self.list_qa_codes = QtWidgets.QListWidget()
        self.list_qa_codes.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.list_qa_codes.setAlternatingRowColors(True)
        self.list_qa_codes.setMaximumHeight(88)
        self.list_qa_codes.setEnabled(False)
        self.list_qa_codes.setToolTip(
            "Чекбоксы фильтруют только issues-table. Heatmap и QA summary сверху всегда строятся по полному scan-результату."
        )
        lay.addWidget(self.list_qa_codes, 0)

        self.lbl_qa_table_filters = QtWidgets.QLabel("")
        self.lbl_qa_table_filters.setWordWrap(True)
        self.lbl_qa_table_filters.setStyleSheet("color:#666;")
        lay.addWidget(self.lbl_qa_table_filters)

        # Issues table
        self.tbl_qa = QtWidgets.QTableWidget()
        self.tbl_qa.setColumnCount(6)
        self.tbl_qa.setHorizontalHeaderLabels(["sev", "run", "signal", "code", "t0", "message"])
        try:
            hdr = self.tbl_qa.horizontalHeader()
            hdr.setStretchLastSection(True)
            hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        except Exception:
            pass
        self.tbl_qa.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_qa.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_qa.setAlternatingRowColors(True)
        self.tbl_qa.setMinimumHeight(180)
        lay.addWidget(self.tbl_qa, 0)

        dock.setWidget(root)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.dock_qa = dock

        # Internal cache
        self._qa_cache_key = None
        self._qa_mat = None
        self._qa_run_labels = []
        self._qa_sig_labels = []
        self._qa_first_t = {}
        self._qa_cell_codes = {}
        self._qa_df = pd.DataFrame()
        self._qa_code_filter_initialized = False
        self._qa_checked_codes_selected: List[str] = []

        # Restore persisted QA settings (loaded earlier)
        try:
            if isinstance(getattr(self, '_restore_after_load', None), dict):
                en = self._restore_after_load.get('qa_enabled', True)
                self.chk_qa_enable.setChecked(self._qs_bool(en, True))
                allsig = self._restore_after_load.get('qa_all', False)
                self.chk_qa_all.setChecked(self._qs_bool(allsig, False))
                sens = str(self._restore_after_load.get('qa_sens', 'normal') or 'normal')
                # match by itemData
                for i in range(self.combo_qa_sens.count()):
                    if str(self.combo_qa_sens.itemData(i)) == sens:
                        self.combo_qa_sens.setCurrentIndex(i)
                        break
        except Exception:
            pass

        # Connections
        self.chk_qa_enable.stateChanged.connect(self._rebuild_qa)
        self.combo_qa_sens.currentIndexChanged.connect(self._rebuild_qa)
        self.chk_qa_all.stateChanged.connect(self._rebuild_qa)
        self.btn_qa_rescan.clicked.connect(lambda: self._rebuild_qa(force=True))
        self.combo_qa_min_sev.currentIndexChanged.connect(self._refresh_qa_table_view)
        self.btn_qa_codes_all.clicked.connect(lambda: self._set_all_qa_code_filters(True))
        self.btn_qa_codes_none.clicked.connect(lambda: self._set_all_qa_code_filters(False))
        try:
            self.list_qa_codes.itemChanged.connect(self._on_qa_code_filter_changed)
        except Exception:
            pass

        try:
            self.qa_plot.scene().sigMouseMoved.connect(self._on_qa_mouse_move)
            self.qa_plot.scene().sigMouseClicked.connect(self._on_qa_mouse_click)
        except Exception:
            pass
        try:
            self.tbl_qa.cellDoubleClicked.connect(self._on_qa_table_double_clicked)
        except Exception:
            pass

        # First paint
        self._rebuild_qa(force=True)

    def _qa_min_severity(self) -> int:
        try:
            return int(self.combo_qa_min_sev.currentData() or 1)
        except Exception:
            return 1

    def _qa_checked_code_filters(self) -> List[str]:
        lst = getattr(self, "list_qa_codes", None)
        if lst is None:
            return []
        out: List[str] = []
        try:
            for i in range(lst.count()):
                it = lst.item(i)
                if it is None:
                    continue
                code = str(it.data(QtCore.Qt.UserRole) or it.text() or "").strip()
                if code and it.checkState() == QtCore.Qt.Checked:
                    out.append(code)
        except Exception:
            return []
        return out

    def _sync_qa_code_filters(self, df: Optional[pd.DataFrame]) -> None:
        lst = getattr(self, "list_qa_codes", None)
        if lst is None:
            return
        if not isinstance(df, pd.DataFrame) or df.empty or "code" not in df.columns:
            try:
                prev = lst.blockSignals(True)
                lst.clear()
                lst.setEnabled(False)
            except Exception:
                prev = False
            finally:
                try:
                    lst.blockSignals(prev)
                except Exception:
                    pass
            self._qa_checked_codes_selected = []
            self._qa_code_filter_initialized = False
            return

        codes = sorted({str(x).strip() for x in df["code"].tolist() if pd.notna(x) and str(x).strip()})
        prev_checked = {str(x).strip() for x in getattr(self, "_qa_checked_codes_selected", []) if str(x).strip()}
        if not getattr(self, "_qa_code_filter_initialized", False):
            checked = set(codes)
        elif prev_checked:
            checked = {code for code in codes if code in prev_checked}
            if not checked:
                checked = set(codes)
        else:
            checked = set()

        prev = False
        try:
            prev = lst.blockSignals(True)
            lst.clear()
            for code in codes:
                it = QtWidgets.QListWidgetItem(code)
                it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
                it.setData(QtCore.Qt.UserRole, code)
                it.setCheckState(QtCore.Qt.Checked if code in checked else QtCore.Qt.Unchecked)
                lst.addItem(it)
            lst.setEnabled(bool(codes))
        except Exception:
            pass
        finally:
            try:
                lst.blockSignals(prev)
            except Exception:
                pass

        self._qa_checked_codes_selected = [code for code in codes if code in checked]
        self._qa_code_filter_initialized = True

    def _set_all_qa_code_filters(self, checked: bool) -> None:
        lst = getattr(self, "list_qa_codes", None)
        if lst is None:
            return
        prev = False
        try:
            prev = lst.blockSignals(True)
            for i in range(lst.count()):
                it = lst.item(i)
                if it is not None:
                    it.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        except Exception:
            pass
        finally:
            try:
                lst.blockSignals(prev)
            except Exception:
                pass
        self._qa_checked_codes_selected = self._qa_checked_code_filters()
        self._qa_code_filter_initialized = True
        self._refresh_qa_table_view()

    def _on_qa_code_filter_changed(self, _item: Optional[QtWidgets.QListWidgetItem] = None) -> None:
        self._qa_checked_codes_selected = self._qa_checked_code_filters()
        self._qa_code_filter_initialized = True
        self._refresh_qa_table_view()

    def _qa_filtered_table_frame(self) -> pd.DataFrame:
        df = getattr(self, "_qa_df", None)
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()
        view = df.copy()
        try:
            view = view[pd.to_numeric(view["severity"], errors="coerce").fillna(0) >= float(self._qa_min_severity())]
        except Exception:
            pass
        if "code" in view.columns:
            checked_codes = self._qa_checked_code_filters()
            if getattr(self, "list_qa_codes", None) is not None and self.list_qa_codes.count() > 0:
                if checked_codes:
                    view = view[view["code"].astype(str).isin([str(x) for x in checked_codes])]
                else:
                    view = view.iloc[0:0].copy()
        return view

    def _refresh_qa_table_view(self) -> None:
        tbl = getattr(self, "tbl_qa", None)
        if tbl is None:
            return
        df = self._qa_filtered_table_frame()
        total_df = getattr(self, "_qa_df", None)
        total_count = int(len(total_df)) if isinstance(total_df, pd.DataFrame) else 0
        visible_count = int(len(df))
        try:
            checked_codes = self._qa_checked_code_filters()
            if total_count <= 0:
                self.lbl_qa_table_filters.setText("")
            else:
                code_txt = (
                    f"codes={len(checked_codes)}"
                    if getattr(self, "list_qa_codes", None) is not None and self.list_qa_codes.count() > 0
                    else "codes=0"
                )
                self.lbl_qa_table_filters.setText(
                    f"Issues table: {visible_count}/{total_count} row(s) after severity ≥ {self._qa_min_severity()} and {code_txt}."
                )
        except Exception:
            pass
        try:
            tbl.setRowCount(0)
            if df is None or df.empty:
                tbl.setEnabled(False)
                return
            rows = df[["severity", "run_label", "signal", "code", "t0", "message"]].values.tolist()
            rows = rows[:500]
            tbl.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for j, val in enumerate(row):
                    it = QtWidgets.QTableWidgetItem("" if val is None else str(val))
                    tbl.setItem(i, j, it)
            tbl.setEnabled(bool(rows))
        except Exception:
            pass

    def _qa_status_text(
        self,
        *,
        table: str,
        runs_count: int,
        sigs_count: int,
        sensitivity: str,
        issues_count: int,
        err_count: int,
        warn_count: int,
        top_run: str = "",
        top_sig: str = "",
        top_time_s: float = float("nan"),
        top_severity: float = float("nan"),
    ) -> str:
        line1 = (
            f"QA: issues={int(issues_count)} (err={int(err_count)}, warn={int(warn_count)}) | "
            f"table={table or '—'} | runs={int(runs_count)} | sigs={int(sigs_count)} | sens={sensitivity}"
        )
        if int(issues_count) <= 0:
            line2 = "Top suspect: none"
        elif top_run and top_sig and np.isfinite(float(top_time_s)):
            sev_txt = f" | sev={float(top_severity):g}" if np.isfinite(float(top_severity)) else ""
            line2 = f"Top suspect: {top_sig} in {top_run} @ {float(top_time_s):.4f}s{sev_txt}"
        else:
            line2 = "Top suspect: see the brightest QA cell or first table row"

        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if int(issues_count) <= 0:
            if analysis_mode == "all_to_all":
                hint = "No obvious QA blockers: compare cloud clusters with heatmap hotspots instead of debugging data quality first."
            else:
                hint = "No obvious QA blockers: move on to heatmaps / influence and test the current explanation."
        elif analysis_mode == "one_to_all":
            hint = "Use QA as a guardrail: if the hotspot is artefactual, do not trust fan-out conclusions yet."
        elif analysis_mode == "all_to_one":
            hint = "Validate the target waveform here before accepting any lead driver from Influence(t)."
        else:
            hint = "Treat QA as the veto layer before trusting cluster separation or corridor structure."
        return "\n".join([line1, line2, f"Heuristic: {hint}"])

    def _events_status_text(
        self,
        *,
        baseline_label: str,
        rows_count: int,
        selected_signals: Sequence[str],
        have_filter_items: bool,
        no_signals_selected: bool,
        sample_signal: str = "",
        sample_time_s: float = float("nan"),
    ) -> str:
        pick = [str(x) for x in (selected_signals or []) if str(x).strip()]
        line1 = (
            f"Events: {int(rows_count)} | baseline={baseline_label or '—'} | "
            f"filters={len(pick) if have_filter_items else 0}"
        )
        if no_signals_selected:
            line2 = "Focus: no event signals selected"
        elif sample_signal and np.isfinite(float(sample_time_s)):
            line2 = f"Focus: {sample_signal} @ {float(sample_time_s):.4f}s"
        elif sample_signal:
            line2 = f"Focus: {sample_signal}"
        elif rows_count > 0:
            line2 = "Focus: earliest visible event"
        else:
            line2 = "Focus: no visible events"

        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        if no_signals_selected:
            hint = "Pick one or more event signals to turn the table into an explanatory filter, not just a log."
        elif analysis_mode == "one_to_all":
            hint = "Check whether one discrete trigger propagates into several nearby response hotspots."
        elif analysis_mode == "all_to_one":
            hint = "Use nearby events to confirm or reject the current target-driver explanation."
        else:
            hint = "Compare these event grains with cloud clusters and pebbles to see whether structure is event-driven."
        return "\n".join([line1, line2, f"Heuristic: {hint}"])


    def _build_events_dock(self):
        """Dock: discrete events table for baseline run (first selected)."""
        self.dock_events = QtWidgets.QDockWidget("Events", self)
        self.dock_events.setObjectName("dock_events")

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        lbl = QtWidgets.QLabel(
            "Discrete events = переключения дискретных сигналов (0/1/2...). "
            "Показываем их для baseline (reference run). Двойной клик → playhead в момент события."
        )
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        self.lbl_events_info = QtWidgets.QLabel("Events: none")
        self.lbl_events_info.setWordWrap(True)
        lay.addWidget(self.lbl_events_info)

        tabs = QtWidgets.QTabWidget()
        self.tabs_events_panel = tabs
        try:
            tabs.currentChanged.connect(self._on_events_dock_tab_changed)
        except Exception:
            pass

        tab_table = QtWidgets.QWidget()
        table_lay = QtWidgets.QVBoxLayout(tab_table)
        table_lay.setContentsMargins(6, 6, 6, 6)
        table_lay.setSpacing(6)

        self.tbl_events = QtWidgets.QTableWidget(0, 5)
        self.tbl_events.setHorizontalHeaderLabels(["t, s", "signal", "from", "to", "table"])
        try:
            self.tbl_events.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass
        self.tbl_events.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_events.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_events.setSortingEnabled(True)
        try:
            self.tbl_events.cellDoubleClicked.connect(self._on_event_row_double_clicked)
        except Exception:
            pass
        table_lay.addWidget(self.tbl_events, 1)
        tabs.addTab(tab_table, "Table")

        tab_timeline = QtWidgets.QWidget()
        timeline_lay = QtWidgets.QVBoxLayout(tab_timeline)
        timeline_lay.setContentsMargins(6, 6, 6, 6)
        timeline_lay.setSpacing(6)

        self.lbl_events_timeline_note = QtWidgets.QLabel(
            "Timeline: visible baseline events as a raster-like layer. Click a point to focus signal and move playhead."
        )
        self.lbl_events_timeline_note.setWordWrap(True)
        timeline_lay.addWidget(self.lbl_events_timeline_note)

        self.plot_events_timeline = None
        self.scatter_events_timeline = None
        self.line_events_timeline = None
        self._events_timeline_proxy = None
        self.lbl_events_timeline_readout = QtWidgets.QLabel("")
        self.lbl_events_timeline_readout.setWordWrap(True)

        if pg is None:
            timeline_lay.addWidget(QtWidgets.QLabel("Events timeline unavailable: pyqtgraph not found"))
        else:
            try:
                self.plot_events_timeline = pg.PlotWidget()
                self.plot_events_timeline.setMinimumHeight(240)
                self.plot_events_timeline.setBackground(None)
                self.plot_events_timeline.showGrid(x=True, y=False, alpha=0.20)
                self.plot_events_timeline.setMouseEnabled(x=True, y=False)
                self.plot_events_timeline.invertY(True)
                try:
                    self.plot_events_timeline.setLabel("bottom", "t, s")
                except Exception:
                    pass
                self.plot_events_timeline.setEnabled(False)
                self.scatter_events_timeline = pg.ScatterPlotItem(pxMode=True)
                self.plot_events_timeline.addItem(self.scatter_events_timeline)
                self.line_events_timeline = pg.InfiniteLine(
                    angle=90, movable=False, pen=pg.mkPen((255, 140, 0, 190), width=2)
                )
                self.plot_events_timeline.addItem(self.line_events_timeline)
                try:
                    self.line_events_timeline.hide()
                except Exception:
                    pass
                try:
                    self.scatter_events_timeline.sigClicked.connect(self._on_events_timeline_points_clicked)
                except Exception:
                    pass
                try:
                    self._events_timeline_proxy = pg.SignalProxy(
                        self.plot_events_timeline.scene().sigMouseMoved,
                        rateLimit=60,
                        slot=self._on_events_timeline_mouse_moved,
                    )
                except Exception:
                    self._events_timeline_proxy = None
                timeline_lay.addWidget(self.plot_events_timeline, 1)
                timeline_lay.addWidget(self.lbl_events_timeline_readout)
            except Exception as e:
                self.plot_events_timeline = None
                timeline_lay.addWidget(QtWidgets.QLabel(f"Events timeline init failed: {e}"))

        tabs.addTab(tab_timeline, "Timeline")

        tab_compare = QtWidgets.QWidget()
        compare_lay = QtWidgets.QVBoxLayout(tab_compare)
        compare_lay.setContentsMargins(6, 6, 6, 6)
        compare_lay.setSpacing(6)

        self.lbl_events_compare = QtWidgets.QLabel(
            "Mismatch vs ref: rows are visible baseline event signals, columns are selected runs."
        )
        self.lbl_events_compare.setWordWrap(True)
        self.lbl_events_compare.setStyleSheet("color:#666;")
        compare_lay.addWidget(self.lbl_events_compare)

        self.tbl_events_compare = QtWidgets.QTableWidget()
        self.tbl_events_compare.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tbl_events_compare.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_events_compare.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        try:
            self.tbl_events_compare.horizontalHeader().setStretchLastSection(False)
            self.tbl_events_compare.verticalHeader().setVisible(True)
        except Exception:
            pass
        try:
            self.tbl_events_compare.cellClicked.connect(self._on_events_compare_cell_clicked)
            self.tbl_events_compare.cellDoubleClicked.connect(self._on_events_compare_cell_clicked)
        except Exception:
            pass
        compare_lay.addWidget(self.tbl_events_compare, 1)

        tabs.addTab(tab_compare, "Mismatch vs ref")

        tab_runs = QtWidgets.QWidget()
        runs_lay = QtWidgets.QVBoxLayout(tab_runs)
        runs_lay.setContentsMargins(6, 6, 6, 6)
        runs_lay.setSpacing(6)

        self.lbl_events_runs_note = QtWidgets.QLabel(
            "Runs raster: visible event signals across all selected runs. Click a point to focus run / signal and move playhead."
        )
        self.lbl_events_runs_note.setWordWrap(True)
        runs_lay.addWidget(self.lbl_events_runs_note)

        self.plot_events_runs = None
        self.scatter_events_runs = None
        self.line_events_runs = None
        self._events_runs_proxy = None
        self.lbl_events_runs_readout = QtWidgets.QLabel("")
        self.lbl_events_runs_readout.setWordWrap(True)

        if pg is None:
            runs_lay.addWidget(QtWidgets.QLabel("Runs raster unavailable: pyqtgraph not found"))
        else:
            try:
                self.plot_events_runs = pg.PlotWidget()
                self.plot_events_runs.setMinimumHeight(240)
                self.plot_events_runs.setBackground(None)
                self.plot_events_runs.showGrid(x=True, y=False, alpha=0.20)
                self.plot_events_runs.setMouseEnabled(x=True, y=False)
                self.plot_events_runs.invertY(True)
                try:
                    self.plot_events_runs.setLabel("bottom", "t, s")
                except Exception:
                    pass
                self.plot_events_runs.setEnabled(False)
                self.scatter_events_runs = pg.ScatterPlotItem(pxMode=True)
                self.plot_events_runs.addItem(self.scatter_events_runs)
                self.line_events_runs = pg.InfiniteLine(
                    angle=90, movable=False, pen=pg.mkPen((255, 140, 0, 190), width=2)
                )
                self.plot_events_runs.addItem(self.line_events_runs)
                try:
                    self.line_events_runs.hide()
                except Exception:
                    pass
                try:
                    self.scatter_events_runs.sigClicked.connect(self._on_events_runs_points_clicked)
                except Exception:
                    pass
                try:
                    self._events_runs_proxy = pg.SignalProxy(
                        self.plot_events_runs.scene().sigMouseMoved,
                        rateLimit=60,
                        slot=self._on_events_runs_mouse_moved,
                    )
                except Exception:
                    self._events_runs_proxy = None
                runs_lay.addWidget(self.plot_events_runs, 1)
                runs_lay.addWidget(self.lbl_events_runs_readout)
            except Exception as e:
                self.plot_events_runs = None
                runs_lay.addWidget(QtWidgets.QLabel(f"Runs raster init failed: {e}"))

        tabs.addTab(tab_runs, "Runs raster")
        lay.addWidget(tabs, 1)

        self.dock_events.setWidget(w)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_events)
        try:
            if hasattr(self, 'dock_qa') and self.dock_qa is not None:
                self.tabifyDockWidget(self.dock_qa, self.dock_events)
        except Exception:
            pass


    def _on_event_row_double_clicked(self, row: int, col: int):
        try:
            _ = int(col)
            row = int(row)
            it_t = self.tbl_events.item(row, 0)
            it_sig = self.tbl_events.item(row, 1)
            it_tab = self.tbl_events.item(row, 4)
            if it_t is None:
                return
            t = float(str(it_t.text()).strip())
            if not np.isfinite(t):
                return
            sig = str(it_sig.text()).strip() if it_sig is not None else ""
            want_table = str(it_tab.text()).strip() if it_tab is not None else ""

            ref = self._reference_run(self._selected_runs())
            ref_label = str(getattr(ref, "label", "") or "").strip()
            candidate_runs = list(self._selected_runs())
            if ref is not None and all(str(getattr(run, "label", "") or "").strip() != ref_label for run in candidate_runs):
                candidate_runs.append(ref)
            probe_table = str(want_table or getattr(self, "current_table", "") or "").strip()
            if want_table:
                table_possible = False
                for run in candidate_runs:
                    try:
                        if want_table in getattr(run, "tables", {}):
                            table_possible = True
                            break
                    except Exception:
                        pass
                if not table_possible:
                    return
            if sig and probe_table:
                sig_possible = False
                for run in candidate_runs:
                    try:
                        df_probe = getattr(run, "tables", {}).get(probe_table)
                    except Exception:
                        df_probe = None
                    if isinstance(df_probe, pd.DataFrame) and sig in df_probe.columns:
                        sig_possible = True
                        break
                if not sig_possible:
                    return
            def _selected_run_labels_now() -> List[str]:
                return [str(getattr(run, "label", "") or "").strip() for run in self._selected_runs()]

            def _select_run_labels(labels: Sequence[str], *, current_label: str = "") -> bool:
                if not hasattr(self, 'list_runs'):
                    return False
                label_list = [str(x).strip() for x in labels if str(x).strip()]
                if not label_list:
                    return False
                label_set = set(label_list)
                changed = False
                picked_paths: List[str] = []
                current_row = -1
                try:
                    self.list_runs.blockSignals(True)
                    for i in range(self.list_runs.count()):
                        it = self.list_runs.item(i)
                        if it is None:
                            continue
                        is_target = str(it.text()) in label_set
                        if it.isSelected() != is_target:
                            changed = True
                        it.setSelected(is_target)
                        if is_target:
                            key = it.data(QtCore.Qt.UserRole)
                            key = str(key).strip() if key is not None else ""
                            if key:
                                picked_paths.append(key)
                            if current_label and str(it.text()) == str(current_label):
                                current_row = i
                            elif current_row < 0:
                                current_row = i
                    if current_row >= 0:
                        self._set_current_list_row(self.list_runs, current_row)
                    self._runs_selection_explicit = True
                    if picked_paths:
                        self.runs_selected_paths = list(picked_paths)
                finally:
                    try:
                        self.list_runs.blockSignals(False)
                    except Exception:
                        pass
                if ref is not None:
                    try:
                        self._remember_reference_run(ref)
                    except Exception:
                        pass
                if changed:
                    try:
                        self._on_run_selection_changed()
                    except Exception:
                        pass
                return True

            def _set_table_if_available(name: str) -> bool:
                if not name or not hasattr(self, "combo_table"):
                    return False
                try:
                    idx = self.combo_table.findText(name)
                except Exception:
                    idx = -1
                if idx < 0:
                    return False
                if str(self.combo_table.currentText() or "") != name:
                    try:
                        self.combo_table.setCurrentIndex(idx)
                    except Exception:
                        return False
                return True

            current_labels = _selected_run_labels_now()
            if ref_label and ref_label not in current_labels:
                _select_run_labels(current_labels + [ref_label], current_label=ref_label)
                current_labels = _selected_run_labels_now()

            if want_table and not _set_table_if_available(want_table):
                compat_labels = []
                for run in self._selected_runs():
                    try:
                        if want_table in getattr(run, "tables", {}):
                            compat_labels.append(str(getattr(run, "label", "") or "").strip())
                    except Exception:
                        pass
                if ref_label and ref is not None:
                    try:
                        if want_table in getattr(ref, "tables", {}) and ref_label not in compat_labels:
                            compat_labels.insert(0, ref_label)
                    except Exception:
                        pass
                if compat_labels:
                    _select_run_labels(compat_labels, current_label=ref_label or compat_labels[0])
                    _set_table_if_available(want_table)

            if sig and sig not in list(getattr(self, "available_signals", []) or []):
                table_name = str(want_table or getattr(self, "current_table", "") or "").strip()
                compat_labels = []
                for run in self._selected_runs():
                    try:
                        df_sig = getattr(run, "tables", {}).get(table_name)
                    except Exception:
                        df_sig = None
                    if isinstance(df_sig, pd.DataFrame) and sig in df_sig.columns:
                        compat_labels.append(str(getattr(run, "label", "") or "").strip())
                if ref_label and ref is not None:
                    try:
                        df_ref = getattr(ref, "tables", {}).get(table_name)
                    except Exception:
                        df_ref = None
                    if isinstance(df_ref, pd.DataFrame) and sig in df_ref.columns and ref_label not in compat_labels:
                        compat_labels.insert(0, ref_label)
                if compat_labels:
                    _select_run_labels(compat_labels, current_label=ref_label or compat_labels[0])
                    if want_table:
                        _set_table_if_available(want_table)

            focus_ok = not bool(sig)
            try:
                if sig:
                    focus_ok = bool(self._select_signal_by_name(sig, exclusive=True))
                    if focus_ok:
                        self._rebuild_plots()
            except Exception:
                focus_ok = False

            if not focus_ok:
                return

            self._set_playhead_time(float(t))
        except Exception:
            return

    def _events_dock_current_subtarget(self) -> str:
        tabs = getattr(self, "tabs_events_panel", None)
        if not isinstance(tabs, QtWidgets.QTabWidget):
            return ""
        try:
            idx = int(tabs.currentIndex())
        except Exception:
            return ""
        if idx < 0:
            return ""
        try:
            return str(tabs.tabText(idx) or "").strip()
        except Exception:
            return ""

    def _events_dock_route_label(self, subtarget: str, *, short: bool = False) -> str:
        key = str(subtarget or "").strip()
        mapping = {
            "Table": "Events",
            "Timeline": "Events timeline" if not short else "Timeline",
            "Mismatch vs ref": "Event mismatch" if not short else "Mismatch",
            "Runs raster": "Runs raster",
        }
        return str(mapping.get(key, "Events") or "Events")

    def _set_events_dock_tab(self, subtarget: str) -> bool:
        tabs = getattr(self, "tabs_events_panel", None)
        if not isinstance(tabs, QtWidgets.QTabWidget):
            return False
        want = str(subtarget or "").strip().lower()
        aliases = {
            "events": "table",
            "events table": "table",
            "table": "table",
            "events timeline": "timeline",
            "timeline": "timeline",
            "event mismatch": "mismatch vs ref",
            "mismatch": "mismatch vs ref",
            "mismatch vs ref": "mismatch vs ref",
            "runs raster": "runs raster",
        }
        want_norm = aliases.get(want, want)
        for i in range(tabs.count()):
            try:
                tab_text = str(tabs.tabText(i) or "").strip()
            except Exception:
                tab_text = ""
            if aliases.get(tab_text.lower(), tab_text.lower()) == want_norm:
                try:
                    tabs.setCurrentIndex(i)
                except Exception:
                    return False
                return True
        return False

    def _on_events_dock_tab_changed(self, _index: int) -> None:
        try:
            self._update_workspace_status()
        except Exception:
            pass

    def _clear_events_timeline_view(self, note: str) -> None:
        self._events_timeline_cache = None
        try:
            if getattr(self, "scatter_events_timeline", None) is not None:
                self.scatter_events_timeline.setData([])
        except Exception:
            pass
        try:
            plot = getattr(self, "plot_events_timeline", None)
            if plot is not None:
                plot.clear()
                if getattr(self, "scatter_events_timeline", None) is not None:
                    plot.addItem(self.scatter_events_timeline)
                if getattr(self, "line_events_timeline", None) is not None:
                    plot.addItem(self.line_events_timeline)
                    self.line_events_timeline.hide()
                plot.setEnabled(False)
                plot.setTitle("")
                ax = plot.getAxis("left")
                if ax is not None:
                    ax.setTicks([])
        except Exception:
            pass
        try:
            self.lbl_events_timeline_note.setText(str(note or "Timeline: none"))
            self.lbl_events_timeline_readout.setText("")
        except Exception:
            pass

    def _event_timeline_color(self, row: int, total: int) -> object:
        try:
            return pg.intColor(int(row), hues=max(6, int(total)), values=1, maxValue=220, minValue=140)
        except Exception:
            return pg.mkBrush(60, 90, 180, 210)

    def _rebuild_events_timeline_view(
        self,
        baseline_label: str,
        df_events: pd.DataFrame,
        selected_signals: Sequence[str],
        *,
        no_signals_selected: bool,
    ) -> None:
        plot = getattr(self, "plot_events_timeline", None)
        scatter = getattr(self, "scatter_events_timeline", None)
        if plot is None or scatter is None:
            return

        if no_signals_selected:
            self._clear_events_timeline_view(
                "Timeline: no event signals selected. Check one or more event rows to turn the timeline into a visual gate."
            )
            return
        if not isinstance(df_events, pd.DataFrame) or df_events.empty:
            self._clear_events_timeline_view(
                "Timeline: no visible events in the current baseline / filter context."
            )
            return

        try:
            df_use = df_events.copy()
            df_use["signal"] = df_use["signal"].astype(str)
            df_use["table"] = df_use["table"].astype(str)
            df_use["t"] = pd.to_numeric(df_use["t"], errors="coerce")
            df_use = df_use[np.isfinite(df_use["t"].values)].copy()
        except Exception:
            df_use = pd.DataFrame()
        if df_use.empty:
            self._clear_events_timeline_view("Timeline: all visible rows have invalid event time.")
            return

        available_names = set(df_use["signal"].tolist())
        ordered_signals: List[str] = []
        for sig in selected_signals:
            sig_name = str(sig or "").strip()
            if sig_name and sig_name in available_names and sig_name not in ordered_signals:
                ordered_signals.append(sig_name)
        if not ordered_signals:
            try:
                ordered_signals = [str(x) for x in df_use["signal"].drop_duplicates().tolist()]
            except Exception:
                ordered_signals = []
        if not ordered_signals:
            self._clear_events_timeline_view("Timeline: no visible event rows after ordering.")
            return

        row_map = {str(sig): idx for idx, sig in enumerate(ordered_signals)}
        try:
            df_use["row_y"] = df_use["signal"].map(row_map)
            df_use = df_use[pd.notna(df_use["row_y"])].copy()
            df_use["row_y"] = df_use["row_y"].astype(int)
        except Exception:
            pass
        if df_use.empty:
            self._clear_events_timeline_view("Timeline: current events do not map to visible signal rows.")
            return

        df_use.sort_values(["row_y", "t", "signal"], inplace=True, kind="mergesort")
        df_use.reset_index(drop=True, inplace=True)

        spots = []
        records: List[Dict[str, object]] = []
        total_rows = max(1, len(ordered_signals))
        for row in df_use.itertuples(index=False):
            try:
                t = float(getattr(row, "t", np.nan))
            except Exception:
                t = np.nan
            signal_name = str(getattr(row, "signal", "") or "")
            table_name = str(getattr(row, "table", "") or "")
            try:
                row_y = int(getattr(row, "row_y", -1))
            except Exception:
                row_y = -1
            if not np.isfinite(t) or row_y < 0:
                continue
            payload = {
                "baseline": str(baseline_label or ""),
                "time_s": float(t),
                "signal": signal_name,
                "from": getattr(row, "from", ""),
                "to": getattr(row, "to", ""),
                "table": table_name,
                "row_y": int(row_y),
            }
            records.append(payload)
            spots.append(
                {
                    "pos": (float(t), float(row_y)),
                    "data": payload,
                    "size": 9,
                    "symbol": "o",
                    "brush": self._event_timeline_color(row_y, total_rows),
                    "pen": pg.mkPen(40, 40, 40, 200),
                }
            )

        if not records:
            self._clear_events_timeline_view("Timeline: no finite event points available for plotting.")
            return

        try:
            scatter.setData(spots)
        except Exception:
            self._clear_events_timeline_view("Timeline: failed to populate event scatter.")
            return
        try:
            ax = plot.getAxis("left")
            if ax is not None:
                ax.setTicks([[(float(i), str(sig)) for i, sig in enumerate(ordered_signals)]])
        except Exception:
            pass
        try:
            plot.setTitle(f"Baseline {baseline_label or '—'} | {len(records)} visible event(s)")
            plot.setEnabled(True)
            plot.setYRange(-0.5, float(len(ordered_signals) - 0.5), padding=0.02)
            t_min = float(df_use["t"].min())
            t_max = float(df_use["t"].max())
            if np.isfinite(t_min) and np.isfinite(t_max):
                if t_max <= t_min:
                    span = max(0.1, abs(t_min) * 0.1, 1.0)
                    plot.setXRange(t_min - span, t_max + span, padding=0.02)
                else:
                    plot.setXRange(t_min, t_max, padding=0.03)
            if getattr(self, "line_events_timeline", None) is not None:
                self.line_events_timeline.show()
        except Exception:
            pass

        self._events_timeline_cache = {
            "baseline": str(baseline_label or ""),
            "signals": list(ordered_signals),
            "records": list(records),
            "times": np.asarray([float(rec.get("time_s", np.nan)) for rec in records], dtype=float),
            "rows": np.asarray([int(rec.get("row_y", -1)) for rec in records], dtype=float),
        }
        try:
            self.lbl_events_timeline_note.setText(
                f"Timeline: {len(records)} visible event(s) across {len(ordered_signals)} signal row(s). "
                "Click a point to focus the baseline signal and jump playhead."
            )
            self.lbl_events_timeline_readout.setText("")
        except Exception:
            pass
        try:
            if hasattr(self, "_t_ref") and np.asarray(getattr(self, "_t_ref", np.asarray([])), dtype=float).size > 0:
                idx = int(self.slider_time.value()) if hasattr(self, "slider_time") else 0
                idx = max(0, min(idx, int(len(self._t_ref) - 1)))
                self._sync_events_timeline_to_time(float(self._t_ref[idx]))
        except Exception:
            pass

    def _sync_events_timeline_to_time(self, t: float) -> None:
        cache = dict(getattr(self, "_events_timeline_cache", {}) or {})
        tt = np.asarray(cache.get("times", np.asarray([])), dtype=float)
        if tt.size <= 0:
            return
        try:
            idx = int(np.argmin(np.abs(tt - float(t))))
        except Exception:
            return
        idx = max(0, min(idx, int(tt.size - 1)))
        x = float(tt[idx])
        try:
            if getattr(self, "line_events_timeline", None) is not None:
                self.line_events_timeline.setPos(x)
        except Exception:
            pass
        try:
            records = list(cache.get("records") or [])
            if 0 <= idx < len(records):
                rec = dict(records[idx] or {})
                self.lbl_events_timeline_readout.setText(
                    f"baseline={str(cache.get('baseline') or '—')} | near={str(rec.get('signal') or '—')} | "
                    f"event t={float(rec.get('time_s', float('nan'))):.3f}s | playhead={float(t):.3f}s"
                )
        except Exception:
            pass

    def _events_timeline_sample(self, scene_pos) -> Dict[str, object]:
        cache = dict(getattr(self, "_events_timeline_cache", {}) or {})
        plot = getattr(self, "plot_events_timeline", None)
        if plot is None or not cache:
            return {}
        tt = np.asarray(cache.get("times", np.asarray([])), dtype=float)
        yy = np.asarray(cache.get("rows", np.asarray([])), dtype=float)
        records = list(cache.get("records") or [])
        if tt.size <= 0 or yy.size <= 0 or not records:
            return {}
        try:
            mp = plot.getViewBox().mapSceneToView(scene_pos)
            x = float(mp.x())
            y = float(mp.y())
        except Exception:
            return {}
        if not np.isfinite(x) or not np.isfinite(y):
            return {}
        try:
            xr = plot.getViewBox().viewRange()[0]
            x_tol = max(0.05, 0.03 * abs(float(xr[1]) - float(xr[0])))
        except Exception:
            x_tol = 0.2
        cand = np.flatnonzero(np.abs(yy - y) <= 0.45)
        if cand.size <= 0:
            return {}
        dx = np.abs(tt[cand] - x)
        best_local = int(np.argmin(dx))
        if not np.isfinite(dx[best_local]) or float(dx[best_local]) > float(x_tol):
            return {}
        idx = int(cand[best_local])
        if idx < 0 or idx >= len(records):
            return {}
        return dict(records[idx] or {})

    def _on_events_timeline_mouse_moved(self, evt) -> None:
        pos = evt[0] if isinstance(evt, tuple) else evt
        sample = self._events_timeline_sample(pos)
        if not sample:
            return
        try:
            self.lbl_events_timeline_readout.setText(
                f"baseline={str(sample.get('baseline') or '—')} | signal={str(sample.get('signal') or '—')} | "
                f"t={float(sample.get('time_s', float('nan'))):.3f}s | "
                f"{sample.get('from')}→{sample.get('to')} | table={str(sample.get('table') or '—')}"
            )
        except Exception:
            pass

    def _on_events_timeline_points_clicked(self, _item, points, *_args) -> None:
        if points is None:
            return
        try:
            if len(points) <= 0:
                return
        except Exception:
            return
        try:
            data = points[0].data()
            if isinstance(data, np.ndarray):
                data = data.tolist()
            if isinstance(data, (list, tuple)):
                data = data[0] if data else {}
            payload = dict(data or {})
        except Exception:
            return
        baseline = str(payload.get("baseline") or "").strip()
        signal_name = str(payload.get("signal") or "").strip()
        try:
            t = float(payload.get("time_s", np.nan))
        except Exception:
            t = float("nan")
        if not baseline or not signal_name or not np.isfinite(t):
            return
        try:
            focused = bool(self._focus_run_signal(baseline, signal_name))
        except Exception:
            focused = False
        if not focused:
            return
        try:
            self._set_playhead_time(float(t))
        except Exception:
            pass

    def _clear_events_compare_view(self, note: str) -> None:
        tbl = getattr(self, "tbl_events_compare", None)
        if tbl is not None:
            try:
                tbl.clear()
                tbl.setRowCount(0)
                tbl.setColumnCount(0)
                tbl.setEnabled(False)
            except Exception:
                pass
        try:
            self.lbl_events_compare.setText(str(note or "Mismatch vs ref: none"))
        except Exception:
            pass

    def _events_compare_color(
        self,
        *,
        count_delta: int,
        first_lag_s: float,
        is_ref: bool,
        has_ref: bool,
        has_run: bool,
    ) -> QtGui.QColor:
        if is_ref:
            return QtGui.QColor(232, 232, 232)
        if not has_ref and not has_run:
            return QtGui.QColor(242, 242, 242)
        if has_ref and not has_run:
            return QtGui.QColor(242, 199, 199)
        if has_run and not has_ref:
            return QtGui.QColor(250, 220, 180)
        abs_delta = abs(int(count_delta))
        lag_abs = abs(float(first_lag_s)) if np.isfinite(first_lag_s) else float("nan")
        if abs_delta == 0 and np.isfinite(lag_abs) and lag_abs <= 1e-6:
            return QtGui.QColor(205, 238, 210)
        if abs_delta >= 2 or (np.isfinite(lag_abs) and lag_abs >= 0.5):
            return QtGui.QColor(244, 191, 191)
        if abs_delta >= 1 or (np.isfinite(lag_abs) and lag_abs >= 0.05):
            return QtGui.QColor(250, 227, 182)
        return QtGui.QColor(221, 239, 222)

    def _rebuild_events_compare_view(
        self,
        baseline_label: str,
        baseline_events: pd.DataFrame,
        selected_signals: Sequence[str],
        *,
        no_signals_selected: bool,
    ) -> None:
        tbl = getattr(self, "tbl_events_compare", None)
        if tbl is None:
            return
        runs = list(self._selected_runs())
        if no_signals_selected:
            self._clear_events_compare_view(
                "Mismatch vs ref: no event signals selected. Check one or more event signals to compare runs."
            )
            return
        ref_run = self._reference_run(runs)
        if ref_run is None or not isinstance(baseline_events, pd.DataFrame) or baseline_events.empty:
            self._clear_events_compare_view(
                "Mismatch vs ref: no baseline events available for the current reference run."
            )
            return

        run_list = list(runs)
        if all(str(getattr(run, "label", "") or "").strip() != str(baseline_label or "").strip() for run in run_list):
            run_list.insert(0, ref_run)
        if len(run_list) < 2:
            self._clear_events_compare_view(
                "Mismatch vs ref: select at least two runs to compare event drift against the reference."
            )
            return

        try:
            ref_df = baseline_events.copy()
            ref_df["signal"] = ref_df["signal"].astype(str)
            ref_df["t"] = pd.to_numeric(ref_df["t"], errors="coerce")
            ref_df = ref_df[np.isfinite(ref_df["t"].values)].copy()
        except Exception:
            ref_df = pd.DataFrame()
        if ref_df.empty:
            self._clear_events_compare_view(
                "Mismatch vs ref: baseline events exist, but no finite event timestamps are available."
            )
            return

        ref_counts = ref_df["signal"].astype(str).value_counts()
        ref_available = set(ref_counts.index.tolist())
        row_labels: List[str] = []
        for sig in selected_signals:
            sig_name = str(sig or "").strip()
            if sig_name and sig_name in ref_available and sig_name not in row_labels:
                row_labels.append(sig_name)
        if not row_labels:
            row_labels = [str(x) for x in ref_counts.index.tolist()]
        if not row_labels:
            self._clear_events_compare_view("Mismatch vs ref: no visible baseline event signals remain after filtering.")
            return

        tbl.clear()
        tbl.setRowCount(int(len(row_labels)))
        tbl.setColumnCount(int(len(run_list)))
        tbl.setVerticalHeaderLabels([str(x) for x in row_labels])
        tbl.setHorizontalHeaderLabels([str(getattr(run, "label", "") or "") for run in run_list])

        mismatch_cells = 0
        for c, run in enumerate(run_list):
            run_label = str(getattr(run, "label", "") or "").strip()
            is_ref = bool(ref_run is not None and run is ref_run) or (run_label == str(baseline_label or "").strip())
            try:
                run_df = getattr(run, "events", None)
                if isinstance(run_df, pd.DataFrame) and not run_df.empty:
                    run_df = run_df.copy()
                    run_df["signal"] = run_df["signal"].astype(str)
                    run_df["t"] = pd.to_numeric(run_df["t"], errors="coerce")
                    run_df = run_df[np.isfinite(run_df["t"].values)].copy()
                    run_df = run_df[run_df["signal"].isin(row_labels)].copy()
                else:
                    run_df = pd.DataFrame()
            except Exception:
                run_df = pd.DataFrame()

            run_groups = {}
            if isinstance(run_df, pd.DataFrame) and not run_df.empty:
                try:
                    run_groups = {str(sig): grp.copy() for sig, grp in run_df.groupby("signal", sort=False)}
                except Exception:
                    run_groups = {}

            for r, sig_name in enumerate(row_labels):
                ref_sig = ref_df[ref_df["signal"].astype(str) == str(sig_name)].copy()
                run_sig = run_groups.get(str(sig_name), pd.DataFrame())
                ref_count = int(len(ref_sig)) if isinstance(ref_sig, pd.DataFrame) else 0
                run_count = int(len(run_sig)) if isinstance(run_sig, pd.DataFrame) else 0
                try:
                    ref_first = float(ref_sig["t"].min()) if ref_count > 0 else float("nan")
                except Exception:
                    ref_first = float("nan")
                try:
                    run_first = float(run_sig["t"].min()) if run_count > 0 else float("nan")
                except Exception:
                    run_first = float("nan")
                count_delta = int(run_count - ref_count)
                first_lag_s = float(run_first - ref_first) if np.isfinite(run_first) and np.isfinite(ref_first) else float("nan")
                has_ref = bool(ref_count > 0)
                has_run = bool(run_count > 0)

                if is_ref:
                    text = "ref"
                elif not has_ref and not has_run:
                    text = "—"
                elif has_ref and not has_run:
                    text = "miss"
                elif has_run and not has_ref:
                    text = "extra"
                else:
                    pieces: List[str] = []
                    if count_delta != 0:
                        pieces.append(f"{count_delta:+d}")
                    if np.isfinite(first_lag_s) and abs(first_lag_s) > 1e-6:
                        pieces.append(f"{first_lag_s:+.2f}s")
                    text = "ok" if not pieces else " | ".join(pieces)

                item = QtWidgets.QTableWidgetItem(text)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setBackground(
                    self._events_compare_color(
                        count_delta=count_delta,
                        first_lag_s=first_lag_s,
                        is_ref=is_ref,
                        has_ref=has_ref,
                        has_run=has_run,
                    )
                )
                tooltip = (
                    f"signal: {sig_name}\nrun: {run_label}\nref: {baseline_label or '—'}\n"
                    f"ref events: {ref_count}\nrun events: {run_count}"
                )
                if np.isfinite(ref_first):
                    tooltip = f"{tooltip}\nref first: {ref_first:.6f} s"
                if np.isfinite(run_first):
                    tooltip = f"{tooltip}\nrun first: {run_first:.6f} s"
                if np.isfinite(first_lag_s):
                    tooltip = f"{tooltip}\nfirst-event lag: {first_lag_s:+.6f} s"
                item.setToolTip(tooltip)
                item.setData(
                    QtCore.Qt.UserRole,
                    {
                        "run": run_label,
                        "signal": sig_name,
                        "time_s": run_first if np.isfinite(run_first) else ref_first,
                        "is_ref": bool(is_ref),
                        "count_delta": int(count_delta),
                        "first_lag_s": first_lag_s,
                    },
                )
                if (not is_ref) and ((count_delta != 0) or (np.isfinite(first_lag_s) and abs(first_lag_s) > 1e-6)):
                    mismatch_cells += 1
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                tbl.setItem(r, c, item)

        try:
            hdr = tbl.horizontalHeader()
            for c in range(tbl.columnCount()):
                hdr.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
            tbl.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            tbl.setEnabled(True)
        except Exception:
            pass
        try:
            self.lbl_events_compare.setText(
                f"Mismatch vs ref: {len(row_labels)} signal row(s) across {len(run_list)} run(s). "
                f"Highlighted drift cells: {int(mismatch_cells)}. Click a cell to focus run / signal and jump to the first local event."
            )
        except Exception:
            pass

    def _on_events_compare_cell_clicked(self, row: int, col: int) -> None:
        tbl = getattr(self, "tbl_events_compare", None)
        if tbl is None:
            return
        try:
            item = tbl.item(int(row), int(col))
        except Exception:
            item = None
        if item is None:
            return
        try:
            payload = dict(item.data(QtCore.Qt.UserRole) or {})
        except Exception:
            payload = {}
        run_label = str(payload.get("run") or "").strip()
        sig = str(payload.get("signal") or "").strip()
        try:
            t = float(payload.get("time_s", np.nan))
        except Exception:
            t = float("nan")
        if not run_label or not sig:
            return
        try:
            focused = bool(self._focus_run_signal(run_label, sig))
        except Exception:
            focused = False
        if (not focused) and run_label:
            try:
                focused = bool(self._focus_run_label_preserving_context(run_label))
            except Exception:
                focused = False
        if focused and np.isfinite(t):
            try:
                self._set_playhead_time(float(t))
            except Exception:
                pass

    def _clear_events_runs_view(self, note: str) -> None:
        self._events_runs_cache = None
        try:
            if getattr(self, "scatter_events_runs", None) is not None:
                self.scatter_events_runs.setData([])
        except Exception:
            pass
        try:
            plot = getattr(self, "plot_events_runs", None)
            if plot is not None:
                plot.clear()
                if getattr(self, "scatter_events_runs", None) is not None:
                    plot.addItem(self.scatter_events_runs)
                if getattr(self, "line_events_runs", None) is not None:
                    plot.addItem(self.line_events_runs)
                    self.line_events_runs.hide()
                plot.setEnabled(False)
                plot.setTitle("")
                ax = plot.getAxis("left")
                if ax is not None:
                    ax.setTicks([])
        except Exception:
            pass
        try:
            self.lbl_events_runs_note.setText(str(note or "Runs raster: none"))
            self.lbl_events_runs_readout.setText("")
        except Exception:
            pass

    def _rebuild_events_runs_view(
        self,
        selected_signals: Sequence[str],
        *,
        no_signals_selected: bool,
    ) -> None:
        plot = getattr(self, "plot_events_runs", None)
        scatter = getattr(self, "scatter_events_runs", None)
        if plot is None or scatter is None:
            return
        runs = list(self._selected_runs())
        if not runs:
            self._clear_events_runs_view("Runs raster: select one or more runs to compare event timing.")
            return
        if no_signals_selected:
            self._clear_events_runs_view(
                "Runs raster: no event signals selected. Check one or more event signals to compare timing across runs."
            )
            return

        run_labels = [str(getattr(run, "label", "") or "").strip() for run in runs]
        ref_label = str(self._reference_run_label(runs) or "").strip()
        run_rows = {lab: idx for idx, lab in enumerate(run_labels)}

        signal_order: List[str] = []
        seen_signals = set()
        visible_by_run: Dict[str, pd.DataFrame] = {}
        for run in runs:
            run_label = str(getattr(run, "label", "") or "").strip()
            df_run = getattr(run, "events", None)
            if not isinstance(df_run, pd.DataFrame) or df_run.empty:
                visible_by_run[run_label] = pd.DataFrame()
                continue
            try:
                df_use = df_run.copy()
                df_use["signal"] = df_use["signal"].astype(str)
                df_use["table"] = df_use["table"].astype(str)
                df_use["t"] = pd.to_numeric(df_use["t"], errors="coerce")
                df_use = df_use[np.isfinite(df_use["t"].values)].copy()
            except Exception:
                df_use = pd.DataFrame()
            if df_use.empty:
                visible_by_run[run_label] = pd.DataFrame()
                continue
            try:
                df_use = df_use[df_use["signal"].isin([str(x) for x in selected_signals])].copy()
            except Exception:
                pass
            visible_by_run[run_label] = df_use
            try:
                for sig_name in df_use["signal"].drop_duplicates().tolist():
                    sig_text = str(sig_name or "").strip()
                    if sig_text and sig_text not in seen_signals:
                        seen_signals.add(sig_text)
                        signal_order.append(sig_text)
            except Exception:
                pass

        if not signal_order:
            self._clear_events_runs_view("Runs raster: no visible events remain for the current run / signal context.")
            return

        offsets = {signal_order[0]: 0.0} if len(signal_order) == 1 else {
            sig: float(off) for sig, off in zip(signal_order, np.linspace(-0.28, 0.28, len(signal_order)))
        }
        color_map = {sig: self._event_timeline_color(idx, len(signal_order)) for idx, sig in enumerate(signal_order)}

        spots = []
        records: List[Dict[str, object]] = []
        for run_label in run_labels:
            df_use = visible_by_run.get(run_label)
            if not isinstance(df_use, pd.DataFrame) or df_use.empty:
                continue
            base_y = float(run_rows.get(run_label, 0))
            for row in df_use.itertuples(index=False):
                try:
                    t = float(getattr(row, "t", np.nan))
                except Exception:
                    t = np.nan
                sig_name = str(getattr(row, "signal", "") or "")
                if not np.isfinite(t) or sig_name not in offsets:
                    continue
                payload = {
                    "run": run_label,
                    "signal": sig_name,
                    "time_s": float(t),
                    "from": getattr(row, "from", ""),
                    "to": getattr(row, "to", ""),
                    "table": str(getattr(row, "table", "") or ""),
                    "y": float(base_y + offsets.get(sig_name, 0.0)),
                }
                records.append(payload)
                is_ref = bool(ref_label and run_label == ref_label)
                spots.append(
                    {
                        "pos": (float(t), float(payload["y"])),
                        "data": payload,
                        "size": 11 if is_ref else 8,
                        "symbol": "o",
                        "brush": color_map.get(sig_name, pg.mkBrush(60, 90, 180, 210)),
                        "pen": pg.mkPen(45, 45, 45, 220) if not is_ref else pg.mkPen(170, 110, 25, 230, width=2),
                    }
                )

        if not records:
            self._clear_events_runs_view("Runs raster: no finite event points are available across the selected runs.")
            return

        try:
            scatter.setData(spots)
        except Exception:
            self._clear_events_runs_view("Runs raster: failed to populate cross-run event scatter.")
            return

        try:
            ax = plot.getAxis("left")
            if ax is not None:
                ax.setTicks([[(float(i), str(label)) for i, label in enumerate(run_labels)]])
        except Exception:
            pass
        try:
            plot.setEnabled(True)
            plot.setTitle(
                f"Runs raster | {len(records)} visible event(s) across {len(run_labels)} run(s) and {len(signal_order)} signal(s)"
            )
            plot.setYRange(-0.5, float(len(run_labels) - 0.5), padding=0.02)
            times = np.asarray([float(rec.get("time_s", np.nan)) for rec in records], dtype=float)
            t_min = float(np.nanmin(times))
            t_max = float(np.nanmax(times))
            if np.isfinite(t_min) and np.isfinite(t_max):
                if t_max <= t_min:
                    span = max(0.1, abs(t_min) * 0.1, 1.0)
                    plot.setXRange(t_min - span, t_max + span, padding=0.02)
                else:
                    plot.setXRange(t_min, t_max, padding=0.03)
            if getattr(self, "line_events_runs", None) is not None:
                self.line_events_runs.show()
        except Exception:
            pass

        self._events_runs_cache = {
            "run_labels": list(run_labels),
            "signal_order": list(signal_order),
            "ref_label": ref_label,
            "records": list(records),
            "times": np.asarray([float(rec.get("time_s", np.nan)) for rec in records], dtype=float),
            "ys": np.asarray([float(rec.get("y", np.nan)) for rec in records], dtype=float),
        }
        try:
            self.lbl_events_runs_note.setText(
                f"Runs raster: compare {len(signal_order)} visible event signal(s) across {len(run_labels)} selected run(s). "
                "Colors identify event signals; click a point to jump into that run / signal."
            )
            self.lbl_events_runs_readout.setText("")
        except Exception:
            pass
        try:
            if hasattr(self, "_t_ref") and np.asarray(getattr(self, "_t_ref", np.asarray([])), dtype=float).size > 0:
                idx = int(self.slider_time.value()) if hasattr(self, "slider_time") else 0
                idx = max(0, min(idx, int(len(self._t_ref) - 1)))
                self._sync_events_runs_to_time(float(self._t_ref[idx]))
        except Exception:
            pass

    def _sync_events_runs_to_time(self, t: float) -> None:
        cache = dict(getattr(self, "_events_runs_cache", {}) or {})
        tt = np.asarray(cache.get("times", np.asarray([])), dtype=float)
        if tt.size <= 0:
            return
        try:
            idx = int(np.argmin(np.abs(tt - float(t))))
        except Exception:
            return
        idx = max(0, min(idx, int(tt.size - 1)))
        try:
            if getattr(self, "line_events_runs", None) is not None:
                self.line_events_runs.setPos(float(t))
        except Exception:
            pass
        try:
            records = list(cache.get("records") or [])
            if 0 <= idx < len(records):
                rec = dict(records[idx] or {})
                self.lbl_events_runs_readout.setText(
                    f"ref={str(cache.get('ref_label') or '—')} | near={str(rec.get('run') or '—')} / {str(rec.get('signal') or '—')} | "
                    f"event t={float(rec.get('time_s', float('nan'))):.3f}s | playhead={float(t):.3f}s"
                )
        except Exception:
            pass

    def _events_runs_sample(self, scene_pos) -> Dict[str, object]:
        cache = dict(getattr(self, "_events_runs_cache", {}) or {})
        plot = getattr(self, "plot_events_runs", None)
        if plot is None or not cache:
            return {}
        tt = np.asarray(cache.get("times", np.asarray([])), dtype=float)
        yy = np.asarray(cache.get("ys", np.asarray([])), dtype=float)
        records = list(cache.get("records") or [])
        if tt.size <= 0 or yy.size <= 0 or not records:
            return {}
        try:
            mp = plot.getViewBox().mapSceneToView(scene_pos)
            x = float(mp.x())
            y = float(mp.y())
        except Exception:
            return {}
        if not np.isfinite(x) or not np.isfinite(y):
            return {}
        try:
            xr = plot.getViewBox().viewRange()[0]
            x_tol = max(0.05, 0.03 * abs(float(xr[1]) - float(xr[0])))
        except Exception:
            x_tol = 0.2
        cand = np.flatnonzero(np.abs(yy - y) <= 0.35)
        if cand.size <= 0:
            return {}
        dx = np.abs(tt[cand] - x)
        best_local = int(np.argmin(dx))
        if not np.isfinite(dx[best_local]) or float(dx[best_local]) > float(x_tol):
            return {}
        idx = int(cand[best_local])
        if idx < 0 or idx >= len(records):
            return {}
        return dict(records[idx] or {})

    def _on_events_runs_mouse_moved(self, evt) -> None:
        pos = evt[0] if isinstance(evt, tuple) else evt
        sample = self._events_runs_sample(pos)
        if not sample:
            return
        try:
            self.lbl_events_runs_readout.setText(
                f"run={str(sample.get('run') or '—')} | signal={str(sample.get('signal') or '—')} | "
                f"t={float(sample.get('time_s', float('nan'))):.3f}s | "
                f"{sample.get('from')}→{sample.get('to')} | table={str(sample.get('table') or '—')}"
            )
        except Exception:
            pass

    def _on_events_runs_points_clicked(self, _item, points, *_args) -> None:
        if points is None:
            return
        try:
            if len(points) <= 0:
                return
        except Exception:
            return
        try:
            data = points[0].data()
            if isinstance(data, np.ndarray):
                data = data.tolist()
            if isinstance(data, (list, tuple)):
                data = data[0] if data else {}
            payload = dict(data or {})
        except Exception:
            return
        run_label = str(payload.get("run") or "").strip()
        sig = str(payload.get("signal") or "").strip()
        try:
            t = float(payload.get("time_s", np.nan))
        except Exception:
            t = float("nan")
        if not run_label or not sig:
            return
        try:
            focused = bool(self._focus_run_signal(run_label, sig))
        except Exception:
            focused = False
        if focused and np.isfinite(t):
            try:
                self._set_playhead_time(float(t))
            except Exception:
                pass


    def _qa_sensitivity_code(self) -> str:
        try:
            return str(self.combo_qa_sens.currentData() or "normal")
        except Exception:
            return "normal"


    def _rebuild_qa(self, *_args, force: bool = False) -> None:
        if getattr(self, 'dock_qa', None) is None:
            return
        if qa_scan_run_tables is None or qa_issues_to_frame is None or qa_severity_matrix is None:
            self._clear_qa_view("QA: модуль недоступен")
            return

        try:
            enabled = bool(self.chk_qa_enable.isChecked())
        except Exception:
            enabled = True
        if not enabled:
            self._clear_qa_view("QA: выключено")
            return

        # inputs
        table = str(self.combo_table.currentText()) if hasattr(self, 'combo_table') else ""
        runs = self._selected_runs()
        if not runs:
            self._clear_qa_view("QA: выберите хотя бы один прогон")
            return

        qa_all = bool(getattr(self, 'chk_qa_all', None) and self.chk_qa_all.isChecked())
        if qa_all:
            sigs = self._current_context_signal_names(apply_filter=False)
        else:
            sigs = [it.text() for it in self.list_signals.selectedItems()]
        # Remove obvious time columns
        sigs = [s for s in sigs if str(s).strip().lower() not in ("t", "time", "timestamp")]
        if not sigs:
            if bool(getattr(self, '_signals_selection_explicit', False)):
                self._clear_qa_view("QA: выберите хотя бы один сигнал")
                return
            if qa_all:
                sigs = self._current_context_signal_names(apply_filter=False)[:8]
            else:
                sigs = [self.list_signals.item(i).text() for i in range(min(8, self.list_signals.count()))]

        sens = self._qa_sensitivity_code()
        key = (tuple([r.label for r in runs]), table, tuple(sigs[:60]), sens)
        if (not force) and key == self._qa_cache_key:
            return
        self._qa_cache_key = key

        # scan
        issues = []
        for r in runs:
            try:
                issues.extend(
                    qa_scan_run_tables(
                        r.tables,
                        run_label=str(r.label),
                        table=str(table),
                        signals=list(sigs)[:60],
                        sensitivity=str(sens),
                    )
                )
            except Exception:
                pass

        df = qa_issues_to_frame(issues)
        self._qa_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        summ = qa_summarize(df) if qa_summarize is not None else {"n": int(len(df))}
        n = int(summ.get('n', 0) or 0)
        n_err = int(summ.get('n_err', 0) or 0)
        n_warn = int(summ.get('n_warn', 0) or 0)

        self._insight_qa = {"issues": int(n), "err": int(n_err), "warn": int(n_warn)}

        run_labels = [r.label for r in runs]
        sig_labels = list(sigs)[:60]
        Z, first_t = qa_severity_matrix(df, run_labels=run_labels, signals=sig_labels)
        self._qa_mat = Z
        self._qa_run_labels = list(run_labels)
        self._qa_sig_labels = list(sig_labels)
        self._qa_first_t = first_t or {}
        try:
            if np.asarray(Z, dtype=float).size and np.isfinite(Z).any():
                A = np.nan_to_num(np.asarray(Z, dtype=float), nan=0.0)
                k_top = int(np.argmax(A))
                isig_top, irun_top = np.unravel_index(k_top, A.shape)
                top_run = self._qa_run_labels[irun_top] if 0 <= irun_top < len(self._qa_run_labels) else ""
                top_sig = self._qa_sig_labels[isig_top] if 0 <= isig_top < len(self._qa_sig_labels) else ""
                self._insight_qa.update(
                    {
                        "top_run": top_run,
                        "top_signal": top_sig,
                        "top_severity": float(A[isig_top, irun_top]),
                        "top_time_s": float(self._qa_first_t.get((str(top_run), str(top_sig)), np.nan)),
                    }
                )
        except Exception:
            pass

        try:
            self.lbl_qa_summary.setText(
                self._qa_status_text(
                    table=table,
                    runs_count=len(runs),
                    sigs_count=len(sigs),
                    sensitivity=sens,
                    issues_count=n,
                    err_count=n_err,
                    warn_count=n_warn,
                    top_run=str(self._insight_qa.get("top_run") or ""),
                    top_sig=str(self._insight_qa.get("top_signal") or ""),
                    top_time_s=float(self._insight_qa.get("top_time_s", np.nan)),
                    top_severity=float(self._insight_qa.get("top_severity", np.nan)),
                )
            )
        except Exception:
            pass
        self._update_workspace_status()

        # cell codes summary
        cell_codes = {}
        try:
            if not df.empty:
                g = df.groupby(['run_label', 'signal'])['code'].apply(lambda s: ",".join(sorted(set([str(x) for x in s if pd.notna(x)]))))
                for (rk, sk), v in g.items():
                    cell_codes[(str(rk), str(sk))] = str(v)
        except Exception:
            pass
        self._qa_cell_codes = cell_codes

        # build RGBA image
        h, w = int(Z.shape[0]), int(Z.shape[1])
        img = np.zeros((max(1, h), max(1, w), 4), dtype=np.ubyte)
        # 0 -> transparent
        img[:, :, 3] = 0
        # severity colors
        def paint(level: int, rgba: Tuple[int, int, int, int]):
            m = (Z == float(level))
            if m.any():
                img[m, 0] = rgba[0]
                img[m, 1] = rgba[1]
                img[m, 2] = rgba[2]
                img[m, 3] = rgba[3]

        paint(1, (255, 243, 205, 210))
        paint(2, (255, 216, 168, 230))
        paint(3, (250, 82, 82, 235))

        try:
            self.qa_img.setImage(img, autoLevels=False)
            self.qa_plot.setXRange(0, max(1, w), padding=0.02)
            self.qa_plot.setYRange(0, max(1, h), padding=0.02)
            self.qa_plot.setEnabled(True)
        except Exception:
            pass

        # fill table
        try:
            self._sync_qa_code_filters(df)
            self._refresh_qa_table_view()
        except Exception:
            pass

    def _clear_qa_view(self, summary: str = "QA: —") -> None:
        self._qa_cache_key = None
        self._qa_mat = None
        self._qa_run_labels = []
        self._qa_sig_labels = []
        self._qa_first_t = {}
        self._qa_cell_codes = {}
        self._insight_qa = {}
        self._qa_df = pd.DataFrame()
        self._qa_checked_codes_selected = []
        self._qa_code_filter_initialized = False
        try:
            self.lbl_qa_summary.setText(str(summary or "QA: —"))
        except Exception:
            pass
        try:
            self.lbl_qa_readout.setText("")
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_qa_table_filters"):
                self.lbl_qa_table_filters.setText("")
        except Exception:
            pass
        try:
            if hasattr(self, "list_qa_codes"):
                prev = self.list_qa_codes.blockSignals(True)
                self.list_qa_codes.clear()
                self.list_qa_codes.setEnabled(False)
                self.list_qa_codes.blockSignals(prev)
        except Exception:
            pass
        try:
            self.tbl_qa.setRowCount(0)
            self.tbl_qa.setEnabled(False)
        except Exception:
            pass
        try:
            self.qa_img.setImage(np.zeros((1, 1, 4), dtype=np.ubyte), autoLevels=False)
            self.qa_plot.setEnabled(False)
        except Exception:
            pass
        self._update_workspace_status()


    def _qa_pos_to_rc(self, pos: QtCore.QPointF) -> Optional[Tuple[int, int]]:
        if self._qa_mat is None:
            return None
        try:
            mp = self.qa_plot.plotItem.vb.mapSceneToView(pos)
            x = float(mp.x())
            y = float(mp.y())
            r = int(np.clip(np.floor(y), 0, self._qa_mat.shape[0] - 1))
            c = int(np.clip(np.floor(x), 0, self._qa_mat.shape[1] - 1))
            return r, c
        except Exception:
            return None


    def _on_qa_mouse_move(self, pos):
        rc = self._qa_pos_to_rc(pos)
        if rc is None:
            return
        r, c = rc
        try:
            sig = self._qa_sig_labels[r] if r < len(self._qa_sig_labels) else str(r)
            run = self._qa_run_labels[c] if c < len(self._qa_run_labels) else str(c)
            sev = float(self._qa_mat[r, c]) if self._qa_mat is not None else 0
            codes = self._qa_cell_codes.get((str(run), str(sig)), "")
            self.lbl_qa_readout.setText(f"run={run} | signal={sig} | severity={sev:g} | {codes}")
        except Exception:
            pass


    def _on_qa_mouse_click(self, ev):
        try:
            if ev.button() != QtCore.Qt.LeftButton:
                return
        except Exception:
            return
        pos = None
        try:
            pos = ev.scenePos()
        except Exception:
            return
        rc = self._qa_pos_to_rc(pos)
        if rc is None:
            return
        r, c = rc
        if self._qa_mat is None:
            return
        if float(self._qa_mat[r, c]) <= 0:
            return
        try:
            sig = self._qa_sig_labels[r]
            run = self._qa_run_labels[c]
        except Exception:
            return

        # Select run + signal
        focused = False
        try:
            focused = bool(self._focus_run_signal(str(run), str(sig)))
        except Exception:
            focused = False

        # Move playhead to first issue time if available
        if focused:
            t0 = self._qa_first_t.get((str(run), str(sig)))
            if t0 is not None and isinstance(t0, (int, float)) and np.isfinite(float(t0)):
                try:
                    self._set_playhead_time(float(t0))
                except Exception:
                    pass

        if focused:
            self._rebuild_plots()


    def _on_qa_table_double_clicked(self, row: int, _col: int):
        try:
            run = self.tbl_qa.item(row, 1).text()
            sig = self.tbl_qa.item(row, 2).text()
            t0_txt = self.tbl_qa.item(row, 4).text()
        except Exception:
            return
        focused = False
        try:
            focused = bool(self._focus_run_signal(str(run), str(sig)))
        except Exception:
            focused = False
        if focused:
            try:
                t0 = float(t0_txt)
                if np.isfinite(t0):
                    self._set_playhead_time(t0)
            except Exception:
                pass
            self._rebuild_plots()


    def _select_run_by_label(self, label: str) -> bool:
        if not hasattr(self, 'list_runs'):
            return False
        target_row = None
        for i in range(self.list_runs.count()):
            it = self.list_runs.item(i)
            if it is not None and str(it.text()) == str(label):
                target_row = i
                break
        if target_row is None:
            return False
        try:
            self.list_runs.blockSignals(True)
            for i in range(self.list_runs.count()):
                it = self.list_runs.item(i)
                is_target = (i == target_row)
                it.setSelected(is_target)
            self._set_current_list_row(self.list_runs, int(target_row))
            self._runs_selection_explicit = True
            picked_paths: List[str] = []
            for i in range(self.list_runs.count()):
                it = self.list_runs.item(i)
                if it is None or not it.isSelected():
                    continue
                key = it.data(QtCore.Qt.UserRole)
                key = str(key).strip() if key is not None else ""
                if key:
                    picked_paths.append(key)
            self.runs_selected_paths = list(picked_paths)
        finally:
            self.list_runs.blockSignals(False)
        return True

    def _current_context_signal_names(self, apply_filter: bool = True) -> List[str]:
        table_name = str(getattr(self, "current_table", "") or "").strip()
        if not table_name:
            return []
        runs = list(self._selected_runs())
        if not runs:
            return []
        cols_sets = []
        for run in runs:
            try:
                df = getattr(run, "tables", {}).get(table_name)
            except Exception:
                df = None
            if isinstance(df, pd.DataFrame) and len(df.columns):
                cols_sets.append(set(map(str, df.columns)))
        if not cols_sets:
            return []
        try:
            common = set.intersection(*cols_sets)
        except Exception:
            common = set()
        if not common:
            return []
        try:
            df0 = getattr(runs[0], "tables", {}).get(table_name)
            if isinstance(df0, pd.DataFrame) and not df0.empty:
                common.discard(detect_time_col(df0))
        except Exception:
            pass
        sigs = sorted(common)
        if apply_filter:
            try:
                q = str(self.edit_filter.text() or "").strip()
            except Exception:
                q = ""
            if q:
                try:
                    import re

                    rx = re.compile(q, flags=re.IGNORECASE)
                    sigs = [s for s in sigs if rx.search(s)]
                except Exception:
                    ql = q.lower()
                    sigs = [s for s in sigs if ql in s.lower()]
        return sigs

    def _signal_exists_in_current_context(self, name: str) -> bool:
        sig_name = str(name).strip()
        if not sig_name:
            return False
        return sig_name in self._current_context_signal_names(apply_filter=False)

    def _ensure_signal_visible(self, name: str) -> bool:
        sig_name = str(name).strip()
        if not sig_name or not hasattr(self, "edit_filter"):
            return False
        try:
            current_filter = str(self.edit_filter.text() or "")
        except Exception:
            current_filter = ""
        if not current_filter:
            return False
        if not self._signal_exists_in_current_context(sig_name):
            return False
        try:
            self.edit_filter.blockSignals(True)
            self.edit_filter.clear()
        finally:
            try:
                self.edit_filter.blockSignals(False)
            except Exception:
                pass
        try:
            self._refresh_signal_list()
        except Exception:
            return False
        try:
            self._update_workspace_status()
        except Exception:
            pass
        return sig_name in list(getattr(self, "available_signals", []) or [])

    def _select_signal_by_name(self, name: str, *, exclusive: bool = False) -> bool:
        if not hasattr(self, 'list_signals'):
            return False
        # ensure signal is selected; keep previous selection if multi unless exclusive focus requested
        target_row = None
        for i in range(self.list_signals.count()):
            it = self.list_signals.item(i)
            if it is not None and str(it.text()) == str(name):
                target_row = i
                break
        if target_row is None and self._ensure_signal_visible(str(name)):
            for i in range(self.list_signals.count()):
                it = self.list_signals.item(i)
                if it is not None and str(it.text()) == str(name):
                    target_row = i
                    break
        if target_row is None:
            return False
        try:
            self.list_signals.blockSignals(True)
            for i in range(self.list_signals.count()):
                it = self.list_signals.item(i)
                is_target = (i == target_row)
                if is_target:
                    it.setSelected(True)
                    self._set_current_list_row(self.list_signals, i)
                elif exclusive:
                    it.setSelected(False)
            self._signals_selection_explicit = True
            try:
                self.signals_selected = self._selected_signals()
            except Exception:
                self.signals_selected = []
        finally:
            self.list_signals.blockSignals(False)
        return True

    def _focus_run_signal(self, run_label: str, signal_name: str) -> bool:
        target_run = None
        try:
            for run in getattr(self, "runs", []):
                if str(getattr(run, "label", "") or "") == str(run_label):
                    target_run = run
                    break
        except Exception:
            target_run = None
        if target_run is None:
            return False

        sig_name = str(signal_name or "").strip()
        run_label = str(run_label or "").strip()
        target_table = ""
        if sig_name:
            try:
                current_table = str(
                    getattr(self, "combo_table", None).currentText()
                    if hasattr(self, "combo_table") and getattr(self, "combo_table", None) is not None
                    else (getattr(self, "current_table", "") or "")
                ).strip()
            except Exception:
                current_table = str(getattr(self, "current_table", "") or "").strip()
            remembered_table = str(getattr(self, "table_selected", "") or "").strip()
            matching_tables: List[str] = []
            try:
                for table_name, df in (getattr(target_run, "tables", {}) or {}).items():
                    if isinstance(df, pd.DataFrame) and sig_name in df.columns:
                        matching_tables.append(str(table_name))
            except Exception:
                matching_tables = []
            if not matching_tables:
                return False
            for candidate in (current_table, remembered_table, "main"):
                if candidate and candidate in matching_tables:
                    target_table = candidate
                    break
            if not target_table:
                target_table = matching_tables[0]

        run_map: Dict[str, Run] = {}
        try:
            for run in getattr(self, "runs", []):
                lab = str(getattr(run, "label", "") or "").strip()
                if lab and lab not in run_map:
                    run_map[lab] = run
        except Exception:
            run_map = {}

        def _selected_run_labels_now() -> List[str]:
            labels: List[str] = []
            try:
                for run in self._selected_runs():
                    lab = str(getattr(run, "label", "") or "").strip()
                    if lab:
                        labels.append(lab)
            except Exception:
                return []
            return labels

        def _run_has_table(label: str, table_name: str) -> bool:
            if not table_name:
                return True
            run = run_map.get(str(label).strip())
            if run is None:
                return False
            try:
                return str(table_name) in (getattr(run, "tables", {}) or {})
            except Exception:
                return False

        def _run_has_signal(label: str, table_name: str, sig: str) -> bool:
            run = run_map.get(str(label).strip())
            if run is None or not table_name or not sig:
                return False
            try:
                df = getattr(run, "tables", {}).get(str(table_name))
            except Exception:
                df = None
            return isinstance(df, pd.DataFrame) and str(sig) in df.columns

        def _select_run_labels(labels: Sequence[str], *, current_label: str = "") -> bool:
            picked: List[str] = []
            for lab in labels:
                lab_txt = str(lab).strip()
                if lab_txt and lab_txt in run_map and lab_txt not in picked:
                    picked.append(lab_txt)
            if not picked or not hasattr(self, "list_runs"):
                return False
            try:
                self.list_runs.blockSignals(True)
                picked_paths: List[str] = []
                current_row = -1
                for i in range(self.list_runs.count()):
                    it = self.list_runs.item(i)
                    is_pick = it is not None and str(it.text()) in picked
                    if it is not None:
                        it.setSelected(bool(is_pick))
                        if is_pick:
                            key = it.data(QtCore.Qt.UserRole)
                            key = str(key).strip() if key is not None else ""
                            if key:
                                picked_paths.append(key)
                            if current_label and str(it.text()) == str(current_label):
                                current_row = i
                            elif current_row < 0:
                                current_row = i
                if current_row >= 0:
                    self._set_current_list_row(self.list_runs, current_row)
                self._runs_selection_explicit = True
                self.runs_selected_paths = list(picked_paths)
            finally:
                try:
                    self.list_runs.blockSignals(False)
                except Exception:
                    pass
            return True

        desired_labels = _selected_run_labels_now()
        if run_label not in desired_labels:
            desired_labels.append(run_label)
        if not desired_labels:
            desired_labels = [run_label]
        if target_table:
            desired_labels = [lab for lab in desired_labels if _run_has_table(lab, target_table)]
            if run_label not in desired_labels:
                if not _run_has_table(run_label, target_table):
                    return False
                desired_labels.insert(0, run_label)
        if sig_name:
            desired_labels = [lab for lab in desired_labels if _run_has_signal(lab, target_table, sig_name)]
            if run_label not in desired_labels:
                if not _run_has_signal(run_label, target_table, sig_name):
                    return False
                desired_labels.insert(0, run_label)
        if not _select_run_labels(desired_labels, current_label=run_label):
            return False
        self._on_run_selection_changed()
        try:
            self._remember_reference_run(target_run)
        except Exception:
            pass
        try:
            if hasattr(self, "combo_ref") and getattr(self, "combo_ref", None) is not None:
                idx_ref = self.combo_ref.findText(run_label)
                if idx_ref >= 0 and str(self.combo_ref.currentText() or "") != run_label:
                    self.combo_ref.setCurrentIndex(idx_ref)
            if target_table and hasattr(self, "combo_table"):
                idx = self.combo_table.findText(target_table)
                if idx >= 0 and str(self.combo_table.currentText() or "") != target_table:
                    self.combo_table.setCurrentIndex(idx)
        except Exception:
            return False
        if sig_name and not self._select_signal_by_name(sig_name, exclusive=True):
            return False
        self._rebuild_plots()
        return True

    def _set_current_list_row(self, widget, row: int) -> None:
        try:
            row = int(row)
            model = widget.model() if widget is not None else None
            sel_model = widget.selectionModel() if widget is not None else None
            if model is not None and sel_model is not None:
                idx = model.index(row, 0)
                if idx.isValid():
                    sel_model.setCurrentIndex(idx, QtCore.QItemSelectionModel.NoUpdate)
                    return
        except Exception:
            pass
        try:
            if widget is not None:
                widget.setCurrentRow(int(row))
        except Exception:
            pass

    def _set_current_list_item_by_text(self, widget, text: str) -> bool:
        if widget is None:
            return False
        for i in range(widget.count()):
            it = widget.item(i)
            if it is not None and str(it.text()) == str(text):
                self._set_current_list_row(widget, i)
                return True
        return False


    def _set_playhead_time(self, t: float) -> None:
        """Set playhead by time (best effort)."""
        try:
            t_ref = getattr(self, '_t_ref', None)
            if t_ref is None or len(t_ref) == 0:
                return
            t = float(t)
            idx = int(np.argmin(np.abs(np.asarray(t_ref, dtype=float) - t)))
            idx = int(np.clip(idx, 0, len(t_ref) - 1))
            self.slider_time.setValue(idx)
        except Exception:
            pass

    def _schedule_influence_rebuild(self) -> None:
        """Debounce rebuild (playhead может ездить часто)."""
        try:
            if not hasattr(self, "_infl_timer") or self._infl_timer is None:
                return
            # 120–200 мс достаточно: успевает “дышать”, но не убивает FPS при Play
            self._infl_timer.start(160)
        except Exception:
            pass

    def _corr_color(self, v: float) -> QtGui.QColor:
        """Пастельная diverging раскраска для корреляций [-1..1]."""
        try:
            if not np.isfinite(v):
                return QtGui.QColor(245, 245, 245)
            a = float(min(1.0, max(0.0, abs(v))))
            # лёгкая насыщенность, чтобы текст оставался читаемым
            k = int(120 * a)
            if v >= 0:
                # красный оттенок
                return QtGui.QColor(255, 255 - k, 255 - k)
            else:
                # синий оттенок
                return QtGui.QColor(255 - k, 255 - k, 255)
        except Exception:
            return QtGui.QColor(245, 245, 245)

    def _influence_status_text(
        self,
        *,
        t0: float,
        runs_count: int,
        sigs_count: int,
        feat_all_count: int,
        feat_sel_count: int,
        use_delta: bool,
        ref_label: str,
        top_feature: str,
        top_signal: str,
        top_corr: float,
    ) -> str:
        mode_txt = f"Δ vs {ref_label}" if use_delta else "value"
        line1 = (
            f"t={float(t0):.4f}s | runs={int(runs_count)} | sigs={int(sigs_count)} | "
            f"meta(all)={int(feat_all_count)} shown={int(feat_sel_count)} | mode={mode_txt}"
        )
        analysis_mode = str(getattr(self, "_workspace_analysis_mode", "all_to_all") or "all_to_all")
        target_signal = self._workspace_analysis_target_signal([str(top_signal)]) if str(top_signal or "").strip() else ""
        if analysis_mode == "one_to_all":
            line2 = (
                f"Driver candidate: {top_feature or '—'} | strongest visible response: {top_signal or '—'} "
                f"({float(top_corr):+.2f})"
            )
            hint = "Sweep nearby times to see whether one driver keeps fanning out across multiple signals."
        elif analysis_mode == "all_to_one":
            line2 = (
                f"Target: {target_signal or top_signal or '—'} | lead driver: {top_feature or '—'} "
                f"({float(top_corr):+.2f})"
            )
            hint = "Keep one target stable and cross-check the lead driver with Events / Delta."
        else:
            line2 = (
                f"Dominant corridor: {top_feature or '—'} -> {top_signal or '—'} "
                f"({float(top_corr):+.2f})"
            )
            hint = "Compare this corridor against the current cloud/clusters before trusting the coupling."
        line3 = f"Heuristic: {hint} Click a cell to open the scatter below."
        return "\n".join([line1, line2, line3])

    def _clear_influence_view(self, note: str = "") -> None:
        try:
            self.tbl_infl.setRowCount(0)
            self.tbl_infl.setColumnCount(0)
            self.tbl_infl.setEnabled(False)
        except Exception:
            pass
        try:
            self._infl_scatter_item = None
            self.plot_infl.clear()
            self.plot_infl.setEnabled(False)
        except Exception:
            pass
        try:
            self.lbl_infl_note.setText(note)
        except Exception:
            pass
        self._infl_cache = None
        self._insight_infl = {}
        self._update_workspace_status()

    def _value_at_time(self, run: Run, sig: str, t: float) -> float:
        x, y, _u = self._get_xy(run, sig)
        if x.size >= 2:
            try:
                return float(np.interp(float(t), x, y, left=np.nan, right=np.nan))
            except Exception:
                return float("nan")
        if y.size:
            return float(y[-1])
        return float("nan")

    def _rebuild_influence(self) -> None:
        """Полная перестройка Influence(t) таблицы + scatter (если возможно)."""
        try:
            if not hasattr(self, "chk_infl_enable"):
                return
            if not bool(self.chk_infl_enable.isChecked()):
                self._clear_influence_view("Influence(t) выключен.")
                return

            if infl_flatten_meta_numeric is None or infl_corr_matrix is None:
                self._clear_influence_view("Influence(t) недоступен: модуль compare_influence не импортирован.")
                return

            runs = self._ordered_runs_for_reference(self._selected_runs())
            sigs = self._selected_signals()

            if not runs:
                self._clear_influence_view("Выберите хотя бы один прогон (Runs).")
                return
            if len(runs) < 3:
                self._clear_influence_view("Для корреляции нужно минимум 3 прогона (runs).")
                return
            if len(sigs) < 1:
                self._clear_influence_view("Выберите хотя бы один сигнал (Signals).")
                return
            if self._t_ref.size == 0:
                self._clear_influence_view("Нет общего времени (t_ref) — вероятно, не загружены данные.")
                return

            # playhead time
            idx = int(max(0, min(self.slider_time.value(), int(len(self._t_ref) - 1))))
            t0 = float(self._t_ref[idx])

            # reference for Δ
            ref_run = self._reference_run(runs) or runs[0]
            use_delta = bool(self.chk_delta.isChecked())

            # Y: runs × sigs
            Y = np.full((len(runs), len(sigs)), np.nan, dtype=float)
            ref_vals = np.array([self._value_at_time(ref_run, s, t0) for s in sigs], dtype=float)

            for i, r in enumerate(runs):
                for j, s in enumerate(sigs):
                    v = self._value_at_time(r, s, t0)
                    if use_delta:
                        if r.label == ref_run.label:
                            v = 0.0
                        else:
                            v = v - float(ref_vals[j])
                    Y[i, j] = float(v)

            # X: runs × features
            flat = [infl_flatten_meta_numeric(getattr(r, "meta", {})) for r in runs]  # type: ignore
            feat_all = sorted({k for d in flat for k in d.keys()})
            if not feat_all:
                self._clear_influence_view("В meta_json нет численных параметров.")
                return

            X = np.asarray([[float(d.get(k, np.nan)) for k in feat_all] for d in flat], dtype=float)

            # prefilter if too many
            feat_use = list(feat_all)
            X_use = X
            if len(feat_use) > 600 and infl_prefilter_features_by_variance is not None:  # type: ignore
                keep0 = max(240, int(self.spin_infl_maxfeat.value()) * 10)
                pref = infl_prefilter_features_by_variance(X_use, feat_use, keep=keep0)  # type: ignore
                idx_map = {n: ii for ii, n in enumerate(feat_use)}
                pref_idx = [idx_map[n] for n in pref if n in idx_map]
                feat_use = [feat_use[ii] for ii in pref_idx]
                X_use = X_use[:, pref_idx] if pref_idx else X_use

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                C = infl_corr_matrix(X_use, Y, min_n=3)  # type: ignore  # features × sigs
            if np.asarray(C, dtype=float).size == 0 or not np.isfinite(C).any():
                self._clear_influence_view("Influence(t): текущий выбор даёт только NaN/пустые корреляции.")
                return

            # rank features by max |corr|
            if infl_rank_features_by_max_abs_corr is not None:  # type: ignore
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    feat_sorted = infl_rank_features_by_max_abs_corr(C, feat_use)  # type: ignore
            else:
                feat_sorted = feat_use

            feat_sel = feat_sorted[: int(self.spin_infl_maxfeat.value())]
            if not feat_sel:
                self._clear_influence_view("Не удалось выбрать meta параметры для отображения.")
                return

            idx_map2 = {n: ii for ii, n in enumerate(feat_use)}
            sel_idx = [idx_map2[n] for n in feat_sel if n in idx_map2]
            C_sel = C[sel_idx, :] if sel_idx else C
            if np.asarray(C_sel, dtype=float).size == 0 or not np.isfinite(C_sel).any():
                self._clear_influence_view("Influence(t): нет конечных корреляций для текущего выбора.")
                return

            # Fill table
            self.tbl_infl.setRowCount(len(feat_sel))
            self.tbl_infl.setColumnCount(len(sigs))
            self.tbl_infl.setEnabled(bool(feat_sel) and bool(sigs))
            self.plot_infl.setEnabled(bool(feat_sel) and bool(sigs))

            # headers with trim + tooltip
            def _trim(s: str, n: int = 34) -> str:
                s = str(s)
                return s if len(s) <= n else (s[: max(0, n - 1)] + "…")

            for j, s in enumerate(sigs):
                hi = QtWidgets.QTableWidgetItem(_trim(s, 30))
                hi.setToolTip(str(s))
                self.tbl_infl.setHorizontalHeaderItem(j, hi)

            for i, f in enumerate(feat_sel):
                vi = QtWidgets.QTableWidgetItem(_trim(f, 34))
                vi.setToolTip(str(f))
                self.tbl_infl.setVerticalHeaderItem(i, vi)

            for i in range(len(feat_sel)):
                for j in range(len(sigs)):
                    v = float(C_sel[i, j]) if C_sel.size else float("nan")
                    it = QtWidgets.QTableWidgetItem("" if not np.isfinite(v) else f"{v:+.2f}")
                    it.setTextAlignment(QtCore.Qt.AlignCenter)
                    it.setBackground(self._corr_color(v))
                    it.setToolTip(
                        f"meta: {feat_sel[i]}\n"
                        f"sig:  {sigs[j]}\n"
                        f"corr: {v:.4f}\n"
                        f"t:    {t0:.6f} s"
                    )
                    self.tbl_infl.setItem(i, j, it)

            try:
                self.tbl_infl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
                self.tbl_infl.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            except Exception:
                pass

            try:
                A = np.abs(np.asarray(C_sel, dtype=float))
                A = np.nan_to_num(A, nan=-1.0, posinf=-1.0, neginf=-1.0)
                k_top = int(np.argmax(A))
                i_top, j_top = int(k_top // len(sigs)), int(k_top % len(sigs))
                self._insight_infl = {
                    "feature": feat_sel[i_top] if 0 <= i_top < len(feat_sel) else "",
                    "signal": sigs[j_top] if 0 <= j_top < len(sigs) else "",
                    "corr": float(C_sel[i_top, j_top]) if C_sel.size else float("nan"),
                    "time_s": float(t0),
                    "runs": int(len(runs)),
                    "meta_count": int(len(feat_sel)),
                    "delta": bool(use_delta),
                }
            except Exception:
                self._insight_infl = {}

            top_feature = str((self._insight_infl or {}).get("feature") or "")
            top_signal = str((self._insight_infl or {}).get("signal") or "")
            top_corr = float((self._insight_infl or {}).get("corr", float("nan")) or float("nan"))
            self.lbl_infl_note.setText(
                self._influence_status_text(
                    t0=float(t0),
                    runs_count=len(runs),
                    sigs_count=len(sigs),
                    feat_all_count=len(feat_all),
                    feat_sel_count=len(feat_sel),
                    use_delta=bool(use_delta),
                    ref_label=str(ref_run.label),
                    top_feature=top_feature,
                    top_signal=top_signal,
                    top_corr=top_corr,
                )
            )

            # Cache for fast scatter updates
            self._infl_cache = {
                "t": t0,
                "runs": runs,
                "run_labels": [r.label for r in runs],
                "sigs": list(sigs),
                "feat_sel": list(feat_sel),
                "X_sel": X_use[:, sel_idx] if sel_idx else X_use,
                "Y": Y,
                "C_sel": C_sel,
                "use_delta": use_delta,
                "ref_label": ref_run.label,
            }

            # Choose default focus: max |corr|
            try:
                if self._infl_focus_feat in feat_sel and self._infl_focus_sig in sigs:
                    i0 = feat_sel.index(self._infl_focus_feat)
                    j0 = sigs.index(self._infl_focus_sig)
                else:
                    A = np.abs(C_sel)
                    A = np.nan_to_num(A, nan=-1.0)
                    k = int(np.argmax(A))
                    i0, j0 = int(k // len(sigs)), int(k % len(sigs))
                    self._infl_focus_feat = feat_sel[i0]
                    self._infl_focus_sig = sigs[j0]
                self.tbl_infl.setCurrentCell(i0, j0)
            except Exception:
                pass

            self._update_influence_scatter_from_cache()
            self._update_workspace_status()

        except Exception as e:
            self._clear_influence_view(f"Influence(t) ошибка: {e}")

    def _on_infl_cell_clicked(self, row: int, col: int) -> None:
        try:
            if self._infl_cache is None:
                return
            feat_sel = self._infl_cache.get("feat_sel", [])
            sigs = self._infl_cache.get("sigs", [])
            if 0 <= int(row) < len(feat_sel) and 0 <= int(col) < len(sigs):
                self._infl_focus_feat = str(feat_sel[int(row)])
                self._infl_focus_sig = str(sigs[int(col)])
                self._update_influence_scatter_from_cache()
                self._update_inflheat_pair_trace()
        except Exception:
            pass

    def _on_influence_scatter_clicked(self, _item, points, *_args) -> None:
        if points is None:
            return
        try:
            if len(points) <= 0:
                return
        except Exception:
            return
        try:
            point = points[0]
            data = point.data()
            if isinstance(data, np.ndarray):
                data = data.tolist()
            if isinstance(data, (list, tuple)):
                data = data[0] if data else ""
            run_label = str(data or "").strip()
        except Exception:
            return
        sig = str(getattr(self, "_infl_focus_sig", "") or "").strip()
        if not run_label or not sig:
            return
        self._focus_run_signal(run_label, sig)

    def _update_influence_scatter_from_cache(self) -> None:
        try:
            if self._infl_cache is None:
                return
            feat_sel = self._infl_cache["feat_sel"]
            sigs = self._infl_cache["sigs"]
            runs = self._infl_cache["runs"]
            X_sel = np.asarray(self._infl_cache["X_sel"], dtype=float)
            Y = np.asarray(self._infl_cache["Y"], dtype=float)
            C_sel = np.asarray(self._infl_cache["C_sel"], dtype=float)
            t0 = float(self._infl_cache["t"])

            if self._infl_focus_feat not in feat_sel or self._infl_focus_sig not in sigs:
                return
            i = feat_sel.index(self._infl_focus_feat)
            j = sigs.index(self._infl_focus_sig)

            x = X_sel[:, i] if X_sel.ndim == 2 and X_sel.shape[1] > i else np.full((len(runs),), np.nan)
            y = Y[:, j] if Y.ndim == 2 and Y.shape[1] > j else np.full((len(runs),), np.nan)
            c = float(C_sel[i, j]) if C_sel.size else float("nan")

            m = np.isfinite(x) & np.isfinite(y)

            self.plot_infl.clear()
            self.plot_infl.showGrid(x=True, y=True, alpha=0.25)
            self._infl_scatter_item = None

            # points
            try:
                ref_label = str(self._infl_cache.get("ref_label") or "")
                spots = []
                for idx, run in enumerate(runs):
                    xv = float(x[idx]) if idx < len(x) else float("nan")
                    yv = float(y[idx]) if idx < len(y) else float("nan")
                    if not (np.isfinite(xv) and np.isfinite(yv)):
                        continue
                    run_label = str(getattr(run, "label", "") or "")
                    is_ref = bool(ref_label and run_label == ref_label)
                    spots.append(
                        {
                            "pos": (xv, yv),
                            "data": run_label,
                            "size": 12 if is_ref else 9,
                            "brush": pg.mkBrush(235, 165, 40, 220) if is_ref else pg.mkBrush(80, 80, 80, 185),
                            "pen": pg.mkPen(150, 90, 20, 220) if is_ref else pg.mkPen(45, 45, 45, 200),
                            "symbol": "o",
                        }
                    )
                scatter = pg.ScatterPlotItem(pxMode=True)
                if spots:
                    scatter.addPoints(spots)
                    try:
                        scatter.sigClicked.connect(self._on_influence_scatter_clicked)
                    except Exception:
                        pass
                    self.plot_infl.addItem(scatter)
                    self._infl_scatter_item = scatter
            except Exception:
                pass

            # trend
            if self.chk_infl_trend.isChecked() and int(m.sum()) >= 3:
                try:
                    coef = np.polyfit(x[m], y[m], 1)
                    xs = np.linspace(float(np.nanmin(x[m])), float(np.nanmax(x[m])), 120)
                    ys = coef[0] * xs + coef[1]
                    self.plot_infl.plot(xs, ys, pen=pg.mkPen((0, 0, 0, 200), width=2))
                except Exception:
                    pass

            self.plot_infl.setLabel('bottom', f"meta: {self._infl_focus_feat}")
            self.plot_infl.setLabel('left', f"sig@t: {self._infl_focus_sig}")

            # title / info
            try:
                title = f"t={t0:.4f}s | corr={c:.3f} | n={int(m.sum())} | click a point to focus run"
                self.plot_infl.setTitle(title)
            except Exception:
                pass
            try:
                self._update_inflheat_pair_trace()
            except Exception:
                pass

        except Exception:
            pass
    def _run_from_npz_path(self, path: Path) -> Run:
        p = self._absolute_run_path(Path(path))
        b = load_npz_bundle(p)
        tables = b.get("tables") or {}
        meta = b.get("meta") or {}
        label = _default_label(p, meta)
        ev_df = None
        if ev_scan_run_tables is not None and ev_events_to_frame is not None:
            try:
                evs = ev_scan_run_tables(tables, rising_only=True)
                ev_df = ev_events_to_frame(evs)
            except Exception:
                ev_df = None
        return Run(
            label=label,
            path=p,
            tables=tables,
            meta=meta,
            visual_contract=dict(b.get('visual_contract') or {}),
            anim_diagnostics=dict(b.get('anim_diagnostics') or {}),
            geometry_acceptance=dict(b.get('geometry_acceptance') or {}),
            events=ev_df,
        )

    def _rebuild_runs_ui(
        self,
        preferred_selected_paths: Optional[Sequence[str]] = None,
        preferred_signals: Optional[Sequence[str]] = None,
    ) -> None:
        # populate runs list without firing selection storms or duplicating connections
        if bool(getattr(self, "_runs_selection_connected", False)):
            try:
                self.list_runs.itemSelectionChanged.disconnect(self._on_run_selection_changed)
            except Exception:
                pass
            self._runs_selection_connected = False
        selected_keys = None if preferred_selected_paths is None else {
            str(p) for p in preferred_selected_paths if str(p).strip()
        }
        self.list_runs.blockSignals(True)
        try:
            self.list_runs.clear()
            for r in self.runs:
                it = QtWidgets.QListWidgetItem(r.label)
                it.setToolTip(str(r.path))
                run_key = self._normalized_run_path(getattr(r, 'path', Path('')))
                it.setData(QtCore.Qt.UserRole, run_key)
                self.list_runs.addItem(it)
                if selected_keys is None or run_key in selected_keys:
                    it.setSelected(True)
        finally:
            self.list_runs.blockSignals(False)

        built_selected_keys: List[str] = []
        try:
            for i in range(self.list_runs.count()):
                it = self.list_runs.item(i)
                if it is None or not it.isSelected():
                    continue
                key = it.data(QtCore.Qt.UserRole)
                key = str(key).strip() if key is not None else ""
                if key:
                    built_selected_keys.append(key)
        except Exception:
            built_selected_keys = []
        if built_selected_keys:
            self.runs_selected_paths = list(built_selected_keys)
        elif not bool(getattr(self, '_runs_selection_explicit', False)):
            self.runs_selected_paths = []

        self.list_runs.itemSelectionChanged.connect(self._on_run_selection_changed)
        self._runs_selection_connected = True
        self._refresh_reference_runs()
        self._refresh_table_list()
        kept_selected = self._refresh_signal_list(preferred_signals)
        if (not kept_selected) and self.available_signals and not bool(getattr(self, '_signals_selection_explicit', False)):
            self._select_default_signals()
        self._refresh_event_list()
        self._refresh_events_table()
        self._refresh_anim_diag_panel()
        self._rebuild_plots()

    def _load_paths(self, paths: List[Path], *, replace: bool = False) -> int:
        if not paths:
            return 0
        self._last_load_errors = []
        had_runs_before = bool(getattr(self, "runs", []))
        prev_selected_keys: Set[str] = set()
        prev_runs_explicit = bool(getattr(self, "_runs_selection_explicit", False))
        prev_runs_selected_paths = [str(x) for x in (getattr(self, "runs_selected_paths", []) or []) if str(x).strip()]
        prev_signals_explicit = bool(getattr(self, "_signals_selection_explicit", False))
        prev_events_explicit = bool(getattr(self, "_events_selection_explicit", False))
        try:
            prev_signals_selected = [
                str(x)
                for x in (
                    getattr(self, "signals_selected", [])
                    if prev_signals_explicit
                    else self._selected_signals()
                )
            ]
        except Exception:
            prev_signals_selected = []
        try:
            prev_events_selected = [
                str(x)
                for x in (
                    getattr(self, "events_selected", [])
                    if prev_events_explicit
                    else self._get_selected_event_signals()
                )
            ]
        except Exception:
            prev_events_selected = []
        try:
            for run in self._selected_runs():
                prev_selected_keys.add(self._normalized_run_path(getattr(run, "path", Path(""))))
        except Exception:
            prev_selected_keys = set()
        if prev_selected_keys and not prev_runs_selected_paths:
            prev_runs_selected_paths = list(prev_selected_keys)
        base_runs = [] if replace else list(self.runs)
        old_run_keys: Set[str] = set()
        if replace:
            for run in getattr(self, "runs", []):
                try:
                    old_run_keys.add(self._normalized_run_path(getattr(run, "path", Path(""))))
                except Exception:
                    pass
        seen_paths: Set[str] = set()
        for run in base_runs:
            try:
                seen_paths.add(self._normalized_run_path(getattr(run, "path", Path(""))))
            except Exception:
                pass
        unique_paths: List[Path] = []
        for p in paths:
            p_abs = self._absolute_run_path(Path(p))
            key = self._normalized_run_path(p_abs)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            unique_paths.append(p_abs)

        new_runs = list(base_runs)
        loaded_count = 0
        loaded_run_keys: Set[str] = set()
        preserve_selection_state = bool(had_runs_before and not replace)
        for p in unique_paths:
            p = self._absolute_run_path(Path(p))
            if not p.exists() or p.suffix.lower() != ".npz":
                continue
            try:
                run_obj = self._run_from_npz_path(p)
                new_runs.append(run_obj)
                try:
                    loaded_run_keys.add(self._normalized_run_path(getattr(run_obj, "path", p)))
                except Exception:
                    pass
                loaded_count += 1
            except Exception as e:
                self._last_load_errors.append(f"Failed to load {p}: {e}")

        if loaded_count <= 0:
            for msg in self._last_load_errors:
                print(msg)
            return 0

        if replace and old_run_keys:
            new_run_keys: Set[str] = set()
            for run in new_runs:
                try:
                    new_run_keys.add(self._normalized_run_path(getattr(run, "path", Path(""))))
                except Exception:
                    pass
            if new_run_keys and new_run_keys == old_run_keys:
                preserve_selection_state = True
            elif new_run_keys and new_run_keys != old_run_keys:
                self._clear_runtime_dataset_memory()
                preserve_selection_state = False
        else:
            new_run_keys = set()

        self.runs = new_runs
        self._invalidate_run_dependent_caches()
        if preserve_selection_state:
            self.runs_selected_paths = list(prev_runs_selected_paths)
            self._runs_selection_explicit = bool(prev_runs_explicit)
            self.signals_selected = list(prev_signals_selected)
            self._signals_selection_explicit = bool(prev_signals_explicit)
            self.events_selected = list(prev_events_selected)
            self._events_selection_explicit = bool(prev_events_explicit)
            preferred_signals = list(prev_signals_selected)
        else:
            self.runs_selected_paths = []
            self._runs_selection_explicit = False
            self.signals_selected = []
            self._signals_selection_explicit = False
            self.events_selected = []
            self._events_selection_explicit = False
            preferred_signals = []
        self._ensure_unique_run_labels()
        preferred_selected_keys: Optional[Set[str]]
        if not had_runs_before:
            preferred_selected_keys = set(loaded_run_keys)
        elif replace:
            if new_run_keys and new_run_keys == old_run_keys:
                preferred_selected_keys = set(prev_selected_keys)
            else:
                preferred_selected_keys = None
        else:
            if prev_selected_keys:
                preferred_selected_keys = set(prev_selected_keys) | set(loaded_run_keys)
            else:
                preferred_selected_keys = set()
        self._rebuild_runs_ui(preferred_selected_keys, preferred_signals)
        for msg in self._last_load_errors:
            print(msg)
        self._update_workspace_status()
        return loaded_count

    def _selected_runs(self) -> List[Run]:
        idxs = [i.row() for i in self.list_runs.selectedIndexes()]
        if not idxs:
            return []
        return [self.runs[i] for i in idxs if 0 <= i < len(self.runs)]

    def _reference_run(self, runs: Optional[List[Run]] = None) -> Optional[Run]:
        runs_use = list(runs) if runs is not None else list(self._selected_runs())
        if not runs_use:
            return None
        want = ""
        try:
            want = str(self.combo_ref.currentText() or "").strip()
        except Exception:
            want = ""
        if want:
            for run in runs_use:
                if str(run.label) == want:
                    return run
        return runs_use[0]

    def _reference_run_label(self, runs: Optional[List[Run]] = None) -> str:
        ref = self._reference_run(runs)
        return str(ref.label) if ref is not None else ""

    def _remember_reference_run(self, run: Optional[Run] = None) -> None:
        ref = run if run is not None else self._reference_run()
        if ref is None:
            return
        try:
            self.reference_run_selected = str(getattr(ref, "label", "") or "")
        except Exception:
            self.reference_run_selected = ""
        try:
            self.reference_run_selected_path = self._normalized_run_path(getattr(ref, "path", Path("")))
        except Exception:
            self.reference_run_selected_path = ""

    def _ordered_runs_for_reference(self, runs: Optional[List[Run]] = None) -> List[Run]:
        runs_use = list(runs) if runs is not None else list(self._selected_runs())
        ref = self._reference_run(runs_use)
        if ref is None:
            return runs_use
        return [ref] + [run for run in runs_use if run is not ref]

    def _refresh_reference_runs(self, preferred_label: str = "") -> None:
        combo = getattr(self, "combo_ref", None)
        if combo is None:
            return
        runs = self._selected_runs()
        labels = [str(r.label) for r in runs]
        remembered_label = str(getattr(self, "reference_run_selected", "") or "").strip()
        current = ""
        try:
            current = str(combo.currentText() or "").strip()
        except Exception:
            current = ""
        target = ""
        remembered_target = ""
        remembered_path = str(getattr(self, "reference_run_selected_path", "") or "").strip()
        if remembered_path:
            for run in runs:
                try:
                    if self._normalized_run_path(getattr(run, "path", Path(""))) == remembered_path:
                        target = str(run.label)
                        remembered_target = target
                        break
                except Exception:
                    pass
        for candidate in (str(preferred_label or "").strip(), remembered_target, remembered_label, current):
            if candidate and candidate in labels:
                target = candidate
                break
        if not target and labels:
            target = labels[0]
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(labels)
            combo.setEnabled(bool(labels))
            if target:
                combo.setCurrentText(target)
        finally:
            combo.blockSignals(False)
        if labels:
            if remembered_target or (not remembered_label and not remembered_path):
                self._remember_reference_run(self._reference_run(runs))

    def _ensure_unique_run_labels(self) -> None:
        used: Set[str] = set()
        for idx, run in enumerate(self.runs):
            base = str(getattr(run, "label", "") or "").strip()
            if not base:
                try:
                    base = str(getattr(run, "path", None).stem or "").strip()
                except Exception:
                    base = ""
            if not base:
                base = f"run {idx + 1}"

            label = base
            if label in used:
                stem = ""
                try:
                    stem = str(getattr(run, "path", None).stem or "").strip()
                except Exception:
                    stem = ""
                if stem and stem != base:
                    candidate = f"{base} [{stem}]"
                    if candidate not in used:
                        label = candidate
                if label in used:
                    n = 2
                    while True:
                        candidate = f"{base} ({n})"
                        if candidate not in used:
                            label = candidate
                            break
                        n += 1

            run.label = label
            used.add(label)

    def _clear_pending_dataset_restore(self) -> None:
        stt = getattr(self, '_restore_after_load', None)
        if not isinstance(stt, dict):
            return
        for k in (
            'dataset_paths',
            'runs',
            'runs_paths',
            'runs_selection_explicit',
            'reference_run',
            'reference_run_path',
            'table',
            'dist_signal',
            'nav_signal',
            'nav_region',
            'play_time',
            'play_index',
            'signals',
            'signals_selection_explicit',
            'events_selected',
            'events_selection_explicit',
        ):
            stt.pop(k, None)

    def _pending_dataset_restore_matches_paths(self, paths: Sequence[Path]) -> bool:
        stt = getattr(self, '_restore_after_load', None)
        if not isinstance(stt, dict):
            return False
        dataset_paths = [str(x) for x in (stt.get('dataset_paths') or []) if str(x).strip()]
        want_paths = [str(x) for x in (stt.get('runs_paths') or []) if str(x).strip()]
        ref_path = str(stt.get('reference_run_path') or '').strip()
        if not dataset_paths and ref_path:
            want_paths.append(ref_path)
        if not dataset_paths and not want_paths and not ref_path:
            dataset_keys = (
                'dataset_paths',
                'runs',
                'runs_selection_explicit',
                'reference_run',
                'table',
                'dist_signal',
                'play_time',
                'play_index',
                'signals',
                'signals_selection_explicit',
                'events_selected',
                'events_selection_explicit',
            )
            return not any(k in stt for k in dataset_keys)
        try:
            selected = {self._normalized_run_path(Path(p)) for p in paths}
            dataset_wanted = {self._normalized_run_path(Path(p)) for p in dataset_paths}
            wanted = {self._normalized_run_path(Path(p)) for p in want_paths}
            ref_wanted = self._normalized_run_path(Path(ref_path)) if ref_path else ""
        except Exception:
            return True
        if not selected:
            return True
        if dataset_wanted:
            return selected == dataset_wanted
        if wanted and not wanted.issubset(selected):
            return False
        if ref_wanted:
            return ref_wanted in selected
        if wanted:
            return True
        return False

    def _clear_pending_dataset_restore_if_mismatch(self, paths: Sequence[Path]) -> None:
        try:
            real_paths = [Path(p) for p in paths if str(p).strip()]
        except Exception:
            return
        if not real_paths:
            return
        if not self._pending_dataset_restore_matches_paths(real_paths):
            self._clear_pending_dataset_restore()

    def _clear_runtime_dataset_memory(self) -> None:
        self.runs_selected_paths = []
        self._runs_selection_explicit = False
        self.current_table = ""
        self.table_selected = ""
        self.dist_signal_selected = ""
        edit_filter = getattr(self, "edit_filter", None)
        if edit_filter is not None:
            try:
                edit_filter.blockSignals(True)
                edit_filter.clear()
            finally:
                try:
                    edit_filter.blockSignals(False)
                except Exception:
                    pass
        self.navigator_signal_selected = ""
        self.navigator_region_selected = None
        self.playhead_time_selected = None
        self.playhead_index_selected = None
        self.reference_run_selected = ""
        self.reference_run_selected_path = ""
        self._events_runs_cache = None
        self._peak_cache = None
        self._open_timeline_cache = None
        self._static_stroke_cache = None
        self._geometry_acceptance_cache = None
        self._insight_peak_heat = {}
        self._insight_events = {}
        self._mv_checked_dims_selected = None
        self._infl_focus_feat = None
        self._infl_focus_sig = None
        combo = getattr(self, "combo_ref", None)
        if combo is not None:
            try:
                combo.blockSignals(True)
                combo.clear()
            finally:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass
        table_combo = getattr(self, "combo_table", None)
        if table_combo is not None:
            try:
                table_combo.blockSignals(True)
                table_combo.clear()
            finally:
                try:
                    table_combo.blockSignals(False)
                except Exception:
                    pass

    def _invalidate_run_dependent_caches(self) -> None:
        self._invalidate_multivar_cache()
        self._infl_cache = None
        self._peak_cache = None
        self._insight_peak_heat = {}
        self._dist_cache = None
        self._qa_cache_key = None
        self._qa_mat = None
        self._qa_run_labels = []
        self._qa_sig_labels = []
        self._qa_first_t = {}
        self._qa_cell_codes = {}

    def _normalized_run_path(self, path: Path) -> str:
        return _normalized_fs_path_key(path)

    def _absolute_run_path(self, path: Path) -> Path:
        return _absolute_fs_path(path)

    def _refresh_anim_diag_panel(self) -> None:
        txtw = getattr(self, 'txt_anim_diag', None)
        if txtw is None:
            return
        runs = self._selected_runs()
        if not runs:
            txtw.setPlainText('Нет выбранных прогонов.')
            self._update_workspace_status()
            return
        blocks: List[str] = []
        for run in runs[:6]:
            lines = format_anim_diagnostics_lines(getattr(run, 'anim_diagnostics', {}), label=str(getattr(run, 'label', '')))
            ga = dict(getattr(run, 'geometry_acceptance', {}) or {})
            if ga:
                lines.extend(format_geometry_acceptance_summary_lines(ga, label=str(getattr(run, 'label', ''))))
            vc = dict(getattr(run, 'visual_contract', {}) or {})
            if vc:
                lines.append(f"Road source: {vc.get('road_source') or '—'}")
                lines.append(f"Road complete: {vc.get('road_complete')}")
                lines.append(f"Solver points complete: {vc.get('solver_points_complete')}")
                lines.append(f"Geometry contract ok: {vc.get('geometry_contract_ok')}")
            blocks.append('\n'.join(lines))
        if len(runs) > 6:
            blocks.append(f'... +{len(runs)-6} more selected runs')
        txtw.setPlainText('\n\n'.join(blocks))
        self._update_workspace_status()

    def _on_table_changed(self, _i: int):
        txt = self.combo_table.currentText()
        if txt:
            try:
                prev_signals = self._selected_signals()
            except Exception:
                prev_signals = []
            self.current_table = txt
            self.table_selected = str(txt)
            kept_selected = self._refresh_signal_list(prev_signals)
            if (not kept_selected) and self.available_signals and not bool(getattr(self, '_signals_selection_explicit', False)):
                self._select_default_signals()
            self._schedule_static_stroke_rebuild(delay_ms=10)
            self._rebuild_plots()
        self._update_workspace_status()

    def _refresh_table_list(self) -> None:
        runs = self._selected_runs()
        combo_current = self.combo_table.currentText() if hasattr(self, "combo_table") else ""
        remembered_table = str(getattr(self, "table_selected", "") or "").strip()
        current = str(combo_current or self.current_table or remembered_table or "")
        if not runs:
            tables = []
        else:
            table_sets = [set(map(str, r.tables.keys())) for r in runs if getattr(r, "tables", None)]
            tables = sorted(set.intersection(*table_sets)) if table_sets else []
        self.table_names = tables
        target = ""
        for candidate in (remembered_table, current):
            if candidate and candidate in tables:
                target = candidate
                break
        if not target and tables:
            target = "main" if "main" in tables else tables[0]
        if not hasattr(self, "combo_table"):
            if tables:
                self.current_table = target
                if self.current_table and ((not remembered_table) or (self.current_table == remembered_table)):
                    self.table_selected = str(self.current_table)
            else:
                self.current_table = ""
            return
        self.combo_table.blockSignals(True)
        try:
            self.combo_table.clear()
            self.combo_table.addItems(tables)
            self.combo_table.setEnabled(bool(tables))
            if tables:
                self.combo_table.setCurrentText(target)
                self.current_table = self.combo_table.currentText() or self.current_table
                if self.current_table and ((not remembered_table) or (self.current_table == remembered_table)):
                    self.table_selected = str(self.current_table)
            else:
                self.current_table = ""
        finally:
            self.combo_table.blockSignals(False)

    def _on_display_opts_changed(self, *args):
        """Sync dock controls -> attributes and rebuild plots.

        Важно: метод не должен падать, иначе GUI станет 'ломким'.
        """
        try:
            if hasattr(self, 'combo_dist_unit'):
                self.dist_unit = str(self.combo_dist_unit.currentText() or 'mm')
            if hasattr(self, 'combo_angle_unit'):
                self.angle_unit = str(self.combo_angle_unit.currentText() or 'deg')
            if hasattr(self, 'chk_zero_baseline'):
                self.zero_baseline = bool(self.chk_zero_baseline.isChecked())
            if hasattr(self, 'spin_baseline_s'):
                self.baseline_window_s = float(self.spin_baseline_s.value())
            if hasattr(self, 'chk_lock_y'):
                self.lock_y = bool(self.chk_lock_y.isChecked())
            if hasattr(self, 'chk_lock_y_unit'):
                self.lock_y_by_unit = bool(self.chk_lock_y_unit.isChecked())
            if hasattr(self, 'chk_sym_y'):
                self.sym_y = bool(self.chk_sym_y.isChecked())
        except Exception:
            # never crash on UI glue
            pass
        self._rebuild_plots()
        self._schedule_run_metrics_rebuild(delay_ms=80)
        self._schedule_static_stroke_rebuild(delay_ms=80)

    def _refresh_signal_list(self, preferred_selected: Optional[Sequence[str]] = None) -> List[str]:
        try:
            prev_selected = [str(x) for x in (preferred_selected if preferred_selected is not None else self._selected_signals())]
        except Exception:
            prev_selected = []
        explicit_signals = bool(getattr(self, '_signals_selection_explicit', False))
        remembered_selected = [str(x) for x in (getattr(self, 'signals_selected', []) or [])]
        if explicit_signals:
            if remembered_selected:
                prev_selected = list(remembered_selected)
            elif not prev_selected:
                prev_selected = []
        try:
            current_item = self.list_signals.currentItem() if hasattr(self, "list_signals") else None
            prev_current = str(current_item.text()) if current_item is not None else ""
        except Exception:
            prev_current = ""

        runs = self._selected_runs()
        if not runs:
            self.available_signals = []
            if not explicit_signals:
                self.signals_selected = []
            try:
                self.list_signals.blockSignals(True)
                self.list_signals.clear()
            finally:
                try:
                    self.list_signals.blockSignals(False)
                except Exception:
                    pass
            try:
                self.list_signals.setEnabled(False)
            except Exception:
                pass
            try:
                self.combo_nav_signal.blockSignals(True)
                self.combo_nav_signal.clear()
            finally:
                try:
                    self.combo_nav_signal.blockSignals(False)
                except Exception:
                    pass
            try:
                self.combo_nav_signal.setEnabled(False)
            except Exception:
                pass
            try:
                self._refresh_run_metrics_signal_combo()
            except Exception:
                pass
            return []
        self.available_signals = self._current_context_signal_names(apply_filter=True)

        if explicit_signals:
            kept_selected = [sig for sig in prev_selected if sig in self.available_signals]
        else:
            kept_selected = [sig for sig in self._default_signal_names() if sig in self.available_signals]
        try:
            self.list_signals.blockSignals(True)
            self.list_signals.clear()
            for s in self.available_signals:
                it = QtWidgets.QListWidgetItem(s)
                self.list_signals.addItem(it)
                if s in kept_selected:
                    it.setSelected(True)
            if explicit_signals and prev_current and prev_current in self.available_signals:
                self._set_current_list_item_by_text(self.list_signals, prev_current)
            elif kept_selected:
                self._set_current_list_item_by_text(self.list_signals, kept_selected[0])
        finally:
            try:
                self.list_signals.blockSignals(False)
            except Exception:
                pass
        try:
            self.list_signals.setEnabled(bool(self.available_signals))
        except Exception:
            pass

        # navigator signals (keep selection if possible)
        try:
            cur = self.combo_nav_signal.currentText() if hasattr(self, 'combo_nav_signal') else ''
        except Exception:
            cur = ''
        remembered_nav = str(getattr(self, 'navigator_signal_selected', '') or '').strip()
        remembered_nav_available = bool(remembered_nav) and self._signal_exists_in_current_context(remembered_nav)
        nav_target = str(remembered_nav if remembered_nav_available else (cur or remembered_nav or '')).strip()
        nav_options = list(self.available_signals[: min(200, len(self.available_signals))])
        if nav_target and nav_target not in nav_options and self._signal_exists_in_current_context(nav_target):
            nav_options = [str(nav_target)] + nav_options
        try:
            self.combo_nav_signal.blockSignals(True)
            self.combo_nav_signal.clear()
            self.combo_nav_signal.addItems(nav_options)
            if nav_target:
                self.combo_nav_signal.setCurrentText(nav_target)
        finally:
            try:
                self.combo_nav_signal.blockSignals(False)
            except Exception:
                pass
        try:
            self.combo_nav_signal.setEnabled(bool(nav_options))
        except Exception:
            pass
        try:
            current_nav = str(self.combo_nav_signal.currentText() or '').strip()
            if current_nav and (not remembered_nav or remembered_nav_available or current_nav == remembered_nav):
                self.navigator_signal_selected = current_nav
        except Exception:
            pass
        try:
            self._refresh_run_metrics_signal_combo()
        except Exception:
            pass
        try:
            picked = self._selected_signals()
            if picked:
                if explicit_signals and remembered_selected:
                    self.signals_selected = list(remembered_selected)
                else:
                    self.signals_selected = list(picked)
            elif not explicit_signals:
                self.signals_selected = []
            elif remembered_selected:
                self.signals_selected = list(remembered_selected)
            return picked
        except Exception:
            if explicit_signals and remembered_selected:
                self.signals_selected = list(remembered_selected)
            elif kept_selected:
                self.signals_selected = list(kept_selected)
            elif not explicit_signals:
                self.signals_selected = []
            return kept_selected

    def _on_signal_filter_changed(self, _txt: str) -> None:
        kept_selected = self._refresh_signal_list()
        if (not kept_selected) and self.available_signals and not bool(getattr(self, '_signals_selection_explicit', False)):
            self._select_default_signals()
        self._rebuild_plots()
        self._update_workspace_status()

    def _on_navigator_signal_changed(self, _index: int) -> None:
        try:
            self.navigator_signal_selected = str(self.combo_nav_signal.currentText() or '').strip()
        except Exception:
            self.navigator_signal_selected = ""
        self._rebuild_plots()

    def _on_signal_selection_changed(self) -> None:
        self._signals_selection_explicit = True
        try:
            self.signals_selected = self._selected_signals()
        except Exception:
            self.signals_selected = []
        self._rebuild_plots()
        self._update_workspace_status()

    def _on_run_selection_changed(self):
        """Runs selection changed → refresh dependent UI then rebuild plots."""
        self._runs_selection_explicit = True
        try:
            self.runs_selected_paths = [
                self._normalized_run_path(getattr(run, 'path', Path('')))
                for run in self._selected_runs()
            ]
        except Exception:
            self.runs_selected_paths = []
        try:
            prev_signals = self._selected_signals()
        except Exception:
            prev_signals = []
        try:
            self._refresh_table_list()
        except Exception:
            pass
        try:
            self._refresh_reference_runs()
        except Exception:
            pass
        try:
            kept_selected = self._refresh_signal_list(prev_signals)
            if (not kept_selected) and self.available_signals and not bool(getattr(self, '_signals_selection_explicit', False)):
                self._select_default_signals()
        except Exception:
            pass
        try:
            self._refresh_event_list()
            self._refresh_events_table()
        except Exception:
            pass
        try:
            self._refresh_anim_diag_panel()
        except Exception:
            pass
        try:
            self._schedule_static_stroke_rebuild(delay_ms=10)
        except Exception:
            pass
        self._rebuild_plots()
        self._update_workspace_status()

    def _on_reference_run_changed(self, _i: int):
        try:
            self._remember_reference_run()
        except Exception:
            pass
        try:
            self._refresh_event_list()
        except Exception:
            pass
        try:
            self._refresh_events_table()
        except Exception:
            pass
        try:
            self._schedule_static_stroke_rebuild(delay_ms=10)
        except Exception:
            pass
        self._rebuild_plots()
        self._update_workspace_status()

    def _on_event_selection_changed(self, _item=None) -> None:
        try:
            self.events_selected = self._get_selected_event_signals()
            self._events_selection_explicit = True
        except Exception:
            self.events_selected = []
            self._events_selection_explicit = True
        try:
            self._refresh_events_table()
        except Exception:
            pass
        self._rebuild_plots()
        self._update_workspace_status()

    def _get_selected_event_signals(self) -> List[str]:
        out: List[str] = []
        lw = getattr(self, 'list_events', None)
        if lw is None:
            return out
        try:
            for i in range(lw.count()):
                it = lw.item(i)
                if it is None:
                    continue
                if it.checkState() == QtCore.Qt.Checked:
                    sig = it.data(QtCore.Qt.UserRole)
                    sig = str(sig) if sig is not None else str(it.text()).strip()
                    if "  [" in sig:
                        sig = sig.split("  [", 1)[0]
                    out.append(sig)
        except Exception:
            return out
        return out

    def _refresh_event_list(self):
        lw = getattr(self, 'list_events', None)
        if lw is None:
            return

        explicit_events = bool(getattr(self, '_events_selection_explicit', False))
        remembered_sel = [str(x) for x in (getattr(self, 'events_selected', []) or [])]
        prev_sel = set(self._get_selected_event_signals())
        preserve_empty = False
        if not prev_sel and explicit_events:
            prev_sel = set(remembered_sel)
            preserve_empty = not prev_sel

        counts: Dict[str, int] = {}
        ref_run = self._reference_run(self._selected_runs())
        df = getattr(ref_run, 'events', None) if ref_run is not None else None
        if isinstance(df, pd.DataFrame) and not df.empty:
            try:
                vc = df['signal'].astype(str).value_counts()
                for k, v in vc.items():
                    counts[str(k)] = int(v)
            except Exception:
                counts = {}

        lw.blockSignals(True)
        lw.clear()

        if not counts:
            if not explicit_events:
                self.events_selected = []
            lw.blockSignals(False)
            try:
                lw.setEnabled(False)
            except Exception:
                pass
            self._update_workspace_status()
            return

        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        names = [k for (k, _v) in items]
        if explicit_events:
            if remembered_sel:
                prev_sel = {name for name in remembered_sel if name in names}
            else:
                prev_sel = {name for name in prev_sel if name in names}
        else:
            prev_sel = set(self._default_event_names(names))

        for name, cnt in items:
            text = f"{name}  [{cnt}]"
            it = QtWidgets.QListWidgetItem(text)
            it.setData(QtCore.Qt.UserRole, name)
            it.setToolTip(name)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Checked if name in prev_sel else QtCore.Qt.Unchecked)
            lw.addItem(it)

        lw.blockSignals(False)
        try:
            lw.setEnabled(True)
        except Exception:
            pass
        if explicit_events:
            self.events_selected = list(remembered_sel)
        else:
            self.events_selected = [name for name in names if name in prev_sel]
        self._update_workspace_status()

    def _refresh_events_table(self):
        tbl = getattr(self, 'tbl_events', None)
        if tbl is None:
            return

        # baseline = selected reference run
        sel = self._selected_runs()
        ref_run = self._reference_run(sel)

        df = getattr(ref_run, 'events', None) if ref_run is not None else None
        pick_names = self._get_selected_event_signals()
        have_filter_items = bool(getattr(self, 'list_events', None) is not None and self.list_events.count() > 0)
        baseline_label = str(ref_run.label) if ref_run is not None else ""
        if not isinstance(df, pd.DataFrame) or df.empty:
            self._insight_events = {
                "baseline": baseline_label,
                "rows": 0,
                "source_rows": 0,
                "selected_signals": list(pick_names),
                "filter_items": int(self.list_events.count()) if have_filter_items and getattr(self, "list_events", None) is not None else 0,
                "no_signals_selected": bool(have_filter_items and not pick_names),
                "top_signal": "",
                "top_count": 0,
                "sample_signal": "",
                "sample_time_s": float("nan"),
                "table_count": 0,
            }
            try:
                tbl.setRowCount(0)
            except Exception:
                pass
            try:
                tbl.setEnabled(False)
            except Exception:
                pass
            try:
                self._clear_events_timeline_view(
                    "Timeline: no baseline events available in the current reference run."
                )
            except Exception:
                pass
            try:
                self._clear_events_compare_view(
                    "Mismatch vs ref: no baseline events available in the current reference run."
                )
            except Exception:
                pass
            try:
                self._clear_events_runs_view(
                    "Runs raster: no baseline events available in the current reference run."
                )
            except Exception:
                pass
            try:
                self.lbl_events_info.setText(
                    self._events_status_text(
                        baseline_label=str(ref_run.label) if ref_run is not None else "",
                        rows_count=0,
                        selected_signals=list(pick_names),
                        have_filter_items=have_filter_items,
                        no_signals_selected=bool(have_filter_items and not pick_names),
                    )
                )
            except Exception:
                pass
            self._update_workspace_status()
            return

        try:
            source_rows = int(len(df))
        except Exception:
            source_rows = 0
        try:
            source_table_count = int(pd.Series(df.get('table', pd.Series([], dtype=object))).astype(str).nunique())
        except Exception:
            source_table_count = 0
        pick = set(pick_names)
        if have_filter_items:
            if pick:
                try:
                    df = df[df['signal'].astype(str).isin([str(x) for x in pick])].copy()
                except Exception:
                    pass
            else:
                df = df.iloc[0:0].copy()

        try:
            df_compare = df.copy()
        except Exception:
            df_compare = pd.DataFrame()

        max_rows = 500
        if len(df) > max_rows:
            df = df.sort_values('t', kind='mergesort').head(max_rows).copy()
        else:
            df = df.copy()

        cols = ["t", "signal", "from", "to", "table"]
        for c in cols:
            if c not in df.columns:
                df.loc[:, c] = ""
        df = df.loc[:, cols].copy()

        sample_signal = ""
        sample_time_s = np.nan
        top_signal = ""
        top_count = 0
        try:
            if len(df):
                df_focus = df.sort_values('t', kind='mergesort') if 't' in df.columns else df
                first_row = df_focus.iloc[0]
                sample_signal = str(first_row.get("signal", "") or "")
                try:
                    sample_time_s = float(first_row.get("t", np.nan))
                except Exception:
                    sample_time_s = np.nan
                vc = df['signal'].astype(str).value_counts()
                if len(vc):
                    top_signal = str(vc.index[0])
                    top_count = int(vc.iloc[0])
        except Exception:
            sample_signal = ""
            sample_time_s = np.nan
            top_signal = ""
            top_count = 0

        self._insight_events = {
            "baseline": baseline_label,
            "rows": int(len(df)),
            "source_rows": int(source_rows),
            "selected_signals": [str(x) for x in pick_names],
            "filter_items": int(self.list_events.count()) if have_filter_items and getattr(self, "list_events", None) is not None else 0,
            "no_signals_selected": bool(have_filter_items and not pick_names),
            "top_signal": top_signal,
            "top_count": int(top_count),
            "sample_signal": sample_signal,
            "sample_time_s": float(sample_time_s) if np.isfinite(sample_time_s) else float("nan"),
            "table_count": int(source_table_count),
        }

        try:
            tbl.setSortingEnabled(False)
        except Exception:
            pass
        tbl.clearContents()
        tbl.setRowCount(int(len(df)))

        for i, row in enumerate(df.itertuples(index=False, name=None)):
            try:
                t = float(row[0])
            except Exception:
                t = np.nan
            s = str(row[1])
            v0 = row[2]
            v1 = row[3]
            tab = str(row[4])

            items = [
                QtWidgets.QTableWidgetItem("" if not np.isfinite(t) else f"{t:.6g}"),
                QtWidgets.QTableWidgetItem(s),
                QtWidgets.QTableWidgetItem(str(v0)),
                QtWidgets.QTableWidgetItem(str(v1)),
                QtWidgets.QTableWidgetItem(tab),
            ]
            for j, it in enumerate(items):
                it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                tbl.setItem(i, j, it)

        try:
            tbl.setSortingEnabled(True)
        except Exception:
            pass
        try:
            tbl.setEnabled(bool(len(df)))
        except Exception:
            pass
        try:
            self._rebuild_events_timeline_view(
                baseline_label=baseline_label,
                df_events=df,
                selected_signals=list(pick_names),
                no_signals_selected=bool(have_filter_items and not pick_names),
            )
        except Exception:
            self._clear_events_timeline_view(
                "Timeline: temporarily unavailable, but the Events table above remains valid."
            )
        try:
            self._rebuild_events_compare_view(
                baseline_label=baseline_label,
                baseline_events=df_compare,
                selected_signals=list(pick_names),
                no_signals_selected=bool(have_filter_items and not pick_names),
            )
        except Exception:
            self._clear_events_compare_view(
                "Mismatch vs ref is temporarily unavailable, but the baseline Events table remains valid."
            )
        try:
            self._rebuild_events_runs_view(
                selected_signals=list(pick_names),
                no_signals_selected=bool(have_filter_items and not pick_names),
            )
        except Exception:
            self._clear_events_runs_view(
                "Runs raster is temporarily unavailable, but the baseline Events views remain valid."
            )

        try:
            self.lbl_events_info.setText(
                self._events_status_text(
                    baseline_label=baseline_label,
                    rows_count=len(df),
                    selected_signals=list(pick_names),
                    have_filter_items=have_filter_items,
                    no_signals_selected=bool(have_filter_items and not pick_names),
                    sample_signal=sample_signal,
                    sample_time_s=sample_time_s,
                )
            )
        except Exception:
            pass
        self._update_workspace_status()

    def _default_event_names(self, names: Sequence[str]) -> List[str]:
        return list(names[: min(6, len(names))])

    def _default_signal_names(self) -> List[str]:
        prefs = [
            "крен_phi_рад",
            "тангаж_theta_рад",
            "давление_аккумулятор_Па",
            "давление_ресивер1_Па",
            "давление_ресивер2_Па",
            "давление_ресивер3_Па",
        ]
        want = [p for p in prefs if p in self.available_signals]
        if want:
            return want
        return list(self.available_signals[: min(6, len(self.available_signals))])

    def _select_default_signals(self):
        # pick a few meaningful defaults if present
        want = self._default_signal_names()

        # select in widget
        self._signals_selection_explicit = False
        self.list_signals.blockSignals(True)
        try:
            self.list_signals.clearSelection()
            for i in range(self.list_signals.count()):
                it = self.list_signals.item(i)
                if it.text() in want:
                    it.setSelected(True)
        finally:
            self.list_signals.blockSignals(False)
        try:
            self.signals_selected = self._selected_signals()
        except Exception:
            self.signals_selected = list(want)

    def _selected_signals(self) -> List[str]:
        idxs = [i.row() for i in self.list_signals.selectedIndexes()]
        return [self.available_signals[i] for i in idxs if 0 <= i < len(self.available_signals)]

    def _selected_plot_signals(self) -> List[str]:
        sigs = self._selected_signals()
        max_rows = int(self.spin_rows.value())
        return sigs[:max_rows]

    # ---------------- plotting ----------------
    def _clear_plots(self):
        self.glw.clear()
        self.plots = []
        self.vlines = []
        self.plot_signals = []
        self._navigator_plot = None
        self._navigator_region = None
        self._region = None
        self._event_overlays = []

    def _clear_playhead_state(self) -> None:
        try:
            self._update_time_slider_range(np.asarray([], dtype=float))
        except Exception:
            self._t_ref = np.asarray([], dtype=float)
        self._is_playing = False
        try:
            self._play_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "btn_play"):
                self.btn_play.blockSignals(True)
                self.btn_play.setChecked(False)
                self.btn_play.blockSignals(False)
        except Exception:
            try:
                if hasattr(self, "btn_play"):
                    self.btn_play.blockSignals(False)
            except Exception:
                pass
        try:
            self.lbl_readout.setText("x: –")
        except Exception:
            pass

    def _get_xy_from_table(
        self,
        run: Run,
        sig: str,
        *,
        table_name: Optional[str] = None,
        apply_zero_baseline: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, str]:
        table_key = str(table_name or getattr(self, "current_table", "") or "").strip()
        if not table_key:
            return np.asarray([]), np.asarray([]), ""
        df = run.tables.get(table_key)
        if df is None or df.empty or sig not in df.columns:
            return np.asarray([]), np.asarray([]), ""
        tcol = detect_time_col(df)

        # extract_time_vector() compatibility:
        # - some builds expose extract_time_vector(df)
        # - others expose extract_time_vector(df, time_col=None)
        try:
            x = extract_time_vector(df, tcol)
        except TypeError:
            x = extract_time_vector(df)

        y = np.asarray(df[sig], dtype=float)
        # _infer_unit_and_transform() compatibility:
        # - legacy: (unit, transform, aux)
        # - current: (unit, transform)
        unit = ""
        tr = None
        try:
            res = _infer_unit_and_transform(
                sig,
                P_ATM=float(getattr(self, "P_ATM", 100000.0)),
                BAR_PA=float(getattr(self, "BAR_PA", 100000.0)),
                ATM_PA=float(getattr(self, "ATM_PA", 100000.0)),
                dist_unit=str(getattr(self, "dist_unit", "mm")),
                angle_unit=str(getattr(self, "angle_unit", "deg")),
            )
            if isinstance(res, (tuple, list)) and len(res) >= 2:
                unit = str(res[0] or "")
                tr = res[1]
        except Exception:
            unit = ""
            tr = None

        if callable(tr):
            try:
                y = np.asarray(tr(y), dtype=float)
            except Exception:
                pass

        # Zero-baseline (display-only) for displacement/angle-like units
        try:
            if apply_zero_baseline and bool(getattr(self, "zero_baseline", False)):
                u0 = (unit or "").lower()
                is_pos_like = u0 in ("m", "mm", "deg", "rad")
                if is_pos_like and y.size:
                    w = float(getattr(self, "baseline_window_s", 0.0) or 0.0)
                    if w > 0 and x.size == y.size:
                        x0 = float(x[0]) if x.size else 0.0
                        mask = (x <= x0 + w)
                        if bool(getattr(mask, 'any', lambda: False)()):
                            y0 = float(np.nanmedian(y[mask]))
                        else:
                            y0 = float(y[0])
                    else:
                        y0 = float(y[0])
                    # subtract if not NaN
                    if y0 == y0:
                        y = y - y0
        except Exception:
            pass

        return x, y, unit

    def _get_xy(self, run: Run, sig: str) -> Tuple[np.ndarray, np.ndarray, str]:
        return self._get_xy_from_table(run, sig, table_name=str(getattr(self, "current_table", "") or ""), apply_zero_baseline=True)


    def _on_region_changed(self):
        if getattr(self, "_updating_region", False):
            return
        if not getattr(self, "_region", None) or not self.plots:
            return
        self._updating_region = True
        try:
            r0, r1 = self._region.getRegion()
            if np.isfinite(float(r0)) and np.isfinite(float(r1)):
                self.navigator_region_selected = (float(r0), float(r1))
            for p in self.plots:
                p.setXRange(r0, r1, padding=0)
        finally:
            self._updating_region = False
        try:
            if hasattr(self, "chk_dist_use_view") and self.chk_dist_use_view.isChecked():
                self._schedule_run_metrics_rebuild(delay_ms=120)
        except Exception:
            pass

    def _on_main_xrange_changed(self, *args, **kwargs):
        """Keep region in sync with user zoom/pan on the main plot.

        NOTE: pyqtgraph's ViewBox.sigXRangeChanged payload is not stable across
        Qt bindings / versions. In practice we've seen it deliver:
          - (viewbox, (xmin, xmax))
          - (viewbox, [[xmin, xmax], [ymin, ymax]])
          - (viewbox, xmin)  # PySide6/SignalProxy quirks

        To be robust we do **not** trust the emitted payload and instead query
        the actual ViewBox.viewRange().
        """
        if getattr(self, "_updating_region", False):
            return

        # Try to locate a ViewBox from the signal args.
        vb = None
        if args:
            a0 = args[0]
            if hasattr(a0, "viewRange"):
                vb = a0
        if vb is None:
            try:
                if getattr(self, "plots", None):
                    vb = self.plots[0].getViewBox()
            except Exception:
                vb = None
        if vb is None:
            return

        if getattr(self, "_region", None):
            self._updating_region = True
            try:
                vr = vb.viewRange()
                # viewRange() -> [[xmin, xmax], [ymin, ymax]]
                if not (isinstance(vr, (list, tuple)) and len(vr) >= 1):
                    return
                xr = vr[0]
                if not (isinstance(xr, (list, tuple)) and len(xr) >= 2):
                    return
                r0, r1 = float(xr[0]), float(xr[1])
                if not (np.isfinite(r0) and np.isfinite(r1)):
                    return
                self.navigator_region_selected = (r0, r1)
                self._region.setRegion((r0, r1))
            finally:
                self._updating_region = False
        try:
            if hasattr(self, "chk_dist_use_view") and self.chk_dist_use_view.isChecked():
                self._schedule_run_metrics_rebuild(delay_ms=120)
        except Exception:
            pass

    def _rebuild_plots(self):
        """Build small-multiples plots for selected signals and runs.

        Key goals (Диаграммы):
        - Быстрое сравнение серий (наложение / Δ к эталону)
        - Единые шкалы (lock-Y) для корректного визуального сопоставления
        - Нулевая базовая позиция (display-only) для перемещений/углов
        """

        runs = self._selected_runs()
        sigs = self._selected_plot_signals()
        prev_region: Optional[Tuple[float, float]] = None
        try:
            region = getattr(self, "_region", None)
            if region is not None:
                rr = region.getRegion()
                if isinstance(rr, (list, tuple)) and len(rr) >= 2:
                    r0 = float(rr[0])
                    r1 = float(rr[1])
                    if np.isfinite(r0) and np.isfinite(r1) and r1 > r0:
                        prev_region = (r0, r1)
                        self.navigator_region_selected = prev_region
        except Exception:
            prev_region = None
        if prev_region is None and getattr(self, "plots", None):
            try:
                xr = self.plots[0].getViewBox().viewRange()[0]
                if isinstance(xr, (list, tuple)) and len(xr) >= 2:
                    r0 = float(xr[0])
                    r1 = float(xr[1])
                    if np.isfinite(r0) and np.isfinite(r1) and r1 > r0:
                        prev_region = (r0, r1)
                        self.navigator_region_selected = prev_region
            except Exception:
                prev_region = None
        if prev_region is None:
            prev_region = getattr(self, "navigator_region_selected", None)
        if not runs or not sigs:
            self._clear_plots()
            self._clear_playhead_state()
            try:
                self.lbl_trust.setVisible(False)
            except Exception:
                pass
            try:
                self._clear_heatmap_view("Выберите хотя бы один прогон и один сигнал.")
            except Exception:
                pass
            try:
                self._clear_inflheat_view("Выберите хотя бы один прогон и один сигнал.")
            except Exception:
                pass
            try:
                note = "Выберите хотя бы один прогон." if not runs else "Выберите хотя бы один сигнал (Signals)."
                self._clear_influence_view(note)
            except Exception:
                pass
            try:
                self._rebuild_qa(force=True)
            except Exception:
                pass
            try:
                self._schedule_run_metrics_rebuild(delay_ms=10)
            except Exception:
                pass
            try:
                self._schedule_open_timeline_rebuild(delay_ms=10)
            except Exception:
                pass
            try:
                self._schedule_static_stroke_rebuild(delay_ms=10)
            except Exception:
                pass
            try:
                self._schedule_geometry_acceptance_rebuild(delay_ms=10)
            except Exception:
                pass
            return

        self._clear_plots()
        self.plot_signals = []

        # trust banner (dt/NaN/non‑monotonic)
        try:
            self._update_trust_banner(runs, list(sigs)[:24])
        except Exception:
            pass

        # reference for delta / navigator / events baseline
        runs_plot = self._ordered_runs_for_reference(runs)
        ref = runs_plot[0]
        do_delta = bool(getattr(self, "chk_delta", None) and self.chk_delta.isChecked()) and len(runs) >= 2

        # discrete event markers (baseline = ref)
        event_times: List[float] = []
        try:
            if getattr(self, 'chk_events', None) is not None and self.chk_events.isChecked():
                pick = set(self._get_selected_event_signals())
                have_filter_items = bool(getattr(self, 'list_events', None) is not None and self.list_events.count() > 0)
                df_ev = getattr(ref, 'events', None)
                if isinstance(df_ev, pd.DataFrame) and not df_ev.empty:
                    if have_filter_items:
                        if pick:
                            df_ev = df_ev[df_ev['signal'].astype(str).isin([str(x) for x in pick])]
                        else:
                            df_ev = df_ev.iloc[0:0].copy()
                    elif pick:
                        df_ev = df_ev[df_ev['signal'].astype(str).isin([str(x) for x in pick])]
                    times = pd.to_numeric(df_ev.get('t', pd.Series([], dtype=float)), errors='coerce').dropna().tolist()
                    times = [float(x) for x in times if np.isfinite(float(x))]
                    times.sort()
                    lim = int(getattr(self, 'spin_events_max', None).value() if getattr(self, 'spin_events_max', None) is not None else 60)
                    if lim <= 0:
                        event_times = []
                    elif len(times) <= lim:
                        event_times = times
                    else:
                        idx = np.linspace(0, len(times) - 1, lim).astype(int)
                        event_times = [times[i] for i in idx.tolist()]
        except Exception:
            event_times = []

        # keep overlays alive
        self._event_overlays: List[VerticalLinesOverlay] = []

        # update time slider reference (reference run, first signal)
        try:
            x_ref0, _y0, _u0 = self._get_xy(ref, sigs[0])
            self._update_time_slider_range(x_ref0)
        except Exception:
            self._update_time_slider_range(np.asarray([], dtype=float))

        # --- Navigator (overview + detail) ---
        use_nav = bool(getattr(self, "chk_nav", None) and self.chk_nav.isChecked())
        nav_sig = None
        if getattr(self, "combo_nav_signal", None):
            try:
                nav_sig = self.combo_nav_signal.currentText() or None
            except Exception:
                nav_sig = None
        if use_nav and not nav_sig:
            nav_sig = sigs[0]

        first_plot: Optional[pg.PlotItem] = None

        row0 = 0
        if use_nav and nav_sig:
            nav_plot: pg.PlotItem = self.glw.addPlot(row=0, col=0)
            nav_plot.setMaximumHeight(160)
            nav_plot.showGrid(x=True, y=True, alpha=0.25)
            nav_plot.setLabel("left", f"Navigator: {nav_sig}")
            x_nav, y_nav, _unit_nav = self._get_xy(ref, nav_sig)
            if x_nav.size:
                nav_plot.plot(x_nav, y_nav, pen=pg.mkPen((60, 60, 60), width=1))

                # discrete event markers (baseline)
                if event_times:
                    try:
                        ov = VerticalLinesOverlay(nav_plot, event_times)
                        nav_plot.addItem(ov)
                        self._event_overlays.append(ov)
                    except Exception:
                        pass

                # region defaults: full range, but keep a reasonable initial span
                x0 = float(x_nav[0])
                x1 = float(x_nav[-1])
                span = max(1e-6, (x1 - x0))
                r0 = x0 + 0.05 * span
                r1 = x0 + 0.25 * span
                try:
                    if prev_region is not None:
                        pr0, pr1 = sorted((float(prev_region[0]), float(prev_region[1])))
                        lo = min(x0, x1)
                        hi = max(x0, x1)
                        pr0 = float(np.clip(pr0, lo, hi))
                        pr1 = float(np.clip(pr1, lo, hi))
                        if np.isfinite(pr0) and np.isfinite(pr1) and (pr1 - pr0) > 1e-9:
                            r0, r1 = pr0, pr1
                except Exception:
                    pass
                self._region = pg.LinearRegionItem(values=(r0, r1), orientation="vertical")
                self._region.sigRegionChanged.connect(self._on_region_changed)
                nav_plot.addItem(self._region)
            self._navigator_plot = nav_plot
            row0 = 1

        # --- Main plots (small multiples) ---
        sig_ranges: dict[str, tuple[str, float, float]] = {}

        for i, sig in enumerate(sigs):
            p: pg.PlotItem = self.glw.addPlot(row=row0 + i, col=0)
            p.showGrid(x=True, y=True, alpha=0.25)
            p.setLabel("left", sig)
            p.setDownsampling(auto=True, mode="peak")
            p.setClipToView(True)

            unit = ""
            y_for_range = []

            # reference
            x_ref, y_ref, unit = self._get_xy(ref, sig)
            if x_ref.size and y_ref.size:
                if do_delta:
                    # In Δ mode we want the reference to be a 0-line.
                    y0 = np.zeros_like(y_ref)
                    pen0 = pg.mkPen((0, 0, 0, 90), width=1)
                    p.plot(x_ref, y0, pen=pen0, name=f"0 ({ref.label})")
                    y_for_range.append(y0)
                else:
                    pen_ref = pg.mkPen(pg.intColor(0), width=1)
                    p.plot(x_ref, y_ref, pen=pen_ref, name=ref.label)
                    y_for_range.append(y_ref)

            # other runs
            for ri, r in enumerate(runs_plot[1:], start=1):
                x, y, unit2 = self._get_xy(r, sig)
                if not x.size or not y.size:
                    continue

                if do_delta and x_ref.size and y_ref.size:
                    try:
                        y_i = np.interp(x_ref, x, y, left=np.nan, right=np.nan)
                        y_d = y_i - y_ref
                        pen_d = pg.mkPen(pg.intColor(ri), width=1, style=QtCore.Qt.DashLine)
                        p.plot(x_ref, y_d, pen=pen_d, name=f"Δ {r.label}-{ref.label}")
                        y_for_range.append(y_d)
                    except Exception:
                        # fallback: plot raw
                        pen_r = pg.mkPen(pg.intColor(ri), width=1)
                        p.plot(x, y, pen=pen_r, name=r.label)
                        y_for_range.append(y)
                else:
                    pen_r = pg.mkPen(pg.intColor(ri), width=1)
                    p.plot(x, y, pen=pen_r, name=r.label)
                    y_for_range.append(y)

                if unit2:
                    unit = unit2

            if unit:
                p.setLabel("right", unit)

            if first_plot is None:
                first_plot = p
            else:
                p.setXLink(first_plot)

            # crosshair / playhead line
            v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen((0, 0, 0, 80)))
            p.addItem(v, ignoreBounds=True)
            self.vlines.append(v)

            # discrete event markers (baseline)
            if event_times:
                try:
                    ov = VerticalLinesOverlay(p, event_times)
                    p.addItem(ov, ignoreBounds=True)
                    self._event_overlays.append(ov)
                except Exception:
                    pass
            self.plots.append(p)
            self.plot_signals.append(sig)

            # range estimate for this signal (after transforms + baseline + delta)
            try:
                arrs = []
                for yy in y_for_range:
                    if yy is None:
                        continue
                    yv = np.asarray(yy, dtype=float).ravel()
                    yv = yv[np.isfinite(yv)]
                    if yv.size:
                        arrs.append(yv)
                if arrs:
                    ycat = np.concatenate(arrs)
                    ymin = float(np.nanmin(ycat))
                    ymax = float(np.nanmax(ycat))
                else:
                    ymin = float('nan'); ymax = float('nan')
                sig_ranges[str(sig)] = (str(unit or ""), ymin, ymax)
            except Exception:
                sig_ranges[str(sig)] = (str(unit or ""), float('nan'), float('nan'))

        # keep region synced with main x-range (first plot)
        if first_plot is not None:
            try:
                first_plot.getViewBox().sigXRangeChanged.connect(self._on_main_xrange_changed)
            except Exception:
                pass
            if use_nav and getattr(self, "_region", None):
                try:
                    self._on_region_changed()
                except Exception:
                    pass

        # add legend to first plot only
        try:
            if self.plots:
                self.plots[0].addLegend(offset=(10, 10))
        except Exception:
            pass

        # --- Apply Y ranges (lock scales) ---
        try:
            want_lock = bool(getattr(self, 'lock_y', False)) or bool(getattr(self, 'lock_y_by_unit', False))
            if want_lock and self.plots:
                # build per-unit ranges if requested
                unit_ranges: dict[str, tuple[float, float]] = {}
                if bool(getattr(self, 'lock_y_by_unit', False)):
                    for _sig, (u, ymin, ymax) in sig_ranges.items():
                        if not (np.isfinite(ymin) and np.isfinite(ymax)):
                            continue
                        key = u or _sig
                        if key not in unit_ranges:
                            unit_ranges[key] = (float(ymin), float(ymax))
                        else:
                            lo, hi = unit_ranges[key]
                            unit_ranges[key] = (min(lo, float(ymin)), max(hi, float(ymax)))

                for p, sig in zip(self.plots, self.plot_signals):
                    u, ymin, ymax = sig_ranges.get(str(sig), ("", float('nan'), float('nan')))
                    if bool(getattr(self, 'lock_y_by_unit', False)):
                        key = (u or str(sig))
                        ymin, ymax = unit_ranges.get(key, (ymin, ymax))

                    if not (np.isfinite(ymin) and np.isfinite(ymax)):
                        continue

                    ymin = float(ymin); ymax = float(ymax)

                    # symmetric around 0 (useful for Δ and baseline-zeroed coords)
                    if bool(getattr(self, 'sym_y', False)):
                        m = max(abs(ymin), abs(ymax))
                        if not np.isfinite(m) or m <= 0:
                            m = 1.0
                        ymin, ymax = -m, m

                    # avoid flat range
                    if ymin == ymax:
                        d = max(1e-9, abs(ymin) * 0.05)
                        ymin -= d
                        ymax += d

                    span = max(1e-9, (ymax - ymin))
                    pad = 0.02 * span
                    try:
                        p.setYRange(ymin - pad, ymax + pad, padding=0)
                    except Exception:
                        pass
        except Exception:
            # never crash compare viewer on range logic
            pass

        # update Δ(t) heatmap
        try:
            self._rebuild_heatmap()
            self._schedule_peak_heatmap_rebuild(delay_ms=10)
            self._schedule_influence_rebuild()
            self._schedule_inflheat_rebuild()
            # QA (cached): should not add noticeable cost
            self._rebuild_qa()
        except Exception:
            pass

        # events table is lightweight; keep it in sync
        try:
            self._refresh_events_table()
        except Exception:
            pass

        # multivariate explorer: keep in sync (debounced)
        try:
            self._schedule_multivar_update()
        except Exception:
            pass

        try:
            self._sync_playhead_visuals()
        except Exception:
            pass
        try:
            self._schedule_run_metrics_rebuild(delay_ms=10)
        except Exception:
            pass
        try:
            self._schedule_open_timeline_rebuild(delay_ms=10)
        except Exception:
            pass
        try:
            self._schedule_static_stroke_rebuild(delay_ms=10)
        except Exception:
            pass
        try:
            self._schedule_geometry_acceptance_rebuild(delay_ms=10)
        except Exception:
            pass

        self.glw.nextRow()
        self._update_workspace_status()
    # ---------------- playhead ----------------
    def _update_time_slider_range(self, x_ref: np.ndarray) -> None:
        try:
            x_ref = np.asarray(x_ref, dtype=float)
            x_ref = x_ref[np.isfinite(x_ref)]
        except Exception:
            x_ref = np.asarray([], dtype=float)
        self._t_ref = x_ref
        if not hasattr(self, "slider_time"):
            return
        self._time_slider_updating = True
        try:
            n = int(len(self._t_ref))
            self.slider_time.setRange(0, max(0, n - 1))
            if n > 0:
                target_idx = min(self.slider_time.value(), n - 1)
                remembered_time = getattr(self, 'playhead_time_selected', None)
                remembered_idx = getattr(self, 'playhead_index_selected', None)
                try:
                    if remembered_time is not None and np.isfinite(float(remembered_time)):
                        target_idx = int(np.argmin(np.abs(np.asarray(self._t_ref, dtype=float) - float(remembered_time))))
                    elif remembered_idx is not None:
                        target_idx = int(remembered_idx)
                except Exception:
                    pass
                target_idx = max(0, min(int(target_idx), n - 1))
                self.slider_time.setValue(target_idx)
            else:
                self.slider_time.setValue(0)
            self.slider_time.setEnabled(bool(n))
            if hasattr(self, "btn_play"):
                self.btn_play.setEnabled(bool(n))
            if hasattr(self, "spin_fps"):
                self.spin_fps.setEnabled(bool(n))
        finally:
            self._time_slider_updating = False

    def _sync_playhead_visuals(self) -> Optional[Tuple[int, float]]:
        if self._t_ref.size == 0:
            try:
                self.lbl_readout.setText("x: –")
            except Exception:
                pass
            return None
        idx = 0
        if hasattr(self, "slider_time"):
            try:
                idx = int(self.slider_time.value())
            except Exception:
                idx = 0
        idx = max(0, min(idx, int(len(self._t_ref) - 1)))
        x = float(self._t_ref[idx])
        self.playhead_time_selected = float(x)
        self.playhead_index_selected = int(idx)
        for v in self.vlines:
            try:
                v.setPos(x)
            except Exception:
                pass
        try:
            self.lbl_readout.setText(f"x={x:.3f} (idx={idx})")
        except Exception:
            pass
        try:
            if getattr(self, '_heat_enabled', False):
                self._sync_heatmap_to_time(float(x))
        except Exception:
            pass
        try:
            if getattr(self, "_open_timeline_cache", None):
                self._sync_open_timeline_to_time(float(x))
        except Exception:
            pass
        try:
            if getattr(self, "_events_timeline_cache", None):
                self._sync_events_timeline_to_time(float(x))
        except Exception:
            pass
        try:
            if getattr(self, "_events_runs_cache", None):
                self._sync_events_runs_to_time(float(x))
        except Exception:
            pass
        try:
            if getattr(self, "_inflheat", None) is not None:
                self._sync_inflheat_to_time(float(x))
        except Exception:
            pass
        return idx, x

    def _ensure_playhead_visible_in_view(self) -> Optional[Tuple[int, float]]:
        synced = self._sync_playhead_visuals()
        if synced is None or not getattr(self, "plots", None):
            return synced
        idx, x = synced
        try:
            vb = self.plots[0].getViewBox()
            xr = vb.viewRange()[0]
            xmin, xmax = float(xr[0]), float(xr[1])
            if (not getattr(self, "_region", None)) and np.isfinite(xmin) and np.isfinite(xmax) and xmax > xmin:
                remembered_region = getattr(self, "navigator_region_selected", None)
                keep_remembered = False
                try:
                    if isinstance(remembered_region, (list, tuple)) and len(remembered_region) >= 2:
                        rr0, rr1 = sorted((float(remembered_region[0]), float(remembered_region[1])))
                        keep_remembered = np.isfinite(rr0) and np.isfinite(rr1) and rr0 <= x <= rr1
                except Exception:
                    keep_remembered = False
                if not keep_remembered:
                    self.navigator_region_selected = (float(xmin), float(xmax))
            if xmin <= x <= xmax:
                return synced
            span = max(1e-6, float(xmax - xmin))
            t0 = float(np.nanmin(self._t_ref))
            t1 = float(np.nanmax(self._t_ref))
            lo = min(t0, t1)
            hi = max(t0, t1)
            new_min = float(x - 0.5 * span)
            new_max = float(x + 0.5 * span)
            if new_min < lo:
                new_max += (lo - new_min)
                new_min = lo
            if new_max > hi:
                new_min -= (new_max - hi)
                new_max = hi
            new_min = max(lo, new_min)
            new_max = min(hi, new_max)
            if not (np.isfinite(new_min) and np.isfinite(new_max)):
                return synced
            if new_max <= new_min:
                new_min = max(lo, min(x, hi) - 0.5 * span)
                new_max = min(hi, new_min + span)
            vb.setXRange(new_min, new_max, padding=0)
            if np.isfinite(new_min) and np.isfinite(new_max) and new_max > new_min:
                self.navigator_region_selected = (float(new_min), float(new_max))
        except Exception:
            pass
        return synced

    def _on_time_slider(self, idx: int) -> None:
        if getattr(self, "_time_slider_updating", False):
            return
        synced = self._sync_playhead_visuals()
        if synced is None:
            return
        i, x = synced
        # keep x visible (pan) on main plot
        try:
            if self.plots:
                vb = self.plots[0].getViewBox()
                (xmin, xmax) = vb.viewRange()[0]
                if not (xmin <= x <= xmax):
                    span = max(1e-6, float(xmax - xmin))
                    vb.setXRange(x - 0.5 * span, x + 0.5 * span, padding=0)
        except Exception:
            pass

        # sync Influence(t) to playhead (debounced)
        try:
            self._schedule_influence_rebuild()
        except Exception:
            pass
        try:
            self._schedule_run_metrics_rebuild(delay_ms=80)
        except Exception:
            pass

        # multivariate: update pebbles in "active@t" mode (debounced)
        try:
            if hasattr(self, "dock_multivar") and (self.dock_multivar is not None) and self.dock_multivar.isVisible():
                if hasattr(self, "chk_mv_pebbles") and self.chk_mv_pebbles.isChecked():
                    if hasattr(self, "combo_mv_peb_mode") and str(self.combo_mv_peb_mode.currentText()) == "active@t":
                        self._schedule_multivar_update(force=False)
        except Exception:
            pass

    def _toggle_play(self, on: bool) -> None:
        if bool(on) and self._t_ref.size == 0:
            self._is_playing = False
            try:
                if hasattr(self, "btn_play"):
                    self.btn_play.blockSignals(True)
                    self.btn_play.setChecked(False)
                    self.btn_play.blockSignals(False)
            except Exception:
                try:
                    if hasattr(self, "btn_play"):
                        self.btn_play.blockSignals(False)
                except Exception:
                    pass
            return
        self._is_playing = bool(on)
        if not self._is_playing:
            try:
                self._play_timer.stop()
            except Exception:
                pass
            return
        fps = int(getattr(self, "spin_fps", None).value()) if hasattr(self, "spin_fps") else 24
        fps = max(1, min(60, fps))
        try:
            self._play_timer.start(int(1000 / fps))
        except Exception:
            pass

    def _on_fps_changed(self, _value: int) -> None:
        if not bool(getattr(self, "_is_playing", False)):
            return
        try:
            fps = int(self.spin_fps.value()) if hasattr(self, "spin_fps") else 24
        except Exception:
            fps = 24
        fps = max(1, min(60, int(fps)))
        try:
            self._play_timer.start(int(1000 / fps))
        except Exception:
            pass

    def _on_play_tick(self) -> None:
        if not hasattr(self, "slider_time"):
            return
        if self._t_ref.size == 0:
            return
        j = int(self.slider_time.value()) + 1
        if j >= int(len(self._t_ref)):
            j = 0
        self.slider_time.setValue(j)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        try:
            key = event.key()
        except Exception:
            return super().keyPressEvent(event)
        # Space: play/pause
        if key == QtCore.Qt.Key_Space and hasattr(self, "btn_play") and self.btn_play.isEnabled():
            self.btn_play.setChecked(not self.btn_play.isChecked())
            event.accept(); return
        # Left/Right: step
        if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right) and hasattr(self, "slider_time") and self.slider_time.isEnabled():
            step = -1 if key == QtCore.Qt.Key_Left else 1
            self.slider_time.setValue(max(0, min(self.slider_time.maximum(), self.slider_time.value() + step)))
            event.accept(); return
        return super().keyPressEvent(event)

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if not self.plots:
            return
        # choose plot under mouse if possible
        p0 = None
        for p in self.plots:
            if p.sceneBoundingRect().contains(pos):
                p0 = p
                break
        if p0 is None:
            p0 = self.plots[0]

        mouse_point = p0.vb.mapSceneToView(pos)
        x = float(mouse_point.x())
        for v in self.vlines:
            v.setPos(x)

        # compute quick readout for hovered signal
        sigs = self._selected_plot_signals()
        runs = self._selected_runs()
        if not sigs or not runs:
            self.lbl_readout.setText(f"x: {x:.3f}")
            return
        sig0 = sigs[0]
        try:
            if p0 in self.plots:
                sig0 = self.plot_signals[self.plots.index(p0)]
        except Exception:
            pass
        parts = [f"x={x:.3f}", f"sig={sig0}"]
        for r in runs[:4]:
            xx, yy, _unit = self._get_xy(r, sig0)
            if xx.size < 2:
                continue
            try:
                v = float(np.interp(x, xx, yy, left=np.nan, right=np.nan))
            except Exception:
                # nearest
                j = int(np.argmin(np.abs(xx - x)))
                v = float(yy[j]) if j < len(yy) else float("nan")
            parts.append(f"{r.label}: {v:.6g}")
        self.lbl_readout.setText(" | ".join(parts))

    # ---------------- actions ----------------
    def _iter_visible_plotly_export_widgets(self) -> List[QtWidgets.QWidget]:
        out: List[QtWidgets.QWidget] = []
        for attr in ("mv_view_splom", "mv_view_par", "mv_view_3d"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                if (not widget.isVisible()) or widget.isHidden():
                    continue
            except Exception:
                continue
            try:
                if widget.width() < 64 or widget.height() < 64:
                    continue
            except Exception:
                continue
            out.append(widget)
        return out

    def _overlay_plotly_static_exports(self, pixmap: QtGui.QPixmap) -> QtGui.QPixmap:
        if pixmap.isNull():
            return pixmap
        widgets = self._iter_visible_plotly_export_widgets()
        if not widgets:
            return pixmap

        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            for widget in widgets:
                render_static = getattr(widget, "render_static_qimage", None)
                if not callable(render_static):
                    continue
                try:
                    image = render_static(width=int(widget.width()), height=int(widget.height()), scale=1.5)
                except Exception:
                    image = None
                if image is None or image.isNull():
                    continue
                try:
                    origin = widget.mapTo(self, QtCore.QPoint(0, 0))
                    target = QtCore.QRect(origin, widget.size())
                except Exception:
                    continue
                try:
                    painter.fillRect(target, QtGui.QColor("#ffffff"))
                    painter.drawImage(target, image)
                    painter.setPen(QtGui.QPen(QtGui.QColor("#d6c8af"), 1))
                    painter.drawRect(target.adjusted(0, 0, -1, -1))
                except Exception:
                    continue
        finally:
            try:
                painter.end()
            except Exception:
                pass
        return pixmap

    def _save_workspace_png(self, path) -> Path:
        out = _absolute_fs_path(path)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            self.show()
        except Exception:
            pass
        try:
            self.repaint()
        except Exception:
            pass
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass
        pm = self.grab()
        if pm.isNull():
            raise RuntimeError("Qt returned an empty workspace snapshot")
        try:
            pm = self._overlay_plotly_static_exports(pm)
        except Exception:
            pass
        if not pm.save(str(out), "PNG"):
            raise RuntimeError("Qt failed to save PNG")
        return out

    def _export_workspace_snapshot_set(self, out_dir) -> List[Path]:
        out_root = _absolute_fs_path(out_dir)
        try:
            out_root.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        saved_state = None
        saved_geometry = None
        saved_focus_mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        try:
            saved_state = self.saveState()
            saved_geometry = self.saveGeometry()
        except Exception:
            pass

        exports: List[Path] = []
        try:
            preset_specs = (
                ("compare_workspace_overview", "all"),
                ("compare_workspace_heatmaps", "heatmaps"),
                ("compare_workspace_multivariate", "multivariate"),
                ("compare_workspace_qa", "qa"),
            )
            for stem, mode in preset_specs:
                self._activate_workspace_focus_mode(mode)
                if mode == "multivariate":
                    try:
                        self._update_multivar_views()
                    except Exception:
                        pass
                try:
                    QtWidgets.QApplication.processEvents()
                except Exception:
                    pass
                filename = self._workspace_export_filename(stem)
                exports.append(self._save_workspace_png(out_root / filename))
        finally:
            restored = False
            try:
                if saved_geometry is not None:
                    self.restoreGeometry(saved_geometry)
                if saved_state is not None:
                    restored = bool(self.restoreState(saved_state))
            except Exception:
                restored = False
            if not restored:
                try:
                    self._apply_default_workspace_layout()
                except Exception:
                    pass
            else:
                self._workspace_focus_mode = saved_focus_mode
            try:
                self._update_workspace_status()
            except Exception:
                pass
            try:
                QtWidgets.QApplication.processEvents()
            except Exception:
                pass

        return exports

    def _export_png(self):
        default_name = self._workspace_export_filename("compare")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export PNG", default_name, "PNG Images (*.png)")
        if not path:
            return
        try:
            self._save_workspace_png(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", str(e))

    def _export_snapshot_set_dialog(self):
        base_dir = str(_absolute_fs_path(Path.cwd()))
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Export Workspace Snapshot Set",
            base_dir,
        )
        if not out_dir:
            return
        try:
            exports = self._export_workspace_snapshot_set(out_dir)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export snapshot set failed", str(e))
            return
        if exports:
            lines = "\n".join(str(p) for p in exports[:8])
            QtWidgets.QMessageBox.information(
                self,
                "Snapshot set exported",
                f"Saved {len(exports)} workspace snapshots.\n\n{lines}",
            )

    def _open_dialog(self):
        dlg = QtWidgets.QFileDialog(self)
        dlg.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        dlg.setNameFilter("NPZ files (*.npz)")
        if dlg.exec():
            files = [Path(s) for s in dlg.selectedFiles()]
            loaded = self._load_paths(files, replace=True)
            if loaded > 0:
                loaded_paths = [getattr(r, 'path', Path('')) for r in getattr(self, 'runs', [])]
                self._clear_pending_dataset_restore_if_mismatch(loaded_paths)
                self._apply_restore_after_load()
                if self._last_load_errors:
                    details = "\n".join(self._last_load_errors[:6])
                    tail = ""
                    if len(self._last_load_errors) > 6:
                        tail = f"\n... и ещё {len(self._last_load_errors) - 6}"
                    loaded_labels = ", ".join([str(r.label) for r in getattr(self, 'runs', [])[:6]])
                    if len(getattr(self, 'runs', [])) > 6:
                        loaded_labels += ", ..."
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Open NPZ warnings",
                        f"Загружено {loaded} NPZ, но часть файлов открыть не удалось.\n"
                        f"Открыты: {loaded_labels}\n\n{details}{tail}",
                    )
            elif self._last_load_errors:
                details = "\n".join(self._last_load_errors[:6])
                QtWidgets.QMessageBox.warning(
                    self,
                    "Open NPZ failed",
                    "Не удалось загрузить выбранные NPZ.\nТекущая сессия оставлена без изменений.\n\n"
                    + details,
                )


def _auto_find_npz(max_files: int = 6) -> List[Path]:
    """Best-effort auto-detection of latest NPZ runs.

    Goal: when user launches compare viewer without selecting files,
    it should open something useful automatically.

    Strategy:
    - include anim_latest / latest_simulation pointers from both workspace root
      and session-local workspaces under runs/ui_sessions/*;
    - scan exports/osc folders in repo root, package-local workspace, current
      working directory, and per-session workspaces (newest first).
    """
    max_files = int(max(1, max_files))

    this = Path(__file__).resolve()
    ui_dir = this.parent            # .../pneumo_solver_ui
    repo_root = ui_dir.parent       # project root

    root_candidates = [repo_root, ui_dir, Path.cwd()]
    root_candidates = [p.resolve() for p in root_candidates if p.exists()]

    out: List[Path] = []
    seen: set[str] = set()

    def _add(p: Path):
        p2 = _absolute_fs_path(p)
        s = _normalized_fs_path_key(p2)
        if s in seen:
            return
        if p2.exists() and p2.is_file() and p2.suffix.lower() == '.npz':
            seen.add(s)
            out.append(p2)

    candidate_dirs: list[Path] = []
    for base in root_candidates:
        candidate_dirs.extend([
            base / 'workspace' / 'osc',
            base / 'workspace' / 'exports',
            base / 'workspace' / 'osc_logs',
            base / 'osc_logs',
        ])
        for ws in iter_session_workspaces(base):
            candidate_dirs.extend([ws / 'osc', ws / 'exports', ws / 'osc_logs'])

    pointer_candidates: list[Path] = []
    for base in root_candidates:
        base_workspace = base / 'workspace'
        if base_workspace.exists() and base_workspace.is_dir():
            pointer_candidates.extend(workspace_autoload_pointer_candidates(base_workspace))
        for ws in iter_session_workspaces(base):
            pointer_candidates.extend(workspace_autoload_pointer_candidates(ws))

    for ptr in pointer_candidates:
        try:
            if not ptr.exists():
                continue
            obj = json.loads(ptr.read_text(encoding='utf-8', errors='ignore'))
            if not isinstance(obj, dict):
                continue
            rel = obj.get('npz_path') or obj.get('path') or obj.get('file')
            if not isinstance(rel, str) or not rel.strip():
                continue
            npz = Path(rel.strip())
            if not npz.is_absolute():
                npz = _absolute_fs_path(ptr.parent / npz)
            _add(npz)
            if len(out) >= max_files:
                return out
        except Exception:
            pass

    files: List[Path] = []
    for d in candidate_dirs:
        try:
            if d.exists() and d.is_dir():
                files.extend(list(d.glob('*.npz')))
        except Exception:
            pass

    files_sorted = sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    for f in files_sorted:
        _add(f)
        if len(out) >= max_files:
            break

    return out




def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("npz", nargs="*", help="Paths to *.npz")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    args = parse_args(argv)
    paths = [Path(p) for p in (args.npz or [])]
    startup_from_history = False

    # Auto-load latest runs if no files passed
    if not paths:
        # Prefer the last opened files (persistent state)
        try:
            s = QtCore.QSettings('UnifiedPneumoApp', 'DiagrammyCompareViewer')
            raw = s.value('last_files', None)
            if raw:
                try:
                    arr = _parse_qsettings_str_list(raw)
                except Exception:
                    arr = []
                cand = [Path(p) for p in arr if p]
                cand = [p for p in cand if p.exists() and p.is_file() and p.suffix.lower() == '.npz']
                seen_last: set[str] = set()
                cand_unique: List[Path] = []
                for p in cand:
                    key = _normalized_fs_path_key(p)
                    if key in seen_last:
                        continue
                    seen_last.add(key)
                    cand_unique.append(_absolute_fs_path(p))
                cand = cand_unique
                if cand:
                    paths = cand
                    startup_from_history = True
        except Exception:
            pass
        if not paths:
            paths = _auto_find_npz(max_files=6)

    app = QtWidgets.QApplication(sys.argv)
    w = CompareViewer(paths)
    if startup_from_history and (not getattr(w, 'runs', None)):
        tried = {_normalized_fs_path_key(p) for p in paths}
        fallback = [p for p in _auto_find_npz(max_files=6) if _normalized_fs_path_key(p) not in tried]
        if fallback:
            loaded = w._load_paths(fallback)
            if loaded > 0:
                loaded_paths = [getattr(r, 'path', Path('')) for r in getattr(w, 'runs', [])]
                w._clear_pending_dataset_restore_if_mismatch(loaded_paths)
                w._apply_restore_after_load()
    # Default size only if there is no saved geometry
    try:
        s = QtCore.QSettings('UnifiedPneumoApp', 'DiagrammyCompareViewer')
        if s.value('geometry') is None:
            w.resize(1280, 800)
    except Exception:
        w.resize(1280, 800)
    w.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
