from __future__ import annotations

import math
import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_geometry_reference_model import (
    ArtifactReferenceContext,
    CYLINDER_PACKAGING_ADVANCED_FIELDS,
    PackagingPassportEvidenceSnapshot,
    TRUTH_STATE_APPROXIMATE,
    TRUTH_STATE_SOURCE_DATA_CONFIRMED,
    CylinderFamilyReferenceRow,
    build_catalog_source_summary,
    build_geometry_reference_diagnostics_handoff,
    build_producer_truth_gap_map,
    build_solver_points_hardpoints_evidence,
    build_cylinder_match_recommendations,
    build_cylinder_force_bias_estimate,
    build_current_cylinder_package_rows,
    build_current_cylinder_precharge_rows,
    build_current_spring_reference_snapshot,
    build_artifact_reference_context,
    build_geometry_acceptance_evidence,
    build_packaging_passport_evidence,
    build_road_width_evidence,
    build_road_width_reference,
    cylinder_packaging_passport_key,
    load_camozzi_catalog_rows,
)
from pneumo_solver_ui.desktop_geometry_reference_runtime import DesktopGeometryReferenceRuntime
from pneumo_solver_ui.anim_export_contract import (
    HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME,
    VISIBLE_SUSPENSION_FAMILIES,
)
from pneumo_solver_ui.suspension_family_contract import (
    cylinder_axle_geometry_key,
    cylinder_family_key,
    cylinder_precharge_key,
    spring_family_key,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def _geometry_acceptance_mapping() -> dict[str, np.ndarray]:
    time = np.array([0.0, 0.1], dtype=float)
    data: dict[str, np.ndarray] = {"время_с": time}
    corners = {
        "ЛП": (0.75, 0.50),
        "ПП": (0.75, -0.50),
        "ЛЗ": (-0.75, 0.50),
        "ПЗ": (-0.75, -0.50),
    }
    frame_z = np.array([0.50, 0.51], dtype=float)
    wheel_z = np.array([0.30, 0.31], dtype=float)
    road_z = np.array([0.00, 0.00], dtype=float)
    for corner, (x, y) in corners.items():
        data[f"рама_относительно_дороги_{corner}_м"] = frame_z - road_z
        data[f"колесо_относительно_дороги_{corner}_м"] = wheel_z - road_z
        data[f"колесо_относительно_рамы_{corner}_м"] = wheel_z - frame_z
        data[f"frame_corner_{corner}_x_м"] = np.full_like(time, x)
        data[f"frame_corner_{corner}_y_м"] = np.full_like(time, y)
        data[f"frame_corner_{corner}_z_м"] = frame_z
        data[f"wheel_center_{corner}_x_м"] = np.full_like(time, x)
        data[f"wheel_center_{corner}_y_м"] = np.full_like(time, y)
        data[f"wheel_center_{corner}_z_м"] = wheel_z
        data[f"road_contact_{corner}_x_м"] = np.full_like(time, x)
        data[f"road_contact_{corner}_y_м"] = np.full_like(time, y)
        data[f"road_contact_{corner}_z_м"] = road_z
    return data


def _write_reference_artifact(tmp_path: Path) -> dict[str, object]:
    mapping = _geometry_acceptance_mapping()
    cols = list(mapping.keys())
    values = np.column_stack([mapping[col] for col in cols])
    packaging = {
        "schema": "cylinder_packaging.contract.v1",
        "status": "partial",
        "packaging_contract_hash": "pkg-hash-123",
        "required_advanced_fields": ["gland_or_sleeve_position_m"],
        "missing_advanced_fields": ["gland_or_sleeve_position_m"],
        "complete_cylinders": ["cyl1"],
        "axis_only_cylinders": ["cyl2"],
        "cylinders": {
            "cyl1": {
                "contract_complete": True,
                "truth_mode": "full_mesh_allowed",
                "full_mesh_allowed": True,
                "consumer_geometry_fabrication_allowed": False,
                "advanced_fields_missing": [],
                "missing_geometry_fields": [],
                "length_status_by_corner": {
                    "ЛП": "already_finite",
                    "ПП": "already_finite",
                    "ЛЗ": "already_finite",
                    "ПЗ": "already_finite",
                },
            },
            "cyl2": {
                "contract_complete": False,
                "truth_mode": "axis_only_honesty_mode",
                "full_mesh_allowed": False,
                "consumer_geometry_fabrication_allowed": False,
                "advanced_fields_missing": ["gland_or_sleeve_position_m"],
                "missing_geometry_fields": ["explicit_body_axis_world_m"],
                "length_status_by_corner": {
                    "ЛП": "missing",
                    "ПП": "missing",
                    "ЛЗ": "missing",
                    "ПЗ": "missing",
                },
            },
        },
        "policy": {
            "consumer_geometry_fabrication_allowed": False,
            "full_body_rod_piston_requires_complete_passport": True,
            "axis_only_honesty_mode_when_incomplete": True,
        },
    }
    meta = _producer_meta_with_solver_hardpoints({
        "geometry": {
            "road_width_m": 1.5,
            "track_m": 1.0,
            "wheel_width_m": 0.22,
        },
        "packaging": packaging,
        "anim_export_contract_artifacts": {
            "cylinder_packaging_passport": "CYLINDER_PACKAGING_PASSPORT.json",
            "hardpoints_source_of_truth": HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME,
            "geometry_acceptance_json": "geometry_acceptance_report.json",
        },
    })
    npz_path = tmp_path / "anim_latest.npz"
    pointer_path = tmp_path / "anim_latest.json"
    passport_path = tmp_path / "CYLINDER_PACKAGING_PASSPORT.json"
    hardpoints_sot_path = _write_hardpoints_sot(tmp_path)
    geometry_acceptance_path = tmp_path / "geometry_acceptance_report.json"
    np.savez_compressed(
        npz_path,
        main_cols=np.array(cols, dtype=str),
        main_values=values,
        meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=str),
    )
    pointer_path.write_text(
        json.dumps(
            {
                "npz_path": str(npz_path),
                "updated_utc": "2026-04-17T00:00:00+00:00",
                "meta": meta,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    passport = {
        "schema": "cylinder_packaging_passport.v1",
        "updated_utc": "2026-04-17T00:00:00+00:00",
        "npz_path": str(npz_path),
        "pointer_path": str(pointer_path),
        "packaging_status": "partial",
        "packaging_contract_hash": "pkg-hash-123",
        "required_advanced_fields": ["gland_or_sleeve_position_m"],
        "missing_advanced_fields": ["gland_or_sleeve_position_m"],
        "complete_cylinders": ["cyl1"],
        "axis_only_cylinders": ["cyl2"],
        "cylinders": packaging["cylinders"],
        "consumer_policy": {
            "consumer_geometry_fabrication_allowed": False,
            "full_body_rod_piston_requires_complete_passport": True,
        },
    }
    passport_path.write_text(json.dumps(passport, ensure_ascii=False, indent=2), encoding="utf-8")
    geometry_acceptance_path.write_text(
        json.dumps(
            {
                "schema": "geometry_acceptance_report.v1",
                "release_gate": "PASS",
                "release_gate_reason": "solver-point contract consistent",
                "available": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert hardpoints_sot_path.exists()
    return {
        "anim_latest_usable": True,
        "anim_latest_pointer_json": str(pointer_path),
        "anim_latest_npz_path": str(npz_path),
        "anim_latest_pointer_json_exists": True,
        "anim_latest_npz_exists": True,
        "anim_latest_pointer_json_in_workspace": True,
        "anim_latest_npz_in_workspace": True,
        "anim_latest_updated_utc": "2026-04-17T00:00:00+00:00",
        "anim_latest_visual_cache_token": "token-123",
        "anim_latest_meta": meta,
        "anim_latest_cylinder_packaging_passport_path": str(passport_path),
        "anim_latest_cylinder_packaging_passport_exists": True,
        "anim_latest_geometry_acceptance_json_path": str(geometry_acceptance_path),
        "anim_latest_geometry_acceptance_json_exists": True,
    }


def test_desktop_geometry_reference_runtime_builds_reference_snapshots() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    geometry = runtime.geometry_snapshot(dw_min_mm=-80.0, dw_max_mm=80.0)
    component_fit = runtime.component_fit_rows(dw_min_mm=-80.0, dw_max_mm=80.0)
    cylinders = runtime.current_cylinder_rows()
    cylinder_packages = runtime.current_cylinder_package_rows()
    cylinder_precharge = runtime.current_cylinder_precharge_rows()
    springs = runtime.current_spring_snapshot()
    catalog = runtime.cylinder_catalog_rows()
    guide = runtime.parameter_guide_rows("давление", limit=8)
    component_passport = runtime.component_passport_rows()
    road_width = runtime.road_width_reference()
    acceptance = runtime.geometry_acceptance_evidence()

    assert geometry.base_path.name.endswith(".json")
    assert len(geometry.families) == 4
    assert any(row.motion_ratio_peak > 0.0 for row in geometry.families)
    assert len(component_fit) == 4
    assert all(row.family for row in component_fit)
    assert all(row.action_summary for row in component_fit)
    assert len(cylinders) == 4
    assert all(row.cap_area_cm2 > 0.0 for row in cylinders)
    assert len(cylinder_packages) == 4
    assert all(row.family for row in cylinder_packages)
    assert len(cylinder_precharge) == 4
    assert all(row.family for row in cylinder_precharge)
    assert len(springs.families) == 4
    assert all(row.family for row in springs.families)
    assert all(hasattr(row, "inner_diameter_mm") for row in springs.families)
    assert all(hasattr(row, "outer_diameter_mm") for row in springs.families)
    assert all(hasattr(row, "free_length_mm") for row in springs.families)
    assert all(hasattr(row, "top_offset_mm") for row in springs.families)
    assert all(hasattr(row, "rebound_preload_min_mm") for row in springs.families)
    assert len(catalog) > 0
    assert all(row.cap_area_cm2 > 0.0 for row in catalog[:5])
    assert len(guide) > 0
    assert any("давление" in row.label.lower() or "давление" in row.description.lower() for row in guide)
    assert component_passport
    assert any("component_passport.json" in row.help_text for row in component_passport)
    assert road_width.parameter_key == "road_width_m"
    assert road_width.unit_label == "м"
    assert road_width.status in {"explicit", "derived_from_track_and_wheel_width", "missing"}
    assert "GAP-008" in road_width.explanation
    assert acceptance.gate == "MISSING"
    assert "solver-point" in acceptance.evidence_required


def test_desktop_geometry_reference_center_uses_split_workspace_with_sidebar() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_geometry_reference_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert 'workspace = ttk.Panedwindow(outer, orient="horizontal")' in src
    assert 'source = ttk.LabelFrame(sidebar, text="Источник", padding=10)' in src
    assert 'quick = ttk.LabelFrame(sidebar, text="Переходы", padding=8)' in src
    assert 'ttk.Button(header_actions, text="Подвеска", command=lambda: self.notebook.select(0)).pack(side="left")' in src
    assert "workspace.add(self.notebook, weight=5)" in src


def test_desktop_geometry_reference_runtime_filters_catalog_variants_and_search() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    variant_labels = runtime.catalog_variant_labels()
    assert variant_labels

    first_variant = variant_labels[0]
    filtered = runtime.cylinder_catalog_rows(variant_label=first_variant, search_query="46.5")

    assert filtered
    assert all(row.variant_label == first_variant for row in filtered)
    assert all(math.isclose(row.TG_mm, 46.5, rel_tol=0.0, abs_tol=1e-9) for row in filtered)


def test_desktop_geometry_reference_runtime_builds_family_match_recommendations() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    recommendations = runtime.cylinder_match_recommendations("Ц1 перед", limit=3)

    assert len(recommendations) == 3
    assert all(item.family == "Ц1 перед" for item in recommendations)
    assert recommendations[0].score <= recommendations[1].score <= recommendations[2].score
    assert all(item.bore_mm > 0 and item.rod_mm > 0 for item in recommendations)
    assert all(item.notes for item in recommendations)
    assert all(hasattr(item, "net_force_delta_N") for item in recommendations)
    assert all(hasattr(item, "bias_direction") for item in recommendations)


def test_desktop_geometry_reference_runtime_builds_cross_component_fit_summary() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    rows = runtime.component_fit_rows(dw_min_mm=-60.0, dw_max_mm=60.0)

    assert len(rows) == 4
    assert any(row.status in {"ok", "warn"} for row in rows)
    assert all(row.recommended_catalog_label for row in rows)
    assert all(row.notes for row in rows)
    assert all(row.action_summary for row in rows)
    assert all(hasattr(row, "cylinder_outer_diameter_mm") for row in rows)
    assert all(hasattr(row, "spring_to_cylinder_clearance_mm") for row in rows)
    assert all(hasattr(row, "recommended_net_force_delta_N") for row in rows)
    assert all(hasattr(row, "recommended_bias_direction") for row in rows)
    assert all(
        any(marker in " ".join(row.notes) for marker in ("clearance", "diameter", "ID"))
        for row in rows
    )


def test_cylinder_precharge_reference_rows_estimate_force_bias_from_absolute_pressures() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    base = runtime.load_base_payload()
    base[cylinder_precharge_key("Ц1", "CAP", "перед")] = 701325.0
    base[cylinder_precharge_key("Ц1", "ROD", "перед")] = 401325.0

    rows = {row.family: row for row in build_current_cylinder_precharge_rows(base)}
    row = rows["Ц1 перед"]

    assert math.isclose(row.cap_precharge_abs_kpa, 701.325, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(row.rod_precharge_abs_kpa, 401.325, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(row.cap_precharge_bar_g, 6.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.rod_precharge_bar_g, 3.0, rel_tol=0.0, abs_tol=1e-9)
    assert row.cap_force_N > row.rod_force_N > 0.0
    assert row.net_force_N > 0.0
    assert row.bias_direction == "extend"
    assert any("bias" in note for note in row.notes)


def test_cylinder_force_bias_estimate_supports_catalog_rows() -> None:
    row = next(item for item in load_camozzi_catalog_rows() if item.bore_mm == 50 and item.rod_mm == 20)

    estimate = build_cylinder_force_bias_estimate(
        row,
        cap_pressure_bar_gauge=6.0,
        rod_pressure_bar_gauge=3.0,
        clamp_negative=False,
    )

    assert estimate.cap_force_N > estimate.rod_force_N > 0.0
    assert estimate.net_force_N > 0.0
    assert estimate.bias_direction == "extend"
    assert any("bias" in note for note in estimate.notes)


def test_cylinder_match_recommendations_keep_current_bias_preferred_when_precharge_known() -> None:
    catalog_rows = tuple(
        item
        for item in load_camozzi_catalog_rows()
        if item.variant_label == "Round tube (tie-rod)" and (item.bore_mm, item.rod_mm) in {(50, 20), (63, 20)}
    )
    current_catalog = next(item for item in catalog_rows if (item.bore_mm, item.rod_mm) == (50, 20))
    current = CylinderFamilyReferenceRow(
        family="Ц1 перед",
        bore_mm=float(current_catalog.bore_mm),
        rod_mm=float(current_catalog.rod_mm),
        stroke_mm=120.0,
        cap_area_cm2=float(current_catalog.cap_area_cm2),
        annulus_area_cm2=float(current_catalog.annulus_area_cm2),
    )
    current_bias = build_cylinder_force_bias_estimate(
        current,
        cap_pressure_bar_gauge=6.0,
        rod_pressure_bar_gauge=3.0,
        clamp_negative=False,
    )
    current_precharge = build_current_cylinder_precharge_rows(
        {
            cylinder_family_key("bore", "Ц1", "перед"): 0.050,
            cylinder_family_key("rod", "Ц1", "перед"): 0.020,
            cylinder_precharge_key("Ц1", "CAP", "перед"): 701325.0,
            cylinder_precharge_key("Ц1", "ROD", "перед"): 401325.0,
        }
    )[0]

    recommendations = build_cylinder_match_recommendations(
        current,
        catalog_rows,
        current_precharge=current_precharge,
        limit=2,
    )

    assert len(recommendations) == 2
    assert recommendations[0].bore_mm == 50
    assert recommendations[0].rod_mm == 20
    assert math.isclose(recommendations[0].net_force_N, current_bias.net_force_N, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(recommendations[0].net_force_delta_N, 0.0, rel_tol=0.0, abs_tol=1e-6)
    assert recommendations[0].bias_direction == "extend"
    assert any("bias" in note for note in recommendations[0].notes)
    assert recommendations[1].net_force_delta_N > 0.0


def test_cylinder_package_reference_rows_report_body_vs_dead_lengths() -> None:
    base: dict[str, float] = {
        cylinder_family_key("bore", "Ц1", "перед"): 0.040,
        cylinder_family_key("rod", "Ц1", "перед"): 0.020,
        cylinder_family_key("stroke", "Ц1", "перед"): 0.120,
        cylinder_axle_geometry_key("outer_diameter_m", "Ц1", "перед"): 0.048,
        cylinder_axle_geometry_key("dead_cap_length_m", "Ц1", "перед"): 0.030,
        cylinder_axle_geometry_key("dead_rod_length_m", "Ц1", "перед"): 0.025,
        cylinder_axle_geometry_key("dead_height_m", "Ц1", "перед"): 0.028,
        cylinder_axle_geometry_key("body_length_m", "Ц1", "перед"): 0.178,
    }

    rows = {row.family: row for row in build_current_cylinder_package_rows(base)}
    row = rows["Ц1 перед"]

    assert math.isclose(row.outer_diameter_mm, 48.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.dead_cap_length_mm, 30.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.dead_rod_length_mm, 25.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.dead_height_mm, 28.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.expected_body_length_mm, 175.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.body_length_mm, 178.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.body_length_gap_mm, 3.0, rel_tol=0.0, abs_tol=1e-9)
    assert any("body" in note for note in row.notes)
    assert row.status == "axis_only"
    assert row.truth_state == TRUTH_STATE_APPROXIMATE
    assert 0.0 < row.completeness_pct < 100.0
    assert "gland_length_m" in row.missing_fields
    assert "body" in row.hidden_elements
    assert "axis-only" in row.explanation

    for field in CYLINDER_PACKAGING_ADVANCED_FIELDS:
        base[cylinder_packaging_passport_key(field, "Ц1", "перед")] = 0.010

    complete = {item.family: item for item in build_current_cylinder_package_rows(base)}["Ц1 перед"]

    assert complete.status == "complete"
    assert complete.truth_state == TRUTH_STATE_SOURCE_DATA_CONFIRMED
    assert math.isclose(complete.completeness_pct, 100.0, rel_tol=0.0, abs_tol=1e-9)
    assert complete.missing_fields == ()
    assert complete.hidden_elements == ()
    assert "complete" in complete.explanation.lower()


def test_geometry_reference_exposes_road_width_contract_and_help_label() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    derived = build_road_width_reference({"колея": 1.0, "wheel_width_m": 0.22})
    explicit = build_road_width_reference({"road_width_m": 1.5, "колея": 1.0, "wheel_width_m": 0.22})
    guide_rows = runtime.parameter_guide_rows("road_width_m", limit=5)

    assert derived.status == "derived_from_track_and_wheel_width"
    assert math.isclose(derived.effective_road_width_m, 1.22, rel_tol=0.0, abs_tol=1e-9)
    assert "declared supplement" in derived.explanation
    assert explicit.status == "explicit"
    assert math.isclose(explicit.effective_road_width_m, 1.5, rel_tol=0.0, abs_tol=1e-9)
    assert guide_rows
    assert any(row.key == "road_width_m" and row.unit_label == "м" and "GAP-008" in row.description for row in guide_rows)


def test_geometry_acceptance_evidence_reports_missing_and_pass_runtime_contract() -> None:
    missing = build_geometry_acceptance_evidence()
    passed = build_geometry_acceptance_evidence(_geometry_acceptance_mapping(), source_label="unit geometry frame")

    assert missing.gate == "MISSING"
    assert missing.available is False
    assert "solver-point" in missing.evidence_required
    assert passed.gate == "PASS"
    assert passed.available is True
    assert len(passed.rows) == 4
    assert all(row.gate == "PASS" for row in passed.rows)
    assert any("gate=PASS" in line for line in passed.summary_lines)


def test_artifact_backed_runtime_reports_missing_without_latest_artifact() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    artifact = runtime.artifact_context({})
    acceptance = runtime.artifact_geometry_acceptance_evidence(artifact)
    handoff = runtime.diagnostics_handoff_evidence(artifact_context=artifact)

    assert artifact.status == "missing"
    assert artifact.source_label == "anim_latest missing"
    assert acceptance.gate == "MISSING"
    assert acceptance.artifact_status == "missing"
    assert any("No latest anim artifact" in item for item in acceptance.warnings)
    assert handoff["schema"] == "geometry_reference_evidence.v1"
    assert handoff["does_not_render_animator_meshes"] is True
    assert "artifact_context" in handoff["evidence_missing"]
    assert handoff["producer_artifact_status"] == "missing"
    assert handoff["packaging_status"] == "missing"
    assert "artifact_context_missing" in handoff["producer_readiness_reasons"]
    assert "artifact_freshness_missing" in handoff["producer_readiness_reasons"]
    assert "geometry_acceptance_not_pass" in handoff["producer_readiness_reasons"]
    assert handoff["producer_evidence_owner"] == "producer_export"
    assert "workspace/exports/anim_latest.npz" in handoff["producer_required_artifacts"]
    assert handoff["consumer_may_fabricate_geometry"] is False
    assert "Reference Center must not fabricate" in handoff["producer_next_action"]


def test_artifact_backed_runtime_reads_npz_acceptance_and_packaging_passport(tmp_path: Path) -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    summary = _write_reference_artifact(tmp_path)
    artifact = runtime.artifact_context(summary)  # type: ignore[arg-type]
    acceptance = runtime.artifact_geometry_acceptance_evidence(artifact)
    packaging = runtime.packaging_passport_evidence(artifact_context=artifact)
    handoff = runtime.diagnostics_handoff_evidence(artifact_context=artifact)

    assert artifact.status == "current"
    assert artifact.packaging_passport_exists is True
    assert acceptance.gate == "PASS"
    assert acceptance.artifact_status == "current"
    assert acceptance.source_path.endswith("anim_latest.npz")
    assert len(acceptance.rows) == 4
    assert all(row.gate == "PASS" for row in acceptance.rows)
    assert packaging.schema == "cylinder_packaging_passport.v1"
    assert packaging.packaging_status == "partial"
    assert packaging.packaging_contract_hash == "pkg-hash-123"
    assert packaging.complete_cylinders == ("cyl1",)
    assert packaging.axis_only_cylinders == ("cyl2",)
    assert packaging.consumer_geometry_fabrication_allowed is False
    assert any(row.cylinder == "cyl2" and row.export_status == "axis_only" for row in packaging.rows)
    assert handoff["packaging_contract_hash"] == "pkg-hash-123"
    assert handoff["geometry_acceptance_gate"] == "PASS"
    assert handoff["producer_artifact_status"] == "partial"
    assert "packaging_status_not_complete" in handoff["producer_readiness_reasons"]
    assert "packaging_mismatch_not_match" in handoff["producer_readiness_reasons"]
    assert handoff["consumer_may_fabricate_geometry"] is False


def test_runtime_can_use_selected_pointer_and_npz_artifact_without_rebinding_latest(tmp_path: Path) -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    summary = _write_reference_artifact(tmp_path)
    pointer_path = str(summary["anim_latest_pointer_json"])
    npz_path = str(summary["anim_latest_npz_path"])

    pointer_artifact = runtime.artifact_context(artifact_path=pointer_path)
    npz_artifact = runtime.artifact_context(artifact_path=npz_path)
    missing_artifact = runtime.artifact_context(artifact_path=tmp_path / "missing_anim_latest.json")

    assert pointer_artifact.status == "historical"
    assert pointer_artifact.source_label.startswith("selected artifact pointer:")
    assert pointer_artifact.pointer_path == pointer_path
    assert pointer_artifact.npz_path == npz_path
    assert pointer_artifact.packaging_passport_exists is True
    assert runtime.artifact_geometry_acceptance_evidence(pointer_artifact).gate == "PASS"
    assert npz_artifact.status == "historical"
    assert npz_artifact.source_label.startswith("selected artifact:")
    assert npz_artifact.pointer_path == ""
    assert npz_artifact.npz_path == npz_path
    assert npz_artifact.meta["geometry"]["road_width_m"] == 1.5
    assert runtime.artifact_geometry_acceptance_evidence(npz_artifact).gate == "PASS"
    assert missing_artifact.status == "stale"
    assert any("stale" in issue for issue in missing_artifact.issues)


def test_runtime_acceptance_and_handoff_helpers_accept_summary_or_artifact_path(tmp_path: Path) -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    summary = _write_reference_artifact(tmp_path)
    pointer_path = str(summary["anim_latest_pointer_json"])

    summary_acceptance = runtime.artifact_geometry_acceptance_evidence(summary=summary)  # type: ignore[arg-type]
    selected_acceptance = runtime.artifact_geometry_acceptance_evidence(artifact_path=pointer_path)
    selected_handoff = runtime.diagnostics_handoff_evidence(artifact_path=pointer_path)

    assert summary_acceptance.gate == "PASS"
    assert selected_acceptance.gate == "PASS"
    assert selected_acceptance.source_path == str(summary["anim_latest_npz_path"])
    assert selected_handoff["artifact_pointer_path"] == pointer_path
    assert selected_handoff["geometry_acceptance_gate"] == "PASS"
    assert selected_handoff["road_width_status"] == "explicit_meta"
    assert selected_handoff["packaging_contract_hash"] == "pkg-hash-123"
    assert selected_handoff["producer_artifact_status"] == "partial"


def test_runtime_reports_selected_artifact_freshness_against_latest(tmp_path: Path) -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    selected_dir = tmp_path / "selected"
    latest_dir = tmp_path / "latest"
    selected_dir.mkdir()
    latest_dir.mkdir()
    selected_summary = _write_reference_artifact(selected_dir)
    latest_summary = _write_reference_artifact(latest_dir)

    selected_path = str(selected_summary["anim_latest_pointer_json"])
    latest_path = str(latest_summary["anim_latest_pointer_json"])
    selected_artifact = runtime.artifact_context(artifact_path=selected_path)
    latest_artifact = runtime.artifact_context(latest_summary)  # type: ignore[arg-type]
    matching_selected_artifact = runtime.artifact_context(artifact_path=latest_path)

    historical = runtime.artifact_freshness_evidence(
        selected_artifact,
        artifact_path=selected_path,
        latest_context=latest_artifact,
    )
    current = runtime.artifact_freshness_evidence(
        matching_selected_artifact,
        artifact_path=latest_path,
        latest_context=latest_artifact,
    )
    latest_mode = runtime.artifact_freshness_evidence(
        latest_artifact,
        latest_context=latest_artifact,
    )

    assert historical["status"] == "historical"
    assert historical["relation"] == "differs_from_latest"
    assert historical["selected_pointer_path"] == selected_path
    assert historical["latest_pointer_path"] == str(latest_summary["anim_latest_pointer_json"])
    assert any("selected NPZ differs from latest NPZ" in issue for issue in historical["issues"])
    assert current["status"] == "current"
    assert current["relation"] == "matches_latest"
    assert latest_mode["status"] == "current"
    assert latest_mode["relation"] == "latest"


def test_runtime_writes_geometry_reference_evidence_for_diagnostics_send(tmp_path: Path) -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    summary = _write_reference_artifact(tmp_path)
    pointer_path = str(summary["anim_latest_pointer_json"])
    artifact = runtime.artifact_context(artifact_path=pointer_path)

    result = runtime.write_diagnostics_handoff_evidence(
        artifact_context=artifact,
        artifact_path=pointer_path,
        exports_dir=tmp_path / "workspace" / "exports",
        send_bundles_dir=tmp_path / "send_bundles",
    )
    workspace_path = Path(result["workspace_path"])
    sidecar_path = Path(result["sidecar_path"])
    workspace_payload = json.loads(workspace_path.read_text(encoding="utf-8"))
    sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert workspace_path.name == "geometry_reference_evidence.json"
    assert sidecar_path.name == "latest_geometry_reference_evidence.json"
    assert workspace_payload == sidecar_payload == result["payload"]
    assert workspace_payload["schema"] == "geometry_reference_evidence.v1"
    assert workspace_payload["artifact_status"] == "historical"
    assert workspace_payload["artifact_freshness_status"] in {"historical", "current"}
    assert workspace_payload["artifact_freshness_relation"] in {
        "differs_from_latest",
        "matches_latest",
        "selected_without_latest",
    }
    assert workspace_payload["artifact_pointer_path"] == pointer_path
    assert workspace_payload["geometry_acceptance_gate"] == "PASS"
    assert workspace_payload["road_width_status"] == "explicit_meta"
    assert workspace_payload["road_width_source"] == "meta.geometry.road_width_m"
    assert workspace_payload["packaging_contract_hash"] == "pkg-hash-123"
    assert workspace_payload["packaging_axis_only_cylinders"] == ["cyl2"]
    assert workspace_payload["evidence_missing"] == []
    assert workspace_payload["producer_artifact_status"] == "partial"
    assert "packaging_status_not_complete" in workspace_payload["producer_readiness_reasons"]
    assert workspace_payload["consumer_may_fabricate_geometry"] is False
    assert workspace_payload["producer_truth_gap_map"]["OG-002"]["status"] == "partial"
    assert workspace_payload["producer_truth_gap_map"]["OG-006"]["status"] in {"ready", "partial"}
    assert workspace_payload["producer_truth_gap_map"]["GAP-008"]["status"] == "ready"
    assert workspace_payload["catalog_source"]["path"].endswith("camozzi_catalog.json")
    assert workspace_payload["catalog_source"]["item_count"] > 0


def test_road_width_evidence_prefers_explicit_meta_and_keeps_missing_gap_warning() -> None:
    explicit = build_road_width_evidence(
        {"колея": 1.0, "wheel_width_m": 0.22},
        artifact_meta={"geometry": {"road_width_m": 1.5}},
    )
    missing = build_road_width_evidence({}, artifact_meta={})

    assert explicit.status == "explicit_meta"
    assert explicit.preferred_source == "meta.geometry.road_width_m"
    assert math.isclose(explicit.effective_road_width_m, 1.5, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(explicit.base_effective_m, 1.22, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(explicit.mismatch_mm, 280.0, rel_tol=0.0, abs_tol=1e-9)
    assert "Animator must not derive it silently" in explicit.explanation
    assert missing.status == "missing"
    assert "GAP-008" in missing.explanation


def _complete_solver_points_hardpoints_meta() -> dict[str, object]:
    families = {family: {"coverage": "full", "corners": {}} for family in VISIBLE_SUSPENSION_FAMILIES}
    return {
        "solver_points": {
            "schema": "solver_points.contract.v1",
            "visible_suspension_skeleton_families": list(VISIBLE_SUSPENSION_FAMILIES),
            "partial_visible_suspension_skeleton_families": [],
            "policy": {
                "consumer_geometry_fabrication_allowed": False,
                "missing_truth_state": "unavailable",
            },
        },
        "hardpoints": {
            "schema": "hardpoints.export.v1",
            "canonical_families": list(VISIBLE_SUSPENSION_FAMILIES),
            "partial_families": [],
            "families": families,
            "policy": {
                "consumer_geometry_fabrication_allowed": False,
                "missing_truth_state": "unavailable",
                "legacy_alias_reconstruction_allowed": False,
            },
        },
        "anim_export_contract_artifacts": {
            "hardpoints_source_of_truth": HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME,
        },
    }


def _producer_meta_with_solver_hardpoints(extra: dict[str, object] | None = None) -> dict[str, object]:
    meta = _complete_solver_points_hardpoints_meta()
    for key, value in dict(extra or {}).items():
        if key == "anim_export_contract_artifacts" and isinstance(value, dict):
            refs = dict(meta.get("anim_export_contract_artifacts") or {})
            refs.update(value)
            meta[key] = refs
        else:
            meta[key] = value
    return meta


def _write_hardpoints_sot(exports_dir: Path, *, complete: bool = True) -> Path:
    exports_dir.mkdir(parents=True, exist_ok=True)
    visible_present = list(VISIBLE_SUSPENSION_FAMILIES) if complete else list(VISIBLE_SUSPENSION_FAMILIES[:-1])
    visible_missing = [] if complete else [VISIBLE_SUSPENSION_FAMILIES[-1]]
    path = exports_dir / HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME
    path.write_text(
        json.dumps(
            {
                "schema": "hardpoints.source_of_truth.v1",
                "complete": complete,
                "visible_required_families": list(VISIBLE_SUSPENSION_FAMILIES),
                "visible_present_families": visible_present,
                "visible_partial_families": [],
                "visible_missing_families": visible_missing,
                "policy": {
                    "consumer_geometry_fabrication_allowed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _current_producer_artifact_context(
    *,
    source_label: str,
    meta: dict[str, object] | None = None,
    exports_dir: str | Path = "C:/workspace/exports",
    geometry_acceptance_exists: bool = True,
    packaging_passport_exists: bool = True,
) -> ArtifactReferenceContext:
    exports_text = str(exports_dir).rstrip("/\\")
    return ArtifactReferenceContext(
        status="current",
        source_label=source_label,
        pointer_path=f"{exports_text}/anim_latest.json",
        npz_path=f"{exports_text}/anim_latest.npz",
        exports_dir=exports_text,
        updated_utc="2026-04-17T00:00:00+00:00",
        visual_cache_token="token",
        meta=meta or {},
        issues=(),
        packaging_passport_path=f"{exports_text}/CYLINDER_PACKAGING_PASSPORT.json",
        packaging_passport_exists=packaging_passport_exists,
        geometry_acceptance_path=f"{exports_text}/geometry_acceptance_report.json",
        geometry_acceptance_exists=geometry_acceptance_exists,
    )


def _complete_packaging_passport_evidence() -> PackagingPassportEvidenceSnapshot:
    return PackagingPassportEvidenceSnapshot(
        artifact_status="current",
        source_label="synthetic complete passport",
        passport_path="C:/workspace/exports/CYLINDER_PACKAGING_PASSPORT.json",
        schema="cylinder_packaging_passport.v1",
        packaging_status="complete",
        packaging_contract_hash="pkg-complete",
        mismatch_status="match",
        complete_cylinders=("cyl1", "cyl2"),
        axis_only_cylinders=(),
        missing_advanced_fields=(),
        consumer_geometry_fabrication_allowed=False,
        warnings=(),
        rows=(),
    )


def _partial_packaging_passport_evidence() -> PackagingPassportEvidenceSnapshot:
    return PackagingPassportEvidenceSnapshot(
        artifact_status="current",
        source_label="synthetic partial passport",
        passport_path="C:/workspace/exports/CYLINDER_PACKAGING_PASSPORT.json",
        schema="cylinder_packaging_passport.v1",
        packaging_status="partial",
        packaging_contract_hash="pkg-partial",
        mismatch_status="match",
        complete_cylinders=("cyl1",),
        axis_only_cylinders=("cyl2",),
        missing_advanced_fields=("gland_or_sleeve_position_m",),
        consumer_geometry_fabrication_allowed=False,
        warnings=(),
        rows=(),
    )


def _failed_geometry_acceptance_evidence():
    mapping = _geometry_acceptance_mapping()
    mapping["колесо_относительно_дороги_ПЗ_м"] = np.array([0.90, 0.91], dtype=float)
    return build_geometry_acceptance_evidence(mapping, source_label="synthetic FAIL frame")


def test_producer_handoff_stays_partial_when_road_width_evidence_is_missing(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _write_hardpoints_sot(exports_dir)
    artifact_meta = _producer_meta_with_solver_hardpoints()
    artifact = _current_producer_artifact_context(
        source_label="synthetic complete artifact without road_width_m",
        meta=artifact_meta,
        exports_dir=exports_dir,
    )
    road_width = build_road_width_evidence({}, artifact_meta=artifact_meta)
    handoff = build_geometry_reference_diagnostics_handoff(
        artifact_context=artifact,
        component_rows=(),
        road_width=road_width,
        packaging=_complete_packaging_passport_evidence(),
        acceptance=build_geometry_acceptance_evidence(
            _geometry_acceptance_mapping(),
            source_label="synthetic PASS frame",
        ),
    )

    assert handoff["geometry_acceptance_gate"] == "PASS"
    assert handoff["packaging_mismatch_status"] == "match"
    assert handoff["road_width_status"] == "missing"
    assert handoff["producer_artifact_status"] == "partial"
    assert "road_width_m" in handoff["evidence_missing"]
    assert handoff["producer_readiness_reasons"] == ["road_width_m_missing"]
    assert handoff["producer_truth_gap_map"]["GAP-008"]["status"] == "missing"
    assert handoff["producer_truth_gap_map"]["GAP-008"]["consumer_may_fabricate_geometry"] is False


def test_producer_handoff_is_ready_with_pass_complete_packaging_and_explicit_road_width(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _write_hardpoints_sot(exports_dir)
    artifact_meta: dict[str, object] = _producer_meta_with_solver_hardpoints(
        {"geometry": {"road_width_m": 1.5}}
    )
    artifact = _current_producer_artifact_context(
        source_label="synthetic ready producer artifact",
        meta=artifact_meta,
        exports_dir=exports_dir,
    )
    road_width = build_road_width_evidence({}, artifact_meta=artifact_meta)
    handoff = build_geometry_reference_diagnostics_handoff(
        artifact_context=artifact,
        component_rows=(),
        road_width=road_width,
        packaging=_complete_packaging_passport_evidence(),
        acceptance=build_geometry_acceptance_evidence(
            _geometry_acceptance_mapping(),
            source_label="synthetic PASS frame",
        ),
    )

    assert handoff["artifact_status"] == "current"
    assert handoff["geometry_acceptance_gate"] == "PASS"
    assert handoff["packaging_status"] == "complete"
    assert handoff["packaging_mismatch_status"] == "match"
    assert handoff["road_width_status"] == "explicit_meta"
    assert handoff["road_width_source"] == "meta.geometry.road_width_m"
    assert math.isclose(handoff["road_width_effective_m"], 1.5, rel_tol=0.0, abs_tol=1e-9)
    assert handoff["producer_artifact_status"] == "ready"
    assert handoff["producer_readiness_reasons"] == []
    assert handoff["evidence_missing"] == []
    assert handoff["consumer_may_fabricate_geometry"] is False
    assert handoff["solver_points_hardpoints_evidence"]["status"] == "ready"
    assert handoff["solver_points_hardpoints_evidence"]["hardpoints_source_of_truth"]["complete"] is True
    assert handoff["consumer_handoff_policy"]["input"]["reference_data_is_editable_master"] is False
    assert handoff["consumer_handoff_policy"]["animator"]["may_fabricate_geometry"] is False
    assert handoff["consumer_handoff_policy"]["diagnostics"]["warning_policy_changed_by_reference_center"] is False
    assert set(handoff["producer_truth_gap_map"]) == {"OG-001", "OG-002", "OG-006", "GAP-008"}
    assert all(entry["status"] == "ready" for entry in handoff["producer_truth_gap_map"].values())
    assert all(
        entry["consumer_may_fabricate_geometry"] is False
        for entry in handoff["producer_truth_gap_map"].values()
    )
    assert handoff["catalog_source"]["path"].endswith("camozzi_catalog.json")
    assert handoff["catalog_source"]["item_count"] > 0


def test_solver_points_hardpoints_evidence_reports_missing_partial_ready_and_fail(tmp_path: Path) -> None:
    acceptance_pass = build_geometry_acceptance_evidence(
        _geometry_acceptance_mapping(),
        source_label="synthetic PASS frame",
    )
    missing = build_solver_points_hardpoints_evidence(
        artifact_context=_current_producer_artifact_context(
            source_label="synthetic artifact without solver/hardpoints blocks",
            meta={"geometry": {"road_width_m": 1.5}},
            exports_dir=tmp_path / "missing_exports",
        ),
        acceptance=acceptance_pass,
    )
    assert missing["status"] == "missing"
    assert "meta_solver_points_missing" in missing["blocking_reasons"]
    assert "meta_hardpoints_missing" in missing["blocking_reasons"]
    assert "hardpoints_source_of_truth_missing" in missing["blocking_reasons"]
    assert missing["consumer_may_fabricate_geometry"] is False

    partial_exports = tmp_path / "partial_exports"
    _write_hardpoints_sot(partial_exports, complete=False)
    partial = build_solver_points_hardpoints_evidence(
        artifact_context=_current_producer_artifact_context(
            source_label="synthetic partial hardpoints SOT",
            meta=_producer_meta_with_solver_hardpoints({"geometry": {"road_width_m": 1.5}}),
            exports_dir=partial_exports,
        ),
        acceptance=acceptance_pass,
    )
    assert partial["status"] == "partial"
    assert "hardpoints_source_of_truth_not_complete" in partial["blocking_reasons"]
    assert partial["hardpoints_source_of_truth"]["exists"] is True
    assert partial["hardpoints_source_of_truth"]["complete"] is False

    ready_exports = tmp_path / "ready_exports"
    _write_hardpoints_sot(ready_exports)
    ready_context = _current_producer_artifact_context(
        source_label="synthetic ready solver/hardpoints evidence",
        meta=_producer_meta_with_solver_hardpoints({"geometry": {"road_width_m": 1.5}}),
        exports_dir=ready_exports,
    )
    ready = build_solver_points_hardpoints_evidence(
        artifact_context=ready_context,
        acceptance=acceptance_pass,
    )
    assert ready["status"] == "ready"
    assert ready["blocking_reasons"] == []
    assert ready["meta_solver_points"]["present"] is True
    assert ready["meta_hardpoints"]["present"] is True
    assert ready["hardpoints_source_of_truth"]["complete"] is True

    failed = build_solver_points_hardpoints_evidence(
        artifact_context=ready_context,
        acceptance=_failed_geometry_acceptance_evidence(),
    )
    assert failed["status"] == "fail"
    assert "geometry_acceptance_fail" in failed["blocking_reasons"]


def test_og001_does_not_become_ready_from_acceptance_pass_alone() -> None:
    artifact_meta: dict[str, object] = {"geometry": {"road_width_m": 1.5}}
    gap_map = build_producer_truth_gap_map(
        artifact_context=_current_producer_artifact_context(
            source_label="synthetic PASS-only artifact",
            meta=artifact_meta,
        ),
        road_width=build_road_width_evidence({}, artifact_meta=artifact_meta),
        packaging=_complete_packaging_passport_evidence(),
        acceptance=build_geometry_acceptance_evidence(
            _geometry_acceptance_mapping(),
            source_label="synthetic PASS frame",
        ),
    )

    assert gap_map["OG-001"]["status"] == "missing"
    assert "meta_solver_points_missing" in gap_map["OG-001"]["blocking_reasons"]
    assert "meta_hardpoints_missing" in gap_map["OG-001"]["blocking_reasons"]
    assert "hardpoints_source_of_truth_missing" in gap_map["OG-001"]["blocking_reasons"]


def test_producer_truth_gap_map_reports_partial_packaging_without_ready() -> None:
    artifact_meta: dict[str, object] = {"geometry": {"road_width_m": 1.5}}
    artifact = _current_producer_artifact_context(
        source_label="synthetic partial packaging artifact",
        meta=artifact_meta,
    )
    gap_map = build_producer_truth_gap_map(
        artifact_context=artifact,
        road_width=build_road_width_evidence({}, artifact_meta=artifact_meta),
        packaging=_partial_packaging_passport_evidence(),
        acceptance=build_geometry_acceptance_evidence(
            _geometry_acceptance_mapping(),
            source_label="synthetic PASS frame",
        ),
    )

    assert gap_map["OG-002"]["status"] == "partial"
    assert "packaging_status_not_complete" in gap_map["OG-002"]["blocking_reasons"]
    assert "axis_only_cylinders_present" in gap_map["OG-002"]["blocking_reasons"]


def test_producer_truth_gap_map_reports_packaging_hash_mismatch_as_partial() -> None:
    artifact_meta: dict[str, object] = {"geometry": {"road_width_m": 1.5}}
    artifact = _current_producer_artifact_context(
        source_label="synthetic packaging drift artifact",
        meta=artifact_meta,
    )
    packaging = PackagingPassportEvidenceSnapshot(
        artifact_status="current",
        source_label="synthetic drifted passport",
        passport_path="C:/workspace/exports/CYLINDER_PACKAGING_PASSPORT.json",
        schema="cylinder_packaging_passport.v1",
        packaging_status="complete",
        packaging_contract_hash="passport-hash",
        mismatch_status="mismatch",
        complete_cylinders=("cyl1", "cyl2"),
        axis_only_cylinders=(),
        missing_advanced_fields=(),
        consumer_geometry_fabrication_allowed=False,
        warnings=("CYLINDER_PACKAGING_PASSPORT.json packaging_contract_hash differs from meta.packaging.",),
        rows=(),
    )
    gap_map = build_producer_truth_gap_map(
        artifact_context=artifact,
        road_width=build_road_width_evidence({}, artifact_meta=artifact_meta),
        packaging=packaging,
        acceptance=build_geometry_acceptance_evidence(
            _geometry_acceptance_mapping(),
            source_label="synthetic PASS frame",
        ),
    )

    assert gap_map["OG-002"]["status"] == "partial"
    assert "packaging_mismatch_not_match" in gap_map["OG-002"]["blocking_reasons"]


def test_producer_truth_gap_map_reports_historical_artifact_as_partial(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _write_hardpoints_sot(exports_dir)
    artifact_meta: dict[str, object] = _producer_meta_with_solver_hardpoints(
        {"geometry": {"road_width_m": 1.5}}
    )
    artifact = _current_producer_artifact_context(
        source_label="synthetic historical artifact",
        meta=artifact_meta,
        exports_dir=exports_dir,
    )
    gap_map = build_producer_truth_gap_map(
        artifact_context=artifact,
        road_width=build_road_width_evidence({}, artifact_meta=artifact_meta),
        packaging=_complete_packaging_passport_evidence(),
        acceptance=build_geometry_acceptance_evidence(
            _geometry_acceptance_mapping(),
            source_label="synthetic PASS frame",
        ),
        artifact_freshness={
            "status": "historical",
            "relation": "differs_from_latest",
            "reason": "Selected artifact differs from latest.",
            "selected_status": "current",
            "latest_status": "current",
        },
    )

    assert gap_map["OG-001"]["status"] == "partial"
    assert gap_map["OG-006"]["status"] == "partial"
    assert "artifact_relation_differs_from_latest" in gap_map["OG-006"]["blocking_reasons"]


def test_producer_truth_gap_map_reports_missing_and_failed_acceptance(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _write_hardpoints_sot(exports_dir)
    artifact_meta: dict[str, object] = _producer_meta_with_solver_hardpoints(
        {"geometry": {"road_width_m": 1.5}}
    )
    artifact = _current_producer_artifact_context(
        source_label="synthetic acceptance artifact",
        meta=artifact_meta,
        exports_dir=exports_dir,
    )
    common = {
        "artifact_context": artifact,
        "road_width": build_road_width_evidence({}, artifact_meta=artifact_meta),
        "packaging": _complete_packaging_passport_evidence(),
    }

    missing = build_producer_truth_gap_map(
        **common,
        acceptance=build_geometry_acceptance_evidence(None, source_label="missing frame"),
    )
    failed = build_producer_truth_gap_map(
        **common,
        acceptance=_failed_geometry_acceptance_evidence(),
    )

    assert missing["OG-001"]["status"] == "missing"
    assert "geometry_acceptance_missing" in missing["OG-001"]["blocking_reasons"]
    assert failed["OG-001"]["status"] == "fail"
    assert failed["OG-002"]["status"] == "fail"
    assert "geometry_acceptance_fail" in failed["OG-001"]["blocking_reasons"]


def test_catalog_source_summary_reports_camozzi_provenance() -> None:
    summary = build_catalog_source_summary()

    assert summary["path"].endswith("camozzi_catalog.json")
    assert summary["exists"] is True
    assert "Camozzi" in summary["source"]
    assert summary["source_pdf"].startswith("https://")
    assert summary["variant_count"] > 0
    assert summary["item_count"] > 0


def test_packaging_passport_reader_surfaces_base_export_mismatch_and_truth_policy(tmp_path: Path) -> None:
    summary = _write_reference_artifact(tmp_path)
    artifact = build_artifact_reference_context(summary)  # type: ignore[arg-type]
    base_rows = build_current_cylinder_package_rows({})
    packaging = build_packaging_passport_evidence(base_rows, artifact_context=artifact)

    assert packaging.source_label == "CYLINDER_PACKAGING_PASSPORT.json"
    assert packaging.mismatch_status == "mismatch"
    assert packaging.consumer_geometry_fabrication_allowed is False
    assert any(row.mismatch_status == "base_missing" for row in packaging.rows)
    assert any("Base/reference packaging differs" in warning for warning in packaging.warnings)


def test_spring_reference_snapshot_keeps_missing_diameter_data_unknown() -> None:
    snapshot = build_current_spring_reference_snapshot({})

    assert len(snapshot.families) == 4
    assert all(not math.isfinite(row.inner_diameter_mm) for row in snapshot.families)
    assert all(not math.isfinite(row.outer_diameter_mm) for row in snapshot.families)


def test_spring_reference_snapshot_exposes_install_contract_and_free_length_gap() -> None:
    base: dict[str, float] = {
        spring_family_key("геом_диаметр_проволоки_м", "Ц1", "перед"): 0.008,
        spring_family_key("геом_диаметр_средний_м", "Ц1", "перед"): 0.060,
        spring_family_key("геом_число_витков_активных", "Ц1", "перед"): 8.0,
        spring_family_key("геом_число_витков_полное", "Ц1", "перед"): 10.0,
        spring_family_key("геом_шаг_витка_м", "Ц1", "перед"): 0.012,
        spring_family_key("геом_G_Па", "Ц1", "перед"): 79.0e9,
        spring_family_key("длина_свободная_м", "Ц1", "перед"): 0.120,
        spring_family_key("верхний_отступ_от_крышки_м", "Ц1", "перед"): 0.015,
        spring_family_key("преднатяг_на_отбое_минимум_м", "Ц1", "перед"): 0.010,
        spring_family_key("запас_до_coil_bind_минимум_м", "Ц1", "перед"): 0.005,
    }

    rows = {row.family: row for row in build_current_spring_reference_snapshot(base).families}
    row = rows["Ц1 перед"]

    assert math.isclose(row.free_length_mm, 120.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.free_length_from_pitch_mm, 116.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.free_length_pitch_gap_mm, 4.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.top_offset_mm, 15.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.rebound_preload_min_mm, 10.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.bind_margin_target_mm, 5.0, rel_tol=0.0, abs_tol=1e-9)


def test_desktop_geometry_reference_runtime_exposes_family_contract_parameter_guides() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    rows = runtime.parameter_guide_rows("coil bind", limit=20)
    precharge_rows = runtime.parameter_guide_rows("предзаряд", limit=20)

    assert rows
    assert any("Пружины по семействам" == row.section_title for row in rows)
    assert any("coil" in row.key.lower() or "coil" in row.description.lower() for row in rows)
    assert precharge_rows
    assert any("Пневматика по семействам" == row.section_title for row in precharge_rows)
    assert any(row.current_value_text for row in precharge_rows)


def test_desktop_geometry_reference_center_keeps_tabbed_desktop_workspace_contract() -> None:
    tool_src = (UI_ROOT / "tools" / "desktop_geometry_reference_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    model_src = (UI_ROOT / "desktop_geometry_reference_model.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_src = (UI_ROOT / "desktop_geometry_reference_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    adapter_src = (UI_ROOT / "desktop_shell" / "adapters" / "desktop_geometry_reference_adapter.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopGeometryReferenceCenter" in tool_src
    assert "ttk.Notebook" in tool_src
    assert "create_scrollable_tab(self.notebook" in tool_src
    assert 'self.notebook.add(geometry_tab_host, text="Подвеска")' in tool_src
    assert 'self.notebook.add(cylinder_tab_host, text="Цилиндры")' in tool_src
    assert 'self.notebook.add(spring_tab_host, text="Пружины")' in tool_src
    assert 'self.notebook.add(guide_tab_host, text="Параметры")' in tool_src
    assert 'self.notebook.add(passport_tab_host, text="Паспорта")' in tool_src
    assert "self.artifact_path_var" in tool_src
    assert "self.artifact_freshness_var" in tool_src
    assert "self.evidence_export_summary_var" in tool_src
    assert 'text="Artifact JSON/NPZ:"' in tool_src
    assert 'text="Artifact freshness:"' in tool_src
    assert 'text="Export evidence for SEND"' in tool_src
    assert "def _browse_artifact_path(self) -> None:" in tool_src
    assert "def _use_latest_artifact(self) -> None:" in tool_src
    assert "def _artifact_context(self):" in tool_src
    assert "def _export_evidence_for_send(self) -> None:" in tool_src
    assert "artifact_path=self._artifact_path()" in tool_src
    assert '("Animator artifacts", "*.json *.npz")' in tool_src
    assert "DesktopGeometryReferenceRuntime()" in tool_src
    assert "def _refresh_geometry_tab(self) -> None:" in tool_src
    assert "def _refresh_cylinder_tab(self) -> None:" in tool_src
    assert "def _on_recommendation_selected(self, _event: object) -> None:" in tool_src
    assert "def _refresh_spring_tab(self) -> None:" in tool_src
    assert "def _refresh_parameter_guide(self) -> None:" in tool_src
    assert "def _refresh_passport_tab(self) -> None:" in tool_src
    assert "attach_tooltip" in tool_src
    assert "show_help_dialog" in tool_src
    assert "self.artifact_summary_var" in tool_src
    assert "self.solver_points_hardpoints_summary_var" in tool_src
    assert "self.solver_points_hardpoints_tree = self._build_tree(" in tool_src
    assert 'text="solver_points / hardpoints producer evidence"' in tool_src
    assert "solver_points_hardpoints_evidence" in tool_src
    assert "Read-only reference/evidence surface" in tool_src
    assert "hardpoints/solver_points remain producer-owned" in tool_src
    assert "self.producer_gap_summary_var" in tool_src
    assert "self.producer_gap_tree = self._build_tree(" in tool_src
    assert 'text="producer truth gap map"' in tool_src
    assert "producer_truth_gap_map" in tool_src
    assert 'text="road_width_m reference / GAP-008"' in tool_src
    assert 'text="Geometry acceptance evidence / GAP-006"' in tool_src
    assert "self.road_width_tree = self._build_tree(" in tool_src
    assert "self.geometry_acceptance_tree = self._build_tree(" in tool_src
    assert "self.component_passport_tree = self._build_tree(" in tool_src
    assert "self.packaging_passport_tree = self._build_tree(" in tool_src
    assert "self.packaging_artifact_tree = self._build_tree(" in tool_src
    assert 'text="export/runtime packaging passport evidence"' in tool_src
    assert "self.catalog_source_summary_var" in tool_src
    assert "Catalog source:" in tool_src
    assert '("unit", "Ед. изм.", 80, "w")' in tool_src
    assert '("layer", "Layer", 120, "w")' in tool_src
    assert '("source", "Source", 220, "w")' in tool_src
    assert "artifact_geometry_acceptance_evidence" in tool_src
    assert "build_catalog_source_summary" in runtime_src
    assert "build_producer_truth_gap_map" in model_src
    assert "build_solver_points_hardpoints_evidence" in model_src
    assert "consumer_handoff_policy" in model_src
    assert "reference_data_is_editable_master" in model_src
    assert "HARDPOINTS_SOURCE_OF_TRUTH.json" in model_src
    assert "producer_truth_gap_map" in model_src
    assert "catalog_source" in model_src
    assert 'workflow_stage="reference"' in adapter_src
    assert 'entry_kind="tool"' in adapter_src
    assert 'launch_contexts=("data", "baseline", "optimization", "results", "animator")' in adapter_src
    assert "artifact_freshness_evidence" in tool_src
    assert "road_width_evidence" in tool_src
    assert "diagnostics_handoff_evidence" in tool_src
    assert "def _producer_readiness_reasons(" in tool_src
    assert "def _producer_readiness_text(" in tool_src
    assert "producer_readiness_reasons=" in tool_src
    assert "producer_artifact_status" in tool_src
    assert "write_diagnostics_handoff_evidence" in tool_src
    assert 'text="Сквозная совместимость компонентов по семействам"' in tool_src
    assert "self.component_fit_summary_var" in tool_src
    assert "self.component_fit_tree = self._build_tree(" in tool_src
    assert '("cyl_od", "Cylinder OD, мм", 110, "e")' in tool_src
    assert '("spring_id", "Spring ID, мм", 110, "e")' in tool_src
    assert '("clearance", "ID-OD, мм", 90, "e")' in tool_src
    assert '("od", "OD, мм", 90, "e")' in tool_src
    assert '("body", "Body, мм", 90, "e")' in tool_src
    assert '("body_need", "Stroke+dead, мм", 110, "e")' in tool_src
    assert '("body_gap", "Δbody, мм", 90, "e")' in tool_src
    assert '("pkg_status", "Pkg status", 100, "w")' in tool_src
    assert '("pkg_complete", "Pkg, %", 80, "e")' in tool_src
    assert '("truth", "Truth state", 170, "w")' in tool_src
    assert '("dnet", "ΔFnet rec, Н", 110, "e")' in tool_src
    assert '("bias", "Bias rec", 90, "w")' in tool_src
    assert '("B", "B, мм", 80, "e")' in tool_src
    assert '("E", "E, мм", 80, "e")' in tool_src
    assert '("TG", "TG, мм", 80, "e")' in tool_src
    assert 'text="Текущий precharge / force bias из base"' in tool_src
    assert "self.cylinder_precharge_summary_var" in tool_src
    assert "self.current_cylinder_precharge_tree = self._build_tree(" in tool_src
    assert '("pcap_abs", "Pcap abs, кПа", 100, "e")' in tool_src
    assert '("f_net", "Fnet, Н", 100, "e")' in tool_src
    assert "text=\"Рекомендованные каталожные варианты для текущего family\"" in tool_src
    assert '("dnet", "ΔFnet, Н", 100, "e")' in tool_src
    assert '("bias", "Bias", 80, "w")' in tool_src
    assert '("inner", "ID, мм", 80, "e")' in tool_src
    assert '("outer", "OD, мм", 80, "e")' in tool_src
    assert 'text="Текущий spring install contract из base"' in tool_src
    assert "self.spring_install_summary_var" in tool_src
    assert "self.current_spring_install_tree = self._build_tree(" in tool_src
    assert '("free_gap", "ΔLfree, мм", 90, "e")' in tool_src
    assert '("rebound", "Rebound min, мм", 110, "e")' in tool_src
    assert '(\"current\", \"Текущее\", 140, \"w\")' in tool_src
    assert "self.cylinder_recommendation_var" in tool_src
    assert "self.recommendation_tree = self._build_tree(" in tool_src
    assert "def on_host_close(self) -> None:" in tool_src
    assert "def main() -> int:" in tool_src

    assert "class GeometryReferenceSnapshot" in model_src
    assert "class CylinderCatalogRow" in model_src
    assert "class CylinderForceBiasEstimate" in model_src
    assert "class CylinderMatchRecommendation" in model_src
    assert "class CylinderPackageReferenceRow" in model_src
    assert "class CylinderPrechargeReferenceRow" in model_src
    assert "class ComponentPassportCatalogRow" in model_src
    assert "class ComponentFitReferenceRow" in model_src
    assert "class ArtifactReferenceContext" in model_src
    assert "class PackagingPassportEvidenceSnapshot" in model_src
    assert "class RoadWidthEvidence" in model_src
    assert "class RoadWidthReference" in model_src
    assert "class GeometryAcceptanceEvidenceSnapshot" in model_src
    assert "class SpringReferenceSnapshot" in model_src
    assert "def build_geometry_reference_snapshot(" in model_src
    assert "def build_geometry_acceptance_evidence(" in model_src
    assert "def build_artifact_reference_context(" in model_src
    assert "def build_geometry_acceptance_evidence_from_artifact(" in model_src
    assert "def build_packaging_passport_evidence(" in model_src
    assert "def build_geometry_reference_diagnostics_handoff(" in model_src
    assert "def build_cylinder_force_bias_estimate(" in model_src
    assert "def build_current_cylinder_package_rows(" in model_src
    assert "def build_current_cylinder_precharge_rows(" in model_src
    assert "def build_current_cylinder_reference_rows(" in model_src
    assert "def build_current_cylinder_outer_diameter_rows(" in model_src
    assert "def build_cylinder_match_recommendations(" in model_src
    assert "def build_component_fit_reference_rows(" in model_src
    assert "def build_current_spring_reference_snapshot(" in model_src
    assert "def build_parameter_guide_rows(" in model_src
    assert "def build_road_width_reference(" in model_src
    assert "def load_component_passport_catalog_rows(" in model_src
    assert "def cylinder_packaging_passport_key(" in model_src
    assert "def _build_family_parameter_guide_rows(" in model_src

    assert "class DesktopGeometryReferenceRuntime" in runtime_src
    assert "def _artifact_summary_from_path(" in runtime_src
    assert "def geometry_snapshot(" in runtime_src
    assert "def current_cylinder_package_rows(" in runtime_src
    assert "def current_cylinder_rows(" in runtime_src
    assert "def current_cylinder_precharge_rows(" in runtime_src
    assert "def current_spring_snapshot(" in runtime_src
    assert "def component_fit_rows(" in runtime_src
    assert "def cylinder_catalog_rows(" in runtime_src
    assert "def cylinder_match_recommendations(" in runtime_src
    assert "def parameter_guide_rows(" in runtime_src
    assert "def component_passport_rows(" in runtime_src
    assert "def road_width_reference(" in runtime_src
    assert "def geometry_acceptance_evidence(" in runtime_src
    assert "def artifact_context(" in runtime_src
    assert "artifact_path: str | Path | None = None" in runtime_src
    assert "def artifact_geometry_acceptance_evidence(" in runtime_src
    assert "def artifact_freshness_evidence(" in runtime_src
    assert "def road_width_evidence(" in runtime_src
    assert "def packaging_passport_evidence(" in runtime_src
    assert "def diagnostics_handoff_evidence(" in runtime_src
    assert "def write_diagnostics_handoff_evidence(" in runtime_src
    assert '"geometry_reference_evidence.json"' in runtime_src
    assert '"latest_geometry_reference_evidence.json"' in runtime_src
