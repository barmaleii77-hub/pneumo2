from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pneumo_solver_ui.data_contract import build_geometry_meta_from_base, read_visual_geometry_meta
from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    cylinder_dead_lengths_from_contract,
    cylinder_visual_segments_from_state,
    cylinder_visual_state_from_packaging,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_geometry_meta_exports_explicit_cylinder_packaging_contract() -> None:
    base = {
        "база": 1.5,
        "колея": 1.0,
        "диаметр_поршня_Ц1": 0.032,
        "диаметр_штока_Ц1": 0.016,
        "диаметр_поршня_Ц2": 0.05,
        "диаметр_штока_Ц2": 0.014,
        "ход_штока_Ц1_перед_м": 0.25,
        "ход_штока_Ц1_зад_м": 0.25,
        "ход_штока_Ц2_перед_м": 0.25,
        "ход_штока_Ц2_зад_м": 0.25,
        "мёртвый_объём_камеры": 1.5e-5,
        "стенка_толщина_м": 0.003,
    }
    geom = build_geometry_meta_from_base(base)
    assert math.isclose(geom["cyl1_outer_diameter_m"], 0.038, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(geom["cyl2_outer_diameter_m"], 0.056, rel_tol=0.0, abs_tol=1e-12)
    assert geom["cyl1_dead_cap_length_m"] > 0.0
    assert geom["cyl1_dead_rod_length_m"] > geom["cyl1_dead_cap_length_m"]
    assert geom["cyl2_dead_cap_length_m"] > 0.0
    assert geom["cyl2_dead_rod_length_m"] > geom["cyl2_dead_cap_length_m"]
    assert math.isclose(geom["cylinder_wall_thickness_m"], 0.003, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(geom["cyl1_dead_height_m"], geom["cyl1_dead_cap_length_m"], rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(
        geom["cyl1_body_length_front_m"],
        geom["cyl1_stroke_front_m"] + 2.0 * geom["cyl1_dead_height_m"] + 2.0 * geom["cylinder_wall_thickness_m"],
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def test_read_visual_geometry_meta_exposes_packaging_keys() -> None:
    meta = {
        "geometry": {
            "wheelbase_m": 1.5,
            "track_m": 1.0,
            "cyl1_outer_diameter_m": 0.038,
            "cyl2_outer_diameter_m": 0.056,
            "cyl1_dead_cap_length_m": 0.01,
            "cyl1_dead_rod_length_m": 0.02,
            "cyl2_dead_cap_length_m": 0.03,
            "cyl2_dead_rod_length_m": 0.04,
            "cylinder_wall_thickness_m": 0.003,
            "cyl1_dead_height_m": 0.01,
            "cyl1_body_length_front_m": 0.266,
        }
    }
    vis = read_visual_geometry_meta(meta, context="pytest meta")
    assert vis["cyl1_outer_diameter_m"] == 0.038
    assert vis["cyl2_outer_diameter_m"] == 0.056
    assert vis["cyl1_dead_cap_length_m"] == 0.01
    assert vis["cyl2_dead_rod_length_m"] == 0.04
    assert vis["cylinder_wall_thickness_m"] == 0.003
    assert vis["cyl1_body_length_front_m"] == 0.266


def test_cylinder_visual_state_from_packaging_uses_exact_contract_and_no_fake_piston_thickness() -> None:
    dead_cap, dead_rod = cylinder_dead_lengths_from_contract(bore_d_m=0.05, rod_d_m=0.014, dead_vol_m3=1.5e-5)
    assert dead_cap is not None and dead_rod is not None
    wall = 0.003
    body_len = 0.25 + 2.0 * float(dead_cap) + 2.0 * wall
    st = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.array([0.0, 0.34, 0.0], dtype=float),
        stroke_pos_m=0.12,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        outer_d_m=0.056,
        dead_cap_len_m=float(dead_cap),
        dead_rod_len_m=float(dead_rod),
        dead_height_m=float(dead_cap),
        body_len_m=float(body_len),
    )
    assert st is not None
    assert math.isclose(float(st["body_outer_radius_m"]), 0.028, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(float(st["rod_radius_m"]), 0.007, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(float(st["piston_radius_m"]), 0.025, rel_tol=0.0, abs_tol=1e-12)
    piston_center = np.asarray(st["piston_center"], dtype=float)
    assert 0.0 < float(piston_center[1]) < float(body_len)


def test_cylinder_visual_state_keeps_body_on_frame_and_rod_on_arm() -> None:
    dead_cap, dead_rod = cylinder_dead_lengths_from_contract(bore_d_m=0.05, rod_d_m=0.014, dead_vol_m3=1.5e-5)
    assert dead_cap is not None and dead_rod is not None
    wall = 0.003
    body_len = 0.25 + 2.0 * float(dead_cap) + 2.0 * wall
    st = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.array([0.0, 0.34, 0.0], dtype=float),
        stroke_pos_m=0.18,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        outer_d_m=0.056,
        dead_cap_len_m=float(dead_cap),
        dead_rod_len_m=float(dead_rod),
        dead_height_m=float(dead_cap),
        body_len_m=float(body_len),
    )
    assert st is not None
    body_seg = st["body_seg"]
    rod_seg = st["rod_seg"]
    housing_seg = st["housing_seg"]
    piston_center = np.asarray(st["piston_center"], dtype=float)
    assert np.allclose(np.asarray(body_seg[0], dtype=float), np.array([0.0, 0.0, 0.0], dtype=float))
    assert np.allclose(np.asarray(body_seg[1], dtype=float), piston_center)
    assert np.allclose(np.asarray(housing_seg[0], dtype=float), np.array([0.0, 0.0, 0.0], dtype=float))
    assert math.isclose(float(np.asarray(housing_seg[1], dtype=float)[1]), float(body_len), rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(float(np.asarray(rod_seg[1], dtype=float)[1]), 0.34, rel_tol=0.0, abs_tol=1e-12)
    assert float(np.asarray(rod_seg[0], dtype=float)[1]) >= float(np.asarray(housing_seg[1], dtype=float)[1]) - 1e-12


def test_cylinder_piston_moves_toward_rod_when_extension_grows() -> None:
    dead_cap, dead_rod = cylinder_dead_lengths_from_contract(bore_d_m=0.05, rod_d_m=0.014, dead_vol_m3=1.5e-5)
    assert dead_cap is not None and dead_rod is not None
    wall = 0.003
    body_len = 0.25 + 2.0 * float(dead_cap) + 2.0 * wall
    st_retracted = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.array([0.0, 0.34, 0.0], dtype=float),
        stroke_pos_m=0.02,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        outer_d_m=0.056,
        dead_cap_len_m=float(dead_cap),
        dead_rod_len_m=float(dead_rod),
        dead_height_m=float(dead_cap),
        body_len_m=float(body_len),
    )
    st_extended = cylinder_visual_state_from_packaging(
        top_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.array([0.0, 0.34, 0.0], dtype=float),
        stroke_pos_m=0.23,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        outer_d_m=0.056,
        dead_cap_len_m=float(dead_cap),
        dead_rod_len_m=float(dead_rod),
        dead_height_m=float(dead_cap),
        body_len_m=float(body_len),
    )
    assert st_retracted is not None and st_extended is not None
    y_retracted = float(np.asarray(st_retracted["piston_center"], dtype=float)[1])
    y_extended = float(np.asarray(st_extended["piston_center"], dtype=float)[1])
    assert y_extended > y_retracted


def test_cylinder_visual_segments_keep_piston_as_exact_plane_center() -> None:
    _body_seg, rod_seg, piston_seg = cylinder_visual_segments_from_state(
        top_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        bot_xyz=np.array([0.0, 0.14, 0.0], dtype=float),
        stroke_pos_m=0.12,
        stroke_len_m=0.25,
        bore_d_m=0.05,
        rod_d_m=0.014,
        dead_vol_m3=1.5e-5,
    )
    assert rod_seg is not None
    assert piston_seg is not None
    assert np.allclose(np.asarray(piston_seg[0]), np.asarray(piston_seg[1]))
    assert float(np.linalg.norm(np.asarray(rod_seg[1]) - np.asarray(rod_seg[0]))) > 0.0


def test_desktop_animator_source_restores_honest_packaging_rendering() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
    assert "_cylinder_visual_state_from_packaging" in src
    assert "_set_disc_mesh(" in src
    assert "body/rod/piston stay disabled" not in src
