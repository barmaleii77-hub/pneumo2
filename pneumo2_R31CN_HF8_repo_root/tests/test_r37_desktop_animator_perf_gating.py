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


def test_desktop_animator_3d_springs_and_pneumo_visuals_use_real_force_channels() -> None:
    src = APP.read_text(encoding="utf-8")

    assert "self._visual_sample_dt_s: float = 1.0 / 120.0" in src
    assert "self._last_visual_sample_t_s: float | None = None" in src
    assert "def _time_scaled_smoothing_response(self, response: float) -> float:" in src
    assert "def _update_visual_sample_dt(self, sample_t_s: float | None) -> None:" in src
    assert "dt_ratio = float(_clamp(float(dt_s / nominal_dt_s), 0.25, 6.0))" in src
    assert "rr = 1.0 - ((1.0 - base_rr) ** dt_ratio)" in src
    assert "rr = self._time_scaled_smoothing_response(response)" in src
    assert "self._update_visual_sample_dt(_sample_t)" in src
    assert "self._last_visual_sample_t_s = None" in src
    assert "self._spring_force_series_map = {}" in src
    assert "self._pneumo_force_series_map = {}" in src
    assert 'corner_cache.get(str(corner), {}).get("springF", 0.0)' in src
    assert 'corner_cache.get(str(corner), {}).get("pneumoF", 0.0)' in src
    assert 'pneumo_force_col = f"сила_пневматики_{cyl}_{corner}_Н"' in src
    assert "def _sample_spring_force_n(" in src
    assert "def _sample_cylinder_pneumatic_force_n(" in src
    assert "def _sample_cylinder_chamber_pressure_fallback_pa(" in src
    assert "self._sample_cylinder_chamber_pressure_fallback_pa(" in src
    assert "active_gauge_pa = float(abs(pneumo_force_n) / (cap_area_m2 if pneumo_force_n >= 0.0 else annulus_area_m2))" in src
    assert "chamber_gauge_pa = active_gauge_pa if ((pneumo_force_n >= 0.0) == bool(is_cap)) else residual_gauge_pa" in src
    assert "spring_force_n: float," in src
    assert "spring_load_u = float(_clamp(abs(float(spring_force_n)) / spring_force_cap, 0.0, 1.0))" in src
    assert '"spring_force_n": float(' in src
    assert 'spring_force_n=float(spring_state.get("spring_force_n", 0.0))' in src
    assert "pneumo_force_u = float(" in src
    assert "glass_energy_u = float(max(cap_pressure_u, pneumo_force_u))" in src
    assert "glass_energy_u = float(max(rod_pressure_u, pneumo_force_u))" in src
    assert "spring_energy_u=float(pneumo_force_u)" in src


def test_desktop_animator_3d_road_wire_grid_uses_square_world_cells() -> None:
    src = APP.read_text(encoding="utf-8")

    assert "def _square_road_grid_lateral_stride(*, half_width_m: float, lateral_count: int, cross_spacing_m: float) -> int:" in src
    assert "lateral_step = (2.0 * half_width) / float(max(1, lat_count - 1))" in src
    assert "lateral_stride = int(" in src
    assert "_square_road_grid_lateral_stride(" in src
    assert "cross_spacing_m=float(grid_cross_spacing_m)," in src


def test_desktop_animator_3d_road_preview_uses_speed_magnitude_for_truthful_lookahead() -> None:
    src = APP.read_text(encoding="utf-8")

    assert 'summary = _ensure_telemetry_summary_cache(bundle)' in src
    assert 'np.asarray(summary["vx"], dtype=float).reshape(-1)' in src
    assert 'np.asarray(summary["vy"], dtype=float).reshape(-1)' in src
    assert "vxb, vyb = bundle.ensure_body_velocity_xy()" in src
    assert "v_mag = np.hypot(" in src
    assert 'np.asarray(vx_body, dtype=float).reshape(-1)' in src
    assert 'np.asarray(vy_body, dtype=float).reshape(-1)' in src
    assert 'vx = np.asarray(bundle.get("скорость_vx_м_с", 0.0), dtype=float).reshape(-1)' in src
    assert 'vy = np.asarray(bundle.get("скорость_vy_м_с", 0.0), dtype=float).reshape(-1)' in src
    assert "v_mag = np.hypot(vx[:n_v], vy[:n_v])" in src
    assert "finite_v = np.asarray(v_mag[np.isfinite(v_mag)], dtype=float)" in src
    assert 'finite_v = np.asarray(np.abs(vx[np.isfinite(vx)]), dtype=float)' not in src
    assert "def _sampled_road_preview_lookahead_m(self, speed_m_s: float) -> float:" in src
    assert "def _sampled_road_preview_window_m(" in src
    assert "sampled = float(max(0.0, self._auto_lookahead(float(abs(speed_m_s)))))" in src
    assert "current_speed_m_s = float(math.hypot(vel_body_x, vel_body_y))" in src
    assert "preview_back_m, preview_fwd_m = self._sampled_road_preview_window_m(" in src
    assert "signed_speed_m_s=float(speed_along_road)," in src
    assert "return float(-lookahead_m), float(history_m)" in src
    assert "return float(-history_m), float(lookahead_m)" in src
    assert "la = self._sampled_road_preview_lookahead_m(current_speed_m_s)" not in src


def test_desktop_animator_status_line_uses_aligned_summary_speed_truth() -> None:
    src = APP.read_text(encoding="utf-8")
    anchor = 'self._status(f"t={t:.3f}s, v={v:.2f}m/s, file={b.npz_path.name}")'
    assert anchor in src
    tail = src.split(anchor)[0][-1400:]

    assert 'summary = _ensure_telemetry_summary_cache(b)' in tail
    assert 't_status = _sample_series_local(summary["t"], i0=sample_i0, i1=sample_i1, alpha=alpha, default=t)' in tail
    assert 'vx_status = _sample_series_local(summary["vx"], i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in tail
    assert 'vy_status = _sample_series_local(summary["vy"], i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in tail
    assert 'if np.isfinite(float(t_status)):' in tail
    assert "vxb_status = b.get(" not in tail
    assert "vyb_status = b.get(" not in tail


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
    assert "ReceiverTankWidget" in app_src
    assert "RoadProfilePanel" in app_src
    assert "PressurePanel" in app_src
    assert "FlowPanel" in app_src
    assert "ValvePanel" in app_src
    assert "if isinstance(" in app_src
    assert "CornerHeatmapPanel," in app_src
    assert "ReceiverTankWidget," in app_src
    assert "RoadProfilePanel," in app_src
    assert "PressurePanel," in app_src
    assert "FlowPanel," in app_src
    assert "ValvePanel," in app_src
    assert "EventTimelineWidget," in app_src
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
    assert '"stroke": np.asarray(b.get(f"сжатие_подвески_шток_{c}_м", 0.0), dtype=float)' in app_src
    assert '"strokePos": np.asarray(b.get(f"положение_штока_{c}_м", 0.0), dtype=float)' in app_src
    assert '"strokeFrac": np.asarray(b.get(f"доля_хода_штока_{c}", 0.0), dtype=float)' in app_src
    assert '"suspF": np.asarray(b.get(f"сила_подвески_{c}_Н", 0.0), dtype=float)' in app_src
    assert '"springF": np.asarray(b.get(f"сила_пружины_{c}_Н", 0.0), dtype=float)' in app_src
    assert '"pneumoF": np.asarray(b.get(f"сила_пневматики_{c}_Н", 0.0), dtype=float)' in app_src
    assert '"tireCompression": np.asarray(b.get(f"сжатие_шины_{c}_м", 0.0), dtype=float)' in app_src
    assert "self._cell_items" in app_src
    assert "self._corner_cache = _ensure_corner_signal_cache(b)" in app_src
    assert '"Fподв (Н)"' in app_src
    assert '"Fпруж (Н)"' in app_src
    assert '"Fпневм (Н)"' in app_src
    assert '"Шток Δ (м)"' in app_src
    assert '"Шина сжатие (м)"' in app_src
    assert 'title="3D: Кузов/дорога/контакт"' in app_src
    assert 'action_text="3D: Кузов/дорога/контакт (отдельное окно)"' in app_src
    assert 'РљСѓР·РѕРІ/РґРѕСЂРѕРіР°/РєРѕРЅС‚Р°РєС‚' not in app_src
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
    assert "def _prepare_static_text(text_item: QtGui.QStaticText, font: QtGui.QFont) -> None:" in app_src
    assert "def _ensure_row_layout(self) -> list[tuple[QtCore.QRectF, QtCore.QRectF, QtCore.QRectF]]:" in app_src
    assert "def _rebuild_display_rows(self) -> None:" in app_src
    assert "self._rebuild_display_rows()" in app_src
    assert "display_key = (rows_key, layout_key, metrics_key)" in app_src
    assert "left_static = QtGui.QStaticText(left_text)" in app_src
    assert "right_static = QtGui.QStaticText(right_text)" in app_src
    assert "p.drawStaticText(left_pos, left_static)" in app_src
    assert "p.drawStaticText(right_pos, right_static)" in app_src
    assert "class _PressureQuickGridCanvas" in app_src
    assert "self.canvas = _PressureQuickGridCanvas" in app_src
    assert 'self._display_values: Dict[str, str] = {str(x): "—" for x in self._nodes}' in app_src
    assert 'self._value_static_texts: Dict[str, QtGui.QStaticText] = {str(x): QtGui.QStaticText("—") for x in self._nodes}' in app_src
    assert "self._bg_cache_pixmap" in app_src
    assert "def _ensure_background_cache" in app_src
    assert "def _prepare_static_text(self, text_item: QtGui.QStaticText) -> None:" in app_src
    assert 'key = "svc__telemetry_summary_cache"' in app_src
    assert "def _ensure_telemetry_summary_cache(b: DataBundle) -> Dict[str, np.ndarray]:" in app_src
    assert "t_series = np.asarray(b.t, dtype=float).reshape(-1)" in app_src
    assert "n_t = int(t_series.size)" in app_src
    assert "vxb, vyb = b.ensure_body_velocity_xy()" in app_src
    assert "vx_series = _align_series_length(vxb, n_t, fill=0.0)" in app_src
    assert "vy_series = _align_series_length(vyb, n_t, fill=0.0)" in app_src
    assert "yaw_rate_series = _align_series_length(b.ensure_yaw_rate_rad_s(), n_t, fill=0.0)" in app_src
    assert "axb, ayb = b.ensure_body_acceleration_xy()" in app_src
    assert "ax_series = _align_series_length(axb, n_t, fill=0.0)" in app_src
    assert "ay_series = _align_series_length(ayb, n_t, fill=0.0)" in app_src
    assert "self._value_font = QtGui.QFont(self.font())" in app_src
    assert "self._value_text_pen = QtGui.QPen(QtGui.QColor(234, 238, 243))" in app_src
    assert "self._value_text_pen.setCosmetic(True)" in app_src
    assert 'display_values[str(node)] = f"{rounded:.2f} bar(g)"' in app_src
    assert 'text_item.setText(str(text))' in app_src
    assert 'text_item = self._value_static_texts.get(node)' in app_src
    assert 'p.drawStaticText(info["value_pos"], text_item)' in app_src
    assert "p.setFont(self._value_font)" in app_src
    assert "p.setPen(self._value_text_pen)" in app_src
    assert "p.setRenderHint(QtGui.QPainter.Antialiasing, False)" in app_src
    assert "p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)" in app_src
    assert "p.setRenderHint(QtGui.QPainter.Antialiasing, True)" in app_src
    assert "vx_body, vy_body = bundle.ensure_body_velocity_xy()" in app_src
    assert "speed_mag = np.hypot(" in app_src
    assert "finite_v = np.asarray(speed_mag[np.isfinite(speed_mag)], dtype=float)" in app_src
    assert "x_path, y_path = bundle.ensure_world_xy()" in app_src
    assert "x_path = np.asarray(x_path, dtype=float).reshape(-1)" in app_src
    assert "y_path = np.asarray(y_path, dtype=float).reshape(-1)" in app_src
    assert "self._pressure_series_map: Dict[str, np.ndarray] = {}" in app_src
    assert "self._main_pressure_series_map: Dict[str, np.ndarray] = {}" in app_src
    assert "self._patm_arr, self._patm_default_pa = _infer_patm_source(b)" in app_src
    assert "P = sample(arr, patm)" in app_src
    assert 's = "—" if not np.isfinite(bar_g) else f"{bar_g:.2f}"' in app_src
    assert 'key = "svc__world_progress_series"' in app_src
    assert 'key = "svc__body_longitudinal_progress_series"' in app_src
    assert "def _cumulative_path_length_series(x_series: Any, y_series: Any) -> np.ndarray:" in app_src
    assert "def _ensure_world_progress_series(b: DataBundle) -> np.ndarray:" in app_src
    assert "def _ensure_body_longitudinal_progress_series(b: DataBundle) -> np.ndarray:" in app_src
    assert "return np.concatenate(([0.0], np.cumsum(ds, dtype=float))).astype(float, copy=False)" in app_src
    assert 'np.asarray(b.get("путь_x_м", 0.0), dtype=float).reshape(-1)' in app_src
    assert 'np.asarray(b.get("путь_y_м", 0.0), dtype=float).reshape(-1)' in app_src
    assert "vxb_arr, _ = b.ensure_body_velocity_xy()" in app_src
    assert "vx_mid = 0.5 * (vx[:-1] + vx[1:])" in app_src
    assert "ds = vx_mid * dt" in app_src
    assert "def _solver_signed_speed_along_road(" in app_src
    assert "_ensure_world_progress_series(b) if s_progress_series is None else s_progress_series" in app_src
    assert "speed_mag = abs(ds / dt)" in app_src
    assert "xw_arr, yw_arr = b.ensure_world_xy()" in app_src
    assert "vxw_arr, vyw_arr = b.ensure_world_velocity_xy()" in app_src
    assert "vxb_arr, vyb_arr = b.ensure_body_velocity_xy()" in app_src
    assert 'body_vx = float("nan")' in app_src
    assert 'body_vy = float("nan")' in app_src
    assert 'body_vx = float(get_value("скорость_vx_м_с", 0.0))' in app_src
    assert 'body_vy = float(get_value("скорость_vy_м_с", 0.0))' in app_src
    assert "solver_speed_mag = float(math.hypot(body_vx, body_vy))" in app_src
    assert "tangent_x = float(tx / tangent_norm)" in app_src
    assert "tangent_y = float(ty / tangent_norm)" in app_src
    assert "v_proj = float(vxw * tangent_x + vyw * tangent_y)" in app_src
    assert "return float(v_proj)" in app_src
    assert "return float(math.copysign(speed_mag, body_vx))" in app_src
    assert "vxb_arr, vyb_arr = b.ensure_body_velocity_xy()" in app_src
    assert "yaw_rate = b.ensure_yaw_rate_rad_s()" in app_src
    assert "axb_arr, ayb_arr = b.ensure_body_acceleration_xy()" in app_src
    assert 'vxb_arr = b.get("скорость_vx_м_с", 0.0)' in app_src
    assert 'vyb_arr = b.get("скорость_vy_м_с", 0.0)' in app_src
    assert 'summary = _ensure_telemetry_summary_cache(b)' in app_src
    assert 'yaw_series = summary["yaw"]' in app_src
    assert 'vxb_series = summary["vx"]' in app_src
    assert 'vyb_series = summary["vy"]' in app_src
    assert 'yaw_rate_series = summary["yaw_rate"]' in app_src
    assert 'ax_series = summary["ax"]' in app_src
    assert 'ay_series = summary["ay"]' in app_src
    assert "vel_body_x = float(" in app_src
    assert "vel_body_y = float(" in app_src
    assert "spin_progress_series = np.asarray(_ensure_body_longitudinal_progress_series(b), dtype=float)" in app_src
    assert "spin_progress_m = float(" in app_src
    assert "rolling_progress_m=spin_progress_m" in app_src
    assert "self._tire_compression_series_map[str(corner)] = np.asarray(" in app_src
    assert "def _sample_corner_tire_compression_m(" in app_src
    assert "tire_compressions_m = [" in app_src
    assert "path_progress_m=s_progress_m" not in app_src
    assert "if np.isfinite(float(speed_m_s)) and float(speed_m_s) < -1e-6:" not in app_src
    assert "# ---- Vectors (velocity & acceleration) in local road plane" in app_src
    assert "vec_origin = np.asarray(center_draw, dtype=float) + np.array(" in app_src
    assert "[0.0, 0.0, float(z_vec_offset)]" in app_src
    assert "vel_vec = np.asarray(" in app_src
    assert "float(vel_body_x * self._vel_scale)" in app_src
    assert "float(vel_body_y * self._vel_scale)" in app_src
    assert "acc_vec = np.asarray(" in app_src
    assert "float(external_ax * self._accel_scale)" in app_src
    assert "float(external_ay * self._accel_scale)" in app_src
    assert "np.asarray(R_local[:, 1], dtype=float) * float(vel_body_y * self._vel_scale)" not in app_src
    assert 'vec_origin = np.asarray(center_draw, dtype=float) + np.asarray(R_local[:, 2], dtype=float) * float(z_vec_offset)' not in app_src
    assert "focus_center = (" in app_src
    assert "else np.asarray(center_draw, dtype=float).reshape(3) + np.array([0.0, 0.0, 0.18 * body_h], dtype=float)" in app_src
    assert "else np.asarray(center_draw, dtype=float).reshape(3) + np.asarray(R_local[:, 2], dtype=float).reshape(3) * (0.18 * body_h)" not in app_src
    assert 'self.lbl_v = QtWidgets.QLabel("v = —")' in app_src
    assert "if abs(yaw_rate) > 1e-6 and abs(v_mps) > 1e-3:" in app_src
    assert "R = v_mps / yaw_rate" in app_src
    assert "a_c = v_mps * yaw_rate" in app_src
    assert "a_c = ay" not in app_src
    assert "_set_label_text_if_changed(self.lbl_v, f\"v = {_fmt(v_mps, ' m/s', digits=2)}\")" in app_src
    assert "road_forward = _project_vector_to_plane(" in app_src
    assert "road_motion_forward = (" in app_src
    assert "if float(speed_along_road) >= -1e-6" in app_src
    assert "road_side = _project_vector_to_plane(" in app_src
    assert "road_view_dir = _norm_or(road_view_dir, road_motion_forward)" in app_src
    assert "fog_center = np.asarray(road_plane_center, dtype=float) + road_motion_forward * float(offset_fwd_m)" in app_src
    assert "axis_u_xyz=road_motion_forward," in app_src
    assert "fog_center = np.asarray(road_plane_center, dtype=float) + road_forward * float(offset_fwd_m)" not in app_src
    assert "axis_u_xyz=road_forward," not in app_src
    assert "focus_primary_dir = _norm_or(" in app_src
    assert "np.asarray(road_motion_forward, dtype=float).reshape(3)," in app_src
    assert "np.asarray(body_forward, dtype=float).reshape(3)," in app_src
    assert "primary_dir_xyz=focus_primary_dir," in app_src
    assert "fallback_dir_xyz=road_side," in app_src
    assert "shadow_motion_fwd = (" in app_src
    assert "key_light_fwd = _project_vector_to_plane(np.asarray(shadow_motion_fwd, dtype=float).reshape(3), wheel_up)" in app_src
    assert "key_light_fwd = _norm_or(np.asarray(key_light_fwd, dtype=float).reshape(3), shadow_motion_fwd)" in app_src
    assert "key_light_fwd = _project_vector_to_plane(np.asarray(wheel_pose_fwds[idx], dtype=float).reshape(3), wheel_up)" not in app_src
    assert "motion_forward_for_grade = (" in app_src
    assert "body_forward_xyz=motion_forward_for_grade," in app_src
    assert "body_forward_xyz=body_forward_for_grade," not in app_src
    assert "body_h = np.asarray(body, dtype=float)" in app_src
    assert "body_h[2] = 0.0" in app_src
    assert "view_h = np.asarray(body_h, dtype=float)" in app_src
    assert "frontal_u = float(_clamp(0.5 + 0.5 * float(np.dot(view_h, body_h)), 0.0, 1.0))" in app_src
    assert "frontal_u = float(_clamp(0.5 + 0.5 * float(np.dot(view_h, body)), 0.0, 1.0))" not in app_src
    assert "def _sample_signed_speed_along_world_path_local(" in app_src
    assert "xw_arr, yw_arr = b.ensure_world_xy()" in app_src
    assert "vxw_arr, vyw_arr = b.ensure_world_velocity_xy()" in app_src
    assert "yaw_series = b.get(\"yaw_рад\", 0.0)" in app_src
    assert "yaw_value = float(" in app_src
    assert "_sample_angle_series_local(" in app_src
    assert "vxw = float(body_vx * math.cos(yaw_value) - body_vy * math.sin(yaw_value))" in app_src
    assert "vyw = float(body_vx * math.sin(yaw_value) + body_vy * math.cos(yaw_value))" in app_src
    assert "tangent_x = float(tx / tangent_norm)" in app_src
    assert "tangent_y = float(ty / tangent_norm)" in app_src
    assert "v_proj = float(vxw * tangent_x + vyw * tangent_y)" in app_src
    assert "signed_speed_hint = _sample_signed_speed_along_world_path_local(" in app_src
    assert "return float(math.copysign(speed_mag, signed_speed_hint))" in app_src
    assert "def _hud_motion_window_extents(self, *, signed_body_forward_m_s: float) -> tuple[float, float]:" in app_src
    assert "v_forward_signed_m_s = _sample_signed_speed_along_world_path_local(" in app_src
    assert "default_signed_m_s=float(sample(vxb_series, 0.0))," in app_src
    assert "hud_rear_m, hud_forward_m = self._hud_motion_window_extents(" in app_src
    assert "self._apply_lane_pens_if_needed(rear_m=float(hud_rear_m), forward_m=float(hud_forward_m))" in app_src
    assert "mask = (yl >= -float(hud_rear_m)) & (yl <= float(hud_forward_m))" in app_src
    assert "top_y = float(hud_forward_m) - 4.5" in app_src
    assert "scene_rect = QtCore.QRectF(-8.0, -float(hud_rear_m) - 4.0, 16.0, float(hud_forward_m + hud_rear_m) + 8.0)" in app_src
    assert "v_forward_signed_m_s = float(sample(vxb_series, 0.0))" not in app_src
    assert "axis_v_xyz=road_side," in app_src
    assert "def _camera_view_direction_local_xyz(self, *, target_xyz: Optional[np.ndarray] = None) -> np.ndarray:" in app_src
    assert "def _set_camera_center_if_needed(self, center_xyz: np.ndarray) -> None:" in app_src
    assert "follow_center = np.array(" in app_src
    assert "0.2 * float(max(0.1, self.geom.frame_height))" in app_src
    assert 'self.view.opts["center"] = pg.Vector(float(follow_center[0]), float(follow_center[1]), float(follow_center[2]))' in app_src
    assert "self._last_camera_center_key: Optional[tuple[int, int, int]] = None" in app_src
    assert "self._set_camera_center_if_needed(np.asarray(center_draw, dtype=float).reshape(3))" in app_src
    assert "if target_xyz is not None:" in app_src
    assert 'target = np.asarray(target_xyz, dtype=float).reshape(3)' in app_src
    assert 'camera_view_dir = self._camera_view_direction_local_xyz(target_xyz=np.asarray(center_draw, dtype=float))' in app_src
    assert "self._p_series_map: Dict[str, np.ndarray] = {}" in app_src
    assert "class _PressureBarCanvas(QtWidgets.QWidget):" in app_src
    assert "self.bar = _PressureBarCanvas(max_bar_g=self.max_bar_g)" in app_src
    assert "class _PercentBarCanvas(QtWidgets.QWidget):" in app_src
    assert "def setValue(self, value: int) -> None:" in app_src
    assert "self._fill_brush = QtGui.QBrush(QtGui.QColor(fill_color))" in app_src
    assert "def set_value_bar_g(self, bar_g: Optional[float]) -> None:" in app_src
    assert "visual_key = int(round(frac * 1000.0))" in app_src
    assert "self._marker_active_pen = QtGui.QPen(QtGui.QColor(230, 190, 90, 230), 2)" in app_src
    assert "self._flow_in_brush = QtGui.QBrush(QtGui.QColor(80, 220, 120, 230))" in app_src
    assert "self._pipe_out_brush = QtGui.QBrush(QtGui.QColor(240, 90, 90, 220))" in app_src
    assert 'self._pressure_static_text = QtGui.QStaticText("P: —")' in app_src
    assert 'self._flow_static_text = QtGui.QStaticText("in:   0.0 g/s\\nout:  0.0 g/s")' in app_src
    assert "self._last_sample_t_s: float | None = None" in app_src
    assert "def _time_scaled_indicator_response(self, sample_t_s: float | None, *, base_response: float = 0.18) -> float:" in app_src
    assert "flow_response = self._time_scaled_indicator_response(_sample_t, base_response=0.18)" in app_src
    assert "a = float(flow_response)" in app_src
    assert "def _prepare_static_text(self, text_item: QtGui.QStaticText) -> None:" in app_src
    assert "def _set_static_text_if_changed(self, text_item: QtGui.QStaticText, text: str) -> None:" in app_src
    assert 'self._set_static_text_if_changed(self._pressure_static_text, p_txt)' in app_src
    assert 'self._set_static_text_if_changed(self._flow_static_text, q_txt)' in app_src
    assert "p.drawStaticText(QtCore.QPointF(max(0.0, 0.5 * (float(w) - p_w)), float(tank.bottom() + 6.0)), self._pressure_static_text)" in app_src
    assert "p.drawStaticText(QtCore.QPointF(max(0.0, 0.5 * (float(w) - q_w)), float(tank.bottom() + 26.0)), self._flow_static_text)" in app_src
    assert "self._last_visual_key: Optional[tuple[int, int, int, int, int, int]] = None" in app_src
    assert "visual_key = (" in app_src
    assert "summary = _ensure_telemetry_summary_cache(b)" in app_src
    assert 'sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(' in app_src
    assert 'sample = _make_series_sampler(i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha))' in app_src
    assert 't = sample(summary["t"], 0.0)' in app_src
    assert 'vx = sample(summary["vx"], 0.0)' in app_src
    assert 'vy = sample(summary["vy"], 0.0)' in app_src
    assert 'yaw_rate = sample(summary["yaw_rate"], 0.0)' in app_src
    assert 'ax = sample(summary["ax"], 0.0)' in app_src
    assert 'ay = sample(summary["ay"], 0.0)' in app_src
    assert 'zcm = sample(summary["zcm"], 0.0)' in app_src
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
    assert "s_world = np.asarray(_ensure_world_progress_series(b), dtype=float)" in app_src
    assert "s_world = np.asarray(_ensure_world_progress_series(b), dtype=float).reshape(-1)" in app_src
    assert "self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None" in app_src
    assert "def _invalidate_background_cache(self) -> None:" in app_src
    assert "def _ensure_background_cache(" in app_src
    assert "self._signal_cache = _ensure_vertical_view_signal_cache(b, float(self.geom.wheelbase))" in app_src
    assert "if int(getattr(self, \"_bundle_key\", 0) or 0) != id(b) or not self._signal_cache:" in app_src
    assert "sample_i0, sample_i1, alpha, _sample_t = _sample_time_bracket(" in app_src
    assert "sample = _make_series_sampler(i0=sample_i0, i1=sample_i1, alpha=alpha)" in app_src
    assert "def _sample_signed_speed_along_world_path_local(" in app_src
    assert "def _solver_signed_speed_along_road(" in app_src
    assert "return _sample_signed_speed_along_world_path_local(" in app_src
    assert "default_signed_m_s=float(get_value(\"скорость_vx_м_с\", 0.0))" in app_src
    assert "speed_along_road = self._solver_signed_speed_along_road(" in app_src
    assert "i0=i0," in app_src
    assert "i1=i1," in app_src
    assert "alpha=alpha," in app_src
    assert "get_value=_g," in app_src
    assert "arr = series if isinstance(series, np.ndarray) else np.asarray(series, dtype=float)" in app_src
    assert "if ii0 == ii1 or a <= 1e-12:" in app_src
    assert "if a >= 1.0 - 1e-12:" in app_src
    assert 'idx_ref = int(_clamp(int(sample_i0 if float(alpha) < 0.5 else sample_i1), 0, n - 1))' in app_src
    assert "win_i0 = max(0, idx_ref - 200)" in app_src
    assert "win_i1 = min(n, idx_ref + 400)" in app_src
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
    assert "def _camera_view_direction_local_xyz(self, target_xyz: Optional[np.ndarray] = None) -> np.ndarray:" in app_src
    assert "cam_xyz - center_xyz" in app_src
    assert "camera_view_dir = self._camera_view_direction_local_xyz(target_xyz=np.asarray(center_draw, dtype=float).reshape(3))" in app_src
    assert "camera_view_dir = self._camera_view_direction_local_xyz()" not in app_src
    assert "road_forward = _project_vector_to_plane(body_forward, np.array([0.0, 0.0, 1.0], dtype=float))" in app_src
    assert "road_motion_forward = (" in app_src
    assert "if float(speed_along_road) >= -1e-6" in app_src
    assert "road_side = _project_vector_to_plane(body_side, np.array([0.0, 0.0, 1.0], dtype=float))" in app_src
    assert "road_view_dir = _norm_or(road_view_dir, road_motion_forward)" in app_src
    assert "fog_center = np.asarray(road_plane_center, dtype=float) + road_motion_forward * float(offset_fwd_m)" in app_src
    assert "axis_u_xyz=road_motion_forward," in app_src
    assert "axis_v_xyz=road_side," in app_src
    assert "fog_center = np.asarray(road_plane_center, dtype=float) + body_forward * float(offset_fwd_m)" not in app_src
    assert "center_xyz=fog_center,\n                                    axis_u_xyz=body_forward," not in app_src
    assert "center_xyz=fog_center,\n                                    axis_u_xyz=body_forward,\n                                    axis_v_xyz=body_side," not in app_src
    assert "else np.asarray(center_draw, dtype=float).reshape(3) + np.array([0.0, 0.0, 0.18 * body_h], dtype=float)" in app_src
    assert "else np.asarray(center_draw, dtype=float).reshape(3) + np.asarray(R_local[:, 2], dtype=float).reshape(3) * (0.18 * body_h)" not in app_src
    assert "primary_dir_xyz=road_motion_forward," in app_src
    assert "fallback_dir_xyz=road_side," in app_src
    assert "shadow_motion_fwd = (" in app_src
    assert "key_light_fwd = _project_vector_to_plane(np.asarray(shadow_motion_fwd, dtype=float).reshape(3), wheel_up)" in app_src
    assert "key_light_fwd = _norm_or(np.asarray(key_light_fwd, dtype=float).reshape(3), shadow_motion_fwd)" in app_src
    assert "key_light_fwd = _project_vector_to_plane(np.asarray(wheel_pose_fwds[idx], dtype=float).reshape(3), wheel_up)" not in app_src
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
    assert "def _apply_lane_pens_if_needed(self, *, rear_m: float, forward_m: float) -> None:" in app_src
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
    assert "def _current_segment_index_for_sample(self, *, idx: int, s_value: float) -> int:" in app_src
    assert "v0_mps = math.hypot(vx0, vy0)" in app_src
    assert "self._lookahead_m = float(_clamp(20.0 + v0_mps * 4.0, 40.0, 140.0))" in app_src
    assert "cur_seg_idx = self._current_segment_index_for_sample(idx=idx_ref, s_value=s_now)" in app_src
    assert 'seg_id = int(info.get("id", info.get("seg_id", 0)))' in app_src
    assert "dynamic_lines: list[str] = [f\"v  {v_mps*3.6:6.1f} км/ч\"]" in app_src
    assert "s_world = _ensure_world_progress_series(b)" in app_src
    assert "context_lines: list[str] = []" in app_src
    assert "acceptance_lines = list(format_acceptance_hud_lines(b, i, sample_t=_sample_t))" in app_src
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
    assert '"t": np.asarray(b.t, dtype=float).reshape(-1)' in app_src
    assert "zb = sample(sig[\"zb\"], 0.0)" in app_src
    assert "air = int(sample(sig[\"air\"], 0.0) > 0.5)" in app_src
    assert "v = sample(arr, 0.0) if isinstance(arr, np.ndarray) else 0.0" in app_src
    assert "zr = sample(road_arr, float(\"nan\")) if road_arr is not None else float(\"nan\")" in app_src
    assert 'idx_ref = int(_clamp(int(sample_i0 if float(alpha) < 0.5 else sample_i1), 0, len(s) - 1))' in app_src
    assert "s0 = sample(s, float(s[idx_ref]))" in app_src
    assert "zc = sample(z_arr, float(\"nan\"))" in app_src
    assert "s_progress_series = np.asarray(_ensure_world_progress_series(b), dtype=float)" in app_src
    assert "s_path = np.asarray(_ensure_world_progress_series(bundle), dtype=float).reshape(-1)" in app_src
    assert "speed_sign * math.hypot(float(x0), float(y0))" not in app_src
    assert "self.corner_table.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "self.corner_heatmap.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "self.corner_quick.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "self.road_profile.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "self.press_panel.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "self.flow_panel.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "self.valve_panel.update_frame(b, i, sample_t=sample_t)" in app_src
    assert "vals0 = np.asarray(b.open.values[i0, self._idxs], dtype=float)" in app_src
    assert "q0 = np.asarray(b.q.values[i0, self._idxs], dtype=float)" in app_src
    assert "self._compact_visual_expanded = False" in app_src
    assert "class _CompactTelemetrySummaryCanvas(QtWidgets.QWidget):" in app_src
    assert "self._value_static_texts: list[QtGui.QStaticText] = []" in app_src
    assert "self._value_font = QtGui.QFont(self.font())" in app_src
    assert "def _prepare_static_text(self, text_item: QtGui.QStaticText) -> None:" in app_src
    assert "self.compact_summary = _CompactTelemetrySummaryCanvas()" in app_src
    assert "self.compact_summary.setVisible(bool(compact))" in app_src
    assert "self.compact_summary.set_metrics(" in app_src
    assert "text_item = QtGui.QStaticText(str(value))" in app_src
    assert "self._value_static_texts.append(text_item)" in app_src
    assert "p.drawStaticText(value_pos, text_item)" in app_src
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
    assert "self._fg_pen = QtGui.QPen(self._fg_color, 1.0)" in app_src
    assert "self._bg_brush = QtGui.QBrush(self._bg_color)" in app_src
    assert "self._corner_font = QtGui.QFont(self.font())" in app_src
    assert "self._value_font = QtGui.QFont(self.font())" in app_src
    assert "self._corner_static_text = QtGui.QStaticText(self.corner)" in app_src
    assert "self._value_static_text = QtGui.QStaticText(self._value_text)" in app_src
    assert "self._frame_rect = QtCore.QRectF()" in app_src
    assert "self._bg_cache_key: Optional[tuple[int, int, int, int, int, int]] = None" in app_src
    assert "self._bg_cache_pixmap: Optional[QtGui.QPixmap] = None" in app_src
    assert "def _prepare_static_text(text_item: QtGui.QStaticText, font: QtGui.QFont) -> None:" in app_src
    assert "def _ensure_layout(self) -> None:" in app_src
    assert "def _ensure_background_cache(self) -> Optional[QtGui.QPixmap]:" in app_src
    assert "self._bg_cache_key = None" in app_src
    assert "bg = self._ensure_background_cache()" in app_src
    assert "p.drawPixmap(0, 0, bg)" in app_src
    assert "p.drawRoundedRect(self._frame_rect, 8.0, 8.0)" in app_src
    assert "p.drawStaticText(self._corner_pos, self._corner_static_text)" in app_src
    assert "p.drawStaticText(self._value_pos, self._value_static_text)" in app_src
    assert "self.plot.setMaximumHeight(plot_h if compact else 16777215)" in app_src
    assert "world_lo = float(s0 + x_min)" in app_src
    assert "y_range = tuple(cache.get(\"y_range\"" in app_src
    assert "visual_key = (" in app_src
    assert "if visual_key == self._last_visual_key:" in app_src
    assert "self._last_visual_key = visual_key" in app_src
    assert "def _top_descending_indices(values: Any, limit: int, *, threshold: float = 0.0) -> np.ndarray:" in app_src
    assert "self._last_display_key: Optional[tuple[Any, ...]] = None" in app_src
    assert "self._visible_rows: int = 0" in app_src
    assert "self._row_handles: list[tuple[QtWidgets.QTableWidgetItem, _PercentBarCanvas, QtWidgets.QTableWidgetItem]] = []" in app_src
    assert "self._row_handles: list[tuple[QtWidgets.QTableWidgetItem, QtWidgets.QTableWidgetItem, _PercentBarCanvas, QtWidgets.QTableWidgetItem]] = []" in app_src
    assert "class _QuickTextStripCanvas(QtWidgets.QWidget):" in app_src
    assert "self._segments_layout: list[tuple[str, QtGui.QColor, float, QtGui.QStaticText]] = []" in app_src
    assert "self._segments_layout_key" in app_src
    assert "def _ensure_text_metrics(self) -> tuple[QtGui.QFont, QtGui.QFontMetrics]:" in app_src
    assert "def _prepare_static_text(text_item: QtGui.QStaticText, font: QtGui.QFont) -> None:" in app_src
    assert "def _rebuild_segment_layout(self) -> None:" in app_src
    assert "static_text = QtGui.QStaticText(text_s)" in app_src
    assert "layout.append((text_s, qcolor, float(fm.horizontalAdvance(text_s)), static_text))" in app_src
    assert "if expected_layout_key != self._segments_layout_key:" in app_src
    assert "p.drawStaticText(QtCore.QPointF(x, text_y), static_text)" in app_src
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
    assert "QtWidgets.QProgressBar()" not in app_src
    assert "idxs = _top_descending_indices(vals, self.max_rows, threshold=thr)" in app_src
    assert "order = _top_descending_indices(aq, self.max_rows, threshold=thr)" in app_src
    assert "def _decimate_series_for_display" in hmi_src
    assert "self._static_cache_key: Optional[tuple[int, int, Any]] = None" in hmi_src
    assert "def _ensure_static_cache(self, rect: QtCore.QRect) -> Optional[QtGui.QPixmap]:" in hmi_src
    assert "bg = self._ensure_static_cache(r)" in hmi_src
    assert "if idx_i == self._idx:" in hmi_src
    assert "# The rounded panel chrome is already cached with AA; dynamic trend redraw only needs crisp text." in hmi_src
    assert "p.setRenderHints(QtGui.QPainter.TextAntialiasing)" in hmi_src


def test_desktop_animator_source_routes_hot_3d_draw_paths_through_safe_helpers() -> None:
    app_src = APP.read_text(encoding="utf-8")

    for needle in (
        "def _set_line_item_data(",
        "or np.any(faces < 0)",
        "or np.any(faces >= verts.shape[0])",
        "_set_poly_mesh(self._chassis_mesh, v_box, self._box_faces)",
        "face_colors_rgba_u8=wheel_face_colors",
        "_set_line_item_data(self._contact_pts, marker_pos, colors_rgba=marker_cols)",
        "_set_line_item_data(self._contact_links, link_pos, colors_rgba=link_cols)",
        "face_colors_rgba_u8=road_face_colors",
        "_set_line_item_data(self._road_edges, edge, colors_rgba=edge_colors)",
        "_set_line_item_data(self._road_stripes, grid_lines, colors_rgba=stripe_colors)",
    ):
        assert needle in app_src


def test_desktop_animator_source_uses_named_gl_draw_diagnostics() -> None:
    app_src = APP.read_text(encoding="utf-8")

    for needle in (
        "class _DiagnosticGLViewWidget(gl.GLViewWidget):",
        "self._anim_draw_failure_counts: Dict[str, int] = {}",
        'self.view = _DiagnosticGLViewWidget() if _DiagnosticGLViewWidget is not None else gl.GLViewWidget()',
        'print(f"Error while drawing item {name} ({type(i).__name__}).")',
        'print(f"Further draw errors for item {name} are suppressed.")',
        "def _refresh_gl_debug_names(self) -> None:",
        '_set_gl_item_debug_name(self._grid, "grid")',
        '("_road_mesh", "road_mesh")',
        '("_wheel_meshes", "wheel_mesh")',
    ):
        assert needle in app_src
