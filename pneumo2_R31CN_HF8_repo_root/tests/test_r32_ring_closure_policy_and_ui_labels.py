from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks, validate_ring_spec, summarize_ring_track_segments


ROOT = Path(__file__).resolve().parents[1]


def test_ring_tracks_default_to_closed_c1_periodic_and_publish_seam_diagnostics() -> None:
    spec = {
        "schema": "ring_v2",
        "name": "closure_diag",
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "drive_mode": "STRAIGHT",
                "duration_s": 4.0,
                "speed_kph": 20.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 5.0,
                    "aR_mm": 7.0,
                    "lambdaL_m": 2.5,
                    "lambdaR_m": 2.5,
                    "phaseL_deg": 30.0,
                    "phaseR_deg": 45.0,
                },
            }
        ],
    }

    tracks = generate_ring_tracks(spec, dx_m=0.02, seed=0)
    meta = dict(tracks.get("meta") or {})

    assert meta["closure_policy"] == "closed_c1_periodic"
    assert meta["closure_applied"] is True
    assert meta["closure_bc_type"] == "periodic"
    assert float(meta["raw_seam_max_jump_m"]) > 0.0
    assert meta["seam_open"] is False
    assert np.isclose(float(meta["seam_max_jump_m"]), 0.0, atol=1e-12)
    assert float(meta["closure_correction_left_max_m"]) > 0.0
    assert float(meta["closure_correction_right_max_m"]) > 0.0


def test_local_c1_closure_does_not_destroy_middle_segment_sine_amplitude() -> None:
    spec = {
        "schema": "ring_v2",
        "name": "amp_preserve",
        "segments": [
            {"name": "S1_прямо", "drive_mode": "STRAIGHT", "duration_s": 5.0, "speed_kph": 40.0, "road": {"mode": "ISO8608", "iso_class": "C"}},
            {"name": "S2_поворот", "drive_mode": "TURN_LEFT", "duration_s": 4.0, "speed_kph": 40.0, "turn_radius_m": 60.0,
             "road": {"mode": "SINE", "aL_mm": 100.0, "aR_mm": 100.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0, "phaseL_deg": 5.0, "phaseR_deg": 180.0}},
            {"name": "S3_разгон", "drive_mode": "ACCEL", "duration_s": 3.5, "v_end_kph": 55.0, "road": {"mode": "ISO8608", "iso_class": "C"}},
            {"name": "S4_торможение", "drive_mode": "BRAKE", "duration_s": 2.5, "v_end_kph": 40.0, "road": {"mode": "ISO8608", "iso_class": "C"}},
        ],
        "closure_policy": "closed_c1_periodic",
    }
    tracks = generate_ring_tracks(spec, dx_m=0.02, seed=123)
    rows = summarize_ring_track_segments(spec, tracks)
    s2 = rows[1]
    meta = dict(tracks.get("meta") or {})
    assert meta["seam_open"] is False
    assert np.isclose(float(meta["seam_max_jump_m"]), 0.0, atol=1e-12)
    # local amplitude stays in the same order as the authored 100 mm request
    assert 90.0 <= float(s2["L_amp_mm"]) <= 120.0
    assert 180.0 <= float(s2["L_p2p_mm"]) <= 220.0


def test_validate_ring_spec_rejects_noncanonical_closure_policy() -> None:
    spec = {
        "schema": "ring_v2",
        "closure_policy": "explicit_closure_segment",
        "segments": [
            {
                "name": "S1",
                "drive_mode": "STRAIGHT",
                "duration_s": 1.0,
                "speed_kph": 10.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            }
        ],
    }

    report = validate_ring_spec(spec)
    assert report["errors"]
    assert any("closure_policy" in msg for msg in report["errors"])


def test_ui_full_ring_summary_labels_explicitly_distinguish_a_and_p2p() -> None:
    src = (ROOT / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")

    assert "Профиль ВСЕГО кольца: amplitude A L/R (служ.)" in src
    assert "Профиль ВСЕГО кольца: p-p=max-min L/R (НЕ A)" in src
    assert "closure_policy=" in src
