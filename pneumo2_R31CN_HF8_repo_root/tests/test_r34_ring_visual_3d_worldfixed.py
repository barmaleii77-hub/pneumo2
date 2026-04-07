from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ring_visuals import build_ring_visual_payload_from_spec, embed_path_payload_on_ring

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
    assert max(ring["curvature_abs_m_inv"]) > 0.0
    assert ring["road_width_m"] > 1.0


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


def test_mech_car3d_has_world_fixed_default_fps_and_ring_rendering_hooks() -> None:
    src = (ROOT / "pneumo_solver_ui" / "components" / "mech_car3d" / "index.html").read_text(encoding="utf-8")
    assert 'const followCar = (geo && (geo.camera_follow === false || geo.camera_follow === true)) ? !!geo.camera_follow : false;' in src
    assert 'const minDt = playing ? (1000/60) : (1000/8);' in src
    assert 'drawRingRoadEmbedded(currentRingSeg)' in src or 'drawRingRoadEmbedded()' in src
    assert 'pillFps' in src
    assert 'curvature_abs_m_inv' in src


def test_apps_pass_ring_visual_payload_and_world_fixed_defaults() -> None:
    src_main = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    src_cockpit = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")
    assert 'load_ring_spec_from_test_cfg' in src_main
    assert '"ring_visual": ring_visual' in src_main
    assert 'Камера следует за машиной (центр кадра)", value=False' in src_main
    assert 'load_ring_spec_from_npz' in src_cockpit
    assert '"ring_visual": ring_visual' in src_cockpit
    assert 'key="anim_3d_camera_follow"' in src_cockpit and 'value=False' in src_cockpit
