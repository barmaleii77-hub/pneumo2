from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_runtime_proof_cli_contract_is_exposed() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_mnemo" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "--runtime-proof" in src
    assert "--runtime-proof-offscreen" in src
    assert "--runtime-proof-validate" in src
    assert "--runtime-proof-startup-budget-s" in src
    assert "write_desktop_mnemo_runtime_proof" in src
    assert "validate_desktop_mnemo_runtime_proof" in src


def test_desktop_mnemo_runtime_proof_collects_and_validates_offscreen(tmp_path: Path) -> None:
    from pneumo_solver_ui.desktop_mnemo.runtime_proof import (
        DESKTOP_MNEMO_RUNTIME_PROOF_JSON_NAME,
        write_desktop_mnemo_runtime_proof,
        validate_desktop_mnemo_runtime_proof,
    )

    output = write_desktop_mnemo_runtime_proof(
        tmp_path,
        offscreen=True,
        startup_budget_s=3.0,
    )
    proof_path = tmp_path / DESKTOP_MNEMO_RUNTIME_PROOF_JSON_NAME

    assert output["schema"] == "desktop_mnemo_runtime_proof_output.v1"
    assert output["status"] == "PASS"
    assert output["release_readiness"] == "PENDING_REAL_WINDOWS_VISUAL_CHECK"
    assert proof_path.exists()

    validation = validate_desktop_mnemo_runtime_proof(proof_path)
    assert validation["ok"] is True
    assert validation["automated_status"] == "PASS"
    assert validation["release_readiness"] == "PENDING_REAL_WINDOWS_VISUAL_CHECK"
    assert validation["warnings"] == ["real Windows visual/no-hang verification is still pending"]


def test_send_bundle_evidence_manifest_tracks_desktop_mnemo_runtime_proof(tmp_path: Path) -> None:
    from pneumo_solver_ui.tools.send_bundle_evidence import build_evidence_manifest

    evidence = build_evidence_manifest(
        zip_path=tmp_path / "bundle.zip",
        names=["workspace/exports/desktop_mnemo_runtime_proof.json"],
        meta={"trigger": "pytest"},
        stage="pytest",
    )
    evidence_ids = {row["evidence_id"]: row for row in evidence["evidence_classes"]}

    assert evidence_ids["BND-022"]["required"] is True
    assert evidence_ids["BND-022"]["required_reason"] == "desktop_mnemo_runtime_claimed"
    assert evidence_ids["BND-022"]["status"] == "present"
    assert "workspace/exports/desktop_mnemo_runtime_proof.json" in evidence_ids["BND-022"]["present_paths"]
