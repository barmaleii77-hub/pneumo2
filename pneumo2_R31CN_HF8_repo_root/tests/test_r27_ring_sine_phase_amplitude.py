from __future__ import annotations

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks


def test_ring_sine_preserves_requested_amplitude_when_ring_is_periodic() -> None:
    spec = {
        "schema": "ring_v2",
        "name": "phase_preserve",
        "dt_s": 0.01,
        "v0_kph": 54.0,
        "segments": [
            {
                "name": "S1",
                "drive_mode": "STRAIGHT",
                "duration_s": 4.0,
                "speed_kph": 54.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 5.0,
                    "aR_mm": 7.0,
                    "lambdaL_m": 2.5,
                    "lambdaR_m": 3.0,
                    "phaseL_deg": 0.0,
                    "phaseR_deg": 30.0,
                },
            }
        ],
    }

    tracks = generate_ring_tracks(spec)
    x = np.asarray(tracks["x_m"], dtype=float)
    z_l = np.asarray(tracks["zL_m"], dtype=float)
    z_r = np.asarray(tracks["zR_m"], dtype=float)

    # Length coordinate must still correspond to distance = v * t.
    assert abs(float(x[-1]) - 60.0) < 1e-9

    # Requested sine amplitudes must remain requested amplitudes; no artificial A*2 effect.
    assert np.isclose(0.5 * (float(z_l.max()) - float(z_l.min())), 0.005, atol=5e-6)
    assert np.isclose(0.5 * (float(z_r.max()) - float(z_r.min())), 0.007, atol=5e-6)

    # For a periodic ring with integer number of wavelengths, the phase offset must not be
    # destroyed by force-shifting the first sample to zero.
    assert np.isclose(float(z_r[0]), 0.007 * np.sin(np.deg2rad(30.0)), atol=5e-6)
