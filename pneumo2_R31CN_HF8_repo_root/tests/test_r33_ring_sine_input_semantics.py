from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks, summarize_ring_track_segments

ROOT = Path(__file__).resolve().parents[1]


def test_sine_amplitude_100_mm_means_plus_minus_100_and_pp_200() -> None:
    spec = {
        "schema": "ring_v2",
        "name": "amp100",
        "v0_kph": 36.0,
        "segments": [
            {
                "name": "S1",
                "drive_mode": "STRAIGHT",
                "duration_s": 5.0,
                "speed_kph": 36.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 100.0,
                    "aR_mm": 100.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "phaseL_deg": 0.0,
                    "phaseR_deg": 0.0,
                },
            }
        ],
    }
    tracks = generate_ring_tracks(spec, dx_m=0.02, seed=0)
    rows = summarize_ring_track_segments(spec, tracks)
    row = rows[0]
    assert np.isclose(float(row["L_amp_mm"]), 100.0, atol=0.3)
    assert np.isclose(float(row["L_p2p_mm"]), 200.0, atol=0.6)
    assert np.isclose(float(row["R_amp_mm"]), 100.0, atol=0.3)
    assert np.isclose(float(row["R_p2p_mm"]), 200.0, atol=0.6)


def test_ui_sine_inputs_explicitly_explain_half_span_vs_peak_to_peak() -> None:
    src = (ROOT / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")
    assert "Амплитуда A (полуразмах), мм" in src
    assert "Если вы хотите получить профиль от -100 до +100 мм, задавайте A=100 мм" in src
    assert "полный размах p-p = 200 мм" in src
