from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np

SRC = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_validation_scene_grade_profile_is_neutral_and_non_smoothing() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win._scene_scalar_visual_state = {}
    neutral = win._effective_scene_grade_profile(
        validation_perf_mode=True,
        key_prefix="scene-grade-test",
        camera_view_dir_xyz=(0.0, 0.0, 1.0),
        body_forward_xyz=(1.0, 0.0, 0.0),
        mean_load_u=0.9,
        spring_energy_u=0.8,
        glass_energy_u=0.7,
        speed_m_s=42.0,
    )
    assert neutral == {
        "exposure": 1.0,
        "saturation": 1.0,
        "warmth": 0.0,
        "fog_gain": 1.0,
        "highlight_gain": 1.0,
        "alpha_gain": 1.0,
        "frontal_u": 0.5,
        "pitch_u": 0.5,
        "energy_u": 0.0,
    }
    assert win._scene_scalar_visual_state["scene-grade-test:exposure"] == 1.0
    assert win._scene_scalar_visual_state["scene-grade-test:saturation"] == 1.0
    assert win._scene_scalar_visual_state["scene-grade-test:warmth"] == 0.0
    assert win._scene_scalar_visual_state["scene-grade-test:fog_gain"] == 1.0
    assert win._scene_scalar_visual_state["scene-grade-test:highlight_gain"] == 1.0
    assert win._scene_scalar_visual_state["scene-grade-test:alpha_gain"] == 1.0
    assert win._scene_graded_rgba(
        key="scene-grade-test:rgba",
        rgba=(0.12, 0.34, 0.56, 0.78),
        exposure=1.0,
        saturation=1.0,
        warmth=0.0,
        highlight_gain=1.0,
        alpha_gain=1.0,
    ) == (0.12, 0.34, 0.56, 0.78)
    graded_identity = win._scene_grade_color_array(
        np.asarray([[12, 34, 56, 78]], dtype=np.uint8),
        exposure=1.0,
        saturation=1.0,
        warmth=0.0,
        highlight_gain=1.0,
        alpha_gain=1.0,
        output_u8=False,
    )
    np.testing.assert_allclose(
        graded_identity,
        np.asarray([[12, 34, 56, 78]], dtype=np.float32) / 255.0,
        rtol=0.0,
        atol=1e-7,
    )
    default_normal = win._effective_scene_grade_profile(
        validation_perf_mode=False,
        key_prefix="scene-grade-default-normal",
        camera_view_dir_xyz=(0.0, 0.0, 1.0),
        body_forward_xyz=(1.0, 0.0, 0.0),
        mean_load_u=0.9,
        spring_energy_u=0.8,
        glass_energy_u=0.7,
        speed_m_s=42.0,
    )
    assert default_normal == neutral


def test_scene_line_fx_are_explicit_opt_in_for_validator_view() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win._lookbehind_m = 12.0
    win._auto_lookahead = lambda vx_m_s: 35.0 + 2.5 * abs(float(vx_m_s))
    assert not win._scene_line_fx_enabled()

    win._show_scene_line_fx = True
    assert win._scene_line_fx_enabled()

    assert '_show_scene_line_fx = False' in SRC
    assert 'show_scene_line_fx = self._scene_line_fx_enabled()' in SRC
    assert 'body_silhouette_line = self._body_silhouette_line if show_scene_line_fx else None' in SRC
    assert 'focus_halo_line = self._focus_halo_line if show_scene_line_fx else None' in SRC
    assert 'accent_ring = accent_ring_item if show_scene_line_fx else None' in SRC
    assert 'key_light = key_light_item if show_scene_line_fx else None' in SRC


def test_set_bundle_context_reads_spring_runtime_from_npztable_like_main() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget
    from pneumo_solver_ui.suspension_family_runtime import (
        spring_family_active_flag_column,
        spring_family_runtime_column,
    )

    class _FakeMain:
        def __init__(self, data: dict[str, np.ndarray]) -> None:
            self.cols = list(data.keys())
            self._data = {str(k): np.asarray(v, dtype=float) for k, v in data.items()}

        def column(self, name: str) -> np.ndarray:
            return np.asarray(self._data[str(name)], dtype=float)

    class _FakeBundle:
        def __init__(self, main: _FakeMain) -> None:
            self.main = main
            self.meta = {}
            self.p = None

    active_col = spring_family_active_flag_column("Ц1", "ЛП")
    runtime_col = spring_family_runtime_column("длина_установленная_м", "Ц1", "ЛП")
    legacy_col = "пружина_длина_ЛП_м"
    pneumo_force_col = "сила_пневматики_Ц1_ЛП_Н"

    bundle = _FakeBundle(
        _FakeMain(
            {
                active_col: np.asarray([1.0, 1.0, 1.0], dtype=float),
                runtime_col: np.asarray([0.51, 0.50, 0.49], dtype=float),
                legacy_col: np.asarray([0.52, 0.51, 0.50], dtype=float),
                pneumo_force_col: np.asarray([120.0, 130.0, 140.0], dtype=float),
            }
        )
    )

    win = Car3DWidget.__new__(Car3DWidget)
    win._lookbehind_m = 12.0
    win._auto_lookahead = lambda vx_m_s: 35.0 + 2.5 * abs(float(vx_m_s))

    orig_corner_cache = appmod._ensure_corner_signal_cache
    orig_patm = appmod._infer_patm_source
    appmod._ensure_corner_signal_cache = lambda _bundle: {
        corner: {"tireF": np.zeros(3), "tireCompression": np.zeros(3), "springF": np.zeros(3), "pneumoF": np.zeros(3)}
        for corner in appmod.CORNERS
    }
    appmod._infer_patm_source = lambda _bundle: (None, appmod.PATM_PA_DEFAULT)
    try:
        Car3DWidget.set_bundle_context(win, bundle)
    finally:
        appmod._ensure_corner_signal_cache = orig_corner_cache
        appmod._infer_patm_source = orig_patm

    np.testing.assert_allclose(win._spring_active_series_map[str(active_col)], np.asarray([1.0, 1.0, 1.0], dtype=float))
    np.testing.assert_allclose(win._spring_metric_series_map[str(runtime_col)], np.asarray([0.51, 0.50, 0.49], dtype=float))
    np.testing.assert_allclose(win._spring_metric_series_map[str(legacy_col)], np.asarray([0.52, 0.51, 0.50], dtype=float))
    np.testing.assert_allclose(win._pneumo_force_series_map["Ц1:ЛП"], np.asarray([120.0, 130.0, 140.0], dtype=float))


def test_sample_spring_visible_length_prefers_dynamic_runtime_length() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget
    from pneumo_solver_ui.suspension_family_runtime import spring_family_runtime_column

    win = Car3DWidget.__new__(Car3DWidget)
    win._spring_metric_series_map = {
        str(spring_family_runtime_column("длина_м", "Ц1", "ЛП")): np.asarray([0.31, 0.29], dtype=float),
        str(spring_family_runtime_column("длина_установленная_м", "Ц1", "ЛП")): np.asarray([0.52, 0.52], dtype=float),
    }

    sample = win._sample_spring_visible_length_m("Ц1", "ЛП", i0=0, i1=1, alpha=0.5, default_m=float("nan"))

    assert math.isclose(sample, 0.30, rel_tol=0.0, abs_tol=1e-12)


def test_mandatory_spring_geometry_todo_messages_surface_missing_export_geometry() -> None:
    from pneumo_solver_ui.desktop_animator.app import _mandatory_spring_geometry_todo_messages

    bundle = SimpleNamespace(
        meta={
            "packaging": {
                "spring_families": {
                    "cyl1_front": {
                        "label": "Ц1 перед",
                        "missing_geometry_fields": [
                            "wire_diameter_m",
                            "mean_diameter_m",
                            "inner_diameter_m",
                            "outer_diameter_m",
                        ],
                    },
                    "cyl2_front": {
                        "label": "Ц2 перед",
                        "missing_geometry_fields": [],
                    },
                }
            }
        }
    )

    msgs = _mandatory_spring_geometry_todo_messages(bundle)

    assert len(msgs) == 1
    assert "MANDATORY TODO" in msgs[0]
    assert "cyl1_front" in msgs[0]
    assert "wire_diameter_m" in msgs[0]
    assert "outer_diameter_m" in msgs[0]


def test_ring_overlay_info_messages_surface_ring_metadata(monkeypatch) -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod

    bundle = SimpleNamespace(
        npz_path=Path("C:/tmp/anim_latest.npz"),
        meta={"geometry": {"track_m": 1.92, "wheel_width_m": 0.34}},
    )

    monkeypatch.setattr(
        appmod,
        "load_ring_spec_from_npz",
        lambda _path: {
            "seed": 7,
            "segments": [{"name": "S1"}, {"name": "S2"}, {"name": "S3"}],
        },
    )
    monkeypatch.setattr(
        appmod,
        "build_ring_visual_payload_from_spec",
        lambda spec, *, track_m, wheel_width_m, seed: {
            "closure_policy": "strict_exact",
            "ring_length_m": 42.5,
            "meta": {"seam_open": True},
            "seed_echo": seed,
            "track_echo": track_m,
            "wheel_width_echo": wheel_width_m,
            "segments_echo": len(list(spec.get("segments") or [])),
        },
    )

    msgs = appmod._ring_overlay_info_messages(bundle)

    assert msgs == ["RING: strict_exact, шов открыт, сегментов=3, L≈42.50 м"]


def test_ring_segment_ranges_for_bundle_use_nominal_ring_progress(monkeypatch) -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod

    bundle = SimpleNamespace(
        npz_path=Path("C:/tmp/anim_latest.npz"),
        meta={"geometry": {"track_m": 2.0, "wheel_width_m": 0.32}},
        t=np.asarray([0.0, 0.5, 1.0], dtype=float),
    )

    monkeypatch.setattr(
        appmod,
        "load_ring_spec_from_npz",
        lambda _path: {"seed": 3, "segments": [{"name": "S1"}, {"name": "S2"}]},
    )
    monkeypatch.setattr(
        appmod,
        "build_ring_visual_payload_from_spec",
        lambda spec, *, track_m, wheel_width_m, seed: {"segments": list(spec.get("segments") or []), "meta": {}, "closure_policy": "closed_c1_periodic"},
    )
    monkeypatch.setattr(
        appmod,
        "build_nominal_ring_progress_from_spec",
        lambda spec, time_s: {"distance_m": [0.0, 5.0, 10.0]},
    )
    monkeypatch.setattr(
        appmod,
        "build_segment_ranges_from_progress",
        lambda ring_visual, s_values: [
            {"seg_idx": 1, "name": "ISO rough", "road_mode_label": "ISO 8608 (шероховатость)", "turn_direction_label": "Прямо", "idx0": 0, "idx1": 1},
            {"seg_idx": 2, "name": "Sine L/R", "road_mode_label": "Синус L/R", "turn_direction_label": "Поворот влево", "idx0": 2, "idx1": 2},
        ],
    )

    ranges = appmod._ring_segment_ranges_for_bundle(bundle)

    assert len(ranges) == 2
    assert ranges[0]["name"] == "ISO rough"
    assert ranges[1]["turn_direction_label"] == "Поворот влево"


def test_bundle_canvas_warning_lines_surface_overlay_summary() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win._cylinder_truth_gates = {
        "cyl1": {
            "cyl_name": "cyl1",
            "enabled": False,
            "mode": "axis_only",
            "reason": "missing_truth_gate",
        }
    }
    bundle = SimpleNamespace(
        meta={
            "packaging": {
                "spring_families": {
                    "cyl1_front": {"missing_geometry_fields": ["wire_diameter_m"]},
                }
            }
        },
        service_fallback_messages=lambda: ["fallback channel active"],
    )

    orig_ring = appmod._ring_overlay_info_messages
    appmod._ring_overlay_info_messages = lambda _bundle: ["RING: strict_exact, шов замкнут, сегментов=5, L≈18.00 м"]
    try:
        lines = win._bundle_canvas_warning_lines(bundle)
    finally:
        appmod._ring_overlay_info_messages = orig_ring

    assert any("fallback channels active" in line for line in lines)
    assert any("incomplete spring geometry" in line for line in lines)
    assert any("cylinder truth reduced" in line for line in lines)
    assert any(line.startswith("RING: strict_exact") for line in lines)
    assert len(lines) <= 4


def test_road_hud_segment_cache_prefers_ring_ranges_for_authored_ring_context(monkeypatch) -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import RoadHudWidget

    class _FakeBundle:
        def __init__(self) -> None:
            self.t = np.asarray([0.0, 0.2, 0.4, 0.6, 0.8, 1.0], dtype=float)
            self.meta = {}

        def get(self, _name, default=None):
            return default

        def ensure_road_profile(self):
            raise RuntimeError("no canonical road profile in unit test")

    monkeypatch.setattr(
        appmod,
        "_ensure_world_progress_series",
        lambda _bundle: np.asarray([0.0, 2.0, 4.0, 6.0, 8.0, 10.0], dtype=float),
    )
    monkeypatch.setattr(
        appmod,
        "_ring_segment_ranges_for_bundle",
        lambda _bundle: [
            {
                "seg_idx": 1,
                "name": "ISO-1",
                "road_mode_label": "ISO 8608 (шероховатость)",
                "turn_direction_label": "Прямо",
                "speed_start_kph": 30.0,
                "speed_end_kph": 30.0,
                "idx0": 0,
                "idx1": 2,
            },
            {
                "seg_idx": 2,
                "name": "Sine turn",
                "road_mode_label": "Синус L/R",
                "turn_direction_label": "Поворот влево",
                "turn_radius_m": 42.0,
                "speed_start_kph": 45.0,
                "speed_end_kph": 60.0,
                "idx0": 3,
                "idx1": 5,
            },
        ],
    )

    hud = RoadHudWidget.__new__(RoadHudWidget)
    hud._seg_cache_key = None
    hud._seg_starts = None
    hud._seg_ends = None
    hud._seg_ids = None
    hud._seg_full = None
    hud._seg_infos = []
    hud._seg_start_to_idx = {}
    hud._seg_id_to_info = {}

    hud._ensure_segment_cache(_FakeBundle())

    assert [int(v) for v in hud._seg_starts.tolist()] == [0, 3]
    assert [int(v) for v in hud._seg_ends.tolist()] == [3, 6]
    assert hud._seg_infos[0]["name"] == "ISO-1"
    assert hud._seg_infos[0]["surface"] == "ISO 8608 (шероховатость)"
    assert hud._seg_infos[1]["maneuver"] == "Поворот влево"
    assert math.isclose(float(hud._seg_infos[1]["radius_m"]), 42.0, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(float(hud._seg_infos[1]["speed_start_kph"]), 45.0, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(float(hud._seg_infos[1]["speed_end_kph"]), 60.0, rel_tol=0.0, abs_tol=1e-12)


def test_timeline_ring_segment_ranges_for_bundle_use_desktop_bundle_cache() -> None:
    from pneumo_solver_ui.desktop_animator.hmi_widgets import _timeline_ring_segment_ranges_for_bundle

    bundle = SimpleNamespace(
        _desktop_ring_segment_ranges_cache=(
            {
                "seg_idx": 1,
                "name": "ISO rough",
                "edge_color": "#7fa4ff",
                "idx0": 0,
                "idx1": 4,
            },
            {
                "seg_idx": 2,
                "name": "Left turn",
                "edge_color": "#ffb860",
                "idx0": 5,
                "idx1": 9,
            },
        )
    )

    ranges = _timeline_ring_segment_ranges_for_bundle(bundle)

    assert len(ranges) == 2
    assert ranges[0]["name"] == "ISO rough"
    assert ranges[1]["edge_color"] == "#ffb860"


def test_spring_mount_state_anchors_to_housing_and_arm_joint() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    state = Car3DWidget._spring_mount_state_from_packaging(
        packaging_state={
            "housing_seg": (
                np.asarray([0.0, 0.0, 0.0], dtype=float),
                np.asarray([0.0, 0.24, 0.0], dtype=float),
            ),
            "body_seg": (
                np.asarray([0.0, 0.0, 0.0], dtype=float),
                np.asarray([0.0, 0.08, 0.0], dtype=float),
            ),
            "axis_unit": np.asarray([0.0, 1.0, 0.0], dtype=float),
            "body_outer_radius_m": 0.045,
        },
        top_xyz=np.asarray([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.asarray([0.0, 0.36, 0.0], dtype=float),
        top_offset_m=0.09,
    )

    assert state is not None
    assert np.allclose(np.asarray(state["bot_xyz"], dtype=float), np.asarray([0.0, 0.36, 0.0], dtype=float), atol=1e-12)
    assert 0.08 < float(np.asarray(state["top_xyz"], dtype=float)[1]) < 0.24
    assert math.isclose(float(state["host_radius_m"]), 0.045, rel_tol=0.0, abs_tol=1e-12)


def test_road_preview_defaults_to_mesh_without_wire_overlay() -> None:
    assert "self._canvas_warning_label = QtWidgets.QLabel(self.view)" in SRC
    assert "self._set_canvas_warning_lines(self._bundle_canvas_warning_lines(bundle))" in SRC
    assert "ring_info_lines = _ring_overlay_info_messages(bundle)" in SRC
    assert "ring_ranges = _ring_segment_ranges_for_bundle(b)" in SRC
    assert "if not ring_ranges:" in SRC
    assert "build_nominal_ring_progress_from_spec" in SRC
    assert "build_segment_ranges_from_progress" in SRC
    assert 'show_road_wire = bool(show_road and bool(self._visual.get("show_road_wire", False)))' in SRC
    assert "_set_line_item_pos(self._road_edges, None)" in SRC
    assert "_set_line_item_pos(self._road_stripes, None)" in SRC
    assert 'edgeColor=(0.22, 0.30, 0.38, 0.40),' in SRC
    assert "spring_todo_msgs = _mandatory_spring_geometry_todo_messages(b)" in SRC
    assert "ring_info_msgs = _ring_overlay_info_messages(b)" in SRC
    assert 'code="mandatory_spring_geometry_todo"' in SRC
    assert 'spring-todo={len(spring_todo_msgs)}' in SRC


def test_spring_render_uses_trimmed_translucent_geometry_without_tail_leads() -> None:
    assert "end_trim_m: float = 0.0," in SRC
    assert "path = np.asarray(helix, dtype=float)" in SRC
    assert "lead_top =" not in SRC
    assert "lead_bot =" not in SRC
    assert "drawEdges=False," in SRC
    assert 'spring.setGLOptions("translucent")' in SRC
    assert 'spring_seat.setGLOptions("opaque")' in SRC
    assert '"end_trim_m": float(max(0.007, 1.35 * wire_radius_m))' in SRC
    assert "top_seat_center = np.asarray(spring_state[\"top_xyz\"], dtype=float) + spring_axis_unit * (0.10 * seat_thickness_m)" in SRC
    assert "bot_seat_center = np.asarray(spring_state[\"bot_xyz\"], dtype=float) - spring_axis_unit * (1.15 * seat_thickness_m + 1.10 * float(spring_state[\"wire_radius_m\"]))" in SRC
    assert "seat_base_edge_rgba = (0.0, 0.0, 0.0, 0.0)" in SRC


def test_cylinder_internals_render_as_solid_truth_with_outline_overlay() -> None:
    assert "_set_mesh_from_segment(" in SRC
    assert "rod_display_seg = self._rod_display_segment_from_packaging_state(packaging_state)" in SRC
    assert "_set_disc_mesh(" in SRC
    assert "packaging_state.get(\"piston_center\")" in SRC
    assert "self._apply_mesh_material(" in SRC
    assert "self._cyl_rod_meshes[cyl_mesh_idx]" in SRC
    assert "self._cyl_piston_meshes[cyl_mesh_idx]" in SRC
    assert "rod_solid_face_scene_grade" in SRC
    assert "piston_solid_face_scene_grade" in SRC
    assert "show_cylinder_internal_detail_lines = True" in SRC
    assert "self._cyl_piston_ring_lines[cyl_mesh_idx]" in SRC
    assert "self._cyl_rod_core_lines[cyl_mesh_idx]" in SRC
    assert "self._segment_contour_line_vertices(" in SRC
    assert "radius_m=float(packaging_state.get(\"rod_radius_m\", 0.0) or 0.0)" in SRC
    assert "view_dir_xyz=camera_view_dir" in SRC
    assert 'piston_ring.setGLOptions("additive")' in SRC
    assert 'rod_core.setGLOptions("additive")' in SRC


def test_periodic_series_support_for_window_extends_ring_support_across_closure() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    s_support, v_support = Car3DWidget._periodic_series_support_for_window(
        np.asarray([0.0, 4.0, 8.0], dtype=float),
        np.asarray([10.0, 20.0, 30.0], dtype=float),
        cycle_len_m=12.0,
        query_start_m=10.0,
        query_end_m=14.0,
    )

    assert np.any(np.isclose(s_support, 12.0, atol=1e-12))
    assert float(np.max(s_support)) > 12.0
    interp = np.interp(np.asarray([11.0, 13.0], dtype=float), s_support, v_support)
    np.testing.assert_allclose(interp, np.asarray([15.0, 12.5], dtype=float), rtol=0.0, atol=1e-12)


def test_wheel_tire_face_colors_local_matches_world_projection_path() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win.geom = SimpleNamespace(wheel_radius=0.52, wheel_width=0.28)
    win._tire_force_visual_max_n = 4500.0

    verts_local = np.asarray(
        [
            [0.52, -0.14, 0.00],
            [0.00, -0.14, 0.52],
            [-0.52, -0.14, 0.00],
            [0.00, -0.14, -0.52],
            [0.52, 0.14, 0.00],
            [0.00, 0.14, 0.52],
            [-0.52, 0.14, 0.00],
            [0.00, 0.14, -0.52],
        ],
        dtype=float,
    )
    faces = np.asarray(
        [
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int32,
    )

    colors_local = win._wheel_tire_face_colors_local(
        verts_local,
        faces,
        tire_force_n=1850.0,
        wheel_gap_m=0.021,
        speed_m_s=11.0,
        in_air=False,
        spin_phase_rad=0.37,
    )

    center = np.asarray([2.0, -1.5, 4.0], dtype=float)
    forward = np.asarray([0.0, 0.0, 1.0], dtype=float)
    axle = np.asarray([1.0, 0.0, 0.0], dtype=float)
    up = np.asarray([0.0, 1.0, 0.0], dtype=float)
    verts_world = (
        center.reshape(1, 3)
        + verts_local[:, [0]] * forward.reshape(1, 3)
        + verts_local[:, [1]] * axle.reshape(1, 3)
        + verts_local[:, [2]] * up.reshape(1, 3)
    )
    colors_world = win._wheel_tire_face_colors(
        verts_world,
        faces,
        wheel_center_xyz=center,
        axle_xyz=axle,
        forward_xyz=forward,
        up_xyz=up,
        tire_force_n=1850.0,
        wheel_gap_m=0.021,
        speed_m_s=11.0,
        in_air=False,
        spin_phase_rad=0.37,
    )
    np.testing.assert_array_equal(colors_local, colors_world)


def test_wheel_tire_face_colors_from_deform_basis_matches_local_centroid_path() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win.geom = SimpleNamespace(wheel_radius=0.52, wheel_width=0.28)
    win._tire_force_visual_max_n = 4500.0
    win._wheel_deform_basis_cache = {}
    win._wheel_face_gather_cache = {}
    win._wheel_face_color_basis_cache = {}

    base = np.asarray(
        [
            [0.52, -0.14, 0.00],
            [0.00, -0.14, 0.52],
            [-0.52, -0.14, 0.00],
            [0.00, -0.14, -0.52],
            [0.52, 0.14, 0.00],
            [0.00, 0.14, 0.52],
            [-0.52, 0.14, 0.00],
            [0.00, 0.14, -0.52],
        ],
        dtype=float,
    )
    faces = np.asarray(
        [
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int32,
    )
    deformed = win._deformed_wheel_vertices(
        tire_force_n=1850.0,
        tire_compression_m=0.014,
        wheel_gap_m=0.021,
        in_air=False,
        speed_m_s=11.0,
        spin_phase_rad=0.37,
        base_vertices_xyz=base,
    )
    assert deformed is not None

    colors_local = win._wheel_tire_face_colors_local(
        deformed,
        faces,
        tire_force_n=1850.0,
        wheel_gap_m=0.021,
        speed_m_s=11.0,
        in_air=False,
        spin_phase_rad=0.0,
    )
    colors_fast = win._wheel_tire_face_colors_from_deform_basis(
        base,
        faces,
        tire_force_n=1850.0,
        tire_compression_m=0.014,
        wheel_gap_m=0.021,
        speed_m_s=11.0,
        in_air=False,
        spin_phase_rad=0.37,
    )
    np.testing.assert_allclose(colors_fast.astype(float), colors_local.astype(float), rtol=0.0, atol=2.0)


def test_wheel_tire_face_colors_keep_visible_tread_contrast_and_spin_variation() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win.geom = SimpleNamespace(wheel_radius=0.34, wheel_width=0.24)
    win._tire_force_visual_max_n = 4500.0

    verts_local = np.asarray(
        [
            [0.34, -0.12, 0.00],
            [0.00, -0.12, 0.34],
            [-0.34, -0.12, 0.00],
            [0.00, -0.12, -0.34],
            [0.34, 0.12, 0.00],
            [0.00, 0.12, 0.34],
            [-0.34, 0.12, 0.00],
            [0.00, 0.12, -0.34],
        ],
        dtype=float,
    )
    faces = np.asarray(
        [
            [0, 1, 4],
            [1, 5, 4],
            [1, 2, 5],
            [2, 6, 5],
            [2, 3, 6],
            [3, 7, 6],
            [3, 0, 7],
            [0, 4, 7],
        ],
        dtype=np.int32,
    )

    colors_0 = win._wheel_tire_face_colors_local(
        verts_local,
        faces,
        tire_force_n=1800.0,
        wheel_gap_m=0.01,
        speed_m_s=10.0,
        in_air=False,
        spin_phase_rad=0.0,
    )
    colors_1 = win._wheel_tire_face_colors_local(
        verts_local,
        faces,
        tire_force_n=1800.0,
        wheel_gap_m=0.01,
        speed_m_s=10.0,
        in_air=False,
        spin_phase_rad=0.4,
    )

    mean_rgb_contrast = float(np.ptp(colors_0[:, :3].astype(float), axis=0).mean())
    mean_spin_delta = float(np.abs(colors_1[:, :3].astype(float) - colors_0[:, :3].astype(float)).mean())
    mean_alpha = float(colors_0[:, 3].astype(float).mean())

    assert mean_rgb_contrast >= 14.0
    assert mean_spin_delta >= 5.0
    assert mean_alpha >= 96.0


def test_deformed_wheel_vertices_rotate_mesh_with_spin_phase() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win.geom = SimpleNamespace(wheel_radius=0.52, wheel_width=0.28)
    win._tire_force_visual_max_n = 4500.0
    win._wheel_deform_basis_cache = {}

    base = np.asarray(
        [
            [0.52, -0.14, 0.00],
            [0.00, -0.14, 0.52],
            [-0.52, -0.14, 0.00],
            [0.00, -0.14, -0.52],
        ],
        dtype=float,
    )

    verts0 = win._deformed_wheel_vertices(
        tire_force_n=0.0,
        tire_compression_m=0.0,
        wheel_gap_m=0.06,
        in_air=True,
        speed_m_s=0.0,
        spin_phase_rad=0.0,
        base_vertices_xyz=base,
    )
    verts90 = win._deformed_wheel_vertices(
        tire_force_n=0.0,
        tire_compression_m=0.0,
        wheel_gap_m=0.06,
        in_air=True,
        speed_m_s=0.0,
        spin_phase_rad=0.5 * math.pi,
        base_vertices_xyz=base,
    )

    assert verts0 is not None
    assert verts90 is not None
    assert float(verts0[0, 0]) > 0.5
    assert abs(float(verts0[0, 2])) <= 1e-5
    assert abs(float(verts90[0, 0])) <= 1e-5
    assert math.isclose(float(verts90[0, 1]), -0.14, rel_tol=0.0, abs_tol=1e-12)
    assert float(verts90[0, 2]) < -0.5


def test_rotation_from_y_to_vec_keeps_y_axis_aligned_and_orthonormal() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    for vec in (
        np.asarray([0.0, 1.0, 0.0], dtype=float),
        np.asarray([0.0, -1.0, 0.0], dtype=float),
        np.asarray([1.0, 0.0, 0.0], dtype=float),
        np.asarray([0.0, 0.0, 1.0], dtype=float),
        np.asarray([1.0, 2.0, 3.0], dtype=float),
        np.asarray([-2.0, 0.25, 1.0], dtype=float),
    ):
        rot = np.asarray(win._rotation_from_y_to_vec(vec), dtype=float)
        target = np.asarray(vec, dtype=float) / float(np.linalg.norm(vec))
        np.testing.assert_allclose(rot @ np.asarray([0.0, 1.0, 0.0], dtype=float), target, rtol=0.0, atol=1e-7)
        np.testing.assert_allclose(rot.T @ rot, np.eye(3, dtype=float), rtol=0.0, atol=1e-7)


def test_scene_grade_rgba_scalar_matches_array_pipeline() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    rgba = (0.23, 0.47, 0.81, 0.66)
    params = dict(
        exposure=1.08,
        saturation=0.87,
        warmth=0.12,
        highlight_gain=1.14,
        alpha_gain=0.91,
    )
    scalar = Car3DWidget._scene_grade_rgba_scalar(rgba, **params)
    arr = Car3DWidget._scene_grade_color_array(
        np.asarray([rgba], dtype=float),
        output_u8=False,
        **params,
    )
    np.testing.assert_allclose(np.asarray(scalar, dtype=float), np.asarray(arr[0], dtype=float), rtol=0.0, atol=1e-7)


def test_scene_grade_color_array_identity_reuses_contiguous_u8_input_for_u8_output() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    cols = np.asarray([[12, 34, 56, 78], [90, 120, 150, 180]], dtype=np.uint8)
    out = Car3DWidget._scene_grade_color_array(
        cols,
        exposure=1.0,
        saturation=1.0,
        warmth=0.0,
        highlight_gain=1.0,
        alpha_gain=1.0,
        output_u8=True,
    )
    assert out.dtype == np.uint8
    assert out.flags.c_contiguous
    np.testing.assert_array_equal(out, cols)
    assert np.shares_memory(out, cols)


def test_scaled_y_axis_transform3d_matches_rotation_basis_path() -> None:
    from pneumo_solver_ui.desktop_animator.app import (
        Car3DWidget,
        _road_face_color_pattern_cached,
        _segment_endpoints_transform3d,
        _segment_endpoints_transform3d_components,
        _scaled_basis_transform3d,
        _scaled_y_axis_transform3d,
    )

    win = Car3DWidget.__new__(Car3DWidget)
    axis = np.asarray([1.5, 2.0, -0.75], dtype=float)
    rot = np.asarray(win._rotation_from_y_to_vec(axis), dtype=float)
    center = np.asarray([0.25, -1.0, 2.5], dtype=float)
    ref = _scaled_basis_transform3d(
        rot[:, 0],
        rot[:, 1],
        rot[:, 2],
        scale_x=0.12,
        scale_y=float(np.linalg.norm(axis)),
        scale_z=0.12,
        center_xyz=center,
    )
    fast = _scaled_y_axis_transform3d(
        axis,
        scale_radius=0.12,
        scale_y=float(np.linalg.norm(axis)),
        center_xyz=center,
    )
    np.testing.assert_allclose(np.asarray(fast, dtype=float), np.asarray(ref, dtype=float), rtol=0.0, atol=1e-7)

    shoulder_a, center_a, grain_a, weave_a, warm_a = _road_face_color_pattern_cached(33, 9)
    shoulder_b, center_b, grain_b, weave_b, warm_b = _road_face_color_pattern_cached(33, 9)
    assert shoulder_a is shoulder_b
    assert center_a is center_b
    assert grain_a is grain_b
    assert weave_a is weave_b
    assert warm_a is warm_b

    p0 = np.asarray([0.5, -1.25, 2.0], dtype=float)
    p1 = np.asarray([2.0, 0.75, 1.25], dtype=float)
    seg_ref = _scaled_y_axis_transform3d(
        p1 - p0,
        scale_radius=0.12,
        scale_y=float(np.linalg.norm(p1 - p0)),
        center_xyz=0.5 * (p0 + p1),
    )
    seg_fast = _segment_endpoints_transform3d(p0, p1, radius_m=0.12)
    assert seg_fast is not None
    np.testing.assert_allclose(np.asarray(seg_fast, dtype=float), np.asarray(seg_ref, dtype=float), rtol=0.0, atol=1e-7)
    seg_fast_components = _segment_endpoints_transform3d_components(
        p0x=float(p0[0]),
        p0y=float(p0[1]),
        p0z=float(p0[2]),
        p1x=float(p1[0]),
        p1y=float(p1[1]),
        p1z=float(p1[2]),
        radius_m=0.12,
    )
    assert seg_fast_components is not None
    np.testing.assert_allclose(np.asarray(seg_fast_components, dtype=float), np.asarray(seg_ref, dtype=float), rtol=0.0, atol=1e-7)


def test_validation_playback_disables_only_derived_contact_patch_mesh() -> None:
    from pneumo_solver_ui.desktop_animator.app import _should_render_contact_patch_mesh

    assert not _should_render_contact_patch_mesh(show_road=True, validation_perf_mode=True, playback_active=False)
    assert not _should_render_contact_patch_mesh(show_road=True, validation_perf_mode=False, playback_active=True)
    assert not _should_render_contact_patch_mesh(show_road=True, validation_perf_mode=False, playback_active=False)
    assert not _should_render_contact_patch_mesh(show_road=False, validation_perf_mode=False, playback_active=False)


def test_gl_mesh_updates_reuse_meshdata_when_topology_is_unchanged() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import _update_gl_mesh_item_fast

    class _FakeMeshData:
        def __init__(self, *, vertexes, faces, faceColors=None):
            self._vertexes = np.asarray(vertexes, dtype=np.float32)
            self._faces = np.asarray(faces, dtype=np.uint32)
            self._face_colors = None if faceColors is None else np.asarray(faceColors)

        def setVertexes(self, verts, indexed=None, resetNormals=True):
            self._vertexes = np.asarray(verts, dtype=np.float32)

        def setFaceColors(self, colors, indexed=None):
            self._face_colors = np.asarray(colors)

        def vertexes(self):
            return np.asarray(self._vertexes, dtype=np.float32)

    class _FakeGL:
        MeshData = _FakeMeshData

    class _FakeMeshItem:
        def __init__(self) -> None:
            self.opts = {"computeNormals": False}
            self.visible = False
            self.set_mesh_calls = 0
            self.mesh_changed_calls = 0
            self.visible_calls = 0

        def setMeshData(self, *, meshdata):
            self.opts["meshdata"] = meshdata
            self.set_mesh_calls += 1

        def meshDataChanged(self):
            self.mesh_changed_calls += 1

        def setVisible(self, visible: bool):
            self.visible = bool(visible)
            self.visible_calls += 1

    item = _FakeMeshItem()
    verts0 = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    verts1 = np.asarray(
        [
            [0.0, 0.0, 0.1],
            [1.0, 0.0, 0.1],
            [0.0, 1.0, 0.1],
        ],
        dtype=float,
    )
    faces = np.asarray([[0, 1, 2]], dtype=np.int32)
    colors = np.asarray([[10, 20, 30, 255]], dtype=np.uint8)

    orig_gl = appmod.gl
    appmod.gl = _FakeGL()
    try:
        assert _update_gl_mesh_item_fast(item, verts0, faces, face_colors_rgba_u8=colors)
        first_meshdata = item.opts["meshdata"]
        assert hasattr(first_meshdata, "vertexes")
        assert item.set_mesh_calls == 1
        assert item.mesh_changed_calls == 0
        assert item.visible
        assert item.visible_calls == 1

        assert _update_gl_mesh_item_fast(item, verts1, faces, face_colors_rgba_u8=colors)
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert item.mesh_changed_calls == 1
        assert item.visible_calls == 1
        np.testing.assert_allclose(item.opts["meshdata"].vertexes(), verts1.astype(np.float32), rtol=0.0, atol=1e-7)
    finally:
        appmod.gl = orig_gl


def test_set_gl_item_visible_if_changed_supports_gl_visible_method() -> None:
    from pneumo_solver_ui.desktop_animator.app import _set_gl_item_visible_if_changed

    class _FakeGLItem:
        def __init__(self) -> None:
            self._visible = False
            self.visible_calls = 0

        def visible(self) -> bool:
            return bool(self._visible)

        def setVisible(self, visible: bool) -> None:
            self._visible = bool(visible)
            self.visible_calls += 1

    item = _FakeGLItem()
    _set_gl_item_visible_if_changed(item, True)
    assert item.visible() is True
    assert item.visible_calls == 1

    _set_gl_item_visible_if_changed(item, True)
    assert item.visible_calls == 1

    _set_gl_item_visible_if_changed(item, False)
    assert item.visible() is False
    assert item.visible_calls == 2


def test_gl_mesh_updates_reuse_meshdata_for_equal_faces_with_new_array_object() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import _update_gl_mesh_item_fast

    class _FakeMeshData:
        def __init__(self, *, vertexes, faces, faceColors=None):
            self._vertexes = np.asarray(vertexes, dtype=np.float32)
            self._faces = np.asarray(faces, dtype=np.uint32)
            self._face_colors = None if faceColors is None else np.asarray(faceColors)

        def setVertexes(self, verts, indexed=None, resetNormals=True):
            self._vertexes = np.asarray(verts, dtype=np.float32)

        def setFaceColors(self, colors, indexed=None):
            self._face_colors = np.asarray(colors)

        def vertexes(self):
            return np.asarray(self._vertexes, dtype=np.float32)

    class _FakeGL:
        MeshData = _FakeMeshData

    class _FakeMeshItem:
        def __init__(self) -> None:
            self.opts = {"computeNormals": False}
            self.visible = False
            self.set_mesh_calls = 0
            self.mesh_changed_calls = 0

        def setMeshData(self, *, meshdata):
            self.opts["meshdata"] = meshdata
            self.set_mesh_calls += 1

        def meshDataChanged(self):
            self.mesh_changed_calls += 1

        def setVisible(self, visible: bool):
            self.visible = bool(visible)

    item = _FakeMeshItem()
    verts0 = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    verts1 = np.asarray(
        [
            [0.0, 0.0, 0.2],
            [1.0, 0.0, 0.2],
            [0.0, 1.0, 0.2],
        ],
        dtype=float,
    )
    faces0 = np.asarray([[0, 1, 2]], dtype=np.int32)
    faces1 = np.asarray([[0, 1, 2]], dtype=np.int32).copy()

    orig_gl = appmod.gl
    appmod.gl = _FakeGL()
    try:
        assert _update_gl_mesh_item_fast(item, verts0, faces0)
        first_meshdata = item.opts["meshdata"]
        assert item.set_mesh_calls == 1

        assert _update_gl_mesh_item_fast(item, verts1, faces1)
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert item.mesh_changed_calls == 1
        np.testing.assert_allclose(item.opts["meshdata"].vertexes(), verts1.astype(np.float32), rtol=0.0, atol=1e-7)
    finally:
        appmod.gl = orig_gl


def test_gl_mesh_updates_with_explicit_topology_key_skip_crc32_signature_work() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import _update_gl_mesh_item_fast

    class _FakeMeshData:
        def __init__(self, *, vertexes, faces, faceColors=None):
            self._vertexes = np.asarray(vertexes, dtype=np.float32)
            self._faces = np.asarray(faces, dtype=np.uint32)

        def setVertexes(self, verts, indexed=None, resetNormals=True):
            self._vertexes = np.asarray(verts, dtype=np.float32)

    class _FakeGL:
        MeshData = _FakeMeshData

    class _FakeMeshItem:
        def __init__(self) -> None:
            self.opts = {"computeNormals": False}
            self.visible = False

        def setMeshData(self, *, meshdata):
            self.opts["meshdata"] = meshdata

        def meshDataChanged(self):
            pass

        def setVisible(self, visible: bool):
            self.visible = bool(visible)

    item = _FakeMeshItem()
    verts = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    faces = np.asarray([[0, 1, 2]], dtype=np.int32)

    orig_gl = appmod.gl
    orig_crc32 = appmod.zlib.crc32
    crc_calls = {"n": 0}

    def _fail_crc32(data):
        crc_calls["n"] += 1
        return orig_crc32(data)

    appmod.gl = _FakeGL()
    appmod.zlib.crc32 = _fail_crc32
    try:
        assert _update_gl_mesh_item_fast(item, verts, faces, topology_key=("unit-test-topology", 1))
        assert crc_calls["n"] == 0
        assert item.visible
    finally:
        appmod.gl = orig_gl
        appmod.zlib.crc32 = orig_crc32


def test_normalize_face_colors_u8_reuses_contiguous_uint8_input() -> None:
    from pneumo_solver_ui.desktop_animator.app import _normalize_face_colors_u8

    colors = np.asarray([[10, 20, 30, 255], [40, 50, 60, 200]], dtype=np.uint8)
    out = _normalize_face_colors_u8(colors, expected_faces_n=2)
    assert out is not None
    assert out.dtype == np.uint8
    assert out.flags.c_contiguous
    assert np.shares_memory(out, colors)
    np.testing.assert_array_equal(out, colors)


def test_normalize_face_colors_u8_accepts_float_like_input_once() -> None:
    from pneumo_solver_ui.desktop_animator.app import _normalize_face_colors_u8

    colors = np.asarray([[10.2, 20.7, 30.1, 255.0]], dtype=float)
    out = _normalize_face_colors_u8(colors, expected_faces_n=1)
    assert out is not None
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(out, np.asarray([[10, 21, 30, 255]], dtype=np.uint8))


def test_install_cached_gl_location_lookups_memoizes_program_name_pairs() -> None:
    from pneumo_solver_ui.desktop_animator.app import _install_cached_gl_location_lookups

    class _FakeGL:
        def __init__(self) -> None:
            self.attrib_calls = 0
            self.uniform_calls = 0

        def glGetAttribLocation(self, program, name):
            self.attrib_calls += 1
            return 7 if int(program) == 11 and str(name).endswith("a_position") else -1

        def glGetUniformLocation(self, program, name):
            self.uniform_calls += 1
            return 13 if int(program) == 11 and bytes(name).endswith(b"u_mvp") else -1

    fake = _FakeGL()
    _install_cached_gl_location_lookups(fake)

    assert fake.glGetAttribLocation(11, "a_position") == 7
    assert fake.glGetAttribLocation(11, "a_position") == 7
    assert fake.attrib_calls == 1

    assert fake.glGetUniformLocation(11, b"u_mvp") == 13
    assert fake.glGetUniformLocation(11, b"u_mvp") == 13
    assert fake.uniform_calls == 1

    _install_cached_gl_location_lookups(fake)
    assert fake.glGetAttribLocation(11, "a_position") == 7
    assert fake.glGetUniformLocation(11, b"u_mvp") == 13
    assert fake.attrib_calls == 1
    assert fake.uniform_calls == 1


def test_static_mesh_transform_reuses_bound_topology() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import _set_gl_mesh_item_static_transform

    class _FakeMeshData:
        def __init__(self, *, vertexes, faces, faceColors=None):
            self.vertexes = np.asarray(vertexes, dtype=np.float32)
            self.faces = np.asarray(faces, dtype=np.uint32)

    class _FakeGL:
        MeshData = _FakeMeshData

    class _FakeMeshItem:
        def __init__(self) -> None:
            self.opts = {}
            self.visible = False
            self.transforms = []
            self.set_mesh_calls = 0
            self.visible_calls = 0

        def setMeshData(self, *, meshdata):
            self.opts["meshdata"] = meshdata
            self.set_mesh_calls += 1

        def setTransform(self, transform):
            self.transforms.append(transform)

        def setVisible(self, visible: bool):
            self.visible = bool(visible)
            self.visible_calls += 1

    base_verts = np.asarray(
        [
            [0.0, -0.5, 0.0],
            [1.0, -0.5, 0.0],
            [0.0, 0.5, 0.0],
        ],
        dtype=float,
    )
    faces = np.asarray([[0, 1, 2]], dtype=np.int32)
    tr0 = np.eye(4, dtype=float)
    tr1 = np.asarray(
        [
            [2.0, 0.0, 0.0, 1.0],
            [0.0, 3.0, 0.0, 2.0],
            [0.0, 0.0, 4.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )

    item = _FakeMeshItem()
    orig_gl = appmod.gl
    appmod.gl = _FakeGL()
    try:
        assert _set_gl_mesh_item_static_transform(
            item,
            mesh_key="unit-test-segment",
            base_vertices_xyz=base_verts,
            faces_ijk=faces,
            transform=tr0,
        )
        first_meshdata = item.opts["meshdata"]
        assert item.set_mesh_calls == 1
        assert item.visible
        assert item.visible_calls == 1

        assert _set_gl_mesh_item_static_transform(
            item,
            mesh_key="unit-test-segment",
            base_vertices_xyz=base_verts,
            faces_ijk=faces.copy(),
            transform=tr1,
        )
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert len(item.transforms) == 2
        assert item.visible_calls == 1

        assert _set_gl_mesh_item_static_transform(
            item,
            mesh_key="unit-test-segment",
            base_vertices_xyz=base_verts,
            faces_ijk=faces,
            transform=tr1.copy(),
        )
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert len(item.transforms) == 2
        assert item.visible_calls == 1

        tr1_jitter = tr1.copy()
        tr1_jitter[0, 3] += 5e-7
        assert _set_gl_mesh_item_static_transform(
            item,
            mesh_key="unit-test-segment",
            base_vertices_xyz=base_verts,
            faces_ijk=faces,
            transform=tr1_jitter,
        )
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert len(item.transforms) == 2
        assert item.visible_calls == 1

        tr1_real_move = tr1.copy()
        tr1_real_move[0, 3] += 2e-5
        assert _set_gl_mesh_item_static_transform(
            item,
            mesh_key="unit-test-segment",
            base_vertices_xyz=base_verts,
            faces_ijk=faces,
            transform=tr1_real_move,
        )
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert len(item.transforms) == 3
        assert item.visible_calls == 1

        assert _set_gl_mesh_item_static_transform(
            item,
            mesh_key="unit-test-segment",
            base_vertices_xyz=np.asarray([[np.nan, 0.0, 0.0]], dtype=float),
            faces_ijk=np.asarray([[0, 0, 0]], dtype=np.int32),
            transform=tr0.copy(),
        )
        assert item.opts["meshdata"] is first_meshdata
        assert item.set_mesh_calls == 1
        assert len(item.transforms) == 4
    finally:
        appmod.gl = orig_gl


def test_mesh_hot_path_uses_cached_unit_arrays_without_extra_rewrapping() -> None:
    root = Path(__file__).resolve().parents[1]
    app_src = (root / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
    assert 'base_vertices_xyz=self._unit_cyl_y_vertices' in app_src
    assert 'faces_ijk=self._unit_cyl_faces' in app_src
    assert 'base_vertices_xyz=self._unit_disc_y_vertices' in app_src
    assert 'faces_ijk=self._unit_disc_faces' in app_src
    assert 'item,\n                verts_xyz,\n                faces_ijk,' in app_src
    assert "def _segment_endpoints_transform3d_components(" in app_src
    assert "return _segment_endpoints_transform3d_components(" in app_src
    assert "pg.Transform3D(transform_arr)" in app_src
    assert "pg.Transform3D(transform_arr.tolist())" not in app_src
    assert "def _transform_matrices_equivalent_for_render(" in app_src
    assert "_transform_matrices_equivalent_for_render(prev_transform, transform_arr)" in app_src
    assert "def _normalize_face_colors_u8(" in app_src
    assert "face_cols = _normalize_face_colors_u8(face_colors_rgba_u8, expected_faces_n=int(faces.shape[0]))" in app_src
    assert 'topology_key=("chassis-box"' in app_src
    assert 'topology_key=(' in app_src
    assert '"wheel-tire"' in app_src
    assert 'topology_key=("road-mesh", int(n_long), int(n_lat))' in app_src


def test_request_gl_view_redraw_stays_async_even_if_view_exposes_sync_flag() -> None:
    from pneumo_solver_ui.desktop_animator.app import _request_gl_view_redraw

    class _FakeViewport:
        def __init__(self) -> None:
            self.update_calls = 0
            self.repaint_calls = 0

        def update(self):
            self.update_calls += 1

        def repaint(self):
            self.repaint_calls += 1

    class _FakeView:
        def __init__(self, *, force_sync: bool) -> None:
            self._anim_present_pending = False
            self._anim_force_sync_present = bool(force_sync)
            self.update_calls = 0
            self.repaint_calls = 0
            self._viewport = _FakeViewport()

        def update(self):
            self.update_calls += 1

        def repaint(self):
            self.repaint_calls += 1

        def viewport(self):
            return self._viewport

    async_view = _FakeView(force_sync=False)
    _request_gl_view_redraw(async_view)
    assert async_view._anim_present_pending
    assert async_view.update_calls == 1
    assert async_view.repaint_calls == 0
    assert async_view._viewport.update_calls == 1

    sync_view = _FakeView(force_sync=True)
    _request_gl_view_redraw(sync_view)
    assert sync_view._anim_present_pending
    assert sync_view.update_calls == 1
    assert sync_view.repaint_calls == 0
    assert sync_view._viewport.update_calls == 1


def test_wheel_tire_face_colors_local_reuses_triangle_gather_without_changing_colors() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win.geom = SimpleNamespace(wheel_radius=0.52, wheel_width=0.28)
    win._tire_force_visual_max_n = 4500.0
    win._wheel_face_gather_cache = {}

    verts_local = np.asarray(
        [
            [0.52, -0.14, 0.00],
            [0.00, -0.14, 0.52],
            [-0.52, -0.14, 0.00],
            [0.00, -0.14, -0.52],
            [0.52, 0.14, 0.00],
            [0.00, 0.14, 0.52],
            [-0.52, 0.14, 0.00],
            [0.00, 0.14, -0.52],
        ],
        dtype=float,
    )
    faces = np.asarray(
        [
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int32,
    )

    colors0 = win._wheel_tire_face_colors_local(
        verts_local,
        faces,
        tire_force_n=1500.0,
        wheel_gap_m=0.01,
        speed_m_s=8.0,
        in_air=False,
        spin_phase_rad=0.2,
    )
    cache_after_first = dict(win._wheel_face_gather_cache)
    colors1 = win._wheel_tire_face_colors_local(
        verts_local * np.asarray([1.0, 1.0, 0.98], dtype=float).reshape(1, 3),
        faces,
        tire_force_n=1500.0,
        wheel_gap_m=0.01,
        speed_m_s=8.0,
        in_air=False,
        spin_phase_rad=0.2,
    )

    assert len(cache_after_first) == 1
    assert len(win._wheel_face_gather_cache) == 1
    np.testing.assert_equal(colors0.shape, colors1.shape)


def test_deformed_wheel_vertices_reuse_cached_static_deform_basis() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    win = Car3DWidget.__new__(Car3DWidget)
    win.geom = SimpleNamespace(wheel_radius=0.52, wheel_width=0.28)
    win._tire_force_visual_max_n = 4500.0
    win._wheel_deform_basis_cache = {}

    base = np.asarray(
        [
            [0.52, -0.14, 0.00],
            [0.00, -0.14, 0.52],
            [-0.52, -0.14, 0.00],
            [0.00, -0.14, -0.52],
            [0.52, 0.14, 0.00],
            [0.00, 0.14, 0.52],
            [-0.52, 0.14, 0.00],
            [0.00, 0.14, -0.52],
        ],
        dtype=float,
    )

    verts0 = win._deformed_wheel_vertices(
        tire_force_n=1600.0,
        tire_compression_m=0.012,
        wheel_gap_m=0.006,
        in_air=False,
        speed_m_s=9.0,
        base_vertices_xyz=base,
    )
    basis0 = next(iter(win._wheel_deform_basis_cache.values()))
    verts1 = win._deformed_wheel_vertices(
        tire_force_n=2200.0,
        tire_compression_m=0.018,
        wheel_gap_m=0.002,
        in_air=False,
        speed_m_s=14.0,
        base_vertices_xyz=base,
    )
    basis1 = next(iter(win._wheel_deform_basis_cache.values()))

    assert verts0 is not None
    assert verts1 is not None
    assert len(win._wheel_deform_basis_cache) == 1
    assert basis0 is basis1
    np.testing.assert_equal(verts0.shape, base.shape)
    np.testing.assert_equal(verts1.shape, base.shape)


def test_sample_point_local_matches_playback_lerp_point_row_for_dense_solver_rows() -> None:
    from pneumo_solver_ui.desktop_animator.app import _sample_point_local
    from pneumo_solver_ui.desktop_animator.playback_sampling import lerp_point_row

    rows = np.asarray(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ],
        dtype=float,
    )
    sampled = _sample_point_local(rows, i0=0, i1=1, alpha=0.25)
    ref = lerp_point_row(rows, i0=0, i1=1, alpha=0.25)
    assert sampled is not None
    assert ref is not None
    np.testing.assert_allclose(sampled, ref, rtol=0.0, atol=1e-12)


def test_wishbone_plate_mesh_reuses_static_faces_topology() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    verts0, faces0 = Car3DWidget._wishbone_plate_mesh(
        np.asarray([0.0, 0.0, 0.0], dtype=float),
        np.asarray([0.0, 0.2, 0.0], dtype=float),
        np.asarray([0.6, 0.0, 0.1], dtype=float),
        np.asarray([0.6, 0.2, 0.1], dtype=float),
        thickness_m=0.03,
    )
    verts1, faces1 = Car3DWidget._wishbone_plate_mesh(
        np.asarray([0.0, 0.0, 0.1], dtype=float),
        np.asarray([0.0, 0.2, 0.1], dtype=float),
        np.asarray([0.6, 0.0, 0.2], dtype=float),
        np.asarray([0.6, 0.2, 0.2], dtype=float),
        thickness_m=0.03,
    )
    assert verts0 is not None
    assert verts1 is not None
    assert faces0 is faces1
    assert faces0 is not None
    assert faces0.flags.writeable is False


def test_structural_wire_overlays_are_enabled_as_xray_contours_for_validator_view() -> None:
    assert "show_solver_wire_overlay = True" in SRC
    assert "_set_line_item_pos(self._arm_lines, pos)" in SRC
    assert "_set_line_item_pos(self._cyl1_lines, pos)" in SRC
    assert "_set_line_item_pos(self._cyl2_lines, pos)" in SRC
    assert 'self._arm_lines.setGLOptions("additive")' in SRC


def test_hidden_gl_items_are_not_reinvalidated_or_recleared_every_frame() -> None:
    assert 'if bool(getattr(item, "_animator_mesh_invalidated", False)):' in SRC
    assert 'setattr(item, "_animator_mesh_invalidated", False)' in SRC
    assert 'setattr(item, "_animator_mesh_invalidated", True)' in SRC
    assert 'if getattr(item, "_animator_static_mesh_key", None) is not None:' in SRC
    assert 'if bool(getattr(item, "_animator_line_empty", False)):' in SRC
    assert 'setattr(item, "_animator_line_empty", True)' in SRC
    assert 'setattr(item, "_animator_line_empty", False)' in SRC
    assert '_set_gl_mesh_item_static_transform(' in SRC


def test_invalidate_mesh_resets_fast_mesh_reuse_state() -> None:
    import pneumo_solver_ui.desktop_animator.app as appmod
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget, _update_gl_mesh_item_fast

    class _FakeMeshData:
        def __init__(self, *, vertexes, faces, faceColors=None):
            self._vertexes = np.asarray(vertexes, dtype=np.float32)
            self._faces = np.asarray(faces, dtype=np.uint32)
            self._face_colors = None if faceColors is None else np.asarray(faceColors)

        def setVertexes(self, verts, indexed=None, resetNormals=True):
            self._vertexes = np.asarray(verts, dtype=np.float32)

        def setFaceColors(self, colors, indexed=None):
            self._face_colors = np.asarray(colors)

    class _FakeGL:
        MeshData = _FakeMeshData

    class _FakeMeshItem:
        def __init__(self) -> None:
            self.opts = {"computeNormals": False}
            self.visible = False

        def setMeshData(self, *, meshdata):
            self.opts["meshdata"] = meshdata

        def setVisible(self, visible: bool):
            self.visible = bool(visible)

    item = _FakeMeshItem()
    verts = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    faces = np.asarray([[0, 1, 2]], dtype=np.int32)

    orig_gl = appmod.gl
    appmod.gl = _FakeGL()
    try:
        assert _update_gl_mesh_item_fast(item, verts, faces)
        assert getattr(item, "_animator_faces_signature", None) is not None
        assert getattr(item, "_animator_mesh_invalidated", True) is False
        Car3DWidget._invalidate_mesh(item)
        assert getattr(item, "_animator_faces_signature", "sentinel") is None
        assert getattr(item, "_animator_face_colors_enabled", True) is False
        assert getattr(item, "_animator_mesh_invalidated", False) is True
        assert not item.visible
    finally:
        appmod.gl = orig_gl


def test_invalidate_mesh_preserves_static_topology_and_only_hides_item() -> None:
    from pneumo_solver_ui.desktop_animator.app import Car3DWidget

    class _FakeMeshItem:
        def __init__(self) -> None:
            self.visible = True
            self.reset_calls = 0
            self.mesh_calls = 0
            self._animator_static_mesh_key = "unit_cylinder_y"

        def resetTransform(self):
            self.reset_calls += 1

        def setMeshData(self, *, meshdata):
            self.mesh_calls += 1

        def setVisible(self, visible: bool):
            self.visible = bool(visible)

    item = _FakeMeshItem()
    Car3DWidget._invalidate_mesh(item)
    assert item.reset_calls == 1
    assert item.mesh_calls == 0
    assert getattr(item, "_animator_mesh_invalidated", False) is True
    assert not item.visible


def test_many_docks_mode_uses_lighter_overlays_but_keeps_aux_panels_live() -> None:
    assert "def _requires_dense_validation_budget(source_dt_s: float | None, *, visible_aux: int) -> bool:" in SRC
    assert "def _update_playback_underrun_score(" in SRC
    assert "self._aux_play_fast_fps: float = 24.0" in SRC
    assert "self._aux_play_slow_fps: float = 12.0" in SRC
    assert "self._aux_many_fast_fps: float = 18.0" in SRC
    assert "self._aux_many_slow_fps: float = 10.0" in SRC
    assert "self._many_visible_threshold: int = 12" in SRC
    assert 'many_visible_budget = (bool(playing) or interactive_scrub) and visible_aux >= int(getattr(self, "_many_visible_threshold", 10))' in SRC
    assert 'dense_validation_budget = (bool(playing) or interactive_scrub) and _requires_dense_validation_budget(' in SRC
    assert 'runtime_validation_budget = bool(playing) and bool(getattr(self, "_runtime_validation_budget_active", False))' in SRC
    assert "motion_validation_budget = bool(dense_validation_budget or runtime_validation_budget)" in SRC
    assert "perf_budget_active = bool(many_visible_budget or dense_validation_budget)" not in SRC
    assert "perf_budget_active = bool(many_visible_budget or motion_validation_budget)" in SRC


def test_neutral_scene_grade_skips_wheel_face_regrading_in_hot_path() -> None:
    assert "scene_grade_base_identity = self._scene_grade_is_identity(" in SRC
    assert "wheel_face_colors = self._wheel_tire_face_colors_from_deform_basis(" in SRC
    assert "if not bool(scene_grade_base_identity):" in SRC
    assert "K @ K" not in SRC
    assert "_scaled_basis_transform3d(" in SRC
    assert "def _scene_grade_rgba_scalar(" in SRC
    assert "self._playback_perf_mode_active: bool = False" in SRC
    assert "self._runtime_validation_budget_active: bool = False" in SRC
    assert "def _visible_aux_dock_count(self) -> int:" in SRC
    assert "def _apply_playback_perf_mode(self, enabled: bool) -> None:" in SRC
    assert "self._apply_playback_perf_mode(perf_budget_active)" not in SRC
    assert "self._apply_playback_perf_mode(False)" in SRC
    assert "def set_runtime_validation_budget(self, enabled: bool) -> None:" in SRC
    assert 'if bool(validation_perf_mode) or not bool(getattr(self, "_enable_scene_grade", False)):' in SRC


def test_visible_fast_and_slow_groups_are_refreshed_as_groups() -> None:
    assert "always_play_panels: List[Tuple[str, Any, str]] = []" in SRC
    assert "for entry in fast_visible:" in SRC
    assert "slow_entries = slow_visible" in SRC
    assert "for entry in slow_entries:" in SRC
    assert "_call_panel(entry)" in SRC
    assert "elif bool(playing):" in SRC
    assert '("dock_front", self.axleF, "update_frame")' in SRC
    assert '("dock_rear", self.axleR, "update_frame")' in SRC
    assert '("dock_left", self.sideL, "update_frame")' in SRC
    assert '("dock_right", self.sideR, "update_frame")' in SRC
    assert 'if not motion_validation_budget:' in SRC
    assert '("dock_telemetry", self.telemetry, "update_frame")' in SRC
    assert '("dock_corner_quick", getattr(self, "telemetry_corner_quick", None), "update_frame")' in SRC
    assert '("dock_road_profile", getattr(self, "telemetry_road_profile", None), "update_frame")' in SRC
    assert 'if not perf_budget_active:' in SRC
    assert 'always_play_panels.append(' in SRC
    assert 'always_play_panels.extend(' in SRC
    assert '("dock_heatmap", getattr(self, "telemetry_heatmap", None), "update_frame")' in SRC
    assert '("dock_corner_table", getattr(self, "telemetry_corner_table", None), "update_frame")' in SRC
    assert '("dock_pressures", getattr(self, "telemetry_press_panel", None), "update_frame")' in SRC
    assert '("dock_flows", getattr(self, "telemetry_flow_panel", None), "update_frame")' in SRC
    assert '("dock_valves", getattr(self, "telemetry_valve_panel", None), "update_frame")' in SRC
    assert 'if perf_budget_active:' in SRC
    assert 'slow_panels.extend(' in SRC
    assert "always_play_visible = _visible_panel_entries(always_play_panels)" in SRC
    assert "if bool(playing):" in SRC
    assert "for entry in always_play_visible:" in SRC
    assert 'if self._dock_is_exposed("dock_timeline") and (bool(playing) or interactive_scrub or fast_due):' in SRC
    assert 'if interactive_scrub and self._dock_is_exposed("dock_telemetry"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and pressure_panel is not None and self._dock_is_exposed("dock_pressures"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and flow_panel is not None and self._dock_is_exposed("dock_flows"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and valve_panel is not None and self._dock_is_exposed("dock_valves"):' in SRC
    assert 'if interactive_scrub and (not many_visible_budget) and slow_due and corner_table_panel is not None and self._dock_is_exposed("dock_corner_table"):' in SRC
    assert 'if interactive_scrub and heatmap_panel is not None and self._dock_is_exposed("dock_heatmap"):' in SRC
    assert 'if interactive_scrub and corner_quick_panel is not None and self._dock_is_exposed("dock_corner_quick"):' in SRC
    assert 'if interactive_scrub and road_profile_panel is not None and self._dock_is_exposed("dock_road_profile"):' in SRC
    assert '"dock_multifactor",' in SRC
    assert '("dock_multifactor", getattr(self, "telemetry_multifactor", None), "update_frame"),' in SRC
    assert 'if interactive_scrub and multifactor_panel is not None and self._dock_is_exposed("dock_multifactor"):' not in SRC
    assert "self.timeline.set_playhead_time(self._playback_sample_t_s, idx=i)" in SRC
    assert "pressure_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "flow_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "valve_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "corner_table_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "heatmap_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "corner_quick_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert "road_profile_panel.update_frame(b, i, sample_t=self._playback_sample_t_s)" in SRC
    assert 'if interactive_scrub and self._dock_is_exposed("dock_trends"):' in SRC
    assert 'if bool(playing) and (not motion_validation_budget) and self._dock_is_exposed("dock_trends"):' in SRC
    assert "self.trends.update_frame(i, sample_t=self._playback_sample_t_s)" in SRC
    assert 'heatmap_panel = getattr(self, "telemetry_heatmap", None)' in SRC
    assert 'corner_quick_panel = getattr(self, "telemetry_corner_quick", None)' in SRC
    assert 'corner_table_panel = getattr(self, "telemetry_corner_table", None)' in SRC
    assert 'pressure_panel = getattr(self, "telemetry_press_panel", None)' in SRC
    assert 'flow_panel = getattr(self, "telemetry_flow_panel", None)' in SRC
    assert 'valve_panel = getattr(self, "telemetry_valve_panel", None)' in SRC
    assert 'road_profile_panel = getattr(self, "telemetry_road_profile", None)' in SRC
    assert "sample_t_panels = (" in SRC
    assert "sample_t=self._playback_sample_t_s," in SRC
    assert 'if self._dock_is_exposed("dock_timeline") and not interactive_scrub:' not in SRC
    assert 'if self._dock_is_exposed("dock_trends") and (not interactive_scrub) and ((not bool(playing)) or motion_validation_budget):' in SRC


def test_runtime_underrun_warning_path_throttles_secondary_panels_explicitly() -> None:
    assert "def _resolve_runtime_validation_budget_state(" in SRC
    assert 'self._playback_underrun_score, runtime_budget_active = _update_playback_underrun_score(' in SRC
    assert 'self._set_runtime_validation_budget(' in SRC
    assert 'active = _resolve_runtime_validation_budget_state(' in SRC
    assert 'code="playback_runtime_validation_budget"' in SRC
    assert 'VALIDATION WARN: runtime cadence underrun, secondary panels throttled | ' in SRC
    assert 'cursor_f = float(cursor_f + max(0.05, float(self._speed)))' not in SRC
    assert 'cursor_f, sample_t_prepared = _advance_prepared_playback_cursor_limited(' in SRC


def test_views_have_playback_perf_mode_and_hide_expensive_overlays() -> None:
    assert SRC.count("def set_playback_perf_mode(self, enabled: bool) -> None:") >= 3
    assert "def _request_gl_view_redraw(view: Any) -> None:" in SRC
    assert "def _set_gl_mesh_compute_normals(item: Any, enabled: bool) -> None:" in SRC
    assert "def _update_gl_mesh_item_fast(" in SRC
    assert "def _validation_scene_grade_profile() -> dict[str, float]:" in SRC
    assert "def _effective_scene_grade_profile(" in SRC
    assert "def _scene_grade_is_identity(" in SRC
    assert 'self._scene_scalar_visual_state[f"{key_prefix}:{suffix}"] = float(neutral[suffix])' in SRC
    assert "eff_show_labels = bool(self.show_labels) and not bool(self._playback_perf_mode)" in SRC
    assert "eff_show_text = bool(self.show_text) and not bool(self._playback_perf_mode)" in SRC
    assert "eff_show_seg_markers = bool(self.show_seg_markers) and not bool(self._playback_perf_mode)" in SRC
    assert "validation_perf_mode = bool(self._playback_active) and bool(self._playback_perf_mode)" in SRC
    assert "rich_suspension_fx = not bool(validation_perf_mode)" in SRC
    assert 'self._show_wheel_hardware = False' in SRC
    assert 'self._show_cylinder_chrome = False' in SRC
    assert 'self._enable_scene_grade = False' in SRC
    assert 'self._show_environment_fx = False' in SRC
    assert 'rich_wheel_fx = bool(getattr(self, "_show_wheel_hardware", False)) and not bool(validation_perf_mode)' in SRC
    assert 'rich_cylinder_fx = bool(getattr(self, "_show_cylinder_chrome", False)) and rich_suspension_fx' in SRC
    assert 'show_cylinder_detail_lines = bool(getattr(self, "_show_cylinder_chrome", False))' in SRC
    assert "scene_grade_base = self._effective_scene_grade_profile(" in SRC
    assert "cap_scene_grade = self._effective_scene_grade_profile(" in SRC
    assert "rod_scene_grade = self._effective_scene_grade_profile(" in SRC
    assert "scene_grade = self._effective_scene_grade_profile(" in SRC
    assert "for bloom_item in self._cyl_bloom_card_meshes:" in SRC
    assert "for glow_item in self._spring_glow_lines:" in SRC
    assert "for glint_item in self._cyl_glass_glint_lines:" in SRC
    assert "for caustic_item in self._cyl_glass_caustic_lines:" in SRC
    assert "for rim_item in self._wheel_rim_meshes:" in SRC
    assert "for rotor_item in self._wheel_brake_rotor_meshes:" in SRC
    assert "for caliper_item in self._wheel_brake_caliper_meshes:" in SRC
    assert "for hub_item in self._wheel_hub_meshes:" in SRC
    assert "for glow_item in self._wheel_spin_glow_lines:" in SRC
    assert "for glint_item in self._wheel_crown_glint_lines:" in SRC
    assert "for streak_item in self._wheel_rotor_streak_lines:" in SRC
    assert "def _should_render_contact_patch_mesh(" in SRC
    assert "return False" in SRC
    assert "show_contact_patch_mesh = _should_render_contact_patch_mesh(" in SRC
    assert "playback_active=bool(self._playback_active)," in SRC
    assert "need_contact_patch_mesh = bool(self._contact_patch_mesh is not None and show_contact_patch_mesh)" in SRC
    assert "meshdata.setVertexes(verts, resetNormals=bool(opts.get(\"computeNormals\", True)))" in SRC
    assert "item.meshDataChanged()" in SRC
    assert 'setattr(item, "_animator_faces_signature", None)' in SRC
    assert 'setattr(item, "_animator_face_colors_enabled", False)' in SRC
    assert "_set_gl_mesh_compute_normals(self._road_mesh, False)" in SRC
    assert "for wheel_item in self._wheel_meshes:" in SRC
    assert "_set_gl_mesh_compute_normals(wheel_item, not enabled)" in SRC
    assert 'w.setGLOptions("translucent")' in SRC
    assert "smooth=False," in SRC
    assert "shader=None," in SRC
    assert 'drawEdges=True,' in SRC
    assert 'show_solver_wire_overlay = True' in SRC
    assert 'self._arm_lines.setGLOptions("additive")' in SRC
    assert 'self._cyl1_lines.setGLOptions("additive")' in SRC
    assert 'self._cyl2_lines.setGLOptions("additive")' in SRC
    assert "_set_gl_mesh_compute_normals(self._chassis_mesh, False)" in SRC
    assert "_set_gl_mesh_compute_normals(w, False)" in SRC
    assert "_set_gl_mesh_compute_normals(lower_arm, False)" in SRC
    assert "_set_gl_mesh_compute_normals(upper_arm, False)" in SRC
    assert "_set_gl_mesh_compute_normals(spring, False)" in SRC
    assert "_set_gl_mesh_compute_normals(spring_seat, False)" in SRC
    assert "if not _update_gl_mesh_item_fast(" in SRC
    assert "self._wheel_perf_base_vertices: Optional[np.ndarray] = None" in SRC
    assert "self._wheel_perf_faces: Optional[np.ndarray] = None" in SRC
    assert "md_perf = gl.MeshData.cylinder(rows=8, cols=16, radius=[wheel_r, wheel_r], length=wheel_w)" in SRC
    assert "wheel_base_vertices = self._wheel_perf_base_vertices" in SRC
    assert "wheel_faces = self._wheel_perf_faces" in SRC
    assert '"samples_per_turn": 6 if bool(validation_perf_mode) else 16,' in SRC
    assert '"tube_sides": 5 if bool(validation_perf_mode) else 10,' in SRC
    assert "seat_segments = 14 if bool(validation_perf_mode) else 26" in SRC
    assert "min_long = int(max(72, min(self._road_pts, 96)))" in SRC
    assert "max_long = 140" in SRC
    assert "min_lat = 4" in SRC
    assert "max_lat = 5" in SRC
    assert 'rich_road_fx = bool(' in SRC
    assert 'and bool(getattr(self, "_show_environment_fx", False))' in SRC
    assert "if rich_suspension_fx and spring_glow is not None and spring_path is not None:" in SRC
    assert "if rich_cylinder_fx:" in SRC
    assert "if show_cylinder_detail_lines:" in SRC
    assert "elif cyl_mesh_idx < len(self._cyl_piston_ring_lines):" in SRC
    assert "elif cyl_mesh_idx < len(self._cyl_rod_core_lines):" in SRC
    assert "if rich_wheel_fx:" in SRC
    assert "self._invalidate_mesh(cap_bloom_item)" in SRC
    assert "self._invalidate_mesh(rod_bloom_item)" in SRC
    assert "_set_line_item_pos(cap_glint_item, None)" in SRC
    assert "_set_line_item_pos(rod_glint_item, None)" in SRC
    assert "_set_line_item_pos(cap_caustic_item, None)" in SRC
    assert "_set_line_item_pos(rod_caustic_item, None)" in SRC
    assert "self._invalidate_mesh(rim_item)" in SRC
    assert "self._invalidate_mesh(rotor_item)" in SRC
    assert "self._invalidate_mesh(caliper_item)" in SRC
    assert "self._invalidate_mesh(hub_item)" in SRC
    assert "_set_line_item_pos(spin_glow_item, None)" in SRC
    assert "_set_line_item_pos(crown_glint_item, None)" in SRC
    assert "_set_line_item_pos(rotor_streak_item, None)" in SRC
    assert "_request_gl_view_redraw(self.view)" in SRC
