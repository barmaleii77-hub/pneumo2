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
    assert 'self.mnemo_view = MnemoNativeView(self)' in src
    assert 'self.native_canvas = MnemoNativeCanvas(self)' in src
    assert 'self.setObjectName("mnemo_native_canvas")' in src
    assert 'self.mode_badge = QtWidgets.QLabel("Native Canvas", header)' in src
    assert "self.native_canvas.set_alerts(alerts)" in src
    assert "self.native_canvas.set_diagnostics(diagnostics)" in src
    assert "self.native_canvas.set_focus_region(focus_region)" in src
    assert "self.native_canvas.show_overview(overview_meta)" in src
    assert 'self.fidelity_panel.render(self.dataset)' in src
    assert "Desktop Mnemo switched to native Qt canvas." in src
    assert "wheel = zoom, drag = pan, click = select" in src
    assert "QtSvg.QSvgRenderer" in src
    assert "def set_diagnostics(self, diagnostics: dict[str, Any]) -> None:" in src
    assert "_build_mnemo_diagnostics_payload" in src
    assert "self._push_diagnostics()" in src
    assert "def set_focus_region(self, focus_region: dict[str, Any] | None) -> None:" in src
    assert "def show_overview(self, meta: dict[str, Any] | None = None) -> None:" in src
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
    assert "self._camera_target_rect: QtCore.QRectF | None = None" in src
    assert "def _set_camera_target(self, target_rect: QtCore.QRectF, *, immediate: bool = False) -> None:" in src
    assert "def _sync_anim_timer(self) -> None:" in src
    assert "def _advance_animations(self) -> None:" in src
    assert "def _interpolate_rect(current: QtCore.QRectF, target: QtCore.QRectF, factor: float) -> QtCore.QRectF:" in src
    assert "def _rect_close_enough(current: QtCore.QRectF, target: QtCore.QRectF) -> bool:" in src
    assert "def _inline_route_symbol_payloads(self, *, max_abs_flow: float) -> dict[str, dict[str, Any]]:" in src
    assert "def _draw_inline_route_symbol(self, painter: QtGui.QPainter, *, edge_name: str, payload: dict[str, Any]) -> None:" in src
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

    assert "def _draw_alert_markers(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_diagnostics_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_focus_overlay(self, painter: QtGui.QPainter) -> None:" in src
    assert "def _draw_cylinder_card(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_badge(self, painter: QtGui.QPainter, rect: QtCore.QRectF, payload: dict[str, Any]) -> None:" in src
    assert "def _draw_component_icon(" in src
    assert "self._draw_inline_route_symbol(painter, edge_name=edge_name, payload=inline_payload)" in src
    assert "Inline symbol" in src
    assert "self._overlay_targets.append((\"node\", str(cap.get(\"node_name\") or \"\"), cap_rect))" in src
    assert "self._overlay_targets.append((\"edge\", str(payload.get(\"edge_name\") or \"\"), rect))" in src
    assert "Каталог / серия" in src
    assert "\"canonical_kind\"" in src
    assert "\"camozzi_code\"" in src
