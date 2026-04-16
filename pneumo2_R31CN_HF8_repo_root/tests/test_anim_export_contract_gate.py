from __future__ import annotations

from pathlib import Path

import json
import pandas as pd

from pneumo_solver_ui.anim_export_contract import (
    build_packaging_block,
    CYLINDER_PACKAGING_PASSPORT_JSON_NAME,
    HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME,
    augment_anim_latest_meta,
    ensure_cylinder_length_columns,
    validate_anim_export_contract_meta,
    write_anim_export_contract_artifacts,
)
from pneumo_solver_ui.desktop_geometry_reference_model import (
    build_current_cylinder_package_rows,
    build_packaging_passport_evidence,
)
from pneumo_solver_ui.solver_points_contract import CORNERS


VISIBLE_FAMILIES = (
    "frame_corner",
    "wheel_center",
    "road_contact",
    "lower_arm_frame_front",
    "lower_arm_frame_rear",
    "lower_arm_hub_front",
    "lower_arm_hub_rear",
    "upper_arm_frame_front",
    "upper_arm_frame_rear",
    "upper_arm_hub_front",
    "upper_arm_hub_rear",
    "cyl1_top",
    "cyl1_bot",
    "cyl2_top",
    "cyl2_bot",
)


def _build_df() -> pd.DataFrame:
    row = {"время_с": 0.0}
    base = 0.0
    for family in VISIBLE_FAMILIES:
        for idx, corner in enumerate(CORNERS):
            row[f"{family}_{corner}_x_м"] = base + idx + 0.1
            row[f"{family}_{corner}_y_м"] = base + idx + 0.2
            row[f"{family}_{corner}_z_м"] = base + idx + 0.3
        base += 1.0
    for corner in CORNERS:
        row[f"длина_цилиндра_{corner}_м"] = 0.5
        row[f"длина_цилиндра_Ц2_{corner}_м"] = 0.55
        row[f"положение_штока_{corner}_м"] = 0.1
        row[f"положение_штока_Ц2_{corner}_м"] = 0.11
    return pd.DataFrame([row])


def _build_meta() -> dict:
    return {
        "geometry": {
            "wheelbase_m": 1.5,
            "track_m": 1.0,
            "wheel_radius_m": 0.3,
            "wheel_width_m": 0.2,
            "road_width_m": 1.2,
            "frame_length_m": 1.8,
            "frame_width_m": 0.3,
            "frame_height_m": 0.5,
            "cylinder_wall_thickness_m": 0.003,
            "dead_volume_chamber_m3": 1.5e-5,
            "cyl1_bore_diameter_m": 0.032,
            "cyl1_rod_diameter_m": 0.016,
            "cyl2_bore_diameter_m": 0.05,
            "cyl2_rod_diameter_m": 0.014,
            "cyl1_stroke_front_m": 0.25,
            "cyl1_stroke_rear_m": 0.25,
            "cyl2_stroke_front_m": 0.25,
            "cyl2_stroke_rear_m": 0.25,
            "cyl1_outer_diameter_m": 0.038,
            "cyl2_outer_diameter_m": 0.056,
            "cyl1_dead_cap_length_m": 0.018,
            "cyl1_dead_rod_length_m": 0.024,
            "cyl2_dead_cap_length_m": 0.007,
            "cyl2_dead_rod_length_m": 0.008,
            "cyl1_dead_height_m": 0.018,
            "cyl2_dead_height_m": 0.007,
            "cyl1_body_length_front_m": 0.29,
            "cyl1_body_length_rear_m": 0.29,
            "cyl2_body_length_front_m": 0.27,
            "cyl2_body_length_rear_m": 0.27,
            "spring_cyl1_front_wire_diameter_m": 0.008,
            "spring_cyl1_front_mean_diameter_m": 0.060,
            "spring_cyl1_front_inner_diameter_m": 0.052,
            "spring_cyl1_front_outer_diameter_m": 0.068,
            "spring_cyl1_front_free_length_m": 0.31,
            "spring_cyl1_front_solid_length_m": 0.085,
            "spring_cyl1_front_top_offset_m": 0.02,
            "spring_cyl1_front_coil_bind_margin_min_m": 0.005,
            "spring_cyl1_front_rebound_preload_min_m": 0.01,
            "spring_cyl2_front_wire_diameter_m": 0.007,
            "spring_cyl2_front_mean_diameter_m": 0.072,
            "spring_cyl2_front_inner_diameter_m": 0.065,
            "spring_cyl2_front_outer_diameter_m": 0.079,
            "spring_cyl2_front_free_length_m": 0.30,
            "spring_cyl2_front_solid_length_m": 0.084,
            "spring_cyl2_front_top_offset_m": 0.019,
            "spring_cyl2_front_coil_bind_margin_min_m": 0.005,
            "spring_cyl2_front_rebound_preload_min_m": 0.01,
        },
        "scenario_kind": "ring",
        "road_len_m": 100.0,
        "vx0_м_с": 10.0,
        "dt": 0.01,
        "t_end": 1.0,
        "road_csv": "anim_latest_road_csv.csv",
    }


def test_validate_anim_export_contract_warns_on_partial_packaging() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    packaging_again = build_packaging_block(meta, df_fixed, length_repair=length_repair)
    report = validate_anim_export_contract_meta(meta)
    assert report["level"] == "WARN"
    assert report["summary"]["visible_present_family_count"] == len(VISIBLE_FAMILIES)
    assert report["summary"]["has_solver_points_block"] is True
    assert report["summary"]["has_hardpoints_block"] is True
    assert report["summary"]["has_packaging_block"] is True
    assert report["summary"]["packaging_truth_ready"] is False
    assert report["summary"]["axis_only_cylinders"] == ["cyl1", "cyl2"]
    assert report["summary"]["contract_drift_failures"] == []
    assert report["summary"]["fake_geometry_failures"] == []
    assert meta["packaging"]["packaging_contract_hash"] == packaging_again["packaging_contract_hash"]
    assert any("shared axle fallback" in msg for msg in report["warnings"])


def test_validate_anim_export_contract_fails_on_missing_truth_blocks() -> None:
    report = validate_anim_export_contract_meta({})

    assert report["level"] == "FAIL"
    assert any("missing meta.solver_points" in msg for msg in report["messages"])
    assert any("missing meta.hardpoints" in msg for msg in report["messages"])


def test_write_anim_export_contract_artifacts_writes_files(tmp_path: Path) -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    report = validate_anim_export_contract_meta(meta)
    meta["anim_export_validation"] = dict(report["summary"])
    meta["anim_export_validation"]["validation_level"] = report["level"]
    out = write_anim_export_contract_artifacts(
        tmp_path,
        meta=meta,
        updated_utc="2026-03-30T00:00:00+00:00",
        npz_path=tmp_path / "anim_latest.npz",
        pointer_path=tmp_path / "anim_latest.json",
    )
    assert Path(out["sidecar_path"]).exists()
    assert Path(out["validation_json_path"]).exists()
    assert Path(out["hardpoints_source_of_truth_path"]).exists()
    assert Path(out["cylinder_packaging_passport_path"]).exists()
    assert Path(tmp_path / HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME).exists()
    assert Path(tmp_path / CYLINDER_PACKAGING_PASSPORT_JSON_NAME).exists()
    hardpoints = json.loads(Path(out["hardpoints_source_of_truth_path"]).read_text(encoding="utf-8"))
    packaging = json.loads(Path(out["cylinder_packaging_passport_path"]).read_text(encoding="utf-8"))
    assert hardpoints["schema"] == "hardpoints.source_of_truth.v1"
    assert hardpoints["visible_missing_families"] == []
    assert hardpoints["hardpoints_contract_hash"]
    assert hardpoints["families"]["cyl1_top"]["family_contract_hash"]
    assert hardpoints["policy"]["consumer_geometry_fabrication_allowed"] is False
    assert packaging["schema"] == "cylinder_packaging_passport.v1"
    assert packaging["packaging_contract_hash"]
    assert packaging["axis_only_cylinders"] == ["cyl1", "cyl2"]
    assert packaging["cylinders"]["cyl1"]["mount_families"]["top"] == "cyl1_top"
    assert packaging["cylinders"]["cyl1"]["truth_mode"] == "axis_only_honesty_mode"
    assert packaging["cylinders"]["cyl1"]["full_mesh_allowed"] is False
    assert packaging["consumer_policy"]["consumer_geometry_fabrication_allowed"] is False
    reference_evidence = build_packaging_passport_evidence(
        build_current_cylinder_package_rows({}),
        artifact_meta=meta,
        passport_path=out["cylinder_packaging_passport_path"],
    )
    assert reference_evidence.schema == "cylinder_packaging_passport.v1"
    assert reference_evidence.packaging_contract_hash == packaging["packaging_contract_hash"]
    assert reference_evidence.axis_only_cylinders == ("cyl1", "cyl2")
    assert reference_evidence.consumer_geometry_fabrication_allowed is False
    assert all(not row.consumer_geometry_fabrication_allowed for row in reference_evidence.rows)
    md = Path(out["validation_md_path"]).read_text(encoding="utf-8")
    assert "packaging_truth_ready" in md
    assert "visible_present_family_count" in md


def test_validate_anim_export_contract_fails_on_spring_cylinder_interference() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = _build_meta()
    meta["geometry"]["spring_cyl1_front_inner_diameter_m"] = 0.030
    meta = augment_anim_latest_meta(meta, df_main=df_fixed, length_repair=length_repair)
    report = validate_anim_export_contract_meta(meta)
    assert report["level"] == "FAIL"
    assert any("spring/cylinder interference" in msg for msg in report["messages"])


def test_validate_anim_export_contract_fails_on_spring_spring_interference() -> None:
    df = _build_df()
    for corner in ("ЛП", "ПП"):
        df.loc[:, f"cyl2_top_{corner}_x_м"] = df.loc[:, f"cyl1_top_{corner}_x_м"] + 0.01
        df.loc[:, f"cyl2_bot_{corner}_x_м"] = df.loc[:, f"cyl1_bot_{corner}_x_м"] + 0.01
        df.loc[:, f"cyl2_top_{corner}_y_м"] = df.loc[:, f"cyl1_top_{corner}_y_м"]
        df.loc[:, f"cyl2_bot_{corner}_y_м"] = df.loc[:, f"cyl1_bot_{corner}_y_м"]
        df.loc[:, f"cyl2_top_{corner}_z_м"] = df.loc[:, f"cyl1_top_{corner}_z_м"]
        df.loc[:, f"cyl2_bot_{corner}_z_м"] = df.loc[:, f"cyl1_bot_{corner}_z_м"]
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    report = validate_anim_export_contract_meta(meta)
    assert report["level"] == "FAIL"
    assert any("spring/spring interference" in msg for msg in report["messages"])


def test_validate_anim_export_contract_fails_on_contract_drift() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    meta["hardpoints"]["families"].pop("lower_arm_frame_front")

    report = validate_anim_export_contract_meta(meta)

    assert report["level"] == "FAIL"
    assert any("contract drift" in msg for msg in report["messages"])


def test_validate_anim_export_contract_fails_on_partial_visible_hardpoint_triplet() -> None:
    df = _build_df().drop(columns=["lower_arm_frame_front_ЛП_z_м"])
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)

    report = validate_anim_export_contract_meta(meta)

    assert report["level"] == "FAIL"
    assert "lower_arm_frame_front" in report["summary"]["visible_partial_families"]
    assert any("partial visible hardpoint families" in msg for msg in report["messages"])


def test_validate_anim_export_contract_fails_on_missing_family_hash() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    meta["hardpoints"]["families"]["cyl1_top"].pop("family_contract_hash")

    report = validate_anim_export_contract_meta(meta)

    assert report["level"] == "FAIL"
    assert any("missing hardpoint family_contract_hash" in msg for msg in report["messages"])


def test_validate_anim_export_contract_fails_on_stale_validation_summary() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    meta["anim_export_validation"] = {
        "visible_present_family_count": 0,
        "visible_missing_families": ["stale_fake_family"],
        "packaging_status": "complete",
        "packaging_truth_ready": True,
    }

    report = validate_anim_export_contract_meta(meta)

    assert report["level"] == "FAIL"
    assert any("anim_export_validation" in msg and "current" in msg for msg in report["messages"])


def test_validate_anim_export_contract_fails_on_fake_geometry_source() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    meta["hardpoints"]["families"]["cyl1_top"]["source_kind"] = "fabricated"

    report = validate_anim_export_contract_meta(meta)

    assert report["level"] == "FAIL"
    assert any("fake/invented geometry" in msg for msg in report["messages"])


def test_validate_anim_export_contract_rejects_full_mesh_without_packaging_passport() -> None:
    df = _build_df()
    df_fixed, length_repair = ensure_cylinder_length_columns(df)
    meta = augment_anim_latest_meta(_build_meta(), df_main=df_fixed, length_repair=length_repair)
    meta["packaging"]["cylinders"]["cyl1"]["full_mesh_allowed"] = True

    report = validate_anim_export_contract_meta(meta)

    assert report["level"] == "FAIL"
    assert any("full mesh allowed without complete passport" in msg for msg in report["messages"])
