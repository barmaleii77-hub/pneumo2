from __future__ import annotations

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks, summarize_ring_track_segments


def test_ring_segment_summary_distinguishes_amplitude_from_peak_to_peak() -> None:
    spec = {
        "schema": "ring_v2",
        "name": "summary_amp",
        "dt_s": 0.01,
        "v0_kph": 36.0,
        "segments": [
            {
                "name": "S1",
                "drive_mode": "STRAIGHT",
                "duration_s": 5.0,
                "speed_kph": 36.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 80.0,
                    "aR_mm": 60.0,
                    "lambdaL_m": 1.5,
                    "lambdaR_m": 2.0,
                    "phaseL_deg": 0.0,
                    "phaseR_deg": 180.0,
                },
            }
        ],
    }

    tracks = generate_ring_tracks(spec, dx_m=0.02, seed=123)
    rows = summarize_ring_track_segments(spec, tracks)
    assert len(rows) == 1
    row = rows[0]
    assert np.isclose(float(row["L_amp_mm"]), 80.0, atol=0.2)
    assert np.isclose(float(row["R_amp_mm"]), 60.0, atol=0.2)
    assert np.isclose(float(row["L_p2p_mm"]), 160.0, atol=0.4)
    assert np.isclose(float(row["R_p2p_mm"]), 120.0, atol=0.4)
    assert np.isclose(float(row["generated_x_local_end_m"]), 50.0, atol=1e-9)
