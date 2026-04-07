# -*- coding: utf-8 -*-
import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks


def test_ring_sine_segment_local_amplitude_stays_near_requested_even_after_previous_segments():
    spec = {
        "schema_version": "ring_v2",
        "v0_kph": 40.0,
        "seed": 123,
        "dx_m": 0.02,
        "segments": [
            {
                "name": "S1",
                "duration_s": 5.0,
                "drive_mode": "STRAIGHT",
                "speed_kph": 40.0,
                "road": {"mode": "ISO8608", "iso_class": "D", "gd_pick": "mid", "gd_n0_scale": 1.0, "waviness_w": 2.0, "left_right_coherence": 0.5, "seed": 111},
                "events": [],
                "length_m": 55.5555555556,
            },
            {
                "name": "S2",
                "duration_s": 4.0,
                "drive_mode": "TURN_LEFT",
                "speed_kph": 40.0,
                "turn_radius_m": 60.0,
                "road": {"mode": "SINE", "aL_mm": 80.0, "aR_mm": 60.0, "lambdaL_m": 1.5, "lambdaR_m": 2.0, "phaseL_deg": 0.0, "phaseR_deg": 180.0},
                "events": [],
                "length_m": 44.4444444444,
            },
        ],
    }
    tracks = generate_ring_tracks(spec, dx_m=0.02, seed=123)
    x = np.asarray(tracks["x_m"], dtype=float)
    zL = np.asarray(tracks["zL_m"], dtype=float)
    zR = np.asarray(tracks["zR_m"], dtype=float)

    s1_len = float(spec["segments"][0]["length_m"])
    s2_len = float(spec["segments"][1]["length_m"])
    mask = (x >= s1_len - 1e-9) & (x <= s1_len + s2_len + 1e-9)
    zL2 = zL[mask]
    zR2 = zR[mask]
    aL_local_mm = 1000.0 * float(np.max(np.abs(zL2 - np.median(zL2))))
    aR_local_mm = 1000.0 * float(np.max(np.abs(zR2 - np.median(zR2))))

    assert abs(aL_local_mm - 80.0) < 5.0
    assert abs(aR_local_mm - 60.0) < 5.0
