from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_drive_profile, generate_ring_tracks, summarize_ring_track_segments


ROOT = Path(__file__).resolve().parents[1]


def test_generate_ring_drive_profile_accepts_turn_direction_and_speed_end_contract() -> None:
    spec = {
        "v0_kph": 40.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 2.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 50.0,
                "road": {"mode": "SINE", "aL_mm": 0.0, "aR_mm": 0.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0},
            },
            {
                "name": "S2",
                "duration_s": 2.0,
                "turn_direction": "LEFT",
                "turn_radius_m": 40.0,
                "speed_end_kph": 40.0,
                "road": {"mode": "SINE", "aL_mm": 0.0, "aR_mm": 0.0, "lambdaL_m": 2.0, "lambdaR_m": 2.0},
            },
        ],
    }

    prof = generate_ring_drive_profile(spec, dt_s=0.02, n_laps=1)

    assert np.isclose(float(prof["v_mps"][0] * 3.6), 40.0, atol=1e-9)
    assert np.isclose(float(prof["v_mps"][-1] * 3.6), 40.0, atol=1e-9)
    assert float(np.nanmax(prof["ay_mps2"])) > 0.0


def test_generate_ring_tracks_apply_height_and_cross_slope_from_segment_end_states() -> None:
    spec = {
        "v0_kph": 20.0,
        "track_m": 1.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 2.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 20.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "center_height_start_mm": 0.0,
                    "center_height_end_mm": 50.0,
                    "cross_slope_start_pct": 0.0,
                    "cross_slope_end_pct": 2.0,
                },
            },
            {
                "name": "S2",
                "duration_s": 2.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 20.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "center_height_end_mm": 0.0,
                    "cross_slope_end_pct": 0.0,
                },
            },
        ],
    }

    tracks = generate_ring_tracks(spec, dx_m=0.05, seed=0)
    rows = summarize_ring_track_segments(spec, tracks)
    x = np.asarray(tracks["x_m"], dtype=float)
    z_l = np.asarray(tracks["zL_m"], dtype=float)
    z_r = np.asarray(tracks["zR_m"], dtype=float)

    x_end_s1 = float(rows[0]["x_end_m"])
    idx_end_s1 = int(np.argmin(np.abs(x - x_end_s1)))

    assert tracks["meta"]["road_state_contract"] is True
    assert np.isclose(float(z_l[0]), 0.0, atol=1e-9)
    assert np.isclose(float(z_r[0]), 0.0, atol=1e-9)
    assert np.isclose(float(z_l[idx_end_s1]), 0.04, atol=1e-6)
    assert np.isclose(float(z_r[idx_end_s1]), 0.06, atol=1e-6)
    assert np.isclose(float(z_l[-1]), 0.0, atol=1e-9)
    assert np.isclose(float(z_r[-1]), 0.0, atol=1e-9)


def test_ui_ring_editor_exposes_canonical_direction_and_road_state_controls() -> None:
    src = (ROOT / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")

    assert "Направление движения" in src
    assert "Конечная скорость, км/ч" in src
    assert "Высота дороги в конце сегмента, мм" in src
    assert "Поперечный уклон в конце, %" in src
    assert "Колея, м" in src
    assert "Legacy `drive_mode` сохраняется только как внутренний совместимый слой." in src
