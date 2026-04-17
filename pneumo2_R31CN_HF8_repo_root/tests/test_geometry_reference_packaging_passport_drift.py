from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.desktop_geometry_reference_model import (
    CylinderPackageReferenceRow,
    build_packaging_passport_evidence,
)


def _complete_base_rows() -> tuple[CylinderPackageReferenceRow, ...]:
    return (
        CylinderPackageReferenceRow(
            family="Ц1 перед",
            outer_diameter_mm=38.0,
            dead_cap_length_mm=18.0,
            dead_rod_length_mm=24.0,
            dead_height_mm=18.0,
            body_length_mm=290.0,
            expected_body_length_mm=290.0,
            body_length_gap_mm=0.0,
            notes=(),
            status="complete",
            completeness_pct=100.0,
        ),
        CylinderPackageReferenceRow(
            family="Ц2 перед",
            outer_diameter_mm=56.0,
            dead_cap_length_mm=7.0,
            dead_rod_length_mm=8.0,
            dead_height_mm=7.0,
            body_length_mm=270.0,
            expected_body_length_mm=270.0,
            body_length_gap_mm=0.0,
            notes=(),
            status="complete",
            completeness_pct=100.0,
        ),
    )


def _complete_passport(hash_value: str) -> dict[str, object]:
    return {
        "schema": "cylinder_packaging_passport.v1",
        "packaging_status": "complete",
        "packaging_contract_hash": hash_value,
        "complete_cylinders": ["cyl1", "cyl2"],
        "axis_only_cylinders": [],
        "cylinders": {
            "cyl1": {
                "contract_complete": True,
                "truth_mode": "full_mesh_allowed",
                "full_mesh_allowed": True,
                "consumer_geometry_fabrication_allowed": False,
            },
            "cyl2": {
                "contract_complete": True,
                "truth_mode": "full_mesh_allowed",
                "full_mesh_allowed": True,
                "consumer_geometry_fabrication_allowed": False,
            },
        },
        "consumer_policy": {
            "consumer_geometry_fabrication_allowed": False,
            "full_body_rod_piston_requires_complete_passport": True,
        },
    }


def test_packaging_passport_evidence_fails_meta_hash_drift(tmp_path: Path) -> None:
    passport_path = tmp_path / "CYLINDER_PACKAGING_PASSPORT.json"
    passport_path.write_text(
        json.dumps(_complete_passport("passport-hash"), ensure_ascii=False),
        encoding="utf-8",
    )
    meta = {
        "packaging": {
            "status": "complete",
            "packaging_contract_hash": "meta-hash",
        }
    }

    evidence = build_packaging_passport_evidence(
        _complete_base_rows(),
        artifact_meta=meta,
        passport_path=passport_path,
    )

    assert evidence.packaging_contract_hash == "passport-hash"
    assert evidence.mismatch_status == "mismatch"
    assert all(row.mismatch_status == "match" for row in evidence.rows)
    assert any("packaging_contract_hash differs from meta.packaging" in warning for warning in evidence.warnings)


def test_packaging_passport_evidence_accepts_matching_meta_hash(tmp_path: Path) -> None:
    passport_path = tmp_path / "CYLINDER_PACKAGING_PASSPORT.json"
    passport_path.write_text(
        json.dumps(_complete_passport("same-hash"), ensure_ascii=False),
        encoding="utf-8",
    )
    meta = {
        "packaging": {
            "status": "complete",
            "packaging_contract_hash": "same-hash",
        }
    }

    evidence = build_packaging_passport_evidence(
        _complete_base_rows(),
        artifact_meta=meta,
        passport_path=passport_path,
    )

    assert evidence.packaging_contract_hash == "same-hash"
    assert evidence.mismatch_status == "match"
    assert evidence.warnings == ()
