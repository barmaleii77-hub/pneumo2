from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.suspension_family_runtime import (
    build_spring_family_runtime_snapshot,
    normalize_spring_attachment_mode,
    resolve_cylinder_corner_geometry,
    resolve_spring_corner_geometry,
    split_dual_spring_force_target,
    spring_family_active_flag_column,
    spring_family_mode_id,
    spring_family_runtime_column,
    spring_family_runtime_series_template,
)


def test_resolve_cylinder_corner_geometry_uses_family_keys_and_legacy_stroke_aliases() -> None:
    params = {
        "диаметр_поршня_Ц1": 0.031,
        "диаметр_штока_Ц1": 0.015,
        "ход_штока": 0.25,
        "диаметр_поршня_Ц1_перед_м": 0.033,
        "диаметр_штока_Ц1_зад_м": 0.014,
        "ход_Ц1_перед_м": 0.27,
        "ход_штока_Ц1_зад_м": 0.29,
    }

    geom = resolve_cylinder_corner_geometry(
        params,
        "Ц1",
        default_bore=0.032,
        default_rod=0.016,
        default_stroke=0.25,
    )

    np.testing.assert_allclose(geom["bore_m"], [0.033, 0.033, 0.031, 0.031])
    np.testing.assert_allclose(geom["rod_m"], [0.015, 0.015, 0.014, 0.014])
    np.testing.assert_allclose(geom["stroke_m"], [0.27, 0.27, 0.29, 0.29])
    assert np.all(geom["cap_area_m2"] > geom["rod_area_m2"])


def test_resolve_spring_corner_geometry_tracks_active_family() -> None:
    params = {
        "пружина_масштаб": 1.0,
        "пружина_длина_свободная_м": 0.30,
        "пружина_преднатяг_на_отбое_минимум_м": 0.01,
        "пружина_Ц1_перед_масштаб": 1.1,
        "пружина_Ц1_зад_масштаб": 1.2,
        "пружина_Ц2_перед_масштаб": 1.3,
        "пружина_Ц2_зад_масштаб": 1.4,
        "пружина_Ц2_перед_длина_свободная_м": 0.31,
        "пружина_Ц2_зад_длина_свободная_м": 0.33,
        "пружина_Ц2_перед_преднатяг_на_отбое_минимум_м": 0.02,
        "пружина_Ц2_зад_преднатяг_на_отбое_минимум_м": 0.03,
    }

    spring_c2 = resolve_spring_corner_geometry(params, spring_mode="c2")
    spring_c1 = resolve_spring_corner_geometry(params, spring_mode="c1")
    spring_delta = resolve_spring_corner_geometry(params, spring_mode="delta")

    np.testing.assert_allclose(spring_c2["scale"], [1.3, 1.3, 1.4, 1.4])
    np.testing.assert_allclose(spring_c2["free_length_m"], [0.31, 0.31, 0.33, 0.33])
    np.testing.assert_allclose(spring_c2["rebound_preload_min_m"], [0.02, 0.02, 0.03, 0.03])
    np.testing.assert_allclose(spring_c1["scale"], [1.1, 1.1, 1.2, 1.2])
    np.testing.assert_allclose(spring_delta["scale"], [1.0, 1.0, 1.0, 1.0])


def test_normalize_spring_attachment_mode_aliases() -> None:
    assert normalize_spring_attachment_mode("coilover") == "c1"
    assert normalize_spring_attachment_mode("Ц2") == "c2"
    assert normalize_spring_attachment_mode("both") == "dual"
    assert normalize_spring_attachment_mode("legacy") == "delta"
    assert normalize_spring_attachment_mode("unknown") == "c1"


def test_build_spring_family_runtime_helpers_emit_explicit_family_columns() -> None:
    template = spring_family_runtime_series_template(3)
    assert spring_family_active_flag_column("Ц1", "ЛП") in template
    assert spring_family_runtime_column("длина_м", "Ц2", "ПЗ") in template
    assert template[spring_family_active_flag_column("Ц2", "ПЗ")].shape == (3,)
    assert spring_family_mode_id("c1") == 1
    assert spring_family_mode_id("c2") == 2
    assert spring_family_mode_id("dual") == 3
    assert spring_family_mode_id("delta") == 0

    snap = build_spring_family_runtime_snapshot(
        spring_mode="c2",
        compression_m=np.array([0.01, 0.02, 0.03, 0.04], dtype=float),
        length_m=np.array([0.21, 0.22, 0.23, 0.24], dtype=float),
        gap_to_cap_m=np.array([0.005, 0.006, 0.007, 0.008], dtype=float),
        coil_bind_margin_m=np.array([0.015, 0.016, 0.017, 0.018], dtype=float),
        installed_length_m=np.array([0.25, 0.26, 0.27, 0.28], dtype=float),
    )
    assert snap[spring_family_active_flag_column("Ц2", "ЛП")] == 1.0
    assert snap[spring_family_active_flag_column("Ц1", "ЛП")] == 0.0
    assert np.isnan(snap[spring_family_runtime_column("длина_м", "Ц1", "ЛП")])
    assert snap[spring_family_runtime_column("длина_м", "Ц2", "ЛП")] == 0.21
    assert snap[spring_family_runtime_column("запас_до_coil_bind_м", "Ц2", "ПЗ")] == 0.018

    dual_left, dual_right = split_dual_spring_force_target(
        np.array([100.0, 200.0, 300.0, 400.0], dtype=float),
        np.array([1.0, 3.0, 1.0, 0.0], dtype=float),
        np.array([1.0, 1.0, 3.0, 0.0], dtype=float),
    )
    np.testing.assert_allclose(dual_left + dual_right, [100.0, 200.0, 300.0, 400.0])
    np.testing.assert_allclose(dual_left[:3], [50.0, 150.0, 75.0])
    np.testing.assert_allclose(dual_right[:3], [50.0, 50.0, 225.0])
    assert dual_left[3] == 200.0
    assert dual_right[3] == 200.0

    dual_snap = build_spring_family_runtime_snapshot(
        spring_mode="dual",
        metrics_by_cyl={
            "Ц1": {
                "компрессия_м": np.array([0.01, 0.02, 0.03, 0.04], dtype=float),
                "длина_м": np.array([0.21, 0.22, 0.23, 0.24], dtype=float),
            },
            "Ц2": {
                "компрессия_м": np.array([0.05, 0.06, 0.07, 0.08], dtype=float),
                "длина_м": np.array([0.25, 0.26, 0.27, 0.28], dtype=float),
            },
        },
    )
    assert dual_snap[spring_family_active_flag_column("Ц1", "ЛП")] == 1.0
    assert dual_snap[spring_family_active_flag_column("Ц2", "ЛП")] == 1.0
    assert dual_snap[spring_family_runtime_column("компрессия_м", "Ц1", "ЛП")] == 0.01
    assert dual_snap[spring_family_runtime_column("компрессия_м", "Ц2", "ЛП")] == 0.05


def test_solver_sources_use_family_runtime_helpers() -> None:
    root = Path(__file__).resolve().parents[1]
    camozzi = (root / "pneumo_solver_ui" / "model_pneumo_v9_doublewishbone_camozzi.py").read_text(encoding="utf-8")
    worldroad = (root / "pneumo_solver_ui" / "model_pneumo_v9_mech_doublewishbone_worldroad.py").read_text(encoding="utf-8")
    export = (root / "pneumo_solver_ui" / "anim_export_contract.py").read_text(encoding="utf-8")

    assert "resolve_cylinder_corner_geometry" in camozzi
    assert "resolve_spring_corner_geometry" in camozzi
    assert "масштаб_пружины_vec" in camozzi
    assert "spring_family_runtime_series_template" in camozzi
    assert "build_spring_family_runtime_snapshot" in camozzi
    assert "resolve_cylinder_corner_geometry" in worldroad
    assert "resolve_spring_corner_geometry" in worldroad
    assert "spring_mode == 'c2'" in worldroad
    assert "spring_family_runtime_series_template" in worldroad
    assert "build_spring_family_runtime_snapshot" in worldroad
    assert "spring_family_runtime_column" in export
    assert "_build_family_spring_runtime_block" in export
