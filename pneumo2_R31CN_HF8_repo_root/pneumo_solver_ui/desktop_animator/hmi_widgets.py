# -*- coding: utf-8 -*-
"""hmi_widgets.py

Дополнительные "инструментальные" виджеты для Desktop Animator.

Цель: повысить информативность анимации без превращения проекта в CAD.
Подход: использовать HMI-практики "glanceable" (малые, быстрые, читаемые элементы):
- small multiples (несколько маленьких графиков вместо одного большого),
- sparklines (мини‑тренды прямо рядом с числом),
- event timeline (события/флаги/активации в виде полос на шкале времени),
чтобы одновременно отслеживать множество параметров.

Файл специально вынесен из app.py, чтобы не раздувать основной модуль.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from PySide6 import QtCore, QtGui, QtWidgets


def _clamp(x: float, a: float, b: float) -> float:
    return float(max(a, min(b, x)))


def _robust_minmax(y: np.ndarray, *, p_lo: float = 1.0, p_hi: float = 99.0) -> Tuple[float, float]:
    """Robust min/max for visualization (percentiles, NaN-safe)."""
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return -1.0, 1.0
    try:
        lo = float(np.nanpercentile(y, p_lo))
        hi = float(np.nanpercentile(y, p_hi))
    except Exception:
        lo = float(np.nanmin(y)) if np.isfinite(np.nanmin(y)) else -1.0
        hi = float(np.nanmax(y)) if np.isfinite(np.nanmax(y)) else 1.0

    if not np.isfinite(lo) or not np.isfinite(hi) or abs(hi - lo) < 1e-12:
        try:
            lo2 = float(np.nanmin(y))
            hi2 = float(np.nanmax(y))
            if np.isfinite(lo2) and np.isfinite(hi2) and abs(hi2 - lo2) >= 1e-12:
                lo, hi = lo2, hi2
            else:
                lo, hi = -1.0, 1.0
        except Exception:
            lo, hi = -1.0, 1.0
    return lo, hi


class SparklineWidget(QtWidgets.QWidget):
    """Tiny trend (sparkline) + current value.

    Designed to be cheap to redraw at ~60Hz.
    """

    def __init__(
        self,
        title: str,
        *,
        unit: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setMinimumHeight(46)
        self.setMaximumHeight(64)

        self.title = str(title)
        self.unit = str(unit)
        self._t: Optional[np.ndarray] = None
        self._y: Optional[np.ndarray] = None
        self._idx: int = 0

        self.lookback_s = 2.0
        self.lookahead_s = 0.5

        self._y_lo = -1.0
        self._y_hi = 1.0

        # style
        self._bg = QtGui.QColor(18, 22, 28)
        self._grid = QtGui.QColor(60, 70, 80, 160)
        self._line = QtGui.QColor(220, 220, 220, 220)
        self._accent = QtGui.QColor(255, 180, 60, 220)
        self._text = QtGui.QColor(235, 235, 235)
        self._muted = QtGui.QColor(170, 170, 170)

        f = QtGui.QFont("Consolas", 8)
        self.setFont(f)

    def set_data(self, t: Sequence[float], y: Sequence[float]):
        self._t = np.asarray(t, dtype=float)
        self._y = np.asarray(y, dtype=float)
        if self._y.size > 0:
            self._y_lo, self._y_hi = _robust_minmax(self._y)
        else:
            self._y_lo, self._y_hi = -1.0, 1.0
        self._idx = 0
        self.update()

    def set_window(self, *, lookback_s: float = 2.0, lookahead_s: float = 0.5):
        self.lookback_s = float(max(0.0, lookback_s))
        self.lookahead_s = float(max(0.0, lookahead_s))
        self.update()

    def set_index(self, idx: int):
        self._idx = int(max(0, idx))
        self.update()

    def _window_indices(self) -> Tuple[int, int]:
        if self._t is None or self._y is None or self._t.size == 0:
            return 0, 0
        n = int(self._t.size)
        i = int(_clamp(self._idx, 0, n - 1))
        t0 = float(self._t[i])
        t_lo = t0 - float(self.lookback_s)
        t_hi = t0 + float(self.lookahead_s)
        i0 = int(np.searchsorted(self._t, t_lo, side="left"))
        i1 = int(np.searchsorted(self._t, t_hi, side="right"))
        i0 = int(_clamp(i0, 0, n - 1))
        i1 = int(_clamp(i1, i0 + 1, n))
        return i0, i1

    def paintEvent(self, ev: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

        r = self.rect()
        p.fillRect(r, self._bg)

        # layout
        pad = 6
        title_h = 14
        value_w = 86
        # plot area excludes right value column
        plot = QtCore.QRect(pad, pad + title_h, r.width() - value_w - 2 * pad, r.height() - title_h - 2 * pad)
        valr = QtCore.QRect(r.width() - value_w - pad, pad, value_w, r.height() - 2 * pad)

        # title
        p.setPen(self._muted)
        p.drawText(QtCore.QRect(pad, pad, r.width() - 2 * pad, title_h), int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter), self.title)

        # no data
        if self._t is None or self._y is None or self._t.size == 0 or self._y.size == 0:
            p.setPen(self._muted)
            p.drawText(plot, int(QtCore.Qt.AlignCenter), "n/a")
            return

        n = int(self._t.size)
        i = int(_clamp(self._idx, 0, n - 1))
        y0 = float(self._y[i])

        # value column
        p.setPen(self._text)
        p.drawText(valr, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop), f"{y0:+.3f}")
        p.setPen(self._muted)
        p.drawText(valr, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop) | int(QtCore.Qt.TextWordWrap), f"\n{self.unit}")

        # grid (simple)
        p.setPen(QtGui.QPen(self._grid, 1))
        for yy in (0.25, 0.5, 0.75):
            ypix = int(plot.top() + (1.0 - yy) * plot.height())
            p.drawLine(plot.left(), ypix, plot.right(), ypix)

        # windowed polyline
        i0, i1 = self._window_indices()
        tt = self._t[i0:i1]
        yy = self._y[i0:i1]
        if tt.size < 2:
            return

        t_min = float(tt[0])
        t_max = float(tt[-1])
        if abs(t_max - t_min) < 1e-9:
            t_max = t_min + 1e-9

        y_lo, y_hi = float(self._y_lo), float(self._y_hi)
        if abs(y_hi - y_lo) < 1e-12:
            y_hi = y_lo + 1e-12

        poly = QtGui.QPolygonF()
        for k in range(int(tt.size)):
            x = (float(tt[k]) - t_min) / (t_max - t_min)
            u = (float(yy[k]) - y_lo) / (y_hi - y_lo)
            u = _clamp(u, 0.0, 1.0)
            px = plot.left() + x * plot.width()
            py = plot.top() + (1.0 - u) * plot.height()
            poly.append(QtCore.QPointF(float(px), float(py)))

        p.setPen(QtGui.QPen(self._line, 1.6))
        p.drawPolyline(poly)

        # playhead marker
        t_i = float(self._t[i])
        x_i = (t_i - t_min) / (t_max - t_min)
        xpix = plot.left() + x_i * plot.width()
        p.setPen(QtGui.QPen(self._accent, 1.2))
        p.drawLine(int(xpix), plot.top(), int(xpix), plot.bottom())


class TrendsPanel(QtWidgets.QWidget):
    """Grid of sparklines for key signals."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(6)
        lay.setVerticalSpacing(6)

        # Fixed set (glanceable). If some signals are absent, widgets show n/a.
        self.s_v = SparklineWidget("v", unit="m/s")
        self.s_az = SparklineWidget("az_cm", unit="m/s²")
        self.s_roll = SparklineWidget("roll", unit="deg")
        self.s_pitch = SparklineWidget("pitch", unit="deg")
        self.s_pacc = SparklineWidget("P_acc", unit="bar(g)")
        self.s_open = SparklineWidget("valves_open", unit="count")
        self.s_qmax = SparklineWidget("mdot_max", unit="g/s")
        self.s_qcnt = SparklineWidget("mdot_active", unit="count")
        self.s_air = SparklineWidget("wheels_air", unit="count")

        w = [self.s_v, self.s_az, self.s_roll, self.s_pitch, self.s_pacc, self.s_open, self.s_qmax, self.s_qcnt, self.s_air]
        for i, sw in enumerate(w):
            r = i // 3
            c = i % 3
            lay.addWidget(sw, r, c)

        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        lay.setColumnStretch(2, 1)

        self._t: Optional[np.ndarray] = None

    def set_bundle(self, b):
        # b is DataBundle (kept untyped here to avoid import cycles)
        t = np.asarray(getattr(b, "t", np.zeros((0,), dtype=float)), dtype=float)
        self._t = t
        if t.size == 0:
            return

        # helper for pressures: prefer df_p("Аккумулятор") if present, else df_main
        def _patm_pa(i: int = 0) -> float:
            try:
                if getattr(b, "p", None) is not None and b.p.has("АТМ"):
                    return float(b.p.column("АТМ")[i])
            except Exception:
                pass
            return 101325.0

        # v
        self.s_v.set_data(t, np.asarray(b.get("скорость_vx_м_с", 0.0), dtype=float))
        # az_cm
        self.s_az.set_data(t, np.asarray(b.get("ускорение_рамы_z_м_с2", 0.0), dtype=float))
        # roll/pitch in deg
        self.s_roll.set_data(t, np.degrees(np.asarray(b.get("крен_phi_рад", 0.0), dtype=float)))
        self.s_pitch.set_data(t, np.degrees(np.asarray(b.get("тангаж_theta_рад", 0.0), dtype=float)))

        # P accumulator in bar(g)
        patm0 = _patm_pa(0)
        if getattr(b, "p", None) is not None and b.p.has("Аккумулятор"):
            pacc = np.asarray(b.p.column("Аккумулятор"), dtype=float)
            patm = np.asarray(b.p.column("АТМ", patm0), dtype=float) if b.p.has("АТМ") else np.full_like(pacc, patm0)
            bar_g = (pacc - patm) / 1e5
        else:
            pacc = np.asarray(b.get("давление_аккумулятор_Па", patm0), dtype=float)
            bar_g = (pacc - patm0) / 1e5
        self.s_pacc.set_data(t, bar_g)

        # valves_open count (df_open)
        if getattr(b, "open", None) is not None:
            try:
                mat = np.asarray(b.open.values, dtype=float)
                # exclude time column if present
                cols = list(getattr(b.open, "cols", []))
                idxs = [j for j, c in enumerate(cols) if str(c) != "время_с"]
                if idxs:
                    thr = 0.05
                    cnt = np.sum(mat[:, idxs] > thr, axis=1).astype(float)
                else:
                    cnt = np.zeros((t.size,), dtype=float)
            except Exception:
                cnt = np.zeros((t.size,), dtype=float)
        else:
            cnt = np.zeros((t.size,), dtype=float)
        self.s_open.set_data(t, cnt)

        # mdot / mass flow (glanceable)
        if getattr(b, "q", None) is not None:
            try:
                matq = np.asarray(b.q.values, dtype=float)
                cols = list(getattr(b.q, "cols", []))
                idxs = [j for j, c in enumerate(cols) if str(c) != "время_с"]
                if idxs:
                    qv = matq[:, idxs]
                    aq = np.abs(qv)
                    mdot_max = np.nanmax(aq, axis=1) * 1000.0  # g/s
                    thr = 0.001  # kg/s == 1 g/s
                    mdot_active = np.sum(aq > thr, axis=1).astype(float)
                else:
                    mdot_max = np.zeros((t.size,), dtype=float)
                    mdot_active = np.zeros((t.size,), dtype=float)
            except Exception:
                mdot_max = np.zeros((t.size,), dtype=float)
                mdot_active = np.zeros((t.size,), dtype=float)
        else:
            mdot_max = np.zeros((t.size,), dtype=float)
            mdot_active = np.zeros((t.size,), dtype=float)

        self.s_qmax.set_data(t, mdot_max)
        self.s_qcnt.set_data(t, mdot_active)

        # Wheels airborne count (0..4)
        try:
            a_fl = (np.asarray(b.get("колесо_в_воздухе_ЛП", 0.0), dtype=float) > 0.5).astype(float)
            a_fr = (np.asarray(b.get("колесо_в_воздухе_ПП", 0.0), dtype=float) > 0.5).astype(float)
            a_rl = (np.asarray(b.get("колесо_в_воздухе_ЛЗ", 0.0), dtype=float) > 0.5).astype(float)
            a_rr = (np.asarray(b.get("колесо_в_воздухе_ПЗ", 0.0), dtype=float) > 0.5).astype(float)
            air_cnt = a_fl + a_fr + a_rl + a_rr
        except Exception:
            air_cnt = np.zeros((t.size,), dtype=float)

        self.s_air.set_data(t, air_cnt)

        # window tuning (same for all)
        for sw in (self.s_v, self.s_az, self.s_roll, self.s_pitch, self.s_pacc, self.s_open, self.s_qmax, self.s_qcnt, self.s_air):
            sw.set_window(lookback_s=2.0, lookahead_s=0.5)

    def update_frame(self, i: int):
        for sw in (self.s_v, self.s_az, self.s_roll, self.s_pitch, self.s_pacc, self.s_open, self.s_qmax, self.s_qcnt, self.s_air):
            sw.set_index(i)


def _infer_valve_kind(name: str) -> str:
    s = str(name).lower()
    if any(k in s for k in ("atm", "атм", "выхлоп", "exh", "exhaust")):
        return "exhaust"
    if any(k in s for k in ("fill", "supply", "подпит", "inlet")):
        return "fill"
    if any(k in s for k in ("charge", "заряд", "acc", "акк")):
        return "charge"
    return "other"


def _segments_from_mask(mask: np.ndarray) -> List[Tuple[int, int]]:
    mask = np.asarray(mask, dtype=bool)
    n = int(mask.size)
    segs: List[Tuple[int, int]] = []
    i = 0
    while i < n:
        if not bool(mask[i]):
            i += 1
            continue
        j = i + 1
        while j < n and bool(mask[j]):
            j += 1
        segs.append((i, j - 1))
        i = j
    return segs


@dataclass
class _Lane:
    name: str
    color: QtGui.QColor
    segs: List[Tuple[int, int]]


class EventTimelineWidget(QtWidgets.QWidget):
    """Event timeline (flags / activations) with click-to-seek."""

    seek_index = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setMaximumHeight(140)

        self._t: Optional[np.ndarray] = None
        self._lanes: List[_Lane] = []
        self._markers: List[int] = []  # segment transitions etc
        self._idx: int = 0
        self._label_w = 120
        self._pad = 6

        self._bg = QtGui.QColor(14, 18, 22)
        self._grid = QtGui.QColor(70, 80, 90, 120)
        self._text = QtGui.QColor(220, 220, 220)
        self._muted = QtGui.QColor(160, 160, 160)
        self._play = QtGui.QColor(255, 180, 60, 220)

        self.setToolTip("Клик по таймлайну → перемотка")

    def set_bundle(self, b):
        # b is DataBundle
        t = np.asarray(getattr(b, "t", np.zeros((0,), dtype=float)), dtype=float)
        self._t = t
        self._idx = 0
        self._lanes = []
        self._markers = []

        if t.size == 0:
            self.update()
            return

        n = int(t.size)

        # Wheel airborne flags (4 lanes)
        corner_map = {
            "AIR ЛП": ("колесо_в_воздухе_ЛП", QtGui.QColor(120, 200, 255, 200)),
            "AIR ПП": ("колесо_в_воздухе_ПП", QtGui.QColor(120, 255, 180, 200)),
            "AIR ЛЗ": ("колесо_в_воздухе_ЛЗ", QtGui.QColor(200, 160, 255, 200)),
            "AIR ПЗ": ("колесо_в_воздухе_ПЗ", QtGui.QColor(255, 180, 120, 200)),
        }
        for nm, (col, colr) in corner_map.items():
            try:
                m = np.asarray(b.get(col, 0.0), dtype=float) > 0.5
            except Exception:
                m = np.zeros((n,), dtype=bool)
            self._lanes.append(_Lane(nm, colr, _segments_from_mask(m)))

        # Valve groups (3 lanes) from df_open if available
        if getattr(b, "open", None) is not None:
            try:
                cols = list(getattr(b.open, "cols", []))
                mat = np.asarray(b.open.values, dtype=float)
                # build groups
                groups: Dict[str, List[int]] = {"exhaust": [], "fill": [], "charge": []}
                for j, name in enumerate(cols):
                    if str(name) == "время_с":
                        continue
                    kind = _infer_valve_kind(name)
                    if kind in groups:
                        groups[kind].append(j)
                thr = 0.05
                for kind, idxs in groups.items():
                    if not idxs:
                        m = np.zeros((n,), dtype=bool)
                    else:
                        try:
                            m = np.any(mat[:, idxs] > thr, axis=1)
                        except Exception:
                            m = np.zeros((n,), dtype=bool)
                    if kind == "exhaust":
                        nm = "VALVE exh"
                        colr = QtGui.QColor(255, 90, 120, 200)
                    elif kind == "fill":
                        nm = "VALVE fill"
                        colr = QtGui.QColor(80, 220, 200, 200)
                    else:
                        nm = "VALVE chg"
                        colr = QtGui.QColor(250, 210, 80, 210)
                    self._lanes.append(_Lane(nm, colr, _segments_from_mask(m)))
            except Exception:
                pass

        # Flow groups (3 lanes) from df_q (mdot) if available
        if getattr(b, "q", None) is not None:
            try:
                cols = list(getattr(b.q, "cols", []))
                matq = np.asarray(b.q.values, dtype=float)
                groups_q: Dict[str, List[int]] = {"exhaust": [], "fill": [], "charge": []}
                for j, name in enumerate(cols):
                    if str(name) == "время_с":
                        continue
                    kind = _infer_valve_kind(name)
                    if kind in groups_q:
                        groups_q[kind].append(j)

                thr_q = 0.001  # kg/s == 1 g/s
                for kind, idxs in groups_q.items():
                    if not idxs:
                        continue
                    try:
                        m = np.any(np.abs(matq[:, idxs]) > thr_q, axis=1)
                    except Exception:
                        m = np.zeros((n,), dtype=bool)

                    if kind == "exhaust":
                        nm = "FLOW exh"
                        colr = QtGui.QColor(255, 140, 160, 160)
                    elif kind == "fill":
                        nm = "FLOW fill"
                        colr = QtGui.QColor(120, 255, 230, 160)
                    else:
                        nm = "FLOW chg"
                        colr = QtGui.QColor(255, 235, 120, 170)

                    self._lanes.append(_Lane(nm, colr, _segments_from_mask(m)))
            except Exception:
                pass

        # Segment transitions marker (if present)
        try:
            sid = np.asarray(b.get("сегмент_id", 0.0), dtype=float).astype(int)
            if sid.size == n and n > 1:
                ch = np.where(sid[1:] != sid[:-1])[0]
                self._markers = [int(x + 1) for x in ch.tolist()]
        except Exception:
            self._markers = []

        self.update()

    def set_index(self, idx: int):
        self._idx = int(max(0, idx))
        self.update()

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        if self._t is None or self._t.size == 0:
            return
        x = float(ev.position().x())
        r = self.rect()
        w = float(r.width())
        if w <= 1:
            return
        x0 = float(self._label_w + self._pad)
        x1 = float(w - self._pad)
        if x < x0:
            return
        u = (x - x0) / max(1e-6, (x1 - x0))
        u = _clamp(u, 0.0, 1.0)
        t0 = float(self._t[0])
        t1 = float(self._t[-1])
        tc = t0 + u * (t1 - t0)
        idx = int(np.searchsorted(self._t, tc, side="left"))
        idx = int(_clamp(idx, 0, int(self._t.size) - 1))
        try:
            self.seek_index.emit(idx)
        except Exception:
            pass

    def paintEvent(self, ev: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        r = self.rect()
        p.fillRect(r, self._bg)

        if self._t is None or self._t.size == 0:
            p.setPen(self._muted)
            p.drawText(r, int(QtCore.Qt.AlignCenter), "events: n/a")
            return

        t = self._t
        n = int(t.size)
        idx = int(_clamp(self._idx, 0, n - 1))

        pad = self._pad
        label_w = int(self._label_w)
        lanes = self._lanes
        lane_h = max(10, int((r.height() - 2 * pad) / max(1, len(lanes))))
        top = pad
        x0 = label_w + pad
        x1 = r.width() - pad
        w = max(1, x1 - x0)
        t0 = float(t[0])
        t1 = float(t[-1])
        dt = max(1e-9, t1 - t0)

        # faint grid (time ticks)
        p.setPen(QtGui.QPen(self._grid, 1))
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            xx = int(x0 + frac * w)
            p.drawLine(xx, top, xx, r.height() - pad)

        # lanes
        for li, lane in enumerate(lanes):
            y = top + li * lane_h
            rr = QtCore.QRect(x0, y, w, lane_h - 2)

            # label
            p.setPen(self._muted)
            p.drawText(QtCore.QRect(pad, y, label_w - 2, lane_h - 2), int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter), lane.name)

            # segments
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QBrush(lane.color))
            for i0, i1 in lane.segs:
                i0 = int(_clamp(i0, 0, n - 1))
                i1 = int(_clamp(i1, 0, n - 1))
                tt0 = float(t[i0])
                tt1 = float(t[i1])
                # small pad in time to make single-frame events visible
                if i1 == i0:
                    tt1 = min(t1, tt0 + 0.02)
                u0 = (tt0 - t0) / dt
                u1 = (tt1 - t0) / dt
                xx0 = int(x0 + _clamp(u0, 0.0, 1.0) * w)
                xx1 = int(x0 + _clamp(u1, 0.0, 1.0) * w)
                if xx1 <= xx0:
                    xx1 = xx0 + 1
                p.drawRect(QtCore.QRect(xx0, rr.top(), xx1 - xx0, rr.height()))

        # segment markers (vertical)
        if self._markers:
            p.setPen(QtGui.QPen(QtGui.QColor(120, 120, 120, 140), 1, QtCore.Qt.DotLine))
            for mi in self._markers:
                mi = int(_clamp(mi, 0, n - 1))
                u = (float(t[mi]) - t0) / dt
                xx = int(x0 + _clamp(u, 0.0, 1.0) * w)
                p.drawLine(xx, top, xx, r.height() - pad)

        # playhead line
        p.setPen(QtGui.QPen(self._play, 2))
        u = (float(t[idx]) - t0) / dt
        xx = int(x0 + _clamp(u, 0.0, 1.0) * w)
        p.drawLine(xx, top, xx, r.height() - pad)

        # caption
        p.setPen(self._text)
        p.drawText(QtCore.QRect(x0, pad, w, 14), int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter), "Events (wheel_air + valve groups) — click to seek")
