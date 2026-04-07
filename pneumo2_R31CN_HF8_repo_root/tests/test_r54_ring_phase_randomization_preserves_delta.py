from __future__ import annotations

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks


def _single_sine_spec(*, rand_pl: bool = True, rand_pr: bool = True, p: float = 1.0) -> dict:
    return {
        "v0_kph": 40.0,
        "dx_m": 0.02,
        "segments": [
            {
                "drive_mode": "STRAIGHT",
                "length_m": 3.0,
                "speed_kph": 40.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 50.0,
                    "aR_mm": 50.0,
                    "lambdaL_m": 1.5,
                    "lambdaR_m": 1.5,
                    "phaseL_deg": 0.0,
                    "phaseR_deg": 180.0,
                    "rand_pL": rand_pl,
                    "rand_pR": rand_pr,
                    "rand_pL_p": p,
                    "rand_pR_p": p,
                    "rand_pL_lo_deg": 0.0,
                    "rand_pL_hi_deg": 360.0,
                    "rand_pR_lo_deg": 0.0,
                    "rand_pR_hi_deg": 360.0,
                },
            }
        ],
    }


def test_symmetric_phase_randomization_preserves_explicit_left_right_delta() -> None:
    tracks = generate_ring_tracks(_single_sine_spec(rand_pl=True, rand_pr=True, p=1.0), dx_m=0.01, seed=123)

    z_left = np.asarray(tracks["zL_m"], dtype=float)
    z_right = np.asarray(tracks["zR_m"], dtype=float)

    assert z_left.shape == z_right.shape
    # Same amplitude/wavelength with explicit 180° delta must remain strict anti-phase
    # even when phase randomization is enabled symmetrically on both sides.
    assert np.max(np.abs(z_left + z_right)) <= 1e-9


def test_asymmetric_phase_randomization_can_still_fall_back_to_independent_side_behavior() -> None:
    tracks = generate_ring_tracks(_single_sine_spec(rand_pl=False, rand_pr=True, p=1.0), dx_m=0.01, seed=123)

    z_left = np.asarray(tracks["zL_m"], dtype=float)
    z_right = np.asarray(tracks["zR_m"], dtype=float)

    assert z_left.shape == z_right.shape
    # Historical independent-side semantics remain available when only one side requests
    # randomization: this should generally break the perfect anti-phase identity.
    assert np.max(np.abs(z_left + z_right)) > 1e-4
