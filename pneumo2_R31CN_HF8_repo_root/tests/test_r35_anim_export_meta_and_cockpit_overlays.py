from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.anim_export_meta import extract_anim_sidecar_meta

ROOT = Path(__file__).resolve().parents[1]


def test_extract_anim_sidecar_meta_infers_ring_scenario_and_effective_v0(tmp_path: Path) -> None:
    road = tmp_path / "scenario_demo_road.csv"
    axay = tmp_path / "scenario_demo_axay.csv"
    spec = tmp_path / "scenario_demo_spec.json"
    road.write_text("t_s,z_fl_m,z_fr_m,z_rl_m,z_rr_m\n0,0,0,0,0\n", encoding="utf-8")
    axay.write_text("t_s,ax_mps2,ay_mps2\n0,0,0\n", encoding="utf-8")
    spec.write_text(
        json.dumps(
            {
                "schema": "ring_v2",
                "v0_kph": 0.0,
                "segments": [
                    {"name": "S1", "drive_mode": "STRAIGHT", "duration_s": 5.0, "speed_kph": 40.0, "road": {"mode": "ISO8608", "iso_class": "C"}},
                    {"name": "S2", "drive_mode": "TURN_LEFT", "duration_s": 4.0, "speed_kph": 40.0, "turn_radius_m": 60.0, "road": {"mode": "SINE", "aL_mm": 100.0, "aR_mm": 100.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0}},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    meta = extract_anim_sidecar_meta(
        {
            "road_csv": str(road),
            "axay_csv": str(axay),
            "vx0_м_с": 0.0,
            "road_len_m": 179.2,
        },
        base_dirs=[tmp_path],
    )
    assert Path(meta["scenario_json"]).resolve() == spec.resolve()
    assert meta["scenario_kind"] == "ring"
    assert abs(float(meta["vx0_м_с"]) - (40.0 / 3.6)) < 1e-9
    assert abs(float(meta["ring_v0_kph"]) - 40.0) < 1e-9
    assert float(meta["ring_nominal_speed_max_mps"]) >= float(meta["ring_nominal_speed_min_mps"]) > 0.0


def test_extract_anim_sidecar_meta_keeps_non_ring_speed() -> None:
    meta = extract_anim_sidecar_meta({"vx0_м_с": 12.5, "road_csv": "demo.csv"}, base_dirs=[])
    assert abs(float(meta["vx0_м_с"]) - 12.5) < 1e-12
    assert "scenario_json" not in meta


def test_animation_cockpit_passes_ring_visual_to_minimap_and_profile() -> None:
    src = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")
    assert "ring_visual=ring_visual" in src
    assert src.count("ring_visual=ring_visual") >= 2


def test_minimap_and_road_profile_have_segment_overlay_hooks() -> None:
    mini = (ROOT / "pneumo_solver_ui" / "components" / "minimap_live" / "index.html").read_text(encoding="utf-8")
    prof = (ROOT / "pneumo_solver_ui" / "components" / "road_profile_live" / "index.html").read_text(encoding="utf-8")
    assert "drawRingSegmentOverlay" in mini
    assert "badgeSeg" in mini
    assert "turn_direction_label" in mini
    assert "DATA.ring_visual" in mini
    assert "drawRingSegmentBands" in prof
    assert "segNowName" in prof
    assert "turn_direction_label" in prof
    assert "DATA.ring_visual" in prof
