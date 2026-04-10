from __future__ import annotations

import math
from pathlib import Path

from pneumo_solver_ui.ring_visuals import (
    build_ring_visual_payload_from_spec,
    build_segment_ranges_from_progress,
    embed_path_payload_on_ring,
)

ROOT = Path(__file__).resolve().parents[1]


def test_ring_visual_payload_contains_segments_and_curvature_heatmap() -> None:
    spec = {
        "schema": "ring_v2",
        "segments": [
            {"name": "S1", "drive_mode": "STRAIGHT", "duration_s": 5.0, "speed_kph": 40.0, "road": {"mode": "ISO8608", "iso_class": "C"}},
            {"name": "S2", "drive_mode": "TURN_LEFT", "duration_s": 4.0, "speed_kph": 40.0, "turn_radius_m": 60.0, "road": {"mode": "SINE", "aL_mm": 100.0, "aR_mm": 100.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0}},
        ],
    }
    ring = build_ring_visual_payload_from_spec(spec, track_m=1.0, wheel_width_m=0.22, seed=0)
    assert ring is not None
    assert ring["mode"] == "ring_closed_circle"
    assert len(ring["segments"]) == 2
    assert ring["segments"][0]["turn_direction"] == "STRAIGHT"
    assert ring["segments"][0]["turn_direction_label"] == "Прямо"
    assert ring["segments"][0]["drive_mode"] == "STRAIGHT"
    assert ring["segments"][0]["road_mode"] == "ISO8608"
    assert ring["segments"][0]["road_mode_label"] == "ISO 8608 (шероховатость)"
    assert ring["segments"][1]["turn_direction"] == "LEFT"
    assert ring["segments"][1]["turn_direction_label"] == "Поворот влево"
    assert ring["segments"][1]["drive_mode"] == "TURN_LEFT"
    assert ring["segments"][1]["turn_radius_m"] == 60.0
    assert ring["segments"][1]["road_mode"] == "SINE"
    assert ring["segments"][1]["road_mode_label"] == "Синус L/R"
    assert max(ring["curvature_abs_m_inv"]) > 0.0
    assert ring["road_width_m"] > 1.0


def test_ring_visual_payload_keeps_canonical_turn_direction_even_for_legacy_accel_segments() -> None:
    spec = {
        "schema": "ring_v2",
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "drive_mode": "ACCEL",
                "duration_s": 3.0,
                "v_end_kph": 35.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
            {
                "name": "S2",
                "drive_mode": "BRAKE",
                "duration_s": 2.0,
                "v_end_kph": 20.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
        ],
    }

    ring = build_ring_visual_payload_from_spec(spec, track_m=1.0, wheel_width_m=0.22, seed=0)

    assert ring is not None
    assert ring["segments"][0]["drive_mode"] == "ACCEL"
    assert ring["segments"][0]["turn_direction"] == "STRAIGHT"
    assert ring["segments"][0]["turn_direction_label"] == "Прямо"
    assert ring["segments"][0]["speed_start_kph"] == 20.0
    assert ring["segments"][0]["speed_end_kph"] == 35.0


def test_ring_visual_payload_respects_authored_strict_exact_closure_policy() -> None:
    spec = {
        "schema": "ring_v2",
        "closure_policy": "strict_exact",
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 20.0,
                "road": {"mode": "SINE", "aL_mm": 10.0, "aR_mm": 0.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0},
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 20.0,
                "road": {"mode": "SINE", "aL_mm": 0.0, "aR_mm": 0.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0},
            },
        ],
    }

    ring = build_ring_visual_payload_from_spec(spec, track_m=1.0, wheel_width_m=0.22, seed=0)

    assert ring is not None
    assert ring["closure_policy"] == "strict_exact"
    assert ring["source_closure_policy"] == "strict_exact"
    assert ring["meta"]["closure_policy"] == "strict_exact"


def test_ring_visual_payload_falls_back_to_source_spec_road_mode_when_summary_row_omits_it(monkeypatch) -> None:
    def _fake_tracks(spec, *, dx_m, seed):
        return {
            "x_m": [0.0, 5.0, 10.0, 15.0, 20.0],
            "zL_m": [0.0, 0.0, 0.0, 0.0, 0.0],
            "zR_m": [0.0, 0.0, 0.0, 0.0, 0.0],
            "meta": {"L_total_m": 20.0},
        }

    def _fake_rows(spec, tracks):
        return [
            {"seg_idx": 1, "name": "S1", "x_start_m": 0.0, "x_end_m": 10.0, "speed_start_kph": 30.0, "speed_end_kph": 30.0},
            {"seg_idx": 2, "name": "S2", "x_start_m": 10.0, "x_end_m": 20.0, "speed_start_kph": 30.0, "speed_end_kph": 30.0},
        ]

    monkeypatch.setattr("pneumo_solver_ui.ring_visuals.generate_ring_tracks", _fake_tracks)
    monkeypatch.setattr("pneumo_solver_ui.ring_visuals.summarize_ring_track_segments", _fake_rows)

    spec = {
        "schema": "ring_v2",
        "segments": [
            {"name": "S1", "turn_direction": "STRAIGHT", "road": {"mode": "ISO8608"}},
            {"name": "S2", "turn_direction": "LEFT", "road": {"mode": "SINE"}, "turn_radius_m": 40.0},
        ],
    }

    ring = build_ring_visual_payload_from_spec(spec, track_m=1.0, wheel_width_m=0.22, seed=0)

    assert ring is not None
    assert ring["segments"][0]["road_mode"] == "ISO8608"
    assert ring["segments"][0]["road_mode_label"] == "ISO 8608 (шероховатость)"
    assert ring["segments"][1]["road_mode"] == "SINE"
    assert ring["segments"][1]["road_mode_label"] == "Синус L/R"


def test_ring_visual_payload_falls_back_to_source_and_inherited_speed_start_when_summary_row_omits_it(monkeypatch) -> None:
    def _fake_tracks(spec, *, dx_m, seed):
        return {
            "x_m": [0.0, 5.0, 10.0, 15.0, 20.0],
            "zL_m": [0.0, 0.0, 0.0, 0.0, 0.0],
            "zR_m": [0.0, 0.0, 0.0, 0.0, 0.0],
            "meta": {"L_total_m": 20.0},
        }

    def _fake_rows(spec, tracks):
        return [
            {"seg_idx": 1, "name": "S1", "x_start_m": 0.0, "x_end_m": 10.0, "speed_end_kph": 45.0},
            {"seg_idx": 2, "name": "S2", "x_start_m": 10.0, "x_end_m": 20.0, "speed_end_kph": 55.0},
        ]

    monkeypatch.setattr("pneumo_solver_ui.ring_visuals.generate_ring_tracks", _fake_tracks)
    monkeypatch.setattr("pneumo_solver_ui.ring_visuals.summarize_ring_track_segments", _fake_rows)

    spec = {
        "schema": "ring_v2",
        "v0_kph": 25.0,
        "segments": [
            {"name": "S1", "turn_direction": "STRAIGHT", "speed_start_kph": 30.0, "speed_end_kph": 45.0, "road": {"mode": "ISO8608"}},
            {"name": "S2", "turn_direction": "LEFT", "speed_end_kph": 55.0, "turn_radius_m": 40.0, "road": {"mode": "SINE"}},
        ],
    }

    ring = build_ring_visual_payload_from_spec(spec, track_m=1.0, wheel_width_m=0.22, seed=0)

    assert ring is not None
    assert ring["segments"][0]["speed_start_kph"] == 30.0
    assert ring["segments"][0]["speed_end_kph"] == 45.0
    assert ring["segments"][1]["speed_start_kph"] == 45.0
    assert ring["segments"][1]["speed_end_kph"] == 55.0


def test_ring_visual_payload_falls_back_to_source_name_drive_mode_and_turn_radius_when_summary_row_omits_them(monkeypatch) -> None:
    def _fake_tracks(spec, *, dx_m, seed):
        return {
            "x_m": [0.0, 5.0, 10.0, 15.0, 20.0],
            "zL_m": [0.0, 0.0, 0.0, 0.0, 0.0],
            "zR_m": [0.0, 0.0, 0.0, 0.0, 0.0],
            "meta": {"L_total_m": 20.0},
        }

    def _fake_rows(spec, tracks):
        return [
            {"seg_idx": 1, "x_start_m": 0.0, "x_end_m": 10.0, "speed_start_kph": 20.0, "speed_end_kph": 20.0},
            {"seg_idx": 2, "x_start_m": 10.0, "x_end_m": 20.0, "speed_start_kph": 20.0, "speed_end_kph": 20.0},
        ]

    monkeypatch.setattr("pneumo_solver_ui.ring_visuals.generate_ring_tracks", _fake_tracks)
    monkeypatch.setattr("pneumo_solver_ui.ring_visuals.summarize_ring_track_segments", _fake_rows)

    spec = {
        "schema": "ring_v2",
        "segments": [
            {"name": "Straight authored", "turn_direction": "STRAIGHT", "speed_end_kph": 20.0, "road": {"mode": "ISO8608"}},
            {"name": "Left authored", "turn_direction": "LEFT", "turn_radius_m": 35.0, "speed_end_kph": 20.0, "road": {"mode": "SINE"}},
        ],
    }

    ring = build_ring_visual_payload_from_spec(spec, track_m=1.0, wheel_width_m=0.22, seed=0)

    assert ring is not None
    assert ring["segments"][0]["name"] == "Straight authored"
    assert ring["segments"][0]["drive_mode"] == "STRAIGHT"
    assert ring["segments"][1]["name"] == "Left authored"
    assert ring["segments"][1]["drive_mode"] == "TURN_LEFT"
    assert ring["segments"][1]["turn_radius_m"] == 35.0


def test_segment_ranges_keep_canonical_direction_labels_for_playhead_hud() -> None:
    ring = {
        "ring_length_m": 30.0,
        "segments": [
            {
                "seg_idx": 1,
                "name": "S1",
                "drive_mode": "STRAIGHT",
                "turn_direction": "STRAIGHT",
                "turn_direction_label": "Прямо",
                "speed_start_kph": 40.0,
                "speed_end_kph": 40.0,
                "turn_radius_m": 0.0,
                "road_mode": "ISO8608",
                "road_mode_label": "ISO 8608 (шероховатость)",
                "edge_color": "#111111",
                "x_start_m": 0.0,
                "x_end_m": 10.0,
            },
            {
                "seg_idx": 2,
                "name": "S2",
                "drive_mode": "TURN_LEFT",
                "turn_direction": "LEFT",
                "turn_direction_label": "Поворот влево",
                "speed_start_kph": 40.0,
                "speed_end_kph": 40.0,
                "turn_radius_m": 25.0,
                "road_mode": "SINE",
                "road_mode_label": "Синус L/R",
                "edge_color": "#222222",
                "x_start_m": 10.0,
                "x_end_m": 30.0,
            },
        ],
    }

    ranges = build_segment_ranges_from_progress(ring, [0.0, 5.0, 12.0, 28.0])

    assert len(ranges) == 2
    assert ranges[0]["drive_mode"] == "STRAIGHT"
    assert ranges[0]["turn_direction"] == "STRAIGHT"
    assert ranges[0]["turn_direction_label"] == "Прямо"
    assert ranges[0]["speed_start_kph"] == 40.0
    assert ranges[0]["speed_end_kph"] == 40.0
    assert ranges[0]["turn_radius_m"] == 0.0
    assert ranges[0]["road_mode"] == "ISO8608"
    assert ranges[0]["road_mode_label"] == "ISO 8608 (шероховатость)"
    assert ranges[1]["drive_mode"] == "TURN_LEFT"
    assert ranges[1]["turn_direction"] == "LEFT"
    assert ranges[1]["turn_direction_label"] == "Поворот влево"
    assert ranges[1]["speed_start_kph"] == 40.0
    assert ranges[1]["speed_end_kph"] == 40.0
    assert ranges[1]["turn_radius_m"] == 25.0
    assert ranges[1]["road_mode"] == "SINE"
    assert ranges[1]["road_mode_label"] == "Синус L/R"


def test_embed_path_payload_on_ring_produces_closed_world_path() -> None:
    ring = {
        "ring_length_m": 100.0,
        "ring_radius_m": 100.0 / (2.0 * 3.141592653589793),
        "segments": [{"x_start_m": 0.0, "x_end_m": 100.0, "curvature_signed_m_inv": 0.0}],
    }
    path = {"s": [0.0, 25.0, 50.0, 75.0, 100.0], "v": [10.0] * 5}
    out = embed_path_payload_on_ring(path, ring, wheelbase_m=1.5)
    assert out["ring_mode"] is True
    assert abs(out["x"][0] - out["x"][-1]) < 1e-9
    assert abs(out["z"][0] - out["z"][-1]) < 1e-9


def test_embed_path_payload_on_ring_preserves_last_segment_curvature_at_exact_ring_end() -> None:
    ring = {
        "ring_length_m": 100.0,
        "ring_radius_m": 100.0 / (2.0 * 3.141592653589793),
        "segments": [
            {"x_start_m": 0.0, "x_end_m": 50.0, "curvature_signed_m_inv": 0.0},
            {"x_start_m": 50.0, "x_end_m": 100.0, "curvature_signed_m_inv": 0.2},
        ],
    }
    path = {"s": [100.0], "v": [10.0]}

    out = embed_path_payload_on_ring(path, ring, wheelbase_m=1.0)

    assert len(out["steer"]) == 1
    assert abs(float(out["steer"][0]) - float(math.atan(0.2))) < 1e-12


def test_mech_car3d_has_world_fixed_default_fps_and_ring_rendering_hooks() -> None:
    src = (ROOT / "pneumo_solver_ui" / "components" / "mech_car3d" / "index.html").read_text(encoding="utf-8")
    assert 'const followCar = (geo && (geo.camera_follow === false || geo.camera_follow === true)) ? !!geo.camera_follow : false;' in src
    assert 'const minDt = playing ? (1000/60) : (1000/8);' in src
    assert 'drawRingRoadEmbedded(currentRingSeg)' in src or 'drawRingRoadEmbedded()' in src
    assert 'pillFps' in src
    assert 'curvature_abs_m_inv' in src


def test_apps_pass_ring_visual_payload_and_world_fixed_defaults() -> None:
    src_main = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    src_helper = (ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py").read_text(encoding="utf-8")
    src_cockpit = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")
    assert 'load_ring_spec_from_test_cfg' in src_main
    assert 'render_heavy_results_surface_section(' in src_main
    assert 'ring_visual_pick=pick' in src_main
    assert 'ring_visual_base_dir=ROOT_DIR' in src_main
    assert '"ring_visual_pick": ring_visual_pick' in src_helper
    assert '"ring_visual_base_dir": ring_visual_base_dir' in src_helper
    assert 'load_ring_spec_from_npz' in src_cockpit
    assert '"ring_visual": ring_visual' in src_cockpit
    assert 'key="anim_3d_camera_follow"' in src_cockpit and 'value=False' in src_cockpit


def test_ring_visual_core_uses_half_open_segment_masks_for_curvature_assignment() -> None:
    src = (ROOT / "pneumo_solver_ui" / "ring_visuals.py").read_text(encoding="utf-8")
    assert 'if i >= len(rows) - 1:' in src
    assert 'mask = (x >= x0 - 1e-9) & (x < x1 - 1e-9)' in src
    assert 'if not np.any(mask):' in src
    assert 'spec_vis["closure_policy"] = "closed_c1_periodic"' not in src
