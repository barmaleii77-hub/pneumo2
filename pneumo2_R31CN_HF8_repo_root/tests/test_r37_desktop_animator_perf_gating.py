from __future__ import annotations

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py"
HMI = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "hmi_widgets.py"
GEOM_ACCEPT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "geometry_acceptance.py"


def test_desktop_animator_refreshes_all_visible_aux_panes_at_capped_fps() -> None:
    src = APP.read_text(encoding="utf-8")

    assert "self._aux_play_fast_fps" in src
    assert "self._aux_play_slow_fps" in src
    assert "self._aux_scrub_fast_fps" in src
    assert "self._aux_scrub_slow_fps" in src
    assert "self._interactive_scrub_slow_batch_size" in src
    assert "self._interactive_scrub_slow_rr_cursor" in src
    assert "self._interactive_scrub_release_only_docks" in src
    assert "self._aux_cadence_tracking_active: bool = False" in src
    assert "self._paused_seek_settle_delay_ms = 20" in src
    assert "self._many_visible_threshold" in src
    assert "def _dock_is_exposed(self, dock_name: str) -> bool:" in src
    assert "for entry in fast_visible:" in src
    assert "for entry in slow_entries:" in src
    assert 'if self.car3d is not None and self._dock_is_visible("dock_3d")' in src
    assert "interactive_scrub = bool(not self._playing and (self._interactive_scrub_active or self.slider.isSliderDown()))" in src
    assert "interactive_scrub=bool(interactive_scrub)" in src
    assert "track_aux_cadence = bool(playing or interactive_scrub)" in src
    assert 'self.slider.sliderPressed.connect(self._slider_pressed)' in src
    assert 'self.slider.sliderReleased.connect(self._slider_released)' in src
    assert 'self._scrub_release_timer.timeout.connect(self._flush_scrub_release_batch)' in src
    assert "def flush_interactive_scrub_detail_batch" in src
    assert "def _take_interactive_scrub_slow_batch" in src


def test_desktop_animator_acceptance_hud_lines_use_bundle_cache() -> None:
    src = GEOM_ACCEPT.read_text(encoding="utf-8")

    assert 'cache_key = "_geometry_acceptance_hud_cache"' in src
    assert "def _ensure_acceptance_hud_cache(bundle: DataBundle) -> Dict[str, Any]:" in src
    assert '"frame_wheel_lines": frame_wheel_lines' in src
    assert "cache = _ensure_acceptance_hud_cache(bundle)" in src
    assert "frame_wheel_lines = tuple(cache.get(\"frame_wheel_lines\") or ())" in src


def test_desktop_animator_geometry_overlays_use_live_viewgeometry_fields() -> None:
    src = APP.read_text(encoding="utf-8")

    assert "self.geom.track:.3f" in src
    assert "self.geom.wheelbase:.3f" in src
    assert "self.geom.wheel_radius:.3f" in src
    assert "self.geom.track_m" not in src
    assert "self.geom.wheelbase_m" not in src
    assert "self.geom.wheel_radius_m" not in src


def test_desktop_animator_scrub_path_avoids_redundant_qt_setters_and_repaints() -> None:
    app_src = APP.read_text(encoding="utf-8")
    hmi_src = HMI.read_text(encoding="utf-8")

    assert "def _set_label_text_if_changed" in app_src
    assert "def _set_graphics_text_if_changed" in app_src
    assert "def _set_graphics_pos_if_changed" in app_src
    assert "def _make_graphics_label_item(" in app_src
    assert "def _set_table_item_text_if_changed" in app_src
    assert "def _set_progress_value_if_changed" in app_src
    assert "def _set_table_row_hidden_if_changed(" in app_src
    assert "def _infer_patm_source(b: \"DataBundle\") -> tuple[Optional[np.ndarray], float]:" in app_src
    assert "def _patm_value_from_source(patm_arr: Optional[np.ndarray], patm_default_pa: float, i: int) -> float:" in app_src
    assert "def _make_series_sampler(*, i0: int, i1: int, alpha: float) -> Callable[[Any, float], float]:" in app_src
    assert "def _sample_series_avg2(" in app_src
    assert "def _ensure_vertical_view_signal_cache(b: DataBundle, wheelbase_m: float) -> Dict[str, Any]:" in app_src
    assert 'key = f"svc__vertical_view_signal_cache__{wb:.6f}"' in app_src
    assert "def _set_table_row_count_if_changed" in app_src
    assert "def _set_table_fixed_row_height" in app_src
    assert "if isinstance(widget, (QtWidgets.QGraphicsView, QtWidgets.QTableWidget, TelemetryPanel)):" in app_src
    assert "vh.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)" in app_src
    assert "self._last_xrange" in app_src
    assert "self._last_yrange" in app_src
    assert "def _range_changed" in app_src
    assert "cache = self._profile_cache or {}" in app_src
    assert "s_cached = cache.get(\"s_world\")" in app_src
    assert "corners_cache = cache.get(\"corners\", {}) or {}" in app_src
    assert "budget_cap = self._road_profile_point_budget_compact if bool(self._compact_dock_mode) else self._road_profile_point_budget_full" in app_src
    assert "max_points = int(max(96, min(int(budget_cap), (plot_width_px // 4) + 24)))" in app_src
    assert "if interactive_scrub:" in app_src
    assert "self._aux_slow_last_ts = float(time.perf_counter())" in app_src
    assert "release_only = set(getattr(self, \"_interactive_scrub_release_only_docks\", set()))" in app_src
    assert "slow_entries = []" in app_src
    assert "coalesced_seek = bool(not self._playing and not interactive_scrub)" in app_src
    assert "interactive_scrub=bool(interactive_scrub or coalesced_seek)" in app_src
    assert "self._scrub_release_timer.start(int(max(0, getattr(self, \"_paused_seek_settle_delay_ms\", 20))))" in app_src
    assert 'key = "svc__corner_signal_cache"' in app_src
    assert "self._cell_items" in app_src
    assert "self._corner_cache = _ensure_corner_signal_cache(b)" in app_src
    assert "self._corner_metric_cache: Dict[str, Dict[str, Any]] = {}" in app_src
    assert "corner_cache = _ensure_corner_signal_cache(b)" in app_src
    assert "self._corner_metric_cache = metric_cache" in app_src
    assert "self._static_bg_cache_key: Optional[tuple[int, int, int]] = None" in app_src
    assert "def _ensure_static_background_cache(self) -> Optional[QtGui.QPixmap]:" in app_src
    assert "bg = self._ensure_static_background_cache()" in app_src
    assert "self._last_fit_rect_key" in app_src
    assert "def _fit_view_to_scene_if_needed" in app_src
    assert "self._fit_view_to_scene_if_needed(scene_rect)" in app_src
    assert "class _QuickBarListCanvas" in app_src
    assert "self.rows_canvas = _QuickBarListCanvas" in app_src
    assert "p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)" in app_src
    assert "p.setRenderHint(QtGui.QPainter.Antialiasing, False)" in app_src
    assert "self._row_layout_key: Optional[tuple[int, int, int]] = None" in app_src
    assert "self._display_rows_key: Optional[tuple[tuple[Any, ...], tuple[int, int, int], tuple[str, int, int, int]]] = None" in app_src
    assert "def _ensure_text_metrics(self) -> tuple[QtGui.QFont, QtGui.QFontMetrics]:" in app_src
    assert "def _ensure_row_layout(self) -> list[tuple[QtCore.QRectF, QtCore.QRectF, QtCore.QRectF]]:" in app_src
    assert "def _rebuild_display_rows(self) -> None:" in app_src
    assert "self._rebuild_display_rows()" in app_src
    assert "display_key = (rows_key, layout_key, metrics_key)" in app_src
    assert "class _PressureQuickGridCanvas" in app_src
    assert "self.canvas = _PressureQuickGridCanvas" in app_src
    assert "self._bg_cache_pixmap" in app_src
    assert "def _ensure_background_cache" in app_src
    assert 'key = "svc__telemetry_summary_cache"' in app_src
    assert "def _ensure_telemetry_summary_cache(b: DataBundle) -> Dict[str, np.ndarray]:" in app_src
    assert "self._value_font = QtGui.QFont(self.font())" in app_src
    assert "self._value_text_pen = QtGui.QPen(QtGui.QColor(234, 238, 243))" in app_src
    assert "self._value_text_pen.setCosmetic(True)" in app_src
    assert "p.setFont(self._value_font)" in app_src
    assert "p.setPen(self._value_text_pen)" in app_src
    assert "self._pressure_series_map: Dict[str, np.ndarray] = {}" in app_src
    assert "self._p_series_map: Dict[str, np.ndarray] = {}" in app_src
    assert "self._last_visual_key: Optional[tuple[int, int, int, int, int, int]] = None" in app_src
    assert "visual_key = (" in app_src
    assert "summary = _ensure_telemetry_summary_cache(b)" in app_src
    assert 't = float(summary["t"][i])' in app_src
    assert 'vx = float(summary["vx"][i])' in app_src
    assert 'zcm = float(summary["zcm"][i])' in app_src
    assert "def set_compact_dock_mode(self, compact: bool) -> None:" in app_src
    assert "dock.topLevelChanged.connect(" in app_src
    assert 'getattr(widget, "set_compact_dock_mode")(not bool(dock.isFloating()))' in app_src
    assert "def set_compact_mode(self, compact: bool) -> None:" in app_src
    assert "self._compact_max_rows" in app_src
    assert "self.setMaximumHeight(82 if compact else 16777215)" in app_src
    assert "self.setMaximumHeight(154 if compact else 16777215)" in app_src
    assert "max_h = 280 if compact else 16777215" in app_src
    assert "self.road = QtWidgets.QGraphicsLineItem()" in app_src
    assert "self.body = QtWidgets.QGraphicsLineItem()" in app_src
    assert "QtWidgets.QGraphicsSimpleTextItem()" in app_src
    assert "self._compact_max_height = 176" in app_src
    assert "self._compact_max_height = 150" in app_src
    assert "def _road_polyline_sample_count(self) -> int:" in app_src
    assert "def _road_x_nodes_for_scene(self, x_min: float, x_max: float) -> np.ndarray:" in app_src
    assert "self._road_x_nodes_cache_key" in app_src
    assert "self._road_x_nodes_cache = np.linspace" in app_src
    assert "def _ensure_road_profile_panel_cache(b: DataBundle, wheelbase_m: float) -> Dict[str, Any]:" in app_src
    assert 'key = f"svc__road_profile_panel_cache__{wb:.6f}"' in app_src
    assert "self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None" in app_src
    assert "def _invalidate_background_cache(self) -> None:" in app_src
    assert "def _ensure_background_cache(" in app_src
    assert "self._signal_cache = _ensure_vertical_view_signal_cache(b, float(self.geom.wheelbase))" in app_src
    assert "if int(getattr(self, \"_bundle_key\", 0) or 0) != id(b) or not self._signal_cache:" in app_src
    assert "sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(" in app_src
    assert "sample = _make_series_sampler(i0=sample_i0, i1=sample_i1, alpha=alpha)" in app_src
    assert "arr = series if isinstance(series, np.ndarray) else np.asarray(series, dtype=float)" in app_src
    assert "if ii0 == ii1 or a <= 1e-12:" in app_src
    assert "if a >= 1.0 - 1e-12:" in app_src
    assert "win_i0 = max(0, i - 200)" in app_src
    assert "win_i1 = min(n, i + 400)" in app_src
    assert "for panel in (self.axleF, self.axleR, self.sideL, self.sideR):" in app_src
    assert "panel.set_bundle(b)" in app_src
    assert "def _geom_key(" in app_src
    assert "def _apply_body_style(" in app_src
    assert "def _apply_head_style(" in app_src
    assert "self.body = QtWidgets.QGraphicsLineItem()" in app_src
    assert "self.gradient_body = bool(gradient_body)" in app_src
    assert "self.arrow_a = Arrow2D(self.scene, width_m=0.03, gradient_body=True)" in app_src
    assert app_src.count("self._render_hints_compact = QtGui.QPainter.TextAntialiasing") >= 2
    assert app_src.count("def _apply_render_hint_policy(self) -> None:") >= 2
    assert app_src.count("elif bool(self._compact_dock_mode):") >= 2
    assert "self._seg_full: Optional[np.ndarray] = None" in app_src
    assert "self._seg_marker_active_count: int = 0" in app_src
    assert "self._last_lane_pen_key: Optional[tuple[int, int]] = None" in app_src
    assert "self._hud_polyline_point_budget_min = 160" in app_src
    assert "self._hud_polyline_point_budget_max = 520" in app_src
    assert "self._hud_perf_polyline_point_budget_cap = 180" in app_src
    assert "self._hud_lane_polyline_scale = 0.58" in app_src
    assert "self._hud_lane_polyline_min_points = 92" in app_src
    assert "self._hud_perf_lane_polyline_scale = 0.46" in app_src
    assert "self._hud_perf_lane_polyline_min_points = 68" in app_src
    assert "self._hud_fill_polyline_scale = 0.42" in app_src
    assert "self._hud_fill_polyline_min_points = 64" in app_src
    assert "self._hud_perf_fill_polyline_scale = 0.34" in app_src
    assert "self._hud_perf_fill_polyline_min_points = 48" in app_src
    assert "self._hud_path_visual_key_quant_scale = 2.0" in app_src
    assert "self._hud_fill_visual_key_quant_scale = 1.0" in app_src
    assert "self._hud_elide_cache: Dict[tuple[str, int, str], str] = {}" in app_src
    assert "self._last_perf_visual_key: Optional[tuple[int, ...]] = None" in app_src
    assert "self._centerline_path_key: Optional[tuple[int, ...]] = None" in app_src
    assert "self._lane_l_path_key: Optional[tuple[int, ...]] = None" in app_src
    assert "self._road_fill_poly_key: Optional[tuple[int, ...]] = None" in app_src
    assert "def _visible_polyline_point_budget(self) -> int:" in app_src
    assert "def _lane_polyline_point_budget(self, centerline_points: int) -> int:" in app_src
    assert "def _fill_polyline_point_budget(self, centerline_points: int) -> int:" in app_src
    assert "def _perf_visual_key(" in app_src
    assert "def _poly_visual_key(self, xa: np.ndarray, ya: np.ndarray, *, closed: bool = False) -> tuple[int, ...]:" in app_src
    assert "def _poly_visual_key_from_arrays(" in app_src
    assert "def _set_poly_path_if_changed(" in app_src
    assert "def _set_poly_polygon_if_changed(" in app_src
    assert "def _ensure_seg_marker_pool(self, n: int) -> None:" in app_src
    assert "@staticmethod\n    def _offset_lane_edges(" in app_src
    assert "def _offset_lane_edges(" in app_src
    assert "def _path_from_xy(xa: np.ndarray, ya: np.ndarray, *, closed: bool = False) -> QtGui.QPainterPath:" in app_src
    assert "def _path_from_arrays(x_arr: np.ndarray, y_arr: np.ndarray, *, closed: bool = False) -> QtGui.QPainterPath:" in app_src
    assert "def _hud_font_key(font: QtGui.QFont) -> str:" in app_src
    assert "def _ensure_hud_static_lines(self, b: DataBundle) -> tuple[str, ...]:" in app_src
    assert "def _hud_static_text(self, b: DataBundle, font: QtGui.QFont, max_px: int) -> str:" in app_src
    assert "def _elide_hud_lines(self, lines: list[str], font: QtGui.QFont, max_px: int) -> list[str]:" in app_src
    assert "self.road_fill = QtWidgets.QGraphicsPolygonItem()" in app_src
    assert "path = QtGui.QPainterPath(QtCore.QPointF(float(x_arr[0]), float(y_arr[0])))" in app_src
    assert "path.lineTo(float(x), float(y))" in app_src
    assert "item.setPolygon(" in app_src
    assert "sel = np.linspace(0, n - 1, num=limit, dtype=int)" in app_src
    assert "np.unique(sel)" not in app_src
    assert "np.insert(sel, 0, 0)" not in app_src
    assert "np.append(sel, n - 1)" not in app_src
    assert "if len(cache) > 2048:" in app_src
    assert "cached = fm.elidedText(text, QtCore.Qt.ElideRight, width_px)" in app_src
    assert "fill_points = self._fill_polyline_point_budget(len(lane_xl))" in app_src
    assert "xlL, ylL, xlR, ylR = self._offset_lane_edges(lane_xl, lane_yl, w)" in app_src
    assert "fill_xlL, fill_ylL, fill_xlR, fill_ylR, _fill_idxs = self._decimate_visible_polyline(fill_points, xlL, ylL, xlR, ylR, lane_idxs)" in app_src
    assert "np.concatenate((fill_xlL, fill_xlR[::-1]))" in app_src
    assert "it = self._seg_marker_items[marker_count]" in app_src
    assert "it.setLine(float(x1), float(y1), float(x2), float(y2))" in app_src
    assert "def _apply_lane_pens_if_needed(self) -> None:" in app_src
    assert "key = self._poly_visual_key_from_arrays(x_arr, y_arr, closed=closed)" in app_src
    assert "quant_scale: float = 2.0" in app_src
    assert "if attr_name == \"_road_fill_poly_key\"" in app_src
    assert "else float(self._hud_path_visual_key_quant_scale)" in app_src
    assert "item.setPath(self._path_from_arrays(x_arr, y_arr, closed=closed))" in app_src
    assert "self.hud_text_static = _make_graphics_label_item(self.scene, font_size=9, z=10.0)" in app_src
    assert "self.hud_text_context = _make_graphics_label_item(self.scene, font_size=9, z=10.0)" in app_src
    assert "self._hud_static_bundle_key: int = 0" in app_src
    assert "self._hud_static_text_cache_key: Optional[tuple[int, str, int]] = None" in app_src
    assert "self._set_poly_path_if_changed(\"_centerline_path_key\", self.centerline, xl, yl)" in app_src
    assert "lane_xl, lane_yl, lane_idxs = self._decimate_visible_polyline(lane_points, xl, yl, idxs)" in app_src
    assert "self._set_poly_polygon_if_changed(" in app_src
    assert "if perf_visual_key == self._last_perf_visual_key:" in app_src
    assert "self._last_perf_visual_key = perf_visual_key" in app_src
    assert "dynamic_lines: list[str] = [f\"v  {v_mps*3.6:6.1f} км/ч\"]" in app_src
    assert "context_lines: list[str] = []" in app_src
    assert "acceptance_lines = list(format_acceptance_hud_lines(b, i))" in app_src
    assert "dynamic_lines = self._elide_hud_lines(dynamic_lines, fnt, max_px)" in app_src
    assert "context_lines = self._elide_hud_lines(context_lines, fnt, max_px)" in app_src
    assert "static_txt = self._hud_static_text(b, fnt, max_px)" in app_src
    assert "_set_graphics_text_if_changed(self.hud_text, dynamic_txt)" in app_src
    assert "_set_graphics_text_if_changed(self.hud_text_context, context_txt)" in app_src
    assert "_set_graphics_text_if_changed(self.hud_text_static, static_txt)" in app_src
    assert "_set_graphics_pos_if_changed(self.hud_text, top_x, top_y)" in app_src
    assert "_set_graphics_pos_if_changed(self.hud_text_context, top_x, context_y)" in app_src
    assert "_set_graphics_pos_if_changed(self.hud_text_static, top_x, static_y)" in app_src
    assert "self.hud_text_context.hide()" in app_src
    assert "self.hud_text_static.hide()" in app_src
    assert app_src.count("self.show_dims = False") >= 2
    assert app_src.count("self.show_scale_bar = True") >= 2
    assert "self._road_profile_point_budget_compact = 176" in app_src
    assert "self._road_profile_point_budget_full = 288" in app_src
    assert "self._compact_plot_height = 110" in app_src
    assert "self._compact_max_height = 138" in app_src
    assert "self.controls_row = QtWidgets.QWidget(self)" in app_src
    assert "self.controls_row.setVisible(not compact)" in app_src
    assert "self.lbl_legend.setVisible(not compact)" in app_src
    assert "self._compact_visual_expanded = False" in app_src
    assert "class _CompactTelemetrySummaryCanvas(QtWidgets.QWidget):" in app_src
    assert "self.compact_summary = _CompactTelemetrySummaryCanvas()" in app_src
    assert "self.compact_summary.setVisible(bool(compact))" in app_src
    assert "self.compact_summary.set_metrics(" in app_src
    assert "if not bool(getattr(self, \"_compact_dock_mode\", False)):" in app_src
    assert "elif self.compact_summary.isVisible():" in app_src
    assert "self.compact_vis_strip = QtWidgets.QWidget()" in app_src
    assert "self.btn_compact_hud = self._make_compact_toggle_button(\"hud\", \"HUD overlays (lanes/text/accel)\")" in app_src
    assert "self.btn_compact_more = self._make_compact_toggle_button(\"...\", \"Показать полный блок визуализации\")" in app_src
    assert "def _sync_compact_visual_strip(self, *_args) -> None:" in app_src
    assert "def _set_compact_visual_expanded(self, expanded: bool) -> None:" in app_src
    assert "self.compact_vis_strip.setVisible(bool(compact_mode and not self._compact_visual_expanded))" in app_src
    assert "self._panel_bg = QtGui.QColor(15, 18, 24)" in app_src
    assert "self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)" in app_src
    assert "def paintEvent(self, event: QtGui.QPaintEvent):  # type: ignore[override]" in app_src
    assert "self._border_pen = QtGui.QPen(self._border_color, 1.0)" in app_src
    assert "self._corner_font = QtGui.QFont(self.font())" in app_src
    assert "self._value_font = QtGui.QFont(self.font())" in app_src
    assert "self.plot.setMaximumHeight(plot_h if compact else 16777215)" in app_src
    assert "world_lo = float(s0 + x_min)" in app_src
    assert "y_range = tuple(cache.get(\"y_range\"" in app_src
    assert "visual_key = (" in app_src
    assert "if visual_key == self._last_visual_key:" in app_src
    assert "self._last_visual_key = visual_key" in app_src
    assert "def _top_descending_indices(values: Any, limit: int, *, threshold: float = 0.0) -> np.ndarray:" in app_src
    assert "self._last_display_key: Optional[tuple[Any, ...]] = None" in app_src
    assert "self._visible_rows: int = 0" in app_src
    assert "self._row_handles: list[tuple[QtWidgets.QTableWidgetItem, QtWidgets.QProgressBar, QtWidgets.QTableWidgetItem]] = []" in app_src
    assert "self._row_handles: list[tuple[QtWidgets.QTableWidgetItem, QtWidgets.QTableWidgetItem, QtWidgets.QProgressBar, QtWidgets.QTableWidgetItem]] = []" in app_src
    assert "class _QuickTextStripCanvas(QtWidgets.QWidget):" in app_src
    assert "self._segments_layout: list[tuple[str, QtGui.QColor, float]] = []" in app_src
    assert "self._segments_layout_key" in app_src
    assert "def _ensure_text_metrics(self) -> tuple[QtGui.QFont, QtGui.QFontMetrics]:" in app_src
    assert "def _rebuild_segment_layout(self) -> None:" in app_src
    assert "layout.append((text_s, qcolor, float(fm.horizontalAdvance(text_s))))" in app_src
    assert "if expected_layout_key != self._segments_layout_key:" in app_src
    assert app_src.count("self._row_binding_keys: list[Optional[int]] = []") >= 2
    assert "order = _top_descending_indices(vals, topn, threshold=(thr if only_active else -1.0))" in app_src
    assert "order = _top_descending_indices(aq, topn, threshold=(thr if only_active else -1.0))" in app_src
    assert "if self._row_binding_keys[r] != j:" in app_src
    assert "self._row_binding_keys[r] = j" in app_src
    assert "_call_with_qt_update_batch(self.table, _apply_rows)" in app_src
    assert "_set_table_row_hidden_if_changed(self.table, r, True)" in app_src
    assert "self._short_names: list[str] = []" in app_src
    assert "self._kind_codes = np.asarray(kind_codes, dtype=np.int8)" in app_src
    assert "self.lbl_exh = QtWidgets.QLabel(\"выхлоп: —\")" in app_src
    assert app_src.count("self.header_canvas = _QuickTextStripCanvas(self)") >= 2
    assert "self.header_canvas.setVisible(compact)" in app_src
    assert "self.lbl_groups.setVisible(not compact)" in app_src
    assert "self.lbl.setVisible(not compact)" in app_src
    assert "self.header_canvas.set_segments(" in app_src
    assert "_set_progress_value_if_changed(bar" not in app_src
    assert "idxs = _top_descending_indices(vals, self.max_rows, threshold=thr)" in app_src
    assert "order = _top_descending_indices(aq, self.max_rows, threshold=thr)" in app_src
    assert "def _decimate_series_for_display" in hmi_src
    assert "self._static_cache_key: Optional[tuple[int, int, Any]] = None" in hmi_src
    assert "def _ensure_static_cache(self, rect: QtCore.QRect) -> Optional[QtGui.QPixmap]:" in hmi_src
    assert "bg = self._ensure_static_cache(r)" in hmi_src
    assert "if idx_i == self._idx:" in hmi_src
    assert "# The rounded panel chrome is already cached with AA; dynamic trend redraw only needs crisp text." in hmi_src
    assert "p.setRenderHints(QtGui.QPainter.TextAntialiasing)" in hmi_src
