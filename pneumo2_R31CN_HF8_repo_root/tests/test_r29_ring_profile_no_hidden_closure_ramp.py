from __future__ import annotations

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks


def test_ring_nonperiodic_sine_keeps_requested_amplitude_and_reports_open_seam() -> None:
    spec = {
        "schema": "ring_v2",
        "name": "nonperiodic_sine",
        "dt_s": 0.01,
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
    z_l = np.asarray(tracks["zL_m"], dtype=float)
    z_r = np.asarray(tracks["zR_m"], dtype=float)

    # The generator must keep the requested deterministic amplitudes instead of
    # silently bending the whole ring with a closure ramp.
    assert np.isclose(0.5 * (float(z_l.max()) - float(z_l.min())), 0.005, atol=5e-6)
    assert np.isclose(0.5 * (float(z_r.max()) - float(z_r.min())), 0.007, atol=5e-6)

    # A non-periodic ring is allowed to keep an open seam; no hidden closure is applied.
    assert not np.isclose(float(z_l[-1]), float(z_l[0]), atol=1e-6)
    assert not np.isclose(float(z_r[-1]), float(z_r[0]), atol=1e-6)
