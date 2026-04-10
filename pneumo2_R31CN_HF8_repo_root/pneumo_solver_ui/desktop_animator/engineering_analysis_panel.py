# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from .data_bundle import CORNERS, DataBundle
from .engineering_analysis import (
    CORNER_METRIC_OPTIONS,
    GLOBAL_METRIC_OPTIONS,
    MODE_OPTIONS,
    AnalysisCatalog,
    build_multifactor_analysis_payload,
    collect_analysis_catalog,
    rank_global_focus_metrics,
)


def _lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    tt = float(max(0.0, min(1.0, t)))
    return tuple(
        int(round((1.0 - tt) * float(x) + tt * float(y)))
        for x, y in zip(tuple(a), tuple(b))
    )


def _heat_color(score: float, *, signed: float | None = None) -> QtGui.QColor:
    cool = (48, 132, 230)
    warm = (245, 130, 56)
    neutral = (86, 97, 112)
    if signed is None:
        rgb = _lerp_color(neutral, (232, 92, 66), float(score))
    elif float(signed) >= 0.0:
        rgb = _lerp_color(neutral, warm, float(score))
    else:
        rgb = _lerp_color(neutral, cool, float(score))
    return QtGui.QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))


class _CornerCloudCanvas(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(156)
        self._payload: dict[str, dict[str, object]] = {}

    def set_payload(self, payload: dict[str, dict[str, object]]) -> None:
        if payload == self._payload:
            return
        self._payload = dict(payload or {})
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)

        bg = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QtGui.QColor(35, 31, 26))
        bg.setColorAt(0.52, QtGui.QColor(28, 32, 39))
        bg.setColorAt(1.0, QtGui.QColor(16, 20, 28))
        p.setPen(QtGui.QPen(QtGui.QColor(66, 74, 86), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 12.0, 12.0)

        # Soft "pebbles on sand" background for a calmer engineering canvas.
        p.setPen(QtCore.Qt.NoPen)
        pebble_brushes = (
            QtGui.QColor(128, 108, 77, 28),
            QtGui.QColor(166, 148, 110, 22),
            QtGui.QColor(88, 99, 114, 24),
        )
        step_x = 34
        step_y = 22
        for iy in range(1, int(rect.height() // step_y) + 2):
            for ix in range(1, int(rect.width() // step_x) + 2):
                seed = (ix * 37) + (iy * 61)
                cx = rect.left() + (ix * step_x) + (seed % 9) - 4
                cy = rect.top() + (iy * step_y) + ((seed // 5) % 7) - 3
                rr = 1.2 + float(seed % 4)
                p.setBrush(pebble_brushes[seed % len(pebble_brushes)])
                p.drawEllipse(QtCore.QPointF(cx, cy), rr, rr * (0.55 + 0.20 * (seed % 3)))

        body = QtCore.QRectF(
            rect.left() + 0.18 * rect.width(),
            rect.top() + 0.22 * rect.height(),
            0.64 * rect.width(),
            0.54 * rect.height(),
        )
        body_grad = QtGui.QLinearGradient(body.topLeft(), body.bottomRight())
        body_grad.setColorAt(0.0, QtGui.QColor(70, 80, 94, 210))
        body_grad.setColorAt(1.0, QtGui.QColor(34, 40, 50, 224))
        p.setPen(QtGui.QPen(QtGui.QColor(190, 203, 216, 62), 1.1))
        p.setBrush(body_grad)
        p.drawRoundedRect(body, 20.0, 20.0)

        cabin = QtCore.QRectF(
            body.left() + 0.18 * body.width(),
            body.top() + 0.12 * body.height(),
            0.64 * body.width(),
            0.30 * body.height(),
        )
        cabin_grad = QtGui.QLinearGradient(cabin.topLeft(), cabin.bottomLeft())
        cabin_grad.setColorAt(0.0, QtGui.QColor(156, 202, 232, 68))
        cabin_grad.setColorAt(1.0, QtGui.QColor(60, 90, 120, 18))
        p.setBrush(cabin_grad)
        p.drawRoundedRect(cabin, 14.0, 14.0)

        center_line = QtCore.QLineF(body.center().x(), body.top() + 8.0, body.center().x(), body.bottom() - 8.0)
        p.setPen(QtGui.QPen(QtGui.QColor(220, 225, 232, 26), 1.0, QtCore.Qt.DashLine))
        p.drawLine(center_line)

        wheel_pos = {
            "ЛП": QtCore.QPointF(body.left() + 0.12 * body.width(), body.top() + 0.16 * body.height()),
            "ПП": QtCore.QPointF(body.right() - 0.12 * body.width(), body.top() + 0.16 * body.height()),
            "ЛЗ": QtCore.QPointF(body.left() + 0.12 * body.width(), body.bottom() - 0.16 * body.height()),
            "ПЗ": QtCore.QPointF(body.right() - 0.12 * body.width(), body.bottom() - 0.16 * body.height()),
        }

        title_rect = QtCore.QRectF(rect.left() + 12.0, rect.top() + 8.0, rect.width() - 24.0, 22.0)
        p.setPen(QtGui.QPen(QtGui.QColor(221, 229, 238), 1.0))
        title_font = QtGui.QFont(self.font())
        title_font.setBold(True)
        p.setFont(title_font)
        p.drawText(title_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, "Corner Cloud")

        meta_font = QtGui.QFont(self.font())
        meta_font.setPointSize(max(8, meta_font.pointSize() - 1))
        p.setFont(meta_font)

        for corner in CORNERS:
            c = str(corner)
            data = dict(self._payload.get(c, {}))
            score = float(max(0.0, min(1.0, float(data.get("score", 0.0) or 0.0))))
            metric_label = str(data.get("label", "—"))
            value_text = str(data.get("value_text", "—"))
            pos = wheel_pos[c]

            base_radius = 18.0
            cloud_radius = base_radius + (28.0 * score)
            accent = _heat_color(score, signed=float(data.get("value", 0.0) or 0.0))
            cloud = QtGui.QRadialGradient(pos, cloud_radius)
            cloud.setColorAt(0.0, QtGui.QColor(accent.red(), accent.green(), accent.blue(), 166))
            cloud.setColorAt(0.42, QtGui.QColor(accent.red(), accent.green(), accent.blue(), 72))
            cloud.setColorAt(1.0, QtGui.QColor(accent.red(), accent.green(), accent.blue(), 0))
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(cloud)
            p.drawEllipse(pos, cloud_radius, cloud_radius)

            halo = QtGui.QRadialGradient(pos.x(), pos.y() - 2.0, base_radius * 0.9)
            halo.setColorAt(0.0, QtGui.QColor(255, 255, 255, 95))
            halo.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
            p.setBrush(halo)
            p.drawEllipse(pos, base_radius * 0.9, base_radius * 0.9)

            p.setBrush(QtGui.QColor(26, 32, 40, 214))
            p.setPen(QtGui.QPen(QtGui.QColor(236, 241, 247, 180), 1.1))
            p.drawEllipse(pos, base_radius, base_radius)

            code_font = QtGui.QFont(self.font())
            code_font.setBold(True)
            p.setFont(code_font)
            p.drawText(
                QtCore.QRectF(pos.x() - 18.0, pos.y() - 12.0, 36.0, 18.0),
                QtCore.Qt.AlignCenter,
                c,
            )

            p.setFont(meta_font)
            p.setPen(QtGui.QPen(QtGui.QColor(228, 235, 243), 1.0))
            p.drawText(
                QtCore.QRectF(pos.x() - 44.0, pos.y() + 18.0, 88.0, 18.0),
                QtCore.Qt.AlignCenter,
                value_text,
            )
            p.setPen(QtGui.QPen(QtGui.QColor(170, 183, 197), 1.0))
            p.drawText(
                QtCore.QRectF(pos.x() - 58.0, pos.y() + 34.0, 116.0, 18.0),
                QtCore.Qt.AlignCenter,
                metric_label,
            )


class _CorrelationMatrixCanvas(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(270)
        self._labels: list[str] = []
        self._names: list[str] = []
        self._current_text: dict[str, str] = {}
        self._matrix = np.zeros((0, 0), dtype=float)
        self._highlight_focus = False

    def set_payload(
        self,
        *,
        names: list[str],
        labels: list[str],
        current_text: dict[str, str],
        matrix: np.ndarray,
        highlight_focus: bool,
    ) -> None:
        self._names = list(names)
        self._labels = list(labels)
        self._current_text = dict(current_text or {})
        self._matrix = np.asarray(matrix, dtype=float)
        self._highlight_focus = bool(highlight_focus)
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QtGui.QColor(18, 22, 29))
        bg.setColorAt(1.0, QtGui.QColor(12, 16, 22))
        p.setPen(QtGui.QPen(QtGui.QColor(54, 62, 74), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 12.0, 12.0)

        n = len(self._labels)
        if n <= 0:
            p.setPen(QtGui.QPen(QtGui.QColor(210, 218, 228), 1.0))
            p.drawText(rect, QtCore.Qt.AlignCenter, "Нет данных для матрицы связей")
            return

        left_margin = 144.0
        top_margin = 84.0
        right_margin = 120.0
        bottom_margin = 20.0
        matrix_side = min(
            max(80.0, rect.width() - left_margin - right_margin),
            max(80.0, rect.height() - top_margin - bottom_margin),
        )
        cell = matrix_side / float(max(1, n))
        origin = QtCore.QPointF(rect.left() + left_margin, rect.top() + top_margin)
        fm = QtGui.QFontMetrics(self.font())

        title_font = QtGui.QFont(self.font())
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QtGui.QPen(QtGui.QColor(224, 232, 240), 1.0))
        p.drawText(
            QtCore.QRectF(rect.left() + 12.0, rect.top() + 8.0, rect.width() - 24.0, 24.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Correlation Heatmap",
        )

        label_font = QtGui.QFont(self.font())
        label_font.setPointSize(max(8, label_font.pointSize() - 1))
        p.setFont(label_font)

        for i, label in enumerate(self._labels):
            row_rect = QtCore.QRectF(rect.left() + 12.0, origin.y() + (i * cell), left_margin - 18.0, cell)
            value_text = self._current_text.get(self._names[i], "")
            p.setPen(QtGui.QPen(QtGui.QColor(201, 210, 220), 1.0))
            p.drawText(row_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, fm.elidedText(label, QtCore.Qt.ElideRight, int(row_rect.width() - 8.0)))
            p.setPen(QtGui.QPen(QtGui.QColor(133, 146, 162), 1.0))
            p.drawText(row_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, value_text)

            top_rect = QtCore.QRectF(origin.x() + (i * cell), rect.top() + 34.0, cell, top_margin - 26.0)
            p.save()
            p.translate(top_rect.center())
            p.rotate(-37.0)
            p.setPen(QtGui.QPen(QtGui.QColor(178, 189, 202), 1.0))
            elided = fm.elidedText(label, QtCore.Qt.ElideRight, int(cell * 1.7))
            p.drawText(QtCore.QRectF(-cell * 0.82, -10.0, cell * 1.64, 20.0), QtCore.Qt.AlignCenter, elided)
            p.restore()

        for i in range(n):
            for j in range(n):
                cell_rect = QtCore.QRectF(origin.x() + (j * cell), origin.y() + (i * cell), cell, cell).adjusted(1.0, 1.0, -1.0, -1.0)
                corr = float(self._matrix[i, j]) if i < self._matrix.shape[0] and j < self._matrix.shape[1] else 0.0
                strength = abs(corr) if i != j else 0.0
                if i == j:
                    fill = QtGui.QColor(46, 56, 68, 210)
                    if self._highlight_focus and i == 0:
                        fill = QtGui.QColor(86, 70, 45, 230)
                    p.setPen(QtGui.QPen(QtGui.QColor(106, 118, 132), 1.0))
                    p.setBrush(fill)
                    p.drawRoundedRect(cell_rect, 6.0, 6.0)
                    continue

                accent = _heat_color(strength, signed=corr)
                grad = QtGui.QRadialGradient(cell_rect.center(), 0.72 * cell_rect.width())
                grad.setColorAt(0.0, QtGui.QColor(accent.red(), accent.green(), accent.blue(), int(54 + (160 * strength))))
                grad.setColorAt(0.55, QtGui.QColor(accent.red(), accent.green(), accent.blue(), int(18 + (72 * strength))))
                grad.setColorAt(1.0, QtGui.QColor(accent.red(), accent.green(), accent.blue(), 0))
                p.setPen(QtGui.QPen(QtGui.QColor(68, 76, 88, 155), 1.0))
                p.setBrush(grad)
                p.drawRoundedRect(cell_rect, 5.0, 5.0)

                p.setPen(QtGui.QPen(QtGui.QColor(228, 235, 244, int(120 + (100 * strength))), 1.0))
                txt = f"{corr:+.2f}"
                p.drawText(cell_rect, QtCore.Qt.AlignCenter, txt)


class MultiFactorAnalysisPanel(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._bundle_key: Optional[int] = None
        self._catalog: Optional[AnalysisCatalog] = None
        self._compact_mode = False
        self._last_payload_key: Optional[tuple[object, ...]] = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        controls = QtWidgets.QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.lbl_title = QtWidgets.QLabel("Мультифакторный анализ")
        self.lbl_title.setStyleSheet("font-weight:600;")

        self.cb_mode = QtWidgets.QComboBox()
        for key, label in MODE_OPTIONS:
            self.cb_mode.addItem(label, userData=key)
        self.cb_mode.currentIndexChanged.connect(self._on_controls_changed)

        self.cb_focus = QtWidgets.QComboBox()
        for key, label in GLOBAL_METRIC_OPTIONS:
            self.cb_focus.addItem(label, userData=key)
        self.cb_focus.currentIndexChanged.connect(self._on_controls_changed)

        self.cb_corner_family = QtWidgets.QComboBox()
        for key, label in CORNER_METRIC_OPTIONS:
            self.cb_corner_family.addItem(label, userData=key)
        self.cb_corner_family.currentIndexChanged.connect(self._on_controls_changed)

        self.cb_window = QtWidgets.QComboBox()
        for seconds in (0.8, 1.5, 3.0, 6.0, 12.0):
            self.cb_window.addItem(f"окно {seconds:g} c", userData=float(seconds))
        self.cb_window.setCurrentIndex(2)
        self.cb_window.currentIndexChanged.connect(self._on_controls_changed)

        controls.addWidget(self.lbl_title, 1)
        self.lbl_mode = QtWidgets.QLabel("Режим")
        controls.addWidget(self.lbl_mode)
        controls.addWidget(self.cb_mode)
        self.lbl_focus = QtWidgets.QLabel("Фокус")
        controls.addWidget(self.lbl_focus)
        controls.addWidget(self.cb_focus)
        self.lbl_corner_family = QtWidgets.QLabel("Углы")
        controls.addWidget(self.lbl_corner_family)
        controls.addWidget(self.cb_corner_family)
        controls.addWidget(self.cb_window)
        outer.addLayout(controls)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)
        preset_row.addWidget(QtWidgets.QLabel("Пресеты"))

        self.btn_preset_balance = QtWidgets.QToolButton()
        self.btn_preset_balance.setText("Balance")
        self.btn_preset_balance.clicked.connect(lambda: self._apply_preset("balance"))
        preset_row.addWidget(self.btn_preset_balance)

        self.btn_preset_ride = QtWidgets.QToolButton()
        self.btn_preset_ride.setText("Ride")
        self.btn_preset_ride.clicked.connect(lambda: self._apply_preset("ride"))
        preset_row.addWidget(self.btn_preset_ride)

        self.btn_preset_contact = QtWidgets.QToolButton()
        self.btn_preset_contact.setText("Contact")
        self.btn_preset_contact.clicked.connect(lambda: self._apply_preset("contact"))
        preset_row.addWidget(self.btn_preset_contact)

        self.btn_preset_pneumo = QtWidgets.QToolButton()
        self.btn_preset_pneumo.setText("Pneumo")
        self.btn_preset_pneumo.clicked.connect(lambda: self._apply_preset("pneumo"))
        preset_row.addWidget(self.btn_preset_pneumo)

        self.cb_auto_focus = QtWidgets.QCheckBox("Auto focus")
        self.cb_auto_focus.setToolTip("В режиме 'Фокус↔Все' автоматически выбирает самую значимую метрику в текущем окне.")
        self.cb_auto_focus.toggled.connect(lambda _checked: self._on_controls_changed(-1))
        preset_row.addWidget(self.cb_auto_focus)

        self.lbl_focus_hint = QtWidgets.QLabel("smart: —")
        self.lbl_focus_hint.setStyleSheet("color:#9bb0c5;")
        preset_row.addWidget(self.lbl_focus_hint, 1)
        outer.addLayout(preset_row)

        self.cloud = _CornerCloudCanvas()
        outer.addWidget(self.cloud)

        self.matrix = _CorrelationMatrixCanvas()
        outer.addWidget(self.matrix, 1)

        self.summary = QtWidgets.QTextBrowser()
        self.summary.setOpenExternalLinks(False)
        self.summary.setStyleSheet(
            "QTextBrowser{background:#0f141b;border:1px solid #2b3440;border-radius:10px;color:#d9e2ec;}"
        )
        self.summary.setMinimumHeight(148)
        outer.addWidget(self.summary)

        self._sync_control_visibility()

    def set_compact_dock_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self.cloud.setMinimumHeight(132 if compact else 156)
        self.summary.setMinimumHeight(122 if compact else 148)

    def _set_combo_data(self, combo: QtWidgets.QComboBox, target: str) -> None:
        idx = combo.findData(str(target))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _apply_preset(self, name: str) -> None:
        presets: dict[str, dict[str, object]] = {
            "balance": {"mode": "all_all", "window": 3.0, "auto_focus": False},
            "ride": {"mode": "one_all", "focus": "body_az_mean", "window": 3.0, "auto_focus": True},
            "contact": {"mode": "corner_corner", "corner": "wheel_road", "window": 1.5, "auto_focus": False},
            "pneumo": {"mode": "one_all", "focus": "pressure_spread_bar", "corner": "stroke", "window": 6.0, "auto_focus": False},
        }
        preset = dict(presets.get(str(name), presets["balance"]))
        blockers = [
            QtCore.QSignalBlocker(self.cb_mode),
            QtCore.QSignalBlocker(self.cb_focus),
            QtCore.QSignalBlocker(self.cb_corner_family),
            QtCore.QSignalBlocker(self.cb_window),
            QtCore.QSignalBlocker(self.cb_auto_focus),
        ]
        try:
            self._set_combo_data(self.cb_mode, str(preset.get("mode", "all_all")))
            self._set_combo_data(self.cb_focus, str(preset.get("focus", "roll_proxy")))
            self._set_combo_data(self.cb_corner_family, str(preset.get("corner", "wheel_road")))
            window_idx = self.cb_window.findData(float(preset.get("window", 3.0)))
            if window_idx >= 0:
                self.cb_window.setCurrentIndex(window_idx)
            self.cb_auto_focus.setChecked(bool(preset.get("auto_focus", False)))
        finally:
            blockers.clear()
        self._on_controls_changed(-1)

    def _sync_control_visibility(self) -> None:
        mode = str(self.cb_mode.currentData() or "all_all")
        show_focus = mode == "one_all"
        show_corner = mode == "corner_corner"
        self.lbl_focus.setVisible(show_focus)
        self.cb_focus.setVisible(show_focus)
        self.lbl_corner_family.setVisible(show_corner)
        self.cb_corner_family.setVisible(show_corner)
        self.cb_auto_focus.setVisible(show_focus)

    def _on_controls_changed(self, _idx: int) -> None:
        self._sync_control_visibility()
        self._last_payload_key = None

    def set_bundle(self, bundle: DataBundle) -> None:
        self._bundle_key = id(bundle)
        self._catalog = collect_analysis_catalog(bundle)
        self._last_payload_key = None

    def update_frame(self, bundle: DataBundle, i: int, *, sample_t: float | None = None) -> None:
        if int(getattr(self, "_bundle_key", 0) or 0) != id(bundle) or self._catalog is None:
            self.set_bundle(bundle)
        if self._catalog is None:
            return

        mode = str(self.cb_mode.currentData() or "all_all")
        focus_metric = str(self.cb_focus.currentData() or "roll_proxy")
        corner_metric = str(self.cb_corner_family.currentData() or "wheel_road")
        window_s = float(self.cb_window.currentData() or 3.0)
        center_t = float(sample_t if sample_t is not None else np.asarray(bundle.t, dtype=float)[int(max(0, min(i, len(bundle.t) - 1)))])
        ranked_focus = rank_global_focus_metrics(
            self._catalog,
            idx=int(i),
            sample_t=center_t,
            window_s=window_s,
        )
        if ranked_focus:
            best_focus = str(ranked_focus[0].get("metric", focus_metric))
            best_label = str(ranked_focus[0].get("label", best_focus))
            best_text = str(ranked_focus[0].get("value_text", "—"))
            self.lbl_focus_hint.setText(f"smart: {best_label} = {best_text}")
            if mode == "one_all" and bool(self.cb_auto_focus.isChecked()) and best_focus != focus_metric:
                blocker = QtCore.QSignalBlocker(self.cb_focus)
                try:
                    self._set_combo_data(self.cb_focus, best_focus)
                finally:
                    del blocker
                focus_metric = best_focus
                self._last_payload_key = None
        else:
            self.lbl_focus_hint.setText("smart: —")

        payload_key = (
            id(bundle),
            str(mode),
            str(focus_metric),
            str(corner_metric),
            round(float(window_s), 3),
            round(float(center_t), 4),
        )
        if payload_key == self._last_payload_key:
            return
        self._last_payload_key = payload_key

        payload = build_multifactor_analysis_payload(
            self._catalog,
            idx=int(i),
            sample_t=center_t,
            mode=mode,
            focus_metric=focus_metric,
            corner_metric=corner_metric,
            window_s=window_s,
        )

        names = list(payload.get("names", []) or [])
        labels = list(payload.get("labels", []) or [])
        current_text = dict(payload.get("current_text", {}) or {})
        matrix = np.asarray(payload.get("matrix", np.zeros((0, 0), dtype=float)), dtype=float)
        self.cloud.set_payload(dict(payload.get("corner_cloud", {}) or {}))
        self.matrix.set_payload(
            names=names,
            labels=labels,
            current_text=current_text,
            matrix=matrix,
            highlight_focus=(mode == "one_all"),
        )
        self.summary.setHtml(self._build_summary_html(payload, ranked_focus))

    def _build_summary_html(self, payload: dict[str, object], ranked_focus: list[dict[str, object]]) -> str:
        center_t = float(payload.get("center_t_s", 0.0) or 0.0)
        window_s = float(payload.get("window_s", 0.0) or 0.0)
        insights = [str(x) for x in (payload.get("insights", []) or []) if str(x).strip()]
        top_pairs = list(payload.get("top_pairs", []) or [])
        parts = [
            "<div style='font-weight:600;color:#eef4fb;'>Heuristic Assistant</div>",
            f"<div style='color:#93a4b6;margin-top:4px;'>t = {center_t:.2f} c, окно = {window_s:.2f} c</div>",
        ]
        if ranked_focus:
            parts.append("<div style='font-weight:600;color:#eef4fb;margin-top:8px;'>Smart focus</div>")
            for item in ranked_focus[:3]:
                parts.append(
                    "<div style='display:flex;align-items:center;margin-top:4px;'>"
                    f"<div style='width:180px;color:#d6deea;'>{str(item.get('label', '—'))}</div>"
                    f"<div style='width:74px;color:#8ea4ba;'>score {float(item.get('score', 0.0)):.2f}</div>"
                    f"<div style='color:#b9c7d5;'>{str(item.get('value_text', '—'))}</div>"
                    "</div>"
                )
        if insights:
            parts.append("<div style='margin-top:8px;'>")
            for item in insights:
                parts.append(f"<div style='margin:0 0 6px 0;'>• {item}</div>")
            parts.append("</div>")
        if top_pairs:
            parts.append("<div style='font-weight:600;color:#eef4fb;margin-top:6px;'>Топ связей</div>")
            for pair in top_pairs[:4]:
                corr = float(pair.get("corr", 0.0) or 0.0)
                strength = min(1.0, abs(corr))
                width = 42 + int(round(128.0 * strength))
                color = "#f28a37" if corr >= 0.0 else "#4b8ef8"
                left = str(pair.get("left_label", pair.get("left", "")))
                right = str(pair.get("right_label", pair.get("right", "")))
                parts.append(
                    "<div style='display:flex;align-items:center;margin:6px 0 0 0;'>"
                    f"<div style='width:210px;color:#d6deea;'>{left} ↔ {right}</div>"
                    f"<div style='height:8px;width:{width}px;background:{color};border-radius:999px;margin-right:8px;opacity:0.85;'></div>"
                    f"<div style='color:#aebccc;'>{corr:+.2f}</div>"
                    "</div>"
                )
        return "".join(parts)


__all__ = ["MultiFactorAnalysisPanel"]
