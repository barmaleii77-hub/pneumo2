from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui.scenario_ring import (
    generate_ring_drive_profile,
    generate_ring_scenario_bundle,
    generate_ring_tracks,
    summarize_ring_track_segments,
    validate_ring_spec,
)
from pneumo_solver_ui.ui_scenario_ring import (
    _default_ring_spec,
    _segment_end_speed_kph,
    _segment_length_estimate_m,
)


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


def test_missing_v0_kph_uses_first_segment_speed_end_as_safe_canonical_fallback() -> None:
    spec = {
        "segments": [
            {
                "name": "S1",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 40.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "RIGHT",
                "turn_radius_m": 40.0,
                "speed_end_kph": 40.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
        ],
    }

    report = validate_ring_spec(spec)
    prof = generate_ring_drive_profile(spec, dt_s=0.02, n_laps=1)

    assert np.isclose(float(prof["v_mps"][0] * 3.6), 40.0, atol=1e-9)
    assert any("явное speed_start_kph" in msg for msg in report["warnings"])


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


def test_default_ring_spec_uses_canonical_segment_semantics_without_accel_brake_types() -> None:
    spec = _default_ring_spec()
    segs = list(spec.get("segments", []) or [])

    assert segs
    assert all("turn_direction" in seg for seg in segs)
    assert all("speed_end_kph" in seg for seg in segs)
    assert all("speed_kph" not in seg for seg in segs)
    assert all("v_end_kph" not in seg for seg in segs)
    assert all(str(seg.get("drive_mode", "") or "").upper() not in {"ACCEL", "BRAKE"} for seg in segs)
    assert not any("разгон" in str(seg.get("name", "")).lower() for seg in segs)
    assert not any("тормож" in str(seg.get("name", "")).lower() for seg in segs)


def test_ui_preview_helpers_auto_close_last_segment_speed_and_length() -> None:
    seg = {
        "name": "S_last",
        "duration_s": 2.0,
        "turn_direction": "STRAIGHT",
        "speed_end_kph": 45.0,
        "road": {"mode": "ISO8608", "iso_class": "C"},
    }

    v_end = _segment_end_speed_kph(30.0, seg, forced_end_kph=20.0)
    length_m = _segment_length_estimate_m(30.0, seg, forced_end_kph=20.0)
    expected_length_m = 0.5 * ((30.0 / 3.6) + (20.0 / 3.6)) * 2.0

    assert np.isclose(v_end, 20.0, atol=1e-9)
    assert np.isclose(length_m, expected_length_m, atol=1e-9)


def test_validate_ring_spec_is_canonical_first_and_does_not_require_legacy_speed_fields() -> None:
    spec = {
        "v0_kph": 40.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 2.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 45.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                },
                "events": [{"kind": "яма", "start_m": 1.0, "length_m": 0.2, "depth_mm": -10.0}],
            },
            {
                "name": "S2",
                "duration_s": 2.0,
                "turn_direction": "RIGHT",
                "turn_radius_m": 50.0,
                "speed_end_kph": 40.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                },
                "events": [{"kind": "препятствие", "start_m": 0.5, "length_m": 0.2, "depth_mm": 10.0}],
            },
        ],
    }

    report = validate_ring_spec(spec)

    assert report["errors"] == []
    assert not any("speed_kph" in msg and "алиасы запрещены" in msg for msg in report["warnings"])
    assert not any("v_end_kph" in msg and "алиасы запрещены" in msg for msg in report["warnings"])
    assert not any("drive_mode" in msg and "неизвестный" in msg for msg in report["warnings"] + report["errors"])


def test_validate_ring_spec_warns_when_nonfirst_segment_uses_start_fields() -> None:
    spec = {
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 20.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "center_height_start_mm": 0.0,
                    "cross_slope_start_pct": 0.0,
                },
                "events": [{"kind": "яма", "start_m": 0.2, "length_m": 0.1, "depth_mm": -10.0}],
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_start_kph": 99.0,
                "speed_end_kph": 20.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "center_height_start_mm": 100.0,
                    "cross_slope_start_pct": 5.0,
                },
                "events": [{"kind": "препятствие", "start_m": 0.2, "length_m": 0.1, "depth_mm": 10.0}],
            },
        ],
    }

    report = validate_ring_spec(spec)

    assert report["errors"] == []
    assert any("speed_start_kph для сегментов 2..N" in msg for msg in report["warnings"])
    assert any("center_height_start_mm для сегментов 2..N" in msg for msg in report["warnings"])
    assert any("cross_slope_start_pct для сегментов 2..N" in msg for msg in report["warnings"])


def test_validate_ring_spec_collects_numeric_input_errors_instead_of_crashing() -> None:
    spec = {
        "v0_kph": "fast",
        "track_m": "wide",
        "segments": [
            {
                "name": "S1",
                "duration_s": "oops",
                "turn_direction": "LEFT",
                "turn_radius_m": "tight",
                "speed_start_kph": "start",
                "speed_end_kph": "finish",
                "road": {
                    "mode": "SINE",
                    "aL_mm": "high",
                    "lambdaL_m": "short",
                },
                "events": [
                    {
                        "kind": "яма",
                        "start_m": "near",
                        "length_m": "long",
                        "depth_mm": "deep",
                    }
                ],
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 20.0,
                "road": {
                    "mode": "ISO8608",
                    "iso_class": "C",
                    "waviness_w": "wavy",
                    "left_right_coherence": "linked",
                },
                "events": [
                    {
                        "kind": "препятствие",
                        "start_m": 0.2,
                        "length_m": 0.1,
                        "depth_mm": 10.0,
                    }
                ],
            },
        ],
    }

    report = validate_ring_spec(spec)

    assert any("v0_kph должен быть числом." in msg for msg in report["errors"])
    assert any("track_m должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: duration_s должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: turn_radius_m должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: speed_start_kph должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: speed_end_kph должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: aL_mm должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: lambdaL_m должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: event.start_m должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: event.length_m должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 1: event.depth_mm должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 2: waviness_w должен быть числом." in msg for msg in report["errors"])
    assert any("Сегмент 2: left_right_coherence должен быть числом." in msg for msg in report["errors"])


def test_ring_runtime_ignores_nonfirst_authored_start_speed_and_keeps_chain_continuity() -> None:
    spec = {
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 2.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 35.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
            {
                "name": "S2",
                "duration_s": 2.0,
                "turn_direction": "STRAIGHT",
                "speed_start_kph": 99.0,
                "speed_end_kph": 20.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
        ],
    }

    tracks = generate_ring_tracks(spec, dx_m=0.05, seed=0)
    rows = summarize_ring_track_segments(spec, tracks)

    assert np.isclose(float(rows[0]["speed_end_kph"]), 35.0, atol=1e-9)
    assert np.isclose(float(rows[1]["speed_start_kph"]), 35.0, atol=1e-9)
    assert np.isclose(float(rows[1]["speed_end_kph"]), 20.0, atol=1e-9)


def test_ring_runtime_auto_closes_last_segment_end_speed_to_first_segment_start() -> None:
    spec = {
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 30.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 45.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
        ],
    }

    prof = generate_ring_drive_profile(spec, dt_s=0.02, n_laps=1)
    tracks = generate_ring_tracks(spec, dx_m=0.05, seed=0)
    rows = summarize_ring_track_segments(spec, tracks)

    assert np.isclose(float(prof["v_mps"][0] * 3.6), 20.0, atol=1e-9)
    assert np.isclose(float(prof["v_mps"][-1] * 3.6), 20.0, atol=1e-9)
    assert np.isclose(float(rows[-1]["speed_end_kph"]), 20.0, atol=1e-9)


def test_generate_ring_scenario_bundle_drops_nonfirst_start_only_fields(tmp_path: Path) -> None:
    spec = {
        "v0_kph": 20.0,
        "track_m": 1.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_start_kph": 20.0,
                "speed_end_kph": 25.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "center_height_start_mm": 0.0,
                    "center_height_end_mm": 10.0,
                    "cross_slope_start_pct": 0.0,
                    "cross_slope_end_pct": 1.0,
                },
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_start_kph": 99.0,
                "speed_end_kph": 20.0,
                "road": {
                    "mode": "SINE",
                    "aL_mm": 0.0,
                    "aR_mm": 0.0,
                    "lambdaL_m": 2.0,
                    "lambdaR_m": 2.0,
                    "center_height_start_mm": 100.0,
                    "center_height_end_mm": 0.0,
                    "cross_slope_start_pct": 5.0,
                    "cross_slope_end_pct": 0.0,
                },
            },
        ],
    }

    bundle = generate_ring_scenario_bundle(
        spec,
        out_dir=tmp_path,
        dt_s=0.02,
        n_laps=1,
        wheelbase_m=1.5,
        dx_m=0.05,
        seed=0,
        tag="canonical_ring",
    )
    saved = json.loads(Path(bundle["scenario_json"]).read_text(encoding="utf-8"))

    assert float(saved["segments"][0]["speed_start_kph"]) == 20.0
    assert "speed_start_kph" not in saved["segments"][1]
    assert "center_height_start_mm" not in saved["segments"][1]["road"]
    assert "cross_slope_start_pct" not in saved["segments"][1]["road"]
    assert all("drive_mode" not in seg for seg in saved["segments"])
    assert all("speed_kph" not in seg for seg in saved["segments"])
    assert all("v_end_kph" not in seg for seg in saved["segments"])


def test_generate_ring_scenario_bundle_auto_closes_last_segment_speed_and_validation_explains_it(
    tmp_path: Path,
) -> None:
    spec = {
        "v0_kph": 20.0,
        "segments": [
            {
                "name": "S1",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 30.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
            {
                "name": "S2",
                "duration_s": 1.0,
                "turn_direction": "STRAIGHT",
                "speed_end_kph": 45.0,
                "road": {"mode": "ISO8608", "iso_class": "C"},
            },
        ],
    }

    report = validate_ring_spec(spec)
    bundle = generate_ring_scenario_bundle(
        spec,
        out_dir=tmp_path,
        dt_s=0.02,
        n_laps=1,
        wheelbase_m=1.5,
        dx_m=0.05,
        seed=0,
        tag="closed_speed_ring",
    )
    saved = json.loads(Path(bundle["scenario_json"]).read_text(encoding="utf-8"))

    assert any("UI/генератор всё равно замкнёт кольцо по начальной скорости" in msg for msg in report["warnings"])
    assert np.isclose(float(saved["segments"][-1]["speed_end_kph"]), 20.0, atol=1e-9)


def test_ui_ring_editor_source_keeps_start_only_fields_on_first_segment() -> None:
    src = (ROOT / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")

    assert 'seg.pop("speed_start_kph", None)' in src
    assert 'seg.pop("drive_mode", None)' in src
    assert 'seg.pop("speed_kph", None)' in src
    assert 'seg.pop("v_end_kph", None)' in src
    assert 'road.pop("center_height_start_mm", None)' in src
    assert 'road.pop("cross_slope_start_pct", None)' in src
    assert 'seg["drive_mode"] =' not in src
    assert 'seg["speed_kph"] =' not in src
    assert 'seg["v_end_kph"] =' not in src
    assert 'out["accel_time_s"]' not in src
    assert 'out["brake_time_s"]' not in src
