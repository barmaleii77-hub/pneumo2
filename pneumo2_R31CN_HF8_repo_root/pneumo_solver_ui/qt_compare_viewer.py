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
        from geometry_acceptance_contract import format_geometry_acceptance_summary_lines  # type: ignore
    except Exception:
        from pneumo_solver_ui.geometry_acceptance_contract import format_geometry_acceptance_summary_lines  # type: ignore
except Exception:
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
        self.setWindowTitle("Pneumo: NPZ Compare Viewer (DiagrammyV680R05)")
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
        self._syncing_region: bool = False
        self._region = None
        self._updating_region = False

        # playhead / animation
        self._t_ref = np.asarray([], dtype=float)
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
        self._mv_updating: bool = False
        self._mv_restoring_settings: bool = False
        self._workspace_focus_mode: str = "all"
        self._insight_heat: Dict[str, object] = {}
        self._insight_infl: Dict[str, object] = {}
        self._insight_qa: Dict[str, object] = {}
        self._mv_timer = QtCore.QTimer(self)
        self._mv_timer.setSingleShot(True)
        self._mv_timer.timeout.connect(self._update_multivar_views)

        self._build_dock()
        self._build_menu()
        self._build_status_bar()
        self._apply_workspace_theme()

        # Persistent UI state (desktop): keep user selections across restarts
        self._settings = QtCore.QSettings('UnifiedPneumoApp', 'DiagrammyCompareViewer')
        self._restore_after_load = {}
        self._load_settings()
        self._build_heatmap_dock()
        self._build_influence_dock()
        self._build_infl_heatmap_dock()
        self._build_multivar_dock()
        self._build_qa_dock()
        self._build_events_dock()
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
        self.btn_workspace_focus_all.clicked.connect(lambda _=False: self._focus_workspace_preset("all"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_all)
        row_focus.addWidget(self.btn_workspace_focus_all)

        self.btn_workspace_focus_heatmaps = QtWidgets.QPushButton("Heatmaps")
        self.btn_workspace_focus_heatmaps.setObjectName("workspaceFocusHeatmapsButton")
        self.btn_workspace_focus_heatmaps.setToolTip("Focus Delta and Influence heatmaps.")
        self.btn_workspace_focus_heatmaps.setCheckable(True)
        self.btn_workspace_focus_heatmaps.clicked.connect(lambda _=False: self._focus_workspace_preset("heatmaps"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_heatmaps)
        row_focus.addWidget(self.btn_workspace_focus_heatmaps)

        self.btn_workspace_focus_multivar = QtWidgets.QPushButton("Multivar")
        self.btn_workspace_focus_multivar.setObjectName("workspaceFocusMultivarButton")
        self.btn_workspace_focus_multivar.setToolTip("Focus SPLOM, Parallel and 3D cloud views.")
        self.btn_workspace_focus_multivar.setCheckable(True)
        self.btn_workspace_focus_multivar.clicked.connect(lambda _=False: self._focus_workspace_preset("multivariate"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_multivar)
        row_focus.addWidget(self.btn_workspace_focus_multivar)

        self.btn_workspace_focus_qa = QtWidgets.QPushButton("QA / Events")
        self.btn_workspace_focus_qa.setObjectName("workspaceFocusQaButton")
        self.btn_workspace_focus_qa.setToolTip("Focus QA and event drill-down tools.")
        self.btn_workspace_focus_qa.setCheckable(True)
        self.btn_workspace_focus_qa.clicked.connect(lambda _=False: self._focus_workspace_preset("qa"))
        self._workspace_focus_buttons.addButton(self.btn_workspace_focus_qa)
        row_focus.addWidget(self.btn_workspace_focus_qa)

        ga.addLayout(row_focus)
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
        self.combo_nav_signal.currentIndexChanged.connect(self._rebuild_plots)
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
            self.chk_delta.setChecked(self._qs_bool(s.value('mode_delta', self.chk_delta.isChecked()), self.chk_delta.isChecked()))
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
        try:
            win_state = stt.get('window_state')
            if win_state is not None:
                self.restoreState(win_state)
        except Exception:
            pass
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
            keep_keys = (
                'dataset_paths',
                'runs',
                'runs_paths',
                'runs_selection_explicit',
                'reference_run',
                'reference_run_path',
                'table',
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
            s.setValue('mode_delta', int(self.chk_delta.isChecked()))
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

        self.lbl_status_layout = QtWidgets.QLabel("Focus all | Docks 0/0 | Ref —")
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
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())

        events_rows = 0
        try:
            if getattr(self, "tbl_events", None) is not None:
                events_rows = int(self.tbl_events.rowCount())
        except Exception:
            events_rows = 0

        qa_issues = 0
        try:
            qa_text = str(
                getattr(self, "lbl_qa_summary", None).text()
                if getattr(self, "lbl_qa_summary", None) is not None
                else ""
            )
            if "issues=" in qa_text:
                qa_issues = int(str(qa_text).split("issues=", 1)[1].split()[0].split("(", 1)[0].rstrip(",)"))
        except Exception:
            qa_issues = 0

        notes: List[str] = []
        if trust_visible:
            notes.append("trust banner active")
        if qa_issues > 0:
            notes.append(f"QA issues: {qa_issues}")
        if events_rows > 0:
            notes.append(f"event rows: {events_rows}")

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
        elif mode == "heatmaps":
            title = "Heatmap comparison"
            body = (
                f"Use Delta and Influence heatmaps to localize where {len(runs)} runs diverge across "
                f"{len(sigs)} selected signals in table {table}. Review QA or Events when a hotspot needs explanation."
            )
            tone = "accent"
        elif mode == "multivariate":
            title = "Multivariate scouting"
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

    def _update_workspace_insights(self) -> None:
        browser = getattr(self, "txt_workspace_insights", None)
        if browser is None:
            return

        runs = list(self._selected_runs()) if hasattr(self, "list_runs") else []
        sigs = list(self._selected_signals()) if hasattr(self, "list_signals") else []
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())
        table = str(getattr(self, "current_table", "") or "-")

        events_rows = 0
        try:
            if getattr(self, "tbl_events", None) is not None:
                events_rows = int(self.tbl_events.rowCount())
        except Exception:
            events_rows = 0

        heat = dict(getattr(self, "_insight_heat", {}) or {})
        infl = dict(getattr(self, "_insight_infl", {}) or {})
        qa = dict(getattr(self, "_insight_qa", {}) or {})

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

        cards: List[str] = []

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

        if not runs:
            quality_headline = "Load a compare set"
            quality_detail = "Open 2+ NPZ runs to unlock heatmaps, QA and multivariate clustering."
            quality_tone = "neutral"
        elif trust_visible:
            quality_headline = "Trust attention required"
            quality_detail = (
                f"Trust banner is active. QA issues={qa_issues} (err={qa_err}, warn={qa_warn}), events rows={events_rows}. "
                "Next: QA / Events."
            )
            if qa_focus:
                quality_detail = f"{quality_detail} {qa_focus}"
            quality_tone = "alert" if qa_err > 0 else "warn"
        elif qa_issues > 0:
            quality_headline = f"QA flagged {qa_issues} issue(s)"
            quality_detail = (
                f"err={qa_err}, warn={qa_warn}, events rows={events_rows}. "
                "Next: inspect QA / Events, then return to Heatmaps for root-cause localization."
            )
            if qa_focus:
                quality_detail = f"{quality_detail} {qa_focus}"
            quality_tone = "warn" if qa_err == 0 else "alert"
        elif len(runs) >= 3 and len(sigs) >= 3:
            quality_headline = "Ready for all-to-all scouting"
            quality_detail = (
                f"Table {table}, runs={len(runs)}, signals={len(sigs)}, events rows={events_rows}. "
                "Next: Multivar for clusters and sparse outliers, then Heatmaps for time localization."
            )
            quality_tone = "ok"
        else:
            quality_headline = "Build comparison density"
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

    def _workspace_focus_label(self) -> str:
        mode = str(getattr(self, "_workspace_focus_mode", "all") or "all")
        labels = {
            "all": "all",
            "heatmaps": "heatmaps",
            "multivariate": "multivar",
            "qa": "qa/events",
        }
        return labels.get(mode, mode)

    def _update_workspace_status(self) -> None:
        runs = list(self._selected_runs()) if hasattr(self, "list_runs") else []
        sigs = list(self._selected_signals()) if hasattr(self, "list_signals") else []
        table = str(getattr(self, "current_table", "") or "—")
        ref = str(self._reference_run_label(runs) or "—")
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

        qa_text = str(getattr(self, "lbl_qa_summary", None).text() if getattr(self, "lbl_qa_summary", None) is not None else "QA —")
        qa_issues = 0
        try:
            if "issues=" in qa_text:
                qa_issues = int(str(qa_text).split("issues=", 1)[1].split()[0].split("(", 1)[0].rstrip(",)"))
        except Exception:
            qa_issues = 0
        trust_visible = bool(getattr(self, "lbl_trust", None) is not None and self.lbl_trust.isVisible())

        selection_text = f"Runs {len(runs)} | Table {table} | Signals {len(sigs)}"
        quality_text = f"Events {events_rows} | {'Trust attention' if trust_visible else 'Trust ok'} | QA {qa_issues}"
        layout_text = f"Focus {self._workspace_focus_label()} | Docks {visible_docks}/{total_docks} | Ref {ref}"

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
        self._set_status_chip_tone(self.lbl_status_layout, "accent" if visible_docks else "neutral")
        self._sync_workspace_focus_buttons()
        self._update_workspace_assistant()
        self._update_workspace_insights()

    def _iter_workspace_docks(self) -> List[QtWidgets.QDockWidget]:
        docks: List[QtWidgets.QDockWidget] = []
        for attr in (
            "dock_controls",
            "dock_heatmap",
            "dock_influence",
            "dock_inflheat",
            "dock_multivar",
            "dock_qa",
            "dock_events",
        ):
            dock = getattr(self, attr, None)
            if isinstance(dock, QtWidgets.QDockWidget):
                docks.append(dock)
        return docks

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
            dock.raise_()
        except Exception:
            pass

    def _apply_default_workspace_layout(self) -> None:
        self._workspace_focus_mode = "all"
        controls = getattr(self, "dock_controls", None)
        heatmap = getattr(self, "dock_heatmap", None)
        influence = getattr(self, "dock_influence", None)
        inflheat = getattr(self, "dock_inflheat", None)
        multivar = getattr(self, "dock_multivar", None)
        qa = getattr(self, "dock_qa", None)
        events = getattr(self, "dock_events", None)

        for dock in self._iter_workspace_docks():
            self._show_dock(dock)
            try:
                self.removeDockWidget(dock)
            except Exception:
                pass

        if controls is not None:
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, controls)

        analysis_anchor = heatmap or influence or inflheat or multivar
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

        for dock in (heatmap, influence, inflheat, multivar):
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
        influence = getattr(self, "dock_influence", None)
        inflheat = getattr(self, "dock_inflheat", None)
        multivar = getattr(self, "dock_multivar", None)
        qa = getattr(self, "dock_qa", None)
        events = getattr(self, "dock_events", None)

        show_attrs = {"dock_controls"}
        active_dock = controls
        if mode == "heatmaps":
            show_attrs.update({"dock_heatmap", "dock_influence", "dock_inflheat"})
            active_dock = heatmap or influence or inflheat or controls
        elif mode == "multivariate":
            show_attrs.add("dock_multivar")
            active_dock = multivar or controls
        elif mode == "qa":
            show_attrs.update({"dock_qa", "dock_events"})
            active_dock = qa or events or controls
        else:
            show_attrs.update(
                {
                    "dock_heatmap",
                    "dock_influence",
                    "dock_inflheat",
                    "dock_multivar",
                    "dock_qa",
                    "dock_events",
                }
            )
            active_dock = heatmap or multivar or qa or controls

        for attr in (
            "dock_controls",
            "dock_heatmap",
            "dock_influence",
            "dock_inflheat",
            "dock_multivar",
            "dock_qa",
            "dock_events",
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
        self.act_view_show_all_docks.triggered.connect(lambda: self._focus_workspace_preset("all"))
        layout_menu.addAction(self.act_view_show_all_docks)

        layout_menu.addSeparator()

        self.act_view_focus_heatmaps = QtGui.QAction("Focus Heatmaps", self)
        self.act_view_focus_heatmaps.setObjectName("act_view_focus_heatmaps")
        self.act_view_focus_heatmaps.setShortcut("Ctrl+Shift+1")
        self.act_view_focus_heatmaps.triggered.connect(lambda: self._focus_workspace_preset("heatmaps"))
        layout_menu.addAction(self.act_view_focus_heatmaps)

        self.act_view_focus_multivar = QtGui.QAction("Focus Multivariate", self)
        self.act_view_focus_multivar.setObjectName("act_view_focus_multivar")
        self.act_view_focus_multivar.setShortcut("Ctrl+Shift+2")
        self.act_view_focus_multivar.triggered.connect(lambda: self._focus_workspace_preset("multivariate"))
        layout_menu.addAction(self.act_view_focus_multivar)

        self.act_view_focus_qa = QtGui.QAction("Focus QA / Events", self)
        self.act_view_focus_qa.setObjectName("act_view_focus_qa")
        self.act_view_focus_qa.setShortcut("Ctrl+Shift+3")
        self.act_view_focus_qa.triggered.connect(lambda: self._focus_workspace_preset("qa"))
        layout_menu.addAction(self.act_view_focus_qa)

        docks_menu = view_menu.addMenu("Docks")
        self.menu_view_docks = docks_menu
        dock_specs = (
            ("Controls", getattr(self, "dock_controls", None)),
            ("Δ(t) Heatmap", getattr(self, "dock_heatmap", None)),
            ("Influence(t)", getattr(self, "dock_influence", None)),
            ("Influence(t) Heatmap", getattr(self, "dock_inflheat", None)),
            ("Multivariate", getattr(self, "dock_multivar", None)),
            ("QA", getattr(self, "dock_qa", None)),
            ("Events", getattr(self, "dock_events", None)),
        )
        for text, dock in dock_specs:
            if not isinstance(dock, QtWidgets.QDockWidget):
                continue
            act = dock.toggleViewAction()
            act.setText(text)
            docks_menu.addAction(act)



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
        self.chk_heatmap.setChecked(True)
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
            self.lbl_heat_note.setText(self._heatmap_default_note())
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
            # Add signal to selection and move current focus without altering multi-select state.
            self._select_signal_by_name(str(sig_lab), exclusive=False)
            run_added = False
            if hasattr(self, 'list_runs'):
                try:
                    self.list_runs.blockSignals(True)
                    for i in range(self.list_runs.count()):
                        it = self.list_runs.item(i)
                        if it is None or str(it.text()) != str(run_lab):
                            continue
                        if not it.isSelected():
                            it.setSelected(True)
                            run_added = True
                        self._set_current_list_row(self.list_runs, i)
                        break
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
            "Совет: включите Δ-mode, чтобы видеть влияние на Δ(signal) относительно reference run."
        )

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
            self.lbl_inflheat_note.setText(self._inflheat_default_note())
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
        except Exception:
            pass

    def _clear_inflheat_view(self, note: str = "") -> None:
        self._inflheat = None
        self._inflheat_t = np.zeros(0, dtype=float)
        self._inflheat_sig_labels = []
        self._inflheat_feat_labels = []
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
        except Exception:
            return

    def _on_inflheat_mouse_moved(self, evt):
        if self.imv_inflheat is None:
            return
        try:
            pos = evt[0] if isinstance(evt, (tuple, list)) else evt
            vb = self.imv_inflheat.getView()
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
        self.combo_mv_color.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
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
        self.combo_mv_x = QtWidgets.QComboBox(); self.combo_mv_x.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3.addWidget(self.combo_mv_x, 1)
        row3.addWidget(QtWidgets.QLabel("Y:"))
        self.combo_mv_y = QtWidgets.QComboBox(); self.combo_mv_y.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3.addWidget(self.combo_mv_y, 1)
        row3.addWidget(QtWidgets.QLabel("Z:"))
        self.combo_mv_z = QtWidgets.QComboBox(); self.combo_mv_z.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
        row3.addWidget(self.combo_mv_z, 1)
        tv.addLayout(row3)

        row3b = QtWidgets.QHBoxLayout()
        row3b.setSpacing(8)
        row3b.addWidget(QtWidgets.QLabel("3D color:"))
        self.combo_mv_color3d = QtWidgets.QComboBox(); self.combo_mv_color3d.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
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
        self.combo_mv_peb_sig = QtWidgets.QComboBox(); self.combo_mv_peb_sig.currentIndexChanged.connect(lambda _=None: self._schedule_multivar_update())
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
            self.chk_mv_pebbles.setChecked(
                self._qs_bool(
                    s.value("mv_pebbles", self.chk_mv_pebbles.isChecked()),
                    self.chk_mv_pebbles.isChecked(),
                )
            )
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
                s.setValue("mv_pebbles", bool(self.chk_mv_pebbles.isChecked()))
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
                f"Runs: {len(runs)} | Signals: {len(sigs)} | Fields: {len(dfp.columns)-1} | "
                f"Metric: {metric} | Δ-mode: {bool(getattr(self,'chk_delta',None) and self.chk_delta.isChecked())}"
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

            prefer_color = "RMS_mean" if "RMS_mean" in cols_all else (cols_all[0] if cols_all else "")
            _refill(self.combo_mv_color, cols_all, prefer=prefer_color)
            _refill(self.combo_mv_color3d, cols_all, prefer=prefer_color)
            _refill(self.combo_mv_x, cols_all, prefer=cols_all[0] if cols_all else "")
            _refill(self.combo_mv_y, cols_all, prefer=cols_all[1] if len(cols_all) > 1 else (cols_all[0] if cols_all else ""))
            _refill(self.combo_mv_z, cols_all, prefer=cols_all[2] if len(cols_all) > 2 else (cols_all[0] if cols_all else ""))
            for combo in (self.combo_mv_color, self.combo_mv_color3d, self.combo_mv_x, self.combo_mv_y, self.combo_mv_z):
                combo.setEnabled(bool(combo.count()))
        except Exception:
            pass

        # pebbles signals options (from events / discrete detection)
        try:
            disc = self._mv_discrete_signal_options()
            cur = str(self.combo_mv_peb_sig.currentText() or "")
            self.combo_mv_peb_sig.blockSignals(True)
            self.combo_mv_peb_sig.clear()
            self.combo_mv_peb_sig.addItems([""] + disc)
            if cur in disc:
                self.combo_mv_peb_sig.setCurrentText(cur)
            elif disc:
                self.combo_mv_peb_sig.setCurrentText(disc[0])
            self.combo_mv_peb_sig.blockSignals(False)
            self.combo_mv_peb_sig.setEnabled(bool(disc))
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
        lay.addWidget(self.lbl_events_info)

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
        lay.addWidget(self.tbl_events, 1)

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

            try:
                if sig and self._select_signal_by_name(sig, exclusive=True):
                    self._rebuild_plots()
            except Exception:
                pass

            self._set_playhead_time(float(t))
        except Exception:
            return


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

        if bool(getattr(self, 'chk_qa_all', None) and self.chk_qa_all.isChecked()):
            sigs = [self.list_signals.item(i).text() for i in range(self.list_signals.count())]
        else:
            sigs = [it.text() for it in self.list_signals.selectedItems()]
        # Remove obvious time columns
        sigs = [s for s in sigs if str(s).strip().lower() not in ("t", "time", "timestamp")]
        if not sigs:
            if bool(getattr(self, '_signals_selection_explicit', False)):
                self._clear_qa_view("QA: выберите хотя бы один сигнал")
                return
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
        summ = qa_summarize(df) if qa_summarize is not None else {"n": int(len(df))}
        n = int(summ.get('n', 0) or 0)
        n_err = int(summ.get('n_err', 0) or 0)
        n_warn = int(summ.get('n_warn', 0) or 0)

        try:
            if n == 0:
                self.lbl_qa_summary.setText("QA: явных проблем не найдено")
            else:
                self.lbl_qa_summary.setText(f"QA: issues={n} (err={n_err}, warn={n_warn})")
        except Exception:
            pass
        self._insight_qa = {"issues": int(n), "err": int(n_err), "warn": int(n_warn)}
        self._update_workspace_status()

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
            self.tbl_qa.setRowCount(0)
            if df is None or df.empty:
                self.tbl_qa.setEnabled(False)
                return
            # columns: severity, run, signal, code, t0, message
            rows = df[["severity", "run_label", "signal", "code", "t0", "message"]].values.tolist()
            self.tbl_qa.setRowCount(len(rows))
            for i, row in enumerate(rows[:500]):
                for j, val in enumerate(row):
                    it = QtWidgets.QTableWidgetItem("" if val is None else str(val))
                    self.tbl_qa.setItem(i, j, it)
            self.tbl_qa.setEnabled(bool(rows))
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
        try:
            self.lbl_qa_summary.setText(str(summary or "QA: —"))
        except Exception:
            pass
        try:
            self.lbl_qa_readout.setText("")
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
        try:
            self._focus_run_signal(str(run), str(sig))
        except Exception:
            pass

        # Move playhead to first issue time if available
        t0 = self._qa_first_t.get((str(run), str(sig)))
        if t0 is not None and isinstance(t0, (int, float)) and np.isfinite(float(t0)):
            try:
                self._set_playhead_time(float(t0))
            except Exception:
                pass

        self._rebuild_plots()


    def _on_qa_table_double_clicked(self, row: int, _col: int):
        try:
            run = self.tbl_qa.item(row, 1).text()
            sig = self.tbl_qa.item(row, 2).text()
            t0_txt = self.tbl_qa.item(row, 4).text()
        except Exception:
            return
        try:
            self._focus_run_signal(str(run), str(sig))
        except Exception:
            pass
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

    def _focus_run_signal(self, run_label: str, signal_name: str) -> None:
        target_run = None
        try:
            for run in getattr(self, "runs", []):
                if str(getattr(run, "label", "") or "") == str(run_label):
                    target_run = run
                    break
        except Exception:
            target_run = None
        if target_run is None:
            return

        sig_name = str(signal_name)
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
                return
            for candidate in (current_table, remembered_table, "main"):
                if candidate and candidate in matching_tables:
                    target_table = candidate
                    break
            if not target_table:
                target_table = matching_tables[0]

        if not self._select_run_by_label(str(run_label)):
            return
        self._on_run_selection_changed()
        try:
            self._remember_reference_run(target_run)
        except Exception:
            pass
        try:
            if target_table and hasattr(self, "combo_table"):
                idx = self.combo_table.findText(target_table)
                if idx >= 0 and str(self.combo_table.currentText() or "") != target_table:
                    self.combo_table.setCurrentIndex(idx)
        except Exception:
            pass
        if sig_name and not self._select_signal_by_name(sig_name, exclusive=True):
            return
        self._rebuild_plots()

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

    def _clear_influence_view(self, note: str = "") -> None:
        try:
            self.tbl_infl.setRowCount(0)
            self.tbl_infl.setColumnCount(0)
            self.tbl_infl.setEnabled(False)
        except Exception:
            pass
        try:
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

            note = f"t={t0:.4f}s | runs={len(runs)} | sigs={len(sigs)} | meta(all)={len(feat_all)} показано={len(feat_sel)}"
            if use_delta:
                note += f" | mode=Δ относительно {ref_run.label}"
            else:
                note += " | mode=value"
            self.lbl_infl_note.setText(note)

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
        except Exception:
            pass

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

            # points
            try:
                self.plot_infl.plot(x, y, pen=None, symbol="o", symbolSize=7, symbolBrush=(80, 80, 80, 180))
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
                title = f"t={t0:.4f}s | corr={c:.3f} | n={int(m.sum())}"
                self.plot_infl.setTitle(title)
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
        self.reference_run_selected = ""
        self.reference_run_selected_path = ""
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
            return []
        # intersection by default
        cols_sets = []
        for r in runs:
            df = r.tables.get(self.current_table)
            if isinstance(df, pd.DataFrame) and len(df.columns):
                cols_sets.append(set(map(str, df.columns)))
        if not cols_sets:
            self.available_signals = []
        else:
            common = set.intersection(*cols_sets)
            # remove time col (from first run)
            df0 = runs[0].tables.get(self.current_table)
            if df0 is not None and not df0.empty:
                tcol = detect_time_col(df0)
                common.discard(tcol)
            sigs = sorted(common)

            # apply filter
            q = self.edit_filter.text().strip()
            if q:
                try:
                    import re

                    rx = re.compile(q, flags=re.IGNORECASE)
                    sigs = [s for s in sigs if rx.search(s)]
                except Exception:
                    ql = q.lower()
                    sigs = [s for s in sigs if ql in s.lower()]
            self.available_signals = sigs

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
        try:
            self.combo_nav_signal.blockSignals(True)
            self.combo_nav_signal.clear()
            self.combo_nav_signal.addItems(self.available_signals[: min(200, len(self.available_signals))])
            if cur:
                self.combo_nav_signal.setCurrentText(cur)
        finally:
            try:
                self.combo_nav_signal.blockSignals(False)
            except Exception:
                pass
        try:
            self.combo_nav_signal.setEnabled(bool(self.available_signals))
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
        if not isinstance(df, pd.DataFrame) or df.empty:
            try:
                tbl.setRowCount(0)
            except Exception:
                pass
            try:
                tbl.setEnabled(False)
            except Exception:
                pass
            try:
                self.lbl_events_info.setText("Events: none")
            except Exception:
                pass
            self._update_workspace_status()
            return

        pick = set(self._get_selected_event_signals())
        have_filter_items = bool(getattr(self, 'list_events', None) is not None and self.list_events.count() > 0)
        if have_filter_items:
            if pick:
                try:
                    df = df[df['signal'].astype(str).isin([str(x) for x in pick])].copy()
                except Exception:
                    pass
            else:
                df = df.iloc[0:0].copy()

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
            suffix = " | no signals selected" if have_filter_items and not pick else ""
            self.lbl_events_info.setText(f"Events: {len(df)} (baseline={ref_run.label if ref_run else ''}){suffix}")
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

    def _get_xy(self, run: Run, sig: str) -> Tuple[np.ndarray, np.ndarray, str]:
        df = run.tables.get(self.current_table)
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
            if bool(getattr(self, "zero_baseline", False)):
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


    def _on_region_changed(self):
        if getattr(self, "_updating_region", False):
            return
        if not getattr(self, "_region", None) or not self.plots:
            return
        self._updating_region = True
        try:
            r0, r1 = self._region.getRegion()
            for p in self.plots:
                p.setXRange(r0, r1, padding=0)
        finally:
            self._updating_region = False

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
        if not getattr(self, "_region", None):
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
            self._region.setRegion((r0, r1))
        finally:
            self._updating_region = False

    def _rebuild_plots(self):
        """Build small-multiples plots for selected signals and runs.

        Key goals (Диаграммы):
        - Быстрое сравнение серий (наложение / Δ к эталону)
        - Единые шкалы (lock-Y) для корректного визуального сопоставления
        - Нулевая базовая позиция (display-only) для перемещений/углов
        """

        runs = self._selected_runs()
        sigs = self._selected_plot_signals()
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
        if use_nav and getattr(self, "_region", None) and first_plot is not None:
            try:
                first_plot.getViewBox().sigXRangeChanged.connect(self._on_main_xrange_changed)
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
                self.slider_time.setValue(min(self.slider_time.value(), n - 1))
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
        return idx, x

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
        try:
            saved_state = self.saveState()
            saved_geometry = self.saveGeometry()
        except Exception:
            pass

        exports: List[Path] = []
        try:
            preset_specs = (
                ("compare_workspace_overview.png", "all"),
                ("compare_workspace_heatmaps.png", "heatmaps"),
                ("compare_workspace_multivariate.png", "multivariate"),
                ("compare_workspace_qa.png", "qa"),
            )
            for filename, mode in preset_specs:
                self._focus_workspace_preset(mode)
                if mode == "multivariate":
                    try:
                        self._update_multivar_views()
                    except Exception:
                        pass
                try:
                    QtWidgets.QApplication.processEvents()
                except Exception:
                    pass
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
            try:
                QtWidgets.QApplication.processEvents()
            except Exception:
                pass

        return exports

    def _export_png(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export PNG", "compare.png", "PNG Images (*.png)")
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
