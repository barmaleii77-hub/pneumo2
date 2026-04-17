from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest


def _write_runtime_mnemo_npz(tmp_path: Path) -> Path:
    t = np.array([0.0, 0.5, 1.0], dtype=float)
    npz_path = tmp_path / "desktop_mnemo_runtime_bundle.npz"
    meta = {
        "P_ATM": 101325.0,
        "geometry": {
            "wheelbase_m": 2.8,
            "track_m": 1.6,
            "wheel_radius_m": 0.32,
            "wheel_width_m": 0.24,
            "frame_length_m": 3.2,
            "frame_width_m": 1.7,
            "frame_height_m": 0.25,
            "cyl1_bore_diameter_m": 0.032,
            "cyl1_rod_diameter_m": 0.016,
            "cyl2_bore_diameter_m": 0.050,
            "cyl2_rod_diameter_m": 0.014,
            "cyl1_stroke_front_m": 0.250,
            "cyl1_stroke_rear_m": 0.250,
            "cyl2_stroke_front_m": 0.250,
            "cyl2_stroke_rear_m": 0.250,
            "cyl1_dead_cap_length_m": 0.010,
            "cyl1_dead_rod_length_m": 0.012,
            "cyl2_dead_cap_length_m": 0.008,
            "cyl2_dead_rod_length_m": 0.009,
        },
    }
    edge_cols = np.array(
        ["время_с", "регулятор_до_себя_Pmid_сброс", "обратный_клапан_Pmid_к_выхлопу", "дроссель_выхлоп_Pmid"],
        dtype=object,
    )
    main_cols = [
        "время_с",
        "положение_штока_ЛП_м",
        "скорость_штока_ЛП_м_с",
        "перемещение_рамы_z_м",
        "скорость_vx_м_с",
        "yaw_рад",
        "дорога_ЛП_м",
        "перемещение_колеса_ЛП_м",
        "рама_угол_ЛП_z_м",
        "дорога_ПП_м",
        "перемещение_колеса_ПП_м",
        "рама_угол_ПП_z_м",
        "дорога_ЛЗ_м",
        "перемещение_колеса_ЛЗ_м",
        "рама_угол_ЛЗ_z_м",
        "дорога_ПЗ_м",
        "перемещение_колеса_ПЗ_м",
        "рама_угол_ПЗ_z_м",
    ]
    main_series = [
        t,
        np.array([0.05, 0.125, 0.20], dtype=float),
        np.array([0.12, 0.18, 0.10], dtype=float),
        np.array([0.01, 0.012, 0.011], dtype=float),
        np.array([1.2, 1.2, 1.2], dtype=float),
        np.array([0.0, 0.01, 0.02], dtype=float),
    ]
    main_series.extend(np.zeros_like(t) for _ in range(len(main_cols) - len(main_series)))
    np.savez(
        npz_path,
        main_cols=np.array(main_cols, dtype=object),
        main_values=np.column_stack(main_series).astype(float),
        p_cols=np.array(
            ["время_с", "Ресивер1", "Ресивер3", "узел_после_рег_Pmid", "узел_после_ОК_Pmid", "Ц1_ЛП_БП", "Ц1_ЛП_ШП"],
            dtype=object,
        ),
        p_values=np.column_stack(
            [
                t,
                np.array([305000.0, 308000.0, 312000.0], dtype=float),
                np.array([498000.0, 501000.0, 505000.0], dtype=float),
                np.array([255000.0, 260000.0, 270000.0], dtype=float),
                np.array([240000.0, 242000.0, 245000.0], dtype=float),
                np.array([480000.0, 501325.0, 520000.0], dtype=float),
                np.array([290000.0, 301325.0, 315000.0], dtype=float),
            ]
        ).astype(float),
        q_cols=edge_cols,
        q_values=np.column_stack(
            [
                t,
                np.array([0.0010, 0.0012, 0.0014], dtype=float),
                np.array([0.0007, 0.0004, 0.0001], dtype=float),
                np.array([0.0002, 0.0005, 0.0008], dtype=float),
            ]
        ).astype(float),
        open_cols=edge_cols,
        open_values=np.column_stack(
            [
                t,
                np.array([1, 1, 0], dtype=float),
                np.array([1, 0, 0], dtype=float),
                np.array([0, 1, 1], dtype=float),
            ]
        ).astype(float),
        meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=object),
    )
    return npz_path


def _pixmap_color_sample_count(pixmap: object) -> int:
    image = pixmap.toImage()
    width = max(1, int(image.width()))
    height = max(1, int(image.height()))
    colors: set[int] = set()
    for x in np.linspace(0, width - 1, num=min(8, width), dtype=int):
        for y in np.linspace(0, height - 1, num=min(8, height), dtype=int):
            colors.add(int(image.pixelColor(int(x), int(y)).rgba()))
    return len(colors)


def test_desktop_mnemo_window_has_persistent_docks_and_playhead_bridge() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_mnemo" / "app.py").read_text(encoding="utf-8")

    assert 'obj_name="dock_overview"' in src
    assert 'obj_name="dock_selection"' in src
    assert 'obj_name="dock_guide"' in src
    assert 'obj_name="dock_fidelity"' in src
    assert 'obj_name="dock_events"' in src
    assert 'obj_name="dock_trends"' in src
    assert 'obj_name="dock_legend"' in src
    assert 'prefix="desktop_mnemo"' in src
    assert "toggleViewAction()" in src
    assert "GuidancePanel" in src
    assert "SchemeFidelityPanel" in src
    assert "EventMemoryPanel" in src
    assert "StartupBannerPanel" in src
    assert "build_launch_onboarding_context" in src
    assert "build_onboarding_focus_target" in src
    assert "build_onboarding_focus_region_payload" in src
    assert "prefer_selected: bool = False" in src
    assert "startup_time_s: float | None = None" in src
    assert "startup_time_label: str = \"\"" in src
    assert 'self.startup_banner_action = QtGui.QAction("Стартовая панель", self)' in src
    assert "focus_requested = QtCore.Signal()" in src
    assert 'self.startup_banner.focus_requested.connect(self._apply_onboarding_focus)' in src
    assert "Скрыть onboarding" in src
    assert "Навести фокус на схему" in src
    assert "Почему окно открылось так" in src
    assert "Первый чек-лист оператора" in src
    assert "Подсветка onboarding" in src
    assert "Что сделает кнопка" in src
    assert "MnemoEventTracker" in src
    assert "Диагностические сценарии" in src
    assert "Латчи и события" in src
    assert "Подтвердить события" in src
    assert "Сбросить события" in src
    assert "Экспорт событий" in src
    assert "_write_event_log_sidecar" in src
    assert "desktop_mnemo_events.json" in src
    assert "class MnemoNativeCanvas" in src
    assert "class MnemoNativeView(QtWidgets.QWidget):" in src
    assert "focus_step_jump_requested = QtCore.Signal(str, int)" in src
    assert 'self.mnemo_view = MnemoNativeView(self)' in src
    assert 'self.native_view = self.mnemo_view' in src
    assert 'self.native_canvas = MnemoNativeCanvas(self)' in src
    assert "self.native_canvas.focus_step_jump_requested.connect(self.focus_step_jump_requested.emit)" in src
    assert 'self.setObjectName("mnemo_native_canvas")' in src
    assert 'self.mode_badge = QtWidgets.QLabel("Схема", header)' in src
    assert "self.native_canvas.set_alerts(alerts)" in src
    assert "self.native_canvas.set_diagnostics(diagnostics)" in src
    assert "self.native_canvas.set_focus_region(focus_region)" in src
    assert "self.native_canvas.show_overview(overview_meta)" in src
    assert "self.native_canvas.set_display_modes(" in src
    assert 'self.fidelity_panel.render(self.dataset)' in src
    assert 'self._central_layout.addWidget(self.mnemo_view, 1)' in src
    assert 'self._set_startup_banner_visible(False)' in src
    assert "self.mnemo_view.focus_step_jump_requested.connect(self._jump_to_focus_step)" in src
    assert "Desktop Mnemo switched to native Qt canvas." in src
    assert "Колесо — масштаб, перетаскивание — панорама, щелчок — выбор элемента" in src
    assert "QtSvg.QSvgRenderer" in src
    assert "CANONICAL_PNEUMO_SCHEME_SVG_PATHS" in src
    assert "SOURCE_OF_TRUTH_PNEUMO_IMAGE_PATH" in src
    assert "REFERENCE_COMPONENT_NODE_ANCHORS_SVG" in src
    assert "REFERENCE_INDICATOR_NODE_ANCHORS_SVG" in src
    assert "REFERENCE_CHAMBER_NODE_ANCHORS_SVG" in src
    assert "def _reference_scheme_scene_rect_tuple() -> tuple[float, float, float, float]:" in src
    assert "def _reference_svg_point_to_scene(x: float, y: float) -> tuple[float, float]:" in src
    assert "def _reference_node_anchor_positions(node_names: list[str]) -> dict[str, tuple[float, float]]:" in src
    assert "def _reference_diagonal_geometry_positions(node_names: list[str]) -> dict[str, tuple[float, float]]:" in src
    assert "def _node_pressure_for_index(dataset: MnemoDataset | None, node_name: str, idx: int) -> float | None:" in src
    assert "def _node_pressure_series_bar_g(dataset: MnemoDataset | None, node_name: str) -> np.ndarray | None:" in src
    assert "def _route_pressure_strip_trend_meta(" in src
    assert "def _build_route_pressure_strip_payloads(" in src
    assert "def _route_pressure_strip_terminal_meta(" in src
    assert "def _build_active_diagonal_focus_meta(" in src
    assert "def _build_diagonal_pressure_strip_payloads(" in src
    assert "reference_svg_inline: str" in src
    assert "reference_scheme_source: str" in src
    assert "def _load_canonical_pneumo_scheme_svg() -> tuple[str, str]:" in src
    assert 'self.reference_scheme_action = QtGui.QAction("Исходная пневмосхема", self)' in src
    assert "self.reference_scheme_action.toggled.connect(self._toggle_reference_scheme)" in src
    assert "def _toggle_reference_scheme(self, checked: bool) -> None:" in src
    assert "def set_reference_scheme_visible(self, visible: bool) -> bool:" in src
    assert "def _apply_default_workplace_layout(self) -> None:" in src
    assert "self.tabifyDockWidget(self._selection_dock, self._guide_dock)" in src
    assert "self.resizeDocks([self._overview_dock, self._selection_dock], [320, 360], QtCore.Qt.Horizontal)" in src
    assert "self._reference_svg_renderer: Any = None" in src
    assert "self._show_reference_scheme = True" in src
    assert 'WINDOW_LAYOUT_CONTRACT_SCHEMA_VERSION = "desktop_mnemo_window_layout_contract_v1"' in src
    assert 'self.setObjectName("desktop_mnemo_main_window")' in src
    assert "def _build_window_layout_contract(self) -> dict[str, Any]:" in src
    assert "def _layout_contract_docks(self) -> list[QtWidgets.QDockWidget]:" in src
    assert '"objectName": dock.objectName()' in src
    assert '"visible": bool(dock.isVisible())' in src
    assert '"floating": bool(dock.isFloating())' in src
    assert '"dock_area": self._dock_area_contract_name(area)' in src
    assert '"window/geometry"' in src
    assert '"window/state"' in src
    assert '"saved_window_geometry_available"' in src
    assert '"saved_window_state_available"' in src
    assert '"current_theme": self.theme' in src
    assert '"dpi_ratio": self._dpi_ratio_for_layout_contract()' in src
    assert '"custom_titlebar_assumption": False' in src
    assert '"window_layout_contract": layout_contract' in src
    assert "window_layout_contract=self._build_window_layout_contract()" in src
    assert 'self.truth_text = QtWidgets.QLabel("Mnemo: unavailable pressure/state")' in src
    assert "def _set_truth_status(self, availability: dict[str, Any] | None) -> None:" in src
    assert 'return "Mnemo: confirmed"' in src
    assert 'return "Mnemo: warnings"' in src
    assert 'return "Mnemo: unavailable pressure/state"' in src
    assert 'self._hover_focus_edge = ""' in src
    assert "self._hover_focus_restore_rect: QtCore.QRectF | None = None" in src
    assert "def _load_reference_svg_renderer(self, svg_inline: str) -> None:" in src
    assert "def _reference_scheme_rect(self) -> QtCore.QRectF:" in src
    assert "Исходная пневмосхема • pneumo_scheme.svg" in src
    assert '"reference_scheme_mode"] = "native_underlay"' in src
    assert '"reference_indicator_nodes_snapped"] = len(reference_indicator_names)' in src
    assert '"reference_component_nodes_snapped"] = len(reference_component_names)' in src
    assert '"reference_chamber_nodes_snapped"] = len(reference_chamber_names)' in src
    assert '"reference_diagonal_nodes_geometry_locked"] = len(reference_diagonal_names)' in src
    assert "critical indicator anchors = " in src
    assert "chamber indicator anchors = " in src
    assert "diagonal geometry from source scheme = " in src
    assert "node_series = _build_node_series(bundle, node_names, p_atm)" in src
    assert '"diagonal_focus": diagonal_focus' in src
    assert '"route_pressure_strips": route_pressure_strips' in src
    assert '"diagonal_pressure_strips": diagonal_pressure_strips' in src
    assert "def set_diagnostics(self, diagnostics: dict[str, Any]) -> None:" in src
    assert "def _diagnostic_availability(self) -> dict[str, Any]:" in src
    assert "def _surface_available(self, surface: str) -> bool:" in src
    assert "def _draw_truth_badge(self, painter: QtGui.QPainter) -> None:" in src
    assert "_truth_status_text(availability)" in src
    assert 'badge_text = _truth_status_text(availability)' in src
    assert "pressure_available = self._surface_available(\"pressure\")" in src
    assert '"pressure_available": bool(pressure_available and pressure_now is not None)' in src
    assert "_build_mnemo_diagnostics_payload" in src
    assert "self._push_diagnostics()" in src
    assert "def set_focus_region(self, focus_region: dict[str, Any] | None) -> None:" in src
    assert "def show_overview(self, meta: dict[str, Any] | None = None) -> None:" in src
    assert "def _route_pressure_strip_payload_for_edge(self, edge_name: str) -> dict[str, Any] | None:" in src
    assert "def _active_route_pressure_terminal_meta(self) -> dict[str, Any] | None:" in src
    assert "def _route_pressure_strip_focus_rect(self, payload: dict[str, Any] | None) -> QtCore.QRectF | None:" in src
    assert "def _camera_contains_rect(self, rect: QtCore.QRectF, *, margin: float = 48.0) -> bool:" in src
    assert "def _update_hover_route_pressure_focus(self) -> None:" in src
    assert "def _dismiss_hover_route_pressure_focus(self, *, restore: bool) -> None:" in src
    assert "startup_view_mode: str," in src
    assert "startup_time_s: float | None," in src
    assert "startup_time_label: str," in src
    assert "startup_edge: str," in src
    assert "startup_node: str," in src
    assert "startup_event_title: str," in src
    assert "startup_time_ref_npz: str," in src
    assert 'self._persisted_view_mode = self._normalize_view_mode(self.ui_state.get_str("view_mode", "focus"))' in src
    assert 'self.detail_mode = self._normalize_detail_mode(self.ui_state.get_str("detail_mode", "operator"))' in src
    assert "FLOW_DISPLAY_MODE_LABELS" in src
    assert "PRESSURE_DISPLAY_MODE_LABELS" in src
    assert 'self.flow_display_mode = _normalize_flow_display_mode(self.ui_state.get_str("flow_display_mode", "nlpm"))' in src
    assert 'self.pressure_display_mode = _normalize_pressure_display_mode(self.ui_state.get_str("pressure_display_mode", "bar_g"))' in src
    assert "DETAIL_MODE_LABELS" in src
    assert 'self.mnemo_view.set_detail_mode(self.detail_mode)' in src
    assert "self.trends_panel.set_display_modes(" in src
    assert "self._startup_view_mode_override = self._parse_startup_view_mode_override(startup_view_mode)" in src
    assert "self._view_mode_override_active = bool(self._startup_view_mode_override)" in src
    assert "self._startup_time_s = float(startup_time_s) if startup_time_s is not None else None" in src
    assert "self._startup_time_label = str(startup_time_label or \"\").strip()" in src
    assert "self._startup_edge = str(startup_edge or \"\").strip()" in src
    assert "self._startup_node = str(startup_node or \"\").strip()" in src
    assert "self._startup_event_title = str(startup_event_title or \"\").strip()" in src
    assert "self._startup_time_consumed = False" in src
    assert "self._startup_selection_consumed = False" in src
    assert "self._startup_selection_active = False" in src
    assert "def _consume_startup_seek_index(self, dataset: MnemoDataset | None) -> int | None:" in src
    assert "def _consume_startup_focus_selection(" in src
    assert "def _resolve_startup_event_target(self) -> MnemoTimelineEvent | None:" in src
    assert "def _render_event_panel(self) -> None:" in src
    assert "jump {context.startup_time_s:0.3f} s" in src
    assert "Стартовый jump:" in src
    assert "Стартовая запись event-memory" in src
    assert "self._last_startup_anchor_signature = \"\"" in src
    assert "self.scrollToAnchor(anchor)" in src
    assert "def _parse_startup_view_mode_override(mode: str) -> str:" in src
    assert "def _normalize_detail_mode(mode: str) -> str:" in src
    assert 'def _set_view_mode(self, mode: str, *, persist: bool) -> str:' in src
    assert 'def _set_detail_mode(self, mode: str, *, announce: bool) -> str:' in src
    assert "def _detail_mode_changed(self, index: int) -> None:" in src
    assert "self._startup_view_mode_override = \"\"" in src
    assert "self._view_mode_override_active = False" in src
    assert 'self.ui_state.set_value("view_mode", str(self.view_mode))' in src
    assert 'self.ui_state.set_value("detail_mode", str(self.detail_mode))' in src
    assert 'self.ui_state.set_value("view_mode", self.view_mode)' in src
    assert "if not self._view_mode_override_active:" in src
    assert "startup_seek_idx = self._consume_startup_seek_index(self.dataset)" in src
    assert "startup_focus_edge, startup_focus_node = self._consume_startup_focus_selection(self.dataset)" in src
    assert 'status += f" • старт у {self._last_startup_seek_applied_label}"' in src
    assert 'status += f" • фокус {self._last_startup_selection_applied_label}"' in src
    assert 'self._apply_current_view_mode(source="dataset_load", auto_focus=not preserve_selection)' in src
    assert '"focus_region": focus_region' in src
    assert "clear_focus_region: bool = False" in src
    assert 'self.return_focus_action = QtGui.QAction("Вернуться к фокусу", self)' in src
    assert 'self.full_scheme_action = QtGui.QAction("Вся схема", self)' in src
    assert "def _show_full_scheme_overview(self) -> None:" in src
    assert "def _jump_to_focus_step(self, step_label: str, target_idx: int) -> None:" in src
    assert "Jump к шагу" in src
    assert "self._camera_target_rect: QtCore.QRectF | None = None" in src
    assert "def _set_camera_target(self, target_rect: QtCore.QRectF, *, immediate: bool = False) -> None:" in src
    assert "def _sync_anim_timer(self) -> None:" in src
    assert "def _advance_animations(self) -> None:" in src
    assert "def _interpolate_rect(current: QtCore.QRectF, target: QtCore.QRectF, factor: float) -> QtCore.QRectF:" in src
    assert "def _rect_close_enough(current: QtCore.QRectF, target: QtCore.QRectF) -> bool:" in src
    assert "def _inline_route_symbol_payloads(self, *, max_abs_flow: float) -> dict[str, dict[str, Any]]:" in src
    assert "def _draw_inline_route_symbol(self, painter: QtGui.QPainter, *, edge_name: str, payload: dict[str, Any]) -> None:" in src
    assert "def _edge_direction_meta(edge_def: dict[str, Any], q_now: float | None) -> dict[str, Any]:" in src
    assert "Паспортное направление:" in src
    assert "Поток в кадре:" in src
    assert "Статус направления:" in src
    assert "Элемент vs поток:" in src
    assert "Комментарий элемента:" in src
    assert "Источник / приёмник:" in src
    assert "Концы ветви:" in src
    assert "ΔP ветви (n1-n2):" in src
    assert "Ведущее давление:" in src
    assert "Q vs ΔP:" in src
    assert "Оценка ΔP:" in src
    assert "Инженерный verdict:" in src
    assert "Комментарий verdict:" in src
    assert "Согласованность сигналов:" in src
    assert "Комментарий согласованности:" in src
    assert "Временной ход:" in src
    assert "Комментарий хода:" in src
    assert "Окно анализа:" in src
    assert "def _path_angle_deg(path: QtGui.QPainterPath, percent: float) -> float:" in src
    assert "_build_frame_alert_payload" in src
    assert "self._draw_alert_markers(painter)" in src
    assert 'self.detail_combo = QtWidgets.QComboBox()' in src
    assert 'self.flow_unit_combo = QtWidgets.QComboBox()' in src
    assert 'self.flow_unit_combo.setObjectName("mnemo_flow_unit_combo")' in src
    assert 'self.flow_unit_combo.addItem("Q: Нл/мин", "nlpm")' in src
    assert 'self.flow_unit_combo.addItem("Q: кг/с", "kg_s")' in src
    assert 'self.pressure_unit_combo = QtWidgets.QComboBox()' in src
    assert 'self.pressure_unit_combo.setObjectName("mnemo_pressure_unit_combo")' in src
    assert 'self.pressure_unit_combo.addItem("P: бар(g)", "bar_g")' in src
    assert 'self.pressure_unit_combo.addItem("P: Па(abs)", "pa_abs")' in src
    assert 'self.detail_combo.addItem("Тихо", "quiet")' in src
    assert 'self.detail_combo.addItem("Оператор", "operator")' in src
    assert 'self.detail_combo.addItem("Полно", "full")' in src
    assert 'detail_menu = view_menu.addMenu("Насыщенность наложений")' in src
    assert "def _set_flow_display_mode(self, mode: str, *, announce: bool) -> str:" in src
    assert "def _set_pressure_display_mode(self, mode: str, *, announce: bool) -> str:" in src
    assert "def _flow_unit_changed(self, index: int) -> None:" in src
    assert "def _pressure_unit_changed(self, index: int) -> None:" in src
    assert 'self.ui_state.set_value("flow_display_mode", self.flow_display_mode)' in src
    assert 'self.ui_state.set_value("pressure_display_mode", self.pressure_display_mode)' in src
    assert 'PLAYHEAD_STORAGE_KEY = "pneumo_desktop_mnemo_playhead"' in src
    assert "BOOTSTRAP_JS" not in src
    assert "MnemoWebView" not in src
    assert "QtWebEngine" not in src
    assert "QtWebEngineWidgets" not in src


def test_desktop_mnemo_native_canvas_has_overlay_contract() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_mnemo" / "app.py").read_text(encoding="utf-8")

    assert "def _build_selected_edge_focus_meta(" in src
    assert "def _draw_alert_markers(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_diagonal_focus_pressure_strips(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _active_route_pressure_strip_payload(self) -> dict[str, Any] | None:" in src
    assert "def _draw_route_pressure_strip_terminal_focus(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_diagnostics_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_focus_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_selected_edge_focus_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_selected_edge_focus_terminals(self, painter: QtGui.QPainter, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_selected_edge_phase_ribbon(" in src
    assert "def _toggle_focus_step(self, step_label: str) -> None:" in src
    assert '"focus_step"' in src
    assert "def _edge_pressure_drive_meta(" in src
    assert "def _edge_element_flow_contract_meta(" in src
    assert "def _edge_operability_meta(" in src
    assert "def _edge_consistency_meta(" in src
    assert "def _edge_temporal_meta(" in src
    assert "def _edge_recent_history_meta(" in src
    assert "def _edge_recent_history_summary(" in src
    assert "def _edge_recent_pressure_meta(" in src
    assert "def _edge_recent_pressure_summary(" in src
    assert "def _edge_recent_causality_meta(" in src
    assert "def _edge_recent_causality_summary(" in src
    assert "def _edge_recent_latency_meta(" in src
    assert "def _edge_recent_latency_summary(" in src
    assert "def _edge_phase_ribbon_meta(" in src
    assert "def _edge_operator_hint_meta(" in src
    assert "def _edge_operator_checklist_meta(" in src
    assert "def _draw_selected_edge_terminal_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_terminal_role_badges(" in src
    assert "def _draw_selected_edge_direction_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_edge_recent_history_strip(" in src
    assert "def _draw_edge_recent_pressure_strip(" in src
    assert "def _draw_edge_direction_marker(" in src
    assert "ЭЛ-вход" in src
    assert "ЭЛ-выход" in src
    assert "P+" in src
    assert "P-" in src
    assert "P≈" in src
    assert "Q-ист" in src
    assert "Q-прием" in src
    assert "Q-пауза" in src
    assert "ΔP ok" in src
    assert "ΔP rev" in src
    assert "ΔP≈" in src
    assert "EL ok" in src
    assert "EL rev" in src
    assert "EL bi" in src
    assert "EL dir" in src
    assert "EL gen" in src
    assert "OP leak" in src
    assert "OP ok" in src
    assert "OP hold" in src
    assert "OP shut" in src
    assert "OP ctx" in src
    assert "CS q" in src
    assert "CS ok" in src
    assert "CS hold" in src
    assert "CS el" in src
    assert "CS dp" in src
    assert "CS ctx" in src
    assert "TM ramp" in src
    assert "TM steady" in src
    assert "TM osc" in src
    assert "TM flip" in src
    assert "TM idle" in src
    assert "CX ok" in src
    assert "CX leak" in src
    assert "CX wait" in src
    assert "LG ok" in src
    assert "LG wait" in src
    assert "LG soft" in src
    assert "LG late" in src
    assert "Последнее окно:" in src
    assert "ΔP-контур:" in src
    assert '"regulator": "регулятора"' in src
    assert '"supply": "питания"' in src
    assert "Причинная связка:" in src
    assert "Комментарий связки:" in src
    assert "Лаг реакции:" in src
    assert "Комментарий лага:" in src
    assert "Фаза окна:" in src
    assert "Фазовая лента:" in src
    assert "Интервалы фаз:" in src
    assert "Узкое место фазы:" in src
    assert "Тип узкого места:" in src
    assert "Комментарий узкого места:" in src
    assert "Фокус узкого места:" in src
    assert "Подсказка фокуса:" in src
    assert "Операторский приоритет:" in src
    assert "Комментарий приоритета:" in src
    assert "Чек-лист разбора:" in src
    assert "ΔP-контур • " in src
    assert "ΔP диагонали" in src
    assert "ΔP↑" in src
    assert "ΔP↓" in src
    assert "ΔP=" in src
    assert "ΔP без истории" in src
    assert "def _edge_flow_series_scaled(dataset: MnemoDataset | None, edge_name: str) -> np.ndarray | None:" in src
    assert "def _route_pressure_strip_flow_meta(" in src
    assert "def _route_pressure_strip_history_meta(" in src
    assert "def _route_pressure_strip_cause_effect_meta(" in src
    assert "def _route_pressure_strip_intermediate_nodes_meta(" in src
    assert "def _edge_actuation_active(" in src
    assert "Регуляторный узел" in src
    assert "Камерный узел" in src
    assert "Почти как ведущий конец" in src
    assert "Ниже ведущего на " in src
    assert "Выше ведущего на " in src
    assert "Идёт к выравниванию" in src
    assert "Сближается с ведущим" in src
    assert "Уходит от ведущего" in src
    assert "Держит разброс к ведущему" in src
    assert "Q доходит до узла" in src
    assert "Q ещё не дошёл до узла" in src
    assert "Q тянется через узел" in src
    assert "Q гаснет у узла" in src
    assert "Q↑" in src
    assert "Q↓" in src
    assert "Q=" in src
    assert "Q без истории" in src
    assert "Q-лента" in src


def test_desktop_mnemo_ui_surfaces_dataset_truth_markers() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_mnemo" / "app.py").read_text(encoding="utf-8")

    assert "def _truth_state_label(state: str) -> str:" in src
    assert "def _truth_summary_html(availability: dict[str, Any] | None) -> str:" in src
    assert "def _source_markers_table_html(availability: dict[str, Any] | None" in src
    assert "overall_truth_state" in src
    assert "unavailable_surfaces" in src
    assert "source_markers" in src
    assert "missing/reason" in src
    assert "class SchemeFidelityPanel" in src
    assert "_source_markers_table_html(availability)" in src
    assert "class GuidancePanel" in src
    assert "_truth_summary_html(availability)" in src
    assert "Honest state:" in src
    assert "class PneumoSnapshotPanel" in src
    assert "P only (geometry unavailable)" in src
    assert "Cylinder snapshot unavailable: отображается pressure-only без тихого volume fallback." in src
    assert "Cylinder snapshot approximate: неполная геометрия помечена явно." in src
    assert "class MnemoNativeCanvas" in src
    assert "def _draw_truth_badge(self, painter: QtGui.QPainter) -> None:" in src
    assert "self._draw_truth_badge(painter)" in src
    assert "ΔP→Q ok" in src
    assert "ΔP→Q lag" in src
    assert "ΔP→Q tail" in src
    assert "def _route_focus_visibility_meta(" in src
    assert "def _route_focus_opacity_profile(" in src
    assert '"show_leading_chip"' in src
    assert '"show_trailing_chip"' in src
    assert '"show_summary"' in src
    assert '"show_history_strip"' in src
    assert '"strip_glow_alpha"' in src
    assert '"strip_core_alpha"' in src
    assert '"node_ring_alpha"' in src
    assert '"node_badge_alpha"' in src
    assert '"node_label_bg_alpha"' in src
    assert '"node_value_bg_alpha"' in src
    assert '"node_label_text_alpha"' in src
    assert '"node_value_text_alpha"' in src
    assert '"node_badge_text_alpha"' in src
    assert "def _node_label_presentation_meta(" in src
    assert '"layout_mode": layout_mode' in src
    assert '"minimal": 0.72 if mode != "quiet" else 0.56' in src
    assert '"value_mode": "inline"' in src
    assert '"inline_value_rect": (16.0, -11.0, 52.0, 16.0)' in src
    assert "def _draw_node_indicator_bars(" in src
    assert "def _draw_edge_flow_arrows(" in src
    assert "def _draw_actuation_led(" in src
    assert "def _route_node_label_opacity_profile(" in src
    assert "def _route_pressure_chip_rect(" in src
    assert "def _draw_route_pressure_strip_compact_chip(" in src
    assert "def _draw_route_pressure_strip_terminal_compact_summary(" in src
    assert "def _draw_route_pressure_strip_cause_effect_accent(" in src
    assert "Ведёт:" in src
    assert "Ведущий конец не определён" in src
    assert "Последние " in src
    assert "self._draw_route_pressure_strip_terminal_focus(painter)" in src
    assert "self._draw_route_pressure_strip_cause_effect_accent(" in src
    assert "def _draw_route_pressure_strip_flow_history(" in src
    assert "self._draw_route_pressure_strip_compact_chip(" in src
    assert "self._draw_route_pressure_strip_terminal_compact_summary(" in src
    assert "visibility_meta = _route_focus_visibility_meta(payload, terminal_meta, detail_mode=self._detail_mode)" in src
    assert "opacity_meta = _route_focus_opacity_profile(visibility_meta, detail_mode=self._detail_mode)" in src
    assert "self._update_hover_route_pressure_focus()" in src
    assert "route_terminal_meta = self._active_route_pressure_terminal_meta()" in src
    assert "route_intermediate_items = _route_pressure_strip_intermediate_nodes_meta(" in src
    assert "route_label_role = \"\"" in src
    assert "presentation_meta = _node_label_presentation_meta(" in src
    assert "indicator_rect = self._draw_node_indicator_bars(" in src

    assert "alpha_scale = float(presentation_meta.get(\"alpha_scale\") or 1.0)" in src
    assert "value_mode = str(presentation_meta.get(\"value_mode\") or \"separate\")" in src
    assert "if value_mode == \"inline\":" in src
    assert "value_padding = (5.0, 1.0, -5.0, -1.0)" in src
    assert "self._occupied_node_overlay_rects: list[QtCore.QRectF] = []" in src
    assert "chosen_shift_y" in src
    assert "route_label_opacity = _route_node_label_opacity_profile(" in src
    assert "label_text_color.setAlpha(label_text_alpha)" in src
    assert "value_text_color.setAlpha(value_text_alpha)" in src
    assert "badge_text_color.setAlpha(badge_text_alpha)" in src
    assert "self._draw_edge_flow_arrows(" in src
    assert '"actuated": _edge_actuation_active(' in src
    assert "self._draw_actuation_led(" in src
    assert "occupied_inline_rects: list[QtCore.QRectF] = [QtCore.QRectF(item) for item in self._occupied_node_overlay_rects]" in src
    assert "def _resolve_overlay_rect(" in src
    assert "def _payload_is_focus_cylinder(self, payload: dict[str, Any]) -> bool:" in src
    assert "def _cylinder_inline_indicator_rect(self, payload: dict[str, Any]) -> QtCore.QRectF | None:" in src
    assert "def _component_anchor_marker_rect(self, payload: dict[str, Any]) -> QtCore.QRectF | None:" in src
    assert "def _component_anchor_badge_rect(self, payload: dict[str, Any]) -> QtCore.QRectF | None:" in src
    assert "def _component_inline_badge_rect(self, payload: dict[str, Any]) -> QtCore.QRectF | None:" in src
    assert "def _canvas_zoom_scale(self) -> float:" in src
    assert "def _component_anchor_presentation_meta(self, payload: dict[str, Any]) -> dict[str, Any]:" in src
    assert "def _component_indicator_payload(self, payload: dict[str, Any], *, global_peak_flow_abs: float) -> dict[str, Any]:" in src
    assert "def _draw_component_indicator_bars(" in src
    assert "def _normalize_flow_display_mode(mode: str) -> str:" in src
    assert "def _normalize_pressure_display_mode(mode: str) -> str:" in src
    assert "def _flow_display_unit(dataset: MnemoDataset | None, mode: str) -> str:" in src
    assert "def _pressure_display_unit(mode: str) -> str:" in src
    assert "def _flow_series_for_display(dataset: MnemoDataset | None, q_values: np.ndarray | list[float], mode: str) -> np.ndarray:" in src
    assert "def _pressure_series_from_pa(dataset: MnemoDataset | None, p_values: np.ndarray | list[float], mode: str) -> np.ndarray:" in src
    assert "def _edge_recent_history_summary_display(" in src
    assert "def _edge_recent_pressure_summary_display(" in src
    assert "def set_display_context(self, *, dataset: MnemoDataset | None, pressure_display_mode: str) -> None:" in src
    assert "def set_display_modes(self, *, flow_display_mode: str, pressure_display_mode: str) -> None:" in src
    assert "def _display_flow_unit(self) -> str:" in src
    assert "def _display_pressure_unit(self) -> str:" in src
    assert "def _display_pressure_delta_unit(self) -> str:" in src
    assert "def _fmt_flow_value(self, value: Any, *, digits: int) -> str:" in src
    assert "def _fmt_pressure_value(self, value_bar_g: Any, *, digits: int) -> str:" in src
    assert "def _fmt_pressure_delta_value(self, value_bar: Any, *, digits: int) -> str:" in src
    assert "def render_details(" in src
    assert "flow_display_mode: str," in src
    assert "pressure_display_mode: str," in src
    assert "q_vals_display = _flow_series_for_display(dataset, np.asarray(q_arr, dtype=float), flow_display_mode)" in src
    assert "p_vals = _pressure_series_from_pa(dataset, np.asarray(p_arr, dtype=float), pressure_display_mode)" in src
    assert "_edge_recent_history_summary_display(history_meta, dataset, flow_display_mode)" in src
    assert "_edge_recent_pressure_summary_display(pressure_history_meta, pressure_display_mode)" in src
    assert "self.heatmap.set_display_context(dataset=dataset, pressure_display_mode=pressure_display_mode)" in src
    assert "_pressure_value_from_bar_g(" in src
    assert "_pressure_delta_from_bar(card.get(\"delta_peak_bar\"), self._pressure_display_mode)" in src
    assert "pressure_spread_display = _pressure_delta_from_bar(pressure_spread, pressure_display_mode)" in src
    assert "self.guide_panel.set_display_modes(" in src
    assert "self.startup_banner.set_display_modes(" in src
    assert "flow_display_mode=self._flow_display_mode," in src
    assert "pressure_display_mode=self._pressure_display_mode," in src
    assert "flow_display_mode=self.flow_display_mode," in src
    assert "pressure_display_mode=self.flow_display_mode," not in src
    assert "unit=flow_unit," in src
    assert "unit=pressure_unit," in src
    assert "def _build_active_diagonal_focus_meta(" in src
    assert "flow_display_mode: str = \"nlpm\"" in src
    assert "pressure_display_mode: str = \"bar_g\"" in src
    assert "q_values=q_series_display," in src
    assert "q_unit=flow_unit," in src
    assert "\"flow_unit\": flow_unit," in src
    assert "\"pressure_unit\": pressure_unit," in src
    assert "\"pressure_delta_unit\": pressure_delta_unit," in src
    assert "pressure_display_mode=self._pressure_display_mode," in src
    assert "flow_display_mode=self.flow_display_mode," in src
    assert "pressure_display_mode=self.pressure_display_mode," in src
    assert "self._push_diagnostics()" in src
    assert "self._fmt_pressure_value(pressure, digits=2)" in src
    assert "self._fmt_pressure_delta_value(payload.get('delta_p_bar'), digits=2)" in src
    assert "self._fmt_flow_value(payload.get(\"q_now\"), digits=2)" in src
    assert "self.mnemo_view.set_display_modes(" in src
    assert "flow_display_mode=self.flow_display_mode," in src
    assert "pressure_display_mode=self.pressure_display_mode," in src
    assert "def _rect_connection_point(rect: QtCore.QRectF, target: QtCore.QPointF) -> QtCore.QPointF:" in src
    assert "def _draw_overlay_tether(" in src
    assert "def _draw_cylinder_bridge_indicator(" in src
    assert "def _draw_cylinder_inline_indicator(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_anchor_marker(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_anchor_badge(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_inline_badge(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "self._draw_cylinder_bridge_indicator(" in src
    assert 'component_payloads = [' in src
    assert 'if self._detail_mode == "quiet" and not bool(payload.get("is_selected")) and not bool(presentation_meta.get("show_badge")):' in src
    assert "if not is_focus_payload:" in src
    assert 'if self._detail_mode in {"operator", "quiet"}:' in src
    assert "self._draw_cylinder_inline_indicator(painter, resolved_rect, payload)" in src
    assert "self._draw_component_anchor_marker(painter, resolved_marker_rect, payload)" in src
    assert "self._draw_component_anchor_badge(painter, resolved_rect, payload)" in src
    assert "indicator_payload = self._component_indicator_payload(payload, global_peak_flow_abs=self._global_peak_flow_abs())" in src
    assert "presentation_meta = self._component_anchor_presentation_meta(payload)" in src
    assert 'badge_mode = str(presentation_meta.get("badge_mode") or "text")' in src
    assert '"badge_mode": badge_mode' in src
    assert 'if not bool(presentation_meta.get("show_marker")):' in src
    assert 'if not bool(presentation_meta.get("show_badge")):' in src
    assert 'if bool(presentation_meta.get("show_indicator_bars")):' in src
    assert 'if badge_mode != "graphic":' in src
    assert 'if badge_mode == "graphic":' in src
    assert "self._draw_component_indicator_bars(" in src
    assert "self._draw_overlay_tether(" in src
    assert "self._draw_component_inline_badge(painter, resolved_rect, payload)" in src
    assert 'intermediate_hover_item = route_intermediate_lookup.get(node_name) or {}' in src
    assert 'str(intermediate_hover_item.get("lead_hint_text") or "")' in src
    assert 'str(intermediate_hover_item.get("lead_trend_text") or "")' in src
    assert 'str(intermediate_hover_item.get("flow_hint_text") or "")' in src
    assert 'and self._hover_kind == "node"' in src
    assert "self._draw_selected_edge_terminal_overlay(painter)" in src
    assert "self._draw_diagonal_focus_pressure_strips(painter)" in src
    assert "spotlight_nodes.update(diagonal_focus_nodes)" in src
    assert "def _cylinder_compact_rect(self, payload: dict[str, Any]) -> QtCore.QRectF:" in src
    assert "def _draw_cylinder_compact_card(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_cylinder_compact_row(" in src
    assert 'if self._detail_mode != "full":' in src
    assert "self._draw_cylinder_compact_card(painter, rect, payload)" in src
    assert "def _selected_edge_direction_card_rect(" in src
    assert "def _draw_selected_edge_direction_compact_card(" in src
    assert "self._draw_selected_edge_direction_compact_card(painter, compact_rect, payload)" in src
    assert "Направление выбранной ветви" in src
    assert "Вердикт:" in src
    assert "Сигналы:" in src
    assert "Динамика:" in src
    assert "Причинность:" in src
    assert "Лаг:" in src
    assert "Фаза:" in src
    assert "Узкое место:" in src
    assert "Сначала:" in src
    assert "Проверь:" in src
    assert "operator_checklist_rows" in src
    assert "def _draw_edge_operator_checklist(" in src
    assert "def _draw_edge_phase_ribbon(" in src
    assert "phase_ribbon_intervals" in src
    assert "phase_ribbon_interval_label" in src
    assert "phase_ribbon_bottleneck_label" in src
    assert "phase_ribbon_bottleneck_kind" in src
    assert "phase_ribbon_focus_pair_label" in src
    assert "phase_ribbon_focus_stage_labels" in src
    assert "self._draw_edge_recent_history_strip(" in src
    assert "self._draw_edge_recent_pressure_strip(" in src
    assert "self._draw_edge_phase_ribbon(" in src
    assert "def _draw_strip_marker(" in src
    assert "emphasized: bool = False" in src
    assert '"SIG"' in src
    assert "self._draw_selected_edge_direction_overlay(painter)" in src
    assert "def _draw_cylinder_card(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_badge(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_icon(" in src
    assert "self._draw_inline_route_symbol(painter, edge_name=edge_name, payload=inline_payload)" in src
    assert "Inline symbol" in src
    assert "Инженерный фокус ветви" in src
    assert "Клик по 01/02/03 усиливает локальный этап и при необходимости подводит playhead" in src
    assert '"phase_sequence_label": "SIG → ΔP → Q"' in src
    assert '"target_time_s": float(dataset.time_s[step_01_idx])' in src
    assert '"badge_text": "P+"' in src
    assert '"badge_text": "SRC"' in src
    assert "t≈" in src
    assert "self._overlay_targets.append((\"node\", str(cap.get(\"node_name\") or \"\"), cap_rect))" in src
    assert "self._overlay_targets.append((\"node\", node_name, chip_rect))" in src
    assert "self._overlay_targets.append((\"edge\", str(payload.get(\"edge_name\") or \"\"), rect))" in src
    assert "Каталог / серия" in src
    assert "\"canonical_kind\"" in src
    assert "\"camozzi_code\"" in src


def test_desktop_mnemo_offscreen_runtime_window_layout_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")

    from PySide6 import QtWidgets
    from pneumo_solver_ui.desktop_mnemo import app as mnemo_app

    settings_path = tmp_path / "desktop_animator_settings.ini"
    monkeypatch.setattr(mnemo_app, "default_settings_path", lambda _project_root: settings_path)
    npz_path = _write_runtime_mnemo_npz(tmp_path)
    pointer_path = tmp_path / "anim_latest.json"

    qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = mnemo_app.MnemoMainWindow(
        npz_path=npz_path,
        follow=False,
        pointer_path=pointer_path,
        theme="dark",
        startup_preset="runtime_smoke",
        startup_title="Runtime smoke",
        startup_reason="Verify Desktop Mnemo window-layout evidence contract.",
        startup_view_mode="overview",
        startup_time_s=0.5,
        startup_time_label="mid-frame",
        startup_edge="регулятор_до_себя_Pmid_сброс",
        startup_node="Ресивер3",
        startup_event_title="",
        startup_time_ref_npz=str(npz_path),
        startup_checklist=["Проверить layout contract.", "Проверить truth badge."],
    )
    try:
        window.resize(1500, 980)
        window.show()
        for _ in range(4):
            qt_app.processEvents()
        window._push_diagnostics()

        assert window.dataset is not None
        assert window.dataset.npz_path == npz_path.resolve()
        assert window.current_idx == 1
        assert window.selected_edge == "регулятор_до_себя_Pmid_сброс"
        assert window.selected_node == "Ресивер3"
        assert window.truth_text.text() == "Mnemo: confirmed"

        layout_contract = window._build_window_layout_contract()
        assert layout_contract["schema_version"] == "desktop_mnemo_window_layout_contract_v1"
        assert layout_contract["available"] is True
        assert layout_contract["window_objectName"] == "desktop_mnemo_main_window"
        assert layout_contract["window_chrome"] == "native_qt"
        assert layout_contract["custom_titlebar_assumption"] is False
        assert layout_contract["window_geometry_available"] is True
        assert layout_contract["window_state_available"] is True
        assert layout_contract["ui_state_prefix"] == "desktop_mnemo"
        assert layout_contract["current_theme"] == "dark"
        assert layout_contract["dpi_ratio"] is None or float(layout_contract["dpi_ratio"]) > 0.0

        dock_names = {str(item["objectName"]) for item in layout_contract["docks"]}
        assert {
            "dock_overview",
            "dock_snapshot",
            "dock_selection",
            "dock_guide",
            "dock_fidelity",
            "dock_events",
            "dock_trends",
            "dock_legend",
        }.issubset(dock_names)
        assert all("dock_area" in item and "floating" in item and "visible" in item for item in layout_contract["docks"])

        diagnostics = window.mnemo_view.native_canvas._diagnostics
        assert diagnostics["window_layout_contract"]["schema_version"] == "desktop_mnemo_window_layout_contract_v1"
        assert diagnostics["window_layout_contract"]["available"] is True
        assert diagnostics["dataset_contract"]["schema_version"] == "desktop_mnemo_dataset_contract_v1"
        assert diagnostics["dataset_contract"]["available"] is True
        assert diagnostics["overall_truth_state"] in {"solver_confirmed", "source_data_confirmed"}
        assert diagnostics["unavailable_surfaces"] == []
        assert diagnostics["source_markers"]

        sidecar_path = window._persist_event_log(silent=True)
        assert sidecar_path is not None and sidecar_path.exists()
        sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert sidecar_payload["window_layout_contract"]["schema_version"] == "desktop_mnemo_window_layout_contract_v1"
        assert sidecar_payload["window_layout_contract"]["available"] is True
        assert sidecar_payload["dataset_contract"]["schema_version"] == "desktop_mnemo_dataset_contract_v1"
        assert sidecar_payload["dataset_contract"]["available"] is True

        window_png = tmp_path / "desktop_mnemo_window_runtime.png"
        canvas_png = tmp_path / "desktop_mnemo_canvas_runtime.png"
        window_pixmap = window.grab()
        canvas_pixmap = window.mnemo_view.native_canvas.grab()
        assert window_pixmap.save(str(window_png), "PNG")
        assert canvas_pixmap.save(str(canvas_png), "PNG")
        assert window_png.stat().st_size > 4096
        assert canvas_png.stat().st_size > 4096
        assert _pixmap_color_sample_count(window_pixmap) >= 4
        assert _pixmap_color_sample_count(canvas_pixmap) >= 4
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()

    restored = mnemo_app.MnemoMainWindow(
        npz_path=None,
        follow=False,
        pointer_path=pointer_path,
        theme="dark",
        startup_preset="",
        startup_title="",
        startup_reason="",
        startup_view_mode="",
        startup_time_s=None,
        startup_time_label="",
        startup_edge="",
        startup_node="",
        startup_event_title="",
        startup_time_ref_npz="",
        startup_checklist=[],
    )
    try:
        restored.show()
        qt_app.processEvents()
        restored_layout = restored._build_window_layout_contract()
        assert restored_layout["saved_window_geometry_available"] is True
        assert restored_layout["saved_window_state_available"] is True
        assert "window/geometry" in restored_layout["saved_ui_state_keys"]
        assert "window/state" in restored_layout["saved_ui_state_keys"]
    finally:
        restored.close()
        restored.deleteLater()
        qt_app.processEvents()


def test_desktop_mnemo_offscreen_bad_npz_reports_status_without_modal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")

    from PySide6 import QtWidgets
    from pneumo_solver_ui.desktop_mnemo import app as mnemo_app

    settings_path = tmp_path / "desktop_animator_settings.ini"
    monkeypatch.setattr(mnemo_app, "default_settings_path", lambda _project_root: settings_path)
    bad_npz_path = tmp_path / "broken_desktop_mnemo_bundle.npz"
    bad_npz_path.write_bytes(b"not a valid npz bundle")
    pointer_path = tmp_path / "anim_latest.json"

    def forbidden_modal(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Desktop Mnemo must not open QMessageBox.critical in offscreen runtime.")

    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", forbidden_modal)

    qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert mnemo_app._desktop_mnemo_can_show_blocking_dialog() is False

    window = mnemo_app.MnemoMainWindow(
        npz_path=bad_npz_path,
        follow=False,
        pointer_path=pointer_path,
        theme="dark",
        startup_preset="runtime_bad_npz",
        startup_title="Bad NPZ smoke",
        startup_reason="Verify Desktop Mnemo reports load errors without blocking modal in offscreen mode.",
        startup_view_mode="overview",
        startup_time_s=None,
        startup_time_label="",
        startup_edge="",
        startup_node="",
        startup_event_title="",
        startup_time_ref_npz="",
        startup_checklist=["Проверить no-modal load failure."],
    )
    try:
        qt_app.processEvents()
        assert window.dataset is None
        assert window.truth_text.text() == "Mnemo: unavailable pressure/state"
        assert window.status_text.text().startswith("Ошибка загрузки:")
        window._push_diagnostics()
        diagnostics = window.mnemo_view.native_canvas._diagnostics
        assert diagnostics["overall_truth_state"] == "unavailable"
        assert "dataset" in diagnostics["unavailable_surfaces"]
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()
