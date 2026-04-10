# -*- coding: utf-8 -*-
"""Separate Windows desktop mnemonic viewer for pneumatic runs."""

from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Optional

import numpy as np

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from PySide6 import QtWebChannel, QtWebEngineWidgets

    _HAS_WEBENGINE = True
except Exception:
    QtWebChannel = None  # type: ignore[assignment]
    QtWebEngineWidgets = None  # type: ignore[assignment]
    _HAS_WEBENGINE = False

try:
    import pyqtgraph as pg

    pg.setConfigOptions(antialias=True, foreground="#d9e6ed")
    _HAS_PG = True
except Exception:
    pg = None  # type: ignore[assignment]
    _HAS_PG = False

from pneumo_solver_ui.desktop_animator.data_bundle import DataBundle, load_npz
from pneumo_solver_ui.desktop_animator.ui_state import UiState, default_settings_path
from pneumo_solver_ui.ui_svg_flow_helpers import default_svg_pressure_nodes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = PROJECT_ROOT / "pneumo_solver_ui"
COMPONENT_HTML_PATH = UI_ROOT / "components" / "pneumo_svg_flow" / "index.html"
SCHEME_JSON_PATH = UI_ROOT / "PNEUMO_SCHEME.json"

VIEWBOX_W = 2200.0
VIEWBOX_H = 1500.0
VIEWBOX = f"0 0 {int(VIEWBOX_W)} {int(VIEWBOX_H)}"
PLAYHEAD_STORAGE_KEY = "pneumo_desktop_mnemo_playhead"
EVENT_LOG_SCHEMA_VERSION = "desktop_mnemo_event_log_v1"

SUPPLY_POSITIONS: dict[str, tuple[float, float]] = {
    "АТМ": (180.0, 150.0),
    "Ресивер1": (760.0, 150.0),
    "Ресивер2": (1100.0, 150.0),
    "Ресивер3": (1450.0, 150.0),
    "Аккумулятор": (1840.0, 150.0),
    "узел_после_предохран_Pmax": (1600.0, 300.0),
    "узел_после_рег_Pmid": (1450.0, 390.0),
    "узел_после_ОК_Pmid": (1260.0, 390.0),
    "узел_после_рег_Pmin_сброс": (1450.0, 520.0),
    "узел_после_ОК_Pmin": (1260.0, 520.0),
    "узел_после_рег_заряд_аккумулятора": (1760.0, 390.0),
    "узел_после_рег_Pmin_питание_Р2": (1760.0, 520.0),
    "Магистраль_ПП2_ЛЗ2": (980.0, 980.0),
    "Магистраль_ЛП2_ПЗ2": (1220.0, 980.0),
}

CORNER_ANCHORS: dict[str, tuple[float, float]] = {
    "ЛП": (520.0, 790.0),
    "ПП": (1680.0, 790.0),
    "ЛЗ": (520.0, 1180.0),
    "ПЗ": (1680.0, 1180.0),
}

SUPPLY_LABELS: dict[str, tuple[str, str]] = {
    "АТМ": ("АТМ", "сброс / атмосфера"),
    "Ресивер1": ("Ресивер 1", "контур Ц1 / штоковые"),
    "Ресивер2": ("Ресивер 2", "контур Ц2 / питание"),
    "Ресивер3": ("Ресивер 3", "магистрали / регуляторы"),
    "Аккумулятор": ("Аккумулятор", "линия after-self"),
    "узел_после_предохран_Pmax": ("Pmax", "после предохранительного"),
    "узел_после_рег_Pmid": ("Pmid reg", "регулятор до себя"),
    "узел_после_ОК_Pmid": ("Pmid chk", "обратный к выхлопу"),
    "узел_после_рег_Pmin_сброс": ("Pmin reg", "сброс"),
    "узел_после_ОК_Pmin": ("Pmin chk", "обратный к выхлопу"),
    "узел_после_рег_заряд_аккумулятора": ("ACC charge", "заряд аккумулятора"),
    "узел_после_рег_Pmin_питание_Р2": ("Pmin -> Р2", "питание Ресивер2"),
    "Магистраль_ПП2_ЛЗ2": ("Магистраль ПП2-ЛЗ2", "диагональный сбор"),
    "Магистраль_ЛП2_ПЗ2": ("Магистраль ЛП2-ПЗ2", "диагональный сбор"),
}

KEY_NODE_HINTS = (
    "Ресивер1",
    "Ресивер2",
    "Ресивер3",
    "Аккумулятор",
    "узел_после_предохран_Pmax",
    "узел_после_рег_Pmid",
    "узел_после_рег_Pmin_сброс",
    "узел_после_рег_Pmin_питание_Р2",
    "Магистраль_ПП2_ЛЗ2",
    "Магистраль_ЛП2_ПЗ2",
)

CHAMBER_RE = re.compile(r"^Ц(?P<cyl>[12])_(?P<corner>ЛП|ПП|ЛЗ|ПЗ)_(?P<ch>БП|ШП)$")
DIAGONAL_RE = re.compile(
    r"^узел_(?P<src_corner>ЛП|ПП|ЛЗ|ПЗ)(?P<src_ch>CAP|ROD)_к_(?P<dst_corner>ЛП|ПП|ЛЗ|ПЗ)(?P<dst_ch>CAP|ROD)_(?P<stage>междуОКиДР|послеДР)$"
)

BOOTSTRAP_JS = """
(function() {
  if (window.__codexMnemoBootstrapInstalled) return "ok";
  window.__codexMnemoBootstrapInstalled = true;
  function installBridge(channel) {
    window.codexBridge = channel.objects.codexBridge;
    try {
      if (window.parent && typeof window.parent === "object") {
        window.parent.postMessage = function(data, _target) {
          try {
            window.codexBridge.postMessage(JSON.stringify(data || null));
          } catch (err) {
            console.error("codex bridge postMessage failed", err);
          }
        };
      }
    } catch (err) {
      console.error("codex bridge patch failed", err);
    }
  }
  if (window.QWebChannel && window.qt && window.qt.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport, function(channel) {
      installBridge(channel);
    });
  }
  window.codexMnemoDispatch = function(args) {
    window.dispatchEvent(new MessageEvent("message", { data: { type: "streamlit:render", args: args || {} } }));
    return true;
  };
  window.codexMnemoSetPlayhead = function(state) {
    try {
      var key = String((state && state.key) || (window.DATA && DATA.playhead_storage_key) || "pneumo_desktop_mnemo_playhead");
      localStorage.setItem(key, JSON.stringify(state || {}));
      if (state && state.idx !== undefined && state.idx !== null && typeof slider !== "undefined" && slider) {
        idx = Number(state.idx) || 0;
        slider.value = String(idx);
      }
      if (typeof __FLOW_DIRTY !== "undefined") __FLOW_DIRTY = true;
      if (typeof __wakeLoop === "function") __wakeLoop();
      return true;
    } catch (err) {
      return String(err);
    }
  };
  window.codexMnemoSetSelection = function(sel) {
    try {
      if (!window.__lastArgs) return false;
      var args = Object.assign({}, window.__lastArgs || {});
      args.selected = sel || {};
      window.__lastArgs = args;
      build(args);
      return true;
    } catch (err) {
      return String(err);
    }
  };
  window.codexMnemoSetAlerts = function(alerts) {
    try {
      if (!window.__lastArgs) window.__lastArgs = {};
      window.__lastArgs = Object.assign({}, window.__lastArgs || {}, { alerts: alerts || {} });
      if (typeof DATA !== "undefined" && DATA) DATA.alerts = alerts || {};
      if (typeof updateAlertOverlay === "function") updateAlertOverlay();
      return true;
    } catch (err) {
      return String(err);
    }
  };
  window.codexMnemoSetFocusRegion = function(focus) {
    try {
      if (!window.__lastArgs) window.__lastArgs = {};
      window.__lastArgs = Object.assign({}, window.__lastArgs || {}, { focus_region: focus || null });
      if (typeof DATA !== "undefined" && DATA) DATA.focus_region = focus || null;
      if (typeof applyFocusRegion === "function") applyFocusRegion(focus || null, { source: "qt-bridge" });
      return true;
    } catch (err) {
      return String(err);
    }
  };
  window.codexMnemoShowOverview = function(meta) {
    try {
      if (!window.__lastArgs) window.__lastArgs = {};
      if (meta && Object.prototype.hasOwnProperty.call(meta, "focus_region")) {
        window.__lastArgs = Object.assign({}, window.__lastArgs || {}, { focus_region: meta.focus_region || null });
        if (typeof DATA !== "undefined" && DATA) DATA.focus_region = meta.focus_region || null;
      }
      if (typeof showFocusOverview === "function") {
        return !!showFocusOverview(meta || {});
      }
      return false;
    } catch (err) {
      return String(err);
    }
  };
  return "ok";
})();
"""

APP_STYLESHEET_DARK = """
QMainWindow, QWidget {
  background: #09141a;
  color: #d9e6ed;
  font-family: "Bahnschrift SemiCondensed", "Segoe UI", sans-serif;
  font-size: 10pt;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
  background: #0d1d25;
  color: #d9e6ed;
}
QToolBar { spacing: 8px; border: 0; padding: 6px 8px; }
QDockWidget { border: 1px solid #16303b; }
QDockWidget::title {
  background: #0f2530;
  color: #f0f6f9;
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid #16303b;
}
QLabel#kpiValue { font-size: 18pt; font-weight: 700; color: #f0f6f9; }
QLabel#kpiCaption { color: #88a3af; font-size: 8.5pt; }
QPushButton, QToolButton, QComboBox {
  background: #12303b;
  color: #e7f2f7;
  border: 1px solid #1b4553;
  border-radius: 8px;
  padding: 6px 10px;
}
QPushButton:hover, QToolButton:hover, QComboBox:hover { background: #173a47; }
QPushButton:checked, QToolButton:checked { background: #1c5363; border-color: #63d3f5; }
QLineEdit, QTextBrowser, QTableWidget {
  background: #0f212b;
  color: #d9e6ed;
  border: 1px solid #16303b;
  border-radius: 10px;
}
QHeaderView::section {
  background: #12303b;
  color: #d9e6ed;
  padding: 6px;
  border: 0;
  border-right: 1px solid #16303b;
}
QTableWidget { gridline-color: #16303b; selection-background-color: #1a4654; }
QSlider::groove:horizontal { height: 8px; background: #12303b; border-radius: 4px; }
QSlider::handle:horizontal { width: 16px; margin: -5px 0; border-radius: 8px; background: #63d3f5; }
QFrame#startup_banner {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #102733, stop:1 #143847);
  border: 1px solid #1e5365;
  border-radius: 16px;
}
QLabel#startup_banner_title {
  font-size: 15pt;
  font-weight: 700;
  color: #f0f6f9;
}
QLabel#startup_banner_caption {
  color: #9fc5d2;
  font-size: 9pt;
}
QTextBrowser#startup_banner_body {
  background: transparent;
  color: #d9e6ed;
  border: 0;
}
"""

APP_STYLESHEET_LIGHT = """
QMainWindow, QWidget {
  background: #f4f7f9;
  color: #102028;
  font-family: "Bahnschrift SemiCondensed", "Segoe UI", sans-serif;
}
QDockWidget::title {
  background: #e6eef2;
  color: #102028;
  padding: 8px 10px;
  border-bottom: 1px solid #ccd9df;
}
QPushButton, QToolButton, QComboBox {
  background: #ffffff;
  color: #102028;
  border: 1px solid #c5d4db;
  border-radius: 8px;
  padding: 6px 10px;
}
QLineEdit, QTextBrowser, QTableWidget {
  background: #ffffff;
  color: #102028;
  border: 1px solid #ccd9df;
  border-radius: 10px;
}
QTableWidget { gridline-color: #dce7ec; }
QFrame#startup_banner {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #edf5f8);
  border: 1px solid #ccd9df;
  border-radius: 16px;
}
QLabel#startup_banner_title {
  font-size: 15pt;
  font-weight: 700;
  color: #102028;
}
QLabel#startup_banner_caption {
  color: #516a75;
  font-size: 9pt;
}
QTextBrowser#startup_banner_body {
  background: transparent;
  color: #102028;
  border: 0;
}
"""


@dataclass
class MnemoDataset:
    npz_path: Path
    bundle: DataBundle
    dataset_id: str
    svg_inline: str
    mapping: dict[str, Any]
    edge_names: list[str]
    node_names: list[str]
    overlay_node_names: list[str]
    edge_series: list[dict[str, Any]]
    node_series: list[dict[str, Any]]
    edge_defs: dict[str, dict[str, Any]]
    time_s: np.ndarray
    q_scale: float
    q_unit: str
    p_atm: float


@dataclass
class DiagnosticMode:
    title: str
    severity: str
    summary: str
    action: str


@dataclass
class FrameNarrative:
    primary_title: str
    primary_summary: str
    top_edge_name: str
    top_edge_value: float
    top_node_name: str
    top_node_value: float
    pressure_spread: float
    modes: list[DiagnosticMode]


@dataclass(frozen=True)
class LaunchOnboardingContext:
    preset_key: str
    title: str
    reason: str
    checklist: tuple[str, ...]
    launch_mode: str


@dataclass(frozen=True)
class OnboardingFocusTarget:
    edge_name: str
    node_name: str
    mode_title: str
    summary: str
    has_target: bool


@dataclass(frozen=True)
class MnemoTimelineEvent:
    frame_idx: int
    time_s: float
    kind: str
    severity: str
    title: str
    summary: str
    edge_name: str
    node_name: str


def build_launch_onboarding_context(
    *,
    npz_path: Path | None,
    follow: bool,
    pointer_path: Path | None,
    preset_key: str = "",
    title: str = "",
    reason: str = "",
    checklist: list[str] | tuple[str, ...] | None = None,
) -> LaunchOnboardingContext:
    launch_mode = "follow" if follow else ("npz" if npz_path is not None else "blank")
    normalized_checks = tuple(str(x).strip() for x in (checklist or []) if str(x).strip())
    pointer_name = Path(pointer_path).name if pointer_path else "anim_latest.json"
    npz_name = Path(npz_path).name if npz_path is not None else "NPZ ещё не выбран"

    if not title:
        if launch_mode == "follow":
            title = "Live follow-разбор"
        elif launch_mode == "npz":
            title = "Ретроспективный разбор NPZ"
        else:
            title = "Пустой инженерный старт"

    if not reason:
        if launch_mode == "follow":
            reason = (
                f"Окно открыто в follow-режиме и будет держаться за pointer {pointer_name}, "
                "чтобы оператор видел актуальный сценарий без ручного reopen."
            )
        elif launch_mode == "npz":
            reason = (
                f"Окно открыто на фиксированном bundle {npz_name}, чтобы спокойно разобрать одну историю "
                "без переключения на новые экспорты."
            )
        else:
            reason = (
                "Окно открыто без привязанного bundle. Это безопасный режим для ориентации в интерфейсе, "
                "перед тем как подключать live pointer или конкретный NPZ."
            )

    if not normalized_checks:
        if launch_mode == "follow":
            normalized_checks = (
                "Сначала подтвердите ведущую ветку и один опорный узел давления.",
                "ACK/Reset делайте только после того, как режим на схеме совпал с трендами.",
                "Если pointer обновится, сравните новый кадр с предыдущим режимом, а не читайте схему заново целиком.",
            )
        elif launch_mode == "npz":
            normalized_checks = (
                "Держите в голове один фиксированный сценарий и не ожидайте live-обновления pointer.",
                "Сначала выделите ведущую ветку, затем закрепите один узел давления как эталон.",
                "Численную проверку проводите через тренды только после того, как топология уже понятна.",
            )
        else:
            normalized_checks = (
                "Сначала откройте pointer или конкретный NPZ, чтобы схема получила реальный сценарий.",
                "После загрузки bundle ищите не всю картину сразу, а одну ведущую ветку и один опорный узел.",
                "Тренды и память событий используйте как подтверждение гипотезы, а не как первый экран чтения.",
            )

    context_key = str(preset_key or launch_mode).strip() or launch_mode
    return LaunchOnboardingContext(
        preset_key=context_key,
        title=str(title).strip() or "Стартовый сценарий",
        reason=str(reason).strip() or "",
        checklist=normalized_checks,
        launch_mode=launch_mode,
    )


def build_onboarding_focus_target(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None = None,
    selected_node: str | None = None,
) -> OnboardingFocusTarget:
    if dataset is None or dataset.time_s.size == 0:
        return OnboardingFocusTarget(
            edge_name="",
            node_name="",
            mode_title="Ожидание данных",
            summary="Bundle ещё не загружен, поэтому стартовый фокус пока не вычислен.",
            has_target=False,
        )

    narrative = _build_frame_narrative(dataset, idx, selected_edge=selected_edge, selected_node=selected_node)
    edge_name = narrative.top_edge_name if narrative.top_edge_name in dataset.edge_names else ""
    if not edge_name and selected_edge in dataset.edge_names:
        edge_name = str(selected_edge)
    node_name = narrative.top_node_name if narrative.top_node_name in dataset.node_names else ""
    if not node_name and selected_node in dataset.node_names:
        node_name = str(selected_node)

    has_target = bool(edge_name or node_name)
    focus_pair = f"{edge_name or '—'} / {node_name or '—'}"
    summary = (
        f"Стартовый фокус для этого кадра: {focus_pair}. "
        f"{narrative.primary_title}: {narrative.primary_summary}"
    )
    return OnboardingFocusTarget(
        edge_name=edge_name,
        node_name=node_name,
        mode_title=narrative.primary_title,
        summary=summary,
        has_target=has_target,
    )


def build_onboarding_focus_region_payload(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None = None,
    selected_node: str | None = None,
    source: str = "onboarding",
    auto_focus: bool = False,
) -> dict[str, Any]:
    focus_target = build_onboarding_focus_target(
        dataset,
        idx,
        selected_edge=selected_edge,
        selected_node=selected_node,
    )
    dataset_id = str(dataset.dataset_id) if dataset is not None else ""
    signature = f"{dataset_id}::{idx}::{focus_target.edge_name}::{focus_target.node_name}::{source}"
    return {
        "available": bool(focus_target.has_target),
        "edge_name": focus_target.edge_name,
        "node_name": focus_target.node_name,
        "title": "Onboarding focus",
        "mode_title": focus_target.mode_title,
        "summary": focus_target.summary,
        "source": str(source),
        "signature": signature,
        "auto_focus": bool(auto_focus),
        "animate": True,
        "duration_ms": 460,
        "padding": 170,
        "focus_fill_ratio": 0.42,
        "ttl_ms": 2600,
    }


def _severity_rank(severity: str) -> int:
    order = {
        "warn": 50,
        "attention": 40,
        "focus": 35,
        "info": 20,
        "ok": 10,
    }
    return order.get(str(severity or "").strip().lower(), 0)


def _merge_alert_marker(
    bucket: dict[str, dict[str, Any]],
    *,
    name: str,
    severity: str,
    label: str,
    summary: str,
    value: float | None,
    unit: str,
) -> None:
    marker_name = str(name or "").strip()
    if not marker_name or marker_name == "—":
        return

    candidate = {
        "name": marker_name,
        "severity": str(severity or "info"),
        "label": str(label or ""),
        "summary": str(summary or ""),
        "value": None if value is None else float(value),
        "unit": str(unit or ""),
    }
    prev = bucket.get(marker_name)
    if prev is None:
        bucket[marker_name] = candidate
        return

    prev_rank = _severity_rank(str(prev.get("severity") or ""))
    next_rank = _severity_rank(candidate["severity"])
    if next_rank > prev_rank:
        bucket[marker_name] = candidate
        return
    if next_rank == prev_rank:
        if not prev.get("label") and candidate["label"]:
            prev["label"] = candidate["label"]
        if not prev.get("summary") and candidate["summary"]:
            prev["summary"] = candidate["summary"]
        if prev.get("value") is None and candidate["value"] is not None:
            prev["value"] = candidate["value"]
        if not prev.get("unit") and candidate["unit"]:
            prev["unit"] = candidate["unit"]


class MnemoEventTracker:
    def __init__(self, *, max_events: int = 80):
        self.max_events = max(12, int(max_events))
        self.reset()

    def reset(self) -> None:
        self.dataset_id: str | None = None
        self.events: list[MnemoTimelineEvent] = []
        self._prev_time_s: float | None = None
        self._prev_primary_title: str | None = None
        self._prev_top_edge_name: str | None = None
        self._prev_watch_titles: set[str] = set()
        self._current_watch_titles: set[str] = set()
        self._acked_titles: set[str] = set()

    def bind_dataset(self, dataset: MnemoDataset | None, *, idx: int) -> None:
        self.reset()
        if dataset is None or dataset.time_s.size == 0:
            return

        self.dataset_id = dataset.dataset_id
        narrative = _build_frame_narrative(dataset, idx, selected_edge=None, selected_node=None)
        clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
        time_s = float(dataset.time_s[clamped_idx])

        self._append_event(
            frame_idx=clamped_idx,
            time_s=time_s,
            kind="session",
            severity="info",
            title="Новый прогон",
            summary=(
                f"{dataset.npz_path.name}: стартовая точка в режиме {narrative.primary_title}. "
                f"Ведущая ветка {narrative.top_edge_name}."
            ),
            edge_name=narrative.top_edge_name,
            node_name=narrative.top_node_name,
        )

        current_watch = {mode.title: mode for mode in narrative.modes if mode.severity in {"warn", "attention"}}
        for mode in current_watch.values():
            self._append_event(
                frame_idx=clamped_idx,
                time_s=time_s,
                kind="latched",
                severity=mode.severity,
                title=mode.title,
                summary=mode.summary,
                edge_name=narrative.top_edge_name,
                node_name=narrative.top_node_name,
            )

        self._prev_time_s = time_s
        self._prev_primary_title = narrative.primary_title
        self._prev_top_edge_name = narrative.top_edge_name
        self._prev_watch_titles = set(current_watch)
        self._current_watch_titles = set(current_watch)

    def observe_frame(self, dataset: MnemoDataset | None, *, idx: int) -> list[MnemoTimelineEvent]:
        if dataset is None or dataset.time_s.size == 0:
            return []
        if self.dataset_id != dataset.dataset_id:
            self.bind_dataset(dataset, idx=idx)
            return self.recent_events(limit=3)

        clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
        time_s = float(dataset.time_s[clamped_idx])
        narrative = _build_frame_narrative(dataset, clamped_idx, selected_edge=None, selected_node=None)
        current_watch = {mode.title: mode for mode in narrative.modes if mode.severity in {"warn", "attention"}}

        if self._prev_time_s is not None and time_s < self._prev_time_s - 1.0e-9:
            self._prev_time_s = time_s
            self._prev_primary_title = narrative.primary_title
            self._prev_top_edge_name = narrative.top_edge_name
            self._prev_watch_titles = set(current_watch)
            self._current_watch_titles = set(current_watch)
            return []

        new_events: list[MnemoTimelineEvent] = []

        if self._prev_primary_title is not None and narrative.primary_title != self._prev_primary_title:
            new_events.append(
                self._append_event(
                    frame_idx=clamped_idx,
                    time_s=time_s,
                    kind="mode",
                    severity="focus",
                    title="Смена режима",
                    summary=(
                        f"{self._prev_primary_title} → {narrative.primary_title}. "
                        f"Новая ведущая ветка: {narrative.top_edge_name}."
                    ),
                    edge_name=narrative.top_edge_name,
                    node_name=narrative.top_node_name,
                )
            )
        elif (
            self._prev_top_edge_name is not None
            and narrative.top_edge_name != "—"
            and narrative.top_edge_name != self._prev_top_edge_name
        ):
            new_events.append(
                self._append_event(
                    frame_idx=clamped_idx,
                    time_s=time_s,
                    kind="flow",
                    severity="info",
                    title="Смена ведущей ветки",
                    summary=(
                        f"Доминирование перешло с {self._prev_top_edge_name} на {narrative.top_edge_name}. "
                        f"Имеет смысл проверить, не сместился ли и опорный узел."
                    ),
                    edge_name=narrative.top_edge_name,
                    node_name=narrative.top_node_name,
                )
            )

        for title, mode in current_watch.items():
            if title in self._prev_watch_titles:
                continue
            self._acked_titles.discard(title)
            new_events.append(
                self._append_event(
                    frame_idx=clamped_idx,
                    time_s=time_s,
                    kind="latched",
                    severity=mode.severity,
                    title=mode.title,
                    summary=mode.summary,
                    edge_name=narrative.top_edge_name,
                    node_name=narrative.top_node_name,
                )
            )

        self._prev_time_s = time_s
        self._prev_primary_title = narrative.primary_title
        self._prev_top_edge_name = narrative.top_edge_name
        self._prev_watch_titles = set(current_watch)
        self._current_watch_titles = set(current_watch)
        return new_events

    def recent_events(self, *, limit: int = 8) -> list[MnemoTimelineEvent]:
        return list(reversed(self.events[-max(1, int(limit)) :]))

    def latched_events(self, *, limit: int = 6) -> list[MnemoTimelineEvent]:
        latest_by_title: dict[str, MnemoTimelineEvent] = {}
        for event in self.events:
            if event.severity not in {"warn", "attention"}:
                continue
            latest_by_title[event.title] = event
        ordered = sorted(latest_by_title.values(), key=lambda item: (item.time_s, item.frame_idx), reverse=True)
        return ordered[: max(1, int(limit))]

    def active_latched_events(self, *, limit: int = 6) -> list[MnemoTimelineEvent]:
        rows = [event for event in self.latched_events(limit=max(limit, self.max_events)) if event.title in self._current_watch_titles and event.title not in self._acked_titles]
        return rows[: max(1, int(limit))]

    def acknowledged_latched_events(self, *, limit: int = 6) -> list[MnemoTimelineEvent]:
        rows = [event for event in self.latched_events(limit=max(limit, self.max_events)) if event.title in self._current_watch_titles and event.title in self._acked_titles]
        return rows[: max(1, int(limit))]

    def acknowledge_active_latches(self, *, dataset: MnemoDataset | None, idx: int) -> list[MnemoTimelineEvent]:
        if dataset is None or dataset.time_s.size == 0:
            return []
        clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
        current = self.active_latched_events(limit=self.max_events)
        if not current:
            return []
        for event in current:
            self._acked_titles.add(event.title)
        time_s = float(dataset.time_s[clamped_idx])
        self._append_event(
            frame_idx=clamped_idx,
            time_s=time_s,
            kind="ack",
            severity="ok",
            title="ACK latched-событий",
            summary=f"Оператор подтвердил {len(current)} активных latched-событий.",
            edge_name=current[0].edge_name if current else "",
            node_name=current[0].node_name if current else "",
        )
        return current

    def reset_memory(self, dataset: MnemoDataset | None, *, idx: int) -> None:
        self.bind_dataset(dataset, idx=idx)

    def acknowledged_titles(self) -> list[str]:
        return sorted(self._acked_titles)

    def current_watch_titles(self) -> list[str]:
        return sorted(self._current_watch_titles)

    def _append_event(
        self,
        *,
        frame_idx: int,
        time_s: float,
        kind: str,
        severity: str,
        title: str,
        summary: str,
        edge_name: str,
        node_name: str,
    ) -> MnemoTimelineEvent:
        event = MnemoTimelineEvent(
            frame_idx=int(frame_idx),
            time_s=float(time_s),
            kind=str(kind),
            severity=str(severity),
            title=str(title),
            summary=str(summary),
            edge_name=str(edge_name or ""),
            node_name=str(node_name or ""),
        )
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]
        return event


def _friendly_error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _event_log_sidecar_path(npz_path: Path) -> Path:
    npz_abs = Path(npz_path).expanduser().resolve()
    return npz_abs.with_name(f"{npz_abs.stem}.desktop_mnemo_events.json")


def _event_to_dict(event: MnemoTimelineEvent, *, acked: bool) -> dict[str, Any]:
    return {
        "frame_idx": int(event.frame_idx),
        "time_s": float(event.time_s),
        "kind": str(event.kind),
        "severity": str(event.severity),
        "title": str(event.title),
        "summary": str(event.summary),
        "edge_name": str(event.edge_name),
        "node_name": str(event.node_name),
        "acked": bool(acked),
    }


def _build_event_log_payload(
    dataset: MnemoDataset | None,
    tracker: MnemoEventTracker,
    *,
    idx: int,
    selected_edge: str | None,
    selected_node: str | None,
    follow_enabled: bool,
    pointer_path: Path | None,
) -> dict[str, Any]:
    if dataset is None or dataset.time_s.size == 0:
        return {
            "schema_version": EVENT_LOG_SCHEMA_VERSION,
            "updated_utc": _utc_iso(),
            "source": "desktop_mnemo",
            "available": False,
            "events": [],
        }

    clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
    narrative = _build_frame_narrative(dataset, clamped_idx, selected_edge=selected_edge, selected_node=selected_node)
    payload = {
        "schema_version": EVENT_LOG_SCHEMA_VERSION,
        "updated_utc": _utc_iso(),
        "source": "desktop_mnemo",
        "available": True,
        "npz_path": str(dataset.npz_path),
        "npz_name": dataset.npz_path.name,
        "event_log_path": str(_event_log_sidecar_path(dataset.npz_path)),
        "pointer_json": str(pointer_path.resolve()) if pointer_path is not None else "",
        "follow_enabled": bool(follow_enabled),
        "dataset_id": str(dataset.dataset_id),
        "current_idx": clamped_idx,
        "current_time_s": float(dataset.time_s[clamped_idx]),
        "selected_edge": str(selected_edge or ""),
        "selected_node": str(selected_node or ""),
        "current_mode": narrative.primary_title,
        "active_watch_titles": tracker.current_watch_titles(),
        "acknowledged_titles": tracker.acknowledged_titles(),
        "active_latches": [
            _event_to_dict(event, acked=False)
            for event in tracker.active_latched_events(limit=tracker.max_events)
        ],
        "acknowledged_latches": [
            _event_to_dict(event, acked=True)
            for event in tracker.acknowledged_latched_events(limit=tracker.max_events)
        ],
        "recent_events": [
            _event_to_dict(event, acked=(event.title in set(tracker.acknowledged_titles())))
            for event in tracker.recent_events(limit=12)
        ],
        "events": [
            _event_to_dict(event, acked=(event.title in set(tracker.acknowledged_titles())))
            for event in tracker.events
        ],
    }
    payload["event_count"] = len(payload["events"])
    payload["active_latch_count"] = len(payload["active_latches"])
    payload["acknowledged_latch_count"] = len(payload["acknowledged_latches"])
    return payload


def _write_event_log_sidecar(
    dataset: MnemoDataset | None,
    tracker: MnemoEventTracker,
    *,
    idx: int,
    selected_edge: str | None,
    selected_node: str | None,
    follow_enabled: bool,
    pointer_path: Path | None,
) -> Path | None:
    if dataset is None or dataset.time_s.size == 0:
        return None
    out_path = _event_log_sidecar_path(dataset.npz_path)
    payload = _build_event_log_payload(
        dataset,
        tracker,
        idx=idx,
        selected_edge=selected_edge,
        selected_node=selected_node,
        follow_enabled=follow_enabled,
        pointer_path=pointer_path,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)
    return out_path


def _load_canonical_edges() -> tuple[list[str], dict[str, dict[str, Any]]]:
    obj = json.loads(SCHEME_JSON_PATH.read_text(encoding="utf-8"))
    nodes = [str(item.get("name")) for item in obj.get("canonical", {}).get("nodes", []) if item.get("name")]
    edge_defs: dict[str, dict[str, Any]] = {}
    for edge in obj.get("canonical", {}).get("edges", []):
        name = str(edge.get("name") or "").strip()
        if not name:
            continue
        edge_defs[name] = {
            "name": name,
            "n1": str(edge.get("n1") or ""),
            "n2": str(edge.get("n2") or ""),
            "kind": str(edge.get("kind") or ""),
        }
    return nodes, edge_defs


def _p_atm_from_meta(meta: dict[str, Any]) -> float:
    for key in ("P_ATM", "p_atm", "patm_pa", "patm"):
        try:
            value = meta.get(key)
            if value is None:
                continue
            value_f = float(value)
            if np.isfinite(value_f) and value_f > 1000.0:
                return float(value_f)
        except Exception:
            continue
    return 101325.0


def _flow_scale_and_unit(p_atm: float) -> tuple[float, str]:
    rho_n = max(float(p_atm) / (287.0 * 293.15), 1e-6)
    return 1000.0 * 60.0 / rho_n, "Нл/мин"


def _bar_g(pa_values: np.ndarray, p_atm: float) -> np.ndarray:
    return (np.asarray(pa_values, dtype=float) - float(p_atm)) / 1.0e5


def _remove_duplicate_points(points: list[tuple[float, float]]) -> list[list[float]]:
    cleaned: list[tuple[float, float]] = []
    for px, py in points:
        candidate = (round(float(px), 2), round(float(py), 2))
        if cleaned and cleaned[-1] == candidate:
            continue
        cleaned.append(candidate)
    return [[float(x), float(y)] for x, y in cleaned]


def _orth_route(p1: tuple[float, float], p2: tuple[float, float], *, mid_y: float | None = None, mid_x: float | None = None) -> list[list[float]]:
    if abs(p1[0] - p2[0]) < 1.0 or abs(p1[1] - p2[1]) < 1.0:
        return _remove_duplicate_points([p1, p2])
    if mid_y is not None:
        return _remove_duplicate_points([p1, (p1[0], mid_y), (p2[0], mid_y), p2])
    if mid_x is not None:
        return _remove_duplicate_points([p1, (mid_x, p1[1]), (mid_x, p2[1]), p2])
    mid = (p1[1] + p2[1]) * 0.5
    return _remove_duplicate_points([p1, (p1[0], mid), (p2[0], mid), p2])


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * float(t), a[1] + (b[1] - a[1]) * float(t))


def _offset_point_along_perp(a: tuple[float, float], b: tuple[float, float], t: float, offset: float) -> tuple[float, float]:
    x, y = _lerp(a, b, t)
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        return (x, y)
    px = -dy / norm
    py = dx / norm
    return (x + px * offset, y + py * offset)


def _chamber_short(chamber_name: str) -> str:
    return "БП" if chamber_name in {"БП", "CAP"} else "ШП"


def _node_kind(node_name: str) -> str:
    if node_name == "АТМ":
        return "atm"
    if node_name.startswith("Ресивер"):
        return "receiver"
    if node_name == "Аккумулятор":
        return "accumulator"
    if node_name.startswith("Магистраль_"):
        return "mainline"
    if CHAMBER_RE.match(node_name):
        return "chamber"
    if DIAGONAL_RE.match(node_name):
        return "diagonal"
    if node_name.startswith("узел_после_"):
        return "regulator"
    return "other"


def _edge_mid_rail(edge_def: dict[str, Any]) -> float | None:
    endpoints = {str(edge_def.get("n1") or ""), str(edge_def.get("n2") or "")}
    if "АТМ" in endpoints:
        return 650.0
    if "Ресивер1" in endpoints:
        return 720.0
    if "Ресивер2" in endpoints:
        return 900.0
    if "Ресивер3" in endpoints:
        return 320.0
    if "Аккумулятор" in endpoints:
        return 420.0
    if "Магистраль_ПП2_ЛЗ2" in endpoints or "Магистраль_ЛП2_ПЗ2" in endpoints:
        return 980.0
    return None


def _build_node_positions(node_names: list[str]) -> dict[str, tuple[float, float]]:
    positions = dict(SUPPLY_POSITIONS)
    chamber_positions: dict[str, tuple[float, float]] = {}

    for node_name in node_names:
        match = CHAMBER_RE.match(node_name)
        if not match:
            continue
        corner = str(match.group("corner"))
        cyl = str(match.group("cyl"))
        chamber = str(match.group("ch"))
        gx, gy = CORNER_ANCHORS[corner]
        x = gx + (-90.0 if cyl == "1" else 90.0)
        y = gy + (-46.0 if chamber == "БП" else 46.0)
        chamber_positions[node_name] = (x, y)
        positions[node_name] = (x, y)

    fallback_index = 0
    for node_name in node_names:
        if node_name in positions:
            continue
        match = DIAGONAL_RE.match(node_name)
        if match:
            src_corner = str(match.group("src_corner"))
            src_ch = "БП" if match.group("src_ch") == "CAP" else "ШП"
            dst_corner = str(match.group("dst_corner"))
            dst_ch = "БП" if match.group("dst_ch") == "CAP" else "ШП"
            src_name = f"Ц2_{src_corner}_{src_ch}"
            dst_name = f"Ц2_{dst_corner}_{dst_ch}"
            a = chamber_positions.get(src_name)
            b = chamber_positions.get(dst_name)
            if a is not None and b is not None:
                stage = str(match.group("stage"))
                offset = 24.0 if match.group("src_ch") == "CAP" else -24.0
                if src_corner in {"ПП", "ПЗ"}:
                    offset *= -1.0
                t = 0.35 if stage == "междуОКиДР" else 0.68
                positions[node_name] = _offset_point_along_perp(a, b, t, offset)
                continue

        positions[node_name] = (2080.0, 180.0 + fallback_index * 24.0)
        fallback_index += 1

    return positions


def _build_semantic_svg(node_positions: dict[str, tuple[float, float]]) -> str:
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEWBOX}" role="img" aria-label="Пневматическая мнемосхема">',
        "<defs>",
        '  <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#071117"/>',
        '    <stop offset="100%" stop-color="#0a1d26"/>',
        "  </linearGradient>",
        '  <linearGradient id="cardGrad" x1="0" y1="0" x2="1" y2="1">',
        '    <stop offset="0%" stop-color="#102630"/>',
        '    <stop offset="100%" stop-color="#123442"/>',
        "  </linearGradient>",
        '  <linearGradient id="cornerGrad" x1="0" y1="0" x2="1" y2="1">',
        '    <stop offset="0%" stop-color="#122b36"/>',
        '    <stop offset="100%" stop-color="#153947"/>',
        "  </linearGradient>",
        '  <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feGaussianBlur stdDeviation="8" result="blur"/>',
        '    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        "  </filter>",
        '  <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">',
        '    <path d="M 48 0 L 0 0 0 48" fill="none" stroke="rgba(255,255,255,0.045)" stroke-width="1"/>',
        "  </pattern>",
        "</defs>",
        '  <rect x="0" y="0" width="2200" height="1500" fill="url(#bgGrad)"/>',
        '  <rect x="0" y="0" width="2200" height="1500" fill="url(#grid)" opacity="0.55"/>',
        '  <rect x="60" y="70" width="2080" height="220" rx="32" fill="rgba(13,33,42,0.74)" stroke="rgba(99,211,245,0.20)" stroke-width="2"/>',
        '  <rect x="60" y="320" width="2080" height="290" rx="32" fill="rgba(12,29,37,0.62)" stroke="rgba(248,193,92,0.18)" stroke-width="2"/>',
        '  <rect x="60" y="650" width="2080" height="760" rx="36" fill="rgba(10,24,31,0.55)" stroke="rgba(129,231,163,0.18)" stroke-width="2"/>',
        '  <text x="100" y="128" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="28" font-weight="700" fill="#edf5f8" pointer-events="none">Пневматическая мнемосхема</text>',
        '  <text x="100" y="162" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="15" fill="#8fa9b5" pointer-events="none">Отдельное desktop-окно: обзор системы, топология и быстрые инженерные решения.</text>',
        '  <text x="100" y="370" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#f2d08f" pointer-events="none">Питание и регуляторы</text>',
        '  <text x="100" y="702" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#8be2f8" pointer-events="none">Исполнительные контуры и диагональные связи</text>',
        '  <text x="420" y="728" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="15" fill="#86a6b3" pointer-events="none">Передняя ось</text>',
        '  <text x="420" y="1118" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="15" fill="#86a6b3" pointer-events="none">Задняя ось</text>',
        '  <path d="M 180 650 L 2020 650" stroke="rgba(243,172,91,0.22)" stroke-width="6" stroke-linecap="round"/>',
        '  <path d="M 760 720 L 1960 720" stroke="rgba(99,211,245,0.20)" stroke-width="6" stroke-linecap="round"/>',
        '  <path d="M 1100 900 L 1960 900" stroke="rgba(129,231,163,0.20)" stroke-width="6" stroke-linecap="round"/>',
        '  <path d="M 980 980 L 1220 980" stroke="rgba(248,193,92,0.26)" stroke-width="9" stroke-linecap="round" filter="url(#softGlow)"/>',
    ]

    for node_name, (title, subtitle) in SUPPLY_LABELS.items():
        x, y = node_positions.get(node_name, SUPPLY_POSITIONS.get(node_name, (100.0, 100.0)))
        width = 184.0 if node_name.startswith("Ресивер") or node_name == "Аккумулятор" else 170.0
        height = 84.0 if node_name.startswith("Ресивер") or node_name == "Аккумулятор" else 68.0
        parts.extend(
            [
                f'  <rect x="{x - width / 2:.1f}" y="{y - height / 2:.1f}" width="{width:.1f}" height="{height:.1f}" rx="24" fill="url(#cardGrad)" stroke="rgba(99,211,245,0.28)" stroke-width="2"/>',
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#63d3f5" fill-opacity="0.72"/>',
                f'  <text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#eef6f8" pointer-events="none">{escape(title)}</text>',
                f'  <text x="{x:.1f}" y="{y + 18:.1f}" text-anchor="middle" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="12" fill="#8fa9b5" pointer-events="none">{escape(subtitle)}</text>',
            ]
        )

    for corner, (gx, gy) in CORNER_ANCHORS.items():
        parts.extend(
            [
                f'  <rect x="{gx - 150:.1f}" y="{gy - 100:.1f}" width="300" height="200" rx="26" fill="url(#cornerGrad)" stroke="rgba(129,231,163,0.24)" stroke-width="2"/>',
                f'  <text x="{gx - 118:.1f}" y="{gy - 66:.1f}" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="24" font-weight="700" fill="#eef6f8" pointer-events="none">{corner}</text>',
                f'  <text x="{gx - 118:.1f}" y="{gy - 40:.1f}" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="12" fill="#8fa9b5" pointer-events="none">двойной цилиндровый узел</text>',
                f'  <line x1="{gx:.1f}" y1="{gy - 74:.1f}" x2="{gx:.1f}" y2="{gy + 74:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="2"/>',
                f'  <text x="{gx - 88:.1f}" y="{gy - 12:.1f}" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="13" fill="#8fa9b5" pointer-events="none">Ц1</text>',
                f'  <text x="{gx + 56:.1f}" y="{gy - 12:.1f}" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="13" fill="#8fa9b5" pointer-events="none">Ц2</text>',
            ]
        )
        for cyl in ("1", "2"):
            for chamber in ("БП", "ШП"):
                node_name = f"Ц{cyl}_{corner}_{chamber}"
                px, py = node_positions[node_name]
                parts.extend(
                    [
                        f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="rgba(99,211,245,0.16)" stroke="rgba(99,211,245,0.32)" stroke-width="2"/>',
                        f'  <text x="{px + 16:.1f}" y="{py + 4:.1f}" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="13" fill="#cfe0e8" pointer-events="none">C{cyl} {_chamber_short(chamber)}</text>',
                    ]
                )

    for node_name in KEY_NODE_HINTS:
        if node_name not in node_positions:
            continue
        x, y = node_positions[node_name]
        title, _subtitle = SUPPLY_LABELS.get(node_name, (node_name, ""))
        parts.extend(
            [
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#f8c15c" fill-opacity="0.9"/>',
                f'  <text x="{x:.1f}" y="{y - 16:.1f}" text-anchor="middle" font-family="Bahnschrift, Segoe UI, sans-serif" font-size="11" fill="#cfdde4" pointer-events="none">{escape(title)}</text>',
            ]
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _build_mapping(
    edge_names: list[str],
    node_names: list[str],
    edge_defs: dict[str, dict[str, Any]],
    node_positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    mapping: dict[str, Any] = {"version": 2, "viewBox": VIEWBOX, "edges": {}, "nodes": {}, "edges_meta": {}}

    for node_name in node_names:
        pos = node_positions.get(node_name)
        if pos is not None:
            mapping["nodes"][node_name] = [float(pos[0]), float(pos[1])]

    fallback_index = 0
    for edge_name in edge_names:
        edge_def = edge_defs.get(edge_name)
        if edge_def is None:
            y = 190.0 + fallback_index * 18.0
            mapping["edges"][edge_name] = [[[2040.0, y], [2140.0, y]]]
            mapping["edges_meta"][edge_name] = {"kind": "unknown", "mnemo_route": "fallback_lane"}
            fallback_index += 1
            continue

        n1 = str(edge_def.get("n1") or "")
        n2 = str(edge_def.get("n2") or "")
        p1 = node_positions.get(n1)
        p2 = node_positions.get(n2)
        if p1 is None or p2 is None:
            y = 190.0 + fallback_index * 18.0
            mapping["edges"][edge_name] = [[[2040.0, y], [2140.0, y]]]
            mapping["edges_meta"][edge_name] = {"kind": str(edge_def.get("kind") or ""), "mnemo_route": "missing_endpoint"}
            fallback_index += 1
            continue

        mid_rail = _edge_mid_rail(edge_def)
        kind_1 = _node_kind(n1)
        kind_2 = _node_kind(n2)
        if kind_1 in {"diagonal", "chamber"} and kind_2 in {"diagonal", "chamber"}:
            poly = _remove_duplicate_points([p1, p2])
            route_name = "direct_chamber"
        elif mid_rail is not None:
            poly = _orth_route(p1, p2, mid_y=float(mid_rail))
            route_name = "rail"
        elif kind_1 == "regulator" and kind_2 == "regulator":
            poly = _orth_route(p1, p2, mid_x=(p1[0] + p2[0]) * 0.5)
            route_name = "regulator_bus"
        else:
            poly = _orth_route(p1, p2)
            route_name = "orthogonal"

        mapping["edges"][edge_name] = [poly]
        mapping["edges_meta"][edge_name] = {
            "kind": str(edge_def.get("kind") or ""),
            "mnemo_route": route_name,
            "endpoints": [n1, n2],
        }

    return mapping


def _pick_overlay_nodes(all_nodes: list[str]) -> list[str]:
    preferred = default_svg_pressure_nodes(all_nodes, limit=10)
    seen: set[str] = set()
    picked: list[str] = []
    for node_name in [*preferred, *KEY_NODE_HINTS]:
        if node_name in all_nodes and node_name not in seen:
            seen.add(node_name)
            picked.append(node_name)
    return picked[:12]


def _build_edge_series(bundle: DataBundle, edge_names: list[str], q_scale: float, q_unit: str) -> list[dict[str, Any]]:
    if bundle.q is None:
        return []
    edge_series: list[dict[str, Any]] = []
    for edge_name in edge_names:
        q_arr = bundle.q.column(edge_name, default=None)
        if q_arr is None:
            continue
        open_arr = bundle.open.column(edge_name, default=None) if bundle.open is not None else None
        edge_series.append(
            {
                "name": edge_name,
                "q": (np.asarray(q_arr, dtype=float) * float(q_scale)).tolist(),
                "open": np.asarray(open_arr, dtype=int).tolist() if open_arr is not None else None,
                "unit": q_unit,
            }
        )
    return edge_series


def _build_node_series(bundle: DataBundle, node_names: list[str], p_atm: float) -> list[dict[str, Any]]:
    if bundle.p is None:
        return []
    out: list[dict[str, Any]] = []
    for node_name in node_names:
        p_arr = bundle.p.column(node_name, default=None)
        if p_arr is None:
            continue
        out.append({"name": node_name, "p": _bar_g(np.asarray(p_arr, dtype=float), p_atm).tolist(), "unit": "бар(g)"})
    return out


def _edge_rows_for_index(dataset: MnemoDataset, idx: int) -> list[tuple[str, float]]:
    q_table = dataset.bundle.q
    if q_table is None or not dataset.edge_names:
        return []
    clamped = max(0, min(int(idx), max(0, dataset.time_s.size - 1)))
    rows: list[tuple[str, float]] = []
    for edge_name in dataset.edge_names:
        arr = q_table.column(edge_name, default=None)
        if arr is None:
            continue
        q_now = float(np.asarray(arr, dtype=float)[clamped] * dataset.q_scale)
        rows.append((edge_name, q_now))
    rows.sort(key=lambda item: abs(item[1]), reverse=True)
    return rows


def _node_rows_for_index(dataset: MnemoDataset, idx: int, *, overlay_only: bool = False) -> list[tuple[str, float]]:
    p_table = dataset.bundle.p
    if p_table is None:
        return []
    names = dataset.overlay_node_names if overlay_only and dataset.overlay_node_names else dataset.node_names
    if not names:
        return []
    clamped = max(0, min(int(idx), max(0, dataset.time_s.size - 1)))
    rows: list[tuple[str, float]] = []
    for node_name in names:
        arr = p_table.column(node_name, default=None)
        if arr is None:
            continue
        p_now = float(_bar_g(np.asarray(arr, dtype=float), dataset.p_atm)[clamped])
        rows.append((node_name, p_now))
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows


def _edge_role(edge_name: str, edge_def: dict[str, Any]) -> str:
    _ = edge_name
    n1 = str(edge_def.get("n1") or "")
    n2 = str(edge_def.get("n2") or "")
    endpoints = [n1, n2]
    kinds = {_node_kind(node_name) for node_name in endpoints if node_name}

    if "АТМ" in endpoints:
        return "vent"
    if any(node_name.startswith("Магистраль_") for node_name in endpoints) or "diagonal" in kinds:
        return "diagonal"
    if "chamber" in kinds:
        return "actuator"
    if "regulator" in kinds:
        return "regulator"
    if "receiver" in kinds or "accumulator" in kinds:
        return "supply"
    return "other"


def _build_frame_narrative(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
    selected_node: str | None,
) -> FrameNarrative:
    if dataset is None or dataset.time_s.size == 0:
        return FrameNarrative(
            primary_title="Ожидание данных",
            primary_summary="Откройте NPZ или включите follow-режим, чтобы мнемосхема начала показывать инженерные сценарии.",
            top_edge_name="—",
            top_edge_value=0.0,
            top_node_name="—",
            top_node_value=0.0,
            pressure_spread=0.0,
            modes=[
                DiagnosticMode(
                    title="Стартовый протокол",
                    severity="info",
                    summary="Сначала найдите доминирующую ветку, затем подтвердите узел давления и только после этого открывайте тренды.",
                    action="Когда появится bundle, панель сама подскажет ведущий режим и точку следующей проверки.",
                )
            ],
        )

    edge_rows = _edge_rows_for_index(dataset, idx)
    node_rows = _node_rows_for_index(dataset, idx, overlay_only=True) or _node_rows_for_index(dataset, idx)

    top_edge_name, top_edge_value = edge_rows[0] if edge_rows else ("—", 0.0)
    top_node_name, top_node_value = node_rows[0] if node_rows else ("—", 0.0)
    min_pressure = node_rows[-1][1] if node_rows else top_node_value
    pressure_spread = float(top_node_value - min_pressure)

    focus_edge = selected_edge if selected_edge in dataset.edge_names else top_edge_name
    focus_node = selected_node if selected_node in dataset.node_names else top_node_name
    edge_def = dataset.edge_defs.get(focus_edge, {})
    role = _edge_role(focus_edge, edge_def)
    flow_dir = "по направлению ветки" if top_edge_value >= 0.0 else "в обратную сторону"
    abs_top_flow = abs(float(top_edge_value))

    if role == "vent":
        primary_title = "Сброс / разгрузка"
        primary_summary = (
            f"Доминирует ветка {focus_edge}: поток идёт {flow_dir}, а один из концов маршрута связан с атмосферой. "
            "Это характерно для продувки, аварийного разгружения или работы через выхлопной дроссель."
        )
    elif role == "diagonal":
        primary_title = "Диагональное перераспределение"
        primary_summary = (
            f"Сейчас активна диагональная линия {focus_edge}. Сценарий похож на выравнивание или перегон давления между удалёнными контурами."
        )
    elif role == "actuator":
        primary_title = "Исполнительный контур"
        primary_summary = (
            f"Наибольшая активность пришлась на {focus_edge}. Вероятнее всего, сейчас работает цилиндровый контур, "
            "а мнемосхема показывает подпитку или выпуск конкретной полости."
        )
    elif role == "regulator":
        primary_title = "Регуляторный коридор"
        primary_summary = (
            f"Пик активности проходит через {focus_edge}. Это похоже на формирование рабочего давления в зоне регуляторов и обратных клапанов."
        )
    elif role == "supply":
        primary_title = "Набор / подпитка запаса"
        primary_summary = (
            f"Доминирует линия {focus_edge}. Сценарий больше всего напоминает подпитку ресиверов или аккумулятора перед дальнейшим перераспределением."
        )
    else:
        primary_title = "Смешанный переходный режим"
        primary_summary = (
            f"Ведущая ветка {focus_edge} не относится к типовой группе. Имеет смысл смотреть на связанный узел давления и тренд по времени."
        )

    modes: list[DiagnosticMode] = [
        DiagnosticMode(
            title=primary_title,
            severity="focus",
            summary=primary_summary,
            action=(
                f"Подтвердите сценарий: выделите {focus_edge} на схеме и сравните её Q с узлом {focus_node} в нижних трендах."
                if focus_edge != "—" and focus_node != "—"
                else "Подтвердите доминирующую ветку по схеме и затем сравните соседние давления."
            ),
        )
    ]

    if pressure_spread >= 2.0:
        modes.append(
            DiagnosticMode(
                title="Большой перепад давлений",
                severity="warn",
                summary=(
                    f"Среди ключевых узлов разброс составляет {pressure_spread:4.2f} бар(g). Это много для спокойного режима "
                    "и обычно означает активное перераспределение, подпитку или сброс."
                ),
                action=f"Сначала сравните {top_node_name} и самый слабый ключевой узел, затем проверьте ветви между ними.",
            )
        )
    elif pressure_spread <= 0.45 and node_rows:
        modes.append(
            DiagnosticMode(
                title="Контур близок к выравниванию",
                severity="ok",
                summary=(
                    f"Разброс между ключевыми узлами сейчас около {pressure_spread:4.2f} бар(g). "
                    "Это похоже на устойчивое или почти выровненное состояние."
                ),
                action="Проверьте, не остались ли локальные импульсы только в одной ветви или на одном клапане.",
            )
        )

    vent_candidates = []
    for edge_name, q_now in edge_rows[:6]:
        edge_role = _edge_role(edge_name, dataset.edge_defs.get(edge_name, {}))
        if edge_role == "vent" and abs(float(q_now)) >= max(15.0, abs_top_flow * 0.35):
            vent_candidates.append((edge_name, float(q_now)))
    if vent_candidates and role != "vent":
        vent_name, vent_flow = vent_candidates[0]
        modes.append(
            DiagnosticMode(
                title="Сброс присутствует параллельно",
                severity="attention",
                summary=(
                    f"Помимо основного сценария заметен атмосферный канал {vent_name} "
                    f"с расходом {vent_flow:6.1f} {dataset.q_unit}. Это может быть нормальным выпуском или признаком лишней утечки энергии."
                ),
                action="Сравните этот канал с соседним регулятором или обратным клапаном: открытие должно быть объяснимо режимом.",
            )
        )

    if focus_node and focus_node != "—" and dataset.bundle.p is not None:
        p_arr = dataset.bundle.p.column(focus_node, default=None)
        if p_arr is not None:
            p_vals = _bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)
            p_now = float(p_vals[max(0, min(int(idx), p_vals.size - 1))])
            p_min = float(np.min(p_vals)) if p_vals.size else p_now
            p_max = float(np.max(p_vals)) if p_vals.size else p_now
            modes.append(
                DiagnosticMode(
                    title="Фокус узла",
                    severity="info",
                    summary=(
                        f"Узел {focus_node} сейчас на уровне {p_now:4.2f} бар(g); его рабочий диапазон в загруженном bundle "
                        f"составляет {p_min:4.2f} ... {p_max:4.2f} бар(g)."
                    ),
                    action="Если это опорный узел режима, закрепите его в голове как эталон и сравнивайте остальные ветви относительно него.",
                )
            )

    modes.append(
        DiagnosticMode(
            title="Короткий инженерный протокол",
            severity="info",
            summary="Не пытайтесь читать всю схему сразу. Лучше держать один главный вопрос на кадр.",
            action=(
                "1. Найдите ведущую ветку. 2. Подтвердите один ключевой узел давления. "
                "3. Проверьте, что открытие/сброс согласованы с трендами."
            ),
        )
    )

    return FrameNarrative(
        primary_title=primary_title,
        primary_summary=primary_summary,
        top_edge_name=top_edge_name,
        top_edge_value=top_edge_value,
        top_node_name=top_node_name,
        top_node_value=top_node_value,
        pressure_spread=pressure_spread,
        modes=modes[:5],
    )


def _build_frame_alert_payload(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
    selected_node: str | None,
) -> dict[str, Any]:
    narrative = _build_frame_narrative(dataset, idx, selected_edge=selected_edge, selected_node=selected_node)
    primary_mode = narrative.modes[0] if narrative.modes else DiagnosticMode(
        title=narrative.primary_title,
        severity="info",
        summary=narrative.primary_summary,
        action="",
    )
    if dataset is None or dataset.time_s.size == 0:
        return {
            "primary": {
                "title": narrative.primary_title,
                "summary": narrative.primary_summary,
                "action": primary_mode.action,
                "severity": primary_mode.severity,
            },
            "edges": [],
            "nodes": [],
            "mode_badges": [{"title": mode.title, "severity": mode.severity} for mode in narrative.modes[:3]],
        }

    edge_rows = _edge_rows_for_index(dataset, idx)
    node_rows = _node_rows_for_index(dataset, idx, overlay_only=True) or _node_rows_for_index(dataset, idx)

    focus_edge = selected_edge if selected_edge in dataset.edge_names else narrative.top_edge_name
    focus_node = selected_node if selected_node in dataset.node_names else narrative.top_node_name

    edge_markers: dict[str, dict[str, Any]] = {}
    node_markers: dict[str, dict[str, Any]] = {}

    _merge_alert_marker(
        edge_markers,
        name=narrative.top_edge_name,
        severity="focus",
        label="Ведущая ветка",
        summary="Максимальный |Q| на текущем кадре.",
        value=narrative.top_edge_value,
        unit=dataset.q_unit,
    )
    if focus_edge and focus_edge != narrative.top_edge_name:
        edge_role = _edge_role(focus_edge, dataset.edge_defs.get(focus_edge, {}))
        role_label = "Выбранная ветка"
        if edge_role == "vent":
            role_label = "Фокус: сброс"
        elif edge_role == "regulator":
            role_label = "Фокус: регулятор"
        _merge_alert_marker(
            edge_markers,
            name=focus_edge,
            severity="info",
            label=role_label,
            summary="Пользователь держит эту ветку в инженерном фокусе.",
            value=None,
            unit=dataset.q_unit,
        )

    if edge_rows:
        abs_top_flow = abs(float(edge_rows[0][1]))
        for edge_name, q_now in edge_rows[:6]:
            edge_role = _edge_role(edge_name, dataset.edge_defs.get(edge_name, {}))
            if edge_role == "vent" and abs(float(q_now)) >= max(15.0, abs_top_flow * 0.35):
                _merge_alert_marker(
                    edge_markers,
                    name=edge_name,
                    severity="attention",
                    label="Параллельный сброс",
                    summary="Атмосферная ветка заметно участвует в текущем режиме.",
                    value=q_now,
                    unit=dataset.q_unit,
                )
                break

    if node_rows:
        top_node_name, top_node_value = node_rows[0]
        _merge_alert_marker(
            node_markers,
            name=top_node_name,
            severity="focus" if narrative.pressure_spread < 2.0 else "warn",
            label="Максимум давления",
            summary="Верхний опорный узел на текущем кадре.",
            value=top_node_value,
            unit="бар(g)",
        )
        low_node_name, low_node_value = node_rows[-1]
        if low_node_name != top_node_name:
            low_severity = "warn" if narrative.pressure_spread >= 2.0 else "info"
            low_label = "Минимум давления" if narrative.pressure_spread >= 2.0 else "Слабый узел"
            _merge_alert_marker(
                node_markers,
                name=low_node_name,
                severity=low_severity,
                label=low_label,
                summary="Нижняя опорная точка, с которой стоит сравнивать перепад.",
                value=low_node_value,
                unit="бар(g)",
            )

    if focus_node and focus_node != narrative.top_node_name:
        _merge_alert_marker(
            node_markers,
            name=focus_node,
            severity="info",
            label="Фокус пользователя",
            summary="Этот узел выбран для сопоставления со сценарием кадра.",
            value=None,
            unit="бар(g)",
        )

    edge_items = sorted(edge_markers.values(), key=lambda item: (-_severity_rank(str(item.get("severity") or "")), item["name"]))[:3]
    node_items = sorted(node_markers.values(), key=lambda item: (-_severity_rank(str(item.get("severity") or "")), item["name"]))[:3]

    return {
        "primary": {
            "title": narrative.primary_title,
            "summary": narrative.primary_summary,
            "action": primary_mode.action,
            "severity": primary_mode.severity,
        },
        "edges": edge_items,
        "nodes": node_items,
        "mode_badges": [{"title": mode.title, "severity": mode.severity} for mode in narrative.modes[:3]],
    }


def prepare_dataset(npz_path: Path) -> MnemoDataset:
    bundle = load_npz(npz_path)
    if bundle.q is None:
        raise ValueError("NPZ bundle has no q_values table for pneumatic mnemonic.")

    all_scheme_nodes, edge_defs = _load_canonical_edges()
    edge_names = [name for name in bundle.q.cols if name != "время_с"]
    node_names = [name for name in (bundle.p.cols if bundle.p is not None else []) if name != "время_с"]
    full_node_inventory = list(dict.fromkeys([*all_scheme_nodes, *node_names]))
    node_positions = _build_node_positions(full_node_inventory)
    svg_inline = _build_semantic_svg(node_positions)
    mapping = _build_mapping(edge_names, full_node_inventory, edge_defs, node_positions)

    p_atm = _p_atm_from_meta(bundle.meta if isinstance(bundle.meta, dict) else {})
    q_scale, q_unit = _flow_scale_and_unit(p_atm)
    overlay_node_names = _pick_overlay_nodes(node_names)
    edge_series = _build_edge_series(bundle, edge_names, q_scale, q_unit)
    node_series = _build_node_series(bundle, overlay_node_names, p_atm)
    time_s = np.asarray(bundle.t, dtype=float)
    dataset_id = f"{npz_path.resolve()}::{npz_path.stat().st_mtime_ns}"

    return MnemoDataset(
        npz_path=npz_path.resolve(),
        bundle=bundle,
        dataset_id=dataset_id,
        svg_inline=svg_inline,
        mapping=mapping,
        edge_names=edge_names,
        node_names=node_names,
        overlay_node_names=overlay_node_names,
        edge_series=edge_series,
        node_series=node_series,
        edge_defs=edge_defs,
        time_s=time_s,
        q_scale=q_scale,
        q_unit=q_unit,
        p_atm=p_atm,
    )


class PointerWatcher(QtCore.QObject):
    npz_changed = QtCore.Signal(object)
    status = QtCore.Signal(str)

    def __init__(self, pointer_path: Path, *, poll_ms: int = 700):
        super().__init__()
        self.pointer_path = Path(pointer_path)
        self._last_pointer_sig: tuple[bool, int, int] | None = None
        self._last_npz_sig: tuple[bool, int, int] | None = None
        self._current_npz: Path | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(int(poll_ms))
        self._timer.timeout.connect(self._poll)

    @staticmethod
    def _file_sig(path: Path) -> tuple[bool, int, int]:
        try:
            if not path.exists():
                return (False, 0, 0)
            st = path.stat()
            return (True, int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return (False, 0, 0)

    def _resolve_pointer_npz(self) -> Optional[Path]:
        try:
            if not self.pointer_path.exists():
                return None
            obj = json.loads(self.pointer_path.read_text(encoding="utf-8", errors="ignore"))
            if not isinstance(obj, dict):
                return None
            raw = obj.get("npz_path") or obj.get("path") or obj.get("file")
            if not isinstance(raw, str) or not raw.strip():
                return None
            npz_path = Path(raw.strip())
            if not npz_path.is_absolute():
                npz_path = (self.pointer_path.parent / npz_path).resolve()
            return npz_path
        except Exception:
            return None

    def start(self) -> None:
        self.status.emit(f"Follow: {self.pointer_path}")
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        try:
            pointer_sig = self._file_sig(self.pointer_path)
            pointer_changed = pointer_sig != self._last_pointer_sig
            if pointer_changed:
                self._last_pointer_sig = pointer_sig
                resolved = self._resolve_pointer_npz()
                if resolved is not None:
                    self._current_npz = resolved
                    self.status.emit(f"Pointer -> {resolved.name}")

            if self._current_npz is None:
                self._current_npz = self._resolve_pointer_npz()
            if self._current_npz is None:
                return

            npz_sig = self._file_sig(self._current_npz)
            if npz_sig[0] and npz_sig != self._last_npz_sig:
                self._last_npz_sig = npz_sig
                self.status.emit(f"Reload: {self._current_npz.name}")
                self.npz_changed.emit(self._current_npz)
        except Exception as exc:
            self.status.emit(f"Follow error: {exc}")


class BridgeObject(QtCore.QObject):
    message_received = QtCore.Signal(str)

    @QtCore.Slot(str)
    def postMessage(self, payload: str) -> None:
        self.message_received.emit(str(payload))


class MnemoWebView(QtWidgets.QWidget):
    edge_picked = QtCore.Signal(str)
    node_picked = QtCore.Signal(str)
    status = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._loaded = False
        self._bridge: BridgeObject | None = None
        self._pending_js: list[str] = []

        if not _HAS_WEBENGINE:
            fallback = QtWidgets.QTextBrowser()
            fallback.setHtml(
                "<h3>Qt WebEngine не найден</h3>"
                "<p>Для анимированной мнемосхемы нужен модуль <code>PySide6.QtWebEngineWidgets</code>.</p>"
            )
            lay.addWidget(fallback)
            self.view = None
            return

        assert QtWebEngineWidgets is not None
        assert QtWebChannel is not None
        self.view = QtWebEngineWidgets.QWebEngineView(self)
        lay.addWidget(self.view)

        self._bridge = BridgeObject()
        self._bridge.message_received.connect(self._on_bridge_message)
        channel = QtWebChannel.QWebChannel(self.view.page())
        channel.registerObject("codexBridge", self._bridge)
        self.view.page().setWebChannel(channel)
        self.view.loadFinished.connect(self._on_load_finished)
        self._load_component_html()

    def _load_component_html(self) -> None:
        if self.view is None:
            return
        html_text = COMPONENT_HTML_PATH.read_text(encoding="utf-8")
        if "qrc:///qtwebchannel/qwebchannel.js" not in html_text:
            html_text = html_text.replace("</head>", '  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>\n</head>', 1)
        self.view.setHtml(html_text, QtCore.QUrl.fromLocalFile(str(COMPONENT_HTML_PATH.resolve())))

    def _on_load_finished(self, ok: bool) -> None:
        if not ok or self.view is None:
            self.status.emit("Не удалось загрузить HTML-компонент мнемосхемы.")
            return
        self._loaded = True
        self.view.page().runJavaScript(BOOTSTRAP_JS)
        QtCore.QTimer.singleShot(0, self._flush_pending)

    def _queue_or_run(self, js_code: str) -> None:
        if self.view is None:
            return
        if not self._loaded:
            self._pending_js.append(js_code)
            return
        self.view.page().runJavaScript(js_code)

    def _flush_pending(self) -> None:
        if self.view is None or not self._loaded:
            return
        pending = list(self._pending_js)
        self._pending_js.clear()
        for js_code in pending:
            self.view.page().runJavaScript(js_code)

    def render_dataset(self, dataset: MnemoDataset, *, selected_edge: str | None, selected_node: str | None) -> None:
        args = {
            "title": "Пневмосхема: desktop mnemonic",
            "svg": dataset.svg_inline,
            "mapping": dataset.mapping,
            "time": dataset.time_s.astype(float).tolist(),
            "edges": dataset.edge_series,
            "nodes": dataset.node_series,
            "selected": {"edge": selected_edge, "node": selected_node},
            "sync_playhead": True,
            "playhead_storage_key": PLAYHEAD_STORAGE_KEY,
            "dataset_id": dataset.dataset_id,
            "height": 1260,
            "show_review_overlay": False,
            "show_alert_overlay": True,
            "alerts": _build_frame_alert_payload(
                dataset,
                0,
                selected_edge=selected_edge,
                selected_node=selected_node,
            ),
        }
        payload = json.dumps(args, ensure_ascii=False)
        self._queue_or_run(f"window.codexMnemoDispatch({payload});")

    def set_playhead(self, idx: int, playing: bool, dataset_id: str) -> None:
        state = json.dumps(
            {"idx": int(idx), "playing": bool(playing), "dataset_id": str(dataset_id), "key": PLAYHEAD_STORAGE_KEY},
            ensure_ascii=False,
        )
        self._queue_or_run(f"window.codexMnemoSetPlayhead({state});")

    def set_selection(self, *, edge: str | None, node: str | None) -> None:
        payload = json.dumps({"edge": edge, "node": node}, ensure_ascii=False)
        self._queue_or_run(f"window.codexMnemoSetSelection({payload});")

    def set_alerts(self, alerts: dict[str, Any]) -> None:
        payload = json.dumps(alerts, ensure_ascii=False)
        self._queue_or_run(f"window.codexMnemoSetAlerts({payload});")

    def set_focus_region(self, focus_region: dict[str, Any] | None) -> None:
        payload = json.dumps(focus_region, ensure_ascii=False)
        self._queue_or_run(f"window.codexMnemoSetFocusRegion({payload});")

    def show_overview(self, meta: dict[str, Any] | None = None) -> None:
        payload = json.dumps(meta or {}, ensure_ascii=False)
        self._queue_or_run(f"window.codexMnemoShowOverview({payload});")

    def _on_bridge_message(self, payload: str) -> None:
        try:
            obj = json.loads(payload)
        except Exception:
            return
        if not isinstance(obj, dict):
            return
        if obj.get("type") == "streamlit:setFrameHeight":
            return
        kind = str(obj.get("kind") or "")
        name = str(obj.get("name") or "")
        if kind == "edge" and name:
            self.edge_picked.emit(name)
        elif kind == "node" and name:
            self.node_picked.emit(name)


class OverviewPanel(QtWidgets.QWidget):
    edge_activated = QtCore.Signal(str)
    node_activated = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        lay.addLayout(grid)

        self.kpi_time = self._make_kpi("Текущий момент")
        self.kpi_flow = self._make_kpi("Самый активный поток")
        self.kpi_pressure = self._make_kpi("Макс. давление")
        self.kpi_state = self._make_kpi("Режим")

        for idx, widget in enumerate((self.kpi_time, self.kpi_flow, self.kpi_pressure, self.kpi_state)):
            grid.addWidget(widget, idx // 2, idx % 2)

        self.dataset_meta = QtWidgets.QTextBrowser()
        self.dataset_meta.setMaximumHeight(176)
        lay.addWidget(self.dataset_meta)

        lay.addWidget(self._section_label("Топ веток"))
        self.edge_table = QtWidgets.QTableWidget(0, 2)
        self.edge_table.setHorizontalHeaderLabels(["Ветка", "Q"])
        self.edge_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.edge_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.edge_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.edge_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.edge_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.edge_table.cellClicked.connect(self._edge_clicked)
        lay.addWidget(self.edge_table, 1)

        lay.addWidget(self._section_label("Топ узлов"))
        self.node_table = QtWidgets.QTableWidget(0, 2)
        self.node_table.setHorizontalHeaderLabels(["Узел", "P"])
        self.node_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.node_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.node_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.node_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.node_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.node_table.cellClicked.connect(self._node_clicked)
        lay.addWidget(self.node_table, 1)

    @staticmethod
    def _section_label(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-weight:700; color:#eef6f8; padding-top:4px;")
        return label

    @staticmethod
    def _make_kpi(caption: str) -> QtWidgets.QWidget:
        box = QtWidgets.QFrame()
        box.setStyleSheet("QFrame { background:#102630; border:1px solid #173845; border-radius:14px; }")
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 10)
        value = QtWidgets.QLabel("—")
        value.setObjectName("kpiValue")
        cap = QtWidgets.QLabel(caption)
        cap.setObjectName("kpiCaption")
        lay.addWidget(value)
        lay.addWidget(cap)
        box.value_label = value  # type: ignore[attr-defined]
        return box

    def _set_kpi(self, widget: QtWidgets.QWidget, text: str) -> None:
        value_label = getattr(widget, "value_label", None)
        if isinstance(value_label, QtWidgets.QLabel):
            value_label.setText(text)

    def _edge_clicked(self, row: int, _column: int) -> None:
        item = self.edge_table.item(row, 0)
        if item is not None:
            self.edge_activated.emit(str(item.data(QtCore.Qt.UserRole) or item.text()))

    def _node_clicked(self, row: int, _column: int) -> None:
        item = self.node_table.item(row, 0)
        if item is not None:
            self.node_activated.emit(str(item.data(QtCore.Qt.UserRole) or item.text()))

    def update_frame(self, dataset: MnemoDataset | None, idx: int, *, playing: bool, follow_enabled: bool) -> None:
        if dataset is None or dataset.time_s.size == 0:
            self.dataset_meta.setHtml("<p>Нет загруженного NPZ.</p>")
            return

        time_s = float(dataset.time_s[max(0, min(idx, dataset.time_s.size - 1))])
        edge_rows = _edge_rows_for_index(dataset, idx)
        node_rows = _node_rows_for_index(dataset, idx)
        narrative = _build_frame_narrative(dataset, idx, selected_edge=None, selected_node=None)

        top_edge_name = narrative.top_edge_name
        top_edge_value = narrative.top_edge_value
        max_pressure = narrative.top_node_value

        self._fill_table(self.edge_table, edge_rows[:8], dataset.q_unit)
        self._fill_table(self.node_table, node_rows[:8], "бар(g)")

        follow_text = "follow" if follow_enabled else "manual"
        state_text = "play" if playing else "pause"
        self._set_kpi(self.kpi_time, f"{time_s:5.2f} s")
        self._set_kpi(self.kpi_flow, f"{top_edge_value:6.1f}")
        self._set_kpi(self.kpi_pressure, f"{max_pressure:4.2f}")
        self._set_kpi(self.kpi_state, f"{follow_text} / {state_text}")
        self.dataset_meta.setHtml(
            "<b>Файл:</b> "
            + escape(dataset.npz_path.name)
            + "<br/><b>Overlay:</b> "
            + f"{len(dataset.edge_names)} веток, {len(dataset.overlay_node_names)} ключевых узлов"
            + "<br/><b>Ведущий сценарий:</b> "
            + escape(narrative.primary_title)
            + "<br/><b>Самая активная ветка:</b> "
            + escape(top_edge_name)
            + f" ({top_edge_value:6.1f} {dataset.q_unit})"
            + "<br/><b>Макс. узел:</b> "
            + escape(narrative.top_node_name)
            + f" ({narrative.top_node_value:4.2f} бар(g))"
            + "<br/><b>Перепад ключевых давлений:</b> "
            + f"{narrative.pressure_spread:4.2f} бар(g)"
            + "<br/><b>Подход:</b> semantic layout, отдельное окно, внешние docks, глобальный playhead."
        )

    @staticmethod
    def _fill_table(table: QtWidgets.QTableWidget, rows: list[tuple[str, float]], unit: str) -> None:
        table.setRowCount(len(rows))
        for row_idx, (name, value) in enumerate(rows):
            item_name = QtWidgets.QTableWidgetItem(name)
            item_name.setData(QtCore.Qt.UserRole, name)
            item_value = QtWidgets.QTableWidgetItem(f"{value:8.2f} {unit}")
            table.setItem(row_idx, 0, item_name)
            table.setItem(row_idx, 1, item_value)


class SelectionPanel(QtWidgets.QWidget):
    edge_selected = QtCore.Signal(str)
    node_selected = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        edge_row = QtWidgets.QHBoxLayout()
        edge_row.addWidget(QtWidgets.QLabel("Ветка"))
        self.edge_combo = QtWidgets.QComboBox()
        self.edge_combo.setEditable(True)
        self.edge_combo.currentTextChanged.connect(self._on_edge_changed)
        edge_row.addWidget(self.edge_combo, 1)
        lay.addLayout(edge_row)

        node_row = QtWidgets.QHBoxLayout()
        node_row.addWidget(QtWidgets.QLabel("Узел"))
        self.node_combo = QtWidgets.QComboBox()
        self.node_combo.setEditable(True)
        self.node_combo.currentTextChanged.connect(self._on_node_changed)
        node_row.addWidget(self.node_combo, 1)
        lay.addLayout(node_row)

        self.details = QtWidgets.QTextBrowser()
        lay.addWidget(self.details, 1)

    def set_inventory(self, edge_names: list[str], node_names: list[str]) -> None:
        self._set_combo_items(self.edge_combo, edge_names)
        self._set_combo_items(self.node_combo, node_names)

    @staticmethod
    def _set_combo_items(combo: QtWidgets.QComboBox, items: list[str]) -> None:
        with QtCore.QSignalBlocker(combo):
            current = combo.currentText()
            combo.clear()
            combo.addItem("")
            combo.addItems(items)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)

    def set_selection(self, *, edge_name: str | None, node_name: str | None) -> None:
        with QtCore.QSignalBlocker(self.edge_combo):
            idx = self.edge_combo.findText(edge_name or "")
            self.edge_combo.setCurrentIndex(idx if idx >= 0 else 0)
        with QtCore.QSignalBlocker(self.node_combo):
            idx = self.node_combo.findText(node_name or "")
            self.node_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def render_details(self, dataset: MnemoDataset | None, idx: int, *, edge_name: str | None, node_name: str | None) -> None:
        if dataset is None:
            self.details.setHtml("<p>Нет данных.</p>")
            return

        chunks: list[str] = ["<h3>Выбор</h3>"]
        if edge_name and dataset.bundle.q is not None:
            q_arr = dataset.bundle.q.column(edge_name, default=None)
            open_arr = dataset.bundle.open.column(edge_name, default=None) if dataset.bundle.open is not None else None
            if q_arr is not None:
                q_vals = np.asarray(q_arr, dtype=float) * dataset.q_scale
                q_now = float(q_vals[idx])
                q_peak = float(np.max(np.abs(q_vals))) if q_vals.size else 0.0
                edge_def = dataset.edge_defs.get(edge_name, {})
                endpoint_1 = str(edge_def.get("n1") or "—")
                endpoint_2 = str(edge_def.get("n2") or "—")
                state = "открыт"
                if open_arr is not None:
                    state = "открыт" if int(np.asarray(open_arr, dtype=int)[idx]) else "закрыт"
                chunks.append(
                    "<p><b>Ветка:</b> "
                    + escape(edge_name)
                    + "<br/><b>Текущее Q:</b> "
                    + f"{q_now:8.2f} {dataset.q_unit}"
                    + "<br/><b>Пик |Q|:</b> "
                    + f"{q_peak:8.2f} {dataset.q_unit}"
                    + "<br/><b>Состояние:</b> "
                    + escape(state)
                    + "<br/><b>Маршрут:</b> "
                    + escape(endpoint_1)
                    + " → "
                    + escape(endpoint_2)
                    + "</p>"
                )

        if node_name and dataset.bundle.p is not None:
            p_arr = dataset.bundle.p.column(node_name, default=None)
            if p_arr is not None:
                p_vals = _bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)
                p_now = float(p_vals[idx])
                p_min = float(np.min(p_vals)) if p_vals.size else 0.0
                p_max = float(np.max(p_vals)) if p_vals.size else 0.0
                chunks.append(
                    "<p><b>Узел:</b> "
                    + escape(node_name)
                    + "<br/><b>Текущее P:</b> "
                    + f"{p_now:6.2f} бар(g)"
                    + "<br/><b>Диапазон:</b> "
                    + f"{p_min:6.2f} ... {p_max:6.2f} бар(g)"
                    + "<br/><b>Тип отображения:</b> cognitive overlay / contextual details</p>"
                )

        if len(chunks) == 1:
            chunks.append(
                "<p>Клик по ветке или узлу на мнемосхеме, либо выберите сигнал из комбобоксов. "
                "Панель справа оставляет деталь короткой и численной, чтобы не перегружать восприятие во время анимации.</p>"
            )

        self.details.setHtml("".join(chunks))

    def _on_edge_changed(self, text: str) -> None:
        if text:
            self.edge_selected.emit(text)

    def _on_node_changed(self, text: str) -> None:
        if text:
            self.node_selected.emit(text)


class GuidancePanel(QtWidgets.QTextBrowser):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)

    @staticmethod
    def _severity_badge(severity: str) -> str:
        palette = {
            "focus": ("#63d3f5", "#09212a"),
            "warn": ("#f8c15c", "#2b1c09"),
            "attention": ("#f0936b", "#30150f"),
            "ok": ("#81e7a3", "#0f2a1c"),
            "info": ("#9cb9c7", "#17252d"),
        }
        fg, bg = palette.get(str(severity), ("#9cb9c7", "#17252d"))
        return (
            f'<span style="display:inline-block; padding:2px 8px; border-radius:999px; '
            f'background:{bg}; color:{fg}; font-weight:700; font-size:11px;">{escape(str(severity).upper())}</span>'
        )

    def render(
        self,
        dataset: MnemoDataset | None,
        idx: int,
        *,
        selected_edge: str | None,
        selected_node: str | None,
        playing: bool,
        follow_enabled: bool,
    ) -> None:
        narrative = _build_frame_narrative(dataset, idx, selected_edge=selected_edge, selected_node=selected_node)

        if dataset is None or dataset.time_s.size == 0:
            self.setHtml(
                "<h3>Диагностические сценарии</h3>"
                "<p>Это окно помогает читать мнемосхему как инженерную историю, а не как набор линий.</p>"
                "<p><b>Порядок чтения:</b><br/>"
                "1. Найдите ведущую ветку.<br/>"
                "2. Подтвердите один опорный узел давления.<br/>"
                "3. Только потом открывайте тренды для численной проверки.</p>"
                "<p>Как только появится NPZ, панель начнёт подсказывать текущий режим и следующий шаг диагностики.</p>"
            )
            return

        mode_cards: list[str] = []
        for mode in narrative.modes:
            mode_cards.append(
                '<div style="margin:0 0 10px 0; padding:10px 12px; border-radius:12px; '
                'background:rgba(16,38,48,0.86); border:1px solid rgba(99,211,245,0.16);">'
                + self._severity_badge(mode.severity)
                + f'<div style="margin-top:8px; font-weight:700; color:#eef6f8;">{escape(mode.title)}</div>'
                + f'<div style="margin-top:6px; color:#d2e1e8;">{escape(mode.summary)}</div>'
                + f'<div style="margin-top:6px; color:#8fb0bc;"><b>Что проверить дальше:</b> {escape(mode.action)}</div>'
                + "</div>"
            )

        state_text = "follow" if follow_enabled else "manual"
        playback_text = "play" if playing else "pause"
        selected_block = (
            "<b>Фокус:</b> "
            + escape(selected_edge or "—")
            + " / "
            + escape(selected_node or "—")
        )

        self.setHtml(
            "<h3>Диагностические сценарии</h3>"
            + "<p><b>Текущий режим:</b> "
            + escape(narrative.primary_title)
            + "<br/>"
            + "<b>Состояние окна:</b> "
            + escape(state_text)
            + " / "
            + escape(playback_text)
            + "<br/>"
            + selected_block
            + "</p>"
            + "<p style='color:#8fb0bc;'>"
            + escape(narrative.primary_summary)
            + "</p>"
            + "".join(mode_cards)
        )


class StartupBannerPanel(QtWidgets.QFrame):
    hide_requested = QtCore.Signal()
    focus_requested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("startup_banner")
        self._focus_available = False

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)
        lay.addLayout(top_row)

        title_wrap = QtWidgets.QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        top_row.addLayout(title_wrap, 1)

        self.title_label = QtWidgets.QLabel("Рекомендуемый старт")
        self.title_label.setObjectName("startup_banner_title")
        title_wrap.addWidget(self.title_label)

        self.caption_label = QtWidgets.QLabel(
            "Небольшой onboarding-блок снижает когнитивный шум: сначала сценарий, потом числа, потом действие."
        )
        self.caption_label.setObjectName("startup_banner_caption")
        self.caption_label.setWordWrap(True)
        title_wrap.addWidget(self.caption_label)

        self.focus_button = QtWidgets.QPushButton(self)
        self.focus_button.setText("Навести фокус на схему")
        self.focus_button.clicked.connect(lambda _checked=False: self.focus_requested.emit())
        top_row.addWidget(self.focus_button, 0, QtCore.Qt.AlignTop)

        self.dismiss_button = QtWidgets.QToolButton(self)
        self.dismiss_button.setText("Скрыть onboarding")
        self.dismiss_button.clicked.connect(lambda _checked=False: self.hide_requested.emit())
        top_row.addWidget(self.dismiss_button, 0, QtCore.Qt.AlignTop)

        self.body = QtWidgets.QTextBrowser(self)
        self.body.setObjectName("startup_banner_body")
        self.body.setOpenExternalLinks(False)
        self.body.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.body.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.body.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.body.setMaximumHeight(210)
        lay.addWidget(self.body)

    @staticmethod
    def _pill(text: str, *, fg: str, bg: str) -> str:
        return (
            f'<span style="display:inline-block; margin:0 6px 6px 0; padding:3px 10px; border-radius:999px; '
            f'background:{bg}; color:{fg}; font-weight:700; font-size:11px;">{escape(text)}</span>'
        )

    def render(
        self,
        context: LaunchOnboardingContext,
        *,
        dataset: MnemoDataset | None,
        idx: int,
        tracker: MnemoEventTracker,
        follow_enabled: bool,
    ) -> None:
        self.title_label.setText(context.title)
        narrative = _build_frame_narrative(dataset, idx, selected_edge=None, selected_node=None)
        focus_target = build_onboarding_focus_target(dataset, idx)
        self._focus_available = focus_target.has_target
        self.focus_button.setEnabled(focus_target.has_target)
        self.focus_button.setToolTip(focus_target.summary)
        active_latches = tracker.active_latched_events(limit=6) if dataset is not None else []
        active_latch_count = len(active_latches)
        launch_mode_map = {
            "follow": "FOLLOW",
            "npz": "NPZ REVIEW",
            "blank": "EMPTY START",
        }
        launch_mode_label = launch_mode_map.get(context.launch_mode, context.launch_mode.upper())

        badges = [
            self._pill(launch_mode_label, fg="#eef6f8", bg="rgba(9,33,42,0.72)"),
            self._pill(
                "live pointer" if follow_enabled else "manual dataset",
                fg="#63d3f5",
                bg="rgba(9,33,42,0.72)",
            ),
            self._pill(
                f"active latch {active_latch_count}",
                fg="#f8c15c" if active_latch_count else "#81e7a3",
                bg="rgba(9,33,42,0.72)",
            ),
        ]
        if dataset is not None and dataset.time_s.size:
            badges.append(
                self._pill(
                    narrative.primary_title,
                    fg="#9fdcf0",
                    bg="rgba(9,33,42,0.72)",
                )
            )

        checklist_html = "".join(f"<li>{escape(item)}</li>" for item in context.checklist[:4])
        if dataset is None or dataset.time_s.size == 0:
            focus_block = (
                "<p style='color:#8fb0bc; margin:8px 0 0 0;'>"
                "Bundle ещё не загружен. Как только появится NPZ, banner уточнит ведущую ветку и опорный узел."
                "</p>"
            )
        else:
            focus_block = (
                "<p style='margin:8px 0 0 0;'>"
                f"<b>Первый инженерный фокус:</b> {escape(narrative.top_edge_name)} / {escape(narrative.top_node_name)}"
                f"<br/><b>Текущий режим:</b> {escape(narrative.primary_title)}"
                f"<br/><b>Подсветка onboarding:</b> {escape(focus_target.edge_name or '—')} / {escape(focus_target.node_name or '—')}"
                f"<br/><b>Bundle:</b> {escape(dataset.npz_path.name)}"
                "</p>"
            )

        self.body.setHtml(
            "<div>"
            + "".join(badges)
            + f"<p style='margin:6px 0 0 0;'><b>Почему окно открылось так:</b> {escape(context.reason)}</p>"
            + focus_block
            + f"<p style='margin:8px 0 0 0; color:#9fc5d2;'><b>Что сделает кнопка:</b> {escape(focus_target.summary)}</p>"
            + "<p style='margin:10px 0 4px 0;'><b>Первый чек-лист оператора:</b></p>"
            + f"<ol style='margin:0 0 0 18px; padding:0;'>{checklist_html}</ol>"
            + "</div>"
        )


class EventMemoryPanel(QtWidgets.QTextBrowser):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)

    @staticmethod
    def _severity_badge(severity: str, title: str) -> str:
        palette = {
            "focus": ("#63d3f5", "#09212a"),
            "warn": ("#f8c15c", "#2b1c09"),
            "attention": ("#f0936b", "#30150f"),
            "ok": ("#81e7a3", "#0f2a1c"),
            "info": ("#9cb9c7", "#17252d"),
        }
        fg, bg = palette.get(str(severity), ("#9cb9c7", "#17252d"))
        return (
            f'<span style="display:inline-block; padding:2px 8px; border-radius:999px; '
            f'background:{bg}; color:{fg}; font-weight:700; font-size:11px;">{escape(title)}</span>'
        )

    @staticmethod
    def _severity_color(severity: str) -> str:
        palette = {
            "focus": "#63d3f5",
            "warn": "#f8c15c",
            "attention": "#f0936b",
            "ok": "#81e7a3",
            "info": "#9cb9c7",
        }
        return palette.get(str(severity), "#9cb9c7")

    def render(
        self,
        dataset: MnemoDataset | None,
        idx: int,
        *,
        tracker: MnemoEventTracker,
        playing: bool,
        follow_enabled: bool,
    ) -> None:
        if dataset is None or dataset.time_s.size == 0:
            self.setHtml(
                "<h3>Латчи и события</h3>"
                "<p>Панель запоминает важные переключения режима и тревожные эпизоды, "
                "чтобы оператор видел не только текущий кадр, но и недавнюю историю.</p>"
                "<p>После загрузки NPZ здесь появятся:</p>"
                "<p>1. Латчи тревог текущего прогона.<br/>"
                "2. Мини-таймлайн с метками событий.<br/>"
                "3. Недавние переключения режима и ветвей.<br/>"
                "4. ACK/RESET цикл и экспорт event-log sidecar.</p>"
            )
            return

        clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
        time_now = float(dataset.time_s[clamped_idx])
        narrative = _build_frame_narrative(dataset, clamped_idx, selected_edge=None, selected_node=None)
        active_latched = tracker.active_latched_events(limit=5)
        acked_latched = tracker.acknowledged_latched_events(limit=5)
        recent = tracker.recent_events(limit=8)
        live_modes = [mode for mode in narrative.modes if mode.severity in {"focus", "warn", "attention"}]
        state_text = "follow" if follow_enabled else "manual"
        playback_text = "play" if playing else "pause"
        sidecar_path = _event_log_sidecar_path(dataset.npz_path)

        live_badges = "".join(self._severity_badge(mode.severity, mode.title) for mode in live_modes)
        if not live_badges:
            live_badges = self._severity_badge("ok", "Спокойный кадр")

        active_rows: list[str] = []
        for event in active_latched:
            active_rows.append(
                '<div style="margin:0 0 8px 0; padding:8px 10px; border-radius:12px; '
                'background:rgba(16,38,48,0.86); border:1px solid rgba(248,193,92,0.20);">'
                + self._severity_badge(event.severity, event.title)
                + f"<div style='margin-top:6px; color:#d2e1e8;'>{escape(event.summary)}</div>"
                + f"<div style='margin-top:4px; color:#8fb0bc;'>t={event.time_s:5.2f} s"
                + (f" • {escape(event.edge_name)}" if event.edge_name else "")
                + "</div></div>"
            )
        if not active_rows:
            active_rows.append(
                "<p style='color:#8fb0bc;'>Сейчас нет необработанных latched-событий. "
                "Новые warn/attention эпизоды сразу появятся здесь без ручного обновления.</p>"
            )

        acked_rows: list[str] = []
        for event in acked_latched:
            acked_rows.append(
                '<div style="margin:0 0 8px 0; padding:8px 10px; border-radius:12px; '
                'background:rgba(10,27,34,0.72); border:1px solid rgba(129,231,163,0.18);">'
                + self._severity_badge("ok", "ACK")
                + " "
                + self._severity_badge(event.severity, event.title)
                + f"<div style='margin-top:6px; color:#d2e1e8;'>{escape(event.summary)}</div>"
                + f"<div style='margin-top:4px; color:#8fb0bc;'>t={event.time_s:5.2f} s"
                + (f" • {escape(event.edge_name)}" if event.edge_name else "")
                + "</div></div>"
            )
        if not acked_rows:
            acked_rows.append(
                "<p style='color:#8fb0bc;'>ACK-подтверждённых latched-событий пока нет.</p>"
            )

        recent_rows: list[str] = []
        for event in recent:
            recent_rows.append(
                "<div style='margin:0 0 6px 0; padding:8px 10px; border-radius:10px; "
                "background:rgba(10,27,34,0.65); border:1px solid rgba(99,211,245,0.10);'>"
                + self._severity_badge(event.severity, event.title)
                + f"<div style='margin-top:5px; color:#d2e1e8;'>{escape(event.summary)}</div>"
                + f"<div style='margin-top:4px; color:#8fb0bc;'>t={event.time_s:5.2f} s • кадр {event.frame_idx}</div>"
                + "</div>"
            )

        span = max(float(dataset.time_s[-1] - dataset.time_s[0]), 1.0e-9)
        timeline_markers: list[str] = []
        for event in tracker.events[-24:]:
            left = 100.0 * max(0.0, min(1.0, (event.time_s - float(dataset.time_s[0])) / span))
            height = 24 if event.severity in {"warn", "attention"} else 18
            top = 6 if event.severity in {"warn", "attention"} else 12
            timeline_markers.append(
                f'<div title="{escape(event.title)} @ {event.time_s:5.2f}s" '
                f'style="position:absolute; left:calc({left:5.2f}% - 2px); top:{top}px; '
                f'width:4px; height:{height}px; border-radius:999px; '
                f'background:{self._severity_color(event.severity)}; opacity:0.92;"></div>'
            )
        cursor_left = 100.0 * max(0.0, min(1.0, (time_now - float(dataset.time_s[0])) / span))
        timeline_markers.append(
            f'<div title="Текущий кадр" style="position:absolute; left:calc({cursor_left:5.2f}% - 1px); top:0; '
            'width:2px; height:36px; border-radius:999px; background:#eef6f8; opacity:0.95;"></div>'
        )

        self.setHtml(
            "<h3>Латчи и события</h3>"
            + "<p><b>Состояние окна:</b> "
            + escape(state_text)
            + " / "
            + escape(playback_text)
            + f"<br/><b>Текущий режим:</b> {escape(narrative.primary_title)}"
            + f"<br/><b>Ведущая ветка:</b> {escape(narrative.top_edge_name)}"
            + f"<br/><b>Время:</b> {time_now:5.2f} s</p>"
            + "<p><b>Живые индикаторы кадра:</b><br/>"
            + live_badges
            + "</p>"
            + "<p style='color:#8fb0bc;'><b>Управление:</b> используйте toolbar или меню "
            "<b>События</b> для действий <b>ACK</b>, <b>Reset</b> и <b>Экспорт событий</b>."
            + f"<br/><b>Sidecar:</b> {escape(str(sidecar_path.name))}</p>"
            + "<h4>Активные latched-события</h4>"
            + "".join(active_rows)
            + "<h4>ACK-подтверждённые latched-события</h4>"
            + "".join(acked_rows)
            + "<h4>Мини-таймлайн событий</h4>"
            + '<div style="position:relative; height:36px; border-radius:12px; '
            'background:linear-gradient(180deg, rgba(16,38,48,0.95), rgba(9,20,26,0.95)); '
            'border:1px solid rgba(99,211,245,0.14); overflow:hidden;">'
            + "".join(timeline_markers)
            + "</div>"
            + f"<div style='display:flex; justify-content:space-between; color:#8fb0bc; margin-top:4px;'>"
            + f"<span>{float(dataset.time_s[0]):5.2f} s</span><span>{float(dataset.time_s[-1]):5.2f} s</span></div>"
            + "<h4>Недавние события</h4>"
            + ("".join(recent_rows) if recent_rows else "<p style='color:#8fb0bc;'>История пока пуста.</p>")
        )


class TrendsPanel(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        self._has_pg = _HAS_PG
        if not self._has_pg:
            msg = QtWidgets.QTextBrowser()
            msg.setHtml("<p>pyqtgraph не установлен. Тренды недоступны.</p>")
            lay.addWidget(msg)
            self.flow_plot = None
            self.pressure_plot = None
            self.flow_curve = None
            self.pressure_curve = None
            self.flow_marker = None
            self.pressure_marker = None
            return

        assert pg is not None
        self.flow_plot = pg.PlotWidget()
        self.pressure_plot = pg.PlotWidget()
        for plot in (self.flow_plot, self.pressure_plot):
            plot.setBackground((9, 20, 26))
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.getAxis("left").setTextPen("#d9e6ed")
            plot.getAxis("bottom").setTextPen("#d9e6ed")
            plot.getAxis("left").setPen("#315563")
            plot.getAxis("bottom").setPen("#315563")
            plot.addLegend(offset=(10, 10))
            lay.addWidget(plot, 1)

        self.flow_plot.setLabel("left", "Q", units="")
        self.flow_plot.setLabel("bottom", "t", units="s")
        self.pressure_plot.setLabel("left", "P", units="бар(g)")
        self.pressure_plot.setLabel("bottom", "t", units="s")

        self.flow_curve = self.flow_plot.plot(pen=pg.mkPen("#63d3f5", width=2), name="Q")
        self.pressure_curve = self.pressure_plot.plot(pen=pg.mkPen("#81e7a3", width=2), name="P")
        self.flow_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#f8c15c", width=1.2))
        self.pressure_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#f8c15c", width=1.2))
        self.flow_plot.addItem(self.flow_marker)
        self.pressure_plot.addItem(self.pressure_marker)

    def set_series(self, dataset: MnemoDataset | None, *, edge_name: str | None, node_name: str | None) -> None:
        if not self._has_pg or dataset is None:
            return
        assert self.flow_curve is not None
        assert self.pressure_curve is not None
        assert self.flow_plot is not None
        assert self.pressure_plot is not None

        if edge_name and dataset.bundle.q is not None:
            q_arr = dataset.bundle.q.column(edge_name, default=None)
            if q_arr is not None:
                q_vals = np.asarray(q_arr, dtype=float) * dataset.q_scale
                self.flow_curve.setData(dataset.time_s, q_vals, name=edge_name)
                self.flow_plot.setTitle(f"Q: {edge_name}", color="#d9e6ed")
        else:
            self.flow_curve.setData([], [])
            self.flow_plot.setTitle("Q: выберите ветку", color="#88a3af")

        if node_name and dataset.bundle.p is not None:
            p_arr = dataset.bundle.p.column(node_name, default=None)
            if p_arr is not None:
                p_vals = _bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)
                self.pressure_curve.setData(dataset.time_s, p_vals, name=node_name)
                self.pressure_plot.setTitle(f"P: {node_name}", color="#d9e6ed")
        else:
            self.pressure_curve.setData([], [])
            self.pressure_plot.setTitle("P: выберите узел", color="#88a3af")

    def set_index(self, dataset: MnemoDataset | None, idx: int) -> None:
        if not self._has_pg or dataset is None or dataset.time_s.size == 0:
            return
        time_value = float(dataset.time_s[max(0, min(idx, dataset.time_s.size - 1))])
        assert self.flow_marker is not None
        assert self.pressure_marker is not None
        self.flow_marker.setValue(time_value)
        self.pressure_marker.setValue(time_value)


class MnemoMainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        *,
        npz_path: Path | None,
        follow: bool,
        pointer_path: Path,
        theme: str,
        startup_preset: str,
        startup_title: str,
        startup_reason: str,
        startup_view_mode: str,
        startup_checklist: list[str] | tuple[str, ...] | None,
    ):
        super().__init__()
        self.setWindowTitle("Desktop Pneumo Mnemo")
        self.setMinimumSize(1500, 980)
        self.setDockOptions(
            QtWidgets.QMainWindow.AllowNestedDocks
            | QtWidgets.QMainWindow.AllowTabbedDocks
            | QtWidgets.QMainWindow.AnimatedDocks
        )

        self.pointer_path = Path(pointer_path)
        self.follow_enabled = bool(follow)
        self.theme = str(theme)
        self.dataset: MnemoDataset | None = None
        self.selected_edge: str | None = None
        self.selected_node: str | None = None
        self.current_idx = 0
        self.playing = False
        self._last_tick = time.perf_counter()
        self._play_speed = 1.0
        self.event_tracker = MnemoEventTracker(max_events=96)
        self._last_event_log_path: Path | None = None
        self.launch_context = build_launch_onboarding_context(
            npz_path=npz_path,
            follow=self.follow_enabled,
            pointer_path=self.pointer_path,
            preset_key=startup_preset,
            title=startup_title,
            reason=startup_reason,
            checklist=startup_checklist,
        )

        self.ui_state = UiState(default_settings_path(PROJECT_ROOT), prefix="desktop_mnemo")
        self._persisted_view_mode = self._normalize_view_mode(self.ui_state.get_str("view_mode", "focus"))
        self._startup_view_mode_override = self._parse_startup_view_mode_override(startup_view_mode)
        self._view_mode_override_active = bool(self._startup_view_mode_override)
        self.view_mode = self._startup_view_mode_override or self._persisted_view_mode
        self.setStyleSheet(APP_STYLESHEET_DARK if self.theme == "dark" else APP_STYLESHEET_LIGHT)

        self.web = MnemoWebView(self)
        self.web.edge_picked.connect(self._select_edge)
        self.web.node_picked.connect(self._select_node)
        self.web.status.connect(self._set_status)
        self.startup_banner = StartupBannerPanel(self)
        self.startup_banner.hide_requested.connect(lambda: self._set_startup_banner_visible(False))
        self.startup_banner.focus_requested.connect(self._apply_onboarding_focus)
        self.startup_banner.render(
            self.launch_context,
            dataset=None,
            idx=0,
            tracker=self.event_tracker,
            follow_enabled=self.follow_enabled,
        )

        self._central_host = QtWidgets.QWidget(self)
        self._central_layout = QtWidgets.QVBoxLayout(self._central_host)
        self._central_layout.setContentsMargins(8, 8, 8, 0)
        self._central_layout.setSpacing(8)
        self._central_layout.addWidget(self.startup_banner, 0)
        self._central_layout.addWidget(self.web, 1)
        self.setCentralWidget(self._central_host)

        self.overview_panel = OverviewPanel(self)
        self.overview_panel.edge_activated.connect(self._select_edge)
        self.overview_panel.node_activated.connect(self._select_node)
        self.selection_panel = SelectionPanel(self)
        self.selection_panel.edge_selected.connect(self._select_edge)
        self.selection_panel.node_selected.connect(self._select_node)
        self.trends_panel = TrendsPanel(self)
        self.guide_panel = GuidancePanel(self)
        self.event_panel = EventMemoryPanel(self)
        self.legend_panel = QtWidgets.QTextBrowser(self)
        self.legend_panel.setHtml(
            "<h3>Легенда и UX-правила</h3>"
            "<p><b>Бирюзовый</b> — поток по направлению ветки.<br/>"
            "<b>Оранжевый</b> — реверс потока.<br/>"
            "<b>Серый</b> — закрытый элемент.</p>"
            "<p><b>Что где читать:</b><br/>"
            "<b>Центр</b> — топология и причинно-следственная картина.<br/>"
            "<b>Обзор</b> — что сейчас доминирует.<br/>"
            "<b>Диагностические сценарии</b> — как интерпретировать текущий кадр.<br/>"
            "<b>События</b> — latched-память и недавние переключения.<br/>"
            "<b>Тренды</b> — численная проверка гипотезы.</p>"
            "<p>Такое разделение снижает когнитивное переключение: в центре остаётся только схема, "
            "а чтение режима и чисел уходит в отдельные docks, как в современных инженерных HMI.</p>"
        )
        self.guide_panel.render(None, 0, selected_edge=None, selected_node=None, playing=self.playing, follow_enabled=self.follow_enabled)
        self.event_panel.render(None, 0, tracker=self.event_tracker, playing=self.playing, follow_enabled=self.follow_enabled)

        self._overview_dock = self._add_dock("Обзор", self.overview_panel, QtCore.Qt.LeftDockWidgetArea, obj_name="dock_overview")
        self._selection_dock = self._add_dock("Выбор", self.selection_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_selection")
        self._guide_dock = self._add_dock("Диагностика", self.guide_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_guide")
        self._events_dock = self._add_dock("События", self.event_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_events")
        self._trends_dock = self._add_dock("Тренды", self.trends_panel, QtCore.Qt.BottomDockWidgetArea, obj_name="dock_trends")
        self._legend_dock = self._add_dock("Легенда", self.legend_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_legend")

        self._build_toolbar()
        self._build_menus()
        self._build_statusbar()
        self._set_startup_banner_visible(True)

        self.play_timer = QtCore.QTimer(self)
        self.play_timer.setInterval(40)
        self.play_timer.timeout.connect(self._advance_playback)

        self.pointer_watcher = PointerWatcher(self.pointer_path)
        self.pointer_watcher.npz_changed.connect(self._reload_from_pointer)
        self.pointer_watcher.status.connect(self._set_status)
        if self.follow_enabled:
            self.pointer_watcher.start()

        self._restore_window_state()
        self.follow_action.setChecked(self.follow_enabled)

        initial_path = Path(npz_path).resolve() if npz_path is not None else self.pointer_watcher._resolve_pointer_npz()
        if initial_path is not None and initial_path.exists():
            self.load_dataset(initial_path, preserve_selection=False)
        else:
            self._set_status(f"Ожидание NPZ. Pointer: {self.pointer_path}")
            self._render_startup_banner()

    def _add_dock(
        self,
        title: str,
        widget: QtWidgets.QWidget,
        area: QtCore.Qt.DockWidgetArea,
        *,
        obj_name: str,
    ) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(title, self)
        dock.setObjectName(obj_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.RightDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
            | QtCore.Qt.TopDockWidgetArea
        )
        self.addDockWidget(area, dock)
        return dock

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Mnemo")
        tb.setMovable(False)

        open_action = QtGui.QAction("Открыть NPZ", self)
        open_action.triggered.connect(self._open_npz_dialog)
        tb.addAction(open_action)

        reload_action = QtGui.QAction("Reload", self)
        reload_action.triggered.connect(self._reload_current)
        tb.addAction(reload_action)

        self.follow_action = QtGui.QAction("Follow", self)
        self.follow_action.setCheckable(True)
        self.follow_action.toggled.connect(self._toggle_follow)
        tb.addAction(self.follow_action)

        self.play_action = QtGui.QAction("Play", self)
        self.play_action.setCheckable(True)
        self.play_action.toggled.connect(self._toggle_play)
        tb.addAction(self.play_action)

        self.ack_events_action = QtGui.QAction("ACK события", self)
        self.ack_events_action.triggered.connect(self._acknowledge_events)
        tb.addAction(self.ack_events_action)

        self.reset_events_action = QtGui.QAction("Reset события", self)
        self.reset_events_action.triggered.connect(self._reset_events_memory)
        tb.addAction(self.reset_events_action)

        self.export_events_action = QtGui.QAction("Экспорт событий", self)
        self.export_events_action.triggered.connect(self._export_event_log)
        tb.addAction(self.export_events_action)

        self.startup_banner_action = QtGui.QAction("Onboarding", self)
        self.startup_banner_action.setCheckable(True)
        self.startup_banner_action.toggled.connect(self._set_startup_banner_visible)
        tb.addAction(self.startup_banner_action)

        self.return_focus_action = QtGui.QAction("Вернуться к фокусу", self)
        self.return_focus_action.triggered.connect(self._apply_onboarding_focus)
        tb.addAction(self.return_focus_action)

        self.full_scheme_action = QtGui.QAction("Вся схема", self)
        self.full_scheme_action.triggered.connect(self._show_full_scheme_overview)
        tb.addAction(self.full_scheme_action)

        self.speed_combo = QtWidgets.QComboBox()
        for speed in (0.25, 0.5, 1.0, 1.5, 2.0, 4.0):
            self.speed_combo.addItem(f"{speed:.2f}x", speed)
        saved_speed = self.ui_state.get_float("play_speed", 1.0)
        idx = max(0, self.speed_combo.findData(saved_speed))
        self.speed_combo.setCurrentIndex(idx)
        self.speed_combo.currentIndexChanged.connect(self._speed_changed)
        tb.addWidget(self.speed_combo)

        self.scrubber = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.scrubber.setMinimum(0)
        self.scrubber.setMaximum(0)
        self.scrubber.setTracking(True)
        self.scrubber.setMinimumWidth(420)
        self.scrubber.valueChanged.connect(self._on_scrubbed)
        tb.addWidget(self.scrubber)

        self.time_label = QtWidgets.QLabel("t = —")
        tb.addWidget(self.time_label)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        action_open = file_menu.addAction("Открыть NPZ…")
        action_open.triggered.connect(self._open_npz_dialog)
        action_reload = file_menu.addAction("Reload")
        action_reload.triggered.connect(self._reload_current)
        file_menu.addSeparator()
        action_quit = file_menu.addAction("Выход")
        action_quit.triggered.connect(self.close)

        view_menu = self.menuBar().addMenu("Вид")
        view_menu.addAction(self._overview_dock.toggleViewAction())
        view_menu.addAction(self._selection_dock.toggleViewAction())
        view_menu.addAction(self._guide_dock.toggleViewAction())
        view_menu.addAction(self._events_dock.toggleViewAction())
        view_menu.addAction(self._trends_dock.toggleViewAction())
        view_menu.addAction(self._legend_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction(self.startup_banner_action)
        view_menu.addAction(self.return_focus_action)
        view_menu.addAction(self.full_scheme_action)

        playback_menu = self.menuBar().addMenu("Анимация")
        playback_menu.addAction(self.play_action)
        act_reset = playback_menu.addAction("В начало")
        act_reset.triggered.connect(self._jump_to_start)

        events_menu = self.menuBar().addMenu("События")
        events_menu.addAction(self._events_dock.toggleViewAction())
        events_menu.addSeparator()
        events_menu.addAction(self.ack_events_action)
        events_menu.addAction(self.reset_events_action)
        events_menu.addAction(self.export_events_action)

    def _build_statusbar(self) -> None:
        self.status_text = QtWidgets.QLabel("Готово.")
        self.path_text = QtWidgets.QLabel("")
        self.statusBar().addWidget(self.status_text, 1)
        self.statusBar().addPermanentWidget(self.path_text, 1)

    @staticmethod
    def _normalize_view_mode(mode: str) -> str:
        return "overview" if str(mode or "").strip().lower() == "overview" else "focus"

    @staticmethod
    def _parse_startup_view_mode_override(mode: str) -> str:
        raw_mode = str(mode or "").strip().lower()
        if raw_mode in {"focus", "overview"}:
            return raw_mode
        return ""

    def _set_view_mode(self, mode: str, *, persist: bool) -> str:
        self.view_mode = self._normalize_view_mode(mode)
        if persist:
            self._persisted_view_mode = self.view_mode
            self._startup_view_mode_override = ""
            self._view_mode_override_active = False
            try:
                self.ui_state.set_value("view_mode", self.view_mode)
            except Exception:
                pass
        return self.view_mode

    def _set_startup_banner_visible(self, visible: bool) -> None:
        is_visible = bool(visible)
        if is_visible:
            self._render_startup_banner()
        self.startup_banner.setVisible(is_visible)
        with QtCore.QSignalBlocker(self.startup_banner_action):
            self.startup_banner_action.setChecked(is_visible)

    def _render_startup_banner(self) -> None:
        self.startup_banner.render(
            self.launch_context,
            dataset=self.dataset,
            idx=self.current_idx,
            tracker=self.event_tracker,
            follow_enabled=self.follow_enabled,
        )

    def _current_focus_region_payload(self, *, source: str, auto_focus: bool) -> dict[str, Any] | None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return None
        return build_onboarding_focus_region_payload(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            source=source,
            auto_focus=auto_focus,
        )

    def _apply_current_view_mode(self, *, source: str, auto_focus: bool) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        focus_region = self._current_focus_region_payload(source=source, auto_focus=auto_focus)
        if self.view_mode == "overview":
            self.web.show_overview(
                {
                    "title": "Полная схема",
                    "summary": "Сравните рекомендуемый сценарий с полной топологией, не теряя быстрый путь назад к фокусу.",
                    "focus_region": focus_region,
                }
            )
            return
        self.web.set_focus_region(focus_region)

    def _sync_selection_views(self, *, clear_focus_region: bool = False) -> None:
        if self.dataset is None:
            return
        if clear_focus_region:
            self.web.set_focus_region(None)
        self.selection_panel.set_selection(edge_name=self.selected_edge, node_name=self.selected_node)
        self.selection_panel.render_details(
            self.dataset,
            self.current_idx,
            edge_name=self.selected_edge,
            node_name=self.selected_node,
        )
        self.trends_panel.set_series(self.dataset, edge_name=self.selected_edge, node_name=self.selected_node)
        self.guide_panel.render(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self.web.set_selection(edge=self.selected_edge, node=self.selected_node)
        self._push_alerts()
        if self.startup_banner.isVisible():
            self._render_startup_banner()

    def _apply_onboarding_focus(self) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        focus_target = build_onboarding_focus_target(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
        )
        if not focus_target.has_target:
            self._set_status("Onboarding focus пока не вычислен для текущего кадра.")
            return
        if focus_target.edge_name in self.dataset.edge_names:
            self.selected_edge = focus_target.edge_name
        if focus_target.node_name in self.dataset.node_names:
            self.selected_node = focus_target.node_name
        self._set_view_mode("focus", persist=True)
        self._sync_selection_views(clear_focus_region=False)
        self._apply_current_view_mode(source="startup_banner", auto_focus=False)
        self._set_status(
            f"Onboarding focus: {focus_target.edge_name or '—'} / {focus_target.node_name or '—'}"
        )

    def _show_full_scheme_overview(self) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        self._set_view_mode("overview", persist=True)
        self._apply_current_view_mode(source="toolbar_overview", auto_focus=False)
        self._set_status("Overview mode: показана полная схема.")

    def _restore_window_state(self) -> None:
        self.ui_state.bind_window_geometry(self, "window/geometry")
        state = self.ui_state.get_bytes("window/state")
        if state is not None:
            try:
                self.restoreState(state)
            except Exception:
                pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        self.ui_state.save_window_geometry(self, "window/geometry")
        try:
            self.ui_state.set_value("window/state", self.saveState())
            self.ui_state.set_value("play_speed", float(self._play_speed))
            if not self._view_mode_override_active:
                self.ui_state.set_value("view_mode", str(self.view_mode))
            self.ui_state.sync()
        except Exception:
            pass
        super().closeEvent(event)

    def _set_status(self, text: str) -> None:
        self.status_text.setText(str(text))

    def _set_dataset_title(self) -> None:
        if self.dataset is None:
            self.setWindowTitle("Desktop Pneumo Mnemo")
            self.path_text.setText("")
            return
        self.setWindowTitle(f"Desktop Pneumo Mnemo • {self.dataset.npz_path.name}")
        self.path_text.setText(str(self.dataset.npz_path))

    def _open_npz_dialog(self) -> None:
        base_dir = str(self.dataset.npz_path.parent if self.dataset is not None else PROJECT_ROOT)
        file_name, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Открыть NPZ", base_dir, "NPZ (*.npz)")
        if not file_name:
            return
        self.follow_action.setChecked(False)
        self.load_dataset(Path(file_name), preserve_selection=False)

    def _reload_current(self) -> None:
        if self.dataset is None:
            return
        self.load_dataset(self.dataset.npz_path, preserve_selection=True)

    def _reload_from_pointer(self, npz_path: Path) -> None:
        if self.follow_enabled:
            self.load_dataset(Path(npz_path), preserve_selection=True)

    def _toggle_follow(self, checked: bool) -> None:
        self.follow_enabled = bool(checked)
        if self.follow_enabled:
            self.pointer_watcher.start()
        else:
            self.pointer_watcher.stop()
        self._set_status(f"Follow {'ON' if self.follow_enabled else 'OFF'}")
        self.overview_panel.update_frame(self.dataset, self.current_idx, playing=self.playing, follow_enabled=self.follow_enabled)
        self.guide_panel.render(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self.event_panel.render(
            self.dataset,
            self.current_idx,
            tracker=self.event_tracker,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self._render_startup_banner()

    def _toggle_play(self, checked: bool) -> None:
        self.playing = bool(checked)
        self.play_action.setText("Pause" if self.playing else "Play")
        self._last_tick = time.perf_counter()
        if self.playing:
            self.play_timer.start()
        else:
            self.play_timer.stop()
        self._push_playhead()
        self.overview_panel.update_frame(self.dataset, self.current_idx, playing=self.playing, follow_enabled=self.follow_enabled)
        self.guide_panel.render(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self.event_panel.render(
            self.dataset,
            self.current_idx,
            tracker=self.event_tracker,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )

    def _jump_to_start(self) -> None:
        self.current_idx = 0
        self._refresh_frame()

    def _acknowledge_events(self) -> None:
        if self.dataset is None:
            return
        acked = self.event_tracker.acknowledge_active_latches(dataset=self.dataset, idx=self.current_idx)
        if not acked:
            self._set_status("ACK: активных latched-событий нет.")
            return
        self.event_panel.render(
            self.dataset,
            self.current_idx,
            tracker=self.event_tracker,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self._persist_event_log(silent=True)
        self._set_status(f"ACK: подтверждено {len(acked)} latched-событий.")

    def _reset_events_memory(self) -> None:
        if self.dataset is None:
            return
        self.event_tracker.reset_memory(self.dataset, idx=self.current_idx)
        self.event_panel.render(
            self.dataset,
            self.current_idx,
            tracker=self.event_tracker,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self._persist_event_log(silent=True)
        self._set_status("Память событий сброшена к текущему кадру.")

    def _export_event_log(self) -> None:
        path = self._persist_event_log(silent=True)
        if path is None:
            return
        self._set_status(f"Журнал событий экспортирован: {path.name}")

    def _speed_changed(self, index: int) -> None:
        speed = self.speed_combo.itemData(index)
        try:
            self._play_speed = float(speed)
        except Exception:
            self._play_speed = 1.0

    def _on_scrubbed(self, value: int) -> None:
        if self.dataset is None:
            return
        self.current_idx = int(max(0, min(value, self.dataset.time_s.size - 1)))
        self._refresh_frame(push_to_web=True)

    def _advance_playback(self) -> None:
        if not self.playing or self.dataset is None or self.dataset.time_s.size <= 1:
            return
        now = time.perf_counter()
        dt = max(0.0, now - self._last_tick)
        self._last_tick = now
        cur_time = float(self.dataset.time_s[self.current_idx])
        target_time = cur_time + dt * self._play_speed
        if target_time > float(self.dataset.time_s[-1]):
            target_time = float(self.dataset.time_s[0])
        new_idx = int(np.searchsorted(self.dataset.time_s, target_time, side="left"))
        if new_idx >= self.dataset.time_s.size:
            new_idx = 0
        self.current_idx = new_idx
        self._refresh_frame(push_to_web=True)

    def load_dataset(self, npz_path: Path, *, preserve_selection: bool) -> None:
        try:
            old_edge = self.selected_edge if preserve_selection else None
            old_node = self.selected_node if preserve_selection else None
            self.dataset = prepare_dataset(Path(npz_path))
            self.current_idx = min(self.current_idx, max(0, self.dataset.time_s.size - 1))
            self.scrubber.setMaximum(max(0, self.dataset.time_s.size - 1))
            self.selection_panel.set_inventory(self.dataset.edge_names, self.dataset.node_names)

            if old_edge not in self.dataset.edge_names:
                old_edge = self.dataset.edge_names[0] if self.dataset.edge_names else None
            if old_node not in self.dataset.node_names:
                old_node = self.dataset.overlay_node_names[0] if self.dataset.overlay_node_names else (self.dataset.node_names[0] if self.dataset.node_names else None)
            if not preserve_selection:
                focus_target = build_onboarding_focus_target(
                    self.dataset,
                    self.current_idx,
                    selected_edge=old_edge,
                    selected_node=old_node,
                )
                if focus_target.edge_name in self.dataset.edge_names:
                    old_edge = focus_target.edge_name
                if focus_target.node_name in self.dataset.node_names:
                    old_node = focus_target.node_name

            self.selected_edge = old_edge
            self.selected_node = old_node
            self.event_tracker.bind_dataset(self.dataset, idx=self.current_idx)
            self.selection_panel.set_selection(edge_name=self.selected_edge, node_name=self.selected_node)
            self.trends_panel.set_series(self.dataset, edge_name=self.selected_edge, node_name=self.selected_node)
            self.web.render_dataset(self.dataset, selected_edge=self.selected_edge, selected_node=self.selected_node)
            self._apply_current_view_mode(source="dataset_load", auto_focus=not preserve_selection)
            self._refresh_frame(push_to_web=True)
            self._persist_event_log(silent=True)
            self._set_dataset_title()
            self._render_startup_banner()
            self._set_status(f"Загружено: {self.dataset.npz_path.name}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Desktop Mnemo", _friendly_error_text(exc))
            self._set_status(f"Ошибка загрузки: {exc}")

    def _refresh_frame(self, *, push_to_web: bool = False) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        self.current_idx = int(max(0, min(self.current_idx, self.dataset.time_s.size - 1)))
        new_events = self.event_tracker.observe_frame(self.dataset, idx=self.current_idx)
        with QtCore.QSignalBlocker(self.scrubber):
            self.scrubber.setValue(self.current_idx)
        self.time_label.setText(f"t = {float(self.dataset.time_s[self.current_idx]):6.3f} s")
        self.overview_panel.update_frame(self.dataset, self.current_idx, playing=self.playing, follow_enabled=self.follow_enabled)
        self.selection_panel.render_details(self.dataset, self.current_idx, edge_name=self.selected_edge, node_name=self.selected_node)
        self.trends_panel.set_index(self.dataset, self.current_idx)
        self.guide_panel.render(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self.event_panel.render(
            self.dataset,
            self.current_idx,
            tracker=self.event_tracker,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        if self.startup_banner.isVisible() and not self.playing:
            self._render_startup_banner()
        if new_events:
            self._persist_event_log(silent=True)
        if push_to_web:
            self._push_alerts()
            self._push_playhead()

    def _push_playhead(self) -> None:
        if self.dataset is None:
            return
        self.web.set_playhead(self.current_idx, self.playing, self.dataset.dataset_id)

    def _push_alerts(self) -> None:
        alerts = _build_frame_alert_payload(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
        )
        self.web.set_alerts(alerts)

    def _persist_event_log(self, *, silent: bool) -> Path | None:
        path = _write_event_log_sidecar(
            self.dataset,
            self.event_tracker,
            idx=self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            follow_enabled=self.follow_enabled,
            pointer_path=self.pointer_path if self.pointer_path else None,
        )
        self._last_event_log_path = path
        if path is not None and not silent:
            self._set_status(f"Журнал событий: {path.name}")
        return path

    def _select_edge(self, edge_name: str) -> None:
        if not edge_name or self.dataset is None or edge_name not in self.dataset.edge_names:
            return
        self.selected_edge = edge_name
        self._sync_selection_views(clear_focus_region=True)

    def _select_node(self, node_name: str) -> None:
        if not node_name or self.dataset is None or node_name not in self.dataset.node_names:
            return
        self.selected_node = node_name
        self._sync_selection_views(clear_focus_region=True)


def run_app(
    *,
    npz_path: Path | None,
    follow: bool,
    pointer_path: Path,
    theme: str,
    startup_preset: str = "",
    startup_title: str = "",
    startup_reason: str = "",
    startup_view_mode: str = "",
    startup_checklist: list[str] | tuple[str, ...] | None = None,
) -> int:
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication([])
        created = True
    app.setApplicationName("DesktopMnemo")
    app.setOrganizationName("UnifiedPneumoApp")

    window = MnemoMainWindow(
        npz_path=npz_path,
        follow=follow,
        pointer_path=pointer_path,
        theme=theme,
        startup_preset=startup_preset,
        startup_title=startup_title,
        startup_reason=startup_reason,
        startup_view_mode=startup_view_mode,
        startup_checklist=startup_checklist,
    )
    window.show()
    if created:
        return int(app.exec())
    return 0
