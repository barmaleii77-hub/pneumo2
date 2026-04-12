from __future__ import annotations

from pathlib import Path


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
    assert 'self.startup_banner_action = QtGui.QAction("Onboarding", self)' in src
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
    assert "ACK события" in src
    assert "Reset события" in src
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
    assert 'self.mode_badge = QtWidgets.QLabel("Native Canvas", header)' in src
    assert "self.native_canvas.set_alerts(alerts)" in src
    assert "self.native_canvas.set_diagnostics(diagnostics)" in src
    assert "self.native_canvas.set_focus_region(focus_region)" in src
    assert "self.native_canvas.show_overview(overview_meta)" in src
    assert 'self.fidelity_panel.render(self.dataset)' in src
    assert 'self._central_layout.addWidget(self.mnemo_view, 1)' in src
    assert "self.mnemo_view.focus_step_jump_requested.connect(self._jump_to_focus_step)" in src
    assert "Desktop Mnemo switched to native Qt canvas." in src
    assert "wheel = zoom, drag = pan, click = select" in src
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
    assert "self._reference_svg_renderer: Any = None" in src
    assert "self._show_reference_scheme = True" in src
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
    assert "DETAIL_MODE_LABELS" in src
    assert 'self.mnemo_view.set_detail_mode(self.detail_mode)' in src
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
    assert 'self.detail_combo.addItem("Тихо", "quiet")' in src
    assert 'self.detail_combo.addItem("Оператор", "operator")' in src
    assert 'self.detail_combo.addItem("Полно", "full")' in src
    assert 'detail_menu = view_menu.addMenu("Плотность overlays")' in src
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
    assert "Регуляторный узел" in src
    assert "Камерный узел" in src
    assert "Почти как ведущий конец" in src
    assert "Ниже ведущего на " in src
    assert "Выше ведущего на " in src
    assert "Идёт к выравниванию" in src
    assert "Сближается с ведущим" in src
    assert "Уходит от ведущего" in src
    assert "Держит разброс к ведущему" in src
    assert "Q↑" in src
    assert "Q↓" in src
    assert "Q=" in src
    assert "Q без истории" in src
    assert "Q-лента" in src
    assert "ΔP→Q ok" in src
    assert "ΔP→Q lag" in src
    assert "ΔP→Q tail" in src
    assert "def _draw_route_pressure_strip_cause_effect_accent(" in src
    assert "Ведёт:" in src
    assert "Ведущий конец не определён" in src
    assert "Последние " in src
    assert "self._draw_route_pressure_strip_terminal_focus(painter)" in src
    assert "self._draw_route_pressure_strip_cause_effect_accent(" in src
    assert "def _draw_route_pressure_strip_flow_history(" in src
    assert "self._update_hover_route_pressure_focus()" in src
    assert "route_terminal_meta = self._active_route_pressure_terminal_meta()" in src
    assert "route_intermediate_items = _route_pressure_strip_intermediate_nodes_meta(" in src
    assert 'intermediate_hover_item = route_intermediate_lookup.get(node_name) or {}' in src
    assert 'str(intermediate_hover_item.get("lead_hint_text") or "")' in src
    assert 'str(intermediate_hover_item.get("lead_trend_text") or "")' in src
    assert 'and self._hover_kind == "node"' in src
    assert "self._draw_selected_edge_terminal_overlay(painter)" in src
    assert "self._draw_diagonal_focus_pressure_strips(painter)" in src
    assert "spotlight_nodes.update(diagonal_focus_nodes)" in src
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
