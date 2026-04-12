# -*- coding: utf-8 -*-
"""Separate Windows desktop mnemonic viewer for pneumatic runs."""

from __future__ import annotations

import json
import math
import re
import time
import hashlib
from collections import Counter
from datetime import datetime, timezone
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Optional

import numpy as np

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from PySide6 import QtSvg
except Exception:
    QtSvg = None  # type: ignore[assignment]

try:
    import pyqtgraph as pg

    pg.setConfigOptions(antialias=True, foreground="#d9e6ed")
    _HAS_PG = True
except Exception:
    pg = None  # type: ignore[assignment]
    _HAS_PG = False

from pneumo_solver_ui.desktop_animator.data_bundle import DataBundle, load_npz
from pneumo_solver_ui.desktop_animator.ui_state import UiState, default_settings_path
from pneumo_solver_ui.data_contract import read_visual_geometry_meta
from pneumo_solver_ui.ui_svg_flow_helpers import default_svg_pressure_nodes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = PROJECT_ROOT / "pneumo_solver_ui"
SCHEME_JSON_PATH = UI_ROOT / "PNEUMO_SCHEME.json"
CANONICAL_PNEUMO_SCHEME_SVG_PATHS: tuple[Path, ...] = (
    UI_ROOT / "data" / "pneumo_scheme" / "pneumo_scheme.svg",
    UI_ROOT / "assets" / "pneumo_scheme.svg",
)
SOURCE_OF_TRUTH_PNEUMO_IMAGE_PATH = PROJECT_ROOT / "docs" / "PneumoScheme_source_of_truth" / "PneumoScheme_corrected2.png"

VIEWBOX_W = 2200.0
VIEWBOX_H = 1500.0
VIEWBOX = f"0 0 {int(VIEWBOX_W)} {int(VIEWBOX_H)}"
REFERENCE_SCHEME_VIEWBOX_W = 1920.0
REFERENCE_SCHEME_VIEWBOX_H = 1080.0
REFERENCE_SCHEME_SCENE_INSET = (84.0, 150.0, 84.0, 140.0)
PLAYHEAD_STORAGE_KEY = "pneumo_desktop_mnemo_playhead"
EVENT_LOG_SCHEMA_VERSION = "desktop_mnemo_event_log_v1"
CORNER_ORDER: tuple[str, str, str, str] = ("ЛП", "ПП", "ЛЗ", "ПЗ")
DETAIL_MODE_LABELS: dict[str, str] = {
    "quiet": "Тихо",
    "operator": "Оператор",
    "full": "Полно",
}

PRESSURE_HEAT_STOPS: tuple[tuple[float, tuple[int, int, int]], ...] = (
    (0.00, (86, 198, 255)),
    (0.22, (70, 232, 255)),
    (0.54, (72, 255, 190)),
    (0.82, (255, 214, 96)),
    (1.00, (255, 126, 76)),
)
FLOW_FORWARD_RGB = (99, 211, 245)
FLOW_REVERSE_RGB = (240, 147, 107)
FLOW_IDLE_RGB = (77, 106, 118)

REFERENCE_COMPONENT_NODE_ANCHORS_SVG: dict[str, tuple[float, float]] = {
    "Ресивер1": (557.455, 540.0),
    "Ресивер2": (627.585, 540.0),
    "Аккумулятор": (1041.35, 540.0),
    "Ресивер3": (1244.73, 540.0),
}

REFERENCE_INDICATOR_NODE_ANCHORS_SVG: dict[str, tuple[float, float]] = {
    "узел_после_рег_Pmin_питание_Р2": (873.8483, 541.6678),
    "узел_после_рег_заряд_аккумулятора": (1112.2898, 541.6678),
    "узел_после_предохран_Pmax": (1317.8694, 541.6865),
    "узел_после_рег_Pmid": (1285.2229, 510.3164),
    "узел_после_ОК_Pmid": (1373.9732, 485.5826),
    "узел_после_рег_Pmin_сброс": (1285.1964, 573.4269),
    "узел_после_ОК_Pmin": (1373.9732, 597.7904),
}

REFERENCE_CHAMBER_NODE_ANCHORS_SVG: dict[str, tuple[float, float]] = {
    "Ц1_ЛП_БП": (616.6456, 145.1721),
    "Ц1_ЛП_ШП": (616.6456, 369.5877),
    "Ц2_ЛП_БП": (719.6435, 145.1721),
    "Ц2_ЛП_ШП": (719.6435, 369.5877),
    "Ц1_ПП_БП": (1037.4248, 145.1721),
    "Ц1_ПП_ШП": (1037.4248, 313.4838),
    "Ц2_ПП_БП": (1317.9442, 145.1721),
    "Ц2_ПП_ШП": (1317.9442, 313.4838),
    "Ц1_ЛЗ_БП": (616.6456, 706.2111),
    "Ц1_ЛЗ_ШП": (616.6456, 930.6267),
    "Ц2_ЛЗ_БП": (719.6435, 706.2111),
    "Ц2_ЛЗ_ШП": (719.6435, 930.6267),
    "Ц1_ПЗ_БП": (1037.4248, 762.3150),
    "Ц1_ПЗ_ШП": (1037.4248, 930.6267),
    "Ц2_ПЗ_БП": (1317.9442, 762.3150),
    "Ц2_ПЗ_ШП": (1317.9442, 930.6267),
}

REFERENCE_NODE_ANCHORS_SVG: dict[str, tuple[float, float]] = {
    **REFERENCE_COMPONENT_NODE_ANCHORS_SVG,
    **REFERENCE_INDICATOR_NODE_ANCHORS_SVG,
    **REFERENCE_CHAMBER_NODE_ANCHORS_SVG,
}

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
    reference_svg_inline: str
    reference_scheme_source: str
    mapping: dict[str, Any]
    edge_names: list[str]
    node_names: list[str]
    overlay_node_names: list[str]
    edge_series: list[dict[str, Any]]
    node_series: list[dict[str, Any]]
    edge_defs: dict[str, dict[str, Any]]
    canonical_node_names: list[str]
    canonical_edge_names: list[str]
    time_s: np.ndarray
    q_scale: float
    q_unit: str
    p_atm: float
    node_edges: dict[str, list[str]]
    visual_geometry: dict[str, Any]
    geometry_issues: list[str]
    geometry_warnings: list[str]
    scheme_fidelity: dict[str, Any]


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
    startup_time_s: float | None
    startup_time_label: str


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


@dataclass(frozen=True)
class ChamberSnapshot:
    node_name: str
    chamber_key: str
    pressure_bar_g: float | None
    pressure_min_bar_g: float | None
    pressure_max_bar_g: float | None
    volume_l: float | None
    fill_ratio: float | None


@dataclass(frozen=True)
class CylinderSnapshot:
    corner: str
    cyl_index: int
    stroke_m: float | None
    stroke_speed_m_s: float | None
    stroke_ratio: float | None
    stroke_len_m: float | None
    cap: ChamberSnapshot
    rod: ChamberSnapshot
    delta_p_bar: float | None
    motion_label: str
    volume_mode: str
    geometry_ready: bool
    focus_node: str


@dataclass(frozen=True)
class EdgeActivitySnapshot:
    edge_name: str
    component_kind: str
    q_now: float
    direction_label: str
    state_label: str
    zone_label: str
    corners: tuple[str, ...]


def build_launch_onboarding_context(
    *,
    npz_path: Path | None,
    follow: bool,
    pointer_path: Path | None,
    preset_key: str = "",
    title: str = "",
    reason: str = "",
    startup_time_s: float | None = None,
    startup_time_label: str = "",
    checklist: list[str] | tuple[str, ...] | None = None,
) -> LaunchOnboardingContext:
    launch_mode = "follow" if follow else ("npz" if npz_path is not None else "blank")
    normalized_checks = tuple(str(x).strip() for x in (checklist or []) if str(x).strip())
    pointer_name = Path(pointer_path).name if pointer_path else "anim_latest.json"
    npz_name = Path(npz_path).name if npz_path is not None else "NPZ ещё не выбран"
    startup_time_value = float(startup_time_s) if startup_time_s is not None else None
    startup_time_text = str(startup_time_label or "").strip()

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

    if startup_time_value is not None:
        if not startup_time_text:
            startup_time_text = f"{startup_time_value:0.3f} s"
        reason = (
            f"{reason} Стартовый кадр смещён к {startup_time_text}, "
            "чтобы оператор сразу попал в релевантный момент сценария."
        ).strip()
        normalized_checks = (
            f"Сначала проверьте кадр около {startup_time_text} и убедитесь, что режим на схеме совпадает с ожиданием.",
            *normalized_checks,
        )

    context_key = str(preset_key or launch_mode).strip() or launch_mode
    return LaunchOnboardingContext(
        preset_key=context_key,
        title=str(title).strip() or "Стартовый сценарий",
        reason=str(reason).strip() or "",
        checklist=normalized_checks,
        launch_mode=launch_mode,
        startup_time_s=startup_time_value,
        startup_time_label=startup_time_text,
    )


def build_onboarding_focus_target(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None = None,
    selected_node: str | None = None,
    prefer_selected: bool = False,
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
    selected_edge_name = str(selected_edge) if selected_edge in dataset.edge_names else ""
    selected_node_name = str(selected_node) if selected_node in dataset.node_names else ""
    edge_name = narrative.top_edge_name if narrative.top_edge_name in dataset.edge_names else ""
    node_name = narrative.top_node_name if narrative.top_node_name in dataset.node_names else ""
    if prefer_selected:
        edge_name = selected_edge_name or edge_name
        node_name = selected_node_name or node_name
    else:
        edge_name = edge_name or selected_edge_name
        node_name = node_name or selected_node_name

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
    prefer_selected: bool = False,
    source: str = "onboarding",
    auto_focus: bool = False,
) -> dict[str, Any]:
    focus_target = build_onboarding_focus_target(
        dataset,
        idx,
        selected_edge=selected_edge,
        selected_node=selected_node,
        prefer_selected=prefer_selected,
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


def _load_canonical_pneumo_scheme_svg() -> tuple[str, str]:
    for path in CANONICAL_PNEUMO_SCHEME_SVG_PATHS:
        try:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "<svg" in text:
            return text, str(path.resolve())
    return "", ""


def _reference_scheme_scene_rect_tuple() -> tuple[float, float, float, float]:
    left_inset, top_inset, right_inset, bottom_inset = REFERENCE_SCHEME_SCENE_INSET
    bounds_width = VIEWBOX_W - left_inset - right_inset
    bounds_height = VIEWBOX_H - top_inset - bottom_inset
    scale = min(
        bounds_width / max(1.0, REFERENCE_SCHEME_VIEWBOX_W),
        bounds_height / max(1.0, REFERENCE_SCHEME_VIEWBOX_H),
    )
    width = REFERENCE_SCHEME_VIEWBOX_W * scale
    height = REFERENCE_SCHEME_VIEWBOX_H * scale
    left = left_inset + (bounds_width - width) * 0.5
    top = top_inset + (bounds_height - height) * 0.5
    return (left, top, width, height)


def _reference_svg_point_to_scene(x: float, y: float) -> tuple[float, float]:
    left, top, width, height = _reference_scheme_scene_rect_tuple()
    scene_x = left + (float(x) / max(1.0, REFERENCE_SCHEME_VIEWBOX_W)) * width
    scene_y = top + (float(y) / max(1.0, REFERENCE_SCHEME_VIEWBOX_H)) * height
    return (scene_x, scene_y)


def _reference_node_anchor_positions(node_names: list[str]) -> dict[str, tuple[float, float]]:
    node_set = {str(name) for name in node_names if str(name).strip()}
    anchors: dict[str, tuple[float, float]] = {}
    for node_name, svg_point in REFERENCE_NODE_ANCHORS_SVG.items():
        if node_name not in node_set:
            continue
        anchors[node_name] = _reference_svg_point_to_scene(*svg_point)
    return anchors


def _reference_diagonal_geometry_positions(node_names: list[str]) -> dict[str, tuple[float, float]]:
    node_set = {str(name) for name in node_names if str(name).strip()}
    positions: dict[str, tuple[float, float]] = {}
    for node_name in node_set:
        match = DIAGONAL_RE.match(node_name)
        if not match:
            continue
        src_corner = str(match.group("src_corner"))
        src_ch = "БП" if match.group("src_ch") == "CAP" else "ШП"
        dst_corner = str(match.group("dst_corner"))
        dst_ch = "БП" if match.group("dst_ch") == "CAP" else "ШП"
        src_name = f"Ц2_{src_corner}_{src_ch}"
        dst_name = f"Ц2_{dst_corner}_{dst_ch}"
        a = REFERENCE_CHAMBER_NODE_ANCHORS_SVG.get(src_name)
        b = REFERENCE_CHAMBER_NODE_ANCHORS_SVG.get(dst_name)
        if a is None or b is None:
            continue
        offset = 24.0 if match.group("src_ch") == "CAP" else -24.0
        if src_corner in {"ПП", "ПЗ"}:
            offset *= -1.0
        t = 0.35 if str(match.group("stage")) == "междуОКиДР" else 0.68
        positions[node_name] = _reference_svg_point_to_scene(*_offset_point_along_perp(a, b, t, offset))
    return positions


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
            "camozzi_code": str(edge.get("camozzi_код") or edge.get("camozzi_code") or ""),
        }
    return nodes, edge_defs


def _build_node_edges(edge_defs: dict[str, dict[str, Any]], edge_names: list[str]) -> dict[str, list[str]]:
    node_edges: dict[str, list[str]] = {}
    for edge_name in edge_names:
        edge_def = edge_defs.get(edge_name)
        if not edge_def:
            continue
        for node_name in (str(edge_def.get("n1") or ""), str(edge_def.get("n2") or "")):
            if not node_name:
                continue
            node_edges.setdefault(node_name, []).append(edge_name)
    return node_edges


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
    positions.update(_reference_node_anchor_positions(node_names))
    positions.update(_reference_diagonal_geometry_positions(node_names))
    chamber_positions: dict[str, tuple[float, float]] = {}

    for node_name in node_names:
        match = CHAMBER_RE.match(node_name)
        if not match:
            continue
        if node_name in positions:
            chamber_positions[node_name] = positions[node_name]
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


def _mapping_route_issues(mapping: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for edge_name, payload in dict(mapping.get("edges_meta") or {}).items():
        route_name = str(dict(payload or {}).get("mnemo_route") or "")
        if route_name in {"fallback_lane", "missing_endpoint"}:
            issues.append(str(edge_name))
    return sorted(issues)


def _mapping_route_counts(mapping: dict[str, Any]) -> dict[str, int]:
    counts = Counter(str(dict(payload or {}).get("mnemo_route") or "unknown") for payload in dict(mapping.get("edges_meta") or {}).values())
    return {str(name): int(count) for name, count in sorted(counts.items()) if int(count) > 0}


def _build_scheme_fidelity_report(
    *,
    canonical_node_names: list[str],
    edge_defs: dict[str, dict[str, Any]],
    bundle_edge_names: list[str],
    bundle_node_names: list[str],
    node_positions: dict[str, tuple[float, float]],
    bundle_mapping: dict[str, Any],
) -> dict[str, Any]:
    canonical_nodes = [str(name) for name in canonical_node_names if str(name).strip()]
    canonical_edge_names = [str(name) for name in edge_defs.keys() if str(name).strip()]
    canonical_node_set = set(canonical_nodes)
    canonical_edge_set = set(canonical_edge_names)
    canonical_mapping = _build_mapping(canonical_edge_names, canonical_nodes, edge_defs, node_positions)
    canonical_missing_nodes = sorted(name for name in canonical_nodes if name not in node_positions)
    canonical_route_issues = _mapping_route_issues(canonical_mapping)
    bundle_route_issues = _mapping_route_issues(bundle_mapping)
    bundle_extra_edges = sorted(name for name in bundle_edge_names if name not in canonical_edge_set)
    bundle_extra_nodes = sorted(name for name in bundle_node_names if name not in canonical_node_set)
    bundle_known_edges = [name for name in bundle_edge_names if name in canonical_edge_set]
    bundle_known_nodes = [name for name in bundle_node_names if name in canonical_node_set]
    canonical_nodes_positioned = len(canonical_nodes) - len(canonical_missing_nodes)
    canonical_edges_routed = len(canonical_edge_names) - len(canonical_route_issues)
    status = "ok"
    if canonical_missing_nodes or canonical_route_issues or bundle_route_issues or bundle_extra_edges:
        status = "warn"
    elif bundle_extra_nodes:
        status = "attention"
    summary = (
        f"Canonical-схема покрыта нативной мнемосхемой: {canonical_nodes_positioned}/{len(canonical_nodes)} узлов размещены, "
        f"{canonical_edges_routed}/{len(canonical_edge_names)} ветвей маршрутизированы без fallback."
    )
    bundle_summary = (
        f"Текущий bundle распознан по canonical-словарю: {len(bundle_known_edges)}/{len(bundle_edge_names)} ветвей и "
        f"{len(bundle_known_nodes)}/{len(bundle_node_names)} pressure-узлов."
    )
    if bundle_extra_edges:
        bundle_summary += f" Вне canonical осталось {len(bundle_extra_edges)} ветвей."
    elif bundle_extra_nodes:
        bundle_summary += f" Вне canonical осталось {len(bundle_extra_nodes)} узлов."
    return {
        "status": status,
        "summary": summary,
        "bundle_summary": bundle_summary,
        "canonical_nodes_total": len(canonical_nodes),
        "canonical_nodes_positioned": canonical_nodes_positioned,
        "canonical_edges_total": len(canonical_edge_names),
        "canonical_edges_routed": canonical_edges_routed,
        "canonical_missing_nodes": canonical_missing_nodes,
        "canonical_route_issues": canonical_route_issues,
        "bundle_edges_total": len(bundle_edge_names),
        "bundle_edges_known": len(bundle_known_edges),
        "bundle_nodes_total": len(bundle_node_names),
        "bundle_nodes_known": len(bundle_known_nodes),
        "bundle_extra_edges": bundle_extra_edges,
        "bundle_extra_nodes": bundle_extra_nodes,
        "bundle_route_issues": bundle_route_issues,
        "canonical_route_counts": _mapping_route_counts(canonical_mapping),
        "bundle_route_counts": _mapping_route_counts(bundle_mapping),
    }


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


def _node_pressure_for_index(dataset: MnemoDataset | None, node_name: str, idx: int) -> float | None:
    if dataset is None or dataset.bundle.p is None or not node_name:
        return None
    p_arr = dataset.bundle.p.column(node_name, default=None)
    if p_arr is None:
        return None
    p_vals = _bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)
    if p_vals.size == 0:
        return None
    clamped = max(0, min(int(idx), p_vals.size - 1))
    return _finite_or_none(p_vals[clamped])


def _node_pressure_series_bar_g(dataset: MnemoDataset | None, node_name: str) -> np.ndarray | None:
    if dataset is None or dataset.bundle.p is None or not node_name:
        return None
    p_arr = dataset.bundle.p.column(node_name, default=None)
    if p_arr is None:
        return None
    p_vals = _bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)
    if p_vals.size == 0:
        return None
    return np.asarray(p_vals, dtype=float)


def _edge_flow_series_scaled(dataset: MnemoDataset | None, edge_name: str) -> np.ndarray | None:
    if dataset is None or dataset.bundle.q is None or not edge_name:
        return None
    q_arr = dataset.bundle.q.column(edge_name, default=None)
    if q_arr is None:
        return None
    q_vals = np.asarray(q_arr, dtype=float) * float(dataset.q_scale)
    if q_vals.size == 0:
        return None
    return np.asarray(q_vals, dtype=float)


def _edge_open_series(dataset: MnemoDataset | None, edge_name: str) -> np.ndarray | None:
    if dataset is None or dataset.bundle.open is None or not edge_name:
        return None
    open_arr = dataset.bundle.open.column(edge_name, default=None)
    if open_arr is None:
        return None
    values = np.asarray(open_arr, dtype=int)
    if values.size == 0:
        return None
    return values.reshape(-1)


def _route_pressure_strip_trend_meta(
    *,
    time_s: np.ndarray | list[float],
    p1_values: np.ndarray | list[float] | None,
    p2_values: np.ndarray | list[float] | None,
    idx: int,
    max_points: int = 6,
) -> dict[str, Any]:
    pressure_meta = _edge_recent_pressure_meta(
        time_s=time_s,
        p1_values=p1_values,
        p2_values=p2_values,
        idx=idx,
        max_points=max_points,
    )
    if not bool(pressure_meta.get("pressure_history_available")):
        return {
            "trend_available": False,
            "trend_status": "ΔP без истории",
            "trend_badge": "ΔP?",
            "trend_tone": "neutral",
            "trend_summary": "Нужны хотя бы два соседних кадра давления.",
        }

    p1_arr = np.asarray(p1_values, dtype=float).reshape(-1)
    p2_arr = np.asarray(p2_values, dtype=float).reshape(-1)
    sample_count = min(p1_arr.size, p2_arr.size)
    if sample_count <= 0:
        return {
            "trend_available": False,
            "trend_status": "ΔP без истории",
            "trend_badge": "ΔP?",
            "trend_tone": "neutral",
            "trend_summary": "Нужны хотя бы два соседних кадра давления.",
        }

    delta_arr = (p1_arr[:sample_count] - p2_arr[:sample_count]).astype(float)
    clamped_idx = int(max(0, min(idx, sample_count - 1)))
    start_idx = max(0, clamped_idx - max(2, int(max_points)) + 1)
    recent_delta = delta_arr[start_idx : clamped_idx + 1]
    last_delta = float(recent_delta[-1]) if recent_delta.size else 0.0
    prev_delta = float(recent_delta[-2]) if recent_delta.size >= 2 else float(last_delta)
    peak_abs = float(np.max(np.abs(recent_delta))) if recent_delta.size else 0.0
    delta_step = float(last_delta - prev_delta)
    step_floor = max(0.006, peak_abs * 0.005)
    near_zero_floor = max(0.05, peak_abs * 0.12)
    sign_changes = sum(
        1
        for prev, nxt in zip(recent_delta[:-1], recent_delta[1:])
        if abs(float(prev)) > near_zero_floor
        and abs(float(nxt)) > near_zero_floor
        and math.copysign(1.0, float(prev)) != math.copysign(1.0, float(nxt))
    )

    if peak_abs <= 0.05:
        status = "ΔP выровнен"
        badge = "ΔP≈"
        tone = "neutral"
    elif sign_changes >= 1:
        status = "ΔP сменил знак"
        badge = "ΔP↕"
        tone = "warn"
    elif abs(last_delta) <= near_zero_floor and abs(prev_delta) > abs(last_delta) and delta_step < -step_floor:
        status = "ΔP выравнивается"
        badge = "ΔP≈"
        tone = "info"
    elif delta_step > step_floor:
        status = "ΔP нарастает"
        badge = "ΔP↑"
        tone = "info"
    elif delta_step < -step_floor:
        status = "ΔP спадает"
        badge = "ΔP↓"
        tone = "info"
    else:
        status = "ΔP удерживается"
        badge = "ΔP="
        tone = "ok"

    span_s = float(pressure_meta.get("pressure_history_span_s") or 0.0)
    return {
        "trend_available": True,
        "trend_status": status,
        "trend_badge": badge,
        "trend_tone": tone,
        "trend_last_delta": last_delta,
        "trend_prev_delta": prev_delta,
        "trend_summary": f"{status} • {span_s:0.2f} s • текущее {last_delta:+0.2f} бар",
    }


def _route_pressure_strip_flow_meta(
    *,
    time_s: np.ndarray | list[float],
    q_values: np.ndarray | list[float] | None,
    open_values: np.ndarray | list[int] | None,
    idx: int,
    q_unit: str,
    max_points: int = 6,
) -> dict[str, Any]:
    if q_values is None:
        return {
            "q_available": False,
            "q_status": "Q без истории",
            "q_badge": "Q?",
            "q_tone": "neutral",
            "q_summary": "Нужны хотя бы два соседних кадра расхода.",
        }

    q_arr = np.asarray(q_values, dtype=float).reshape(-1)
    if q_arr.size <= 1:
        return {
            "q_available": False,
            "q_status": "Q без истории",
            "q_badge": "Q?",
            "q_tone": "neutral",
            "q_summary": "Нужны хотя бы два соседних кадра расхода.",
        }

    t_arr = np.asarray(time_s, dtype=float).reshape(-1)
    if t_arr.size != q_arr.size:
        t_arr = np.arange(q_arr.size, dtype=float)

    clamped_idx = int(max(0, min(idx, q_arr.size - 1, t_arr.size - 1)))
    start_idx = max(0, clamped_idx - max(2, int(max_points)) + 1)
    recent_q = q_arr[start_idx : clamped_idx + 1]
    recent_t = t_arr[start_idx : clamped_idx + 1]
    recent_open = None
    if open_values is not None:
        open_arr = np.asarray(open_values, dtype=int).reshape(-1)
        if open_arr.size:
            recent_open = open_arr[start_idx : min(clamped_idx + 1, open_arr.size)]

    if recent_q.size <= 1:
        return {
            "q_available": False,
            "q_status": "Q без истории",
            "q_badge": "Q?",
            "q_tone": "neutral",
            "q_summary": "Нужны хотя бы два соседних кадра расхода.",
        }

    q_now = float(recent_q[-1])
    q_prev = float(recent_q[-2])
    peak_abs = float(np.max(np.abs(q_arr))) if q_arr.size else 0.0
    active_floor = max(1.0e-6, peak_abs * 0.08)
    change_floor = max(active_floor * 0.35, peak_abs * 0.12)
    delta_abs = abs(q_now) - abs(q_prev)
    active_signs = [int(np.sign(val)) for val in recent_q if abs(float(val)) > active_floor]
    sign_changes = sum(1 for prev, nxt in zip(active_signs[:-1], active_signs[1:]) if prev != nxt)
    open_changed = bool(
        recent_open is not None
        and recent_open.size >= 2
        and np.any(recent_open[1:] != recent_open[:-1])
    )
    span_s = float(recent_t[-1] - recent_t[0]) if recent_t.size >= 2 else 0.0

    if peak_abs <= active_floor and abs(q_now) <= active_floor:
        status = "Q спокоен"
        badge = "Q≈"
        tone = "neutral"
    elif sign_changes >= 1 and abs(q_now) > active_floor:
        status = "Q сменил знак"
        badge = "Q↕"
        tone = "warn"
    elif open_changed and abs(q_now) > active_floor and delta_abs > (change_floor * 0.5):
        status = "Q после переключения"
        badge = "Q⇢"
        tone = "info"
    elif delta_abs > change_floor:
        status = "Q нарастает"
        badge = "Q↑"
        tone = "info"
    elif delta_abs < -change_floor:
        status = "Q спадает"
        badge = "Q↓"
        tone = "info"
    elif abs(q_now) > active_floor:
        status = "Q удерживается"
        badge = "Q="
        tone = "ok"
    else:
        status = "Q затихает"
        badge = "Q≈"
        tone = "neutral"

    return {
        "q_available": True,
        "q_status": status,
        "q_badge": badge,
        "q_tone": tone,
        "q_summary": f"{status} • {span_s:0.2f} s • текущее {q_now:+0.1f} {q_unit}",
        "q_now": q_now,
        "q_prev": q_prev,
    }


def _route_pressure_strip_history_meta(
    *,
    time_s: np.ndarray | list[float],
    q_values: np.ndarray | list[float] | None,
    open_values: np.ndarray | list[int] | None,
    idx: int,
    q_unit: str,
    max_points: int = 6,
) -> dict[str, Any]:
    if q_values is None:
        return {
            "q_history_available": False,
            "q_history_summary": "история расхода ещё не накоплена",
            "q_history_points": [],
            "q_history_open_blocks": [],
            "q_history_span_s": 0.0,
            "q_history_peak_abs": 0.0,
            "q_history_zero_y": 0.5,
        }

    history_meta = _edge_recent_history_meta(
        time_s=time_s,
        q_values=q_values,
        open_values=open_values,
        idx=idx,
        max_points=max_points,
    )
    return {
        "q_history_available": bool(history_meta.get("history_available")),
        "q_history_summary": _edge_recent_history_summary(history_meta, q_unit),
        "q_history_points": list(history_meta.get("history_points") or []),
        "q_history_open_blocks": list(history_meta.get("history_open_blocks") or []),
        "q_history_span_s": float(history_meta.get("history_span_s") or 0.0),
        "q_history_peak_abs": float(history_meta.get("history_peak_abs") or 0.0),
        "q_history_zero_y": float(history_meta.get("history_zero_y") or 0.5),
    }


def _route_pressure_strip_cause_effect_meta(
    *,
    trend_meta: dict[str, Any],
    flow_meta: dict[str, Any],
) -> dict[str, Any]:
    trend_available = bool(trend_meta.get("trend_available"))
    q_available = bool(flow_meta.get("q_available"))
    if not trend_available or not q_available:
        return {
            "cause_effect_available": False,
            "cause_effect_status": "Связка ΔP→Q не определена",
            "cause_effect_badge": "ΔP→Q ?",
            "cause_effect_tone": "neutral",
            "cause_effect_summary": "Недостаточно истории, чтобы сопоставить перепад и расход.",
        }

    trend_status = str(trend_meta.get("trend_status") or "")
    q_status = str(flow_meta.get("q_status") or "")

    trend_rising = trend_status in {"ΔP нарастает", "ΔP удерживается"}
    trend_falling = trend_status in {"ΔP спадает", "ΔP выравнивается", "ΔP выровнен"}
    trend_flip = trend_status == "ΔP сменил знак"
    q_rising = q_status in {"Q нарастает", "Q после переключения"}
    q_active = q_status in {"Q нарастает", "Q после переключения", "Q удерживается"}
    q_falling = q_status in {"Q спадает", "Q затихает", "Q спокоен"}
    q_flip = q_status == "Q сменил знак"

    if trend_flip or q_flip:
        status = "Q спорит с ΔP"
        badge = "ΔP↔Q"
        tone = "warn"
    elif trend_rising and q_rising:
        status = "Q догоняет ΔP"
        badge = "ΔP→Q ok"
        tone = "ok"
    elif trend_rising and q_active:
        status = "Q держится на ΔP"
        badge = "ΔP→Q hold"
        tone = "ok"
    elif trend_rising:
        status = "Q запаздывает за ΔP"
        badge = "ΔP→Q lag"
        tone = "warn"
    elif trend_falling and q_falling:
        status = "Q гаснет вместе с ΔP"
        badge = "ΔP→Q soft"
        tone = "info"
    elif trend_falling and q_active:
        status = "Q тянется после ΔP"
        badge = "ΔP→Q tail"
        tone = "warn"
    else:
        status = "Q спокоен при ровном ΔP"
        badge = "ΔP→Q idle"
        tone = "neutral"

    return {
        "cause_effect_available": True,
        "cause_effect_status": status,
        "cause_effect_badge": badge,
        "cause_effect_tone": tone,
        "cause_effect_summary": f"{status} • {trend_status} / {q_status}",
    }


def _route_pressure_strip_intermediate_nodes_meta(
    dataset: MnemoDataset | None,
    diagnostics: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    *,
    idx: int,
) -> list[dict[str, Any]]:
    if dataset is None or payload is None:
        return []

    item = dict(payload or {})
    edge_name = str(item.get("edge_name") or "")
    role = str(item.get("role") or "")
    start_node = str(item.get("start_node") or "")
    end_node = str(item.get("end_node") or "")
    terminal_meta = _route_pressure_strip_terminal_meta(item)
    leading_node_name = str(terminal_meta.get("leading_node") or "")
    leading_pressure_bar_g = _node_pressure_for_index(dataset, leading_node_name, idx) if leading_node_name else None
    endpoint_names = {name for name in [start_node, end_node] if name}
    if not edge_name:
        return []

    rows: list[dict[str, Any]] = []
    seen = set(endpoint_names)

    def _badge_for_node(node_name: str) -> str:
        kind = _node_kind(node_name)
        if kind == "regulator":
            return "REG"
        if kind == "diagonal":
            return "MID"
        if kind == "chamber":
            match = CHAMBER_RE.match(node_name)
            if match:
                return _chamber_short(str(match.group("ch")))
            return "CAM"
        if kind == "mainline":
            return "MAG"
        if kind == "receiver":
            return "RES"
        if kind == "accumulator":
            return "ACC"
        return "MID"

    def _tone_for_kind(kind: str) -> str:
        if kind == "regulator":
            return "info"
        if kind == "diagonal":
            return "ok"
        if kind == "chamber":
            return "neutral"
        return "neutral"

    def _role_label(kind: str, source: str) -> str:
        if kind == "regulator":
            return "Регуляторный узел"
        if kind == "diagonal":
            return "Узел диагонали"
        if kind == "chamber":
            return "Камерный узел"
        if kind == "mainline":
            return "Магистральный узел"
        if kind == "receiver":
            return "Ресиверный узел"
        if kind == "accumulator":
            return "Аккумуляторный узел"
        return "Промежуточный узел" if source == "adjacent" else "Узел маршрута"

    def _lead_hint_text(pressure_bar_g: float | None) -> str:
        if pressure_bar_g is None or leading_pressure_bar_g is None or not leading_node_name:
            return "Δ к ведущему: —"
        delta = float(pressure_bar_g) - float(leading_pressure_bar_g)
        if abs(delta) <= 0.08:
            return "Почти как ведущий конец"
        if delta < 0.0:
            return f"Ниже ведущего на {abs(delta):0.2f} бар"
        return f"Выше ведущего на {abs(delta):0.2f} бар"

    def _lead_trend_text(node_name: str) -> str:
        if not leading_node_name:
            return "Ход к ведущему: —"
        node_series = _node_pressure_series_bar_g(dataset, node_name)
        lead_series = _node_pressure_series_bar_g(dataset, leading_node_name)
        if node_series is None or lead_series is None:
            return "Ход к ведущему: —"
        sample_count = min(int(node_series.size), int(lead_series.size))
        if sample_count <= 1:
            return "Ход к ведущему: —"
        clamped_idx = int(max(0, min(idx, sample_count - 1)))
        if clamped_idx <= 0:
            return "Ход к ведущему: —"
        delta_now = float(node_series[clamped_idx] - lead_series[clamped_idx])
        delta_prev = float(node_series[clamped_idx - 1] - lead_series[clamped_idx - 1])
        abs_now = abs(delta_now)
        abs_prev = abs(delta_prev)
        spread_floor = max(0.01, max(abs_now, abs_prev) * 0.03)
        if abs_now <= 0.08 and abs_prev > abs_now + spread_floor * 0.5:
            return "Идёт к выравниванию"
        if math.copysign(1.0, delta_now) != math.copysign(1.0, delta_prev) and abs_prev > 0.08 and abs_now > 0.08:
            return "Переходит через уровень ведущего"
        if abs_now < abs_prev - spread_floor:
            return "Сближается с ведущим"
        if abs_now > abs_prev + spread_floor:
            return "Уходит от ведущего"
        return "Держит разброс к ведущему"

    def _add_node(node_name: str, source: str) -> None:
        name = str(node_name or "")
        if not name or name in seen or name not in dataset.node_names:
            return
        seen.add(name)
        kind = _node_kind(name)
        pressure_bar_g = _node_pressure_for_index(dataset, name, idx)
        role_label = _role_label(kind, source)
        pressure_label = f"{float(pressure_bar_g):0.2f} бар(g)" if pressure_bar_g is not None else "давление —"
        lead_hint = _lead_hint_text(pressure_bar_g)
        lead_trend = _lead_trend_text(name)
        rows.append(
            {
                "name": name,
                "label": _short_node_label(name),
                "kind": kind,
                "badge_text": _badge_for_node(name),
                "tone": _tone_for_kind(kind),
                "pressure_bar_g": pressure_bar_g,
                "role_label": role_label,
                "summary_text": f"{role_label} • {pressure_label}",
                "lead_hint_text": lead_hint,
                "lead_trend_text": lead_trend,
                "source": source,
            }
        )

    allowed_kinds: set[str] = set()
    if role == "regulator":
        allowed_kinds = {"regulator"}
    elif role == "diagonal":
        allowed_kinds = {"diagonal", "chamber"}
    elif role == "supply":
        allowed_kinds = {"mainline", "receiver", "accumulator", "regulator"}

    if role == "diagonal":
        diagonal_focus = dict((diagnostics or {}).get("diagonal_focus") or {})
        for node_item in list(diagonal_focus.get("nodes") or []):
            row = dict(node_item or {})
            node_name = str(row.get("name") or "")
            edge_names = {str(name) for name in list(row.get("edge_names") or []) if str(name)}
            if edge_name in edge_names:
                _add_node(node_name, "diagonal_focus")

    frontier = [name for name in [start_node, end_node] if name]
    visited = set(frontier)
    for _depth in range(2):
        next_frontier: list[str] = []
        for seed_node in frontier:
            for neighbor_edge in list(dataset.node_edges.get(seed_node) or []):
                edge_def = dict(dataset.edge_defs.get(str(neighbor_edge)) or {})
                for neighbor_node in [str(edge_def.get("n1") or ""), str(edge_def.get("n2") or "")]:
                    if not neighbor_node or neighbor_node in visited:
                        continue
                    visited.add(neighbor_node)
                    kind = _node_kind(neighbor_node)
                    if kind in allowed_kinds:
                        _add_node(neighbor_node, "adjacent")
                    if kind in allowed_kinds or kind == "other":
                        next_frontier.append(neighbor_node)
        frontier = next_frontier

    rows.sort(
        key=lambda row: (
            0 if str(row.get("source") or "") == "diagonal_focus" else 1,
            0 if str(row.get("kind") or "") == "regulator" else 1,
            str(row.get("name") or ""),
        )
    )
    return rows[:3]


def _build_active_diagonal_focus_meta(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
) -> dict[str, Any]:
    if dataset is None or dataset.time_s.size == 0:
        return {"edges": [], "nodes": [], "node_names": []}

    edge_rows = _edge_rows_for_index(dataset, idx)
    if not edge_rows:
        return {"edges": [], "nodes": [], "node_names": []}

    selected_edge_name = str(selected_edge or "") if selected_edge in dataset.edge_names else ""
    top_abs_flow = abs(float(edge_rows[0][1])) if edge_rows else 0.0
    activation_threshold = max(6.0, top_abs_flow * 0.24)

    edge_items: list[dict[str, Any]] = []
    node_bucket: dict[str, dict[str, Any]] = {}

    for rank, (edge_name, q_now) in enumerate(edge_rows[:12], start=1):
        edge_def = dict(dataset.edge_defs.get(edge_name) or {})
        endpoints = [str(edge_def.get("n1") or ""), str(edge_def.get("n2") or "")]
        focus_nodes = [name for name in endpoints if DIAGONAL_RE.match(name) or CHAMBER_RE.match(name)]
        role = _edge_role(edge_name, edge_def)
        if role != "diagonal" and not focus_nodes:
            continue
        if edge_name != selected_edge_name and abs(float(q_now)) < activation_threshold:
            continue

        pressure_pairs = [(name, _node_pressure_for_index(dataset, name, idx)) for name in focus_nodes]
        known_pressures = [float(value) for _, value in pressure_pairs if value is not None]
        pressure_span = max(known_pressures) - min(known_pressures) if len(known_pressures) >= 2 else None
        severity = "focus" if edge_name == selected_edge_name or rank == 1 else "attention"
        if severity != "focus" and pressure_span is not None and pressure_span >= 1.2:
            severity = "warn"

        edge_items.append(
            {
                "name": edge_name,
                "flow": float(q_now),
                "severity": severity,
                "node_names": focus_nodes,
                "pressure_span_bar": pressure_span,
                "label": "Активная диагональ" if edge_name != selected_edge_name else "Выбранная диагональ",
                "summary": (
                    f"{edge_name}: |Q|={abs(float(q_now)):4.1f} {dataset.q_unit}"
                    + (
                        f", ΔP по узлам {pressure_span:4.2f} бар(g)."
                        if pressure_span is not None
                        else "."
                    )
                ),
            }
        )

        for node_name, pressure in pressure_pairs:
            if not node_name:
                continue
            item = node_bucket.setdefault(
                node_name,
                {
                    "name": node_name,
                    "severity": severity,
                    "pressure_bar_g": pressure,
                    "max_abs_flow": abs(float(q_now)),
                    "edge_names": [],
                    "label": "Узел диагонали" if DIAGONAL_RE.match(node_name) else "Порт диагонали",
                    "summary": "Участвует в активной диагональной связи.",
                },
            )
            if _severity_rank(severity) > _severity_rank(str(item.get("severity") or "")):
                item["severity"] = severity
            if pressure is not None and item.get("pressure_bar_g") is None:
                item["pressure_bar_g"] = pressure
            item["max_abs_flow"] = max(float(item.get("max_abs_flow") or 0.0), abs(float(q_now)))
            item.setdefault("edge_names", []).append(edge_name)

    node_items = sorted(
        node_bucket.values(),
        key=lambda item: (
            -_severity_rank(str(item.get("severity") or "")),
            -float(item.get("max_abs_flow") or 0.0),
            str(item.get("name") or ""),
        ),
    )
    for item in node_items:
        item["edge_names"] = sorted({str(name) for name in list(item.get("edge_names") or []) if str(name)})
        item["short_label"] = _short_node_label(str(item.get("name") or ""))
    return {
        "edges": edge_items[:4],
        "nodes": node_items[:6],
        "node_names": [str(item.get("name") or "") for item in node_items[:6] if str(item.get("name") or "")],
        "selected_edge": selected_edge_name,
        "activation_threshold": float(activation_threshold),
    }


def _build_route_pressure_strip_payloads(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
) -> list[dict[str, Any]]:
    if dataset is None or dataset.time_s.size == 0:
        return []

    edge_rows = _edge_rows_for_index(dataset, idx)
    if not edge_rows:
        return []

    payloads: list[dict[str, Any]] = []
    selected_edge_name = str(selected_edge or "") if selected_edge in dataset.edge_names else ""
    top_abs_flow = abs(float(edge_rows[0][1])) if edge_rows else 0.0
    activation_threshold = max(6.0, top_abs_flow * 0.18)

    for rank, (edge_name, q_now) in enumerate(edge_rows[:18], start=1):
        edge_name = str(edge_name or "")
        if not edge_name:
            continue
        edge_def = dict(dataset.edge_defs.get(edge_name) or {})
        role = _edge_role(edge_name, edge_def)
        if role not in {"diagonal", "regulator", "supply"}:
            continue
        if edge_name != selected_edge_name and abs(float(q_now)) < activation_threshold:
            continue

        node_1 = str(edge_def.get("n1") or "")
        node_2 = str(edge_def.get("n2") or "")
        if not node_1 and not node_2:
            continue

        p1_bar_g = _node_pressure_for_index(dataset, node_1, idx) if node_1 else None
        p2_bar_g = _node_pressure_for_index(dataset, node_2, idx) if node_2 else None
        if p1_bar_g is None and p2_bar_g is None:
            continue
        p1_series_bar_g = _node_pressure_series_bar_g(dataset, node_1) if node_1 else None
        p2_series_bar_g = _node_pressure_series_bar_g(dataset, node_2) if node_2 else None
        q_series = _edge_flow_series_scaled(dataset, edge_name)
        open_series = _edge_open_series(dataset, edge_name)

        delta_p_bar = None
        if p1_bar_g is not None and p2_bar_g is not None:
            delta_p_bar = abs(float(p1_bar_g) - float(p2_bar_g))
        trend_meta = _route_pressure_strip_trend_meta(
            time_s=dataset.time_s,
            p1_values=p1_series_bar_g,
            p2_values=p2_series_bar_g,
            idx=idx,
        )
        flow_meta = _route_pressure_strip_flow_meta(
            time_s=dataset.time_s,
            q_values=q_series,
            open_values=open_series,
            idx=idx,
            q_unit=dataset.q_unit,
        )
        history_meta = _route_pressure_strip_history_meta(
            time_s=dataset.time_s,
            q_values=q_series,
            open_values=open_series,
            idx=idx,
            q_unit=dataset.q_unit,
        )
        cause_effect_meta = _route_pressure_strip_cause_effect_meta(
            trend_meta=trend_meta,
            flow_meta=flow_meta,
        )

        severity = "focus" if edge_name == selected_edge_name or rank == 1 else "attention"
        if severity != "focus" and delta_p_bar is not None and delta_p_bar >= (1.0 if role == "diagonal" else 1.4):
            severity = "warn"
        role_label = {
            "diagonal": "диагонали",
            "regulator": "регулятора",
            "supply": "питания",
        }.get(role, "ветви")
        payloads.append(
            {
                "edge_name": edge_name,
                "role": role,
                "severity": severity,
                "order": int(len(payloads)),
                "selected": edge_name == selected_edge_name,
                "node_names": [node_1, node_2],
                "start_node": node_1,
                "end_node": node_2,
                "start_label": _short_node_label(node_1),
                "end_label": _short_node_label(node_2),
                "p1_bar_g": _finite_or_none(p1_bar_g),
                "p2_bar_g": _finite_or_none(p2_bar_g),
                "delta_p_bar": _finite_or_none(delta_p_bar),
                "flow": _finite_or_none(q_now),
                "label": f"ΔP фокус-{role_label}" if edge_name == selected_edge_name else f"ΔP {role_label}",
                "pressure_label": (
                    f"{float(p1_bar_g):0.2f} → {float(p2_bar_g):0.2f} бар(g)"
                    if p1_bar_g is not None and p2_bar_g is not None
                    else (
                        f"{float(p1_bar_g):0.2f} бар(g)"
                        if p1_bar_g is not None
                        else f"{float(p2_bar_g):0.2f} бар(g)"
                    )
                ),
                "delta_label": f"ΔP {float(delta_p_bar):0.2f}" if delta_p_bar is not None else "ΔP —",
                "summary": (
                    f"{_short_node_label(node_1)} → {_short_node_label(node_2)}"
                    + (
                        f" • {float(p1_bar_g):0.2f} → {float(p2_bar_g):0.2f} бар(g)"
                        if p1_bar_g is not None and p2_bar_g is not None
                        else ""
                    )
                )
                + f" • роль {role_label}",
                "trend_status": str(trend_meta.get("trend_status") or ""),
                "trend_badge": str(trend_meta.get("trend_badge") or ""),
                "trend_tone": str(trend_meta.get("trend_tone") or "neutral"),
                "trend_summary": str(trend_meta.get("trend_summary") or ""),
                "q_status": str(flow_meta.get("q_status") or ""),
                "q_badge": str(flow_meta.get("q_badge") or ""),
                "q_tone": str(flow_meta.get("q_tone") or "neutral"),
                "q_summary": str(flow_meta.get("q_summary") or ""),
                "q_history_available": bool(history_meta.get("q_history_available")),
                "q_history_summary": str(history_meta.get("q_history_summary") or ""),
                "q_history_points": list(history_meta.get("q_history_points") or []),
                "q_history_open_blocks": list(history_meta.get("q_history_open_blocks") or []),
                "q_history_span_s": float(history_meta.get("q_history_span_s") or 0.0),
                "q_history_peak_abs": float(history_meta.get("q_history_peak_abs") or 0.0),
                "q_history_zero_y": float(history_meta.get("q_history_zero_y") or 0.5),
                "cause_effect_status": str(cause_effect_meta.get("cause_effect_status") or ""),
                "cause_effect_badge": str(cause_effect_meta.get("cause_effect_badge") or ""),
                "cause_effect_tone": str(cause_effect_meta.get("cause_effect_tone") or "neutral"),
                "cause_effect_summary": str(cause_effect_meta.get("cause_effect_summary") or ""),
            }
        )

    payloads.sort(
        key=lambda payload: (
            -_severity_rank(str(payload.get("severity") or "")),
            0 if bool(payload.get("selected")) else 1,
            -abs(float(payload.get("flow") or 0.0)),
            str(payload.get("edge_name") or ""),
        )
    )
    return payloads[:6]


def _route_pressure_strip_terminal_meta(payload: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(payload or {})
    start_node = str(item.get("start_node") or "")
    end_node = str(item.get("end_node") or "")
    start_label = str(item.get("start_label") or _short_node_label(start_node))
    end_label = str(item.get("end_label") or _short_node_label(end_node))
    p1_bar_g = _finite_or_none(item.get("p1_bar_g"))
    p2_bar_g = _finite_or_none(item.get("p2_bar_g"))
    equalized = False
    leading_node = ""
    leading_label = ""
    trailing_node = ""
    trailing_label = ""
    start_badge = "P?"
    end_badge = "P?"
    leader_summary = "Ведущий конец не определён"
    tone = str(item.get("severity") or "info")

    if p1_bar_g is not None and p2_bar_g is not None:
        delta = float(p1_bar_g) - float(p2_bar_g)
        if abs(delta) <= 0.12:
            equalized = True
            start_badge = "P≈"
            end_badge = "P≈"
            leader_summary = "Давления почти выровнены"
            tone = "info" if tone not in {"focus", "warn"} else tone
        elif delta > 0.0:
            leading_node = start_node
            leading_label = start_label
            trailing_node = end_node
            trailing_label = end_label
            start_badge = "P+"
            end_badge = "P-"
            leader_summary = f"Ведёт: {start_label}"
        else:
            leading_node = end_node
            leading_label = end_label
            trailing_node = start_node
            trailing_label = start_label
            start_badge = "P-"
            end_badge = "P+"
            leader_summary = f"Ведёт: {end_label}"
    elif p1_bar_g is not None:
        leading_node = start_node
        leading_label = start_label
        start_badge = "P"
        end_badge = "P?"
        leader_summary = f"Опорный конец: {start_label}"
    elif p2_bar_g is not None:
        leading_node = end_node
        leading_label = end_label
        start_badge = "P?"
        end_badge = "P"
        leader_summary = f"Опорный конец: {end_label}"

    return {
        "edge_name": str(item.get("edge_name") or ""),
        "role": str(item.get("role") or ""),
        "severity": tone,
        "selected": bool(item.get("selected")),
        "equalized": bool(equalized),
        "leading_node": leading_node,
        "leading_label": leading_label,
        "trailing_node": trailing_node,
        "trailing_label": trailing_label,
        "leader_summary": leader_summary,
        "start_node": start_node,
        "end_node": end_node,
        "start_label": start_label,
        "end_label": end_label,
        "start_badge": start_badge,
        "end_badge": end_badge,
        "start_pressure_label": f"{float(p1_bar_g):0.2f} бар(g)" if p1_bar_g is not None else "—",
        "end_pressure_label": f"{float(p2_bar_g):0.2f} бар(g)" if p2_bar_g is not None else "—",
        "trend_status": str(item.get("trend_status") or ""),
        "trend_badge": str(item.get("trend_badge") or ""),
        "trend_tone": str(item.get("trend_tone") or "neutral"),
        "trend_summary": str(item.get("trend_summary") or ""),
        "q_status": str(item.get("q_status") or ""),
        "q_badge": str(item.get("q_badge") or ""),
        "q_tone": str(item.get("q_tone") or "neutral"),
        "q_summary": str(item.get("q_summary") or ""),
        "q_history_available": bool(item.get("q_history_available")),
        "q_history_summary": str(item.get("q_history_summary") or ""),
        "q_history_points": list(item.get("q_history_points") or []),
        "q_history_open_blocks": list(item.get("q_history_open_blocks") or []),
        "q_history_span_s": float(item.get("q_history_span_s") or 0.0),
        "q_history_peak_abs": float(item.get("q_history_peak_abs") or 0.0),
        "q_history_zero_y": float(item.get("q_history_zero_y") or 0.5),
        "cause_effect_status": str(item.get("cause_effect_status") or ""),
        "cause_effect_badge": str(item.get("cause_effect_badge") or ""),
        "cause_effect_tone": str(item.get("cause_effect_tone") or "neutral"),
        "cause_effect_summary": str(item.get("cause_effect_summary") or ""),
    }


def _build_diagonal_pressure_strip_payloads(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in _build_route_pressure_strip_payloads(dataset, idx, selected_edge=selected_edge)
        if str(dict(item).get("role") or "") == "diagonal"
    ]


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
            "scheme_fidelity": {},
            "edges": [],
            "nodes": [],
            "mode_badges": [{"title": mode.title, "severity": mode.severity} for mode in narrative.modes[:3]],
        }

    edge_rows = _edge_rows_for_index(dataset, idx)
    node_rows = _node_rows_for_index(dataset, idx, overlay_only=True) or _node_rows_for_index(dataset, idx)
    focus_edge = selected_edge if selected_edge in dataset.edge_names else narrative.top_edge_name
    focus_node = selected_node if selected_node in dataset.node_names else narrative.top_node_name
    diagonal_focus = _build_active_diagonal_focus_meta(dataset, idx, selected_edge=focus_edge)

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
    diagonal_edges = list(diagonal_focus.get("edges") or [])
    if diagonal_edges:
        first_diagonal = dict(diagonal_edges[0] or {})
        _merge_alert_marker(
            edge_markers,
            name=str(first_diagonal.get("name") or ""),
            severity=str(first_diagonal.get("severity") or "attention"),
            label=str(first_diagonal.get("label") or "Активная диагональ"),
            summary=str(first_diagonal.get("summary") or "Диагональная связь заметно участвует в текущем кадре."),
            value=_finite_or_none(first_diagonal.get("flow")),
            unit=dataset.q_unit,
        )
        for item in list(diagonal_focus.get("nodes") or [])[:3]:
            marker_name = str(item.get("name") or "")
            _merge_alert_marker(
                node_markers,
                name=marker_name,
                severity=str(item.get("severity") or "attention"),
                label=str(item.get("label") or "Узел диагонали"),
                summary=str(item.get("summary") or "Участвует в активной диагональной связи."),
                value=_finite_or_none(item.get("pressure_bar_g")),
                unit="бар(g)",
            )

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
        "scheme_fidelity": dict(dataset.scheme_fidelity),
        "edges": edge_items,
        "nodes": node_items,
        "mode_badges": [{"title": mode.title, "severity": mode.severity} for mode in narrative.modes[:3]],
        "diagonal_focus": diagonal_focus,
    }


def prepare_dataset(npz_path: Path) -> MnemoDataset:
    bundle = load_npz(npz_path)
    if bundle.q is None:
        raise ValueError("NPZ bundle has no q_values table for pneumatic mnemonic.")

    canonical_node_names, edge_defs = _load_canonical_edges()
    edge_names = [name for name in bundle.q.cols if name != "время_с"]
    node_names = [name for name in (bundle.p.cols if bundle.p is not None else []) if name != "время_с"]
    full_node_inventory = list(dict.fromkeys([*canonical_node_names, *node_names]))
    node_positions = _build_node_positions(full_node_inventory)
    svg_inline = _build_semantic_svg(node_positions)
    reference_svg_inline, reference_scheme_source = _load_canonical_pneumo_scheme_svg()
    mapping = _build_mapping(edge_names, full_node_inventory, edge_defs, node_positions)
    scheme_fidelity = _build_scheme_fidelity_report(
        canonical_node_names=canonical_node_names,
        edge_defs=edge_defs,
        bundle_edge_names=edge_names,
        bundle_node_names=node_names,
        node_positions=node_positions,
        bundle_mapping=mapping,
    )
    reference_anchor_positions = _reference_node_anchor_positions(full_node_inventory)
    reference_component_names = sorted(name for name in reference_anchor_positions if name in REFERENCE_COMPONENT_NODE_ANCHORS_SVG)
    reference_indicator_names = sorted(name for name in reference_anchor_positions if name in REFERENCE_INDICATOR_NODE_ANCHORS_SVG)
    reference_chamber_names = sorted(name for name in reference_anchor_positions if name in REFERENCE_CHAMBER_NODE_ANCHORS_SVG)
    reference_diagonal_positions = _reference_diagonal_geometry_positions(full_node_inventory)
    reference_diagonal_names = sorted(reference_diagonal_positions)
    scheme_fidelity["reference_scheme_source"] = reference_scheme_source
    scheme_fidelity["reference_scheme_available"] = bool(reference_svg_inline)
    scheme_fidelity["reference_scheme_mode"] = "native_underlay" if reference_svg_inline else "semantic_fallback"
    scheme_fidelity["reference_scheme_image_source"] = (
        str(SOURCE_OF_TRUTH_PNEUMO_IMAGE_PATH.resolve()) if SOURCE_OF_TRUTH_PNEUMO_IMAGE_PATH.exists() else ""
    )
    scheme_fidelity["reference_component_nodes_total"] = len(REFERENCE_COMPONENT_NODE_ANCHORS_SVG)
    scheme_fidelity["reference_component_nodes_snapped"] = len(reference_component_names)
    scheme_fidelity["reference_component_node_names"] = reference_component_names
    scheme_fidelity["reference_indicator_nodes_total"] = len(REFERENCE_INDICATOR_NODE_ANCHORS_SVG)
    scheme_fidelity["reference_indicator_nodes_snapped"] = len(reference_indicator_names)
    scheme_fidelity["reference_indicator_node_names"] = reference_indicator_names
    scheme_fidelity["reference_chamber_nodes_total"] = len(REFERENCE_CHAMBER_NODE_ANCHORS_SVG)
    scheme_fidelity["reference_chamber_nodes_snapped"] = len(reference_chamber_names)
    scheme_fidelity["reference_chamber_node_names"] = reference_chamber_names
    scheme_fidelity["reference_diagonal_nodes_total"] = len([name for name in canonical_node_names if DIAGONAL_RE.match(name)])
    scheme_fidelity["reference_diagonal_nodes_geometry_locked"] = len(reference_diagonal_names)
    scheme_fidelity["reference_diagonal_node_names"] = reference_diagonal_names

    p_atm = _p_atm_from_meta(bundle.meta if isinstance(bundle.meta, dict) else {})
    q_scale, q_unit = _flow_scale_and_unit(p_atm)
    overlay_node_names = _pick_overlay_nodes(node_names)
    edge_series = _build_edge_series(bundle, edge_names, q_scale, q_unit)
    node_series = _build_node_series(bundle, node_names, p_atm)
    node_edges = _build_node_edges(edge_defs, edge_names)
    visual_geometry = read_visual_geometry_meta(
        bundle.meta if isinstance(bundle.meta, dict) else {},
        context="Desktop Mnemo visual geometry",
        log=None,
    )
    geometry_issues = [str(item) for item in visual_geometry.get("issues", []) if str(item).strip()]
    geometry_warnings = [str(item) for item in visual_geometry.get("warnings", []) if str(item).strip()]
    time_s = np.asarray(bundle.t, dtype=float)
    dataset_id = f"{npz_path.resolve()}::{npz_path.stat().st_mtime_ns}"

    return MnemoDataset(
        npz_path=npz_path.resolve(),
        bundle=bundle,
        dataset_id=dataset_id,
        svg_inline=svg_inline,
        reference_svg_inline=reference_svg_inline,
        reference_scheme_source=reference_scheme_source,
        mapping=mapping,
        edge_names=edge_names,
        node_names=node_names,
        overlay_node_names=overlay_node_names,
        edge_series=edge_series,
        node_series=node_series,
        edge_defs=edge_defs,
        canonical_node_names=list(canonical_node_names),
        canonical_edge_names=list(edge_defs.keys()),
        time_s=time_s,
        q_scale=q_scale,
        q_unit=q_unit,
        p_atm=p_atm,
        node_edges=node_edges,
        visual_geometry=visual_geometry,
        geometry_issues=geometry_issues,
        geometry_warnings=geometry_warnings,
        scheme_fidelity=scheme_fidelity,
    )


def _finite_or_none(value: Any) -> float | None:
    try:
        value_f = float(value)
    except Exception:
        return None
    if not np.isfinite(value_f):
        return None
    return float(value_f)


def _clamp01(value: float) -> float:
    return float(max(0.0, min(1.0, float(value))))


def _mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    tt = _clamp01(t)
    return tuple(
        int(round((1.0 - tt) * float(av) + tt * float(bv)))
        for av, bv in zip(a, b)
    )


def _palette_rgb(stops: tuple[tuple[float, tuple[int, int, int]], ...], value: float) -> tuple[int, int, int]:
    if not stops:
        return (128, 128, 128)
    v = _clamp01(value)
    prev_pos, prev_rgb = stops[0]
    for pos, rgb in stops[1:]:
        if v <= pos:
            span = max(1.0e-9, float(pos) - float(prev_pos))
            t = (v - float(prev_pos)) / span
            return _mix_rgb(prev_rgb, rgb, t)
        prev_pos, prev_rgb = pos, rgb
    return tuple(prev_rgb)


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*tuple(int(max(0, min(255, c))) for c in rgb))


def _text_color_for_rgb(rgb: tuple[int, int, int]) -> str:
    luminance = 0.299 * float(rgb[0]) + 0.587 * float(rgb[1]) + 0.114 * float(rgb[2])
    return "#0c1620" if luminance >= 170.0 else "#eef6f8"


def _pressure_to_heat_rgb(pressure_bar_g: float | None) -> tuple[int, int, int]:
    if pressure_bar_g is None:
        return (34, 48, 58)
    normalized = _clamp01((float(pressure_bar_g) + 0.35) / 10.35)
    return _palette_rgb(PRESSURE_HEAT_STOPS, normalized)


def _flow_to_heat_rgb(flow_value: float, *, max_abs_flow: float) -> tuple[int, int, int]:
    if not np.isfinite(flow_value) or abs(float(flow_value)) <= 1.0e-9 or max_abs_flow <= 1.0e-9:
        return FLOW_IDLE_RGB
    base = FLOW_FORWARD_RGB if float(flow_value) >= 0.0 else FLOW_REVERSE_RGB
    strength = _clamp01(abs(float(flow_value)) / float(max_abs_flow))
    return _mix_rgb(FLOW_IDLE_RGB, base, 0.20 + 0.80 * strength)


def _corner_is_front(corner: str) -> bool:
    return str(corner) in {"ЛП", "ПП"}


def _short_node_label(node_name: str) -> str:
    label = str(node_name or "").strip()
    if not label:
        return "—"
    if label in SUPPLY_LABELS:
        return str(SUPPLY_LABELS[label][0])
    chamber_match = CHAMBER_RE.match(label)
    if chamber_match:
        return (
            f"Ц{chamber_match.group('cyl')} "
            f"{chamber_match.group('corner')} "
            f"{chamber_match.group('ch')}"
        )
    diagonal_match = DIAGONAL_RE.match(label)
    if diagonal_match:
        src_corner = str(diagonal_match.group("src_corner"))
        dst_corner = str(diagonal_match.group("dst_corner"))
        src_ch = _chamber_short(str(diagonal_match.group("src_ch")))
        dst_ch = _chamber_short(str(diagonal_match.group("dst_ch")))
        return f"{src_corner}/{src_ch} → {dst_corner}/{dst_ch}"
    if label.startswith("узел_после_"):
        return label.replace("узел_после_", "", 1)
    return label


def _edge_open_state(dataset: MnemoDataset, edge_name: str, idx: int) -> str:
    if dataset.bundle.open is None:
        return "нет сигнала"
    open_arr = dataset.bundle.open.column(edge_name, default=None)
    if open_arr is None:
        return "нет сигнала"
    clamped_idx = int(max(0, min(idx, max(0, len(open_arr) - 1))))
    return "открыт" if int(np.asarray(open_arr, dtype=int)[clamped_idx]) else "закрыт"


def _edge_zone_corners(edge_name: str, edge_def: dict[str, Any]) -> tuple[str, ...]:
    corners: list[str] = []
    for node_name in (str(edge_def.get("n1") or ""), str(edge_def.get("n2") or "")):
        chamber_match = CHAMBER_RE.match(node_name)
        if chamber_match:
            corners.append(str(chamber_match.group("corner")))
        diagonal_match = DIAGONAL_RE.match(node_name)
        if diagonal_match:
            corners.extend(
                (
                    str(diagonal_match.group("src_corner")),
                    str(diagonal_match.group("dst_corner")),
                )
            )
    if not corners:
        for corner in CORNER_ORDER:
            if corner in str(edge_name):
                corners.append(corner)
    ordered = [corner for corner in CORNER_ORDER if corner in corners]
    return tuple(dict.fromkeys(ordered))


def _edge_zone_label(edge_name: str, edge_def: dict[str, Any]) -> str:
    corners = _edge_zone_corners(edge_name, edge_def)
    if corners:
        return " / ".join(corners)
    endpoints = [str(edge_def.get("n1") or ""), str(edge_def.get("n2") or "")]
    named = [_short_node_label(item) for item in endpoints if item]
    if named:
        return " · ".join(named[:2])
    return "магистраль"


def _edge_component_kind(edge_name: str, edge_def: dict[str, Any]) -> str:
    lower_name = str(edge_name).lower()
    if any(token in lower_name for token in ("обратн", "check", "chk", "клапан", "ok_")):
        return "РћР±СЂР°С‚РЅС‹Р№ РєР»Р°РїР°РЅ"
    if any(token in lower_name for token in ("регулятор", "regulator", "reg_")):
        return "Р РµРіСѓР»СЏС‚РѕСЂ"
    if any(token in lower_name for token in ("дроссель", "throttle", "drossel", "dr_")):
        return "Р”СЂРѕСЃСЃРµР»СЊ"
    if "обратн" in lower_name:
        return "Обратный клапан"
    if "регулятор" in lower_name:
        return "Регулятор"
    if "дроссель" in lower_name:
        return "Дроссель"
    role = _edge_role(edge_name, edge_def)
    if role == "vent":
        return "Сброс"
    if role == "diagonal":
        return "Диагональ"
    if role == "supply":
        return "Питание"
    if role == "actuator":
        return "Исполнительная ветвь"
    return "Линия"


def _stroke_arrays_for_corner(dataset: MnemoDataset, corner: str) -> tuple[np.ndarray | None, np.ndarray | None]:
    stroke_arr = dataset.bundle.main.column(f"положение_штока_{corner}_м", default=None)
    if stroke_arr is None:
        return None, None
    stroke_vals = np.asarray(stroke_arr, dtype=float).reshape(-1)
    speed_arr = dataset.bundle.main.column(f"скорость_штока_{corner}_м_с", default=None)
    if speed_arr is not None:
        speed_vals = np.asarray(speed_arr, dtype=float).reshape(-1)
    elif stroke_vals.size >= 2 and dataset.time_s.size == stroke_vals.size:
        try:
            speed_vals = np.asarray(np.gradient(stroke_vals, dataset.time_s), dtype=float)
        except Exception:
            speed_vals = np.zeros_like(stroke_vals)
    else:
        speed_vals = np.zeros_like(stroke_vals)
    return stroke_vals, speed_vals


def _cylinder_geometry_for_corner(
    dataset: MnemoDataset,
    *,
    cyl_index: int,
    corner: str,
) -> dict[str, float | None]:
    geom = dataset.visual_geometry if isinstance(dataset.visual_geometry, dict) else {}
    stroke_key = f"cyl{int(cyl_index)}_stroke_front_m" if _corner_is_front(corner) else f"cyl{int(cyl_index)}_stroke_rear_m"
    return {
        "bore_diameter_m": _finite_or_none(geom.get(f"cyl{int(cyl_index)}_bore_diameter_m")),
        "rod_diameter_m": _finite_or_none(geom.get(f"cyl{int(cyl_index)}_rod_diameter_m")),
        "stroke_len_m": _finite_or_none(geom.get(stroke_key)),
        "dead_cap_length_m": _finite_or_none(geom.get(f"cyl{int(cyl_index)}_dead_cap_length_m")),
        "dead_rod_length_m": _finite_or_none(geom.get(f"cyl{int(cyl_index)}_dead_rod_length_m")),
    }


def _pressure_triplet(dataset: MnemoDataset, idx: int, node_name: str) -> tuple[float | None, float | None, float | None]:
    if dataset.bundle.p is None:
        return None, None, None
    p_arr = dataset.bundle.p.column(node_name, default=None)
    if p_arr is None:
        return None, None, None
    p_vals = _bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)
    if p_vals.size == 0:
        return None, None, None
    clamped_idx = int(max(0, min(idx, p_vals.size - 1)))
    return (
        float(p_vals[clamped_idx]),
        float(np.nanmin(p_vals)),
        float(np.nanmax(p_vals)),
    )


def _chamber_volume_snapshot(
    *,
    chamber_key: str,
    stroke_m: float | None,
    geometry: dict[str, float | None],
) -> tuple[float | None, float | None, bool]:
    bore_diameter = geometry.get("bore_diameter_m")
    rod_diameter = geometry.get("rod_diameter_m")
    stroke_len = geometry.get("stroke_len_m")
    dead_cap = geometry.get("dead_cap_length_m")
    dead_rod = geometry.get("dead_rod_length_m")
    if None in {bore_diameter, rod_diameter, stroke_len, dead_cap, dead_rod} or stroke_m is None:
        return None, None, False

    bore_radius = 0.5 * float(bore_diameter)
    rod_radius = 0.5 * float(rod_diameter)
    cap_area = math.pi * bore_radius * bore_radius
    rod_area = cap_area - math.pi * rod_radius * rod_radius
    if not (cap_area > 0.0 and rod_area > 0.0):
        return None, None, False

    stroke_clamped = max(0.0, min(float(stroke_m), float(stroke_len)))
    cap_len = float(dead_cap) + max(0.0, float(stroke_len) - stroke_clamped)
    rod_len = float(dead_rod) + stroke_clamped
    if str(chamber_key) == "БП":
        max_len = max(1.0e-9, float(dead_cap) + float(stroke_len))
        return float(cap_area * cap_len * 1000.0), _clamp01(cap_len / max_len), True
    max_len = max(1.0e-9, float(dead_rod) + float(stroke_len))
    return float(rod_area * rod_len * 1000.0), _clamp01(rod_len / max_len), True


def _build_cylinder_snapshots(dataset: MnemoDataset | None, idx: int) -> list[CylinderSnapshot]:
    if dataset is None or dataset.time_s.size == 0:
        return []

    snapshots: list[CylinderSnapshot] = []
    for corner in CORNER_ORDER:
        stroke_vals, speed_vals = _stroke_arrays_for_corner(dataset, corner)
        clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
        stroke_m = None if stroke_vals is None or stroke_vals.size == 0 else float(stroke_vals[min(clamped_idx, stroke_vals.size - 1)])
        stroke_speed_m_s = None if speed_vals is None or speed_vals.size == 0 else float(speed_vals[min(clamped_idx, speed_vals.size - 1)])

        for cyl_index in (1, 2):
            cap_name = f"Ц{cyl_index}_{corner}_БП"
            rod_name = f"Ц{cyl_index}_{corner}_ШП"
            cap_p, cap_min, cap_max = _pressure_triplet(dataset, clamped_idx, cap_name)
            rod_p, rod_min, rod_max = _pressure_triplet(dataset, clamped_idx, rod_name)
            geometry = _cylinder_geometry_for_corner(dataset, cyl_index=cyl_index, corner=corner)
            stroke_len_m = geometry.get("stroke_len_m")
            stroke_ratio = None
            if stroke_len_m is not None and stroke_len_m > 1.0e-9 and stroke_m is not None:
                stroke_ratio = _clamp01(float(stroke_m) / float(stroke_len_m))
            cap_volume_l, cap_fill_ratio, cap_volume_ready = _chamber_volume_snapshot(
                chamber_key="БП",
                stroke_m=stroke_m,
                geometry=geometry,
            )
            rod_volume_l, rod_fill_ratio, rod_volume_ready = _chamber_volume_snapshot(
                chamber_key="ШП",
                stroke_m=stroke_m,
                geometry=geometry,
            )
            delta_p_bar = None
            if cap_p is not None and rod_p is not None:
                delta_p_bar = float(cap_p - rod_p)
            if stroke_speed_m_s is None:
                motion_label = "нет сигнала хода"
            elif stroke_speed_m_s > 1.0e-4:
                motion_label = "шток выдвигается"
            elif stroke_speed_m_s < -1.0e-4:
                motion_label = "шток втягивается"
            else:
                motion_label = "шток удерживается"

            cap_snapshot = ChamberSnapshot(
                node_name=cap_name,
                chamber_key="БП",
                pressure_bar_g=cap_p,
                pressure_min_bar_g=cap_min,
                pressure_max_bar_g=cap_max,
                volume_l=cap_volume_l,
                fill_ratio=cap_fill_ratio,
            )
            rod_snapshot = ChamberSnapshot(
                node_name=rod_name,
                chamber_key="ШП",
                pressure_bar_g=rod_p,
                pressure_min_bar_g=rod_min,
                pressure_max_bar_g=rod_max,
                volume_l=rod_volume_l,
                fill_ratio=rod_fill_ratio,
            )
            focus_node = cap_name
            if (rod_p or float("-inf")) > (cap_p or float("-inf")):
                focus_node = rod_name

            snapshots.append(
                CylinderSnapshot(
                    corner=corner,
                    cyl_index=cyl_index,
                    stroke_m=stroke_m,
                    stroke_speed_m_s=stroke_speed_m_s,
                    stroke_ratio=stroke_ratio,
                    stroke_len_m=stroke_len_m,
                    cap=cap_snapshot,
                    rod=rod_snapshot,
                    delta_p_bar=delta_p_bar,
                    motion_label=motion_label,
                    volume_mode="absolute" if cap_volume_ready and rod_volume_ready else "pressure_only",
                    geometry_ready=bool(cap_volume_ready and rod_volume_ready),
                    focus_node=focus_node,
                )
            )
    return snapshots


def _build_edge_activity_snapshots(dataset: MnemoDataset | None, idx: int) -> list[EdgeActivitySnapshot]:
    if dataset is None or dataset.time_s.size == 0:
        return []

    rows: list[EdgeActivitySnapshot] = []
    for edge_name, q_now in _edge_rows_for_index(dataset, idx)[:12]:
        edge_def = dataset.edge_defs.get(edge_name, {})
        n1 = str(edge_def.get("n1") or "")
        n2 = str(edge_def.get("n2") or "")
        if q_now >= 0.0:
            direction_label = f"{_short_node_label(n1)} → {_short_node_label(n2)}"
        else:
            direction_label = f"{_short_node_label(n2)} → {_short_node_label(n1)}"
        corners = _edge_zone_corners(edge_name, edge_def)
        rows.append(
            EdgeActivitySnapshot(
                edge_name=edge_name,
                component_kind=_edge_component_kind(edge_name, edge_def),
                q_now=float(q_now),
                direction_label=direction_label,
                state_label=_edge_open_state(dataset, edge_name, idx),
                zone_label=_edge_zone_label(edge_name, edge_def),
                corners=corners,
            )
        )
    return rows


def _build_edge_activity_snapshots_full(dataset: MnemoDataset | None, idx: int) -> list[EdgeActivitySnapshot]:
    if dataset is None or dataset.time_s.size == 0:
        return []

    rows: list[EdgeActivitySnapshot] = []
    for edge_name, q_now in _edge_rows_for_index(dataset, idx):
        edge_def = dataset.edge_defs.get(edge_name, {})
        n1 = str(edge_def.get("n1") or "")
        n2 = str(edge_def.get("n2") or "")
        if q_now >= 0.0:
            direction_label = f"{_short_node_label(n1)} в†’ {_short_node_label(n2)}"
        else:
            direction_label = f"{_short_node_label(n2)} в†’ {_short_node_label(n1)}"
        corners = _edge_zone_corners(edge_name, edge_def)
        rows.append(
            EdgeActivitySnapshot(
                edge_name=edge_name,
                component_kind=_edge_component_kind(edge_name, edge_def),
                q_now=float(q_now),
                direction_label=direction_label,
                state_label=_edge_open_state(dataset, edge_name, idx),
                zone_label=_edge_zone_label(edge_name, edge_def),
                corners=corners,
            )
        )
    return rows


def _build_corner_snapshot_cards(
    cylinder_rows: list[CylinderSnapshot],
    edge_rows: list[EdgeActivitySnapshot],
) -> dict[str, dict[str, Any]]:
    max_abs_flow = max((abs(float(item.q_now)) for item in edge_rows), default=0.0)
    cards: dict[str, dict[str, Any]] = {}
    for corner in CORNER_ORDER:
        corner_cylinders = [item for item in cylinder_rows if item.corner == corner]
        corner_edges = [item for item in edge_rows if corner in item.corners]
        pressures = [
            value
            for item in corner_cylinders
            for value in (item.cap.pressure_bar_g, item.rod.pressure_bar_g)
            if value is not None
        ]
        max_pressure = max(pressures) if pressures else None
        delta_candidates = [abs(float(item.delta_p_bar)) for item in corner_cylinders if item.delta_p_bar is not None]
        delta_peak = max(delta_candidates) if delta_candidates else 0.0
        stroke_ratio = next((item.stroke_ratio for item in corner_cylinders if item.stroke_ratio is not None), None)
        stroke_speed = next((item.stroke_speed_m_s for item in corner_cylinders if item.stroke_speed_m_s is not None), None)
        dominant_flow = max(corner_edges, key=lambda item: abs(float(item.q_now)), default=None)
        cards[corner] = {
            "corner": corner,
            "max_pressure_bar_g": max_pressure,
            "pressure_rgb": _pressure_to_heat_rgb(max_pressure),
            "delta_peak_bar": float(delta_peak),
            "stroke_ratio": stroke_ratio,
            "stroke_speed_m_s": stroke_speed,
            "dominant_flow_q": None if dominant_flow is None else float(dominant_flow.q_now),
            "dominant_flow_rgb": _flow_to_heat_rgb(
                0.0 if dominant_flow is None else float(dominant_flow.q_now),
                max_abs_flow=max_abs_flow,
            ),
            "flow_zone_label": "—" if dominant_flow is None else dominant_flow.zone_label,
            "motion_label": next((item.motion_label for item in corner_cylinders if item.motion_label), "нет сигнала"),
        }
    return cards


def _find_cylinder_snapshot_for_node(
    rows: list[CylinderSnapshot],
    node_name: str,
) -> tuple[CylinderSnapshot, ChamberSnapshot] | None:
    for item in rows:
        if item.cap.node_name == node_name:
            return item, item.cap
        if item.rod.node_name == node_name:
            return item, item.rod
    return None


def _focus_corner_from_selection(
    dataset: MnemoDataset | None,
    *,
    edge_name: str | None,
    node_name: str | None,
) -> str | None:
    if node_name:
        chamber_match = CHAMBER_RE.match(node_name)
        if chamber_match:
            return str(chamber_match.group("corner"))
    if dataset is None or not edge_name:
        return None
    corners = _edge_zone_corners(edge_name, dataset.edge_defs.get(edge_name, {}))
    if len(corners) == 1:
        return str(corners[0])
    return None


def _component_kind_short_label(kind: str) -> str:
    mapping = {
        "РћР±СЂР°С‚РЅС‹Р№ РєР»Р°РїР°РЅ": "CHK",
        "Р РµРіСѓР»СЏС‚РѕСЂ": "REG",
        "Р”СЂРѕСЃСЃРµР»СЊ": "THR",
        "РЎР±СЂРѕСЃ": "VENT",
        "Р”РёР°РіРѕРЅР°Р»СЊ": "XOVR",
        "РџРёС‚Р°РЅРёРµ": "SUP",
        "РСЃРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РІРµС‚РІСЊ": "ACT",
        "Р›РёРЅРёСЏ": "LINE",
    }
    return mapping.get(str(kind), "LINE")


def _state_short_label(state_label: str) -> str:
    lowered = str(state_label).lower()
    if "РѕС‚РєСЂ" in lowered:
        return "OPEN"
    if "Р·Р°РєСЂ" in lowered:
        return "SHUT"
    return "SIG?"


def _motion_short_label(stroke_speed_m_s: float | None) -> str:
    if stroke_speed_m_s is None:
        return "SIG?"
    if stroke_speed_m_s > 1.0e-4:
        return "EXT"
    if stroke_speed_m_s < -1.0e-4:
        return "RET"
    return "HOLD"


def _serialize_chamber_overlay(chamber: ChamberSnapshot) -> dict[str, Any]:
    heat_rgb = _pressure_to_heat_rgb(chamber.pressure_bar_g)
    return {
        "node_name": chamber.node_name,
        "chamber_key": chamber.chamber_key,
        "pressure_bar_g": _finite_or_none(chamber.pressure_bar_g),
        "pressure_min_bar_g": _finite_or_none(chamber.pressure_min_bar_g),
        "pressure_max_bar_g": _finite_or_none(chamber.pressure_max_bar_g),
        "volume_l": _finite_or_none(chamber.volume_l),
        "fill_ratio": _finite_or_none(chamber.fill_ratio),
        "heat_hex": _rgb_hex(heat_rgb),
        "text_hex": _text_color_for_rgb(heat_rgb),
    }


def _serialize_cylinder_overlay(snapshot: CylinderSnapshot) -> dict[str, Any]:
    delta_value = _finite_or_none(snapshot.delta_p_bar)
    delta_rgb = _pressure_to_heat_rgb(abs(delta_value) if delta_value is not None else None)
    return {
        "id": f"cyl{snapshot.cyl_index}_{snapshot.corner}",
        "corner": snapshot.corner,
        "cyl_index": int(snapshot.cyl_index),
        "stroke_m": _finite_or_none(snapshot.stroke_m),
        "stroke_speed_m_s": _finite_or_none(snapshot.stroke_speed_m_s),
        "stroke_ratio": _finite_or_none(snapshot.stroke_ratio),
        "stroke_len_m": _finite_or_none(snapshot.stroke_len_m),
        "delta_p_bar": delta_value,
        "delta_hex": _rgb_hex(delta_rgb),
        "delta_text_hex": _text_color_for_rgb(delta_rgb),
        "motion_label": snapshot.motion_label,
        "motion_short": _motion_short_label(snapshot.stroke_speed_m_s),
        "volume_mode": snapshot.volume_mode,
        "geometry_ready": bool(snapshot.geometry_ready),
        "focus_node": snapshot.focus_node,
        "cap": _serialize_chamber_overlay(snapshot.cap),
        "rod": _serialize_chamber_overlay(snapshot.rod),
    }


def _build_component_overlay_rows(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
) -> list[dict[str, Any]]:
    all_rows = _build_edge_activity_snapshots_full(dataset, idx)
    if not all_rows:
        return []

    selected_name = str(selected_edge or "")
    relevant_kinds = {
        "РћР±СЂР°С‚РЅС‹Р№ РєР»Р°РїР°РЅ",
        "Р РµРіСѓР»СЏС‚РѕСЂ",
        "Р”СЂРѕСЃСЃРµР»СЊ",
        "РЎР±СЂРѕСЃ",
        "Р”РёР°РіРѕРЅР°Р»СЊ",
    }
    max_abs_flow = max((abs(float(item.q_now)) for item in all_rows), default=0.0)
    diagonal_floor = max_abs_flow * 0.08 if max_abs_flow > 1.0e-9 else 0.0

    payload_rows: list[dict[str, Any]] = []
    for order, item in enumerate(all_rows):
        if item.edge_name != selected_name and item.component_kind not in relevant_kinds:
            continue
        if (
            item.edge_name != selected_name
            and item.component_kind == "Р”РёР°РіРѕРЅР°Р»СЊ"
            and abs(float(item.q_now)) < diagonal_floor
        ):
            continue
        flow_rgb = _flow_to_heat_rgb(item.q_now, max_abs_flow=max_abs_flow)
        payload_rows.append(
            {
                "edge_name": item.edge_name,
                "component_kind": item.component_kind,
                "component_short": _component_kind_short_label(item.component_kind),
                "q_now": _finite_or_none(item.q_now),
                "flow_abs": _finite_or_none(abs(float(item.q_now))),
                "direction_label": item.direction_label,
                "state_label": item.state_label,
                "state_short": _state_short_label(item.state_label),
                "zone_label": item.zone_label,
                "corners": list(item.corners),
                "flow_hex": _rgb_hex(flow_rgb),
                "text_hex": _text_color_for_rgb(flow_rgb),
                "is_selected": bool(item.edge_name == selected_name),
                "is_active": bool(
                    abs(float(item.q_now)) >= max_abs_flow * 0.04 if max_abs_flow > 1.0e-9 else item.edge_name == selected_name
                ),
                "order": int(order),
            }
        )

    payload_rows.sort(
        key=lambda item: (
            0 if item.get("is_selected") else 1,
            -float(item.get("flow_abs") or 0.0),
            str(item.get("edge_name") or ""),
        )
    )
    return payload_rows[:18]


def _build_mnemo_diagnostics_payload(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
    selected_node: str | None,
) -> dict[str, Any]:
    cylinder_rows = _build_cylinder_snapshots(dataset, idx)
    component_rows = _build_component_overlay_rows(dataset, idx, selected_edge=selected_edge)
    focus_corner = _focus_corner_from_selection(dataset, edge_name=selected_edge, node_name=selected_node)
    diagonal_focus = _build_active_diagonal_focus_meta(dataset, idx, selected_edge=selected_edge)
    route_pressure_strips = _build_route_pressure_strip_payloads(dataset, idx, selected_edge=selected_edge)
    diagonal_pressure_strips = _build_diagonal_pressure_strip_payloads(dataset, idx, selected_edge=selected_edge)
    return {
        "frame_idx": int(max(0, idx)),
        "focus_corner": focus_corner,
        "selected_edge": str(selected_edge or ""),
        "selected_node": str(selected_node or ""),
        "scheme_fidelity": dict(dataset.scheme_fidelity) if dataset is not None else {},
        "geometry_warnings": list(dataset.geometry_warnings) if dataset is not None else [],
        "geometry_issues": list(dataset.geometry_issues) if dataset is not None else [],
        "cylinders": [_serialize_cylinder_overlay(item) for item in cylinder_rows],
        "components": component_rows,
        "diagonal_focus": diagonal_focus,
        "route_pressure_strips": route_pressure_strips,
        "diagonal_pressure_strips": diagonal_pressure_strips,
    }


def _edge_component_kind(edge_name: str, edge_def: dict[str, Any]) -> str:
    lower_name = str(edge_name).lower()
    if any(token in lower_name for token in ("обратн", "check", "chk", "клапан", "ok_")):
        return "Обратный клапан"
    if any(token in lower_name for token in ("регулятор", "regulator", "reg_")):
        return "Регулятор"
    if any(token in lower_name for token in ("дроссель", "throttle", "drossel", "dr_")):
        return "Дроссель"
    role = _edge_role(edge_name, edge_def)
    if role == "vent":
        return "Сброс"
    if role == "diagonal":
        return "Диагональ"
    if role == "supply":
        return "Питание"
    if role == "actuator":
        return "Исполнительная ветвь"
    return "Линия"


def _component_kind_short_label(kind: str) -> str:
    mapping = {
        "Обратный клапан": "CHK",
        "Регулятор": "REG",
        "Дроссель": "THR",
        "Сброс": "VENT",
        "Диагональ": "XOVR",
        "Питание": "SUP",
        "Исполнительная ветвь": "ACT",
        "Линия": "LINE",
        "РћР±СЂР°С‚РЅС‹Р№ РєР»Р°РїР°РЅ": "CHK",
        "Р РµРіСѓР»СЏС‚РѕСЂ": "REG",
        "Р”СЂРѕСЃСЃРµР»СЊ": "THR",
        "РЎР±СЂРѕСЃ": "VENT",
        "Р”РёР°РіРѕРЅР°Р»СЊ": "XOVR",
        "РџРёС‚Р°РЅРёРµ": "SUP",
        "РСЃРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РІРµС‚РІСЊ": "ACT",
        "Р›РёРЅРёСЏ": "LINE",
    }
    return mapping.get(str(kind), "LINE")


def _canonical_kind_label(kind: str) -> str:
    mapping = {
        "check": "check valve",
        "orifice": "orifice",
        "relief": "relief regulator",
        "reg_after": "after-self regulator",
    }
    return mapping.get(str(kind or "").strip().lower(), "generic line")


def _edge_direction_meta(edge_def: dict[str, Any], q_now: float | None) -> dict[str, Any]:
    endpoint_1 = str(edge_def.get("n1") or "")
    endpoint_2 = str(edge_def.get("n2") or "")
    endpoint_1_short = _short_node_label(endpoint_1)
    endpoint_2_short = _short_node_label(endpoint_2)
    canonical_direction_label = (
        f"{endpoint_1_short} → {endpoint_2_short}" if endpoint_1 or endpoint_2 else "—"
    )
    q_value = _finite_or_none(q_now)
    flow_active = q_value is not None and abs(float(q_value)) > 1.0e-6
    if not flow_active:
        return {
            "endpoint_1": endpoint_1,
            "endpoint_2": endpoint_2,
            "endpoint_1_short": endpoint_1_short,
            "endpoint_2_short": endpoint_2_short,
            "canonical_direction_label": canonical_direction_label,
            "flow_direction_label": "нет выраженного потока",
            "flow_status_label": "стагнация / переход",
            "canonical_source": endpoint_1,
            "canonical_sink": endpoint_2,
            "canonical_source_short": endpoint_1_short,
            "canonical_sink_short": endpoint_2_short,
            "flow_source": "",
            "flow_sink": "",
            "flow_source_short": "",
            "flow_sink_short": "",
            "flow_matches_canonical": None,
            "flow_forward": None,
        }
    flow_forward = bool(float(q_value) >= 0.0)
    if flow_forward:
        flow_direction_label = f"{endpoint_1_short} → {endpoint_2_short}"
        flow_status_label = "по паспорту"
        flow_source = endpoint_1
        flow_sink = endpoint_2
        flow_source_short = endpoint_1_short
        flow_sink_short = endpoint_2_short
    else:
        flow_direction_label = f"{endpoint_2_short} → {endpoint_1_short}"
        flow_status_label = "реверс к паспорту"
        flow_source = endpoint_2
        flow_sink = endpoint_1
        flow_source_short = endpoint_2_short
        flow_sink_short = endpoint_1_short
    return {
        "endpoint_1": endpoint_1,
        "endpoint_2": endpoint_2,
        "endpoint_1_short": endpoint_1_short,
        "endpoint_2_short": endpoint_2_short,
        "canonical_direction_label": canonical_direction_label,
        "flow_direction_label": flow_direction_label,
        "flow_status_label": flow_status_label,
        "canonical_source": endpoint_1,
        "canonical_sink": endpoint_2,
        "canonical_source_short": endpoint_1_short,
        "canonical_sink_short": endpoint_2_short,
        "flow_source": flow_source,
        "flow_sink": flow_sink,
        "flow_source_short": flow_source_short,
        "flow_sink_short": flow_sink_short,
        "flow_matches_canonical": flow_forward,
        "flow_forward": flow_forward,
    }


def _edge_pressure_drive_meta(
    direction_meta: dict[str, Any],
    *,
    p1_bar_g: float | None,
    p2_bar_g: float | None,
    q_now: float | None,
) -> dict[str, Any]:
    endpoint_1_short = str(direction_meta.get("endpoint_1_short") or "—")
    endpoint_2_short = str(direction_meta.get("endpoint_2_short") or "—")
    delta_p_bar = (
        float(p1_bar_g) - float(p2_bar_g)
        if p1_bar_g is not None and p2_bar_g is not None
        else None
    )
    if delta_p_bar is None:
        return {
            "delta_p_bar": None,
            "pressure_drive_label": "нет данных по давлениям",
            "pressure_drive_status": "нет данных",
            "pressure_drive_badge": "ΔP ?",
            "pressure_lead": "",
            "pressure_sink": "",
            "pressure_lead_short": "",
            "pressure_sink_short": "",
            "endpoint_1_pressure_role": "P?",
            "endpoint_2_pressure_role": "P?",
        }

    near_zero = abs(float(delta_p_bar)) <= 0.05
    if near_zero:
        flow_active = q_now is not None and np.isfinite(float(q_now)) and abs(float(q_now)) > 1.0e-6
        return {
            "delta_p_bar": float(delta_p_bar),
            "pressure_drive_label": f"{endpoint_1_short} ≈ {endpoint_2_short}",
            "pressure_drive_status": "перепад мал",
            "pressure_drive_badge": "ΔP≈",
            "pressure_lead": "",
            "pressure_sink": "",
            "pressure_lead_short": "",
            "pressure_sink_short": "",
            "endpoint_1_pressure_role": "P≈",
            "endpoint_2_pressure_role": "P≈",
            "flow_vs_pressure": "перепад мал" if flow_active else "нет выраженного потока",
        }

    endpoint_1 = str(direction_meta.get("endpoint_1") or "")
    endpoint_2 = str(direction_meta.get("endpoint_2") or "")
    lead_is_n1 = bool(delta_p_bar >= 0.0)
    pressure_lead = endpoint_1 if lead_is_n1 else endpoint_2
    pressure_sink = endpoint_2 if lead_is_n1 else endpoint_1
    pressure_lead_short = endpoint_1_short if lead_is_n1 else endpoint_2_short
    pressure_sink_short = endpoint_2_short if lead_is_n1 else endpoint_1_short
    endpoint_1_pressure_role = "P+" if lead_is_n1 else "P-"
    endpoint_2_pressure_role = "P-" if lead_is_n1 else "P+"
    q_value = _finite_or_none(q_now)
    if q_value is None or abs(float(q_value)) <= 1.0e-6:
        flow_vs_pressure = "нет выраженного потока"
        pressure_drive_status = "ведущий перепад"
        pressure_drive_badge = "ΔP lead"
    else:
        flow_source = str(direction_meta.get("flow_source") or "")
        if flow_source and flow_source == pressure_lead:
            flow_vs_pressure = "по перепаду"
            pressure_drive_status = "согласовано с ΔP"
            pressure_drive_badge = "ΔP ok"
        else:
            flow_vs_pressure = "против перепада"
            pressure_drive_status = "реверс к ΔP"
            pressure_drive_badge = "ΔP rev"
    return {
        "delta_p_bar": float(delta_p_bar),
        "pressure_drive_label": f"{pressure_lead_short} > {pressure_sink_short}",
        "pressure_drive_status": pressure_drive_status,
        "pressure_drive_badge": pressure_drive_badge,
        "pressure_lead": pressure_lead,
        "pressure_sink": pressure_sink,
        "pressure_lead_short": pressure_lead_short,
        "pressure_sink_short": pressure_sink_short,
        "endpoint_1_pressure_role": endpoint_1_pressure_role,
        "endpoint_2_pressure_role": endpoint_2_pressure_role,
        "flow_vs_pressure": flow_vs_pressure,
    }


def _edge_element_flow_contract_meta(
    canonical_kind: str,
    component_kind: str,
    direction_meta: dict[str, Any],
    *,
    q_now: float | None,
) -> dict[str, Any]:
    canonical = str(canonical_kind or "").strip().lower()
    component = str(component_kind or "").strip()
    q_value = _finite_or_none(q_now)
    flow_active = q_value is not None and abs(float(q_value)) > 1.0e-6
    flow_matches = direction_meta.get("flow_matches_canonical")

    if canonical == "orifice":
        if not flow_active:
            return {
                "element_flow_status": "двусторонний дроссель без выраженного потока",
                "element_flow_label": "реверс допустим, элемент симметричен по направлению",
                "element_flow_badge": "EL bi",
                "element_flow_tone": "info",
            }
        return {
            "element_flow_status": "двусторонний дроссель",
            "element_flow_label": "реверс допустим для orifice",
            "element_flow_badge": "EL bi",
            "element_flow_tone": "info",
        }

    if canonical in {"check", "reg_after"} or component in {"Обратный клапан", "Регулятор"}:
        if not flow_active:
            return {
                "element_flow_status": "односторонний элемент, поток не выражен",
                "element_flow_label": "направление элемента задано, но активный ход не наблюдается",
                "element_flow_badge": "EL dir",
                "element_flow_tone": "neutral",
            }
        if flow_matches is True:
            return {
                "element_flow_status": "по направлению элемента",
                "element_flow_label": "ход согласован с односторонней арматурой",
                "element_flow_badge": "EL ok",
                "element_flow_tone": "ok",
            }
        return {
            "element_flow_status": "против направления элемента",
            "element_flow_label": "обратный ход для односторонней арматуры",
            "element_flow_badge": "EL rev",
            "element_flow_tone": "warn",
        }

    if canonical == "relief" or component == "Сброс":
        if not flow_active:
            return {
                "element_flow_status": "разгрузочный элемент без активного хода",
                "element_flow_label": "разгрузка не выражена в текущем кадре",
                "element_flow_badge": "EL vent",
                "element_flow_tone": "neutral",
            }
        if flow_matches is True:
            return {
                "element_flow_status": "разгрузка по схеме",
                "element_flow_label": "ход согласован с relief-направлением",
                "element_flow_badge": "EL vent",
                "element_flow_tone": "ok",
            }
        return {
            "element_flow_status": "нетипичный реверс для relief",
            "element_flow_label": "обратный ход относительно relief-направления",
            "element_flow_badge": "EL rev",
            "element_flow_tone": "warn",
        }

    if not flow_active:
        return {
            "element_flow_status": "линия без выраженного потока",
            "element_flow_label": "тип элемента не ограничивает ход в текущем кадре",
            "element_flow_badge": "EL gen",
            "element_flow_tone": "neutral",
        }
    return {
        "element_flow_status": "линия без жёсткого directional-ограничения",
        "element_flow_label": "направление читается по Q и ΔP, а не по типу элемента",
        "element_flow_badge": "EL gen",
        "element_flow_tone": "info",
    }


def _edge_operability_meta(
    state_label: str,
    *,
    q_now: float | None,
    pressure_meta: dict[str, Any],
    element_meta: dict[str, Any],
) -> dict[str, Any]:
    state = str(state_label or "").strip().lower()
    q_value = _finite_or_none(q_now)
    flow_active = q_value is not None and abs(float(q_value)) > 1.0e-6
    delta_p_bar = _finite_or_none(pressure_meta.get("delta_p_bar"))
    delta_active = delta_p_bar is not None and abs(float(delta_p_bar)) >= 0.25
    pressure_badge = str(pressure_meta.get("pressure_drive_badge") or "")
    element_tone = str(element_meta.get("element_flow_tone") or "neutral")
    element_status = str(element_meta.get("element_flow_status") or "—")

    if "закрыт" in state:
        if flow_active:
            return {
                "operability_status": "закрыт, но расход есть",
                "operability_label": "проверьте отсечку, байпас или утечку через элемент",
                "operability_badge": "OP leak",
                "operability_tone": "warn",
            }
        return {
            "operability_status": "закрыт и потока нет",
            "operability_label": "сигнал закрытия согласован с кадром",
            "operability_badge": "OP shut",
            "operability_tone": "neutral",
        }

    if element_tone == "warn" and flow_active:
        return {
            "operability_status": "поток конфликтует с арматурой",
            "operability_label": element_status,
            "operability_badge": "OP elem",
            "operability_tone": "warn",
        }

    if pressure_badge == "ΔP rev" and flow_active:
        return {
            "operability_status": "поток идёт против ведущего перепада",
            "operability_label": "проверьте локальный обход, переходный режим или ошибку знака",
            "operability_badge": "OP dp",
            "operability_tone": "warn",
        }

    if "открыт" in state:
        if flow_active and pressure_badge in {"ΔP ok", "ΔP lead", "ΔP≈"} and element_tone != "warn":
            return {
                "operability_status": "ветвь ведёт себя согласованно",
                "operability_label": "сигнал, поток и перепад не противоречат друг другу",
                "operability_badge": "OP ok",
                "operability_tone": "ok",
            }
        if not flow_active and delta_active:
            return {
                "operability_status": "открыт, но расход не набран",
                "operability_label": "перепад уже есть, а поток ещё не развивается",
                "operability_badge": "OP hold",
                "operability_tone": "info",
            }
        if not flow_active:
            return {
                "operability_status": "открыт, ожидание расхода",
                "operability_label": "ветвь готова, но текущий кадр ещё без выраженного хода",
                "operability_badge": "OP idle",
                "operability_tone": "neutral",
            }

    return {
        "operability_status": "состояние ветви требует контекста",
        "operability_label": "оценка опирается на Q, ΔP и тип элемента без надёжного сигнала открытия",
        "operability_badge": "OP ctx",
        "operability_tone": "info",
    }


def _edge_consistency_meta(
    state_label: str,
    *,
    q_now: float | None,
    pressure_meta: dict[str, Any],
    element_meta: dict[str, Any],
) -> dict[str, Any]:
    state = str(state_label or "").strip().lower()
    q_value = _finite_or_none(q_now)
    flow_active = q_value is not None and abs(float(q_value)) > 1.0e-6
    pressure_badge = str(pressure_meta.get("pressure_drive_badge") or "")
    element_tone = str(element_meta.get("element_flow_tone") or "neutral")

    if "закрыт" in state and flow_active:
        return {
            "consistency_status": "сигнал закрытия конфликтует с расходом",
            "consistency_label": "ветвь закрыта по сигналу, но расход уже наблюдается",
            "consistency_badge": "CS q",
            "consistency_tone": "warn",
        }
    if element_tone == "warn" and flow_active:
        return {
            "consistency_status": "поток конфликтует с типом элемента",
            "consistency_label": str(element_meta.get("element_flow_status") or "—"),
            "consistency_badge": "CS el",
            "consistency_tone": "warn",
        }
    if pressure_badge == "ΔP rev" and flow_active:
        return {
            "consistency_status": "расход конфликтует с ведущим перепадом",
            "consistency_label": "текущий ход не поддержан знаком ΔP",
            "consistency_badge": "CS dp",
            "consistency_tone": "warn",
        }
    if "открыт" in state and not flow_active and pressure_badge in {"ΔP ok", "ΔP lead"}:
        return {
            "consistency_status": "открыт, но расход запаздывает",
            "consistency_label": "сигнал и ΔP уже согласованы, а поток ещё не набран",
            "consistency_badge": "CS hold",
            "consistency_tone": "info",
        }
    if ("открыт" in state and flow_active and pressure_badge in {"ΔP ok", "ΔP lead", "ΔP≈"} and element_tone != "warn"):
        return {
            "consistency_status": "сигналы ветви согласованы",
            "consistency_label": "open-state, Q, ΔP и тип элемента не противоречат друг другу",
            "consistency_badge": "CS ok",
            "consistency_tone": "ok",
        }
    return {
        "consistency_status": "сигналы неполные или переходные",
        "consistency_label": "оценка требует дополнительного контекста по соседним ветвям",
        "consistency_badge": "CS ctx",
        "consistency_tone": "neutral",
    }


def _edge_temporal_meta(
    *,
    time_s: np.ndarray | list[float],
    q_values: np.ndarray | list[float],
    open_values: np.ndarray | list[int] | None,
    idx: int,
) -> dict[str, Any]:
    q_arr = np.asarray(q_values, dtype=float).reshape(-1)
    if q_arr.size == 0:
        return {
            "temporal_status": "нет временного ряда",
            "temporal_label": "для ветви нет истории расхода",
            "temporal_badge": "TM ?",
            "temporal_tone": "neutral",
            "window_s": 0.0,
            "dq_dt": None,
        }
    t_arr = np.asarray(time_s, dtype=float).reshape(-1)
    if t_arr.size != q_arr.size:
        t_arr = np.arange(q_arr.size, dtype=float)
    clamped_idx = int(max(0, min(idx, q_arr.size - 1, t_arr.size - 1)))
    start_idx = max(0, clamped_idx - 3)
    recent_q = q_arr[start_idx : clamped_idx + 1]
    recent_t = t_arr[start_idx : clamped_idx + 1]
    recent_open = None
    if open_values is not None:
        open_arr = np.asarray(open_values, dtype=int).reshape(-1)
        if open_arr.size:
            recent_open = open_arr[start_idx : min(clamped_idx + 1, open_arr.size)]

    q_now = float(recent_q[-1])
    q_prev = float(recent_q[-2]) if recent_q.size >= 2 else float(recent_q[-1])
    dt = float(recent_t[-1] - recent_t[-2]) if recent_t.size >= 2 else 0.0
    dq_dt = None if abs(dt) <= 1.0e-9 else float((q_now - q_prev) / dt)
    window_s = float(recent_t[-1] - recent_t[0]) if recent_t.size >= 2 else 0.0
    global_peak = float(np.max(np.abs(q_arr))) if q_arr.size else 0.0
    active_floor = max(1.0e-6, global_peak * 0.08)
    flow_active = abs(float(q_now)) > active_floor
    change_floor = max(active_floor * 0.35, global_peak * 0.12)
    delta_abs = abs(float(q_now)) - abs(float(q_prev))
    active_signs = [int(np.sign(val)) for val in recent_q if abs(float(val)) > active_floor]
    sign_changes = sum(1 for prev, nxt in zip(active_signs[:-1], active_signs[1:]) if prev != nxt)
    open_changed = bool(
        recent_open is not None
        and recent_open.size >= 2
        and np.any(recent_open[1:] != recent_open[:-1])
    )

    if sign_changes >= 2:
        return {
            "temporal_status": "колебание расхода",
            "temporal_label": "ветвь несколько раз меняет знак в коротком окне",
            "temporal_badge": "TM osc",
            "temporal_tone": "warn",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    if sign_changes == 1 and flow_active:
        return {
            "temporal_status": "смена направления",
            "temporal_label": "ветвь развернула ход в недавнем окне",
            "temporal_badge": "TM flip",
            "temporal_tone": "warn",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    if open_changed and flow_active:
        return {
            "temporal_status": "ход после переключения",
            "temporal_label": "ветвь недавно переключилась и уже набирает расход",
            "temporal_badge": "TM gate",
            "temporal_tone": "info",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    if not flow_active and float(np.max(np.abs(recent_q))) <= active_floor:
        return {
            "temporal_status": "спокойный кадр",
            "temporal_label": "в недавнем окне ветвь остаётся без выраженного хода",
            "temporal_badge": "TM idle",
            "temporal_tone": "neutral",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    if delta_abs > change_floor:
        return {
            "temporal_status": "набор расхода",
            "temporal_label": "амплитуда расхода растёт в последних кадрах",
            "temporal_badge": "TM ramp",
            "temporal_tone": "info",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    if delta_abs < -change_floor:
        return {
            "temporal_status": "затухание расхода",
            "temporal_label": "амплитуда расхода снижается в последних кадрах",
            "temporal_badge": "TM fall",
            "temporal_tone": "info",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    if flow_active:
        return {
            "temporal_status": "устойчивый ход",
            "temporal_label": "ветвь держит направление и уровень расхода без резких срывов",
            "temporal_badge": "TM steady",
            "temporal_tone": "ok",
            "window_s": window_s,
            "dq_dt": dq_dt,
        }
    return {
        "temporal_status": "переходная пауза",
        "temporal_label": "ход ослаб, но ветвь ещё находится в переходном окне",
        "temporal_badge": "TM soft",
        "temporal_tone": "neutral",
        "window_s": window_s,
        "dq_dt": dq_dt,
    }


def _edge_recent_history_meta(
    *,
    time_s: np.ndarray | list[float],
    q_values: np.ndarray | list[float],
    open_values: np.ndarray | list[int] | None,
    idx: int,
    max_points: int = 8,
) -> dict[str, Any]:
    q_arr = np.asarray(q_values, dtype=float).reshape(-1)
    if q_arr.size == 0:
        return {
            "history_available": False,
            "history_points": [],
            "history_open_blocks": [],
            "history_span_s": 0.0,
            "history_sample_count": 0,
            "history_peak_abs": 0.0,
            "history_open_ratio": None,
            "history_zero_y": 0.5,
        }

    t_arr = np.asarray(time_s, dtype=float).reshape(-1)
    if t_arr.size != q_arr.size:
        t_arr = np.arange(q_arr.size, dtype=float)
    clamped_idx = int(max(0, min(idx, q_arr.size - 1, t_arr.size - 1)))
    history_points_count = max(2, int(max_points))
    start_idx = max(0, clamped_idx - history_points_count + 1)
    recent_q = q_arr[start_idx : clamped_idx + 1]
    recent_t = t_arr[start_idx : clamped_idx + 1]

    peak_abs = float(np.max(np.abs(recent_q))) if recent_q.size else 0.0
    amplitude = peak_abs if peak_abs > 1.0e-9 else 1.0
    points: list[tuple[float, float]] = []
    for point_idx, q_value in enumerate(recent_q):
        x_norm = 0.0 if recent_q.size <= 1 else float(point_idx / max(1, recent_q.size - 1))
        y_norm = 0.5 - max(-0.42, min(0.42, 0.42 * float(q_value) / amplitude))
        points.append((x_norm, float(y_norm)))

    open_ratio = None
    open_blocks: list[dict[str, Any]] = []
    if open_values is not None:
        open_arr = np.asarray(open_values, dtype=int).reshape(-1)
        if open_arr.size:
            recent_open = open_arr[start_idx : min(clamped_idx + 1, open_arr.size)]
            if recent_open.size:
                open_ratio = float(np.mean(recent_open > 0))
                segment_count = max(1, int(recent_open.size))
                for segment_idx, state in enumerate(recent_open):
                    x0 = float(segment_idx / segment_count)
                    x1 = float((segment_idx + 1) / segment_count)
                    open_blocks.append(
                        {
                            "x0": x0,
                            "x1": x1,
                            "open": bool(int(state)),
                        }
                    )

    span_s = float(recent_t[-1] - recent_t[0]) if recent_t.size >= 2 else 0.0
    return {
        "history_available": True,
        "history_points": points,
        "history_open_blocks": open_blocks,
        "history_span_s": span_s,
        "history_sample_count": int(recent_q.size),
        "history_peak_abs": peak_abs,
        "history_open_ratio": open_ratio,
        "history_zero_y": 0.5,
    }


def _edge_recent_history_summary(history_meta: dict[str, Any], q_unit: str) -> str:
    if not bool(history_meta.get("history_available")):
        return "история ветви ещё не накоплена"

    span_s = float(history_meta.get("history_span_s") or 0.0)
    sample_count = int(history_meta.get("history_sample_count") or 0)
    peak_abs = float(history_meta.get("history_peak_abs") or 0.0)
    summary = f"{span_s:0.2f} s • {sample_count} кадр."
    if peak_abs > 0.0:
        summary += f" • пик |Q| {peak_abs:0.2f} {q_unit}"
    else:
        summary += " • без выраженного расхода"
    open_ratio = history_meta.get("history_open_ratio")
    if open_ratio is not None:
        summary += f" • открыт {float(open_ratio) * 100.0:0.0f}% окна"
    return summary


def _edge_recent_pressure_meta(
    *,
    time_s: np.ndarray | list[float],
    p1_values: np.ndarray | list[float] | None,
    p2_values: np.ndarray | list[float] | None,
    idx: int,
    max_points: int = 8,
) -> dict[str, Any]:
    if p1_values is None or p2_values is None:
        return {
            "pressure_history_available": False,
            "pressure_history_points": [],
            "pressure_history_span_s": 0.0,
            "pressure_history_sample_count": 0,
            "pressure_history_peak_abs": 0.0,
            "pressure_history_last_delta": None,
            "pressure_history_status": "нет данных по давлениям",
            "pressure_history_tone": "neutral",
            "pressure_history_zero_y": 0.5,
        }

    p1_arr = np.asarray(p1_values, dtype=float).reshape(-1)
    p2_arr = np.asarray(p2_values, dtype=float).reshape(-1)
    sample_count = min(p1_arr.size, p2_arr.size)
    if sample_count <= 0:
        return {
            "pressure_history_available": False,
            "pressure_history_points": [],
            "pressure_history_span_s": 0.0,
            "pressure_history_sample_count": 0,
            "pressure_history_peak_abs": 0.0,
            "pressure_history_last_delta": None,
            "pressure_history_status": "нет данных по давлениям",
            "pressure_history_tone": "neutral",
            "pressure_history_zero_y": 0.5,
        }

    delta_arr = (p1_arr[:sample_count] - p2_arr[:sample_count]).astype(float)
    t_arr = np.asarray(time_s, dtype=float).reshape(-1)
    if t_arr.size != sample_count:
        t_arr = np.arange(sample_count, dtype=float)
    clamped_idx = int(max(0, min(idx, sample_count - 1, t_arr.size - 1)))
    history_points_count = max(2, int(max_points))
    start_idx = max(0, clamped_idx - history_points_count + 1)
    recent_delta = delta_arr[start_idx : clamped_idx + 1]
    recent_t = t_arr[start_idx : clamped_idx + 1]
    peak_abs = float(np.max(np.abs(recent_delta))) if recent_delta.size else 0.0
    amplitude = peak_abs if peak_abs > 1.0e-9 else 1.0
    points: list[tuple[float, float]] = []
    for point_idx, delta_value in enumerate(recent_delta):
        x_norm = 0.0 if recent_delta.size <= 1 else float(point_idx / max(1, recent_delta.size - 1))
        y_norm = 0.5 - max(-0.42, min(0.42, 0.42 * float(delta_value) / amplitude))
        points.append((x_norm, float(y_norm)))

    span_s = float(recent_t[-1] - recent_t[0]) if recent_t.size >= 2 else 0.0
    last_delta = float(recent_delta[-1]) if recent_delta.size else None
    prev_delta = float(recent_delta[-2]) if recent_delta.size >= 2 else float(recent_delta[-1])
    stable_floor = max(0.05, peak_abs * 0.14)
    delta_step = abs(float(last_delta or 0.0) - float(prev_delta))
    active_signs = [int(np.sign(val)) for val in recent_delta if abs(float(val)) > stable_floor]
    sign_changes = sum(1 for prev, nxt in zip(active_signs[:-1], active_signs[1:]) if prev != nxt)
    if peak_abs <= 0.05:
        status = "ΔP почти выровнен"
        tone = "neutral"
    elif sign_changes >= 1:
        status = "ΔP сменил знак"
        tone = "warn"
    elif delta_step > stable_floor:
        status = "ΔP заметно перестраивается"
        tone = "info"
    else:
        status = "ΔP удерживается"
        tone = "ok"

    return {
        "pressure_history_available": True,
        "pressure_history_points": points,
        "pressure_history_span_s": span_s,
        "pressure_history_sample_count": int(recent_delta.size),
        "pressure_history_peak_abs": peak_abs,
        "pressure_history_last_delta": last_delta,
        "pressure_history_status": status,
        "pressure_history_tone": tone,
        "pressure_history_zero_y": 0.5,
    }


def _edge_recent_pressure_summary(pressure_meta: dict[str, Any]) -> str:
    if not bool(pressure_meta.get("pressure_history_available")):
        return "контур ΔP ещё не вычислен"

    span_s = float(pressure_meta.get("pressure_history_span_s") or 0.0)
    sample_count = int(pressure_meta.get("pressure_history_sample_count") or 0)
    peak_abs = float(pressure_meta.get("pressure_history_peak_abs") or 0.0)
    summary = (
        f"{span_s:0.2f} s • {sample_count} кадр. • "
        f"{str(pressure_meta.get('pressure_history_status') or 'ΔP без статуса')}"
    )
    if peak_abs > 0.0:
        summary += f" • |ΔP|max {peak_abs:0.2f} бар"
    last_delta = pressure_meta.get("pressure_history_last_delta")
    if last_delta is not None:
        summary += f" • текущее {float(last_delta):+0.2f} бар"
    return summary


def _edge_recent_causality_meta(
    *,
    state_label: str,
    history_meta: dict[str, Any],
    pressure_meta: dict[str, Any],
    temporal_meta: dict[str, Any],
    consistency_meta: dict[str, Any],
) -> dict[str, Any]:
    flow_peak = float(history_meta.get("history_peak_abs") or 0.0)
    pressure_peak = float(pressure_meta.get("pressure_history_peak_abs") or 0.0)
    open_ratio_raw = history_meta.get("history_open_ratio")
    open_ratio = None if open_ratio_raw is None else float(open_ratio_raw)
    pressure_status = str(pressure_meta.get("pressure_history_status") or "")
    temporal_status = str(temporal_meta.get("temporal_status") or "")
    consistency_status = str(consistency_meta.get("consistency_status") or "")
    last_delta = pressure_meta.get("pressure_history_last_delta")

    flow_recent = flow_peak > 1.0e-6
    pressure_recent = pressure_peak > 0.05
    open_high = open_ratio is not None and open_ratio >= 0.55
    open_low = open_ratio is not None and open_ratio <= 0.25
    state_lower = str(state_label or "").lower()

    if not flow_recent and not pressure_recent:
        return {
            "causality_status": "ветвь остаётся в покое",
            "causality_label": "в недавнем окне нет ни выраженного ΔP, ни выраженного расхода",
            "causality_badge": "CX idle",
            "causality_tone": "neutral",
        }
    if open_low and flow_recent:
        return {
            "causality_status": "поток идёт без устойчивого открытия",
            "causality_label": "расход уже проявлен, но окно почти не подтверждает open-state",
            "causality_badge": "CX leak",
            "causality_tone": "warn",
        }
    if pressure_status == "ΔP сменил знак" and flow_recent:
        return {
            "causality_status": "ветвь проходит через смену причинности",
            "causality_label": "перепад и расход одновременно перестраивают направление",
            "causality_badge": "CX flip",
            "causality_tone": "warn",
        }
    if open_high and pressure_recent and not flow_recent:
        return {
            "causality_status": "ветвь подготовлена, но Q запаздывает",
            "causality_label": "открытие и ΔP уже собраны, а расход ещё не развился",
            "causality_badge": "CX wait",
            "causality_tone": "info",
        }
    if open_high and flow_recent and pressure_recent:
        if "почти выровнен" in pressure_status or (last_delta is not None and abs(float(last_delta)) <= 0.05):
            return {
                "causality_status": "ветвь уже разгружается после хода",
                "causality_label": "расход выражен, а перепад на концах ветви уже почти снят",
                "causality_badge": "CX dump",
                "causality_tone": "info",
            }
        if (
            "согласованы" in consistency_status
            or temporal_status in {"устойчивый ход", "набор расхода", "затухание расхода", "ход после переключения"}
            or "открыт" in state_lower
        ):
            return {
                "causality_status": "Q откликается на открытие и ΔP",
                "causality_label": "недавнее окно подтверждает причинную связку между сигналом, перепадом и ходом",
                "causality_badge": "CX ok",
                "causality_tone": "ok",
            }
    if pressure_recent and flow_recent:
        return {
            "causality_status": "Q и ΔP движутся вместе, но без явной команды",
            "causality_label": "динамика ветви связана, но open-state в окне выражен слабо",
            "causality_badge": "CX mix",
            "causality_tone": "info",
        }
    if pressure_recent and not flow_recent:
        return {
            "causality_status": "ΔP собирается без расхода",
            "causality_label": "ветвь накапливает перепад, но ход пока не развился",
            "causality_badge": "CX hold",
            "causality_tone": "info",
        }
    return {
        "causality_status": "причинная связка требует контекста",
        "causality_label": "для уверенного вывода нужен соседний контур или большее временное окно",
        "causality_badge": "CX ctx",
        "causality_tone": "neutral",
    }


def _edge_recent_causality_summary(causality_meta: dict[str, Any], history_meta: dict[str, Any]) -> str:
    status = str(causality_meta.get("causality_status") or "причинная связка не определена")
    summary = status
    open_ratio = history_meta.get("history_open_ratio")
    if open_ratio is not None:
        summary += f" • открыт {float(open_ratio) * 100.0:0.0f}% окна"
    return summary


def _edge_recent_latency_meta(
    *,
    time_s: np.ndarray | list[float],
    q_values: np.ndarray | list[float],
    open_values: np.ndarray | list[int] | None,
    p1_values: np.ndarray | list[float] | None,
    p2_values: np.ndarray | list[float] | None,
    idx: int,
    max_points: int = 8,
) -> dict[str, Any]:
    q_arr = np.asarray(q_values, dtype=float).reshape(-1)
    if q_arr.size == 0:
        return {
            "latency_status": "нет окна для оценки лага",
            "latency_label": "история ветви ещё не накоплена",
            "latency_badge": "LG ?",
            "latency_tone": "neutral",
            "latency_s": None,
            "latency_cause": "",
        }

    t_arr = np.asarray(time_s, dtype=float).reshape(-1)
    if t_arr.size != q_arr.size:
        t_arr = np.arange(q_arr.size, dtype=float)
    clamped_idx = int(max(0, min(idx, q_arr.size - 1, t_arr.size - 1)))
    history_points_count = max(2, int(max_points))
    start_idx = max(0, clamped_idx - history_points_count + 1)
    recent_q = q_arr[start_idx : clamped_idx + 1]
    recent_t = t_arr[start_idx : clamped_idx + 1]
    if recent_q.size == 0 or recent_t.size == 0:
        return {
            "latency_status": "нет окна для оценки лага",
            "latency_label": "история ветви ещё не накоплена",
            "latency_badge": "LG ?",
            "latency_tone": "neutral",
            "latency_s": None,
            "latency_cause": "",
        }

    dt_nominal = float(np.median(np.diff(recent_t))) if recent_t.size >= 2 else 0.0
    tolerance_s = max(0.04, dt_nominal * 0.55)
    q_peak = float(np.max(np.abs(recent_q))) if recent_q.size else 0.0
    q_floor = max(1.0e-6, q_peak * 0.12)

    recent_open = None
    if open_values is not None:
        open_arr = np.asarray(open_values, dtype=int).reshape(-1)
        if open_arr.size:
            recent_open = open_arr[start_idx : min(clamped_idx + 1, open_arr.size)]

    recent_delta = None
    if p1_values is not None and p2_values is not None:
        p1_arr = np.asarray(p1_values, dtype=float).reshape(-1)
        p2_arr = np.asarray(p2_values, dtype=float).reshape(-1)
        sample_count = min(p1_arr.size, p2_arr.size, t_arr.size)
        if sample_count > 0:
            delta_arr = (p1_arr[:sample_count] - p2_arr[:sample_count]).astype(float)
            recent_delta = delta_arr[start_idx : min(clamped_idx + 1, sample_count)]

    def _first_match_index(values: np.ndarray | None, predicate: Any) -> int | None:
        if values is None or values.size == 0:
            return None
        for local_idx, value in enumerate(values):
            if predicate(value):
                return local_idx
        return None

    def _marker_x(local_idx: int | None, size: int) -> float | None:
        if local_idx is None or size <= 0:
            return None
        if size <= 1:
            return 0.0
        return float(local_idx / max(1, size - 1))

    q_idx = _first_match_index(recent_q, lambda value: abs(float(value)) > q_floor)
    open_idx = _first_match_index(recent_open, lambda value: int(value) > 0)
    dp_idx = None
    if recent_delta is not None and recent_delta.size:
        dp_peak = float(np.max(np.abs(recent_delta)))
        dp_floor = max(0.05, dp_peak * 0.18)
        dp_idx = _first_match_index(recent_delta, lambda value: abs(float(value)) > dp_floor)

    phase_events: list[tuple[int, int, str]] = []
    if open_idx is not None:
        phase_events.append((open_idx, 0, "SIG"))
    if dp_idx is not None:
        phase_events.append((dp_idx, 1, "ΔP"))
    if q_idx is not None:
        phase_events.append((q_idx, 2, "Q"))
    phase_label = "нет выраженной фазы"
    if phase_events:
        phase_label = " → ".join(label for _, _, label in sorted(phase_events, key=lambda item: (item[0], item[1])))

    signal_to_dp_s = (
        None if open_idx is None or dp_idx is None else float(recent_t[dp_idx] - recent_t[open_idx])
    )
    dp_to_q_s = None if dp_idx is None or q_idx is None else float(recent_t[q_idx] - recent_t[dp_idx])
    signal_to_q_s = None if open_idx is None or q_idx is None else float(recent_t[q_idx] - recent_t[open_idx])
    base_latency_meta = {
        "latency_phase_label": phase_label,
        "latency_signal_x": _marker_x(open_idx, recent_q.size),
        "latency_dp_x": _marker_x(dp_idx, recent_q.size),
        "latency_q_x": _marker_x(q_idx, recent_q.size),
        "latency_sig_to_dp_s": signal_to_dp_s,
        "latency_dp_to_q_s": dp_to_q_s,
        "latency_sig_to_q_s": signal_to_q_s,
    }

    def _payload(**kwargs: Any) -> dict[str, Any]:
        return {**base_latency_meta, **kwargs}

    cause_candidates: list[tuple[int, str]] = []
    if open_idx is not None:
        cause_candidates.append((open_idx, "открытия"))
    if dp_idx is not None:
        cause_candidates.append((dp_idx, "сборки ΔP"))

    if q_idx is None and not cause_candidates:
        return _payload(
            latency_status="нет выраженного лага",
            latency_label="в окне нет ни команды, ни расхода, ни ΔP для сравнения",
            latency_badge="LG idle",
            latency_tone="neutral",
            latency_s=None,
            latency_cause="",
        )
    if q_idx is None and cause_candidates:
        cause_idx, cause_label = min(cause_candidates, key=lambda item: item[0])
        waiting_s = float(recent_t[-1] - recent_t[cause_idx])
        return _payload(
            latency_status="Q ещё не дошёл до ветви",
            latency_label=f"после {cause_label} прошло {waiting_s:0.2f} s, а расход в окне ещё не проявился",
            latency_badge="LG wait",
            latency_tone="info",
            latency_s=waiting_s,
            latency_cause=cause_label,
        )
    if q_idx is not None and not cause_candidates:
        return _payload(
            latency_status="Q появляется раньше причины",
            latency_label="расход проявляется без явного открытия или выраженного ΔP в текущем окне",
            latency_badge="LG early",
            latency_tone="warn",
            latency_s=None,
            latency_cause="",
        )

    cause_idx, cause_label = min(cause_candidates, key=lambda item: item[0])
    lag_s = float(recent_t[q_idx] - recent_t[cause_idx]) if q_idx is not None else None
    if lag_s is None:
        return _payload(
            latency_status="лаг не определён",
            latency_label="окно недостаточно для уверенной оценки задержки",
            latency_badge="LG ?",
            latency_tone="neutral",
            latency_s=None,
            latency_cause=cause_label,
        )
    if lag_s < -tolerance_s:
        return _payload(
            latency_status="Q опережает окно причины",
            latency_label=f"расход появляется на {abs(lag_s):0.2f} s раньше {cause_label}",
            latency_badge="LG early",
            latency_tone="warn",
            latency_s=lag_s,
            latency_cause=cause_label,
        )
    if abs(lag_s) <= tolerance_s:
        return _payload(
            latency_status="Q подключается почти без лага",
            latency_label=f"между {cause_label} и расходом нет заметной задержки",
            latency_badge="LG ok",
            latency_tone="ok",
            latency_s=lag_s,
            latency_cause=cause_label,
        )
    if lag_s <= max(0.25, tolerance_s * 3.0):
        return _payload(
            latency_status="Q подключается с умеренным лагом",
            latency_label=f"расход приходит через {lag_s:0.2f} s после {cause_label}",
            latency_badge="LG soft",
            latency_tone="info",
            latency_s=lag_s,
            latency_cause=cause_label,
        )
    return _payload(
        latency_status="Q заметно запаздывает",
        latency_label=f"между {cause_label} и расходом накопилась задержка {lag_s:0.2f} s",
        latency_badge="LG late",
        latency_tone="warn",
        latency_s=lag_s,
        latency_cause=cause_label,
    )


def _edge_recent_latency_summary(latency_meta: dict[str, Any]) -> str:
    status = str(latency_meta.get("latency_status") or "лаг не определён")
    lag_s = latency_meta.get("latency_s")
    cause_label = str(latency_meta.get("latency_cause") or "")
    summary = status
    if lag_s is not None:
        summary += f" • Δt {float(lag_s):+0.2f} s"
    if cause_label:
        summary += f" • от {cause_label}"
    phase_label = str(latency_meta.get("latency_phase_label") or "")
    if phase_label:
        summary += f" • {phase_label}"
    return summary


def _edge_phase_ribbon_meta(latency_meta: dict[str, Any]) -> dict[str, Any]:
    phase_label = str(latency_meta.get("latency_phase_label") or "")
    parts = [part.strip() for part in phase_label.split("→") if part.strip()]
    order_map = {label: idx + 1 for idx, label in enumerate(parts)}
    latency_status = str(latency_meta.get("latency_status") or "")
    latency_tone = str(latency_meta.get("latency_tone") or "neutral")

    stages: list[dict[str, Any]] = []
    for label in ("SIG", "ΔP", "Q"):
        order = order_map.get(label)
        present = order is not None
        tone = "neutral"
        status = "нет в окне"
        if present:
            status = f"этап {order}"
            if label == "SIG":
                tone = "info"
            elif label == "ΔP":
                tone = "info"
            else:
                tone = latency_tone if latency_tone in {"ok", "info", "warn"} else "ok"
                if "раньше" in latency_status or "опережает" in latency_status:
                    status = f"этап {order} • раньше причины"
                elif "запаздывает" in latency_status:
                    status = f"этап {order} • с заметным лагом"
                elif "умеренным лагом" in latency_status:
                    status = f"этап {order} • с умеренным лагом"
                else:
                    status = f"этап {order} • в фазе"
        elif label == "Q" and "не дошёл" in latency_status:
            tone = "info"
            status = "ещё не дошёл"
        elif label in {"SIG", "ΔP"} and "раньше причины" in latency_status:
            tone = "warn"
            status = "не пойман в окне"
        stages.append(
            {
                "label": label,
                "order": int(order or 0),
                "present": bool(present),
                "tone": tone,
                "status": status,
                "chip_text": f"{order} {label}" if present else f"· {label}",
            }
        )

    def _interval_kind(from_label: str, to_label: str) -> tuple[str, str]:
        if from_label == "SIG" and to_label == "ΔP":
            return "control", "контур управления"
        if from_label == "ΔP" and to_label == "Q":
            return "response", "расходный отклик"
        return "phase", "фазовый порядок"

    def _interval_payload(from_label: str, to_label: str, dt_value: float | None) -> dict[str, Any]:
        interval_kind, interval_kind_label = _interval_kind(from_label, to_label)
        if dt_value is None:
            return {
                "from_label": from_label,
                "to_label": to_label,
                "kind": interval_kind,
                "kind_label": interval_kind_label,
                "chip_text": "miss",
                "tone": "neutral",
                "status": "нет полного интервала",
            }
        dt_float = float(dt_value)
        if dt_float < -0.04:
            return {
                "from_label": from_label,
                "to_label": to_label,
                "kind": interval_kind,
                "kind_label": interval_kind_label,
                "dt_s": dt_float,
                "chip_text": f"{dt_float:+0.2f}s",
                "tone": "warn",
                "status": "обратный порядок",
            }
        if abs(dt_float) <= 0.04:
            return {
                "from_label": from_label,
                "to_label": to_label,
                "kind": interval_kind,
                "kind_label": interval_kind_label,
                "dt_s": dt_float,
                "chip_text": "0.00s",
                "tone": "ok",
                "status": "почти синхронно",
            }
        if dt_float <= 0.25:
            return {
                "from_label": from_label,
                "to_label": to_label,
                "kind": interval_kind,
                "kind_label": interval_kind_label,
                "dt_s": dt_float,
                "chip_text": f"+{dt_float:0.2f}s",
                "tone": "info",
                "status": "умеренный интервал",
            }
        return {
            "from_label": from_label,
            "to_label": to_label,
            "kind": interval_kind,
            "kind_label": interval_kind_label,
            "dt_s": dt_float,
            "chip_text": f"+{dt_float:0.2f}s",
            "tone": "warn",
            "status": "длинный интервал",
        }

    intervals = [
        _interval_payload("SIG", "ΔP", _finite_or_none(latency_meta.get("latency_sig_to_dp_s"))),
        _interval_payload("ΔP", "Q", _finite_or_none(latency_meta.get("latency_dp_to_q_s"))),
    ]
    tone_rank = {"neutral": 0, "ok": 1, "info": 2, "warn": 3}
    bottleneck: dict[str, Any] | None = None
    for interval in intervals:
        interval["is_bottleneck"] = False
        score = (
            tone_rank.get(str(interval.get("tone") or "neutral"), 0),
            abs(float(_finite_or_none(interval.get("dt_s")) or 0.0)),
        )
        if bottleneck is None:
            bottleneck = dict(interval)
            bottleneck["_score"] = score
            continue
        if score > tuple(bottleneck.get("_score") or (0, 0.0)):
            bottleneck = dict(interval)
            bottleneck["_score"] = score

    bottleneck_label = "нет доминирующего узкого места"
    bottleneck_status = "фазовые интервалы не выделяются"
    bottleneck_tone = "neutral"
    bottleneck_kind = "нет доминирующего bottleneck"
    bottleneck_comment = "интервалы перехода не требуют отдельного операторского внимания"
    focus_pair_label = "нет фокусной пары"
    focus_stage_labels: list[str] = []
    focus_hint = "фазовая лента не требует дополнительного визуального акцента"
    if bottleneck is not None:
        bottleneck_label = (
            f"{str(bottleneck.get('from_label') or '—')}→{str(bottleneck.get('to_label') or '—')} "
            f"{str(bottleneck.get('chip_text') or '—')}"
        )
        bottleneck_status = str(bottleneck.get("status") or bottleneck_status)
        bottleneck_tone = str(bottleneck.get("tone") or "neutral")
        bottleneck_kind = str(bottleneck.get("kind_label") or bottleneck_kind)
        focus_pair_label = f"{str(bottleneck.get('from_label') or '—')} → {str(bottleneck.get('to_label') or '—')}"
        focus_stage_labels = [
            str(bottleneck.get("from_label") or ""),
            str(bottleneck.get("to_label") or ""),
        ]
        if str(bottleneck.get("kind") or "") == "control":
            bottleneck_comment = "задержка копится между командой и формированием перепада на ветви"
            focus_hint = "смотрите связку сигнала и набора ΔP: bottleneck сидит в управленческой части ветви"
        elif str(bottleneck.get("kind") or "") == "response":
            bottleneck_comment = "перепад уже собран, а расход подключается позже и даёт основной лаг"
            focus_hint = "смотрите связку ΔP и Q: bottleneck сидит в отклике расхода на уже собранный перепад"
        else:
            bottleneck_comment = "этапы проходят в нетипичном порядке и требуют проверки последовательности"
            focus_hint = "смотрите полный порядок фаз: bottleneck связан с нетипичным прохождением этапов"
        for interval in intervals:
            if (
                str(interval.get("from_label") or "") == str(bottleneck.get("from_label") or "")
                and str(interval.get("to_label") or "") == str(bottleneck.get("to_label") or "")
                and str(interval.get("chip_text") or "") == str(bottleneck.get("chip_text") or "")
            ):
                interval["is_bottleneck"] = True
                break

    ribbon_label = "нет выраженной фазовой ленты"
    if parts:
        ribbon_label = " → ".join(f"{label}({order_map.get(label, 0)})" for label in parts)
    interval_label = " • ".join(
        f"{item.get('from_label')}→{item.get('to_label')} {item.get('chip_text')}"
        for item in intervals
    )
    return {
        "phase_ribbon_label": ribbon_label,
        "phase_ribbon_stages": stages,
        "phase_ribbon_intervals": intervals,
        "phase_ribbon_interval_label": interval_label,
        "phase_ribbon_bottleneck_label": bottleneck_label,
        "phase_ribbon_bottleneck_status": bottleneck_status,
        "phase_ribbon_bottleneck_tone": bottleneck_tone,
        "phase_ribbon_bottleneck_kind": bottleneck_kind,
        "phase_ribbon_bottleneck_comment": bottleneck_comment,
        "phase_ribbon_focus_pair_label": focus_pair_label,
        "phase_ribbon_focus_stage_labels": focus_stage_labels,
        "phase_ribbon_focus_hint": focus_hint,
    }


def _edge_operator_hint_meta(
    *,
    component_kind: str,
    canonical_kind: str,
    operability_status: str,
    consistency_status: str,
    pressure_drive_status: str,
    latency_status: str,
    phase_ribbon_bottleneck_kind: str,
    phase_ribbon_bottleneck_comment: str,
    phase_ribbon_focus_hint: str,
) -> dict[str, Any]:
    component = str(component_kind or "").strip().lower()
    canonical = str(canonical_kind or "").strip().lower()
    operability = str(operability_status or "")
    consistency = str(consistency_status or "")
    pressure_status = str(pressure_drive_status or "")
    latency = str(latency_status or "")
    bottleneck_kind = str(phase_ribbon_bottleneck_kind or "")
    focus_hint = str(phase_ribbon_focus_hint or "")

    if "закрыт, но расход есть" in operability or "конфликтует с расходом" in consistency:
        return {
            "operator_hint_title": "проверить паразитный проход ветви",
            "operator_hint_label": "ищите негерметичный клапан, обходной путь или скрытый реверс через арматуру",
            "operator_hint_badge": "ACT leak",
            "operator_hint_tone": "warn",
        }
    if "реверс" in pressure_status or "против" in consistency:
        return {
            "operator_hint_title": "проверить реверс и направление ветви",
            "operator_hint_label": "сопоставьте стрелку элемента, знак ΔP и фактический ход Q; вероятен обратный проход или перепутанный маршрут",
            "operator_hint_badge": "ACT rev",
            "operator_hint_tone": "warn",
        }
    if bottleneck_kind == "контур управления":
        title = "проверить команду и сборку ΔP"
        label = "смотрите upstream-команду ветви и момент появления перепада до развития расхода"
        if canonical in {"reg_after"} or "регулятор" in component:
            label = "проверьте регулятор/управляющую арматуру и появляется ли перепад на ветви сразу после команды"
        elif canonical in {"check"} or "обратный клапан" in component:
            label = "проверьте момент открытия одностороннего элемента и набор перепада до появления расхода"
        return {
            "operator_hint_title": title,
            "operator_hint_label": label,
            "operator_hint_badge": "ACT ctrl",
            "operator_hint_tone": "warn" if "длинный" in latency or "запаздывает" in latency else "info",
        }
    if bottleneck_kind == "расходный отклик":
        title = "проверить проход и downstream отклик"
        label = "ΔP уже собран; ищите, где ветвь тормозит развитие расхода после перепада"
        if canonical == "orifice" or "дроссель" in component:
            label = "ΔP уже собран; сначала проверьте дроссель, узкое сечение и downstream-объём"
        elif canonical in {"check", "reg_after"} or "обратный клапан" in component or "регулятор" in component:
            label = "ΔP уже собран; проверьте проход через арматуру и downstream-нагрузку ветви"
        return {
            "operator_hint_title": title,
            "operator_hint_label": label,
            "operator_hint_badge": "ACT flow",
            "operator_hint_tone": "warn" if "запаздывает" in latency else "info",
        }
    if "раньше причины" in latency or "опережает" in latency:
        return {
            "operator_hint_title": "проверить порядок фаз и источник обходного хода",
            "operator_hint_label": "расход появляется раньше ожидаемой причины; проверьте синхронизацию сигналов и скрытый bypass",
            "operator_hint_badge": "ACT seq",
            "operator_hint_tone": "warn",
        }
    return {
        "operator_hint_title": "проверить последовательность фазы",
        "operator_hint_label": focus_hint or phase_ribbon_bottleneck_comment or "сопоставьте SIG, ΔP и Q на выбранной ветви",
        "operator_hint_badge": "ACT ctx",
        "operator_hint_tone": "neutral",
    }


def _edge_operator_checklist_meta(
    *,
    component_kind: str,
    canonical_kind: str,
    operator_hint_badge: str,
    phase_ribbon_bottleneck_kind: str,
    operability_status: str,
    consistency_status: str,
) -> dict[str, Any]:
    component = str(component_kind or "").strip().lower()
    canonical = str(canonical_kind or "").strip().lower()
    hint_badge = str(operator_hint_badge or "")
    bottleneck_kind = str(phase_ribbon_bottleneck_kind or "")
    operability = str(operability_status or "")
    consistency = str(consistency_status or "")

    items: list[str]
    if hint_badge == "ACT leak":
        items = [
            "герметичность седла и фактическое закрытие арматуры",
            "обходные ветви и скрытый реверс через соседние линии",
            "совпадает ли open-state с фактическим перекрытием ветви",
        ]
    elif hint_badge == "ACT rev":
        items = [
            "стрелку элемента и паспортное направление ветви",
            "знак ΔP на концах ветви в момент хода",
            "нет ли перепутанного upstream/downstream маршрута",
        ]
    elif bottleneck_kind == "контур управления":
        items = [
            "момент прихода команды на ветвь",
            "собирается ли ΔP сразу после команды",
            "не тормозит ли управляющая арматура открытие",
        ]
        if canonical in {"reg_after"} or "регулятор" in component:
            items[2] = "не тормозит ли регулятор или pilot-часть открытие"
        elif canonical in {"check"} or "обратный клапан" in component:
            items[2] = "не зависает ли односторонний клапан до появления ΔP"
    elif bottleneck_kind == "расходный отклик":
        items = [
            "проходит ли расход через элемент после сборки ΔP",
            "нет ли узкого сечения или дросселирования downstream",
            "не забирает ли downstream-объём весь отклик ветви",
        ]
        if canonical == "orifice" or "дроссель" in component:
            items[1] = "настроен ли дроссель и не слишком ли зажат проход"
        elif canonical in {"check", "reg_after"} or "обратный клапан" in component or "регулятор" in component:
            items[1] = "не ограничивает ли арматура проход при уже собранном ΔP"
    elif "конфликтует" in consistency or "закрыт, но расход есть" in operability:
        items = [
            "реальное состояние закрытия ветви",
            "паразитный обходной проход",
            "нет ли реверса через соседнюю арматуру",
        ]
    else:
        items = [
            "порядок SIG → ΔP → Q в текущем окне",
            "совпадает ли bottleneck с поведением ветви на схеме",
            "нет ли соседнего контура, который перехватывает ход",
        ]

    focus_tone = "neutral"
    if hint_badge in {"ACT leak", "ACT rev"} or "конфликтует" in consistency or "закрыт, но расход есть" in operability:
        focus_tone = "warn"
    elif bottleneck_kind in {"контур управления", "расходный отклик"}:
        focus_tone = "info"
    rows = [
        {
            "index_label": f"{idx + 1:02d}",
            "title": item,
            "tone": focus_tone if idx == 0 else ("info" if idx == 1 and focus_tone != "warn" else "neutral"),
            "is_focus": idx == 0,
        }
        for idx, item in enumerate(items[:3])
    ]
    summary = " • ".join(items[:2])
    return {
        "operator_checklist_items": items,
        "operator_checklist_rows": rows,
        "operator_checklist_summary": summary,
    }


def _component_icon_key(kind: str, canonical_kind: str) -> str:
    canonical = str(canonical_kind or "").strip().lower()
    if canonical in {"check", "orifice", "relief", "reg_after"}:
        return canonical
    normalized = str(kind or "").strip().lower()
    if "диагон" in normalized:
        return "diagonal"
    if "сброс" in normalized:
        return "vent"
    if "питание" in normalized:
        return "supply"
    if "исполнитель" in normalized:
        return "actuator"
    return "line"


def _state_short_label(state_label: str) -> str:
    lowered = str(state_label).lower()
    if any(token in lowered for token in ("откр", "рѕс‚рєсЂ")):
        return "OPEN"
    if any(token in lowered for token in ("закр", "р·р°рєсЂ")):
        return "SHUT"
    return "SIG?"


def _build_selected_edge_focus_meta(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    edge_name: str | None,
) -> dict[str, Any]:
    if dataset is None or dataset.time_s.size == 0:
        return {}
    selected_edge = str(edge_name or "")
    if not selected_edge or selected_edge not in dataset.edge_names:
        return {}

    clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
    edge_def = dataset.edge_defs.get(selected_edge, {})
    n1 = str(edge_def.get("n1") or "")
    n2 = str(edge_def.get("n2") or "")
    if not n1 and not n2:
        return {}

    q_now = 0.0
    if dataset.bundle.q is not None:
        q_arr = dataset.bundle.q.column(selected_edge, default=None)
        if q_arr is not None:
            q_vals = np.asarray(q_arr, dtype=float) * dataset.q_scale
            q_now = float(q_vals[clamped_idx])

    p1 = None
    p2 = None
    if dataset.bundle.p is not None:
        if n1:
            p_arr = dataset.bundle.p.column(n1, default=None)
            if p_arr is not None:
                p1 = _finite_or_none(_bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)[clamped_idx])
        if n2:
            p_arr = dataset.bundle.p.column(n2, default=None)
            if p_arr is not None:
                p2 = _finite_or_none(_bar_g(np.asarray(p_arr, dtype=float), dataset.p_atm)[clamped_idx])

    component_kind = _edge_component_kind(selected_edge, edge_def)
    component_short = _component_kind_short_label(component_kind)
    state_label = _edge_open_state(dataset, selected_edge, clamped_idx)
    state_short = _state_short_label(state_label)
    zone_label = _edge_zone_label(selected_edge, edge_def)
    q_abs = abs(float(q_now))
    flow_source = n1 if q_now >= 0.0 else n2
    flow_sink = n2 if q_now >= 0.0 else n1
    flow_label = (
        f"{_short_node_label(flow_source)} → {_short_node_label(flow_sink)}"
        if q_abs > 1.0e-9 and flow_source and flow_sink
        else "Q на ветви пока близок к нулю"
    )

    delta_p_bar = None if p1 is None or p2 is None else float(p1 - p2)
    pressure_source = ""
    pressure_sink = ""
    if delta_p_bar is not None and abs(delta_p_bar) > 0.05:
        pressure_source = n1 if delta_p_bar >= 0.0 else n2
        pressure_sink = n2 if delta_p_bar >= 0.0 else n1
        pressure_label = f"{_short_node_label(pressure_source)} → {_short_node_label(pressure_sink)}"
    elif delta_p_bar is not None:
        pressure_label = "концы ветви близки к выравниванию"
    else:
        pressure_label = "давление на концах ветви недоступно"

    step_01_tone = "neutral"
    if state_short == "SHUT" and q_abs > 1.0e-9:
        step_01_tone = "warn"
    elif state_short == "OPEN":
        step_01_tone = "info"

    step_02_tone = "neutral"
    if delta_p_bar is not None and abs(delta_p_bar) > 0.05:
        step_02_tone = "info"
        if q_abs > 1.0e-9 and pressure_source and flow_source and pressure_source != flow_source:
            step_02_tone = "warn"

    step_03_tone = "neutral"
    if q_abs > 1.0e-9:
        step_03_tone = "warn" if state_short == "SHUT" else "ok"

    step_01_idx = clamped_idx
    if dataset.bundle.open is not None:
        open_arr = dataset.bundle.open.column(selected_edge, default=None)
        if open_arr is not None:
            open_vals = np.asarray(open_arr, dtype=int)
            change_idx = np.flatnonzero(np.diff(open_vals) != 0) + 1
            if change_idx.size:
                step_01_idx = int(change_idx[np.argmin(np.abs(change_idx - clamped_idx))])

    step_02_idx = clamped_idx
    if delta_p_bar is not None and dataset.bundle.p is not None and n1 and n2:
        p1_arr = dataset.bundle.p.column(n1, default=None)
        p2_arr = dataset.bundle.p.column(n2, default=None)
        if p1_arr is not None and p2_arr is not None:
            p1_vals = _bar_g(np.asarray(p1_arr, dtype=float), dataset.p_atm)
            p2_vals = _bar_g(np.asarray(p2_arr, dtype=float), dataset.p_atm)
            dp_vals = np.abs(np.asarray(p1_vals - p2_vals, dtype=float))
            if dp_vals.size:
                dp_peak = float(np.max(dp_vals))
                if dp_peak > 1.0e-9:
                    candidate_idx = np.flatnonzero(dp_vals >= max(0.05, dp_peak * 0.55))
                    if candidate_idx.size:
                        step_02_idx = int(candidate_idx[np.argmin(np.abs(candidate_idx - clamped_idx))])
                    else:
                        step_02_idx = int(np.argmax(dp_vals))

    step_03_idx = clamped_idx
    if dataset.bundle.q is not None:
        q_arr = dataset.bundle.q.column(selected_edge, default=None)
        if q_arr is not None:
            q_vals = np.abs(np.asarray(q_arr, dtype=float) * dataset.q_scale)
            if q_vals.size:
                q_peak = float(np.max(q_vals))
                if q_peak > 1.0e-9:
                    candidate_idx = np.flatnonzero(q_vals >= max(1.0e-6, q_peak * 0.55))
                    if candidate_idx.size:
                        step_03_idx = int(candidate_idx[np.argmin(np.abs(candidate_idx - clamped_idx))])
                    else:
                        step_03_idx = int(np.argmax(q_vals))

    step_rows = [
        {
            "index_label": "01",
            "phase_label": "SIG",
            "title": f"{component_short} / {state_label}",
            "tone": step_01_tone,
            "target_idx": step_01_idx,
            "target_time_s": float(dataset.time_s[step_01_idx]),
        },
        {
            "index_label": "02",
            "phase_label": "ΔP",
            "title": (
                f"{pressure_label} • {delta_p_bar:+0.2f} бар"
                if delta_p_bar is not None
                else pressure_label
            ),
            "tone": step_02_tone,
            "target_idx": step_02_idx,
            "target_time_s": float(dataset.time_s[step_02_idx]),
        },
        {
            "index_label": "03",
            "phase_label": "Q",
            "title": (
                f"{flow_label} • {q_abs:0.2f} {dataset.q_unit}"
                if q_abs > 1.0e-9
                else flow_label
            ),
            "tone": step_03_tone,
            "target_idx": step_03_idx,
            "target_time_s": float(dataset.time_s[step_03_idx]),
        },
    ]
    phase_items = [
        {
            "step_label": row["index_label"],
            "phase_label": row["phase_label"],
            "title": row["title"],
            "tone": row["tone"],
            "target_idx": row["target_idx"],
            "target_time_s": row["target_time_s"],
        }
        for row in step_rows
    ]

    terminal_markers: list[dict[str, Any]] = []
    if pressure_source and pressure_sink:
        terminal_markers.extend(
            [
                {"node_name": pressure_source, "step_label": "02", "badge_text": "P+", "tone": step_02_tone},
                {"node_name": pressure_sink, "step_label": "02", "badge_text": "P-", "tone": step_02_tone},
            ]
        )
    if q_abs > 1.0e-9 and flow_source and flow_sink:
        terminal_markers.extend(
            [
                {"node_name": flow_source, "step_label": "03", "badge_text": "SRC", "tone": step_03_tone},
                {"node_name": flow_sink, "step_label": "03", "badge_text": "SNK", "tone": step_03_tone},
            ]
        )

    return {
        "edge_name": selected_edge,
        "component_kind": component_kind,
        "component_short": component_short,
        "state_label": state_label,
        "state_short": state_short,
        "zone_label": zone_label,
        "q_now": q_now,
        "q_unit": dataset.q_unit,
        "q_abs": q_abs,
        "flow_label": flow_label,
        "flow_source": flow_source,
        "flow_sink": flow_sink,
        "n1": n1,
        "n2": n2,
        "p1_bar_g": p1,
        "p2_bar_g": p2,
        "delta_p_bar": delta_p_bar,
        "pressure_label": pressure_label,
        "pressure_source": pressure_source,
        "pressure_sink": pressure_sink,
        "phase_sequence_label": "SIG → ΔP → Q",
        "step_rows": step_rows,
        "phase_items": phase_items,
        "terminal_markers": terminal_markers,
    }


def _build_component_overlay_rows(
    dataset: MnemoDataset | None,
    idx: int,
    *,
    selected_edge: str | None,
) -> list[dict[str, Any]]:
    all_rows = _build_edge_activity_snapshots_full(dataset, idx)
    if not all_rows:
        return []

    selected_name = str(selected_edge or "")
    relevant_kinds = {
        "Обратный клапан",
        "Регулятор",
        "Дроссель",
        "Сброс",
        "Диагональ",
    }
    max_abs_flow = max((abs(float(item.q_now)) for item in all_rows), default=0.0)
    diagonal_floor = max_abs_flow * 0.08 if max_abs_flow > 1.0e-9 else 0.0

    payload_rows: list[dict[str, Any]] = []
    for order, item in enumerate(all_rows):
        if item.edge_name != selected_name and item.component_kind not in relevant_kinds:
            continue
        if item.edge_name != selected_name and item.component_kind == "Диагональ" and abs(float(item.q_now)) < diagonal_floor:
            continue
        flow_rgb = _flow_to_heat_rgb(item.q_now, max_abs_flow=max_abs_flow)
        edge_def = dataset.edge_defs.get(item.edge_name, {}) if dataset is not None else {}
        canonical_kind = str(edge_def.get("kind") or "")
        payload_rows.append(
            {
                "edge_name": item.edge_name,
                "component_kind": item.component_kind,
                "component_short": _component_kind_short_label(item.component_kind),
                "canonical_kind": canonical_kind,
                "canonical_kind_label": _canonical_kind_label(canonical_kind),
                "camozzi_code": str(edge_def.get("camozzi_code") or ""),
                "icon_key": _component_icon_key(item.component_kind, canonical_kind),
                "q_now": _finite_or_none(item.q_now),
                "flow_abs": _finite_or_none(abs(float(item.q_now))),
                "direction_label": item.direction_label,
                "state_label": item.state_label,
                "state_short": _state_short_label(item.state_label),
                "zone_label": item.zone_label,
                "corners": list(item.corners),
                "flow_hex": _rgb_hex(flow_rgb),
                "text_hex": _text_color_for_rgb(flow_rgb),
                "is_selected": bool(item.edge_name == selected_name),
                "is_active": bool(
                    abs(float(item.q_now)) >= max_abs_flow * 0.04 if max_abs_flow > 1.0e-9 else item.edge_name == selected_name
                ),
                "order": int(order),
            }
        )

    payload_rows.sort(
        key=lambda item: (
            0 if item.get("is_selected") else 1,
            -float(item.get("flow_abs") or 0.0),
            str(item.get("edge_name") or ""),
        )
    )
    return payload_rows[:18]


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


class MnemoNativeView(QtWidgets.QWidget):
    edge_picked = QtCore.Signal(str)
    node_picked = QtCore.Signal(str)
    status = QtCore.Signal(str)
    focus_step_jump_requested = QtCore.Signal(str, int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._detail_mode = "operator"
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        header = QtWidgets.QFrame(self)
        header.setObjectName("mnemo_native_header")
        header_lay = QtWidgets.QHBoxLayout(header)
        header_lay.setContentsMargins(12, 10, 12, 10)
        header_lay.setSpacing(12)

        self.mode_badge = QtWidgets.QLabel("Native Canvas", header)
        self.mode_badge.setObjectName("mnemo_native_mode_badge")
        self.mode_badge.setStyleSheet(
            "QLabel#mnemo_native_mode_badge {"
            "background:#102c36; color:#9fe7f7; border:1px solid #265563; "
            "border-radius:10px; padding:6px 10px; font-weight:700; }"
        )
        header_lay.addWidget(self.mode_badge, 0)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(2)
        self.summary_label = QtWidgets.QLabel(
            "Нативная Windows/Qt мнемосхема без WebEngine: один экран для давления, расходов, состояний арматуры и хода цилиндров.",
            header,
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color:#d9eef2; font-weight:600;")
        self.hint_label = QtWidgets.QLabel("Колесо: zoom • drag: pan • click: выбрать ветвь или узел", header)
        self.hint_label.setStyleSheet("color:#89aeb8;")
        text_col.addWidget(self.summary_label)
        text_col.addWidget(self.hint_label)
        header_lay.addLayout(text_col, 1)
        lay.addWidget(header, 0)

        self.native_canvas = MnemoNativeCanvas(self)
        self.native_canvas.edge_picked.connect(self.edge_picked.emit)
        self.native_canvas.node_picked.connect(self.node_picked.emit)
        self.native_canvas.status.connect(self.status.emit)
        self.native_canvas.focus_step_jump_requested.connect(self.focus_step_jump_requested.emit)
        lay.addWidget(self.native_canvas, 1)

    def render_dataset(self, dataset: MnemoDataset, *, selected_edge: str | None, selected_node: str | None) -> None:
        self.mode_badge.setText("Native Canvas")
        self.summary_label.setText(
            f"{dataset.npz_path.name}: нативный canvas держит full-system мнемосхему и живые overlays на одном экране."
            + (" Базовая ориентация идёт по исходной пневмосхеме проекта." if dataset.reference_scheme_source else "")
        )
        self.native_canvas.render_dataset(dataset, selected_edge=selected_edge, selected_node=selected_node)

    @staticmethod
    def _detail_mode_label(mode: str) -> str:
        return str(DETAIL_MODE_LABELS.get(str(mode or "").strip().lower(), DETAIL_MODE_LABELS["operator"]))

    def set_detail_mode(self, mode: str) -> None:
        self._detail_mode = self.native_canvas.set_detail_mode(mode)
        self.hint_label.setText(
            "Колесо: zoom • drag: pan • click: выбрать ветвь или узел"
            + f" • слой: {self._detail_mode_label(self._detail_mode)}"
        )

    def set_playhead(self, idx: int, playing: bool, dataset_id: str) -> None:
        self.mode_badge.setText("Playback" if playing else "Hold")
        self.native_canvas.set_frame_state(idx, playing, dataset_id)

    def set_selection(self, *, edge: str | None, node: str | None) -> None:
        label = edge or node or "Native Canvas"
        self.mode_badge.setText(str(label))
        self.native_canvas.set_selection(edge=edge, node=node)

    def set_alerts(self, alerts: dict[str, Any]) -> None:
        primary = dict(alerts.get("primary") or {})
        severity = str(primary.get("severity") or "")
        if primary:
            self.summary_label.setText(str(primary.get("summary") or self.summary_label.text()))
            if severity:
                self.mode_badge.setText(str(primary.get("title") or severity))
        self.native_canvas.set_alerts(alerts)

    def set_diagnostics(self, diagnostics: dict[str, Any]) -> None:
        fidelity = dict(diagnostics.get("scheme_fidelity") or {})
        canonical_nodes_positioned = int(fidelity.get("canonical_nodes_positioned") or 0)
        canonical_nodes_total = int(fidelity.get("canonical_nodes_total") or 0)
        canonical_edges_routed = int(fidelity.get("canonical_edges_routed") or 0)
        canonical_edges_total = int(fidelity.get("canonical_edges_total") or 0)
        warnings = len(list(diagnostics.get("geometry_warnings") or []))
        issues = len(list(diagnostics.get("geometry_issues") or []))
        reference_mode = str(fidelity.get("reference_scheme_mode") or "")
        self.hint_label.setText(
            "Native overlay: "
            + f"schema {canonical_nodes_positioned}/{canonical_nodes_total} nodes, "
            + f"{canonical_edges_routed}/{canonical_edges_total} routes, "
            + f"geometry {warnings}/{issues}"
            + (f" • фон {reference_mode}" if reference_mode else "")
            + f" • слой {self._detail_mode_label(self._detail_mode)}"
        )
        self.native_canvas.set_diagnostics(diagnostics)

    def set_reference_scheme_visible(self, visible: bool) -> bool:
        return self.native_canvas.set_reference_scheme_visible(visible)

    def set_focus_region(self, focus_region: dict[str, Any] | None) -> None:
        if focus_region:
            self.mode_badge.setText("Focus")
            self.summary_label.setText(str(focus_region.get("summary") or "Фокусный сценарий"))
        self.native_canvas.set_focus_region(focus_region)

    def show_overview(self, meta: dict[str, Any] | None = None) -> None:
        overview_meta = dict(meta or {})
        self.mode_badge.setText("Overview")
        self.summary_label.setText(
            str(overview_meta.get("summary") or "Полная схема: сравните активный сценарий с целой топологией и вернитесь к фокусу через toolbar.")
        )
        self.native_canvas.show_overview(overview_meta)


class CornerHeatmapWidget(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._cards: dict[str, dict[str, Any]] = {}
        self.setMinimumHeight(220)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_cards(self, cards: dict[str, dict[str, Any]]) -> None:
        self._cards = dict(cards or {})
        self.update()

    @staticmethod
    def _fmt(value: float | None, *, suffix: str, digits: int = 2) -> str:
        if value is None or not np.isfinite(value):
            return f"— {suffix}".strip()
        return f"{float(value):.{digits}f} {suffix}".strip()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        full_rect = self.rect().adjusted(8, 8, -8, -8)
        painter.fillRect(self.rect(), QtGui.QColor("#0b1720"))
        if full_rect.width() <= 20 or full_rect.height() <= 20:
            return

        if not self._cards:
            painter.setPen(QtGui.QColor("#8fb0bc"))
            painter.drawText(full_rect, QtCore.Qt.AlignCenter, "Теплокарта углов ждёт данные bundle.")
            return

        gap = 10
        cell_width = max(40, int((full_rect.width() - gap) / 2))
        cell_height = max(60, int((full_rect.height() - gap) / 2))
        title_font = QtGui.QFont(self.font())
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        body_font = QtGui.QFont(self.font())
        body_font.setPointSize(max(8, body_font.pointSize() - 1))
        caption_font = QtGui.QFont(self.font())
        caption_font.setPointSize(max(8, caption_font.pointSize() - 2))

        for index, corner in enumerate(CORNER_ORDER):
            row = 0 if index < 2 else 1
            col = index % 2
            left = full_rect.left() + col * (cell_width + gap)
            top = full_rect.top() + row * (cell_height + gap)
            rect = QtCore.QRectF(left, top, cell_width, cell_height)
            card = self._cards.get(corner, {})
            pressure_rgb = tuple(card.get("pressure_rgb", (34, 48, 58)))
            pressure_color = QtGui.QColor(*pressure_rgb)
            flow_rgb = tuple(card.get("dominant_flow_rgb", FLOW_IDLE_RGB))
            flow_color = QtGui.QColor(*flow_rgb)
            text_color = QtGui.QColor(_text_color_for_rgb(pressure_rgb))
            border_color = QtGui.QColor(flow_color)
            border_color.setAlpha(190)

            grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, pressure_color.lighter(118))
            grad.setColorAt(1.0, pressure_color.darker(235))
            painter.setBrush(QtGui.QBrush(grad))
            painter.setPen(QtGui.QPen(border_color, 1.6))
            painter.drawRoundedRect(rect, 14.0, 14.0)

            flow_bar_rect = QtCore.QRectF(rect.left() + 10.0, rect.bottom() - 16.0, rect.width() - 20.0, 7.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(18, 31, 40, 165))
            painter.drawRoundedRect(flow_bar_rect, 4.0, 4.0)
            painter.setBrush(flow_color)
            painter.drawRoundedRect(flow_bar_rect, 4.0, 4.0)

            painter.setPen(text_color)
            painter.setFont(title_font)
            painter.drawText(
                QtCore.QRectF(rect.left() + 12.0, rect.top() + 10.0, rect.width() - 24.0, 24.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                corner,
            )
            painter.setFont(body_font)
            painter.drawText(
                QtCore.QRectF(rect.left() + 12.0, rect.top() + 40.0, rect.width() - 24.0, 20.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"Pmax {self._fmt(card.get('max_pressure_bar_g'), suffix='бар(g)', digits=2)}",
            )
            painter.drawText(
                QtCore.QRectF(rect.left() + 12.0, rect.top() + 62.0, rect.width() - 24.0, 20.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"ΔPпик {self._fmt(card.get('delta_peak_bar'), suffix='бар', digits=2)}",
            )

            stroke_ratio = card.get("stroke_ratio")
            if stroke_ratio is None:
                stroke_text = "Ход —"
            else:
                stroke_text = f"Ход {int(round(100.0 * float(stroke_ratio))):d}%"
            stroke_speed = card.get("stroke_speed_m_s")
            if stroke_speed is None:
                speed_text = "vшт —"
            else:
                speed_text = f"vшт {float(stroke_speed):+0.3f} м/с"
            painter.drawText(
                QtCore.QRectF(rect.left() + 12.0, rect.top() + 84.0, rect.width() - 24.0, 20.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"{stroke_text} · {speed_text}",
            )

            painter.setFont(caption_font)
            painter.drawText(
                QtCore.QRectF(rect.left() + 12.0, rect.top() + 108.0, rect.width() - 24.0, 16.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                str(card.get("motion_label") or "нет сигнала"),
            )
            painter.drawText(
                QtCore.QRectF(rect.left() + 12.0, rect.bottom() - 38.0, rect.width() - 24.0, 16.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"Зона потока: {str(card.get('flow_zone_label') or '—')}",
            )


class PneumoSnapshotPanel(QtWidgets.QWidget):
    edge_selected = QtCore.Signal(str)
    node_selected = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.summary = QtWidgets.QTextBrowser()
        self.summary.setMaximumHeight(152)
        lay.addWidget(self.summary)

        self.heatmap = CornerHeatmapWidget(self)
        lay.addWidget(self.heatmap)

        lay.addWidget(self._section_label("Полости / штоки"))
        self.actuator_table = QtWidgets.QTableWidget(0, 9)
        self.actuator_table.setHorizontalHeaderLabels(
            ["Угол", "Цил", "P БП", "P ШП", "ΔP", "Ход", "vшт", "V БП", "V ШП"]
        )
        self.actuator_table.verticalHeader().setVisible(False)
        self.actuator_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.actuator_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.actuator_table.horizontalHeader().setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeToContents)
        for col in range(2, 8):
            self.actuator_table.horizontalHeader().setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        self.actuator_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.actuator_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.actuator_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.actuator_table.cellClicked.connect(self._actuator_clicked)
        lay.addWidget(self.actuator_table, 1)

        lay.addWidget(self._section_label("Активная арматура"))
        self.components_table = QtWidgets.QTableWidget(0, 6)
        self.components_table.setHorizontalHeaderLabels(
            ["Элемент", "Тип", "Q", "Направление", "Состояние", "Зона"]
        )
        self.components_table.verticalHeader().setVisible(False)
        self.components_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.components_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.components_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.components_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.components_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.components_table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        self.components_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.components_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.components_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.components_table.cellClicked.connect(self._component_clicked)
        lay.addWidget(self.components_table, 1)

    @staticmethod
    def _section_label(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-weight:700; color:#eef6f8; padding-top:4px;")
        return label

    @staticmethod
    def _fmt(value: float | None, *, suffix: str, digits: int = 2) -> str:
        if value is None or not np.isfinite(value):
            return "—"
        return f"{float(value):.{digits}f} {suffix}".strip()

    @staticmethod
    def _make_item(
        text: str,
        *,
        align: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignCenter,
        user_data: Any = None,
        background_rgb: tuple[int, int, int] | None = None,
    ) -> QtWidgets.QTableWidgetItem:
        item = QtWidgets.QTableWidgetItem(str(text))
        item.setTextAlignment(int(align | QtCore.Qt.AlignVCenter))
        if user_data is not None:
            item.setData(QtCore.Qt.UserRole, user_data)
        if background_rgb is not None:
            item.setBackground(QtGui.QBrush(QtGui.QColor(*background_rgb)))
            item.setForeground(QtGui.QBrush(QtGui.QColor(_text_color_for_rgb(background_rgb))))
        return item

    def _fill_actuator_table(self, rows: list[CylinderSnapshot]) -> None:
        max_abs_dp = max((abs(float(item.delta_p_bar)) for item in rows if item.delta_p_bar is not None), default=0.0)
        self.actuator_table.setRowCount(len(rows))
        for row_idx, item in enumerate(rows):
            stroke_rgb = _mix_rgb((24, 40, 50), FLOW_FORWARD_RGB, 0.0 if item.stroke_ratio is None else float(item.stroke_ratio))
            speed_rgb = _flow_to_heat_rgb(
                0.0 if item.stroke_speed_m_s is None else float(item.stroke_speed_m_s),
                max_abs_flow=max(
                    1.0e-6,
                    max((abs(float(row.stroke_speed_m_s)) for row in rows if row.stroke_speed_m_s is not None), default=0.0),
                ),
            )
            delta_rgb = _flow_to_heat_rgb(
                0.0 if item.delta_p_bar is None else float(item.delta_p_bar),
                max_abs_flow=max_abs_dp,
            )
            mode_suffix = "abs" if item.geometry_ready else "P only"
            self.actuator_table.setItem(
                row_idx,
                0,
                self._make_item(
                    item.corner,
                    align=QtCore.Qt.AlignLeft,
                    user_data={"node": item.focus_node},
                ),
            )
            self.actuator_table.setItem(row_idx, 1, self._make_item(f"Ц{item.cyl_index}"))
            self.actuator_table.setItem(
                row_idx,
                2,
                self._make_item(
                    self._fmt(item.cap.pressure_bar_g, suffix="бар(g)"),
                    background_rgb=_pressure_to_heat_rgb(item.cap.pressure_bar_g),
                ),
            )
            self.actuator_table.setItem(
                row_idx,
                3,
                self._make_item(
                    self._fmt(item.rod.pressure_bar_g, suffix="бар(g)"),
                    background_rgb=_pressure_to_heat_rgb(item.rod.pressure_bar_g),
                ),
            )
            self.actuator_table.setItem(
                row_idx,
                4,
                self._make_item(self._fmt(item.delta_p_bar, suffix="бар"), background_rgb=delta_rgb),
            )
            self.actuator_table.setItem(
                row_idx,
                5,
                self._make_item(
                    "—" if item.stroke_m is None else f"{float(item.stroke_m):0.3f} м / {0 if item.stroke_ratio is None else int(round(100.0 * float(item.stroke_ratio))):d}%",
                    background_rgb=stroke_rgb,
                ),
            )
            self.actuator_table.setItem(
                row_idx,
                6,
                self._make_item(
                    "—" if item.stroke_speed_m_s is None else f"{float(item.stroke_speed_m_s):+0.3f} м/с",
                    background_rgb=speed_rgb,
                ),
            )
            self.actuator_table.setItem(
                row_idx,
                7,
                self._make_item("—" if item.cap.volume_l is None else f"{float(item.cap.volume_l):0.2f} л"),
            )
            self.actuator_table.setItem(
                row_idx,
                8,
                self._make_item(
                    ("—" if item.rod.volume_l is None else f"{float(item.rod.volume_l):0.2f} л")
                    + f" · {mode_suffix}",
                    align=QtCore.Qt.AlignLeft,
                ),
            )
            self.actuator_table.setVerticalHeaderItem(row_idx, QtWidgets.QTableWidgetItem(item.motion_label))

    def _fill_components_table(self, dataset: MnemoDataset, rows: list[EdgeActivitySnapshot]) -> None:
        max_abs_flow = max((abs(float(item.q_now)) for item in rows), default=0.0)
        self.components_table.setRowCount(len(rows))
        for row_idx, item in enumerate(rows):
            flow_rgb = _flow_to_heat_rgb(float(item.q_now), max_abs_flow=max_abs_flow)
            state_rgb = (53, 110, 83) if item.state_label == "открыт" else ((83, 89, 94) if item.state_label == "закрыт" else (44, 57, 66))
            self.components_table.setItem(
                row_idx,
                0,
                self._make_item(
                    item.edge_name,
                    align=QtCore.Qt.AlignLeft,
                    user_data=item.edge_name,
                ),
            )
            self.components_table.setItem(row_idx, 1, self._make_item(item.component_kind))
            self.components_table.setItem(
                row_idx,
                2,
                self._make_item(f"{float(item.q_now):8.2f} {dataset.q_unit}", background_rgb=flow_rgb),
            )
            self.components_table.setItem(
                row_idx,
                3,
                self._make_item(item.direction_label, align=QtCore.Qt.AlignLeft),
            )
            self.components_table.setItem(
                row_idx,
                4,
                self._make_item(item.state_label, background_rgb=state_rgb),
            )
            self.components_table.setItem(
                row_idx,
                5,
                self._make_item(item.zone_label, align=QtCore.Qt.AlignLeft),
            )

    def update_frame(self, dataset: MnemoDataset | None, idx: int) -> None:
        if dataset is None or dataset.time_s.size == 0:
            self.summary.setHtml("<p>Snapshot ждёт NPZ bundle.</p>")
            self.heatmap.set_cards({})
            self.actuator_table.setRowCount(0)
            self.components_table.setRowCount(0)
            return

        clamped_idx = int(max(0, min(idx, dataset.time_s.size - 1)))
        time_s = float(dataset.time_s[clamped_idx])
        narrative = _build_frame_narrative(dataset, clamped_idx, selected_edge=None, selected_node=None)
        cylinder_rows = _build_cylinder_snapshots(dataset, clamped_idx)
        edge_rows = _build_edge_activity_snapshots(dataset, clamped_idx)
        corner_cards = _build_corner_snapshot_cards(cylinder_rows, edge_rows)
        geometry_ready = sum(1 for item in cylinder_rows if item.geometry_ready)
        fastest = max(
            (item for item in cylinder_rows if item.stroke_speed_m_s is not None),
            key=lambda item: abs(float(item.stroke_speed_m_s)),
            default=None,
        )
        geometry_note = f"Абсолютные объёмы доступны для {geometry_ready}/{len(cylinder_rows)} цилиндров."
        if dataset.geometry_issues:
            geometry_note += " Есть contract-issues в geometry."
        elif dataset.geometry_warnings:
            geometry_note += " Geometry читается с предупреждениями."

        fastest_text = "Самый быстрый шток: нет сигнала."
        if fastest is not None and fastest.stroke_speed_m_s is not None:
            fastest_text = (
                f"Самый быстрый шток: {fastest.corner} / Ц{fastest.cyl_index} "
                f"{float(fastest.stroke_speed_m_s):+0.3f} м/с."
            )

        active_devices = [item for item in edge_rows if item.state_label == "открыт"]
        self.summary.setHtml(
            "<b>Snapshot:</b> "
            + escape(narrative.primary_title)
            + f"<br/><b>t:</b> {time_s:0.3f} s"
            + f"<br/><b>Активная арматура:</b> {len(active_devices)} из {len(edge_rows)} верхних ветвей открыты."
            + f"<br/><b>{escape(fastest_text)}</b>"
            + f"<br/><b>Geometry:</b> {escape(geometry_note)}"
        )
        self.heatmap.set_cards(corner_cards)
        self._fill_actuator_table(cylinder_rows)
        self._fill_components_table(dataset, edge_rows)

    def _actuator_clicked(self, row: int, _column: int) -> None:
        item = self.actuator_table.item(row, 0)
        payload = item.data(QtCore.Qt.UserRole) if item is not None else None
        if isinstance(payload, dict):
            node_name = str(payload.get("node") or "")
            if node_name:
                self.node_selected.emit(node_name)

    def _component_clicked(self, row: int, _column: int) -> None:
        item = self.components_table.item(row, 0)
        edge_name = str(item.data(QtCore.Qt.UserRole) or item.text()) if item is not None else ""
        if edge_name:
            self.edge_selected.emit(edge_name)


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
                edge_meta = dict(dataset.mapping.get("edges_meta", {}).get(edge_name) or {})
                endpoint_1 = str(edge_def.get("n1") or "—")
                endpoint_2 = str(edge_def.get("n2") or "—")
                component_kind = _edge_component_kind(edge_name, edge_def)
                canonical_kind = str(edge_def.get("kind") or "")
                route_class = str(edge_meta.get("mnemo_route") or "—")
                zone_label = _edge_zone_label(edge_name, edge_def)
                direction_meta = _edge_direction_meta(edge_def, q_now)
                p1_now, _, _ = _pressure_triplet(dataset, idx, endpoint_1)
                p2_now, _, _ = _pressure_triplet(dataset, idx, endpoint_2)
                element_meta = _edge_element_flow_contract_meta(
                    canonical_kind,
                    component_kind,
                    direction_meta,
                    q_now=q_now,
                )
                pressure_meta = _edge_pressure_drive_meta(
                    direction_meta,
                    p1_bar_g=p1_now,
                    p2_bar_g=p2_now,
                    q_now=q_now,
                )
                camozzi_code = str(edge_def.get("camozzi_code") or "").strip() or "—"
                state = "открыт"
                if open_arr is not None:
                    state = "открыт" if int(np.asarray(open_arr, dtype=int)[idx]) else "закрыт"
                operability_meta = _edge_operability_meta(
                    state,
                    q_now=q_now,
                    pressure_meta=pressure_meta,
                    element_meta=element_meta,
                )
                consistency_meta = _edge_consistency_meta(
                    state,
                    q_now=q_now,
                    pressure_meta=pressure_meta,
                    element_meta=element_meta,
                )
                temporal_meta = _edge_temporal_meta(
                    time_s=dataset.time_s,
                    q_values=q_vals,
                    open_values=None if open_arr is None else np.asarray(open_arr, dtype=int),
                    idx=idx,
                )
                pressure_history_meta = _edge_recent_pressure_meta(
                    time_s=dataset.time_s,
                    p1_values=None if endpoint_1 == "" or dataset.bundle.p is None else _bar_g(np.asarray(dataset.bundle.p.column(endpoint_1, default=[]), dtype=float), dataset.p_atm),
                    p2_values=None if endpoint_2 == "" or dataset.bundle.p is None else _bar_g(np.asarray(dataset.bundle.p.column(endpoint_2, default=[]), dtype=float), dataset.p_atm),
                    idx=idx,
                )
                history_meta = _edge_recent_history_meta(
                    time_s=dataset.time_s,
                    q_values=q_vals,
                    open_values=None if open_arr is None else np.asarray(open_arr, dtype=int),
                    idx=idx,
                )
                causality_meta = _edge_recent_causality_meta(
                    state_label=state,
                    history_meta=history_meta,
                    pressure_meta=pressure_history_meta,
                    temporal_meta=temporal_meta,
                    consistency_meta=consistency_meta,
                )
                latency_meta = _edge_recent_latency_meta(
                    time_s=dataset.time_s,
                    q_values=q_vals,
                    open_values=None if open_arr is None else np.asarray(open_arr, dtype=int),
                    p1_values=None if endpoint_1 == "" or dataset.bundle.p is None else _bar_g(np.asarray(dataset.bundle.p.column(endpoint_1, default=[]), dtype=float), dataset.p_atm),
                    p2_values=None if endpoint_2 == "" or dataset.bundle.p is None else _bar_g(np.asarray(dataset.bundle.p.column(endpoint_2, default=[]), dtype=float), dataset.p_atm),
                    idx=idx,
                )
                phase_ribbon_meta = _edge_phase_ribbon_meta(latency_meta)
                operator_hint_meta = _edge_operator_hint_meta(
                    component_kind=component_kind,
                    canonical_kind=canonical_kind,
                    operability_status=str(operability_meta.get("operability_status") or ""),
                    consistency_status=str(consistency_meta.get("consistency_status") or ""),
                    pressure_drive_status=str(pressure_meta.get("pressure_drive_status") or ""),
                    latency_status=str(latency_meta.get("latency_status") or ""),
                    phase_ribbon_bottleneck_kind=str(phase_ribbon_meta.get("phase_ribbon_bottleneck_kind") or ""),
                    phase_ribbon_bottleneck_comment=str(phase_ribbon_meta.get("phase_ribbon_bottleneck_comment") or ""),
                    phase_ribbon_focus_hint=str(phase_ribbon_meta.get("phase_ribbon_focus_hint") or ""),
                )
                operator_checklist_meta = _edge_operator_checklist_meta(
                    component_kind=component_kind,
                    canonical_kind=canonical_kind,
                    operator_hint_badge=str(operator_hint_meta.get("operator_hint_badge") or ""),
                    phase_ribbon_bottleneck_kind=str(phase_ribbon_meta.get("phase_ribbon_bottleneck_kind") or ""),
                    operability_status=str(operability_meta.get("operability_status") or ""),
                    consistency_status=str(consistency_meta.get("consistency_status") or ""),
                )
                chunks.append(
                    "<p><b>Ветка:</b> "
                    + escape(edge_name)
                    + "<br/><b>Текущее Q:</b> "
                    + f"{q_now:8.2f} {dataset.q_unit}"
                    + "<br/><b>Пик |Q|:</b> "
                    + f"{q_peak:8.2f} {dataset.q_unit}"
                    + "<br/><b>Состояние:</b> "
                    + escape(state)
                    + "<br/><b>Элемент:</b> "
                    + escape(component_kind)
                    + " / "
                    + escape(_canonical_kind_label(canonical_kind))
                    + "<br/><b>Маршрут:</b> "
                    + escape(endpoint_1)
                    + " → "
                    + escape(endpoint_2)
                    + "<br/><b>Паспортное направление:</b> "
                    + escape(str(direction_meta.get("canonical_direction_label") or "—"))
                    + "<br/><b>Поток в кадре:</b> "
                    + escape(str(direction_meta.get("flow_direction_label") or "—"))
                    + "<br/><b>Статус направления:</b> "
                    + escape(str(direction_meta.get("flow_status_label") or "—"))
                    + "<br/><b>Элемент vs поток:</b> "
                    + escape(str(element_meta.get("element_flow_status") or "—"))
                    + "<br/><b>Комментарий элемента:</b> "
                    + escape(str(element_meta.get("element_flow_label") or "—"))
                    + "<br/><b>Источник / приёмник:</b> "
                    + escape(
                        (
                            f"{direction_meta.get('flow_source_short') or '—'} → {direction_meta.get('flow_sink_short') or '—'}"
                            if direction_meta.get("flow_source_short")
                            else "неустойчиво / пауза"
                        )
                    )
                    + "<br/><b>Концы ветви:</b> "
                    + escape(str(direction_meta.get("endpoint_1_short") or "—"))
                    + " "
                    + ("—" if p1_now is None else f"{float(p1_now):0.2f} бар(g)")
                    + " / "
                    + escape(str(direction_meta.get("endpoint_2_short") or "—"))
                    + " "
                    + ("—" if p2_now is None else f"{float(p2_now):0.2f} бар(g)")
                    + "<br/><b>ΔP ветви (n1-n2):</b> "
                    + ("—" if pressure_meta.get("delta_p_bar") is None else f"{float(pressure_meta.get('delta_p_bar') or 0.0):+0.2f} бар")
                    + "<br/><b>Ведущее давление:</b> "
                    + escape(str(pressure_meta.get("pressure_drive_label") or "—"))
                    + "<br/><b>Q vs ΔP:</b> "
                    + escape(str(pressure_meta.get("flow_vs_pressure") or "—"))
                    + "<br/><b>Оценка ΔP:</b> "
                    + escape(str(pressure_meta.get("pressure_drive_status") or "—"))
                    + "<br/><b>Инженерный verdict:</b> "
                    + escape(str(operability_meta.get("operability_status") or "—"))
                    + "<br/><b>Комментарий verdict:</b> "
                    + escape(str(operability_meta.get("operability_label") or "—"))
                    + "<br/><b>Согласованность сигналов:</b> "
                    + escape(str(consistency_meta.get("consistency_status") or "—"))
                    + "<br/><b>Комментарий согласованности:</b> "
                    + escape(str(consistency_meta.get("consistency_label") or "—"))
                    + "<br/><b>Временной ход:</b> "
                    + escape(str(temporal_meta.get("temporal_status") or "—"))
                    + "<br/><b>Комментарий хода:</b> "
                    + escape(str(temporal_meta.get("temporal_label") or "—"))
                    + "<br/><b>Окно анализа:</b> "
                    + f"{float(temporal_meta.get('window_s') or 0.0):0.2f} s"
                    + " / dQ/dt "
                    + (
                        "—"
                        if temporal_meta.get("dq_dt") is None
                        else f"{float(temporal_meta.get('dq_dt') or 0.0):+0.2f} {dataset.q_unit}/s"
                    )
                    + "<br/><b>Последнее окно:</b> "
                    + escape(_edge_recent_history_summary(history_meta, dataset.q_unit))
                    + "<br/><b>ΔP-контур:</b> "
                    + escape(_edge_recent_pressure_summary(pressure_history_meta))
                    + "<br/><b>Причинная связка:</b> "
                    + escape(str(causality_meta.get("causality_status") or "—"))
                    + "<br/><b>Комментарий связки:</b> "
                    + escape(str(causality_meta.get("causality_label") or "—"))
                    + "<br/><b>Лаг реакции:</b> "
                    + escape(str(latency_meta.get("latency_status") or "—"))
                    + "<br/><b>Комментарий лага:</b> "
                    + escape(str(latency_meta.get("latency_label") or "—"))
                    + "<br/><b>Фаза окна:</b> "
                    + escape(str(latency_meta.get("latency_phase_label") or "—"))
                    + "<br/><b>Фазовая лента:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_label") or "—"))
                    + "<br/><b>Интервалы фаз:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_interval_label") or "—"))
                    + "<br/><b>Узкое место фазы:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_bottleneck_label") or "—"))
                    + "<br/><b>Тип узкого места:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_bottleneck_kind") or "—"))
                    + "<br/><b>Комментарий узкого места:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_bottleneck_comment") or "—"))
                    + "<br/><b>Фокус узкого места:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_focus_pair_label") or "—"))
                    + "<br/><b>Подсказка фокуса:</b> "
                    + escape(str(phase_ribbon_meta.get("phase_ribbon_focus_hint") or "—"))
                    + "<br/><b>Операторский приоритет:</b> "
                    + escape(str(operator_hint_meta.get("operator_hint_title") or "—"))
                    + "<br/><b>Комментарий приоритета:</b> "
                    + escape(str(operator_hint_meta.get("operator_hint_label") or "—"))
                    + "<br/><b>Чек-лист разбора:</b> "
                    + escape(str(operator_checklist_meta.get("operator_checklist_summary") or "—"))
                    + "".join(
                        "<br/>"
                        + escape(str(item.get("index_label") or "•"))
                        + " "
                        + escape(str(item.get("title") or "—"))
                        for item in list(operator_checklist_meta.get("operator_checklist_rows") or [])[:3]
                    )
                    + "<br/><b>Зона:</b> "
                    + escape(zone_label)
                    + "<br/><b>Класс прокладки:</b> "
                    + escape(route_class)
                    + "<br/><b>Каталог / серия:</b> "
                    + escape(camozzi_code)
                    + "</p>"
                )
                focus_meta = _build_selected_edge_focus_meta(dataset, idx, edge_name=edge_name)
                if focus_meta:
                    steps_html = "".join(
                        "<li><b>"
                        + escape(str(item.get("index_label") or "—"))
                        + " "
                        + escape(str(item.get("phase_label") or "—"))
                        + ":</b> "
                        + escape(str(item.get("title") or "—"))
                        + (
                            ""
                            if item.get("target_time_s") is None
                            else f" <span style='color:#8fb0bc;'>@ t≈{float(item.get('target_time_s') or 0.0):0.3f}s</span>"
                        )
                        + "</li>"
                        for item in list(focus_meta.get("step_rows") or [])[:3]
                    )
                    chunks.append(
                        "<p><b>Инженерный фокус ветви:</b> "
                        + escape(str(focus_meta.get("phase_sequence_label") or "SIG → ΔP → Q"))
                        + "<br/><b>Зона:</b> "
                        + escape(str(focus_meta.get("zone_label") or "—"))
                        + "<br/><b>Что искать на схеме:</b> "
                        + "шаги уже подсвечены на фазовой ленте и концах выбранной ветви.</p>"
                        + "<ol style='margin:0 0 8px 18px; padding:0;'>"
                        + steps_html
                        + "</ol>"
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
                chamber_context = _find_cylinder_snapshot_for_node(_build_cylinder_snapshots(dataset, idx), node_name)
                if chamber_context is not None:
                    cylinder_snapshot, chamber_snapshot = chamber_context
                    sister_snapshot = cylinder_snapshot.rod if chamber_snapshot.chamber_key == "БП" else cylinder_snapshot.cap
                    chunks.append(
                        "<p><b>Исполнительный контур:</b> "
                        + f"Ц{cylinder_snapshot.cyl_index} / {escape(cylinder_snapshot.corner)}"
                        + "<br/><b>Ход штока:</b> "
                        + ("—" if cylinder_snapshot.stroke_m is None else f"{cylinder_snapshot.stroke_m:0.3f} м")
                        + (""
                           if cylinder_snapshot.stroke_ratio is None
                           else f" ({int(round(100.0 * cylinder_snapshot.stroke_ratio))}% хода)")
                        + "<br/><b>Скорость штока:</b> "
                        + ("—" if cylinder_snapshot.stroke_speed_m_s is None else f"{cylinder_snapshot.stroke_speed_m_s:+0.3f} м/с")
                        + "<br/><b>Парная полость:</b> "
                        + escape(sister_snapshot.node_name)
                        + " / "
                        + ("—" if sister_snapshot.pressure_bar_g is None else f"{sister_snapshot.pressure_bar_g:0.2f} бар(g)")
                        + "<br/><b>ΔP БП-ШП:</b> "
                        + ("—" if cylinder_snapshot.delta_p_bar is None else f"{cylinder_snapshot.delta_p_bar:+0.2f} бар")
                        + "<br/><b>Объём текущей полости:</b> "
                        + ("—" if chamber_snapshot.volume_l is None else f"{chamber_snapshot.volume_l:0.2f} л")
                        + "<br/><b>Режим:</b> "
                        + escape(cylinder_snapshot.motion_label)
                        + "</p>"
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


class SchemeFidelityPanel(QtWidgets.QTextBrowser):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)

    @staticmethod
    def _badge(status: str) -> str:
        palette = {
            "ok": ("#81e7a3", "#0f2a1c"),
            "attention": ("#f8c15c", "#2b1c09"),
            "warn": ("#f0936b", "#30150f"),
        }
        fg, bg = palette.get(str(status), ("#9cb9c7", "#17252d"))
        return (
            f'<span style="display:inline-block; padding:2px 8px; border-radius:999px; '
            f'background:{bg}; color:{fg}; font-weight:700; font-size:11px;">{escape(str(status).upper())}</span>'
        )

    @staticmethod
    def _route_counts_html(route_counts: dict[str, Any]) -> str:
        if not route_counts:
            return "нет данных"
        return " • ".join(f"{escape(str(name))}: {int(count)}" for name, count in sorted(route_counts.items()))

    @staticmethod
    def _issue_list_html(items: list[str], *, empty_text: str, limit: int = 8) -> str:
        if not items:
            return f"<p>{escape(empty_text)}</p>"
        preview = "".join(f"<li>{escape(str(item))}</li>" for item in items[:limit])
        tail = ""
        if len(items) > limit:
            tail = f"<li>… ещё {len(items) - limit}</li>"
        return f"<ul>{preview}{tail}</ul>"

    def render(self, dataset: MnemoDataset | None) -> None:
        if dataset is None:
            self.setHtml(
                "<h3>Соответствие схеме</h3>"
                "<p>Панель проверяет, насколько native-мнемосхема совпадает с canonical-пневмосхемой из "
                "<code>PNEUMO_SCHEME.json</code>.</p>"
                "<p>После загрузки bundle здесь появятся покрытие узлов, маршрутов и все отклонения без web-прослойки.</p>"
            )
            return

        fidelity = dict(dataset.scheme_fidelity or {})
        reference_scheme_source = str(fidelity.get("reference_scheme_source") or "—")
        reference_scheme_mode = str(fidelity.get("reference_scheme_mode") or "semantic_fallback")
        reference_scheme_image_source = str(fidelity.get("reference_scheme_image_source") or "—")
        reference_component_nodes_snapped = int(fidelity.get("reference_component_nodes_snapped") or 0)
        reference_component_nodes_total = int(fidelity.get("reference_component_nodes_total") or 0)
        reference_indicator_nodes_snapped = int(fidelity.get("reference_indicator_nodes_snapped") or 0)
        reference_indicator_nodes_total = int(fidelity.get("reference_indicator_nodes_total") or 0)
        reference_chamber_nodes_snapped = int(fidelity.get("reference_chamber_nodes_snapped") or 0)
        reference_chamber_nodes_total = int(fidelity.get("reference_chamber_nodes_total") or 0)
        reference_diagonal_nodes_locked = int(fidelity.get("reference_diagonal_nodes_geometry_locked") or 0)
        reference_diagonal_nodes_total = int(fidelity.get("reference_diagonal_nodes_total") or 0)
        self.setHtml(
            "<h3>Соответствие схеме</h3>"
            + "<p>"
            + self._badge(str(fidelity.get("status") or "ok"))
            + f" <span style='margin-left:8px;'>{escape(str(fidelity.get('summary') or ''))}</span></p>"
            + f"<p><b>Bundle:</b> {escape(str(fidelity.get('bundle_summary') or ''))}</p>"
            + "<p><b>Source-of-truth:</b><br/>"
            + f"native underlay = {escape(reference_scheme_mode)}"
            + f"<br/>svg = <code>{escape(reference_scheme_source)}</code>"
            + f"<br/>image = <code>{escape(reference_scheme_image_source)}</code>"
            + f"<br/>component anchors = {reference_component_nodes_snapped}/{reference_component_nodes_total}"
            + f"<br/>critical indicator anchors = {reference_indicator_nodes_snapped}/{reference_indicator_nodes_total}"
            + f"<br/>chamber indicator anchors = {reference_chamber_nodes_snapped}/{reference_chamber_nodes_total}"
            + f"<br/>diagonal geometry from source scheme = {reference_diagonal_nodes_locked}/{reference_diagonal_nodes_total}</p>"
            + "<p><b>Canonical layout:</b><br/>"
            + f"узлы {int(fidelity.get('canonical_nodes_positioned') or 0)}/{int(fidelity.get('canonical_nodes_total') or 0)}"
            + " • "
            + f"ветви {int(fidelity.get('canonical_edges_routed') or 0)}/{int(fidelity.get('canonical_edges_total') or 0)}</p>"
            + "<p><b>Профиль маршрутов:</b><br/>"
            + escape(self._route_counts_html(dict(fidelity.get("canonical_route_counts") or {})))
            + "</p>"
            + "<p><b>Проблемы canonical layout:</b></p>"
            + self._issue_list_html(
                list(fidelity.get("canonical_missing_nodes") or []) + list(fidelity.get("canonical_route_issues") or []),
                empty_text="Критичных расхождений между mnemonic layout и canonical-схемой не найдено.",
            )
            + "<p><b>Отклонения текущего bundle:</b></p>"
            + self._issue_list_html(
                list(fidelity.get("bundle_extra_edges") or [])
                + list(fidelity.get("bundle_extra_nodes") or [])
                + list(fidelity.get("bundle_route_issues") or []),
                empty_text="Все текущие ветви и pressure-узлы распознаны в рамках canonical-словаря.",
            )
            + (
                "<p><b>Geometry contract:</b> есть issues/warnings, проверьте панель приводов и diagnostics.</p>"
                if dataset.geometry_issues or dataset.geometry_warnings
                else "<p><b>Geometry contract:</b> читается чисто.</p>"
            )
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
        selected_edge: str | None = None,
        selected_node: str | None = None,
        prefer_selected_focus: bool = False,
    ) -> None:
        self.title_label.setText(context.title)
        narrative = _build_frame_narrative(dataset, idx, selected_edge=None, selected_node=None)
        focus_target = build_onboarding_focus_target(
            dataset,
            idx,
            selected_edge=selected_edge,
            selected_node=selected_node,
            prefer_selected=prefer_selected_focus,
        )
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
        if context.startup_time_s is not None:
            badges.append(
                self._pill(
                    f"jump {context.startup_time_s:0.3f} s",
                    fg="#f7d18b",
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
            startup_jump_html = ""
            if context.startup_time_s is not None:
                startup_jump_html = (
                    f"<br/><b>Стартовый jump:</b> "
                    f"{escape(context.startup_time_label or f'{context.startup_time_s:0.3f} s')}"
                )
            focus_block = (
                "<p style='margin:8px 0 0 0;'>"
                f"<b>Первый инженерный фокус:</b> {escape(narrative.top_edge_name)} / {escape(narrative.top_node_name)}"
                f"<br/><b>Текущий режим:</b> {escape(narrative.primary_title)}"
                f"<br/><b>Подсветка onboarding:</b> {escape(focus_target.edge_name or '—')} / {escape(focus_target.node_name or '—')}"
                f"{startup_jump_html}"
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
        self._last_startup_anchor_signature = ""

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

    @staticmethod
    def _event_anchor(event: MnemoTimelineEvent) -> str:
        raw = (
            f"{event.kind}|{event.severity}|{event.frame_idx}|{event.time_s:0.6f}|"
            f"{event.title}|{event.edge_name}|{event.node_name}"
        )
        return f"event_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:14]}"

    @staticmethod
    def _event_card_style(*, highlighted: bool, accent: str) -> str:
        if highlighted:
            return (
                "margin:0 0 8px 0; padding:10px 12px; border-radius:12px; "
                f"background:rgba(27,55,68,0.92); border:1px solid {accent}; "
                "box-shadow:0 0 0 1px rgba(238,246,248,0.05) inset;"
            )
        return (
            "margin:0 0 8px 0; padding:8px 10px; border-radius:12px; "
            "background:rgba(10,27,34,0.72); border:1px solid rgba(99,211,245,0.10);"
        )

    def render(
        self,
        dataset: MnemoDataset | None,
        idx: int,
        *,
        tracker: MnemoEventTracker,
        playing: bool,
        follow_enabled: bool,
        startup_event: MnemoTimelineEvent | None = None,
        startup_time_label: str = "",
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
        startup_anchor = self._event_anchor(startup_event) if startup_event is not None else ""
        startup_anchor_signature = f"{dataset.dataset_id}:{startup_anchor}" if startup_anchor else ""

        live_badges = "".join(self._severity_badge(mode.severity, mode.title) for mode in live_modes)
        if not live_badges:
            live_badges = self._severity_badge("ok", "Спокойный кадр")

        active_rows: list[str] = []
        for event in active_latched:
            event_anchor = self._event_anchor(event)
            is_startup_event = bool(startup_anchor and event_anchor == startup_anchor)
            active_rows.append(
                f'<a name="{event_anchor}"></a>'
                + f'<div style="{self._event_card_style(highlighted=is_startup_event, accent="#f8c15c")}">'
                + (self._severity_badge("focus", "START") + " " if is_startup_event else "")
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
            event_anchor = self._event_anchor(event)
            is_startup_event = bool(startup_anchor and event_anchor == startup_anchor)
            acked_rows.append(
                f'<a name="{event_anchor}"></a>'
                + f'<div style="{self._event_card_style(highlighted=is_startup_event, accent="#81e7a3")}">'
                + (self._severity_badge("focus", "START") + " " if is_startup_event else "")
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
            event_anchor = self._event_anchor(event)
            is_startup_event = bool(startup_anchor and event_anchor == startup_anchor)
            recent_rows.append(
                f'<a name="{event_anchor}"></a>'
                + f"<div style='{self._event_card_style(highlighted=is_startup_event, accent='#63d3f5')}'>"
                + (self._severity_badge("focus", "START") + " " if is_startup_event else "")
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
        startup_summary_html = ""
        if startup_event is not None:
            startup_summary_html = (
                "<h4>Стартовая запись event-memory</h4>"
                '<div style="margin:0 0 10px 0; padding:10px 12px; border-radius:14px; '
                'background:rgba(16,38,48,0.92); border:1px solid rgba(99,211,245,0.22);">'
                + self._severity_badge("focus", "START")
                + " "
                + self._severity_badge(startup_event.severity, startup_event.title)
                + f"<div style='margin-top:6px; color:#d2e1e8;'>{escape(startup_event.summary)}</div>"
                + f"<div style='margin-top:4px; color:#8fb0bc;'>"
                + escape(startup_time_label or f"{startup_event.time_s:0.3f} s")
                + (f" • {escape(startup_event.edge_name)}" if startup_event.edge_name else "")
                + (f" • {escape(startup_event.node_name)}" if startup_event.node_name else "")
                + "</div>"
                + "<div style='margin-top:4px; color:#8fb0bc;'>Панель прокручена к этой записи один раз при открытии окна.</div>"
                + "</div>"
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
             + startup_summary_html
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
        if startup_anchor_signature and startup_anchor_signature != self._last_startup_anchor_signature:
            self._last_startup_anchor_signature = startup_anchor_signature
            QtCore.QTimer.singleShot(0, lambda anchor=startup_anchor: self.scrollToAnchor(anchor))
        elif not startup_anchor_signature:
            self._last_startup_anchor_signature = ""


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
            self.stroke_plot = None
            self.flow_curve = None
            self.pressure_curve = None
            self.stroke_curve = None
            self.flow_marker = None
            self.pressure_marker = None
            self.stroke_marker = None
            return

        assert pg is not None
        self.flow_plot = pg.PlotWidget()
        self.pressure_plot = pg.PlotWidget()
        self.stroke_plot = pg.PlotWidget()
        for plot in (self.flow_plot, self.pressure_plot, self.stroke_plot):
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
        self.stroke_plot.setLabel("left", "sшт", units="м")
        self.stroke_plot.setLabel("bottom", "t", units="s")

        self.flow_curve = self.flow_plot.plot(pen=pg.mkPen("#63d3f5", width=2), name="Q")
        self.pressure_curve = self.pressure_plot.plot(pen=pg.mkPen("#81e7a3", width=2), name="P")
        self.stroke_curve = self.stroke_plot.plot(pen=pg.mkPen("#f8c15c", width=2), name="sшт")
        self.flow_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#f8c15c", width=1.2))
        self.pressure_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#f8c15c", width=1.2))
        self.stroke_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#63d3f5", width=1.2))
        self.flow_plot.addItem(self.flow_marker)
        self.pressure_plot.addItem(self.pressure_marker)
        self.stroke_plot.addItem(self.stroke_marker)

    def set_series(self, dataset: MnemoDataset | None, *, edge_name: str | None, node_name: str | None) -> None:
        if not self._has_pg or dataset is None:
            return
        assert self.flow_curve is not None
        assert self.pressure_curve is not None
        assert self.stroke_curve is not None
        assert self.flow_plot is not None
        assert self.pressure_plot is not None
        assert self.stroke_plot is not None

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

        focus_corner = _focus_corner_from_selection(dataset, edge_name=edge_name, node_name=node_name)
        if focus_corner:
            stroke_arr = dataset.bundle.main.column(f"положение_штока_{focus_corner}_м", default=None)
            if stroke_arr is not None:
                stroke_vals = np.asarray(stroke_arr, dtype=float)
                self.stroke_curve.setData(dataset.time_s, stroke_vals, name=focus_corner)
                self.stroke_plot.setTitle(f"Шток: {focus_corner}", color="#d9e6ed")
            else:
                self.stroke_curve.setData([], [])
                self.stroke_plot.setTitle("Шток: нет сигнала", color="#88a3af")
        else:
            self.stroke_curve.setData([], [])
            self.stroke_plot.setTitle("Шток: выберите полость/угол", color="#88a3af")

    def set_index(self, dataset: MnemoDataset | None, idx: int) -> None:
        if not self._has_pg or dataset is None or dataset.time_s.size == 0:
            return
        time_value = float(dataset.time_s[max(0, min(idx, dataset.time_s.size - 1))])
        assert self.flow_marker is not None
        assert self.pressure_marker is not None
        assert self.stroke_marker is not None
        self.flow_marker.setValue(time_value)
        self.pressure_marker.setValue(time_value)
        self.stroke_marker.setValue(time_value)


class MnemoNativeCanvas(QtWidgets.QWidget):
    edge_picked = QtCore.Signal(str)
    node_picked = QtCore.Signal(str)
    status = QtCore.Signal(str)
    focus_step_jump_requested = QtCore.Signal(str, int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("mnemo_native_canvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumSize(760, 520)

        self._scene_rect = QtCore.QRectF(0.0, 0.0, VIEWBOX_W, VIEWBOX_H)
        self._camera_rect = QtCore.QRectF(self._scene_rect)
        self._camera_target_rect: QtCore.QRectF | None = None
        self._dataset: MnemoDataset | None = None
        self._dataset_id = ""
        self._detail_mode = "operator"
        self._frame_idx = 0
        self._playing = False
        self._selected_edge = ""
        self._selected_node = ""
        self._alerts: dict[str, Any] = {}
        self._diagnostics: dict[str, Any] = {}
        self._focus_region: dict[str, Any] | None = None
        self._overview_meta: dict[str, Any] = {}
        self._mode = "overview"
        self._edge_series_map: dict[str, dict[str, Any]] = {}
        self._node_series_map: dict[str, dict[str, Any]] = {}
        self._edge_paths: dict[str, QtGui.QPainterPath] = {}
        self._edge_hit_paths: dict[str, QtGui.QPainterPath] = {}
        self._edge_midpoints: dict[str, QtCore.QPointF] = {}
        self._node_points: dict[str, QtCore.QPointF] = {}
        self._node_hit_rects: dict[str, QtCore.QRectF] = {}
        self._overlay_targets: list[tuple[str, str, QtCore.QRectF]] = []
        self._svg_renderer: Any = None
        self._reference_svg_renderer: Any = None
        self._reference_scheme_source = ""
        self._show_reference_scheme = True
        self._background_cache: QtGui.QPixmap | None = None
        self._background_cache_key: tuple[Any, ...] | None = None
        self._last_mouse_pos = QtCore.QPoint()
        self._dragging = False
        self._hover_kind = ""
        self._hover_name = ""
        self._hover_focus_edge = ""
        self._hover_focus_restore_rect: QtCore.QRectF | None = None
        self._selected_focus_step = ""
        self._flow_phase = 0.0
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.setInterval(40)
        self._anim_timer.timeout.connect(self._advance_animations)

    @staticmethod
    def _normalize_detail_mode(mode: str) -> str:
        raw_mode = str(mode or "").strip().lower()
        return raw_mode if raw_mode in DETAIL_MODE_LABELS else "operator"

    def set_detail_mode(self, mode: str) -> str:
        self._detail_mode = self._normalize_detail_mode(mode)
        self._invalidate_background_cache()
        self.update()
        return self._detail_mode

    def set_reference_scheme_visible(self, visible: bool) -> bool:
        self._show_reference_scheme = bool(visible)
        self._invalidate_background_cache()
        self.update()
        return self._show_reference_scheme

    def _detail_mode_label(self) -> str:
        return str(DETAIL_MODE_LABELS.get(self._detail_mode, DETAIL_MODE_LABELS["operator"]))

    def render_dataset(self, dataset: MnemoDataset, *, selected_edge: str | None, selected_node: str | None) -> None:
        self._dataset = dataset
        self._dataset_id = str(dataset.dataset_id)
        self._frame_idx = 0
        self._dismiss_hover_route_pressure_focus(restore=False)
        self._selected_edge = str(selected_edge or "")
        self._selected_node = str(selected_node or "")
        self._camera_target_rect = None
        self._edge_series_map = {str(item.get("name") or ""): item for item in dataset.edge_series}
        self._node_series_map = {str(item.get("name") or ""): item for item in dataset.node_series}
        self._selected_focus_step = ""
        self._build_native_scene_cache()
        self._load_svg_renderer(dataset.svg_inline)
        self._load_reference_svg_renderer(dataset.reference_svg_inline)
        self._reference_scheme_source = str(dataset.reference_scheme_source or "")
        if self._mode == "overview":
            self._set_camera_target(self._scene_rect, immediate=True)
        self._invalidate_background_cache()
        self.update()
        self.status.emit("Desktop Mnemo switched to native Qt canvas.")

    def set_frame_state(self, idx: int, playing: bool, dataset_id: str) -> None:
        self._frame_idx = int(max(0, idx))
        self._playing = bool(playing)
        self._dataset_id = str(dataset_id or self._dataset_id)
        self._sync_anim_timer()
        self.update()

    def set_selection(self, *, edge: str | None, node: str | None) -> None:
        self._dismiss_hover_route_pressure_focus(restore=False)
        new_edge = str(edge or "")
        if new_edge != self._selected_edge:
            self._selected_focus_step = ""
        self._selected_edge = new_edge
        self._selected_node = str(node or "")
        self.update()

    def set_alerts(self, alerts: dict[str, Any]) -> None:
        self._alerts = dict(alerts or {})
        self.update()

    def set_diagnostics(self, diagnostics: dict[str, Any]) -> None:
        self._diagnostics = dict(diagnostics or {})
        self.update()

    def set_focus_region(self, focus_region: dict[str, Any] | None) -> None:
        self._dismiss_hover_route_pressure_focus(restore=False)
        self._focus_region = dict(focus_region) if isinstance(focus_region, dict) else None
        if self._focus_region:
            self._mode = "focus"
            target_rect = self._focus_scene_rect(self._focus_region)
            if target_rect is not None:
                self._set_camera_target(target_rect)
            self.status.emit(
                f"Фокус: {self._focus_region.get('edge_name') or self._focus_region.get('node_name') or 'scene'}"
            )
        self._invalidate_background_cache()
        self.update()

    def show_overview(self, meta: dict[str, Any] | None = None) -> None:
        self._dismiss_hover_route_pressure_focus(restore=False)
        self._mode = "overview"
        self._overview_meta = dict(meta or {})
        focus_region = self._overview_meta.get("focus_region")
        self._focus_region = dict(focus_region) if isinstance(focus_region, dict) else self._focus_region
        self._set_camera_target(self._scene_rect)
        self._invalidate_background_cache()
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._invalidate_background_cache()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # type: ignore[override]
        if self._dataset is None:
            return
        self._dismiss_hover_route_pressure_focus(restore=False)
        delta_y = event.angleDelta().y()
        if delta_y == 0:
            return
        cursor_scene = self._widget_to_scene(event.position())
        factor = 0.84 if delta_y > 0 else 1.18
        new_rect = QtCore.QRectF(self._camera_rect)
        new_rect.setWidth(max(260.0, min(self._scene_rect.width() * 1.04, new_rect.width() * factor)))
        new_rect.setHeight(max(180.0, min(self._scene_rect.height() * 1.04, new_rect.height() * factor)))
        rx = 0.5 if self.width() <= 1 else float(event.position().x()) / float(max(1, self.width()))
        ry = 0.5 if self.height() <= 1 else float(event.position().y()) / float(max(1, self.height()))
        new_rect.moveTo(
            float(cursor_scene.x()) - new_rect.width() * rx,
            float(cursor_scene.y()) - new_rect.height() * ry,
        )
        self._camera_target_rect = None
        self._camera_rect = self._clamped_camera_rect(new_rect)
        self._invalidate_background_cache()
        self.update()
        self._sync_anim_timer()
        event.accept()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.LeftButton:
            scene_pos = self._widget_to_scene(event.position())
            hit_kind, hit_name = self._hit_test(scene_pos)
            if hit_kind == "node" and hit_name:
                self.node_picked.emit(hit_name)
                self.status.emit(f"Узел: {_short_node_label(hit_name)}")
                event.accept()
                return
            if hit_kind == "edge" and hit_name:
                self.edge_picked.emit(hit_name)
                self.status.emit(f"Ветка: {hit_name}")
                event.accept()
                return
            if hit_kind == "focus_step" and hit_name:
                self._toggle_focus_step(hit_name)
                event.accept()
                return
            self._dragging = True
            self._last_mouse_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if self._dragging:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self._pan_camera(delta)
            event.accept()
            return

        scene_pos = self._widget_to_scene(event.position())
        hit_kind, hit_name = self._hit_test(scene_pos)
        if hit_kind != self._hover_kind or hit_name != self._hover_name:
            self._hover_kind = hit_kind
            self._hover_name = hit_name
            self.setCursor(QtCore.Qt.PointingHandCursor if hit_kind else QtCore.Qt.ArrowCursor)
            self._update_hover_route_pressure_focus()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.LeftButton:
            target_rect = self._focus_scene_rect(self._focus_region) if self._mode == "focus" else self._scene_rect
            self._set_camera_target(target_rect or self._scene_rect)
            self._invalidate_background_cache()
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
        self._dismiss_hover_route_pressure_focus(restore=True)
        self._hover_kind = ""
        self._hover_name = ""
        self._dragging = False
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.drawPixmap(0, 0, self._background_pixmap())
        if self._dataset is None:
            self._draw_empty_state(painter)
            return

        painter.save()
        painter.setClipRect(self._content_rect())
        painter.setTransform(self._scene_transform())
        self._overlay_targets.clear()
        self._draw_live_edges(painter)
        self._draw_diagonal_focus_pressure_strips(painter)
        self._draw_live_nodes(painter)
        self._draw_route_pressure_strip_terminal_focus(painter)
        self._draw_selected_edge_terminal_overlay(painter)
        self._draw_selected_edge_direction_overlay(painter)
        self._draw_focus_overlay(painter)
        self._draw_alert_markers(painter)
        self._draw_diagnostics_overlay(painter)
        self._draw_selected_edge_focus_overlay(painter)
        painter.restore()
        self._draw_hud(painter)

    def _advance_animations(self) -> None:
        dirty = False
        if self._playing:
            self._flow_phase = (self._flow_phase + 6.0) % 1000.0
            dirty = True
        if self._camera_target_rect is not None:
            next_rect = self._interpolate_rect(self._camera_rect, self._camera_target_rect, 0.22)
            if self._rect_close_enough(next_rect, self._camera_target_rect):
                next_rect = QtCore.QRectF(self._camera_target_rect)
                self._camera_target_rect = None
            self._camera_rect = self._clamped_camera_rect(next_rect)
            self._invalidate_background_cache()
            dirty = True
        if dirty:
            self.update()
        self._sync_anim_timer()

    def _toggle_focus_step(self, step_label: str) -> None:
        normalized = str(step_label or "").strip()
        if normalized not in {"01", "02", "03"}:
            return
        self._selected_focus_step = "" if self._selected_focus_step == normalized else normalized
        if not self._selected_focus_step:
            self.status.emit("Фокус шага снят: показана полная локальная последовательность ветви.")
            self.update()
            return
        payload = self._selected_edge_focus_payload()
        target_idx = None
        target_time_s = None
        if payload is not None:
            for row in list(payload.get("step_rows") or []):
                if str(row.get("index_label") or "") == self._selected_focus_step:
                    raw_target_idx = row.get("target_idx")
                    target_idx = int(raw_target_idx) if raw_target_idx is not None else None
                    raw_target_time = row.get("target_time_s")
                    target_time_s = float(raw_target_time) if raw_target_time is not None else None
                    break
        if target_idx is not None and target_idx != self._frame_idx:
            self.focus_step_jump_requested.emit(self._selected_focus_step, int(target_idx))
            if target_time_s is not None:
                self.status.emit(
                    f"Фокус шага {self._selected_focus_step}: переход к ближайшему кадру {target_time_s:0.3f} s."
                )
        else:
            self.status.emit(f"Фокус шага {self._selected_focus_step}: усилен локальный этап ветви.")
        self.update()

    def _content_rect(self) -> QtCore.QRectF:
        return QtCore.QRectF(self.rect()).adjusted(12.0, 12.0, -12.0, -12.0)

    def _build_native_scene_cache(self) -> None:
        self._edge_paths.clear()
        self._edge_hit_paths.clear()
        self._edge_midpoints.clear()
        self._node_points.clear()
        self._node_hit_rects.clear()
        if self._dataset is None:
            return

        mapping = self._dataset.mapping if isinstance(self._dataset.mapping, dict) else {}
        for node_name, coords in dict(mapping.get("nodes") or {}).items():
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                continue
            point = QtCore.QPointF(float(coords[0]), float(coords[1]))
            self._node_points[str(node_name)] = point
            self._node_hit_rects[str(node_name)] = QtCore.QRectF(point.x() - 18.0, point.y() - 18.0, 36.0, 36.0)

        for edge_name, lanes in dict(mapping.get("edges") or {}).items():
            path = QtGui.QPainterPath()
            sampled_points: list[QtCore.QPointF] = []
            for lane in list(lanes or []):
                points = [QtCore.QPointF(float(pt[0]), float(pt[1])) for pt in list(lane or []) if len(pt) >= 2]
                if not points:
                    continue
                sampled_points.extend(points)
                path.moveTo(points[0])
                for point in points[1:]:
                    path.lineTo(point)
            if path.isEmpty():
                continue
            self._edge_paths[str(edge_name)] = path
            stroker = QtGui.QPainterPathStroker()
            stroker.setCapStyle(QtCore.Qt.RoundCap)
            stroker.setJoinStyle(QtCore.Qt.RoundJoin)
            stroker.setWidth(30.0)
            self._edge_hit_paths[str(edge_name)] = stroker.createStroke(path)
            self._edge_midpoints[str(edge_name)] = self._polyline_midpoint(sampled_points) or path.boundingRect().center()

    def _load_svg_renderer(self, svg_inline: str) -> None:
        self._svg_renderer = None
        if QtSvg is None or not svg_inline:
            return
        try:
            renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_inline.encode("utf-8")), self)
            if renderer.isValid():
                self._svg_renderer = renderer
        except Exception:
            self._svg_renderer = None

    def _load_reference_svg_renderer(self, svg_inline: str) -> None:
        self._reference_svg_renderer = None
        if QtSvg is None or not svg_inline:
            return
        try:
            renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_inline.encode("utf-8")), self)
            if renderer.isValid():
                self._reference_svg_renderer = renderer
        except Exception:
            self._reference_svg_renderer = None

    def _invalidate_background_cache(self) -> None:
        self._background_cache = None
        self._background_cache_key = None

    def _background_pixmap(self) -> QtGui.QPixmap:
        key = (
            int(self.width()),
            int(self.height()),
            round(float(self._camera_rect.left()), 2),
            round(float(self._camera_rect.top()), 2),
            round(float(self._camera_rect.width()), 2),
            round(float(self._camera_rect.height()), 2),
            str(self._dataset_id),
            bool(self._svg_renderer is not None),
            bool(self._reference_svg_renderer is not None),
            bool(self._show_reference_scheme),
            str(self._reference_scheme_source),
        )
        if self._background_cache is not None and self._background_cache_key == key:
            return self._background_cache

        device_ratio = max(1.0, float(self.devicePixelRatioF()))
        pixmap = QtGui.QPixmap(max(1, int(self.width() * device_ratio)), max(1, int(self.height() * device_ratio)))
        pixmap.setDevicePixelRatio(device_ratio)
        pixmap.fill(QtGui.QColor("#071117"))

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor("#071117"))
        painter.save()
        painter.setClipRect(self._content_rect())
        painter.setTransform(self._scene_transform())
        self._draw_static_scene(painter)
        painter.restore()
        painter.end()

        self._background_cache = pixmap
        self._background_cache_key = key
        return pixmap

    def _scene_transform(self) -> QtGui.QTransform:
        content_rect = self._content_rect()
        if content_rect.width() <= 1.0 or content_rect.height() <= 1.0:
            return QtGui.QTransform()
        sx = content_rect.width() / max(1.0, self._camera_rect.width())
        sy = content_rect.height() / max(1.0, self._camera_rect.height())
        tx = content_rect.left() - self._camera_rect.left() * sx
        ty = content_rect.top() - self._camera_rect.top() * sy
        return QtGui.QTransform(sx, 0.0, 0.0, sy, tx, ty)

    def _widget_to_scene(self, point: QtCore.QPointF) -> QtCore.QPointF:
        inverted, ok = self._scene_transform().inverted()
        if ok:
            return inverted.map(point)
        return QtCore.QPointF(point)

    def _fit_camera(self, target_rect: QtCore.QRectF) -> None:
        self._camera_rect = self._resolved_camera_rect(target_rect)

    def _resolved_camera_rect(self, target_rect: QtCore.QRectF) -> QtCore.QRectF:
        normalized = QtCore.QRectF(target_rect if target_rect.isValid() else self._scene_rect)
        if normalized.width() < 10.0 or normalized.height() < 10.0:
            normalized = QtCore.QRectF(self._scene_rect)
        padding = max(40.0, min(180.0, 0.10 * max(normalized.width(), normalized.height())))
        normalized.adjust(-padding, -padding, padding, padding)
        return self._clamped_camera_rect(normalized)

    def _set_camera_target(self, target_rect: QtCore.QRectF, *, immediate: bool = False) -> None:
        resolved = self._resolved_camera_rect(target_rect)
        if immediate:
            self._camera_rect = QtCore.QRectF(resolved)
            self._camera_target_rect = None
            self._invalidate_background_cache()
            self.update()
            self._sync_anim_timer()
            return
        self._camera_target_rect = resolved
        self._sync_anim_timer()

    def _sync_anim_timer(self) -> None:
        should_run = bool(self._playing or self._camera_target_rect is not None)
        if should_run and not self._anim_timer.isActive():
            self._anim_timer.start()
        elif not should_run and self._anim_timer.isActive():
            self._anim_timer.stop()

    @staticmethod
    def _interpolate_rect(current: QtCore.QRectF, target: QtCore.QRectF, factor: float) -> QtCore.QRectF:
        t = max(0.0, min(1.0, float(factor)))
        return QtCore.QRectF(
            current.left() + (target.left() - current.left()) * t,
            current.top() + (target.top() - current.top()) * t,
            current.width() + (target.width() - current.width()) * t,
            current.height() + (target.height() - current.height()) * t,
        )

    @staticmethod
    def _rect_close_enough(current: QtCore.QRectF, target: QtCore.QRectF) -> bool:
        return (
            abs(current.left() - target.left()) <= 1.5
            and abs(current.top() - target.top()) <= 1.5
            and abs(current.width() - target.width()) <= 1.5
            and abs(current.height() - target.height()) <= 1.5
        )

    def _clamped_camera_rect(self, rect: QtCore.QRectF) -> QtCore.QRectF:
        content_rect = self._content_rect()
        if content_rect.width() <= 1.0 or content_rect.height() <= 1.0:
            return QtCore.QRectF(self._scene_rect)

        target = QtCore.QRectF(rect)
        target_width = max(220.0, min(self._scene_rect.width() * 1.04, target.width()))
        target_height = max(160.0, min(self._scene_rect.height() * 1.04, target.height()))
        aspect = content_rect.width() / max(1.0, content_rect.height())
        if target_width / max(1.0, target_height) > aspect:
            target_height = target_width / aspect
        else:
            target_width = target_height * aspect
        target_width = min(self._scene_rect.width() * 1.04, target_width)
        target_height = min(self._scene_rect.height() * 1.04, target_height)
        center = target.center()
        out = QtCore.QRectF(
            center.x() - target_width * 0.5,
            center.y() - target_height * 0.5,
            target_width,
            target_height,
        )
        if out.width() >= self._scene_rect.width():
            out.moveLeft(self._scene_rect.left() - (out.width() - self._scene_rect.width()) * 0.5)
        else:
            out.moveLeft(min(max(out.left(), self._scene_rect.left()), self._scene_rect.right() - out.width()))
        if out.height() >= self._scene_rect.height():
            out.moveTop(self._scene_rect.top() - (out.height() - self._scene_rect.height()) * 0.5)
        else:
            out.moveTop(min(max(out.top(), self._scene_rect.top()), self._scene_rect.bottom() - out.height()))
        return out

    def _pan_camera(self, delta_px: QtCore.QPoint) -> None:
        if self._dataset is None:
            return
        self._dismiss_hover_route_pressure_focus(restore=False)
        content_rect = self._content_rect()
        if content_rect.width() <= 1.0 or content_rect.height() <= 1.0:
            return
        dx = -float(delta_px.x()) * self._camera_rect.width() / float(content_rect.width())
        dy = -float(delta_px.y()) * self._camera_rect.height() / float(content_rect.height())
        target = QtCore.QRectF(self._camera_rect)
        target.translate(dx, dy)
        self._camera_target_rect = None
        self._camera_rect = self._clamped_camera_rect(target)
        self._invalidate_background_cache()
        self.update()
        self._sync_anim_timer()

    def _focus_scene_rect(self, focus_region: dict[str, Any] | None) -> QtCore.QRectF | None:
        if self._dataset is None or not focus_region:
            return None
        target_rect: QtCore.QRectF | None = None
        edge_name = str(focus_region.get("edge_name") or "")
        node_name = str(focus_region.get("node_name") or "")
        if edge_name and edge_name in self._edge_paths:
            target_rect = QtCore.QRectF(self._edge_paths[edge_name].boundingRect())
        if node_name and node_name in self._node_points:
            point = self._node_points[node_name]
            node_rect = QtCore.QRectF(point.x() - 42.0, point.y() - 42.0, 84.0, 84.0)
            target_rect = node_rect if target_rect is None else target_rect.united(node_rect)
        if target_rect is None:
            return None
        padding = float(focus_region.get("padding") or 150.0)
        target_rect.adjust(-padding, -padding, padding, padding)
        return target_rect

    def _route_pressure_strip_payload_for_edge(self, edge_name: str) -> dict[str, Any] | None:
        edge_key = str(edge_name or "")
        if not edge_key:
            return None
        diagnostics = self._diagnostics if isinstance(self._diagnostics, dict) else {}
        for item in list(diagnostics.get("route_pressure_strips") or []):
            payload = dict(item or {})
            if str(payload.get("edge_name") or "") == edge_key:
                return payload
        return None

    def _route_pressure_strip_focus_rect(self, payload: dict[str, Any] | None) -> QtCore.QRectF | None:
        item = dict(payload or {})
        edge_name = str(item.get("edge_name") or "")
        if not edge_name:
            return None
        target_rect: QtCore.QRectF | None = None
        path = self._edge_paths.get(edge_name)
        if isinstance(path, QtGui.QPainterPath) and not path.isEmpty():
            target_rect = QtCore.QRectF(path.boundingRect())
        for node_name in [str(item.get("start_node") or ""), str(item.get("end_node") or "")]:
            point = self._node_points.get(node_name)
            if point is None:
                continue
            node_rect = QtCore.QRectF(point.x() - 46.0, point.y() - 46.0, 92.0, 92.0)
            target_rect = node_rect if target_rect is None else target_rect.united(node_rect)
        if target_rect is None:
            return None
        target_rect.adjust(-120.0, -120.0, 120.0, 120.0)
        return target_rect

    def _camera_contains_rect(self, rect: QtCore.QRectF, *, margin: float = 48.0) -> bool:
        expanded = QtCore.QRectF(self._camera_rect).adjusted(margin, margin, -margin, -margin)
        return expanded.contains(rect)

    def _update_hover_route_pressure_focus(self) -> None:
        hover_edge = str(self._hover_name or "") if self._hover_kind == "edge" else ""
        payload = self._route_pressure_strip_payload_for_edge(hover_edge)
        if payload is None or self._detail_mode == "quiet":
            self._dismiss_hover_route_pressure_focus(restore=True)
            return

        focus_rect = self._route_pressure_strip_focus_rect(payload)
        if focus_rect is None:
            self._dismiss_hover_route_pressure_focus(restore=True)
            return
        if self._camera_contains_rect(focus_rect, margin=54.0):
            return
        if self._hover_focus_restore_rect is None:
            self._hover_focus_restore_rect = QtCore.QRectF(self._camera_rect)
        self._hover_focus_edge = hover_edge
        self._set_camera_target(focus_rect)

    def _dismiss_hover_route_pressure_focus(self, *, restore: bool) -> None:
        restore_rect = QtCore.QRectF(self._hover_focus_restore_rect) if self._hover_focus_restore_rect is not None else None
        had_focus = bool(self._hover_focus_edge)
        self._hover_focus_edge = ""
        self._hover_focus_restore_rect = None
        if restore and had_focus and restore_rect is not None:
            self._set_camera_target(restore_rect)

    def _hit_test(self, scene_pos: QtCore.QPointF) -> tuple[str, str]:
        for kind, name, rect in reversed(self._overlay_targets):
            if rect.contains(scene_pos):
                return kind, name
        for node_name, rect in self._node_hit_rects.items():
            if rect.contains(scene_pos):
                return "node", node_name
        for edge_name, hit_path in self._edge_hit_paths.items():
            if hit_path.contains(scene_pos):
                return "edge", edge_name
        return "", ""

    def _reference_scheme_rect(self) -> QtCore.QRectF:
        left_inset, top_inset, right_inset, bottom_inset = REFERENCE_SCHEME_SCENE_INSET
        bounds = QtCore.QRectF(self._scene_rect).adjusted(left_inset, top_inset, -right_inset, -bottom_inset)
        if bounds.width() <= 10.0 or bounds.height() <= 10.0:
            return QtCore.QRectF(self._scene_rect)
        source_width = REFERENCE_SCHEME_VIEWBOX_W
        source_height = REFERENCE_SCHEME_VIEWBOX_H
        if self._reference_svg_renderer is not None:
            try:
                view_box = self._reference_svg_renderer.viewBoxF()
                if view_box.isValid() and view_box.width() > 1.0 and view_box.height() > 1.0:
                    source_width = float(view_box.width())
                    source_height = float(view_box.height())
            except Exception:
                pass
        scale = min(bounds.width() / max(1.0, source_width), bounds.height() / max(1.0, source_height))
        width = source_width * scale
        height = source_height * scale
        center = bounds.center()
        return QtCore.QRectF(center.x() - width * 0.5, center.y() - height * 0.5, width, height)

    def _draw_static_scene(self, painter: QtGui.QPainter) -> None:
        if self._reference_svg_renderer is not None and self._show_reference_scheme:
            painter.fillRect(self._scene_rect, QtGui.QColor("#071117"))
            reference_rect = self._reference_scheme_rect()
            frame_rect = reference_rect.adjusted(-16.0, -16.0, 16.0, 16.0)
            painter.save()
            painter.setPen(QtGui.QPen(QtGui.QColor(99, 211, 245, 46), 2.0))
            painter.setBrush(QtGui.QColor(7, 17, 23, 14))
            painter.drawRoundedRect(frame_rect, 28.0, 28.0)
            painter.restore()
            painter.save()
            painter.setOpacity(0.44 if self._detail_mode == "quiet" else 0.58)
            self._reference_svg_renderer.render(painter, reference_rect)
            painter.restore()
            painter.save()
            badge_rect = QtCore.QRectF(reference_rect.left() + 18.0, reference_rect.top() + 16.0, 330.0, 34.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(9, 20, 26, 198))
            painter.drawRoundedRect(badge_rect, 12.0, 12.0)
            painter.setPen(QtGui.QColor("#9fe7f7"))
            font = QtGui.QFont("Bahnschrift SemiCondensed", 12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                badge_rect.adjusted(12.0, 0.0, -12.0, 0.0),
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                "Исходная пневмосхема • pneumo_scheme.svg",
            )
            painter.restore()
            return
        if self._svg_renderer is not None:
            self._svg_renderer.render(painter, self._scene_rect)
            return

        painter.fillRect(self._scene_rect, QtGui.QColor("#071117"))
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 14), 1.0)
        painter.setPen(pen)
        step = 48
        for x in range(0, int(VIEWBOX_W) + step, step):
            painter.drawLine(x, 0, x, int(VIEWBOX_H))
        for y in range(0, int(VIEWBOX_H) + step, step):
            painter.drawLine(0, y, int(VIEWBOX_W), y)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(13, 33, 42, 185))
        painter.drawRoundedRect(QtCore.QRectF(60.0, 70.0, 2080.0, 220.0), 28.0, 28.0)
        painter.drawRoundedRect(QtCore.QRectF(60.0, 320.0, 2080.0, 290.0), 28.0, 28.0)
        painter.drawRoundedRect(QtCore.QRectF(60.0, 650.0, 2080.0, 760.0), 36.0, 36.0)

    def _draw_live_edges(self, painter: QtGui.QPainter) -> None:
        if self._dataset is None:
            return
        flows = [abs(self._current_edge_flow(edge_name)) for edge_name in self._dataset.edge_names]
        max_abs_flow = max(flows, default=0.0)
        inline_symbols = self._inline_route_symbol_payloads(max_abs_flow=max_abs_flow)
        for edge_name in self._dataset.edge_names:
            path = self._edge_paths.get(edge_name)
            if path is None:
                continue
            flow_value = self._current_edge_flow(edge_name)
            flow_rgb = _flow_to_heat_rgb(flow_value, max_abs_flow=max_abs_flow)
            flow_color = QtGui.QColor(*flow_rgb)
            magnitude = 0.0 if max_abs_flow <= 1.0e-9 else _clamp01(abs(flow_value) / max_abs_flow)
            open_state = self._current_edge_open(edge_name)
            base_width = 6.0 + 14.0 * math.sqrt(max(0.0, magnitude))
            glow_color = QtGui.QColor(flow_color)
            glow_color.setAlpha(70 if open_state is False else 135)
            core_color = QtGui.QColor(flow_color)
            core_color.setAlpha(90 if open_state is False else 245)

            painter.setPen(
                QtGui.QPen(glow_color, base_width + 8.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            )
            painter.drawPath(path)

            dash_pen = QtGui.QPen(core_color, base_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            dash_pen.setDashPattern([24.0, 15.0])
            dash_pen.setDashOffset((self._flow_phase + self._frame_idx * 3.0) * (-1.0 if flow_value >= 0.0 else 1.0))
            painter.setPen(
                dash_pen
                if abs(flow_value) > 1.0e-9
                else QtGui.QPen(core_color, max(3.0, base_width * 0.55), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            )
            painter.drawPath(path)

            if edge_name == self._selected_edge or (self._hover_kind == "edge" and edge_name == self._hover_name):
                accent = QtGui.QColor("#fff4c7" if edge_name == self._selected_edge else "#d5f7ff")
                painter.setPen(
                    QtGui.QPen(accent, base_width + 2.5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
                )
                painter.drawPath(path)
            inline_payload = inline_symbols.get(edge_name)
            if inline_payload is not None:
                self._draw_inline_route_symbol(painter, edge_name=edge_name, payload=inline_payload)

    def _draw_diagonal_focus_pressure_strips(self, painter: QtGui.QPainter) -> None:
        diagnostics = self._diagnostics if isinstance(self._diagnostics, dict) else {}
        strip_payloads = list(diagnostics.get("route_pressure_strips") or diagnostics.get("diagonal_pressure_strips") or [])
        if not strip_payloads:
            return
        if self._detail_mode == "quiet":
            selected = [
                dict(item or {})
                for item in strip_payloads
                if str(dict(item or {}).get("edge_name") or "") == str(self._selected_edge or "")
            ]
            strip_payloads = selected[:1] if selected else strip_payloads[:1]
        elif self._detail_mode == "operator":
            strip_payloads = strip_payloads[:3]
        else:
            strip_payloads = strip_payloads[:6]

        safe_rect = self._scene_rect.adjusted(24.0, 24.0, -24.0, -24.0)
        for item in strip_payloads:
            payload = dict(item or {})
            edge_name = str(payload.get("edge_name") or "")
            path = self._edge_paths.get(edge_name)
            if not isinstance(path, QtGui.QPainterPath) or path.isEmpty():
                continue

            severity = str(payload.get("severity") or "attention")
            p1_bar_g = _finite_or_none(payload.get("p1_bar_g"))
            p2_bar_g = _finite_or_none(payload.get("p2_bar_g"))
            order = int(payload.get("order") or 0)
            is_selected = bool(payload.get("selected"))
            severity_color = QtGui.QColor(self._severity_color_hex(severity))
            severity_color.setAlpha(84 if not is_selected else 118)
            start_color = QtGui.QColor(
                *(_pressure_to_heat_rgb(p1_bar_g) if p1_bar_g is not None else _flow_to_heat_rgb(0.0, max_abs_flow=1.0))
            )
            end_color = QtGui.QColor(
                *(_pressure_to_heat_rgb(p2_bar_g) if p2_bar_g is not None else _flow_to_heat_rgb(0.0, max_abs_flow=1.0))
            )
            start_color.setAlpha(232 if is_selected else 210)
            end_color.setAlpha(232 if is_selected else 210)
            gradient = QtGui.QLinearGradient(path.pointAtPercent(0.0), path.pointAtPercent(1.0))
            gradient.setColorAt(0.0, start_color)
            gradient.setColorAt(1.0, end_color)

            painter.save()
            painter.setPen(
                QtGui.QPen(
                    severity_color,
                    10.0 if is_selected else 8.0,
                    QtCore.Qt.SolidLine,
                    QtCore.Qt.RoundCap,
                    QtCore.Qt.RoundJoin,
                )
            )
            painter.drawPath(path)
            painter.setPen(
                QtGui.QPen(
                    QtGui.QBrush(gradient),
                    5.6 if is_selected else 4.6,
                    QtCore.Qt.SolidLine,
                    QtCore.Qt.RoundCap,
                    QtCore.Qt.RoundJoin,
                )
            )
            painter.drawPath(path)
            self._draw_route_pressure_strip_cause_effect_accent(
                painter,
                path=path,
                payload=payload,
                is_selected=is_selected,
                order=order,
            )

            anchor_percent = min(0.78, 0.34 + float(order) * 0.22)
            anchor = path.pointAtPercent(anchor_percent)
            angle_deg = _path_angle_deg(path, anchor_percent)
            angle_rad = math.radians(angle_deg)
            side = -1.0 if order % 2 else 1.0
            offset = 34.0 + 8.0 * float(order)
            anchor = QtCore.QPointF(
                anchor.x() + (-math.sin(angle_rad) * offset * side),
                anchor.y() + (math.cos(angle_rad) * offset * side),
            )
            chip_rect = QtCore.QRectF(anchor.x() - 88.0, anchor.y() - 22.0, 176.0, 44.0)
            if chip_rect.left() < safe_rect.left():
                chip_rect.moveLeft(safe_rect.left())
            if chip_rect.right() > safe_rect.right():
                chip_rect.moveRight(safe_rect.right())
            if chip_rect.top() < safe_rect.top():
                chip_rect.moveTop(safe_rect.top())
            if chip_rect.bottom() > safe_rect.bottom():
                chip_rect.moveBottom(safe_rect.bottom())

            painter.setPen(QtGui.QPen(QtGui.QColor("#f7fbff" if is_selected else severity_color), 1.6))
            painter.setBrush(QtGui.QColor(7, 17, 23, 222))
            painter.drawRoundedRect(chip_rect, 12.0, 12.0)

            title_font = QtGui.QFont(self.font())
            title_font.setPointSizeF(6.2)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QtGui.QColor("#eef7fa"))
            painter.drawText(
                chip_rect.adjusted(10.0, 5.0, -10.0, -22.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                str(payload.get("label") or "ΔP диагонали"),
            )
            painter.setPen(QtGui.QColor("#9fc5d2"))
            painter.drawText(
                chip_rect.adjusted(10.0, 5.0, -10.0, -22.0),
                QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                str(payload.get("delta_label") or "ΔP —"),
            )

            body_font = QtGui.QFont(self.font())
            body_font.setPointSizeF(5.9)
            painter.setFont(body_font)
            painter.setPen(QtGui.QColor("#d6e8ee"))
            painter.drawText(
                chip_rect.adjusted(10.0, 18.0, -10.0, -4.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"{payload.get('start_label') or '—'} → {payload.get('end_label') or '—'}",
            )
            painter.setPen(QtGui.QColor("#8be2f8"))
            painter.drawText(
                chip_rect.adjusted(10.0, 18.0, -10.0, -4.0),
                QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                str(payload.get("pressure_label") or "—"),
            )
            self._overlay_targets.append(("edge", edge_name, chip_rect))
            painter.restore()

    def _draw_route_pressure_strip_cause_effect_accent(
        self,
        painter: QtGui.QPainter,
        *,
        path: QtGui.QPainterPath,
        payload: dict[str, Any],
        is_selected: bool,
        order: int,
    ) -> None:
        if path.isEmpty():
            return
        badge_text = str(payload.get("cause_effect_badge") or "")
        if not badge_text:
            return

        tone = str(payload.get("cause_effect_tone") or "neutral")
        fill, border, text_color = self._focus_tone_colors(tone)
        accent_percent = min(0.68, 0.48 + float(order) * 0.04)
        start_percent = max(0.10, accent_percent - 0.10)
        end_percent = min(0.92, accent_percent + 0.10)
        start_point = path.pointAtPercent(start_percent)
        end_point = path.pointAtPercent(end_percent)

        painter.save()
        accent_pen = QtGui.QPen(border, 7.2 if is_selected else 6.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(accent_pen)
        painter.drawLine(start_point, end_point)

        anchor = path.pointAtPercent(accent_percent)
        angle_deg = _path_angle_deg(path, accent_percent)
        angle_rad = math.radians(angle_deg)
        side = -1.0 if order % 2 else 1.0
        offset = 18.0 if is_selected else 14.0
        chip_center = QtCore.QPointF(
            anchor.x() + (-math.sin(angle_rad) * offset * side),
            anchor.y() + (math.cos(angle_rad) * offset * side),
        )
        chip_width = max(52.0, min(94.0, 24.0 + float(len(badge_text)) * 4.6))
        chip_rect = QtCore.QRectF(chip_center.x() - chip_width * 0.5, chip_center.y() - 7.0, chip_width, 14.0)

        painter.setPen(QtGui.QPen(border, 0.9))
        painter.setBrush(fill)
        painter.drawRoundedRect(chip_rect, 6.0, 6.0)
        chip_font = QtGui.QFont(self.font())
        chip_font.setPointSizeF(4.8 if is_selected else 4.6)
        chip_font.setBold(True)
        painter.setFont(chip_font)
        painter.setPen(text_color)
        painter.drawText(
            chip_rect.adjusted(4.0, 0.0, -4.0, 0.0),
            QtCore.Qt.AlignCenter,
            badge_text,
        )
        painter.restore()

    def _active_route_pressure_strip_payload(self) -> dict[str, Any] | None:
        diagnostics = self._diagnostics if isinstance(self._diagnostics, dict) else {}
        strip_payloads = [dict(item or {}) for item in list(diagnostics.get("route_pressure_strips") or []) if isinstance(item, dict)]
        if not strip_payloads:
            return None
        hover_edge = str(self._hover_name or "") if self._hover_kind == "edge" else ""
        if hover_edge:
            for payload in strip_payloads:
                if str(payload.get("edge_name") or "") == hover_edge:
                    payload["hovered"] = True
                    return payload
        selected_edge = str(self._selected_edge or "")
        if selected_edge:
            for payload in strip_payloads:
                if str(payload.get("edge_name") or "") == selected_edge:
                    payload["hovered"] = False
                    return payload
        return None

    def _active_route_pressure_terminal_meta(self) -> dict[str, Any] | None:
        payload = self._active_route_pressure_strip_payload()
        if payload is None:
            return None
        return _route_pressure_strip_terminal_meta(payload)

    def _draw_route_pressure_strip_terminal_focus(self, painter: QtGui.QPainter) -> None:
        payload = self._active_route_pressure_strip_payload()
        if payload is None:
            return
        terminal_meta = _route_pressure_strip_terminal_meta(payload)
        edge_name = str(terminal_meta.get("edge_name") or "")
        midpoint = self._edge_midpoints.get(edge_name)
        if midpoint is None:
            return

        severity = str(terminal_meta.get("severity") or "info")
        highlight = QtGui.QColor(self._severity_color_hex(severity))
        if bool(payload.get("hovered")):
            highlight = QtGui.QColor("#f6d98b")
        endpoint_rows = [
            (
                str(terminal_meta.get("start_node") or ""),
                str(terminal_meta.get("start_badge") or "P?"),
                str(terminal_meta.get("start_pressure_label") or "—"),
                str(terminal_meta.get("start_label") or "—"),
            ),
            (
                str(terminal_meta.get("end_node") or ""),
                str(terminal_meta.get("end_badge") or "P?"),
                str(terminal_meta.get("end_pressure_label") or "—"),
                str(terminal_meta.get("end_label") or "—"),
            ),
        ]

        painter.save()
        for node_name, badge_text, pressure_text, label_text in endpoint_rows:
            point = self._node_points.get(node_name)
            if point is None:
                continue
            is_leading = node_name and node_name == str(terminal_meta.get("leading_node") or "")
            ring_color = QtGui.QColor(highlight)
            ring_color.setAlpha(255 if is_leading else 214)
            painter.setPen(QtGui.QPen(ring_color, 3.6 if is_leading else 2.4))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(point, 26.0 if is_leading else 22.0, 26.0 if is_leading else 22.0)

            side = 1.0 if point.x() <= midpoint.x() else -1.0
            chip_rect = QtCore.QRectF(
                point.x() + (18.0 if side > 0.0 else -106.0),
                point.y() - 14.0,
                88.0,
                28.0,
            )
            painter.setPen(QtGui.QPen(ring_color, 1.8 if is_leading else 1.2))
            painter.setBrush(QtGui.QColor(7, 17, 23, 232))
            painter.drawRoundedRect(chip_rect, 9.0, 9.0)

            chip_font = QtGui.QFont(self.font())
            chip_font.setPointSizeF(6.0 if is_leading else 5.8)
            chip_font.setBold(True)
            painter.setFont(chip_font)
            painter.setPen(QtGui.QColor("#eef7fa"))
            painter.drawText(
                chip_rect.adjusted(8.0, 2.0, -8.0, -12.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                f"{badge_text} {pressure_text}",
            )
            painter.setPen(QtGui.QColor("#8be2f8" if is_leading else "#9fc5d2"))
            painter.drawText(
                chip_rect.adjusted(8.0, 12.0, -8.0, -2.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                label_text,
            )
            self._overlay_targets.append(("node", node_name, chip_rect))

        trend_fill, trend_border, trend_text = self._focus_tone_colors(str(terminal_meta.get("trend_tone") or "neutral"))
        q_fill, q_border, q_text = self._focus_tone_colors(str(terminal_meta.get("q_tone") or "neutral"))
        cause_fill, cause_border, cause_text = self._focus_tone_colors(str(terminal_meta.get("cause_effect_tone") or "neutral"))
        summary_rect = QtCore.QRectF(midpoint.x() - 92.0, midpoint.y() - 98.0, 184.0, 102.0)
        painter.setPen(QtGui.QPen(highlight, 1.4))
        painter.setBrush(QtGui.QColor(8, 20, 28, 228))
        painter.drawRoundedRect(summary_rect, 9.0, 9.0)
        summary_font = QtGui.QFont(self.font())
        summary_font.setPointSizeF(5.9)
        summary_font.setBold(True)
        painter.setFont(summary_font)
        painter.setPen(QtGui.QColor("#eef7fa"))
        painter.drawText(
            summary_rect.adjusted(8.0, 1.0, -8.0, -73.0),
            QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter,
            str(terminal_meta.get("leader_summary") or "Ведущий конец не определён"),
        )
        trend_rect = QtCore.QRectF(summary_rect.left() + 10.0, summary_rect.top() + 20.0, summary_rect.width() - 20.0, 13.0)
        painter.setPen(QtGui.QPen(trend_border, 1.0))
        painter.setBrush(trend_fill)
        painter.drawRoundedRect(trend_rect, 7.0, 7.0)
        trend_font = QtGui.QFont(self.font())
        trend_font.setPointSizeF(5.5)
        trend_font.setBold(True)
        painter.setFont(trend_font)
        painter.setPen(trend_text)
        painter.drawText(
            trend_rect.adjusted(6.0, 0.0, -6.0, 0.0),
            QtCore.Qt.AlignCenter,
            f"{terminal_meta.get('trend_badge') or 'ΔP?'} • {terminal_meta.get('trend_status') or 'ΔP без истории'}",
        )
        q_rect = QtCore.QRectF(summary_rect.left() + 10.0, summary_rect.top() + 36.0, summary_rect.width() - 20.0, 13.0)
        painter.setPen(QtGui.QPen(q_border, 1.0))
        painter.setBrush(q_fill)
        painter.drawRoundedRect(q_rect, 7.0, 7.0)
        q_font = QtGui.QFont(self.font())
        q_font.setPointSizeF(5.5)
        q_font.setBold(True)
        painter.setFont(q_font)
        painter.setPen(q_text)
        painter.drawText(
            q_rect.adjusted(6.0, 0.0, -6.0, 0.0),
            QtCore.Qt.AlignCenter,
            f"{terminal_meta.get('q_badge') or 'Q?'} • {terminal_meta.get('q_status') or 'Q без истории'}",
        )
        cause_rect = QtCore.QRectF(summary_rect.left() + 10.0, summary_rect.top() + 52.0, summary_rect.width() - 20.0, 10.0)
        painter.setPen(QtGui.QPen(cause_border, 0.9))
        painter.setBrush(cause_fill)
        painter.drawRoundedRect(cause_rect, 5.0, 5.0)
        cause_font = QtGui.QFont(self.font())
        cause_font.setPointSizeF(4.7)
        cause_font.setBold(True)
        painter.setFont(cause_font)
        painter.setPen(cause_text)
        painter.drawText(
            cause_rect.adjusted(4.0, 0.0, -4.0, 0.0),
            QtCore.Qt.AlignCenter,
            str(terminal_meta.get("cause_effect_badge") or "ΔP→Q ?"),
        )
        history_rect = QtCore.QRectF(summary_rect.left() + 10.0, summary_rect.top() + 66.0, summary_rect.width() - 20.0, 22.0)
        self._draw_route_pressure_strip_flow_history(
            painter,
            rect=history_rect,
            payload=terminal_meta,
            accent=q_border,
        )
        self._overlay_targets.append(("edge", edge_name, summary_rect))
        painter.restore()

    def _draw_route_pressure_strip_flow_history(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
        accent: QtGui.QColor,
    ) -> None:
        points = list(payload.get("q_history_points") or [])
        if not points:
            return

        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(10, 23, 31, 224))
        painter.drawRoundedRect(rect, 6.0, 6.0)

        caption_font = QtGui.QFont(self.font())
        caption_font.setPointSizeF(4.9)
        caption_font.setBold(True)
        painter.setFont(caption_font)
        painter.setPen(QtGui.QColor("#bfdce6"))
        painter.drawText(
            QtCore.QRectF(rect.left() + 6.0, rect.top() + 1.0, 66.0, 8.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Q-лента",
        )
        painter.drawText(
            QtCore.QRectF(rect.right() - 76.0, rect.top() + 1.0, 70.0, 8.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"|Q|max {float(payload.get('q_history_peak_abs') or 0.0):0.0f}",
        )

        trace_rect = QtCore.QRectF(rect.left() + 6.0, rect.top() + 8.0, rect.width() - 12.0, rect.height() - 11.0)
        zero_y = trace_rect.top() + trace_rect.height() * float(payload.get("q_history_zero_y") or 0.5)
        painter.setPen(QtGui.QPen(QtGui.QColor(112, 134, 146, 96), 1.0, QtCore.Qt.DashLine))
        painter.drawLine(QtCore.QPointF(trace_rect.left(), zero_y), QtCore.QPointF(trace_rect.right(), zero_y))

        open_blocks = list(payload.get("q_history_open_blocks") or [])
        if open_blocks:
            gate_rect = QtCore.QRectF(trace_rect.left(), trace_rect.bottom() - 3.0, trace_rect.width(), 3.0)
            painter.setPen(QtCore.Qt.NoPen)
            for block in open_blocks:
                x0 = float(block.get("x0") or 0.0)
                x1 = float(block.get("x1") or 0.0)
                block_rect = QtCore.QRectF(
                    gate_rect.left() + gate_rect.width() * x0,
                    gate_rect.top(),
                    max(1.5, gate_rect.width() * max(0.0, x1 - x0) - 0.8),
                    gate_rect.height(),
                )
                block_fill = QtGui.QColor(127, 228, 167, 178) if bool(block.get("open")) else QtGui.QColor(70, 84, 95, 150)
                painter.setBrush(block_fill)
                painter.drawRoundedRect(block_rect, 1.5, 1.5)

        trace_height = max(6.0, trace_rect.height() - 3.0)
        line_path = QtGui.QPainterPath()
        for point_idx, point in enumerate(points):
            x_norm = float(point[0]) if len(point) >= 1 else 0.0
            y_norm = float(point[1]) if len(point) >= 2 else 0.5
            trace_point = QtCore.QPointF(
                trace_rect.left() + trace_rect.width() * x_norm,
                trace_rect.top() + max(0.0, min(1.0, y_norm)) * trace_height,
            )
            if point_idx == 0:
                line_path.moveTo(trace_point)
            else:
                line_path.lineTo(trace_point)

        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        glow = QtGui.QColor(accent)
        glow.setAlpha(220)
        line = QtGui.QColor(accent)
        line.setAlpha(255)
        painter.setPen(QtGui.QPen(glow.lighter(118), 3.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(line_path)
        painter.setPen(QtGui.QPen(line, 1.6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(line_path)
        last_point = line_path.currentPosition()
        painter.setPen(QtGui.QPen(QtGui.QColor("#071117"), 0.8))
        painter.setBrush(line)
        painter.drawEllipse(last_point, 2.1, 2.1)
        painter.restore()

    def _draw_live_nodes(self, painter: QtGui.QPainter) -> None:
        if self._dataset is None:
            return
        diagnostics = self._diagnostics if isinstance(self._diagnostics, dict) else {}
        route_payload = self._active_route_pressure_strip_payload()
        route_terminal_meta = self._active_route_pressure_terminal_meta()
        route_intermediate_items = _route_pressure_strip_intermediate_nodes_meta(
            self._dataset,
            diagnostics,
            route_payload,
            idx=self._frame_idx,
        )
        route_intermediate_lookup = {
            str(item.get("name") or ""): dict(item or {})
            for item in route_intermediate_items
            if str(dict(item or {}).get("name") or "").strip()
        }
        diagonal_focus = dict(diagnostics.get("diagonal_focus") or {})
        diagonal_focus_nodes = {
            str(name)
            for name in list(diagonal_focus.get("node_names") or [])
            if str(name).strip()
        }
        diagonal_focus_lookup = {
            str(item.get("name") or ""): dict(item or {})
            for item in list(diagonal_focus.get("nodes") or [])
            if str(dict(item or {}).get("name") or "").strip()
        }
        if self._detail_mode == "quiet":
            spotlight_nodes: set[str] = set()
        elif self._detail_mode == "full":
            spotlight_nodes = set(self._node_points.keys())
        else:
            spotlight_nodes = set(self._dataset.overlay_node_names)
        if self._detail_mode != "quiet":
            spotlight_nodes.update(diagonal_focus_nodes)
        spotlight_nodes.update(str(item.get("name") or "") for item in list(self._alerts.get("nodes") or []))
        if self._selected_node:
            spotlight_nodes.add(self._selected_node)
        if self._selected_edge:
            edge_def = dict(self._dataset.edge_defs.get(str(self._selected_edge)) or {})
            spotlight_nodes.add(str(edge_def.get("n1") or ""))
            spotlight_nodes.add(str(edge_def.get("n2") or ""))
        if self._hover_kind == "node" and self._hover_name:
            spotlight_nodes.add(self._hover_name)
        if route_terminal_meta:
            spotlight_nodes.update(
                name
                for name in [
                    str(route_terminal_meta.get("start_node") or ""),
                    str(route_terminal_meta.get("end_node") or ""),
                    str(route_terminal_meta.get("leading_node") or ""),
                    str(route_terminal_meta.get("trailing_node") or ""),
                ]
                if name
            )
        spotlight_nodes.update(route_intermediate_lookup.keys())

        for node_name, point in self._node_points.items():
            pressure = self._current_node_pressure(node_name)
            rgb = _pressure_to_heat_rgb(pressure)
            fill = QtGui.QColor(*rgb)
            radius = 12.0 if node_name in spotlight_nodes else 9.0
            if node_name == self._selected_node:
                radius = 14.0
            diagonal_meta = diagonal_focus_lookup.get(node_name)
            if diagonal_meta:
                ring_color = QtGui.QColor("#9fe7f7")
                severity = str(diagonal_meta.get("severity") or "attention")
                if severity == "warn":
                    ring_color = QtGui.QColor("#f8c15c")
                elif severity == "focus":
                    ring_color = QtGui.QColor("#f7fbff")
                painter.setPen(QtGui.QPen(ring_color, 3.0))
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawEllipse(point, radius + 7.0, radius + 7.0)
            route_badge = ""
            route_ring_color: QtGui.QColor | None = None
            route_badge_fill: QtGui.QColor | None = None
            if route_terminal_meta:
                leading_node = str(route_terminal_meta.get("leading_node") or "")
                trailing_node = str(route_terminal_meta.get("trailing_node") or "")
                start_node = str(route_terminal_meta.get("start_node") or "")
                end_node = str(route_terminal_meta.get("end_node") or "")
                if node_name and node_name == leading_node:
                    route_badge = (
                        str(route_terminal_meta.get("start_badge") or "")
                        if node_name == start_node
                        else str(route_terminal_meta.get("end_badge") or "")
                    )
                    route_ring_color = QtGui.QColor("#f6d98b")
                    route_badge_fill = QtGui.QColor(76, 56, 24, 228)
                elif node_name and node_name == trailing_node:
                    route_badge = (
                        str(route_terminal_meta.get("start_badge") or "")
                        if node_name == start_node
                        else str(route_terminal_meta.get("end_badge") or "")
                    )
                    route_ring_color = QtGui.QColor("#8be2f8")
                    route_badge_fill = QtGui.QColor(16, 46, 58, 228)
                elif node_name and node_name in {start_node, end_node}:
                    route_badge = (
                        str(route_terminal_meta.get("start_badge") or "")
                        if node_name == start_node
                        else str(route_terminal_meta.get("end_badge") or "")
                    )
                    route_ring_color = QtGui.QColor("#d6e8ee")
                    route_badge_fill = QtGui.QColor(22, 36, 45, 228)
            if not route_badge and node_name in route_intermediate_lookup:
                intermediate_item = route_intermediate_lookup.get(node_name) or {}
                route_badge = str(intermediate_item.get("badge_text") or "")
                kind = str(intermediate_item.get("kind") or "")
                if kind == "regulator":
                    route_ring_color = QtGui.QColor("#9fe7f7")
                    route_badge_fill = QtGui.QColor(18, 52, 64, 228)
                elif kind == "diagonal":
                    route_ring_color = QtGui.QColor("#9ce8ba")
                    route_badge_fill = QtGui.QColor(18, 56, 42, 228)
                elif kind == "chamber":
                    route_ring_color = QtGui.QColor("#d6e8ee")
                    route_badge_fill = QtGui.QColor(26, 40, 49, 228)
                else:
                    route_ring_color = QtGui.QColor("#bfdce6")
                    route_badge_fill = QtGui.QColor(24, 36, 45, 228)
            if route_ring_color is not None:
                route_leading_node = str(route_terminal_meta.get("leading_node") or "") if route_terminal_meta else ""
                painter.setPen(
                    QtGui.QPen(
                        route_ring_color,
                        3.4 if node_name == route_leading_node else 2.6,
                    )
                )
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawEllipse(point, radius + 10.0, radius + 10.0)
            painter.setPen(QtGui.QPen(QtGui.QColor("#f7fbff" if node_name == self._selected_node else "#102028"), 2.0))
            painter.setBrush(fill)
            painter.drawEllipse(point, radius, radius)

            if node_name not in spotlight_nodes:
                continue
            label_rect = QtCore.QRectF(point.x() - 82.0, point.y() - 54.0, 164.0, 34.0)
            label_bg = QtGui.QColor(fill)
            label_bg.setAlpha(228)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(label_bg)
            painter.drawRoundedRect(label_rect, 12.0, 12.0)
            painter.setPen(QtGui.QColor(_text_color_for_rgb(rgb)))
            label_font = QtGui.QFont(self.font())
            label_font.setPointSizeF(10.0)
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.drawText(
                label_rect.adjusted(10.0, 6.0, -10.0, -6.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                _short_node_label(node_name),
            )

            value_rect = QtCore.QRectF(point.x() - 72.0, point.y() - 18.0, 144.0, 24.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(7, 17, 23, 212))
            painter.drawRoundedRect(value_rect, 9.0, 9.0)
            painter.setPen(QtGui.QColor("#d8eef2"))
            value_font = QtGui.QFont(self.font())
            value_font.setPointSizeF(8.5)
            painter.setFont(value_font)
            painter.drawText(
                value_rect.adjusted(8.0, 3.0, -8.0, -3.0),
                QtCore.Qt.AlignCenter,
                self._fmt_value(pressure, "бар(g)", digits=2),
            )
            if route_badge and route_badge_fill is not None and route_ring_color is not None:
                badge_rect = QtCore.QRectF(point.x() + 16.0, point.y() - 38.0, 40.0, 18.0)
                painter.setPen(QtGui.QPen(route_ring_color, 1.0))
                painter.setBrush(route_badge_fill)
                painter.drawRoundedRect(badge_rect, 8.0, 8.0)
                badge_font = QtGui.QFont(self.font())
                badge_font.setPointSizeF(7.2)
                badge_font.setBold(True)
                painter.setFont(badge_font)
                painter.setPen(QtGui.QColor("#f7fbff"))
                painter.drawText(
                    badge_rect.adjusted(4.0, 0.0, -4.0, 0.0),
                    QtCore.Qt.AlignCenter,
                    route_badge,
                )
                self._overlay_targets.append(("node", node_name, badge_rect))
            intermediate_hover_item = route_intermediate_lookup.get(node_name) or {}
            if (
                intermediate_hover_item
                and self._hover_kind == "node"
                and str(self._hover_name or "") == node_name
            ):
                summary_rect = QtCore.QRectF(point.x() - 92.0, point.y() + 12.0, 184.0, 42.0)
                summary_fill, summary_border, summary_text = self._focus_tone_colors(
                    str(intermediate_hover_item.get("tone") or "neutral")
                )
                painter.setPen(QtGui.QPen(summary_border, 1.0))
                painter.setBrush(summary_fill)
                painter.drawRoundedRect(summary_rect, 8.0, 8.0)
                summary_font = QtGui.QFont(self.font())
                summary_font.setPointSizeF(5.2)
                summary_font.setBold(True)
                painter.setFont(summary_font)
                painter.setPen(summary_text)
                painter.drawText(
                    summary_rect.adjusted(6.0, -16.0, -6.0, 0.0),
                    QtCore.Qt.AlignCenter,
                    str(intermediate_hover_item.get("summary_text") or ""),
                )
                hint_font = QtGui.QFont(self.font())
                hint_font.setPointSizeF(4.8)
                hint_font.setBold(True)
                painter.setFont(hint_font)
                painter.drawText(
                    summary_rect.adjusted(6.0, -1.0, -6.0, 0.0),
                    QtCore.Qt.AlignCenter,
                    str(intermediate_hover_item.get("lead_hint_text") or ""),
                )
                trend_font = QtGui.QFont(self.font())
                trend_font.setPointSizeF(4.6)
                trend_font.setBold(True)
                painter.setFont(trend_font)
                painter.drawText(
                    summary_rect.adjusted(6.0, 15.0, -6.0, 0.0),
                    QtCore.Qt.AlignCenter,
                    str(intermediate_hover_item.get("lead_trend_text") or ""),
                )
            self._overlay_targets.append(("node", node_name, label_rect.united(value_rect)))

    def _selected_edge_direction_payload(self, *, max_abs_flow: float) -> dict[str, Any] | None:
        if self._dataset is None or not self._selected_edge:
            return None
        edge_name = str(self._selected_edge)
        series = self._edge_series_map.get(edge_name)
        path = self._edge_paths.get(edge_name)
        if path is None or path.isEmpty():
            return None
        edge_def = dict(self._dataset.edge_defs.get(edge_name) or {})
        flow_value = self._current_edge_flow(edge_name)
        direction_meta = _edge_direction_meta(edge_def, flow_value)
        flow_rgb = _flow_to_heat_rgb(flow_value, max_abs_flow=max_abs_flow)
        endpoint_1 = str(direction_meta.get("endpoint_1") or "")
        endpoint_2 = str(direction_meta.get("endpoint_2") or "")
        endpoint_1_pressure = self._current_node_pressure(endpoint_1) if endpoint_1 else None
        endpoint_2_pressure = self._current_node_pressure(endpoint_2) if endpoint_2 else None
        component_kind = _edge_component_kind(edge_name, edge_def)
        canonical_kind = str(edge_def.get("kind") or "")
        element_meta = _edge_element_flow_contract_meta(
            canonical_kind,
            component_kind,
            direction_meta,
            q_now=flow_value,
        )
        pressure_meta = _edge_pressure_drive_meta(
            direction_meta,
            p1_bar_g=endpoint_1_pressure,
            p2_bar_g=endpoint_2_pressure,
            q_now=flow_value,
        )
        open_state = self._current_edge_open(edge_name)
        if open_state is True:
            state_label = "открыт"
        elif open_state is False:
            state_label = "закрыт"
        else:
            state_label = "нет сигнала"
        operability_meta = _edge_operability_meta(
            state_label,
            q_now=flow_value,
            pressure_meta=pressure_meta,
            element_meta=element_meta,
        )
        consistency_meta = _edge_consistency_meta(
            state_label,
            q_now=flow_value,
            pressure_meta=pressure_meta,
            element_meta=element_meta,
        )
        temporal_meta = _edge_temporal_meta(
            time_s=self._dataset.time_s,
            q_values=list(series.get("q") or []) if isinstance(series, dict) else [],
            open_values=list(series.get("open") or []) if isinstance(series, dict) else None,
            idx=self._frame_idx,
        )
        endpoint_1_series = self._node_series_map.get(endpoint_1) if endpoint_1 else None
        endpoint_2_series = self._node_series_map.get(endpoint_2) if endpoint_2 else None
        pressure_history_meta = _edge_recent_pressure_meta(
            time_s=self._dataset.time_s,
            p1_values=list(endpoint_1_series.get("p") or []) if isinstance(endpoint_1_series, dict) else None,
            p2_values=list(endpoint_2_series.get("p") or []) if isinstance(endpoint_2_series, dict) else None,
            idx=self._frame_idx,
        )
        history_meta = _edge_recent_history_meta(
            time_s=self._dataset.time_s,
            q_values=list(series.get("q") or []) if isinstance(series, dict) else [],
            open_values=list(series.get("open") or []) if isinstance(series, dict) else None,
            idx=self._frame_idx,
        )
        causality_meta = _edge_recent_causality_meta(
            state_label=state_label,
            history_meta=history_meta,
            pressure_meta=pressure_history_meta,
            temporal_meta=temporal_meta,
            consistency_meta=consistency_meta,
        )
        latency_meta = _edge_recent_latency_meta(
            time_s=self._dataset.time_s,
            q_values=list(series.get("q") or []) if isinstance(series, dict) else [],
            open_values=list(series.get("open") or []) if isinstance(series, dict) else None,
            p1_values=list(endpoint_1_series.get("p") or []) if isinstance(endpoint_1_series, dict) else None,
            p2_values=list(endpoint_2_series.get("p") or []) if isinstance(endpoint_2_series, dict) else None,
            idx=self._frame_idx,
        )
        phase_ribbon_meta = _edge_phase_ribbon_meta(latency_meta)
        operator_hint_meta = _edge_operator_hint_meta(
            component_kind=component_kind,
            canonical_kind=canonical_kind,
            operability_status=str(operability_meta.get("operability_status") or ""),
            consistency_status=str(consistency_meta.get("consistency_status") or ""),
            pressure_drive_status=str(pressure_meta.get("pressure_drive_status") or ""),
            latency_status=str(latency_meta.get("latency_status") or ""),
            phase_ribbon_bottleneck_kind=str(phase_ribbon_meta.get("phase_ribbon_bottleneck_kind") or ""),
            phase_ribbon_bottleneck_comment=str(phase_ribbon_meta.get("phase_ribbon_bottleneck_comment") or ""),
            phase_ribbon_focus_hint=str(phase_ribbon_meta.get("phase_ribbon_focus_hint") or ""),
        )
        operator_checklist_meta = _edge_operator_checklist_meta(
            component_kind=component_kind,
            canonical_kind=canonical_kind,
            operator_hint_badge=str(operator_hint_meta.get("operator_hint_badge") or ""),
            phase_ribbon_bottleneck_kind=str(phase_ribbon_meta.get("phase_ribbon_bottleneck_kind") or ""),
            operability_status=str(operability_meta.get("operability_status") or ""),
            consistency_status=str(consistency_meta.get("consistency_status") or ""),
        )
        return {
            "edge_name": edge_name,
            "path": path,
            "flow_value": float(flow_value),
            "flow_rgb": flow_rgb,
            "flow_hex": _rgb_hex(flow_rgb),
            "flow_text_hex": _text_color_for_rgb(flow_rgb),
            "component_kind": component_kind,
            "canonical_kind": canonical_kind,
            "state_label": state_label,
            "endpoint_1": endpoint_1,
            "endpoint_2": endpoint_2,
            "endpoint_1_short": str(direction_meta.get("endpoint_1_short") or "—"),
            "endpoint_2_short": str(direction_meta.get("endpoint_2_short") or "—"),
            "endpoint_1_pressure": endpoint_1_pressure,
            "endpoint_2_pressure": endpoint_2_pressure,
            "canonical_direction_label": str(direction_meta.get("canonical_direction_label") or "—"),
            "flow_direction_label": str(direction_meta.get("flow_direction_label") or "—"),
            "flow_status_label": str(direction_meta.get("flow_status_label") or "—"),
            "canonical_source": str(direction_meta.get("canonical_source") or ""),
            "canonical_sink": str(direction_meta.get("canonical_sink") or ""),
            "canonical_source_short": str(direction_meta.get("canonical_source_short") or ""),
            "canonical_sink_short": str(direction_meta.get("canonical_sink_short") or ""),
            "flow_source": str(direction_meta.get("flow_source") or ""),
            "flow_sink": str(direction_meta.get("flow_sink") or ""),
            "flow_source_short": str(direction_meta.get("flow_source_short") or ""),
            "flow_sink_short": str(direction_meta.get("flow_sink_short") or ""),
            "flow_forward": direction_meta.get("flow_forward"),
            "flow_matches_canonical": direction_meta.get("flow_matches_canonical"),
            "pressure_drive_label": str(pressure_meta.get("pressure_drive_label") or ""),
            "pressure_drive_status": str(pressure_meta.get("pressure_drive_status") or ""),
            "pressure_drive_badge": str(pressure_meta.get("pressure_drive_badge") or ""),
            "pressure_lead_short": str(pressure_meta.get("pressure_lead_short") or ""),
            "pressure_sink_short": str(pressure_meta.get("pressure_sink_short") or ""),
            "endpoint_1_pressure_role": str(pressure_meta.get("endpoint_1_pressure_role") or "P?"),
            "endpoint_2_pressure_role": str(pressure_meta.get("endpoint_2_pressure_role") or "P?"),
            "flow_vs_pressure": str(pressure_meta.get("flow_vs_pressure") or ""),
            "delta_p_bar": pressure_meta.get("delta_p_bar"),
            "element_flow_status": str(element_meta.get("element_flow_status") or ""),
            "element_flow_label": str(element_meta.get("element_flow_label") or ""),
            "element_flow_badge": str(element_meta.get("element_flow_badge") or ""),
            "element_flow_tone": str(element_meta.get("element_flow_tone") or "neutral"),
            "operability_status": str(operability_meta.get("operability_status") or ""),
            "operability_label": str(operability_meta.get("operability_label") or ""),
            "operability_badge": str(operability_meta.get("operability_badge") or ""),
            "operability_tone": str(operability_meta.get("operability_tone") or "neutral"),
            "consistency_status": str(consistency_meta.get("consistency_status") or ""),
            "consistency_label": str(consistency_meta.get("consistency_label") or ""),
            "consistency_badge": str(consistency_meta.get("consistency_badge") or ""),
            "consistency_tone": str(consistency_meta.get("consistency_tone") or "neutral"),
            "temporal_status": str(temporal_meta.get("temporal_status") or ""),
            "temporal_label": str(temporal_meta.get("temporal_label") or ""),
            "temporal_badge": str(temporal_meta.get("temporal_badge") or ""),
            "temporal_tone": str(temporal_meta.get("temporal_tone") or "neutral"),
            "temporal_window_s": float(temporal_meta.get("window_s") or 0.0),
            "temporal_dq_dt": temporal_meta.get("dq_dt"),
            "history_summary": _edge_recent_history_summary(history_meta, self._dataset.q_unit),
            "history_points": list(history_meta.get("history_points") or []),
            "history_open_blocks": list(history_meta.get("history_open_blocks") or []),
            "history_span_s": float(history_meta.get("history_span_s") or 0.0),
            "history_sample_count": int(history_meta.get("history_sample_count") or 0),
            "history_peak_abs": float(history_meta.get("history_peak_abs") or 0.0),
            "history_open_ratio": history_meta.get("history_open_ratio"),
            "history_zero_y": float(history_meta.get("history_zero_y") or 0.5),
            "pressure_history_summary": _edge_recent_pressure_summary(pressure_history_meta),
            "pressure_history_points": list(pressure_history_meta.get("pressure_history_points") or []),
            "pressure_history_span_s": float(pressure_history_meta.get("pressure_history_span_s") or 0.0),
            "pressure_history_sample_count": int(pressure_history_meta.get("pressure_history_sample_count") or 0),
            "pressure_history_peak_abs": float(pressure_history_meta.get("pressure_history_peak_abs") or 0.0),
            "pressure_history_last_delta": pressure_history_meta.get("pressure_history_last_delta"),
            "pressure_history_status": str(pressure_history_meta.get("pressure_history_status") or ""),
            "pressure_history_tone": str(pressure_history_meta.get("pressure_history_tone") or "neutral"),
            "pressure_history_zero_y": float(pressure_history_meta.get("pressure_history_zero_y") or 0.5),
            "causality_status": str(causality_meta.get("causality_status") or ""),
            "causality_label": str(causality_meta.get("causality_label") or ""),
            "causality_badge": str(causality_meta.get("causality_badge") or ""),
            "causality_tone": str(causality_meta.get("causality_tone") or "neutral"),
            "causality_summary": _edge_recent_causality_summary(causality_meta, history_meta),
            "latency_status": str(latency_meta.get("latency_status") or ""),
            "latency_label": str(latency_meta.get("latency_label") or ""),
            "latency_badge": str(latency_meta.get("latency_badge") or ""),
            "latency_tone": str(latency_meta.get("latency_tone") or "neutral"),
            "latency_s": latency_meta.get("latency_s"),
            "latency_cause": str(latency_meta.get("latency_cause") or ""),
            "latency_phase_label": str(latency_meta.get("latency_phase_label") or ""),
            "latency_signal_x": latency_meta.get("latency_signal_x"),
            "latency_dp_x": latency_meta.get("latency_dp_x"),
            "latency_q_x": latency_meta.get("latency_q_x"),
            "latency_summary": _edge_recent_latency_summary(latency_meta),
            "phase_ribbon_label": str(phase_ribbon_meta.get("phase_ribbon_label") or ""),
            "phase_ribbon_stages": list(phase_ribbon_meta.get("phase_ribbon_stages") or []),
            "phase_ribbon_intervals": list(phase_ribbon_meta.get("phase_ribbon_intervals") or []),
            "phase_ribbon_interval_label": str(phase_ribbon_meta.get("phase_ribbon_interval_label") or ""),
            "phase_ribbon_bottleneck_label": str(phase_ribbon_meta.get("phase_ribbon_bottleneck_label") or ""),
            "phase_ribbon_bottleneck_status": str(phase_ribbon_meta.get("phase_ribbon_bottleneck_status") or ""),
            "phase_ribbon_bottleneck_tone": str(phase_ribbon_meta.get("phase_ribbon_bottleneck_tone") or "neutral"),
            "phase_ribbon_bottleneck_kind": str(phase_ribbon_meta.get("phase_ribbon_bottleneck_kind") or ""),
            "phase_ribbon_bottleneck_comment": str(phase_ribbon_meta.get("phase_ribbon_bottleneck_comment") or ""),
            "phase_ribbon_focus_pair_label": str(phase_ribbon_meta.get("phase_ribbon_focus_pair_label") or ""),
            "phase_ribbon_focus_stage_labels": list(phase_ribbon_meta.get("phase_ribbon_focus_stage_labels") or []),
            "phase_ribbon_focus_hint": str(phase_ribbon_meta.get("phase_ribbon_focus_hint") or ""),
            "operator_hint_title": str(operator_hint_meta.get("operator_hint_title") or ""),
            "operator_hint_label": str(operator_hint_meta.get("operator_hint_label") or ""),
            "operator_hint_badge": str(operator_hint_meta.get("operator_hint_badge") or ""),
            "operator_hint_tone": str(operator_hint_meta.get("operator_hint_tone") or "neutral"),
            "operator_checklist_items": list(operator_checklist_meta.get("operator_checklist_items") or []),
            "operator_checklist_rows": list(operator_checklist_meta.get("operator_checklist_rows") or []),
            "operator_checklist_summary": str(operator_checklist_meta.get("operator_checklist_summary") or ""),
        }

    def _draw_selected_edge_terminal_overlay(self, painter: QtGui.QPainter) -> None:
        if self._dataset is None or not self._selected_edge:
            return
        max_abs_flow = max(
            (abs(self._current_edge_flow(edge_name)) for edge_name in self._dataset.edge_names),
            default=0.0,
        )
        payload = self._selected_edge_direction_payload(max_abs_flow=max_abs_flow)
        if payload is None:
            return
        for endpoint_key, canonical_role in (
            ("endpoint_1", "ЭЛ-вход"),
            ("endpoint_2", "ЭЛ-выход"),
        ):
            node_name = str(payload.get(endpoint_key) or "")
            if not node_name:
                continue
            point = self._node_points.get(node_name)
            if point is None:
                continue
            if node_name == str(payload.get("flow_source") or ""):
                flow_role = "Q-ист"
            elif node_name == str(payload.get("flow_sink") or ""):
                flow_role = "Q-прием"
            else:
                flow_role = "Q-пауза"
            pressure = _finite_or_none(payload.get(f"{endpoint_key}_pressure"))
            pressure_rgb = _pressure_to_heat_rgb(pressure)
            self._draw_terminal_role_badges(
                painter,
                point=point,
                pressure_rgb=pressure_rgb,
                canonical_role=canonical_role,
                pressure_role=str(payload.get(f"{endpoint_key}_pressure_role") or "P?"),
                flow_role=flow_role,
                flow_rgb=tuple(payload.get("flow_rgb") or FLOW_IDLE_RGB),
            )

    def _draw_terminal_role_badges(
        self,
        painter: QtGui.QPainter,
        *,
        point: QtCore.QPointF,
        pressure_rgb: tuple[int, int, int],
        canonical_role: str,
        pressure_role: str,
        flow_role: str,
        flow_rgb: tuple[int, int, int],
    ) -> None:
        side = 1.0 if point.x() < self._scene_rect.center().x() else -1.0
        chip_w = 82.0
        chip_h = 20.0
        x = point.x() + side * 28.0 + (0.0 if side > 0.0 else -chip_w)
        role_w = 54.0
        top_y = point.y() - 42.0
        pressure_rect = QtCore.QRectF(x + (chip_w - role_w) * 0.5, top_y, role_w, 16.0)
        canonical_rect = QtCore.QRectF(x, top_y + 18.0, chip_w, chip_h)
        flow_rect = QtCore.QRectF(x, top_y + 18.0 + chip_h + 4.0, chip_w, chip_h)
        ring_rgb = _mix_rgb(pressure_rgb, (255, 244, 199), 0.36)
        flow_fill_rgb = flow_rgb if flow_role != "Q-пауза" else (66, 80, 90)

        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor(*ring_rgb), 3.2))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(point, 19.0, 19.0)
        painter.setPen(QtGui.QPen(QtGui.QColor("#071117"), 1.0))
        painter.setBrush(QtGui.QColor(*ring_rgb))
        painter.drawRoundedRect(pressure_rect, 8.0, 8.0)
        painter.setPen(QtGui.QPen(QtGui.QColor("#071117"), 1.0))
        painter.setBrush(QtGui.QColor(7, 17, 23, 228))
        painter.drawRoundedRect(canonical_rect, 10.0, 10.0)
        font = QtGui.QFont(self.font())
        font.setPointSizeF(6.9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#071117"))
        painter.drawText(pressure_rect, QtCore.Qt.AlignCenter, pressure_role)
        painter.setPen(QtGui.QColor("#f6d98b"))
        painter.drawText(canonical_rect, QtCore.Qt.AlignCenter, canonical_role)

        painter.setPen(QtGui.QPen(QtGui.QColor("#071117"), 1.0))
        painter.setBrush(QtGui.QColor(*flow_fill_rgb))
        painter.drawRoundedRect(flow_rect, 10.0, 10.0)
        painter.setPen(QtGui.QColor(_text_color_for_rgb(flow_fill_rgb)))
        painter.drawText(flow_rect, QtCore.Qt.AlignCenter, flow_role)
        painter.restore()

    def _draw_selected_edge_direction_overlay(self, painter: QtGui.QPainter) -> None:
        if self._dataset is None or not self._selected_edge:
            return
        max_abs_flow = max(
            (abs(self._current_edge_flow(edge_name)) for edge_name in self._dataset.edge_names),
            default=0.0,
        )
        payload = self._selected_edge_direction_payload(max_abs_flow=max_abs_flow)
        if payload is None:
            return
        path = payload.get("path")
        if not isinstance(path, QtGui.QPainterPath):
            return

        self._draw_edge_direction_marker(
            painter,
            path=path,
            percent=0.28,
            forward=True,
            label="EL",
            fill_color=QtGui.QColor(7, 17, 23, 228),
            border_color=QtGui.QColor("#f6d98b"),
            text_color=QtGui.QColor("#f6d98b"),
        )
        flow_forward = payload.get("flow_forward")
        if isinstance(flow_forward, bool):
            flow_color = QtGui.QColor(str(payload.get("flow_hex") or "#63d3f5"))
            self._draw_edge_direction_marker(
                painter,
                path=path,
                percent=0.72 if flow_forward else 0.36,
                forward=flow_forward,
                label="Q",
                fill_color=flow_color,
                border_color=QtGui.QColor("#071117"),
                text_color=QtGui.QColor(str(payload.get("flow_text_hex") or "#eef7fa")),
            )

        anchor_t = 0.52
        anchor = path.pointAtPercent(anchor_t)
        angle_deg = self._path_angle_deg(path, anchor_t)
        angle_rad = math.radians(angle_deg)
        normal = QtCore.QPointF(-math.sin(angle_rad), math.cos(angle_rad))
        if abs(normal.x()) <= 1.0e-6 and abs(normal.y()) <= 1.0e-6:
            normal = QtCore.QPointF(0.0, -1.0)
        center = QtCore.QPointF(anchor.x() + normal.x() * 96.0, anchor.y() + normal.y() * 96.0)
        card_rect = QtCore.QRectF(center.x() - 202.0, center.y() - 177.0, 404.0, 486.0)
        safe_rect = self._scene_rect.adjusted(36.0, 36.0, -36.0, -36.0)
        if card_rect.left() < safe_rect.left():
            card_rect.moveLeft(safe_rect.left())
        if card_rect.right() > safe_rect.right():
            card_rect.moveRight(safe_rect.right())
        if card_rect.top() < safe_rect.top():
            card_rect.moveTop(safe_rect.top())
        if card_rect.bottom() > safe_rect.bottom():
            card_rect.moveBottom(safe_rect.bottom())

        flow_matches = payload.get("flow_matches_canonical")
        if flow_matches is True:
            badge_fill = QtGui.QColor(91, 192, 231, 220)
            badge_text = QtGui.QColor("#071117")
        elif flow_matches is False:
            badge_fill = QtGui.QColor(248, 193, 92, 232)
            badge_text = QtGui.QColor("#071117")
        else:
            badge_fill = QtGui.QColor(80, 96, 106, 224)
            badge_text = QtGui.QColor("#eef7fa")

        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#f6d98b" if flow_matches is False else "#bfdce6"), 2.0))
        painter.setBrush(QtGui.QColor(7, 17, 23, 224))
        painter.drawRoundedRect(card_rect, 16.0, 16.0)

        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(8.8)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor("#eef7fa"))
        painter.drawText(
            card_rect.adjusted(12.0, 6.0, -104.0, -50.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Направление выбранной ветви",
        )

        badge_rect = QtCore.QRectF(card_rect.right() - 96.0, card_rect.top() + 8.0, 84.0, 20.0)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(badge_fill)
        painter.drawRoundedRect(badge_rect, 10.0, 10.0)
        badge_font = QtGui.QFont(self.font())
        badge_font.setPointSizeF(7.0)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        painter.setPen(badge_text)
        painter.drawText(
            badge_rect,
            QtCore.Qt.AlignCenter,
            str(payload.get("flow_status_label") or "—"),
        )
        pressure_badge = str(payload.get("pressure_drive_badge") or "")
        if pressure_badge:
            pressure_fill = QtGui.QColor(91, 192, 231, 220)
            pressure_text = QtGui.QColor("#071117")
            if pressure_badge == "ΔP rev":
                pressure_fill = QtGui.QColor(248, 193, 92, 232)
            elif pressure_badge == "ΔP ?":
                pressure_fill = QtGui.QColor(80, 96, 106, 224)
                pressure_text = QtGui.QColor("#eef7fa")
            second_badge_rect = QtCore.QRectF(card_rect.right() - 182.0, card_rect.top() + 8.0, 78.0, 20.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(pressure_fill)
            painter.drawRoundedRect(second_badge_rect, 10.0, 10.0)
            painter.setPen(pressure_text)
            painter.drawText(second_badge_rect, QtCore.Qt.AlignCenter, pressure_badge)
        element_badge = str(payload.get("element_flow_badge") or "")
        if element_badge:
            element_tone = str(payload.get("element_flow_tone") or "neutral")
            element_fill = QtGui.QColor(80, 96, 106, 224)
            element_text = QtGui.QColor("#eef7fa")
            if element_tone == "ok":
                element_fill = QtGui.QColor(91, 192, 231, 220)
                element_text = QtGui.QColor("#071117")
            elif element_tone == "warn":
                element_fill = QtGui.QColor(248, 193, 92, 232)
                element_text = QtGui.QColor("#071117")
            elif element_tone == "info":
                element_fill = QtGui.QColor(138, 226, 248, 210)
                element_text = QtGui.QColor("#071117")
            third_badge_rect = QtCore.QRectF(card_rect.right() - 266.0, card_rect.top() + 8.0, 78.0, 20.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(element_fill)
            painter.drawRoundedRect(third_badge_rect, 10.0, 10.0)
            painter.setPen(element_text)
            painter.drawText(third_badge_rect, QtCore.Qt.AlignCenter, element_badge)
        operability_badge = str(payload.get("operability_badge") or "")
        if operability_badge:
            operability_tone = str(payload.get("operability_tone") or "neutral")
            operability_fill = QtGui.QColor(80, 96, 106, 224)
            operability_text = QtGui.QColor("#eef7fa")
            if operability_tone == "ok":
                operability_fill = QtGui.QColor(127, 228, 167, 220)
                operability_text = QtGui.QColor("#071117")
            elif operability_tone == "warn":
                operability_fill = QtGui.QColor(255, 156, 102, 236)
                operability_text = QtGui.QColor("#071117")
            elif operability_tone == "info":
                operability_fill = QtGui.QColor(138, 226, 248, 210)
                operability_text = QtGui.QColor("#071117")
            fourth_badge_rect = QtCore.QRectF(card_rect.right() - 350.0, card_rect.top() + 8.0, 78.0, 20.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(operability_fill)
            painter.drawRoundedRect(fourth_badge_rect, 10.0, 10.0)
            painter.setPen(operability_text)
            painter.drawText(fourth_badge_rect, QtCore.Qt.AlignCenter, operability_badge)
        consistency_badge = str(payload.get("consistency_badge") or "")
        if consistency_badge:
            consistency_tone = str(payload.get("consistency_tone") or "neutral")
            consistency_fill = QtGui.QColor(80, 96, 106, 224)
            consistency_text = QtGui.QColor("#eef7fa")
            if consistency_tone == "ok":
                consistency_fill = QtGui.QColor(127, 228, 167, 220)
                consistency_text = QtGui.QColor("#071117")
            elif consistency_tone == "warn":
                consistency_fill = QtGui.QColor(255, 156, 102, 236)
                consistency_text = QtGui.QColor("#071117")
            elif consistency_tone == "info":
                consistency_fill = QtGui.QColor(138, 226, 248, 210)
                consistency_text = QtGui.QColor("#071117")
            fifth_badge_rect = QtCore.QRectF(card_rect.right() - 434.0, card_rect.top() + 8.0, 78.0, 20.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(consistency_fill)
            painter.drawRoundedRect(fifth_badge_rect, 10.0, 10.0)
            painter.setPen(consistency_text)
            painter.drawText(fifth_badge_rect, QtCore.Qt.AlignCenter, consistency_badge)
        temporal_badge = str(payload.get("temporal_badge") or "")
        if temporal_badge:
            temporal_tone = str(payload.get("temporal_tone") or "neutral")
            temporal_fill = QtGui.QColor(80, 96, 106, 224)
            temporal_text = QtGui.QColor("#eef7fa")
            if temporal_tone == "ok":
                temporal_fill = QtGui.QColor(127, 228, 167, 220)
                temporal_text = QtGui.QColor("#071117")
            elif temporal_tone == "warn":
                temporal_fill = QtGui.QColor(255, 156, 102, 236)
                temporal_text = QtGui.QColor("#071117")
            elif temporal_tone == "info":
                temporal_fill = QtGui.QColor(138, 226, 248, 210)
                temporal_text = QtGui.QColor("#071117")
            sixth_badge_rect = QtCore.QRectF(card_rect.left() + 14.0, card_rect.top() + 30.0, 78.0, 20.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(temporal_fill)
            painter.drawRoundedRect(sixth_badge_rect, 10.0, 10.0)
            painter.setPen(temporal_text)
            painter.drawText(sixth_badge_rect, QtCore.Qt.AlignCenter, temporal_badge)

        row_font = QtGui.QFont(self.font())
        row_font.setPointSizeF(7.7)
        painter.setFont(row_font)
        painter.setPen(QtGui.QColor("#f6d98b"))
        painter.drawText(
            card_rect.adjusted(14.0, 28.0, -12.0, -28.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Элемент: {payload.get('canonical_direction_label') or '—'}",
        )
        painter.setPen(QtGui.QColor(str(payload.get("flow_hex") or "#63d3f5")))
        painter.drawText(
            card_rect.adjusted(14.0, 50.0, -12.0, -8.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Поток: {payload.get('flow_direction_label') or '—'}",
        )
        pressure_line = (
            f"ΔP: {float(payload.get('delta_p_bar') or 0.0):+0.2f} бар • "
            f"{payload.get('pressure_drive_label') or '—'} • "
            f"{payload.get('flow_vs_pressure') or '—'}"
            if payload.get("delta_p_bar") is not None
            else "ΔP: нет данных по давлениям"
        )
        painter.setPen(QtGui.QColor("#a7d8e5"))
        painter.drawText(
            card_rect.adjusted(14.0, 72.0, -12.0, 14.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            pressure_line,
        )
        painter.setPen(QtGui.QColor("#f5e4b0"))
        painter.drawText(
            card_rect.adjusted(14.0, 92.0, -12.0, 34.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Элемент: {payload.get('element_flow_status') or '—'}",
        )
        verdict_color = QtGui.QColor("#a7f0c6")
        if str(payload.get("operability_tone") or "neutral") == "warn":
            verdict_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("operability_tone") or "neutral") == "info":
            verdict_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("operability_tone") or "neutral") == "neutral":
            verdict_color = QtGui.QColor("#c5d2d8")
        painter.setPen(verdict_color)
        painter.drawText(
            card_rect.adjusted(14.0, 112.0, -12.0, 54.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Вердикт: {payload.get('operability_status') or '—'}",
        )
        consistency_color = QtGui.QColor("#a7f0c6")
        if str(payload.get("consistency_tone") or "neutral") == "warn":
            consistency_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("consistency_tone") or "neutral") == "info":
            consistency_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("consistency_tone") or "neutral") == "neutral":
            consistency_color = QtGui.QColor("#c5d2d8")
        painter.setPen(consistency_color)
        painter.drawText(
            card_rect.adjusted(14.0, 132.0, -12.0, 74.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Сигналы: {payload.get('consistency_status') or '—'}",
        )
        temporal_color = QtGui.QColor("#a7f0c6")
        if str(payload.get("temporal_tone") or "neutral") == "warn":
            temporal_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("temporal_tone") or "neutral") == "info":
            temporal_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("temporal_tone") or "neutral") == "neutral":
            temporal_color = QtGui.QColor("#c5d2d8")
        temporal_line = (
            f"Динамика: {payload.get('temporal_status') or '—'}"
            f" • {float(payload.get('temporal_window_s') or 0.0):0.2f} s"
        )
        if payload.get("temporal_dq_dt") is not None and self._dataset is not None:
            temporal_line += f" • dQ/dt {float(payload.get('temporal_dq_dt') or 0.0):+0.2f} {self._dataset.q_unit}/s"
        painter.setPen(temporal_color)
        painter.drawText(
            card_rect.adjusted(14.0, 152.0, -12.0, 94.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            temporal_line,
        )
        causality_color = QtGui.QColor("#a7f0c6")
        if str(payload.get("causality_tone") or "neutral") == "warn":
            causality_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("causality_tone") or "neutral") == "info":
            causality_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("causality_tone") or "neutral") == "neutral":
            causality_color = QtGui.QColor("#c5d2d8")
        painter.setPen(causality_color)
        painter.drawText(
            card_rect.adjusted(14.0, 172.0, -12.0, 114.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Причинность: {payload.get('causality_status') or '—'}",
        )
        latency_color = QtGui.QColor("#a7f0c6")
        if str(payload.get("latency_tone") or "neutral") == "warn":
            latency_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("latency_tone") or "neutral") == "info":
            latency_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("latency_tone") or "neutral") == "neutral":
            latency_color = QtGui.QColor("#c5d2d8")
        latency_line = f"Лаг: {payload.get('latency_status') or '—'}"
        if payload.get("latency_s") is not None:
            latency_line += f" • Δt {float(payload.get('latency_s') or 0.0):+0.2f} s"
        painter.setPen(latency_color)
        painter.drawText(
            card_rect.adjusted(14.0, 192.0, -12.0, 134.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            latency_line,
        )
        painter.setPen(QtGui.QColor("#bfdce6"))
        painter.drawText(
            card_rect.adjusted(14.0, 212.0, -12.0, 154.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Фаза: {payload.get('latency_phase_label') or '—'}",
        )
        bottleneck_color = QtGui.QColor("#bfdce6")
        if str(payload.get("phase_ribbon_bottleneck_tone") or "neutral") == "warn":
            bottleneck_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("phase_ribbon_bottleneck_tone") or "neutral") == "info":
            bottleneck_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("phase_ribbon_bottleneck_tone") or "neutral") == "ok":
            bottleneck_color = QtGui.QColor("#a7f0c6")
        painter.setPen(bottleneck_color)
        bottleneck_line = f"Узкое место: {payload.get('phase_ribbon_bottleneck_label') or '—'}"
        bottleneck_kind = str(payload.get("phase_ribbon_bottleneck_kind") or "")
        if bottleneck_kind:
            bottleneck_line += f" • {bottleneck_kind}"
        painter.drawText(
            card_rect.adjusted(14.0, 232.0, -12.0, 174.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            bottleneck_line,
        )
        operator_hint_color = QtGui.QColor("#bfdce6")
        if str(payload.get("operator_hint_tone") or "neutral") == "warn":
            operator_hint_color = QtGui.QColor("#ffbf9f")
        elif str(payload.get("operator_hint_tone") or "neutral") == "info":
            operator_hint_color = QtGui.QColor("#a7d8e5")
        elif str(payload.get("operator_hint_tone") or "neutral") == "ok":
            operator_hint_color = QtGui.QColor("#a7f0c6")
        painter.setPen(operator_hint_color)
        painter.drawText(
            card_rect.adjusted(14.0, 252.0, -12.0, 194.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Сначала: {payload.get('operator_hint_title') or '—'}",
        )
        painter.setPen(operator_hint_color)
        painter.drawText(
            card_rect.adjusted(14.0, 272.0, -12.0, 214.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Проверь: {payload.get('operator_checklist_summary') or '—'}",
        )
        checklist_rect = QtCore.QRectF(card_rect.left() + 14.0, card_rect.top() + 296.0, card_rect.width() - 28.0, 58.0)
        self._draw_edge_operator_checklist(
            painter,
            rect=checklist_rect,
            payload=payload,
        )
        phase_ribbon_rect = QtCore.QRectF(card_rect.left() + 14.0, card_rect.bottom() - 128.0, card_rect.width() - 28.0, 24.0)
        self._draw_edge_phase_ribbon(
            painter,
            rect=phase_ribbon_rect,
            payload=payload,
        )
        history_strip_rect = QtCore.QRectF(card_rect.left() + 14.0, card_rect.bottom() - 92.0, card_rect.width() - 28.0, 28.0)
        self._draw_edge_recent_history_strip(
            painter,
            rect=history_strip_rect,
            payload=payload,
        )
        pressure_history_strip_rect = QtCore.QRectF(card_rect.left() + 14.0, card_rect.bottom() - 54.0, card_rect.width() - 28.0, 24.0)
        self._draw_edge_recent_pressure_strip(
            painter,
            rect=pressure_history_strip_rect,
            payload=payload,
        )
        painter.restore()

    def _draw_edge_direction_marker(
        self,
        painter: QtGui.QPainter,
        *,
        path: QtGui.QPainterPath,
        percent: float,
        forward: bool,
        label: str,
        fill_color: QtGui.QColor,
        border_color: QtGui.QColor,
        text_color: QtGui.QColor,
    ) -> None:
        center = path.pointAtPercent(max(0.08, min(0.92, float(percent))))
        angle = self._path_angle_deg(path, percent)
        if not forward:
            angle += 180.0
        painter.save()
        painter.translate(center)
        painter.rotate(angle)
        body_w = 42.0
        body_h = 20.0
        tip_w = 10.0
        arrow = QtGui.QPainterPath()
        arrow.moveTo(-body_w * 0.5, -body_h * 0.5)
        arrow.lineTo(body_w * 0.5 - tip_w, -body_h * 0.5)
        arrow.lineTo(body_w * 0.5, 0.0)
        arrow.lineTo(body_w * 0.5 - tip_w, body_h * 0.5)
        arrow.lineTo(-body_w * 0.5, body_h * 0.5)
        arrow.closeSubpath()
        painter.setPen(QtGui.QPen(border_color, 1.6))
        painter.setBrush(fill_color)
        painter.drawPath(arrow)
        font = QtGui.QFont(self.font())
        font.setPointSizeF(6.6)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            QtCore.QRectF(-body_w * 0.5 + 3.0, -body_h * 0.5, body_w - tip_w - 4.0, body_h),
            QtCore.Qt.AlignCenter,
            str(label or ""),
        )
        painter.restore()

    def _draw_edge_recent_history_strip(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
    ) -> None:
        points = list(payload.get("history_points") or [])
        if not points:
            return

        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(11, 26, 34, 232))
        painter.drawRoundedRect(rect, 11.0, 11.0)

        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(6.4)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor("#bfdce6"))
        painter.drawText(
            QtCore.QRectF(rect.left() + 8.0, rect.top() + 2.0, 210.0, 12.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Последние {float(payload.get('history_span_s') or 0.0):0.2f} s",
        )
        painter.drawText(
            QtCore.QRectF(rect.right() - 168.0, rect.top() + 2.0, 160.0, 12.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"|Q|max {float(payload.get('history_peak_abs') or 0.0):0.1f}",
        )

        trace_rect = QtCore.QRectF(rect.left() + 8.0, rect.top() + 13.0, rect.width() - 16.0, rect.height() - 17.0)
        zero_y = trace_rect.top() + trace_rect.height() * float(payload.get("history_zero_y") or 0.5)
        painter.setPen(QtGui.QPen(QtGui.QColor(112, 134, 146, 110), 1.0, QtCore.Qt.DashLine))
        painter.drawLine(QtCore.QPointF(trace_rect.left(), zero_y), QtCore.QPointF(trace_rect.right(), zero_y))

        open_blocks = list(payload.get("history_open_blocks") or [])
        if open_blocks:
            gate_rect = QtCore.QRectF(trace_rect.left(), trace_rect.bottom() - 5.0, trace_rect.width(), 5.0)
            painter.setPen(QtCore.Qt.NoPen)
            for block in open_blocks:
                x0 = float(block.get("x0") or 0.0)
                x1 = float(block.get("x1") or 0.0)
                block_rect = QtCore.QRectF(
                    gate_rect.left() + gate_rect.width() * x0,
                    gate_rect.top(),
                    max(2.0, gate_rect.width() * max(0.0, x1 - x0) - 1.0),
                    gate_rect.height(),
                )
                block_fill = QtGui.QColor(127, 228, 167, 190) if bool(block.get("open")) else QtGui.QColor(70, 84, 95, 175)
                painter.setBrush(block_fill)
                painter.drawRoundedRect(block_rect, 2.0, 2.0)

        trace_height = max(8.0, trace_rect.height() - 8.0)
        line_path = QtGui.QPainterPath()
        for point_idx, point in enumerate(points):
            x_norm = float(point[0]) if len(point) >= 1 else 0.0
            y_norm = float(point[1]) if len(point) >= 2 else 0.5
            trace_point = QtCore.QPointF(
                trace_rect.left() + trace_rect.width() * x_norm,
                trace_rect.top() + max(0.0, min(1.0, y_norm)) * trace_height,
            )
            if point_idx == 0:
                line_path.moveTo(trace_point)
            else:
                line_path.lineTo(trace_point)

        flow_color = QtGui.QColor(str(payload.get("flow_hex") or "#63d3f5"))
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(flow_color.lighter(115), 4.4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(line_path)
        painter.setPen(QtGui.QPen(flow_color, 2.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(line_path)

        self._draw_strip_marker(
            painter,
            rect=trace_rect,
            x_norm=payload.get("latency_signal_x"),
            label="SIG",
            color=QtGui.QColor("#f6d98b"),
            emphasized="SIG" in list(payload.get("phase_ribbon_focus_stage_labels") or []),
        )
        self._draw_strip_marker(
            painter,
            rect=trace_rect,
            x_norm=payload.get("latency_q_x"),
            label="Q",
            color=flow_color,
            emphasized="Q" in list(payload.get("phase_ribbon_focus_stage_labels") or []),
        )

        last_point = line_path.currentPosition()
        painter.setPen(QtGui.QPen(QtGui.QColor("#071117"), 1.0))
        painter.setBrush(flow_color)
        painter.drawEllipse(last_point, 3.2, 3.2)
        painter.restore()

    def _draw_edge_recent_pressure_strip(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
    ) -> None:
        points = list(payload.get("pressure_history_points") or [])
        if not points:
            return

        tone = str(payload.get("pressure_history_tone") or "neutral")
        trace_color = QtGui.QColor("#a7d8e5")
        if tone == "warn":
            trace_color = QtGui.QColor("#f8c15c")
        elif tone == "ok":
            trace_color = QtGui.QColor("#8ee7b8")
        elif tone == "info":
            trace_color = QtGui.QColor("#9de1ff")

        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(9, 21, 30, 228))
        painter.drawRoundedRect(rect, 10.0, 10.0)

        caption_font = QtGui.QFont(self.font())
        caption_font.setPointSizeF(6.2)
        caption_font.setBold(True)
        painter.setFont(caption_font)
        painter.setPen(QtGui.QColor("#bfdce6"))
        painter.drawText(
            QtCore.QRectF(rect.left() + 8.0, rect.top() + 1.0, 188.0, 10.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"ΔP-контур • {str(payload.get('pressure_history_status') or '—')}",
        )
        painter.drawText(
            QtCore.QRectF(rect.right() - 160.0, rect.top() + 1.0, 152.0, 10.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"|ΔP|max {float(payload.get('pressure_history_peak_abs') or 0.0):0.2f}",
        )

        trace_rect = QtCore.QRectF(rect.left() + 8.0, rect.top() + 11.0, rect.width() - 16.0, rect.height() - 14.0)
        zero_y = trace_rect.top() + trace_rect.height() * float(payload.get("pressure_history_zero_y") or 0.5)
        painter.setPen(QtGui.QPen(QtGui.QColor(112, 134, 146, 110), 1.0, QtCore.Qt.DashLine))
        painter.drawLine(QtCore.QPointF(trace_rect.left(), zero_y), QtCore.QPointF(trace_rect.right(), zero_y))

        line_path = QtGui.QPainterPath()
        for point_idx, point in enumerate(points):
            x_norm = float(point[0]) if len(point) >= 1 else 0.0
            y_norm = float(point[1]) if len(point) >= 2 else 0.5
            trace_point = QtCore.QPointF(
                trace_rect.left() + trace_rect.width() * x_norm,
                trace_rect.top() + max(0.0, min(1.0, y_norm)) * trace_rect.height(),
            )
            if point_idx == 0:
                line_path.moveTo(trace_point)
            else:
                line_path.lineTo(trace_point)

        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(trace_color.lighter(115), 3.6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(line_path)
        painter.setPen(QtGui.QPen(trace_color, 1.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPath(line_path)
        self._draw_strip_marker(
            painter,
            rect=trace_rect,
            x_norm=payload.get("latency_dp_x"),
            label="ΔP",
            color=trace_color,
            emphasized="ΔP" in list(payload.get("phase_ribbon_focus_stage_labels") or []),
        )
        last_point = line_path.currentPosition()
        painter.setPen(QtGui.QPen(QtGui.QColor("#071117"), 1.0))
        painter.setBrush(trace_color)
        painter.drawEllipse(last_point, 2.8, 2.8)
        painter.restore()

    def _draw_edge_phase_ribbon(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
    ) -> None:
        stages = list(payload.get("phase_ribbon_stages") or [])
        if not stages:
            return

        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(10, 22, 31, 228))
        painter.drawRoundedRect(rect, 10.0, 10.0)

        centers: list[QtCore.QPointF] = []
        step = rect.width() / max(1, len(stages))
        for idx, _stage in enumerate(stages):
            centers.append(QtCore.QPointF(rect.left() + step * (idx + 0.5), rect.center().y()))

        painter.setPen(QtGui.QPen(QtGui.QColor(88, 110, 122, 168), 2.0))
        intervals = list(payload.get("phase_ribbon_intervals") or [])
        for pair_idx, (p1, p2) in enumerate(zip(centers[:-1], centers[1:])):
            if pair_idx >= len(intervals):
                painter.setPen(QtGui.QPen(QtGui.QColor(88, 110, 122, 168), 2.0))
                painter.drawLine(QtCore.QPointF(p1.x() + 34.0, p1.y()), QtCore.QPointF(p2.x() - 34.0, p2.y()))
                continue
            interval = intervals[pair_idx]
            connector_color = QtGui.QColor(88, 110, 122, 168)
            connector_width = 2.0
            if bool(interval.get("is_bottleneck")):
                interval_kind = str(interval.get("kind") or "")
                if interval_kind == "control":
                    connector_color = QtGui.QColor("#f6d98b")
                elif interval_kind == "response":
                    connector_color = QtGui.QColor("#63d3f5")
                else:
                    connector_color = QtGui.QColor("#ff9c66")
                connector_width = 3.0
            painter.setPen(QtGui.QPen(connector_color, connector_width))
            painter.drawLine(QtCore.QPointF(p1.x() + 34.0, p1.y()), QtCore.QPointF(p2.x() - 34.0, p2.y()))
            interval_tone = str(interval.get("tone") or "neutral")
            interval_fill = QtGui.QColor(70, 84, 95, 220)
            interval_text = QtGui.QColor("#eef7fa")
            if interval_tone == "ok":
                interval_fill = QtGui.QColor(127, 228, 167, 220)
                interval_text = QtGui.QColor("#071117")
            elif interval_tone == "info":
                interval_fill = QtGui.QColor(138, 226, 248, 210)
                interval_text = QtGui.QColor("#071117")
            elif interval_tone == "warn":
                interval_fill = QtGui.QColor(255, 156, 102, 236)
                interval_text = QtGui.QColor("#071117")
            mid_x = (p1.x() + p2.x()) * 0.5
            mid_y = p1.y() - 0.5
            interval_rect = QtCore.QRectF(mid_x - 24.0, mid_y - 7.0, 48.0, 14.0)
            border_color = QtGui.QColor("#071117")
            border_width = 1.0
            if bool(interval.get("is_bottleneck")):
                border_color = QtGui.QColor("#f6d98b")
                border_width = 2.0
            painter.setPen(QtGui.QPen(border_color, border_width))
            painter.setBrush(interval_fill)
            painter.drawRoundedRect(interval_rect, 6.0, 6.0)
            painter.setPen(interval_text)
            painter.drawText(interval_rect, QtCore.Qt.AlignCenter, str(interval.get("chip_text") or "—"))

        chip_w = min(90.0, max(74.0, step - 20.0))
        chip_h = rect.height() - 8.0
        font = QtGui.QFont(self.font())
        font.setPointSizeF(6.1)
        font.setBold(True)
        painter.setFont(font)

        for center, stage in zip(centers, stages):
            tone = str(stage.get("tone") or "neutral")
            fill = QtGui.QColor(70, 84, 95, 220)
            text = QtGui.QColor("#eef7fa")
            if tone == "ok":
                fill = QtGui.QColor(127, 228, 167, 220)
                text = QtGui.QColor("#071117")
            elif tone == "info":
                fill = QtGui.QColor(138, 226, 248, 210)
                text = QtGui.QColor("#071117")
            elif tone == "warn":
                fill = QtGui.QColor(255, 156, 102, 236)
                text = QtGui.QColor("#071117")
            chip_rect = QtCore.QRectF(center.x() - chip_w * 0.5, center.y() - chip_h * 0.5, chip_w, chip_h)
            stage_border = QtGui.QColor("#071117")
            stage_border_width = 1.0
            if str(stage.get("label") or "") in list(payload.get("phase_ribbon_focus_stage_labels") or []):
                stage_border = QtGui.QColor("#f6d98b")
                stage_border_width = 2.0
            painter.setPen(QtGui.QPen(stage_border, stage_border_width))
            painter.setBrush(fill)
            painter.drawRoundedRect(chip_rect, 9.0, 9.0)
            painter.setPen(text)
            painter.drawText(chip_rect, QtCore.Qt.AlignCenter, str(stage.get("chip_text") or stage.get("label") or "—"))
        painter.restore()

    def _draw_strip_marker(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        x_norm: Any,
        label: str,
        color: QtGui.QColor,
        emphasized: bool = False,
    ) -> None:
        marker_x = _finite_or_none(x_norm)
        if marker_x is None:
            return
        x = rect.left() + rect.width() * max(0.0, min(1.0, float(marker_x)))
        painter.save()
        line_width = 2.2 if emphasized else 1.2
        painter.setPen(QtGui.QPen(color, line_width, QtCore.Qt.DashLine))
        painter.drawLine(QtCore.QPointF(x, rect.top()), QtCore.QPointF(x, rect.bottom()))
        chip_rect = QtCore.QRectF(x - 16.0, rect.top() - 2.0, 32.0, 12.0) if emphasized else QtCore.QRectF(x - 15.0, rect.top() - 1.0, 30.0, 10.0)
        chip_border = QtGui.QColor("#f6d98b") if emphasized else QtGui.QColor("#071117")
        chip_border_width = 1.8 if emphasized else 1.0
        painter.setPen(QtGui.QPen(chip_border, chip_border_width))
        painter.setBrush(color)
        painter.drawRoundedRect(chip_rect, 4.0, 4.0)
        font = QtGui.QFont(self.font())
        font.setPointSizeF(5.8 if emphasized else 5.6)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(_text_color_for_rgb((color.red(), color.green(), color.blue()))))
        painter.drawText(chip_rect, QtCore.Qt.AlignCenter, label)
        painter.restore()

    def _draw_edge_operator_checklist(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
    ) -> None:
        rows = list(payload.get("operator_checklist_rows") or [])[:3]
        if not rows:
            return

        painter.save()
        gap = 4.0
        row_h = max(16.0, min(18.0, (rect.height() - gap * (len(rows) - 1)) / max(1, len(rows))))
        index_w = 30.0
        text_font = QtGui.QFont(self.font())
        text_font.setPointSizeF(6.35)
        number_font = QtGui.QFont(self.font())
        number_font.setPointSizeF(6.1)
        number_font.setBold(True)
        y = rect.top()

        for row in rows:
            tone = str(row.get("tone") or "neutral")
            is_focus = bool(row.get("is_focus"))
            fill = QtGui.QColor(24, 36, 45, 216)
            border = QtGui.QColor("#4f6470")
            number_fill = QtGui.QColor(69, 84, 95, 228)
            text_color = QtGui.QColor("#eef7fa")
            number_color = QtGui.QColor("#eef7fa")
            if tone == "warn":
                fill = QtGui.QColor(72, 47, 34, 226)
                border = QtGui.QColor("#ffb587")
                number_fill = QtGui.QColor(255, 156, 102, 236)
                text_color = QtGui.QColor("#fff4ed")
                number_color = QtGui.QColor("#071117")
            elif tone == "info":
                fill = QtGui.QColor(22, 44, 54, 220)
                border = QtGui.QColor("#7fcde0")
                number_fill = QtGui.QColor(138, 226, 248, 210)
                text_color = QtGui.QColor("#eef7fa")
                number_color = QtGui.QColor("#071117")
            if is_focus and tone == "neutral":
                border = QtGui.QColor("#f6d98b")

            row_rect = QtCore.QRectF(rect.left(), y, rect.width(), row_h)
            number_rect = QtCore.QRectF(row_rect.left(), row_rect.top(), index_w, row_rect.height())
            text_rect = QtCore.QRectF(row_rect.left() + index_w + 6.0, row_rect.top(), row_rect.width() - index_w - 6.0, row_rect.height())
            painter.setPen(QtGui.QPen(border, 1.4 if is_focus else 1.0))
            painter.setBrush(fill)
            painter.drawRoundedRect(text_rect, 8.0, 8.0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(number_fill)
            painter.drawRoundedRect(number_rect, 8.0, 8.0)

            painter.setFont(number_font)
            painter.setPen(number_color)
            painter.drawText(number_rect, QtCore.Qt.AlignCenter, str(row.get("index_label") or "—"))

            painter.setFont(text_font)
            painter.setPen(text_color)
            metrics = QtGui.QFontMetrics(text_font)
            elided = metrics.elidedText(str(row.get("title") or "—"), QtCore.Qt.ElideRight, max(20, int(text_rect.width() - 12.0)))
            painter.drawText(
                text_rect.adjusted(10.0, 0.0, -8.0, 0.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                elided,
            )
            y += row_h + gap
        painter.restore()

    def _draw_focus_overlay(self, painter: QtGui.QPainter) -> None:
        if not self._focus_region:
            return
        target_rect = self._focus_scene_rect(self._focus_region)
        if target_rect is None:
            return
        glow_color = QtGui.QColor("#f8c15c" if self._mode == "focus" else "#63d3f5")
        glow_color.setAlpha(135 if self._mode == "focus" else 96)
        fill_color = QtGui.QColor(glow_color)
        fill_color.setAlpha(28 if self._mode == "focus" else 16)
        painter.setBrush(fill_color)
        painter.setPen(
            QtGui.QPen(
                glow_color,
                8.0 if self._mode == "focus" else 5.0,
                QtCore.Qt.DashLine,
                QtCore.Qt.RoundCap,
                QtCore.Qt.RoundJoin,
            )
        )
        painter.drawRoundedRect(target_rect, 36.0, 36.0)

    def _draw_alert_markers(self, painter: QtGui.QPainter) -> None:
        if not self._alerts:
            return
        edge_items = list(self._alerts.get("edges") or [])
        if self._detail_mode == "quiet":
            edge_items = [item for item in edge_items if str(item.get("name") or "") == self._selected_edge][:1] or edge_items[:1]
        for item in edge_items:
            edge_name = str(item.get("name") or "")
            midpoint = self._edge_midpoints.get(edge_name)
            if midpoint is None:
                continue
            rect = QtCore.QRectF(midpoint.x() - 68.0, midpoint.y() - 80.0, 136.0, 26.0)
            self._draw_chip(
                painter,
                rect,
                text=str(item.get("label") or item.get("severity") or "edge"),
                color_hex=self._severity_color_hex(str(item.get("severity") or "info")),
                text_hex="#f7fbff",
            )

        for item in list(self._alerts.get("nodes") or []):
            node_name = str(item.get("name") or "")
            point = self._node_points.get(node_name)
            if point is None:
                continue
            painter.setPen(
                QtGui.QPen(QtGui.QColor(self._severity_color_hex(str(item.get("severity") or "info"))), 4.0)
            )
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(point, 22.0, 22.0)

    def _draw_diagnostics_overlay(self, painter: QtGui.QPainter) -> None:
        diagnostics = self._diagnostics if isinstance(self._diagnostics, dict) else {}
        cylinder_payloads = list(diagnostics.get("cylinders") or [])
        component_payloads = list(diagnostics.get("components") or [])
        if self._detail_mode == "quiet":
            focus_corner = str(diagnostics.get("focus_corner") or "")
            selected_node = str(diagnostics.get("selected_node") or "")
            filtered = [
                payload
                for payload in cylinder_payloads
                if str(payload.get("corner") or "") == focus_corner or str(payload.get("focus_node") or "") == selected_node
            ]
            cylinder_payloads = filtered[:2] if filtered else cylinder_payloads[:1]
            component_payloads = []
        elif self._detail_mode == "operator":
            component_payloads = component_payloads[:8]
        for payload in cylinder_payloads:
            if not isinstance(payload, dict):
                continue
            rect = self._cylinder_card_rect(payload)
            self._draw_cylinder_card(painter, rect, payload)
        for payload in component_payloads:
            if not isinstance(payload, dict):
                continue
            rect = self._component_badge_rect(payload)
            if rect is None:
                continue
            self._draw_component_badge(painter, rect, payload)

    def _selected_edge_focus_payload(self) -> dict[str, Any] | None:
        payload = _build_selected_edge_focus_meta(self._dataset, self._frame_idx, edge_name=self._selected_edge)
        if not payload:
            return None
        active_step = str(self._selected_focus_step or "")
        payload["active_step_label"] = active_step
        if active_step:
            payload["phase_items"] = [
                {
                    **dict(item),
                    "is_active": str(item.get("step_label") or "") == active_step,
                }
                for item in list(payload.get("phase_items") or [])
            ]
            payload["terminal_markers"] = [
                {
                    **dict(item),
                    "is_active": str(item.get("step_label") or "") == active_step,
                }
                for item in list(payload.get("terminal_markers") or [])
            ]
            payload["step_rows"] = [
                {
                    **dict(item),
                    "is_active": str(item.get("index_label") or "") == active_step,
                }
                for item in list(payload.get("step_rows") or [])
            ]
        return payload

    @staticmethod
    def _focus_tone_colors(tone: str) -> tuple[QtGui.QColor, QtGui.QColor, QtGui.QColor]:
        key = str(tone or "neutral").strip().lower()
        if key == "warn":
            return QtGui.QColor(72, 47, 34, 228), QtGui.QColor("#ffb587"), QtGui.QColor("#fff4ed")
        if key == "info":
            return QtGui.QColor(22, 44, 54, 222), QtGui.QColor("#7fcde0"), QtGui.QColor("#eef7fa")
        if key == "ok":
            return QtGui.QColor(26, 52, 40, 224), QtGui.QColor("#9ce8ba"), QtGui.QColor("#effdf5")
        return QtGui.QColor(24, 36, 45, 216), QtGui.QColor("#4f6470"), QtGui.QColor("#eef7fa")

    def _draw_selected_edge_focus_overlay(self, painter: QtGui.QPainter) -> None:
        payload = self._selected_edge_focus_payload()
        if payload is None:
            return
        edge_name = str(payload.get("edge_name") or "")
        midpoint = self._edge_midpoints.get(edge_name)
        if midpoint is None:
            return

        self._draw_selected_edge_focus_terminals(painter, payload)

        card_rect = QtCore.QRectF(midpoint.x() - 190.0, midpoint.y() - 154.0, 380.0, 164.0)
        safe_rect = self._scene_rect.adjusted(28.0, 28.0, -28.0, -28.0)
        if card_rect.left() < safe_rect.left():
            card_rect.moveLeft(safe_rect.left())
        if card_rect.right() > safe_rect.right():
            card_rect.moveRight(safe_rect.right())
        if card_rect.top() < safe_rect.top():
            card_rect.moveTop(safe_rect.top())
        if card_rect.bottom() > safe_rect.bottom():
            card_rect.moveBottom(safe_rect.bottom())

        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#f6d98b"), 2.0))
        painter.setBrush(QtGui.QColor(7, 17, 23, 228))
        painter.drawRoundedRect(card_rect, 18.0, 18.0)
        self._overlay_targets.append(("edge", edge_name, card_rect))

        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(8.9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor("#eef7fa"))
        painter.drawText(
            card_rect.adjusted(14.0, 10.0, -14.0, -126.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Инженерный фокус ветви",
        )

        body_font = QtGui.QFont(self.font())
        body_font.setPointSizeF(7.4)
        painter.setFont(body_font)
        painter.setPen(QtGui.QColor("#9fc5d2"))
        painter.drawText(
            card_rect.adjusted(14.0, 30.0, -14.0, -102.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"{payload.get('edge_name') or '—'} • {payload.get('component_kind') or '—'} • {payload.get('zone_label') or '—'}",
        )
        painter.drawText(
            card_rect.adjusted(14.0, 46.0, -14.0, -86.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Клик по 01/02/03 усиливает локальный этап и при необходимости подводит playhead",
        )

        step_rows = list(payload.get("step_rows") or [])[:3]
        row_top = card_rect.top() + 64.0
        row_h = 20.0
        for idx, row in enumerate(step_rows):
            row_rect = QtCore.QRectF(card_rect.left() + 14.0, row_top + idx * (row_h + 4.0), card_rect.width() - 28.0, row_h)
            fill, border, text = self._focus_tone_colors(str(row.get("tone") or "neutral"))
            is_active = bool(row.get("is_active"))
            number_rect = QtCore.QRectF(row_rect.left(), row_rect.top(), 34.0, row_rect.height())
            phase_rect = QtCore.QRectF(row_rect.right() - 42.0, row_rect.top(), 42.0, row_rect.height())
            text_rect = QtCore.QRectF(number_rect.right() + 6.0, row_rect.top(), row_rect.width() - 88.0, row_rect.height())

            painter.setPen(QtGui.QPen(QtGui.QColor("#f6d98b") if is_active else border, 2.0 if is_active else 1.2))
            painter.setBrush(fill)
            painter.drawRoundedRect(text_rect, 8.0, 8.0)
            painter.drawRoundedRect(number_rect, 8.0, 8.0)
            painter.drawRoundedRect(phase_rect, 8.0, 8.0)

            num_font = QtGui.QFont(self.font())
            num_font.setPointSizeF(6.2)
            num_font.setBold(True)
            painter.setFont(num_font)
            painter.setPen(text)
            painter.drawText(number_rect, QtCore.Qt.AlignCenter, str(row.get("index_label") or "—"))
            painter.drawText(phase_rect, QtCore.Qt.AlignCenter, str(row.get("phase_label") or "—"))

            painter.setFont(body_font)
            metrics = QtGui.QFontMetrics(body_font)
            label = metrics.elidedText(str(row.get("title") or "—"), QtCore.Qt.ElideRight, max(40, int(text_rect.width() - 12.0)))
            painter.drawText(
                text_rect.adjusted(10.0, 0.0, -10.0, 0.0),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                label,
            )
            jump_time_s = row.get("target_time_s")
            if jump_time_s is not None:
                jump_font = QtGui.QFont(self.font())
                jump_font.setPointSizeF(5.4 if is_active else 5.2)
                painter.setFont(jump_font)
                painter.setPen(QtGui.QColor("#9fc5d2"))
                painter.drawText(
                    text_rect.adjusted(0.0, 0.0, -6.0, 0.0),
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                    f"t≈{float(jump_time_s):0.3f}s",
                )
            self._overlay_targets.append(("focus_step", str(row.get("index_label") or ""), row_rect))

        phase_rect = QtCore.QRectF(card_rect.left() + 14.0, card_rect.bottom() - 30.0, card_rect.width() - 28.0, 18.0)
        self._draw_selected_edge_phase_ribbon(painter, rect=phase_rect, payload=payload)
        painter.restore()

    def _draw_selected_edge_focus_terminals(self, painter: QtGui.QPainter, payload: dict[str, Any]) -> None:
        edge_name = str(payload.get("edge_name") or "")
        midpoint = self._edge_midpoints.get(edge_name)
        if midpoint is None:
            return
        grouped: dict[str, list[dict[str, Any]]] = {}
        for marker in list(payload.get("terminal_markers") or []):
            node_name = str(marker.get("node_name") or "")
            if not node_name:
                continue
            grouped.setdefault(node_name, []).append(dict(marker))

        for node_name, markers in grouped.items():
            point = self._node_points.get(node_name)
            if point is None:
                continue
            has_active = any(bool(marker.get("is_active")) for marker in markers)
            ring_color = QtGui.QColor("#f6d98b")
            if any(str(marker.get("tone") or "") == "warn" for marker in markers):
                ring_color = QtGui.QColor("#ffb587")
            elif any(str(marker.get("tone") or "") == "ok" for marker in markers):
                ring_color = QtGui.QColor("#9ce8ba")
            ring_color.setAlpha(255 if has_active else 214)
            painter.setPen(QtGui.QPen(ring_color, 3.4 if has_active else 2.4))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(point, 22.0 if has_active else 20.0, 22.0 if has_active else 20.0)

            side = 1.0 if point.x() <= midpoint.x() else -1.0
            chip_w = 54.0
            chip_h = 16.0
            base_x = point.x() + 14.0 if side > 0.0 else point.x() - chip_w - 14.0
            base_y = point.y() - ((len(markers) * chip_h + max(0, len(markers) - 1) * 4.0) * 0.5)
            for idx, marker in enumerate(markers):
                is_active = bool(marker.get("is_active"))
                rect = QtCore.QRectF(base_x, base_y + idx * (chip_h + 4.0), chip_w, chip_h)
                fill, border, text = self._focus_tone_colors(str(marker.get("tone") or "neutral"))
                if is_active:
                    border = QtGui.QColor("#f6d98b")
                fill.setAlpha(244 if is_active else fill.alpha())
                painter.setPen(QtGui.QPen(border, 2.0 if is_active else 1.2))
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 7.0, 7.0)
                chip_font = QtGui.QFont(self.font())
                chip_font.setPointSizeF(6.2 if is_active else 5.9)
                chip_font.setBold(True)
                painter.setFont(chip_font)
                painter.setPen(text)
                painter.drawText(
                    rect,
                    QtCore.Qt.AlignCenter,
                    f"{marker.get('step_label') or '—'} {marker.get('badge_text') or ''}".strip(),
                )

    def _draw_selected_edge_phase_ribbon(
        self,
        painter: QtGui.QPainter,
        *,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
    ) -> None:
        items = list(payload.get("phase_items") or [])
        if not items:
            return

        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#324650"), 1.2))
        painter.setBrush(QtGui.QColor(10, 22, 31, 220))
        painter.drawRoundedRect(rect, 9.0, 9.0)
        centers: list[QtCore.QPointF] = []
        step = rect.width() / max(1, len(items))
        for idx in range(len(items)):
            centers.append(QtCore.QPointF(rect.left() + step * (idx + 0.5), rect.center().y()))
        active_step = str(payload.get("active_step_label") or "")
        for pair_idx, (p1, p2) in enumerate(zip(centers[:-1], centers[1:])):
            left_item = items[pair_idx]
            right_item = items[pair_idx + 1]
            is_active_segment = active_step and (
                str(left_item.get("step_label") or "") == active_step or str(right_item.get("step_label") or "") == active_step
            )
            segment_color = QtGui.QColor("#f6d98b") if is_active_segment else QtGui.QColor("#4f6470")
            painter.setPen(QtGui.QPen(segment_color, 2.6 if is_active_segment else 1.6))
            painter.drawLine(QtCore.QPointF(p1.x() + 26.0, p1.y()), QtCore.QPointF(p2.x() - 26.0, p2.y()))

        stage_font = QtGui.QFont(self.font())
        stage_font.setPointSizeF(6.1)
        stage_font.setBold(True)
        painter.setFont(stage_font)
        for center, item in zip(centers, items):
            fill, border, text = self._focus_tone_colors(str(item.get("tone") or "neutral"))
            is_active = bool(item.get("is_active"))
            chip_rect = QtCore.QRectF(center.x() - 34.0, center.y() - 8.0, 68.0, 16.0)
            if is_active:
                border = QtGui.QColor("#f6d98b")
            fill.setAlpha(244 if is_active else fill.alpha())
            painter.setPen(QtGui.QPen(border, 2.0 if is_active else 1.2))
            painter.setBrush(fill)
            painter.drawRoundedRect(chip_rect, 8.0, 8.0)
            painter.setPen(text)
            painter.drawText(
                chip_rect,
                QtCore.Qt.AlignCenter,
                f"{item.get('step_label') or '—'} {item.get('phase_label') or '—'}",
            )
        painter.restore()

    def _draw_hud(self, painter: QtGui.QPainter) -> None:
        content_rect = self._content_rect()
        left_hud = QtCore.QRectF(content_rect.left() + 16.0, content_rect.top() + 16.0, 360.0, 88.0)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(7, 17, 23, 210))
        painter.drawRoundedRect(left_hud, 16.0, 16.0)

        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(11.5)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor("#f4fbff"))
        painter.drawText(
            left_hud.adjusted(16.0, 12.0, -16.0, -48.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Native Mnemo canvas",
        )

        body_font = QtGui.QFont(self.font())
        body_font.setPointSizeF(8.8)
        painter.setFont(body_font)
        painter.setPen(QtGui.QColor("#b8d1d9"))
        painter.drawText(
            left_hud.adjusted(16.0, 38.0, -16.0, -26.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            " • ".join(
                [
                    f"t idx {self._frame_idx}",
                    "focus" if self._mode == "focus" else "overview",
                    "play" if self._playing else "hold",
                    self._detail_mode_label().lower(),
                ]
            ),
        )
        painter.drawText(
            left_hud.adjusted(16.0, 58.0, -16.0, -10.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "wheel = zoom, drag = pan, click = select",
        )

        if not self._diagnostics:
            return
        fidelity = dict(self._diagnostics.get("scheme_fidelity") or {})
        warnings = len(list(self._diagnostics.get("geometry_warnings") or []))
        issues = len(list(self._diagnostics.get("geometry_issues") or []))
        right_hud = QtCore.QRectF(content_rect.right() - 360.0, content_rect.top() + 16.0, 344.0, 108.0)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(7, 17, 23, 204))
        painter.drawRoundedRect(right_hud, 16.0, 16.0)
        painter.setPen(QtGui.QColor("#d9eef2"))
        painter.setFont(title_font)
        painter.drawText(
            right_hud.adjusted(16.0, 12.0, -16.0, -48.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Diagnostics",
        )
        painter.setFont(body_font)
        painter.setPen(QtGui.QColor("#b8d1d9"))
        painter.drawText(
            right_hud.adjusted(16.0, 34.0, -16.0, -52.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            "Schema "
            + f"{int(fidelity.get('canonical_nodes_positioned') or 0)}/{int(fidelity.get('canonical_nodes_total') or 0)} nodes"
            + " • "
            + f"{int(fidelity.get('canonical_edges_routed') or 0)}/{int(fidelity.get('canonical_edges_total') or 0)} routes",
        )
        painter.drawText(
            right_hud.adjusted(16.0, 56.0, -16.0, -30.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Cylinders {len(list(self._diagnostics.get('cylinders') or []))} • Components {len(list(self._diagnostics.get('components') or []))}",
        )
        painter.drawText(
            right_hud.adjusted(16.0, 78.0, -16.0, -8.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"Geometry warnings {warnings} • issues {issues}",
        )

    def _draw_empty_state(self, painter: QtGui.QPainter) -> None:
        painter.fillRect(self.rect(), QtGui.QColor("#071117"))
        rect = self.rect().adjusted(40, 40, -40, -40)
        painter.setPen(QtGui.QPen(QtGui.QColor("#63d3f5"), 2.0))
        painter.setBrush(QtGui.QColor(9, 24, 31, 220))
        painter.drawRoundedRect(rect, 24.0, 24.0)
        painter.setPen(QtGui.QColor("#eef7fa"))
        font = QtGui.QFont(self.font())
        font.setPointSizeF(14.0)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(20, 24, -20, -80), QtCore.Qt.AlignCenter, "Desktop Mnemo ждёт bundle")
        font.setPointSizeF(10.5)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#b3cbd3"))
        painter.drawText(
            rect.adjusted(30, 72, -30, -26),
            QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap,
            "Нативное Windows/Qt окно без WebEngine. Загрузите NPZ или включите follow, чтобы увидеть давление, расход, направления потоков и ход цилиндров на одной схеме.",
        )

    def _draw_chip(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
        *,
        text: str,
        color_hex: str,
        text_hex: str,
    ) -> None:
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(color_hex))
        painter.drawRoundedRect(rect, 11.0, 11.0)
        painter.setPen(QtGui.QColor(text_hex))
        font = QtGui.QFont(self.font())
        font.setPointSizeF(8.5)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(10.0, 4.0, -10.0, -4.0), QtCore.Qt.AlignCenter, str(text))

    def _cylinder_card_rect(self, payload: dict[str, Any]) -> QtCore.QRectF:
        corner = str(payload.get("corner") or "")
        cyl_index = int(payload.get("cyl_index") or 1)
        base_x, base_y = CORNER_ANCHORS.get(corner, (360.0, 820.0))
        return QtCore.QRectF(
            float(base_x) - 206.0 + float(cyl_index - 1) * 212.0,
            float(base_y) - 188.0,
            196.0,
            170.0,
        )

    def _component_badge_rect(self, payload: dict[str, Any]) -> QtCore.QRectF | None:
        edge_name = str(payload.get("edge_name") or "")
        midpoint = self._edge_midpoints.get(edge_name)
        if midpoint is None:
            return None
        order = int(payload.get("order") or 0)
        shift_x = -48.0 if order % 2 else 48.0
        shift_y = -46.0 - float(order % 3) * 36.0
        return QtCore.QRectF(midpoint.x() + shift_x - 86.0, midpoint.y() + shift_y - 26.0, 172.0, 52.0)

    def _draw_cylinder_card(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:
        cap = dict(payload.get("cap") or {})
        rod = dict(payload.get("rod") or {})
        focus_corner = str(self._diagnostics.get("focus_corner") or "")
        is_focus = str(payload.get("corner") or "") == focus_corner or str(payload.get("focus_node") or "") == self._selected_node
        border = QtGui.QColor("#f8c15c" if is_focus else "#63d3f5")
        border.setAlpha(220 if is_focus else 120)
        painter.setPen(QtGui.QPen(border, 3.0 if is_focus else 2.0))
        painter.setBrush(QtGui.QColor(8, 20, 28, 216))
        painter.drawRoundedRect(rect, 18.0, 18.0)

        title_rect = QtCore.QRectF(rect.left() + 12.0, rect.top() + 10.0, rect.width() - 24.0, 24.0)
        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(9.5)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor("#eff9fb"))
        painter.drawText(
            title_rect,
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"{payload.get('corner')} • Ц{int(payload.get('cyl_index') or 1)} • {payload.get('motion_short') or 'SIG?'}",
        )

        cap_rect = QtCore.QRectF(rect.left() + 12.0, rect.top() + 42.0, rect.width() - 24.0, 50.0)
        rod_rect = QtCore.QRectF(rect.left() + 12.0, rect.top() + 96.0, rect.width() - 24.0, 50.0)
        self._draw_chamber_panel(painter, cap_rect, cap, caption="БП")
        self._draw_chamber_panel(painter, rod_rect, rod, caption="ШП")
        self._overlay_targets.append(("node", str(cap.get("node_name") or ""), cap_rect))
        self._overlay_targets.append(("node", str(rod.get("node_name") or ""), rod_rect))

        footer_rect = QtCore.QRectF(rect.left() + 12.0, rect.bottom() - 30.0, rect.width() - 24.0, 18.0)
        footer_font = QtGui.QFont(self.font())
        footer_font.setPointSizeF(7.8)
        painter.setFont(footer_font)
        painter.setPen(QtGui.QColor("#c8dce2"))
        painter.drawText(
            footer_rect,
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"ΔP {self._fmt_value(payload.get('delta_p_bar'), 'бар', digits=2)}",
        )
        painter.drawText(
            footer_rect,
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"x {self._fmt_value(payload.get('stroke_m'), 'м', digits=3)} / v {self._fmt_value(payload.get('stroke_speed_m_s'), 'м/с', digits=3)}",
        )

    def _draw_chamber_panel(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
        *,
        caption: str,
    ) -> None:
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(str(payload.get("heat_hex") or "#22303a")))
        painter.drawRoundedRect(rect, 12.0, 12.0)
        painter.setPen(QtGui.QColor(str(payload.get("text_hex") or "#eef7fa")))
        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(8.2)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            rect.adjusted(10.0, 4.0, -10.0, -22.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"{caption} • {_short_node_label(str(payload.get('node_name') or ''))}",
        )
        body_font = QtGui.QFont(self.font())
        body_font.setPointSizeF(7.6)
        painter.setFont(body_font)
        painter.drawText(
            rect.adjusted(10.0, 20.0, -10.0, -8.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"P {self._fmt_value(payload.get('pressure_bar_g'), 'бар(g)', digits=2)}",
        )
        painter.drawText(
            rect.adjusted(10.0, 20.0, -10.0, -8.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            f"V {self._fmt_value(payload.get('volume_l'), 'л', digits=2)}",
        )

    def _draw_component_badge(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:
        flow_hex = str(payload.get("flow_hex") or "#304754")
        text_hex = str(payload.get("text_hex") or "#eef7fa")
        is_selected = bool(payload.get("is_selected"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#fff4c7" if is_selected else "#0c1620"), 2.0))
        painter.setBrush(QtGui.QColor(flow_hex))
        painter.drawRoundedRect(rect, 14.0, 14.0)
        icon_rect = QtCore.QRectF(rect.left() + 8.0, rect.top() + 8.0, 32.0, rect.height() - 16.0)
        self._draw_component_icon(painter, icon_rect, payload, text_hex=text_hex)
        painter.setPen(QtGui.QColor(text_hex))
        title_font = QtGui.QFont(self.font())
        title_font.setPointSizeF(8.8)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            rect.adjusted(46.0, 4.0, -10.0, -22.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"{payload.get('component_short') or 'LINE'} • {payload.get('state_short') or 'SIG?'}",
        )
        body_font = QtGui.QFont(self.font())
        body_font.setPointSizeF(7.4)
        painter.setFont(body_font)
        painter.drawText(
            rect.adjusted(46.0, 18.0, -10.0, -4.0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            self._fmt_value(payload.get("q_now"), self._dataset.q_unit if self._dataset is not None else "", digits=2),
        )
        painter.drawText(
            rect.adjusted(46.0, 18.0, -10.0, -4.0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            str(payload.get("zone_label") or ""),
        )
        self._overlay_targets.append(("edge", str(payload.get("edge_name") or ""), rect))

    def _inline_route_symbol_payloads(self, *, max_abs_flow: float) -> dict[str, dict[str, Any]]:
        if self._dataset is None:
            return {}
        payloads: dict[str, dict[str, Any]] = {}
        alert_edges = {
            str(item.get("name") or ""): dict(item)
            for item in list(self._alerts.get("edges") or [])
            if str(item.get("name") or "").strip()
        }
        candidates: list[dict[str, Any]] = []
        if self._detail_mode == "quiet":
            active_floor = max(28.0, float(max_abs_flow) * 0.35) if max_abs_flow > 1.0e-9 else 0.0
            max_symbols = 3
        elif self._detail_mode == "full":
            active_floor = max(8.0, float(max_abs_flow) * 0.12) if max_abs_flow > 1.0e-9 else 0.0
            max_symbols = 10
        else:
            active_floor = max(18.0, float(max_abs_flow) * 0.22) if max_abs_flow > 1.0e-9 else 0.0
            max_symbols = 6
        for edge_name in self._dataset.edge_names:
            edge_def = dict(self._dataset.edge_defs.get(edge_name) or {})
            component_kind = _edge_component_kind(edge_name, edge_def)
            canonical_kind = str(edge_def.get("kind") or "")
            icon_key = _component_icon_key(component_kind, canonical_kind)
            if icon_key == "line":
                continue
            flow_value = self._current_edge_flow(edge_name)
            flow_abs = abs(float(flow_value))
            is_selected = edge_name == self._selected_edge
            alert_meta = alert_edges.get(edge_name, {})
            is_alert = bool(alert_meta)
            if not (is_selected or is_alert or flow_abs >= active_floor):
                continue
            candidates.append(
                {
                    "edge_name": edge_name,
                    "component_kind": component_kind,
                    "component_short": _component_kind_short_label(component_kind),
                    "canonical_kind": canonical_kind,
                    "canonical_kind_label": _canonical_kind_label(canonical_kind),
                    "icon_key": icon_key,
                    "camozzi_code": str(edge_def.get("camozzi_code") or ""),
                    "zone_label": _edge_zone_label(edge_name, edge_def),
                    "flow_value": flow_value,
                    "flow_abs": flow_abs,
                    "is_selected": is_selected,
                    "is_alert": is_alert,
                    "severity": str(alert_meta.get("severity") or ("focus" if is_selected else "info")),
                    "symbol_t": 0.42 if is_selected else 0.5,
                }
            )
        candidates.sort(
            key=lambda item: (
                0 if item.get("is_selected") else 1,
                0 if item.get("is_alert") else 1,
                -float(item.get("flow_abs") or 0.0),
                str(item.get("edge_name") or ""),
            )
        )
        for item in candidates[:max_symbols]:
            payloads[str(item.get("edge_name") or "")] = item
        return payloads

    def _draw_inline_route_symbol(self, painter: QtGui.QPainter, *, edge_name: str, payload: dict[str, Any]) -> None:
        path = self._edge_paths.get(edge_name)
        if path is None or path.isEmpty():
            return
        t = max(0.1, min(0.9, float(payload.get("symbol_t") or 0.5)))
        center = path.pointAtPercent(t)
        angle = self._path_angle_deg(path, t)
        is_selected = bool(payload.get("is_selected"))
        width = 62.0 if is_selected else 54.0
        height = 28.0 if is_selected else 24.0
        border_hex = "#fff4c7" if is_selected else self._severity_color_hex(str(payload.get("severity") or "info"))
        fill = QtGui.QColor(7, 17, 23, 228 if is_selected else 212)
        painter.save()
        painter.translate(center)
        painter.rotate(angle)
        plate = QtCore.QRectF(-width * 0.5, -height * 0.5, width, height)
        painter.setPen(QtGui.QPen(QtGui.QColor(border_hex), 2.2 if is_selected else 1.8))
        painter.setBrush(fill)
        painter.drawRoundedRect(plate, 11.0, 11.0)
        icon_rect = QtCore.QRectF(plate.left() + 4.0, plate.top() + 4.0, 18.0, plate.height() - 8.0)
        self._draw_component_icon(
            painter,
            icon_rect,
            payload,
            text_hex="#eef7fa",
            draw_backplate=False,
            stroke_width=1.45,
        )
        text_rect = QtCore.QRectF(icon_rect.right() + 4.0, plate.top() + 1.0, plate.width() - 28.0, plate.height() - 2.0)
        font = QtGui.QFont(self.font())
        font.setPointSizeF(7.2 if is_selected else 6.8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#eef7fa"))
        painter.drawText(
            text_rect,
            QtCore.Qt.AlignCenter,
            str(payload.get("component_short") or "LINE"),
        )
        painter.restore()

    @staticmethod
    def _path_angle_deg(path: QtGui.QPainterPath, percent: float) -> float:
        p1 = path.pointAtPercent(max(0.0, float(percent) - 0.03))
        p2 = path.pointAtPercent(min(1.0, float(percent) + 0.03))
        dx = float(p2.x() - p1.x())
        dy = float(p2.y() - p1.y())
        if abs(dx) <= 1.0e-9 and abs(dy) <= 1.0e-9:
            return 0.0
        return math.degrees(math.atan2(dy, dx))

    def _draw_component_icon(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
        payload: dict[str, Any],
        *,
        text_hex: str,
        draw_backplate: bool = True,
        stroke_width: float = 1.8,
    ) -> None:
        painter.save()
        if draw_backplate:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(7, 17, 23, 132))
            painter.drawRoundedRect(rect, 10.0, 10.0)
        pen = QtGui.QPen(QtGui.QColor(text_hex), float(stroke_width), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(text_hex)))
        key = str(payload.get("icon_key") or "line")
        cx = rect.center().x()
        cy = rect.center().y()
        left = rect.left() + 6.0
        right = rect.right() - 6.0
        top = rect.top() + 6.0
        bottom = rect.bottom() - 6.0
        if key == "check":
            painter.drawLine(left, cy, right - 10.0, cy)
            painter.drawLine(right - 6.0, top + 1.0, right - 6.0, bottom - 1.0)
            triangle = QtGui.QPolygonF(
                [
                    QtCore.QPointF(cx - 6.0, top + 2.0),
                    QtCore.QPointF(cx - 6.0, bottom - 2.0),
                    QtCore.QPointF(right - 8.0, cy),
                ]
            )
            painter.drawPolygon(triangle)
        elif key == "orifice":
            painter.drawLine(left, cy, cx - 7.0, cy)
            painter.drawLine(cx + 7.0, cy, right, cy)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawLine(cx - 7.0, top + 3.0, cx + 1.0, bottom - 3.0)
            painter.drawLine(cx + 7.0, top + 3.0, cx - 1.0, bottom - 3.0)
        elif key == "relief":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(QtCore.QRectF(left + 2.0, top + 3.0, rect.width() - 14.0, rect.height() - 10.0))
            painter.drawLine(cx, top + 2.0, cx, top - 2.0)
            painter.drawLine(cx - 5.0, top - 1.0, cx + 5.0, top - 1.0)
            painter.drawLine(left + 2.0, bottom - 2.0, right - 2.0, bottom - 2.0)
        elif key == "reg_after":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(QtCore.QRectF(left + 2.0, top + 3.0, rect.width() - 14.0, rect.height() - 10.0))
            painter.drawLine(cx, top + 5.0, cx, bottom - 5.0)
            painter.drawLine(cx - 5.0, cy, cx, cy - 5.0)
            painter.drawLine(cx - 5.0, cy, cx, cy + 5.0)
            painter.drawLine(cx, cy, cx + 6.0, cy)
        elif key == "diagonal":
            painter.drawLine(left, top, right, bottom)
            painter.drawLine(left, bottom, right, top)
        elif key == "vent":
            painter.drawLine(cx, top + 2.0, cx, cy + 2.0)
            painter.drawLine(cx - 8.0, cy + 2.0, cx + 8.0, cy + 2.0)
            painter.drawLine(cx - 6.0, cy + 6.0, cx + 6.0, cy + 6.0)
            painter.drawLine(cx - 4.0, cy + 10.0, cx + 4.0, cy + 10.0)
        elif key == "supply":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QRectF(cx - 8.0, cy - 8.0, 16.0, 16.0))
            painter.drawLine(cx + 8.0, cy, right, cy)
        elif key == "actuator":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(QtCore.QRectF(left + 2.0, cy - 7.0, 14.0, 14.0))
            painter.drawLine(left + 16.0, cy, right, cy)
            painter.drawLine(right - 5.0, cy - 4.0, right, cy)
            painter.drawLine(right - 5.0, cy + 4.0, right, cy)
        else:
            painter.drawLine(left, cy, right, cy)
        painter.restore()

    def _current_edge_flow(self, edge_name: str) -> float:
        series = self._edge_series_map.get(edge_name)
        if not isinstance(series, dict):
            return 0.0
        values = list(series.get("q") or [])
        if not values:
            return 0.0
        idx = max(0, min(int(self._frame_idx), len(values) - 1))
        try:
            return float(values[idx])
        except Exception:
            return 0.0

    def _current_edge_open(self, edge_name: str) -> bool | None:
        series = self._edge_series_map.get(edge_name)
        if not isinstance(series, dict):
            return None
        values = series.get("open")
        if not isinstance(values, list) or not values:
            return None
        idx = max(0, min(int(self._frame_idx), len(values) - 1))
        try:
            return bool(int(values[idx]))
        except Exception:
            return None

    def _current_node_pressure(self, node_name: str) -> float | None:
        series = self._node_series_map.get(node_name)
        if not isinstance(series, dict):
            return None
        values = list(series.get("p") or [])
        if not values:
            return None
        idx = max(0, min(int(self._frame_idx), len(values) - 1))
        return _finite_or_none(values[idx])

    @staticmethod
    def _polyline_midpoint(points: list[QtCore.QPointF]) -> QtCore.QPointF | None:
        if not points:
            return None
        if len(points) == 1:
            return QtCore.QPointF(points[0])
        lengths: list[float] = []
        total = 0.0
        for p1, p2 in zip(points[:-1], points[1:]):
            seg = math.hypot(float(p2.x() - p1.x()), float(p2.y() - p1.y()))
            lengths.append(seg)
            total += seg
        if total <= 1.0e-9:
            return QtCore.QPointF(points[len(points) // 2])
        target = total * 0.5
        acc = 0.0
        for seg, p1, p2 in zip(lengths, points[:-1], points[1:]):
            if acc + seg >= target:
                ratio = 0.0 if seg <= 1.0e-9 else (target - acc) / seg
                return QtCore.QPointF(
                    float(p1.x()) + (float(p2.x()) - float(p1.x())) * ratio,
                    float(p1.y()) + (float(p2.y()) - float(p1.y())) * ratio,
                )
            acc += seg
        return QtCore.QPointF(points[-1])

    @staticmethod
    def _fmt_value(value: Any, unit: str, *, digits: int) -> str:
        finite = _finite_or_none(value)
        if finite is None:
            return f"— {unit}".strip()
        return f"{finite:.{int(digits)}f} {unit}".strip()

    @staticmethod
    def _severity_color_hex(severity: str) -> str:
        mapping = {
            "warn": "#ff9c66",
            "attention": "#f8c15c",
            "focus": "#8be2f8",
            "info": "#63d3f5",
            "ok": "#7fe4a7",
        }
        return mapping.get(str(severity or "").strip().lower(), "#63d3f5")

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
        startup_time_s: float | None,
        startup_time_label: str,
        startup_edge: str,
        startup_node: str,
        startup_event_title: str,
        startup_time_ref_npz: str,
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
        self._startup_time_s = float(startup_time_s) if startup_time_s is not None else None
        self._startup_time_label = str(startup_time_label or "").strip()
        self._startup_edge = str(startup_edge or "").strip()
        self._startup_node = str(startup_node or "").strip()
        self._startup_event_title = str(startup_event_title or "").strip()
        self._startup_time_ref_npz = (
            Path(startup_time_ref_npz).expanduser().resolve() if str(startup_time_ref_npz or "").strip() else None
        )
        self._startup_time_consumed = False
        self._startup_selection_consumed = False
        self._startup_selection_active = False
        self._last_startup_seek_applied_label = ""
        self._last_startup_selection_applied_label = ""
        self.launch_context = build_launch_onboarding_context(
            npz_path=npz_path,
            follow=self.follow_enabled,
            pointer_path=self.pointer_path,
            preset_key=startup_preset,
            title=startup_title,
            reason=startup_reason,
            startup_time_s=self._startup_time_s,
            startup_time_label=self._startup_time_label,
            checklist=startup_checklist,
        )

        self.ui_state = UiState(default_settings_path(PROJECT_ROOT), prefix="desktop_mnemo")
        self._persisted_view_mode = self._normalize_view_mode(self.ui_state.get_str("view_mode", "focus"))
        self._startup_view_mode_override = self._parse_startup_view_mode_override(startup_view_mode)
        self._view_mode_override_active = bool(self._startup_view_mode_override)
        self.view_mode = self._startup_view_mode_override or self._persisted_view_mode
        self.detail_mode = self._normalize_detail_mode(self.ui_state.get_str("detail_mode", "operator"))
        self.reference_scheme_visible = bool(self.ui_state.get_bool("reference_scheme_visible", True))
        self.setStyleSheet(APP_STYLESHEET_DARK if self.theme == "dark" else APP_STYLESHEET_LIGHT)

        self.mnemo_view = MnemoNativeView(self)
        self.native_view = self.mnemo_view
        self.mnemo_view.set_detail_mode(self.detail_mode)
        self.mnemo_view.set_reference_scheme_visible(self.reference_scheme_visible)
        self.mnemo_view.edge_picked.connect(self._select_edge)
        self.mnemo_view.node_picked.connect(self._select_node)
        self.mnemo_view.status.connect(self._set_status)
        self.mnemo_view.focus_step_jump_requested.connect(self._jump_to_focus_step)
        self.startup_banner = StartupBannerPanel(self)
        self.startup_banner.hide_requested.connect(lambda: self._set_startup_banner_visible(False))
        self.startup_banner.focus_requested.connect(self._apply_onboarding_focus)
        self.startup_banner.render(
            self.launch_context,
            dataset=None,
            idx=0,
            tracker=self.event_tracker,
            follow_enabled=self.follow_enabled,
            selected_edge=None,
            selected_node=None,
            prefer_selected_focus=False,
        )

        self._central_host = QtWidgets.QWidget(self)
        self._central_layout = QtWidgets.QVBoxLayout(self._central_host)
        self._central_layout.setContentsMargins(8, 8, 8, 0)
        self._central_layout.setSpacing(8)
        self._central_layout.addWidget(self.startup_banner, 0)
        self._central_layout.addWidget(self.mnemo_view, 1)
        self.setCentralWidget(self._central_host)

        self.overview_panel = OverviewPanel(self)
        self.overview_panel.edge_activated.connect(self._select_edge)
        self.overview_panel.node_activated.connect(self._select_node)
        self.snapshot_panel = PneumoSnapshotPanel(self)
        self.snapshot_panel.edge_selected.connect(self._select_edge)
        self.snapshot_panel.node_selected.connect(self._select_node)
        self.selection_panel = SelectionPanel(self)
        self.selection_panel.edge_selected.connect(self._select_edge)
        self.selection_panel.node_selected.connect(self._select_node)
        self.trends_panel = TrendsPanel(self)
        self.guide_panel = GuidancePanel(self)
        self.fidelity_panel = SchemeFidelityPanel(self)
        self.event_panel = EventMemoryPanel(self)
        self.legend_panel = QtWidgets.QTextBrowser(self)
        self.legend_panel.setHtml(
            "<h3>Легенда и UX-правила</h3>"
            "<p><b>Бирюзовый</b> — поток по направлению ветки.<br/>"
            "<b>Оранжевый</b> — реверс потока.<br/>"
            "<b>Серый</b> — закрытый элемент.<br/>"
            "<b>Inline symbol</b> — canonical-тип арматуры прямо на линии маршрута.</p>"
            "<p><b>Плотность overlays:</b><br/>"
            "<b>Тихо</b> — только основной контекст и минимум карточек.<br/>"
            "<b>Оператор</b> — сбалансированный рабочий режим.<br/>"
            "<b>Полно</b> — максимум labels и inline-символов для разборов схемы.</p>"
            "<p><b>Что где читать:</b><br/>"
            "<b>Центр</b> — топология и причинно-следственная картина.<br/>"
            "<b>Обзор</b> — что сейчас доминирует.<br/>"
            "<b>Приводы</b> — полости, штоки, объёмы, heatmap углов и активная арматура.<br/>"
            "<b>Диагностические сценарии</b> — как интерпретировать текущий кадр.<br/>"
            "<b>Соответствие схеме</b> — покрытие canonical-узлов и ветвей без fallback.<br/>"
            "<b>События</b> — latched-память и недавние переключения.<br/>"
            "<b>Тренды</b> — численная проверка гипотезы.</p>"
            "<p>Такое разделение снижает когнитивное переключение: в центре остаётся только схема, "
            "а чтение режима и чисел уходит в отдельные docks, как в современных инженерных HMI.</p>"
        )
        self.guide_panel.render(None, 0, selected_edge=None, selected_node=None, playing=self.playing, follow_enabled=self.follow_enabled)
        self.fidelity_panel.render(None)
        self._render_event_panel()

        self._overview_dock = self._add_dock("Обзор", self.overview_panel, QtCore.Qt.LeftDockWidgetArea, obj_name="dock_overview")
        self._snapshot_dock = self._add_dock("Приводы", self.snapshot_panel, QtCore.Qt.LeftDockWidgetArea, obj_name="dock_snapshot")
        self._selection_dock = self._add_dock("Выбор", self.selection_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_selection")
        self._guide_dock = self._add_dock("Диагностика", self.guide_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_guide")
        self._fidelity_dock = self._add_dock("Соответствие", self.fidelity_panel, QtCore.Qt.RightDockWidgetArea, obj_name="dock_fidelity")
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

        self.reference_scheme_action = QtGui.QAction("Исходная пневмосхема", self)
        self.reference_scheme_action.setCheckable(True)
        self.reference_scheme_action.setChecked(self.reference_scheme_visible)
        self.reference_scheme_action.toggled.connect(self._toggle_reference_scheme)
        tb.addAction(self.reference_scheme_action)

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

        self.detail_combo = QtWidgets.QComboBox()
        self.detail_combo.setObjectName("mnemo_detail_combo")
        self.detail_combo.addItem("Тихо", "quiet")
        self.detail_combo.addItem("Оператор", "operator")
        self.detail_combo.addItem("Полно", "full")
        detail_idx = max(0, self.detail_combo.findData(self.detail_mode))
        self.detail_combo.setCurrentIndex(detail_idx)
        self.detail_combo.currentIndexChanged.connect(self._detail_mode_changed)
        tb.addWidget(self.detail_combo)

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
        view_menu.addAction(self._snapshot_dock.toggleViewAction())
        view_menu.addAction(self._selection_dock.toggleViewAction())
        view_menu.addAction(self._guide_dock.toggleViewAction())
        view_menu.addAction(self._events_dock.toggleViewAction())
        view_menu.addAction(self._trends_dock.toggleViewAction())
        view_menu.addAction(self._legend_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction(self.reference_scheme_action)
        view_menu.addAction(self.startup_banner_action)
        view_menu.addAction(self.return_focus_action)
        view_menu.addAction(self.full_scheme_action)
        detail_menu = view_menu.addMenu("Плотность overlays")
        for mode in ("quiet", "operator", "full"):
            action = detail_menu.addAction(DETAIL_MODE_LABELS[mode])
            action.triggered.connect(lambda _checked=False, mode=mode: self._set_detail_mode(mode, announce=True))

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
    def _normalize_detail_mode(mode: str) -> str:
        raw_mode = str(mode or "").strip().lower()
        return raw_mode if raw_mode in DETAIL_MODE_LABELS else "operator"

    @staticmethod
    def _parse_startup_view_mode_override(mode: str) -> str:
        raw_mode = str(mode or "").strip().lower()
        if raw_mode in {"focus", "overview"}:
            return raw_mode
        return ""

    def _consume_startup_seek_index(self, dataset: MnemoDataset | None) -> int | None:
        if dataset is None or dataset.time_s.size == 0:
            return None
        if self._startup_time_consumed or self._startup_time_s is None:
            return None
        if self._startup_time_ref_npz is not None:
            try:
                if dataset.npz_path.resolve() != self._startup_time_ref_npz:
                    return None
            except Exception:
                return None

        target_time = float(self._startup_time_s)
        idx = int(np.searchsorted(dataset.time_s, target_time, side="left"))
        if idx >= dataset.time_s.size:
            idx = dataset.time_s.size - 1
        if idx > 0:
            prev_idx = idx - 1
            if abs(float(dataset.time_s[prev_idx]) - target_time) <= abs(float(dataset.time_s[idx]) - target_time):
                idx = prev_idx
        self._startup_time_consumed = True
        applied_time = float(dataset.time_s[idx])
        if self.launch_context.startup_time_label:
            self._last_startup_seek_applied_label = f"{self.launch_context.startup_time_label} -> {applied_time:0.3f} s"
        else:
            self._last_startup_seek_applied_label = f"{applied_time:0.3f} s"
        return int(idx)

    def _consume_startup_focus_selection(
        self,
        dataset: MnemoDataset | None,
    ) -> tuple[str | None, str | None]:
        if dataset is None or dataset.time_s.size == 0:
            return None, None
        if self._startup_selection_consumed:
            return None, None
        if not self._startup_edge and not self._startup_node:
            return None, None
        if self._startup_time_ref_npz is not None:
            try:
                if dataset.npz_path.resolve() != self._startup_time_ref_npz:
                    return None, None
            except Exception:
                return None, None

        startup_edge = self._startup_edge if self._startup_edge in dataset.edge_names else None
        startup_node = self._startup_node if self._startup_node in dataset.node_names else None
        self._startup_selection_consumed = True
        self._startup_selection_active = bool(startup_edge or startup_node)
        if self._startup_selection_active:
            self._last_startup_selection_applied_label = f"{startup_edge or '—'} / {startup_node or '—'}"
        else:
            self._last_startup_selection_applied_label = ""
        return startup_edge, startup_node

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

    def _set_detail_mode(self, mode: str, *, announce: bool) -> str:
        self.detail_mode = self._normalize_detail_mode(mode)
        self.mnemo_view.set_detail_mode(self.detail_mode)
        if hasattr(self, "detail_combo"):
            with QtCore.QSignalBlocker(self.detail_combo):
                idx = max(0, self.detail_combo.findData(self.detail_mode))
                self.detail_combo.setCurrentIndex(idx)
        try:
            self.ui_state.set_value("detail_mode", self.detail_mode)
        except Exception:
            pass
        if announce:
            self._set_status(f"Плотность overlays: {DETAIL_MODE_LABELS[self.detail_mode]}")
        return self.detail_mode

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
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            prefer_selected_focus=self._startup_selection_active,
        )

    def _resolve_startup_event_target(self) -> MnemoTimelineEvent | None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return None
        if self._startup_time_ref_npz is not None:
            try:
                if self.dataset.npz_path.resolve() != self._startup_time_ref_npz:
                    return None
            except Exception:
                return None
        if not (
            self._startup_event_title
            or self._startup_time_s is not None
            or self._startup_edge
            or self._startup_node
        ):
            return None

        best_event: MnemoTimelineEvent | None = None
        best_score = float("-inf")
        for event in self.event_tracker.events:
            score = 0.0
            if self._startup_event_title:
                if event.title == self._startup_event_title:
                    score += 240.0
                elif self._startup_event_title in event.summary:
                    score += 80.0
                elif event.title and event.title in self._startup_event_title:
                    score += 40.0
            if self._startup_edge and event.edge_name == self._startup_edge:
                score += 60.0
            if self._startup_node and event.node_name == self._startup_node:
                score += 60.0
            if self._startup_time_s is not None:
                delta = abs(float(event.time_s) - float(self._startup_time_s))
                score += max(0.0, 36.0 - delta * 120.0)
            if event.severity in {"warn", "attention", "focus"}:
                score += 8.0
            if event.kind == "session":
                score -= 18.0
            if score > best_score:
                best_score = score
                best_event = event
        return best_event if best_event is not None and best_score > 0.0 else None

    def _render_event_panel(self) -> None:
        self.event_panel.render(
            self.dataset,
            self.current_idx,
            tracker=self.event_tracker,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
            startup_event=self._resolve_startup_event_target(),
            startup_time_label=self._startup_time_label,
        )

    def _detail_mode_changed(self, index: int) -> None:
        mode = str(self.detail_combo.itemData(index) or "operator")
        self._set_detail_mode(mode, announce=True)

    def _toggle_reference_scheme(self, checked: bool) -> None:
        self.reference_scheme_visible = bool(checked)
        try:
            self.ui_state.set_value("reference_scheme_visible", self.reference_scheme_visible)
        except Exception:
            pass
        self.mnemo_view.set_reference_scheme_visible(self.reference_scheme_visible)
        self._set_status("Исходная пневмосхема показана." if self.reference_scheme_visible else "Исходная пневмосхема скрыта.")

    def _current_focus_region_payload(self, *, source: str, auto_focus: bool) -> dict[str, Any] | None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return None
        return build_onboarding_focus_region_payload(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            prefer_selected=self._startup_selection_active,
            source=source,
            auto_focus=auto_focus,
        )

    def _apply_current_view_mode(self, *, source: str, auto_focus: bool) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        focus_region = self._current_focus_region_payload(source=source, auto_focus=auto_focus)
        if self.view_mode == "overview":
            self.mnemo_view.show_overview(
                {
                    "title": "Полная схема",
                    "summary": "Сравните рекомендуемый сценарий с полной топологией, не теряя быстрый путь назад к фокусу.",
                    "focus_region": focus_region,
                }
            )
            return
        self.mnemo_view.set_focus_region(focus_region)

    def _sync_selection_views(self, *, clear_focus_region: bool = False) -> None:
        if self.dataset is None:
            return
        if clear_focus_region:
            self.mnemo_view.set_focus_region(None)
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
        self.mnemo_view.set_selection(edge=self.selected_edge, node=self.selected_node)
        self._push_diagnostics()
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
            prefer_selected=self._startup_selection_active,
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
            self.ui_state.set_value("detail_mode", str(self.detail_mode))
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
        self.snapshot_panel.update_frame(self.dataset, self.current_idx)
        self.guide_panel.render(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self._render_event_panel()
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
        self.snapshot_panel.update_frame(self.dataset, self.current_idx)
        self.guide_panel.render(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
            playing=self.playing,
            follow_enabled=self.follow_enabled,
        )
        self._render_event_panel()

    def _jump_to_start(self) -> None:
        self.current_idx = 0
        self._refresh_frame()

    def _jump_to_focus_step(self, step_label: str, target_idx: int) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        clamped_idx = int(max(0, min(int(target_idx), self.dataset.time_s.size - 1)))
        if self.playing:
            self.play_action.setChecked(False)
        self.current_idx = clamped_idx
        self._refresh_frame(push_to_view=True)
        target_time_s = float(self.dataset.time_s[clamped_idx])
        self._set_status(f"Jump к шагу {str(step_label or '—')}: t = {target_time_s:0.3f} s")

    def _acknowledge_events(self) -> None:
        if self.dataset is None:
            return
        acked = self.event_tracker.acknowledge_active_latches(dataset=self.dataset, idx=self.current_idx)
        if not acked:
            self._set_status("ACK: активных latched-событий нет.")
            return
        self._render_event_panel()
        self._persist_event_log(silent=True)
        self._set_status(f"ACK: подтверждено {len(acked)} latched-событий.")

    def _reset_events_memory(self) -> None:
        if self.dataset is None:
            return
        self.event_tracker.reset_memory(self.dataset, idx=self.current_idx)
        self._render_event_panel()
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
        self._refresh_frame(push_to_view=True)

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
        self._refresh_frame(push_to_view=True)

    def load_dataset(self, npz_path: Path, *, preserve_selection: bool) -> None:
        try:
            old_edge = self.selected_edge if preserve_selection else None
            old_node = self.selected_node if preserve_selection else None
            self._last_startup_seek_applied_label = ""
            self._last_startup_selection_applied_label = ""
            if not preserve_selection:
                self._startup_selection_active = False
            self.dataset = prepare_dataset(Path(npz_path))
            startup_seek_idx = self._consume_startup_seek_index(self.dataset)
            startup_focus_edge, startup_focus_node = self._consume_startup_focus_selection(self.dataset)
            if startup_seek_idx is not None:
                self.current_idx = startup_seek_idx
            else:
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
            if startup_focus_edge in self.dataset.edge_names:
                old_edge = startup_focus_edge
            if startup_focus_node in self.dataset.node_names:
                old_node = startup_focus_node

            self.selected_edge = old_edge
            self.selected_node = old_node
            self.event_tracker.bind_dataset(self.dataset, idx=self.current_idx)
            self.selection_panel.set_selection(edge_name=self.selected_edge, node_name=self.selected_node)
            self.trends_panel.set_series(self.dataset, edge_name=self.selected_edge, node_name=self.selected_node)
            self.fidelity_panel.render(self.dataset)
            self.mnemo_view.render_dataset(self.dataset, selected_edge=self.selected_edge, selected_node=self.selected_node)
            self._apply_current_view_mode(source="dataset_load", auto_focus=not preserve_selection)
            self._refresh_frame(push_to_view=True)
            self._persist_event_log(silent=True)
            self._set_dataset_title()
            self._render_startup_banner()
            status = f"Загружено: {self.dataset.npz_path.name}"
            if self._last_startup_seek_applied_label:
                status += f" • старт у {self._last_startup_seek_applied_label}"
            if self._last_startup_selection_applied_label:
                status += f" • фокус {self._last_startup_selection_applied_label}"
            self._set_status(status)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Desktop Mnemo", _friendly_error_text(exc))
            self._set_status(f"Ошибка загрузки: {exc}")

    def _refresh_frame(self, *, push_to_view: bool = False) -> None:
        if self.dataset is None or self.dataset.time_s.size == 0:
            return
        self.current_idx = int(max(0, min(self.current_idx, self.dataset.time_s.size - 1)))
        new_events = self.event_tracker.observe_frame(self.dataset, idx=self.current_idx)
        with QtCore.QSignalBlocker(self.scrubber):
            self.scrubber.setValue(self.current_idx)
        self.time_label.setText(f"t = {float(self.dataset.time_s[self.current_idx]):6.3f} s")
        self.overview_panel.update_frame(self.dataset, self.current_idx, playing=self.playing, follow_enabled=self.follow_enabled)
        self.snapshot_panel.update_frame(self.dataset, self.current_idx)
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
        self._render_event_panel()
        if self.startup_banner.isVisible() and not self.playing:
            self._render_startup_banner()
        if new_events:
            self._persist_event_log(silent=True)
        if push_to_view:
            self._push_diagnostics()
            self._push_alerts()
            self._push_playhead()

    def _push_playhead(self) -> None:
        if self.dataset is None:
            return
        self.mnemo_view.set_playhead(self.current_idx, self.playing, self.dataset.dataset_id)

    def _push_alerts(self) -> None:
        alerts = _build_frame_alert_payload(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
        )
        self.mnemo_view.set_alerts(alerts)

    def _push_diagnostics(self) -> None:
        diagnostics = _build_mnemo_diagnostics_payload(
            self.dataset,
            self.current_idx,
            selected_edge=self.selected_edge,
            selected_node=self.selected_node,
        )
        self.mnemo_view.set_diagnostics(diagnostics)

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
        self._startup_selection_active = False
        self.selected_edge = edge_name
        self._sync_selection_views(clear_focus_region=True)

    def _select_node(self, node_name: str) -> None:
        if not node_name or self.dataset is None or node_name not in self.dataset.node_names:
            return
        self._startup_selection_active = False
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
    startup_time_s: float | None = None,
    startup_time_label: str = "",
    startup_edge: str = "",
    startup_node: str = "",
    startup_event_title: str = "",
    startup_time_ref_npz: str = "",
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
        startup_time_s=startup_time_s,
        startup_time_label=startup_time_label,
        startup_edge=startup_edge,
        startup_node=startup_node,
        startup_event_title=startup_event_title,
        startup_time_ref_npz=startup_time_ref_npz,
        startup_checklist=startup_checklist,
    )
    window.show()
    if created:
        return int(app.exec())
    return 0
