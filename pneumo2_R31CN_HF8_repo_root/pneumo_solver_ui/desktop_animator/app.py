# -*- coding: utf-8 -*-
"""PySide6 Desktop Animator (multi-view).

Goals:
- Informative animation for suspension + pneumatics.
- Multi-view cockpit: 3D + front/rear + left/right + road HUD.
- Minimal manual workflow: follow a pointer file (anim_latest.json).

NOTE: This is not a CAD editor. Geometry is auto-constructed from
wheelbase/track and simulation outputs.

LAW (ABSOLUTE-ONLY ANIMATION):
- Animator must render geometry strictly from **absolute** signals exported by the model.
- No hidden baselines/offsets/"zero pose" invented by a renderer.
- *_rel0 columns may exist for plots, but must never be used implicitly for rendering.
"""

from __future__ import annotations

# ---------------------------------------------------------------------
# Bootstrap: allow running as a script (python pneumo_solver_ui/desktop_animator/app.py)
# ---------------------------------------------------------------------
# When this file is executed directly, __package__ is empty and relative imports fail
# ("attempted relative import with no known parent package").
# Fix: add project root to sys.path and set __package__ so that relative imports work.
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    import sys as _sys
    from pathlib import Path as _Path
    _ROOT = _Path(__file__).resolve().parents[2]
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.desktop_animator"

# Diagnostics hooks (best-effort; never crash animator if diag is broken)

# Crash guard (auto-save send-bundle on unexpected crashes)
try:
    from pneumo_solver_ui.release_info import get_release
    from pneumo_solver_ui import crash_guard
    crash_guard.install(extra_meta={"release": get_release(), "entry": "desktop_animator"})
except Exception:
    pass

try:
    from pneumo_solver_ui.diag.bootstrap import init_nonstreamlit as _init_diag

    _init_diag()
except Exception:
    _init_diag = None  # type: ignore

from pathlib import Path as _PathProject
PROJECT_ROOT = _PathProject(__file__).resolve().parents[2]

import os
import logging

# Enforce a single Qt binding for the whole process (PySide6).
# This avoids mixed-Qt situations where pyqtgraph/QtPy pick a different binding than the rest of the app,
# leading to "empty" windows or runtime crashes on some systems.
# NOTE: This is not a key alias/compatibility bridge. It is a runtime dependency selection to keep the stack consistent.
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
import math
import json
import re
import time
import colorsys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from pneumo_solver_ui.data_contract import read_visual_geometry_meta
from pneumo_solver_ui.visual_contract import (
    collect_visual_cache_dependencies,
    visual_cache_dependencies_token,
)
from pneumo_solver_ui.desktop_animator.pointer_paths import default_anim_pointer_path
from pneumo_solver_ui.desktop_animator.geometry_acceptance import (
    collect_acceptance_status,
    corner_acceptance_arrays,
    format_acceptance_hud_lines,
)
from pneumo_solver_ui.desktop_animator.suspension_geometry_diagnostics import (
    format_suspension_hud_lines,
)

logger = logging.getLogger(__name__)

_ANIMATOR_WARNING_SEEN: set[str] = set()

# ---------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------

# 1 bar = 100000 Pa
BAR_PA: float = 100000.0

# Default atmospheric pressure (used only as fallback if meta/log does not provide it)
PATM_PA_DEFAULT: float = 101325.0


def _max_visible_advances_per_tick(speed: float) -> int:
    """Playback policy: prefer smoothness over large visible jumps.

    Why this helper exists:
    - at x1.0 the dataset can legitimately require ~80-150 source frames per second;
    - when the GUI thread is late, blindly catching up all accumulated source steps in one
      timer tick makes the image jump, which looks exactly like "insufficient frames" even
      when the bundle itself is reasonably dense;
    - for <= x1.0 we deliberately allow only one visible sample advance per tick, keeping
      the remaining wall-time debt for the next timer wake-up. This may lag slightly under
      overload, but it preserves motion continuity far better than multi-frame jumps.
    """
    spd = float(max(0.05, speed))
    if spd <= 1.0:
        return 1
    if spd <= 2.0:
        return 2
    return 4


def _infer_patm_pa(b: "DataBundle", i: int) -> float:
    """Best-effort atmospheric pressure inference.

    The animator needs Patm to show gauge pressure (bar-g).

    Priority:
      1) meta: 'patm_pa' / 'P_ATM' / 'p_atm_pa'
      2) main log column (if present): 'patm_pa' / 'P_ATM_Па' / 'p_atm_Па'
      3) fallback constant.
    """
    # 1) meta
    try:
        m = b.meta or {}
        for k in ("patm_pa", "p_atm_pa", "P_ATM", "P_ATM_Па", "p_atm_Па"):
            if k in m and m.get(k) is not None:
                try:
                    return float(m.get(k))
                except Exception:
                    pass
    except Exception:
        pass

    # 2) main
    try:
        df = b.main
        if df is not None and hasattr(df, "columns"):
            for c in ("patm_pa", "p_atm_pa", "P_ATM", "P_ATM_Па", "p_atm_Па"):
                if c in df.columns:
                    try:
                        v = float(df[c].iloc[int(i)])
                        if v == v and abs(v) > 1.0:
                            return v
                    except Exception:
                        pass
    except Exception:
        pass

    return float(PATM_PA_DEFAULT)


def _infer_patm_source(b: "DataBundle") -> tuple[Optional[np.ndarray], float]:
    try:
        m = b.meta or {}
        for k in ("patm_pa", "p_atm_pa", "P_ATM", "P_ATM_Па", "p_atm_Па"):
            if k in m and m.get(k) is not None:
                try:
                    return None, float(m.get(k))
                except Exception:
                    pass
    except Exception:
        pass

    try:
        df = b.main
        if df is not None and hasattr(df, "columns"):
            for c in ("patm_pa", "p_atm_pa", "P_ATM", "P_ATM_Па", "p_atm_Па"):
                if c in df.columns:
                    try:
                        arr = np.asarray(df[c], dtype=float).reshape(-1)
                        if arr.size:
                            return arr, float(PATM_PA_DEFAULT)
                    except Exception:
                        pass
    except Exception:
        pass

    return None, float(PATM_PA_DEFAULT)


def _patm_value_from_source(patm_arr: Optional[np.ndarray], patm_default_pa: float, i: int) -> float:
    if patm_arr is not None and 0 <= int(i) < int(patm_arr.size):
        try:
            v = float(patm_arr[int(i)])
            if np.isfinite(v) and abs(v) > 1.0:
                return v
        except Exception:
            pass
    return float(patm_default_pa)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ModuleNotFoundError as e:
    # Mandatory event in logs (so that "тихо закрылось" не было без следов)
    try:
        from pneumo_solver_ui.diag.eventlog import get_global_logger

        get_global_logger(PROJECT_ROOT).emit(
            "ModuleNotFoundError",
            repr(e),
            module="PySide6",
            context="desktop_animator",
        )
    except Exception:
        pass

    _msg = (
        "PySide6 не установлен. Desktop Animator требует PySide6 (Qt for Python).\n\n"
        "Авто-установка: открой Streamlit страницу 'Desktop Animator' и нажми 'Установить PySide6'.\n"
        "Вручную:  pip install PySide6\n"
    )
    # На Windows (без консоли) покажем MessageBox, чтобы окно не закрывалось молча.
    try:
        import sys as _sys

        if _sys.platform.startswith("win"):
            try:
                import ctypes  # type: ignore

                ctypes.windll.user32.MessageBoxW(0, _msg, "Desktop Animator", 0x10)
            except Exception:
                pass
    except Exception:
        pass

    raise SystemExit(_msg) from e


from .data_bundle import CORNERS, DataBundle, load_npz
from .hmi_widgets import EventTimelineWidget, TrendsPanel
from .cylinder_truth_gate import (
    evaluate_all_cylinder_truth_gates as _evaluate_all_cylinder_truth_gates,
    render_cylinder_truth_gate_message as _render_cylinder_truth_gate_message,
)
from .playback_sampling import (
    lerp_point_row as _lerp_point_row,
    lerp_series_value as _lerp_series_value,
    sample_time_bracket as _sample_time_bracket,
)

from .geom3d_helpers import (
    car_frame_rotate_xy as _car_frame_rotate_xy,
    center_and_orient_cylinder_vertices_to_y as _center_and_orient_cylinder_vertices_to_y,
    contact_point_from_patch_faces as _contact_point_from_patch_faces,
    cylinder_visual_segments_from_state as _cylinder_visual_segments_from_state,
    cylinder_visual_state_from_packaging as _cylinder_visual_state_from_packaging,
    derive_wheel_pose_from_hardpoints as _derive_wheel_pose_from_hardpoints,
    grid_faces_rect as _grid_faces_rect,
    lifted_box_center_from_lower_corners as _lifted_box_center_from_lower_corners,
    localize_world_points_to_car_frame as _localize_world_points_to_car_frame,
    orient_centered_cylinder_vertices_to_y as _orient_centered_cylinder_vertices_to_y,
    orthonormal_frame_from_corners as _orthonormal_frame_from_corners,
    project_vector_to_plane as _project_vector_to_plane,
    regular_grid_submesh as _regular_grid_submesh,
    road_display_counts_from_view as _road_display_counts_from_view,
    clamp_window_to_interpolation_support as _clamp_window_to_interpolation_support,
    road_grid_line_segments as _road_grid_line_segments,
    road_grid_target_s_values_from_range as _road_grid_target_s_values_from_range,
    road_native_support_s_values_from_axis as _road_native_support_s_values_from_axis,
    road_crossbar_line_segments_from_profiles as _road_crossbar_line_segments_from_profiles,
    rod_internal_centerline_vertices_from_packaging_state as _rod_internal_centerline_vertices_from_packaging_state,
    stable_road_grid_cross_spacing_from_view as _stable_road_grid_cross_spacing_from_view,
    stable_road_surface_spacing_from_view as _stable_road_surface_spacing_from_view,
    road_patch_faces_inside_wheel_cylinder as _road_patch_faces_inside_wheel_cylinder,
    road_patch_mesh_inside_wheel_cylinder as _road_patch_mesh_inside_wheel_cylinder,
    road_surface_grid_from_profiles as _road_surface_grid_from_profiles,
)

try:
    import qdarktheme  # type: ignore
except Exception:
    qdarktheme = None

# Optional pyqtgraph (2D) + OpenGL (3D)
# NOTE: keep them separate: OpenGL may fail while 2D plots are still usable.
try:
    import pyqtgraph as pg  # type: ignore
except Exception:
    pg = None

try:
    import pyqtgraph.opengl as gl  # type: ignore
    _HAS_GL = True
except Exception:
    gl = None
    _HAS_GL = False

_HAS_PG = pg is not None


# -----------------------------
# Utils
# -----------------------------

def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _safe_float(x: Any, default: float) -> float:
    try:
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return float(default)
        return v
    except Exception:
        return float(default)


def _fmt(x: float, unit: str = "", *, digits: int = 3) -> str:
    try:
        v = float(x)
        if not np.isfinite(v):
            return "—"
        return f"{v:.{digits}f}{unit}"
    except Exception:
        return f"?{unit}"


_AIR_ITEM_STATE_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) + 17


def _set_label_text_if_changed(label: Optional[QtWidgets.QLabel], text: str) -> None:
    if label is None:
        return
    try:
        if label.text() == text:
            return
    except Exception:
        pass
    try:
        label.setText(text)
    except Exception:
        pass


def _set_graphics_text_if_changed(item: Optional[Any], text: str) -> None:
    if item is None:
        return
    try:
        if hasattr(item, "text"):
            if str(item.text()) == text:
                return
        elif hasattr(item, "toPlainText"):
            if str(item.toPlainText()) == text:
                return
    except Exception:
        pass
    try:
        if hasattr(item, "setText"):
            item.setText(text)
        elif hasattr(item, "setPlainText"):
            item.setPlainText(text)
    except Exception:
        pass


def _set_graphics_pos_if_changed(item: Optional[Any], x: float, y: float) -> None:
    if item is None:
        return
    tx = float(x)
    ty = float(y)
    try:
        pos = item.pos()
        if abs(float(pos.x()) - tx) <= 1e-9 and abs(float(pos.y()) - ty) <= 1e-9:
            return
    except Exception:
        pass
    try:
        item.setPos(tx, ty)
    except Exception:
        pass


def _make_graphics_label_item(
    scene: Optional[QtWidgets.QGraphicsScene],
    *,
    color: Optional[QtGui.QColor] = None,
    font_family: str = "Consolas",
    font_size: int = 8,
    z: float = 20.0,
) -> QtWidgets.QGraphicsSimpleTextItem:
    item = QtWidgets.QGraphicsSimpleTextItem()
    item.setZValue(float(z))
    try:
        item.setBrush(QtGui.QBrush(color or QtGui.QColor(220, 220, 220)))
    except Exception:
        pass
    try:
        item.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
    except Exception:
        pass
    try:
        item.setFont(QtGui.QFont(str(font_family), int(font_size)))
    except Exception:
        pass
    try:
        if scene is not None:
            scene.addItem(item)
    except Exception:
        pass
    return item


def _set_table_item_text_if_changed(item: Optional[QtWidgets.QTableWidgetItem], text: str) -> None:
    if item is None:
        return
    try:
        if item.text() == text:
            return
    except Exception:
        pass
    try:
        item.setText(text)
    except Exception:
        pass


def _set_progress_value_if_changed(pb: Any, value: int) -> None:
    if pb is None:
        return
    try:
        target = int(value)
    except Exception:
        target = 0
    try:
        if int(pb.value()) == target:
            return
    except Exception:
        pass
    try:
        pb.setValue(target)
    except Exception:
        pass


def _set_table_row_count_if_changed(table: Optional[QtWidgets.QTableWidget], rows: int) -> None:
    if table is None:
        return
    target = int(max(0, rows))
    try:
        if int(table.rowCount()) == target:
            return
    except Exception:
        pass
    try:
        table.setRowCount(target)
    except Exception:
        pass


def _set_table_row_hidden_if_changed(
    table: Optional[QtWidgets.QTableWidget], row: int, hidden: bool
) -> None:
    if table is None:
        return
    row_i = int(max(0, row))
    target = bool(hidden)
    try:
        if bool(table.isRowHidden(row_i)) == target:
            return
    except Exception:
        pass
    try:
        table.setRowHidden(row_i, target)
    except Exception:
        pass


def _set_table_fixed_row_height(
    table: Optional[QtWidgets.QTableWidget], *, padding: int = 8, minimum: int = 20
) -> None:
    if table is None:
        return
    try:
        table.setWordWrap(False)
    except Exception:
        pass
    try:
        vh = table.verticalHeader()
    except Exception:
        return
    try:
        fm = QtGui.QFontMetrics(table.font())
        row_h = int(max(int(minimum), int(fm.height()) + int(padding)))
    except Exception:
        row_h = int(max(int(minimum), 22))
    try:
        vh.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
    except Exception:
        pass
    try:
        vh.setMinimumSectionSize(int(row_h))
    except Exception:
        pass
    try:
        vh.setDefaultSectionSize(int(row_h))
    except Exception:
        pass


def _set_air_flag_item_foreground(item: Optional[QtWidgets.QTableWidgetItem], air: bool) -> None:
    if item is None:
        return
    state = 1 if air else 0
    try:
        if int(item.data(_AIR_ITEM_STATE_ROLE) or -1) == state:
            return
    except Exception:
        pass
    try:
        item.setData(_AIR_ITEM_STATE_ROLE, state)
        item.setForeground(
            QtGui.QBrush(QtGui.QColor(255, 120, 120) if air else QtGui.QColor(120, 220, 140))
        )
    except Exception:
        pass


def _begin_qt_update_batch(widget: Optional[QtWidgets.QWidget]) -> list[tuple[QtWidgets.QWidget, bool]]:
    if widget is None:
        return []
    handles: list[tuple[QtWidgets.QWidget, bool]] = []
    targets: list[QtWidgets.QWidget] = [widget]
    try:
        viewport = widget.viewport() if hasattr(widget, "viewport") else None
    except Exception:
        viewport = None
    if viewport is not None and viewport is not widget:
        targets.append(viewport)

    seen: set[int] = set()
    for target in targets:
        if target is None:
            continue
        ident = id(target)
        if ident in seen:
            continue
        seen.add(ident)
        try:
            enabled = bool(target.updatesEnabled())
        except Exception:
            enabled = False
        try:
            if enabled:
                target.setUpdatesEnabled(False)
        except Exception:
            enabled = False
        handles.append((target, enabled))
    return handles


def _end_qt_update_batch(handles: list[tuple[QtWidgets.QWidget, bool]]) -> None:
    for target, enabled in reversed(handles):
        if not enabled:
            continue
        try:
            target.setUpdatesEnabled(True)
        except Exception:
            pass


def _call_with_qt_update_batch(widget: Any, fn: Callable[[], None]) -> None:
    # QGraphicsView scene-item updates are already coalesced well enough for our
    # animator hot path; toggling updatesEnabled() on the view/viewport each tick
    # only adds overhead and can force broader invalidation work.
    # Telemetry/detail container panels are mostly coordinators for child widgets;
    # toggling updatesEnabled() on the container each frame adds churn without
    # helping the already granular child-level updates. Trends/timeline canvases
    # are similarly self-contained and already coalesce their own repaint work well.
    if isinstance(
        widget,
        (
            QtWidgets.QGraphicsView,
            QtWidgets.QTableWidget,
            TelemetryPanel,
            CornerHeatmapPanel,
            ReceiverTankWidget,
            RoadProfilePanel,
            PressurePanel,
            FlowPanel,
            ValvePanel,
            TrendsPanel,
            EventTimelineWidget,
        ),
    ):
        fn()
        return
    handles = _begin_qt_update_batch(widget if isinstance(widget, QtWidgets.QWidget) else None)
    try:
        fn()
    finally:
        _end_qt_update_batch(handles)


def _ensure_corner_signal_cache(b: DataBundle) -> Dict[str, Dict[str, Any]]:
    key = "svc__corner_signal_cache"
    cached = b._derived.get(key)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    cache: Dict[str, Dict[str, Any]] = {}
    for c in CORNERS:
        road_arr = b.road_series(c)
        cache[str(c)] = {
            "zb": np.asarray(b.frame_corner_z(c, default=0.0), dtype=float),
            "vb": np.asarray(b.frame_corner_v(c, default=0.0), dtype=float),
            "ab": np.asarray(b.frame_corner_a(c, default=0.0), dtype=float),
            "zw": np.asarray(b.get(f"перемещение_колеса_{c}_м", 0.0), dtype=float),
            "vw": np.asarray(b.get(f"скорость_колеса_{c}_м_с", 0.0), dtype=float),
            "aw": np.asarray(b.get(f"ускорение_колеса_{c}_м_с2", 0.0), dtype=float),
            "zr": None if road_arr is None else np.asarray(road_arr, dtype=float),
            "stroke": np.asarray(b.get(f"положение_штока_{c}_м", 0.0), dtype=float),
            "tireF": np.asarray(b.get(f"нормальная_сила_шины_{c}_Н", 0.0), dtype=float),
            "air": np.asarray(b.get(f"колесо_в_воздухе_{c}", 0.0), dtype=float),
        }
    b._derived[key] = cache  # type: ignore[assignment]
    return cache


def _ensure_vertical_view_signal_cache(b: DataBundle, wheelbase_m: float) -> Dict[str, Any]:
    wb = float(max(0.0, wheelbase_m))
    key = f"svc__vertical_view_signal_cache__{wb:.6f}"
    cached = b._derived.get(key)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    frame_cache = {
        "z_com": np.asarray(b.get("перемещение_рамы_z_м", 0.0), dtype=float),
        "vz_com": np.asarray(b.get("скорость_рамы_z_м_с", 0.0), dtype=float),
        "az_com": np.asarray(b.get("ускорение_рамы_z_м_с2", 0.0), dtype=float),
    }
    try:
        s_world = np.asarray(b.ensure_s_world(), dtype=float)
    except Exception:
        s_world = np.zeros((0,), dtype=float)

    road_profiles: Dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for mode in ("center", "left", "right"):
        try:
            s_prof, z_prof = b.ensure_road_profile(wheelbase_m=wb, mode=mode)
            road_profiles[str(mode)] = (
                np.asarray(s_prof, dtype=float),
                np.asarray(z_prof, dtype=float),
            )
        except Exception:
            road_profiles[str(mode)] = (np.zeros((0,), dtype=float), np.zeros((0,), dtype=float))

    cache: Dict[str, Any] = {
        "corners": _ensure_corner_signal_cache(b),
        "frame": frame_cache,
        "s_world": s_world,
        "road_profiles": road_profiles,
    }
    b._derived[key] = cache  # type: ignore[assignment]
    return cache


def _road_profile_corner_offset_m(corner: str, wheelbase_m: float) -> float:
    return (+0.5 * float(wheelbase_m)) if (len(str(corner)) >= 2 and str(corner)[1] == "П") else (-0.5 * float(wheelbase_m))


def _ensure_road_profile_panel_cache(b: DataBundle, wheelbase_m: float) -> Dict[str, Any]:
    wb = float(max(0.0, wheelbase_m))
    key = f"svc__road_profile_panel_cache__{wb:.6f}"
    cached = b._derived.get(key)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    try:
        s_world = np.asarray(b.ensure_s_world(), dtype=float).reshape(-1)
    except Exception:
        s_world = np.zeros((0,), dtype=float)

    corners: Dict[str, Dict[str, Any]] = {}
    z_min = float("inf")
    z_max = float("-inf")
    have_finite = False

    for c in CORNERS:
        name = str(c)
        marker_x = float(_road_profile_corner_offset_m(name, wb))
        zr_full = b.road_series(name)
        if zr_full is None:
            corners[name] = {
                "x_world": np.zeros((0,), dtype=float),
                "z": np.zeros((0,), dtype=float),
                "marker_x": marker_x,
                "missing": True,
            }
            continue

        z_arr = np.asarray(zr_full, dtype=float).reshape(-1)
        n = int(min(s_world.size, z_arr.size))
        if n <= 0:
            corners[name] = {
                "x_world": np.zeros((0,), dtype=float),
                "z": np.zeros((0,), dtype=float),
                "marker_x": marker_x,
                "missing": True,
            }
            continue

        x_world = np.asarray(s_world[:n], dtype=float) + marker_x
        z_arr = np.asarray(z_arr[:n], dtype=float)
        corners[name] = {
            "x_world": x_world,
            "z": z_arr,
            "marker_x": marker_x,
            "missing": False,
        }

        try:
            finite = z_arr[np.isfinite(z_arr)]
        except Exception:
            finite = np.zeros((0,), dtype=float)
        if finite.size:
            z_min = min(z_min, float(np.nanmin(finite)))
            z_max = max(z_max, float(np.nanmax(finite)))
            have_finite = True

    if have_finite:
        pad = max(0.03, 0.15 * (z_max - z_min + 1e-9))
        y_range = (float(z_min - pad), float(z_max + pad))
    else:
        y_range = (-0.1, 0.1)

    cache: Dict[str, Any] = {
        "wheelbase_m": wb,
        "t": np.asarray(b.t, dtype=float).reshape(-1),
        "s_world": s_world,
        "corners": corners,
        "y_range": y_range,
    }
    b._derived[key] = cache  # type: ignore[assignment]
    return cache


def _ensure_telemetry_summary_cache(b: DataBundle) -> Dict[str, np.ndarray]:
    key = "svc__telemetry_summary_cache"
    cached = b._derived.get(key)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    def _series(name: str, default: float = 0.0) -> np.ndarray:
        return np.asarray(b.get(name, default), dtype=float).reshape(-1)

    cache: Dict[str, np.ndarray] = {
        "t": np.asarray(b.t, dtype=float).reshape(-1),
        "vx": _series("скорость_vx_м_с", 0.0),
        "vy": _series("скорость_vy_м_с", 0.0),
        "yaw": _series("yaw_рад", 0.0),
        "yaw_rate": _series("yaw_rate_рад_с", 0.0),
        "ax": _series("ускорение_продольное_ax_м_с2", 0.0),
        "ay": _series("ускорение_поперечное_ay_м_с2", 0.0),
        "roll": _series("крен_phi_рад", 0.0),
        "pitch": _series("тангаж_theta_рад", 0.0),
        "zcm": _series("перемещение_рамы_z_м", 0.0),
        "vzcm": _series("скорость_рамы_z_м_с", 0.0),
        "azcm": _series("ускорение_рамы_z_м_с2", 0.0),
    }
    b._derived[key] = cache  # type: ignore[assignment]
    return cache


def _shorten_display_name(name: str, limit: int = 34) -> str:
    text = str(name)
    max_len = int(max(4, limit))
    if len(text) <= max_len:
        return text
    keep = max(1, max_len - 3)
    return text[:keep] + "..."


def _kind_code_from_label(kind: str) -> int:
    normalized = str(kind).strip().lower()
    if normalized == "выхлоп":
        return 0
    if normalized == "подпитка":
        return 1
    if normalized == "заряд":
        return 2
    if normalized in ("обратный", "чек"):
        return 3
    return 4


def _top_descending_indices(values: Any, limit: int, *, threshold: float = 0.0) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    top_n = int(max(0, limit))
    if arr.size == 0 or top_n <= 0:
        return np.zeros((0,), dtype=int)

    active = np.flatnonzero(arr > float(threshold))
    if active.size == 0:
        return np.zeros((0,), dtype=int)

    scores = arr[active]
    top_n = min(top_n, int(scores.size))
    if top_n <= 0:
        return np.zeros((0,), dtype=int)
    if int(scores.size) <= top_n:
        order = np.argsort(-scores)
    else:
        part = np.argpartition(-scores, top_n - 1)[:top_n]
        order = part[np.argsort(-scores[part])]
    return np.asarray(active[order], dtype=int)


def _sample_series_local(
    series: Any,
    *,
    i0: int,
    i1: int,
    alpha: float,
    default: float = 0.0,
) -> float:
    try:
        arr = series if isinstance(series, np.ndarray) else np.asarray(series, dtype=float)
        n = int(arr.shape[0]) if getattr(arr, "ndim", 0) >= 1 else 0
        if n <= 0:
            return float(default)
        ii0 = max(0, min(int(i0), n - 1))
        ii1 = max(0, min(int(i1), n - 1))
        a = float(alpha)
        if ii0 == ii1 or a <= 1e-12:
            return float(arr[ii0])
        if a >= 1.0 - 1e-12:
            return float(arr[ii1])
        return float(
            _lerp_series_value(
                arr,
                i0=ii0,
                i1=ii1,
                alpha=a,
                default=float(default),
            )
        )
    except Exception:
        return float(default)


def _make_series_sampler(*, i0: int, i1: int, alpha: float) -> Callable[[Any, float], float]:
    def _sample(series: Any, default: float = 0.0) -> float:
        return _sample_series_local(series, i0=int(i0), i1=int(i1), alpha=float(alpha), default=float(default))

    return _sample


def _sample_series_avg2(
    sample: Callable[[Any, float], float],
    series_a: Any,
    series_b: Any,
    *,
    default: float = 0.0,
) -> float:
    return 0.5 * (
        float(sample(series_a, default))
        + float(sample(series_b, default))
    )


def _sample_point_local(
    rows_xyz: Any,
    *,
    i0: int,
    i1: int,
    alpha: float,
) -> Optional[np.ndarray]:
    try:
        return _lerp_point_row(
            np.asarray(rows_xyz, dtype=float),
            i0=int(i0),
            i1=int(i1),
            alpha=float(alpha),
        )
    except Exception:
        return None


def _elide_px(text: str, font: QtGui.QFont, max_px: int) -> str:
    """Обрезка строки по пиксельной ширине (Qt) — чтобы подписи не налезали друг на друга.

    В Qt это делает QFontMetrics.elidedText(). Используем в HUD‑подписях.
    """
    try:
        fm = QtGui.QFontMetrics(font)
        return fm.elidedText(str(text), QtCore.Qt.ElideRight, max(10, int(max_px)))
    except Exception:
        s = str(text)
        return s if len(s) <= 80 else (s[:79] + "…")



def _animator_warning_key(message: str, *, code: str, context: Dict[str, Any]) -> str:
    try:
        ctx_json = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        ctx_json = repr(sorted((str(k), repr(v)) for k, v in context.items()))
    return f"{code}|{str(message)}|{ctx_json}"


def _emit_animator_warning(message: str, *, code: str, **context: Any) -> None:
    """Best-effort warning logger for suspicious animator contract situations.

    Important: repeated identical warnings must not flood logs every frame.
    We log the first occurrence of each (code, message, normalized context)
    tuple and keep the root cause visible without generating thousands of
    duplicate records.
    """
    norm_context = {str(k): v for k, v in context.items()}
    warn_key = _animator_warning_key(str(message), code=str(code), context=norm_context)
    if warn_key in _ANIMATOR_WARNING_SEEN:
        return
    _ANIMATOR_WARNING_SEEN.add(warn_key)
    try:
        logger.warning(message)
    except Exception:
        pass
    try:
        from pneumo_solver_ui.diag.eventlog import get_global_logger

        get_global_logger(PROJECT_ROOT).emit(
            "AnimatorWarning",
            str(message),
            code=str(code),
            context=norm_context,
        )
    except Exception:
        pass


# SERVICE/DERIVED: visual ribbon width is derived from canonical geometry.
def _derive_visual_road_width_m(track_m: float, wheel_width_m: float) -> float:
    track_m = _safe_float(track_m, float("nan"))
    wheel_width_m = _safe_float(wheel_width_m, 0.0)
    if not (np.isfinite(track_m) and track_m > 0.0):
        return 0.0
    if not (np.isfinite(wheel_width_m) and wheel_width_m >= 0.0):
        wheel_width_m = 0.0
    return float(max(track_m, track_m + wheel_width_m))


def infer_geometry(meta: Dict[str, Any]) -> "ViewGeometry":
    """Read basic geometry for the animator from nested ``meta_json.geometry`` only.

    ABSOLUTE LAW:
      - no aliases ("база_м", "track", "wheel_radius", etc.)
      - no fallback to top-level meta/base/default_base
      - missing data stays missing and is surfaced via warnings / self-checks
    """
    meta = meta or {}
    vis_geom = read_visual_geometry_meta(
        meta,
        context="Desktop Animator NPZ meta_json",
        log=lambda m: _emit_animator_warning(
            f"[Animator] {m}",
            code="geometry_contract",
            contract_message=str(m),
        ),
    )

    wheelbase = vis_geom.get("wheelbase_m")
    track = vis_geom.get("track_m")
    wheel_radius = vis_geom.get("wheel_radius_m")
    wheel_width = vis_geom.get("wheel_width_m")
    frame_length = vis_geom.get("frame_length_m")
    frame_width = vis_geom.get("frame_width_m")
    frame_height = vis_geom.get("frame_height_m")
    road_width = vis_geom.get("road_width_m")
    cyl1_bore = vis_geom.get("cyl1_bore_diameter_m")
    cyl1_rod = vis_geom.get("cyl1_rod_diameter_m")
    cyl2_bore = vis_geom.get("cyl2_bore_diameter_m")
    cyl2_rod = vis_geom.get("cyl2_rod_diameter_m")
    cyl1_stroke_front = vis_geom.get("cyl1_stroke_front_m")
    cyl1_stroke_rear = vis_geom.get("cyl1_stroke_rear_m")
    cyl2_stroke_front = vis_geom.get("cyl2_stroke_front_m")
    cyl2_stroke_rear = vis_geom.get("cyl2_stroke_rear_m")
    dead_volume = vis_geom.get("dead_volume_chamber_m3")
    cyl1_outer = vis_geom.get("cyl1_outer_diameter_m")
    cyl2_outer = vis_geom.get("cyl2_outer_diameter_m")
    cyl1_dead_cap = vis_geom.get("cyl1_dead_cap_length_m")
    cyl1_dead_rod = vis_geom.get("cyl1_dead_rod_length_m")
    cyl2_dead_cap = vis_geom.get("cyl2_dead_cap_length_m")
    cyl2_dead_rod = vis_geom.get("cyl2_dead_rod_length_m")
    cylinder_wall_thickness = vis_geom.get("cylinder_wall_thickness_m")
    cyl1_dead_height = vis_geom.get("cyl1_dead_height_m")
    cyl2_dead_height = vis_geom.get("cyl2_dead_height_m")
    cyl1_body_front = vis_geom.get("cyl1_body_length_front_m")
    cyl1_body_rear = vis_geom.get("cyl1_body_length_rear_m")
    cyl2_body_front = vis_geom.get("cyl2_body_length_front_m")
    cyl2_body_rear = vis_geom.get("cyl2_body_length_rear_m")

    if wheelbase is None:
        wheelbase = 0.0
        _emit_animator_warning(
            "[Animator] wheelbase_m отсутствует/некорректен в meta_json.geometry → база визуализации установлена в 0.0 м. Исправьте exporter.",
            code="missing_wheelbase_m",
        )

    if track is None:
        track = 0.0
        _emit_animator_warning(
            "[Animator] track_m отсутствует/некорректен в meta_json.geometry → колея визуализации установлена в 0.0 м. Исправьте exporter.",
            code="missing_track_m",
        )

    if wheel_radius is None:
        wheel_radius = 0.0
        _emit_animator_warning(
            "[Animator] wheel_radius_m отсутствует/некорректен в meta_json.geometry → радиус колеса установлен в 0.0 м. Исправьте exporter.",
            code="missing_wheel_radius_m",
        )

    if wheel_width is None:
        wheel_width = 0.0
        _emit_animator_warning(
            "[Animator] wheel_width_m отсутствует/некорректен в meta_json.geometry → ширина колеса отключена (0.0 м, без скрытых дефолтов).",
            code="missing_wheel_width_m",
            meta_keys=sorted(meta.keys()) if isinstance(meta, dict) else [],
        )

    if frame_length is None:
        frame_length = 0.0
        _emit_animator_warning(
            "[Animator] frame_length_m отсутствует/некорректен в meta_json.geometry → 3D-рама не будет дорисовываться скрытым дефолтом. Исправьте exporter/base.",
            code="missing_frame_length_m",
        )

    if frame_width is None:
        frame_width = 0.0
        _emit_animator_warning(
            "[Animator] frame_width_m отсутствует/некорректен в meta_json.geometry → 3D-рама не будет дорисовываться скрытым дефолтом. Исправьте exporter/base.",
            code="missing_frame_width_m",
        )

    if frame_height is None:
        frame_height = 0.0
        _emit_animator_warning(
            "[Animator] frame_height_m отсутствует/некорректен в meta_json.geometry → 3D-рама не будет дорисовываться скрытым дефолтом. Исправьте exporter/base.",
            code="missing_frame_height_m",
        )

    if road_width is None:
        road_width = _derive_visual_road_width_m(float(track), float(wheel_width))
        if road_width > 0.0:
            _emit_animator_warning(
                f"[Animator] road_width_m отсутствует/некорректен в meta_json.geometry → использована SERVICE/DERIVED ширина ленты дороги {road_width:.6g} м из track_m + wheel_width_m.",
                code="derived_road_width_m",
                track_m=float(track),
                wheel_width_m=float(wheel_width),
                derived_road_width_m=float(road_width),
            )
        else:
            _emit_animator_warning(
                "[Animator] road_width_m отсутствует/некорректен в meta_json.geometry, а track_m тоже недоступен → ширина ленты дороги установлена в 0.0 м.",
                code="missing_road_width_m",
                track_m=float(track),
                wheel_width_m=float(wheel_width),
            )

    cyl1_any = any(v is not None for v in (cyl1_bore, cyl1_rod, cyl1_stroke_front, cyl1_stroke_rear, dead_volume))
    cyl2_any = any(v is not None for v in (cyl2_bore, cyl2_rod, cyl2_stroke_front, cyl2_stroke_rear, dead_volume))
    if cyl1_any and cyl1_outer is None:
        _emit_animator_warning(
            "[Animator] C1 packaging contract is incomplete in meta_json.geometry: missing 'cyl1_outer_diameter_m' → honest 3D body/rod/piston for C1 stay disabled until exporter supplies explicit packaging geometry.",
            code="missing_cyl1_outer_diameter_m",
        )
    if cyl2_any and cyl2_outer is None:
        _emit_animator_warning(
            "[Animator] C2 packaging contract is incomplete in meta_json.geometry: missing 'cyl2_outer_diameter_m' → honest 3D body/rod/piston for C2 stay disabled until exporter supplies explicit packaging geometry.",
            code="missing_cyl2_outer_diameter_m",
        )
    if cyl1_any and (cyl1_dead_cap is None or cyl1_dead_rod is None):
        _emit_animator_warning(
            "[Animator] C1 packaging contract is incomplete in meta_json.geometry: missing dead-length keys ('cyl1_dead_cap_length_m'/'cyl1_dead_rod_length_m').",
            code="missing_cyl1_dead_lengths",
        )
    if cylinder_wall_thickness is None:
        for _bore, _outer in ((cyl1_bore, cyl1_outer), (cyl2_bore, cyl2_outer)):
            if _bore is not None and _outer is not None:
                _wt = 0.5 * (float(_outer) - float(_bore))
                if _wt >= 0.0 and math.isfinite(_wt):
                    cylinder_wall_thickness = float(_wt)
                    break

    if cyl1_dead_height is None and cyl1_dead_cap is not None:
        cyl1_dead_height = float(cyl1_dead_cap)
    if cyl2_dead_height is None and cyl2_dead_cap is not None:
        cyl2_dead_height = float(cyl2_dead_cap)

    def _derive_body_len(stroke_val, dead_h_val):
        if stroke_val is None or dead_h_val is None or cylinder_wall_thickness is None:
            return None
        try:
            return float(float(stroke_val) + 2.0 * float(dead_h_val) + 2.0 * float(cylinder_wall_thickness))
        except Exception:
            return None

    if cyl1_body_front is None:
        cyl1_body_front = _derive_body_len(cyl1_stroke_front, cyl1_dead_height)
    if cyl1_body_rear is None:
        cyl1_body_rear = _derive_body_len(cyl1_stroke_rear, cyl1_dead_height)
    if cyl2_body_front is None:
        cyl2_body_front = _derive_body_len(cyl2_stroke_front, cyl2_dead_height)
    if cyl2_body_rear is None:
        cyl2_body_rear = _derive_body_len(cyl2_stroke_rear, cyl2_dead_height)

    return ViewGeometry(
        wheelbase=float(wheelbase),
        track=float(track),
        wheel_radius=float(wheel_radius),
        wheel_width=float(wheel_width),
        frame_length=float(frame_length),
        frame_width=float(frame_width),
        frame_height=float(frame_height),
        road_width=float(road_width),
        cyl1_bore_diameter=float(_safe_float(cyl1_bore, 0.0)),
        cyl1_rod_diameter=float(_safe_float(cyl1_rod, 0.0)),
        cyl2_bore_diameter=float(_safe_float(cyl2_bore, 0.0)),
        cyl2_rod_diameter=float(_safe_float(cyl2_rod, 0.0)),
        cyl1_stroke_front=float(_safe_float(cyl1_stroke_front, 0.0)),
        cyl1_stroke_rear=float(_safe_float(cyl1_stroke_rear, 0.0)),
        cyl2_stroke_front=float(_safe_float(cyl2_stroke_front, 0.0)),
        cyl2_stroke_rear=float(_safe_float(cyl2_stroke_rear, 0.0)),
        dead_volume_chamber=float(_safe_float(dead_volume, 0.0)),
        cyl1_outer_diameter=float(_safe_float(cyl1_outer, 0.0)),
        cyl2_outer_diameter=float(_safe_float(cyl2_outer, 0.0)),
        cyl1_dead_cap_length=float(_safe_float(cyl1_dead_cap, 0.0)),
        cyl1_dead_rod_length=float(_safe_float(cyl1_dead_rod, 0.0)),
        cyl2_dead_cap_length=float(_safe_float(cyl2_dead_cap, 0.0)),
        cyl2_dead_rod_length=float(_safe_float(cyl2_dead_rod, 0.0)),
        cylinder_wall_thickness=float(_safe_float(cylinder_wall_thickness, 0.0)),
        cyl1_dead_height=float(_safe_float(cyl1_dead_height, 0.0)),
        cyl2_dead_height=float(_safe_float(cyl2_dead_height, 0.0)),
        cyl1_body_length_front=float(_safe_float(cyl1_body_front, 0.0)),
        cyl1_body_length_rear=float(_safe_float(cyl1_body_rear, 0.0)),
        cyl2_body_length_front=float(_safe_float(cyl2_body_front, 0.0)),
        cyl2_body_length_rear=float(_safe_float(cyl2_body_rear, 0.0)),
    )


def _qt_color(rgb: Tuple[int, int, int], a: int = 255) -> QtGui.QColor:
    r, g, b = rgb
    return QtGui.QColor(int(r), int(g), int(b), int(a))


def _heat_rgb(u: float, *, sat: float = 0.95, val: float = 0.95) -> Tuple[int, int, int]:
    """Blue→Red heat color for u in [0..1]."""
    u = float(_clamp(float(u), 0.0, 1.0))
    # HSV hue: 0.66 (~240° blue) -> 0.0 (red)
    h = (1.0 - u) * 0.66
    r, g, b = colorsys.hsv_to_rgb(h, float(sat), float(val))
    return int(r * 255), int(g * 255), int(b * 255)


def _bg_text_rgb(bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Choose black/white text color for readability on given background."""
    r, g, b = [max(0, min(255, int(x))) for x in bg]
    # relative luminance (sRGB)
    lum = 0.2126 * (r / 255.0) + 0.7152 * (g / 255.0) + 0.0722 * (b / 255.0)
    return (0, 0, 0) if lum > 0.60 else (255, 255, 255)


def _robust_max_abs(arr: Any, *, q: float = 95.0) -> float:
    """Robust max(|x|) via percentile (avoids single spikes)."""
    try:
        a = np.asarray(arr, dtype=float)
        a = a[np.isfinite(a)]
        if a.size == 0:
            return 0.0
        return float(np.nanpercentile(np.abs(a), float(q)))
    except Exception:
        return 0.0


# -----------------------------
# Pointer watcher (follow mode)
# -----------------------------


class PointerWatcher(QtCore.QObject):
    npz_changed = QtCore.Signal(Path)
    status = QtCore.Signal(str)

    def __init__(self, pointer_path: Path, *, poll_ms: int = 500):
        super().__init__()
        self.pointer_path = Path(pointer_path)
        self._last_pointer_sig: Optional[Tuple[bool, int, int]] = None
        self._last_npz: Optional[str] = None
        self._last_npz_sig: Optional[Tuple[bool, int, int]] = None
        self._last_road_path: Optional[Path] = None
        self._last_road_sig: Optional[Tuple[bool, int, int]] = None
        self._last_deps_token: str = ""
        self._current_npz: Optional[Path] = None

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(int(poll_ms))
        self._timer.timeout.connect(self._poll)

    @staticmethod
    def _file_sig(path: Path) -> Tuple[bool, int, int]:
        try:
            p = Path(path)
        except Exception:
            return (False, 0, 0)
        if not p.exists():
            return (False, 0, 0)
        try:
            st = p.stat()
            return (True, int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return (True, 0, 0)

    def _resolve_pointer_npz(self) -> Optional[Path]:
        if not self.pointer_path.exists():
            return None
        obj = json.loads(self.pointer_path.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(obj, dict):
            return None
        p = obj.get("npz_path") or obj.get("path") or obj.get("file")
        if not isinstance(p, str) or not p.strip():
            return None
        npz_path = Path(p.strip())
        if not npz_path.is_absolute():
            npz_path = (self.pointer_path.parent / npz_path).resolve()
        return npz_path

    def _collect_follow_deps(self, npz_path: Path) -> Dict[str, object]:
        return collect_visual_cache_dependencies(
            npz_path,
            context="Desktop Animator follow",
            log=lambda m: logger.warning("[Animator] %s", m),
        )

    def start(self):
        self._timer.start()
        self.status.emit(f"Follow: {self.pointer_path}")

    def stop(self):
        self._timer.stop()

    def _poll(self):
        try:
            pointer_sig = self._file_sig(self.pointer_path)
            pointer_changed = pointer_sig != self._last_pointer_sig
            if pointer_changed:
                self._last_pointer_sig = pointer_sig
                resolved = self._resolve_pointer_npz()
                if resolved is not None:
                    self._current_npz = resolved

            if self._current_npz is None:
                resolved = self._resolve_pointer_npz()
                if resolved is None:
                    return
                self._current_npz = resolved

            npz_path = self._current_npz
            if npz_path is None:
                return
            if not npz_path.exists():
                self.status.emit(f"NPZ missing: {npz_path}")
                return
            npz_sig = self._file_sig(npz_path)
            cached_road_sig = self._file_sig(self._last_road_path)
            if (
                not pointer_changed
                and str(npz_path) == str(self._last_npz or "")
                and npz_sig == self._last_npz_sig
                and cached_road_sig == self._last_road_sig
            ):
                return

            deps = self._collect_follow_deps(npz_path)
            deps_token = visual_cache_dependencies_token(deps) or str(npz_path)
            road_path_raw = str(deps.get("road_csv_path") or "").strip()
            road_path = Path(road_path_raw) if road_path_raw else None
            road_sig = self._file_sig(road_path)
            deps_changed = (
                deps_token != self._last_deps_token
                or str(npz_path) != str(self._last_npz or "")
                or npz_sig != self._last_npz_sig
                or road_path != self._last_road_path
                or road_sig != self._last_road_sig
            )
            if not deps_changed:
                return

            reasons: List[str] = []
            if pointer_changed:
                reasons.append("pointer")
            if self._last_deps_token:
                reasons.append("deps")
            reason_text = "+".join(reasons) if reasons else "init"

            self._last_deps_token = deps_token
            self._last_npz = str(npz_path)
            self._last_npz_sig = npz_sig
            self._last_road_path = road_path
            self._last_road_sig = road_sig
            self.status.emit(f"Reload ({reason_text}): {npz_path.name}")
            self.npz_changed.emit(npz_path)
        except Exception as e:
            self.status.emit(f"Follow error: {e}")

# -----------------------------
# 2D Arrow helper
# -----------------------------


class Arrow2D(QtCore.QObject):
    """Gradient arrow (body line + head polygon)."""

    def __init__(self, scene: QtWidgets.QGraphicsScene, *, width_m: float = 0.03, gradient_body: bool = False):
        super().__init__()
        self.scene = scene
        self.width_m = float(width_m)
        self.gradient_body = bool(gradient_body)
        self.body = QtWidgets.QGraphicsLineItem()
        self.head = QtWidgets.QGraphicsPolygonItem()
        self.body.setZValue(10)
        self.head.setZValue(11)
        self.scene.addItem(self.body)
        self.scene.addItem(self.head)
        self._hidden = False
        self._last_body_style_key: Optional[tuple[Any, ...]] = None
        self._last_head_style_key: Optional[tuple[Any, ...]] = None
        self._last_geom_key: Optional[tuple[Any, ...]] = None
        self.hide()

    def hide(self):
        if self._hidden:
            return
        self._hidden = True
        self.body.setVisible(False)
        self.head.setVisible(False)

    def show(self):
        if not self._hidden:
            return
        self._hidden = False
        self.body.setVisible(True)
        self.head.setVisible(True)

    @staticmethod
    def _geom_key(
        p0: QtCore.QPointF,
        p1: QtCore.QPointF,
        *,
        head_len_m: float,
        head_w_m: float,
    ) -> tuple[int, int, int, int, int, int]:
        return (
            int(round(float(p0.x()) * 10000.0)),
            int(round(float(p0.y()) * 10000.0)),
            int(round(float(p1.x()) * 10000.0)),
            int(round(float(p1.y()) * 10000.0)),
            int(round(float(head_len_m) * 10000.0)),
            int(round(float(head_w_m) * 10000.0)),
        )

    def _apply_body_style(
        self,
        p0: QtCore.QPointF,
        p1: QtCore.QPointF,
        *,
        rgb: Tuple[int, int, int],
        alpha: int,
        width_m: float,
    ) -> None:
        if bool(self.gradient_body):
            body_style_key = ("gradient", tuple(int(v) for v in rgb), int(alpha), round(float(width_m), 5), self._geom_key(p0, p1, head_len_m=0.0, head_w_m=0.0))
            if body_style_key == self._last_body_style_key:
                return
            grad = QtGui.QLinearGradient(p0, p1)
            c_end = _qt_color(rgb, a=int(alpha))
            c0 = _qt_color(rgb, a=0)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c_end)
            pen = QtGui.QPen(QtGui.QBrush(grad), float(width_m))
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            self.body.setPen(pen)
            self._last_body_style_key = body_style_key
            return

        body_style_key = ("solid", tuple(int(v) for v in rgb), int(alpha), round(float(width_m), 5))
        if body_style_key == self._last_body_style_key:
            return
        pen = QtGui.QPen(_qt_color(rgb, a=int(alpha)), float(width_m))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        self.body.setPen(pen)
        self._last_body_style_key = body_style_key

    def _apply_head_style(self, *, rgb: Tuple[int, int, int], alpha: int, width_m: float) -> None:
        head_style_key = (tuple(int(v) for v in rgb), int(alpha), round(float(width_m), 5))
        if head_style_key == self._last_head_style_key:
            return
        color = _qt_color(rgb, a=int(alpha))
        self.head.setPen(QtGui.QPen(color, max(0.001, float(width_m) * 0.2)))
        self.head.setBrush(QtGui.QBrush(color))
        self._last_head_style_key = head_style_key

    def set_arrow(
        self,
        p0: QtCore.QPointF,
        p1: QtCore.QPointF,
        *,
        rgb: Tuple[int, int, int] = (80, 200, 120),
        alpha: int = 220,
        head_len_m: float = 0.10,
        head_w_m: float = 0.07,
    ):
        v = QtCore.QPointF(p1.x() - p0.x(), p1.y() - p0.y())
        L = float((v.x() ** 2 + v.y() ** 2) ** 0.5)
        if L < 1e-6:
            self.hide()
            return

        self.show()

        # Unit dir
        ux, uy = v.x() / L, v.y() / L
        # Perp
        px, py = -uy, ux

        head_len = float(head_len_m)
        head_w = float(head_w_m)
        w = float(self.width_m)

        # Body segment ends before head
        body_end = QtCore.QPointF(p1.x() - ux * head_len, p1.y() - uy * head_len)
        self._apply_body_style(p0, p1, rgb=rgb, alpha=alpha, width_m=w)
        self._apply_head_style(rgb=rgb, alpha=alpha, width_m=w)

        # Head triangle
        tip = p1
        left = QtCore.QPointF(body_end.x() + px * (0.5 * head_w), body_end.y() + py * (0.5 * head_w))
        right = QtCore.QPointF(body_end.x() - px * (0.5 * head_w), body_end.y() - py * (0.5 * head_w))
        geom_key = self._geom_key(p0, p1, head_len_m=head_len, head_w_m=head_w)
        if geom_key != self._last_geom_key:
            self.body.setLine(QtCore.QLineF(p0, body_end))
            self.head.setPolygon(QtGui.QPolygonF([tip, left, right]))
            self._last_geom_key = geom_key


# -----------------------------
# 2D Views
# -----------------------------


@dataclass
class ViewGeometry:
    """Minimal vehicle geometry used by visualizers.

    All values are in meters.
    """

    # Empty-view placeholders before a valid bundle is loaded.
    wheelbase: float = 0.0
    track: float = 0.0

    # Wheel size (used for consistent, proportional rendering)
    wheel_radius: float = 0.0
    # If wheel_width is unknown, keep it disabled (0.0) instead of inventing 0.22.
    wheel_width: float = 0.0

    # Frame / body dimensions.
    # IMPORTANT: these are body dimensions, not the clearance above road.
    frame_length: float = 0.0
    frame_width: float = 0.0
    frame_height: float = 0.0

    # SERVICE/DERIVED visual ribbon width (meters).
    road_width: float = 0.0

    # Optional cylinder visual contract (all values in meters).
    cyl1_bore_diameter: float = 0.0
    cyl1_rod_diameter: float = 0.0
    cyl2_bore_diameter: float = 0.0
    cyl2_rod_diameter: float = 0.0
    cyl1_stroke_front: float = 0.0
    cyl1_stroke_rear: float = 0.0
    cyl2_stroke_front: float = 0.0
    cyl2_stroke_rear: float = 0.0
    dead_volume_chamber: float = 0.0
    cyl1_outer_diameter: float = 0.0
    cyl2_outer_diameter: float = 0.0
    cyl1_dead_cap_length: float = 0.0
    cyl1_dead_rod_length: float = 0.0
    cyl2_dead_cap_length: float = 0.0
    cyl2_dead_rod_length: float = 0.0
    cylinder_wall_thickness: float = 0.0
    cyl1_dead_height: float = 0.0
    cyl2_dead_height: float = 0.0
    cyl1_body_length_front: float = 0.0
    cyl1_body_length_rear: float = 0.0
    cyl2_body_length_front: float = 0.0
    cyl2_body_length_rear: float = 0.0

    @property
    def x_pos(self) -> np.ndarray:
        wb = float(self.wheelbase)
        return np.array([+wb / 2, +wb / 2, -wb / 2, -wb / 2], dtype=float)

    @property
    def y_pos(self) -> np.ndarray:
        tr = float(self.track)
        return np.array([+tr / 2, -tr / 2, +tr / 2, -tr / 2], dtype=float)



class FrontViewWidget(QtWidgets.QGraphicsView):
    """Axle (left-right) view: roll + vertical motion.

    By default shows the *front* axle (ЛП/ПП). For the rear axle use:
        FrontViewWidget(axle="rear")  # ЛЗ/ПЗ

    R50 upgrades:
    - optional velocity arrows (vz) in addition to acceleration arrows (az)
    - optional numeric labels near each arrow (magnitude + sign)
    - runtime toggles via TelemetryPanel (no hotkeys required)

    R52 upgrades:
    - axle selector (front/rear) so we can show both axles simultaneously.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, axle: str = "front"):
        super().__init__(parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(14, 18, 22)))
        # We manage scaling explicitly; keep the view clean.
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setAlignment(QtCore.Qt.AlignCenter)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        # Perf: scenes with many animated items are faster with NoIndex
        try:
            self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        except Exception:
            pass
        try:
            self.setViewportUpdateMode(QtWidgets.QGraphicsView.BoundingRectViewportUpdate)
            self.setOptimizationFlag(QtWidgets.QGraphicsView.DontSavePainterState, True)
            self.setOptimizationFlag(QtWidgets.QGraphicsView.DontAdjustForAntialiasing, True)
        except Exception:
            pass

        # Items
        self.road = QtWidgets.QGraphicsLineItem()
        self.body = QtWidgets.QGraphicsLineItem()
        self.susp_l = QtWidgets.QGraphicsLineItem()
        self.susp_r = QtWidgets.QGraphicsLineItem()

        # Wheels: for front/rear view draw as rectangles (not circles)
        self.wheel_l = QtWidgets.QGraphicsRectItem()
        self.wheel_r = QtWidgets.QGraphicsRectItem()
        self.com = QtWidgets.QGraphicsEllipseItem()

        # Road reference levels
        self.road_zero = QtWidgets.QGraphicsLineItem()  # z=0 reference
        self.road_lvl_l = QtWidgets.QGraphicsLineItem()  # road under left wheel
        self.road_lvl_r = QtWidgets.QGraphicsLineItem()  # road under right wheel

        # Arrows: acceleration
        self.arrow_a_com = Arrow2D(self.scene, width_m=0.02)
        self.arrow_a_body_l = Arrow2D(self.scene, width_m=0.02)
        self.arrow_a_body_r = Arrow2D(self.scene, width_m=0.02)
        self.arrow_a_wheel_l = Arrow2D(self.scene, width_m=0.015)
        self.arrow_a_wheel_r = Arrow2D(self.scene, width_m=0.015)

        # Arrows: velocity (optional)
        self.arrow_v_com = Arrow2D(self.scene, width_m=0.012)
        self.arrow_v_body_l = Arrow2D(self.scene, width_m=0.012)
        self.arrow_v_body_r = Arrow2D(self.scene, width_m=0.012)
        self.arrow_v_wheel_l = Arrow2D(self.scene, width_m=0.010)
        self.arrow_v_wheel_r = Arrow2D(self.scene, width_m=0.010)

        # Labels (optional)
        self.lab_com = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_body_l = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_body_r = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_wheel_l = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_wheel_r = _make_graphics_label_item(self.scene, font_size=8)

        # Reference road lines behind everything
        for it in (self.road_zero, self.road_lvl_l, self.road_lvl_r):
            it.setZValue(0)
            self.scene.addItem(it)

        for it in [self.road, self.body]:
            it.setZValue(1)
            self.scene.addItem(it)
        for it in [self.susp_l, self.susp_r, self.wheel_l, self.wheel_r, self.com]:
            it.setZValue(2)
            self.scene.addItem(it)

        # Style
        pen_zero = QtGui.QPen(QtGui.QColor(60, 70, 80), 0.01, QtCore.Qt.DashLine)
        pen_zero.setCosmetic(True)
        self.road_zero.setPen(pen_zero)

        pen_lvl = QtGui.QPen(QtGui.QColor(120, 120, 120), 0.012)
        pen_lvl.setCosmetic(True)
        self.road_lvl_l.setPen(pen_lvl)
        self.road_lvl_r.setPen(pen_lvl)

        self.road.setPen(QtGui.QPen(QtGui.QColor(90, 90, 90), 0.01))
        self.body.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 0.02))

        for ln in [self.susp_l, self.susp_r]:
            ln.setPen(QtGui.QPen(QtGui.QColor(150, 160, 170), 0.01, QtCore.Qt.DashLine))

        for wh in [self.wheel_l, self.wheel_r]:
            wh.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 0.02))
            wh.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60)))

        self.com.setPen(QtGui.QPen(QtGui.QColor(240, 200, 80), 0.02))
        self.com.setBrush(QtGui.QBrush(QtGui.QColor(240, 200, 80)))

        # Scene transform: meters -> pixels, flip Y so +z is up.
        # `_base_px_per_m` is the automatic scale chosen by the cockpit; `_user_zoom`
        # is an explicit mouse override and survives future auto-scale updates.
        self._px_per_m = 260.0
        self._base_px_per_m = float(self._px_per_m)
        self._user_zoom = 1.0
        self._set_transform()

        self.geom = ViewGeometry()

        self.axle = str(axle).lower().strip() or "front"
        if self.axle.startswith("r"):
            self.cL, self.cR = "ЛЗ", "ПЗ"
        else:
            self.cL, self.cR = "ЛП", "ПП"

        # Visual config (runtime)
        self._accel_scale = 0.05  # m per (m/s^2)
        self._vel_scale = 0.08    # m per (m/s)
        self.show_accel = True
        self.show_vel = False
        self.show_labels = True
        self.show_dims = False
        self.show_scale_bar = True
        self.show_dims = False
        self.show_scale_bar = True
        self._playback_perf_mode = False
        self._compact_dock_mode = False
        self._compact_max_height = 176
        self._render_hints_normal = QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing
        self._render_hints_compact = QtGui.QPainter.TextAntialiasing
        self._render_hints_perf = QtGui.QPainter.RenderHints()
        self._bundle_key: Optional[int] = None
        self._signal_cache: Dict[str, Any] = {}
        self._apply_render_hint_policy()

    def set_px_per_m(self, px_per_m: float):
        self._base_px_per_m = float(px_per_m)
        self._px_per_m = float(self._base_px_per_m) * float(max(0.1, self._user_zoom))
        self._set_transform()

    def reset_user_zoom(self) -> None:
        self._user_zoom = 1.0
        self._px_per_m = float(self._base_px_per_m)
        self._set_transform()

    def _set_transform(self):
        tr = QtGui.QTransform()
        tr.scale(self._px_per_m, -self._px_per_m)
        self.setTransform(tr)

    def wheelEvent(self, event: QtGui.QWheelEvent):  # type: ignore[override]
        delta = 0
        try:
            delta = int(event.angleDelta().y())
        except Exception:
            delta = 0
        if delta:
            step = 1.12 if delta > 0 else (1.0 / 1.12)
            self._user_zoom = float(_clamp(self._user_zoom * step, 0.35, 6.0))
            self._px_per_m = float(self._base_px_per_m) * float(self._user_zoom)
            self._set_transform()
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):  # type: ignore[override]
        self.reset_user_zoom()
        try:
            event.accept()
        except Exception:
            pass
        return

    def set_geometry(self, geom: ViewGeometry):
        self.geom = geom

    def set_bundle(self, b: DataBundle) -> None:
        self._bundle_key = id(b)
        self._signal_cache = _ensure_vertical_view_signal_cache(b, float(self.geom.wheelbase))

    def set_scales(self, accel_scale: float, vel_scale: float):
        self._accel_scale = float(accel_scale)
        self._vel_scale = float(vel_scale)

    def set_visual(
        self,
        *,
        show_accel: Optional[bool] = None,
        show_vel: Optional[bool] = None,
        show_labels: Optional[bool] = None,
        show_dims: Optional[bool] = None,
        show_scale_bar: Optional[bool] = None,
    ):
        if show_accel is not None:
            self.show_accel = bool(show_accel)
        if show_vel is not None:
            self.show_vel = bool(show_vel)
        if show_labels is not None:
            self.show_labels = bool(show_labels)
        if show_dims is not None:
            self.show_dims = bool(show_dims)
        if show_scale_bar is not None:
            self.show_scale_bar = bool(show_scale_bar)

    def set_playback_perf_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == bool(self._playback_perf_mode):
            return
        self._playback_perf_mode = enabled
        self._apply_render_hint_policy()
        try:
            self.viewport().update()
        except Exception:
            pass

    def _apply_render_hint_policy(self) -> None:
        if bool(self._playback_perf_mode):
            hints = self._render_hints_perf
        elif bool(self._compact_dock_mode):
            hints = self._render_hints_compact
        else:
            hints = self._render_hints_normal
        try:
            self.setRenderHints(hints)
        except Exception:
            pass

    def set_compact_dock_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(getattr(self, "_compact_dock_mode", False)):
            return
        self._compact_dock_mode = compact
        self._apply_render_hint_policy()
        max_h = int(self._compact_max_height) if compact else 16777215
        vpol = QtWidgets.QSizePolicy.Maximum if compact else QtWidgets.QSizePolicy.Expanding
        try:
            self.setMaximumHeight(max_h)
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
        except Exception:
            pass
        try:
            self.updateGeometry()
            self.viewport().update()
        except Exception:
            pass

    def drawForeground(self, painter: QtGui.QPainter, rect: QtCore.QRectF):  # type: ignore
        """Overlay in viewport coordinates (fixed-size, no overlaps)."""
        super().drawForeground(painter, rect)

        eff_show_dims = bool(self.show_dims) and not bool(self._playback_perf_mode)
        eff_show_scale_bar = bool(self.show_scale_bar) and not bool(self._playback_perf_mode)
        if not (eff_show_dims or eff_show_scale_bar):
            return

        painter.save()
        painter.resetTransform()  # switch to viewport pixels

        w = self.viewport().width()
        h = self.viewport().height()
        m = 10

        # --- scale bar ---
        if eff_show_scale_bar and self._px_per_m > 1e-6:
            # choose a "nice" bar length so it stays readable across resizes
            target_px = max(60, min(160, int(0.22 * w)))
            nice_m = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
            bar_m = 1.0
            for v in nice_m:
                if v * self._px_per_m >= target_px:
                    bar_m = v
                    break
            bar_px = int(bar_m * self._px_per_m)

            x0 = m
            y0 = h - m
            painter.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 2))
            painter.drawLine(x0, y0, x0 + bar_px, y0)
            painter.drawLine(x0, y0 - 6, x0, y0 + 6)
            painter.drawLine(x0 + bar_px, y0 - 6, x0 + bar_px, y0 + 6)
            painter.setPen(QtGui.QPen(QtGui.QColor(230, 230, 230), 1))
            painter.drawText(x0, y0 - 8, f"{bar_m:g} м")

        # --- geometry overlay ---
        if eff_show_dims:
            txt = (
                f"Геометрия (м):\n"
                f"  Колея W = {self.geom.track:.3f}\n"
                f"  Радиус колеса R = {self.geom.wheel_radius:.3f}"
            )
            fm = painter.fontMetrics()
            lines = txt.split("\n")
            line_h = fm.height()
            box_w = max(fm.horizontalAdvance(s) for s in lines) + 2 * m
            box_h = line_h * len(lines) + 2 * m
            x = w - box_w - m
            y = m
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 0, 0, 150))
            painter.drawRoundedRect(QtCore.QRectF(x, y, box_w, box_h), 6, 6)
            painter.setPen(QtGui.QPen(QtGui.QColor(240, 240, 240), 1))
            for k, s in enumerate(lines):
                painter.drawText(x + m, y + m + (k + 1) * line_h - fm.descent(), s)

        painter.restore()

    def _hide_all(self):
        for a in (
            self.arrow_a_com, self.arrow_a_body_l, self.arrow_a_body_r, self.arrow_a_wheel_l, self.arrow_a_wheel_r,
            self.arrow_v_com, self.arrow_v_body_l, self.arrow_v_body_r, self.arrow_v_wheel_l, self.arrow_v_wheel_r,
        ):
            a.hide()
        for lab in (self.lab_com, self.lab_body_l, self.lab_body_r, self.lab_wheel_l, self.lab_wheel_r):
            lab.setVisible(False)


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def _clear_segment_markers(self) -> None:
        try:
            for it in getattr(self, "_seg_marker_items", []) or []:
                try:
                    self.scene.removeItem(it)
                except Exception:
                    pass
        finally:
            self._seg_marker_items = []

    def _ensure_segment_cache(self, b: DataBundle) -> None:
        """Кэш сегментов теста.

        Источники:
        - предпочитаем колонку сегмент_id/segment_id, если она есть;
        - иначе — единый сегмент (0).

        В кэше держим границы сегментов в индексах, базовую статистику и строки
        для tooltips/лейблов. Это используется для:
        - подписи «где именно по тесту мы сейчас»;
        - отрисовки маркеров границ сегментов на карте.
        """
        # Привязываемся к массиву main_values: при загрузке нового .npz поменяется id.
        try:
            key = (id(b.main_values), int(b.main_values.shape[0]))
        except Exception:
            key = id(b)

        if key == self._seg_cache_key:
            return
        self._seg_cache_key = key

        t = b.t
        n = int(len(t))

        # 1) Сегмент id
        seg = b.get("сегмент_id", None)

        if seg is None:
            seg = np.zeros(n, dtype=np.int32)
        else:
            seg = np.asarray(seg)
            if seg.shape[0] != n:
                try:
                    seg = np.resize(seg, n)
                except Exception:
                    seg = np.zeros(n, dtype=np.int32)
            if seg.dtype.kind in ("f", "c"):
                seg = np.rint(seg).astype(np.int32, copy=False)
            else:
                seg = seg.astype(np.int32, copy=False)

        self._seg_id = seg

        if n <= 0:
            self._seg_starts = np.array([0], dtype=np.int32)
            self._seg_ends = np.array([0], dtype=np.int32)
            self._seg_ids = np.array([0], dtype=np.int32)
            self._seg_start_to_idx = {0: 0}
            self._seg_infos = []
            return

        # 2) Границы сегментов
        transitions = np.flatnonzero(seg[1:] != seg[:-1]) + 1
        starts = np.concatenate(([0], transitions)).astype(np.int32, copy=False)
        ends = np.concatenate((transitions, [n])).astype(np.int32, copy=False)
        seg_ids = seg[starts].astype(np.int32, copy=False)
        self._seg_starts = starts
        self._seg_ends = ends
        self._seg_ids = seg_ids
        self._seg_start_to_idx = {int(starts[j]): int(j) for j in range(len(starts))}

        # 3) Базовая статистика по сегментам (для «инженерного» текста и tooltips)
        try:
            s_world = b.ensure_s_world()
        except Exception:
            # fallback: просто индекс как «расстояние»
            s_world = np.arange(n, dtype=float)

        # Canonical channels (no aliases / no silent compatibility bridges).
        vx = b.get("скорость_vx_м_с", 0.0)
        vy = b.get("скорость_vy_м_с", 0.0)
        # ABSOLUTE LAW: speed is DERIVED from model outputs (vx, vy); we do NOT invent an alternative channel.
        speed = np.hypot(vx, vy)
        yaw_rate = b.get("yaw_rate_рад_с", 0.0)
        ax = b.get("ускорение_продольное_ax_м_с2", 0.0)
        ay = b.get("ускорение_поперечное_ay_м_с2", 0.0)

        # Roughness: std(z_center) within segment, if road profile exists.
        zc = None
        try:
            _, zc = b.ensure_road_profile("center")
        except Exception:
            zc = None

        infos: list[dict] = []
        for j, (i0, i1) in enumerate(zip(starts.tolist(), ends.tolist())):
            if i1 <= i0:
                i1 = min(i0 + 1, n)
            ii1 = int(max(i0, i1 - 1))

            t0 = float(t[i0])
            t1 = float(t[ii1])
            s0 = float(s_world[i0])
            s1 = float(s_world[ii1])

            dur = max(0.0, t1 - t0)
            seg_len = max(0.0, s1 - s0)

            v_mean = float(np.nanmean(speed[i0:i1])) if speed is not None else float("nan")
            ax_mean = float(np.nanmean(ax[i0:i1])) if ax is not None else float("nan")
            ay_rms = float(np.nanstd(ay[i0:i1])) if ay is not None else float("nan")

            # Signed radius estimate from mean yaw_rate / mean speed
            radius_m = float("nan")
            if yaw_rate is not None and speed is not None:
                try:
                    wr = float(np.nanmean(yaw_rate[i0:i1]))
                    vv = float(np.nanmean(speed[i0:i1]))
                    if abs(wr) > 1e-9 and abs(vv) > 1e-3:
                        kappa = wr / vv
                        if abs(kappa) > 1e-9:
                            radius_m = 1.0 / kappa
                except Exception:
                    radius_m = float("nan")

            rough_std_m = float(np.nanstd(zc[i0:i1])) if zc is not None else float("nan")

            infos.append(
                {
                    "seg_idx": int(j),
                    "seg_id": int(seg_ids[j]),
                    "i0": int(i0),
                    "i1": int(i1),
                    "t0": t0,
                    "t1": t1,
                    "s0": s0,
                    "s1": s1,
                    "dur_s": dur,
                    "len_m": seg_len,
                    "v_mean_mps": v_mean,
                    "ax_mean_mps2": ax_mean,
                    "ay_rms_mps2": ay_rms,
                    "radius_m": radius_m,
                    "rough_std_m": rough_std_m,
                }
            )

        self._seg_infos = infos
        try:
            self._seg_s0 = np.array([d.get("s0", 0.0) for d in infos], dtype=float)
            self._seg_s1 = np.array([d.get("s1", 0.0) for d in infos], dtype=float)
        except Exception:
            self._seg_s0 = None
            self._seg_s1 = None

    @staticmethod
    def _surface_hint(rough_std_m: float) -> str:
        """Грубая классификация типа покрытия по σ(z) профиля дороги.

        Это *подсказка* (эвристика), не «истина».
        Выводим вместе с числом (σz), чтобы инженер видел основание.
        """
        try:
            if not math.isfinite(float(rough_std_m)):
                return "?"
            mm = abs(float(rough_std_m)) * 1000.0
            if mm < 2.0:
                return "ровно"
            if mm < 6.0:
                return "асфальт"
            if mm < 15.0:
                return "неровно"
            return "очень неровно"
        except Exception:
            return "?"

    @staticmethod
    def _segment_tooltip(info: dict, seg_count: int) -> str:
        try:
            j = int(info.get("seg_idx", 0))
            seg_id = int(info.get("seg_id", 0))
            s0 = float(info.get("s0", 0.0))
            s1 = float(info.get("s1", 0.0))
            t0 = float(info.get("t0", 0.0))
            t1 = float(info.get("t1", 0.0))
            L = float(info.get("len_m", 0.0))
            rough = float(info.get("rough_std_m", float("nan")))
            return (
                f"Сегмент {j + 1}/{max(1, seg_count)} (ID={seg_id})\n"
                f"S: {s0:.0f}…{s1:.0f} м  (L≈{L:.0f} м)\n"
                f"t: {t0:.1f}…{t1:.1f} с\n"
                f"σz≈{rough * 1000.0:.1f} мм"
            )
        except Exception:
            return "Сегмент"

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        # Runtime visual toggles. These must be resolved locally in the front/rear
        # axle views as well; otherwise partial graphics silently disappear when the
        # method reaches richer overlay paths below.
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b) or not self._signal_cache:
            self.set_bundle(b)
        eff_show_accel = bool(getattr(self, 'show_accel', True)) and (not bool(getattr(self, '_playback_perf_mode', False)))
        eff_show_vel = bool(getattr(self, 'show_vel', False)) and (not bool(getattr(self, '_playback_perf_mode', False)))
        eff_show_labels = bool(getattr(self, 'show_labels', True)) and (not bool(getattr(self, '_playback_perf_mode', False)))
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=sample_i0, i1=sample_i1, alpha=alpha)

        # Geometry constants
        y = self.geom.y_pos
        yL, yR = float(y[0]), float(y[1])
        wheel_r = float(self.geom.wheel_radius)
        wheel_w = float(self.geom.wheel_width)

        # Signals
        cL, cR = self.cL, self.cR
        cache = getattr(self, "_signal_cache", {}) or {}
        corner_cache = cache.get("corners", {}) or {}
        frame_cache = cache.get("frame", {}) or {}
        corner_L = corner_cache.get(str(cL), {}) or {}
        corner_R = corner_cache.get(str(cR), {}) or {}

        z_body_L = sample(corner_L.get("zb", 0.0), 0.0)
        z_body_R = sample(corner_R.get("zb", 0.0), 0.0)
        z_com = sample(frame_cache.get("z_com", 0.0), 0.0)

        z_wL = sample(corner_L.get("zw", 0.0), 0.0)
        z_wR = sample(corner_R.get("zw", 0.0), 0.0)
        road_L = corner_L.get("zr")
        road_R = corner_R.get("zr")
        z_rL = sample(road_L, float("nan")) if road_L is not None else float("nan")
        z_rR = sample(road_R, float("nan")) if road_R is not None else float("nan")

        # Reference levels: z=0 + explicit road levels under each wheel
        try:
            r = self.scene.sceneRect()
            self.road_zero.setLine(r.left(), 0.0, r.right(), 0.0)
        except Exception:
            self.road_zero.setLine(yL - 1.0, 0.0, yR + 1.0, 0.0)
        seg = max(0.05, 0.55 * wheel_w)
        self.road_lvl_l.setVisible(bool(np.isfinite(z_rL)))
        self.road_lvl_r.setVisible(bool(np.isfinite(z_rR)))
        if np.isfinite(z_rL):
            self.road_lvl_l.setLine(yL - seg, z_rL, yL + seg, z_rL)
        if np.isfinite(z_rR):
            self.road_lvl_r.setLine(yR - seg, z_rR, yR + seg, z_rR)

        # Derived: velocities/accelerations
        az_com = sample(frame_cache.get("az_com", 0.0), 0.0)
        az_body_L = sample(corner_L.get("ab", 0.0), 0.0)
        az_body_R = sample(corner_R.get("ab", 0.0), 0.0)
        az_wL = sample(corner_L.get("aw", 0.0), 0.0)
        az_wR = sample(corner_R.get("aw", 0.0), 0.0)

        vz_com = sample(frame_cache.get("vz_com", 0.0), 0.0)
        vz_body_L = sample(corner_L.get("vb", 0.0), 0.0)
        vz_body_R = sample(corner_R.get("vb", 0.0), 0.0)
        vz_wL = sample(corner_L.get("vw", 0.0), 0.0)
        vz_wR = sample(corner_R.get("vw", 0.0), 0.0)

        # Road line
        if np.isfinite(z_rL) and np.isfinite(z_rR):
            self.road.setLine(yL, z_rL, yR, z_rR)
            self.road.show()
        else:
            self.road.hide()

        # Body line
        self.body.setLine(yL, z_body_L, yR, z_body_R)

        # Suspension
        self.susp_l.setLine(yL, z_body_L, yL, z_wL)
        self.susp_r.setLine(yR, z_body_R, yR, z_wR)

        # Wheels (rectangles) - front/rear orthographic look
        self.wheel_l.setRect(yL - 0.5 * wheel_w, z_wL - wheel_r, wheel_w, 2 * wheel_r)
        self.wheel_r.setRect(yR - 0.5 * wheel_w, z_wR - wheel_r, wheel_w, 2 * wheel_r)

        # COM point
        self.com.setRect(-0.04, z_com - 0.04, 0.08, 0.08)

        # Arrows helpers
        def _a_to_len(a: float) -> float:
            return float(_clamp(a * self._accel_scale, -0.6, 0.6))

        def _v_to_len(v: float) -> float:
            return float(_clamp(v * self._vel_scale, -0.6, 0.6))

        # Acceleration arrows
        if eff_show_accel:
            # COM accel (cyan)
            self.arrow_a_com.set_arrow(
                QtCore.QPointF(0.0, z_com),
                QtCore.QPointF(0.0, z_com + _a_to_len(az_com)),
                rgb=(70, 180, 255),
                alpha=240,
                head_len_m=0.12,
                head_w_m=0.08,
            )

            # Body corner accel (green)
            self.arrow_a_body_l.set_arrow(QtCore.QPointF(yL, z_body_L), QtCore.QPointF(yL, z_body_L + _a_to_len(az_body_L)), rgb=(90, 220, 130))
            self.arrow_a_body_r.set_arrow(QtCore.QPointF(yR, z_body_R), QtCore.QPointF(yR, z_body_R + _a_to_len(az_body_R)), rgb=(90, 220, 130))

            # Wheel accel (orange)
            self.arrow_a_wheel_l.set_arrow(QtCore.QPointF(yL, z_wL), QtCore.QPointF(yL, z_wL + _a_to_len(az_wL)), rgb=(255, 170, 60))
            self.arrow_a_wheel_r.set_arrow(QtCore.QPointF(yR, z_wR), QtCore.QPointF(yR, z_wR + _a_to_len(az_wR)), rgb=(255, 170, 60))
        else:
            for a in (self.arrow_a_com, self.arrow_a_body_l, self.arrow_a_body_r, self.arrow_a_wheel_l, self.arrow_a_wheel_r):
                a.hide()

        # Velocity arrows (purple, thinner)
        if eff_show_vel:
            self.arrow_v_com.set_arrow(QtCore.QPointF(0.0, z_com), QtCore.QPointF(0.0, z_com + _v_to_len(vz_com)), rgb=(190, 140, 255), alpha=220, head_len_m=0.09, head_w_m=0.06)
            self.arrow_v_body_l.set_arrow(QtCore.QPointF(yL, z_body_L), QtCore.QPointF(yL, z_body_L + _v_to_len(vz_body_L)), rgb=(190, 140, 255), alpha=200, head_len_m=0.09, head_w_m=0.06)
            self.arrow_v_body_r.set_arrow(QtCore.QPointF(yR, z_body_R), QtCore.QPointF(yR, z_body_R + _v_to_len(vz_body_R)), rgb=(190, 140, 255), alpha=200, head_len_m=0.09, head_w_m=0.06)
            self.arrow_v_wheel_l.set_arrow(QtCore.QPointF(yL, z_wL), QtCore.QPointF(yL, z_wL + _v_to_len(vz_wL)), rgb=(220, 190, 255), alpha=200, head_len_m=0.08, head_w_m=0.05)
            self.arrow_v_wheel_r.set_arrow(QtCore.QPointF(yR, z_wR), QtCore.QPointF(yR, z_wR + _v_to_len(vz_wR)), rgb=(220, 190, 255), alpha=200, head_len_m=0.08, head_w_m=0.05)
        else:
            for a in (self.arrow_v_com, self.arrow_v_body_l, self.arrow_v_body_r, self.arrow_v_wheel_l, self.arrow_v_wheel_r):
                a.hide()

        # Labels (compact, pinned to key points)
        if eff_show_labels:
            def _txt(az: float, vz: float) -> str:
                if eff_show_vel:
                    return f"az {az:+.1f}\nvz {vz:+.2f}"
                return f"az {az:+.1f}"

            # small offsets in scene meters
            _set_graphics_text_if_changed(self.lab_com, _txt(az_com, vz_com))
            _set_graphics_pos_if_changed(self.lab_com, 0.06, z_com + 0.06)
            self.lab_com.setVisible(True)

            _set_graphics_text_if_changed(self.lab_body_l, _txt(az_body_L, vz_body_L))
            _set_graphics_pos_if_changed(self.lab_body_l, yL + 0.06, z_body_L + 0.06)
            self.lab_body_l.setVisible(True)

            _set_graphics_text_if_changed(self.lab_body_r, _txt(az_body_R, vz_body_R))
            _set_graphics_pos_if_changed(self.lab_body_r, yR + 0.06, z_body_R + 0.06)
            self.lab_body_r.setVisible(True)

            _set_graphics_text_if_changed(self.lab_wheel_l, _txt(az_wL, vz_wL))
            _set_graphics_pos_if_changed(self.lab_wheel_l, yL + 0.06, z_wL - 0.26)
            self.lab_wheel_l.setVisible(True)

            _set_graphics_text_if_changed(self.lab_wheel_r, _txt(az_wR, vz_wR))
            _set_graphics_pos_if_changed(self.lab_wheel_r, yR + 0.06, z_wR - 0.26)
            self.lab_wheel_r.setVisible(True)
        else:
            for lab in (self.lab_com, self.lab_body_l, self.lab_body_r, self.lab_wheel_l, self.lab_wheel_r):
                lab.setVisible(False)

        # Scene rect / scaling are configured once per bundle (CockpitWidget).


class SideViewWidget(QtWidgets.QGraphicsView):
    """Side (front-rear) view: pitch + vertical motion.

    Mode:
      - "avg": average left/right per axle (classic pitch view)
      - "left": only left side (ЛП/ЛЗ)
      - "right": only right side (ПП/ПЗ)

    R50 upgrades:
    - optional velocity arrows + numeric labels
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, mode: str = "avg"):
        super().__init__(parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(14, 18, 22)))
        # We manage scaling explicitly; keep the view clean.
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setAlignment(QtCore.Qt.AlignCenter)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        # Perf: animated scenes are faster with NoIndex
        try:
            self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        except Exception:
            pass
        try:
            self.setViewportUpdateMode(QtWidgets.QGraphicsView.BoundingRectViewportUpdate)
            self.setOptimizationFlag(QtWidgets.QGraphicsView.DontSavePainterState, True)
            self.setOptimizationFlag(QtWidgets.QGraphicsView.DontAdjustForAntialiasing, True)
        except Exception:
            pass

        self.mode = str(mode).lower().strip() or "avg"

        self.road = QtWidgets.QGraphicsPathItem()
        self.body = QtWidgets.QGraphicsLineItem()
        self.susp_f = QtWidgets.QGraphicsLineItem()
        self.susp_r = QtWidgets.QGraphicsLineItem()

        # Road reference levels (z=0 + explicit road levels under each wheel)
        self.road_zero = QtWidgets.QGraphicsLineItem()  # z=0
        self.road_lvl_f = QtWidgets.QGraphicsLineItem()  # road under front wheel
        self.road_lvl_r = QtWidgets.QGraphicsLineItem()  # road under rear wheel

        self.wheel_f = QtWidgets.QGraphicsEllipseItem()
        self.wheel_r = QtWidgets.QGraphicsEllipseItem()
        self.com = QtWidgets.QGraphicsEllipseItem()

        # Accel arrows
        self.arrow_a_com = Arrow2D(self.scene, width_m=0.02)
        self.arrow_a_body_f = Arrow2D(self.scene, width_m=0.02)
        self.arrow_a_body_r = Arrow2D(self.scene, width_m=0.02)
        self.arrow_a_wheel_f = Arrow2D(self.scene, width_m=0.015)
        self.arrow_a_wheel_r = Arrow2D(self.scene, width_m=0.015)

        # Vel arrows
        self.arrow_v_com = Arrow2D(self.scene, width_m=0.012)
        self.arrow_v_body_f = Arrow2D(self.scene, width_m=0.012)
        self.arrow_v_body_r = Arrow2D(self.scene, width_m=0.012)
        self.arrow_v_wheel_f = Arrow2D(self.scene, width_m=0.010)
        self.arrow_v_wheel_r = Arrow2D(self.scene, width_m=0.010)

        # Labels
        self.lab_com = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_f = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_r = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_wf = _make_graphics_label_item(self.scene, font_size=8)
        self.lab_wr = _make_graphics_label_item(self.scene, font_size=8)

        # Reference road lines behind everything
        for it in [self.road_zero, self.road_lvl_f, self.road_lvl_r]:
            it.setZValue(0)
            self.scene.addItem(it)

        for it in [self.road, self.body]:
            it.setZValue(1)
            self.scene.addItem(it)
        for it in [self.susp_f, self.susp_r, self.wheel_f, self.wheel_r, self.com]:
            it.setZValue(2)
            self.scene.addItem(it)

        pen_zero = QtGui.QPen(QtGui.QColor(60, 70, 80), 0.01, QtCore.Qt.DashLine)
        pen_zero.setCosmetic(True)
        self.road_zero.setPen(pen_zero)

        pen_lvl = QtGui.QPen(QtGui.QColor(120, 120, 120), 0.012)
        pen_lvl.setCosmetic(True)
        self.road_lvl_f.setPen(pen_lvl)
        self.road_lvl_r.setPen(pen_lvl)

        self.road.setPen(QtGui.QPen(QtGui.QColor(90, 90, 90), 0.01))
        self.body.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 0.02))

        for ln in [self.susp_f, self.susp_r]:
            ln.setPen(QtGui.QPen(QtGui.QColor(150, 160, 170), 0.01, QtCore.Qt.DashLine))

        for wh in [self.wheel_f, self.wheel_r]:
            wh.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 0.02))
            wh.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60)))

        self.com.setPen(QtGui.QPen(QtGui.QColor(240, 200, 80), 0.02))
        self.com.setBrush(QtGui.QBrush(QtGui.QColor(240, 200, 80)))

        self._px_per_m = 260.0
        self._base_px_per_m = float(self._px_per_m)
        self._user_zoom = 1.0
        self._set_transform()

        self.geom = ViewGeometry()
        self._accel_scale = 0.05
        self._vel_scale = 0.08

        self.show_accel = True
        self.show_vel = False
        self.show_labels = True
        self.show_dims = False
        self.show_scale_bar = True
        self._playback_perf_mode = False
        self._compact_dock_mode = False
        self._compact_max_height = 150
        self._road_x_nodes_cache_key: Optional[Tuple[float, float, int]] = None
        self._road_x_nodes_cache: Optional[np.ndarray] = None
        self._render_hints_normal = QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing
        self._render_hints_compact = QtGui.QPainter.TextAntialiasing
        self._render_hints_perf = QtGui.QPainter.RenderHints()
        self._bundle_key: Optional[int] = None
        self._signal_cache: Dict[str, Any] = {}
        self._apply_render_hint_policy()

    def set_px_per_m(self, px_per_m: float):
        self._base_px_per_m = float(px_per_m)
        self._px_per_m = float(self._base_px_per_m) * float(max(0.1, self._user_zoom))
        self._set_transform()

    def reset_user_zoom(self) -> None:
        self._user_zoom = 1.0
        self._px_per_m = float(self._base_px_per_m)
        self._set_transform()

    def _set_transform(self):
        tr = QtGui.QTransform()
        tr.scale(self._px_per_m, -self._px_per_m)
        self.setTransform(tr)

    def wheelEvent(self, event: QtGui.QWheelEvent):  # type: ignore[override]
        delta = 0
        try:
            delta = int(event.angleDelta().y())
        except Exception:
            delta = 0
        if delta:
            step = 1.12 if delta > 0 else (1.0 / 1.12)
            self._user_zoom = float(_clamp(self._user_zoom * step, 0.35, 6.0))
            self._px_per_m = float(self._base_px_per_m) * float(self._user_zoom)
            self._set_transform()
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):  # type: ignore[override]
        self.reset_user_zoom()
        try:
            event.accept()
        except Exception:
            pass
        return

    def set_geometry(self, geom: ViewGeometry):
        self.geom = geom
        self._bundle_key = None
        self._signal_cache = {}

    def set_bundle(self, b: DataBundle) -> None:
        self._bundle_key = id(b)
        self._signal_cache = _ensure_vertical_view_signal_cache(b, float(self.geom.wheelbase))

    def set_scales(self, accel_scale: float, vel_scale: float):
        self._accel_scale = float(accel_scale)
        self._vel_scale = float(vel_scale)

    def set_visual(
        self,
        *,
        show_accel: Optional[bool] = None,
        show_vel: Optional[bool] = None,
        show_labels: Optional[bool] = None,
        show_dims: Optional[bool] = None,
        show_scale_bar: Optional[bool] = None,
    ):
        if show_accel is not None:
            self.show_accel = bool(show_accel)
        if show_vel is not None:
            self.show_vel = bool(show_vel)
        if show_labels is not None:
            self.show_labels = bool(show_labels)
        if show_dims is not None:
            self.show_dims = bool(show_dims)
        if show_scale_bar is not None:
            self.show_scale_bar = bool(show_scale_bar)

    def set_playback_perf_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == bool(self._playback_perf_mode):
            return
        self._playback_perf_mode = enabled
        self._apply_render_hint_policy()
        try:
            self.viewport().update()
        except Exception:
            pass

    def _apply_render_hint_policy(self) -> None:
        if bool(self._playback_perf_mode):
            hints = self._render_hints_perf
        elif bool(self._compact_dock_mode):
            hints = self._render_hints_compact
        else:
            hints = self._render_hints_normal
        try:
            self.setRenderHints(hints)
        except Exception:
            pass

    def set_compact_dock_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(getattr(self, "_compact_dock_mode", False)):
            return
        self._compact_dock_mode = compact
        self._apply_render_hint_policy()
        self._road_x_nodes_cache_key = None
        self._road_x_nodes_cache = None
        max_h = int(self._compact_max_height) if compact else 16777215
        vpol = QtWidgets.QSizePolicy.Maximum if compact else QtWidgets.QSizePolicy.Expanding
        try:
            self.setMaximumHeight(max_h)
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
        except Exception:
            pass
        try:
            self.updateGeometry()
            self.viewport().update()
        except Exception:
            pass

    def _road_polyline_sample_count(self) -> int:
        try:
            viewport_w = int(max(180, self.viewport().width()))
        except Exception:
            viewport_w = 320
        budget_cap = 64 if bool(getattr(self, "_compact_dock_mode", False)) else 144
        return int(max(32, min(int(budget_cap), (viewport_w // 5) + 8)))

    def _road_x_nodes_for_scene(self, x_min: float, x_max: float) -> np.ndarray:
        count = self._road_polyline_sample_count()
        key = (round(float(x_min), 4), round(float(x_max), 4), int(count))
        if key != self._road_x_nodes_cache_key or self._road_x_nodes_cache is None:
            self._road_x_nodes_cache_key = key
            self._road_x_nodes_cache = np.linspace(float(x_min), float(x_max), int(count), dtype=float)
        return self._road_x_nodes_cache

    def drawForeground(self, painter: QtGui.QPainter, rect: QtCore.QRectF):  # type: ignore
        super().drawForeground(painter, rect)

        eff_show_dims = bool(self.show_dims) and not bool(self._playback_perf_mode)
        eff_show_scale_bar = bool(self.show_scale_bar) and not bool(self._playback_perf_mode)
        if not (eff_show_dims or eff_show_scale_bar):
            return

        painter.save()
        painter.resetTransform()

        w = self.viewport().width()
        h = self.viewport().height()
        m = 10

        # --- scale bar ---
        if eff_show_scale_bar and self._px_per_m > 1e-6:
            target_px = max(60, min(160, int(0.22 * w)))
            nice_m = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
            bar_m = 1.0
            for v in nice_m:
                if v * self._px_per_m >= target_px:
                    bar_m = v
                    break
            bar_px = int(bar_m * self._px_per_m)

            x0 = m
            y0 = h - m
            painter.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 2))
            painter.drawLine(x0, y0, x0 + bar_px, y0)
            painter.drawLine(x0, y0 - 6, x0, y0 + 6)
            painter.drawLine(x0 + bar_px, y0 - 6, x0 + bar_px, y0 + 6)
            painter.setPen(QtGui.QPen(QtGui.QColor(230, 230, 230), 1))
            painter.drawText(x0, y0 - 8, f"{bar_m:g} м")

        # --- geometry overlay ---
        if eff_show_dims:
            txt = (
                f"Геометрия (м):\n"
                f"  База L = {self.geom.wheelbase:.3f}\n"
                f"  Радиус колеса R = {self.geom.wheel_radius:.3f}"
            )
            fm = painter.fontMetrics()
            lines = txt.split("\n")
            line_h = fm.height()
            box_w = max(fm.horizontalAdvance(s) for s in lines) + 2 * m
            box_h = line_h * len(lines) + 2 * m
            x = w - box_w - m
            y = m
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 0, 0, 150))
            painter.drawRoundedRect(QtCore.QRectF(x, y, box_w, box_h), 6, 6)
            painter.setPen(QtGui.QPen(QtGui.QColor(240, 240, 240), 1))
            for k, s in enumerate(lines):
                painter.drawText(x + m, y + m + (k + 1) * line_h - fm.descent(), s)

        painter.restore()

    def _pick(self) -> Tuple[str, str]:
        if self.mode.startswith("l"):
            return "ЛП", "ЛЗ"
        if self.mode.startswith("r"):
            return "ПП", "ПЗ"
        return "avg", "avg"


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b) or not self._signal_cache:
            self.set_bundle(b)
        eff_show_accel = bool(self.show_accel) and not bool(self._playback_perf_mode)
        eff_show_vel = bool(self.show_vel) and not bool(self._playback_perf_mode)
        eff_show_labels = bool(self.show_labels) and not bool(self._playback_perf_mode)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=sample_i0, i1=sample_i1, alpha=alpha)
        x = self.geom.x_pos
        xF, xR = float(x[0]), float(x[2])
        wheel_r = float(self.geom.wheel_radius)

        modeF, modeR = self._pick()
        cache = getattr(self, "_signal_cache", {}) or {}
        corner_cache = cache.get("corners", {}) or {}
        frame_cache = cache.get("frame", {}) or {}

        # Body/wheel/road signals
        if modeF == "avg":
            fl = corner_cache.get("ЛП", {}) or {}
            fr = corner_cache.get("ПП", {}) or {}
            rl = corner_cache.get("ЛЗ", {}) or {}
            rr = corner_cache.get("ПЗ", {}) or {}
            # Average left/right per axle
            z_body_F = _sample_series_avg2(sample, fl.get("zb", 0.0), fr.get("zb", 0.0), default=0.0)
            z_body_R = _sample_series_avg2(sample, rl.get("zb", 0.0), rr.get("zb", 0.0), default=0.0)

            z_wF = _sample_series_avg2(sample, fl.get("zw", 0.0), fr.get("zw", 0.0), default=0.0)
            z_wR = _sample_series_avg2(sample, rl.get("zw", 0.0), rr.get("zw", 0.0), default=0.0)

            road_LP = fl.get("zr")
            road_PP = fr.get("zr")
            road_LZ = rl.get("zr")
            road_PZ = rr.get("zr")
            z_rF = 0.5 * (
                sample(road_LP, float("nan"))
                + sample(road_PP, float("nan"))
            ) if (road_LP is not None and road_PP is not None) else float("nan")
            z_rR = 0.5 * (
                sample(road_LZ, float("nan"))
                + sample(road_PZ, float("nan"))
            ) if (road_LZ is not None and road_PZ is not None) else float("nan")

            az_body_F = _sample_series_avg2(sample, fl.get("ab", 0.0), fr.get("ab", 0.0), default=0.0)
            az_body_R = _sample_series_avg2(sample, rl.get("ab", 0.0), rr.get("ab", 0.0), default=0.0)
            az_wF = _sample_series_avg2(sample, fl.get("aw", 0.0), fr.get("aw", 0.0), default=0.0)
            az_wR = _sample_series_avg2(sample, rl.get("aw", 0.0), rr.get("aw", 0.0), default=0.0)

            vz_body_F = _sample_series_avg2(sample, fl.get("vb", 0.0), fr.get("vb", 0.0), default=0.0)
            vz_body_R = _sample_series_avg2(sample, rl.get("vb", 0.0), rr.get("vb", 0.0), default=0.0)
            vz_wF = _sample_series_avg2(sample, fl.get("vw", 0.0), fr.get("vw", 0.0), default=0.0)
            vz_wR = _sample_series_avg2(sample, rl.get("vw", 0.0), rr.get("vw", 0.0), default=0.0)
        else:
            # One side only
            cF, cR = modeF, modeR
            front_cache = corner_cache.get(str(cF), {}) or {}
            rear_cache = corner_cache.get(str(cR), {}) or {}
            z_body_F = sample(front_cache.get("zb", 0.0), 0.0)
            z_body_R = sample(rear_cache.get("zb", 0.0), 0.0)
            z_wF = sample(front_cache.get("zw", 0.0), 0.0)
            z_wR = sample(rear_cache.get("zw", 0.0), 0.0)
            road_F = front_cache.get("zr")
            road_R = rear_cache.get("zr")
            z_rF = sample(road_F, float("nan")) if road_F is not None else float("nan")
            z_rR = sample(road_R, float("nan")) if road_R is not None else float("nan")

            az_body_F = sample(front_cache.get("ab", 0.0), 0.0)
            az_body_R = sample(rear_cache.get("ab", 0.0), 0.0)
            az_wF = sample(front_cache.get("aw", 0.0), 0.0)
            az_wR = sample(rear_cache.get("aw", 0.0), 0.0)

            vz_body_F = sample(front_cache.get("vb", 0.0), 0.0)
            vz_body_R = sample(rear_cache.get("vb", 0.0), 0.0)
            vz_wF = sample(front_cache.get("vw", 0.0), 0.0)
            vz_wR = sample(rear_cache.get("vw", 0.0), 0.0)

        # Reference levels: z=0 + explicit road levels under each wheel
        try:
            r = self.scene.sceneRect()
            self.road_zero.setLine(r.left(), 0.0, r.right(), 0.0)
        except Exception:
            self.road_zero.setLine(xR - 2.0, 0.0, xF + 2.0, 0.0)
        seg = max(0.08, wheel_r * 0.9)
        self.road_lvl_f.setVisible(bool(np.isfinite(z_rF)))
        self.road_lvl_r.setVisible(bool(np.isfinite(z_rR)))
        if np.isfinite(z_rF):
            self.road_lvl_f.setLine(xF - seg, z_rF, xF + seg, z_rF)
        if np.isfinite(z_rR):
            self.road_lvl_r.setLine(xR - seg, z_rR, xR + seg, z_rR)

        z_com = sample(frame_cache.get("z_com", 0.0), 0.0)
        az_com = sample(frame_cache.get("az_com", 0.0), 0.0)
        vz_com = sample(frame_cache.get("vz_com", 0.0), 0.0)

        def _a_to_len(a: float) -> float:
            return float(_clamp(a * self._accel_scale, -0.6, 0.6))

        def _v_to_len(v: float) -> float:
            return float(_clamp(v * self._vel_scale, -0.6, 0.6))

        # Road — prefer the canonical reconstructed road profile so that 2D side view
        # matches the same curvature that the 3D ribbon uses.
        road_path = QtGui.QPainterPath()
        road_ok = False
        try:
            s_world = np.asarray(cache.get("s_world", np.zeros((0,), dtype=float)), dtype=float)
            s0 = sample(
                s_world,
                float(s_world[min(max(i, 0), max(0, len(s_world) - 1))]),
            )
            mode_profile = "center" if modeF == "avg" else ("left" if str(modeF).startswith("Л") else "right")
            road_profiles = cache.get("road_profiles", {}) or {}
            s_prof, z_prof = tuple(road_profiles.get(str(mode_profile), (np.zeros((0,), dtype=float), np.zeros((0,), dtype=float))))
            r = self.scene.sceneRect()
            x_min = float(r.left()) if r.width() > 0.0 else float(min(xR, xF) - 0.6)
            x_max = float(r.right()) if r.width() > 0.0 else float(max(xR, xF) + 0.6)
            x_nodes = self._road_x_nodes_for_scene(x_min, x_max)
            z_nodes = np.interp(s0 + x_nodes, np.asarray(s_prof, dtype=float), np.asarray(z_prof, dtype=float))
            if z_nodes.size >= 2 and np.isfinite(z_nodes).any():
                road_path.moveTo(QtCore.QPointF(float(x_nodes[0]), float(z_nodes[0])))
                for xx, zz in zip(x_nodes[1:], z_nodes[1:]):
                    road_path.lineTo(QtCore.QPointF(float(xx), float(zz)))
                road_ok = True
        except Exception:
            road_ok = False

        if not road_ok and np.isfinite(z_rF) and np.isfinite(z_rR):
            road_path.moveTo(QtCore.QPointF(xF, z_rF))
            road_path.lineTo(QtCore.QPointF(xR, z_rR))
            road_ok = True

        if road_ok:
            self.road.setPath(road_path)
            self.road.show()
        else:
            self.road.setPath(QtGui.QPainterPath())
            self.road.hide()

        # Body
        self.body.setLine(xF, z_body_F, xR, z_body_R)

        # Susp
        self.susp_f.setLine(xF, z_body_F, xF, z_wF)
        self.susp_r.setLine(xR, z_body_R, xR, z_wR)

        self.wheel_f.setRect(xF - wheel_r, z_wF - wheel_r, 2 * wheel_r, 2 * wheel_r)
        self.wheel_r.setRect(xR - wheel_r, z_wR - wheel_r, 2 * wheel_r, 2 * wheel_r)

        self.com.setRect(-0.04, z_com - 0.04, 0.08, 0.08)

        # Arrows: accel
        if eff_show_accel:
            self.arrow_a_com.set_arrow(QtCore.QPointF(0.0, z_com), QtCore.QPointF(0.0, z_com + _a_to_len(az_com)), rgb=(70, 180, 255), alpha=240)
            self.arrow_a_body_f.set_arrow(QtCore.QPointF(xF, z_body_F), QtCore.QPointF(xF, z_body_F + _a_to_len(az_body_F)), rgb=(90, 220, 130))
            self.arrow_a_body_r.set_arrow(QtCore.QPointF(xR, z_body_R), QtCore.QPointF(xR, z_body_R + _a_to_len(az_body_R)), rgb=(90, 220, 130))
            self.arrow_a_wheel_f.set_arrow(QtCore.QPointF(xF, z_wF), QtCore.QPointF(xF, z_wF + _a_to_len(az_wF)), rgb=(255, 170, 60))
            self.arrow_a_wheel_r.set_arrow(QtCore.QPointF(xR, z_wR), QtCore.QPointF(xR, z_wR + _a_to_len(az_wR)), rgb=(255, 170, 60))
        else:
            for a in (self.arrow_a_com, self.arrow_a_body_f, self.arrow_a_body_r, self.arrow_a_wheel_f, self.arrow_a_wheel_r):
                a.hide()

        # Arrows: vel
        if eff_show_vel:
            self.arrow_v_com.set_arrow(QtCore.QPointF(0.0, z_com), QtCore.QPointF(0.0, z_com + _v_to_len(vz_com)), rgb=(190, 140, 255), alpha=220, head_len_m=0.09, head_w_m=0.06)
            self.arrow_v_body_f.set_arrow(QtCore.QPointF(xF, z_body_F), QtCore.QPointF(xF, z_body_F + _v_to_len(vz_body_F)), rgb=(190, 140, 255), alpha=200, head_len_m=0.09, head_w_m=0.06)
            self.arrow_v_body_r.set_arrow(QtCore.QPointF(xR, z_body_R), QtCore.QPointF(xR, z_body_R + _v_to_len(vz_body_R)), rgb=(190, 140, 255), alpha=200, head_len_m=0.09, head_w_m=0.06)
            self.arrow_v_wheel_f.set_arrow(QtCore.QPointF(xF, z_wF), QtCore.QPointF(xF, z_wF + _v_to_len(vz_wF)), rgb=(220, 190, 255), alpha=200, head_len_m=0.08, head_w_m=0.05)
            self.arrow_v_wheel_r.set_arrow(QtCore.QPointF(xR, z_wR), QtCore.QPointF(xR, z_wR + _v_to_len(vz_wR)), rgb=(220, 190, 255), alpha=200, head_len_m=0.08, head_w_m=0.05)
        else:
            for a in (self.arrow_v_com, self.arrow_v_body_f, self.arrow_v_body_r, self.arrow_v_wheel_f, self.arrow_v_wheel_r):
                a.hide()

        # Labels
        if eff_show_labels:
            def _txt(az: float, vz: float) -> str:
                if eff_show_vel:
                    return f"az {az:+.1f}\nvz {vz:+.2f}"
                return f"az {az:+.1f}"

            _set_graphics_text_if_changed(self.lab_com, _txt(az_com, vz_com))
            _set_graphics_pos_if_changed(self.lab_com, 0.06, z_com + 0.06)
            self.lab_com.setVisible(True)

            _set_graphics_text_if_changed(self.lab_f, _txt(az_body_F, vz_body_F))
            _set_graphics_pos_if_changed(self.lab_f, xF + 0.06, z_body_F + 0.06)
            self.lab_f.setVisible(True)

            _set_graphics_text_if_changed(self.lab_r, _txt(az_body_R, vz_body_R))
            _set_graphics_pos_if_changed(self.lab_r, xR + 0.06, z_body_R + 0.06)
            self.lab_r.setVisible(True)

            _set_graphics_text_if_changed(self.lab_wf, _txt(az_wF, vz_wF))
            _set_graphics_pos_if_changed(self.lab_wf, xF + 0.06, z_wF - 0.26)
            self.lab_wf.setVisible(True)

            _set_graphics_text_if_changed(self.lab_wr, _txt(az_wR, vz_wR))
            _set_graphics_pos_if_changed(self.lab_wr, xR + 0.06, z_wR - 0.26)
            self.lab_wr.setVisible(True)
        else:
            for lab in (self.lab_com, self.lab_f, self.lab_r, self.lab_wf, self.lab_wr):
                lab.setVisible(False)

        # Scene rect / scaling are configured once per bundle (CockpitWidget).


class RoadHudWidget(QtWidgets.QGraphicsView):
    """Top-down "instrument cluster" preview: curved road + key dynamics.

    R50 upgrades:
    - overlay text (speed, yaw_rate, radius, ax/ay) for quick reading
    - toggleable layers (lanes / accel arrow / text)
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, compact: bool = False):
        super().__init__(parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(10, 12, 14)))

        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)

        try:
            self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        except Exception:
            pass
        try:
            self.setViewportUpdateMode(QtWidgets.QGraphicsView.BoundingRectViewportUpdate)
            self.setOptimizationFlag(QtWidgets.QGraphicsView.DontSavePainterState, True)
            self.setOptimizationFlag(QtWidgets.QGraphicsView.DontAdjustForAntialiasing, True)
        except Exception:
            pass


        self.centerline = QtWidgets.QGraphicsPathItem()
        self.lane_l = QtWidgets.QGraphicsPathItem()
        self.lane_r = QtWidgets.QGraphicsPathItem()
        # semi-transparent road ribbon (instrument-cluster style)
        self.road_fill = QtWidgets.QGraphicsPolygonItem()
        self.car = QtWidgets.QGraphicsPathItem()

        self.arrow_a = Arrow2D(self.scene, width_m=0.03, gradient_body=True)

        # Text overlay (readability > style)
        self.hud_text = _make_graphics_label_item(self.scene, font_size=9, z=10.0)
        self.hud_text_context = _make_graphics_label_item(self.scene, font_size=9, z=10.0)
        self.hud_text_static = _make_graphics_label_item(self.scene, font_size=9, z=10.0)

        # Road ribbon fill (under lane edges)
        self.road_fill.setZValue(0)
        self.road_fill.setPen(QtCore.Qt.NoPen)
        self.road_fill.setBrush(QtGui.QBrush(QtGui.QColor(50, 80, 100, 55)))
        self.scene.addItem(self.road_fill)

        # Segment fill overlays (muted). Created lazily to match visible runs.
        self._seg_fill_items: list[QtWidgets.QGraphicsPathItem] = []
        self._seg_fill_nopen = QtGui.QPen(QtCore.Qt.NoPen)
        self._seg_id_to_info: dict[int, dict] = {}

        for it in [self.lane_l, self.lane_r]:
            it.setZValue(1)
            it.setPen(QtGui.QPen(QtGui.QColor(80, 80, 80), 0.03))
            self.scene.addItem(it)

        self.centerline.setZValue(1)
        self.centerline.setPen(QtGui.QPen(QtGui.QColor(120, 120, 120), 0.02, QtCore.Qt.DashLine))
        self.scene.addItem(self.centerline)

        self.car.setZValue(2)
        self.car.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 0.03))
        self.car.setBrush(QtGui.QBrush(QtGui.QColor(40, 40, 40)))
        self.scene.addItem(self.car)

        # Segment boundary markers (помогают связать «где мы сейчас» с тест‑планом/генератором).
        # Рисуем поперечные пунктирные линии на дороге; инструментально и без «гирлянд».
        self._seg_marker_items: list[QtWidgets.QGraphicsLineItem] = []
        self._seg_marker_active_count: int = 0
        self._seg_marker_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 90), 1, QtCore.Qt.DashLine)
        try:
            self._seg_marker_pen.setCosmetic(True)  # толщина в пикселях (не зависит от зума)
        except Exception:
            pass

        self._px_per_m = 18.0
        self._auto_view_fit = True
        self._last_fit_rect_key: Optional[tuple[float, float, float, float]] = None
        self._last_fit_viewport_size: tuple[int, int] = (0, 0)
        self._set_transform()

        self._lane_width = 3.5
        self._lookahead_m = 60.0
        self._history_m = 20.0

        # Segment cache (for "where are we in the test" overlay).
        self._seg_cache_key: Optional[object] = None
        self._seg_starts: Optional[np.ndarray] = None
        self._seg_ends: Optional[np.ndarray] = None
        self._seg_ids: Optional[np.ndarray] = None
        self._seg_full: Optional[np.ndarray] = None
        self._seg_s0: Optional[np.ndarray] = None
        self._seg_s1: Optional[np.ndarray] = None
        self._seg_start_to_idx: dict[int, int] = {}
        self._seg_infos: list[dict] = []


        # Geometry (used for car silhouette sizing)
        self.geom: ViewGeometry = ViewGeometry()
        # Visual toggles
        self.show_lanes = True
        self.show_accel = True
        self.show_text = True
        self.auto_lookahead = True
        # Segment overlays (muted color-coding + boundary markers)
        self.show_seg_colors = True
        self.show_seg_markers = True
        self._playback_perf_mode = False
        self._render_hints_normal = QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing
        self._render_hints_perf = QtGui.QPainter.RenderHints()
        self._last_lane_pen_key: Optional[tuple[int, int]] = None
        self._car_path_key: Optional[tuple[int, int, int, int]] = None
        self._last_perf_visual_key: Optional[tuple[int, ...]] = None
        self._centerline_path_key: Optional[tuple[int, ...]] = None
        self._lane_l_path_key: Optional[tuple[int, ...]] = None
        self._lane_r_path_key: Optional[tuple[int, ...]] = None
        self._road_fill_poly_key: Optional[tuple[int, ...]] = None
        self._hud_polyline_point_budget_min = 160
        self._hud_polyline_point_budget_max = 520
        self._hud_perf_polyline_point_budget_cap = 180
        self._hud_lane_polyline_scale = 0.58
        self._hud_lane_polyline_min_points = 92
        self._hud_perf_lane_polyline_scale = 0.46
        self._hud_perf_lane_polyline_min_points = 68
        self._hud_fill_polyline_scale = 0.42
        self._hud_fill_polyline_min_points = 64
        self._hud_perf_fill_polyline_scale = 0.34
        self._hud_perf_fill_polyline_min_points = 48
        self._hud_path_visual_key_quant_scale = 2.0
        self._hud_fill_visual_key_quant_scale = 1.0
        self._hud_elide_cache: Dict[tuple[str, int, str], str] = {}
        self._hud_static_bundle_key: int = 0
        self._hud_static_lines: tuple[str, ...] = ()
        self._hud_static_text_cache_key: Optional[tuple[int, str, int]] = None
        self._hud_static_text_cache_value: str = ""

    def set_px_per_m(self, px_per_m: float):
        self._px_per_m = float(px_per_m)
        self._set_transform()
        self._last_perf_visual_key = None
        self._centerline_path_key = None
        self._lane_l_path_key = None
        self._lane_r_path_key = None
        self._road_fill_poly_key = None

    def _set_transform(self):
        tr = QtGui.QTransform()
        # x right, y forward; flip y so forward is up
        tr.scale(self._px_per_m, -self._px_per_m)
        self.setTransform(tr)
        self._last_fit_rect_key = None
        self._last_fit_viewport_size = (0, 0)

    @staticmethod
    def _scene_rect_fit_key(rect: QtCore.QRectF) -> tuple[float, float, float, float]:
        return (
            round(float(rect.x()), 3),
            round(float(rect.y()), 3),
            round(float(rect.width()), 3),
            round(float(rect.height()), 3),
        )

    def _fit_view_to_scene_if_needed(self, rect: Optional[QtCore.QRectF] = None, *, force: bool = False) -> None:
        if rect is None:
            rect = self.scene.sceneRect()
        try:
            vp = self.viewport()
            viewport_size = (int(vp.width()), int(vp.height()))
        except Exception:
            viewport_size = (0, 0)
        rect_key = self._scene_rect_fit_key(rect)
        if (
            not bool(force)
            and viewport_size == tuple(getattr(self, "_last_fit_viewport_size", (0, 0)))
            and rect_key == getattr(self, "_last_fit_rect_key", None)
        ):
            return
        try:
            self.fitInView(rect, QtCore.Qt.KeepAspectRatio)
            self._last_fit_rect_key = rect_key
            self._last_fit_viewport_size = viewport_size
        except Exception:
            pass

    def wheelEvent(self, event: QtGui.QWheelEvent):  # type: ignore[override]
        delta = 0
        try:
            delta = int(event.angleDelta().y())
        except Exception:
            delta = 0
        if delta:
            self._auto_view_fit = False
            step = 1.12 if delta > 0 else (1.0 / 1.12)
            self.scale(step, step)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):  # type: ignore[override]
        self._auto_view_fit = True
        self._fit_view_to_scene_if_needed(force=True)
        try:
            event.accept()
        except Exception:
            pass
        return

    def set_geometry(self, geom: 'ViewGeometry'):
        """Apply inferred vehicle geometry (wheelbase/track/wheel sizes) to HUD view."""
        try:
            self.geom = geom
            self._car_path_key = None
            self._last_perf_visual_key = None
            self._centerline_path_key = None
            self._lane_l_path_key = None
            self._lane_r_path_key = None
            self._road_fill_poly_key = None
        except Exception:
            pass


    def set_visual(self, *, show_lanes: Optional[bool] = None, show_accel: Optional[bool] = None, show_text: Optional[bool] = None, auto_lookahead: Optional[bool] = None, show_seg_markers: Optional[bool] = None, show_seg_colors: Optional[bool] = None):
        if show_lanes is not None:
            self.show_lanes = bool(show_lanes)
        if show_accel is not None:
            self.show_accel = bool(show_accel)
        if show_text is not None:
            self.show_text = bool(show_text)
        if auto_lookahead is not None:
            self.auto_lookahead = bool(auto_lookahead)
        if show_seg_markers is not None:
            self.show_seg_markers = bool(show_seg_markers)
        if show_seg_colors is not None:
            self.show_seg_colors = bool(show_seg_colors)
        self._last_perf_visual_key = None

    def _poly_visual_key(self, xa: np.ndarray, ya: np.ndarray, *, closed: bool = False) -> tuple[int, ...]:
        x_arr = np.asarray(xa, dtype=float).reshape(-1)
        y_arr = np.asarray(ya, dtype=float).reshape(-1)
        return self._poly_visual_key_from_arrays(x_arr, y_arr, closed=closed)

    def _poly_visual_key_from_arrays(
        self,
        x_arr: np.ndarray,
        y_arr: np.ndarray,
        *,
        closed: bool = False,
        quant_scale: float = 2.0,
    ) -> tuple[int, ...]:
        n = int(min(x_arr.size, y_arr.size))
        if n <= 0:
            return (int(bool(closed)), 0, 0)
        quant = float(max(1.0, float(self._px_per_m) * float(quant_scale)))
        coords = np.empty((n, 2), dtype=np.int32)
        coords[:, 0] = np.rint(x_arr[:n] * quant).astype(np.int32, copy=False)
        coords[:, 1] = np.rint(y_arr[:n] * quant).astype(np.int32, copy=False)
        return (int(bool(closed)), n, int(hash(coords.tobytes())))

    def _set_poly_path_if_changed(
        self,
        attr_name: str,
        item: QtWidgets.QGraphicsPathItem,
        xa: np.ndarray,
        ya: np.ndarray,
        *,
        closed: bool = False,
    ) -> None:
        x_arr = np.asarray(xa, dtype=float).reshape(-1)
        y_arr = np.asarray(ya, dtype=float).reshape(-1)
        key = self._poly_visual_key_from_arrays(x_arr, y_arr, closed=closed)
        if key == getattr(self, attr_name, None):
            return
        setattr(self, attr_name, key)
        item.setPath(self._path_from_arrays(x_arr, y_arr, closed=closed))

    def _set_poly_polygon_if_changed(
        self,
        attr_name: str,
        item: QtWidgets.QGraphicsPolygonItem,
        xa: np.ndarray,
        ya: np.ndarray,
    ) -> None:
        x_arr = np.asarray(xa, dtype=float).reshape(-1)
        y_arr = np.asarray(ya, dtype=float).reshape(-1)
        key = self._poly_visual_key_from_arrays(
            x_arr,
            y_arr,
            closed=True,
            quant_scale=float(self._hud_fill_visual_key_quant_scale)
            if attr_name == "_road_fill_poly_key"
            else float(self._hud_path_visual_key_quant_scale),
        )
        if key == getattr(self, attr_name, None):
            return
        setattr(self, attr_name, key)
        item.setPolygon(
            QtGui.QPolygonF(
                [
                    QtCore.QPointF(float(x), float(y))
                    for x, y in zip(x_arr, y_arr)
                ]
            )
        )

    def set_playback_perf_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == bool(self._playback_perf_mode):
            return
        self._playback_perf_mode = enabled
        self._last_perf_visual_key = None
        try:
            self.setRenderHints(self._render_hints_perf if enabled else self._render_hints_normal)
        except Exception:
            pass
        try:
            self.viewport().update()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Segment metadata (from segment_id + optional meta_json road.segments)
    # ---------------------------------------------------------------------
    def _clear_segment_markers(self) -> None:
        """Hide dynamic segment boundary markers without rebuilding scene items."""
        for it in self._seg_marker_items:
            try:
                it.setVisible(False)
            except Exception:
                pass
        self._seg_marker_active_count = 0

    def _ensure_seg_marker_pool(self, n: int) -> None:
        sc = self.scene()
        while len(self._seg_marker_items) < int(max(0, n)):
            it = QtWidgets.QGraphicsLineItem()
            it.setZValue(1.25)
            it.setPen(self._seg_marker_pen)
            it.setVisible(False)
            sc.addItem(it)
            self._seg_marker_items.append(it)

    def _ensure_seg_fill_pool(self, n: int) -> None:
        """Ensure we have at least N segment overlay items (created lazily)."""
        sc = self.scene()
        while len(self._seg_fill_items) < n:
            it = QtWidgets.QGraphicsPathItem()
            it.setPen(self._seg_fill_nopen)
            # Between base fill (z~0) and lane/center lines (z~2)
            it.setZValue(1.2)
            it.setVisible(False)
            sc.addItem(it)
            self._seg_fill_items.append(it)

    def _hide_seg_fills(self) -> None:
        for it in self._seg_fill_items:
            it.setVisible(False)

    def _visible_polyline_point_budget(self) -> int:
        try:
            vp = self.viewport()
            vw = max(120, int(vp.width()))
            vh = max(120, int(vp.height()))
        except Exception:
            vw, vh = 320, 220
        span = max(vw, vh)
        budget = int(round(0.55 * float(span)))
        if bool(getattr(self, "_playback_perf_mode", False)):
            budget = min(budget, int(self._hud_perf_polyline_point_budget_cap))
        return int(
            max(
                int(self._hud_polyline_point_budget_min),
                min(int(self._hud_polyline_point_budget_max), budget),
            )
        )

    def _lane_polyline_point_budget(self, centerline_points: int) -> int:
        if bool(getattr(self, "_playback_perf_mode", False)):
            points = int(round(float(centerline_points) * float(self._hud_perf_lane_polyline_scale)))
            min_points = int(self._hud_perf_lane_polyline_min_points)
        else:
            points = int(round(float(centerline_points) * float(self._hud_lane_polyline_scale)))
            min_points = int(self._hud_lane_polyline_min_points)
        return int(
            max(
                int(min_points),
                min(int(centerline_points), points),
            )
        )

    def _fill_polyline_point_budget(self, centerline_points: int) -> int:
        if bool(getattr(self, "_playback_perf_mode", False)):
            points = int(round(float(centerline_points) * float(self._hud_perf_fill_polyline_scale)))
            min_points = int(self._hud_perf_fill_polyline_min_points)
        else:
            points = int(round(float(centerline_points) * float(self._hud_fill_polyline_scale)))
            min_points = int(self._hud_fill_polyline_min_points)
        return int(
            max(
                int(min_points),
                min(int(centerline_points), points),
            )
        )

    @staticmethod
    def _decimate_visible_polyline(max_points: int, *arrays: np.ndarray) -> tuple[np.ndarray, ...]:
        """Keep a viewport-sized point budget for HUD polylines.

        The HUD often sees thousands of source path samples inside the same visible window.
        Replaying every point into QPainterPath brings no visible benefit once adjacent points
        land within the same screen pixel, but it does cost a lot of Python/Qt calls.  We keep
        endpoints and uniformly subsample the middle so the rendered shape stays stable while the
        path build cost scales with the actual widget size, not with raw export density.
        """
        if not arrays:
            return tuple()
        ref = np.asarray(arrays[0])
        n = int(ref.shape[0]) if ref.ndim >= 1 else 0
        limit = int(max(8, max_points))
        if n <= limit:
            return tuple(np.asarray(arr) for arr in arrays)
        # For n > limit and positive endpoints, np.linspace(..., dtype=int) already
        # keeps 0..n-1 monotonic and endpoint-preserving, so no extra unique/insert work
        # is needed on every HUD redraw.
        sel = np.linspace(0, n - 1, num=limit, dtype=int)
        return tuple(np.asarray(arr)[sel] for arr in arrays)

    @staticmethod
    def _offset_lane_edges(
        xa: np.ndarray,
        ya: np.ndarray,
        half_width: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        x_arr = np.asarray(xa, dtype=float).reshape(-1)
        y_arr = np.asarray(ya, dtype=float).reshape(-1)
        if min(x_arr.size, y_arr.size) <= 1:
            return x_arr, y_arr, x_arr, y_arr
        dx = np.gradient(x_arr)
        dy = np.gradient(y_arr)
        norm = np.sqrt(dx * dx + dy * dy)
        norm[norm < 1e-9] = 1.0
        nx = -(dy / norm)
        ny = dx / norm
        w = float(half_width)
        return x_arr + nx * w, y_arr + ny * w, x_arr - nx * w, y_arr - ny * w

    @staticmethod
    def _path_from_xy(xa: np.ndarray, ya: np.ndarray, *, closed: bool = False) -> QtGui.QPainterPath:
        x_arr = np.asarray(xa, dtype=float).reshape(-1)
        y_arr = np.asarray(ya, dtype=float).reshape(-1)
        return RoadHudWidget._path_from_arrays(x_arr, y_arr, closed=closed)

    @staticmethod
    def _path_from_arrays(x_arr: np.ndarray, y_arr: np.ndarray, *, closed: bool = False) -> QtGui.QPainterPath:
        n = int(min(x_arr.size, y_arr.size))
        if n <= 0:
            return QtGui.QPainterPath()
        path = QtGui.QPainterPath(QtCore.QPointF(float(x_arr[0]), float(y_arr[0])))
        for x, y in zip(x_arr[1:n], y_arr[1:n]):
            path.lineTo(float(x), float(y))
        if bool(closed):
            path.closeSubpath()
        return path

    @staticmethod
    def _hud_font_key(font: QtGui.QFont) -> str:
        try:
            return str(font.key())
        except Exception:
            return f"{font.family()}|{font.pointSizeF():.2f}|{int(font.weight())}|{int(bool(font.italic()))}"

    def _ensure_hud_static_lines(self, b: DataBundle) -> tuple[str, ...]:
        bundle_key = int(id(b))
        if bundle_key == int(getattr(self, "_hud_static_bundle_key", 0)):
            return tuple(self._hud_static_lines)
        static_lines: list[str] = []
        try:
            acceptance_preview = list(format_acceptance_hud_lines(b, 0))
            static_lines.extend(str(line) for line in acceptance_preview[1:])
        except Exception:
            pass
        try:
            static_lines.extend(str(line) for line in format_suspension_hud_lines(b))
        except Exception:
            pass
        self._hud_static_bundle_key = bundle_key
        self._hud_static_lines = tuple(static_lines)
        self._hud_static_text_cache_key = None
        self._hud_static_text_cache_value = ""
        return tuple(self._hud_static_lines)

    def _hud_static_text(self, b: DataBundle, font: QtGui.QFont, max_px: int) -> str:
        static_lines = self._ensure_hud_static_lines(b)
        if not static_lines:
            return ""
        width_px = max(10, int(max_px))
        font_key = self._hud_font_key(font)
        cache_key = (int(id(b)), font_key, int(width_px))
        if cache_key != getattr(self, "_hud_static_text_cache_key", None):
            elided = self._elide_hud_lines(list(static_lines), font, width_px)
            self._hud_static_text_cache_key = cache_key
            self._hud_static_text_cache_value = "\n".join(elided)
        return str(getattr(self, "_hud_static_text_cache_value", "") or "")

    def _elide_hud_lines(self, lines: list[str], font: QtGui.QFont, max_px: int) -> list[str]:
        width_px = max(10, int(max_px))
        font_key = self._hud_font_key(font)
        cache = self._hud_elide_cache
        if len(cache) > 2048:
            cache.clear()
        fm = QtGui.QFontMetrics(font)
        out: list[str] = []
        for line in lines:
            text = str(line)
            key = (font_key, int(width_px), text)
            cached = cache.get(key)
            if cached is None:
                cached = fm.elidedText(text, QtCore.Qt.ElideRight, width_px)
                cache[key] = cached
            out.append(cached)
        return out

    @staticmethod
    def _surface_hint(rough_std_m: float) -> str:
        """Heuristic road surface hint from profile roughness std (meters)."""
        try:
            mm = float(rough_std_m) * 1000.0
        except Exception:
            return "неизвестно"
        if mm < 1.0:
            return "очень ровно"
        if mm < 3.0:
            return "ровно"
        if mm < 8.0:
            return "средне"
        if mm < 15.0:
            return "неровно"
        return "очень неровно"

    @staticmethod
    def _segment_tooltip(info: dict, seg_no: int, seg_total: int) -> str:
        """Human-readable tooltip for a road/test segment."""
        sid = info.get("id", "?")
        name = info.get("name") or info.get("title") or info.get("label")
        surface = info.get("surface") or info.get("road_type") or info.get("type")
        maneuver = info.get("maneuver") or info.get("manoeuvre")
        s0 = info.get("s0", None)
        s1 = info.get("s1", None)
        t0 = info.get("t0", None)
        t1 = info.get("t1", None)
        rough = info.get("rough_std_m", None)
        lines: list[str] = []
        head = f"Сегмент {seg_no}/{seg_total} (ID={sid})"
        if name:
            head += f": {name}"
        lines.append(head)
        if surface or maneuver:
            parts = []
            if surface:
                parts.append(f"дорога: {surface}")
            if maneuver:
                parts.append(f"манёвр: {maneuver}")
            lines.append("; ".join(parts))
        if (s0 is not None) and (s1 is not None):
            try:
                lines.append(f"s: {float(s0):.1f}…{float(s1):.1f} м   L≈{abs(float(s1)-float(s0)):.1f} м")
            except Exception:
                pass
        if (t0 is not None) and (t1 is not None):
            try:
                dt = float(t1) - float(t0)
                lines.append(f"t: {float(t0):.2f}…{float(t1):.2f} с   Δt≈{dt:.2f} с")
            except Exception:
                pass
        if rough is not None:
            try:
                mm = float(rough) * 1000.0
                lines.append(f"шероховатость σz≈{mm:.1f} мм ({RoadHudWidget._surface_hint(float(rough))})")
            except Exception:
                pass
        if "radius_m" in info:
            try:
                lines.append(f"радиус поворота: {float(info['radius_m']):.1f} м")
            except Exception:
                pass
        if "speed_kmh" in info:
            try:
                lines.append(f"цел. скорость: {float(info['speed_kmh']):.1f} км/ч")
            except Exception:
                pass
        note = info.get("note") or info.get("notes")
        if isinstance(note, str) and note.strip():
            lines.append(f"примечание: {note.strip()}")
        return "\n".join(lines)

    @staticmethod
    def _extract_road_segments_meta(meta: Any) -> dict[int, dict]:
        """Try to find road/test segment metadata in meta_json.

        Supported (recommended) structures:
          - meta['road']['segments'] = [ {id, name, surface, maneuver, ...}, ...]
          - meta['road_segments'] = [ ... ]
          - meta['segments'] = [ ... ]  (fallback)
          - meta['road']['segments_by_id'] = { "1": {...}, ... } (fallback)
        """
        if not isinstance(meta, dict):
            return {}

        def dig(obj: Any, path: tuple[str, ...]) -> Any:
            cur = obj
            for k in path:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            return cur

        candidates: list[Any] = []
        for p in [
            ("road", "segments"),
            ("road", "road_segments"),
            ("road_segments",),
            ("segments",),
        ]:
            obj = dig(meta, p)
            if obj is not None:
                candidates.append(obj)
        for p in [
            ("road", "segments_by_id"),
            ("road_segments_by_id",),
            ("segments_by_id",),
        ]:
            obj = dig(meta, p)
            if isinstance(obj, dict):
                candidates.append(obj)

        seg_map: dict[int, dict] = {}
        for cand in candidates:
            if isinstance(cand, dict):
                items = list(cand.values())
            elif isinstance(cand, list):
                items = cand
            else:
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                sid = (
                    it.get("id")
                    if it.get("id") is not None
                    else it.get("seg_id")
                    if it.get("seg_id") is not None
                    else it.get("segment_id")
                    if it.get("segment_id") is not None
                    else it.get("segmentId")
                )
                if sid is None:
                    continue
                try:
                    sid_i = int(sid)
                except Exception:
                    continue
                seg_map[sid_i] = it
        return seg_map

    @staticmethod
    def _first_str(d: dict, keys: list[str]) -> Optional[str]:
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    @staticmethod
    def _norm_surface_key(s: str) -> str:
        s0 = (s or "").strip().lower()
        if not s0:
            return ""
        # RU/EN fuzzy matching
        if "асф" in s0 or "asph" in s0 or "highway" in s0:
            return "asphalt"
        if "город" in s0 or "city" in s0 or "urban" in s0:
            return "city"
        if "грун" in s0 or "dirt" in s0 or "gravel" in s0 or "soil" in s0:
            return "dirt"
        if "бетон" in s0 or "concrete" in s0:
            return "concrete"
        if "лед" in s0 or "ice" in s0 or "snow" in s0:
            return "ice"
        return s0

    def _segment_fill_color(self, info: Optional[dict], is_current: bool) -> QtGui.QColor:
        """Muted segment tint (avoid "girlands")."""
        # Default: bluish-grey (asphalt-like)
        base = QtGui.QColor(60, 78, 96)
        rough_mm = None
        surface_key = ""

        if isinstance(info, dict):
            surface = (
                info.get("surface")
                or info.get("road_type")
                or info.get("type")
                or info.get("kind")
            )
            if isinstance(surface, str):
                surface_key = self._norm_surface_key(surface)
            if "rough_std_m" in info and info.get("rough_std_m") is not None:
                try:
                    rough_mm = float(info.get("rough_std_m")) * 1000.0
                except Exception:
                    rough_mm = None

        if surface_key in ("dirt", "gravel"):
            base = QtGui.QColor(96, 82, 62)   # brownish-grey
        elif surface_key in ("city",):
            base = QtGui.QColor(72, 76, 82)   # neutral grey
        elif surface_key in ("concrete",):
            base = QtGui.QColor(78, 86, 92)
        elif surface_key in ("ice", "snow"):
            base = QtGui.QColor(78, 92, 106)

        # If surface unknown, derive a gentle tint by roughness
        if not surface_key and rough_mm is not None:
            if rough_mm < 2.0:
                base = QtGui.QColor(60, 78, 96)
            elif rough_mm < 6.0:
                base = QtGui.QColor(70, 78, 86)
            elif rough_mm < 15.0:
                base = QtGui.QColor(90, 82, 64)
            else:
                base = QtGui.QColor(92, 74, 56)

        base.setAlpha(90 if is_current else 45)
        return base

    def _apply_lane_pens_if_needed(self) -> None:
        key = (
            int(round(float(self._history_m) * 10.0)),
            int(round(float(self._lookahead_m) * 10.0)),
        )
        if key == self._last_lane_pen_key:
            return
        self._last_lane_pen_key = key
        try:
            tot = float(self._history_m + self._lookahead_m + 1e-9)
            k0 = float(self._history_m / tot)
            g_lane = QtGui.QLinearGradient(QtCore.QPointF(0.0, -self._history_m), QtCore.QPointF(0.0, self._lookahead_m))
            g_lane.setColorAt(0.0, QtGui.QColor(80, 80, 80, 35))
            g_lane.setColorAt(_clamp(k0, 0.0, 1.0), QtGui.QColor(130, 130, 130, 200))
            g_lane.setColorAt(1.0, QtGui.QColor(80, 80, 80, 70))
            pen_lane = QtGui.QPen(QtGui.QBrush(g_lane), 0.03)
            self.lane_l.setPen(pen_lane)
            self.lane_r.setPen(pen_lane)

            g_c = QtGui.QLinearGradient(QtCore.QPointF(0.0, -self._history_m), QtCore.QPointF(0.0, self._lookahead_m))
            g_c.setColorAt(0.0, QtGui.QColor(120, 120, 120, 25))
            g_c.setColorAt(_clamp(k0, 0.0, 1.0), QtGui.QColor(180, 180, 180, 160))
            g_c.setColorAt(1.0, QtGui.QColor(120, 120, 120, 60))
            self.centerline.setPen(QtGui.QPen(QtGui.QBrush(g_c), 0.02, QtCore.Qt.DashLine))
        except Exception:
            pass

    def _update_car_path_if_needed(self) -> None:
        key = (
            int(round(float(self.geom.track) * 1000.0)),
            int(round(float(self.geom.wheel_width) * 1000.0)),
            int(round(float(self.geom.wheelbase) * 1000.0)),
            int(round(float(self.geom.wheel_radius) * 1000.0)),
        )
        if key == self._car_path_key:
            return
        self._car_path_key = key
        car_w = max(0.6, float(self.geom.track) + float(self.geom.wheel_width))
        car_l = max(0.8, float(self.geom.wheelbase) + 2.0 * float(self.geom.wheel_radius))
        xh = 0.5 * car_w
        yb = -2.0
        self.car.setPath(
            self._path_from_xy(
                np.asarray([-xh, +xh, +xh, -xh], dtype=float),
                np.asarray([yb, yb, yb + car_l, yb + car_l], dtype=float),
                closed=True,
            )
        )

    def _perf_visual_key(
        self,
        *,
        x0: float,
        y0: float,
        yaw: float,
    ) -> tuple[int, ...]:
        pixel_world_step = max(1e-4, 1.0 / max(1e-3, float(self._px_per_m)))
        span_m = max(1.0, float(self._lookahead_m + self._history_m + 4.0))
        yaw_step = max(1e-4, pixel_world_step / span_m)
        try:
            vp = self.viewport()
            viewport_w = int(max(1, vp.width()))
            viewport_h = int(max(1, vp.height()))
        except Exception:
            viewport_w, viewport_h = 0, 0
        return (
            int(round(float(x0) / pixel_world_step)),
            int(round(float(y0) / pixel_world_step)),
            int(round(float(yaw) / yaw_step)),
            int(round(float(self._lookahead_m) * 10.0)),
            int(round(float(self._history_m) * 10.0)),
            int(viewport_w),
            int(viewport_h),
            int(bool(self.show_lanes)),
        )

    def _ensure_segment_cache(self, b: DataBundle) -> None:
        """Compute segment boundaries + merge optional meta_json labels."""
        key = id(b)
        if self._seg_cache_key == key:
            return

        self._seg_cache_key = key
        self._seg_starts = None
        self._seg_ends = None
        self._seg_ids = None
        self._seg_full = None
        self._seg_infos = []
        self._seg_start_to_idx = {}
        self._seg_id_to_info = {}

        # Canonical channel (no aliases / no silent compatibility bridges).
        seg = b.get("сегмент_id", None)
        if seg is None:
            return

        try:
            seg_arr = np.asarray(seg).astype(int).reshape(-1)
        except Exception:
            return
        if seg_arr.size < 2:
            return
        self._seg_full = seg_arr

        # Segment boundaries by changes in segment_id over time index
        changes = np.nonzero(seg_arr[1:] != seg_arr[:-1])[0] + 1
        starts = np.concatenate(([0], changes))
        ends = np.concatenate((changes, [seg_arr.size]))
        ids = seg_arr[starts]

        self._seg_starts = starts
        self._seg_ends = ends
        self._seg_ids = ids

        # World distance (SERVICE/DERIVED) and time axis (canonical).
        try:
            s_world_arr = np.asarray(b.ensure_s_world(), dtype=float).reshape(-1)
        except Exception:
            s_world_arr = None
        try:
            t_arr = np.asarray(b.t, dtype=float).reshape(-1)
        except Exception:
            t_arr = None

        # Road profile roughness per segment (from ensure_road_profile)
        ss, zz = None, None
        try:
            ss, zz = b.ensure_road_profile()
            ss = np.asarray(ss, dtype=float).reshape(-1)
            zz = np.asarray(zz, dtype=float).reshape(-1)
            if zz.size:
                zz = zz - float(np.nanmean(zz))
        except Exception:
            ss, zz = None, None

        meta_map = self._extract_road_segments_meta(getattr(b, "meta", None))

        for j, (st, en, sid) in enumerate(zip(starts, ends, ids)):
            info: dict = {"idx": int(j), "id": int(sid), "i0": int(st), "i1": int(en)}
            if s_world_arr is not None and en - 1 < s_world_arr.size:
                try:
                    info["s0"] = float(s_world_arr[st])
                    info["s1"] = float(s_world_arr[en - 1])
                    info["len_m"] = float(abs(info["s1"] - info["s0"]))
                except Exception:
                    pass
            if t_arr is not None and en - 1 < t_arr.size:
                try:
                    info["t0"] = float(t_arr[st])
                    info["t1"] = float(t_arr[en - 1])
                except Exception:
                    pass

            # Roughness estimate from road profile
            if ss is not None and zz is not None and ("s0" in info) and ("s1" in info):
                try:
                    a = min(float(info["s0"]), float(info["s1"]))
                    bnd = max(float(info["s0"]), float(info["s1"]))
                    m = (ss >= a) & (ss <= bnd)
                    if np.any(m):
                        info["rough_std_m"] = float(np.nanstd(zz[m]))
                except Exception:
                    pass

            # Optional meta_json merge (human readable)
            md = meta_map.get(int(sid))
            if isinstance(md, dict):
                name = self._first_str(md, ["name", "title", "label", "caption", "display_name"])
                if name:
                    info["name"] = name
                surface = self._first_str(md, ["surface", "road_type", "type", "kind", "class"])
                if surface:
                    info["surface"] = surface
                note = self._first_str(md, ["note", "notes", "comment"])
                if note:
                    info["note"] = note

                # Maneuver can be str or dict
                man = md.get("maneuver") if "maneuver" in md else md.get("manoeuvre") if "manoeuvre" in md else md.get("man")
                if isinstance(man, str) and man.strip():
                    info["maneuver"] = man.strip()
                elif isinstance(man, dict):
                    man_name = self._first_str(man, ["name", "title", "label", "kind", "type"])
                    if man_name:
                        info["maneuver"] = man_name
                    for rk in ["radius_m", "radius", "turn_radius_m"]:
                        if rk in man:
                            try:
                                info["radius_m"] = float(man[rk])
                            except Exception:
                                pass
                    for sk in ["speed_kmh", "v_kmh", "target_speed_kmh"]:
                        if sk in man:
                            try:
                                info["speed_kmh"] = float(man[sk])
                            except Exception:
                                pass

                # Top-level speed target / limit
                for sk in ["speed_kmh", "v_kmh", "target_speed_kmh"]:
                    if sk in md and "speed_kmh" not in info:
                        try:
                            info["speed_kmh"] = float(md[sk])
                        except Exception:
                            pass

            self._seg_infos.append(info)
            self._seg_start_to_idx[int(st)] = int(j)
            self._seg_id_to_info[int(sid)] = info

    def _update_segment_fills(self, b: DataBundle, idxs: np.ndarray, xL: np.ndarray, yL: np.ndarray, xR: np.ndarray, yR: np.ndarray, cur_seg_id: Optional[int]) -> None:
        """Update (or hide) muted segment fills on the road ribbon."""
        if not getattr(self, "show_seg_colors", True):
            self._hide_seg_fills()
            return
        if xL is None or xR is None or xL.size < 2 or xR.size < 2:
            self._hide_seg_fills()
            return

        seg_full = b.get("сегмент_id", None)
        if seg_full is None:
            seg_full = b.get("segment_id", None)
        if seg_full is None:
            self._hide_seg_fills()
            return
        try:
            seg_full = np.asarray(seg_full).astype(int).reshape(-1)
        except Exception:
            self._hide_seg_fills()
            return

        try:
            seg_sel = seg_full[idxs]
        except Exception:
            self._hide_seg_fills()
            return
        if seg_sel.size < 2:
            self._hide_seg_fills()
            return

        changes = np.nonzero(seg_sel[1:] != seg_sel[:-1])[0] + 1
        run_starts = np.concatenate(([0], changes))
        run_ends = np.concatenate((changes, [seg_sel.size]))

        runs: list[tuple[int, int, int]] = []
        for rs, re_ in zip(run_starts, run_ends):
            if re_ - rs < 2:
                continue
            runs.append((int(seg_sel[rs]), int(rs), int(re_)))

        self._ensure_seg_fill_pool(len(runs))

        # Update visible runs
        for j, (sid, a, bnd) in enumerate(runs):
            it = self._seg_fill_items[j]
            info = self._seg_id_to_info.get(int(sid))
            is_cur = (cur_seg_id is not None) and (int(sid) == int(cur_seg_id))
            col = self._segment_fill_color(info, is_cur)

            pts: list[QtCore.QPointF] = []
            for k in range(a, bnd):
                pts.append(QtCore.QPointF(float(xL[k]), float(yL[k])))
            for k in range(bnd - 1, a - 1, -1):
                pts.append(QtCore.QPointF(float(xR[k]), float(yR[k])))

            path = QtGui.QPainterPath()
            if pts:
                path.addPolygon(QtGui.QPolygonF(pts))
            it.setPath(path)
            it.setBrush(QtGui.QBrush(col))
            it.setVisible(True)

            # Tooltip: show the segment we are in (by ID)
            if info is not None and self._seg_infos:
                it.setToolTip(self._segment_tooltip(info, int(info.get("idx", 0)) + 1, len(self._seg_infos)))
            else:
                it.setToolTip(f"ID={sid}")

        # Hide unused pool items
        for j in range(len(runs), len(self._seg_fill_items)):
            self._seg_fill_items[j].setVisible(False)

    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        eff_show_accel = bool(self.show_accel) and not bool(self._playback_perf_mode)
        eff_show_text = bool(self.show_text) and not bool(self._playback_perf_mode)
        eff_show_seg_markers = bool(self.show_seg_markers) and not bool(self._playback_perf_mode)
        eff_show_seg_colors = bool(self.show_seg_colors) and not bool(self._playback_perf_mode)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=sample_i0, i1=sample_i1, alpha=alpha)
        xw, yw = b.ensure_world_xy()
        n = len(xw)
        if n <= 1:
            return

        idx_ref = int(_clamp(int(i), 0, n - 1))
        yaw_series = b.get("yaw_рад", 0.0)
        vx_series = b.get("скорость_vx_м_с", 0.0)
        vy_series = b.get("скорость_vy_м_с", 0.0)
        yaw_rate_series = b.get("yaw_rate_рад_с", 0.0)
        ax_series = b.get("ускорение_продольное_ax_м_с2", 0.0)
        ay_series = b.get("ускорение_поперечное_ay_м_с2", 0.0)
        s_world = b.ensure_s_world()

        yaw = sample(yaw_series, 0.0)
        x0 = sample(xw, float(xw[idx_ref]))
        y0 = sample(yw, float(yw[idx_ref]))

        # Auto lookahead scaling: more road shown at higher speed (instrument-cluster style)
        if getattr(self, "auto_lookahead", False):
            try:
                vx0 = sample(vx_series, 0.0)
            except Exception:
                vx0 = 0.0
            self._lookahead_m = float(_clamp(20.0 + vx0 * 4.0, 40.0, 140.0))
            self._history_m = float(_clamp(8.0 + vx0 * 1.5, 15.0, 60.0))

        if bool(self._playback_perf_mode):
            perf_visual_key = self._perf_visual_key(x0=float(x0), y0=float(y0), yaw=float(yaw))
            if perf_visual_key == self._last_perf_visual_key:
                return
        else:
            perf_visual_key = None
            self._last_perf_visual_key = None

        # Pen gradients: brighter near the car, softer far away (instrument-cluster style)
        self._apply_lane_pens_if_needed()

        # Convert world points to car-local coordinates (car at origin).
        # Car frame: X forward, Y left. HUD scene: X right, Y forward (up).
        c, s = np.cos(-yaw), np.sin(-yaw)

        # Window of indices (fast)
        win_i0 = max(0, i - 200)
        win_i1 = min(n, i + 400)

        xs = xw[win_i0:win_i1] - x0
        ys = yw[win_i0:win_i1] - y0
        x_fwd = c * xs - s * ys
        y_left = s * xs + c * ys

        xl = -y_left
        yl = x_fwd

        # Keep only forward range for lookahead and some history
        mask = (yl >= -self._history_m) & (yl <= self._lookahead_m)
        xl = xl[mask]
        yl = yl[mask]

        # Dynamic overlays (segment markers) are recreated each frame.
        # Clear early so stale markers do not remain if we early‑return.
        self._clear_segment_markers()
        self._hide_seg_fills()
        if len(xl) < 2:
            return

        # Indices in the original arrays corresponding to the visible road window
        idxs = np.arange(win_i0, win_i1)[mask]

        max_points = self._visible_polyline_point_budget()
        xl, yl, idxs = self._decimate_visible_polyline(max_points, xl, yl, idxs)
        self._set_poly_path_if_changed("_centerline_path_key", self.centerline, xl, yl)

        # Lane boundaries via offset along normal of tangent
        if self.show_lanes:
            lane_points = self._lane_polyline_point_budget(len(xl))
            lane_xl, lane_yl, lane_idxs = self._decimate_visible_polyline(lane_points, xl, yl, idxs)
            w = 0.5 * float(self._lane_width)
            xlL, ylL, xlR, ylR = self._offset_lane_edges(lane_xl, lane_yl, w)
            self._set_poly_path_if_changed("_lane_l_path_key", self.lane_l, xlL, ylL)
            self._set_poly_path_if_changed("_lane_r_path_key", self.lane_r, xlR, ylR)
            self.lane_l.show()
            self.lane_r.show()


            # Segment tint overlays (muted, non-flashing)
            try:
                self._ensure_segment_cache(b)
                cur_seg_id = None
                seg_full = self._seg_full
                if seg_full is not None:
                    cur_seg_id = int(seg_full[i])
                if eff_show_seg_colors:
                    self._update_segment_fills(b, lane_idxs, xlL, ylL, xlR, ylR, cur_seg_id)
                else:
                    self._hide_seg_fills()
            except Exception:
                # Never fail drawing due to metadata issues
                self._hide_seg_fills()

            # Road ribbon fill between lane edges.
            try:
                fill_points = self._fill_polyline_point_budget(len(lane_xl))
                fill_xlL, fill_ylL, fill_xlR, fill_ylR, _fill_idxs = self._decimate_visible_polyline(fill_points, xlL, ylL, xlR, ylR, lane_idxs)
                self._set_poly_polygon_if_changed(
                    "_road_fill_poly_key",
                    self.road_fill,
                    np.concatenate((fill_xlL, fill_xlR[::-1])),
                    np.concatenate((fill_ylL, fill_ylR[::-1])),
                )
                self.road_fill.show()
            except Exception:
                self.road_fill.hide()
        else:
            self.lane_l.hide()
            self.lane_r.hide()
            self._lane_l_path_key = None
            self._lane_r_path_key = None
            try:
                self.road_fill.hide()
                self._road_fill_poly_key = None
            except Exception:
                pass

        # Segment boundary markers (across lane width).
        # Minimalistic on purpose: dashed markers + tooltip. No labels (avoid clutter).
        if eff_show_seg_markers:
            try:
                self._ensure_segment_cache(b)
                starts = self._seg_starts
                if starts is not None and len(starts) > 1 and self._seg_infos:
                    self._ensure_seg_marker_pool(int(len(starts)))
                    n_all = int(len(xw))
                    marker_count = 0

                    def to_hud(idx: int) -> tuple[float, float]:
                        dx = float(xw[idx] - x0)
                        dy = float(yw[idx] - y0)
                        x_f = float(c * dx - s * dy)
                        y_l = float(s * dx + c * dy)
                        return float(-y_l), float(x_f)  # HUD: x right, y forward

                    for start_idx in starts[1:]:
                        k = int(start_idx)
                        if k < win_i0 or k >= win_i1:
                            continue
                        # Also require that this boundary is in the currently visible (masked) window
                        try:
                            if not bool(mask[k - win_i0]):
                                continue
                        except Exception:
                            pass
                        if k <= 0 or k >= n_all:
                            continue

                        cx, cy = to_hud(k)

                        # Tangent -> normal (across the road)
                        k0 = max(0, k - 1)
                        k1 = min(n_all - 1, k + 1)
                        xA, yA = to_hud(k0)
                        xB, yB = to_hud(k1)
                        tx, ty = (xB - xA), (yB - yA)
                        nn = float(math.hypot(tx, ty))
                        if nn < 1e-6:
                            continue
                        nx, ny = (-ty / nn), (tx / nn)
                        half = 0.5 * float(self._lane_width)
                        x1, y1 = (cx - nx * half), (cy - ny * half)
                        x2, y2 = (cx + nx * half), (cy + ny * half)

                        it = self._seg_marker_items[marker_count]
                        marker_count += 1
                        it.setLine(float(x1), float(y1), float(x2), float(y2))
                        j = self._seg_start_to_idx.get(k, None)
                        if j is not None and 0 <= j < len(self._seg_infos):
                            it.setToolTip(self._segment_tooltip(self._seg_infos[j], j + 1, len(self._seg_infos)))
                        else:
                            it.setToolTip("")
                        it.setVisible(True)
                    self._seg_marker_active_count = int(marker_count)
            except Exception:
                # Optional overlay must never break the cockpit.
                pass

        # Car silhouette at origin
        # Силуэт машины на миникарте — в одном масштабе с расчётной геометрией.
        yb = -2.0  # a bit down
        self._update_car_path_if_needed()

        # Horizontal accel vector at COM (car frame): ax forward, ay left
        if eff_show_accel:
            ax = sample(ax_series, 0.0)
            ay = sample(ay_series, 0.0)
            # scale (m/s^2 -> meters)
            a_scale = 0.6
            p0 = QtCore.QPointF(0.0, yb + 1.0)
            p1 = QtCore.QPointF(_clamp(-ay * a_scale, -6.0, 6.0), _clamp((ax * a_scale), -6.0, 6.0) + (yb + 1.0))
            self.arrow_a.set_arrow(p0, p1, rgb=(255, 90, 120), alpha=240, head_len_m=0.35, head_w_m=0.25)
        else:
            self.arrow_a.hide()

        # Overlay text: speed/turn/accels + segment progress (no text overlap).
        if eff_show_text:
            vx = sample(vx_series, 0.0)
            vy = sample(vy_series, 0.0)
            v_mps = math.hypot(vx, vy)  # DERIVED from model outputs (vx, vy)
            yaw_rate = sample(yaw_rate_series, 0.0)
            ax = sample(ax_series, 0.0)
            ay = sample(ay_series, 0.0)
            s = sample(s_world, 0.0)

            # Signed radius estimate
            R = float("inf")
            if abs(yaw_rate) > 1e-6 and v_mps > 1e-3:
                R = v_mps / yaw_rate

            # Segment / progress
            seg_line = ""
            road_line = ""
            cur_seg_info: dict = {}
            try:
                self._ensure_segment_cache(b)
                if self._seg_starts is not None and self._seg_infos:
                    j = int(np.searchsorted(self._seg_starts, i, side="right") - 1)
                    j = max(0, min(j, len(self._seg_infos) - 1))
                    info = self._seg_infos[j]
                    cur_seg_info = info
                    seg_id = int(info.get("seg_id", 0))
                    s0 = float(info.get("s0", 0.0))
                    s1 = float(info.get("s1", 0.0))

                    u = float("nan")
                    if s1 > s0 + 1e-6:
                        u = (s - s0) / (s1 - s0)
                    seg_name = (
                        info.get("name")
                        or info.get("title")
                        or info.get("label")
                    )
                    seg_name = seg_name.strip() if isinstance(seg_name, str) else ""
                    seg_head = f"Сегмент {j+1}/{len(self._seg_infos)}"
                    if seg_name:
                        seg_head += f": {seg_name}"
                    else:
                        seg_head += f" (ID={seg_id})"

                    if np.isfinite(u):
                        u = float(max(0.0, min(1.0, u)))
                        seg_line = f"{seg_head}  {u*100:4.0f}%  S={s0:.0f}…{s1:.0f} м"
                    else:
                        seg_line = seg_head

                    rough_std_m = float(info.get("rough_std_m", float("nan")))
                    if math.isfinite(rough_std_m):
                        surface_txt = (
                            info.get("surface")
                            or info.get("road_type")
                            or info.get("type")
                            or info.get("kind")
                        )
                        surface_txt = surface_txt.strip() if isinstance(surface_txt, str) else ""
                        hint = self._surface_hint(rough_std_m)
                        if surface_txt:
                            road_line = f"Дорога: {surface_txt}; σz≈{rough_std_m*1000.0:.1f} мм, {hint}"
                        else:
                            road_line = f"Дорога: σz≈{rough_std_m*1000.0:.1f} мм, {hint}"
            except Exception:
                pass

            # Simple maneuver classifier (conservative)
            man_parts: list[str] = []
            # If meta_json provides a maneuver label for the current segment — show it first.
            meta_maneuver = cur_seg_info.get("maneuver") if isinstance(cur_seg_info, dict) else ""
            meta_maneuver = meta_maneuver.strip() if isinstance(meta_maneuver, str) else ""
            if meta_maneuver:
                man_parts.append(f"по тесту: {meta_maneuver}")
            if abs(yaw_rate) > 0.12 and v_mps > 1.0:
                man_parts.append("поворот влево" if yaw_rate > 0 else "поворот вправо")
                if np.isfinite(R):
                    man_parts.append(f"R≈{abs(R):.0f} м")
            else:
                man_parts.append("прямо")
            if ax > 0.6:
                man_parts.append("разгон")
            elif ax < -0.6:
                man_parts.append("торможение")
            man_line = "Манёвр: " + ", ".join(man_parts)

            # Compose HUD lines (Russian; elide per line)
            dynamic_lines: list[str] = [f"v  {v_mps*3.6:6.1f} км/ч"]
            context_lines: list[str] = []
            if seg_line:
                context_lines.append(seg_line)
            if road_line:
                context_lines.append(road_line)
            if man_line:
                context_lines.append(man_line)
            dynamic_lines += [
                f"ψ̇ {np.degrees(yaw_rate):6.2f} °/с   R {'—' if not np.isfinite(R) else f'{abs(R):.0f} м'}",
                f"ax {ax:+6.2f} м/с²   ay {ay:+6.2f} м/с²",
            ]
            try:
                acceptance_lines = list(format_acceptance_hud_lines(b, i))
                if acceptance_lines:
                    dynamic_lines.append(str(acceptance_lines[0]))
            except Exception:
                pass

            max_px = max(260, int(self.viewport().width() * 0.78))
            fnt = self.hud_text.font()
            dynamic_lines = self._elide_hud_lines(dynamic_lines, fnt, max_px)
            dynamic_txt = "\n".join(dynamic_lines)
            _set_graphics_text_if_changed(self.hud_text, dynamic_txt)
            top_x = -7.6
            top_y = self._lookahead_m - 4.5
            _set_graphics_pos_if_changed(self.hud_text, top_x, top_y)
            self.hud_text.show()
            line_step_m = max(0.001, float(QtGui.QFontMetricsF(fnt).lineSpacing()) / max(1.0, float(self._px_per_m)))
            context_count = 0
            if context_lines:
                context_lines = self._elide_hud_lines(context_lines, fnt, max_px)
                context_txt = "\n".join(context_lines)
                _set_graphics_text_if_changed(self.hud_text_context, context_txt)
                context_y = float(top_y) - (line_step_m * float(len(dynamic_lines)))
                _set_graphics_pos_if_changed(self.hud_text_context, top_x, context_y)
                self.hud_text_context.show()
                context_count = len(context_lines)
            else:
                self.hud_text_context.hide()
            static_txt = self._hud_static_text(b, fnt, max_px)
            if static_txt:
                _set_graphics_text_if_changed(self.hud_text_static, static_txt)
                static_y = float(top_y) - (line_step_m * float(len(dynamic_lines) + context_count))
                _set_graphics_pos_if_changed(self.hud_text_static, top_x, static_y)
                self.hud_text_static.show()
            else:
                self.hud_text_static.hide()
        else:
            self.hud_text.hide()
            self.hud_text_context.hide()
            self.hud_text_static.hide()

        # Frame
        scene_rect = QtCore.QRectF(-8.0, -self._history_m - 4.0, 16.0, self._lookahead_m + self._history_m + 8.0)
        self.scene.setSceneRect(scene_rect)
        if bool(getattr(self, "_auto_view_fit", True)):
            self._fit_view_to_scene_if_needed(scene_rect)
        if perf_visual_key is not None:
            self._last_perf_visual_key = perf_visual_key

# -----------------------------
# 3D View (optional)
# -----------------------------




class Car3DWidget(QtWidgets.QWidget):
    """3D-вид (настоящий 3D, не псевдо).

    Требования проекта:
      - рама = параллелепипед (box mesh)
      - колёса = цилиндры (cylinder mesh)
      - дорога в 3D: лента (ribbon mesh) + кромки + «штрихи движения» (поперечные полосы)

    Геометрия берётся из ViewGeometry (wheelbase/track/wheel_radius/wheel_width).
    Координаты:
      x — вперёд, y — влево, z — вверх.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, compact: bool = False):
        super().__init__(parent)
        self._has_live_gl_context = bool(_HAS_GL)
        self.geom: ViewGeometry = ViewGeometry()
        self._visual = {
            "show_road": True,
            "show_vectors": True,
        }

        # ---- Road preview params (meters)
        self._road_width_m = float(ViewGeometry().road_width)
        self._lookahead_min_m = 35.0
        self._lookahead_max_m = 140.0
        self._lookbehind_m = 12.0
        # IMPORTANT:
        # - the road surface mesh must stay dense enough to show actual relief;
        # - the visible wire grid may be much sparser than the surface mesh;
        # - the wheel contact patch must remain a subset of the road mesh, but must be
        #   computed from a local road subgrid around each wheel instead of testing the
        #   full visible road mesh every frame.
        self._road_pts = 220
        self._road_lat_pts = 15
        self._playback_active = False
        self._playback_perf_mode = False
        self._road_grid_cross_stride = 4
        self._stripe_step_m = 1.0  # legacy knob kept for compatibility/log readability
        self._stripe_half_factor = 0.92
        self._road_grid_nominal_visible_len_m = float(self._lookbehind_m + self._auto_lookahead(0.0))
        self._road_grid_max_visible_len_m = float(self._road_grid_nominal_visible_len_m)
        self._road_native_long_step_m = 0.06
        self._bundle_history_m: Optional[float] = None
        self._bundle_lookahead_m: Optional[float] = None
        self._road_grid_cross_spacing_m: Optional[float] = None
        self._road_grid_cross_spacing_viewport_key: Optional[int] = None
        self._road_surface_spacing_m: Optional[float] = None
        self._road_surface_spacing_cache_key: Optional[tuple[int, int, int]] = None
        self._road_path_s_world_cache: Optional[np.ndarray] = None
        self._road_path_nx_world_cache: Optional[np.ndarray] = None
        self._road_path_ny_world_cache: Optional[np.ndarray] = None
        self._show_piston_markers_debug = False
        self._layout_transition_active = False
        self._cylinder_truth_gates: Dict[str, Dict[str, Any]] = _evaluate_all_cylinder_truth_gates(None)

        # ---- Vector scales (convert physical units to screen meters)
        self._vel_scale = 0.35    # (m/s)  -> (m)
        self._accel_scale = 0.25  # (m/s²) -> (m)

        if not _HAS_GL:
            lbl = QtWidgets.QLabel(
                "3D недоступен: установите PyOpenGL + pyqtgraph (pip install pyopengl pyqtgraph).\n"
                "Остальные 2D-панели продолжают работать.",
                self,
            )
            lbl.setWordWrap(True)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(8, 8, 8, 8)
            lay.addWidget(lbl)
            lay.addStretch(1)
            return

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor(10, 10, 10)
        self.view.opts["distance"] = 9.0
        self.view.opts["elevation"] = 18.0
        self.view.opts["azimuth"] = -55.0

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._layout_pause_placeholder = QtWidgets.QLabel(
            "3D временно приостановлен: перестройка layout/окна.\n"
            "После завершения перемещения/масштабирования кадр будет восстановлен автоматически.",
            self,
        )
        self._layout_pause_placeholder.setWordWrap(True)
        self._layout_pause_placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._layout_pause_placeholder.hide()
        lay.addWidget(self.view, 1)
        lay.addWidget(self._layout_pause_placeholder, 1)

        # Static scene
        self._grid = gl.GLGridItem()
        self._grid.setSize(10, 10)
        self._grid.setSpacing(1, 1)
        self._grid.translate(0, 0, 0)
        self.view.addItem(self._grid)
        try:
            self._grid.setVisible(False)
        except Exception:
            pass

        # Dynamic items (created in _rebuild_scene_items)
        self._road_mesh: Optional["gl.GLMeshItem"] = None
        self._road_edges: Optional["gl.GLLinePlotItem"] = None
        self._road_stripes: Optional["gl.GLLinePlotItem"] = None

        self._chassis_mesh: Optional["gl.GLMeshItem"] = None
        self._wheel_meshes: List["gl.GLMeshItem"] = []
        self._cyl_body_meshes: List["gl.GLMeshItem"] = []
        self._cyl_chamber_meshes: List["gl.GLMeshItem"] = []
        self._cyl_rod_meshes: List["gl.GLMeshItem"] = []
        self._cyl_piston_meshes: List["gl.GLMeshItem"] = []
        self._cyl_piston_ring_lines: List["gl.GLLinePlotItem"] = []
        self._cyl_rod_core_lines: List["gl.GLLinePlotItem"] = []
        self._cyl_piston_markers: Optional[Any] = None
        self._cyl_frame_mount_markers: Optional["gl.GLLinePlotItem"] = None

        self._contact_pts: Optional["gl.GLLinePlotItem"] = None
        self._contact_links: Optional["gl.GLLinePlotItem"] = None
        self._arm_lines: Optional["gl.GLLinePlotItem"] = None
        self._cyl1_lines: Optional["gl.GLLinePlotItem"] = None
        self._cyl2_lines: Optional["gl.GLLinePlotItem"] = None
        self._contact_patch_mesh: Optional["gl.GLMeshItem"] = None

        self._vec_vel: Optional["gl.GLLinePlotItem"] = None
        self._vec_acc: Optional["gl.GLLinePlotItem"] = None

        # Cached faces for the road ribbon (depends only on N points)
        self._road_faces_cache: Dict[tuple[int, int], np.ndarray] = {}

        # Base meshes kept in canonical local basis (x forward, y left, z up).
        self._box_base_vertices: Optional[np.ndarray] = None
        self._box_faces: Optional[np.ndarray] = None
        self._wheel_base_vertices: Optional[np.ndarray] = None
        self._wheel_faces: Optional[np.ndarray] = None
        self._unit_cyl_y_vertices: Optional[np.ndarray] = None
        self._unit_cyl_faces: Optional[np.ndarray] = None

        self._rebuild_scene_items()

    def has_live_gl_context(self) -> bool:
        """Return True only when the widget owns a real OpenGL viewport."""
        return bool(getattr(self, "_has_live_gl_context", False))

    # ---------------------------- mesh helpers ----------------------------

    @staticmethod
    def _faces_for_ribbon(n_points: int) -> np.ndarray:
        """Return faces for a ribbon with 2*n_points vertices (left/right interleaved)."""
        n = int(max(2, n_points))
        faces = []
        for j in range(n - 1):
            i0 = 2 * j
            i1 = 2 * j + 1
            i2 = 2 * (j + 1) + 1
            i3 = 2 * (j + 1)
            faces.append([i0, i1, i2])
            faces.append([i0, i2, i3])
        return np.asarray(faces, dtype=np.int32)

    @staticmethod
    def _box_mesh(length: float, width: float, height: float) -> Tuple[np.ndarray, np.ndarray]:
        """Create a box mesh centered at origin."""
        lx = float(length) / 2.0
        wy = float(width) / 2.0
        hz = float(height) / 2.0
        v = np.array(
            [
                [-lx, -wy, -hz],
                [+lx, -wy, -hz],
                [+lx, +wy, -hz],
                [-lx, +wy, -hz],
                [-lx, -wy, +hz],
                [+lx, -wy, +hz],
                [+lx, +wy, +hz],
                [-lx, +wy, +hz],
            ],
            dtype=float,
        )
        f = np.array(
            [
                # bottom
                [0, 1, 2],
                [0, 2, 3],
                # top
                [4, 6, 5],
                [4, 7, 6],
                # front (+x)
                [1, 5, 6],
                [1, 6, 2],
                # back (-x)
                [0, 3, 7],
                [0, 7, 4],
                # left (+y)
                [3, 2, 6],
                [3, 6, 7],
                # right (-y)
                [0, 4, 5],
                [0, 5, 1],
            ],
            dtype=np.int32,
        )
        return v, f

    @staticmethod
    def _cylinder_mesh(radius: float, length: float, cols: int = 28) -> Tuple[np.ndarray, np.ndarray]:
        """Fallback cylinder mesh (axis along Z), used if MeshData.cylinder() is unavailable."""
        r = float(radius)
        L = float(length)
        n = int(max(6, cols))
        ang = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
        x = r * np.cos(ang)
        y = r * np.sin(ang)
        z0 = -0.5 * L
        z1 = +0.5 * L
        v0 = np.stack([x, y, np.full_like(x, z0)], axis=1)
        v1 = np.stack([x, y, np.full_like(x, z1)], axis=1)
        verts = np.vstack([v0, v1])

        faces = []
        for j in range(n):
            jn = (j + 1) % n
            a = j
            b = jn
            c = n + jn
            d = n + j
            faces.append([a, b, c])
            faces.append([a, c, d])
        return verts.astype(float), np.asarray(faces, dtype=np.int32)


    @staticmethod
    def _capped_cylinder_mesh(radius: float, length: float, cols: int = 28) -> Tuple[np.ndarray, np.ndarray]:
        """Closed cylinder mesh (axis along Z) with readable end caps.

        The generic MeshData.cylinder() output used by older releases visually behaved like
        an open tube in the actuator views, which is exactly why the user perceived an
        extra inner cylinder on one side of the piston.  This helper guarantees explicit
        end-cap faces for actuator housing/chamber/rod meshes.
        """
        r = float(radius)
        L = float(length)
        n = int(max(6, cols))
        ang = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
        x = r * np.cos(ang)
        y = r * np.sin(ang)
        z0 = -0.5 * L
        z1 = +0.5 * L
        ring0 = np.stack([x, y, np.full_like(x, z0)], axis=1)
        ring1 = np.stack([x, y, np.full_like(x, z1)], axis=1)
        c0 = np.array([[0.0, 0.0, z0]], dtype=float)
        c1 = np.array([[0.0, 0.0, z1]], dtype=float)
        verts = np.vstack([ring0, ring1, c0, c1])
        bot_center = 2 * n
        top_center = 2 * n + 1
        faces: list[list[int]] = []
        for j in range(n):
            jn = (j + 1) % n
            a = j
            b = jn
            c = n + jn
            d = n + j
            faces.append([a, b, c])
            faces.append([a, c, d])
            # bottom cap (two-sided for translucent actuators)
            faces.append([bot_center, b, a])
            faces.append([bot_center, a, b])
            # top cap
            faces.append([top_center, d, c])
            faces.append([top_center, c, d])
        return verts.astype(float), np.asarray(faces, dtype=np.int32)


    @staticmethod
    def _rotation_from_y_to_vec(vec_xyz: np.ndarray) -> np.ndarray:
        """Return rotation matrix that maps canonical +Y axis to ``vec_xyz``."""
        v = np.asarray(vec_xyz, dtype=float).reshape(3)
        n = float(np.linalg.norm(v))
        if not np.isfinite(n) or n <= 1e-12:
            return np.eye(3, dtype=float)
        dst = v / n
        src = np.array([0.0, 1.0, 0.0], dtype=float)
        c = float(np.dot(src, dst))
        if c >= 1.0 - 1e-12:
            return np.eye(3, dtype=float)
        if c <= -1.0 + 1e-12:
            return np.array([[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]], dtype=float)
        axis = np.cross(src, dst)
        s = float(np.linalg.norm(axis))
        if s <= 1e-12:
            return np.eye(3, dtype=float)
        ax = axis / s
        K = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]], dtype=float)
        return np.eye(3, dtype=float) + K * s + (K @ K) * (1.0 - c)

    def _segment_mesh_vertices(self, *, radius_m: float, p0_xyz: np.ndarray, p1_xyz: np.ndarray) -> Optional[np.ndarray]:
        if self._unit_cyl_y_vertices is None:
            return None
        p0 = np.asarray(p0_xyz, dtype=float).reshape(3)
        p1 = np.asarray(p1_xyz, dtype=float).reshape(3)
        seg = p1 - p0
        length = float(np.linalg.norm(seg))
        if not np.isfinite(length) or length <= 1e-9 or radius_m <= 0.0:
            return None
        base = np.asarray(self._unit_cyl_y_vertices, dtype=float)
        scaled = base * np.array([float(radius_m), float(length), float(radius_m)], dtype=float).reshape(1, 3)
        R = self._rotation_from_y_to_vec(seg)
        center = 0.5 * (p0 + p1)
        return (scaled @ R.T) + center.reshape(1, 3)

    def _disc_mesh_vertices(self, *, radius_m: float, center_xyz: np.ndarray, normal_xyz: np.ndarray) -> Optional[np.ndarray]:
        if getattr(self, '_unit_disc_y_vertices', None) is None:
            return None
        radius = float(radius_m)
        if not np.isfinite(radius) or radius <= 0.0:
            return None
        center = np.asarray(center_xyz, dtype=float).reshape(3)
        normal = np.asarray(normal_xyz, dtype=float).reshape(3)
        if not np.all(np.isfinite(center)) or not np.all(np.isfinite(normal)):
            return None
        base = np.asarray(self._unit_disc_y_vertices, dtype=float)
        scaled = base * np.array([radius, 1.0, radius], dtype=float).reshape(1, 3)
        R = self._rotation_from_y_to_vec(normal)
        return (scaled @ R.T) + center.reshape(1, 3)

    @staticmethod
    def _circle_line_vertices(*, radius_m: float, center_xyz: np.ndarray, normal_xyz: np.ndarray, segments: int = 40) -> Optional[np.ndarray]:
        radius = float(radius_m)
        if not np.isfinite(radius) or radius <= 0.0:
            return None
        center = np.asarray(center_xyz, dtype=float).reshape(3)
        normal = np.asarray(normal_xyz, dtype=float).reshape(3)
        n = float(np.linalg.norm(normal))
        if not np.isfinite(n) or n <= 1e-9 or not np.all(np.isfinite(center)):
            return None
        normal = normal / n
        ref = np.array([1.0, 0.0, 0.0], dtype=float) if abs(float(normal[0])) < 0.9 else np.array([0.0, 1.0, 0.0], dtype=float)
        u = np.cross(normal, ref)
        un = float(np.linalg.norm(u))
        if not np.isfinite(un) or un <= 1e-9:
            return None
        u = u / un
        v = np.cross(normal, u)
        ang = np.linspace(0.0, 2.0 * np.pi, int(max(12, segments)) + 1, endpoint=True)
        pts = center.reshape(1, 3) + radius * (np.cos(ang).reshape(-1, 1) * u.reshape(1, 3) + np.sin(ang).reshape(-1, 1) * v.reshape(1, 3))
        return np.asarray(pts, dtype=float)

    @staticmethod
    def _contact_marker_line_vertices(points_xyz: np.ndarray, size_m: float = 0.04) -> np.ndarray:
        pts = np.asarray(points_xyz, dtype=float).reshape(-1, 3)
        if pts.size == 0:
            return np.zeros((0, 3), dtype=float)
        segs: list[np.ndarray] = []
        d_xy = float(max(0.01, size_m))
        d_z = 0.65 * d_xy
        for p in pts:
            if not np.all(np.isfinite(p)):
                continue
            segs.extend([
                p + np.array([-d_xy, 0.0, 0.0], dtype=float),
                p + np.array([+d_xy, 0.0, 0.0], dtype=float),
                p + np.array([0.0, -d_xy, 0.0], dtype=float),
                p + np.array([0.0, +d_xy, 0.0], dtype=float),
                p + np.array([0.0, 0.0, -d_z], dtype=float),
                p + np.array([0.0, 0.0, +d_z], dtype=float),
            ])
        if not segs:
            return np.zeros((0, 3), dtype=float)
        return np.asarray(segs, dtype=float)

    def set_layout_transition_active(self, active: bool) -> None:
        active = bool(active)
        if active == bool(getattr(self, '_layout_transition_active', False)):
            return
        self._layout_transition_active = active
        if not _HAS_GL:
            return
        try:
            self.view.setUpdatesEnabled(not active)
        except Exception:
            pass
        # Do not hide/show the live GL widget during layout churn.  Hide/show was cheap
        # from the Qt side but it repeatedly invalidated the active GL program/shader
        # state on Windows and produced exactly the freezes/jitter reported by the user.
        # We only suspend repaints while the layout is unstable and then request a fresh
        # redraw once the dock settles.
        try:
            self._layout_pause_placeholder.setVisible(False)
        except Exception:
            pass
        try:
            vp = self.view.viewport()
            if vp is not None:
                vp.setUpdatesEnabled(not active)
        except Exception:
            pass
        if not active:
            try:
                self.view.update()
            except Exception:
                pass

    @staticmethod
    def _corner_is_front(corner: str) -> bool:
        return str(corner) in ("ЛП", "ПП")

    def _corner_cylinder_contract(self, *, cyl_index: int, corner: str) -> tuple[float, float, float, float, float, float, float, float]:
        front = self._corner_is_front(corner)
        if cyl_index == 1:
            bore = float(getattr(self.geom, 'cyl1_bore_diameter', 0.0))
            rod = float(getattr(self.geom, 'cyl1_rod_diameter', 0.0))
            outer = float(getattr(self.geom, 'cyl1_outer_diameter', 0.0))
            dead_cap = float(getattr(self.geom, 'cyl1_dead_cap_length', 0.0))
            dead_rod = float(getattr(self.geom, 'cyl1_dead_rod_length', 0.0))
            dead_height = float(getattr(self.geom, 'cyl1_dead_height', 0.0))
            body_len = float(getattr(self.geom, 'cyl1_body_length_front' if front else 'cyl1_body_length_rear', 0.0))
            stroke = float(getattr(self.geom, 'cyl1_stroke_front' if front else 'cyl1_stroke_rear', 0.0))
        else:
            bore = float(getattr(self.geom, 'cyl2_bore_diameter', 0.0))
            rod = float(getattr(self.geom, 'cyl2_rod_diameter', 0.0))
            outer = float(getattr(self.geom, 'cyl2_outer_diameter', 0.0))
            dead_cap = float(getattr(self.geom, 'cyl2_dead_cap_length', 0.0))
            dead_rod = float(getattr(self.geom, 'cyl2_dead_rod_length', 0.0))
            dead_height = float(getattr(self.geom, 'cyl2_dead_height', 0.0))
            body_len = float(getattr(self.geom, 'cyl2_body_length_front' if front else 'cyl2_body_length_rear', 0.0))
            stroke = float(getattr(self.geom, 'cyl2_stroke_front' if front else 'cyl2_stroke_rear', 0.0))
        return bore, rod, outer, stroke, dead_cap, dead_rod, dead_height, body_len

    @staticmethod
    def _column_for_cyl_stroke(cyl_index: int, corner: str) -> str:
        return f"положение_штока_{corner}_м" if int(cyl_index) == 1 else f"положение_штока_Ц2_{corner}_м"

    @staticmethod
    def _cylinder_name(cyl_index: int) -> str:
        return "cyl1" if int(cyl_index) == 1 else "cyl2"

    def _cylinder_truth_gate(self, cyl_index: int) -> Dict[str, Any]:
        gates = getattr(self, "_cylinder_truth_gates", {}) or {}
        key = self._cylinder_name(cyl_index)
        gate = gates.get(key)
        if isinstance(gate, dict):
            return dict(gate)
        return {
            "cyl_name": key,
            "enabled": False,
            "mode": "axis_only",
            "reason": "missing_truth_gate",
        }

    @staticmethod
    def _empty_meshdata() -> "gl.MeshData":
        return gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32))

    @staticmethod
    def _invalidate_mesh(item: Optional["gl.GLMeshItem"]) -> None:
        if item is None:
            return
        try:
            item.setMeshData(meshdata=gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32)))
            item.setVisible(False)
        except Exception:
            pass

    @staticmethod
    def _cylinder_visual_segments(*, top_xyz: np.ndarray, bot_xyz: np.ndarray, stroke_pos_m: float, stroke_len_m: float, bore_d_m: float, rod_d_m: float, dead_vol_m3: float) -> tuple[Optional[tuple[np.ndarray, np.ndarray]], Optional[tuple[np.ndarray, np.ndarray]], Optional[tuple[np.ndarray, np.ndarray]]]:
        return _cylinder_visual_segments_from_state(
            top_xyz=np.asarray(top_xyz, dtype=float),
            bot_xyz=np.asarray(bot_xyz, dtype=float),
            stroke_pos_m=float(stroke_pos_m),
            stroke_len_m=float(stroke_len_m),
            bore_d_m=float(bore_d_m),
            rod_d_m=float(rod_d_m),
            dead_vol_m3=float(dead_vol_m3),
        )

    @staticmethod
    def _clamp(x: float, a: float, b: float) -> float:
        return float(max(a, min(b, x)))

    def _auto_lookahead(self, vx_m_s: float) -> float:
        v = abs(float(vx_m_s))
        la = 25.0 + 2.5 * v
        return self._clamp(la, self._lookahead_min_m, self._lookahead_max_m)

    # ---------------------------- scene rebuild ----------------------------

    def _rebuild_scene_items(self) -> None:
        """(Re)create GL items that depend on geometry or feature set."""
        if not _HAS_GL:
            return

        # Remove old items (safe if None)
        for it in [self._road_mesh, self._road_edges, self._road_stripes,
                   self._chassis_mesh, self._contact_pts, self._contact_links,
                   self._arm_lines, self._cyl1_lines, self._cyl2_lines,
                   self._contact_patch_mesh, self._vec_vel, self._vec_acc,
                   self._cyl_piston_markers, self._cyl_frame_mount_markers,
                   *self._cyl_piston_ring_lines, *self._cyl_rod_core_lines]:
            if it is not None:
                try:
                    self.view.removeItem(it)
                except Exception:
                    pass
        for w in self._wheel_meshes:
            try:
                self.view.removeItem(w)
            except Exception:
                pass
        self._wheel_meshes = []
        for meshes in (self._cyl_body_meshes, self._cyl_chamber_meshes, self._cyl_rod_meshes, self._cyl_piston_meshes):
            for it in list(meshes):
                try:
                    self.view.removeItem(it)
                except Exception:
                    pass
            meshes.clear()
        self._cyl_piston_ring_lines = []
        self._cyl_rod_core_lines = []

        # --- Road: ribbon mesh + edges + stripes
        self._road_mesh = gl.GLMeshItem(
            meshdata=self._empty_meshdata(),
            smooth=True,
            drawEdges=False,
            color=(0.72, 0.74, 0.77, 0.98),
            shader="shaded",
        )
        self._road_mesh.setGLOptions("opaque")
        self._road_mesh.setVisible(False)
        self.view.addItem(self._road_mesh)

        self._road_edges = gl.GLLinePlotItem(
            pos=np.zeros((2, 3)),
            color=(0.12, 0.14, 0.16, 0.95),
            width=2.4,
            antialias=True,
            mode="line_strip",
        )
        self._road_edges.setVisible(False)
        self.view.addItem(self._road_edges)

        self._road_stripes = gl.GLLinePlotItem(
            pos=np.zeros((2, 3)),
            color=(0.05, 0.32, 0.58, 0.88),
            width=1.6,
            antialias=True,
            mode="lines",
        )
        self._road_stripes.setVisible(False)
        self.view.addItem(self._road_stripes)

        # --- Chassis: box mesh
        # IMPORTANT: use explicit frame geometry from meta.geometry only.
        # No hidden derivation from wheelbase/track/radius is allowed here.
        body_len = max(0.0, float(getattr(self.geom, "frame_length", 0.0)))
        body_w = max(0.0, float(getattr(self.geom, "frame_width", 0.0)))
        body_h = max(0.0, float(getattr(self.geom, "frame_height", 0.0)))

        self._box_base_vertices = None
        self._box_faces = None
        if body_len > 0.0 and body_w > 0.0 and body_h > 0.0:
            v_box, f_box = self._box_mesh(body_len, body_w, body_h)
            self._box_base_vertices = np.asarray(v_box, dtype=float)
            self._box_faces = np.asarray(f_box, dtype=np.int32)
            self._chassis_mesh = gl.GLMeshItem(
                meshdata=gl.MeshData(vertexes=self._box_base_vertices, faces=self._box_faces),
                smooth=False,
                drawEdges=True,
                edgeColor=(0.25, 0.25, 0.25, 1.0),
                color=(0.12, 0.36, 0.62, 0.85),
                shader="shaded",
            )
            self._chassis_mesh.setGLOptions("opaque")
            self.view.addItem(self._chassis_mesh)
        else:
            self._chassis_mesh = None

        # --- Wheels: cylinders (stored already centered and oriented along local +Y axle)
        wheel_r = float(self.geom.wheel_radius)
        wheel_w = float(self.geom.wheel_width)
        self._wheel_base_vertices = None
        self._wheel_faces = None
        if hasattr(gl.MeshData, "cylinder"):
            md_raw = gl.MeshData.cylinder(rows=12, cols=28, radius=[wheel_r, wheel_r], length=wheel_w)
            v_cyl = np.asarray(md_raw.vertexes(), dtype=float)
            f_cyl = np.asarray(md_raw.faces(), dtype=np.int32)
        else:
            v_cyl, f_cyl = self._cylinder_mesh(wheel_r, wheel_w, cols=28)
            v_cyl = np.asarray(v_cyl, dtype=float)
            f_cyl = np.asarray(f_cyl, dtype=np.int32)
        v_cyl = _center_and_orient_cylinder_vertices_to_y(v_cyl, length_m=float(wheel_w))
        self._wheel_base_vertices = np.asarray(v_cyl, dtype=float)
        self._wheel_faces = np.asarray(f_cyl, dtype=np.int32)
        # Unit +Y cylinder for dynamic actuator meshes (radius=1, length=1).
        # Use an explicit capped mesh instead of the generic helper so the actuator body
        # has readable side walls and end caps from every angle.
        v_unit, f_unit = self._capped_cylinder_mesh(1.0, 1.0, cols=24)
        v_unit = np.asarray(v_unit, dtype=float)
        f_unit = np.asarray(f_unit, dtype=np.int32)
        self._unit_cyl_y_vertices = np.asarray(_orient_centered_cylinder_vertices_to_y(v_unit), dtype=float)
        self._unit_cyl_faces = np.asarray(f_unit, dtype=np.int32)
        disc_seg = 24
        disc_ang = np.linspace(0.0, 2.0 * np.pi, disc_seg, endpoint=False)
        disc_ring = np.stack([np.cos(disc_ang), np.zeros_like(disc_ang), np.sin(disc_ang)], axis=1)
        self._unit_disc_y_vertices = np.vstack([np.zeros((1, 3), dtype=float), disc_ring]).astype(float)
        disc_faces: list[list[int]] = []
        for _j in range(disc_seg):
            _a = 1 + _j
            _b = 1 + ((_j + 1) % disc_seg)
            disc_faces.append([0, _a, _b])
            disc_faces.append([0, _b, _a])
        self._unit_disc_faces = np.asarray(disc_faces, dtype=np.int32)
        cyl_md = gl.MeshData(vertexes=self._wheel_base_vertices, faces=self._wheel_faces)

        for _ in range(4):
            w = gl.GLMeshItem(
                meshdata=cyl_md,
                smooth=False,
                drawEdges=True,
                edgeColor=(0.15, 0.15, 0.15, 1.0),
                color=(0.05, 0.05, 0.05, 1.0),
                shader="shaded",
            )
            w.setGLOptions("opaque")
            self.view.addItem(w)
            self._wheel_meshes.append(w)

        # --- Pneumatic cylinders: translucent housing + exact cap-side chamber + external rod
        # mesh + separate inner rod-core overlay + exact piston plane.
        # Honesty policy:
        # - housing shell uses explicit packaging length when the bundle exports it;
        # - the exact cap-side -> piston split is shown as a separate semi-transparent chamber;
        # - the opaque rod mesh represents only the exposed external rod, while a light line overlay
        #   keeps the internal rod readable through the translucent shell;
        # - piston is rendered from the contract-derived plane only, without fake thickness.
        cyl_body_md = gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32))
        for _ in range(8):
            body = gl.GLMeshItem(
                meshdata=cyl_body_md,
                smooth=False,
                drawFaces=True,
                drawEdges=True,
                edgeColor=(0.18, 0.62, 0.88, 0.26),
                color=(0.16, 0.52, 0.78, 0.10),
                shader="shaded",
            )
            body.setGLOptions("translucent")
            body.setVisible(False)
            self.view.addItem(body)
            self._cyl_body_meshes.append(body)

            chamber = gl.GLMeshItem(
                meshdata=cyl_body_md,
                smooth=False,
                drawEdges=False,
                edgeColor=(0.0, 0.0, 0.0, 0.0),
                color=(0.20, 0.74, 0.98, 0.08),
                shader="shaded",
            )
            chamber.setGLOptions("translucent")
            chamber.setVisible(False)
            self.view.addItem(chamber)
            self._cyl_chamber_meshes.append(chamber)

            rod = gl.GLMeshItem(
                meshdata=cyl_body_md,
                smooth=False,
                drawEdges=True,
                edgeColor=(0.78, 0.82, 0.88, 1.0),
                color=(0.90, 0.92, 0.96, 0.98),
                shader="shaded",
            )
            rod.setGLOptions("opaque")
            rod.setVisible(False)
            self.view.addItem(rod)
            self._cyl_rod_meshes.append(rod)

            piston = gl.GLMeshItem(
                meshdata=cyl_body_md,
                smooth=False,
                drawEdges=True,
                edgeColor=(1.00, 0.88, 0.18, 1.0),
                color=(1.00, 0.88, 0.22, 0.88),
                shader="shaded",
            )
            piston.setGLOptions("translucent")
            piston.setVisible(False)
            self.view.addItem(piston)
            self._cyl_piston_meshes.append(piston)

            piston_ring = gl.GLLinePlotItem(
                pos=np.zeros((0, 3), dtype=float),
                color=(1.00, 0.88, 0.18, 0.96),
                width=2.2,
                antialias=True,
                mode="line_strip",
            )
            piston_ring.setVisible(False)
            self.view.addItem(piston_ring)
            self._cyl_piston_ring_lines.append(piston_ring)

            rod_core = gl.GLLinePlotItem(
                pos=np.zeros((0, 3), dtype=float),
                color=(0.96, 0.98, 1.00, 0.92),
                width=2.6,
                antialias=True,
                mode="lines",
            )
            rod_core.setVisible(False)
            self.view.addItem(rod_core)
            self._cyl_rod_core_lines.append(rod_core)

        # No GL point sprites here: they caused Windows/OpenGL runtime warnings and were
        # easily mistaken for frame mounts or other packaging points.
        self._cyl_piston_markers = None
        self._cyl_frame_mount_markers = gl.GLLinePlotItem(
            pos=np.zeros((0, 3), dtype=float),
            color=(1.00, 0.56, 0.12, 0.98),
            width=2.0,
            antialias=True,
            mode="lines",
        )
        self._cyl_frame_mount_markers.setVisible(False)
        self.view.addItem(self._cyl_frame_mount_markers)

        # --- Contact markers and links
        # Use line-based cross markers instead of GL point sprites: the latter produced
        # `GL_POINT_SPRITE` invalid-op warnings on some Windows/OpenGL stacks and also
        # looked like mysterious floating balls in the scene.
        self._contact_pts = gl.GLLinePlotItem(
            pos=np.zeros((0, 3), dtype=float),
            color=(0.96, 0.96, 0.98, 0.92),
            width=1.6,
            antialias=True,
            mode="lines",
        )
        self._contact_pts.setVisible(False)
        self.view.addItem(self._contact_pts)

        self._contact_links = gl.GLLinePlotItem(
            pos=np.zeros((8, 3)),  # 4 segments => 8 points
            color=(0.9, 0.9, 0.9, 0.55),
            width=1.0,
            antialias=True,
            mode="lines",
        )
        self._contact_links.setVisible(False)
        self.view.addItem(self._contact_links)

        self._arm_lines = gl.GLLinePlotItem(
            pos=np.zeros((2, 3)),
            color=(0.82, 0.82, 0.86, 0.95),
            width=2.0,
            antialias=True,
            mode="lines",
        )
        self._arm_lines.setVisible(False)
        self.view.addItem(self._arm_lines)

        self._cyl1_lines = gl.GLLinePlotItem(
            pos=np.zeros((2, 3)),
            color=(0.30, 0.82, 0.98, 0.95),
            width=2.0,
            antialias=True,
            mode="lines",
        )
        self._cyl1_lines.setVisible(False)
        self.view.addItem(self._cyl1_lines)

        self._cyl2_lines = gl.GLLinePlotItem(
            pos=np.zeros((2, 3)),
            color=(0.98, 0.72, 0.28, 0.95),
            width=2.0,
            antialias=True,
            mode="lines",
        )
        self._cyl2_lines.setVisible(False)
        self.view.addItem(self._cyl2_lines)

        self._contact_patch_mesh = gl.GLMeshItem(
            meshdata=self._empty_meshdata(),
            smooth=True,
            drawEdges=True,
            edgeColor=(0.95, 0.85, 0.25, 0.95),
            color=(0.95, 0.85, 0.25, 0.35),
            shader="shaded",
        )
        self._contact_patch_mesh.setGLOptions("translucent")
        self._contact_patch_mesh.setVisible(False)
        self.view.addItem(self._contact_patch_mesh)

        # --- Vectors: velocity & acceleration (simple arrows)
        self._vec_vel = gl.GLLinePlotItem(
            pos=np.zeros((6, 3)),
            color=(0.2, 0.75, 0.35, 0.9),
            width=2.0,
            antialias=True,
            mode="lines",
        )
        self._vec_vel.setVisible(False)
        self.view.addItem(self._vec_vel)

        self._vec_acc = gl.GLLinePlotItem(
            pos=np.zeros((6, 3)),
            color=(0.95, 0.55, 0.15, 0.9),
            width=2.0,
            antialias=True,
            mode="lines",
        )
        self._vec_acc.setVisible(False)
        self.view.addItem(self._vec_acc)

        self.set_visual(**self._visual)

    # ---------------------------- public API ----------------------------

    def set_geometry(self, geom: ViewGeometry) -> None:
        self.geom = geom
        # Keep road ribbon width consistent with generator/meta.
        try:
            self._road_width_m = float(getattr(geom, "road_width", self._road_width_m))
        except Exception:
            pass
        if _HAS_GL:
            self._rebuild_scene_items()
            self.fit_camera_to_geometry()


    def set_bundle_context(self, bundle: Optional[DataBundle]) -> None:
        """Remember bundle-level context that must stay stable during playback.

        In particular, both the visible road wire-grid *and the dense shaded surface*
        must not derive their longitudinal spacing from the instantaneous playback
        window or from the current viewport size on every frame. Otherwise users see
        the road mesh/grid stretch, shrink and drift relative to the same relief.
        """
        self._road_grid_cross_spacing_m = None
        self._road_grid_cross_spacing_viewport_key = None
        self._road_surface_spacing_m = None
        self._road_surface_spacing_cache_key = None
        self._road_path_s_world_cache = None
        self._road_path_nx_world_cache = None
        self._road_path_ny_world_cache = None
        self._bundle_history_m = None
        self._bundle_lookahead_m = None
        try:
            self._cylinder_truth_gates = _evaluate_all_cylinder_truth_gates(getattr(bundle, "meta", None) if bundle is not None else None)
            for _gate in self._cylinder_truth_gates.values():
                if not bool(dict(_gate).get("enabled")):
                    _emit_animator_warning(
                        f"[Animator] {_render_cylinder_truth_gate_message(_gate)}",
                        code=f"{dict(_gate).get('cyl_name') or 'cyl'}_axis_only_honesty_mode",
                        truth_gate=dict(_gate),
                    )
        except Exception:
            self._cylinder_truth_gates = _evaluate_all_cylinder_truth_gates(None)
        try:
            if bundle is None:
                raise ValueError('missing bundle')
            vx = np.asarray(bundle.get("скорость_vx_м_с", 0.0), dtype=float).reshape(-1)
            finite_v = np.asarray(np.abs(vx[np.isfinite(vx)]), dtype=float)
            if finite_v.size > 0:
                v_ref = float(np.nanmedian(finite_v))
                v_max = float(np.nanmax(finite_v))
            else:
                meta = dict(getattr(bundle, "meta", {}) or {})
                v_ref = float(meta.get("ring_nominal_speed_mean_mps") or meta.get("vx0_м_с") or 0.0)
                v_max = float(meta.get("ring_nominal_speed_max_mps") or v_ref)
        except Exception:
            v_ref = 0.0
            v_max = 0.0
        self._road_grid_nominal_visible_len_m = float(max(5.0, self._lookbehind_m + self._auto_lookahead(v_ref)))
        self._road_grid_max_visible_len_m = float(max(self._road_grid_nominal_visible_len_m, self._lookbehind_m + self._auto_lookahead(v_max)))
        self._bundle_history_m = float(max(0.0, self._lookbehind_m))
        self._bundle_lookahead_m = float(
            max(0.0, self._road_grid_nominal_visible_len_m - float(self._bundle_history_m))
        )
        native_step = None
        try:
            if bundle is not None:
                wb = float(getattr(self.geom, "wheelbase", 1.5))
                s_c, _z_c = bundle.ensure_road_profile(wheelbase_m=wb, mode="center")
                ds = np.diff(np.asarray(s_c, dtype=float).reshape(-1))
                ds = ds[np.isfinite(ds) & (ds > 1e-9)]
                if ds.size > 0:
                    native_step = float(np.nanmedian(ds))
        except Exception:
            native_step = None
        if native_step is None:
            try:
                if bundle is not None:
                    s_world = np.asarray(bundle.ensure_s_world(), dtype=float).reshape(-1)
                    ds = np.diff(s_world)
                    ds = ds[np.isfinite(ds) & (ds > 1e-9)]
                    if ds.size > 0:
                        native_step = float(np.nanmedian(ds))
            except Exception:
                native_step = None
        if native_step is None or not np.isfinite(float(native_step)):
            native_step = 0.06
        self._road_native_long_step_m = float(max(0.005, float(native_step)))

        # Cache world-anchored path normals once per bundle. The visible road mesh must
        # not re-estimate its lateral normal from the current viewport slice because that
        # makes the same road relief depend on window size / visible range.
        try:
            if bundle is None:
                raise ValueError('missing bundle')
            s_path = np.asarray(bundle.ensure_s_world(), dtype=float).reshape(-1)
            x_path = np.asarray(bundle.get("путь_x_м", 0.0), dtype=float).reshape(-1)
            y_path = np.asarray(bundle.get("путь_y_м", 0.0), dtype=float).reshape(-1)
            mask = np.isfinite(s_path) & np.isfinite(x_path) & np.isfinite(y_path)
            if int(np.count_nonzero(mask)) < 2:
                raise ValueError('insufficient finite path samples')
            s_path = np.asarray(s_path[mask], dtype=float)
            x_path = np.asarray(x_path[mask], dtype=float)
            y_path = np.asarray(y_path[mask], dtype=float)
            order = np.argsort(s_path, kind="mergesort")
            s_path = s_path[order]
            x_path = x_path[order]
            y_path = y_path[order]
            keep = np.ones_like(s_path, dtype=bool)
            keep[1:] = np.diff(s_path) > 1e-9
            s_path = s_path[keep]
            x_path = x_path[keep]
            y_path = y_path[keep]
            if s_path.size >= 2:
                dx_ds = np.gradient(x_path, s_path)
                dy_ds = np.gradient(y_path, s_path)
                norm = np.sqrt(dx_ds * dx_ds + dy_ds * dy_ds)
                good = np.isfinite(norm) & (norm > 1e-9)
                if int(np.count_nonzero(good)) >= 2:
                    tx = np.zeros_like(dx_ds, dtype=float)
                    ty = np.zeros_like(dy_ds, dtype=float)
                    tx[good] = dx_ds[good] / norm[good]
                    ty[good] = dy_ds[good] / norm[good]
                    if int(np.count_nonzero(~good)) > 0:
                        idx = np.flatnonzero(good)
                        tx[~good] = np.interp(s_path[~good], s_path[idx], tx[idx])
                        ty[~good] = np.interp(s_path[~good], s_path[idx], ty[idx])
                    nx_world = -ty
                    ny_world = tx
                    n_norm = np.sqrt(nx_world * nx_world + ny_world * ny_world)
                    valid_n = np.isfinite(n_norm) & (n_norm > 1e-9)
                    if int(np.count_nonzero(valid_n)) >= 2:
                        nx_world[valid_n] /= n_norm[valid_n]
                        ny_world[valid_n] /= n_norm[valid_n]
                        self._road_path_s_world_cache = np.asarray(s_path, dtype=float)
                        self._road_path_nx_world_cache = np.asarray(nx_world, dtype=float)
                        self._road_path_ny_world_cache = np.asarray(ny_world, dtype=float)
        except Exception:
            self._road_path_s_world_cache = None
            self._road_path_nx_world_cache = None
            self._road_path_ny_world_cache = None

    def _stable_road_grid_cross_spacing(self, *, viewport_width_px: int, ds_long_m: float) -> float:
        del viewport_width_px
        # Cross-bars must keep a world-stable spacing for the whole bundle. They may
        # differ by perf tier, but never by the current window size.
        cache_key = (
            int(bool(self._playback_active)),
            int(bool(self._playback_perf_mode)),
        )
        cached = float(self._road_grid_cross_spacing_m) if self._road_grid_cross_spacing_m is not None else None
        if cached is None or self._road_grid_cross_spacing_viewport_key != cache_key:
            if bool(self._playback_active) and bool(self._playback_perf_mode):
                target_cross = 52
            elif bool(self._playback_active):
                target_cross = 64
            else:
                target_cross = 72
            nominal = float(max(self._road_grid_nominal_visible_len_m, self._road_grid_max_visible_len_m))
            cached = float(_stable_road_grid_cross_spacing_from_view(
                nominal_visible_length_m=float(nominal),
                viewport_width_px=1280,
                min_spacing_m=0.25,
                max_spacing_m=4.0,
                quant_step_m=0.05,
            ))
            # Re-quantise by target_cross so spacing stays tied to bundle scale, not viewport.
            cached = float(max(0.25, round((nominal / float(max(1, target_cross))) / 0.05) * 0.05))
            self._road_grid_cross_spacing_m = float(cached)
            self._road_grid_cross_spacing_viewport_key = cache_key
        return float(max(float(max(1e-6, ds_long_m)), float(cached)))

    def _stable_road_surface_spacing(self, *, viewport_width_px: int, min_long: int, max_long: int) -> float:
        del viewport_width_px
        cache_key = (
            int(max(2, min_long)),
            int(max(int(max(2, min_long)), max_long)),
        )
        cached = float(self._road_surface_spacing_m) if self._road_surface_spacing_m is not None else None
        if cached is None or self._road_surface_spacing_cache_key != cache_key:
            lo = int(max(2, min_long))
            hi = int(max(lo, max_long))
            native_step = float(max(1e-6, getattr(self, "_road_native_long_step_m", 0.06)))
            # Keep spacing bundle-stable and integer-multiple of the native sampled road step.
            # This removes viewport-size dependence and prevents the dense surface from sliding
            # over the same relief when the 3D window is resized.
            max_visible_len = float(max(self._road_grid_nominal_visible_len_m, self._road_grid_max_visible_len_m))
            max_native_rows = int(max(2, math.floor(max_visible_len / native_step) + 1))
            allowed_rows = int(max(lo, min(hi, max_native_rows)))
            stride = int(max(1, math.ceil(max_visible_len / (float(max(1, allowed_rows - 1)) * native_step))))
            cached = float(max(1e-6, native_step * float(stride)))
            self._road_surface_spacing_m = float(cached)
            self._road_surface_spacing_cache_key = cache_key
        return float(max(1e-6, cached))

    def _stable_road_preview_history_m(self) -> float:
        cached = self._bundle_history_m
        if cached is None or not np.isfinite(float(cached)):
            cached = float(self._lookbehind_m)
        return float(max(0.0, float(cached)))

    def _stable_road_preview_lookahead_m(self) -> float:
        hist = self._stable_road_preview_history_m()
        nominal = float(max(0.0, self._road_grid_nominal_visible_len_m - hist))
        cached = self._bundle_lookahead_m
        if cached is None or not np.isfinite(float(cached)):
            cached = nominal
        max_visible = float(max(self._road_grid_nominal_visible_len_m, self._road_grid_max_visible_len_m))
        max_lookahead = float(max(0.0, max_visible - hist))
        return float(max(0.0, min(max_lookahead, max(float(cached), nominal))))

    def fit_camera_to_geometry(self) -> None:
        if not _HAS_GL:
            return
        span = max(
            3.0 * float(max(0.05, self.geom.wheel_radius)),
            1.35 * float(max(0.5, self.geom.wheelbase)),
            1.45 * float(max(0.5, self.geom.track)),
            0.75 * float(max(0.5, self.geom.road_width)),
            2.0 * float(max(0.15, self.geom.frame_height)),
        )
        try:
            self.view.opts["distance"] = float(max(4.0, 2.8 * span))
            self.view.opts["elevation"] = 18.0
            self.view.opts["azimuth"] = -55.0
            try:
                self.view.opts["center"] = pg.Vector(0.0, 0.0, 0.2 * float(max(0.1, self.geom.frame_height)))
            except Exception:
                pass
            self.view.update()
        except Exception:
            pass

    def set_visual(self, show_road: Optional[bool] = None, show_vectors: Optional[bool] = None) -> None:
        if show_road is not None:
            self._visual["show_road"] = bool(show_road)
        if show_vectors is not None:
            self._visual["show_vectors"] = bool(show_vectors)

        if not _HAS_GL:
            return

        show_road = bool(self._visual.get("show_road", True))
        show_vectors = bool(self._visual.get("show_vectors", True))

        # Do not force empty startup road meshes visible here. The per-frame update
        # decides when road geometry is valid enough to show. set_visual only hides them
        # when the user disables road rendering globally.
        if self._road_mesh and not show_road:
            self._road_mesh.setVisible(False)
        if self._road_edges and not show_road:
            self._road_edges.setVisible(False)
        if self._road_stripes and not show_road:
            self._road_stripes.setVisible(False)

        if self._contact_pts:
            self._contact_pts.setVisible(True)  # always useful
        if self._contact_links:
            self._contact_links.setVisible(True)
        if self._arm_lines:
            self._arm_lines.setVisible(True)
        if self._cyl1_lines:
            self._cyl1_lines.setVisible(True)
        if self._cyl2_lines:
            self._cyl2_lines.setVisible(True)
        if self._contact_patch_mesh and not show_road:
            self._contact_patch_mesh.setVisible(False)
        # Packaging meshes are shown by the per-frame update only when they carry real
        # geometry. Never force empty startup meshes visible here: that caused black
        # startup scenes and OpenGL warnings before the first valid frame arrived.
        for meshes in (self._cyl_body_meshes, self._cyl_chamber_meshes, self._cyl_rod_meshes, self._cyl_piston_meshes):
            for it in meshes:
                try:
                    it.setVisible(bool(it.isVisible()))
                except Exception:
                    pass
        for it in self._cyl_piston_ring_lines:
            try:
                it.setVisible(bool(it.isVisible()))
            except Exception:
                pass
        for it in self._cyl_rod_core_lines:
            try:
                it.setVisible(bool(it.isVisible()))
            except Exception:
                pass
        if self._cyl_piston_markers:
            self._cyl_piston_markers.setVisible(bool(getattr(self, "_show_piston_markers_debug", False)))

        if self._vec_vel:
            self._vec_vel.setVisible(show_vectors)
        if self._vec_acc:
            self._vec_acc.setVisible(show_vectors)

    def set_playback_state(self, playing: bool) -> None:
        self._playback_active = bool(playing)

    def set_playback_perf_mode(self, enabled: bool) -> None:
        self._playback_perf_mode = bool(enabled)

    def set_scales(self, vel_scale: Optional[float] = None, accel_scale: Optional[float] = None) -> None:
        if vel_scale is not None:
            self._vel_scale = float(vel_scale)
        if accel_scale is not None:
            self._accel_scale = float(accel_scale)

    def _solver_signed_speed_along_road(self, get_value) -> float:
        try:
            return float(get_value("скорость_vx_м_с", 0.0))
        except Exception:
            return 0.0

    def _solver_external_acceleration_xy(self, get_value) -> tuple[float, float]:
        try:
            return (
                float(get_value("ускорение_продольное_ax_м_с2", 0.0)),
                float(get_value("ускорение_поперечное_ay_м_с2", 0.0)),
            )
        except Exception:
            return 0.0, 0.0

    # ---------------------------- main update ----------------------------

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None) -> None:
        if not _HAS_GL:
            return
        if bool(getattr(self, '_layout_transition_active', False)):
            return

        i0, i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )

        # ---- Data (with safe fallbacks)
        # DataBundle.get(...) -> np.ndarray; sample continuously between source rows so
        # sparse bundles still look smooth at high display cadence.
        def _g(name: str, default: float = 0.0) -> float:
            return _sample_series_local(b.get(name, default), i0=i0, i1=i1, alpha=alpha, default=default)

        # Canonical solver-truth channels only. The user-facing 3D arrows intentionally stay
        # in the road plane and do not mix in heave channels or reconstructed body helpers.
        speed_along_road = self._solver_signed_speed_along_road(_g)
        external_ax, external_ay = self._solver_external_acceleration_xy(_g)

        yaw0 = _g("yaw_рад", 0.0)

        roll = _g("крен_phi_рад", 0.0)
        pitch = _g("тангаж_theta_рад", 0.0)
        z_body = _g("перемещение_рамы_z_м", 0.0)

        # ---- Wheel & road heights (per-corner)
        corners = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
        z_wheels = [_g(f"перемещение_колеса_{c}_м", 0.0) for c in corners]
        z_roads = [
            _sample_series_local(arr, i0=i0, i1=i1, alpha=alpha, default=float("nan"))
            if (arr := b.road_series(c)) is not None else float("nan")
            for c in corners
        ]
        wheel_air = [_g(f"колесо_в_воздухе_{c}", 0.0) for c in corners]

        # ---- Canonical local car-frame coordinates (no axis remapping)
        x0 = _g("путь_x_м", 0.0)
        y0 = _g("путь_y_м", 0.0)

        wb = float(self.geom.wheelbase)
        tr = float(self.geom.track)
        xr = 0.5 * wb
        yl = 0.5 * tr
        wheel_xy_fallback = [
            (+xr, +yl),  # ЛП
            (+xr, -yl),  # ПП
            (-xr, +yl),  # ЛЗ
            (-xr, -yl),  # ПЗ
        ]

        wheel_local_pts: list[np.ndarray] = []
        road_local_pts: list[np.ndarray] = []
        frame_local_pts: list[np.ndarray] = []
        arm_pivot_local_pts: list[Optional[np.ndarray]] = []
        arm_joint_local_pts: list[Optional[np.ndarray]] = []
        arm2_pivot_local_pts: list[Optional[np.ndarray]] = []
        arm2_joint_local_pts: list[Optional[np.ndarray]] = []
        lower_frame_front_local_pts: list[Optional[np.ndarray]] = []
        lower_frame_rear_local_pts: list[Optional[np.ndarray]] = []
        lower_hub_front_local_pts: list[Optional[np.ndarray]] = []
        lower_hub_rear_local_pts: list[Optional[np.ndarray]] = []
        upper_frame_front_local_pts: list[Optional[np.ndarray]] = []
        upper_frame_rear_local_pts: list[Optional[np.ndarray]] = []
        upper_hub_front_local_pts: list[Optional[np.ndarray]] = []
        upper_hub_rear_local_pts: list[Optional[np.ndarray]] = []
        cyl1_top_local_pts: list[Optional[np.ndarray]] = []
        cyl1_bot_local_pts: list[Optional[np.ndarray]] = []
        cyl2_top_local_pts: list[Optional[np.ndarray]] = []
        cyl2_bot_local_pts: list[Optional[np.ndarray]] = []

        def _solver_local_point(kind: str, corner: str) -> Optional[np.ndarray]:
            arr = b.point_xyz(kind, corner)
            if arr is None:
                return None
            try:
                sample = _sample_point_local(arr, i0=i0, i1=i1, alpha=alpha)
                if sample is None:
                    return None
                return np.asarray(
                    _localize_world_points_to_car_frame(sample, x0=x0, y0=y0, yaw_rad=yaw0)[0],
                    dtype=float,
                )
            except Exception:
                return None

        for idx, corner in enumerate(corners):
            wpt = b.wheel_center_xyz(corner)
            rpt = b.road_contact_xyz(corner)
            fpt = b.frame_corner_xyz(corner)

            if wpt is not None:
                wpt_sample = _sample_point_local(wpt, i0=i0, i1=i1, alpha=alpha)
                if wpt_sample is not None:
                    wloc = _localize_world_points_to_car_frame(wpt_sample, x0=x0, y0=y0, yaw_rad=yaw0)[0]
                else:
                    fx, fy = wheel_xy_fallback[idx]
                    wloc = np.asarray([fx, fy, z_wheels[idx]], dtype=float)
            else:
                fx, fy = wheel_xy_fallback[idx]
                wloc = np.asarray([fx, fy, z_wheels[idx]], dtype=float)
            if rpt is not None:
                rpt_sample = _sample_point_local(rpt, i0=i0, i1=i1, alpha=alpha)
                if rpt_sample is not None:
                    rloc = _localize_world_points_to_car_frame(rpt_sample, x0=x0, y0=y0, yaw_rad=yaw0)[0]
                else:
                    zr = z_roads[idx]
                    if not np.isfinite(zr):
                        zr = float(wloc[2]) - float(self.geom.wheel_radius)
                    rloc = np.asarray([wloc[0], wloc[1], zr], dtype=float)
            else:
                zr = z_roads[idx]
                if not np.isfinite(zr):
                    zr = float(wloc[2]) - float(self.geom.wheel_radius)
                rloc = np.asarray([wloc[0], wloc[1], zr], dtype=float)
            if fpt is not None:
                fpt_sample = _sample_point_local(fpt, i0=i0, i1=i1, alpha=alpha)
                if fpt_sample is not None:
                    floc = _localize_world_points_to_car_frame(fpt_sample, x0=x0, y0=y0, yaw_rad=yaw0)[0]
                else:
                    floc = np.asarray([wloc[0], wloc[1], z_body], dtype=float)
            else:
                floc = np.asarray([wloc[0], wloc[1], z_body], dtype=float)

            wheel_local_pts.append(np.asarray(wloc, dtype=float))
            road_local_pts.append(np.asarray(rloc, dtype=float))
            frame_local_pts.append(np.asarray(floc, dtype=float))
            arm_pivot_local_pts.append(_solver_local_point("arm_pivot", corner))
            arm_joint_local_pts.append(_solver_local_point("arm_joint", corner))
            arm2_pivot_local_pts.append(_solver_local_point("arm2_pivot", corner))
            arm2_joint_local_pts.append(_solver_local_point("arm2_joint", corner))
            lower_frame_front_local_pts.append(_solver_local_point("lower_arm_frame_front", corner))
            lower_frame_rear_local_pts.append(_solver_local_point("lower_arm_frame_rear", corner))
            lower_hub_front_local_pts.append(_solver_local_point("lower_arm_hub_front", corner))
            lower_hub_rear_local_pts.append(_solver_local_point("lower_arm_hub_rear", corner))
            upper_frame_front_local_pts.append(_solver_local_point("upper_arm_frame_front", corner))
            upper_frame_rear_local_pts.append(_solver_local_point("upper_arm_frame_rear", corner))
            upper_hub_front_local_pts.append(_solver_local_point("upper_arm_hub_front", corner))
            upper_hub_rear_local_pts.append(_solver_local_point("upper_arm_hub_rear", corner))
            cyl1_top_local_pts.append(_solver_local_point("cyl1_top", corner))
            cyl1_bot_local_pts.append(_solver_local_point("cyl1_bot", corner))
            cyl2_top_local_pts.append(_solver_local_point("cyl2_top", corner))
            cyl2_bot_local_pts.append(_solver_local_point("cyl2_bot", corner))

        def _norm_or(vec_xyz: np.ndarray, fallback_xyz: np.ndarray) -> np.ndarray:
            v = np.asarray(vec_xyz, dtype=float).reshape(3)
            n = float(np.linalg.norm(v))
            if np.isfinite(n) and n > 1e-12:
                return v / n
            fb = np.asarray(fallback_xyz, dtype=float).reshape(3)
            fn = float(np.linalg.norm(fb))
            if np.isfinite(fn) and fn > 1e-12:
                return fb / fn
            return np.array([0.0, 0.0, 1.0], dtype=float)

        wheel_pose_centers: list[np.ndarray] = []
        wheel_pose_axles: list[np.ndarray] = []
        wheel_pose_fwds: list[np.ndarray] = []
        wheel_pose_ups: list[np.ndarray] = []
        wheel_pose_toe: list[float] = []
        wheel_pose_camber: list[float] = []
        for idx, corner in enumerate(corners):
            c_xyz, axle_xyz, fwd_xyz, up_xyz, toe_rad, camber_rad = _derive_wheel_pose_from_hardpoints(
                fallback_center_xyz=np.asarray(wheel_local_pts[idx], dtype=float),
                lower_front_xyz=lower_hub_front_local_pts[idx],
                lower_rear_xyz=lower_hub_rear_local_pts[idx],
                upper_front_xyz=upper_hub_front_local_pts[idx],
                upper_rear_xyz=upper_hub_rear_local_pts[idx],
            )
            # ABSOLUTE LAW: if the solver exported an explicit road_contact_{x,y,z},
            # keep it as-is. We only fall back to wheel-center XY when the contact
            # point itself is missing.
            wheel_pose_centers.append(np.asarray(c_xyz, dtype=float))
            wheel_pose_axles.append(_norm_or(axle_xyz, np.array([0.0, 1.0 if c_xyz[1] >= 0.0 else -1.0, 0.0], dtype=float)))
            wheel_pose_fwds.append(_norm_or(fwd_xyz, np.array([1.0, 0.0, 0.0], dtype=float)))
            wheel_pose_ups.append(_norm_or(up_xyz, np.array([0.0, 0.0, 1.0], dtype=float)))
            wheel_pose_toe.append(float(toe_rad))
            wheel_pose_camber.append(float(camber_rad))

        # ---- Place chassis (box)
        body_h = max(0.0, float(getattr(self.geom, "frame_height", 0.0)))
        center_draw = np.asarray([0.0, 0.0, z_body], dtype=float)
        R_local = np.eye(3, dtype=float)
        if self._chassis_mesh and self._box_base_vertices is not None and self._box_faces is not None:
            try:
                center_local, R_local = _orthonormal_frame_from_corners(
                    frame_local_pts[0], frame_local_pts[1], frame_local_pts[2], frame_local_pts[3]
                )
                center_draw = _lifted_box_center_from_lower_corners(center_local, R_local, height_m=body_h)
                v_box = (np.asarray(self._box_base_vertices, dtype=float) @ np.asarray(R_local, dtype=float).T) + center_draw
            except Exception:
                # Fallback for incomplete bundles: keep canonical axes and only use roll/pitch/heave.
                cr, sr = math.cos(float(roll)), math.sin(float(roll))
                cp, sp = math.cos(float(pitch)), math.sin(float(pitch))
                Rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=float)
                Ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=float)
                R_local = Rx @ Ry
                center_draw = np.asarray([0.0, 0.0, z_body], dtype=float)
                v_box = (np.asarray(self._box_base_vertices, dtype=float) @ R_local.T) + center_draw
            self._chassis_mesh.setMeshData(meshdata=gl.MeshData(vertexes=v_box, faces=self._box_faces))

        # ---- Place wheels using wheel pose derived from explicit hardpoints
        if self._wheel_base_vertices is not None and self._wheel_faces is not None:
            base_wheel = np.asarray(self._wheel_base_vertices, dtype=float)
            for idx, w in enumerate(self._wheel_meshes):
                center = np.asarray(wheel_pose_centers[idx], dtype=float)
                axle = np.asarray(wheel_pose_axles[idx], dtype=float)
                rot = self._rotation_from_y_to_vec(axle)
                v_wheel = (base_wheel @ np.asarray(rot, dtype=float).T) + center.reshape(1, 3)
                w.setMeshData(meshdata=gl.MeshData(vertexes=v_wheel, faces=self._wheel_faces))

        # ---- Contact points and links (mesh-derived patch is updated later together with road grid)
        if self._contact_pts and self._contact_links:
            pts = []
            cols = []
            links = []
            wheel_r = float(self.geom.wheel_radius)
            for idx, corner in enumerate(corners):
                wloc = np.asarray(wheel_pose_centers[idx], dtype=float)
                rloc = np.asarray(road_local_pts[idx], dtype=float)
                zc = float(wloc[2]) - wheel_r
                zr = float(rloc[2])
                pts.append([float(rloc[0]), float(rloc[1]), zr])
                in_air = bool(wheel_air[idx] > 0.5)
                cols.append([1.0, 0.35, 0.2, 1.0] if in_air else [0.2, 0.9, 0.35, 1.0])
                links.append([float(rloc[0]), float(rloc[1]), zr])
                links.append([float(wloc[0]), float(wloc[1]), zc])
            self._contact_pts.setData(pos=self._contact_marker_line_vertices(np.asarray(pts, dtype=float), size_m=max(0.02, 0.18 * wheel_r)))
            self._contact_links.setData(pos=np.asarray(links, float))
            if self._contact_patch_mesh is not None:
                self._contact_patch_mesh.setMeshData(
                    meshdata=gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32))
                )
                self._contact_patch_mesh.setVisible(False)

        # ---- Solver-point suspension primitives (honest lines, no invented body geometry)
        def _segments_from_pairs(a_list: list[Optional[np.ndarray]], b_list: list[Optional[np.ndarray]]) -> np.ndarray:
            pts: list[list[float]] = []
            for pa, pb in zip(a_list, b_list):
                if pa is None or pb is None:
                    continue
                pts.append(np.asarray(pa, dtype=float).tolist())
                pts.append(np.asarray(pb, dtype=float).tolist())
            if not pts:
                return np.zeros((0, 3), dtype=float)
            return np.asarray(pts, dtype=float)

        def _segments_from_quads(
            frame_front: list[Optional[np.ndarray]],
            frame_rear: list[Optional[np.ndarray]],
            hub_front: list[Optional[np.ndarray]],
            hub_rear: list[Optional[np.ndarray]],
        ) -> np.ndarray:
            pts: list[list[float]] = []
            for ff, fr, hf, hr in zip(frame_front, frame_rear, hub_front, hub_rear):
                if ff is None or fr is None or hf is None or hr is None:
                    continue
                ff = np.asarray(ff, dtype=float)
                fr = np.asarray(fr, dtype=float)
                hf = np.asarray(hf, dtype=float)
                hr = np.asarray(hr, dtype=float)
                pts.extend([ff.tolist(), fr.tolist(), hf.tolist(), hr.tolist(), ff.tolist(), hf.tolist(), fr.tolist(), hr.tolist()])
            if not pts:
                return np.zeros((0, 3), dtype=float)
            return np.asarray(pts, dtype=float)

        if self._arm_lines is not None:
            pos_lower_quad = _segments_from_quads(lower_frame_front_local_pts, lower_frame_rear_local_pts, lower_hub_front_local_pts, lower_hub_rear_local_pts)
            pos_upper_quad = _segments_from_quads(upper_frame_front_local_pts, upper_frame_rear_local_pts, upper_hub_front_local_pts, upper_hub_rear_local_pts)
            pos_lower = pos_lower_quad if pos_lower_quad.size else _segments_from_pairs(arm_pivot_local_pts, arm_joint_local_pts)
            pos_upper = pos_upper_quad if pos_upper_quad.size else _segments_from_pairs(arm2_pivot_local_pts, arm2_joint_local_pts)
            pos = pos_lower if pos_upper.size == 0 else (pos_upper if pos_lower.size == 0 else np.vstack([pos_lower, pos_upper]))
            self._arm_lines.setData(pos=pos)
            self._arm_lines.setVisible(bool(pos.shape[0] >= 2))
        if self._cyl1_lines is not None:
            pos = _segments_from_pairs(cyl1_top_local_pts, cyl1_bot_local_pts)
            self._cyl1_lines.setData(pos=pos)
            self._cyl1_lines.setVisible(bool(pos.shape[0] >= 2))
        if self._cyl2_lines is not None:
            pos = _segments_from_pairs(cyl2_top_local_pts, cyl2_bot_local_pts)
            self._cyl2_lines.setData(pos=pos)
            self._cyl2_lines.setVisible(bool(pos.shape[0] >= 2))

        def _set_mesh_from_segment(item: Optional["gl.GLMeshItem"], seg: Optional[tuple[np.ndarray, np.ndarray]], radius_m: float) -> None:
            if item is None or self._unit_cyl_faces is None:
                return
            if seg is None or radius_m <= 0.0:
                self._invalidate_mesh(item)
                return
            verts = self._segment_mesh_vertices(radius_m=float(radius_m), p0_xyz=np.asarray(seg[0], dtype=float), p1_xyz=np.asarray(seg[1], dtype=float))
            if verts is None:
                self._invalidate_mesh(item)
                return
            try:
                item.setMeshData(meshdata=gl.MeshData(vertexes=np.asarray(verts, dtype=float), faces=np.asarray(self._unit_cyl_faces, dtype=np.int32)))
                item.setVisible(True)
            except Exception:
                self._invalidate_mesh(item)

        def _set_disc_mesh(item: Optional["gl.GLMeshItem"], center_xyz: Optional[np.ndarray], normal_xyz: Optional[np.ndarray], radius_m: float) -> None:
            if item is None or getattr(self, '_unit_disc_faces', None) is None:
                return
            if center_xyz is None or normal_xyz is None or radius_m <= 0.0:
                self._invalidate_mesh(item)
                return
            verts = self._disc_mesh_vertices(radius_m=float(radius_m), center_xyz=np.asarray(center_xyz, dtype=float), normal_xyz=np.asarray(normal_xyz, dtype=float))
            if verts is None:
                self._invalidate_mesh(item)
                return
            try:
                item.setMeshData(meshdata=gl.MeshData(vertexes=np.asarray(verts, dtype=float), faces=np.asarray(self._unit_disc_faces, dtype=np.int32)))
                item.setVisible(True)
            except Exception:
                self._invalidate_mesh(item)

        def _set_line_item_pos(item: Optional["gl.GLLinePlotItem"], pos_xyz: Optional[np.ndarray]) -> None:
            if item is None:
                return
            if pos_xyz is None:
                try:
                    item.setData(pos=np.zeros((0, 3), dtype=float))
                    item.setVisible(False)
                except Exception:
                    pass
                return
            pos = np.asarray(pos_xyz, dtype=float).reshape(-1, 3)
            if pos.shape[0] < 2 or not np.all(np.isfinite(pos)):
                try:
                    item.setData(pos=np.zeros((0, 3), dtype=float))
                    item.setVisible(False)
                except Exception:
                    pass
                return
            try:
                item.setData(pos=pos)
                item.setVisible(True)
            except Exception:
                try:
                    item.setData(pos=np.zeros((0, 3), dtype=float))
                    item.setVisible(False)
                except Exception:
                    pass

        cyl_mesh_idx = 0
        for idx, corner in enumerate(corners):
            for cyl_index, top_list, bot_list in ((1, cyl1_top_local_pts, cyl1_bot_local_pts), (2, cyl2_top_local_pts, cyl2_bot_local_pts)):
                top_pt = top_list[idx]
                bot_pt = bot_list[idx]
                if top_pt is None or bot_pt is None:
                    if cyl_mesh_idx < len(self._cyl_body_meshes):
                        self._invalidate_mesh(self._cyl_body_meshes[cyl_mesh_idx])
                        if cyl_mesh_idx < len(self._cyl_chamber_meshes):
                            self._invalidate_mesh(self._cyl_chamber_meshes[cyl_mesh_idx])
                        self._invalidate_mesh(self._cyl_rod_meshes[cyl_mesh_idx])
                        self._invalidate_mesh(self._cyl_piston_meshes[cyl_mesh_idx])
                        if cyl_mesh_idx < len(self._cyl_piston_ring_lines):
                            _set_line_item_pos(self._cyl_piston_ring_lines[cyl_mesh_idx], None)
                        if cyl_mesh_idx < len(self._cyl_rod_core_lines):
                            _set_line_item_pos(self._cyl_rod_core_lines[cyl_mesh_idx], None)
                    cyl_mesh_idx += 1
                    continue
                bore_d, rod_d, outer_d, stroke_len, dead_cap_len, dead_rod_len, dead_height_len, body_len = self._corner_cylinder_contract(cyl_index=cyl_index, corner=corner)
                stroke_col = self._column_for_cyl_stroke(cyl_index, corner)
                try:
                    stroke_pos = _g(stroke_col, 0.0)
                except Exception:
                    stroke_pos = 0.0
                truth_gate = self._cylinder_truth_gate(cyl_index)
                packaging_state = None
                if bool(truth_gate.get("enabled")):
                    packaging_state = _cylinder_visual_state_from_packaging(
                        top_xyz=np.asarray(top_pt, dtype=float),
                        bot_xyz=np.asarray(bot_pt, dtype=float),
                        stroke_pos_m=float(stroke_pos),
                        stroke_len_m=float(stroke_len),
                        bore_d_m=float(bore_d),
                        rod_d_m=float(rod_d),
                        outer_d_m=float(outer_d),
                        dead_cap_len_m=float(dead_cap_len),
                        dead_rod_len_m=float(dead_rod_len),
                        dead_height_m=float(dead_height_len),
                        body_len_m=float(body_len),
                    )
                if cyl_mesh_idx < len(self._cyl_body_meshes):
                    if packaging_state is None:
                        self._invalidate_mesh(self._cyl_body_meshes[cyl_mesh_idx])
                        if cyl_mesh_idx < len(self._cyl_chamber_meshes):
                            self._invalidate_mesh(self._cyl_chamber_meshes[cyl_mesh_idx])
                        self._invalidate_mesh(self._cyl_rod_meshes[cyl_mesh_idx])
                        self._invalidate_mesh(self._cyl_piston_meshes[cyl_mesh_idx])
                        if cyl_mesh_idx < len(self._cyl_piston_ring_lines):
                            _set_line_item_pos(self._cyl_piston_ring_lines[cyl_mesh_idx], None)
                        if cyl_mesh_idx < len(self._cyl_rod_core_lines):
                            _set_line_item_pos(self._cyl_rod_core_lines[cyl_mesh_idx], None)
                    else:
                        piston_radius = float(packaging_state.get("piston_radius_m", 0.0) or 0.0)
                        _set_mesh_from_segment(
                            self._cyl_body_meshes[cyl_mesh_idx],
                            packaging_state.get("housing_seg") or packaging_state.get("body_seg"),
                            float(packaging_state.get("body_outer_radius_m", 0.0) or 0.0),
                        )
                        if cyl_mesh_idx < len(self._cyl_chamber_meshes):
                            _set_mesh_from_segment(
                                self._cyl_chamber_meshes[cyl_mesh_idx],
                                packaging_state.get("body_seg"),
                                piston_radius,
                            )
                        _set_mesh_from_segment(
                            self._cyl_rod_meshes[cyl_mesh_idx],
                            packaging_state.get("rod_seg"),
                            float(packaging_state.get("rod_radius_m", 0.0) or 0.0),
                        )
                        _set_disc_mesh(
                            self._cyl_piston_meshes[cyl_mesh_idx],
                            packaging_state.get("piston_center"),
                            packaging_state.get("axis_unit"),
                            piston_radius,
                        )
                        if cyl_mesh_idx < len(self._cyl_piston_ring_lines):
                            ring_vertices = None
                            try:
                                ring_vertices = self._circle_line_vertices(
                                    radius_m=piston_radius,
                                    center_xyz=np.asarray(packaging_state.get("piston_center"), dtype=float) if packaging_state.get("piston_center") is not None else np.zeros(3, dtype=float),
                                    normal_xyz=np.asarray(packaging_state.get("axis_unit"), dtype=float) if packaging_state.get("axis_unit") is not None else np.array([0.0, 1.0, 0.0], dtype=float),
                                    segments=40,
                                )
                            except Exception:
                                logger.exception(
                                    "Car3D piston ring polyline build failed; hiding piston ring instead of aborting frame.",
                                    extra={"corner": str(corner), "cyl_index": int(cyl_index)},
                                )
                            _set_line_item_pos(self._cyl_piston_ring_lines[cyl_mesh_idx], ring_vertices)
                        if cyl_mesh_idx < len(self._cyl_rod_core_lines):
                            _set_line_item_pos(
                                self._cyl_rod_core_lines[cyl_mesh_idx],
                                _rod_internal_centerline_vertices_from_packaging_state(packaging_state),
                            )
                cyl_mesh_idx += 1
        if self._cyl_frame_mount_markers is not None:
            try:
                frame_mount_pts = [p for p in (cyl1_top_local_pts + cyl2_top_local_pts) if p is not None]
                if frame_mount_pts:
                    mount_lines = self._contact_marker_line_vertices(
                        np.asarray(frame_mount_pts, dtype=float),
                        size_m=max(0.018, 0.14 * float(self.geom.wheel_radius)),
                    )
                    self._cyl_frame_mount_markers.setData(pos=np.asarray(mount_lines, dtype=float))
                    self._cyl_frame_mount_markers.setVisible(True)
                else:
                    self._cyl_frame_mount_markers.setData(pos=np.zeros((0, 3), dtype=float))
                    self._cyl_frame_mount_markers.setVisible(False)
            except Exception:
                try:
                    self._cyl_frame_mount_markers.setData(pos=np.zeros((0, 3), dtype=float))
                    self._cyl_frame_mount_markers.setVisible(False)
                except Exception:
                    pass
        if self._cyl_piston_markers is not None:
            try:
                self._cyl_piston_markers.setVisible(False)
            except Exception:
                pass

        # ---- Vectors (velocity & acceleration) in local body frame
        def _arrow_lines_3d(origin_xyz: np.ndarray, vec_xyz: np.ndarray) -> np.ndarray:
            origin = np.asarray(origin_xyz, dtype=float).reshape(3)
            vec = np.asarray(vec_xyz, dtype=float).reshape(3)
            mag = float(np.linalg.norm(vec))
            if not np.isfinite(mag) or mag <= 1e-12:
                return np.zeros((0, 3), dtype=float)
            end = origin + vec
            u = vec / mag
            side = np.cross(u, np.array([0.0, 0.0, 1.0], dtype=float))
            side_norm = float(np.linalg.norm(side))
            if not np.isfinite(side_norm) or side_norm <= 1e-12:
                side = np.cross(u, np.array([0.0, 1.0, 0.0], dtype=float))
                side_norm = float(np.linalg.norm(side))
            side = side / max(side_norm, 1e-12)
            head = 0.18 * max(0.2, mag)
            leg1 = end + head * (-u + 0.35 * side)
            leg2 = end + head * (-u - 0.35 * side)
            return np.asarray([origin, end, end, leg1, end, leg2], dtype=float)

        z_vec_offset = 0.55 * body_h + 0.15 * float(self.geom.wheel_radius)
        vec_origin = np.asarray(center_draw, dtype=float) + np.asarray(R_local[:, 2], dtype=float) * float(z_vec_offset)
        vel_vec = np.asarray(R_local[:, 0], dtype=float) * float(speed_along_road * self._vel_scale)
        acc_vec = (
            np.asarray(R_local[:, 0], dtype=float) * float(external_ax * self._accel_scale)
            + np.asarray(R_local[:, 1], dtype=float) * float(external_ay * self._accel_scale)
        )
        if self._vec_vel:
            self._vec_vel.setData(pos=_arrow_lines_3d(vec_origin, vel_vec))
        if self._vec_acc:
            self._vec_acc.setData(pos=_arrow_lines_3d(vec_origin, acc_vec))

        # ---- Road preview (dense surface mesh + lighter visible wire grid)
        try:
            if self._grid is not None:
                self._grid.setVisible(not bool(self._visual.get("show_road", True)))
        except Exception:
            pass

        if self._visual.get("show_road", True) and self._road_mesh and self._road_edges and self._road_stripes:
            try:
                s_world = b.ensure_s_world()
                xw, yw = b.ensure_world_xy()
                s0 = _sample_series_local(s_world, i0=i0, i1=i1, alpha=alpha, default=0.0)
                x0 = _sample_series_local(xw, i0=i0, i1=i1, alpha=alpha, default=0.0)
                y0 = _sample_series_local(yw, i0=i0, i1=i1, alpha=alpha, default=0.0)

                la = self._stable_road_preview_lookahead_m()
                s_min = s0 - self._stable_road_preview_history_m()
                s_max = s0 + la

                wb = float(getattr(self.geom, "wheelbase", 1.5))
                s_c, z_c = b.ensure_road_profile(wheelbase_m=wb, mode="center")
                s_l, z_l = b.ensure_road_profile(wheelbase_m=wb, mode="left")
                s_r, z_r = b.ensure_road_profile(wheelbase_m=wb, mode="right")

                s_min, s_max = _clamp_window_to_interpolation_support(
                    request_start_m=float(s_min),
                    request_end_m=float(s_max),
                    support_axes=(s_world, s_c, s_l, s_r),
                )
                if s_max <= s_min + 1e-6:
                    if self._contact_patch_mesh is not None:
                        self._contact_patch_mesh.setMeshData(meshdata=gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32)))
                        self._contact_patch_mesh.setVisible(False)
                    return

                try:
                    raw_n = int(max(
                        np.count_nonzero((np.asarray(s_world, dtype=float) >= s_min) & (np.asarray(s_world, dtype=float) <= s_max)),
                        np.count_nonzero((np.asarray(s_c, dtype=float) >= s_min) & (np.asarray(s_c, dtype=float) <= s_max)),
                    ))
                except Exception:
                    raw_n = 0
                try:
                    vp_w = int(max(640, self.view.width()))
                    vp_h = int(max(480, self.view.height()))
                except Exception:
                    vp_w, vp_h = 1280, 720

                if bool(self._playback_active) and bool(self._playback_perf_mode):
                    min_long = int(max(120, min(self._road_pts, 160)))
                    max_long = 260
                    min_lat = 5
                    max_lat = 7
                elif bool(self._playback_active):
                    min_long = int(max(160, min(self._road_pts, 180)))
                    max_long = 420
                    min_lat = 5
                    max_lat = 9
                else:
                    min_long = int(max(240, self._road_pts))
                    max_long = 1200
                    min_lat = 9
                    max_lat = int(max(15, self._road_lat_pts))

                target_n_long, n_lat, cross_stride, lateral_stride = _road_display_counts_from_view(
                    visible_length_m=float(s_max - s_min),
                    raw_point_count=int(raw_n),
                    viewport_width_px=vp_w,
                    viewport_height_px=vp_h,
                    min_long=int(min_long),
                    max_long=int(max_long),
                    min_lat=int(min_lat),
                    max_lat=int(max_lat),
                )

                # Dense surface mesh must be world-anchored too, otherwise the shaded
                # triangles visibly drift over the same road relief during playback.
                # The key requirement here is stronger than the previous fix:
                #   - spacing must not depend on the *current viewport size*;
                #   - rows must be fully world-anchored, not "anchored interior + moving edges".
                # We therefore build the surface rows from a bundle-stable spacing and extend
                # the requested range by one row on both sides before clamping to support.
                surface_spacing_m = float(self._stable_road_surface_spacing(
                    viewport_width_px=int(vp_w),
                    min_long=int(min_long),
                    max_long=int(max_long),
                ))
                native_step_m = float(max(1e-6, float(getattr(self, "_road_native_long_step_m", surface_spacing_m))))
                surface_spacing_m = float(max(surface_spacing_m, native_step_m))
                surface_row_min, surface_row_max = _clamp_window_to_interpolation_support(
                    request_start_m=float(s_min - surface_spacing_m),
                    request_end_m=float(s_max + surface_spacing_m),
                    support_axes=(s_world, s_c, s_l, s_r),
                )
                surface_stride_rows = int(max(1, round(surface_spacing_m / native_step_m)))
                # Build the dense surface from stable native support rows instead of from a fresh
                # local resampling grid for every frame. This removes viewport/playback-dependent
                # longitudinal drift of the shaded road mesh and of the rails derived from it.
                s_nodes = _road_native_support_s_values_from_axis(
                    support_s_m=np.asarray(s_world, dtype=float),
                    s_min_m=float(surface_row_min),
                    s_max_m=float(surface_row_max),
                    stride_rows=int(surface_stride_rows),
                    extra_rows_each_side=1,
                )
                if s_nodes.size < 2:
                    s_nodes = _road_grid_target_s_values_from_range(
                        s_min_m=float(surface_row_min),
                        s_max_m=float(surface_row_max),
                        cross_spacing_m=float(surface_spacing_m),
                        anchor_s_m=0.0,
                        include_last=False,
                    )
                if s_nodes.size >= 2:
                    s_nodes = np.asarray(s_nodes, dtype=float)
                else:
                    s_nodes = np.linspace(surface_row_min, surface_row_max, int(max(2, target_n_long)), dtype=float)
                n_long = int(s_nodes.size)
                x_nodes = np.interp(s_nodes, s_world, xw)
                y_nodes = np.interp(s_nodes, s_world, yw)

                dx = x_nodes - x0
                dy = y_nodes - y0
                c = math.cos(-yaw0)
                s = math.sin(-yaw0)
                xl = c * dx - s * dy
                yl = s * dx + c * dy

                zc = np.interp(s_nodes, s_c, z_c)
                zl = np.interp(s_nodes, s_l, z_l)
                zr = np.interp(s_nodes, s_r, z_r)

                s_norm_cache = getattr(self, "_road_path_s_world_cache", None)
                nx_world_cache = getattr(self, "_road_path_nx_world_cache", None)
                ny_world_cache = getattr(self, "_road_path_ny_world_cache", None)
                if (
                    s_norm_cache is not None
                    and nx_world_cache is not None
                    and ny_world_cache is not None
                    and int(np.asarray(s_norm_cache, dtype=float).size) >= 2
                ):
                    nx_world = np.interp(s_nodes, np.asarray(s_norm_cache, dtype=float), np.asarray(nx_world_cache, dtype=float))
                    ny_world = np.interp(s_nodes, np.asarray(s_norm_cache, dtype=float), np.asarray(ny_world_cache, dtype=float))
                    nx = c * nx_world - s * ny_world
                    ny = s * nx_world + c * ny_world
                    norm = np.sqrt(nx * nx + ny * ny) + 1e-9
                    nx = nx / norm
                    ny = ny / norm
                else:
                    dxl = np.gradient(xl)
                    dyl = np.gradient(yl)
                    norm = np.sqrt(dxl * dxl + dyl * dyl) + 1e-9
                    nx = -dyl / norm
                    ny = dxl / norm

                half = 0.5 * float(self._road_width_m)
                verts, _faces_unused, _lat_t = _road_surface_grid_from_profiles(
                    x_center=xl,
                    y_center=yl,
                    z_left=zl,
                    z_center=zc,
                    z_right=zr,
                    normal_x=nx,
                    normal_y=ny,
                    half_width_m=half,
                    lateral_count=int(n_lat),
                    build_faces=False,
                )
                if verts.size == 0:
                    raise ValueError('road surface grid is empty')
                cache_key = (int(n_long), int(n_lat))
                if cache_key not in self._road_faces_cache:
                    self._road_faces_cache[cache_key] = _grid_faces_rect(int(n_long), int(n_lat))
                faces = np.asarray(self._road_faces_cache[cache_key], dtype=np.int32)
                self._road_mesh.setMeshData(meshdata=gl.MeshData(vertexes=verts, faces=faces))
                self._road_mesh.setVisible(True)

                left_edge = np.asarray([verts[ii * int(n_lat) + (int(n_lat) - 1)] for ii in range(int(n_long))], dtype=float)
                right_edge = np.asarray([verts[ii * int(n_lat) + 0] for ii in range(int(n_long))], dtype=float)
                edge = np.vstack([left_edge, right_edge[::-1]])
                self._road_edges.setData(pos=edge)
                self._road_edges.setVisible(True)

                ds_long = float(max(1e-6, surface_spacing_m))
                grid_cross_spacing_m = float(self._stable_road_grid_cross_spacing(
                    viewport_width_px=int(vp_w),
                    ds_long_m=float(ds_long),
                ))
                grid_stride_rows = int(max(1, round(float(grid_cross_spacing_m) / native_step_m)))
                # Use the same bundle-stable native support lattice for the visible wire grid.
                # World-anchored spacing alone is not enough when the viewport changes: the
                # cross-bars must come from fixed dataset rows rather than from a fresh range-based
                # target list rebuilt for every visible window.
                grid_target_s = _road_native_support_s_values_from_axis(
                    support_s_m=np.asarray(s_world, dtype=float),
                    s_min_m=float(s_min),
                    s_max_m=float(s_max),
                    stride_rows=int(grid_stride_rows),
                    extra_rows_each_side=0,
                )
                if grid_target_s.size < 1:
                    grid_target_s = _road_grid_target_s_values_from_range(
                        s_min_m=float(s_min),
                        s_max_m=float(s_max),
                        cross_spacing_m=grid_cross_spacing_m,
                        anchor_s_m=0.0,
                        include_last=False,
                    )
                rail_lines = _road_grid_line_segments(
                    vertices_xyz=verts,
                    n_long=int(n_long),
                    n_lat=int(n_lat),
                    cross_stride=int(max(1, cross_stride)),
                    lateral_stride=int(max(1, lateral_stride)),
                    include_longitudinal=True,
                    include_crossbars=False,
                    force_last_crossbar=False,
                )
                cross_lines = _road_crossbar_line_segments_from_profiles(
                    s_targets_m=grid_target_s,
                    s_nodes_m=s_nodes,
                    x_center=xl,
                    y_center=yl,
                    z_left=zl,
                    z_center=zc,
                    z_right=zr,
                    normal_x=nx,
                    normal_y=ny,
                    half_width_m=half,
                    lateral_count=int(n_lat),
                )
                if rail_lines.size == 0 and cross_lines.size == 0:
                    grid_lines = np.zeros((0, 3), dtype=float)
                elif rail_lines.size == 0:
                    grid_lines = np.asarray(cross_lines, dtype=float)
                elif cross_lines.size == 0:
                    grid_lines = np.asarray(rail_lines, dtype=float)
                else:
                    grid_lines = np.vstack([np.asarray(rail_lines, dtype=float), np.asarray(cross_lines, dtype=float)])
                if grid_lines.size == 0:
                    grid_lines = np.zeros((0, 3), dtype=float)
                else:
                    grid_lines = np.asarray(grid_lines, dtype=float)
                    grid_lines[:, 2] += 0.003
                self._road_stripes.setData(pos=grid_lines)
                self._road_stripes.setVisible(True)

                if self._contact_patch_mesh is not None or self._contact_pts is not None or self._contact_links is not None:
                    patch_faces_all: list[np.ndarray] = []
                    patch_verts_all: list[np.ndarray] = []
                    pts: list[list[float]] = []
                    cols: list[list[float]] = []
                    links: list[list[float]] = []
                    wheel_radius_m = float(self.geom.wheel_radius)
                    wheel_width_m = float(self.geom.wheel_width)
                    ds = float(max(1e-6, (s_max - s_min) / max(1, int(n_long) - 1)))
                    row_half_span = int(max(4, math.ceil(max(0.55, 1.5 * wheel_radius_m) / ds)))
                    for idx, corner in enumerate(corners):
                        center = np.asarray(wheel_pose_centers[idx], dtype=float)
                        axle = np.asarray(wheel_pose_axles[idx], dtype=float)
                        up = np.asarray(wheel_pose_ups[idx], dtype=float)
                        solver_contact_pt = np.asarray(road_local_pts[idx], dtype=float)

                        if np.all(np.isfinite(solver_contact_pt)):
                            row_anchor_x = float(solver_contact_pt[0])
                            row_anchor_y = float(solver_contact_pt[1])
                        else:
                            row_anchor_x = float(center[0])
                            row_anchor_y = float(center[1])
                        row_center = int(np.argmin((xl - row_anchor_x) ** 2 + (yl - row_anchor_y) ** 2))
                        row_start = max(0, row_center - row_half_span)
                        row_stop = min(int(n_long), row_center + row_half_span + 1)
                        sub_verts, sub_faces = _regular_grid_submesh(
                            vertices_xyz=verts,
                            n_long=int(n_long),
                            n_lat=int(n_lat),
                            row_start=int(row_start),
                            row_stop=int(row_stop),
                            col_start=0,
                            col_stop=int(n_lat),
                        )
                        patch_verts_i, patch_faces_i = _road_patch_mesh_inside_wheel_cylinder(
                            vertices_xyz=sub_verts,
                            faces=sub_faces,
                            wheel_center_xyz=center,
                            wheel_axle_xyz=axle,
                            wheel_up_xyz=up,
                            wheel_radius_m=wheel_radius_m,
                            wheel_width_m=wheel_width_m,
                            refine_steps=1,
                        )
                        patch_contact_pt = _contact_point_from_patch_faces(
                            vertices_xyz=patch_verts_i,
                            faces=patch_faces_i,
                            wheel_center_xyz=center,
                            wheel_up_xyz=up,
                        )
                        if np.all(np.isfinite(solver_contact_pt)):
                            contact_pt = solver_contact_pt
                        elif patch_contact_pt is not None:
                            contact_pt = np.asarray(patch_contact_pt, dtype=float)
                            road_local_pts[idx] = np.asarray(contact_pt, dtype=float)
                        else:
                            contact_pt = np.asarray(center, dtype=float) - np.asarray(up, dtype=float) * wheel_radius_m
                        pts.append([float(contact_pt[0]), float(contact_pt[1]), float(contact_pt[2])])
                        in_air = bool(wheel_air[idx] > 0.5) or (patch_faces_i.size == 0)
                        cols.append([1.0, 0.35, 0.2, 1.0] if in_air else [0.2, 0.9, 0.35, 1.0])
                        links.append([float(contact_pt[0]), float(contact_pt[1]), float(contact_pt[2])])
                        link_wheel_pt = np.asarray(center, dtype=float) - np.asarray(up, dtype=float) * wheel_radius_m
                        links.append([float(link_wheel_pt[0]), float(link_wheel_pt[1]), float(link_wheel_pt[2])])
                        if patch_faces_i.size and patch_verts_i.size:
                            base = sum(arr.shape[0] for arr in patch_verts_all)
                            patch_verts_all.append(np.asarray(patch_verts_i, dtype=float))
                            patch_faces_all.append(np.asarray(np.asarray(patch_faces_i, dtype=np.int32) + int(base), dtype=np.int32))

                    if self._contact_pts is not None:
                        self._contact_pts.setData(pos=self._contact_marker_line_vertices(np.asarray(pts, dtype=float), size_m=max(0.02, 0.18 * wheel_radius_m)))
                    if self._contact_links is not None:
                        self._contact_links.setData(pos=np.asarray(links, dtype=float))
                    if self._contact_patch_mesh is not None:
                        if patch_faces_all and patch_verts_all:
                            patch_faces = np.vstack(patch_faces_all)
                            patch_verts = np.vstack(patch_verts_all)
                            self._contact_patch_mesh.setMeshData(meshdata=gl.MeshData(vertexes=patch_verts, faces=patch_faces))
                            self._contact_patch_mesh.setVisible(bool(self._visual.get("show_road", True)))
                        else:
                            self._contact_patch_mesh.setMeshData(meshdata=gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32)))
                            self._contact_patch_mesh.setVisible(False)
            except Exception:
                try:
                    self._road_mesh.setMeshData(meshdata=gl.MeshData(vertexes=np.zeros((0, 3), float), faces=np.zeros((0, 3), int)))
                    self._road_mesh.setVisible(False)
                    self._road_edges.setData(pos=np.zeros((0, 3), float))
                    self._road_edges.setVisible(False)
                    self._road_stripes.setData(pos=np.zeros((0, 3), float))
                    self._road_stripes.setVisible(False)
                    if self._contact_patch_mesh is not None:
                        self._contact_patch_mesh.setMeshData(meshdata=gl.MeshData(vertexes=np.zeros((0, 3), dtype=float), faces=np.zeros((0, 3), dtype=np.int32)))
                        self._contact_patch_mesh.setVisible(False)
                except Exception:
                    pass

class CornerTable(QtWidgets.QTableWidget):
    """One compact table for 'all 4 corners at once' observability.

    Rows are picked from the wishlist: z/v/a for frame corners & wheels,
    road profile under each wheel, suspension deflections, stroke, contact flag.
    """

    ROWS = [
        "Рама z (м)",
        "Рама vz (м/с)",
        "Рама az (м/с²)",
        "Колесо z (м)",
        "Колесо vz (м/с)",
        "Колесо az (м/с²)",
        "Дорога z (м)",
        "Колесо-Рама (м)",
        "Колесо-Дорога (м)",
        "Шток s (м)",
        "Fшина (Н)",
        "В воздухе",
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(len(self.ROWS), 4, parent)
        self.setHorizontalHeaderLabels(list(CORNERS))
        self.setVerticalHeaderLabels(self.ROWS)
        self.horizontalHeader().setStretchLastSection(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setAlternatingRowColors(True)
        self._bundle_key: Optional[int] = None
        self._corner_cache: Dict[str, Dict[str, Any]] = {}
        self._cell_items: List[List[QtWidgets.QTableWidgetItem]] = [
            [QtWidgets.QTableWidgetItem("–") for _ in range(self.columnCount())]
            for _ in range(self.rowCount())
        ]

        # Pre-create items
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                it = self._cell_items[r][c]
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, c, it)
        _set_table_fixed_row_height(self)


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def set_bundle(self, b: DataBundle):
        self._bundle_key = id(b)
        self._corner_cache = _ensure_corner_signal_cache(b)

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b):
            self.set_bundle(b)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))

        for ci, c in enumerate(CORNERS):
            sig = self._corner_cache.get(str(c))
            if not sig:
                continue
            zb = sample(sig["zb"], 0.0)
            vb = sample(sig["vb"], 0.0)
            ab = sample(sig["ab"], 0.0)

            zw = sample(sig["zw"], 0.0)
            vw = sample(sig["vw"], 0.0)
            aw = sample(sig["aw"], 0.0)

            road_arr = sig["zr"]
            zr = sample(road_arr, float("nan")) if road_arr is not None else float("nan")

            z_w_minus_body = zw - zb
            z_w_minus_road = (zw - zr) if np.isfinite(zr) else float("nan")

            s = sample(sig["stroke"], 0.0)
            Ft = sample(sig["tireF"], 0.0)
            air = int(sample(sig["air"], 0.0) > 0.5)

            vals = [
                _fmt(zb, digits=3),
                _fmt(vb, digits=3),
                _fmt(ab, digits=2),
                _fmt(zw, digits=3),
                _fmt(vw, digits=3),
                _fmt(aw, digits=2),
                _fmt(zr, digits=3),
                _fmt(z_w_minus_body, digits=3),
                _fmt(z_w_minus_road, digits=3),
                _fmt(s, digits=3),
                _fmt(Ft, digits=0),
                "1" if air else "0",
            ]
            for r, v in enumerate(vals):
                it = self._cell_items[r][ci]
                _set_table_item_text_if_changed(it, v)

                # Colorize "in air"
                if r == (len(self.ROWS) - 1):
                    _set_air_flag_item_foreground(it, bool(air))

class CornerQuickTable(QtWidgets.QTableWidget):
    """Pinned compact table: the 4 corners at once (most important signals).

    Goal: keep essential z/deflection/stroke/contact visible WITHOUT scrolling.
    This complements the full CornerTable (detailed) below in the scroll area.
    """

    ROWS = [
        "Рама z (м)",
        "Колесо-Рама (м)",
        "Колесо-Дорога (м)",
        "Шток s (м)",
        "Fшина (Н)",
        "В воздухе",
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(len(self.ROWS), 4, parent)
        self.setHorizontalHeaderLabels(list(CORNERS))
        self.setVerticalHeaderLabels(self.ROWS)
        self.horizontalHeader().setStretchLastSection(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setAlternatingRowColors(True)
        self.setMaximumHeight(165)
        self._bundle_key: Optional[int] = None
        self._corner_cache: Dict[str, Dict[str, Any]] = {}
        self._cell_items: List[List[QtWidgets.QTableWidgetItem]] = [
            [QtWidgets.QTableWidgetItem("–") for _ in range(self.columnCount())]
            for _ in range(self.rowCount())
        ]

        # Slightly smaller font to fit in the pinned area
        f = self.font()
        try:
            f.setPointSize(max(7, int(f.pointSize()) - 1))
            self.setFont(f)
        except Exception:
            pass

        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                it = self._cell_items[r][c]
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, c, it)
        _set_table_fixed_row_height(self, padding=7, minimum=18)

    def set_bundle(self, b: DataBundle):
        self._bundle_key = id(b)
        self._corner_cache = _ensure_corner_signal_cache(b)

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b):
            self.set_bundle(b)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))

        for ci, c in enumerate(CORNERS):
            sig = self._corner_cache.get(str(c))
            if not sig:
                continue
            zb = sample(sig["zb"], 0.0)
            zw = sample(sig["zw"], 0.0)
            road_arr = sig["zr"]
            zr = sample(road_arr, float("nan")) if road_arr is not None else float("nan")

            z_w_minus_body = zw - zb
            z_w_minus_road = (zw - zr) if np.isfinite(zr) else float("nan")

            s = sample(sig["stroke"], 0.0)
            Ft = sample(sig["tireF"], 0.0)
            air = int(sample(sig["air"], 0.0) > 0.5)

            vals = [
                _fmt(zb, digits=3),
                _fmt(z_w_minus_body, digits=3),
                _fmt(z_w_minus_road, digits=3),
                _fmt(s, digits=3),
                _fmt(Ft, digits=0),
                "1" if air else "0",
            ]
            for r, v in enumerate(vals):
                it = self._cell_items[r][ci]
                _set_table_item_text_if_changed(it, v)

                # Colorize wheel in air
                if r == (len(self.ROWS) - 1):
                    _set_air_flag_item_foreground(it, bool(air))



class _RoadProfileCanvas(QtWidgets.QWidget):
    """Lightweight road profile renderer for always-visible dock mode."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self._xrange: tuple[float, float] = (-8.0, 35.0)
        self._yrange: tuple[float, float] = (-0.15, 0.15)
        self._front_x: float = 1.15
        self._rear_x: float = -1.15
        self._curves: Dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._markers: Dict[str, Optional[tuple[float, float]]] = {}
        self._curve_colors: Dict[str, QtGui.QColor] = {
            "ЛП": QtGui.QColor(70, 180, 255, 220),
            "ПП": QtGui.QColor(90, 220, 130, 220),
            "ЛЗ": QtGui.QColor(255, 170, 60, 220),
            "ПЗ": QtGui.QColor(255, 90, 120, 220),
        }
        self._bg_cache_key: Optional[tuple[Any, ...]] = None
        self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        self._curve_pens: Dict[str, QtGui.QPen] = {}
        for corner, color in self._curve_colors.items():
            pen = QtGui.QPen(color, 2.0)
            try:
                pen.setCosmetic(True)
            except Exception:
                pass
            self._curve_pens[corner] = pen
        self._grid_pen = QtGui.QPen(QtGui.QColor(90, 98, 110, 70), 1.0, QtCore.Qt.DashLine)
        self._zero_pen = QtGui.QPen(QtGui.QColor(180, 180, 180, 120), 1.0)
        self._wheel_pen = QtGui.QPen(QtGui.QColor(140, 140, 140, 120), 1.0, QtCore.Qt.DashLine)
        self._border_pen = QtGui.QPen(QtGui.QColor(62, 68, 78), 1.0)
        for pen in (self._grid_pen, self._zero_pen, self._wheel_pen, self._border_pen):
            try:
                pen.setCosmetic(True)
            except Exception:
                pass

    def clear_data(self) -> None:
        self._curves.clear()
        self._markers.clear()
        self.update()

    def _invalidate_background_cache(self) -> None:
        self._bg_cache_key = None
        self._bg_cache_pixmap = None

    def resizeEvent(self, event: QtGui.QResizeEvent):  # type: ignore[override]
        self._invalidate_background_cache()
        super().resizeEvent(event)

    def set_wheelbase(self, wheelbase_m: float) -> None:
        wb = float(wheelbase_m)
        new_front = +0.5 * wb
        new_rear = -0.5 * wb
        if abs(float(new_front) - float(self._front_x)) > 1e-9 or abs(float(new_rear) - float(self._rear_x)) > 1e-9:
            self._front_x = new_front
            self._rear_x = new_rear
            self._invalidate_background_cache()

    def set_state(
        self,
        *,
        curves: Dict[str, tuple[np.ndarray, np.ndarray]],
        markers: Dict[str, Optional[tuple[float, float]]],
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        wheelbase_m: float,
    ) -> None:
        self._curves = {
            str(corner): (
                np.asarray(pair[0], dtype=float).reshape(-1),
                np.asarray(pair[1], dtype=float).reshape(-1),
            )
            for corner, pair in curves.items()
        }
        self._markers = {
            str(corner): (None if pos is None else (float(pos[0]), float(pos[1])))
            for corner, pos in markers.items()
        }
        next_xrange = (float(x_range[0]), float(x_range[1]))
        next_yrange = (float(y_range[0]), float(y_range[1]))
        if next_xrange != self._xrange or next_yrange != self._yrange:
            self._xrange = next_xrange
            self._yrange = next_yrange
            self._invalidate_background_cache()
        else:
            self._xrange = next_xrange
            self._yrange = next_yrange
        self.set_wheelbase(float(wheelbase_m))
        self.update()

    @staticmethod
    def _plot_rect(rect: QtCore.QRect) -> QtCore.QRectF:
        return QtCore.QRectF(rect.adjusted(52, 12, -14, -28))

    @staticmethod
    def _safe_range(lo: float, hi: float, pad: float) -> tuple[float, float]:
        if not np.isfinite(lo) or not np.isfinite(hi):
            return (-pad, pad)
        if abs(float(hi) - float(lo)) <= 1e-9:
            mid = 0.5 * (float(lo) + float(hi))
            return (mid - pad, mid + pad)
        return (float(lo), float(hi))

    @staticmethod
    def _draw_tick_labels(
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
    ) -> None:
        painter.setPen(QtGui.QColor(178, 186, 196))
        font = painter.font()
        try:
            font.setPointSize(max(7, int(font.pointSize()) - 1))
        except Exception:
            pass
        painter.setFont(font)
        x0, x1 = x_range
        y0, y1 = y_range
        painter.drawText(
            QtCore.QRectF(rect.left(), rect.bottom() + 6.0, 110.0, 16.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"{x0:.0f} m",
        )
        painter.drawText(
            QtCore.QRectF(rect.right() - 110.0, rect.bottom() + 6.0, 110.0, 16.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"{x1:.0f} m",
        )
        painter.drawText(
            QtCore.QRectF(rect.left() - 48.0, rect.top() - 8.0, 42.0, 16.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"{y1:.2f}",
        )
        painter.drawText(
            QtCore.QRectF(rect.left() - 48.0, rect.bottom() - 8.0, 42.0, 16.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"{y0:.2f}",
        )
        painter.drawText(
            QtCore.QRectF(rect.left(), rect.bottom() + 6.0, rect.width(), 16.0),
            QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter,
            "distance (m)",
        )
        painter.save()
        try:
            painter.translate(rect.left() - 36.0, rect.center().y())
            painter.rotate(-90.0)
            painter.drawText(
                QtCore.QRectF(-0.5 * rect.height(), -8.0, rect.height(), 16.0),
                QtCore.Qt.AlignCenter,
                "road z (m)",
            )
        finally:
            painter.restore()

    def _ensure_background_cache(
        self,
        *,
        plot_rect: QtCore.QRectF,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
    ) -> Optional[QtGui.QPixmap]:
        w = max(1, int(self.width()))
        h = max(1, int(self.height()))
        key = (
            w,
            h,
            round(float(plot_rect.left()), 3),
            round(float(plot_rect.top()), 3),
            round(float(plot_rect.width()), 3),
            round(float(plot_rect.height()), 3),
            round(float(x_range[0]), 6),
            round(float(x_range[1]), 6),
            round(float(y_range[0]), 6),
            round(float(y_range[1]), 6),
            round(float(self._front_x), 6),
            round(float(self._rear_x), 6),
        )
        if key == self._bg_cache_key and self._bg_cache_pixmap is not None:
            return self._bg_cache_pixmap

        dpr = 1.0
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        pix = QtGui.QPixmap(int(max(1.0, w * dpr)), int(max(1.0, h * dpr)))
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(QtGui.QColor(15, 18, 24))

        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        p.setPen(self._border_pen)
        p.setBrush(QtGui.QColor(21, 26, 34))
        p.drawRoundedRect(plot_rect, 6.0, 6.0)

        x0, x1 = x_range
        y0, y1 = y_range
        dx = max(1e-9, float(x1 - x0))
        dy = max(1e-9, float(y1 - y0))

        def map_x_scalar(x: float) -> float:
            return float(plot_rect.left()) + (float(x) - float(x0)) * (float(plot_rect.width()) / dx)

        def map_y_scalar(y: float) -> float:
            return float(plot_rect.bottom()) - (float(y) - float(y0)) * (float(plot_rect.height()) / dy)

        p.setClipRect(plot_rect.adjusted(0.0, 0.0, 1.0, 1.0))
        p.setPen(self._grid_pen)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            xx = plot_rect.left() + frac * plot_rect.width()
            yy = plot_rect.top() + frac * plot_rect.height()
            p.drawLine(QtCore.QPointF(xx, plot_rect.top()), QtCore.QPointF(xx, plot_rect.bottom()))
            p.drawLine(QtCore.QPointF(plot_rect.left(), yy), QtCore.QPointF(plot_rect.right(), yy))

        p.setPen(self._wheel_pen)
        for wx in (self._front_x, self._rear_x):
            if x0 <= float(wx) <= x1:
                xp = map_x_scalar(float(wx))
                p.drawLine(QtCore.QPointF(xp, plot_rect.top()), QtCore.QPointF(xp, plot_rect.bottom()))

        if y0 <= 0.0 <= y1:
            p.setPen(self._zero_pen)
            yz = map_y_scalar(0.0)
            p.drawLine(QtCore.QPointF(plot_rect.left(), yz), QtCore.QPointF(plot_rect.right(), yz))

        p.setClipping(False)
        self._draw_tick_labels(p, rect=plot_rect, x_range=x_range, y_range=y_range)
        p.end()

        self._bg_cache_key = key
        self._bg_cache_pixmap = pix
        return self._bg_cache_pixmap

    def paintEvent(self, _event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        plot_rect = self._plot_rect(self.rect())
        if plot_rect.width() <= 8.0 or plot_rect.height() <= 8.0:
            p.fillRect(self.rect(), QtGui.QColor(15, 18, 24))
            return

        x0, x1 = self._safe_range(*self._xrange, pad=1.0)
        y0, y1 = self._safe_range(*self._yrange, pad=0.1)
        dx = max(1e-9, float(x1 - x0))
        dy = max(1e-9, float(y1 - y0))

        def map_x(x: np.ndarray | float) -> np.ndarray | float:
            return plot_rect.left() + (np.asarray(x, dtype=float) - x0) * (plot_rect.width() / dx)

        def map_y(y: np.ndarray | float) -> np.ndarray | float:
            return plot_rect.bottom() - (np.asarray(y, dtype=float) - y0) * (plot_rect.height() / dy)

        bg = self._ensure_background_cache(plot_rect=plot_rect, x_range=(x0, x1), y_range=(y0, y1))
        if bg is not None:
            p.drawPixmap(0, 0, bg)
        else:
            p.fillRect(self.rect(), QtGui.QColor(15, 18, 24))

        p.setClipRect(plot_rect.adjusted(0.0, 0.0, 1.0, 1.0))
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for corner in CORNERS:
            pair = self._curves.get(str(corner))
            if pair is None:
                continue
            x_arr, y_arr = pair
            if x_arr.size < 2 or y_arr.size < 2:
                continue
            mask = np.isfinite(x_arr) & np.isfinite(y_arr)
            if np.count_nonzero(mask) < 2:
                continue
            xp = np.asarray(map_x(x_arr[mask]), dtype=float).reshape(-1)
            yp = np.asarray(map_y(y_arr[mask]), dtype=float).reshape(-1)
            poly = QtGui.QPolygonF([QtCore.QPointF(float(xv), float(yv)) for xv, yv in zip(xp, yp)])
            if poly.count() >= 2:
                p.setPen(self._curve_pens.get(str(corner), QtGui.QPen(QtGui.QColor(220, 220, 220), 2.0)))
                p.drawPolyline(poly)

            marker = self._markers.get(str(corner))
            if marker is None:
                continue
            mx, my = marker
            if not np.isfinite(mx) or not np.isfinite(my):
                continue
            if not (x0 <= float(mx) <= x1 and y0 <= float(my) <= y1):
                continue
            color = self._curve_colors.get(str(corner), QtGui.QColor(220, 220, 220, 220))
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QBrush(color))
            p.drawEllipse(QtCore.QPointF(float(map_x(mx)), float(map_y(my))), 3.5, 3.5)

        p.setClipping(False)


class RoadProfilePanel(QtWidgets.QWidget):
    """Road elevation profile (per wheel) in a distance window around the car.

    X-axis: meters relative to the car's COM (0). Wheel contact positions are
    marked at ±wheelbase/2.
    Y-axis: road Z (meters).

    This is intentionally simple: it is NOT a road/CAD editor.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._wheelbase = 2.3
        self._bundle_key: Optional[int] = None
        self._profile_cache: Dict[str, Any] = {}
        self._last_xrange: Optional[tuple[float, float]] = None
        self._last_yrange: Optional[tuple[float, float]] = None
        self._last_visual_key: Optional[tuple[Any, ...]] = None
        self._compact_dock_mode = False
        self._compact_plot_height = 110
        self._compact_max_height = 138
        self._full_plot_min_height = 150
        self._road_profile_point_budget_compact = 176
        self._road_profile_point_budget_full = 288
        self._panel_bg = QtGui.QColor(15, 18, 24)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.controls_row = QtWidgets.QWidget(self)
        ctl = QtWidgets.QHBoxLayout(self.controls_row)
        ctl.setContentsMargins(0, 0, 0, 0)

        self.sp_hist = QtWidgets.QDoubleSpinBox()
        self.sp_hist.setRange(0.0, 100.0)
        self.sp_hist.setSingleStep(1.0)
        self.sp_hist.setValue(8.0)
        self.sp_hist.setSuffix(" m")

        self.sp_ahead = QtWidgets.QDoubleSpinBox()
        self.sp_ahead.setRange(5.0, 300.0)
        self.sp_ahead.setSingleStep(5.0)
        self.sp_ahead.setValue(35.0)
        self.sp_ahead.setSuffix(" m")

        self.lbl_hist = QtWidgets.QLabel("history:")
        ctl.addWidget(self.lbl_hist)
        ctl.addWidget(self.sp_hist)
        ctl.addSpacing(10)
        self.lbl_ahead = QtWidgets.QLabel("lookahead:")
        ctl.addWidget(self.lbl_ahead)
        ctl.addWidget(self.sp_ahead)
        ctl.addStretch(1)
        lay.addWidget(self.controls_row)

        self.lbl_status = QtWidgets.QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color:#b45309;font-weight:600;")
        self.lbl_status.hide()
        lay.addWidget(self.lbl_status)

        self.lbl_legend = QtWidgets.QLabel(
            "<span style='color:#46b4ff'>ЛП</span>   "
            "<span style='color:#5adc82'>ПП</span>   "
            "<span style='color:#ffaa3c'>ЛЗ</span>   "
            "<span style='color:#ff5a78'>ПЗ</span>"
        )
        try:
            self.lbl_legend.setStyleSheet("color:#cfd8e3;")
        except Exception:
            pass
        lay.addWidget(self.lbl_legend)

        self.plot = _RoadProfileCanvas()
        lay.addWidget(self.plot, stretch=1)
        self.set_compact_dock_mode(True)

    def paintEvent(self, event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), self._panel_bg)

    def set_compact_dock_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(getattr(self, "_compact_dock_mode", False)):
            return
        self._compact_dock_mode = compact
        vpol = QtWidgets.QSizePolicy.Maximum if compact else QtWidgets.QSizePolicy.Expanding
        plot_h = int(self._compact_plot_height if compact else self._full_plot_min_height)
        max_h = int(self._compact_max_height if compact else 16777215)
        try:
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
            self.setMaximumHeight(max_h)
        except Exception:
            pass
        try:
            self.plot.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
            self.plot.setMinimumHeight(plot_h)
            self.plot.setMaximumHeight(plot_h if compact else 16777215)
        except Exception:
            pass
        try:
            self.controls_row.setVisible(not compact)
        except Exception:
            pass
        try:
            self.lbl_legend.setVisible(not compact)
        except Exception:
            pass
        try:
            self.updateGeometry()
            self.adjustSize()
        except Exception:
            pass

    def set_bundle(self, b: DataBundle) -> None:
        self._bundle_key = id(b)
        geom = infer_geometry(b.meta)
        self._wheelbase = float(geom.wheelbase)
        self._profile_cache = _ensure_road_profile_panel_cache(b, float(self._wheelbase))
        self._last_yrange = tuple(self._profile_cache.get("y_range", (-0.1, 0.1)))
        self._last_xrange = None
        self._last_visual_key = None
        self._update_wheel_lines()

    def set_wheelbase(self, wheelbase_m: float):
        self._wheelbase = float(wheelbase_m)
        self._update_wheel_lines()

    def _update_wheel_lines(self):
        if self.plot is None:
            return
        try:
            self.plot.set_wheelbase(float(self._wheelbase))
        except Exception:
            pass

    def _set_status(self, message: str) -> None:
        if not hasattr(self, "lbl_status"):
            return
        msg = str(message or "").strip()
        if msg:
            self.lbl_status.setText(msg)
            self.lbl_status.show()
        else:
            self.lbl_status.hide()

    def _clear_curves(self) -> None:
        if self.plot is None:
            return
        self._last_visual_key = None
        try:
            self.plot.clear_data()
        except Exception:
            pass

    @staticmethod
    def _range_changed(prev: Optional[tuple[float, float]], curr: tuple[float, float], *, tol: float = 1e-9) -> bool:
        if prev is None:
            return True
        return abs(float(prev[0]) - float(curr[0])) > tol or abs(float(prev[1]) - float(curr[1])) > tol

    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if self.plot is None:
            return
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b) or not self._profile_cache:
            self.set_bundle(b)

        wb = float(self._wheelbase)
        cache = self._profile_cache or {}

        hist = float(self.sp_hist.value())
        ahead = float(self.sp_ahead.value())
        x_min = -hist
        x_max = +ahead

        t_cached = cache.get("t")
        t_series = t_cached if isinstance(t_cached, np.ndarray) else np.asarray(b.t, dtype=float).reshape(-1)
        s_cached = cache.get("s_world")
        s = s_cached if isinstance(s_cached, np.ndarray) else np.asarray(cache.get("s_world", np.zeros((0,), dtype=float)), dtype=float)
        if len(s) <= 1:
            return
        idx = int(_clamp(int(i), 0, len(s) - 1))
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(t_series, dtype=float),
            sample_t=sample_t,
            fallback_index=idx,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))
        s0 = sample(s, float(s[idx]))
        plot_width_px = int(max(160, float(self.plot.width())))
        budget_cap = self._road_profile_point_budget_compact if bool(self._compact_dock_mode) else self._road_profile_point_budget_full
        max_points = int(max(96, min(int(budget_cap), (plot_width_px // 4) + 24)))

        self._set_status("")
        missing_road: list[str] = []
        any_curve = False
        curves: Dict[str, tuple[np.ndarray, np.ndarray]] = {}
        markers: Dict[str, Optional[tuple[float, float]]] = {}
        corners_cache = cache.get("corners", {}) or {}
        prepared_corners: List[tuple[str, Dict[str, Any]]] = []
        visual_corner_keys: List[tuple[Any, ...]] = []
        world_lo = float(s0 + x_min)
        world_hi = float(s0 + x_max)
        pixel_world_step = max(1e-6, float(x_max - x_min) / max(24.0, float(plot_width_px)))
        s_bucket = int(round(float(s0) / pixel_world_step))

        for c in CORNERS:
            name = str(c)
            corner_cache = corners_cache.get(str(c))
            if not corner_cache or bool(corner_cache.get("missing", False)):
                missing_road.append(name)
                prepared_corners.append((name, {"missing": True}))
                visual_corner_keys.append((name, "missing"))
                continue

            x_world_cached = corner_cache.get("x_world")
            x_world = x_world_cached if isinstance(x_world_cached, np.ndarray) else np.asarray(corner_cache.get("x_world", np.zeros((0,), dtype=float)), dtype=float)
            z_cached = corner_cache.get("z")
            z_arr = z_cached if isinstance(z_cached, np.ndarray) else np.asarray(corner_cache.get("z", np.zeros((0,), dtype=float)), dtype=float)
            n = int(min(x_world.size, z_arr.size))
            if n <= 1:
                prepared_corners.append((name, {"missing": False, "empty": True}))
                visual_corner_keys.append((name, "empty"))
                continue
            x_world = x_world[:n]
            z_arr = z_arr[:n]

            j0 = int(np.searchsorted(x_world, world_lo, side="left"))
            j1 = int(np.searchsorted(x_world, world_hi, side="right"))
            j0 = int(_clamp(j0, 0, n - 1))
            j1 = int(_clamp(j1, j0 + 1, n))

            count = int(max(0, j1 - j0))
            if count <= 0:
                prepared_corners.append((name, {"missing": False, "empty": True}))
                visual_corner_keys.append((name, "empty"))
                continue

            try:
                marker_x = float(corner_cache.get("marker_x", _road_profile_corner_offset_m(name, wb)))
                zc = sample(z_arr, float("nan"))
                marker_z_bucket = -999999 if not np.isfinite(zc) else int(round(float(zc) * 1000.0))
            except Exception:
                marker_x = float(_road_profile_corner_offset_m(name, wb))
                zc = float("nan")
                marker_z_bucket = -999999

            prepared_corners.append(
                (
                    name,
                    {
                        "missing": False,
                        "empty": False,
                        "x_world": x_world,
                        "z_arr": z_arr,
                        "j0": int(j0),
                        "j1": int(j1),
                        "count": int(count),
                        "marker_x": float(marker_x),
                        "marker_z": float(zc),
                    },
                )
            )
            visual_corner_keys.append((name, int(j0), int(j1), int(min(count, int(max_points))), int(marker_z_bucket)))
            any_curve = True

        if missing_road:
            self._set_status(
                "NO ROAD DATA: missing canonical road traces for corners " + ", ".join(missing_road)
            )
        if not any_curve:
            self._clear_curves()
            return

        try:
            x_range = (float(x_min), float(x_max))
            self._last_xrange = x_range
            y_range = tuple(cache.get("y_range", self._last_yrange if self._last_yrange is not None else (-0.1, 0.1)))
            self._last_yrange = y_range
            visual_key = (
                int(s_bucket),
                int(max_points),
                tuple(visual_corner_keys),
                tuple(missing_road),
                int(round(float(x_range[0]) * 1000.0)),
                int(round(float(x_range[1]) * 1000.0)),
            )
            if visual_key == self._last_visual_key:
                return

            for name, meta in prepared_corners:
                if bool(meta.get("missing", False)) or bool(meta.get("empty", False)):
                    curves[name] = (np.zeros((0,), dtype=float), np.zeros((0,), dtype=float))
                    markers[name] = None
                    continue
                x_world = np.asarray(meta.get("x_world", np.zeros((0,), dtype=float)), dtype=float)
                z_arr = np.asarray(meta.get("z_arr", np.zeros((0,), dtype=float)), dtype=float)
                j0 = int(meta.get("j0", 0))
                j1 = int(meta.get("j1", 0))
                count = int(meta.get("count", 0))
                if count > int(max_points):
                    idx = np.unique(np.linspace(j0, j1 - 1, int(max_points), dtype=int))
                    x2 = np.asarray(x_world[idx], dtype=float) - float(s0)
                    z2 = np.asarray(z_arr[idx], dtype=float)
                else:
                    x2 = np.asarray(x_world[j0:j1], dtype=float) - float(s0)
                    z2 = np.asarray(z_arr[j0:j1], dtype=float)
                curves[name] = (np.asarray(x2, dtype=float), np.asarray(z2, dtype=float))
                zc = float(meta.get("marker_z", float("nan")))
                markers[name] = None if not np.isfinite(zc) else (float(meta.get("marker_x", 0.0)), zc)

            self.plot.set_state(
                curves=curves,
                markers=markers,
                x_range=x_range,
                y_range=y_range,
                wheelbase_m=float(self._wheelbase),
            )
            self._last_visual_key = visual_key
        except Exception:
            pass


class PressureGauge(QtWidgets.QWidget):
    """Simple but readable pressure indicator (bar gauge)."""

    def __init__(self, name: str, *, max_bar_g: float = 12.0, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.name = str(name)
        self.max_bar_g = float(max_bar_g)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self.lbl_name = QtWidgets.QLabel(self.name)
        self.lbl_name.setStyleSheet("font-weight:600;")
        self.lbl_value = QtWidgets.QLabel("—")
        self.lbl_value.setStyleSheet("color: #cfcfcf;")

        self.bar = _PressureBarCanvas(max_bar_g=self.max_bar_g)

        lay.addWidget(self.lbl_name)
        lay.addWidget(self.lbl_value)
        lay.addWidget(self.bar)

    def set_value_bar_g(self, bar_g: Optional[float]):
        if bar_g is None or (isinstance(bar_g, float) and (np.isnan(bar_g) or np.isinf(bar_g))):
            _set_label_text_if_changed(self.lbl_value, "—")
            self.bar.set_value_bar_g(None)
            return
        v = float(bar_g)
        _set_label_text_if_changed(self.lbl_value, f"{v:.2f} bar(g)")
        self.bar.set_value_bar_g(v)


class _PressureBarCanvas(QtWidgets.QWidget):
    """Lightweight static-gradient bar used by PressureGauge."""

    def __init__(self, *, max_bar_g: float, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.max_bar_g = float(max(1.0, max_bar_g))
        self._value_bar_g: Optional[float] = None
        self._fill_frac: float = 0.0
        self._visual_key: Optional[int] = None
        self._bg_color = QtGui.QColor(27, 31, 36)
        self._track_color = QtGui.QColor(27, 31, 36)
        self._border_pen = QtGui.QPen(QtGui.QColor(68, 68, 68), 1.0)
        self._bg_cache_key: Optional[tuple[int, int]] = None
        self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        try:
            self._border_pen.setCosmetic(True)
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self.setFixedHeight(10)

    def resizeEvent(self, event: QtGui.QResizeEvent):  # type: ignore[override]
        self._bg_cache_key = None
        self._bg_cache_pixmap = None
        super().resizeEvent(event)

    def _ensure_background_cache(self) -> Optional[QtGui.QPixmap]:
        key = (int(max(1, self.width())), int(max(1, self.height())))
        if key == self._bg_cache_key and self._bg_cache_pixmap is not None:
            return self._bg_cache_pixmap
        dpr = 1.0
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        pix = QtGui.QPixmap(int(max(1.0, float(key[0]) * dpr)), int(max(1.0, float(key[1]) * dpr)))
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(self._bg_color)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(0.5, 0.5, max(1.0, float(key[0]) - 1.0), max(1.0, float(key[1]) - 1.0))
        p.setPen(self._border_pen)
        p.setBrush(self._track_color)
        p.drawRoundedRect(rect, 4.0, 4.0)
        p.end()
        self._bg_cache_key = key
        self._bg_cache_pixmap = pix
        return self._bg_cache_pixmap

    def set_value_bar_g(self, bar_g: Optional[float]) -> None:
        if bar_g is None or (isinstance(bar_g, float) and (np.isnan(bar_g) or np.isinf(bar_g))):
            frac = 0.0
            visual_key = -1
        else:
            v = float(_clamp(float(bar_g), 0.0, float(self.max_bar_g)))
            frac = 0.0 if self.max_bar_g <= 1e-12 else float(v / self.max_bar_g)
            visual_key = int(round(frac * 1000.0))
        if visual_key == self._visual_key:
            return
        self._value_bar_g = None if visual_key < 0 else float(bar_g)
        self._fill_frac = float(frac)
        self._visual_key = int(visual_key)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        bg = self._ensure_background_cache()
        if bg is not None:
            p.drawPixmap(0, 0, bg)
        frac = float(self._fill_frac)
        if frac <= 1e-6:
            return
        rect = QtCore.QRectF(0.5, 0.5, max(1.0, float(self.width()) - 1.0), max(1.0, float(self.height()) - 1.0))
        fill_w = max(0.0, (rect.width() - 2.0) * frac)
        if fill_w <= 0.0:
            return
        fill = QtCore.QRectF(rect.left() + 1.0, rect.top() + 1.0, fill_w, max(1.0, rect.height() - 2.0))
        grad = QtGui.QLinearGradient(fill.topLeft(), fill.topRight())
        grad.setColorAt(0.0, QtGui.QColor("#3fa34d"))
        grad.setColorAt(0.65, QtGui.QColor("#f6c244"))
        grad.setColorAt(1.0, QtGui.QColor("#d9534f"))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QBrush(grad))
        p.drawRoundedRect(fill, 3.5, 3.5)


class _PercentBarCanvas(QtWidgets.QWidget):
    """Cheap percent bar for dense detail tables."""

    _bg_cache: Dict[tuple[int, int, int], QtGui.QPixmap] = {}

    def __init__(self, *, fill_color: Any, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self._fill_frac = 0.0
        self._format = "%p%"
        self._text_visible = True
        self._display_text = "0%"
        self._bg_color = QtGui.QColor(27, 31, 36)
        self._track_color = QtGui.QColor(27, 31, 36)
        self._fill_brush = QtGui.QBrush(QtGui.QColor(fill_color))
        self._border_pen = QtGui.QPen(QtGui.QColor(68, 68, 68), 1.0)
        self._text_pen = QtGui.QPen(QtGui.QColor(235, 240, 245))
        self._text_font = QtGui.QFont(self.font())
        try:
            self._border_pen.setCosmetic(True)
            self._text_pen.setCosmetic(True)
            self._text_font.setPointSize(max(7, int(self._text_font.pointSize()) - 1))
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self.setFixedHeight(12)

    def value(self) -> int:
        return int(self._value)

    def setRange(self, minimum: int, maximum: int) -> None:
        mn = int(minimum)
        mx = int(maximum)
        if mx < mn:
            mn, mx = mx, mn
        if mn == self._minimum and mx == self._maximum:
            return
        self._minimum = mn
        self._maximum = mx
        self.setValue(self._value)

    def setTextVisible(self, visible: bool) -> None:
        target = bool(visible)
        if self._text_visible == target:
            return
        self._text_visible = target
        self._sync_text_state()
        self.update()

    def setFormat(self, fmt: str) -> None:
        target = str(fmt or "%p%")
        if self._format == target:
            return
        self._format = target
        self._sync_text_state()
        self.update()

    def setValue(self, value: int) -> None:
        try:
            target = int(value)
        except Exception:
            target = 0
        target = int(_clamp(float(target), float(self._minimum), float(self._maximum)))
        if target == self._value:
            return
        self._value = target
        denom = max(1, int(self._maximum - self._minimum))
        self._fill_frac = float(max(0.0, min(1.0, float(target - self._minimum) / float(denom))))
        self._sync_text_state()
        self.update()

    def _sync_text_state(self) -> None:
        if not bool(self._text_visible):
            self._display_text = ""
            return
        denom = max(1, int(self._maximum - self._minimum))
        pct = int(round(float(self._value - self._minimum) * 100.0 / float(denom)))
        self._display_text = str(self._format).replace("%p", str(pct))

    @classmethod
    def _ensure_bg_cache(
        cls,
        key: tuple[int, int, int],
        *,
        dpr: float,
        bg_color: QtGui.QColor,
        track_color: QtGui.QColor,
        border_pen: QtGui.QPen,
    ) -> Optional[QtGui.QPixmap]:
        cached = cls._bg_cache.get(key)
        if cached is not None:
            return cached
        width, height, _ = key
        pix = QtGui.QPixmap(int(max(1.0, float(width) * dpr)), int(max(1.0, float(height) * dpr)))
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(bg_color)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(0.5, 0.5, max(1.0, float(width) - 1.0), max(1.0, float(height) - 1.0))
        p.setPen(border_pen)
        p.setBrush(track_color)
        p.drawRoundedRect(rect, 4.0, 4.0)
        p.end()
        if len(cls._bg_cache) > 96:
            cls._bg_cache.clear()
        cls._bg_cache[key] = pix
        return pix

    def _cached_background(self) -> Optional[QtGui.QPixmap]:
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        key = (
            int(max(1, self.width())),
            int(max(1, self.height())),
            int(round(dpr * 100.0)),
        )
        return self._ensure_bg_cache(
            key,
            dpr=dpr,
            bg_color=self._bg_color,
            track_color=self._track_color,
            border_pen=self._border_pen,
        )

    def paintEvent(self, event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        bg = self._cached_background()
        if bg is not None:
            p.drawPixmap(0, 0, bg)
        frac = float(self._fill_frac)
        if frac > 1e-6:
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            rect = QtCore.QRectF(0.5, 0.5, max(1.0, float(self.width()) - 1.0), max(1.0, float(self.height()) - 1.0))
            fill_w = max(0.0, (rect.width() - 2.0) * frac)
            if fill_w > 0.0:
                fill = QtCore.QRectF(rect.left() + 1.0, rect.top() + 1.0, fill_w, max(1.0, rect.height() - 2.0))
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(self._fill_brush)
                p.drawRoundedRect(fill, 3.5, 3.5)
        if self._display_text:
            p.setRenderHint(QtGui.QPainter.Antialiasing, False)
            p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
            p.setPen(self._text_pen)
            p.setFont(self._text_font)
            p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self._display_text)


class PressurePanel(QtWidgets.QWidget):
    """Key node pressures + optional extra nodes list."""

    KEY_NODES = ("Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор")

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        lay.addLayout(grid)

        self.gauges: Dict[str, PressureGauge] = {}
        for k, (r, c) in zip(self.KEY_NODES, [(0, 0), (0, 1), (1, 0), (1, 1)]):
            g = PressureGauge(k, max_bar_g=12.0)
            self.gauges[k] = g
            grid.addWidget(g, r, c)

        # Extra nodes table (top-dynamics by default)
        self.lbl_extra = QtWidgets.QLabel("Другие узлы (top‑динамика):")
        self.lbl_extra.setStyleSheet("color:#cfcfcf;")
        lay.addWidget(self.lbl_extra)

        self.tbl_extra = QtWidgets.QTableWidget(0, 2)
        self.tbl_extra.setHorizontalHeaderLabels(["Узел", "P bar(g)"])
        self.tbl_extra.horizontalHeader().setStretchLastSection(True)
        self.tbl_extra.verticalHeader().setVisible(False)
        self.tbl_extra.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_extra.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tbl_extra.setAlternatingRowColors(True)
        self.tbl_extra.setMaximumHeight(220)
        lay.addWidget(self.tbl_extra)

        self._extra_nodes: list[str] = []
        self._has_p = False
        self._bundle_key: Optional[int] = None
        self._patm_arr: Optional[np.ndarray] = None
        self._patm_default_pa: float = float(PATM_PA_DEFAULT)
        self._pressure_series_map: Dict[str, np.ndarray] = {}
        self._main_pressure_series_map: Dict[str, np.ndarray] = {}

    # NOTE:
    # Dock installation belongs to CockpitWidget, not PressurePanel.
    # Keep PressurePanel focused on pressure gauges / extra nodes only.

    def set_bundle(self, b: DataBundle):
        self._bundle_key = id(b)
        self._extra_nodes = []
        self._has_p = b.p is not None
        self._pressure_series_map = {}
        self._main_pressure_series_map = {}
        self._patm_arr, self._patm_default_pa = _infer_patm_source(b)
        fallback_mapping = {
            "Ресивер1": "давление_ресивер1_Па",
            "Ресивер2": "давление_ресивер2_Па",
            "Ресивер3": "давление_ресивер3_Па",
            "Аккумулятор": "давление_аккумулятор_Па",
        }
        for node, col in fallback_mapping.items():
            try:
                if b.main.has(col):
                    self._main_pressure_series_map[str(node)] = np.asarray(b.get(col, self._patm_default_pa), dtype=float)
            except Exception:
                pass
        if b.p is None:
            return

        # Choose "top dynamic" nodes: highest std over time (excluding ATМ + key nodes + time col)
        cols = [c for c in b.p.cols if c not in ("время_с", "АТМ") and c not in self.KEY_NODES]
        if not cols:
            return
        try:
            mat = b.p.values
            # Build std per column; safe for NaNs
            stds = []
            for c in cols:
                idx = b.p.index_of(c)
                if idx is None:
                    continue
                v = np.asarray(mat[:, idx], dtype=float)
                s = float(np.nanstd(v))
                stds.append((s, c))
            stds.sort(reverse=True, key=lambda t: t[0])
            self._extra_nodes = [c for _s, c in stds[: min(12, len(stds))]]
        except Exception:
            self._extra_nodes = cols[: min(12, len(cols))]
        for node in list(self.KEY_NODES) + list(self._extra_nodes):
            try:
                if b.p.has(node):
                    self._pressure_series_map[str(node)] = np.asarray(b.p.column(node), dtype=float)
            except Exception:
                pass


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b):
            self.set_bundle(b)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))
        if b.p is None:
            # Fallback: try df_main "давление_ресиверX_Па"
            # (This is less detailed than df_p, but keeps the panel useful.)
            patm = sample(self._patm_arr, self._patm_default_pa)
            for node, g in self.gauges.items():
                arr = self._main_pressure_series_map.get(str(node))
                if arr is not None:
                    P = sample(arr, patm)
                    g.set_value_bar_g((P - patm) / BAR_PA)
                else:
                    g.set_value_bar_g(None)

            _set_label_text_if_changed(self.lbl_extra, "Другие узлы: n/a (нужно record_full=True)")
            _set_table_row_count_if_changed(self.tbl_extra, 0)
            return

        patm = sample(self._patm_arr, self._patm_default_pa)
        # Key gauges
        for node, g in self.gauges.items():
            arr = self._pressure_series_map.get(str(node))
            if arr is not None:
                P = sample(arr, float("nan"))
                g.set_value_bar_g((P - patm) / BAR_PA)
            else:
                g.set_value_bar_g(None)

        # Extra nodes table
        if not self._extra_nodes:
            _set_label_text_if_changed(self.lbl_extra, "Другие узлы: —")
            _set_table_row_count_if_changed(self.tbl_extra, 0)
            return

        _set_label_text_if_changed(self.lbl_extra, f"Другие узлы (top‑динамика, {len(self._extra_nodes)}):")
        _set_table_row_count_if_changed(self.tbl_extra, len(self._extra_nodes))
        for r, name in enumerate(self._extra_nodes):
            try:
                arr = self._pressure_series_map.get(str(name))
                P = sample(arr, float("nan")) if arr is not None else float("nan")
                bar_g = (P - patm) / BAR_PA
                s = "—" if not np.isfinite(bar_g) else f"{bar_g:.2f}"
            except Exception:
                s = "—"

            it0 = self.tbl_extra.item(r, 0)
            if it0 is None:
                it0 = QtWidgets.QTableWidgetItem(str(name))
                self.tbl_extra.setItem(r, 0, it0)
            _set_table_item_text_if_changed(it0, str(name))

            it1 = self.tbl_extra.item(r, 1)
            if it1 is None:
                it1 = QtWidgets.QTableWidgetItem(s)
                it1.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.tbl_extra.setItem(r, 1, it1)
            _set_table_item_text_if_changed(it1, s)


def _infer_valve_kind(name: str) -> str:
    s = str(name).lower()
    # heuristics (keep it cheap and robust)
    if any(k in s for k in ("atm", "атм", "выхлоп", "exh", "exhaust")):
        return "выхлоп"
    if any(k in s for k in ("fill", "supply", "подпит", "inlet", "charge_in")):
        return "подпитка"
    if any(k in s for k in ("charge", "заряд", "acc", "акк")):
        return "заряд"
    if any(k in s for k in ("check", "обрат", "diode")):
        return "обратный"
    return "прочее"


class ValvePanel(QtWidgets.QWidget):
    """Valve opening indicators from df_open.

    Default shows only active valves (open > threshold) sorted by open.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        ctrl = QtWidgets.QHBoxLayout()
        lay.addLayout(ctrl)

        self.chk_active = QtWidgets.QCheckBox("только активные")
        self.chk_active.setChecked(True)
        ctrl.addWidget(self.chk_active)

        ctrl.addWidget(QtWidgets.QLabel("thr"))
        self.thr = QtWidgets.QDoubleSpinBox()
        self.thr.setRange(0.0, 1.0)
        self.thr.setSingleStep(0.05)
        self.thr.setDecimals(2)
        self.thr.setValue(0.05)
        ctrl.addWidget(self.thr)

        ctrl.addWidget(QtWidgets.QLabel("top"))
        self.topn = QtWidgets.QSpinBox()
        self.topn.setRange(5, 200)
        self.topn.setValue(30)
        ctrl.addWidget(self.topn)

        ctrl.addStretch(1)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Клапан/ребро", "Open %", "Тип"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMaximumHeight(280)
        lay.addWidget(self.table)
        _set_table_fixed_row_height(self.table, padding=6, minimum=18)

        self._names: list[str] = []
        self._kinds: list[str] = []
        self._idxs: np.ndarray | None = None
        self._row_handles: list[tuple[QtWidgets.QTableWidgetItem, _PercentBarCanvas, QtWidgets.QTableWidgetItem]] = []
        self._row_binding_keys: list[Optional[int]] = []
        self._last_display_key: Optional[tuple[Any, ...]] = None
        self._visible_rows: int = 0

    def set_bundle(self, b: DataBundle):
        self._names = []
        self._kinds = []
        self._idxs = None
        self._row_handles = []
        self._row_binding_keys = []
        self._last_display_key = None
        self._visible_rows = 0
        _set_table_row_count_if_changed(self.table, 0)
        if b.open is None:
            return
        cols = [c for c in b.open.cols if c not in ("время_с",)]
        idxs = []
        names = []
        kinds = []
        for c in cols:
            j = b.open.index_of(c)
            if j is None:
                continue
            idxs.append(int(j))
            names.append(str(c))
            kinds.append(_infer_valve_kind(str(c)))
        if idxs:
            self._idxs = np.array(idxs, dtype=int)
            self._names = names
            self._kinds = kinds

    def _ensure_row_widgets(self, rows: int) -> None:
        rows = int(max(0, rows))
        if int(self.table.rowCount()) < rows:
            _set_table_row_count_if_changed(self.table, rows)
        for r in range(len(self._row_handles), rows):
            it0 = QtWidgets.QTableWidgetItem("")
            pb = _PercentBarCanvas(fill_color="#4aa3df")
            pb.setRange(0, 100)
            pb.setTextVisible(True)
            pb.setFormat("%p%")
            it2 = QtWidgets.QTableWidgetItem("")
            it2.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 0, it0)
            self.table.setCellWidget(r, 1, pb)
            self.table.setItem(r, 2, it2)
            self._row_handles.append((it0, pb, it2))
            self._row_binding_keys.append(None)

    def _set_visible_rows(self, rows: int) -> None:
        target = int(max(0, rows))
        current = int(max(0, getattr(self, "_visible_rows", 0)))
        if target == current:
            return
        if target > current:
            for r in range(current, target):
                _set_table_row_hidden_if_changed(self.table, r, False)
        else:
            for r in range(target, current):
                _set_table_row_hidden_if_changed(self.table, r, True)
        self._visible_rows = target


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if b.open is None or self._idxs is None or not self._names:
            if self._last_display_key == tuple() and int(getattr(self, "_visible_rows", 0)) == 0:
                return
            self._last_display_key = tuple()
            _call_with_qt_update_batch(self.table, lambda: self._set_visible_rows(0))
            return

        thr = float(self.thr.value())
        topn = int(self.topn.value())
        only_active = bool(self.chk_active.isChecked())

        # values for all valves at time i
        try:
            sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
                np.asarray(b.t, dtype=float),
                sample_t=sample_t,
                fallback_index=i,
            )
            i0 = int(sample_i0)
            i1 = int(sample_i1)
            a = float(alpha)
            if i0 == i1 or a <= 1e-12:
                vals = np.asarray(b.open.values[i0, self._idxs], dtype=float)
            elif a >= 1.0 - 1e-12:
                vals = np.asarray(b.open.values[i1, self._idxs], dtype=float)
            else:
                vals0 = np.asarray(b.open.values[i0, self._idxs], dtype=float)
                vals1 = np.asarray(b.open.values[i1, self._idxs], dtype=float)
                vals = vals0 + (vals1 - vals0) * a
        except Exception:
            if self._last_display_key == tuple() and int(getattr(self, "_visible_rows", 0)) == 0:
                return
            self._last_display_key = tuple()
            _call_with_qt_update_batch(self.table, lambda: self._set_visible_rows(0))
            return

        order = _top_descending_indices(vals, topn, threshold=(thr if only_active else -1.0))
        if order.size == 0:
            if self._last_display_key == tuple() and int(getattr(self, "_visible_rows", 0)) == 0:
                return
            self._last_display_key = tuple()
            _call_with_qt_update_batch(self.table, lambda: self._set_visible_rows(0))
            return

        idxs = np.asarray(order, dtype=int)
        sel_vals = vals[idxs]
        display_pct = np.asarray(np.rint(np.clip(sel_vals, 0.0, 1.0) * 100.0), dtype=int)
        visual_key = tuple((int(j), int(display_pct[pos])) for pos, j in enumerate(idxs.tolist()))
        if visual_key == self._last_display_key and int(self.table.rowCount()) == int(idxs.size):
            return
        self._last_display_key = visual_key

        def _apply_rows() -> None:
            self._ensure_row_widgets(int(idxs.size))
            for r in range(int(idxs.size)):
                j = int(idxs[r])
                name = self._names[j]
                kind = self._kinds[j] if j < len(self._kinds) else _infer_valve_kind(name)
                it0, pb, it2 = self._row_handles[r]
                if self._row_binding_keys[r] != j:
                    _set_table_item_text_if_changed(it0, name)
                    _set_table_item_text_if_changed(it2, kind)
                    self._row_binding_keys[r] = j
                try:
                    _set_progress_value_if_changed(pb, int(display_pct[r]))
                except Exception:
                    pass
            self._set_visible_rows(int(idxs.size))

        _call_with_qt_update_batch(self.table, _apply_rows)








def _infer_flow_kind(name: str) -> str:
    """Heuristic flow grouping.

    We intentionally reuse the same keywords as valve grouping, because
    in this project edge names for mdot/open are usually similar.
    """
    try:
        return _infer_valve_kind(name)
    except Exception:
        return "other"


class _QuickBarListCanvas(QtWidgets.QWidget):
    """Compact lightweight list of bars with left/right text."""

    def __init__(
        self,
        *,
        max_rows: int,
        bar_color: QtGui.QColor,
        empty_label: str = "—",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.max_rows = int(max(1, max_rows))
        self.empty_label = str(empty_label)
        self._rows: List[Tuple[str, float, str]] = []
        self._rows_key: Optional[tuple[tuple[str, int, str], ...]] = None
        self._bar_color = QtGui.QColor(bar_color)
        self._bg_color = QtGui.QColor(19, 23, 28)
        self._row_bg_color = QtGui.QColor(24, 29, 35)
        self._track_color = QtGui.QColor(45, 52, 61)
        self._text_color = QtGui.QColor(232, 236, 241)
        self._muted_text_color = QtGui.QColor(176, 184, 196)
        self._border_pen = QtGui.QPen(QtGui.QColor(60, 68, 80), 1.0)
        self._text_font = QtGui.QFont(self.font())
        self._text_metrics = QtGui.QFontMetrics(self._text_font)
        self._text_metrics_key: Optional[tuple[str, int, int, int]] = None
        self._row_layout_key: Optional[tuple[int, int, int]] = None
        self._row_layout: list[tuple[QtCore.QRectF, QtCore.QRectF, QtCore.QRectF]] = []
        self._display_rows_key: Optional[tuple[tuple[Any, ...], tuple[int, int, int], tuple[str, int, int, int]]] = None
        self._display_rows: list[
            tuple[
                QtGui.QStaticText,
                QtCore.QPointF,
                float,
                QtGui.QColor,
                QtGui.QStaticText,
                QtCore.QPointF,
                QtGui.QColor,
            ]
        ] = []
        try:
            self._border_pen.setCosmetic(True)
        except Exception:
            pass
        self.setMinimumHeight(int(8 + self.max_rows * 18))
        self._static_bg_cache_key: Optional[tuple[int, int, int]] = None
        self._static_bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass

    def _invalidate_static_background_cache(self) -> None:
        self._static_bg_cache_key = None
        self._static_bg_cache_pixmap = None

    def resizeEvent(self, event: QtGui.QResizeEvent):  # type: ignore[override]
        self._invalidate_static_background_cache()
        self._row_layout_key = None
        self._row_layout = []
        self._display_rows_key = None
        self._display_rows = []
        super().resizeEvent(event)

    def clear_rows(self) -> None:
        self.set_rows([])

    def set_rows(self, rows: Sequence[tuple[str, float, str]]) -> None:
        normalized: List[Tuple[str, float, str]] = []
        for left, frac, right in list(rows)[: self.max_rows]:
            normalized.append(
                (
                    str(left),
                    float(_clamp(float(frac), 0.0, 1.0)),
                    str(right),
                )
            )
        key = tuple((left, int(round(frac * 100.0)), right) for left, frac, right in normalized)
        if key == self._rows_key:
            return
        self._rows = normalized
        self._rows_key = key
        self._rebuild_display_rows()
        self.update()

    @staticmethod
    def _row_metrics(rect: QtCore.QRectF, max_rows: int) -> tuple[float, float]:
        row_gap = 4.0
        row_h = max(16.0, (rect.height() - row_gap * max(0, max_rows - 1)) / max(1, max_rows))
        return row_h, row_gap

    def _ensure_text_metrics(self) -> tuple[QtGui.QFont, QtGui.QFontMetrics]:
        font = QtGui.QFont(self.font())
        try:
            font.setPointSize(max(8, int(font.pointSize()) - 1))
        except Exception:
            pass
        key = (
            str(font.family()),
            int(round(float(font.pointSizeF()) * 10.0)),
            int(font.weight()),
            int(bool(font.italic())),
        )
        if key != self._text_metrics_key:
            self._text_font = font
            self._text_metrics = QtGui.QFontMetrics(font)
            self._text_metrics_key = key
            self._display_rows_key = None
        return self._text_font, self._text_metrics

    @staticmethod
    def _prepare_static_text(text_item: QtGui.QStaticText, font: QtGui.QFont) -> None:
        try:
            text_item.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            text_item.prepare(QtGui.QTransform(), font)
        except Exception:
            pass

    def _ensure_row_layout(self) -> list[tuple[QtCore.QRectF, QtCore.QRectF, QtCore.QRectF]]:
        key = (int(max(1, self.width())), int(max(1, self.height())), int(self.max_rows))
        if key == self._row_layout_key and self._row_layout:
            return self._row_layout
        outer = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        row_h, row_gap = self._row_metrics(outer, self.max_rows)
        label_w = min(240.0, max(132.0, outer.width() * 0.42))
        right_w = min(132.0, max(72.0, outer.width() * 0.22))
        bar_gap = 8.0
        text_margin = 8.0
        layout: list[tuple[QtCore.QRectF, QtCore.QRectF, QtCore.QRectF]] = []
        for row_idx in range(self.max_rows):
            top = outer.top() + row_idx * (row_h + row_gap)
            row_rect = QtCore.QRectF(outer.left(), top, outer.width(), row_h)
            left_rect = QtCore.QRectF(
                row_rect.left() + text_margin,
                row_rect.top(),
                label_w - text_margin,
                row_rect.height(),
            )
            right_rect = QtCore.QRectF(
                row_rect.right() - right_w,
                row_rect.top(),
                right_w - text_margin,
                row_rect.height(),
            )
            bar_rect = QtCore.QRectF(
                left_rect.right() + bar_gap,
                row_rect.center().y() - 4.5,
                max(18.0, right_rect.left() - left_rect.right() - bar_gap * 2.0),
                9.0,
            )
            layout.append((left_rect, right_rect, bar_rect))
        self._row_layout_key = key
        self._row_layout = layout
        self._display_rows_key = None
        return self._row_layout

    def _rebuild_display_rows(self) -> None:
        _font, fm = self._ensure_text_metrics()
        layout = self._ensure_row_layout()
        metrics_key = tuple(self._text_metrics_key or ())
        layout_key = tuple(self._row_layout_key or ())
        rows_key = tuple(self._rows_key or ())
        display_key = (rows_key, layout_key, metrics_key)
        if display_key == self._display_rows_key:
            return
        display_rows: list[
            tuple[
                QtGui.QStaticText,
                QtCore.QPointF,
                float,
                QtGui.QColor,
                QtGui.QStaticText,
                QtCore.QPointF,
                QtGui.QColor,
            ]
        ] = []
        for row_idx, (left_rect, right_rect, _bar_rect) in enumerate(layout):
            if row_idx < len(self._rows):
                left, frac, right = self._rows[row_idx]
                text_color = self._text_color
                right_color = self._muted_text_color if not right else text_color
            else:
                left, frac, right = self.empty_label, 0.0, ""
                text_color = self._muted_text_color
                right_color = self._muted_text_color
            left_text = fm.elidedText(str(left), QtCore.Qt.ElideRight, max(8, int(left_rect.width())))
            right_text = fm.elidedText(str(right), QtCore.Qt.ElideLeft, max(8, int(right_rect.width())))
            left_static = QtGui.QStaticText(left_text)
            right_static = QtGui.QStaticText(right_text)
            self._prepare_static_text(left_static, self._text_font)
            self._prepare_static_text(right_static, self._text_font)
            left_y = float(left_rect.top() + max(0.0, (left_rect.height() - float(fm.height())) * 0.5))
            right_y = float(right_rect.top() + max(0.0, (right_rect.height() - float(fm.height())) * 0.5))
            right_w = float(fm.horizontalAdvance(right_text))
            display_rows.append(
                (
                    left_static,
                    QtCore.QPointF(float(left_rect.left()), left_y),
                    float(frac),
                    text_color,
                    right_static,
                    QtCore.QPointF(float(max(right_rect.left(), right_rect.right() - right_w)), right_y),
                    right_color,
                )
            )
        self._display_rows = display_rows
        self._display_rows_key = display_key

    def _ensure_static_background_cache(self) -> Optional[QtGui.QPixmap]:
        key = (int(max(1, self.width())), int(max(1, self.height())), int(self.max_rows))
        if key == self._static_bg_cache_key and self._static_bg_cache_pixmap is not None:
            return self._static_bg_cache_pixmap

        dpr = 1.0
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        pix = QtGui.QPixmap(
            int(max(1.0, float(max(1, self.width())) * dpr)),
            int(max(1.0, float(max(1, self.height())) * dpr)),
        )
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(self._bg_color)

        outer = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        row_h, row_gap = self._row_metrics(outer, self.max_rows)
        label_w = min(240.0, max(132.0, outer.width() * 0.42))
        right_w = min(132.0, max(72.0, outer.width() * 0.22))
        bar_gap = 8.0
        text_margin = 8.0

        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for row_idx in range(self.max_rows):
            top = outer.top() + row_idx * (row_h + row_gap)
            row_rect = QtCore.QRectF(outer.left(), top, outer.width(), row_h)
            p.setPen(self._border_pen)
            p.setBrush(self._row_bg_color)
            p.drawRoundedRect(row_rect, 6.0, 6.0)

            left_rect = QtCore.QRectF(
                row_rect.left() + text_margin,
                row_rect.top(),
                label_w - text_margin,
                row_rect.height(),
            )
            right_rect = QtCore.QRectF(
                row_rect.right() - right_w,
                row_rect.top(),
                right_w - text_margin,
                row_rect.height(),
            )
            bar_rect = QtCore.QRectF(
                left_rect.right() + bar_gap,
                row_rect.center().y() - 4.5,
                max(18.0, right_rect.left() - left_rect.right() - bar_gap * 2.0),
                9.0,
            )
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(self._track_color)
            p.drawRoundedRect(bar_rect, 4.0, 4.0)
        p.end()

        self._static_bg_cache_key = key
        self._static_bg_cache_pixmap = pix
        return self._static_bg_cache_pixmap

    def paintEvent(self, _event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        bg = self._ensure_static_background_cache()
        if bg is not None:
            p.drawPixmap(0, 0, bg)
        else:
            p.fillRect(self.rect(), self._bg_color)
        font, _fm = self._ensure_text_metrics()
        layout = self._ensure_row_layout()
        self._rebuild_display_rows()
        p.setFont(font)
        for row_idx, (left_rect, right_rect, bar_rect) in enumerate(layout):
            if row_idx < len(self._display_rows):
                left_static, left_pos, frac, text_color, right_static, right_pos, right_color = self._display_rows[row_idx]
            else:
                left_static = QtGui.QStaticText(self.empty_label)
                self._prepare_static_text(left_static, font)
                right_static = QtGui.QStaticText("")
                self._prepare_static_text(right_static, font)
                frac, text_color, right_color = (
                    0.0,
                    self._muted_text_color,
                    self._muted_text_color,
                )
                left_pos = QtCore.QPointF(float(left_rect.left()), float(left_rect.top()))
                right_pos = QtCore.QPointF(float(right_rect.left()), float(right_rect.top()))
            p.setPen(text_color)
            p.drawStaticText(left_pos, left_static)
            if float(frac) > 1e-6:
                fill_rect = QtCore.QRectF(bar_rect)
                fill_rect.setWidth(max(1.0, bar_rect.width() * float(frac)))
                p.setRenderHint(QtGui.QPainter.Antialiasing, True)
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(self._bar_color)
                p.drawRoundedRect(fill_rect, 4.0, 4.0)
                p.setRenderHint(QtGui.QPainter.Antialiasing, False)

            p.setPen(right_color)
            p.drawStaticText(right_pos, right_static)


class _QuickTextStripCanvas(QtWidgets.QWidget):
    """Compact painter-based header strip for quick panels."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._segments: list[tuple[str, QtGui.QColor]] = []
        self._segments_layout: list[tuple[str, QtGui.QColor, float, QtGui.QStaticText]] = []
        self._segments_key: Optional[tuple[tuple[str, int], ...]] = None
        self._segments_layout_key: Optional[tuple[tuple[Any, ...], tuple[tuple[str, int], ...]]] = None
        self._bg_color = QtGui.QColor(19, 23, 28)
        self._text_font = QtGui.QFont(self.font())
        self._text_metrics = QtGui.QFontMetrics(self._text_font)
        self._text_metrics_key: Optional[tuple[str, int, int, int]] = None
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self.setMinimumHeight(18)

    @staticmethod
    def _prepare_static_text(text_item: QtGui.QStaticText, font: QtGui.QFont) -> None:
        try:
            text_item.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            text_item.prepare(QtGui.QTransform(), font)
        except Exception:
            pass

    def _ensure_text_metrics(self) -> tuple[QtGui.QFont, QtGui.QFontMetrics]:
        font = QtGui.QFont(self.font())
        try:
            font.setPointSize(max(8, int(font.pointSize()) - 1))
        except Exception:
            pass
        key = (
            str(font.family()),
            int(round(float(font.pointSizeF()) * 10.0)),
            int(font.weight()),
            int(bool(font.italic())),
        )
        if key != self._text_metrics_key:
            self._text_font = font
            self._text_metrics = QtGui.QFontMetrics(font)
            self._text_metrics_key = key
        return self._text_font, self._text_metrics

    def _rebuild_segment_layout(self) -> None:
        font, fm = self._ensure_text_metrics()
        self._segments_layout = [
            (
                text,
                color,
                float(fm.horizontalAdvance(text)),
                QtGui.QStaticText(text),
            )
            for text, color in self._segments
        ]
        for _text, _color, _width, static_text in self._segments_layout:
            self._prepare_static_text(static_text, font)
        self._segments_layout_key = (
            tuple(self._text_metrics_key or ()),
            tuple(self._segments_key or ()),
        )

    def set_segments(self, segments: Sequence[tuple[str, QtGui.QColor]]) -> None:
        normalized: list[tuple[str, QtGui.QColor]] = []
        key_parts: list[tuple[str, int]] = []
        font, fm = self._ensure_text_metrics()
        layout: list[tuple[str, QtGui.QColor, float, QtGui.QStaticText]] = []
        for text, color in segments:
            text_s = str(text)
            qcolor = QtGui.QColor(color)
            normalized.append((text_s, qcolor))
            key_parts.append((text_s, int(qcolor.rgba())))
            static_text = QtGui.QStaticText(text_s)
            self._prepare_static_text(static_text, font)
            layout.append((text_s, qcolor, float(fm.horizontalAdvance(text_s)), static_text))
        key = tuple(key_parts)
        layout_key = (tuple(self._text_metrics_key or ()), key)
        if layout_key == self._segments_layout_key:
            return
        self._segments = normalized
        self._segments_key = key
        self._segments_layout = layout
        self._segments_layout_key = layout_key
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), self._bg_color)
        p.setRenderHints(QtGui.QPainter.TextAntialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(4.0, 0.0, -4.0, 0.0)
        font, _fm = self._ensure_text_metrics()
        expected_layout_key = (
            tuple(self._text_metrics_key or ()),
            tuple(self._segments_key or ()),
        )
        if expected_layout_key != self._segments_layout_key:
            self._rebuild_segment_layout()
        p.setFont(font)
        x = float(rect.left())
        y = float(rect.top())
        h = float(rect.height())
        spacing = 10.0
        last_rgba: Optional[int] = None
        for text, color, width0, static_text in self._segments_layout:
            if x >= rect.right():
                break
            width = min(float(width0), max(0.0, rect.right() - x))
            rgba = int(color.rgba())
            if rgba != last_rgba:
                p.setPen(color)
                last_rgba = rgba
            text_y = float(y + max(0.0, (h - float(_fm.height())) * 0.5))
            p.drawStaticText(QtCore.QPointF(x, text_y), static_text)
            x += max(8.0, width) + spacing


class FlowQuickPanel(QtWidgets.QWidget):
    """Pinned mini-panel: top mass flows (df_q / mdot) + group counters.

    Goal: see "is there flow right now?" at a glance without opening any tables.
    Does NOT require manual mapping (no CAD): edges are detected automatically by name.
    """

    def __init__(self, *, max_rows: int = 6, thr_kg_s: float = 0.001, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._full_max_rows = int(max(1, max_rows))
        self._compact_max_rows = int(max(2, min(self._full_max_rows, 3)))
        self.max_rows = int(self._full_max_rows)
        self.thr_kg_s = float(max(0.0, thr_kg_s))

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.header_canvas = _QuickTextStripCanvas(self)
        self.header_canvas.hide()
        lay.addWidget(self.header_canvas)

        self.lbl_groups = QtWidgets.QLabel("FLOW: n/a")
        self.lbl_groups.setStyleSheet("color:#b8c3cf;")
        lay.addWidget(self.lbl_groups)

        self.rows_canvas = _QuickBarListCanvas(
            max_rows=self.max_rows,
            bar_color=QtGui.QColor(123, 216, 143),
            parent=self,
        )
        lay.addWidget(self.rows_canvas)

        self._names: list[str] = []
        self._short_names: list[str] = []
        self._idxs: np.ndarray | None = None
        self._maxabs: np.ndarray | None = None
        self._kinds: list[str] = []
        self._kind_codes = np.zeros((0,), dtype=np.int8)
        self._compact_mode = False

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(self._compact_mode):
            return
        self._compact_mode = compact
        self.max_rows = int(self._compact_max_rows if compact else self._full_max_rows)
        self.rows_canvas.max_rows = int(self.max_rows)
        self.rows_canvas.setMinimumHeight(int(8 + self.max_rows * 18))
        try:
            self.setMaximumHeight(112 if compact else 16777215)
        except Exception:
            pass
        try:
            self.header_canvas.setVisible(compact)
            self.lbl_groups.setVisible(not compact)
        except Exception:
            pass
        self.rows_canvas.clear_rows()
        try:
            self.updateGeometry()
        except Exception:
            pass

    def set_bundle(self, b: DataBundle):
        self._names = []
        self._short_names = []
        self._idxs = None
        self._maxabs = None
        self._kinds = []
        self._kind_codes = np.zeros((0,), dtype=np.int8)

        if getattr(b, "q", None) is None:
            self.header_canvas.set_segments([("FLOW: n/a", QtGui.QColor(184, 195, 207))])
            _set_label_text_if_changed(self.lbl_groups, "FLOW: n/a")
            self._clear_rows()
            return

        cols = [c for c in b.q.cols if c not in ("время_с",)]
        idxs = []
        names = []
        short_names = []
        kinds = []
        kind_codes = []

        for c in cols:
            j = b.q.index_of(c)
            if j is None:
                continue
            name = str(c)
            kind = _infer_flow_kind(name)
            idxs.append(int(j))
            names.append(name)
            short_names.append(_shorten_display_name(name))
            kinds.append(kind)
            kind_codes.append(_kind_code_from_label(kind))

        if not idxs:
            self.header_canvas.set_segments([("FLOW: n/a", QtGui.QColor(184, 195, 207))])
            _set_label_text_if_changed(self.lbl_groups, "FLOW: n/a")
            self._clear_rows()
            return

        self._idxs = np.array(idxs, dtype=int)
        self._names = names
        self._short_names = short_names
        self._kinds = kinds
        self._kind_codes = np.asarray(kind_codes, dtype=np.int8)

        # robust max abs flow per edge for stable normalization
        try:
            mat = np.asarray(b.q.values[:, self._idxs], dtype=float)
            a = np.abs(mat)
            mx = np.nanpercentile(a, 99.0, axis=0)
            mx = np.asarray(mx, dtype=float)
            mx[~np.isfinite(mx)] = 0.0
            self._maxabs = mx
        except Exception:
            self._maxabs = None

        self._clear_rows()

    def _clear_rows(self):
        self.rows_canvas.clear_rows()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if getattr(b, "q", None) is None or self._idxs is None or not self._names:
            self.header_canvas.set_segments([("FLOW: n/a", QtGui.QColor(184, 195, 207))])
            _set_label_text_if_changed(self.lbl_groups, "FLOW: n/a")
            self._clear_rows()
            return

        try:
            sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
                np.asarray(b.t, dtype=float),
                sample_t=sample_t,
                fallback_index=i,
            )
            i0 = int(sample_i0)
            i1 = int(sample_i1)
            a = float(alpha)
            if i0 == i1 or a <= 1e-12:
                q = np.asarray(b.q.values[i0, self._idxs], dtype=float)
            elif a >= 1.0 - 1e-12:
                q = np.asarray(b.q.values[i1, self._idxs], dtype=float)
            else:
                q0 = np.asarray(b.q.values[i0, self._idxs], dtype=float)
                q1 = np.asarray(b.q.values[i1, self._idxs], dtype=float)
                q = q0 + (q1 - q0) * a
        except Exception:
            self.header_canvas.set_segments([("FLOW: n/a", QtGui.QColor(184, 195, 207))])
            _set_label_text_if_changed(self.lbl_groups, "FLOW: n/a")
            self._clear_rows()
            return

        thr = float(self.thr_kg_s)
        aq = np.abs(q)
        active_mask = aq > thr

        # group counters
        if self._kind_codes.size == aq.size:
            active_codes = self._kind_codes[active_mask]
            c_exh = int(np.count_nonzero(active_codes == 0))
            c_fill = int(np.count_nonzero(active_codes == 1))
            c_chg = int(np.count_nonzero(active_codes == 2))
            c_chk = int(np.count_nonzero(active_codes == 3))
            c_oth = int(np.count_nonzero(active_codes == 4))
        else:
            c_exh = c_fill = c_chg = c_chk = c_oth = 0

        flow_header = f"FLOW>|{thr*1000:.1f} g/s|  вых:{c_exh}  подп:{c_fill}  зар:{c_chg}  чек:{c_chk}  проч:{c_oth}"
        self.header_canvas.set_segments([(flow_header, QtGui.QColor(184, 195, 207))])
        _set_label_text_if_changed(self.lbl_groups, flow_header)

        # pick top by abs
        order = _top_descending_indices(aq, self.max_rows, threshold=thr)

        # update rows
        rows_data: list[tuple[str, float, str]] = []
        for j in order.tolist():
            j = int(j)
            mdot = float(q[j])
            kind = self._kinds[j] if j < len(self._kinds) else "other"
            # normalize
            denom = 0.0
            if self._maxabs is not None and j < int(self._maxabs.size):
                denom = float(self._maxabs[j])
            frac = 0.0 if denom <= 1e-12 else float(abs(mdot) / denom)
            short = self._short_names[j] if j < len(self._short_names) else _shorten_display_name(self._names[j])

            arrow = "→" if mdot >= 0.0 else "←"
            rows_data.append(
                (
                    f"{short} [{kind}]",
                    float(_clamp(frac, 0.0, 1.0)),
                    f"{arrow} {mdot*1000.0:+.1f} g/s",
                )
            )
        self.rows_canvas.set_rows(rows_data)


class FlowPanel(QtWidgets.QWidget):
    """Detailed mass flow table (df_q / mdot).

    - automatic edge detection
    - sortable by current |mdot|
    - optional filtering by |mdot| threshold
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        ctrl = QtWidgets.QHBoxLayout()
        lay.addLayout(ctrl)

        self.chk_active = QtWidgets.QCheckBox("только активные")
        self.chk_active.setChecked(True)
        ctrl.addWidget(self.chk_active)

        ctrl.addWidget(QtWidgets.QLabel("thr"))
        self.thr = QtWidgets.QDoubleSpinBox()
        self.thr.setRange(0.0, 10.0)
        self.thr.setSingleStep(0.1)
        self.thr.setDecimals(3)
        self.thr.setValue(1.0)  # g/s
        self.thr.setSuffix(" g/s")
        ctrl.addWidget(self.thr)

        ctrl.addWidget(QtWidgets.QLabel("top"))
        self.topn = QtWidgets.QSpinBox()
        self.topn.setRange(5, 500)
        self.topn.setValue(40)
        ctrl.addWidget(self.topn)

        ctrl.addStretch(1)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Ребро (mdot)", "q", "|q| %", "Тип"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMaximumHeight(320)
        lay.addWidget(self.table)
        _set_table_fixed_row_height(self.table, padding=6, minimum=18)

        self._names: list[str] = []
        self._idxs: np.ndarray | None = None
        self._maxabs: np.ndarray | None = None
        self._kinds: list[str] = []
        self._row_handles: list[tuple[QtWidgets.QTableWidgetItem, QtWidgets.QTableWidgetItem, _PercentBarCanvas, QtWidgets.QTableWidgetItem]] = []
        self._row_binding_keys: list[Optional[int]] = []
        self._last_display_key: Optional[tuple[Any, ...]] = None
        self._visible_rows: int = 0

    def set_bundle(self, b: DataBundle):
        self._names = []
        self._idxs = None
        self._maxabs = None
        self._kinds = []
        self._row_handles = []
        self._row_binding_keys = []
        self._last_display_key = None
        self._visible_rows = 0
        _set_table_row_count_if_changed(self.table, 0)

        if getattr(b, "q", None) is None:
            return

        cols = [c for c in b.q.cols if c not in ("время_с",)]
        idxs = []
        names = []
        kinds = []

        for c in cols:
            j = b.q.index_of(c)
            if j is None:
                continue
            idxs.append(int(j))
            names.append(str(c))
            kinds.append(_infer_flow_kind(str(c)))

        if idxs:
            self._idxs = np.array(idxs, dtype=int)
            self._names = names
            self._kinds = kinds

            # robust max abs for normalization
            try:
                mat = np.asarray(b.q.values[:, self._idxs], dtype=float)
                a = np.abs(mat)
                mx = np.nanpercentile(a, 99.0, axis=0)
                mx = np.asarray(mx, dtype=float)
                mx[~np.isfinite(mx)] = 0.0
                self._maxabs = mx
            except Exception:
                self._maxabs = None

    def _ensure_row_widgets(self, rows: int) -> None:
        rows = int(max(0, rows))
        if int(self.table.rowCount()) < rows:
            _set_table_row_count_if_changed(self.table, rows)
        for r in range(len(self._row_handles), rows):
            it0 = QtWidgets.QTableWidgetItem("")
            it1 = QtWidgets.QTableWidgetItem("")
            it1.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            pb = _PercentBarCanvas(fill_color="#7bd88f")
            pb.setRange(0, 100)
            pb.setTextVisible(True)
            pb.setFormat("%p%")
            it3 = QtWidgets.QTableWidgetItem("")
            it3.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 0, it0)
            self.table.setItem(r, 1, it1)
            self.table.setCellWidget(r, 2, pb)
            self.table.setItem(r, 3, it3)
            self._row_handles.append((it0, it1, pb, it3))
            self._row_binding_keys.append(None)

    def _set_visible_rows(self, rows: int) -> None:
        target = int(max(0, rows))
        current = int(max(0, getattr(self, "_visible_rows", 0)))
        if target == current:
            return
        if target > current:
            for r in range(current, target):
                _set_table_row_hidden_if_changed(self.table, r, False)
        else:
            for r in range(target, current):
                _set_table_row_hidden_if_changed(self.table, r, True)
        self._visible_rows = target

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if getattr(b, "q", None) is None or self._idxs is None or not self._names:
            if self._last_display_key == tuple() and int(getattr(self, "_visible_rows", 0)) == 0:
                return
            self._last_display_key = tuple()
            _call_with_qt_update_batch(self.table, lambda: self._set_visible_rows(0))
            return

        # thr is in g/s in UI
        thr_gs = float(self.thr.value())
        thr = thr_gs / 1000.0  # kg/s
        topn = int(self.topn.value())
        only_active = bool(self.chk_active.isChecked())

        try:
            sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
                np.asarray(b.t, dtype=float),
                sample_t=sample_t,
                fallback_index=i,
            )
            i0 = int(sample_i0)
            i1 = int(sample_i1)
            a = float(alpha)
            if i0 == i1 or a <= 1e-12:
                q = np.asarray(b.q.values[i0, self._idxs], dtype=float)
            elif a >= 1.0 - 1e-12:
                q = np.asarray(b.q.values[i1, self._idxs], dtype=float)
            else:
                q0 = np.asarray(b.q.values[i0, self._idxs], dtype=float)
                q1 = np.asarray(b.q.values[i1, self._idxs], dtype=float)
                q = q0 + (q1 - q0) * a
        except Exception:
            if self._last_display_key == tuple() and int(getattr(self, "_visible_rows", 0)) == 0:
                return
            self._last_display_key = tuple()
            _call_with_qt_update_batch(self.table, lambda: self._set_visible_rows(0))
            return

        aq = np.abs(q)
        order = _top_descending_indices(aq, topn, threshold=(thr if only_active else -1.0))
        if order.size == 0:
            if self._last_display_key == tuple() and int(getattr(self, "_visible_rows", 0)) == 0:
                return
            self._last_display_key = tuple()
            _call_with_qt_update_batch(self.table, lambda: self._set_visible_rows(0))
            return

        idxs = np.asarray(order, dtype=int)
        sel_q = q[idxs]
        sel_aq = aq[idxs]
        frac_pct = np.zeros(int(idxs.size), dtype=int)
        for pos, j in enumerate(idxs.tolist()):
            denom = 0.0
            if self._maxabs is not None and int(j) < int(self._maxabs.size):
                denom = float(self._maxabs[int(j)])
            frac = 0.0 if denom <= 1e-12 else float(sel_aq[pos] / denom)
            frac_pct[pos] = int(np.rint(np.clip(frac, 0.0, 1.0) * 100.0))

        value_centigs = np.asarray(np.rint(sel_q * 100000.0), dtype=int)
        visual_key = tuple((int(j), int(value_centigs[pos]), int(frac_pct[pos])) for pos, j in enumerate(idxs.tolist()))
        if visual_key == self._last_display_key and int(self.table.rowCount()) == int(idxs.size):
            return
        self._last_display_key = visual_key

        def _apply_rows() -> None:
            self._ensure_row_widgets(int(idxs.size))
            for r in range(int(idxs.size)):
                j = int(idxs[r])
                name = self._names[j]
                mdot = float(sel_q[r])
                kind = self._kinds[j] if j < len(self._kinds) else "other"
                it0, it1, pb, it3 = self._row_handles[r]
                if self._row_binding_keys[r] != j:
                    _set_table_item_text_if_changed(it0, name)
                    _set_table_item_text_if_changed(it3, kind)
                    self._row_binding_keys[r] = j
                arrow = "→" if mdot >= 0.0 else "←"
                txt = f"{arrow} {mdot*1000.0:+.2f} g/s"
                _set_table_item_text_if_changed(it1, txt)
                _set_progress_value_if_changed(pb, int(frac_pct[r]))
            self._set_visible_rows(int(idxs.size))

        _call_with_qt_update_batch(self.table, _apply_rows)


class _PressureQuickGridCanvas(QtWidgets.QWidget):
    """Lightweight 2x2 pressure quick cards."""

    def __init__(self, *, nodes: Sequence[str], max_bar_g: float = 12.0, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._nodes = [str(x) for x in nodes]
        self._max_bar_g = float(max_bar_g)
        self._values: Dict[str, Optional[float]] = {str(x): None for x in self._nodes}
        self._display_values: Dict[str, str] = {str(x): "—" for x in self._nodes}
        self._value_static_texts: Dict[str, QtGui.QStaticText] = {str(x): QtGui.QStaticText("—") for x in self._nodes}
        self._values_key: Optional[tuple[tuple[str, Optional[float]], ...]] = None
        self._bg_cache_key: Optional[tuple[int, int]] = None
        self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        self._layout_cache_key: Optional[tuple[int, int]] = None
        self._layout_cache: Dict[str, Any] = {}
        self.setMinimumHeight(86)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self._bg = QtGui.QColor(18, 22, 28)
        self._card_bg = QtGui.QColor(24, 29, 35)
        self._track = QtGui.QColor(42, 48, 56)
        self._border_pen = QtGui.QPen(QtGui.QColor(60, 68, 80), 1.0)
        self._value_font = QtGui.QFont(self.font())
        self._value_text_pen = QtGui.QPen(QtGui.QColor(234, 238, 243))
        try:
            self._border_pen.setCosmetic(True)
            self._value_text_pen.setCosmetic(True)
            self._value_font.setPointSize(max(8, int(self._value_font.pointSize()) - 1))
        except Exception:
            pass
        for text_item in self._value_static_texts.values():
            self._prepare_static_text(text_item)

    def _invalidate_background_cache(self) -> None:
        self._bg_cache_key = None
        self._bg_cache_pixmap = None

    def _prepare_static_text(self, text_item: QtGui.QStaticText) -> None:
        try:
            text_item.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            text_item.prepare(QtGui.QTransform(), self._value_font)
        except Exception:
            pass

    def resizeEvent(self, event: QtGui.QResizeEvent):  # type: ignore[override]
        self._layout_cache_key = None
        self._layout_cache = {}
        self._invalidate_background_cache()
        super().resizeEvent(event)

    def _layout_metrics(self) -> Dict[str, Any]:
        key = (int(self.width()), int(self.height()))
        if key == self._layout_cache_key and self._layout_cache:
            return self._layout_cache

        w = max(1, key[0])
        h = max(1, key[1])
        outer = QtCore.QRectF(0.5, 0.5, max(1.0, float(w) - 1.0), max(1.0, float(h) - 1.0))
        cols = 2
        rows = max(1, int(math.ceil(float(len(self._nodes)) / float(cols))))
        gap = 6.0
        card_w = max(40.0, (outer.width() - gap * (cols - 1)) / cols)
        card_h = max(34.0, (outer.height() - gap * (rows - 1)) / rows)

        cards: list[dict[str, Any]] = []
        for idx, node in enumerate(self._nodes):
            r = idx // cols
            c = idx % cols
            card = QtCore.QRectF(
                outer.left() + c * (card_w + gap),
                outer.top() + r * (card_h + gap),
                card_w,
                card_h,
            )
            cards.append(
                {
                    "node": str(node),
                    "card": card,
                    "title_rect": QtCore.QRectF(card.left() + 8.0, card.top() + 4.0, card.width() - 16.0, 14.0),
                    "value_rect": QtCore.QRectF(card.left() + 8.0, card.top() + 18.0, card.width() - 16.0, 14.0),
                    "value_pos": QtCore.QPointF(
                        card.left() + 8.0,
                        card.top() + 18.0 + max(0.0, (14.0 - float(QtGui.QFontMetrics(self._value_font).height())) * 0.5),
                    ),
                    "bar_rect": QtCore.QRectF(card.left() + 8.0, card.bottom() - 12.0, card.width() - 16.0, 7.0),
                }
            )

        self._layout_cache_key = key
        self._layout_cache = {"w": w, "h": h, "cards": cards}
        return self._layout_cache

    def _ensure_background_cache(self) -> tuple[Optional[QtGui.QPixmap], Dict[str, Any]]:
        metrics = self._layout_metrics()
        key = (int(metrics["w"]), int(metrics["h"]))
        if key == self._bg_cache_key and self._bg_cache_pixmap is not None:
            return self._bg_cache_pixmap, metrics

        dpr = 1.0
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        pix = QtGui.QPixmap(int(max(1.0, float(metrics["w"]) * dpr)), int(max(1.0, float(metrics["h"]) * dpr)))
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(self._bg)

        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        title_font = p.font()
        try:
            title_font.setPointSize(max(8, int(title_font.pointSize()) - 1))
            title_font.setBold(True)
        except Exception:
            pass
        p.setFont(title_font)
        p.setPen(QtGui.QColor(214, 220, 228))
        for info in metrics["cards"]:
            card = info["card"]
            p.setPen(self._border_pen)
            p.setBrush(self._card_bg)
            p.drawRoundedRect(card, 7.0, 7.0)
            p.drawText(
                info["title_rect"],
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                str(info["node"]),
            )
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(self._track)
            p.drawRoundedRect(info["bar_rect"], 3.5, 3.5)
        p.end()

        self._bg_cache_key = key
        self._bg_cache_pixmap = pix
        return self._bg_cache_pixmap, metrics

    def set_values(self, values: Dict[str, Optional[float]]) -> None:
        normalized = []
        display_values: Dict[str, str] = {}
        for node in self._nodes:
            val = values.get(str(node))
            if val is None:
                normalized.append((str(node), None))
                display_values[str(node)] = "—"
            else:
                try:
                    rounded = round(float(val), 2)
                    normalized.append((str(node), rounded))
                    display_values[str(node)] = f"{rounded:.2f} bar(g)"
                except Exception:
                    normalized.append((str(node), None))
                    display_values[str(node)] = "—"
        key = tuple(normalized)
        if key == self._values_key:
            return
        self._values = {node: val for node, val in normalized}
        self._display_values = display_values
        for node, text in display_values.items():
            text_item = self._value_static_texts.get(str(node))
            if text_item is None:
                text_item = QtGui.QStaticText(str(text))
                self._value_static_texts[str(node)] = text_item
            else:
                try:
                    if text_item.text() != str(text):
                        text_item.setText(str(text))
                except Exception:
                    text_item.setText(str(text))
            self._prepare_static_text(text_item)
        self._values_key = key
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        bg_pixmap, metrics = self._ensure_background_cache()
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        if bg_pixmap is not None:
            p.drawPixmap(0, 0, bg_pixmap)
        else:
            p.fillRect(self.rect(), self._bg)
        p.setFont(self._value_font)
        p.setPen(self._value_text_pen)
        for info in metrics.get("cards", []):
            node = str(info.get("node", ""))
            val = self._values.get(node)
            text_item = self._value_static_texts.get(node)
            if text_item is not None:
                p.drawStaticText(info["value_pos"], text_item)

            bar_rect = info["bar_rect"]
            if val is not None and np.isfinite(float(val)):
                frac = float(_clamp(float(val), 0.0, self._max_bar_g) / max(1.0, self._max_bar_g))
                if frac > 1e-6:
                    fill_rect = QtCore.QRectF(bar_rect)
                    fill_rect.setWidth(max(1.0, bar_rect.width() * frac))
                    grad = QtGui.QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
                    grad.setColorAt(0.0, QtGui.QColor(63, 163, 77))
                    grad.setColorAt(0.65, QtGui.QColor(246, 194, 68))
                    grad.setColorAt(1.0, QtGui.QColor(217, 83, 79))
                    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
                    p.setPen(QtCore.Qt.NoPen)
                    p.setBrush(QtGui.QBrush(grad))
                    p.drawRoundedRect(fill_rect, 3.5, 3.5)
                    p.setRenderHint(QtGui.QPainter.Antialiasing, False)
                    p.setPen(self._value_text_pen)


class PressureQuickPanel(QtWidgets.QWidget):
    """Pinned mini-panel: only key node pressures (no tables).

    Goal: keep *always-visible* pneumatics feedback near animation without scrolling.
    """

    KEY_NODES = PressurePanel.KEY_NODES

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.canvas = _PressureQuickGridCanvas(nodes=self.KEY_NODES, max_bar_g=12.0, parent=self)
        lay.addWidget(self.canvas)
        self._bundle_key: Optional[int] = None
        self._pressure_series_map: Dict[str, np.ndarray] = {}
        self._main_p_map = {
            "Ресивер1": "давление_ресивер1_Па",
            "Ресивер2": "давление_ресивер2_Па",
            "Ресивер3": "давление_ресивер3_Па",
            "Аккумулятор": "давление_аккумулятор_Па",
        }
        self._patm_arr: Optional[np.ndarray] = None
        self._patm_default_pa: float = float(PATM_PA_DEFAULT)
        self._compact_mode = False

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(self._compact_mode):
            return
        self._compact_mode = compact
        try:
            self.canvas.setMinimumHeight(72 if compact else 86)
            self.canvas.setMaximumHeight(78 if compact else 16777215)
            self.setMaximumHeight(82 if compact else 16777215)
        except Exception:
            pass
        try:
            self.updateGeometry()
        except Exception:
            pass

    def set_bundle(self, b: DataBundle):
        self._bundle_key = id(b)
        self._pressure_series_map = {}
        self._patm_arr, self._patm_default_pa = _infer_patm_source(b)
        if b.p is not None:
            for node in self.KEY_NODES:
                if b.p.has(node):
                    try:
                        self._pressure_series_map[str(node)] = np.asarray(b.p.column(node), dtype=float).reshape(-1)
                    except Exception:
                        pass
        else:
            for node, col in self._main_p_map.items():
                if b.main.has(col):
                    try:
                        self._pressure_series_map[str(node)] = np.asarray(b.get(col, 0.0), dtype=float).reshape(-1)
                    except Exception:
                        pass


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b):
            self.set_bundle(b)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))
        patm = sample(self._patm_arr, self._patm_default_pa)
        values: Dict[str, Optional[float]] = {}
        for node in self.KEY_NODES:
            arr = self._pressure_series_map.get(str(node))
            if arr is None:
                values[str(node)] = None
                continue
            try:
                P = sample(arr, float("nan"))
                values[str(node)] = float((P - patm) / BAR_PA) if np.isfinite(P) else None
            except Exception:
                values[str(node)] = None
        self.canvas.set_values(values)


class _ReceiverTankCanvas(QtWidgets.QWidget):
    """A compact receiver tank gauge.

    Visual idea:
      - "liquid" fill level ~ pressure (bar g)
      - marker lines (user-defined)
      - inlet/outlet pipes with "balls" sized by inflow/outflow
    """

    DEFAULT_MARKERS_BAR = (2.0, 4.0, 6.0, 8.0)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(150)
        self.setMinimumHeight(170)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

        self._p_name: Optional[str] = None
        self._p_bar_g: Optional[float] = None
        self._p_max_bar_g: float = 10.0
        self._p_series_map: Dict[str, np.ndarray] = {}
        self._p_series_arr: Optional[np.ndarray] = None
        self._p_max_map: Dict[str, float] = {}
        self._markers_bar = list(self.DEFAULT_MARKERS_BAR)

        self._q_in_arr: Optional[np.ndarray] = None
        self._q_out_arr: Optional[np.ndarray] = None
        self._q_name_map: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        self._q_ref: float = 0.02  # kg/s (20 g/s)
        self._q_in: float = 0.0
        self._q_out: float = 0.0

        # Smoothed 0..1 flow indicators (for internal "float" markers)
        self._u_in: float = 0.0
        self._u_out: float = 0.0

        self._bundle_key: Optional[int] = None
        self._patm_arr: Optional[np.ndarray] = None
        self._patm_default_pa: float = float(PATM_PA_DEFAULT)
        self._last_visual_key: Optional[tuple[int, int, int, int, int, int]] = None
        self._main_p_map = {
            "Ресивер1": "давление_ресивер1_Па",
            "Ресивер2": "давление_ресивер2_Па",
            "Ресивер3": "давление_ресивер3_Па",
            "Аккумулятор": "давление_аккумулятор_Па",
        }
        self._bg_cache_key: Optional[tuple[int, int, float, tuple[float, ...]]] = None
        self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        self._layout_cache_key: Optional[tuple[int, int]] = None
        self._layout_cache: Dict[str, Any] = {}
        self._tank_pen = QtGui.QPen(QtGui.QColor(220, 220, 220), 2)
        self._dash_pen = QtGui.QPen(QtGui.QColor(200, 200, 200, 150), 1, QtCore.Qt.DashLine)
        self._pipe_pen = QtGui.QPen(QtGui.QColor(220, 220, 220), 2)
        self._track_pen = QtGui.QPen(QtGui.QColor(220, 220, 220, 120), 1)
        self._text_pen = QtGui.QPen(QtGui.QColor(240, 240, 240), 1)
        self._marker_active_pen = QtGui.QPen(QtGui.QColor(230, 190, 90, 230), 2)
        self._marker_active_brush = QtGui.QBrush(QtGui.QColor(230, 190, 90, 230))
        self._flow_in_brush = QtGui.QBrush(QtGui.QColor(80, 220, 120, 230))
        self._flow_out_brush = QtGui.QBrush(QtGui.QColor(240, 90, 90, 230))
        self._pipe_in_brush = QtGui.QBrush(QtGui.QColor(80, 220, 120, 220))
        self._pipe_out_brush = QtGui.QBrush(QtGui.QColor(240, 90, 90, 220))
        self._text_font = QtGui.QFont(self.font())
        self._pressure_static_text = QtGui.QStaticText("P: —")
        self._flow_static_text = QtGui.QStaticText("in:   0.0 g/s\nout:  0.0 g/s")
        for pen in (self._tank_pen, self._dash_pen, self._pipe_pen, self._track_pen, self._text_pen, self._marker_active_pen):
            try:
                pen.setCosmetic(True)
            except Exception:
                pass
        try:
            self._text_pen.setCosmetic(True)
            self._text_font.setPointSize(max(8, int(self._text_font.pointSize()) - 1))
        except Exception:
            pass
        self._prepare_static_text(self._pressure_static_text)
        self._prepare_static_text(self._flow_static_text)

    def _prepare_static_text(self, text_item: QtGui.QStaticText) -> None:
        try:
            text_item.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            text_item.prepare(QtGui.QTransform(), self._text_font)
        except Exception:
            pass

    def _set_static_text_if_changed(self, text_item: QtGui.QStaticText, text: str) -> None:
        target = str(text)
        try:
            if text_item.text() == target:
                return
        except Exception:
            pass
        text_item.setText(target)
        self._prepare_static_text(text_item)

    @staticmethod
    def _normalize_flow_edge_name(name: str) -> str:
        s = str(name).lower()
        for old_ch, new_ch in {
            "‑": "-",
            "–": "-",
            "—": "-",
            "−": "-",
            "→": "->",
            " ": "_",
        }.items():
            s = s.replace(old_ch, new_ch)
        while "__" in s:
            s = s.replace("__", "_")
        return s

    @classmethod
    def _classify_receiver_flow_orientation(cls, receiver_name: str, edge_name: str) -> Optional[str]:
        """Return 'in'/'out' for a flow edge relative to the selected receiver/tank.

        We only classify edges when the direction is explicit in the edge name.
        Examples:
          - '...-в-Ресивер1'  -> inflow to Ресивер1
          - 'Ресивер1-в-...'  -> outflow from Ресивер1
          - 'Ресивер2-из-Аккумулятор' -> inflow to Ресивер2
          - '...-из-Ресивер3' -> outflow from Ресивер3
        """
        token = cls._normalize_flow_edge_name(receiver_name)
        edge = cls._normalize_flow_edge_name(edge_name)
        if token not in edge:
            return None

        incoming_patterns = (
            f"-в-{token}",
            f"_в_{token}",
            f"->{token}",
            f"-{token}-из-",
            f"_{token}_из_",
        )
        outgoing_patterns = (
            f"{token}-в-",
            f"{token}_в_",
            f"{token}->",
            f"-из-{token}",
            f"_из_{token}",
        )
        inc = any(p in edge for p in incoming_patterns)
        out = any(p in edge for p in outgoing_patterns)
        if inc and not out:
            return "in"
        if out and not inc:
            return "out"
        return None

    @classmethod
    def _build_receiver_flow_arrays(cls, b: DataBundle, receiver_name: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        if b.q is None:
            return None
        try:
            cols = list(b.q.cols)
            token = str(receiver_name)
            cols_sel = [c for c in cols if token.lower() in str(c).lower()]
            if not cols_sel:
                return None
            n = len(b.t)
            q_in = np.zeros(n, dtype=float)
            q_out = np.zeros(n, dtype=float)
            classified = 0
            for c in cols_sel:
                orient = cls._classify_receiver_flow_orientation(token, str(c))
                if orient is None:
                    continue
                a = np.asarray(b.q.column(c), dtype=float)
                if orient == "in":
                    q_in += np.clip(a, 0.0, None)
                    q_out += np.clip(-a, 0.0, None)
                else:
                    q_in += np.clip(-a, 0.0, None)
                    q_out += np.clip(a, 0.0, None)
                classified += 1
            if classified <= 0:
                return None
            return q_in, q_out
        except Exception:
            return None

    def set_pressure_name(self, name: Optional[str]):
        next_name = str(name) if name else None
        self._p_name = next_name
        if next_name is not None:
            self._p_series_arr = self._p_series_map.get(next_name)
            pair = self._q_name_map.get(next_name)
        else:
            self._p_series_arr = None
            pair = None
        if pair is not None:
            self._q_in_arr, self._q_out_arr = pair
        else:
            self._q_in_arr = None
            self._q_out_arr = None
        self._p_max_bar_g = float(self._p_max_map.get(str(next_name), 10.0))
        self._p_bar_g = None
        self._q_in = 0.0
        self._q_out = 0.0
        self._u_in = 0.0
        self._u_out = 0.0
        self._last_visual_key = None
        self._invalidate_background_cache()

    def _pressure_max_for_series(self, series_pa: np.ndarray) -> float:
        arr = np.asarray(series_pa, dtype=float).reshape(-1)
        if arr.size == 0:
            return 10.0
        if self._patm_arr is not None and self._patm_arr.size:
            n = int(min(arr.size, self._patm_arr.size))
            patm = np.asarray(self._patm_arr[:n], dtype=float)
            valid_patm = np.isfinite(patm) & (np.abs(patm) > 1.0)
            patm = np.where(valid_patm, patm, float(self._patm_default_pa))
            gauge_bar = (arr[:n] - patm) / BAR_PA
        else:
            gauge_bar = (arr - float(self._patm_default_pa)) / BAR_PA
        finite = gauge_bar[np.isfinite(gauge_bar)]
        if finite.size <= 0:
            return 10.0
        p99 = float(np.nanpercentile(finite, 99))
        return float(max(10.0, math.ceil(max(0.0, p99) + 0.5)))

    def set_markers_bar(self, markers: Sequence[float]):
        try:
            vals = [float(x) for x in markers]
            vals = [x for x in vals if x > -1e-6]
            self._markers_bar = vals[:8]
        except Exception:
            self._markers_bar = list(self.DEFAULT_MARKERS_BAR)
        self._invalidate_background_cache()
        self.update()

    def _invalidate_background_cache(self) -> None:
        self._bg_cache_key = None
        self._bg_cache_pixmap = None

    def resizeEvent(self, event: QtGui.QResizeEvent):  # type: ignore[override]
        self._layout_cache_key = None
        self._layout_cache = {}
        self._invalidate_background_cache()
        super().resizeEvent(event)

    def _layout_metrics(self) -> Dict[str, Any]:
        key = (int(self.width()), int(self.height()))
        if key == self._layout_cache_key and self._layout_cache:
            return self._layout_cache

        w = max(1, key[0])
        h = max(1, key[1])
        m = 10
        tank_w = max(40, int(0.34 * w))
        tank_h = max(90, int(0.72 * h))
        tx = int(0.5 * (w - tank_w))
        ty = m
        tank = QtCore.QRectF(tx, ty, tank_w, tank_h)
        pipe_len = max(18, int(0.22 * w))
        in_y = tank.top() + 0.22 * tank.height()
        out_y = tank.bottom() - 0.18 * tank.height()
        in_a = QtCore.QPointF(tank.right(), in_y)
        in_b = QtCore.QPointF(tank.right() + pipe_len, in_y)
        out_a = QtCore.QPointF(tank.left(), out_y)
        out_b = QtCore.QPointF(tank.left() - pipe_len, out_y)
        x_mid = tank.center().x()
        dx = 0.18 * tank.width()
        xin = x_mid - dx
        xout = x_mid + dx
        marker_layout: list[dict[str, Any]] = []
        max_bar = max(1e-6, float(self._p_max_bar_g))
        for idx, mk in enumerate(self._markers_bar):
            if mk < 0:
                continue
            mk_u = float(mk) / max_bar
            y = tank.bottom() - mk_u * tank.height()
            if not (tank.top() <= y <= tank.bottom()):
                continue
            side = 1.0 if (idx % 2 == 0) else -1.0
            if abs(y - in_y) < 0.07 * tank.height():
                side = -1.0
            if abs(y - out_y) < 0.07 * tank.height():
                side = 1.0
            stub_len = max(14.0, min(26.0, 0.22 * float(w)))
            if side > 0:
                a = QtCore.QPointF(tank.right(), y)
                bpt = QtCore.QPointF(tank.right() + stub_len, y)
            else:
                a = QtCore.QPointF(tank.left(), y)
                bpt = QtCore.QPointF(tank.left() - stub_len, y)
            marker_layout.append({"mk": float(mk), "y": float(y), "a": a, "b": bpt})

        self._layout_cache_key = key
        self._layout_cache = {
            "w": w,
            "h": h,
            "tank": tank,
            "in_a": in_a,
            "in_b": in_b,
            "out_a": out_a,
            "out_b": out_b,
            "xin": xin,
            "xout": xout,
            "markers": marker_layout,
        }
        return self._layout_cache

    def _ensure_background_cache(self) -> tuple[Optional[QtGui.QPixmap], Dict[str, Any]]:
        metrics = self._layout_metrics()
        key = (
            int(metrics["w"]),
            int(metrics["h"]),
            round(float(self._p_max_bar_g), 3),
            tuple(round(float(x), 3) for x in self._markers_bar),
        )
        if key == self._bg_cache_key and self._bg_cache_pixmap is not None:
            return self._bg_cache_pixmap, metrics

        pix = QtGui.QPixmap(int(metrics["w"]), int(metrics["h"]))
        pix.fill(QtGui.QColor(18, 18, 18))
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        tank = metrics["tank"]
        p.setPen(self._tank_pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(tank, 6, 6)

        p.setPen(self._dash_pen)
        inactive_col = QtGui.QColor(140, 140, 140, 160)
        for info in metrics["markers"]:
            y = float(info["y"])
            p.drawLine(QtCore.QPointF(tank.left(), y), QtCore.QPointF(tank.right(), y))
            p.setPen(QtGui.QPen(inactive_col, 2))
            try:
                p.pen().setCosmetic(True)
            except Exception:
                pass
            p.drawLine(info["a"], info["b"])
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(inactive_col)
            p.drawEllipse(info["b"], 4.0, 4.0)
            p.setPen(self._dash_pen)

        p.setPen(self._pipe_pen)
        p.drawLine(metrics["in_a"], metrics["in_b"])
        p.drawLine(metrics["out_a"], metrics["out_b"])

        p.setPen(self._track_pen)
        p.drawLine(QtCore.QPointF(float(metrics["xin"]), tank.bottom()), QtCore.QPointF(float(metrics["xin"]), tank.top()))
        p.drawLine(QtCore.QPointF(float(metrics["xout"]), tank.bottom()), QtCore.QPointF(float(metrics["xout"]), tank.top()))
        p.end()

        self._bg_cache_key = key
        self._bg_cache_pixmap = pix
        return self._bg_cache_pixmap, metrics

    def set_bundle(self, b: DataBundle):
        self._bundle_key = id(b)
        self._patm_arr, self._patm_default_pa = _infer_patm_source(b)
        self._p_series_map = {}
        self._p_series_arr = None
        self._p_max_map = {}
        self._q_in_arr = None
        self._q_out_arr = None
        self._q_name_map = {}
        self._q_ref = 0.02
        self._last_visual_key = None

        # Precompute per-receiver classified flow magnitudes once (for stable ball scaling).
        # If the edge direction cannot be classified unambiguously from the canonical edge name,
        # we prefer to omit it rather than invent a misleading mnemonic.
        try:
            candidate_names = list(self._main_p_map.keys())
            q_max = []
            for name in candidate_names:
                pair = self._build_receiver_flow_arrays(b, name)
                if pair is None:
                    continue
                q_in, q_out = pair
                self._q_name_map[str(name)] = (q_in, q_out)
                q_max.append(np.maximum(q_in, q_out))
            if self._q_name_map:
                sel_name = str(self._p_name) if self._p_name else next(iter(self._q_name_map.keys()))
                self._q_in_arr, self._q_out_arr = self._q_name_map.get(sel_name, next(iter(self._q_name_map.values())))
                if q_max:
                    q_stack = np.concatenate([np.asarray(x, dtype=float).ravel() for x in q_max])
                    q95 = float(np.nanpercentile(q_stack, 95)) if q_stack.size else 0.02
                    self._q_ref = max(1e-6, q95)
        except Exception:
            self._q_name_map = {}
            self._q_in_arr = None
            self._q_out_arr = None
            self._q_ref = 0.02

        try:
            candidate_names: List[str] = list(self._main_p_map.keys())
            if b.p is not None:
                for name in list(b.p.cols):
                    if str(name) == "время_с":
                        continue
                    if str(name) not in candidate_names:
                        candidate_names.append(str(name))
                for name in candidate_names:
                    if b.p.has(name):
                        arr = np.asarray(b.p.column(name), dtype=float).reshape(-1)
                        self._p_series_map[str(name)] = arr
                        self._p_max_map[str(name)] = self._pressure_max_for_series(arr)
            else:
                for name, col in self._main_p_map.items():
                    if b.main.has(col):
                        arr = np.asarray(b.get(col, 0.0), dtype=float).reshape(-1)
                        self._p_series_map[str(name)] = arr
                        self._p_max_map[str(name)] = self._pressure_max_for_series(arr)
        except Exception:
            self._p_series_map = {}
            self._p_max_map = {}

        if self._p_name is None and self._p_series_map:
            self._p_name = next(iter(self._p_series_map.keys()))
        self.set_pressure_name(self._p_name)

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b):
            self.set_bundle(b)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))
        # pressure
        patm = sample(self._patm_arr, self._patm_default_pa)
        p_bar_g: Optional[float] = None
        try:
            if self._p_series_arr is not None:
                P = sample(self._p_series_arr, float("nan"))
                if np.isfinite(P):
                    p_bar_g = (P - patm) / BAR_PA
        except Exception:
            p_bar_g = None
        self._p_bar_g = p_bar_g

        # flows (classified relative to the currently selected receiver/tank)
        try:
            if self._q_in_arr is not None:
                self._q_in = sample(self._q_in_arr, 0.0)
            else:
                self._q_in = 0.0
            if self._q_out_arr is not None:
                self._q_out = sample(self._q_out_arr, 0.0)
            else:
                self._q_out = 0.0
        except Exception:
            self._q_in = 0.0
            self._q_out = 0.0

        # Smooth flow indicators for internal floats
        try:
            qref = max(1e-6, float(self._q_ref))
            tu_in = (max(0.0, self._q_in) / qref) ** 0.5
            tu_out = (max(0.0, self._q_out) / qref) ** 0.5
            tu_in = max(0.0, min(1.0, float(tu_in)))
            tu_out = max(0.0, min(1.0, float(tu_out)))
            a = 0.18  # smoothing factor
            self._u_in = (1.0 - a) * float(self._u_in) + a * tu_in
            self._u_out = (1.0 - a) * float(self._u_out) + a * tu_out
        except Exception:
            self._u_in *= 0.9
            self._u_out *= 0.9

        visual_key = (
            -9999 if p_bar_g is None or not np.isfinite(float(p_bar_g)) else int(round(float(p_bar_g) * 10.0)),
            int(round(max(0.0, float(self._q_in)) * 10000.0)),
            int(round(max(0.0, float(self._q_out)) * 10000.0)),
            int(round(float(_clamp(self._u_in, 0.0, 1.0)) * 100.0)),
            int(round(float(_clamp(self._u_out, 0.0, 1.0)) * 100.0)),
            int(round(float(self._p_max_bar_g) * 10.0)),
        )
        if visual_key == self._last_visual_key:
            return
        self._last_visual_key = visual_key
        if self._p_bar_g is None:
            p_txt = "P: —"
        else:
            p_txt = f"P: {self._p_bar_g:4.1f} бар"
        q_txt = f"in: {self._q_in*1000:5.1f} g/s\nout:{self._q_out*1000:5.1f} g/s"
        self._set_static_text_if_changed(self._pressure_static_text, p_txt)
        self._set_static_text_if_changed(self._flow_static_text, q_txt)
        self.update()

    def paintEvent(self, ev: QtGui.QPaintEvent):  # type: ignore
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        bg_pixmap, metrics = self._ensure_background_cache()
        if bg_pixmap is not None:
            p.drawPixmap(0, 0, bg_pixmap)
        tank = metrics.get("tank", QtCore.QRectF())
        w = int(metrics.get("w", max(1, self.width())))
        h = int(metrics.get("h", max(1, self.height())))

        # fill level (pressure as "liquid")
        frac = 0.0
        if self._p_bar_g is not None and self._p_max_bar_g > 1e-6:
            frac = max(0.0, min(1.0, float(self._p_bar_g) / float(self._p_max_bar_g)))
        fill_h = tank.height() * frac
        fill = QtCore.QRectF(tank.left() + 2.0, tank.bottom() - fill_h + 2.0, tank.width() - 4.0, fill_h - 4.0)
        if fill.height() > 1.0:
            # Pressure heat gradient: bottom=cold, top=hot (at current pressure level)
            cold = QtGui.QColor(*_heat_rgb(0.0), 210)
            hot = QtGui.QColor(*_heat_rgb(frac), 230)
            grad = QtGui.QLinearGradient(fill.bottomLeft(), fill.topLeft())
            grad.setColorAt(0.0, cold)
            grad.setColorAt(1.0, hot)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QBrush(grad))
            p.drawRoundedRect(fill, 5, 5)

        # markers + "outlet" stubs (user-friendly, experience-based metaphor)
        lvl_bar = float(self._p_bar_g) if (self._p_bar_g is not None and np.isfinite(self._p_bar_g)) else -1e9
        for info in metrics.get("markers", []):
            mk = float(info.get("mk", -1.0))
            if lvl_bar < mk - 1e-6:
                continue
            p.setPen(self._marker_active_pen)
            p.drawLine(info["a"], info["b"])
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(self._marker_active_brush)
            p.drawEllipse(info["b"], 4.0, 4.0)

        # Internal flow "floats" (green=in, red=out): map to 0..1 by q_ref
        try:
            xin = float(metrics.get("xin", tank.center().x()))
            xout = float(metrics.get("xout", tank.center().x()))
            yin = tank.bottom() - float(self._u_in) * tank.height()
            yout = tank.bottom() - float(self._u_out) * tank.height()
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(self._flow_in_brush)
            p.drawEllipse(QtCore.QPointF(xin, yin), 4.2, 4.2)
            p.setBrush(self._flow_out_brush)
            p.drawEllipse(QtCore.QPointF(xout, yout), 4.2, 4.2)
        except Exception:
            pass

        # balls sized by flow (pipes)
        qref = max(1e-6, float(self._q_ref))
        rin = 3.0 + 10.0 * (max(0.0, self._q_in) / qref) ** 0.5
        rout = 3.0 + 10.0 * (max(0.0, self._q_out) / qref) ** 0.5
        rin = max(3.0, min(14.0, rin))
        rout = max(3.0, min(14.0, rout))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(self._pipe_in_brush)
        p.drawEllipse(metrics.get("in_b", QtCore.QPointF()), rin, rin)
        p.setBrush(self._pipe_out_brush)
        p.drawEllipse(metrics.get("out_b", QtCore.QPointF()), rout, rout)

        # labels
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        p.setFont(self._text_font)
        p.setPen(self._text_pen)
        try:
            p_w = float(self._pressure_static_text.size().width())
        except Exception:
            p_w = 0.0
        try:
            q_w = float(self._flow_static_text.size().width())
        except Exception:
            q_w = 0.0
        p.drawStaticText(QtCore.QPointF(max(0.0, 0.5 * (float(w) - p_w)), float(tank.bottom() + 6.0)), self._pressure_static_text)
        p.drawStaticText(QtCore.QPointF(max(0.0, 0.5 * (float(w) - q_w)), float(tank.bottom() + 26.0)), self._flow_static_text)


class ReceiverTankWidget(QtWidgets.QWidget):
    """Pinned receiver tank gauge with a small selector."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self.cmb = QtWidgets.QComboBox()
        self.cmb.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.cmb.setToolTip("Источник давления для ресиверного индикатора")
        top.addWidget(QtWidgets.QLabel("ресивер:"))
        top.addWidget(self.cmb, 1)
        lay.addLayout(top)

        self.legend = QtWidgets.QLabel("заливка=P · зелёный=в ресивер · красный=из ресивера · пунктир=пороги")
        try:
            self.legend.setWordWrap(True)
            self.legend.setStyleSheet("color:#c8c8c8; font-size:11px;")
        except Exception:
            pass
        lay.addWidget(self.legend)

        self.canvas = _ReceiverTankCanvas()
        self.canvas.setToolTip(
            "Заливка = давление выбранного ресивера/аккумулятора.\n"
            "Зелёные индикаторы = суммарный расход В выбранный объём по классифицированным рёбрам.\n"
            "Красные индикаторы = суммарный расход ИЗ выбранного объёма.\n"
            "Если направление ребра нельзя понять честно по каноническому имени, оно не включается в мнемосхему."
        )
        lay.addWidget(self.canvas, 1)

        self._bundle_key: Optional[int] = None
        self._names: List[str] = []
        self.cmb.currentIndexChanged.connect(self._on_sel)
        self._compact_mode = False

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(self._compact_mode):
            return
        self._compact_mode = compact
        try:
            self.legend.setVisible(not compact)
        except Exception:
            pass
        try:
            self.canvas.setMinimumHeight(112 if compact else 170)
            self.canvas.setMaximumHeight(124 if compact else 16777215)
            self.setMaximumHeight(154 if compact else 16777215)
        except Exception:
            pass
        try:
            self.updateGeometry()
            self.adjustSize()
        except Exception:
            pass

    def _on_sel(self, idx: int):
        if 0 <= idx < len(self._names):
            self.canvas.set_pressure_name(self._names[idx])
            self.canvas.update()

    def set_bundle(self, b: DataBundle):
        # build candidates
        names: List[str] = []
        if b.p is not None:
            for k in PressureQuickPanel.KEY_NODES:
                if b.p.has(k):
                    names.append(k)
            if not names:
                names = list(b.p.cols)[:8]
        else:
            # fallback to main-mapped columns
            for k, col in self.canvas._main_p_map.items():
                if b.main.has(col):
                    names.append(k)

        if not names:
            names = ["Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор"]

        prev = self.canvas._p_name
        self._names = names
        self.cmb.blockSignals(True)
        self.cmb.clear()
        self.cmb.addItems(names)
        if prev in names:
            self.cmb.setCurrentIndex(names.index(prev))
        else:
            self.cmb.setCurrentIndex(0)
            self.canvas.set_pressure_name(names[0] if names else None)
        self.cmb.blockSignals(False)

        self.canvas.set_bundle(b)

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        self.canvas.update_frame(b, i, sample_t=sample_t)


class ValveQuickPanel(QtWidgets.QWidget):
    """Pinned mini-panel: top active valves (open%) as a compact list."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, max_rows: int = 8, thr: float = 0.05):
        super().__init__(parent)
        self._full_max_rows = int(max(3, max_rows))
        self._compact_max_rows = int(max(3, min(self._full_max_rows, 4)))
        self.max_rows = int(self._full_max_rows)
        self.thr = float(thr)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.header_canvas = _QuickTextStripCanvas(self)
        self.header_canvas.hide()
        lay.addWidget(self.header_canvas)

        self.lbl = QtWidgets.QLabel("Активные клапаны (top):")
        self.lbl.setStyleSheet("color:#cfcfcf;")
        lay.addWidget(self.lbl)

        # Group counters: keep them as plain labels instead of rich-text HTML so
        # docked telemetry stays cheap even when the counts change every frame.
        groups = QtWidgets.QHBoxLayout()
        groups.setContentsMargins(0, 0, 0, 0)
        groups.setSpacing(8)
        self.lbl_exh = QtWidgets.QLabel("выхлоп: —")
        self.lbl_exh.setStyleSheet("color:#ff8a8a;")
        self.lbl_fill = QtWidgets.QLabel("подпитка: —")
        self.lbl_fill.setStyleSheet("color:#9fe3a8;")
        self.lbl_charge = QtWidgets.QLabel("заряд: —")
        self.lbl_charge.setStyleSheet("color:#f6d57a;")
        groups.addWidget(self.lbl_exh)
        groups.addWidget(self.lbl_fill)
        groups.addWidget(self.lbl_charge)
        groups.addStretch(1)
        lay.addLayout(groups)

        self.rows_canvas = _QuickBarListCanvas(
            max_rows=self.max_rows,
            bar_color=QtGui.QColor(74, 163, 223),
            parent=self,
        )
        lay.addWidget(self.rows_canvas)

        self._names: list[str] = []
        self._short_names: list[str] = []
        self._kinds: list[str] = []
        self._kind_codes = np.zeros((0,), dtype=np.int8)
        self._idxs: np.ndarray | None = None
        self._compact_mode = False

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(self._compact_mode):
            return
        self._compact_mode = compact
        self.max_rows = int(self._compact_max_rows if compact else self._full_max_rows)
        self.rows_canvas.max_rows = int(self.max_rows)
        self.rows_canvas.setMinimumHeight(int(8 + self.max_rows * 18))
        try:
            self.setMaximumHeight(138 if compact else 16777215)
        except Exception:
            pass
        try:
            self.header_canvas.setVisible(compact)
            self.lbl.setVisible(not compact)
            self.lbl_exh.setVisible(not compact)
            self.lbl_fill.setVisible(not compact)
            self.lbl_charge.setVisible(not compact)
        except Exception:
            pass
        self.rows_canvas.clear_rows()
        try:
            self.updateGeometry()
        except Exception:
            pass

    def set_bundle(self, b: DataBundle):
        self._names = []
        self._short_names = []
        self._kinds = []
        self._kind_codes = np.zeros((0,), dtype=np.int8)
        self._idxs = None
        if b.open is None:
            return
        cols = [c for c in b.open.cols if c not in ("время_с",)]
        idxs = []
        names = []
        short_names = []
        kinds = []
        kind_codes = []
        for c in cols:
            j = b.open.index_of(c)
            if j is None:
                continue
            name = str(c)
            kind = _infer_valve_kind(name)
            idxs.append(int(j))
            names.append(name)
            short_names.append(_shorten_display_name(name))
            kinds.append(kind)
            kind_codes.append(_kind_code_from_label(kind))
        if idxs:
            self._idxs = np.array(idxs, dtype=int)
            self._names = names
            self._short_names = short_names
            self._kinds = kinds
            self._kind_codes = np.asarray(kind_codes, dtype=np.int8)


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        # default: clear
        def _clear():
            self.header_canvas.set_segments(
                [
                    ("top: —", QtGui.QColor(207, 207, 207)),
                    ("вых: —", QtGui.QColor(255, 138, 138)),
                    ("подп: —", QtGui.QColor(159, 227, 168)),
                    ("зар: —", QtGui.QColor(246, 213, 122)),
                ]
            )
            _set_label_text_if_changed(self.lbl, "Активные клапаны (top): —")
            _set_label_text_if_changed(self.lbl_exh, "выхлоп: —")
            _set_label_text_if_changed(self.lbl_fill, "подпитка: —")
            _set_label_text_if_changed(self.lbl_charge, "заряд: —")
            self.rows_canvas.clear_rows()
            return

        if b.open is None or self._idxs is None or not self._names:
            _clear()
            return

        try:
            sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
                np.asarray(b.t, dtype=float),
                sample_t=sample_t,
                fallback_index=i,
            )
            i0 = int(sample_i0)
            i1 = int(sample_i1)
            a = float(alpha)
            if i0 == i1 or a <= 1e-12:
                vals = np.asarray(b.open.values[i0, self._idxs], dtype=float)
            elif a >= 1.0 - 1e-12:
                vals = np.asarray(b.open.values[i1, self._idxs], dtype=float)
            else:
                vals0 = np.asarray(b.open.values[i0, self._idxs], dtype=float)
                vals1 = np.asarray(b.open.values[i1, self._idxs], dtype=float)
                vals = vals0 + (vals1 - vals0) * a
        except Exception:
            _clear()
            return

        thr = float(self.thr)
        active_mask = vals > thr
        if not np.any(active_mask):
            _clear()
            return

        # Group counters across ALL active valves (not just the top list)
        if self._kind_codes.size == vals.size:
            active_codes = self._kind_codes[active_mask]
            exh_count = int(np.count_nonzero(active_codes == 0))
            fill_count = int(np.count_nonzero(active_codes == 1))
            charge_count = int(np.count_nonzero(active_codes == 2))
        else:
            exh_count = fill_count = charge_count = 0
        self.header_canvas.set_segments(
            [
                (f"top {int(np.count_nonzero(active_mask))}", QtGui.QColor(207, 207, 207)),
                (f"вых:{exh_count}", QtGui.QColor(255, 138, 138)),
                (f"подп:{fill_count}", QtGui.QColor(159, 227, 168)),
                (f"зар:{charge_count}", QtGui.QColor(246, 213, 122)),
            ]
        )
        _set_label_text_if_changed(self.lbl_exh, f"выхлоп: {exh_count}")
        _set_label_text_if_changed(self.lbl_fill, f"подпитка: {fill_count}")
        _set_label_text_if_changed(self.lbl_charge, f"заряд: {charge_count}")

        idxs = _top_descending_indices(vals, self.max_rows, threshold=thr)
        sel_vals = vals[idxs] if idxs.size else np.zeros((0,), dtype=float)

        _set_label_text_if_changed(self.lbl, f"Активные клапаны (top {int(idxs.size)}):")
        rows_data: list[tuple[str, float, str]] = []
        for row_i, j in enumerate(idxs.tolist()):
            j = int(j)
            nm = self._short_names[j] if j < len(self._short_names) else _shorten_display_name(self._names[j])
            v = float(sel_vals[row_i])
            kind = self._kinds[j] if j < len(self._kinds) else _infer_valve_kind(self._names[j])
            rows_data.append((nm, float(_clamp(v, 0.0, 1.0)), kind))
        self.rows_canvas.set_rows(rows_data)

class _HeatCell(QtWidgets.QWidget):
    def __init__(self, corner: str):
        super().__init__()
        self.corner = str(corner)
        self.setObjectName(f"heatCell_{corner}")
        self.setMinimumSize(92, 54)
        self.setMaximumHeight(60)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self._value_text = "--"
        self._style_key: Optional[tuple[int, int, int, int, int, int]] = None
        self._bg_color = QtGui.QColor(40, 40, 40)
        self._fg_color = QtGui.QColor(235, 235, 235)
        self._border_color = QtGui.QColor(26, 28, 34, 150)
        self._border_pen = QtGui.QPen(self._border_color, 1.0)
        self._fg_pen = QtGui.QPen(self._fg_color, 1.0)
        self._bg_brush = QtGui.QBrush(self._bg_color)
        self._corner_font = QtGui.QFont(self.font())
        self._value_font = QtGui.QFont(self.font())
        self._corner_static_text = QtGui.QStaticText(self.corner)
        self._value_static_text = QtGui.QStaticText(self._value_text)
        self._layout_key: Optional[tuple[int, int]] = None
        self._frame_rect = QtCore.QRectF()
        self._corner_pos = QtCore.QPointF()
        self._value_pos = QtCore.QPointF()
        self._bg_cache_key: Optional[tuple[int, int, int, int, int, int]] = None
        self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        try:
            self._corner_font.setBold(True)
            self._corner_font.setPointSize(max(8, int(self._corner_font.pointSize())))
            self._value_font.setBold(False)
            self._value_font.setPointSize(max(8, int(self._value_font.pointSize()) - 1))
            self._value_font.setFamilies(["Consolas", "Menlo", "DejaVu Sans Mono"])
            self._border_pen.setCosmetic(True)
            self._fg_pen.setCosmetic(True)
        except Exception:
            pass
        self._prepare_static_text(self._corner_static_text, self._corner_font)
        self._prepare_static_text(self._value_static_text, self._value_font)

    @staticmethod
    def _prepare_static_text(text_item: QtGui.QStaticText, font: QtGui.QFont) -> None:
        try:
            text_item.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            text_item.prepare(QtGui.QTransform(), font)
        except Exception:
            pass

    def resizeEvent(self, event: QtGui.QResizeEvent):  # type: ignore[override]
        self._layout_key = None
        self._frame_rect = QtCore.QRectF()
        self._bg_cache_key = None
        self._bg_cache_pixmap = None
        super().resizeEvent(event)

    def _ensure_layout(self) -> None:
        key = (int(max(1, self.width())), int(max(1, self.height())))
        if key == self._layout_key:
            return
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        corner_h = float(QtGui.QFontMetrics(self._corner_font).height())
        value_h = float(QtGui.QFontMetrics(self._value_font).height())
        self._corner_pos = QtCore.QPointF(rect.left() + 8.0, rect.top() + 6.0 + max(0.0, (16.0 - corner_h) * 0.5))
        value_top = rect.top() + 24.0 + max(0.0, ((rect.height() - 30.0) - value_h) * 0.5)
        self._value_pos = QtCore.QPointF(rect.left() + 8.0, value_top)
        self._frame_rect = rect
        self._layout_key = key

    def _ensure_background_cache(self) -> Optional[QtGui.QPixmap]:
        w = int(max(1, self.width()))
        h = int(max(1, self.height()))
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        key = (
            w,
            h,
            int(round(dpr * 100.0)),
            int(self._bg_color.red()),
            int(self._bg_color.green()),
            int(self._bg_color.blue()),
        )
        if key == self._bg_cache_key and self._bg_cache_pixmap is not None:
            return self._bg_cache_pixmap
        pix = QtGui.QPixmap(int(max(1.0, float(w) * dpr)), int(max(1.0, float(h) * dpr)))
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(self._border_pen)
        p.setBrush(QtGui.QBrush(self._bg_color))
        p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, max(1.0, float(w) - 1.0), max(1.0, float(h) - 1.0)), 8.0, 8.0)
        p.end()
        self._bg_cache_key = key
        self._bg_cache_pixmap = pix
        return self._bg_cache_pixmap

    def set_value(self, value: float, *, text: str, u: float):
        rgb = _heat_rgb(u)
        tr, tg, tb = _bg_text_rgb(rgb)
        style_key = (int(rgb[0]), int(rgb[1]), int(rgb[2]), int(tr), int(tg), int(tb))
        changed = False
        if style_key != self._style_key:
            self._bg_color = QtGui.QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
            self._fg_color = QtGui.QColor(int(tr), int(tg), int(tb))
            self._bg_brush.setColor(self._bg_color)
            self._fg_pen.setColor(self._fg_color)
            self._bg_cache_key = None
            self._bg_cache_pixmap = None
            self._style_key = style_key
            changed = True
        if str(text) != self._value_text:
            self._value_text = str(text)
            self._value_static_text.setText(self._value_text)
            self._prepare_static_text(self._value_static_text, self._value_font)
            changed = True
        if changed:
            self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent):  # type: ignore[override]
        self._ensure_layout()
        p = QtGui.QPainter(self)
        bg = self._ensure_background_cache()
        if bg is not None:
            p.drawPixmap(0, 0, bg)
        else:
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            p.setPen(self._border_pen)
            p.setBrush(self._bg_brush)
            p.drawRoundedRect(self._frame_rect, 8.0, 8.0)

        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        p.setPen(self._fg_pen)
        p.setFont(self._corner_font)
        p.drawStaticText(self._corner_pos, self._corner_static_text)

        p.setFont(self._value_font)
        p.drawStaticText(self._value_pos, self._value_static_text)


class CornerHeatmapPanel(QtWidgets.QWidget):
    """Glanceable 2x2 heatmap for corner metrics (front/rear, left/right).

    This is a small-multiples / instrument-cluster style widget:
    - One cell per corner (ЛП/ПП/ЛЗ/ПЗ)
    - Color encodes magnitude
    - Text shows exact value
    """

    METRICS = [
        ("az_body", "|az| рама (м/с²)", "m/s²"),
        ("az_wheel", "|az| колесо (м/с²)", "m/s²"),
        ("wheel_road", "колесо‑дорога (м)", "m"),
        ("wheel_body", "колесо‑рама (м)", "m"),
        ("frame_road", "рама‑дорога (м)", "m"),
        ("inv_sum", "инвариант err (мм)", "mm"),
        ("triplet_xy", "XY err wheel-road (мм)", "mm"),
        ("stroke", "положение штока (м)", "m"),
        ("tireF", "норм. сила шины (Н)", "N"),
        ("wheel_air", "колесо в воздухе (0/1)", ""),
    ]

    def __init__(self):
        super().__init__()
        self._metric = "az_body"
        self._auto = True
        self._max_override = 0.0
        self._ranges: Dict[str, float] = {}
        self._b: Optional[DataBundle] = None
        self._bundle_key: Optional[int] = None
        self._corner_metric_cache: Dict[str, Dict[str, Any]] = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # controls row
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.cb_metric = QtWidgets.QComboBox()
        for key, label, _unit in self.METRICS:
            self.cb_metric.addItem(label, userData=key)
        self.cb_metric.currentIndexChanged.connect(self._on_metric_changed)

        self.cb_auto = QtWidgets.QCheckBox("auto range")
        self.cb_auto.setChecked(True)
        self.cb_auto.stateChanged.connect(self._on_auto_changed)

        self.sp_max = QtWidgets.QDoubleSpinBox()
        self.sp_max.setRange(0.0, 1e9)
        self.sp_max.setDecimals(3)
        self.sp_max.setSingleStep(0.1)
        self.sp_max.setValue(0.0)
        self.sp_max.setEnabled(False)
        self.sp_max.valueChanged.connect(self._on_max_changed)

        row.addWidget(self.cb_metric, stretch=2)
        row.addWidget(self.cb_auto)
        row.addWidget(QtWidgets.QLabel("max:"))
        row.addWidget(self.sp_max, stretch=1)

        outer.addLayout(row)

        # grid 2x2: front row (ЛП, ПП), rear row (ЛЗ, ПЗ)
        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.cells: Dict[str, _HeatCell] = {}
        order = [("ЛП", 0, 0), ("ПП", 0, 1), ("ЛЗ", 1, 0), ("ПЗ", 1, 1)]
        for c, r, k in order:
            cell = _HeatCell(c)
            self.cells[c] = cell
            grid.addWidget(cell, r, k)

        outer.addLayout(grid)

    def _on_metric_changed(self, _idx: int):
        try:
            self._metric = str(self.cb_metric.currentData())
        except Exception:
            self._metric = "az_body"
        self._update_max_from_ranges()

    def _on_auto_changed(self, _state: int):
        self._auto = bool(self.cb_auto.isChecked())
        self.sp_max.setEnabled(not self._auto)
        self._update_max_from_ranges()

    def _on_max_changed(self, _v: float):
        try:
            self._max_override = float(self.sp_max.value())
        except Exception:
            self._max_override = 0.0

    def _update_max_from_ranges(self):
        if self._auto:
            mv = float(self._ranges.get(self._metric, 0.0))
            self.sp_max.blockSignals(True)
            self.sp_max.setValue(float(mv))
            self.sp_max.blockSignals(False)

    def set_bundle(self, b: DataBundle):
        self._b = b
        self._bundle_key = id(b)
        # Precompute robust max for each metric (shared across corners)
        self._ranges = {}
        for key, _label, _unit in self.METRICS:
            mx = 0.0
            if key == "az_body":
                for c in CORNERS:
                    mx = max(mx, _robust_max_abs(b.frame_corner_a(c, default=0.0)))
            elif key == "az_wheel":
                for c in CORNERS:
                    mx = max(mx, _robust_max_abs(b.get(f"ускорение_колеса_{c}_м_с2", 0.0)))
            elif key == "wheel_road":
                for c in CORNERS:
                    zw = np.asarray(b.get(f"перемещение_колеса_{c}_м", 0.0), dtype=float)
                    zr = b.road_series(c)
                    if zr is None:
                        continue
                    zr = np.asarray(zr, dtype=float)
                    mx = max(mx, float(np.nanpercentile(np.abs(zw - zr), 99)))
            elif key == "wheel_body":
                for c in CORNERS:
                    zw = np.asarray(b.get(f"перемещение_колеса_{c}_м", 0.0), dtype=float)
                    zb = np.asarray(b.frame_corner_z(c, default=0.0), dtype=float)
                    mx = max(mx, float(np.nanpercentile(np.abs(zw - zb), 99)))
            elif key == "frame_road":
                for c in CORNERS:
                    acc = corner_acceptance_arrays(b, c)
                    if not acc.get("ok", False):
                        continue
                    mx = max(mx, float(np.nanpercentile(np.abs(acc["frame_road_m"]), 99)))
            elif key == "inv_sum":
                st = collect_acceptance_status(b)
                mx = max(mx, float(st.get("max_invariant_err_m", 0.0)) * 1000.0)
            elif key == "triplet_xy":
                st = collect_acceptance_status(b)
                mx = max(mx, float(st.get("max_xy_err_m", 0.0)) * 1000.0)
            elif key == "stroke":
                for c in CORNERS:
                    mx = max(mx, float(np.nanpercentile(np.abs(b.get(f"положение_штока_{c}_м", 0.0)), 99)))
            elif key == "tireF":
                for c in CORNERS:
                    mx = max(mx, float(np.nanpercentile(np.abs(b.get(f"нормальная_сила_шины_{c}_Н", 0.0)), 99)))
            elif key == "wheel_air":
                mx = 1.0
            self._ranges[key] = float(mx)

        corner_cache = _ensure_corner_signal_cache(b)
        metric_cache: Dict[str, Dict[str, Any]] = {}
        for c in CORNERS:
            sig = corner_cache.get(str(c), {})
            acc = corner_acceptance_arrays(b, c)
            metric_cache[str(c)] = {
                "az_body": np.asarray(sig.get("ab", np.zeros((0,), dtype=float)), dtype=float),
                "az_wheel": np.asarray(sig.get("aw", np.zeros((0,), dtype=float)), dtype=float),
                "zw": np.asarray(sig.get("zw", np.zeros((0,), dtype=float)), dtype=float),
                "zb": np.asarray(sig.get("zb", np.zeros((0,), dtype=float)), dtype=float),
                "zr": None if sig.get("zr") is None else np.asarray(sig.get("zr"), dtype=float),
                "stroke": np.asarray(sig.get("stroke", np.zeros((0,), dtype=float)), dtype=float),
                "tireF": np.asarray(sig.get("tireF", np.zeros((0,), dtype=float)), dtype=float),
                "air": np.asarray(sig.get("air", np.zeros((0,), dtype=float)), dtype=float),
                "frame_road_m": None if not acc.get("ok", False) else np.asarray(acc["frame_road_m"], dtype=float),
                "invariant_err_m": None if not acc.get("ok", False) else np.asarray(acc["invariant_err_m"], dtype=float),
                "xy_err_wheel_road_m": None if not acc.get("ok", False) else np.asarray(acc["xy_err_wheel_road_m"], dtype=float),
            }
        self._corner_metric_cache = metric_cache
        self._update_max_from_ranges()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        if int(getattr(self, "_bundle_key", 0) or 0) != id(b) or not self._corner_metric_cache:
            self.set_bundle(b)
        key = self._metric
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(b.t, dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))
        # determine max range
        if self._auto:
            mv = float(self._ranges.get(key, 0.0))
        else:
            mv = float(self._max_override or 0.0)
        mv = mv if mv > 1e-12 else 1.0

        for c in CORNERS:
            cache = self._corner_metric_cache.get(str(c), {})
            v = 0.0
            if key == "az_body":
                arr = cache.get("az_body")
                v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0
                txt = f"{v:+.2f}"
                u = abs(v) / mv
            elif key == "az_wheel":
                arr = cache.get("az_wheel")
                v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0
                txt = f"{v:+.2f}"
                u = abs(v) / mv
            elif key == "wheel_road":
                zw_arr = cache.get("zw")
                zw = sample(zw_arr, 0.0) if isinstance(zw_arr, np.ndarray) else 0.0
                road_arr = cache.get("zr")
                zr = sample(road_arr, float("nan")) if isinstance(road_arr, np.ndarray) else float("nan")
                v = zw - zr
                txt = f"{v:+.3f}"
                u = abs(v) / mv
            elif key == "wheel_body":
                zw_arr = cache.get("zw")
                zb_arr = cache.get("zb")
                zw = sample(zw_arr, 0.0) if isinstance(zw_arr, np.ndarray) else 0.0
                zb = sample(zb_arr, 0.0) if isinstance(zb_arr, np.ndarray) else 0.0
                v = zw - zb
                txt = f"{v:+.3f}"
                u = abs(v) / mv
            elif key == "frame_road":
                arr = cache.get("frame_road_m")
                v = sample(arr, float("nan")) if isinstance(arr, np.ndarray) else float("nan")
                txt = "—" if not np.isfinite(v) else f"{v:+.3f}"
                u = 0.0 if not np.isfinite(v) else abs(v) / mv
            elif key == "inv_sum":
                arr = cache.get("invariant_err_m")
                v = (sample(arr, float("nan")) * 1000.0) if isinstance(arr, np.ndarray) else float("nan")
                txt = "—" if not np.isfinite(v) else f"{v:.3f}"
                u = 0.0 if not np.isfinite(v) else abs(v) / mv
            elif key == "triplet_xy":
                arr = cache.get("xy_err_wheel_road_m")
                v = (sample(arr, float("nan")) * 1000.0) if isinstance(arr, np.ndarray) else float("nan")
                txt = "—" if not np.isfinite(v) else f"{v:.3f}"
                u = 0.0 if not np.isfinite(v) else abs(v) / mv
            elif key == "stroke":
                arr = cache.get("stroke")
                v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0
                txt = f"{v:.3f}"
                u = abs(v) / mv
            elif key == "tireF":
                arr = cache.get("tireF")
                v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0
                txt = f"{v/1000.0:.1f}k"
                u = abs(v) / mv
            elif key == "wheel_air":
                arr = cache.get("air")
                v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0
                txt = "AIR" if v > 0.5 else "OK"
                u = 1.0 if v > 0.5 else 0.0
            else:
                txt = f"{v:.3f}"
                u = abs(v) / mv

            u = float(_clamp(u, 0.0, 1.0))
            cell = self.cells.get(c)
            if cell is not None:
                cell.set_value(v, text=txt, u=u)


class _CompactTelemetrySummaryCanvas(QtWidgets.QWidget):
    """Compact painter-based motion summary for docked telemetry mode."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(86)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
        self._items: list[tuple[str, str]] = []
        self._items_key: Optional[tuple[tuple[str, str], ...]] = None
        self._value_static_texts: list[QtGui.QStaticText] = []
        self._layout_cache_key: Optional[tuple[int, int, int]] = None
        self._layout_cache: list[QtCore.QRectF] = []
        self._bg_cache_key: Optional[tuple[Any, ...]] = None
        self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None
        self._bg = QtGui.QColor(18, 22, 28)
        self._tile_bg = QtGui.QColor(27, 34, 43)
        self._tile_border = QtGui.QPen(QtGui.QColor(61, 74, 90), 1.0)
        self._title_color = QtGui.QColor(154, 168, 184)
        self._value_color = QtGui.QColor(240, 245, 251)
        self._value_font = QtGui.QFont(self.font())
        try:
            self._tile_border.setCosmetic(True)
            self._value_font.setPointSize(max(9, int(self._value_font.pointSize())))
            self._value_font.setBold(True)
        except Exception:
            pass

    def _prepare_static_text(self, text_item: QtGui.QStaticText) -> None:
        try:
            text_item.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            text_item.prepare(QtGui.QTransform(), self._value_font)
        except Exception:
            pass

    def set_metrics(self, items: Sequence[tuple[str, str]]) -> None:
        normalized = tuple((str(k), str(v)) for k, v in items)
        if normalized == self._items_key:
            return
        self._items = list(normalized)
        self._value_static_texts = []
        for _title, value in self._items:
            text_item = QtGui.QStaticText(str(value))
            self._prepare_static_text(text_item)
            self._value_static_texts.append(text_item)
        self._items_key = normalized
        self.update()

    def _tile_rects(self) -> list[QtCore.QRectF]:
        count = max(1, int(len(self._items)))
        w = max(1, int(self.width()))
        h = max(1, int(self.height()))
        cols = 4 if w >= 420 else 3 if w >= 300 else 2
        rows = max(1, int(math.ceil(float(count) / float(cols))))
        key = (w, h, count)
        if key == self._layout_cache_key and self._layout_cache:
            return self._layout_cache
        gap = 6.0
        outer = QtCore.QRectF(0.0, 0.0, float(w), float(h))
        tile_w = max(54.0, (outer.width() - gap * float(cols - 1)) / float(cols))
        tile_h = max(30.0, (outer.height() - gap * float(rows - 1)) / float(rows))
        rects: list[QtCore.QRectF] = []
        for idx in range(count):
            row = idx // cols
            col = idx % cols
            rects.append(
                QtCore.QRectF(
                    outer.left() + col * (tile_w + gap),
                    outer.top() + row * (tile_h + gap),
                    tile_w,
                    tile_h,
                )
            )
        self._layout_cache_key = key
        self._layout_cache = rects
        return rects

    def _ensure_background_cache(self) -> tuple[Optional[QtGui.QPixmap], list[QtCore.QRectF]]:
        rects = self._tile_rects()
        titles = tuple(title for title, _value in self._items)
        key = (int(self.width()), int(self.height()), titles)
        if key == self._bg_cache_key and self._bg_cache_pixmap is not None:
            return self._bg_cache_pixmap, rects

        dpr = 1.0
        try:
            dpr = float(max(1.0, self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        pix = QtGui.QPixmap(int(max(1.0, float(max(1, self.width())) * dpr)), int(max(1.0, float(max(1, self.height())) * dpr)))
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        pix.fill(self._bg)

        p = QtGui.QPainter(pix)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        title_font = QtGui.QFont(self.font())
        try:
            title_font.setPointSize(max(7, int(title_font.pointSize()) - 1))
        except Exception:
            pass
        p.setFont(title_font)
        for idx, rect in enumerate(rects):
            p.setPen(self._tile_border)
            p.setBrush(self._tile_bg)
            p.drawRoundedRect(rect, 7.0, 7.0)
            if idx < len(titles):
                p.setPen(self._title_color)
                p.drawText(
                    QtCore.QRectF(rect.left() + 8.0, rect.top() + 4.0, rect.width() - 16.0, 14.0),
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                    titles[idx],
                )
        p.end()

        self._bg_cache_key = key
        self._bg_cache_pixmap = pix
        return self._bg_cache_pixmap, rects

    def paintEvent(self, _event: QtGui.QPaintEvent):  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.TextAntialiasing)
        bg, rects = self._ensure_background_cache()
        if bg is not None:
            p.drawPixmap(0, 0, bg)
        else:
            p.fillRect(self.rect(), self._bg)

        p.setFont(self._value_font)
        p.setPen(self._value_color)
        fm = QtGui.QFontMetrics(self._value_font)
        for idx, rect in enumerate(rects):
            if idx >= len(self._items):
                break
            text_item = self._value_static_texts[idx] if idx < len(self._value_static_texts) else None
            if text_item is None:
                continue
            value_rect = QtCore.QRectF(rect.left() + 8.0, rect.top() + 18.0, rect.width() - 16.0, max(18.0, rect.height() - 22.0))
            value_pos = QtCore.QPointF(
                float(value_rect.left()),
                float(value_rect.top() + max(0.0, (value_rect.height() - float(fm.height())) * 0.5)),
            )
            p.drawStaticText(value_pos, text_item)


class TelemetryPanel(QtWidgets.QWidget):
    """Right-side telemetry panel.

    Goals:
    - show the most important signals *always visible* (no scrolling):
        * motion summary (t, speed, yaw, radius, roll/pitch)
        * visualization layer toggles + vector scale
        * pneumatics quick status (pressures + active valves)
        * road elevation profile
    - keep extended details below in a scroll area.
    """

    visual_changed = QtCore.Signal(dict)

    @staticmethod
    def _make_compact_toggle_button(text: str, tooltip: str) -> QtWidgets.QToolButton:
        btn = QtWidgets.QToolButton()
        btn.setText(str(text))
        btn.setCheckable(True)
        btn.setAutoRaise(False)
        btn.setToolTip(str(tooltip))
        try:
            btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            btn.setMinimumHeight(24)
            btn.setStyleSheet(
                """
                QToolButton{
                    padding:3px 8px;
                    border:1px solid #364152;
                    border-radius:6px;
                    background:#1d2530;
                    color:#d8dee8;
                    font-weight:600;
                }
                QToolButton:checked{
                    background:#2f5d8a;
                    border-color:#5e9ad8;
                    color:#f6fbff;
                }
                """
            )
        except Exception:
            pass
        return btn

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, compact: bool = False):
        super().__init__(parent)
        self.compact = bool(compact)
        self._compact_dock_mode = False
        self._compact_visual_expanded = False
        self.lbl_zcm: Optional[QtWidgets.QLabel] = None
        self.lbl_vzcm: Optional[QtWidgets.QLabel] = None
        self.lbl_azcm: Optional[QtWidgets.QLabel] = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QtWidgets.QLabel("Telemetry (mech + pneumo)")
        self.lbl_title.setStyleSheet("font-weight:600;")
        outer.addWidget(self.lbl_title)

        # -------------------
        # Pinned (always visible)
        # -------------------
        pinned = QtWidgets.QWidget()
        pin = QtWidgets.QVBoxLayout(pinned)
        pin.setContentsMargins(0, 0, 0, 0)
        pin.setSpacing(8)

        # Row 0: summary + visual controls
        row0 = QtWidgets.QHBoxLayout()
        row0.setSpacing(8)

        # ---- Summary group (pinned) ----
        gb_sum = QtWidgets.QGroupBox("Сводка движения")
        gb_sum.setStyleSheet("QGroupBox{font-weight:600;}")
        lay_sum = QtWidgets.QGridLayout(gb_sum)
        lay_sum.setHorizontalSpacing(10)
        lay_sum.setVerticalSpacing(2)
        self.gb_sum = gb_sum

        self.lbl_t = QtWidgets.QLabel("t = —")
        self.lbl_v = QtWidgets.QLabel("vx = —")
        self.lbl_vkmh = QtWidgets.QLabel("v = —")
        self.lbl_ax = QtWidgets.QLabel("ax = —")
        self.lbl_ay = QtWidgets.QLabel("ay = —")
        self.lbl_yaw = QtWidgets.QLabel("yaw = —")
        self.lbl_yawr = QtWidgets.QLabel("yaw_rate = —")
        self.lbl_R = QtWidgets.QLabel("R = —")
        self.lbl_ac = QtWidgets.QLabel("a_c = —")
        self.lbl_roll = QtWidgets.QLabel("roll = —")
        self.lbl_pitch = QtWidgets.QLabel("pitch = —")

        labs = [
            self.lbl_t, self.lbl_v, self.lbl_vkmh,
            self.lbl_ax, self.lbl_ay,
            self.lbl_yaw, self.lbl_yawr,
            self.lbl_R, self.lbl_ac,
            self.lbl_roll, self.lbl_pitch,
        ]
        for k, lab in enumerate(labs):
            r = k // 2
            c = k % 2
            lay_sum.addWidget(lab, r, c)

        row0.addWidget(gb_sum, stretch=2)
        self.compact_summary = _CompactTelemetrySummaryCanvas()
        self.compact_summary.hide()
        row0.addWidget(self.compact_summary, stretch=2)

        self.compact_vis_strip = QtWidgets.QWidget()
        strip_lay = QtWidgets.QHBoxLayout(self.compact_vis_strip)
        strip_lay.setContentsMargins(0, 0, 0, 0)
        strip_lay.setSpacing(6)
        self.btn_compact_acc = self._make_compact_toggle_button("a", "Ускорения в видах")
        self.btn_compact_vel = self._make_compact_toggle_button("v", "Скорости в видах")
        self.btn_compact_lbl = self._make_compact_toggle_button("lbl", "Подписи в видах")
        self.btn_compact_hud = self._make_compact_toggle_button("hud", "HUD overlays (lanes/text/accel)")
        self.btn_compact_3d = self._make_compact_toggle_button("3D", "3D дорога + векторы")
        self.btn_compact_auto = self._make_compact_toggle_button("auto", "Авто-масштаб векторов")
        self.btn_compact_more = self._make_compact_toggle_button("...", "Показать полный блок визуализации")
        for btn in (
            self.btn_compact_acc,
            self.btn_compact_vel,
            self.btn_compact_lbl,
            self.btn_compact_hud,
            self.btn_compact_3d,
            self.btn_compact_auto,
            self.btn_compact_more,
        ):
            strip_lay.addWidget(btn, 0)
        strip_lay.addStretch(1)
        row0.addWidget(self.compact_vis_strip, stretch=1)

        # ---- Visual controls (pinned) ----
        gb_vis = QtWidgets.QGroupBox("Визуализация")
        gb_vis.setStyleSheet("QGroupBox{font-weight:600;}")
        lay_vis = QtWidgets.QGridLayout(gb_vis)
        lay_vis.setHorizontalSpacing(8)
        lay_vis.setVerticalSpacing(2)
        self.gb_vis = gb_vis

        self.cb_show_acc = QtWidgets.QCheckBox("ускорения (a)")
        self.cb_show_acc.setChecked(True)
        self.cb_show_vel = QtWidgets.QCheckBox("скорости (v)")
        self.cb_show_vel.setChecked(False)
        self.cb_show_lbl = QtWidgets.QCheckBox("подписи")
        self.cb_show_lbl.setChecked(True)

        self.cb_show_dims = QtWidgets.QCheckBox("2D: размеры")
        self.cb_show_dims.setChecked(False)
        self.cb_show_dims.setToolTip(
            "Числовые размеры геометрии поверх 2D видов (база/колея/радиус)."
        )

        self.cb_show_scale = QtWidgets.QCheckBox("2D: линейка")
        self.cb_show_scale.setChecked(True)
        self.cb_show_scale.setToolTip("Линейка масштаба (в метрах) внизу 2D видов")

        self.cb_hud_lanes = QtWidgets.QCheckBox("HUD: полосы")
        self.cb_hud_lanes.setChecked(True)
        self.cb_hud_text = QtWidgets.QCheckBox("HUD: текст")
        self.cb_hud_text.setChecked(True)
        self.cb_hud_acc = QtWidgets.QCheckBox("HUD: accel")
        self.cb_hud_acc.setChecked(True)
        self.cb_hud_auto = QtWidgets.QCheckBox("HUD: авто дальность")
        self.cb_hud_auto.setChecked(True)

        self.cb_auto_scale = QtWidgets.QCheckBox("auto‑scale (a/v)")
        self.cb_auto_scale.setChecked(True)

        self.cb_3d_road = QtWidgets.QCheckBox("3D: дорога")
        self.cb_3d_road.setChecked(True)
        self.cb_3d_vec = QtWidgets.QCheckBox("3D: векторы")
        self.cb_3d_vec.setChecked(True)

        self.sp_acc_scale = QtWidgets.QDoubleSpinBox()
        self.sp_acc_scale.setRange(0.0, 0.30)
        self.sp_acc_scale.setSingleStep(0.01)
        self.sp_acc_scale.setDecimals(3)
        self.sp_acc_scale.setValue(0.05)
        self.sp_acc_scale.setSuffix(" m/(m/s²)")

        self.sp_vel_scale = QtWidgets.QDoubleSpinBox()
        self.sp_vel_scale.setRange(0.0, 0.50)
        self.sp_vel_scale.setSingleStep(0.01)
        self.sp_vel_scale.setDecimals(3)
        self.sp_vel_scale.setValue(0.08)
        self.sp_vel_scale.setSuffix(" m/(m/s)")

        self._rec_acc_scale: Optional[float] = None
        self._rec_vel_scale: Optional[float] = None

        # layout (2 columns)
        lay_vis.addWidget(self.cb_show_acc, 0, 0)
        lay_vis.addWidget(self.cb_show_vel, 1, 0)
        lay_vis.addWidget(self.cb_show_lbl, 2, 0)

        lay_vis.addWidget(self.cb_hud_lanes, 0, 1)
        lay_vis.addWidget(self.cb_hud_text, 1, 1)
        lay_vis.addWidget(self.cb_hud_acc, 2, 1)

        lay_vis.addWidget(self.cb_auto_scale, 3, 0)
        lay_vis.addWidget(self.cb_hud_auto, 3, 1)

        lay_vis.addWidget(self.cb_3d_road, 4, 0)
        lay_vis.addWidget(self.cb_3d_vec, 4, 1)

        lay_vis.addWidget(QtWidgets.QLabel("scale a:"), 5, 0)
        lay_vis.addWidget(self.sp_acc_scale, 5, 1)

        lay_vis.addWidget(QtWidgets.QLabel("scale v:"), 6, 0)
        lay_vis.addWidget(self.sp_vel_scale, 6, 1)

        lay_vis.addWidget(self.cb_show_dims, 7, 0)
        lay_vis.addWidget(self.cb_show_scale, 7, 1)

        row0.addWidget(gb_vis, stretch=1)

        pin.addLayout(row0)

        # ---- Pneumatics quick (pinned) ----
        gb_pq = QtWidgets.QGroupBox("Пневматика: быстро (давления + клапаны + расход)")
        gb_pq.setStyleSheet("QGroupBox{font-weight:600;}")
        lay_pq = QtWidgets.QGridLayout(gb_pq)
        lay_pq.setContentsMargins(6, 6, 6, 6)
        lay_pq.setHorizontalSpacing(10)
        lay_pq.setVerticalSpacing(6)
        self.gb_pq = gb_pq

        self.press_quick = PressureQuickPanel()
        self.valve_quick = ValveQuickPanel(max_rows=8, thr=0.05)
        self.flow_quick = FlowQuickPanel(max_rows=6, thr_kg_s=0.001)
        self.tank_gauge = ReceiverTankWidget()

        lay_pq.addWidget(self.press_quick, 0, 0)
        lay_pq.addWidget(self.valve_quick, 0, 1)
        lay_pq.addWidget(self.flow_quick, 1, 0, 1, 2)
        lay_pq.addWidget(self.tank_gauge, 0, 2, 2, 1)

        lay_pq.setColumnStretch(0, 1)
        lay_pq.setColumnStretch(1, 1)
        lay_pq.setColumnStretch(2, 0)

        pin.addWidget(gb_pq)

        self.corner_heatmap: Optional[CornerHeatmapPanel] = None
        self.corner_quick: Optional[CornerQuickTable] = None
        self.road_profile: Optional[RoadProfilePanel] = None
        self.corner_table: Optional[CornerTable] = None
        self.press_panel: Optional[PressurePanel] = None
        self.flow_panel: Optional[FlowPanel] = None
        self.valve_panel: Optional[ValvePanel] = None

        outer.addWidget(pinned, stretch=0)

        if not self.compact:
            # ---- Corner heatmap (pinned) ----
            gb_hm = QtWidgets.QGroupBox("Heatmap (углы)")
            gb_hm.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_hm = QtWidgets.QVBoxLayout(gb_hm)
            lay_hm.setContentsMargins(6, 6, 6, 6)
            self.corner_heatmap = CornerHeatmapPanel()
            lay_hm.addWidget(self.corner_heatmap)
            pin.addWidget(gb_hm)

            # ---- Corners quick (pinned) ----
            gb_cq = QtWidgets.QGroupBox("Углы: быстро (z/дефлексия/шток/контакт)")
            gb_cq.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_cq = QtWidgets.QVBoxLayout(gb_cq)
            lay_cq.setContentsMargins(6, 6, 6, 6)
            self.corner_quick = CornerQuickTable()
            lay_cq.addWidget(self.corner_quick)
            pin.addWidget(gb_cq)

            # ---- Road profile (pinned) ----
            gb_rp = QtWidgets.QGroupBox("Профиль дороги (elevation)")
            gb_rp.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_rp = QtWidgets.QVBoxLayout(gb_rp)
            lay_rp.setContentsMargins(6, 6, 6, 6)
            self.road_profile = RoadProfilePanel()
            lay_rp.addWidget(self.road_profile)
            pin.addWidget(gb_rp)

            # -------------------
            # Scroll area (extended details)
            # -------------------
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            outer.addWidget(scroll, stretch=1)

            content = QtWidgets.QWidget()
            scroll.setWidget(content)

            lay = QtWidgets.QVBoxLayout(content)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)

            # ---- Body / COM ----
            gb_body = QtWidgets.QGroupBox("Рама / центр масс (Z)")
            gb_body.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_b = QtWidgets.QGridLayout(gb_body)
            lay_b.setHorizontalSpacing(10)
            lay_b.setVerticalSpacing(2)

            self.lbl_zcm = QtWidgets.QLabel("z_cm = —")
            self.lbl_vzcm = QtWidgets.QLabel("vz_cm = —")
            self.lbl_azcm = QtWidgets.QLabel("az_cm = —")
            lay_b.addWidget(self.lbl_zcm, 0, 0)
            lay_b.addWidget(self.lbl_vzcm, 0, 1)
            lay_b.addWidget(self.lbl_azcm, 1, 0)

            lay.addWidget(gb_body)

            # ---- Corners ----
            gb_corners = QtWidgets.QGroupBox("Углы / колёса (ЛП/ПП/ЛЗ/ПЗ)")
            gb_corners.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_c = QtWidgets.QVBoxLayout(gb_corners)
            lay_c.setContentsMargins(6, 6, 6, 6)

            self.corner_table = CornerTable()
            lay_c.addWidget(self.corner_table)
            lay.addWidget(gb_corners, stretch=0)

            # ---- Pressures (detailed) ----
            gb_p = QtWidgets.QGroupBox("Пневматика: подробно (давления узлов)")
            gb_p.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_p = QtWidgets.QVBoxLayout(gb_p)
            self.press_panel = PressurePanel()
            lay_p.addWidget(self.press_panel)
            lay.addWidget(gb_p)

            # ---- Flows (detailed) ----
            gb_q = QtWidgets.QGroupBox("Пневматика: подробно (массовые расходы mdot)")
            gb_q.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_q = QtWidgets.QVBoxLayout(gb_q)
            self.flow_panel = FlowPanel()
            lay_q.addWidget(self.flow_panel)
            lay.addWidget(gb_q)

            # ---- Valves (detailed) ----
            gb_v = QtWidgets.QGroupBox("Пневматика: подробно (клапаны)")
            gb_v.setStyleSheet("QGroupBox{font-weight:600;}")
            lay_v = QtWidgets.QVBoxLayout(gb_v)
            self.valve_panel = ValvePanel()
            lay_v.addWidget(self.valve_panel)
            lay.addWidget(gb_v)

            lay.addStretch(1)

        # Wire visual controls -> emit dict (so Cockpit can reconfigure views)
        def _connect_bool(cb: QtWidgets.QCheckBox):
            cb.stateChanged.connect(self._emit_visual)

        for cb in (
            self.cb_show_acc,
            self.cb_show_vel,
            self.cb_show_lbl,
            self.cb_show_dims,
            self.cb_show_scale,
            self.cb_hud_lanes,
            self.cb_hud_text,
            self.cb_hud_acc,
            self.cb_hud_auto,
            self.cb_3d_road,
            self.cb_3d_vec,
        ):
            _connect_bool(cb)
        self.cb_auto_scale.stateChanged.connect(self._on_auto_scale_changed)
        self.sp_acc_scale.valueChanged.connect(self._emit_visual)
        self.sp_vel_scale.valueChanged.connect(self._emit_visual)
        self.cb_show_acc.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_show_vel.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_show_lbl.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_hud_lanes.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_hud_text.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_hud_acc.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_3d_road.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_3d_vec.stateChanged.connect(self._sync_compact_visual_strip)
        self.cb_auto_scale.stateChanged.connect(self._sync_compact_visual_strip)
        self.btn_compact_acc.toggled.connect(self.cb_show_acc.setChecked)
        self.btn_compact_vel.toggled.connect(self.cb_show_vel.setChecked)
        self.btn_compact_lbl.toggled.connect(self.cb_show_lbl.setChecked)
        self.btn_compact_auto.toggled.connect(self.cb_auto_scale.setChecked)
        self.btn_compact_hud.toggled.connect(self._set_compact_hud_enabled)
        self.btn_compact_3d.toggled.connect(self._set_compact_3d_enabled)
        self.btn_compact_more.toggled.connect(self._set_compact_visual_expanded)

        # emit initial config once (safe even if no receivers yet)
        QtCore.QTimer.singleShot(0, self._on_auto_scale_changed)
        QtCore.QTimer.singleShot(0, self._emit_visual)
        QtCore.QTimer.singleShot(0, self._sync_compact_visual_strip)
        self.set_compact_dock_mode(False)

    def current_visual(self) -> Dict[str, Any]:
        return {
            "show_accel": bool(self.cb_show_acc.isChecked()),
            "show_vel": bool(self.cb_show_vel.isChecked()),
            "show_labels": bool(self.cb_show_lbl.isChecked()),
            "show_dims": bool(self.cb_show_dims.isChecked()),
            "show_scale_bar": bool(self.cb_show_scale.isChecked()),
            "accel_scale": float(self.sp_acc_scale.value()),
            "vel_scale": float(self.sp_vel_scale.value()),
            "hud_lanes": bool(self.cb_hud_lanes.isChecked()),
            "hud_text": bool(self.cb_hud_text.isChecked()),
            "hud_accel": bool(self.cb_hud_acc.isChecked()),
            "hud_auto": bool(self.cb_hud_auto.isChecked()),
            "auto_scale": bool(self.cb_auto_scale.isChecked()),
            "gl_road": bool(self.cb_3d_road.isChecked()),
            "gl_vectors": bool(self.cb_3d_vec.isChecked()),
        }

    def _sync_compact_visual_strip(self, *_args) -> None:
        state_pairs = (
            (self.btn_compact_acc, bool(self.cb_show_acc.isChecked())),
            (self.btn_compact_vel, bool(self.cb_show_vel.isChecked())),
            (self.btn_compact_lbl, bool(self.cb_show_lbl.isChecked())),
            (
                self.btn_compact_hud,
                bool(self.cb_hud_lanes.isChecked() and self.cb_hud_text.isChecked() and self.cb_hud_acc.isChecked()),
            ),
            (
                self.btn_compact_3d,
                bool(self.cb_3d_road.isChecked() and self.cb_3d_vec.isChecked()),
            ),
            (self.btn_compact_auto, bool(self.cb_auto_scale.isChecked())),
            (self.btn_compact_more, bool(self._compact_visual_expanded)),
        )
        for btn, checked in state_pairs:
            try:
                blocked = btn.blockSignals(True)
                btn.setChecked(bool(checked))
                btn.blockSignals(blocked)
            except Exception:
                pass

    def _set_compact_hud_enabled(self, enabled: bool) -> None:
        for cb in (self.cb_hud_lanes, self.cb_hud_text, self.cb_hud_acc):
            try:
                cb.setChecked(bool(enabled))
            except Exception:
                pass

    def _set_compact_3d_enabled(self, enabled: bool) -> None:
        for cb in (self.cb_3d_road, self.cb_3d_vec):
            try:
                cb.setChecked(bool(enabled))
            except Exception:
                pass

    def _set_compact_visual_expanded(self, expanded: bool) -> None:
        self._compact_visual_expanded = bool(expanded)
        compact_mode = bool(getattr(self, "_compact_dock_mode", False))
        show_full_vis = bool((not compact_mode) or self._compact_visual_expanded)
        try:
            self.gb_vis.setVisible(show_full_vis)
        except Exception:
            pass
        try:
            self.compact_vis_strip.setVisible(bool(compact_mode and not self._compact_visual_expanded))
        except Exception:
            pass
        self._sync_compact_visual_strip()
        try:
            self.updateGeometry()
            self.adjustSize()
        except Exception:
            pass

    def set_compact_dock_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == bool(getattr(self, "_compact_dock_mode", False)):
            return
        self._compact_dock_mode = compact
        max_h = 280 if compact else 16777215
        vpol = QtWidgets.QSizePolicy.Maximum if compact else QtWidgets.QSizePolicy.Preferred
        try:
            self.lbl_title.setVisible(not compact)
        except Exception:
            pass
        try:
            self.setMaximumHeight(max_h)
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
        except Exception:
            pass
        for gb_name, compact_h in (("gb_sum", 132), ("gb_vis", 132), ("gb_pq", 136)):
            gb = getattr(self, gb_name, None)
            if gb is None:
                continue
            try:
                gb.setMaximumHeight(compact_h if compact else 16777215)
                gb.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
            except Exception:
                pass
        try:
            self.gb_sum.setVisible(not compact)
        except Exception:
            pass
        try:
            self.compact_summary.setVisible(bool(compact))
            self.compact_summary.setMinimumHeight(86 if compact else 0)
            self.compact_summary.setMaximumHeight(92 if compact else 16777215)
            self.compact_summary.setSizePolicy(QtWidgets.QSizePolicy.Preferred, vpol)
        except Exception:
            pass
        for child_name in ("press_quick", "valve_quick", "flow_quick", "tank_gauge"):
            child = getattr(self, child_name, None)
            if child is None or not hasattr(child, "set_compact_mode"):
                continue
            try:
                getattr(child, "set_compact_mode")(compact)
            except Exception:
                pass
        self._set_compact_visual_expanded(bool(getattr(self, "_compact_visual_expanded", False)))
        try:
            self.updateGeometry()
            self.adjustSize()
        except Exception:
            pass

    def _emit_visual(self):
        try:
            self.visual_changed.emit(self.current_visual())
        except Exception:
            pass

    def set_bundle(self, b: DataBundle):
        self.press_quick.set_bundle(b)
        self.valve_quick.set_bundle(b)
        self.flow_quick.set_bundle(b)
        self.tank_gauge.set_bundle(b)
        if self.press_panel is not None:
            self.press_panel.set_bundle(b)
        if self.flow_panel is not None:
            self.flow_panel.set_bundle(b)
        if self.valve_panel is not None:
            self.valve_panel.set_bundle(b)
        if self.corner_heatmap is not None:
            try:
                self.corner_heatmap.set_bundle(b)
            except Exception:
                pass
        if self.corner_quick is not None:
            try:
                self.corner_quick.set_bundle(b)
            except Exception:
                pass
        if self.road_profile is not None:
            try:
                self.road_profile.set_bundle(b)
            except Exception:
                pass
        if self.corner_table is not None and hasattr(self.corner_table, 'set_bundle'):
            try:
                self.corner_table.set_bundle(b)
            except Exception:
                pass


    def set_recommended_scales(self, accel_scale: float, vel_scale: float):
        """Provide recommended vector scales (computed from log)."""
        try:
            self._rec_acc_scale = float(accel_scale)
            self._rec_vel_scale = float(vel_scale)
        except Exception:
            self._rec_acc_scale = None
            self._rec_vel_scale = None
        # if auto-scale enabled, apply immediately
        self._apply_recommended_scales()

    def _apply_recommended_scales(self):
        if not bool(getattr(self, "cb_auto_scale", None) and self.cb_auto_scale.isChecked()):
            # manual mode
            try:
                self.sp_acc_scale.setEnabled(True)
                self.sp_vel_scale.setEnabled(True)
            except Exception:
                pass
            return

        # auto mode: lock spinboxes and set recommended values if present
        try:
            self.sp_acc_scale.setEnabled(False)
            self.sp_vel_scale.setEnabled(False)
            if self._rec_acc_scale is not None:
                self.sp_acc_scale.blockSignals(True)
                self.sp_acc_scale.setValue(float(self._rec_acc_scale))
                self.sp_acc_scale.blockSignals(False)
            if self._rec_vel_scale is not None:
                self.sp_vel_scale.blockSignals(True)
                self.sp_vel_scale.setValue(float(self._rec_vel_scale))
                self.sp_vel_scale.blockSignals(False)
        except Exception:
            pass

    def _on_auto_scale_changed(self, *_args):
        # Toggle manual/auto modes
        self._apply_recommended_scales()
        self._emit_visual()

    def update_frame(self, b: DataBundle, i: int, *, sample_t: float | None = None):
        summary = _ensure_telemetry_summary_cache(b)
        sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(
            np.asarray(summary["t"], dtype=float),
            sample_t=sample_t,
            fallback_index=i,
        )
        sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))
        t = sample(summary["t"], 0.0)
        vx = sample(summary["vx"], 0.0)
        vy = sample(summary["vy"], 0.0)

        # Для отображения используем модуль скорости.
        v_mps = math.hypot(vx, vy)
        yaw = sample(summary["yaw"], 0.0)
        yaw_rate = sample(summary["yaw_rate"], 0.0)
        ax = sample(summary["ax"], 0.0)
        ay = sample(summary["ay"], 0.0)
        roll = sample(summary["roll"], 0.0)
        pitch = sample(summary["pitch"], 0.0)

        R = float("inf")
        if abs(yaw_rate) > 1e-6 and abs(vx) > 1e-3:
            R = vx / yaw_rate
        a_c = ay

        if not bool(getattr(self, "_compact_dock_mode", False)):
            _set_label_text_if_changed(self.lbl_t, f"t = {_fmt(t, ' s', digits=3)}")
            _set_label_text_if_changed(self.lbl_v, f"vx = {_fmt(vx, ' m/s', digits=2)}")
            _set_label_text_if_changed(self.lbl_vkmh, f"v = {_fmt(v_mps * 3.6, ' km/h', digits=1)}")
            _set_label_text_if_changed(self.lbl_ax, f"ax = {_fmt(ax, ' m/s²', digits=2)}")
            _set_label_text_if_changed(self.lbl_ay, f"ay = {_fmt(ay, ' m/s²', digits=2)}")
            _set_label_text_if_changed(self.lbl_yaw, f"yaw = {_fmt(np.degrees(yaw), '°', digits=1)}")
            _set_label_text_if_changed(self.lbl_yawr, f"yaw_rate = {_fmt(np.degrees(yaw_rate), '°/s', digits=2)}")
            _set_label_text_if_changed(self.lbl_R, "R = —" if not np.isfinite(R) else f"R = {_fmt(R, ' m', digits=1)}")
            _set_label_text_if_changed(self.lbl_ac, f"a_c = {_fmt(a_c, ' m/s²', digits=2)}")
            _set_label_text_if_changed(self.lbl_roll, f"roll = {_fmt(np.degrees(roll), '°', digits=2)}")
            _set_label_text_if_changed(self.lbl_pitch, f"pitch = {_fmt(np.degrees(pitch), '°', digits=2)}")
        elif self.compact_summary.isVisible():
            try:
                self.compact_summary.set_metrics(
                    [
                        ("t", f"{t:.3f} s"),
                        ("v", f"{(v_mps * 3.6):.1f} km/h"),
                        ("ax", f"{ax:+.2f} m/s²"),
                        ("ay", f"{ay:+.2f} m/s²"),
                        ("yaw", f"{np.degrees(yaw):+.1f}°"),
                        ("R", "—" if not np.isfinite(R) else f"{R:.1f} m"),
                        ("roll", f"{np.degrees(roll):+.2f}°"),
                        ("pitch", f"{np.degrees(pitch):+.2f}°"),
                    ]
                )
            except Exception:
                pass

        zcm = sample(summary["zcm"], 0.0)
        vzcm = sample(summary["vzcm"], 0.0)
        azcm = sample(summary["azcm"], 0.0)
        if self.lbl_zcm is not None:
            _set_label_text_if_changed(self.lbl_zcm, f"z_cm = {_fmt(zcm, ' m', digits=3)}")
        if self.lbl_vzcm is not None:
            _set_label_text_if_changed(self.lbl_vzcm, f"vz_cm = {_fmt(vzcm, ' m/s', digits=3)}")
        if self.lbl_azcm is not None:
            _set_label_text_if_changed(self.lbl_azcm, f"az_cm = {_fmt(azcm, ' m/s²', digits=2)}")

        if self.corner_table is not None:
            self.corner_table.update_frame(b, i, sample_t=sample_t)
        self.press_quick.update_frame(b, i, sample_t=sample_t)
        self.valve_quick.update_frame(b, i, sample_t=sample_t)
        self.flow_quick.update_frame(b, i, sample_t=sample_t)
        self.tank_gauge.update_frame(b, i, sample_t=sample_t)
        if self.press_panel is not None:
            self.press_panel.update_frame(b, i, sample_t=sample_t)
        if self.flow_panel is not None:
            self.flow_panel.update_frame(b, i, sample_t=sample_t)
        if self.valve_panel is not None:
            self.valve_panel.update_frame(b, i, sample_t=sample_t)

        if self.corner_heatmap is not None:
            try:
                self.corner_heatmap.update_frame(b, i, sample_t=sample_t)
            except Exception:
                pass

        # Pinned corners quick table
        if self.corner_quick is not None:
            try:
                self.corner_quick.update_frame(b, i, sample_t=sample_t)
            except Exception:
                pass

        if self.road_profile is not None:
            try:
                self.road_profile.update_frame(b, i, sample_t=sample_t)
            except Exception:
                pass

# -----------------------------
# Cockpit (multi-view)
# -----------------------------



class ExternalPanelWindow(QtWidgets.QWidget):
    """Dedicated top-level host for panels that should not use QDockWidget floating mode."""

    visibilityChanged = QtCore.Signal(bool)

    def __init__(self, *, dock_name: str, title: str, widget: Optional[QtWidgets.QWidget] = None, tooltip: str = ""):
        super().__init__(None, QtCore.Qt.Window)
        self._allow_close = False
        self._dock_name = str(dock_name)
        self._panel_widget: Optional[QtWidgets.QWidget] = None
        self.setObjectName(f"{self._dock_name}_external_window")
        self.setWindowTitle(str(title))
        if tooltip:
            try:
                self.setToolTip(str(tooltip))
            except Exception:
                pass
        try:
            self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        except Exception:
            pass
        try:
            self.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
        except Exception:
            pass
        self._body_layout = QtWidgets.QVBoxLayout(self)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        if widget is not None:
            self.set_panel_widget(widget)

    def dock_name(self) -> str:
        return str(self._dock_name)

    def panel_widget(self) -> Optional[QtWidgets.QWidget]:
        return self._panel_widget

    def take_panel_widget(self) -> Optional[QtWidgets.QWidget]:
        widget = self._panel_widget
        if widget is None:
            return None
        try:
            self._body_layout.removeWidget(widget)
        except Exception:
            pass
        try:
            widget.setParent(None)
        except Exception:
            pass
        self._panel_widget = None
        return widget

    def set_panel_widget(self, widget: Optional[QtWidgets.QWidget]) -> None:
        if widget is None:
            return
        if self._panel_widget is widget:
            return
        if self._panel_widget is not None:
            self.take_panel_widget()
        try:
            widget.setParent(None)
        except Exception:
            pass
        self._body_layout.addWidget(widget)
        self._panel_widget = widget
        try:
            widget.show()
        except Exception:
            pass

    def force_close(self) -> None:
        self._allow_close = True
        try:
            self.close()
        finally:
            self._allow_close = False

    def closeEvent(self, event: QtGui.QCloseEvent):  # type: ignore[override]
        if bool(self._allow_close):
            return super().closeEvent(event)
        try:
            self.hide()
        except Exception:
            pass
        event.ignore()

    def showEvent(self, event: QtGui.QShowEvent):  # type: ignore[override]
        super().showEvent(event)
        try:
            self.visibilityChanged.emit(True)
        except Exception:
            pass

    def hideEvent(self, event: QtGui.QHideEvent):  # type: ignore[override]
        super().hideEvent(event)
        try:
            self.visibilityChanged.emit(False)
        except Exception:
            pass


class CockpitWidget(QtWidgets.QWidget):
    """Central multi-view cockpit.

    R50:
    - 3D + Front + Side(L) + Side(R) + Road HUD visible simultaneously
    - Telemetry panel drives visualization layers (no hotkeys required)

    R51:
    - add *rear axle* L/R view, so you can see front+rear roll behaviour at the same time
    - layout tuned for "front/rear", "left/right" and "3D" simultaneously

    R52:
    - Heatmap (углы) 2×2 + auto‑scale (a/v) для векторов (минимум ручных настроек)
    - HUD авто‑дальность (lookahead зависит от скорости)

    R53:
    - Road HUD: "ribbon" заливка полосы + градиенты линий (ближе к машине ярче, дальше мягче)
    - Пневматика: быстрые счётчики групп (выхлоп/подпитка/заряд) + top‑клапаны
    - Углы: pinned "быстрая таблица" (z/дефлексия/шток/контакт) — без прокрутки

    R54:
    - Event timeline (wheel_air + группы клапанов) + click-to-seek
    - Sparklines/Trends (v, az, roll/pitch, P_acc, valves_open) рядом с анимацией
    """

    # Bridge for click-to-seek from the timeline widget.
    seek_requested = QtCore.Signal(int)

    def __init__(self, *, enable_gl: bool = True, layout_mode: str = "docked", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.enable_gl = bool(enable_gl)
        self.layout_mode = str(layout_mode).strip().lower()
        self.bundle: Optional[DataBundle] = None
        self._last_i: int = 0
        self._playback_sample_t_s: float | None = None
        # Performance policy: the main 3D view owns the playback budget.
        # Auxiliary panes must stay readable, but they must not compete with the 3D
        # renderer for every GUI tick.  We therefore keep only HUD-class overlays in
        # the fast lane and move the axle/side views into the slower lane.
        self._aux_play_fast_fps: float = 24.0
        self._aux_play_slow_fps: float = 12.0
        self._aux_scrub_fast_fps: float = 30.0
        self._aux_scrub_slow_fps: float = 4.0
        self._interactive_scrub_slow_batch_size: int = 2
        self._interactive_scrub_slow_rr_cursor: int = 0
        self._interactive_scrub_release_only_docks: Set[str] = {
            "dock_corner_table",
            "dock_road_profile",
        }
        self._aux_many_fast_fps: float = 18.0
        self._aux_many_slow_fps: float = 10.0
        self._many_visible_threshold: int = 12
        self._aux_fast_last_ts: float = 0.0
        self._aux_slow_last_ts: float = 0.0
        self._playback_perf_mode_active: bool = False
        self._aux_cadence_stats: Dict[str, Dict[str, float]] = {}
        self._aux_cadence_window_started_ts: float = 0.0
        self._aux_cadence_emit_period_s: float = 1.5
        self._aux_cadence_tracking_active: bool = False
        self._external_windows: Dict[str, ExternalPanelWindow] = {}
        self._external_window_actions: Dict[str, QtGui.QAction] = {}
        self._external_window_settings_key_prefix: str = "window/panel_external/"
        self._dock_external_mode: Dict[str, bool] = {}
        self._dock_live_widgets: Dict[str, QtWidgets.QWidget] = {}
        self._dock_live_hosts: Dict[str, QtWidgets.QWidget] = {}
        self._dock_live_host_layouts: Dict[str, QtWidgets.QVBoxLayout] = {}
        self._dock_detached_placeholders: Dict[str, QtWidgets.QWidget] = {}
        self._live_gl_layout_activity_callback: Optional[Callable[[str], None]] = None
        self._live_gl_guard_object_ids: Set[int] = set()
        self._live_gl_guard_dock_name: Optional[str] = None

        # UI layout mode: classic grid (debug) or Windows-like dock panels (recommended).
        if self.layout_mode in ("grid", "mosaic"):
            lay = QtWidgets.QGridLayout(self)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.setHorizontalSpacing(6)
            lay.setVerticalSpacing(6)
        else:
            lay = QtWidgets.QVBoxLayout(self)
            hint = QtWidgets.QLabel("Док-панели: окна/панели управляются в главном окне (меню 'Окна').")
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#666;")
            lay.addWidget(hint)
            lay.addStretch(1)
            self._docks = {}
            self._panel_to_dock_name: Dict[int, str] = {}

        # Axle L/R views: front + rear (requested)
        self.axleF = FrontViewWidget(axle="front")
        self.axleR = FrontViewWidget(axle="rear")
        self.sideL = SideViewWidget(mode="left")
        self.sideR = SideViewWidget(mode="right")
        self.hud = RoadHudWidget()
        # Compact summary/controls dock; heavy telemetry panels live in their own windows.
        self.telemetry = TelemetryPanel(compact=True)
        self.telemetry_heatmap = CornerHeatmapPanel()
        self.telemetry_corner_quick = CornerQuickTable()
        self.telemetry_road_profile = RoadProfilePanel()
        self.telemetry_corner_table = CornerTable()
        self.telemetry_press_panel = PressurePanel()
        self.telemetry_flow_panel = FlowPanel()
        self.telemetry_valve_panel = ValvePanel()

        # R54: extra glanceable widgets (events + trends)
        self.timeline = EventTimelineWidget()
        self.trends = TrendsPanel()

        try:
            self.timeline.seek_index.connect(self.seek_requested.emit)
        except Exception:
            pass

        self.car3d = Car3DWidget() if enable_gl else None

        if self.layout_mode in ("grid", "mosaic"):
            def _wrap(title: str, w: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
                gb = QtWidgets.QGroupBox(title)
                gb.setStyleSheet("QGroupBox{font-weight:600;}")
                glay = QtWidgets.QVBoxLayout(gb)
                glay.setContentsMargins(6, 18, 6, 6)
                glay.addWidget(w)
                return gb

            # Layout: 3 rows of views + right telemetry (spanning)
            # Row 0: 3D + Road HUD
            # Row 1: Front axle (L/R) + Rear axle (L/R)
            # Row 2: Side LEFT + Side RIGHT
            # Row 3: Events + Trends
            if self.car3d is not None:
                lay.addWidget(_wrap("3D (car + road)", self.car3d), 0, 0)
            else:
                lay.addWidget(_wrap("3D", QtWidgets.QLabel("3D disabled (--no-gl)")), 0, 0)

            lay.addWidget(_wrap("Road HUD — turns + ax/ay", self.hud), 0, 1)

            lay.addWidget(_wrap("Axle FRONT (L/R) — roll + z", self.axleF), 1, 0)
            lay.addWidget(_wrap("Axle REAR (L/R) — roll + z", self.axleR), 1, 1)

            lay.addWidget(_wrap("Side LEFT (F/R) — pitch + z", self.sideL), 2, 0)
            lay.addWidget(_wrap("Side RIGHT (F/R) — pitch + z", self.sideR), 2, 1)

            # Bottom: events + trends (glanceable)
            bottom = QtWidgets.QWidget()
            bl = QtWidgets.QVBoxLayout(bottom)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(6)

            gb_tl = QtWidgets.QGroupBox("Events timeline")
            gb_tl.setStyleSheet("QGroupBox{font-weight:600;}")
            tl = QtWidgets.QVBoxLayout(gb_tl)
            tl.setContentsMargins(6, 18, 6, 6)
            tl.addWidget(self.timeline)
            bl.addWidget(gb_tl)

            gb_tr = QtWidgets.QGroupBox("Trends (sparklines)")
            gb_tr.setStyleSheet("QGroupBox{font-weight:600;}")
            tr = QtWidgets.QVBoxLayout(gb_tr)
            tr.setContentsMargins(6, 18, 6, 6)
            tr.addWidget(self.trends)
            bl.addWidget(gb_tr)

            lay.addWidget(bottom, 3, 0, 1, 2)
            lay.addWidget(self.telemetry, 0, 2, 4, 1)

            lay.setColumnStretch(0, 2)
            lay.setColumnStretch(1, 2)
            lay.setColumnStretch(2, 1)

            lay.setRowStretch(0, 3)
            lay.setRowStretch(1, 3)
            lay.setRowStretch(2, 3)
            lay.setRowStretch(3, 1)

        self.geom = ViewGeometry()

        # Auto-fit scaling when panels are resized.
        # Goal: keep correct metric proportions and avoid clipping when user resizes panes.
        self._fit_timer = QtCore.QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._update_global_px_per_m)
        for _w in (self.axleF, self.axleR, self.sideL, self.sideR):
            try:
                _w.installEventFilter(self)
            except Exception:
                pass

        # Telemetry -> visualization toggles
        try:
            self.telemetry.visual_changed.connect(self._on_visual_changed)
        except Exception:
            pass
        # Apply initial config (and also safe if the signal hasn't fired yet)
        try:
            self._on_visual_changed(self.telemetry.current_visual())
        except Exception:
            pass

    def reset_views(self) -> None:
        for av in (self.axleF, self.axleR, self.sideL, self.sideR):
            try:
                av.reset_user_zoom()
            except Exception:
                pass
        try:
            self._update_global_px_per_m()
        except Exception:
            pass
        try:
            self.hud._auto_view_fit = True
            self.hud.fitInView(self.hud.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
        except Exception:
            pass
        if self.car3d is not None:
            try:
                self.car3d.fit_camera_to_geometry()
            except Exception:
                pass

    def install_docks(self, main: QtWidgets.QMainWindow) -> None:
        """Install cockpit panels into a QMainWindow as independent floating windows.

        Project requirement:
        - every animator panel must be a separate detachable window;
        - every panel must remain toggleable, movable and resizable;
        - no panel may be hard-wired as an immovable central view.
        """

        if getattr(self, "_docks_installed", False):
            return
        self._docks_installed = True

        try:
            main.setDockNestingEnabled(True)
        except Exception:
            pass

        menubar = main.menuBar()
        menu_windows: Optional[QtWidgets.QMenu] = None
        for act in menubar.actions():
            m = act.menu()
            if m is None:
                continue
            t = act.text().replace("&", "").strip().lower()
            if t in ("окна", "панели", "windows", "view"):
                menu_windows = m
                break
        if menu_windows is None:
            menu_windows = menubar.addMenu("Окна")
        self._menu_windows = menu_windows

        def _wrap_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
            sa = QtWidgets.QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QtWidgets.QFrame.NoFrame)
            sa.setWidget(widget)
            return sa

        def _dock(*, obj_name: str, title: str, widget: QtWidgets.QWidget, area: QtCore.Qt.DockWidgetArea, tooltip: str, scroll: bool = False, register_toggle: bool = True) -> QtWidgets.QDockWidget:
            dock = QtWidgets.QDockWidget(title, main)
            dock.setObjectName(obj_name)
            dock.setToolTip(tooltip)
            dock.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
            dock.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
                | QtWidgets.QDockWidget.DockWidgetClosable
            )
            dock.setWidget(_wrap_scroll(widget) if scroll else widget)
            main.addDockWidget(area, dock)
            if register_toggle:
                act = dock.toggleViewAction()
                try:
                    act.setText(title)
                except Exception:
                    pass
                menu_windows.addAction(act)
            self._docks[obj_name] = dock
            try:
                self._panel_to_dock_name[id(widget)] = str(obj_name)
            except Exception:
                pass
            try:
                dock.visibilityChanged.connect(lambda visible, _name=str(obj_name): self._on_dock_visibility_changed(_name, bool(visible)))
            except Exception:
                pass
            try:
                if hasattr(widget, "set_compact_dock_mode"):
                    getattr(widget, "set_compact_dock_mode")(not bool(dock.isFloating()))
                    dock.topLevelChanged.connect(
                        lambda floating, _widget=widget: getattr(_widget, "set_compact_dock_mode")(not bool(floating))
                    )
            except Exception:
                pass
            return dock

        # Keep the main window practically empty so that all functional views live in docks/windows.
        central_placeholder = QtWidgets.QWidget()
        central_placeholder.setObjectName("dock_center_placeholder")
        try:
            central_placeholder.setMinimumSize(0, 0)
            central_placeholder.setMaximumSize(1, 1)
            central_placeholder.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            central_placeholder.hide()
        except Exception:
            pass
        main.setCentralWidget(central_placeholder)

        gl_is_live = bool(self.car3d is not None and self.car3d.has_live_gl_context())

        widget_3d: QtWidgets.QWidget
        if self.car3d is not None:
            widget_3d = self.car3d
        else:
            widget_3d = QtWidgets.QLabel("3D отключён (--no-gl)")
        dock_3d = _dock(
            obj_name="dock_3d",
            title="3D: Кузов/дорога/контакт",
            widget=widget_3d,
            area=QtCore.Qt.RightDockWidgetArea,
            tooltip=(
                "Основное 3D окно. Это обычная dock/floating панель: её можно пристыковывать обратно к другим "
                "окнам. Во время перемещения/ресайза live GL playback временно ставится на паузу и "
                "автоматически обновляется после стабилизации layout."
            ),
        )
        if gl_is_live and self.car3d is not None:
            self._register_live_gl_layout_guard("dock_3d", dock_3d)

        _dock(
            obj_name="dock_hud",
            title="Road HUD",
            widget=self.hud,
            area=QtCore.Qt.TopDockWidgetArea,
            tooltip="Road HUD как отдельное окно. Можно скрывать, перетаскивать и менять размер.",
        )
        _dock(
            obj_name="dock_front",
            title="2D: Спереди",
            widget=self.axleF,
            area=QtCore.Qt.LeftDockWidgetArea,
            tooltip="Вид спереди (колёса прямоугольники). Локальный уровень дороги под колесом.",
        )
        _dock(
            obj_name="dock_rear",
            title="2D: Сзади",
            widget=self.axleR,
            area=QtCore.Qt.LeftDockWidgetArea,
            tooltip="Вид сзади (колёса прямоугольники). Локальный уровень дороги под колесом.",
        )
        _dock(
            obj_name="dock_left",
            title="2D: Слева",
            widget=self.sideL,
            area=QtCore.Qt.RightDockWidgetArea,
            tooltip="Вид слева (колёса окружности). Профиль дороги и подвеска.",
        )
        _dock(
            obj_name="dock_right",
            title="2D: Справа",
            widget=self.sideR,
            area=QtCore.Qt.RightDockWidgetArea,
            tooltip="Вид справа (колёса окружности). Профиль дороги и подвеска.",
        )
        _dock(
            obj_name="dock_telemetry",
            title="Телеметрия: сводка и управление",
            widget=self.telemetry,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Компактная сводка движения, визуальные переключатели и быстрая пневматика.",
            scroll=False,
        )
        _dock(
            obj_name="dock_heatmap",
            title="Heatmap углов",
            widget=self.telemetry_heatmap,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Отдельное окно heatmap по углам подвески.",
        )
        _dock(
            obj_name="dock_corner_quick",
            title="Углы: быстро",
            widget=self.telemetry_corner_quick,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Быстрая таблица z/дефлексия/шток/контакт по углам.",
        )
        _dock(
            obj_name="dock_road_profile",
            title="Профиль дороги",
            widget=self.telemetry_road_profile,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Отдельное окно реального профиля дороги под колёсами.",
        )
        _dock(
            obj_name="dock_corner_table",
            title="Углы: подробно",
            widget=self.telemetry_corner_table,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Подробная таблица по углам и колёсам.",
            scroll=True,
        )
        _dock(
            obj_name="dock_pressures",
            title="Пневматика: давления",
            widget=self.telemetry_press_panel,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Подробные давления по узлам и ресиверам.",
            scroll=True,
        )
        _dock(
            obj_name="dock_flows",
            title="Пневматика: расходы",
            widget=self.telemetry_flow_panel,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Подробные массовые расходы по линиям.",
            scroll=True,
        )
        _dock(
            obj_name="dock_valves",
            title="Пневматика: клапаны",
            widget=self.telemetry_valve_panel,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Подробное состояние клапанов.",
            scroll=True,
        )
        _dock(
            obj_name="dock_trends",
            title="Тренды",
            widget=self.trends,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Короткие графики вокруг текущего времени.",
        )
        _dock(
            obj_name="dock_timeline",
            title="Таймлайн теста",
            widget=self.timeline,
            area=QtCore.Qt.BottomDockWidgetArea,
            tooltip="Сегменты/манёвры. Клик — переход к моменту времени.",
        )

        try:
            menu_windows.addSeparator()
            act_show_all = menu_windows.addAction("Показать все панели")
            act_show_all.triggered.connect(self.show_all_docks)
            act_detach = menu_windows.addAction("Разнести панели в отдельные окна")
            act_detach.triggered.connect(lambda: self.enforce_detached_windows(main, reset_geometry=True))
        except Exception:
            pass

    def set_live_gl_layout_activity_callback(self, cb: Optional[Callable[[str], None]]) -> None:
        self._live_gl_layout_activity_callback = cb

    def _notify_live_gl_layout_activity(self, reason: str) -> None:
        cb = getattr(self, "_live_gl_layout_activity_callback", None)
        if cb is None:
            return
        try:
            cb(str(reason))
        except Exception:
            pass

    def _register_live_gl_layout_guard(self, dock_name: str, dock: QtWidgets.QDockWidget) -> None:
        if self.car3d is None:
            return
        name = str(dock_name)
        self._live_gl_guard_dock_name = name
        observed: Set[int] = set()
        # Only observe the dock widget itself. Watching the internal GL widget and its
        # viewport causes a flood of Move/Resize/Show events during floating/re-dock and
        # leads to repeated layout-transition churn exactly when Windows/OpenGL is least
        # stable. The dock-level signals + dock move/resize are enough to gate playback.
        try:
            observed.add(id(dock))
            dock.installEventFilter(self)
        except Exception:
            pass
        self._live_gl_guard_object_ids = observed
        try:
            dock.topLevelChanged.connect(lambda _floating, _name=name: self._notify_live_gl_layout_activity(f"{_name}:topLevelChanged"))
        except Exception:
            pass
        try:
            dock.dockLocationChanged.connect(lambda _area, _name=name: self._notify_live_gl_layout_activity(f"{_name}:dockLocationChanged"))
        except Exception:
            pass

    def set_gl_layout_transition_active(self, active: bool) -> None:
        if self.car3d is None:
            return
        try:
            self.car3d.set_layout_transition_active(bool(active))
        except Exception:
            pass

    def _uses_external_panel_window(self, dock_name: str) -> bool:
        name = str(dock_name)
        return bool(dict(getattr(self, "_dock_external_mode", {}) or {}).get(name, False)) and name in dict(getattr(self, "_external_windows", {}) or {})

    def _sync_external_panel_action(self, dock_name: str, visible: bool) -> None:
        action = dict(getattr(self, "_external_window_actions", {}) or {}).get(str(dock_name))
        if action is None:
            return
        try:
            if bool(action.isChecked()) == bool(visible):
                return
        except Exception:
            pass
        try:
            blocked = action.blockSignals(True)
        except Exception:
            blocked = None
        try:
            action.setChecked(bool(visible))
        except Exception:
            pass
        finally:
            try:
                if blocked is not None:
                    action.blockSignals(bool(blocked))
            except Exception:
                pass

    def _set_panel_external_mode(self, dock_name: str, enabled: bool) -> None:
        name = str(dock_name)
        window = dict(getattr(self, "_external_windows", {}) or {}).get(name)
        if window is None:
            return
        docks = dict(getattr(self, "_docks", {}) or {})
        dock = docks.get(name)
        live_widget = dict(getattr(self, "_dock_live_widgets", {}) or {}).get(name)
        host_layout = dict(getattr(self, "_dock_live_host_layouts", {}) or {}).get(name)
        placeholder = dict(getattr(self, "_dock_detached_placeholders", {}) or {}).get(name)
        if live_widget is None or host_layout is None:
            self._dock_external_mode[name] = bool(enabled)
            return
        current = bool(dict(getattr(self, "_dock_external_mode", {}) or {}).get(name, False))
        if current == bool(enabled):
            return

        def _layout_remove(widget: Optional[QtWidgets.QWidget]) -> None:
            if widget is None:
                return
            try:
                host_layout.removeWidget(widget)
            except Exception:
                pass
            try:
                widget.setParent(None)
            except Exception:
                pass

        if bool(enabled):
            _layout_remove(live_widget)
            if placeholder is not None:
                try:
                    if host_layout.indexOf(placeholder) < 0:
                        host_layout.addWidget(placeholder)
                except Exception:
                    try:
                        host_layout.addWidget(placeholder)
                    except Exception:
                        pass
                try:
                    placeholder.show()
                except Exception:
                    pass
            try:
                window.set_panel_widget(live_widget)
            except Exception:
                pass
            try:
                if hasattr(live_widget, "set_compact_dock_mode"):
                    getattr(live_widget, "set_compact_dock_mode")(False)
            except Exception:
                pass
            self._dock_external_mode[name] = True
        else:
            try:
                if window.panel_widget() is live_widget:
                    window.take_panel_widget()
            except Exception:
                try:
                    live_widget.setParent(None)
                except Exception:
                    pass
            if placeholder is not None:
                try:
                    host_layout.removeWidget(placeholder)
                except Exception:
                    pass
                try:
                    placeholder.hide()
                except Exception:
                    pass
            try:
                if host_layout.indexOf(live_widget) < 0:
                    host_layout.addWidget(live_widget)
            except Exception:
                try:
                    host_layout.addWidget(live_widget)
                except Exception:
                    pass
            try:
                live_widget.show()
            except Exception:
                pass
            try:
                if hasattr(live_widget, "set_compact_dock_mode"):
                    getattr(live_widget, "set_compact_dock_mode")(not bool(dock.isFloating()) if dock is not None else True)
            except Exception:
                pass
            self._dock_external_mode[name] = False

    def _handle_external_window_visibility_change(self, dock_name: str, visible: bool) -> None:
        name = str(dock_name)
        docks = dict(getattr(self, "_docks", {}) or {})
        dock = docks.get(name)
        if not bool(visible) and bool(dict(getattr(self, "_dock_external_mode", {}) or {}).get(name, False)):
            self._set_panel_external_mode(name, False)
            try:
                if dock is not None:
                    dock.show()
            except Exception:
                pass
        self._sync_external_panel_action(name, bool(self._uses_external_panel_window(name) and visible))
        if bool(visible):
            try:
                self._on_dock_visibility_changed(name, True)
            except Exception:
                pass

    def _set_external_panel_visible(self, dock_name: str, visible: bool) -> None:
        name = str(dock_name)
        window = dict(getattr(self, "_external_windows", {}) or {}).get(name)
        docks = dict(getattr(self, "_docks", {}) or {})
        dock = docks.get(name)
        if window is None:
            return
        if bool(visible):
            self._set_panel_external_mode(name, True)
            try:
                if dock is not None:
                    dock.hide()
            except Exception:
                pass
            try:
                if bool(window.isMinimized()):
                    window.showNormal()
            except Exception:
                pass
            try:
                window.show()
            except Exception:
                pass
            try:
                window.raise_()
                window.activateWindow()
            except Exception:
                pass
        else:
            self._set_panel_external_mode(name, False)
            try:
                window.hide()
            except Exception:
                pass
            try:
                if dock is not None:
                    dock.show()
            except Exception:
                pass
        self._sync_external_panel_action(name, bool(self._uses_external_panel_window(name) and visible))

    def _register_external_panel_window(self, *, dock_name: str, title: str, widget: Optional[QtWidgets.QWidget], tooltip: str, menu_windows: QtWidgets.QMenu, main: QtWidgets.QMainWindow) -> ExternalPanelWindow:
        name = str(dock_name)
        windows = dict(getattr(self, "_external_windows", {}) or {})
        if name in windows:
            return windows[name]

        window = ExternalPanelWindow(dock_name=name, title=title, widget=widget, tooltip=tooltip)
        try:
            if widget is not None:
                window.resize(max(820, int(widget.sizeHint().width() or 0)), max(520, int(widget.sizeHint().height() or 0)))
            else:
                window.resize(980, 640)
        except Exception:
            pass
        self._external_windows[name] = window
        if widget is not None:
            try:
                self._panel_to_dock_name[id(widget)] = name
            except Exception:
                pass
        try:
            window.visibilityChanged.connect(lambda visible, _name=name: self._handle_external_window_visibility_change(_name, bool(visible)))
        except Exception:
            pass

        action = QtGui.QAction(title, main)
        action.setCheckable(True)
        action.setChecked(False)
        action.toggled.connect(lambda checked, _name=name: self._set_external_panel_visible(_name, bool(checked)))
        menu_windows.addAction(action)
        self._external_window_actions[name] = action
        return window

    def restore_external_panel_state(self, settings: Optional[QtCore.QSettings]) -> None:
        if settings is None:
            return
        prefix = str(getattr(self, "_external_window_settings_key_prefix", "window/panel_external/"))
        for name, window in dict(getattr(self, "_external_windows", {}) or {}).items():
            try:
                geo = settings.value(f"{prefix}{name}/geometry", None)
                if geo is not None:
                    window.restoreGeometry(geo)
            except Exception:
                pass
            visible = None
            try:
                raw_visible = settings.value(f"{prefix}{name}/visible", None)
                if raw_visible is not None:
                    visible = bool(int(raw_visible))
            except Exception:
                visible = None
            if visible is None:
                try:
                    self._set_external_panel_visible(name, False)
                except Exception:
                    try:
                        window.hide()
                    except Exception:
                        pass
                self._sync_external_panel_action(name, False)
                continue
            try:
                self._set_external_panel_visible(name, bool(visible))
            except Exception:
                try:
                    if bool(visible):
                        window.show()
                    else:
                        window.hide()
                except Exception:
                    pass
            self._sync_external_panel_action(name, bool(self._uses_external_panel_window(name) and visible))

    def save_external_panel_state(self, settings: Optional[QtCore.QSettings]) -> None:
        if settings is None:
            return
        prefix = str(getattr(self, "_external_window_settings_key_prefix", "window/panel_external/"))
        for name, window in dict(getattr(self, "_external_windows", {}) or {}).items():
            try:
                settings.setValue(f"{prefix}{name}/geometry", window.saveGeometry())
            except Exception:
                pass
            try:
                visible = bool(self._uses_external_panel_window(name) and window.isVisible())
                settings.setValue(f"{prefix}{name}/visible", int(visible))
            except Exception:
                pass

    def close_external_panel_windows(self) -> None:
        for window in tuple(dict(getattr(self, "_external_windows", {}) or {}).values()):
            try:
                window.force_close()
            except Exception:
                pass

    def show_all_docks(self) -> None:
        docks = dict(getattr(self, "_docks", {}) or {})
        external_names = set(dict(getattr(self, "_external_windows", {}) or {}).keys())
        for name, dock in tuple(docks.items()):
            try:
                dock.show()
            except Exception:
                pass
            if str(name) in external_names and not self._uses_external_panel_window(str(name)):
                try:
                    dict(getattr(self, "_external_windows", {}) or {})[str(name)].hide()
                except Exception:
                    pass
        for name in external_names:
            if self._uses_external_panel_window(str(name)):
                self._set_external_panel_visible(str(name), True)

    def enforce_detached_windows(self, main: QtWidgets.QMainWindow, *, reset_geometry: bool = False) -> None:
        docks = dict(getattr(self, "_docks", {}) or {})
        external_windows = dict(getattr(self, "_external_windows", {}) or {})
        if not docks and not external_windows:
            return

        screen = None
        try:
            wh = main.windowHandle()
            if wh is not None:
                screen = wh.screen()
        except Exception:
            screen = None
        if screen is None:
            try:
                screen = QtGui.QGuiApplication.screenAt(main.frameGeometry().center())
            except Exception:
                screen = None
        if screen is None:
            try:
                screen = QtGui.QGuiApplication.primaryScreen()
            except Exception:
                screen = None
        try:
            avail = screen.availableGeometry() if screen is not None else main.geometry()
        except Exception:
            avail = main.geometry()

        try:
            dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
        except Exception:
            dpr = 1.0
        try:
            dpi_scale = float(screen.logicalDotsPerInch()) / 96.0 if screen is not None else 1.0
        except Exception:
            dpi_scale = 1.0
        ui_scale = float(max(1.0, dpr, dpi_scale))

        margin = int(16 * ui_scale)
        gap = int(10 * ui_scale)
        left = int(avail.left()) + margin
        top = int(avail.top()) + margin
        span_w = max(1080, int(avail.width() - 2 * margin))
        span_h = max(760, int(avail.height() - 2 * margin))

        # Screen-aware tiling: 4 columns x 5 rows, with a larger dedicated 3D window.
        grid_cols = 4
        grid_rows = 5
        cell_w = max(int(250 * ui_scale), int((span_w - gap * (grid_cols - 1)) / grid_cols))
        cell_h = max(int(146 * ui_scale), int((span_h - gap * (grid_rows - 1)) / grid_rows))
        default_layout = {
            "dock_3d": (0, 0, 2, 2),
            "dock_hud": (0, 2, 1, 1),
            "dock_front": (0, 3, 1, 1),
            "dock_rear": (1, 2, 1, 1),
            "dock_left": (1, 3, 1, 1),
            "dock_right": (2, 0, 1, 1),
            "dock_telemetry": (2, 1, 1, 1),
            "dock_heatmap": (2, 2, 1, 1),
            "dock_corner_quick": (2, 3, 1, 1),
            "dock_road_profile": (3, 0, 1, 1),
            "dock_corner_table": (3, 1, 1, 1),
            "dock_pressures": (3, 2, 1, 1),
            "dock_flows": (3, 3, 1, 1),
            "dock_valves": (4, 0, 1, 1),
            "dock_trends": (4, 1, 1, 1),
            "dock_timeline": (4, 2, 1, 2),
        }

        for name, dock in docks.items():
            if str(name) in external_windows:
                try:
                    dock.hide()
                except Exception:
                    pass
                window = external_windows.get(str(name))
                was_visible = False
                if window is not None:
                    try:
                        was_visible = bool(window.isVisible())
                    except Exception:
                        was_visible = False
                    self._set_external_panel_visible(str(name), True)
                if window is not None and (reset_geometry or (not was_visible)):
                    row, col, row_span, col_span = default_layout.get(str(name), (0, 0, 1, 1))
                    width = max(int(260 * ui_scale), col_span * cell_w + (col_span - 1) * gap)
                    height = max(int(150 * ui_scale), row_span * cell_h + (row_span - 1) * gap)
                    x = left + col * (cell_w + gap)
                    y = top + row * (cell_h + gap)
                    max_x = int(avail.right()) - width - margin
                    max_y = int(avail.bottom()) - height - margin
                    x = max(int(avail.left()) + margin, min(x, max_x))
                    y = max(int(avail.top()) + margin, min(y, max_y))
                    try:
                        if bool(window.isMinimized()):
                            window.showNormal()
                    except Exception:
                        pass
                    try:
                        window.resize(width, height)
                        window.move(x, y)
                    except Exception:
                        pass
                    try:
                        window.raise_()
                        window.activateWindow()
                    except Exception:
                        pass
                try:
                    if not bool(getattr(self, "_gl_external_window_warning_emitted", False)):
                        _emit_animator_warning(
                            "3D GL panel uses a safe dedicated top-level window only when you explicitly detach panels; docked mode remains the default to preserve normal snapping/layout behaviour.",
                            code="gl_safe_external_window_on_detach",
                        )
                        self._gl_external_window_warning_emitted = True
                except Exception:
                    pass
                continue

            try:
                was_floating = bool(dock.isFloating())
            except Exception:
                was_floating = False

            try:
                dock.show()
                dock.setFloating(True)
            except Exception:
                pass

            if reset_geometry or (not was_floating):
                row, col, row_span, col_span = default_layout.get(name, (0, 0, 1, 1))
                width = max(int(260 * ui_scale), col_span * cell_w + (col_span - 1) * gap)
                height = max(int(150 * ui_scale), row_span * cell_h + (row_span - 1) * gap)
                x = left + col * (cell_w + gap)
                y = top + row * (cell_h + gap)
                max_x = int(avail.right()) - width - margin
                max_y = int(avail.bottom()) - height - margin
                x = max(int(avail.left()) + margin, min(x, max_x))
                y = max(int(avail.top()) + margin, min(y, max_y))
                try:
                    dock.resize(width, height)
                    dock.move(x, y)
                except Exception:
                    pass
            try:
                dock.raise_()
            except Exception:
                pass

    def _dock_is_visible(self, dock_name: str) -> bool:
        name = str(dock_name)
        if self._uses_external_panel_window(name):
            window = dict(getattr(self, "_external_windows", {}) or {}).get(name)
            if window is None:
                return False
            try:
                return bool(window.isVisible())
            except Exception:
                return False
        docks = dict(getattr(self, "_docks", {}) or {})
        dock = docks.get(name)
        if dock is None:
            return True
        try:
            return bool(dock.isVisible())
        except Exception:
            return True

    def _dock_is_exposed(self, dock_name: str) -> bool:
        """Best-effort on-screen check for docked auxiliary panes."""
        name = str(dock_name)
        if self._uses_external_panel_window(name):
            window = dict(getattr(self, "_external_windows", {}) or {}).get(name)
            if window is None:
                return False
            try:
                if not bool(window.isVisible()):
                    return False
            except Exception:
                return False
            try:
                if bool(window.isMinimized()):
                    return False
            except Exception:
                pass
            return True
        docks = dict(getattr(self, "_docks", {}) or {})
        dock = docks.get(name)
        if dock is None:
            return True
        try:
            if not bool(dock.isVisible()):
                return False
        except Exception:
            return False
        try:
            if bool(dock.isFloating()) and bool(dock.window().isMinimized()):
                return False
        except Exception:
            pass
        try:
            w = dock.widget()
            if w is not None:
                if not bool(w.isVisibleTo(dock)):
                    return False
                reg = w.visibleRegion()
                if reg is not None and bool(reg.isEmpty()):
                    return False
        except Exception:
            pass
        return True

    def _focused_dock_name(self) -> Optional[str]:
        docks = dict(getattr(self, "_docks", {}) or {})
        external_windows = dict(getattr(self, "_external_windows", {}) or {})
        try:
            app = QtWidgets.QApplication.instance()
            fw = app.focusWidget() if app is not None else None
        except Exception:
            fw = None
        if fw is None:
            return None
        for name, window in external_windows.items():
            try:
                if fw is window or bool(window.isAncestorOf(fw)):
                    return str(name)
            except Exception:
                continue
        for name, dock in docks.items():
            try:
                if fw is dock or bool(dock.isAncestorOf(fw)):
                    return str(name)
            except Exception:
                continue
        return None

    def _visible_aux_dock_count(self) -> int:
        docks = dict(getattr(self, "_docks", {}) or {})
        count = 0
        for name in docks.keys():
            if str(name) == "dock_3d":
                continue
            if self._dock_is_exposed(str(name)):
                count += 1
        return int(count)

    def _apply_playback_perf_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == bool(self._playback_perf_mode_active):
            return
        self._playback_perf_mode_active = enabled
        for panel in (self.axleF, self.axleR, self.sideL, self.sideR, self.hud):
            try:
                panel.set_playback_perf_mode(enabled)
            except Exception:
                pass
        if self.car3d is not None:
            try:
                self.car3d.set_playback_perf_mode(enabled)
            except Exception:
                pass


    def _reset_aux_cadence_window(self, now_ts: float) -> None:
        self._aux_cadence_window_started_ts = float(now_ts)
        self._aux_cadence_stats = {}

    def _record_aux_cadence(self, dock_name: str, now_ts: float) -> None:
        name = str(dock_name)
        ts = float(now_ts)
        if self._aux_cadence_window_started_ts <= 0.0:
            self._aux_cadence_window_started_ts = ts
        stats = self._aux_cadence_stats.setdefault(
            name,
            {
                "count": 0.0,
                "first_ts": ts,
                "last_ts": ts,
                "dt_min_ms": float("inf"),
                "dt_max_ms": 0.0,
            },
        )
        last_ts = float(stats.get("last_ts", ts))
        count = int(round(float(stats.get("count", 0.0))))
        if count > 0:
            dt_ms = max(0.0, (ts - last_ts) * 1000.0)
            stats["dt_min_ms"] = float(min(float(stats.get("dt_min_ms", dt_ms)), dt_ms))
            stats["dt_max_ms"] = float(max(float(stats.get("dt_max_ms", dt_ms)), dt_ms))
        else:
            stats["first_ts"] = ts
        stats["count"] = float(count + 1)
        stats["last_ts"] = ts

    def _emit_aux_cadence_metrics(self, now_ts: float, *, playing: bool, many_visible_budget: bool, force: bool = False) -> None:
        ts = float(now_ts)
        if self._aux_cadence_window_started_ts <= 0.0:
            self._aux_cadence_window_started_ts = ts
            return
        window_s = max(0.0, ts - float(self._aux_cadence_window_started_ts))
        if not force and window_s < float(max(0.25, self._aux_cadence_emit_period_s)):
            return
        payload: Dict[str, Any] = {}
        for name, raw in sorted(self._aux_cadence_stats.items()):
            count = int(round(float(raw.get("count", 0.0))))
            first_ts = float(raw.get("first_ts", ts))
            last_ts = float(raw.get("last_ts", ts))
            active_s = max(1e-6, last_ts - first_ts)
            hz = float((count - 1) / active_s) if count > 1 else (1.0 / max(window_s, 1e-6) if count == 1 else 0.0)
            dt_min_ms = float(raw.get("dt_min_ms", 0.0))
            if not np.isfinite(dt_min_ms):
                dt_min_ms = 0.0
            payload[str(name)] = {
                "count": count,
                "hz": round(hz, 3),
                "dt_min_ms": round(dt_min_ms, 3),
                "dt_max_ms": round(float(raw.get("dt_max_ms", 0.0)), 3),
                "visible": bool(self._dock_is_exposed(str(name))),
            }
        if payload:
            try:
                from pneumo_solver_ui.diag.eventlog import get_global_logger
                get_global_logger(PROJECT_ROOT).emit(
                    "AnimatorAuxCadence",
                    "aux pane cadence window",
                    playing=bool(playing),
                    many_visible_budget=bool(many_visible_budget),
                    visible_aux=int(self._visible_aux_dock_count()),
                    window_s=round(window_s, 3),
                    panels=payload,
                )
            except Exception:
                pass
        self._reset_aux_cadence_window(ts)

    def _on_dock_visibility_changed(self, dock_name: str, visible: bool) -> None:
        if not bool(visible):
            return
        if self.bundle is None:
            return
        try:
            self.update_frame(self._last_i)
        except Exception:
            pass

    def _on_visual_changed(self, cfg: Dict[str, Any]):
        try:
            a_scale = float(cfg.get("accel_scale", 0.05))
            v_scale = float(cfg.get("vel_scale", 0.08))
            show_a = bool(cfg.get("show_accel", True))
            show_v = bool(cfg.get("show_vel", False))
            show_lbl = bool(cfg.get("show_labels", True))
            show_dims = bool(cfg.get("show_dims", False))
            show_scale_bar = bool(cfg.get("show_scale_bar", True))

            for av in (self.axleF, self.axleR):
                av.set_scales(a_scale, v_scale)
                av.set_visual(
                    show_accel=show_a,
                    show_vel=show_v,
                    show_labels=show_lbl,
                    show_dims=show_dims,
                    show_scale_bar=show_scale_bar,
                )

            for sv in (self.sideL, self.sideR):
                sv.set_scales(a_scale, v_scale)
                sv.set_visual(
                    show_accel=show_a,
                    show_vel=show_v,
                    show_labels=show_lbl,
                    show_dims=show_dims,
                    show_scale_bar=show_scale_bar,
                )

            self.hud.set_visual(
                show_lanes=bool(cfg.get("hud_lanes", True)),
                show_text=bool(cfg.get("hud_text", True)),
                show_accel=bool(cfg.get("hud_accel", True)),
                auto_lookahead=bool(cfg.get("hud_auto", True)),
            )

            if self.car3d is not None:
                self.car3d.set_scales(a_scale, v_scale)
                self.car3d.set_visual(
                    show_road=bool(cfg.get("gl_road", True)),
                    show_vectors=bool(cfg.get("gl_vectors", True)),
                )
        except Exception:
            pass

        # Immediate redraw
        if self.bundle is not None:
            try:
                self.update_frame(self._last_i)
            except Exception:
                pass

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # type: ignore
        # Coalesce resize events from metric views and recompute global scale.
        try:
            if event.type() == QtCore.QEvent.Type.Resize and hasattr(self, "_fit_timer"):
                # restart single-shot timer (avoids recomputing on every pixel drag)
                self._fit_timer.start(60)
        except Exception:
            pass
        try:
            live_ids = set(getattr(self, "_live_gl_guard_object_ids", set()) or set())
            if live_ids and id(obj) in live_ids:
                et = event.type()
                dock_is_floating = False
                try:
                    dock_is_floating = bool(isinstance(obj, QtWidgets.QDockWidget) and obj.isFloating())
                except Exception:
                    dock_is_floating = False
                should_notify = et in {
                    QtCore.QEvent.Type.Show,
                    QtCore.QEvent.Type.Hide,
                    QtCore.QEvent.Type.WindowStateChange,
                }
                if not should_notify and dock_is_floating and et in {
                    QtCore.QEvent.Type.Move,
                    QtCore.QEvent.Type.Resize,
                }:
                    should_notify = True
                if should_notify:
                    try:
                        name = str(getattr(obj, "objectName", lambda: "")() or obj.__class__.__name__)
                    except Exception:
                        name = obj.__class__.__name__
                    self._notify_live_gl_layout_activity(f"{name}:{int(et)}")
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def set_bundle(self, b: DataBundle):
        self.bundle = b
        try:
            self._bundle_meta = dict(b.meta or {})
        except Exception:
            self._bundle_meta = {}
        self.geom = infer_geometry(b.meta)
        self.axleF.set_geometry(self.geom)
        self.axleR.set_geometry(self.geom)
        self.sideL.set_geometry(self.geom)
        self.sideR.set_geometry(self.geom)
        for panel in (self.axleF, self.axleR, self.sideL, self.sideR):
            try:
                panel.set_bundle(b)
            except Exception:
                pass
        try:
            self.hud.set_geometry(self.geom)
        except Exception:
            pass


        # Configure 2D viewports once per bundle: fixed meters scene + shared px/m.
        try:
            self._configure_2d_view_limits(b)
        except Exception:
            pass

        try:
            self.telemetry.set_bundle(b)
        except Exception:
            pass
        for panel in (
            getattr(self, "telemetry_heatmap", None),
            getattr(self, "telemetry_corner_quick", None),
            getattr(self, "telemetry_road_profile", None),
            getattr(self, "telemetry_corner_table", None),
            getattr(self, "telemetry_press_panel", None),
            getattr(self, "telemetry_flow_panel", None),
            getattr(self, "telemetry_valve_panel", None),
        ):
            if panel is None or not hasattr(panel, 'set_bundle'):
                continue
            try:
                panel.set_bundle(b)
            except Exception:
                pass

        # R54: event timeline + trends (fully automatic, no mapping files)
        try:
            self.timeline.set_bundle(b)
        except Exception:
            pass
        try:
            self.trends.set_bundle(b)
        except Exception:
            pass

        # compute recommended vector scales from the log (minimal manual tuning)
        try:
            # vertical accelerations/velocities across CM + corners + wheels
            a_max = 0.0
            v_max = 0.0
            a_max = max(a_max, _robust_max_abs(b.get("ускорение_рамы_z_м_с2", 0.0)))
            v_max = max(v_max, _robust_max_abs(b.get("скорость_рамы_z_м_с", 0.0)))
            for c in CORNERS:
                a_max = max(a_max, _robust_max_abs(b.frame_corner_a(c, default=0.0)))
                v_max = max(v_max, _robust_max_abs(b.frame_corner_v(c, default=0.0)))
                a_max = max(a_max, _robust_max_abs(b.get(f"ускорение_колеса_{c}_м_с2", 0.0)))
                v_max = max(v_max, _robust_max_abs(b.get(f"скорость_колеса_{c}_м_с", 0.0)))
            a_max = float(a_max) if a_max > 1e-9 else 5.0
            v_max = float(v_max) if v_max > 1e-9 else 1.0
            target_len = 0.45  # meters in scene
            rec_a = float(_clamp(target_len / a_max, 0.005, 0.30))
            rec_v = float(_clamp(target_len / v_max, 0.005, 0.50))
            self.telemetry.set_recommended_scales(rec_a, rec_v)
        except Exception:
            pass
        self._reset_aux_cadence_window(time.perf_counter())
        if self.car3d is not None:
            self.car3d.set_geometry(self.geom)
            try:
                self.car3d.set_bundle_context(b)
            except Exception:
                pass
        try:
            self.reset_views()
        except Exception:
            pass

    # --------------------------
    # 2D view scaling & framing
    # --------------------------

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        # Recompute a single shared px/m across all 2D views when the layout changes.
        try:
            QtCore.QTimer.singleShot(0, self._update_global_px_per_m)
        except Exception:
            pass

    def _configure_2d_view_limits(self, b: DataBundle):
        """Configure 2D scenes in *meters* once per bundle.

        Why: we want stable, physically consistent proportions. Dynamic fitInView()
        makes scale drift frame-to-frame and breaks the "same scale everywhere" rule.
        """

        import numpy as _np

        def _minmax(*arrays: _np.ndarray) -> Tuple[float, float]:
            mn = float("inf")
            mx = float("-inf")
            for a in arrays:
                try:
                    aa = _np.asarray(a, dtype=float)
                    if aa.size == 0:
                        continue
                    vmin = float(_np.nanmin(aa))
                    vmax = float(_np.nanmax(aa))
                    if _np.isfinite(vmin):
                        mn = min(mn, vmin)
                    if _np.isfinite(vmax):
                        mx = max(mx, vmax)
                except Exception:
                    continue
            if not _np.isfinite(mn):
                mn = 0.0
            if not _np.isfinite(mx):
                mx = 0.0
            return mn, mx

        wheel_r = float(self.geom.wheel_radius)
        wheel_w = float(self.geom.wheel_width)
        wb = float(self.geom.wheelbase)
        tr = float(self.geom.track)
        frame_corner_z_cache = {
            # Cache canonical frame-corner trajectories once per bundle to keep all
            # 2D view framing sourced from the same strict helper contract.
            "ЛП": _np.asarray(b.frame_corner_z("ЛП", default=0.0), dtype=float),
            "ПП": _np.asarray(b.frame_corner_z("ПП", default=0.0), dtype=float),
            "ЛЗ": _np.asarray(b.frame_corner_z("ЛЗ", default=0.0), dtype=float),
            "ПЗ": _np.asarray(b.frame_corner_z("ПЗ", default=0.0), dtype=float),
        }

        # --- Axles (front/rear): x = lateral, y = z
        def _axle_limits(cL: str, cR: str) -> Tuple[float, float]:
            mn, mx = _minmax(
                frame_corner_z_cache[cL],
                frame_corner_z_cache[cR],
                b.get(f"перемещение_колеса_{cL}_м", 0.0),
                b.get(f"перемещение_колеса_{cR}_м", 0.0),
                b.get(f"дорога_{cL}_м", 0.0),
                b.get(f"дорога_{cR}_м", 0.0),
                b.get("перемещение_рамы_z_м", 0.0),
            )
            # Always include road zero reference in the viewport.
            mn = min(mn, 0.0)
            mx = max(mx, 0.0)
            # Expand to include wheel bottom/top + a readable margin.
            mn = mn - (1.25 * wheel_r) - 0.12
            mx = mx + (1.10 * wheel_r) + 0.22
            return mn, mx

        x_half = 0.5 * tr
        x_margin = max(0.10, 0.75 * wheel_w)
        x0 = -x_half - x_margin
        x1 = +x_half + x_margin

        z0, z1 = _axle_limits("ЛП", "ПП")
        self.axleF.scene.setSceneRect(x0, z0, x1 - x0, z1 - z0)
        self.axleF.centerOn(0.0, 0.5 * (z0 + z1))

        z0, z1 = _axle_limits("ЛЗ", "ПЗ")
        self.axleR.scene.setSceneRect(x0, z0, x1 - x0, z1 - z0)
        self.axleR.centerOn(0.0, 0.5 * (z0 + z1))

        # --- Sides (left/right): x = longitudinal, y = z
        def _side_limits(cF: str, cR: str) -> Tuple[float, float]:
            mn, mx = _minmax(
                frame_corner_z_cache[cF],
                frame_corner_z_cache[cR],
                b.get(f"перемещение_колеса_{cF}_м", 0.0),
                b.get(f"перемещение_колеса_{cR}_м", 0.0),
                b.get(f"дорога_{cF}_м", 0.0),
                b.get(f"дорога_{cR}_м", 0.0),
                b.get("перемещение_рамы_z_м", 0.0),
            )
            mn = min(mn, 0.0)
            mx = max(mx, 0.0)
            mn = mn - (1.25 * wheel_r) - 0.12
            mx = mx + (1.10 * wheel_r) + 0.22
            return mn, mx

        x_half = 0.5 * wb
        x_margin = max(0.16, 1.40 * wheel_r)
        x0 = -x_half - x_margin
        x1 = +x_half + x_margin

        z0, z1 = _side_limits("ЛП", "ЛЗ")
        self.sideL.scene.setSceneRect(x0, z0, x1 - x0, z1 - z0)
        self.sideL.centerOn(0.0, 0.5 * (z0 + z1))

        z0, z1 = _side_limits("ПП", "ПЗ")
        self.sideR.scene.setSceneRect(x0, z0, x1 - x0, z1 - z0)
        self.sideR.centerOn(0.0, 0.5 * (z0 + z1))

        # After scene rects are set (meters), choose ONE shared px/m so all views
        # are on the same scale and still fit their viewports.
        try:
            QtCore.QTimer.singleShot(0, self._update_global_px_per_m)
        except Exception:
            self._update_global_px_per_m()

    def _update_global_px_per_m(self):
        """Pick a shared px/m based on current viewports.

        Uses the smallest scale needed so that *all* 2D scenes fit. This keeps the
        front/rear and left/right views comparable at a glance.
        """

        views: List[QtWidgets.QGraphicsView] = [self.axleF, self.axleR, self.sideL, self.sideR]
        scales: List[float] = []
        for v in views:
            try:
                rect = v.scene.sceneRect()
                if rect.width() <= 1e-9 or rect.height() <= 1e-9:
                    continue
                vw = max(50, int(v.viewport().width()))
                vh = max(50, int(v.viewport().height()))
                s = min(vw / float(rect.width()), vh / float(rect.height()))
                if math.isfinite(s) and s > 1.0:
                    scales.append(float(s))
            except Exception:
                continue

        if not scales:
            return

        px_per_m = float(min(scales) * 0.95)
        px_per_m = float(_clamp(px_per_m, 60.0, 380.0))

        for v in views:
            try:
                v.set_px_per_m(px_per_m)
            except Exception:
                pass

    def set_playback_sample_t(self, sample_t: float | None) -> None:
        if sample_t is None:
            self._playback_sample_t_s = None
            return
        try:
            ts = float(sample_t)
        except Exception:
            self._playback_sample_t_s = None
            return
        self._playback_sample_t_s = ts if np.isfinite(ts) else None

    def reset_interactive_scrub_budget(self) -> None:
        self._interactive_scrub_slow_rr_cursor = 0
        self._aux_fast_last_ts = 0.0
        self._aux_slow_last_ts = float(time.perf_counter())

    def _take_interactive_scrub_slow_batch(
        self,
        entries: List[Tuple[str, Any, str]],
    ) -> tuple[List[Tuple[str, Any, str]], bool]:
        if not entries:
            self._interactive_scrub_slow_rr_cursor = 0
            return [], True
        n = int(len(entries))
        batch_size = int(max(1, min(int(getattr(self, "_interactive_scrub_slow_batch_size", 3)), n)))
        start = int(getattr(self, "_interactive_scrub_slow_rr_cursor", 0)) % n
        batch = [entries[(start + k) % n] for k in range(batch_size)]
        cursor = (start + batch_size) % n
        self._interactive_scrub_slow_rr_cursor = cursor
        return batch, cursor == 0

    def flush_interactive_scrub_detail_batch(self, i: int, *, sample_t: float | None = None) -> bool:
        b = self.bundle
        if b is None:
            return True
        n = len(b.t)
        if n <= 0:
            return True
        idx = int(_clamp(int(i), 0, n - 1))
        self._last_i = idx
        self.set_playback_sample_t(sample_t if sample_t is not None else float(np.asarray(b.t, dtype=float)[idx]))
        now_ts = float(time.perf_counter())

        slow_panels: List[Tuple[str, Any, str]] = [
            ("dock_telemetry", self.telemetry, "update_frame"),
            ("dock_heatmap", getattr(self, "telemetry_heatmap", None), "update_frame"),
            ("dock_corner_quick", getattr(self, "telemetry_corner_quick", None), "update_frame"),
            ("dock_road_profile", getattr(self, "telemetry_road_profile", None), "update_frame"),
            ("dock_corner_table", getattr(self, "telemetry_corner_table", None), "update_frame"),
            ("dock_pressures", getattr(self, "telemetry_press_panel", None), "update_frame"),
            ("dock_flows", getattr(self, "telemetry_flow_panel", None), "update_frame"),
            ("dock_valves", getattr(self, "telemetry_valve_panel", None), "update_frame"),
        ]
        visible: List[Tuple[str, Any, str]] = []
        for dock_name, panel, method_name in slow_panels:
            if panel is None or not hasattr(panel, method_name):
                continue
            if not self._dock_is_exposed(dock_name):
                continue
            visible.append((dock_name, panel, method_name))

        batch, done = self._take_interactive_scrub_slow_batch(visible)
        sample_t_panels = (
            self.telemetry,
            getattr(self, "telemetry_heatmap", None),
            getattr(self, "telemetry_corner_quick", None),
            getattr(self, "telemetry_corner_table", None),
            getattr(self, "telemetry_press_panel", None),
            getattr(self, "telemetry_flow_panel", None),
            getattr(self, "telemetry_valve_panel", None),
            getattr(self, "telemetry_road_profile", None),
        )
        for dock_name, panel, method_name in batch:
            try:
                _call_with_qt_update_batch(
                    panel,
                    lambda panel=panel, method_name=method_name: (
                        getattr(panel, method_name)(b, idx, sample_t=self._playback_sample_t_s)
                        if panel in sample_t_panels
                        else getattr(panel, method_name)(b, idx)
                    ),
                )
                self._record_aux_cadence(str(dock_name), now_ts)
            except Exception:
                pass

        if self._dock_is_exposed("dock_timeline"):
            try:
                _call_with_qt_update_batch(
                    self.timeline,
                    lambda: self.timeline.set_playhead_time(self._playback_sample_t_s, idx=idx),
                )
                self._record_aux_cadence("dock_timeline", now_ts)
            except Exception:
                pass
        if self._dock_is_exposed("dock_trends"):
            try:
                _call_with_qt_update_batch(
                    self.trends,
                    lambda: self.trends.update_frame(idx, sample_t=self._playback_sample_t_s),
                )
                self._record_aux_cadence("dock_trends", now_ts)
            except Exception:
                pass
        if done:
            self._apply_playback_perf_mode(False)
            self._aux_cadence_tracking_active = False
            self._emit_aux_cadence_metrics(
                now_ts,
                playing=False,
                many_visible_budget=False,
                force=True,
            )
        return bool(done)

    def update_frame(
        self,
        i: int,
        *,
        playing: bool = False,
        sample_t: float | None = None,
        interactive_scrub: bool = False,
    ):
        b = self.bundle
        if b is None:
            return
        n = len(b.t)
        if n <= 0:
            return
        self.set_playback_sample_t(sample_t if sample_t is not None else float(np.asarray(b.t, dtype=float)[int(_clamp(int(i), 0, n - 1))]))
        i = int(_clamp(int(i), 0, n - 1))
        self._last_i = i

        now_ts = float(time.perf_counter())
        interactive_scrub = bool(interactive_scrub) and not bool(playing)
        track_aux_cadence = bool(playing or interactive_scrub)
        visible_aux = int(self._visible_aux_dock_count()) if (bool(playing) or interactive_scrub) else 0
        many_visible_budget = (bool(playing) or interactive_scrub) and visible_aux >= int(getattr(self, "_many_visible_threshold", 10))
        self._apply_playback_perf_mode(many_visible_budget)
        if self.car3d is not None:
            try:
                self.car3d.set_playback_state(bool(playing))
            except Exception:
                pass
        if not bool(playing) and not interactive_scrub:
            fast_due = True
            slow_due = True
            self._aux_fast_last_ts = now_ts
            self._aux_slow_last_ts = now_ts
        else:
            if bool(playing):
                fast_fps = self._aux_many_fast_fps if many_visible_budget else self._aux_play_fast_fps
                slow_fps = self._aux_many_slow_fps if many_visible_budget else self._aux_play_slow_fps
            else:
                fast_fps = min(self._aux_scrub_fast_fps, self._aux_many_fast_fps) if many_visible_budget else self._aux_scrub_fast_fps
                slow_fps = min(self._aux_scrub_slow_fps, self._aux_many_slow_fps) if many_visible_budget else self._aux_scrub_slow_fps
            fast_period = 1.0 / float(max(0.5, fast_fps))
            slow_period = 1.0 / float(max(0.5, slow_fps))
            fast_due = (now_ts - float(self._aux_fast_last_ts)) >= fast_period
            slow_due = (now_ts - float(self._aux_slow_last_ts)) >= slow_period

        fast_panels: List[Tuple[str, Any, str]] = [
            ("dock_hud", self.hud, "update_frame"),
        ]
        slow_panels: List[Tuple[str, Any, str]] = [
            ("dock_telemetry", self.telemetry, "update_frame"),
            ("dock_heatmap", getattr(self, "telemetry_heatmap", None), "update_frame"),
            ("dock_corner_quick", getattr(self, "telemetry_corner_quick", None), "update_frame"),
            ("dock_road_profile", getattr(self, "telemetry_road_profile", None), "update_frame"),
            ("dock_corner_table", getattr(self, "telemetry_corner_table", None), "update_frame"),
            ("dock_pressures", getattr(self, "telemetry_press_panel", None), "update_frame"),
            ("dock_flows", getattr(self, "telemetry_flow_panel", None), "update_frame"),
            ("dock_valves", getattr(self, "telemetry_valve_panel", None), "update_frame"),
        ]
        if interactive_scrub:
            fast_panels.extend(
                [
                    ("dock_front", self.axleF, "update_frame"),
                    ("dock_rear", self.axleR, "update_frame"),
                    ("dock_left", self.sideL, "update_frame"),
                    ("dock_right", self.sideR, "update_frame"),
                ]
            )
        else:
            slow_panels = [
                ("dock_front", self.axleF, "update_frame"),
                ("dock_rear", self.axleR, "update_frame"),
                ("dock_left", self.sideL, "update_frame"),
                ("dock_right", self.sideR, "update_frame"),
                *slow_panels,
            ]
        road_profile_panel = getattr(self, "telemetry_road_profile", None)
        heatmap_panel = getattr(self, "telemetry_heatmap", None)
        corner_quick_panel = getattr(self, "telemetry_corner_quick", None)
        corner_table_panel = getattr(self, "telemetry_corner_table", None)
        pressure_panel = getattr(self, "telemetry_press_panel", None)
        flow_panel = getattr(self, "telemetry_flow_panel", None)
        valve_panel = getattr(self, "telemetry_valve_panel", None)
        sample_t_panels = (
            self.hud,
            self.axleF,
            self.axleR,
            self.sideL,
            self.sideR,
            self.telemetry,
            heatmap_panel,
            corner_quick_panel,
            corner_table_panel,
            pressure_panel,
            flow_panel,
            valve_panel,
            road_profile_panel,
        )

        def _visible_panel_entries(entries: List[Tuple[str, Any, str]]) -> List[Tuple[str, Any, str]]:
            out: List[Tuple[str, Any, str]] = []
            for dock_name, panel, method_name in entries:
                if panel is None or not hasattr(panel, method_name):
                    continue
                if not self._dock_is_exposed(dock_name):
                    continue
                out.append((dock_name, panel, method_name))
            return out

        def _call_panel(entry: Tuple[str, Any, str]) -> None:
            dock_name, panel, method_name = entry
            try:
                def _update_panel() -> None:
                    if panel in sample_t_panels:
                        getattr(panel, method_name)(
                            b,
                            i,
                            sample_t=self._playback_sample_t_s if bool(playing) else None,
                        )
                    else:
                        getattr(panel, method_name)(b, i)

                _call_with_qt_update_batch(
                    panel,
                    _update_panel,
                )
                if track_aux_cadence:
                    self._record_aux_cadence(str(dock_name), now_ts)
            except Exception:
                pass

        def _call_aux_widget(dock_name: str, widget: Any, fn: Callable[[], None]) -> None:
            try:
                _call_with_qt_update_batch(widget, fn)
                if track_aux_cadence:
                    self._record_aux_cadence(str(dock_name), now_ts)
            except Exception:
                pass

        fast_visible = _visible_panel_entries(fast_panels)
        slow_visible = _visible_panel_entries(slow_panels)
        if interactive_scrub:
            release_only = set(getattr(self, "_interactive_scrub_release_only_docks", set()))
            if release_only:
                slow_visible = [entry for entry in slow_visible if str(entry[0]) not in release_only]
        if self._dock_is_exposed("dock_timeline") and (bool(playing) or interactive_scrub or fast_due):
            _call_aux_widget(
                "dock_timeline",
                self.timeline,
                lambda: self.timeline.set_playhead_time(self._playback_sample_t_s, idx=i),
            )
        if interactive_scrub and self._dock_is_exposed("dock_telemetry"):
            _call_aux_widget(
                "dock_telemetry",
                self.telemetry,
                lambda: self.telemetry.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and (not many_visible_budget) and pressure_panel is not None and self._dock_is_exposed("dock_pressures"):
            _call_aux_widget(
                "dock_pressures",
                pressure_panel,
                lambda: pressure_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and (not many_visible_budget) and flow_panel is not None and self._dock_is_exposed("dock_flows"):
            _call_aux_widget(
                "dock_flows",
                flow_panel,
                lambda: flow_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and (not many_visible_budget) and valve_panel is not None and self._dock_is_exposed("dock_valves"):
            _call_aux_widget(
                "dock_valves",
                valve_panel,
                lambda: valve_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and (not many_visible_budget) and slow_due and corner_table_panel is not None and self._dock_is_exposed("dock_corner_table"):
            _call_aux_widget(
                "dock_corner_table",
                corner_table_panel,
                lambda: corner_table_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and heatmap_panel is not None and self._dock_is_exposed("dock_heatmap"):
            _call_aux_widget(
                "dock_heatmap",
                heatmap_panel,
                lambda: heatmap_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and corner_quick_panel is not None and self._dock_is_exposed("dock_corner_quick"):
            _call_aux_widget(
                "dock_corner_quick",
                corner_quick_panel,
                lambda: corner_quick_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and road_profile_panel is not None and self._dock_is_exposed("dock_road_profile"):
            _call_aux_widget(
                "dock_road_profile",
                road_profile_panel,
                lambda: road_profile_panel.update_frame(b, i, sample_t=self._playback_sample_t_s),
            )
        if interactive_scrub and self._dock_is_exposed("dock_trends"):
            _call_aux_widget(
                "dock_trends",
                self.trends,
                lambda: self.trends.update_frame(i, sample_t=self._playback_sample_t_s),
            )

        if fast_due:
            self._aux_fast_last_ts = now_ts
            for entry in fast_visible:
                _call_panel(entry)

        if slow_due:
            self._aux_slow_last_ts = now_ts
            slow_entries = slow_visible
            if interactive_scrub:
                slow_entries = []
            for entry in slow_entries:
                _call_panel(entry)

            if self._dock_is_exposed("dock_trends") and not interactive_scrub:
                _call_aux_widget(
                    "dock_trends",
                    self.trends,
                    lambda: self.trends.update_frame(i, sample_t=self._playback_sample_t_s),
                )
        if track_aux_cadence and (fast_due or slow_due):
            self._aux_cadence_tracking_active = True
            self._emit_aux_cadence_metrics(
                now_ts,
                playing=bool(playing),
                many_visible_budget=bool(many_visible_budget),
                force=False,
            )
        elif bool(getattr(self, "_aux_cadence_tracking_active", False)) and bool(getattr(self, "_aux_cadence_stats", {})):
            self._aux_cadence_tracking_active = False
            self._emit_aux_cadence_metrics(
                now_ts,
                playing=False,
                many_visible_budget=False,
                force=True,
            )
        if self.car3d is not None and self._dock_is_visible("dock_3d"):
            self.car3d.update_frame(
                b,
                i,
                sample_t=self._playback_sample_t_s if bool(playing) else None,
            )

# -----------------------------
# Main Window + playback
# -----------------------------


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *, enable_gl: bool = True, pointer_path: Optional[Path] = None):
        super().__init__()
        # NOTE: env var is optional; fallback should match packaged release.
        self.setWindowTitle(f"Анимация — Desktop Animator ({os.environ.get('PNEUMO_RELEASE', 'UNIFIED_v6_80')})")
        self.resize(1550, 920)

        self.bundle: Optional[DataBundle] = None
        self._enable_gl = bool(enable_gl)

        # Central / dock layout
        self.cockpit = CockpitWidget(enable_gl=self._enable_gl, layout_mode="docked")
        self.cockpit.install_docks(self)
        self._gl_layout_transition_active = False
        self._resume_after_gl_layout_transition = False
        self._gl_layout_pause_timer = QtCore.QTimer(self)
        self._gl_layout_pause_timer.setSingleShot(True)
        self._gl_layout_pause_timer.setInterval(320)
        self._gl_layout_pause_timer.timeout.connect(self._finish_gl_layout_transition)
        try:
            self.cockpit.set_live_gl_layout_activity_callback(self._on_live_gl_layout_activity)
        except Exception:
            pass

        # Playback controls
        self._playing = False
        self._speed = 1.0
        self._repeat = False
        self._interactive_scrub_active = False
        self._play_wall_ts = 0.0
        self._play_accum_s = 0.0
        self._play_cursor_t_s = 0.0

        self._idx = 0

        # Persistent UI state (window geometry + (future) dock layout + a few runtime toggles)
        # On Windows this is stored in registry (good for "settings must not disappear").
        self._settings = QtCore.QSettings("UnifiedPneumoApp", "DesktopAnimator")
        self._dock_layout_version = "r31cn_continuous_sampling_gl_native_v2"
        self._first_show_layout_pending = True

        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        try:
            self._timer.setTimerType(QtCore.Qt.PreciseTimer)
        except Exception:
            pass
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._scrub_release_timer = QtCore.QTimer(self)
        self._scrub_release_timer.setSingleShot(True)
        try:
            self._scrub_release_timer.setTimerType(QtCore.Qt.PreciseTimer)
        except Exception:
            pass
        self._scrub_release_timer.setInterval(12)
        self._scrub_release_timer.timeout.connect(self._flush_scrub_release_batch)
        self._scrub_release_pending = False
        self._scrub_release_idx = 0
        self._scrub_release_sample_t_s = 0.0
        self._paused_seek_settle_delay_ms = 20

        self._make_toolbar()
        self._make_statusbar()

        # R54: click-to-seek from EventTimelineWidget
        try:
            self.cockpit.seek_requested.connect(self._on_seek_requested)
        except Exception:
            pass

        # Follow mode
        self.pointer_watcher: Optional[PointerWatcher] = None
        if pointer_path is not None:
            self.pointer_watcher = PointerWatcher(pointer_path)
            self.pointer_watcher.npz_changed.connect(self.load_npz)
            self.pointer_watcher.status.connect(self._status)

        # Restore persisted UI state (safe even if keys are missing)
        self._restore_persisted_state()
        try:
            saved_layout_version = str(self._settings.value("window/layout_version", "") or "")
        except Exception:
            saved_layout_version = ""
        self._first_show_layout_pending = bool(saved_layout_version != self._dock_layout_version)

        # Startup policy:
        # - docks start attached for a clean first paint and normal Qt snapping/tabbing;
        # - live 3D GL uses native dock/floating mode again, so it can re-attach to
        #   other panels instead of being routed through a special safe window;
        # - if the user moves/resizes the live 3D panel during playback, playback is
        #   auto-paused, the 3D viewport is temporarily suspended until the layout settles,
        #   and playback then resumes from the current frame;
        # - layout version is bumped so old persisted special-window state does not
        #   silently return after upgrade.
        try:
            _emit_animator_warning(
                "Animator starts with docks attached. Live 3D GL uses native dock/floating mode again; during layout churn playback auto-pauses, the 3D viewport is temporarily suspended until the layout settles, live repaints stay in native dock/floating mode without hide/show, and playback resumes from the current frame once the dock settles.",
                code="startup_native_gl_autopause_with_gl_suspend_on_layout",
            )
        except Exception:
            pass

    def showEvent(self, event: QtGui.QShowEvent):  # type: ignore[override]
        super().showEvent(event)
        if not bool(getattr(self, "_first_show_layout_pending", False)):
            return
        self._first_show_layout_pending = False
        try:
            self._settings.setValue("window/layout_version", self._dock_layout_version)
        except Exception:
            pass

    def _on_live_gl_layout_activity(self, reason: str) -> None:
        if self.cockpit.car3d is None or not bool(getattr(self, "_enable_gl", False)):
            return
        try:
            if not bool(self.cockpit.car3d.has_live_gl_context()):
                return
        except Exception:
            return
        if not bool(getattr(self, "_gl_layout_transition_active", False)):
            self._gl_layout_transition_active = True
            try:
                self.cockpit.set_gl_layout_transition_active(True)
            except Exception:
                pass
            if bool(getattr(self, "_playing", False)):
                self._resume_after_gl_layout_transition = True
                self._playing = False
                try:
                    self._timer.stop()
                except Exception:
                    pass
                self._play_accum_s = 0.0
                try:
                    self.btn_play.setText("▶ Пуск")
                except Exception:
                    pass
                try:
                    self._status(f"3D layout change: playback auto-paused ({reason})")
                except Exception:
                    pass
            else:
                self._resume_after_gl_layout_transition = False
        try:
            self._gl_layout_pause_timer.start()
        except Exception:
            pass

    def _finish_gl_layout_transition(self) -> None:
        if not bool(getattr(self, "_gl_layout_transition_active", False)):
            return
        self._gl_layout_transition_active = False
        try:
            self.cockpit.set_gl_layout_transition_active(False)
        except Exception:
            pass
        try:
            self._update_frame(int(self._idx))
        except Exception:
            pass
        if bool(getattr(self, "_resume_after_gl_layout_transition", False)) and self.bundle is not None:
            self._resume_after_gl_layout_transition = False
            try:
                t = np.asarray(self.bundle.t, dtype=float)
                if t.size >= 2 and int(self._idx) >= int(t.size - 1):
                    self._idx = 0
                    self.slider.setValue(0)
                    self._update_frame(0)
            except Exception:
                pass
            self._playing = True
            self._play_accum_s = 0.0
            self._play_cursor_t_s = self.current_time()
            self._play_wall_ts = float(time.perf_counter())
            try:
                self.btn_play.setText("⏸ Пауза")
            except Exception:
                pass
            self._arm_next_playback_tick()
            try:
                self._status("3D layout settled: playback resumed")
            except Exception:
                pass

    def _make_toolbar(self):
        tb = self.addToolBar("Controls")
        try:
            tb.setObjectName("Controls")
        except Exception:
            pass
        tb.setMovable(False)

        act_open = QtGui.QAction("Open NPZ", self)
        act_open.triggered.connect(self._open_dialog)
        tb.addAction(act_open)

        self.act_follow = QtGui.QAction("Follow", self)
        self.act_follow.setCheckable(True)
        self.act_follow.setChecked(False)
        self.act_follow.triggered.connect(self._toggle_follow)
        tb.addAction(self.act_follow)

        tb.addSeparator()

        self.btn_show_panels = QtWidgets.QToolButton()
        self.btn_show_panels.setText("Панели: показать все")
        self.btn_show_panels.clicked.connect(self.cockpit.show_all_docks)
        tb.addWidget(self.btn_show_panels)

        self.btn_detach_panels = QtWidgets.QToolButton()
        self.btn_detach_panels.setText("Панели: разнести")
        self.btn_detach_panels.clicked.connect(lambda: self.cockpit.enforce_detached_windows(self, reset_geometry=True))
        tb.addWidget(self.btn_detach_panels)

        self.btn_reset_views = QtWidgets.QToolButton()
        self.btn_reset_views.setText("Сбросить масштаб/вид")
        self.btn_reset_views.clicked.connect(self.cockpit.reset_views)
        tb.addWidget(self.btn_reset_views)

        tb.addSeparator()

        self.btn_play = QtWidgets.QToolButton()
        self.btn_play.setText("▶ Пуск")
        self.btn_play.clicked.connect(self.toggle_play)
        tb.addWidget(self.btn_play)

        self.btn_repeat = QtWidgets.QToolButton()
        self.btn_repeat.setText("⟲ Повтор")
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.setChecked(False)
        self.btn_repeat.toggled.connect(self._set_repeat)
        self.btn_repeat.setToolTip(
            "Повторять воспроизведение (loop) по достижении конца таймлайна.\n"
            "Полезно для сравнения поведения на одном и том же участке теста."
        )
        tb.addWidget(self.btn_repeat)

        self.speed_box = QtWidgets.QDoubleSpinBox()
        self.speed_box.setRange(0.05, 8.0)
        self.speed_box.setSingleStep(0.25)
        self.speed_box.setValue(1.0)
        self.speed_box.setPrefix("x")
        self.speed_box.valueChanged.connect(self._set_speed)
        tb.addWidget(QtWidgets.QLabel("  speed:"))
        tb.addWidget(self.speed_box)

        tb.addSeparator()

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self._slider_changed)
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.setMinimumWidth(520)
        tb.addWidget(QtWidgets.QLabel("  frame:"))
        tb.addWidget(self.slider)

        self.lbl_frame = QtWidgets.QLabel("0/0")
        tb.addWidget(self.lbl_frame)

    def _make_statusbar(self):
        sb = self.statusBar()
        self._status_label = QtWidgets.QLabel("Ready")
        sb.addWidget(self._status_label, 1)

    def _status(self, msg: str):
        self._status_label.setText(str(msg))

    def _slider_pressed(self):
        self._interactive_scrub_active = True
        self._scrub_release_pending = False
        try:
            self._scrub_release_timer.stop()
        except Exception:
            pass
        try:
            self.cockpit.reset_interactive_scrub_budget()
        except Exception:
            pass

    def _slider_released(self):
        self._interactive_scrub_active = False
        if self.bundle is None:
            return
        self._idx = int(self.slider.value())
        self._play_cursor_t_s = self.current_time()
        self._scrub_release_idx = int(self._idx)
        self._scrub_release_sample_t_s = float(self._play_cursor_t_s)
        self._scrub_release_pending = True
        try:
            self._scrub_release_timer.start(0)
        except Exception:
            self._flush_scrub_release_batch()

    def _flush_scrub_release_batch(self):
        if not bool(getattr(self, "_scrub_release_pending", False)):
            return
        if self.bundle is None:
            self._scrub_release_pending = False
            return
        done = True
        try:
            done = bool(
                self.cockpit.flush_interactive_scrub_detail_batch(
                    int(self._scrub_release_idx),
                    sample_t=float(self._scrub_release_sample_t_s),
                )
            )
        except Exception:
            done = True
        if done:
            self._scrub_release_pending = False
        else:
            try:
                self._scrub_release_timer.start()
            except Exception:
                pass

    def _restore_persisted_state(self):
        """Restore small persistent UI state.

        Must be safe to call even if settings are absent/corrupted.
        """
        s = getattr(self, "_settings", None)
        if s is None:
            return

        try:
            saved_layout_version = str(s.value("window/layout_version", "") or "")
        except Exception:
            saved_layout_version = ""
        layout_matches = bool(saved_layout_version == str(getattr(self, "_dock_layout_version", "")))

        # Window geometry/state
        try:
            geo = s.value("window/geometry", None)
            if geo is not None:
                self.restoreGeometry(geo)
        except Exception:
            pass

        if layout_matches:
            try:
                st = s.value("window/state", None)
                if st is not None:
                    self.restoreState(st)
            except Exception:
                pass

            try:
                self.cockpit.restore_external_panel_state(s)
            except Exception:
                pass
        else:
            try:
                self.cockpit.show_all_docks()
            except Exception:
                pass

        # Playback settings
        try:
            rep = s.value("playback/repeat", None)
            if rep is not None:
                self._repeat = bool(int(rep))
                if hasattr(self, "btn_repeat"):
                    self.btn_repeat.setChecked(self._repeat)
        except Exception:
            pass

        try:
            spd = s.value("playback/speed", None)
            if spd is not None:
                self._speed = float(spd)
                if hasattr(self, "speed_box"):
                    self.speed_box.setValue(self._speed)
        except Exception:
            pass

        # Follow mode
        try:
            flw = s.value("follow/enabled", None)
            if flw is not None and hasattr(self, "act_follow"):
                enabled = bool(int(flw))
                blocked = self.act_follow.blockSignals(True)
                self.act_follow.setChecked(enabled)
                self.act_follow.blockSignals(blocked)
                if self.pointer_watcher is not None:
                    self._toggle_follow(enabled)
        except Exception:
            pass

    def _save_persisted_state(self):
        s = getattr(self, "_settings", None)
        if s is None:
            return

        try:
            s.setValue("window/geometry", self.saveGeometry())
        except Exception:
            pass
        try:
            s.setValue("window/state", self.saveState())
        except Exception:
            pass
        try:
            s.setValue("window/layout_version", self._dock_layout_version)
        except Exception:
            pass
        try:
            self.cockpit.save_external_panel_state(s)
        except Exception:
            pass

        try:
            s.setValue("playback/repeat", int(bool(self._repeat)))
        except Exception:
            pass
        try:
            s.setValue("playback/speed", float(self._speed))
        except Exception:
            pass

        try:
            if hasattr(self, "act_follow"):
                s.setValue("follow/enabled", int(bool(self.act_follow.isChecked())))
        except Exception:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent):  # type: ignore
        try:
            self._save_persisted_state()
        finally:
            try:
                self.cockpit.close_external_panel_windows()
            except Exception:
                pass
            try:
                self._timer.stop()
            except Exception:
                pass
            try:
                self._scrub_release_timer.stop()
            except Exception:
                pass
            try:
                self._gl_layout_pause_timer.stop()
            except Exception:
                pass
        return super().closeEvent(event)

    def _on_seek_requested(self, idx: int):
        """Seek to a frame requested by widgets (timeline click).

        Implementation note:
        - we delegate actual update to the slider handler (single source of truth)
        - if playback is running, slider handler also re-anchors the time
        """
        if self.bundle is None:
            return
        try:
            n = len(self.bundle.t)
            idx = int(_clamp(int(idx), 0, max(0, n - 1)))
            self.slider.setValue(idx)
        except Exception:
            pass

    def _open_dialog(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open NPZ", str(Path.cwd()), "NPZ files (*.npz)")
        if fn:
            self.load_npz(Path(fn))

    def _toggle_follow(self, checked: bool):
        if self.pointer_watcher is None:
            self._status("Follow unavailable (no pointer_path)")
            self.act_follow.setChecked(False)
            return
        if checked:
            self.pointer_watcher.start()
        else:
            self.pointer_watcher.stop()
            self._status("Follow stopped")

    def _set_speed(self, v: float):
        self._speed = float(v)
        if self._playing:
            self._play_wall_ts = float(time.perf_counter())
            self._arm_next_playback_tick()

    def _set_repeat(self, checked: bool):
        """Loop playback when reaching the end."""
        self._repeat = bool(checked)
        # persist immediately (safe small value)
        try:
            self._settings.setValue("playback/repeat", int(self._repeat))
        except Exception:
            pass

    def _slider_changed(self, v: int):
        if self.bundle is None:
            return
        self._scrub_release_pending = False
        try:
            self._scrub_release_timer.stop()
        except Exception:
            pass
        self._idx = int(v)
        self._play_cursor_t_s = self.current_time()
        interactive_scrub = bool(not self._playing and (self._interactive_scrub_active or self.slider.isSliderDown()))
        coalesced_seek = bool(not self._playing and not interactive_scrub)
        if coalesced_seek:
            try:
                self.cockpit.reset_interactive_scrub_budget()
            except Exception:
                pass
        self._update_frame(
            self._idx,
            sample_t=self._play_cursor_t_s,
            interactive_scrub=bool(interactive_scrub or coalesced_seek),
        )
        if coalesced_seek:
            self._scrub_release_idx = int(self._idx)
            self._scrub_release_sample_t_s = float(self._play_cursor_t_s)
            self._scrub_release_pending = True
            try:
                self._scrub_release_timer.start(int(max(0, getattr(self, "_paused_seek_settle_delay_ms", 20))))
            except Exception:
                self._flush_scrub_release_batch()
        if self._playing:
            self._play_accum_s = 0.0
            self._play_cursor_t_s = self.current_time()
            self._play_wall_ts = float(time.perf_counter())
            self._arm_next_playback_tick()

    def current_time(self) -> float:
        if self.bundle is None:
            return 0.0
        t = self.bundle.t
        if len(t) == 0:
            return 0.0
        i = int(_clamp(self._idx, 0, len(t) - 1))
        return float(t[i])

    def _playback_interval_ms_for_index(self, idx: int) -> int:
        # Playback is display-oriented, not source-frame-oriented.  The old 4 ms service
        # timer tried to chase every dense source frame inside the GUI thread, which made
        # a simple animation look far more expensive than it really is.  We now render at
        # a display cadence and select the source frame from a continuous playhead time.
        speed = float(max(0.05, self._speed))
        if speed <= 1.0:
            base_ms = 12.0  # ~83 Hz keeps x1.0 visibly alive without source-frame chasing.
        elif speed <= 2.0:
            base_ms = 10.0  # ~100 Hz for moderate fast-forward.
        elif speed <= 4.0:
            base_ms = 8.0   # ~125 Hz.
        else:
            base_ms = 6.0   # ~166 Hz upper service cadence on Windows precise timer.
        return int(max(6, min(20, round(base_ms))))

    def _arm_next_playback_tick(self) -> None:
        if self.bundle is None or not self._playing:
            return
        try:
            self._timer.stop()
        except Exception:
            pass
        self._timer.setInterval(self._playback_interval_ms_for_index(self._idx))
        self._timer.start()

    def _refresh_after_playback_stop(self) -> None:
        """Restore full pane rendering immediately after playback stops.

        Why this helper exists:
        - several views intentionally lighten rendering during playback/perf mode;
        - if the user stops playback manually, the previous code only stopped the timer
          and left some panes waiting for the *next* explicit frame refresh;
        - that looked like graphics/labels were disabled and never came back.
        """
        if self.bundle is None:
            return
        try:
            self._update_frame(int(self._idx))
        except Exception:
            try:
                self.cockpit.update_frame(int(self._idx), playing=False)
            except Exception:
                pass

    def toggle_play(self):
        if self.bundle is None:
            return
        self._playing = not self._playing
        self.btn_play.setText("⏸ Пауза" if self._playing else "▶ Пуск")
        if self._playing:
            try:
                t = self.bundle.t
                if len(t) >= 2 and self._idx >= (len(t) - 1):
                    self._idx = 0
                    self.slider.setValue(0)
                    self._update_frame(0)
            except Exception:
                pass
            self._play_accum_s = 0.0
            self._play_cursor_t_s = self.current_time()
            self._play_wall_ts = float(time.perf_counter())
            self._arm_next_playback_tick()
        else:
            self._timer.stop()
            self._play_accum_s = 0.0
            self._refresh_after_playback_stop()

    def _tick(self):
        b = self.bundle
        if b is None or not self._playing:
            return
        t = np.asarray(b.t, dtype=float)
        if t.size == 0:
            return

        now = float(time.perf_counter())
        last = float(self._play_wall_ts) if self._play_wall_ts else now
        wall_dt = max(0.0, now - last)
        self._play_wall_ts = now

        start_t = float(t[0])
        end_t = float(t[-1])
        if not np.isfinite(getattr(self, '_play_cursor_t_s', np.nan)):
            self._play_cursor_t_s = float(t[int(_clamp(self._idx, 0, len(t) - 1))])
        self._play_cursor_t_s = float(self._play_cursor_t_s) + wall_dt * float(max(0.05, self._speed))

        advanced = False
        if self._play_cursor_t_s >= end_t - 1e-12:
            if self._repeat and len(t) >= 2 and end_t > start_t:
                span = max(1e-9, end_t - start_t)
                rel = (float(self._play_cursor_t_s) - start_t) % span
                self._play_cursor_t_s = start_t + rel
            else:
                self._play_cursor_t_s = end_t
                self._idx = len(t) - 1
                self._playing = False
                self.btn_play.setText("▶ Пуск")
                self._timer.stop()

        if self._playing:
            idx = int(np.searchsorted(t, float(self._play_cursor_t_s), side='left'))
            if idx <= 0:
                idx = 0
            elif idx >= len(t):
                idx = len(t) - 1
            else:
                prev_idx = idx - 1
                if abs(float(self._play_cursor_t_s) - float(t[prev_idx])) <= abs(float(t[idx]) - float(self._play_cursor_t_s)):
                    idx = prev_idx
            advanced = idx != int(self._idx)
            self._idx = int(idx)

        if advanced or not self._playing:
            self.slider.blockSignals(True)
            self.slider.setValue(int(self._idx))
            self.slider.blockSignals(False)
            self._update_frame(int(self._idx), sample_t=self._play_cursor_t_s if self._playing else None)
        # Continuous playback sampling only helps if we actually redraw every service tick.
        if self._playing:
            self._update_frame(int(self._idx), sample_t=self._play_cursor_t_s)
        if not self._playing:
            self._refresh_after_playback_stop()

        if self._playing:
            self._arm_next_playback_tick()

    def _update_frame(self, idx: int, *, sample_t: float | None = None, interactive_scrub: bool = False):
        b = self.bundle
        if b is None:
            return
        n = len(b.t)
        idx = int(_clamp(idx, 0, n - 1))
        sample_time = sample_t if (sample_t is not None and np.isfinite(float(sample_t))) else float(np.asarray(b.t, dtype=float)[idx])
        self.cockpit.set_playback_sample_t(sample_time)
        self.lbl_frame.setText(f"{idx+1}/{n}")
        self.cockpit.update_frame(
            idx,
            playing=bool(self._playing),
            sample_t=sample_time,
            interactive_scrub=bool(interactive_scrub),
        )
        # status line: time + speed
        try:
            t = float(sample_time)
            vxw, vyw = b.ensure_world_velocity_xy()
            v = math.hypot(float(vxw[idx]), float(vyw[idx])) if len(vxw) > idx and len(vyw) > idx else float(abs(b.get("скорость_vx_м_с", 0.0)[idx]))
            self._status(f"t={t:.3f}s, v={v:.2f}m/s, file={b.npz_path.name}")
        except Exception:
            pass

    def load_npz(self, path: Path):
        try:
            b = load_npz(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Failed to load NPZ", f"{e}")
            return

        self.bundle = b
        self._scrub_release_pending = False
        try:
            self._scrub_release_timer.stop()
        except Exception:
            pass
        self.cockpit.set_bundle(b)

        n = len(b.t)
        self.slider.blockSignals(True)
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, n - 1))
        self.slider.setValue(0)
        self.slider.blockSignals(False)

        self._idx = 0
        self._playing = False
        self.btn_play.setText("▶ Пуск")
        self._timer.stop()

        self._play_cursor_t_s = float(np.asarray(b.t, dtype=float)[0]) if len(b.t) else 0.0
        self._update_frame(0, sample_t=self._play_cursor_t_s)
        self._status(f"Loaded: {path}")

        # If follow mode is enabled, keep it.


# -----------------------------
# App runner
# -----------------------------


def run_app(
    *,
    npz_path: Optional[Path],
    follow: bool,
    pointer_path: Path,
    theme: str = "dark",
    enable_gl: bool = True,
) -> int:
    # Qt 6 already handles DPI scaling globally; forcing the old application
    # attributes only emits deprecation warnings on current Windows/PySide builds.
    app = QtWidgets.QApplication([])

    if qdarktheme is not None:
        try:
            qdarktheme.setup_theme(str(theme))
        except Exception:
            pass

    win = MainWindow(enable_gl=enable_gl, pointer_path=pointer_path)
    win.show()

    if follow:
        win.act_follow.setChecked(True)
        win._toggle_follow(True)

    if npz_path is not None and npz_path.exists():
        win.load_npz(npz_path)
    else:
        # Try loading from pointer if it exists.
        if follow and pointer_path.exists():
            try:
                obj = json.loads(pointer_path.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(obj, dict):
                    p = obj.get("npz_path") or obj.get("path")
                    if isinstance(p, str) and p.strip():
                        pp = Path(p.strip())
                        if not pp.is_absolute():
                            pp = (pointer_path.parent / pp).resolve()
                        if pp.exists():
                            win.load_npz(pp)
            except Exception:
                pass

    return int(app.exec())


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _default_pointer_path() -> Path:
    """Locate default anim_latest pointer file via the shared candidate chain."""
    return default_anim_pointer_path(PROJECT_ROOT)


def _parse_args(argv: Optional[list[str]] = None):
    import argparse
    import os as _os

    ap = argparse.ArgumentParser(
        prog="desktop_animator",
        description="Pneumo suspension Desktop Animator (Qt).",
    )
    ap.add_argument(
        "--npz",
        default=_os.environ.get("PNEUMO_ANIM_NPZ", ""),
        help="Путь к .npz с траекториями/сигналами (если пусто — берем из pointer).",
    )
    ap.add_argument(
        "--pointer",
        default=_os.environ.get("PNEUMO_ANIM_POINTER", str(_default_pointer_path())),
        help="Путь к JSON pointer (anim_latest.json).",
    )
    ap.add_argument(
        "--no-follow",
        action="store_true",
        help="Не следить за pointer (отключить авто-подхват данных из Web UI).",
    )
    ap.add_argument(
        "--theme",
        default=_os.environ.get("PNEUMO_ANIM_THEME", "dark"),
        choices=["dark", "light"],
        help="Тема оформления (qdarktheme, если установлен).",
    )
    ap.add_argument(
        "--no-gl",
        action="store_true",
        help="Отключить OpenGL viewport (на случай проблем с драйвером).",
    )
    return ap.parse_args(argv)


if __name__ == "__main__":
    # Важно: этот файл должен нормально запускаться и как модуль, и как скрипт,
    # и даже из подпапки. Поэтому выше уже есть bootstrap sys.path.
    args = _parse_args()
    npz = Path(args.npz).expanduser().resolve() if str(args.npz).strip() else None
    pointer = Path(args.pointer).expanduser().resolve() if str(args.pointer).strip() else _default_pointer_path()
    follow = not bool(args.no_follow)
    enable_gl = not bool(args.no_gl)

    try:
        raise SystemExit(run_app(npz_path=npz, follow=follow, pointer_path=pointer, theme=str(args.theme), enable_gl=enable_gl))
    except SystemExit:
        raise
    except Exception:
        # Best-effort: do not crash silently.
        import traceback as _traceback
        try:
            print(_traceback.format_exc())
        except Exception:
            pass
        raise
